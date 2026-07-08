from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.bootstrap_regression_safe_grounding import compare_collateral  # noqa: E402
from tools.compare_completed779_improvement import load_json_or_jsonl  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _golden_rows(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("golden manifest must contain rows list")
    return [row for row in rows if isinstance(row, dict)]


def build_compare(
    *,
    baseline_path: Path,
    after_path: Path,
    golden_manifest: Path,
    compare_id: str,
    expected_shared_posts: int = 375,
    runtime_manifest: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    baseline_rows = load_json_or_jsonl(baseline_path)
    after_rows = load_json_or_jsonl(after_path)
    runtime_payload = load_json(runtime_manifest) if runtime_manifest else None
    runtime_completed = runtime_payload.get("completed_count") if isinstance(runtime_payload, dict) else None
    runtime_pending = runtime_payload.get("pending_count") if isinstance(runtime_payload, dict) else None
    runtime_failed = runtime_payload.get("failed_count") if isinstance(runtime_payload, dict) else None
    runtime_complete = (
        runtime_completed == expected_shared_posts
        and (runtime_pending or 0) == 0
        and (runtime_failed or 0) == 0
    )
    collateral = compare_collateral(
        baseline_rows,
        after_rows,
        expected_rows=_golden_rows(golden_manifest),
    )
    shared = collateral.get("shared_post_count")
    regressions = collateral.get("collateral_regression_count")
    static_gate = "GO" if shared == expected_shared_posts and regressions == 0 else "NO-GO"
    runtime_gate = "GO" if runtime_complete and static_gate == "GO" else "NO-GO"
    runtime_blockers: list[str] = []
    if runtime_manifest is None:
        runtime_blockers.append("collateral_runtime_counts_missing")
    elif not runtime_complete:
        runtime_blockers.append("collateral_runtime_not_complete")
    report = {
        "report_type": (
            "full375_runtime_collateral_compare"
            if runtime_manifest
            else "full375_projection_collateral_compare"
        ),
        "compare_id": compare_id,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": "REVIEW-LOCKED" if static_gate == "GO" else "NO-GO",
        "projection_static_collateral_gate": static_gate,
        "runtime_collateral_gate": runtime_gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "baseline_path": str(baseline_path),
        "after_path": str(after_path),
        "golden_manifest_path": str(golden_manifest),
        "runtime_manifest_path": str(runtime_manifest) if runtime_manifest else None,
        "expected_shared_posts": expected_shared_posts,
        **collateral,
        "runtime_completed_count": runtime_completed,
        "runtime_pending_count": runtime_pending,
        "runtime_failed_count": runtime_failed,
        "runtime_complete": runtime_complete,
        "blockers": [
            *([] if static_gate == "GO" else ["projection_static_collateral_regression_nonzero"]),
            *runtime_blockers,
        ],
        "approval_boundary": {
            "projection_compare_is_not_runtime_replay": runtime_manifest is None,
            "runtime_compare_is_not_semantic_approval": runtime_manifest is not None,
            "projection_static_gate_is_not_full_scan_approval": True,
            "full_scan_approval_requires_full_scan_path": True,
        },
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    runtime_manifest_path = report.get("runtime_manifest_path")
    scope_sentence = (
        "baseline full375와 runtime replay 결과를 비교한 collateral diff다. "
        "runtime 375 완주 여부를 포함하지만 semantic/full_scan approval은 별도 게이트에서 판단한다."
        if runtime_manifest_path
        else "Loop580 projection 결과를 baseline full375와 비교한 정적 collateral diff다. "
        "runtime 375 완주가 아니므로 regression 수가 줄어도 full_scan approval은 열리지 않는다."
    )
    runtime_counts = (
        f"completed={report['runtime_completed_count']}, "
        f"pending={report['runtime_pending_count']}, "
        f"failed={report['runtime_failed_count']}, "
        f"runtime_complete={report['runtime_complete']}"
        if runtime_manifest_path
        else "missing"
    )
    lines = [
        f"# {report.get('compare_id')}",
        "",
        scope_sentence,
        "",
        "## 요약",
        "",
        f"- gate: `{report['gate']}`",
        f"- projection_static_collateral_gate: `{report['projection_static_collateral_gate']}`",
        f"- runtime_collateral_gate: `{report['runtime_collateral_gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- shared posts: `{report['shared_post_count']}/{report['expected_shared_posts']}`",
        f"- changed rows: `{report['changed_post_count']}`",
        f"- raw collateral_regression_count: `{report['collateral_regression_count']}`",
        f"- status_counts: `{report['status_counts']}`",
        f"- regression_status_counts: `{report['regression_status_counts']}`",
        f"- runtime counts: `{runtime_counts}`",
        "",
        "## 차단 항목",
        "",
    ]
    for blocker in report.get("blockers") or []:
        lines.append(f"- `{blocker}`")
    regression_rows = [row for row in report.get("rows") or [] if row.get("is_regression")]
    if regression_rows:
        lines.extend(["", "## Regression 샘플", ""])
        for row in regression_rows[:20]:
            before = row.get("before_identity") or {}
            after = row.get("after_identity") or {}
            lines.append(
                f"- `{row.get('post_id')}` `{row.get('status')}` "
                f"`{before.get('official_title')}` -> `{after.get('official_title')}` "
                f"({before.get('candidate_ledger_status')} -> {after.get('candidate_ledger_status')})"
            )
    lines.extend(["", "## Gate 해석", ""])
    if report["projection_static_collateral_gate"] == "GO":
        lines.append(
            "full375 collateral regression은 0건이다. 단 이 산출물만으로 full_scan approval을 열지 않고 "
            "always-on gate와 full_scan 경로 조건을 함께 확인한다."
        )
    else:
        lines.append(
            f"raw regression `{report['collateral_regression_count']}`건이 남아 있다. "
            "따라서 golden18 PASS는 과적합 가능성을 계속 배제하지 못하며, 회귀패널/잔여 큐 확대가 필요하다."
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare a projection result against full375 baseline collateral.")
    parser.add_argument("--baseline-result", required=True, type=Path)
    parser.add_argument("--after-result", required=True, type=Path)
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--compare-id", default="full375_projection_collateral_compare")
    parser.add_argument("--expected-shared-posts", type=int, default=375)
    parser.add_argument("--runtime-manifest", type=Path, default=None)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-regression", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_compare(
        baseline_path=args.baseline_result,
        after_path=args.after_result,
        golden_manifest=args.golden_manifest,
        compare_id=args.compare_id,
        expected_shared_posts=args.expected_shared_posts,
        runtime_manifest=args.runtime_manifest,
    )
    write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "projection_static_collateral_gate": report["projection_static_collateral_gate"],
                "shared_post_count": report["shared_post_count"],
                "changed_post_count": report["changed_post_count"],
                "collateral_regression_count": report["collateral_regression_count"],
                "blockers": report["blockers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.fail_on_regression and report["projection_static_collateral_gate"] != "GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
