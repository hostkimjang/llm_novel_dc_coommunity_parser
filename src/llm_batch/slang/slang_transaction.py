from __future__ import annotations

"""Crash-reconcilable, bounded DB transaction sidecar for approved slang deltas.

It is intentionally not wired to ``SlangDBManager.flush``.  Operators pass a
fully approved, hash-bound before/after payload; the sidecar only makes the
small DB replacement recoverable under a DB-specific OS lock.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping
import uuid

from ..ledger.framed_wal import _exclusive_file_lock


SCHEMA = "slang_db_transaction_v2"
AUTHORIZATION_SCHEMA = "slang_transaction_authorization_v1"
MAX_BOUNDED_DB_BYTES = 2_000_000


class SlangTransactionError(ValueError): pass


def _require_bounded_temp_scope(*, db_path: Path, journal_dir: Path, sidecar_root: Path) -> tuple[Path, Path, Path]:
    """Refuse an accidental live DB target; this M1 sidecar is temp-only."""
    try:
        temp_root = Path(tempfile.gettempdir()).resolve()
        root = Path(sidecar_root).resolve(strict=True)
        db = Path(db_path).resolve(strict=True)
        journal = Path(journal_dir).resolve()
        root.relative_to(temp_root)
        db.relative_to(root)
        journal.relative_to(root)
    except (OSError, ValueError) as exc:
        raise SlangTransactionError("sidecar target must be inside an explicit bounded temporary root") from exc
    if not db.is_file() or db.stat().st_size > MAX_BOUNDED_DB_BYTES:
        raise SlangTransactionError("sidecar DB is missing or exceeds bounded temporary size")
    return db, journal, root


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()


def _atomic_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with tmp.open("xb") as handle: handle.write(raw); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
        descriptor = None
        try: descriptor = os.open(str(path.parent), os.O_RDONLY); os.fsync(descriptor)
        except OSError: pass
        finally:
            if descriptor is not None: os.close(descriptor)
    finally: tmp.unlink(missing_ok=True)


def _journal_paths(db_path: Path, journal_dir: Path) -> tuple[Path, Path]:
    token = hashlib.sha256(str(db_path.resolve()).encode()).hexdigest()[:16]
    return journal_dir / f"{token}.journal.json", journal_dir / f"{token}.before.json"


def _journal_hash(value: Mapping[str, Any]) -> str:
    return _sha(_bytes({key: item for key, item in value.items() if key != "journal_sha256"}))


def _receipt_hash(value: Mapping[str, Any]) -> str:
    return _sha(_bytes({key: item for key, item in value.items() if key != "receipt_sha256"}))


def _authorization_hash(value: Mapping[str, Any]) -> str:
    return _sha(_bytes({key: item for key, item in value.items() if key != "authorization_sha256"}))


def build_authorization(*, db_path: Path, proposal_sha256: str, before_sha256: str, proposal_path: Path, proposal_file_sha256: str, approval_path: Path, approval_file_sha256: str, approval_sha256: str, source_work_artifact_path: Path | None = None, source_work_artifact_sha256: str | None = None, source_work_entry_sha256: str | None = None, source_run_manifest_path: Path | None = None, source_run_manifest_sha256: str | None = None, source_run_id: str | None = None) -> dict[str, Any]:
    """Make the immutable governance binding persisted in the sidecar journal."""
    value = {
        "schema_version": AUTHORIZATION_SCHEMA,
        "db_path": str(db_path.resolve()),
        "proposal_sha256": proposal_sha256,
        "before_sha256": before_sha256,
        "proposal_path": str(proposal_path.resolve()),
        "proposal_file_sha256": proposal_file_sha256,
        "approval_path": str(approval_path.resolve()),
        "approval_file_sha256": approval_file_sha256,
        "approval_sha256": approval_sha256,
        "source_work_artifact_path": str(source_work_artifact_path.resolve()) if source_work_artifact_path is not None else None,
        "source_work_artifact_sha256": source_work_artifact_sha256,
        "source_work_entry_sha256": source_work_entry_sha256,
        "source_run_manifest_path": str(source_run_manifest_path.resolve()) if source_run_manifest_path is not None else None,
        "source_run_manifest_sha256": source_run_manifest_sha256,
        "source_run_id": source_run_id,
    }
    value["authorization_sha256"] = _authorization_hash(value)
    return value


def _validate_authorization(value: Any, *, db_path: Path, proposal_sha256: str, before_sha256: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SlangTransactionError("governance authorization is required")
    authorization = dict(value)
    if authorization.get("schema_version") != AUTHORIZATION_SCHEMA:
        raise SlangTransactionError("authorization schema mismatch")
    if authorization.get("authorization_sha256") != _authorization_hash(authorization):
        raise SlangTransactionError("authorization self-hash mismatch")
    if authorization.get("proposal_sha256") != proposal_sha256 or authorization.get("before_sha256") != before_sha256:
        raise SlangTransactionError("authorization proposal/base binding mismatch")
    try:
        if Path(str(authorization.get("db_path") or "")).resolve() != db_path.resolve():
            raise SlangTransactionError("authorization DB path mismatch")
    except OSError as exc:
        raise SlangTransactionError("authorization DB path cannot be resolved") from exc
    for key in ("proposal_file_sha256", "approval_file_sha256", "approval_sha256"):
        item = authorization.get(key)
        if not isinstance(item, str) or len(item) != 64:
            raise SlangTransactionError(f"authorization {key} is required")
    source_values = (authorization.get("source_work_artifact_path"), authorization.get("source_work_artifact_sha256"), authorization.get("source_work_entry_sha256"), authorization.get("source_run_manifest_path"), authorization.get("source_run_manifest_sha256"), authorization.get("source_run_id"))
    if any(item is not None for item in source_values) and not all(item is not None and str(item) for item in source_values):
        raise SlangTransactionError("authorization source-work binding is incomplete")
    return authorization


def _terminal_receipt(*, action: str, db_sha256: str, backup_sha256: str, source_journal_sha256: str | None = None) -> dict[str, Any]:
    receipt = {
        "schema_version": SCHEMA,
        "action": action,
        "db_sha256": db_sha256,
        "backup_sha256": backup_sha256,
        "source_journal_sha256": source_journal_sha256,
    }
    receipt["receipt_sha256"] = _receipt_hash(receipt)
    return receipt


def _validate_terminal_receipt(receipt: Any, *, action: str, db_sha256: str, backup_sha256: str, source_journal_sha256: str | None = None) -> None:
    if not isinstance(receipt, Mapping):
        raise SlangTransactionError("terminal receipt is missing")
    if receipt.get("schema_version") != SCHEMA or receipt.get("action") != action:
        raise SlangTransactionError("terminal receipt schema/action mismatch")
    if receipt.get("db_sha256") != db_sha256 or receipt.get("backup_sha256") != backup_sha256:
        raise SlangTransactionError("terminal receipt bytes mismatch")
    if receipt.get("source_journal_sha256") != source_journal_sha256:
        raise SlangTransactionError("terminal receipt source journal mismatch")
    if receipt.get("receipt_sha256") != _receipt_hash(receipt):
        raise SlangTransactionError("terminal receipt self-hash mismatch")


def _read_journal(db_path: Path, journal_dir: Path) -> tuple[dict[str, Any] | None, Path, Path]:
    journal_path, backup_path = _journal_paths(db_path, journal_dir)
    if not journal_path.exists():
        return None, journal_path, backup_path
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    if journal.get("schema_version") != SCHEMA or journal.get("journal_sha256") != _journal_hash(journal):
        raise SlangTransactionError("journal self-hash mismatch")
    if Path(journal.get("db_path", "")).resolve() != db_path.resolve():
        raise SlangTransactionError("journal DB path mismatch")
    return journal, journal_path, backup_path


def _reconcile_locked(db_path: Path, journal_dir: Path) -> dict[str, Any]:
    journal, journal_path, backup_path = _read_journal(db_path, journal_dir)
    if journal is None:
        return {"status": "NO_PENDING_TRANSACTION"}
    _validate_authorization(journal.get("authorization"), db_path=db_path, proposal_sha256=str(journal.get("proposal_sha256") or ""), before_sha256=str(journal.get("before_sha256") or ""))
    status = journal.get("status")
    if status in {"COMMITTED", "COMMITTED_RECOVERED"}:
        if _sha(db_path.read_bytes()) != journal["after_sha256"] or not backup_path.exists() or _sha(backup_path.read_bytes()) != journal["before_sha256"]:
            raise SlangTransactionError("committed journal/DB/backup bytes mismatch")
        _validate_terminal_receipt(journal.get("terminal_receipt"), action="APPLY", db_sha256=journal["after_sha256"], backup_sha256=journal["before_sha256"])
        return dict(journal)
    if status in {"ROLLED_BACK", "ROLLED_BACK_RECOVERED"}:
        if _sha(db_path.read_bytes()) != journal["before_sha256"] or not backup_path.exists() or _sha(backup_path.read_bytes()) != journal["before_sha256"]:
            raise SlangTransactionError("rollback journal/DB/backup bytes mismatch")
        _validate_terminal_receipt(journal.get("terminal_receipt"), action="ROLLBACK", db_sha256=journal["before_sha256"], backup_sha256=journal["before_sha256"], source_journal_sha256=journal.get("rollback_of_journal_sha256"))
        return dict(journal)
    if status == "ABORTED_PRE_DB":
        return dict(journal)
    if status == "ABORTED_PRE_ROLLBACK":
        if _sha(db_path.read_bytes()) != journal["after_sha256"] or not backup_path.exists() or _sha(backup_path.read_bytes()) != journal["before_sha256"]:
            raise SlangTransactionError("aborted rollback journal/DB/backup bytes mismatch")
        _validate_terminal_receipt(journal.get("apply_terminal_receipt"), action="APPLY", db_sha256=journal["after_sha256"], backup_sha256=journal["before_sha256"])
        return dict(journal)
    if status not in {"INTENT", "ROLLBACK_INTENT"}:
        raise SlangTransactionError("unknown transaction status")
    current = _sha(db_path.read_bytes())
    if status == "INTENT":
        if current == journal["before_sha256"]:
            journal["status"] = "ABORTED_PRE_DB"; journal["reconciled"] = True
        elif current == journal["after_sha256"]:
            journal["status"] = "COMMITTED_RECOVERED"; journal["reconciled"] = True
            journal["terminal_receipt"] = _terminal_receipt(action="APPLY", db_sha256=current, backup_sha256=journal["before_sha256"])
        else:
            raise SlangTransactionError("journal/DB state is inconsistent; manual hold required")
    elif current == journal["after_sha256"]:
        journal["status"] = "ABORTED_PRE_ROLLBACK"; journal["reconciled"] = True
    elif current == journal["before_sha256"]:
        journal["status"] = "ROLLED_BACK_RECOVERED"; journal["reconciled"] = True
        journal["terminal_receipt"] = _terminal_receipt(action="ROLLBACK", db_sha256=current, backup_sha256=journal["before_sha256"], source_journal_sha256=journal.get("rollback_of_journal_sha256"))
    else:
        raise SlangTransactionError("rollback journal/DB state is inconsistent; manual hold required")
    journal.pop("journal_sha256", None); journal["journal_sha256"] = _journal_hash(journal); _atomic_bytes(journal_path, _bytes(journal) + b"\n")
    return journal


def reconcile(db_path: Path, journal_dir: Path, *, sidecar_root: Path) -> dict[str, Any]:
    """Reconcile one bounded DB sidecar under the same DB-specific OS lock as apply."""
    db, journal, _ = _require_bounded_temp_scope(db_path=db_path, journal_dir=journal_dir, sidecar_root=sidecar_root)
    with _exclusive_file_lock(db):
        return _reconcile_locked(db, journal)


def apply_approved_delta(*, db_path: Path, journal_dir: Path, sidecar_root: Path, proposal_sha256: str, before_sha256: str, after_payload: Mapping[str, Any], authorization: Mapping[str, Any], crash_after: str | None = None) -> dict[str, Any]:
    """Write intent → backup → DB → terminal receipt; crash injection is test-only."""
    db_path, journal_dir, _ = _require_bounded_temp_scope(db_path=db_path, journal_dir=journal_dir, sidecar_root=sidecar_root)
    if len(proposal_sha256) != 64 or len(before_sha256) != 64: raise SlangTransactionError("proposal and before hashes must be sha256")
    authorization = _validate_authorization(authorization, db_path=db_path, proposal_sha256=proposal_sha256, before_sha256=before_sha256)
    after_raw = _bytes(dict(after_payload)) + b"\n"
    with _exclusive_file_lock(db_path):
        prior = _reconcile_locked(db_path, journal_dir)
        if prior.get("status") in {"INTENT", "ROLLBACK_INTENT"}: raise SlangTransactionError("unreconciled intent")
        current = db_path.read_bytes()
        if _sha(current) != before_sha256: raise SlangTransactionError("approved base DB bytes changed")
        journal_path, backup_path = _journal_paths(db_path, journal_dir)
        intent = {"schema_version": SCHEMA, "action": "APPLY", "status": "INTENT", "db_path": str(db_path.resolve()), "proposal_sha256": proposal_sha256, "before_sha256": before_sha256, "after_sha256": _sha(after_raw), "authorization": authorization, "backup_path": str(backup_path.resolve()), "terminal_receipt": None}
        intent["journal_sha256"] = _journal_hash(intent); _atomic_bytes(journal_path, _bytes(intent) + b"\n")
        if crash_after == "intent": raise RuntimeError("injected crash after intent")
        _atomic_bytes(backup_path, current)
        _atomic_bytes(db_path, after_raw)
        if crash_after == "db": raise RuntimeError("injected crash after db replace")
        terminal = {**intent, "status": "COMMITTED", "terminal_receipt": _terminal_receipt(action="APPLY", db_sha256=_sha(db_path.read_bytes()), backup_sha256=_sha(backup_path.read_bytes()))}
        terminal.pop("journal_sha256", None); terminal["journal_sha256"] = _journal_hash(terminal); _atomic_bytes(journal_path, _bytes(terminal) + b"\n")
        if crash_after == "terminal": raise RuntimeError("injected crash after terminal receipt")
        return terminal


def rollback_committed(*, db_path: Path, journal_dir: Path, sidecar_root: Path, crash_after: str | None = None) -> dict[str, Any]:
    """Restore only the exact fsync'd backup bound to a committed sidecar journal."""
    db_path, journal_dir, _ = _require_bounded_temp_scope(db_path=db_path, journal_dir=journal_dir, sidecar_root=sidecar_root)
    with _exclusive_file_lock(db_path):
        prior = _reconcile_locked(db_path, journal_dir)
        if prior.get("status") not in {"COMMITTED", "COMMITTED_RECOVERED", "ABORTED_PRE_ROLLBACK"}:
            raise SlangTransactionError("rollback requires a committed apply transaction")
        journal_path, backup_path = _journal_paths(db_path, journal_dir)
        backup = backup_path.read_bytes()
        if _sha(backup) != prior["before_sha256"] or _sha(db_path.read_bytes()) != prior["after_sha256"]:
            raise SlangTransactionError("rollback base/backup bytes changed")
        intent = {
            "schema_version": SCHEMA, "action": "ROLLBACK", "status": "ROLLBACK_INTENT",
            "db_path": str(db_path.resolve()), "proposal_sha256": prior["proposal_sha256"],
            "before_sha256": prior["before_sha256"], "after_sha256": prior["after_sha256"],
            "backup_path": str(backup_path.resolve()), "rollback_of_journal_sha256": prior["journal_sha256"],
            "authorization": prior["authorization"],
            "apply_terminal_receipt": prior.get("terminal_receipt") or prior.get("apply_terminal_receipt"),
            "terminal_receipt": None,
        }
        intent["journal_sha256"] = _journal_hash(intent); _atomic_bytes(journal_path, _bytes(intent) + b"\n")
        if crash_after == "intent": raise RuntimeError("injected crash after rollback intent")
        _atomic_bytes(db_path, backup)
        if crash_after == "db": raise RuntimeError("injected crash after rollback db replace")
        terminal = {**intent, "status": "ROLLED_BACK", "terminal_receipt": _terminal_receipt(action="ROLLBACK", db_sha256=_sha(db_path.read_bytes()), backup_sha256=_sha(backup), source_journal_sha256=prior["journal_sha256"])}
        terminal.pop("journal_sha256", None); terminal["journal_sha256"] = _journal_hash(terminal); _atomic_bytes(journal_path, _bytes(terminal) + b"\n")
        if crash_after == "terminal": raise RuntimeError("injected crash after rollback terminal receipt")
        return terminal
