from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def golden_gate(golden: dict[str, Any], expected_rows: int) -> dict[str, Any]:
    row_count = _safe_int(golden.get("row_count"))
    passed_count = _safe_int(golden.get("passed_count"))
    failed_count = _safe_int(golden.get("failed_count"))
    semantic_gate = str(golden.get("canary_semantic_gate") or "").strip()
    runtime = golden.get("runtime") if isinstance(golden.get("runtime"), dict) else {}
    runtime_complete = (
        _safe_int(runtime.get("completed_count")) == expected_rows
        and (_safe_int(runtime.get("pending_count")) or 0) == 0
        and (_safe_int(runtime.get("failed_count")) or 0) == 0
    )
    passed = (
        row_count == expected_rows
        and passed_count == expected_rows
        and (failed_count or 0) == 0
        and semantic_gate in {"PASS", "GO"}
        and runtime_complete
    )
    blockers: list[str] = []
    if row_count != expected_rows:
        blockers.append("golden_row_count_mismatch")
    if passed_count != expected_rows or (failed_count or 0) != 0:
        blockers.append("golden_expected_answer_failures")
    if semantic_gate not in {"PASS", "GO"}:
        blockers.append("golden_semantic_gate_not_pass")
    if not runtime_complete:
        blockers.append("golden_runtime_not_complete")
    return {
        "gate": "GO" if passed else "NO-GO",
        "expected_rows": expected_rows,
        "row_count": row_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "canary_semantic_gate": semantic_gate,
        "runtime_complete": runtime_complete,
        "blockers": blockers,
    }


def collateral_gate(collateral: dict[str, Any], expected_shared_posts: int) -> dict[str, Any]:
    shared = _safe_int(collateral.get("shared_post_count"))
    changed = _safe_int(collateral.get("changed_post_count"))
    regression_count = _safe_int(collateral.get("collateral_regression_count"))
    runtime_completed = _safe_int(collateral.get("runtime_completed_count"))
    runtime_pending = _safe_int(collateral.get("runtime_pending_count"))
    runtime_failed = _safe_int(collateral.get("runtime_failed_count"))
    runtime_complete = (
        runtime_completed in {None, expected_shared_posts}
        and (runtime_pending or 0) == 0
        and (runtime_failed or 0) == 0
    )
    passed = (
        shared == expected_shared_posts
        and (regression_count or 0) == 0
        and runtime_complete
    )
    blockers: list[str] = []
    if shared != expected_shared_posts:
        blockers.append("collateral_shared_post_count_mismatch")
    if (regression_count or 0) != 0:
        blockers.append("collateral_regression_count_nonzero")
    if not runtime_complete:
        blockers.append("collateral_runtime_not_complete")
    return {
        "gate": "GO" if passed else "NO-GO",
        "expected_shared_posts": expected_shared_posts,
        "shared_post_count": shared,
        "changed_post_count": changed,
        "collateral_regression_count": regression_count,
        "runtime_complete": runtime_complete,
        "blockers": blockers,
    }


def evaluate_gates(
    *,
    golden: dict[str, Any],
    collateral: dict[str, Any],
    expected_golden_rows: int = 16,
    expected_collateral_shared_posts: int = 375,
) -> dict[str, Any]:
    golden_result = golden_gate(golden, expected_golden_rows)
    collateral_result = collateral_gate(collateral, expected_collateral_shared_posts)
    gate = "GO" if golden_result["gate"] == "GO" and collateral_result["gate"] == "GO" else "NO-GO"
    return {
        "report_type": "always_on_regression_gates",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "policy": {
            "golden_16_required": True,
            "full_375_collateral_required": True,
            "golden_pass_alone_is_not_approval": True,
            "collateral_runtime_pass_alone_is_not_approval": True,
        },
        "golden": golden_result,
        "collateral": collateral_result,
        "blockers": [
            *[f"golden:{code}" for code in golden_result["blockers"]],
            *[f"collateral:{code}" for code in collateral_result["blockers"]],
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Always-on regression gates",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        "- 정책: golden-16과 full 375 collateral diff를 항상 함께 요구한다.",
        "",
        "## Golden",
        "",
        f"- gate: `{report['golden']['gate']}`",
        f"- rows: `{report['golden']['row_count']}/{report['golden']['expected_rows']}`",
        f"- passed: `{report['golden']['passed_count']}`",
        f"- failed: `{report['golden']['failed_count']}`",
        f"- runtime_complete: `{report['golden']['runtime_complete']}`",
        "",
        "## Collateral",
        "",
        f"- gate: `{report['collateral']['gate']}`",
        (
            "- shared posts: "
            f"`{report['collateral']['shared_post_count']}/{report['collateral']['expected_shared_posts']}`"
        ),
        f"- changed posts: `{report['collateral']['changed_post_count']}`",
        f"- collateral_regression_count: `{report['collateral']['collateral_regression_count']}`",
        f"- runtime_complete: `{report['collateral']['runtime_complete']}`",
        "",
        "## Blockers",
        "",
    ]
    if report["blockers"]:
        for blocker in report["blockers"]:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- 없음")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate golden-16 plus full 375 collateral as always-on gates.")
    parser.add_argument("--golden-audit", required=True, type=Path)
    parser.add_argument("--collateral-compare", required=True, type=Path)
    parser.add_argument("--expected-golden-rows", type=int, default=16)
    parser.add_argument("--expected-collateral-shared-posts", type=int, default=375)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_gates(
        golden=load_json(args.golden_audit),
        collateral=load_json(args.collateral_compare),
        expected_golden_rows=args.expected_golden_rows,
        expected_collateral_shared_posts=args.expected_collateral_shared_posts,
    )
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_no_go and report["gate"] != "GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
