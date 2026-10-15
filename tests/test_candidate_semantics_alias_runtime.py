"""로컬 원문 bundle→실제 R2→별칭 관측→보존 archive 재생의 합성 통합 시험.

SOURCE_BACKED 분기는 schema를 시험하는 합성 자료다. 실제 권리/별칭/품질을
검증했다는 뜻이 아니며 모델·검색·네트워크를 호출하지 않는다.
"""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from llm_batch.domain.models import ContentBlock, PostInput
from llm_batch.grounding import candidate_retrieval_shadow as retrieval
from llm_batch.runtime import candidate_reranker as reranker
from llm_batch.runtime import candidate_semantics as runtime
from test_candidate_reranker_alias_evidence import (
    build_alias_fixture, _inventory, _set_inventory, _rebind_review, _refresh,
)


def _raw(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": path.name, "sha256": _sha(raw), "bytes": len(raw)}


def _write_bundle(root, fixture, *, name="bundle.json", mutate=None, duplicate_json=False):
    evidence_files = {}
    for digest, payload in fixture["evidence_payloads"].items():
        name_in_bundle = f"evidence/{digest}.bin"
        path = root / name_in_bundle
        if not path.exists():
            _write_new(path, payload)
        else:
            assert path.read_bytes() == payload
        evidence_files[digest] = {"path": name_in_bundle, "sha256": digest, "bytes": len(payload)}
    bundle = {"schema_version": runtime.BUNDLE_SCHEMA, "alias_evidence": deepcopy(fixture["alias_evidence"]),
        "evidence_files": evidence_files}
    if mutate is not None:
        mutate(bundle)
    raw = _raw(bundle)
    if duplicate_json:
        raw = b'{"schema_version":' + _raw(runtime.BUNDLE_SCHEMA) + b"," + raw[1:]
    path = root / name
    _write_new(path, raw)
    return path, _sha(raw), bundle


def _settings(path, pin):
    args = SimpleNamespace(candidate_semantics="SHADOW", candidate_retrieval="SHADOW",
        semantic_alias_bundle=str(path), semantic_alias_bundle_sha256=pin)
    return runtime.resolve_candidate_semantics_settings(args, {})


def build_semantics_alias_runtime_fixture(tmp_path, *, source_backed_shape=False, review_authority=None):
    fixture = build_alias_fixture(tmp_path)
    if source_backed_shape:
        fixture["manifest"]["data_kind"] = fixture["corpus"]["data_kind"] = "SOURCE_BACKED"
        inventory = _inventory(fixture)
        inventory["sources"][0]["rights"]["status"] = "REUSE_PERMITTED"
        _set_inventory(fixture, inventory)
        for entry in fixture["corpus"]["entries"]:
            for source in entry["sources"]:
                source["rights"]["status"] = "REUSE_PERMITTED"
        review_authority = review_authority or "HUMAN_REVIEW"
    if review_authority is not None:
        def authority(review, row, alias):
            review["authority"] = row["review"]["authority"] = alias["review"]["authority"] = review_authority
        _rebind_review(fixture, authority)
    _refresh(fixture)
    root = tmp_path / "local-semantic-bundle"
    path, pin, bundle = _write_bundle(root, fixture)
    settings = _settings(path, pin)
    observer = runtime.prepare_candidate_semantics(settings)
    corpus_ref = bundle["evidence_files"][fixture["alias_evidence"]["corpus_sha256"]]
    r2 = retrieval.load_corpus(root / corpus_ref["path"], expected_sha256=corpus_ref["sha256"])
    post = PostInput(post_id=12001, title="아생갤", gallery_id="synthetic-novel-community",
        created_at="2026-10-08T00:00:00Z", content_blocks=[ContentBlock(type="text", text="합성후보")])
    raw_input = _raw(post.model_dump()) + b"\n"
    _write_new(tmp_path / "source-input.jsonl", raw_input)
    return {"fixture": fixture, "bundle_root": root, "bundle_path": path, "bundle_pin": pin,
        "bundle": bundle, "settings": settings, "observer": observer, "retrieval": r2,
        "post": post, "input_sha256": _sha(raw_input), "output_dir": tmp_path / "new-output"}


def _observe(state, post=None):
    post = post or state["post"]
    receipt = state["retrieval"].observe(reranker._source_view(post))
    return runtime.observe_candidate_semantics(state["observer"], post, receipt, state["retrieval"])


def _export(state, package):
    binding = {"run_id": "synthetic-alias-run", "input_index": 1, "post_id": package["post_id"],
        "attempt_id": "synthetic-alias-attempt-1", "publication_scope_id": "synthetic-scope"}
    return runtime.export_candidate_semantics_fields(SimpleNamespace(_candidate_reranker_semantics=package),
        state["observer"], binding=binding, output_dir=state["output_dir"], input_snapshot_sha256=state["input_sha256"],
        current_post=state["post"], retrieval_observer=state["retrieval"])


def _all_hashes(folder):
    return {p.relative_to(folder).as_posix(): _sha(p.read_bytes()) for p in folder.rglob("*") if p.is_file()}


def _capture(state, fields):
    capture = fields["candidate_reranker_semantics_capture"]
    assert capture["status"] == "SAVED", capture
    artifact = runtime.read_candidate_semantics_capture(state["output_dir"], capture["artifact"])
    assert artifact["capture_sha256"] == capture["capture_sha256"]
    assert artifact["input_snapshot_sha256"] == state["input_sha256"]
    return artifact


@pytest.mark.parametrize("source_backed_shape", [False, True])
def test_real_local_bundle_r2_producer_export_and_independent_capture_replay(tmp_path, source_backed_shape):
    state = build_semantics_alias_runtime_fixture(tmp_path, source_backed_shape=source_backed_shape)
    before = _all_hashes(state["bundle_root"])
    post_before = state["post"].model_dump()
    package = _observe(state)
    assert package["status"] == "OBSERVED", package
    alias = package["observation"]["alias_validation"]
    assert alias["status"] == "BOUND"
    assert alias["data_kind"] == ("SOURCE_BACKED" if source_backed_shape else "SYNTHETIC_FIXTURE")
    assert alias["bindings"][0]["evidence_grade"] == ("HUMAN_REVIEW_BOUND" if source_backed_shape else "SYNTHETIC_FIXTURE_BOUND")
    assert alias["actual_semantic_evidence_verified"] is alias["reviewer_identity_verified"] is False
    observed = package["observation"]["observations"]
    assert [(r["role"], r["mention_kind"], r["mention"]["text"]) for r in observed] == [("MENTIONED", "VERIFIED_ALIAS", "아생갤")]
    assert observed[0]["candidate_id"] == "synthetic-corpus-1"
    assert package["observation"]["score_consumption_status"] == "NOT_CONSUMED_MODEL_POLICY_UNBOUND"
    fields = _export(state, package)
    artifact = _capture(state, fields)
    assert artifact["package"] == package
    row = fields["candidate_reranker_semantics"]
    assert row["consumption"]["status"] == "OBSERVED_NOT_CONSUMED"
    assert row["consumption"]["scorer_input_applied"] is row["consumption"]["calibration_input_applied"] is False
    assert row["publication_authority"] is row["public_apply"] is row["central_db_write"] is False
    assert state["post"].model_dump() == post_before
    assert _all_hashes(state["bundle_root"]) == before


def test_archive_contains_original_bytes_and_replays_without_original_bundle_reads(tmp_path, monkeypatch):
    from tools import run_candidate_reranker_training as local
    state = build_semantics_alias_runtime_fixture(tmp_path)
    fields = _export(state, _observe(state))
    artifact = _capture(state, fields)
    archive_ref = artifact["evidence_archive"]
    archive_raw = (state["output_dir"] / archive_ref["path"]).read_bytes()
    assert _sha(archive_raw) == archive_ref["sha256"] and len(archive_raw) == archive_ref["bytes"]
    archive = json.loads(archive_raw)
    assert base64.b64decode(archive["bundle_raw_base64"], validate=True) == state["bundle_path"].read_bytes()
    assert {sha: base64.b64decode(data, validate=True) for sha, data in archive["payloads_base64"].items()} == state["fixture"]["evidence_payloads"]
    original_read = local._read
    def output_only(path, limit):
        assert Path(path).absolute().is_relative_to(state["output_dir"].absolute())
        return original_read(path, limit)
    monkeypatch.setattr(local, "_read", output_only)
    assert runtime.read_candidate_semantics_capture(state["output_dir"], fields["candidate_reranker_semantics_capture"]["artifact"]) == artifact


@pytest.mark.parametrize("kind", ["source", "review"])
def test_local_source_and_review_raw_byte_change_is_rejected_before_observation(tmp_path, kind):
    state = build_semantics_alias_runtime_fixture(tmp_path)
    if kind == "source":
        digest = _inventory(state["fixture"])["sources"][0]["payload_byte_sha256"]
    else:
        review_path = next(name for name in state["fixture"]["snapshot_files"] if name.endswith(".json") and b'"reviewer"' in state["fixture"]["snapshot_files"][name])
        digest = _sha(state["fixture"]["snapshot_files"][review_path])
    path = state["bundle_root"] / state["bundle"]["evidence_files"][digest]["path"]
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b"a", b"b", 1) if b"a" in raw else raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(ValueError):
        runtime.prepare_candidate_semantics(state["settings"])
    assert not state["output_dir"].exists()


