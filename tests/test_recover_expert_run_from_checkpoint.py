import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.llm_batch.ledger.publication_commit import (
    PUBLICATION_COMMIT_JOURNAL_SCHEMA,
    PUBLICATION_COMMIT_SCHEMA,
    PublicationCommitRegistry,
    PublicationScopeDescriptor,
    build_publication_scope_descriptor,
    commit_publication_result,
    compute_publication_decision_commit,
)
from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)
from tools.recover_expert_run_from_checkpoint import recover


class RecoverExpertRunFromCheckpointTest(unittest.TestCase):
    @staticmethod
    def _valid_result(post_id: int) -> dict:
        candidate_title = f"작품 {post_id}"
        candidate_url = f"https://novelpia.com/novel/{post_id}"
        state = GroundingState(
            post_id=post_id,
            candidate_title=candidate_title,
            candidate_url=candidate_url,
            source="recovery-test",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="resolved",
            discussion_type="specific_work",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=("body", "official_detail"),
                conflict_reason_codes=(),
            ),
        )
        evidence = [
            EvidenceRecord(
                kind="official_detail",
                strength="strong",
                source_path_or_snippet=candidate_url,
                supports_publish=True,
                reason_code="official_support",
                candidate_title=candidate_title,
                candidate_url=candidate_url,
                title_url_match=True,
            )
        ]
        identity = {
            "is_relevant": True,
            "novel_identity": {
                "official_title": candidate_title,
                "heretic_url": candidate_url,
                "confidence": "High",
            },
        }
        apply_publish_contract(identity, evaluate_publish_contract(state, evidence))
        return {
            "post_id": post_id,
            "title": "회복 테스트",
            "analysis_result": {"identity": identity},
            "run_meta": {},
        }

    @staticmethod
    def _error_result(post_id: int) -> dict:
        return {
            "post_id": post_id,
            "error": "test terminal error",
            "analysis_result": {
                "identity": {
                    "novel_identity": {"official_title": None, "heretic_url": None}
                }
            },
        }

    def _write_p2_artifacts(
        self,
        root: Path,
        *,
        post_ids: list[int],
        journal_scope_descriptor=None,
        write_journal: bool = True,
        attempt_run_ids: list[str] | None = None,
        error_post_ids: set[int] | None = None,
        release_attestation_status: str = "OPERATOR_ATTESTED",
    ) -> tuple[Path, Path, Path, Path, list[dict]]:
        result_path = root / "result.json"
        checkpoint_path = root / "checkpoint.jsonl"
        pending_path = root / "pending.json"
        manifest_path = root / "manifest.json"
        journal_path = root / "publication_commits.jsonl"
        attempt_claim_path = root / "result_attempt_claim.json"
        release_fingerprint = "b" * 64
        release_fingerprint_source = (
            "trusted_runtime_environment"
            if release_attestation_status == "OPERATOR_ATTESTED"
            else "development_disk_snapshot"
        )
        decision_environment = {
            "LLM_MODEL": "recovery-test-model",
            "PIPELINE_SLANG_DB": "1",
        }
        decision_environment_sha256 = hashlib.sha256(
            json.dumps(
                decision_environment,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        slang_db_input_sha256 = "c" * 64
        decision_config = {
            "decision_environment_keys": sorted(decision_environment),
            "decision_environment_sha256": decision_environment_sha256,
            "release_attestation_status": release_attestation_status,
            "release_fingerprint": release_fingerprint,
            "release_fingerprint_source": release_fingerprint_source,
            "slang_db_input_sha256": slang_db_input_sha256,
        }
        decision_config_sha256 = hashlib.sha256(
            json.dumps(
                decision_config,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        scope_descriptor = build_publication_scope_descriptor(
            input_file_sha256="a" * 64,
            post_ids=post_ids,
            config_hash=decision_config_sha256,
            release_fingerprint=release_fingerprint,
        )
        scope_id = scope_descriptor.publication_scope_id
        registry = PublicationCommitRegistry(
            journal_path,
            scope_descriptor=journal_scope_descriptor or scope_descriptor,
            create_new=True,
        )
        rows: list[dict] = []
        for idx, post_id in enumerate(post_ids, 1):
            result = (
                self._error_result(post_id)
                if post_id in (error_post_ids or set())
                else self._valid_result(post_id)
            )
            receipt, _ = commit_publication_result(
                result,
                registry=registry,
                attempt_run_id=(
                    attempt_run_ids[idx - 1] if attempt_run_ids else "test-run"
                ),
                input_index=idx,
                post_id=post_id,
            )
            rows.append(
                {
                    "global_idx": idx,
                    "post_id": post_id,
                    "status": "completed",
                    "publication_commit": receipt.to_dict(),
                    "result": result,
                }
            )
        if not write_journal:
            journal_path.write_text("", encoding="utf-8")
        result_path.write_text(json.dumps([row["result"] for row in rows]), encoding="utf-8")
        checkpoint_path.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
        pending_path.write_text("[]", encoding="utf-8")
        claim_bytes = (
            json.dumps(
                {
                    "schema_version": "expert_output_attempt_claim_v1",
                    "run_id": "p2-test",
                    "pid": 1234,
                    "output_file": str(result_path.resolve()),
                    "input_file": str((root / "input.json").resolve()),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        attempt_claim_path.write_bytes(claim_bytes)
        scope_config_path = journal_path.with_name(journal_path.name + ".config.json")
        scope_config_payload = {
            "schema_version": "publication_scope_config_v1",
            "publication_scope_id": scope_id,
            "input_snapshot_sha256": scope_descriptor.input_file_sha256,
            "ordered_post_ids": post_ids,
            "decision_config": decision_config,
            "decision_config_sha256": decision_config_sha256,
            "decision_environment": decision_environment,
            "decision_environment_sha256": decision_environment_sha256,
            "release_fingerprint": release_fingerprint,
            "release_fingerprint_source": release_fingerprint_source,
            "release_attestation_status": release_attestation_status,
            "slang_db_input_sha256": slang_db_input_sha256,
        }
        scope_config_bytes = (
            json.dumps(
                scope_config_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        scope_config_path.write_bytes(scope_config_bytes)
        tail_repair_dir = journal_path.with_name(journal_path.name + ".tail_repairs")
        empty_repair_ledger_sha256 = hashlib.sha256(b"[]").hexdigest()
        manifest_path.write_text(
            json.dumps(
                {
                    "run_id": "p2-test",
                    "output_file": str(result_path.resolve()),
                    "input_post_count": len(post_ids),
                    "completed_count": len(post_ids),
                    "flushed_count": len(post_ids),
                    "pending_count": 0,
                    "failed_count": 0,
                    "next_save_idx": len(post_ids) + 1,
                    "publication_commit_count": len(post_ids),
                    "large_run_complete": True,
                    "terminal_artifacts_finalized": True,
                    "publication_commit_schema": PUBLICATION_COMMIT_SCHEMA,
                    "publication_commit_journal_schema": PUBLICATION_COMMIT_JOURNAL_SCHEMA,
                    "publication_scope_id": scope_id,
                    "publication_commit_journal": str(journal_path),
                    "publication_commit_tail_repair_dir": str(tail_repair_dir),
                    "publication_commit_tail_repair_count": 0,
                    "publication_commit_tail_repair_ledger_sha256": empty_repair_ledger_sha256,
                    "publication_scope_descriptor": str(registry.scope_descriptor_path),
                    "publication_scope_descriptor_sha256": scope_descriptor.descriptor_sha256,
                    "publication_input_snapshot_sha256": scope_descriptor.input_file_sha256,
                    "publication_config_sha256": decision_config_sha256,
                    "publication_scope_config": str(scope_config_path),
                    "publication_scope_config_sha256": hashlib.sha256(
                        scope_config_bytes
                    ).hexdigest(),
                    "publication_decision_environment_sha256": decision_environment_sha256,
                    "publication_slang_db_input_sha256": slang_db_input_sha256,
                    "publication_release_fingerprint": release_fingerprint,
                    "publication_release_fingerprint_source": release_fingerprint_source,
                    "publication_release_attestation_status": release_attestation_status,
                    "output_attempt_claim": str(attempt_claim_path),
                    "output_attempt_claim_sha256": hashlib.sha256(claim_bytes).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        return result_path, checkpoint_path, pending_path, manifest_path, rows

    def _write_p2_pending_gap_artifacts(
        self,
        root: Path,
        *,
        non_prefix_final: bool = False,
    ) -> tuple[Path, Path, Path, Path, list[dict]]:
        result_path, checkpoint_path, pending_path, manifest_path, rows = self._write_p2_artifacts(
            root,
            post_ids=[101, 102, 103],
        )
        kept_rows = [rows[0], rows[2]]
        checkpoint_path.write_text(
            "\n".join(json.dumps(row) for row in kept_rows) + "\n",
            encoding="utf-8",
        )
        pending_row = {
            key: value for key, value in rows[2].items() if key != "status"
        }
        pending_path.write_text(json.dumps([pending_row]), encoding="utf-8")
        result_path.write_text(
            json.dumps([rows[2]["result"] if non_prefix_final else rows[0]["result"]]),
            encoding="utf-8",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        journal_path = Path(manifest["publication_commit_journal"])
        journal_payloads = [
            json.loads(line)
            for line in journal_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        journal_path.write_text(
            "\n".join(
                json.dumps(payload, ensure_ascii=False, sort_keys=True)
                for payload in journal_payloads
                if payload["receipt"]["input_index"] in {1, 3}
            )
            + "\n",
            encoding="utf-8",
        )
        manifest.update(
            {
                "completed_count": 2,
                "flushed_count": 1,
                "pending_count": 1,
                "failed_count": 0,
                "next_save_idx": 2,
                "large_run_complete": False,
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return result_path, checkpoint_path, pending_path, manifest_path, rows

    def test_recovers_completed_rows_and_classifies_pending_flush_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            checkpoint_path = root / "checkpoint.jsonl"
            pending_path = root / "pending.json"
            manifest_path = root / "manifest.json"
            recovered_path = root / "recovered.json"
            summary_path = root / "summary.json"

            result_path.write_text(
                json.dumps([{"post_id": 1, "title": "first"}], ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint_rows = [
                {"global_idx": 1, "post_id": 1, "status": "completed", "result": {"post_id": 1, "title": "first"}},
                {"global_idx": 2, "post_id": 2, "status": "completed", "result": {"post_id": 2, "title": "second"}},
            ]
            checkpoint_path.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in checkpoint_rows) + "\n",
                encoding="utf-8",
            )
            pending_path.write_text(
                json.dumps([{"global_idx": 2, "post_id": 2, "result": {"post_id": 2, "title": "second"}}], ensure_ascii=False),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "test",
                        "input_post_count": 10,
                        "completed_count": 2,
                        "flushed_count": 1,
                        "pending_count": 1,
                        "failed_count": 0,
                        "next_save_idx": 2,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=summary_path,
            )

            recovered = json.loads(recovered_path.read_text(encoding="utf-8"))
            self.assertEqual([row["post_id"] for row in recovered], [1, 2])
            self.assertEqual(summary["missing_from_final_post_ids"], [2])
            self.assertEqual(summary["pending_not_in_final_post_ids"], [2])
            self.assertEqual(summary["integrity_classification"], "recoverable_pending_flush_gap")
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertFalse(summary["large_run_complete"])

    def test_classifies_complete_final_and_checkpoint_match_as_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path = root / "result.json"
            checkpoint_path = root / "checkpoint.jsonl"
            pending_path = root / "pending.json"
            manifest_path = root / "manifest.json"
            recovered_path = root / "recovered.json"
            summary_path = root / "summary.json"

            row = {"post_id": 1, "title": "first"}
            result_path.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
            checkpoint_path.write_text(
                json.dumps({"global_idx": 1, "post_id": 1, "status": "completed", "result": row}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            pending_path.write_text("[]", encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    {
                        "run_id": "test",
                        "input_post_count": 1,
                        "completed_count": 1,
                        "flushed_count": 1,
                        "pending_count": 0,
                        "failed_count": 0,
                        "next_save_idx": 2,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=summary_path,
            )

            self.assertEqual(summary["integrity_classification"], "clean_completed_run")
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertTrue(summary["large_run_complete"])

    def test_p2_complete_run_requires_matching_wrappers_and_durable_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101, 102],
            )
            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertTrue(summary["exact_once"]["scope_match"])
            self.assertEqual(summary["manifest"]["failed_count"], 0)
            self.assertEqual(summary["wal_error_hold_count"], 0)
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertTrue(summary["large_run_complete"])
            self.assertTrue(summary["recovered_output_written"])
            self.assertTrue((root / "recovered.json").exists())

    def test_p2_missing_durable_journal_receipt_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
                write_journal=False,
            )
            recovered_path = root / "recovered.json"
            recovered_path.write_text("[]", encoding="utf-8")
            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "NO-GO")
            self.assertEqual(summary["exact_once_status"], "INCOMPLETE")
            self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
            self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertTrue(summary["exact_once"]["journal_correspondence_errors"])
            self.assertFalse(summary["recovered_output_written"])
            self.assertIsNone(summary["recovered_output_path"])
            self.assertFalse(recovered_path.exists())

    def test_p2_scope_mismatch_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong_scope_descriptor = build_publication_scope_descriptor(
                input_file_sha256="b" * 64,
                post_ids=[101],
                config_hash="different-config",
            )
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
                journal_scope_descriptor=wrong_scope_descriptor,
            )
            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "NO-GO")
            self.assertEqual(summary["exact_once_status"], "UNSAFE")
            self.assertFalse(summary["exact_once"]["scope_match"])
            self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])

    def test_p2_wrapper_receipt_prevents_manifest_downgrade_to_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for key in (
                "publication_commit_schema",
                "publication_scope_id",
                "publication_commit_journal",
                "publication_scope_descriptor",
                "publication_scope_descriptor_sha256",
            ):
                manifest.pop(key, None)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertTrue(summary["exact_once"]["enabled"])
            self.assertEqual(summary["exact_once_gate"], "NO-GO")
            self.assertEqual(summary["exact_once_status"], "UNSAFE")
            self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertFalse(summary["large_run_complete"])
            self.assertFalse(summary["recovered_output_written"])
            self.assertFalse(recovered_path.exists())

    def test_new_p2_manifest_missing_scope_descriptor_is_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            Path(manifest["publication_scope_descriptor"]).unlink()
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "NO-GO")
            self.assertEqual(summary["exact_once_status"], "UNSAFE")
            self.assertEqual(summary["exact_once"]["scope_descriptor"]["status"], "NO-GO")
            self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertFalse(recovered_path.exists())

    def test_new_p2_manifest_tampered_scope_descriptor_is_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            descriptor_path = Path(manifest["publication_scope_descriptor"])
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor["post_ids"] = [999]
            descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "NO-GO")
            self.assertEqual(summary["exact_once_status"], "UNSAFE")
            self.assertEqual(summary["exact_once"]["scope_descriptor"]["status"], "NO-GO")
            self.assertTrue(summary["exact_once"]["scope_descriptor"]["errors"])

    def test_new_p2_manifest_cannot_strip_descriptor_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("publication_scope_descriptor")
            manifest.pop("publication_scope_descriptor_sha256")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            descriptor_gate = summary["exact_once"]["scope_descriptor"]
            self.assertTrue(descriptor_gate["required"])
            self.assertFalse(descriptor_gate["declared"])
            self.assertEqual(descriptor_gate["status"], "NO-GO")
            self.assertEqual(summary["exact_once_gate"], "NO-GO")
            self.assertFalse(summary["recovered_output_written"])

    def test_legacy_p2_without_descriptor_is_accepted_but_not_provable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            journal_path = Path(manifest["publication_commit_journal"])
            events = [
                json.loads(line)
                for line in journal_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            journal_path.write_text(
                "\n".join(json.dumps(event["receipt"]) for event in events) + "\n",
                encoding="utf-8",
            )
            manifest["publication_commit_journal_schema"] = (
                "publication_decision_commit_journal_v1"
            )
            Path(manifest["publication_scope_descriptor"]).unlink()
            manifest.pop("publication_scope_descriptor")
            manifest.pop("publication_scope_descriptor_sha256")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "NOT_PROVABLE")
            self.assertEqual(summary["exact_once_status"], "NOT_PROVABLE")
            self.assertEqual(
                summary["exact_once"]["scope_descriptor"]["status"],
                "NOT_PROVABLE",
            )
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])

    def test_p2_duplicate_final_post_id_is_no_go_and_has_no_plain_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, rows = self._write_p2_artifacts(
                root,
                post_ids=[101, 102],
            )
            result_path.write_text(
                json.dumps([rows[0]["result"], rows[0]["result"]]),
                encoding="utf-8",
            )
            recovered_path = root / "recovered.json"
            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
            self.assertEqual(summary["exact_once"]["duplicate_final_post_ids"], [101])
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertTrue(recovered_path.exists())
            self.assertFalse(summary["large_run_complete"])

    def test_p2_final_order_must_match_checkpoint_global_idx_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, rows = self._write_p2_artifacts(
                root,
                post_ids=[101, 102],
            )
            result_path.write_text(
                json.dumps([rows[1]["result"], rows[0]["result"]]),
                encoding="utf-8",
            )
            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
            self.assertTrue(summary["exact_once"]["final_cardinality_match"])
            self.assertFalse(summary["exact_once"]["final_order_match"])

    def test_p2_final_cardinality_must_match_checkpoint_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, rows = self._write_p2_artifacts(
                root,
                post_ids=[101, 102],
            )
            result_path.write_text(json.dumps([rows[0]["result"]]), encoding="utf-8")
            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
            self.assertFalse(summary["exact_once"]["final_cardinality_match"])
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertFalse(summary["large_run_complete"])

    def test_p2_pending_flush_prefix_is_safe_subset_but_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_pending_gap_artifacts(
                root
            )
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once"]["completed_subset_gate"], "GO")
            self.assertEqual(summary["exact_once_gate"], "NO-GO")
            self.assertEqual(summary["exact_once_status"], "INCOMPLETE")
            self.assertEqual(summary["exact_once"]["final_policy"], "canonical_checkpoint_prefix")
            self.assertTrue(summary["exact_once"]["final_order_match"])
            self.assertTrue(summary["exact_once"]["pending_wrapper_match"])
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertTrue(summary["recovered_output_written"])
            self.assertEqual(
                [row["post_id"] for row in json.loads(recovered_path.read_text(encoding="utf-8"))],
                [101, 103],
            )
            self.assertFalse(summary["large_run_complete"])
            self.assertFalse(summary["full_scan_approval"])

    def test_p2_v2_recovers_wal_commit_after_crash_before_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            result_path.write_text("[]", encoding="utf-8")
            checkpoint_path.write_text("", encoding="utf-8")
            pending_path.write_text("[]", encoding="utf-8")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.update(
                {
                    "completed_count": 0,
                    "flushed_count": 0,
                    "pending_count": 0,
                    "next_save_idx": 1,
                    "large_run_complete": False,
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once"]["journal_mode"], "current")
            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertEqual(summary["wal_error_hold_count"], 0)
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertFalse(summary["large_run_complete"])
            self.assertTrue(summary["publication_rows_complete"])
            self.assertEqual(
                summary["terminal_manifest_integrity"]["status"],
                "UNSAFE",
            )
            self.assertEqual(
                [row["post_id"] for row in json.loads(recovered_path.read_text(encoding="utf-8"))],
                [101],
            )

    def test_p2_v2_error_hold_wal_cannot_be_reported_as_large_run_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
                error_post_ids={101},
            )
            # Reproduce a stale/forged success manifest: the WAL remains the
            # canonical source for the terminal ERROR_HOLD outcome.
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["failed_count"] = 0
            manifest["large_run_complete"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertEqual(summary["wal_error_hold_count"], 1)
            self.assertEqual(summary["exact_once"]["wal_error_hold_count"], 1)
            self.assertFalse(summary["large_run_complete"])

    def test_p2_v2_unions_wal_commits_from_multiple_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101, 102],
                attempt_run_ids=["attempt-a", "attempt-b"],
            )
            result_path.write_text("[]", encoding="utf-8")
            checkpoint_path.write_text("", encoding="utf-8")
            pending_path.write_text("[]", encoding="utf-8")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.update(
                {
                    "completed_count": 0,
                    "flushed_count": 0,
                    "pending_count": 0,
                    "next_save_idx": 1,
                    "large_run_complete": False,
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            recovered = json.loads(recovered_path.read_text(encoding="utf-8"))
            self.assertEqual([row["post_id"] for row in recovered], [101, 102])
            self.assertEqual(summary["exact_once"]["journal_event_count"], 2)
            self.assertEqual(summary["exact_once"]["wal_error_hold_count"], 0)
            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertFalse(summary["large_run_complete"])
            self.assertTrue(summary["publication_rows_complete"])
            self.assertEqual(
                summary["terminal_manifest_integrity"]["status"],
                "UNSAFE",
            )

    def test_p2_v2_rejects_wal_result_tamper_and_raw_receipt_line(self) -> None:
        for mutation in ("result_tamper", "raw_receipt"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                    root,
                    post_ids=[101],
                )
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                journal_path = Path(manifest["publication_commit_journal"])
                event = json.loads(journal_path.read_text(encoding="utf-8"))
                if mutation == "result_tamper":
                    event["result"]["error"] = "tampered WAL result"
                    payload = event
                else:
                    payload = event["receipt"]
                journal_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                recovered_path = root / "recovered.json"

                summary = recover(
                    result_path=result_path,
                    checkpoint_path=checkpoint_path,
                    pending_snapshot_path=pending_path,
                    manifest_path=manifest_path,
                    recovered_output_path=recovered_path,
                    summary_output_path=root / "summary.json",
                )

                self.assertEqual(summary["exact_once_status"], "UNSAFE")
                self.assertTrue(summary["exact_once"]["journal_errors"])
                self.assertFalse(recovered_path.exists())

    def test_p2_v2_rejects_wrapper_result_that_differs_from_wal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, rows = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            different_result = self._error_result(101)
            different_result["error"] = "different secondary copy"
            different_receipt = compute_publication_decision_commit(
                different_result,
                publication_scope_id=manifest["publication_scope_id"],
                attempt_run_id="secondary-attempt",
                input_index=1,
                post_id=101,
            )
            mismatched_wrapper = {
                "global_idx": 1,
                "post_id": 101,
                "status": "completed",
                "publication_commit": different_receipt.to_dict(),
                "result": different_result,
            }
            checkpoint_path.write_text(
                json.dumps(mismatched_wrapper) + "\n",
                encoding="utf-8",
            )
            result_path.write_text(json.dumps([rows[0]["result"]]), encoding="utf-8")
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
            self.assertTrue(summary["exact_once"]["journal_correspondence_errors"])
            self.assertTrue(recovered_path.exists())
            self.assertFalse(summary["large_run_complete"])

    def test_p2_pending_flush_rejects_non_prefix_final(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_pending_gap_artifacts(
                root,
                non_prefix_final=True,
            )
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once"]["completed_subset_gate"], "GO")
            self.assertEqual(summary["exact_once_status"], "INCOMPLETE")
            self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
            self.assertFalse(summary["exact_once"]["final_order_match"])
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertTrue(recovered_path.exists())

    def test_p2_source_artifact_parse_anomalies_are_unsafe(self) -> None:
        mutations = ("journal_utf8", "checkpoint_non_object", "pending_non_object")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                    root,
                    post_ids=[101],
                )
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if mutation == "journal_utf8":
                    journal_path = Path(manifest["publication_commit_journal"])
                    journal_path.write_bytes(b"\xff" + journal_path.read_bytes())
                elif mutation == "checkpoint_non_object":
                    with checkpoint_path.open("a", encoding="utf-8", newline="\n") as handle:
                        handle.write("[]\n")
                else:
                    pending_path.write_text("[123]", encoding="utf-8")
                recovered_path = root / "recovered.json"

                summary = recover(
                    result_path=result_path,
                    checkpoint_path=checkpoint_path,
                    pending_snapshot_path=pending_path,
                    manifest_path=manifest_path,
                    recovered_output_path=recovered_path,
                    summary_output_path=root / "summary.json",
                )

                if mutation == "journal_utf8":
                    self.assertEqual(summary["exact_once_gate"], "NO-GO")
                    self.assertEqual(summary["exact_once_status"], "UNSAFE")
                    self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])
                    self.assertFalse(recovered_path.exists())
                else:
                    self.assertEqual(summary["exact_once_gate"], "GO")
                    self.assertEqual(summary["exact_once_status"], "PROVABLE")
                    self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
                    self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])
                    self.assertTrue(recovered_path.exists())
                self.assertFalse(summary["large_run_complete"])

    def test_p2_jsonl_requires_newline_terminated_tail(self) -> None:
        for target in ("checkpoint", "journal"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                    root,
                    post_ids=[101],
                )
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                target_path = (
                    checkpoint_path
                    if target == "checkpoint"
                    else Path(manifest["publication_commit_journal"])
                )
                target_path.write_bytes(target_path.read_bytes().rstrip(b"\n"))

                summary = recover(
                    result_path=result_path,
                    checkpoint_path=checkpoint_path,
                    pending_snapshot_path=pending_path,
                    manifest_path=manifest_path,
                    recovered_output_path=root / "recovered.json",
                    summary_output_path=root / "summary.json",
                )

                if target == "checkpoint":
                    self.assertEqual(summary["exact_once_status"], "PROVABLE")
                    self.assertEqual(summary["exact_once"]["secondary_wrapper_integrity"], "UNSAFE")
                    self.assertTrue(summary["recovered_output_written"])
                else:
                    self.assertEqual(summary["exact_once_status"], "INCOMPLETE")
                    self.assertTrue(summary["exact_once"]["tail_repair_required"])
                    self.assertFalse(summary["recovered_output_written"])
                self.assertFalse(summary["large_run_complete"])

    def test_p2_v2_torn_wal_tail_uses_committed_prefix_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            journal_path = Path(manifest["publication_commit_journal"])
            tail = b'{"uncommitted":'
            torn_bytes = journal_path.read_bytes() + tail
            journal_path.write_bytes(torn_bytes)

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(journal_path.read_bytes(), torn_bytes)
            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertTrue(summary["publication_rows_complete"])
            self.assertTrue(summary["exact_once"]["uncommitted_tail_present"])
            self.assertEqual(summary["exact_once"]["uncommitted_tail_bytes"], len(tail))
            self.assertEqual(
                summary["exact_once"]["uncommitted_tail_sha256"],
                hashlib.sha256(tail).hexdigest(),
            )
            self.assertTrue(summary["exact_once"]["tail_repair_required"])
            self.assertFalse(summary["large_run_complete"])

    def test_p2_v2_complete_invalid_wal_frame_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            journal_path = Path(manifest["publication_commit_journal"])
            journal_path.write_bytes(journal_path.read_bytes() + b"{invalid-frame}\n")
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_status"], "UNSAFE")
            self.assertTrue(summary["exact_once"]["journal_errors"])
            self.assertFalse(recovered_path.exists())

    def test_p2_v2_valid_tail_repair_history_is_not_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            journal_path = Path(manifest["publication_commit_journal"])
            journal_path.write_bytes(journal_path.read_bytes() + b"{truncated")
            descriptor = PublicationScopeDescriptor.from_dict(
                json.loads(
                    Path(manifest["publication_scope_descriptor"]).read_text(
                        encoding="utf-8"
                    )
                )
            )
            repaired_registry = PublicationCommitRegistry(
                journal_path,
                scope_descriptor=descriptor,
                create_new=False,
            )
            self.assertEqual(repaired_registry.tail_repair_count, 1)
            repair_records = repaired_registry.tail_repair_records()
            manifest["publication_commit_tail_repair_count"] = len(repair_records)
            manifest["publication_commit_tail_repair_ledger_sha256"] = hashlib.sha256(
                json.dumps(
                    repair_records,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once"]["tail_repair_record_count"], 1)
            self.assertEqual(summary["exact_once"]["tail_repair_history_status"], "VALID")
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertFalse(summary["exact_once"]["tail_repair_required"])
            self.assertTrue(summary["large_run_complete"])

    def test_p2_v2_tampered_tail_repair_history_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            journal_path = Path(manifest["publication_commit_journal"])
            journal_path.write_bytes(journal_path.read_bytes() + b"{truncated")
            descriptor = PublicationScopeDescriptor.from_dict(
                json.loads(
                    Path(manifest["publication_scope_descriptor"]).read_text(
                        encoding="utf-8"
                    )
                )
            )
            PublicationCommitRegistry(
                journal_path,
                scope_descriptor=descriptor,
                create_new=False,
            )
            repair_path = next(
                journal_path.with_name(journal_path.name + ".tail_repairs").glob(
                    "*.json"
                )
            )
            record = json.loads(repair_path.read_text(encoding="utf-8"))
            manifest["publication_commit_tail_repair_count"] = 1
            manifest["publication_commit_tail_repair_ledger_sha256"] = hashlib.sha256(
                json.dumps(
                    [record],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            record["retained_prefix_sha256"] = "0" * 64
            repair_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            recovered_path = root / "recovered.json"

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=recovered_path,
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once"]["tail_repair_history_status"], "UNSAFE")
            self.assertEqual(summary["exact_once_status"], "UNSAFE")
            self.assertFalse(recovered_path.exists())

    def test_p2_v2_later_repair_supersedes_incomplete_manifest_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["terminal_artifacts_finalized"] = False
            manifest["large_run_complete"] = False
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            journal_path = Path(manifest["publication_commit_journal"])
            journal_path.write_bytes(journal_path.read_bytes() + b"{later-crash")
            descriptor = PublicationScopeDescriptor.from_dict(
                json.loads(
                    Path(manifest["publication_scope_descriptor"]).read_text(
                        encoding="utf-8"
                    )
                )
            )
            PublicationCommitRegistry(
                journal_path,
                scope_descriptor=descriptor,
                create_new=False,
            )

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            binding = summary["exact_once"]["tail_repair_manifest_binding"]
            self.assertEqual(binding["status"], "SUPERSEDED")
            self.assertEqual(binding["declared_count"], 0)
            self.assertEqual(binding["actual_count"], 1)
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertFalse(summary["large_run_complete"])

    def test_p2_v2_terminal_manifest_requires_exact_repair_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            journal_path = Path(manifest["publication_commit_journal"])
            journal_path.write_bytes(journal_path.read_bytes() + b"{terminal-crash")
            descriptor = PublicationScopeDescriptor.from_dict(
                json.loads(
                    Path(manifest["publication_scope_descriptor"]).read_text(
                        encoding="utf-8"
                    )
                )
            )
            PublicationCommitRegistry(
                journal_path,
                scope_descriptor=descriptor,
                create_new=False,
            )

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(
                summary["exact_once"]["tail_repair_history_status"], "VALID"
            )
            self.assertEqual(
                summary["exact_once"]["tail_repair_manifest_binding"]["status"],
                "UNSAFE",
            )
            self.assertEqual(summary["exact_once_status"], "PROVABLE")
            self.assertFalse(summary["large_run_complete"])

    def test_p2_v2_terminal_artifacts_false_keeps_run_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["terminal_artifacts_finalized"] = False
            manifest["large_run_complete"] = True
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertTrue(summary["publication_rows_complete"])
            self.assertFalse(summary["terminal_artifacts_finalized"])
            self.assertFalse(summary["large_run_complete"])

    def test_new_p2_attempt_claim_missing_or_semantically_tampered_is_no_go(self) -> None:
        for mutation in ("missing", "wrong_output"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                    root,
                    post_ids=[101],
                )
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                claim_path = Path(manifest["output_attempt_claim"])
                if mutation == "missing":
                    claim_path.unlink()
                else:
                    claim = json.loads(claim_path.read_text(encoding="utf-8"))
                    claim["output_file"] = str((root / "other.json").resolve())
                    claim_bytes = (
                        json.dumps(claim, ensure_ascii=False, sort_keys=True) + "\n"
                    ).encode("utf-8")
                    claim_path.write_bytes(claim_bytes)
                    manifest["output_attempt_claim_sha256"] = hashlib.sha256(
                        claim_bytes
                    ).hexdigest()
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                summary = recover(
                    result_path=result_path,
                    checkpoint_path=checkpoint_path,
                    pending_snapshot_path=pending_path,
                    manifest_path=manifest_path,
                    recovered_output_path=root / "recovered.json",
                    summary_output_path=root / "summary.json",
                )

                self.assertEqual(summary["exact_once"]["output_attempt_claim"]["status"], "NO-GO")
                self.assertEqual(summary["exact_once_status"], "UNSAFE")
                self.assertFalse(summary["recovered_output_written"])

    def test_legacy_p2_without_attempt_claim_is_not_provable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            Path(manifest["output_attempt_claim"]).unlink()
            manifest.pop("output_attempt_claim")
            manifest.pop("output_attempt_claim_sha256")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(
                summary["exact_once"]["output_attempt_claim"]["status"],
                "NOT_PROVABLE",
            )

    def test_legacy_duplicate_checkpoint_rows_are_not_safe_or_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = {"post_id": 1, "title": "first"}
            (root / "result.json").write_text(json.dumps([row]), encoding="utf-8")
            (root / "checkpoint.jsonl").write_text(
                "\n".join(
                    json.dumps(item)
                    for item in (
                        {"global_idx": 1, "post_id": 1, "status": "completed", "result": row},
                        {"global_idx": 2, "post_id": 1, "status": "completed", "result": row},
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "pending.json").write_text("[]", encoding="utf-8")
            (root / "manifest.json").write_text(
                json.dumps({"run_id": "legacy", "input_post_count": 1}),
                encoding="utf-8",
            )

            summary = recover(
                result_path=root / "result.json",
                checkpoint_path=root / "checkpoint.jsonl",
                pending_snapshot_path=root / "pending.json",
                manifest_path=root / "manifest.json",
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_status"], "NOT_PROVABLE")
            self.assertEqual(summary["integrity_classification"], "requires_manual_review")
            self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])
            self.assertFalse(summary["large_run_complete"])

    def test_p2_current_protocol_v3_and_scope_provenance_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, rows = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["publication_commit_schema"], PUBLICATION_COMMIT_SCHEMA)
            self.assertEqual(
                manifest["publication_commit_journal_schema"],
                PUBLICATION_COMMIT_JOURNAL_SCHEMA,
            )
            self.assertIn("stable_result_sha256", rows[0]["publication_commit"])
            self.assertEqual(summary["exact_once"]["journal_mode"], "current")
            self.assertEqual(summary["scope_provenance_gate"], "GO")
            self.assertEqual(summary["scope_provenance"]["status"], "VALID")
            self.assertEqual(summary["release_attestation_status"], "OPERATOR_ATTESTED")
            self.assertTrue(summary["large_run_complete"])

    def test_p2_scope_config_tamper_is_provenance_unsafe_not_row_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            config_path = Path(manifest["publication_scope_config"])
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            payload["decision_environment"]["LLM_MODEL"] = "tampered-model"
            raw = (
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            config_path.write_bytes(raw)
            manifest["publication_scope_config_sha256"] = hashlib.sha256(raw).hexdigest()
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertTrue(summary["publication_rows_complete"])
            self.assertEqual(summary["scope_provenance_gate"], "NO-GO")
            self.assertEqual(summary["scope_provenance"]["status"], "UNSAFE")
            self.assertEqual(
                summary["integrity_classification"],
                "wal_current_scope_provenance_unsafe",
            )
            self.assertTrue(summary["recovered_output_written"])
            self.assertFalse(summary["large_run_complete"])

    def test_p2_missing_legacy_scope_config_is_not_provable_and_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            Path(manifest["publication_scope_config"]).unlink()
            manifest.pop("publication_scope_config")
            manifest.pop("publication_scope_config_sha256")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertEqual(summary["scope_provenance_gate"], "NOT_PROVABLE")
            self.assertEqual(summary["scope_provenance"]["status"], "NOT_PROVABLE")
            self.assertTrue(summary["publication_rows_complete"])
            self.assertFalse(summary["large_run_complete"])

    def test_p2_terminal_manifest_stale_counts_are_explicitly_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result_path, checkpoint_path, pending_path, manifest_path, _ = self._write_p2_artifacts(
                root,
                post_ids=[101],
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["completed_count"] = 0
            manifest["publication_commit_count"] = 0
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            summary = recover(
                result_path=result_path,
                checkpoint_path=checkpoint_path,
                pending_snapshot_path=pending_path,
                manifest_path=manifest_path,
                recovered_output_path=root / "recovered.json",
                summary_output_path=root / "summary.json",
            )

            self.assertEqual(summary["exact_once_gate"], "GO")
            self.assertTrue(summary["publication_rows_complete"])
            self.assertEqual(summary["terminal_manifest_integrity"]["status"], "UNSAFE")
            self.assertEqual(
                summary["integrity_classification"],
                "wal_current_terminal_manifest_unsafe",
            )
            self.assertFalse(summary["large_run_complete"])


if __name__ == "__main__":
    unittest.main()
