from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from llm_batch.slang.slang_transaction import SlangTransactionError, apply_approved_delta, build_authorization, reconcile, rollback_committed


class SlangTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.db = self.root / "db.json"; self.journals = self.root / "journal"; self.db.write_text(json.dumps({"version": 2, "titles": {}}, ensure_ascii=False) + "\n", encoding="utf-8")
    def tearDown(self): self.tmp.cleanup()
    def _authorization(self, before_sha256):
        return build_authorization(db_path=self.db, proposal_sha256="a" * 64, before_sha256=before_sha256, proposal_path=self.root / "proposal.json", proposal_file_sha256="b" * 64, approval_path=self.root / "approval.json", approval_file_sha256="c" * 64, approval_sha256="d" * 64)
    def _apply(self, crash=None):
        raw = self.db.read_bytes(); return apply_approved_delta(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, proposal_sha256="a" * 64, before_sha256=hashlib.sha256(raw).hexdigest(), after_payload={"version": 2, "titles": {"작품": {}}}, authorization=self._authorization(hashlib.sha256(raw).hexdigest()), crash_after=crash)
    def test_commits_with_terminal_receipt(self): self.assertEqual(self._apply()["status"], "COMMITTED")
    def test_crash_after_intent_reconciles_as_aborted_without_db_write(self):
        before = self.db.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "intent"): self._apply("intent")
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "ABORTED_PRE_DB"); self.assertEqual(self.db.read_bytes(), before)
    def test_crash_after_db_reconciles_as_committed(self):
        with self.assertRaisesRegex(RuntimeError, "db"): self._apply("db")
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "COMMITTED_RECOVERED")
    def test_rejects_changed_base_bytes(self):
        with self.assertRaises(SlangTransactionError): apply_approved_delta(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, proposal_sha256="a" * 64, before_sha256="b" * 64, after_payload={}, authorization=self._authorization("b" * 64))

    def test_rejects_missing_or_tampered_governance_authorization(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        with self.assertRaisesRegex(SlangTransactionError, "authorization schema mismatch"):
            apply_approved_delta(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, proposal_sha256="a" * 64, before_sha256=before, after_payload={}, authorization={})
        authorization = self._authorization(before); authorization["approval_sha256"] = "0" * 64
        with self.assertRaisesRegex(SlangTransactionError, "authorization self-hash"):
            apply_approved_delta(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, proposal_sha256="a" * 64, before_sha256=before, after_payload={}, authorization=authorization)
    def test_concurrent_apply_has_one_commit_and_one_stale_base_rejection(self):
        before = self.db.read_bytes(); results=[]
        def apply():
            try: results.append(apply_approved_delta(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, proposal_sha256="a"*64, before_sha256=hashlib.sha256(before).hexdigest(), after_payload={"version":2,"titles":{"작품":{}}}, authorization=self._authorization(hashlib.sha256(before).hexdigest()))["status"])
            except Exception as exc: results.append(type(exc).__name__)
        workers=[threading.Thread(target=apply) for _ in range(2)]
        [item.start() for item in workers]; [item.join() for item in workers]
        self.assertEqual(sorted(results), ["COMMITTED", "SlangTransactionError"])
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "COMMITTED")

    def test_rollback_restores_exact_backup_and_terminal_receipt(self):
        before = self.db.read_bytes(); self._apply()
        result = rollback_committed(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root)
        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertEqual(self.db.read_bytes(), before)
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "ROLLED_BACK")

    def test_rollback_crash_after_intent_or_db_reconciles(self):
        before = self.db.read_bytes(); self._apply()
        with self.assertRaisesRegex(RuntimeError, "rollback intent"):
            rollback_committed(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, crash_after="intent")
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "ABORTED_PRE_ROLLBACK")
        self.assertNotEqual(self.db.read_bytes(), before)
        rollback_committed(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root)
        self._apply()
        with self.assertRaisesRegex(RuntimeError, "rollback db"):
            rollback_committed(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, crash_after="db")
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "ROLLED_BACK_RECOVERED")
        self.assertEqual(self.db.read_bytes(), before)

    def test_terminal_receipt_crash_is_recoverable_and_tamper_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "terminal receipt"):
            self._apply("terminal")
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "COMMITTED")
        journal = next(self.journals.glob("*.journal.json")); value = json.loads(journal.read_text(encoding="utf-8"))
        value["terminal_receipt"]["receipt_sha256"] = "0" * 64
        value["journal_sha256"] = hashlib.sha256(json.dumps({key: item for key, item in value.items() if key != "journal_sha256"}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        journal.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(SlangTransactionError, "terminal receipt self-hash"):
            reconcile(self.db, self.journals, sidecar_root=self.root)

    def test_rollback_terminal_receipt_crash_is_recoverable(self):
        before = self.db.read_bytes(); self._apply()
        with self.assertRaisesRegex(RuntimeError, "rollback terminal receipt"):
            rollback_committed(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root, crash_after="terminal")
        self.assertEqual(reconcile(self.db, self.journals, sidecar_root=self.root)["status"], "ROLLED_BACK")
        self.assertEqual(self.db.read_bytes(), before)

    def test_concurrent_rollback_has_one_terminal_restore(self):
        before = self.db.read_bytes(); self._apply(); results=[]
        def rollback():
            try: results.append(rollback_committed(db_path=self.db, journal_dir=self.journals, sidecar_root=self.root)["status"])
            except Exception as exc: results.append(type(exc).__name__)
        workers=[threading.Thread(target=rollback) for _ in range(2)]
        [item.start() for item in workers]; [item.join() for item in workers]
        self.assertEqual(sorted(results), ["ROLLED_BACK", "SlangTransactionError"])
        self.assertEqual(self.db.read_bytes(), before)

    def test_rejects_non_temp_or_out_of_scope_target(self):
        with self.assertRaisesRegex(SlangTransactionError, "bounded temporary root"):
            reconcile(self.db, self.journals, sidecar_root=self.root / "not-parent")
