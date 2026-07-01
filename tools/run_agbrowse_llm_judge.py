"""Run and aggregate agbrowse Web-AI LLM judge batches.

This script is intentionally restartable. It only skips a verdict file when the
file is valid and covers exactly the post_ids in the matching batch.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DISAGREEMENT_TYPES = {
    "none",
    "under_resolved_false_negative",
    "wrong_work",
    "garbage_title",
    "over_resolved",
    "wrong_relevance",
    "wrong_discussion_type",
    "cross_media_or_famous_mismatch",
    "title_noisy_ocr",
    "uncertain",
}
LIKELY_CORRECT = {"pipeline", "claude", "both_unclear"}
SEVERITY = {"high", "med", "low"}
REQUIRED_VERDICT_KEYS = {
    "post_id",
    "agree",
    "disagreement_type",
    "likely_correct",
    "claude_take",
    "severity",
    "note",
}
WEB_REQUIRED_VERDICT_KEYS = {
    "judge_provider",
    "independent_is_novel_related",
    "independent_official_title",
    "independent_url",
    "web_search_performed",
    "source_urls",
    "korean_reason",
}
PROVIDER_URLS = {
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/app",
    "grok": "https://grok.com/",
}
SENSITIVE_REDACTIONS = [
    (re.compile(r"ntr|불륜|탁란|근친", re.IGNORECASE), "[금기연애소재]"),
    (
        re.compile(
            r"떡인지|야스|섹스|성관계|성교|강간|윤간|겁탈|박히|따먹|꼴림|초대남|후타|암타|임신튀|좆|망가|고추|고츄|보지|젖|딸딸이|자위|조루|노꼴|닭장|교미",
            re.IGNORECASE,
        ),
        "[성적행위/성인표현]",
    ),
    (re.compile(r"남학생|여학생|미성년|중학생|고등학생|초딩|초등학생|로리", re.IGNORECASE), "[학생/연령민감]"),
    (re.compile(r"테러|폭격|화형|줘패|비명|울부짖|죽이고|죽이는|뒤지고", re.IGNORECASE), "[폭력/사망표현]"),
    (re.compile(r"여선생|남선생|선생님", re.IGNORECASE), "[교사]"),
    (re.compile(r"서방님", re.IGNORECASE), "[부적절호칭]"),
]


PROMPT_TEMPLATE = """너는 한국 웹소설 커뮤니티(dcinside) 글 작품매칭 파이프라인의 판정을 독립 재판정으로 검수하는 평가자다.

아래 POSTS_JSON은 JSON 배열이며 각 항목은 post_id, title, body, comments, image_ocr, img_count, pipe, reason 필드를 가진다.
안전한 자동 처리를 위해 일부 성적/연령 민감 표현은 [성적행위/성인표현], [학생/연령민감] 같은 bracket label로 치환될 수 있다.
이 치환은 작품 관련성/문맥 판단에 필요한 의미만 보존하기 위한 것이며, 치환 label 자체를 작품명으로 보지 마라.
이번 batch 인덱스는 {batch_index}이다. 이번 호출의 verdicts 길이는 정확히 {expected_count}이어야 한다.
필수 post_id 목록: {post_id_list}
POSTS_JSON에 들어 있는 모든 post를 빠짐없이 판정하라. verdicts=[] 또는 batch=null은 실패다.

각 post마다:
1) 본문+댓글+이미지 OCR을 정독해 독립 판단: (a) 소설 관련 글인가 (b) 식별 가능한 특정 웹소설이 있는가/무엇인가 (c) 글의 실제 의도/문맥.
2) 파이프라인 pipe와 대조.
3) disagreement_type을 아래 enum 중 하나로 선택.
4) likely_correct는 pipeline, claude, both_unclear 중 하나, severity는 high, med, low 중 하나.
5) 이번 자동화에서는 웹검색을 수행하지 않는다. 첨부 batch와 기존 지식만으로 판단하고, 웹근거가 필요한 불확실한 건은 note에 web_unverified를 적고 uncertain 또는 낮은 severity로 보수 처리한다.
6) 과대단정하지 말고 불확실하면 uncertain을 쓴다.

disagreement_type enum:
none, under_resolved_false_negative, wrong_work, garbage_title, over_resolved, wrong_relevance, wrong_discussion_type, cross_media_or_famous_mismatch, title_noisy_ocr, uncertain

우선순위:
garbage_title > cross_media_or_famous_mismatch > over_resolved > wrong_work > title_noisy_ocr > under_resolved_false_negative > wrong_relevance > wrong_discussion_type > uncertain

severity 기준:
high = locked/High resolved의 확정 오매칭/garbage/over_resolved/cross_media 또는 명백한 거짓음성.
med = 영향 있는 중간 오류, 모호 단서 거짓음성, Medium 이하 오매칭, 관련성/문맥 라벨 오류.
low = 경계적/사소한 차이.

반환은 코드펜스 없이 JSON 객체 하나만:
{{
  "batch": {batch_index},
  "verdicts": [
    {{
      "post_id": "int",
      "agree": true,
      "disagreement_type": "none",
      "likely_correct": "pipeline",
      "claude_take": "독립 판단 요약 한국어 1문장",
      "severity": "low",
      "note": "근거 한국어 간결, 웹근거 필요 시 web_unverified 명시"
    }}
  ]
}}

중요 검증 조건:
- verdicts의 post_id 집합은 입력 batch의 post_id 집합과 정확히 같아야 한다.
- agree=true iff disagreement_type="none"이다.
- post_id는 문자열이어도 되지만 입력 post_id와 동일해야 한다.
- JSON 외 설명, markdown, 코드펜스는 출력하지 마라.

POSTS_JSON:
{posts_json}
"""

PROMPT_TEMPLATE_EXTERNAL_WEB = """너는 GPT/Claude급 외부 LLM judge 역할이다. 목표는 파이프라인 로그나 내부 추론을 재검산하는 것이 아니라, 각 post를 직접 읽고 이해한 뒤 웹검색으로 작품 정답성을 독립 검증하는 것이다.

아래 POSTS_JSON은 JSON 배열이며 각 항목은 post_id, title, body, comments, image_ocr, img_count, pipe 필드를 가진다. pipe는 감사 대상인 파이프라인 최종 결론일 뿐이고, 내부 처리 history/log/reason_lines는 제공하지 않는다.
안전한 자동 처리를 위해 일부 성적/연령 민감 표현은 [성적행위/성인표현], [학생/연령민감] 같은 bracket label로 치환될 수 있다. 이 치환 label 자체를 작품명으로 보지 마라.

이번 batch 인덱스는 {batch_index}이다. 이번 호출의 verdicts 길이는 정확히 {expected_count}이어야 한다.
필수 post_id 목록: {post_id_list}
POSTS_JSON에 들어 있는 모든 post를 빠짐없이 판정하라. verdicts=[] 또는 batch=null은 실패다.

