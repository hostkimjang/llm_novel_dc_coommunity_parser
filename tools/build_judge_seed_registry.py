from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


RECALL_TYPES = {"under_resolved_false_negative"}
PRECISION_TYPES = {
    "cross_media_or_famous_mismatch",
    "wrong_work",
    "over_resolved",
    "garbage_title",
}
HYGIENE_TYPES = {"wrong_discussion_type", "wrong_relevance", "title_noisy_ocr"}
SEED_TYPES = RECALL_TYPES | PRECISION_TYPES | HYGIENE_TYPES
SEVERITY_RANK = {"high": 0, "med": 1, "medium": 1, "low": 2}
PARALLEL_MAX = 36
PIPELINE_SHADOW_LABELS = {
    "candidate_generation_miss",
    "promotion_blocked",
    "hold_unresolved",
    "safe_resolved",
    "official_title_lint",
    "identity_consistency_lint",
    "output_consistency_lint",
    "review_only",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                payload.setdefault("_source_line_number", line_no)
                rows.append(payload)
    return rows


def expand_source_patterns(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if not matches and Path(pattern).is_file():
            matches = [pattern]
        for match in matches:
            path = Path(match)
            if path.is_file() and path not in paths:
                paths.append(path)
    return paths


def load_source_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows = load_jsonl(path)
    else:
        payload = load_json(path)
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            rows = normalize_result_rows(payload)
        else:
            rows = []
    for row in rows:
        row.setdefault("_source_path", path.as_posix())
    return rows


def source_quality_score(row: dict[str, Any]) -> int:
    score = 0
    if row.get("content_blocks"):
        score += 20
    if row.get("image_urls"):
        score += 20
    if row.get("url"):
        score += 5
    if row.get("gallery_id"):
        score += 3
    if row.get("content"):
        score += 4
    if row.get("body"):
        score += 3
    if row.get("comments"):
        score += 2
    if row.get("pipe"):
        score += 1
    if row.get("analysis_result"):
        score += 8
    return score


def load_source_rows(patterns: list[str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    source_by_id: dict[str, dict[str, Any]] = {}
    source_paths: list[str] = []
    for path in expand_source_patterns(patterns):
        source_paths.append(path.as_posix())
        for row in load_source_file(path):
            pid = post_id_key(row.get("post_id"))
            if not pid:
                continue
            current = source_by_id.get(pid)
            if current is None or source_quality_score(row) > source_quality_score(current):
                source_by_id[pid] = row
    return source_by_id, source_paths


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def post_id_key(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def sort_post_id(value: Any) -> tuple[int, str]:
    key = post_id_key(value)
    return (int(key), "") if key.isdigit() else (10**18, key)


def seed_group(disagreement_type: str) -> str:
    if disagreement_type in RECALL_TYPES:
        return "recall"
    if disagreement_type in PRECISION_TYPES:
        return "precision"
    if disagreement_type in HYGIENE_TYPES:
        return "hygiene"
    return "excluded"


def nested_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def identity_from_result_row(row: dict[str, Any]) -> dict[str, Any]:
    analysis_result = nested_dict(row.get("analysis_result") or row.get("result"))
    identity = nested_dict(analysis_result.get("identity") or row.get("identity"))
    if identity:
        return identity
    pipe = nested_dict(row.get("pipe"))
    if pipe:
        official = str(pipe.get("official_title") or "").strip()
        return {
            "is_relevant": pipe.get("is_relevant"),
            "is_novel_related": None,
            "is_resolved_work_discussion": bool(official) if official else False,
            "title_resolution_state": pipe.get("title_resolution_state"),
            "title_resolution_allowed": None if official else False,
            "work_resolution": pipe.get("work_resolution"),
            "discussion_type": pipe.get("discussion_type"),
            "anchor_type": pipe.get("anchor_type"),
            "anchor_strength": None,
            "topicality": None,
            "context_sources": ["judge_batch_context"],
            "novel_identity": (
                {
                    "official_title": official,
                    "confidence": pipe.get("confidence") or "None",
                    "heretic_url": None,
                }
                if official
                else None
            ),
        }
    return {}


def official_title(identity: dict[str, Any]) -> str:
    novel_identity = nested_dict(identity.get("novel_identity"))
    return str(
        novel_identity.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
        or ""
    ).strip()


def candidate_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""
    return str(
        item.get("official_title")
        or item.get("title")
        or item.get("name")
        or item.get("surface")
        or item.get("decoded_term")
        or ""
    ).strip()


def collect_candidate_titles(identity: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for field in (
        "title_candidates",
        "mentioned_works",
        "recommendation_candidates",
        "secondary_reference_works",
    ):
        value = identity.get(field)
        if isinstance(value, list):
            for item in value:
                name = candidate_name(item)
                if name and name not in candidates:
                    candidates.append(name)
        else:
            name = candidate_name(value)
            if name and name not in candidates:
                candidates.append(name)
    for field in ("primary_work", "future_watch_target", "comparison_target"):
        name = candidate_name(identity.get(field))
        if name and name not in candidates:
            candidates.append(name)
    return candidates


def has_evidence_catalog(identity: dict[str, Any]) -> bool:
    for field in ("search_evidence_catalog", "image_evidence_catalog", "entity_mentions"):
        value = identity.get(field)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def official_title_lint_reasons(identity: dict[str, Any]) -> list[str]:
    title = official_title(identity)
    if not title:
        return []
    reasons: list[str] = []
    if identity.get("title_resolution_allowed") is False:
        reasons.append("official_title_present_when_title_resolution_allowed_false")
    work_resolution = str(identity.get("work_resolution") or "").strip().lower()
    if work_resolution in {"none", "context_only", "nonwork", "unresolved"}:
        reasons.append(f"official_title_present_with_work_resolution_{work_resolution}")
    state = str(identity.get("title_resolution_state") or "").strip().lower()
    if state and state not in {"resolved", "direct_resolved"}:
        reasons.append(f"official_title_present_with_title_resolution_state_{state}")
    return reasons


def identity_consistency_lint_reasons(identity: dict[str, Any], disagreement_type: str) -> list[str]:
    title = official_title(identity)
    reasons: list[str] = []
    if title and identity.get("is_resolved_work_discussion") is False:
        reasons.append("official_title_present_when_is_resolved_work_discussion_false")
    if disagreement_type in PRECISION_TYPES and title:
        reasons.append(f"judge_precision_seed_{disagreement_type}")
    if disagreement_type in HYGIENE_TYPES:
        reasons.append(f"judge_hygiene_seed_{disagreement_type}")
    return reasons


def build_candidate_ledger(row: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    identity = identity_from_result_row(row)
    runtime_ledger = identity.get("candidate_ledger")
    candidates = collect_candidate_titles(identity)
    title = official_title(identity)
    o_lints = identity.get("official_title_lint") or official_title_lint_reasons(identity)
    i_lints = identity.get("identity_consistency_lint") or identity_consistency_lint_reasons(identity, str(review.get("disagreement_type") or ""))
    out_lints = identity.get("output_consistency_lint") or []
    ledger = {
        "pipeline_official_title": title or None,
        "title_candidates": candidates,
        "candidate_count": len(candidates),
        "title_resolution_state": identity.get("title_resolution_state"),
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "work_resolution": identity.get("work_resolution"),
        "discussion_type": identity.get("discussion_type"),
        "topicality": identity.get("topicality"),
        "is_novel_related": identity.get("is_novel_related"),
        "is_resolved_work_discussion": identity.get("is_resolved_work_discussion"),
        "anchor_type": identity.get("anchor_type"),
        "anchor_strength": identity.get("anchor_strength"),
        "context_sources": identity.get("context_sources") or [],
        "has_evidence_catalog": has_evidence_catalog(identity),
        "official_title_lint_reasons": o_lints,
        "identity_consistency_lint_reasons": i_lints,
        "output_consistency_lint_reasons": out_lints,
        "runtime_candidate_ledger_present": isinstance(runtime_ledger, dict),
        "runtime_candidate_ledger_status": identity.get("candidate_ledger_status"),
        "judge_likely_correct": review.get("likely_correct"),
        "judge_note": review.get("note"),
        "judge_claude_take": review.get("claude_take"),
    }
    if isinstance(runtime_ledger, dict):
        for key in ("title_candidates", "candidate_count", "judge_seed_group", "judge_disagreement_type"):
            if key in runtime_ledger:
                ledger[key] = runtime_ledger[key]
    return ledger


def classify_shadow(row: dict[str, Any], review: dict[str, Any]) -> str:
    identity = identity_from_result_row(row)
    runtime_label = str(identity.get("candidate_ledger_status") or "")
    if runtime_label in PIPELINE_SHADOW_LABELS:
        return runtime_label
    disagreement_type = str(review.get("disagreement_type") or "")
    group = seed_group(disagreement_type)
    title = official_title(identity)
    candidates = collect_candidate_titles(identity)
    o_lints = official_title_lint_reasons(identity)
    i_lints = identity_consistency_lint_reasons(identity, disagreement_type)

    if o_lints:
        return "official_title_lint"
    if group == "precision" and (title or i_lints):
        return "identity_consistency_lint"
    if group == "hygiene":
        return "output_consistency_lint"
    if group == "recall":
        if title:
            return "safe_resolved"
        if candidates:
            return "promotion_blocked"
        state = str(identity.get("title_resolution_state") or "").strip().lower()
        work_resolution = str(identity.get("work_resolution") or "").strip().lower()
        if identity.get("is_novel_related") is True or state in {"unresolved_matchable", "adjacent"} or work_resolution in {"unresolved", "hold"}:
            return "hold_unresolved"
        return "candidate_generation_miss"
    return "review_only"


def clean_canary_row(row: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    out = {
        k: v
        for k, v in row.items()
        if k not in {"analysis_result", "run_meta", "pipe", "reason", "_source_path"}
    }
    if "content" not in out and row.get("body"):
        out["content"] = [part.strip() for part in str(row.get("body") or "").split(" / ") if part.strip()]
    if row.get("image_ocr"):
        ocr_lines = [str(item).strip() for item in row.get("image_ocr") or [] if str(item).strip()]
        if ocr_lines:
            out.setdefault("content", [])
            if isinstance(out["content"], str):
                out["content"] = [out["content"]]
            out["content"].extend(f"[이미지 OCR] {line}" for line in ocr_lines)
    if row.get("img_count") and not row.get("content_blocks") and not row.get("image_urls"):
        out.setdefault("content", [])
        if isinstance(out["content"], str):
            out["content"] = [out["content"]]
        out["content"].append(f"[이미지 첨부: 원본 image URL 없음, img_count={row.get('img_count')}]")
    out.setdefault("gallery_id", "genrenovel")
    out.setdefault(
        "url",
        f"https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no={row.get('post_id')}",
    )
    out["_judge_seed"] = {
        "seed_group": seed["seed_group"],
        "disagreement_type": seed["disagreement_type"],
        "severity": seed["severity"],
        "shadow_label_before": seed["shadow_label"],
        "source_path": row.get("_source_path"),
        "source_has_image_url": bool(row.get("image_urls") or row.get("content_blocks")),
        "source_img_count": row.get("img_count") or row.get("image_count") or 0,
    }
    return out


def build_registry(
    *,
    reviews_path: Path,
    source_patterns: list[str],
    out_dir: Path,
    prefix: str,
    canary_per_group: int,
) -> dict[str, Any]:
    reviews = [row for row in load_jsonl(reviews_path) if str(row.get("disagreement_type") or "") in SEED_TYPES]
    source_by_id, source_paths = load_source_rows(source_patterns)

    seeds: list[dict[str, Any]] = []
    missing_source_post_ids: list[str] = []
    for review in reviews:
        pid = post_id_key(review.get("post_id"))
        source = source_by_id.get(pid)
        if source is None:
            missing_source_post_ids.append(pid)
            continue
        disagreement_type = str(review.get("disagreement_type") or "")
        group = seed_group(disagreement_type)
        ledger = build_candidate_ledger(source, review)
        seed = {
            "post_id": int(pid) if pid.isdigit() else pid,
            "seed_group": group,
            "disagreement_type": disagreement_type,
            "severity": str(review.get("severity") or ""),
            "agree": review.get("agree"),
            "likely_correct": review.get("likely_correct"),
            "shadow_label": classify_shadow(source, review),
            "candidate_ledger": ledger,
            "source": {
                "source_path": source.get("_source_path"),
                "title": source.get("title"),
                "url": source.get("url"),
                "image_count": source.get("image_count") or source.get("img_count"),
                "has_image_url": bool(source.get("image_urls") or source.get("content_blocks")),
                "comment_count": len(source.get("comments") or []),
            },
            "judge": {
                "claude_take": review.get("claude_take"),
                "note": review.get("note"),
                "batch": review.get("_batch"),
            },
        }
        seeds.append(seed)

    seeds.sort(
        key=lambda row: (
            row["seed_group"],
            row["disagreement_type"],
            SEVERITY_RANK.get(str(row["severity"]).lower(), 9),
            sort_post_id(row["post_id"]),
        )
    )

    selected_ids = select_canary_ids(seeds, canary_per_group=canary_per_group)
    seed_by_id = {post_id_key(seed["post_id"]): seed for seed in seeds}
    canary_rows = [
        clean_canary_row(source_by_id[pid], seed_by_id[pid])
        for pid in selected_ids
        if pid in source_by_id and pid in seed_by_id
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    registry_path = out_dir / f"{prefix}_seed_registry.json"
    shadow_path = out_dir / f"{prefix}_candidate_ledger_shadow.jsonl"
    canary_path = out_dir / f"{prefix}_expert_main_canary_input.jsonl"
    manifest_path = out_dir / f"{prefix}_manifest.json"
    summary_path = out_dir / f"{prefix}_summary_ko.md"
    expected_result_path = out_dir / f"{prefix}_expert_main_canary_result.json"
    expected_manifest_path = expected_result_path.with_name(expected_result_path.stem + "_manifest.json")
    expected_compare_path = out_dir / f"{prefix}_expert_main_canary_compare.json"
    expected_compare_md = out_dir / f"{prefix}_expert_main_canary_compare_ko.md"

    write_json(registry_path, {"generated_at": now(), "seeds": seeds})
    write_jsonl(shadow_path, seeds)
    write_jsonl(canary_path, canary_rows)

    counts = {
        "by_group": dict(Counter(seed["seed_group"] for seed in seeds)),
        "by_type": dict(Counter(seed["disagreement_type"] for seed in seeds)),
        "by_shadow_label": dict(Counter(seed["shadow_label"] for seed in seeds)),
        "by_severity": dict(Counter(str(seed["severity"] or "") for seed in seeds)),
    }
    image_seed_without_url_count = sum(
        1
        for row in canary_rows
        if nested_dict(row.get("_judge_seed")).get("source_img_count")
        and not nested_dict(row.get("_judge_seed")).get("source_has_image_url")
    )
    recommended_parallel = min(PARALLEL_MAX, max(1, len(canary_rows)))
    recommended_command = (
        f"python expert_main.py --input {canary_path.as_posix()} "
        f"--output {expected_result_path.as_posix()} --server-type vllm "
        f"--parallel {recommended_parallel} --reuse-shards-only --no-dashboard "
        "--slang-db on --vlm on --ocr on --require-vlm-ocr-for-images"
    )
    compare_command = (
        f"python tools/build_judge_seed_registry.py compare "
        f"--registry {registry_path.as_posix()} "
        f"--canary-result {expected_result_path.as_posix()} "
        f"--manifest {manifest_path.as_posix()} "
        f"--output-json {expected_compare_path.as_posix()} "
        f"--output-md {expected_compare_md.as_posix()}"
    )
    manifest = {
        "generated_at": now(),
        "reviews_path": reviews_path.as_posix(),
        "source_patterns": source_patterns,
        "source_paths": source_paths,
        "source_post_count": len(source_by_id),
        "seed_count": len(seeds),
        "missing_source_count": len(missing_source_post_ids),
        "missing_source_post_ids": missing_source_post_ids,
        "canary_post_count": len(canary_rows),
        "canary_image_seed_without_url_count": image_seed_without_url_count,
        "canary_post_ids": [row.get("post_id") for row in canary_rows],
        "counts": counts,
        "outputs": {
            "seed_registry": registry_path.as_posix(),
            "candidate_ledger_shadow": shadow_path.as_posix(),
            "expert_main_canary_input": canary_path.as_posix(),
            "manifest": manifest_path.as_posix(),
            "summary": summary_path.as_posix(),
            "expected_canary_result": expected_result_path.as_posix(),
            "expected_canary_manifest": expected_manifest_path.as_posix(),
            "expected_compare_json": expected_compare_path.as_posix(),
            "expected_compare_md": expected_compare_md.as_posix(),
        },
        "recommended_commands": {
            "expert_main_canary": recommended_command,
            "compare_after_canary": compare_command,
        },
        "gate": {
            "run_integrity": "PENDING",
            "semantic_quality": "REVIEW-LOCKED",
            "reason": "seed registry and shadow artifacts are diagnostic; expert_main canary and compare are required before any improvement claim.",
            "source_limit": "batch_*.json rows may contain img_count/image_ocr without raw image URLs; those canary rows are judge-context canaries, not full VLM/browser evidence.",
        },
    }
    write_json(manifest_path, manifest)
    write_summary(summary_path, manifest)
    return manifest


def select_canary_ids(seeds: list[dict[str, Any]], *, canary_per_group: int) -> list[str]:
    selected: list[str] = []
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seed in seeds:
        by_group[seed["seed_group"]].append(seed)
    for group in ("recall", "precision", "hygiene"):
        group_rows = sorted(
            by_group.get(group, []),
            key=lambda row: (
                SEVERITY_RANK.get(str(row["severity"]).lower(), 9),
                row["disagreement_type"],
                sort_post_id(row["post_id"]),
            ),
        )
        group_selected: list[str] = []
        for dtype in sorted({row["disagreement_type"] for row in group_rows}):
            first = next((row for row in group_rows if row["disagreement_type"] == dtype), None)
            if first is not None:
                group_selected.append(post_id_key(first["post_id"]))
        for row in group_rows:
            pid = post_id_key(row["post_id"])
            if len(group_selected) >= canary_per_group:
                break
            if pid not in group_selected:
                group_selected.append(pid)
        for pid in group_selected[:canary_per_group]:
            if pid not in selected:
                selected.append(pid)
    return selected


def normalize_result_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("results") or payload.get("rows") or payload.get("items") or []
        return [row for row in rows if isinstance(row, dict)]
    return []


def load_expected_compare_ids(manifest_path: Path | None, result_by_id: dict[str, dict[str, Any]]) -> tuple[str, set[str]]:
    if manifest_path is not None and manifest_path.is_file():
        manifest = load_json(manifest_path)
        canary_post_ids = manifest.get("canary_post_ids") if isinstance(manifest, dict) else None
        if isinstance(canary_post_ids, list) and canary_post_ids:
            return "manifest_canary_post_ids", {post_id_key(pid) for pid in canary_post_ids}
    return "result_post_ids_only", set(result_by_id)


def compare_canary(
    *,
    registry_path: Path,
    canary_result_path: Path,
    output_json: Path,
    output_md: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    registry = load_json(registry_path)
    seeds = registry.get("seeds") if isinstance(registry, dict) else []
    seed_by_id = {post_id_key(seed.get("post_id")): seed for seed in seeds if isinstance(seed, dict)}
    result_payload = load_json(canary_result_path)
    result_rows = normalize_result_rows(result_payload)
    result_by_id = {post_id_key(row.get("post_id")): row for row in result_rows}
    scope_source, expected_ids = load_expected_compare_ids(manifest_path, result_by_id)
    scoped_seed_by_id = {pid: seed for pid, seed in seed_by_id.items() if pid in expected_ids}

    rows: list[dict[str, Any]] = []
    for pid, seed in sorted(scoped_seed_by_id.items(), key=lambda kv: sort_post_id(kv[0])):
        if pid not in result_by_id:
            continue
        result_row = result_by_id[pid]
        after_review = {
            "disagreement_type": seed["disagreement_type"],
            "likely_correct": seed.get("likely_correct"),
            "note": seed.get("judge", {}).get("note"),
        }
        after_ledger = build_candidate_ledger(result_row, after_review)
        before_ledger = seed.get("candidate_ledger") or {}
        before_title = before_ledger.get("pipeline_official_title")
        after_title = after_ledger.get("pipeline_official_title")
        rows.append(
            {
                "post_id": int(pid) if pid.isdigit() else pid,
                "seed_group": seed["seed_group"],
                "disagreement_type": seed["disagreement_type"],
                "severity": seed.get("severity"),
                "shadow_label_before": seed.get("shadow_label"),
                "shadow_label_after": classify_shadow(result_row, after_review),
                "official_title_before": before_title,
                "official_title_after": after_title,
                "official_title_changed": before_title != after_title,
                "candidate_count_before": before_ledger.get("candidate_count"),
                "candidate_count_after": after_ledger.get("candidate_count"),
                "official_title_lint_after": after_ledger.get("official_title_lint_reasons") or [],
                "identity_consistency_lint_after": after_ledger.get("identity_consistency_lint_reasons") or [],
            }
        )

    missing_result_post_ids = sorted(
        [pid for pid in expected_ids if pid in seed_by_id and pid not in result_by_id],
        key=sort_post_id,
    )
    missing_registry_seed_post_ids = sorted(
        [pid for pid in expected_ids if pid not in seed_by_id],
        key=sort_post_id,
    )
    extra_result_post_ids = sorted(
        [pid for pid in result_by_id if pid not in expected_ids],
        key=sort_post_id,
    )
    summary = {
        "generated_at": now(),
        "registry_path": registry_path.as_posix(),
        "canary_result_path": canary_result_path.as_posix(),
        "manifest_path": manifest_path.as_posix() if manifest_path else None,
        "compare_scope_source": scope_source,
        "registry_seed_count": len(seed_by_id),
        "compare_scope_seed_count": len(scoped_seed_by_id),
        "expected_post_count": len(expected_ids),
        "result_post_count": len(result_by_id),
        "compared_post_count": len(rows),
        "missing_result_post_ids": missing_result_post_ids,
        "missing_registry_seed_post_ids": missing_registry_seed_post_ids,
        "extra_result_post_ids": extra_result_post_ids,
        "counts": {
            "by_after_shadow_label": dict(Counter(row["shadow_label_after"] for row in rows)),
            "official_title_changed": sum(1 for row in rows if row["official_title_changed"]),
            "official_title_lint_after": sum(1 for row in rows if row["official_title_lint_after"]),
            "identity_consistency_lint_after": sum(1 for row in rows if row["identity_consistency_lint_after"]),
        },
        "rows": rows,
        "gate": {
            "run_integrity": "REVIEW" if missing_result_post_ids or missing_registry_seed_post_ids else "GO",
            "semantic_quality": "REVIEW-LOCKED",
            "reason": "comparison is targeted seed evidence only; random/high-risk expansion is still required.",
        },
    }
    write_json(output_json, summary)
    write_compare_md(output_md, summary)
    return summary


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_summary(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# GPT judge seed registry / candidate ledger shadow",
        "",
        f"- 생성 시각: `{manifest['generated_at']}`",
        f"- seed 수: `{manifest['seed_count']}`",
        f"- canary post 수: `{manifest['canary_post_count']}`",
        f"- missing source 수: `{manifest['missing_source_count']}`",
        "",
        "## Seed group counts",
        "",
    ]
    for key, value in sorted(manifest["counts"]["by_group"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Shadow label counts", ""])
    for key, value in sorted(manifest["counts"]["by_shadow_label"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## 산출물", ""])
    for key, value in sorted(manifest["outputs"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## 권장 expert_main canary", "", "```powershell", manifest["recommended_commands"]["expert_main_canary"], "```"])
    lines.extend(["", "## canary 후 비교", "", "```powershell", manifest["recommended_commands"]["compare_after_canary"], "```"])
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "- 이 산출물은 head-slice judge seed를 실행 가능한 P0 진단 단위로 포장한 것이다.",
            "- `official_title`을 늘리는 개선이 아니라 candidate/shadow/lint 기반 관측을 먼저 만든다.",
            "- expert_main canary와 compare가 끝나기 전까지 run integrity는 `PENDING`, semantic quality는 `REVIEW-LOCKED`다.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_compare_md(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# GPT judge seed expert_main canary compare",
        "",
        f"- 생성 시각: `{summary['generated_at']}`",
        f"- registry seed 수: `{summary['registry_seed_count']}`",
        f"- compare scope: `{summary['compare_scope_source']}`",
        f"- expected post 수: `{summary['expected_post_count']}`",
        f"- scope seed 수: `{summary['compare_scope_seed_count']}`",
        f"- result post 수: `{summary['result_post_count']}`",
        f"- 비교 post 수: `{summary['compared_post_count']}`",
        f"- result missing 수: `{len(summary['missing_result_post_ids'])}`",
        f"- registry seed missing 수: `{len(summary['missing_registry_seed_post_ids'])}`",
        f"- extra result 수: `{len(summary['extra_result_post_ids'])}`",
        f"- official_title changed: `{summary['counts']['official_title_changed']}`",
        f"- official_title lint after: `{summary['counts']['official_title_lint_after']}`",
        f"- identity consistency lint after: `{summary['counts']['identity_consistency_lint_after']}`",
        "",
        "## After shadow label counts",
        "",
    ]
    for key, value in sorted(summary["counts"]["by_after_shadow_label"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Gate", ""])
    lines.append(f"- run integrity: `{summary['gate']['run_integrity']}`")
    lines.append(f"- semantic quality: `{summary['gate']['semantic_quality']}`")
    lines.append(f"- reason: {summary['gate']['reason']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build GPT judge seed registry and candidate-ledger shadow artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--reviews", type=Path, required=True)
    build.add_argument("--source", action="append", required=True, help="JSON/JSONL source path or glob. Repeatable.")
    build.add_argument("--out-dir", type=Path, required=True)
    build.add_argument("--prefix", default="judge3905_p0")
    build.add_argument("--canary-per-group", type=int, default=8)

    compare = sub.add_parser("compare")
    compare.add_argument("--registry", type=Path, required=True)
    compare.add_argument("--canary-result", type=Path, required=True)
    compare.add_argument("--manifest", type=Path, default=None)
    compare.add_argument("--output-json", type=Path, required=True)
    compare.add_argument("--output-md", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "build":
        manifest = build_registry(
            reviews_path=args.reviews,
            source_patterns=args.source,
            out_dir=args.out_dir,
            prefix=args.prefix,
            canary_per_group=args.canary_per_group,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    elif args.command == "compare":
        summary = compare_canary(
            registry_path=args.registry,
            canary_result_path=args.canary_result,
            output_json=args.output_json,
            output_md=args.output_md,
            manifest_path=args.manifest,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
