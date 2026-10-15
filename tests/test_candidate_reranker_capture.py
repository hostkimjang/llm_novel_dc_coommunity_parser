"""실제 선택 전 입력의 보존·UTF-8 좌표·배타 저장·실패 비간섭을 검증한다."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from threading import Barrier
from unittest.mock import patch

import pytest


def test_semantic_capture_preserves_alias_evidence_and_replays_without_original_files(tmp_path, monkeypatch):
    from test_candidate_reranker_runtime import semantic_observed, binding
    from src.llm_batch.grounding.candidate_reranker_capture import validate_capture
    from src.llm_batch.runtime.candidate_capture import export_candidate_capture_fields
    scorer, state, package, observed_value = semantic_observed(tmp_path)
    result = SimpleNamespace(_candidate_reranker_shadow=observed_value["receipt"],
        _candidate_reranker_capture=observed_value["capture"], _candidate_reranker_semantics=package)
    output = tmp_path / "stored"
    ref = export_candidate_capture_fields(result, scorer, binding=binding(state["post"].post_id), output_dir=output,
        input_snapshot_sha256=state["input_sha256"], current_post=state["post"], retrieval_observer=state["retrieval"],
        semantic_observer=state["observer"])["candidate_reranker_capture"]
    assert ref["status"] == "SAVED" and ref["schema_version"] == "candidate_reranker_capture_ref_v2", ref
    raw = (output / ref["artifact"]["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ref["artifact"]["sha256"]
    artifact = json.loads(raw)
    assert artifact["schema_version"] == "candidate_reranker_capture_artifact_v2"
    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", lambda *a, **k: pytest.fail("capture replay read original files"))
        assert validate_capture(artifact["observation"]) == observed_value["capture"]
    assert artifact["observation"]["semantic_payloads_base64"]
    assert artifact["observation"]["training_readiness"] == "NOT_ASSIGNED_OR_ADJUDICATED"


@pytest.mark.parametrize("fault", ["alias", "payload", "receipt", "typed_post"])
def test_semantic_capture_resealed_cross_links_are_rejected(tmp_path, fault):
    from test_candidate_reranker_runtime import semantic_observed
    from src.llm_batch.grounding.candidate_reranker_capture import validate_capture, canonical_sha256
    _, _, _, observed_value = semantic_observed(tmp_path)
    value = deepcopy(observed_value["capture"])
    if fault == "alias": value["frozen_view"]["candidates"][0]["aliases"].append("위조")
    elif fault == "payload":
        key = next(iter(value["semantic_payloads_base64"]))
        value["semantic_payloads_base64"][key] = "eA=="
    elif fault == "typed_post": value["post_id"] = str(value["post_id"])
    else:
        value["raw_receipt"]["semantic_consumption"]["semantic_input_sha256"] = "f" * 64
        value["raw_receipt"]["receipt_sha256"] = canonical_sha256({k:v for k,v in value["raw_receipt"].items()
            if k not in {"receipt_sha256", "latency_ms", "binding"}})
    value["capture_sha256"] = canonical_sha256({k:v for k,v in value.items() if k != "capture_sha256"})
    with pytest.raises(ValueError): validate_capture(value)


def test_semantic_capture_save_requires_fresh_runtime_context(tmp_path):
    from test_candidate_reranker_runtime import semantic_observed, binding
    from src.llm_batch.runtime.candidate_capture import export_candidate_capture_fields
    scorer, state, package, observed_value = semantic_observed(tmp_path)
    result = SimpleNamespace(_candidate_reranker_shadow=observed_value["receipt"],
        _candidate_reranker_capture=observed_value["capture"], _candidate_reranker_semantics=package)
    changed = state["post"].model_copy(deep=True, update={"title": "다른 원문"})
    output = tmp_path / "must-not-write"
    ref = export_candidate_capture_fields(result, scorer, binding=binding(state["post"].post_id), output_dir=output,
        input_snapshot_sha256=state["input_sha256"], current_post=changed, retrieval_observer=state["retrieval"],
        semantic_observer=state["observer"])["candidate_reranker_capture"]
    assert ref["status"] == "NOT_AVAILABLE" and ref["artifact"] is None and not output.exists()

from src.llm_batch.grounding import candidate_reranker_capture as capture
from src.llm_batch.runtime import candidate_reranker as runtime
from src.llm_batch.runtime import candidate_capture as storage
from test_candidate_reranker_runtime import setup_scorer, setup_retrieval, _post, binding


def observed(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    post = _post(); post.title = "🌟 오늘 저녁 비교와 오늘 저녁"
    receipt = retrieval.observe(runtime._source_view(post))
    result = runtime.observe_candidate_reranker_with_capture(scorer, post, receipt, retrieval)
    return scorer, retrieval, post, receipt, result


def saved(tmp_path):
    scorer, retrieval, post, receipt, observed_value = observed(tmp_path)
    result = SimpleNamespace(_candidate_reranker_capture=observed_value["capture"],
                             _candidate_reranker_shadow=observed_value["receipt"])
    return result, observed_value, scorer


def test_single_actual_score_preserves_native_id_input_and_utf8_coordinates(tmp_path):
    scorer, _ = setup_scorer(tmp_path)
    retrieval = setup_retrieval(tmp_path)
    post = _post(); post.title = "🌟 오늘 저녁 비교와 오늘 저녁"
    original = post.model_dump()
    r2 = retrieval.observe(runtime._source_view(post))
    real = type(scorer).score; calls = []
    def scored(self, view):
        calls.append(deepcopy(view)); return real(self, view)
    with patch.object(type(scorer), "score", scored):
        result = runtime.observe_candidate_reranker_with_capture(scorer, post, r2, retrieval)
    assert len(calls) == 1
    value = capture.validate_capture(result["capture"])
    assert value["frozen_view"] == calls[0]
    assert type(value["post_id"]) is int and post.model_dump() == original
    assert value["raw_receipt"] == result["receipt"]
    assert value["training_readiness"] == "NOT_ASSIGNED_OR_ADJUDICATED"
    assert not value["publication_authority"] and value["role_byte_spans"]
    texts = {f["raw_path"]: f["text"] for f in value["frozen_view"]["source_view"]["fragments"]}
    for row in value["role_byte_spans"]:
        part = texts[row["raw_path"]].encode("utf-8")[row["utf8_byte_start"]:row["utf8_byte_end"]]
        assert hashlib.sha256(part).hexdigest() == row["text_sha256"]
    assert any(row["utf8_byte_start"] > row["char_start"] for row in value["role_byte_spans"])
    post.title = "나중에 변경된 제목"
    result["receipt"]["ranked_candidates"].clear()
    assert value["frozen_view"] == calls[0] and value["raw_receipt"]["ranked_candidates"]


def test_legacy_observer_and_capture_failure_do_not_change_raw_result(tmp_path):
    scorer, retrieval, post, r2, _ = observed(tmp_path)
    with patch.object(capture, "build_capture", side_effect=ValueError("CAPTURE_BYTE_LIMIT")):
        old = runtime.observe_candidate_reranker(scorer, post, r2, retrieval)
        new = runtime.observe_candidate_reranker_with_capture(scorer, post, r2, retrieval)
    assert new["capture"] is None
    assert {k:v for k,v in old.items() if k != "latency_ms"} == {k:v for k,v in new["receipt"].items() if k != "latency_ms"}
    assert old["status"] == "SCORED_SYNTHETIC"
    assert runtime.observe_candidate_reranker_with_capture(None, post, r2, retrieval) == {"receipt": None, "capture": None}


@pytest.mark.parametrize("field", ["source_fragments", "role_byte_spans", "post_id", "frozen_view_sha256", "raw_receipt_sha256", "training_readiness"])
def test_resealed_projection_changes_are_rejected(tmp_path, field):
    *_, observed_value = observed(tmp_path)
    value = observed_value["capture"]
    assert value is not None
    if field in {"source_fragments", "role_byte_spans"}: value[field] = []
    elif field == "post_id": value[field] = str(value[field])
    else: value[field] = "changed"
    value["capture_sha256"] = capture.canonical_sha256({k:v for k,v in value.items() if k != "capture_sha256"})
    with pytest.raises(ValueError): capture.validate_capture(value)


def test_capture_storage_binds_input_row_and_reuses_only_identical_bytes(tmp_path):
    result, observed_value, scorer = saved(tmp_path)
    snapshot = "a" * 64
    out = tmp_path / "out"; out.mkdir()
    kwargs = dict(binding=binding(), output_dir=out, input_snapshot_sha256=snapshot)
    ref = storage.export_candidate_capture_fields(result, object(), **kwargs)["candidate_reranker_capture"]
    assert ref["status"] == "SAVED"
    assert ref["observation_sha256"] == observed_value["capture"]["capture_sha256"]
    path = out / ref["artifact"]["path"]; before = path.read_bytes()
    assert ref["artifact"]["sha256"] == hashlib.sha256(before).hexdigest()
    artifact = json.loads(before)
    assert artifact["observation"] == observed_value["capture"]
    assert artifact["binding"] == {**binding(), "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    assert artifact["input_snapshot_sha256"] == snapshot
    again = storage.export_candidate_capture_fields(result, object(), **kwargs)["candidate_reranker_capture"]
    assert again == ref and path.read_bytes() == before
    path.write_bytes(b"existing contents must stay")
    failed = storage.export_candidate_capture_fields(result, object(), **kwargs)["candidate_reranker_capture"]
    assert failed["status"] == "NOT_AVAILABLE" and failed["artifact"] is None
    assert path.read_bytes() == b"existing contents must stay"


def test_missing_stale_and_file_write_failure_never_publish_success_ref(tmp_path):
    result, _, scorer = saved(tmp_path)
    out = tmp_path / "out"; out.mkdir()
    kwargs = dict(binding=binding(), output_dir=out, input_snapshot_sha256="a" * 64)
    assert storage.export_candidate_capture_fields(result, None, **kwargs) == {}
    off = storage.export_candidate_capture_fields(None, object(), **kwargs)["candidate_reranker_capture"]
    assert off["status"] == "NOT_EXECUTED" and off["artifact"] is None
    stale = storage.export_candidate_capture_fields(result, object(), **{**kwargs,"binding": binding(902)})["candidate_reranker_capture"]
    assert stale["status"] == "NOT_AVAILABLE" and stale["artifact"] is None
    from tools import run_candidate_reranker_training as local
    with patch.object(local,"_write",side_effect=OSError("disk failure")):
        failed = storage.export_candidate_capture_fields(result,object(),**kwargs)["candidate_reranker_capture"]
    assert failed["status"] == "NOT_AVAILABLE" and failed["artifact"] is None
    assert list(out.rglob("*.json")) == []


def test_parallel_capture_is_per_call_not_last_worker_state(tmp_path):
    scorer, retrieval, post, _, _ = observed(tmp_path)
    def observe(index):
        item = deepcopy(post); item.post_id = 910 + index
        raw = retrieval.observe(runtime._source_view(item))
        return runtime.observe_candidate_reranker_with_capture(scorer,item,raw,retrieval)
    with ThreadPoolExecutor(max_workers=2) as pool: values = list(pool.map(observe, range(2)))
    assert [v["capture"]["post_id"] for v in values] == [910,911]
    assert len({v["capture"]["capture_sha256"] for v in values}) == 2
    assert all(v["capture"]["raw_receipt"] == v["receipt"] for v in values)


@pytest.mark.parametrize("mutation,reason", [
    ("candidate_ids", "CAPTURE_CANDIDATE_IDS_MISMATCH"),
    ("candidate_order", "CAPTURE_CANDIDATE_IDS_MISMATCH"),
    ("roles", "CAPTURE_CANDIDATE_ROLES_MISMATCH"),
    ("namespace", "CAPTURE_GENERATION_BINDING_MISMATCH"),
    ("candidate_set", "CAPTURE_GENERATION_BINDING_MISMATCH"),
])
def test_resealed_receipt_must_match_actual_view_candidates_and_roles(tmp_path, mutation, reason):
    *_, observed_value = observed(tmp_path)
    value = deepcopy(observed_value["capture"])
    raw = value["raw_receipt"]
    if mutation == "candidate_ids":
        mapping = {key: "other-" + key for key in raw["frozen_candidate_ids"]}
        raw["frozen_candidate_ids"] = [mapping[key] for key in raw["frozen_candidate_ids"]]
        for row in raw["ranked_candidates"] + raw["candidate_observations"]:
            row["candidate_id"] = mapping[row["candidate_id"]]
        raw["ranked_candidates"].sort(key=lambda row: (-row["score"], row["candidate_id"]))
    elif mutation == "candidate_order":
        assert len(raw["frozen_candidate_ids"]) > 1
        raw["frozen_candidate_ids"].reverse()
        raw["candidate_observations"].reverse()
    elif mutation == "roles":
        roles = [role for row in raw["candidate_observations"] for role in row["role_observations"]]
        assert roles
        roles[0]["text_sha256"] = "f" * 64
    elif mutation == "namespace":
        raw["candidate_namespace"] = "CANDIDATE_OPTION"
    else:
        raw["candidate_set_fingerprint"] = "c" * 64
    runtime._seal(raw)
    # 기존 내부 validator와 해시를 통과하는 의미 불일치를 직접 재판독한다.
    assert runtime._valid_receipt(raw, value["scorer_summary"], value["post_id"], require_roles=True)
    value["raw_receipt_sha256"] = raw["receipt_sha256"]
    value["capture_sha256"] = capture.canonical_sha256({k: v for k, v in value.items() if k != "capture_sha256"})
    with pytest.raises(ValueError, match=reason):
        capture.validate_capture(value)


@pytest.mark.parametrize("state", ["TRUNCATED", "EMPTY_CANDIDATE_SET", "UNAVAILABLE_MODEL", "RECEIPT_BYTE_LIMIT"])
def test_capture_preserves_normal_non_scored_and_omitted_detail_terminals(tmp_path, state):
    scorer, _ = setup_scorer(tmp_path)
    # 공유 fixture가 반환한 실제 클래스의 모듈을 사용한다. src.llm_batch와
    # llm_batch가 함께 로드돼도 다른 모듈의 상한을 patch하지 않는다.
    adapter = importlib.import_module(type(scorer).__module__)
    retrieval = setup_retrieval(tmp_path, top_k=1 if state == "TRUNCATED" else 20)
    post = _post()
    if state == "EMPTY_CANDIDATE_SET":
        post.title, post.content_blocks, post.comments = "없는표현", [], []
    if state == "UNAVAILABLE_MODEL":
        scorer = adapter.unavailable_scorer()
    upstream = retrieval.observe(runtime._source_view(post))
    original = type(scorer).score
    assert original.__globals__ is vars(adapter)
    limited_calls = []
    def limited(self, view):
        with patch.object(adapter, "MAX_RECEIPT_BYTES", 1200):
            raw = original(self, view)
        limited_calls.append(raw["status"])
        return raw
    with ExitStack() as stack:
        if state == "RECEIPT_BYTE_LIMIT":
            stack.enter_context(patch.object(type(scorer), "score", limited))
        value = runtime.observe_candidate_reranker_with_capture(scorer, post, upstream, retrieval)
    expected = {"TRUNCATED": "NOT_SCORED_GENERATION_TRUNCATED", "RECEIPT_BYTE_LIMIT": "LIMIT_EXCEEDED"}.get(state, state)
    assert value["receipt"]["status"] == expected
    checked = capture.validate_capture(value["capture"])
    assert checked["raw_receipt"] == value["receipt"]
    assert checked["raw_receipt"]["ranked_candidates"] == []
    if state == "RECEIPT_BYTE_LIMIT":
        assert limited_calls == ["LIMIT_EXCEEDED"]
        assert checked["raw_receipt"]["candidate_observations"] == []
        assert checked["raw_receipt"]["details_available"] is False
    if state == "TRUNCATED":
        raw = deepcopy(checked["raw_receipt"])
        raw["generation_status"] = "COMPLETE"
        runtime._seal(raw)
        assert runtime._valid_receipt(raw, checked["scorer_summary"], post.post_id, require_roles=True)
        with pytest.raises(ValueError, match="CAPTURE_GENERATION_BINDING_MISMATCH"):
            capture.build_capture(checked["frozen_view"], raw, checked["retrieval_receipt"], checked["scorer_summary"])


@pytest.mark.parametrize("phase", ["partial_write", "fsync", "pending_read", "pending_mismatch", "final_read"])
def test_failed_capture_write_is_not_a_final_ref_and_later_retry_can_succeed(tmp_path, phase):
    from tools import run_candidate_reranker_training as local
    result, _, _ = saved(tmp_path)
    original = capture.canonical_bytes(result._candidate_reranker_shadow)
    out = tmp_path / "out"; out.mkdir()
    kwargs = dict(binding=binding(), output_dir=out, input_snapshot_sha256="a" * 64)
    real_read = local._read
    def broken_write(path, value):
        with path.open("xb") as stream:
            stream.write(b'{"incomplete":')
        raise OSError("partial write")
    def broken_read(path, limit):
        if (phase.startswith("pending") and path.suffix == ".pending") or (phase == "final_read" and path.suffix == ".json"):
            if phase == "pending_mismatch":
                return b"wrong bytes"
            raise OSError("readback failure")
        return real_read(path, limit)
    with ExitStack() as stack:
        if phase == "partial_write":
            stack.enter_context(patch.object(local, "_write", broken_write))
        elif phase == "fsync":
            stack.enter_context(patch.object(local.os, "fsync", side_effect=OSError("fsync failure")))
        else:
            stack.enter_context(patch.object(local, "_read", broken_read))
        failed = storage.export_candidate_capture_fields(result, object(), **kwargs)["candidate_reranker_capture"]
    assert failed["status"] == "NOT_AVAILABLE" and failed["artifact"] is None
    if phase != "final_read":
        assert list(out.rglob("*.json")) == []
        assert list(out.rglob("*.pending"))
    retried = storage.export_candidate_capture_fields(result, object(), **kwargs)["candidate_reranker_capture"]
    assert retried["status"] == "SAVED"
    data = (out / retried["artifact"]["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == retried["artifact"]["sha256"]
    assert capture.canonical_bytes(result._candidate_reranker_shadow) == original


@pytest.mark.parametrize("identical", [True, False])
def test_capture_commit_does_not_replace_concurrently_created_destination(tmp_path, identical):
    from tools import run_candidate_reranker_calibration as workflow
    result, _, _ = saved(tmp_path)
    out = tmp_path / "out"; out.mkdir()
    kwargs = dict(binding=binding(), output_dir=out, input_snapshot_sha256="a" * 64)
    rename = workflow._rename_noreplace
    destinations = []
    def collision(pending, target):
        destinations.append(target)
        with target.open("xb") as stream:
            stream.write(pending.read_bytes() if identical else b"preserve competing destination")
        rename(pending, target)
    with patch.object(workflow, "_rename_noreplace", collision):
        ref = storage.export_candidate_capture_fields(result, object(), **kwargs)["candidate_reranker_capture"]
    assert ref["status"] == ("SAVED" if identical else "NOT_AVAILABLE")
    assert len(destinations) == 1
    if not identical:
        assert ref["artifact"] is None
        assert destinations[0].read_bytes() == b"preserve competing destination"
    else:
        assert hashlib.sha256(destinations[0].read_bytes()).hexdigest() == ref["artifact"]["sha256"]


def test_concurrent_identical_capture_writers_share_only_complete_final_bytes(tmp_path):
    from tools import run_candidate_reranker_calibration as workflow
    result, _, _ = saved(tmp_path)
    out = tmp_path / "out"; out.mkdir()
    kwargs = dict(binding=binding(), output_dir=out, input_snapshot_sha256="a" * 64)
    rendezvous = Barrier(2)
    rename = workflow._rename_noreplace
    def synchronized_rename(pending, target):
        rendezvous.wait(timeout=10)
        rename(pending, target)
    with patch.object(workflow, "_rename_noreplace", synchronized_rename):
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(lambda _: storage.export_candidate_capture_fields(
                result, object(), **kwargs)["candidate_reranker_capture"], range(2)))
    assert all(value["status"] == "SAVED" for value in values)
    assert values[0] == values[1]
    assert len(list(out.rglob("*.json"))) == 1
