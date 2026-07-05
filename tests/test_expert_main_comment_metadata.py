import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from expert_main import (
    load_jsonl_posts,
    _image_post_sample_post_ids,
    _public_content_blocks,
    _public_image_urls,
    _public_comment_context_lines,
    _public_comment_dialogue_context_lines,
    _public_comment_metadata,
    _require_vlm_ocr_for_image_posts,
    _sync_final_publication_ledger_contract,
    _scrub_promotion_blocked_result_contract,
    _vlm_ocr_semantic_review_gate_lines,
    _vlm_ocr_semantic_review_skip_reasons,
)


class ExpertMainCommentMetadataTest(unittest.TestCase):
    def test_promotion_blocked_result_contract_scrubs_resolution_text(self):
        result = {
            "identity": {
                "official_title": None,
                "official_novel_title": None,
                "heretic_url": None,
                "title_resolution_allowed": False,
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "Re: 제로부터 시작하는 이세계 생활",
                "blocked_official_title_url": "https://novelpia.com/novel/219051",
                "reason": "\n".join(
                    [
                        "[판정 요약]",
                        "- 판정: 관련",
                        "- 공식 제목: 'Re: 제로부터 시작하는 이세계 생활'",
                        "- 제목/본문 앵커와 검색 근거를 종합하여 'Re: 제로부터 시작하는 이세계 생활' 관련 작품 토론으로 판정했습니다.",
                        "[정합성 교정]",
                        "- 최종 공식 제목은 'Re: 제로부터 시작하는 이세계 생활'로 확정됨.",
                        "- heretic_url_platform: +3 (작품 상세 URL(플랫폼))",
                    ]
                ),
                "candidate_ledger": {
                    "blocked_official_title": "Re: 제로부터 시작하는 이세계 생활",
                    "blocked_official_title_url": "https://novelpia.com/novel/219051",
                },
            },
            "analysis": {
                "notes": "[정합성 교정] 최종 공식 제목은 'Re: 제로부터 시작하는 이세계 생활'로 확정되었으며, 플랫폼/검색 근거를 확보했습니다.",
                "detected_titles": [
                    {
                        "official_title": "Re: 제로부터 시작하는 이세계 생활",
                        "heretic_url": "https://novelpia.com/novel/219051",
                        "reference_role": "primary",
                    }
                ],
            },
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        reason = result["identity"]["reason"]
        self.assertIn("- 공식 제목: 미확정 (promotion blocked; 후보로만 보존)", reason)
        self.assertIn("최종 공식 제목 확정 문구는 promotion block guard로 철회됨", reason)
        self.assertIn("heretic_url_platform 점수는 promotion block guard로 철회됨", reason)
        self.assertNotIn("공식 제목: 'Re: 제로부터 시작하는 이세계 생활'", reason)
        self.assertNotIn("최종 공식 제목은 'Re: 제로부터 시작하는 이세계 생활'로 확정됨", reason)
        self.assertIn("최종 공식 제목은 미확정 상태입니다", result["analysis"]["notes"])
        detected = result["analysis"]["detected_titles"][0]
        self.assertEqual(detected["reference_role"], "candidate")
        self.assertEqual(detected["promotion_policy"], "hold_without_promotion")
        self.assertTrue(detected["blocked_by_candidate_audit"])

    def test_promotion_blocked_result_contract_scrubs_public_urls_and_primary_role(self):
        result = {
            "identity": {
                "official_title": None,
                "official_novel_title": None,
                "heretic_url": "https://novelpia.com/novel/382324",
                "title_resolution_allowed": False,
                "candidate_ledger_status": "promotion_blocked",
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "confidence": "None",
                },
                "primary_work": {
                    "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "reference_role": "primary",
                },
                "candidate_ledger": {
                    "title_candidates": [
                        {
                            "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                            "heretic_url": "https://novelpia.com/novel/382324",
                        }
                    ]
                },
                "reason": "- 공식 제목: 미확정 (promotion blocked; 후보로만 보존)",
            },
            "analysis": {"detected_titles": []},
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertIsNone(identity["heretic_url"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["primary_work"]["reference_role"], "candidate")
        self.assertEqual(identity["primary_work"]["promotion_policy"], "hold_without_promotion")
        self.assertTrue(identity["primary_work"]["blocked_by_candidate_audit"])

    def test_promotion_blocked_result_contract_preserves_blocked_title_in_stale_ledger_summary(self):
        correct_title = "가챠 중독자의 퓨전펑크 생활"
        correct_url = "https://novelpia.com/novel/387014"
        candidate = {
            "official_title": correct_title,
            "heretic_url": correct_url,
            "confidence": "High",
            "alias_or_mention": "가챠펑크",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
            "preservation_role": "title_candidate",
        }
        result = {
            "post_id": 11698880,
            "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
            "content": ["가챠펑크 세드릭도 그렇고"],
            "comments": [],
            "identity": {
                "official_title": None,
                "official_novel_title": None,
                "heretic_url": None,
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": correct_title,
                "blocked_official_title_url": correct_url,
                "context_sources": ["title", "body", "search"],
                "consistency_flags": ["unresolved_worklike_hold:alias_character_discussion"],
                "title_candidates": [dict(candidate)],
                "candidate_preservation_sources": [dict(candidate)],
                "candidate_ledger": {
                    "title_candidates": ["스폰지밥"],
                    "candidate_preservation_sources": [dict(candidate)],
                    "blocked_official_title": correct_title,
                    "blocked_official_title_url": correct_url,
                    "candidate_ledger_status": "promotion_blocked",
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": ["scope_context_only", "scope_not_current_work"],
                        "bypassed_gate": False,
                    },
                    "promotion_gate_state": {
                        "scope": {
                            "scope_kind": "context_only",
                            "confidence": "medium",
                            "conflict_reason_codes": ["unresolved_body_character_work_anchor"],
                        }
                    },
                },
            },
            "analysis": {"detected_titles": [dict(candidate)]},
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        ledger_candidates = identity["candidate_ledger"]["title_candidates"]
        self.assertEqual(ledger_candidates, ["스폰지밥", correct_title])
        self.assertEqual(identity["candidate_ledger"]["candidate_count"], 2)
        self.assertIsNone(identity["official_title"])
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertEqual(
            identity["publish_contract_trace"]["pre_gate_candidate"]["official_title"],
            correct_title,
        )

    def test_promotion_gate_blocked_result_contract_scrubs_nested_public_title(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "promotion_blocked",
                "novel_identity": {
                    "official_title": "잘생기면 인생이 편하다",
                    "heretic_url": "https://novelpia.com/novel/300042",
                    "confidence": "High",
                },
                "primary_work": {
                    "official_title": "잘생기면 인생이 편하다",
                    "heretic_url": "https://novelpia.com/novel/300042",
                    "reference_role": "primary",
                },
                "candidate_ledger": {
                    "pipeline_official_title": "잘생기면 인생이 편하다",
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": ["official_title_exists", "row_discussion_missing"],
                        "bypassed_gate": False,
                    },
                    "promotion_gate_state": {
                        "scope": {
                            "scope_kind": "previous_work",
                            "confidence": "high",
                            "direct_bridge_sources": ["comment_previous_work_alias"],
                            "competing_candidates": ["잘생기면 편해지는 인방 생활"],
                            "conflict_reason_codes": [
                                "current_work_candidate_competes_with_previous_work"
                            ],
                        }
                    },
                },
                "reason": "\n".join(
                    [
                        "- 공식 제목: '잘생기면 인생이 편하다'",
                        "- 최종 공식 제목은 '잘생기면 인생이 편하다'로 확정됨.",
                        "- heretic_url_platform: +3 (작품 상세 URL(플랫폼))",
                    ]
                ),
            },
            "analysis": {"detected_titles": []},
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["novel_identity"]["confidence"], "None")
        self.assertEqual(identity["blocked_official_title"], "잘생기면 인생이 편하다")
        self.assertEqual(identity["blocked_official_title_url"], "https://novelpia.com/novel/300042")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertFalse(identity["is_resolved_work_discussion"])
        self.assertIsNone(identity["candidate_ledger"]["pipeline_official_title"])
        self.assertEqual(identity["primary_work"]["reference_role"], "candidate")
        self.assertEqual(identity["primary_work"]["promotion_policy"], "hold_without_promotion")
        self.assertTrue(identity["primary_work"]["blocked_by_candidate_audit"])
        self.assertIn("공식 제목: 미확정", identity["reason"])
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "잘생기면 인생이 편하다")
        self.assertEqual(
            trace["pre_gate_candidate"]["official_url"],
            "https://novelpia.com/novel/300042",
        )
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertFalse(trace["gate_decision"]["bypassed_gate"])
        self.assertEqual(trace["scope_state"]["scope_kind"], "previous_work")
        self.assertEqual(trace["gate_decision"]["scope"]["scope_kind"], "previous_work")
        self.assertIn("scope_previous_work", trace["reason_codes"])
        self.assertIn("scope_not_current_work", trace["reason_codes"])
        self.assertIn(
            "current_work_candidate_competes_with_previous_work",
            trace["reason_codes"],
        )
        self.assertFalse(trace["post_gate_identity"]["title_resolution_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])
        self.assertIn("serialized_public_identity_scrubbed", trace["reason_codes"])
        self.assertEqual(identity["candidate_ledger"]["publish_contract_trace"], trace)
        publish_ledger = identity["publish_ledger"]
        self.assertEqual(publish_ledger["candidate_preservation"], trace["pre_gate_candidate"])
        self.assertEqual(publish_ledger["public_publish"], trace["post_gate_identity"])
        self.assertEqual(identity["candidate_ledger"]["publish_ledger"], publish_ledger)

    def test_blocked_final_publication_overwrites_stale_publish_decision(self):
        result = {
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "탑의 성좌들이 날 애호한다",
                "blocked_official_title_url": "https://novelpia.com/novel/377032",
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": None,
                    "confidence": "None",
                },
                "candidate_ledger": {
                    "blocked_official_title": "탑의 성좌들이 날 애호한다",
                    "blocked_official_title_url": "https://novelpia.com/novel/377032",
                    "promotion_decision": {
                        "status": "publish",
                        "publish_allowed": True,
                        "official_title": "탑의 성좌들이 날 애호한다",
                        "official_url": "https://novelpia.com/novel/377032",
                        "candidate_preserved": False,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                        ],
                        "bypassed_gate": False,
                    },
                },
            }
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace_decision = identity["publish_contract_trace"]["gate_decision"]
        self.assertEqual(trace_decision["status"], "candidate_only")
        self.assertFalse(trace_decision["publish_allowed"])
        self.assertIsNone(trace_decision["official_title"])
        self.assertEqual(identity["publish_contract_trace"]["scope_state"]["scope_kind"], "current_work")
        self.assertEqual(identity["promotion_decision"], trace_decision)
        self.assertEqual(identity["candidate_ledger"]["promotion_decision"], trace_decision)
        self.assertEqual(identity["publish_ledger"]["gate_decision"], trace_decision)

    def test_blocked_current_work_shared_gate_restores_exact_title_publication(self):
        result = {
            "post_id": 11661876,
            "title": "와인의신 재밌다",
            "content": ["클로이가 정실임", "와그리고 미국은 진짜 토마토를 톤당 5만원에 도매치냐?"],
            "comments": ["난 문피아에서 봣읍니다 - dc App"],
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "discussion_type": "general",
                "candidate_ledger_status": "promotion_blocked",
                "anchor_type": "platform",
                "anchor_strength": "medium",
                "context_sources": ["title", "body", "comments", "search"],
                "blocked_official_title": "와인의 신",
                "blocked_official_title_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                "novel_identity": None,
                "consistency_flags": [
                    "external_ip_unresolved_hold_blocked",
                    "external_ip_unresolved_final_blocked",
                    "decoder_exact_post_title_surface_resolved",
                    "official_detail_url_repaired_from_search",
                    "weak_alias_surface_public_title_bridge",
                ],
                "title_candidates": [
                    {
                        "official_title": "와인의 신",
                        "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                        "reference_role": "candidate",
                    }
                ],
                "candidate_ledger": {
                    "blocked_official_title": "와인의 신",
                    "blocked_official_title_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                    "context_sources": ["title", "body", "comments", "search"],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "와인의 신",
                            "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                            "reference_role": "candidate",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "context_only",
                            "scope_current_work",
                            "official_detail_url",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": ["row_discusses_work_as_work"],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "와인의 신",
                        "candidate_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": ["row_discusses_work_as_work"],
                        },
                    },
                },
                "reason_lines": [
                    "- 공식 제목: 미확정 (promotion blocked; 후보로만 보존)",
                    "- 핵심 결론: 웹소설/장르 맥락은 보이나 단일 공식 제목을 확정할 직접 증거가 부족하여 제목 지목을 보류했습니다.",
                    "- public title promotion blocked: serialized output kept candidate/HOLD",
                ],
            },
            "analysis": {
                "detected_titles": [
                    {
                        "official_title": "와인의 신",
                        "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                        "reference_role": "candidate",
                        "promotion_policy": "hold_without_promotion",
                        "blocked_by_candidate_audit": True,
                        "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                    }
                ]
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertEqual(identity["title_resolution_state"], "resolved")
        self.assertEqual(identity["work_resolution"], "resolved")
        self.assertTrue(identity["is_resolved_work_discussion"])
        self.assertEqual(identity["novel_identity"]["official_title"], "와인의 신")
        self.assertEqual(
            identity["novel_identity"]["heretic_url"],
            "https://series.naver.com/novel/detail.series?productNo=13342533",
        )
        self.assertEqual(identity["primary_work"]["reference_role"], "primary")
        self.assertNotIn("weak_alias_surface_public_title_bridge", identity["consistency_flags"])
        self.assertIn("serialized_public_identity_shared_gate_restored", identity["consistency_flags"])
        self.assertNotIn("public title promotion blocked", identity["reason"])
        self.assertIn("공식 제목: '와인의 신'", identity["reason"])
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["gate_decision"]["status"], "publish")
        self.assertTrue(trace["gate_decision"]["publish_allowed"])
        self.assertEqual(trace["scope_state"]["scope_kind"], "current_work")
        self.assertIn("serialized_public_identity_shared_gate_restored", trace["reason_codes"])
        candidate = identity["candidate_ledger"]["candidate_preservation_sources"][0]
        self.assertEqual(candidate["reference_role"], "primary")
        self.assertIsNone(candidate.get("negative_evidence"))
        detected = result["analysis"]["detected_titles"][0]
        self.assertEqual(detected["reference_role"], "primary")
        self.assertIsNone(detected.get("negative_evidence"))

    def test_inner_analysis_payload_uses_caller_post_title_for_shared_gate_restore(self):
        result = {
            "post_id": 11661876,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "anchor_type": "platform",
                "context_sources": ["title", "body", "comments", "search"],
                "blocked_official_title": "와인의 신",
                "blocked_official_title_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                "consistency_flags": [
                    "decoder_exact_post_title_surface_resolved",
                    "official_detail_url_repaired_from_search",
                    "weak_alias_surface_public_title_bridge",
                ],
                "candidate_ledger": {
                    "blocked_official_title": "와인의 신",
                    "blocked_official_title_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                    "context_sources": ["title", "body", "comments", "search"],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "와인의 신",
                            "heretic_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                            "reference_role": "candidate",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "official_detail_url",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": ["row_discusses_work_as_work"],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "와인의 신",
                        "candidate_url": "https://series.naver.com/novel/detail.series?productNo=13342533",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": ["row_discusses_work_as_work"],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result, post_title="와인의신 재밌다")

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["title_resolution_state"], "resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "와인의 신")
        reason_codes = identity["promotion_decision"]["reason_codes"]
        self.assertIn("serialized_public_identity_shared_gate_restored", reason_codes)
        self.assertIn("serialized_public_identity_published", reason_codes)

    def test_direct_image_character_title_shared_gate_restores_publication(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["주서연이 전차랑 줄다리기 하는 이미지"],
            "comments": ["전 버튜버가 하고 싶은데요 주인공"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "primary_subject_type": "specific_work",
                "anchor_type": "character",
                "anchor_strength": "high",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "전 버튜버가 하고 싶은데요",
                "blocked_official_title_url": "https://novelpia.com/novel/275975",
                "consistency_flags": [
                    "direct_image_explicit_title_rescued",
                    "verified_alias_official_detail_anchor",
                    "confirmed_alias:주서연",
                    "weak_alias_surface_public_title_bridge",
                ],
                "primary_work": {
                    "official_title": "전 버튜버가 하고 싶은데요",
                    "heretic_url": "https://novelpia.com/novel/275975",
                    "alias_or_mention": "주서연",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "candidate",
                    "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                },
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": True,
                        "title_role": "work_title",
                        "evidence_type": "ocr_title",
                        "explicit_work_title": "전 버튜버가 하고 싶은데요",
                    }
                ],
                "verified_character_work_links": [
                    {
                        "character": "주서연",
                        "official_title": "전 버튜버가 하고 싶은데요",
                        "heretic_url": "https://novelpia.com/novel/275975",
                    }
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "전 버튜버가 하고 싶은데요",
                            "heretic_url": "https://novelpia.com/novel/275975",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "candidate",
                            "promotion_policy": "hold_without_promotion",
                            "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "official_detail_url",
                            "direct_image_explicit_title_rescued",
                            "verified_alias_official_detail_anchor",
                            "weak_alias_surface_public_title_bridge",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "image_ocr_work_title",
                                "direct_image_explicit_title_rescued",
                                "verified_character_work_link",
                                "official_detail_url",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "전 버튜버가 하고 싶은데요",
                        "candidate_url": "https://novelpia.com/novel/275975",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "image_ocr_work_title",
                                "direct_image_explicit_title_rescued",
                                "verified_character_work_link",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["title_resolution_state"], "resolved")
        self.assertEqual(identity["work_resolution"], "resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "전 버튜버가 하고 싶은데요")
        self.assertEqual(identity["novel_identity"]["heretic_url"], "https://novelpia.com/novel/275975")
        self.assertNotIn("weak_alias_surface_public_title_bridge", identity["consistency_flags"])
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["gate_decision"]["status"], "publish")
        self.assertTrue(trace["gate_decision"]["publish_allowed"])
        self.assertIn("direct_image_explicit_title_rescued", trace["scope_state"]["direct_bridge_sources"])
        self.assertIn("verified_character_work_link", trace["scope_state"]["direct_bridge_sources"])
        self.assertEqual(identity["candidate_ledger"]["promotion_decision"], trace["gate_decision"])

    def test_direct_image_exact_cover_title_restores_precision_seed_hold(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데"],
            "comments": ["주서연이 클리로 줄다리기해야 아슬아슬하게 대결 성립됨"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "primary_subject_type": "specific_work",
                "anchor_type": "character_mention",
                "anchor_strength": "high",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "전 버튜버가 하고 싶은데요",
                "blocked_official_title_url": "https://novelpia.com/novel/275975",
                "consistency_flags": [
                    "multi_work_title_cleared",
                    "direct_image_explicit_title_rescued",
                    "llm_only_sentence_candidate_pruned",
                ],
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": False,
                        "title_role": "unknown",
                        "evidence_type": "cover_title",
                        "explicit_work_title": "전 버튜버가 하고 싶은데요",
                    }
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "전 버튜버가 하고 싶은데요",
                            "heretic_url": "https://novelpia.com/novel/275975",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "candidate",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "resolved_public_title_scope",
                            "official_detail_url",
                            "precision_seed_official_title_requires_review",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "body",
                                "comments",
                                "search",
                                "image",
                                "anchor_type:image",
                                "official_detail_url",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "전 버튜버가 하고 싶은데요",
                        "candidate_url": "https://novelpia.com/novel/275975",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "body",
                                "comments",
                                "search",
                                "image",
                                "anchor_type:image",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "전 버튜버가 하고 싶은데요")
        trace = identity["publish_contract_trace"]
        self.assertTrue(trace["gate_decision"]["publish_allowed"])
        self.assertIn("image_ocr_official_detail_title", trace["gate_decision"]["reason_codes"])
        self.assertIn("direct_image_explicit_title_rescued", trace["scope_state"]["direct_bridge_sources"])

    def test_direct_image_character_parenthetical_bridge_restores_ocr_variant_hold(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데"],
            "comments": ["전차 주제에 주서연이랑 비비려하네"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "primary_subject_type": "specific_work",
                "anchor_type": "character_mention",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "전 버튜버가 하고 싶은데요",
                "blocked_official_title_url": "https://novelpia.com/novel/275975",
                "consistency_flags": [
                    "image_ocr_variant_not_title_in_post",
                    "multi_work_title_cleared",
                    "direct_image_explicit_title_rescued",
                    "llm_only_sentence_candidate_pruned",
                ],
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": False,
                        "title_role": "unknown",
                        "evidence_type": "cover_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "explicit_work_title": "전 버두바가 하고 싶은데요",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "전 버튜버가 하고 싶은데요",
                        "url": "https://novelpia.com/novel/275975",
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "플라나리아햄버거. 주서연.",
                    },
                    {
                        "title": "주서연(전 버튜버가 하고 싶은데요) - 나무위키",
                        "url": "https://namu.wiki/w/주서연(전%20버튜버가%20하고%20싶은데요)",
                        "domain": "namu.wiki",
                        "source_tier": "wiki",
                        "snippet": "주서연은 전 버튜버가 하고 싶은데요의 주인공이다.",
                    },
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "전 버튜버가 하고 싶은데요",
                            "heretic_url": "https://novelpia.com/novel/275975",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "direct_image_work_surface_bridge",
                            "ocr_catalog_official_title",
                            "official_detail_url",
                            "precision_seed_official_title_requires_review",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "direct_image_work_surface_lock",
                                "structured_direct_image_work_surface",
                                "ocr_catalog_official_title",
                                "official_detail_url",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "전 버튜버가 하고 싶은데요",
                        "candidate_url": "https://novelpia.com/novel/275975",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "direct_image_work_surface_lock",
                                "structured_direct_image_work_surface",
                                "ocr_catalog_official_title",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "전 버튜버가 하고 싶은데요")
        trace = identity["publish_contract_trace"]
        self.assertTrue(trace["gate_decision"]["publish_allowed"])
        self.assertIn("search_character_parenthetical_bridge", trace["gate_decision"]["reason_codes"])
        self.assertIn("direct_image_work_surface_bridge", trace["scope_state"]["direct_bridge_sources"])
        self.assertIn("search_character_parenthetical_bridge", trace["scope_state"]["direct_bridge_sources"])

    def test_direct_image_ocr_publish_canonicalizes_from_search_snippet_bridge(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데"],
            "comments": ["전차 주제에 주서연이랑 비비려하네"],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "context_sources": ["title", "body", "comments", "image", "search"],
                "consistency_flags": [
                    "platform_meta_multi_title_blocked",
                    "direct_image_explicit_title_rescued",
                ],
                "novel_identity": {
                    "official_title": "전 버디가 하고 싶은데요",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": True,
                        "title_role": "work_title",
                        "evidence_type": "cover_title",
                        "explicit_work_title": "전 버디가 하고 싶은데요",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "괴력녀 - 나무위키",
                        "url": "https://namu.wiki/w/example",
                        "domain": "namu.wiki",
                        "source_tier": "wiki",
                        "snippet": "전 버튜버가 하고 싶은데요 - 주서연. 철완 버디 - 버디 시폰 알티라.",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "전 버디가 하고 싶은데요",
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "direct_image_work_surface_bridge",
                        "ocr_catalog_official_title",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "direct_image_work_surface_lock",
                            "structured_direct_image_work_surface",
                            "ocr_catalog_official_title",
                        ],
                    },
                },
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["novel_identity"]["official_title"], "전 버튜버가 하고 싶은데요")
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        decision = identity["promotion_decision"]
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], "전 버튜버가 하고 싶은데요")
        self.assertIn("direct_image_ocr_search_canonicalized", decision["reason_codes"])
        self.assertIn("search_character_parenthetical_bridge", decision["reason_codes"])

    def test_direct_image_ocr_publish_uses_runtime_post_title_bridge_argument(self):
        result = {
            "post_id": 11663540,
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "context_sources": ["title", "image", "search"],
                "novel_identity": {
                    "official_title": "전 버디가 하고 싶은데요",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "search_evidence_catalog": [
                    {
                        "title": "괴력녀 - 나무위키",
                        "url": "https://namu.wiki/w/example",
                        "domain": "namu.wiki",
                        "source_tier": "wiki",
                        "snippet": "전 버튜버가 하고 싶은데요 - 주서연.",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "전 버디가 하고 싶은데요",
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "direct_image_work_surface_bridge",
                        "ocr_catalog_official_title",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "direct_image_work_surface_lock",
                            "structured_direct_image_work_surface",
                            "ocr_catalog_official_title",
                        ],
                    },
                },
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="TS) 주서연 전차랑 줄다리기 하면 이길까?",
        )

        self.assertTrue(changed)
        decision = result["identity"]["promotion_decision"]
        self.assertEqual(decision["official_title"], "전 버튜버가 하고 싶은데요")
        self.assertIn("direct_image_ocr_search_canonicalized", decision["reason_codes"])

    def test_direct_image_ocr_variant_without_parenthetical_bridge_stays_blocked(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데"],
            "comments": ["전차 주제에 주서연이랑 비비려하네"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "전 버튜버가 하고 싶은데요",
                "blocked_official_title_url": "https://novelpia.com/novel/275975",
                "consistency_flags": [
                    "image_ocr_variant_not_title_in_post",
                    "direct_image_explicit_title_rescued",
                ],
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": False,
                        "title_role": "unknown",
                        "evidence_type": "cover_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "explicit_work_title": "전 버두바가 하고 싶은데요",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "전 버튜버가 하고 싶은데요",
                        "url": "https://novelpia.com/novel/275975",
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "플라나리아햄버거. 주서연.",
                    }
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "전 버튜버가 하고 싶은데요",
                            "heretic_url": "https://novelpia.com/novel/275975",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "direct_image_work_surface_bridge",
                            "ocr_catalog_official_title",
                            "official_detail_url",
                            "precision_seed_official_title_requires_review",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "direct_image_work_surface_lock",
                                "structured_direct_image_work_surface",
                                "ocr_catalog_official_title",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity.get("novel_identity", {}).get("official_title"))
        self.assertFalse(identity["publish_contract_trace"]["gate_decision"]["publish_allowed"])
        self.assertNotIn(
            "search_character_parenthetical_bridge",
            identity["publish_contract_trace"]["gate_decision"]["reason_codes"],
        )

    def test_unverified_direct_image_ocr_publication_without_official_bridge_is_held(self):
        result = {
            "post_id": 11685994,
            "title": "교황님 아 하세요 표지",
            "content": [""],
            "comments": [],
            "image_count": 1,
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "context_sources": ["image"],
                "consistency_flags": ["direct_image_explicit_title_rescued"],
                "novel_identity": {
                    "official_title": "교황님 아하세요 마왕 들어 가요",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": True,
                        "title_role": "work_title",
                        "evidence_type": "ocr_title",
                        "explicit_work_title": "교황님 아 하세요 마왕들어가요",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "축구 천재로 태어난 교황님",
                        "url": "https://page.kakao.com/content/56516207",
                        "domain": "page.kakao.com",
                        "source_tier": "novel_platform",
                        "snippet": "교황 후보 단어만 겹치는 별도 작품.",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "교황님 아하세요 마왕 들어 가요",
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "image_ocr_work_title",
                        "direct_image_explicit_title_rescued",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "image_ocr_work_title",
                            "direct_image_explicit_title_rescued",
                        ],
                    },
                },
                "candidate_ledger": {
                    "promotion_gate_state": {
                        "candidate_title": "교황님 아하세요 마왕 들어 가요",
                        "candidate_url": "",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "image_ocr_work_title",
                                "direct_image_explicit_title_rescued",
                            ],
                        },
                    }
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(identity["title_resolution_state"], "ocr_explicit_title_unresolved")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIn(
            "unverified_promoted_image_work_title_without_official_support",
            identity["promotion_blocked_reasons"],
        )
        decision = identity["publish_contract_trace"]["gate_decision"]
        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "unverified_promoted_image_work_title_without_official_support",
            decision["reason_codes"],
        )
        preserved = identity["candidate_ledger"]["candidate_preservation_sources"]
        self.assertEqual(preserved[0]["official_title"], "교황님 아하세요 마왕 들어 가요")

    def test_final_reread_url_title_verified_detail_restores_precision_seed_hold(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데"],
            "comments": ["전차 주제에 주서연이랑 비비려하네"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "primary_subject_type": "specific_work",
                "anchor_type": "character_mention",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "전 버튜버가 하고 싶은데요",
                "blocked_official_title_url": "https://novelpia.com/novel/275975",
                "consistency_flags": [
                    "image_ocr_variant_not_title_in_post",
                    "official_detail_url_repaired_from_search",
                    "final_semantic_reread_reviewed",
                    "final_semantic_reread_accepted_resolution",
                ],
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": False,
                        "title_role": "unknown",
                        "evidence_type": "cover_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "explicit_work_title": "전 버튜바가 하고 싶은데요",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "전 버튜버가 하고 싶은데요",
                        "url": "https://novelpia.com/novel/275975",
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "노벨피아 작품 상세. 주서연.",
                    }
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "전 버튜버가 하고 싶은데요",
                            "heretic_url": "https://novelpia.com/novel/275975",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "resolved_public_title_scope",
                            "official_detail_url",
                            "precision_seed_official_title_requires_review",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "body",
                                "comments",
                                "search",
                                "image",
                                "anchor_type:image",
                                "official_detail_url",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "전 버튜버가 하고 싶은데요",
                        "candidate_url": "https://novelpia.com/novel/275975",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "title_resolution_state": "resolved",
                        "work_resolution": "resolved",
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "body",
                                "comments",
                                "search",
                                "image",
                                "anchor_type:image",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "전 버튜버가 하고 싶은데요")
        trace = identity["publish_contract_trace"]
        self.assertTrue(trace["gate_decision"]["publish_allowed"])
        self.assertIn("url_title_verified_official_detail", trace["gate_decision"]["reason_codes"])
        self.assertIn("final_semantic_reread_accepted_resolution", trace["scope_state"]["direct_bridge_sources"])

    def test_url_title_verified_detail_requires_direct_source_support(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["전 버두비가 하고 싶은데요", "태양을 숨긴 달"],
            "comments": ["전차 주제에 주서연이랑 비비려하네"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "primary_subject_type": "specific_work",
                "anchor_type": "image",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)",
                "blocked_official_title_url": "https://novelpia.com/novel/427233",
                "consistency_flags": [
                    "final_semantic_reread_reviewed",
                    "final_semantic_reread_accepted_resolution",
                    "official_url_recall_candidate_preserved",
                ],
                "novel_identity": {
                    "official_title": "두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)",
                    "heretic_url": "https://novelpia.com/novel/427233",
                },
                "search_evidence_catalog": [
                    {
                        "title": "두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)",
                        "url": "https://novelpia.com/novel/427233",
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "검색 결과 묶음에 섞인 별도 작품.",
                    },
                    {
                        "title": "전 버튜버가 하고 싶은데요 - 나무위키",
                        "url": "https://namu.wiki/w/전%20버튜버가%20하고%20싶은데요",
                        "domain": "namu.wiki",
                        "source_tier": "wiki",
                        "snippet": "주서연은 전 버튜버가 하고 싶은데요의 주인공이다.",
                    },
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)",
                            "heretic_url": "https://novelpia.com/novel/427233",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                            "matched_clue": "official_detail_candidate_cue:주인공",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "resolved_public_title_scope",
                            "official_detail_url",
                            "precision_seed_official_title_requires_review",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "medium",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "body",
                                "comments",
                                "search",
                                "image",
                                "anchor_type:image",
                                "official_detail_url",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)",
                        "candidate_url": "https://novelpia.com/novel/427233",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "title_resolution_state": "resolved",
                        "work_resolution": "resolved",
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "medium",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "body",
                                "comments",
                                "search",
                                "image",
                                "anchor_type:image",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity.get("novel_identity", {}).get("official_title"))
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIn("official_detail_url_missing_direct_source_support", identity["consistency_flags"])
        candidate = identity["candidate_ledger"]["candidate_preservation_sources"][0]
        self.assertIn("official_detail_url_missing_direct_source_support", candidate["negative_evidence"])

    def test_direct_image_character_bridge_blocks_mismatched_official_url_title(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["내가 봤을땐 이 고릴라년이 가볍게 이길것 같은데"],
            "comments": ["전차 주제에 주서연이랑 비비려하네"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "primary_subject_type": "specific_work",
                "anchor_type": "character_mention",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "전 버튜버가 하고 싶은데요",
                "blocked_official_title_url": "https://novelpia.com/novel/311328",
                "consistency_flags": [
                    "image_ocr_variant_not_title_in_post",
                    "official_detail_url_repaired_from_search",
                    "final_semantic_reread_accepted_resolution",
                    "direct_image_explicit_title_rescued",
                ],
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": False,
                        "title_role": "unknown",
                        "evidence_type": "cover_title",
                        "focus_role": "work_anchor",
                        "screen_type": "work_surface",
                        "explicit_work_title": "전 버튜바가 하고 싶은데요",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "버튜버를 동경하여 버튜버가 되고 싶은 한 소녀와 동경하는 버튜버의 매니저인 소년의 만남",
                        "url": "https://novelpia.com/novel/311328",
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "아무래도 내 최애가 이들 중 있는 것 같다.",
                    },
                    {
                        "title": "주서연(전 버튜버가 하고 싶은데요) - 나무위키",
                        "url": "https://namu.wiki/w/주서연(전%20버튜버가%20하고%20싶은데요)",
                        "domain": "namu.wiki",
                        "source_tier": "wiki",
                        "snippet": "주서연은 전 버튜버가 하고 싶은데요의 주인공이다.",
                    },
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "전 버튜버가 하고 싶은데요",
                            "heretic_url": "https://novelpia.com/novel/311328",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "direct_image_work_surface_bridge",
                            "official_detail_url",
                            "precision_seed_official_title_requires_review",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "direct_image_work_surface_lock",
                                "structured_direct_image_work_surface",
                                "official_detail_url",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "전 버튜버가 하고 싶은데요",
                        "candidate_url": "https://novelpia.com/novel/311328",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "direct_image_work_surface_lock",
                                "structured_direct_image_work_surface",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity.get("novel_identity", {}).get("official_title"))
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIn(
            "official_detail_url_title_mismatch_publish_blocked",
            identity["consistency_flags"],
        )
        preserved = identity["candidate_ledger"]["candidate_preservation_sources"][0]
        self.assertIn("url_title_mismatch", preserved["negative_evidence"])

    def test_published_official_url_demotes_same_url_detail_title_mismatch(self):
        official_url = "https://novelpia.com/novel/302245"
        result = {
            "post_id": 11705245,
            "title": "하남자 재밌냐",
            "content": ["주인공 첨부터쌤?"],
            "comments": ["ㄴㄴ"],
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "context_sources": ["title", "body", "comments", "search", "image"],
                "novel_identity": {
                    "official_title": "하남 남자",
                    "heretic_url": official_url,
                    "confidence": "Low",
                },
                "primary_work": {
                    "official_title": "하남 남자",
                    "heretic_url": official_url,
                    "confidence": "High",
                    "alias_or_mention": "하남자",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "negative_evidence": ["missing_official_url_for_official_detail"],
                    "reference_role": "primary",
                },
                "title_candidates": [
                    {
                        "official_title": "하남 남자",
                        "heretic_url": official_url,
                        "confidence": "High",
                        "alias_or_mention": "하남자",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "negative_evidence": ["missing_official_url_for_official_detail"],
                        "reference_role": "primary",
                    },
                    {
                        "official_title": "하남자는 딸깍충이 되고 싶다",
                        "heretic_url": official_url,
                        "confidence": "High",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "content_status": "active",
                        "reference_role": "candidate",
                    },
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "하남 남자",
                        "heretic_url": official_url,
                        "confidence": "High",
                        "alias_or_mention": "하남자",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "negative_evidence": ["missing_official_url_for_official_detail"],
                        "reference_role": "primary",
                        "preservation_role": "title_candidate",
                    },
                    {
                        "official_title": "하남자는 딸깍충이 되고 싶다",
                        "heretic_url": official_url,
                        "confidence": "High",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "content_status": "active",
                        "reference_role": "candidate",
                        "preservation_role": "title_candidate",
                    },
                ],
                "search_evidence_catalog": [
                    {
                        "title": "노벨피아",
                        "url": official_url,
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "노벨피아 - 웹소설로 꿈꾸는 세상! - 하남자는 딸깍충이 되고 싶다 플러스작품",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "하남 남자",
                    "official_url": official_url,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "context_only",
                        "scope_current_work",
                        "official_detail_url",
                        "work_consumption_marker",
                        "thematic_overlap_only",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": ["row_discusses_work_as_work"],
                    },
                },
                "candidate_ledger": {
                    "title_candidates": [
                        {
                            "official_title": "하남 남자",
                            "heretic_url": official_url,
                            "confidence": "High",
                            "alias_or_mention": "하남자",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "negative_evidence": ["missing_official_url_for_official_detail"],
                            "reference_role": "primary",
                        },
                        {
                            "official_title": "하남자는 딸깍충이 되고 싶다",
                            "heretic_url": official_url,
                            "confidence": "High",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "content_status": "active",
                            "reference_role": "candidate",
                        },
                    ],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "하남 남자",
                            "heretic_url": official_url,
                            "confidence": "High",
                            "alias_or_mention": "하남자",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "negative_evidence": ["missing_official_url_for_official_detail"],
                            "reference_role": "primary",
                            "preservation_role": "title_candidate",
                        },
                        {
                            "official_title": "하남자는 딸깍충이 되고 싶다",
                            "heretic_url": official_url,
                            "confidence": "High",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "content_status": "active",
                            "reference_role": "candidate",
                            "preservation_role": "title_candidate",
                        },
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="하남자 재밌냐",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity.get("novel_identity", {}).get("official_title"))
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertIn("url_title_mismatch", identity["promotion_decision"]["reason_codes"])
        self.assertIn(
            "official_detail_url_title_mismatch_publish_blocked",
            identity["consistency_flags"],
        )
        preserved = identity["candidate_ledger"]["candidate_preservation_sources"][0]
        self.assertIn("url_title_mismatch", preserved["negative_evidence"])
        self.assertTrue(str(preserved.get("url_title_mismatch_title") or "").strip())

    def test_context_only_thematic_overlap_publish_demotes_without_hard_bridge(self):
        official_url = "https://novelpia.com/novel/302245"
        stale_gate_url = "https://novelpia.com/novel/315683"
        result = {
            "post_id": 11705245,
            "title": "하남자 재밌냐",
            "content": ["주인공 첨부터쌤?"],
            "comments": ["ㄴㄴ"],
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "context_sources": ["title", "body", "comments", "search", "image"],
                "novel_identity": {
                    "official_title": "하남 남자",
                    "heretic_url": official_url,
                    "confidence": "Low",
                },
                "primary_work": {
                    "official_title": "하남 남자",
                    "heretic_url": official_url,
                    "confidence": "High",
                    "alias_or_mention": "하남자",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "reference_role": "primary",
                },
                "search_evidence_catalog": [
                    {
                        "title": "노벨피아",
                        "url": official_url,
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "노벨피아 - 웹소설로 꿈꾸는 세상! - 하남자는 딸깍충이 되고 싶다 플러스작품",
                    },
                    {
                        "title": "하남자 매니저가 로또 1등을 숨김",
                        "url": stale_gate_url,
                        "domain": "novelpia.com",
                        "source_tier": "novel_platform",
                        "snippet": "작품 상세",
                    },
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "하남 남자",
                    "official_url": official_url,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "context_only",
                        "scope_current_work",
                        "official_detail_url",
                        "work_consumption_marker",
                        "alias_bridge",
                        "thematic_overlap_only",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": ["row_discusses_work_as_work"],
                    },
                },
                "promotion_gate_state": {
                    "candidate_title": "하남 남자",
                    "candidate_url": stale_gate_url,
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "title_resolution_state": "context_only",
                    "work_resolution": "unresolved",
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": ["row_discusses_work_as_work"],
                    },
                },
                "candidate_ledger": {
                    "title_candidates": [
                        {
                            "official_title": "하남 남자",
                            "heretic_url": official_url,
                            "confidence": "High",
                            "alias_or_mention": "하남자",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                        }
                    ],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "하남 남자",
                            "heretic_url": official_url,
                            "confidence": "High",
                            "alias_or_mention": "하남자",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                            "preservation_role": "title_candidate",
                        }
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="하남자 재밌냐",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertIsNone(identity.get("novel_identity", {}).get("official_title"))
        self.assertIn(
            "context_only_thematic_overlap_publish_blocked",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertIn(
            "context_only_thematic_overlap_publish_blocked",
            identity["consistency_flags"],
        )
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])

    def test_direct_image_character_restore_blocks_wrong_work_without_matching_ocr_title(self):
        result = {
            "post_id": 11663540,
            "title": "TS) 주서연 전차랑 줄다리기 하면 이길까?",
            "content": ["주서연 이미지"],
            "comments": ["전 버튜버가 하고 싶은데요 주인공"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "primary_subject_type": "specific_work",
                "anchor_type": "character",
                "context_sources": ["title", "body", "comments", "image", "search"],
                "blocked_official_title": "방구석 여신이 되었다",
                "blocked_official_title_url": "https://novelpia.com/novel/111111",
                "consistency_flags": [
                    "direct_image_explicit_title_rescued",
                    "weak_alias_surface_public_title_bridge",
                ],
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": True,
                        "title_role": "work_title",
                        "evidence_type": "ocr_title",
                        "explicit_work_title": "전 버튜버가 하고 싶은데요",
                    }
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "방구석 여신이 되었다",
                            "heretic_url": "https://novelpia.com/novel/111111",
                            "source_tier": "official_detail",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "official_detail_url",
                            "direct_image_explicit_title_rescued",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "image_ocr_work_title",
                                "direct_image_explicit_title_rescued",
                                "official_detail_url",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "방구석 여신이 되었다",
                        "candidate_url": "https://novelpia.com/novel/111111",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "image_ocr_work_title",
                                "direct_image_explicit_title_rescued",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity.get("novel_identity", {}).get("official_title"))
        self.assertFalse(identity["publish_contract_trace"]["gate_decision"]["publish_allowed"])
        self.assertTrue(identity["publish_contract_trace"]["gate_decision"]["candidate_preserved"])

    def test_title_led_current_work_scope_restores_alias_candidate_publication(self):
        result = {
            "post_id": 11660257,
            "title": "암흑가보스<<이거 재밋네",
            "content": [],
            "comments": [],
            "image_count": 2,
            "identity": {
                "is_relevant": True,
                "is_novel_related": True,
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "discussion_type": "general",
                "is_resolved_work_discussion": False,
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "암흑가 보스요? 제가요?",
                "blocked_official_title_url": "https://novelpia.com/novel/384111",
                "anchor_type": "none",
                "context_sources": ["title", "search", "image"],
                "consistency_flags": [
                    "unresolved_worklike_hold:title_led_consumption",
                    "locked_official_candidate_rescued",
                    "weak_public_title_bridge_locked_official_exempt",
                    "weak_alias_surface_public_title_bridge",
                ],
                "primary_work": {
                    "official_title": "암흑가 보스요? 제가요?",
                    "heretic_url": "https://novelpia.com/novel/384111",
                    "confidence": "High",
                    "alias_or_mention": "암흑가보스",
                    "source_tier": "official_detail",
                    "page_type": "novel_page",
                    "locked": True,
                    "promotion_policy": "hold_without_promotion",
                    "blocked_by_candidate_audit": True,
                },
                "candidate_ledger": {
                    "blocked_official_title": "암흑가 보스요? 제가요?",
                    "blocked_official_title_url": "https://novelpia.com/novel/384111",
                    "context_sources": ["title", "search", "image"],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "암흑가 보스요? 제가요?",
                            "heretic_url": "https://novelpia.com/novel/384111",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "candidate",
                            "alias_or_mention": "암흑가보스",
                            "promotion_policy": "hold_without_promotion",
                            "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                        }
                    ],
                    "promotion_decision": {
                        "status": "candidate_only",
                        "publish_allowed": False,
                        "official_title": None,
                        "official_url": None,
                        "candidate_preserved": True,
                        "reason_codes": [
                            "official_title_exists",
                            "row_discusses_work_as_work",
                            "scope_current_work",
                            "resolved_public_title_scope",
                            "official_detail_url",
                            "weak_alias_surface_public_title_bridge",
                            "serialized_public_identity_scrubbed",
                        ],
                        "bypassed_gate": False,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "image",
                                "anchor_type:none",
                                "official_detail_url",
                                "title_led_consumption_bridge",
                            ],
                        },
                    },
                    "promotion_gate_state": {
                        "candidate_title": "암흑가 보스요? 제가요?",
                        "candidate_url": "https://novelpia.com/novel/384111",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "title_resolution_state": "resolved",
                        "work_resolution": "resolved",
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "resolved_public_title_scope",
                                "title",
                                "image",
                                "anchor_type:none",
                                "official_detail_url",
                                "title_led_consumption_bridge",
                            ],
                        },
                    },
                },
            },
            "analysis": {
                "detected_titles": [
                    {
                        "official_title": "암흑가 보스요? 제가요?",
                        "heretic_url": "https://novelpia.com/novel/384111",
                        "reference_role": "candidate",
                        "promotion_policy": "hold_without_promotion",
                        "blocked_by_candidate_audit": True,
                        "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                    }
                ]
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertEqual(identity["title_resolution_state"], "resolved")
        self.assertEqual(identity["work_resolution"], "resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "암흑가 보스요? 제가요?")
        self.assertEqual(identity["novel_identity"]["heretic_url"], "https://novelpia.com/novel/384111")
        self.assertNotIn("weak_alias_surface_public_title_bridge", identity["consistency_flags"])
        reason_codes = identity["promotion_decision"]["reason_codes"]
        self.assertIn("serialized_public_identity_shared_gate_restored", reason_codes)
        self.assertIn("title_led_consumption_bridge", identity["promotion_decision"]["scope"]["direct_bridge_sources"])
        self.assertEqual(identity["publish_contract_trace"]["scope_state"]["scope_kind"], "current_work")

    def test_blocked_exact_alias_image_context_records_context_only_scope(self):
        result = {
            "post_id": 11660257,
            "title": "암흑가보스<<이거 재밋네",
            "content": [],
            "comments": [],
            "image_count": 2,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "none",
                "discussion_type": "noise",
                "topicality": "unrelated",
                "is_resolved_work_discussion": False,
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "암흑가 보스요? 제가요?",
                "blocked_official_title_url": "https://novelpia.com/novel/384111",
                "anchor_type": "none",
                "context_sources": ["title", "body", "image"],
                "candidate_audit_lint": ["image_scene_cues_unverified_public_title_bridge"],
                "consistency_flags": [
                    "batch_memory_alias_rescue_blocked_nonwork_context",
                    "batch_memory_alias_rescue_blocked_genre_context",
                ],
                "image_evidence_catalog": [
                    {
                        "ocr_text": "오늘은 한층 더 춥네... 역시 돌아갈까?",
                        "evidence_type": "character_visual_only",
                        "title_role": "unknown",
                        "promotion_eligible": False,
                    }
                ],
                "candidate_ledger": {
                    "blocked_official_title": "암흑가 보스요? 제가요?",
                    "blocked_official_title_url": "https://novelpia.com/novel/384111",
                    "context_sources": ["title", "body", "image"],
                    "promotion_blocked_reasons": [
                        "image_scene_cues_unverified_public_title_bridge"
                    ],
                    "candidate_audit_lint_reasons": [
                        "image_scene_cues_unverified_public_title_bridge"
                    ],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "암흑가 보스요? 제가요?",
                            "heretic_url": "https://novelpia.com/novel/384111",
                            "source_tier": "official_detail",
                            "reference_role": "candidate",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "암흑가 보스요? 제가요?")
        self.assertEqual(trace["gate_decision"]["status"], "candidate_only")
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertFalse(trace["gate_decision"]["bypassed_gate"])
        self.assertEqual(trace["scope_state"]["scope_kind"], "context_only")
        self.assertEqual(trace["gate_decision"]["scope"]["scope_kind"], "context_only")
        self.assertIn("scope_context_only", trace["reason_codes"])
        self.assertIn("scope_not_current_work", trace["reason_codes"])
        self.assertIn("image_scene_cues_unverified_public_title_bridge", trace["reason_codes"])
        self.assertIn("image_ocr_without_title_anchor", trace["reason_codes"])
        self.assertIn("body_comments_absent_or_empty", trace["reason_codes"])
        self.assertIn("post_title_alias", trace["scope_state"]["direct_bridge_sources"])
        self.assertIn("official_detail_candidate", trace["scope_state"]["direct_bridge_sources"])
        self.assertIn("image_ocr_nonpromotable", trace["scope_state"]["direct_bridge_sources"])
        self.assertEqual(
            identity["candidate_ledger"]["promotion_gate_state"]["scope"]["scope_kind"],
            "context_only",
        )

    def test_blocked_text_only_alias_does_not_infer_image_context_scope(self):
        result = {
            "post_id": 11669928,
            "title": "탑성좌애호 노벨피아 이거 연중했었네",
            "content": [],
            "comments": [],
            "image_count": 0,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "discussion_type": "noise",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "탑의 성좌들이 날 애호한다",
                "blocked_official_title_url": "https://novelpia.com/novel/377032",
                "anchor_type": "none",
                "context_sources": ["title", "search"],
                "candidate_ledger": {
                    "blocked_official_title": "탑의 성좌들이 날 애호한다",
                    "blocked_official_title_url": "https://novelpia.com/novel/377032",
                    "candidate_preservation_sources": [
                        {
                            "official_title": "탑의 성좌들이 날 애호한다",
                            "heretic_url": "https://novelpia.com/novel/377032",
                            "source_tier": "official_detail",
                            "reference_role": "candidate",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        trace = result["identity"]["publish_contract_trace"]
        self.assertIsNone(trace["scope_state"])
        self.assertNotIn("scope_context_only", trace["reason_codes"])
        self.assertNotIn("image_ocr_without_title_anchor", trace["reason_codes"])
        self.assertFalse(trace["gate_decision"]["publish_allowed"])

    def test_blocked_character_bridge_search_evidence_records_current_scope_and_url(self):
        result = {
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "is_resolved_work_discussion": False,
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "이 무림의 미친년은 나야",
                "anchor_type": "author",
                "context_sources": ["title", "body", "comments", "search"],
                "search_evidence_catalog": [
                    {
                        "title": "이 무림의 미친년은 나야",
                        "url": "https://novelpia.com/novel/217943?sid=main5",
                        "domain": "novelpia.com",
                        "snippet": "서문청 천마혼 최종형태를 크게 감상하세요.",
                        "purpose": "title_anchor_official_probe",
                        "source_tier": "novel_platform",
                    }
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "이 무림의 미친년은 나야",
                        "confidence": "High",
                        "source_tier": "community",
                        "negative_evidence": [
                            "missing_official_url_for_official_detail"
                        ],
                        "reference_role": "primary",
                    }
                ],
                "candidate_ledger": {
                    "blocked_official_title": "이 무림의 미친년은 나야",
                    "context_sources": ["title", "body", "comments", "search"],
                    "anchor_type": "author",
                    "candidate_preservation_sources": [
                        {
                            "official_title": "이 무림의 미친년은 나야",
                            "confidence": "High",
                            "source_tier": "community",
                            "negative_evidence": [
                                "missing_official_url_for_official_detail"
                            ],
                            "reference_role": "primary",
                        }
                    ],
                },
            },
            "analysis": {
                "detected_titles": [
                    {
                        "official_title": "이 무림의 미친년은 나야",
                        "confidence": "High",
                        "source_tier": "community",
                        "negative_evidence": [
                            "missing_official_url_for_official_detail"
                        ],
                        "reference_role": "primary",
                    }
                ]
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        ledger = identity["candidate_ledger"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(
            identity["blocked_official_title_url"],
            "https://novelpia.com/novel/217943?sid=main5",
        )
        self.assertEqual(
            ledger["blocked_official_title_url"],
            "https://novelpia.com/novel/217943?sid=main5",
        )
        self.assertEqual(
            trace["pre_gate_candidate"]["official_url"],
            "https://novelpia.com/novel/217943?sid=main5",
        )
        self.assertEqual(trace["scope_state"]["scope_kind"], "current_work")
        self.assertEqual(trace["gate_decision"]["scope"]["scope_kind"], "current_work")
        self.assertIn("scope_current_work", trace["reason_codes"])
        self.assertNotIn("scope_not_current_work", trace["reason_codes"])
        self.assertIn(
            "official_detail_url_recovered_from_search_evidence",
            trace["reason_codes"],
        )
        self.assertIn("character_bridge_variance_hold", trace["reason_codes"])
        repaired_source = ledger["candidate_preservation_sources"][0]
        self.assertEqual(repaired_source["source_tier"], "official_detail")
        self.assertEqual(repaired_source["page_type"], "novel_page")
        self.assertEqual(
            repaired_source["heretic_url"],
            "https://novelpia.com/novel/217943?sid=main5",
        )
        self.assertIsNone(repaired_source["negative_evidence"])
        self.assertFalse(trace["gate_decision"]["publish_allowed"])

    def test_blocked_search_verified_alias_prefers_current_scope_over_image_context_hold(self):
        result = {
            "post_id": 11716448,
            "title": "아생갤 걍 히로인들 다 괴이 아니냐",
            "content": [
                "아레스랑 연 있었다고 엘리가 인간 확정이라기엔",
                "괴이 확정인 라나도 홍차 마시고 아레스랑 연 있었다는 거 나왔었는데",
            ],
            "comments": ["다 인간에서 변질된거일수도"],
            "image_count": 1,
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "is_resolved_work_discussion": False,
                "discussion_type": "character_talk",
                "topicality": "core_relevant",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "아카데미 생존 갤러리",
                "blocked_official_title_url": "https://novelpia.com/novel/380218",
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "comments", "search", "image"],
                "candidate_audit_lint": ["llm_only_sentence_candidate_pruned"],
                "search_evidence_catalog": [
                    {
                        "title": "아카데미 생존 갤러리",
                        "url": "https://novelpia.com/novel/380218",
                        "domain": "novelpia.com",
                        "snippet": "작품 공식 상세 페이지",
                        "purpose": "title_anchor_official_probe",
                        "source_tier": "novel_platform",
                    }
                ],
                "image_evidence_catalog": [
                    {
                        "ocr_text": "ㄹㅇ인가요",
                        "evidence_type": "character_visual_only",
                        "title_role": "unknown",
                        "promotion_eligible": False,
                    }
                ],
                "candidate_ledger": {
                    "blocked_official_title": "아카데미 생존 갤러리",
                    "blocked_official_title_url": "https://novelpia.com/novel/380218",
                    "anchor_type": "title_alias",
                    "context_sources": ["title", "body", "comments", "search", "image"],
                    "candidate_audit_lint_reasons": [
                        "llm_only_sentence_candidate_pruned"
                    ],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "아카데미 생존 갤러리",
                            "heretic_url": "https://novelpia.com/novel/380218",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "candidate",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["scope_state"]["scope_kind"], "current_work")
        self.assertEqual(trace["gate_decision"]["scope"]["scope_kind"], "current_work")
        self.assertIn("scope_current_work", trace["reason_codes"])
        self.assertNotIn("scope_not_current_work", trace["reason_codes"])
        self.assertIn(
            "official_detail_url_recovered_from_search_evidence",
            trace["reason_codes"],
        )
        self.assertIn("character_bridge_variance_hold", trace["reason_codes"])
        self.assertNotIn("body_comments_absent_or_empty", trace["reason_codes"])
        self.assertFalse(trace["gate_decision"]["publish_allowed"])

    def test_blocked_character_bridge_without_official_detail_keeps_scope_null(self):
        result = {
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "이 무림의 미친년은 나야",
                "anchor_type": "author",
                "context_sources": ["title", "body", "comments", "search"],
                "search_evidence_catalog": [
                    {
                        "title": "이 무림의 미친년은 나야 후기",
                        "url": "https://arca.live/b/tsfiction/127482874",
                        "domain": "arca.live",
                        "source_tier": "community",
                    }
                ],
                "candidate_ledger": {
                    "blocked_official_title": "이 무림의 미친년은 나야",
                    "context_sources": ["title", "body", "comments", "search"],
                    "anchor_type": "author",
                    "candidate_preservation_sources": [
                        {
                            "official_title": "이 무림의 미친년은 나야",
                            "source_tier": "community",
                            "negative_evidence": [
                                "missing_official_url_for_official_detail"
                            ],
                        }
                    ],
                },
            }
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        trace = result["identity"]["publish_contract_trace"]
        self.assertIsNone(trace["scope_state"])
        self.assertIsNone(trace["pre_gate_candidate"]["official_url"])
        self.assertNotIn("scope_current_work", trace["reason_codes"])
        self.assertNotIn(
            "official_detail_url_recovered_from_search_evidence",
            trace["reason_codes"],
        )
        self.assertFalse(trace["gate_decision"]["publish_allowed"])

    def test_blocked_trace_prefers_official_candidate_over_comment_surface_hold(self):
        result = {
            "title": "황제분충 ㄱㅊ함?",
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "context_only",
                "work_resolution": "none",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "표절물인가",
                "context_sources": ["title", "body", "comments", "search"],
                "promotion_decision": {
                    "status": "candidate_only",
                    "publish_allowed": False,
                    "official_title": None,
                    "official_url": None,
                    "candidate_preserved": True,
                    "reason_codes": [
                        "row_discusses_work_as_work",
                        "scope_current_work",
                    ],
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": ["row_discusses_work_as_work"],
                    },
                },
                "title_candidates": [
                    {
                        "title": "표절물인가",
                        "source_tier": "comment_surface",
                        "reference_role": "candidate",
                        "promotion_policy": "hold_without_promotion",
                    }
                ],
                "candidate_ledger": {
                    "blocked_official_title": "표절물인가",
                    "candidate_preservation_sources": [
                        {
                            "official_title": "황제의 딸로 환생했다",
                            "heretic_url": "https://novelpia.com/novel/250464",
                            "confidence": "High",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                        },
                        {
                            "official_title": "표절물인가",
                            "confidence": "Low",
                            "source_tier": "comment_surface",
                            "reference_role": "candidate",
                            "promotion_policy": "hold_without_promotion",
                        },
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "황제의 딸로 환생했다")
        self.assertEqual(
            trace["pre_gate_candidate"]["official_url"],
            "https://novelpia.com/novel/250464",
        )
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(identity["blocked_official_title"], "황제의 딸로 환생했다")
        self.assertFalse(identity.get("safe_resolved", False))

    def test_comment_surface_blocked_trace_recovers_community_primary_official_url(self):
        result = {
            "title": "서문청이랑 주서연이 싸우면 누가 이김?",
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "adjacent",
                "work_resolution": "none",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "호각임",
                "anchor_type": "author",
                "context_sources": ["title", "body", "comments", "search"],
                "promotion_decision": {
                    "status": "candidate_only",
                    "publish_allowed": False,
                    "official_title": None,
                    "official_url": None,
                    "candidate_preserved": True,
                    "reason_codes": ["promotion_blocked"],
                },
                "title_candidates": [
                    {
                        "title": "호각임",
                        "source_tier": "comment_surface",
                        "reference_role": "candidate",
                        "promotion_policy": "hold_without_promotion",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "이 무림의 미친년은 나야",
                        "url": "https://novelpia.com/novel/217943?sid=main5",
                        "domain": "novelpia.com",
                        "snippet": "서문청 천마혼 최종형태를 크게 감상하세요.",
                    }
                ],
                "candidate_ledger": {
                    "blocked_official_title": "호각임",
                    "context_sources": ["title", "body", "comments", "search"],
                    "anchor_type": "author",
                    "candidate_preservation_sources": [
                        {
                            "official_title": "이 무림의 미친년은 나야",
                            "confidence": "High",
                            "source_tier": "community",
                            "negative_evidence": [
                                "missing_official_url_for_official_detail"
                            ],
                            "reference_role": "primary",
                        },
                        {
                            "official_title": "호각임",
                            "confidence": "Low",
                            "source_tier": "comment_surface",
                            "reference_role": "candidate",
                            "promotion_policy": "hold_without_promotion",
                        },
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "이 무림의 미친년은 나야")
        self.assertEqual(
            trace["pre_gate_candidate"]["official_url"],
            "https://novelpia.com/novel/217943?sid=main5",
        )
        self.assertEqual(trace["scope_state"]["scope_kind"], "current_work")
        self.assertIn("official_detail_url_recovered_from_search_evidence", trace["reason_codes"])
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")

    def test_untraced_safe_publication_with_competing_official_candidate_is_blocked(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "novel_identity": {
                    "official_title": "잘생기면 인생이 편하다",
                    "heretic_url": "https://novelpia.com/novel/300042",
                    "confidence": "High",
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "잘생기면 인생이 편하다",
                            "heretic_url": "https://novelpia.com/novel/300042",
                            "source_tier": "official_detail",
                            "reference_role": "primary",
                        },
                        {
                            "official_title": "잘생기면 편해지는 인방 생활",
                            "heretic_url": "https://novelpia.com/novel/384016",
                            "source_tier": "official_detail",
                            "reference_role": "primary",
                        },
                    ],
                },
            }
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertFalse(identity["is_resolved_work_discussion"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "잘생기면 인생이 편하다")
        self.assertEqual(trace["gate_decision"]["status"], "candidate_only")
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIn(
            "final_publication_missing_promotion_gate_decision",
            trace["reason_codes"],
        )
        self.assertIn(
            "untraced_public_title_with_competing_candidate",
            trace["reason_codes"],
        )
        self.assertEqual(trace["scope_state"]["scope_kind"], "unknown")
        self.assertIn(
            "잘생기면 편해지는 인방 생활",
            trace["scope_state"]["competing_candidates"],
        )
        self.assertEqual(identity["candidate_ledger"]["promotion_decision"], trace["gate_decision"])

    def test_final_publication_ledger_records_allowed_nested_public_title(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "anchor_type": "character_title_link",
                "context_sources": ["title", "comments", "search"],
                "novel_identity": {
                    "official_title": "이 무림의 미친년은 나야",
                    "heretic_url": "https://novelpia.com/novel/217943?sid=main5",
                    "confidence": "High",
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "이 무림의 미친년은 나야",
                            "heretic_url": "https://novelpia.com/novel/217943?sid=main5",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                        }
                    ],
                },
            }
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "이 무림의 미친년은 나야")
        self.assertEqual(trace["gate_decision"]["status"], "publish")
        self.assertTrue(trace["gate_decision"]["publish_allowed"])
        self.assertEqual(trace["gate_decision"]["official_title"], "이 무림의 미친년은 나야")
        self.assertFalse(trace["gate_decision"]["bypassed_gate"])
        self.assertEqual(trace["scope_state"]["scope_kind"], "current_work")
        self.assertIn("scope_inferred_from_final_publication", trace["reason_codes"])
        self.assertEqual(
            identity["publish_ledger"]["public_publish"]["official_title"],
            "이 무림의 미친년은 나야",
        )
        self.assertEqual(identity["promotion_decision"], trace["gate_decision"])
        self.assertEqual(identity["candidate_ledger"]["promotion_decision"], trace["gate_decision"])
        self.assertEqual(identity["candidate_ledger"]["publish_ledger"], identity["publish_ledger"])

    def test_inferred_serialized_publication_without_url_stays_candidate_only(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "anchor_type": "title_exact",
                "context_sources": ["title", "body", "comments", "search"],
                "novel_identity": {
                    "official_title": "퇴마록",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "퇴마록",
                            "source_tier": "mixed",
                            "reference_role": "primary",
                        }
                    ],
                },
            }
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertEqual(identity["title_resolution_state"], "unresolved_matchable")
        self.assertEqual(identity["work_resolution"], "unresolved")
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertIn(
            "serialized_public_identity_missing_official_url",
            decision["reason_codes"],
        )
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])
        self.assertFalse(trace["post_gate_identity"]["title_resolution_allowed"])
        self.assertEqual(trace["post_gate_identity"]["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "퇴마록")
        self.assertEqual(identity["candidate_ledger"]["promotion_decision"], decision)

    def test_inferred_serialized_publication_with_critical_counterevidence_stays_candidate_only(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "comments", "search", "image"],
                "novel_identity": {
                    "official_title": "[블루아카이브] 키보토스 속 슈퍼히어로가 되었다",
                    "heretic_url": "https://novelpia.com/novel/268940",
                    "confidence": "High",
                },
                "reason_lines": [
                    "- grounding_anchor: none",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- 유의사항: 본문의 키워드(마블, 슈퍼맨, 배트맨)는 특정 웹소설을 지칭하는 것이 아니라 대중문화 일반 명사임",
                    "- 검증 반론(참고): 본문 내용이 웹소설이 아닌 영화/애니메이션/대중문화 IP에 관한 것임(critical) | relation_judge:thematic_overlap_only(critical)",
                    "- 제목/본문 앵커와 검색 근거를 종합하여 '[블루아카이브] 키보토스 속 슈퍼히어로가 되었다' 관련 작품 토론으로 판정했습니다.",
                ],
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "[블루아카이브] 키보토스 속 슈퍼히어로가 되었다",
                            "heretic_url": "https://novelpia.com/novel/268940",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                        }
                    ],
                },
            }
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertFalse(identity["safe_resolved"])
        self.assertTrue(identity["promotion_blocked"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("inferred_publication_critical_counterevidence", decision["reason_codes"])
        self.assertIn("scope_not_current_work", decision["reason_codes"])
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])
        self.assertEqual(identity["candidate_ledger"]["promotion_decision"], decision)

    def test_inferred_serialized_publication_without_direct_source_support_stays_candidate_only(self):
        result = {
            "title": "도굴왕은 애니화 난이도 다른거 보단 괜찮을거 같은데",
            "content": ["다른 웹툰이랑 다르게 전투씬의 비중이 크지 않아서"],
            "comments": [],
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "search"],
                "novel_identity": {
                    "official_title": "신의 의지가 깃든 물건",
                    "heretic_url": "https://novelpia.com/novel/436971",
                    "confidence": "High",
                },
                "primary_work": {
                    "official_title": "신의 의지가 깃든 물건",
                    "heretic_url": "https://novelpia.com/novel/436971",
                    "alias_or_mention": "다른",
                    "source_tier": "official_detail",
                },
                "reason_lines": [
                    "- grounding_anchor: title_mention",
                    "- evidence_type: search_platform_url",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=0, search_snippets=0, official_urls=1",
                    "- 제목/본문 앵커와 검색 근거를 종합하여 '신의 의지가 깃든 물건' 관련 작품 토론으로 판정했습니다.",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        decision = identity["promotion_decision"]
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("inferred_publication_missing_direct_source_support", decision["reason_codes"])
        self.assertIsNone(identity["novel_identity"]["official_title"])

    def test_inferred_serialized_publication_keeps_direct_alias_source_support(self):
        result = {
            "title": "랫따싶에서 따먹고싶다는애들이",
            "content": ["피갈 얘기"],
            "comments": [],
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "search"],
                "novel_identity": {
                    "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "confidence": "High",
                },
                "primary_work": {
                    "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "alias_or_mention": "림월드 랫따싶에서",
                    "source_tier": "official_detail",
                },
                "reason_lines": [
                    "- grounding_anchor: none",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=0, search_snippets=0, official_urls=1",
                    "- 제목/본문 앵커와 검색 근거를 종합하여 '[림월드]변방계에서 회귀자로 살아남기' 관련 작품 토론으로 판정했습니다.",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(
            identity["novel_identity"]["official_title"],
            "[림월드]변방계에서 회귀자로 살아남기",
        )
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])

    def test_inferred_serialized_publication_uses_post_title_alias_support(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "image", "search"],
                "novel_identity": {
                    "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/382324",
                    "confidence": "High",
                },
                "title_candidates": [
                    {
                        "official_title": "[림월드]변방계에서 회귀자로 살아남기",
                        "heretic_url": "https://novelpia.com/novel/382324",
                        "alias_or_mention": "림월드 랫따싶에서",
                        "source_tier": "official_detail",
                    }
                ],
                "reason_lines": [
                    "- grounding_anchor: none",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=0, search_snippets=0, official_urls=1",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="랫따싶에서 따먹고싶다는애들이",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(
            identity["novel_identity"]["official_title"],
            "[림월드]변방계에서 회귀자로 살아남기",
        )
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])

    def test_inferred_urlless_publication_keeps_verified_pure_alias_support(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_exact",
                "context_sources": ["title", "body", "comments", "search"],
                "novel_identity": {
                    "official_title": "판타지 초인 법사",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "판초법사",
                    "decoded_term": "판타지 초인 법사",
                    "decode_verified": True,
                    "alias_scope": "pure_work_alias",
                    "store_reason": "pure_work_alias",
                },
                "title_candidates": [
                    {
                        "official_title": "판타지 초인 법사",
                        "heretic_url": None,
                        "alias_or_mention": "판초법사",
                        "source_tier": "llm_only",
                    }
                ],
                "reason_lines": [
                    "- grounding_anchor: title_mention",
                    "- title_in_post: true",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: false",
                    "- evidence_bucket: post_spans=2, search_snippets=0, official_urls=0",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="판초법사 막 게이트열린 시점아님?",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "판타지 초인 법사")
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])
        self.assertNotIn(
            "serialized_public_identity_missing_official_url",
            identity["promotion_decision"]["reason_codes"],
        )

    def test_known_title_abbreviation_public_canonicalizes_spacing_variant(self):
        from src.llm_batch.experts import utils as expert_utils

        result = {
            "title": "말투 바뀌는 거 악살싶에서는 호평받았었는데",
            "content": ["갑1송게이 악살싶 초반부 금기교전 파쿠리건"],
            "comments": [],
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "comments", "search"],
                "consistency_flags": [
                    "known_title_abbreviation:악살싶",
                    "confirmed_alias:악살싶",
                    "verified_alias_title_only_publication",
                    "official_url_withheld_by_title_mismatch",
                ],
                "novel_identity": {
                    "official_title": "악당 은 살고 싶다",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "title_candidates": [
                    {
                        "official_title": "악당 은 살고 싶다",
                        "alias_or_mention": "악살싶",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "악당 은 살고 싶다",
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "verified_alias_title_only_publication",
                        "official_url_withheld_by_title_mismatch",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": ["title_abbrev_mentioned"],
                    },
                },
                "candidate_ledger": {},
            },
        }
        original_abbreviations = expert_utils.KNOWN_TITLE_ABBREVIATIONS
        try:
            expert_utils.KNOWN_TITLE_ABBREVIATIONS = {"악살싶": "악당은 살고 싶다"}
            changed = _sync_final_publication_ledger_contract(
                result,
                post_title="말투 바뀌는 거 악살싶에서는 호평받았었는데",
            )
        finally:
            expert_utils.KNOWN_TITLE_ABBREVIATIONS = original_abbreviations

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["novel_identity"]["official_title"], "악당은 살고 싶다")
        decision = identity["promotion_decision"]
        self.assertEqual(decision["official_title"], "악당은 살고 싶다")
        self.assertIsNone(decision["official_url"])
        self.assertIn(
            "known_title_abbreviation_public_canonicalized",
            decision["reason_codes"],
        )
        self.assertIn(
            "known_title_abbreviation_public_canonicalized",
            identity["consistency_flags"],
        )
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["post_gate_identity"]["official_title"], "악당은 살고 싶다")
        self.assertEqual(
            trace["pre_gate_candidate"]["source"],
            "known_title_abbreviation_public_canonicalization",
        )

    def test_blocked_verified_alias_title_only_restores_without_mismatched_url(self):
        result = {
            "title": "창월야 기준 한세건보다 강한 진마 몇 안되네",
            "content": ["유다 팬텀 아르곤 아낙스 정돈가"],
            "comments": ["와 한세건 아르곤 이런거 얼마만에 듣는 이름들이지"],
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "is_resolved_work_discussion": False,
                "safe_resolved": False,
                "promotion_blocked": True,
                "blocked_official_title": "월야환담 창월야",
                "blocked_official_title_url": "https://page.kakao.com/content/46563867",
                "anchor_type": "title_exact",
                "context_sources": ["title", "body", "comments", "search", "image"],
                "consistency_flags": [
                    "weak_alias_surface_public_title_bridge",
                    "official_detail_url_title_mismatch_publish_blocked",
                ],
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": None,
                    "confidence": "High",
                },
                "title_candidates": [
                    {
                        "official_title": "월야환담 창월야",
                        "heretic_url": "https://page.kakao.com/content/46563867",
                        "confidence": "High",
                        "alias_or_mention": "창월야",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "negative_evidence": [
                            "weak_alias_surface_public_title_bridge",
                            "url_title_mismatch",
                        ],
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "월야환담 창월야 - 나무위키",
                        "url": "https://namu.wiki/w/%EC%9B%94%EC%95%BC%ED%99%98%EB%8B%B4%20%EC%B0%BD%EC%9B%94%EC%95%BC",
                        "source_tier": "wiki",
                    }
                ],
                "promotion_decision": {
                    "status": "candidate_only",
                    "publish_allowed": False,
                    "official_title": None,
                    "official_url": None,
                    "candidate_preserved": True,
                    "reason_codes": [
                        "scope_context_only",
                        "serialized_public_identity_scrubbed",
                    ],
                    "bypassed_gate": False,
                    "scope": {"scope_kind": "context_only"},
                },
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="창월야 기준 한세건보다 강한 진마 몇 안되네",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertTrue(identity["safe_resolved"])
        self.assertEqual(identity["novel_identity"]["official_title"], "월야환담 창월야")
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        decision = identity["promotion_decision"]
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], "월야환담 창월야")
        self.assertIsNone(decision["official_url"])
        self.assertIn("verified_alias_title_only_publication", decision["reason_codes"])
        self.assertIn("official_url_withheld_by_title_mismatch", decision["reason_codes"])
        self.assertNotIn("weak_alias_surface_public_title_bridge", identity["consistency_flags"])
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["gate_decision"], decision)
        self.assertEqual(trace["post_gate_identity"]["official_title"], "월야환담 창월야")
        self.assertIsNone(trace["post_gate_identity"]["official_url"])

    def test_exact_surface_title_only_without_distinct_alias_bridge_does_not_restore(self):
        result = {
            "title": "미츄리 혼후순결에서 하인들에게도 멸시당한게 고증에 맞는거였구나",
            "content": ["아내가 혼후순결 요구해서 섹스 안하니까 집안 하인들도 멸시함"],
            "comments": ["이세계에서 사이비로 살아남기 얘기임"],
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "is_resolved_work_discussion": False,
                "safe_resolved": False,
                "promotion_blocked": True,
                "blocked_official_title": "혼후순결",
                "anchor_type": "title_exact",
                "context_sources": ["title", "body", "comments", "search"],
                "discussion_type": "character_talk",
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": None,
                    "confidence": "High",
                },
                "title_candidates": [
                    {
                        "official_title": "혼후순결",
                        "alias_or_mention": "혼후순결",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                    }
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "혼후순결",
                        "alias_or_mention": "혼후순결",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "혼후순결 - 카카오페이지",
                        "url": "https://page.kakao.com/content/12345678",
                        "source_tier": "official_detail",
                    }
                ],
                "promotion_decision": {
                    "status": "candidate_only",
                    "publish_allowed": False,
                    "official_title": None,
                    "official_url": None,
                    "candidate_preserved": True,
                    "reason_codes": [
                        "scope_context_only",
                        "official_url_withheld_by_title_mismatch",
                        "serialized_public_identity_scrubbed",
                    ],
                    "bypassed_gate": False,
                    "scope": {"scope_kind": "context_only"},
                },
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertFalse(decision["publish_allowed"])
        self.assertNotIn("verified_alias_title_only_publication", decision["reason_codes"])

    def test_title_only_official_detail_without_url_does_not_restore(self):
        result = {
            "title": "TS) 시스터즈 퍼스트 정신머리 고치려면",
            "content": ["고쳐질때까지 토우마가 갱생펀치 갈기면 되지 않을까?"],
            "comments": [],
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "is_resolved_work_discussion": False,
                "safe_resolved": False,
                "promotion_blocked": True,
                "blocked_official_title": "성기사는 버생을 산다",
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "search", "image"],
                "discussion_type": "general",
                "topicality": "core_relevant",
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": None,
                    "confidence": "High",
                },
                "title_candidates": [
                    {
                        "official_title": "성기사는 버생을 산다",
                        "heretic_url": None,
                        "confidence": "High",
                        "alias_or_mention": "시스터즈 이미지",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                    },
                    {
                        "official_title": "어떤 마술의 금서목록",
                        "heretic_url": "https://namu.wiki/w/example",
                        "confidence": "High",
                        "source_tier": "wiki",
                        "reference_role": "candidate",
                    },
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "성기사는 버생을 산다",
                        "heretic_url": None,
                        "confidence": "High",
                        "alias_or_mention": "시스터즈 이미지",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                    },
                    {
                        "official_title": "어떤 마술의 금서목록",
                        "heretic_url": "https://namu.wiki/w/example",
                        "confidence": "High",
                        "source_tier": "wiki",
                        "reference_role": "candidate",
                    },
                ],
                "search_evidence_catalog": [
                    {
                        "title": "어떤 마술의 금서목록 3 시스터즈 편",
                        "url": "https://namu.wiki/w/example",
                        "snippet": "카미조 토우마와 시스터즈 편",
                        "source_tier": "wiki",
                    }
                ],
                "promotion_decision": {
                    "status": "candidate_only",
                    "publish_allowed": False,
                    "official_title": None,
                    "official_url": None,
                    "candidate_preserved": True,
                    "reason_codes": [
                        "scope_context_only",
                        "official_url_withheld_by_title_mismatch",
                        "serialized_public_identity_scrubbed",
                    ],
                    "bypassed_gate": False,
                    "scope": {"scope_kind": "context_only"},
                },
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertFalse(decision["publish_allowed"])
        self.assertNotIn("verified_alias_title_only_publication", decision["reason_codes"])

    def test_title_only_missing_direct_source_negative_demotes_restored_publish(self):
        result = {
            "title": "TS) 시스터즈 퍼스트 정신머리 고치려면",
            "content": ["고쳐질때까지 토우마가 갱생펀치 갈기면 되지 않을까?"],
            "comments": [],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "search", "image"],
                "consistency_flags": [
                    "official_detail_url_missing_direct_source_support",
                    "verified_alias_title_only_publication",
                    "serialized_public_identity_shared_gate_restored",
                ],
                "novel_identity": {
                    "official_title": "성기사는 버생을 산다",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "candidate_preservation_sources": [
                    {
                        "official_title": "성기사는 버생을 산다",
                        "heretic_url": None,
                        "confidence": "High",
                        "alias_or_mention": "시스터즈 이미지",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                        "negative_evidence": [
                            "official_detail_url_missing_direct_source_support"
                        ],
                    },
                    {
                        "official_title": "어떤 마술의 금서목록",
                        "heretic_url": "https://namu.wiki/w/example",
                        "confidence": "High",
                        "source_tier": "wiki",
                        "reference_role": "candidate",
                    },
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "성기사는 버생을 산다",
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "verified_alias_title_only_publication",
                        "serialized_public_identity_shared_gate_restored",
                    ],
                    "bypassed_gate": False,
                    "scope": {"scope_kind": "current_work"},
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "성기사는 버생을 산다",
                            "heretic_url": None,
                            "confidence": "High",
                            "alias_or_mention": "시스터즈 이미지",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                            "negative_evidence": [
                                "official_detail_url_missing_direct_source_support"
                            ],
                        }
                    ]
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "official_detail_url_missing_direct_source_support",
            decision["reason_codes"],
        )
        self.assertEqual(decision["status"], "candidate_only")

    def test_verified_alias_title_only_counterevidence_demotes_restored_publish(self):
        result = {
            "post_id": 11705245,
            "title": "하남자 재밌냐",
            "content": ["주인공 첨부터쌤?", "- dc official App"],
            "comments": ["ㄴㄴ - dc App"],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "comments", "search", "image"],
                "novel_identity": {
                    "official_title": "하남자의 탑 공략법",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "reason_lines": [
                    "- 판정: 관련(정식 제목 미확정)",
                    "- 공식 제목: 미확정",
                    "- official_title_evidence: false",
                    "- 복수 후보가 공존하여 단일 제목 확정 위험이 높음",
                    "- 웹소설/장르 맥락은 인정하되 단일 공식 제목 확정은 위험하여 제목 지목을 보류했습니다.",
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "하남자의 탑 공략법",
                        "heretic_url": "https://novel.munpia.com/400210",
                        "confidence": "High",
                        "alias_or_mention": "하남자",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                        "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                    },
                    {
                        "official_title": "하남자는 딸깍충이 되고 싶다",
                        "heretic_url": None,
                        "confidence": "High",
                        "source_tier": "community",
                        "reference_role": "candidate",
                        "negative_evidence": ["missing_official_url_for_official_detail"],
                    },
                ],
                "search_evidence_catalog": [
                    {
                        "title": "하남자의 탑 공략법 - 문피아 웹소설",
                        "url": "https://novel.munpia.com/400210",
                        "source_tier": "novel_platform",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "하남자의 탑 공략법",
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "verified_alias_title_only_publication",
                        "official_url_withheld_by_title_mismatch",
                        "serialized_public_identity_shared_gate_restored",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "verified_alias_title_only_publication",
                            "post_title_alias",
                            "title",
                            "search",
                            "body",
                            "comments",
                        ],
                        "conflict_reason_codes": [
                            "official_url_withheld_by_title_mismatch",
                            "verified_alias_title_only_publication",
                        ],
                    },
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "하남자의 탑 공략법",
                            "heretic_url": "https://novel.munpia.com/400210",
                            "confidence": "High",
                            "alias_or_mention": "하남자",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                            "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                        }
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="하남자 재밌냐",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "verified_alias_title_only_counterevidence_blocked",
            decision["reason_codes"],
        )
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])

    def test_title_only_publication_with_source_denial_is_demoted(self):
        result = {
            "post_id": 11713212,
            "title": "지력 무한일 때 가장 효과 좋은 작물이 머임",
            "content": ["절대 SSS급 지력무한 영지를 손에 넣었다 를 쓰려는 건 아니고"],
            "comments": ["옥수수가 깡패 아닌가", "귀농물은 한번두 안바서.."],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "search", "body", "comments"],
                "slang_insight": {
                    "detected_term": "지력 무한",
                    "decoded_term": "SSS급 지력무한 영지를 손에 넣었다",
                    "decode_verified": True,
                    "alias_scope": "mixed_unknown",
                },
                "novel_identity": {
                    "official_title": "지력",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "title_candidates": [
                    {
                        "official_title": "지력",
                        "heretic_url": None,
                        "confidence": "Medium",
                        "alias_or_mention": "옥수수",
                        "source_tier": "official_detail",
                        "page_type": "novel_page",
                        "reference_role": "primary",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "지력",
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "verified_alias_title_only_publication",
                        "official_url_withheld_by_title_mismatch",
                        "serialized_public_identity_shared_gate_restored",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "verified_alias_title_only_publication",
                            "post_title_alias",
                            "title",
                            "search",
                            "body",
                            "comments",
                        ],
                        "conflict_reason_codes": [
                            "official_url_withheld_by_title_mismatch",
                            "verified_alias_title_only_publication",
                        ],
                    },
                },
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="지력 무한일 때 가장 효과 좋은 작물이 머임",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(identity["title_resolution_state"], "context_only")
        self.assertEqual(identity["work_resolution"], "none")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "source_explicit_work_denial_title_only_publication_blocked",
            decision["reason_codes"],
        )
        self.assertIn(
            "source_explicit_work_denial_title_only_publication_blocked",
            identity["promotion_blocked_reasons"],
        )
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])

    def test_batch_alias_url_only_publication_demotes_ambiguous_alias(self):
        result = {
            "post_id": 11705245,
            "title": "하남자 재밌냐",
            "content": ["주인공 첨부터쌤?"],
            "comments": ["ㄴㄴ - dc App"],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "discussion_type": "general",
                "anchor_type": "title_alias",
                "context_sources": ["title", "body", "comments", "search", "image"],
                "consistency_flags": [
                    "batch_memory_exact_alias_rescued",
                    "title_lead_alias_official_detail_release",
                    "verified_alias_official_detail_anchor",
                    "explicit_alias_official_work_lock",
                    "confirmed_alias:하남자",
                    "final_semantic_reread_official_recall_guarded_resolution",
                    "weak_public_title_bridge_batch_alias_exact_exempt",
                ],
                "novel_identity": {
                    "official_title": "하남자의 탑 공략법",
                    "heretic_url": "https://novel.munpia.com/400210",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "하남자",
                    "decoded_term": "하남자는 딸깍충이 되고 싶다",
                    "decode_verified": True,
                    "alias_scope": "pure_work_alias",
                },
                "reason_lines": [
                    "- grounding_anchor: title_mention",
                    "- evidence_type: search_platform_url",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=0, search_snippets=0, official_urls=1",
                    "- 검증 반론(참고): 제목 '하남자'와 정식 제목 '하남자는 딸깍충이 되고 싶다'의 형태소 불일치(minor)",
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "하남자의 탑 공략법",
                        "heretic_url": "https://novel.munpia.com/400210",
                        "confidence": "High",
                        "alias_or_mention": "하남자",
                        "source_tier": "official_detail",
                        "reference_role": "primary",
                    },
                    {
                        "official_title": "하남자는 딸깍충이 되고 싶다",
                        "confidence": "High",
                        "source_tier": "community",
                        "reference_role": "candidate",
                    },
                    {
                        "official_title": "하남 남자",
                        "heretic_url": "https://novelpia.com/novel/315683",
                        "confidence": "High",
                        "source_tier": "mixed",
                        "reference_role": "primary",
                    },
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "하남자의 탑 공략법",
                    "official_url": "https://novel.munpia.com/400210",
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "batch_alias_public_title_bridge",
                        "official_detail_url",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "batch_alias_candidate_accepted",
                            "title_lead_alias_official_detail_release",
                            "alias_surface",
                            "official_detail_url",
                        ],
                    },
                },
                "promotion_gate_state": {
                    "post_id": 11705245,
                    "candidate_title": "하남자의 탑 공략법",
                    "candidate_url": "https://novel.munpia.com/400210",
                    "source": "title_lead_alias_official_detail_release",
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "title_resolution_state": "resolved",
                    "work_resolution": "resolved",
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "batch_alias_candidate_accepted",
                            "title_lead_alias_official_detail_release",
                            "alias_surface",
                            "official_detail_url",
                        ],
                    },
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "하남자의 탑 공략법",
                            "heretic_url": "https://novel.munpia.com/400210",
                            "confidence": "High",
                            "alias_or_mention": "하남자",
                            "source_tier": "official_detail",
                            "reference_role": "primary",
                        },
                        {
                            "official_title": "하남자는 딸깍충이 되고 싶다",
                            "confidence": "High",
                            "source_tier": "community",
                            "reference_role": "candidate",
                        },
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="하남자 재밌냐",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "batch_alias_url_only_counterevidence_blocked",
            decision["reason_codes"],
        )
        self.assertIn(
            "batch_alias_url_only_counterevidence_blocked",
            identity["promotion_blocked_reasons"],
        )
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])

    def test_low_specificity_batch_alias_publication_demotes_competing_alias(self):
        result = {
            "post_id": 11705245,
            "title": "하남자 재밌냐",
            "content": ["주인공 첨부터쌤?", "- dc official App"],
            "comments": ["ㄴㄴ - dc App"],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "is_resolved_work_discussion": True,
                "discussion_type": "general",
                "anchor_type": "title_alias",
                "anchor_strength": "medium",
                "context_sources": ["title", "body", "comments", "search", "image"],
                "consistency_flags": [
                    "batch_memory_exact_alias_rescued",
                    "title_lead_alias_official_detail_release",
                    "verified_alias_official_detail_anchor",
                    "explicit_alias_official_work_lock",
                    "confirmed_alias:하남자",
                    "final_semantic_reread_official_recall_guarded_resolution",
                    "weak_public_title_bridge_batch_alias_exact_exempt",
                ],
                "novel_identity": {
                    "official_title": "하남자의 탑 공략법",
                    "heretic_url": "https://novel.munpia.com/400210",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "하남자",
                    "decoded_term": "하남자의 괴담 공략법",
                    "decode_verified": True,
                    "alias_scope": "pure_work_alias",
                },
                "reason_lines": [
                    "- grounding_anchor: title_mention",
                    "- evidence_type: search_platform_url",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=1, search_snippets=2, official_urls=1",
                    "- 검증 반론(참고): Decoder가 '하남자의 마탑 레이드'로 식별했으나, 검색 결과와 본문 맥락상 '하남자의 탑 공략법'이 더 유력함(major)",
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "하남자의 탑 공략법",
                        "heretic_url": "https://novel.munpia.com/400210",
                        "confidence": "High",
                        "alias_or_mention": "하남자",
                        "source_tier": "official_detail",
                        "reference_role": "primary",
                    },
                    {
                        "official_title": "하남자의 괴담 공략법",
                        "confidence": "High",
                        "source_tier": "community",
                        "reference_role": "candidate",
                    },
                    {
                        "official_title": "하남자의 마탑 레이드",
                        "heretic_url": "https://novelpia.com/novel/285649",
                        "confidence": "High",
                        "source_tier": "mixed",
                        "reference_role": "mentioned",
                    },
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "하남자의 탑 공략법",
                    "official_url": "https://novel.munpia.com/400210",
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "batch_alias_public_title_bridge",
                        "official_detail_url",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "batch_alias_candidate_accepted",
                            "title_lead_alias_official_detail_release",
                            "alias_surface",
                            "official_detail_url",
                        ],
                    },
                },
                "promotion_gate_state": {
                    "post_id": 11705245,
                    "candidate_title": "하남자의 탑 공략법",
                    "candidate_url": "https://novel.munpia.com/400210",
                    "source": "title_lead_alias_official_detail_release",
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "title_resolution_state": "resolved",
                    "work_resolution": "resolved",
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "batch_alias_candidate_accepted",
                            "title_lead_alias_official_detail_release",
                            "alias_surface",
                            "official_detail_url",
                        ],
                    },
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        {
                            "official_title": "하남자의 탑 공략법",
                            "heretic_url": "https://novel.munpia.com/400210",
                            "confidence": "High",
                            "alias_or_mention": "하남자",
                            "source_tier": "official_detail",
                            "reference_role": "primary",
                        },
                        {
                            "official_title": "하남자의 괴담 공략법",
                            "confidence": "High",
                            "source_tier": "community",
                            "reference_role": "candidate",
                        },
                    ],
                    "promotion_gate_evidence": [
                        {
                            "kind": "batch_alias_bridge",
                            "strength": "high",
                            "source_path_or_snippet": "하남자",
                            "supports_publish": True,
                            "reason_code": "batch_alias_public_title_bridge",
                        }
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="하남자 재밌냐",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertIn(
            "low_specificity_batch_alias_counterevidence_blocked",
            decision["reason_codes"],
        )
        self.assertIn(
            "low_specificity_batch_alias_counterevidence_blocked",
            identity["promotion_blocked_reasons"],
        )
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])

    def test_low_specificity_batch_alias_with_consumption_bridge_stays_publishable(self):
        result = {
            "title": "가챠펑크 세드릭 누구임",
            "content": ["가챠펑크 세드릭 초반부터 나옴?"],
            "comments": [],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "is_resolved_work_discussion": True,
                "discussion_type": "character_talk",
                "anchor_type": "character_title_link",
                "context_sources": ["title", "body", "search"],
                "novel_identity": {
                    "official_title": "가챠 중독자의 퓨전펑크 생활",
                    "heretic_url": "https://novelpia.com/novel/387014",
                    "confidence": "High",
                },
                "reason_lines": [
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- evidence_bucket: post_spans=1, search_snippets=1, official_urls=1",
                    "- 캐릭터 세드릭과 alias가 같은 원문에 결합됨",
                ],
                "candidate_preservation_sources": [
                    {
                        "official_title": "가챠 중독자의 퓨전펑크 생활",
                        "heretic_url": "https://novelpia.com/novel/387014",
                        "confidence": "High",
                        "alias_or_mention": "가챠펑크",
                        "source_tier": "official_detail",
                        "reference_role": "primary",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "가챠 중독자의 퓨전펑크 생활",
                    "official_url": "https://novelpia.com/novel/387014",
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "batch_alias_public_title_bridge",
                        "official_detail_url",
                        "title_led_consumption_bridge",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "batch_alias_candidate_accepted",
                            "alias_surface",
                            "official_detail_url",
                            "title_led_consumption_bridge",
                        ],
                    },
                },
                "candidate_ledger": {},
            },
        }

        _sync_final_publication_ledger_contract(
            result,
            post_title="가챠펑크 세드릭 누구임",
        )

        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])
        self.assertNotIn(
            "low_specificity_batch_alias_counterevidence_blocked",
            identity["promotion_decision"]["reason_codes"],
        )

    def test_short_generic_blocked_alias_does_not_restore_title_only(self):
        result = {
            "title": "판초법사 경찰력 사용하면서도 1달 이상 정보통제가 가능함?",
            "content": ["전국 경찰력 다 동원하는데 소문이 안날수가 있나?"],
            "comments": [],
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "adjacent",
                "work_resolution": "none",
                "is_resolved_work_discussion": False,
                "safe_resolved": False,
                "promotion_blocked": True,
                "blocked_official_title": "판초",
                "anchor_type": "none",
                "context_sources": ["title", "body", "search"],
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": None,
                },
                "title_candidates": [
                    {
                        "official_title": "판초",
                        "alias_or_mention": "판초",
                        "source_tier": "wiki",
                        "negative_evidence": ["weak_alias_surface_public_title_bridge"],
                    }
                ],
                "search_evidence_catalog": [
                    {
                        "title": "판초",
                        "url": "https://namu.wiki/w/%ED%8C%90%EC%B4%88",
                        "source_tier": "wiki",
                    }
                ],
                "promotion_decision": {
                    "status": "candidate_only",
                    "publish_allowed": False,
                    "official_title": None,
                    "official_url": None,
                    "candidate_preserved": True,
                    "reason_codes": ["serialized_public_identity_scrubbed"],
                    "bypassed_gate": False,
                },
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertIn("serialized_public_identity_scrubbed", identity["promotion_decision"]["reason_codes"])

    def test_pure_slang_alias_without_source_surface_does_not_support_publication(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["search"],
                "novel_identity": {
                    "official_title": "판타지 초인 법사",
                    "heretic_url": None,
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "판초법사",
                    "decoded_term": "판타지 초인 법사",
                    "decode_verified": True,
                    "alias_scope": "pure_work_alias",
                    "store_reason": "pure_work_alias",
                },
                "title_candidates": [
                    {
                        "official_title": "판타지 초인 법사",
                        "heretic_url": None,
                        "source_tier": "llm_only",
                    }
                ],
                "reason_lines": [
                    "- grounding_anchor: none",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: false",
                    "- evidence_bucket: post_spans=0, search_snippets=0, official_urls=0",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="요즘 법사물 뭐 봄?",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertIn(
            "inferred_publication_missing_direct_source_support",
            identity["promotion_decision"]["reason_codes"],
        )

    def test_sentence_like_slang_alias_overreach_stays_candidate_only(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "image", "search"],
                "novel_identity": {
                    "official_title": "도네하지 마라",
                    "heretic_url": "https://novelpia.com/novel/74240",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "알파카랑 눈싸움 하지마라",
                    "decoded_term": "도네하지 마라",
                    "decode_verified": True,
                    "alias_scope": "work_plus_meme",
                    "attached_entity_type": "meme",
                    "store_reason": "sentence_like_alias_surface",
                },
                "title_candidates": [
                    {
                        "official_title": "도네하지 마라",
                        "heretic_url": "https://novelpia.com/novel/74240",
                        "source_tier": "official_detail",
                    }
                ],
                "reason_lines": [
                    "- grounding_anchor: character_mention",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=1, search_snippets=4, official_urls=1",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="알파카랑 눈싸움 하지마라",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["title_resolution_allowed"])
        self.assertFalse(identity["safe_resolved"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        decision = identity["promotion_decision"]
        self.assertFalse(decision["publish_allowed"])
        self.assertIn("inferred_publication_sentence_like_alias_overreach", decision["reason_codes"])

    def test_sentence_like_character_pair_with_candidate_alias_support_keeps_publish(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "comments", "search"],
                "novel_identity": {
                    "official_title": "이 무림의 미친년은 나야",
                    "heretic_url": "https://novelpia.com/novel/217943",
                    "confidence": "High",
                },
                "slang_insight": {
                    "detected_term": "서문청이랑 주서연",
                    "decoded_term": "이 무림의 미친년은 나야",
                    "decode_verified": True,
                    "alias_scope": "work_plus_character",
                    "attached_entity_type": "character",
                    "store_reason": "sentence_like_alias_surface",
                },
                "title_candidates": [
                    {
                        "official_title": "이 무림의 미친년은 나야",
                        "heretic_url": "https://novelpia.com/novel/217943",
                        "alias_or_mention": "서문청이랑 주서연",
                        "source_tier": "official_detail",
                    }
                ],
                "reason_lines": [
                    "- grounding_anchor: character_mention",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=1, search_snippets=6, official_urls=1",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="서문청이랑 주서연이 싸우면 누가 이김?",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertEqual(identity["novel_identity"]["official_title"], "이 무림의 미친년은 나야")
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])

    def test_generic_pronoun_alias_does_not_count_as_direct_source_support(self):
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "candidate_ledger_status": "safe_resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "anchor_type": "title_alias",
                "context_sources": ["title", "image", "search"],
                "novel_identity": {
                    "official_title": "미쳐버린 판타지에서 사제로 살아남기",
                    "heretic_url": "https://novelpia.com/novel/115063",
                    "confidence": "High",
                },
                "title_candidates": [
                    {
                        "official_title": "미쳐버린 판타지에서 사제로 살아남기",
                        "heretic_url": "https://novelpia.com/novel/115063",
                        "alias_or_mention": "이새끼들",
                        "source_tier": "official_detail",
                    }
                ],
                "reason_lines": [
                    "- grounding_anchor: none",
                    "- title_in_post: false",
                    "- image_ocr_title_evidence: false",
                    "- official_title_evidence: true",
                    "- evidence_bucket: post_spans=0, search_snippets=0, official_urls=1",
                    "- 유의사항: `시리즈`는 플랫폼 명칭이고 본문은 여러 작품의 업데이트 상태에 대한 잡담임.",
                ],
                "candidate_ledger": {},
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="시리즈 기다리는 중인데 이새끼들 언제옴..",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertIn(
            "inferred_publication_missing_direct_source_support",
            identity["promotion_decision"]["reason_codes"],
        )

    def test_publish_contract_trace_converges_stale_blocked_trace_to_allowed_decision(self):
        stale_blocked_decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": ["stale_trace"],
            "bypassed_gate": False,
        }
        allowed_decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": "이 무림의 미친년은 나야",
            "official_url": "https://novelpia.com/novel/217943?sid=main5",
            "candidate_preserved": False,
            "reason_codes": [
                "row_discusses_work_as_work",
                "scope_current_work",
                "serialized_public_identity_published",
            ],
            "bypassed_gate": False,
            "scope": {"scope_kind": "current_work", "confidence": "high"},
        }
        stale_trace = {
            "pre_gate_candidate": {
                "official_title": "이 무림의 미친년은 나야",
                "official_url": "https://novelpia.com/novel/217943?sid=main5",
                "source": "stale_trace",
            },
            "gate_decision": stale_blocked_decision,
            "scope_state": {"scope_kind": "current_work", "confidence": "high"},
            "post_gate_identity": {
                "official_title": None,
                "official_url": None,
                "candidate_ledger_status": "promotion_blocked",
            },
            "reason_codes": ["stale_trace"],
            "bypassed_gate": False,
        }
        result = {
            "identity": {
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "candidate_ledger_status": "safe_resolved",
                "promotion_decision": allowed_decision,
                "novel_identity": {
                    "official_title": "이 무림의 미친년은 나야",
                    "heretic_url": "https://novelpia.com/novel/217943?sid=main5",
                },
                "publish_contract_trace": stale_trace,
                "publish_ledger": {
                    "candidate_preservation": stale_trace["pre_gate_candidate"],
                    "public_publish": stale_trace["post_gate_identity"],
                    "gate_decision": stale_blocked_decision,
                },
                "candidate_ledger": {
                    "promotion_decision": allowed_decision,
                    "publish_contract_trace": stale_trace,
                },
            }
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["gate_decision"], identity["promotion_decision"])
        self.assertTrue(trace["gate_decision"]["publish_allowed"])
        self.assertEqual(trace["post_gate_identity"]["official_title"], "이 무림의 미친년은 나야")
        self.assertEqual(identity["publish_ledger"]["gate_decision"], identity["promotion_decision"])
        self.assertEqual(identity["candidate_ledger"]["publish_contract_trace"], trace)
        self.assertEqual(identity["candidate_ledger"]["publish_ledger"], identity["publish_ledger"])

    def test_verified_alias_detail_replaces_stale_wrong_alias_blocked_gate(self):
        correct_title = "가챠 중독자의 퓨전펑크 생활"
        correct_url = "https://novelpia.com/novel/387014"
        stale_blocked_decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": [
                "row_discussion_missing",
                "nonwork",
                "scope_platform_meta_nonwork",
                "serialized_public_identity_scrubbed",
            ],
            "bypassed_gate": False,
            "scope": {
                "scope_kind": "platform_meta_nonwork",
                "confidence": "medium",
                "conflict_reason_codes": ["non_novel_discourse"],
            },
        }
        stale_gate_state = {
            "candidate_title": "아카데미 생존 갤러리",
            "candidate_url": "",
            "source": "batch_memory_exact_alias_rescued",
            "official_title_exists": False,
            "row_discusses_work_as_work": False,
            "scope": stale_blocked_decision["scope"],
        }
        candidate = {
            "official_title": correct_title,
            "heretic_url": correct_url,
            "confidence": "High",
            "alias_or_mention": "가챠펑크",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
        }
        result = {
            "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
            "content": ["가챠펑크 세드릭도 그렇고", "시원시원한 상남자라서 너무 좋구나"],
            "comments": [],
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "candidate_ledger_status": "promotion_blocked",
                "discussion_type": "character_talk",
                "topicality": "core_relevant",
                "anchor_type": "title_exact",
                "context_sources": ["title", "body", "search", "image"],
                "blocked_official_title": correct_title,
                "blocked_official_title_url": correct_url,
                "consistency_flags": [
                    "verified_alias_official_detail_anchor",
                    "confirmed_alias:가챠펑크",
                    "explicit_alias_official_work_lock",
                    "weak_public_title_bridge_verified_alias_detail_exempt",
                    "vlm_ocr_title_conflict_with_final_title",
                ],
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": None,
                    "confidence": "None",
                },
                "primary_work": dict(candidate),
                "title_candidates": [dict(candidate)],
                "promotion_decision": stale_blocked_decision,
                "promotion_gate_state": stale_gate_state,
                "candidate_ledger": {
                    "blocked_official_title": correct_title,
                    "blocked_official_title_url": correct_url,
                    "candidate_preservation_sources": [dict(candidate)],
                    "title_candidates": [dict(candidate)],
                    "context_sources": ["title", "body", "search", "image"],
                    "consistency_flags": [
                        "verified_alias_official_detail_anchor",
                        "confirmed_alias:가챠펑크",
                        "explicit_alias_official_work_lock",
                    ],
                    "promotion_decision": stale_blocked_decision,
                    "promotion_gate_state": stale_gate_state,
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "safe_resolved")
        self.assertTrue(identity["title_resolution_allowed"])
        self.assertEqual(identity["novel_identity"]["official_title"], correct_title)
        self.assertEqual(identity["novel_identity"]["heretic_url"], correct_url)
        decision = identity["promotion_decision"]
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], correct_title)
        self.assertEqual(decision["official_url"], correct_url)
        self.assertIn(
            "stale_blocked_gate_replaced_by_verified_alias_detail",
            decision["reason_codes"],
        )
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["gate_decision"], decision)
        self.assertEqual(trace["post_gate_identity"]["official_title"], correct_title)
        self.assertEqual(
            identity["candidate_ledger"]["promotion_gate_state"]["candidate_title"],
            correct_title,
        )

    def test_allowed_publication_reconciles_serialized_identity_to_shared_gate_candidate(self):
        correct_title = "가챠 중독자의 퓨전펑크 생활"
        correct_url = "https://novelpia.com/novel/387014"
        wrong_title = "아카데미 생존 갤러리"
        wrong_url = "https://novelpia.com/novel/380218"
        correct_candidate = {
            "official_title": correct_title,
            "heretic_url": correct_url,
            "confidence": "High",
            "alias_or_mention": "가챠펑크",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "mentioned",
            "preservation_role": "mentioned_work",
        }
        wrong_candidate = {
            "official_title": wrong_title,
            "heretic_url": wrong_url,
            "confidence": "High",
            "alias_or_mention": "아생갤",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
            "preservation_role": "title_candidate",
        }
        result = {
            "post_id": 11698880,
            "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
            "content": [
                "가챠펑크 세드릭도 그렇고",
                "시원시원한 상남자라서 너무 좋구나",
            ],
            "comments": [],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "discussion_type": "general",
                "topicality": "core_relevant",
                "context_sources": ["title", "body", "search", "image"],
                "consistency_flags": [
                    "title_led_evaluation_official_candidate_rescued",
                    "title_led_consumption_bridge",
                ],
                "novel_identity": {
                    "official_title": wrong_title,
                    "heretic_url": wrong_url,
                    "confidence": "High",
                },
                "primary_work": dict(wrong_candidate),
                "title_candidates": [dict(correct_candidate), dict(wrong_candidate)],
                "candidate_preservation_sources": [dict(correct_candidate), dict(wrong_candidate)],
                "search_evidence_catalog": [
                    {
                        "title": correct_title,
                        "url": correct_url,
                        "snippet": "가챠펑크 세드릭 관련 공식 작품",
                        "query": "가챠펑크 웹소설",
                        "source_tier": "novel_platform",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": wrong_title,
                    "official_url": wrong_url,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": ["row_discusses_work_as_work"],
                    },
                },
                "promotion_gate_state": {
                    "candidate_title": correct_title,
                    "candidate_url": correct_url,
                    "source": "known_abbreviation_title_guard:lsa_mapping",
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": ["row_discusses_work_as_work"],
                    },
                },
                "candidate_ledger": {
                    "candidate_ledger_status": "safe_resolved",
                    "title_resolution_allowed": True,
                    "title_resolution_state": "resolved",
                    "work_resolution": "resolved",
                    "title_candidates": [correct_title],
                    "candidate_preservation_sources": [
                        dict(correct_candidate),
                        dict(wrong_candidate),
                    ],
                    "search_evidence_catalog": [
                        {
                            "title": correct_title,
                            "url": correct_url,
                            "snippet": "가챠펑크 세드릭 관련 공식 작품",
                            "query": "가챠펑크 웹소설",
                            "source_tier": "novel_platform",
                        }
                    ],
                    "promotion_gate_state": {
                        "candidate_title": correct_title,
                        "candidate_url": correct_url,
                        "source": "known_abbreviation_title_guard:lsa_mapping",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": ["row_discusses_work_as_work"],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["novel_identity"]["official_title"], correct_title)
        self.assertEqual(identity["novel_identity"]["heretic_url"], correct_url)
        self.assertEqual(identity["primary_work"]["official_title"], correct_title)
        decision = identity["promotion_decision"]
        self.assertTrue(decision["publish_allowed"])
        self.assertEqual(decision["official_title"], correct_title)
        self.assertEqual(decision["official_url"], correct_url)
        self.assertIn(
            "serialized_public_identity_gate_candidate_reconciled",
            decision["reason_codes"],
        )
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], correct_title)
        self.assertEqual(trace["pre_gate_candidate"]["source"], "shared_promotion_gate_candidate")
        self.assertEqual(trace["post_gate_identity"]["official_title"], correct_title)
        self.assertEqual(
            identity["candidate_ledger"]["promotion_gate_state"]["candidate_title"],
            correct_title,
        )

    def test_allowed_publication_reconciles_body_verified_competition_after_gate_overwrite(self):
        correct_title = "가챠 중독자의 퓨전펑크 생활"
        wrong_title = "아카데미 생존 갤러리"
        wrong_url = "https://novelpia.com/novel/390001"
        correct_candidate = {
            "official_title": correct_title,
            "heretic_url": "https://namu.wiki/w/가챠 중독자의 퓨전펑크 생활",
            "confidence": "High",
            "alias_or_mention": "가챠펑크",
            "source_tier": "llm_only",
            "reference_role": "mentioned",
            "preservation_role": "mentioned_work",
        }
        wrong_candidate = {
            "official_title": wrong_title,
            "heretic_url": wrong_url,
            "confidence": "High",
            "alias_or_mention": "아생갤",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
        }
        result = {
            "post_id": 11698880,
            "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
            "content": ["가챠펑크 세드릭도 그렇고", "시원시원한 상남자라서 너무 좋구나"],
            "comments": [],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "primary_subject_text": f"메인 화제는 '{wrong_title}' 관련 작품 토론입니다.",
                "reason_lines": [
                    f"- 공식 제목: '{wrong_title}'",
                    f"- 제목/본문 앵커와 검색 근거를 종합하여 '{wrong_title}' 관련 작품 토론으로 판정했습니다.",
                    f"- 최종 공식 제목은 '{wrong_title}'로 확정됨.",
                ],
                "context_sources": ["title", "body", "search", "image"],
                "consistency_flags": [
                    "official_url_recall_blocked_body_verified_character_work_competes",
                    "body_verified_character_work_competes_with_title_led_alias",
                    "batch_memory_exact_alias_rescued",
                ],
                "novel_identity": {
                    "official_title": wrong_title,
                    "heretic_url": wrong_url,
                    "confidence": "High",
                },
                "primary_work": dict(wrong_candidate),
                "title_candidates": [dict(wrong_candidate), dict(correct_candidate)],
                "candidate_preservation_sources": [dict(wrong_candidate), dict(correct_candidate)],
                "search_evidence_catalog": [
                    {
                        "title": correct_title,
                        "url": "https://namu.wiki/w/가챠 중독자의 퓨전펑크 생활",
                        "snippet": "세드릭 몬트라벤은 가챠 중독자의 퓨전펑크 생활의 주인공",
                        "query": "가챠펑크 세드릭",
                        "source_tier": "wiki",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": wrong_title,
                    "official_url": wrong_url,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "batch_alias_public_title_bridge",
                        "official_detail_url",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "batch_alias_candidate_accepted",
                            "known_title_abbreviation",
                            "alias_surface",
                            "official_detail_url",
                        ],
                    },
                },
                "promotion_gate_state": {
                    "candidate_title": wrong_title,
                    "candidate_url": wrong_url,
                    "source": "known_title_abbreviation",
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "batch_alias_candidate_accepted",
                            "known_title_abbreviation",
                            "alias_surface",
                            "official_detail_url",
                        ],
                    },
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        dict(wrong_candidate),
                        dict(correct_candidate),
                    ],
                    "promotion_gate_state": {
                        "candidate_title": wrong_title,
                        "candidate_url": wrong_url,
                        "source": "known_title_abbreviation",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "batch_alias_candidate_accepted",
                                "known_title_abbreviation",
                                "alias_surface",
                                "official_detail_url",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["novel_identity"]["official_title"], correct_title)
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["primary_work"]["official_title"], correct_title)
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])
        self.assertEqual(identity["promotion_decision"]["official_title"], correct_title)
        self.assertIsNone(identity["promotion_decision"]["official_url"])
        self.assertIn(
            "serialized_public_identity_body_verified_competition_reconciled",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertEqual(
            identity["publish_contract_trace"]["pre_gate_candidate"]["source"],
            "body_verified_character_work_competition",
        )
        self.assertEqual(
            identity["primary_subject_text"],
            f"메인 화제는 '{correct_title}' 관련 작품 토론입니다.",
        )
        reason_text = "\n".join(identity["reason_lines"])
        self.assertIn(f"- 공식 제목: '{correct_title}'", reason_text)
        self.assertIn(f"'{correct_title}' 관련 작품 토론", reason_text)
        self.assertIn(f"- 최종 공식 제목은 '{correct_title}'로 확정됨.", reason_text)
        self.assertNotIn(f"- 공식 제목: '{wrong_title}'", reason_text)
        self.assertNotIn(f"'{wrong_title}' 관련 작품 토론", reason_text)
        self.assertNotIn(f"- 최종 공식 제목은 '{wrong_title}'", reason_text)

    def test_title_led_publication_reconciles_verified_alias_competing_work(self):
        correct_title = "가챠 중독자의 퓨전펑크 생활"
        wrong_title = "아카데미 생존 갤러리"
        wrong_url = "https://novelpia.com/novel/380218"
        correct_candidate = {
            "official_title": correct_title,
            "heretic_url": None,
            "confidence": "High",
            "alias_or_mention": "가챠펑크",
            "source_tier": "llm_only",
            "reference_role": "mentioned",
            "preservation_role": "mentioned_work",
        }
        wrong_candidate = {
            "official_title": wrong_title,
            "heretic_url": wrong_url,
            "confidence": "High",
            "alias_or_mention": "아생갤",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
            "preservation_role": "title_candidate",
        }
        result = {
            "post_id": 11698880,
            "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
            "content": [
                "가챠펑크 세드릭도 그렇고",
                "일본 씹찐따 주인공 처럼",
                "시원시원한 상남자라서 너무 좋구나",
            ],
            "comments": [],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "discussion_type": "character_talk",
                "context_sources": ["title", "body", "search", "image"],
                "consistency_flags": [
                    "multi_work_explicit_alias_official_lock",
                    "verified_alias_official_detail_anchor",
                    "confirmed_alias:가챠펑크",
                    "explicit_alias_official_work_lock",
                    "weak_public_title_bridge_verified_alias_detail_exempt",
                ],
                "novel_identity": {
                    "official_title": wrong_title,
                    "heretic_url": wrong_url,
                    "confidence": "High",
                },
                "primary_work": dict(wrong_candidate),
                "title_candidates": [dict(wrong_candidate), dict(correct_candidate)],
                "candidate_preservation_sources": [
                    dict(wrong_candidate),
                    dict(correct_candidate),
                ],
                "search_evidence_catalog": [
                    {
                        "title": "팬아트 : 팬아트",
                        "url": "https://novelpia.com/fanart/34/7",
                        "domain": "novelpia.com",
                        "snippet": "가챠펑크-정장 세드릭 관련 팬아트",
                        "query": "아생갤 가챠펑크 세드릭",
                        "source_tier": "novel_platform",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": wrong_title,
                    "official_url": wrong_url,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "title_led_consumption_bridge",
                        "title_acceptance_accept",
                        "alias_bridge",
                        "official_detail_url",
                        "serialized_public_identity_published",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "title_led_consumption_bridge",
                            "alias_surface",
                            "title_abbrev_mentioned",
                            "official_detail_url",
                        ],
                    },
                },
                "promotion_gate_state": {
                    "post_id": 11698880,
                    "candidate_title": wrong_title,
                    "candidate_url": wrong_url,
                    "source": "title_led_alias_public_title",
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "title_resolution_state": "resolved",
                    "work_resolution": "resolved",
                    "discussion_type": "character_talk",
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "title_led_consumption_bridge",
                            "alias_surface",
                            "title_abbrev_mentioned",
                            "official_detail_url",
                        ],
                    },
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        dict(wrong_candidate),
                        dict(correct_candidate),
                    ],
                    "consistency_flags": [
                        "multi_work_explicit_alias_official_lock",
                        "verified_alias_official_detail_anchor",
                        "confirmed_alias:가챠펑크",
                        "explicit_alias_official_work_lock",
                    ],
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["novel_identity"]["official_title"], correct_title)
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["primary_work"]["official_title"], correct_title)
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])
        self.assertEqual(identity["promotion_decision"]["official_title"], correct_title)
        self.assertIsNone(identity["promotion_decision"]["official_url"])
        self.assertIn(
            "serialized_public_identity_verified_alias_competition_reconciled",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertIn(
            "title_led_publication_blocked_by_verified_alias_competition",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertEqual(
            identity["publish_contract_trace"]["pre_gate_candidate"]["source"],
            "verified_alias_work_competition",
        )

    def test_title_only_publication_reconciles_preserved_body_alias_candidate_without_url(self):
        correct_title = "가챠 중독자의 퓨전펑크 생활"
        wrong_title = "아카데미 생존 갤러리"
        correct_candidate = {
            "official_title": correct_title,
            "confidence": "High",
            "alias_or_mention": "가챠펑크",
            "source_tier": "llm_only",
            "reference_role": "candidate",
            "preservation_role": "title_candidate",
        }
        wrong_candidate = {
            "official_title": wrong_title,
            "heretic_url": None,
            "confidence": "High",
            "alias_or_mention": "아생갤",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
            "preservation_role": "title_candidate",
            "negative_evidence": [
                "official_detail_url_missing_direct_source_support",
            ],
        }
        result = {
            "post_id": 11698880,
            "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
            "content": [
                "가챠펑크 세드릭도 그렇고",
                "일본 씹찐따 주인공 처럼",
                "시원시원한 상남자라서 너무 좋구나",
            ],
            "comments": [],
        }
        analysis_result = {
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "is_resolved_work_discussion": True,
                "safe_resolved": True,
                "promotion_blocked": False,
                "discussion_type": "general",
                "context_sources": ["title", "body", "search", "image"],
                "consistency_flags": [
                    "title_led_evaluation_official_candidate_rescued",
                    "title_led_consumption_bridge",
                    "official_detail_url_missing_direct_source_support",
                    "verified_alias_title_only_publication",
                    "serialized_public_identity_shared_gate_restored",
                ],
                "novel_identity": {
                    "official_title": wrong_title,
                    "heretic_url": None,
                    "confidence": "High",
                },
                "primary_work": dict(wrong_candidate),
                "title_candidates": [dict(wrong_candidate), dict(correct_candidate)],
                "candidate_preservation_sources": [
                    dict(wrong_candidate),
                    dict(correct_candidate),
                ],
                "search_evidence_catalog": [
                    {
                        "title": wrong_title,
                        "url": "https://novelpia.com/novel/380218",
                        "domain": "novelpia.com",
                        "snippet": "아생갤 팬아트와 리뷰가 검색되지만 본문 별칭 후보와 충돌한다.",
                        "query": "아생갤",
                        "source_tier": "novel_platform",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": wrong_title,
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "verified_alias_title_only_publication",
                        "official_url_withheld_by_title_mismatch",
                        "serialized_public_identity_shared_gate_restored",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "verified_alias_title_only_publication",
                            "post_title_alias",
                            "title",
                            "search",
                            "body",
                        ],
                        "conflict_reason_codes": [
                            "official_url_withheld_by_title_mismatch",
                            "verified_alias_title_only_publication",
                        ],
                    },
                },
                "promotion_gate_state": {
                    "candidate_title": wrong_title,
                    "candidate_url": None,
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "verified_alias_title_only_publication",
                            "post_title_alias",
                            "title",
                            "search",
                            "body",
                        ],
                        "conflict_reason_codes": [
                            "official_url_withheld_by_title_mismatch",
                            "verified_alias_title_only_publication",
                        ],
                    },
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        dict(wrong_candidate),
                        dict(correct_candidate),
                    ],
                    "search_evidence_catalog": [
                        {
                            "title": wrong_title,
                            "url": "https://novelpia.com/novel/380218",
                            "domain": "novelpia.com",
                            "snippet": "아생갤 팬아트와 리뷰가 검색되지만 본문 별칭 후보와 충돌한다.",
                            "query": "아생갤",
                            "source_tier": "novel_platform",
                        }
                    ],
                    "consistency_flags": [
                        "official_detail_url_missing_direct_source_support",
                    ],
                },
            },
        }
        sync_context = dict(analysis_result)
        sync_context.update(
            {
                "title": result["title"],
                "content": result["content"],
                "comments": result["comments"],
            }
        )

        changed = _sync_final_publication_ledger_contract(
            sync_context,
            post_title=result["title"],
        )

        self.assertTrue(changed)
        identity = analysis_result["identity"]
        self.assertEqual(identity["novel_identity"]["official_title"], correct_title)
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertEqual(identity["promotion_decision"]["official_title"], correct_title)
        self.assertIsNone(identity["promotion_decision"]["official_url"])
        self.assertIn(
            "serialized_public_identity_preserved_body_alias_reconciled",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertEqual(
            identity["publish_contract_trace"]["pre_gate_candidate"]["source"],
            "preserved_body_alias_candidate",
        )

    def test_locked_public_candidate_blocks_title_only_gate_candidate_override(self):
        correct_title = "가챠 중독자의 퓨전펑크 생활"
        correct_url = "https://novelpia.com/novel/387014"
        wrong_title = "아카데미 생존 갤러리"
        correct_candidate = {
            "official_title": correct_title,
            "heretic_url": correct_url,
            "confidence": "High",
            "alias_or_mention": "가챠펑크",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
            "locked": True,
        }
        wrong_candidate = {
            "official_title": wrong_title,
            "heretic_url": None,
            "confidence": "High",
            "alias_or_mention": "아생갤",
            "source_tier": "official_detail",
            "page_type": "novel_page",
            "reference_role": "primary",
        }
        result = {
            "title": "아생갤 개 존나게 재밌군 ㅇㅇ",
            "content": ["가챠펑크 세드릭도 그렇고 시원시원한 상남자라서 좋구나"],
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "safe_resolved": True,
                "promotion_blocked": False,
                "novel_identity": {
                    "official_title": wrong_title,
                    "heretic_url": None,
                    "confidence": "High",
                },
                "search_evidence_catalog": [
                    {
                        "title": "세드릭 몬트라벤 - 나무위키",
                        "snippet": "가챠 중독자의 퓨전펑크 생활의 주인공",
                        "url": "https://namu.wiki/w/세드릭 몬트라벤",
                        "source_tier": "wiki",
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": wrong_title,
                    "official_url": None,
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "scope_current_work",
                        "verified_alias_title_only_publication",
                        "official_url_withheld_by_title_mismatch",
                    ],
                    "bypassed_gate": False,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "verified_alias_title_only_publication",
                            "post_title_alias",
                            "title",
                            "search",
                            "body",
                        ],
                    },
                },
                "promotion_gate_state": {
                    "candidate_title": wrong_title,
                    "candidate_url": None,
                    "official_title_exists": True,
                    "row_discusses_work_as_work": True,
                    "scope": {
                        "scope_kind": "current_work",
                        "confidence": "high",
                        "direct_bridge_sources": [
                            "verified_alias_title_only_publication",
                            "post_title_alias",
                            "title",
                            "search",
                            "body",
                        ],
                        "conflict_reason_codes": [
                            "official_url_withheld_by_title_mismatch",
                            "verified_alias_title_only_publication",
                        ],
                    },
                },
                "candidate_ledger": {
                    "candidate_preservation_sources": [
                        dict(correct_candidate),
                        dict(wrong_candidate),
                    ],
                    "promotion_gate_state": {
                        "candidate_title": wrong_title,
                        "candidate_url": None,
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": {
                            "scope_kind": "current_work",
                            "confidence": "high",
                            "direct_bridge_sources": [
                                "verified_alias_title_only_publication",
                                "post_title_alias",
                                "title",
                                "search",
                                "body",
                            ],
                            "conflict_reason_codes": [
                                "official_url_withheld_by_title_mismatch",
                                "verified_alias_title_only_publication",
                            ],
                        },
                    },
                },
            },
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="아생갤 개 존나게 재밌군 ㅇㅇ",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["novel_identity"]["official_title"], correct_title)
        self.assertEqual(identity["promotion_decision"]["official_title"], correct_title)
        self.assertEqual(identity["promotion_decision"]["official_url"], correct_url)
        self.assertIn(
            "serialized_public_identity_gate_candidate_blocked_by_locked_public_candidate",
            identity["promotion_decision"]["reason_codes"],
        )
        self.assertEqual(
            identity["publish_contract_trace"]["pre_gate_candidate"]["source"],
            "locked_competing_public_candidate",
        )

    def test_publish_contract_trace_converges_stale_publish_trace_to_blocked_decision(self):
        stale_publish_decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": "테라포밍",
            "official_url": "https://novel.munpia.com/416826",
            "candidate_preserved": False,
            "reason_codes": ["stale_publish"],
            "bypassed_gate": False,
        }
        blocked_decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": [
                "row_discussion_missing",
                "scope_context_only",
                "scope_not_current_work",
                "serialized_public_identity_scrubbed",
            ],
            "bypassed_gate": False,
            "scope": {"scope_kind": "context_only", "confidence": "high"},
        }
        stale_trace = {
            "pre_gate_candidate": {
                "official_title": "테라포밍",
                "official_url": "https://novel.munpia.com/416826",
                "source": "stale_trace",
            },
            "gate_decision": stale_publish_decision,
            "scope_state": {"scope_kind": "context_only", "confidence": "high"},
            "post_gate_identity": {
                "official_title": "테라포밍",
                "official_url": "https://novel.munpia.com/416826",
                "candidate_ledger_status": "safe_resolved",
            },
            "reason_codes": ["stale_publish"],
            "bypassed_gate": False,
        }
        result = {
            "identity": {
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "none",
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "테라포밍",
                "blocked_official_title_url": "https://novel.munpia.com/416826",
                "promotion_decision": blocked_decision,
                "publish_contract_trace": stale_trace,
                "publish_ledger": {
                    "candidate_preservation": stale_trace["pre_gate_candidate"],
                    "public_publish": stale_trace["post_gate_identity"],
                    "gate_decision": stale_publish_decision,
                },
                "candidate_ledger": {
                    "blocked_official_title": "테라포밍",
                    "blocked_official_title_url": "https://novel.munpia.com/416826",
                    "promotion_decision": blocked_decision,
                    "publish_contract_trace": stale_trace,
                },
            }
        }

        changed = _sync_final_publication_ledger_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["gate_decision"], identity["promotion_decision"])
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])
        self.assertIsNone(trace["post_gate_identity"]["official_url"])
        self.assertEqual(identity["publish_ledger"]["gate_decision"], identity["promotion_decision"])
        self.assertEqual(identity["candidate_ledger"]["publish_contract_trace"], trace)
        self.assertEqual(identity["candidate_ledger"]["publish_ledger"], identity["publish_ledger"])

    def test_platform_meta_image_title_hard_hold_demotes_final_publication_contract(self):
        result = {
            "identity": {
                "candidate_ledger_status": "safe_resolved",
                "title_resolution_allowed": True,
                "is_resolved_work_discussion": True,
                "safe_resolved": True,
                "promotion_blocked": False,
                "title_resolution_state": "resolved",
                "work_resolution": "resolved",
                "context_sources": ["title", "body", "search", "image"],
                "anchor_type": "image",
                "consistency_flags": [
                    "platform_meta_multi_title_blocked",
                    "direct_image_explicit_title_rescued",
                ],
                "novel_identity": {
                    "official_title": "전 버튜버가 하고 싶은데요",
                    "heretic_url": "https://novelpia.com/novel/275975",
                },
                "image_evidence_catalog": [
                    {
                        "ocr_text": "ACTOR 전 버튜버가 하고 싶은데요",
                        "explicit_work_title": "전 버튜버가 하고 싶은데요",
                        "evidence_type": "cover_title",
                        "title_role": "unknown",
                        "promotion_eligible": False,
                    }
                ],
                "promotion_decision": {
                    "status": "publish",
                    "publish_allowed": True,
                    "official_title": "전 버튜버가 하고 싶은데요",
                    "official_url": "https://novelpia.com/novel/275975",
                    "candidate_preserved": False,
                    "reason_codes": [
                        "official_title_exists",
                        "row_discusses_work_as_work",
                        "resolved_public_title_scope",
                    ],
                    "bypassed_gate": False,
                    "scope": {"scope_kind": "current_work"},
                },
                "candidate_ledger": {},
            }
        }

        changed = _sync_final_publication_ledger_contract(
            result,
            post_title="문피아에서는 수정하면 욕 처먹는거고",
        )

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertFalse(identity["safe_resolved"])
        self.assertTrue(identity["promotion_blocked"])
        self.assertIsNone(identity["novel_identity"]["official_title"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        decision = identity["promotion_decision"]
        self.assertEqual(decision["status"], "candidate_only")
        self.assertFalse(decision["publish_allowed"])
        self.assertTrue(decision["candidate_preserved"])
        self.assertIn("platform_meta_image_title_hard_hold", decision["reason_codes"])
        self.assertEqual(decision["scope"]["scope_kind"], "context_only")
        trace = identity["publish_contract_trace"]
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])
        self.assertEqual(identity["candidate_ledger"]["promotion_decision"], decision)

    def test_promotion_blocked_trace_uses_candidate_ledger_sources(self):
        result = {
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "none",
                "candidate_ledger": {
                    "title_candidates": ["암흑가 보스요? 제가요?"],
                    "candidate_preservation_sources": [
                        {
                            "official_title": "암흑가 보스요? 제가요?",
                            "heretic_url": "https://novelpia.com/novel/384111",
                            "promotion_policy": "hold_without_promotion",
                        }
                    ],
                },
            }
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        trace = result["identity"]["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], "암흑가 보스요? 제가요?")
        self.assertEqual(
            trace["pre_gate_candidate"]["official_url"],
            "https://novelpia.com/novel/384111",
        )
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertTrue(trace["gate_decision"]["candidate_preserved"])
        self.assertFalse(trace["gate_decision"]["bypassed_gate"])
        self.assertIsNone(trace["post_gate_identity"]["official_title"])
        self.assertEqual(
            result["identity"]["candidate_ledger"]["publish_ledger"],
            result["identity"]["publish_ledger"],
        )

    def test_promotion_blocked_trace_prefers_gate_competing_candidate_for_contextual_alias_conflict(self):
        wrong_title = "쳇바퀴의 생쥐 사도가 되었다"
        wrong_url = "https://novelpia.com/novel/406113"
        correct_title = "변방계에서 회귀자로 살아남기"
        correct_url = "https://novelpia.com/novel/382324"
        result = {
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "title_resolution_allowed": False,
                "title_resolution_state": "unresolved_matchable",
                "work_resolution": "unresolved",
                "blocked_official_title": wrong_title,
                "blocked_official_title_url": wrong_url,
                "promotion_decision": {
                    "status": "candidate_only",
                    "publish_allowed": False,
                    "official_title": None,
                    "official_url": None,
                    "candidate_preserved": True,
                    "reason_codes": ["title_led_alias_contextual_official_detail_competes"],
                    "scope": {
                        "scope_kind": "context_only",
                        "competing_candidates": [correct_title],
                        "conflict_reason_codes": [
                            "title_led_alias_contextual_official_detail_competes"
                        ],
                    },
                },
                "candidate_ledger": {
                    "blocked_official_title": wrong_title,
                    "blocked_official_title_url": wrong_url,
                    "candidate_preservation_sources": [
                        {
                            "official_title": wrong_title,
                            "heretic_url": wrong_url,
                            "confidence": "High",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "primary",
                        },
                        {
                            "official_title": correct_title,
                            "heretic_url": correct_url,
                            "confidence": "High",
                            "source_tier": "official_detail",
                            "page_type": "novel_page",
                            "reference_role": "candidate",
                        },
                    ],
                },
            }
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        trace = identity["publish_contract_trace"]
        self.assertEqual(trace["pre_gate_candidate"]["official_title"], correct_title)
        self.assertEqual(trace["pre_gate_candidate"]["official_url"], correct_url)
        self.assertEqual(
            trace["pre_gate_candidate"]["source"],
            "promotion_gate_competing_candidate",
        )
        self.assertFalse(trace["gate_decision"]["publish_allowed"])
        self.assertIn(
            "title_led_alias_contextual_official_detail_competes",
            trace["gate_decision"]["reason_codes"],
        )
        self.assertIsNone(trace["post_gate_identity"]["official_title"])
        self.assertEqual(
            identity["publish_ledger"]["candidate_preservation"],
            trace["pre_gate_candidate"],
        )

    def test_output_consistency_lint_hold_scrubs_resolution_text(self):
        result = {
            "identity": {
                "official_title": None,
                "official_novel_title": None,
                "heretic_url": "https://novelpia.com/novel/380804",
                "title_resolution_allowed": False,
                "candidate_ledger_status": "output_consistency_lint",
                "blocked_official_title": "온 세상이 정신이상자다",
                "blocked_official_title_url": "https://novelpia.com/novel/380804",
                "output_consistency_lint": ["judge_candidate_seed_wrong_relevance_public_title_held"],
                "novel_identity": {
                    "official_title": None,
                    "heretic_url": "https://novelpia.com/novel/380804",
                    "confidence": "None",
                },
                "reason_lines": [
                    "- 공식 제목: '온 세상이 정신이상자다'",
                    "- 최종 공식 제목은 '온 세상이 정신이상자다'로 확정됨.",
                    "- heretic_url_platform: +3 (작품 상세 URL(플랫폼))",
                ],
            },
            "analysis": {
                "notes": "최종 공식 제목은 '온 세상이 정신이상자다'로 확정됨.",
                "detected_titles": [
                    {
                        "official_title": "온 세상이 정신이상자다",
                        "heretic_url": "https://novelpia.com/novel/380804",
                        "reference_role": "primary",
                    }
                ],
            },
        }

        changed = _scrub_promotion_blocked_result_contract(result)

        self.assertTrue(changed)
        identity = result["identity"]
        self.assertIsNone(identity["heretic_url"])
        self.assertIsNone(identity["novel_identity"]["heretic_url"])
        self.assertIn("공식 제목: 미확정", identity["reason"])
        self.assertIn("확정 문구는 promotion block guard로 철회됨", identity["reason"])
        detected = result["analysis"]["detected_titles"][0]
        self.assertEqual(detected["reference_role"], "candidate")
        self.assertEqual(detected["promotion_policy"], "hold_without_promotion")
        self.assertTrue(detected["blocked_by_candidate_audit"])

    def test_anonymous_author_match_without_post_ip_is_unverified(self):
        comments = [
            {
                "comment_id": "c1",
                "author": "ㅇㅇ",
                "content": "같은 닉이지만 원글 작성자라고 확정할 수 없음",
                "reply_level": 0,
            },
            {
                "comment_id": "c2",
                "author": "ㅇㅇ",
                "ip": "211.36",
                "content": "댓글 IP만 있고 post IP는 없음",
                "reply_level": 0,
            },
        ]

        metadata = _public_comment_metadata(comments, post_author="ㅇㅇ")
        context_lines = _public_comment_context_lines(metadata)
        dialogue_lines = _public_comment_dialogue_context_lines(comments, metadata)

        self.assertEqual(len(metadata), 2)
        self.assertFalse(metadata[0]["is_post_author"])
        self.assertTrue(metadata[0]["post_author_match_unverified"])
        self.assertFalse(metadata[1]["is_post_author"])
        self.assertTrue(metadata[1]["post_author_match_unverified"])
        self.assertIn("role=author_match_unverified", context_lines[0])
        self.assertNotIn("role=post_author", context_lines[0])
        self.assertIn("role=author_match_unverified", dialogue_lines[1])
        self.assertNotIn("role=post_author", dialogue_lines[1])

    def test_public_content_blocks_preserve_image_urls_for_review(self):
        blocks = [
            {"type": "text", "text": "본문 텍스트"},
            {"type": "image", "url": "https://dcimg.example/novel.png"},
            {"image_url": "https://dcimg.example/alias.jpg"},
            {"src": "https://dcimg.example/src.webp"},
            {"type": "image", "url": "https://dcimg.example/novel.png"},
            {"type": "text", "text": "추가 설명"},
        ]

        public_blocks = _public_content_blocks(blocks)
        image_urls = _public_image_urls(blocks)

        self.assertEqual(public_blocks[0], {"type": "text", "text": "본문 텍스트"})
        self.assertEqual(public_blocks[1], {"type": "image", "url": "https://dcimg.example/novel.png"})
        self.assertEqual(public_blocks[2], {"type": "image", "url": "https://dcimg.example/alias.jpg"})
        self.assertEqual(public_blocks[3], {"type": "image", "url": "https://dcimg.example/src.webp"})
        self.assertEqual(
            image_urls,
            [
                "https://dcimg.example/novel.png",
                "https://dcimg.example/alias.jpg",
                "https://dcimg.example/src.webp",
            ],
        )

    def test_image_post_sample_ids_and_vlm_gate_lines_expose_no_go(self):
        posts = [
            SimpleNamespace(post_id=11718080, content_blocks=[{"type": "text", "text": "본문"}]),
            SimpleNamespace(post_id=11718082, content_blocks=[{"type": "image", "url": "https://dcimg.example/a.jpg"}]),
            SimpleNamespace(post_id=11718096, content_blocks=[{"type": "image", "url": "https://dcimg.example/b.jpg"}]),
        ]

        sample_ids = _image_post_sample_post_ids(posts)
        lines = _vlm_ocr_semantic_review_gate_lines(
            image_post_count=2,
            vlm_enabled=False,
            ocr_enabled=True,
            ready=False,
            sample_post_ids=sample_ids,
        )

        self.assertEqual(sample_ids, [11718082, 11718096])
        self.assertIn("VLM/OCR Semantic Gate: NO-GO", lines[0])
        self.assertIn("skip_reasons=[vlm_disabled]", lines[0])
        self.assertIn("sample_post_ids=[11718082, 11718096]", lines[0])
        self.assertIn("rerun_with_vlm_on_ocr_on_or_browser_review", lines[1])

    def test_vlm_ocr_semantic_review_skip_reasons_are_structured(self):
        self.assertEqual(
            _vlm_ocr_semantic_review_skip_reasons(
                image_post_count=0,
                vlm_enabled=False,
                ocr_enabled=False,
            ),
            ["no_image_blocks"],
        )
        self.assertEqual(
            _vlm_ocr_semantic_review_skip_reasons(
                image_post_count=2,
                vlm_enabled=False,
                ocr_enabled=False,
            ),
            ["vlm_disabled", "ocr_disabled"],
        )
        self.assertEqual(
            _vlm_ocr_semantic_review_skip_reasons(
                image_post_count=2,
                vlm_enabled=True,
                ocr_enabled=True,
            ),
            [],
        )

    def test_require_vlm_ocr_for_images_can_be_enabled_by_env(self):
        with patch.dict("os.environ", {"LLM_REQUIRE_VLM_OCR_FOR_IMAGES": "1"}):
            self.assertTrue(_require_vlm_ocr_for_image_posts())
        with patch.dict("os.environ", {"LLM_REQUIRE_VLM_OCR_FOR_IMAGES": "0"}):
            self.assertFalse(_require_vlm_ocr_for_image_posts())

    def test_public_comment_metadata_uses_post_ip_for_author_match(self):
        comments = [
            {
                "comment_id": "c1",
                "author": "ㅇㅇ",
                "ip": "123.248",
                "content": "원글 작성자가 이어서 설명",
            },
            {
                "comment_id": "c2",
                "author": "ㅇㅇ",
                "ip": "211.36",
                "content": "다른 익명 유저 반응",
            },
        ]

        metadata = _public_comment_metadata(comments, post_author="ㅇㅇ", post_ip="123.248")
        dialogue_lines = _public_comment_dialogue_context_lines(comments, metadata)

        self.assertTrue(metadata[0]["is_post_author"])
        self.assertEqual(metadata[0]["speaker"], "post_author")
        self.assertFalse(metadata[1]["is_post_author"])
        self.assertEqual(metadata[1]["speaker"], "user1")
        self.assertIn("role=post_author", dialogue_lines[0])
        self.assertNotIn("role=post_author", dialogue_lines[1])

    def test_load_jsonl_posts_attaches_comment_rows_when_post_id_types_differ(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.jsonl"
            rows = [
                {
                    "gallery_id": "genrenovel",
                    "post_id": 11718091,
                    "title": "소신발언)) 은영이 23센줄 몰랐음",
                    "author": "ㅇㅇ",
                    "ip": "123.248",
                    "content_blocks": [{"type": "text", "text": "묘사만 보면 한 16살인줄???"}],
                },
                {
                    "comment_id": "40479972",
                    "post_id": "11718091",
                    "author": "ㅇㅇ",
                    "ip": "123.248",
                    "content": "ㄹㅇ 머리도 안올렷잖아 더어린줄",
                },
                {
                    "comment_id": "40479972",
                    "post_id": 11718091,
                    "author": "ㅇㅇ",
                    "ip": "123.248",
                    "content": "ㄹㅇ 머리도 안올렷잖아 더어린줄",
                },
            ]
            path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")

            posts = load_jsonl_posts(path)

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].post_id, 11718091)
        self.assertEqual(len(posts[0].comments), 1)
        self.assertEqual(posts[0].comments[0]["comment_id"], "40479972")
        self.assertEqual(posts[0].comments[0]["gallery_id"], "genrenovel")


if __name__ == "__main__":
    unittest.main()
