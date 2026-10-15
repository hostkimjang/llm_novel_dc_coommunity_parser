"""저장 provider 근거와 살아 있는 pre-final 문맥의 명시 native 복구 진입점.

기존 실행 결과를 덮어쓰지 않는다. 새 guard 결과와 publication WAL을 같은
추가 I/O 예산 안에서 검산하고 저장한다. 완료 job만 재생할 수 있다.
"""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

from ..ledger.publication_commit import (
    PUBLICATION_COMMIT_EVENT_SCHEMA, PublicationCommitRegistry, build_publication_scope_descriptor,
    commit_publication_result, validate_publication_result_commit,
)
from ..ledger.recovery_provider_journal import canonical_bytes, canonical_sha256
from ..ledger.recovery_native_journal import require
from ..measurement.recovery_native_source import read_native_provider_evidence
from .recovery_native_context import NativeRecoveryCapture, require_evidence
from .recovery_native_io import NativeRecoveryIO, NativeLLMFacade, NativeMCPFacade, validate_native_wire_config
from .recovery_provider_transport import _read

SCHEMA = "recovery_native_result_v1"
PROFILE = "EXPLICIT_SAME_CALL_SINGLE_PASS_NATIVE_RECHECK"


def _source_hashes():
    root = Path(__file__).resolve().parents[3]
    paths = [root / "expert_main.py", *sorted((root / "src/llm_batch").rglob("*.py"))]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def _environment_sha256():
    # 환경 원문/인증 값은 저장하지 않는다. 진행 중 native 설정 변경만 감지한다.
    return canonical_sha256(dict(os.environ))


