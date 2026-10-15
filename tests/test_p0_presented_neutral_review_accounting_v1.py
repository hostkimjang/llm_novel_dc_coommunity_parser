from __future__ import annotations

import ast
import base64
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from llm_batch.grounding import p0_actual_packet_contract as packet_contract  # noqa: E402
from llm_batch.grounding import p0_presented_batch_exact_accounting_v1_contract as batch_contract  # noqa: E402
from llm_batch.grounding import p0_presented_neutral_review_accounting_v1_contract as contract  # noqa: E402
from llm_batch.grounding import p0_presented_neutral_review_accounting_v1_parent_validator as parent  # noqa: E402
from tests.test_p0_presented_batch_exact_accounting_v1 import (  # noqa: E402
    BATCH_COMPLETED_AT,
    BATCH_PRECOMMITTED_AT,
    BATCH_STARTED_AT,
    RESULTS_SEALED_AT as BATCH_RESULTS_SEALED_AT,
    REVIEW_INVENTORY_SEALED_AT,
    _base_bundle,
    _batch_inputs,
    _receipt_for_results,
    _unreviewed_for,
)


ASSIGNMENT_SEALED_AT = "2026-09-02T00:00:10Z"
REVIEW_PRECOMMITTED_AT = "2026-09-02T00:00:11Z"
REVIEWED_AT = "2026-09-02T00:00:12Z"
RESULTS_SEALED_AT = "2026-09-02T00:00:13Z"
RECEIPT_SEALED_AT = "2026-09-02T00:00:14Z"


def _object(raw: bytes) -> dict[str, object]:
    return json.loads(raw.decode("utf-8"))


def _rows(raw: bytes) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.decode("utf-8").splitlines()]


def _file(value: object) -> bytes:
    return contract.canonical_file_bytes(value)


def _jsonl(values: list[dict[str, object]]) -> bytes:
    return b"".join(_file(value) for value in values)


def _reseal(value: dict[str, object], field: str) -> dict[str, object]:
    material = {key: item for key, item in value.items() if key != field}
    return {**material, field: contract.canonical_sha256(material)}


def _gold_from_subject(subject: dict[str, object]) -> dict[str, object]:
    return {
        field: subject[field]
        for field in (
            "line_number",
            "character_span_start",
            "character_span_end",
            "utf8_byte_span_start",
            "utf8_byte_span_end",
            "evidence_text",
            "surface_text",
            "presented_definition_text",
        )
    }


def _decisions(units_raw: bytes, *, unjudged_last: bool = False, all_empty: bool = False, all_judged: bool = False) -> list[dict[str, object]]:
    decisions: list[dict[str, object]] = []
    for unit in _rows(units_raw):
        sequence = unit["input_sequence"]
        if unjudged_last and sequence == 40:
            decisions.append(
                {
                    "input_sequence": sequence,
                    "annotation_status": "UNJUDGED",
                    "terminal_reason_code": "PRESENTED_REVIEW_NOT_COMPLETED",
                    "reviewer_id": None,
                    "reviewed_at": None,
                    "gold_spans": None,
                }
            )
        elif sequence == 13 and not all_judged:
            decisions.append(
                {
                    "input_sequence": sequence,
                    "annotation_status": "UNAVAILABLE",
                    "terminal_reason_code": "PRESENTED_REVIEW_UNAVAILABLE",
                    "reviewer_id": "reviewer-opaque-1",
                    "reviewed_at": REVIEWED_AT,
                    "gold_spans": None,
                }
            )
        else:
            subjects = unit["emitted_observation_subjects"]
            decisions.append(
                {
                    "input_sequence": sequence,
                    "annotation_status": "JUDGED",
                    "terminal_reason_code": "PRESENTED_FULL_PAYLOAD_REVIEW_RECORDED",
                    "reviewer_id": "reviewer-opaque-1",
                    "reviewed_at": REVIEWED_AT,
                    "gold_spans": [] if all_empty else [_gold_from_subject(subject) for subject in subjects],
                }
            )
    return decisions


