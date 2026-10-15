from __future__ import annotations

"""Golden saved evidence를 actual calibration dataset으로 승격하기 전 점검한다."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.grounding.calibration_dataset_readiness import (  # noqa: E402
    build_dataset_readiness,
    validate_dataset_readiness_against_sources,
    validate_dataset_readiness_manifest,
)
from src.llm_batch.grounding.candidate_set_calibration_shadow import (  # noqa: E402
    CALIBRATION_POLICY_SCHEMA_V4,
    CalibrationEvaluationPolicy,
)
from tools.run_candidate_set_nil_shadow_harness import (  # noqa: E402
    build_saved_artifact_comparison,
    validate_run_spec as validate_p1_run_spec,
)


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return (value if value.is_absolute() else ROOT / value).resolve()


def _stored(path: str | Path) -> str:
    value = _resolve(path)
    try:
        return value.relative_to(ROOT).as_posix()
    except ValueError:
        return str(value)


def _stable_bytes(path: Path) -> bytes:
    before = path.stat()
    first = path.read_bytes()
    middle = path.stat()
    second = path.read_bytes()
    after = path.stat()
    stat = lambda value: (value.st_size, value.st_mtime_ns, getattr(value, "st_ino", 0))
    if stat(before) != stat(middle) or stat(middle) != stat(after) or first != second:
        raise ValueError(f"source changed during readiness read: {path}")
    return first


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON value: {value}")


def _read_json(path: str | Path) -> tuple[Path, bytes, dict[str, Any]]:
    resolved = _resolve(path)
    raw = _stable_bytes(resolved)
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonfinite,
        )
    except Exception as exc:
        raise ValueError(f"invalid readiness JSON source: {resolved}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"readiness JSON source must be an object: {resolved}")
    return resolved, raw, value


def _ref(path: Path, raw: bytes) -> dict[str, Any]:
    return {
        "path": _stored(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def require_actual_readiness_policy(
    policy: CalibrationEvaluationPolicy,
) -> CalibrationEvaluationPolicy:
    """Require the exact interval protocol accepted by FROZEN_ACTUAL evaluation."""

    if (
        policy.policy_scope != "FROZEN_ACTUAL_PRE_REGISTERED"
        or policy.schema_version != CALIBRATION_POLICY_SCHEMA_V4
    ):
        raise ValueError(
            "actual readiness requires a FROZEN_ACTUAL_PRE_REGISTERED "
            "policy v4 with a hash-bound interval protocol"
        )
    return policy


def build_current_readiness(
    *,
    p1_run_spec_path: str | Path,
    p1_comparison_path: str | Path,
    label_ledger_path: str | Path,
    actual_evaluation_policy_path: str | Path | None = None,
) -> dict[str, Any]:
    run_spec, _, _ = validate_p1_run_spec(p1_run_spec_path, verify_implementation=False)
    run_path, run_raw, stored_run_spec = _read_json(p1_run_spec_path)
    if stored_run_spec != run_spec:
        raise ValueError("P1 validated/stored RunSpec mismatch")
    comparison_path, comparison_raw, comparison = _read_json(p1_comparison_path)
    rebuilt = build_saved_artifact_comparison(
        p1_run_spec_path,
        verify_implementation=False,
    )
    stored_without_time = {key: value for key, value in comparison.items() if key != "generated_at"}
    rebuilt_without_time = {key: value for key, value in rebuilt.items() if key != "generated_at"}
    if stored_without_time != rebuilt_without_time:
        raise ValueError("stored P1 comparison does not replay from its RunSpec")
    label_path, label_raw, label_ledger = _read_json(label_ledger_path)
    bound_label = run_spec.get("artifacts", {}).get("label_ledger", {})
    if (
        bound_label.get("path") != _stored(label_path)
        or bound_label.get("sha256") != hashlib.sha256(label_raw).hexdigest()
    ):
        raise ValueError("readiness label ledger is not the P1-bound artifact")
    policy_path: Path | None = None
    policy_raw: bytes | None = None
    policy_sha256: str | None = None
    policy_payload: dict[str, Any] | None = None
    if actual_evaluation_policy_path is not None:
        policy_path, policy_raw, policy_payload = _read_json(actual_evaluation_policy_path)
        try:
            policy = CalibrationEvaluationPolicy(**policy_payload)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid actual evaluation policy: {exc}") from exc
        require_actual_readiness_policy(policy)
        policy_sha256 = policy.policy_sha256
    manifest = build_dataset_readiness(
        p1_comparison=comparison,
        label_ledger=label_ledger,
        sources={
            "p1_run_spec": _ref(run_path, run_raw),
            "p1_comparison": _ref(comparison_path, comparison_raw),
            "label_ledger": _ref(label_path, label_raw),
        },
        actual_evaluation_policy_sha256=policy_sha256,
        actual_evaluation_policy_ref=(
            None
            if policy_path is None or policy_raw is None
            else _ref(policy_path, policy_raw)
        ),
    )
    validate_dataset_readiness_manifest(manifest)
    validate_dataset_readiness_against_sources(
        manifest,
        p1_comparison=comparison,
        label_ledger=label_ledger,
        actual_evaluation_policy=policy_payload,
        actual_evaluation_policy_ref=(
            None
            if policy_path is None or policy_raw is None
            else _ref(policy_path, policy_raw)
        ),
    )
    if _stable_bytes(run_path) != run_raw or _stable_bytes(comparison_path) != comparison_raw or _stable_bytes(label_path) != label_raw:
        raise ValueError("readiness source changed after validation")
    if policy_path is not None and policy_raw is not None and _stable_bytes(policy_path) != policy_raw:
        raise ValueError("actual evaluation policy changed after validation")
    return manifest


def render_markdown(manifest: Mapping[str, Any]) -> str:
    validate_dataset_readiness_manifest(manifest)
    counts = manifest["counts"]
    blocker_counts: dict[str, int] = {}
    for row in manifest["rows"]:
        for blocker in row["blockers"]:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    lines = [
        "# P3 실제 보정 자료 준비도 점검",
        "",
        "## 결론",
        "",
        f"- 게이트: `{manifest['gate']}`",
        f"- split manifest 생성 가능: `{str(manifest['ready_for_split_manifest']).lower()}`",
        "- 실제 정확도·신뢰구간: `null`",
        "- 의미 품질: `REVIEW-LOCKED`",
        "- 전체 스캔 승인: `false`",
        "",
        "현재 저장 자료를 실제 DEV/CAL/FROZEN 자료로 승격하지 않는다. 아래 항목은 누락 근거를 고정한 준비도 점검이며 새 라벨이나 후보 ID를 만들지 않는다.",
        "",
        "## 집계",
        "",
        "| 항목 | 값 |",
        "| --- | ---: |",
        f"| 전체 행 | {counts['source_rows']} |",
        f"| 작품 정답 행 | {counts['candidate_truth']} |",
        f"| 작품 없음 행 | {counts['nil_truth']} |",
        f"| 미판정 행 | {counts['unjudged']} |",
        f"| producer COMPLETE 행 | {counts['generation_complete']} |",
        f"| split 배정 준비 완료 행 | {counts['ready_rows']} |",
        "",
        "## 차단 사유",
        "",
        "| 차단 상태 | 행 수 |",
        "| --- | ---: |",
    ]
    for blocker, count in sorted(blocker_counts.items()):
        lines.append(f"| `{blocker}` | {count} |")
    lines.extend(
        [
            "",
            "## 다음 증거",
            "",
            "1. 모든 평가 행의 producer `COMPLETE` 영수증을 실제 runtime에서 만든다.",
            "2. 게시글 그룹·본문·출처·작품 단위가 겹치지 않는 split provenance를 고정한다.",
            "3. 작품 정답은 제목 문자열이 아니라 immutable candidate ID와 gold-work 지문으로 결속한다.",
            "4. 미판정 행을 임의로 NIL로 바꾸지 말고 별도 판정 또는 사전 등록 제외 정책을 둔다.",
            "5. actual 평가 정책을 먼저 고정한 뒤에만 split manifest를 만든다.",
            "",
            f"manifest SHA-256: `{manifest['manifest_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    manifest: Mapping[str, Any],
    *,
    output_json: str | Path,
    output_markdown: str | Path,
) -> tuple[Path, Path]:
    validate_dataset_readiness_manifest(manifest)
    json_path = _resolve(output_json)
    markdown_path = _resolve(output_markdown)
    if json_path == markdown_path or json_path.exists() or markdown_path.exists():
        raise ValueError("readiness outputs must be distinct new files")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        with json_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(dict(manifest), ensure_ascii=False, indent=2) + "\n")
        created.append(json_path)
        with markdown_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(render_markdown(manifest))
        created.append(markdown_path)
        _, _, stored = _read_json(json_path)
        if stored != dict(manifest):
            raise ValueError("stored readiness manifest mismatch")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    return json_path, markdown_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P3 actual dataset readiness preflight")
    parser.add_argument("--p1-run-spec", required=True)
    parser.add_argument("--p1-comparison", required=True)
    parser.add_argument("--label-ledger", required=True)
    parser.add_argument(
        "--actual-evaluation-policy",
        help="사전 등록된 candidate_set_calibration_policy_v2 JSON; SHA 문자열 대신 파일을 재판독한다.",
    )
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = build_current_readiness(
        p1_run_spec_path=args.p1_run_spec,
        p1_comparison_path=args.p1_comparison,
        label_ledger_path=args.label_ledger,
        actual_evaluation_policy_path=args.actual_evaluation_policy,
    )
    json_path, markdown_path = write_outputs(
        manifest,
        output_json=args.output_json,
        output_markdown=args.output_md,
    )
    print(
        json.dumps(
            {
                "gate": manifest["gate"],
                "ready_for_split_manifest": manifest["ready_for_split_manifest"],
                "counts": manifest["counts"],
                "manifest_sha256": manifest["manifest_sha256"],
                "actual_evaluation_policy_sha256": manifest[
                    "actual_evaluation_policy_sha256"
                ],
                "output_json": _stored(json_path),
                "output_md": _stored(markdown_path),
                "semantic_quality": "REVIEW-LOCKED",
                "full_scan_approval": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
