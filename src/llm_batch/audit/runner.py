from __future__ import annotations

import csv
import json
import re
import textwrap
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .prompts import BLIND_REREAD_PROMPT, TARGETED_EXPLANATION_PROMPT


WORK_DISCUSSION_TYPES = {
    "review",
    "spoiler",
    "anticipation",
    "meme",
    "character_talk",
    "general",
}
ALL_DISCUSSION_TYPES = WORK_DISCUSSION_TYPES | {
    "author_talk",
    "recommendation",
    "meta",
    "trope_discussion",
    "community_banter",
    "genre_opinion",
    "image_post",
    "off_topic",
    "noise",
    "undecodable_reference",
}
RISK_TAXONOMY = [
    "coverage_gap",
    "body_understanding_failure",
    "general_vs_specific_confusion",
    "multi_work_collapse",
    "author_new_work_title_hallucination",
    "character_to_work_overreach",
    "review_misread",
    "search_thrash_or_underreach",
    "confidence_evidence_mismatch",
    "reason_trace_inconsistency",
]
RISK_WEIGHTS = {
    "coverage_gap": 40,
    "body_understanding_failure": 25,
    "general_vs_specific_confusion": 18,
    "multi_work_collapse": 18,
    "author_new_work_title_hallucination": 20,
    "character_to_work_overreach": 16,
    "review_misread": 16,
    "search_thrash_or_underreach": 12,
    "confidence_evidence_mismatch": 10,
    "reason_trace_inconsistency": 9,
}
OFFICIAL_SITE_TOKENS = (
    "novelpia.com",
    "munpia.com",
    "series.naver.com",
    "page.kakao.com",
    "joara.com",
    "ridi",
    "ridibooks",
)
COMMUNITY_SITE_TOKENS = (
    "gall.dcinside.com",
    "dcinside.com",
    "fmkorea.com",
    "ruliweb.com",
    "arca.live",
    "reddit.com",
)
REASON_HEADERS = [
    "[판정 요약]",
    "[원문 해석]",
    "[전문가별 판단]",
    "[최종 종합]",
    "[근거 스코어]",
]
CONTROL_EXCEPTION_SNIPPETS = (
    "예외 가드",
    "동일문자열 예외 가드",
    "title_deliberately_null",
    "author_new_work 연상 예외",
    "거부권 예외",
    "거부권 무효화",
    "FN 복구 예외",
    "worklike_unresolved 예외",
    "alias_bridge_pending 예외",
)


@dataclass
class AuditConfig:
    result_path: Path
    log_prefix: Path
    output_dir: Path
    input_path: Optional[Path] = None
    queue_path: Optional[Path] = None
    enable_blind_reread: bool = True
    enable_targeted_explanations: bool = True
    blind_workers: int = 1
    explanation_workers: int = 1
    resume: bool = True
    max_dossiers_per_label: int = 3
    max_explanations: int = 0


