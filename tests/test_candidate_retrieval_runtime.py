"""R2 CLI·저장·공개 지문·대시보드 경계를 묶어 검사한다."""
from __future__ import annotations

import argparse
import ast
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from llm_batch.runtime.candidate_retrieval import (
    prepare_candidate_retrieval, candidate_retrieval_policy_fields, export_candidate_retrieval_fields,
)


def receipt(post_id=42):
    return {"schema_version": "candidate_retrieval_shadow_v1", "mode": "SHADOW", "status": "COMPLETE",
            "post_id": post_id, "corpus_sha256": "a" * 64, "query_sha256": "b" * 64,
            "ranked_candidates": [{"corpus_candidate_id": "fixture-work", "title": "시험 작품", "score": 1.0,
                                    "source_refs": [{"source_ref": "fixture://work"}]}],
            "publication_authority": False, "central_db_write": False, "public_apply": False}


def binding(post_id=42):
    return {"run_id": "test-run", "post_id": post_id, "input_index": 0,
            "attempt_id": "attempt-1", "publication_scope_id": "scope-1"}


def test_off_does_not_read_corpus_or_add_feature_output():
    args = argparse.Namespace(candidate_retrieval="OFF", candidate_corpus="missing-and-must-not-read")
    with patch.object(Path, "read_bytes", side_effect=AssertionError("OFF must not read")):
        assert prepare_candidate_retrieval(args) is None
    assert export_candidate_retrieval_fields(object(), None, binding=binding()) == {}
    assert candidate_retrieval_policy_fields(None) == {}


@pytest.mark.parametrize("options", [{}, {"candidate_corpus": "a"},
    {"candidate_corpus": "a", "candidate_corpus_sha256": "A" * 64},
    {"candidate_corpus": "a", "candidate_corpus_sha256": "a" * 64, "candidate_retrieval_top_k": 0},
    {"candidate_corpus": "a", "candidate_corpus_sha256": "a" * 64, "candidate_retrieval_top_k": 101}])
def test_invalid_shadow_configuration_is_rejected_before_loading(options):
    with pytest.raises(ValueError):
        prepare_candidate_retrieval(argparse.Namespace(candidate_retrieval="SHADOW", **options))


def test_cli_and_loaded_observer_are_explicit_and_frozen_once():
    import expert_main
    args = expert_main._parse_args(["--candidate-retrieval", "SHADOW", "--candidate-corpus", "corpus.json",
        "--candidate-corpus-sha256", "a" * 64, "--candidate-retrieval-top-k", "5"])
    policy = {"mode": "SHADOW", "corpus_sha256": "a" * 64}
    observer = SimpleNamespace(summary=lambda: policy)
    with patch("llm_batch.grounding.candidate_retrieval_shadow.load_candidate_retrieval_shadow", return_value=observer) as loader:
        assert prepare_candidate_retrieval(args) is observer
        loader.assert_called_once_with(Path("corpus.json"), expected_sha256="a" * 64, top_k=5)
    fields = candidate_retrieval_policy_fields(observer)
    fields["candidate_retrieval_policy"]["mode"] = "CHANGED"
    assert policy["mode"] == "SHADOW"
    assert expert_main._parse_args([]).candidate_retrieval == "OFF"


def test_missing_or_broken_corpus_is_explicit_unavailable_and_never_fallback_corpus(tmp_path):
    args = argparse.Namespace(candidate_retrieval="SHADOW", candidate_corpus=str(tmp_path / "missing.json"),
                              candidate_corpus_sha256="a" * 64, candidate_retrieval_top_k=20)
    observer = prepare_candidate_retrieval(args)
    assert observer.summary()["status"] == "UNAVAILABLE_CORPUS"
    view = {"schema_version": "candidate_retrieval_source_view_v1", "post_id": 42,
            "fragments": [{"raw_path": "/title", "kind": "TITLE", "text": "원문"}]}
    observed = observer.observe(view)
    assert observed["status"] == "UNAVAILABLE_CORPUS" and not observed["ranked_candidates"]
    assert observed["corpus_sha256"] == "a" * 64
    assert len(observed["query_sha256"]) == 64


