"""실제 producer/validator 계약 시험. 모델·child 호출 및 옛 reference 재봉인 없음."""
import ast
from copy import deepcopy
import hashlib
import json
import socket
import subprocess

import pytest
import expert_main as main
from tests import test_paired_execution_main as harness
from tests.test_paired_execution_main import connected, main_ast
from tests.test_paired_parallel12_main import bind12, preflight
from tests.test_expert_main_early_route_measurement import _post
from tests.test_publication_decision_commit import _valid_result, _scope_id


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("메타데이터 시험의 외부 호출/child 금지")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


@pytest.mark.parametrize("attempt_hash", ["before-local", "after-local", "shadow-local"])
def test_actual_process_one_uses_publication_hash_not_attempt_hash(
        connected, main_ast, tmp_path, monkeypatch, attempt_hash):
    ns = bind12(connected, tmp_path, monkeypatch, 1)
    preflight(connected, main_ast)
    ns["_config_hash"] = attempt_hash
    session = harness.start(connected, main_ast)
    result = ns["_process_one"](_post(author="합성", url="", created_at=""), 1, 1,
                                ns["_create_pipeline"](), 0)
    assert result["run_meta"]["config_hash"] == ns["_publication_config_hash"]
    assert result["run_meta"]["config_hash"] != attempt_hash
    assert "full_run_config_hash" not in result["run_meta"]
    session.finish()


def receipt(row, run="reference"):
    return main._preview_publication_decision(row, publication_scope_id=_scope_id(),
        attempt_run_id=run, input_index=1, post_id=101)


@pytest.mark.parametrize("arm", ["BEFORE", "AFTER", "SHADOW"])
def test_same_publication_config_keeps_real_decision_and_full_attempt_manifest(arm, main_ast):
    reference_payload = {"model": "same", "decision_call_measurement": {"arm": "REFERENCE"},
                         "decision_ledger_v2_shadow": {"mode": "SHADOW"}}
    attempt_payload = deepcopy(reference_payload)
    attempt_payload["decision_call_measurement"] = {"arm": arm}
    attempt_payload["decision_ledger_v2_shadow"] = {"mode": "REQUIRED"}
    def hash_config(payload):
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    semantic = main._decision_affecting_publication_config(reference_payload)
    assert main._decision_affecting_publication_config(attempt_payload) == semantic
    ref = _valid_result(publish=False)
    ref["run_meta"]["config_hash"] = hash_config(semantic)
    fresh = deepcopy(ref)
    # 실제 manifest producer의 attempt_configuration 표현식을 평가한다.
    fn = harness.function(main_ast, "_parallel_manifest_fields")
    expressions = [value for node in ast.walk(fn) if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and key.value == "attempt_configuration"]
    assert len(expressions) == 1
    ns = dict(vars(main), _config_hash=hash_config(attempt_payload)[:12],
              _run_config_payload=attempt_payload)
    settings = eval(compile(ast.Expression(expressions[0]), str(harness.SOURCE), "eval"), ns)
    assert settings == {"config_hash": hash_config(attempt_payload)[:12],
                        "run_config_payload": attempt_payload}
    assert settings["run_config_payload"] is not attempt_payload
    assert hash_config(reference_payload) != hash_config(attempt_payload)
    rc = receipt(ref)
    current = main._preview_publication_decision(fresh, publication_scope_id=_scope_id(),
        attempt_run_id=arm, input_index=1, post_id=101, reference_receipt=rc)
    assert current.decision_id == rc.decision_id


@pytest.mark.parametrize("difference", ["config_hash", "reason", "content"])
def test_same_public_null_does_not_relax_real_semantic_validator(difference):
    ref = _valid_result(publish=False)
    ref["run_meta"]["config_hash"] = "same"
    ref_before = deepcopy(ref)
    rc = receipt(ref)
    fresh = deepcopy(ref)
    if difference == "config_hash":
        fresh["run_meta"]["config_hash"] = "old-attempt-local-value"
    elif difference == "reason":
        fresh["analysis_result"]["identity"]["reason"] = "실제 의미 차이"
    else:
        fresh["content"] = ["원문 변경"]
    before = deepcopy(fresh)
    with pytest.raises(main.PublicationCommitError) as caught:
        main._preview_publication_decision(fresh, publication_scope_id=_scope_id(),
            attempt_run_id="fresh", input_index=1, post_id=101, reference_receipt=rc)
    assert caught.value.current_publication_preview.decision_id != rc.decision_id
    assert fresh == before and ref == ref_before
    public = ref["analysis_result"]["identity"]["novel_identity"]
    assert isinstance(public, dict)
    assert public["official_title"] is None and public["heretic_url"] is None
    main.validate_publication_result_commit(ref, rc)  # 옛 receipt도 변경 없이 읽는다.


def test_preview_keeps_original_exception_identity_and_comparison_input(monkeypatch):
    row = _valid_result(publish=False)
    rc = receipt(row)
    original = main.PublicationCommitError("원래 비교 거절")
    calls = []
    def reject(result, reference, **kwargs):
        calls.append((result, reference, kwargs))
        raise original
    monkeypatch.setattr(main, "validate_publication_result_decision", reject)
    with pytest.raises(main.PublicationCommitError) as caught:
        main._preview_publication_decision(row, publication_scope_id=_scope_id(),
            attempt_run_id="fresh", input_index=1, post_id=101, reference_receipt=rc)
    assert caught.value is original
    assert calls[0][0] is row and calls[0][1] is rc
    assert original.current_publication_preview.result_sha256 == rc.result_sha256
