"""R2 분모·ID 결속·운영 실패·선택 조건을 파일 단위로 검증한다."""
from copy import deepcopy
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from llm_batch.measurement.candidate_retrieval_evaluation import (
    MAPPING_SCHEMA, RetrievalEvaluationError, evaluate_candidate_retrieval, observation_from_saved_shadow,
)
from llm_batch.measurement.research_evaluation_snapshot import (
    REFERENCE_SCHEMA, build_evaluation_snapshot, semantic_hash,
)


def make_inputs(truths=("WORK", "WORK"), *, grades=None):
    grades = grades or ["MODEL_REFERENCE"] * len(truths)
    saved, reference_rows = [], []
    for index, truth in enumerate(truths, 1):
        coordinate = {"post_id": 100 + index, "input_index": index, "attempt_run_id": "run", "row_attempt_id": f"attempt-{index}", "publication_scope_id": "a" * 64}
        saved.append({"post_id": 100 + index, "title": "원문", "run_meta": {"run_id": "run", "decision_call_attempt_receipt": {"row": coordinate}}})
        reference_rows.append({"post_id": 100 + index, "input_index": index, "reference_kind": grades[index-1], "truth_kind": truth, "truth_candidate_id": f"reference-{index}" if truth == "WORK" else None, "expected_action": "RESOLVED" if truth == "WORK" else "NIL"})
    folder = Path.cwd() / "out" / "synthetic_evaluator_no_files"
    refs = {kind: {"path": str(folder / (kind + ".json")), "sha256": letter * 64, "bytes": 1} for kind, letter in (("result", "b"), ("manifest", "c"), ("reference", "d"))}
    dataset = {"dataset_id": "fixture", "sample_namespace": "synthetic", "data_kind": "SYNTHETIC_FIXTURE", "result": saved,
               "manifest": {"run_id": "run", "output_file": refs["result"]["path"], "input_post_count": len(saved), "flushed_count": len(saved), "publication_scope_id": "a" * 64},
               "reference": {"schema_version": REFERENCE_SCHEMA, "result_sha256": refs["result"]["sha256"], "run_id": "run", "rows": reference_rows}, "source_refs": refs}
    snapshot = build_evaluation_snapshot([dataset])
    corpus = {"corpus_sha256": "e" * 64, "data_kind": "SYNTHETIC_FIXTURE", "candidate_ids": [f"corpus-{i}" for i in range(1, 26)]}
    mapping = {"schema_version": MAPPING_SCHEMA, "snapshot_semantic_sha256": snapshot["semantic_sha256"], "corpus_sha256": corpus["corpus_sha256"], "source_ref": {"path": "fixture-explicit-mapping.json", "sha256": "f" * 64},
               "entries": [{"corpus_candidate_id": f"corpus-{i}", "candidate_option_ids": [f"option-{i}", f"mirror-{i}"], "reference_candidate_ids": [f"reference-{i}"]} for i in range(1, 26)]}
    observations = [{"dataset_id": row["dataset_id"], "coordinate": deepcopy(row["coordinate"]), "corpus_sha256": corpus["corpus_sha256"], "lanes": {"bm25": {"status": "COMPLETE", "id_space": "CORPUS", "ranked_candidate_ids": [f"corpus-{i}"]}, "baseline": {"status": "COMPLETE", "id_space": "CANDIDATE_OPTION", "ranked_candidate_ids": [f"option-{i}"]}}} for i, row in enumerate(snapshot["rows"], 1)]
    return snapshot, observations, corpus, mapping


def evaluate(values):
    snapshot, observations, corpus, mapping = values
    return evaluate_candidate_retrieval(snapshot, observations, corpus=corpus, id_mapping=mapping, lane_names=["bm25", "baseline"])


def metrics(result):
    return result["by_data_kind"]["SYNTHETIC_FIXTURE"]


def stored_receipt(values, *, status="OK"):
    row = values[0]["rows"][0]
    coordinate = row["coordinate"]
    receipt = {"schema_version": "candidate_retrieval_shadow_v1", "mode": "SHADOW", "status": status,
               "publication_authority": False, "central_db_write": False, "public_apply": False,
               "post_id": coordinate["post_id"], "corpus_sha256": values[2]["corpus_sha256"],
               "query_sha256": "1" * 64,
               "binding": {"run_id": coordinate["run_id"], "input_index": coordinate["input_index"], "post_id": coordinate["post_id"], "attempt_id": coordinate["row_attempt_id"], "publication_scope_id": "a" * 64},
               "policy": {"config": {"top_k": 20}}, "counts": {"positive_candidates": 1, "omitted_ranked_candidates": 0},
               "ranked_candidates": [{"corpus_candidate_id": "corpus-1", "score": 1.5}] if status == "OK" else []}
    row["saved_row"]["run_meta"]["candidate_retrieval_shadow"] = receipt
    return row, receipt


