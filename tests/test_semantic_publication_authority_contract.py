from __future__ import annotations

from copy import deepcopy
import unittest

from src.llm_batch.agentic_pipeline import AgenticPipeline
from src.llm_batch.experts.orchestrator import ConversationContext, ExpertType
from src.llm_batch.ledger.publication_commit import (
    PublicationCommitError,
    build_publication_scope_id,
    compute_publication_decision_commit,
)
from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    SemanticPublicationState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
    grounding_state_from_dict,
)


class _Dummy:
    pass


def _state(
    semantic_publication: SemanticPublicationState | None = None,
) -> GroundingState:
    return GroundingState(
        post_id=901,
        candidate_title="현재 작품",
        candidate_url="https://novelpia.com/novel/901",
        source="semantic_authority_test",
        official_title_exists=True,
        row_discusses_work_as_work=True,
        title_resolution_state="resolved",
        work_resolution="resolved",
        discussion_type="review",
        scope=ScopeState(
            scope_kind="current_work",
            confidence="high",
            direct_bridge_sources=("body", "official_detail"),
        ),
        semantic_publication=semantic_publication,
    )


def _evidence() -> list[EvidenceRecord]:
    return [
        EvidenceRecord(
            kind="direct_current_work",
            strength="strong",
            source_path_or_snippet="https://novelpia.com/novel/901",
            supports_publish=True,
            reason_code="direct_current_work",
            candidate_title="현재 작품",
            candidate_url="https://novelpia.com/novel/901",
            title_url_match=True,
        )
    ]


def _result_from_contract(contract) -> dict:
    identity = {
        "is_relevant": True,
        "novel_identity": {
            "official_title": "현재 작품",
            "heretic_url": "https://novelpia.com/novel/901",
        },
    }
    apply_publish_contract(identity, contract)
    return {
        "post_id": 901,
        "title": "현재 작품 후기",
        "content": ["현재 작품 본문"],
        "comments": [],
        "analysis_result": {"identity": identity},
        "run_meta": {},
    }