def test_resealed_foreign_review_is_unresolved_not_a_verified_alias(tmp_path):
    state = build_semantics_alias_runtime_fixture(tmp_path)
    fixture = state["fixture"]
    _rebind_review(fixture, lambda review, row, alias: review.update(source_id="another-source"))
    path, pin, _ = _write_bundle(tmp_path / "review-counterexample", fixture)
    state["observer"] = runtime.prepare_candidate_semantics(_settings(path, pin))
    package = _observe(state)
    assert package["status"] == "NO_MATCH", package
    assert package["observation"]["alias_validation"]["bindings"] == []
    assert "REVIEW_SOURCE_CLASSIFICATION_BINDING_MISMATCH" in package["observation"]["alias_validation"]["reason_codes"]
    assert _capture(state, _export(state, package))["package"] == package


@pytest.mark.parametrize("authority", ["MODEL_REFERENCE", "UNKNOWN"])
def test_model_reference_and_unknown_authority_are_not_consumed(tmp_path, authority):
    state = build_semantics_alias_runtime_fixture(tmp_path, review_authority=authority)
    package = _observe(state)
    assert package["status"] == "NO_MATCH", package
    assert package["observation"]["counts"]["alias_observations"] == 0
    alias = package["observation"]["alias_validation"]
    assert alias["bindings"] == [] and "REVIEW_AUTHORITY_INSUFFICIENT" in alias["reason_codes"]
    assert all(not c["aliases"] for c in package["enriched_view"]["candidates"])
    assert _capture(state, _export(state, package))["package"] == package


