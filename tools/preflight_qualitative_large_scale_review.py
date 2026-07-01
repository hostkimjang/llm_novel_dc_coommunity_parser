from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_round2_module(root: Path) -> Any:
    path = root / "tools" / "build_qualitative_round2_review.py"
    spec = importlib.util.spec_from_file_location("build_qualitative_round2_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def count_checkpoint_completed(path: Path | None) -> tuple[int | None, int | None]:
    if path is None or not path.exists():
        return None, None
    total = 0
    completed = 0
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            payload = json.loads(line)
            if isinstance(payload, dict) and payload.get("status") == "completed":
                completed += 1
    return total, completed


def row_count(result_path: Path, round2: Any) -> int:
    total = 0
    for index, _row in round2.iter_json_array(result_path):
        total = index
    return total


def bucket_population_counts(result_path: Path, round2: Any) -> tuple[int, dict[str, int]]:
    counts = {bucket: 0 for bucket in round2.BUCKET_TARGETS}
    total = 0
    for row_index, row in round2.iter_json_array(result_path):
        total = row_index
        facts = round2.extract_facts(row_index, row)
        for bucket in counts:
            if bucket in facts["bucket_reasons"]:
                counts[bucket] += 1
    return total, counts


def default_related_path(result_path: Path, suffix: str) -> Path:
    match = re.match(r"^(?P<stem>.+?)\.json$", result_path.name)
    if match:
        return result_path.with_name(match.group("stem") + suffix)
    return result_path.with_name(result_path.name + suffix)


def manifest_completion_state(manifest: dict[str, Any] | None, result_rows: int) -> dict[str, Any]:
    manifest = manifest or {}
    input_count = manifest.get("input_post_count")
    completed = manifest.get("completed_count")
    flushed = manifest.get("flushed_count")
    pending = manifest.get("pending_count")
    failed = manifest.get("failed_count")
    clean_by_counts = (
        input_count is not None
        and completed is not None
        and int(completed or 0) >= int(input_count or 0)
        and int(failed or 0) == 0
        and int(pending or 0) == 0
        and (flushed is None or int(flushed or 0) >= int(completed or 0))
    )
    partial_signals = []
    if input_count is not None and completed is not None and int(completed or 0) < int(input_count or 0):
        partial_signals.append("completed_count_lt_input_post_count")
    if pending is not None and int(pending or 0) > 0:
        partial_signals.append("pending_count_gt_zero")
    if flushed is not None and completed is not None and int(flushed or 0) < int(completed or 0):
        partial_signals.append("flushed_count_lt_completed_count")
    if result_rows and completed is not None and result_rows < int(completed or 0):
        partial_signals.append("result_rows_lt_completed_count")
    return {
        "input_post_count": input_count,
        "completed_count": completed,
        "flushed_count": flushed,
        "pending_count": pending,
        "failed_count": failed,
        "clean_by_counts": bool(clean_by_counts),
        "partial_signals": partial_signals,
    }


def refine_source_policy_with_manifest(
    source_policy: dict[str, Any],
    *,
    manifest_state: dict[str, Any],
    result_rows: int,
    checkpoint_completed: int | None,
    pending_snapshot_rows: int | None,
) -> dict[str, Any]:
    refined = dict(source_policy or {})
    counts = dict(refined.get("counts") or {})
    counts["final_result_rows"] = result_rows
    counts["checkpoint_completed_rows"] = checkpoint_completed
    counts["pending_snapshot_rows"] = pending_snapshot_rows
    refined["counts"] = counts

    partial_signals = manifest_state.get("partial_signals") or []
    if partial_signals:
        if refined.get("source_dataset_kind") == "final_result_json":
            refined["source_dataset_kind"] = "partial_final_result_json"
        refined["source_integrity_classification"] = refined.get("source_integrity_classification") or "manifest_partial_run"
        refined["large_run_complete"] = False
        refined["approval_policy"] = (
            "manifest/checkpoint/result row count가 partial run을 직접 증명하므로 "
            "10만 건 semantic approval source로 쓰지 않는다. regression seed와 targeted triage에만 사용한다."
        )
    elif manifest_state.get("clean_by_counts"):
        refined["source_integrity_classification"] = refined.get("source_integrity_classification") or "manifest_clean_completion"
        refined["large_run_complete"] = bool(refined.get("large_run_complete") or True)

    return refined


def required_next_actions(*, source_large_run_complete: bool, random_feasible: bool) -> list[str]:
    actions: list[str] = []
    if not source_large_run_complete:
        actions.extend(
            [
                "obtain_completed_source",
                "rerun_preflight_on_completed_source",
            ]
        )
    if source_large_run_complete and not random_feasible:
        actions.append("increase_completed_source_until_random_baseline_feasible")
    if source_large_run_complete and random_feasible:
        actions.extend(
            [
                "build_random_control_v3_1000_plus",
                "build_p0_p1_high_risk_expansion",
                "separate_random_baseline_from_high_risk_oversample",
            ]
        )
    else:
        actions.append("keep_current_source_as_regression_seed_only")
    return actions


def exit_code_for_gate(preflight: dict[str, Any], *, fail_on_locked: bool) -> int:
    if not fail_on_locked:
        return 0
    gate = preflight.get("gate") if isinstance(preflight, dict) else {}
    if isinstance(gate, dict) and gate.get("overall") == "REVIEW-LOCKED":
        return 2
    return 0


def build_preflight(
    *,
    result_path: Path,
    manifest_path: Path | None,
    checkpoint_path: Path | None,
    pending_path: Path | None,
    source_integrity_summary_path: Path | None,
    random_target: int,
    target_scale: float,
) -> dict[str, Any]:
    root = repo_root()
    round2 = load_round2_module(root)
    run_id = round2.infer_run_id(result_path)
    manifest = load_json(manifest_path)
    pending_snapshot = load_json(pending_path)
    summary = round2.load_source_integrity_summary(source_integrity_summary_path)
    source_policy = round2.source_review_policy(result_path, summary)
    result_rows, bucket_counts = bucket_population_counts(result_path, round2)
    checkpoint_rows, checkpoint_completed = count_checkpoint_completed(checkpoint_path)
    pending_snapshot_rows = len(pending_snapshot) if isinstance(pending_snapshot, list) else None
    manifest_state = manifest_completion_state(manifest if isinstance(manifest, dict) else None, result_rows)
    source_policy = refine_source_policy_with_manifest(
        source_policy,
        manifest_state=manifest_state,
        result_rows=result_rows,
        checkpoint_completed=checkpoint_completed,
        pending_snapshot_rows=pending_snapshot_rows,
    )
    targets = OrderedDict(
        (bucket, max(1, int(count * target_scale))) for bucket, count in round2.BUCKET_TARGETS.items()
    )
    bucket_population_limited = {
        bucket: {
            "target": target,
            "population": bucket_counts.get(bucket, 0),
            "population_below_target": bucket_counts.get(bucket, 0) < target,
        }
        for bucket, target in targets.items()
    }
    random_shortfall = max(0, random_target - result_rows)
    random_feasible = random_shortfall == 0
    source_large_run_complete = bool(source_policy.get("large_run_complete") or manifest_state["clean_by_counts"])
    run_integrity_gate = "GO" if source_large_run_complete else "REVIEW"
    semantic_preflight_gate = "GO" if source_large_run_complete and random_feasible else "REVIEW-LOCKED"
    if not random_feasible or not source_large_run_complete:
        overall = "REVIEW-LOCKED"
    else:
        overall = "REVIEW"
    blockers: list[str] = []
    if not source_large_run_complete:
        blockers.append("large_run_completion_not_proven")
    if not random_feasible:
        blockers.append("random_baseline_target_not_feasible")
    if manifest_state["partial_signals"]:
        blockers.extend(manifest_state["partial_signals"])
    if source_policy.get("source_dataset_kind") == "checkpoint_recovered_completed_subset":
        blockers.append("source_is_checkpoint_recovered_subset")
    actions = required_next_actions(
        source_large_run_complete=source_large_run_complete,
        random_feasible=random_feasible,
    )
    return {
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_result_path": result_path.as_posix(),
        "source_integrity_summary_path": source_integrity_summary_path.as_posix()
        if source_integrity_summary_path
        else None,
        "source_review_policy": source_policy,
        "result_rows": result_rows,
        "manifest_path": manifest_path.as_posix() if manifest_path else None,
        "manifest_completion_state": manifest_state,
        "checkpoint_path": checkpoint_path.as_posix() if checkpoint_path else None,
        "checkpoint_rows": checkpoint_rows,
        "checkpoint_completed_rows": checkpoint_completed,
        "pending_snapshot_path": pending_path.as_posix() if pending_path else None,
        "pending_snapshot_rows": pending_snapshot_rows,
        "random_baseline": {
            "requested_sample_size": random_target,
            "available_rows": result_rows,
            "feasible": random_feasible,
            "shortfall": random_shortfall,
        },
        "high_risk": {
            "target_scale": target_scale,
            "bucket_targets": dict(targets),
            "bucket_population_counts": bucket_counts,
            "bucket_population_limited": bucket_population_limited,
            "target_total": sum(targets.values()),
            "population_total_unique_not_deduped": sum(bucket_counts.values()),
        },
        "gate": {
            "run_integrity": run_integrity_gate,
            "semantic_preflight": semantic_preflight_gate,
            "overall": overall,
            "blockers": sorted(set(blockers)),
            "required_next_actions": actions,
        },
    }


def write_markdown(path: Path, preflight: dict[str, Any]) -> None:
    random_baseline = preflight["random_baseline"]
    gate = preflight["gate"]
    lines = [
        f"# 대규모 정성 리뷰 사전 점검 - {preflight['run_id']}",
        "",
        f"- 생성 시각: `{preflight['generated_at']}`",
        f"- 원본 source: `{preflight['source_result_path']}`",
        f"- 결과 row 수: `{preflight['result_rows']}`",
        "",
        "## Source 정책",
        "",
        f"- source dataset kind: `{preflight['source_review_policy'].get('source_dataset_kind')}`",
        f"- 정합성 분류: `{preflight['source_review_policy'].get('source_integrity_classification')}`",
        f"- 대형 run 완료 여부: `{preflight['source_review_policy'].get('large_run_complete')}`",
        f"- 정책: {preflight['source_review_policy'].get('approval_policy')}",
        "",
        "## Manifest/Checkpoint",
        "",
        f"- input/completed/flushed/pending/failed: "
        f"`{preflight['manifest_completion_state'].get('input_post_count')}` / "
        f"`{preflight['manifest_completion_state'].get('completed_count')}` / "
        f"`{preflight['manifest_completion_state'].get('flushed_count')}` / "
        f"`{preflight['manifest_completion_state'].get('pending_count')}` / "
        f"`{preflight['manifest_completion_state'].get('failed_count')}`",
        f"- partial signals: `{', '.join(preflight['manifest_completion_state'].get('partial_signals') or []) or 'none'}`",
        f"- checkpoint completed rows: `{preflight.get('checkpoint_completed_rows')}`",
        f"- pending snapshot rows: `{preflight.get('pending_snapshot_rows')}`",
        "",
        "## 표본 추출 가능성",
        "",
        f"- random 요청 수: `{random_baseline['requested_sample_size']}`",
        f"- random 사용 가능 row: `{random_baseline['available_rows']}`",
        f"- random 가능 여부: `{random_baseline['feasible']}`",
        f"- random 부족분: `{random_baseline['shortfall']}`",
        f"- high-risk 목표 총량: `{preflight['high_risk']['target_total']}`",
        "",
        "## Gate",
        "",
        f"- run 정합성: `{gate['run_integrity']}`",
        f"- semantic preflight: `{gate['semantic_preflight']}`",
        f"- 종합: `{gate['overall']}`",
        f"- blockers: `{', '.join(gate['blockers']) or 'none'}`",
        f"- 다음 필수 액션: `{', '.join(gate.get('required_next_actions') or []) or 'none'}`",
        "",
        "## 판단",
        "",
    ]
    if gate["overall"] == "REVIEW-LOCKED":
        lines.append(
            "현재 source는 large-scale semantic approval 입력으로 부족하다. "
            "random baseline과 P0/P1 high-risk expansion을 실행하더라도 approval 근거가 아니라 부족 증거로만 사용한다."
        )
    else:
        lines.append("preflight 기준으로 large-scale qualitative expansion을 시작할 수 있다. 단 semantic gate는 별도 리뷰 결과로 판정한다.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--pending-snapshot", default=None)
    parser.add_argument("--source-integrity-summary", default=None)
    parser.add_argument("--random-target", type=int, default=1000)
    parser.add_argument("--target-scale", type=float, default=1.0)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument(
        "--fail-on-locked",
        action="store_true",
        help="Exit with code 2 when the preflight gate overall status is REVIEW-LOCKED.",
    )
    args = parser.parse_args()

    root = repo_root()
    result_path = (root / args.result).resolve()
    manifest_path = (root / args.manifest).resolve() if args.manifest else default_related_path(result_path, "_manifest.json")
    checkpoint_path = (root / args.checkpoint).resolve() if args.checkpoint else default_related_path(result_path, "_checkpoint.jsonl")
    pending_path = (root / args.pending_snapshot).resolve() if args.pending_snapshot else default_related_path(result_path, "_pending_snapshot.json")
    summary_path = (root / args.source_integrity_summary).resolve() if args.source_integrity_summary else None

    preflight = build_preflight(
        result_path=result_path,
        manifest_path=manifest_path if manifest_path.exists() else None,
        checkpoint_path=checkpoint_path if checkpoint_path.exists() else None,
        pending_path=pending_path if pending_path.exists() else None,
        source_integrity_summary_path=summary_path,
        random_target=max(1, args.random_target),
        target_scale=args.target_scale,
    )

    output_json = (root / args.output_json).resolve()
    output_md = (root / args.output_md).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(output_md, preflight)
    print(json.dumps({"gate": preflight["gate"], "output_json": output_json.as_posix()}, ensure_ascii=False, indent=2))
    return exit_code_for_gate(preflight, fail_on_locked=args.fail_on_locked)


if __name__ == "__main__":
    raise SystemExit(main())
