"""고정 원본에 결속한 provider 증거를 별도 저장한다. 자동 복구·공개 반영은 수행하지 않는다."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.ledger.private_file import private_file_permissions_ok
from src.llm_batch.ledger.recovery_provider_journal import canonical_bytes, canonical_sha256
from src.llm_batch.measurement.recovery_execution_readback import read_strict_json
from src.llm_batch.measurement.recovery_provider_contract import bind_recovery_provider_plan
from src.llm_batch.measurement.recovery_provider_readback import build_provider_report, validate_provider_report
from src.llm_batch.runtime.execution_config import apply_profile_resources, observe_process_resources
from src.llm_batch.runtime.recovery_provider_transport import RecoveryProviderRunner
from tools.run_recovery_execution_readback import _file
from tools.run_recovery_simulation import _dashboard_health, _dashboard_url, _check_resources, _identifier


def _ref(path, raw):
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _save(bound, path, raw, *, replay=True):
    path = bound.assert_output_path(path)
    if os.path.lexists(path):
        if not replay or _file(path, len(raw)).read_bytes() != raw:
            raise ValueError("기존 provider 산출물과 현재 재판독이 다릅니다")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        bound.assert_output_path(path)
        with path.open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if _file(path, len(raw)).read_bytes() != raw:
        raise ValueError("provider 산출물 저장 재판독 실패")
    return _ref(path, raw)


def _report_markdown(report):
    def value(key):
        v = report[key]
        return "미확정" if v is None else str(v)
    return ("# Provider 복구 증거 저장 결과\n\n"
        + "실행 상태: `" + report["execution_status"] + "`. 공개 guard는 평가하지 않았으며 원래 판정과 공개 결과는 유지한다.\n\n"
        + "- 자료: `" + report["data_kind"] + "`\n"
        + "- 전송: `" + report["transport_mode"] + "`\n"
        + "- 입력: " + value("input_count") + "건, 선택 행 외에는 `NO_PLAN_PROVIDED`\n"
        + "- 확인된 client HTTP 호출: " + value("client_http_invocations") + "\n"
        + "- 실제 외부 HTTP 호출: " + value("actual_external_call_count") + "\n"
        + "- 원격 내부 검색·fallback 호출: 미확정\n"
        + "- 공개 반영: false, 품질·비용 평가: `NOT_ESTIMABLE`\n\n"
        + "원장과 저장된 원시 응답을 독립 판독했다. HTTP 수신 완료는 작품 판정이나 복구 성공을 뜻하지 않는다.\n\n"
        + "계획 SHA: `" + report["plan_sha256"] + "`\n\n"
        + "보고서 SHA: `" + report["report_sha256"] + "`\n")


def _claim_job(bound, root):
    """같은 job의 출력 이동으로 예약/예산을 초기화하지 못하게 고정한다."""
    from src.llm_batch.ledger.recovery_execution_journal import _exclusive_lock
    from src.llm_batch.monitor.recovery_view import _safe
    from src.llm_batch.runtime.recovery_provider_transport import _read, _write_new
    path = _safe(root / ".recovery_provider_jobs" / (bound.job_id + ".json"), root)
    value = {"schema_version": "recovery_provider_job_location_v1", "job_id": bound.job_id,
             "plan_sha256": bound.plan["plan_sha256"], "binding_sha256": bound.plan["binding_sha256"],
             "output_dir": str(bound.output_dir), "journal_path": str(bound.journal_path)}
    raw = canonical_bytes(value)
    with _exclusive_lock(path):
        _safe(path, root)
        if os.path.lexists(path):
            if _read(path, 4096) != raw:
                raise ValueError("동일 provider job의 출력 위치나 원본 참조를 바꿀 수 없습니다")
        else:
            _write_new(path, raw)
        if _read(path, 4096) != raw:
            raise ValueError("provider job 위치 저장 재판독 실패")
    return _ref(path, raw)


def run_recovery_provider(*, plan_path, plan_sha256, hmac_key_path, attempt_id, session_id,
                          root, dashboard_url=None, test_transport=None, clock=None,
                          cancellation=None, headers=None, publish_view=True):
    """별도 계획 한 건을 예약·전송·저장·판독한다. 기존 결과/WAL/key를 만들거나 바꾸지 않는다."""
    if type(publish_view) is not bool:
        raise ValueError("provider companion 발행 여부는 bool이어야 합니다")
    if (os.environ.get("PIPELINE_MEASUREMENT_EXECUTION_MODE", "NORMAL").strip().upper() != "NORMAL"
            or os.environ.get("EXPERT_EXECUTION_PROFILE", "").strip() == "paired-measurement"
            or any(os.environ.get(k, "").strip() for k in (
                "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256", "PIPELINE_MEASUREMENT_PAIR_ID",
                "PIPELINE_MEASUREMENT_ARM", "PIPELINE_MEASUREMENT_RUN_SPEC_PATH",
                "PIPELINE_MEASUREMENT_RUN_SPEC_FILE_SHA256", "PIPELINE_PAIRED_EXECUTION_POLICY_PATH",
                "PIPELINE_PAIRED_EXECUTION_POLICY_SHA256"))):
        raise ValueError("provider 증거 실행은 fresh/paired 계측과 혼합할 수 없습니다")
    for value in (attempt_id, session_id): _identifier(value)
    if attempt_id == session_id:
        raise ValueError("복구 attempt와 session ID는 달라야 합니다")
    if type(plan_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", plan_sha256):
        raise ValueError("명시 계획 파일 SHA256이 필요합니다")
    source, key_path = _file(plan_path, 65536), _file(hmac_key_path, 4096)
    if source == key_path or private_file_permissions_ok(key_path) is not True:
        raise ValueError("기존 비공개 감사 key 파일이 필요합니다")
    source_raw, key_raw = source.read_bytes(), key_path.read_bytes()
    if hashlib.sha256(source_raw).hexdigest() != plan_sha256:
        raise ValueError("provider 계획 파일 지문 불일치")
    try: key_hex = key_raw.decode("ascii").strip().lower()
    except UnicodeError as exc: raise ValueError("감사 key는 ASCII hex64 형식이어야 합니다") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", key_hex):
        raise ValueError("감사 key는 ASCII hex64 형식이어야 합니다")
    bound = bind_recovery_provider_plan(read_strict_json(source_raw), hmac_key=bytes.fromhex(key_hex))
    if test_transport is None and bound.data_kind != "SOURCE_BACKED":
        raise ValueError("합성 또는 종류 미확인 자료는 실제 provider로 보낼 수 없습니다")
    if attempt_id in {bound.base["base_attempt_run_id"], bound.base["export_run_id"]}:
        raise ValueError("원래 실행 ID를 별도 provider attempt로 재사용할 수 없습니다")
    from src.llm_batch.monitor.recovery_view import _safe
    from src.llm_batch.monitor.recovery_provider_view import publish_recovery_provider_view
    root = Path(root).resolve()
    for role in ("result", "manifest"):
        _safe(Path(bound.plan["source_refs"][role]["path"]), root)
    _safe(bound.output_dir, root)
    if source.is_relative_to(bound.output_dir) or key_path.is_relative_to(bound.output_dir):
        raise ValueError("계획과 key는 출력 폴더 밖에 있어야 합니다")
    report_path = bound.assert_output_path(bound.output_dir / "reports/provider_readback.json")
    markdown_path = bound.assert_output_path(bound.output_dir / "reports/provider_readback.md")
    existing = None
    if os.path.lexists(report_path):
        existing = read_strict_json(_file(report_path, 2*1024*1024).read_bytes(), maximum_bytes=2*1024*1024)
        validate_provider_report(existing)
        if canonical_bytes(existing) != canonical_bytes(build_provider_report(bound)):
            raise ValueError("기존 보고서와 provider 원장 판독 불일치")
        if os.path.lexists(markdown_path) and _file(markdown_path, 2*1024*1024).read_bytes() != _report_markdown(existing).encode():
            raise ValueError("기존 provider 보고서 본문 불일치")
    elif os.path.lexists(markdown_path):
        raise ValueError("JSON 없이 남은 provider 보고서를 덮어쓰지 않습니다")
    output = Path(bound.plan["source_refs"]["result"]["path"])
    companion = output.with_name(output.stem + "_recovery_provider_view.json")
    if publish_view and os.path.lexists(companion):
        if existing is None:
            raise ValueError("다른 provider 보고서가 이미 연결돼 있습니다")
        publish_recovery_provider_view(bound, report_path, root=root)
    dashboard_before = _dashboard_health(_dashboard_url(dashboard_url))
    resources_start = apply_profile_resources("low-load-validation", os.environ)
    _check_resources(resources_start)
    job_reference = _claim_job(bound, root)
    def source_check():
        bound.verify_protected_sources()
        registry_raw = _file(job_reference["path"], 4096).read_bytes()
        if _ref(Path(job_reference["path"]), registry_raw) != job_reference:
            raise ValueError("provider job 위치 결속이 바뀌었습니다")
        if _file(source, 65536).read_bytes() != source_raw or _file(key_path, 4096).read_bytes() != key_raw:
            raise ValueError("provider 실행 중 계획 또는 감사 key가 바뀌었습니다")
        return True
    cancelled = cancellation if callable(cancellation) else cancellation.requested if cancellation is not None else lambda: False
    clock_ms = clock if callable(clock) else clock.monotonic_ms if clock is not None else None
    runner = RecoveryProviderRunner(binding=bound.binding, policy=bound.policy,
        requests=bound.requests, journal_path=bound.journal_path, endpoints=bound.endpoints,
        source_check=source_check, cancelled=cancelled, headers=headers,
        test_transport=test_transport, clock_ms=clock_ms)
    request = bound.requests[0]
    execution = runner.request(request["kind"], bound.payload, request_id=request["request_id"])
    report = build_provider_report(bound)
    if existing is not None and canonical_bytes(existing) != canonical_bytes(report):
        raise ValueError("완료된 provider 보고서의 재생 결과가 바뀌었습니다")
    report_raw = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    outputs = [_save(bound, report_path, report_raw),
               _save(bound, markdown_path, _report_markdown(report).encode())]
    reference = publish_recovery_provider_view(bound, report_path, root=root) if publish_view else None
    dashboard_after = _dashboard_health(dashboard_before["url"])
    if dashboard_after != dashboard_before:
        raise ValueError("provider 실행 중 대시보드가 바뀌었습니다. 저장 자료는 보존합니다")
    source_check()
    resources_end = observe_process_resources(os.environ); _check_resources(resources_end)
    if any(resources_start[k] != resources_end[k] for k in ("pid", "priority_class", "affinity_mask", "logical_cpu_count", "numeric_threads")):
        raise ValueError("provider 실행 중 저부하 자원 조건이 바뀌었습니다")
    receipt = {"schema_version": "recovery_provider_workflow_v1",
        "execution_status": report["execution_status"], "guard_status": "GUARD_NOT_EVALUATED",
        "recovery_attempt_id": attempt_id, "recovery_session_id": session_id,
        "plan_sha256": bound.plan["plan_sha256"], "plan_file_sha256": plan_sha256,
        "job_reference": job_reference,
        "execution": execution, "replayed": execution["replayed"],
        "client_http_invocations_this_invocation": execution["transport_invocations_this_invocation"],
        "actual_external_calls_this_invocation": execution["actual_external_calls"],
        "remote_provider_dispatch_count": None, "remote_provider_dispatch_status": "UNKNOWN",
        "reports": outputs, "dashboard_reference": reference, "publish_view": publish_view, "public_apply": False,
        "publication_authority": False, "central_db_write": False,
        "formal_kpi_status": "NOT_ESTIMABLE", "execution_profile": "low-load-validation",
        "resources_start": resources_start, "resources_end": resources_end,
        "dashboard": {"status": "CONNECTED_STANDALONE", "before": dashboard_before,
                      "after": dashboard_after, "visibility_verified": False}}
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    # 현재 invocation 상태는 고정 source/journal 보고서와 분리한다.
    target = bound.output_dir / "reports" / ("workflow_" + uuid4().hex + ".json")
    saved = _save(bound, target, canonical_bytes(receipt), replay=False)
    return {**receipt, "workflow_receipt": saved}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for flag in ("plan", "plan-sha256", "hmac-key-file", "attempt-id", "session-id"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_recovery_provider(plan_path=args.plan, plan_sha256=args.plan_sha256,
            hmac_key_path=args.hmac_key_file, attempt_id=args.attempt_id, session_id=args.session_id, root=ROOT/"out")
    except (OSError, ValueError) as exc:
        print("provider 증거 실행 실패: " + str(exc), file=sys.stderr); return 1
    print(json.dumps(result, ensure_ascii=False)); return 0


if __name__ == "__main__": raise SystemExit(main())
