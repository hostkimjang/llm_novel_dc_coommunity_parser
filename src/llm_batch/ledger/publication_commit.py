from __future__ import annotations

"""Durable exact-once owner for terminal publication decisions.

Provisional publish contracts may be evaluated repeatedly while evidence is
still changing.  A terminal decision becomes authoritative only when this
module validates the typed contract and records a hash-only receipt plus its
canonical recoverable result row in an append-only fsync WAL owned by the
completed-source writer.
"""

from dataclasses import asdict, dataclass
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from ..promotion_gate import (
    PUBLISH_CONTRACT_VERSION,
    evidence_records_from_payload,
    evaluate_publish_contract,
    grounding_state_from_dict,
)


PUBLICATION_COMMIT_SCHEMA = "publication_decision_commit_v3"
PUBLICATION_COMMIT_OWNER = "expert_main.completed_source_writer"
PUBLICATION_COMMIT_JOURNAL_SCHEMA = "publication_decision_commit_journal_v3"
PUBLICATION_COMMIT_EVENT_SCHEMA = "publication_decision_commit_event_v2"
PUBLICATION_SCOPE_DESCRIPTOR_SCHEMA = "publication_scope_descriptor_v1"
PUBLICATION_TAIL_REPAIR_SCHEMA = "publication_commit_tail_repair_v1"

_PROCESS_LOCK_TIMEOUT_SECONDS = 30.0

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_OUTCOMES = frozenset({"PUBLISH", "HOLD", "ERROR_HOLD"})
_PUBLIC_TITLE_KEYS = ("official_title", "official_novel_title", "resolved_title")
_PUBLIC_URL_KEYS = ("heretic_url", "official_url", "resolved_url")
_ATTEMPT_LOCAL_RUN_META_KEYS = frozenset(
    {
        "run_id",
        "worker_id",
        "worker_log_file",
        "main_log_file",
        "decision_cost_trace",
        "decision_call_ledger",
        "decision_call_ledger_summary",
        "decision_call_attempt_receipt",
        "decision_call_measurement",
        "measurement_execution_source",
        "early_route_measurement",
        "fresh375_run_binding_token",
    }
)


