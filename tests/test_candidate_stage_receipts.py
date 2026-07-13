from __future__ import annotations

import copy
import json
from types import SimpleNamespace
import unittest

from src.llm_batch.candidate_generation import (
    CANDIDATE_STAGE_RECEIPT_VERSION,
    CANDIDATE_STAGE_RULES,
    build_candidate_stage_receipt,
    candidate_stage_receipt_from_dict,
    candidate_stage_receipts_from_payload,
    record_candidate_stage_receipt,
)
from src.llm_batch.experts.decoder import DecoderExpert
from src.llm_batch.experts.gatekeeper import GatekeeperExpert
from src.llm_batch.experts.verifier import VerifierExpert


def source(index: int, *, title: str | None = None) -> dict:
    return {"title": title if title is not None else f"후보 {index:02d}"}


class CandidateStageReceiptContractTests(unittest.TestCase):
    def test_all_frozen_stages_detect_first_unique_loss(self):
        for (producer, stage), cap in CANDIDATE_STAGE_RULES.items():
            with self.subTest(producer=producer, stage=stage):
                at_cap = build_candidate_stage_receipt(
                    [source(index) for index in range(cap)],
                    producer=producer,
                    stage=stage,
                )
                past_cap = build_candidate_stage_receipt(
                    [source(index) for index in range(cap + 1)],
                    producer=producer,
                    stage=stage,
                )

                self.assertEqual(CANDIDATE_STAGE_RECEIPT_VERSION, at_cap.schema_version)
                self.assertEqual("UNKNOWN", at_cap.status)
                self.assertEqual(cap, at_cap.retained_source_count)
                self.assertEqual(cap, at_cap.emitted_source_count)
                self.assertEqual("TRUNCATED", past_cap.status)
                self.assertEqual(cap + 1, past_cap.unique_valid_source_count)
                self.assertEqual(cap, past_cap.emitted_source_count)
                self.assertIn(
                    "stage_local_candidate_inventory_truncated",
                    past_cap.reason_codes,
                )

    def test_duplicate_beyond_cap_does_not_create_false_unique_loss(self):
        cap = CANDIDATE_STAGE_RULES[("gatekeeper", "comment_title_candidates")]
        values = [source(index) for index in range(cap)]
        values.append({"official_title": "후보 00"})

        receipt = build_candidate_stage_receipt(
            values,
            producer="gatekeeper",
            stage="comment_title_candidates",
        )

        self.assertEqual("UNKNOWN", receipt.status)
        self.assertEqual(cap + 1, receipt.observed_source_count)
        self.assertEqual(cap, receipt.unique_valid_source_count)
        self.assertEqual(cap, receipt.emitted_source_count)

    def test_duplicate_inside_cap_that_displaces_unique_title_is_truncated(self):
        values = [source(0), source(0)] + [source(index) for index in range(1, 8)]

        receipt = build_candidate_stage_receipt(
            values,
            producer="gatekeeper",
            stage="comment_title_candidates",
        )

        self.assertEqual(9, receipt.observed_source_count)
        self.assertEqual(8, receipt.unique_valid_source_count)
        self.assertEqual(7, receipt.emitted_source_count)
        self.assertEqual("TRUNCATED", receipt.status)

    def test_invalid_rows_are_filtered_and_raw_titles_are_not_exposed(self):
        secret_title = "외부에 노출하지 않을 후보"
        receipt = build_candidate_stage_receipt(
            [None, 1, {}, {"title": ""}, secret_title],
            producer="decoder",
            stage="new_suspected_titles",
        )
        serialized = json.dumps(receipt.to_ledger_dict(), ensure_ascii=False)

        self.assertEqual(1, receipt.observed_source_count)
        self.assertEqual(1, receipt.unique_valid_source_count)
        self.assertNotIn(secret_title, serialized)

    def test_replay_is_exact_and_mutation_fails_closed(self):
        receipt = build_candidate_stage_receipt(
            [source(index) for index in range(6)],
            producer="verifier",
            stage="ranked_update",
        )
        payload = receipt.to_ledger_dict()

        replay = candidate_stage_receipt_from_dict(payload)
        self.assertEqual(payload, replay.to_ledger_dict())

        mutations = []
        for field_name, value in (
            ("status", "COMPLETE"),
            ("cap", 6),
            ("producer", "unknown"),
            ("metadata_fingerprint", "0" * 64),
        ):
            mutated = copy.deepcopy(payload)
            mutated[field_name] = value
            mutations.append((field_name, mutated))
        extra = copy.deepcopy(payload)
        extra["raw_titles"] = ["노출 금지"]
        mutations.append(("extra", extra))

        for label, mutated in mutations:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    candidate_stage_receipt_from_dict(mutated)

    def test_recorder_preserves_repeated_occurrences(self):
        ctx = SimpleNamespace(_candidate_generation_stage_receipts=[])
        first = record_candidate_stage_receipt(
            ctx,
            producer="arbiter",
            stage="candidate_merge",
            observed_sources=[source(index) for index in range(6)],
        )
        second = record_candidate_stage_receipt(
            ctx,
            producer="arbiter",
            stage="candidate_merge",
            observed_sources=[source(index) for index in range(5)],
        )
        receipts = candidate_stage_receipts_from_payload(
            ctx._candidate_generation_stage_receipts
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual((1, 2), tuple(item.occurrence for item in receipts))
        self.assertEqual(("TRUNCATED", "UNKNOWN"), tuple(item.status for item in receipts))

        duplicate = list(ctx._candidate_generation_stage_receipts)
        duplicate.append(copy.deepcopy(duplicate[0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            candidate_stage_receipts_from_payload(duplicate)

    def test_none_context_is_a_noop(self):
        self.assertIsNone(
            record_candidate_stage_receipt(
                None,
                producer="gatekeeper",
                stage="comment_title_candidates",
                observed_sources=[source(1)],
            )
        )


class CandidateStageReceiptExpertWiringTests(unittest.TestCase):
    def test_gatekeeper_records_all_deduped_comment_candidates_before_cap(self):
        gatekeeper = GatekeeperExpert.__new__(GatekeeperExpert)
        gatekeeper.emoji = "🎭"
        gatekeeper._looks_like_repeated_reaction_comment = lambda _value: False
        gatekeeper._is_title_like_surface = lambda _value: True
        gatekeeper._classify_comment_speech_act = lambda _value: "answer_like"
        ctx = SimpleNamespace(_candidate_generation_stage_receipts=[])
        comments = [f"댓글 후보 {index:02d}" for index in range(9)]

        result = gatekeeper._postprocess_comment_titles(
            {"detected_entities": {"possible_titles": ["본문 앵커"]}},
            {},
            comments,
            ctx=ctx,
        )
        receipt = candidate_stage_receipts_from_payload(
            ctx._candidate_generation_stage_receipts
        )[0]

        self.assertEqual(8, len(result["context_clues"]["comment_title_candidates"]))
        self.assertEqual("gatekeeper", receipt.producer)
        self.assertEqual("comment_title_candidates", receipt.stage)
        self.assertEqual(9, receipt.unique_valid_source_count)
        self.assertEqual("TRUNCATED", receipt.status)

    def test_decoder_empty_initialization_still_records_observed_boundary(self):
        decoder = DecoderExpert(llm_client=None)
        ctx = SimpleNamespace(
            expert_outputs={},
            post_data={"title": "", "content_blocks": []},
            comments=[],
            search_results=[],
            snippet_hints={},
            suspected_titles=[],
            _resolved_mappings=[],
            _candidate_generation_stage_receipts=[],
        )

        decoder._init_suspected_titles({"decoded_terms": []}, ctx)
        receipt = candidate_stage_receipts_from_payload(
            ctx._candidate_generation_stage_receipts
        )[0]

        self.assertEqual("decoder", receipt.producer)
        self.assertEqual("new_suspected_titles", receipt.stage)
        self.assertEqual(0, receipt.observed_source_count)
        self.assertEqual("UNKNOWN", receipt.status)
        self.assertEqual([], ctx.suspected_titles)

    def test_verifier_ranked_update_receipt_precedes_legacy_top_five(self):
        verifier = VerifierExpert(llm_client=None)
        ctx = SimpleNamespace(
            suspected_titles=[
                {"title": f"검증 후보 {index:02d}", "confidence": 0.9 - index / 100}
                for index in range(6)
            ],
            comments=[],
            search_results=[],
            expert_outputs={},
            _candidate_generation_stage_receipts=[],
        )

        verifier._update_suspected_titles(
            {"verification_result": {"is_relevant": False}},
            ctx,
        )
        receipt = candidate_stage_receipts_from_payload(
            ctx._candidate_generation_stage_receipts
        )[0]

        self.assertEqual(5, len(ctx.suspected_titles))
        self.assertEqual("verifier", receipt.producer)
        self.assertEqual("ranked_update", receipt.stage)
        self.assertEqual(6, receipt.unique_valid_source_count)
        self.assertEqual("TRUNCATED", receipt.status)

    def test_verifier_comment_boost_records_new_sixth_candidate_before_cap(self):
        verifier = VerifierExpert(llm_client=None)
        ctx = SimpleNamespace(
            suspected_titles=[
                {"title": f"기존 후보 {index:02d}", "confidence": 0.9 - index / 100}
                for index in range(5)
            ],
            comments=["새 작품?", "ㅇㅇ"],
            search_results=[{"title": "새 작품 상세", "content": "웹소설"}],
            _candidate_generation_stage_receipts=[],
        )

        verifier._boost_comment_confirmed_title(ctx)
        receipt = candidate_stage_receipts_from_payload(
            ctx._candidate_generation_stage_receipts
        )[0]

        self.assertEqual(5, len(ctx.suspected_titles))
        self.assertEqual("comment_boost", receipt.stage)
        self.assertEqual(6, receipt.unique_valid_source_count)
        self.assertEqual("TRUNCATED", receipt.status)


if __name__ == "__main__":
    unittest.main()
