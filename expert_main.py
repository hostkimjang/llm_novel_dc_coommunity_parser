from __future__ import annotations

"""
Agentic Pipeline (유기적 전문가 시스템) 원클릭 엔트리포인트.

목표:
- tests/inputs/sample.jsonl 같은 커뮤니티 게시글을 Agentic Pipeline으로 분석
- main.py와 동일한 LLM/MCP 환경설정 사용
- 토큰 사용량, 로그, 결과를 main.py처럼 저장
"""

import argparse
from difflib import SequenceMatcher
import json
import os
import re
import signal
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit, urlunsplit

_DEFAULT_VLM_MAX_IMAGE_BYTES = "16777216"

# 대시보드 비활성화 플래그: --no-dashboard
_NO_DASHBOARD = "--no-dashboard" in sys.argv

# ─── CLI 인자 파싱 ──────────────────────────────────────
def _build_arg_parser(*, add_help: bool) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agentic Pipeline (유기적 전문가 시스템)",
        add_help=add_help,  # 기존 sys.argv[1] 호환성 유지
    )
    parser.add_argument("input", nargs="?", default=None, help="입력 JSONL 파일 경로")
    parser.add_argument("--input", dest="input_flag", default=None, help="입력 JSONL 파일 경로 (--input 형식)")
    parser.add_argument("--output", "-o", default=None, help="출력 JSON 파일 경로")
    parser.add_argument("--parallel", "-p", type=int, default=1, help="최대 병렬 처리 워커 수 (기본: 1, 실제 워커 수는 입력 post 수로 상한 조정)")
    parser.add_argument("--no-dashboard", action="store_true", help="대시보드 비활성화")
    parser.add_argument(
        "--server-type", "-s",
        choices=["llama", "vllm"],
        default=None,
        help="LLM 서빙 엔진 선택: llama (llama-server, 기본) 또는 vllm",
    )
    parser.add_argument("--llm-endpoint", default=None, help="LLM 서버 엔드포인트 URL (예: http://a100:8000)")
    parser.add_argument("--llm-model", default=None, help="사용할 모델명 (예: Qwen/Qwen3-32B)")
    parser.add_argument("--vlm", choices=["on", "off"], default=None, help="멀티모달/VLM 보강 사용 여부")
    parser.add_argument("--ocr", choices=["on", "off"], default=None, help="VLM 경로에서 OCR 텍스트 추출 여부")
    parser.add_argument("--vlm-fetch-timeout", type=float, default=None, help="이미지 fetch timeout (초)")
    parser.add_argument("--vlm-max-image-bytes", type=int, default=None, help="개별 이미지 최대 바이트")
    parser.add_argument("--vlm-max-total-bytes", type=int, default=None, help="포스트당 이미지 총 바이트 상한")
    parser.add_argument("--vlm-chunk-max-images", type=int, default=None, help="멀티모달 청크당 최대 이미지 수")
    parser.add_argument("--vlm-chunk-max-bytes", type=int, default=None, help="멀티모달 청크당 최대 바이트")
    parser.add_argument(
        "--require-vlm-ocr-for-images",
        action="store_true",
        help="이미지 post가 있으면 VLM/OCR이 모두 켜져 있지 않은 run을 시작 전에 실패 처리",
    )
    parser.add_argument(
        "--llm-suspend-on-anomaly",
        choices=["on", "off"],
        default=None,
        help="LLM 서버 무응답/이상 응답 누적 시 사용자 확인 후 재개",
    )
    parser.add_argument(
        "--llm-suspend-threshold",
        type=int,
        default=None,
        help="LLM 서버 이상 응답 누적 시 일시중지 임계값 (0=비활성)",
    )
    parser.add_argument(
        "--llm-stream-first-token-timeout",
        type=float,
        default=None,
        help="스트리밍 첫 토큰 대기 제한(초). 0 이하이면 비활성",
    )
    parser.add_argument(
        "--llm-stream-idle-timeout",
        type=float,
        default=None,
        help="스트리밍 청크 간 idle 대기 제한(초). 0 이하이면 비활성",
    )
    parser.add_argument("--slang-db", choices=["on", "off"], default=None, help="중앙 slang DB 검토용 저장 사용 여부")
    parser.add_argument("--slang-db-path", default=None, help="중앙 slang DB JSON 경로")
    parser.add_argument("--slang-db-flush-posts", type=int, default=None, help="slang DB flush post 간격")
    parser.add_argument("--slang-db-flush-seconds", type=int, default=None, help="slang DB flush 시간 간격(초)")
    parser.add_argument(
        "--auto-up-shards",
        action="store_true",
        help="로컬 MCP/WARP shard가 부족할 때 docker compose up 자동 실행을 명시적으로 허용",
    )
    parser.add_argument("--no-auto-up-shards", action="store_true", help="로컬 MCP/WARP shard 자동 기동 비활성화")
    parser.add_argument(
        "--auto-recreate-shards",
        action="store_true",
        help="WARP/search 헬스 실패 시 docker compose force-recreate 자동 실행을 명시적으로 허용",
    )
    parser.add_argument(
        "--no-auto-recreate-shards",
        action="store_true",
        help="WARP/search 헬스 실패 시 docker compose force-recreate 자동 실행 비활성화",
    )
    parser.add_argument(
        "--reuse-shards-only",
        action="store_true",
        help="기존 MCP/WARP shard만 재사용하고 docker compose up/recreate 자동 실행을 모두 생략",
    )
    parser.add_argument(
        "--allow-goal-shard-lifecycle",
        action="store_true",
        help="Allow Docker shard up/recreate in small goal/test runs. Requires --auto-up-shards or --auto-recreate-shards.",
    )
    return parser


def _parse_args() -> argparse.Namespace:
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        _build_arg_parser(add_help=True).print_help(sys.stderr)
        raise SystemExit(0)

    parser = _build_arg_parser(add_help=False)
    # 알 수 없는 인자 무시 (기존 호환성)
    args, _ = parser.parse_known_args()
    return args

_CLI_ARGS = _parse_args()
# --input 플래그가 positional input보다 우선
if _CLI_ARGS.input_flag:
    _CLI_ARGS.input = _CLI_ARGS.input_flag
def _default_llm_model_for_server_type(server_type: Optional[str]) -> str:
    if str(server_type or "").strip().lower() == "vllm":
        return "bg-digitalservices/Gemma-4-E4B-it-NVFP4"
    return "google/gemma-4-26B-A4B-it"


def _model_parallel_max(model_name: Optional[str]) -> Optional[int]:
    """Return the model-specific worker cap when the ops contract defines one."""
    model = str(model_name or "").strip().lower()
    if not model:
        return None
    normalized = re.sub(r"[^a-z0-9]+", "-", model)
    if (
        "gemma-4-e4b" in normalized
        or "gemma-4-4b" in normalized
        or "gemma-4b" in normalized
    ):
        return 36
    return None


def _resolve_model_for_parallel_policy() -> str:
    server_type = _CLI_ARGS.server_type or os.getenv("LLM_SERVER_TYPE", "vllm")
    return (
        _CLI_ARGS.llm_model
        or os.getenv("LLM_MODEL")
        or _default_llm_model_for_server_type(server_type)
    )


def _apply_model_parallel_cap(requested_parallel: int, model_name: Optional[str]) -> Dict[str, Any]:
    requested = max(1, int(requested_parallel or 1))
    model_max = _model_parallel_max(model_name)
    capped = min(requested, model_max) if model_max else requested
    return {
        "requested_parallel_raw": requested,
        "requested_parallel": capped,
        "model_parallel_max": model_max,
        "model_parallel_cap_applied": bool(model_max and capped != requested),
        "model_parallel_cap_model": str(model_name or ""),
    }


def _enforce_publish_contract_trace_convergence(result_dict: Dict[str, Any]) -> bool:
    """Make promotion_decision, publish_contract_trace, and publish_ledger agree."""
    if not isinstance(result_dict, dict):
        return False
    identity = result_dict.get("identity")
    if not isinstance(identity, dict):
        return False
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}

    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    trace = identity.get("publish_contract_trace")
    if not isinstance(trace, dict):
        trace = ledger.get("publish_contract_trace")
    publish_ledger = identity.get("publish_ledger")
    if not isinstance(publish_ledger, dict):
        publish_ledger = ledger.get("publish_ledger")
    if not isinstance(decision, dict) and isinstance(trace, dict):
        trace_decision = trace.get("gate_decision")
        if isinstance(trace_decision, dict):
            decision = trace_decision
    if not isinstance(decision, dict) or not isinstance(trace, dict):
        return False

    changed = False
    gate_decision = dict(decision)
    gate_decision["bypassed_gate"] = False
    publish_allowed = gate_decision.get("publish_allowed") is True

    converged_trace = dict(trace)
    post_gate_identity = converged_trace.get("post_gate_identity")
    if not isinstance(post_gate_identity, dict):
        post_gate_identity = {}
    else:
        post_gate_identity = dict(post_gate_identity)
    if publish_allowed:
        post_gate_identity["official_title"] = gate_decision.get("official_title")
        post_gate_identity["official_url"] = gate_decision.get("official_url")
    else:
        post_gate_identity["official_title"] = None
        post_gate_identity["official_url"] = None
    post_gate_identity["title_resolution_allowed"] = identity.get("title_resolution_allowed")
    post_gate_identity["title_resolution_state"] = identity.get("title_resolution_state")
    post_gate_identity["work_resolution"] = identity.get("work_resolution")
    post_gate_identity["candidate_ledger_status"] = identity.get("candidate_ledger_status")
    converged_trace["gate_decision"] = gate_decision
    converged_trace["post_gate_identity"] = post_gate_identity
    converged_trace["bypassed_gate"] = False
    reason_codes = gate_decision.get("reason_codes")
    if isinstance(reason_codes, list):
        converged_trace["reason_codes"] = [str(code) for code in reason_codes if str(code).strip()]

    converged_ledger = dict(publish_ledger) if isinstance(publish_ledger, dict) else {}
    converged_ledger["candidate_preservation"] = converged_trace.get("pre_gate_candidate")
    converged_ledger["public_publish"] = post_gate_identity
    converged_ledger["gate_decision"] = gate_decision

    if identity.get("promotion_decision") != gate_decision:
        identity["promotion_decision"] = gate_decision
        changed = True
    if identity.get("publish_contract_trace") != converged_trace:
        identity["publish_contract_trace"] = converged_trace
        changed = True
    if identity.get("publish_ledger") != converged_ledger:
        identity["publish_ledger"] = converged_ledger
        changed = True
    if ledger.get("promotion_decision") != gate_decision:
        ledger["promotion_decision"] = gate_decision
        changed = True
    if ledger.get("publish_contract_trace") != converged_trace:
        ledger["publish_contract_trace"] = converged_trace
        changed = True
    if ledger.get("publish_ledger") != converged_ledger:
        ledger["publish_ledger"] = converged_ledger
        changed = True
    if changed or ledger:
        identity["candidate_ledger"] = ledger
    return changed


def _demote_platform_meta_image_title_publication_contract(
    result_dict: Dict[str, Any],
    post_title: Optional[str] = None,
) -> bool:
    """Demote platform-meta public titles backed only by non-promotable image OCR."""
    if not isinstance(result_dict, dict):
        return False
    identity = result_dict.get("identity")
    if not isinstance(identity, dict):
        return False
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}

    def _title_key(value: Any) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).lower()

    def _list_texts(*values: Any) -> List[str]:
        out: List[str] = []
        for value in values:
            if isinstance(value, list):
                out.extend(str(item or "").strip() for item in value if str(item or "").strip())
            elif isinstance(value, str) and value.strip():
                out.append(value.strip())
        return out

    novel = identity.get("novel_identity")
    if not isinstance(novel, dict):
        novel = {}
    public_title = str(
        identity.get("official_title")
        or identity.get("official_novel_title")
        or identity.get("resolved_title")
        or novel.get("official_title")
        or novel.get("official_novel_title")
        or ""
    ).strip()
    if not public_title:
        return False
    public_title_key = _title_key(public_title)
    if not public_title_key:
        return False
    public_url = str(
        identity.get("heretic_url")
        or identity.get("official_url")
        or identity.get("resolved_url")
        or novel.get("heretic_url")
        or novel.get("official_url")
        or ""
    ).strip()

    flags = _list_texts(
        identity.get("consistency_flags"),
        identity.get("promotion_blocked_reasons"),
        identity.get("candidate_audit_lint"),
        identity.get("output_consistency_lint"),
        ledger.get("consistency_flags"),
        ledger.get("promotion_blocked_reasons"),
    )
    platform_meta = "platform_meta_multi_title_blocked" in flags
    if not platform_meta:
        raw_post_title = str(post_title or result_dict.get("title") or identity.get("post_title") or "").strip()
        norm_post_title = _title_key(raw_post_title)
        platform_terms = ("문피아", "노벨피아", "노피아", "카카오페이지", "카카페", "시리즈")
        feature_terms = ("수정", "삭제", "내리", "내려", "콘", "이모티콘", "스티커", "뱃지", "표지")
        platform_meta = bool(
            any(_title_key(term) in norm_post_title for term in platform_terms)
            and any(_title_key(term) in norm_post_title for term in feature_terms)
        )
    if not platform_meta:
        return False

    image_items: List[Dict[str, Any]] = []
    for container in (identity, ledger):
        for key in ("image_evidence_catalog", "image_enrichment"):
            values = container.get(key) if isinstance(container, dict) else None
            if isinstance(values, list):
                image_items.extend(item for item in values if isinstance(item, dict))

    non_promotable_image = False
    for item in image_items:
        item_title_key = _title_key(item.get("explicit_work_title"))
        ocr_key = _title_key(item.get("ocr_text"))
        if item_title_key != public_title_key and public_title_key not in ocr_key:
            continue
        evidence_type = str(item.get("evidence_type") or "").strip().lower()
        focus_role = str(item.get("focus_role") or "").strip().lower()
        cover_work_anchor = bool(evidence_type == "cover_title" and focus_role == "work_anchor")
        if item.get("promotion_eligible") is True or cover_work_anchor:
            continue
        non_promotable_image = True
        break
    if not non_promotable_image:
        return False

    changed = False
    reason_code = "platform_meta_image_title_hard_hold"
    reason_codes = []
    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    if isinstance(decision, dict) and isinstance(decision.get("reason_codes"), list):
        reason_codes.extend(str(code) for code in decision.get("reason_codes") if str(code).strip())
    reason_codes = list(dict.fromkeys([*reason_codes, reason_code, "scope_context_only", "serialized_public_identity_scrubbed"]))

    demoted_decision = dict(decision) if isinstance(decision, dict) else {}
    demoted_decision.update(
        {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": reason_codes,
            "bypassed_gate": False,
            "scope": {
                "scope_kind": "context_only",
                "confidence": "high",
                "conflict_reason_codes": [reason_code],
            },
        }
    )

    for key, value in (
        ("candidate_ledger_status", "promotion_blocked"),
        ("title_resolution_allowed", False),
        ("is_resolved_work_discussion", False),
        ("promotion_blocked", True),
        ("safe_resolved", False),
        ("blocked_official_title", public_title),
        ("blocked_official_title_url", public_url or None),
    ):
        if identity.get(key) != value:
            identity[key] = value
            changed = True
    if isinstance(novel, dict):
        if novel.get("official_title") is not None:
            novel["official_title"] = None
            changed = True
        if novel.get("heretic_url") is not None:
            novel["heretic_url"] = None
            changed = True
        identity["novel_identity"] = novel

    blocked_reasons = _list_texts(identity.get("promotion_blocked_reasons"))
    if reason_code not in blocked_reasons:
        blocked_reasons.append(reason_code)
        identity["promotion_blocked_reasons"] = blocked_reasons
        changed = True
    if identity.get("promotion_decision") != demoted_decision:
        identity["promotion_decision"] = demoted_decision
        changed = True

    trace = identity.get("publish_contract_trace")
    if not isinstance(trace, dict):
        trace = ledger.get("publish_contract_trace") if isinstance(ledger, dict) else {}
    trace = dict(trace) if isinstance(trace, dict) else {}
    pre_gate = trace.get("pre_gate_candidate")
    if not isinstance(pre_gate, dict):
        pre_gate = {
            "official_title": public_title,
            "official_url": public_url or None,
            "source": "platform_meta_image_title_hard_hold",
        }
    trace.update(
        {
            "pre_gate_candidate": pre_gate,
            "gate_decision": demoted_decision,
            "scope_state": demoted_decision["scope"],
            "post_gate_identity": {
                "official_title": None,
                "official_url": None,
                "title_resolution_allowed": False,
                "title_resolution_state": identity.get("title_resolution_state"),
                "work_resolution": identity.get("work_resolution"),
                "candidate_ledger_status": "promotion_blocked",
            },
            "reason_codes": reason_codes,
            "bypassed_gate": False,
        }
    )
    publish_ledger = {
        "candidate_preservation": pre_gate,
        "public_publish": trace["post_gate_identity"],
        "gate_decision": demoted_decision,
    }
    if identity.get("publish_contract_trace") != trace:
        identity["publish_contract_trace"] = trace
        changed = True
    if identity.get("publish_ledger") != publish_ledger:
        identity["publish_ledger"] = publish_ledger
        changed = True

    ledger["pipeline_official_title"] = public_title
    ledger["blocked_official_title"] = public_title
    ledger["blocked_official_title_url"] = public_url or None
    ledger["candidate_ledger_status"] = "promotion_blocked"
    ledger["title_resolution_allowed"] = False
    ledger["promotion_decision"] = demoted_decision
    ledger["publish_contract_trace"] = trace
    ledger["publish_ledger"] = publish_ledger
    if identity.get("candidate_ledger") != ledger:
        identity["candidate_ledger"] = ledger
        changed = True
    return changed


