"""Build a completed779 Hermes expansion queue and canary inputs.

The builder keeps two ideas separate:

* main rows come from native-web non-ACCEPT rows that have not already been
  consumed by the balanced P0/source-refresh/Loop 4 canaries.
* control rows come from source-correctness residuals, so high-risk regressions
  like wrong-work prevention and URL/title lint preservation stay visible.
"""

from __future__ import annotations

import argparse
import copy
import glob
import json
from collections import Counter
from pathlib import Path
from typing import Any


SOURCE_URL_TYPES = {
    "heretic_url_null",
    "url_mismatch",
    "title_correct_url_mismatch",
    "reason_evidence_mismatch",
    "garbage_title",
}

MAIN_TARGETS = {
    "comment_explicit_title_missed": 4,
    "candidate_preservation_missing": 6,
    "conflicting_or_multi_candidate": 5,
    "under_resolved_false_negative": 8,
    "wrong_relevance": 6,
    "under_resolved": 6,
    "source_url_or_evidence_hygiene": 4,
}

SEVERITY_RANK = {"high": 0, "med": 1, "medium": 1, "low": 2, None: 3}
EVIDENCE_RANK = {"Strong": 0, "Medium": 1, "Weak": 2, "Missing": 3, None: 4}
ISSUE_PRIORITY = {
    "wrong_work": 0,
    "reason_evidence_mismatch": 1,
    "url_mismatch": 1,
    "garbage_title": 2,
    "heretic_url_null": 3,
    "under_resolved_false_negative": 4,
    "wrong_relevance": 5,
    "under_resolved": 6,
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
        return rows
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    raise ValueError(f"unsupported row payload: {path}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def post_id(row: dict[str, Any]) -> int:
    if row.get("post_id") is None:
        raise ValueError("row is missing post_id")
    return int(row["post_id"])


def row_by_post_id(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {post_id(row): row for row in rows}


def load_id_set(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {post_id(row) for row in load_rows(path)}


def source_ids_from_compare(path: Path) -> set[int]:
    if not path.exists():
        return set()
    payload = load_json(path)
    return {post_id(row) for row in payload.get("rows") or [] if isinstance(row, dict)}


def ids_from_payload_path(path: Path) -> set[int]:
    if not path.exists():
        return set()
    try:
        payload = load_json(path)
    except Exception:
        return set()
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        for key in ("rows", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
        if not rows and all(isinstance(value, dict) for value in payload.values()):
            rows.extend(value for value in payload.values() if isinstance(value, dict))
        closed_ids = payload.get("closed_post_ids")
        if isinstance(closed_ids, list):
            return {int(pid) for pid in closed_ids} | {post_id(row) for row in rows if row.get("post_id") is not None}
        if isinstance(closed_ids, dict):
            return {int(pid) for pid in closed_ids} | {post_id(row) for row in rows if row.get("post_id") is not None}
    return {post_id(row) for row in rows if row.get("post_id") is not None}


def ids_from_paths(paths: list[Path]) -> set[int]:
    ids: set[int] = set()
    for path in paths:
        ids.update(ids_from_payload_path(path))
    return ids


def paths_from_globs(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        for match in glob.glob(pattern, recursive=True):
            path = Path(match)
            if path.is_file():
                paths.append(path)
    return sorted(set(paths))


def extract_identity(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("analysis_result") or {}
    identity = result.get("identity") or {}
    novel_identity = identity.get("novel_identity") or {}
    return {
        "official_title": novel_identity.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title"),
        "heretic_url": novel_identity.get("heretic_url") or identity.get("heretic_url"),
        "is_novel_related": identity.get("is_novel_related"),
        "is_resolved_work_discussion": identity.get("is_resolved_work_discussion"),
        "title_resolution_state": identity.get("title_resolution_state"),
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "candidate_ledger_status": identity.get("candidate_ledger_status"),
        "candidate_count": candidate_count(identity),
    }


def candidate_count(identity: dict[str, Any]) -> int:
    ledger_count = (identity.get("candidate_ledger") or {}).get("candidate_count")
    if isinstance(ledger_count, int):
        return ledger_count
    total = 0
    for field in (
        "title_candidates",
        "mentioned_works",
        "recommendation_candidates",
        "secondary_reference_works",
    ):
        value = identity.get(field)
        if isinstance(value, list):
            total += len(value)
    return total


def has_image_source(row: dict[str, Any]) -> bool:
    if row.get("image_urls"):
        return True
    try:
        if int(row.get("image_count") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    for block in row.get("content_blocks") or []:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").lower()
        if block_type in {"image", "img"} or block.get("image_url") or block.get("src"):
            return True
    return False


def work_key(row: dict[str, Any]) -> str | None:
    for field in (
        "independent_official_title",
        "expected_independent_title",
        "pipeline_official_title",
        "baseline_pipeline_title",
        "title",
    ):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    source_identity = row.get("source_identity") or {}
    value = source_identity.get("official_title")
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    return None


def main_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        SEVERITY_RANK.get(row.get("severity"), 3),
        EVIDENCE_RANK.get(row.get("search_evidence_grade"), 4),
        ISSUE_PRIORITY.get(str(row.get("disagreement_type") or ""), 50),
        post_id(row),
    )


def residual_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int]:
    after = row.get("after_identity") or {}
    expected_title = row.get("expected_independent_title")
    after_title = after.get("official_title")
    title_mismatch = 0
    if expected_title and after_title and expected_title != after_title:
        title_mismatch = 0
    elif expected_title and not after_title:
        title_mismatch = 1
    elif expected_title and after_title == expected_title:
        title_mismatch = 2
    else:
        title_mismatch = 3
    url = after.get("heretic_url")
    expected_url = row.get("expected_independent_url")
    url_mismatch = 0 if expected_url and url != expected_url else 1
    return (
        title_mismatch,
        ISSUE_PRIORITY.get(str(row.get("disagreement_type") or ""), 50),
        url_mismatch,
        post_id(row),
    )


def bucket_for_action_row(row: dict[str, Any]) -> str:
    disagreement = row.get("disagreement_type")
    if disagreement in {"wrong_work", "garbage_title", "over_resolved", "overresolved_generic_trope"}:
        return "precision_identity_high"
    if disagreement in {
        "comment_explicit_title_missed",
        "candidate_preservation_missing",
        "conflicting_or_multi_candidate",
    }:
        return "candidate_comment_multi"
    if disagreement in SOURCE_URL_TYPES:
        return "source_url_hygiene"
    return "recall_relevance_representative"


def hook_for_issue(disagreement: Any) -> str:
    mapping = {
        "wrong_work": "source_local_alias_conflict_guard; final_title_gate",
        "garbage_title": "output_consistency_lint; snippet_breadcrumb_title_demotion",
        "over_resolved": "primary_selection_precision_guard",
        "under_resolved": "recall_candidate_preservation; search_intent_generation",
        "under_resolved_false_negative": "recall_candidate_preservation; comment_or_alias_probe",
        "wrong_relevance": "relevance_boundary_hold; work_like_context_recovery",
        "heretic_url_null": "official_url_source_upgrade; source_url_hygiene",
        "url_mismatch": "official_url_canonicalization; source_url_hygiene",
        "reason_evidence_mismatch": "evidence_reason_alignment_lint; source_url_hygiene",
        "candidate_preservation_missing": "candidate_ledger_preservation",
        "conflicting_or_multi_candidate": "multi_candidate_hold_guard",
        "comment_explicit_title_missed": "comment_answer_title_capture",
    }
    return mapping.get(str(disagreement or ""), "completed779_hermes_generalized_fix")


def fix_for_issue(disagreement: Any, *, control: bool) -> str:
    prefix = "control_recheck" if control else "unseen_pool_expansion"
    mapping = {
        "wrong_work": "block final promotion when source-local alias/candidate evidence conflicts with pipeline primary; preserve HOLD/candidate conflict",
        "garbage_title": "demote URL/domain/breadcrumb/snippet-shaped titles and keep source URL/title lint",
        "under_resolved": "recover direct title, strong alias, comment URL/title, OCR explicit title, or character cluster as candidate/HOLD before null/noise",
        "under_resolved_false_negative": "treat work-like internal setting/character/alias posts as candidate recoverable instead of nonwork/noise",
        "wrong_relevance": "separate genre/platform/author meta HOLD from work-specific character/setting/alias evidence",
        "heretic_url_null": "upgrade to official detail URL when title evidence is strong, otherwise keep URL lint/HOLD",
        "url_mismatch": "canonicalize official detail URL and demote stale/wiki/person/community URL",
        "reason_evidence_mismatch": "keep title correctness separate from evidence subtype and URL hygiene",
    }
    return f"{prefix}: " + mapping.get(str(disagreement or ""), "preserve candidates and avoid unsafe final title promotion")


def test_for_issue(disagreement: Any, *, control: bool) -> str:
    suffix = "control must not regress prior HOLD/lint behavior" if control else "new unseen row must move to candidate/HOLD/resolved without over-promotion"
    mapping = {
        "wrong_work": "source_local_alias_conflict_guard: bad pipeline title must not be finalized",
        "garbage_title": "garbage_title_shape_guard: domain/snippet/breadcrumb text cannot become official_title",
        "under_resolved": "recall_candidate_preservation: recover strong alias/comment/OCR/cluster evidence as candidate/HOLD",
        "under_resolved_false_negative": "work_like_false_negative_recovery: novel-internal evidence cannot be dropped as noise",
        "wrong_relevance": "relevance_boundary_hold: work-like discussion recovered, meta stays HOLD",
        "heretic_url_null": "official_url_source_upgrade: strong title with official detail URL gets URL or explicit lint",
        "url_mismatch": "official_url_canonicalization: wrong/stale URL remains lint or upgrades to canonical detail URL",
        "reason_evidence_mismatch": "reason_evidence_alignment: subtype/reason does not contradict title evidence",
    }
    return mapping.get(str(disagreement or ""), "completed779_hermes_compare_contract") + "; " + suffix


def add_main_rows(
    selected: list[dict[str, Any]],
    selected_ids: set[int],
    candidates: list[dict[str, Any]],
    target: int,
    *,
    selection_bucket: str,
    source_index: dict[int, dict[str, Any]],
    work_counts: Counter[str],
    per_work_cap: int,
) -> None:
    current = 0
    for row in sorted(candidates, key=main_sort_key):
        if current >= target:
            return
        pid = post_id(row)
        if pid in selected_ids:
            continue
        key = work_key(row)
        if key and work_counts[key] >= per_work_cap:
            continue
        source_row = source_index.get(pid, {})
        selected.append(
            queue_row_from_action(
                row,
                source_row,
                queue_role="main",
                selection_bucket=selection_bucket,
            )
        )
        selected_ids.add(pid)
        if key:
            work_counts[key] += 1
        current += 1


def queue_row_from_action(
    row: dict[str, Any],
    source_row: dict[str, Any],
    *,
    queue_role: str,
    selection_bucket: str,
) -> dict[str, Any]:
    disagreement = row.get("disagreement_type")
    return {
        "post_id": post_id(row),
        "queue_role": queue_role,
        "selection_bucket": selection_bucket,
        "selection_reason": f"{queue_role}:{selection_bucket}:{disagreement}/{row.get('recommended_action')}",
        "seed_bucket": bucket_for_action_row(row),
        "disagreement_type": disagreement,
        "recommended_action": row.get("recommended_action"),
        "severity": row.get("severity"),
        "search_evidence_grade": row.get("search_evidence_grade"),
        "expected_title": row.get("independent_official_title"),
        "expected_url": row.get("independent_url"),
        "before_title": row.get("pipeline_official_title") or (row.get("source_identity") or {}).get("official_title"),
        "before_url": row.get("pipeline_url") or (row.get("source_identity") or {}).get("heretic_url"),
        "after_title": None,
        "after_url": None,
        "movement_status": "pending_main_unseen",
        "acceptance_status": "pending_canary",
        "observed_problem": row.get("korean_reason"),
        "source_queue_movement_status": None,
        "source_queue_observed_problem": row.get("korean_reason"),
        "suspected_code_hook": hook_for_issue(disagreement),
        "proposed_next_fix": fix_for_issue(disagreement, control=False),
        "required_test": test_for_issue(disagreement, control=False),
        "source_title": source_row.get("title") or row.get("title"),
        "source_url": source_row.get("url") or row.get("url"),
        "source_identity": extract_identity(source_row) if source_row else row.get("source_identity"),
        "source_urls": row.get("source_urls") or [],
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }


def queue_row_from_explicit_control(row: dict[str, Any], source_row: dict[str, Any]) -> dict[str, Any]:
    disagreement = row.get("disagreement_type")
    control = queue_row_from_action(
        row,
        source_row,
        queue_role="control",
        selection_bucket="explicit_regression_control",
    )
    control.update(
        {
            "selection_reason": f"control:explicit_regression_control:{disagreement}/{row.get('recommended_action')}",
            "movement_status": "explicit_regression_control",
            "acceptance_status": "regression_control",
            "proposed_next_fix": fix_for_issue(disagreement, control=True),
            "required_test": test_for_issue(disagreement, control=True),
        }
    )
    return control


def queue_row_from_residual(row: dict[str, Any], source_row: dict[str, Any], *, selection_bucket: str) -> dict[str, Any]:
    disagreement = row.get("disagreement_type")
    before = row.get("before_identity") or {}
    after = row.get("after_identity") or {}
    return {
        "post_id": post_id(row),
        "queue_role": "control",
        "selection_bucket": selection_bucket,
        "selection_reason": f"control:{selection_bucket}:{row.get('movement_status')}:{disagreement}",
        "seed_bucket": row.get("seed_bucket"),
        "disagreement_type": disagreement,
        "recommended_action": row.get("recommended_action"),
        "severity": None,
        "search_evidence_grade": None,
        "expected_title": row.get("expected_independent_title"),
        "expected_url": row.get("expected_independent_url"),
        "before_title": before.get("official_title") or row.get("baseline_pipeline_title"),
        "before_url": before.get("heretic_url") or row.get("baseline_pipeline_url"),
        "after_title": after.get("official_title"),
        "after_url": after.get("heretic_url"),
        "movement_status": row.get("movement_status"),
        "acceptance_status": "residual_control",
        "observed_problem": row.get("observed_problem") or row.get("source_queue_observed_problem"),
        "source_queue_movement_status": row.get("source_queue_movement_status"),
        "source_queue_observed_problem": row.get("source_queue_observed_problem") or row.get("observed_problem"),
        "suspected_code_hook": row.get("suspected_code_hook") or hook_for_issue(disagreement),
        "proposed_next_fix": fix_for_issue(disagreement, control=True),
        "required_test": test_for_issue(disagreement, control=True),
        "source_title": source_row.get("title"),
        "source_url": source_row.get("url"),
        "source_identity": extract_identity(source_row) if source_row else {},
        "source_urls": [],
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }


def select_source_residual_controls(
    compare_path: Path,
    source_index: dict[int, dict[str, Any]],
    *,
    review_target: int,
    url_target: int,
    excluded_ids: set[int] | None = None,
    bucket_prefix: str = "source_refresh",
) -> list[dict[str, Any]]:
    compare = load_json(compare_path)
    rows = [row for row in compare.get("rows") or [] if isinstance(row, dict)]
    review_rows = [row for row in rows if row.get("movement_status") == "review"]
    url_rows = [
        row
        for row in rows
        if row.get("movement_status") == "url_lint_preserved"
        and (row.get("expected_independent_title") or row.get("expected_independent_url"))
    ]
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    excluded = set(excluded_ids or set())
    for row in sorted(review_rows, key=residual_sort_key)[:review_target]:
        if post_id(row) in excluded:
            continue
        selected.append(
            queue_row_from_residual(
                row,
                source_index.get(post_id(row), {}),
                selection_bucket=f"{bucket_prefix}_review_residual",
            )
        )
        selected_ids.add(post_id(row))
    url_lint_bucket = f"{bucket_prefix}_url_lint_residual"
    for row in sorted(url_rows, key=residual_sort_key):
        if len([item for item in selected if item["selection_bucket"] == url_lint_bucket]) >= url_target:
            break
        if post_id(row) in selected_ids or post_id(row) in excluded:
            continue
        selected.append(
            queue_row_from_residual(
                row,
                source_index.get(post_id(row), {}),
                selection_bucket=url_lint_bucket,
            )
        )
        selected_ids.add(post_id(row))
    return selected


def build_queue(
    *,
    action_queue_path: Path,
    source_path: Path,
    balanced_seed_path: Path,
    source_refresh_compare_path: Path,
    loop4_compare_path: Path,
    out_dir: Path,
    prefix: str = "hermes_loop5_source_residual",
    main_targets: dict[str, int] | None = None,
    residual_review_controls: int = 12,
    residual_url_controls: int = 8,
    per_work_cap: int = 3,
    extra_exclude_paths: list[Path] | None = None,
    extra_exclude_globs: list[str] | None = None,
    control_compare_path: Path | None = None,
    control_bucket_prefix: str | None = None,
    exclude_consumed_controls: bool = True,
    exclude_balanced_main: bool = True,
    explicit_control_post_ids: list[int] | None = None,
) -> dict[str, Any]:
    action_payload = load_json(action_queue_path)
    action_rows = list(action_payload.values()) if isinstance(action_payload, dict) else list(action_payload)
    action_index = {post_id(row): row for row in action_rows}
    source_rows = load_rows(source_path)
    source_index = row_by_post_id(source_rows)
    balanced_ids = load_id_set(balanced_seed_path)
    loop4_ids = source_ids_from_compare(loop4_compare_path)
    source_refresh_ids = source_ids_from_compare(source_refresh_compare_path)
    glob_exclude_paths = paths_from_globs(extra_exclude_globs or [])
    all_extra_exclude_paths = list(extra_exclude_paths or []) + glob_exclude_paths
    extra_excluded_ids = ids_from_paths(all_extra_exclude_paths)
    main_excluded_ids = (balanced_ids if exclude_balanced_main else set()) | loop4_ids | source_refresh_ids | extra_excluded_ids

    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    work_counts: Counter[str] = Counter()
    targets = dict(MAIN_TARGETS if main_targets is None else main_targets)
    unseen = [row for row in action_rows if post_id(row) not in main_excluded_ids]

    for disagreement, target in targets.items():
        if disagreement == "source_url_or_evidence_hygiene":
            candidates = [row for row in unseen if row.get("disagreement_type") in SOURCE_URL_TYPES]
        else:
            candidates = [row for row in unseen if row.get("disagreement_type") == disagreement]
        add_main_rows(
            selected,
            selected_ids,
            candidates,
            target,
            selection_bucket=disagreement,
            source_index=source_index,
            work_counts=work_counts,
            per_work_cap=per_work_cap,
        )

    target_main_total = sum(targets.values())
    selected_main_count = sum(1 for row in selected if row.get("queue_role") == "main")
    if selected_main_count < target_main_total:
        add_main_rows(
            selected,
            selected_ids,
            unseen,
            target_main_total - selected_main_count,
            selection_bucket="fallback_unseen_high_risk",
            source_index=source_index,
            work_counts=work_counts,
            per_work_cap=per_work_cap,
        )

    effective_control_compare_path = control_compare_path or source_refresh_compare_path
    effective_control_bucket_prefix = control_bucket_prefix or "source_refresh"
    residual_controls = select_source_residual_controls(
        effective_control_compare_path,
        source_index,
        review_target=residual_review_controls,
        url_target=residual_url_controls,
        excluded_ids=extra_excluded_ids if exclude_consumed_controls else set(),
        bucket_prefix=effective_control_bucket_prefix,
    )
    for row in residual_controls:
        if post_id(row) not in selected_ids:
            selected.append(row)
            selected_ids.add(post_id(row))

    explicit_control_ids = {int(pid) for pid in explicit_control_post_ids or []}
    missing_explicit_controls = sorted(pid for pid in explicit_control_ids if pid not in action_index or pid not in source_index)
    if missing_explicit_controls:
        raise ValueError(f"explicit control post_ids missing from action/source rows: {missing_explicit_controls}")
    for pid in sorted(explicit_control_ids):
        if pid in selected_ids:
            continue
        selected.append(queue_row_from_explicit_control(action_index[pid], source_index[pid]))
        selected_ids.add(pid)

    main_selected_ids = {int(row["post_id"]) for row in selected if row.get("queue_role") == "main"}
    control_selected_ids = {int(row["post_id"]) for row in selected if row.get("queue_role") == "control"}
    main_consumed_overlap = main_selected_ids & extra_excluded_ids
    control_consumed_overlap = control_selected_ids & extra_excluded_ids
    disallowed_consumed_overlap = set(main_consumed_overlap)
    if exclude_consumed_controls:
        disallowed_consumed_overlap.update(control_consumed_overlap - explicit_control_ids)

    selected = sorted(selected, key=lambda row: (0 if row["queue_role"] == "main" else 1, row["selection_bucket"], row["post_id"]))
    if len(selected_ids) != len(selected):
        duplicates = sorted(pid for pid, count in Counter(row["post_id"] for row in selected).items() if count > 1)
        raise ValueError(f"duplicate selected post_ids: {duplicates}")

    return write_outputs(
        selected,
        source_index,
        out_dir=out_dir,
        prefix=prefix,
        source_path=source_path,
        action_queue_path=action_queue_path,
        balanced_seed_path=balanced_seed_path,
        source_refresh_compare_path=source_refresh_compare_path,
        control_compare_path=effective_control_compare_path,
        loop4_compare_path=loop4_compare_path,
        main_excluded_ids=main_excluded_ids,
        extra_exclude_paths=all_extra_exclude_paths,
        extra_excluded_ids=extra_excluded_ids,
        main_consumed_overlap=main_consumed_overlap,
        control_consumed_overlap=control_consumed_overlap,
        disallowed_consumed_overlap=disallowed_consumed_overlap,
        exclude_consumed_controls=exclude_consumed_controls,
        exclude_balanced_main=exclude_balanced_main,
        explicit_control_ids=explicit_control_ids,
        targets=targets,
        per_work_cap=per_work_cap,
    )


def normalized_seed_row(queue_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "post_id": queue_row["post_id"],
        "seed_bucket": queue_row.get("seed_bucket"),
        "seed_reason": queue_row.get("selection_reason"),
        "queue_role": queue_row.get("queue_role"),
        "selection_bucket": queue_row.get("selection_bucket"),
        "disagreement_type": queue_row.get("disagreement_type"),
        "recommended_action": queue_row.get("recommended_action"),
        "independent_official_title": queue_row.get("expected_title"),
        "independent_url": queue_row.get("expected_url"),
        "pipeline_official_title": queue_row.get("before_title"),
        "pipeline_url": queue_row.get("before_url"),
        "source_identity": queue_row.get("source_identity"),
        "source_title": queue_row.get("source_title"),
        "source_url": queue_row.get("source_url"),
        "source_queue_movement_status": queue_row.get("movement_status"),
        "source_queue_observed_problem": queue_row.get("source_queue_observed_problem") or queue_row.get("observed_problem"),
        "observed_problem": queue_row.get("observed_problem"),
        "suspected_code_hook": queue_row.get("suspected_code_hook"),
        "proposed_next_fix": queue_row.get("proposed_next_fix"),
        "required_test": queue_row.get("required_test"),
        "previous_after_title": queue_row.get("after_title"),
        "previous_after_url": queue_row.get("after_url"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }


def canary_input_row(source_row: dict[str, Any], queue_row: dict[str, Any], *, loop_label: str) -> dict[str, Any]:
    row = copy.deepcopy(source_row)
    row.pop("analysis_result", None)
    row["_judge_seed"] = normalized_seed_row(queue_row)
    row["_hermes_expansion_queue"] = {
        "schema_version": 1,
        "loop": loop_label,
        "post_id": queue_row["post_id"],
        "queue_role": queue_row.get("queue_role"),
        "selection_bucket": queue_row.get("selection_bucket"),
        "movement_status": queue_row.get("movement_status"),
        "observed_problem": queue_row.get("observed_problem"),
        "suspected_code_hook": queue_row.get("suspected_code_hook"),
        "proposed_next_fix": queue_row.get("proposed_next_fix"),
        "required_test": queue_row.get("required_test"),
    }
    return row


def write_outputs(
    queue_rows: list[dict[str, Any]],
    source_index: dict[int, dict[str, Any]],
    *,
    out_dir: Path,
    prefix: str,
    source_path: Path,
    action_queue_path: Path,
    balanced_seed_path: Path,
    source_refresh_compare_path: Path,
    control_compare_path: Path,
    loop4_compare_path: Path,
    main_excluded_ids: set[int],
    extra_exclude_paths: list[Path],
    extra_excluded_ids: set[int],
    main_consumed_overlap: set[int],
    control_consumed_overlap: set[int],
    disallowed_consumed_overlap: set[int],
    exclude_consumed_controls: bool,
    exclude_balanced_main: bool,
    explicit_control_ids: set[int],
    targets: dict[str, int],
    per_work_cap: int,
) -> dict[str, Any]:
    if disallowed_consumed_overlap:
        raise ValueError(f"selected consumed post_ids: {sorted(disallowed_consumed_overlap)}")
    inputs_dir = out_dir / "inputs"
    queue_path = out_dir / f"{prefix}_queue.json"
    queue_md_path = out_dir / f"{prefix}_queue_ko.md"
    seed_path = inputs_dir / f"{prefix}_seed.jsonl"
    text_path = inputs_dir / f"{prefix}_text_url_comment.jsonl"
    image_path = inputs_dir / f"{prefix}_image_ocr.jsonl"
    manifest_path = inputs_dir / f"{prefix}_input_manifest.json"
    report_path = inputs_dir / f"{prefix}_input_report_ko.md"

    seed_rows = [normalized_seed_row(row) for row in queue_rows]
    text_rows: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []
    for row in queue_rows:
        source = source_index.get(int(row["post_id"]))
        if source is None:
            raise ValueError(f"missing source row for post_id {row['post_id']}")
        canary_row = canary_input_row(source, row, loop_label=prefix)
        if has_image_source(source):
            image_rows.append(canary_row)
        else:
            text_rows.append(canary_row)

    role_counts = Counter(str(row["queue_role"]) for row in queue_rows)
    selection_counts = Counter(str(row["selection_bucket"]) for row in queue_rows)
    disagreement_counts = Counter(str(row.get("disagreement_type")) for row in queue_rows)
    manifest = {
        "schema_version": 1,
        "created_by": "tools/build_completed779_hermes_expansion.py",
        "prefix": prefix,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "source": {
            "action_queue_path": str(action_queue_path),
            "source_path": str(source_path),
            "balanced_seed_path": str(balanced_seed_path),
            "source_refresh_compare_path": str(source_refresh_compare_path),
            "control_compare_path": str(control_compare_path),
            "loop4_compare_path": str(loop4_compare_path),
            "extra_exclude_paths": [str(path) for path in extra_exclude_paths],
        },
        "selection": {
            "main_targets": targets,
            "per_work_cap": per_work_cap,
            "main_excluded_id_count": len(main_excluded_ids),
            "extra_excluded_id_count": len(extra_excluded_ids),
            "exclude_consumed_controls": exclude_consumed_controls,
            "exclude_balanced_main": exclude_balanced_main,
            "explicit_control_post_ids": sorted(explicit_control_ids),
            "main_consumed_overlap": sorted(main_consumed_overlap),
            "control_consumed_overlap": sorted(control_consumed_overlap),
            "selected_consumed_overlap": sorted(disallowed_consumed_overlap),
            "overlap_blocked_count": len(extra_excluded_ids),
            "queue_rows": len(queue_rows),
            "unique_post_ids": len({row["post_id"] for row in queue_rows}),
            "duplicate_post_ids": sorted(
                pid for pid, count in Counter(row["post_id"] for row in queue_rows).items() if count > 1
            ),
            "role_counts": dict(sorted(role_counts.items())),
            "selection_bucket_counts": dict(sorted(selection_counts.items())),
            "disagreement_counts": dict(sorted(disagreement_counts.items())),
        },
        "split": {
            "text_url_comment_rows": len(text_rows),
            "text_url_comment_post_ids": [post_id(row) for row in text_rows],
            "image_ocr_rows": len(image_rows),
            "image_ocr_post_ids": [post_id(row) for row in image_rows],
        },
        "outputs": {
            "queue_json": str(queue_path),
            "queue_ko_md": str(queue_md_path),
            "seed_jsonl": str(seed_path),
            "text_url_comment_jsonl": str(text_path),
            "image_ocr_jsonl": str(image_path),
            "manifest_json": str(manifest_path),
            "report_ko_md": str(report_path),
        },
    }
    queue_payload = {
        "schema_version": 1,
        "canary_kind": prefix,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "manifest_path": str(manifest_path),
        "rows": queue_rows,
    }
    write_json(queue_path, queue_payload)
    write_jsonl(seed_path, seed_rows)
    write_jsonl(text_path, text_rows)
    write_jsonl(image_path, image_rows)
    write_json(manifest_path, manifest)
    write_queue_markdown(queue_md_path, queue_payload, manifest)
    write_input_report(report_path, manifest)
    return manifest


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split()).replace("|", "\\|")


def write_queue_markdown(path: Path, queue: dict[str, Any], manifest: dict[str, Any]) -> None:
    rows = queue.get("rows") or []
    lines = [
        f"# completed779 Hermes Expansion Queue - {queue.get('canary_kind') or manifest.get('prefix')}",
        "",
        f"- rows: `{len(rows)}`",
        f"- main rows: `{manifest['selection']['role_counts'].get('main', 0)}`",
        f"- control rows: `{manifest['selection']['role_counts'].get('control', 0)}`",
        f"- text/url/comment rows: `{manifest['split']['text_url_comment_rows']}`",
        f"- image/OCR rows: `{manifest['split']['image_ocr_rows']}`",
        "- semantic quality: `REVIEW-LOCKED`",
        "- full scan approval: `false`",
        "",
        "## Selection Buckets",
        "",
    ]
    for key, value in manifest["selection"]["selection_bucket_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| role | post_id | bucket | issue | expected | before | previous after | next hook |",
            "|---|---:|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        expected = " / ".join(item for item in [str(row.get("expected_title") or ""), str(row.get("expected_url") or "")] if item)
        before = " / ".join(item for item in [str(row.get("before_title") or ""), str(row.get("before_url") or "")] if item)
        after = " / ".join(item for item in [str(row.get("after_title") or ""), str(row.get("after_url") or "")] if item)
        lines.append(
            "| {role} | {post_id} | {bucket} | {issue} | {expected} | {before} | {after} | {hook} |".format(
                role=_md_cell(row.get("queue_role")),
                post_id=row.get("post_id"),
                bucket=_md_cell(row.get("selection_bucket")),
                issue=_md_cell(row.get("disagreement_type")),
                expected=_md_cell(expected),
                before=_md_cell(before),
                after=_md_cell(after),
                hook=_md_cell(row.get("suspected_code_hook")),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_input_report(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        f"# completed779 Hermes Input Report - {manifest.get('prefix')}",
        "",
        f"- queue rows: `{manifest['selection']['queue_rows']}`",
        f"- unique post_ids: `{manifest['selection']['unique_post_ids']}`",
        f"- duplicate post_ids: `{len(manifest['selection']['duplicate_post_ids'])}`",
        f"- text/url/comment rows: `{manifest['split']['text_url_comment_rows']}`",
        f"- image/OCR rows: `{manifest['split']['image_ocr_rows']}`",
        "- semantic quality: `REVIEW-LOCKED`",
        "- full scan approval: `false`",
        "",
        "## Role Counts",
        "",
    ]
    for key, value in manifest["selection"]["role_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Disagreement Counts", ""])
    for key, value in manifest["selection"]["disagreement_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Text/URL/Comment Post IDs",
            "",
            ", ".join(str(pid) for pid in manifest["split"]["text_url_comment_post_ids"]),
            "",
            "## Image/OCR Post IDs",
            "",
            ", ".join(str(pid) for pid in manifest["split"]["image_ocr_post_ids"]),
            "",
            "## Outputs",
            "",
        ]
    )
    for key, value in manifest["outputs"].items():
        lines.append(f"- `{key}`: `{value}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action-queue", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--balanced-seed", type=Path, required=True)
    parser.add_argument("--source-refresh-compare", type=Path, required=True)
    parser.add_argument(
        "--control-compare",
        type=Path,
        help="Optional compare artifact used for control rows; defaults to --source-refresh-compare.",
    )
    parser.add_argument(
        "--control-bucket-prefix",
        help="Prefix for control selection buckets; defaults to source_refresh.",
    )
    parser.add_argument("--loop4-compare", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="hermes_loop5_source_residual")
    parser.add_argument("--residual-review-controls", type=int, default=12)
    parser.add_argument("--residual-url-controls", type=int, default=8)
    parser.add_argument("--per-work-cap", type=int, default=3)
    parser.add_argument(
        "--main-target",
        action="append",
        default=[],
        metavar="ISSUE=COUNT",
        help="Override/add a main selection target. Repeatable. Use with --clear-default-main-targets for a custom lane.",
    )
    parser.add_argument(
        "--clear-default-main-targets",
        action="store_true",
        help="Start main target selection from an empty set instead of MAIN_TARGETS.",
    )
    parser.add_argument(
        "--exclude-rows",
        type=Path,
        action="append",
        default=[],
        help="Additional row/compare/queue artifacts whose post_ids are already consumed.",
    )
    parser.add_argument(
        "--exclude-glob",
        action="append",
        default=[],
        help="Glob pattern for additional consumed row artifacts.",
    )
    parser.add_argument(
        "--allow-consumed-controls",
        action="store_true",
        help="Allow control rows to come from consumed artifacts while still excluding consumed rows from main selection.",
    )
    parser.add_argument(
        "--allow-balanced-main",
        action="store_true",
        help="Allow balanced P0 seed rows to be selected as main rows for explicit regression lanes.",
    )
    parser.add_argument(
        "--control-post-id",
        type=int,
        action="append",
        default=[],
        help="Add an explicit consumed-or-unconsumed post_id as a regression control row.",
    )
    return parser.parse_args()


def parse_main_targets(values: list[str], *, clear_defaults: bool = False) -> dict[str, int] | None:
    if not values and not clear_defaults:
        return None
    targets: dict[str, int] = {} if clear_defaults else dict(MAIN_TARGETS)
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"--main-target must be ISSUE=COUNT, got {raw!r}")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"--main-target issue is empty: {raw!r}")
        count = int(value)
        if count < 0:
            raise ValueError(f"--main-target count must be >= 0: {raw!r}")
        targets[key] = count
    return targets


def main() -> None:
    args = parse_args()
    main_targets = parse_main_targets(args.main_target, clear_defaults=args.clear_default_main_targets)
    manifest = build_queue(
        action_queue_path=args.action_queue,
        source_path=args.source,
        balanced_seed_path=args.balanced_seed,
        source_refresh_compare_path=args.source_refresh_compare,
        loop4_compare_path=args.loop4_compare,
        out_dir=args.out_dir,
        prefix=args.prefix,
        main_targets=main_targets,
        residual_review_controls=args.residual_review_controls,
        residual_url_controls=args.residual_url_controls,
        per_work_cap=args.per_work_cap,
        extra_exclude_paths=args.exclude_rows,
        extra_exclude_globs=args.exclude_glob,
        control_compare_path=args.control_compare,
        control_bucket_prefix=args.control_bucket_prefix,
        exclude_consumed_controls=not args.allow_consumed_controls,
        exclude_balanced_main=not args.allow_balanced_main,
        explicit_control_post_ids=args.control_post_id,
    )
    print(
        json.dumps(
            {
                "queue_rows": manifest["selection"]["queue_rows"],
                "duplicates": len(manifest["selection"]["duplicate_post_ids"]),
                "role_counts": manifest["selection"]["role_counts"],
                "selection_bucket_counts": manifest["selection"]["selection_bucket_counts"],
                "split": {
                    "text_url_comment_rows": manifest["split"]["text_url_comment_rows"],
                    "image_ocr_rows": manifest["split"]["image_ocr_rows"],
                },
                "outputs": manifest["outputs"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
