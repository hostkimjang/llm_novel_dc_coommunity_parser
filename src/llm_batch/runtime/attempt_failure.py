"""실패 관측만 보존한다. 공개 원장·결과·provider 호출을 수행하지 않는다."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
import traceback
from typing import Any


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _exclusive(path: Path, payload: Any) -> dict:
    data = _bytes(payload)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest()}


def _replace(path: Path, payload: Any) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        _exclusive(temporary, payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def note_secondary(state: dict, original: BaseException, stage: str,
                   secondary: BaseException) -> None:
    message = f"{stage}: {type(secondary).__name__}: {secondary}"
    state.setdefault("secondary_errors", []).append(message)
    original.add_note(message)


def preserve_rejected_publication(*, state: dict, error: BaseException,
        output_file: Path, run_id: str, publication_scope_id: str,
        input_sha256: str, input_index: int, post_id: Any, result: Any,
        reference_result: Any, reference_receipt: Any) -> None:
    """preview에 전달된 실제 row를 보존한다. 오류가 나도 최초 예외를 대체하지 않는다."""
    try:
        current = getattr(error, "current_publication_preview", None)
        current_dict = current.to_dict() if current is not None else None
        reference_dict = reference_receipt.to_dict() if reference_receipt is not None else None
        current_bytes = _bytes(result)
        reference_bytes = _bytes(reference_result) if reference_result is not None else None
        differences = ([key for key in sorted(set(current_dict) | set(reference_dict))
                        if current_dict.get(key) != reference_dict.get(key)]
                       if current_dict is not None and reference_dict is not None else None)
        # 이름은 행 번호뿐이며 원문 ID를 경로로 사용하지 않는다.
        folder = output_file.with_name(output_file.stem + "_rejected_rows")
        folder.mkdir(exist_ok=True)
        path = folder / f"row_{input_index:06d}.json"
        state["rejected_row_ref"] = _exclusive(path, {
            "schema_version": "rejected_publication_observation_v1",
            "run_id": run_id, "publication_scope_id": publication_scope_id,
            "input_sha256": input_sha256, "input_index": input_index, "post_id": post_id,
            "output_file": str(output_file.resolve()), "accepted": False,
            "error_type": type(error).__name__, "error_message": str(error),
            "fresh_result": json.loads(current_bytes),
            "fresh_result_canonical_sha256": hashlib.sha256(current_bytes[:-1]).hexdigest(),
            "reference_result": json.loads(reference_bytes) if reference_bytes is not None else None,
            "reference_result_canonical_sha256": (hashlib.sha256(reference_bytes[:-1]).hexdigest()
                                                   if reference_bytes is not None else None),
            "current_preview": current_dict, "reference_receipt": reference_dict,
            "receipt_differing_fields": differences,
            "preview_missing_reason": None if current_dict is not None else "REJECTED_BEFORE_REFERENCE_COMPARISON",
        })
    except BaseException as secondary:
        note_secondary(state, error, "rejected_row_preservation", secondary)


def drain_failed_workers(*, executor: Any, futures: Any, stop_event: Any,
                         state: dict, error: BaseException) -> str:
    """진행 중 호출은 강제 취소하지 못한다. 완료값을 commit/학습하지 않고 기다린다."""
    stop_event.set()
    for future in list(futures):
        try:
            future.cancel()
        except BaseException as secondary:
            note_secondary(state, error, "cancel_queued_future", secondary)
    if executor is None:
        return "NOT_STARTED"
    try:
        executor.shutdown(wait=True, cancel_futures=True)
    except BaseException as secondary:
        note_secondary(state, error, "worker_drain", secondary)
        return "CLEANUP_ERROR"
    return "DRAINED"


def close_worker_logs(logs: Any, *, state: dict, error: BaseException) -> None:
    for stream in logs:
        try:
            stream.close()
        except BaseException as secondary:
            note_secondary(state, error, "worker_log_close", secondary)


def record_attempt_failure(*, state: dict, error: BaseException, manifest_path: Path,
        output_file: Path, run_id: str, publication_scope_id: str | None,
        input_sha256: str | None, total: int, flushed: int, pending: int, failed: int,
        parallel_count: int, started_at_epoch: float, shutdown_status: str,
        attempt_configuration: dict, monitor: Any = None) -> None:
    """코어 예외 관측과 OS 종료 관측은 다르다. exit code는 runner만 채운다."""
    state["shutdown_status"] = shutdown_status
    if "failure_observed_at_epoch" not in state:
        state["failure_observed_at_epoch"] = time.time()
    counts = {"input_post_count": total, "completed_count": flushed + pending,
              "flushed_count": flushed, "pending_count": pending, "failed_count": max(1, failed)}
    try:
        if "failure_ref" not in state:
            diagnostic_path = output_file.with_name(output_file.stem + "_failure.json")
            state["failure_ref"] = _exclusive(diagnostic_path, {
                "schema_version": "expert_attempt_failure_v1", "run_id": run_id,
                "publication_scope_id": publication_scope_id,
                "output_file": str(output_file.resolve()), "input_sha256": input_sha256,
                "error_type": type(error).__name__, "error_message": str(error),
                "traceback": "".join(traceback.format_exception(error)),
                "failed_input_index": state.get("input_index"), "failed_post_id": state.get("post_id"),
                "rejected_row_ref": state.get("rejected_row_ref"),
                "attempt_configuration": attempt_configuration,
                "failure_observed_at_epoch": state["failure_observed_at_epoch"],
                "manifest_counts": counts, "secondary_errors": list(state.get("secondary_errors", [])),
            })
    except BaseException as secondary:
        note_secondary(state, error, "failure_diagnostic", secondary)

    event = {
        "schema_version": "dashboard_run_failure_v1", "failure_origin": "CORE_EXCEPTION",
        "run_id": run_id, "publication_scope_id": publication_scope_id,
        "output_file": str(output_file.resolve()), "parallel_count": parallel_count,
        "reason_code": "CORE_EXCEPTION", "message": f"{type(error).__name__}: {error}"[:1000],
        "exit_code": None, "process_exited": False,
        "started_at_epoch": started_at_epoch,
        # 화면 elapsed의 실패 관측 경계이며 프로세스 종료 시각이라고 주장하지 않는다.
        "ended_at_epoch": state["failure_observed_at_epoch"],
        "manifest_counts": counts, "receipt_ref": state.get("failure_ref"),
        "shutdown_status": shutdown_status,
        "rejected_row_ref": state.get("rejected_row_ref"),
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        if manifest:
            if (manifest.get("run_id") != run_id
                    or Path(manifest.get("output_file", "")).resolve() != output_file.resolve()
                    or manifest.get("publication_scope_id") != publication_scope_id):
                raise ValueError("failure manifest belongs to a different run/output/scope")
        manifest.update(run_id=run_id, output_file=str(output_file.resolve()),
                        publication_scope_id=publication_scope_id,
                        terminal_status="FAILED", batch_status="FAILED", batch_running=False,
                        terminal_artifacts_finalized=False, large_run_complete=False,
                        large_run_runtime_complete=False, **counts)
        for name in ("runtime_completion_gate", "measurement_gate"):
            gate = dict(manifest.get(name) or {})
            gate.update(status="NO_GO", reason_codes=sorted(set(gate.get("reason_codes", [])) | {"ATTEMPT_FATAL_FAILURE"}))
            if name == "measurement_gate":
                gate["blocks_large_run_complete"] = True
            else:
                gate.update(schema_version="runtime_completion_gate_v1",
                            input_post_count=total, completed_count=flushed,
                            pending_count=pending, failed_count=max(1, failed),
                            terminal_artifacts_finalized=False)
            manifest[name] = gate
        manifest["batch_failure"] = event
        manifest["failure_secondary_errors"] = list(state.get("secondary_errors", []))
        _replace(manifest_path, manifest)
    except BaseException as secondary:
        note_secondary(state, error, "failure_manifest", secondary)
    if monitor is not None:
        try:
            monitor.emit("batch_failed", event)
        except BaseException as secondary:
            note_secondary(state, error, "failure_monitor", secondary)
