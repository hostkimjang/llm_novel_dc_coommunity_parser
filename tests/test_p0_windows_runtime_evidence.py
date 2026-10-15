from __future__ import annotations

import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest

from llm_batch.grounding import p0_windows_runtime_evidence as contract


VOLUME = "11111111-2222-3333-4444-555555555555"


def _synthetic_receipt() -> dict[str, object]:
    categories = []
    for index, category in enumerate(contract.REQUIRED_PROTECTED_CATEGORIES):
        root = f"\\\\?\\Volume{{{VOLUME}}}\\protected\\category-{index}"
        identity = contract._Identity(root, 1234, f"{index + 1:032x}", False)
        usn_pre = contract._Usn(True, f"\\\\?\\Volume{{{VOLUME}}}", 77, 1, 100, 1, None)
        usn_post = contract._Usn(True, f"\\\\?\\Volume{{{VOLUME}}}", 77, 1, 101, 1, None)
        inventory = contract._Inventory(True, f"{index + 10:064x}", 2, False, None)
        categories.append(
            contract._CategoryEvidence(
                category=category,
                requested_root=root,
                pre_identity=identity,
                post_identity=identity,
                expected_identity_match=True,
                pre_usn=usn_pre,
                post_usn=usn_post,
                pre_inventory=inventory,
                post_inventory=inventory,
                watch=contract._WatchOutcome(
                    True, True, 2, 5, True, False, False, (), None
                ),
                parent_namespace_watch=contract._WatchOutcome(
                    True, True, 2, 5, True, False, False, (), None
                ),
                write_probe=contract._WriteProbe(
                    True, 2, 6, False, True, 5
                ),
            )
        )
    raw = contract._RuntimeRawEvidence(
        windows_observer=True,
        qpc_frequency=10_000_000,
        timeline=tuple(zip(contract._PHASES, range(1, 7))),
        token_created=True,
        token_is_restricted=True,
        impersonation_active_for_operation=True,
        categories=tuple(categories),
        diagnostic_errors=(),
    )
    return contract._receipt(raw, True, None)


def _reseal(value: dict[str, object]) -> dict[str, object]:
    value.pop("evidence_sha256", None)
    value["evidence_sha256"] = contract._canonical_sha256(value)
    return value


