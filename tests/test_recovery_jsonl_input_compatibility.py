"""일반 JSONL의 생략된 embedded 댓글과 별도 댓글 원문을 함께 보존한다."""
from copy import deepcopy
import hashlib
import json

import pytest

from src.llm_batch.measurement.recovery_execution_contract import (
    RecoveryExecutionContractError, _input_snapshot,
)


def encode(records):
    return b"".join(json.dumps(record, ensure_ascii=False).encode() + b"\n" for record in records)


@pytest.mark.parametrize("fallback", [False, True])
def test_missing_comments_matches_main_loader_without_altering_original_records(tmp_path, fallback):
    import expert_main
    post = {"post_id": 101, "gallery_id": "synthetic", "title": "원문", "content": ["본문"]}
    if fallback:
        post["comments_raw"] = [{"comment_id": "embedded", "content": "내장 댓글"}]
    second = {**post, "post_id": 102}
    second.pop("comments_raw", None)
    separate = [{"post_id": 101, "comment_id": "a", "content": "첫 원문 댓글"},
                {"post_id": 102, "comment_id": "b", "content": "다른 게시물 댓글"},
                {"post_id": 101, "comment_id": "c", "content": "둘째 원문 댓글"}]
    records = [post, separate[0], second, *separate[1:]]
    original = deepcopy(records)
    raw = encode(records)
    path = tmp_path / "input.jsonl"
    path.write_bytes(raw)
    posts, binding = _input_snapshot(raw, "JSONL_POST_COMMENT_V1")
    loaded = expert_main.load_jsonl_posts(path, snapshot_bytes=raw)
    assert posts == [post, second] and "comments" not in posts[0]
    assert [b["result_comments"] for b in binding["post_bindings"]] == [
        [c["content"] for c in p.comments] for p in loaded]
    assert binding["post_bindings"][0]["result_comments"] == [
        "첫 원문 댓글", "둘째 원문 댓글", *(["내장 댓글"] if fallback else [])]
    assert [b["payload"] for b in binding["records"]] == original
    assert [b["raw_line_sha256"] for b in binding["records"]] == [
        hashlib.sha256(line).hexdigest() for line in raw.splitlines()]
    assert records == original and path.read_bytes() == raw


@pytest.mark.parametrize("field", ["comments", "comments_raw"])
@pytest.mark.parametrize("value", [None, 0, 2, True, "댓글을 버리지 않는다", {"content": "목록이 아닌 댓글"}])
def test_explicit_non_list_comments_never_become_an_empty_projection(field, value):
    post = {"post_id": 101, field: value}
    with pytest.raises(RecoveryExecutionContractError, match="explicit list"):
        _input_snapshot(encode([post]), "JSONL_POST_COMMENT_V1")


@pytest.mark.parametrize("comments", [
    [{"post_id": 102, "comment_id": "a", "content": "부모 없는 댓글"}],
    [{"post_id": 101, "comment_id": "a", "content": "첫 댓글"},
     {"post_id": 101, "comment_id": "a", "content": "중복 ID의 다른 댓글"}],
])
def test_absent_embedded_field_does_not_relax_orphan_or_duplicate_checks(comments):
    with pytest.raises(RecoveryExecutionContractError, match="orphan|duplicate"):
        _input_snapshot(encode([{"post_id": 101}, *comments]), "JSONL_POST_COMMENT_V1")


def test_json_array_contract_still_requires_explicit_comments():
    with pytest.raises(RecoveryExecutionContractError, match="explicit list"):
        _input_snapshot(json.dumps([{"post_id": 101}]).encode(), "JSON_ARRAY_V1")