@pytest.mark.parametrize("missing", ["gallery", "time", "timezone"])
def test_unrecorded_community_or_time_is_never_inferred_from_default(tmp_path, missing):
    state = build_semantics_alias_runtime_fixture(tmp_path)
    fields = state["post"].model_dump()
    if missing == "gallery":
        fields.pop("gallery_id")
    elif missing == "time":
        fields.pop("created_at")
    else:
        fields["created_at"] = "2026-10-08T00:00:00"
    post = PostInput(**fields)
    package = _observe(state, post)
    assert package["status"] == "NO_MATCH", package
    context = package["alias_evidence"]["community_source_view"]
    key = "community" if missing == "gallery" else "as_of"
    assert context[key]["status"] == "UNKNOWN" and context[key]["value"] is None
    assert package["observation"]["alias_validation"]["reason_codes"] == ["CONTEXT_UNKNOWN"]
    assert package["observation"]["counts"]["alias_observations"] == 0


@pytest.mark.parametrize("invalid_path", ["../outside.bin", "/absolute.bin", "C:/outside.bin", "https://example.invalid/source", "evidence\\source.bin"])
def test_bundle_path_escape_or_remote_path_is_rejected(tmp_path, invalid_path):
    fixture = build_alias_fixture(tmp_path)
    def change(bundle):
        next(iter(bundle["evidence_files"].values()))["path"] = invalid_path
    path, pin, _ = _write_bundle(tmp_path / "invalid-path", fixture, mutate=change)
    with pytest.raises(ValueError, match="SEMANTICS_FILE_PATH_INVALID"):
        runtime.prepare_candidate_semantics(_settings(path, pin))


