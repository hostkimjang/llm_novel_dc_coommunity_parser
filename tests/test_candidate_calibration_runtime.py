"""일반 runtime 좌표와 고정 FROZEN 자료의 연결·저장 실패 격리 시험."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.llm_batch.runtime import candidate_calibration as runtime
from src.llm_batch.grounding.candidate_reranker_capture import build_capture
from tests.candidate_calibration_runtime_fixtures import build_runtime_calibration_fixture, raw, sha


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    return build_runtime_calibration_fixture(tmp_path_factory.mktemp("runtime-calibration"))


@pytest.fixture(scope="module")
def observer(bundle):
    result = runtime.prepare_candidate_calibration(bundle["settings"], bundle["scorer"])
    assert result.summary()["status"] == "AVAILABLE", result.summary()
    return result


def observe(observer, row):
    return runtime.observe_candidate_calibration(observer, row["post"], row["capture"], row["reranker_receipt"])


def binding(row):
    return {"run_id": "live-run", "input_index": 7, "post_id": row["post"].post_id,
            "attempt_id": "live-attempt", "publication_scope_id": "live-scope"}


def capture_storage(row, bound):
    return {"status": "SAVED", "observation_sha256": row["capture"]["capture_sha256"],
            "binding": {**bound, "scope": "ATTEMPT_LOCAL_OBSERVATION"}}


def private_result(row, observation):
    return SimpleNamespace(_candidate_calibration_shadow=deepcopy(observation),
        _candidate_reranker_capture=deepcopy(row["capture"]),
        _candidate_reranker_shadow=deepcopy(row["reranker_receipt"]))


def reseal_raw(receipt):
    receipt["receipt_sha256"] = sha(raw({k: v for k, v in receipt.items() if k not in {"receipt_sha256", "binding", "latency_ms"}}))


def variant(tmp_path, bundle, mutate):
    folder = tmp_path / "variant"; folder.mkdir()
    for source in bundle["bundle_path"].parent.iterdir():
        if source.is_file():
            with (folder / source.name).open("xb") as stream:
                stream.write(source.read_bytes())
    value = deepcopy(bundle["bundle"])
    mutate(value, folder)
    path = folder / "variant.json"
    with path.open("xb") as stream:
        stream.write(raw(value))
    settings = {**bundle["settings"], "bundle_path": str(path), "bundle_sha256": sha(path.read_bytes())}
    return runtime.prepare_candidate_calibration(settings, bundle["scorer"])


def test_off_has_no_io_or_scorer_or_output(monkeypatch):
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("OFF opened input"))
    scorer = SimpleNamespace(summary=lambda: pytest.fail("OFF observed scorer"))
    settings = runtime.resolve_candidate_calibration_settings(SimpleNamespace(candidate_calibration="OFF"),
        {"EXPERT_CALIBRATION_BUNDLE": "https://invalid", "EXPERT_CALIBRATION_BUNDLE_SHA256": "bad"})
    assert runtime.prepare_candidate_calibration(settings, scorer) is None
    assert runtime.candidate_calibration_policy_fields(None, settings) == {}
    assert runtime.observe_candidate_calibration(None, None, None, None) is None
    assert runtime.export_candidate_calibration_fields(None, None, binding={}) == {}


def test_setting_precedence_and_strict_configuration():
    env = {"EXPERT_CANDIDATE_CALIBRATION": "SHADOW", "EXPERT_CALIBRATION_BUNDLE": "declared.json",
        "EXPERT_CALIBRATION_BUNDLE_SHA256": "a" * 64, "EXPERT_CANDIDATE_RERANKER": "SHADOW"}
    settings = runtime.resolve_candidate_calibration_settings(SimpleNamespace(candidate_retrieval="SHADOW"), env)
    assert settings["mode"] == "SHADOW" and set(settings["sources"].values()) == {"ENVIRONMENT"}
    cli = runtime.resolve_candidate_calibration_settings(SimpleNamespace(candidate_calibration="OFF"), env)
    assert cli["mode"] == "OFF" and cli["sources"]["mode"] == "CLI"
    for args in (SimpleNamespace(candidate_calibration=True), SimpleNamespace(candidate_calibration="shadow"),
                 SimpleNamespace(candidate_calibration="SHADOW"), SimpleNamespace(candidate_calibration="SHADOW", calibration_bundle="x", calibration_bundle_sha256="bad")):
        with pytest.raises(ValueError):
            runtime.resolve_candidate_calibration_settings(args, {})


@pytest.mark.parametrize("retrieval_mode,reranker_cli,reranker_env", [("OFF", "SHADOW", "SHADOW"),
    ("SHADOW", "OFF", "SHADOW"), ("SHADOW", None, "OFF"), ("SHADOW", None, "invalid")])
def test_shadow_dependencies_follow_actual_cli_and_reranker_environment_precedence(retrieval_mode, reranker_cli, reranker_env):
    args = SimpleNamespace(candidate_calibration="SHADOW", candidate_retrieval=retrieval_mode,
        candidate_reranker=reranker_cli, calibration_bundle="pinned.json", calibration_bundle_sha256="a" * 64)
    with pytest.raises(ValueError, match="RETRIEVAL_AND_RERANKER_SHADOW_REQUIRED"):
        runtime.resolve_candidate_calibration_settings(args, {"EXPERT_CANDIDATE_RERANKER": reranker_env})


def test_fixed_bundle_load_is_read_only_and_summary_is_detached(bundle):
    paths = list(bundle["bundle_path"].parent.iterdir())
    before = {p.name: p.read_bytes() for p in paths}
    obj = runtime.prepare_candidate_calibration(bundle["settings"], bundle["scorer"])
    summary = obj.summary()
    assert summary["scope"] == "FROZEN_REOBSERVATION_ONLY" and summary["frozen_rows"] == 2
    assert summary["data_kind"] == "SYNTHETIC_FIXTURE" and summary["actual_quality_evaluated"] is False
    assert summary["policy_sha256"] == sha(raw({k: v for k, v in summary.items() if k != "policy_sha256"}))
    summary["status"] = "mutated"
    assert obj.summary()["status"] == "AVAILABLE"
    with pytest.raises(FrozenInstanceError):
        obj._rows = ()
    policy = runtime.candidate_calibration_policy_fields(obj, bundle["settings"])["candidate_calibration_policy"]
    assert policy["policy_sha256"] == sha(raw({k: v for k, v in policy.items() if k != "policy_sha256"}))
    assert before == {p.name: p.read_bytes() for p in paths}


def test_actual_r2_mentioned_runtime_int_to_dataset_str_is_exactly_bound_without_rescore(bundle, observer, monkeypatch):
    row = bundle["frozen_runtime_rows"][0]
    before = deepcopy(row)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("observe opened input"))
    monkeypatch.setattr(type(bundle["scorer"]), "score", lambda *a, **k: pytest.fail("runtime observation rescored"))
    result = observe(observer, row)
    assert row == before and result["status"] == "CALIBRATED_SHADOW_BOUND", result
    assert type(result["post_id"]) is int and type(result["dataset_post_id"]) is str
    assert str(result["post_id"]) != result["dataset_post_id"]
    assert result["runtime_capture_sha256"] == row["capture"]["capture_sha256"]
    assert result["runtime_raw_receipt_sha256"] == row["reranker_receipt"]["receipt_sha256"]
    assert result["runtime_raw_receipt_sha256"] != result["dataset_raw_receipt_sha256"]
    shadow = result["calibration_shadow"]
    assert shadow["post_id"] == row["dataset_post_id"] and shadow["action_applied"] is False
    assert all(role["role"] == "MENTIONED" for c in row["frozen_view"]["candidates"] for role in c["role_observations"])
    assert all(result[k] is False for k in ("publication_authority", "public_apply", "central_db_write", "action_applied"))
    assert result["receipt_sha256"] == sha(raw({k: v for k, v in result.items() if k != "receipt_sha256"}))


@pytest.mark.parametrize("post_id", [0, False, "12006", "dataset-post-6", 99999])
def test_unassigned_and_wrong_id_types_have_null_probabilities(bundle, observer, post_id):
    row = bundle["frozen_runtime_rows"][0]
    post = SimpleNamespace(post_id=post_id, title=row["post"].title, content_blocks=[], comments=[])
    result = runtime.observe_candidate_calibration(observer, post, row["capture"], row["reranker_receipt"])
    assert result["status"] == "NOT_AVAILABLE" and result["calibration_shadow"] is None
    assert "FROZEN_ROW_NOT_ASSIGNED" in result["reason_codes"]


@pytest.mark.parametrize("fault", ["capture_missing", "post_source", "capture_sha", "raw_sha", "model", "foreign_capture", "oversized"])
def test_missing_changed_or_foreign_observations_do_not_inherit_frozen_probability(bundle, observer, fault):
    row = deepcopy(bundle["frozen_runtime_rows"][0])
    if fault == "capture_missing": row["capture"] = None
    elif fault == "post_source": row["post"].title += " changed"
    elif fault == "capture_sha": row["capture"]["capture_sha256"] = "0" * 64
    elif fault == "raw_sha": row["reranker_receipt"]["receipt_sha256"] = "0" * 64
    elif fault == "model": row["capture"]["scorer_summary"]["model_sha256"] = "0" * 64
    elif fault == "foreign_capture": row["capture"] = bundle["frozen_runtime_rows"][1]["capture"]
    else: row["capture"]["extra"] = "x" * (300 * 1024)
    result = observe(observer, row)
    assert result["status"] == "NOT_AVAILABLE" and result["calibration_shadow"] is None


def test_resealed_current_scores_still_must_equal_the_fixed_dataset_model(bundle, observer):
    row = deepcopy(bundle["frozen_runtime_rows"][0])
    receipt = row["reranker_receipt"]
    receipt["nil_score"] = receipt["event_logits"][-1]["score"] = 999.0
    reseal_raw(receipt)
    row["capture"] = build_capture(row["frozen_view"], receipt, row["retrieval_receipt"], bundle["scorer_summary"])
    result = observe(observer, row)
    assert result["reason_codes"] == ["RUNTIME_DATASET_SCORE_MISMATCH"] and result["calibration_shadow"] is None


def test_source_role_change_is_not_one_of_the_two_allowed_post_id_changes(bundle, observer):
    row = deepcopy(bundle["frozen_runtime_rows"][0])
    row["frozen_view"]["candidates"][0]["role_observations"][0]["role"] = "PRIMARY"
    row["reranker_receipt"] = bundle["scorer"].score(row["frozen_view"])
    row["capture"] = build_capture(row["frozen_view"], row["reranker_receipt"], row["retrieval_receipt"], bundle["scorer_summary"])
    result = observe(observer, row)
    assert result["reason_codes"] == ["FROZEN_VIEW_MISMATCH"] and result["calibration_shadow"] is None


@pytest.mark.parametrize("fault", ["missing_row", "reverse_rows", "duplicate_runtime", "bool_runtime", "wrong_dataset", "foreign_split",
    "missing_source", "source_sha", "evidence_key", "outside_path", "absolute_path", "summary_pin", "manifest_pin", "artifact_sha", "raw_score", "legacy_artifact"])
def test_load_rejects_incomplete_mapping_source_and_model_contracts(tmp_path, bundle, fault):
    def mutate(value, folder):
        if fault == "missing_row": value["frozen_rows"].pop()
        elif fault == "reverse_rows": value["frozen_rows"].reverse()
        elif fault == "duplicate_runtime": value["frozen_rows"][1]["runtime_post_id"] = value["frozen_rows"][0]["runtime_post_id"]
        elif fault == "bool_runtime": value["frozen_rows"][0]["runtime_post_id"] = True
        elif fault == "wrong_dataset": value["frozen_rows"][0]["dataset_post_id"] = "12006"
        elif fault == "foreign_split": value["frozen_rows"][0]["example"]["example_id"] = value["training_manifest"]["rows"][0]["assignment"]["example_id"]
        elif fault == "missing_source": value["source_files"].popitem()
        elif fault == "source_sha": next(iter(value["source_files"].values()))["sha256"] = "0" * 64
        elif fault == "evidence_key":
            _, ref = value["evidence_files"].popitem(); value["evidence_files"]["0" * 64] = ref
        elif fault == "outside_path": value["artifact"]["path"] = "../artifact.json"
        elif fault == "absolute_path": value["artifact"]["path"] = str(folder / "artifact.json")
        elif fault == "summary_pin": value["expected_scorer_summary_sha256"] = "0" * 64
        elif fault == "manifest_pin": value["expected_training_manifest_sha256"] = "0" * 64
        elif fault == "artifact_sha": value["artifact"]["sha256"] = "0" * 64
        elif fault == "raw_score":
            r = value["frozen_rows"][0]["raw_receipt"]; r["nil_score"] = r["event_logits"][-1]["score"] = 999.0; reseal_raw(r)
        else:
            artifact = json.loads((folder / "artifact.json").read_bytes())
            artifact["schema_version"] = "candidate_set_calibration_artifact_v1"
            target = folder / "wrong_artifact.json"
            with target.open("xb") as stream: stream.write(raw(artifact))
            value["artifact"] = {"path": target.name, "sha256": sha(target.read_bytes()), "bytes": target.stat().st_size}
    obj = variant(tmp_path, bundle, mutate)
    assert obj.summary()["status"] == "UNAVAILABLE", obj.summary()
    result = observe(obj, bundle["frozen_runtime_rows"][0])
    assert result["status"] == "UNAVAILABLE" and result["calibration_shadow"] is None


def test_load_failures_and_bad_scorer_summary_are_isolated(bundle):
    for scorer in (None, SimpleNamespace(summary=lambda: []), SimpleNamespace(summary=lambda: {"status": "UNAVAILABLE_MODEL"})):
        result = runtime.prepare_candidate_calibration(bundle["settings"], scorer)
        assert result.summary()["status"] == "UNAVAILABLE"
    settings = {**bundle["settings"], "bundle_sha256": "0" * 64}
    assert runtime.prepare_candidate_calibration(settings, bundle["scorer"]).summary()["reason_codes"] == ["BUNDLE_SHA_MISMATCH"]


def test_saved_capture_and_standard_binding_are_required_to_store_bound_probability(bundle, observer, monkeypatch):
    row = bundle["frozen_runtime_rows"][0]; bound = binding(row)
    result = private_result(row, observe(observer, row))
    before = deepcopy(result.__dict__)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("export opened input"))
    monkeypatch.setattr(type(bundle["scorer"]), "score", lambda *a, **k: pytest.fail("export rescored"))
    stored = runtime.export_candidate_calibration_fields(result, observer, binding=bound, capture_receipt=capture_storage(row, bound))["candidate_calibration_shadow"]
    assert stored["status"] == "CALIBRATED_SHADOW_BOUND" and stored["calibration_shadow"] is not None
    assert stored["binding"] == {**bound, "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    assert stored["receipt_sha256"] == result._candidate_calibration_shadow["receipt_sha256"]
    assert "binding" not in result._candidate_calibration_shadow
    assert result.__dict__ == before


@pytest.mark.parametrize("fault", ["missing", "not_saved", "wrong_capture", "wrong_attempt", "missing_binding", "wrong_post", "forged_probability", "bad_selfsha", "huge_binding"])
def test_export_failures_are_visible_null_and_do_not_reuse_probabilities(bundle, observer, fault):
    row = bundle["frozen_runtime_rows"][0]; bound = binding(row)
    output = observe(observer, row); saved = capture_storage(row, bound)
    if fault == "missing": saved = None
    elif fault == "not_saved": saved["status"] = "SAVE_FAILED"
    elif fault == "wrong_capture": saved["observation_sha256"] = "0" * 64
    elif fault == "wrong_attempt": saved["binding"]["attempt_id"] = "other-attempt"
    elif fault == "missing_binding": del saved["binding"]
    elif fault == "wrong_post": bound["post_id"] = 99999
    elif fault == "forged_probability":
        output["calibration_shadow"]["action_applied"] = True
        output["receipt_sha256"] = sha(raw({k: v for k, v in output.items() if k != "receipt_sha256"}))
    elif fault == "bad_selfsha": output["receipt_sha256"] = "0" * 64
    else: bound["run_id"] = "x" * (80 * 1024)
    stored = runtime.export_candidate_calibration_fields(private_result(row, output), observer,
        binding=bound, capture_receipt=saved)["candidate_calibration_shadow"]
    assert stored["status"] == "NOT_AVAILABLE" and stored["calibration_shadow"] is None
    assert len(raw(stored)) <= runtime.MAX_STORED_BYTES
    assert stored["receipt_sha256"] == sha(raw({k: v for k, v in stored.items() if k not in {"receipt_sha256", "binding"}}))


@pytest.mark.parametrize("fault", ["raw_digest", "capture_digest", "missing_capture", "missing_raw",
    "foreign_capture", "foreign_raw", "changed_private_raw"])
def test_export_rechecks_actual_private_capture_raw_and_resealed_envelope(bundle, observer, fault):
    row = bundle["frozen_runtime_rows"][0]; bound = binding(row)
    result = private_result(row, observe(observer, row)); saved = capture_storage(row, bound)
    envelope = result._candidate_calibration_shadow
    if fault == "raw_digest": envelope["runtime_raw_receipt_sha256"] = "0" * 64
    elif fault == "capture_digest":
        envelope["runtime_capture_sha256"] = saved["observation_sha256"] = "0" * 64
    elif fault == "missing_capture": del result._candidate_reranker_capture
    elif fault == "missing_raw": del result._candidate_reranker_shadow
    elif fault == "foreign_capture": result._candidate_reranker_capture = deepcopy(bundle["frozen_runtime_rows"][1]["capture"])
    elif fault == "foreign_raw": result._candidate_reranker_shadow = deepcopy(bundle["frozen_runtime_rows"][1]["reranker_receipt"])
    else:
        result._candidate_reranker_shadow["nil_score"] = 999.0
        reseal_raw(result._candidate_reranker_shadow)
    envelope["receipt_sha256"] = sha(raw({k: v for k, v in envelope.items() if k != "receipt_sha256"}))
    before = deepcopy(result.__dict__)
    stored = runtime.export_candidate_calibration_fields(result, observer, binding=bound, capture_receipt=saved)["candidate_calibration_shadow"]
    assert stored["status"] == "NOT_AVAILABLE" and stored["calibration_shadow"] is None
    if fault in {"raw_digest", "capture_digest"}:
        assert stored["reason_codes"] == ["STORED_OBSERVATION_DIGEST_MISMATCH"]
    assert result.__dict__ == before


@pytest.mark.parametrize("fault", ["scores", "view"])
def test_export_rejects_other_valid_capture_even_when_all_transport_digests_are_resealed(bundle, observer, fault, monkeypatch):
    row = deepcopy(bundle["frozen_runtime_rows"][0]); bound = binding(row)
    envelope = observe(observer, row)
    if fault == "scores":
        row["reranker_receipt"]["nil_score"] = row["reranker_receipt"]["event_logits"][-1]["score"] = 999.0
        reseal_raw(row["reranker_receipt"])
    else:
        row["frozen_view"]["candidates"][0]["role_observations"][0]["role"] = "PRIMARY"
        row["reranker_receipt"] = bundle["scorer"].score(row["frozen_view"])
    row["capture"] = build_capture(row["frozen_view"], row["reranker_receipt"], row["retrieval_receipt"], bundle["scorer_summary"])
    envelope["runtime_capture_sha256"] = row["capture"]["capture_sha256"]
    envelope["runtime_raw_receipt_sha256"] = row["reranker_receipt"]["receipt_sha256"]
    envelope["receipt_sha256"] = sha(raw({k: v for k, v in envelope.items() if k != "receipt_sha256"}))
    result = private_result(row, envelope)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("export opened input"))
    monkeypatch.setattr(type(bundle["scorer"]), "score", lambda *a, **k: pytest.fail("export rescored"))
    stored = runtime.export_candidate_calibration_fields(result, observer, binding=bound,
        capture_receipt=capture_storage(row, bound))["candidate_calibration_shadow"]
    assert stored["status"] == "NOT_AVAILABLE" and stored["calibration_shadow"] is None
    assert stored["reason_codes"] == ["RUNTIME_DATASET_SCORE_MISMATCH" if fault == "scores" else "FROZEN_VIEW_MISMATCH"]


def test_early_return_records_not_executed_without_probability(bundle, observer):
    row = bundle["frozen_runtime_rows"][0]
    result = runtime.export_candidate_calibration_fields(None, observer, binding=binding(row))["candidate_calibration_shadow"]
    assert result["status"] == "NOT_EXECUTED" and result["calibration_shadow"] is None
    assert result["reason_codes"] == ["PIPELINE_NOT_EXECUTED"]


@pytest.mark.parametrize("result", [SimpleNamespace(), SimpleNamespace(_candidate_calibration_shadow=None)])
def test_executed_result_without_calibration_observation_is_visible_missing(bundle, observer, result):
    row = bundle["frozen_runtime_rows"][0]
    stored = runtime.export_candidate_calibration_fields(result, observer, binding=binding(row))["candidate_calibration_shadow"]
    assert stored["status"] == "NOT_AVAILABLE" and stored["calibration_shadow"] is None
    assert stored["reason_codes"] == ["CALIBRATION_OBSERVATION_MISSING"]
    assert stored["binding"] == {**binding(row), "scope": "ATTEMPT_LOCAL_OBSERVATION"}
    assert stored["receipt_sha256"] == sha(raw({k: v for k, v in stored.items() if k not in {"receipt_sha256", "binding"}}))


@pytest.mark.parametrize("bad", [None, [], {"run_id": object()}, {"input_index": float("nan")}, {"post_id": True}])
def test_invalid_storage_binding_never_raises_again_in_fallback(observer, bad):
    result = runtime.export_candidate_calibration_fields(None, observer, binding=bad)["candidate_calibration_shadow"]
    assert result["status"] == "NOT_AVAILABLE" and result["calibration_shadow"] is None
    raw(result)


def test_old_frozen_calibration_does_not_accept_new_semantic_model(bundle, tmp_path):
    from test_candidate_reranker_shadow import _semantic_scorer
    scorer, _, _ = _semantic_scorer(tmp_path, head=True)
    loaded = runtime.prepare_candidate_calibration(bundle["settings"], scorer)
    assert loaded.summary()["status"] == "UNAVAILABLE"
    assert "ARTIFACT_MODEL_BINDING_MISMATCH" in loaded.summary()["reason_codes"]


def _loaded_semantic_calibration_fixture(tmp_path, *, with_alias=False, same_post_ids=False):
    from tests.candidate_reranker_semantic_calibration_fixtures import build_semantic_calibration_fixture
    from tests.candidate_calibration_runtime_fixtures import _write, _stored_row
    from src.llm_batch.grounding.candidate_reranker_calibration import fit_temperature
    fixture = build_semantic_calibration_fixture(tmp_path, with_alias=with_alias)
    artifact = fit_temperature(fixture["calibration_events"],
        split_manifest=fixture["calibration_manifest"], policy=fixture["policy"])["artifact"]
    folder = tmp_path / "semantic-runtime-bundle"
    folder.mkdir()
    artifact_ref = _write(folder / "artifact.json", raw(artifact.to_dict()))
    maps = {category: {key: _write(folder / f"{category}_{i}.bin", value)
        for i, (key, value) in enumerate(values.items())}
        for category, values in (("source_files", fixture["source_payloads"]),
                                  ("evidence_files", fixture["evidence_payloads"]))}
    rows = [_stored_row(args, args["example"]["frozen_view"]["post_id"] if same_post_ids else 25000 + i,
                       args["example"]["frozen_view"]["post_id"])
        for i, args in enumerate(fixture["frozen_args"])]
    value = {"schema_version": runtime.BUNDLE_SCHEMA, "artifact": artifact_ref,
        "training_manifest": fixture["training_manifest"],
        "expected_training_manifest_sha256": fixture["training_manifest"]["manifest_sha256"],
        "calibration_manifest": fixture["calibration_manifest"].to_dict(),
        "expected_calibration_manifest_sha256": fixture["calibration_manifest"].manifest_sha256,
        "policy": fixture["policy"].to_dict(), "expected_scorer_summary_sha256": sha(raw(fixture["scorer_summary"])),
        **maps, "frozen_rows": rows}
    path = folder / "bundle.json"
    ref = _write(path, raw(value))
    loaded = runtime.prepare_candidate_calibration({"mode": "SHADOW", "bundle_path": str(path),
        "bundle_sha256": ref["sha256"]}, fixture["scorer"])
    assert loaded.summary()["status"] == "AVAILABLE", loaded.summary()
    return fixture, artifact, rows, loaded


def test_semantic_model_requires_and_loads_its_actual_fitted_calibration_bundle(tmp_path):
    fixture, artifact, rows, loaded = _loaded_semantic_calibration_fixture(tmp_path)
    assert loaded.summary()["calibration_artifact_sha256"] == artifact.artifact_sha256
    for row in rows:
        record = loaded._record(row["runtime_post_id"])
        expected = fixture["semantic_inputs"][row["example"]["example_id"]]
        assert record["semantic_binding"] == runtime._semantic_binding(expected)
        assert record["dataset_raw_receipt_sha256"] == row["raw_receipt"]["receipt_sha256"]


def test_export_rejects_resealed_bound_capture_with_valid_but_different_alias_as_of(tmp_path, monkeypatch):
    from src.llm_batch.grounding.candidate_reranker_semantic_input import build_semantic_input
    from src.llm_batch.grounding.candidate_reranker_capture import validate_capture
    fixture, _, rows, observer = _loaded_semantic_calibration_fixture(
        tmp_path, with_alias=True, same_post_ids=True)
    item = next(r for r in rows if fixture["semantic_inputs"][r["example"]["example_id"]]["alias_evidence"] is not None)
    original = fixture["semantic_inputs"][item["example"]["example_id"]]
    scorer, evidence = fixture["scorer"], fixture["evidence_payloads"]
    post_id = item["runtime_post_id"]
    bound = binding({"post": SimpleNamespace(post_id=post_id)})
    record = observer._record(post_id)

    def prepared(semantic_input):
        score = scorer.score(semantic_input["enriched_view"], semantic_input=semantic_input, evidence_payloads=evidence)
        assert score["status"] == "SCORED_LEARNED", score
        captured = build_capture(semantic_input["enriched_view"], score, semantic_input["retrieval_receipt"],
            scorer.summary(), semantic_input=semantic_input, evidence_payloads=evidence)
        assert validate_capture(captured) == captured
        # transport는 완전히 재봉인한다. 검산 대역이나 낡은 self SHA에 기대지 않는다.
        envelope = runtime._envelope(observer.summary(), post_id, "CALIBRATED_SHADOW_BOUND",
            ["EXPLICIT_FROZEN_REOBSERVATION"], record,
            capture_sha=captured["capture_sha256"], raw_sha=score["receipt_sha256"])
        row = {"capture": captured, "reranker_receipt": score}
        return row, private_result(row, envelope)

    original_row, original_result = prepared(original)
    alias = deepcopy(original["alias_evidence"])
    alias["community_source_view"]["as_of"]["value"] = "2026-10-09T00:00:00Z"
    changed = build_semantic_input(original["original_view"], retrieval_receipt=original["retrieval_receipt"],
        alias_evidence=alias, evidence_payloads=evidence)
    assert changed["enriched_view"] == original["enriched_view"]
    assert changed["input_sha256"] != original["input_sha256"]
    assert runtime._semantic_binding(changed) != runtime._semantic_binding(original)
    changed_row, changed_result = prepared(changed)
    assert all(changed_row["reranker_receipt"][key] == original_row["reranker_receipt"][key]
               for key in runtime._SCORES)
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("export opened source files"))
    monkeypatch.setattr(type(scorer), "score", lambda *a, **k: pytest.fail("export rescored"))
    accepted = runtime.export_candidate_calibration_fields(original_result, observer, binding=bound,
        capture_receipt=capture_storage(original_row, bound))["candidate_calibration_shadow"]
    rejected = runtime.export_candidate_calibration_fields(changed_result, observer, binding=bound,
        capture_receipt=capture_storage(changed_row, bound))["candidate_calibration_shadow"]
    assert accepted["status"] == "CALIBRATED_SHADOW_BOUND" and accepted["calibration_shadow"] is not None
    assert rejected["status"] == "NOT_AVAILABLE" and rejected["calibration_shadow"] is None
    assert rejected["reason_codes"] == ["FROZEN_SEMANTIC_BINDING_MISMATCH"]
    assert rejected["publication_authority"] is rejected["public_apply"] is rejected["action_applied"] is False


def test_semantic_calibration_binding_preserves_alias_payload_and_context(tmp_path):
    from test_candidate_reranker_runtime import semantic_observed
    _, _, _, observed_value = semantic_observed(tmp_path)
    value = observed_value["capture"]["semantic_input"]
    original = runtime._semantic_binding(value)
    # 별도 runtime/dataset post 매핑만 허용하고 시각·community·근거 변경은 숨기지 않는다.
    remapped = deepcopy(value)
    remapped["alias_evidence"]["community_source_view"]["post_id"] = "dataset-id"
    assert runtime._semantic_binding(remapped) == original
    for key in ("community", "as_of"):
        changed = deepcopy(value)
        changed["alias_evidence"]["community_source_view"][key]["value"] = "different"
        assert runtime._semantic_binding(changed) != original
    changed = deepcopy(value)
    changed["alias_payload_sha256"] = []
    assert runtime._semantic_binding(changed) != original
