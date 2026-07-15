from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from llm_batch.slang.slang_governance import SlangGovernanceError, approve_proposal, apply_approved_proposal, create_proposal, create_proposal_from_work_artifact, recover_application_receipt, rollback_application


class SlangGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "slang_db.json"
        self.db.write_text(json.dumps({"version": 2, "updated_at": None, "titles": {"작품": {"slang": [], "pending": [{"term": "약어", "normalized_term": "약어"}], "conflicts": [], "examples": []}}, "family_aliases": {}}, ensure_ascii=False), encoding="utf-8")
        self.proposal = self.root / "proposal.json"; self.approval = self.root / "approval.json"; self.receipt = self.root / "receipt.json"; self.journals = self.root / "journals"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _manifest(self, work: Path, *, ready: bool = True) -> Path:
        manifest = self.root / "run_manifest.json"
        manifest.write_text(json.dumps({"run_id": "run-1", "publication_slang_db_work_path": str(work), "publication_slang_db_input_sha256": hashlib.sha256(self.db.read_bytes()).hexdigest(), "publication_slang_db_work_artifact_complete": ready, "publication_slang_db_promotion_ready": ready, "publication_slang_db_delayed_writeback": True, "publication_slang_db_promotion_policy": "explicit_post_run_only"}, ensure_ascii=False), encoding="utf-8")
        return manifest

    def test_explicit_approval_apply_and_hash_bound_rollback(self) -> None:
        create_proposal(db_path=self.db, proposal_path=self.proposal, operation={"kind": "promote_pending", "title": "작품", "term": "약어"}, evidence_refs=["post:1"], requested_by="reviewer")
        with self.assertRaises(SlangGovernanceError):
            apply_approved_proposal(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root)
        approve_proposal(proposal_path=self.proposal, approval_path=self.approval, approver="owner")
        receipt = apply_approved_proposal(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root)
        self.assertEqual(receipt["status"], "APPLIED")
        payload = json.loads(self.db.read_text(encoding="utf-8"))
        self.assertEqual(payload["titles"]["작품"]["slang"][0]["term"], "약어")
        rolled = rollback_application(db_path=self.db, receipt_path=self.receipt, journal_dir=self.journals, rollback_by="owner", sidecar_root=self.root)
        self.assertEqual(rolled["status"], "ROLLED_BACK")
        restored = json.loads(self.db.read_text(encoding="utf-8"))
        self.assertEqual(restored["titles"]["작품"]["pending"][0]["term"], "약어")

    def test_changed_db_rejects_stale_approved_proposal(self) -> None:
        create_proposal(db_path=self.db, proposal_path=self.proposal, operation={"kind": "promote_pending", "title": "작품", "term": "약어"}, evidence_refs=[], requested_by="reviewer")
        approve_proposal(proposal_path=self.proposal, approval_path=self.approval, approver="owner")
        self.db.write_text(self.db.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(SlangGovernanceError, "changed since proposal"):
            apply_approved_proposal(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root)

    def test_work_artifact_conversion_is_read_only_and_requester_cannot_approve(self) -> None:
        work = self.root / "result_slang_db_work.json"; work.write_bytes(self.db.read_bytes())
        original = self.db.read_bytes(); work_original = work.read_bytes()
        create_proposal_from_work_artifact(db_path=self.db, work_artifact_path=work, run_manifest_path=self._manifest(work), proposal_path=self.proposal, title="작품", term="약어", evidence_refs=["work"], requested_by="requester")
        self.assertEqual(self.db.read_bytes(), original); self.assertEqual(work.read_bytes(), work_original)
        with self.assertRaisesRegex(SlangGovernanceError, "must differ"):
            approve_proposal(proposal_path=self.proposal, approval_path=self.approval, approver="requester")

    def test_work_only_pending_promotes_as_approved_delta_and_target_path_is_bound(self) -> None:
        work = self.root / "result_slang_db_work.json"; work.write_bytes(self.db.read_bytes())
        central = json.loads(self.db.read_text(encoding="utf-8")); central["titles"] = {}; self.db.write_text(json.dumps(central, ensure_ascii=False), encoding="utf-8")
        create_proposal_from_work_artifact(db_path=self.db, work_artifact_path=work, run_manifest_path=self._manifest(work), proposal_path=self.proposal, title="작품", term="약어", evidence_refs=[], requested_by="requester")
        approve_proposal(proposal_path=self.proposal, approval_path=self.approval, approver="owner")
        self.assertEqual(apply_approved_proposal(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root)["status"], "APPLIED")
        other = self.root / "other.json"; other.write_bytes(self.db.read_bytes())
        with self.assertRaisesRegex(SlangGovernanceError, "base_db_path"):
            apply_approved_proposal(db_path=other, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.root / "other-receipt.json", journal_dir=self.journals, sidecar_root=self.root)

    def test_work_manifest_and_pending_entry_are_revalidated_at_apply(self) -> None:
        work = self.root / "result_slang_db_work.json"; work.write_bytes(self.db.read_bytes()); manifest = self._manifest(work)
        create_proposal_from_work_artifact(db_path=self.db, work_artifact_path=work, run_manifest_path=manifest, proposal_path=self.proposal, title="작품", term="약어", evidence_refs=[], requested_by="requester")
        approve_proposal(proposal_path=self.proposal, approval_path=self.approval, approver="owner")
        work.write_text(work.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(SlangGovernanceError, "source work artifact changed"):
            apply_approved_proposal(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root)

    def test_incomplete_expert_manifest_cannot_create_work_proposal(self) -> None:
        work = self.root / "result_slang_db_work.json"; work.write_bytes(self.db.read_bytes())
        with self.assertRaisesRegex(SlangGovernanceError, "not promotion-ready"):
            create_proposal_from_work_artifact(db_path=self.db, work_artifact_path=work, run_manifest_path=self._manifest(work, ready=False), proposal_path=self.proposal, title="작품", term="약어", evidence_refs=[], requested_by="requester")

    def test_transaction_receipt_gap_and_rollback_terminal_gap_recover(self) -> None:
        create_proposal(db_path=self.db, proposal_path=self.proposal, operation={"kind": "promote_pending", "title": "작품", "term": "약어"}, evidence_refs=[], requested_by="requester")
        approve_proposal(proposal_path=self.proposal, approval_path=self.approval, approver="owner")
        with self.assertRaisesRegex(RuntimeError, "committed transaction"):
            apply_approved_proposal(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root, crash_after="transaction")
        receipt = recover_application_receipt(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root)
        self.assertEqual(receipt["status"], "APPLIED")
        with self.assertRaisesRegex(RuntimeError, "rollback terminal receipt"):
            rollback_application(db_path=self.db, receipt_path=self.receipt, journal_dir=self.journals, rollback_by="owner", sidecar_root=self.root, crash_after="terminal")
        self.assertEqual(rollback_application(db_path=self.db, receipt_path=self.receipt, journal_dir=self.journals, rollback_by="owner", sidecar_root=self.root)["status"], "ROLLED_BACK")

    def test_rollback_requires_recorded_approver(self) -> None:
        create_proposal(db_path=self.db, proposal_path=self.proposal, operation={"kind": "promote_pending", "title": "작품", "term": "약어"}, evidence_refs=[], requested_by="requester")
        approve_proposal(proposal_path=self.proposal, approval_path=self.approval, approver="owner")
        apply_approved_proposal(db_path=self.db, proposal_path=self.proposal, approval_path=self.approval, receipt_path=self.receipt, journal_dir=self.journals, sidecar_root=self.root)
        with self.assertRaisesRegex(SlangGovernanceError, "recorded approver"):
            rollback_application(db_path=self.db, receipt_path=self.receipt, journal_dir=self.journals, rollback_by="requester", sidecar_root=self.root)
