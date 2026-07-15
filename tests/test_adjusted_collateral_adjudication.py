from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

from llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)
from tools.bootstrap_regression_safe_grounding import compare_collateral
from tools.build_adjusted_collateral_adjudication import (
    blind_receipt_digest,
    build_adjudication,
)
from tools.build_adjusted_collateral_blind_packet import (
    SOURCE_FIELDS,
    _validate_golden_audit_diagnostic_contract,
    _validate_interrupted_dashboard_manifest_transition,
    build_blind_packet,
    canonical_digest,
    expected_blind_material,
    prepare_bound_scope,
    source_payload,
)
from tools.validate_adjusted_collateral_adjudication import validate_adjudication


def source_row(post_id: int) -> dict:
    return {
        "post_id": post_id,
        "gallery_id": "novel",
        "title": f"source title {post_id}",
        "content": ["source body"],
        "comments": [{"body": "source comment"}],
        "comment_context_lines": ["user1: source comment"],
        "comment_dialogue_context_lines": ["user1 -> post_author: source comment"],
        "reason_lines": ["must never reach blind judge"],
        "expected_title": "private expected title",
        "survey_label": "private label",
        "_judge_seed": {"expected": "private"},
        "analysis_result": {"private": True},
        "run_meta": {"model": "private"},
    }


def runtime_row(
    post_id: int,
    title: str | None,
    *,
    blocked_candidate: str = "Prior",
    url_override: str | None = None,
    blocked_resolution_state: str = "context_only",
) -> dict:
    url = (url_override or f"https://novelpia.com/novel/{post_id}") if title else None
    if title:
        state = GroundingState(
            post_id=post_id,
            candidate_title=title,
            candidate_url=url or "",
            source="adjusted_collateral_unit_fixture",
            official_title_exists=True,
            row_discusses_work_as_work=True,
            title_resolution_state="resolved",
            work_resolution="resolved",
            scope=ScopeState(
                scope_kind="current_work",
                confidence="high",
                direct_bridge_sources=["explicit_alias_relation", "official_detail_url"],
            ),
        )
        evidence = [
            EvidenceRecord(
                kind="alias_bridge",
                source_path_or_snippet=title,
                supports_publish=True,
                reason_code="explicit_alias_relation",
                candidate_title=title,
            ),
            EvidenceRecord(
                kind="official_detail_url",
                source_path_or_snippet=url or "",
                reason_code="official_detail_url",
                candidate_title=title,
                candidate_url=url or "",
                title_url_match=True,
            ),
        ]
        identity = {"novel_identity": {"official_title": title, "heretic_url": url}}
    else:
        blocked_url = f"https://novelpia.com/novel/{post_id}"
        state = GroundingState(
            post_id=post_id,
            candidate_title=blocked_candidate,
            candidate_url=blocked_url,
            source="adjusted_collateral_unit_fixture",
            official_title_exists=True,
            row_discusses_work_as_work=False,
            title_resolution_state=blocked_resolution_state,
            work_resolution="unresolved",
            scope=ScopeState(scope_kind="context_only", confidence="medium"),
        )
        evidence = [
            EvidenceRecord(
                kind="candidate_surface",
                source_path_or_snippet=blocked_candidate,
                supports_publish=False,
                reason_code="serialized_public_identity_scrubbed",
                candidate_title=blocked_candidate,
                candidate_url=blocked_url,
            )
        ]
        identity = {"novel_identity": {}}
    apply_publish_contract(identity, evaluate_publish_contract(state, evidence))
    return {
        "post_id": post_id,
        "gallery_id": "novel",
        "title": f"source title {post_id}",
        "content": ["source body"],
        "analysis_result": {
            "identity": identity
        },
    }


def golden_manifest(
    *,
    post_id: int = 1,
    expected_title: str | None = None,
    expected_no_public: bool | None = None,
) -> dict:
    if expected_no_public is None:
        expected_no_public = expected_title is None
    return {
        "rows": [
            {
                "post_id": post_id,
                "expected_no_public_title": expected_no_public,
                "expected_title_or_hypothesis": expected_title,
            }
        ]
    }