def test_receipt_is_attempt_bound_copied_and_public_payload_is_identical():
    from llm_batch.ledger.publication_commit import _stable_result_payload
    original = receipt()
    output = SimpleNamespace(_candidate_retrieval_shadow=original)
    fields = export_candidate_retrieval_fields(output, object(), binding=binding())
    saved = fields["candidate_retrieval_shadow"]
    assert saved["binding"]["attempt_id"] == "attempt-1"
    assert saved["binding"]["scope"] == "ATTEMPT_LOCAL_OBSERVATION"
    assert "binding" not in original
    base = {"post_id": 42, "analysis_result": {"identity": {"work_resolution": "HOLD"}}, "run_meta": {}}
    enriched = copy.deepcopy(base)
    enriched["run_meta"].update(fields)
    assert _stable_result_payload(enriched) == _stable_result_payload(base)
    saved["ranked_candidates"][0]["title"] = "changed"
    assert original["ranked_candidates"][0]["title"] == "시험 작품"


@pytest.mark.parametrize("raw", [receipt(99), {**receipt(), "schema_version": "bad"},
    {**receipt(), "publication_authority": True}, {**receipt(), "central_db_write": True}, {**receipt(), "public_apply": True},
    {**receipt(), "blob": "한글" * 40000}, {**receipt(), "score": float("nan")}])
def test_invalid_mismatched_or_oversized_receipt_is_never_silently_stored(raw):
    fields = export_candidate_retrieval_fields(SimpleNamespace(_candidate_retrieval_shadow=raw), object(), binding=binding())
    stored = fields["candidate_retrieval_shadow"]
    assert stored["status"] == "NOT_AVAILABLE"
    assert stored["reason_codes"] == ["INVALID_OR_OVERSIZED_RECEIPT"]
    assert not stored["ranked_candidates"]
    assert len(json.dumps(stored, ensure_ascii=False).encode()) < 64 * 1024


def test_missing_and_early_route_bypass_are_explicit():
    assert export_candidate_retrieval_fields(None, object(), binding=binding())["candidate_retrieval_shadow"]["reason_codes"] == ["PIPELINE_NOT_EXECUTED"]
    assert export_candidate_retrieval_fields(object(), object(), binding=binding())["candidate_retrieval_shadow"]["reason_codes"] == ["RECEIPT_NOT_AVAILABLE"]


def test_actual_dashboard_detail_includes_receipt_but_summary_does_not():
    from llm_batch.monitor.server import _to_live_detail, _to_history_summary
    from llm_batch.monitor.run_index import summary as manifest_summary, row_meta
    fields = export_candidate_retrieval_fields(SimpleNamespace(_candidate_retrieval_shadow=receipt()), object(), binding=binding())
    row = {"post_id": 42, "analysis_result": {"identity": {}}, "run_meta": fields}
    assert _to_live_detail(row)["run_meta"]["candidate_retrieval_shadow"] == fields["candidate_retrieval_shadow"]
    assert row_meta(row)["candidate_retrieval_shadow"]["binding"]["post_id"] == 42
    assert "candidate_retrieval_shadow" not in json.dumps(_to_history_summary(row))
    assert manifest_summary({"candidate_retrieval_policy": {"mode": "SHADOW"}})["candidate_retrieval_policy"]["mode"] == "SHADOW"


def test_main_wires_one_observer_to_workers_and_both_storage_paths():
    tree = ast.parse((ROOT / "expert_main.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    constructors = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "AgenticPipeline"]
    assert constructors and all(any(k.arg == "candidate_retrieval_shadow" for k in node.keywords) for node in constructors)
    rows = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "_candidate_retrieval_row_fields"]
    assert len(rows) == 2
    assert any(isinstance(node.args[0], ast.Constant) and node.args[0].value is None for node in rows)
