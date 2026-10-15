"""기존 세 긍정 시험의 원문과 기대를 그대로 유지한다. 작성 단계 미실행."""
import unittest
from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import ContentBlock, PostInput
from llm_batch.experts.orchestrator import ConversationContext

class NoExternalIO:
    def fetch(self, *args, **kwargs):
        raise AssertionError("외부 fetch 금지")
    def search(self, *args, **kwargs):
        raise AssertionError("외부 search 금지")

def build_pipeline():
    pipeline = AgenticPipeline(llm=object(), mcp=NoExternalIO(), max_iterations=1)
    pipeline.enable_url_fetch_disk_cache = False
    pipeline._use_session_knowledge = False
    return pipeline

class OriginalCommentRecallTests(unittest.TestCase):
    def test_recommendation_comment_answers_are_preserved_as_candidates(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11706856,
            title="요세의 백합계의 슈퍼스타는 뭐임",
            author="ㅇㅇ",
            content_blocks=[ContentBlock(type="text", text="알려다오 장붕")],
            comments=[
                "누드모드",
                "초 가구야 공주",
                "내가 연인이 될 수 있을리 없잔ㄴㅎ아 무리무리무리!(무리가 아니었다?!)재밌게봄",
                "너",
                "나",
                "@아이아\n제-하하하!!! 짤도 달릴수 있다고",
            ],
        )
        ctx = ConversationContext(post_id=11706856, post_data=pipeline._post_to_dict(post), comments=post.comments)

        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="undecodable_reference",
        )
        titles = [cand.official_title for cand in candidates]

        self.assertIn("누드모드", titles)
        self.assertIn("초 가구야 공주", titles)
        self.assertIn("내가 연인이 될 수 있을리 없잔ㄴㅎ아 무리무리무리!(무리가 아니었다?!)", titles)
        self.assertNotIn("너", titles)
        self.assertNotIn("나", titles)
        self.assertTrue(all(cand.confidence == "Low" for cand in candidates))
        self.assertTrue(all("comment_answer_preservation_only" in (cand.negative_evidence or []) for cand in candidates[:3]))


    def test_reply_chain_slash_title_answers_are_preserved_without_single_promotion(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11716478,
            title="근친물은 무조건 1장녀 2작은누나 3여동생 공식이네",
            author="북부",
            content_blocks=[ContentBlock(type="text", text="항상 먼저 따먹히는건 만만한 작은누나고")],
            comments=[
                "2작품이 똑같이 가길래...",
                "@북부\n2개 제목 혹시 알려줄 수 있음?",
                "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들",
            ],
        )
        ctx = ConversationContext(post_id=11716478, post_data=pipeline._post_to_dict(post), comments=post.comments)

        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="recommendation",
        )
        titles = [cand.official_title for cand in candidates]

        self.assertIn("가족친화적게임", titles)
        self.assertIn("엄마가 낳은 정실들", titles)
        self.assertGreaterEqual(len(titles), 2)
        self.assertTrue(all(cand.reference_role == "candidate" for cand in candidates))


    def test_local_hold_candidate_snapshot_keeps_preservation_type(self):
        pipeline = build_pipeline()
        post = PostInput(
            post_id=11716478,
            title="근친물은 무조건 1장녀 2작은누나 3여동생 공식이네",
            author="북부",
            content_blocks=[ContentBlock(type="text", text="항상 먼저 따먹히는건 만만한 작은누나고")],
            comments=[
                "2작품이 똑같이 가길래...",
                "@북부\n2개 제목 혹시 알려줄 수 있음?",
                "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들",
            ],
        )
        ctx = ConversationContext(post_id=11716478, post_data=pipeline._post_to_dict(post), comments=post.comments)
        candidates = pipeline._collect_local_candidate_preservation_hints(
            ctx=ctx,
            discussion_type="recommendation",
        )

        snapshot = pipeline._build_candidate_preservation_sources(
            title_candidates=[],
            mentioned_works=[],
            comparison_target=None,
            recommendation_candidates=candidates,
            secondary_reference_works=None,
        )

        by_title = {row["official_title"]: row for row in snapshot}
        self.assertEqual(by_title["가족친화적게임"]["preservation_role"], "recommendation_candidate")
        self.assertEqual(by_title["가족친화적게임"]["local_preservation_type"], "comment_answer_hold")
        self.assertEqual(by_title["가족친화적게임"]["promotion_policy"], "hold_without_promotion")
        self.assertIn("comment_answer_preservation_only", by_title["가족친화적게임"]["negative_evidence"])

