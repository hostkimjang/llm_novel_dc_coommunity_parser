"""Build the completed779 native-web issue index and P0 canary seed files."""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


VERDICT_RE = re.compile(r"^verdict_(\d{3})\.json$")
SENTINEL_RE = re.compile(r"^verdict_.*sentinel.*\.json$")
NON_ACCEPT_LABELS = {"REPROCESS", "HOLD", "INFO_MISSING", "REJECT"}

DEFAULT_SEED_TARGETS = {
    "precision_identity_high": 15,
    "candidate_comment_multi": 15,
    "recall_relevance_representative": 25,
    "source_url_hygiene": 10,
}

PRECISION_TYPES = {
    "wrong_work",
    "garbage_title",
    "over_resolved",
    "overresolved_generic_trope",
    "reason_evidence_mismatch",
    "title_correct_url_mismatch",
    "url_mismatch",
}
PRECISION_FIRST_TYPES = {"wrong_work"}
CANDIDATE_TYPES = {
    "comment_explicit_title_missed",
    "candidate_preservation_missing",
    "conflicting_or_multi_candidate",
}
RECALL_RELEVANCE_TYPES = {
    "under_resolved",
    "under_resolved_false_negative",
    "wrong_relevance",
    "relevance",
    "trope_or_author_talk_risk",
}
SOURCE_URL_TYPES = {
    "heretic_url_null",
    "url_mismatch",
    "title_correct_url_mismatch",
    "reason_evidence_mismatch",
}

MACRO_BUCKETS = {
    "recall_under_resolved_or_missed_candidate": {
        "under_resolved",
        "under_resolved_false_negative",
        "comment_explicit_title_missed",
        "candidate_preservation_missing",
    },
    "relevance_boundary_false_negative_or_false_positive": {
        "wrong_relevance",
        "relevance",
        "trope_or_author_talk_risk",
        "over_resolved",
        "overresolved_generic_trope",
    },
    "primary_selection_or_identity_precision": {
        "wrong_work",
        "conflicting_or_multi_candidate",
        "reason_evidence_mismatch",
        "garbage_title",
        "title_correct_url_mismatch",
        "url_mismatch",
    },
    "source_url_or_evidence_hygiene": {
        "heretic_url_null",
        "url_mismatch",
        "title_correct_url_mismatch",
        "reason_evidence_mismatch",
    },
    "manual_scope_or_info_gap": {
        "uncertain",
        "trope_or_author_talk_risk",
        "relevance",
    },
}

SEVERITY_RANK = {"high": 0, "med": 1, "medium": 1, "low": 2, None: 3}
EVIDENCE_RANK = {"Strong": 0, "Medium": 1, "Weak": 2, "Missing": 3, None: 4}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def standard_verdict_files(root: Path) -> list[Path]:
    files: list[tuple[int, Path]] = []
    for path in (root / "verdicts").glob("verdict_*.json"):
        match = VERDICT_RE.match(path.name)
        if match:
            files.append((int(match.group(1)), path))
    return [path for _batch, path in sorted(files)]


def sentinel_verdict_files(root: Path) -> list[Path]:
    return sorted(path for path in (root / "verdicts").glob("verdict_*.json") if SENTINEL_RE.match(path.name))


def payload_verdicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        verdicts = payload.get("verdicts")
        if isinstance(verdicts, list):
            return [item for item in verdicts if isinstance(item, dict)]
        if "post_id" in payload:
            return [payload]
    return []