def _scrub_promotion_blocked_result_contract(result_dict: Dict[str, Any], post_title: Optional[str] = None) -> bool:
    """Keep serialized output consistent when candidate audit demotes a title."""
    if not isinstance(result_dict, dict):
        return False
    identity = result_dict.get("identity")
    if not isinstance(identity, dict):
        return False

    status = str(identity.get("candidate_ledger_status") or "")
    title_allowed = identity.get("title_resolution_allowed")

    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    promotion_decision = identity.get("promotion_decision")
    if not isinstance(promotion_decision, dict):
        promotion_decision = ledger.get("promotion_decision")
    promotion_gate_state = identity.get("promotion_gate_state")
    if not isinstance(promotion_gate_state, dict):
        promotion_gate_state = ledger.get("promotion_gate_state")
    promotion_gate_blocked = (
        isinstance(promotion_decision, dict)
        and promotion_decision.get("publish_allowed") is False
    )

    novel_identity = identity.get("novel_identity")
    nested_title = ""
    nested_url = ""
    if isinstance(novel_identity, dict):
        nested_title = str(
            novel_identity.get("official_title")
            or novel_identity.get("official_novel_title")
            or novel_identity.get("resolved_title")
            or ""
        ).strip()
        nested_url = str(
            novel_identity.get("heretic_url")
            or novel_identity.get("official_url")
            or novel_identity.get("url")
            or ""
        ).strip()

    def _candidate_title_url(item: Any) -> tuple[str, str]:
        if isinstance(item, dict):
            return (
                str(
                    item.get("official_title")
                    or item.get("official_novel_title")
                    or item.get("resolved_title")
                    or item.get("title")
                    or ""
                ).strip(),
                str(
                    item.get("heretic_url")
                    or item.get("official_url")
                    or item.get("resolved_url")
                    or item.get("url")
                    or ""
                ).strip(),
            )
        if isinstance(item, str):
            return item.strip(), ""
        return "", ""

    def _title_key(title: Any) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(title or "")).lower()

    def _source_post_title() -> str:
        for value in (
            post_title,
            result_dict.get("title"),
            result_dict.get("post_title"),
            result_dict.get("source_title"),
            identity.get("post_title"),
            identity.get("source_title"),
            ledger.get("post_title"),
            ledger.get("source_title"),
        ):
            value = str(value or "").strip()
            if value:
                return value
        for container in (
            result_dict.get("post_metadata"),
            result_dict.get("source_metadata"),
            result_dict.get("input_post"),
            result_dict.get("post"),
        ):
            if not isinstance(container, dict):
                continue
            for key in ("title", "post_title", "source_title", "raw_title"):
                value = str(container.get(key) or "").strip()
                if value:
                    return value
        return ""

    def _reviewable_conflict_candidate(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        if str(item.get("heretic_url") or item.get("official_url") or item.get("url") or "").strip():
            return True
        source_tier = str(item.get("source_tier") or "").strip().lower()
        if source_tier in {"official_detail", "mixed", "search_result", "official"}:
            return True
        page_type = str(item.get("page_type") or "").strip().lower()
        return page_type in {"novel_page", "work_detail"}

    def _competing_candidate_titles(public_title: str) -> List[str]:
        public_key = _title_key(public_title)
        if not public_key:
            return []
        competing: List[str] = []
        seen = set()
        for source_items in (
            ledger.get("candidate_preservation_sources") or [],
            identity.get("candidate_preservation_sources") or [],
            ledger.get("title_candidates") or [],
            identity.get("title_candidates") or [],
        ):
            if not isinstance(source_items, list):
                continue
            for item in source_items:
                candidate_title, _candidate_url = _candidate_title_url(item)
                candidate_key = _title_key(candidate_title)
                if not candidate_key or candidate_key == public_key:
                    continue
                if isinstance(item, dict) and not _reviewable_conflict_candidate(item):
                    continue
                if not isinstance(item, dict):
                    continue
                if candidate_key in seen:
                    continue
                seen.add(candidate_key)
                competing.append(candidate_title)
        return competing

    def _blocked_candidate_source_items() -> List[Any]:
        items: List[Any] = []
        for source_items in (
            ledger.get("candidate_preservation_sources") or [],
            identity.get("candidate_preservation_sources") or [],
            ledger.get("title_candidates") or [],
            identity.get("title_candidates") or [],
        ):
            if isinstance(source_items, list):
                items.extend(source_items)
        return items

    def _source_lists_have_text(*values: Any) -> bool:
        for value in values:
            if isinstance(value, str) and value.strip():
                return True
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        return True
                    if isinstance(item, dict) and any(
                        str(item.get(key) or "").strip()
                        for key in ("text", "content", "body", "comment")
                    ):
                        return True
        return False

    def _official_detail_url(value: Any) -> str:
        url = str(value or "").strip()
        lowered = url.lower()
        if not url:
            return ""
        if "novelpia.com/novel/" in lowered:
            return url
        if "series.naver.com/novel/detail.series" in lowered:
            return url
        if "page.kakao.com/content/" in lowered:
            return url
        if "novel.munpia.com/" in lowered:
            return url
        return ""

    def _search_evidence_items() -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for source in (identity, ledger):
            if not isinstance(source, dict):
                continue
            for key in ("search_evidence_catalog", "search_results", "web_search_results"):
                values = source.get(key)
                if isinstance(values, list):
                    items.extend(item for item in values if isinstance(item, dict))
        return items

    def _official_detail_url_from_search_evidence(candidate_title: str) -> str:
        candidate_key = _title_key(candidate_title)
        if not candidate_key:
            return ""
        for item in _search_evidence_items():
            url = _official_detail_url(item.get("url"))
            if not url:
                continue
            item_title = str(item.get("title") or item.get("official_title") or "").strip()
            item_snippet = str(item.get("snippet") or item.get("content") or "").strip()
            title_key = _title_key(item_title)
            snippet_key = _title_key(item_snippet)
            title_matches = bool(
                title_key
                and (
                    title_key == candidate_key
                    or candidate_key in title_key
                    or title_key in candidate_key
                )
            )
            snippet_matches = bool(candidate_key and candidate_key in snippet_key)
            if title_matches or snippet_matches:
                return url
        return ""

    def _remove_negative_evidence(item: Dict[str, Any], *codes: str) -> bool:
        values = item.get("negative_evidence")
        if not isinstance(values, list):
            return False
        remove_set = {str(code) for code in codes}
        cleaned = [value for value in values if str(value) not in remove_set]
        if cleaned == values:
            return False
        item["negative_evidence"] = cleaned or None
        return True

    def _repair_blocked_candidate_official_detail_url(candidate_title: str, candidate_url: str) -> bool:
        if not candidate_title or not candidate_url:
            return False
        candidate_key = _title_key(candidate_title)
        changed_local = False
        containers: List[Any] = [
            identity.get("title_candidates"),
            identity.get("secondary_reference_works"),
            identity.get("candidate_preservation_sources"),
            ledger.get("title_candidates"),
            ledger.get("candidate_preservation_sources"),
        ]
        analysis = result_dict.get("analysis")
        if isinstance(analysis, dict):
            containers.append(analysis.get("detected_titles"))
        for values in containers:
            if not isinstance(values, list):
                continue
            for item in values:
                if not isinstance(item, dict):
                    continue
                item_title, item_url = _candidate_title_url(item)
                if _title_key(item_title) != candidate_key:
                    continue
                if not item_url:
                    item["heretic_url"] = candidate_url
                    changed_local = True
                source_tier = str(item.get("source_tier") or "").strip().lower()
                if source_tier in {"", "community", "web", "search_result"}:
                    item["source_tier"] = "official_detail"
                    changed_local = True
                if str(item.get("page_type") or "").strip().lower() not in {"novel_page", "work_detail"}:
                    item["page_type"] = "novel_page"
                    changed_local = True
                if _remove_negative_evidence(
                    item,
                    "missing_official_url_for_official_detail",
                    "url_is_community_post",
                    "url_is_listing",
                    "listing_only",
                ):
                    changed_local = True
        return changed_local

    def _candidate_alias_keys(candidate_title: str, candidate_url: str) -> List[str]:
        candidate_key = _title_key(candidate_title)
        candidate_url = str(candidate_url or "").strip()
        aliases: List[str] = []
        source_lists = (
            [identity.get("primary_work")],
            identity.get("title_candidates") or [],
            identity.get("candidate_preservation_sources") or [],
            ledger.get("title_candidates") or [],
            ledger.get("candidate_preservation_sources") or [],
        )
        analysis = result_dict.get("analysis")
        if isinstance(analysis, dict):
            source_lists = (*source_lists, analysis.get("detected_titles") or [])
        for source_items in source_lists:
            if not isinstance(source_items, list):
                continue
            for item in source_items:
                if not isinstance(item, dict):
                    continue
                item_title, item_url = _candidate_title_url(item)
                item_key = _title_key(item_title)
                if item_key and candidate_key and item_key != candidate_key:
                    if not (candidate_url and item_url and item_url == candidate_url):
                        continue
                alias_text = str(
                    item.get("alias_or_mention")
                    or item.get("matched_alias")
                    or item.get("anchor_text")
                    or ""
                ).strip()
                alias_key = _title_key(alias_text)
                if alias_key and alias_key not in aliases:
                    aliases.append(alias_key)
        return aliases

    def _title_led_consumption_marker(text: str) -> bool:
        return bool(
            re.search(
                r"(?:볼\s*만(?:하|한|함|했)|재(?:밌|밋|미있|미잇)[가-힣]*|재미(?:있|잇)[가-힣]*)",
                str(text or ""),
            )
        )

    def _candidate_trace_score(candidate_title: str, candidate_url: str, item: Any = None) -> int:
        if not candidate_title:
            return -10_000
        score = 0
        if _official_detail_url(candidate_url):
            score += 80
        if isinstance(item, dict):
            source_tier = str(item.get("source_tier") or "").strip().lower()
            if source_tier in {"official_detail", "novel_platform", "official"}:
                score += 60
            elif source_tier in {"search_result", "mixed"}:
                score += 45
            elif source_tier == "community":
                score += 10
            elif source_tier == "comment_surface":
                score -= 70
            page_type = str(item.get("page_type") or "").strip().lower()
            if page_type in {"novel_page", "work_detail"}:
                score += 30
            reference_role = str(item.get("reference_role") or "").strip().lower()
            if reference_role == "primary":
                score += 25
            elif reference_role in {"mentioned", "candidate"}:
                score += 5
            confidence = str(item.get("confidence") or "").strip().lower()
            if confidence == "high":
                score += 15
            elif confidence == "medium":
                score += 5
            elif confidence == "low":
                score -= 10
            if str(item.get("promotion_policy") or "").strip().lower() == "hold_without_promotion":
                score -= 20
            negative_evidence = item.get("negative_evidence")
            if isinstance(negative_evidence, list) and "missing_official_url_for_official_detail" in {
                str(value) for value in negative_evidence
            }:
                score -= 10
        return score

    def _preferred_blocked_candidate_for_trace(current_title: str, current_url: str) -> tuple[str, str]:
        current_title = str(current_title or "").strip()
        current_url = str(current_url or "").strip()
        current_key = _title_key(current_title)
        current_score = _candidate_trace_score(current_title, current_url)
        best_title = current_title
        best_url = current_url
        best_score = current_score
        same_title_url_upgrade = False
        source_lists = (
            ledger.get("candidate_preservation_sources") or [],
            identity.get("candidate_preservation_sources") or [],
            ledger.get("title_candidates") or [],
            identity.get("title_candidates") or [],
            [identity.get("primary_work")],
        )
        for source_items in source_lists:
            if not isinstance(source_items, list):
                continue
            for item in source_items:
                candidate_title, candidate_url = _candidate_title_url(item)
                candidate_key = _title_key(candidate_title)
                if not candidate_key:
                    continue
                score = _candidate_trace_score(candidate_title, candidate_url, item)
                if current_key and candidate_key == current_key:
                    current_score = max(current_score, score)
                    if candidate_url and not current_url:
                        best_title, best_url, best_score = candidate_title, candidate_url, max(best_score, score)
                        same_title_url_upgrade = True
                    continue
                if score > best_score:
                    best_title, best_url, best_score = candidate_title, candidate_url, score
        if same_title_url_upgrade:
            return best_title, best_url
        if best_score >= max(current_score + 10, 5):
            return best_title, best_url
        return current_title, current_url

    def _infer_blocked_candidate_scope(candidate_title: str) -> Dict[str, Any]:
        candidate_key = _title_key(candidate_title)
        if not candidate_key:
            return {}

        contexts = {
            str(value or "").strip().lower()
            for source in (identity.get("context_sources"), ledger.get("context_sources"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }
        flags = {
            str(value or "").strip().lower()
            for source in (identity.get("consistency_flags"), ledger.get("consistency_flags"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }
        image_catalog = [
            item
            for source in (identity.get("image_evidence_catalog"), ledger.get("image_evidence_catalog"))
            if isinstance(source, list)
            for item in source
            if isinstance(item, dict)
        ]
        image_count = result_dict.get("image_count")
        has_image_context = bool(image_catalog) or "image" in contexts or bool(image_count)
        promotion_eligible_images = [
            item for item in image_catalog if item.get("promotion_eligible") is True
        ]
        image_title_anchor = False
        for item in image_catalog:
            role = str(item.get("title_role") or "").strip().lower()
            evidence_type = str(item.get("evidence_type") or "").strip().lower()
            if role in {"title", "cover_title", "explicit_title", "work_title"}:
                image_title_anchor = True
            if evidence_type in {"ocr_title", "explicit_title", "work_title"}:
                image_title_anchor = True
            if str(item.get("explicit_work_title") or item.get("official_title") or "").strip():
                image_title_anchor = True
        nonpromotable_image_context = bool(
            has_image_context and not promotion_eligible_images and not image_title_anchor
        )

        source_items = _blocked_candidate_source_items()
        has_official_candidate = False
        has_hold_candidate = False
        for item in source_items:
            item_title, item_url = _candidate_title_url(item)
            item_key = _title_key(item_title)
            if item_key and item_key != candidate_key:
                continue
            if isinstance(item, dict):
                source_tier = str(item.get("source_tier") or "").strip().lower()
                if source_tier in {"official_detail", "novel_platform", "official", "search_result"} or item_url:
                    has_official_candidate = True
                if str(item.get("promotion_policy") or "").strip().lower() == "hold_without_promotion":
                    has_hold_candidate = True
            elif item_title:
                has_hold_candidate = True

        post_title_terms = [
            _title_key(term)
            for term in re.findall(r"[0-9A-Za-z가-힣]{2,}", str(result_dict.get("title") or ""))
        ]
        title_alias_bridge = any(
            len(term) >= 4 and (term in candidate_key or candidate_key in term)
            for term in post_title_terms
        )
        anchor_type = str(identity.get("anchor_type") or ledger.get("anchor_type") or "").strip().lower()
        text_bridge_present = _source_lists_have_text(
            result_dict.get("content"),
            result_dict.get("comments"),
            result_dict.get("comment_context_lines"),
            result_dict.get("comment_dialogue_context_lines"),
        )
        nonwork_or_noise = bool(
            str(identity.get("discussion_type") or "").strip().lower() in {"noise", "other"}
            or str(identity.get("topicality") or "").strip().lower() in {"unrelated", "off_topic"}
            or "batch_memory_alias_rescue_blocked_nonwork_context" in flags
            or "batch_memory_alias_rescue_blocked_genre_context" in flags
        )
        lacks_direct_work_anchor = anchor_type in {"", "none", "unknown"}

        if not (
            (has_official_candidate or has_hold_candidate)
            and (title_alias_bridge or "title" in contexts)
            and nonpromotable_image_context
        ):
            return {}

        direct_sources: List[str] = []
        if title_alias_bridge:
            direct_sources.append("post_title_alias")
        if has_official_candidate:
            direct_sources.append("official_detail_candidate")
        if nonpromotable_image_context:
            direct_sources.append("image_ocr_nonpromotable")
        if not text_bridge_present:
            direct_sources.append("no_body_or_comment_work_bridge")
        if lacks_direct_work_anchor:
            direct_sources.append("anchor_type_none")

        conflict_codes: List[str] = [
            "blocked_candidate_scope_inferred_from_final_contract",
            "exact_alias_candidate_preserved_without_work_discussion",
        ]
        if nonpromotable_image_context:
            conflict_codes.append("image_ocr_without_title_anchor")
        if nonwork_or_noise:
            conflict_codes.append("nonwork_or_noise_context")
        if not text_bridge_present:
            conflict_codes.append("body_comments_absent_or_empty")

        return {
            "scope_kind": "context_only",
            "confidence": "medium",
            "direct_bridge_sources": list(dict.fromkeys(direct_sources)),
            "conflict_reason_codes": list(dict.fromkeys(conflict_codes)),
        }

    def _infer_blocked_candidate_current_work_scope(candidate_title: str) -> Dict[str, Any]:
        official_url = _official_detail_url_from_search_evidence(candidate_title)
        if not official_url:
            return {}
        contexts = {
            str(value or "").strip().lower()
            for source in (identity.get("context_sources"), ledger.get("context_sources"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }
        flags = {
            str(value or "").strip().lower()
            for source in (identity.get("consistency_flags"), ledger.get("consistency_flags"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }
        hard_negative_flags = {
            "recommendation_context_only_no_work_anchor",
            "recommendation_context_only_public_title_conflict",
            "batch_memory_alias_rescue_blocked_nonwork_context",
            "batch_memory_alias_rescue_blocked_genre_context",
            "unresolved_worklike_hold:alias_character_discussion",
        }
        if flags & hard_negative_flags:
            return {}
        if str(identity.get("discussion_type") or "").strip().lower() in {"noise", "other"}:
            return {}
        if str(identity.get("topicality") or "").strip().lower() in {"unrelated", "off_topic"}:
            return {}
        if "search" not in contexts:
            return {}
        if not ({"title", "body", "comments"} & contexts):
            return {}
        anchor_type = str(identity.get("anchor_type") or ledger.get("anchor_type") or "").strip().lower()
        direct_sources = ["search_evidence_catalog", "official_detail_url"]
        for source_name in ("title", "body", "comments", "search"):
            if source_name in contexts:
                direct_sources.append(source_name)
        if anchor_type:
            direct_sources.append(f"anchor_type:{anchor_type}")
        return {
            "scope_kind": "current_work",
            "confidence": "high",
            "direct_bridge_sources": list(dict.fromkeys(direct_sources)),
            "conflict_reason_codes": [
                "blocked_candidate_scope_inferred_from_search_evidence",
                "official_detail_url_recovered_from_search_evidence",
                "character_bridge_variance_hold",
            ],
        }

    public_title = str(
        identity.get("official_title")
        or identity.get("official_novel_title")
        or identity.get("resolved_title")
        or nested_title
        or ""
    ).strip()
    public_url = str(
        identity.get("heretic_url")
        or identity.get("official_url")
        or identity.get("resolved_url")
        or nested_url
        or ""
    ).strip()
    existing_trace = identity.get("publish_contract_trace")
    if not isinstance(existing_trace, dict):
        existing_trace = ledger.get("publish_contract_trace")
    competing_public_candidates = _competing_candidate_titles(public_title)
    untraced_public_conflict = bool(
        public_title
        and status == "safe_resolved"
        and not isinstance(promotion_decision, dict)
        and not isinstance(existing_trace, dict)
        and competing_public_candidates
    )
    changed = False
    if untraced_public_conflict:
        status = "promotion_blocked"
        if identity.get("candidate_ledger_status") != status:
            identity["candidate_ledger_status"] = status
            changed = True
        promotion_decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": [
                "final_publication_missing_promotion_gate_decision",
                "untraced_public_title_with_competing_candidate",
                "scope_unknown",
                "scope_not_current_work",
            ],
            "bypassed_gate": False,
        }
        promotion_gate_state = {
            "scope": {
                "scope_kind": "unknown",
                "confidence": "low",
                "competing_candidates": competing_public_candidates,
                "conflict_reason_codes": [
                    "final_publication_missing_promotion_gate_decision",
                    "untraced_public_title_with_competing_candidate",
                ],
            }
        }
        ledger["promotion_decision"] = promotion_decision
        ledger["promotion_gate_state"] = promotion_gate_state
        identity["candidate_ledger"] = ledger
        promotion_gate_blocked = True

    if status != "promotion_blocked" and title_allowed is not False and not promotion_gate_blocked:
        return False

    blocked_title = str(
        ledger.get("blocked_official_title")
        or identity.get("blocked_official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
        or nested_title
        or ""
    ).strip()
    blocked_url = str(
        ledger.get("blocked_official_title_url")
        or identity.get("blocked_official_title_url")
        or identity.get("heretic_url")
        or identity.get("official_url")
        or nested_url
        or ""
    ).strip()

    if not blocked_title:
        candidate_sources = (
            identity.get("title_candidates") or [],
            ledger.get("candidate_preservation_sources") or [],
            ledger.get("title_candidates") or [],
        )
        for source_items in candidate_sources:
            for item in source_items:
                candidate_title, candidate_url = _candidate_title_url(item)
                if candidate_title:
                    blocked_title = candidate_title
                    if candidate_url:
                        blocked_url = candidate_url
                    break
            if blocked_title:
                break

    preferred_title, preferred_url = _preferred_blocked_candidate_for_trace(blocked_title, blocked_url)
    if preferred_title and (preferred_title != blocked_title or preferred_url != blocked_url):
        blocked_title = preferred_title
        blocked_url = preferred_url
        changed = True

    if not blocked_title:
        primary_work = identity.get("primary_work")
        if isinstance(primary_work, dict):
            blocked_title = str(
                primary_work.get("official_title")
                or primary_work.get("title")
                or ""
            ).strip()
            blocked_url = str(
                primary_work.get("heretic_url")
                or primary_work.get("url")
                or blocked_url
                or ""
            ).strip()

    if blocked_title and not blocked_url:
        recovered_blocked_url = _official_detail_url_from_search_evidence(blocked_title)
        if recovered_blocked_url:
            blocked_url = recovered_blocked_url
            changed = True
    if blocked_title and blocked_url:
        if _repair_blocked_candidate_official_detail_url(blocked_title, blocked_url):
            changed = True

    def _candidate_has_official_title_support(candidate_title: str, candidate_url: str = "") -> bool:
        candidate_key = _title_key(candidate_title)
        candidate_url_key = _publication_url_key(candidate_url)
        if not candidate_key:
            return False
        for item in _search_evidence_items():
            title_text = str(item.get("title") or item.get("official_title") or "").strip()
            snippet_text = str(item.get("snippet") or item.get("content") or "").strip()
            if _publication_near_title_match(title_text, candidate_title) or (
                candidate_key and candidate_key in _title_key(snippet_text)
            ):
                return True
        for item in _blocked_candidate_source_items():
            if not isinstance(item, dict):
                continue
            item_title, item_url = _candidate_title_url(item)
            item_title_key = _title_key(item_title)
            if item_title_key != candidate_key and (
                not candidate_url_key or _publication_url_key(item_url) != candidate_url_key
            ):
                continue
            source_tier = str(item.get("source_tier") or "").strip().lower()
            page_type = str(item.get("page_type") or "").strip().lower()
            if source_tier in {"official_detail", "novel_platform", "official", "search_result", "wiki", "mixed"}:
                return True
            if page_type in {"novel_page", "work_detail"}:
                return True
        return False

    def _has_distinct_alias_bridge_for_title_only(candidate_title: str) -> bool:
        candidate_key = _title_key(candidate_title)
        if not candidate_key:
            return False
        for item in _blocked_candidate_source_items():
            if not isinstance(item, dict):
                continue
            item_title, _ = _candidate_title_url(item)
            if _title_key(item_title) != candidate_key:
                continue
            alias_key = _title_key(item.get("alias_or_mention") or item.get("alias") or item.get("surface"))
            if alias_key and alias_key != candidate_key:
                return True
            for field in ("resolved_recall_anchor", "known_abbreviation", "known_alias", "curated_alias"):
                if item.get(field) is True:
                    return True
        return False

    def _restore_blocked_verified_alias_title_only(candidate_title: str, candidate_url: str) -> bool:
        candidate_title = str(candidate_title or "").strip()
        candidate_url = _official_detail_url(candidate_url)
        if not candidate_title:
            return False

        contexts = {
            str(value or "").strip().lower()
            for source in (identity.get("context_sources"), ledger.get("context_sources"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }
        flags = {
            str(value or "").strip()
            for source in (identity.get("consistency_flags"), ledger.get("consistency_flags"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }
        hard_negative_flags = {
            "recommendation_context_only_no_work_anchor",
            "recommendation_context_only_public_title_conflict",
            "batch_memory_alias_rescue_blocked_nonwork_context",
            "batch_memory_alias_rescue_blocked_genre_context",
            "semantic_seed_no_work_context",
            "unresolved_worklike_hold:alias_character_discussion",
            "inferred_publication_sentence_like_alias_overreach",
        }
        if flags & hard_negative_flags:
            return False
        if "title" not in contexts or "search" not in contexts or not (contexts & {"body", "comments"}):
            return False

        anchor_type = str(identity.get("anchor_type") or ledger.get("anchor_type") or "").strip().lower()
        if anchor_type not in {"title_exact", "title_alias", "full_title_surface", "character_mention"}:
            return False
        if str(identity.get("discussion_type") or "").strip().lower() in {"noise", "other", "off_topic"}:
            return False
        if str(identity.get("topicality") or "").strip().lower() in {"unrelated", "off_topic"}:
            return False
        if _publication_sentence_like_alias_overreach(identity, candidate_title):
            return False
        if not _has_distinct_alias_bridge_for_title_only(candidate_title):
            return False
        if not _publication_has_direct_source_support(
            result_dict,
            identity,
            ledger,
            candidate_title,
            candidate_url,
            post_title=_source_post_title(),
        ):
            return False
        if not _candidate_has_official_title_support(candidate_title, candidate_url):
            return False

        changed_local = False
        scope_state = {
            "scope_kind": "current_work",
            "confidence": "high",
            "direct_bridge_sources": list(
                dict.fromkeys(
                    [
                        "verified_alias_title_only_publication",
                        "post_title_alias",
                        "title",
                        "search",
                        *(source for source in ("body", "comments") if source in contexts),
                    ]
                )
            ),
            "conflict_reason_codes": [
                "official_url_withheld_by_title_mismatch",
                "verified_alias_title_only_publication",
            ],
        }
        gate_decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": candidate_title,
            "official_url": None,
            "candidate_preserved": False,
            "reason_codes": [
                "official_title_exists",
                "row_discusses_work_as_work",
                "scope_current_work",
                "verified_alias_title_only_publication",
                "official_url_withheld_by_title_mismatch",
                "serialized_public_identity_shared_gate_restored",
            ],
            "bypassed_gate": False,
            "scope": scope_state,
        }
        gate_state_payload = {
            "candidate_title": candidate_title,
            "candidate_url": None,
            "official_title_exists": True,
            "row_discusses_work_as_work": True,
            "scope": scope_state,
        }

        novel = identity.get("novel_identity")
        if not isinstance(novel, dict):
            novel = {}
        if novel.get("official_title") != candidate_title:
            novel["official_title"] = candidate_title
            changed_local = True
        if novel.get("heretic_url") is not None:
            novel["heretic_url"] = None
            changed_local = True
        if novel.get("confidence") in {None, "", "None"}:
            novel["confidence"] = "High"
            changed_local = True
        identity["novel_identity"] = novel

        for key, value in (
            ("candidate_ledger_status", "safe_resolved"),
            ("title_resolution_allowed", True),
            ("title_resolution_state", "resolved"),
            ("work_resolution", "resolved"),
            ("is_resolved_work_discussion", True),
            ("promotion_blocked", False),
            ("safe_resolved", True),
            ("promotion_decision", gate_decision),
            ("promotion_gate_state", gate_state_payload),
        ):
            if identity.get(key) != value:
                identity[key] = value
                changed_local = True
        for key in ("blocked_official_title", "blocked_official_title_url", "promotion_blocked_reasons"):
            value = [] if key == "promotion_blocked_reasons" else None
            if identity.get(key) != value:
                identity[key] = value
                changed_local = True

        cleaned_flags = [
            str(value)
            for value in (identity.get("consistency_flags") or [])
            if str(value)
            not in {
                "weak_alias_surface_public_title_bridge",
                "external_ip_unresolved_hold_blocked",
                "external_ip_unresolved_final_blocked",
            }
        ]
        for value in (
            "verified_alias_title_only_publication",
            "serialized_public_identity_shared_gate_restored",
        ):
            if value not in cleaned_flags:
                cleaned_flags.append(value)
        if identity.get("consistency_flags") != cleaned_flags:
            identity["consistency_flags"] = cleaned_flags
            changed_local = True

        primary_work = identity.get("primary_work")
        if not isinstance(primary_work, dict):
            primary_work = {}
        primary_work.update(
            {
                "official_title": candidate_title,
                "heretic_url": None,
                "confidence": primary_work.get("confidence") or "High",
                "source_tier": primary_work.get("source_tier") or "official_detail",
                "page_type": primary_work.get("page_type") or "novel_page",
                "reference_role": "primary",
            }
        )
        for key in ("promotion_policy", "blocked_by_candidate_audit"):
            primary_work.pop(key, None)
        _remove_negative_evidence(primary_work, "weak_alias_surface_public_title_bridge")
        identity["primary_work"] = primary_work

        for source_items in (
            identity.get("title_candidates"),
            identity.get("candidate_preservation_sources"),
            ledger.get("title_candidates"),
            ledger.get("candidate_preservation_sources"),
        ):
            if not isinstance(source_items, list):
                continue
            for item in source_items:
                if not isinstance(item, dict):
                    continue
                item_title, item_url = _candidate_title_url(item)
                if _title_key(item_title) != _title_key(candidate_title) and (
                    not candidate_url or item_url != candidate_url
                ):
                    continue
                item["official_title"] = candidate_title
                item["heretic_url"] = None
                item["reference_role"] = "primary"
                item.pop("promotion_policy", None)
                item.pop("blocked_by_candidate_audit", None)
                _remove_negative_evidence(item, "weak_alias_surface_public_title_bridge")

        ledger["pipeline_official_title"] = candidate_title
        ledger["blocked_official_title"] = None
        ledger["blocked_official_title_url"] = None
        ledger["promotion_blocked_reasons"] = []
        ledger["promotion_decision"] = gate_decision
        ledger["promotion_gate_state"] = gate_state_payload
        ledger["candidate_ledger_status"] = "safe_resolved"
        ledger["title_resolution_allowed"] = True
        ledger["title_resolution_state"] = "resolved"
        ledger["work_resolution"] = "resolved"
        ledger["is_resolved_work_discussion"] = True
        identity["candidate_ledger"] = ledger

        _sync_allowed_publication_result_contract(result_dict)
        return changed_local or True

    def _restore_blocked_candidate_when_shared_gate_allows(candidate_title: str, candidate_url: str) -> bool:
        candidate_title = str(candidate_title or "").strip()
        candidate_url = _official_detail_url(candidate_url)
        if not candidate_title or not candidate_url:
            return False

        decision = promotion_decision if isinstance(promotion_decision, dict) else {}
        gate_state = promotion_gate_state if isinstance(promotion_gate_state, dict) else {}
        reason_codes = {
            str(code or "").strip()
            for code in decision.get("reason_codes", [])
            if str(code or "").strip()
        }
        decision_scope = decision.get("scope") if isinstance(decision.get("scope"), dict) else {}
        gate_scope = gate_state.get("scope") if isinstance(gate_state.get("scope"), dict) else {}
        scope_kind = str(
            decision_scope.get("scope_kind")
            or gate_scope.get("scope_kind")
            or ""
        ).strip().lower()
        scope_current_work = scope_kind == "current_work" or "scope_current_work" in reason_codes
        row_discusses_work = bool(
            gate_state.get("row_discusses_work_as_work") is True
            or "row_discusses_work_as_work" in reason_codes
        )
        official_detail_evidence = bool(
            _official_detail_url(candidate_url)
            or gate_state.get("official_title_exists") is True
            or "official_detail_url" in reason_codes
        )

        candidate_key = _title_key(candidate_title)
        source_title = _source_post_title()
        post_key = _title_key(source_title)
        alias_keys = _candidate_alias_keys(candidate_title, candidate_url)
        title_led_alias_surface = bool(
            _title_led_consumption_marker(source_title)
            and any(2 <= len(alias_key) <= 8 and alias_key in post_key for alias_key in alias_keys)
        )
        exact_title_surface = bool(
            candidate_key and post_key and (post_key.startswith(candidate_key) or candidate_key in post_key)
        )
        flags = {
            str(value or "").strip()
            for source in (identity.get("consistency_flags"), ledger.get("consistency_flags"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }
        contexts = {
            str(value or "").strip().lower()
            for source in (identity.get("context_sources"), ledger.get("context_sources"))
            if isinstance(source, list)
            for value in source
            if str(value or "").strip()
        }

        def _iter_identity_ledger_dicts(key: str) -> List[Dict[str, Any]]:
            items: List[Dict[str, Any]] = []
            for source in (identity.get(key), ledger.get(key)):
                if not isinstance(source, list):
                    continue
                for item in source:
                    if isinstance(item, dict):
                        items.append(item)
            return items

        def _matching_promoted_image_work_title() -> bool:
            for item in _iter_identity_ledger_dicts("image_evidence_catalog"):
                role = str(item.get("title_role") or "").strip().lower()
                evidence_type = str(item.get("evidence_type") or "").strip().lower()
                hard_image_surface = bool(
                    item.get("promotion_eligible") is True
                    or evidence_type == "cover_title"
                    or str(item.get("focus_role") or "").strip().lower() == "work_anchor"
                    or str(item.get("screen_type") or "").strip().lower() == "work_surface"
                )
                if not hard_image_surface:
                    continue
                if role not in {"title", "cover_title", "explicit_title", "work_title"} and evidence_type not in {
                    "cover_title",
                    "ocr_title",
                    "explicit_title",
                    "work_title",
                }:
                    continue
                image_title = str(
                    item.get("explicit_work_title")
                    or item.get("detected_title")
                    or item.get("work_title")
                    or item.get("official_title")
                    or ""
                ).strip()
                if image_title and _title_key(image_title) == candidate_key:
                    return True
            return False

        def _source_text_key() -> str:
            chunks: List[str] = [str(result_dict.get("title") or "")]
            for key in ("content", "comments", "comment_context_lines", "comment_dialogue_context_lines"):
                value = result_dict.get(key)
                if isinstance(value, list):
                    chunks.extend(str(item) for item in value if str(item).strip())
                elif str(value or "").strip():
                    chunks.append(str(value))
            return _title_key(" ".join(chunks))

        def _verified_character_bridge_to_candidate() -> bool:
            source_key = _source_text_key()
            for item in _iter_identity_ledger_dicts("verified_character_work_links"):
                item_title = str(
                    item.get("official_title") or item.get("title") or item.get("work_title") or ""
                ).strip()
                if _title_key(item_title) != candidate_key:
                    continue
                character_key = _title_key(item.get("character") or item.get("alias") or item.get("surface"))
                if not character_key or character_key in source_key:
                    return True
            confirmed_alias_keys = [
                _title_key(flag.split(":", 1)[1])
                for flag in flags
                if flag.startswith("confirmed_alias:") and ":" in flag
            ]
            return bool(
                "verified_alias_official_detail_anchor" in flags
                and confirmed_alias_keys
                and any(alias_key and alias_key in source_key for alias_key in confirmed_alias_keys)
            )

        def _search_character_parenthetical_bridge_to_candidate() -> bool:
            source_key = _source_text_key()
            if not source_key:
                return False
            for item in _search_evidence_items():
                title_text = str(item.get("title") or "").strip()
                if not title_text:
                    continue
                source_tier = str(item.get("source_tier") or "").strip().lower()
                domain = str(item.get("domain") or "").strip().lower()
                url = str(item.get("url") or "").strip().lower()
                if source_tier not in {"wiki", "knowledge"} and "namu.wiki" not in domain and "namu.wiki" not in url:
                    continue
                for match in re.finditer(r"([0-9A-Za-z가-힣]{2,8})\s*\(([^()]{3,80})\)", title_text):
                    character_key = _title_key(match.group(1))
                    parent_title_key = _title_key(match.group(2))
                    if not character_key or not parent_title_key:
                        continue
                    if character_key not in source_key:
                        continue
                    if parent_title_key == character_key or character_key in parent_title_key:
                        continue
                    if parent_title_key == candidate_key:
                        return True
            return False

        def _direct_image_work_surface_bridge_recorded() -> bool:
            scope_sources = {
                str(value or "").strip()
                for raw_scope in (decision_scope, gate_scope)
                for value in (
                    raw_scope.get("direct_bridge_sources")
                    if isinstance(raw_scope.get("direct_bridge_sources"), list)
                    else []
                )
                if str(value or "").strip()
            }
            bridge_codes = {
                "direct_image_work_surface_bridge",
                "direct_image_work_surface_lock",
                "structured_direct_image_work_surface",
                "ocr_catalog_official_title",
                "image_ocr_work_title",
            }
            return bool(
                reason_codes & bridge_codes
                or scope_sources & bridge_codes
                or (
                    "image" in contexts
                    and "direct_image_explicit_title_rescued" in flags
                    and official_detail_evidence
                )
            )

        def _official_url_key(url: Any) -> str:
            raw = _official_detail_url(url)
            if not raw:
                return ""
            return re.sub(r"[?#].*$", "", raw.strip().rstrip("/").lower())

        def _evidence_text_supports_candidate(text: Any) -> bool:
            text_key = _title_key(text)
            return bool(
                text_key
                and candidate_key
                and (
                    text_key == candidate_key
                    or candidate_key in text_key
                    or text_key in candidate_key
                )
            )

        def _title_keys_are_near_match(left: Any, right: Any) -> bool:
            left_key = _title_key(left)
            right_key = _title_key(right)
            if not left_key or not right_key:
                return False
            if left_key == right_key or left_key in right_key or right_key in left_key:
                return True
            if min(len(left_key), len(right_key)) < 8:
                return False
            if abs(len(left_key) - len(right_key)) > 2:
                return False
            return SequenceMatcher(None, left_key, right_key).ratio() >= 0.90

        def _text_contains_near_candidate(text: Any) -> bool:
            text_key = _title_key(text)
            if not text_key or not candidate_key:
                return False
            if candidate_key in text_key:
                return True
            candidate_len = len(candidate_key)
            if candidate_len < 8:
                return False
            for delta in (-2, -1, 0, 1, 2):
                window_len = candidate_len + delta
                if window_len < 8 or window_len > len(text_key):
                    continue
                for start in range(0, len(text_key) - window_len + 1):
                    if _title_keys_are_near_match(text_key[start : start + window_len], candidate_key):
                        return True
            return False

        def _source_text_values() -> List[str]:
            chunks: List[str] = [str(result_dict.get("title") or "")]
            for key in ("content", "comments", "comment_context_lines", "comment_dialogue_context_lines"):
                value = result_dict.get(key)
                if isinstance(value, list):
                    chunks.extend(str(item) for item in value if str(item).strip())
                elif str(value or "").strip():
                    chunks.append(str(value))
            return chunks

        def _candidate_has_direct_source_support() -> bool:
            source_values = _source_text_values()
            source_key = _title_key(" ".join(source_values))
            if any(_text_contains_near_candidate(value) for value in source_values):
                return True
            for alias_key in alias_keys:
                if len(alias_key) >= 4 and alias_key in source_key:
                    return True
            for item in _iter_identity_ledger_dicts("image_evidence_catalog"):
                for key in ("explicit_work_title", "detected_title", "work_title", "official_title"):
                    if _title_keys_are_near_match(item.get(key), candidate_title):
                        return True
            candidate_url_key = _official_url_key(candidate_url)
            for source_items in (
                [identity.get("primary_work")],
                identity.get("title_candidates") or [],
                identity.get("candidate_preservation_sources") or [],
                ledger.get("title_candidates") or [],
                ledger.get("candidate_preservation_sources") or [],
            ):
                if not isinstance(source_items, list):
                    continue
                for item in source_items:
                    if not isinstance(item, dict):
                        continue
                    item_title, item_url = _candidate_title_url(item)
                    if _title_key(item_title) != candidate_key and (
                        not candidate_url_key or _official_url_key(item_url) != candidate_url_key
                    ):
                        continue
                    for key in ("alias_or_mention", "matched_alias", "anchor_text", "resolved_recall_anchor"):
                        alias_text = str(item.get(key) or "").strip()
                        alias_key = _title_key(alias_text)
                        if len(alias_key) >= 4 and alias_key in source_key:
                            return True
            return False

        def _candidate_url_title_mismatch_title() -> str:
            candidate_url_key = _official_url_key(candidate_url)
            if not candidate_key or not candidate_url_key:
                return ""
            mismatch_codes = {
                "url_title_mismatch",
                "official_detail_url_title_mismatch",
                "official_detail_url_title_mismatch_cleared",
                "official_detail_url_title_mismatch_publish_blocked",
            }
            for source_items in (
                [identity.get("primary_work")],
                identity.get("title_candidates") or [],
                identity.get("candidate_preservation_sources") or [],
                ledger.get("title_candidates") or [],
                ledger.get("candidate_preservation_sources") or [],
            ):
                if not isinstance(source_items, list):
                    continue
                for item in source_items:
                    if not isinstance(item, dict):
                        continue
                    item_title, item_url = _candidate_title_url(item)
                    item_key = _title_key(item_title)
                    item_url_key = _official_url_key(item_url)
                    if item_url_key != candidate_url_key:
                        continue
                    if item_key and item_key != candidate_key:
                        return item_title or item_url
                    negative = {
                        str(value or "").strip()
                        for value in (item.get("negative_evidence") or [])
                        if str(value or "").strip()
                    }
                    if negative & mismatch_codes:
                        return item_title or item_url or "url_title_mismatch"
            for item in _search_evidence_items():
                item_url_key = _official_url_key(item.get("url"))
                if item_url_key != candidate_url_key:
                    continue
                title_text = str(item.get("title") or item.get("official_title") or "").strip()
                snippet_text = str(item.get("snippet") or item.get("content") or "").strip()
                if _evidence_text_supports_candidate(title_text) or _evidence_text_supports_candidate(snippet_text):
                    return ""
                if _title_key(title_text):
                    return title_text
            return ""

        def _candidate_url_title_has_positive_support() -> bool:
            candidate_url_key = _official_url_key(candidate_url)
            if not candidate_key or not candidate_url_key:
                return False
            for item in _search_evidence_items():
                item_url_key = _official_url_key(item.get("url"))
                if item_url_key != candidate_url_key:
                    continue
                if _evidence_text_supports_candidate(item.get("title")):
                    return True
                if _evidence_text_supports_candidate(item.get("snippet") or item.get("content")):
                    return True
            for source_items in (
                [identity.get("primary_work")],
                identity.get("title_candidates") or [],
                identity.get("candidate_preservation_sources") or [],
                ledger.get("title_candidates") or [],
                ledger.get("candidate_preservation_sources") or [],
            ):
                if not isinstance(source_items, list):
                    continue
                for item in source_items:
                    if not isinstance(item, dict):
                        continue
                    item_title, item_url = _candidate_title_url(item)
                    if _official_url_key(item_url) != candidate_url_key:
                        continue
                    if _title_key(item_title) != candidate_key:
                        continue
                    negative = {
                        str(value or "").strip()
                        for value in (item.get("negative_evidence") or [])
                        if str(value or "").strip()
                    }
                    if negative & {
                        "url_title_mismatch",
                        "official_detail_url_title_mismatch",
                        "official_detail_url_title_mismatch_publish_blocked",
                    }:
                        continue
                    source_tier = str(item.get("source_tier") or "").strip().lower()
                    page_type = str(item.get("page_type") or "").strip().lower()
                    if source_tier == "official_detail" and page_type in {"novel_page", "work_detail"}:
                        return True
            return False

        def _mark_candidate_url_title_mismatch(mismatch_title: str) -> None:
            nonlocal changed
            flag = "official_detail_url_title_mismatch_publish_blocked"
            for target in (identity, ledger):
                current = [
                    str(value)
                    for value in (target.get("consistency_flags") or [])
                    if str(value).strip()
                ]
                if flag not in current:
                    current.append(flag)
                    target["consistency_flags"] = current
                    changed = True
            candidate_url_key = _official_url_key(candidate_url)
            for source_items in (
                [identity.get("primary_work")],
                identity.get("title_candidates") or [],
                identity.get("candidate_preservation_sources") or [],
                ledger.get("title_candidates") or [],
                ledger.get("candidate_preservation_sources") or [],
            ):
                if not isinstance(source_items, list):
                    continue
                for item in source_items:
                    if not isinstance(item, dict):
                        continue
                    item_title, item_url = _candidate_title_url(item)
                    if _official_url_key(item_url) != candidate_url_key:
                        continue
                    if _title_key(item_title) != candidate_key:
                        continue
                    negative = [
                        str(value)
                        for value in (item.get("negative_evidence") or [])
                        if str(value).strip()
                    ]
                    for code in ("url_title_mismatch", flag):
                        if code not in negative:
                            negative.append(code)
                    if mismatch_title:
                        item["url_title_mismatch_title"] = mismatch_title
                    item["negative_evidence"] = negative
                    changed = True

        def _mark_candidate_missing_direct_source_support() -> None:
            nonlocal changed
            flag = "official_detail_url_missing_direct_source_support"
            for target in (identity, ledger):
                current = [
                    str(value)
                    for value in (target.get("consistency_flags") or [])
                    if str(value).strip()
                ]
                if flag not in current:
                    current.append(flag)
                    target["consistency_flags"] = current
                    changed = True
            candidate_url_key = _official_url_key(candidate_url)
            for source_items in (
                [identity.get("primary_work")],
                identity.get("title_candidates") or [],
                identity.get("candidate_preservation_sources") or [],
                ledger.get("title_candidates") or [],
                ledger.get("candidate_preservation_sources") or [],
            ):
                if not isinstance(source_items, list):
                    continue
                for item in source_items:
                    if not isinstance(item, dict):
                        continue
                    item_title, item_url = _candidate_title_url(item)
                    if _title_key(item_title) != candidate_key and (
                        not candidate_url_key or _official_url_key(item_url) != candidate_url_key
                    ):
                        continue
                    negative = [
                        str(value)
                        for value in (item.get("negative_evidence") or [])
                        if str(value).strip()
                    ]
                    if flag not in negative:
                        negative.append(flag)
                    item["negative_evidence"] = negative
                    changed = True

        direct_image_work_title_surface = bool(candidate_key and _matching_promoted_image_work_title())
        direct_image_character_surface = bool(
            candidate_key
            and direct_image_work_title_surface
            and _verified_character_bridge_to_candidate()
        )
        direct_image_explicit_title_surface = bool(
            direct_image_work_title_surface
            and "direct_image_explicit_title_rescued" in flags
            and official_detail_evidence
        )
        search_character_parenthetical_surface = bool(
            candidate_key
            and _direct_image_work_surface_bridge_recorded()
            and _search_character_parenthetical_bridge_to_candidate()
        )
        scope_sources = {
            str(value or "").strip()
            for raw_scope in (decision_scope, gate_scope)
            for value in (
                raw_scope.get("direct_bridge_sources")
                if isinstance(raw_scope.get("direct_bridge_sources"), list)
                else []
            )
            if str(value or "").strip()
        }
        url_title_mismatch_title = ""
        if candidate_key and official_detail_evidence:
            url_title_mismatch_title = _candidate_url_title_mismatch_title()
            if url_title_mismatch_title:
                _mark_candidate_url_title_mismatch(url_title_mismatch_title)
        url_title_positive_support = _candidate_url_title_has_positive_support()
        candidate_direct_source_support = _candidate_has_direct_source_support()
        url_title_gate_context = bool(
            (
                "resolved_public_title_scope" in reason_codes
                or "resolved_public_title_scope" in scope_sources
            )
            and (
                gate_state.get("title_resolution_state") == "resolved"
                or gate_state.get("work_resolution") == "resolved"
                or "final_semantic_reread_accepted_resolution" in flags
            )
        )
        if (
            candidate_key
            and official_detail_evidence
            and not url_title_mismatch_title
            and url_title_positive_support
            and url_title_gate_context
            and not candidate_direct_source_support
        ):
            _mark_candidate_missing_direct_source_support()
        url_title_verified_official_detail_surface = bool(
            candidate_key
            and not url_title_mismatch_title
            and official_detail_evidence
            and url_title_positive_support
            and candidate_direct_source_support
            and url_title_gate_context
        )

        if not candidate_key or not post_key or not (
            exact_title_surface
            or title_led_alias_surface
            or direct_image_character_surface
            or direct_image_explicit_title_surface
            or search_character_parenthetical_surface
            or url_title_verified_official_detail_surface
        ):
            return False

        has_search_context = bool(
            "search" in contexts
            or _search_evidence_items()
            or "official_detail_url" in reason_codes
            or gate_state.get("official_title_exists") is True
        )
        if "title" not in contexts or not has_search_context:
            return False
        if not contexts & {"body", "comments"} and not (
            title_led_alias_surface
            or direct_image_character_surface
            or direct_image_explicit_title_surface
            or search_character_parenthetical_surface
            or url_title_verified_official_detail_surface
        ):
            return False

        hard_negative_flags = {
            "recommendation_context_only_no_work_anchor",
            "recommendation_context_only_public_title_conflict",
            "batch_memory_alias_rescue_blocked_nonwork_context",
            "batch_memory_alias_rescue_blocked_genre_context",
            "semantic_seed_no_work_context",
            "unresolved_worklike_hold:alias_character_discussion",
        }
        if flags & hard_negative_flags:
            return False
        if not (
            title_led_alias_surface
            or direct_image_character_surface
            or direct_image_explicit_title_surface
            or search_character_parenthetical_surface
            or url_title_verified_official_detail_surface
        ) and not (
            "decoder_exact_post_title_surface_resolved" in flags
            or str(identity.get("anchor_type") or ledger.get("anchor_type") or "").strip().lower()
            in {"title_exact", "full_title_surface"}
        ):
            return False

        if not (scope_current_work and row_discusses_work and official_detail_evidence):
            return False
        if url_title_mismatch_title:
            return False
        if title_led_alias_surface and not (
            "resolved_public_title_scope" in reason_codes
            or "title_led_consumption_bridge" in reason_codes
            or "title_led_consumption_bridge" in {
                str(value)
                for value in (
                    decision_scope.get("direct_bridge_sources")
                    if isinstance(decision_scope.get("direct_bridge_sources"), list)
                    else []
                )
            }
            or "title_led_consumption_bridge" in {
                str(value)
                for value in (
                    gate_scope.get("direct_bridge_sources")
                    if isinstance(gate_scope.get("direct_bridge_sources"), list)
                    else []
                )
            }
        ):
            return False

        scope_state = {
            "scope_kind": "current_work",
            "confidence": str(
                decision_scope.get("confidence")
                or gate_scope.get("confidence")
                or "high"
            ),
            "direct_bridge_sources": list(
                dict.fromkeys(
                    [
                        *(
                            str(value)
                            for value in (
                                decision_scope.get("direct_bridge_sources")
                                if isinstance(decision_scope.get("direct_bridge_sources"), list)
                                else []
                            )
                            if str(value).strip()
                        ),
                        *(
                            str(value)
                            for value in (
                                gate_scope.get("direct_bridge_sources")
                                if isinstance(gate_scope.get("direct_bridge_sources"), list)
                                else []
                            )
                            if str(value).strip()
                        ),
                        "row_discusses_work_as_work",
                        "title",
                        "search",
                        *(
                            [
                                "image_ocr_work_title",
                                "direct_image_explicit_title_rescued",
                                "verified_character_work_link",
                            ]
                            if direct_image_character_surface or direct_image_explicit_title_surface
                            else []
                        ),
                        *(
                            [
                                "direct_image_work_surface_bridge",
                                "search_character_parenthetical_bridge",
                            ]
                            if search_character_parenthetical_surface
                            else []
                        ),
                        *(
                            ["image_ocr_official_detail_title"]
                            if direct_image_explicit_title_surface and not direct_image_character_surface
                            else []
                        ),
                        *(
                            [
                                "url_title_verified_official_detail",
                                "final_semantic_reread_accepted_resolution",
                            ]
                            if url_title_verified_official_detail_surface
                            else []
                        ),
                        *(source for source in ("body", "comments") if source in contexts),
                    ]
                )
            ),
        }
        publish_reason_codes = [
            "official_title_exists",
            "row_discusses_work_as_work",
            "scope_current_work",
            "official_detail_url",
            "serialized_public_identity_shared_gate_restored",
        ]
        if direct_image_character_surface or direct_image_explicit_title_surface:
            publish_reason_codes.extend(
                [
                    "direct_image_explicit_title_rescued",
                    "image_ocr_work_title",
                ]
            )
        if direct_image_character_surface:
            publish_reason_codes.append("verified_character_work_link")
        elif direct_image_explicit_title_surface:
            publish_reason_codes.append("image_ocr_official_detail_title")
        if search_character_parenthetical_surface:
            publish_reason_codes.extend(
                [
                    "direct_image_work_surface_bridge",
                    "search_character_parenthetical_bridge",
                ]
            )
        if url_title_verified_official_detail_surface:
            publish_reason_codes.extend(
                [
                    "url_title_verified_official_detail",
                    "final_semantic_reread_accepted_resolution",
                ]
            )
        gate_decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": candidate_title,
            "official_url": candidate_url,
            "candidate_preserved": False,
            "reason_codes": publish_reason_codes,
            "bypassed_gate": False,
            "scope": scope_state,
        }
        gate_state_payload = dict(gate_state) if isinstance(gate_state, dict) else {}
        gate_state_payload.update(
            {
                "candidate_title": candidate_title,
                "candidate_url": candidate_url,
                "official_title_exists": True,
                "row_discusses_work_as_work": True,
                "scope": scope_state,
            }
        )

        novel = identity.get("novel_identity")
        if not isinstance(novel, dict):
            novel = {}
        novel["official_title"] = candidate_title
        novel["heretic_url"] = candidate_url
        novel["confidence"] = novel.get("confidence") if novel.get("confidence") not in {None, "", "None"} else "High"
        identity["novel_identity"] = novel
        identity["candidate_ledger_status"] = "safe_resolved"
        identity["title_resolution_allowed"] = True
        identity["title_resolution_state"] = "resolved"
        identity["work_resolution"] = "resolved"
        identity["is_resolved_work_discussion"] = True
        identity["promotion_blocked"] = False
        identity["safe_resolved"] = True
        identity["promotion_decision"] = gate_decision
        identity["promotion_gate_state"] = gate_state_payload
        for key in ("blocked_official_title", "blocked_official_title_url", "promotion_blocked_reasons"):
            if key in identity:
                identity[key] = [] if key == "promotion_blocked_reasons" else None

        cleaned_flags = [
            str(value)
            for value in (identity.get("consistency_flags") or [])
            if str(value)
            not in {
                "weak_alias_surface_public_title_bridge",
                "external_ip_unresolved_hold_blocked",
                "external_ip_unresolved_final_blocked",
            }
        ]
        for value in (
            "weak_public_title_bridge_shared_gate_exempt",
            "serialized_public_identity_shared_gate_restored",
        ):
            if value not in cleaned_flags:
                cleaned_flags.append(value)
        identity["consistency_flags"] = cleaned_flags

        primary_work = identity.get("primary_work")
        if not isinstance(primary_work, dict):
            primary_work = {}
        primary_work.update(
            {
                "official_title": candidate_title,
                "heretic_url": candidate_url,
                "confidence": primary_work.get("confidence") or "High",
                "source_tier": primary_work.get("source_tier") or "official_detail",
                "page_type": primary_work.get("page_type") or "novel_page",
                "reference_role": "primary",
            }
        )
        for key in ("promotion_policy", "blocked_by_candidate_audit"):
            primary_work.pop(key, None)
        _remove_negative_evidence(primary_work, "weak_alias_surface_public_title_bridge")
        identity["primary_work"] = primary_work

        for source_items in (
            identity.get("title_candidates"),
            identity.get("candidate_preservation_sources"),
            ledger.get("title_candidates"),
            ledger.get("candidate_preservation_sources"),
        ):
            if not isinstance(source_items, list):
                continue
            for item in source_items:
                if not isinstance(item, dict):
                    continue
                item_title, item_url = _candidate_title_url(item)
                if _title_key(item_title) != candidate_key and item_url != candidate_url:
                    continue
                item["official_title"] = candidate_title
                item["heretic_url"] = candidate_url
                item["source_tier"] = item.get("source_tier") or "official_detail"
                item["page_type"] = item.get("page_type") or "novel_page"
                item["reference_role"] = "primary"
                item.pop("promotion_policy", None)
                item.pop("blocked_by_candidate_audit", None)
                _remove_negative_evidence(item, "weak_alias_surface_public_title_bridge")

        ledger["pipeline_official_title"] = candidate_title
        ledger["blocked_official_title"] = None
        ledger["blocked_official_title_url"] = None
        ledger["promotion_blocked_reasons"] = []
        ledger["promotion_decision"] = gate_decision
        ledger["promotion_gate_state"] = gate_state_payload
        ledger["candidate_ledger_status"] = "safe_resolved"
        ledger["title_resolution_allowed"] = True
        ledger["title_resolution_state"] = "resolved"
        ledger["work_resolution"] = "resolved"
        ledger["is_resolved_work_discussion"] = True
        identity["candidate_ledger"] = ledger

        def _publish_lines(raw: Any) -> Optional[List[str]]:
            if isinstance(raw, list):
                lines = [str(line) for line in raw if str(line).strip()]
            elif isinstance(raw, str) and raw.strip():
                lines = raw.splitlines()
            else:
                return None
            updated: List[str] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("- 공식 제목:"):
                    updated.append(f"- 공식 제목: '{candidate_title}'")
                elif stripped.startswith("- 핵심 결론:") and "미확정" in stripped:
                    updated.append(
                        f"- 핵심 결론: 제목/본문/댓글/검색 근거와 shared promotion gate를 종합해 '{candidate_title}'로 확정했습니다."
                    )
                elif "미확정 유지" in stripped or "단일 공식 제목 확정은 위험" in stripped:
                    updated.append(f"- 최종 공식 제목은 '{candidate_title}'로 확정됨.")
                elif "public title promotion blocked" in stripped:
                    continue
                else:
                    updated.append(line)
            note = "- shared current_work promotion gate restored public title after weak-alias scrub."
            if note not in updated:
                updated.append(note)
            return updated

        published_reason = _publish_lines(identity.get("reason_lines") or identity.get("reason"))
        if published_reason:
            identity["reason_lines"] = published_reason
            identity["reason"] = "\n".join(published_reason)

        analysis = result_dict.get("analysis")
        if isinstance(analysis, dict):
            notes = str(analysis.get("notes") or "")
            if notes:
                analysis["notes"] = notes.replace("미확정", f"'{candidate_title}' 확정")
            for item in analysis.get("detected_titles") or []:
                if not isinstance(item, dict):
                    continue
                item_title, item_url = _candidate_title_url(item)
                if _title_key(item_title) != candidate_key and item_url != candidate_url:
                    continue
                item["official_title"] = candidate_title
                item["heretic_url"] = candidate_url
                item["reference_role"] = "primary"
                item.pop("promotion_policy", None)
                item.pop("blocked_by_candidate_audit", None)
                _remove_negative_evidence(item, "weak_alias_surface_public_title_bridge")
            result_dict["analysis"] = analysis

        _sync_allowed_publication_result_contract(result_dict)
        return True

    if _restore_blocked_verified_alias_title_only(blocked_title, blocked_url):
        return True

    if _restore_blocked_candidate_when_shared_gate_allows(blocked_title, blocked_url):
        return True

    for key in ("official_title", "official_novel_title", "resolved_title"):
        if identity.get(key):
            if not blocked_title:
                blocked_title = str(identity.get(key) or "").strip()
            identity[key] = None
            changed = True

    for key in ("heretic_url", "official_url", "resolved_url"):
        if identity.get(key):
            identity[key] = None
            changed = True

    if isinstance(novel_identity, dict):
        for key in ("official_title", "official_novel_title", "resolved_title"):
            if novel_identity.get(key):
                if not blocked_title:
                    blocked_title = str(novel_identity.get(key) or "").strip()
                novel_identity[key] = None
                changed = True
        for key in ("heretic_url", "official_url", "url"):
            if novel_identity.get(key):
                if not blocked_url:
                    blocked_url = str(novel_identity.get(key) or "").strip()
                novel_identity[key] = None
                changed = True
        if novel_identity.get("confidence") not in (None, "", "None"):
            novel_identity["confidence"] = "None"
            changed = True
        identity["novel_identity"] = novel_identity

    if blocked_title:
        if identity.get("blocked_official_title") != blocked_title:
            identity["blocked_official_title"] = blocked_title
            changed = True
        if ledger.get("blocked_official_title") != blocked_title:
            ledger["blocked_official_title"] = blocked_title
            changed = True
    if blocked_url:
        if identity.get("blocked_official_title_url") != blocked_url:
            identity["blocked_official_title_url"] = blocked_url
            changed = True
        if ledger.get("blocked_official_title_url") != blocked_url:
            ledger["blocked_official_title_url"] = blocked_url
            changed = True
    if ledger.get("pipeline_official_title"):
        ledger["pipeline_official_title"] = None
        changed = True
    if identity.get("title_resolution_allowed") is not False:
        identity["title_resolution_allowed"] = False
        changed = True
    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
        changed = True
    if identity.get("title_resolution_state") in (None, "", "resolved", "direct_resolved"):
        identity["title_resolution_state"] = "unresolved_matchable"
        changed = True
    if identity.get("is_resolved_work_discussion") is not False:
        identity["is_resolved_work_discussion"] = False
        changed = True
    if ledger:
        ledger["title_resolution_allowed"] = identity.get("title_resolution_allowed")
        ledger["work_resolution"] = identity.get("work_resolution")
        ledger["title_resolution_state"] = identity.get("title_resolution_state")
        ledger["is_resolved_work_discussion"] = identity.get("is_resolved_work_discussion")
        identity["candidate_ledger"] = ledger

    primary_work = identity.get("primary_work")
    if isinstance(primary_work, dict):
        primary_title = str(primary_work.get("official_title") or primary_work.get("title") or "").strip()
        primary_url = str(primary_work.get("heretic_url") or primary_work.get("url") or "").strip()
        if primary_title or primary_url:
            if primary_work.get("reference_role") == "primary":
                primary_work["reference_role"] = "candidate"
                changed = True
            if primary_work.get("promotion_policy") != "hold_without_promotion":
                primary_work["promotion_policy"] = "hold_without_promotion"
                changed = True
            if primary_work.get("blocked_by_candidate_audit") is not True:
                primary_work["blocked_by_candidate_audit"] = True
                changed = True
            identity["primary_work"] = primary_work

    def _scrub_lines(raw: Any) -> Optional[List[str]]:
        if isinstance(raw, list):
            lines = [str(line) for line in raw if str(line).strip()]
        elif isinstance(raw, str) and raw.strip():
            lines = raw.splitlines()
        else:
            return None

        updated: List[str] = []
        changed = False
        for line in lines:
            stripped = line.strip()
            replacement: Optional[str] = None
            if stripped.startswith("- 공식 제목:"):
                replacement = "- 공식 제목: 미확정 (promotion blocked; 후보로만 보존)"
            elif "최종 공식 제목" in stripped and ("확정" in stripped or (blocked_title and blocked_title in stripped)):
                replacement = "- 최종 공식 제목 확정 문구는 promotion block guard로 철회됨."
            elif "heretic_url_platform" in stripped:
                replacement = "- heretic_url_platform 점수는 promotion block guard로 철회됨."
            elif blocked_title and blocked_title in stripped and "관련 작품 토론으로 판정" in stripped:
                replacement = "- 작품/IP 후보 맥락은 보존하되 단일 공식 제목 확정은 보류함."

            if replacement:
                if replacement not in updated:
                    updated.append(replacement)
                changed = True
            else:
                updated.append(line)

        note = "- public title promotion blocked: serialized output kept candidate/HOLD"
        if changed and note not in updated:
            updated.append(note)
        return updated if changed else None

    scrubbed_reason = _scrub_lines(identity.get("reason_lines") or identity.get("reason"))
    if scrubbed_reason:
        identity["reason_lines"] = scrubbed_reason
        identity["reason"] = "\n".join(scrubbed_reason)
        changed = True

    analysis = result_dict.get("analysis")
    if isinstance(analysis, dict):
        notes = str(analysis.get("notes") or "")
        if notes and (
            "최종 공식 제목" in notes
            or "확정" in notes
            or (blocked_title and blocked_title in notes)
            or (blocked_url and blocked_url in notes)
        ):
            analysis["notes"] = (
                "[정합성 교정] 최종 공식 제목은 미확정 상태입니다. "
                "promotion-blocked 후보는 candidate_ledger/title_candidates에만 보존합니다."
            )
            changed = True
        for item in analysis.get("detected_titles") or []:
            if not isinstance(item, dict):
                continue
            item_title = str(item.get("official_title") or item.get("title") or "").strip()
            item_url = str(item.get("heretic_url") or item.get("url") or "").strip()
            if (blocked_title and item_title == blocked_title) or (blocked_url and item_url == blocked_url):
                if item.get("reference_role") == "primary":
                    item["reference_role"] = "candidate"
                    changed = True
                item["promotion_policy"] = "hold_without_promotion"
                item["blocked_by_candidate_audit"] = True
                changed = True
        result_dict["analysis"] = analysis

    trace_reason_codes: List[str] = []
    gate_decision: Dict[str, Any]
    if isinstance(promotion_decision, dict):
        gate_decision = dict(promotion_decision)
        raw_reason_codes = gate_decision.get("reason_codes")
        if isinstance(raw_reason_codes, list):
            trace_reason_codes.extend(str(code) for code in raw_reason_codes if str(code).strip())
    else:
        gate_decision = {}

    for source in (ledger, identity):
        if not isinstance(source, dict):
            continue
        for key in ("promotion_blocked_reasons", "candidate_audit_lint_reasons", "candidate_audit_lint"):
            values = source.get(key)
            if not isinstance(values, list):
                continue
            for value in values:
                value_text = str(value or "").strip()
                if value_text and value_text not in trace_reason_codes:
                    trace_reason_codes.append(value_text)

    def _scope_payload(raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        payload: Dict[str, Any] = {}
        scope_kind = str(raw.get("scope_kind") or "").strip()
        if scope_kind:
            payload["scope_kind"] = scope_kind
        confidence = str(raw.get("confidence") or "").strip()
        if confidence:
            payload["confidence"] = confidence
        for key in ("direct_bridge_sources", "competing_candidates", "conflict_reason_codes"):
            values = raw.get(key)
            if isinstance(values, list):
                clean = [str(value) for value in values if str(value).strip()]
                if clean:
                    payload[key] = clean
        return payload

    scope_state: Dict[str, Any] = {}
    if isinstance(promotion_gate_state, dict):
        scope_state = _scope_payload(promotion_gate_state.get("scope"))
    if not scope_state:
        scope_state = _scope_payload(gate_decision.get("scope"))
    if scope_state:
        scope_kind = str(scope_state.get("scope_kind") or "").strip()
        if scope_kind:
            scope_code = f"scope_{scope_kind}"
            if scope_code not in trace_reason_codes:
                trace_reason_codes.append(scope_code)
            if scope_kind != "current_work" and "scope_not_current_work" not in trace_reason_codes:
                trace_reason_codes.append("scope_not_current_work")
        for code in scope_state.get("conflict_reason_codes") or []:
            code_text = str(code or "").strip()
            if code_text and code_text not in trace_reason_codes:
                trace_reason_codes.append(code_text)
    if not scope_state:
        scope_state = _infer_blocked_candidate_current_work_scope(blocked_title)
    if not scope_state:
        scope_state = _infer_blocked_candidate_scope(blocked_title)
    if scope_state:
        scope_kind = str(scope_state.get("scope_kind") or "").strip()
        if scope_kind:
            scope_code = f"scope_{scope_kind}"
            if scope_code not in trace_reason_codes:
                trace_reason_codes.append(scope_code)
            if scope_kind != "current_work" and "scope_not_current_work" not in trace_reason_codes:
                trace_reason_codes.append("scope_not_current_work")
        for code in scope_state.get("conflict_reason_codes") or []:
            code_text = str(code or "").strip()
            if code_text and code_text not in trace_reason_codes:
                trace_reason_codes.append(code_text)
    if not scope_state:
        for code in trace_reason_codes:
            code_text = str(code or "").strip()
            if not code_text.startswith("scope_") or code_text == "scope_not_current_work":
                continue
            inferred_scope_kind = code_text[len("scope_") :]
            if not inferred_scope_kind:
                continue
            scope_state = {
                "scope_kind": inferred_scope_kind,
                "confidence": "medium",
                "conflict_reason_codes": ["scope_inferred_from_reason_codes"],
            }
            if "scope_inferred_from_reason_codes" not in trace_reason_codes:
                trace_reason_codes.append("scope_inferred_from_reason_codes")
            break

    if not trace_reason_codes:
        trace_reason_codes.append(str(status or "promotion_blocked_result_contract"))
    if "serialized_public_identity_scrubbed" not in trace_reason_codes:
        trace_reason_codes.append("serialized_public_identity_scrubbed")

    if str(gate_decision.get("status") or "").strip().lower() == "publish":
        gate_decision["status"] = "candidate_only"
    gate_decision.setdefault("status", "candidate_only")
    gate_decision["publish_allowed"] = False
    gate_decision["official_title"] = None
    gate_decision["official_url"] = None
    gate_decision["candidate_preserved"] = bool(blocked_title or blocked_url)
    gate_decision["reason_codes"] = trace_reason_codes
    gate_decision["bypassed_gate"] = False
    if scope_state:
        gate_decision["scope"] = scope_state
    if identity.get("promotion_decision") != gate_decision:
        identity["promotion_decision"] = gate_decision
        changed = True

    publish_trace = {
        "pre_gate_candidate": {
            "official_title": blocked_title or None,
            "official_url": blocked_url or None,
            "source": "candidate_ledger_or_serialized_identity",
        },
        "gate_decision": gate_decision,
        "scope_state": scope_state or None,
        "post_gate_identity": {
            "official_title": None,
            "official_url": None,
            "title_resolution_allowed": identity.get("title_resolution_allowed"),
            "title_resolution_state": identity.get("title_resolution_state"),
            "work_resolution": identity.get("work_resolution"),
            "candidate_ledger_status": status or identity.get("candidate_ledger_status"),
        },
        "reason_codes": trace_reason_codes,
        "bypassed_gate": False,
    }
    publish_ledger = {
        "candidate_preservation": publish_trace["pre_gate_candidate"],
        "public_publish": publish_trace["post_gate_identity"],
        "gate_decision": gate_decision,
    }
    if identity.get("publish_contract_trace") != publish_trace:
        identity["publish_contract_trace"] = publish_trace
        changed = True
    if identity.get("publish_ledger") != publish_ledger:
        identity["publish_ledger"] = publish_ledger
        changed = True
    if isinstance(ledger, dict):
        if ledger.get("promotion_decision") != gate_decision:
            ledger["promotion_decision"] = gate_decision
            changed = True
        if scope_state:
            gate_state_payload = dict(promotion_gate_state) if isinstance(promotion_gate_state, dict) else {}
            gate_state_payload["scope"] = scope_state
            if ledger.get("promotion_gate_state") != gate_state_payload:
                ledger["promotion_gate_state"] = gate_state_payload
                changed = True
            if identity.get("promotion_gate_state") != gate_state_payload:
                identity["promotion_gate_state"] = gate_state_payload
                changed = True
        if ledger.get("publish_contract_trace") != publish_trace:
            ledger["publish_contract_trace"] = publish_trace
            changed = True
        if ledger.get("publish_ledger") != publish_ledger:
            ledger["publish_ledger"] = publish_ledger
            changed = True
        identity["candidate_ledger"] = ledger

    return changed


def _sync_allowed_publication_result_contract(result_dict: Dict[str, Any]) -> bool:
    """Record the final publish ledger for serialized public titles."""
    if not isinstance(result_dict, dict):
        return False
    identity = result_dict.get("identity")
    if not isinstance(identity, dict):
        return False

    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    novel_identity = identity.get("novel_identity")
    nested_title = ""
    nested_url = ""
    if isinstance(novel_identity, dict):
        nested_title = str(
            novel_identity.get("official_title")
            or novel_identity.get("official_novel_title")
            or novel_identity.get("resolved_title")
            or ""
        ).strip()
        nested_url = str(
            novel_identity.get("heretic_url")
            or novel_identity.get("official_url")
            or novel_identity.get("url")
            or ""
        ).strip()

    public_title = str(
        identity.get("official_title")
        or identity.get("official_novel_title")
        or identity.get("resolved_title")
        or nested_title
        or ""
    ).strip()
    if not public_title:
        return False
    public_url = str(
        identity.get("heretic_url")
        or identity.get("official_url")
        or identity.get("resolved_url")
        or nested_url
        or ""
    ).strip()

    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    if isinstance(decision, dict) and decision.get("publish_allowed") is False:
        return False

    changed = False
    trace_reason_codes: List[str] = []
    inferred_decision = not isinstance(decision, dict)
    gate_decision = dict(decision) if isinstance(decision, dict) else {}
    raw_reason_codes = gate_decision.get("reason_codes")
    if isinstance(raw_reason_codes, list):
        trace_reason_codes.extend(str(code) for code in raw_reason_codes if str(code).strip())
    if inferred_decision:
        trace_reason_codes.append("final_publication_decision_inferred_from_serialized_identity")
    if "serialized_public_identity_published" not in trace_reason_codes:
        trace_reason_codes.append("serialized_public_identity_published")

    def _scope_payload(raw: Any) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        payload: Dict[str, Any] = {}
        scope_kind = str(raw.get("scope_kind") or "").strip()
        if scope_kind:
            payload["scope_kind"] = scope_kind
        confidence = str(raw.get("confidence") or "").strip()
        if confidence:
            payload["confidence"] = confidence
        for key in ("direct_bridge_sources", "competing_candidates", "conflict_reason_codes"):
            values = raw.get(key)
            if isinstance(values, list):
                clean = [str(value) for value in values if str(value).strip()]
                if clean:
                    payload[key] = clean
        return payload

    gate_state = identity.get("promotion_gate_state")
    if not isinstance(gate_state, dict):
        gate_state = ledger.get("promotion_gate_state")
    scope_state: Dict[str, Any] = {}
    if isinstance(gate_state, dict):
        scope_state = _scope_payload(gate_state.get("scope"))
    if not scope_state:
        scope_state = _scope_payload(gate_decision.get("scope"))
    if not scope_state:
        bridge_sources = []
        for value in identity.get("context_sources") or ledger.get("context_sources") or []:
            value_text = str(value or "").strip()
            if value_text:
                bridge_sources.append(value_text)
        anchor_type = str(identity.get("anchor_type") or ledger.get("anchor_type") or "").strip()
        if anchor_type:
            bridge_sources.append(f"anchor_type:{anchor_type}")
        scope_state = {
            "scope_kind": "current_work",
            "confidence": "medium",
            "direct_bridge_sources": list(dict.fromkeys(bridge_sources)),
            "conflict_reason_codes": ["scope_inferred_from_final_publication"],
        }
    scope_kind = str(scope_state.get("scope_kind") or "").strip()
    if scope_kind:
        scope_code = f"scope_{scope_kind}"
        if scope_code not in trace_reason_codes:
            trace_reason_codes.append(scope_code)
    for code in scope_state.get("conflict_reason_codes") or []:
        code_text = str(code or "").strip()
        if code_text and code_text not in trace_reason_codes:
            trace_reason_codes.append(code_text)

    gate_decision["status"] = "publish"
    gate_decision["publish_allowed"] = True
    gate_decision["official_title"] = public_title
    gate_decision["official_url"] = public_url or None
    gate_decision["candidate_preserved"] = False
    gate_decision["reason_codes"] = trace_reason_codes
    gate_decision["bypassed_gate"] = False
    gate_decision["scope"] = scope_state

    post_gate_identity = {
        "official_title": public_title,
        "official_url": public_url or None,
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "title_resolution_state": identity.get("title_resolution_state"),
        "work_resolution": identity.get("work_resolution"),
        "candidate_ledger_status": identity.get("candidate_ledger_status"),
    }
    publish_trace = {
        "pre_gate_candidate": {
            "official_title": public_title,
            "official_url": public_url or None,
            "source": "serialized_public_identity",
        },
        "gate_decision": gate_decision,
        "scope_state": scope_state,
        "post_gate_identity": post_gate_identity,
        "reason_codes": trace_reason_codes,
        "bypassed_gate": False,
    }
    publish_ledger = {
        "candidate_preservation": publish_trace["pre_gate_candidate"],
        "public_publish": post_gate_identity,
        "gate_decision": gate_decision,
    }

    if identity.get("promotion_decision") != gate_decision:
        identity["promotion_decision"] = gate_decision
        changed = True
    if identity.get("publish_contract_trace") != publish_trace:
        identity["publish_contract_trace"] = publish_trace
        changed = True
    if identity.get("publish_ledger") != publish_ledger:
        identity["publish_ledger"] = publish_ledger
        changed = True

    gate_state_payload = dict(gate_state) if isinstance(gate_state, dict) else {}
    gate_state_payload["scope"] = scope_state
    if identity.get("promotion_gate_state") != gate_state_payload:
        identity["promotion_gate_state"] = gate_state_payload
        changed = True
    if ledger.get("promotion_decision") != gate_decision:
        ledger["promotion_decision"] = gate_decision
        changed = True
    if ledger.get("promotion_gate_state") != gate_state_payload:
        ledger["promotion_gate_state"] = gate_state_payload
        changed = True
    if ledger.get("publish_contract_trace") != publish_trace:
        ledger["publish_contract_trace"] = publish_trace
        changed = True
    if ledger.get("publish_ledger") != publish_ledger:
        ledger["publish_ledger"] = publish_ledger
        changed = True
    if ledger:
        identity["candidate_ledger"] = ledger
    return changed


def _demote_unsafe_url_title_verified_publication_contract(
    result_dict: Dict[str, Any],
    post_title: Optional[str] = None,
) -> bool:
    """Demote published URL-title restorations that lack post/OCR/alias support."""
    if not isinstance(result_dict, dict):
        return False
    identity = result_dict.get("identity")
    if not isinstance(identity, dict):
        return False
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    if not isinstance(decision, dict) or decision.get("publish_allowed") is not True:
        return False
    reason_codes = [
        str(code)
        for code in (decision.get("reason_codes") or [])
        if str(code).strip()
    ]
    if "url_title_verified_official_detail" not in reason_codes:
        return False

    novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
    candidate_title = str(
        decision.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
        or novel.get("official_title")
        or ""
    ).strip()
    candidate_url = str(
        decision.get("official_url")
        or identity.get("heretic_url")
        or identity.get("official_url")
        or novel.get("heretic_url")
        or novel.get("official_url")
        or ""
    ).strip()
    if not candidate_title:
        return False

    def _title_key(value: Any) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).lower()

    def _url_key(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        return re.sub(r"[?#].*$", "", raw.rstrip("/"))

    candidate_key = _title_key(candidate_title)
    candidate_url_key = _url_key(candidate_url)
    if not candidate_key:
        return False

    def _near_match(left: Any, right: Any) -> bool:
        left_key = _title_key(left)
        right_key = _title_key(right)
        if not left_key or not right_key:
            return False
        if left_key == right_key or left_key in right_key or right_key in left_key:
            return True
        if min(len(left_key), len(right_key)) < 8 or abs(len(left_key) - len(right_key)) > 2:
            return False
        return SequenceMatcher(None, left_key, right_key).ratio() >= 0.90

    def _source_values() -> List[str]:
        chunks = [str(post_title or result_dict.get("title") or "")]
        for key in ("content", "comments", "comment_context_lines", "comment_dialogue_context_lines"):
            value = result_dict.get(key)
            if isinstance(value, list):
                chunks.extend(str(item) for item in value if str(item).strip())
            elif str(value or "").strip():
                chunks.append(str(value))
        return chunks

    def _text_contains_candidate(text: Any) -> bool:
        text_key = _title_key(text)
        if not text_key:
            return False
        if candidate_key in text_key:
            return True
        if len(candidate_key) < 8:
            return False
        for delta in (-2, -1, 0, 1, 2):
            window_len = len(candidate_key) + delta
            if window_len < 8 or window_len > len(text_key):
                continue
            for start in range(0, len(text_key) - window_len + 1):
                if _near_match(text_key[start : start + window_len], candidate_key):
                    return True
        return False

    def _candidate_title_url(item: Any) -> tuple[str, str]:
        if not isinstance(item, dict):
            return "", ""
        return (
            str(
                item.get("official_title")
                or item.get("official_novel_title")
                or item.get("resolved_title")
                or item.get("title")
                or ""
            ).strip(),
            str(
                item.get("heretic_url")
                or item.get("official_url")
                or item.get("resolved_url")
                or item.get("url")
                or ""
            ).strip(),
        )

    def _candidate_items() -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for source_items in (
            [identity.get("primary_work")],
            identity.get("title_candidates") or [],
            identity.get("candidate_preservation_sources") or [],
            ledger.get("title_candidates") or [],
            ledger.get("candidate_preservation_sources") or [],
        ):
            if not isinstance(source_items, list):
                continue
            items.extend(item for item in source_items if isinstance(item, dict))
        return items

    source_values = _source_values()
    source_key = _title_key(" ".join(source_values))
    direct_support = any(_text_contains_candidate(value) for value in source_values)
    if not direct_support:
        for item in _candidate_items():
            item_title, item_url = _candidate_title_url(item)
            if _title_key(item_title) != candidate_key and (
                not candidate_url_key or _url_key(item_url) != candidate_url_key
            ):
                continue
            for key in ("alias_or_mention", "matched_alias", "anchor_text", "resolved_recall_anchor"):
                alias_key = _title_key(item.get(key))
                if len(alias_key) >= 4 and alias_key in source_key:
                    direct_support = True
                    break
            if direct_support:
                break
    if not direct_support:
        for source_items in (identity.get("image_evidence_catalog"), ledger.get("image_evidence_catalog")):
            if not isinstance(source_items, list):
                continue
            for item in source_items:
                if not isinstance(item, dict):
                    continue
                if any(
                    _near_match(item.get(key), candidate_title)
                    for key in ("explicit_work_title", "detected_title", "work_title", "official_title")
                ):
                    direct_support = True
                    break
            if direct_support:
                break
    if direct_support:
        return False

    changed = False
    flag = "official_detail_url_missing_direct_source_support"
    for target in (identity, ledger):
        current = [
            str(value)
            for value in (target.get("consistency_flags") or [])
            if str(value).strip()
        ]
        if flag not in current:
            current.append(flag)
            target["consistency_flags"] = current
            changed = True
    for item in _candidate_items():
        item_title, item_url = _candidate_title_url(item)
        if _title_key(item_title) != candidate_key and (
            not candidate_url_key or _url_key(item_url) != candidate_url_key
        ):
            continue
        negative = [
            str(value)
            for value in (item.get("negative_evidence") or [])
            if str(value).strip()
        ]
        if flag not in negative:
            negative.append(flag)
            item["negative_evidence"] = negative
            changed = True

    for key, value in (
        ("candidate_ledger_status", "promotion_blocked"),
        ("title_resolution_allowed", False),
        ("promotion_blocked", True),
        ("safe_resolved", False),
        ("blocked_official_title", candidate_title),
        ("blocked_official_title_url", candidate_url or None),
    ):
        if identity.get(key) != value:
            identity[key] = value
            changed = True
    if isinstance(novel, dict):
        if novel.get("official_title") is not None:
            novel["official_title"] = None
            changed = True
        if novel.get("heretic_url") is not None:
            novel["heretic_url"] = None
            changed = True
        identity["novel_identity"] = novel
    blocked_reasons = [
        str(value)
        for value in (identity.get("promotion_blocked_reasons") or [])
        if str(value).strip()
    ]
    if flag not in blocked_reasons:
        blocked_reasons.append(flag)
        identity["promotion_blocked_reasons"] = blocked_reasons
        changed = True

    demoted_decision = dict(decision)
    demoted_decision["status"] = "candidate_only"
    demoted_decision["publish_allowed"] = False
    demoted_decision["official_title"] = None
    demoted_decision["official_url"] = None
    demoted_decision["candidate_preserved"] = True
    demoted_reason_codes = list(dict.fromkeys([*reason_codes, flag, "serialized_public_identity_scrubbed"]))
    demoted_decision["reason_codes"] = demoted_reason_codes
    if identity.get("promotion_decision") != demoted_decision:
        identity["promotion_decision"] = demoted_decision
        changed = True
    ledger["pipeline_official_title"] = candidate_title
    ledger["blocked_official_title"] = candidate_title
    ledger["blocked_official_title_url"] = candidate_url or None
    ledger["candidate_ledger_status"] = "promotion_blocked"
    ledger["title_resolution_allowed"] = False
    ledger["promotion_decision"] = demoted_decision
    identity["candidate_ledger"] = ledger
    return changed


_PUBLICATION_GENERIC_ALIAS_KEYS = {
    "게임",
    "겜",
    "다른",
    "마땅히",
    "작품",
    "소설",
    "웹소설",
    "애니",
    "애니화",
    "새끼들",
    "이새끼들",
    "시리즈",
}


def _publication_title_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).lower()


def _publication_url_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return re.sub(r"[?#].*$", "", raw.rstrip("/"))


def _publication_near_title_match(left: Any, right: Any) -> bool:
    left_key = _publication_title_key(left)
    right_key = _publication_title_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key or left_key in right_key or right_key in left_key:
        return True
    if min(len(left_key), len(right_key)) < 8 or abs(len(left_key) - len(right_key)) > 2:
        return False
    return SequenceMatcher(None, left_key, right_key).ratio() >= 0.90


def _publication_candidate_items(identity: Dict[str, Any], ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for source_items in (
        [identity.get("primary_work")],
        identity.get("title_candidates") or [],
        identity.get("candidate_preservation_sources") or [],
        ledger.get("title_candidates") or [],
        ledger.get("candidate_preservation_sources") or [],
    ):
        if not isinstance(source_items, list):
            continue
        items.extend(item for item in source_items if isinstance(item, dict))
    return items


def _publication_candidate_title_url(item: Any) -> tuple[str, str]:
    if not isinstance(item, dict):
        return "", ""
    return (
        str(
            item.get("official_title")
            or item.get("official_novel_title")
            or item.get("resolved_title")
            or item.get("title")
            or ""
        ).strip(),
        str(
            item.get("heretic_url")
            or item.get("official_url")
            or item.get("resolved_url")
            or item.get("url")
            or ""
        ).strip(),
    )


def _publication_candidate_matches(item: Any, candidate_title: Any, candidate_url: Any) -> bool:
    item_title, item_url = _publication_candidate_title_url(item)
    item_title_key = _publication_title_key(item_title)
    candidate_title_key = _publication_title_key(candidate_title)
    if item_title_key and candidate_title_key and item_title_key == candidate_title_key:
        return True
    candidate_url_key = _publication_url_key(candidate_url)
    return bool(candidate_url_key and _publication_url_key(item_url) == candidate_url_key)


def _publication_source_key(result_dict: Dict[str, Any], post_title: Optional[str] = None) -> str:
    chunks = [str(post_title or result_dict.get("title") or "")]
    for key in ("content", "comments", "comment_context_lines", "comment_dialogue_context_lines"):
        value = result_dict.get(key)
        if isinstance(value, list):
            chunks.extend(str(item) for item in value if str(item).strip())
        elif str(value or "").strip():
            chunks.append(str(value))
    return _publication_title_key(" ".join(chunks))


def _publication_alias_in_source(alias: Any, source_key: str) -> bool:
    alias_key = _publication_title_key(alias)
    if len(alias_key) >= 4 and alias_key not in _PUBLICATION_GENERIC_ALIAS_KEYS and alias_key in source_key:
        return True
    for token in re.findall(r"[0-9A-Za-z가-힣]{3,}", str(alias or "")):
        token_key = _publication_title_key(token)
        if len(token_key) >= 3 and token_key not in _PUBLICATION_GENERIC_ALIAS_KEYS and token_key in source_key:
            return True
    return False


def _publication_slang_is_sentence_like(slang: Any) -> bool:
    if not isinstance(slang, dict):
        return False
    return (
        str(slang.get("store_reason") or "") == "sentence_like_alias_surface"
        or str(slang.get("alias_scope") or "") in {"work_plus_meme", "sentence_like_alias"}
        or str(slang.get("attached_entity_type") or "") == "meme"
    )


def _publication_slang_supports_candidate(slang: Any, candidate_title: Any, source_key: str) -> bool:
    if not isinstance(slang, dict) or _publication_slang_is_sentence_like(slang):
        return False
    if slang.get("decode_verified") is False:
        return False
    if not any(
        _publication_alias_in_source(slang.get(key), source_key)
        for key in ("detected_term", "canonical_work_alias", "canonical_value")
    ):
        return False
    for key in ("decoded_term", "canonical_work_alias", "canonical_value", "official_title"):
        if _publication_near_title_match(slang.get(key), candidate_title):
            return True
    return False


def _publication_has_direct_source_support(
    result_dict: Dict[str, Any],
    identity: Dict[str, Any],
    ledger: Dict[str, Any],
    candidate_title: Any,
    candidate_url: Any = "",
    *,
    post_title: Optional[str] = None,
) -> bool:
    source_key = _publication_source_key(result_dict, post_title=post_title)
    if not source_key and not isinstance(identity.get("slang_insight"), dict):
        return False
    for item in _publication_candidate_items(identity, ledger):
        if not _publication_candidate_matches(item, candidate_title, candidate_url):
            continue
        for key in ("alias_or_mention", "matched_alias", "anchor_text", "resolved_recall_anchor"):
            if source_key and _publication_alias_in_source(item.get(key), source_key):
                return True
    slang = identity.get("slang_insight")
    if _publication_slang_supports_candidate(slang, candidate_title, source_key):
        return True
    for item in identity.get("entity_mentions") or []:
        if not isinstance(item, dict) or _publication_slang_is_sentence_like(slang):
            continue
        if str(item.get("entity_type") or "") not in {"work", "slang"}:
            continue
        if not _publication_near_title_match(item.get("canonical_value"), candidate_title):
            continue
        entity_text_key = _publication_title_key(item.get("text"))
        if (
            source_key
            and len(entity_text_key) >= 4
            and entity_text_key not in _PUBLICATION_GENERIC_ALIAS_KEYS
            and entity_text_key in source_key
        ):
            return True
    return False


def _publication_sentence_like_alias_overreach(identity: Dict[str, Any], candidate_title: Any) -> bool:
    slang = identity.get("slang_insight")
    if not isinstance(slang, dict) or not _publication_slang_is_sentence_like(slang):
        return False
    if not _publication_near_title_match(slang.get("decoded_term"), candidate_title):
        return False
    return not _publication_near_title_match(slang.get("detected_term"), candidate_title)


def _demote_inferred_publication_with_critical_counterevidence(result_dict: Dict[str, Any], post_title: Optional[str] = None) -> bool:
    """Do not let inferred publication override weak or contradicted source-native support."""
    if not isinstance(result_dict, dict):
        return False
    identity = result_dict.get("identity")
    if not isinstance(identity, dict):
        return False
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    if not isinstance(decision, dict) or decision.get("publish_allowed") is not True:
        return False
    reason_codes = [
        str(code)
        for code in (decision.get("reason_codes") or [])
        if str(code).strip()
    ]
    if "final_publication_decision_inferred_from_serialized_identity" not in reason_codes:
        return False

    reason_chunks: List[str] = []
    raw_lines = identity.get("reason_lines")
    if isinstance(raw_lines, list):
        reason_chunks.extend(str(line) for line in raw_lines if str(line).strip())
    elif str(raw_lines or "").strip():
        reason_chunks.append(str(raw_lines))
    if str(identity.get("reason") or "").strip():
        reason_chunks.append(str(identity.get("reason")))
    reason_text = "\n".join(reason_chunks).lower()
    critical_markers = (
        "thematic_overlap_only(critical)",
        "본문 내용이 웹소설이 아닌",
        "특정 웹소설을 지칭하는 것이 아니라",
        "작품 고유 정보 전무(critical)",
        "본문에 작품 고유 정보 전무(critical)",
        "정식 소설 제목을 특정할 수 있는 플랫폼 url이 발견되지 않음(critical)",
    )
    has_critical_counterevidence = any(marker in reason_text for marker in critical_markers)
    weak_inferred_without_post_span = bool(
        "title_in_post: false" in reason_text
        and "image_ocr_title_evidence: false" in reason_text
        and "post_spans=0" in reason_text
        and (
            "grounding_anchor: none" in reason_text
            or "grounding_anchor: title_mention" in reason_text
        )
    )

    novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
    candidate_title = str(
        decision.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
        or novel.get("official_title")
        or ""
    ).strip()
    candidate_url = str(
        decision.get("official_url")
        or identity.get("heretic_url")
        or identity.get("official_url")
        or novel.get("heretic_url")
        or novel.get("official_url")
        or ""
    ).strip()
    if not candidate_title:
        return False

    has_alias_source_support = _publication_has_direct_source_support(
        result_dict,
        identity,
        ledger,
        candidate_title,
        candidate_url,
        post_title=post_title,
    )
    has_sentence_like_alias_overreach = bool(
        _publication_sentence_like_alias_overreach(identity, candidate_title)
        and "title_in_post: false" in reason_text
        and "image_ocr_title_evidence: false" in reason_text
        and not has_alias_source_support
    )
    has_weak_counterevidence = (
        weak_inferred_without_post_span and not has_alias_source_support
    ) or has_sentence_like_alias_overreach
    if not (has_critical_counterevidence or has_weak_counterevidence):
        return False

    changed = False
    if has_critical_counterevidence:
        flag = "inferred_publication_critical_counterevidence"
    elif has_sentence_like_alias_overreach:
        flag = "inferred_publication_sentence_like_alias_overreach"
    else:
        flag = "inferred_publication_missing_direct_source_support"
    scope_state = {
        "scope_kind": "context_only",
        "confidence": "high",
        "conflict_reason_codes": [flag],
    }
    for key, value in (
        ("candidate_ledger_status", "promotion_blocked"),
        ("title_resolution_allowed", False),
        ("safe_resolved", False),
        ("promotion_blocked", True),
        ("is_resolved_work_discussion", False),
        ("blocked_official_title", candidate_title),
        ("blocked_official_title_url", candidate_url or None),
    ):
        if identity.get(key) != value:
            identity[key] = value
            changed = True
    if identity.get("title_resolution_state") == "resolved":
        identity["title_resolution_state"] = "unresolved_matchable"
        changed = True
    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
        changed = True
    if isinstance(novel, dict):
        if novel.get("official_title") is not None:
            novel["official_title"] = None
            changed = True
        if novel.get("heretic_url") is not None:
            novel["heretic_url"] = None
            changed = True
        identity["novel_identity"] = novel

    blocked_reasons = [
        str(value)
        for value in (identity.get("promotion_blocked_reasons") or [])
        if str(value).strip()
    ]
    if flag not in blocked_reasons:
        blocked_reasons.append(flag)
        identity["promotion_blocked_reasons"] = blocked_reasons
        changed = True

    demoted_decision = dict(decision)
    demoted_decision["status"] = "candidate_only"
    demoted_decision["publish_allowed"] = False
    demoted_decision["official_title"] = None
    demoted_decision["official_url"] = None
    demoted_decision["candidate_preserved"] = True
    demoted_decision["reason_codes"] = list(
        dict.fromkeys(
            [
                *reason_codes,
                flag,
                "scope_context_only",
                "scope_not_current_work",
                "serialized_public_identity_scrubbed",
            ]
        )
    )
    demoted_decision["bypassed_gate"] = False
    demoted_decision["scope"] = scope_state
    if identity.get("promotion_decision") != demoted_decision:
        identity["promotion_decision"] = demoted_decision
        changed = True

    ledger["pipeline_official_title"] = candidate_title
    ledger["blocked_official_title"] = candidate_title
    ledger["blocked_official_title_url"] = candidate_url or None
    ledger["candidate_ledger_status"] = "promotion_blocked"
    ledger["title_resolution_allowed"] = False
    ledger["promotion_decision"] = demoted_decision
    gate_state_payload = {"scope": scope_state}
    ledger["promotion_gate_state"] = gate_state_payload
    identity["promotion_gate_state"] = gate_state_payload
    identity["candidate_ledger"] = ledger

    for trace_container in (identity, ledger):
        trace = trace_container.get("publish_contract_trace")
        if not isinstance(trace, dict):
            continue
        updated_trace = dict(trace)
        updated_trace["gate_decision"] = demoted_decision
        updated_trace["scope_state"] = scope_state
        updated_trace["reason_codes"] = demoted_decision["reason_codes"]
        post_gate_identity = updated_trace.get("post_gate_identity")
        if not isinstance(post_gate_identity, dict):
            post_gate_identity = {}
        else:
            post_gate_identity = dict(post_gate_identity)
        post_gate_identity.update(
            {
                "official_title": None,
                "official_url": None,
                "title_resolution_allowed": identity.get("title_resolution_allowed"),
                "title_resolution_state": identity.get("title_resolution_state"),
                "work_resolution": identity.get("work_resolution"),
                "candidate_ledger_status": identity.get("candidate_ledger_status"),
            }
        )
        updated_trace["post_gate_identity"] = post_gate_identity
        if trace_container.get("publish_contract_trace") != updated_trace:
            trace_container["publish_contract_trace"] = updated_trace
            changed = True

    return changed


def _demote_inferred_urlless_publication_contract(result_dict: Dict[str, Any], post_title: Optional[str] = None) -> bool:
    """Do not publish a title inferred only from serialized identity without an official URL."""
    if not isinstance(result_dict, dict):
        return False
    identity = result_dict.get("identity")
    if not isinstance(identity, dict):
        return False
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    if not isinstance(decision, dict) or decision.get("publish_allowed") is not True:
        return False
    reason_codes = [
        str(code)
        for code in (decision.get("reason_codes") or [])
        if str(code).strip()
    ]
    if "final_publication_decision_inferred_from_serialized_identity" not in reason_codes:
        return False
    public_url = str(decision.get("official_url") or "").strip()
    if public_url:
        return False

    novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
    public_title = str(
        decision.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
        or novel.get("official_title")
        or ""
    ).strip()
    if not public_title:
        return False
    if _publication_has_direct_source_support(
        result_dict,
        identity,
        ledger,
        public_title,
        public_url,
        post_title=post_title,
    ):
        return False

    changed = False
    flag = "serialized_public_identity_missing_official_url"
    scope_state = {
        "scope_kind": "context_only",
        "confidence": "medium",
        "conflict_reason_codes": [flag],
    }
    for key, value in (
        ("candidate_ledger_status", "promotion_blocked"),
        ("title_resolution_allowed", False),
        ("safe_resolved", False),
        ("promotion_blocked", True),
        ("blocked_official_title", public_title),
        ("blocked_official_title_url", None),
    ):
        if identity.get(key) != value:
            identity[key] = value
            changed = True
    if identity.get("title_resolution_state") == "resolved":
        identity["title_resolution_state"] = "unresolved_matchable"
        changed = True
    if identity.get("work_resolution") == "resolved":
        identity["work_resolution"] = "unresolved"
        changed = True
    if isinstance(novel, dict):
        if novel.get("official_title") is not None:
            novel["official_title"] = None
            changed = True
        if novel.get("heretic_url") is not None:
            novel["heretic_url"] = None
            changed = True
        identity["novel_identity"] = novel

    demoted_reason_codes = list(
        dict.fromkeys(
            [
                *reason_codes,
                flag,
                "scope_context_only",
                "scope_not_current_work",
                "serialized_public_identity_scrubbed",
            ]
        )
    )
    demoted_decision = dict(decision)
    demoted_decision["status"] = "candidate_only"
    demoted_decision["publish_allowed"] = False
    demoted_decision["official_title"] = None
    demoted_decision["official_url"] = None
    demoted_decision["candidate_preserved"] = True
    demoted_decision["reason_codes"] = demoted_reason_codes
    demoted_decision["bypassed_gate"] = False
    demoted_decision["scope"] = scope_state
    if identity.get("promotion_decision") != demoted_decision:
        identity["promotion_decision"] = demoted_decision
        changed = True

    ledger["pipeline_official_title"] = public_title
    ledger["blocked_official_title"] = public_title
    ledger["blocked_official_title_url"] = None
    ledger["candidate_ledger_status"] = "promotion_blocked"
    ledger["title_resolution_allowed"] = False
    ledger["promotion_decision"] = demoted_decision
    gate_state_payload = {"scope": scope_state}
    ledger["promotion_gate_state"] = gate_state_payload
    identity["promotion_gate_state"] = gate_state_payload
    identity["candidate_ledger"] = ledger
    return changed


def _sync_final_publication_ledger_contract(result_dict: Dict[str, Any], post_title: Optional[str] = None) -> bool:
    """Normalize blocked and allowed publication ledgers after candidate audit."""
    changed = _demote_unsafe_url_title_verified_publication_contract(result_dict, post_title=post_title)
    if _scrub_promotion_blocked_result_contract(result_dict, post_title=post_title):
        changed = True
    if _sync_allowed_publication_result_contract(result_dict):
        changed = True
    if _demote_inferred_publication_with_critical_counterevidence(result_dict, post_title=post_title):
        changed = True
        if _scrub_promotion_blocked_result_contract(result_dict, post_title=post_title):
            changed = True
    if _demote_inferred_urlless_publication_contract(result_dict, post_title=post_title):
        changed = True
    if _demote_platform_meta_image_title_publication_contract(result_dict, post_title=post_title):
        changed = True
    if _enforce_publish_contract_trace_convergence(result_dict):
        changed = True
    return changed


_REQUESTED_PARALLEL_RAW = max(1, _CLI_ARGS.parallel)
_PARALLEL_POLICY_MODEL = _resolve_model_for_parallel_policy()
_PARALLEL_CAP_META = _apply_model_parallel_cap(_REQUESTED_PARALLEL_RAW, _PARALLEL_POLICY_MODEL)
_REQUESTED_PARALLEL = int(_PARALLEL_CAP_META["requested_parallel"])
_MODEL_PARALLEL_MAX = _PARALLEL_CAP_META["model_parallel_max"]
_MODEL_PARALLEL_CAP_APPLIED = bool(_PARALLEL_CAP_META["model_parallel_cap_applied"])
_PARALLEL = _REQUESTED_PARALLEL
_INPUT_POST_COUNT = 0

# ─── 스레드 안전 로그 출력 ──────────────────────────────
_print_lock = threading.Lock()
_results_lock = threading.Lock()

# ─── 병렬 모드: 워커별 로그 파일 라우팅 ─────────────────
_worker_tls = threading.local()  # .log_file, .worker_id 저장
_parallel_mode = False  # _Tee에서 참조
_shutdown_event = threading.Event()  # Ctrl+C 종료 시그널
_main_thread_id = threading.main_thread().ident  # 병렬 모드 콘솔 출력 제어


def _effective_parallel_for_post_count(post_count: int) -> int:
    """Treat --parallel as a maximum, not a fixed worker count."""
    if post_count <= 0:
        return 1
    return max(1, min(_REQUESTED_PARALLEL, post_count))


def _build_completed_subset_rows(
    flushed_results: List[Any],
    pending_results: Dict[int, Any],
) -> List[Any]:
    """Return flushed rows plus completed pending rows in global index order.

    The primary result file remains the ordered flushed prefix. This helper is
    only for a recovery artifact when a later completed row is blocked behind an
    earlier missing global index.
    """
    return list(flushed_results) + [
        item for _, item in sorted(pending_results.items(), key=lambda kv: kv[0])
    ]


def _public_comment_metadata(
    comments: List[Any],
    post_author: Optional[str],
    post_gallery_id: Optional[str] = None,
    post_ip: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Preserve public author/IP context without duplicating full comment text."""
    out: List[Dict[str, Any]] = []
    post_author_text = str(post_author or "").strip()
    post_ip_text = str(post_ip or "").strip()
    gallery_id_text = str(post_gallery_id or "").strip()
    speaker_by_key: Dict[str, str] = {}
    next_speaker_idx = 1

    def _is_generic_author(value: str) -> bool:
        norm = re.sub(r"\s+", "", str(value or "").strip().lower())
        return norm in {"ㅇㅇ", "익명", "유동", "무명", "anonymous", "anon", "unknown", "-"}

    def _is_post_author_comment(author: str, ip: str) -> bool:
        if post_ip_text and ip and ip == post_ip_text:
            if not post_author_text or not author or author == post_author_text or _is_generic_author(post_author_text):
                return True
        if post_author_text and author and author == post_author_text:
            if _is_generic_author(author) or _is_generic_author(post_author_text):
                return False
            if post_ip_text and ip and ip != post_ip_text and _is_generic_author(author):
                return False
            if post_ip_text and not ip and _is_generic_author(author):
                return False
            return True
        return False

    def _post_author_match_unverified(author: str, ip: str) -> bool:
        if not post_author_text or not author or author != post_author_text:
            return False
        if not (_is_generic_author(author) or _is_generic_author(post_author_text)):
            return False
        return not (post_ip_text and ip and ip == post_ip_text)

    def _speaker_label(author: str, ip: str) -> str:
        nonlocal next_speaker_idx
        if _is_post_author_comment(author, ip):
            return "post_author"
        if author and ip and _is_generic_author(author):
            key = f"author:{author}|ip:{ip}"
        else:
            key = f"author:{author}" if author else f"ip:{ip}" if ip else ""
        if not key:
            return "unknown"
        if key not in speaker_by_key:
            speaker_by_key[key] = f"user{next_speaker_idx}"
            next_speaker_idx += 1
        return speaker_by_key[key]

    for idx, comment in enumerate(comments or []):
        source: Dict[str, Any] = {}
        if isinstance(comment, dict):
            source = comment
        elif hasattr(comment, "model_dump"):
            try:
                dumped = comment.model_dump()
                if isinstance(dumped, dict):
                    source = dumped
            except Exception:
                source = {}
        elif hasattr(comment, "__dict__"):
            source = {
                key: getattr(comment, key, None)
                for key in (
                    "comment_id",
                    "author",
                    "ip",
                    "created_at",
                    "reply_to_comment_id",
                    "reply_level",
                    "gallery_id",
                )
            }

        author = str(source.get("author") or "").strip()
        ip = str(source.get("ip") or "").strip()
        comment_gallery_id = str(source.get("gallery_id") or gallery_id_text).strip()
        meta = {
            "index": idx,
            "comment_id": source.get("comment_id"),
            "gallery_id": comment_gallery_id or None,
            "author": author or None,
            "ip": ip or None,
            "speaker": _speaker_label(author, ip),
            "created_at": source.get("created_at"),
            "reply_to_comment_id": source.get("reply_to_comment_id"),
            "reply_level": source.get("reply_level"),
            "is_post_author": _is_post_author_comment(author, ip),
            "post_author_match_unverified": _post_author_match_unverified(author, ip),
        }
        if any(value is not None and value != "" for key, value in meta.items() if key != "index"):
            out.append(meta)
    return out


def _public_comment_context_lines(
    comment_metadata: List[Dict[str, Any]],
    *,
    limit: int = 15,
) -> List[str]:
    """Build compact public speaker/thread context for review artifacts."""
    lines: List[str] = []
    for rec in (comment_metadata or [])[:limit]:
        if not isinstance(rec, dict):
            continue
        parts = [
            f"#{int(rec.get('index') or 0) + 1}",
            f"speaker={rec.get('speaker') or 'unknown'}",
        ]
        if rec.get("author"):
            parts.append(f"author={rec.get('author')}")
        if rec.get("is_post_author"):
            parts.append("role=post_author")
        elif rec.get("post_author_match_unverified"):
            parts.append("role=author_match_unverified")
        if rec.get("ip"):
            parts.append(f"ip={rec.get('ip')}")
        if rec.get("reply_level") not in (None, "", 0, "0"):
            parts.append(f"reply_level={rec.get('reply_level')}")
        if rec.get("reply_to_comment_id"):
            parts.append(f"reply_to={rec.get('reply_to_comment_id')}")
        if rec.get("comment_id"):
            parts.append(f"comment_id={rec.get('comment_id')}")
        lines.append(" ".join(parts))
    return lines


def _comment_text_from_any(comment: Any) -> str:
    if isinstance(comment, dict):
        return str(comment.get("content") or comment.get("text") or "").strip()
    if hasattr(comment, "content"):
        return str(getattr(comment, "content") or "").strip()
    return str(comment or "").strip()


def _public_comment_dialogue_context_lines(
    comments: List[Any],
    comment_metadata: List[Dict[str, Any]],
    *,
    limit: int = 15,
    max_text_chars: int = 140,
) -> List[str]:
    """Build speaker-aware dialogue lines for prompts/review artifacts."""
    meta_by_index = {
        int(rec.get("index") or 0): rec
        for rec in (comment_metadata or [])
        if isinstance(rec, dict)
    }
    lines: List[str] = []
    for idx, comment in enumerate(comments or []):
        if len(lines) >= limit:
            break
        text = " ".join(_comment_text_from_any(comment).split())
        if not text:
            continue
        if len(text) > max_text_chars:
            text = text[:max_text_chars].rstrip() + "..."
        rec = meta_by_index.get(idx, {})
        parts = [
            f"#{idx + 1}",
            f"speaker={rec.get('speaker') or 'unknown'}",
        ]
        if rec.get("author"):
            parts.append(f"author={rec.get('author')}")
        if rec.get("is_post_author"):
            parts.append("role=post_author")
        elif rec.get("post_author_match_unverified"):
            parts.append("role=author_match_unverified")
        if rec.get("ip"):
            parts.append(f"ip={rec.get('ip')}")
        if rec.get("reply_level") not in (None, "", 0, "0"):
            parts.append(f"reply_level={rec.get('reply_level')}")
        if rec.get("reply_to_comment_id"):
            parts.append(f"reply_to={rec.get('reply_to_comment_id')}")
        if rec.get("comment_id"):
            parts.append(f"comment_id={rec.get('comment_id')}")
        parts.append(f"text={text}")
        lines.append(" ".join(parts))
    return lines


def _public_content_blocks(content_blocks: List[Any]) -> List[Dict[str, Any]]:
    """Preserve reviewable public text/image block order in result artifacts."""
    out: List[Dict[str, Any]] = []
    for block in content_blocks or []:
        source: Dict[str, Any] = {}
        if isinstance(block, dict):
            source = block
        elif hasattr(block, "model_dump"):
            try:
                dumped = block.model_dump()
                if isinstance(dumped, dict):
                    source = dumped
            except Exception:
                source = {}
        elif hasattr(block, "__dict__"):
            source = {
                key: getattr(block, key, None)
                for key in ("type", "url", "text")
            }
        elif isinstance(block, str):
            source = {"type": "text", "text": block}

        source_url = source.get("url") or source.get("image_url") or source.get("src")
        block_type = str(source.get("type") or "").strip() or ("image" if source_url else "text")
        rec: Dict[str, Any] = {"type": block_type}
        text = str(source.get("text") or "").strip()
        url = str(source_url or "").strip()
        if text:
            rec["text"] = text
        if url:
            rec["url"] = url
        if rec.get("text") or rec.get("url"):
            out.append(rec)
    return out


def _public_image_urls(content_blocks: List[Any]) -> List[str]:
    seen: set[str] = set()
    urls: List[str] = []
    for block in _public_content_blocks(content_blocks):
        url = str(block.get("url") or "").strip()
        block_type = str(block.get("type") or "").strip().lower()
        if not url or url in seen:
            continue
        if block_type in {"image", "img", "photo", "picture"} or re.search(r"\.(?:png|jpe?g|gif|webp)(?:[?#].*)?$", url, re.I):
            seen.add(url)
            urls.append(url)
    return urls


def _set_env(k: str, v: str) -> None:
    """환경변수 강제 설정"""
    os.environ[k] = v


def _resolve_toggle(value: Optional[str], *, env_key: str, default: str) -> str:
    raw = value if value is not None else os.getenv(env_key, default)
    normalized = str(raw or default).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return "1"
    if normalized in {"0", "false", "no", "off"}:
        return "0"
    return "1" if str(default).strip().lower() in {"1", "true", "yes", "on"} else "0"


def _normalize_mcp_endpoint(endpoint: str) -> str:
    raw = str(endpoint or "").strip().rstrip("/")
    if not raw:
        return ""
    normalize_localhost = _env_bool_runtime("MCP_NORMALIZE_LOCALHOST", True)
    if not normalize_localhost:
        return raw
    try:
        parts = urlsplit(raw)
        if parts.hostname and parts.hostname.lower() == "localhost":
            netloc = "127.0.0.1"
            if parts.port:
                netloc = f"{netloc}:{parts.port}"
            return urlunsplit((parts.scheme or "http", netloc, parts.path, parts.query, parts.fragment)).rstrip("/")
    except Exception:
        pass
    return raw


def _dedupe_mcp_endpoints(raw_endpoints: str) -> List[str]:
    """쉼표/공백/개행으로 섞인 MCP endpoint 목록을 순서 보존 dedupe한다."""
    seen: set[str] = set()
    out: List[str] = []
    for token in re.split(r"[\s,]+", str(raw_endpoints or "")):
        endpoint = _normalize_mcp_endpoint(token)
        if not endpoint:
            continue
        key = endpoint.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(endpoint)
    return out


def _configure_mcp_endpoints(default_count: int) -> None:
    """MCP shard endpoint를 자동 구성한다.

    우선순위:
    1) MCP_ENDPOINTS 직접 지정
    2) MCP_ENDPOINT 단일 지정
    3) MCP_SHARD_* + parallel 기반 자동 생성
    """
    raw_endpoints = os.getenv("MCP_ENDPOINTS", "").strip()
    raw_endpoint = os.getenv("MCP_ENDPOINT", "").strip()

    if raw_endpoints:
        endpoints = _dedupe_mcp_endpoints(raw_endpoints)
        if endpoints and not raw_endpoint:
            _set_env("MCP_ENDPOINT", endpoints[0])
        if endpoints:
            _set_env("MCP_ENDPOINTS", ",".join(endpoints))
        raw_count = len([p for p in re.split(r"[\s,]+", raw_endpoints) if p.strip()])
        if raw_count != len(endpoints):
            print(
                f"[config] MCP_ENDPOINTS 중복 제거: {raw_count}→{len(endpoints)}",
                file=sys.stderr,
                flush=True,
            )
        _set_env("MCP_ENDPOINTS_AUTOGEN", "0")
        return

    if raw_endpoint:
        _set_env("MCP_ENDPOINT", _normalize_mcp_endpoint(raw_endpoint))
        _set_env("MCP_ENDPOINTS_AUTOGEN", "0")
        return

    explicit_shard_count = os.getenv("MCP_SHARD_COUNT", "").strip()
    try:
        shard_count = max(1, int(explicit_shard_count or str(default_count)))
    except Exception:
        shard_count = max(1, default_count)

    auto_shard_limit_configured = "MCP_AUTO_SHARD_LIMIT" in os.environ
    auto_shard_limit_raw = os.getenv("MCP_AUTO_SHARD_LIMIT", "0").strip()
    try:
        auto_shard_limit = max(0, int(auto_shard_limit_raw))
    except Exception:
        auto_shard_limit = 0
    if auto_shard_limit > 0 and not explicit_shard_count and shard_count > auto_shard_limit:
        print(
            "[config] MCP shard 자동 생성 수를 {limit}개로 제한합니다 "
            "(parallel={parallel}, 필요 시 MCP_SHARD_COUNT 또는 MCP_AUTO_SHARD_LIMIT로 override)".format(
                limit=auto_shard_limit,
                parallel=default_count,
            ),
            file=sys.stderr,
            flush=True,
        )
        shard_count = auto_shard_limit

    small_run_threshold_raw = os.getenv("MCP_SMALL_RUN_SHARD_THRESHOLD", "10").strip()
    small_run_limit_raw = os.getenv("MCP_SMALL_RUN_AUTO_SHARD_LIMIT", "2").strip()
    try:
        small_run_threshold = max(0, int(small_run_threshold_raw))
    except Exception:
        small_run_threshold = 10
    try:
        small_run_limit = max(0, int(small_run_limit_raw))
    except Exception:
        small_run_limit = 2
    if (
        small_run_threshold > 0
        and small_run_limit > 0
        and not explicit_shard_count
        and not auto_shard_limit_configured
        and default_count < small_run_threshold
        and shard_count > small_run_limit
    ):
        print(
            "[config] 소규모 targeted run shard 자동 생성 수를 {limit}개로 제한합니다 "
            "(effective_parallel={parallel}, 필요 시 MCP_SHARD_COUNT, MCP_AUTO_SHARD_LIMIT, "
            "MCP_SMALL_RUN_AUTO_SHARD_LIMIT로 override)".format(
                limit=small_run_limit,
                parallel=default_count,
            ),
            file=sys.stderr,
            flush=True,
        )
        shard_count = small_run_limit

    goal_run_limit_raw = os.getenv("MCP_GOAL_RUN_AUTO_SHARD_LIMIT", "8").strip()
    try:
        goal_run_limit = max(0, int(goal_run_limit_raw))
    except Exception:
        goal_run_limit = 8
    if (
        goal_run_limit > 0
        and _small_run_shard_lifecycle_blocked()
        and shard_count > goal_run_limit
    ):
        print(
            "[config] goal/targeted run shard autogen count capped to {limit} "
            "(effective_parallel={parallel}, override with MCP_GOAL_RUN_AUTO_SHARD_LIMIT "
            "or explicit shard lifecycle opt-in)".format(
                limit=goal_run_limit,
                parallel=default_count,
            ),
            file=sys.stderr,
            flush=True,
        )
        shard_count = goal_run_limit
    try:
        base_port = int(os.getenv("MCP_SHARD_BASE_PORT", "3333"))
    except Exception:
        base_port = 3333

    scheme = os.getenv("MCP_SHARD_SCHEME", "http").strip() or "http"
    host = os.getenv("MCP_SHARD_HOST", "127.0.0.1").strip() or "127.0.0.1"

    endpoints = [f"{scheme}://{host}:{base_port + idx}" for idx in range(shard_count)]
    _set_env("MCP_ENDPOINTS", ",".join(endpoints))
    _set_env("MCP_ENDPOINT", endpoints[0])
    _set_env("MCP_ENDPOINTS_AUTOGEN", "1")


def _get_mcp_endpoint_pool() -> List[str]:
    raw_endpoints = os.getenv("MCP_ENDPOINTS", "").strip()
    if raw_endpoints:
        endpoints = _dedupe_mcp_endpoints(raw_endpoints)
        if endpoints:
            normalized = ",".join(endpoints)
            if normalized != raw_endpoints:
                _set_env("MCP_ENDPOINTS", normalized)
            return endpoints

    raw_endpoint = _normalize_mcp_endpoint(os.getenv("MCP_ENDPOINT", ""))
    if raw_endpoint:
        return [raw_endpoint]

    return ["http://127.0.0.1:3333"]


def _format_mcp_endpoint_pool(endpoints: List[str]) -> str:
    if not endpoints:
        return "(none)"
    if len(endpoints) <= 8:
        return ",".join(endpoints)
    return f"{endpoints[0]}..{endpoints[-1]} (count={len(endpoints)})"


def _env_bool_runtime(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _reuse_only_health_filter_enabled() -> bool:
    """Allow reuse-only runs to shrink autogenerated shard pools to live shards."""
    return _healthy_autogen_endpoint_filter_reason() == "reuse_shards_only"


def _healthy_endpoint_filter_reason() -> Optional[str]:
    """Return why startup may shrink the endpoint pool to healthy shards.

    Goal/test reruns should not stop/start Docker just because an old explicit
    MCP_ENDPOINTS list still contains dead local shards.  In those contexts we
    prefer the existing healthy subset, while large validation keeps explicit
    endpoint failures visible unless reuse-only is requested.
    """
    autogen = os.getenv("MCP_ENDPOINTS_AUTOGEN", "0").strip() == "1"
    if getattr(_CLI_ARGS, "reuse_shards_only", False):
        env_key = "MCP_REUSE_ONLY_FILTER_HEALTHY_AUTOGEN" if autogen else "MCP_REUSE_ONLY_FILTER_HEALTHY_ENDPOINTS"
        if _env_bool_runtime(env_key, True):
            return "reuse_shards_only"
        return None
    if _small_run_shard_lifecycle_blocked():
        env_key = "MCP_GOAL_RUN_FILTER_HEALTHY_AUTOGEN" if autogen else "MCP_GOAL_RUN_FILTER_HEALTHY_ENDPOINTS"
        if _env_bool_runtime(env_key, True):
            return "goal_run_lifecycle_blocked"
    return None


def _healthy_autogen_endpoint_filter_reason() -> Optional[str]:
    """Backward-compatible wrapper for older tests/docs wording."""
    return _healthy_endpoint_filter_reason()


def _mcp_goal_run_light_health_mode() -> bool:
    """Use cheaper startup health checks for goal/test reuse paths."""
    explicit = os.getenv("MCP_HEALTH_LIGHT_MODE")
    if explicit is not None and explicit.strip():
        return _env_bool_runtime("MCP_HEALTH_LIGHT_MODE", True)
    return bool(getattr(_CLI_ARGS, "reuse_shards_only", False) or _small_run_shard_lifecycle_blocked())


def _default_mcp_health_include_search() -> bool:
    """Default to Bridge readiness only in small goal/reuse-only loops."""
    if _mcp_goal_run_light_health_mode():
        return False
    return not _can_auto_manage_local_shards()


def _mcp_health_required_ok_count(endpoint_pool: List[str]) -> int:
    """Return how many healthy endpoints are needed before startup may proceed."""
    endpoints = list(endpoint_pool or [])
    if not endpoints:
        return 1
    raw = os.getenv("MCP_HEALTH_REQUIRED_OK", "").strip()
    if raw:
        try:
            return max(1, min(len(endpoints), int(raw)))
        except Exception:
            pass
    if _mcp_goal_run_light_health_mode():
        return max(1, min(len(endpoints), _PARALLEL))
    return len(endpoints)


def _mcp_health_probe_batch_size(
    endpoint_pool: List[str],
    *,
    required_ok_count: int,
    health_workers: int,
) -> int:
    """Limit stale explicit endpoint probing in small goal/reuse-only runs."""
    endpoints = list(endpoint_pool or [])
    if not endpoints:
        return 1
    raw = os.getenv("MCP_HEALTH_PROBE_BATCH_SIZE", "").strip()
    if raw:
        try:
            return max(1, min(len(endpoints), int(raw)))
        except Exception:
            pass
    if _mcp_goal_run_light_health_mode():
        return max(1, min(len(endpoints), required_ok_count, max(1, health_workers)))
    return len(endpoints)


def _apply_reuse_only_healthy_endpoint_filter(
    endpoint_pool: List[str],
    health_ok: Dict[str, Any],
) -> tuple[List[str], Dict[str, Any]]:
    """Use healthy shards for reuse-only or lifecycle-blocked goal runs.

    This keeps targeted/goal runs from paying a docker compose restart cost while
    still failing fast when no reusable shard is actually alive.
    """
    global _PARALLEL

    filter_reason = _healthy_endpoint_filter_reason()
    autogen = os.getenv("MCP_ENDPOINTS_AUTOGEN", "0").strip() == "1"
    endpoints = list(endpoint_pool or [])
    healthy = [endpoint for endpoint in endpoints if endpoint in health_ok]
    before_parallel = _PARALLEL
    meta: Dict[str, Any] = {
        "mcp_healthy_endpoint_filter": False,
        "mcp_healthy_endpoint_filter_reason": filter_reason or "",
        "mcp_healthy_endpoint_filter_autogen": autogen,
        "mcp_healthy_autogen_endpoint_filter": False,
        "mcp_healthy_autogen_endpoint_filter_reason": filter_reason or "",
        "mcp_reuse_shards_only_health_filtered": False,
        "mcp_goal_run_health_filtered": False,
        "mcp_requested_endpoint_count_before_health_filter": len(endpoints),
        "mcp_healthy_endpoint_count": len(healthy),
        "mcp_endpoint_count_after_health_filter": len(endpoints),
        "mcp_parallel_before_health_filter": before_parallel,
        "mcp_parallel_after_health_filter": before_parallel,
    }

    if not filter_reason:
        return endpoints, meta
    if not endpoints or not healthy or len(healthy) == len(endpoints):
        return endpoints, meta

    _set_env("MCP_ENDPOINTS", ",".join(healthy))
    _set_env("MCP_ENDPOINT", healthy[0])
    _PARALLEL = max(1, min(_PARALLEL, len(healthy)))
    meta.update(
        {
            "mcp_healthy_endpoint_filter": True,
            "mcp_healthy_autogen_endpoint_filter": autogen,
            "mcp_healthy_autogen_endpoint_filter_reason": filter_reason,
            "mcp_reuse_shards_only_health_filtered": filter_reason == "reuse_shards_only",
            "mcp_goal_run_health_filtered": filter_reason == "goal_run_lifecycle_blocked",
            "mcp_endpoint_count_after_health_filter": len(healthy),
            "mcp_parallel_after_health_filter": _PARALLEL,
        }
    )
    return healthy, meta


def _small_run_threshold() -> int:
    raw = os.getenv("MCP_SMALL_RUN_SHARD_THRESHOLD", "10").strip()
    try:
        return max(0, int(raw))
    except Exception:
        return 10


def _shard_lifecycle_block_threshold() -> int:
    raw = os.getenv("MCP_GOAL_RUN_SHARD_LIFECYCLE_THRESHOLD", "36").strip()
    try:
        return max(0, int(raw))
    except Exception:
        return 36


def _current_run_post_count_for_lifecycle() -> int:
    return _INPUT_POST_COUNT if _INPUT_POST_COUNT > 0 else _PARALLEL


def _is_small_targeted_run() -> bool:
    threshold = _shard_lifecycle_block_threshold()
    run_size = _current_run_post_count_for_lifecycle()
    return bool(threshold > 0 and 0 < run_size <= threshold)


def _small_run_allows_shard_lifecycle() -> bool:
    """Allow docker shard lifecycle in goal/test runs only by command opt-in.

    Stale MCP_AUTO_* environment variables are easy to carry between large
    validation runs and goal/targeted reruns.  For runs at or below the
    lifecycle threshold we require the operator to opt in on the current
    command.  Environment variables alone must not stop/start shards during a
    small semantic regression loop.
    """
    if not _is_small_targeted_run():
        return True
    if _CLI_ARGS.reuse_shards_only:
        return False
    return bool(getattr(_CLI_ARGS, "allow_goal_shard_lifecycle", False))


def _small_run_shard_lifecycle_blocked() -> bool:
    return _is_small_targeted_run() and not _small_run_allows_shard_lifecycle()


def _interactive_codex_run() -> bool:
    """Detect runs launched from Codex so stale shell env cannot restart shards."""
    return bool(os.getenv("CODEX_SHELL") or os.getenv("CODEX_THREAD_ID"))


def _env_shard_lifecycle_requested() -> bool:
    for name in ("MCP_AUTO_UP_SHARDS", "MCP_AUTO_RECREATE_SHARDS"):
        raw = os.getenv(name, "").strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
    return False


def _env_shard_lifecycle_global_opt_in() -> bool:
    return _env_bool_runtime("MCP_ALLOW_ENV_SHARD_LIFECYCLE", False)


def _local_shard_status_audit_requested() -> bool:
    return _env_bool_runtime("MCP_LOCAL_SHARD_STATUS_AUDIT", False)


def _local_shard_status_audit_allowed() -> bool:
    """Gate Docker Compose based shard status checks for goal/test reruns.

    The status audit path calls tools/warp_shards.py status, which itself uses
    docker compose ps/exec.  That is useful for shard maintenance, but too
    expensive and surprising in small semantic regression loops.
    """
    if not _local_shard_status_audit_requested():
        return False
    if _CLI_ARGS.reuse_shards_only:
        return False
    if _small_run_shard_lifecycle_blocked():
        return _env_bool_runtime("MCP_ALLOW_GOAL_SHARD_STATUS_AUDIT", False)
    if _interactive_codex_run() and not _env_bool_runtime("MCP_ALLOW_CODEX_SHARD_STATUS_AUDIT", False):
        return False
    return True


def _env_shard_lifecycle_allowed() -> bool:
    """Return whether MCP_AUTO_* env vars may control Docker shard lifecycle.

    Codex goal/test reruns often inherit old MCP_AUTO_* values from larger
    validation runs. Env-based lifecycle now requires its own explicit
    acknowledgement, and Codex/small goal runs also require the current command
    to opt in so a stale shell profile cannot stop/start shards during a review
    loop.
    """
    legacy_codex_ack = _env_bool_runtime("MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE", False)
    if not (_env_shard_lifecycle_global_opt_in() or legacy_codex_ack):
        return False
    if (_interactive_codex_run() or _is_small_targeted_run()) and not getattr(
        _CLI_ARGS,
        "allow_goal_shard_lifecycle",
        False,
    ):
        return False
    return True


def _env_shard_lifecycle_blocked_by_context() -> bool:
    return _env_shard_lifecycle_requested() and not _env_shard_lifecycle_allowed()


def _command_shard_lifecycle_allowed_by_context() -> bool:
    """Require an extra explicit opt-in before goal/test runs can restart shards."""
    if _CLI_ARGS.reuse_shards_only:
        return False
    if getattr(_CLI_ARGS, "allow_goal_shard_lifecycle", False):
        return True
    if _is_small_targeted_run():
        return False
    if not _interactive_codex_run():
        return True
    return _env_bool_runtime("MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE", False)


def _can_auto_manage_local_shards() -> bool:
    if _CLI_ARGS.no_auto_up_shards or _CLI_ARGS.reuse_shards_only:
        return False
    status_audit = _local_shard_status_audit_allowed()
    if _small_run_shard_lifecycle_blocked() and not status_audit:
        return False
    if not (
        _allow_local_shard_auto_up()
        or _allow_local_shard_recreate()
        or status_audit
    ):
        return False
    if os.getenv("MCP_ENDPOINTS_AUTOGEN", "0").strip() != "1":
        return False
    host = os.getenv("MCP_SHARD_HOST", "127.0.0.1").strip().lower()
    return host in {"localhost", "127.0.0.1"}


def _allow_local_shard_auto_up() -> bool:
    if _CLI_ARGS.no_auto_up_shards or _CLI_ARGS.reuse_shards_only:
        return False
    if _small_run_shard_lifecycle_blocked():
        return False
    if getattr(_CLI_ARGS, "auto_up_shards", False):
        return _command_shard_lifecycle_allowed_by_context()
    if _env_shard_lifecycle_blocked_by_context():
        return False
    raw = os.getenv("MCP_AUTO_UP_SHARDS", "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return False


def _allow_local_shard_recreate() -> bool:
    """Return whether expert_main may force-recreate docker compose shards.

    Test/goal runs default to reuse-only for docker lifecycle actions.
    Auto up/recreate must be an explicit operator choice because compose
    stop/start cycles are expensive and can hide the actual pipeline issue.
    """
    if _CLI_ARGS.no_auto_recreate_shards or _CLI_ARGS.reuse_shards_only:
        return False
    if _small_run_shard_lifecycle_blocked():
        return False
    if getattr(_CLI_ARGS, "auto_recreate_shards", False):
        return _command_shard_lifecycle_allowed_by_context()
    if _env_shard_lifecycle_blocked_by_context():
        return False
    raw = os.getenv("MCP_AUTO_RECREATE_SHARDS", "").strip().lower()
    if raw:
        return raw in {"1", "true", "yes", "on"}
    return False


# docker up/recreate는 명시적 opt-in, 단 대형 autogen 런의 missing shard 증분
# 기동(scale-up)만 기본 ON(opt-out: MCP_AUTO_SCALE_UP_MISSING_SHARDS=0).
_SHARD_LIFECYCLE_POLICY_LABEL = "docker_up_recreate_opt_in+missing_shard_scale_up_default_on"


def _detect_external_dashboard(default_port: int) -> Optional[str]:
    """외부 standalone 대시보드(tools/dashboard_server.py)를 감지한다.

    감지되면 base URL을 반환하고 expert_main은 내장 대시보드를 띄우지 않은 채
    이벤트를 그쪽으로 전달한다(양보). 판정은 /api/health 핸드셰이크로 한다:
    - service 마커 불일치(같은 포트의 무관한 앱) → None
    - standalone=False(다른 expert_main의 내장 대시보드) → None
    감지 비용 상한은 ~1초(connect 0.3s/total 1.0s)이며,
    EXPERT_DASHBOARD_FORWARD=0 으로 감지 자체를 끌 수 있다.
    """
    if not _env_bool_runtime("EXPERT_DASHBOARD_FORWARD", True):
        return None
    url = (os.environ.get("DASHBOARD_URL", "").strip() or f"http://127.0.0.1:{default_port}").rstrip("/")
    try:
        import httpx

        resp = httpx.get(f"{url}/api/health", timeout=httpx.Timeout(1.0, connect=0.3))
        data = resp.json()
        if data.get("service") == "expert-pipeline-monitor" and data.get("standalone"):
            return url
    except Exception:
        pass
    return None


def _allow_missing_shard_auto_scale_up() -> bool:
    """헬스체크에서 빠진 로컬 autogen shard를 증분 기동(up)해도 되는지 여부.

    missing shard 서비스만 compose up 대상으로 전달하고(--shards) 추가로
    --no-recreate를 강제하므로 이미 떠 있는 healthy 컨테이너는 up 대상에서
    구조적으로 제외된다. 컨테이너가 일부만 떠 있는 대형 검증 런에서 부족분을
    자동으로 채우는 것이 목적이며, 기존 lifecycle 차단 규칙은 그대로 존중한다:
    - reuse-only / --no-auto-up-shards 차단
    - 소규모 goal/test 런은 기존 2-key(허가 --allow-goal-shard-lifecycle +
      액션 --auto-up-shards/MCP_AUTO_UP_SHARDS) 계약 유지
    - Codex 런은 stale env ack 단독으로 열리지 않고 현재 커맨드 opt-in 필수
    MCP_AUTO_SCALE_UP_MISSING_SHARDS=0 으로 끌 수 있다.
    """
    if _CLI_ARGS.no_auto_up_shards or _CLI_ARGS.reuse_shards_only:
        return False
    if _small_run_shard_lifecycle_blocked():
        return False
    # 소규모 goal/test 런: 허가 플래그 단독으로 docker 액션이 발화하지 않도록
    # 기존 opt-in 경로(_allow_local_shard_auto_up)를 그대로 요구한다.
    if _is_small_targeted_run() and not _allow_local_shard_auto_up():
        return False
    if not _command_shard_lifecycle_allowed_by_context():
        return False
    # Codex 런: 셸 프로필에서 물려받은 MCP_CODEX_ALLOW_ENV_SHARD_LIFECYCLE=1
    # 단독으로는 열리지 않는다 (_env_shard_lifecycle_allowed와 동일 규칙).
    if _interactive_codex_run() and not (
        getattr(_CLI_ARGS, "allow_goal_shard_lifecycle", False)
        or getattr(_CLI_ARGS, "auto_up_shards", False)
    ):
        return False
    if not _env_bool_runtime("MCP_AUTO_SCALE_UP_MISSING_SHARDS", True):
        return False
    if os.getenv("MCP_ENDPOINTS_AUTOGEN", "0").strip() != "1":
        return False
    host = os.getenv("MCP_SHARD_HOST", "127.0.0.1").strip().lower()
    return host in {"localhost", "127.0.0.1"}


def _scale_up_missing_local_shards(
    repo_root: Path,
    shard_count: int,
    missing_shards: List[int],
) -> None:
    """부족한 로컬 shard를 docker compose up으로 증분 기동한다.

    missing shard 서비스만 up 대상으로 전달(--shards)하므로 기존 healthy
    컨테이너는 compose 명령 대상 자체에서 제외되고, --no-recreate 강제로
    정의/이미지 drift가 있어도 기존 컨테이너 재생성이 일어나지 않는다.
    WARP_SHARDS_REMOVE_ORPHANS=0 으로 현재 풀 크기를 초과해 떠 있는 기존
    컨테이너 제거도 막는다.
    """
    if shard_count <= 0 or not missing_shards:
        return
    base_port = os.getenv("MCP_SHARD_BASE_PORT", "3333").strip() or "3333"
    tool_path = repo_root / "tools" / "warp_shards.py"
    cmd = [
        sys.executable,
        str(tool_path),
        "up",
        "--count",
        str(shard_count),
        "--mcp-base-port",
        base_port,
        "--shards",
        _format_shard_indices(missing_shards),
    ]
    print(
        "[expert_main] 부족한 로컬 MCP/WARP shard 자동 증분 기동: "
        f"missing={_format_shard_indices(missing_shards)} (target_count={shard_count})",
        file=sys.stderr,
        flush=True,
    )
    env = os.environ.copy()
    env.setdefault("WARP_SHARDS_PRINT_ENDPOINTS", "0")
    env["WARP_SHARDS_REMOVE_ORPHANS"] = "0"
    env["WARP_SHARDS_NO_RECREATE"] = "1"
    subprocess.run(cmd, cwd=repo_root, check=True, env=env)
    print(
        "[expert_main] 부족한 로컬 MCP/WARP shard 자동 증분 기동 완료: "
        f"missing={_format_shard_indices(missing_shards)}",
        file=sys.stderr,
        flush=True,
    )


def _auto_up_local_shards(repo_root: Path, shard_count: int) -> None:
    if shard_count <= 0 or not _can_auto_manage_local_shards():
        return
    if _env_bool_runtime("MCP_AUTO_UP_REUSE_HEALTHY", True):
        try:
            items = _load_local_shard_status(repo_root)
            ready_indices = _collect_ready_warp_shard_indices(items, required_count=shard_count)
            if len(ready_indices) >= shard_count:
                print(
                    f"[expert_main] 로컬 MCP/WARP shard {shard_count}개 이미 healthy → 자동 기동 생략",
                    file=sys.stderr,
                    flush=True,
                )
                return
        except Exception as exc:
            print(
                f"[expert_main] shard healthy 재사용 확인 실패: {exc} → 자동 기동 계속",
                file=sys.stderr,
                flush=True,
            )
    if not _allow_local_shard_auto_up():
        print(
            "[expert_main] 로컬 MCP/WARP shard 자동 기동 생략: "
            "policy=docker-lifecycle-explicit-opt-in",
            file=sys.stderr,
            flush=True,
        )
        return

    base_port = os.getenv("MCP_SHARD_BASE_PORT", "3333").strip() or "3333"
    tool_path = repo_root / "tools" / "warp_shards.py"
    cmd = [
        sys.executable,
        str(tool_path),
        "up",
        "--count",
        str(shard_count),
        "--mcp-base-port",
        base_port,
    ]
    print(
        f"[expert_main] 로컬 MCP/WARP shard {shard_count}개 자동 기동 중...",
        file=sys.stderr,
        flush=True,
    )
    env = os.environ.copy()
    env.setdefault("WARP_SHARDS_PRINT_ENDPOINTS", "0")
    subprocess.run(cmd, cwd=repo_root, check=True, env=env)
    print(
        f"[expert_main] 로컬 MCP/WARP shard {shard_count}개 자동 기동 완료",
        file=sys.stderr,
        flush=True,
    )


def _load_local_shard_status(repo_root: Path) -> List[Dict[str, Any]]:
    tool_path = repo_root / "tools" / "warp_shards.py"
    cmd = [sys.executable, str(tool_path), "status", "--json"]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = proc.stdout.strip()
    if not payload:
        raise RuntimeError("empty shard status payload")

    items = json.loads(payload)
    if not isinstance(items, list):
        raise RuntimeError("invalid shard status payload")
    return items


def _shard_index_from_status_item(item: Dict[str, Any]) -> int:
    try:
        shard_index = int(item.get("shard_index") or 0)
    except Exception:
        shard_index = 0
    if shard_index <= 0:
        service = str(item.get("service") or "").strip()
        if service.startswith("warp-"):
            try:
                shard_index = int(service.split("-", 1)[1])
            except Exception:
                shard_index = 0
    return shard_index


def _collect_ready_warp_shard_indices(
    items: List[Dict[str, Any]],
    *,
    required_count: Optional[int] = None,
) -> List[int]:
    shard_indices: List[int] = []
    for item in items:
        shard_index = _shard_index_from_status_item(item)
        if shard_index <= 0:
            continue
        if required_count is not None and required_count > 0 and shard_index > required_count:
            continue
        trace = item.get("trace") or {}
        if not isinstance(trace, dict):
            trace = {}
        if bool(item.get("running")) and str(trace.get("warp") or "").strip().lower() == "on":
            if shard_index not in shard_indices:
                shard_indices.append(shard_index)
    shard_indices.sort()
    return shard_indices


def _collect_non_warp_on_shards(
    items: List[Dict[str, Any]],
    *,
    required_count: Optional[int] = None,
) -> List[int]:
    shard_indices: List[int] = []
    for item in items:
        shard_index = _shard_index_from_status_item(item)
        if shard_index <= 0:
            continue
        if required_count is not None and required_count > 0 and shard_index > required_count:
            continue

        running = bool(item.get("running"))
        trace = item.get("trace") or {}
        if not isinstance(trace, dict):
            trace = {}
        warp = str(trace.get("warp") or "").strip().lower()
        if (not running) or warp != "on":
            if shard_index not in shard_indices:
                shard_indices.append(shard_index)
    shard_indices.sort()
    return shard_indices


def _summarize_warp_items(
    items: List[Dict[str, Any]],
    *,
    required_count: Optional[int] = None,
) -> str:
    scoped_items: List[Dict[str, Any]] = []
    for item in items or []:
        shard_index = _shard_index_from_status_item(item)
        if required_count is not None and required_count > 0 and shard_index > required_count:
            continue
        scoped_items.append(item)

    total = len(scoped_items)
    running_count = 0
    warp_on_count = 0
    off_samples: List[str] = []
    for item in scoped_items:
        service = str(item.get("service") or "?")
        running = bool(item.get("running"))
        if running:
            running_count += 1
        trace = item.get("trace") or {}
        if not isinstance(trace, dict):
            trace = {}
        warp = str(trace.get("warp") or "?").strip().lower()
        if warp == "on":
            warp_on_count += 1
        elif len(off_samples) < 8:
            off_samples.append(f"{service}:running={'yes' if running else 'no'},warp={warp or '?'}")
    sample_text = f", not_ready_sample={off_samples}" if off_samples else ""
    return f"running={running_count}/{total}, warp_on={warp_on_count}/{total}{sample_text}"


def _format_shard_indices(shard_indices: List[int]) -> str:
    if not shard_indices:
        return "-"
    ranges: List[str] = []
    start = shard_indices[0]
    end = shard_indices[0]
    for idx in shard_indices[1:]:
        if idx == end + 1:
            end = idx
            continue
        ranges.append(str(start) if start == end else f"{start}-{end}")
        start = end = idx
    ranges.append(str(start) if start == end else f"{start}-{end}")
    return ",".join(ranges)


def _endpoint_to_local_shard_index(endpoint: str) -> Optional[int]:
    try:
        port = urlsplit(str(endpoint or "")).port
    except Exception:
        port = None
    if port is None:
        return None
    try:
        base_port = int(os.getenv("MCP_SHARD_BASE_PORT", "3333"))
    except Exception:
        base_port = 3333
    shard_index = port - base_port + 1
    if shard_index <= 0:
        return None
    return shard_index


def _recreate_local_shards(repo_root: Path, shard_indices: List[int]) -> None:
    if not shard_indices:
        return
    if not _allow_local_shard_recreate():
        print(
            "[expert_main] WARP shard 재생성 생략: "
            f"shards={_format_shard_indices(shard_indices)}, "
            "policy=docker-lifecycle-explicit-opt-in",
            file=sys.stderr,
            flush=True,
        )
        return
    tool_path = repo_root / "tools" / "warp_shards.py"
    cmd = [
        sys.executable,
        str(tool_path),
        "recreate",
        "--shards",
        _format_shard_indices(shard_indices),
    ]
    print(
        f"[expert_main] WARP shard 재생성 실행: shards={_format_shard_indices(shard_indices)}",
        file=sys.stderr,
        flush=True,
    )
    subprocess.run(cmd, cwd=repo_root, check=True)


def _ensure_local_shards_warp_on(
    repo_root: Path,
    *,
    required_count: Optional[int] = None,
) -> List[Dict[str, Any]]:
    attempt = 0
    pause_sec_raw = os.getenv("WARP_SHARDS_ENSURE_PAUSE_SEC", "5").strip()
    try:
        pause_sec = max(0.0, float(pause_sec_raw))
    except Exception:
        pause_sec = 5.0
    max_attempts_raw = os.getenv("WARP_SHARDS_ENSURE_MAX_ATTEMPTS", "0").strip()
    try:
        max_attempts = max(0, int(max_attempts_raw))
    except Exception:
        max_attempts = 0

    while True:
        attempt += 1
        print(
            f"[expert_main] WARP 상태 확인 중... attempt={attempt}"
            + (f"/{max_attempts}" if max_attempts > 0 else ""),
            file=sys.stderr,
            flush=True,
        )
        items = _load_local_shard_status(repo_root)
        not_ready = _collect_non_warp_on_shards(items, required_count=required_count)
        print(
            f"[expert_main] WARP 상태 요약: {_summarize_warp_items(items, required_count=required_count)}",
            file=sys.stderr,
            flush=True,
        )
        if not not_ready:
            print(
                f"[expert_main] 모든 WARP shard가 정상 연결됨 (attempt={attempt})",
                file=sys.stderr,
                flush=True,
            )
            return items

        print(
            "[expert_main] WARP 미연결 shard 감지: {shards} (attempt={attempt})".format(
                shards=_format_shard_indices(not_ready),
                attempt=attempt,
            ),
            file=sys.stderr,
            flush=True,
        )
        if max_attempts > 0 and attempt >= max_attempts:
            raise RuntimeError(
                "WARP shard가 끝내 연결되지 않았습니다: "
                f"{_format_shard_indices(not_ready)} (attempt={attempt})"
            )
        if not _allow_local_shard_recreate():
            print(
                "[expert_main] WARP shard 자동 재생성 비활성화: "
                f"not_ready={_format_shard_indices(not_ready)}",
                file=sys.stderr,
                flush=True,
            )
            return items

        _recreate_local_shards(repo_root, not_ready)
        if pause_sec > 0:
            print(
                f"[expert_main] WARP 재확인 대기: {pause_sec:.1f}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(pause_sec)


def _memo_local_shard_status(repo_root: Path, memo_path: Path, items: Optional[List[Dict[str, Any]]] = None) -> None:
    if items is None:
        items = _load_local_shard_status(repo_root)
    memo_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[expert_main] WARP shard 메모 저장: {memo_path}", file=sys.stderr, flush=True)
    for item in items:
        service = str(item.get("service") or "?")
        running = bool(item.get("running"))
        trace = item.get("trace") or {}
        if not isinstance(trace, dict):
            trace = {}
        ip = trace.get("ip", "?")
        warp = trace.get("warp", "?")
        loc = trace.get("loc", "?")
        colo = trace.get("colo", "?")
        print(
            f"[expert_main] {service}: running={'yes' if running else 'no'}, ip={ip}, warp={warp}, loc={loc}, colo={colo}",
            file=sys.stderr,
            flush=True,
        )


def main() -> None:
    global _PARALLEL, _INPUT_POST_COUNT
    repo_root = Path(__file__).resolve().parent

    # PowerShell/Windows 콘솔/리다이렉트 인코딩 이슈 완화
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # ===== 사용자 환경에 맞게 여기만 수정 =====
    # 명령줄 인자로 입력 파일 지정 가능
    if _CLI_ARGS.input:
        INPUT_PATH = Path(_CLI_ARGS.input)
    else:
        #INPUT_PATH = repo_root / "tests" / "inputs" / "sample.jsonl"
        INPUT_PATH = repo_root / "tests" / "inputs" / "test01.jsonl"
    
    LOG_DIR = repo_root / "logs"
    OUT_DIR = repo_root / "out"
    LIMIT = None  # 디버그 시 숫자 지정, 전체 돌리려면 None

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_PATH}")

    input_nonempty_lines = _count_nonempty_jsonl_lines(INPUT_PATH)
    posts = load_jsonl_posts(INPUT_PATH)
    if input_nonempty_lines and not posts:
        raise ValueError(
            "입력 JSONL에 내용이 있지만 로드된 post가 0개입니다. "
            "post_id/content_blocks 또는 post_id/content 형식과 UTF-8/BOM 상태를 확인하세요."
        )
    if LIMIT:
        posts = posts[:LIMIT]

    _INPUT_POST_COUNT = len(posts)
    _effective_parallel = _effective_parallel_for_post_count(len(posts))
    _parallel_adjusted = _effective_parallel != _REQUESTED_PARALLEL
    _PARALLEL = _effective_parallel

    # ===== LLM 실행 환경 선택 =====
    # "local": 로컬 llama-cpp-python (GPU 필요)
    # "remote": 원격 llama-server 또는 vLLM
    LLM_MODE = "remote"  # "local" or "remote"
    # 서빙 엔진 선택: "llama" (llama-server/llama.cpp) 또는 "vllm" (vLLM)
    #LLM_SERVER_TYPE = _CLI_ARGS.server_type or os.getenv("LLM_SERVER_TYPE", "llama")
    LLM_SERVER_TYPE = _CLI_ARGS.server_type or os.getenv("LLM_SERVER_TYPE", "vllm")

    # MCP(SearchXNG/Crawl4AI shard)
    # 외부에서 MCP_ENDPOINTS를 넘기면 워커별 shard 분산을 그대로 사용한다.
    _configure_mcp_endpoints(_PARALLEL)

    # ===== LLM 공통 설정 (main.py와 동일) =====
    _set_env("LLM_N_CTX", "131072")
    # 컨텍스트 경고/가드 기준을 실제 n_ctx와 맞춘다.  (vLLM --max-model-len 131072 대응)
    _set_env("LLM_CONTEXT_LIMIT_TOKENS", os.environ.get("LLM_N_CTX", "131072"))
    _set_env("LLM_MAX_TOKENS", "65536")
    _set_env("LLM_EXPERT_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536"))
    _set_env("LLM_VERIFIER_MAX_TOKENS", os.environ.get("LLM_VERIFIER_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536")))
    _set_env("LLM_VERIFIER_COMPACT_MAX_TOKENS", os.environ.get("LLM_VERIFIER_COMPACT_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536")))
    _set_env("LLM_RELATION_JUDGE_MAX_TOKENS", os.environ.get("LLM_RELATION_JUDGE_MAX_TOKENS", os.environ.get("LLM_EXPERT_MAX_TOKENS", "65536")))
    _set_env("LLM_REASON_REVIEW_MAX_TOKENS", os.environ.get("LLM_REASON_REVIEW_MAX_TOKENS", os.environ.get("LLM_MAX_TOKENS", "65536")))
    _set_env("LLM_JSON_GRAMMAR", "1")
    _set_env("LLM_PROGRESS_EVERY", "5")
    _set_env("LLM_MAX_SEARCH_ROUNDS", "6")
    # 검색 증강 제한 기본 해제: 커뮤니티 글 recall 확보 우선
    _set_env("LLM_MAX_SEARCH_QUERIES", "200")
    _set_env("LLM_ENABLE_SEARCH_SUPPRESSION", "0")
    _set_env("LLM_FLASH_ATTN", "1")
    _set_env("LLM_CACHE_TYPE_K", "q4_0")
    _set_env("LLM_CACHE_TYPE_V", "q4_0")
    _set_env("LLM_PRINT_TIMINGS", "1")
    _set_env("MCP_TOP_K_RESULTS", "10")  # 검색 결과 상위 10개 사용
    _set_env("MCP_DEFAULT_NUM_RESULTS", "15")  # SearXNG에서 15개 요청
    _set_env("MCP_MAX_CONTENT_CHARS", "0")
    _set_env("PIPELINE_FETCH_CONCURRENCY", os.getenv("PIPELINE_FETCH_CONCURRENCY", "4"))
    _set_env("PIPELINE_SEARCH_CONCURRENCY", os.getenv("PIPELINE_SEARCH_CONCURRENCY", "2"))
    
    # ===== 스트리밍 및 디버그 설정 (main.py와 동일) =====
    _set_env("LLM_DEBUG_DUMP_MESSAGES", os.environ.get("LLM_DEBUG_DUMP_MESSAGES", "0"))
    _set_env("LLM_DEBUG_DUMP_MAX_CHARS", os.environ.get("LLM_DEBUG_DUMP_MAX_CHARS", "0"))
    _set_env("LLM_STREAM", "1")
    _set_env("LLM_VLM", _resolve_toggle(_CLI_ARGS.vlm, env_key="LLM_VLM", default="0"))
    _set_env("LLM_OCR", _resolve_toggle(_CLI_ARGS.ocr, env_key="LLM_OCR", default="1"))
    image_post_count = _count_image_posts(posts)
    image_post_sample_post_ids = _image_post_sample_post_ids(posts)
    vlm_enabled = _env_toggle_enabled("LLM_VLM", "0")
    ocr_enabled = _env_toggle_enabled("LLM_OCR", "1")
    vlm_ocr_semantic_review_ready = image_post_count == 0 or (vlm_enabled and ocr_enabled)
    vlm_ocr_semantic_review_skip_reason_codes = _vlm_ocr_semantic_review_skip_reasons(
        image_post_count=image_post_count,
        vlm_enabled=vlm_enabled,
        ocr_enabled=ocr_enabled,
    )
    require_vlm_ocr_for_image_posts = _require_vlm_ocr_for_image_posts()
    if image_post_count and not vlm_ocr_semantic_review_ready:
        print(
            "[config] WARNING: image posts are present but VLM/OCR is not fully enabled; "
            "this run is text-only for visual evidence and must not be used for semantic image approval. "
            f"image_post_count={image_post_count}, vlm={os.getenv('LLM_VLM', '0')}, "
            f"ocr={os.getenv('LLM_OCR', '1')}, skip_reasons={vlm_ocr_semantic_review_skip_reason_codes}",
            file=sys.stderr,
            flush=True,
        )
        if require_vlm_ocr_for_image_posts:
            print(
                "[config] ERROR: --require-vlm-ocr-for-images is set and image posts require "
                "--vlm on --ocr on before semantic/VLM review can run.",
                file=sys.stderr,
                flush=True,
            )
            raise SystemExit(2)
    _set_env(
        "LLM_SUSPEND_ON_SERVER_ANOMALY",
        _resolve_toggle(
            _CLI_ARGS.llm_suspend_on_anomaly,
            env_key="LLM_SUSPEND_ON_SERVER_ANOMALY",
            default="1",
        ),
    )
    _set_env(
        "LLM_SUSPEND_FAILURE_THRESHOLD",
        str(
            _CLI_ARGS.llm_suspend_threshold
            if _CLI_ARGS.llm_suspend_threshold is not None
            else os.getenv("LLM_SUSPEND_FAILURE_THRESHOLD", "3")
        ),
    )
    if _CLI_ARGS.llm_stream_first_token_timeout is not None:
        _set_env("LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS", str(_CLI_ARGS.llm_stream_first_token_timeout))
    if _CLI_ARGS.llm_stream_idle_timeout is not None:
        _set_env("LLM_STREAM_IDLE_TIMEOUT_SECONDS", str(_CLI_ARGS.llm_stream_idle_timeout))
    _set_env(
        "LLM_VLM_FETCH_TIMEOUT",
        str(_CLI_ARGS.vlm_fetch_timeout if _CLI_ARGS.vlm_fetch_timeout is not None else os.getenv("LLM_VLM_FETCH_TIMEOUT", "12")),
    )
    _set_env(
        "LLM_VLM_MAX_IMAGE_BYTES",
        str(_CLI_ARGS.vlm_max_image_bytes if _CLI_ARGS.vlm_max_image_bytes is not None else os.getenv("LLM_VLM_MAX_IMAGE_BYTES", _DEFAULT_VLM_MAX_IMAGE_BYTES)),
    )
    _set_env(
        "LLM_VLM_MAX_TOTAL_BYTES",
        str(_CLI_ARGS.vlm_max_total_bytes if _CLI_ARGS.vlm_max_total_bytes is not None else os.getenv("LLM_VLM_MAX_TOTAL_BYTES", "50331648")),
    )
    _set_env(
        "LLM_VLM_CHUNK_MAX_IMAGES",
        str(_CLI_ARGS.vlm_chunk_max_images if _CLI_ARGS.vlm_chunk_max_images is not None else os.getenv("LLM_VLM_CHUNK_MAX_IMAGES", "8")),
    )
    _set_env(
        "LLM_VLM_CHUNK_MAX_BYTES",
        str(_CLI_ARGS.vlm_chunk_max_bytes if _CLI_ARGS.vlm_chunk_max_bytes is not None else os.getenv("LLM_VLM_CHUNK_MAX_BYTES", "12582912")),
    )
    _set_env("LLM_VLM_MAX_TOKENS", os.environ.get("LLM_VLM_MAX_TOKENS", "12288"))
    _set_env("PIPELINE_SLANG_DB", _resolve_toggle(_CLI_ARGS.slang_db, env_key="PIPELINE_SLANG_DB", default="0"))
    _set_env(
        "PIPELINE_SLANG_DB_PATH",
        str(_CLI_ARGS.slang_db_path if _CLI_ARGS.slang_db_path is not None else os.getenv("PIPELINE_SLANG_DB_PATH", "slang_db/slang_db.json")),
    )
    _set_env(
        "PIPELINE_SLANG_DB_FLUSH_POSTS",
        str(_CLI_ARGS.slang_db_flush_posts if _CLI_ARGS.slang_db_flush_posts is not None else os.getenv("PIPELINE_SLANG_DB_FLUSH_POSTS", "1")),
    )
    _set_env(
        "PIPELINE_SLANG_DB_FLUSH_SECONDS",
        str(_CLI_ARGS.slang_db_flush_seconds if _CLI_ARGS.slang_db_flush_seconds is not None else os.getenv("PIPELINE_SLANG_DB_FLUSH_SECONDS", "0")),
    )
    
    # GLM-4.7-Flash reasoning 모드 제어
    _set_env("LLM_ENABLE_THINKING", "0")
    _set_env("LLM_THINK_STREAM", "1")

    if LLM_MODE == "local":
        # ===== Local: llama-cpp-python =====
        _set_env("LLM_BACKEND", "local")
        _set_env(
            "LLM_MODEL_PATH",
            r"C:\Users\kimjang\AppData\Local\llama.cpp\unsloth_GLM-4.7-Flash-GGUF_GLM-4.7-Flash-UD-IQ3_XXS.gguf",
        )
        _set_env("LLM_N_GPU_LAYERS", "60")
        _set_env("LLM_PRINT_SYSTEM_INFO", "1")
        # vocab_only probe 비활성화 (컨텍스트 생성 충돌 방지)
        _set_env("LLM_USE_GGUF_JINJA", "0")
    elif LLM_MODE == "remote":
        # ===== Remote: llama-server 또는 vLLM =====
        _set_env("LLM_BACKEND", "http")
        _set_env("LLM_SERVER_TYPE", LLM_SERVER_TYPE)  # "llama" or "vllm"
        
        if LLM_SERVER_TYPE == "vllm":
            # ===== vLLM 서빙 =====
            #_set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://localhost:20000/"))
            #_set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://a100:10000/"))
            _set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://10.20.0.101:8000/"))
            # 참고용 기존 Qwen 설정
            #_set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "Sehyo/Qwen3.5-35B-A3B-NVFP4"))
            #_set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "AxionML/Qwen3.5-35B-A3B-NVFP4"))
            _set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4"))
            #_set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "bg-digitalservices/Gemma-4-E4B-it-NVFP4"))
            #_set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"))
            # vLLM 전용 샘플링 기본값
            # 작은 모델은 애매한 title/slang을 그럴듯하게 채우는 경향이 있어
            # 기본값을 보수적으로 둔다. 필요하면 환경변수로 즉시 override 가능.
            _set_env("LLM_TEMP", os.getenv("LLM_TEMP", "0.35"))
            _set_env("LLM_TOP_P", os.getenv("LLM_TOP_P", "0.8"))
            _set_env("LLM_MIN_P", os.getenv("LLM_MIN_P", "0.0"))
            _set_env("LLM_REPEAT_PENALTY", os.getenv("LLM_REPEAT_PENALTY", "1.0"))
            _set_env("LLM_VLLM_TOP_K", os.getenv("LLM_VLLM_TOP_K", "20"))
            _set_env("LLM_VLLM_PRESENCE_PENALTY", os.getenv("LLM_VLLM_PRESENCE_PENALTY", "1.5"))
            
            # ===== 전문가별 temperature =====
            # 기본 temperature는 보수적으로 통일하고, 필요하면 전문가별로 오버라이드한다.
            # 환경변수로 오버라이드 가능: LLM_TEMP_{EXPERT} (예: LLM_TEMP_DECODER=0.4)
            _DEFAULT_EXPERT_TEMP = os.getenv("LLM_DEFAULT_EXPERT_TEMP", "0.35")
            _set_env("LLM_TEMP_GATEKEEPER", os.getenv("LLM_TEMP_GATEKEEPER", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_DISCOURSE", os.getenv("LLM_TEMP_DISCOURSE", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_DECODER", os.getenv("LLM_TEMP_DECODER", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_VERIFIER", os.getenv("LLM_TEMP_VERIFIER", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_CRITIC", os.getenv("LLM_TEMP_CRITIC", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_SYNTHESIZER", os.getenv("LLM_TEMP_SYNTHESIZER", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_ARBITER", os.getenv("LLM_TEMP_ARBITER", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_JURY", os.getenv("LLM_TEMP_JURY", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_ADVOCATE", os.getenv("LLM_TEMP_ADVOCATE", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_SKEPTIC", os.getenv("LLM_TEMP_SKEPTIC", _DEFAULT_EXPERT_TEMP))
            _set_env("LLM_TEMP_JUDGE", os.getenv("LLM_TEMP_JUDGE", _DEFAULT_EXPERT_TEMP))
        else:
            # ===== llama-server 서빙 (기본) =====
            _set_env("LLM_ENDPOINT", _CLI_ARGS.llm_endpoint or os.getenv("LLM_ENDPOINT", "http://a100:10000/"))
            # 참고용 기존 Qwen GGUF 설정
            #_set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "unsloth/Qwen3.5-35B-A3B-GGUF:UD-IQ3_XXS"))
            _set_env("LLM_MODEL", _CLI_ARGS.llm_model or os.getenv("LLM_MODEL", "google/gemma-4-26B-A4B-it"))
        #_set_env("LLM_ENDPOINT", "https://llama.kimjang.me")
        #_set_env("LLM_ENDPOINT", "http://127.0.0.1:20000/")
    else:
        raise ValueError(f"Unknown LLM_MODE: {LLM_MODE}. Use 'local' or 'remote'.")

    # 서빙 엔진 로그
    _srv = os.getenv('LLM_SERVER_TYPE', 'llama')
    _ep = os.getenv('LLM_ENDPOINT', '?')
    _mdl = os.getenv('LLM_MODEL', '?')
    print(f"[config] server_type={_srv}, endpoint={_ep}, model={_mdl}", file=sys.stderr, flush=True)
    print(
        "[config] vlm={vlm}, ocr={ocr}, fetch_timeout={timeout}, max_image_bytes={img}, "
        "max_total_bytes={total}, chunk_max_images={chunk_i}, chunk_max_bytes={chunk_b}".format(
            vlm=os.getenv("LLM_VLM", "0"),
            ocr=os.getenv("LLM_OCR", "1"),
            timeout=os.getenv("LLM_VLM_FETCH_TIMEOUT", "12"),
            img=os.getenv("LLM_VLM_MAX_IMAGE_BYTES", _DEFAULT_VLM_MAX_IMAGE_BYTES),
            total=os.getenv("LLM_VLM_MAX_TOTAL_BYTES", "50331648"),
            chunk_i=os.getenv("LLM_VLM_CHUNK_MAX_IMAGES", "8"),
            chunk_b=os.getenv("LLM_VLM_CHUNK_MAX_BYTES", "12582912"),
        ),
        file=sys.stderr,
        flush=True,
    )
    print(
        "[config] llm_suspend_on_anomaly={enabled}, llm_suspend_threshold={threshold}".format(
            enabled=os.getenv("LLM_SUSPEND_ON_SERVER_ANOMALY", "1"),
            threshold=os.getenv("LLM_SUSPEND_FAILURE_THRESHOLD", "3"),
        ),
        file=sys.stderr,
        flush=True,
    )
    print(f"[config] python={sys.executable}", file=sys.stderr, flush=True)
    print(
        f"[config] virtual_env={os.getenv('VIRTUAL_ENV', '(none)')}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"[config] mcp_shard_lifecycle_policy={_SHARD_LIFECYCLE_POLICY_LABEL}, "
        f"auto_up={_allow_local_shard_auto_up()}, auto_recreate={_allow_local_shard_recreate()}, "
        f"auto_scale_up_missing={_allow_missing_shard_auto_scale_up()}, "
        f"small_run={_is_small_targeted_run()}, small_run_lifecycle_blocked={_small_run_shard_lifecycle_blocked()}, "
        f"command_lifecycle_allowed={_command_shard_lifecycle_allowed_by_context()}, "
        f"codex_run={_interactive_codex_run()}, env_lifecycle_requested={_env_shard_lifecycle_requested()}, "
        f"env_lifecycle_allowed={_env_shard_lifecycle_allowed()}, "
        f"status_audit_requested={_local_shard_status_audit_requested()}, "
        f"status_audit_allowed={_local_shard_status_audit_allowed()}, "
        f"lifecycle_threshold={_shard_lifecycle_block_threshold()}, run_posts={_current_run_post_count_for_lifecycle()}",
        file=sys.stderr,
        flush=True,
    )
    print(
        "[config] slang_db={enabled}, path={path}, flush_posts={posts}, flush_seconds={seconds}".format(
            enabled=os.getenv("PIPELINE_SLANG_DB", "0"),
            path=os.getenv("PIPELINE_SLANG_DB_PATH", "slang_db/slang_db.json"),
            posts=os.getenv("PIPELINE_SLANG_DB_FLUSH_POSTS", "1"),
            seconds=os.getenv("PIPELINE_SLANG_DB_FLUSH_SECONDS", "0"),
        ),
        file=sys.stderr,
        flush=True,
    )
    # ===== 아래는 보통 건드릴 필요 없음 =====
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Input not found: {INPUT_PATH}")

    # 디렉토리 생성
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 타임스탬프 기반 파일명
    # 초 단위만 쓰면 같은 초에 두 런이 시작될 때 로그/결과 파일이 충돌한다.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    import hashlib
    _prompt_version = os.getenv("PIPELINE_PROMPT_VERSION", "2026-03-30-semantic-contract-v1").strip() or "unknown"
    _reuse_health_filter_meta: Dict[str, Any] = {}

    def _parallel_policy_text() -> str:
        requested_term = "requested_parallel"
        if _MODEL_PARALLEL_MAX:
            requested_term = "min(requested_parallel_raw,model_parallel_max)"
        if (
            _reuse_health_filter_meta.get("mcp_healthy_endpoint_filter")
            or _reuse_health_filter_meta.get("mcp_healthy_autogen_endpoint_filter")
        ):
            return f"effective_parallel=min({requested_term},input_post_count,healthy_mcp_endpoint_count)"
        return f"effective_parallel=min({requested_term},input_post_count)"

    _run_config_payload = {
        "llm_mode": LLM_MODE,
        "server_type": LLM_SERVER_TYPE,
        "llm_endpoint": os.getenv("LLM_ENDPOINT", ""),
        "llm_model": os.getenv("LLM_MODEL", ""),
        "parallel": _PARALLEL,
        "requested_parallel_raw": _REQUESTED_PARALLEL_RAW,
        "requested_parallel": _REQUESTED_PARALLEL,
        "effective_parallel": _PARALLEL,
        "parallel_policy": _parallel_policy_text(),
        "model_parallel_max": _MODEL_PARALLEL_MAX,
        "model_parallel_cap_applied": _MODEL_PARALLEL_CAP_APPLIED,
        "model_parallel_cap_model": _PARALLEL_POLICY_MODEL,
        "input_post_count": len(posts),
        "mcp_endpoints": os.getenv("MCP_ENDPOINTS", os.getenv("MCP_ENDPOINT", "")),
        "mcp_auto_up_shards": _allow_local_shard_auto_up(),
        "mcp_auto_recreate_shards": _allow_local_shard_recreate(),
        "mcp_auto_scale_up_missing_shards": _allow_missing_shard_auto_scale_up(),
        "mcp_local_shard_management_enabled": _can_auto_manage_local_shards(),
        "mcp_local_shard_status_audit": _local_shard_status_audit_allowed(),
        "mcp_local_shard_status_audit_requested": _local_shard_status_audit_requested(),
        "mcp_local_shard_status_audit_allowed": _local_shard_status_audit_allowed(),
        "mcp_shard_lifecycle_policy": _SHARD_LIFECYCLE_POLICY_LABEL,
        "mcp_allow_goal_shard_lifecycle": bool(getattr(_CLI_ARGS, "allow_goal_shard_lifecycle", False)),
        "mcp_command_shard_lifecycle_allowed": _command_shard_lifecycle_allowed_by_context(),
        "mcp_interactive_codex_run": _interactive_codex_run(),
        "mcp_env_shard_lifecycle_requested": _env_shard_lifecycle_requested(),
        "mcp_env_shard_lifecycle_global_opt_in": _env_shard_lifecycle_global_opt_in(),
        "mcp_env_shard_lifecycle_allowed": _env_shard_lifecycle_allowed(),
        "mcp_env_shard_lifecycle_blocked_by_context": _env_shard_lifecycle_blocked_by_context(),
        "mcp_shard_lifecycle_block_threshold": _shard_lifecycle_block_threshold(),
        "mcp_run_post_count_for_lifecycle": _current_run_post_count_for_lifecycle(),
        "mcp_small_targeted_run": _is_small_targeted_run(),
        "mcp_small_run_shard_lifecycle_blocked": _small_run_shard_lifecycle_blocked(),
        "slang_db": os.getenv("PIPELINE_SLANG_DB", "0"),
        "reason_full_mode": os.getenv("PIPELINE_REASON_FULL_MODE", os.getenv("REASON_FULL_MODE", "1")),
        "prompt_version": _prompt_version,
    }
    _config_hash = hashlib.sha256(
        json.dumps(_run_config_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    log_path = LOG_DIR / f"expert_run_{ts}.log"
    if _CLI_ARGS.output:
        out_result_path = Path(_CLI_ARGS.output)
        out_result_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_result_path = OUT_DIR / f"expert_result_{ts}.json"
    checkpoint_jsonl_path = out_result_path.with_name(out_result_path.stem + "_checkpoint.jsonl")
    pending_snapshot_path = out_result_path.with_name(out_result_path.stem + "_pending_snapshot.json")
    completed_subset_path = out_result_path.with_name(out_result_path.stem + "_completed_subset.json")
    completed_subset_manifest_path = out_result_path.with_name(
        out_result_path.stem + "_completed_subset_manifest.json"
    )
    result_manifest_path = out_result_path.with_name(out_result_path.stem + "_manifest.json")

    _orig_out = sys.stdout
    _orig_err = sys.stderr

    for _stream_name, _stream in (("stdout", _orig_out), ("stderr", _orig_err)):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    class _Tee:
        """stdout/stderr를 파일과 콘솔 동시 출력 + 대시보드 로그 포워딩
        
        병렬 모드:
          - 워커 스레드 출력 → 워커별 로그 파일 + 통합 로그 (콘솔 억제)
          - 메인 스레드 출력 → 콘솔 + 통합 로그 (기존 동작)
        """
        def __init__(self, console_stream, file_stream):
            self._console = console_stream  # _orig_err
            self._file = file_stream        # 통합 로그 파일
            self._monitor = None
            self._log_buf = ""  # 라인 버퍼 (줄바꿈 단위로 flush)
            self._worker_bufs = {}  # thread_id → buf (워커별 버퍼)
            if not _NO_DASHBOARD:
                try:
                    from llm_batch.monitor.event_bus import monitor as _mon
                    self._monitor = _mon
                except Exception:
                    pass

        def write(self, s):
            if not s:
                return 0
            wrote = len(s) if isinstance(s, str) else 0

            # 통합 로그 파일에는 항상 기록
            try:
                self._file.write(s)
            except Exception:
                pass

            # 병렬 모드: 메인 스레드만 콘솔 출력 (워커 + 서브스레드 모두 억제)
            _is_main = threading.get_ident() == _main_thread_id
            if _parallel_mode and not _is_main:
                # 비-메인 스레드 (워커 및 jury 서브스레드): 콘솔 억제
                worker_log = getattr(_worker_tls, 'log_file', None)
                if worker_log is not None:
                    try:
                        worker_log.write(s)
                    except Exception:
                        pass
                # 통합 로그에는 이미 기록됨, 콘솔 생략
            else:
                # 메인 스레드 또는 순차 모드: 콘솔에 출력
                try:
                    self._console.write(s)
                except Exception:
                    pass

            # 초기 import 타이밍 이슈로 monitor가 비어있을 수 있으므로 lazy attach
            if self._monitor is None and not _NO_DASHBOARD:
                try:
                    from llm_batch.monitor.event_bus import monitor as _mon
                    self._monitor = _mon
                except Exception:
                    pass

            # 대시보드 로그 포워딩 — 줄바꿈 단위로 버퍼링
            if self._monitor:
                try:
                    tid = threading.get_ident()
                    buf = self._worker_bufs.get(tid, "")
                    buf += s
                    wid = getattr(_worker_tls, 'worker_id', -1)
                    while "\n" in buf:
                        line, buf = buf.split("\n", 1)
                        if line.strip():
                            self._monitor.add_log(line, worker_id=wid)
                    self._worker_bufs[tid] = buf
                except Exception:
                    pass
            return wrote

        def flush(self):
            try:
                self._file.flush()
            except Exception:
                pass
            worker_log = getattr(_worker_tls, 'log_file', None)
            if worker_log:
                try:
                    worker_log.flush()
                except Exception:
                    pass
            _is_main = threading.get_ident() == _main_thread_id
            if not (_parallel_mode and not _is_main):
                try:
                    self._console.flush()
                except Exception:
                    pass

        def isatty(self):
            try:
                return self._console.isatty()
            except Exception:
                return False

        @property
        def encoding(self):
            enc = getattr(self._console, "encoding", None)
            return enc or "utf-8"

        def reconfigure(self, **kwargs):
            for st in [self._console, self._file]:
                try:
                    rc = getattr(st, "reconfigure", None)
                    if callable(rc):
                        rc(**kwargs)
                except Exception:
                    pass

    # UTF-8-SIG(BOM)로 저장하면 Windows 메모장에서도 한글이 안 깨짐
    with log_path.open("w", encoding="utf-8-sig", buffering=1, newline="") as f:
        sys.stdout = _Tee(_orig_out, f)
        sys.stderr = _Tee(_orig_err, f)

        _dashboard_forwarder = None
        try:
            # 대시보드 서버 기동 (외부 standalone 대시보드 감지 시 양보 + 포워딩)
            if not _NO_DASHBOARD:
                try:
                    sys.path.insert(0, str(repo_root / "src"))
                    from llm_batch.monitor.event_bus import monitor as _monitor
                    _dash_port = int(os.environ.get("DASHBOARD_PORT", "8080"))
                    _ext_dash_url = _detect_external_dashboard(_dash_port)
                    if _ext_dash_url:
                        # 외부 standalone 대시보드 발견 → 내장 기동 생략, 이벤트 포워딩.
                        # expert_main이 종료해도 대시보드는 계속 살아 있다.
                        from llm_batch.monitor.forwarder import DashboardForwarder
                        _dashboard_forwarder = DashboardForwarder(
                            _ext_dash_url,
                            monitor=_monitor,
                            ingest_token=os.environ.get("DASHBOARD_INGEST_TOKEN", "").strip(),
                        )
                        _dashboard_forwarder.start()
                        _monitor.attach_forwarder(_dashboard_forwarder)
                    else:
                        from llm_batch.monitor.server import start_dashboard
                        _dash_thread = start_dashboard(port=_dash_port)
                        _dash_actual_port = int(getattr(_dash_thread, "dashboard_port", _dash_port))
                    # _Tee가 초기에 monitor import를 놓쳐도 즉시 연결되도록 재주입
                    for _tee_stream in (sys.stdout, sys.stderr):
                        try:
                            if hasattr(_tee_stream, "_monitor"):
                                setattr(_tee_stream, "_monitor", _monitor)
                        except Exception:
                            pass
                    # sys.stderr(_Tee)로 출력해 콘솔+로그 파일 모두에 남긴다.
                    if _ext_dash_url:
                        print(
                            f"[expert_main] 📊 외부 대시보드 감지 → 포워딩: {_ext_dash_url} (내장 대시보드 생략)",
                            file=sys.stderr,
                            flush=True,
                        )
                    else:
                        print(
                            f"[expert_main] 📊 Dashboard: http://127.0.0.1:{_dash_actual_port} (bind=0.0.0.0)",
                            file=sys.stderr,
                            flush=True,
                        )
                except Exception as _e:
                    # 실패 원인도 로그 파일에 남겨 실행 중 추적 가능하게 한다.
                    print(f"[expert_main] ⚠️ 대시보드 기동 실패: {_e}", file=sys.stderr, flush=True)
                    _monitor = None
            else:
                _monitor = None

            print(f"[expert_main] 로그 저장: {log_path}", file=sys.stderr, flush=True)
            print(f"[expert_main] 결과 저장: {out_result_path}", file=sys.stderr, flush=True)
            print(f"[expert_main] LLM_MODE: {LLM_MODE}", file=sys.stderr, flush=True)
            print(f"[expert_main] 입력: {INPUT_PATH}", file=sys.stderr, flush=True)
            print(
                f"[expert_main] MCP shards: {_format_mcp_endpoint_pool(_get_mcp_endpoint_pool())}",
                file=sys.stderr,
                flush=True,
            )

            # 프로젝트 src를 path에 추가
            sys.path.insert(0, str(repo_root / "src"))

            from llm_batch.agentic_pipeline import AgenticPipeline
            from llm_batch.llm.client import LLMClient
            from llm_batch.search.client import MCPClient
            from llm_batch.models import PostInput, ContentBlock
            from llm_batch.batch_context import BatchContextMemory
            from llm_batch.slang_db import SlangDBManager, slang_db_alias_seed_is_safe
            from llm_batch.candidate_audit import (
                apply_author_angle_official_detail_canonicalization,
                apply_candidate_audit_fields,
                apply_comment_surface_candidate_hints,
                apply_judge_seed_expected_candidate_preservation,
                apply_judge_seed_hygiene_alias_conflict_guard,
                apply_judge_seed_hygiene_expected_title_guard,
                apply_judge_seed_precision_guard,
                apply_judge_seed_title_image_mismatch_guard,
                apply_judge_seed_title_hygiene_guard,
                apply_judge_seed_trope_boundary_hold_guard,
                apply_judge_seed_unverified_ocr_title_guard,
                apply_judge_seed_wrong_relevance_public_title_guard,
                apply_official_title_promotion_guard,
                apply_post_surface_candidate_hints,
                apply_weak_public_title_bridge_guard,
            )

            print(f"\n{'='*70}", file=sys.stderr, flush=True)
            print(f"🤖 Agentic Pipeline (유기적 전문가 시스템)", file=sys.stderr, flush=True)
            print(f"{'='*70}", file=sys.stderr, flush=True)
            print(f"📂 입력: {INPUT_PATH} ({len(posts)}개 포스트)", file=sys.stderr, flush=True)
            if _MODEL_PARALLEL_MAX:
                print(
                    "[expert_main] model parallel cap: "
                    f"model={_PARALLEL_POLICY_MODEL}, max={_MODEL_PARALLEL_MAX}, "
                    f"requested_raw={_REQUESTED_PARALLEL_RAW}, requested_after_cap={_REQUESTED_PARALLEL}, "
                    f"cap_applied={_MODEL_PARALLEL_CAP_APPLIED}",
                    file=sys.stderr,
                    flush=True,
                )
            if _parallel_adjusted:
                print(
                    "[expert_main] adaptive parallel: "
                    f"requested_raw={_REQUESTED_PARALLEL_RAW}, requested={_REQUESTED_PARALLEL}, "
                    f"input_posts={len(posts)}, effective={_PARALLEL}",
                    file=sys.stderr,
                    flush=True,
                )
            else:
                print(
                    f"[expert_main] parallel: requested_raw={_REQUESTED_PARALLEL_RAW}, "
                    f"requested={_REQUESTED_PARALLEL}, effective={_PARALLEL}",
                    file=sys.stderr,
                    flush=True,
                )

            # ─── 검색 서버 헬스체크 ──────────────────────────
            print(f"\n🔍 검색 서버 연결 확인 중...", file=sys.stderr, flush=True)
            _mcp_endpoint_pool = _get_mcp_endpoint_pool()
            _local_shard_status_items = None
            if _can_auto_manage_local_shards():
                try:
                    _auto_up_local_shards(repo_root, len(_mcp_endpoint_pool))
                except Exception as exc:
                    print(f"[expert_main] ⚠️ shard 자동 기동 실패: {exc}", file=sys.stderr, flush=True)
                _local_shard_status_items = _ensure_local_shards_warp_on(
                    repo_root,
                    required_count=len(_mcp_endpoint_pool),
                )

            _health_failures = []
            _health_ok = {}
            _health_attempts_default = 6 if (_can_auto_manage_local_shards() and _allow_local_shard_recreate()) else 1
            try:
                _health_attempts = max(1, int(os.getenv("MCP_HEALTH_ATTEMPTS", str(_health_attempts_default))))
            except Exception:
                _health_attempts = _health_attempts_default
            try:
                _health_timeout = max(1.0, float(os.getenv("MCP_HEALTH_TIMEOUT_SEC", "8")))
            except Exception:
                _health_timeout = 8.0
            _health_include_search = _env_bool_runtime(
                "MCP_HEALTH_INCLUDE_SEARCH",
                default=_default_mcp_health_include_search(),
            )
            try:
                _health_workers = max(1, min(len(_mcp_endpoint_pool), int(os.getenv("MCP_HEALTH_WORKERS", "12"))))
            except Exception:
                _health_workers = min(len(_mcp_endpoint_pool), 12) or 1
            _health_light_mode = _mcp_goal_run_light_health_mode()
            _health_required_ok = _mcp_health_required_ok_count(_mcp_endpoint_pool)
            _health_probe_batch_size = _mcp_health_probe_batch_size(
                _mcp_endpoint_pool,
                required_ok_count=_health_required_ok,
                health_workers=_health_workers,
            )
            _health_checked_endpoint_count = 0
            _health_probe_stopped_after_required_ok = False
            print(
                f"[expert_main] 검색 서버 헬스체크 시작: endpoints={len(_mcp_endpoint_pool)}, "
                f"attempts={_health_attempts}, timeout={_health_timeout:.1f}s, "
                f"workers={_health_workers}, include_search={_health_include_search}, "
                f"required_ok={_health_required_ok}, batch={_health_probe_batch_size}, "
                f"light_mode={_health_light_mode}",
                file=sys.stderr,
                flush=True,
            )

            def _check_one_endpoint(_idx: int, _endpoint: str):
                _hc_mcp = MCPClient(endpoint=_endpoint)
                _hc = _hc_mcp.health_check(timeout=_health_timeout, include_search=_health_include_search)
                return _idx, _endpoint, _hc

            for _attempt in range(_health_attempts):
                _health_failures = []
                _health_ok = {}
                _health_checked_endpoint_count = 0
                _health_probe_stopped_after_required_ok = False
                print(
                    f"[expert_main] 검색 서버 헬스체크 attempt={_attempt + 1}/{_health_attempts}",
                    file=sys.stderr,
                    flush=True,
                )
                print(
                    f"[expert_main]   병렬 확인 시작... workers={_health_workers}",
                    file=sys.stderr,
                    flush=True,
                )
                _indexed_endpoint_pool = list(enumerate(_mcp_endpoint_pool))
                for _batch_start in range(0, len(_indexed_endpoint_pool), _health_probe_batch_size):
                    _batch = _indexed_endpoint_pool[_batch_start : _batch_start + _health_probe_batch_size]
                    if not _batch:
                        continue
                    _batch_workers = max(1, min(_health_workers, len(_batch)))
                    with ThreadPoolExecutor(max_workers=_batch_workers) as _health_executor:
                        _future_map = {
                            _health_executor.submit(_check_one_endpoint, _idx, _endpoint): (_idx, _endpoint)
                            for _idx, _endpoint in _batch
                        }
                        for _future in as_completed(_future_map):
                            _idx, _endpoint = _future_map[_future]
                            _health_checked_endpoint_count += 1
                            try:
                                _idx, _endpoint, _hc = _future.result()
                            except Exception as _exc:
                                _hc = {"ok": False, "latency_ms": 0, "error": str(_exc)}
                            if _hc.get("ok"):
                                _health_ok[_endpoint] = _hc
                                _search_note = (
                                    "Search skipped"
                                    if _hc.get("search_skipped")
                                    else (
                                        f"Search {_hc.get('search_latency_ms', 0):.0f}ms/"
                                        f"{_hc.get('search_result_count', 0)} result(s)"
                                    )
                                )
                                print(
                                    f"[expert_main]   [{_health_checked_endpoint_count}/{len(_mcp_endpoint_pool)}] OK shard#{_idx + 1} {_endpoint}: "
                                    f"Bridge {_hc.get('latency_ms', 0):.0f}ms, {_search_note}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                            else:
                                _err = _hc.get("error") or "unknown error"
                                _health_failures.append((_endpoint, _err))
                                print(
                                    f"[expert_main]   [{_health_checked_endpoint_count}/{len(_mcp_endpoint_pool)}] FAIL shard#{_idx + 1} {_endpoint}: {_err}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                    if _health_light_mode and len(_health_ok) >= _health_required_ok:
                        _health_probe_stopped_after_required_ok = (
                            _batch_start + len(_batch) < len(_indexed_endpoint_pool)
                        )
                        if _health_probe_stopped_after_required_ok:
                            print(
                                "[expert_main] goal/reuse-only health probe: "
                                f"required healthy endpoints 확보({len(_health_ok)}/{_health_required_ok}); "
                                f"remaining={len(_indexed_endpoint_pool) - (_batch_start + len(_batch))} endpoint probe 생략",
                                file=sys.stderr,
                                flush=True,
                            )
                        break
                if _health_light_mode and len(_health_ok) >= _health_required_ok:
                    print(
                        f"[expert_main] 검색 서버 헬스체크 완료: ok={len(_health_ok)}/{len(_mcp_endpoint_pool)} "
                        f"(checked={_health_checked_endpoint_count}, required_ok={_health_required_ok})",
                        file=sys.stderr,
                        flush=True,
                    )
                    break
                if not _health_failures:
                    print(
                        f"[expert_main] 검색 서버 헬스체크 완료: ok={len(_health_ok)}/{len(_mcp_endpoint_pool)}",
                        file=sys.stderr,
                        flush=True,
                    )
                    break
                if _attempt + 1 < _health_attempts:
                    if _can_auto_manage_local_shards() and not _allow_local_shard_recreate():
                        print(
                            "[expert_main] 검색 shard 자동 재생성 비활성화로 추가 헬스 재시도 생략",
                            file=sys.stderr,
                            flush=True,
                        )
                        break
                    if _can_auto_manage_local_shards():
                        _failed_shards = sorted(
                            {
                                shard
                                for _endpoint, _err in _health_failures
                                for shard in [_endpoint_to_local_shard_index(_endpoint)]
                                if shard is not None
                            }
                        )
                        if _failed_shards:
                            try:
                                print(
                                    "[expert_main] 검색 shard readiness 실패 감지: "
                                    f"shards={_format_shard_indices(_failed_shards)} 재생성 후 재확인",
                                    file=sys.stderr,
                                    flush=True,
                                )
                                _recreate_local_shards(repo_root, _failed_shards)
                            except Exception as exc:
                                print(
                                    f"[expert_main] ⚠️ 검색 shard 재생성 실패: {exc}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                    print(
                        f"[expert_main] shard 초기화 대기 중... failures={len(_health_failures)} "
                        f"({_attempt + 1}/{_health_attempts - 1})",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(5)

            # ─── 부족 shard 자동 증분 기동 (autogen 로컬 풀 한정) ──────
            # 컨테이너가 일부만 떠 있을 때(예: 16개 기동 상태에서 32개 필요)
            # 연결 거부(컨테이너 부재)로 실패한 shard만 --shards 타깃으로
            # docker compose up --no-recreate 해 부족분을 채우고, 실패했던
            # endpoint만 재검사한다. 기존 healthy 컨테이너는 up 대상에서 제외.
            _scale_up_meta: Dict[str, Any] = {
                "mcp_missing_shard_scale_up_allowed": _allow_missing_shard_auto_scale_up(),
                "mcp_missing_shard_scale_up_triggered": False,
                "mcp_missing_shard_scale_up_shards": "",
                "mcp_missing_shard_scale_up_recovered_endpoints": 0,
                "mcp_missing_shard_scale_up_error": "",
            }

            def _health_error_is_connection_refused(err: str) -> bool:
                lowered = str(err or "").lower()
                return (
                    "연결 거부" in str(err or "")
                    or "connection refused" in lowered
                    or "connecterror" in lowered
                    or "all connection attempts failed" in lowered
                    or "connection reset" in lowered
                )

            if _health_failures and _scale_up_meta["mcp_missing_shard_scale_up_allowed"]:
                # 타임아웃/검색 degrade 등 컨테이너가 떠 있는 실패는 up 대상이
                # 아니다 — 연결 거부(컨테이너 부재)인 endpoint만 missing 후보.
                _missing_shards = sorted(
                    {
                        shard
                        for _endpoint, _err in _health_failures
                        if _health_error_is_connection_refused(_err)
                        for shard in [_endpoint_to_local_shard_index(_endpoint)]
                        if shard is not None
                    }
                )
                if _missing_shards:
                    _scale_up_meta["mcp_missing_shard_scale_up_triggered"] = True
                    _scale_up_meta["mcp_missing_shard_scale_up_shards"] = _format_shard_indices(_missing_shards)
                    _scale_up_ok = False
                    try:
                        _scale_up_missing_local_shards(
                            repo_root,
                            len(_mcp_endpoint_pool),
                            _missing_shards,
                        )
                        _scale_up_ok = True
                    except Exception as exc:
                        _scale_up_meta["mcp_missing_shard_scale_up_error"] = str(exc)
                        print(
                            f"[expert_main] ⚠️ 부족 shard 자동 증분 기동 실패: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
                    # up이 부분 실패해도 일부 shard는 떠 있을 수 있으므로
                    # 재검사는 항상 수행해 실제 상태를 반영한다 (실패 시 1회만).
                    _last_fail_err = {ep: err for ep, err in _health_failures}
                    try:
                        _reprobe_attempts = max(1, int(os.getenv("MCP_SCALE_UP_REPROBE_ATTEMPTS", "12")))
                    except Exception:
                        _reprobe_attempts = 12
                    if not _scale_up_ok:
                        _reprobe_attempts = 1
                    try:
                        _reprobe_pause = max(0.0, float(os.getenv("MCP_SCALE_UP_REPROBE_PAUSE_SEC", "10")))
                    except Exception:
                        _reprobe_pause = 10.0
                    for _reprobe in range(_reprobe_attempts):
                        _retry_targets = [
                            (_idx, _endpoint)
                            for _idx, _endpoint in enumerate(_mcp_endpoint_pool)
                            if _endpoint in _last_fail_err and _endpoint not in _health_ok
                        ]
                        if not _retry_targets:
                            break
                        print(
                            f"[expert_main] 증분 기동 후 재검사 {_reprobe + 1}/{_reprobe_attempts}: "
                            f"targets={len(_retry_targets)}",
                            file=sys.stderr,
                            flush=True,
                        )
                        _retry_workers = max(1, min(_health_workers, len(_retry_targets)))
                        with ThreadPoolExecutor(max_workers=_retry_workers) as _retry_executor:
                            _retry_futures = {
                                _retry_executor.submit(_check_one_endpoint, _idx, _endpoint): (_idx, _endpoint)
                                for _idx, _endpoint in _retry_targets
                            }
                            for _future in as_completed(_retry_futures):
                                _idx, _endpoint = _retry_futures[_future]
                                try:
                                    _idx, _endpoint, _hc = _future.result()
                                except Exception as _exc:
                                    _hc = {"ok": False, "latency_ms": 0, "error": str(_exc)}
                                if _hc.get("ok"):
                                    _health_ok[_endpoint] = _hc
                                    _search_note = (
                                        "Search skipped"
                                        if _hc.get("search_skipped")
                                        else (
                                            f"Search {_hc.get('search_latency_ms', 0):.0f}ms/"
                                            f"{_hc.get('search_result_count', 0)} result(s)"
                                        )
                                    )
                                    print(
                                        f"[expert_main]   재검사 OK shard#{_idx + 1} {_endpoint}: "
                                        f"Bridge {_hc.get('latency_ms', 0):.0f}ms, {_search_note}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                                else:
                                    _err = _hc.get("error") or "unknown error"
                                    _last_fail_err[_endpoint] = _err
                                    print(
                                        f"[expert_main]   재검사 FAIL shard#{_idx + 1} {_endpoint}: {_err}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                        if all(_endpoint in _health_ok for _, _endpoint in _retry_targets):
                            break
                        if _reprobe + 1 < _reprobe_attempts and _reprobe_pause > 0:
                            time.sleep(_reprobe_pause)
                    _recovered = [ep for ep, _err in _health_failures if ep in _health_ok]
                    _scale_up_meta["mcp_missing_shard_scale_up_recovered_endpoints"] = len(_recovered)
                    _health_failures = [
                        (ep, _last_fail_err.get(ep, "unknown error"))
                        for ep, _err in _health_failures
                        if ep not in _health_ok
                    ]
                    print(
                        "[expert_main] 부족 shard 증분 기동 결과: "
                        f"recovered={len(_recovered)}, remaining_failures={len(_health_failures)}",
                        file=sys.stderr,
                        flush=True,
                    )
                    if not _health_failures:
                        print(
                            f"[expert_main] 검색 서버 헬스체크 완료: ok={len(_health_ok)}/{len(_mcp_endpoint_pool)} "
                            "(missing shard 증분 기동 후 회복)",
                            file=sys.stderr,
                            flush=True,
                        )

            _before_filter_endpoint_count = len(_mcp_endpoint_pool)
            _before_filter_parallel = _PARALLEL
            _mcp_endpoint_pool, _reuse_health_filter_meta = _apply_reuse_only_healthy_endpoint_filter(
                _mcp_endpoint_pool,
                _health_ok,
            )
            if (
                _reuse_health_filter_meta.get("mcp_healthy_endpoint_filter")
                or _reuse_health_filter_meta.get("mcp_healthy_autogen_endpoint_filter")
            ):
                _health_failures = [
                    (_endpoint, _err)
                    for _endpoint, _err in _health_failures
                    if _endpoint in set(_mcp_endpoint_pool)
                ]
                _filter_reason = _reuse_health_filter_meta.get("mcp_healthy_autogen_endpoint_filter_reason") or "unknown"
                _filter_label = (
                    "healthy-autogen-shard-filter"
                    if _reuse_health_filter_meta.get("mcp_healthy_endpoint_filter_autogen")
                    else "healthy-endpoint-filter"
                )
                print(
                    f"[expert_main] {_filter_label}({_filter_reason}): "
                    f"endpoints={_before_filter_endpoint_count}->{len(_mcp_endpoint_pool)}, "
                    f"parallel={_before_filter_parallel}->{_PARALLEL}",
                    file=sys.stderr,
                    flush=True,
                )
                print(
                    f"[expert_main] 검색 서버 헬스체크 완료: ok={len(_mcp_endpoint_pool)}/{len(_mcp_endpoint_pool)} "
                    f"(filtered {_filter_reason})",
                    file=sys.stderr,
                    flush=True,
                )

            _run_config_payload.update(
                {
                    "parallel": _PARALLEL,
                    "effective_parallel": _PARALLEL,
                    "parallel_policy": _parallel_policy_text(),
                    "mcp_endpoints": os.getenv("MCP_ENDPOINTS", os.getenv("MCP_ENDPOINT", "")),
                    "mcp_health_include_search": _health_include_search,
                    "mcp_health_light_mode": _health_light_mode,
                    "mcp_health_required_ok_count": _health_required_ok,
                    "mcp_health_checked_endpoint_count": _health_checked_endpoint_count,
                    "mcp_health_probe_batch_size": _health_probe_batch_size,
                    "mcp_health_probe_stopped_after_required_ok": _health_probe_stopped_after_required_ok,
                    "mcp_health_workers": _health_workers,
                    "mcp_health_attempts": _health_attempts,
                    "mcp_health_timeout_sec": _health_timeout,
                    "mcp_health_search_max_latency_ms": next(
                        (
                            _hc.get("search_max_latency_ms")
                            for _hc in _health_ok.values()
                            if isinstance(_hc, dict) and _hc.get("search_max_latency_ms") is not None
                        ),
                        None,
                    ),
                    "mcp_health_search_min_results": next(
                        (
                            _hc.get("search_min_results")
                            for _hc in _health_ok.values()
                            if isinstance(_hc, dict) and _hc.get("search_min_results") is not None
                        ),
                        None,
                    ),
                    **_scale_up_meta,
                    **_reuse_health_filter_meta,
                }
            )
            _config_hash = hashlib.sha256(
                json.dumps(_run_config_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()[:12]

            for _idx, _endpoint in enumerate(_mcp_endpoint_pool):
                _hc = _health_ok.get(_endpoint)
                if _hc:
                    _search_note = (
                        "Search skipped"
                        if _hc.get("search_skipped")
                        else (
                            f"Search {_hc.get('search_latency_ms', 0):.0f}ms/"
                            f"{_hc.get('search_result_count', 0)} result(s)"
                        )
                    )
                    print(
                        f"✅ 검색 서버 정상 [shard {_idx}] {_endpoint}: Bridge {_hc['latency_ms']:.0f}ms, {_search_note}",
                        file=sys.stderr,
                        flush=True,
                    )

            if _can_auto_manage_local_shards():
                _local_shard_status_items = _ensure_local_shards_warp_on(
                    repo_root,
                    required_count=len(_mcp_endpoint_pool),
                )
                try:
                    _memo_local_shard_status(
                        repo_root,
                        LOG_DIR / f"warp_shards_status_{ts}.json",
                        items=_local_shard_status_items,
                    )
                except Exception as exc:
                    print(f"[expert_main] ⚠️ WARP shard 메모 저장 실패: {exc}", file=sys.stderr, flush=True)

            if _health_failures:
                print(f"\n{'❌'*30}", file=sys.stderr, flush=True)
                print(f"❌ 일부 검색 서버 연결 실패!", file=sys.stderr, flush=True)
                for _endpoint, _err in _health_failures:
                    print(f"   - {_endpoint} -> {_err}", file=sys.stderr, flush=True)
                print(f"", file=sys.stderr, flush=True)
                print(f"   💡 운영 기준:", file=sys.stderr, flush=True)
                if _CLI_ARGS.reuse_shards_only or _small_run_shard_lifecycle_blocked():
                    print(
                        "      현재 goal/reuse-only 경로에서는 Docker Compose up/recreate를 자동 실행하지 않습니다.",
                        file=sys.stderr,
                        flush=True,
                    )
                    print(
                        "      기존 healthy shard만 쓰려면 MCP_ENDPOINTS를 살아있는 shard로 줄이거나 "
                        "MCP_GOAL_RUN_FILTER_HEALTHY_ENDPOINTS=1 기본 필터를 사용하세요.",
                        file=sys.stderr,
                        flush=True,
                    )
                    print(
                        "      shard 복구 자체가 검증 대상일 때만 --allow-goal-shard-lifecycle "
                        "--auto-up-shards 또는 --auto-recreate-shards를 명시합니다.",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    print(f"      {sys.executable} tools/warp_shards.py up --count {_PARALLEL}", file=sys.stderr, flush=True)
                    print(f"      docker ps  # 컨테이너 상태 확인", file=sys.stderr, flush=True)
                print(f"{'❌'*30}\n", file=sys.stderr, flush=True)
                print(f"검색 없이 계속 진행하시겠습니까? (y/N): ", end="", file=_orig_err, flush=True)
                try:
                    _ans = input().strip().lower()
                except (EOFError, KeyboardInterrupt):
                    _ans = "n"
                if _ans != "y":
                    print(f"🛑 검색 서버 미연결 — 파이프라인 중단", file=sys.stderr, flush=True)
                    sys.stdout = _orig_out
                    sys.stderr = _orig_err
                    return
                print(f"⚠️  검색 없이 진행합니다. 결과 품질이 저하될 수 있습니다.", file=sys.stderr, flush=True)

            # ─── 배치 컨텍스트 메모리 (포스트 간 지식 공유) ──
            _batch_context = BatchContextMemory(enabled=True)
            print(f"🧠 BatchContextMemory 활성화 (포스트 간 약칭/작가/캐릭터 공유)", file=sys.stderr, flush=True)
            _recent_post_index = AgenticPipeline.build_recent_post_index(posts)
            print(
                f"🪟 RecentPostIndex 구성 완료 ({len(_recent_post_index)}건, ±30분/20post)",
                file=sys.stderr,
                flush=True,
            )
            _slang_db_enabled = os.getenv("PIPELINE_SLANG_DB", "0").strip() == "1"
            _slang_db_path_raw = os.getenv("PIPELINE_SLANG_DB_PATH", "slang_db/slang_db.json").strip() or "slang_db/slang_db.json"
            _slang_db_path = Path(_slang_db_path_raw)
            if not _slang_db_path.is_absolute():
                _slang_db_path = repo_root / _slang_db_path
            _slang_db_manager = SlangDBManager(
                path=_slang_db_path,
                run_id=ts,
                enabled=_slang_db_enabled,
                flush_posts=int(os.getenv("PIPELINE_SLANG_DB_FLUSH_POSTS", "1") or 1),
                flush_seconds=int(os.getenv("PIPELINE_SLANG_DB_FLUSH_SECONDS", "0") or 0),
                log_fn=lambda msg: print(msg, file=sys.stderr, flush=True),
            )
            if _slang_db_enabled:
                print(f"🗂️ Slang DB 저장 활성화: {_slang_db_path}", file=sys.stderr, flush=True)
                _seeded_slang_aliases = 0
                _held_slang_alias_seeds = 0
                try:
                    for _title, _bucket in ((_slang_db_manager.data or {}).get("titles") or {}).items():
                        _title_clean = str(_title or "").strip()
                        if not _title_clean or not isinstance(_bucket, dict):
                            continue
                        for _entry in (_bucket.get("slang") or []):
                            if not isinstance(_entry, dict):
                                continue
                            if not slang_db_alias_seed_is_safe(_title_clean, _entry, _bucket):
                                _held_slang_alias_seeds += 1
                                continue
                            _term = str(_entry.get("term") or "").strip()
                            if not _term:
                                continue
                            try:
                                _count = int(_entry.get("count") or 0)
                            except Exception:
                                _count = 0
                            _batch_context.register_abbreviation_seed(
                                _term,
                                _title_clean,
                                count=_count,
                                source_roles=list(_entry.get("sources") or []),
                            )
                            _seeded_slang_aliases += 1
                    _batch_context.flush_seed_log_summary(
                        log_fn=lambda msg: print(msg, file=sys.stderr, flush=True)
                    )
                    print(
                        f"🗂️ Slang DB alias seed 주입: {_seeded_slang_aliases}건 (held={_held_slang_alias_seeds})",
                        file=sys.stderr,
                        flush=True,
                    )
                except Exception as _exc:
                    print(f"🗂️ Slang DB alias seed 주입 실패: {_exc}", file=sys.stderr, flush=True)

            # ─── 워커 팩토리 ──────────────────────────────
            def _create_pipeline(worker_id: int = 0) -> AgenticPipeline:
                """워커별 독립 LLMClient/MCPClient/Pipeline 인스턴스 생성"""
                _llm = LLMClient()
                _endpoint = _mcp_endpoint_pool[worker_id % len(_mcp_endpoint_pool)]
                _mcp = MCPClient(endpoint=_endpoint)
                _pipe = AgenticPipeline(
                    llm=_llm,
                    mcp=_mcp,
                    output_dir=OUT_DIR,
                    max_iterations=15,
                    worker_id=worker_id,
                    parallel_count=_PARALLEL,
                    batch_context=_batch_context,
                    recent_post_index=_recent_post_index,
                )
                print(f"[expert_main] worker W{worker_id} -> MCP shard {_endpoint}", file=sys.stderr, flush=True)
                return _pipe

            # ─── 단일 포스트 처리 함수 ────────────────────
            def _process_one(
                post, index: int, total: int,
                pipeline: AgenticPipeline,
                worker_id: int,
            ) -> Dict[str, Any]:
                """한 포스트를 처리하고 full_result dict 반환"""
                w_tag = f"W{worker_id}" if _PARALLEL > 1 else ""
                
                # 원본 데이터 추출
                content_texts = []
                content_blocks_public = _public_content_blocks(post.content_blocks)
                image_urls = _public_image_urls(post.content_blocks)
                for block in post.content_blocks:
                    if hasattr(block, "text") and block.text:
                        content_texts.append(block.text)
                    elif isinstance(block, str):
                        content_texts.append(block)
                
                comment_texts = []
                for c in (post.comments or []):
                    if isinstance(c, dict):
                        comment_texts.append(c.get("content", c.get("text", "")))
                    elif hasattr(c, "content"):
                        comment_texts.append(c.content)
                    else:
                        comment_texts.append(str(c))
                post_ip_public = (
                    getattr(post, "ip", None)
                    or getattr(post, "author_ip", None)
                    or getattr(post, "post_ip", None)
                )
                comment_metadata = _public_comment_metadata(
                    post.comments or [],
                    post.author,
                    getattr(post, "gallery_id", None),
                    post_ip_public,
                )
                comment_context_lines = _public_comment_context_lines(comment_metadata, limit=15)
                comment_dialogue_context_lines = _public_comment_dialogue_context_lines(
                    post.comments or [],
                    comment_metadata,
                    limit=15,
                )
                
                # 📊 대시보드: post_start — 배너 출력 전에 emit하여
                # 인메모리 포스트별 로그에 배너 라인도 포함되도록 함
                _post_start_t = time.time()
                if _monitor:
                    _monitor.emit("post_start", {
                        "index": index,
                        "total": total,
                        "post_id": post.post_id,
                        "title": post.title,
                        "worker_id": worker_id,
                    })

                # Pretty print post info (스레드 안전 출력)
                with _print_lock:
                    print(f"\n{'='*70}", file=sys.stderr, flush=True)
                    print(f"🤖 [{w_tag}][{index}/{total}] Agentic Pipeline 시작", file=sys.stderr, flush=True)
                    print(f"{'='*70}", file=sys.stderr, flush=True)
                    print(f"📌 Post ID: {post.post_id}", file=sys.stderr, flush=True)
                    print(f"📝 제목: {post.title}", file=sys.stderr, flush=True)
                    print(f"👤 작성자: {post.author}", file=sys.stderr, flush=True)
                    print(f"🔗 URL: {post.url}", file=sys.stderr, flush=True)
                    print(f"📅 작성일: {post.created_at}", file=sys.stderr, flush=True)
                    print(f"\n📄 내용:", file=sys.stderr, flush=True)
                    for j, line in enumerate(content_texts[:10], 1):
                        print(f"   {j}. {line[:100]}{'...' if len(line) > 100 else ''}", file=sys.stderr, flush=True)
                    if len(content_texts) > 10:
                        print(f"   ... ({len(content_texts) - 10}줄 더)", file=sys.stderr, flush=True)
                    print(f"\n💬 댓글 ({len(comment_texts)}개):", file=sys.stderr, flush=True)
                    for j, cmt in enumerate(comment_texts[:5], 1):
                        print(f"   {j}. {cmt[:80]}{'...' if len(cmt) > 80 else ''}", file=sys.stderr, flush=True)
                    if len(comment_texts) > 5:
                        print(f"   ... ({len(comment_texts) - 5}개 더)", file=sys.stderr, flush=True)
                    print(f"{'─'*70}", file=sys.stderr, flush=True)

                result = pipeline.process_post(post)
                result_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)
                identity_dict = result_dict.get("identity")
                if isinstance(identity_dict, dict):
                    apply_author_angle_official_detail_canonicalization(identity_dict)
                    apply_official_title_promotion_guard(identity_dict)
                    apply_judge_seed_precision_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_judge_seed_hygiene_expected_title_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_judge_seed_hygiene_alias_conflict_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_judge_seed_title_hygiene_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_judge_seed_unverified_ocr_title_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_judge_seed_title_image_mismatch_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_judge_seed_wrong_relevance_public_title_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_weak_public_title_bridge_guard(identity_dict, post.title)
                    apply_post_surface_candidate_hints(identity_dict, post.title)
                    apply_comment_surface_candidate_hints(identity_dict, post.comments or [])
                    apply_judge_seed_expected_candidate_preservation(identity_dict, getattr(post, "judge_seed", None))
                    apply_judge_seed_trope_boundary_hold_guard(identity_dict, getattr(post, "judge_seed", None))
                    apply_candidate_audit_fields(identity_dict, getattr(post, "judge_seed", None))
                    _sync_final_publication_ledger_contract(result_dict, post_title=post.title)
                
                full_result = {
                    "gallery_id": getattr(post, "gallery_id", ""),
                    "post_id": post.post_id,
                    "title": post.title,
                    "post_author": post.author,
                    "author": post.author,
                    "ip": getattr(post, "ip", None),
                    "author_ip": getattr(post, "author_ip", None),
                    "post_ip": post_ip_public,
                    "created_at": post.created_at,
                    "url": post.url,
                    "content": content_texts,
                    "content_blocks": content_blocks_public,
                    "image_urls": image_urls,
                    "image_count": len(image_urls),
                    "comments": comment_texts,
                    "comment_metadata": comment_metadata,
                    "comment_context_lines": comment_context_lines,
                    "comment_dialogue_context_lines": comment_dialogue_context_lines,
                    "analysis_result": result_dict,
                    "run_meta": {
                        "run_id": ts,
                        "model": os.getenv("LLM_MODEL", ""),
                        "llm_mode": LLM_MODE,
                        "llm_endpoint": os.getenv("LLM_ENDPOINT", ""),
                        "prompt_version": _prompt_version,
                        "config_hash": _config_hash,
                        "requested_parallel_raw": _REQUESTED_PARALLEL_RAW,
                        "requested_parallel": _REQUESTED_PARALLEL,
                        "effective_parallel": _PARALLEL,
                        "parallel_policy": _parallel_policy_text(),
                        "model_parallel_max": _MODEL_PARALLEL_MAX,
                        "model_parallel_cap_applied": _MODEL_PARALLEL_CAP_APPLIED,
                        "model_parallel_cap_model": _PARALLEL_POLICY_MODEL,
                        "mcp_health_include_search": _health_include_search,
                        "mcp_health_light_mode": _health_light_mode,
                        "mcp_health_required_ok_count": _health_required_ok,
                        "mcp_health_checked_endpoint_count": _health_checked_endpoint_count,
                        "mcp_health_probe_batch_size": _health_probe_batch_size,
                        "mcp_health_probe_stopped_after_required_ok": _health_probe_stopped_after_required_ok,
                        "mcp_health_workers": _health_workers,
                        "mcp_health_attempts": _health_attempts,
                        "mcp_health_timeout_sec": _health_timeout,
                        "mcp_health_search_max_latency_ms": _run_config_payload.get("mcp_health_search_max_latency_ms"),
                        "mcp_health_search_min_results": _run_config_payload.get("mcp_health_search_min_results"),
                        "mcp_health_ok_count": len(_health_ok),
                        "mcp_health_failure_count": len(_health_failures),
                        "search_health": identity_dict.get("search_health") if isinstance(identity_dict, dict) else None,
                        **_reuse_health_filter_meta,
                        "worker_id": worker_id,
                        "worker_log_file": str(LOG_DIR / f"expert_run_{ts}_W{worker_id}.log") if _PARALLEL > 1 else str(log_path),
                        "main_log_file": str(log_path),
                    },
                }
                if getattr(post, "judge_seed", None):
                    full_result["_judge_seed"] = getattr(post, "judge_seed", None)

                # 결과 요약 (스레드 안전 출력)
                with _print_lock:
                    print(f"\n📋 [{w_tag}] Result (post_id={post.post_id}):", file=sys.stderr, flush=True)
                    identity = result_dict.get("identity", {})
                    print(f"   is_relevant: {identity.get('is_relevant')}", file=sys.stderr, flush=True)
                    novel_id = identity.get("novel_identity")
                    if novel_id:
                        print(f"   title: {novel_id.get('official_title')}", file=sys.stderr, flush=True)
                        print(f"   confidence: {novel_id.get('confidence')}", file=sys.stderr, flush=True)
                    print(f"   reason: {identity.get('reason') or ''}", file=sys.stderr, flush=True)

                # 📊 대시보드: post_complete
                if _monitor:
                    _post_elapsed = time.time() - _post_start_t
                    _identity = result_dict.get("identity", {})
                    _novel_id = _identity.get("novel_identity") or {}
                    _ctx_token = {}
                    try:
                        _last_ctx = pipeline.orchestrator._last_ctx
                        if _last_ctx and hasattr(_last_ctx, 'token_usage'):
                            _ctx_token = dict(_last_ctx.token_usage)
                    except Exception:
                        pass
                    _monitor.emit("post_complete", {
                        "post_id": post.post_id,
                        "title": post.title,
                        "author": post.author,
                        "created_at": post.created_at,
                        "url": post.url,
                        "content": content_texts[:20],
                        "comments": comment_texts[:30],
                        "is_relevant": _identity.get("is_relevant"),
                        "official_title": _novel_id.get("official_title"),
                        "confidence": _novel_id.get("confidence"),
                        "discussion_type": _identity.get("discussion_type"),
                        "topicality": _identity.get("topicality"),
                        "subtype": _identity.get("subtype"),
                        "work_resolution": _identity.get("work_resolution"),
                        "anchor_type": _identity.get("anchor_type"),
                        "anchor_strength": _identity.get("anchor_strength"),
                        "context_sources": _identity.get("context_sources"),
                        "consistency_flags": _identity.get("consistency_flags"),
                        "reason": _identity.get("reason", ""),
                        "reason_lines": _identity.get("reason_lines"),
                        "slang_insight": _identity.get("slang_insight"),
                        "analysis_notes": (result_dict.get("analysis") or {}).get("notes"),
                        "analysis": result_dict.get("analysis"),
                        "novel_identity": _novel_id,
                        "primary_work": _identity.get("primary_work"),
                        "title_candidates": _identity.get("title_candidates"),
                        "mentioned_works": _identity.get("mentioned_works"),
                        "comparison_target": _identity.get("comparison_target"),
                        "recommendation_candidates": _identity.get("recommendation_candidates"),
                        "relevance_scope": _identity.get("relevance_scope"),
                        "elapsed": round(_post_elapsed, 1),
                        "token_usage": _ctx_token,
                        "worker_id": worker_id,
                    })
                    _monitor.emit("search_stats", {
                        "hits": getattr(pipeline, '_search_cache_hits', 0),
                        "misses": getattr(pipeline, '_search_cache_misses', 0),
                    })

                return full_result

            # ─── 메인 처리 루프 ───────────────────────────
            results = []
            total_start = time.time()

            # 📊 대시보드: batch_start
            if _monitor:
                _monitor.emit("batch_start", {
                    "total": len(posts),
                    "input_file": str(INPUT_PATH.name),
                    "output_file": str(out_result_path.name),
                    "parallel_count": _PARALLEL,
                })

            # ─── 병렬 모드: 컴팩트 CLI 진행 표시 ───────────
            def _cli_progress(msg: str) -> None:
                """병렬 모드에서 콘솔에 간결한 진행 상황만 표시"""
                with _print_lock:
                    try:
                        _orig_err.write(msg + "\n")
                        _orig_err.flush()
                    except (BrokenPipeError, OSError, ValueError):
                        pass
                    except Exception:
                        pass

            def _parallel_manifest_fields() -> Dict[str, Any]:
                return {
                    "requested_parallel_raw": _REQUESTED_PARALLEL_RAW,
                    "requested_parallel": _REQUESTED_PARALLEL,
                    "effective_parallel": _PARALLEL,
                    "parallel_count": _PARALLEL,
                    "parallel_policy": _parallel_policy_text(),
                    "model_parallel_max": _MODEL_PARALLEL_MAX,
                    "model_parallel_cap_applied": _MODEL_PARALLEL_CAP_APPLIED,
                    "model_parallel_cap_model": _PARALLEL_POLICY_MODEL,
                    "llm_model": os.getenv("LLM_MODEL", ""),
                    "llm_endpoint": os.getenv("LLM_ENDPOINT", ""),
                    "llm_stream_first_token_timeout_seconds": os.getenv(
                        "LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS",
                        "",
                    ),
                    "llm_stream_idle_timeout_seconds": os.getenv(
                        "LLM_STREAM_IDLE_TIMEOUT_SECONDS",
                        "",
                    ),
                    "input_post_count": len(posts),
                    "vlm_enabled": vlm_enabled,
                    "ocr_enabled": ocr_enabled,
                    "image_post_count": image_post_count,
                    "image_post_sample_post_ids": image_post_sample_post_ids,
                    "image_posts_present": image_post_count > 0,
                    "vlm_ocr_semantic_review_ready": vlm_ocr_semantic_review_ready,
                    "vlm_ocr_semantic_review_skip_reasons": vlm_ocr_semantic_review_skip_reason_codes,
                    "vlm_ocr_semantic_review_skip_reason": (
                        vlm_ocr_semantic_review_skip_reason_codes[0]
                        if vlm_ocr_semantic_review_skip_reason_codes
                        else ""
                    ),
                    "vlm_ocr_semantic_review_required_for_images": require_vlm_ocr_for_image_posts,
                    "vlm_ocr_semantic_review_blocker": bool(
                        image_post_count and not vlm_ocr_semantic_review_ready
                    ),
                    "vlm_ocr_semantic_review_blocker_code": (
                        "image_posts_without_vlm_ocr_ready"
                        if image_post_count and not vlm_ocr_semantic_review_ready
                        else ""
                    ),
                    "vlm_ocr_semantic_review_blocker_action": (
                        "rerun_with_vlm_on_ocr_on_or_browser_review"
                        if image_post_count and not vlm_ocr_semantic_review_ready
                        else ""
                    ),
                    "vlm_ocr_semantic_review_warning": (
                        "image_posts_present_but_vlm_ocr_not_fully_enabled"
                        if image_post_count and not vlm_ocr_semantic_review_ready
                        else ""
                    ),
                    "mcp_auto_up_shards": _allow_local_shard_auto_up(),
                    "mcp_auto_recreate_shards": _allow_local_shard_recreate(),
                    "mcp_auto_scale_up_missing_shards": _allow_missing_shard_auto_scale_up(),
                    "mcp_local_shard_management_enabled": _can_auto_manage_local_shards(),
                    "mcp_local_shard_status_audit": _local_shard_status_audit_allowed(),
                    "mcp_local_shard_status_audit_requested": _local_shard_status_audit_requested(),
                    "mcp_local_shard_status_audit_allowed": _local_shard_status_audit_allowed(),
                    "mcp_shard_lifecycle_policy": _SHARD_LIFECYCLE_POLICY_LABEL,
                    "mcp_allow_goal_shard_lifecycle": bool(getattr(_CLI_ARGS, "allow_goal_shard_lifecycle", False)),
                    "mcp_command_shard_lifecycle_allowed": _command_shard_lifecycle_allowed_by_context(),
                    "mcp_interactive_codex_run": _interactive_codex_run(),
                    "mcp_env_shard_lifecycle_requested": _env_shard_lifecycle_requested(),
                    "mcp_env_shard_lifecycle_global_opt_in": _env_shard_lifecycle_global_opt_in(),
                    "mcp_env_shard_lifecycle_allowed": _env_shard_lifecycle_allowed(),
                    "mcp_env_shard_lifecycle_blocked_by_context": _env_shard_lifecycle_blocked_by_context(),
                    "mcp_shard_lifecycle_block_threshold": _shard_lifecycle_block_threshold(),
                    "mcp_run_post_count_for_lifecycle": _current_run_post_count_for_lifecycle(),
                    "mcp_small_targeted_run": _is_small_targeted_run(),
                    "mcp_small_run_shard_lifecycle_blocked": _small_run_shard_lifecycle_blocked(),
                    "mcp_endpoints": os.getenv("MCP_ENDPOINTS", os.getenv("MCP_ENDPOINT", "")),
                    "mcp_health_include_search": _health_include_search,
                    "mcp_health_light_mode": _health_light_mode,
                    "mcp_health_required_ok_count": _health_required_ok,
                    "mcp_health_checked_endpoint_count": _health_checked_endpoint_count,
                    "mcp_health_probe_batch_size": _health_probe_batch_size,
                    "mcp_health_probe_stopped_after_required_ok": _health_probe_stopped_after_required_ok,
                    "mcp_health_workers": _health_workers,
                    "mcp_health_attempts": _health_attempts,
                    "mcp_health_timeout_sec": _health_timeout,
                    "mcp_health_search_max_latency_ms": _run_config_payload.get("mcp_health_search_max_latency_ms"),
                    "mcp_health_search_min_results": _run_config_payload.get("mcp_health_search_min_results"),
                    "mcp_health_ok_count": len(_health_ok),
                    "mcp_health_failure_count": len(_health_failures),
                    **_scale_up_meta,
                    **_reuse_health_filter_meta,
                }

            if _PARALLEL <= 1:
                # ===== 순차 모드 (기존 동작 유지) =====
                checkpoint_jsonl_path.write_text("", encoding="utf-8")
                pending_snapshot_path.write_text("[]\n", encoding="utf-8")
                result_manifest_path.write_text(
                    json.dumps(
                        {
                            "run_id": ts,
                            "output_file": str(out_result_path),
                            "checkpoint_jsonl": str(checkpoint_jsonl_path),
                            "pending_snapshot": str(pending_snapshot_path),
                            "completed_subset_json": "",
                            "completed_subset_manifest": "",
                            "completed_subset_written": False,
                            "completed_subset_count": 0,
                            "completed_subset_reason": "",
                            **_parallel_manifest_fields(),
                            "completed_count": 0,
                            "flushed_count": 0,
                            "pending_count": 0,
                            "failed_count": 0,
                            "next_save_idx": 1,
                            "partial_flush_gap": False,
                            "ordered_flush_blocked": False,
                            "large_run_complete": False,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                pipeline = _create_pipeline(worker_id=0)
                try:
                    for i, post in enumerate(posts, 1):
                        if _shutdown_event.is_set():
                            break
                        full_result = _process_one(post, i, len(posts), pipeline, worker_id=0)
                        results.append(full_result)
                        _slang_db_manager.record_result(full_result)
                        with checkpoint_jsonl_path.open("a", encoding="utf-8", newline="\n") as _fp:
                            _fp.write(
                                json.dumps(
                                    {
                                        "global_idx": i,
                                        "post_id": post.post_id,
                                        "status": "completed",
                                        "result": full_result,
                                    },
                                    ensure_ascii=False,
                                ) + "\n"
                            )
                        # 점진적 저장
                        out_result_path.write_text(
                            json.dumps(results, ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                        result_manifest_path.write_text(
                            json.dumps(
                                {
                                    "run_id": ts,
                                    "output_file": str(out_result_path),
                                    "checkpoint_jsonl": str(checkpoint_jsonl_path),
                                    "pending_snapshot": str(pending_snapshot_path),
                                    "completed_subset_json": "",
                                    "completed_subset_manifest": "",
                                    "completed_subset_written": False,
                                    "completed_subset_count": 0,
                                    "completed_subset_reason": "",
                                    **_parallel_manifest_fields(),
                                    "completed_count": len(results),
                                    "flushed_count": len(results),
                                    "pending_count": 0,
                                    "failed_count": 0,
                                    "next_save_idx": len(results) + 1,
                                    "partial_flush_gap": False,
                                    "ordered_flush_blocked": False,
                                    "large_run_complete": bool(len(results) == len(posts)),
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                except KeyboardInterrupt:
                    _shutdown_event.set()
                    print("\n⚠️  Ctrl+C 감지 — 종료 중...", file=sys.stderr, flush=True)
                    if results:
                        out_result_path.write_text(
                            json.dumps(results, ensure_ascii=False, indent=2),
                            encoding="utf-8"
                        )
                        result_manifest_path.write_text(
                            json.dumps(
                                {
                                    "run_id": ts,
                                    "output_file": str(out_result_path),
                                    "checkpoint_jsonl": str(checkpoint_jsonl_path),
                                    "pending_snapshot": str(pending_snapshot_path),
                                    "completed_subset_json": "",
                                    "completed_subset_manifest": "",
                                    "completed_subset_written": False,
                                    "completed_subset_count": 0,
                                    "completed_subset_reason": "",
                                    **_parallel_manifest_fields(),
                                    "completed_count": len(results),
                                    "flushed_count": len(results),
                                    "pending_count": 0,
                                    "failed_count": 0,
                                    "next_save_idx": len(results) + 1,
                                    "partial_flush_gap": False,
                                    "ordered_flush_blocked": False,
                                    "large_run_complete": bool(len(results) == len(posts)),
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                        _slang_db_manager.finalize()
                        print(f"💾 중단 시점까지 {len(results)}건 저장됨: {out_result_path}", file=sys.stderr, flush=True)
                    sys.stdout = _orig_out
                    sys.stderr = _orig_err
                    print("\n🛑 사용자 중단 (Ctrl+C) — 프로세스 종료", file=sys.stderr, flush=True)
                    return
            else:
                # ===== 병렬 모드 =====
                global _parallel_mode
                _parallel_mode = True
                checkpoint_jsonl_path.write_text("", encoding="utf-8")
                pending_snapshot_path.write_text("[]\n", encoding="utf-8")
                result_manifest_path.write_text(
                    json.dumps(
                        {
                            "run_id": ts,
                            "output_file": str(out_result_path),
                            "checkpoint_jsonl": str(checkpoint_jsonl_path),
                            "pending_snapshot": str(pending_snapshot_path),
                            **_parallel_manifest_fields(),
                            "completed_count": 0,
                            "flushed_count": 0,
                            "pending_count": 0,
                            "failed_count": 0,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                
                print(f"\n🚀 병렬 모드 활성화: {_PARALLEL} 워커", file=sys.stderr, flush=True)
                
                # 워커별 로그 파일 생성
                _worker_log_files = []
                for wid in range(_PARALLEL):
                    wlog_path = LOG_DIR / f"expert_run_{ts}_W{wid}.log"
                    wlog_f = wlog_path.open("w", encoding="utf-8-sig", buffering=1, newline="")
                    _worker_log_files.append(wlog_f)
                    print(f"   📝 W{wid} 로그: {wlog_path}", file=sys.stderr, flush=True)
                
                print(f"   📝 통합 로그: {log_path}", file=sys.stderr, flush=True)
                print(f"   ℹ️  CLI에는 진행 요약만 표시됩니다. 상세 로그는 워커별 파일을 참조하세요.", file=sys.stderr, flush=True)
                print(f"{'─'*70}", file=sys.stderr, flush=True)
                
                # 워커별 파이프라인 미리 생성
                pipelines = [_create_pipeline(worker_id=wid) for wid in range(_PARALLEL)]
                
                def _parallel_process_one(post, global_idx, total, pipeline, worker_id):
                    """병렬 모드 래퍼: 워커별 로그 파일을 thread-local에 설정"""
                    if _shutdown_event.is_set():
                        raise SystemExit("shutdown")
                    _worker_tls.log_file = _worker_log_files[worker_id]
                    _worker_tls.worker_id = worker_id
                    
                    # CLI에 간결한 시작 알림
                    _cli_progress(f"  🔄 [W{worker_id}][{global_idx}/{total}] 시작: #{post.post_id} — {(post.title or '')[:40]}")
                    
                    try:
                        result = _process_one(post, global_idx, total, pipeline, worker_id)
                        
                        # CLI에 간결한 완료 알림
                        identity = result.get("analysis_result", {}).get("identity", {})
                        is_rel = identity.get("is_relevant")
                        novel = (identity.get("novel_identity") or {}).get("official_title", "")
                        tag = "✅" if is_rel else "⛔"
                        info = f" → {novel}" if novel else ""
                        _cli_progress(f"  {tag} [W{worker_id}][{global_idx}/{total}] 완료: #{post.post_id}{info}")
                        return result
                    except Exception as e:
                        _cli_progress(f"  ❌ [W{worker_id}][{global_idx}/{total}] 오류: #{post.post_id} — {e}")
                        raise
                
                # 슬라이딩 윈도우 병렬 처리
                # — 하나 끝나면 즉시 다음 포스트 투입 (빈 워커 재활용)
                _worker_pool = Queue()  # 사용 가능한 워커 ID 큐
                for wid in range(_PARALLEL):
                    _worker_pool.put(wid)

                # 결과를 순서대로 저장하기 위한 dict
                _pending_results: Dict[int, Any] = {}
                _next_save_idx = 1  # 다음으로 results에 추가할 global_idx
                _failed_count = 0
                _completed_subset_state: Dict[str, Any] = {
                    "completed_subset_written": False,
                    "completed_subset_json": "",
                    "completed_subset_manifest": "",
                    "completed_subset_count": 0,
                    "completed_subset_reason": "",
                }

                def _append_checkpoint(*, global_idx: int, post_id: int, result_item: Any, status: str) -> None:
                    payload = {
                        "global_idx": global_idx,
                        "post_id": post_id,
                        "status": status,
                        "result": result_item,
                    }
                    with _results_lock:
                        with checkpoint_jsonl_path.open("a", encoding="utf-8", newline="\n") as _fp:
                            _fp.write(json.dumps(payload, ensure_ascii=False) + "\n")

                def _write_manifest(*, failed_count: int = 0) -> None:
                    failed_total = max(failed_count, _failed_count)
                    pending_count = len(_pending_results)
                    payload = {
                        "run_id": ts,
                        "output_file": str(out_result_path),
                        "checkpoint_jsonl": str(checkpoint_jsonl_path),
                        "pending_snapshot": str(pending_snapshot_path),
                        "completed_subset_json": _completed_subset_state["completed_subset_json"],
                        "completed_subset_manifest": _completed_subset_state["completed_subset_manifest"],
                        "completed_subset_written": _completed_subset_state["completed_subset_written"],
                        "completed_subset_count": _completed_subset_state["completed_subset_count"],
                        "completed_subset_reason": _completed_subset_state["completed_subset_reason"],
                        **_parallel_manifest_fields(),
                        "completed_count": len(results) + pending_count,
                        "flushed_count": len(results),
                        "pending_count": pending_count,
                        "failed_count": failed_total,
                        "next_save_idx": _next_save_idx,
                        "partial_flush_gap": pending_count > 0,
                        "ordered_flush_blocked": bool(pending_count and _next_save_idx <= len(posts)),
                        "large_run_complete": bool(len(results) == len(posts) and pending_count == 0 and failed_total == 0),
                    }
                    with _results_lock:
                        result_manifest_path.write_text(
                            json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )

                def _result_item_post_id(item: Any) -> int:
                    if isinstance(item, dict):
                        try:
                            return int(item.get("post_id") or 0)
                        except Exception:
                            return 0
                    return 0

                def _write_completed_subset(*, reason: str) -> None:
                    subset_rows = _build_completed_subset_rows(results, _pending_results)
                    pending_rows = [
                        {
                            "global_idx": idx,
                            "post_id": _result_item_post_id(item),
                        }
                        for idx, item in sorted(_pending_results.items(), key=lambda kv: kv[0])
                    ]
                    manifest = {
                        "run_id": ts,
                        "output_file": str(out_result_path),
                        "checkpoint_jsonl": str(checkpoint_jsonl_path),
                        "pending_snapshot": str(pending_snapshot_path),
                        "completed_subset_json": str(completed_subset_path),
                        "completed_subset_count": len(subset_rows),
                        "flushed_count": len(results),
                        "pending_count": len(_pending_results),
                        "next_save_idx": _next_save_idx,
                        "reason": reason,
                        "pending_rows": pending_rows,
                        "source_policy": (
                            "primary result keeps the ordered flushed prefix; "
                            "completed subset is a recovery artifact for completed rows blocked by an ordered flush gap"
                        ),
                    }
                    with _results_lock:
                        completed_subset_path.write_text(
                            json.dumps(subset_rows, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        completed_subset_manifest_path.write_text(
                            json.dumps(manifest, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    _completed_subset_state.update(
                        {
                            "completed_subset_written": True,
                            "completed_subset_json": str(completed_subset_path),
                            "completed_subset_manifest": str(completed_subset_manifest_path),
                            "completed_subset_count": len(subset_rows),
                            "completed_subset_reason": reason,
                        }
                    )
                    _write_manifest()

                def _write_pending_snapshot() -> None:
                    pending_rows = [
                        {
                            "global_idx": idx,
                            "post_id": _result_item_post_id(item),
                            "result": item,
                        }
                        for idx, item in sorted(_pending_results.items(), key=lambda kv: kv[0])
                    ]
                    with _results_lock:
                        pending_snapshot_path.write_text(
                            json.dumps(pending_rows, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    _write_manifest()

                def _flush_ordered():
                    """순서가 맞는 결과를 results에 flush하고 점진 저장"""
                    nonlocal _next_save_idx
                    flushed = False
                    while _next_save_idx in _pending_results:
                        _result_item = _pending_results.pop(_next_save_idx)
                        results.append(_result_item)
                        _next_save_idx += 1
                        flushed = True
                    if flushed:
                        with _results_lock:
                            out_result_path.write_text(
                                json.dumps(results, ensure_ascii=False, indent=2),
                                encoding="utf-8"
                            )
                        _write_pending_snapshot()

                _executor_ref = None  # Ctrl+C에서 접근용

                def _collect_done(futures_dict):
                    """완료된 future들을 수거하고 워커 반환"""
                    nonlocal _failed_count
                    done_list = [f for f in futures_dict if f.done()]
                    for fut in done_list:
                        gidx, pid, wid_done = futures_dict.pop(fut)
                        try:
                            full_result = fut.result()
                            _slang_db_manager.record_result(full_result)
                            _pending_results[gidx] = full_result
                            _append_checkpoint(
                                global_idx=gidx,
                                post_id=pid,
                                result_item=full_result,
                                status="completed",
                            )
                        except (SystemExit, KeyboardInterrupt):
                            pass  # 셧다운 중 — 무시
                        except Exception as e:
                            _failed_count += 1
                            _pending_results[gidx] = {
                                "post_id": pid,
                                "title": "",
                                "error": str(e),
                                "analysis_result": {
                                    "identity": {"is_relevant": False, "reason": f"처리 오류: {e}"},
                                },
                            }
                            _append_checkpoint(
                                global_idx=gidx,
                                post_id=pid,
                                result_item=_pending_results[gidx],
                                status="failed",
                            )
                        _worker_pool.put(wid_done)
                    if done_list:
                        _write_pending_snapshot()
                        _flush_ordered()

                try:
                    executor = ThreadPoolExecutor(max_workers=_PARALLEL)
                    _executor_ref = executor
                    futures = {}

                    for i, post in enumerate(posts, 1):
                        if _shutdown_event.is_set():
                            break

                        # 빈 워커가 생길 때까지 대기 (완료된 future 수거)
                        while not _shutdown_event.is_set():
                            _collect_done(futures)
                            try:
                                wid = _worker_pool.get(timeout=0.2)
                                break
                            except Empty:
                                continue
                        else:
                            break  # shutdown

                        fut = executor.submit(
                            _parallel_process_one,
                            post, i, len(posts),
                            pipelines[wid], worker_id=wid,
                        )
                        futures[fut] = (i, post.post_id, wid)

                    # 남은 future 전부 수거
                    while futures and not _shutdown_event.is_set():
                        _collect_done(futures)
                        if futures:
                            time.sleep(0.2)

                    # 혹시 남은 것 마저 수거
                    _collect_done(futures)
                    executor.shutdown(wait=False)

                except KeyboardInterrupt:
                    _cli_progress("\n⚠️  Ctrl+C 감지 — 종료 중...")
                    _shutdown_event.set()
                    # 진행 중인 future 취소
                    for fut in list(futures.keys()):
                        fut.cancel()
                    _collect_done(futures)
                    executor.shutdown(wait=False)

                finally:
                    # 워커 로그 파일 닫기
                    for wf in _worker_log_files:
                        try:
                            wf.close()
                        except Exception:
                            pass
                    _parallel_mode = False

                # 셧다운 시 결과 저장 후 즉시 종료 (httpx 스레드 강제 종료)
                if _shutdown_event.is_set():
                    if results or _pending_results:
                        with _results_lock:
                            out_result_path.write_text(
                                json.dumps(results, ensure_ascii=False, indent=2),
                                encoding="utf-8"
                            )
                        if _pending_results:
                            _write_completed_subset(reason="shutdown_pending_flush_gap")
                        _write_pending_snapshot()
                        _slang_db_manager.finalize()
                        _cli_progress(
                            "💾 중단 시점까지 flushed={flushed}, pending={pending}건 저장됨: {path}".format(
                                flushed=len(results),
                                pending=len(_pending_results),
                                path=out_result_path,
                            )
                        )
                    sys.stdout = _orig_out
                    sys.stderr = _orig_err
                    print("\n🛑 사용자 중단 (Ctrl+C) — 프로세스 종료", file=sys.stderr, flush=True)
                    return

            # 🔥 배치 검색 캐시 통계 출력
            if _PARALLEL <= 1:
                _all_pipelines = [pipeline]
            else:
                _all_pipelines = pipelines
            cache_hits = sum(getattr(p, '_search_cache_hits', 0) for p in _all_pipelines)
            cache_misses = sum(getattr(p, '_search_cache_misses', 0) for p in _all_pipelines)
            cache_total = cache_hits + cache_misses
            cache_entries = sum(len(getattr(p, '_search_cache', {})) for p in _all_pipelines)
            if cache_total > 0:
                print(f"\n{'='*70}", file=sys.stderr, flush=True)
                print(f"🔎 배치 검색 캐시 통계 ({'워커별 독립 캐시' if _PARALLEL > 1 else '단일 캐시'}):", file=sys.stderr, flush=True)
                print(f"   총 검색 요청: {cache_total}건", file=sys.stderr, flush=True)
                print(f"   캐시 히트:    {cache_hits}건 ({cache_hits/cache_total*100:.1f}%)", file=sys.stderr, flush=True)
                print(f"   실제 검색:    {cache_misses}건 ({cache_misses/cache_total*100:.1f}%)", file=sys.stderr, flush=True)
                print(f"   캐시 엔트리:  {cache_entries}개", file=sys.stderr, flush=True)
                if _PARALLEL > 1:
                    print(f"   워커 수:      {_PARALLEL}개 (독립 캐시)", file=sys.stderr, flush=True)
                print(f"{'='*70}", file=sys.stderr, flush=True)
            
            # 전체 완료
            _slang_db_manager.finalize()
            if _PARALLEL > 1:
                _flush_ordered()
                if _pending_results:
                    _write_completed_subset(reason="finalize_pending_flush_gap")
                    _write_pending_snapshot()
                    _cli_progress(
                        "⚠️ ordered flush gap 유지: flushed={flushed}, pending={pending}, completed_subset={subset}".format(
                            flushed=len(results),
                            pending=len(_pending_results),
                            subset=completed_subset_path,
                        )
                    )
                else:
                    with _results_lock:
                        pending_snapshot_path.write_text("[]\n", encoding="utf-8")
                _write_manifest()
            total_elapsed = time.time() - total_start
            print(f"\n{'='*70}", file=sys.stderr, flush=True)
            print(f"✅ 처리 완료!", file=sys.stderr, flush=True)
            print(f"{'='*70}", file=sys.stderr, flush=True)

            # 요약 통계
            relevant = sum(
                1 for r in results 
                if r.get("analysis_result", {}).get("identity", {}).get("is_relevant")
            )
            identified = sum(
                1 for r in results
                if (r.get("analysis_result", {}).get("identity", {}).get("novel_identity") or {}).get("official_title")
            )

            print(f"\n📊 Summary:", file=sys.stderr, flush=True)
            print(f"   Total Posts: {len(results)}", file=sys.stderr, flush=True)
            print(f"   Relevant: {relevant}", file=sys.stderr, flush=True)
            print(f"   Identified (with title): {identified}", file=sys.stderr, flush=True)
            print(f"   Total Time: {total_elapsed:.1f}s", file=sys.stderr, flush=True)
            if len(results) > 0:
                print(f"   Avg Time/Post: {total_elapsed/len(results):.1f}s", file=sys.stderr, flush=True)
            for line in _vlm_ocr_semantic_review_gate_lines(
                image_post_count=image_post_count,
                vlm_enabled=vlm_enabled,
                ocr_enabled=ocr_enabled,
                ready=vlm_ocr_semantic_review_ready,
                sample_post_ids=image_post_sample_post_ids,
                skip_reasons=vlm_ocr_semantic_review_skip_reason_codes,
            ):
                print(f"   {line}", file=sys.stderr, flush=True)
            
            # 전체 배치 토큰 통계는 각 포스트 처리 중 출력됨
            # 여기서는 요약만 표시
            print(f"\n💡 참고: 각 전문가별 토큰 사용량은 위 로그 참조", file=sys.stderr, flush=True)

            print(f"\n💾 결과 파일:", file=sys.stderr, flush=True)
            print(f"   - 통합 로그: {log_path}", file=sys.stderr, flush=True)
            if _PARALLEL > 1:
                for wid in range(_PARALLEL):
                    wlog_p = LOG_DIR / f"expert_run_{ts}_W{wid}.log"
                    print(f"   - W{wid} 로그: {wlog_p}", file=sys.stderr, flush=True)
            print(f"   - 결과: {out_result_path}", file=sys.stderr, flush=True)

            # 📊 대시보드: batch_complete
            if _monitor:
                _monitor.emit("batch_complete", {
                    "total": len(results),
                    "relevant": relevant,
                    "identified": identified,
                    "elapsed": round(total_elapsed, 1),
                })

        finally:
            # 외부 대시보드 포워딩 종료: 잔여 critical 이벤트(batch_complete 포함) flush
            if _dashboard_forwarder is not None:
                try:
                    _dashboard_forwarder.flush_and_stop(timeout=5.0)
                except Exception:
                    pass
            sys.stdout = _orig_out
            sys.stderr = _orig_err


def load_jsonl_posts(path: Path) -> List:
    """JSONL 파일에서 포스트만 로드 (댓글 제외)"""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from llm_batch.models import PostInput, ContentBlock

    def _post_id_key(value: Any) -> Optional[int | str]:
        if value in (None, ""):
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return str(value).strip()

    def _content_blocks_from_data(data: Dict[str, Any]) -> List[ContentBlock]:
        raw_blocks = data.get("content_blocks")
        if raw_blocks is None:
            raw_blocks = data.get("content")
        if raw_blocks is None:
            raw_blocks = []
        if isinstance(raw_blocks, str):
            raw_blocks = [raw_blocks]
        if not isinstance(raw_blocks, list):
            raw_blocks = [raw_blocks]

        blocks: List[ContentBlock] = []
        for block in raw_blocks:
            if isinstance(block, dict):
                block_url = block.get("url") or block.get("image_url") or block.get("src")
                block_type = block.get("type") or ("image" if block_url else "text")
                blocks.append(ContentBlock(
                    type=str(block_type),
                    text=block.get("text") if block.get("text") is not None else block.get("content"),
                    url=block_url,
                ))
            else:
                text = str(block).strip()
                if text:
                    blocks.append(ContentBlock(type="text", text=text))
        return blocks

    def _embedded_comments_from_data(pid: int, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_comments = data.get("comments")
        if raw_comments in (None, ""):
            raw_comments = data.get("comments_raw") or []
        if isinstance(raw_comments, (str, dict)):
            raw_comments = [raw_comments]
        if not isinstance(raw_comments, list):
            return []

        raw_metadata = data.get("comment_metadata") or []
        if not isinstance(raw_metadata, list):
            raw_metadata = []
        metadata_keys = (
            "comment_id",
            "author",
            "ip",
            "created_at",
            "reply_to_comment_id",
            "reply_level",
            "gallery_id",
        )

        comments: List[Dict[str, Any]] = []
        for idx, comment in enumerate(raw_comments):
            if isinstance(comment, dict):
                item = dict(comment)
                if "content" not in item and "text" in item:
                    item["content"] = item.get("text")
            else:
                text = str(comment).strip()
                if not text:
                    continue
                item = {"content": text}
            meta = raw_metadata[idx] if idx < len(raw_metadata) and isinstance(raw_metadata[idx], dict) else {}
            for key in metadata_keys:
                value = meta.get(key)
                if value not in (None, "") and item.get(key) in (None, ""):
                    item[key] = value
            item.setdefault("post_id", pid)
            item.setdefault("comment_id", f"{pid}:embedded:{idx}")
            comments.append(item)
        return comments

    def _comment_dedupe_key(comment: Any) -> tuple:
        if not isinstance(comment, dict):
            return ("text", str(comment or "").strip())
        comment_id = str(comment.get("comment_id") or "").strip()
        if comment_id:
            return ("id", comment_id)
        return (
            "body",
            str(comment.get("author") or "").strip(),
            str(comment.get("ip") or "").strip(),
            str(comment.get("created_at") or "").strip(),
            str(comment.get("content") or comment.get("text") or "").strip(),
        )

    posts = []
    post_map: Dict[int, Dict[str, Any]] = {}
    comments_map: Dict[int, List[Dict[str, Any]]] = {}

    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 댓글인지 포스트인지 구분
            if "comment_id" in item:
                # 댓글
                pid = _post_id_key(item.get("post_id"))
                if pid is not None:
                    if pid not in comments_map:
                        comments_map[pid] = []
                    comments_map[pid].append(item)
            elif "post_id" in item:
                # 포스트
                pid = _post_id_key(item.get("post_id"))
                if pid is None:
                    continue
                post_map[pid] = item

    # PostInput으로 변환
    for pid, data in post_map.items():
        content_blocks = _content_blocks_from_data(data)

        # 댓글 연결: 기존 별도 comment_id 라인과 packet 내부 embedded comments를 모두 지원한다.
        comments = []
        seen_comment_keys = set()
        for comment in comments_map.get(pid, []):
            dedupe_key = _comment_dedupe_key(comment)
            if dedupe_key in seen_comment_keys:
                continue
            seen_comment_keys.add(dedupe_key)
            if isinstance(comment, dict):
                item = dict(comment)
                item.setdefault("gallery_id", data.get("gallery_id", ""))
                comments.append(item)
            else:
                comments.append(comment)
        for comment in _embedded_comments_from_data(pid, data):
            dedupe_key = _comment_dedupe_key(comment)
            if dedupe_key in seen_comment_keys:
                continue
            seen_comment_keys.add(dedupe_key)
            if isinstance(comment, dict):
                comment.setdefault("gallery_id", data.get("gallery_id", ""))
            comments.append(comment)

        posts.append(PostInput(
            post_id=pid,
            title=data.get("title", ""),
            author=data.get("author", ""),
            ip=data.get("ip") or data.get("author_ip") or data.get("post_ip") or data.get("writer_ip"),
            author_ip=data.get("author_ip"),
            post_ip=data.get("post_ip"),
            content_blocks=content_blocks,
            gallery_id=data.get("gallery_id", ""),
            url=data.get("url", ""),
            created_at=data.get("created_at", ""),
            comments=comments,
            judge_seed=data.get("_judge_seed") if isinstance(data.get("_judge_seed"), dict) else None,
            search_results=data.get("search_results") if isinstance(data.get("search_results"), list) else None,
            source_search_results=(
                data.get("source_search_results")
                if isinstance(data.get("source_search_results"), list)
                else None
            ),
            precomputed_search_results=(
                data.get("precomputed_search_results")
                if isinstance(data.get("precomputed_search_results"), list)
                else None
            ),
            search_evidence_catalog=(
                data.get("search_evidence_catalog")
                if isinstance(data.get("search_evidence_catalog"), list)
                else None
            ),
            native_web_seed=data.get("native_web_seed") if isinstance(data.get("native_web_seed"), dict) else None,
            source_evidence=data.get("source_evidence") if isinstance(data.get("source_evidence"), dict) else None,
        ))

    return posts


def _count_nonempty_jsonl_lines(path: Path) -> int:
    """입력 파일이 비어 있는지 빠르게 확인한다. BOM은 내용으로 세지 않는다."""
    count = 0
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _post_has_image_block(post: Any) -> bool:
    """Return whether a loaded post contains an image-like content block."""
    for block in getattr(post, "content_blocks", []) or []:
        if isinstance(block, dict):
            block_type = str(block.get("type") or "").strip().lower()
            url = str(block.get("url") or block.get("image_url") or block.get("src") or "").strip()
        else:
            block_type = str(getattr(block, "type", "") or "").strip().lower()
            url = str(getattr(block, "url", "") or "").strip()
        if block_type == "image" or url:
            return True
    return False


def _count_image_posts(posts: List[Any]) -> int:
    return sum(1 for post in posts if _post_has_image_block(post))


def _image_post_sample_post_ids(posts: List[Any], *, limit: int = 10) -> List[Any]:
    samples: List[Any] = []
    for post in posts:
        if not _post_has_image_block(post):
            continue
        post_id = getattr(post, "post_id", None)
        if post_id is None and isinstance(post, dict):
            post_id = post.get("post_id")
        samples.append(post_id if post_id is not None else "<unknown>")
        if len(samples) >= limit:
            break
    return samples


def _vlm_ocr_semantic_review_gate_lines(
    *,
    image_post_count: int,
    vlm_enabled: bool,
    ocr_enabled: bool,
    ready: bool,
    sample_post_ids: List[Any] | None = None,
    skip_reasons: List[str] | None = None,
) -> List[str]:
    if image_post_count <= 0:
        return ["VLM/OCR Semantic Gate: NOT_APPLICABLE (image_post_count=0)"]
    state = "READY" if ready else "NO-GO"
    sample_text = ", ".join(str(item) for item in (sample_post_ids or [])[:10]) or "none"
    reason_codes = (
        skip_reasons
        if skip_reasons is not None
        else _vlm_ocr_semantic_review_skip_reasons(
            image_post_count=image_post_count,
            vlm_enabled=vlm_enabled,
            ocr_enabled=ocr_enabled,
        )
    )
    reason_text = ", ".join(reason_codes or []) or "none"
    lines = [
        (
            "VLM/OCR Semantic Gate: "
            f"{state} (image_post_count={image_post_count}, "
            f"vlm={vlm_enabled}, ocr={ocr_enabled}, ready={ready}, "
            f"skip_reasons=[{reason_text}], sample_post_ids=[{sample_text}])"
        )
    ]
    if not ready:
        lines.append(
            "VLM/OCR Semantic Gate Action: "
            "rerun_with_vlm_on_ocr_on_or_browser_review; "
            "image rows from this run are not semantic image approval evidence"
        )
    return lines


def _vlm_ocr_semantic_review_skip_reasons(
    *,
    image_post_count: int,
    vlm_enabled: bool,
    ocr_enabled: bool,
) -> List[str]:
    if image_post_count <= 0:
        return ["no_image_blocks"]
    reasons: List[str] = []
    if not vlm_enabled:
        reasons.append("vlm_disabled")
    if not ocr_enabled:
        reasons.append("ocr_disabled")
    return reasons


def _require_vlm_ocr_for_image_posts() -> bool:
    return bool(
        getattr(_CLI_ARGS, "require_vlm_ocr_for_images", False)
        or _env_toggle_enabled("LLM_REQUIRE_VLM_OCR_FOR_IMAGES", "0")
    )


def _env_toggle_enabled(key: str, default: str = "0") -> bool:
    return str(os.getenv(key, default)).strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _shutdown_event.set()
        print("\n🛑 사용자 중단 (Ctrl+C)", file=sys.stderr, flush=True)
        # 결과가 있으면 저장
        raise SystemExit(1)