def _review_bundle(
    *,
    unjudged_last: bool = False,
    all_empty: bool = False,
    all_judged: bool = False,
    upstream: dict[str, bytes] | None = None,
) -> dict[str, bytes]:
    upstream = _base_bundle() if upstream is None else upstream
    roster = contract.build_reviewer_roster_bytes(
        [
            {
                "reviewer_id": "reviewer-opaque-1",
                "identity_commitment_sha256": contract.canonical_sha256("reviewer-identity-1"),
                "independence_group_id": "group-presented-1",
            }
        ]
    )
    units = contract.build_review_unit_inventory_bytes(
        sampling_plan_raw=upstream["plan"],
        expected_sampling_plan_raw_sha256=contract.raw_sha256(upstream["plan"]),
        bridge_inventory_raw=upstream["bridge"],
        batch_precommit_raw=upstream["precommit"],
        expected_batch_precommit_raw_sha256=contract.raw_sha256(upstream["precommit"]),
        results_raw=upstream["results"],
        batch_receipt_raw=upstream["receipt"],
        unreviewed_inventory_raw=upstream["unreviewed"],
    )
    assignments = contract.build_assignment_inventory_bytes(
        units, roster, ["reviewer-opaque-1"] * 40
    )
    review_precommit = contract.build_review_precommit_bytes(
        sampling_plan_raw=upstream["plan"],
        expected_sampling_plan_raw_sha256=contract.raw_sha256(upstream["plan"]),
        bridge_inventory_raw=upstream["bridge"],
        batch_precommit_raw=upstream["precommit"],
        expected_batch_precommit_raw_sha256=contract.raw_sha256(upstream["precommit"]),
        results_raw=upstream["results"],
        batch_receipt_raw=upstream["receipt"],
        unreviewed_inventory_raw=upstream["unreviewed"],
        reviewer_roster_raw=roster,
        review_unit_inventory_raw=units,
        assignment_inventory_raw=assignments,
        review_guideline_sha256=contract.canonical_sha256("presented-neutral-guideline-v1"),
        assignment_sealed_at=ASSIGNMENT_SEALED_AT,
        review_precommitted_at=REVIEW_PRECOMMITTED_AT,
    )
    review_results, review_receipt = contract.execute_presented_review(
        sampling_plan_raw=upstream["plan"],
        expected_sampling_plan_raw_sha256=contract.raw_sha256(upstream["plan"]),
        bridge_inventory_raw=upstream["bridge"],
        batch_precommit_raw=upstream["precommit"],
        expected_batch_precommit_raw_sha256=contract.raw_sha256(upstream["precommit"]),
        results_raw=upstream["results"],
        batch_receipt_raw=upstream["receipt"],
        unreviewed_inventory_raw=upstream["unreviewed"],
        reviewer_roster_raw=roster,
        review_unit_inventory_raw=units,
        assignment_inventory_raw=assignments,
        review_precommit_raw=review_precommit,
        review_decisions=_decisions(units, unjudged_last=unjudged_last, all_empty=all_empty, all_judged=all_judged),
        review_results_sealed_at=RESULTS_SEALED_AT,
        receipt_sealed_at=RECEIPT_SEALED_AT,
    )
    return {
        **upstream,
        "roster": roster,
        "units": units,
        "assignments": assignments,
        "review_precommit": review_precommit,
        "review_results": review_results,
        "review_receipt": review_receipt,
    }


def _all_utf8_upstream() -> dict[str, bytes]:
    upstream = _base_bundle()
    inputs = _batch_inputs(upstream["plan"])
    inputs[12]["payload"] = "'복구표면'은 복구 정의를 뜻한다.".encode("utf-8")
    bridge = batch_contract.build_bridge_inventory_bytes(
        scope_raw=upstream["scope"], census_raw=upstream["census"],
        frame_manifest_raw=upstream["frame"], seed_receipt_raw=upstream["seed"],
        sampling_plan_raw=upstream["plan"], batch_inputs=inputs,
    )
    precommit = batch_contract.build_batch_precommit_bytes(
        scope_raw=upstream["scope"], census_raw=upstream["census"],
        frame_manifest_raw=upstream["frame"], seed_receipt_raw=upstream["seed"],
        sampling_plan_raw=upstream["plan"], bridge_inventory_raw=bridge,
        precommitted_at=BATCH_PRECOMMITTED_AT,
    )
    results, receipt = batch_contract.execute_presented_batch(
        scope_raw=upstream["scope"], census_raw=upstream["census"],
        frame_manifest_raw=upstream["frame"], seed_receipt_raw=upstream["seed"],
        sampling_plan_raw=upstream["plan"], bridge_inventory_raw=bridge,
        batch_precommit_raw=precommit, batch_started_at=BATCH_STARTED_AT,
        batch_completed_at=BATCH_COMPLETED_AT, results_sealed_at=BATCH_RESULTS_SEALED_AT,
    )
    unreviewed = batch_contract.build_unreviewed_inventory_bytes(
        receipt, scope_raw=upstream["scope"], census_raw=upstream["census"],
        frame_manifest_raw=upstream["frame"], seed_receipt_raw=upstream["seed"],
        sampling_plan_raw=upstream["plan"], bridge_inventory_raw=bridge,
        batch_precommit_raw=precommit, results_raw=results,
        review_inventory_sealed_at=REVIEW_INVENTORY_SEALED_AT,
    )
    return {**upstream, "bridge": bridge, "precommit": precommit, "results": results, "receipt": receipt, "unreviewed": unreviewed}


