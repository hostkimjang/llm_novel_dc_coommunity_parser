from __future__ import annotations

"""fresh BEFORE/AFTER 물리 호출 원장을 독립 재판독하는 안전한 하네스.

이 도구는 LLM/MCP를 실행하지 않고 공개 WAL에도 쓰지 않는다. 이미 끝난
두 실행의 manifest와 immutable call ledger를 다시 읽어 실제 호출·토큰
감소만 계산하고, 정확도·전체 지연·금액 비용은 근거가 없으면 null 상태로
남긴다.
"""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.measurement.paired_measurement_readback import (  # noqa: E402
    build_paired_measurement_run_spec,
    build_paired_measurement_readback,
    validate_paired_measurement_run_spec,
    validate_paired_measurement_readback,
)


_METRIC_LABELS = {
    "expert_calls": ("물리 LLM 호출", "실제로 provider에 보낸 요청 횟수이며 retry도 별도 호출로 센다."),
    "text_calls": ("텍스트 모델 호출", "물리 LLM 호출 중 텍스트 요청 횟수다."),
    "vlm_calls": ("VLM 호출", "물리 LLM 호출 중 이미지/VLM 요청 횟수다."),
    "retry_count": ("재시도 호출", "첫 요청 이후 같은 논리 요청을 다시 보낸 물리 재시도 횟수다."),
    "prompt_tokens": ("입력 토큰", "provider가 응답한 usage의 입력 토큰 합계다."),
    "completion_tokens": ("출력 토큰", "provider가 응답한 usage의 출력 토큰 합계다."),
    "total_tokens": ("전체 토큰", "입력 토큰과 출력 토큰의 합이다."),
    "physical_call_wall_ms_sum": (
        "모델 호출 누적 시간(ms)",
        "각 물리 모델 호출의 wall time 합이다. 검색·후처리·대기까지 포함한 배치 전체 지연은 아니다.",
    ),
}


