"""별도 provider 근거 보고서의 파일·base 결속만 읽는다. GET은 실행하지 않는다."""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..measurement.recovery_execution_contract import canonical_sha256
from ..measurement.recovery_execution_readback import read_strict_json
from .recovery_view import _read, _read_ref, _ref, _safe

SCHEMA = "recovery_provider_dashboard_reference_v1"
REPORT_LIMIT = 2 * 1024 * 1024
SOURCE_LIMIT = 16 * 1024 * 1024
REFERENCE_LIMIT = 65536
SCOPE = "FILE_AND_BASE_BINDING_ONLY"


def _view_path(output: Path) -> Path:
    return output.with_name(output.stem + "_recovery_provider_view.json")


def _check_report(report: dict, base: dict) -> None:
    # 이 검산은 순수 보고서 schema/self SHA 확인이다. 원장·key 판독이 아니다.
    from ..measurement.recovery_provider_readback import validate_provider_report

    validate_provider_report(report)
    if (type(report) is not dict or report.get("schema_version") != "recovery_provider_report_v1"
            or type(base) is not dict or canonical_sha256(report.get("base")) != canonical_sha256(base)):
        raise ValueError("provider 보고서와 원래 판정 결속 불일치")
    fixed = {"guard_status": "GUARD_NOT_EVALUATED", "remote_provider_dispatch_count": None,
             "remote_provider_dispatch_status": "UNKNOWN", "public_apply": False,
             "publication_authority": False, "central_db_write": False,
             "formal_kpi_status": "NOT_ESTIMABLE"}
    if any(type(report.get(key)) is not type(value) or report.get(key) != value
           for key, value in fixed.items()):
        raise ValueError("provider 근거 수집 표시 계약 불일치")


def _check_manifest(manifest: dict, base: dict, output: Path) -> None:
    if (type(manifest) is not dict or manifest.get("terminal_artifacts_finalized") is not True
            or manifest.get("publication_scope_id") != base["publication_scope_id"]
            or manifest.get("run_id") != base["export_run_id"]
            or type(manifest.get("output_file")) is not str
            or Path(manifest["output_file"]).absolute() != output):
        raise ValueError("provider base와 원본 종료 manifest 불일치")


def publish_recovery_provider_view(bound_plan, report_path: str | Path, *, root: str | Path) -> dict:
    """고정 원본과 검산된 보고서를 별도 companion으로 연결한다. 덮어쓰지 않는다."""
    from ..measurement.recovery_provider_contract import BoundRecoveryProviderPlan
    from ..measurement.recovery_provider_readback import build_provider_report

    if type(bound_plan) is not BoundRecoveryProviderPlan:
        raise ValueError("검산된 provider 계획이 필요합니다")
    if bound_plan.verify_protected_sources() is not True:
        raise ValueError("provider 원본 보호 검산 실패")
    root = Path(root).resolve()
    plan, base = bound_plan.plan, bound_plan.base
    output = _safe(Path(plan["source_refs"]["result"]["path"]), root)
    manifest_path = _safe(Path(plan["source_refs"]["manifest"]["path"]), root)
    report_path = _safe(Path(report_path), root)
    bound_plan.assert_output_path(report_path)
    report_raw = _read(report_path, root, REPORT_LIMIT)
    report = read_strict_json(report_raw, maximum_bytes=REPORT_LIMIT)
    _check_report(report, base)
    if report["plan_sha256"] != plan["plan_sha256"] or report["data_kind"] != bound_plan.data_kind:
        raise ValueError("provider 보고서 계획·자료 종류 불일치")
    if canonical_sha256(report) != canonical_sha256(build_provider_report(bound_plan)):
        raise ValueError("provider 저장 보고서와 원장·응답 재판독 불일치")
    result_raw = _read_ref(plan["source_refs"]["result"], root, SOURCE_LIMIT)
    manifest_raw = _read_ref(plan["source_refs"]["manifest"], root, SOURCE_LIMIT)
    _check_manifest(read_strict_json(manifest_raw, maximum_bytes=SOURCE_LIMIT), base, output)
    payload = {"schema_version": SCHEMA, "base": base,
               "result": _ref(output, result_raw), "manifest": _ref(manifest_path, manifest_raw),
               "report": _ref(report_path, report_raw)}
    raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False) + "\n").encode("utf-8")
    if len(raw) > REFERENCE_LIMIT:
        raise ValueError("provider 표시 참조 크기 초과")
    target = _safe(_view_path(output), root)
    if target in (output, manifest_path, report_path):
        raise ValueError("provider 표시 출력과 입력 경로 충돌")
    if os.path.lexists(target):
        if _read(target, root, REFERENCE_LIMIT) != raw:
            raise ValueError("이 결과에는 이미 다른 provider 보고서가 연결되어 있습니다")
    else:
        with target.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    if _read(target, root, REFERENCE_LIMIT) != raw:
        raise ValueError("provider 표시 참조 저장 검산 실패")
    if bound_plan.verify_protected_sources() is not True or _read(report_path, root, REPORT_LIMIT) != report_raw:
        raise ValueError("provider 표시 저장 중 원본 또는 보고서 변경")
    return _ref(target, raw)