def _parent_validate(bundle: dict[str, bytes]) -> dict[str, object]:
    return parent.validate_review_bundle_against_raw_inputs(
        sampling_plan_raw=bundle["plan"],
        expected_sampling_plan_raw_sha256=contract.raw_sha256(bundle["plan"]),
        bridge_inventory_raw=bundle["bridge"],
        batch_precommit_raw=bundle["precommit"],
        expected_batch_precommit_raw_sha256=contract.raw_sha256(bundle["precommit"]),
        results_raw=bundle["results"],
        batch_receipt_raw=bundle["receipt"],
        unreviewed_inventory_raw=bundle["unreviewed"],
        expected_unreviewed_inventory_raw_sha256=contract.raw_sha256(bundle["unreviewed"]),
        reviewer_roster_raw=bundle["roster"],
        review_unit_inventory_raw=bundle["units"],
        assignment_inventory_raw=bundle["assignments"],
        review_precommit_raw=bundle["review_precommit"],
        expected_review_precommit_raw_sha256=contract.raw_sha256(bundle["review_precommit"]),
        review_results_raw=bundle["review_results"],
        review_receipt_raw=bundle["review_receipt"],
    )


def _execute_decisions(bundle: dict[str, bytes], decisions: object) -> tuple[bytes, bytes]:
    return contract.execute_presented_review(
        sampling_plan_raw=bundle["plan"],
        expected_sampling_plan_raw_sha256=contract.raw_sha256(bundle["plan"]),
        bridge_inventory_raw=bundle["bridge"],
        batch_precommit_raw=bundle["precommit"],
        expected_batch_precommit_raw_sha256=contract.raw_sha256(bundle["precommit"]),
        results_raw=bundle["results"],
        batch_receipt_raw=bundle["receipt"],
        unreviewed_inventory_raw=bundle["unreviewed"],
        reviewer_roster_raw=bundle["roster"],
        review_unit_inventory_raw=bundle["units"],
        assignment_inventory_raw=bundle["assignments"],
        review_precommit_raw=bundle["review_precommit"],
        review_decisions=decisions,
        review_results_sealed_at=RESULTS_SEALED_AT,
        receipt_sealed_at=RECEIPT_SEALED_AT,
    )


