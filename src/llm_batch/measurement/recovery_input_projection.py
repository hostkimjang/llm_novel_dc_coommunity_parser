"""원시 게시글과 main의 텍스트·블록·이미지 투영을 순수 검산한다.

main loader를 import하거나 원문을 다시 쓰지 않는다. 구조형 입력은 loader의
명시적 부분집합만 허용하며, 과거 문자열 content의 정확 비교 계약도 유지한다.
댓글/전체 입력 순서/WAL 및 raw bytes SHA는 호출자의 기존 계약이 검산한다.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re


MAX_BLOCKS = 10000
_TEXT = frozenset({"text", "plain_text", "paragraph"})
_IMAGE = frozenset({"image", "img", "photo", "picture"})
_BLOCK_KEYS = frozenset({"type", "text", "content", "url", "image_url", "src"})
_IMAGE_SUFFIX = re.compile(r"\.(?:png|jpe?g|gif|webp)(?:[?#].*)?$", re.I)


class RecoveryInputProjectionError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise RecoveryInputProjectionError(code)


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise RecoveryInputProjectionError("INPUT_PROJECTION_INVALID_JSON") from exc


def _same(left, right, code):
    _require(_canonical(left) == _canonical(right), code)


def project_main_input_content(source_post):
    """실제 loader→process_one→public block helper와 같은 명시 투영을 반환한다.

문자열 블록은 loader처럼 strip하고, dict의 text는 그대로 content에 보존한다.
public content_blocks의 text/url은 main처럼 strip하며 이미지 URL은 순서대로
중복을 제거한다. 불명확한 alias·비문자열 변환·알 수 없는 블록은 거절한다.
"""
    _require(type(source_post) is dict, "ORIGINAL_INPUT_OBJECT_REQUIRED")
    for field in ("input_truncated", "truncated", "_input_truncated"):
        if field in source_post:
            _require(source_post[field] is False, "ORIGINAL_INPUT_TRUNCATED_OR_INVALID")
    for field in ("parse_error_codes", "parse_errors", "_parse_errors"):
        if field in source_post:
            value = source_post[field]
            _require(value is None or type(value) is str and value == ""
                     or type(value) is list and not value, "ORIGINAL_INPUT_PARSE_ERRORS")
    blocks, content = source_post.get("content_blocks"), source_post.get("content")
    if blocks is not None and content is not None:
        _same(blocks, content, "ORIGINAL_CONTENT_ALIAS_CONFLICT")
    selected = blocks if blocks is not None else content
    _require(selected is not None, "ORIGINAL_INPUT_FIELD_MISSING")
    raw_blocks = [selected] if type(selected) is str else selected
    _require(type(raw_blocks) is list and len(raw_blocks) <= MAX_BLOCKS,
             "ORIGINAL_CONTENT_BLOCKS_NOT_SEQUENCE_OR_LIMIT")
    structured = blocks is not None or any(type(item) is dict for item in raw_blocks)
    texts, public, images = [], [], []
    for item in raw_blocks:
        if type(item) is str:
            kind, text, url = "text", item.strip(), None
            if not text:
                continue
        else:
            _require(type(item) is dict, "ORIGINAL_CONTENT_BLOCK_UNPARSEABLE")
            _require(not (set(item) - _BLOCK_KEYS), "ORIGINAL_CONTENT_BLOCK_UNKNOWN_FIELDS")
            kind = item.get("type")
            _require(type(kind) is str and kind.strip().casefold() in _TEXT | _IMAGE,
                     "ORIGINAL_CONTENT_BLOCK_TYPE_INVALID")
            for key in ("text", "content", "url", "image_url", "src"):
                _require(item.get(key) is None or type(item[key]) is str,
                         "ORIGINAL_CONTENT_BLOCK_VALUE_NOT_STRING")
            if item.get("text") is not None and item.get("content") is not None:
                _same(item["text"], item["content"], "ORIGINAL_CONTENT_BLOCK_TEXT_ALIAS_CONFLICT")
            urls = [item[key].strip() for key in ("url", "image_url", "src") if item.get(key)]
            _require(len(set(urls)) <= 1, "ORIGINAL_CONTENT_BLOCK_URL_ALIAS_CONFLICT")
            text = item.get("text") if item.get("text") is not None else item.get("content")
            url = item.get("url") or item.get("image_url") or item.get("src")
            if kind.strip().casefold() in _IMAGE:
                _require(type(url) is str and bool(url.strip()), "ORIGINAL_IMAGE_URL_MISSING")
        if text:
            texts.append(text)
        record = {"type": kind.strip()}
        if text and text.strip():
            record["text"] = text.strip()
        if url and url.strip():
            record["url"] = url.strip()
        if "text" not in record and "url" not in record:
            continue
        public.append(record)
        public_url = record.get("url")
        if public_url and public_url not in images and (
                record["type"].lower() in _IMAGE or _IMAGE_SUFFIX.search(public_url)):
            images.append(public_url)
    # legacy exact content의 허용 여부도 입력 구조만으로 결정한다.
    return {"structured": structured, "content": texts, "content_blocks": public,
            "image_urls": images, "image_count": len(images)}


def validate_main_input_projection(source_post, result):
    """원문/결과를 변경하지 않고 source-bound main 투영 또는 legacy exact를 검산한다."""
    _require(type(source_post) is dict and type(result) is dict, "ORIGINAL_INPUT_RESULT_OBJECT_REQUIRED")
    for key in ("gallery_id", "post_id", "title"):
        _require(key in source_post and key in result, "ORIGINAL_INPUT_FIELD_MISSING")
        _same(source_post[key], result[key], "ORIGINAL_INPUT_RESULT_MISMATCH")
    expected = project_main_input_content(source_post)
    _require("content" in result, "ORIGINAL_INPUT_FIELD_MISSING")
    legacy_exact = (not expected["structured"]
                    and _canonical(source_post["content"]) == _canonical(result["content"]))
    if not legacy_exact:
        _same(result["content"], expected["content"], "ORIGINAL_CONTENT_PROJECTION_MISMATCH")
    for key in ("content_blocks", "image_urls"):
        _require(not expected["structured"] or key in result, "ORIGINAL_PUBLIC_BLOCK_PROJECTION_MISSING")
        if key in result:
            _same(result[key], expected[key], "ORIGINAL_" + key.upper() + "_PROJECTION_MISMATCH")
    if "image_count" in result and (expected["structured"] or "image_urls" in result or "content_blocks" in result):
        _require(type(result["image_count"]) is int and result["image_count"] == expected["image_count"],
                 "ORIGINAL_IMAGE_COUNT_PROJECTION_MISMATCH")
    return {"mode": "LEGACY_TEXT_EXACT" if legacy_exact else "MAIN_BLOCK_PROJECTION", **deepcopy(expected)}
