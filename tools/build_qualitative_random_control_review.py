from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


RUN_ID = "20260505_214349_324347"
ROUND_NAME = "round1_random_control"
SEED = f"{RUN_ID}:random_control:v3_1000_stratified"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_round2_module(root: Path) -> Any:
    path = root / "tools" / "build_qualitative_round2_review.py"
    spec = importlib.util.spec_from_file_location("build_qualitative_round2_review", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def quick_official_title(row: dict[str, Any]) -> str | None:
    idn = row.get("analysis_result", {}).get("identity", {}) or {}
    novel = idn.get("novel_identity") or {}
    if novel.get("official_title"):
        return str(novel.get("official_title"))
    primary = idn.get("primary_work") or {}
    if primary.get("official_title"):
        return str(primary.get("official_title"))
    return None


def quick_state(row: dict[str, Any]) -> dict[str, Any]:
    idn = row.get("analysis_result", {}).get("identity", {}) or {}
    title = quick_official_title(row)
    relevance = idn.get("is_relevant")
    confidence = str((idn.get("novel_identity") or {}).get("confidence") or "").lower()
    reason = str(idn.get("reason") or "")
    degraded = any(token in reason for token in ["degraded", "저하", "엔진경고", "무결과"])
    slang = isinstance(idn.get("slang_insight"), dict) and bool(idn.get("slang_insight"))
    if relevance is False:
        base = "non_relevant"
    elif relevance is True and title:
        base = "resolved_high" if confidence == "high" else "resolved_non_high"
    elif relevance is True:
        base = "relevant_unresolved"
    else:
        base = "unknown_relevance"
    return {
        "base_state": base,
        "search_degraded": degraded,
        "slang_db_related": slang,
        "worker": (row.get("run_meta") or {}).get("worker_id", "missing"),
    }


def select_random_rows(
    result_path: Path,
    review_dir: Path,
    round2: Any,
    size: int,
    source_integrity_summary: dict[str, Any] | None = None,
) -> tuple[list[tuple[int, dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    existing_labels = load_jsonl(review_dir / "review_labels.jsonl")
    excluded_ids = {
        str(row.get("post_id"))
        for row in existing_labels
        if row.get("post_id") is not None and row.get("bucket") != "random_control"
    }
    rng = random.Random(SEED)
    candidates: list[dict[str, Any]] = []
    total_rows = 0
    for row_index, row in round2.iter_json_array(result_path):
        total_rows = row_index
        post_id = row.get("post_id")
        if post_id is None or str(post_id) in excluded_ids:
            continue
        state = quick_state(row)
        candidates.append(
            {
                "row_index": row_index,
                "post_id": post_id,
                "base_state": state["base_state"],
                "search_degraded": state["search_degraded"],
                "slang_db_related": state["slang_db_related"],
                "worker": state["worker"],
            }
        )

    for item in candidates:
        item["row_decile"] = min(9, int(((int(item["row_index"]) - 1) / max(1, total_rows)) * 10))
        item["stratum"] = f"d{item['row_decile']}|{item['base_state']}"

    by_stratum: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        by_stratum.setdefault(str(item["stratum"]), []).append(item)

    selected_meta: list[dict[str, Any]] = []
    quota = max(1, math.ceil(size / max(1, len(by_stratum))))
    for stratum, rows in sorted(by_stratum.items()):
        shuffled = rows[:]
        rng.shuffle(shuffled)
        take = min(quota, len(shuffled), max(0, size - len(selected_meta)))
        selected_meta.extend(shuffled[:take])
    if len(selected_meta) < size:
        selected_ids = {str(item["post_id"]) for item in selected_meta}
        remaining = [item for item in candidates if str(item["post_id"]) not in selected_ids]
        rng.shuffle(remaining)
        selected_meta.extend(remaining[: size - len(selected_meta)])
    rng.shuffle(selected_meta)

    selected_ids_ordered = [str(item["post_id"]) for item in selected_meta[:size]]
    selected_id_set = set(selected_ids_ordered)
    selected_by_id: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] = {}
    for row_index, row in round2.iter_json_array(result_path):
        post_id = str(row.get("post_id"))
        if post_id in selected_id_set:
            facts = round2.extract_facts(row_index, row)
            selected_by_id[post_id] = (row_index, row, facts)
            if len(selected_by_id) == len(selected_id_set):
                break
    reservoir = [selected_by_id[post_id] for post_id in selected_ids_ordered if post_id in selected_by_id]
    selected_meta_by_id = {str(item["post_id"]): item for item in selected_meta[:size]}
    selected_size = len(reservoir)
    requested_size = size
    selection_shortfall = max(0, requested_size - selected_size)

    def dist(key: str) -> dict[str, int]:
        return dict(Counter(str(item.get(key)) for item in selected_meta[:size]))

    manifest = {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "round": ROUND_NAME,
        "bucket": "random_control",
        "sample_seed": SEED,
        "source_result_path": result_path.as_posix(),
        "source_review_policy": round2.source_review_policy(result_path, source_integrity_summary),
        "sample_size": selected_size,
        "requested_sample_size": requested_size,
        "selected_sample_size": selected_size,
        "sample_target_satisfied": selection_shortfall == 0,
        "sample_shortfall": selection_shortfall,
        "sample_coverage_ratio": round(selected_size / max(1, requested_size), 6),
        "total_rows_scanned": total_rows,
        "eligible_rows_after_dedup": len(candidates),
        "excluded_existing_non_random_post_ids": len(excluded_ids),
        "dedupe_key": "post_id",
        "selection_method": "이미 추출된 비무작위 post_id를 제외한 뒤 row-index decile과 decision state 기준으로 고정 seed 층화 표본 추출",
        "selected_row_index_min": min((item[0] for item in reservoir), default=None),
        "selected_row_index_max": max((item[0] for item in reservoir), default=None),
        "stratification": {
            "primary": ["row_index_decile", "base_state"],
            "distribution_row_decile": dist("row_decile"),
            "distribution_base_state": dist("base_state"),
            "distribution_worker": dist("worker"),
            "distribution_search_degraded": dist("search_degraded"),
            "distribution_slang_db_related": dist("slang_db_related"),
            "processing_time_window_note": "server-poc 결과 row에는 row별 처리 timestamp가 없어 row_index_decile을 안정적인 순서 proxy로 사용한다.",
            "shard_note": "server-poc 결과 row는 worker_id를 노출하지만 모든 row에 shard id가 있는 것은 아니다.",
        },
        "selected_meta_by_post_id": selected_meta_by_id,
    }
    return reservoir, manifest


def build_random_packet(packet_id: str, row_index: int, row: dict[str, Any], facts: dict[str, Any], result_path: Path, round2: Any) -> dict[str, Any]:
    idn = facts["identity"]
    slang = facts["slang"] or {}
    run_meta = row.get("run_meta") or {}
    text_for_image = " ".join([facts["title"], facts["body"], facts["reason"]])
    return {
        "run_id": run_meta.get("run_id") or RUN_ID,
        "packet_id": packet_id,
        "round": ROUND_NAME,
        "bucket": "random_control",
        "sample_seed": SEED,
        "random_row_index": row_index,
        "source_path": result_path.as_posix(),
        "result_source_path": result_path.as_posix(),
        "checkpoint_row_index": None,
        "line_number": row_index,
        "post_id": row.get("post_id"),
        "url": row.get("url"),
        "title": facts["title"],
        "content_blocks": facts["content_blocks"],
        "image_urls": facts["image_urls"],
        "image_count": facts["image_count"],
        "body_excerpt": round2.excerpt(row.get("content"), 720),
        "comment_excerpt": round2.comments_excerpt(row, 480),
        "comment_metadata": facts["comment_metadata"],
        "comment_context_lines": facts["comment_context_lines"],
        "comment_context_source": facts["comment_context_source"],
        "comment_dialogue_context_lines": facts["comment_dialogue_context_lines"],
        "comment_dialogue_context_source": facts["comment_dialogue_context_source"],
        "resolved_title": facts["resolved_title"],
        "relevance": idn.get("is_relevant"),
        "final_decision_fields": round2.final_decision_fields(idn),
        "reason": facts["reason"],
        "risk_tags": sorted(set(["random_control"] + list(facts["bucket_reasons"].keys()) + facts["search_flags"])),
        "bucket_match_reasons": ["deterministic_random_control"],
        "search_health_flags": facts["search_flags"],
        "evidence_urls": round2.evidence_urls(idn),
        "evidence_snippets": round2.evidence_snippets(facts["reason"]),
        "evidence_catalog": round2.evidence_catalog(row, idn),
        "evidence_counts": {
            "image_count": facts["image_count"],
            "image_url_count": len(facts["image_urls"]),
            "image_evidence_catalog_count": facts["image_evidence_catalog_count"],
            "image_evidence_catalog_missing": facts["image_evidence_catalog_missing"],
        },
        "prompt_public_fields": {
            "gallery_id": row.get("gallery_id"),
            "post_author": row.get("post_author") or row.get("author"),
            "content_blocks": facts["content_blocks"],
            "image_urls": facts["image_urls"],
            "image_count": facts["image_count"],
            "comment_metadata": facts["comment_metadata"],
            "comment_context_lines": facts["comment_context_lines"],
            "comment_context_source": facts["comment_context_source"],
            "comment_dialogue_context_lines": facts["comment_dialogue_context_lines"],
            "comment_dialogue_context_source": facts["comment_dialogue_context_source"],
        },
        "result_public_fields": {
            **round2.final_decision_fields(idn),
            "gallery_id": row.get("gallery_id"),
            "post_author": row.get("post_author") or row.get("author"),
            "comment_metadata_count": facts["comment_metadata_count"],
            "comment_context_line_count": facts["comment_context_line_count"],
            "comment_context_source": facts["comment_context_source"],
            "comment_dialogue_context_line_count": facts["comment_dialogue_context_line_count"],
            "comment_dialogue_context_source": facts["comment_dialogue_context_source"],
            "image_count": facts["image_count"],
            "image_url_count": len(facts["image_urls"]),
            "image_evidence_catalog_count": facts["image_evidence_catalog_count"],
            "image_evidence_catalog_missing": facts["image_evidence_catalog_missing"],
        },
        "vlm_ocr_fields": {
            "context_sources": facts["context_sources"],
            "mentioned_image": bool(round2.has_any(text_for_image, ["이미지", "[이미지 첨부]", "image"])),
            "mentioned_ocr": bool("OCR" in facts["reason"]),
            "public_state_weak": facts["vlm_ocr_public_state_weak"],
            "image_urls": facts["image_urls"],
            "image_count": facts["image_count"],
            "image_evidence_catalog": facts["image_evidence_catalog"],
            "image_evidence_catalog_count": facts["image_evidence_catalog_count"],
            "image_evidence_catalog_missing": facts["image_evidence_catalog_missing"],
        },
        "slang_db_fields": {
            "detected_term": slang.get("detected_term"),
            "decoded_term": slang.get("decoded_term"),
            "decode_verified": slang.get("decode_verified"),
            "canonical_work_alias": slang.get("canonical_work_alias"),
            "alias_scope": slang.get("alias_scope"),
            "store_in_slang_db": slang.get("store_in_slang_db"),
            "store_reason": slang.get("store_reason"),
        },
        "worker": run_meta.get("worker_id"),
        "shard": run_meta.get("shard_id") or run_meta.get("shard"),
        "timestamp": row.get("created_at") or run_meta.get("timestamp"),
        "limitations": [
            "무작위 기준선 리뷰는 공개 title/body/comment/reason/final 필드만 사용한다.",
            "server-poc 패키지에는 checkpoint lineage가 없다.",
        ],
    }


def write_random_summary(path: Path, labels: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    label_counts = Counter(str(row.get("label")) for row in labels)
    action_counts = Counter(str(row.get("action")) for row in labels)
    lines = [
        f"# 무작위 기준선 리뷰 - {RUN_ID}",
        "",
        f"생성 시각: {manifest['generated_at']}",
        "",
        "## 범위",
        "",
        "이 문서는 자연어 의미 품질 리뷰의 확장 고정 seed 무작위 기준선이다.",
        "",
        "## 표본 정보",
        "",
        f"- 요청 표본 수: `{manifest.get('requested_sample_size', manifest['sample_size'])}`",
        f"- 실제 선택 표본 수: `{manifest.get('selected_sample_size', manifest['sample_size'])}`",
        f"- 표본 부족분: `{manifest.get('sample_shortfall', 0)}`",
        f"- Seed: `{manifest['sample_seed']}`",
        f"- row index 범위: `{manifest['selected_row_index_min']}` ~ `{manifest['selected_row_index_max']}`",
        "",
        "## 라벨 집계",
        "",
    ]
    for label in ["ACCEPT", "HOLD", "REPROCESS", "REJECT", "INFO_MISSING"]:
        lines.append(f"- `{label}`: `{label_counts.get(label, 0)}`")
    lines.extend(["", "## 액션 집계", ""])
    for action, count in sorted(action_counts.items()):
        lines.append(f"- `{action}`: `{count}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    global RUN_ID, SEED
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default="server-poc/expert_result_20260505_214349_324347.json")
    parser.add_argument("--review-dir", default=None)
    parser.add_argument("--size", type=int, default=300)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--source-integrity-summary", default=None)
    parser.add_argument("--preflight", default=None, help="Preflight JSON that must match --result for approval-oriented runs.")
    parser.add_argument(
        "--fail-on-locked-source",
        action="store_true",
        help="Exit with code 2 before writing outputs when --preflight is missing, mismatched, or REVIEW-LOCKED.",
    )
    args = parser.parse_args()

    root = repo_root()
    result_path = root / args.result
    round2 = load_round2_module(root)
    preflight_path = (root / args.preflight).resolve() if args.preflight else None
    preflight = round2.load_preflight_summary(preflight_path)
    preflight_gate = round2.preflight_source_gate_status(
        preflight,
        result_path=result_path.resolve(),
        fail_on_locked_source=args.fail_on_locked_source,
    )
    if preflight_gate.get("blocked"):
        print(
            json.dumps(
                {
                    "blocked": True,
                    "tool": "build_qualitative_random_control_review",
                    "preflight_path": preflight_path.as_posix() if preflight_path else None,
                    **preflight_gate,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return int(preflight_gate["exit_code"])

    source_integrity_summary = round2.load_source_integrity_summary(
        root / args.source_integrity_summary if args.source_integrity_summary else None
    )
    RUN_ID = args.run_id or round2.infer_run_id(result_path)
    SEED = f"{RUN_ID}:random_control:v3_1000_stratified"
    review_dir = root / (args.review_dir or f"qualitative_review/{RUN_ID}")
    review_dir.mkdir(parents=True, exist_ok=True)

    selected, manifest = select_random_rows(
        result_path,
        review_dir,
        round2,
        max(1, args.size),
        source_integrity_summary,
    )
    packets = []
    labels = []
    for index, (row_index, row, facts) in enumerate(selected, start=1):
        packet = build_random_packet(f"RC3-{index:04d}", row_index, row, facts, result_path, round2)
        packets.append(packet)
        label = round2.review_label(packet, facts)
        label["random_row_index"] = row_index
        labels.append(label)

    manifest["label_counts"] = dict(Counter(str(row.get("label")) for row in labels))
    manifest["action_counts"] = dict(Counter(str(row.get("action")) for row in labels))
    (review_dir / "random_control_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (review_dir / "random_control_v3_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_jsonl(review_dir / "random_control_packets.jsonl", packets)
    write_jsonl(review_dir / "random_control_labels.jsonl", labels)
    write_jsonl(review_dir / "random_control_v3_packets.jsonl", packets)
    write_jsonl(review_dir / "random_control_v3_labels.jsonl", labels)
    write_random_summary(review_dir / "random_control_summary.md", labels, manifest)

    existing_packets = [row for row in load_jsonl(review_dir / "review_packets.jsonl") if row.get("bucket") != "random_control"]
    existing_labels = [row for row in load_jsonl(review_dir / "review_labels.jsonl") if row.get("bucket") != "random_control"]
    all_packets = existing_packets + packets
    all_labels = existing_labels + labels
    write_jsonl(review_dir / "review_packets.jsonl", all_packets)
    write_jsonl(review_dir / "review_labels.jsonl", all_labels)

    round2_manifest_path = review_dir / "round2_manifest.json"
    if round2_manifest_path.exists():
        round2_manifest = json.loads(round2_manifest_path.read_text(encoding="utf-8-sig"))
        if isinstance(round2_manifest, dict):
            round2.RUN_ID = str(round2_manifest.get("run_id") or RUN_ID)
            round2.SEED = str(round2_manifest.get("sample_seed") or getattr(round2, "SEED", ""))
            round2.write_canonical_summaries(review_dir, all_packets, all_labels, round2_manifest)

    print(
        json.dumps(
            {
                "random_control_rows": len(labels),
                "label_counts": manifest["label_counts"],
                "action_counts": manifest["action_counts"],
                "canonical_rows_after_random_update": len(existing_labels) + len(labels),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
