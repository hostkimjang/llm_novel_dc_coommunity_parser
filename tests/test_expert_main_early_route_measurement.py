from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import expert_main
from src.llm_batch.ledger.decision_call_events import DecisionCallLedgerRegistry
from src.llm_batch.ledger.decision_call_readback import read_decision_call_ledger
from src.llm_batch.ledger.decision_tracing_llm import DecisionTracingLLMClient
from src.llm_batch.measurement.early_route_measurement import (
    ACCURACY_NOT_ESTIMABLE,
    LANE_CHEAP_NIL,
    LANE_FULL,
    EarlyRouteDecision,
    canonical_hash,
)
from tests.test_publication_decision_commit import _valid_result


PublicationCommitRegistry = expert_main.PublicationCommitRegistry
build_publication_scope_descriptor = expert_main.build_publication_scope_descriptor
commit_publication_result = expert_main.commit_publication_result
compute_publication_decision_commit = expert_main.compute_publication_decision_commit


def _required_env(*, arm: str = "AFTER", early: bool = True) -> dict[str, str]:
    return {
        "PIPELINE_DECISION_CALL_LEDGER_MODE": "REQUIRED",
        "PIPELINE_MEASUREMENT_RUN_SPEC_SHA256": "a" * 64,
        "PIPELINE_MEASUREMENT_PAIR_ID": "pair-early-route",
        "PIPELINE_MEASUREMENT_ARM": arm,
        "PIPELINE_MEASUREMENT_EXECUTION_MODE": "FRESH_EXECUTION_REQUIRED",
        "PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE": (
            "SOURCE_ONLY_V1" if early else "OFF"
        ),
        "PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE": "FROZEN_OFF",
        "PIPELINE_SLANG_DB": "0",
    }


def _post(**changes):
    payload = {
        "post_id": 101,
        "title": "ㅋㅋㅋ!!!",
        "content_blocks": [],
        "comments": [],
        "search_results": None,
        "source_search_results": None,
        "precomputed_search_results": None,
        "search_evidence_catalog": None,
        "native_web_seed": None,
        "source_evidence": None,
        "judge_seed": None,
        "projection_followup": None,
    }
    payload.update(changes)
    return SimpleNamespace(**payload)


class ExpertMainEarlyRouteMeasurementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scope = build_publication_scope_descriptor(
            input_file_sha256="1" * 64,
            post_ids=[101],
            config_hash="early-route-test",
            release_fingerprint="2" * 64,
        )
        self.config = expert_main._decision_call_measurement_config(_required_env())

    def test_only_required_fresh_after_explicit_mode_can_skip(self) -> None:
        self.assertTrue(self.config["early_route_enabled"])
        self.assertEqual(self.config["mutable_context_mode"], "FROZEN_OFF")
        self.assertTrue(self.config["mutable_context_frozen"])
        self.assertEqual(self.config["slang_access_mode"], "OFF")
        self.assertFalse(self.config["central_slang_db_write_allowed"])

        before = expert_main._decision_call_measurement_config(
            _required_env(arm="BEFORE")
        )
        self.assertFalse(before["early_route_enabled"])
        self.assertEqual(
            before["mutable_context_binding_sha256"],
            self.config["mutable_context_binding_sha256"],
        )

        shadow_env = _required_env()
        shadow_env["PIPELINE_DECISION_CALL_LEDGER_MODE"] = "SHADOW"
        shadow = expert_main._decision_call_measurement_config(shadow_env)
        self.assertFalse(shadow["early_route_enabled"])

        off = expert_main._decision_call_measurement_config({})
        self.assertFalse(off["early_route_enabled"])

    def test_decision_ledger_v2_shadow_is_explicit_and_legacy_bound(self) -> None:
        off_measurement = expert_main._decision_call_measurement_config({})
        off = expert_main._decision_ledger_v2_shadow_config(off_measurement, {})
        self.assertFalse(off["enabled"])
        self.assertTrue(off["legacy_authoritative"])
        self.assertFalse(off["public_result_interference"])

        with self.assertRaisesRegex(ValueError, "requires the legacy"):
            expert_main._decision_ledger_v2_shadow_config(
                off_measurement,
                {"PIPELINE_DECISION_LEDGER_V2_SHADOW_MODE": "DUAL_WRITE_SHADOW"},
            )

        enabled = expert_main._decision_ledger_v2_shadow_config(
            self.config,
            {"PIPELINE_DECISION_LEDGER_V2_SHADOW_MODE": "DUAL_WRITE_SHADOW"},
        )
        self.assertTrue(enabled["enabled"])
        self.assertFalse(enabled["production_auto_enable_allowed"])

        with self.assertRaisesRegex(ValueError, "OFF or DUAL_WRITE_SHADOW"):
            expert_main._decision_ledger_v2_shadow_config(
                self.config,
                {"PIPELINE_DECISION_LEDGER_V2_SHADOW_MODE": "AUTO"},
            )

    def test_required_measurement_requires_frozen_context_and_nonmutable_slang(self) -> None:
        missing = _required_env()
        missing.pop("PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE")
        with self.assertRaisesRegex(ValueError, "FROZEN_OFF"):
            expert_main._decision_call_measurement_config(missing)

        mutable = _required_env()
        mutable["PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE"] = "NORMAL"
        with self.assertRaisesRegex(ValueError, "FROZEN_OFF"):
            expert_main._decision_call_measurement_config(mutable)

        slang_write = _required_env()
        slang_write["PIPELINE_SLANG_DB"] = "1"
        with self.assertRaisesRegex(ValueError, "OFF or READ_ONLY"):
            expert_main._decision_call_measurement_config(slang_write)

        read_only = _required_env()
        read_only["PIPELINE_SLANG_DB"] = "read-only"
        read_only_config = expert_main._decision_call_measurement_config(read_only)
        self.assertEqual(read_only_config["slang_access_mode"], "READ_ONLY")
        self.assertTrue(read_only_config["early_route_enabled"])

    def test_provider_poison_cheap_lane_performs_zero_full_calls(self) -> None:
        reference = _valid_result(post_id=101)
        calls = 0

        def poison():
            nonlocal calls
            calls += 1
            raise AssertionError("provider/MCP/VLM/expert path must not run")

        result, decision, execution, skipped = (
            expert_main._execute_source_only_early_route(
                _post(),
                measurement_config=self.config,
                publication_scope_id=self.scope.publication_scope_id,
                input_index=1,
                authoritative_reference_result=reference,
                process_full=poison,
            )
        )
        self.assertEqual(calls, 0)
        self.assertTrue(skipped)
        self.assertEqual(decision.selected_lane, LANE_CHEAP_NIL)
        self.assertFalse(decision.provider_dispatch_allowed)
        self.assertEqual(
            execution["execution_status"],
            "CHEAP_ZERO_CALL_AUTHORITATIVE_REFERENCE_COPY",
        )
        self.assertIsNot(result, reference)
        self.assertEqual(result, reference)

    def test_wal_reference_is_loaded_only_after_cheap_route_decision(self) -> None:
        authoritative = _valid_result(post_id=101, publish=False)
        events: list[str] = []
        original_decide = expert_main.decide_early_route

        def traced_decide(*args, **kwargs):
            events.append("route_decided")
            return original_decide(*args, **kwargs)

        def load_reference():
            self.assertEqual(events, ["route_decided"])
            events.append("wal_loaded")
            return authoritative

        with patch.object(expert_main, "decide_early_route", side_effect=traced_decide):
            copied, decision, _, skipped = expert_main._execute_source_only_early_route(
                _post(),
                measurement_config=self.config,
                publication_scope_id=self.scope.publication_scope_id,
                input_index=1,
                process_full=lambda: self.fail("full provider path called"),
                authoritative_reference_loader=load_reference,
            )
        self.assertTrue(skipped)
        self.assertEqual(decision.selected_lane, LANE_CHEAP_NIL)
        self.assertEqual(events, ["route_decided", "wal_loaded"])
        self.assertEqual(copied, authoritative)
        self.assertIsNot(copied, authoritative)

        full, full_decision, _, full_skipped = expert_main._execute_source_only_early_route(
            _post(title="작품 제목"),
            measurement_config=self.config,
            publication_scope_id=self.scope.publication_scope_id,
            input_index=1,
            process_full=lambda: {"full": True},
            authoritative_reference_loader=lambda: self.fail(
                "full route must not read the WAL result before execution"
            ),
        )
        self.assertFalse(full_skipped)
        self.assertEqual(full_decision.selected_lane, LANE_FULL)
        self.assertEqual(full, {"full": True})

    def test_before_never_routes_and_meaningful_after_runs_full(self) -> None:
        before = expert_main._decision_call_measurement_config(
            _required_env(arm="BEFORE")
        )
        calls = []
        value, decision, execution, skipped = (
            expert_main._execute_source_only_early_route(
                _post(),
                measurement_config=before,
                publication_scope_id=self.scope.publication_scope_id,
                input_index=1,
                authoritative_reference_result=_valid_result(post_id=101),
                process_full=lambda: calls.append("before-full") or "before-result",
            )
        )
        self.assertEqual(value, "before-result")
        self.assertEqual(calls, ["before-full"])
        self.assertIsNone(decision)
        self.assertIsNone(execution)
        self.assertFalse(skipped)

        value, decision, execution, skipped = (
            expert_main._execute_source_only_early_route(
                _post(title="아생갤 123화 노벨피아"),
                measurement_config=self.config,
                publication_scope_id=self.scope.publication_scope_id,
                input_index=1,
                authoritative_reference_result=_valid_result(post_id=101),
                process_full=lambda: calls.append("after-full") or "after-result",
            )
        )
        self.assertEqual(value, "after-result")
        self.assertEqual(decision.selected_lane, LANE_FULL)
        self.assertFalse(skipped)
        self.assertEqual(execution["execution_status"], "FULL_EXPERT_EXECUTED")
        self.assertEqual(calls[-1], "after-full")

    def test_hidden_evidence_and_content_or_comment_urls_fail_closed(self) -> None:
        attacks = {
            "search_results": {"search_results": [{"title": "hidden"}]},
            "source_search": {"source_search_results": [{"title": "hidden"}]},
            "precomputed": {"precomputed_search_results": [{"title": "hidden"}]},
            "catalog": {"search_evidence_catalog": [{"title": "hidden"}]},
            "native": {"native_web_seed": {"title": "hidden"}},
            "source_evidence": {"source_evidence": {"title": "hidden"}},
            "judge": {"judge_seed": {"expected": "hidden"}},
            "projection": {"projection_followup": {"title": "hidden"}},
            "content_url": {
                "content_blocks": [
                    {"type": "text", "text": "https://novelpia.com/novel/1"}
                ]
            },
            "comment_url": {"comments": ["novelpia.com/novel/1"]},
            "comment_url_field": {
                "comments": [{"content": "ㅋㅋㅋ", "url": "https://example.com/work"}]
            },
            "comment_image_field": {
                "comments": [{"content": "ㅋㅋㅋ", "image_url": "https://x.test/a.png"}]
            },
            "comment_html": {
                "comments": [{"content": "ㅋㅋㅋ", "content_html": "<img src='x'>"}]
            },
            "comment_unknown_field": {
                "comments": [{"content": "ㅋㅋㅋ", "opaque_payload": "hidden"}]
            },
            "image_url_alias": {
                "content_blocks": [
                    {"type": "image", "image_url": "https://x.test/a.png"}
                ]
            },
            "src_alias": {
                "content_blocks": [
                    {"type": "image", "src": "https://x.test/a.png"}
                ]
            },
            "unknown_block": {"content_blocks": [{"type": "mystery", "text": "ㅋㅋ"}]},
            "truncated": {"input_truncated": True},
            "parse_ambiguity": {"parse_errors": ["upstream"]},
        }
        for name, changes in attacks.items():
            with self.subTest(name=name):
                source = expert_main._build_early_route_source_view(
                    _post(**changes),
                    measurement_config=self.config,
                    publication_scope_id=self.scope.publication_scope_id,
                    input_index=1,
                )
                decision = expert_main.decide_early_route(source)
                self.assertEqual(decision.selected_lane, LANE_FULL)
                self.assertTrue(decision.hard_risk_codes)

    def test_post_url_is_not_router_evidence_but_comment_url_is(self) -> None:
        post = _post(url="https://gall.dcinside.com/novel/101")
        source = expert_main._build_early_route_source_view(
            post,
            measurement_config=self.config,
            publication_scope_id=self.scope.publication_scope_id,
            input_index=1,
        )
        self.assertEqual(expert_main.decide_early_route(source).selected_lane, LANE_CHEAP_NIL)
        comment_source = expert_main._build_early_route_source_view(
            _post(comments=["https://example.com/work"]),
            measurement_config=self.config,
            publication_scope_id=self.scope.publication_scope_id,
            input_index=1,
        )
        self.assertEqual(
            expert_main.decide_early_route(comment_source).selected_lane,
            LANE_FULL,
        )

    def test_jsonl_loader_preserves_raw_parse_and_truncation_guards(self) -> None:
        base = {
            "post_id": 101,
            "title": "ㅋㅋㅋ!!!",
            "url": "https://gall.dcinside.com/novel/101",
            "content_blocks": [{"type": "text", "text": "ㅎㅎㅎ"}],
            "comments": [],
        }
        variants = (
            ({}, LANE_CHEAP_NIL),
            (
                {
                    "content_blocks": [
                        {"type": "text", "text": "ㅎㅎㅎ", "unknown": "lost"}
                    ]
                },
                LANE_FULL,
            ),
            ({"input_truncated": True}, LANE_FULL),
            ({"judge_seed": {"candidate": "hidden"}}, LANE_FULL),
            ({"search_results": {"wrong": "shape"}}, LANE_FULL),
        )
        for changes, expected_lane in variants:
            with self.subTest(changes=changes):
                payload = {**base, **changes}
                posts = expert_main.load_jsonl_posts(
                    Path("unused.jsonl"),
                    snapshot_bytes=(
                        json.dumps(payload, ensure_ascii=False) + "\n"
                    ).encode("utf-8"),
                )
                self.assertEqual(len(posts), 1)
                source = expert_main._build_early_route_source_view(
                    posts[0],
                    measurement_config=self.config,
                    publication_scope_id=self.scope.publication_scope_id,
                    input_index=1,
                )
                self.assertEqual(
                    expert_main.decide_early_route(source).selected_lane,
                    expected_lane,
                )

    def test_public_decision_and_wal_are_noninterfering_and_accuracy_stays_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = PublicationCommitRegistry(
                Path(tmp) / "publication.jsonl",
                scope_descriptor=self.scope,
                create_new=True,
            )
            authoritative_result = _valid_result(post_id=101, publish=False)
            authoritative_receipt, created = commit_publication_result(
                authoritative_result,
                registry=registry,
                attempt_run_id="authoritative",
                input_index=1,
                post_id=101,
            )
            self.assertTrue(created)
            initial_count = registry.count

            copied, decision, execution, skipped = (
                expert_main._execute_source_only_early_route(
                    _post(),
                    measurement_config=self.config,
                    publication_scope_id=self.scope.publication_scope_id,
                    input_index=1,
                    authoritative_reference_result=authoritative_result,
                    process_full=lambda: self.fail("full provider path called"),
                )
            )
            self.assertTrue(skipped)
            copied.setdefault("run_meta", {})["early_route_measurement"] = {
                "execution_receipt": execution,
                "comparison_receipt": None,
            }
            current_receipt = compute_publication_decision_commit(
                copied,
                publication_scope_id=self.scope.publication_scope_id,
                attempt_run_id="after",
                input_index=1,
                post_id=101,
            )
            comparison = expert_main._compare_early_route_publication(
                decision,
                current_result=copied,
                current_receipt=current_receipt,
                authoritative_result=authoritative_result,
                authoritative_receipt=authoritative_receipt,
            )
            self.assertEqual(current_receipt.decision_id, authoritative_receipt.decision_id)
            self.assertEqual(
                current_receipt.public_projection_sha256,
                authoritative_receipt.public_projection_sha256,
            )
            self.assertEqual(comparison["accuracy_status"], ACCURACY_NOT_ESTIMABLE)
            self.assertEqual(comparison["gate"], "NO_GO_ACCURACY_NOT_ESTIMABLE")
            self.assertFalse(comparison["baseline_equivalence_is_truth"])
            self.assertFalse(comparison["production_enable_allowed"])
            self.assertEqual(registry.count, initial_count)

    def test_zero_call_row_seals_links_and_independent_readback_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            publication = PublicationCommitRegistry(
                root / "publication.jsonl",
                scope_descriptor=self.scope,
                create_new=True,
            )
            authoritative_result = _valid_result(post_id=101)
            authoritative_receipt, _ = commit_publication_result(
                authoritative_result,
                registry=publication,
                attempt_run_id="authoritative",
                input_index=1,
                post_id=101,
            )
            ledger_path = root / "decision-ledger"
            ledger = DecisionCallLedgerRegistry(
                ledger_path,
                scope_descriptor=self.scope,
                create_new=True,
                enabled=True,
                run_spec_sha256="a" * 64,
                pair_id="pair-early-route",
                arm="AFTER",
                fresh_execution_mode=True,
            )
            client = DecisionTracingLLMClient(decision_call_ledger=ledger)
            row = client.begin_row_attempt("after-run", "row-1", 1, 101)
            _, decision, _, skipped = expert_main._execute_source_only_early_route(
                _post(),
                measurement_config=self.config,
                publication_scope_id=self.scope.publication_scope_id,
                input_index=1,
                authoritative_reference_result=authoritative_result,
                process_full=lambda: self.fail("provider path called"),
            )
            self.assertEqual(decision.selected_lane, LANE_CHEAP_NIL)
            self.assertTrue(skipped)
            client.seal_row_attempt()
            ledger.link_publication(
                row,
                publication_decision_id=authoritative_receipt.decision_id,
            )
            report = read_decision_call_ledger(ledger_path)
            self.assertEqual(report["gate_status"], "GO")
            self.assertEqual(report["actual_metrics"]["expert_calls"], 0)
            self.assertEqual(report["rows"][0]["usage_status"], "NO_CALLS")
            self.assertEqual(report["rows"][0]["expert_calls"], 0)
            self.assertEqual(report["rows"][0]["link_status"], "LINKED")

    def test_manifest_aggregate_is_partial_recovery_compatible_and_self_hashed(self) -> None:
        _, cheap, cheap_execution, _ = expert_main._execute_source_only_early_route(
            _post(),
            measurement_config=self.config,
            publication_scope_id=self.scope.publication_scope_id,
            input_index=1,
            authoritative_reference_result=_valid_result(post_id=101),
            process_full=lambda: self.fail("provider path called"),
        )
        partial = expert_main._build_early_route_manifest_aggregate(
            {1: {"execution_receipt": cheap_execution, "comparison_receipt": None}},
            expected_input_count=2,
            measurement_config=self.config,
        )
        self.assertEqual(partial["cheap_count"], 1)
        self.assertEqual(partial["full_count"], 0)
        self.assertEqual(partial["missing_route_count"], 1)
        self.assertEqual(partial["accuracy_status"], ACCURACY_NOT_ESTIMABLE)
        self.assertFalse(partial["production_enable_allowed"])
        self.assertEqual(partial["execution_gate"], "NO_GO")
        self.assertIn("ROUTE_COVERAGE_INCOMPLETE", partial["execution_reason_codes"])
        self.assertEqual(
            partial["aggregate_sha256"],
            canonical_hash(
                {key: value for key, value in partial.items() if key != "aggregate_sha256"}
            ),
        )
        self.assertEqual(
            partial["mutable_context_binding_sha256"],
            self.config["mutable_context_binding_sha256"],
        )

        # A cheap deterministic-NIL route is baseline-equivalent only when the
        # authoritative WAL decision is HOLD.  A published reference must
        # correctly keep the aggregate at NO_GO with CHEAP_BASELINE_MISMATCH.
        authoritative_result = _valid_result(post_id=101, publish=False)
        authoritative_receipt = compute_publication_decision_commit(
            authoritative_result,
            publication_scope_id=self.scope.publication_scope_id,
            attempt_run_id="authoritative",
            input_index=1,
            post_id=101,
        )
        current_result = deepcopy(authoritative_result)
        current_receipt = compute_publication_decision_commit(
            current_result,
            publication_scope_id=self.scope.publication_scope_id,
            attempt_run_id="after",
            input_index=1,
            post_id=101,
        )
        comparison = expert_main._compare_early_route_publication(
            cheap,
            current_result=current_result,
            current_receipt=current_receipt,
            authoritative_result=authoritative_result,
            authoritative_receipt=authoritative_receipt,
        )
        zero_call_row = {
            "ledger_ref": {
                "closure_kind": "ROW_SEAL",
                "event_root_sha256": "1" * 64,
            },
            "row_summary": {
                "writer_complete": True,
                "usage_status": "NO_CALLS",
                "derived_observation": {
                    "expert_calls": 0,
                    "text_calls": 0,
                    "vlm_calls": 0,
                    "retry_count": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            },
            "attempt_receipt": {
                "publication_link_status": "LINKED_EXTERNAL_LEDGER"
            },
        }
        complete = expert_main._build_early_route_manifest_aggregate(
            {
                1: {
                    "execution_receipt": cheap_execution,
                    "comparison_receipt": comparison,
                }
            },
            expected_input_count=1,
            measurement_config=self.config,
            decision_call_rows_by_index={1: zero_call_row},
        )
        self.assertEqual(complete["execution_gate"], "GO")
        self.assertEqual(complete["observed_comparison_count"], 1)
        self.assertEqual(complete["cheap_zero_call_writer_verified_count"], 1)
        self.assertEqual(complete["execution_reason_codes"], [])
        self.assertEqual(len(complete["row_bindings"]), 1)

    def test_process_one_source_places_router_before_pipeline_dispatch(self) -> None:
        text = Path(expert_main.__file__).read_text(encoding="utf-8")
        process_start = text.index("            def _process_one(")
        process_end = text.index("            # ─── 메인 처리 루프", process_start)
        body = text[process_start:process_end]
        self.assertLess(
            body.index("_execute_source_only_early_route("),
            body.index("pipeline.process_post(post)"),
        )
        self.assertIn("CHEAP_ZERO_CALL_AUTHORITATIVE_REFERENCE_COPY", text)


if __name__ == "__main__":
    unittest.main()
