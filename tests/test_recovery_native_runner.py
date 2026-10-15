"""명시 native 진입점의 실제 guard·새 WAL·0회 재생과 원본 보존을 검증한다."""
from pathlib import Path

import httpx
import pytest

from src.llm_batch.agentic_pipeline import AgenticPipeline
from src.llm_batch.runtime import recovery_native_io as io_module
from src.llm_batch.runtime.recovery_native_workflow import run_native_recovery
from tests.recovery_native_fixtures import (
    ENDPOINTS, NativeHTTPFixture, build_native_base_fixture, build_native_capture,
    store_native_provider_evidence, source_bytes,
)


@pytest.fixture(autouse=True)
def native_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(io_module, "NATIVE_JOB_REGISTRY_ROOT", tmp_path / "registry")


def prepare(tmp_path, case="positive"):
    bundle = build_native_base_fixture(tmp_path / "base", case=case)
    handler = NativeHTTPFixture(bundle["native_case"])
    store_native_provider_evidence(bundle, handler)
    pipeline = AgenticPipeline(llm=object(), mcp=object(), output_dir=tmp_path / "capture", native_recovery=True)
    capture = build_native_capture(pipeline, bundle)["capture"]
    options = dict(policy={"max_calls": 32, "max_elapsed_ms": 180000, "request_timeout_ms": 30000,
                          "max_response_bytes": 2 * 1024 * 1024, "max_total_response_bytes": 64 * 1024 * 1024},
                   endpoints=ENDPOINTS, model="synthetic-native-model", max_tokens=32768,
                   test_transport=httpx.MockTransport(handler), clock_ms=lambda: 2000)
    return bundle, handler, capture, options


@pytest.mark.parametrize("case,server_type", [("positive", "openai"), ("hold", "vllm")])
def test_native_runner_guard_wal_readback_and_zero_call_replay(tmp_path, case, server_type):
    bundle, handler, capture, options = prepare(tmp_path, case)
    if server_type == "vllm":
        options.update(server_type="vllm", min_p=0.02, repeat_penalty=1.1,
            vllm_top_k=17, vllm_presence_penalty=1.25, enable_thinking=False,
            temperature_by_tag={"decoder": 0.4, "reason_review": 0.3})
    before = source_bytes(bundle)
    result = run_native_recovery(bundle["bound"], capture, **options)
    assert result["status"] == "COMPLETED_NATIVE_IO", result
    native = result["native_result"]
    assert native["guard_status"] == bundle["native_case"]["expected_outcome"]
    assert native["continuation"]["status"] == "NATIVE_GUARD_EVALUATED"
    assert all(native[k] is False for k in ("public_apply", "central_db_write", "publication_authority"))
    assert native["publication_scope"]["publication_scope_id"] != bundle["scope"].publication_scope_id
    assert native["serialization_checks"] and len(native["publication_files"]) == 2
    count = len(handler.requests)
    replay = run_native_recovery(bundle["bound"], capture, **options)
    assert replay["status"] == "COMPLETED_NATIVE_IO" and replay["replayed"]
    assert replay["native_result"] == native
    assert replay["transport_invocations_this_invocation"] == 0 and len(handler.requests) == count
    assert replay["total_actual_external_calls"] == 0
    assert replay["total_client_http_invocations"] == count
    assert source_bytes(bundle) == before

    from src.llm_batch.runtime.recovery_native_workflow import validate_native_wire_config
    wire = validate_native_wire_config(**{key: options[key] for key in (
        "model", "max_tokens", "temperature", "top_p", "server_type", "min_p",
        "repeat_penalty", "enable_thinking", "temperature_by_tag", "vllm_top_k",
        "vllm_presence_penalty") if key in options})
    assert {key: native["config"][key] for key in wire} == wire
    if server_type == "vllm":
        from copy import deepcopy
        drift = deepcopy(options["temperature_by_tag"])
        drift["decoder"] = 0.5
        changed = run_native_recovery(bundle["bound"], capture, **{**options, "temperature_by_tag": drift})
        assert changed["status"] == "NOT_AVAILABLE" and len(handler.requests) == count

    from copy import deepcopy
    from src.llm_batch.runtime.recovery_native_workflow import _validate_saved_result
    for field, value in (("guard_status", "UNVERIFIED"), ("public_apply", True)):
        changed = deepcopy(native)
        changed[field] = value
        with pytest.raises(ValueError):
            _validate_saved_result(bundle["bound"], changed, config=native["config"],
                                   capture=capture, binding=native["binding"])


