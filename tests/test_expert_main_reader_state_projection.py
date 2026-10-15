"""최종 typed 공개 상태에 따른 독자 설명만 검증한다."""

import copy
import unittest

from expert_main import _sync_final_publication_ledger_contract
from llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    candidate_inventory_evidence_from_sources,
    evaluate_publish_contract,
)


class ExpertMainReaderStateProjectionTest(unittest.TestCase):
    @staticmethod
    def _candidate_result(title, reason_lines, subject, discussion_type="general"):
        sources = [{"official_title": title, "heretic_url": "https://novelpia.com/novel/233173"}]
        evidence = candidate_inventory_evidence_from_sources(sources)
        contract = evaluate_publish_contract(
            GroundingState(
                post_id=11718075,
                candidate_title="",
                candidate_inventory_count=1,
                source="serializer_candidate_inventory_preserved",
                scope=ScopeState(scope_kind="unknown", confidence="low"),
            ),
            evidence,
        )
        identity = {
            "title_candidates": copy.deepcopy(sources),
            "candidate_preservation_sources": copy.deepcopy(sources),
            "candidate_ledger": {"candidate_preservation_sources": copy.deepcopy(sources)},
            "discussion_type": discussion_type,
            "reason_lines": list(reason_lines),
            "reason": "\n".join(reason_lines),
            "primary_subject_text": subject,
            "is_resolved_work_discussion": False,
            "image_evidence_catalog": [{"ocr_text": title, "title_role": "work_title"}],
        }
        apply_publish_contract(identity, contract)
        return {"identity": identity}

    @staticmethod
    def _publish_result(title, url, reason_lines, subject):
        contract = evaluate_publish_contract(
            GroundingState(
                post_id=11718077,
                candidate_title=title,
                candidate_url=url,
                source="expert_serializer_test",
                official_title_exists=True,
                row_discusses_work_as_work=True,
                title_resolution_state="resolved",
                work_resolution="resolved",
                discussion_type="review",
                scope=ScopeState(
                    scope_kind="current_work", confidence="high",
                    direct_bridge_sources=["explicit_alias_relation", "official_detail_url"],
                ),
            ),
            [
                EvidenceRecord(kind="alias_bridge", source_path_or_snippet=title, supports_publish=True, candidate_title=title),
                EvidenceRecord(kind="official_detail_url", source_path_or_snippet=url, candidate_title=title, candidate_url=url, title_url_match=True),
            ],
        )
        identity = {
            "reason_lines": list(reason_lines),
            "reason": "\n".join(reason_lines),
            "primary_subject_text": subject,
            "is_resolved_work_discussion": True,
            "is_relevant": True,
            "title_resolution_allowed": True,
            "title_resolution_state": "resolved",
            "work_resolution": "resolved",
            "discussion_type": "review",
            "novel_identity": {"confidence": "High"},
        }
        apply_publish_contract(identity, contract)
        return {"identity": identity}

    @staticmethod
    def _authority_snapshot(identity):
        return copy.deepcopy({
            key: identity.get(key)
            for key in (
                "promotion_gate_state", "promotion_gate_evidence", "promotion_decision",
                "publish_contract_trace", "publish_ledger", "publish_contract_input_fingerprint",
                "candidate_ledger", "title_candidates", "candidate_preservation_sources",
                "image_evidence_catalog", "novel_identity", "entity_mentions",
            )
        })

    def test_candidate_only_generated_claims_follow_v6_w2_w7_w11_w12_shapes(self):
        cases = (
            ("W2", "죽었다 깨어도 수선", "general", "메인 화제는 작가 '돌마늘'에 대한 품평/방향 제안입니다.", False),
            ("W7", "즉사기 들고 무림에 떨어지다", "anticipation", "메인 화제는 '즉사기 들고 무림에 떨어지다' 관련 작품 토론입니다.", False),
            ("W11", "빌어먹을 환생", "general", "메인 화제는 '빌어먹을 환생' 관련 작품 토론입니다.", True),
            ("W12", "마법 좋아좋아좋아", "review", "메인 화제는 '마법 좋아좋아좋아' 감상/평가입니다.", False),
        )
        for worker, title, discussion_type, subject, has_ocr_claim in cases:
            with self.subTest(worker=worker):
                summary = f"[판정 요약] - 판정: 관련 - 공식 제목: '{title}' [원문 해석] - 제목: 원문 약칭 [최종 종합] - 제목/본문 앵커와 검색 근거를 종합하여 '{title}' 관련 작품 토론으로 판정했습니다."
                if has_ocr_claim:
                    summary += f" 이미지 직접 근거(OCR/표지)에서도 '{title}'를 확인했습니다."
                summary += " [정합성 교정]"
                if has_ocr_claim:
                    summary = summary.replace("[원문 해석]", "- image_ocr_title_evidence: false [원문 해석]")
                lines = [summary, f"- 최종 공식 제목은 '{title}'로 확정됨. [근거 스코어] - total: +5"]
                result = self._candidate_result(title, lines, subject, discussion_type)
                identity = result["identity"]
                if worker == "W11":
                    identity["entity_mentions"] = [{
                        "text": "VLM/OCR explicit work title", "entity_type": "work",
                        "canonical_value": title,
                    }]
                authority = self._authority_snapshot(identity)

                self.assertTrue(_sync_final_publication_ledger_contract(result))
                self.assertEqual(self._authority_snapshot(identity), authority)
                self.assertEqual(identity["promotion_decision"]["status"], "candidate_only")
                self.assertIsNone(identity["novel_identity"]["official_title"])
                self.assertIn("- 공식 제목: 미확정", identity["reason"])
                self.assertIn("- 최종 공개: 제목·URL 보류, 작품 후보 보존.", identity["reason"])
                self.assertNotIn(f"'{title}' 관련 작품 토론으로 판정했습니다.", identity["reason"])
                self.assertEqual(identity["reason"], "\n".join(identity["reason_lines"]))
                if worker == "W2":
                    self.assertEqual(identity["primary_subject_text"], subject)
                else:
                    self.assertNotIn(f"'{title}'", identity["primary_subject_text"])
                    self.assertIn("공식 제목은 보류", identity["primary_subject_text"])
                if has_ocr_claim:
                    self.assertIn("OCR/표지 문자열은 후보 단서", identity["reason"])
                    self.assertNotIn("OCR/표지)에서도", identity["reason"])
                    self.assertEqual(identity["entity_mentions"], authority["entity_mentions"])
                self.assertFalse(_sync_final_publication_ledger_contract(result))

    def test_w10_subject_only_claim_is_reconciled_without_changing_hold_reason(self):
        lines = [
            "[판정 요약] - 공식 제목: 미확정 [원문 해석] - 제목: 망겜성 질문",
            "[최종 종합] - 단일 공식 제목은 미확정으로 유지합니다. [근거 스코어] - total: +2",
        ]
        result = self._candidate_result(
            "망겜의 성기사", lines,
            "메인 화제는 '망겜의 성기사' 캐릭터/장면 반응입니다.",
            "character_talk",
        )
        identity = result["identity"]
        before_reason = identity["reason"]
        authority = self._authority_snapshot(identity)
        self.assertTrue(_sync_final_publication_ledger_contract(result))
        self.assertEqual(identity["reason"], before_reason)
        self.assertIn("인물·장면에 관한 반응", identity["primary_subject_text"])
        self.assertNotIn("망겜의 성기사", identity["primary_subject_text"])
        self.assertEqual(self._authority_snapshot(identity), authority)
        self.assertFalse(_sync_final_publication_ledger_contract(result))

    def test_w10_wrapped_generated_claim_is_held_without_rewriting_source_quote(self):
        title = "망겜의 성기사"
        source_quote = f"원문 인용: '{title}'\n관련 작품 토론으로 판정했습니다."
        lines = [
            f"[판정 요약] - 공식 제목: 미확정 [원문 해석] - 본문 요약: {source_quote}",
            f"[최종 종합] - 제목/본문 앵커와 검색 근거를 종합하여 '{title}'",
            "관련 작품 토론으로 판정했습니다. [정합성 교정] - 최종 공식 제목은 미확정 상태로 유지합니다. [근거 스코어] - total: +9",
        ]
        result = self._candidate_result(
            title, lines, f"메인 화제는 '{title}' 캐릭터/장면 반응입니다.",
            "character_talk",
        )
        identity = result["identity"]
        authority = self._authority_snapshot(identity)

        self.assertTrue(_sync_final_publication_ledger_contract(result))
        self.assertEqual(self._authority_snapshot(identity), authority)
        self.assertIn(source_quote, identity["reason"])
        self.assertIn("- 작품 관련 단서는 있으나 주작품의 공식 제목은 최종 공개 계약에서 보류했습니다.", identity["reason"])
        self.assertNotIn("- 제목/본문 앵커와 검색 근거를 종합하여", identity["reason"])
        self.assertNotIn(title, identity["primary_subject_text"])
        self.assertEqual(identity["reason"], "\n".join(identity["reason_lines"]))
        self.assertFalse(_sync_final_publication_ledger_contract(result))

    def test_published_pair_and_reader_topic_remain_or_reconcile_to_public_title(self):
        for title, url, topic in (
            ("즉사기 들고 무림에 떨어지다", "https://www.munpia.com/novel/detail/528383", "감상/평가"),
            ("즉사기 들고 무림에 떨어지다", "https://www.munpia.com/novel/detail/528383", "캐릭터/장면 반응"),
            ("망겜의 힐러", "https://page.kakao.com/home/61763847", "감상/평가"),
        ):
            with self.subTest(title=title):
                lines = [
                    f"[판정 요약] - 공식 제목: '{title}' [원문 해석] - 제목: 원문 약칭",
                    f"[최종 종합] - 제목/본문 앵커와 검색 근거를 종합하여 '{title}' 관련 작품 토론으로 판정했습니다. [정합성 교정] - 최종 공식 제목은 '{title}'로 확정됨. [근거 스코어] - total: +14",
                ]
                subject = f"메인 화제는 '{title}' {topic}입니다."
                result = self._publish_result(title, url, lines, subject)
                identity = result["identity"]
                authority = self._authority_snapshot(identity)
                _sync_final_publication_ledger_contract(result)
                self.assertEqual(identity["reason"], "\n".join(lines))
                self.assertEqual(identity["primary_subject_text"], subject)
                self.assertEqual(self._authority_snapshot(identity), authority)
                self.assertFalse(_sync_final_publication_ledger_contract(result))

                identity["reason_lines"] = [line.replace(f"'{title}'", "'이전 후보'") for line in lines]
                identity["reason"] = "\n".join(identity["reason_lines"])
                identity["primary_subject_text"] = f"메인 화제는 '이전 후보' {topic}입니다."
                self.assertTrue(_sync_final_publication_ledger_contract(result))
                self.assertEqual(identity["reason"], "\n".join(lines))
                self.assertEqual(identity["primary_subject_text"], subject)
                self.assertEqual(self._authority_snapshot(identity), authority)

    def test_nil_genre_and_comic_explanations_are_untouched(self):
        for topic in ("장르/트로프 일반론", "현실 친구 관계", "성인 만화 문맥"):
            with self.subTest(topic=topic):
                contract = evaluate_publish_contract(
                    GroundingState(post_id=124, candidate_title="", source="no_candidate"), []
                )
                identity = {
                    "reason_lines": ["[판정 요약] - 공식 제목: 미확정 [원문 해석]", "[최종 종합] - 주제는 " + topic + "입니다. [근거 스코어]"],
                    "primary_subject_text": "메인 화제는 " + topic + "입니다.",
                }
                identity["reason"] = "\n".join(identity["reason_lines"])
                apply_publish_contract(identity, contract)
                result = {"identity": identity}
                reader = (identity["reason"], identity["reason_lines"], identity["primary_subject_text"])
                _sync_final_publication_ledger_contract(result)
                self.assertEqual((identity["reason"], identity["reason_lines"], identity["primary_subject_text"]), reader)

    def test_original_quote_in_source_section_is_not_rewritten(self):
        title = "후보 작품"
        quote = "사용자 인용: - 최종 공식 제목은 '인용 작품'로 확정됨."
        lines = [
            f"[판정 요약] - 공식 제목: '{title}' [원문 해석] - 본문 요약: {quote}",
            f"[최종 종합] - 최종 공식 제목은 '{title}'로 확정됨. [근거 스코어]",
        ]
        result = self._candidate_result(title, lines, "메인 화제는 작품 관련 논의지만 단일 제목은 아직 미확정입니다.")
        self.assertTrue(_sync_final_publication_ledger_contract(result))
        reason = result["identity"]["reason"]
        self.assertIn(quote, reason)
        self.assertNotIn(f"- 최종 공식 제목은 '{title}'로 확정됨.", reason)


if __name__ == "__main__":
    unittest.main()
