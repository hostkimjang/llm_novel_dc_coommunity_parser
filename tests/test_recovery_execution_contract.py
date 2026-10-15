from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.recovery_execution_fixtures import (
    build_bound_fixture, json_bytes, make_recovery_fixture, reseal_plan,
)
from src.llm_batch.ledger.recovery_activation import _create_event
from src.llm_batch.measurement.recovery_execution_contract import (
    BoundRecoveryPlan, RecoveryExecutionContractError, bind_recovery_execution_plan,
    build_recovery_execution_plan, canonical_sha256, execution_journal_arguments,
    read_bound_input_bindings, read_bound_input_posts, read_recovery_activation_snapshot,
    validate_fixture, validate_plan,
)


class RecoveryExecutionContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.bundle = build_bound_fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _kwargs(self):
        return deepcopy(self.bundle["build_kwargs"])

    def _bytes(self, kwargs, role, raw):
        kwargs["artifact_bytes"][role] = raw
        kwargs["artifact_refs"][role].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))

    def _json(self, kwargs, role, value, *, newline=False):
        self._bytes(kwargs, role, json_bytes(value) + (b"\n" if newline else b""))

    def test_valid_typed_hold_plan_retains_all_authority_and_denominator_limits(self):
        plan = self.bundle["plan"]
        self.assertEqual(self.bundle["router"]["state"], "REVIEW_REQUIRED")
        self.assertIn("OCR_TITLE_UNRESOLVED", self.bundle["router"]["trigger_codes"])
        self.assertEqual(self.bundle["recovery_plan"]["plan"]["state"], "HOLD")
        self.assertEqual(validate_plan(plan), plan)
        self.assertEqual(plan["execution_mode"], "LOCAL_SIMULATION_ONLY")
        self.assertEqual(plan["data_kind"], "SYNTHETIC_CONTRACT_ONLY")
        for key in ("public_apply", "publication_authority", "central_db_write"):
            self.assertIs(plan[key], False)
        self.assertEqual(plan["actual_external_call_budget"], 0)
        self.assertEqual(plan["base"]["input_count"], 2)
        self.assertEqual(plan["base"]["input_order_sha256"], canonical_sha256([101, 102]))
        self.assertEqual(plan["activation"]["mode"], "AUDIT_ONLY")
        self.assertEqual(plan["activation"]["capability_scope"], "proposal_authorization_only")
        self.assertFalse(self.bundle["bound"].output_dir.exists())

    def test_authentic_no_review_receipt_remains_ineligible(self):
        # Rebuild all original receipts and HMAC; do not just corrupt a checksum.
        with self.assertRaisesRegex(RecoveryExecutionContractError, "router=NO_REVIEW, plan=HOLD"):
            make_recovery_fixture(self.root / "no-review", ocr_review_required=False,
                                  router_rule_version="strict_evidence_v1")

    def test_original_public_fields_and_files_remain_byte_exact(self):
        refs = self.bundle["artifact_refs"]
        before = {role: Path(ref["path"]).read_bytes() for role, ref in refs.items()}
        bound = bind_recovery_execution_plan(self.bundle["plan"], hmac_key=self.bundle["hmac_key"])
        records = bound.verify_protected_sources()
        self.assertEqual({record["role"] for record in records}, set(refs))
        self.assertEqual({role: Path(ref["path"]).read_bytes() for role, ref in refs.items()}, before)
        identity = self.bundle["result"]["analysis_result"]["identity"]
        self.assertIs(identity["promotion_decision"]["publish_allowed"], False)
        self.assertFalse(identity.get("official_title"))
        self.assertFalse(identity.get("heretic_url"))
        self.assertEqual(list((self.root / "source").glob("*.lock")), [])

    def test_bound_is_factory_only_frozen_and_returns_deep_copies(self):
        with self.assertRaises(RecoveryExecutionContractError):
            BoundRecoveryPlan()
        bound = self.bundle["bound"]
        with self.assertRaises(FrozenInstanceError):
            bound._serialized = b"{}"
        view = bound.plan
        view["policy"]["max_simulated_dispatches"] = 900
        fixture = bound.fixture
        fixture["actions"].clear()
        self.assertEqual(bound.plan, self.bundle["plan"])
        self.assertEqual(bound.fixture, self.bundle["fixture"])
        self.assertEqual(bound.input_rows(), [{"input_index": 1, "post_id": 101},
                                              {"input_index": 2, "post_id": 102}])
        rows = read_bound_input_posts(bound)
        rows.clear()
        self.assertEqual(len(read_bound_input_posts(bound)), 2)

    def test_journal_projection_includes_file_binding_not_just_semantic_hash(self):
        plan = self.bundle["plan"]
        arguments = execution_journal_arguments(plan)
        self.assertEqual(arguments["binding"]["config_sha256"], plan["binding_sha256"])
        self.assertEqual(arguments["binding"]["source_sha256"],
                         canonical_sha256({"source_binding": plan["source_binding"], "artifacts": plan["artifacts"]}))
        self.assertEqual(arguments["actions"], [{"action_id": "action-1",
            "action_kind": "REVALIDATE_SAVED_EVIDENCE", "query_sha256": plan["source_binding"]["query_sha256"]}])

    def test_pure_builder_never_opens_files_or_constructs_registry(self):
        with patch("builtins.open", side_effect=AssertionError("file I/O forbidden")), \
             patch("src.llm_batch.ledger.recovery_activation.RecoveryActivationRegistry",
                   side_effect=AssertionError("registry mutation forbidden")):
            rebuilt = build_recovery_execution_plan(**self._kwargs())
        self.assertEqual(rebuilt, self.bundle["plan"])

    def test_path_independent_semantic_hash_and_path_sensitive_binding_hash(self):
        kwargs = self._kwargs()
        kwargs["output_dir"] = str(self.root / "different-output")
        for role, ref in kwargs["artifact_refs"].items():
            ref["path"] = str(self.root / "different-source" / (role + ".json"))
        plan = build_recovery_execution_plan(**kwargs)
        self.assertEqual(plan["plan_sha256"], self.bundle["plan"]["plan_sha256"])
        self.assertNotEqual(plan["binding_sha256"], self.bundle["plan"]["binding_sha256"])
        with self.assertRaises((RecoveryExecutionContractError, FileNotFoundError)):
            bind_recovery_execution_plan(plan, hmac_key=self.bundle["hmac_key"])

    def test_strict_json_rejects_nonfinite_foreign_keys_and_python_objects(self):
        for value in (float("nan"), float("inf"), {1: "bad"}, {"bad": (1, 2)}, {"bad": object()}):
            with self.subTest(value=type(value).__name__), self.assertRaises(RecoveryExecutionContractError):
                canonical_sha256(value)
        self.assertEqual(canonical_sha256({"b": 2, "a": 1}), canonical_sha256({"a": 1, "b": 2}))

    def test_resealed_authority_and_strict_boolean_integer_tampering_rejected(self):
        changes = [("public_apply", True), ("publication_authority", 0),
                   ("central_db_write", None), ("actual_external_call_budget", False),
                   ("execution_mode", "ACTUAL"), ("data_kind", "ACTUAL_DATA")]
        for key, value in changes:
            plan = deepcopy(self.bundle["plan"])
            plan[key] = value
            with self.subTest(key=key), self.assertRaises(RecoveryExecutionContractError):
                validate_plan(reseal_plan(plan))
        for value in (True, 1.0, 0):
            plan = deepcopy(self.bundle["plan"])
            plan["base"]["input_index"] = value
            with self.subTest(index=value), self.assertRaises(RecoveryExecutionContractError):
                validate_plan(reseal_plan(plan))

    def test_forged_base_coordinate_passes_self_hash_but_fails_source_binding(self):
        for field, value in (("post_id", "101"), ("base_attempt_run_id", "other-attempt"),
                             ("input_count", 3), ("publication_scope_id", "c" * 64),
                             ("input_order_sha256", "d" * 64)):
            plan = deepcopy(self.bundle["plan"])
            plan["base"][field] = value
            plan = reseal_plan(plan)
            self.assertEqual(validate_plan(plan), plan)
            with self.subTest(field=field), self.assertRaises(RecoveryExecutionContractError):
                bind_recovery_execution_plan(plan, hmac_key=self.bundle["hmac_key"])

    def test_original_manifest_scope_attempt_input_and_data_kind_are_mandatory(self):
        for key, value in (("publication_scope_id", "a" * 64), ("run_id", "other"),
                           ("input_sha256", "f" * 64), ("data_kind", "ACTUAL_DATA")):
            kwargs = self._kwargs()
            manifest = deepcopy(self.bundle["manifest"])
            manifest[key] = value
            self._json(kwargs, "manifest", manifest)
            with self.subTest(key=key), self.assertRaises(RecoveryExecutionContractError):
                build_recovery_execution_plan(**kwargs)

    def test_result_and_authoritative_wal_cannot_be_substituted_by_stable_hash_only(self):
        kwargs = self._kwargs()
        result = deepcopy(self.bundle["result"])
        result["run_meta"]["run_id"] = "different-current-run"
        self._json(kwargs, "result", result)
        with self.assertRaisesRegex(RecoveryExecutionContractError, "result/WAL"):
            build_recovery_execution_plan(**kwargs)

    def test_publication_post_type_cannot_use_legacy_string_normalization(self):
        kwargs = self._kwargs()
        event = json.loads(kwargs["artifact_bytes"]["publication_wal"])
        event["result"]["post_id"] = "101"
        self._json(kwargs, "publication_wal", event, newline=True)
        with self.assertRaises(RecoveryExecutionContractError):
            build_recovery_execution_plan(**kwargs)

    def test_resigned_activation_for_other_base_rejected(self):
        kwargs = self._kwargs()
        original = self.bundle["event"]
        other = replace(self.bundle["receipt"], decision_id="b" * 64)
        forged = _create_event(receipt=other, proposal=original.proposal, raw_capability="test-only-other",
            hmac_key=self.bundle["hmac_key"], sequence=1, prev_event_sha256="GENESIS")
        raw = json_bytes(forged.to_dict()) + b"\n"
        # Valid audit HMAC and event self hash do not override authoritative base.
        self.assertEqual(len(read_recovery_activation_snapshot(raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(), hmac_key=self.bundle["hmac_key"])), 1)
        self._bytes(kwargs, "activation_journal", raw)
        kwargs["activation_event_sha256"] = forged.event_sha256
        with self.assertRaisesRegex(RecoveryExecutionContractError, "activation base"):
            build_recovery_execution_plan(**kwargs)

    def test_resealed_semantic_receipt_cannot_override_original_evidence(self):
        kwargs = self._kwargs()
        router = deepcopy(self.bundle["router"])
        router["attempt_run_id"] = "different-attempt"
        router["receipt_sha256"] = canonical_sha256({key: value for key, value in router.items() if key != "receipt_sha256"})
        self._json(kwargs, "router", router)
        with self.assertRaisesRegex(RecoveryExecutionContractError, "semantic receipt"):
            build_recovery_execution_plan(**kwargs)

    def test_canonical_source_item_sha_cannot_be_replaced_with_raw_payload_sha(self):
        kwargs = self._kwargs()
        digest = kwargs["artifact_refs"]["source_payload"]["sha256"]
        self.assertNotEqual(digest, kwargs["source_binding"]["source_item_sha256"])
        kwargs["source_binding"]["source_item_sha256"] = digest
        kwargs["actions"][0]["source_item_sha256"] = digest
        with self.assertRaisesRegex(RecoveryExecutionContractError, "source item canonical"):
            build_recovery_execution_plan(**kwargs)

    def test_source_payload_parent_and_locator_are_independently_bound(self):
        for key, value in (("input_raw_sha256", "e" * 64), ("input_index", 2),
                           ("post_id", "101"), ("source_locator", "OTHER_IMAGE")):
            kwargs = self._kwargs()
            payload = deepcopy(self.bundle["source_payload"])
            payload[key] = value
            self._json(kwargs, "source_payload", payload)
            with self.subTest(key=key), self.assertRaises(RecoveryExecutionContractError):
                build_recovery_execution_plan(**kwargs)

    def test_source_field_utf8_span_cannot_be_shifted_or_synthesized(self):
        for change in ({"span_start": 1, "span_end": self.bundle["source_binding"]["span_end"] + 1},
                       {"field_pointer": "/missing"}, {"span_unit": "CHARACTER"}):
            kwargs = self._kwargs()
            kwargs["source_binding"].update(change)
            with self.subTest(change=change), self.assertRaises(RecoveryExecutionContractError):
                build_recovery_execution_plan(**kwargs)
        kwargs = self._kwargs()
        kwargs["actions"][0]["query"] = "추론한 새 제목"
        kwargs["actions"][0]["query_sha256"] = hashlib.sha256("추론한 새 제목".encode()).hexdigest()
        with self.assertRaises(RecoveryExecutionContractError):
            build_recovery_execution_plan(**kwargs)

    def test_missing_historical_source_sha_is_not_filled_from_current_file(self):
        kwargs = self._kwargs()
        event = self.bundle["event"]
        missing = _create_event(receipt=self.bundle["receipt"],
            proposal=replace(event.proposal, source_payload_sha256=None), raw_capability="missing-test",
            hmac_key=self.bundle["hmac_key"], sequence=1, prev_event_sha256="GENESIS")
        self._json(kwargs, "activation_journal", missing.to_dict(), newline=True)
        kwargs["activation_event_sha256"] = missing.event_sha256
        with self.assertRaises(RecoveryExecutionContractError):
            build_recovery_execution_plan(**kwargs)

    def test_original_candidate_role_is_preserved_without_primary_promotion(self):
        bundle = make_recovery_fixture(self.root / "candidate", relation_role="candidate")
        self.assertEqual(bundle["plan"]["source_binding"]["relation_role"], "candidate")
        kwargs = deepcopy(bundle["build_kwargs"])
        kwargs["source_binding"]["relation_role"] = "primary"
        kwargs["actions"][0]["relation_role"] = "primary"
        with self.assertRaisesRegex(RecoveryExecutionContractError, "relation_role"):
            build_recovery_execution_plan(**kwargs)

    def test_query_purpose_requires_actual_original_query_and_semantic_permission(self):
        bundle = make_recovery_fixture(self.root / "search", action_kinds=["SIMULATED_TARGETED_SEARCH"])
        self.assertGreaterEqual(bundle["plan"]["review"]["max_queries"], 1)
        self.assertLessEqual(bundle["plan"]["review"]["max_queries"], 2)
        kwargs = deepcopy(bundle["build_kwargs"])
        kwargs["actions"][0]["purpose"] = "INVENTED_PURPOSE"
        with self.assertRaisesRegex(RecoveryExecutionContractError, "purpose"):
            build_recovery_execution_plan(**kwargs)
        kwargs = deepcopy(bundle["build_kwargs"])
        kwargs["actions"][0].pop("query")
        with self.assertRaises(RecoveryExecutionContractError):
            build_recovery_execution_plan(**kwargs)

    def test_duplicate_actions_and_unregistered_backend_kind_are_rejected(self):
        for change in ("duplicate", "backend"):
            kwargs = self._kwargs()
            if change == "duplicate":
                kwargs["actions"].append(deepcopy(kwargs["actions"][0]))
            else:
                kwargs["actions"][0]["kind"] = "HTTP_MODEL_BACKEND"
            with self.subTest(change=change), self.assertRaises(RecoveryExecutionContractError):
                build_recovery_execution_plan(**kwargs)

    def test_policy_limits_do_not_accept_bool_negative_or_external_calls(self):
        for key, value in (("actual_external_call_budget", 1), ("max_simulated_dispatches", True),
                           ("max_retries_per_action", -1), ("max_actions", 17),
                           ("per_action_timeout_ms", 1001), ("max_output_bytes", 65537)):
            kwargs = self._kwargs()
            kwargs["policy"][key] = value
            with self.subTest(key=key), self.assertRaises(RecoveryExecutionContractError):
                build_recovery_execution_plan(**kwargs)
        kwargs = self._kwargs()
        kwargs["policy"]["max_simulated_dispatches"] = 0
        self.assertEqual(build_recovery_execution_plan(**kwargs)["policy"]["max_simulated_dispatches"], 0)

    def test_fixture_rejects_extra_backend_duplicate_action_bool_delay_and_nan(self):
        for field, value in (("delay_ms", True), ("retry_delay_ms", -1), ("outcome", "MODEL_SUCCESS"),
                             ("response", {"value": float("nan")})):
            fixture = deepcopy(self.bundle["fixture"])
            fixture["actions"][0]["responses"][0][field] = value
            with self.subTest(field=field), self.assertRaises(RecoveryExecutionContractError):
                validate_fixture(fixture, actions=self.bundle["plan"]["actions"])
        fixture = deepcopy(self.bundle["fixture"])
        fixture["backend"] = "external"
        with self.assertRaises(RecoveryExecutionContractError):
            validate_fixture(fixture, actions=self.bundle["plan"]["actions"])

    def test_activation_hmac_chain_tail_duplicate_keys_and_reorder_rejected_without_repair(self):
        raw = self.bundle["artifact_bytes"]["activation_journal"]
        key = self.bundle["hmac_key"]
        for value, hmac_key in ((raw[:-1], key), (raw + raw, key), (raw, b"wrong-hmac-key-material" * 2),
                                 (b'{"x":1,"x":2}\n', key), (b"\n", key)):
            with self.subTest(length=len(value)), self.assertRaises(RecoveryExecutionContractError):
                read_recovery_activation_snapshot(value, expected_sha256=hashlib.sha256(value).hexdigest(),
                                                    hmac_key=hmac_key)
        self.assertEqual(Path(self.bundle["artifact_refs"]["activation_journal"]["path"]).read_bytes(), raw)

    def test_input_duplicate_or_orphan_records_are_not_silently_removed(self):
        for rows in ([*self.bundle["input_posts"], self.bundle["input_posts"][0]],
                     [*self.bundle["input_posts"], {"post_id": 999, "comment_id": 1, "content": "orphan"}]):
            kwargs = self._kwargs()
            kwargs["input_format"] = "JSONL_POST_COMMENT_V1"
            self._bytes(kwargs, "input", b"".join(json_bytes(row) + b"\n" for row in rows))
            with self.assertRaisesRegex(RecoveryExecutionContractError, "duplicate|orphan"):
                build_recovery_execution_plan(**kwargs)

    def test_jsonl_explicit_input_preserves_full_post_order(self):
        bundle = make_recovery_fixture(self.root / "jsonl", input_format="JSONL_POST_COMMENT_V1",
                                       post_ids=[201, 205, 209])
        self.assertEqual(bundle["bound"].input_rows(), [{"input_index": 1, "post_id": 201},
            {"input_index": 2, "post_id": 205}, {"input_index": 3, "post_id": 209}])

    def test_jsonl_comments_bind_raw_records_parent_order_and_canonical_projection(self):
        comments = [{"post_id": 101, "comment_id": 7, "content": "첫 합성 경쟁 작품 언급"},
                    {"post_id": 102, "comment_id": 9, "content": "다른 부모 댓글"},
                    {"post_id": 101, "comment_id": 8, "text": "둘째 합성 댓글"}]
        embedded = [{"post_id": 101, "comment_id": "embedded-a", "text": "세 번째 내장 댓글"},
                    "  네 번째 내장 댓글  "]
        bundle = make_recovery_fixture(self.root / "comments", input_format="JSONL_POST_COMMENT_V1",
                                       jsonl_comment_rows=comments, embedded_comments=embedded)
        self.assertEqual(bundle["result"]["comments"], [comments[0]["content"], comments[2]["text"],
                                                       embedded[0]["text"], embedded[1].strip()])
        bindings = read_bound_input_bindings(bundle["bound"])
        self.assertEqual([record["payload"] for record in bindings["records"][-3:]], comments)
        selected = bindings["post_bindings"][0]
        self.assertEqual([record["record_index"] for record in selected["separate_comment_records"]], [3, 5])
        self.assertEqual(selected["result_comments"], bundle["result"]["comments"])
        self.assertEqual(bindings["post_bindings"][1]["result_comments"], [comments[1]["content"]])
        for record, raw in zip(bindings["records"], bundle["artifact_bytes"]["input"].splitlines()):
            self.assertEqual(record["raw_line_sha256"], hashlib.sha256(raw).hexdigest())
        # Accessors retain originals and do not expose mutable internal state.
        self.assertEqual(read_bound_input_posts(bundle["bound"])[0]["comments"], embedded)
        bindings["records"].clear()
        self.assertEqual(len(bundle["bound"].input_bindings()["records"]), 5)

    def test_resealed_jsonl_missing_changed_or_reordered_comments_fail_result_binding(self):
        comments = [{"post_id": 101, "comment_id": 7, "content": "첫 원문"},
                    {"post_id": 101, "comment_id": 8, "content": "둘째 원문"}]
        for name, rows, result_comments in (
            ("missing", comments, []),
            ("changed", [{**comments[0], "content": "바뀐 원문"}, comments[1]], ["첫 원문", "둘째 원문"]),
            ("reordered", list(reversed(comments)), ["첫 원문", "둘째 원문"]),
            ("other-parent", [{**comments[0], "post_id": 102}, comments[1]], ["첫 원문", "둘째 원문"]),
        ):
            # All raw refs, scope, manifest, authoritative WAL, receipts, and HMAC
            # are freshly built. Failure must be semantic binding, not old hashes.
            with self.subTest(name=name), self.assertRaisesRegex(RecoveryExecutionContractError,
                                                                 "comments projection"):
                make_recovery_fixture(self.root / name, input_format="JSONL_POST_COMMENT_V1",
                    jsonl_comment_rows=rows, result_comments_override=result_comments)

    def test_jsonl_comments_reject_duplicate_type_parent_and_embedded_id_conflicts(self):
        first = {"post_id": 101, "comment_id": 7, "content": "댓글"}
        cases = (
            ("duplicate", [first, deepcopy(first)], []),
            ("typed-parent", [{**first, "post_id": "101"}], []),
            ("normalized-id", [first, {**first, "comment_id": "7"}], []),
            ("embedded-id", [first], [{"post_id": 101, "comment_id": 7, "content": "중복 내장"}]),
            ("embedded-parent", [], [{"post_id": 102, "comment_id": 8, "content": "다른 부모"}]),
        )
        for name, comments, embedded in cases:
            with self.subTest(name=name), self.assertRaises(RecoveryExecutionContractError):
                make_recovery_fixture(self.root / name, input_format="JSONL_POST_COMMENT_V1",
                                       jsonl_comment_rows=comments, embedded_comments=embedded)

    def test_jsonl_explicit_empty_ids_never_become_unique_ordinal_ids(self):
        for index, identifier in enumerate((None, "", "   ", 0)):
            for same_body in (True, False):
                embedded = [{"comment_id": identifier, "content": "합성 댓글"},
                            {"comment_id": identifier, "content": "합성 댓글" if same_body else "다른 댓글"}]
                with self.subTest(identifier=identifier, same_body=same_body), self.assertRaisesRegex(
                        RecoveryExecutionContractError, "explicit empty comment_id"):
                    make_recovery_fixture(self.root / f"empty-id-{index}-{same_body}",
                        input_format="JSONL_POST_COMMENT_V1", embedded_comments=embedded)

    def test_jsonl_absent_ids_keep_loader_ordinal_identity_and_original_body(self):
        embedded = [{"content": "같은 합성 댓글"}, {"content": "같은 합성 댓글"}]
        bundle = make_recovery_fixture(self.root / "absent-ids", input_format="JSONL_POST_COMMENT_V1",
                                       embedded_comments=embedded)
        selected = read_bound_input_bindings(bundle["bound"])["post_bindings"][0]
        self.assertEqual(selected["result_comments"], ["같은 합성 댓글", "같은 합성 댓글"])
        self.assertEqual(read_bound_input_posts(bundle["bound"])[0]["comments"], embedded)

    def test_jsonl_metadata_can_fill_explicit_empty_ids_before_projection(self):
        embedded = [{"comment_id": None, "content": "같은 합성 댓글"},
                    {"comment_id": "", "content": "같은 합성 댓글"}]
        metadata = [{"comment_id": "meta-a"}, {"comment_id": "meta-b"}]
        bundle = make_recovery_fixture(self.root / "metadata-ids", input_format="JSONL_POST_COMMENT_V1",
                                       embedded_comments=embedded, comment_metadata=metadata)
        self.assertEqual(bundle["result"]["comments"], ["같은 합성 댓글", "같은 합성 댓글"])
        original = read_bound_input_posts(bundle["bound"])[0]
        self.assertEqual(original["comments"], embedded)
        self.assertEqual(original["comment_metadata"], metadata)
        with self.assertRaisesRegex(RecoveryExecutionContractError, "duplicate separate/embedded"):
            make_recovery_fixture(self.root / "metadata-duplicate", input_format="JSONL_POST_COMMENT_V1",
                embedded_comments=embedded, comment_metadata=[{"comment_id": "same"}, {"comment_id": "same"}])

    def test_unknown_and_undefined_roles_are_ineligible_without_role_rewriting(self):
        for index, role in enumerate(("UNKNOWN", "unknown", "unrecognized_role", "primary_candidate")):
            with self.subTest(role=role), self.assertRaisesRegex(RecoveryExecutionContractError,
                                                                "SOURCE_ROLE_NOT_ELIGIBLE"):
                make_recovery_fixture(self.root / f"role-{index}", relation_role=role)
            plan = deepcopy(self.bundle["plan"])
            plan["source_binding"]["relation_role"] = role
            for action in plan["actions"]:
                action["relation_role"] = role
            with self.assertRaisesRegex(RecoveryExecutionContractError, "SOURCE_ROLE_NOT_ELIGIBLE"):
                validate_plan(reseal_plan(plan))

    def test_known_nonprimary_and_ambiguous_roles_remain_exactly_as_proposed(self):
        for role in ("previous", "mentioned", "comparison", "candidate", "ambiguous"):
            with self.subTest(role=role):
                bundle = make_recovery_fixture(self.root / role, relation_role=role)
                self.assertEqual(bundle["event"].proposal.relation_role, role)
                self.assertEqual(bundle["plan"]["source_binding"]["relation_role"], role)
                self.assertTrue(all(action["relation_role"] == role for action in bundle["plan"]["actions"]))

    def test_bind_detects_raw_drift_even_when_mutator_preserves_file_size(self):
        path = Path(self.bundle["artifact_refs"]["fixture"]["path"])
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"SUCCESS", b"FAILURE"))
        with self.assertRaisesRegex(RecoveryExecutionContractError, "SHA drift"):
            self.bundle["bound"].verify_protected_sources()

    def test_output_namespace_rejects_overlap_and_traversal(self):
        bound = self.bundle["bound"]
        for path in (self.root / "elsewhere.json", bound.output_dir,
                     bound.output_dir / ".." / "source" / "result.json"):
            with self.subTest(path=str(path)), self.assertRaises(RecoveryExecutionContractError):
                bound.assert_output_path(path)
        kwargs = self._kwargs()
        kwargs["output_dir"] = str(self.root)
        with self.assertRaisesRegex(RecoveryExecutionContractError, "overlaps"):
            build_recovery_execution_plan(**kwargs)

    def test_hardlink_source_and_output_aliases_are_rejected(self):
        source = Path(self.bundle["artifact_refs"]["result"]["path"])
        alias = self.root / "hardlink.json"
        try:
            os.link(source, alias)
        except (OSError, NotImplementedError):
            self.skipTest("filesystem does not permit hardlinks")
        with self.assertRaisesRegex(RecoveryExecutionContractError, "single regular link"):
            self.bundle["bound"].verify_protected_sources()
        self.bundle["bound"].output_dir.mkdir()
        target = self.bundle["bound"].output_dir / "alias.json"
        os.link(source, target)
        with self.assertRaises(RecoveryExecutionContractError):
            self.bundle["bound"].assert_output_path(target)

    def test_symlink_output_parent_is_rejected_when_supported(self):
        output = self.bundle["bound"].output_dir
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        try:
            output.symlink_to(elsewhere, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("filesystem does not permit symlinks")
        with self.assertRaisesRegex(RecoveryExecutionContractError, "symlink/reparse"):
            self.bundle["bound"].assert_output_path(output / "result.json")

    def test_duplicate_source_path_and_oversized_artifact_ref_are_rejected(self):
        kwargs = self._kwargs()
        kwargs["artifact_refs"]["router"]["path"] = kwargs["artifact_refs"]["result"]["path"]
        with self.assertRaisesRegex(RecoveryExecutionContractError, "duplicate artifact"):
            build_recovery_execution_plan(**kwargs)
        kwargs = self._kwargs()
        kwargs["artifact_refs"]["fixture"]["bytes"] = 16 * 1024 * 1024 + 1
        with self.assertRaisesRegex(RecoveryExecutionContractError, "bytes"):
            build_recovery_execution_plan(**kwargs)

    def test_unc_and_alternate_stream_paths_are_rejected_before_reads(self):
        for path in (r"\\server\share\source.json", str(self.root / "result.json") + ":stream"):
            kwargs = self._kwargs()
            kwargs["artifact_refs"]["result"]["path"] = path
            with self.subTest(path=path), self.assertRaises(RecoveryExecutionContractError):
                build_recovery_execution_plan(**kwargs)


if __name__ == "__main__":
    unittest.main()