def _display(value: Any, digits: int = 2) -> str:
    if value is None:
        return "측정 불가"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_korean_report(report: Mapping[str, Any]) -> str:
    metrics = report["actual_cost_metrics"]
    reference_copy = report["counterfactual_reference_copy_cost"]
    reference_metrics = reference_copy["cost_metrics"]
    gates = report["gates"]
    zero = report["zero_physical_call_coverage"]
    lines = [
        "# LLM 파이프라인 개선 전·후 독립 비용 판독",
        "",
        "## 한눈에 보는 결론",
        "",
        f"- 비용 원장 판독: `{report['status']}`",
        f"- 비교 게시글: `{report['input_post_count']}`건",
        f"- 공개 판정 비간섭: `{gates['public_decision_link_equivalence']}`",
        f"- 실제 정확도: `{gates['frozen_actual_accuracy']}`",
        f"- 의미 품질: `{gates['semantic_quality']}`",
        f"- 운영 적용 허용: `{str(gates['production_enable_allowed']).lower()}`",
        f"- 전체 스캔 승인: `{str(gates['full_scan_approval']).lower()}`",
        "",
        "이 보고서의 기능은 개선 전(BEFORE)과 개선 후(AFTER)의 물리 호출 원장을 "
        "provider 응답과 별도로 다시 읽어 호출 수와 토큰 감소를 확인하는 것이다. "
        "공개 작품명 판정은 같은 authoritative WAL에 연결됐는지만 확인한다. "
        "정확도 정답이나 운영 승인을 대신하지 않는다.",
        "",
        "## 실제 production inference 비교 가능 행의 비용 지표",
        "",
        f"- 비교 가능 행: `{report['production_inference_comparable_row_count']}/"
        f"{report['input_post_count']}`",
        "- authoritative WAL reference-copy 행은 이 표에서 제외한다.",
        "",
        "| 지표 | 개선 전 | 개선 후 | 감소량 | 감소율 | 상태 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name in _METRIC_LABELS:
        item = metrics[name]
        label, _ = _METRIC_LABELS[name]
        percent = (
            "측정 불가"
            if item["reduction_percent"] is None
            else f"{item['reduction_percent']:.2f}%"
        )
        lines.append(
            f"| {label} | {_display(item['before'])} | {_display(item['after'])} | "
            f"{_display(item['absolute_reduction'])} | {percent} | `{item['status']}` |"
        )
    lines.extend(
        [
            "",
            "### 각 지표가 하는 일",
            "",
        ]
    )
    for name in _METRIC_LABELS:
        label, meaning = _METRIC_LABELS[name]
        lines.append(f"- **{label}**: {meaning}")
    lines.extend(
        [
            "",
            "## REFERENCE_COPY_COST_ONLY 반사실 비용",
            "",
            f"- reference-copy 행: `{reference_copy['row_count']}`건",
            f"- production 절감 KPI 포함: `"
            f"{str(reference_copy['production_savings_kpi_eligible']).lower()}`",
            f"- 의미: {reference_copy['meaning']}",
            "",
            "| 지표 | BEFORE 비용 | reference-copy AFTER 비용 | 차이 | 감소율 | 상태 |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for name in _METRIC_LABELS:
        item = reference_metrics[name]
        label, _ = _METRIC_LABELS[name]
        percent = (
            "측정 불가"
            if item["reduction_percent"] is None
            else f"{item['reduction_percent']:.2f}%"
        )
        lines.append(
            f"| {label} | {_display(item['before'])} | {_display(item['after'])} | "
            f"{_display(item['absolute_reduction'])} | {percent} | `{item['status']}` |"
        )
    lines.extend(
        [
            "",
            "## 호출 0건 행의 분류",
            "",
            f"- 검증된 reference-copy 0-call: `{zero['numerator']}/{zero['denominator']}` "
            f"(`{zero['percent']:.2f}%`)",
            f"- 설명되지 않은 0-call: `{zero['unexplained_zero_call_count']}`",
            f"- production 절감 KPI 포함: `"
            f"{str(zero['production_savings_kpi_eligible']).lower()}`",
            f"- 의미: {zero['meaning']}",
            "",
            "## 게이트 상태",
            "",
            "| 게이트 | 상태 | 무엇을 뜻하나 |",
            "| --- | --- | --- |",
            f"| BEFORE 독립 판독 | `{gates['fresh_before_independent_readback']}` | 개선 전 원장이 완결됐고 모든 행이 공개 WAL에 연결됐는지 확인 |",
            f"| AFTER 독립 판독 | `{gates['fresh_after_independent_readback']}` | 개선 후 원장이 완결됐고 모든 행이 공개 WAL에 연결됐는지 확인 |",
            f"| 동일 실행 조건 | `{gates['same_runspec_pair_scope']}` | 입력·pair·scope가 같은 비교인지 확인 |",
            f"| RunSpec 실바이트 결속 | `{gates['run_spec_bytes_and_self_hash_bound']}` | RunSpec 파일의 실제 바이트와 self-hash를 함께 재검증 |",
            f"| 입력 실바이트·순서 결속 | `{gates['input_bytes_and_order_bound']}` | 두 arm의 실제 input SHA와 post_id 순서를 RunSpec에 결속 |",
            f"| output/route/ledger/WAL 결속 | `{gates['output_route_ledger_wal_binding']}` | 행 좌표와 실행·비교 receipt가 독립 원장 및 WAL과 일치하는지 확인 |",
            f"| 원장 최종 재판독 | `{gates['ledger_final_replay_unchanged']}` | 모든 source 재확인 뒤 두 ledger의 frame/report 지문을 다시 검증 |",
            f"| 공개 WAL 무변경 | `{gates['authoritative_publication_wal_unchanged']}` | 측정 중 공개 판정 원장을 새로 쓰지 않았는지 확인 |",
            f"| 공개 판정 연결 동일 | `{gates['public_decision_link_equivalence']}` | 게시글별 최종 공개 decision_id가 동일한지 확인 |",
            f"| 실제 정확도 | `{gates['frozen_actual_accuracy']}` | FROZEN_ACTUAL 정답과 신뢰구간이 이 보고서에는 아직 결속되지 않음 |",
            f"| 전체 처리 지연 | `{gates['end_to_end_latency']}` | 별도 실행 envelope가 없으므로 모델 호출 시간과 혼동하지 않음 |",
            f"| 금액 비용 | `{gates['money_cost']}` | 가격표 출처·시점·통화가 없어 계산하지 않음 |",
            "",
            "## 근거 파일",
            "",
            f"- paired RunSpec: `{report['sources']['run_spec']['path']}`",
            f"- BEFORE manifest: `{report['sources']['before_manifest']['path']}`",
            f"- AFTER manifest: `{report['sources']['after_manifest']['path']}`",
            f"- BEFORE output: `{report['sources']['before_output']['path']}`",
            f"- AFTER output: `{report['sources']['after_output']['path']}`",
            f"- BEFORE input: `{report['sources']['before_input']['path']}`",
            f"- AFTER input: `{report['sources']['after_input']['path']}`",
            f"- authoritative publication WAL: `{report['sources']['authoritative_publication_wal']['path']}`",
            f"- BEFORE ledger: `{report['sources']['before_ledger']['path']}`",
            f"- AFTER ledger: `{report['sources']['after_ledger']['path']}`",
            f"- 보고서 지문: `{report['report_sha256']}`",
            "",
            "## 아직 주장하면 안 되는 것",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend(
        [
            "- 현재 상태는 `REVIEW-LOCKED`, `full_scan_approval=false`다.",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _exclusive_write_run_spec(path: Path, payload: Mapping[str, Any]) -> None:
    """Persist a pre-run RunSpec exactly once, then read it back independently."""

    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        remaining = memoryview(raw)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError("paired RunSpec write made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        validate_paired_measurement_run_spec(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="완료된 fresh BEFORE/AFTER call ledger를 읽기 전용으로 비교합니다."
    )
    parser.add_argument("--freeze-run-spec")
    parser.add_argument("--input")
    parser.add_argument("--source-manifest")
    parser.add_argument("--pair-id")
    parser.add_argument("--slang-access-mode", choices=("OFF", "READ_ONLY"), default="OFF")
    parser.add_argument("--run-spec")
    parser.add_argument("--before-manifest")
    parser.add_argument("--after-manifest")
    parser.add_argument("--output-json")
    parser.add_argument("--output-md")
    parser.add_argument("--validate-report")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.freeze_run_spec:
        missing = [
            flag
            for flag, value in (
                ("--input", args.input),
                ("--source-manifest", args.source_manifest),
                ("--pair-id", args.pair_id),
            )
            if not value
        ]
        if missing:
            raise SystemExit(f"freeze requires: {', '.join(missing)}")
        spec = build_paired_measurement_run_spec(
            input_path=args.input,
            source_manifest_path=args.source_manifest,
            pair_id=args.pair_id,
            slang_access_mode=args.slang_access_mode,
        )
        output = Path(args.freeze_run_spec).resolve()
        _exclusive_write_run_spec(output, spec)
        print(
            json.dumps(
                {
                    "run_spec": str(output),
                    "run_spec_sha256": spec["run_spec_sha256"],
                    "input_post_count": spec["input_post_count"],
                },
                ensure_ascii=False,
            )
        )
        return
    missing = [
        flag
        for flag, value in (
            ("--run-spec", args.run_spec),
            ("--before-manifest", args.before_manifest),
            ("--after-manifest", args.after_manifest),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"readback requires: {', '.join(missing)}")
    report = build_paired_measurement_readback(
        run_spec_path=args.run_spec,
        before_manifest_path=args.before_manifest,
        after_manifest_path=args.after_manifest,
    )
    if args.validate_report:
        stored = json.loads(Path(args.validate_report).read_text(encoding="utf-8"))
        validate_paired_measurement_readback(
            stored,
            run_spec_path=args.run_spec,
            before_manifest_path=args.before_manifest,
            after_manifest_path=args.after_manifest,
        )
    if args.output_json:
        _atomic_write(
            Path(args.output_json),
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        )
    if args.output_md:
        _atomic_write(Path(args.output_md), render_korean_report(report))
    if not args.output_json and not args.output_md:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
