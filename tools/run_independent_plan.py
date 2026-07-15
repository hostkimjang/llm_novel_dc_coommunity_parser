from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.test_run_dashboard_policy import DEFAULT_DASHBOARD_URL, strip_no_dashboard


MANIFEST_ATTACH_WAIT_SECONDS = 120.0
SAFE_LOSS_PLAN_TYPE = "safe_loss_flip_rate_probe_independent_run_plan"
EXECUTION_CLAIM_VERSION = "independent-plan-execution-claim-v3"
RUNTIME_PATH_CLAIM_VERSION = "independent-plan-runtime-path-claim-v1"
RECOVERY_ARTIFACT_QUIESCENCE_SECONDS = 0.1
CHILD_LIVENESS_ACTIVE = "ACTIVE"
CHILD_LIVENESS_EXITED = "EXITED_CONFIRMED"
CHILD_LIVENESS_UNKNOWN = "UNKNOWN"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"plan must be a JSON object: {path}")
    return payload


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def _write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


def _write_line_exclusive(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text + "\n")


def _validate_plan_self_binding(plan: dict[str, Any]) -> None:
    binding = plan.get("plan_self_binding")
    if plan.get("manifest_type") != SAFE_LOSS_PLAN_TYPE and binding is None:
        return
    if not isinstance(binding, dict):
        raise ValueError("run plan self binding missing or invalid")
    payload = dict(plan)
    payload.pop("plan_self_binding", None)
    expected = {
        "version": "safe-loss-flip-rate-plan-self-binding-v1",
        "algorithm": "sha256",
        "canonicalization": "json-sort-keys-compact-utf8",
        "excluded_field": "plan_self_binding",
        "canonical_sha256": _canonical_sha256(payload),
    }
    if binding != expected:
        raise ValueError("run plan self binding mismatch")


def _validate_safe_loss_blind_judge_binding(plan: dict[str, Any]) -> None:
    if plan.get("manifest_type") != SAFE_LOSS_PLAN_TYPE:
        return
    from tools.safe_loss_flip_rate_probe import _blind_judge_binding

    blind_judge = plan.get("blind_judge")
    recorded = plan.get("blind_judge_binding")
    post_ids = [str(value or "").strip() for value in (plan.get("post_ids") or [])]
    repeats = plan.get("repeats")
    if not isinstance(blind_judge, str) or not isinstance(recorded, dict):
        raise ValueError("safe-loss run plan blind judge binding missing or invalid")
    if isinstance(repeats, bool) or not isinstance(repeats, int):
        raise ValueError("safe-loss run plan repeats missing or invalid")
    current = _blind_judge_binding(
        _resolve_path(blind_judge), post_ids=post_ids, repeats=repeats
    )
    if current != recorded:
        raise ValueError("safe-loss run plan blind judge binding mismatch")


def _resolve_path(value: Any) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        path = _REPO_ROOT / path
    return path.resolve()


def _execution_claim_contract(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    runs: list[Any],
) -> dict[str, Any]:
    raw = plan.get("execution_claim_contract")
    if plan.get("manifest_type") == SAFE_LOSS_PLAN_TYPE:
        if not isinstance(raw, dict):
            raise ValueError("safe-loss plan execution_claim_contract missing or invalid")
        if raw.get("version") != EXECUTION_CLAIM_VERSION:
            raise ValueError("safe-loss plan execution claim version mismatch")
        required_paths = (
            "anchor_dir",
            "persistent_plan_claim_json",
            "active_lock_file",
            "attempts_dir",
            "adoptions_dir",
        )
        resolved = {field: _resolve_path(raw.get(field)) for field in required_paths}
        anchor = resolved["anchor_dir"]
        if any(path != anchor and anchor not in path.parents for path in resolved.values()):
            raise ValueError("safe-loss execution claim paths escape anchor_dir")
        if raw.get("required_adopted_completion_count") != len(runs):
            raise ValueError("safe-loss required adopted completion count mismatch")
        for field in (
            "one_adopted_attempt_per_post_repeat",
            "unrecorded_attempts_allowed",
            "indeterminate_attempts_allowed",
            "failed_child_rc_without_artifacts_may_retry",
            "complete_artifacts_without_terminal_may_recover",
            "global_runtime_path_claims_required",
            "runtime_path_overlap_allowed",
            "recovery_unknown_child_liveness_allowed",
        ):
            expected = field in {
                "one_adopted_attempt_per_post_repeat",
                "complete_artifacts_without_terminal_may_recover",
                "global_runtime_path_claims_required",
            }
            if raw.get(field) is not expected:
                raise ValueError(f"safe-loss execution claim policy mismatch: {field}")
        quiescence = raw.get("recovery_artifact_quiescence_seconds")
        if (
            isinstance(quiescence, bool)
            or not isinstance(quiescence, (int, float))
            or float(quiescence) < RECOVERY_ARTIFACT_QUIESCENCE_SECONDS
        ):
            raise ValueError("safe-loss recovery artifact quiescence policy mismatch")
        return {**raw, **{field: str(path) for field, path in resolved.items()}}

    anchor = (plan_path.parent / f".{plan_path.stem}.independent_plan_execution").resolve()
    return {
        "version": EXECUTION_CLAIM_VERSION,
        "anchor_dir": str(anchor),
        "persistent_plan_claim_json": str(anchor / "plan.claim.json"),
        "active_lock_file": str(anchor / "plan.active.lock"),
        "attempts_dir": str(anchor / "attempts"),
        "adoptions_dir": str(anchor / "adoptions"),
        "attempt_claim_pattern": "attempt_{index:03d}.claim.json",
        "attempt_terminal_receipt_pattern": "attempt_{index:03d}.terminal.json",
        "required_adopted_completion_count": len(runs),
        "one_adopted_attempt_per_post_repeat": True,
        "unrecorded_attempts_allowed": False,
        "indeterminate_attempts_allowed": False,
        "failed_child_rc_without_artifacts_may_retry": False,
        "complete_artifacts_without_terminal_may_recover": True,
        "global_runtime_path_claims_required": True,
        "runtime_path_overlap_allowed": False,
        "recovery_unknown_child_liveness_allowed": False,
        "recovery_artifact_quiescence_seconds": RECOVERY_ARTIFACT_QUIESCENCE_SECONDS,
    }


def _run_execution_paths(
    *,
    contract: dict[str, Any],
    run: dict[str, Any],
    index: int,
) -> dict[str, Path]:
    fallback_stem = _safe_stem(str(run.get("output_json") or ""), f"run_{index:03d}")
    raw_attempt_dir = run.get("attempt_dir")
    raw_adoption = run.get("adopted_completion_receipt_json")
    attempt_dir = (
        _resolve_path(raw_attempt_dir)
        if isinstance(raw_attempt_dir, str) and raw_attempt_dir.strip()
        else _resolve_path(contract["attempts_dir"]) / f"run_{index:03d}_{fallback_stem}"
    )
    adoption = (
        _resolve_path(raw_adoption)
        if isinstance(raw_adoption, str) and raw_adoption.strip()
        else _resolve_path(contract["adoptions_dir"]) / f"run_{index:03d}_{fallback_stem}.adopted.json"
    )
    attempts_root = _resolve_path(contract["attempts_dir"])
    adoptions_root = _resolve_path(contract["adoptions_dir"])
    if attempt_dir != attempts_root and attempts_root not in attempt_dir.parents:
        raise ValueError(f"planned_runs[{index}] attempt_dir escapes contract root")
    if adoption != adoptions_root and adoptions_root not in adoption.parents:
        raise ValueError(f"planned_runs[{index}] adoption receipt escapes contract root")
    return {"attempt_dir": attempt_dir, "adoption_receipt": adoption}


