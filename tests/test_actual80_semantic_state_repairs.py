"""저장 전문가 관측을 실제 serializer에 공급하는 국소 회귀. 새 추론/검색은 없다."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import DetectedTitle, PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType
from llm_batch.ledger.publication_commit import compute_publication_decision_commit

FIXTURE = Path(__file__).parent / "fixtures/actual80_semantic_state_evidence.json"


class NoExternalIO:
    def fetch(self, *args, **kwargs):
        raise AssertionError("NEW_EXTERNAL_FETCH_FORBIDDEN")

    def search(self, *args, **kwargs):
        raise AssertionError("NEW_EXTERNAL_SEARCH_FORBIDDEN")


def context_for(index, *, title=None, body=None):
    record = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8"))["records"][str(index)])
    raw = record["post"]
    if title is not None:
        raw["title"] = title
    if body is not None:
        raw["content_blocks"] = [{"type": "text", "text": text} for text in body]
    post = PostInput(**raw, comments=record["comments"])
    pipe = AgenticPipeline(llm=object(), mcp=NoExternalIO(), max_iterations=1)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post), comments=post.comments)
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    for name, payload in record["experts"].items():
        ctx.set_expert_output(ExpertType(name), copy.deepcopy(payload))
    discourse = (record["experts"].get("discourse") or {}).get("discourse_analysis") or {}
    ctx.primary_domain = discourse.get("primary_domain")
    ctx.discourse_intent = discourse.get("intent")
    return pipe, ctx, record


class ActualSemanticStateTests(unittest.TestCase):
    def serialize(self, pipe, ctx):
        before = copy.deepcopy(ctx.post_data)
        result = pipe._context_to_output(ctx)
        payload = result.model_dump(mode="json")
        self.assertEqual(ctx.post_data, before)
        checked = pipe.verify_final_source_context_serialization(result, payload, stage="regression_saved_json")
        self.assertIsInstance(checked, dict)
        self.assertIsNone(payload["identity"]["novel_identity"])
        self.assertFalse(payload["identity"]["title_resolution_allowed"])
        commit = compute_publication_decision_commit(
            payload, publication_scope_id=hashlib.sha256(b"semantic-state-regression").hexdigest(), attempt_run_id="saved-experts",
            input_index=1, post_id=ctx.post_id,
        )
        self.assertEqual(commit.outcome, "HOLD")
        self.assertFalse(commit.publish_allowed)
        return result, payload

    def test_saved_non_novel_comic_without_arbiter_has_nsfw_in_final_serializer(self):
        pipe, ctx, record = context_for(16)
        self.assertNotIn("arbiter", record["experts"])
        self.assertIn("비-소설", ctx.get_expert_output(ExpertType.GATEKEEPER)["noise_reason"])
        self.assertFalse(record["stored_analysis"]["is_nsfw"])
        _, saved = self.serialize(pipe, ctx)
        self.assertIs(saved["analysis"]["is_nsfw"], True)

    def test_non_novel_spelling_variants_preserve_same_nsfw_evidence(self):
        for spelling in ("비소설", "비-소설", "비 소설", "비–소설"):
            with self.subTest(spelling=spelling):
                pipe, ctx, _ = context_for(16)
                gate = ctx.get_expert_output(ExpertType.GATEKEEPER)
                gate["noise_reason"] = gate["noise_reason"].replace("비-소설", spelling)
                self.assertTrue(pipe._fallback_explicit_nsfw_from_post(ctx))

    def test_nsfw_requires_positive_authored_comic_evidence(self):
        cases = (
            ("히토미 안 꼴리네", ["연상여친 만화인데 안 꼴리네"]),
            ("히토미 씹꼴리는거 나왔네", ["만화 스토리는 꼴리지 않음"]),
            ("히토미 씹꼴리는거 나왔네", ["원작 소설을 만화화한 스토리가 꼴리네"]),
            ("히토미 씹꼴리는거 나왔네", ["이 소설은 만화처럼 전개가 꼴리네"]),
            ("새 게임 나왔네", ["만화 같은 액션 전투가 꼴리네"]),
            ("히토미 이야기", ["오늘은 날씨가 좋다"]),
        )
        for title, body in cases:
            with self.subTest(title=title, body=body):
                pipe, ctx, _ = context_for(16, title=title, body=body)
                ctx.comments = ["히토미 만화가 꼴리네"]
                ctx.search_results = [{"title": "히토미", "content": "성인 만화가 꼴리네"}]
                self.assertFalse(pipe._fallback_explicit_nsfw_from_post(ctx))

    def test_explicit_metadata_false_still_owns_nsfw_value(self):
        pipe, ctx, _ = context_for(16)
        ctx.set_expert_output(ExpertType.ARBITER, {
            "final_decision": {"is_relevant": False, "discussion_type": "noise"},
            "metadata_synthesis": {"is_nsfw": False},
        })
        _, saved = self.serialize(pipe, ctx)
        self.assertFalse(saved["analysis"]["is_nsfw"])

    def test_saved_trope_final_classification_updates_identity_state_and_seal(self):
        pipe, ctx, record = context_for(70)
        self.assertEqual(record["stored_identity"]["identity_state"], "non_relevant")
        result, saved = self.serialize(pipe, ctx)
        ident = saved["identity"]
        self.assertEqual(ident["topicality"], "adjacent_relevant")
        self.assertEqual(ident["identity_state"], "adjacent_relevant")
        self.assertEqual(ident["relevance_scope"], "adjacent")
        self.assertIs(ident["is_novel_related"], True)
        self.assertIn("빌런하고 주인공", ident["reason"])
        # A stale state cannot be smuggled into the same final-source receipt.
        result.identity.identity_state = "non_relevant"
        with self.assertRaises(ValueError):
            pipe.verify_final_source_context_serialization(result, result.model_dump(mode="json"), stage="state_tamper")

    def test_trope_source_routing_invalidates_the_old_preclassification_state(self):
        pipe, ctx, _ = context_for(70)
        from llm_batch.domain.models import PickvelIdentity
        # The observed old identity_state was derived from unrelated taxonomy
        # before this same original-source correction. Exercise that boundary
        # directly as well as the complete serializer above.
        identity = PickvelIdentity(is_relevant=False, discussion_type="noise", topicality="unrelated",
            relevance_scope="off_topic", is_novel_related=False, identity_state="non_relevant")
        _, verify = pipe._consume_final_source_context(ctx, identity, None)
        self.assertEqual(identity.topicality, "adjacent_relevant")
        self.assertEqual(identity.identity_state, "adjacent_relevant")
        self.assertTrue(verify())
        identity.identity_state = "non_relevant"
        self.assertFalse(verify())

    def test_saved_coordinated_webtoon_novel_opinion_keeps_both_and_stays_unpublished(self):
        pipe, ctx, record = context_for(17)
        self.assertFalse(record["stored_identity"]["is_novel_related"])
        _, saved = self.serialize(pipe, ctx)
        ident = saved["identity"]
        self.assertTrue(ident["is_novel_related"])
        self.assertEqual(ident["topicality"], "adjacent_relevant")
        self.assertEqual(ident["identity_state"], "adjacent_relevant")
        self.assertIn("웹툰·소설", ident["reason"])
        self.assertEqual(ident["work_resolution"], "none")
        self.assertFalse(ident["is_resolved_work_discussion"])

    def test_coordinated_source_not_expert_primary_order_controls_broad_relevance(self):
        pipe, ctx, _ = context_for(17)
        discourse = ctx.get_expert_output(ExpertType.DISCOURSE)["discourse_analysis"]
        discourse["primary_domain"] = "novel_literature"
        discourse["secondary_domains"] = ["manga_comics"]
        ctx.primary_domain = "novel_literature"
        _, saved = self.serialize(pipe, ctx)
        self.assertTrue(saved["identity"]["is_novel_related"])
        self.assertEqual(saved["identity"]["identity_state"], "adjacent_relevant")

    def test_coordinated_source_excludes_other_media_report_and_denial(self):
        for title in ("만화도 영화도 볼만한게 없네", "소설이 아니라 만화 얘기임",
                      '친구가 "웹툰도 소설도 빡오는게 없구나"라고 했다',
                      "웹툰도 소설도 빡오는게 없구나라고 말할 예정"):
            with self.subTest(title=title):
                pipe, ctx, _ = context_for(17, title=title)
                from llm_batch.domain.models import PickvelIdentity
                identity = PickvelIdentity(is_relevant=False, discussion_type="general", topicality="unrelated",
                    relevance_scope="off_topic", is_novel_related=False, identity_state="non_relevant")
                _, verify = pipe._consume_final_source_context(ctx, identity, None)
                # Intentionally retain the old expert secondary-domain claim;
                # it cannot replace the missing current-authored source proof.
                self.assertFalse(identity.is_novel_related)
                self.assertEqual(identity.identity_state, "non_relevant")
                self.assertTrue(verify())

    def test_unchanged_taxonomy_keeps_technical_failure_state(self):
        pipe, ctx, _ = context_for(17, title="오늘 날씨 얘기", body=["날이 흐리네"])
        from llm_batch.domain.models import PickvelIdentity
        identity = PickvelIdentity(is_relevant=False, discussion_type="general", topicality="unrelated",
                                   relevance_scope="off_topic", identity_state="technical_inconclusive")
        _, verify = pipe._consume_final_source_context(ctx, identity, None)
        self.assertEqual(identity.identity_state, "technical_inconclusive")
        self.assertTrue(verify())

    def test_blocked_nonwork_alias_remains_diagnostic_not_recommendation(self):
        pipe, ctx, record = context_for(77)
        self.assert_blocked_nonwork_alias_preservation(pipe, ctx, record)

    def test_decoder_mapping_cannot_restore_a_blocked_nonwork_alias(self):
        pipe, ctx, record = context_for(77)
        candidate = record["stored_identity"]["recommendation_candidates"][0]
        original_post = copy.deepcopy(ctx.post_data)
        decoder = {"decoded_terms": [{"original": candidate["alias_or_mention"],
            "best_match": {"title": candidate["official_title"], "confidence": "none"}}]}
        ctx.set_expert_output(ExpertType.DECODER, copy.deepcopy(decoder))
        # This inference used to satisfy the new source exception by itself.
        self.assertTrue(pipe._title_mentioned_in_post_main_context(ctx, candidate["official_title"]))
        self.assertFalse(pipe._full_title_mentioned_in_raw_post_context(
            ctx, candidate["official_title"], include_comments=False))
        self.assert_blocked_nonwork_alias_preservation(pipe, ctx, record)
        self.assertEqual(ctx.post_data, original_post)
        self.assertEqual(ctx.get_expert_output(ExpertType.DECODER), decoder)

    def assert_blocked_nonwork_alias_preservation(self, pipe, ctx, record):
        stored = record["stored_identity"]["recommendation_candidates"]
        self.assertEqual(len(stored), 1)
        rejected = DetectedTitle(**stored[0])
        self.assertIn("batch_alias_nonwork_context_hold_without_promotion", rejected.negative_evidence)
        self.assertFalse(pipe._local_hold_has_work_role(ctx, rejected))
        ctx._batch_alias_rescue_blocked_nonwork_context_title = rejected.official_title
        ctx._batch_alias_rescue_blocked_nonwork_context_alias = rejected.alias_or_mention
        ctx._batch_alias_rescue_blocked_nonwork_context_url = rejected.heretic_url
        ctx._batch_alias_rescue_blocked_nonwork_context_source = "search_evidence_alias_inference"
        ctx._batch_alias_rescue_blocked_nonwork_context_reason = "genre_discussion_nonwork_context"
        other = DetectedTitle(official_title="원문에서 독립적으로 추천한 작품", reference_role="candidate")
        extended = {}
        merged = pipe._merge_local_candidate_preservation_hints(
            ctx=ctx, discussion_type="trope_discussion", recommendation_candidates=[other],
            extended_identity=extended, official_title=None,
        )
        self.assertIn(other, merged)
        self.assertNotIn(rejected.official_title, [x.official_title for x in merged])
        diagnostics = extended["_local_surface_diagnostic_holds"]
        self.assertTrue(any(x.official_title == rejected.official_title for x in diagnostics))
        snap = pipe._build_candidate_preservation_snapshot(title_candidates=[], mentioned_works=[],
            comparison_target=None, recommendation_candidates=merged, local_diagnostic_sources=diagnostics)
        kept = [x for x in snap.retained_sources if x.get("official_title") == rejected.official_title]
        self.assertTrue(kept)
        self.assertTrue(all(x["promotion_policy"] == "hold_without_promotion" for x in kept))

    def test_independent_authored_title_relation_is_not_blocked_by_old_alias_marker(self):
        pipe, ctx, record = context_for(77)
        candidate = DetectedTitle(**record["stored_identity"]["recommendation_candidates"][0])
        pipe, ctx, _ = context_for(77, body=[f"소설 {candidate.official_title} 읽었는데 추천함"])
        self.assertTrue(pipe._local_hold_has_work_role(ctx, candidate))

    def test_independent_authored_alias_work_relation_remains_eligible(self):
        pipe, ctx, record = context_for(77, title="빛기사는 재밌다", body=[])
        candidate = DetectedTitle(**record["stored_identity"]["recommendation_candidates"][0])
        candidate.alias_or_mention = "빛기사"
        self.assertFalse(pipe._full_title_mentioned_in_raw_post_context(
            ctx, candidate.official_title, include_comments=False))
        self.assertTrue(pipe._search_inferred_alias_has_explicit_context_anchor(
            ctx, candidate.alias_or_mention, require_work_relation=True, work_title=candidate.official_title))
        self.assertTrue(pipe._local_hold_has_work_role(ctx, candidate))

    def test_abbreviation_explanation_is_diagnostic_not_ranked_title(self):
        pipe, ctx, record = context_for(35)
        self.assert_abbreviation_explanation_preservation(pipe, ctx, record)

    def test_decoder_best_match_cannot_turn_its_own_explanation_into_a_title(self):
        pipe, ctx, record = context_for(35)
        gloss = "회귀/빙의/모험/장르 등의 약칭 가능성"
        original_post = copy.deepcopy(ctx.post_data)
        term = next(t for t in ctx.get_expert_output(ExpertType.DECODER)["decoded_terms"]
                    if t["original"] == "회모장")
        term["best_match"] = {"title": gloss, "confidence": "none"}
        self.assertTrue(pipe._title_mentioned_in_post_main_context(ctx, gloss))
        self.assertFalse(pipe._full_title_mentioned_in_raw_post_context(ctx, gloss, include_comments=False))
        self.assertTrue(pipe._is_unbound_title_meta_explanation(ctx, gloss))
        self.assert_abbreviation_explanation_preservation(pipe, ctx, record)
        self.assertEqual(ctx.post_data, original_post)

    def assert_abbreviation_explanation_preservation(self, pipe, ctx, record,
            gloss="회귀/빙의/모험/장르 등의 약칭 가능성"):
        before = copy.deepcopy(ctx.get_expert_output(ExpertType.DECODER))
        self.assertIn(gloss, json.dumps(before, ensure_ascii=False))
        from llm_batch.experts.decoder import DecoderExpert
        DecoderExpert(object())._init_suspected_titles(ctx.get_expert_output(ExpertType.DECODER), ctx)
        self.assertFalse(any(x["title"] == gloss for x in ctx.suspected_titles))
        titles, snapshot = pipe._build_title_candidates_with_snapshot(
            ctx=ctx, is_relevant=record["stored_identity"]["is_relevant"], official_title=None, heretic_url=None, confidence="Low",
            vf_result=(ctx.get_expert_output(ExpertType.VERIFIER) or {}).get("verification_result") or {},
        )
        self.assertNotIn(gloss, [x.official_title for x in titles])
        self.assertFalse(any(x.get("official_title") == gloss for x in snapshot.retained_sources))
        self.assertTrue(any(x["text"] == gloss for x in ctx._title_meta_explanation_observations))
        self.assertEqual(ctx.get_expert_output(ExpertType.DECODER), before)
        self.assertIn("회모장", json.dumps(before, ensure_ascii=False))
        _, saved = self.serialize(pipe, ctx)
        self.assertNotIn(gloss, [x["official_title"] for x in saved["identity"].get("title_candidates") or []])
        self.assertNotIn(gloss, [x["official_title"] for x in (saved["analysis"] or {}).get("detected_titles") or []])
        self.assertTrue(any(x["text"] == gloss for x in
            saved["identity"]["candidate_ledger"]["title_meta_explanation_observations"]))

    def test_meta_wording_is_not_a_title_blacklist(self):
        pipe, ctx, _ = context_for(35, title="다른 작품을 읽었다", body=[])
        self.assertTrue(pipe._is_unbound_title_meta_explanation(ctx, "여러 장르 등의 약자 추정"))
        self.assertFalse(pipe._is_unbound_title_meta_explanation(ctx, "아카데미 생존 갤러리"))
        self.assertFalse(pipe._is_unbound_title_meta_explanation(ctx, "약칭으로 살아남기"))
        ctx.comments = ["여러 장르 등의 약자 추정"]
        ctx.post_data["content_blocks"] = [{"type": "ocr_text", "text": "여러 장르 등의 약자 추정"}]
        self.assertTrue(pipe._is_unbound_title_meta_explanation(ctx, "여러 장르 등의 약자 추정"))
        pipe, ctx, _ = context_for(35, title="다른 작품을 읽었다",
                                  body=["소설 '여러 장르 등의 약자 추정'을 읽었다"])
        self.assertFalse(pipe._is_unbound_title_meta_explanation(ctx, "여러 장르 등의 약자 추정"))

    def test_partial_or_scattered_meta_title_is_not_a_literal_exception(self):
        gloss = "여러 장르 등의 약자 추정"
        for body in (["여러 장르 등의 약자"],
                     ["여러 장르. 등의 약자. 추정."],
                     ["여러 장르 등의", "약자 추정"]):
            with self.subTest(body=body):
                pipe, ctx, record = context_for(35, title="다른 작품을 읽었다", body=body)
                self.assertTrue(pipe._full_title_mentioned_in_raw_post_context(ctx, gloss, include_comments=False))
                self.assertFalse(pipe._has_literal_author_title_occurrence(ctx, gloss))
                decoder = ctx.get_expert_output(ExpertType.DECODER)
                term = next(t for t in decoder["decoded_terms"] if t["original"] == "회모장")
                # Explicit synthetic expert candidate, consumed by the real
                # Decoder producer; confidence cannot replace a full source span.
                term["original"] = "여러 장르 등의 약자"
                term["best_match"] = {"title": gloss, "confidence": "medium"}
                term["candidates"] = [{"official_title": gloss, "morphological_score": 0.55}]
                term["interpretations"][0]["value"] = gloss
                self.assert_abbreviation_explanation_preservation(pipe, ctx, record, gloss)

    def test_blocked_work_cannot_use_a_fuzzy_full_title_exception(self):
        full_title = "별빛 기사의 마지막 귀환 기록"
        for body in (["별빛 기사의 마지막 귀환"], ["별빛 기사의. 마지막 귀환 기록."]):
            with self.subTest(body=body):
                pipe, ctx, record = context_for(77, title="오늘 본 단어", body=body)
                candidate = DetectedTitle(**record["stored_identity"]["recommendation_candidates"][0])
                candidate.official_title, candidate.alias_or_mention = full_title, "별기"
                self.assertTrue(pipe._full_title_mentioned_in_raw_post_context(ctx, full_title, include_comments=False))
                self.assertFalse(pipe._local_hold_has_work_role(ctx, candidate))
        pipe, ctx, _ = context_for(77, title="오늘 읽은 소설", body=[f"{full_title} 읽었다"])
        self.assertTrue(pipe._local_hold_has_work_role(ctx, candidate))

    def test_literal_title_requires_original_author_quote_boundary(self):
        title = "여러 장르 등의 약자 추정"
        negative_bodies = (
            [f'친구가 "{title}"라고 했다'],
            [f"친구가 {title} 읽었대"],
            [f"> {title}"],
            ["친구가 “말하길", title, "그랬다”라고 했다"],
            [f"앞{title}뒤"],
            ["여러 장르 등의 약자추정"],
            ["여러 장르 등의 '다른 말'이라고 약자 추정"],
        )
        for body in negative_bodies:
            with self.subTest(body=body):
                pipe, ctx, _ = context_for(35, title="다른 작품을 읽었다", body=body)
                self.assertFalse(pipe._has_literal_author_title_occurrence(ctx, title))
                self.assertTrue(pipe._is_unbound_title_meta_explanation(ctx, title))
        for body in ([f"소설 '{title}'을 읽었다"], [f"나는 「{title}」를 읽었다"],
                     [f"{title} 읽었다"]):
            with self.subTest(body=body):
                pipe, ctx, _ = context_for(35, title="다른 작품을 읽었다", body=body)
                self.assertTrue(pipe._has_literal_author_title_occurrence(ctx, title))
                self.assertFalse(pipe._is_unbound_title_meta_explanation(ctx, title))


if __name__ == "__main__":
    unittest.main()