각 post마다 반드시 수행할 일:
1) title/body/comments/image_ocr를 먼저 정독해 글의 실제 의도와 특정 작품 단서를 독립적으로 판단한다.
2) 작품명이 해소됐거나, 약칭/별칭/다후보/유명작/검색오인 가능성이 있거나, 파이프라인 결론과 원문 단서가 충돌하면 웹검색을 수행한다.
3) 웹검색은 작품 공식/플랫폼 상세페이지, 작품명, 작가명, 줄거리/소개, 별칭 정합성을 확인하기 위한 것이다. 검색 snippet만으로 단정하지 말고 가능한 URL을 source_urls에 남긴다.
4) 명백한 잡담/noise/trope 일반론이라 검색이 불필요하면 web_search_performed=false로 두되, 왜 검색 없이 판단 가능한지 korean_reason에 적는다.
5) 독립 판단 결과와 pipe를 대조하여 disagreement_type을 고른다. 과대단정하지 말고 불확실하면 uncertain/both_unclear를 사용한다.

disagreement_type enum:
none, under_resolved_false_negative, wrong_work, garbage_title, over_resolved, wrong_relevance, wrong_discussion_type, cross_media_or_famous_mismatch, title_noisy_ocr, uncertain

likely_correct enum: pipeline, claude, both_unclear
severity enum: high, med, low

반환은 코드펜스 없이 JSON 객체 하나만:
{{
  "batch": {batch_index},
  "verdicts": [
    {{
      "post_id": "int",
      "agree": true,
      "disagreement_type": "none",
      "likely_correct": "pipeline",
      "claude_take": "독립 판단 요약 한국어 1문장",
      "severity": "low",
      "note": "웹검색/원문 근거 한국어 간결. URL은 source_urls에도 넣기.",
      "judge_provider": "chatgpt",
      "independent_is_novel_related": true,
      "independent_official_title": "작품명 또는 null",
      "independent_url": "대표 공식/플랫폼 URL 또는 null",
      "web_search_performed": true,
      "source_urls": ["https://..."],
      "korean_reason": "원문 단서와 웹검색 근거를 종합한 한국어 판단 사유 1~3문장"
    }}
  ]
}}

중요 검증 조건:
- verdicts의 post_id 집합은 입력 batch의 post_id 집합과 정확히 같아야 한다.
- agree=true iff disagreement_type="none"이다.
- source_urls는 배열이어야 한다. 검색을 했으면 가능한 한 URL을 1개 이상 남긴다.
- JSON 외 설명, markdown, 코드펜스는 출력하지 마라.