def load_verdicts(judge_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load native-web verdicts with post_id dedupe.

    Sentinel files are read first so a normal batch verdict for the same post
    becomes the canonical row. The output order follows numeric post_id.
    """

    deduped: dict[int, dict[str, Any]] = {}
    raw_rows = 0
    duplicate_ids: set[int] = set()
    files = sentinel_verdict_files(judge_root) + standard_verdict_files(judge_root)
    for path in files:
        for verdict in payload_verdicts(load_json(path)):
            raw_rows += 1
            post_id = int(verdict["post_id"])
            if post_id in deduped:
                duplicate_ids.add(post_id)
            row = dict(verdict)
            row["_verdict_file"] = str(path)
            deduped[post_id] = row
    metadata = {
        "verdict_files": len(files),
        "raw_verdict_rows": raw_rows,
        "deduped_duplicates_removed": raw_rows - len(deduped),
        "duplicate_post_ids_removed": sorted(duplicate_ids),
        "duplicate_post_ids_after_dedupe": 0,
    }
    return [deduped[key] for key in sorted(deduped)], metadata


def load_source_rows(result_path: Path) -> list[dict[str, Any]]:
    payload = load_json(result_path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        rows = payload["rows"]
    elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
        rows = payload["results"]
    else:
        raise ValueError(f"unsupported result payload shape: {result_path}")
    return [row for row in rows if isinstance(row, dict) and row.get("post_id") is not None]


def non_accept(verdict: dict[str, Any]) -> bool:
    return verdict.get("resolution_label") in NON_ACCEPT_LABELS


def counter_dict(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field)) for row in rows).items(), key=lambda item: (-item[1], item[0])))


def issue_tags(verdict: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    disagreement = verdict.get("disagreement_type")
    if disagreement and disagreement != "none":
        tags.append(str(disagreement))
    hold_reason = verdict.get("hold_reason")
    if hold_reason and hold_reason != "na" and hold_reason not in tags:
        tags.append(str(hold_reason))
    action = verdict.get("recommended_action")
    if action and action not in {"no_action", "none"}:
        tags.append(f"action:{action}")
    return tags


def macro_bucket_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {name: 0 for name in MACRO_BUCKETS}
    for row in rows:
        disagreement = row.get("disagreement_type")
        for name, members in MACRO_BUCKETS.items():
            if disagreement in members:
                counts[name] += 1
    return counts


def repeated_work_counts(rows: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        title = row.get("independent_official_title") or row.get("pipeline_official_title")
        if title:
            counter[str(title)] += 1
    return [{"official_title": title, "count": count} for title, count in counter.most_common(limit)]


def seed_sort_key(row: dict[str, Any]) -> tuple[int, int, int]:
    return (
        SEVERITY_RANK.get(row.get("severity"), 3),
        EVIDENCE_RANK.get(row.get("search_evidence_grade"), 4),
        int(row["post_id"]),
    )


def add_seed(
    selected: list[dict[str, Any]],
    selected_ids: set[int],
    candidates: list[dict[str, Any]],
    bucket: str,
    target: int,
) -> None:
    current = sum(1 for row in selected if row.get("seed_bucket") == bucket)
    for row in candidates:
        if current >= target:
            break
        post_id = int(row["post_id"])
        if post_id in selected_ids:
            continue
        seeded = dict(row)
        seeded["seed_bucket"] = bucket
        seeded["seed_reason"] = f"{bucket}:{row.get('disagreement_type')}/{row.get('recommended_action')}"
        selected.append(seeded)
        selected_ids.add(post_id)
        current += 1


def select_balanced_seed(
    verdicts: list[dict[str, Any]],
    seed_targets: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    targets = dict(seed_targets or DEFAULT_SEED_TARGETS)
    rows = [row for row in verdicts if non_accept(row)]
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()

    wrong_work = sorted(
        [row for row in rows if row.get("disagreement_type") in PRECISION_FIRST_TYPES],
        key=seed_sort_key,
    )
    precision_rest = sorted(
        [
            row
            for row in rows
            if row.get("disagreement_type") in PRECISION_TYPES
            and row.get("disagreement_type") not in PRECISION_FIRST_TYPES
        ],
        key=seed_sort_key,
    )
    add_seed(selected, selected_ids, wrong_work + precision_rest, "precision_identity_high", targets["precision_identity_high"])

    candidate_rows = sorted(
        [row for row in rows if row.get("disagreement_type") in CANDIDATE_TYPES],
        key=seed_sort_key,
    )
    add_seed(selected, selected_ids, candidate_rows, "candidate_comment_multi", targets["candidate_comment_multi"])

    recall_rows = sorted(
        [row for row in rows if row.get("disagreement_type") in RECALL_RELEVANCE_TYPES],
        key=seed_sort_key,
    )
    add_seed(
        selected,
        selected_ids,
        recall_rows,
        "recall_relevance_representative",
        targets["recall_relevance_representative"],
    )

    source_rows = sorted(
        [row for row in rows if row.get("disagreement_type") in SOURCE_URL_TYPES],
        key=seed_sort_key,
    )
    add_seed(selected, selected_ids, source_rows, "source_url_hygiene", targets["source_url_hygiene"])

    for bucket, target in targets.items():
        have = sum(1 for row in selected if row.get("seed_bucket") == bucket)
        if have < target:
            fallback = sorted(rows, key=seed_sort_key)
            add_seed(selected, selected_ids, fallback, bucket, target)

    bucket_counts = Counter(str(row["seed_bucket"]) for row in selected)
    wrong_work_ids = sorted(int(row["post_id"]) for row in rows if row.get("disagreement_type") == "wrong_work")
    seeded_wrong_work_ids = sorted(
        int(row["post_id"]) for row in selected if row.get("disagreement_type") == "wrong_work"
    )
    metadata = {
        "target_counts": targets,
        "actual_counts": dict(sorted(bucket_counts.items())),
        "seed_count": len(selected),
        "sentinel_11694064_included": any(int(row["post_id"]) == 11694064 for row in selected),
        "wrong_work_post_ids": wrong_work_ids,
        "wrong_work_seed_post_ids": seeded_wrong_work_ids,
        "wrong_work_all_seeded": wrong_work_ids == seeded_wrong_work_ids,
        "warnings": [
            f"{bucket} target={target} actual={bucket_counts.get(bucket, 0)}"
            for bucket, target in targets.items()
            if bucket_counts.get(bucket, 0) != target
        ],
    }
    return sorted(selected, key=lambda row: (str(row["seed_bucket"]), int(row["post_id"]))), metadata


def extract_identity(row: dict[str, Any]) -> dict[str, Any]:
    identity = (row.get("analysis_result") or {}).get("identity") or {}
    novel_identity = identity.get("novel_identity") or {}
    return {
        "official_title": novel_identity.get("official_title"),
        "heretic_url": novel_identity.get("heretic_url"),
        "is_novel_related": identity.get("is_novel_related"),
        "is_resolved_work_discussion": identity.get("is_resolved_work_discussion"),
        "title_resolution_state": identity.get("title_resolution_state"),
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "candidate_count": len(identity.get("title_candidates") or []),
        "candidate_ledger_status": identity.get("candidate_ledger_status"),
    }


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


def build_action_queue(
    verdicts: list[dict[str, Any]],
    source_index: dict[int, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    queue: dict[str, dict[str, Any]] = {}
    for row in verdicts:
        if not non_accept(row):
            continue
        post_id = int(row["post_id"])
        source = source_index.get(post_id, {})
        queue[str(post_id)] = {
            "post_id": post_id,
            "title": source.get("title"),
            "url": source.get("url"),
            "source_identity": extract_identity(source),
            "resolution_label": row.get("resolution_label"),
            "disagreement_type": row.get("disagreement_type"),
            "severity": row.get("severity"),
            "recommended_action": row.get("recommended_action"),
            "search_evidence_grade": row.get("search_evidence_grade"),
            "independent_official_title": row.get("independent_official_title"),
            "independent_url": row.get("independent_url"),
            "pipeline_official_title": row.get("pipeline_official_title"),
            "pipeline_url": row.get("pipeline_url"),
            "source_urls": row.get("source_urls") or [],
            "korean_reason": row.get("korean_reason"),
            "issue_tags": issue_tags(row),
            "macro_buckets": [
                name
                for name, members in MACRO_BUCKETS.items()
                if row.get("disagreement_type") in members
            ],
        }
    return dict(sorted(queue.items(), key=lambda item: int(item[0])))


def canary_seed_row(source_row: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(source_row)
    row.pop("analysis_result", None)
    row["_judge_seed"] = {
        "post_id": int(seed["post_id"]),
        "seed_bucket": seed.get("seed_bucket"),
        "seed_reason": seed.get("seed_reason"),
        "resolution_label": seed.get("resolution_label"),
        "disagreement_type": seed.get("disagreement_type"),
        "severity": seed.get("severity"),
        "recommended_action": seed.get("recommended_action"),
        "search_evidence_grade": seed.get("search_evidence_grade"),
        "independent_official_title": seed.get("independent_official_title"),
        "independent_url": seed.get("independent_url"),
        "pipeline_official_title": seed.get("pipeline_official_title"),
        "pipeline_url": seed.get("pipeline_url"),
        "source_urls": seed.get("source_urls") or [],
        "korean_reason": seed.get("korean_reason"),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    return row


def build_issue_index(
    result_path: Path,
    judge_root: Path,
    out_dir: Path,
    *,
    expected_total: int | None = 779,
    expected_non_accept: int | None = 266,
    seed_targets: dict[str, int] | None = None,
) -> dict[str, Any]:
    source_rows = load_source_rows(result_path)
    source_index = {int(row["post_id"]): row for row in source_rows}
    verdicts, verdict_metadata = load_verdicts(judge_root)
    verdict_index = {int(row["post_id"]): row for row in verdicts}

    missing_from_verdicts = sorted(set(source_index) - set(verdict_index))
    extra_verdict_ids = sorted(set(verdict_index) - set(source_index))
    non_accept_rows = [row for row in verdicts if non_accept(row)]
    accepted_rows = [row for row in verdicts if not non_accept(row)]
    seed_rows, seed_metadata = select_balanced_seed(verdicts, seed_targets=seed_targets)

    action_queue = build_action_queue(verdicts, source_index)
    seed_jsonl_rows = []
    text_rows: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []
    for seed in seed_rows:
        post_id = int(seed["post_id"])
        source = source_index.get(post_id)
        if source is None:
            continue
        seed_row = {
            "post_id": post_id,
            "seed_bucket": seed.get("seed_bucket"),
            "seed_reason": seed.get("seed_reason"),
            "resolution_label": seed.get("resolution_label"),
            "disagreement_type": seed.get("disagreement_type"),
            "severity": seed.get("severity"),
            "recommended_action": seed.get("recommended_action"),
            "search_evidence_grade": seed.get("search_evidence_grade"),
            "source_title": source.get("title"),
            "source_url": source.get("url"),
            "source_identity": extract_identity(source),
            "independent_official_title": seed.get("independent_official_title"),
            "independent_url": seed.get("independent_url"),
            "pipeline_official_title": seed.get("pipeline_official_title"),
            "pipeline_url": seed.get("pipeline_url"),
            "source_urls": seed.get("source_urls") or [],
            "korean_reason": seed.get("korean_reason"),
        }
        seed_jsonl_rows.append(seed_row)
        canary_row = canary_seed_row(source, seed)
        if has_image_source(source):
            image_rows.append(canary_row)
        else:
            text_rows.append(canary_row)

    summary = {
        "created_by": "tools/build_completed779_issue_index.py",
        "result_path": str(result_path),
        "judge_root": str(judge_root),
        "out_dir": str(out_dir),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "source_coverage": {
            "completed_subset_rows": len(source_rows),
            "primary_flushed_rows": 757,
            "shutdown_pending_flush_gap": 22,
            "primary_json_is_partial_for_improvement": True,
        },
        "coverage": {
            "source_unique_post_ids": len(source_index),
            "verdict_unique_post_ids": len(verdict_index),
            "missing": len(missing_from_verdicts),
            "missing_post_ids": missing_from_verdicts,
            "extra_verdict_ids": extra_verdict_ids,
            **verdict_metadata,
        },
        "native_web_aggregate": {
            "total": len(verdicts),
            "accept": len(accepted_rows),
            "non_accept": len(non_accept_rows),
            "resolution_label": counter_dict(verdicts, "resolution_label"),
            "disagreement_type": counter_dict(verdicts, "disagreement_type"),
            "recommended_action": counter_dict(verdicts, "recommended_action"),
            "severity": counter_dict(verdicts, "severity"),
            "search_evidence_grade": counter_dict(verdicts, "search_evidence_grade"),
            "macro_buckets": macro_bucket_counts(non_accept_rows),
            "repeated_works": repeated_work_counts(non_accept_rows),
        },
        "deterministic_full_post_judge_aggregate": {
            "status": "separate_stale_aggregate_do_not_mix_with_native_web",
            "report_path": "out/full_post_judge_20260620_165159_711176_completed779/report/full_post_judge_report.md",
            "metrics_path": "out/full_post_judge_20260620_165159_711176_completed779/report/full_post_judge_metrics.json",
        },
        "seed_packet": {
            **seed_metadata,
            "text_url_comment_rows": len(text_rows),
            "image_ocr_rows": len(image_rows),
        },
        "workstreams": {
            "recall_under_resolution": "direct title, strong alias, comment URL/title, OCR explicit title, official detail URL recovery",
            "relevance_boundary": "recover in-work setting/character/alias posts while preserving trope/platform/author meta as HOLD",
            "primary_selection_precision": "prefer source-local alias strength over unrelated primary promotion",
            "source_url_hygiene": "official URL enrichment or URL mismatch lint/HOLD",
            "candidate_ledger_multi_candidate": "preserve recommendations/comments/comparisons without forced single-title promotion",
            "prompt_orchestration_comment_ocr": "include comment/OCR/short alias/character clusters in search intent and evidence catalog",
        },
        "strict_expectations": {
            "expected_total": expected_total,
            "expected_non_accept": expected_non_accept,
            "total_matches": expected_total is None or len(verdicts) == expected_total,
            "non_accept_matches": expected_non_accept is None or len(non_accept_rows) == expected_non_accept,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "native_web_issue_index.json", summary)
    write_json(out_dir / "action_queue_by_post_id.json", action_queue)
    write_jsonl(out_dir / "balanced_p0_seed.jsonl", seed_jsonl_rows)
    write_jsonl(out_dir / "inputs" / "balanced_p0_text_url_comment.jsonl", text_rows)
    write_jsonl(out_dir / "inputs" / "balanced_p0_image_ocr.jsonl", image_rows)
    write_markdown_report(out_dir / "native_web_issue_index_ko.md", summary)

    if expected_total is not None and len(verdicts) != expected_total:
        raise ValueError(f"expected total {expected_total}, got {len(verdicts)}")
    if expected_non_accept is not None and len(non_accept_rows) != expected_non_accept:
        raise ValueError(f"expected non-ACCEPT {expected_non_accept}, got {len(non_accept_rows)}")
    if missing_from_verdicts:
        raise ValueError(f"missing verdicts for post_ids: {missing_from_verdicts[:10]}")
    return summary


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    aggregate = summary["native_web_aggregate"]
    coverage = summary["coverage"]
    seed = summary["seed_packet"]
    lines = [
        "# completed779 Native-Web Issue Index",
        "",
        "## 결론",
        "",
        "- completed subset `779`건 기준 native-web verdict를 `post_id`로 dedupe해 issue index를 생성했다.",
        f"- unique verdict/source coverage: `{coverage['verdict_unique_post_ids']}/{coverage['source_unique_post_ids']}`",
        f"- missing: `{coverage['missing']}`",
        f"- duplicate after dedupe: `{coverage['duplicate_post_ids_after_dedupe']}`",
        f"- non-ACCEPT: `{aggregate['non_accept']}`",
        "- semantic quality: `REVIEW-LOCKED`",
        "- full scan approval: `false`",
        "",
        "## Stale Aggregate 금지",
        "",
        "deterministic `full_post_judge_report.md` 집계와 native-web verdict 집계를 섞지 않는다. 개선 우선순위와 seed packet은 이 native-web aggregate만 기준으로 한다.",
        "",
        "## Resolution Labels",
        "",
    ]
    for key, value in aggregate["resolution_label"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## 주요 Issue Types", ""])
    for key, value in aggregate["disagreement_type"].items():
        if key == "none":
            continue
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Macro Buckets", ""])
    for key, value in aggregate["macro_buckets"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## 반복 작품/패턴", ""])
    for item in aggregate["repeated_works"][:12]:
        lines.append(f"- `{item['official_title']}`: `{item['count']}`")
    lines.extend(
        [
            "",
            "## Balanced P0 Seed",
            "",
            f"- total: `{seed['seed_count']}`",
            f"- text/url/comment input: `{seed['text_url_comment_rows']}`",
            f"- image/OCR input: `{seed['image_ocr_rows']}`",
            f"- `11694064` included: `{str(seed['sentinel_11694064_included']).lower()}`",
            f"- `wrong_work` all seeded: `{str(seed['wrong_work_all_seeded']).lower()}`",
            "",
        ]
    )
    for key, value in seed["actual_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    if seed["warnings"]:
        lines.extend(["", "## Seed Warnings", ""])
        for warning in seed["warnings"]:
            lines.append(f"- {warning}")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- `native_web_issue_index.json`",
            "- `action_queue_by_post_id.json`",
            "- `balanced_p0_seed.jsonl`",
            "- `inputs/balanced_p0_text_url_comment.jsonl`",
            "- `inputs/balanced_p0_image_ocr.jsonl`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--judge-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--expected-total", type=int, default=779)
    parser.add_argument("--expected-non-accept", type=int, default=266)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_issue_index(
        args.result,
        args.judge_root,
        args.out_dir,
        expected_total=args.expected_total,
        expected_non_accept=args.expected_non_accept,
    )
    print(
        json.dumps(
            {
                "total": summary["native_web_aggregate"]["total"],
                "non_accept": summary["native_web_aggregate"]["non_accept"],
                "missing": summary["coverage"]["missing"],
                "duplicate_after_dedupe": summary["coverage"]["duplicate_post_ids_after_dedupe"],
                "seed_count": summary["seed_packet"]["seed_count"],
                "seed_counts": summary["seed_packet"]["actual_counts"],
                "out_dir": summary["out_dir"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
