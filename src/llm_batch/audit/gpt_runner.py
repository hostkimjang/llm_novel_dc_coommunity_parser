from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .gpt_prompts import GPT_ADJUDICATION_PROMPT, GPT_BLIND_READ_PROMPT
from .openai_client import OpenAIJSONClient
from .runner import (
    ALL_DISCUSSION_TYPES,
    AuditConfig,
    AuditRunner,
    _build_blind_payload,
    _compact_join,
    _coerce_bool,
    _load_active_learning_map,
    _load_input_post_index,
    _load_json_file,
    _new_log_summary,
    _normalize_confidence,
    _normalize_discussion_type,
    _normalize_title,
    _safe_int,
    flatten_result_item,
    parse_worker_logs,
)

GPT_DISCUSSION_SCOPE_VALUES = {
    "single_work",
    "multi_work",
    "work_cluster_meta",
    "genre_general",
    "community_banter",
    "off_topic",
    "unclear",
}
GPT_REVIEW_STYLE_VALUES = {
    "none",
    "single_work_review",
    "multi_work_review",
    "partial_review",
    "unclear",
}
GPT_PIPELINE_AGREEMENT_VALUES = {"agree", "partial", "disagree"}
GPT_ERROR_TAXONOMY = [
    "false_negative_due_to_alias_conservatism",
    "multi_work_collapse",
    "genre_vs_specific_confusion",
    "character_rant_misread",
    "review_bundle_misframed",
    "reason_final_contradiction",
    "search_overkill",
    "search_underreach",
    "comment_evidence_undervalued",
    "image_or_short_body_uncertainty",
]
GPT_ERROR_SET = set(GPT_ERROR_TAXONOMY)
COMMENTARY_HEADERS = [
    "1. 이 글이 실제로 말하는 것",
    "2. GPT가 왜 이렇게 읽는지",
    "3. 파이프라인 판정의 적절성",
    "4. 검색/검증 과정 평",
    "5. 현재 처리 방식의 한계 또는 오판 가능성",
    "6. GPT 최종 재판정",
]


@dataclass
class GPTFullAuditConfig:
    result_path: Path
    log_prefix: Path
    output_dir: Path
    openai_model: str
    input_path: Optional[Path] = None
    queue_path: Optional[Path] = None
    openai_base_url: Optional[str] = None
    workers: int = 1
    timeout_s: float = 300.0
    resume: bool = True
    max_casebook_per_class: int = 3