def read_recovery_provider_view(output_path: str | Path, root: str | Path, *, item: dict | None = None) -> dict:
    """고정 companion만 읽는다. HMAC·원장·응답 검증이나 provider 실행을 하지 않는다."""
    result = {"binding_status": "MISSING", "verification_scope": SCOPE,
              "reason_codes": ["PROVIDER_REPORT_NOT_ATTACHED"]}
    try:
        root = Path(root).resolve()
        output = _safe(Path(output_path), root)
        target = _safe(_view_path(output), root)
        if not os.path.lexists(target):
            return result
        raw = _read(target, root, REFERENCE_LIMIT)
        ref = read_strict_json(raw, maximum_bytes=REFERENCE_LIMIT)
        if (type(ref) is not dict or set(ref) != {"schema_version", "base", "result", "manifest", "report"}
                or ref["schema_version"] != SCHEMA or Path(ref["result"]["path"]).absolute() != output):
            raise ValueError("provider 표시 참조 schema 또는 결과 경로 불일치")
        _read_ref(ref["result"], root, SOURCE_LIMIT)
        manifest_raw = _read_ref(ref["manifest"], root, SOURCE_LIMIT)
        manifest = read_strict_json(manifest_raw, maximum_bytes=SOURCE_LIMIT)
        report_raw = _read_ref(ref["report"], root, REPORT_LIMIT)
        report = read_strict_json(report_raw, maximum_bytes=REPORT_LIMIT)
        _check_report(report, ref["base"])
        _check_manifest(manifest, ref["base"], output)
        if _read(target, root, REFERENCE_LIMIT) != raw:
            raise ValueError("판독 중 provider 참조 변경")
        view = {**result, "binding_status": "BOUND", "reason_codes": [], "report": report}
        return bind_recovery_provider_view_row(view, item) if item is not None else view
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return {**result, "binding_status": "INVALID", "reason_codes": ["PROVIDER_REFERENCE_OR_BASE_INVALID"]}


def bind_recovery_provider_view_row(view: dict, item: dict) -> dict:
    """전체 결과는 파일을 한 번 읽고 원래 각 행을 바꾸기 전에 따로 대조한다."""
    if view.get("binding_status") != "BOUND":
        return view
    result = {key: value for key, value in view.items() if key != "report"}
    try:
        base = view["report"]["base"]
        if type(item.get("post_id")) is not type(base["post_id"]) or item.get("post_id") != base["post_id"]:
            return {**result, "binding_status": "NO_PLAN_PROVIDED", "reason_codes": ["NO_PROVIDER_PLAN_FOR_SELECTED_ROW"]}
        if canonical_sha256(item) != base["result_sha256"]:
            raise ValueError("선택 행과 provider base 지문 불일치")
        meta = item.get("run_meta") or {}
        if type(meta) is not dict:
            raise ValueError("잘못된 원래 행 metadata")
        for key in ("semantic_review_router_receipt", "semantic_recovery_plan_receipt"):
            receipt = meta.get(key)
            if receipt is not None and (type(receipt) is not dict or any(
                    type(receipt.get(field)) is not type(base[field]) or receipt.get(field) != base[field]
                    for field in ("publication_scope_id", "input_index", "post_id", "publication_decision_id",
                                  "stable_result_sha256", "public_projection_sha256"))):
                raise ValueError("행 검토 수령증과 provider base 불일치")
        return view
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        return {**result, "binding_status": "INVALID", "reason_codes": ["PROVIDER_REFERENCE_OR_BASE_INVALID"]}
