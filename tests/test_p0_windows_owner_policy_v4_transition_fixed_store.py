from __future__ import annotations

import inspect
import os
import unittest

from llm_batch.grounding import p0_windows_owner_policy_v4_transition_fixed_store as store
from llm_batch.grounding import p0_windows_fixed_directory_identity as fixed


@unittest.skipUnless(os.name == "nt", "Windows transition fixed-store test")
class TransitionFixedStoreTests(unittest.TestCase):
    def test_public_api_is_zero_argument(self) -> None:
        self.assertEqual(
            list(inspect.signature(store.observe_fixed_windows_owner_policy_v4_transition_store).parameters),
            [],
        )

    def test_compiled_inventory_is_twenty_one_roles_nine_files_three_watches(self) -> None:
        self.assertEqual(len(store.ROLE_SEQUENCE), 21)
        self.assertEqual(len(store.FILE_ROLE_SEQUENCE), 9)
        self.assertEqual(len(store.WATCH_SCOPE_SEQUENCE), 3)
        self.assertEqual(len(set(store.ROLE_SEQUENCE)), 21)

    def test_current_host_is_deterministic_component_only_no_go(self) -> None:
        first = store.observe_fixed_windows_owner_policy_v4_transition_store()
        second = store.observe_fixed_windows_owner_policy_v4_transition_store()
        self.assertEqual(first, second)
        self.assertEqual(tuple(first), store._RECEIPT_FIELDS)
        self.assertEqual(first["decision"], "NO_GO")
        self.assertTrue(all(first[field] is False for field in store._FALSE_FIELDS))
        self.assertEqual(first["credited_actual_source_claim_count"], 0)
        self.assertEqual(first["credited_actual_a_context_review_count"], 0)

    def test_failure_helper_code_mutation_is_detected(self) -> None:
        original = store._failure_receipt.__code__
        def forged(stage):
            return {}
        try:
            store._failure_receipt.__code__ = forged.__code__
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store.observe_fixed_windows_owner_policy_v4_transition_store()
        finally:
            store._failure_receipt.__code__ = original

    def test_integrity_checker_code_mutation_is_detected_by_public_boundary(self) -> None:
        original = store._assert_integrity.__code__
        def forged():
            return None
        try:
            store._assert_integrity.__code__ = forged.__code__
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store.observe_fixed_windows_owner_policy_v4_transition_store()
        finally:
            store._assert_integrity.__code__ = original

    def test_observe_held_code_mutation_is_detected(self) -> None:
        original = store._observe_held.__code__
        def forged(*, program_data, watches, v3_paths, v4_paths):
            return {}
        try:
            store._observe_held.__code__ = forged.__code__
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store.observe_fixed_windows_owner_policy_v4_transition_store()
        finally:
            store._observe_held.__code__ = original

    def test_query_snapshot_dependency_code_mutation_is_detected(self) -> None:
        original = fixed._query_snapshot.__code__
        def forged(api, handle, *, include_streams):
            return None
        try:
            fixed._query_snapshot.__code__ = forged.__code__
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store._assert_integrity()
        finally:
            fixed._query_snapshot.__code__ = original

    def test_known_folder_selector_rebinding_is_detected(self) -> None:
        original = store.v3_store._KnownFolderApi
        class ForgedKnownFolderApi:
            pass
        try:
            store.v3_store._KnownFolderApi = ForgedKnownFolderApi
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store._assert_integrity()
        finally:
            store.v3_store._KnownFolderApi = original

    def test_known_folder_class_init_in_place_mutation_is_detected(self) -> None:
        original = store.v3_store._KnownFolderApi.__init__.__code__
        def forged(self):
            return None
        try:
            store.v3_store._KnownFolderApi.__init__.__code__ = forged.__code__
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store._assert_integrity()
        finally:
            store.v3_store._KnownFolderApi.__init__.__code__ = original

    def test_path_join_dependency_rebinding_is_detected(self) -> None:
        original = store.os.path.join
        def forged(*parts):
            return r"C:\attacker"
        try:
            store.os.path.join = forged
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store._assert_integrity()
        finally:
            store.os.path.join = original

    def test_open_reparse_point_flag_mutation_is_detected(self) -> None:
        original = store.fixed._FILE_FLAG_OPEN_REPARSE_POINT
        try:
            store.fixed._FILE_FLAG_OPEN_REPARSE_POINT = 0
            with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                store._assert_integrity()
        finally:
            store.fixed._FILE_FLAG_OPEN_REPARSE_POINT = original

    def test_v3_signed_identity_cross_binding_is_present(self) -> None:
        source = inspect.getsource(store._observe_held)
        self.assertIn('signed_v3_objects', source)
        self.assertIn('final_volume_guid_path', source)
        self.assertIn('signed/live V3 object identity mismatch', source)

    def test_watch_rows_reject_duplicate_or_wrong_scope_evidence(self) -> None:
        program_data = store.v3_store._program_data_path(store.v3_store._KnownFolderApi())
        common = store.os.path.join(
            program_data, store.v3_contract.FIXED_POLICY_STORE_SUFFIX[0]
        )
        rows = [
            {
                "requested_path": common,
                "final_path": r"\\?\Volume{00000000-0000-0000-0000-000000000001}\llm-novel-dc",
                "volume_serial_decimal": "1", "file_id_128_hex": "01" * 16,
                "notify_filter": store._V4_WATCH_FILTER_PIN,
                "completion_status": "CANCELED_PENDING_AT_END", "clean": True,
            },
            {
                "requested_path": common + r"\p0-owner-policy-v1",
                "final_path": r"\\?\Volume{00000000-0000-0000-0000-000000000001}\llm-novel-dc\p0-owner-policy-v1",
                "volume_serial_decimal": "1", "file_id_128_hex": "02" * 16,
                "notify_filter": store._V4_WATCH_FILTER_PIN,
                "completion_status": "CANCELED_PENDING_AT_END", "clean": True,
            },
            {
                "requested_path": common + r"\p0-owner-policy-v4-packet-v2",
                "final_path": r"\\?\Volume{00000000-0000-0000-0000-000000000001}\llm-novel-dc\p0-owner-policy-v4-packet-v2",
                "volume_serial_decimal": "1", "file_id_128_hex": "03" * 16,
                "notify_filter": store._V4_WATCH_FILTER_PIN,
                "completion_status": "CANCELED_PENDING_AT_END", "clean": True,
            },
        ]
        self.assertTrue(store._watch_rows_strict(rows))
        self.assertFalse(store._watch_rows_strict([rows[0], rows[0], rows[0]]))
        wrong = [dict(row) for row in rows]
        wrong[2]["notify_filter"] = True
        self.assertFalse(store._watch_rows_strict(wrong))
        attacker = [dict(row) for row in rows]
        attacker_root = r"C:\attacker\llm-novel-dc"
        attacker[0]["requested_path"] = attacker_root
        attacker[1]["requested_path"] = attacker_root + r"\p0-owner-policy-v1"
        attacker[2]["requested_path"] = attacker_root + r"\p0-owner-policy-v4-packet-v2"
        self.assertFalse(store._watch_rows_strict(attacker))

    def test_success_handle_counts_require_exact_int_types(self) -> None:
        source = inspect.getsource(store._validate_receipt)
        self.assertIn('type(receipt["role_handle_count"]) is not int', source)
        self.assertIn('type(receipt["file_handle_count"]) is not int', source)

    def test_resealed_success_truth_with_empty_evidence_fails(self) -> None:
        forged = store._failure_receipt("FIXED_STORE")
        forged["failure_stage"] = "EXTERNAL_STATE"
        forged["blocker_codes"] = list(store._BLOCKERS[9:])
        for field in store._TRUE_FIELDS:
            forged[field] = True
        material = dict(forged)
        material.pop("receipt_sha256")
        forged["receipt_sha256"] = store.canonical_sha256(material)
        with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
            store._validate_receipt(forged)

    def test_resealed_unknown_failure_stage_or_partial_evidence_fails(self) -> None:
        for field, value in (
            ("failure_stage", "ATTACKER_STAGE"),
            ("ancestor_handle_count", 1),
            ("role_identity_projection_sha256", "aa" * 32),
        ):
            with self.subTest(field=field):
                forged = store._failure_receipt("FIXED_STORE")
                forged[field] = value
                material = dict(forged)
                material.pop("receipt_sha256")
                forged["receipt_sha256"] = store.canonical_sha256(material)
                with self.assertRaises(store.P0WindowsOwnerPolicyV4TransitionFixedStoreError):
                    store._validate_receipt(forged)

    def test_held_interval_source_orders_handles_before_reads_and_barrier_last(self) -> None:
        source = inspect.getsource(store._observe_held)
        self.assertLess(source.index("for role in ROLE_SEQUENCE"), source.index("for role in FILE_ROLE_SEQUENCE"))
        self.assertLess(source.index("common_inventory ="), source.index("for role in FILE_ROLE_SEQUENCE"))
        self.assertLess(source.index("compare_exact_security_projection"), source.index("barriers ="))
        self.assertLess(source.index("reopen mismatch"), source.index("barriers ="))


if __name__ == "__main__":
    unittest.main()