def _runtime_path_records(runs: list[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            raise ValueError(f"planned_runs[{index}] is not an object")
        paths = _run_artifact_paths(run, index=index)
        records.append(
            {
                "index": index,
                "post_id": str(run.get("post_id") or "").strip(),
                "repeat_index": run.get("repeat_index"),
                **{field: str(path) for field, path in paths.items()},
            }
        )
    _runtime_path_entries(records)
    return records


def _plan_claim_payload(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    runs: list[Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    plan_sha256 = _file_sha256(plan_path.resolve())
    judge_binding = plan.get("blind_judge_binding")
    runtime_records = _runtime_path_records(runs)
    stable = {
        "claim_type": "independent_plan_global_claim",
        "version": EXECUTION_CLAIM_VERSION,
        "plan_path": str(plan_path.resolve()),
        "plan_sha256": plan_sha256,
        "blind_judge_binding_canonical_sha256": _canonical_sha256(
            judge_binding if isinstance(judge_binding, dict) else {}
        ),
        "runtime_path_records_canonical_sha256": _canonical_sha256(runtime_records),
        "runtime_path_claim_version": RUNTIME_PATH_CLAIM_VERSION,
        "runtime_path_identity_policy": "resolve+os.path.normcase",
        "execution_claim_contract_canonical_sha256": _canonical_sha256(contract),
        "planned_run_count": len(runs),
    }
    return {**stable, "claim_contract_canonical_sha256": _canonical_sha256(stable)}


def _ensure_persistent_plan_claim(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        actual = _load_json(path)
        if actual != expected:
            raise ValueError("persistent plan claim mismatch")
        return actual
    _write_json_exclusive(path, expected)
    actual = _load_json(path)
    if actual != expected:
        raise ValueError("persistent plan claim readback mismatch")
    return actual


@contextmanager
def _active_plan_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"active plan lock already held: {path}") from exc
        yield handle
    finally:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def _run_artifact_paths(run: dict[str, Any], *, index: int) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for field in ("output_json", "checkpoint_jsonl", "manifest_json"):
        value = run.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"planned_runs[{index}] {field} missing or invalid")
        out[field] = _resolve_path(value)
    if len(set(out.values())) != len(out):
        raise ValueError(f"planned_runs[{index}] runtime artifact paths overlap")
    return out


def _runtime_path_identity(path: Path) -> str:
    """Return one platform-canonical identity for a planned runtime write path."""
    return os.path.normcase(str(path.resolve()))


def _runtime_path_entries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: dict[str, tuple[int, str]] = {}
    for record in records:
        index = record.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError("runtime path record index missing or invalid")
        for field in ("output_json", "checkpoint_jsonl", "manifest_json"):
            path = _resolve_path(record.get(field))
            identity = _runtime_path_identity(path)
            previous = seen.get(identity)
            if previous is not None:
                raise ValueError(
                    "run plan has duplicate runtime artifact paths: "
                    f"run[{previous[0]}].{previous[1]} and run[{index}].{field}"
                )
            seen[identity] = (index, field)
            entries.append(
                {
                    "run_index": index,
                    "post_id": str(record.get("post_id") or "").strip(),
                    "repeat_index": record.get("repeat_index"),
                    "field": field,
                    "path": path,
                    "identity": identity,
                    "identity_sha256": _sha256_bytes(identity.encode("utf-8")),
                }
            )
    return entries


def _planned_runtime_path_entries(runs: list[Any]) -> list[dict[str, Any]]:
    return _runtime_path_entries(_runtime_path_records(runs))


def _runtime_path_registry_paths(entry: dict[str, Any]) -> tuple[Path, Path]:
    runtime_path = entry["path"]
    digest = str(entry["identity_sha256"])
    registry_dir = runtime_path.parent / ".independent_plan_runtime_claims"
    return registry_dir / f"{digest}.active.lock", registry_dir / f"{digest}.claim.json"


@contextmanager
def _active_runtime_path_locks(entries: list[dict[str, Any]]):
    lock_paths = sorted(
        (_runtime_path_registry_paths(entry)[0] for entry in entries),
        key=lambda path: _runtime_path_identity(path),
    )
    if len(lock_paths) != len(set(map(_runtime_path_identity, lock_paths))):
        raise ValueError("runtime path lock identities overlap")
    with ExitStack() as stack:
        for lock_path in lock_paths:
            try:
                stack.enter_context(_active_plan_lock(lock_path))
            except RuntimeError as exc:
                raise RuntimeError(
                    f"active runtime path lock already held: {lock_path}"
                ) from exc
        yield


def _runtime_path_claim_payload(
    *, entry: dict[str, Any], plan_claim: dict[str, Any]
) -> dict[str, Any]:
    stable = {
        "claim_type": "independent_plan_runtime_path_claim",
        "version": RUNTIME_PATH_CLAIM_VERSION,
        "runtime_path": str(entry["path"]),
        "runtime_path_identity": entry["identity"],
        "runtime_path_identity_sha256": entry["identity_sha256"],
        "runtime_field": entry["field"],
        "run_index": entry["run_index"],
        "post_id": entry["post_id"],
        "repeat_index": entry["repeat_index"],
        "owner_plan_path": plan_claim["plan_path"],
        "owner_plan_sha256": plan_claim["plan_sha256"],
        "owner_plan_claim_contract_sha256": plan_claim[
            "claim_contract_canonical_sha256"
        ],
    }
    return {
        **stable,
        "runtime_path_claim_canonical_sha256": _canonical_sha256(stable),
    }


def _ensure_runtime_path_claims(
    entries: list[dict[str, Any]], *, plan_claim: dict[str, Any]
) -> list[Path]:
    claim_paths: list[Path] = []
    for entry in entries:
        _lock_path, claim_path = _runtime_path_registry_paths(entry)
        expected = _runtime_path_claim_payload(entry=entry, plan_claim=plan_claim)
        if claim_path.exists():
            try:
                actual = _load_json(claim_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"persistent runtime path claim unreadable: {entry['path']}"
                ) from exc
            if actual != expected:
                raise ValueError(
                    f"persistent runtime path claim mismatch: {entry['path']}"
                )
        else:
            _write_json_exclusive(claim_path, expected)
            if _load_json(claim_path) != expected:
                raise ValueError(
                    f"persistent runtime path claim readback mismatch: {entry['path']}"
                )
        claim_paths.append(claim_path)
    return claim_paths


def _validate_runtime_path_claims(
    entries: list[dict[str, Any]], *, plan_claim: dict[str, Any]
) -> list[Path]:
    claim_paths: list[Path] = []
    for entry in entries:
        _lock_path, claim_path = _runtime_path_registry_paths(entry)
        if not claim_path.is_file():
            raise ValueError(f"persistent runtime path claim missing: {entry['path']}")
        expected = _runtime_path_claim_payload(entry=entry, plan_claim=plan_claim)
        if _load_json(claim_path) != expected:
            raise ValueError(f"persistent runtime path claim mismatch: {entry['path']}")
        claim_paths.append(claim_path)
    return claim_paths


def _validate_run_input_binding(run: dict[str, Any], *, index: int) -> None:
    input_value = run.get("input_jsonl")
    input_sha256 = run.get("input_sha256")
    if input_value in (None, "") and input_sha256 in (None, ""):
        return
    if not isinstance(input_value, str) or not input_value.strip():
        raise ValueError(f"planned_runs[{index}] input_jsonl missing or invalid")
    if not isinstance(input_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", input_sha256) is None:
        raise ValueError(f"planned_runs[{index}] input_sha256 missing or invalid")
    input_path = _resolve_path(input_value)
    if not input_path.is_file():
        raise ValueError(f"planned_runs[{index}] input_jsonl not found")
    if _file_sha256(input_path) != input_sha256:
        raise ValueError(f"planned_runs[{index}] input_jsonl byte sha256 mismatch")
    lines = [line for line in input_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError(f"planned_runs[{index}] input_jsonl must contain exactly one row")
    row = json.loads(lines[0])
    if not isinstance(row, dict) or str(row.get("post_id") or "").strip() != str(
        run.get("post_id") or ""
    ).strip():
        raise ValueError(f"planned_runs[{index}] input_jsonl post_id mismatch")


def _result_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"unsupported result payload: {path}")


def _checkpoint_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"checkpoint row is not an object: {path}:{line_no}")
        rows.append(row)
    return rows


def _validate_complete_run_artifacts(
    run: dict[str, Any],
    *,
    index: int,
    paths: dict[str, Path],
) -> dict[str, Any]:
    missing = [field for field, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError(f"planned_runs[{index}] incomplete existing artifacts: missing={missing}")
    manifest = _load_json(paths["manifest_json"])
    expected_manifest = {
        "input_post_count": 1,
        "completed_count": 1,
        "flushed_count": 1,
        "pending_count": 0,
        "failed_count": 0,
    }
    for field, expected in expected_manifest.items():
        value = manifest.get(field)
        if type(value) is not type(expected) or value != expected:
            raise ValueError(
                f"planned_runs[{index}] resume manifest {field} mismatch: {value!r}"
            )
    if _resolve_path(manifest.get("output_file")) != paths["output_json"]:
        raise ValueError(f"planned_runs[{index}] resume manifest output_file mismatch")
    manifest_checkpoint = manifest.get("checkpoint_jsonl")
    if not isinstance(manifest_checkpoint, str) or _resolve_path(manifest_checkpoint) != paths[
        "checkpoint_jsonl"
    ]:
        raise ValueError(f"planned_runs[{index}] resume manifest checkpoint_jsonl mismatch")

    pid = str(run.get("post_id") or "").strip()
    result_rows = _result_rows(paths["output_json"])
    if len(result_rows) != 1:
        raise ValueError(f"planned_runs[{index}] resume result row count is not one")
    result = result_rows[0].get("result")
    if not isinstance(result, dict):
        result = result_rows[0]
    if str(result.get("post_id") or "").strip() != pid:
        raise ValueError(f"planned_runs[{index}] resume result post_id mismatch")
    checkpoint_rows = _checkpoint_rows(paths["checkpoint_jsonl"])
    if len(checkpoint_rows) != 1:
        raise ValueError(f"planned_runs[{index}] resume checkpoint row count is not one")
    if str(checkpoint_rows[0].get("post_id") or "").strip() != pid:
        raise ValueError(f"planned_runs[{index}] resume checkpoint post_id mismatch")
    if checkpoint_rows[0].get("status") != "completed":
        raise ValueError(f"planned_runs[{index}] resume checkpoint status is not completed")

    manifest_run_id = str(manifest.get("run_id") or "").strip()
    run_meta = result.get("run_meta") if isinstance(result.get("run_meta"), dict) else {}
    if not manifest_run_id or str(run_meta.get("run_id") or "").strip() != manifest_run_id:
        raise ValueError(f"planned_runs[{index}] resume run_id binding mismatch")
    return {
        "index": index,
        "post_id": pid,
        "repeat_index": run.get("repeat_index"),
        "run_id": manifest_run_id,
        "output_json": str(paths["output_json"]),
        "output_sha256": _file_sha256(paths["output_json"]),
        "checkpoint_sha256": _file_sha256(paths["checkpoint_jsonl"]),
        "manifest_sha256": _file_sha256(paths["manifest_json"]),
        "runtime_counts": expected_manifest,
        "gate": "SKIP_VERIFIED_COMPLETE",
    }


def _artifact_presence(paths: dict[str, Path]) -> dict[str, bool]:
    return {field: path.is_file() for field, path in paths.items()}


def _attempt_claim_payload(
    *,
    run: dict[str, Any],
    index: int,
    attempt_index: int,
    plan_sha256: str,
    global_claim_sha256: str,
    artifact_paths: dict[str, Path],
) -> dict[str, Any]:
    stable = {
        "claim_type": "independent_plan_run_attempt_claim",
        "version": EXECUTION_CLAIM_VERSION,
        "plan_sha256": plan_sha256,
        "global_plan_claim_sha256": global_claim_sha256,
        "run_index": index,
        "post_id": str(run.get("post_id") or "").strip(),
        "repeat_index": run.get("repeat_index"),
        "attempt_index": attempt_index,
        "runtime_paths": {field: str(path) for field, path in artifact_paths.items()},
        "runtime_paths_canonical_sha256": _canonical_sha256(
            {field: str(path) for field, path in artifact_paths.items()}
        ),
        "input_sha256": run.get("input_sha256"),
        "command_argv_canonical_sha256": _canonical_sha256(run.get("command_argv")),
    }
    return {**stable, "attempt_contract_canonical_sha256": _canonical_sha256(stable)}


def _process_creation_token(proc: subprocess.Popen[Any]) -> str:
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            ok = ctypes.windll.kernel32.GetProcessTimes(
                wintypes.HANDLE(int(proc._handle)),
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            )
            if ok:
                value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
                return f"windows-filetime:{value}"
        except (AttributeError, OSError, TypeError, ValueError):
            pass
    proc_stat = Path(f"/proc/{proc.pid}/stat")
    try:
        fields = proc_stat.read_text(encoding="utf-8").split()
        if len(fields) > 21:
            return f"proc-start-ticks:{fields[21]}"
    except OSError:
        pass
    return f"pid-observed:{proc.pid}:{time.time_ns()}"


def _child_started_receipt_payload(
    *,
    claim_path: Path,
    claim: dict[str, Any],
    child_pid: int,
    process_creation_token: str,
) -> dict[str, Any]:
    stable = {
        "receipt_type": "independent_plan_run_child_started_receipt",
        "version": EXECUTION_CLAIM_VERSION,
        "plan_sha256": claim["plan_sha256"],
        "global_plan_claim_sha256": claim["global_plan_claim_sha256"],
        "run_index": claim["run_index"],
        "post_id": claim["post_id"],
        "repeat_index": claim["repeat_index"],
        "attempt_index": claim["attempt_index"],
        "attempt_claim_path": str(claim_path),
        "attempt_claim_sha256": _file_sha256(claim_path),
        "child_pid": child_pid,
        "process_creation_token": process_creation_token,
    }
    return {**stable, "child_started_contract_canonical_sha256": _canonical_sha256(stable)}


def _validate_child_started_receipt(
    path: Path,
    *,
    claim_path: Path,
    claim: dict[str, Any],
    run_index: int,
) -> dict[str, Any]:
    receipt = _load_json(path)
    common = {
        "receipt_type": "independent_plan_run_child_started_receipt",
        "version": EXECUTION_CLAIM_VERSION,
        "plan_sha256": claim["plan_sha256"],
        "global_plan_claim_sha256": claim["global_plan_claim_sha256"],
        "run_index": claim["run_index"],
        "post_id": claim["post_id"],
        "repeat_index": claim["repeat_index"],
        "attempt_index": claim["attempt_index"],
        "attempt_claim_path": str(claim_path),
        "attempt_claim_sha256": _file_sha256(claim_path),
    }
    for field, expected in common.items():
        if receipt.get(field) != expected or type(receipt.get(field)) is not type(expected):
            raise ValueError(f"planned_runs[{run_index}] child_started {field} mismatch")
    if isinstance(receipt.get("child_pid"), bool) or not isinstance(receipt.get("child_pid"), int):
        raise ValueError(f"planned_runs[{run_index}] child_started pid invalid")
    token = receipt.get("process_creation_token")
    if not isinstance(token, str) or not token.strip():
        raise ValueError(f"planned_runs[{run_index}] child_started creation token invalid")
    stable = dict(receipt)
    digest = stable.pop("child_started_contract_canonical_sha256", None)
    if digest != _canonical_sha256(stable):
        raise ValueError(f"planned_runs[{run_index}] child_started self binding mismatch")
    return receipt


def _query_windows_process(pid: int) -> tuple[str, str | None]:
    """Query one Windows PID without treating access/query failures as exit."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        ctypes.set_last_error(0)
        process = kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            # ERROR_INVALID_PARAMETER is the documented no-such-process result.
            if ctypes.get_last_error() == 87:
                return CHILD_LIVENESS_EXITED, None
            return CHILD_LIVENESS_UNKNOWN, None
        try:
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                process,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                return CHILD_LIVENESS_UNKNOWN, None
            value = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
            observed_token = f"windows-filetime:{value}"
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                return CHILD_LIVENESS_UNKNOWN, observed_token
            state = (
                CHILD_LIVENESS_ACTIVE
                if exit_code.value == 259
                else CHILD_LIVENESS_EXITED
            )
            return state, observed_token
        finally:
            kernel32.CloseHandle(process)
    except (AttributeError, OSError, TypeError, ValueError):
        return CHILD_LIVENESS_UNKNOWN, None


def _recorded_child_liveness(child_started: dict[str, Any]) -> str:
    pid = child_started.get("child_pid")
    token = str(child_started.get("process_creation_token") or "")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return CHILD_LIVENESS_UNKNOWN
    if os.name == "nt":
        if not token.startswith("windows-filetime:"):
            return CHILD_LIVENESS_UNKNOWN
        state, observed_token = _query_windows_process(pid)
        if state == CHILD_LIVENESS_EXITED and observed_token is None:
            return CHILD_LIVENESS_EXITED
        if state == CHILD_LIVENESS_UNKNOWN or observed_token != token:
            return CHILD_LIVENESS_UNKNOWN
        return state
    if not token.startswith("proc-start-ticks:"):
        return CHILD_LIVENESS_UNKNOWN
    proc_stat = Path(f"/proc/{pid}/stat")
    if not proc_stat.is_file():
        return CHILD_LIVENESS_EXITED
    try:
        fields = proc_stat.read_text(encoding="utf-8").split()
    except OSError:
        return CHILD_LIVENESS_UNKNOWN
    if len(fields) > 21:
        return (
            CHILD_LIVENESS_ACTIVE
            if token == f"proc-start-ticks:{fields[21]}"
            else CHILD_LIVENESS_UNKNOWN
        )
    return CHILD_LIVENESS_UNKNOWN


def _recorded_child_is_still_active(child_started: dict[str, Any]) -> bool:
    """Compatibility wrapper; unknown is intentionally treated as active."""
    return _recorded_child_liveness(child_started) != CHILD_LIVENESS_EXITED


def _assert_artifacts_stable(paths: dict[str, Path], *, run_index: int) -> None:
    first = {
        field: (path.stat().st_size, path.stat().st_mtime_ns, _file_sha256(path))
        for field, path in paths.items()
    }
    time.sleep(RECOVERY_ARTIFACT_QUIESCENCE_SECONDS)
    second = {
        field: (path.stat().st_size, path.stat().st_mtime_ns, _file_sha256(path))
        for field, path in paths.items()
    }
    if first != second:
        raise ValueError(f"planned_runs[{run_index}] recovery artifacts are still changing")


def _attempt_file_paths(attempt_dir: Path, attempt_index: int) -> tuple[Path, Path]:
    return (
        attempt_dir / f"attempt_{attempt_index:03d}.claim.json",
        attempt_dir / f"attempt_{attempt_index:03d}.terminal.json",
    )


def _child_started_path(attempt_dir: Path, attempt_index: int) -> Path:
    return attempt_dir / f"attempt_{attempt_index:03d}.child_started.json"


def _scan_attempt_files(
    attempt_dir: Path,
) -> tuple[dict[int, Path], dict[int, Path], dict[int, Path], list[str]]:
    claims: dict[int, Path] = {}
    child_started: dict[int, Path] = {}
    terminals: dict[int, Path] = {}
    issues: list[str] = []
    if not attempt_dir.exists():
        return claims, child_started, terminals, issues
    for path in attempt_dir.iterdir():
        if not path.is_file():
            continue
        match = re.fullmatch(
            r"attempt_(\d{3})\.(claim|child_started|terminal)\.json", path.name
        )
        if match is None:
            issues.append(f"unexpected_attempt_artifact:{path.name}")
            continue
        attempt_index = int(match.group(1))
        owner = {
            "claim": claims,
            "child_started": child_started,
            "terminal": terminals,
        }[match.group(2)]
        if attempt_index in owner:
            issues.append(f"duplicate_attempt_artifact:{path.name}")
        owner[attempt_index] = path
    expected_indexes = list(range(1, max(claims.keys() | terminals.keys(), default=0) + 1))
    if sorted(claims) != expected_indexes:
        issues.append("attempt_claim_indexes_not_contiguous_from_one")
    terminal_without_claim = sorted(set(terminals) - set(claims))
    if terminal_without_claim:
        issues.append(f"terminal_without_claim:{terminal_without_claim}")
    child_without_claim = sorted(set(child_started) - set(claims))
    if child_without_claim:
        issues.append(f"child_started_without_claim:{child_without_claim}")
    return claims, child_started, terminals, issues


def _validate_attempt_claim(
    path: Path,
    *,
    expected: dict[str, Any],
    run_index: int,
) -> dict[str, Any]:
    actual = _load_json(path)
    if actual != expected:
        raise ValueError(f"planned_runs[{run_index}] attempt claim mismatch: {path}")
    return actual


def _terminal_receipt_payload(
    *,
    status: str,
    claim_path: Path,
    claim: dict[str, Any],
    child_started_path: Path,
    child_started: dict[str, Any],
    child_returncode: int | None,
    artifact_presence: dict[str, bool],
    artifact_binding: dict[str, Any] | None,
) -> dict[str, Any]:
    stable = {
        "receipt_type": "independent_plan_run_attempt_terminal_receipt",
        "version": EXECUTION_CLAIM_VERSION,
        "status": status,
        "plan_sha256": claim["plan_sha256"],
        "global_plan_claim_sha256": claim["global_plan_claim_sha256"],
        "run_index": claim["run_index"],
        "post_id": claim["post_id"],
        "repeat_index": claim["repeat_index"],
        "attempt_index": claim["attempt_index"],
        "attempt_claim_path": str(claim_path),
        "attempt_claim_sha256": _file_sha256(claim_path),
        "child_started_receipt_path": str(child_started_path),
        "child_started_receipt_sha256": _file_sha256(child_started_path),
        "child_pid": child_started["child_pid"],
        "process_creation_token": child_started["process_creation_token"],
        "child_returncode": child_returncode,
        "artifact_presence": artifact_presence,
        "artifact_binding": artifact_binding,
    }
    return {**stable, "terminal_contract_canonical_sha256": _canonical_sha256(stable)}


def _validate_terminal_receipt(
    path: Path,
    *,
    claim_path: Path,
    claim: dict[str, Any],
    child_started_path: Path,
    child_started: dict[str, Any],
    run_index: int,
) -> dict[str, Any]:
    terminal = _load_json(path)
    common = {
        "receipt_type": "independent_plan_run_attempt_terminal_receipt",
        "version": EXECUTION_CLAIM_VERSION,
        "plan_sha256": claim["plan_sha256"],
        "global_plan_claim_sha256": claim["global_plan_claim_sha256"],
        "run_index": claim["run_index"],
        "post_id": claim["post_id"],
        "repeat_index": claim["repeat_index"],
        "attempt_index": claim["attempt_index"],
        "attempt_claim_path": str(claim_path),
        "attempt_claim_sha256": _file_sha256(claim_path),
        "child_started_receipt_path": str(child_started_path),
        "child_started_receipt_sha256": _file_sha256(child_started_path),
        "child_pid": child_started["child_pid"],
        "process_creation_token": child_started["process_creation_token"],
    }
    for field, expected in common.items():
        if terminal.get(field) != expected or type(terminal.get(field)) is not type(expected):
            raise ValueError(f"planned_runs[{run_index}] terminal {field} mismatch")
    stable = dict(terminal)
    recorded_digest = stable.pop("terminal_contract_canonical_sha256", None)
    if recorded_digest != _canonical_sha256(stable):
        raise ValueError(f"planned_runs[{run_index}] terminal self binding mismatch")
    status = terminal.get("status")
    presence = terminal.get("artifact_presence")
    if not isinstance(presence, dict) or set(presence) != {
        "output_json",
        "checkpoint_jsonl",
        "manifest_json",
    }:
        raise ValueError(f"planned_runs[{run_index}] terminal artifact presence invalid")
    if status == "FAILED_CHILD_RC":
        rc = terminal.get("child_returncode")
        if isinstance(rc, bool) or not isinstance(rc, int) or rc == 0:
            raise ValueError(f"planned_runs[{run_index}] failed terminal rc invalid")
        if any(presence.values()) or terminal.get("artifact_binding") is not None:
            raise ValueError(f"planned_runs[{run_index}] failed terminal retained artifacts")
    elif status in {"FAILED_CHILD_RC_DIRTY", "FAILED_ARTIFACT_VALIDATION"}:
        rc = terminal.get("child_returncode")
        if status == "FAILED_CHILD_RC_DIRTY" and (
            isinstance(rc, bool) or not isinstance(rc, int) or rc == 0
        ):
            raise ValueError(f"planned_runs[{run_index}] dirty failed terminal rc invalid")
        if status == "FAILED_ARTIFACT_VALIDATION" and rc != 0:
            raise ValueError(f"planned_runs[{run_index}] artifact validation terminal rc mismatch")
        if terminal.get("artifact_binding") is not None:
            raise ValueError(f"planned_runs[{run_index}] failed terminal cannot bind artifacts")
    elif status in {"COMPLETE_VERIFIED", "RECOVERED_COMPLETE"}:
        if not all(presence.values()) or not isinstance(terminal.get("artifact_binding"), dict):
            raise ValueError(f"planned_runs[{run_index}] complete terminal binding invalid")
        if status == "COMPLETE_VERIFIED" and terminal.get("child_returncode") != 0:
            raise ValueError(f"planned_runs[{run_index}] complete terminal rc mismatch")
        if status == "RECOVERED_COMPLETE" and terminal.get("child_returncode") is not None:
            raise ValueError(f"planned_runs[{run_index}] recovered terminal rc must be unknown")
    else:
        raise ValueError(f"planned_runs[{run_index}] terminal status invalid: {status}")
    return terminal


def _adoption_receipt_payload(
    *,
    terminal_path: Path,
    terminal: dict[str, Any],
) -> dict[str, Any]:
    stable = {
        "receipt_type": "independent_plan_run_adopted_completion_receipt",
        "version": EXECUTION_CLAIM_VERSION,
        "gate": "ADOPTED_COMPLETE",
        "plan_sha256": terminal["plan_sha256"],
        "global_plan_claim_sha256": terminal["global_plan_claim_sha256"],
        "run_index": terminal["run_index"],
        "post_id": terminal["post_id"],
        "repeat_index": terminal["repeat_index"],
        "adopted_attempt_index": terminal["attempt_index"],
        "terminal_receipt_path": str(terminal_path),
        "terminal_receipt_sha256": _file_sha256(terminal_path),
        "artifact_binding": terminal["artifact_binding"],
    }
    return {**stable, "adoption_contract_canonical_sha256": _canonical_sha256(stable)}


def _validate_adoption_receipt(
    path: Path,
    *,
    terminal_path: Path,
    terminal: dict[str, Any],
    run_index: int,
) -> dict[str, Any]:
    adoption = _load_json(path)
    expected = _adoption_receipt_payload(terminal_path=terminal_path, terminal=terminal)
    if adoption != expected:
        raise ValueError(f"planned_runs[{run_index}] adoption receipt mismatch")
    return adoption


def _write_adoption_exclusive(
    path: Path,
    *,
    terminal_path: Path,
    terminal: dict[str, Any],
) -> dict[str, Any]:
    payload = _adoption_receipt_payload(terminal_path=terminal_path, terminal=terminal)
    _write_json_exclusive(path, payload)
    return payload


def _completion_receipt_path(log_dir: Path, run: dict[str, Any], *, index: int) -> Path:
    stem = _safe_stem(str(run.get("output_json") or ""), f"run_{index:03d}")
    return log_dir / f"run_{index:03d}_{stem}.completion_receipt.json"


def _validate_completion_receipt(
    path: Path,
    *,
    current_binding: dict[str, Any],
    plan_sha256: str,
    index: int,
) -> None:
    if not path.is_file():
        raise ValueError(f"planned_runs[{index}] immutable completion receipt missing")
    receipt = _load_json(path)
    if receipt.get("receipt_type") != "independent_plan_run_completion_receipt":
        raise ValueError(f"planned_runs[{index}] completion receipt type mismatch")
    if receipt.get("gate") != "COMPLETE_VERIFIED":
        raise ValueError(f"planned_runs[{index}] completion receipt gate mismatch")
    if receipt.get("exclusive_create") is not True:
        raise ValueError(f"planned_runs[{index}] completion receipt is not exclusive")
    if receipt.get("plan_sha256") != plan_sha256:
        raise ValueError(f"planned_runs[{index}] completion receipt plan binding mismatch")
    if receipt.get("artifact_binding") != current_binding:
        raise ValueError(f"planned_runs[{index}] completion receipt artifact hash mismatch")


def _preflight_run_artifacts(
    runs: list[Any],
    *,
    skip_existing: bool,
    completion_receipt_dir: Path | None = None,
    plan_sha256: str | None = None,
) -> dict[int, dict[str, Any]]:
    all_paths: list[Path] = []
    skip_receipts: dict[int, dict[str, Any]] = {}
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            raise ValueError(f"planned_runs[{index}] is not an object")
        paths = _run_artifact_paths(run, index=index)
        all_paths.extend(paths.values())
        existing = {field: path.exists() for field, path in paths.items()}
        if not skip_existing:
            if any(existing.values()):
                present = [field for field, exists in existing.items() if exists]
                raise FileExistsError(
                    f"planned_runs[{index}] first execution refuses existing artifacts: {present}"
                )
            continue
        if not any(existing.values()):
            continue
        if not all(existing.values()):
            present = [field for field, exists in existing.items() if exists]
            missing = [field for field, exists in existing.items() if not exists]
            raise ValueError(
                f"planned_runs[{index}] incomplete existing artifacts: present={present}, missing={missing}"
            )
        artifact_binding = _validate_complete_run_artifacts(
            run, index=index, paths=paths
        )
        if completion_receipt_dir is not None:
            if not plan_sha256:
                raise ValueError("resume completion receipt validation requires plan sha256")
            _validate_completion_receipt(
                _completion_receipt_path(completion_receipt_dir, run, index=index),
                current_binding=artifact_binding,
                plan_sha256=plan_sha256,
                index=index,
            )
        skip_receipts[index] = artifact_binding
    if len(all_paths) != len(set(all_paths)):
        raise ValueError("run plan has duplicate runtime artifact paths")
    return skip_receipts


def _validated_attempt_history(
    *,
    run: dict[str, Any],
    run_index: int,
    execution_paths: dict[str, Path],
    artifact_paths: dict[str, Path],
    plan_sha256: str,
    global_claim_sha256: str,
) -> tuple[
    dict[int, tuple[Path, dict[str, Any]]],
    dict[int, tuple[Path, dict[str, Any]]],
    dict[int, tuple[Path, dict[str, Any]]],
    list[str],
]:
    claim_paths, child_paths, terminal_paths, issues = _scan_attempt_files(
        execution_paths["attempt_dir"]
    )
    claims: dict[int, tuple[Path, dict[str, Any]]] = {}
    children: dict[int, tuple[Path, dict[str, Any]]] = {}
    terminals: dict[int, tuple[Path, dict[str, Any]]] = {}
    for attempt_index, claim_path in sorted(claim_paths.items()):
        expected = _attempt_claim_payload(
            run=run,
            index=run_index,
            attempt_index=attempt_index,
            plan_sha256=plan_sha256,
            global_claim_sha256=global_claim_sha256,
            artifact_paths=artifact_paths,
        )
        try:
            claim = _validate_attempt_claim(
                claim_path, expected=expected, run_index=run_index
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"attempt_{attempt_index:03d}_claim_invalid:{exc}")
            continue
        claims[attempt_index] = (claim_path, claim)
        child_path = child_paths.get(attempt_index)
        child: dict[str, Any] | None = None
        if child_path is not None:
            try:
                child = _validate_child_started_receipt(
                    child_path,
                    claim_path=claim_path,
                    claim=claim,
                    run_index=run_index,
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                issues.append(f"attempt_{attempt_index:03d}_child_started_invalid:{exc}")
            else:
                children[attempt_index] = (child_path, child)
        terminal_path = terminal_paths.get(attempt_index)
        if terminal_path is None:
            continue
        if child_path is None or child is None:
            issues.append(f"attempt_{attempt_index:03d}_terminal_without_valid_child_started")
            continue
        try:
            terminal = _validate_terminal_receipt(
                terminal_path,
                claim_path=claim_path,
                claim=claim,
                child_started_path=child_path,
                child_started=child,
                run_index=run_index,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"attempt_{attempt_index:03d}_terminal_invalid:{exc}")
            continue
        terminals[attempt_index] = (terminal_path, terminal)
    return claims, children, terminals, issues


def _prepare_run_attempt_states(
    *,
    plan: dict[str, Any],
    runs: list[Any],
    contract: dict[str, Any],
    plan_sha256: str,
    global_claim_path: Path,
    skip_existing: bool,
) -> dict[int, dict[str, Any]]:
    global_claim_sha256 = _file_sha256(global_claim_path)
    states: dict[int, dict[str, Any]] = {}
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            raise ValueError(f"planned_runs[{index}] is not an object")
        _validate_run_input_binding(run, index=index)
        artifact_paths = _run_artifact_paths(run, index=index)
        execution_paths = _run_execution_paths(contract=contract, run=run, index=index)
        presence = _artifact_presence(artifact_paths)
        claims, children, terminals, history_issues = _validated_attempt_history(
            run=run,
            run_index=index,
            execution_paths=execution_paths,
            artifact_paths=artifact_paths,
            plan_sha256=plan_sha256,
            global_claim_sha256=global_claim_sha256,
        )
        if history_issues:
            raise ValueError(f"planned_runs[{index}] attempt history invalid: {history_issues}")
        adoption_path = execution_paths["adoption_receipt"]

        if not skip_existing:
            if claims or terminals or adoption_path.exists() or any(presence.values()):
                raise FileExistsError(
                    f"planned_runs[{index}] first execution refuses prior claim/receipt/runtime artifacts"
                )
            states[index] = {
                "action": "RUN",
                "next_attempt_index": 1,
                "artifact_paths": artifact_paths,
                "execution_paths": execution_paths,
            }
            continue

        if adoption_path.exists():
            complete_indexes = [
                attempt_index
                for attempt_index, (_path, terminal) in terminals.items()
                if terminal.get("status") in {"COMPLETE_VERIFIED", "RECOVERED_COMPLETE"}
            ]
            if len(complete_indexes) != 1:
                raise ValueError(f"planned_runs[{index}] adopted receipt has no unique complete attempt")
            adopted_index = complete_indexes[0]
            terminal_path, terminal = terminals[adopted_index]
            current_binding = _validate_complete_run_artifacts(
                run, index=index, paths=artifact_paths
            )
            if terminal.get("artifact_binding") != current_binding:
                raise ValueError(f"planned_runs[{index}] adopted artifact hash mismatch")
            adoption = _validate_adoption_receipt(
                adoption_path,
                terminal_path=terminal_path,
                terminal=terminal,
                run_index=index,
            )
            if any(attempt_index > adopted_index for attempt_index in claims):
                raise ValueError(f"planned_runs[{index}] attempt exists after adoption")
            states[index] = {
                "action": "SKIP_ADOPTED",
                "artifact_binding": current_binding,
                "adoption": adoption,
                "artifact_paths": artifact_paths,
                "execution_paths": execution_paths,
            }
            continue

        if not claims:
            if any(presence.values()):
                raise ValueError(f"planned_runs[{index}] runtime artifacts exist without attempt claim")
            states[index] = {
                "action": "RUN",
                "next_attempt_index": 1,
                "artifact_paths": artifact_paths,
                "execution_paths": execution_paths,
            }
            continue

        latest_index = max(claims)
        if latest_index not in terminals:
            if all(presence.values()):
                if latest_index not in children:
                    raise ValueError(
                        f"planned_runs[{index}] complete artifacts lack child_started receipt"
                    )
                current_binding = _validate_complete_run_artifacts(
                    run, index=index, paths=artifact_paths
                )
                claim_path, claim = claims[latest_index]
                child_path, child_started = children[latest_index]
                child_liveness = _recorded_child_liveness(child_started)
                if child_liveness != CHILD_LIVENESS_EXITED:
                    raise ValueError(
                        f"planned_runs[{index}] recorded child liveness is "
                        f"{child_liveness}; recovery forbidden"
                    )
                _assert_artifacts_stable(artifact_paths, run_index=index)
                terminal_path = _attempt_file_paths(
                    execution_paths["attempt_dir"], latest_index
                )[1]
                terminal = _terminal_receipt_payload(
                    status="RECOVERED_COMPLETE",
                    claim_path=claim_path,
                    claim=claim,
                    child_started_path=child_path,
                    child_started=child_started,
                    child_returncode=None,
                    artifact_presence=presence,
                    artifact_binding=current_binding,
                )
                _write_json_exclusive(terminal_path, terminal)
                adoption = _write_adoption_exclusive(
                    adoption_path,
                    terminal_path=terminal_path,
                    terminal=terminal,
                )
                states[index] = {
                    "action": "SKIP_RECOVERED",
                    "artifact_binding": current_binding,
                    "adoption": adoption,
                    "artifact_paths": artifact_paths,
                    "execution_paths": execution_paths,
                }
                continue
            raise ValueError(
                f"planned_runs[{index}] INDETERMINATE attempt claim without terminal receipt"
            )

        complete_indexes = [
            attempt_index
            for attempt_index, (_path, terminal) in terminals.items()
            if terminal.get("status") in {"COMPLETE_VERIFIED", "RECOVERED_COMPLETE"}
        ]
        if len(complete_indexes) > 1:
            raise ValueError(f"planned_runs[{index}] duplicate complete attempts")
        if len(complete_indexes) == 1:
            adopted_index = complete_indexes[0]
            terminal_path, terminal = terminals[adopted_index]
            if not all(presence.values()):
                raise ValueError(f"planned_runs[{index}] complete terminal artifacts missing")
            current_binding = _validate_complete_run_artifacts(
                run, index=index, paths=artifact_paths
            )
            if terminal.get("artifact_binding") != current_binding:
                raise ValueError(f"planned_runs[{index}] complete terminal artifact hash mismatch")
            adoption = _write_adoption_exclusive(
                adoption_path,
                terminal_path=terminal_path,
                terminal=terminal,
            )
            states[index] = {
                "action": "SKIP_RECOVERED_ADOPTION",
                "artifact_binding": current_binding,
                "adoption": adoption,
                "artifact_paths": artifact_paths,
                "execution_paths": execution_paths,
            }
            continue

        if any(presence.values()):
            raise ValueError(f"planned_runs[{index}] failed attempts retained runtime artifacts")
        raise ValueError(f"planned_runs[{index}] terminal failure is final and not retryable")
    return states


def audit_plan_execution_adoption_contract(
    *,
    plan_path: Path,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = plan if isinstance(plan, dict) else _load_json(plan_path)
    runs = plan.get("planned_runs")
    report: dict[str, Any] = {
        "report_type": "independent_plan_execution_adoption_audit",
        "gate": "NO-GO",
        "plan": str(plan_path),
        "issues": [],
        "runs": [],
    }
    issues: list[str] = report["issues"]
    if not isinstance(runs, list):
        issues.append("planned_runs_missing_or_invalid")
        return report
    try:
        _validate_plan_self_binding(plan)
        _validate_safe_loss_blind_judge_binding(plan)
        contract = _execution_claim_contract(plan_path=plan_path, plan=plan, runs=runs)
        claim_path = _resolve_path(contract["persistent_plan_claim_json"])
        expected_claim = _plan_claim_payload(
            plan_path=plan_path, plan=plan, runs=runs, contract=contract
        )
        if not claim_path.is_file():
            raise ValueError("persistent plan claim missing")
        claim = _load_json(claim_path)
        if claim != expected_claim:
            raise ValueError("persistent plan claim mismatch")
        runtime_entries = _planned_runtime_path_entries(runs)
        runtime_claim_paths = _validate_runtime_path_claims(
            runtime_entries, plan_claim=expected_claim
        )
        global_claim_sha256 = _file_sha256(claim_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"global_claim_invalid:{type(exc).__name__}:{exc}")
        return report

    adopted_pairs: list[tuple[str, Any]] = []
    total_claims = 0
    total_child_started = 0
    total_failed = 0
    total_indeterminate = 0
    for index, run in enumerate(runs, start=1):
        run_issues: list[str] = []
        if not isinstance(run, dict):
            issues.append(f"run[{index}]:not_object")
            continue
        artifact_paths = _run_artifact_paths(run, index=index)
        execution_paths = _run_execution_paths(contract=contract, run=run, index=index)
        claims, children, terminals, history_issues = _validated_attempt_history(
            run=run,
            run_index=index,
            execution_paths=execution_paths,
            artifact_paths=artifact_paths,
            plan_sha256=expected_claim["plan_sha256"],
            global_claim_sha256=global_claim_sha256,
        )
        total_claims += len(claims)
        total_child_started += len(children)
        run_issues.extend(history_issues)
        indeterminate = sorted(set(claims) - set(terminals))
        total_indeterminate += len(indeterminate)
        if indeterminate:
            run_issues.append(f"indeterminate_attempts:{indeterminate}")
        if len(claims) != 1:
            run_issues.append(f"attempt_claim_count_not_one:{len(claims)}")
        if len(children) != 1:
            run_issues.append(f"child_started_count_not_one:{len(children)}")
        failed_indexes = [
            idx
            for idx, (_path, terminal) in terminals.items()
            if str(terminal.get("status") or "").startswith("FAILED_")
        ]
        total_failed += len(failed_indexes)
        unsafe_failed_indexes = [
            idx
            for idx in failed_indexes
            if terminals[idx][1].get("status") != "FAILED_CHILD_RC"
        ]
        if unsafe_failed_indexes:
            run_issues.append(f"nonretryable_failed_attempts:{unsafe_failed_indexes}")
        complete_indexes = [
            idx
            for idx, (_path, terminal) in terminals.items()
            if terminal.get("status") in {"COMPLETE_VERIFIED", "RECOVERED_COMPLETE"}
        ]
        if len(complete_indexes) != 1:
            run_issues.append(f"complete_attempt_count_not_one:{len(complete_indexes)}")
        adoption_path = execution_paths["adoption_receipt"]
        adoption: dict[str, Any] = {}
        current_binding: dict[str, Any] = {}
        if len(complete_indexes) == 1:
            adopted_index = complete_indexes[0]
            terminal_path, terminal = terminals[adopted_index]
            try:
                current_binding = _validate_complete_run_artifacts(
                    run, index=index, paths=artifact_paths
                )
                if terminal.get("artifact_binding") != current_binding:
                    raise ValueError("terminal artifact binding mismatch")
                adoption = _validate_adoption_receipt(
                    adoption_path,
                    terminal_path=terminal_path,
                    terminal=terminal,
                    run_index=index,
                )
                if any(attempt_index > adopted_index for attempt_index in claims):
                    raise ValueError("attempt exists after adopted completion")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                run_issues.append(f"adoption_invalid:{type(exc).__name__}:{exc}")
        elif adoption_path.exists():
            run_issues.append("adoption_receipt_without_unique_complete_attempt")
        pair = (str(run.get("post_id") or "").strip(), run.get("repeat_index"))
        if adoption:
            adopted_pairs.append(pair)
        report["runs"].append(
            {
                "index": index,
                "post_id": pair[0],
                "repeat_index": pair[1],
                "attempt_claim_count": len(claims),
                "failed_attempt_count": len(failed_indexes),
                "indeterminate_attempt_count": len(indeterminate),
                "adopted": bool(adoption),
                "artifact_binding": current_binding,
                "issues": run_issues,
                "gate": "GO" if not run_issues else "NO-GO",
            }
        )
        issues.extend(f"run[{index}]:{issue}" for issue in run_issues)
    duplicate_pairs = sorted(
        pair for pair in set(adopted_pairs) if adopted_pairs.count(pair) > 1
    )
    if duplicate_pairs:
        issues.append(f"duplicate_adopted_post_repeat_pairs:{duplicate_pairs}")
    if len(adopted_pairs) != len(runs):
        issues.append("adopted_completion_count_mismatch")
    report["summary"] = {
        "planned_run_count": len(runs),
        "adopted_completion_count": len(adopted_pairs),
        "unique_adopted_pair_count": len(set(adopted_pairs)),
        "runtime_path_claim_count": len(runtime_claim_paths),
        "attempt_claim_count": total_claims,
        "child_started_count": total_child_started,
        "failed_attempt_count": total_failed,
        "indeterminate_attempt_count": total_indeterminate,
        "unrecorded_attempt_count": sum(
            1
            for issue in issues
            if "terminal_without_claim" in issue or "child_started_without_claim" in issue
        ),
        "issue_count": len(issues),
    }
    report["gate"] = "GO" if not issues else "NO-GO"
    return report


def _env_overrides(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"--set-env expects KEY=VALUE, got: {raw}")
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"empty environment key in: {raw}")
        out[key] = value
    return out


def _env_mapping(raw: Any, *, field_name: str) -> dict[str, str]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object")
    out: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} has an empty/non-string key")
        out[key.strip()] = str(value)
    return out


def _plan_env_overrides(plan: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    out.update(_env_mapping(plan.get("required_env"), field_name="required_env"))
    out.update(_env_mapping(plan.get("env_overrides"), field_name="env_overrides"))
    runtime_contract = plan.get("runtime_contract")
    if isinstance(runtime_contract, dict):
        out.update(
            _env_mapping(
                runtime_contract.get("required_env"),
                field_name="runtime_contract.required_env",
            )
        )
    return out


def _run_env_overrides(run: dict[str, Any], *, index: int) -> dict[str, str]:
    out: dict[str, str] = {}
    out.update(_env_mapping(run.get("required_env"), field_name=f"planned_runs[{index}].required_env"))
    out.update(_env_mapping(run.get("env_overrides"), field_name=f"planned_runs[{index}].env_overrides"))
    return out


def _env_truthy(name: str, *, env: dict[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    raw = str(values.get(name, "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _dashboard_enabled_from_cli(
    no_dashboard_requested: bool,
    *,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    if not no_dashboard_requested:
        return True, "default_on"
    if _env_truthy("ALLOW_TEST_RUN_NO_DASHBOARD", env=env):
        return False, "breakglass_disabled"
    return True, "forced_on_no_dashboard_forbidden"


def _safe_stem(path: str, fallback: str) -> str:
    stem = Path(path).stem
    if stem:
        return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in stem)
    return fallback


def _write_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")


def _dashboard_health(dashboard_url: str, *, timeout: float = 2.0) -> dict[str, Any]:
    health_url = f"{dashboard_url.rstrip('/')}/api/health"
    try:
        with urlopen(health_url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
        if not isinstance(payload, dict):
            payload = {}
        return {
            "ok": bool(payload.get("ok")),
            "standalone": bool(payload.get("standalone")),
            "service": payload.get("service") or "",
            "url": dashboard_url.rstrip("/"),
        }
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "standalone": False,
            "service": "",
            "url": dashboard_url.rstrip("/"),
            "error": repr(exc),
        }


def _dashboard_host_port(dashboard_url: str) -> tuple[str, int]:
    parsed = urlparse(dashboard_url)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    return host, port


def _manifest_path_for_run(run: dict[str, Any], output_path: Path | None) -> Path | None:
    raw_manifest = str(run.get("manifest_json") or "").strip()
    if raw_manifest:
        return Path(raw_manifest)
    if output_path is None:
        return None
    return output_path.with_name(output_path.stem + "_manifest.json")


def _start_manifest_attach(
    *,
    manifest_path: Path,
    dashboard_url: str,
    log_path: Path,
    python_executable: str,
    wait_sec: float = MANIFEST_ATTACH_WAIT_SECONDS,
) -> tuple[subprocess.Popen[Any], dict[str, Any]]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        python_executable,
        "tools/attach_manifest_dashboard.py",
        "--manifest",
        str(manifest_path),
        "--dashboard-url",
        dashboard_url,
        "--wait-for-manifest-sec",
        str(max(0.0, wait_sec)),
    ]
    token = os.environ.get("DASHBOARD_INGEST_TOKEN", "").strip()
    if token:
        argv.extend(["--token", token])
    with log_path.open("x", encoding="utf-8", errors="replace", newline="\n") as log_file:
        log_file.write(
            f"START_ATTACH {datetime.now().isoformat()} COMMAND {subprocess.list2cmdline(argv)}\n"
        )
        log_file.flush()
        proc = subprocess.Popen(
            argv,
            cwd=Path.cwd(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    return proc, {
        "pid": proc.pid,
        "manifest": str(manifest_path),
        "log": str(log_path),
        "command": subprocess.list2cmdline(argv),
    }


def _finish_manifest_attach(
    proc: subprocess.Popen[Any],
    *,
    run_returncode: int,
    timeout_sec: float = 10.0,
) -> int | str | None:
    try:
        return proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        if run_returncode == 0:
            proc.terminate()
        else:
            proc.kill()
        try:
            return proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            return "killed_after_timeout"


def _ensure_dashboard(
    *,
    dashboard_url: str,
    log_dir: Path,
    python_executable: str,
    wait_sec: float = 5.0,
) -> dict[str, Any]:
    dashboard_url = dashboard_url.rstrip("/") or DEFAULT_DASHBOARD_URL
    before = _dashboard_health(dashboard_url)
    if before.get("ok") and before.get("standalone"):
        return {"status": "already_running", **before}

    host, port = _dashboard_host_port(dashboard_url)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "dashboard_server.log"
    argv = [
        python_executable,
        "tools/dashboard_server.py",
        "--host",
        host,
        "--port",
        str(port),
    ]
    with log_path.open("a", encoding="utf-8", errors="replace", newline="\n") as log_file:
        log_file.write(f"START_DASHBOARD {datetime.now().isoformat()} COMMAND {subprocess.list2cmdline(argv)}\n")
        log_file.flush()
        proc = subprocess.Popen(
            argv,
            cwd=Path.cwd(),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    deadline = time.time() + max(0.5, wait_sec)
    last = before
    while time.time() < deadline:
        time.sleep(0.25)
        last = _dashboard_health(dashboard_url)
        if last.get("ok") and last.get("standalone"):
            return {"status": "started", "pid": proc.pid, "log": str(log_path), **last}
        if proc.poll() is not None:
            break
    return {
        "status": "unavailable",
        "pid": proc.pid,
        "exit_code": proc.poll(),
        "log": str(log_path),
        **last,
    }


def _write_invocation_receipt(
    path: Path,
    *,
    execution_id: str,
    gate: str,
    exit_code: int,
    plan_path: Path,
    plan_sha256: str,
    marker_path: Path,
    summary: dict[str, Any],
    error: str | None = None,
) -> None:
    payload = {
        "receipt_type": "independent_plan_execution_receipt",
        "execution_id": execution_id,
        "completed_at": datetime.now().isoformat(),
        "gate": gate,
        "exit_code": exit_code,
        "plan": str(plan_path.resolve()),
        "plan_sha256": plan_sha256,
        "execution_marker": str(marker_path.resolve()),
        "exclusive_create": True,
        **summary,
    }
    if error is not None:
        payload["error"] = error
    _write_json_exclusive(path, payload)


def _run_plan_locked(
    *,
    plan_path: Path,
    plan: dict[str, Any],
    runs: list[Any],
    contract: dict[str, Any],
    plan_claim_path: Path,
    states: dict[int, dict[str, Any]],
    log_dir: Path,
    env_updates: dict[str, str],
    skip_existing: bool,
    limit: int | None,
    dashboard: bool,
    dashboard_url: str,
    dashboard_python: str | None,
) -> int:
    plan_sha256 = _file_sha256(plan_path.resolve())
    global_claim_sha256 = _file_sha256(plan_claim_path)
    pending_indices = [index for index in range(1, len(runs) + 1) if states[index]["action"] == "RUN"]
    selected_indices = pending_indices[:limit] if limit is not None else pending_indices
    execution_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{os.getpid()}"
    attempt_log_dir = log_dir / "attempts" / execution_id
    execution_marker = attempt_log_dir / "execution.marker.json"
    execution_receipt = attempt_log_dir / "execution.receipt.json"
    attempt_log_dir.mkdir(parents=True, exist_ok=False)
    _write_json_exclusive(
        execution_marker,
        {
            "marker_type": "independent_plan_execution_started",
            "execution_id": execution_id,
            "created_at": datetime.now().isoformat(),
            "plan": str(plan_path.resolve()),
            "plan_sha256": plan_sha256,
            "global_plan_claim_sha256": global_claim_sha256,
            "selected_plan_indices": selected_indices,
            "pending_before": pending_indices,
            "adopted_before": [
                index for index, state in states.items() if state["action"] != "RUN"
            ],
            "skip_existing": skip_existing,
            "limit_requested": limit,
            "receipt_path": str(execution_receipt.resolve()),
            "exclusive_create": True,
        },
    )

    plan_env_updates = _plan_env_overrides(plan)
    env = os.environ.copy()
    env.update(plan_env_updates)
    env.update(env_updates)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("LLM_SUSPEND_ON_SERVER_ANOMALY", "0")
    env.setdefault("LLM_SUSPEND_FAILURE_THRESHOLD", "0")
    env.setdefault("LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS", "45")
    env.setdefault("LLM_STREAM_IDLE_TIMEOUT_SECONDS", "45")
    dashboard_state: dict[str, Any] = {"status": "disabled"}
    if dashboard:
        dashboard_url = dashboard_url.rstrip("/") or DEFAULT_DASHBOARD_URL
        host, port = _dashboard_host_port(dashboard_url)
        env.setdefault("DASHBOARD_URL", dashboard_url)
        env.setdefault("DASHBOARD_PORT", str(port))
        env.setdefault("EXPERT_DASHBOARD_FORWARD", "1")
        dashboard_state = _ensure_dashboard(
            dashboard_url=dashboard_url,
            log_dir=log_dir,
            python_executable=dashboard_python or sys.executable,
        )
        print(
            json.dumps(
                {
                    "event": "dashboard_ready",
                    "dashboard_url": dashboard_url,
                    "dashboard_status": dashboard_state.get("status"),
                    "dashboard_ok": dashboard_state.get("ok"),
                    "dashboard_standalone": dashboard_state.get("standalone"),
                    "dashboard_log": dashboard_state.get("log", ""),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        _write_line_exclusive(
            attempt_log_dir / "dashboard.marker.log",
            (
                f"DASHBOARD {datetime.now().isoformat()} status={dashboard_state.get('status')} "
                f"url={dashboard_url} host={host} port={port} log={dashboard_state.get('log', '')}"
            ),
        )

    completed = 0
    stripped_no_dashboard = 0
    dashboard_attach_started = 0
    dashboard_attach_records: list[dict[str, Any]] = []
    run_env_override_records: list[dict[str, Any]] = []
    adopted_this_execution: list[dict[str, Any]] = []
    summary_base = {
        "plan_total_runs": len(runs),
        "selected_runs": len(selected_indices),
        "selected_plan_indices": selected_indices,
        "skipped_adopted_before": len(runs) - len(pending_indices),
        "limit_requested": limit,
    }

    for index in selected_indices:
        run = runs[index - 1]
        if not isinstance(run, dict):
            raise ValueError(f"planned_runs[{index}] is not an object")
        state = states[index]
        artifact_paths: dict[str, Path] = state["artifact_paths"]
        execution_paths: dict[str, Path] = state["execution_paths"]
        attempt_index = int(state["next_attempt_index"])
        claim_path, terminal_path = _attempt_file_paths(
            execution_paths["attempt_dir"], attempt_index
        )
        claim = _attempt_claim_payload(
            run=run,
            index=index,
            attempt_index=attempt_index,
            plan_sha256=plan_sha256,
            global_claim_sha256=global_claim_sha256,
            artifact_paths=artifact_paths,
        )
        _write_json_exclusive(claim_path, claim)

        argv = run.get("command_argv")
        if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
            raise ValueError(f"planned_runs[{index}] has invalid command_argv")
        argv = list(argv)
        if dashboard:
            before_len = len(argv)
            argv = strip_no_dashboard(argv)
            stripped_no_dashboard += before_len - len(argv)
        stem = f"run_{index:03d}_" + _safe_stem(
            str(run.get("output_json") or ""), f"run_{index:03d}"
        )
        marker = attempt_log_dir / f"{stem}.marker.log"
        combined = attempt_log_dir / f"{stem}.combined.log"
        manifest_path = artifact_paths["manifest_json"]
        run_env_updates = _run_env_overrides(run, index=index)
        if run_env_updates:
            run_env_override_records.append({"index": index, "keys": sorted(run_env_updates)})
        run_env = env.copy()
        run_env.update(run_env_updates)

        attach_proc: subprocess.Popen[Any] | None = None
        attach_record: dict[str, Any] | None = None
        if dashboard:
            attach_proc, attach_record = _start_manifest_attach(
                manifest_path=manifest_path,
                dashboard_url=dashboard_url,
                log_path=attempt_log_dir / f"{stem}.dashboard_attach.log",
                python_executable=dashboard_python or sys.executable,
            )
            dashboard_attach_started += 1
            dashboard_attach_records.append({"index": index, **attach_record})
        _write_line_exclusive(
            marker,
            (
                f"START {datetime.now().isoformat()} index={index} attempt={attempt_index} "
                f"post_id={run.get('post_id')} repeat={run.get('repeat_index')} "
                f"claim={claim_path} manifest={manifest_path} "
                f"dashboard_attach_pid={(attach_record or {}).get('pid', '')}"
            ),
        )
        with combined.open("x", encoding="utf-8", errors="replace", newline="\n") as log_file:
            log_file.write(f"COMMAND {subprocess.list2cmdline(argv)}\n")
            log_file.flush()
            proc = subprocess.Popen(
                argv,
                cwd=Path.cwd(),
                env=run_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            child_started_path = _child_started_path(
                execution_paths["attempt_dir"], attempt_index
            )
            child_started = _child_started_receipt_payload(
                claim_path=claim_path,
                claim=claim,
                child_pid=proc.pid,
                process_creation_token=_process_creation_token(proc),
            )
            try:
                _write_json_exclusive(child_started_path, child_started)
            except Exception:
                proc.terminate()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise
            assert proc.stdout is not None
            try:
                for line in proc.stdout:
                    log_file.write(line)
                    log_file.flush()
                rc = proc.wait()
            finally:
                proc.stdout.close()
        attach_exit: int | str | None = None
        if attach_proc is not None:
            attach_exit = _finish_manifest_attach(attach_proc, run_returncode=rc)
            if attach_record is not None:
                attach_record["exit"] = attach_exit
        presence = _artifact_presence(artifact_paths)
        _write_line(
            marker,
            f"END {datetime.now().isoformat()} exit={rc} presence={presence} dashboard_attach_exit={attach_exit}",
        )
        if rc != 0:
            status = "FAILED_CHILD_RC" if not any(presence.values()) else "FAILED_CHILD_RC_DIRTY"
            terminal = _terminal_receipt_payload(
                status=status,
                claim_path=claim_path,
                claim=claim,
                child_started_path=child_started_path,
                child_started=child_started,
                child_returncode=rc,
                artifact_presence=presence,
                artifact_binding=None,
            )
            _write_json_exclusive(terminal_path, terminal)
            failure_summary = {
                **summary_base,
                "completed_runs": completed,
                "failed_run_index": index,
                "failed_attempt_index": attempt_index,
                "dashboard": dashboard_state,
            }
            _write_invocation_receipt(
                execution_receipt,
                execution_id=execution_id,
                gate="FAILED",
                exit_code=rc,
                plan_path=plan_path,
                plan_sha256=plan_sha256,
                marker_path=execution_marker,
                summary=failure_summary,
            )
            return rc
        try:
            artifact_binding = _validate_complete_run_artifacts(
                run, index=index, paths=artifact_paths
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            terminal = _terminal_receipt_payload(
                status="FAILED_ARTIFACT_VALIDATION",
                claim_path=claim_path,
                claim=claim,
                child_started_path=child_started_path,
                child_started=child_started,
                child_returncode=0,
                artifact_presence=presence,
                artifact_binding=None,
            )
            _write_json_exclusive(terminal_path, terminal)
            failure_summary = {
                **summary_base,
                "completed_runs": completed,
                "failed_run_index": index,
                "failed_attempt_index": attempt_index,
                "dashboard": dashboard_state,
            }
            _write_invocation_receipt(
                execution_receipt,
                execution_id=execution_id,
                gate="FAILED_RUNTIME_ARTIFACT_VALIDATION",
                exit_code=1,
                plan_path=plan_path,
                plan_sha256=plan_sha256,
                marker_path=execution_marker,
                summary=failure_summary,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        terminal = _terminal_receipt_payload(
            status="COMPLETE_VERIFIED",
            claim_path=claim_path,
            claim=claim,
            child_started_path=child_started_path,
            child_started=child_started,
            child_returncode=0,
            artifact_presence=presence,
            artifact_binding=artifact_binding,
        )
        _write_json_exclusive(terminal_path, terminal)
        adoption = _write_adoption_exclusive(
            execution_paths["adoption_receipt"],
            terminal_path=terminal_path,
            terminal=terminal,
        )
        adopted_this_execution.append(adoption)
        completed += 1

    adoption_audit = audit_plan_execution_adoption_contract(plan_path=plan_path, plan=plan)
    final_gate = "GO" if adoption_audit["gate"] == "GO" else "PARTIAL_NOT_COMPLETE"
    summary = {
        **summary_base,
        "plan": str(plan_path),
        "log_dir": str(log_dir),
        "attempt_log_dir": str(attempt_log_dir),
        "completed_runs": completed,
        "adopted_this_execution": len(adopted_this_execution),
        "adopted_total": adoption_audit.get("summary", {}).get("adopted_completion_count", 0),
        "remaining_unadopted": len(runs)
        - adoption_audit.get("summary", {}).get("adopted_completion_count", 0),
        "env_overrides": sorted(env_updates),
        "plan_env_overrides": sorted(plan_env_updates),
        "run_env_overrides": run_env_override_records,
        "dashboard": dashboard_state,
        "stripped_no_dashboard_flags": stripped_no_dashboard,
        "dashboard_attach_started_runs": dashboard_attach_started,
        "dashboard_attach_processes": dashboard_attach_records,
        "execution_adoption_audit": adoption_audit,
        "execution_marker": str(execution_marker.resolve()),
        "execution_receipt": str(execution_receipt.resolve()),
    }
    _write_invocation_receipt(
        execution_receipt,
        execution_id=execution_id,
        gate=final_gate,
        exit_code=0,
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        marker_path=execution_marker,
        summary=summary,
    )
    print(json.dumps({"gate": final_gate, **summary}, ensure_ascii=False, indent=2))
    return 0


def run_plan(
    *,
    plan_path: Path,
    log_dir: Path,
    env_updates: dict[str, str],
    skip_existing: bool,
    limit: int | None,
    dashboard: bool = True,
    dashboard_url: str = DEFAULT_DASHBOARD_URL,
    dashboard_python: str | None = None,
) -> int:
    if limit is not None and limit <= 0:
        raise ValueError("--limit must be a positive pending-run count")
    initial_plan = _load_json(plan_path)
    initial_runs = initial_plan.get("planned_runs")
    if not isinstance(initial_runs, list):
        raise ValueError(f"plan has no planned_runs list: {plan_path}")
    _validate_plan_self_binding(initial_plan)
    _validate_safe_loss_blind_judge_binding(initial_plan)
    initial_contract = _execution_claim_contract(
        plan_path=plan_path, plan=initial_plan, runs=initial_runs
    )
    initial_runtime_entries = _planned_runtime_path_entries(initial_runs)
    initial_runtime_identities = [entry["identity"] for entry in initial_runtime_entries]
    lock_path = _resolve_path(initial_contract["active_lock_file"])
    with _active_plan_lock(lock_path):
        with _active_runtime_path_locks(initial_runtime_entries):
            plan = _load_json(plan_path)
            _validate_plan_self_binding(plan)
            _validate_safe_loss_blind_judge_binding(plan)
            runs = plan.get("planned_runs")
            if not isinstance(runs, list):
                raise ValueError(f"plan has no planned_runs list: {plan_path}")
            contract = _execution_claim_contract(plan_path=plan_path, plan=plan, runs=runs)
            if _resolve_path(contract["active_lock_file"]) != lock_path:
                raise ValueError("plan active lock path changed during acquisition")
            runtime_entries = _planned_runtime_path_entries(runs)
            if [entry["identity"] for entry in runtime_entries] != initial_runtime_identities:
                raise ValueError("plan runtime paths changed during lock acquisition")
            expected_claim = _plan_claim_payload(
                plan_path=plan_path, plan=plan, runs=runs, contract=contract
            )
            claim_path = _resolve_path(contract["persistent_plan_claim_json"])
            _ensure_persistent_plan_claim(claim_path, expected_claim)
            _ensure_runtime_path_claims(runtime_entries, plan_claim=expected_claim)
            states = _prepare_run_attempt_states(
                plan=plan,
                runs=runs,
                contract=contract,
                plan_sha256=expected_claim["plan_sha256"],
                global_claim_path=claim_path,
                skip_existing=skip_existing,
            )
            return _run_plan_locked(
                plan_path=plan_path,
                plan=plan,
                runs=runs,
                contract=contract,
                plan_claim_path=claim_path,
                states=states,
                log_dir=log_dir,
                env_updates=env_updates,
                skip_existing=skip_existing,
                limit=limit,
                dashboard=dashboard,
                dashboard_url=dashboard_url,
                dashboard_python=dashboard_python,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an independent JSON run-plan sequentially with logs.")
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--log-dir", required=True, type=Path)
    parser.add_argument("--set-env", action="append", default=[], help="Environment override as KEY=VALUE.")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--dashboard-url",
        default=DEFAULT_DASHBOARD_URL,
        help="Standalone dashboard URL to start/use for test-run progress.",
    )
    parser.add_argument(
        "--dashboard-python",
        default=sys.executable,
        help="Python executable used to start tools/dashboard_server.py.",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help=(
            "Legacy breakglass only: ignored unless ALLOW_TEST_RUN_NO_DASHBOARD=1. "
            "Test/runtime plans default to standalone dashboard forwarding."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dashboard_enabled, dashboard_policy_status = _dashboard_enabled_from_cli(bool(args.no_dashboard))
    if args.no_dashboard:
        print(
            json.dumps(
                {
                    "event": "dashboard_policy",
                    "requested_no_dashboard": True,
                    "dashboard_enabled": dashboard_enabled,
                    "dashboard_policy_status": dashboard_policy_status,
                    "breakglass_env": "ALLOW_TEST_RUN_NO_DASHBOARD=1",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )
    return run_plan(
        plan_path=args.plan,
        log_dir=args.log_dir,
        env_updates=_env_overrides(list(args.set_env or [])),
        skip_existing=bool(args.skip_existing),
        limit=args.limit,
        dashboard=dashboard_enabled,
        dashboard_url=str(args.dashboard_url),
        dashboard_python=str(args.dashboard_python),
    )


if __name__ == "__main__":
    raise SystemExit(main())
