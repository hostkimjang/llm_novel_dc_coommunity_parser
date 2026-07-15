from __future__ import annotations

import copy
import unittest

from src.llm_batch.agentic_pipeline import AgenticPipeline
from src.llm_batch.grounding.candidate_generation import (
    CANDIDATE_GENERATION_VERSION,
    TITLE_CANDIDATE_GENERATION_VERSION,
    build_candidate_generation_snapshot,
    build_title_candidate_generation_snapshot,
    candidate_generation_snapshot_from_dict,
)
from src.llm_batch.domain.models import DetectedTitle


class DummyLLM:
    pass


class DummyMCP:
    pass


def source(
    index: int,
    *,
    title: str | None = None,
    url: str | None = None,
    role: str = "title_candidate",
) -> dict:
    return {
        "official_title": title if title is not None else f"작품 {index}",
        "heretic_url": url if url is not None else f"https://example.test/work/{index}",
        "preservation_role": role,
    }


class CandidateGenerationSnapshotTests(unittest.TestCase):
    def test_empty_and_invalid_sources_remain_unknown(self):
        snapshot = build_candidate_generation_snapshot(
            [None, "scalar", {}, {"official_title": ""}],
            cap=24,
        )

        self.assertEqual(CANDIDATE_GENERATION_VERSION, snapshot.schema_version)
        self.assertEqual("UNKNOWN", snapshot.status)
        self.assertEqual(0, snapshot.unique_valid_source_count)
        self.assertEqual(0, snapshot.emitted_source_count)
        self.assertEqual((), snapshot.retained_sources)
        self.assertIn("upstream_completeness_unknown", snapshot.reason_codes)

    def test_exactly_at_cap_is_unknown_and_never_complete(self):
        snapshot = build_candidate_generation_snapshot(
            [source(index) for index in range(24)],
            cap=24,
        )

        self.assertEqual("UNKNOWN", snapshot.status)
        self.assertEqual(24, snapshot.unique_valid_source_count)
        self.assertEqual(24, snapshot.emitted_source_count)
        self.assertNotIn("COMPLETE", snapshot.to_ledger_dict().values())

    def test_twenty_fifth_unique_source_is_detected_after_retention_cap(self):
        snapshot = build_candidate_generation_snapshot(
            [source(index) for index in range(25)],
            cap=24,
        )

        self.assertEqual("TRUNCATED", snapshot.status)
        self.assertEqual(25, snapshot.unique_valid_source_count)
        self.assertEqual(24, snapshot.emitted_source_count)
        self.assertEqual(24, len(snapshot.retained_sources))
        self.assertEqual("작품 23", snapshot.retained_sources[-1]["official_title"])
        self.assertIn("serializer_preservation_inventory_truncated", snapshot.reason_codes)

    def test_normalized_duplicate_does_not_create_false_truncation(self):
        values = [source(index) for index in range(23)]
        values.extend(
            [
                source(
                    23,
                    title="중복 작품",
                    url="https://EXAMPLE.test/work/dup/?utm_source=one",
                ),
                source(
                    24,
                    title="중복 작품",
                    url="https://example.test/work/dup",
                ),
            ]
        )

        snapshot = build_candidate_generation_snapshot(values, cap=24)

        self.assertEqual("UNKNOWN", snapshot.status)
        self.assertEqual(24, snapshot.unique_valid_source_count)
        self.assertEqual(24, snapshot.emitted_source_count)

    def test_same_title_url_with_different_role_is_distinct(self):
        snapshot = build_candidate_generation_snapshot(
            [
                source(1, title="역할 작품", url="https://example.test/role", role="title_candidate"),
                source(2, title="역할 작품", url="https://example.test/role", role="mentioned_work"),
            ],
            cap=24,
        )

        self.assertEqual(2, snapshot.unique_valid_source_count)
        self.assertEqual(2, snapshot.emitted_source_count)

    def test_invalid_cap_is_rejected_strictly(self):
        for cap in (0, -1, True, "24"):
            with self.subTest(cap=cap):
                with self.assertRaisesRegex(ValueError, "cap must be a positive int"):
                    build_candidate_generation_snapshot([], cap=cap)  # type: ignore[arg-type]

    def test_metadata_fingerprint_and_retained_sources_are_self_validating(self):
        snapshot = build_candidate_generation_snapshot([source(index) for index in range(25)], cap=24)
        payload = snapshot.to_ledger_dict()

        replay = candidate_generation_snapshot_from_dict(
            payload,
            retained_sources=list(snapshot.retained_sources),
        )
        self.assertEqual(payload, replay.to_ledger_dict())

        tampered = copy.deepcopy(payload)
        tampered["unique_valid_source_count"] = 26
        with self.assertRaisesRegex(ValueError, "metadata_fingerprint mismatch"):
            candidate_generation_snapshot_from_dict(tampered)

        wrong_sources = list(snapshot.retained_sources)
        wrong_sources[0] = source(999)
        with self.assertRaisesRegex(ValueError, "retained sources fingerprint mismatch"):
            candidate_generation_snapshot_from_dict(payload, retained_sources=wrong_sources)

    def test_complete_claim_is_rejected_by_v1_parser(self):
        snapshot = build_candidate_generation_snapshot([source(1)], cap=24)
        payload = snapshot.to_ledger_dict()
        payload["status"] = "COMPLETE"
        with self.assertRaisesRegex(ValueError, "status must be UNKNOWN or TRUNCATED"):
            candidate_generation_snapshot_from_dict(payload)

    def test_title_stage_seven_is_truncated_and_six_is_unknown(self):
        seven = build_title_candidate_generation_snapshot(
            [source(index, role="ranked_title_candidate") for index in range(7)],
            cap=6,
        )
        six = build_title_candidate_generation_snapshot(
            [source(index, role="ranked_title_candidate") for index in range(6)],
            cap=6,
        )

        self.assertEqual(TITLE_CANDIDATE_GENERATION_VERSION, seven.schema_version)
        self.assertEqual("title_candidate_ranked_inventory", seven.scope)
        self.assertEqual("TRUNCATED", seven.status)
        self.assertEqual(7, seven.unique_valid_source_count)
        self.assertEqual(6, seven.emitted_source_count)
        self.assertEqual("UNKNOWN", six.status)
        self.assertEqual(6, six.unique_valid_source_count)
        self.assertEqual(6, six.emitted_source_count)

    def test_title_stage_duplicate_does_not_create_false_truncation(self):
        values = [
            source(index, role="ranked_title_candidate")
            for index in range(6)
        ]
        values.append(copy.deepcopy(values[-1]))

        snapshot = build_title_candidate_generation_snapshot(values, cap=6)

        self.assertEqual("UNKNOWN", snapshot.status)
        self.assertEqual(6, snapshot.unique_valid_source_count)
        self.assertEqual(6, snapshot.emitted_source_count)
        replay = candidate_generation_snapshot_from_dict(
            snapshot.to_ledger_dict(),
            retained_sources=list(snapshot.retained_sources or ()),
        )
        self.assertEqual(snapshot.to_ledger_dict(), replay.to_ledger_dict())

    def test_title_stage_same_normalized_title_with_different_url_and_role_is_one(self):
        values = [
            source(
                1,
                title="같은 작품",
                url="https://example.test/work/first",
                role="ranked_title_candidate",
            ),
            source(
                2,
                title="같은   작품",
                url="https://example.test/work/second",
                role="alternate_ranked_title_candidate",
            ),
        ]

        snapshot = build_title_candidate_generation_snapshot(values, cap=6)

        self.assertEqual("UNKNOWN", snapshot.status)
        self.assertEqual(1, snapshot.unique_valid_source_count)
        self.assertEqual(1, snapshot.emitted_source_count)
        self.assertEqual(
            "https://example.test/work/first",
            snapshot.retained_sources[0]["heretic_url"],
        )
        replay = candidate_generation_snapshot_from_dict(
            snapshot.to_ledger_dict(),
            retained_sources=values,
        )
        self.assertEqual(snapshot.to_ledger_dict(), replay.to_ledger_dict())
        self.assertEqual(1, len(replay.retained_sources or ()))


class CandidateGenerationPipelineWiringTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = AgenticPipeline(
            llm=DummyLLM(),
            mcp=DummyMCP(),
            max_iterations=2,
        )

    def test_pipeline_scans_past_cap_but_preserves_legacy_emission_order(self):
        titles = [
            DetectedTitle(
                official_title=f"후보 {index:02d}",
                heretic_url=f"https://example.test/{index}",
            )
            for index in range(25)
        ]

        snapshot = self.pipeline._build_candidate_preservation_snapshot(
            title_candidates=titles,
            mentioned_works=None,
            comparison_target=None,
            recommendation_candidates=None,
            secondary_reference_works=None,
            max_items=24,
        )
        legacy = self.pipeline._build_candidate_preservation_sources(
            title_candidates=titles,
            mentioned_works=None,
            comparison_target=None,
            recommendation_candidates=None,
            secondary_reference_works=None,
            max_items=24,
        )

        self.assertEqual("TRUNCATED", snapshot.status)
        self.assertEqual(25, snapshot.unique_valid_source_count)
        self.assertEqual(24, snapshot.emitted_source_count)
        self.assertEqual(list(snapshot.retained_sources), legacy)
        self.assertEqual("후보 23", legacy[-1]["official_title"])

    def test_pipeline_rejects_zero_cap_instead_of_emitting_one_item(self):
        with self.assertRaisesRegex(ValueError, "cap must be a positive int"):
            self.pipeline._build_candidate_preservation_snapshot(
                title_candidates=[DetectedTitle(official_title="후보")],
                mentioned_works=None,
                comparison_target=None,
                recommendation_candidates=None,
                secondary_reference_works=None,
                max_items=0,
            )

    def test_title_stage_finalize_preserves_existing_top_six_order(self):
        scored = [
            (
                100 - index,
                index == 0,
                {
                    "title": f"상류 후보 {index:02d}",
                    "url": f"https://example.test/upstream/{index}",
                    "confidence": "High",
                    "alias": None,
                    "source_tier": "official_search",
                    "page_type": "detail",
                    "content_status": "active",
                    "locked": index == 0,
                    "negative_evidence": [],
                },
            )
            for index in range(7)
        ]

        emitted, snapshot = self.pipeline._finalize_title_candidate_generation(
            scored=scored,
            final_norm=self.pipeline._normalize_match_text("상류 후보 00"),
            max_items=6,
        )

        self.assertEqual("TRUNCATED", snapshot.status)
        self.assertEqual(7, snapshot.unique_valid_source_count)
        self.assertEqual(6, len(emitted))
        self.assertEqual(
            [f"상류 후보 {index:02d}" for index in range(6)],
            [item.official_title for item in emitted],
        )

    def test_title_stage_does_not_materialize_invalid_row_beyond_emission_cap(self):
        scored = [
            (
                100 - index,
                index == 0,
                {
                    "title": f"상류 후보 {index:02d}",
                    "url": f"https://example.test/upstream/{index}",
                    "confidence": "High",
                    "source_tier": (
                        "not_a_valid_detected_title_tier"
                        if index == 6
                        else "official_detail"
                    ),
                },
            )
            for index in range(7)
        ]

        emitted, snapshot = self.pipeline._finalize_title_candidate_generation(
            scored=scored,
            final_norm=self.pipeline._normalize_match_text("상류 후보 00"),
            max_items=6,
        )

        self.assertEqual(6, len(emitted))
        self.assertEqual("TRUNCATED", snapshot.status)
        self.assertEqual(7, snapshot.unique_valid_source_count)

    def test_title_stage_finalize_rejects_invalid_cap(self):
        for cap in (0, -1, True, 6.0, "6"):
            with self.subTest(cap=cap):
                with self.assertRaisesRegex(ValueError, "max_items must be a positive int"):
                    self.pipeline._finalize_title_candidate_generation(
                        scored=[],
                        final_norm="",
                        max_items=cap,  # type: ignore[arg-type]
                    )


if __name__ == "__main__":
    unittest.main()
