"""R3 실행 정책·판정 범위·저장과 API를 기능 단위로 검증한다."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from llm_batch.runtime.community_knowledge import (
    resolve_community_knowledge_settings, prepare_community_knowledge,
    community_knowledge_decision_fields, community_knowledge_policy_fields,
    export_community_knowledge_fields,
)

ROOT = Path(__file__).resolve().parents[1]


def store(sha="a" * 64, status="READY"):
    return SimpleNamespace(summary=lambda: {"snapshot_sha256": sha, "config_sha256": "b" * 64,
        "status": status, "reason_codes": [], "data_kind": "SYNTHETIC_FIXTURE"})


def receipt(post_id=42):
    value = {"schema_version": "community_knowledge_readback_v1", "mode": "READ_ONLY", "post_id": post_id,
        "status": "AMBIGUOUS", "reason_codes": [], "snapshot_sha256": "a" * 64,
        "query_sha256": "c" * 64, "config_sha256": "b" * 64,
        "candidates": [{"candidate_id": "fixture-1", "sense_candidate_id": "sense-1", "definition_text": "가상 의미"}],
        "occurrences": [], "consumption": {"status": "PROMPT_SECTION_INCLUDED"},
        "public_authority": False, "central_db_write": False, "public_apply": False}
    value["receipt_sha256"] = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return value


def binding():
    return {"run_id": "r3-run", "input_index": 1, "post_id": 42, "attempt_id": "r3-attempt", "publication_scope_id": "scope"}


def test_off_settings_do_not_load_storage_and_keep_old_config():
    resolved = resolve_community_knowledge_settings(argparse.Namespace(), {})
    assert resolved["mode"] == "OFF"
    with patch.object(Path, "read_bytes", side_effect=AssertionError("OFF must not read")):
        assert prepare_community_knowledge(resolved) is None
    assert community_knowledge_decision_fields(None) == community_knowledge_policy_fields(None) == {}
    assert export_community_knowledge_fields(object(), None, binding=binding()) == {}


def test_cli_overrides_environment_and_profile_does_not_enable_feature():
    import expert_main
    args = expert_main._parse_args(["--community-knowledge", "OFF", "--execution-profile", "low-load-validation"])
    resolved = resolve_community_knowledge_settings(args, {"EXPERT_COMMUNITY_KNOWLEDGE": "READ_ONLY"})
    assert resolved["mode"] == "OFF" and resolved["sources"]["mode"] == "CLI"
    args = expert_main._parse_args([])
    assert resolve_community_knowledge_settings(args, {})["mode"] == "OFF"
    env = {"EXPERT_COMMUNITY_KNOWLEDGE": "READ_ONLY", "EXPERT_COMMUNITY_SNAPSHOT": "fixture.json",
           "EXPERT_COMMUNITY_SNAPSHOT_SHA256": "a" * 64}
    assert resolve_community_knowledge_settings(args, env)["sources"]["snapshot_path"] == "ENVIRONMENT"
    override = expert_main._parse_args(["--community-snapshot", "selected.json"])
    assert resolve_community_knowledge_settings(override, env)["snapshot_path"] == "selected.json"


@pytest.mark.parametrize("options", [{}, {"community_snapshot": "a"},
    {"community_snapshot": "a", "community_snapshot_sha256": "A" * 64},
    {"community_snapshot": "a", "community_snapshot_sha256": "bad"}])
def test_read_only_requires_explicit_frozen_manifest(options):
    with pytest.raises(ValueError):
        resolve_community_knowledge_settings(argparse.Namespace(community_knowledge="READ_ONLY", **options), {})


def test_loader_is_called_once_and_no_alternate_data_on_load_failure(tmp_path):
    from llm_batch.grounding import community_knowledge
    settings = {"mode": "READ_ONLY", "snapshot_path": str(tmp_path / "missing.json"), "snapshot_sha256": "a" * 64}
    frozen = store()
    with patch.object(community_knowledge, "load_snapshot", return_value=frozen) as loader:
        assert prepare_community_knowledge(settings) is frozen
        loader.assert_called_once_with(Path(settings["snapshot_path"]), expected_sha256="a" * 64)
    unavailable = prepare_community_knowledge(settings)
    assert unavailable.summary()["snapshot_sha256"] == "a" * 64
    assert unavailable.summary()["status"] == "UNAVAILABLE"


def test_read_only_disables_both_writers_and_records_actual_measurement_state():
    import expert_main
    original_env = {"PIPELINE_SLANG_DB": "1"}
    off = expert_main._decision_call_measurement_config(original_env)
    active = expert_main._decision_call_measurement_config(original_env, community_knowledge_read_only=True)
    assert original_env == {"PIPELINE_SLANG_DB": "1"}
    assert off["mutable_context_binding"]["batch_context_enabled"] is True
    assert off["slang_access_mode"] == "MUTABLE_WRITE"
    assert active["mutable_context_mode"] == "FROZEN_OFF" and active["mutable_context_frozen"] is True
    assert active["mutable_context_binding"]["batch_context_enabled"] is False
    assert active["slang_access_mode"] == "OFF" and active["central_slang_db_write_allowed"] is False
    assert active["mutable_context_binding_sha256"] != off["mutable_context_binding_sha256"]


def test_snapshot_and_load_outcome_change_decision_config_without_local_path_noise():
    def sha(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    values = [community_knowledge_decision_fields(value) for value in (None, store(), store("d" * 64), store(status="UNAVAILABLE"))]
    assert len({sha(value) for value in values}) == 4
    policy = community_knowledge_policy_fields(store(), {"snapshot_path": "a.json", "sources": {"mode": "CLI"}})
    assert policy["community_knowledge_policy"]["model_input_may_change"] is True
    assert policy["community_knowledge_policy"]["batch_context_learning_enabled"] is False
    assert "snapshot_path" not in json.dumps(values)


def test_source_only_route_cannot_reuse_off_decision_with_read_only_context():
    import expert_main
    environment = {expert_main._MEASUREMENT_EARLY_ROUTE_MODE_ENV: "SOURCE_ONLY_V1"}
    with pytest.raises(ValueError, match="source-only early route"):
        expert_main._decision_call_measurement_config(environment, community_knowledge_read_only=True)


def test_receipt_only_is_volatile_and_original_private_object_not_mutated():
    from llm_batch.ledger.publication_commit import _stable_result_payload
    original = receipt()
    fields = export_community_knowledge_fields(SimpleNamespace(_community_knowledge_readback=original), store(), binding=binding())
    saved = fields["community_knowledge_readback"]
    assert saved["binding"]["scope"] == "ATTEMPT_LOCAL_CONSUMPTION"
    assert saved["binding"]["input_index"] == 1 and "binding" not in original
    base = {"post_id": 42, "analysis_result": {"identity": {"work_resolution": "HOLD"}}, "run_meta": {}}
    rich = copy.deepcopy(base); rich["run_meta"].update(fields)
    assert _stable_result_payload(rich) == _stable_result_payload(base)
    saved["candidates"][0]["definition_text"] = "변경"
    assert original["candidates"][0]["definition_text"] == "가상 의미"


@pytest.mark.parametrize("raw", [receipt(99), {**receipt(), "snapshot_sha256": "d" * 64},
    {**receipt(), "config_sha256": "e" * 64}, {**receipt(), "receipt_sha256": "e" * 64},
    {**receipt(), "consumption": {"status": "QUERY_ONLY"}},
    {**receipt(), "public_authority": True}, {**receipt(), "central_db_write": True}, {**receipt(), "public_apply": True},
    {**receipt(), "binding": {"attempt_id": "old"}}, {**receipt(), "blob": "한글" * 40000},
    {**receipt(), "schema_version": "old"}, {**receipt(), "value": float("nan")}])
def test_other_post_snapshot_attempt_authority_or_invalid_size_is_not_saved(raw):
    fields = export_community_knowledge_fields(SimpleNamespace(_community_knowledge_readback=raw), store(), binding=binding())
    assert fields["community_knowledge_readback"]["status"] == "NOT_AVAILABLE"
    assert fields["community_knowledge_readback"]["candidates"] == []


def test_early_route_and_missing_receipt_have_no_fabricated_consumption():
    early = export_community_knowledge_fields(None, store(), binding=binding())["community_knowledge_readback"]
    missing = export_community_knowledge_fields(object(), store(), binding=binding())["community_knowledge_readback"]
    assert early["reason_codes"] == ["PIPELINE_NOT_EXECUTED"]
    assert early["consumption"]["status"] == "NOT_CONSUMED_FAST_PATH"
    assert missing["consumption"]["status"] == "NOT_CONSUMED_ERROR"


@pytest.mark.parametrize("result", [None, object(), SimpleNamespace(_community_knowledge_readback={**receipt(), "consumption": {"status": "FORGED"}})])
def test_error_receipts_keep_config_binding_and_have_verifiable_digest(result):
    saved = export_community_knowledge_fields(result, store(), binding=binding())["community_knowledge_readback"]
    assert saved["snapshot_sha256"] == "a" * 64 and saved["config_sha256"] == "b" * 64
    assert saved["query_sha256"] is None and saved["status"] == "NOT_AVAILABLE"
    body = {k: v for k, v in saved.items() if k not in {"receipt_sha256", "binding", "elapsed_ms", "latency_ms"}}
    assert saved["receipt_sha256"] == hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def test_binding_limit_includes_final_digest_bytes():
    fields = export_community_knowledge_fields(None, store(), binding={**binding(), "run_id": "a" * 66000})
    saved = fields["community_knowledge_readback"]
    assert saved["reason_codes"] == ["BINDING_BYTE_LIMIT"]
    assert saved["snapshot_sha256"] == "a" * 64 and saved["receipt_sha256"]
    assert len(json.dumps(saved).encode()) < 64 * 1024


def test_actual_dashboard_details_but_not_lists_expose_bound_receipt():
    from llm_batch.monitor.server import _to_live_detail, _to_history_summary
    from llm_batch.monitor.run_index import summary, row_meta
    fields = export_community_knowledge_fields(SimpleNamespace(_community_knowledge_readback=receipt()), store(), binding=binding())
    row = {"post_id": 42, "analysis_result": {"identity": {}}, "run_meta": fields}
    assert _to_live_detail(row)["run_meta"]["community_knowledge_readback"] == fields["community_knowledge_readback"]
    assert row_meta(row)["community_knowledge_readback"]["binding"]["post_id"] == 42
    assert "community_knowledge_readback" not in json.dumps(_to_history_summary(row))
    assert summary({"community_knowledge_policy": {"mode": "READ_ONLY"}})["community_knowledge_policy"]["mode"] == "READ_ONLY"


def test_main_injects_one_snapshot_and_binds_both_storage_paths():
    tree = ast.parse((ROOT / "expert_main.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    pipelines = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "AgenticPipeline"]
    assert pipelines and all(any(k.arg == "community_knowledge" for k in n.keywords) for n in pipelines)
    storage = [n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "_community_knowledge_row_fields"]
    assert len(storage) == 2
    assert any(isinstance(n.args[0], ast.Constant) and n.args[0].value is None for n in storage)