def _normalized_string_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalize_scope(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in GPT_DISCUSSION_SCOPE_VALUES else "unclear"


def _normalize_review_style(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in GPT_REVIEW_STYLE_VALUES else "unclear"


def _normalize_agreement(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in GPT_PIPELINE_AGREEMENT_VALUES else ""


def _extract_reason_trace_contradiction(row: Dict[str, Any]) -> bool:
    reason_text = str(row.get("reason") or "")
    if row.get("pipeline_is_relevant") and "판정: 비관련" in reason_text:
        return True
    if (not row.get("pipeline_is_relevant")) and "판정: 관련" in reason_text:
        return True
    if row.get("identity_state") == "resolved_title" and "공식 제목: 미확정" in reason_text:
        return True
    return False


def _derive_agreement(row: Dict[str, Any], final_result: Dict[str, Any]) -> str:
    same_relevance = _coerce_bool(final_result.get("final_is_relevant")) == _coerce_bool(row.get("pipeline_is_relevant"))
    same_discussion = str(final_result.get("final_discussion_type") or "") == str(row.get("pipeline_discussion_type") or "")
    final_title = _normalize_title(final_result.get("final_primary_work"))
    pipeline_title = _normalize_title(row.get("pipeline_official_title"))
    same_title = (not final_title and not pipeline_title) or (final_title and final_title == pipeline_title)
    if same_relevance and same_discussion and same_title:
        return "agree"
    if same_relevance or same_discussion or same_title:
        return "partial"
    return "disagree"


def _infer_error_class(
    row: Dict[str, Any],
    blind: Dict[str, Any],
    final_result: Dict[str, Any],
    search_audit: Dict[str, Any],
) -> str:
    if _coerce_bool(final_result.get("image_or_short_body_uncertainty")):
        return "image_or_short_body_uncertainty"
    if _extract_reason_trace_contradiction(row):
        return "reason_final_contradiction"
    if final_result.get("final_scope") == "multi_work":
        return "multi_work_collapse"
    if blind.get("is_review") and blind.get("discussion_scope") == "multi_work":
        return "review_bundle_misframed"
    if blind.get("character_anchor_only") and row.get("pipeline_official_title"):
        return "character_rant_misread"
    if _coerce_bool(final_result.get("final_is_relevant")) and not _coerce_bool(row.get("pipeline_is_relevant")):
        if "under_searched" in (search_audit.get("search_labels") or []) or not row.get("pipeline_official_title"):
            return "false_negative_due_to_alias_conservatism"
        return "comment_evidence_undervalued"
    if not _coerce_bool(final_result.get("final_is_relevant")) and _coerce_bool(row.get("pipeline_is_relevant")):
        return "genre_vs_specific_confusion"
    if "search_thrash" in (search_audit.get("search_labels") or []) or "verification_loop_stalled" in (search_audit.get("search_labels") or []):
        return "search_overkill"
    if "under_searched" in (search_audit.get("search_labels") or []):
        return "search_underreach"
    return "none"


def _collect_failure_modes(
    row: Dict[str, Any],
    blind: Dict[str, Any],
    final_result: Dict[str, Any],
    search_audit: Dict[str, Any],
    error_class: str,
    raw_modes: Any,
) -> List[str]:
    modes = [mode for mode in _normalized_string_list(raw_modes) if mode in GPT_ERROR_SET]
    if error_class in GPT_ERROR_SET and error_class not in modes:
        modes.append(error_class)
    if _extract_reason_trace_contradiction(row) and "reason_final_contradiction" not in modes:
        modes.append("reason_final_contradiction")
    if blind.get("discussion_scope") == "multi_work" and "multi_work_collapse" not in modes:
        if row.get("pipeline_official_title") or _safe_int(row.get("mentioned_work_count")) < 2:
            modes.append("multi_work_collapse")
    if blind.get("is_review") and blind.get("discussion_scope") == "multi_work" and "review_bundle_misframed" not in modes:
        modes.append("review_bundle_misframed")
    if blind.get("character_anchor_only") and row.get("pipeline_official_title") and "character_rant_misread" not in modes:
        modes.append("character_rant_misread")
    if "search_thrash" in (search_audit.get("search_labels") or []) and "search_overkill" not in modes:
        modes.append("search_overkill")
    if "under_searched" in (search_audit.get("search_labels") or []) and "search_underreach" not in modes:
        modes.append("search_underreach")
    if blind.get("image_or_short_body_uncertainty") and "image_or_short_body_uncertainty" not in modes:
        modes.append("image_or_short_body_uncertainty")
    return [mode for mode in GPT_ERROR_TAXONOMY if mode in set(modes)]


def _build_final_judgment_line(final_result: Dict[str, Any]) -> str:
    title = str(final_result.get("final_primary_work") or "").strip()
    secondary = _compact_join(final_result.get("final_secondary_works") or [])
    title_text = title or "단일 대표작 미확정"
    if secondary:
        title_text = f"{title_text} / 보조 작품: {secondary}"
    return (
        f"관련={final_result.get('final_is_relevant')} / discussion_type={final_result.get('final_discussion_type')} / "
        f"scope={final_result.get('final_scope')} / 대표작={title_text}"
    )


def _ensure_commentary(
    commentary: Any,
    *,
    blind: Dict[str, Any],
    row: Dict[str, Any],
    final_result: Dict[str, Any],
    search_audit: Dict[str, Any],
) -> str:
    text = str(commentary or "").strip()
    if all(header in text for header in COMMENTARY_HEADERS):
        return text

    fallback_parts = [
        f"{COMMENTARY_HEADERS[0]}\n{blind.get('body_understanding') or '텍스트 단서가 제한적이어서 해석을 보수적으로 잡았다.'}",
        f"{COMMENTARY_HEADERS[1]}\n{blind.get('why') or '제목, 본문, 댓글에 드러난 단서 조합으로 작품 관련성과 범위를 판단했다.'}",
        (
            f"{COMMENTARY_HEADERS[2]}\n"
            f"파이프라인은 relevant={row.get('pipeline_is_relevant')} / discussion_type={row.get('pipeline_discussion_type')} / "
            f"official_title={row.get('pipeline_official_title') or '미확정'}로 처리했다. "
            f"GPT 기준 최종 합의도는 {final_result.get('pipeline_agreement')}다."
        ),
        (
            f"{COMMENTARY_HEADERS[3]}\n"
            f"{final_result.get('search_strategy_review') or '검색/검증 로그에서 과탐색과 과소탐색 여부를 함께 검토했다.'} "
            f"(executed_queries={search_audit.get('executed_queries')}, labels={_compact_join(search_audit.get('search_labels') or []) or '없음'})"
        ),
        f"{COMMENTARY_HEADERS[4]}\n{final_result.get('limitations_observed') or '현재 처리 방식은 약칭, 복수 작품, 댓글 증거 활용에서 흔들릴 여지가 있다.'}",
        f"{COMMENTARY_HEADERS[5]}\n{_build_final_judgment_line(final_result)}",
    ]
    return "\n".join(fallback_parts).strip()


def _normalize_gpt_blind_result(post_id: int, raw: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        "post_id": post_id,
        "is_relevant": _coerce_bool(raw.get("is_relevant")),
        "discussion_type": _normalize_discussion_type(raw.get("discussion_type")),
        "primary_work": str(raw.get("primary_work") or "").strip(),
        "secondary_works": _normalized_string_list(raw.get("secondary_works")),
        "discussion_scope": _normalize_scope(raw.get("discussion_scope")),
        "is_review": _coerce_bool(raw.get("is_review")),
        "review_style": _normalize_review_style(raw.get("review_style")),
        "author_new_work_context": _coerce_bool(raw.get("author_new_work_context")),
        "association_post": _coerce_bool(raw.get("association_post")),
        "general_vs_specific": str(raw.get("general_vs_specific") or "unclear").strip().lower() or "unclear",
        "character_anchor_only": _coerce_bool(raw.get("character_anchor_only")),
        "image_or_short_body_uncertainty": _coerce_bool(raw.get("image_or_short_body_uncertainty")),
        "confidence": _normalize_confidence(raw.get("confidence")),
        "body_understanding": str(raw.get("body_understanding") or "").strip(),
        "why": str(raw.get("why") or "").strip(),
    }
    if normalized["discussion_type"] not in ALL_DISCUSSION_TYPES and normalized["discussion_type"] != "None":
        normalized["discussion_type"] = "None"
    if normalized["general_vs_specific"] not in {"specific", "general", "mixed", "unclear"}:
        normalized["general_vs_specific"] = "unclear"
    if normalized["discussion_scope"] == "unclear":
        if normalized["secondary_works"]:
            normalized["discussion_scope"] = "multi_work"
        elif normalized["is_relevant"] and normalized["primary_work"]:
            normalized["discussion_scope"] = "single_work"
    if normalized["review_style"] == "unclear":
        if normalized["is_review"] and normalized["discussion_scope"] == "multi_work":
            normalized["review_style"] = "multi_work_review"
        elif normalized["is_review"]:
            normalized["review_style"] = "single_work_review"
        else:
            normalized["review_style"] = "none"
    return normalized


def _normalize_gpt_adjudication_result(
    post_id: int,
    raw: Dict[str, Any],
    *,
    row: Dict[str, Any],
    blind: Dict[str, Any],
    search_audit: Dict[str, Any],
) -> Dict[str, Any]:
    final_result = {
        "post_id": post_id,
        "final_is_relevant": _coerce_bool(raw.get("final_is_relevant")) if "final_is_relevant" in raw else _coerce_bool(blind.get("is_relevant")),
        "final_discussion_type": _normalize_discussion_type(raw.get("final_discussion_type") or blind.get("discussion_type")),
        "final_primary_work": str(raw.get("final_primary_work") or blind.get("primary_work") or "").strip(),
        "final_secondary_works": _normalized_string_list(raw.get("final_secondary_works") or blind.get("secondary_works")),
        "final_scope": _normalize_scope(raw.get("final_scope") or blind.get("discussion_scope")),
        "pipeline_agreement": _normalize_agreement(raw.get("pipeline_agreement")),
        "error_class": str(raw.get("error_class") or "").strip().lower(),
        "body_understanding": str(raw.get("body_understanding") or blind.get("body_understanding") or "").strip(),
        "search_strategy_review": str(raw.get("search_strategy_review") or "").strip(),
        "review_analysis": str(raw.get("review_analysis") or "").strip(),
        "limitations_observed": str(raw.get("limitations_observed") or "").strip(),
        "detailed_commentary": str(raw.get("detailed_commentary") or "").strip(),
        "image_or_short_body_uncertainty": _coerce_bool(raw.get("image_or_short_body_uncertainty")) or _coerce_bool(blind.get("image_or_short_body_uncertainty")),
    }
    if final_result["final_discussion_type"] not in ALL_DISCUSSION_TYPES and final_result["final_discussion_type"] != "None":
        final_result["final_discussion_type"] = "None"
    if final_result["final_scope"] == "unclear":
        if final_result["final_secondary_works"]:
            final_result["final_scope"] = "multi_work"
        elif final_result["final_is_relevant"] and final_result["final_primary_work"]:
            final_result["final_scope"] = "single_work"
    if final_result["final_scope"] == "multi_work" and not final_result["final_secondary_works"]:
        if blind.get("secondary_works"):
            final_result["final_secondary_works"] = list(blind.get("secondary_works") or [])
        elif final_result["final_primary_work"]:
            final_result["final_scope"] = "single_work"
        else:
            final_result["final_scope"] = "unclear"

    if not final_result["pipeline_agreement"]:
        final_result["pipeline_agreement"] = _derive_agreement(row, final_result)
    if final_result["error_class"] not in GPT_ERROR_SET | {"none"}:
        final_result["error_class"] = ""
    if not final_result["error_class"]:
        final_result["error_class"] = _infer_error_class(row, blind, final_result, search_audit)
    final_result["failure_modes"] = _collect_failure_modes(
        row,
        blind,
        final_result,
        search_audit,
        final_result["error_class"],
        raw.get("failure_modes"),
    )
    if not final_result["final_is_relevant"] and final_result["final_primary_work"] and "reason_final_contradiction" not in final_result["failure_modes"]:
        final_result["failure_modes"].append("reason_final_contradiction")
        if final_result["error_class"] == "none":
            final_result["error_class"] = "reason_final_contradiction"
    final_result["failure_modes"] = [mode for mode in GPT_ERROR_TAXONOMY if mode in set(final_result["failure_modes"])]
    if final_result["error_class"] not in GPT_ERROR_SET | {"none"}:
        final_result["error_class"] = "none"
    final_result["detailed_commentary"] = _ensure_commentary(
        final_result["detailed_commentary"],
        blind=blind,
        row=row,
        final_result=final_result,
        search_audit=search_audit,
    )
    return final_result


class GPTFullAuditRunner(AuditRunner):
    def __init__(
        self,
        config: GPTFullAuditConfig,
        *,
        gpt_client_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.gpt_config = config
        self.gpt_client_factory = gpt_client_factory
        super().__init__(
            AuditConfig(
                result_path=config.result_path,
                log_prefix=config.log_prefix,
                output_dir=config.output_dir,
                input_path=config.input_path,
                queue_path=config.queue_path,
                enable_blind_reread=False,
                enable_targeted_explanations=False,
                blind_workers=max(1, config.workers),
                explanation_workers=max(1, config.workers),
                resume=config.resume,
                max_dossiers_per_label=max(1, config.max_casebook_per_class),
            )
        )

    def _make_gpt_client(self) -> Any:
        if self.gpt_client_factory is not None:
            return self.gpt_client_factory()
        return OpenAIJSONClient(
            model=self.gpt_config.openai_model,
            base_url=self.gpt_config.openai_base_url,
            timeout_s=self.gpt_config.timeout_s,
        )

    def _build_source_post(self, row: Dict[str, Any], input_posts: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        input_row = input_posts.get(row["post_id"]) or {}
        return {
            "post_id": row["post_id"],
            "title": input_row.get("title") or row.get("title") or "",
            "content_blocks": input_row.get("content_blocks") or row.get("content") or row.get("raw_result", {}).get("content") or [],
            "comments": input_row.get("comments") or row.get("comments") or row.get("raw_result", {}).get("comments") or [],
        }

    def _blind_read_one(self, row: Dict[str, Any]) -> Dict[str, Any]:
        client = self._make_gpt_client()
        raw = client.complete_json(
            GPT_BLIND_READ_PROMPT,
            row["gpt_blind_payload"],
            tag=f"gpt_blind:{row['post_id']}",
            max_tokens=1200,
            temperature=0.1,
        )
        return _normalize_gpt_blind_result(row["post_id"], raw)

    def _adjudicate_one(
        self,
        row: Dict[str, Any],
        blind: Dict[str, Any],
        search_audit: Dict[str, Any],
        trace: Dict[str, Any],
        log_summary: Dict[str, Any],
    ) -> Dict[str, Any]:
        client = self._make_gpt_client()
        payload = {
            "post_id": row["post_id"],
            "original": row["gpt_blind_payload"],
            "blind": blind,
            "pipeline": {
                "is_relevant": row.get("pipeline_is_relevant"),
                "relevance_scope": row.get("pipeline_relevance_scope"),
                "discussion_type": row.get("pipeline_discussion_type"),
                "official_title": row.get("pipeline_official_title"),
                "confidence": row.get("pipeline_confidence"),
                "identity_state": row.get("identity_state"),
                "run_id": row.get("run_id"),
                "run_model": row.get("run_model"),
                "run_prompt_version": row.get("run_prompt_version"),
                "run_config_hash": row.get("run_config_hash"),
                "candidate_titles": row.get("candidate_titles"),
                "mentioned_titles": row.get("mentioned_titles"),
                "active_learning_flags": row.get("active_learning_flags"),
            },
            "reason_summary": {
                "decision_line": row.get("reason_decision_line"),
                "discussion_line": row.get("reason_discussion_line"),
                "official_line": row.get("reason_official_line"),
                "evidence_diversity": row.get("reason_evidence_diversity"),
                "reason_sections": row.get("reason_sections"),
            },
            "search_audit": {
                "executed_queries": search_audit.get("executed_queries"),
                "effective_queries": search_audit.get("effective_queries"),
                "duplicate_queries": search_audit.get("duplicate_queries"),
                "zero_result_queries": search_audit.get("zero_result_queries"),
                "degraded_queries": search_audit.get("degraded_queries"),
                "official_query_ratio": search_audit.get("official_query_ratio"),
                "community_query_ratio": search_audit.get("community_query_ratio"),
                "search_labels": search_audit.get("search_labels"),
                "query_chain_preview": search_audit.get("query_chain_preview"),
            },
            "trace": {
                "reconciliation_status": trace.get("reconciliation_status"),
                "log_started": trace.get("log_started"),
                "log_done": trace.get("log_done"),
                "worker_ids": trace.get("worker_ids"),
            },
            "log_trace": list((log_summary.get("excerpts") or [])[:12]),
        }
        raw = client.complete_json(
            GPT_ADJUDICATION_PROMPT,
            payload,
            tag=f"gpt_adjudication:{row['post_id']}",
            max_tokens=2600,
            temperature=0.1,
        )
        return _normalize_gpt_adjudication_result(
            row["post_id"],
            raw,
            row=row,
            blind=blind,
            search_audit=search_audit,
        )

    def _validate_post_rows(self, rows: List[Dict[str, Any]]) -> None:
        seen = set()
        for row in rows:
            post_id = row["post_id"]
            if post_id in seen:
                raise ValueError(f"duplicate post_id in GPT audit output: {post_id}")
            seen.add(post_id)
            if row.get("gpt_final_is_relevant") not in {True, False}:
                raise ValueError(f"missing gpt_final_is_relevant for post_id={post_id}")
            if not str(row.get("gpt_final_discussion_type") or "").strip():
                raise ValueError(f"missing gpt_final_discussion_type for post_id={post_id}")
            if not str(row.get("gpt_detailed_commentary") or "").strip():
                raise ValueError(f"missing gpt_detailed_commentary for post_id={post_id}")
            if row.get("gpt_final_scope") == "multi_work" and not (row.get("gpt_final_secondary_works") or []):
                raise ValueError(f"multi_work final_scope without secondary works: post_id={post_id}")

    def _write_gpt_summary(
        self,
        path: Path,
        post_rows: List[Dict[str, Any]],
        trace_rows: List[Dict[str, Any]],
    ) -> None:
        agreement_counts = Counter(row.get("gpt_pipeline_agreement") or "unknown" for row in post_rows)
        error_counts = Counter(row.get("gpt_error_class") or "none" for row in post_rows)
        failure_counts = Counter(mode for row in post_rows for mode in (row.get("gpt_failure_modes") or []))
        final_discussion_counts = Counter(row.get("gpt_final_discussion_type") or "None" for row in post_rows)
        blind_scope_counts = Counter(row.get("gpt_blind_scope") or "unclear" for row in post_rows)
        final_scope_counts = Counter(row.get("gpt_final_scope") or "unclear" for row in post_rows)
        coverage_counts = Counter(row.get("reconciliation_status") or "unknown" for row in trace_rows)
        top_disagreements = [
            row
            for row in post_rows
            if row.get("gpt_pipeline_agreement") != "agree" or row.get("gpt_error_class") != "none"
        ]
        top_disagreements = sorted(
            top_disagreements,
            key=lambda row: (
                row.get("gpt_pipeline_agreement") == "agree",
                row.get("gpt_error_class") == "none",
                -_safe_int(row.get("executed_queries")),
                row.get("post_id"),
            ),
        )[:12]

        lines = [
            "# GPT Full Audit Summary",
            "",
            "## Run",
            f"- total_posts: {len(post_rows)}",
            f"- openai_model: {self.gpt_config.openai_model}",
            f"- blind_plus_adjudication_coverage: {len(post_rows)}/{len(post_rows)}",
            "",
            "## Pipeline Agreement",
        ]
        for key, count in sorted(agreement_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {count}")
        lines.extend(["", "## GPT Final Discussion Types"])
        for key, count in sorted(final_discussion_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {count}")
        lines.extend(["", "## Scope Distribution"])
        for key, count in sorted(blind_scope_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- blind_{key}: {count}")
        for key, count in sorted(final_scope_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- final_{key}: {count}")
        lines.extend(["", "## Error Classes"])
        for key in ["none"] + GPT_ERROR_TAXONOMY:
            lines.append(f"- {key}: {error_counts.get(key, 0)}")
        lines.extend(["", "## Failure Modes"])
        for key in GPT_ERROR_TAXONOMY:
            lines.append(f"- {key}: {failure_counts.get(key, 0)}")
        lines.extend(["", "## Coverage / Trace"])
        for key, count in sorted(coverage_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {count}")
        lines.extend(["", "## Search Strategy Totals"])
        for label in [
            "smart_search",
            "under_searched",
            "search_thrash",
            "community_overfit",
            "official_anchor_missing",
            "verification_loop_good",
            "verification_loop_stalled",
        ]:
            lines.append(f"- {label}: {sum(1 for row in post_rows if label in (row.get('search_labels') or []))}")
        lines.extend(["", "## Representative Disagreements"])
        for row in top_disagreements:
            lines.append(
                f"- post_id={row['post_id']} agreement={row.get('gpt_pipeline_agreement')} error={row.get('gpt_error_class')} "
                f"pipeline_title={row.get('pipeline_official_title') or 'None'} gpt_title={row.get('gpt_final_primary_work') or 'None'} "
                f"labels={_compact_join(row.get('gpt_failure_modes') or []) or 'none'}"
            )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _render_casebook_case(self, row: Dict[str, Any]) -> List[str]:
        return [
            f"### post_id={row['post_id']} | {row.get('title') or '(untitled)'}",
            f"- pipeline: relevant={row.get('pipeline_is_relevant')} dt={row.get('pipeline_discussion_type')} title={row.get('pipeline_official_title') or 'None'} conf={row.get('pipeline_confidence')}",
            f"- blind: relevant={row.get('gpt_blind_is_relevant')} dt={row.get('gpt_blind_discussion_type')} scope={row.get('gpt_blind_scope')} title={row.get('gpt_blind_primary_work') or 'None'}",
            f"- final: relevant={row.get('gpt_final_is_relevant')} dt={row.get('gpt_final_discussion_type')} scope={row.get('gpt_final_scope')} title={row.get('gpt_final_primary_work') or 'None'}",
            f"- agreement: {row.get('gpt_pipeline_agreement')} / error_class={row.get('gpt_error_class')} / failure_modes={_compact_join(row.get('gpt_failure_modes') or []) or 'none'}",
            f"- search: executed={row.get('executed_queries')} labels={_compact_join(row.get('search_labels') or []) or 'none'}",
            "",
            row.get("gpt_detailed_commentary") or "",
        ]

    def _write_gpt_casebook(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        by_error: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_error[row.get("gpt_error_class") or "none"].append(row)
        strong_cases = [
            row
            for row in rows
            if row.get("gpt_pipeline_agreement") == "agree"
            and row.get("gpt_error_class") == "none"
            and "smart_search" in (row.get("search_labels") or [])
        ]
        lines = ["# GPT Full Audit Casebook", ""]
        for error_class in GPT_ERROR_TAXONOMY:
            cases = sorted(
                by_error.get(error_class) or [],
                key=lambda row: (-_safe_int(row.get("executed_queries")), row.get("post_id")),
            )
            lines.append(f"## {error_class}")
            lines.append(f"- count: {len(cases)}")
            lines.append("")
            for row in cases[: self.gpt_config.max_casebook_per_class]:
                lines.extend(self._render_casebook_case(row))
                lines.append("")
        lines.append("## Strong Agreements")
        lines.append(f"- count: {len(strong_cases)}")
        lines.append("")
        for row in strong_cases[: self.gpt_config.max_casebook_per_class]:
            lines.extend(self._render_casebook_case(row))
            lines.append("")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def run(self) -> Dict[str, Path]:
        results = _load_json_file(self.config.result_path)
        result_items = results if isinstance(results, list) else (results.get("results") or [])
        queue_map = _load_active_learning_map(self.config.queue_path)
        input_posts = _load_input_post_index(self.config.input_path)
        log_data = parse_worker_logs(self.config.log_prefix)

        result_rows = [
            flatten_result_item(item, queue_map)
            for item in result_items
            if _safe_int(item.get("post_id"))
        ]
        result_rows.sort(key=lambda row: row["post_id"])
        result_map = {row["post_id"]: row for row in result_rows}
        trace_map = self._compute_trace_reconciliation(result_map, input_posts, log_data, queue_map)
        search_map = {
            row["post_id"]: self._compute_search_audit(row, log_data["posts"].get(row["post_id"]) or _new_log_summary(row["post_id"]))
            for row in result_rows
        }

        blind_rows = []
        for row in result_rows:
            enriched = dict(row)
            enriched["gpt_blind_payload"] = _build_blind_payload(self._build_source_post(row, input_posts))
            blind_rows.append(enriched)

        blind_path = self.config.output_dir / "gpt_blind_read.jsonl"
        blind_map = self._run_llm_pass(
            blind_rows,
            blind_path,
            max(1, self.gpt_config.workers),
            self._blind_read_one,
        )

        adjudication_path = self.config.output_dir / "gpt_adjudication.jsonl"

        def adjudicate_wrapper(row: Dict[str, Any]) -> Dict[str, Any]:
            blind = blind_map[row["post_id"]]
            search_audit = search_map[row["post_id"]]
            trace = trace_map[row["post_id"]]
            log_summary = log_data["posts"].get(row["post_id"]) or _new_log_summary(row["post_id"])
            return self._adjudicate_one(row, blind, search_audit, trace, log_summary)

        adjudication_map = self._run_llm_pass(
            blind_rows,
            adjudication_path,
            max(1, self.gpt_config.workers),
            adjudicate_wrapper,
        )

        post_rows: List[Dict[str, Any]] = []
        for row in result_rows:
            blind = blind_map.get(row["post_id"]) or {}
            adjudication = adjudication_map.get(row["post_id"]) or {}
            search_audit = search_map.get(row["post_id"]) or {}
            trace = trace_map.get(row["post_id"]) or {}
            merged = {
                "post_id": row["post_id"],
                "title": row.get("title") or "",
                "pipeline_is_relevant": row.get("pipeline_is_relevant"),
                "pipeline_discussion_type": row.get("pipeline_discussion_type"),
                "pipeline_official_title": row.get("pipeline_official_title"),
                "pipeline_confidence": row.get("pipeline_confidence"),
                "identity_state": row.get("identity_state"),
                "candidate_count": row.get("candidate_count"),
                "mentioned_work_count": row.get("mentioned_work_count"),
                "active_learning_flags": row.get("active_learning_flags") or [],
                "executed_queries": search_audit.get("executed_queries", 0),
                "search_labels": search_audit.get("search_labels") or [],
                "reconciliation_status": trace.get("reconciliation_status") or "",
                "gpt_blind_is_relevant": blind.get("is_relevant"),
                "gpt_blind_discussion_type": blind.get("discussion_type"),
                "gpt_blind_primary_work": blind.get("primary_work"),
                "gpt_blind_secondary_works": blind.get("secondary_works") or [],
                "gpt_blind_scope": blind.get("discussion_scope"),
                "gpt_blind_is_review": blind.get("is_review"),
                "gpt_blind_review_style": blind.get("review_style"),
                "gpt_blind_confidence": blind.get("confidence"),
                "gpt_final_is_relevant": adjudication.get("final_is_relevant"),
                "gpt_final_discussion_type": adjudication.get("final_discussion_type"),
                "gpt_final_primary_work": adjudication.get("final_primary_work"),
                "gpt_final_secondary_works": adjudication.get("final_secondary_works") or [],
                "gpt_final_scope": adjudication.get("final_scope"),
                "gpt_pipeline_agreement": adjudication.get("pipeline_agreement"),
                "gpt_error_class": adjudication.get("error_class"),
                "gpt_failure_modes": adjudication.get("failure_modes") or [],
                "gpt_body_understanding": adjudication.get("body_understanding") or blind.get("body_understanding") or "",
                "gpt_search_strategy_review": adjudication.get("search_strategy_review") or "",
                "gpt_review_analysis": adjudication.get("review_analysis") or "",
                "gpt_limitations_observed": adjudication.get("limitations_observed") or "",
                "gpt_detailed_commentary": adjudication.get("detailed_commentary") or "",
            }
            post_rows.append(merged)

        self._validate_post_rows(post_rows)

        post_jsonl_path = self.config.output_dir / "gpt_post_audit.jsonl"
        post_csv_path = self.config.output_dir / "gpt_post_audit.csv"
        summary_path = self.config.output_dir / "gpt_summary.md"
        casebook_path = self.config.output_dir / "gpt_casebook.md"

        self._write_jsonl(post_jsonl_path, post_rows)
        self._write_csv(
            post_csv_path,
            post_rows,
            [
                "post_id",
                "title",
                "pipeline_is_relevant",
                "pipeline_discussion_type",
                "pipeline_official_title",
                "pipeline_confidence",
                "identity_state",
                "candidate_count",
                "mentioned_work_count",
                "active_learning_flags",
                "executed_queries",
                "search_labels",
                "reconciliation_status",
                "gpt_blind_is_relevant",
                "gpt_blind_discussion_type",
                "gpt_blind_primary_work",
                "gpt_blind_secondary_works",
                "gpt_blind_scope",
                "gpt_final_is_relevant",
                "gpt_final_discussion_type",
                "gpt_final_primary_work",
                "gpt_final_secondary_works",
                "gpt_final_scope",
                "gpt_pipeline_agreement",
                "gpt_error_class",
                "gpt_failure_modes",
                "gpt_body_understanding",
                "gpt_search_strategy_review",
                "gpt_review_analysis",
                "gpt_limitations_observed",
                "gpt_detailed_commentary",
            ],
        )
        self._write_gpt_summary(summary_path, post_rows, list(trace_map.values()))
        self._write_gpt_casebook(casebook_path, post_rows)

        return {
            "gpt_post_audit_jsonl": post_jsonl_path,
            "gpt_post_audit_csv": post_csv_path,
            "gpt_summary_md": summary_path,
            "gpt_casebook_md": casebook_path,
            "gpt_blind_read_jsonl": blind_path,
            "gpt_adjudication_jsonl": adjudication_path,
        }