class SemanticPublicationAuthorityContractTest(unittest.TestCase):
    def test_clean_current_work_direct_evidence_still_publishes(self) -> None:
        semantic = SemanticPublicationState(
            evidence_status="sufficient",
            media_domain_class="novel_work",
            primary_work_status="unique",
        )
        contract = evaluate_publish_contract(_state(semantic), _evidence())

        self.assertTrue(contract.decision.publish_allowed)
        self.assertEqual(contract.decision.official_title, "현재 작품")
        self.assertEqual(
            contract.decision.official_url,
            "https://novelpia.com/novel/901",
        )

    def test_explicit_semantic_blockers_hold_candidate_and_null_public_projection(self) -> None:
        cases = (
            (
                SemanticPublicationState(
                    evidence_status="conflict",
                    media_domain_class="novel_work",
                    primary_work_status="unique",
                ),
                "evidence_conflict",
            ),
            (
                SemanticPublicationState(
                    evidence_status="insufficient",
                    media_domain_class="novel_work",
                    primary_work_status="unique",
                ),
                "evidence_insufficient",
            ),
            (
                SemanticPublicationState(
                    evidence_status="sufficient",
                    media_domain_class="non_novel_media",
                    primary_work_status="unique",
                ),
                "non_novel_media",
            ),
            (
                SemanticPublicationState(
                    evidence_status="sufficient",
                    media_domain_class="novel_work",
                    primary_work_status="multiple",
                ),
                "multiple_primary_works",
            ),
            (
                SemanticPublicationState(
                    evidence_status="sufficient",
                    media_domain_class="novel_work",
                    primary_work_status="missing",
                ),
                "no_unique_primary_work",
            ),
            (
                SemanticPublicationState(
                    evidence_status="sufficient",
                    media_domain_class="novel_work",
                    primary_work_status="ambiguous",
                ),
                "primary_work_ambiguous",
            ),
        )
        for semantic, reason in cases:
            with self.subTest(reason=reason):
                contract = evaluate_publish_contract(_state(semantic), _evidence())
                identity = {
                    "official_title": "late revival",
                    "official_url": "https://novelpia.com/novel/999",
                    "novel_identity": {
                        "official_title": "late revival",
                        "heretic_url": "https://novelpia.com/novel/999",
                    },
                }
                apply_publish_contract(identity, contract)

                self.assertFalse(contract.decision.publish_allowed)
                self.assertTrue(contract.decision.candidate_preserved)
                self.assertIn(reason, contract.decision.reason_codes)
                self.assertIsNone(contract.decision.official_title)
                self.assertIsNone(contract.decision.official_url)
                self.assertIsNone(identity["official_title"])
                self.assertIsNone(identity["official_url"])
                self.assertIsNone(identity["novel_identity"]["official_title"])
                self.assertIsNone(identity["novel_identity"]["heretic_url"])
                self.assertEqual(identity["blocked_official_title"], "현재 작품")
                self.assertEqual(
                    identity["blocked_official_title_url"],
                    "https://novelpia.com/novel/901",
                )

    def test_default_semantic_state_serializes_away_and_keeps_v2_fingerprint(self) -> None:
        legacy = evaluate_publish_contract(_state(), _evidence())
        defaulted = evaluate_publish_contract(
            _state(SemanticPublicationState()),
            _evidence(),
        )

        self.assertNotIn("semantic_publication", defaulted.state.to_dict())
        self.assertEqual(legacy.state.to_dict(), defaulted.state.to_dict())
        self.assertEqual(legacy.input_fingerprint, defaulted.input_fingerprint)

    def test_semantic_state_roundtrips_as_authoritative_typed_input(self) -> None:
        original = _state(
            SemanticPublicationState(
                evidence_status="conflict",
                media_domain_class="novel_work",
                primary_work_status="unique",
            )
        )
        restored = grounding_state_from_dict(original.to_dict())

        self.assertEqual(restored, original)
        self.assertFalse(evaluate_publish_contract(restored, _evidence()).decision.publish_allowed)

    def test_agentic_builder_uses_structured_status_and_not_gallery_surface(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        ctx = ConversationContext(
            post_id=901,
            post_data={"post_id": 901, "title": "작품 갤러리 후기"},
            comments=[],
        )
        ctx.set_expert_output(
            ExpertType.DISCOURSE,
            {
                "discourse_analysis": {
                    "primary_domain": "novel_literature",
                    "domain_confidence": "high",
                }
            },
        )
        semantic = pipeline._derive_semantic_publication_state(
            ctx,
            _state(),
            _evidence(),
            final_decision={
                "evidence_status": "sufficient",
                "primary_work_status": "unique",
            },
            verification_result={},
            title_candidates=[],
        )

        self.assertEqual(semantic.evidence_status, "sufficient")
        self.assertEqual(semantic.media_domain_class, "novel_work")
        self.assertEqual(semantic.primary_work_status, "unique")
        self.assertFalse(semantic.blocks_publish())

    def test_agentic_builder_maps_structured_conflict_media_and_multiwork(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        ctx = ConversationContext(
            post_id=901,
            post_data={"post_id": 901, "title": "후기"},
            comments=[],
        )
        semantic = pipeline._derive_semantic_publication_state(
            ctx,
            _state(),
            _evidence(),
            final_decision={
                "consistency_flags": ["VLM_OCR_TITLE_CONFLICT_WITH_FINAL_TITLE"],
                "media_domain_class": "non_novel_media",
                "work_resolution": "multi_work",
            },
            verification_result={
                "relation_judgment": {
                    "discussion_target": "specific_work",
                    "promotion_decision": "allow",
                }
            },
            title_candidates=[],
        )

        self.assertEqual(semantic.evidence_status, "conflict")
        self.assertEqual(semantic.media_domain_class, "non_novel_media")
        self.assertEqual(semantic.primary_work_status, "multiple")
        self.assertEqual(
            set(semantic.derived_reason_codes()),
            {"evidence_conflict", "non_novel_media", "multiple_primary_works"},
        )

    def test_primary_title_without_url_matches_current_candidate_with_url(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        semantic = pipeline._derive_semantic_publication_state(
            None,
            _state(),
            _evidence(),
            final_decision={
                "evidence_status": "sufficient",
                "media_domain_class": "novel_work",
                "primary_work": {
                    "reference_role": "primary",
                    "official_title": "현재 작품",
                },
            },
            verification_result={},
            title_candidates=[],
        )

        self.assertEqual("unique", semantic.primary_work_status)
        self.assertFalse(semantic.blocks_publish())

    def test_different_primary_urls_override_explicit_unique_even_with_same_title(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        candidates = [
            {
                "reference_role": "primary",
                "official_title": "같은 표면 제목",
                "heretic_url": "https://novelpia.com/novel/1",
            },
            {
                "reference_role": "primary",
                "official_title": "같은 표면 제목",
            },
            {
                "reference_role": "primary",
                "official_title": "같은 표면 제목",
                "heretic_url": "https://novelpia.com/novel/2",
            },
        ]
        semantic = pipeline._derive_semantic_publication_state(
            None,
            _state(),
            _evidence(),
            final_decision={
                "evidence_status": "sufficient",
                "media_domain_class": "novel_work",
                "primary_work_status": "unique",
                "primary_works": candidates,
            },
            verification_result={},
            title_candidates=[],
        )

        self.assertEqual("multiple", semantic.primary_work_status)
        self.assertIn("multiple_primary_works", semantic.derived_reason_codes())

    def test_cross_source_semantic_disagreement_fails_closed(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        semantic = pipeline._derive_semantic_publication_state(
            None,
            _state(),
            _evidence(),
            final_decision={
                "evidence_status": "sufficient",
                "media_domain_class": "novel_work",
                "primary_work_status": "unique",
            },
            verification_result={
                "evidence_status": "insufficient",
                "media_domain_class": "non_novel_media",
                "primary_work_status": "unique",
            },
            title_candidates=[],
        )

        self.assertEqual("conflict", semantic.evidence_status)
        self.assertEqual("cross_media_unresolved", semantic.media_domain_class)
        self.assertTrue(semantic.blocks_publish())

    def test_canonical_binding_can_match_verified_precanonical_primary_title(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        semantic = pipeline._derive_semantic_publication_state(
            None,
            _state(),
            _evidence(),
            final_decision={
                "evidence_status": "sufficient",
                "media_domain_class": "novel_work",
                "primary_work": {
                    "reference_role": "primary",
                    "official_title": "검증된 이전 표면",
                },
            },
            verification_result={},
            title_candidates=[],
            equivalent_candidate_titles=("검증된 이전 표면",),
        )

        self.assertEqual("unique", semantic.primary_work_status)

    def test_existing_semantic_blocker_survives_later_allow_state(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        pipeline._official_detail_display_title_binding = lambda *args, **kwargs: {
            "status": "unavailable",
            "canonical_title": "",
        }
        ctx = ConversationContext(
            post_id=901,
            post_data={"post_id": 901, "title": "현재 작품 후기"},
            comments=[],
        )
        decision = pipeline._record_public_title_gate_decision(
            ctx,
            _state(
                SemanticPublicationState(
                    evidence_status="conflict",
                    media_domain_class="novel_work",
                    primary_work_status="unique",
                )
            ),
            _evidence(),
            final_decision={
                "evidence_status": "sufficient",
                "media_domain_class": "novel_work",
                "primary_work_status": "unique",
            },
            verification_result={},
            title_candidates=[],
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertEqual(
            "conflict",
            ctx._last_promotion_gate_state["semantic_publication"]["evidence_status"],
        )

    def test_official_detail_binding_mismatch_is_sealed_as_semantic_conflict(self) -> None:
        pipeline = AgenticPipeline(llm=_Dummy(), mcp=_Dummy(), max_iterations=1)
        pipeline._official_detail_display_title_binding = lambda *args, **kwargs: {
            "status": "mismatch",
            "canonical_title": "다른 작품",
            "reason_code": "official_detail_display_title_mismatch",
        }
        ctx = ConversationContext(
            post_id=901,
            post_data={"post_id": 901, "title": "현재 작품 후기"},
            comments=[],
        )
        decision = pipeline._record_public_title_gate_decision(
            ctx,
            _state(),
            _evidence(),
            final_decision={
                "evidence_status": "sufficient",
                "media_domain_class": "novel_work",
                "primary_work_status": "unique",
            },
            verification_result={},
            title_candidates=[],
        )

        self.assertFalse(decision["publish_allowed"])
        self.assertIn("evidence_conflict", decision["reason_codes"])
        self.assertEqual(
            "conflict",
            ctx._last_promotion_gate_state["semantic_publication"]["evidence_status"],
        )

    def test_publication_wal_recompute_rejects_semantic_state_tamper(self) -> None:
        publish_contract = evaluate_publish_contract(
            _state(
                SemanticPublicationState(
                    evidence_status="sufficient",
                    media_domain_class="novel_work",
                    primary_work_status="unique",
                )
            ),
            _evidence(),
        )
        result = _result_from_contract(publish_contract)
        scope_id = build_publication_scope_id(
            input_file_sha256="a" * 64,
            post_ids=[901],
            config_hash="semantic-authority-test",
        )
        compute_publication_decision_commit(
            result,
            publication_scope_id=scope_id,
            attempt_run_id="attempt-clean",
            input_index=1,
            post_id=901,
        )

        tampered = deepcopy(result)
        identity = tampered["analysis_result"]["identity"]
        forged_state = deepcopy(identity["promotion_gate_state"])
        forged_state["semantic_publication"]["evidence_status"] = "conflict"
        identity["promotion_gate_state"] = forged_state
        identity["candidate_ledger"]["promotion_gate_state"] = deepcopy(forged_state)

        with self.assertRaisesRegex(
            PublicationCommitError,
            "recompute does not match decision",
        ):
            compute_publication_decision_commit(
                tampered,
                publication_scope_id=scope_id,
                attempt_run_id="attempt-tampered",
                input_index=1,
                post_id=901,
            )


if __name__ == "__main__":
    unittest.main()