class PresentedNeutralReviewAccountingV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = _review_bundle()

    def test_positive_presented_terminal_accounting_and_parent_replay(self) -> None:
        receipt = _object(self.bundle["review_receipt"])
        self.assertEqual(receipt["selected_input_itt_denominator"], 40)
        self.assertEqual(receipt["annotation_status_counts"], {"JUDGED": 39, "UNAVAILABLE": 1, "UNJUDGED": 0})
        self.assertTrue(receipt["presented_terminal_review_accounting_exhaustive"])
        self.assertFalse(receipt["presented_all_full_payload_inputs_judged"])
        self.assertEqual(receipt["contextual_review_denominator"], 9)
        self.assertEqual(receipt["full_payload_review_denominator"], 40)
        self.assertEqual(receipt["judged_subset_emitted_observation_denominator"], 9)
        self.assertEqual(receipt["judged_subset_gold_span_denominator"], 9)
        self.assertIsNone(receipt["all_input_emitted_observation_denominator"])
        self.assertIsNone(receipt["all_input_gold_span_denominator"])
        self.assertIsNone(receipt["all_input_gold_span_count"])
        replay = _parent_validate(self.bundle)
        self.assertTrue(replay["parent_separate_implementation_review_replay_verified"])
        self.assertTrue(replay["presented_terminal_review_accounting_exhaustive"])
        self.assertFalse(replay["exhaustive_human_review_verified"])

    def test_unjudged_is_explicit_terminal_but_presented_exhaustive_is_false(self) -> None:
        bundle = _review_bundle(unjudged_last=True)
        receipt = _object(bundle["review_receipt"])
        self.assertEqual(receipt["presented_terminal_input_count"], 40)
        self.assertEqual(receipt["presented_unjudged_input_count"], 1)
        self.assertFalse(receipt["presented_terminal_review_accounting_exhaustive"])
        self.assertEqual(receipt["actual_human_unreviewed_input_count"], 40)
        self.assertFalse(_parent_validate(bundle)["presented_terminal_review_accounting_exhaustive"])

    def test_unavailable_and_unjudged_keep_gold_and_arithmetic_null(self) -> None:
        unavailable = _rows(self.bundle["review_results"])[12]
        for field in (
            "observation_adjudications", "observation_adjudications_sha256",
            "presented_gold_spans", "presented_gold_spans_sha256", "gold_span_count",
            "confirmed_emitted_count", "spurious_emitted_count", "missed_gold_span_count",
        ):
            self.assertIsNone(unavailable[field])
        bundle = _review_bundle(unjudged_last=True)
        self.assertIsNone(_rows(bundle["review_results"])[39]["reviewed_at"])

    def test_judged_empty_gold_is_zero_not_unavailable_null(self) -> None:
        row = _rows(self.bundle["review_results"])[11]
        self.assertEqual(row["annotation_status"], "JUDGED")
        self.assertEqual(row["presented_gold_spans"], [])
        self.assertEqual(row["gold_span_count"], 0)
        self.assertEqual(row["missed_gold_span_count"], 0)

    def test_asaenggal_is_confirmed_neutral_surface_only(self) -> None:
        row = _rows(self.bundle["review_results"])[13]
        self.assertEqual(row["confirmed_emitted_count"], 1)
        serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)
        self.assertIn("아생갤", serialized)
        for forbidden in contract._FORBIDDEN_SEMANTIC_FIELDS:
            self.assertNotIn(forbidden, serialized)

    def test_unit_assignment_and_result_drop_duplicate_reorder_fail(self) -> None:
        for key in ("units", "assignments", "review_results"):
            rows = _rows(self.bundle[key])
            variants = (rows[:-1], rows + [deepcopy(rows[-1])], list(reversed(rows)))
            for variant in variants:
                with self.subTest(key=key, length=len(variant)), self.assertRaises(parent.P0PresentedNeutralReviewParentError):
                    _parent_validate({**self.bundle, key: _jsonl(variant)})

    def test_cross_input_contextual_subject_and_missed_unit_fail(self) -> None:
        rows = _rows(self.bundle["units"])
        for mutate in (
            lambda changed: changed[0].__setitem__("emitted_observation_subjects", deepcopy(changed[10]["emitted_observation_subjects"])),
            lambda changed: changed[0].__setitem__("full_payload_missed_span_unit_sha256", changed[1]["full_payload_missed_span_unit_sha256"]),
        ):
            changed = deepcopy(rows)
            mutate(changed)
            changed[0]["emitted_observation_subjects_sha256"] = contract.canonical_sha256(changed[0]["emitted_observation_subjects"])
            material = {key: value for key, value in changed[0].items() if key != "input_review_unit_sha256"}
            changed[0]["input_review_unit_sha256"] = contract.canonical_sha256({"domain": "P0_PRESENTED_NEUTRAL_INPUT_REVIEW_UNIT_V1", **material})
            with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
                _parent_validate({**self.bundle, "units": _jsonl(changed)})

    def test_reviewer_roster_and_assignment_swap_fail(self) -> None:
        assignments = _rows(self.bundle["assignments"])
        changed = deepcopy(assignments)
        changed[0]["reviewer_identity_commitment_sha256"] = contract.canonical_sha256("attacker")
        changed[0] = _reseal(changed[0], "assignment_row_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "assignments": _jsonl(changed)})
        roster = _rows(self.bundle["roster"])
        roster[0]["reviewer_id"] = "reviewer-personal-name-injection"
        roster[0] = _reseal(roster[0], "reviewer_row_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "roster": _jsonl(roster)})

    def test_precommit_raw_pin_and_chronology_attacks_fail(self) -> None:
        precommit = _object(self.bundle["review_precommit"])
        for field, value in (
            ("upstream_results_raw_sha256", contract.canonical_sha256("other")),
            ("review_guideline_sha256", contract.canonical_sha256("posthoc-guide")),
            ("review_precommitted_at", ASSIGNMENT_SEALED_AT),
        ):
            changed = deepcopy(precommit)
            changed[field] = value
            changed = _reseal(changed, "artifact_sha256")
            with self.subTest(field=field), self.assertRaises(parent.P0PresentedNeutralReviewParentError):
                _parent_validate({**self.bundle, "review_precommit": _file(changed)})

    def test_gold_span_offset_utf8_evidence_overlap_and_hash_attacks_fail(self) -> None:
        result_rows = _rows(self.bundle["review_results"])
        target_index = 13
        for mutate in (
            lambda span: span.__setitem__("character_span_end", span["character_span_end"] - 1),
            lambda span: span.__setitem__("utf8_byte_span_start", span["utf8_byte_span_start"] + 1),
            lambda span: span.__setitem__("evidence_text", "다른 증거"),
            lambda span: span.__setitem__("evidence_utf8_sha256", contract.canonical_sha256("wrong")),
        ):
            changed = deepcopy(result_rows)
            span = changed[target_index]["presented_gold_spans"][0]
            mutate(span)
            span_material = {key: value for key, value in span.items() if key != "gold_span_sha256"}
            span["gold_span_sha256"] = contract.canonical_sha256({"domain": "P0_PRESENTED_NEUTRAL_GOLD_SPAN_V1", "input_review_unit_sha256": changed[target_index]["input_review_unit_sha256"], **span_material})
            changed[target_index]["presented_gold_spans_sha256"] = contract.canonical_sha256(changed[target_index]["presented_gold_spans"])
            changed[target_index] = _reseal(changed[target_index], "review_result_row_sha256")
            with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
                _parent_validate({**self.bundle, "review_results": _jsonl(changed)})

    def test_adjudication_and_tp_fp_fn_arithmetic_laundering_fail(self) -> None:
        rows = _rows(self.bundle["review_results"])
        target_index = 13
        for field, value in (
            ("confirmed_emitted_count", 0),
            ("spurious_emitted_count", 1),
            ("missed_gold_span_count", 1),
        ):
            changed = deepcopy(rows)
            changed[target_index][field] = value
            changed[target_index] = _reseal(changed[target_index], "review_result_row_sha256")
            with self.subTest(field=field), self.assertRaises(parent.P0PresentedNeutralReviewParentError):
                _parent_validate({**self.bundle, "review_results": _jsonl(changed)})

    def test_unavailable_zero_laundering_and_unjudged_exhaustive_laundering_fail(self) -> None:
        rows = _rows(self.bundle["review_results"])
        changed = deepcopy(rows)
        for field, value in (
            ("observation_adjudications", []), ("observation_adjudications_sha256", contract.canonical_sha256([])),
            ("presented_gold_spans", []), ("presented_gold_spans_sha256", contract.canonical_sha256([])),
            ("gold_span_count", 0), ("confirmed_emitted_count", 0), ("spurious_emitted_count", 0), ("missed_gold_span_count", 0),
        ):
            changed[12][field] = value
        changed[12] = _reseal(changed[12], "review_result_row_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "review_results": _jsonl(changed)})

        partial = _review_bundle(unjudged_last=True)
        receipt = _object(partial["review_receipt"])
        receipt["presented_terminal_review_accounting_exhaustive"] = True
        receipt = _reseal(receipt, "artifact_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**partial, "review_receipt": _file(receipt)})

    def test_receipt_denominator_metric_credit_and_bool_scalar_attacks_fail(self) -> None:
        receipt = _object(self.bundle["review_receipt"])
        for field, value in (
            ("selected_input_itt_denominator", 39),
            ("actual_human_review_count", 40),
            ("actual_source_credit_count", 40),
            ("metric_status", "ESTIMABLE"),
            ("semantic_metrics_allowed", True),
            ("observation_rows_are_sampling_units", True),
            ("presented_judged_input_count", True),
            ("all_input_emitted_observation_denominator", 9),
            ("all_input_gold_span_denominator", 9),
        ):
            changed = deepcopy(receipt)
            changed[field] = value
            changed = _reseal(changed, "artifact_sha256")
            with self.subTest(field=field), self.assertRaises(parent.P0PresentedNeutralReviewParentError):
                _parent_validate({**self.bundle, "review_receipt": _file(changed)})

    def test_all_judged_denominators_are_exact_and_all_unavailable_is_not_gold_verified(self) -> None:
        complete = _review_bundle(all_judged=True, upstream=_all_utf8_upstream())
        receipt = _object(complete["review_receipt"])
        self.assertTrue(receipt["presented_all_full_payload_inputs_judged"])
        self.assertEqual(receipt["all_input_emitted_observation_denominator"], 10)
        self.assertEqual(receipt["all_input_gold_span_denominator"], 10)
        self.assertEqual(receipt["all_input_gold_span_count"], 10)
        self.assertTrue(receipt["judged_subset_presented_gold_span_set_accounting_verified"])
        self.assertEqual(_parent_validate(complete)["all_input_gold_span_denominator"], 10)

        unavailable = [
            {
                "input_sequence": index,
                "annotation_status": "UNAVAILABLE",
                "terminal_reason_code": "PRESENTED_REVIEW_UNAVAILABLE",
                "reviewer_id": "reviewer-opaque-1",
                "reviewed_at": REVIEWED_AT,
                "gold_spans": None,
            }
            for index in range(1, 41)
        ]
        results, accounting = _execute_decisions(self.bundle, unavailable)
        unavailable_bundle = {**self.bundle, "review_results": results, "review_receipt": accounting}
        unavailable_receipt = _object(accounting)
        self.assertFalse(unavailable_receipt["judged_subset_presented_gold_span_set_accounting_verified"])
        self.assertEqual(unavailable_receipt["judged_subset_emitted_observation_denominator"], 0)
        self.assertEqual(unavailable_receipt["judged_subset_gold_span_denominator"], 0)
        self.assertIsNone(unavailable_receipt["all_input_emitted_observation_denominator"])
        self.assertIsNone(unavailable_receipt["all_input_gold_span_denominator"])
        self.assertTrue(_parent_validate(unavailable_bundle)["presented_terminal_review_accounting_exhaustive"])

    def test_upstream_plan_and_batch_precommit_lineage_replacements_fail(self) -> None:
        bogus = b"{}\n"
        common = {
            "bridge_inventory_raw": self.bundle["bridge"],
            "results_raw": self.bundle["results"],
            "batch_receipt_raw": self.bundle["receipt"],
            "unreviewed_inventory_raw": self.bundle["unreviewed"],
            "reviewer_roster_raw": self.bundle["roster"],
            "review_unit_inventory_raw": self.bundle["units"],
            "assignment_inventory_raw": self.bundle["assignments"],
            "review_guideline_sha256": contract.canonical_sha256("lineage-attack"),
            "assignment_sealed_at": ASSIGNMENT_SEALED_AT,
            "review_precommitted_at": REVIEW_PRECOMMITTED_AT,
        }
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            contract.build_review_precommit_bytes(
                sampling_plan_raw=bogus,
                expected_sampling_plan_raw_sha256=contract.raw_sha256(bogus),
                batch_precommit_raw=self.bundle["precommit"],
                expected_batch_precommit_raw_sha256=contract.raw_sha256(self.bundle["precommit"]),
                **common,
            )
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            contract.build_review_precommit_bytes(
                sampling_plan_raw=self.bundle["plan"],
                expected_sampling_plan_raw_sha256=contract.raw_sha256(self.bundle["plan"]),
                batch_precommit_raw=bogus,
                expected_batch_precommit_raw_sha256=contract.raw_sha256(bogus),
                **common,
            )
        for key in ("plan", "precommit"):
            with self.subTest(key=key), self.assertRaises(parent.P0PresentedNeutralReviewParentError):
                _parent_validate({**self.bundle, key: bogus})

        other_plan = _object(self.bundle["plan"])
        selected = deepcopy(other_plan["selected_inputs"])
        selected[0]["candidate_id"] = "candidate-lineage-replacement"
        other_plan["selected_inputs"] = selected
        other_plan["selected_input_set_sha256"] = contract.canonical_sha256(selected)
        other_plan = _reseal(other_plan, "artifact_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "plan": _file(other_plan)})

    def test_public_mapping_inputs_fail_with_contract_errors(self) -> None:
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            contract.build_reviewer_roster_bytes([None])
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            contract.build_assignment_inventory_bytes(
                self.bundle["units"], self.bundle["roster"], [{}] + ["reviewer-opaque-1"] * 39
            )
        decisions = _decisions(self.bundle["units"])
        decisions[0] = None
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            _execute_decisions(self.bundle, decisions)
        decisions = _decisions(self.bundle["units"])
        decisions[0]["gold_spans"] = [None]
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            _execute_decisions(self.bundle, decisions)

        assignments = _rows(self.bundle["assignments"])
        assignments[0]["reviewer_id"] = {}
        assignments[0] = _reseal(assignments[0], "assignment_row_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "assignments": _jsonl(assignments)})

    def test_gold_relation_projection_definition_limit_and_over_64_capacity(self) -> None:
        line = "'첫말'은 첫 정의를 뜻한다."
        payload = line.encode("utf-8")
        unit = {
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "payload_sha256": contract.raw_sha256(payload),
            "input_review_unit_sha256": contract.canonical_sha256("relation-unit"),
        }
        base_span = {
            "line_number": 1,
            "character_span_start": 0,
            "character_span_end": len(line),
            "utf8_byte_span_start": 0,
            "utf8_byte_span_end": len(payload),
            "evidence_text": line,
            "surface_text": "첫말",
            "presented_definition_text": "첫 정의",
        }
        reversed_span = {**base_span, "surface_text": "첫 정의", "presented_definition_text": "첫말"}
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            contract._gold_spans([reversed_span], unit)

        long_definition = "가" * 513
        long_line = f"'s'은 {long_definition}를 뜻한다."
        long_payload = long_line.encode("utf-8")
        long_unit = {
            "payload_base64": base64.b64encode(long_payload).decode("ascii"),
            "payload_sha256": contract.raw_sha256(long_payload),
            "input_review_unit_sha256": contract.canonical_sha256("long-definition-unit"),
        }
        long_span = {
            "line_number": 1, "character_span_start": 0, "character_span_end": len(long_line),
            "utf8_byte_span_start": 0, "utf8_byte_span_end": len(long_payload),
            "evidence_text": long_line, "surface_text": "s", "presented_definition_text": long_definition,
        }
        self.assertEqual(len(contract._gold_spans([long_span], long_unit)), 1)

        lines = [f"'s{index}'은 d{index}를 뜻한다." for index in range(65)]
        document = "\n".join(lines)
        document_raw = document.encode("utf-8")
        many_unit = {
            "payload_base64": base64.b64encode(document_raw).decode("ascii"),
            "payload_sha256": contract.raw_sha256(document_raw),
            "input_review_unit_sha256": contract.canonical_sha256("65-span-unit"),
        }
        spans = []
        character_start = 0
        for index, evidence in enumerate(lines, start=1):
            character_end = character_start + len(evidence)
            spans.append(
                {
                    "line_number": index,
                    "character_span_start": character_start,
                    "character_span_end": character_end,
                    "utf8_byte_span_start": len(document[:character_start].encode("utf-8")),
                    "utf8_byte_span_end": len(document[:character_end].encode("utf-8")),
                    "evidence_text": evidence,
                    "surface_text": f"s{index - 1}",
                    "presented_definition_text": f"d{index - 1}",
                }
            )
            character_start = character_end + 1
        self.assertEqual(len(contract._gold_spans(spans, many_unit)), 65)

        overlong_document = "\n".join(["'a'은 b를 뜻한다."] * 5042)
        overlong_raw = overlong_document.encode("utf-8")
        self.assertGreater(len(overlong_document), 64 * 1024)
        self.assertLessEqual(len(overlong_raw), 256 * 1024)
        overlong_unit = {
            "payload_base64": base64.b64encode(overlong_raw).decode("ascii"),
            "payload_sha256": contract.raw_sha256(overlong_raw),
            "input_review_unit_sha256": contract.canonical_sha256("overlong-review-unit"),
        }
        with self.assertRaises(contract.P0PresentedNeutralReviewError):
            contract._gold_spans([], overlong_unit)
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            parent._gold([], overlong_unit)
        self.assertEqual(contract.MAX_GOLD_SPANS_PER_INPUT, 5041)
        self.assertEqual(
            contract.COMPONENT_MANIFEST["gold_span_capacity_policy"]["overlong_strict_utf8_payload_terminal"],
            "UNAVAILABLE_REQUIRED",
        )

    def test_fully_resealed_all_empty_judged_bundle_remains_presented_only(self) -> None:
        bundle = _review_bundle(all_empty=True)
        replay = _parent_validate(bundle)
        self.assertEqual(_object(bundle["review_receipt"])["judged_subset_presented_gold_span_count"], 0)
        self.assertFalse(replay["human_judgment_factuality_verified"])
        self.assertFalse(replay["gold_span_completeness_factuality_verified"])
        self.assertFalse(replay["exhaustive_human_review_verified"])
        self.assertEqual(replay["actual_human_review_count"], 0)

    def test_presented_core_error_input_is_retained_and_reviewable(self) -> None:
        upstream = _base_bundle()
        rows = _rows(upstream["results"])
        rows[0].update(
            {
                "terminal_disposition": "CORE_ERROR",
                "core_result": None,
                "core_result_sha256": None,
                "core_observations_sha256": None,
                "observation_count": 0,
                "core_error_stage": "CORE_EXECUTION",
                "core_error_code": "UNEXPECTED_CORE_EXCEPTION",
                "core_error_presented_only": True,
            }
        )
        rows[0] = _reseal(rows[0], "result_row_sha256")
        upstream["results"] = _jsonl(rows)
        upstream["receipt"] = _receipt_for_results(upstream, upstream["results"])
        upstream["unreviewed"] = _unreviewed_for(upstream, upstream["results"], upstream["receipt"])
        bundle = _review_bundle(upstream=upstream)
        unit = _rows(bundle["units"])[0]
        review = _rows(bundle["review_results"])[0]
        self.assertEqual(unit["parser_terminal_disposition"], "CORE_ERROR")
        self.assertEqual(review["annotation_status"], "JUDGED")
        self.assertEqual(_object(bundle["review_receipt"])["selected_input_itt_denominator"], 40)
        self.assertEqual(_parent_validate(bundle)["presented_terminal_input_count"], 40)

    def test_upstream_and_precommit_scalar_aliases_are_rejected(self) -> None:
        bridge = _rows(self.bundle["bridge"])
        bridge[0]["input_sequence"] = True
        bridge[0] = _reseal(bridge[0], "bridge_row_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "bridge": _jsonl(bridge)})

        batch_results = _rows(self.bundle["results"])
        batch_results[0]["attempt_count"] = True
        batch_results[0] = _reseal(batch_results[0], "result_row_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "results": _jsonl(batch_results)})

        precommit = _object(self.bundle["review_precommit"])
        precommit["reviewer_roster_row_count"] = True
        precommit = _reseal(precommit, "artifact_sha256")
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "review_precommit": _file(precommit)})

    def test_noncanonical_deep_json_invalid_time_and_semantic_injection_fail(self) -> None:
        nested = b'{"x":' + (b"[" * 5000) + b"0" + (b"]" * 5000) + b'}\n'
        for parser_call, error_type in (
            (lambda: contract._object(nested, "nested"), contract.P0PresentedNeutralReviewError),
            (lambda: parent._object(nested, "nested"), parent.P0PresentedNeutralReviewParentError),
            (lambda: contract._time("2026-02-31T00:00:00Z", "bad"), contract.P0PresentedNeutralReviewError),
            (lambda: parent._time("2026-02-31T00:00:00Z", "bad"), parent.P0PresentedNeutralReviewParentError),
        ):
            with self.assertRaises(error_type):
                parser_call()
        result_rows = _rows(self.bundle["review_results"])
        result_rows[0]["target_work_id"] = "ATTACKER:WORK"
        with self.assertRaises(parent.P0PresentedNeutralReviewParentError):
            _parent_validate({**self.bundle, "review_results": _jsonl(result_rows)})

    def test_manifest_is_exact_and_producer_monkeypatch_does_not_change_parent(self) -> None:
        self.assertEqual(contract.COMPONENT_MANIFEST_SHA256, parent.EXPECTED_COMPONENT_MANIFEST_SHA256)
        before = parent.EXPECTED_COMPONENT_MANIFEST_SHA256
        contract.COMPONENT_MANIFEST["actual_human_review_count"] = 40
        try:
            self.assertEqual(parent.EXPECTED_COMPONENT_MANIFEST_SHA256, before)
            self.assertEqual(_parent_validate(self.bundle)["actual_human_review_count"], 0)
        finally:
            contract.COMPONENT_MANIFEST["actual_human_review_count"] = 0

    def test_parent_imports_only_standard_library(self) -> None:
        tree = ast.parse(inspect.getsource(parent))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertFalse({"llm_batch", "p0_presented_neutral_review_accounting_v1_contract"}.intersection(roots))

    def test_existing_runtime_paths_and_packet_inventory_are_unchanged(self) -> None:
        self.assertEqual(len(packet_contract.CHILD_FILES), 13)
        runtime_files = (
            "p0_actual_route_contract.py",
            "p0_parser_process_protocol.py",
            "p0_parser_process_worker.py",
            "p0_windows_parser_process_sandbox.py",
            "p0_actual_packet_contract.py",
        )
        for filename in runtime_files:
            text = (SRC / "llm_batch" / "grounding" / filename).read_text(encoding="utf-8")
            self.assertNotIn("p0_presented_neutral_review_accounting", text)

    def test_authority_metrics_and_operational_effect_remain_false(self) -> None:
        manifest = contract.COMPONENT_MANIFEST
        self.assertEqual(manifest["metric_status"], "NOT_ESTIMABLE_PRESENTED_REVIEW_ONLY")
        self.assertEqual(manifest["actual_human_review_count"], 0)
        self.assertEqual(manifest["actual_human_unreviewed_input_count"], 40)
        for field in contract._FALSE_AUTHORITY_FIELDS:
            self.assertFalse(manifest[field])
        self.assertFalse(manifest["action_applied"])
        self.assertEqual(manifest["operational_effect"], "NONE_SHADOW_ONLY")


if __name__ == "__main__":
    unittest.main()
