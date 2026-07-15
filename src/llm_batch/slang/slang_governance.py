from __future__ import annotations

"""Proposal/approval/apply/rollback workflow for slang-db mutations.

The live parser remains read-only by default.  This module is an operator tool:
no proposal is applied without an explicit approver and exact base-db hash.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping
import uuid

from .slang_transaction import SlangTransactionError, apply_approved_delta, build_authorization, reconcile as reconcile_transaction, rollback_committed


SCHEMA = "slang_db_governance_v1"
APPROVAL_SCHEMA = "slang_db_approval_v1"


class SlangGovernanceError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _proposal_fingerprint(value: Mapping[str, Any]) -> str:
    material = {key: value.get(key) for key in ("schema_version", "proposal_id", "requested_at", "requested_by", "base_db_path", "base_db_sha256", "operation", "evidence_refs", "source_work_artifact_path", "source_work_artifact_sha256", "source_work_entry_sha256", "source_run_manifest_path", "source_run_manifest_sha256", "source_run_id")}
    return hashlib.sha256(_bytes(material)).hexdigest()


def _approval_fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_bytes({key: value.get(key) for key in ("schema_version", "approved_at", "approver", "decision_note", "proposal_path", "proposal_file_sha256", "proposal_sha256", "requested_by")})).hexdigest()


def _read_object(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SlangGovernanceError(f"JSON object required: {path}") from exc
    if not isinstance(value, dict):
        raise SlangGovernanceError(f"JSON object required: {path}")
    return value


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    payload = _bytes(dict(value)) + b"\n"
    try:
        with tmp.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, path)
        try:
            descriptor = os.open(str(path.parent), os.O_RDONLY); os.fsync(descriptor); os.close(descriptor)
        except OSError:
            pass
    finally:
        tmp.unlink(missing_ok=True)


def _source_pending(work_path: Path, *, title: str, term: str) -> Dict[str, Any]:
    work = _read_object(work_path)
    bucket = ((work.get("titles") or {}).get(title) or {})
    matches = [item for item in (bucket.get("pending") or []) if isinstance(item, dict) and str(item.get("term") or "").strip() == term]
    if len(matches) != 1:
        raise SlangGovernanceError("source work artifact must contain exactly one pending alias")
    return deepcopy(matches[0])


def _validate_source_binding(proposal: Mapping[str, Any]) -> Dict[str, Any] | None:
    work_value = proposal.get("source_work_artifact_path")
    if work_value is None:
        return None
    fields = ("source_work_artifact_sha256", "source_work_entry_sha256", "source_run_manifest_path", "source_run_manifest_sha256", "source_run_id")
    if not all(isinstance(proposal.get(key), str) and proposal.get(key) for key in fields):
        raise SlangGovernanceError("source work/manifest binding is incomplete")
    work_path, manifest_path = Path(str(work_value)), Path(str(proposal["source_run_manifest_path"]))
    if not work_path.is_file() or _sha_path(work_path) != proposal["source_work_artifact_sha256"]:
        raise SlangGovernanceError("source work artifact changed or missing")
    if not manifest_path.is_file() or _sha_path(manifest_path) != proposal["source_run_manifest_sha256"]:
        raise SlangGovernanceError("source run manifest changed or missing")
    manifest = _read_object(manifest_path)
    if str(manifest.get("run_id") or "") != proposal["source_run_id"]:
        raise SlangGovernanceError("source run manifest run_id mismatch")
    try:
        if Path(str(manifest.get("publication_slang_db_work_path") or "")).resolve() != work_path.resolve():
            raise SlangGovernanceError("source run manifest work path mismatch")
    except OSError as exc:
        raise SlangGovernanceError("source run manifest work path cannot be resolved") from exc
    if manifest.get("publication_slang_db_work_artifact_complete") is not True or manifest.get("publication_slang_db_promotion_ready") is not True:
        raise SlangGovernanceError("source run manifest is not promotion-ready")
    if manifest.get("publication_slang_db_delayed_writeback") is not True or manifest.get("publication_slang_db_promotion_policy") != "explicit_post_run_only":
        raise SlangGovernanceError("source run manifest delayed-writeback policy mismatch")
    pending = _source_pending(work_path, title=str(proposal["operation"]["title"]), term=str(proposal["operation"]["term"]))
    if hashlib.sha256(_bytes(pending)).hexdigest() != proposal["source_work_entry_sha256"]:
        raise SlangGovernanceError("source work pending entry changed")
    return pending


def create_proposal(*, db_path: Path, proposal_path: Path, operation: Mapping[str, Any], evidence_refs: list[str], requested_by: str, source_work_artifact_path: Path | None = None, source_work_entry_sha256: str | None = None, source_run_manifest_path: Path | None = None, source_run_manifest_sha256: str | None = None, source_run_id: str | None = None) -> Dict[str, Any]:
    db = _read_object(db_path)
    if proposal_path.exists():
        raise FileExistsError(proposal_path)
    kind = str(operation.get("kind") or "").strip()
    if kind not in {"promote_pending", "remove_slang"}:
        raise SlangGovernanceError("operation.kind must be promote_pending or remove_slang")
    title, term = (str(operation.get(key) or "").strip() for key in ("title", "term"))
    if not title or not term:
        raise SlangGovernanceError("operation title and term are required")
    proposal = {
        "schema_version": SCHEMA,
        "proposal_id": uuid.uuid4().hex,
        "status": "PROPOSED",
        "requested_at": _now(),
        "requested_by": str(requested_by or "").strip() or "unknown",
        "base_db_path": str(db_path),
        "base_db_sha256": _sha_path(db_path),
        "operation": {"kind": kind, "title": title, "term": term},
        "evidence_refs": sorted({str(item).strip() for item in evidence_refs if str(item).strip()}),
        "approval": None,
        "application": None,
        "source_work_artifact_path": str(source_work_artifact_path) if source_work_artifact_path is not None else None,
        "source_work_artifact_sha256": _sha_path(source_work_artifact_path) if source_work_artifact_path is not None else None,
        "source_work_entry_sha256": source_work_entry_sha256,
        "source_run_manifest_path": str(source_run_manifest_path) if source_run_manifest_path is not None else None,
        "source_run_manifest_sha256": source_run_manifest_sha256,
        "source_run_id": source_run_id,
    }
    proposal["proposal_sha256"] = _proposal_fingerprint(proposal)
    _atomic_write(proposal_path, proposal)
    return proposal


def create_proposal_from_work_artifact(*, db_path: Path, work_artifact_path: Path, run_manifest_path: Path, proposal_path: Path, title: str, term: str, evidence_refs: list[str], requested_by: str) -> Dict[str, Any]:
    """Read-only conversion of expert_main's delayed ``*_slang_db_work.json``.

    This function does not instantiate ``SlangDBManager`` and never writes the
    DB/work artifact.  It merely proves that one pending alias exists in the
    completed work snapshot before an owner can review a proposal.
    """
    selected = _source_pending(work_artifact_path, title=str(title).strip(), term=str(term).strip())
    manifest = _read_object(run_manifest_path)
    if not str(manifest.get("run_id") or ""):
        raise SlangGovernanceError("source run manifest run_id is required")
    if manifest.get("publication_slang_db_work_artifact_complete") is not True or manifest.get("publication_slang_db_promotion_ready") is not True:
        raise SlangGovernanceError("source run manifest is not promotion-ready")
    if manifest.get("publication_slang_db_delayed_writeback") is not True or manifest.get("publication_slang_db_promotion_policy") != "explicit_post_run_only":
        raise SlangGovernanceError("source run manifest delayed-writeback policy mismatch")
    try:
        if Path(str(manifest.get("publication_slang_db_work_path") or "")).resolve() != work_artifact_path.resolve():
            raise SlangGovernanceError("source run manifest work path mismatch")
    except OSError as exc:
        raise SlangGovernanceError("source run manifest work path cannot be resolved") from exc
    if manifest.get("publication_slang_db_input_sha256") != _sha_path(db_path):
        raise SlangGovernanceError("source run manifest base DB bytes mismatch")
    return create_proposal(db_path=db_path, proposal_path=proposal_path, operation={"kind": "promote_pending", "title": title, "term": term}, evidence_refs=evidence_refs, requested_by=requested_by, source_work_artifact_path=work_artifact_path, source_work_entry_sha256=hashlib.sha256(_bytes(selected)).hexdigest(), source_run_manifest_path=run_manifest_path, source_run_manifest_sha256=_sha_path(run_manifest_path), source_run_id=str(manifest["run_id"]))


def approve_proposal(*, proposal_path: Path, approval_path: Path, approver: str, decision_note: str = "") -> Dict[str, Any]:
    proposal = _read_object(proposal_path)
    if proposal.get("schema_version") != SCHEMA or proposal.get("status") != "PROPOSED":
        raise SlangGovernanceError("only PROPOSED v1 proposal can be approved")
    if approval_path.exists():
        raise FileExistsError(approval_path)
    name = str(approver or "").strip()
    if not name:
        raise SlangGovernanceError("approver is required")
    if proposal.get("proposal_sha256") != _proposal_fingerprint(proposal):
        raise SlangGovernanceError("proposal self-hash mismatch")
    _validate_source_binding(proposal)
    if name == str(proposal.get("requested_by") or "").strip():
        raise SlangGovernanceError("requester and approver must differ")
    proposal["status"] = "APPROVED"
    approval = {"schema_version": APPROVAL_SCHEMA, "approved_at": _now(), "approver": name, "decision_note": str(decision_note or "").strip() or None, "proposal_path": str(proposal_path.resolve()), "proposal_file_sha256": _sha_path(proposal_path), "proposal_sha256": proposal["proposal_sha256"], "requested_by": proposal["requested_by"]}
    approval["approval_sha256"] = _approval_fingerprint(approval)
    _atomic_write(approval_path, approval)
    return approval


def _validated_approved_proposal(*, db_path: Path, proposal_path: Path, approval_path: Path) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any] | None]:
    proposal = _read_object(proposal_path)
    if proposal.get("schema_version") != SCHEMA or proposal.get("status") != "PROPOSED":
        raise SlangGovernanceError("explicit APPROVED proposal is required")
    approval = _read_object(approval_path)
    if proposal.get("proposal_sha256") != _proposal_fingerprint(proposal) or approval.get("schema_version") != APPROVAL_SCHEMA or approval.get("proposal_sha256") != proposal.get("proposal_sha256") or approval.get("approval_sha256") != _approval_fingerprint(approval):
        raise SlangGovernanceError("proposal/approval hash binding mismatch")
    try:
        proposal_path_bound = Path(str(approval.get("proposal_path") or "")).resolve() == proposal_path.resolve()
    except OSError:
        proposal_path_bound = False
    if not proposal_path_bound or approval.get("proposal_file_sha256") != _sha_path(proposal_path) or approval.get("requested_by") != proposal.get("requested_by"):
        raise SlangGovernanceError("approval proposal file binding mismatch")
    if str(approval.get("approver") or "") == str(proposal.get("requested_by") or ""):
        raise SlangGovernanceError("requester and approver must differ")
    try:
        if Path(str(proposal.get("base_db_path") or "")).resolve() != Path(db_path).resolve():
            raise SlangGovernanceError("proposal base_db_path does not match target db")
    except OSError as exc:
        raise SlangGovernanceError("proposal base_db_path cannot be resolved") from exc
    return proposal, approval, _validate_source_binding(proposal)


def _build_after_payload(*, db_path: Path, proposal: Mapping[str, Any], source_pending: Dict[str, Any] | None) -> Dict[str, Any]:
    db = _read_object(db_path)
    operation = proposal["operation"]
    title, term = operation["title"], operation["term"]
    bucket = (db.get("titles") or {}).get(title)
    if not isinstance(bucket, dict):
        if source_pending is None: raise SlangGovernanceError("proposal title bucket is absent")
        db.setdefault("titles", {})[title] = {"raw_titles": [title], "slang": [], "pending": [], "conflicts": [], "examples": [], "updated_at": None}
        bucket = db["titles"][title]
    if operation["kind"] == "promote_pending":
        pending = list(bucket.get("pending") or [])
        matches = [item for item in pending if isinstance(item, dict) and str(item.get("term") or "").strip() == term]
        if len(matches) > 1: raise SlangGovernanceError("at most one central pending alias is required")
        if not matches and source_pending is None: raise SlangGovernanceError("exactly one pending alias is required")
        selected = matches[0] if matches else source_pending
        bucket["pending"] = [item for item in pending if item is not selected]
        slang = list(bucket.get("slang") or [])
        if not any(str(item.get("term") or "").strip() == term for item in slang if isinstance(item, dict)):
            slang.append(selected)
        bucket["slang"] = slang
    else:
        slang = list(bucket.get("slang") or [])
        updated = [item for item in slang if not (isinstance(item, dict) and str(item.get("term") or "").strip() == term)]
        if len(updated) == len(slang):
            raise SlangGovernanceError("slang alias is absent")
        bucket["slang"] = updated
    db["updated_at"] = _now()
    return db


def _application_receipt(*, proposal: Mapping[str, Any], approval: Mapping[str, Any], db_path: Path, transaction: Mapping[str, Any]) -> Dict[str, Any]:
    authorization = transaction["authorization"]
    receipt = {
        "schema_version": SCHEMA,
        "status": "APPLIED",
        "proposal_id": proposal["proposal_id"],
        "proposal_sha256": proposal["proposal_sha256"],
        "approval_path": authorization["approval_path"],
        "approval_file_sha256": authorization["approval_file_sha256"],
        "approval_sha256": approval["approval_sha256"],
        "approver": approval["approver"],
        "db_path": str(db_path.resolve()),
        "before_sha256": transaction["before_sha256"],
        "after_sha256": transaction["after_sha256"],
        "backup_path": transaction["backup_path"],
        "authorization_sha256": authorization["authorization_sha256"],
        "transaction_journal_sha256": transaction["journal_sha256"],
        "transaction_terminal_receipt_sha256": transaction["terminal_receipt"]["receipt_sha256"],
        "source_work_artifact_sha256": proposal.get("source_work_artifact_sha256"),
        "source_work_entry_sha256": proposal.get("source_work_entry_sha256"),
        "source_run_manifest_sha256": proposal.get("source_run_manifest_sha256"),
        "applied_at": _now(),
    }
    receipt["receipt_sha256"] = hashlib.sha256(_bytes(receipt)).hexdigest()
    return receipt


def _validate_transaction_for_proposal(*, db_path: Path, proposal_path: Path, approval_path: Path, proposal: Mapping[str, Any], approval: Mapping[str, Any], transaction: Mapping[str, Any]) -> None:
    if transaction.get("status") not in {"COMMITTED", "COMMITTED_RECOVERED"}:
        raise SlangGovernanceError("committed transaction is required")
    authorization = transaction.get("authorization")
    if not isinstance(authorization, Mapping) or transaction.get("proposal_sha256") != proposal.get("proposal_sha256"):
        raise SlangGovernanceError("transaction/proposal binding mismatch")
    if authorization.get("proposal_file_sha256") != _sha_path(proposal_path) or authorization.get("approval_path") != str(approval_path.resolve()) or authorization.get("approval_file_sha256") != _sha_path(approval_path) or authorization.get("approval_sha256") != approval.get("approval_sha256"):
        raise SlangGovernanceError("transaction proposal/approval file binding mismatch")
    if _sha_path(db_path) != transaction.get("after_sha256"):
        raise SlangGovernanceError("transaction after DB bytes mismatch")


def recover_application_receipt(*, db_path: Path, proposal_path: Path, approval_path: Path, receipt_path: Path, journal_dir: Path, sidecar_root: Path) -> Dict[str, Any]:
    """Rebuild the external governance receipt only from a committed sidecar journal."""
    if receipt_path.exists():
        return _read_object(receipt_path)
    proposal, approval, _ = _validated_approved_proposal(db_path=db_path, proposal_path=proposal_path, approval_path=approval_path)
    try:
        transaction = reconcile_transaction(db_path, journal_dir, sidecar_root=sidecar_root)
    except SlangTransactionError as exc:
        raise SlangGovernanceError(str(exc)) from exc
    _validate_transaction_for_proposal(db_path=db_path, proposal_path=proposal_path, approval_path=approval_path, proposal=proposal, approval=approval, transaction=transaction)
    receipt = _application_receipt(proposal=proposal, approval=approval, db_path=db_path, transaction=transaction)
    _atomic_write(receipt_path, receipt)
    return receipt


def apply_approved_proposal(*, db_path: Path, proposal_path: Path, approval_path: Path, receipt_path: Path, journal_dir: Path, sidecar_root: Path, crash_after: str | None = None) -> Dict[str, Any]:
    """Apply only via the crash-reconcilable sidecar; no direct DB replacement."""
    if receipt_path.exists():
        raise FileExistsError(receipt_path)
    proposal, approval, source_pending = _validated_approved_proposal(db_path=db_path, proposal_path=proposal_path, approval_path=approval_path)
    if _sha_path(db_path) != proposal.get("base_db_sha256"):
        raise SlangGovernanceError("slang db changed since proposal; re-propose against current bytes")
    after_payload = _build_after_payload(db_path=db_path, proposal=proposal, source_pending=source_pending)
    authorization = build_authorization(db_path=db_path, proposal_sha256=proposal["proposal_sha256"], before_sha256=proposal["base_db_sha256"], proposal_path=proposal_path, proposal_file_sha256=_sha_path(proposal_path), approval_path=approval_path, approval_file_sha256=_sha_path(approval_path), approval_sha256=approval["approval_sha256"], source_work_artifact_path=Path(proposal["source_work_artifact_path"]) if proposal.get("source_work_artifact_path") else None, source_work_artifact_sha256=proposal.get("source_work_artifact_sha256"), source_work_entry_sha256=proposal.get("source_work_entry_sha256"), source_run_manifest_path=Path(proposal["source_run_manifest_path"]) if proposal.get("source_run_manifest_path") else None, source_run_manifest_sha256=proposal.get("source_run_manifest_sha256"), source_run_id=proposal.get("source_run_id"))
    try:
        transaction = apply_approved_delta(db_path=db_path, journal_dir=journal_dir, sidecar_root=sidecar_root, proposal_sha256=proposal["proposal_sha256"], before_sha256=proposal["base_db_sha256"], after_payload=after_payload, authorization=authorization, crash_after=crash_after if crash_after in {"intent", "db", "terminal"} else None)
    except SlangTransactionError as exc:
        raise SlangGovernanceError(str(exc)) from exc
    if crash_after == "transaction":
        raise RuntimeError("injected crash after committed transaction")
    receipt = _application_receipt(proposal=proposal, approval=approval, db_path=db_path, transaction=transaction)
    _atomic_write(receipt_path, receipt)
    return receipt


def rollback_application(*, db_path: Path, receipt_path: Path, journal_dir: Path, rollback_by: str, sidecar_root: Path, crash_after: str | None = None) -> Dict[str, Any]:
    receipt = _read_object(receipt_path)
    if receipt.get("schema_version") != SCHEMA or receipt.get("status") != "APPLIED":
        raise SlangGovernanceError("APPLIED receipt is required")
    recorded_hash = receipt.get("receipt_sha256")
    if not isinstance(recorded_hash, str) or recorded_hash != hashlib.sha256(_bytes({key: value for key, value in receipt.items() if key != "receipt_sha256"})).hexdigest():
        raise SlangGovernanceError("application receipt self-hash mismatch")
    if str(rollback_by or "").strip() != str(receipt.get("approver") or "").strip():
        raise SlangGovernanceError("rollback requester must be the recorded approver")
    try:
        transaction = reconcile_transaction(db_path, journal_dir, sidecar_root=sidecar_root)
    except SlangTransactionError as exc:
        raise SlangGovernanceError(str(exc)) from exc
    if transaction.get("status") in {"ROLLED_BACK", "ROLLED_BACK_RECOVERED"}:
        if _sha_path(db_path) != receipt.get("before_sha256"):
            raise SlangGovernanceError("reconciled rollback bytes mismatch")
    else:
        if _sha_path(db_path) != receipt.get("after_sha256"):
            raise SlangGovernanceError("current slang db differs from receipt; rollback would erase later changes")
        if transaction.get("proposal_sha256") != receipt.get("proposal_sha256") or transaction.get("authorization", {}).get("authorization_sha256") != receipt.get("authorization_sha256"):
            raise SlangGovernanceError("transaction/governance receipt binding mismatch")
        try:
            transaction = rollback_committed(db_path=db_path, journal_dir=journal_dir, sidecar_root=sidecar_root, crash_after=crash_after)
        except SlangTransactionError as exc:
            raise SlangGovernanceError(str(exc)) from exc
    receipt["status"] = "ROLLED_BACK"
    receipt["rollback"] = {"rolled_back_at": _now(), "rollback_by": str(rollback_by).strip(), "restored_sha256": _sha_path(db_path), "application_receipt_sha256": recorded_hash, "transaction_journal_sha256": transaction["journal_sha256"], "transaction_terminal_receipt_sha256": transaction["terminal_receipt"]["receipt_sha256"]}
    receipt.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = hashlib.sha256(_bytes(receipt)).hexdigest()
    _atomic_write(receipt_path, receipt)
    return receipt