POSTS_JSON:
{posts_json}
"""

STATIC_SYSTEM = (
    "You are a strict JSON API for an evaluation pipeline. "
    "Return exactly one valid JSON object and no markdown, no tables, no prose, no analysis outside JSON. "
    "Do not browse the web. Do not cite sources. "
    "If evidence is insufficient, use disagreement_type='uncertain' and likely_correct='both_unclear'."
)
EXTERNAL_WEB_SYSTEM = (
    "You are an external LLM judge for Korean webnovel community post-to-work matching. "
    "Read the supplied post text directly, then use web search when needed to verify official titles, aliases, authors, and platform detail pages. "
    "Return exactly one valid JSON object and no markdown, no tables, no prose outside JSON. "
    "Do not rely on pipeline logs or hidden reasoning; only compare the supplied post source against the supplied pipe final decision."
)

STRICT_OUTPUT = (
    "Valid JSON object only. The object must have keys batch and verdicts. "
    "Do not use markdown, code fences, tables, headings, citations outside strings, or explanatory text."
)

STATIC_CONSTRAINTS = (
    "Each input post_id must appear exactly once in verdicts. "
    "agree must be true if and only if disagreement_type is none. "
    "Use only the declared enum values. "
    "No web search. No citations. No markdown links. "
    "The note key is required. The notes key is forbidden. "
    "severity must be high, med, or low."
)
EXTERNAL_WEB_CONSTRAINTS = (
    "Each input post_id must appear exactly once in verdicts. "
    "agree must be true if and only if disagreement_type is none. "
    "Use only the declared enum values. "
    "Use web search for resolved, ambiguous, alias, wrong-work, multi-candidate, famous-title, or search-risk cases. "
    "Put all cited/decisive URLs inside source_urls. "
    "The keys note, korean_reason, web_search_performed, source_urls, independent_official_title, and independent_url are required. "
    "The notes key is forbidden. "
    "severity must be high, med, or low. "
    "All human-facing reasons must be Korean."
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def log(message: str, *, error: bool = False) -> None:
    print(message, file=sys.stderr if error else sys.stdout, flush=True)


def redact_sensitive_text(text: str) -> str:
    result = text
    for pattern, replacement in SENSITIVE_REDACTIONS:
        result = pattern.sub(replacement, result)
    return result


def redact_sensitive_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [redact_sensitive_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_sensitive_payload(item) for key, item in value.items()}
    return value


def batch_post_ids(batch: list[Any]) -> list[str]:
    return [str(item.get("post_id")) for item in batch if isinstance(item, dict)]


def expected_count(meta: dict[str, Any], batch_index: int) -> int:
    batch_size = int(meta["batch_size"])
    total = int(meta["total"])
    return min(batch_size, total - batch_index * batch_size)


def limit_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def iter_source_results(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if str(item.get("status") or "completed") != "completed":
                    continue
                result = item.get("result") or item
                if isinstance(result, dict):
                    rows.append(result)
        return rows
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return [row for row in payload["results"] if isinstance(row, dict)]
    raise ValueError(f"unsupported source result shape: {path}")


def content_text(row: dict[str, Any]) -> str:
    blocks = row.get("content_blocks") or row.get("content") or []
    if isinstance(blocks, str):
        return limit_text(blocks, 4000)
    parts: list[str] = []
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict):
                text = block.get("text") or block.get("content") or ""
                url = block.get("url") or ""
                if text:
                    parts.append(str(text))
                if url:
                    parts.append(f"[url] {url}")
            elif isinstance(block, str):
                parts.append(block)
    if not parts and row.get("body"):
        parts.append(str(row.get("body")))
    return limit_text(" / ".join(part.strip() for part in parts if part and part.strip()), 4000)


def comment_texts(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    comments = row.get("comments") or []
    if not isinstance(comments, list):
        return out
    for comment in comments[:20]:
        if isinstance(comment, dict):
            text = comment.get("text") or comment.get("content") or comment.get("body") or ""
            author = comment.get("author") or comment.get("nickname") or ""
            if author:
                out.append(limit_text(f"{author}: {text}", 360))
            elif text:
                out.append(limit_text(text, 360))
        elif isinstance(comment, str):
            out.append(limit_text(comment, 360))
    return [text for text in out if text]


def identity_from_result(row: dict[str, Any]) -> dict[str, Any]:
    analysis_result = row.get("analysis_result") or {}
    identity = analysis_result.get("identity") or row.get("identity") or {}
    return identity if isinstance(identity, dict) else {}


def image_ocr_items(identity: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    catalog = identity.get("image_evidence_catalog") or []
    if not isinstance(catalog, list):
        return out
    for item in catalog[:5]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "explicit_work_title": limit_text(item.get("explicit_work_title"), 160) or None,
                "explicit_author_name": limit_text(item.get("explicit_author_name"), 80) or None,
                "ocr_text": limit_text(item.get("ocr_text"), 500) or None,
                "visual_summary": limit_text(item.get("visual_summary"), 360) or None,
                "evidence_type": item.get("evidence_type"),
            }
        )
    return out


def title_candidate_items(identity: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    candidates = identity.get("title_candidates") or []
    if not isinstance(candidates, list):
        return out
    for item in candidates[:12]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "official_title": item.get("official_title") or item.get("title"),
                "alias_or_mention": item.get("alias_or_mention"),
                "heretic_url": item.get("heretic_url") or item.get("url"),
                "source_tier": item.get("source_tier"),
                "confidence": item.get("confidence"),
            }
        )
    return out


def pipeline_pipe(identity: dict[str, Any]) -> dict[str, Any]:
    primary = identity.get("primary_work") or {}
    if not isinstance(primary, dict):
        primary = {}
    novel_identity = identity.get("novel_identity") or {}
    if not isinstance(novel_identity, dict):
        novel_identity = {}
    official_title = (
        primary.get("official_title")
        or novel_identity.get("official_title")
        or identity.get("official_title")
    )
    heretic_url = (
        primary.get("heretic_url")
        or primary.get("url")
        or novel_identity.get("heretic_url")
        or novel_identity.get("url")
        or identity.get("heretic_url")
    )
    return {
        "is_relevant": identity.get("is_relevant"),
        "work_resolution": identity.get("work_resolution"),
        "title_resolution_state": identity.get("title_resolution_state"),
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "discussion_type": identity.get("discussion_type"),
        "subtype": identity.get("subtype"),
        "anchor_type": identity.get("anchor_type"),
        "official_title": official_title,
        "heretic_url": heretic_url,
        "source_tier": primary.get("source_tier") or novel_identity.get("source_tier"),
        "locked": primary.get("locked") or novel_identity.get("locked"),
        "confidence": primary.get("confidence") or novel_identity.get("confidence") or identity.get("confidence"),
    }


def build_external_record(row: dict[str, Any]) -> dict[str, Any]:
    identity = identity_from_result(row)
    return {
        "post_id": row.get("post_id"),
        "gallery_id": row.get("gallery_id"),
        "title": limit_text(row.get("title"), 240),
        "body": content_text(row),
        "comments": comment_texts(row),
        "image_urls": row.get("image_urls")[:5] if isinstance(row.get("image_urls"), list) else [],
        "image_ocr": image_ocr_items(identity),
        "img_count": row.get("image_count") or row.get("img_count") or len(row.get("image_urls") or []),
        "pipe": pipeline_pipe(identity),
        "title_candidates_for_audit": title_candidate_items(identity),
    }


def build_batches(args: argparse.Namespace) -> int:
    result_path = Path(args.result)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    selected_post_ids = {str(pid) for pid in (args.post_id or [])}
    rows: list[dict[str, Any]] = []
    for row in iter_source_results(result_path):
        if selected_post_ids and str(row.get("post_id")) not in selected_post_ids:
            continue
        rows.append(build_external_record(row))
        if args.limit is not None and len(rows) >= int(args.limit):
            break
    batch_size = int(args.batch_size)
    for old in out_dir.glob("batch_*.json"):
        old.unlink()
    for index, group in enumerate(chunks(rows, batch_size)):
        atomic_write_json(out_dir / f"batch_{index:03d}.json", group)
    meta = {
        "source_result": str(result_path),
        "judge_mode": args.judge_mode,
        "provider": args.vendor,
        "model": args.model,
        "batch_size": batch_size,
        "total": len(rows),
        "num_batches": len(chunks(rows, batch_size)),
        "post_ids": [row.get("post_id") for row in rows],
        "contract": "external LLM reads post source directly and uses web search when needed; pipeline history/reason_lines excluded",
    }
    atomic_write_json(out_dir / "_meta.json", meta)
    log(f"batches: {meta['num_batches']} total: {meta['total']} out_dir={out_dir}")
    return 0


def extract_json_object(text: str) -> Any:
    stripped = text.strip()
    try:
        loaded = json.loads(stripped)
        if isinstance(loaded, dict):
            for key_path in (("answerText",), ("answerArtifact", "text"), ("answerArtifact", "markdown")):
                current: Any = loaded
                for key in key_path:
                    if isinstance(current, dict):
                        current = current.get(key)
                    else:
                        current = None
                        break
                if isinstance(current, str) and current.strip():
                    try:
                        return extract_json_object(current)
                    except Exception:
                        pass
        return loaded
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fence:
        return json.loads(fence.group(1))

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(stripped[start : end + 1])
    raise ValueError("no JSON object found in model output")


def normalize_batch_value(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return int(value)
        match = re.fullmatch(r"batch_(\d+)", value)
        if match:
            return int(match.group(1))
    return None


def normalize_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    batch_value = normalize_batch_value(payload.get("batch"))
    if batch_value is not None:
        payload["batch"] = batch_value
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list):
        return payload
    for item in verdicts:
        if not isinstance(item, dict):
            continue
        if "note" not in item and "notes" in item:
            item["note"] = item.get("notes")
        if "claude_take" not in item and item.get("note"):
            item["claude_take"] = str(item.get("note"))
        if isinstance(item.get("likely_correct"), bool):
            item["likely_correct"] = "pipeline" if item.get("likely_correct") else "claude"
        if item.get("likely_correct") in {"reviewer", "evaluator"}:
            item["likely_correct"] = "claude"
        if item.get("disagreement_type") == "relevance":
            item["disagreement_type"] = "wrong_relevance"
        if item.get("disagreement_type") in {"work_resolution", "false_negative"}:
            item["disagreement_type"] = "under_resolved_false_negative"
        if item.get("severity") == "none":
            item["severity"] = "low"
        if item.get("severity") == "major":
            item["severity"] = "high"
        if "web_search_performed" in item and isinstance(item.get("web_search_performed"), str):
            item["web_search_performed"] = item["web_search_performed"].strip().lower() in {"true", "yes", "1", "검색함"}
        if "source_urls" in item and isinstance(item.get("source_urls"), str):
            urls = re.findall(r"https?://[^\s,)\]]+", item["source_urls"])
            item["source_urls"] = urls
        if item.get("independent_official_title") in {"", "-", "null", "None"}:
            item["independent_official_title"] = None
        if item.get("independent_url") in {"", "-", "null", "None"}:
            item["independent_url"] = None
    return payload


def validate_verdict(
    payload: Any,
    batch_index: int,
    expected_ids: list[str],
    *,
    judge_mode: str = "static",
) -> tuple[bool, str]:
    payload = normalize_payload(payload)
    if not isinstance(payload, dict):
        return False, "payload is not an object"
    actual_batch = normalize_batch_value(payload.get("batch"))
    if actual_batch != batch_index:
        return False, f"batch mismatch: {payload.get('batch')} != {batch_index}"
    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list):
        return False, "verdicts is not a list"
    actual_ids = [str(v.get("post_id")) for v in verdicts if isinstance(v, dict)]
    if Counter(actual_ids) != Counter(expected_ids):
        return False, f"post_id set mismatch expected={len(expected_ids)} actual={len(actual_ids)}"
    for idx, item in enumerate(verdicts):
        if not isinstance(item, dict):
            return False, f"verdict[{idx}] is not an object"
        missing = REQUIRED_VERDICT_KEYS - set(item)
        if judge_mode == "external_web":
            missing |= WEB_REQUIRED_VERDICT_KEYS - set(item)
        if missing:
            return False, f"verdict[{idx}] missing {sorted(missing)}"
        if item["disagreement_type"] not in DISAGREEMENT_TYPES:
            return False, f"verdict[{idx}] bad disagreement_type {item['disagreement_type']}"
        if item["likely_correct"] not in LIKELY_CORRECT:
            return False, f"verdict[{idx}] bad likely_correct {item['likely_correct']}"
        if item["severity"] not in SEVERITY:
            return False, f"verdict[{idx}] bad severity {item['severity']}"
        if not isinstance(item["agree"], bool):
            return False, f"verdict[{idx}] agree is not bool"
        if item["agree"] != (item["disagreement_type"] == "none"):
            return False, f"verdict[{idx}] agree/type invariant failed"
        if judge_mode == "external_web":
            if not isinstance(item.get("web_search_performed"), bool):
                return False, f"verdict[{idx}] web_search_performed is not bool"
            if not isinstance(item.get("source_urls"), list):
                return False, f"verdict[{idx}] source_urls is not a list"
            if item.get("web_search_performed") and not item.get("source_urls"):
                return False, f"verdict[{idx}] searched but source_urls is empty"
            if not str(item.get("korean_reason") or "").strip():
                return False, f"verdict[{idx}] korean_reason is empty"
    return True, "ok"


def fallback_payload(batch_index: int, expected_ids: list[str], reason: str, *, judge_mode: str = "static") -> dict[str, Any]:
    verdicts = [
        {
            "post_id": post_id,
            "agree": False,
            "disagreement_type": "uncertain",
            "likely_correct": "both_unclear",
            "claude_take": "agbrowse/ChatGPT Pro 호출 또는 스키마 검증 실패로 독립 판단을 확정하지 못함.",
            "severity": "low",
            "note": f"schema_fail: {reason}",
        }
        for post_id in expected_ids
    ]
    if judge_mode == "external_web":
        for item in verdicts:
            item.update(
                {
                    "judge_provider": "unknown",
                    "independent_is_novel_related": None,
                    "independent_official_title": None,
                    "independent_url": None,
                    "web_search_performed": False,
                    "source_urls": [],
                    "korean_reason": f"외부 웹검색 LLM judge 호출 또는 스키마 검증 실패로 판단을 확정하지 못했다. 실패 사유: {reason}",
                }
            )
    return {
        "batch": batch_index,
        "verdicts": verdicts,
    }


def build_web_ai_args(
    records: list[dict[str, Any]],
    batch_index: int,
    expected_ids: list[str],
    model: str,
    vendor: str,
    effort: str | None,
    provider_url: str | None,
    timeout_sec: int,
    agbrowse_bin: str,
    extra_args: list[str],
    command: str,
    provider_tab_mode: str,
    judge_mode: str,
) -> list[str]:
    provider_records = redact_sensitive_payload(records)
    prompt_template = PROMPT_TEMPLATE_EXTERNAL_WEB if judge_mode == "external_web" else PROMPT_TEMPLATE
    prompt = prompt_template.format(
        batch_index=batch_index,
        expected_count=len(expected_ids),
        post_id_list=", ".join(expected_ids),
        posts_json=json.dumps(provider_records, ensure_ascii=False, separators=(",", ":")),
    )
    system = EXTERNAL_WEB_SYSTEM if judge_mode == "external_web" else STATIC_SYSTEM
    constraints = EXTERNAL_WEB_CONSTRAINTS if judge_mode == "external_web" else STATIC_CONSTRAINTS
    cmd = resolve_agbrowse_command(agbrowse_bin) + [
        "web-ai",
        command,
        "--vendor",
        vendor,
        "--model",
        model,
        "--url",
        provider_url or PROVIDER_URLS.get(vendor, PROVIDER_URLS["chatgpt"]),
        "--inline-only",
        "--system",
        system,
        "--output",
        STRICT_OUTPUT,
        "--constraints",
        constraints,
        "--allow-copy-markdown-fallback",
        "--timeout",
        str(timeout_sec),
        "--prompt",
        prompt,
        "--json",
    ]
    if vendor == "chatgpt" and effort:
        cmd[cmd.index("--url") : cmd.index("--url")] = ["--effort", effort]
    if provider_tab_mode == "reuse":
        cmd.append("--reuse-tab")
    elif provider_tab_mode == "new":
        cmd.append("--new-tab")
    cmd.extend(extra_args)
    return cmd


def run_process(cmd: list[str], timeout_sec: int) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.setdefault("AGBROWSE_JSON_ERRORS", "1")
    try:
        return subprocess.run(
            cmd,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise TimeoutError(
            f"process timeout after {timeout_sec}s; stdout={stdout[-1000:]}; stderr={stderr[-1000:]}"
        ) from exc


def json_candidates_from_output(text: str) -> list[Any]:
    candidates: list[Any] = []
    try:
        candidates.append(extract_json_object(text))
    except Exception:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            candidates.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return candidates


def run_agbrowse_query(
    records: list[dict[str, Any]],
    batch_index: int,
    expected_ids: list[str],
    model: str,
    vendor: str,
    effort: str | None,
    provider_url: str | None,
    timeout_sec: int,
    agbrowse_bin: str,
    extra_args: list[str],
    provider_tab_mode: str,
    judge_mode: str,
) -> str:
    cmd = build_web_ai_args(
        records=records,
        batch_index=batch_index,
        expected_ids=expected_ids,
        model=model,
        vendor=vendor,
        effort=effort,
        provider_url=provider_url,
        timeout_sec=timeout_sec,
        agbrowse_bin=agbrowse_bin,
        extra_args=extra_args,
        command="query",
        provider_tab_mode=provider_tab_mode,
        judge_mode=judge_mode,
    )
    process_timeout = max(timeout_sec + 120, 180)
    completed = run_process(cmd, timeout_sec=process_timeout)
    if completed.returncode != 0:
        raise RuntimeError(
            f"agbrowse query failed rc={completed.returncode}; stdout={completed.stdout[-1000:]}; stderr={completed.stderr[-1000:]}"
        )
    return completed.stdout


def extract_session_id(text: str) -> str:
    for payload in json_candidates_from_output(text):
        if not isinstance(payload, dict):
            continue
        for key in ("sessionId", "session_id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        session = payload.get("session")
        if isinstance(session, dict):
            value = session.get("sessionId")
            if isinstance(value, str) and value:
                return value
    raise ValueError(f"sessionId not found in send output: {text[-1000:]}")


def extract_session_answer(text: str) -> str | None:
    for payload in json_candidates_from_output(text):
        if not isinstance(payload, dict):
            continue
        session = payload.get("session")
        if isinstance(session, dict) and isinstance(session.get("answer"), str):
            return session["answer"]
        final = payload.get("final")
        if isinstance(final, dict) and isinstance(final.get("answerText"), str):
            return final["answerText"]
        if isinstance(payload.get("answerText"), str):
            return payload["answerText"]
        if isinstance(payload.get("answer"), str):
            return payload["answer"]
    return None


def cleanup_chatgpt_tabs(base_cmd: list[str]) -> None:
    cmd = base_cmd + ["tab-cleanup", "--provider", "chatgpt", "--keep-provider-tabs", "1", "--json"]
    try:
        completed = run_process(cmd, timeout_sec=45)
    except Exception as exc:  # noqa: BLE001
        log(f"[warn] tab cleanup failed: {exc}", error=True)
        return
    if completed.returncode != 0:
        log(
            f"[warn] tab cleanup rc={completed.returncode}; "
            f"stdout={completed.stdout[-500:]}; stderr={completed.stderr[-500:]}",
            error=True,
        )


def prune_stale_sent_sessions(base_cmd: list[str], older_than: str = "30s") -> None:
    cmd = base_cmd + ["web-ai", "sessions", "prune", "--status", "sent", "--older-than", older_than, "--json"]
    try:
        completed = run_process(cmd, timeout_sec=45)
    except Exception as exc:  # noqa: BLE001
        log(f"[warn] stale sent-session prune failed: {exc}", error=True)
        return
    if completed.returncode != 0:
        log(
            f"[warn] stale sent-session prune rc={completed.returncode}; "
            f"stdout={completed.stdout[-500:]}; stderr={completed.stderr[-500:]}",
            error=True,
        )
        return
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return
    removed = payload.get("removed")
    if isinstance(removed, int) and removed > 0:
        log(f"[cleanup] pruned stale sent sessions: {removed}")


def run_agbrowse_session(
    records: list[dict[str, Any]],
    batch_index: int,
    expected_ids: list[str],
    model: str,
    vendor: str,
    effort: str | None,
    provider_url: str | None,
    timeout_sec: int,
    agbrowse_bin: str,
    extra_args: list[str],
    provider_tab_mode: str,
    judge_mode: str,
) -> str:
    base = resolve_agbrowse_command(agbrowse_bin)
    if vendor == "chatgpt":
        prune_stale_sent_sessions(base)
        cleanup_chatgpt_tabs(base)
    send_cmd = build_web_ai_args(
        records=records,
        batch_index=batch_index,
        expected_ids=expected_ids,
        model=model,
        vendor=vendor,
        effort=effort,
        provider_url=provider_url,
        timeout_sec=timeout_sec,
        agbrowse_bin=agbrowse_bin,
        extra_args=extra_args,
        command="send",
        provider_tab_mode=provider_tab_mode,
        judge_mode=judge_mode,
    )
    send_completed = run_process(send_cmd, timeout_sec=120)
    if send_completed.returncode != 0:
        if vendor == "chatgpt":
            prune_stale_sent_sessions(base)
        raise RuntimeError(
            f"agbrowse send failed rc={send_completed.returncode}; stdout={send_completed.stdout[-1000:]}; stderr={send_completed.stderr[-1000:]}"
        )
    session_id = extract_session_id(send_completed.stdout)

    watch_cmd = base + [
        "web-ai",
        "watch",
        "--session",
        session_id,
        "--interval",
        "15s",
        "--poll-timeout",
        "30",
        "--navigate",
        "--json",
    ]
    process_timeout = max(timeout_sec + 180, 240)
    watch_completed = run_process(watch_cmd, timeout_sec=process_timeout)

    show_cmd = base + ["web-ai", "sessions", "show", session_id, "--json"]
    show_completed = run_process(show_cmd, timeout_sec=60)
    answer = extract_session_answer(show_completed.stdout) if show_completed.returncode == 0 else None
    if answer:
        if vendor == "chatgpt":
            cleanup_chatgpt_tabs(base)
            prune_stale_sent_sessions(base)
        return answer
    answer = extract_session_answer(watch_completed.stdout)
    if answer:
        if vendor == "chatgpt":
            cleanup_chatgpt_tabs(base)
            prune_stale_sent_sessions(base)
        return answer
    if watch_completed.returncode != 0:
        if vendor == "chatgpt":
            prune_stale_sent_sessions(base)
        raise RuntimeError(
            f"agbrowse watch failed rc={watch_completed.returncode}; session={session_id}; "
            f"stdout={watch_completed.stdout[-1000:]}; stderr={watch_completed.stderr[-1000:]}"
        )
    if vendor == "chatgpt":
        prune_stale_sent_sessions(base)
    raise RuntimeError(f"session completed without extractable answer: {session_id}")


def run_model_call(
    records: list[dict[str, Any]],
    batch_index: int,
    expected_ids: list[str],
    model: str,
    vendor: str,
    effort: str | None,
    provider_url: str | None,
    timeout_sec: int,
    agbrowse_bin: str,
    extra_args: list[str],
    mode: str,
    provider_tab_mode: str,
    judge_mode: str,
) -> str:
    if mode == "query":
        return run_agbrowse_query(
            records=records,
            batch_index=batch_index,
            expected_ids=expected_ids,
            model=model,
            vendor=vendor,
            effort=effort,
            provider_url=provider_url,
            timeout_sec=timeout_sec,
            agbrowse_bin=agbrowse_bin,
            extra_args=extra_args,
            provider_tab_mode=provider_tab_mode,
            judge_mode=judge_mode,
        )
    if mode == "session":
        return run_agbrowse_session(
            records=records,
            batch_index=batch_index,
            expected_ids=expected_ids,
            model=model,
            vendor=vendor,
            effort=effort,
            provider_url=provider_url,
            timeout_sec=timeout_sec,
            agbrowse_bin=agbrowse_bin,
            extra_args=extra_args,
            provider_tab_mode=provider_tab_mode,
            judge_mode=judge_mode,
        )
    raise ValueError(f"unknown web_ai_mode: {mode}")


def load_valid_chunk(
    chunk_path: Path,
    batch_index: int,
    chunk_ids: list[str],
    *,
    judge_mode: str = "static",
) -> list[dict[str, Any]] | None:
    if not chunk_path.exists():
        return None
    try:
        payload = load_json(chunk_path)
        ok, why = validate_verdict(payload, batch_index, chunk_ids, judge_mode=judge_mode)
    except Exception as exc:  # noqa: BLE001
        ok, why = False, str(exc)
    if ok:
        return payload["verdicts"]
    log(f"[redo] {chunk_path.name}: {why}")
    return None


def chunk_path_for(out_dir: Path, batch_index: int, chunk_index: int) -> Path:
    return out_dir / f"chunk_{batch_index:03d}_{chunk_index:02d}.json"


def subchunk_path_for(out_dir: Path, batch_index: int, chunk_index: int, sub_index: int) -> Path:
    return out_dir / f"chunk_{batch_index:03d}_{chunk_index:02d}_sub{sub_index:02d}.json"


def call_and_validate_chunk(
    *,
    record_chunk: list[dict[str, Any]],
    batch_index: int,
    expected_ids: list[str],
    model: str,
    vendor: str,
    effort: str | None,
    provider_url: str | None,
    timeout_sec: int,
    agbrowse_bin: str,
    extra_args: list[str],
    mode: str,
    provider_tab_mode: str,
    judge_mode: str,
) -> tuple[dict[str, Any], str]:
    stdout = run_model_call(
        records=record_chunk,
        batch_index=batch_index,
        expected_ids=expected_ids,
        model=model,
        vendor=vendor,
        effort=effort,
        provider_url=provider_url,
        timeout_sec=timeout_sec,
        agbrowse_bin=agbrowse_bin,
        extra_args=extra_args,
        mode=mode,
        provider_tab_mode=provider_tab_mode,
        judge_mode=judge_mode,
    )
    payload = normalize_payload(extract_json_object(stdout))
    ok, why = validate_verdict(payload, batch_index, expected_ids, judge_mode=judge_mode)
    if not ok:
        raise ValueError(why)
    return payload, stdout


def call_chunk_with_split(
    *,
    record_chunk: list[dict[str, Any]],
    batch_index: int,
    chunk_index: int,
    expected_ids: list[str],
    out_dir: Path,
    attempt: int,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], str]:
    try:
        return call_and_validate_chunk(
            record_chunk=record_chunk,
            batch_index=batch_index,
            expected_ids=expected_ids,
            model=args.model,
            vendor=args.vendor,
            effort=args.effort,
            provider_url=args.provider_url,
            timeout_sec=int(args.timeout_sec),
            agbrowse_bin=args.agbrowse_bin,
            extra_args=args.extra_agbrowse_arg,
            mode=args.web_ai_mode,
            provider_tab_mode=args.provider_tab_mode,
            judge_mode=args.judge_mode,
        )
    except Exception as exc:  # noqa: BLE001
        if len(record_chunk) <= 1 or not args.split_on_failure:
            raise
        log(
            f"[split] batch {batch_index:03d} chunk {chunk_index + 1}: "
            f"{len(record_chunk)} -> singles after error: {exc}",
            error=True,
        )
        merged_verdicts: list[dict[str, Any]] = []
        last_stdout = ""
        for sub_index, single_record in enumerate(record_chunk):
            single_ids = batch_post_ids([single_record])
            sub_path = subchunk_path_for(out_dir, batch_index, chunk_index, sub_index)
            existing_sub = load_valid_chunk(sub_path, batch_index, single_ids, judge_mode=args.judge_mode)
            if existing_sub is not None:
                merged_verdicts.extend(existing_sub)
                log(
                    f"[skip] batch {batch_index:03d} chunk {chunk_index + 1} "
                    f"sub {sub_index + 1}: valid checkpoint"
                )
                continue
            log(
                f"[run] batch {batch_index:03d} chunk {chunk_index + 1} "
                f"sub {sub_index + 1}/{len(record_chunk)} post={single_ids[0]}"
            )
            try:
                sub_payload, sub_stdout = call_and_validate_chunk(
                    record_chunk=[single_record],
                    batch_index=batch_index,
                    expected_ids=single_ids,
                    model=args.model,
                    vendor=args.vendor,
                    effort=args.effort,
                    provider_url=args.provider_url,
                    timeout_sec=int(args.timeout_sec),
                    agbrowse_bin=args.agbrowse_bin,
                    extra_args=args.extra_agbrowse_arg,
                    mode=args.web_ai_mode,
                    provider_tab_mode=args.provider_tab_mode,
                    judge_mode=args.judge_mode,
                )
            except Exception as sub_exc:  # noqa: BLE001
                raise RuntimeError(f"split subchunk {sub_index} failed: {sub_exc}") from sub_exc
            last_stdout = sub_stdout
            atomic_write_json(sub_path, sub_payload)
            merged_verdicts.extend(sub_payload["verdicts"])
            append_jsonl(
                out_dir / "_run_state.jsonl",
                {
                    "batch": batch_index,
                    "chunk": chunk_index,
                    "subchunk": sub_index,
                    "status": "subchunk_ok",
                    "attempt": attempt,
                    "verdicts": len(sub_payload["verdicts"]),
                },
            )
            if float(args.chunk_sleep_sec) > 0 and sub_index < len(record_chunk) - 1:
                time.sleep(float(args.chunk_sleep_sec))
        payload = {"batch": batch_index, "verdicts": merged_verdicts}
        ok, why = validate_verdict(payload, batch_index, expected_ids, judge_mode=args.judge_mode)
        if not ok:
            raise ValueError(f"split merge invalid: {why}")
        return payload, last_stdout


def resolve_agbrowse_command(agbrowse_bin: str) -> list[str]:
    if agbrowse_bin != "agbrowse":
        return [agbrowse_bin]
    npm_root = os.environ.get("APPDATA")
    if npm_root:
        mjs = Path(npm_root) / "npm" / "node_modules" / "agbrowse" / "bin" / "agbrowse.mjs"
        node = shutil.which("node")
        if node and mjs.exists():
            return [node, str(mjs)]
    found = shutil.which("agbrowse") or shutil.which("agbrowse.cmd")
    return [found or "agbrowse"]


def chunks(records: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [records[i : i + size] for i in range(0, len(records), size)]


def run_batches(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    meta = load_json(out_dir / "_meta.json")
    args.judge_mode = getattr(args, "judge_mode", None) or meta.get("judge_mode", "static")
    args.vendor = getattr(args, "vendor", None) or meta.get("provider") or "chatgpt"
    args.model = getattr(args, "model", None) or meta.get("model") or "pro"
    if getattr(args, "effort", None) is None and args.vendor == "chatgpt":
        args.effort = "standard"
    num_batches = int(meta["num_batches"])
    start = max(0, int(args.start_batch))
    stop = num_batches if args.stop_batch is None else min(num_batches, int(args.stop_batch))
    if args.max_batches is not None:
        stop = min(stop, start + int(args.max_batches))
    failed_batches: list[dict[str, Any]] = []

    for batch_index in range(start, stop):
        batch_path = out_dir / f"batch_{batch_index:03d}.json"
        verdict_path = out_dir / f"verdict_{batch_index:03d}.json"
        batch = load_json(batch_path)
        expected_ids = batch_post_ids(batch)
        exp = expected_count(meta, batch_index)
        if len(expected_ids) != exp:
            raise RuntimeError(f"{batch_path} has {len(expected_ids)} ids, expected {exp}")

        if verdict_path.exists():
            try:
                existing = load_json(verdict_path)
                ok, why = validate_verdict(existing, batch_index, expected_ids, judge_mode=args.judge_mode)
            except Exception as exc:  # noqa: BLE001
                ok, why = False, f"existing parse failed: {exc}"
            if ok:
                log(f"[skip] batch {batch_index:03d}: valid existing verdict")
                continue
            log(f"[redo] batch {batch_index:03d}: {why}")

        last_error = "not attempted"
        for attempt in range(1, int(args.retries) + 1):
            log(f"[run] batch {batch_index:03d} attempt {attempt}/{args.retries}")
            started = time.time()
            stdout = ""
            try:
                merged_verdicts: list[dict[str, Any]] = []
                record_chunks = chunks(batch, int(args.records_per_call))
                for chunk_index, record_chunk in enumerate(record_chunks):
                    chunk_ids = batch_post_ids(record_chunk)
                    chunk_path = chunk_path_for(out_dir, batch_index, chunk_index)
                    existing_chunk = load_valid_chunk(chunk_path, batch_index, chunk_ids, judge_mode=args.judge_mode)
                    if existing_chunk is not None:
                        merged_verdicts.extend(existing_chunk)
                        log(
                            f"[skip] batch {batch_index:03d} chunk {chunk_index + 1}: "
                            f"valid checkpoint posts={len(chunk_ids)}"
                        )
                        continue
                    log(
                        f"[run] batch {batch_index:03d} chunk {chunk_index + 1}/"
                        f"{len(record_chunks)} "
                        f"posts={len(chunk_ids)}"
                    )
                    try:
                        chunk_payload, stdout = call_chunk_with_split(
                            record_chunk=record_chunk,
                            batch_index=batch_index,
                            chunk_index=chunk_index,
                            expected_ids=chunk_ids,
                            out_dir=out_dir,
                            attempt=attempt,
                            args=args,
                        )
                    except ValueError as exc:
                        raw_path = out_dir / f"raw_invalid_{batch_index:03d}_chunk{chunk_index:02d}_attempt{attempt}.txt"
                        if stdout:
                            raw_path.write_text(stdout, encoding="utf-8")
                        raise ValueError(f"chunk {chunk_index} invalid: {exc}") from exc
                    atomic_write_json(chunk_path, chunk_payload)
                    append_jsonl(
                        out_dir / "_run_state.jsonl",
                        {
                            "batch": batch_index,
                            "chunk": chunk_index,
                            "status": "chunk_ok",
                            "attempt": attempt,
                            "elapsed_sec": round(time.time() - started, 1),
                            "verdicts": len(chunk_payload["verdicts"]),
                        },
                    )
                    merged_verdicts.extend(chunk_payload["verdicts"])
                    if float(args.chunk_sleep_sec) > 0 and chunk_index < len(record_chunks) - 1:
                        time.sleep(float(args.chunk_sleep_sec))
                payload = {"batch": batch_index, "verdicts": merged_verdicts}
                ok, why = validate_verdict(payload, batch_index, expected_ids, judge_mode=args.judge_mode)
                if ok:
                    atomic_write_json(verdict_path, payload)
                    append_jsonl(
                        out_dir / "_run_state.jsonl",
                        {
                            "batch": batch_index,
                            "status": "ok",
                            "attempt": attempt,
                            "elapsed_sec": round(time.time() - started, 1),
                            "verdicts": len(payload["verdicts"]),
                        },
                    )
                    log(f"[ok] batch {batch_index:03d}: {len(payload['verdicts'])} verdicts")
                    break
                last_error = why
                raw_path = out_dir / f"raw_invalid_{batch_index:03d}_attempt{attempt}.txt"
                raw_path.write_text(stdout, encoding="utf-8")
                log(f"[invalid] batch {batch_index:03d}: {why}")
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if stdout:
                    raw_path = out_dir / f"raw_error_{batch_index:03d}_attempt{attempt}.txt"
                    raw_path.write_text(stdout, encoding="utf-8")
                append_jsonl(
                    out_dir / "_run_state.jsonl",
                    {
                        "batch": batch_index,
                        "status": "error",
                        "attempt": attempt,
                        "elapsed_sec": round(time.time() - started, 1),
                        "error": last_error[-2000:],
                    },
                )
                log(f"[error] batch {batch_index:03d}: {last_error}", error=True)
            if attempt < int(args.retries):
                time.sleep(float(args.retry_sleep_sec))
        else:
            if args.no_fallback:
                log(f"[fail] batch {batch_index:03d}: {last_error}", error=True)
                failed_batches.append({"batch": batch_index, "error": last_error[-2000:]})
                append_jsonl(
                    out_dir / "_run_state.jsonl",
                    {
                        "batch": batch_index,
                        "status": "failed_no_fallback",
                        "error": last_error[-2000:],
                    },
                )
                if args.continue_on_fail:
                    continue
                return 2
            payload = fallback_payload(batch_index, expected_ids, last_error, judge_mode=args.judge_mode)
            atomic_write_json(verdict_path, payload)
            append_jsonl(
                out_dir / "_run_state.jsonl",
                {
                    "batch": batch_index,
                    "status": "fallback",
                    "error": last_error[-2000:],
                    "verdicts": len(payload["verdicts"]),
                },
            )
            log(f"[fallback] batch {batch_index:03d}: {last_error}")
    if failed_batches:
        log(f"[failures] {len(failed_batches)} batch(es) incomplete: {failed_batches[:10]}", error=True)
        return 2
    return 0


def collect_verdicts(out_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta = load_json(out_dir / "_meta.json")
    judge_mode = meta.get("judge_mode", "static")
    all_verdicts: list[dict[str, Any]] = []
    valid_batches = 0
    invalid: list[dict[str, Any]] = []
    for batch_index in range(int(meta["num_batches"])):
        batch = load_json(out_dir / f"batch_{batch_index:03d}.json")
        expected_ids = batch_post_ids(batch)
        verdict_path = out_dir / f"verdict_{batch_index:03d}.json"
        if not verdict_path.exists():
            invalid.append({"batch": batch_index, "reason": "missing"})
            continue
        try:
            payload = load_json(verdict_path)
            ok, why = validate_verdict(payload, batch_index, expected_ids, judge_mode=judge_mode)
        except Exception as exc:  # noqa: BLE001
            ok, why, payload = False, str(exc), None
        if not ok:
            invalid.append({"batch": batch_index, "reason": why})
            continue
        valid_batches += 1
        for verdict in payload["verdicts"]:
            item = dict(verdict)
            item["_batch"] = batch_index
            all_verdicts.append(item)
    return {"meta": meta, "valid_batches": valid_batches, "invalid_batches": invalid}, all_verdicts


def aggregate(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    state, verdicts = collect_verdicts(out_dir)
    meta = state["meta"]
    by_type = Counter(v["disagreement_type"] for v in verdicts)
    by_severity = Counter(v["severity"] for v in verdicts)
    agree = sum(1 for v in verdicts if v["agree"])
    high_issues = [
        {
            "post_id": v["post_id"],
            "type": v["disagreement_type"],
            "correct": v["likely_correct"],
            "claude": v["claude_take"],
            "note": v["note"],
        }
        for v in verdicts
        if (not v["agree"]) and v["severity"] == "high"
    ]
    ids_by_type: dict[str, list[Any]] = defaultdict(list)
    for v in verdicts:
        ids_by_type[v["disagreement_type"]].append(v["post_id"])
    web_search_count = sum(1 for v in verdicts if v.get("web_search_performed") is True)
    source_url_count = sum(len(v.get("source_urls") or []) for v in verdicts)

    result = {
        "judge_mode": meta.get("judge_mode", "static"),
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "total_judged": len(verdicts),
        "expected_total": meta["total"],
        "batches_ok": state["valid_batches"],
        "num_batches": meta["num_batches"],
        "invalid_batches": state["invalid_batches"],
        "agree": agree,
        "disagree": len(verdicts) - agree,
        "by_disagreement_type": dict(sorted(by_type.items())),
        "by_severity": {s: by_severity.get(s, 0) for s in ("high", "med", "low")},
        "high_severity_issues": high_issues,
        "post_ids_by_type": {k: v for k, v in sorted(ids_by_type.items())},
        "web_search_performed": web_search_count,
        "source_url_count": source_url_count,
    }
    atomic_write_json(out_dir / "_result.json", result)
    atomic_write_json(out_dir / "post_ids_by_type.json", result["post_ids_by_type"])

    with (out_dir / "post_reviews.jsonl").open("w", encoding="utf-8") as f:
        for v in verdicts:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    write_post_review_markdown(out_dir / "post_reviews.md", result, verdicts)
    log(
        " ".join(
            [
                "판정",
                str(result["total_judged"]),
                "/",
                str(result["expected_total"]),
                "배치",
                str(result["batches_ok"]),
                "/",
                str(result["num_batches"]),
                "일치",
                str(result["agree"]),
            ]
        )
    )
    if result["invalid_batches"]:
        log(f"invalid_batches: {result['invalid_batches'][:10]}", error=True)
        return 3
    return 0


def md_escape(value: Any, limit: int = 220) -> str:
    text = str(value if value is not None else "")
    text = text.replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def write_post_review_markdown(path: Path, result: dict[str, Any], verdicts: list[dict[str, Any]]) -> None:
    external = result.get("judge_mode") == "external_web"
    lines = [
        "# External LLM-Judge Post Reviews" if external else "# GPT Pro LLM-Judge Post Reviews",
        "",
        f"- judge_mode: {result.get('judge_mode')}",
        f"- provider/model: {result.get('provider')}/{result.get('model')}",
        f"- total_judged: {result['total_judged']} / {result['expected_total']}",
        f"- batches_ok: {result['batches_ok']} / {result['num_batches']}",
        f"- agree: {result['agree']}",
        f"- disagree: {result['disagree']}",
        f"- web_search_performed: {result.get('web_search_performed', 0)}",
        f"- source_url_count: {result.get('source_url_count', 0)}",
        "",
    ]
    if external:
        lines += [
            "| post_id | agree | type | correct | severity | independent_title | searched | sources | 한국어 판단 사유 |",
            "|---|---:|---|---|---|---|---:|---|---|",
        ]
    else:
        lines += [
            "| post_id | agree | type | correct | severity | take | note |",
            "|---|---:|---|---|---|---|---|",
        ]
    for v in verdicts:
        if external:
            sources = ", ".join(str(url) for url in (v.get("source_urls") or []))
            cells = [
                md_escape(v["post_id"], 60),
                md_escape(v["agree"], 20),
                md_escape(v["disagreement_type"], 60),
                md_escape(v["likely_correct"], 40),
                md_escape(v["severity"], 20),
                md_escape(v.get("independent_official_title"), 120),
                md_escape(v.get("web_search_performed"), 20),
                md_escape(sources, 220),
                md_escape(v.get("korean_reason") or v.get("note"), 360),
            ]
        else:
            cells = [
                md_escape(v["post_id"], 60),
                md_escape(v["agree"], 20),
                md_escape(v["disagreement_type"], 60),
                md_escape(v["likely_correct"], 40),
                md_escape(v["severity"], 20),
                md_escape(v["claude_take"], 180),
                md_escape(v["note"], 220),
            ]
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    build_p = sub.add_parser("build")
    build_p.add_argument("--result", required=True)
    build_p.add_argument("--out-dir", required=True)
    build_p.add_argument("--batch-size", type=int, default=5)
    build_p.add_argument("--judge-mode", choices=["static", "external_web"], default="external_web")
    build_p.add_argument("--vendor", choices=["chatgpt", "gemini", "grok"], default="chatgpt")
    build_p.add_argument("--model", default="pro")
    build_p.add_argument("--post-id", action="append")
    build_p.add_argument("--limit", type=int)
    build_p.set_defaults(func=build_batches)

    run_p = sub.add_parser("run")
    run_p.add_argument("--out-dir", required=True)
    run_p.add_argument("--judge-mode", choices=["static", "external_web"])
    run_p.add_argument("--vendor", choices=["chatgpt", "gemini", "grok"])
    run_p.add_argument("--model")
    run_p.add_argument("--effort")
    run_p.add_argument("--provider-url")
    run_p.add_argument("--timeout-sec", type=int, default=1200)
    run_p.add_argument("--retries", type=int, default=3)
    run_p.add_argument("--retry-sleep-sec", type=float, default=5.0)
    run_p.add_argument("--chunk-sleep-sec", type=float, default=0.0)
    run_p.add_argument("--records-per-call", type=int, default=5)
    run_p.add_argument("--start-batch", type=int, default=0)
    run_p.add_argument("--stop-batch", type=int)
    run_p.add_argument("--max-batches", type=int)
    run_p.add_argument("--agbrowse-bin", default="agbrowse")
    run_p.add_argument("--web-ai-mode", choices=["session", "query"], default="session")
    run_p.add_argument("--provider-tab-mode", choices=["reuse", "new", "default"], default="reuse")
    run_p.add_argument("--split-on-failure", action=argparse.BooleanOptionalAction, default=True)
    run_p.add_argument("--no-fallback", action="store_true")
    run_p.add_argument("--continue-on-fail", action="store_true")
    run_p.add_argument("--extra-agbrowse-arg", action="append", default=[])
    run_p.set_defaults(func=run_batches)

    agg_p = sub.add_parser("aggregate")
    agg_p.add_argument("--out-dir", required=True)
    agg_p.set_defaults(func=aggregate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