def _file_ref(bound, path):
    path = bound.assert_output_path(path)
    raw = _read(path, 32 * 1024 * 1024)
    return {"path": str(path.relative_to(bound.output_dir)), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _validate_saved_result(bound, result, *, config, capture, binding):
    """재생 시 private native 객체를 복원하지 않고 저장된 계약과 파일을 검산한다."""
    require(type(result) is dict and result.get("schema_version") == SCHEMA, "NATIVE_RESULT_SCHEMA")
    require(result.get("config") == config and result.get("binding") == binding, "NATIVE_RESULT_CONFIG")
    require(result.get("capture_sha256") == capture.capture_sha256, "NATIVE_RESULT_CAPTURE")
    require(all(result.get(k) is False for k in ("public_apply", "central_db_write", "publication_authority")), "NATIVE_RESULT_AUTHORITY")
    from ..ledger.publication_commit import PublicationScopeDescriptor
    descriptor = PublicationScopeDescriptor.from_dict(result["publication_scope"])
    expected = build_publication_scope_descriptor(input_file_sha256=bound.base["input_raw_sha256"],
        post_ids=[capture.post.post_id], config_hash=canonical_sha256({"binding": binding, "policy": config["policy"]}),
        release_fingerprint=binding["source_sha256"])
    require(descriptor.to_dict() == expected.to_dict(), "NATIVE_PUBLICATION_SCOPE_CHANGED")
    row, receipt = result["result"], result["publication_commit"]
    validate_publication_result_commit(row, receipt, expected_scope_id=descriptor.publication_scope_id,
                                      expected_input_index=1, expected_post_id=capture.post.post_id)
    refs = result.get("publication_files")
    require(type(refs) is list and len(refs) == 2 and [r.get("path") for r in refs] ==
            [str(Path("native/publication_commits.jsonl")), str(Path("native/publication_commits.jsonl.scope.json"))], "NATIVE_PUBLICATION_FILES")
    for ref in refs:
        path = bound.assert_output_path(bound.output_dir / ref["path"])
        require(_file_ref(bound, path) == ref, "NATIVE_PUBLICATION_FILE_CHANGED")
    # strict JSONL readback: Registry의 미완결 tail 수리 동작을 재생에 사용하지 않는다.
    from ..measurement.recovery_execution_readback import read_strict_json
    scope_raw = _read(bound.assert_output_path(bound.output_dir / refs[1]["path"]), refs[1]["bytes"])
    require(read_strict_json(scope_raw, maximum_bytes=len(scope_raw)) == expected.to_dict(), "NATIVE_SCOPE_FILE_CHANGED")
    wal = _read(bound.assert_output_path(bound.output_dir / refs[0]["path"]), refs[0]["bytes"])
    require(wal.endswith(b"\n") and len(wal.splitlines()) == 1, "NATIVE_PUBLICATION_WAL_ROWS")
    event = read_strict_json(wal.strip(), maximum_bytes=len(wal))
    require(event.get("schema_version") == PUBLICATION_COMMIT_EVENT_SCHEMA
            and event.get("result") == row and event.get("receipt") == receipt, "NATIVE_PUBLICATION_WAL_BINDING")
    require(result.get("guard_status") == receipt["outcome"], "NATIVE_GUARD_STATUS_CHANGED")
    return True


def run_native_recovery(bound, capture, *, policy, endpoints, model, max_tokens,
                        temperature=0, top_p=1, headers=None, cancelled=None,
                        test_transport=None, clock_ms=None, server_type='openai',
                        min_p=None, repeat_penalty=None, enable_thinking=False,
                        temperature_by_tag=None, vllm_top_k=None, vllm_presence_penalty=None):
    """명시 provider 완료와 same-call capture를 받아 별도 native 결과를 반환한다.

    output 경로는 provider namespace 아래 고정된다. source/config/context를
    바꾸어 같은 upstream job의 예산을 다시 시작하는 것은 영속 원장이 거절한다.
    실제 transport는 명시 caller의 책임이다. TEST_SYNTHETIC은 mock만 허용한다.
    """
    wire_config = validate_native_wire_config(model=model, max_tokens=max_tokens,
        temperature=temperature, top_p=top_p, server_type=server_type, min_p=min_p,
        repeat_penalty=repeat_penalty, enable_thinking=enable_thinking,
        temperature_by_tag=temperature_by_tag, vllm_top_k=vllm_top_k,
        vllm_presence_penalty=vllm_presence_penalty)
    require(type(capture) is NativeRecoveryCapture, "NATIVE_CAPTURE_TYPE")
    capture.verify_current()
    evidence = read_native_provider_evidence(bound)
    require_evidence(capture, evidence)
    require(evidence.data_kind != "TEST_SYNTHETIC" or test_transport is not None, "NATIVE_SYNTHETIC_REQUIRES_MOCK")
    require(type(endpoints) is dict and set(endpoints) == {"OPENAI_CHAT", "MCP_SEARCH", "MCP_FETCH"}, "NATIVE_ENDPOINT_SET")
    config = {"profile": PROFILE, **deepcopy(wire_config), "endpoints": dict(endpoints),
              "environment_sha256": _environment_sha256(), "policy": deepcopy(policy)}
    sources = _source_hashes()
    binding = {"source_sha256": canonical_sha256(sources), "config_sha256": canonical_sha256(config),
               "base_sha256": canonical_sha256(evidence.base), "context_sha256": capture.context_sha256,
               "upstream_sha256": canonical_sha256(evidence.report)}
    directory = bound.output_dir / "native"
    journal_path = bound.assert_output_path(directory / "native_journal.jsonl")

    def source_check():
        bound.assert_output_path(journal_path)
        require(evidence.verify_current() and capture.verify_current(), "NATIVE_SOURCE_CHANGED")
        require(_source_hashes() == sources and _environment_sha256() == config["environment_sha256"], "NATIVE_RUNTIME_CHANGED")
        return True

    io = NativeRecoveryIO(binding=binding, policy=policy, endpoints=endpoints, journal_path=journal_path,
        upstream_receipt=evidence.report, source_check=source_check,
        cancelled=cancelled or (lambda: False), headers=headers, test_transport=test_transport, clock_ms=clock_ms)
    io.llm = NativeLLMFacade(io, **wire_config)
    io.mcp = NativeMCPFacade(io)
    replay = io.readback()
    if replay["status"] == "COMPLETED_NATIVE_IO":
        _validate_saved_result(bound, replay["native_result"], config=config, capture=capture, binding=binding)
        return replay
    if replay["status"] != "NOT_STARTED":
        return replay
    io.check()
    from ..agentic_pipeline import AgenticPipeline
    from expert_main import _FinalSourceContextResult
    pipeline = AgenticPipeline(llm=io.llm, mcp=io.mcp, output_dir=directory / "pipeline", native_recovery=True)
    try:
        outcome = pipeline.continue_native_recovery(capture, evidence, io)
        output = outcome.output
        payload = output.model_dump(mode="json")
        first_observation = pipeline.verify_final_source_context_serialization(output, payload, stage="model_dump")
        row = capture.post_snapshot
        row["analysis_result"] = payload
        attempt = "native-" + canonical_sha256(binding)[:40]
        row["run_meta"] = {"run_id": attempt, "execution_mode": PROFILE, "public_apply": False}
        wrapped = _FinalSourceContextResult(row, output=output, verifier=pipeline.verify_final_source_context_serialization)
        descriptor = build_publication_scope_descriptor(input_file_sha256=evidence.base["input_raw_sha256"],
            post_ids=[capture.post.post_id], config_hash=canonical_sha256({"binding": binding, "policy": policy}),
            release_fingerprint=binding["source_sha256"])
        require(descriptor.publication_scope_id != evidence.base["publication_scope_id"], "NATIVE_SCOPE_NOT_SEPARATE")
        io.check()
        wal_path = bound.assert_output_path(directory / "publication_commits.jsonl")
        descriptor_path = bound.assert_output_path(wal_path.with_name(wal_path.name + ".scope.json"))
        registry = PublicationCommitRegistry(wal_path, scope_descriptor=descriptor, create_new=True)
        receipt, created = commit_publication_result(wrapped, registry=registry, attempt_run_id=attempt,
                                                     input_index=1, post_id=capture.post.post_id)
        require(created, "NATIVE_PUBLICATION_NOT_NEW")
        stored = registry.result(capture.post.post_id)
        stored_observation = wrapped.verify_stored_payload(stored, stage="canonical_stored_payload")
        validate_publication_result_commit(stored, receipt, expected_scope_id=descriptor.publication_scope_id,
                                          expected_input_index=1, expected_post_id=capture.post.post_id)
        io.check()
        result = {"schema_version": SCHEMA, "execution_mode": PROFILE, "binding": binding,
            "config": config, "source_files_sha256": sources, "capture_sha256": capture.capture_sha256,
            "base": evidence.base, "data_kind": evidence.data_kind,
            "continuation": outcome.receipt, "result": stored, "guard_status": receipt.outcome,
            "publication_commit": receipt.to_dict(), "publication_scope": descriptor.to_dict(),
            "publication_files": [_file_ref(bound, wal_path), _file_ref(bound, descriptor_path)],
            "serialization_checks": json.loads(json.dumps([first_observation, stored_observation],
                                                           ensure_ascii=False, allow_nan=False)),
            "publication_authority": False, "public_apply": False, "central_db_write": False,
            "actual_quality_evaluated": False, "formal_kpi_status": "NOT_ESTIMABLE"}
        _validate_saved_result(bound, result, config=config, capture=capture, binding=binding)
        finished = io.finish(result)
        if finished["status"] == "COMPLETED_NATIVE_IO":
            _validate_saved_result(bound, finished["native_result"], config=config, capture=capture, binding=binding)
        return finished
    except Exception as exc:
        code = getattr(exc, "code", "NATIVE_WORKFLOW_FAILED")
        io.fail(code)
