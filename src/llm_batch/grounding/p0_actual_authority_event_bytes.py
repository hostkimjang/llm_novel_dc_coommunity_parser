"""Byte-exact annotation-event verifier for the actual-P0 authority packet.

This module verifies canonical JSONL framing, annotation journal chains, sealed
prefixes, and reconstructed target heads.  It deliberately does not validate a
trusted directory root, an external owner anchor, or runtime write denial, so
its receipt can never open the actual-P0 gate.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from llm_batch.grounding import p0_actual_registry_contract as registry
from llm_batch.grounding.p0_actual_authority_contract import (
    P0ActualAuthorityError,
    canonical_sha256,
    validate_checkpoint,
    validate_head_map,
)


EVENT_BYTES_RECEIPT_SCHEMA = "p0_actual_annotation_event_bytes_receipt_v1"
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise P0ActualAuthorityError(f"duplicate JSON key in annotation event: {key}")
        value[key] = item
    return value


def _reject_nonfinite_constant(token: str) -> None:
    raise P0ActualAuthorityError(
        f"annotation event JSON must not contain non-finite constant: {token}"
    )


def _is_reparse(stat_value: os.stat_result) -> bool:
    return bool(
        getattr(stat_value, "st_file_attributes", 0)
        & _FILE_ATTRIBUTE_REPARSE_POINT
    )


def _rfc3339(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _stable_regular_file_bytes(path: str | Path) -> tuple[Path, bytes]:
    requested = Path(path).absolute()
    for component in reversed((requested, *requested.parents)):
        try:
            observed = component.lstat()
        except OSError as exc:
            raise P0ActualAuthorityError(
                f"annotation event path component is unavailable: {component}"
            ) from exc
        if component.is_symlink() or _is_reparse(observed):
            raise P0ActualAuthorityError(
                f"annotation event path must not traverse symlink/reparse points: {component}"
            )
    before = requested.lstat()
    if not requested.is_file() or requested.is_symlink() or _is_reparse(before):
        raise P0ActualAuthorityError("annotation event path must be a regular file")
    if before.st_nlink != 1:
        raise P0ActualAuthorityError("annotation event file must not have hard-link aliases")

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(requested, flags)
    try:
        opened = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise P0ActualAuthorityError("annotation event file changed before read")
        if opened.st_nlink != 1:
            raise P0ActualAuthorityError(
                "annotation event file must not have hard-link aliases"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read()
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    path_after = requested.lstat()
    if (
        (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or (after.st_dev, after.st_ino) != (path_after.st_dev, path_after.st_ino)
        or len(raw) != opened.st_size
    ):
        raise P0ActualAuthorityError("annotation event file changed during read")
    return requested, raw


def _canonical_event_rows(
    raw: bytes,
    *,
    expected_event_origin: str,
) -> tuple[list[dict[str, Any]], list[bytes]]:
    if not raw:
        raise P0ActualAuthorityError("annotation event JSONL must be non-empty")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise P0ActualAuthorityError("annotation event JSONL must not contain UTF-8 BOM")
    if b"\r" in raw:
        raise P0ActualAuthorityError("annotation event JSONL must use LF framing")
    if any(marker in raw for marker in (b"\x0b", b"\x0c", b"\x1c", b"\x1d", b"\x1e", b"\x85")):
        raise P0ActualAuthorityError(
            "annotation event JSONL contains a non-LF record boundary"
        )
    if not raw.endswith(b"\n"):
        raise P0ActualAuthorityError("annotation event JSONL requires final LF")
    lines = raw.splitlines(keepends=True)
    if any(not line.endswith(b"\n") for line in lines):
        raise P0ActualAuthorityError(
            "annotation event JSONL contains a non-LF record boundary"
        )
    if any(line == b"\n" for line in lines):
        raise P0ActualAuthorityError("annotation event JSONL must not contain blank rows")

    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        try:
            decoded = line[:-1].decode("utf-8")
            value = json.loads(
                decoded,
                object_pairs_hook=_duplicate_rejecting_object,
                parse_constant=_reject_nonfinite_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P0ActualAuthorityError(
                f"annotation event row {index} is not strict UTF-8 JSON"
            ) from exc
        if not isinstance(value, dict):
            raise P0ActualAuthorityError(
                f"annotation event row {index} must be an object"
            )
        canonical = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        if line != canonical:
            raise P0ActualAuthorityError(
                f"annotation event row {index} is not canonical JSON"
            )
        try:
            rows.append(registry._validate_annotation_event(value, expected_event_origin))
        except registry.P0ActualContractError as exc:
            raise P0ActualAuthorityError(
                f"annotation event row {index} contract failure: {exc}"
            ) from exc

    try:
        registry._validate_event_chains(rows)
    except registry.P0ActualContractError as exc:
        raise P0ActualAuthorityError(f"annotation journal chain failure: {exc}") from exc
    last_by_journal: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        previous = last_by_journal.get(row["journal_id"])
        if row["journal_sequence"] == 1:
            if previous is not None:
                raise P0ActualAuthorityError(
                    "annotation event file order restarts an existing journal"
                )
        elif previous is None or (
            row["journal_sequence"] != previous["journal_sequence"] + 1
            or row["previous_event_id"] != previous["event_id"]
            or row["previous_event_sha256"] != previous["event_sha256"]
        ):
            raise P0ActualAuthorityError(
                "annotation event file order is not prefix-closed"
            )
        last_by_journal[row["journal_id"]] = row
    target_journals: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        target = (row["target_record_type"], row["target_id"])
        target_journals.setdefault(target, set()).add(row["journal_id"])
    if any(len(journals) != 1 for journals in target_journals.values()):
        raise P0ActualAuthorityError(
            "annotation subject must have one authoritative journal"
        )
    return rows, lines


def _reconstruct_heads(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        target = (row["target_record_type"], row["target_id"])
        current = latest.get(target)
        if current is None or row["journal_sequence"] > current["journal_sequence"]:
            latest[target] = row
    return [
        {
            "target_record_type": row["target_record_type"],
            "target_id": row["target_id"],
            "target_subject_sha256": row["target_subject_sha256"],
            "journal_id": row["journal_id"],
            "head_sequence": row["journal_sequence"],
            "head_event_id": row["event_id"],
            "head_event_sha256": row["event_sha256"],
        }
        for _, row in sorted(latest.items())
    ]


def verify_annotation_event_bytes_from_bytes(
    *,
    event_bytes: bytes,
    predecessor_checkpoint: Mapping[str, Any],
    predecessor_head_map: Mapping[str, Any],
    current_checkpoint: Mapping[str, Any],
    current_head_map: Mapping[str, Any],
    expected_authority_origin: str,
    expected_event_origin: str,
) -> dict[str, Any]:
    """Verify immutable event bytes and projections without granting authority."""

    if not isinstance(event_bytes, bytes):
        raise P0ActualAuthorityError("annotation event input must be bytes")

    predecessor = validate_checkpoint(predecessor_checkpoint, expected_authority_origin)
    predecessor_heads = validate_head_map(
        predecessor_head_map, expected_authority_origin
    )
    current = validate_checkpoint(current_checkpoint, expected_authority_origin)
    current_heads = validate_head_map(current_head_map, expected_authority_origin)
    raw = event_bytes
    rows, lines = _canonical_event_rows(
        raw,
        expected_event_origin=expected_event_origin,
    )

    if current["previous_checkpoint_sha256"] != predecessor["artifact_sha256"]:
        raise P0ActualAuthorityError("current checkpoint predecessor binding mismatch")
    if not (0 < predecessor["prefix_rows"] < current["prefix_rows"] == len(rows)):
        raise P0ActualAuthorityError("checkpoint row boundaries are not a strict append")
    if current["prefix_bytes"] != len(raw):
        raise P0ActualAuthorityError("current checkpoint byte count mismatch")
    current_sha = hashlib.sha256(raw).hexdigest()
    if current["prefix_sha256"] != current_sha:
        raise P0ActualAuthorityError("current checkpoint byte hash mismatch")

    predecessor_rows = predecessor["prefix_rows"]
    predecessor_raw = b"".join(lines[:predecessor_rows])
    try:
        registry._validate_event_chains(rows[:predecessor_rows])
    except registry.P0ActualContractError as exc:
        raise P0ActualAuthorityError(
            f"predecessor prefix journal chain failure: {exc}"
        ) from exc
    if predecessor["prefix_bytes"] != len(predecessor_raw):
        raise P0ActualAuthorityError("predecessor checkpoint byte count mismatch")
    predecessor_sha = hashlib.sha256(predecessor_raw).hexdigest()
    if predecessor["prefix_sha256"] != predecessor_sha:
        raise P0ActualAuthorityError("predecessor checkpoint byte hash mismatch")
    if current["prefix_bytes"] <= predecessor["prefix_bytes"]:
        raise P0ActualAuthorityError("checkpoint byte boundaries are not a strict append")

    predecessor_reconstructed = _reconstruct_heads(rows[:predecessor_rows])
    current_reconstructed = _reconstruct_heads(rows)
    for label, checkpoint, head_map, prefix_rows, reconstructed in (
        (
            "predecessor",
            predecessor,
            predecessor_heads,
            rows[:predecessor_rows],
            predecessor_reconstructed,
        ),
        ("current", current, current_heads, rows, current_reconstructed),
    ):
        if max(_rfc3339(row["occurred_at"]) for row in prefix_rows) > _rfc3339(
            checkpoint["created_at"]
        ):
            raise P0ActualAuthorityError(
                f"{label} checkpoint cannot predate its event prefix"
            )
        if head_map["heads"] != reconstructed:
            raise P0ActualAuthorityError(f"{label} head map reconstruction mismatch")
        if checkpoint["prefix_head_set_sha256"] != canonical_sha256(reconstructed):
            raise P0ActualAuthorityError(f"{label} checkpoint head-set mismatch")
        if checkpoint["head_map_artifact_sha256"] != head_map["artifact_sha256"]:
            raise P0ActualAuthorityError(f"{label} checkpoint head artifact mismatch")

    material = {
        "schema_version": EVENT_BYTES_RECEIPT_SCHEMA,
        "event_file_sha256": current_sha,
        "event_row_count": len(rows),
        "predecessor_prefix_rows": predecessor["prefix_rows"],
        "predecessor_prefix_bytes": predecessor["prefix_bytes"],
        "canonical_jsonl_verified": True,
        "journal_chains_verified": True,
        "checkpoint_prefixes_verified": True,
        "head_maps_reconstructed": True,
        "filesystem_handle_trust_verified": False,
        "durable_predecessor_verified": False,
        "owner_authority_verified": False,
        "runtime_noninterference_verified": False,
        "gate_status": "NO_GO_ACTUAL_P0_NOT_STARTED",
        "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY",
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


def verify_annotation_event_bytes(
    *,
    event_path: str | Path,
    predecessor_checkpoint: Mapping[str, Any],
    predecessor_head_map: Mapping[str, Any],
    current_checkpoint: Mapping[str, Any],
    current_head_map: Mapping[str, Any],
    expected_authority_origin: str,
    expected_event_origin: str,
) -> dict[str, Any]:
    """Read a stable regular file, then verify its immutable event bytes."""

    _, raw = _stable_regular_file_bytes(event_path)
    return verify_annotation_event_bytes_from_bytes(
        event_bytes=raw,
        predecessor_checkpoint=predecessor_checkpoint,
        predecessor_head_map=predecessor_head_map,
        current_checkpoint=current_checkpoint,
        current_head_map=current_head_map,
        expected_authority_origin=expected_authority_origin,
        expected_event_origin=expected_event_origin,
    )


__all__ = [
    "EVENT_BYTES_RECEIPT_SCHEMA",
    "verify_annotation_event_bytes",
    "verify_annotation_event_bytes_from_bytes",
]