def compare_payload(
    baseline_rows: list[dict],
    after_rows: list[dict],
    golden: dict,
    *,
    allow_multi_variant: bool = False,
) -> dict:
    baseline_by_id = {str(row["post_id"]): row for row in baseline_rows}
    golden_by_id = {str(row["post_id"]): row for row in golden.get("rows", [])}
    changes: list[dict] = []
    for after in after_rows:
        pid = str(after["post_id"])
        result = compare_collateral(
            [baseline_by_id[pid]],
            [after],
            expected_rows=[golden_by_id[pid]] if pid in golden_by_id else [],
        )
        changes.extend(result["rows"])
    if not allow_multi_variant and len({row["post_id"] for row in after_rows}) != len(after_rows):
        raise ValueError("test fixture duplicate after post_id")
    return {
        "baseline_mode": "adjudicated_rebaseline",
        "collateral_measure": "adjusted_drift",
        "expected_shared_posts": len(baseline_rows),
        "shared_post_count": len(baseline_rows),
        "changed_post_count": len(changes),
        "adjusted_drift_count": len(changes),
        "collateral_regression_count": sum(1 for row in changes if row.get("is_regression")),
        "status_counts": dict(Counter(row["status"] for row in changes)),
        "regression_status_counts": dict(
            Counter(row["status"] for row in changes if row.get("is_regression"))
        ),
        "rows": changes,
    }


def build_material(
    baseline: list[dict],
    source: list[dict],
    after: list[dict],
    golden: dict,
    *,
    allow_multi_variant: bool = False,
    expected_golden_rows: int = 1,
):
    compare = compare_payload(
        baseline,
        after,
        golden,
        allow_multi_variant=allow_multi_variant,
    )
    packets, mapping = build_blind_packet(
        compare=compare,
        baseline_rows=baseline,
        source_rows=source,
        after_rows=after,
        golden_manifest=golden,
        packet_id="unit",
        expected_scope_rows=len(baseline),
        expected_golden_rows=expected_golden_rows,
        allow_multi_variant=allow_multi_variant,
        allow_untrusted_test_scope=True,
    )
    return compare, packets, mapping


def verdict_for(
    packet: dict,
    map_row: dict,
    source: dict,
    after: dict,
    drift: dict,
    *,
    preferred_origin: str | None = None,
    terminal: bool = False,
) -> dict:
    origins = map_row["option_origins"]
    if preferred_origin:
        preferred = next(option for option, origin in origins.items() if origin == preferred_origin)
    elif terminal:
        preferred = "INSUFFICIENT"
    else:
        preferred = "EQUIVALENT"
    blind = {
        "review_id": f"blind-{packet['drift_id'][:12]}",
        "reviewer_id": "independent-blind-reviewer",
        "method": "source_native_blind",
        "provider": "codex",
        "judge_model": "gpt-5.6-sol",
        "judge_run_id": "judge-run-unit",
        "codex_thread_id": "11111111-1111-4111-8111-111111111111",
        "goal_id": "019f4850-7a35-7263-8347-362d7e553966",
        "reviewed_at": "2026-07-10T12:00:00+09:00",
        "prompt_sha256": "a" * 64,
        "delivered_packet_sha256": packet["packet_row_sha256"],
        "packet_row_sha256": packet["packet_row_sha256"],
        "blind_to_baseline_preference": True,
        "preferred_option": preferred,
        "same_work": False,
        "relation_to_post": "direct",
    }
    blind["receipt_sha256"] = blind_receipt_digest(blind)
    verdict = {
        "drift_id": packet["drift_id"],
        "post_id": packet["post_id"],
        "packet_row_sha256": packet["packet_row_sha256"],
        "classification": None,
        "review_label": "HOLD" if terminal else "ACCEPT",
        "evidence_grade": "Strong",
        "row_rationale": "원문과 익명 후보를 비교한 독립 판결이다.",
        "evidence_refs": [f"source://post/{packet['post_id']}"],
        "blind_verdict": blind,
    }
    return verdict


