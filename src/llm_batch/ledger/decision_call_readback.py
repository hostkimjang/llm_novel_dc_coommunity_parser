"""Independent, read-only validation of a persisted decision-call ledger.

This module intentionally does not import or instantiate the ledger writer.  It
rebuilds identities, hashes, row evidence, retry lineages, seals, and links from
the bytes on disk.  It is a bounded v1 prerequisite and is not production-wired.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping


READBACK_SCHEMA = "decision_call_independent_readback_v1"
SCOPE_SCHEMA = "decision_call_ledger_scope_v1"
FRAME_SCHEMA = "decision_call_immutable_frame_v1"
ROW_SCHEMA = "decision_call_row_attempt_v1"
KINDS = {"DISPATCH_INTENT", "TERMINAL", "ROW_SEAL", "ROW_ABORT", "PUBLICATION_LINK"}
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED", "UNKNOWN"}
PROVENANCE = {"PROVIDER_REPORTED", "ESTIMATED", "UNAVAILABLE"}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class _Invalid(ValueError):
    pass


def _stable_bytes(path: Path) -> bytes:
    """Double-read one immutable source and reject replacement during readback."""

    try:
        before = path.stat()
        first = path.read_bytes()
        middle = path.stat()
        second = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        raise _Invalid(f"source read failed: {exc}") from exc
    identity = lambda value: (
        value.st_size,
        value.st_mtime_ns,
        getattr(value, "st_ino", 0),
    )
    if (
        identity(before) != identity(middle)
        or identity(middle) != identity(after)
        or first != second
    ):
        raise _Invalid("source changed during independent readback")
    return first


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key = str(key)
            if key in result:
                raise _Invalid("canonical key collision")
            result[key] = _canonical(item)
        return {key: result[key] for key in sorted(result)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise _Invalid("non-finite canonical number")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise _Invalid("unsupported canonical value")


def _sha(value: Any) -> str:
    payload = json.dumps(
        _canonical(value), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _keys(value: Any, expected: Iterable[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _Invalid(f"{label} must be an object")
    expected_set = set(expected)
    if set(value) != expected_set:
        raise _Invalid(f"{label} fields mismatch")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _Invalid(f"{field} must be non-empty text")
    return value.strip()


def _hex(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise _Invalid(f"{field} must be lowercase sha256")
    return value


def _uint(value: Any, field: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < int(positive):
        raise _Invalid(f"{field} must be {'positive' if positive else 'nonnegative'} int")
    return value


def _optional_uint(value: Any, field: str) -> int | None:
    return None if value is None else _uint(value, field)


def _time(value: Any, field: str) -> str:
    value = _text(value, field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise _Invalid(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise _Invalid(f"{field} must include timezone")
    return value


def _post_id(value: Any) -> int | str:
    if isinstance(value, bool) or value in (None, ""):
        raise _Invalid("post_id must be non-empty")
    if isinstance(value, int):
        if value <= 0:
            raise _Invalid("post_id must be positive")
        return value
    text = str(value).strip()
    try:
        number = int(text)
    except ValueError:
        return text
    if number <= 0:
        raise _Invalid("post_id must be positive")
    return number


def _row(value: Any, scope_id: str, post_ids: list[int | str]) -> dict[str, Any]:
    value = _keys(value, {
        "publication_scope_id", "attempt_run_id", "row_attempt_id",
        "input_index", "post_id", "schema_version",
    }, "row")
    if value["schema_version"] != ROW_SCHEMA:
        raise _Invalid("row schema mismatch")
    row = {
        "publication_scope_id": _hex(value["publication_scope_id"], "publication_scope_id"),
        "attempt_run_id": _text(value["attempt_run_id"], "attempt_run_id"),
        "row_attempt_id": _text(value["row_attempt_id"], "row_attempt_id"),
        "input_index": _uint(value["input_index"], "input_index", positive=True),
        "post_id": _post_id(value["post_id"]),
        "schema_version": ROW_SCHEMA,
    }
    if row["publication_scope_id"] != scope_id:
        raise _Invalid("row scope mismatch")
    index = row["input_index"]
    if index > len(post_ids) or post_ids[index - 1] != row["post_id"]:
        raise _Invalid("row input_index/post_id mismatch")
    return row


def _row_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (row["attempt_run_id"], row["row_attempt_id"], row["input_index"], row["post_id"])


def _scope_from_bytes(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _Invalid(f"invalid scope JSON: {exc}") from exc
    value = _keys(value, {
        "schema_version", "publication_scope_id", "publication_scope_descriptor",
        "measurement_bindings", "stage_allowlist", "scope_sha256",
    }, "scope")
    if value["schema_version"] != SCOPE_SCHEMA:
        raise _Invalid("scope schema mismatch")
    descriptor = _keys(value["publication_scope_descriptor"], {
        "schema_version", "publication_scope_id", "input_file_sha256", "post_ids",
        "config_hash", "release_fingerprint", "descriptor_sha256",
    }, "scope descriptor")
    if descriptor["schema_version"] != "publication_scope_descriptor_v1":
        raise _Invalid("scope descriptor schema mismatch")
    raw_posts = descriptor["post_ids"]
    if not isinstance(raw_posts, list):
        raise _Invalid("scope post_ids must be a list")
    posts = [_post_id(item) for item in raw_posts]
    if not posts or len(posts) != len(set(posts)):
        raise _Invalid("scope post_ids must be non-empty and unique")
    input_hash = _hex(descriptor["input_file_sha256"], "input_file_sha256")
    config_hash = _text(descriptor["config_hash"], "config_hash")
    release = descriptor["release_fingerprint"]
    if release is not None:
        release = _text(release, "release_fingerprint")
    scope_id = _sha({
        "schema_version": "publication_scope_v1", "input_file_sha256": input_hash,
        "post_id_order": posts, "config_hash": config_hash,
        "release_fingerprint": release,
    })
    if _hex(descriptor["publication_scope_id"], "publication_scope_id") != scope_id:
        raise _Invalid("scope id mismatch")
    descriptor_material = {
        "schema_version": "publication_scope_descriptor_v1",
        "publication_scope_id": scope_id, "input_file_sha256": input_hash,
        "post_ids": posts, "config_hash": config_hash, "release_fingerprint": release,
    }
    descriptor_hash = _hex(descriptor["descriptor_sha256"], "descriptor_sha256")
    if descriptor_hash != _sha(descriptor_material):
        raise _Invalid("scope descriptor hash mismatch")
    descriptor_normal = {**descriptor_material, "descriptor_sha256": descriptor_hash}
    if _hex(value["publication_scope_id"], "publication_scope_id") != scope_id:
        raise _Invalid("scope sidecar id mismatch")
    bindings = _keys(value["measurement_bindings"], {
        "run_spec_sha256", "pair_id", "arm", "fresh_execution_mode",
    }, "measurement bindings")
    run_hash = bindings["run_spec_sha256"]
    if run_hash is not None:
        run_hash = _hex(run_hash, "run_spec_sha256")
    pair_id = bindings["pair_id"]
    if pair_id is not None:
        pair_id = _text(pair_id, "pair_id")
    arm = bindings["arm"]
    if arm is not None and arm not in {"BEFORE", "AFTER"}:
        raise _Invalid("arm mismatch")
    fresh = bindings["fresh_execution_mode"]
    if fresh is not None and not isinstance(fresh, bool):
        raise _Invalid("fresh_execution_mode must be bool")
    bindings_normal = {
        "run_spec_sha256": run_hash, "pair_id": pair_id, "arm": arm,
        "fresh_execution_mode": fresh,
    }
    stages = value["stage_allowlist"]
    if not isinstance(stages, list) or not stages:
        raise _Invalid("stage_allowlist must be non-empty list")
    stages_normal = sorted({_text(item, "stage").upper() for item in stages})
    material = {
        "schema_version": SCOPE_SCHEMA, "publication_scope_id": scope_id,
        "publication_scope_descriptor": descriptor_normal,
        "measurement_bindings": bindings_normal, "stage_allowlist": stages_normal,
    }
    scope_hash = _hex(value["scope_sha256"], "scope_sha256")
    if scope_hash != _sha(material):
        raise _Invalid("scope self hash mismatch")
    return {**material, "scope_sha256": scope_hash}


_DISPATCH_FIELDS = {
    "logical_call_id", "call_id", "retry_ordinal", "retry_of_call_id", "stage",
    "modality", "requested_model", "resolved_model", "endpoint", "backend",
    "started_at", "monotonic_started_ns", "request_sha256",
}
_TERMINAL_EXTRA = {
    "terminal_status", "finished_at", "monotonic_finished_ns", "wall_ms",
    "response_sha256", "usage_provenance", "prompt_tokens", "completion_tokens",
    "total_tokens", "error_type", "error_message_sha256",
}


def _optional_text(value: Any, field: str) -> str | None:
    return None if value is None else _text(value, field)


def _dispatch_payload(value: Any, stages: set[str]) -> dict[str, Any]:
    value = _keys(value, _DISPATCH_FIELDS, "dispatch payload")
    ordinal = _uint(value["retry_ordinal"], "retry_ordinal")
    parent = _optional_text(value["retry_of_call_id"], "retry_of_call_id")
    if (ordinal == 0) != (parent is None):
        raise _Invalid("retry parent/ordinal mismatch")
    stage = _text(value["stage"], "stage").upper()
    if stage not in stages:
        raise _Invalid("stage not allowlisted")
    modality = _text(value["modality"], "modality").upper()
    if modality not in {"TEXT", "VLM"}:
        raise _Invalid("modality mismatch")
    resolved = _optional_text(value["resolved_model"], "resolved_model")
    return {
        "logical_call_id": _text(value["logical_call_id"], "logical_call_id"),
        "call_id": _text(value["call_id"], "call_id"), "retry_ordinal": ordinal,
        "retry_of_call_id": parent, "stage": stage, "modality": modality,
        "requested_model": _text(value["requested_model"], "requested_model"),
        "resolved_model": resolved, "endpoint": _text(value["endpoint"], "endpoint"),
        "backend": _text(value["backend"], "backend"),
        "started_at": _time(value["started_at"], "started_at"),
        "monotonic_started_ns": _uint(value["monotonic_started_ns"], "monotonic_started_ns"),
        "request_sha256": _hex(value["request_sha256"], "request_sha256"),
    }


def _payload(kind: str, value: Any, stages: set[str]) -> dict[str, Any]:
    if kind == "DISPATCH_INTENT":
        return _dispatch_payload(value, stages)
    if kind == "TERMINAL":
        value = _keys(value, _DISPATCH_FIELDS | _TERMINAL_EXTRA, "terminal payload")
        base = _dispatch_payload({key: value[key] for key in _DISPATCH_FIELDS}, stages)
        status = _text(value["terminal_status"], "terminal_status").upper()
        if status not in TERMINAL_STATUSES:
            raise _Invalid("terminal status mismatch")
        finished_at = _time(value["finished_at"], "finished_at")
        finished_ns = _uint(value["monotonic_finished_ns"], "monotonic_finished_ns")
        if datetime.fromisoformat(finished_at) < datetime.fromisoformat(base["started_at"]):
            raise _Invalid("terminal timestamp precedes dispatch")
        if finished_ns < base["monotonic_started_ns"]:
            raise _Invalid("terminal monotonic timestamp precedes dispatch")
        wall_ms = _uint(value["wall_ms"], "wall_ms")
        if wall_ms != (finished_ns - base["monotonic_started_ns"]) // 1_000_000:
            raise _Invalid("terminal wall_ms mismatch")
        provenance = _text(value["usage_provenance"], "usage_provenance").upper()
        if provenance not in PROVENANCE:
            raise _Invalid("usage provenance mismatch")
        tokens = tuple(_optional_uint(value[name], name) for name in (
            "prompt_tokens", "completion_tokens", "total_tokens"))
        if provenance == "UNAVAILABLE":
            if any(item is not None for item in tokens):
                raise _Invalid("unavailable usage has tokens")
        elif any(item is None for item in tokens) or tokens[2] != tokens[0] + tokens[1]:
            raise _Invalid("token usage mismatch")
        response = value["response_sha256"]
        response = None if response is None else _hex(response, "response_sha256")
        error_type = _optional_text(value["error_type"], "error_type")
        error_hash = value["error_message_sha256"]
        error_hash = None if error_hash is None else _hex(error_hash, "error_message_sha256")
        if status == "SUCCEEDED":
            if response is None or error_type is not None or error_hash is not None:
                raise _Invalid("successful terminal response/error mismatch")
        elif error_type is None:
            raise _Invalid("failed terminal requires error_type")
        return {**base, "terminal_status": status, "finished_at": finished_at,
                "monotonic_finished_ns": finished_ns, "wall_ms": wall_ms,
                "response_sha256": response, "usage_provenance": provenance,
                "prompt_tokens": tokens[0], "completion_tokens": tokens[1],
                "total_tokens": tokens[2], "error_type": error_type,
                "error_message_sha256": error_hash}
    if kind == "ROW_SEAL":
        fields = {"event_root_sha256", "event_frame_count", "expert_calls", "text_calls",
                  "vlm_calls", "retry_count", "terminal_counts", "usage_status",
                  "prompt_tokens", "completion_tokens", "total_tokens", "sealed_at",
                  "monotonic_finished_ns"}
        value = _keys(value, fields, "row seal payload")
        counts = _keys(value["terminal_counts"], TERMINAL_STATUSES, "terminal_counts")
        counts = {key: _uint(counts[key], f"terminal_counts.{key}") for key in sorted(counts)}
        usage = _text(value["usage_status"], "usage_status")
        if usage not in {"NO_CALLS", "COMPLETE_PROVIDER_REPORTED", "COMPLETE_WITH_ESTIMATES", "UNAVAILABLE"}:
            raise _Invalid("seal usage status mismatch")
        tokens = tuple(_optional_uint(value[name], name) for name in (
            "prompt_tokens", "completion_tokens", "total_tokens"))
        if usage == "UNAVAILABLE":
            if any(item is not None for item in tokens):
                raise _Invalid("unavailable seal has tokens")
        elif any(item is None for item in tokens) or tokens[2] != tokens[0] + tokens[1]:
            raise _Invalid("seal token mismatch")
        return {"event_root_sha256": _hex(value["event_root_sha256"], "event_root_sha256"),
                "event_frame_count": _uint(value["event_frame_count"], "event_frame_count"),
                "expert_calls": _uint(value["expert_calls"], "expert_calls"),
                "text_calls": _uint(value["text_calls"], "text_calls"),
                "vlm_calls": _uint(value["vlm_calls"], "vlm_calls"),
                "retry_count": _uint(value["retry_count"], "retry_count"),
                "terminal_counts": counts, "usage_status": usage,
                "prompt_tokens": tokens[0], "completion_tokens": tokens[1],
                "total_tokens": tokens[2], "sealed_at": _time(value["sealed_at"], "sealed_at"),
                "monotonic_finished_ns": _uint(value["monotonic_finished_ns"], "monotonic_finished_ns")}
    if kind == "ROW_ABORT":
        value = _keys(value, {"reason_code", "event_root_sha256", "event_frame_count",
                              "expert_calls", "open_call_count", "aborted_at",
                              "monotonic_finished_ns"}, "row abort payload")
        return {"reason_code": _text(value["reason_code"], "reason_code"),
                "event_root_sha256": _hex(value["event_root_sha256"], "event_root_sha256"),
                "event_frame_count": _uint(value["event_frame_count"], "event_frame_count"),
                "expert_calls": _uint(value["expert_calls"], "expert_calls"),
                "open_call_count": _uint(value["open_call_count"], "open_call_count"),
                "aborted_at": _time(value["aborted_at"], "aborted_at"),
                "monotonic_finished_ns": _uint(value["monotonic_finished_ns"], "monotonic_finished_ns")}
    value = _keys(value, {"publication_decision_id", "event_root_sha256",
                          "seal_frame_sha256", "linked_at"}, "publication link payload")
    return {"publication_decision_id": _hex(value["publication_decision_id"], "publication_decision_id"),
            "event_root_sha256": _hex(value["event_root_sha256"], "event_root_sha256"),
            "seal_frame_sha256": _hex(value["seal_frame_sha256"], "seal_frame_sha256"),
            "linked_at": _time(value["linked_at"], "linked_at")}


def _frame_from_bytes(raw: bytes, filename: str, scope: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _Invalid(f"invalid frame JSON: {exc}") from exc
    value = _keys(value, {"schema_version", "frame_kind", "row", "identity_sha256",
                          "payload", "frame_sha256"}, "frame")
    if value["schema_version"] != FRAME_SCHEMA:
        raise _Invalid("frame schema mismatch")
    kind = _text(value["frame_kind"], "frame_kind")
    if kind not in KINDS:
        raise _Invalid("frame kind mismatch")
    descriptor = scope["publication_scope_descriptor"]
    row = _row(value["row"], scope["publication_scope_id"], descriptor["post_ids"])
    payload = _payload(kind, value["payload"], set(scope["stage_allowlist"]))
    identity_material: dict[str, Any] = {"frame_kind": kind, "row": row}
    if kind in {"DISPATCH_INTENT", "TERMINAL"}:
        identity_material["call_id"] = payload["call_id"]
    identity = _sha(identity_material)
    if value["identity_sha256"] != identity:
        raise _Invalid("frame identity mismatch")
    material = {"schema_version": FRAME_SCHEMA, "frame_kind": kind, "row": row,
                "identity_sha256": identity, "payload": payload}
    frame_hash = _sha(material)
    if value["frame_sha256"] != frame_hash:
        raise _Invalid("frame self hash mismatch")
    expected_name = f"{kind.lower()}_{identity}.json"
    if filename != expected_name:
        raise _Invalid("frame filename/identity mismatch")
    return {**material, "frame_sha256": frame_hash, "_filename": filename}


def _evidence(row_frames: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [frame for frame in row_frames if frame["frame_kind"] in {"DISPATCH_INTENT", "TERMINAL"}]
    calls.sort(key=lambda frame: (frame["payload"]["monotonic_started_ns"],
                                  frame["payload"]["call_id"],
                                  0 if frame["frame_kind"] == "DISPATCH_INTENT" else 1))
    dispatches = [frame for frame in calls if frame["frame_kind"] == "DISPATCH_INTENT"]
    terminals = [frame for frame in calls if frame["frame_kind"] == "TERMINAL"]
    terminal_ids = {frame["payload"]["call_id"] for frame in terminals}
    open_count = sum(frame["payload"]["call_id"] not in terminal_ids for frame in dispatches)
    provenance = [frame["payload"]["usage_provenance"] for frame in terminals]
    if not dispatches:
        usage_status, prompt, completion, total = "NO_CALLS", 0, 0, 0
    elif open_count or "UNAVAILABLE" in provenance:
        usage_status, prompt, completion, total = "UNAVAILABLE", None, None, None
    else:
        usage_status = "COMPLETE_WITH_ESTIMATES" if "ESTIMATED" in provenance else "COMPLETE_PROVIDER_REPORTED"
        prompt = sum(frame["payload"]["prompt_tokens"] for frame in terminals)
        completion = sum(frame["payload"]["completion_tokens"] for frame in terminals)
        total = prompt + completion
    return {"event_root_sha256": _sha([frame["frame_sha256"] for frame in calls]),
            "event_frame_count": len(calls), "expert_calls": len(dispatches),
            "text_calls": sum(frame["payload"]["modality"] == "TEXT" for frame in dispatches),
            "vlm_calls": sum(frame["payload"]["modality"] == "VLM" for frame in dispatches),
            "retry_count": sum(frame["payload"]["retry_ordinal"] > 0 for frame in dispatches),
            "physical_call_wall_ms_sum": sum(
                frame["payload"]["wall_ms"] for frame in terminals
            ),
            "physical_call_wall_ms_max": max(
                (frame["payload"]["wall_ms"] for frame in terminals),
                default=0,
            ),
            "terminal_counts": {status: sum(frame["payload"]["terminal_status"] == status
                                               for frame in terminals)
                                for status in sorted(TERMINAL_STATUSES)},
            "usage_status": usage_status, "prompt_tokens": prompt,
            "completion_tokens": completion, "total_tokens": total,
            "open_call_count": open_count}


def compute_readback_report_sha256(report: Mapping[str, Any]) -> str:
    """Hash every report field except the report digest itself."""

    if not isinstance(report, Mapping):
        raise TypeError("report must be a mapping")
    return _sha({key: value for key, value in report.items() if key != "report_sha256"})


def verify_readback_report_sha256(report: Mapping[str, Any]) -> bool:
    """Verify a report digest after loading it from an untrusted file."""

    supplied = report.get("report_sha256") if isinstance(report, Mapping) else None
    return isinstance(supplied, str) and bool(_HEX64.fullmatch(supplied)) and (
        supplied == compute_readback_report_sha256(report)
    )


def read_decision_call_ledger(path: str | Path) -> dict[str, Any]:
    """Validate and aggregate one ledger from persisted bytes only.

    Invalid or ambiguous evidence is returned as ``NO-GO`` / ``NOT_ESTIMABLE``
    instead of raising, so callers can persist a useful forensic report.
    """

    root = Path(path).resolve()
    reasons: list[str] = []
    errors: list[dict[str, str]] = []
    scope: dict[str, Any] | None = None
    scope_source_sha256: str | None = None
    frames: list[dict[str, Any]] = []
    frame_source_sha256: dict[str, str] = {}
    initial_entry_names: tuple[str, ...] = ()
    try:
        scope_raw = _stable_bytes(root / "scope.json")
        scope_source_sha256 = hashlib.sha256(scope_raw).hexdigest()
        scope = _scope_from_bytes(scope_raw)
    except (OSError, _Invalid) as exc:
        reasons.append("INVALID_SCOPE")
        errors.append({"path": "scope.json", "error": str(exc)})

    frames_dir = root / "frames"
    if scope is not None:
        try:
            entries = sorted(frames_dir.iterdir(), key=lambda item: item.name)
            initial_entry_names = tuple(item.name for item in entries)
        except OSError as exc:
            entries = []
            reasons.append("INVALID_FRAMES_DIRECTORY")
            errors.append({"path": "frames", "error": str(exc)})
        seen_hashes: Counter[str] = Counter()
        for entry in entries:
            if entry.name.startswith(".") and entry.name.endswith(".tmp"):
                continue
            if not entry.is_file() or entry.suffix != ".json":
                reasons.append("UNEXPECTED_FRAME_ENTRY")
                errors.append({"path": f"frames/{entry.name}", "error": "unexpected entry"})
                continue
            try:
                frame_raw = _stable_bytes(entry)
                frame = _frame_from_bytes(frame_raw, entry.name, scope)
            except (OSError, _Invalid) as exc:
                reasons.append("INVALID_FRAME")
                errors.append({"path": f"frames/{entry.name}", "error": str(exc)})
                continue
            frames.append(frame)
            frame_source_sha256[entry.name] = hashlib.sha256(frame_raw).hexdigest()
            seen_hashes[frame["frame_sha256"]] += 1
        if any(count > 1 for count in seen_hashes.values()):
            reasons.append("DUPLICATE_FRAME")

        # Re-enumerate and re-read the complete source set after parsing.  A
        # frame added, removed, or replaced mid-read makes the report forensic
        # NO-GO instead of a falsely exact partial snapshot.
        try:
            final_entries = sorted(frames_dir.iterdir(), key=lambda item: item.name)
            final_entry_names = tuple(item.name for item in final_entries)
            if final_entry_names != initial_entry_names:
                reasons.append("FRAME_SET_CHANGED_DURING_READBACK")
                errors.append(
                    {
                        "path": "frames",
                        "error": "frame directory membership changed during readback",
                    }
                )
            else:
                for entry in final_entries:
                    if entry.name.startswith(".") and entry.name.endswith(".tmp"):
                        continue
                    if entry.name not in frame_source_sha256:
                        continue
                    final_raw = _stable_bytes(entry)
                    if hashlib.sha256(final_raw).hexdigest() != frame_source_sha256[entry.name]:
                        reasons.append("FRAME_CHANGED_DURING_READBACK")
                        errors.append(
                            {
                                "path": f"frames/{entry.name}",
                                "error": "frame bytes changed after parsing",
                            }
                        )
        except (OSError, _Invalid) as exc:
            reasons.append("FRAME_SET_CHANGED_DURING_READBACK")
            errors.append({"path": "frames", "error": str(exc)})
        try:
            final_scope_raw = _stable_bytes(root / "scope.json")
            if hashlib.sha256(final_scope_raw).hexdigest() != scope_source_sha256:
                reasons.append("SCOPE_CHANGED_DURING_READBACK")
                errors.append(
                    {"path": "scope.json", "error": "scope bytes changed after parsing"}
                )
        except _Invalid as exc:
            reasons.append("SCOPE_CHANGED_DURING_READBACK")
            errors.append({"path": "scope.json", "error": str(exc)})

    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_row: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for frame in frames:
        by_kind[frame["frame_kind"]].append(frame)
        by_row[_row_key(frame["row"])].append(frame)

    dispatches: dict[str, dict[str, Any]] = {}
    terminals: dict[str, dict[str, Any]] = {}
    duplicate_calls: set[str] = set()
    ordinal_seen: dict[tuple[Any, ...], str] = {}
    for frame in by_kind["DISPATCH_INTENT"]:
        call_id = frame["payload"]["call_id"]
        if call_id in dispatches:
            duplicate_calls.add(call_id)
        dispatches[call_id] = frame
        ordinal_key = _row_key(frame["row"]) + (frame["payload"]["logical_call_id"],
                                                   frame["payload"]["retry_ordinal"])
        if ordinal_key in ordinal_seen and ordinal_seen[ordinal_key] != call_id:
            reasons.append("DUPLICATE_RETRY_ORDINAL")
        ordinal_seen[ordinal_key] = call_id
    for frame in by_kind["TERMINAL"]:
        call_id = frame["payload"]["call_id"]
        if call_id in terminals:
            duplicate_calls.add(call_id)
        terminals[call_id] = frame
    if duplicate_calls:
        reasons.append("DUPLICATE_CALL")

    orphan_terminals: list[str] = []
    for call_id, terminal in terminals.items():
        dispatch = dispatches.get(call_id)
        if dispatch is None:
            orphan_terminals.append(call_id)
            continue
        if terminal["row"] != dispatch["row"]:
            reasons.append("TERMINAL_ROW_MISMATCH")
        bound_fields = _DISPATCH_FIELDS - {"resolved_model"}
        if any(terminal["payload"][field] != dispatch["payload"][field]
               for field in bound_fields):
            reasons.append("TERMINAL_DISPATCH_MISMATCH")
        expected_model = dispatch["payload"]["resolved_model"]
        if expected_model is not None and terminal["payload"]["resolved_model"] != expected_model:
            reasons.append("TERMINAL_MODEL_MISMATCH")
    if orphan_terminals:
        reasons.append("ORPHAN_TERMINAL")

    for call_id, dispatch in dispatches.items():
        payload = dispatch["payload"]
        if not payload["retry_ordinal"]:
            continue
        parent_id = payload["retry_of_call_id"]
        parent = dispatches.get(parent_id)
        parent_terminal = terminals.get(parent_id)
        if parent is None or parent_terminal is None:
            reasons.append("RETRY_LINEAGE_GAP")
            continue
        if parent["row"] != dispatch["row"]:
            reasons.append("RETRY_PARENT_ROW_MISMATCH")
        if parent["payload"]["logical_call_id"] != payload["logical_call_id"]:
            reasons.append("RETRY_LOGICAL_CALL_MISMATCH")
        if parent["payload"]["retry_ordinal"] != payload["retry_ordinal"] - 1:
            reasons.append("RETRY_ORDINAL_GAP")
        if parent_terminal["payload"]["terminal_status"] == "SUCCEEDED":
            reasons.append("RETRY_AFTER_SUCCESS")
        if payload["monotonic_started_ns"] < parent_terminal["payload"]["monotonic_finished_ns"]:
            reasons.append("RETRY_STARTED_BEFORE_PARENT_TERMINAL")

    seals: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    aborts: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    links: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for kind, target in (("ROW_SEAL", seals), ("ROW_ABORT", aborts),
                         ("PUBLICATION_LINK", links)):
        for frame in by_kind[kind]:
            target[_row_key(frame["row"])].append(frame)
    for target, code in ((seals, "DUPLICATE_ROW_SEAL"), (aborts, "DUPLICATE_ROW_ABORT"),
                         (links, "DUPLICATE_PUBLICATION_LINK")):
        if any(len(items) > 1 for items in target.values()):
            reasons.append(code)

    evidence_by_row = {key: _evidence(items) for key, items in by_row.items()}
    unlinked_rows: list[str] = []
    aborted_rows: list[str] = []
    for key, evidence in evidence_by_row.items():
        seal_items, abort_items, link_items = seals[key], aborts[key], links[key]
        label = str(key[1])
        if seal_items and abort_items:
            reasons.append("ROW_SEALED_AND_ABORTED")
        if abort_items:
            aborted_rows.append(label)
            abort = abort_items[0]["payload"]
            expected = {"reason_code": abort["reason_code"],
                        "event_root_sha256": evidence["event_root_sha256"],
                        "event_frame_count": evidence["event_frame_count"],
                        "expert_calls": evidence["expert_calls"],
                        "open_call_count": evidence["open_call_count"],
                        "aborted_at": abort["aborted_at"],
                        "monotonic_finished_ns": abort["monotonic_finished_ns"]}
            if abort != expected:
                reasons.append("ROW_ABORT_MISMATCH")
        if seal_items:
            seal = seal_items[0]
            expected = {key_name: evidence[key_name] for key_name in (
                "event_root_sha256", "event_frame_count", "expert_calls", "text_calls",
                "vlm_calls", "retry_count", "terminal_counts", "usage_status",
                "prompt_tokens", "completion_tokens", "total_tokens")}
            expected.update({"sealed_at": seal["payload"]["sealed_at"],
                             "monotonic_finished_ns": seal["payload"]["monotonic_finished_ns"]})
            if seal["payload"] != expected:
                reasons.append("ROW_SEAL_MISMATCH")
            if evidence["open_call_count"]:
                reasons.append("SEALED_ROW_HAS_OPEN_CALL")
            if evidence["expert_calls"] and not evidence["terminal_counts"]["SUCCEEDED"]:
                reasons.append("SEALED_ROW_HAS_NO_SUCCESS")
            row_terminals = [frame for frame in by_row[key] if frame["frame_kind"] == "TERMINAL"]
            if any(frame["payload"]["monotonic_finished_ns"] >
                   seal["payload"]["monotonic_finished_ns"] for frame in row_terminals):
                reasons.append("SEAL_PRECEDES_CALL_TERMINAL")
            if any(datetime.fromisoformat(frame["payload"]["finished_at"]) >
                   datetime.fromisoformat(seal["payload"]["sealed_at"])
                   for frame in row_terminals):
                reasons.append("SEAL_WALL_TIME_PRECEDES_CALL_TERMINAL")
        elif not abort_items:
            reasons.append("UNSEALED_ROW")
        if link_items:
            if not seal_items:
                reasons.append("ORPHAN_PUBLICATION_LINK")
            else:
                link, seal = link_items[0], seal_items[0]
                if (link["payload"]["event_root_sha256"] != seal["payload"]["event_root_sha256"]
                        or link["payload"]["seal_frame_sha256"] != seal["frame_sha256"]):
                    reasons.append("PUBLICATION_LINK_MISMATCH")
                if datetime.fromisoformat(link["payload"]["linked_at"]) < datetime.fromisoformat(
                        seal["payload"]["sealed_at"]):
                    reasons.append("LINK_PRECEDES_SEAL")
        elif seal_items:
            unlinked_rows.append(label)
    if unlinked_rows:
        reasons.append("UNLINKED_ROW")
    if aborted_rows:
        reasons.append("ABORTED_ROW")

    ambiguous_rows: list[str] = []
    expected_count = len(scope["publication_scope_descriptor"]["post_ids"]) if scope else 0
    by_run: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
    for key in by_row:
        by_run[str(key[0])].append(key)
    if len(by_run) != 1:
        reasons.append("AMBIGUOUS_ATTEMPT_RUN")
    for run_id, keys in by_run.items():
        coordinates = [(key[2], key[3]) for key in keys]
        if len(coordinates) != len(set(coordinates)):
            ambiguous_rows.extend(str(key[1]) for key in keys)
            reasons.append("AMBIGUOUS_ROW_ATTEMPT")
        expected = set(enumerate(scope["publication_scope_descriptor"]["post_ids"], 1)) if scope else set()
        if set(coordinates) != expected:
            reasons.append("ROW_COVERAGE_INCOMPLETE")

    if any(evidence["open_call_count"] for evidence in evidence_by_row.values()):
        reasons.append("OPEN_CALL")
    provenance_counts = Counter(frame["payload"]["usage_provenance"]
                                for frame in by_kind["TERMINAL"])
    if provenance_counts["UNAVAILABLE"]:
        reasons.append("USAGE_UNAVAILABLE")
    if provenance_counts["ESTIMATED"]:
        reasons.append("USAGE_ESTIMATED")
    if any(frame["payload"]["resolved_model"] is None for frame in by_kind["TERMINAL"]):
        reasons.append("RESOLVED_MODEL_UNAVAILABLE")
    bindings = scope["measurement_bindings"] if scope else {}
    if not scope or not (bindings.get("run_spec_sha256") and bindings.get("pair_id")
                         and bindings.get("arm") and bindings.get("fresh_execution_mode") is True):
        reasons.append("MEASUREMENT_NOT_BOUND_FRESH")

    reasons = sorted(set(reasons))
    exact = not reasons
    observed_prompt = (sum(frame["payload"]["prompt_tokens"] for frame in by_kind["TERMINAL"]
                           if frame["payload"]["prompt_tokens"] is not None)
                       if frames else 0)
    observed_completion = (sum(frame["payload"]["completion_tokens"] for frame in by_kind["TERMINAL"]
                               if frame["payload"]["completion_tokens"] is not None)
                           if frames else 0)
    observed_metrics = {
        "expert_calls": len(by_kind["DISPATCH_INTENT"]),
        "text_calls": sum(
            frame["payload"]["modality"] == "TEXT"
            for frame in by_kind["DISPATCH_INTENT"]
        ),
        "vlm_calls": sum(
            frame["payload"]["modality"] == "VLM"
            for frame in by_kind["DISPATCH_INTENT"]
        ),
        "retry_count": sum(
            frame["payload"]["retry_ordinal"] > 0
            for frame in by_kind["DISPATCH_INTENT"]
        ),
        "prompt_tokens": observed_prompt,
        "completion_tokens": observed_completion,
        "total_tokens": observed_prompt + observed_completion,
        "physical_call_wall_ms_sum": sum(
            frame["payload"]["wall_ms"] for frame in by_kind["TERMINAL"]
        ),
    }
    actual_metrics = dict(observed_metrics) if exact else {key: None for key in observed_metrics}
    status_counts = Counter(frame["payload"]["terminal_status"] for frame in by_kind["TERMINAL"])
    row_receipts = []
    for key in sorted(by_row, key=str):
        seal = seals[key][0] if len(seals[key]) == 1 else None
        link = links[key][0] if len(links[key]) == 1 else None
        row_receipts.append({
            "attempt_run_id": key[0], "row_attempt_id": key[1],
            "input_index": key[2], "post_id": key[3],
            "event_root_sha256": seal["payload"]["event_root_sha256"] if seal else None,
            "seal_frame_sha256": seal["frame_sha256"] if seal else None,
            "publication_decision_id": link["payload"]["publication_decision_id"] if link else None,
            "link_event_root_sha256": link["payload"]["event_root_sha256"] if link else None,
            "link_seal_frame_sha256": link["payload"]["seal_frame_sha256"] if link else None,
            "seal_status": "SEALED" if seal else "NOT_UNIQUE_OR_MISSING",
            "link_status": "LINKED" if link else "NOT_UNIQUE_OR_MISSING",
            "expert_calls": evidence_by_row[key]["expert_calls"],
            "text_calls": evidence_by_row[key]["text_calls"],
            "vlm_calls": evidence_by_row[key]["vlm_calls"],
            "retry_count": evidence_by_row[key]["retry_count"],
            "usage_status": evidence_by_row[key]["usage_status"],
            "prompt_tokens": evidence_by_row[key]["prompt_tokens"],
            "completion_tokens": evidence_by_row[key]["completion_tokens"],
            "total_tokens": evidence_by_row[key]["total_tokens"],
            "physical_call_wall_ms_sum": evidence_by_row[key][
                "physical_call_wall_ms_sum"
            ],
            "physical_call_wall_ms_max": evidence_by_row[key][
                "physical_call_wall_ms_max"
            ],
        })
    report = {
        "schema_version": READBACK_SCHEMA, "ledger_path": str(root),
        "frame_set_sha256": _sha(sorted(frame["frame_sha256"] for frame in frames)),
        "source_snapshot_sha256": _sha(
            {
                "scope": scope_source_sha256,
                "frames": dict(sorted(frame_source_sha256.items())),
            }
        ),
        "gate_status": "GO" if exact else "NO-GO",
        "aggregate_status": "EXACT" if exact else "NOT_ESTIMABLE",
        "actual_kpi_status": "EXACT" if exact else "NOT_ESTIMABLE",
        "reason_codes": reasons, "errors": errors,
        "scope": {"publication_scope_id": scope["publication_scope_id"],
                  "scope_sha256": scope["scope_sha256"],
                  "expected_row_count": expected_count,
                  "measurement_bindings": scope["measurement_bindings"]} if scope else None,
        "measurement_completion_status": "EXACT" if exact else "NOT_ESTIMABLE",
        "publication_recovery_status": "NOT_ASSESSED",
        "publication_recovery_note": "authoritative publication WAL is outside this read-only ledger scope",
        "coverage": {"attempt_run_count": len(by_run), "observed_row_count": len(by_row),
                     "attempt_run_ids": sorted(by_run),
                     "sealed_row_count": len(seals), "linked_row_count": len(links),
                     "unlinked_rows": sorted(set(unlinked_rows)),
                     "ambiguous_rows": sorted(set(ambiguous_rows))},
        "attempts": {"dispatched": len(by_kind["DISPATCH_INTENT"]),
                     "terminal": len(by_kind["TERMINAL"]),
                     "successful": status_counts["SUCCEEDED"],
                     "failed": status_counts["FAILED"],
                     "cancelled": status_counts["CANCELLED"],
                     "unknown": status_counts["UNKNOWN"],
                     "open": sum(e["open_call_count"] for e in evidence_by_row.values()),
                     "retries": sum(e["retry_count"] for e in evidence_by_row.values())},
        "findings": {"duplicate_calls": sorted(duplicate_calls),
                     "orphan_terminals": sorted(orphan_terminals),
                     "aborted_rows": sorted(set(aborted_rows))},
        "usage": {"provenance_counts": {key: provenance_counts[key] for key in sorted(PROVENANCE)},
                  "aggregate_exact": exact},
        "actual_metrics": actual_metrics, "observed_metrics": observed_metrics,
        "rows": row_receipts,
    }
    report["report_sha256"] = compute_readback_report_sha256(report)
    return report


validate_decision_call_ledger = read_decision_call_ledger

__all__ = [
    "READBACK_SCHEMA", "compute_readback_report_sha256", "read_decision_call_ledger",
    "validate_decision_call_ledger", "verify_readback_report_sha256",
]