def test_invalid_wire_is_rejected_before_capture_provider_read_or_io(monkeypatch):
    from src.llm_batch.runtime import recovery_native_workflow as workflow
    def forbidden(*args, **kwargs): pytest.fail("설정 오류를 source/I/O 생성 전에 거절해야 한다")
    monkeypatch.setattr(workflow, 'read_native_provider_evidence', forbidden)
    monkeypatch.setattr(workflow, 'NativeRecoveryIO', forbidden)
    with pytest.raises(ValueError, match='NATIVE_LLM_VLLM_TOP_K'):
        workflow.run_native_recovery(None, None, policy={}, endpoints={}, model='synthetic-model',
            max_tokens=1024, server_type='vllm', vllm_top_k=True)


def test_native_runner_failed_job_does_not_restart_or_reset_budget(tmp_path):
    bundle, handler, capture, options = prepare(tmp_path)
    options["policy"]["max_calls"] = 1
    with pytest.raises(ValueError):
        run_native_recovery(bundle["bound"], capture, **options)
    count = len(handler.requests)
    assert count == 2  # upstream 검색 1회 + native 첫 전문가 1회
    replay = run_native_recovery(bundle["bound"], capture, **options)
    assert replay["status"] in {"INCOMPLETE", "NOT_AVAILABLE"}
    assert len(handler.requests) == count and replay["transport_invocations_this_invocation"] == 0
    options["policy"]["max_calls"] = 32
    changed = run_native_recovery(bundle["bound"], capture, **options)
    assert changed["status"] == "NOT_AVAILABLE" and len(handler.requests) == count


def test_native_runner_rejects_changed_input_before_dispatch(tmp_path):
    bundle, handler, capture, options = prepare(tmp_path)
    Path(bundle["source_refs"]["input"]["path"]).write_bytes(b"{}\n")
    with pytest.raises(ValueError):
        run_native_recovery(bundle["bound"], capture, **options)
    assert len(handler.requests) == 1
    assert not (bundle["bound"].output_dir / "native" / "native_journal.jsonl").exists()


def test_native_runner_stored_wal_tamper_is_not_repaired(tmp_path):
    bundle, handler, capture, options = prepare(tmp_path)
    result = run_native_recovery(bundle["bound"], capture, **options)
    assert result["status"] == "COMPLETED_NATIVE_IO", result
    wal = bundle["bound"].output_dir / result["native_result"]["publication_files"][0]["path"]
    raw = wal.read_bytes() + b"unfinished"
    wal.write_bytes(raw)
    count = len(handler.requests)
    with pytest.raises(ValueError, match="NATIVE_PUBLICATION_FILE_CHANGED"):
        run_native_recovery(bundle["bound"], capture, **options)
    assert wal.read_bytes() == raw and len(handler.requests) == count


def test_native_runner_changed_fallback_environment_cannot_replay_or_send(tmp_path, monkeypatch):
    bundle, handler, capture, options = prepare(tmp_path)
    result = run_native_recovery(bundle["bound"], capture, **options)
    assert result["status"] == "COMPLETED_NATIVE_IO", result
    count = len(handler.requests)
    monkeypatch.setenv("REASON_FULL_MODE", "0" if __import__("os").environ.get("REASON_FULL_MODE") != "0" else "1")
    replay = run_native_recovery(bundle["bound"], capture, **options)
    assert replay["status"] == "NOT_AVAILABLE" and len(handler.requests) == count