def _slugify(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", str(value or "")).strip("_").lower()


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _normalize_confidence(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"max"}:
        return "Max"
    if raw in {"high"}:
        return "High"
    if raw in {"medium", "mid"}:
        return "Medium"
    if raw in {"low"}:
        return "Low"
    return "None"


def _normalize_discussion_type(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "None"
    lowered = raw.lower()
    return lowered if lowered in ALL_DISCUSSION_TYPES else raw


def _normalize_title(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "").lower())


def _compact_join(values: Iterable[Any], *, sep: str = "|") -> str:
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return sep.join(out)


def _json_dump_line(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _load_json_or_jsonl(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _parse_block_string(block: str) -> Dict[str, Any]:
    text = str(block or "").strip()
    if not text:
        return {"type": "text", "text": ""}
    image_match = re.search(r"type='?image'?|type=image", text)
    url_match = re.search(r"url='([^']+)'|url=([^ ]+)", text)
    text_match = re.search(r"text='([^']*)'|text=([^ ]+)", text)
    if image_match:
        return {
            "type": "image",
            "url": (url_match.group(1) or url_match.group(2) or "").strip() if url_match else "",
            "text": "",
        }
    if url_match and "http" in text and not text_match:
        return {
            "type": "image",
            "url": (url_match.group(1) or url_match.group(2) or "").strip(),
            "text": "",
        }
    if text_match:
        value = (text_match.group(1) or text_match.group(2) or "").strip()
        if value and value.lower() != "none":
            return {"type": "text", "text": value}
    return {"type": "text", "text": text}


def _normalize_content_blocks(blocks: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for block in blocks or []:
        if isinstance(block, dict):
            text = str(block.get("text") or block.get("content") or "").strip()
            image_url = str(
                block.get("url")
                or block.get("image_url")
                or block.get("src")
                or ""
            ).strip()
            block_type = str(block.get("type") or ("image" if image_url and not text else "text")).strip() or "text"
            normalized.append({"type": block_type, "text": text, "url": image_url})
        else:
            normalized.append(_parse_block_string(str(block)))
    return normalized


def _extract_comment_texts(comments: Any) -> List[str]:
    values: List[str] = []
    for item in comments or []:
        if isinstance(item, dict):
            text = item.get("content") or item.get("text") or ""
        else:
            text = str(item)
        text = str(text or "").strip()
        if text:
            values.append(text)
    return values


def _render_body_lines(blocks: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    for block in blocks:
        block_type = str(block.get("type") or "text").strip().lower()
        if block_type == "image":
            lines.append("[image]")
            continue
        text = str(block.get("text") or "").strip()
        if text:
            lines.append(text)
    return lines


def _build_blind_payload(source: Dict[str, Any]) -> Dict[str, Any]:
    content_blocks = _normalize_content_blocks(source.get("content") or source.get("content_blocks") or [])
    comments = _extract_comment_texts(source.get("comments") or source.get("comments_raw") or [])
    return {
        "post_id": _safe_int(source.get("post_id")),
        "title": str(source.get("title") or "").strip(),
        "body_blocks": [
            {
                "type": block.get("type") or "text",
                "text": str(block.get("text") or "").strip(),
            }
            for block in content_blocks[:50]
        ],
        "image_count": sum(1 for block in content_blocks if str(block.get("type") or "").lower() == "image"),
        "comments": comments[:20],
    }


def _load_input_post_index(path: Optional[Path]) -> Dict[int, Dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    posts: Dict[int, Dict[str, Any]] = {}
    comments: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for item in _load_json_or_jsonl(path):
        post_id = _safe_int(item.get("post_id"))
        if not post_id:
            continue
        if "comment_id" in item:
            comments[post_id].append(item)
            continue
        posts[post_id] = {
            "post_id": post_id,
            "title": item.get("title") or "",
            "author": item.get("author") or "",
            "created_at": item.get("created_at") or "",
            "url": item.get("url") or "",
            "content_blocks": _normalize_content_blocks(item.get("content_blocks") or item.get("content") or []),
            "comments": [],
        }
    for post_id, raw_comments in comments.items():
        if post_id in posts:
            posts[post_id]["comments"] = _extract_comment_texts(raw_comments)
    return posts


def _load_active_learning_map(path: Optional[Path]) -> Dict[int, Dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    merged: Dict[int, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            post_id = _safe_int(row.get("post_id"))
            if not post_id:
                continue
            entry = merged.setdefault(
                post_id,
                {
                    "flags": set(),
                    "unanimous": "",
                    "hypothesis_margin": "",
                    "executed_queries": "",
                    "title_acceptance": "",
                    "title_candidate_class": "",
                    "reason_head": "",
                },
            )
            for flag in str(row.get("flags") or "").split("|"):
                flag = flag.strip()
                if flag:
                    entry["flags"].add(flag)
            for key in ("unanimous", "hypothesis_margin", "executed_queries", "title_acceptance", "title_candidate_class", "reason_head"):
                value = str(row.get(key) or "").strip()
                if value:
                    entry[key] = value
    for entry in merged.values():
        entry["flags"] = sorted(entry["flags"])
    return merged


def _parse_reason(reason: str) -> Dict[str, Any]:
    text = str(reason or "").strip()
    sections: Dict[str, str] = {}
    positions: List[Tuple[int, str]] = []
    for header in REASON_HEADERS:
        idx = text.find(header)
        if idx >= 0:
            positions.append((idx, header))
    positions.sort()
    for i, (start, header) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        sections[header] = text[start:end].strip()

    search_summary_match = re.search(
        r"검색 요약:\s*실행\s*(\d+)건\s*\(유효\s*(\d+)건\s*/\s*무결과\s*(\d+)건\)",
        text,
    )
    effective_match = re.search(
        r"보정집계:\s*실행\s*(\d+)건\s*\(유효\s*(\d+)건\s*/\s*무결과\s*(\d+)건\)",
        text,
    )
    degraded_match = re.search(
        r"-\s*degraded_queries:\s*(\d+).*?degraded_nonzero=(\d+),\s*degraded_zero=(\d+),\s*retried=(\d+)",
        text,
    )
    executed_match = re.search(r"-\s*executed_queries:\s*(\d+)", text)
    planned_match = re.search(r"-\s*planned_unique_queries:\s*(\d+)", text)
    evidence_diversity_match = re.search(r"-\s*evidence_diversity:\s*(\d+)", text)
    code_guards = re.findall(r"\[코드가드 ([^\]]+)\]", text)
    decision_line_match = re.search(r"-\s*판정:\s*([^\n]+)", text)
    discussion_line_match = re.search(r"-\s*discussion_type:\s*([^\n]+)", text)
    official_line_match = re.search(r"-\s*공식 제목:\s*([^\n]+)", text)

    return {
        "sections": sections,
        "executed_queries": _safe_int(executed_match.group(1)) if executed_match else (
            _safe_int(search_summary_match.group(1)) if search_summary_match else 0
        ),
        "effective_queries": _safe_int(effective_match.group(1)) if effective_match else 0,
        "effective_nonzero_queries": _safe_int(effective_match.group(2)) if effective_match else 0,
        "zero_result_queries": _safe_int(search_summary_match.group(3)) if search_summary_match else 0,
        "planned_queries": _safe_int(planned_match.group(1)) if planned_match else 0,
        "degraded_queries": _safe_int(degraded_match.group(1)) if degraded_match else 0,
        "degraded_nonzero_queries": _safe_int(degraded_match.group(2)) if degraded_match else 0,
        "degraded_zero_queries": _safe_int(degraded_match.group(3)) if degraded_match else 0,
        "retried_queries": _safe_int(degraded_match.group(4)) if degraded_match else 0,
        "evidence_diversity": _safe_int(evidence_diversity_match.group(1)) if evidence_diversity_match else 0,
        "code_guards": code_guards,
        "decision_line": decision_line_match.group(1).strip() if decision_line_match else "",
        "discussion_line": discussion_line_match.group(1).strip() if discussion_line_match else "",
        "official_line": official_line_match.group(1).strip() if official_line_match else "",
    }


def flatten_result_item(
    item: Dict[str, Any],
    queue_map: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    post_id = _safe_int(item.get("post_id"))
    analysis_result = item.get("analysis_result") or {}
    identity = analysis_result.get("identity") or {}
    analysis = analysis_result.get("analysis") or {}
    novel_identity = identity.get("novel_identity") or {}
    run_meta = item.get("run_meta") or {}
    title_candidates = identity.get("title_candidates") or []
    mentioned_works = identity.get("mentioned_works") or []
    future_watch_target = identity.get("future_watch_target") or {}
    entity_mentions = identity.get("entity_mentions") or []
    reason = str(identity.get("reason") or "").strip()
    parsed_reason = _parse_reason(reason)
    queue_entry = (queue_map or {}).get(post_id) or {}

    candidate_titles = [str((cand or {}).get("official_title") or "").strip() for cand in title_candidates]
    candidate_source_tiers = [str((cand or {}).get("source_tier") or "").strip() for cand in title_candidates]
    mentioned_titles = [str((cand or {}).get("official_title") or "").strip() for cand in mentioned_works]
    entity_types = [str((ent or {}).get("entity_type") or "").strip() for ent in entity_mentions]

    return {
        "post_id": post_id,
        "title": str(item.get("title") or "").strip(),
        "author": str(item.get("author") or "").strip(),
        "created_at": str(item.get("created_at") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "content": item.get("content") or [],
        "comments": item.get("comments") or [],
        "raw_result": item,
        "analysis_result": analysis_result,
        "pipeline_is_relevant": _coerce_bool(identity.get("is_relevant")),
        "pipeline_discussion_type": _normalize_discussion_type(identity.get("discussion_type")),
        "pipeline_relevance_scope": str(identity.get("relevance_scope") or "").strip(),
        "pipeline_official_title": str(novel_identity.get("official_title") or "").strip(),
        "pipeline_heretic_url": str(novel_identity.get("heretic_url") or "").strip(),
        "pipeline_confidence": _normalize_confidence(novel_identity.get("confidence")),
        "identity_state": str(identity.get("identity_state") or "None"),
        "run_id": str(run_meta.get("run_id") or "").strip(),
        "run_model": str(run_meta.get("model") or "").strip(),
        "run_llm_mode": str(run_meta.get("llm_mode") or "").strip(),
        "run_prompt_version": str(run_meta.get("prompt_version") or "").strip(),
        "run_config_hash": str(run_meta.get("config_hash") or "").strip(),
        "candidate_count": len(title_candidates),
        "mentioned_work_count": len(mentioned_works),
        "future_watch_target_present": bool(future_watch_target),
        "future_watch_target": str(future_watch_target.get("official_title") or "").strip(),
        "candidate_titles": candidate_titles,
        "candidate_source_tiers": candidate_source_tiers,
        "mentioned_titles": mentioned_titles,
        "entity_types": entity_types,
        "micro_tags": analysis.get("micro_tags") or [],
        "is_nsfw": _coerce_bool(analysis.get("is_nsfw")),
        "reason": reason,
        "reason_sections": parsed_reason["sections"],
        "reason_executed_queries": parsed_reason["executed_queries"],
        "reason_effective_queries": parsed_reason["effective_queries"],
        "reason_zero_result_queries": parsed_reason["zero_result_queries"],
        "reason_degraded_queries": parsed_reason["degraded_queries"],
        "reason_evidence_diversity": parsed_reason["evidence_diversity"],
        "reason_code_guards": parsed_reason["code_guards"],
        "reason_decision_line": parsed_reason["decision_line"],
        "reason_discussion_line": parsed_reason["discussion_line"],
        "reason_official_line": parsed_reason["official_line"],
        "active_learning_flags": list(queue_entry.get("flags") or []),
        "active_learning_unanimous": str(queue_entry.get("unanimous") or ""),
        "active_learning_hypothesis_margin": str(queue_entry.get("hypothesis_margin") or ""),
        "active_learning_title_acceptance": str(queue_entry.get("title_acceptance") or ""),
        "active_learning_title_candidate_class": str(queue_entry.get("title_candidate_class") or ""),
        "active_learning_reason_head": str(queue_entry.get("reason_head") or ""),
        "expert_conflict": "expert_conflict" in set(queue_entry.get("flags") or []),
    }


def _new_log_summary(post_id: int) -> Dict[str, Any]:
    return {
        "post_id": post_id,
        "workers": set(),
        "log_started": False,
        "log_done": False,
        "start_count": 0,
        "done_count": 0,
        "elapsed_s": 0.0,
        "iterations": 0,
        "stage_calls": Counter(),
        "stage_durations": defaultdict(list),
        "queries": [],
        "from_queries": [],
        "skipped_queries": [],
        "search_events": [],
        "verification_requested": 0,
        "verification_filtered": 0,
        "verification_pruned": 0,
        "verification_skipped": 0,
        "verification_executed": 0,
        "guard_flags": Counter(),
        "override_flags": Counter(),
        "veto_count": 0,
        "veto_override_count": 0,
        "bm25_trims": [],
        "errors": [],
        "control_lines": [],
        "excerpts": [],
    }


def _append_excerpt(summary: Dict[str, Any], line: str, limit: int = 40) -> None:
    if len(summary["excerpts"]) < limit:
        summary["excerpts"].append(line.strip())


def _parse_main_log_metadata(path: Path) -> Dict[str, Any]:
    metadata = {
        "input_path": "",
        "result_path": "",
        "total_input_posts": 0,
        "worker_count": 0,
        "llm_mode": "",
    }
    if not path.exists():
        return metadata
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f, 1):
            if idx > 200:
                break
            if "결과 저장:" in line:
                metadata["result_path"] = line.split("결과 저장:", 1)[1].strip()
            elif "입력:" in line and "포스트" in line:
                metadata["input_path"] = line.split("입력:", 1)[1].split("(", 1)[0].strip()
                m = re.search(r"\((\d+)개 포스트\)", line)
                if m:
                    metadata["total_input_posts"] = _safe_int(m.group(1))
            elif "병렬 모드 활성화:" in line:
                m = re.search(r"활성화:\s*(\d+)\s*워커", line)
                if m:
                    metadata["worker_count"] = _safe_int(m.group(1))
            elif "LLM_MODE:" in line:
                metadata["llm_mode"] = line.split("LLM_MODE:", 1)[1].strip()
    return metadata


def parse_worker_logs(log_prefix: Path) -> Dict[str, Any]:
    main_log = log_prefix.with_suffix(".log")
    worker_logs = sorted(log_prefix.parent.glob(f"{log_prefix.name}_W*.log"))
    results: Dict[int, Dict[str, Any]] = {}

    start_re = re.compile(r"Agentic Pipeline start: Post (\d+)")
    done_re = re.compile(r"✅ Post (\d+) 완료 \(([\d.]+)s,\s*(\d+) iterations\)")
    stage_start_patterns = {
        "gatekeeper": re.compile(r"Gatekeeper 분석 시작: post_id=(\d+)"),
        "discourse": re.compile(r"DiscourseAnalyzer 분석 시작: post_id=(\d+)"),
        "verifier": re.compile(r"Verifier 검증 시작: post_id=(\d+)"),
        "synthesizer": re.compile(r"Synthesizer 증거 기반 재해석 시작: post_id=(\d+)"),
        "arbiter": re.compile(r"Arbiter 최종 판정 시작: post_id=(\d+)"),
    }
    stage_complete_patterns = {
        "gatekeeper": re.compile(r"Gatekeeper 완료 \(([\d.]+)s\):"),
        "discourse": re.compile(r"DiscourseAnalyzer 완료 \(([\d.]+)s\):"),
        "decoder": re.compile(r"Decoder 완료 \(([\d.]+)s\):"),
        "verifier": re.compile(r"Verifier 완료 \(([\d.]+)s\):"),
        "synthesizer": re.compile(r"Synthesizer 완료 \(([\d.]+)s\):"),
        "arbiter": re.compile(r"Arbiter 완료 \(([\d.]+)s\):"),
    }
    decoder_start_re = re.compile(r"Decoder 분석 시작:")
    query_re = re.compile(r"🔍 검 (.+?) \(목적: ([^)]+)\)")
    from_query_re = re.compile(r"from_query:\s*(.+)")
    skipped_query_re = re.compile(r"스킵: purpose=([^ ]+).*?query='([^']+)'")
    search_event_re = re.compile(r"search results \[([^\]]+)\]:\s*(.+)")
    verification_filtered_re = re.compile(r"verification_search 정합성 필터: kept=(\d+) pruned=(\d+)")
    verification_skip_re = re.compile(r"verification_search 실행 생략")
    bm25_re = re.compile(r"BM25 트리밍: ([\d,]+)자→([\d,]+)자 \(query='([^']*)'\)")

    def ensure(post_id: int) -> Dict[str, Any]:
        if post_id not in results:
            results[post_id] = _new_log_summary(post_id)
        return results[post_id]

    for log_path in worker_logs:
        worker_id = log_path.stem.split("_")[-1]
        current_pid: Optional[int] = None
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                raw = line.rstrip("\n")
                start_match = start_re.search(raw)
                if start_match:
                    current_pid = _safe_int(start_match.group(1))
                    summary = ensure(current_pid)
                    summary["workers"].add(worker_id)
                    summary["log_started"] = True
                    summary["start_count"] += 1
                    _append_excerpt(summary, raw)
                    continue

                done_match = done_re.search(raw)
                if done_match:
                    current_pid = _safe_int(done_match.group(1))
                    summary = ensure(current_pid)
                    summary["workers"].add(worker_id)
                    summary["log_done"] = True
                    summary["done_count"] += 1
                    summary["elapsed_s"] = _safe_float(done_match.group(2))
                    summary["iterations"] = _safe_int(done_match.group(3))
                    _append_excerpt(summary, raw)
                    continue

                matched_pid: Optional[int] = None
                for stage_name, pattern in stage_start_patterns.items():
                    stage_match = pattern.search(raw)
                    if not stage_match:
                        continue
                    matched_pid = _safe_int(stage_match.group(1))
                    current_pid = matched_pid
                    summary = ensure(matched_pid)
                    summary["workers"].add(worker_id)
                    summary["stage_calls"][stage_name] += 1
                    _append_excerpt(summary, raw)
                    break
                if matched_pid is not None:
                    continue

                if decoder_start_re.search(raw) and current_pid:
                    summary = ensure(current_pid)
                    summary["workers"].add(worker_id)
                    summary["stage_calls"]["decoder"] += 1
                    _append_excerpt(summary, raw)
                    continue

                if current_pid is None:
                    continue

                summary = ensure(current_pid)
                summary["workers"].add(worker_id)

                stage_complete_handled = False
                for stage_name, pattern in stage_complete_patterns.items():
                    complete_match = pattern.search(raw)
                    if complete_match:
                        summary["stage_durations"][stage_name].append(_safe_float(complete_match.group(1)))
                        _append_excerpt(summary, raw)
                        stage_complete_handled = True
                        break
                if stage_complete_handled:
                    continue

                query_match = query_re.search(raw)
                if query_match:
                    summary["queries"].append(
                        {
                            "query": query_match.group(1).strip(),
                            "purpose": query_match.group(2).strip(),
                        }
                    )
                    _append_excerpt(summary, raw)
                    continue

                from_query_match = from_query_re.search(raw)
                if from_query_match:
                    summary["from_queries"].append(from_query_match.group(1).strip())
                    _append_excerpt(summary, raw)
                    continue

                skipped_match = skipped_query_re.search(raw)
                if skipped_match:
                    summary["skipped_queries"].append(
                        {
                            "purpose": skipped_match.group(1).strip(),
                            "query": skipped_match.group(2).strip(),
                        }
                    )
                    _append_excerpt(summary, raw)
                    continue

                search_match = search_event_re.search(raw)
                if search_match:
                    detail = search_match.group(2)
                    event = {
                        "status": search_match.group(1).strip(),
                        "detail": detail.strip(),
                        "new": _safe_int(re.search(r"new=(\d+)", detail).group(1)) if re.search(r"new=(\d+)", detail) else 0,
                        "accepted": _safe_int(re.search(r"accepted=(\d+)", detail).group(1)) if re.search(r"accepted=(\d+)", detail) else 0,
                        "bridge_raw": _safe_int(re.search(r"bridge_raw=(\d+)", detail).group(1)) if re.search(r"bridge_raw=(\d+)", detail) else 0,
                        "bridge_after_filter": _safe_int(re.search(r"bridge_after_filter=(\d+)", detail).group(1)) if re.search(r"bridge_after_filter=(\d+)", detail) else 0,
                        "duplicate": _safe_int(re.search(r"중복 (\d+)개", detail).group(1)) if re.search(r"중복 (\d+)개", detail) else 0,
                        "bridge_filtered": _safe_int(re.search(r"bridge필터 (\d+)개", detail).group(1)) if re.search(r"bridge필터 (\d+)개", detail) else 0,
                        "domain_blocked": _safe_int(re.search(r"도메인차단 (\d+)개", detail).group(1)) if re.search(r"도메인차단 (\d+)개", detail) else 0,
                        "preserved_irrelevant": _safe_int(re.search(r"비관련보존 (\d+)개", detail).group(1)) if re.search(r"비관련보존 (\d+)개", detail) else 0,
                        "retries": _safe_int(re.search(r"retries (\d+)", detail).group(1)) if re.search(r"retries (\d+)", detail) else 0,
                        "attempts": _safe_int(re.search(r"attempts (\d+)", detail).group(1)) if re.search(r"attempts (\d+)", detail) else 0,
                    }
                    summary["search_events"].append(event)
                    _append_excerpt(summary, raw)
                    continue

                filtered_match = verification_filtered_re.search(raw)
                if filtered_match:
                    summary["verification_requested"] += 1
                    summary["verification_filtered"] += 1
                    summary["verification_pruned"] += _safe_int(filtered_match.group(2))
                    _append_excerpt(summary, raw)
                    continue

                if "verification_search" in raw and '"verification_search": [' in raw:
                    summary["verification_requested"] += 1
                    _append_excerpt(summary, raw)
                    continue

                if verification_skip_re.search(raw):
                    summary["verification_skipped"] += 1
                    _append_excerpt(summary, raw)
                    continue

                if "verification_search 쿼리가 이미 검색됨" in raw or "verification_search 스킵 해제" in raw:
                    summary["verification_executed"] += 1
                    _append_excerpt(summary, raw)
                    continue

                bm25_match = bm25_re.search(raw)
                if bm25_match:
                    summary["bm25_trims"].append(
                        {
                            "before_chars": _safe_int(bm25_match.group(1).replace(",", "")),
                            "after_chars": _safe_int(bm25_match.group(2).replace(",", "")),
                            "query": bm25_match.group(3).strip(),
                        }
                    )
                    _append_excerpt(summary, raw)
                    continue

                lowered = raw.lower()
                if "거부권" in raw or "veto" in lowered:
                    summary["veto_count"] += 1
                    if "예외" in raw or "무효화" in raw:
                        summary["veto_override_count"] += 1
                        summary["override_flags"]["verifier_veto_override"] += 1
                    _append_excerpt(summary, raw)

                guard_map = {
                    "title_deliberately_null": ("title_deliberately_null", "guard"),
                    "author_new_work": ("author_new_work", "guard"),
                    "multi_work": ("multi_work", "guard"),
                    "worklike_unresolved": ("worklike_unresolved", "guard"),
                    "alias_bridge_pending": ("alias_bridge_pending", "guard"),
                    "동일문자열 예외 가드": ("same_string_exception", "guard"),
                    "FN 복구 예외": ("fn_recovery", "override"),
                    "heretic_url 폴백 적용": ("heretic_url_fallback", "override"),
                    "증거 기반 구출": ("evidence_based_rescue", "override"),
                }
                for needle, (flag, bucket) in guard_map.items():
                    if needle in raw:
                        if bucket == "guard":
                            summary["guard_flags"][flag] += 1
                        else:
                            summary["override_flags"][flag] += 1
                        _append_excerpt(summary, raw)

                if ("Traceback" in raw or "처리 오류" in raw or "ERROR" in raw or "Exception" in raw or "예외" in raw):
                    if any(snippet in raw for snippet in CONTROL_EXCEPTION_SNIPPETS):
                        summary["control_lines"].append(raw.strip())
                    elif "예외" in raw and "Exception" not in raw and "ERROR" not in raw and "Traceback" not in raw and "처리 오류" not in raw:
                        summary["control_lines"].append(raw.strip())
                    else:
                        summary["errors"].append(raw.strip())
                        _append_excerpt(summary, raw)

    return {
        "main_log": main_log,
        "worker_logs": worker_logs,
        "main_meta": _parse_main_log_metadata(main_log),
        "posts": results,
    }


def _normalize_blind_result(post_id: int, raw: Dict[str, Any]) -> Dict[str, Any]:
    secondary = raw.get("secondary_works") or []
    if not isinstance(secondary, list):
        secondary = []
    normalized = {
        "post_id": post_id,
        "is_relevant": _coerce_bool(raw.get("is_relevant")),
        "discussion_type": _normalize_discussion_type(raw.get("discussion_type")),
        "primary_work": str(raw.get("primary_work") or "").strip(),
        "secondary_works": [str(x).strip() for x in secondary if str(x).strip()],
        "is_review": _coerce_bool(raw.get("is_review")),
        "multi_work": _coerce_bool(raw.get("multi_work")),
        "author_new_work_context": _coerce_bool(raw.get("author_new_work_context")),
        "association_post": _coerce_bool(raw.get("association_post")),
        "general_vs_specific": str(raw.get("general_vs_specific") or "unclear").strip().lower() or "unclear",
        "character_anchor_only": _coerce_bool(raw.get("character_anchor_only")),
        "confidence": _normalize_confidence(raw.get("confidence")),
        "body_understanding_summary": str(raw.get("body_understanding_summary") or "").strip(),
        "why": str(raw.get("why") or "").strip(),
    }
    if normalized["discussion_type"] not in ALL_DISCUSSION_TYPES and normalized["discussion_type"] != "None":
        normalized["discussion_type"] = "None"
    if normalized["general_vs_specific"] not in {"specific", "general", "mixed", "unclear"}:
        normalized["general_vs_specific"] = "unclear"
    return normalized


def _normalize_targeted_explanation(post_id: int, raw: Dict[str, Any]) -> Dict[str, Any]:
    failure_modes = raw.get("pipeline_failure_modes") or []
    if not isinstance(failure_modes, list):
        failure_modes = []
    cleaned_modes = [str(x).strip() for x in failure_modes if str(x).strip() in set(RISK_TAXONOMY)]
    mismatch_class = str(raw.get("mismatch_class") or "unclear").strip().lower() or "unclear"
    if mismatch_class not in {
        "match",
        "relevance_disagreement",
        "discussion_type_disagreement",
        "title_disagreement",
        "multi_work_disagreement",
        "coverage_gap",
        "unclear",
    }:
        mismatch_class = "unclear"
    trace_consistency = str(raw.get("reason_trace_consistency") or "unclear").strip().lower() or "unclear"
    if trace_consistency not in {"consistent", "inconsistent", "unclear"}:
        trace_consistency = "unclear"
    return {
        "post_id": post_id,
        "mismatch_class": mismatch_class,
        "pipeline_failure_modes": cleaned_modes,
        "body_understanding_notes": str(raw.get("body_understanding_notes") or "").strip(),
        "review_notes": str(raw.get("review_notes") or "").strip(),
        "search_assessment": str(raw.get("search_assessment") or "").strip(),
        "reason_trace_consistency": trace_consistency,
        "summary": str(raw.get("summary") or "").strip(),
    }


def _load_jsonl_map(path: Path) -> Dict[int, Dict[str, Any]]:
    if not path.exists():
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for item in _iter_jsonl(path):
        post_id = _safe_int(item.get("post_id"))
        if post_id:
            out[post_id] = item
    return out


def _csv_safe(value: Any) -> Any:
    if isinstance(value, list):
        return _compact_join(value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


class AuditRunner:
    def __init__(
        self,
        config: AuditConfig,
        *,
        llm_client_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.config = config
        self.llm_client_factory = llm_client_factory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def _make_llm_client(self) -> Any:
        if self.llm_client_factory is not None:
            return self.llm_client_factory()
        from ..llm.client import LLMClient

        return LLMClient(stream=False)

    def _blind_reread_one(self, row: Dict[str, Any]) -> Dict[str, Any]:
        client = self._make_llm_client()
        payload = _build_blind_payload(row["raw_result"])
        raw = client.complete_json(
            BLIND_REREAD_PROMPT,
            payload,
            tag=f"blind_reread:{row['post_id']}",
            max_tokens=700,
        )
        return _normalize_blind_result(row["post_id"], raw)

    def _targeted_explain_one(
        self,
        row: Dict[str, Any],
        blind: Dict[str, Any],
        search_audit: Dict[str, Any],
        log_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        client = self._make_llm_client()
        payload = {
            "post_id": row["post_id"],
            "original": _build_blind_payload(row["raw_result"]),
            "pipeline": {
                "is_relevant": row.get("pipeline_is_relevant"),
                "discussion_type": row.get("pipeline_discussion_type"),
                "official_title": row.get("pipeline_official_title"),
                "confidence": row.get("pipeline_confidence"),
                "identity_state": row.get("identity_state"),
                "candidate_titles": row.get("candidate_titles"),
                "mentioned_titles": row.get("mentioned_titles"),
                "active_learning_flags": row.get("active_learning_flags"),
            },
            "blind": blind,
            "search_audit": {
                "executed_queries": search_audit.get("executed_queries"),
                "official_query_ratio": search_audit.get("official_query_ratio"),
                "community_query_ratio": search_audit.get("community_query_ratio"),
                "duplicate_queries": search_audit.get("duplicate_queries"),
                "zero_result_queries": search_audit.get("zero_result_queries"),
                "degraded_queries": search_audit.get("degraded_queries"),
                "verification_requested": search_audit.get("verification_requested"),
                "verification_filtered": search_audit.get("verification_filtered"),
                "search_labels": search_audit.get("search_labels"),
                "query_chain_preview": search_audit.get("query_chain_preview"),
            },
            "log_trace": log_summary.get("excerpts") or [],
        }
        raw = client.complete_json(
            TARGETED_EXPLANATION_PROMPT,
            payload,
            tag=f"targeted_explanation:{row['post_id']}",
            max_tokens=800,
        )
        return _normalize_targeted_explanation(row["post_id"], raw)

    def _run_llm_pass(
        self,
        rows: List[Dict[str, Any]],
        output_path: Path,
        worker_count: int,
        fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        existing = _load_jsonl_map(output_path) if self.config.resume else {}
        pending = [row for row in rows if row["post_id"] not in existing]
        write_mode = "a" if (self.config.resume and output_path.exists()) else "w"
        if not pending:
            if not output_path.exists():
                output_path.write_text("", encoding="utf-8")
            return existing

        if worker_count <= 1:
            with output_path.open(write_mode, encoding="utf-8") as f:
                for row in pending:
                    item = fn(row)
                    existing[row["post_id"]] = item
                    f.write(_json_dump_line(item) + "\n")
            return existing

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(fn, row): row["post_id"] for row in pending}
            with output_path.open(write_mode, encoding="utf-8") as f:
                for future in as_completed(futures):
                    post_id = futures[future]
                    item = future.result()
                    existing[post_id] = item
                    f.write(_json_dump_line(item) + "\n")
        return existing

    def _compute_search_audit(
        self,
        row: Dict[str, Any],
        log_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        queries = log_summary.get("queries") or []
        skipped_queries = log_summary.get("skipped_queries") or []
        search_events = log_summary.get("search_events") or []
        executed_queries = len(queries) or row.get("reason_executed_queries") or 0
        unique_queries = len({str(q.get("query") or "").strip() for q in queries if str(q.get("query") or "").strip()})
        duplicate_queries = sum(_safe_int(event.get("duplicate")) for event in search_events)
        if duplicate_queries == 0 and executed_queries and unique_queries:
            duplicate_queries = max(0, executed_queries - unique_queries)
        zero_result_queries = sum(
            1
            for event in search_events
            if _safe_int(event.get("bridge_after_filter")) == 0 or "bridge필터후0" in str(event.get("status") or "")
        ) or row.get("reason_zero_result_queries") or 0
        degraded_queries = sum(
            1
            for event in search_events
            if _safe_int(event.get("retries")) > 0 or "degraded" in str(event.get("status") or "").lower()
        ) or row.get("reason_degraded_queries") or 0
        official_query_count = sum(
            1
            for q in queries
            if any(token in str(q.get("query") or "").lower() for token in OFFICIAL_SITE_TOKENS)
            or str(q.get("purpose") or "").lower() in {"official_title_verify", "platform_title_search", "author_works_search"}
        )
        community_query_count = sum(
            1
            for q in queries
            if any(token in str(q.get("query") or "").lower() for token in COMMUNITY_SITE_TOKENS)
            or str(q.get("purpose") or "").lower() == "community_site_probe"
        )
        verification_requested = _safe_int(log_summary.get("verification_requested"))
        verification_filtered = _safe_int(log_summary.get("verification_filtered"))
        verification_skipped = _safe_int(log_summary.get("verification_skipped"))
        official_query_ratio = round(official_query_count / executed_queries, 4) if executed_queries else 0.0
        community_query_ratio = round(community_query_count / executed_queries, 4) if executed_queries else 0.0
        duplicate_ratio = round(duplicate_queries / executed_queries, 4) if executed_queries else 0.0
        zero_ratio = round(zero_result_queries / executed_queries, 4) if executed_queries else 0.0
        degraded_ratio = round(degraded_queries / executed_queries, 4) if executed_queries else 0.0
        candidate_tiers = set(x for x in row.get("candidate_source_tiers") or [] if x)

        search_labels: List[str] = []
        if (
            executed_queries > 0
            and official_query_count > 0
            and (row.get("pipeline_heretic_url") or row.get("reason_evidence_diversity", 0) >= 4)
            and duplicate_ratio <= 0.45
            and zero_ratio <= 0.35
        ):
            search_labels.append("smart_search")
        if row.get("identity_state") == "unresolved_title" and (executed_queries < 8 or official_query_count == 0):
            search_labels.append("under_searched")
        if executed_queries >= 10 and (duplicate_ratio > 0.45 or zero_ratio > 0.35 or degraded_ratio > 0.35):
            search_labels.append("search_thrash")
        if (
            row.get("pipeline_is_relevant")
            and row.get("pipeline_official_title")
            and not row.get("pipeline_heretic_url")
            and candidate_tiers
            and candidate_tiers <= {"community", "llm_only"}
        ):
            search_labels.append("community_overfit")
        if (
            row.get("pipeline_is_relevant")
            and row.get("pipeline_confidence") in {"High", "Medium"}
            and not row.get("pipeline_heretic_url")
            and _safe_int(row.get("reason_evidence_diversity")) <= 2
        ):
            search_labels.append("official_anchor_missing")
        if verification_requested > 0 and row.get("identity_state") == "resolved_title" and row.get("pipeline_official_title"):
            search_labels.append("verification_loop_good")
        if verification_requested > 0 and row.get("identity_state") != "resolved_title" and (verification_filtered > 0 or executed_queries >= 10):
            search_labels.append("verification_loop_stalled")

        purpose_counts = Counter(str(q.get("purpose") or "").strip() for q in queries if str(q.get("purpose") or "").strip())
        return {
            "post_id": row["post_id"],
            "executed_queries": executed_queries,
            "unique_executed_queries": unique_queries or executed_queries,
            "effective_queries": row.get("reason_effective_queries") or executed_queries,
            "official_query_count": official_query_count,
            "official_query_ratio": official_query_ratio,
            "community_query_count": community_query_count,
            "community_query_ratio": community_query_ratio,
            "duplicate_queries": duplicate_queries,
            "duplicate_ratio": duplicate_ratio,
            "zero_result_queries": zero_result_queries,
            "zero_result_ratio": zero_ratio,
            "degraded_queries": degraded_queries,
            "degraded_ratio": degraded_ratio,
            "verification_requested": verification_requested,
            "verification_filtered": verification_filtered,
            "verification_skipped": verification_skipped,
            "skipped_queries": len(skipped_queries),
            "search_labels": search_labels,
            "purpose_counts": dict(sorted(purpose_counts.items())),
            "query_chain_preview": _compact_join([q.get("query") for q in queries[:12]], sep=" || "),
        }

    def _compute_trace_reconciliation(
        self,
        result_map: Dict[int, Dict[str, Any]],
        input_posts: Dict[int, Dict[str, Any]],
        log_data: Dict[str, Any],
        queue_map: Dict[int, Dict[str, Any]],
    ) -> Dict[int, Dict[str, Any]]:
        started_ids = set(log_data["posts"].keys())
        done_ids = {pid for pid, summary in log_data["posts"].items() if summary.get("log_done")}
        result_ids = set(result_map.keys())
        input_ids = set(input_posts.keys())
        queue_ids = set(queue_map.keys())
        union_ids = result_ids | started_ids | queue_ids
        rows: Dict[int, Dict[str, Any]] = {}
        for post_id in sorted(union_ids):
            log_summary = log_data["posts"].get(post_id) or _new_log_summary(post_id)
            in_result = post_id in result_ids
            in_input = post_id in input_ids
            in_queue = post_id in queue_ids
            log_started = post_id in started_ids
            log_done = post_id in done_ids
            if in_result and log_started and log_done:
                status = "covered"
            elif in_result and log_started and not log_done:
                status = "started_not_done_result_present"
            elif in_result and not log_started:
                status = "result_only"
            elif (not in_result) and log_started and log_done:
                status = "log_done_missing_result"
            elif (not in_result) and log_started:
                status = "log_only_started_not_done"
            elif in_queue and not in_result:
                status = "queue_only"
            else:
                status = "input_only" if in_input else "untracked"
            rows[post_id] = {
                "post_id": post_id,
                "in_result": in_result,
                "in_input": in_input,
                "in_queue": in_queue,
                "log_started": log_started,
                "log_done": log_done,
                "worker_ids": sorted(log_summary.get("workers") or []),
                "start_count": _safe_int(log_summary.get("start_count")),
                "done_count": _safe_int(log_summary.get("done_count")),
                "elapsed_s": _safe_float(log_summary.get("elapsed_s")),
                "reconciliation_status": status,
            }
        return rows

    def _compute_risk_labels(
        self,
        row: Dict[str, Any],
        blind: Optional[Dict[str, Any]],
        search_audit: Dict[str, Any],
        trace: Dict[str, Any],
        explanation: Optional[Dict[str, Any]],
    ) -> Tuple[str, List[str], int]:
        mismatch_class = "match"
        if trace.get("reconciliation_status") != "covered":
            mismatch_class = "coverage_gap"
        elif blind:
            blind_title_norm = _normalize_title(blind.get("primary_work"))
            pipeline_title_norm = _normalize_title(row.get("pipeline_official_title"))
            if _coerce_bool(blind.get("is_relevant")) != _coerce_bool(row.get("pipeline_is_relevant")):
                mismatch_class = "relevance_disagreement"
            elif blind.get("discussion_type") != row.get("pipeline_discussion_type"):
                mismatch_class = "discussion_type_disagreement"
            elif blind_title_norm and pipeline_title_norm and blind_title_norm != pipeline_title_norm:
                mismatch_class = "title_disagreement"
            elif blind.get("multi_work") and not row.get("mentioned_work_count"):
                mismatch_class = "multi_work_disagreement"
        if explanation and explanation.get("mismatch_class") and explanation.get("mismatch_class") != "unclear":
            mismatch_class = explanation["mismatch_class"]

        risk_labels: List[str] = []
        if mismatch_class == "coverage_gap":
            risk_labels.append("coverage_gap")

        if blind:
            blind_high = blind.get("confidence") in {"High", "Medium"}
            if mismatch_class in {"relevance_disagreement", "title_disagreement"} and blind_high:
                risk_labels.append("body_understanding_failure")
            if (
                blind.get("general_vs_specific") in {"general", "mixed"}
                and row.get("pipeline_is_relevant")
                and row.get("pipeline_official_title")
            ) or (
                blind.get("general_vs_specific") == "specific"
                and not row.get("pipeline_is_relevant")
            ):
                risk_labels.append("general_vs_specific_confusion")
            if blind.get("multi_work") or _safe_int(row.get("mentioned_work_count")) >= 2 or _safe_int(row.get("candidate_count")) >= 3:
                if mismatch_class in {"multi_work_disagreement", "title_disagreement", "discussion_type_disagreement"}:
                    risk_labels.append("multi_work_collapse")
            if blind.get("author_new_work_context") and row.get("pipeline_official_title"):
                risk_labels.append("author_new_work_title_hallucination")
            if blind.get("character_anchor_only") and row.get("pipeline_official_title") and _safe_int(row.get("reason_evidence_diversity")) <= 2:
                risk_labels.append("character_to_work_overreach")
            if (
                (row.get("pipeline_discussion_type") == "review" and not blind.get("is_review"))
                or (blind.get("is_review") and row.get("pipeline_discussion_type") != "review")
            ):
                risk_labels.append("review_misread")

        if any(label in search_audit.get("search_labels", []) for label in {"under_searched", "search_thrash", "verification_loop_stalled"}):
            risk_labels.append("search_thrash_or_underreach")

        if (
            row.get("pipeline_confidence") in {"High", "Medium"}
            and (_safe_int(row.get("reason_evidence_diversity")) <= 1 or not row.get("pipeline_heretic_url"))
            and mismatch_class != "match"
        ):
            risk_labels.append("confidence_evidence_mismatch")

        reason_text = str(row.get("reason") or "")
        reason_inconsistent = False
        if row.get("pipeline_is_relevant") and "판정: 비관련" in reason_text:
            reason_inconsistent = True
        if (not row.get("pipeline_is_relevant")) and "판정: 관련" in reason_text:
            reason_inconsistent = True
        if row.get("identity_state") == "resolved_title" and "공식 제목: 미확정" in reason_text:
            reason_inconsistent = True
        if row.get("reason_code_guards") and "[코드가드" not in reason_text:
            reason_inconsistent = True
        if explanation and explanation.get("reason_trace_consistency") == "inconsistent":
            reason_inconsistent = True
        if reason_inconsistent:
            risk_labels.append("reason_trace_inconsistency")

        if explanation:
            for label in explanation.get("pipeline_failure_modes") or []:
                if label in RISK_TAXONOMY and label not in risk_labels:
                    risk_labels.append(label)

        risk_labels = [label for label in RISK_TAXONOMY if label in set(risk_labels)]
        risk_score = min(100, sum(RISK_WEIGHTS[label] for label in risk_labels))
        if row.get("expert_conflict"):
            risk_score = min(100, risk_score + 5)
        if _safe_int(row.get("candidate_count")) >= 4:
            risk_score = min(100, risk_score + 3)
        return mismatch_class, risk_labels, risk_score

    def _select_targeted_explanation_rows(
        self,
        merged_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for row in merged_rows:
            if not row.get("in_result"):
                continue
            if row.get("mismatch_class") != "match":
                rows.append(row)
                continue
            if row.get("active_learning_flags"):
                rows.append(row)
                continue
            if _safe_int(row.get("candidate_count")) >= 2:
                rows.append(row)
                continue
            if _safe_int(row.get("mentioned_work_count")) >= 2:
                rows.append(row)
                continue
            if row.get("identity_state") == "unresolved_title":
                rows.append(row)
                continue
            if row.get("pipeline_discussion_type") == "review":
                rows.append(row)
                continue
            if any(label in row.get("search_labels", []) for label in {"under_searched", "search_thrash", "verification_loop_stalled"}):
                rows.append(row)
                continue
            if row.get("reconciliation_status") != "covered":
                rows.append(row)
        if self.config.max_explanations > 0:
            return rows[: self.config.max_explanations]
        return rows

    def _write_csv(self, path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({name: _csv_safe(row.get(name)) for name in fieldnames})

    def _write_jsonl(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(_json_dump_line(row) + "\n")

    def _write_risk_dossiers(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        by_label: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            for label in row.get("risk_labels") or []:
                by_label[label].append(row)
        strong_cases = [
            row
            for row in rows
            if row.get("mismatch_class") == "match" and "smart_search" in (row.get("search_labels") or []) and row.get("risk_score", 0) <= 5
        ]
        lines = ["# Risk Dossiers", ""]
        for label in RISK_TAXONOMY:
            cases = sorted(by_label.get(label) or [], key=lambda x: (-_safe_int(x.get("risk_score")), -_safe_int(x.get("executed_queries"))))
            lines.append(f"## {label}")
            lines.append(f"- count: {len(cases)}")
            lines.append("")
            for row in cases[: self.config.max_dossiers_per_label]:
                lines.extend(self._render_dossier_case(row))
                lines.append("")
        lines.append("## Strong Cases")
        lines.append(f"- count: {len(strong_cases)}")
        lines.append("")
        for row in strong_cases[: self.config.max_dossiers_per_label]:
            lines.extend(self._render_dossier_case(row))
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _render_dossier_case(self, row: Dict[str, Any]) -> List[str]:
        excerpts = row.get("log_excerpts") or []
        lines = [
            f"### post_id={row['post_id']} | {row.get('title') or '(untitled)'}",
            f"- pipeline: relevant={row.get('pipeline_is_relevant')} dt={row.get('pipeline_discussion_type')} title={row.get('pipeline_official_title') or 'None'} conf={row.get('pipeline_confidence')}",
            f"- blind: relevant={row.get('blind_is_relevant')} dt={row.get('blind_discussion_type')} title={row.get('blind_primary_work') or 'None'} conf={row.get('blind_confidence')}",
            f"- search: executed={row.get('executed_queries')} labels={_compact_join(row.get('search_labels') or [])}",
            f"- risk: mismatch={row.get('mismatch_class')} score={row.get('risk_score')} labels={_compact_join(row.get('risk_labels') or [])}",
            f"- notes: {row.get('body_understanding_notes') or row.get('review_notes') or ''}",
        ]
        if row.get("active_learning_flags"):
            lines.append(f"- active_learning: {row.get('active_learning_flags')}")
        if excerpts:
            lines.append("- log_trace:")
            for excerpt in excerpts[:10]:
                lines.append(f"  - {excerpt}")
        return lines

    def _write_summary(
        self,
        path: Path,
        post_rows: List[Dict[str, Any]],
        trace_rows: List[Dict[str, Any]],
        search_rows: List[Dict[str, Any]],
        log_data: Dict[str, Any],
    ) -> None:
        total_results = sum(1 for row in post_rows if row.get("in_result"))
        blind_ready = sum(1 for row in post_rows if row.get("in_result") and row.get("blind_confidence"))
        mismatches = Counter(row.get("mismatch_class") or "None" for row in post_rows if row.get("in_result"))
        risk_counts = Counter(label for row in post_rows for label in (row.get("risk_labels") or []))
        search_counts = Counter(label for row in search_rows for label in (row.get("search_labels") or []))
        review_rows = [row for row in post_rows if row.get("pipeline_discussion_type") == "review" or row.get("blind_is_review")]
        multi_work_rows = [row for row in post_rows if _safe_int(row.get("mentioned_work_count")) >= 2 or _coerce_bool(row.get("blind_multi_work"))]
        coverage_counts = Counter(row.get("reconciliation_status") or "None" for row in trace_rows)
        lines = [
            "# Audit Summary",
            "",
            "## Run",
            f"- result_posts: {total_results}",
            f"- blind_reread_coverage: {blind_ready}/{total_results}",
            f"- log_started_posts: {len(log_data['posts'])}",
            f"- log_done_posts: {sum(1 for summary in log_data['posts'].values() if summary.get('log_done'))}",
            f"- active_learning_queue_posts: {sum(1 for row in post_rows if row.get('active_learning_flags'))}",
            f"- worker_count: {log_data['main_meta'].get('worker_count')}",
            f"- llm_mode: {log_data['main_meta'].get('llm_mode')}",
            "",
            "## Reconciliation",
        ]
        for status, count in sorted(coverage_counts.items()):
            lines.append(f"- {status}: {count}")
        lines.extend(["", "## Mismatch Distribution"])
        for key, count in sorted(mismatches.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {count}")
        lines.extend(["", "## Risk Taxonomy"])
        for label in RISK_TAXONOMY:
            lines.append(f"- {label}: {risk_counts.get(label, 0)}")
        lines.extend(["", "## Search Audit"])
        for label in ["smart_search", "under_searched", "search_thrash", "community_overfit", "official_anchor_missing", "verification_loop_good", "verification_loop_stalled"]:
            lines.append(f"- {label}: {search_counts.get(label, 0)}")
        lines.extend(
            [
                "",
                "## Review / Multi-Work",
                f"- review_related_rows: {len(review_rows)}",
                f"- multi_work_related_rows: {len(multi_work_rows)}",
            ]
        )
        top_risks = sorted(
            [row for row in post_rows if row.get("risk_score", 0) > 0],
            key=lambda row: (-_safe_int(row.get("risk_score")), row.get("post_id")),
        )[:10]
        lines.extend(["", "## Top Risk Cases"])
        for row in top_risks:
            lines.append(
                f"- post_id={row['post_id']} score={row.get('risk_score')} mismatch={row.get('mismatch_class')} labels={_compact_join(row.get('risk_labels') or [])} title={row.get('title') or ''}"
            )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def run(self) -> Dict[str, Path]:
        results = _load_json_file(self.config.result_path)
        result_items = results if isinstance(results, list) else (results.get("results") or [])
        queue_map = _load_active_learning_map(self.config.queue_path)
        input_posts = _load_input_post_index(self.config.input_path)
        log_data = parse_worker_logs(self.config.log_prefix)

        result_map = {
            _safe_int(item.get("post_id")): flatten_result_item(item, queue_map)
            for item in result_items
            if _safe_int(item.get("post_id"))
        }
        trace_map = self._compute_trace_reconciliation(result_map, input_posts, log_data, queue_map)

        blind_path = self.config.output_dir / "llm_blind_reread.jsonl"
        blind_map: Dict[int, Dict[str, Any]] = {}
        if self.config.enable_blind_reread:
            blind_map = self._run_llm_pass(
                list(result_map.values()),
                blind_path,
                max(1, self.config.blind_workers),
                self._blind_reread_one,
            )
        elif blind_path.exists():
            blind_map = _load_jsonl_map(blind_path)
        else:
            blind_path.write_text("", encoding="utf-8")

        search_map = {
            post_id: self._compute_search_audit(row, log_data["posts"].get(post_id) or _new_log_summary(post_id))
            for post_id, row in result_map.items()
        }

        merged_rows: List[Dict[str, Any]] = []
        for post_id, trace in sorted(trace_map.items()):
            result_row = result_map.get(post_id)
            input_row = input_posts.get(post_id) or {}
            blind = blind_map.get(post_id)
            search_audit = search_map.get(post_id) or {
                "post_id": post_id,
                "executed_queries": 0,
                "effective_queries": 0,
                "official_query_count": 0,
                "official_query_ratio": 0.0,
                "community_query_count": 0,
                "community_query_ratio": 0.0,
                "duplicate_queries": 0,
                "zero_result_queries": 0,
                "degraded_queries": 0,
                "verification_requested": 0,
                "verification_filtered": 0,
                "verification_skipped": 0,
                "search_labels": [],
                "query_chain_preview": "",
            }
            base = dict(trace)
            source = result_row or {
                "post_id": post_id,
                "title": str(input_row.get("title") or "").strip(),
                "author": str(input_row.get("author") or "").strip(),
                "created_at": str(input_row.get("created_at") or "").strip(),
                "url": str(input_row.get("url") or "").strip(),
                "content": input_row.get("content_blocks") or [],
                "comments": input_row.get("comments") or [],
                "raw_result": input_row,
                "pipeline_is_relevant": False,
                "pipeline_discussion_type": "None",
                "pipeline_official_title": "",
                "pipeline_heretic_url": "",
                "pipeline_confidence": "None",
                "identity_state": "None",
                "candidate_count": 0,
                "mentioned_work_count": 0,
                "future_watch_target_present": False,
                "future_watch_target": "",
                "candidate_titles": [],
                "candidate_source_tiers": [],
                "mentioned_titles": [],
                "entity_types": [],
                "micro_tags": [],
                "is_nsfw": False,
                "reason": "",
                "reason_sections": {},
                "reason_executed_queries": 0,
                "reason_effective_queries": 0,
                "reason_zero_result_queries": 0,
                "reason_degraded_queries": 0,
                "reason_evidence_diversity": 0,
                "reason_code_guards": [],
                "reason_decision_line": "",
                "reason_discussion_line": "",
                "reason_official_line": "",
                "active_learning_flags": list((queue_map.get(post_id) or {}).get("flags") or []),
                "active_learning_unanimous": str((queue_map.get(post_id) or {}).get("unanimous") or ""),
                "active_learning_hypothesis_margin": str((queue_map.get(post_id) or {}).get("hypothesis_margin") or ""),
                "active_learning_title_acceptance": str((queue_map.get(post_id) or {}).get("title_acceptance") or ""),
                "active_learning_title_candidate_class": str((queue_map.get(post_id) or {}).get("title_candidate_class") or ""),
                "active_learning_reason_head": str((queue_map.get(post_id) or {}).get("reason_head") or ""),
                "expert_conflict": "expert_conflict" in set((queue_map.get(post_id) or {}).get("flags") or []),
            }
            base.update(source)
            base.update(search_audit)
            base["guard_flags"] = sorted((log_data["posts"].get(post_id) or _new_log_summary(post_id))["guard_flags"].keys())
            base["override_flags"] = sorted((log_data["posts"].get(post_id) or _new_log_summary(post_id))["override_flags"].keys())
            base["log_excerpts"] = list((log_data["posts"].get(post_id) or _new_log_summary(post_id))["excerpts"])
            base["blind_is_relevant"] = blind.get("is_relevant") if blind else ""
            base["blind_discussion_type"] = blind.get("discussion_type") if blind else ""
            base["blind_primary_work"] = blind.get("primary_work") if blind else ""
            base["blind_secondary_works"] = blind.get("secondary_works") if blind else []
            base["blind_confidence"] = blind.get("confidence") if blind else ""
            base["blind_is_review"] = blind.get("is_review") if blind else False
            base["blind_multi_work"] = blind.get("multi_work") if blind else False
            base["blind_author_new_work_context"] = blind.get("author_new_work_context") if blind else False
            base["blind_association_post"] = blind.get("association_post") if blind else False
            base["blind_general_vs_specific"] = blind.get("general_vs_specific") if blind else ""
            base["blind_character_anchor_only"] = blind.get("character_anchor_only") if blind else False
            base["body_understanding_notes"] = blind.get("body_understanding_summary") if blind else ""
            base["review_notes"] = ""
            mismatch_class, risk_labels, risk_score = self._compute_risk_labels(base, blind, search_audit, trace, None)
            base["mismatch_class"] = mismatch_class
            base["risk_labels"] = risk_labels
            base["risk_score"] = risk_score
            merged_rows.append(base)

        explanation_path = self.config.output_dir / "llm_targeted_explanations.jsonl"
        explanation_map: Dict[int, Dict[str, Any]] = {}
        if self.config.enable_targeted_explanations:
            explain_rows = self._select_targeted_explanation_rows(merged_rows)
            existing_explanations = _load_jsonl_map(explanation_path) if self.config.resume else {}
            pending = [row for row in explain_rows if row["post_id"] not in existing_explanations]
            if pending:
                def explain_wrapper(row: Dict[str, Any]) -> Dict[str, Any]:
                    blind = blind_map.get(row["post_id"]) or {}
                    search_audit = search_map.get(row["post_id"]) or {}
                    log_summary = log_data["posts"].get(row["post_id"]) or _new_log_summary(row["post_id"])
                    return self._targeted_explain_one(row, blind, search_audit, log_summary)

                explanation_map = self._run_llm_pass(
                    pending,
                    explanation_path,
                    max(1, self.config.explanation_workers),
                    explain_wrapper,
                )
                explanation_map.update(existing_explanations)
            else:
                explanation_map = existing_explanations
        elif explanation_path.exists():
            explanation_map = _load_jsonl_map(explanation_path)
        else:
            explanation_path.write_text("", encoding="utf-8")

        post_rows: List[Dict[str, Any]] = []
        for row in merged_rows:
            explanation = explanation_map.get(row["post_id"])
            mismatch_class, risk_labels, risk_score = self._compute_risk_labels(
                row,
                blind_map.get(row["post_id"]),
                search_map.get(row["post_id"]) or {},
                trace_map.get(row["post_id"]) or {},
                explanation,
            )
            updated = dict(row)
            updated["mismatch_class"] = mismatch_class
            updated["risk_labels"] = risk_labels
            updated["risk_score"] = risk_score
            if explanation:
                updated["body_understanding_notes"] = explanation.get("body_understanding_notes") or updated.get("body_understanding_notes") or ""
                updated["review_notes"] = explanation.get("review_notes") or ""
                updated["targeted_summary"] = explanation.get("summary") or ""
                updated["search_assessment"] = explanation.get("search_assessment") or ""
            else:
                if updated.get("pipeline_discussion_type") == "review" or updated.get("blind_is_review"):
                    updated["review_notes"] = (
                        f"pipeline_review={updated.get('pipeline_discussion_type') == 'review'} "
                        f"blind_review={updated.get('blind_is_review')} "
                        f"secondary={_compact_join(updated.get('blind_secondary_works') or [])}"
                    )
                updated["targeted_summary"] = ""
                updated["search_assessment"] = ""
            post_rows.append(updated)

        trace_rows = [trace_map[post_id] for post_id in sorted(trace_map)]
        search_rows = [
            {
                **search_map[post_id],
                "pipeline_official_title": result_map[post_id].get("pipeline_official_title"),
                "pipeline_confidence": result_map[post_id].get("pipeline_confidence"),
                "has_official_url": bool(result_map[post_id].get("pipeline_heretic_url")),
                "candidate_source_tiers": _compact_join(result_map[post_id].get("candidate_source_tiers") or []),
            }
            for post_id in sorted(search_map)
        ]

        post_jsonl_path = self.config.output_dir / "post_audit.jsonl"
        post_csv_path = self.config.output_dir / "post_audit.csv"
        trace_csv_path = self.config.output_dir / "trace_reconciliation.csv"
        search_csv_path = self.config.output_dir / "search_audit.csv"
        summary_path = self.config.output_dir / "summary.md"
        dossiers_path = self.config.output_dir / "risk_dossiers.md"

        self._write_jsonl(post_jsonl_path, post_rows)
        self._write_csv(
            post_csv_path,
            post_rows,
            [
                "post_id",
                "title",
                "pipeline_is_relevant",
                "pipeline_discussion_type",
                "pipeline_relevance_scope",
                "pipeline_official_title",
                "pipeline_confidence",
                "identity_state",
                "run_id",
                "run_model",
                "run_llm_mode",
                "run_prompt_version",
                "run_config_hash",
                "candidate_count",
                "mentioned_work_count",
                "future_watch_target_present",
                "executed_queries",
                "effective_queries",
                "degraded_queries",
                "zero_result_queries",
                "duplicate_queries",
                "reason_evidence_diversity",
                "guard_flags",
                "override_flags",
                "expert_conflict",
                "active_learning_flags",
                "blind_is_relevant",
                "blind_discussion_type",
                "blind_primary_work",
                "blind_secondary_works",
                "blind_confidence",
                "mismatch_class",
                "risk_score",
                "risk_labels",
                "review_notes",
                "body_understanding_notes",
            ],
        )
        self._write_csv(
            trace_csv_path,
            trace_rows,
            [
                "post_id",
                "in_result",
                "in_input",
                "in_queue",
                "log_started",
                "log_done",
                "worker_ids",
                "start_count",
                "done_count",
                "elapsed_s",
                "reconciliation_status",
            ],
        )
        self._write_csv(
            search_csv_path,
            search_rows,
            [
                "post_id",
                "pipeline_official_title",
                "pipeline_confidence",
                "has_official_url",
                "executed_queries",
                "unique_executed_queries",
                "effective_queries",
                "official_query_count",
                "official_query_ratio",
                "community_query_count",
                "community_query_ratio",
                "duplicate_queries",
                "duplicate_ratio",
                "zero_result_queries",
                "zero_result_ratio",
                "degraded_queries",
                "degraded_ratio",
                "verification_requested",
                "verification_filtered",
                "verification_skipped",
                "skipped_queries",
                "search_labels",
                "purpose_counts",
                "query_chain_preview",
                "candidate_source_tiers",
            ],
        )
        self._write_summary(summary_path, post_rows, trace_rows, search_rows, log_data)
        self._write_risk_dossiers(dossiers_path, post_rows)

        return {
            "summary_md": summary_path,
            "post_audit_jsonl": post_jsonl_path,
            "post_audit_csv": post_csv_path,
            "llm_blind_reread_jsonl": blind_path,
            "trace_reconciliation_csv": trace_csv_path,
            "search_audit_csv": search_csv_path,
            "risk_dossiers_md": dossiers_path,
            "targeted_explanations_jsonl": explanation_path,
        }