def call_builder(
    *,
    compare: dict,
    verdicts: list[dict],
    baseline: list[dict],
    source: list[dict],
    after: list[dict],
    golden: dict,
    packets: list[dict],
    mapping: dict,
    allow_multi_variant: bool = False,
    expected_golden_rows: int = 1,
) -> dict:
    return build_adjudication(
        compare=compare,
        verdict_rows=verdicts,
        baseline_rows=baseline,
        source_rows=source,
        after_rows=after,
        golden_manifest=golden,
        blind_packet_rows=packets,
        blind_map=mapping,
        expected_scope_rows=len(baseline),
        expected_golden_rows=expected_golden_rows,
        allow_multi_variant=allow_multi_variant,
        allow_untrusted_test_scope=True,
    )


class AdjustedCollateralAdjudicationTest(unittest.TestCase):
    def test_interrupted_composite_dashboard_is_the_only_manifest_transition(self) -> None:
        stable = {
            "llm_model": "Gemma",
            "requested_parallel": 16,
            "dashboard_enabled": True,
            "dashboard_mode": "standalone_forward",
            "dashboard_standalone_forwarding": True,
        }
        source = copy.deepcopy(stable)
        residual = copy.deepcopy(stable)
        merged = {**copy.deepcopy(stable), "dashboard_mode": "composite_source_runs"}

        _validate_interrupted_dashboard_manifest_transition(
            stable_manifest=stable,
            source_manifest=source,
            residual_manifest=residual,
            merged_manifest=merged,
        )

        for arbitrary_mode in ("standalone_forward", "disabled", "arbitrary"):
            with self.subTest(arbitrary_mode=arbitrary_mode):
                forged = {**merged, "dashboard_mode": arbitrary_mode}
                with self.assertRaisesRegex(
                    ValueError,
                    "merged dashboard mode is not composite_source_runs",
                ):
                    _validate_interrupted_dashboard_manifest_transition(
                        stable_manifest=stable,
                        source_manifest=source,
                        residual_manifest=residual,
                        merged_manifest=forged,
                    )

        other_field_drift = {**merged, "llm_model": "different-runtime"}
        with self.assertRaisesRegex(
            ValueError,
            "stable projection mismatch outside dashboard_mode: llm_model",
        ):
            _validate_interrupted_dashboard_manifest_transition(
                stable_manifest=stable,
                source_manifest=source,
                residual_manifest=residual,
                merged_manifest=other_field_drift,
            )

        for component_name in ("source", "residual"):
            component = {**stable, "dashboard_mode": "composite_source_runs"}
            with self.subTest(component=component_name):
                with self.assertRaisesRegex(
                    ValueError,
                    f"{component_name} component dashboard mode is not standalone_forward",
                ):
                    _validate_interrupted_dashboard_manifest_transition(
                        stable_manifest=stable,
                        source_manifest=(component if component_name == "source" else source),
                        residual_manifest=(
                            component if component_name == "residual" else residual
                        ),
                        merged_manifest=merged,
                    )

    def test_golden_no_go_is_bound_diagnostic_but_bad_accounting_fails(self) -> None:
        rows = [
            {
                "post_id": index,
                "passed": index != 18,
                "status": (
                    "positive_work_unresolved"
                    if index == 18
                    else "expected_work_identity_match"
                ),
            }
            for index in range(1, 19)
        ]
        audit = {
            "report_type": "golden18_bound_audit",
            "scope": "golden_canary_expected_answer_audit",
            "gate": "NO-GO",
            "canary_semantic_gate": "NO-GO",
            "row_count": 18,
            "passed_count": 17,
            "failed_count": 1,
            "rows": rows,
        }
        diagnostic = _validate_golden_audit_diagnostic_contract(
            golden_audit=audit,
            expected_golden_rows=18,
            canonical_audit_sha256="a" * 64,
        )
        self.assertEqual(diagnostic["failed_count"], 1)
        self.assertEqual(
            diagnostic["failed_rows"],
            [{"post_id": "18", "status": "positive_work_unresolved"}],
        )
        self.assertFalse(diagnostic["blind_judge_may_override"])

        baseline = [runtime_row(1, "Prior")]
        source_rows = [source_row(1)]
        after = [runtime_row(1, None, blocked_candidate="Expected")]
        golden = golden_manifest(expected_title="Expected")
        compare = compare_payload(baseline, after, golden)
        scope = prepare_bound_scope(
            compare=compare,
            baseline_rows=baseline,
            source_rows=source_rows,
            after_rows=after,
            golden_manifest=golden,
            expected_scope_rows=1,
            expected_golden_rows=1,
            allow_untrusted_test_scope=True,
        )
        scoped_diagnostic = {
            **diagnostic,
            "row_count": 1,
            "passed_count": 0,
            "failed_count": 1,
            "failed_rows": [
                {"post_id": "1", "status": "positive_work_unresolved"}
            ],
        }
        scoped_diagnostic["failed_rows_sha256"] = canonical_digest(
            scoped_diagnostic["failed_rows"]
        )
        scope["authoritative_trust"]["golden_audit_diagnostic"] = scoped_diagnostic
        packet_rows, private_map = expected_blind_material(
            scope=scope,
            packet_id="golden-no-go-diagnostic",
        )
        constraint_sha256 = canonical_digest(scoped_diagnostic)
        self.assertTrue(packet_rows)
        self.assertTrue(
            all(
                row["golden_audit_constraint_sha256"] == constraint_sha256
                for row in packet_rows
            )
        )
        self.assertEqual(private_map["golden_audit_constraint"], scoped_diagnostic)
        self.assertEqual(
            private_map["golden_audit_constraint_sha256"],
            constraint_sha256,
        )
        self.assertNotIn("failed_rows", packet_rows[0])

        mutations = {
            "tampered_count": {**audit, "passed_count": 18},
            "missing_row": {**audit, "rows": rows[:-1]},
            "wrong_row_count": {**audit, "row_count": 17},
            "semantic_gate_override": {
                **audit,
                "gate": "PASS",
                "canary_semantic_gate": "PASS",
            },
        }
        for name, mutated in mutations.items():
            with self.subTest(mutation=name):
                with self.assertRaises(ValueError):
                    _validate_golden_audit_diagnostic_contract(
                        golden_audit=mutated,
                        expected_golden_rows=18,
                        canonical_audit_sha256="a" * 64,
                    )

    def test_direct_script_entrypoints_import_repo_tools(self) -> None:
        root = Path(__file__).resolve().parents[1]
        scripts = [
            "tools/build_adjusted_collateral_blind_packet.py",
            "tools/build_adjusted_collateral_adjudication.py",
            "tools/validate_adjusted_collateral_adjudication.py",
        ]
        for script in scripts:
            with self.subTest(script=script):
                completed = subprocess.run(
                    [sys.executable, script, "--help"],
                    cwd=root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout)

    def test_blind_packet_uses_whitelist_and_minimal_identity(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        _, packets, mapping = build_material(baseline, source, after, golden)

        self.assertTrue(set(packets[0]["source"]).issubset(SOURCE_FIELDS))
        for private in ("reason_lines", "expected_title", "survey_label", "_judge_seed", "analysis_result", "run_meta"):
            self.assertNotIn(private, packets[0]["source"])
        for option in packets[0]["candidate_options"]:
            self.assertEqual(set(option["identity"]), {"official_title", "official_url"})
        self.assertIn("comment_context_lines", packets[0]["source"])
        self.assertIn("comment_dialogue_context_lines", packets[0]["source"])
        self.assertNotIn("status", packets[0])
        self.assertEqual(set(mapping["rows"][0]["option_origins"].values()), {"before", "after"})

    def test_nonzero_drift_go_requires_complete_source_bound_blind_adjudication(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["unreviewed_adjusted_rows"], 0)
        self.assertEqual(report["true_semantic_regression_count"], 0)

    def test_blind_choice_for_before_is_true_regression(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        after = [runtime_row(1, "Changed")]
        golden = golden_manifest(expected_title="Prior")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="before"
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["true_semantic_regression_count"], 1)

    def test_missing_verdict_is_fail_closed(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        report = call_builder(
            compare=compare, verdicts=[], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )
        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["unreviewed_adjusted_rows"], 1)

    def test_empty_self_authored_compare_claiming_375_is_rejected(self) -> None:
        compare = {
            "baseline_mode": "adjudicated_rebaseline",
            "collateral_measure": "adjusted_drift",
            "expected_shared_posts": 375,
            "shared_post_count": 375,
            "changed_post_count": 0,
            "adjusted_drift_count": 0,
            "collateral_regression_count": 0,
            "status_counts": {},
            "regression_status_counts": {},
            "rows": [],
        }
        with self.assertRaisesRegex(ValueError, "baseline row count mismatch"):
            build_blind_packet(
                compare=compare,
                baseline_rows=[],
                source_rows=[],
                after_rows=[],
                golden_manifest={"rows": []},
                packet_id="attack",
            )

    def test_packet_source_tamper_with_stale_hash_is_rejected(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        tampered_packets = copy.deepcopy(packets)
        tampered_packets[0]["source"]["content"] = ["tampered"]
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=tampered_packets, mapping=mapping,
        )
        self.assertEqual(report["gate"], "NO-GO")
        self.assertTrue(any("blind_packet_source_binding_mismatch" in issue for issue in report["validation_issues"]))

    def test_private_map_origin_swap_is_rejected(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        tampered_map = copy.deepcopy(mapping)
        origins = tampered_map["rows"][0]["option_origins"]
        origins["A"], origins["B"] = origins["B"], origins["A"]
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=tampered_map,
        )
        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("blind_private_map_source_binding_mismatch", report["validation_issues"])

    def test_compare_null_but_actual_public_title_is_rejected_before_adjudication(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        declared_after = [runtime_row(1, None)]
        actual_after = [runtime_row(1, "LEAKED PUBLIC")]
        golden = golden_manifest(expected_no_public=True)
        compare, packets, mapping = build_material(baseline, source, declared_after, golden)
        with self.assertRaisesRegex(ValueError, "collateral compare does not match recomputation"):
            call_builder(
                compare=compare, verdicts=[], baseline=baseline, source=source,
                after=actual_after, golden=golden, packets=packets, mapping=mapping,
            )

    def test_after_row_source_payload_mismatch_is_rejected(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        after[0]["title"] = "tampered source title"
        golden = golden_manifest(expected_title="Recovered")
        compare = compare_payload(baseline, after, golden)

        with self.assertRaisesRegex(ValueError, "after/source payload mismatch"):
            build_blind_packet(
                compare=compare,
                baseline_rows=baseline,
                source_rows=source,
                after_rows=after,
                golden_manifest=golden,
                packet_id="unit",
                expected_scope_rows=1,
                expected_golden_rows=1,
            )

    def test_golden_expected_title_mismatch_is_true_regression(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Wrong")]
        golden = golden_manifest(expected_title="Expected")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )
        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["true_semantic_regression_count"], 1)
        self.assertIn("golden_expected_title_mismatch", report["reviewed_rows"][0]["hard_safety_issues"])

    def test_no_public_drift_without_promotion_contract_is_true_regression(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        valid_after = runtime_row(1, None)
        after = [copy.deepcopy(valid_after)]
        after[0]["analysis_result"]["identity"] = {"relevant": False}
        golden = golden_manifest(expected_no_public=True)
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], valid_after, compare["rows"][0], preferred_origin="after"
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["true_semantic_regression_count"], 1)
        self.assertIn(
            "nonpublic_promotion_decision_missing",
            report["reviewed_rows"][0]["hard_safety_issues"],
        )

    def test_insufficient_evidence_cannot_publish_intended_recovery(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        verdict["review_label"] = "INFO_MISSING"
        verdict["evidence_grade"] = "Missing"
        verdict["blind_verdict"]["relation_to_post"] = "insufficient"
        verdict["blind_verdict"]["receipt_sha256"] = blind_receipt_digest(verdict["blind_verdict"])
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        self.assertEqual(report["gate"], "NO-GO")
        issues = report["reviewed_rows"][0]["validation_issues"]
        self.assertIn("nonterminal_recovery_or_removal_requires_accept", issues)
        self.assertIn("insufficient_evidence_must_be_safe_terminal_or_regression", issues)

    def test_same_post_multiple_variants_keep_distinct_drift_ids_and_missing_verdict(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Variant A"), runtime_row(1, "Variant B")]
        golden = {"rows": []}
        compare, packets, mapping = build_material(
            baseline, source, after, golden, allow_multi_variant=True, expected_golden_rows=0
        )
        self.assertEqual(len({packet["drift_id"] for packet in packets}), 2)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
            allow_multi_variant=True, expected_golden_rows=0,
        )
        self.assertEqual(report["drift_union_count"], 2)
        self.assertEqual(report["unreviewed_adjusted_rows"], 1)
        self.assertEqual(report["gate"], "NO-GO")

    def test_safe_terminal_contract_is_derived_not_judge_authored(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        after = [runtime_row(1, None)]
        golden = golden_manifest(expected_no_public=True)
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], terminal=True
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )
        reviewed = report["reviewed_rows"][0]
        contract = reviewed["terminal_contract"]
        self.assertEqual(report["gate"], "GO")
        self.assertEqual(reviewed["validation_issues"], [])
        self.assertEqual(contract["source_hash"], canonical_digest(source_payload(source[0])))
        self.assertEqual(contract["input_hash"], canonical_digest(source[0]))
        self.assertTrue(contract["test_replay_artifacts"])
        self.assertNotIn("independent_review", contract)
        self.assertEqual(
            contract["validator_contract_recompute"]["semantic_judgment_source"],
            "raw_codex_blind_receipt",
        )

    def test_valid_safe_terminal_goes_only_with_actual_no_publish_contract(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        after = [runtime_row(1, None)]
        golden = golden_manifest(expected_no_public=True)
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], terminal=True
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )
        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["classification_counts"], {"safe_no_public_terminal": 1})

    def test_positive_golden_preserved_unresolved_can_be_safe_terminal(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        after = [
            runtime_row(
                1,
                None,
                blocked_candidate="Expected",
                blocked_resolution_state="unresolved_matchable",
            )
        ]
        identity = after[0]["analysis_result"]["identity"]
        identity["is_relevant"] = True
        identity["is_novel_related"] = True
        golden = golden_manifest(expected_title="Expected")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], terminal=True
        )

        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        reviewed = report["reviewed_rows"][0]
        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["classification_counts"], {"safe_no_public_terminal": 1})
        self.assertEqual(
            reviewed["golden_audit_binding"],
            {
                "passed": True,
                "status": "expected_work_evidence_preserved_unresolved",
            },
        )
        self.assertTrue(reviewed["terminal_contract"]["golden_audit_binding"]["passed"])

    def test_positive_golden_terminal_rejects_missing_candidate_and_failed_audit(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        after = [runtime_row(1, None, blocked_candidate="Expected")]
        identity = after[0]["analysis_result"]["identity"]
        identity["title_resolution_state"] = "unresolved_matchable"
        identity["is_relevant"] = True
        identity["is_novel_related"] = True
        identity["promotion_decision"]["candidate_preserved"] = False
        identity["publish_contract_trace"]["pre_gate_candidate"] = {
            "official_title": None,
            "official_url": None,
        }
        identity["publish_ledger"]["candidate_preservation"] = {
            "official_title": None,
            "official_url": None,
        }
        identity["candidate_ledger"] = {
            "promotion_decision": identity["promotion_decision"],
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }
        identity.pop("blocked_official_title", None)
        identity.pop("blocked_official_title_url", None)
        golden = golden_manifest(expected_title="Expected")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], terminal=True
        )

        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        reviewed = report["reviewed_rows"][0]
        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["true_semantic_regression_count"], 1)
        self.assertEqual(report["actionable_unfixed_count"], 1)
        self.assertEqual(report["golden_audit_diagnostic"]["failed_count"], 1)
        self.assertEqual(
            report["golden_audit_diagnostic"]["failed_rows"],
            [{"post_id": "1", "status": "positive_work_unresolved"}],
        )
        self.assertFalse(
            report["golden_audit_diagnostic"]["blind_judge_may_override"]
        )
        self.assertEqual(
            reviewed["golden_audit_binding"],
            {"passed": False, "status": "positive_work_unresolved"},
        )
        self.assertIn(
            "nonpublic_candidate_must_be_preserved_or_no_candidate",
            reviewed["hard_safety_issues"],
        )
        self.assertIsNone(reviewed["terminal_contract"])

    def test_terminal_does_not_invent_missing_candidate_accounting_reason(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        after = [runtime_row(1, None)]
        identity = after[0]["analysis_result"]["identity"]
        identity["promotion_decision"]["candidate_preserved"] = False
        identity["candidate_ledger"]["promotion_decision"]["candidate_preserved"] = False
        golden = golden_manifest(expected_no_public=True)
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], terminal=True
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["true_semantic_regression_count"], 1)
        self.assertIn(
            "nonpublic_candidate_must_be_preserved_or_no_candidate",
            report["reviewed_rows"][0]["hard_safety_issues"],
        )
        self.assertIsNone(report["reviewed_rows"][0]["terminal_contract"])

    def test_fake_judge_independent_review_claim_is_rejected(self) -> None:
        baseline = [runtime_row(1, "Prior")]
        source = [source_row(1)]
        after = [runtime_row(1, None)]
        golden = golden_manifest(expected_no_public=True)
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], terminal=True
        )
        verdict["independent_review"] = {
            "reviewer_id": "INDEPENDENT-BLIND-REVIEWER",
            "claim": "self-authored second review",
        }
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn(
            "judge_supplied_derived_terminal_contract_fields_forbidden",
            report["reviewed_rows"][0]["validation_issues"],
        )
        contract = report["reviewed_rows"][0]["terminal_contract"]
        self.assertNotIn("independent_review", contract)
        self.assertEqual(
            contract["validator_contract_recompute"]["validator_id"],
            "deterministic-source-bound-contract-validator",
        )

    def test_missing_review_label_is_invalid(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        verdict["review_label"] = None
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )
        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("review_label_invalid_or_missing", report["reviewed_rows"][0]["validation_issues"])

    def test_production_scope_cannot_be_shrunk_to_unit_claim(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare = compare_payload(baseline, after, golden)
        with self.assertRaisesRegex(ValueError, "baseline row count mismatch"):
            build_blind_packet(
                compare=compare,
                baseline_rows=baseline,
                source_rows=source,
                after_rows=after,
                golden_manifest=golden,
                packet_id="unit",
            )

    def test_validator_recomputes_and_rejects_self_authored_go(self) -> None:
        baseline = [runtime_row(1, None)]
        source = [source_row(1)]
        after = [runtime_row(1, "Recovered")]
        golden = golden_manifest(expected_title="Recovered")
        compare, packets, mapping = build_material(baseline, source, after, golden)
        verdict = verdict_for(
            packets[0], mapping["rows"][0], source[0], after[0], compare["rows"][0], preferred_origin="after"
        )
        report = call_builder(
            compare=compare, verdicts=[verdict], baseline=baseline, source=source,
            after=after, golden=golden, packets=packets, mapping=mapping,
        )
        tampered = copy.deepcopy(report)
        tampered["unreviewed_adjusted_rows"] = 99
        validation = validate_adjudication(
            report=tampered,
            compare=compare,
            verdict_rows=[verdict],
            baseline_rows=baseline,
            source_rows=source,
            after_rows=after,
            golden_manifest=golden,
            blind_packet_rows=packets,
            blind_map=mapping,
            expected_scope_rows=1,
            expected_golden_rows=1,
            allow_untrusted_test_scope=True,
        )
        self.assertEqual(validation["validator_gate"], "NO-GO")
        self.assertIn("unreviewed_adjusted_rows", validation["mismatched_fields"])


if __name__ == "__main__":
    unittest.main()
