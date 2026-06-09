"""rank2 (recall / 근본원인 A) 단위테스트.

대상: _has_ocr_catalog_official_title_evidence — 이미지 OCR 카탈로그 상세를 official_title_evidence 로 인정.
명시 seed 게이트: (작품명 토큰)+(작가명 라벨)+(메트릭/시놉시스/플랫폼마커) 중 2종 이상 공기 시에만 True.
배경 리스팅·약 evidence_type·제목 불일치 제외, 본문 플랫폼/연재 메타 위주면 제외(author_talk/release_meta 오확정 방지).
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm_batch.agentic_pipeline import AgenticPipeline  # noqa: E402
from llm_batch.experts.orchestrator import ExpertType  # noqa: E402


class _Ctx(SimpleNamespace):
    def get_expert_output(self, expert, *_a, **_k):
        return (getattr(self, "_outputs", {}) or {}).get(expert, {})


def _ctx(image_enrichment, *, post_title="이 소설 진짜 띵작이다"):
    return _Ctx(
        _outputs={ExpertType.DISCOURSE: {}, ExpertType.DECODER: {}, ExpertType.GATEKEEPER: {}},
        post_data={"title": post_title, "content_blocks": [], "image_enrichment": image_enrichment},
        search_results=[],
        comments=[],
        discourse_warning="",
    )


TITLE = "전지적 독자 시점"


def _catalog_item(**over):
    # 기존 이미지 1차 승격 계약(_has_image_primary_promotion_signal)을 통과하는 vetted work-title 카탈로그 item
    base = {
        "explicit_work_title": TITLE,
        "evidence_type": "cover_title",
        "explicit_author_name": "싱숑",
        "ocr_text": "조회수 1.2억 ★9.8 연재중",
        "work_cues": [],
        "promotion_eligible": True,
        "focus_role": "work_anchor",
        "title_role": "work_title",
    }
    base.update(over)
    return base


class Rank2StructureMarkerTest(unittest.TestCase):
    def setUp(self):
        self.p = object.__new__(AgenticPipeline)

    def test_platform_marker(self):
        self.assertTrue(self.p._ocr_catalog_structure_marker("노벨피아 연재 / 표지"))

    def test_metric_marker(self):
        self.assertTrue(self.p._ocr_catalog_structure_marker("조회수 1.2억 ★9.8"))

    def test_synopsis_marker(self):
        self.assertTrue(self.p._ocr_catalog_structure_marker("줄거리: 멸망한 세계에서..."))

    def test_plain_text_no_marker(self):
        self.assertFalse(self.p._ocr_catalog_structure_marker("주인공 표정이 인상적이다"))


class Rank2OcrCatalogEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.p = object.__new__(AgenticPipeline)

    def test_title_plus_author_plus_metric_is_official(self):
        ctx = _ctx([_catalog_item()])
        self.assertTrue(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_title_plus_author_only_two_signals_is_official(self):
        # 메트릭 없음, 작품명+작가 2종 → True
        ctx = _ctx([_catalog_item(ocr_text="", work_cues=[])])
        self.assertTrue(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_title_only_one_signal_not_official(self):
        # 작가 없음 + 메트릭 없음 → 신호 1종 → False (단편 표면만으로 과확정 금지)
        ctx = _ctx([_catalog_item(explicit_author_name="", ocr_text="", work_cues=[])])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_weak_evidence_type_not_official(self):
        # 표지/명시 텍스트가 아닌 분위기/장면 추정 → False (멀티모달 precision)
        ctx = _ctx([_catalog_item(evidence_type="scene_mood")])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_title_mismatch_not_official(self):
        ctx = _ctx([_catalog_item(explicit_work_title="다른 작품")])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_background_listing_excluded(self):
        # 상위 배경리스팅 가드는 background_listing_only 플래그 + promotion_eligible=False 로 강등 → 제외
        ctx = _ctx([_catalog_item(background_listing_only=True, promotion_eligible=False)])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_not_promotion_eligible_excluded(self):
        # 파이프라인이 promotion 부적격으로 판정한 item(약신호/게임UI 등)은 title+author 여도 제외(계약 동형)
        ctx = _ctx([_catalog_item(promotion_eligible=False)])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_item_name_title_role_excluded(self):
        # title_role=item_name(게임 UI 아이템명) 등 비-work 표면은 제외
        ctx = _ctx([_catalog_item(title_role="item_name")])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_community_meta_banter_post_excluded(self):
        # 본문이 커뮤니티 잡담/밈 본질(개추·분탕 등 메타 2종+ & 작품 내부앵커 부재)이면 부수 카탈로그 제목 제외
        ctx = _ctx([_catalog_item()], post_title="개추 분탕 ㄴㄴ 이런 글 念글 가야됨")
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_platform_meta_post_excluded(self):
        # 본문이 플랫폼/연재 메타 위주면 OCR 카탈로그 제목은 부수적 → 제외(주제 정합성)
        self.p._looks_like_platform_meta_post = lambda *a, **k: True
        ctx = _ctx([_catalog_item()])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))

    def test_no_image_enrichment_not_official(self):
        ctx = _ctx([])
        self.assertFalse(self.p._has_ocr_catalog_official_title_evidence(ctx, TITLE))


class Rank2VerifierVetoInvarianceTest(unittest.TestCase):
    """finding1(critical) 수정 검증: rank2 OCR 카탈로그 근거는 allow_ocr_catalog=False 소비처(verifier
    promotion veto)를 우회하지 못한다 — 검색/공식URL/fetch 1차 앵커가 없으면 official_evidence=False."""

    def setUp(self):
        self.p = object.__new__(AgenticPipeline)
        # 검색/공식URL/fetch 등 비-OCR 공식 근거 경로를 모두 차단 → official_ev 는 OCR 카탈로그로만 결정
        self.p._is_platform_branding_title = lambda *a, **k: False
        self.p._looks_like_listing_title = lambda *a, **k: False
        self.p._is_structural_nonwork_title = lambda *a, **k: False
        self.p._is_generic_topic_title = lambda *a, **k: False
        self.p._has_filtered_official_detail_support_for_title = lambda *a, **k: False
        self.p._get_candidate_bridge_profile = lambda *a, **k: {}

    def _ctx_with_catalog(self):
        return _ctx([_catalog_item()])

    def test_allow_ocr_true_counts_catalog(self):
        ctx = self._ctx_with_catalog()
        self.assertTrue(self.p._has_official_title_evidence(ctx, TITLE, allow_ocr_catalog=True))

    def test_allow_ocr_false_excludes_catalog(self):
        # verifier veto 처럼 allow_ocr_catalog=False 로 호출하면 OCR-only 근거는 official 로 인정되지 않음(게이트 불변)
        ctx = self._ctx_with_catalog()
        self.assertFalse(self.p._has_official_title_evidence(ctx, TITLE, allow_ocr_catalog=False))


if __name__ == "__main__":
    unittest.main()
