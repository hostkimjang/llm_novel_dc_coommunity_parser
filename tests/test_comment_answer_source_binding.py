"""격리 후보의 기능 단위 회귀 초안. root 통합 뒤 실행하며 이 작성 단계에서는 미실행."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from llm_batch.agentic_pipeline import AgenticPipeline
from llm_batch.domain.models import DetectedTitle, PostInput
from llm_batch.experts.orchestrator import ConversationContext, ExpertType

FIXTURE = Path(__file__).parent / "fixtures/comment_answer_source_snapshot.json"
LEGACY_FIXTURE = Path(__file__).parent / "fixtures/comment_answer_legacy_source.json"


class NoExternalIO:
    def fetch(self, *args, **kwargs):
        raise AssertionError("외부 fetch 금지")

    def search(self, *args, **kwargs):
        raise AssertionError("외부 search 금지")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf8")


def make_context(title, comments, body="", *, post_data=None):
    raw = copy.deepcopy(post_data) if post_data is not None else {
        "post_id": 1, "author": "검토용", "title": title,
        "content_blocks": [{"type": "text", "text": body}] if body else [],
    }
    post = PostInput(**raw, comments=copy.deepcopy(comments))
    pipe = AgenticPipeline(llm=object(), mcp=NoExternalIO(), max_iterations=1)
    pipe.enable_url_fetch_disk_cache = False
    pipe._use_session_knowledge = False
    ctx = ConversationContext(post_id=post.post_id, post_data=pipe._post_to_dict(post),
                              comments=pipe._extract_comments(post))
    ctx._final_source_original_inputs = pipe._capture_final_source_original_inputs(post)
    ctx._final_source_original_comment_refs = tuple(post.comments)
    return pipe, ctx


def comment(cid, text, parent=None, level=0):
    return {"comment_id": cid, "content": text, "reply_to_comment_id": parent,
            "reply_level": level, "author": "익명"}


def titles(pipe, ctx):
    return [x.official_title for x in pipe._collect_comment_answer_preservation_candidates(
        ctx, discussion_type="recommendation")]


class CommentAnswerSourceBindingTests(unittest.TestCase):
    def test_current18_and32_source_preserved_without_comment_work_candidates(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf8"))
        for index in ("18", "32"):
            with self.subTest(index=index):
                row = fixture["records"][index]
                self.assertEqual(hashlib.sha256(canonical({"post": row["source_post"],
                    "comments": row["source_comments"]})).hexdigest(), row["source_canonical_sha256"])
                self.assertEqual(hashlib.sha256(canonical(row["checkpoint_result"])).hexdigest(),
                                 row["result_canonical_sha256"])
                pipe, ctx = make_context("", row["source_comments"], post_data=row["source_post"])
                original = copy.deepcopy((ctx.post_data, ctx.comments,
                    ctx._final_source_original_comment_refs, ctx._final_source_original_inputs))
                # 현재18의 모델 work target 또는 recommendation 분류를 흉내낸 교란이다.
                # 저장 expert 전체 재생이라고 주장하지 않는다.
                ctx.set_expert_output(ExpertType.DISCOURSE, {"discourse_analysis": {
                    "primary_domain": "novel_literature", "intent": "ask_question", "target_kind": "work"}})
                self.assertEqual(titles(pipe, ctx), [])
                self.assertFalse(pipe._has_comment_answer_candidate_context(ctx, discussion_type="recommendation"))
                if index == "18":
                    self.assertTrue(pipe._post_likely_requests_title_answer(ctx))
                self.assertEqual(original, (ctx.post_data, ctx.comments,
                    ctx._final_source_original_comment_refs, ctx._final_source_original_inputs))

    def test_model_target_punctuation_and_nearby_requests_do_not_bind(self):
        cases = [
            ("그럼 어떻게 됨?", ["인공지능", "짤캐 누구", "ai 모델명 춘식이"]),
            ("일상 이야기", ["제목이 곧...", "너무 낡았어"]),
            ("일상 이야기", ["소설 제목 뭐임?", "인공지능"]),
            ("일상 이야기", ["인공지능", "소설 제목 뭐임?"]),
            ("식당 추천좀", ["인공지능"]),
            ("친구가 제목 뭐냐고 물었어", ["인공지능"]),
            ("기록", ["제목: 인공지능"]),
        ]
        for title, comments in cases:
            with self.subTest(title=title, comments=comments):
                pipe, ctx = make_context(title, comments)
                self.assertEqual(titles(pipe, ctx), [])

    def test_title_answer_recommendation_common_noun_question_title_and_links(self):
        cases = [
            ("소설 제목 뭐임?", ["별빛 기사의 마지막 귀환"], ["별빛 기사의 마지막 귀환"]),
            ("백합 소설 추천좀", ["누드모드", "초 가구야 공주"], ["누드모드", "초 가구야 공주"]),
            ("작품명 알려줘", ["제목: 인공지능"], ["인공지능"]),
            ("작품명 알려줘", ["제목: 누구인가?"], ["누구인가?"]),
            ("작품명 알려줘", ["제목: 봄"], ["봄"]),
            ("작품명 알려줘", ["제목: 너무 낡았어"], ["너무 낡았어"]),
            ("작품명 알려줘", ["[인공지능](https://novelpia.com/novel/12345)"], ["인공지능"]),
            ("작품명 알려줘", ["제목: 누구인가? https://novelpia.com/novel/12345"], ["누구인가?"]),
        ]
        for title, comments, expected in cases:
            with self.subTest(title=title, comments=comments):
                pipe, ctx = make_context(title, comments)
                candidates = pipe._collect_comment_answer_preservation_candidates(ctx, discussion_type="general")
                self.assertEqual([x.official_title for x in candidates], expected)
                self.assertTrue(all(pipe._local_hold_has_work_role(ctx, x) for x in candidates))
                self.assertTrue(all(x.confidence == "Low" and x.reference_role == "candidate" for x in candidates))
                self.assertTrue(all("comment_answer_preservation_only" in x.negative_evidence for x in candidates))

    def test_exact_reply_id_after_empty_comment_binds_only_its_request(self):
        comments = [comment("empty", ""), comment("q", "2개 제목 혹시 알려줄 수 있음?"),
                    comment("sibling", "반응 문장"),
                    comment("a", "@익명\n가족친화적게임 / 엄마가 낳은 정실들", "q", 1)]
        pipe, ctx = make_context("읽은 작품 이야기", comments)
        self.assertEqual(titles(pipe, ctx), ["가족친화적게임", "엄마가 낳은 정실들"])
        observed = pipe._bound_comment_answer_observations(ctx)
        self.assertTrue(all(x["original_index"] == 3 and x["request_index"] == 1
                            and x["comment_id"] == "a" and x["request_comment_id"] == "q"
                            for x in observed))

    def test_sibling_prior_answer_chain_unknown_parent_and_typed_id_mismatch_block(self):
        for comments in (
            [comment("q", "소설 제목 뭐임?"), comment("a", "제목: 인공지능")],
            [comment("a", "제목: 인공지능", "q", 1), comment("q", "소설 제목 뭐임?")],
            [comment("q", "소설 제목 뭐임?"), comment("a", "별빛 기사의 마지막 귀환", "q", 1),
             comment("b", "제목: 인공지능", "a", 1)],
            [comment("q", "소설 제목 뭐임?"), comment("a", "제목: 인공지능", "missing", 1)],
            [comment(17, "소설 제목 뭐임?"), comment("a", "제목: 인공지능", "17", 1)],
            [comment("q", "소설 제목 뭐임?"), comment("q", "다른 말"),
             comment("a", "제목: 인공지능", "q", 1)],
        ):
            with self.subTest(comments=comments):
                pipe, ctx = make_context("읽은 작품 이야기", comments)
                self.assertNotIn("인공지능", titles(pipe, ctx))

    def test_post_request_does_not_authorize_reply_to_unrelated_comment(self):
        # 무관 부모는 이름으로도 읽히는 명사구가 아니라 명백한 주제 전환 발화다.
        unrelated = "작품 제목은 모르겠고 지금은 점심을 먹고 있습니다."
        pipe, ctx = make_context("작품명 알려줘", [comment("s", unrelated),
            comment("a", "제목: 인공지능", "s", 1), comment("b", "@익명 인공지능", None, 1)])
        self.assertEqual(pipe._comment_work_request_kind(unrelated), "")
        self.assertEqual(titles(pipe, ctx), [])

    def test_questions_and_reactions_are_not_cleaned_into_titles(self):
        pipe, ctx = make_context("소설 제목 뭐임?", ["짤캐 누구", "제목 뭐임?", "정말 그런가?",
            "너무 낡았어", "우리한테도 묻지 말아다오", "근데 다들 좀", "읽어보니 별로네요"])
        self.assertEqual(titles(pipe, ctx), [])

    def test_captured_original_ignores_later_derived_title_question(self):
        pipe, ctx = make_context("일상 이야기", ["인공지능"])
        ctx.post_data["content_blocks"].append({"type": "text", "text": "작품명 알려줘", "source": "vlm"})
        self.assertEqual(titles(pipe, ctx), [])

    def test_cross_block_quote_does_not_authorize_answers(self):
        raw = {"post_id": 1, "author": "검토용", "title": "대화 기록", "content_blocks": [
            {"type": "text", "text": "친구가 “"}, {"type": "text", "text": "소설 제목 알려줘"},
            {"type": "text", "text": "”라고 말했다"}]}
        pipe, ctx = make_context("", ["인공지능"], post_data=raw)
        self.assertEqual(titles(pipe, ctx), [])

    def test_stale_comment_candidate_is_rechecked_and_not_moved_into_typed_diagnostics(self):
        pipe, ctx = make_context("", ["인공지능"], body="귀신임?")
        stale = DetectedTitle(official_title="인공지능", alias_or_mention="인공지능",
            negative_evidence=["comment_answer_preservation_only"], reference_role="candidate")
        extended = {}
        merged = pipe._merge_local_candidate_preservation_hints(ctx=ctx, discussion_type="recommendation",
            recommendation_candidates=[stale], extended_identity=extended, official_title=None)
        self.assertEqual(merged, [])
        self.assertNotIn("_local_surface_diagnostic_holds", extended)
        snap = pipe._build_candidate_preservation_snapshot(title_candidates=[], mentioned_works=[],
            comparison_target=None, recommendation_candidates=merged,
            local_diagnostic_sources=extended.get("_local_surface_diagnostic_holds"))
        self.assertEqual(list(snap.retained_sources), [])

    def test_existing_non_authoritative_diagnostics_and_raw49_are_preserved(self):
        row = json.loads(FIXTURE.read_text(encoding="utf8"))["records"]["49"]
        pipe, ctx = make_context("", row["source_comments"], post_data=row["source_post"])
        before = copy.deepcopy(ctx._final_source_original_comment_refs)
        self.assertEqual(pipe._post_comment_answer_request_kind(ctx), "title_request")
        self.assertEqual(titles(pipe, ctx), [])
        diagnostic = {"raw_text": "반응 관측", "work_role": False}
        extended = {"_nonwork_comment_observations": [diagnostic],
                    "_local_surface_diagnostic_holds": ["기존 비권한 진단 sentinel"]}
        pipe._merge_local_candidate_preservation_hints(ctx=ctx, discussion_type="general",
            recommendation_candidates=[], extended_identity=extended, official_title=None)
        self.assertEqual(extended["_nonwork_comment_observations"], [diagnostic])
        self.assertEqual(extended["_local_surface_diagnostic_holds"][:1], ["기존 비권한 진단 sentinel"])
        self.assertEqual(before, ctx._final_source_original_comment_refs)
        # 이미지의 제목/역할 정답 및 source guard→main→WAL은 이 국소 시험 범위 밖이다.

    def test_legacy_real_source_metadata_reply_chain_and_recommendations(self):
        records = json.loads(LEGACY_FIXTURE.read_text(encoding="utf8"))["records"]
        for pid, record in records.items():
            with self.subTest(pid=pid):
                source = copy.deepcopy(record["source"])
                self.assertEqual(hashlib.sha256(canonical(source)).hexdigest(), record["selected_source_sha256"])
                # 원래 index로 결합한다. 빈 댓글을 제거한 뒤 metadata를 붙이지 않는다.
                raw_comments = []
                metadata = {item["index"]: item for item in source.pop("comment_metadata")}
                for index, text in enumerate(source.pop("comments")):
                    meta = metadata.get(index, {})
                    raw_comments.append({"content": text, **{key: meta.get(key) for key in (
                        "comment_id", "author", "ip", "reply_to_comment_id", "reply_level", "created_at")}})
                pipe, ctx = make_context("", raw_comments, post_data=source)
                before = canonical([ctx.post_data, ctx.comments, list(ctx._final_source_original_comment_refs)])
                observed = pipe._bound_comment_answer_observations(ctx)
                candidates = pipe._collect_comment_answer_preservation_candidates(ctx, discussion_type="general")
                expected = (["누드모드", "초 가구야 공주",
                    "내가 연인이 될 수 있을리 없잔ㄴㅎ아 무리무리무리!(무리가 아니었다?!)"]
                    if pid == "11706856" else ["가족친화적게임", "엄마가 낳은 정실들"])
                self.assertEqual([item.official_title for item in candidates], expected)
                self.assertTrue(all(pipe._local_hold_has_work_role(ctx, item) for item in candidates))
                if pid == "11716478":
                    self.assertTrue(all(item["original_index"] == 4 and item["request_index"] == 3
                        and item["comment_id"] == "40480807" and item["request_comment_id"] == "40480410"
                        and item["relation"] == "reply_to_work_request" for item in observed))
                else:
                    bound = pipe._post_comment_answer_request_observation(ctx)
                    self.assertEqual([unit["origin"] for unit in bound["source_units"]], ["post_title", "body_line"])
                self.assertEqual(before, canonical([ctx.post_data, ctx.comments, list(ctx._final_source_original_comment_refs)]))

    def test_source_title_body_request_composition_and_bound_raw_positions(self):
        for title, body in (("요세의 백합계의 슈퍼스타는 뭐임", "알려다오 장붕"),
                            ("요즘 읽을 만한 판타지 소설", "추천해줘")):
            with self.subTest(title=title):
                pipe, ctx = make_context(title, ["  제목: 인공지능  "], body)
                self.assertEqual(titles(pipe, ctx), ["인공지능"])
                observation = pipe._bound_comment_answer_observations(ctx)[0]
                lo, hi = observation["answer_raw_span"]
                self.assertEqual(observation["raw_text"], "  제목: 인공지능  ")
                self.assertEqual(observation["raw_text"][lo:hi], "인공지능")
                self.assertEqual(len(observation["post_request"]["source_units"]), 2)

    def test_genre_statement_or_quoted_request_does_not_borrow_title_context(self):
        for title, body in (("백합 꽃말은 뭐임", "알려다오 장붕"),
                            ("선협의 수련이 뭐임", "알려다오"),
                            ("판타지 소설", "친구가 추천해줘라고 말했다"),
                            ("식당 메뉴", "추천해줘")):
            with self.subTest(title=title):
                pipe, ctx = make_context(title, ["제목: 인공지능"], body)
                self.assertEqual(titles(pipe, ctx), [])

    def test_counted_text_relation_records_uncertainty_without_id_claim(self):
        pipe, ctx = make_context("읽은 작품 이야기", ["2작품이 똑같이 가길래...",
            "@북부\n2개 제목 혹시 알려줄 수 있음?",
            "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들"])
        observations = pipe._bound_comment_answer_observations(ctx)
        self.assertEqual(len(observations), 2)
        self.assertTrue(all(item["relation"] == "explicit_multi_title_answer_turn"
            and item["speaker_identity"] == "unverified" and item["requested_count"] == 2
            and item["request_comment_id"] is None and item["comment_id"] is None
            for item in observations))
        pipe, ctx = make_context("읽은 작품 이야기", ["2작품이 똑같이 가길래...",
            "@북부\n2개 제목 혹시 알려줄 수 있음?",
            "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들 - dc App"])
        self.assertEqual(titles(pipe, ctx), ["가족친화적게임", "엄마가 낳은 정실들"])

    def test_counted_text_does_not_bypass_explicit_bad_parent_or_forged_ids(self):
        lead = comment("lead", "2작품이 똑같이 가길래...")
        question = comment("q", "@북부\n2개 제목 혹시 알려줄 수 있음?", "lead", 1)
        answer = comment("a", "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들", "q", 1)
        lead["author"] = answer["author"] = "북부"
        question.update(author="ㅇㅇ2", ip="220.94")
        changes = [
            {"reply_to_comment_id": "missing"}, {"reply_to_comment_id": "lead"},
            {"reply_to_comment_id": True}, {"comment_id": "q"},
            {"comment_id": False}, {"reply_to_comment_id": 17},
        ]
        for change in changes:
            with self.subTest(change=change):
                bad = dict(answer, **change)
                pipe, ctx = make_context("읽은 작품 이야기", [lead, question, bad])
                self.assertEqual(titles(pipe, ctx), [])
        # 문자열17과 정수17은 별도 ID다. 원문 count/명칭이 맞아도 fallback 금지.
        q2, a2 = dict(question, comment_id=17), dict(answer, reply_to_comment_id="17")
        pipe, ctx = make_context("읽은 작품 이야기", [lead, q2, a2])
        self.assertEqual(titles(pipe, ctx), [])

    def test_counted_text_requires_work_count_question_and_complete_nominal_response(self):
        lead = "2작품이 똑같이 가길래..."
        question = "@북부\n2개 제목 혹시 알려줄 수 있음?"
        answer = "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들"
        cases = [
            [question, answer], [lead, answer, question],
            [lead, question, "잡담", answer],
            ["2명이 똑같이 가길래...", question, answer],
            [lead, "@북부\n2개 제목이 곧...", answer],
            [lead, "@북부\n3개 제목 혹시 알려줄 수 있음?", answer],
            [lead, question, "@ㅇㅇ2(220.94)\n너무 낡았어 / 엄마가 낳은 정실들"],
            [lead, question, "@ㅇㅇ2(220.94)\n가족친화적게임 / 누구임?"],
            [lead, question, "가족친화적게임 / 엄마가 낳은 정실들"],
            [lead, question, answer, "@북부\n별빛 기사의 마지막 귀환 / 기사의 최후"],
        ]
        for comments in cases:
            with self.subTest(comments=comments):
                pipe, ctx = make_context("읽은 작품 이야기", comments)
                got = titles(pipe, ctx)
                if comments[:3] == [lead, question, answer]:
                    self.assertEqual(got, ["가족친화적게임", "엄마가 낳은 정실들"])
                else:
                    self.assertEqual(got, [])

    def test_counted_text_author_metadata_conflict_and_question_parent_conflict(self):
        lead = {"content": "2작품이 똑같이 가길래...", "author": "북부"}
        q = {"content": "@북부\n2개 제목 혹시 알려줄 수 있음?", "author": "ㅇㅇ2", "ip": "220.94"}
        a = {"content": "@ㅇㅇ2(220.94)\n가족친화적게임 / 엄마가 낳은 정실들", "author": "북부"}
        pipe, ctx = make_context("읽은 작품 이야기", [lead, q, a])
        self.assertEqual(titles(pipe, ctx), ["가족친화적게임", "엄마가 낳은 정실들"])
        for altered_q, altered_a in ((dict(q, author="다른사람"), a),
                                     (q, dict(a, author="다른사람")),
                                     (dict(q, reply_to_comment_id="missing"), a)):
            pipe, ctx = make_context("읽은 작품 이야기", [lead, altered_q, altered_a])
            self.assertEqual(titles(pipe, ctx), [])

    def test_unlabelled_speculative_predicates_do_not_become_work_titles(self):
        responses = ["폴리우레탄같은데", "인공지능 인듯", "모험같음", "모험 같아",
                     "모험인듯함", "모험일듯", "모험인가 싶은데", "모험같은데요ㅋㅋ"]
        for response in responses:
            with self.subTest(response=response):
                pipe, ctx = make_context("소설 제목 뭐임?", [response])
                before = canonical([ctx.post_data, ctx.comments, list(ctx._final_source_original_comment_refs)])
                self.assertEqual(titles(pipe, ctx), [])
                candidate = DetectedTitle(official_title=response, alias_or_mention=response,
                    negative_evidence=["comment_answer_preservation_only"], reference_role="candidate")
                self.assertFalse(pipe._local_hold_has_work_role(ctx, candidate))
                self.assertEqual(before, canonical([ctx.post_data, ctx.comments, list(ctx._final_source_original_comment_refs)]))

    def test_sentence_shaped_declared_titles_and_explicit_links_are_preserved(self):
        for response, expected in [
            ("제목: 폴리우레탄같은데", "폴리우레탄같은데"),
            ("작품명: 이건 꿈인듯", "이건 꿈인듯"),
            ("[모험같음](https://novelpia.com/novel/12345)", "모험같음"),
            ("「모험 같아」", "모험 같아"),
            ("제목: 내가 연인이 될 수 있을리 없잖아?", "내가 연인이 될 수 있을리 없잖아?"),
        ]:
            with self.subTest(response=response):
                pipe, ctx = make_context("소설 제목 뭐임?", [response])
                candidates = pipe._collect_comment_answer_preservation_candidates(ctx, discussion_type="general")
                self.assertEqual([item.official_title for item in candidates], [expected])
                self.assertTrue(pipe._local_hold_has_work_role(ctx, candidates[0]))
                observation = pipe._bound_comment_answer_observations(ctx)[0]
                self.assertTrue(observation["explicit_title_span"])
                lo, hi = observation["answer_raw_span"]
                self.assertEqual(observation["raw_text"][lo:hi], expected)

    def test_counted_named_answer_keeps_sentence_titles_without_guessing_unlabelled_reactions(self):
        lead = "2작품이 똑같이 가길래..."
        q = "@북부\n2개 제목 혹시 알려줄 수 있음?"
        answer = "@ㅇㅇ2(220.94)\n「폴리우레탄같은데」 / 「이건 꿈인듯」"
        pipe, ctx = make_context("읽은 작품 이야기", [lead, q, answer])
        self.assertEqual(titles(pipe, ctx), ["폴리우레탄같은데", "이건 꿈인듯"])
        observed = pipe._bound_comment_answer_observations(ctx)
        self.assertTrue(all(item["relation"] == "explicit_multi_title_answer_turn"
                            and item["explicit_title_span"] for item in observed))
        # 수량 목록만으로 추측 절 전체를 표제로 바꾸지는 않는다. 닫힌 명칭 구간이 다른 점이다.
        pipe, ctx = make_context("읽은 작품 이야기", [lead, q,
            "@ㅇㅇ2(220.94)\n폴리우레탄같은데 / 이건 꿈인듯"])
        self.assertEqual(titles(pipe, ctx), [])

    def test_quoted_names_do_not_bypass_unrelated_or_wrong_parent(self):
        answer = "@ㅇㅇ2(220.94)\n「폴리우레탄같은데」 / 「이건 꿈인듯」"
        pipe, ctx = make_context("일상 이야기", [answer])
        self.assertEqual(titles(pipe, ctx), [])
        pipe, ctx = make_context("읽은 작품 이야기", [
            comment("lead", "2작품이 똑같이 가길래..."),
            comment("q", "@북부\n2개 제목 혹시 알려줄 수 있음?", "lead", 1),
            comment("a", answer, "missing", 1)])
        self.assertEqual(titles(pipe, ctx), [])

    def test_exact49_speculative_comment_has_no_new_candidate_and_diagnostics_survive(self):
        row = json.loads(FIXTURE.read_text(encoding="utf8"))["records"]["49"]
        pipe, ctx = make_context("", row["source_comments"], post_data=row["source_post"])
        target = next(item for item in ctx._final_source_original_comment_refs
                      if item.get("comment_id") == "33540785")
        self.assertEqual(target["content"], "폴리우레탄같은데")
        before = canonical([ctx.post_data, list(ctx._final_source_original_comment_refs)])
        stale = DetectedTitle(official_title=target["content"], alias_or_mention=target["content"],
            negative_evidence=["comment_answer_preservation_only"], reference_role="candidate")
        preserved = {"text": target["content"], "comment_id": "33540785", "work_role": False}
        extended = {"_nonwork_comment_observations": [copy.deepcopy(preserved)]}
        merged = pipe._merge_local_candidate_preservation_hints(ctx=ctx, discussion_type="general",
            recommendation_candidates=[stale], extended_identity=extended, official_title=None)
        self.assertNotIn(stale, merged)
        self.assertEqual(titles(pipe, ctx), [])
        self.assertEqual(extended["_nonwork_comment_observations"], [preserved])
        self.assertFalse(any(item.official_title == target["content"]
                             for item in extended.get("_local_surface_diagnostic_holds", [])))
        self.assertEqual(before, canonical([ctx.post_data, list(ctx._final_source_original_comment_refs)]))

    def test_v4_continuing_predicate_replies_do_not_fill_requested_title_slots(self):
        responses = ["이거 작가 그림체 아는데", "그 그림체 나도 아는데요", "거기서 보는데",
                     "오늘도 읽는데", "그런 장면은 있는데", "저 사람은 여기 가는데",
                     "그 장면은 좋은데", "그 작가는 다르던데"]
        for response in responses:
            for relation in ("post", "reply"):
                with self.subTest(response=response, relation=relation):
                    if relation == "post":
                        pipe, ctx = make_context("소설 제목 뭐임?", [response])
                    else:
                        pipe, ctx = make_context("읽은 작품 이야기", [comment("q", "작품명 알려줘"),
                            comment("a", response, "q", 1)])
                    before = canonical([ctx.post_data, ctx.comments, list(ctx._final_source_original_comment_refs)])
                    self.assertEqual(titles(pipe, ctx), [])
                    stale = DetectedTitle(official_title=response, alias_or_mention=response,
                        negative_evidence=["comment_answer_preservation_only"], reference_role="candidate")
                    self.assertFalse(pipe._local_hold_has_work_role(ctx, stale))
                    self.assertEqual(before, canonical([ctx.post_data, ctx.comments,
                                                       list(ctx._final_source_original_comment_refs)]))

    def test_v4_same_clause_as_explicit_title_requires_real_request_relation(self):
        title = "이거 작가 그림체 아는데"
        unrelated = "작품 제목은 모르겠고 지금은 점심을 먹고 있습니다."
        for response, act in [("제목: " + title, "labelled_work_name"),
                              ("「" + title + "」", "delimited_work_name"),
                              ("[" + title + "](https://novelpia.com/novel/12345)", "linked_work_name")]:
            with self.subTest(response=response):
                pipe, ctx = make_context("소설 제목 뭐임?", [response])
                self.assertEqual(titles(pipe, ctx), [title])
                observed = pipe._bound_comment_answer_observations(ctx)
                self.assertEqual(len(observed), 1)
                self.assertEqual(observed[0]["response_act"], act)
                self.assertEqual(observed[0]["relation"], "direct_post_work_request")
                self.assertEqual(observed[0]["raw_text"][slice(*observed[0]["answer_raw_span"])], title)
                self.assertTrue(observed[0]["explicit_title_span"])
                for bad_title, comments in [("일상 이야기", [response]),
                        ("소설 제목 뭐임?", [comment("q", unrelated),
                                               comment("a", response, "q", 1)])]:
                    wrong_pipe, wrong_ctx = make_context(bad_title, comments)
                    self.assertEqual(wrong_pipe._comment_work_request_kind(unrelated), "")
                    self.assertEqual(titles(wrong_pipe, wrong_ctx), [])

    def test_v4_exact49_recognition_reply_is_not_a_name_and_raw_diagnostics_remain(self):
        row = json.loads(FIXTURE.read_text(encoding="utf8"))["records"]["49"]
        pipe, ctx = make_context("", row["source_comments"], post_data=row["source_post"])
        raw = next(item for item in ctx._final_source_original_comment_refs
                   if item.get("comment_id") == "33540718")
        self.assertEqual(raw["content"], "이거 작가 그림체 아는데")
        self.assertEqual(raw["reply_level"], 0)
        self.assertIsNone(raw["reply_to_comment_id"])
        before = canonical([ctx.post_data, ctx.comments, list(ctx._final_source_original_comment_refs)])
        self.assertEqual(pipe._post_comment_answer_request_kind(ctx), "title_request")
        self.assertEqual(pipe._bound_comment_answer_observations(ctx), [])
        stale = DetectedTitle(official_title=raw["content"], alias_or_mention=raw["content"],
            negative_evidence=["comment_answer_preservation_only"], reference_role="candidate")
        diagnostic = {"raw_text": raw["content"], "comment_id": "33540718", "work_role": False}
        extended = {"_nonwork_comment_observations": [copy.deepcopy(diagnostic)]}
        merged = pipe._merge_local_candidate_preservation_hints(ctx=ctx, discussion_type="recommendation",
            recommendation_candidates=[stale], extended_identity=extended, official_title=None)
        self.assertEqual(merged, [])
        self.assertFalse(pipe._local_hold_has_work_role(ctx, stale))
        self.assertEqual(extended["_nonwork_comment_observations"], [diagnostic])
        self.assertFalse(any(isinstance(item, DetectedTitle) and item.official_title == raw["content"]
                             for item in extended.get("_local_surface_diagnostic_holds", [])))
        self.assertEqual(before, canonical([ctx.post_data, ctx.comments,
                                           list(ctx._final_source_original_comment_refs)]))

    def test_v5_nominal_parent_can_name_a_title_but_cannot_authorize_its_replies(self):
        # 이전 합성 문구를 버리지 않는다. 실제 작품 실재를 주장하지 않는 Low 이름 후보다.
        nominal = "점심 이야기"
        pipe, ctx = make_context("작품명 알려줘", [comment("s", nominal),
            comment("a", "제목: 인공지능", "s", 1), comment("b", "@익명 인공지능", None, 1)])
        before = canonical([ctx.post_data, ctx.comments, list(ctx._final_source_original_comment_refs)])
        self.assertEqual(pipe._comment_work_request_kind(nominal), "")
        candidates = pipe._collect_comment_answer_preservation_candidates(ctx, discussion_type="general")
        self.assertEqual([item.official_title for item in candidates], [nominal])
        self.assertTrue(all(item.confidence == "Low" and item.reference_role == "candidate"
                            and "comment_answer_preservation_only" in item.negative_evidence for item in candidates))
        observed = pipe._bound_comment_answer_observations(ctx)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["comment_id"], "s")
        self.assertEqual(observed[0]["original_index"], 0)
        self.assertEqual(observed[0]["relation"], "direct_post_work_request")
        self.assertEqual(observed[0]["response_act"], "nominal_answer_fragment")
        self.assertIsNone(observed[0]["request_comment_id"])
        self.assertFalse(any(item["comment_id"] in {"a", "b"} for item in observed))
        self.assertEqual(before, canonical([ctx.post_data, ctx.comments,
                                           list(ctx._final_source_original_comment_refs)]))


if __name__ == "__main__":
    unittest.main()