class PublicationCommitError(ValueError):
    """Raised when a terminal publication decision cannot be committed safely."""


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _replace_scope_descriptor_atomically(
    path: Path,
    descriptor: "PublicationScopeDescriptor",
) -> None:
    """Durably install a complete descriptor without exposing a torn final file."""

    payload = (
        json.dumps(
            descriptor.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _replace_bytes_atomically(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
    )
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@contextmanager
def _exclusive_file_lock(path: Path):
    """Serialize registry reload/CAS/append across independent processes.

    The journal contains strict receipt+result frames.  A one-byte sibling lock
    file is used so a zero-length newly-created journal can still be locked on
    Windows.  The lock is held only for the short reload/CAS/fsync critical
    section, so a process crash releases the OS lock automatically.
    """

    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        deadline = time.monotonic() + _PROCESS_LOCK_TIMEOUT_SECONDS
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise PublicationCommitError(
                            f"publication commit journal lock timeout: {lock_path}"
                        ) from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    if time.monotonic() >= deadline:
                        raise PublicationCommitError(
                            f"publication commit journal lock timeout: {lock_path}"
                        ) from exc
                    time.sleep(0.01)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _canonical_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_payload(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _stable_result_payload(result: Mapping[str, Any]) -> Dict[str, Any]:
    stable = _canonical_payload(result)
    if not isinstance(stable, dict):
        raise PublicationCommitError("publication stable result must be an object")
    run_meta = stable.get("run_meta")
    if isinstance(run_meta, dict):
        stable["run_meta"] = {
            key: value
            for key, value in run_meta.items()
            if key not in _ATTEMPT_LOCAL_RUN_META_KEYS
        }
    return stable


def _sha256(value: Any) -> str:
    data = json.dumps(
        _canonical_payload(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _normalize_hex64(value: Any, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _HEX64.fullmatch(text):
        raise PublicationCommitError(f"{field} must be a lowercase sha256")
    return text


def _normalize_nonempty(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PublicationCommitError(f"{field} must be non-empty")
    return text


def _normalize_post_id(value: Any) -> int | str:
    if isinstance(value, bool) or value in (None, ""):
        raise PublicationCommitError("post_id must be non-empty")
    if isinstance(value, int):
        if value <= 0:
            raise PublicationCommitError("post_id must be positive")
        return value
    text = str(value).strip()
    if not text:
        raise PublicationCommitError("post_id must be non-empty")
    try:
        number = int(text)
    except ValueError:
        return text
    if number <= 0:
        raise PublicationCommitError("post_id must be positive")
    return number


def _normalize_input_index(value: Any) -> int:
    if isinstance(value, bool):
        raise PublicationCommitError("input_index must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PublicationCommitError("input_index must be a positive integer") from exc
    if number <= 0:
        raise PublicationCommitError("input_index must be positive")
    return number


def _nonempty_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def build_publication_scope_id(
    *,
    input_file_sha256: Any,
    post_ids: Sequence[Any],
    config_hash: Any,
    release_fingerprint: Any = None,
) -> str:
    input_hash = _normalize_hex64(input_file_sha256, field="input_file_sha256")
    normalized_ids = [_normalize_post_id(value) for value in post_ids]
    if len(normalized_ids) != len(set(normalized_ids)):
        raise PublicationCommitError("publication scope post_ids must be unique")
    config = _normalize_nonempty(config_hash, field="config_hash")
    return _sha256(
        {
            "schema_version": "publication_scope_v1",
            "input_file_sha256": input_hash,
            "post_id_order": normalized_ids,
            "config_hash": config,
            "release_fingerprint": str(release_fingerprint or "").strip() or None,
        }
    )


@dataclass(frozen=True, slots=True)
class PublicationScopeDescriptor:
    schema_version: str
    publication_scope_id: str
    input_file_sha256: str
    post_ids: Tuple[int | str, ...]
    config_hash: str
    release_fingerprint: Optional[str]
    descriptor_sha256: str

    @classmethod
    def create(
        cls,
        *,
        input_file_sha256: Any,
        post_ids: Sequence[Any],
        config_hash: Any,
        release_fingerprint: Any = None,
    ) -> "PublicationScopeDescriptor":
        input_hash = _normalize_hex64(input_file_sha256, field="input_file_sha256")
        normalized_ids = tuple(_normalize_post_id(value) for value in post_ids)
        if len(normalized_ids) != len(set(normalized_ids)):
            raise PublicationCommitError("publication scope post_ids must be unique")
        config = _normalize_nonempty(config_hash, field="config_hash")
        release = str(release_fingerprint or "").strip() or None
        scope_id = build_publication_scope_id(
            input_file_sha256=input_hash,
            post_ids=normalized_ids,
            config_hash=config,
            release_fingerprint=release,
        )
        material = {
            "schema_version": PUBLICATION_SCOPE_DESCRIPTOR_SCHEMA,
            "publication_scope_id": scope_id,
            "input_file_sha256": input_hash,
            "post_ids": list(normalized_ids),
            "config_hash": config,
            "release_fingerprint": release,
        }
        return cls(
            schema_version=PUBLICATION_SCOPE_DESCRIPTOR_SCHEMA,
            publication_scope_id=scope_id,
            input_file_sha256=input_hash,
            post_ids=normalized_ids,
            config_hash=config,
            release_fingerprint=release,
            descriptor_sha256=_sha256(material),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicationScopeDescriptor":
        if not isinstance(value, Mapping):
            raise PublicationCommitError("publication scope descriptor must be an object")
        expected_fields = set(cls.__dataclass_fields__)
        actual_fields = set(value)
        if actual_fields != expected_fields:
            raise PublicationCommitError(
                "publication scope descriptor fields mismatch: "
                f"missing={sorted(expected_fields - actual_fields)}, "
                f"extra={sorted(actual_fields - expected_fields)}"
            )
        post_ids = value.get("post_ids")
        if not isinstance(post_ids, (list, tuple)):
            raise PublicationCommitError("publication scope descriptor post_ids must be a list")
        descriptor = cls(
            schema_version=str(value.get("schema_version") or ""),
            publication_scope_id=str(value.get("publication_scope_id") or ""),
            input_file_sha256=str(value.get("input_file_sha256") or ""),
            post_ids=tuple(post_ids),
            config_hash=str(value.get("config_hash") or ""),
            release_fingerprint=(
                str(value.get("release_fingerprint")).strip()
                if value.get("release_fingerprint") not in (None, "")
                else None
            ),
            descriptor_sha256=str(value.get("descriptor_sha256") or ""),
        )
        descriptor.validate()
        return descriptor

    def validate(self) -> None:
        if self.schema_version != PUBLICATION_SCOPE_DESCRIPTOR_SCHEMA:
            raise PublicationCommitError("publication scope descriptor schema mismatch")
        recreated = type(self).create(
            input_file_sha256=self.input_file_sha256,
            post_ids=self.post_ids,
            config_hash=self.config_hash,
            release_fingerprint=self.release_fingerprint,
        )
        if recreated.publication_scope_id != self.publication_scope_id:
            raise PublicationCommitError("publication scope descriptor scope mismatch")
        if recreated.descriptor_sha256 != self.descriptor_sha256:
            raise PublicationCommitError("publication scope descriptor hash mismatch")

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["post_ids"] = list(self.post_ids)
        return payload

    def expected_post_id(self, input_index: Any) -> int | str:
        index = _normalize_input_index(input_index)
        if index > len(self.post_ids):
            raise PublicationCommitError("publication input_index is outside scope")
        return self.post_ids[index - 1]


def build_publication_scope_descriptor(
    *,
    input_file_sha256: Any,
    post_ids: Sequence[Any],
    config_hash: Any,
    release_fingerprint: Any = None,
) -> PublicationScopeDescriptor:
    return PublicationScopeDescriptor.create(
        input_file_sha256=input_file_sha256,
        post_ids=post_ids,
        config_hash=config_hash,
        release_fingerprint=release_fingerprint,
    )


def _result_identity(result: Mapping[str, Any]) -> Mapping[str, Any]:
    analysis = result.get("analysis_result")
    if isinstance(analysis, Mapping) and isinstance(analysis.get("identity"), Mapping):
        return analysis["identity"]
    identity = result.get("identity")
    return identity if isinstance(identity, Mapping) else {}


def _input_snapshot(result: Mapping[str, Any], *, post_id: int | str) -> Dict[str, Any]:
    return {
        "gallery_id": result.get("gallery_id"),
        "post_id": post_id,
        "title": result.get("title"),
        "post_author": result.get("post_author"),
        "created_at": result.get("created_at"),
        "url": result.get("url"),
        "content": result.get("content"),
        "content_blocks": result.get("content_blocks"),
        "comments": result.get("comments"),
        "comment_metadata": result.get("comment_metadata"),
    }


def _public_projection(identity: Mapping[str, Any]) -> Dict[str, Any]:
    novel = identity.get("novel_identity")
    novel = novel if isinstance(novel, Mapping) else {}
    fields: Dict[str, Any] = {}
    for prefix, source in (("identity", identity), ("novel_identity", novel)):
        for key in (*_PUBLIC_TITLE_KEYS, *_PUBLIC_URL_KEYS):
            fields[f"{prefix}.{key}"] = {
                "present": key in source,
                "value": source.get(key) if key in source else None,
            }
    return fields


def _validate_result_root_public_aliases(
    result: Mapping[str, Any],
    *,
    expected_title: Optional[str],
    expected_url: Optional[str],
) -> None:
    analysis_result = result.get("analysis_result")
    analysis_result = analysis_result if isinstance(analysis_result, Mapping) else {}
    for path, source in (("result", result), ("analysis_result", analysis_result)):
        _validate_projection_mapping(
            source,
            path=path,
            expected_title=expected_title,
            expected_url=expected_url,
        )


def _validate_public_projection(
    identity: Mapping[str, Any],
    *,
    publish_allowed: bool,
    expected_title: Optional[str],
    expected_url: Optional[str],
) -> None:
    novel = identity.get("novel_identity")
    novel = novel if isinstance(novel, Mapping) else {}
    for prefix, source in (("identity", identity), ("novel_identity", novel)):
        _validate_projection_mapping(
            source,
            path=prefix,
            expected_title=expected_title,
            expected_url=expected_url,
        )
    if not publish_allowed and (expected_title is not None or expected_url is not None):
        raise PublicationCommitError("HOLD decision must have null public projection")


def _validate_projection_mapping(
    source: Mapping[str, Any],
    *,
    path: str,
    expected_title: Optional[str],
    expected_url: Optional[str],
) -> None:
    for key in _PUBLIC_TITLE_KEYS:
        if key in source and _nonempty_text(source.get(key)) != expected_title:
            raise PublicationCommitError(
                f"serialized {path}.{key} does not match decision"
            )
    for key in _PUBLIC_URL_KEYS:
        if key in source and _nonempty_text(source.get(key)) != expected_url:
            raise PublicationCommitError(
                f"serialized {path}.{key} does not match decision"
            )


def _validated_typed_decision(
    identity: Mapping[str, Any],
    *,
    expected_post_id: int | str,
) -> Tuple[Dict[str, Any], str, str]:
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, Mapping):
        raise PublicationCommitError("candidate ledger is missing")

    decision = identity.get("promotion_decision")
    ledger_decision = ledger.get("promotion_decision")
    if not isinstance(decision, Mapping) or not isinstance(ledger_decision, Mapping):
        raise PublicationCommitError("typed promotion decision mirrors are missing")
    decision_payload = dict(decision)
    if decision_payload != dict(ledger_decision):
        raise PublicationCommitError("promotion decision mirrors do not match")
    if not isinstance(decision_payload.get("publish_allowed"), bool):
        raise PublicationCommitError("publish_allowed must be a strict boolean")
    if decision_payload.get("bypassed_gate") is not False:
        raise PublicationCommitError("bypassed_gate must be false")

    contract_version = str(identity.get("publish_contract_version") or "").strip()
    if contract_version != PUBLISH_CONTRACT_VERSION:
        raise PublicationCommitError("publish contract version is not authoritative")
    if str(ledger.get("publish_contract_version") or "").strip() != contract_version:
        raise PublicationCommitError("publish contract version mirrors do not match")
    if str(decision_payload.get("contract_version") or "").strip() != contract_version:
        raise PublicationCommitError("decision contract version does not match")

    state_payload = identity.get("promotion_gate_state")
    evidence_payload = identity.get("promotion_gate_evidence")
    if not isinstance(state_payload, Mapping) or not isinstance(evidence_payload, list):
        raise PublicationCommitError("typed state/evidence are missing")
    if dict(state_payload) != ledger.get("promotion_gate_state"):
        raise PublicationCommitError("promotion gate state mirrors do not match")
    if evidence_payload != ledger.get("promotion_gate_evidence"):
        raise PublicationCommitError("promotion gate evidence mirrors do not match")
    typed_state = grounding_state_from_dict(state_payload)
    if _normalize_post_id(typed_state.post_id) != expected_post_id:
        raise PublicationCommitError("typed state post_id does not match result post_id")
    typed_evidence = evidence_records_from_payload(evidence_payload)
    recomputed = evaluate_publish_contract(typed_state, typed_evidence)
    recomputed_decision = recomputed.decision.to_dict()
    if recomputed_decision != decision_payload:
        raise PublicationCommitError("typed state/evidence recompute does not match decision")

    fingerprint = _normalize_hex64(
        identity.get("publish_contract_input_fingerprint"),
        field="publish_contract_input_fingerprint",
    )
    if fingerprint != str(ledger.get("publish_contract_input_fingerprint") or "").strip():
        raise PublicationCommitError("publish contract fingerprint mirrors do not match")
    if fingerprint != str(decision_payload.get("input_fingerprint") or "").strip():
        raise PublicationCommitError("decision fingerprint does not match")
    if fingerprint != recomputed.input_fingerprint:
        raise PublicationCommitError("typed state/evidence fingerprint recompute mismatch")

    trace = identity.get("publish_contract_trace")
    if not isinstance(trace, Mapping) or dict(trace) != ledger.get("publish_contract_trace"):
        raise PublicationCommitError("publish trace mirrors do not match")
    if trace.get("bypassed_gate") is not False:
        raise PublicationCommitError("publish trace bypassed_gate must be false")
    if str(trace.get("input_fingerprint") or "").strip() != fingerprint:
        raise PublicationCommitError("publish trace fingerprint does not match")
    if trace.get("gate_decision") != decision_payload:
        raise PublicationCommitError("publish trace decision does not match")

    publish_ledger = identity.get("publish_ledger")
    if not isinstance(publish_ledger, Mapping) or dict(publish_ledger) != ledger.get("publish_ledger"):
        raise PublicationCommitError("publish ledger mirrors do not match")
    if publish_ledger.get("gate_decision") != decision_payload:
        raise PublicationCommitError("publish ledger decision does not match")
    post_gate = trace.get("post_gate_identity")
    public_publish = publish_ledger.get("public_publish")
    if not isinstance(post_gate, Mapping) or not isinstance(public_publish, Mapping):
        raise PublicationCommitError("post-gate public projection is missing")
    if dict(post_gate) != dict(public_publish):
        raise PublicationCommitError("post-gate and ledger public projections do not match")

    publish_allowed = decision_payload["publish_allowed"]
    expected_title = _nonempty_text(decision_payload.get("official_title")) if publish_allowed else None
    expected_url = _nonempty_text(decision_payload.get("official_url")) if publish_allowed else None
    if publish_allowed and expected_title is None:
        raise PublicationCommitError("PUBLISH decision requires an official title")
    if _nonempty_text(post_gate.get("official_title")) != expected_title:
        raise PublicationCommitError("post-gate official title does not match decision")
    if _nonempty_text(post_gate.get("official_url")) != expected_url:
        raise PublicationCommitError("post-gate official URL does not match decision")
    for path, projection in (
        ("publish_contract_trace.post_gate_identity", post_gate),
        ("publish_ledger.public_publish", public_publish),
    ):
        _validate_projection_mapping(
            projection,
            path=path,
            expected_title=expected_title,
            expected_url=expected_url,
        )
    _validate_public_projection(
        identity,
        publish_allowed=publish_allowed,
        expected_title=expected_title,
        expected_url=expected_url,
    )
    return decision_payload, contract_version, fingerprint


def _validate_error_row_public_null(identity: Mapping[str, Any]) -> None:
    if identity.get("is_relevant") is True:
        raise PublicationCommitError("ERROR_HOLD row cannot be publicly relevant")
    _validate_public_projection(
        identity,
        publish_allowed=False,
        expected_title=None,
        expected_url=None,
    )
    ledger = identity.get("candidate_ledger")
    ledger = ledger if isinstance(ledger, Mapping) else {}
    decision_mirrors: tuple[tuple[str, Any], ...] = (
        ("promotion_decision", identity.get("promotion_decision")),
        ("candidate_ledger.promotion_decision", ledger.get("promotion_decision")),
        (
            "publish_contract_trace.gate_decision",
            (identity.get("publish_contract_trace") or {}).get("gate_decision")
            if isinstance(identity.get("publish_contract_trace"), Mapping)
            else None,
        ),
        (
            "publish_ledger.gate_decision",
            (identity.get("publish_ledger") or {}).get("gate_decision")
            if isinstance(identity.get("publish_ledger"), Mapping)
            else None,
        ),
        (
            "candidate_ledger.publish_contract_trace.gate_decision",
            (ledger.get("publish_contract_trace") or {}).get("gate_decision")
            if isinstance(ledger.get("publish_contract_trace"), Mapping)
            else None,
        ),
        (
            "candidate_ledger.publish_ledger.gate_decision",
            (ledger.get("publish_ledger") or {}).get("gate_decision")
            if isinstance(ledger.get("publish_ledger"), Mapping)
            else None,
        ),
    )
    for path, decision in decision_mirrors:
        if not isinstance(decision, Mapping):
            continue
        if decision.get("publish_allowed") is not False:
            raise PublicationCommitError(
                f"ERROR_HOLD {path}.publish_allowed must be strict false"
            )
        if decision.get("bypassed_gate") is not False:
            raise PublicationCommitError(
                f"ERROR_HOLD {path}.bypassed_gate must be strict false"
            )
        if str(decision.get("status") or "").strip().lower() in {
            "publish",
            "published",
        }:
            raise PublicationCommitError(
                f"ERROR_HOLD {path}.status cannot be publish"
            )
    public_mirrors: tuple[tuple[str, Any], ...] = (
        ("promotion_decision", identity.get("promotion_decision")),
        ("candidate_ledger.promotion_decision", ledger.get("promotion_decision")),
        (
            "publish_contract_trace.gate_decision",
            (identity.get("publish_contract_trace") or {}).get("gate_decision")
            if isinstance(identity.get("publish_contract_trace"), Mapping)
            else None,
        ),
        (
            "publish_contract_trace.post_gate_identity",
            (identity.get("publish_contract_trace") or {}).get("post_gate_identity")
            if isinstance(identity.get("publish_contract_trace"), Mapping)
            else None,
        ),
        (
            "publish_ledger.gate_decision",
            (identity.get("publish_ledger") or {}).get("gate_decision")
            if isinstance(identity.get("publish_ledger"), Mapping)
            else None,
        ),
        (
            "publish_ledger.public_publish",
            (identity.get("publish_ledger") or {}).get("public_publish")
            if isinstance(identity.get("publish_ledger"), Mapping)
            else None,
        ),
        (
            "candidate_ledger.publish_contract_trace.post_gate_identity",
            (ledger.get("publish_contract_trace") or {}).get("post_gate_identity")
            if isinstance(ledger.get("publish_contract_trace"), Mapping)
            else None,
        ),
        (
            "candidate_ledger.publish_ledger.public_publish",
            (ledger.get("publish_ledger") or {}).get("public_publish")
            if isinstance(ledger.get("publish_ledger"), Mapping)
            else None,
        ),
    )
    for path, mirror in public_mirrors:
        if not isinstance(mirror, Mapping):
            continue
        if mirror.get("publish_allowed") is True:
            raise PublicationCommitError(
                f"ERROR_HOLD {path}.publish_allowed must not be true"
            )
        for key in (*_PUBLIC_TITLE_KEYS, *_PUBLIC_URL_KEYS):
            if key in mirror and _nonempty_text(mirror.get(key)) is not None:
                raise PublicationCommitError(
                    f"ERROR_HOLD {path}.{key} must be null"
                )


@dataclass(frozen=True, slots=True)
class PublicationDecisionCommit:
    schema_version: str
    publication_scope_id: str
    attempt_run_id: str
    input_index: int
    post_id: int | str
    owner: str
    commit_index: int
    outcome: str
    publish_allowed: bool
    contract_version: Optional[str]
    contract_input_fingerprint: Optional[str]
    input_sha256: str
    decision_sha256: str
    public_projection_sha256: str
    stable_result_sha256: str
    result_sha256: str
    decision_id: str
    commit_sha256: str

    @classmethod
    def create(
        cls,
        *,
        publication_scope_id: Any,
        attempt_run_id: Any,
        input_index: Any,
        post_id: Any,
        outcome: str,
        publish_allowed: bool,
        contract_version: Optional[str],
        contract_input_fingerprint: Optional[str],
        input_sha256: str,
        decision_sha256: str,
        public_projection_sha256: str,
        stable_result_sha256: str,
        result_sha256: str,
    ) -> "PublicationDecisionCommit":
        scope_id = _normalize_hex64(publication_scope_id, field="publication_scope_id")
        run_id = _normalize_nonempty(attempt_run_id, field="attempt_run_id")
        index = _normalize_input_index(input_index)
        normalized_post_id = _normalize_post_id(post_id)
        if outcome not in _OUTCOMES:
            raise PublicationCommitError("publication decision outcome is invalid")
        if not isinstance(publish_allowed, bool):
            raise PublicationCommitError("publish_allowed must be boolean")
        if (outcome == "PUBLISH") != publish_allowed:
            raise PublicationCommitError("publication outcome/allow mismatch")
        logical_material = {
            "schema_version": PUBLICATION_COMMIT_SCHEMA,
            "publication_scope_id": scope_id,
            "input_index": index,
            "post_id": normalized_post_id,
            "owner": PUBLICATION_COMMIT_OWNER,
            "commit_index": 1,
            "outcome": outcome,
            "publish_allowed": publish_allowed,
            "contract_version": contract_version,
            "contract_input_fingerprint": contract_input_fingerprint,
            "input_sha256": _normalize_hex64(input_sha256, field="input_sha256"),
            "decision_sha256": _normalize_hex64(decision_sha256, field="decision_sha256"),
            "public_projection_sha256": _normalize_hex64(
                public_projection_sha256,
                field="public_projection_sha256",
            ),
            "stable_result_sha256": _normalize_hex64(
                stable_result_sha256,
                field="stable_result_sha256",
            ),
        }
        decision_id = _sha256(logical_material)
        receipt_material = {
            **logical_material,
            "attempt_run_id": run_id,
            # Exact stored-row integrity remains attempt-bound, while the
            # logical terminal publication decision above intentionally does
            # not depend on attempt-local run_meta/log paths.
            "result_sha256": _normalize_hex64(
                result_sha256,
                field="result_sha256",
            ),
            "decision_id": decision_id,
        }
        return cls(
            **receipt_material,
            commit_sha256=_sha256(receipt_material),
        )

    @classmethod
    def from_dict(cls, value: Any) -> "PublicationDecisionCommit":
        if not isinstance(value, Mapping):
            raise PublicationCommitError("publication decision commit must be an object")
        expected_fields = set(cls.__dataclass_fields__)
        actual_fields = set(value)
        if actual_fields != expected_fields:
            raise PublicationCommitError(
                "publication decision commit fields mismatch: "
                f"missing={sorted(expected_fields - actual_fields)}, "
                f"extra={sorted(actual_fields - expected_fields)}"
            )
        receipt = cls(**dict(value))
        receipt.validate()
        return receipt

    def validate(self) -> None:
        if self.schema_version != PUBLICATION_COMMIT_SCHEMA:
            raise PublicationCommitError("publication decision commit schema mismatch")
        if self.owner != PUBLICATION_COMMIT_OWNER:
            raise PublicationCommitError("publication decision commit owner mismatch")
        if self.commit_index != 1:
            raise PublicationCommitError("publication decision commit index must be 1")
        recreated = type(self).create(
            publication_scope_id=self.publication_scope_id,
            attempt_run_id=self.attempt_run_id,
            input_index=self.input_index,
            post_id=self.post_id,
            outcome=self.outcome,
            publish_allowed=self.publish_allowed,
            contract_version=self.contract_version,
            contract_input_fingerprint=self.contract_input_fingerprint,
            input_sha256=self.input_sha256,
            decision_sha256=self.decision_sha256,
            public_projection_sha256=self.public_projection_sha256,
            stable_result_sha256=self.stable_result_sha256,
            result_sha256=self.result_sha256,
        )
        if recreated.decision_id != self.decision_id:
            raise PublicationCommitError("publication decision id mismatch")
        if recreated.commit_sha256 != self.commit_sha256:
            raise PublicationCommitError("publication decision commit hash mismatch")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_publication_decision_commit(
    result: Mapping[str, Any],
    *,
    publication_scope_id: Any,
    attempt_run_id: Any,
    input_index: Any,
    post_id: Any,
) -> PublicationDecisionCommit:
    if not isinstance(result, Mapping):
        raise PublicationCommitError("publication result must be an object")
    normalized_post_id = _normalize_post_id(post_id)
    if _normalize_post_id(result.get("post_id")) != normalized_post_id:
        raise PublicationCommitError("result post_id does not match commit post_id")
    identity = _result_identity(result)
    if bool(result.get("error")):
        _validate_error_row_public_null(identity)
        decision_payload: Dict[str, Any] = {
            "status": "error_hold",
            "publish_allowed": False,
            "reason_code": "pipeline_error",
        }
        outcome = "ERROR_HOLD"
        publish_allowed = False
        contract_version: Optional[str] = None
        contract_fingerprint: Optional[str] = None
    else:
        decision_payload, contract_version, contract_fingerprint = _validated_typed_decision(
            identity,
            expected_post_id=normalized_post_id,
        )
        publish_allowed = bool(decision_payload["publish_allowed"])
        outcome = "PUBLISH" if publish_allowed else "HOLD"
    expected_public_title = (
        _nonempty_text(decision_payload.get("official_title"))
        if publish_allowed
        else None
    )
    expected_public_url = (
        _nonempty_text(decision_payload.get("official_url"))
        if publish_allowed
        else None
    )
    _validate_result_root_public_aliases(
        result,
        expected_title=expected_public_title,
        expected_url=expected_public_url,
    )
    return PublicationDecisionCommit.create(
        publication_scope_id=publication_scope_id,
        attempt_run_id=attempt_run_id,
        input_index=input_index,
        post_id=normalized_post_id,
        outcome=outcome,
        publish_allowed=publish_allowed,
        contract_version=contract_version,
        contract_input_fingerprint=contract_fingerprint,
        input_sha256=_sha256(_input_snapshot(result, post_id=normalized_post_id)),
        decision_sha256=_sha256(decision_payload),
        public_projection_sha256=_sha256(_public_projection(identity)),
        stable_result_sha256=_sha256(_stable_result_payload(result)),
        result_sha256=_sha256(result),
    )


def validate_publication_result_commit(
    result: Mapping[str, Any],
    receipt: PublicationDecisionCommit | Mapping[str, Any],
    *,
    expected_scope_id: Any = None,
    expected_input_index: Any = None,
    expected_post_id: Any = None,
) -> PublicationDecisionCommit:
    authoritative = (
        receipt
        if isinstance(receipt, PublicationDecisionCommit)
        else PublicationDecisionCommit.from_dict(receipt)
    )
    authoritative.validate()
    if expected_scope_id is not None and authoritative.publication_scope_id != _normalize_hex64(
        expected_scope_id,
        field="expected_scope_id",
    ):
        raise PublicationCommitError("publication scope id mismatch")
    if expected_input_index is not None and authoritative.input_index != _normalize_input_index(
        expected_input_index
    ):
        raise PublicationCommitError("publication input index mismatch")
    if expected_post_id is not None and authoritative.post_id != _normalize_post_id(expected_post_id):
        raise PublicationCommitError("publication post_id mismatch")
    recomputed = compute_publication_decision_commit(
        result,
        publication_scope_id=authoritative.publication_scope_id,
        attempt_run_id=authoritative.attempt_run_id,
        input_index=authoritative.input_index,
        post_id=authoritative.post_id,
    )
    if recomputed.decision_id != authoritative.decision_id:
        raise PublicationCommitError("publication decision commit no longer matches the row")
    if recomputed.commit_sha256 != authoritative.commit_sha256:
        raise PublicationCommitError(
            "publication stored result no longer matches the receipt"
        )
    return authoritative


def validate_publication_result_decision(
    result: Mapping[str, Any],
    receipt: PublicationDecisionCommit | Mapping[str, Any],
    *,
    expected_scope_id: Any = None,
    expected_input_index: Any = None,
    expected_post_id: Any = None,
) -> PublicationDecisionCommit:
    """Validate logical decision equivalence without claiming stored-row identity."""

    authoritative = (
        receipt
        if isinstance(receipt, PublicationDecisionCommit)
        else PublicationDecisionCommit.from_dict(receipt)
    )
    authoritative.validate()
    if expected_scope_id is not None and authoritative.publication_scope_id != _normalize_hex64(
        expected_scope_id,
        field="expected_scope_id",
    ):
        raise PublicationCommitError("publication scope id mismatch")
    if expected_input_index is not None and authoritative.input_index != _normalize_input_index(
        expected_input_index
    ):
        raise PublicationCommitError("publication input index mismatch")
    if expected_post_id is not None and authoritative.post_id != _normalize_post_id(expected_post_id):
        raise PublicationCommitError("publication post_id mismatch")
    recomputed = compute_publication_decision_commit(
        result,
        publication_scope_id=authoritative.publication_scope_id,
        attempt_run_id=authoritative.attempt_run_id,
        input_index=authoritative.input_index,
        post_id=authoritative.post_id,
    )
    if recomputed.decision_id != authoritative.decision_id:
        raise PublicationCommitError(
            "publication terminal decision no longer matches the authoritative row"
        )
    return authoritative


class PublicationCommitRegistry:
    """Append-only fsync CAS journal keyed by (scope_id, post_id)."""

    def __init__(
        self,
        path: str | Path,
        *,
        scope_descriptor: PublicationScopeDescriptor | Mapping[str, Any],
        create_new: bool,
    ) -> None:
        self.path = Path(path).resolve()
        self.scope_descriptor = (
            scope_descriptor
            if isinstance(scope_descriptor, PublicationScopeDescriptor)
            else PublicationScopeDescriptor.from_dict(scope_descriptor)
        )
        self.scope_descriptor.validate()
        self.publication_scope_id = self.scope_descriptor.publication_scope_id
        self.scope_descriptor_path = self.path.with_name(self.path.name + ".scope.json")
        self._lock = threading.RLock()
        self._by_post_id: Dict[int | str, PublicationDecisionCommit] = {}
        self._by_input_index: Dict[int, int | str] = {}
        self._result_by_post_id: Dict[int | str, Dict[str, Any]] = {}
        self.tail_repair_dir = self.path.with_name(self.path.name + ".tail_repairs")
        self._validated_size_bytes = 0
        self._validated_line_count = 0
        self._validated_tail_anchor_sha256 = hashlib.sha256(b"").hexdigest()
        self._journal_file_identity: tuple[int, int] | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.path):
            if create_new:
                if self.path.exists():
                    raise FileExistsError(self.path)
                descriptor_needs_install = not self.scope_descriptor_path.exists()
                if not descriptor_needs_install:
                    try:
                        descriptor_payload = json.loads(
                            self.scope_descriptor_path.read_text(encoding="utf-8")
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # The journal does not exist, so this can only be a
                        # descriptor-write crash residue.  No committed event
                        # can be hidden by replacing the torn sidecar.
                        descriptor_needs_install = True
                    else:
                        try:
                            existing_descriptor = PublicationScopeDescriptor.from_dict(
                                descriptor_payload
                            )
                        except PublicationCommitError as exc:
                            raise PublicationCommitError(
                                f"invalid publication scope descriptor: {exc}"
                            ) from exc
                        if existing_descriptor.to_dict() != self.scope_descriptor.to_dict():
                            raise PublicationCommitError(
                                "publication scope descriptor does not match requested scope"
                            )
                if descriptor_needs_install:
                    _replace_scope_descriptor_atomically(
                        self.scope_descriptor_path,
                        self.scope_descriptor,
                    )
                with self.path.open("x", encoding="utf-8", newline="\n") as handle:
                    handle.flush()
                    os.fsync(handle.fileno())
                _fsync_directory(self.path.parent)
            elif not self.path.exists():
                raise PublicationCommitError(f"publication commit journal missing: {self.path}")
            if not self.scope_descriptor_path.exists():
                raise PublicationCommitError(
                    f"publication scope descriptor missing: {self.scope_descriptor_path}"
                )
            try:
                stored_descriptor = PublicationScopeDescriptor.from_dict(
                    json.loads(self.scope_descriptor_path.read_text(encoding="utf-8"))
                )
            except (json.JSONDecodeError, PublicationCommitError) as exc:
                raise PublicationCommitError(
                    f"invalid publication scope descriptor: {exc}"
                ) from exc
            if stored_descriptor.to_dict() != self.scope_descriptor.to_dict():
                raise PublicationCommitError(
                    "publication scope descriptor does not match requested scope"
                )
            self._load()

    @staticmethod
    def _file_identity(stat_result: os.stat_result) -> tuple[int, int]:
        return (int(stat_result.st_dev), int(stat_result.st_ino))

    def _parse_complete_frames(
        self,
        raw: bytes,
        *,
        line_number_base: int,
        initial_by_post_id: Mapping[int | str, PublicationDecisionCommit],
        initial_by_input_index: Mapping[int, int | str],
        initial_results: Mapping[int | str, Mapping[str, Any]],
    ) -> tuple[
        Dict[int | str, PublicationDecisionCommit],
        Dict[int, int | str],
        Dict[int | str, Dict[str, Any]],
        int,
    ]:
        if raw and not raw.endswith(b"\n"):
            raise PublicationCommitError(
                "publication commit parser received a non-newline frame"
            )
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise PublicationCommitError(
                f"publication commit journal is not valid UTF-8: {exc}"
            ) from exc
        by_post_id = dict(initial_by_post_id)
        by_input_index = dict(initial_by_input_index)
        results = {
            post_id: dict(result)
            for post_id, result in initial_results.items()
        }
        for offset, line in enumerate(text.splitlines(), 1):
            line_number = line_number_base + offset
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, Mapping):
                    raise PublicationCommitError(
                        "publication commit event must be an object"
                    )
                if set(payload) != {"schema_version", "receipt", "result"}:
                    raise PublicationCommitError(
                        "publication commit event fields mismatch"
                    )
                if payload.get("schema_version") != PUBLICATION_COMMIT_EVENT_SCHEMA:
                    raise PublicationCommitError(
                        "publication commit event schema mismatch"
                    )
                result = payload.get("result")
                if not isinstance(result, Mapping):
                    raise PublicationCommitError(
                        "publication commit event result must be an object"
                    )
                receipt = PublicationDecisionCommit.from_dict(payload.get("receipt"))
                validate_publication_result_commit(result, receipt)
            except (json.JSONDecodeError, PublicationCommitError) as exc:
                raise PublicationCommitError(
                    f"invalid publication commit journal line {line_number}: {exc}"
                ) from exc
            if receipt.publication_scope_id != self.publication_scope_id:
                raise PublicationCommitError("mixed publication scope in commit journal")
            expected_post_id = self.scope_descriptor.expected_post_id(
                receipt.input_index
            )
            if receipt.post_id != expected_post_id:
                raise PublicationCommitError(
                    "publication journal receipt is outside scope membership"
                )
            if receipt.post_id in by_post_id:
                raise PublicationCommitError(
                    "duplicate post_id in publication commit journal"
                )
            if receipt.input_index in by_input_index:
                raise PublicationCommitError(
                    "duplicate input_index in publication commit journal"
                )
            by_post_id[receipt.post_id] = receipt
            by_input_index[receipt.input_index] = receipt.post_id
            results[receipt.post_id] = dict(result)
        return (
            by_post_id,
            by_input_index,
            results,
            line_number_base + raw.count(b"\n"),
        )

    def _write_tail_repair_record(
        self,
        *,
        original_size_bytes: int,
        retained_size_bytes: int,
        retained_prefix_sha256: str,
        discarded_tail: bytes,
    ) -> Dict[str, Any]:
        tail_sha256 = hashlib.sha256(discarded_tail).hexdigest()
        repair_id = hashlib.sha256(
            (
                f"{self.publication_scope_id}:{original_size_bytes}:"
                f"{retained_size_bytes}:{retained_prefix_sha256}:"
                f"{self.scope_descriptor.descriptor_sha256}:{tail_sha256}"
            ).encode("utf-8")
        ).hexdigest()
        record = {
            "schema_version": PUBLICATION_TAIL_REPAIR_SCHEMA,
            "repair_id": repair_id,
            "publication_scope_id": self.publication_scope_id,
            "scope_descriptor_sha256": self.scope_descriptor.descriptor_sha256,
            "journal_name": self.path.name,
            "original_size_bytes": original_size_bytes,
            "retained_size_bytes": retained_size_bytes,
            "retained_prefix_sha256": retained_prefix_sha256,
            "discarded_tail_bytes": len(discarded_tail),
            "discarded_tail_sha256": tail_sha256,
            "commit_point_policy": "newline_terminated_valid_frame",
            "repaired_at_unix_ns": time.time_ns(),
        }
        repair_path = self.tail_repair_dir / f"{repair_id}.json"
        _replace_bytes_atomically(
            repair_path,
            (
                json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8"),
        )
        return record

    def _repair_uncommitted_tail(
        self,
        *,
        original_raw: bytes,
        retained_size_bytes: int,
    ) -> None:
        discarded_tail = original_raw[retained_size_bytes:]
        if not discarded_tail:
            return
        self._write_tail_repair_record(
            original_size_bytes=len(original_raw),
            retained_size_bytes=retained_size_bytes,
            retained_prefix_sha256=hashlib.sha256(
                original_raw[:retained_size_bytes]
            ).hexdigest(),
            discarded_tail=discarded_tail,
        )
        with self.path.open("r+b") as handle:
            handle.truncate(retained_size_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.path.parent)

    def _bind_validated_file(self, *, size_bytes: int, line_count: int) -> None:
        stat_result = self.path.stat()
        if stat_result.st_size != size_bytes:
            raise PublicationCommitError(
                "publication commit journal size changed during validation"
            )
        anchor_size = min(4096, size_bytes)
        with self.path.open("rb") as handle:
            if anchor_size:
                handle.seek(size_bytes - anchor_size)
                anchor = handle.read(anchor_size)
            else:
                anchor = b""
        self._validated_size_bytes = size_bytes
        self._validated_line_count = line_count
        self._validated_tail_anchor_sha256 = hashlib.sha256(anchor).hexdigest()
        self._journal_file_identity = self._file_identity(stat_result)

    def _validate_cached_prefix_binding(self) -> bytes:
        stat_result = self.path.stat()
        current_identity = self._file_identity(stat_result)
        if (
            self._journal_file_identity is not None
            and current_identity != self._journal_file_identity
            and self._journal_file_identity != (0, 0)
            and current_identity != (0, 0)
        ):
            raise PublicationCommitError(
                "publication commit journal file identity changed; reopen required"
            )
        if stat_result.st_size < self._validated_size_bytes:
            raise PublicationCommitError(
                "publication commit journal shrank below the validated prefix"
            )
        anchor_size = min(4096, self._validated_size_bytes)
        with self.path.open("rb") as handle:
            if anchor_size:
                handle.seek(self._validated_size_bytes - anchor_size)
                anchor = handle.read(anchor_size)
            else:
                anchor = b""
            handle.seek(self._validated_size_bytes)
            new_raw = handle.read()
        if hashlib.sha256(anchor).hexdigest() != self._validated_tail_anchor_sha256:
            raise PublicationCommitError(
                "publication commit journal validated prefix tail changed"
            )
        return new_raw

    def _load(self) -> None:
        """Full validation used on open; repairs only an uncommitted final suffix."""

        with self._lock:
            raw = self.path.read_bytes()
            if raw and not raw.endswith(b"\n"):
                retained_size = raw.rfind(b"\n") + 1
                retained_raw = raw[:retained_size]
                parsed = self._parse_complete_frames(
                    retained_raw,
                    line_number_base=0,
                    initial_by_post_id={},
                    initial_by_input_index={},
                    initial_results={},
                )
                self._repair_uncommitted_tail(
                    original_raw=raw,
                    retained_size_bytes=retained_size,
                )
                raw = retained_raw
            else:
                parsed = self._parse_complete_frames(
                    raw,
                    line_number_base=0,
                    initial_by_post_id={},
                    initial_by_input_index={},
                    initial_results={},
                )
            (
                self._by_post_id,
                self._by_input_index,
                self._result_by_post_id,
                line_count,
            ) = parsed
            self._bind_validated_file(
                size_bytes=len(raw),
                line_count=line_count,
            )

    def _ingest_new_frames(self) -> None:
        """Validate only bytes appended since this instance's trusted offset."""

        new_raw = self._validate_cached_prefix_binding()
        if not new_raw:
            return
        original_size = self._validated_size_bytes + len(new_raw)
        if not new_raw.endswith(b"\n"):
            relative_retained_size = new_raw.rfind(b"\n") + 1
            complete_new_raw = new_raw[:relative_retained_size]
        else:
            relative_retained_size = len(new_raw)
            complete_new_raw = new_raw
        parsed = self._parse_complete_frames(
            complete_new_raw,
            line_number_base=self._validated_line_count,
            initial_by_post_id=self._by_post_id,
            initial_by_input_index=self._by_input_index,
            initial_results=self._result_by_post_id,
        )
        if relative_retained_size != len(new_raw):
            full_raw = self.path.read_bytes()
            if len(full_raw) != original_size:
                raise PublicationCommitError(
                    "publication commit journal changed during tail repair"
                )
            self._repair_uncommitted_tail(
                original_raw=full_raw,
                retained_size_bytes=self._validated_size_bytes
                + relative_retained_size,
            )
        (
            self._by_post_id,
            self._by_input_index,
            self._result_by_post_id,
            line_count,
        ) = parsed
        self._bind_validated_file(
            size_bytes=self._validated_size_bytes + relative_retained_size,
            line_count=line_count,
        )

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._by_post_id)

    def receipts(self) -> list[PublicationDecisionCommit]:
        with self._lock:
            return sorted(self._by_post_id.values(), key=lambda item: item.input_index)

    def get(self, post_id: Any) -> Optional[PublicationDecisionCommit]:
        with self._lock:
            return self._by_post_id.get(_normalize_post_id(post_id))

    def result(self, post_id: Any) -> Optional[Dict[str, Any]]:
        with self._lock:
            value = self._result_by_post_id.get(_normalize_post_id(post_id))
            return json.loads(json.dumps(value, ensure_ascii=False)) if value is not None else None

    def events(self) -> list[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
                    "receipt": receipt.to_dict(),
                    "result": json.loads(
                        json.dumps(self._result_by_post_id[receipt.post_id], ensure_ascii=False)
                    ),
                }
                for receipt in self.receipts()
            ]

    def tail_repair_records(self) -> list[Dict[str, Any]]:
        records: list[Dict[str, Any]] = []
        if not self.tail_repair_dir.is_dir():
            return records
        for path in sorted(self.tail_repair_dir.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PublicationCommitError(
                    f"invalid publication tail repair record {path}: {exc}"
                ) from exc
            if (
                not isinstance(value, Mapping)
                or value.get("schema_version") != PUBLICATION_TAIL_REPAIR_SCHEMA
                or value.get("publication_scope_id") != self.publication_scope_id
            ):
                raise PublicationCommitError(
                    f"invalid publication tail repair record binding: {path}"
                )
            records.append(dict(value))
        return records

    @property
    def tail_repair_count(self) -> int:
        return len(self.tail_repair_records())

    def record(
        self,
        candidate: PublicationDecisionCommit,
        *,
        result: Mapping[str, Any],
    ) -> Tuple[PublicationDecisionCommit, bool]:
        canonical_result = _canonical_payload(result)
        if not isinstance(canonical_result, Mapping):
            raise PublicationCommitError("publication result snapshot must be an object")
        candidate.validate()
        validate_publication_result_commit(canonical_result, candidate)
        if candidate.publication_scope_id != self.publication_scope_id:
            raise PublicationCommitError("candidate publication scope does not match journal")
        expected_post_id = self.scope_descriptor.expected_post_id(candidate.input_index)
        if candidate.post_id != expected_post_id:
            raise PublicationCommitError(
                "candidate publication post_id does not match scope membership"
            )
        with self._lock:
            with _exclusive_file_lock(self.path):
                # Another process or registry instance may have appended since
                # this object was constructed.  Validate only the new binary
                # frames under the OS lock; constructor/reopen performs the one
                # full scan.  This keeps a single writer O(n) instead of O(n²).
                self._ingest_new_frames()
                existing = self._by_post_id.get(candidate.post_id)
                if existing is not None:
                    if (
                        existing.decision_id == candidate.decision_id
                        and existing.input_index == candidate.input_index
                    ):
                        return existing, False
                    raise PublicationCommitError(
                        "conflicting terminal publication decision for scope/post_id"
                    )
                index_owner = self._by_input_index.get(candidate.input_index)
                if index_owner is not None and index_owner != candidate.post_id:
                    raise PublicationCommitError(
                        "publication input_index already belongs to another post_id"
                    )
                event = {
                    "schema_version": PUBLICATION_COMMIT_EVENT_SCHEMA,
                    "receipt": candidate.to_dict(),
                    "result": canonical_result,
                }
                line = (
                    json.dumps(
                    event,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
                with self.path.open("ab") as handle:
                    handle.write(line)
                    handle.flush()
                    os.fsync(handle.fileno())
                self._by_post_id[candidate.post_id] = candidate
                self._by_input_index[candidate.input_index] = candidate.post_id
                self._result_by_post_id[candidate.post_id] = dict(event["result"])
                self._validated_line_count += 1
                self._bind_validated_file(
                    size_bytes=self._validated_size_bytes + len(line),
                    line_count=self._validated_line_count,
                )
                return candidate, True


def commit_publication_result(
    result: Mapping[str, Any],
    *,
    registry: PublicationCommitRegistry,
    attempt_run_id: Any,
    input_index: Any,
    post_id: Any,
) -> Tuple[PublicationDecisionCommit, bool]:
    canonical_result = _canonical_payload(result)
    if not isinstance(canonical_result, Mapping):
        raise PublicationCommitError("publication result snapshot must be an object")
    candidate = compute_publication_decision_commit(
        canonical_result,
        publication_scope_id=registry.publication_scope_id,
        attempt_run_id=attempt_run_id,
        input_index=input_index,
        post_id=post_id,
    )
    authoritative, created = registry.record(candidate, result=canonical_result)
    if created:
        validate_publication_result_commit(
            canonical_result,
            authoritative,
            expected_scope_id=registry.publication_scope_id,
            expected_input_index=input_index,
            expected_post_id=post_id,
        )
    else:
        validate_publication_result_decision(
            canonical_result,
            authoritative,
            expected_scope_id=registry.publication_scope_id,
            expected_input_index=input_index,
            expected_post_id=post_id,
        )
        canonical_stored_result = registry.result(post_id)
        if canonical_stored_result is None:
            raise PublicationCommitError(
                "authoritative publication receipt has no stored WAL result"
            )
        validate_publication_result_commit(
            canonical_stored_result,
            authoritative,
            expected_scope_id=registry.publication_scope_id,
            expected_input_index=input_index,
            expected_post_id=post_id,
        )
    return authoritative, created


def audit_publication_commits(
    rows: Any,
    receipts: Iterable[PublicationDecisionCommit | Mapping[str, Any]],
    *,
    expected_post_ids: Optional[Sequence[Any]] = None,
    expected_scope_id: Any = None,
) -> Dict[str, Any]:
    if not isinstance(rows, list):
        raise PublicationCommitError("publication audit rows must be a list")
    parsed: list[PublicationDecisionCommit] = []
    invalid_receipts: list[Dict[str, Any]] = []
    for receipt_number, value in enumerate(receipts, 1):
        try:
            receipt = (
                value
                if isinstance(value, PublicationDecisionCommit)
                else PublicationDecisionCommit.from_dict(value)
            )
            receipt.validate()
            parsed.append(receipt)
        except PublicationCommitError as exc:
            invalid_receipts.append(
                {"receipt_number": receipt_number, "error": str(exc)}
            )

    receipt_by_post: Dict[int | str, PublicationDecisionCommit] = {}
    duplicate_post_ids: list[int | str] = []
    index_to_post: Dict[int, int | str] = {}
    duplicate_input_indices: list[int] = []
    scope_ids = sorted({item.publication_scope_id for item in parsed})
    for receipt in parsed:
        if receipt.post_id in receipt_by_post:
            duplicate_post_ids.append(receipt.post_id)
        else:
            receipt_by_post[receipt.post_id] = receipt
        if receipt.input_index in index_to_post:
            duplicate_input_indices.append(receipt.input_index)
        else:
            index_to_post[receipt.input_index] = receipt.post_id

    row_by_post: Dict[int | str, Mapping[str, Any]] = {}
    duplicate_row_post_ids: list[int | str] = []
    invalid_rows: list[Dict[str, Any]] = []
    for row_number, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            invalid_rows.append({"row_number": row_number, "error": "row is not object"})
            continue
        try:
            post_id = _normalize_post_id(row.get("post_id"))
        except PublicationCommitError as exc:
            invalid_rows.append({"row_number": row_number, "error": str(exc)})
            continue
        if post_id in row_by_post:
            duplicate_row_post_ids.append(post_id)
        else:
            row_by_post[post_id] = row

    row_ids = set(row_by_post)
    receipt_ids = set(receipt_by_post)
    missing_receipt_post_ids = sorted(row_ids - receipt_ids, key=str)
    orphan_receipt_post_ids = sorted(receipt_ids - row_ids, key=str)
    valid_commit_count = 0
    for post_id in sorted(row_ids & receipt_ids, key=str):
        try:
            validate_publication_result_commit(row_by_post[post_id], receipt_by_post[post_id])
            valid_commit_count += 1
        except PublicationCommitError as exc:
            invalid_rows.append({"post_id": post_id, "error": str(exc)})

    expected = (
        [_normalize_post_id(value) for value in expected_post_ids]
        if expected_post_ids is not None
        else None
    )
    expected_duplicate_post_ids: list[int | str] = []
    if expected is not None:
        seen_expected: set[int | str] = set()
        for post_id in expected:
            if post_id in seen_expected:
                expected_duplicate_post_ids.append(post_id)
            seen_expected.add(post_id)
    expected_set = set(expected or [])
    missing_expected_post_ids = (
        sorted(expected_set - row_ids, key=str) if expected is not None else []
    )
    extra_row_post_ids = (
        sorted(row_ids - expected_set, key=str) if expected is not None else []
    )
    ordered_receipt_post_ids = [
        item.post_id for item in sorted(parsed, key=lambda item: item.input_index)
    ]
    post_id_order_match = expected is None or ordered_receipt_post_ids == expected
    expected_indices = list(range(1, len(parsed) + 1))
    actual_indices = sorted(item.input_index for item in parsed)
    input_indices_contiguous = actual_indices == expected_indices
    expected_scope = (
        _normalize_hex64(expected_scope_id, field="expected_scope_id")
        if expected_scope_id is not None
        else None
    )
    scope_match = (
        len(scope_ids) <= 1
        and (expected_scope is None or scope_ids == [expected_scope])
    )

    blockers = any(
        (
            invalid_receipts,
            invalid_rows,
            duplicate_post_ids,
            duplicate_input_indices,
            duplicate_row_post_ids,
            expected_duplicate_post_ids,
            missing_receipt_post_ids,
            orphan_receipt_post_ids,
            missing_expected_post_ids,
            extra_row_post_ids,
        )
    ) or not post_id_order_match or not input_indices_contiguous or not scope_match
    return {
        "schema_version": "publication_commit_audit_v2",
        "gate": "NO-GO" if blockers else "GO",
        "row_count": len(rows),
        "receipt_count": len(parsed),
        "valid_commit_count": valid_commit_count,
        "scope_ids": scope_ids,
        "scope_match": scope_match,
        "post_id_order_match": post_id_order_match,
        "input_indices_contiguous": input_indices_contiguous,
        "invalid_receipts": invalid_receipts,
        "invalid_rows": invalid_rows,
        "duplicate_post_ids": sorted(set(duplicate_post_ids), key=str),
        "duplicate_input_indices": sorted(set(duplicate_input_indices)),
        "duplicate_row_post_ids": sorted(set(duplicate_row_post_ids), key=str),
        "expected_duplicate_post_ids": sorted(set(expected_duplicate_post_ids), key=str),
        "missing_receipt_post_ids": missing_receipt_post_ids,
        "orphan_receipt_post_ids": orphan_receipt_post_ids,
        "missing_expected_post_ids": missing_expected_post_ids,
        "extra_row_post_ids": extra_row_post_ids,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