@pytest.mark.parametrize("kind", ["pin", "duplicate_json", "per_post_context"])
def test_bundle_pin_duplicate_json_and_baked_post_context_are_rejected(tmp_path, kind):
    fixture = build_alias_fixture(tmp_path)
    def change(bundle):
        if kind == "per_post_context":
            bundle["alias_evidence"]["community_source_view"] = fixture["community_source_view"]
    path, pin, _ = _write_bundle(tmp_path / "invalid-bundle", fixture, mutate=change, duplicate_json=kind == "duplicate_json")
    with pytest.raises(ValueError):
        runtime.prepare_candidate_semantics(_settings(path, "0" * 64 if kind == "pin" else pin))


def test_resealed_archive_with_corrupt_inner_bytes_fails_independent_replay(tmp_path):
    state = build_semantics_alias_runtime_fixture(tmp_path)
    artifact = _capture(state, _export(state, _observe(state)))
    original_path = state["output_dir"] / artifact["evidence_archive"]["path"]
    archive = json.loads(original_path.read_bytes())
    digest = next(iter(archive["payloads_base64"]))
    archive["payloads_base64"][digest] = base64.b64encode(b"forged bytes with resealed outer files").decode("ascii")
    bad_archive = state["output_dir"] / "counterexample-archive.json"
    ref = _write_new(bad_archive, _raw(archive))
    changed = deepcopy(artifact)
    changed["evidence_archive"] = ref
    changed["capture_sha256"] = _sha(_raw({k: v for k, v in changed.items() if k != "capture_sha256"}))
    bad_capture = state["output_dir"] / "counterexample-capture.json"
    bad_ref = _write_new(bad_capture, _raw(changed))
    with pytest.raises(ValueError, match="SEMANTICS_ARCHIVE_PAYLOAD_SHA"):
        runtime.read_candidate_semantics_capture(state["output_dir"], bad_ref)
    assert _sha(original_path.read_bytes()) == artifact["evidence_archive"]["sha256"]


def test_capture_reuse_is_identical_and_existing_conflicting_file_is_not_overwritten(tmp_path):
    state = build_semantics_alias_runtime_fixture(tmp_path)
    package = _observe(state)
    first = _export(state, package)
    second = _export(state, package)
    assert second == first
    capture = first["candidate_reranker_semantics_capture"]
    path = state["output_dir"] / capture["artifact"]["path"]
    path.write_bytes(b'{"preexisting":"must remain unchanged"}\n')
    preexisting = path.read_bytes()
    result = _export(state, package)
    assert result["candidate_reranker_semantics"]["status"] == "OBSERVED"
    failed = result["candidate_reranker_semantics_capture"]
    assert failed["status"] == "NOT_AVAILABLE" and failed["artifact"] is None
    assert "SEMANTICS_CAPTURE_EXISTING_MISMATCH" in failed["reason_codes"]
    assert path.read_bytes() == preexisting