def reseal(values):
    values[0]["semantic_sha256"] = semantic_hash({key: value for key, value in values[0].items() if key != "semantic_sha256"})
    values[3]["snapshot_semantic_sha256"] = values[0]["semantic_sha256"]


class CandidateRetrievalEvaluationTests(unittest.TestCase):
    def test_helper_absence_remains_operational_miss_with_work_denominator(self):
        for missing in ("receipt", "row_attempt", "binding_attempt", "corpus_sha", "query_sha"):
            values = make_inputs(("WORK",))
            row = values[0]["rows"][0]
            if missing != "receipt":
                row, receipt = stored_receipt(values)
                if missing == "row_attempt":
                    row["coordinate"]["row_attempt_id"] = None
                elif missing == "binding_attempt":
                    receipt["binding"].pop("attempt_id")
                else:
                    receipt.pop("corpus_sha256" if missing == "corpus_sha" else "query_sha256")
            values[1][0] = observation_from_saved_shadow(row)
            reseal(values)
            result = evaluate(values)
            with self.subTest(missing=missing):
                self.assertEqual(result["status"], "COMPLETE_WITH_LIMITS")
                self.assertEqual(result["rows"][0]["binding_status"], "NOT_AVAILABLE")
                self.assertEqual(metrics(result)["judged_work_denominator"], 1)
                self.assertEqual(metrics(result)["lanes"]["bm25"]["recall"]["at_20"]["value"], 0)

    def test_known_wrong_corpus_is_invalid_even_when_attempt_missing(self):
        values = make_inputs(("WORK",))
        row, receipt = stored_receipt(values)
        receipt["binding"].pop("attempt_id")
        receipt["corpus_sha256"] = "0" * 64
        values[1][0] = observation_from_saved_shadow(row)
        reseal(values)
        self.assertEqual(evaluate(values)["status"], "INVALID_BINDING")

    def test_all_known_scope_carriers_checked_independently(self):
        for carrier in ("meta", "receipt_top", "ledger", "ledger_row", "cost_trace"):
            values = make_inputs(("WORK",))
            row, receipt = stored_receipt(values)
            meta = row["saved_row"]["run_meta"]
            meta["decision_call_attempt_receipt"]["row"].pop("publication_scope_id")
            if carrier == "meta":
                meta["publication_scope_id"] = "2" * 64
            elif carrier == "receipt_top":
                receipt["publication_scope_id"] = "2" * 64
            elif carrier == "ledger":
                meta["decision_call_ledger"] = {"publication_scope_id": "2" * 64}
            elif carrier == "ledger_row":
                meta["decision_call_ledger"] = {"row": {"publication_scope_id": "2" * 64}}
            else:
                meta["decision_cost_trace"] = {"publication_scope_id": "2" * 64}
            with self.subTest(carrier=carrier):
                self.assertEqual(observation_from_saved_shadow(row)["binding_status"], "INVALID_BINDING")

    def test_optional_observation_digest_ignores_latency_and_binding_only(self):
        values = make_inputs(("WORK",))
        row, receipt = stored_receipt(values)
        receipt["latency_ms"] = 0.1
        receipt["observation_sha256"] = semantic_hash({key: value for key, value in receipt.items() if key not in {"latency_ms", "binding", "observation_sha256"}})
        self.assertEqual(observation_from_saved_shadow(row)["binding_status"], "BOUND")
        receipt["latency_ms"] = 99
        self.assertEqual(observation_from_saved_shadow(row)["binding_status"], "BOUND")
        receipt["ranked_candidates"][0]["score"] = 5
        self.assertEqual(observation_from_saved_shadow(row)["reason_codes"], ["OBSERVATION_SHA_MISMATCH"])

    def test_query_fingerprint_must_be_lowercase_sha256(self):
        for invalid in ("not-a-hash", "A" * 64, 123, False):
            values = make_inputs(("WORK",))
            row, receipt = stored_receipt(values)
            receipt["query_sha256"] = invalid
            self.assertEqual(observation_from_saved_shadow(row)["reason_codes"], ["QUERY_SHA_INVALID"])

    def test_synthetic_corpus_cannot_supply_saved_actual_metrics(self):
        values = make_inputs()
        values[0]["rows"][0]["data_kind"] = "SAVED_ARTIFACT"
        reseal(values)
        with self.assertRaises(RetrievalEvaluationError):
            evaluate(values)
        values[2]["data_kind"] = "SOURCE_BACKED"
        result = evaluate(values)
        self.assertEqual(result["by_data_kind"]["SAVED_ARTIFACT"]["saved_observation_count"], 1)
        self.assertEqual(result["by_data_kind"]["SYNTHETIC_FIXTURE"]["saved_observation_count"], 1)

    def test_saved_shadow_adapter_binding_and_status_conversion(self):
        for status, expected in (("OK", "COMPLETE"), ("NO_MATCH", "EMPTY"), ("EMPTY_QUERY", "EMPTY"), ("EMPTY_CORPUS", "EMPTY"), ("RECEIPT_LIMIT_EXCEEDED", "RECEIPT_LIMIT_EXCEEDED")):
            values = make_inputs(("WORK",))
            row, receipt = stored_receipt(values, status=status)
            converted = observation_from_saved_shadow(row)
            self.assertEqual(converted["binding_status"], "BOUND")
            self.assertEqual(converted["lanes"]["bm25"]["status"], expected)
            values[1][0] = converted
            reseal(values)
            self.assertEqual(metrics(evaluate(values))["lanes"]["bm25"]["recall"]["at_1"]["value"], 1 if status == "OK" else 0)

    def test_saved_shadow_cannot_be_relabelled_complete_or_different_candidate(self):
        for mutation in ("status", "candidate"):
            values = make_inputs(("WORK",))
            row, receipt = stored_receipt(values, status="SCORING_LIMIT_EXCEEDED")
            converted = observation_from_saved_shadow(row)
            if mutation == "status":
                converted["lanes"]["bm25"]["status"] = "COMPLETE"
            else:
                converted["lanes"]["bm25"]["ranked_candidate_ids"] = ["corpus-1"]
            values[1][0] = converted
            reseal(values)
            self.assertEqual(evaluate(values)["status"], "INVALID_BINDING")

    def test_saved_shadow_rejects_known_row_authority_score_conflicts(self):
        for mutation in ("run_id", "input_index", "post_id", "attempt_id", "publication_scope_id", "authority", "score", "duplicate", "corpus_sha"):
            values = make_inputs(("WORK",))
            row, receipt = stored_receipt(values)
            if mutation in receipt["binding"]:
                receipt["binding"][mutation] = "foreign"
            elif mutation == "authority":
                receipt["central_db_write"] = True
            elif mutation == "score":
                receipt["ranked_candidates"][0]["score"] = float("nan")
            elif mutation == "duplicate":
                receipt["ranked_candidates"].append(deepcopy(receipt["ranked_candidates"][0]))
            else:
                receipt["corpus_sha256"] = "invalid"
            with self.subTest(mutation=mutation):
                self.assertEqual(observation_from_saved_shadow(row)["binding_status"], "INVALID_BINDING")

    def test_saved_shadow_missing_attempt_or_receipt_is_not_available(self):
        values = make_inputs(("WORK",))
        self.assertEqual(observation_from_saved_shadow(values[0]["rows"][0])["binding_status"], "NOT_AVAILABLE")
        row, receipt = stored_receipt(values)
        row["coordinate"]["row_attempt_id"] = None
        self.assertEqual(observation_from_saved_shadow(row)["reason_codes"], ["ROW_COORDINATE_NOT_AVAILABLE"])

    def test_saved_shadow_small_top_k_omission_is_incomplete(self):
        values = make_inputs(("WORK",))
        row, receipt = stored_receipt(values)
        receipt["policy"]["config"]["top_k"] = 5
        receipt["counts"]["positive_candidates"] = 30
        self.assertEqual(observation_from_saved_shadow(row)["lanes"]["bm25"]["status"], "INCOMPLETE")

    def test_common_work_denominator_and_nil_unjudged_separation(self):
        values = make_inputs(("WORK", "WORK", "NIL", "WORK"), grades=["MODEL_REFERENCE", "GOLD_LITE", "MODEL_REFERENCE", "UNJUDGED"])
        values[1][1]["lanes"]["bm25"]["ranked_candidate_ids"] = ["corpus-25", "corpus-2"]
        result = evaluate(values)
        counts = metrics(result)
        self.assertEqual(counts["judged_work_denominator"], 2)
        self.assertEqual(counts["reference_status_counts"], {"JUDGED_WORK": 2, "NIL": 1, "UNJUDGED": 1})
        self.assertEqual(counts["lanes"]["bm25"]["recall"]["at_1"]["value"], .5)
        for lane in counts["lanes"].values():
            self.assertTrue(all(metric["denominator"] == 2 for metric in lane["recall"].values()))
        self.assertEqual(counts["lanes"]["union"]["recall"]["at_1"]["value"], 1)
        self.assertEqual(result["formal_kpi_status"], "NOT_ESTIMABLE")
        self.assertFalse(result["publication_authority"])
        self.assertIn("SYNTHETIC_FIXTURE:MODEL_REFERENCE", result["by_reference_kind"])

    def test_unavailable_incomplete_missing_are_operational_misses(self):
        for status in ("UNAVAILABLE", "INCOMPLETE", "TRUNCATED", "ERROR", "NOT_AVAILABLE", "UNKNOWN", "OFF"):
            with self.subTest(status=status):
                values = make_inputs()
                values[1][0]["lanes"]["bm25"]["status"] = status
                values[1][1]["lanes"].pop("bm25")
                lane = metrics(evaluate(values))["lanes"]["bm25"]
                self.assertEqual(lane["recall"]["at_20"]["value"], 0)
                self.assertEqual(lane["recall"]["at_20"]["denominator"], 2)

    def test_union_credits_only_complete_lanes_and_is_not_fused_ranking(self):
        values = make_inputs()
        values[1][0]["lanes"]["bm25"]["status"] = "INCOMPLETE"
        values[1][0]["lanes"]["baseline"]["ranked_candidate_ids"] = ["option-25"]
        values[1][1]["lanes"]["bm25"]["ranked_candidate_ids"] = ["corpus-25"]
        self.assertEqual(metrics(evaluate(values))["lanes"]["union"]["recall"]["at_1"]["value"], .5)

    def test_recall_1_5_10_20_and_mirror_ids_do_not_consume_ranks(self):
        values = make_inputs(("WORK",))
        values[1][0]["lanes"]["baseline"]["ranked_candidate_ids"] = ["option-2", "mirror-2", "option-1"]
        values[1][0]["lanes"]["bm25"]["ranked_candidate_ids"] = [f"corpus-{i}" for i in range(2, 12)] + ["corpus-1"]
        result = metrics(evaluate(values))["lanes"]
        self.assertEqual([result["bm25"]["recall"][f"at_{k}"]["value"] for k in (1, 5, 10, 20)], [0, 0, 0, 1])
        self.assertEqual(result["baseline"]["recall"]["at_5"]["value"], 1)

    def test_missing_immutable_reference_mapping_is_not_title_matching(self):
        values = make_inputs()
        values[3]["entries"][0]["reference_candidate_ids"] = []
        result = metrics(evaluate(values))
        self.assertEqual(result["judged_work_denominator"], 2)
        self.assertEqual(result["reference_status_counts"]["UNMAPPED_WORK"], 1)
        self.assertIsNone(result["lanes"]["baseline"]["recall"]["at_1"]["value"])

    def test_ambiguous_id_mapping_and_binding_hashes_rejected(self):
        for mutation in ("ambiguous", "corpus", "snapshot", "schema"):
            values = make_inputs()
            if mutation == "ambiguous":
                values[3]["entries"][1]["reference_candidate_ids"] = ["reference-1"]
            elif mutation == "corpus":
                values[3]["corpus_sha256"] = "0" * 64
            elif mutation == "snapshot":
                values[3]["snapshot_semantic_sha256"] = "0" * 64
            else:
                values[3]["schema_version"] = "unknown"
            with self.subTest(mutation=mutation), self.assertRaises(RetrievalEvaluationError):
                evaluate(values)

    def test_observation_attempt_corpus_and_extra_rows_invalidate_metrics(self):
        for mutation in ("attempt", "run", "result", "index", "post", "corpus", "duplicate", "unknown_id"):
            values = make_inputs()
            if mutation == "corpus":
                values[1][0]["corpus_sha256"] = "0" * 64
            elif mutation == "duplicate":
                values[1].append(deepcopy(values[1][0]))
            elif mutation == "unknown_id":
                values[1][0]["lanes"]["bm25"]["ranked_candidate_ids"] = ["not-in-corpus"]
            else:
                field = {"attempt": "row_attempt_id", "run": "run_id", "result": "result_sha256", "index": "input_index", "post": "post_id"}[mutation]
                values[1][0]["coordinate"][field] = 999 if mutation in {"index", "post"} else "0" * 64
            result = evaluate(values)
            with self.subTest(mutation=mutation):
                self.assertEqual(result["status"], "INVALID_BINDING")
                self.assertIsNone(metrics(result)["lanes"]["bm25"]["recall"]["at_20"]["value"])

    def test_selection_conditions_keep_unavailable_in_operational_denominator(self):
        values = make_inputs(("WORK", "WORK", "WORK"))
        for i, row in enumerate(values[1], 1):
            row["selection"] = {"status": "COMPLETE" if i == 1 else "UNAVAILABLE", "id_space": "CANDIDATE_OPTION", "candidate_ids": ["option-25", f"option-{i}"], "ranked_candidate_ids": ["option-25", f"option-{i}"], "selected_candidate_id": f"option-{i}"}
        values[1][2]["selection"]["candidate_ids"] = ["option-25"]
        values[1][2]["selection"]["ranked_candidate_ids"] = []
        values[1][2]["selection"]["selected_candidate_id"] = None
        result = metrics(evaluate(values))["selection"]
        self.assertEqual(result["gold_present_denominator"], 2)
        self.assertEqual(result["complete_observation_denominator"], 1)
        self.assertEqual(result["operational_mrr"]["value"], .25)
        self.assertEqual(result["complete_only_mrr"]["value"], .5)
        self.assertEqual(result["operational_gold_present_accuracy"]["value"], .5)
        self.assertEqual(result["complete_only_gold_present_accuracy"]["value"], 1)

    def test_hold_and_unknown_expected_action_do_not_become_selection_errors(self):
        for action in ("HOLD", None):
            values = make_inputs(("WORK",))
            values[0]["rows"][0]["reference"]["payload"]["expected_action"] = action
            values[0]["semantic_sha256"] = semantic_hash({k: v for k, v in values[0].items() if k != "semantic_sha256"})
            values[3]["snapshot_semantic_sha256"] = values[0]["semantic_sha256"]
            values[1][0]["selection"] = {"status": "COMPLETE", "id_space": "CORPUS", "candidate_ids": ["corpus-1"], "ranked_candidate_ids": ["corpus-1"], "selected_candidate_id": "corpus-1"}
            result = metrics(evaluate(values))["selection"]
            self.assertEqual(result["gold_present_denominator"], 0)
            self.assertEqual(result["condition_status_counts"], {"ACTION_NOT_RESOLVE": 1})

    def test_selection_outside_pool_and_empty_with_prediction_rejected(self):
        for status, pool in (("COMPLETE", ["corpus-2"]), ("EMPTY", ["corpus-1"])):
            values = make_inputs(("WORK",))
            values[1][0]["selection"] = {"status": status, "id_space": "CORPUS", "candidate_ids": pool, "ranked_candidate_ids": ["corpus-1"], "selected_candidate_id": "corpus-1"}
            self.assertEqual(evaluate(values)["status"], "INVALID_BINDING")

    def test_invalid_snapshot_and_reference_are_not_nil(self):
        values = make_inputs()
        values[0]["binding_status"] = "INVALID_BINDING"
        values[0]["rows"][0]["reference"]["binding_status"] = "INVALID_BINDING"
        values[0]["semantic_sha256"] = semantic_hash({k: v for k, v in values[0].items() if k != "semantic_sha256"})
        values[3]["snapshot_semantic_sha256"] = values[0]["semantic_sha256"]
        result = evaluate(values)
        self.assertEqual(result["status"], "INVALID_BINDING")
        self.assertEqual(metrics(result)["reference_status_counts"]["INVALID_BINDING"], 1)

    def test_missing_observation_is_miss_not_removed(self):
        values = make_inputs()
        values[1].clear()
        result = metrics(evaluate(values))
        self.assertEqual(result["lanes"]["union"]["recall"]["at_1"]["value"], 0)
        self.assertEqual(result["judged_work_denominator"], 2)

    def test_snapshot_tampering_rejected(self):
        values = make_inputs()
        values[0]["rows"][0]["saved_row"]["title"] = "변조"
        with self.assertRaises(RetrievalEvaluationError):
            evaluate(values)

    def test_network_forbidden_deterministic_and_inputs_unchanged(self):
        values = make_inputs()
        original = deepcopy(values)
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            one, two = evaluate(values), evaluate(values)
        self.assertEqual(values, original)
        self.assertEqual(one["semantic_sha256"], two["semantic_sha256"])
        self.assertIsNone(one["independent_sample_count"])


if __name__ == "__main__":
    unittest.main()
