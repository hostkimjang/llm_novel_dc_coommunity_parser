from __future__ import annotations

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.llm_batch.ledger.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.ledger.decision_call_readback import read_decision_call_ledger
from src.llm_batch.measurement.early_route_measurement import (
    LANE_CHEAP_NIL,
    EarlyRoutePolicyV1,
    EarlyRouteSourceView,
    canonical_hash as early_route_canonical_hash,
    compare_early_route,
    decide_early_route,
)
from src.llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry,
    PublicationScopeDescriptor,
    commit_publication_result,
    compute_publication_decision_commit,
)
from tests.test_publication_decision_commit import _valid_result as _publication_valid_result
from tests.test_recover_expert_run_from_checkpoint import RecoverExpertRunFromCheckpointTest
from tools.recover_expert_run_from_checkpoint import (
    _validate_fresh_measurement_recovery,
    recover,
)


RUN_SPEC_SHA = "e" * 64
STARTED_AT = "2026-07-12T10:00:00+09:00"
FINISHED_AT = "2026-07-12T10:00:01+09:00"


class FreshMeasurementRecoveryTest(unittest.TestCase):
    def _base_artifacts(self, root: Path) -> tuple[Path, Path, Path, Path, dict]:
        helper = RecoverExpertRunFromCheckpointTest(methodName="runTest")
        result, checkpoint, pending, manifest_path, _ = helper._write_p2_artifacts(
            root, post_ids=[101, 102]
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return result, checkpoint, pending, manifest_path, manifest

    @staticmethod
    def _wal_decisions(manifest: dict) -> dict[int, dict]:
        return {
            int(event["receipt"]["input_index"]): {
                "post_id": event["receipt"]["post_id"],
                "decision_id": event["receipt"]["decision_id"],
            }
            for event in (
                json.loads(line)
                for line in Path(manifest["publication_commit_journal"])
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            )
        }

    def _configure_measurement(
        self,
        manifest: dict,
        manifest_path: Path,
        *,
        mode: str = "complete",
        manifest_arm: str = "BEFORE",
        ledger_arm: str = "BEFORE",
        scope_override: str | None = None,
        link_mismatch: bool = False,
        zero_calls: bool = False,
        early_route_enabled: bool = False,
    ) -> None:
        descriptor = PublicationScopeDescriptor.from_dict(
            json.loads(Path(manifest["publication_scope_descriptor"]).read_text(encoding="utf-8"))
        )
        decisions = self._wal_decisions(manifest)
        ledger_path = manifest_path.with_name("measurement_ledger")
        registry = DecisionCallLedgerRegistry(
            ledger_path,
            scope_descriptor=descriptor,
            create_new=True,
            enabled=True,
            run_spec_sha256=RUN_SPEC_SHA,
            pair_id="pair-recovery",
            arm=ledger_arm,
            fresh_execution_mode=True,
        )

        def write_row(index: int, post_id: int, run_id: str, *, close: str = "seal") -> None:
            row = registry.row_attempt(
                attempt_run_id=run_id,
                row_attempt_id=f"{run_id}-row-{index}",
                input_index=index,
                post_id=post_id,
            )
            if zero_calls:
                registry.seal_row(
                    row,
                    sealed_at=FINISHED_AT,
                    monotonic_finished_ns=1_100_000_000 + index,
                )
                decision_id = decisions[index]["decision_id"]
                registry.link_publication(
                    row,
                    publication_decision_id=(
                        "f" * 64 if link_mismatch and index == 1 else decision_id
                    ),
                    linked_at=FINISHED_AT,
                )
                return
            call_id = f"{run_id}-call-{index}"
            registry.record_dispatch_intent(
                row,
                logical_call_id=f"logical-{index}",
                call_id=call_id,
                retry_ordinal=0,
                retry_of_call_id=None,
                stage="GATEKEEPER",
                modality="TEXT",
                requested_model="requested-model",
                resolved_model=None,
                endpoint="http://127.0.0.1:8000/v1",
                backend="http",
                started_at=STARTED_AT,
                monotonic_started_ns=1_000_000_000 + index,
                request_sha256="a" * 64,
            )
            if close == "open":
                return
            if close == "abort":
                registry.abort_row(
                    row,
                    reason_code="TEST_ABORT",
                    aborted_at=FINISHED_AT,
                    monotonic_finished_ns=1_100_000_000 + index,
                )
                return
            registry.record_terminal(
                row,
                call_id=call_id,
                terminal_status="SUCCEEDED",
                resolved_model="resolved-model",
                response_sha256="b" * 64,
                usage_provenance="PROVIDER_REPORTED",
                prompt_tokens=10,
                completion_tokens=2,
                total_tokens=12,
                finished_at=FINISHED_AT,
                monotonic_finished_ns=1_100_000_000 + index,
            )
            registry.seal_row(
                row,
                sealed_at=FINISHED_AT,
                monotonic_finished_ns=1_100_000_000 + index,
            )
            decision_id = decisions[index]["decision_id"]
            registry.link_publication(
                row,
                publication_decision_id=("f" * 64 if link_mismatch and index == 1 else decision_id),
                linked_at=FINISHED_AT,
            )

        if mode == "partial":
            write_row(1, 101, "p2-test")
        elif mode == "open":
            write_row(1, 101, "p2-test", close="open")
            write_row(2, 102, "p2-test")
        elif mode == "aborted":
            write_row(1, 101, "p2-test", close="abort")
            write_row(2, 102, "p2-test")
        elif mode == "multi":
            write_row(1, 101, "p2-test")
            write_row(2, 102, "p2-test-alt")
        else:
            write_row(1, 101, "p2-test")
            write_row(2, 102, "p2-test")

        scope_sha = json.loads((ledger_path / "scope.json").read_text(encoding="utf-8"))["scope_sha256"]
        measurement = {
            "mode": "REQUIRED",
            "run_spec_sha256": RUN_SPEC_SHA,
            "pair_id": "pair-recovery",
            "arm": manifest_arm,
            "execution_mode": "FRESH_EXECUTION_REQUIRED",
            "binding_status": "BOUND",
            "fresh_execution_required": True,
            "actual_kpi_eligible": True,
        }
        if early_route_enabled:
            mutable_context = {
                "schema_version": "paired_measurement_mutable_context_binding_v1",
                "mutable_context_mode": "FROZEN_OFF",
                "batch_context_enabled": False,
                "slang_access_mode": "OFF",
                "central_slang_db_write_allowed": False,
            }
            measurement.update(
                {
                    "early_route_mode": "SOURCE_ONLY_V1",
                    "early_route_enabled": True,
                    "early_route_enable_status": "ENABLED_AFTER_REQUIRED_FRESH_SOURCE_ONLY_V1",
                    "mutable_context_mode": "FROZEN_OFF",
                    "mutable_context_frozen": True,
                    "slang_access_mode": "OFF",
                    "central_slang_db_write_allowed": False,
                    "mutable_context_binding": mutable_context,
                    "mutable_context_binding_sha256": early_route_canonical_hash(
                        mutable_context
                    ),
                }
            )
        manifest.update(
            {
                "publication_execution_mode": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
                "decision_call_measurement": measurement,
                "decision_call_ledger_path": str(ledger_path),
                "decision_call_ledger_scope_sha256": scope_override or scope_sha,
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def _recover(self, root: Path, result: Path, checkpoint: Path, pending: Path, manifest: Path) -> dict:
        return recover(
            result_path=result,
            checkpoint_path=checkpoint,
            pending_snapshot_path=pending,
            manifest_path=manifest,
            recovered_output_path=root / "recovered.json",
            summary_output_path=root / "summary.json",
        )

    @staticmethod
    def _make_checkpoint_receipts_attempt_local(manifest: dict, checkpoint_path: Path) -> None:
        rows = [
            json.loads(line)
            for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in rows:
            result = dict(row["result"])
            result["run_meta"] = {
                "run_id": "p2-test",
                "decision_call_measurement": {
                    "pair_id": "pair-recovery",
                    "arm": "BEFORE",
                },
                "measurement_execution_source": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
            }
            row["result"] = result
            row["publication_commit"] = compute_publication_decision_commit(
                row["result"],
                publication_scope_id=manifest["publication_scope_id"],
                attempt_run_id="p2-test",
                input_index=row["global_idx"],
                post_id=row["post_id"],
            ).to_dict()
        checkpoint_path.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
        Path(manifest["output_file"]).write_text(
            json.dumps([row["result"] for row in rows]), encoding="utf-8"
        )

    @staticmethod
    def _early_execution_receipt(decision) -> dict:
        payload = {
            "schema_version": "early_route_execution_receipt_v1",
            "mode": "SOURCE_ONLY_V1",
            "route_decision": decision.to_dict(),
            "execution_status": "CHEAP_ZERO_CALL_AUTHORITATIVE_REFERENCE_COPY",
            "compute_skip_applied": True,
            "public_action_applied": False,
            "production_enable_allowed": False,
            "accuracy_status": "NOT_ESTIMABLE",
        }
        return {**payload, "receipt_sha256": early_route_canonical_hash(payload)}

    def _replace_p2_wal_with_hold_rows(
        self,
        manifest: dict,
        result_path: Path,
        checkpoint_path: Path,
    ) -> None:
        descriptor = PublicationScopeDescriptor.from_dict(
            json.loads(Path(manifest["publication_scope_descriptor"]).read_text(encoding="utf-8"))
        )
        journal_path = Path(manifest["publication_commit_journal"])
        journal_path.unlink()
        registry = PublicationCommitRegistry(
            journal_path,
            scope_descriptor=descriptor,
            create_new=True,
        )
        rows = []
        for index, post_id in enumerate(descriptor.post_ids, 1):
            result = _publication_valid_result(post_id=int(post_id), publish=False)
            receipt, _ = commit_publication_result(
                result,
                registry=registry,
                attempt_run_id="authoritative-hold",
                input_index=index,
                post_id=post_id,
            )
            rows.append(
                {
                    "global_idx": index,
                    "post_id": post_id,
                    "status": "completed",
                    "publication_commit": receipt.to_dict(),
                    "result": result,
                }
            )
        checkpoint_path.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
        result_path.write_text(
            json.dumps([row["result"] for row in rows]),
            encoding="utf-8",
        )

    @staticmethod
    def _early_route_aggregate(
        *,
        measurement: dict,
        row_bindings: list[dict],
        expected_input_count: int,
    ) -> dict:
        cheap_count = sum(
            binding["selected_lane"] == LANE_CHEAP_NIL for binding in row_bindings
        )
        payload = {
            "schema_version": "early_route_manifest_aggregate_v1",
            "mode": "SOURCE_ONLY_V1",
            "enabled": True,
            "measurement_arm": "AFTER",
            "mutable_context_mode": measurement["mutable_context_mode"],
            "mutable_context_binding_sha256": measurement[
                "mutable_context_binding_sha256"
            ],
            "slang_access_mode": measurement["slang_access_mode"],
            "central_slang_db_write_allowed": measurement[
                "central_slang_db_write_allowed"
            ],
            "expected_input_count": expected_input_count,
            "observed_route_count": expected_input_count,
            "observed_comparison_count": expected_input_count,
            "cheap_count": cheap_count,
            "full_count": expected_input_count - cheap_count,
            "cheap_zero_call_writer_verified_count": cheap_count,
            "missing_route_count": 0,
            "missing_comparison_count": 0,
            "row_bindings": row_bindings,
            "row_bindings_sha256": early_route_canonical_hash(row_bindings),
            "execution_gate": "GO",
            "execution_reason_codes": [],
            "production_enable_allowed": False,
            "accuracy_status": "NOT_ESTIMABLE",
            "gate": "NO_GO_ACCURACY_NOT_ESTIMABLE",
        }
        return {**payload, "aggregate_sha256": early_route_canonical_hash(payload)}

    def _make_after_early_route_fixture(
        self,
        root: Path,
        *,
        zero_calls: bool = True,
        forge_zero_call_claim: bool = False,
    ) -> tuple[Path, Path, Path, Path, dict]:
        result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
        self._replace_p2_wal_with_hold_rows(manifest, result, checkpoint)
        self._configure_measurement(
            manifest,
            manifest_path,
            manifest_arm="AFTER",
            ledger_arm="AFTER",
            zero_calls=zero_calls,
            early_route_enabled=True,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        measurement = manifest["decision_call_measurement"]
        wal_events = {
            int(event["receipt"]["input_index"]): event["receipt"]
            for event in (
                json.loads(line)
                for line in Path(manifest["publication_commit_journal"])
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            )
        }
        ledger_rows = {
            int(row["input_index"]): row
            for row in read_decision_call_ledger(Path(manifest["decision_call_ledger_path"]))[
                "rows"
            ]
        }
        rows = [
            json.loads(line)
            for line in checkpoint.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        row_bindings: list[dict] = []
        for row in rows:
            index = int(row["global_idx"])
            post_id = int(row["post_id"])
            source = EarlyRouteSourceView.create(
                publication_scope_id=manifest["publication_scope_id"],
                pair_id=measurement["pair_id"],
                arm="AFTER",
                input_index=index,
                post_id=post_id,
                source_input_sha256=early_route_canonical_hash(
                    {"post_id": post_id, "index": index, "source": "fixture"}
                ),
                title="ㅋㅋㅋ",
            )
            decision = decide_early_route(source, EarlyRoutePolicyV1.create())
            self.assertEqual(decision.selected_lane, LANE_CHEAP_NIL)
            execution = self._early_execution_receipt(decision)
            result_item = deepcopy(row["result"])
            result_item["run_meta"] = {
                "run_id": manifest["run_id"],
                "decision_call_measurement": deepcopy(measurement),
                "measurement_execution_source": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
                "early_route_measurement": {
                    "execution_receipt": execution,
                    "comparison_receipt": None,
                },
            }
            preview = compute_publication_decision_commit(
                result_item,
                publication_scope_id=manifest["publication_scope_id"],
                attempt_run_id=manifest["run_id"],
                input_index=index,
                post_id=post_id,
            )
            authoritative = wal_events[index]
            comparison = compare_early_route(
                decision,
                authoritative_wal_receipt_sha256=authoritative["commit_sha256"],
                authoritative_wal_outcome=authoritative["outcome"],
                authoritative_publish_allowed=False,
                authoritative_title=None,
                authoritative_url=None,
                public_projection_before_sha256=authoritative[
                    "public_projection_sha256"
                ],
                public_projection_after_sha256=preview.public_projection_sha256,
            ).to_dict()
            result_item["run_meta"]["early_route_measurement"][
                "comparison_receipt"
            ] = comparison
            row["result"] = result_item
            row["publication_commit"] = compute_publication_decision_commit(
                result_item,
                publication_scope_id=manifest["publication_scope_id"],
                attempt_run_id=manifest["run_id"],
                input_index=index,
                post_id=post_id,
            ).to_dict()
            ledger_row = ledger_rows[index]
            row_bindings.append(
                {
                    "input_index": index,
                    "post_id": decision.post_id,
                    "selected_lane": decision.selected_lane,
                    "source_view_sha256": decision.source_view_sha256,
                    "policy_sha256": decision.policy_sha256,
                    "route_decision_sha256": decision.decision_sha256,
                    "execution_receipt_sha256": execution["receipt_sha256"],
                    "comparison_receipt_sha256": comparison["receipt_sha256"],
                    "comparison_gate": comparison["gate"],
                    "decision_call_event_root_sha256": ledger_row["event_root_sha256"],
                    "cheap_zero_call_writer_verified": (
                        True if forge_zero_call_claim else zero_calls
                    ),
                }
            )
        checkpoint.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
        result.write_text(
            json.dumps([row["result"] for row in rows]),
            encoding="utf-8",
        )
        manifest["early_route_measurement"] = self._early_route_aggregate(
            measurement=measurement,
            row_bindings=row_bindings,
            expected_input_count=len(rows),
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return result, checkpoint, pending, manifest_path, manifest

    @staticmethod
    def _rewrite_checkpoint_attempt_receipts(
        manifest: dict,
        checkpoint_path: Path,
    ) -> None:
        rows = [
            json.loads(line)
            for line in checkpoint_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for row in rows:
            row["publication_commit"] = compute_publication_decision_commit(
                row["result"],
                publication_scope_id=manifest["publication_scope_id"],
                attempt_run_id=manifest["run_id"],
                input_index=row["global_idx"],
                post_id=row["post_id"],
            ).to_dict()
        checkpoint_path.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n",
            encoding="utf-8",
        )
        Path(manifest["output_file"]).write_text(
            json.dumps([row["result"] for row in rows]), encoding="utf-8"
        )

    def test_direct_complete_single_attempt_is_go_and_wal_is_not_mutated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
            self._configure_measurement(manifest, manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self._make_checkpoint_receipts_attempt_local(manifest, checkpoint)
            before = Path(manifest["publication_commit_journal"]).read_bytes()
            gate = _validate_fresh_measurement_recovery(
                manifest=manifest,
                manifest_path=manifest_path,
                canonical_wal_decision_ids=self._wal_decisions(manifest),
            )
            self.assertEqual(gate["status"], "GO")
            self.assertEqual(gate["actual_kpi_status"], "INDEPENDENTLY_VERIFIED_EXACT")
            summary = self._recover(root, result, checkpoint, pending, manifest_path)
            after = Path(manifest["publication_commit_journal"]).read_bytes()
            self.assertEqual(before, after)
            self.assertEqual(summary["fresh_measurement_recovery"]["status"], "GO")
            self.assertTrue(summary["fresh_measurement_recovery"]["publication_wal_unchanged"])
            self.assertTrue(summary["large_run_complete"])
            self.assertTrue(summary["recovery_safe_to_use_as_completed_subset"])

    def test_after_early_route_exact_receipts_are_independently_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, checkpoint, pending, manifest_path, manifest = (
                self._make_after_early_route_fixture(root)
            )
            summary = self._recover(root, result, checkpoint, pending, manifest_path)
            gate = summary["fresh_measurement_recovery"]
            self.assertEqual(gate["status"], "GO")
            self.assertEqual(gate["recovery_action"], "NONE")
            self.assertEqual(
                gate["early_route_recovery"]["independent_route_receipt_count"], 2
            )
            self.assertEqual(
                gate["early_route_recovery"][
                    "independent_cheap_zero_call_verified_count"
                ],
                2,
            )
            self.assertEqual(summary["logical_publication_recovery"]["status"], "GO")
            self.assertTrue(summary["large_run_complete"])

    def test_after_early_route_missing_tampered_partial_and_nonzero_cheap_are_no_go(self) -> None:
        for label in ("missing", "tampered", "partial", "cheap-nonzero"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result, checkpoint, pending, manifest_path, manifest = (
                    self._make_after_early_route_fixture(
                        root,
                        zero_calls=label != "cheap-nonzero",
                        forge_zero_call_claim=label == "cheap-nonzero",
                    )
                )
                if label == "missing":
                    rows = [
                        json.loads(line)
                        for line in checkpoint.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]
                    rows[0]["result"]["run_meta"].pop("early_route_measurement")
                    checkpoint.write_text(
                        "\n".join(json.dumps(row) for row in rows) + "\n",
                        encoding="utf-8",
                    )
                    self._rewrite_checkpoint_attempt_receipts(manifest, checkpoint)
                elif label == "tampered":
                    manifest["early_route_measurement"]["aggregate_sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                elif label == "partial":
                    aggregate = manifest["early_route_measurement"]
                    aggregate["row_bindings"] = aggregate["row_bindings"][:1]
                    aggregate["row_bindings_sha256"] = early_route_canonical_hash(
                        aggregate["row_bindings"]
                    )
                    aggregate["observed_route_count"] = 1
                    aggregate["observed_comparison_count"] = 1
                    aggregate["cheap_count"] = 1
                    aggregate["full_count"] = 0
                    aggregate["cheap_zero_call_writer_verified_count"] = 1
                    aggregate["missing_route_count"] = 1
                    aggregate["missing_comparison_count"] = 1
                    aggregate["execution_gate"] = "NO_GO"
                    aggregate["execution_reason_codes"] = ["ROUTE_COVERAGE_INCOMPLETE"]
                    aggregate["aggregate_sha256"] = early_route_canonical_hash(
                        {
                            key: value
                            for key, value in aggregate.items()
                            if key != "aggregate_sha256"
                        }
                    )
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                summary = self._recover(root, result, checkpoint, pending, manifest_path)
                gate = summary["fresh_measurement_recovery"]
                self.assertEqual(gate["status"], "NO-GO")
                self.assertEqual(
                    gate["recovery_action"], "FULL_FRESH_ARM_RERUN_REQUIRED"
                )
                self.assertFalse(summary["large_run_complete"])
                self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])
                self.assertEqual(
                    summary["logical_publication_recovery"]["status"], "GO"
                )
                if label == "missing":
                    self.assertIn(
                        "EARLY_ROUTE_CHECKPOINT_RECEIPTS_MISSING", gate["reason_codes"]
                    )
                elif label == "tampered":
                    self.assertIn(
                        "EARLY_ROUTE_MANIFEST_AGGREGATE_HASH_INVALID",
                        gate["reason_codes"],
                    )
                elif label == "partial":
                    self.assertIn(
                        "EARLY_ROUTE_MANIFEST_AGGREGATE_CONTRACT_MISMATCH",
                        gate["reason_codes"],
                    )
                else:
                    self.assertIn(
                        "EARLY_ROUTE_CHEAP_ZERO_CALL_NOT_PROVEN", gate["reason_codes"]
                    )

    def test_partial_fresh_ledger_keeps_logical_recovery_but_blocks_measurement_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
            self._configure_measurement(manifest, manifest_path, mode="partial")
            summary = self._recover(root, result, checkpoint, pending, manifest_path)
            self.assertEqual(summary["logical_publication_recovery"]["status"], "GO")
            self.assertEqual(summary["fresh_measurement_recovery"]["status"], "NO-GO")
            self.assertEqual(
                summary["fresh_measurement_recovery"]["recovery_action"],
                "FULL_FRESH_ARM_RERUN_REQUIRED",
            )
            self.assertFalse(summary["large_run_complete"])
            self.assertFalse(summary["recovery_safe_to_use_as_completed_subset"])

    def test_authoritative_link_mismatch_is_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
            self._configure_measurement(manifest, manifest_path, link_mismatch=True)
            summary = self._recover(root, result, checkpoint, pending, manifest_path)
            self.assertIn(
                "AUTHORITATIVE_WAL_LINK_MISMATCH",
                summary["fresh_measurement_recovery"]["reason_codes"],
            )
            self.assertFalse(summary["large_run_complete"])

    def test_binding_and_scope_mismatches_are_no_go(self) -> None:
        for label, kwargs, expected_reason in (
            ("binding", {"manifest_arm": "AFTER"}, "DECISION_CALL_MEASUREMENT_BINDING_MISMATCH"),
            ("scope", {"scope_override": "0" * 64}, "DECISION_CALL_LEDGER_SCOPE_SHA256_MISMATCH"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
                self._configure_measurement(manifest, manifest_path, **kwargs)
                summary = self._recover(root, result, checkpoint, pending, manifest_path)
                self.assertIn(expected_reason, summary["fresh_measurement_recovery"]["reason_codes"])
                self.assertFalse(summary["large_run_complete"])

    def test_required_manifest_tampering_never_becomes_not_applicable(self) -> None:
        for label, mutation in (
            ("fresh-flag", {"fresh_execution_required": False}),
            ("execution-mode", {"execution_mode": "NORMAL"}),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
                self._configure_measurement(manifest, manifest_path)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["publication_execution_mode"] = "FRESH_EXECUTION_NO_PUBLIC_WRITE"
                manifest["decision_call_measurement"].update(mutation)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                summary = self._recover(root, result, checkpoint, pending, manifest_path)
                gate = summary["fresh_measurement_recovery"]
                self.assertEqual(gate["status"], "NO-GO")
                self.assertIn("MEASUREMENT_MANIFEST_BINDING_INVALID", gate["reason_codes"])
                self.assertFalse(summary["large_run_complete"])

    def test_required_measurement_without_fresh_publication_mode_is_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
            self._configure_measurement(manifest, manifest_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("publication_execution_mode", None)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            summary = self._recover(root, result, checkpoint, pending, manifest_path)
            gate = summary["fresh_measurement_recovery"]
            self.assertEqual(gate["status"], "NO-GO")
            self.assertIn(
                "PUBLICATION_FRESH_MODE_MEASUREMENT_INCONSISTENT",
                gate["reason_codes"],
            )
            self.assertFalse(summary["large_run_complete"])

    def test_direct_rejects_invalid_bindings_and_publication_scope(self) -> None:
        for label, mutation, expected_reason in (
            ("run-spec", {"run_spec_sha256": "X" * 64}, "MEASUREMENT_MANIFEST_BINDING_INVALID"),
            ("pair", {"pair_id": ""}, "MEASUREMENT_MANIFEST_BINDING_INVALID"),
            ("arm", {"arm": "INVALID"}, "MEASUREMENT_MANIFEST_BINDING_INVALID"),
            ("scope", {"publication_scope_id": "0" * 64}, "DECISION_CALL_LEDGER_PUBLICATION_SCOPE_MISMATCH"),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, _, _, manifest_path, manifest = self._base_artifacts(root)
                self._configure_measurement(manifest, manifest_path)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if label == "scope":
                    manifest.update(mutation)
                else:
                    manifest["decision_call_measurement"].update(mutation)
                gate = _validate_fresh_measurement_recovery(
                    manifest=manifest,
                    manifest_path=manifest_path,
                    canonical_wal_decision_ids=self._wal_decisions(
                        json.loads(manifest_path.read_text(encoding="utf-8"))
                    ),
                )
                self.assertEqual(gate["status"], "NO-GO")
                self.assertIn(expected_reason, gate["reason_codes"])

    def test_wal_snapshot_change_forces_measurement_no_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
            self._configure_measurement(manifest, manifest_path)
            with patch(
                "tools.recover_expert_run_from_checkpoint._wal_snapshot",
                side_effect=[
                    {"sha256": "1" * 64, "event_count": 2},
                    {"sha256": "2" * 64, "event_count": 3},
                ],
            ):
                summary = self._recover(root, result, checkpoint, pending, manifest_path)
            gate = summary["fresh_measurement_recovery"]
            self.assertEqual(gate["status"], "NO-GO")
            self.assertFalse(gate["measurement_eligible"])
            self.assertEqual(gate["actual_kpi_status"], "NOT_ESTIMABLE")
            self.assertIn("PUBLICATION_WAL_CHANGED_DURING_RECOVERY", gate["reason_codes"])
            self.assertFalse(summary["large_run_complete"])

    def test_aborted_open_and_multiple_attempt_ledgers_are_no_go(self) -> None:
        for mode in ("aborted", "open", "multi"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                result, checkpoint, pending, manifest_path, manifest = self._base_artifacts(root)
                self._configure_measurement(manifest, manifest_path, mode=mode)
                summary = self._recover(root, result, checkpoint, pending, manifest_path)
                gate = summary["fresh_measurement_recovery"]
                self.assertEqual(gate["status"], "NO-GO")
                self.assertEqual(gate["actual_kpi_status"], "NOT_ESTIMABLE")
                self.assertEqual(gate["recovery_action"], "FULL_FRESH_ARM_RERUN_REQUIRED")
                self.assertFalse(summary["large_run_complete"])


if __name__ == "__main__":
    unittest.main()