def _roots(base: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for index, category in enumerate(contract.REQUIRED_PROTECTED_CATEGORIES):
        root = base / f"category-{index}"
        root.mkdir(parents=True, exist_ok=True)
        values[category] = str(root.resolve())
    return values


class PresentedRuntimeEvidenceTests(unittest.TestCase):
    def test_bounded_current_thread_witness_never_upgrades_process_runtime(self) -> None:
        receipt = _synthetic_receipt()
        self.assertTrue(receipt["bounded_runtime_noninterference_verified"])
        self.assertTrue(
            receipt[
                "current_thread_restricted_token_write_open_denial_verified"
            ]
        )
        self.assertFalse(receipt["os_write_deny_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])

    def test_complete_presented_receipt_is_explicitly_downgraded(self) -> None:
        receipt = contract.validate_windows_runtime_evidence(_synthetic_receipt())

        self.assertTrue(receipt["presented_structure_verified"])
        self.assertTrue(receipt["presented_bounded_claim_well_formed"])
        for field in (
            "same_process_execution_provenance_verified",
            "qpc_monotonic_timeline_verified",
            "root_identity_and_membership_verified",
            "usn_interval_verified",
            "watch_continuity_verified",
            "restricted_parser_write_denial_verified",
            "runtime_noninterference_verified",
            "owner_authority_verified",
            "semantic_quality_verified",
            "p0_exit_authorized",
            "production_authorized",
        ):
            self.assertIs(receipt[field], False, field)
        self.assertEqual(
            receipt["gate_status"],
            "NO_GO_PRESENTED_RECEIPT_CANNOT_PROVE_EXECUTION",
        )
        material = dict(receipt)
        stored = material.pop("receipt_sha256")
        self.assertEqual(contract._canonical_sha256(material), stored)

    def test_self_hash_tamper_is_rejected(self) -> None:
        receipt = _synthetic_receipt()
        receipt["gate_status"] = "GO"
        with self.assertRaisesRegex(
            contract.P0WindowsRuntimeEvidenceError, "self-hash"
        ):
            contract.validate_windows_runtime_evidence(receipt)

    def test_missing_category_overlap_identity_and_timeline_are_rejected(self) -> None:
        cases = []

        missing = _synthetic_receipt()
        missing["categories"].pop()  # type: ignore[union-attr]
        cases.append(("missing", _reseal(missing), "categories"))

        overlap = _synthetic_receipt()
        overlap_categories = overlap["categories"]  # type: ignore[assignment]
        overlap_categories[1]["requested_root"] = (  # type: ignore[index]
            overlap_categories[0]["requested_root"] + "\\nested"  # type: ignore[index,operator]
        )
        cases.append(("overlap", _reseal(overlap), "overlap"))

        identity = _synthetic_receipt()
        identity["categories"][0]["post_identity"]["file_id"] = "f" * 32  # type: ignore[index]
        cases.append(("identity", _reseal(identity), "identity mismatch"))

        timeline = _synthetic_receipt()
        timeline["timeline"][3]["counter"] = 0  # type: ignore[index]
        cases.append(("timeline", _reseal(timeline), "not monotonic"))

        for label, value, message in cases:
            with self.subTest(label=label), self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, message
            ):
                contract.validate_windows_runtime_evidence(value)

    def test_change_watch_gap_overflow_and_write_success_are_rejected(self) -> None:
        variants = []
        changed = _synthetic_receipt()
        changed["categories"][0]["post_inventory"]["sha256"] = "f" * 64  # type: ignore[index]
        variants.append(("changed", _reseal(changed), "inventory changed"))

        event = _synthetic_receipt()
        event["categories"][0]["watch"]["events"] = [  # type: ignore[index]
            {"action": 3, "relative_path": "changed.json"}
        ]
        variants.append(("event", _reseal(event), "change event"))

        gap = _synthetic_receipt()
        gap["categories"][0]["watch"]["gap"] = True  # type: ignore[index]
        gap["categories"][0]["watch"]["continuous"] = False  # type: ignore[index]
        variants.append(("gap", _reseal(gap), "continuity gap"))

        overflow = _synthetic_receipt()
        overflow["categories"][0]["watch"]["overflow"] = True  # type: ignore[index]
        variants.append(("overflow", _reseal(overflow), "overflow"))

        write = _synthetic_receipt()
        probe = write["categories"][0]["write_open_probe"]  # type: ignore[index]
        probe.update({"open_succeeded": True, "denied": False, "error_code": None})
        variants.append(("write", _reseal(write), "write-open denial"))

        for label, value, message in variants:
            with self.subTest(label=label), self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, message
            ):
                contract.validate_windows_runtime_evidence(value)

    def test_usn_discontinuity_and_forbidden_claim_upgrade_are_rejected(self) -> None:
        usn = _synthetic_receipt()
        usn["categories"][0]["post_usn"]["journal_id"] = 78  # type: ignore[index]
        with self.assertRaisesRegex(
            contract.P0WindowsRuntimeEvidenceError, "USN journal interval"
        ):
            contract.validate_windows_runtime_evidence(_reseal(usn))

        upgraded = _synthetic_receipt()
        upgraded["owner_authority_verified"] = True
        with self.assertRaisesRegex(
            contract.P0WindowsRuntimeEvidenceError, "forbidden upgrade"
        ):
            contract.validate_windows_runtime_evidence(_reseal(upgraded))


class ObserverBoundaryTests(unittest.TestCase):
    def test_exact_category_map_and_nonoverlapping_roots_are_required(self) -> None:
        called = False

        def operation() -> None:
            nonlocal called
            called = True

        with tempfile.TemporaryDirectory() as directory:
            values = _roots(Path(directory))
            missing = dict(values)
            missing.pop(contract.REQUIRED_PROTECTED_CATEGORIES[-1])
            with self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, "exact ordered"
            ):
                contract.execute_windows_runtime_evidence(missing, operation)

            overlapping = dict(values)
            overlapping[contract.REQUIRED_PROTECTED_CATEGORIES[1]] = str(
                Path(overlapping[contract.REQUIRED_PROTECTED_CATEGORIES[0]]) / "nested"
            )
            with self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, "non-overlapping"
            ):
                contract.execute_windows_runtime_evidence(overlapping, operation)
        self.assertFalse(called)

    def test_private_state_is_immutable_and_public_receipt_is_detached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = _roots(Path(directory))
            state = contract._execute_windows_runtime_evidence_state(
                roots, lambda: "result"
            )
            self.assertEqual(state.operation_result, "result")
            with self.assertRaises((AttributeError, TypeError)):
                state.bounded_runtime_noninterference_verified = True  # type: ignore[misc]
            with self.assertRaises(TypeError):
                state.detached_receipt["p0_exit_authorized"] = True  # type: ignore[index]
            with self.assertRaises(TypeError):
                state.detached_receipt["categories"][0]["watch"]["gap"] = True  # type: ignore[index]
            self.assertIs(
                contract._consume_windows_runtime_evidence_state(state), state
            )
            with self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, "already consumed"
            ):
                contract._consume_windows_runtime_evidence_state(state)

            result, detached = contract.execute_windows_runtime_evidence(
                roots, lambda: "public"
            )
            self.assertEqual(result, "public")
            detached["p0_exit_authorized"] = True
            self.assertIs(state.detached_receipt["p0_exit_authorized"], False)
            self.assertNotIn("_execute_windows_runtime_evidence_state", contract.__all__)

    def test_fake_copied_and_raw_incoherent_private_states_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = _roots(Path(directory))
            issued = contract._execute_windows_runtime_evidence_state(
                roots, lambda: "issued"
            )
            fake = SimpleNamespace(
                raw_evidence=issued.raw_evidence,
                operation_result=issued.operation_result,
                operation_exception=issued.operation_exception,
                operation_traceback=issued.operation_traceback,
                bounded_runtime_noninterference_verified=(
                    issued.bounded_runtime_noninterference_verified
                ),
                detached_receipt=issued.detached_receipt,
                _execution_seal=issued._execution_seal,
            )
            with self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, "not minted"
            ):
                contract._consume_windows_runtime_evidence_state(fake)

            copied = contract._RuntimeExecutionState(
                issued.raw_evidence,
                issued.operation_result,
                issued.operation_exception,
                issued.operation_traceback,
                issued.bounded_runtime_noninterference_verified,
                issued.detached_receipt,
                issued._execution_seal,
            )
            with self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, "absent, copied"
            ):
                contract._consume_windows_runtime_evidence_state(copied)
            contract._consume_windows_runtime_evidence_state(issued)

            incoherent = contract._execute_windows_runtime_evidence_state(
                roots, lambda: "incoherent"
            )
            forged = contract._thaw_json(incoherent.detached_receipt)
            forged["continuous_watch_verified"] = not forged[
                "continuous_watch_verified"
            ]
            forged.pop("evidence_sha256")
            forged["evidence_sha256"] = contract._canonical_sha256(forged)
            object.__setattr__(
                incoherent, "detached_receipt", contract._freeze_json(forged)
            )
            with self.assertRaisesRegex(
                contract.P0WindowsRuntimeEvidenceError, "disagrees with frozen raw"
            ):
                contract._consume_windows_runtime_evidence_state(incoherent)

    def test_operation_exception_is_rethrown_after_receipt_finalization(self) -> None:
        class MarkerError(RuntimeError):
            pass

        with tempfile.TemporaryDirectory() as directory:
            roots = _roots(Path(directory))

            def fail() -> None:
                raise MarkerError("marker")

            with self.assertRaises(MarkerError) as caught:
                contract.execute_windows_runtime_evidence(roots, fail)
            receipt = caught.exception.p0_windows_runtime_evidence_receipt
            self.assertTrue(receipt["operation_exception_observed"])
            self.assertFalse(receipt["operation_completed"])
            self.assertFalse(receipt["bounded_runtime_noninterference_verified"])
            self.assertEqual(
                [point["phase"] for point in receipt["timeline"]],
                list(contract._PHASES),
            )

    @unittest.skipUnless(os.name == "nt", "requires the real Windows observer")
    def test_probe_only_impersonation_restores_before_validator_callback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = _roots(Path(directory))

            def validator_callback() -> bytes:
                # This source read fails under the restricted token on the
                # integration host; probe-only mode must restore first.
                return Path(contract.__file__).read_bytes()[:16]

            result, receipt = contract.execute_windows_runtime_evidence(
                roots,
                validator_callback,
                impersonate_operation=False,
            )
        self.assertTrue(result)
        token = receipt["restricted_parser_token"]
        self.assertTrue(token["created"])
        self.assertTrue(token["is_restricted"])
        self.assertFalse(token["impersonation_active_for_operation"])
        self.assertTrue(
            all(row["write_open_probe"]["denied"] for row in receipt["categories"])
        )
        self.assertFalse(receipt["os_write_deny_verified"])
        self.assertFalse(
            receipt[
                "current_thread_restricted_token_write_open_denial_verified"
            ]
        )
        self.assertFalse(receipt["bounded_runtime_noninterference_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])

    @unittest.skipUnless(os.name == "nt", "requires the real Windows observer")
    def test_windows_e2e_captures_raw_signals_without_p0_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = _roots(Path(directory))
            result, receipt = contract.execute_windows_runtime_evidence(
                roots, lambda: 42
            )
        self.assertEqual(result, 42)
        self.assertEqual(receipt["platform"], "windows")
        self.assertEqual(
            [point["phase"] for point in receipt["timeline"]],
            list(contract._PHASES),
        )
        self.assertEqual(
            [row["category"] for row in receipt["categories"]],
            list(contract.REQUIRED_PROTECTED_CATEGORIES),
        )
        for row in receipt["categories"]:
            self.assertIsNotNone(row["pre_identity"])
            self.assertEqual(row["pre_identity"], row["post_identity"])
            self.assertTrue(row["write_open_probe"]["attempted"])
        # A temp directory normally permits the requested write-open.  Even if
        # host ACLs deny it, no bounded witness can authorize these claims.
        self.assertFalse(receipt["owner_authority_verified"])
        self.assertFalse(receipt["semantic_quality_verified"])
        self.assertFalse(receipt["p0_exit_authorized"])
        self.assertFalse(receipt["production_authorized"])
        self.assertFalse(receipt["os_write_deny_verified"])
        self.assertTrue(str(receipt["gate_status"]).startswith("NO_GO"))

    @unittest.skipUnless(os.name == "nt", "requires the real Windows observer")
    def test_windows_e2e_detects_protected_tree_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = _roots(Path(directory))
            target = Path(roots[contract.REQUIRED_PROTECTED_CATEGORIES[0]])

            def mutate() -> None:
                # Impersonation is thread-local.  A distinct process-token
                # thread models an external writer while the watched callback
                # window is active.
                worker = threading.Thread(
                    target=lambda: (target / "changed.txt").write_text(
                        "changed", encoding="utf-8"
                    )
                )
                worker.start()
                worker.join()

            _, receipt = contract.execute_windows_runtime_evidence(roots, mutate)
        first = receipt["categories"][0]
        self.assertFalse(first["bounded_category_noninterference_verified"])
        self.assertTrue(
            first["pre_inventory"]["sha256"] != first["post_inventory"]["sha256"]
            or bool(first["watch"]["events"])
        )
        self.assertFalse(receipt["bounded_runtime_noninterference_verified"])

    @unittest.skipUnless(os.name == "nt", "requires the real Windows observer")
    def test_windows_parent_namespace_watch_detects_swap_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            roots = _roots(Path(directory))
            category = contract.REQUIRED_PROTECTED_CATEGORIES[0]
            target = Path(roots[category])
            aside = target.with_name(target.name + "-aside")
            worker_errors: list[BaseException] = []

            def swap_restore_worker() -> None:
                try:
                    target.rename(aside)
                    target.mkdir()
                    replacement_file = target / "replacement.txt"
                    replacement_file.write_text("replacement", encoding="utf-8")
                    replacement_file.unlink()
                    target.rmdir()
                    aside.rename(target)
                except BaseException as exc:
                    worker_errors.append(exc)

            def operation() -> None:
                worker = threading.Thread(target=swap_restore_worker)
                worker.start()
                worker.join()

            _, receipt = contract.execute_windows_runtime_evidence(roots, operation)
        self.assertEqual(worker_errors, [])
        first = receipt["categories"][0]
        self.assertEqual(first["pre_identity"], first["post_identity"])
        self.assertEqual(
            first["pre_inventory"]["sha256"],
            first["post_inventory"]["sha256"],
        )
        parent_watch = first["parent_namespace_watch"]
        self.assertTrue(
            bool(parent_watch["events"])
            or parent_watch["gap"]
            or parent_watch["overflow"]
        )
        self.assertFalse(first["bounded_category_noninterference_verified"])
        self.assertFalse(receipt["continuous_watch_verified"])
        self.assertFalse(receipt["runtime_noninterference_verified"])


if __name__ == "__main__":
    unittest.main()
