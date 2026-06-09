"""
Multi-Expert Deliberation System (다중 전문가 심의 시스템)

세 가지 접근법을 결합하여 Arbiter의 LLM 비결정성을 완화하고 판정 안정성을 높인다.

Architecture:
  C: EvidenceScorer — 코드레벨 증거 점수 (0 LLM cost, 항상 실행)
  A: Jury Panel — 3× 병렬 Arbiter 호출 + 다수결 (conflict 시에만)
  B: Debate Pattern — Advocate→Skeptic→Judge (conflict 시에만)

흐름:
  1. EvidenceScorer가 ctx 기반 증거 점수 계산 → Arbiter 프롬프트에 주입
  2. 기본 Arbiter 호출 (1회)
  3. conflict_score 계산 → 임계치 초과 시 Jury Panel + Debate 실행
  4. 최종 결과 합성 (가중 다수결)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .orchestrator import ConversationContext, ExpertType
    from ..llm.client import LLMClient

from .utils import _ts  # 통합 타임스탬프 (worker-aware)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# C: EvidenceScorer (코드레벨 증거 점수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EvidenceScorer:
    """
    모든 전문가 출력을 코드 레벨에서 분석하여 객관적 증거 점수를 계산.
    LLM 호출 없이 순수 코드로 동작 (0 cost).
    Arbiter 프롬프트에 주입되어 LLM의 판단 안정성을 높인다.
    """

    # 증거 유형별 가중치
    WEIGHTS = {
        "platform_url": 5.0,       # 소설 플랫폼 URL 확인 (노벨피아, 문피아 등)
        "wiki_url": 3.0,           # 나무위키/위키 URL
        "decoder_high": 4.0,       # Decoder best_match confidence=High/Max
        "decoder_medium": 2.0,     # Decoder best_match confidence=Medium
        "verifier_relevant": 3.0,  # Verifier is_relevant=true
        "verifier_high_conf": 2.0, # Verifier confidence=High/Max
        "verifier_anchor": 2.0,    # Verifier grounding anchor 발견
        "critic_title": 1.5,       # Critic이 제목 감지
        "comment_title": 1.5,      # 댓글에서 작품명 언급
        "gatekeeper_novel": 1.0,   # Gatekeeper가 novel 관련으로 판단
        "discourse_novel": 1.0,    # Discourse가 novel 도메인으로 판단
        "synthesizer_agree": 2.0,  # Synthesizer가 작품 식별에 동의
        "abbreviation_match": 1.0, # Curated alias hit is a recall hint, not standalone proof.
        "dv_consensus": 3.0,       # Decoder+Verifier 제목 합의
    }

    @staticmethod
    def _norm_text(value: Any) -> str:
        return re.sub(r"\s+", "", str(value or "")).lower()

    @staticmethod
    def _contains_alias_surface(text: Any, alias: str) -> bool:
        raw = str(text or "")
        alias_raw = str(alias or "").strip()
        if not raw or not alias_raw:
            return False
        # Prefer a visible surface boundary. If Korean particles are attached,
        # downstream title recovery can still use stronger pipeline guards.
        return bool(
            re.search(
                rf"(?<![0-9A-Za-z가-힣]){re.escape(alias_raw)}(?![0-9A-Za-z가-힣])",
                raw,
                flags=re.IGNORECASE,
            )
        )

    @classmethod
    def _post_text_parts(cls, ctx: "ConversationContext", post_data: Optional[Dict[str, Any]] = None) -> List[str]:
        post_data = post_data or getattr(ctx, "post_data", None) or {}
        parts: List[str] = [str(post_data.get("title") or "")]
        for block in post_data.get("content_blocks") or []:
            if isinstance(block, dict):
                text = block.get("text")
                if text:
                    parts.append(str(text))
            elif isinstance(block, str):
                parts.append(block)
        for comment in getattr(ctx, "comments", None) or []:
            if isinstance(comment, dict):
                text = comment.get("content") or comment.get("text")
                if text:
                    parts.append(str(text))
            elif isinstance(comment, str):
                parts.append(comment)
        return parts

    @classmethod
    def _semantic_seed_denies_work(cls, ctx: "ConversationContext", disc: Optional[Dict[str, Any]] = None) -> bool:
        disc = disc or {}
        analysis = disc.get("discourse_analysis") if isinstance(disc.get("discourse_analysis"), dict) else {}
        semantic_seed = analysis.get("semantic_seed_review") if isinstance(analysis.get("semantic_seed_review"), dict) else {}
        if semantic_seed.get("is_specific_work_discussion") is False:
            return True
        warnings = analysis.get("warnings") or disc.get("warnings") or []
        if any("semantic_seed_review_specific_work_denied" in str(item) for item in warnings):
            return True
        uncertainty = getattr(ctx, "uncertainty_sources", None) or []
        return any("intent_permit_for_title_search=false" in str(item) for item in uncertainty)

    @classmethod
    def _has_independent_work_anchor(
        cls,
        ctx: "ConversationContext",
        *,
        gk: Optional[Dict[str, Any]] = None,
        disc: Optional[Dict[str, Any]] = None,
        post_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        gk = gk or {}
        disc = disc or {}
        post_data = post_data or getattr(ctx, "post_data", None) or {}
        gk_type = str(gk.get("post_type") or "").lower()
        if gk_type in ("work_discussion", "novel_discussion", "novel_review", "novel_spoiler"):
            return True
        analysis = disc.get("discourse_analysis") if isinstance(disc.get("discourse_analysis"), dict) else {}
        intent = str(analysis.get("intent") or getattr(ctx, "discourse_intent", "") or "").lower()
        if intent in ("discuss_work", "work_discussion", "review_work"):
            return True
        clues = gk.get("context_clues") if isinstance(gk.get("context_clues"), dict) else {}
        if any(clues.get(key) for key in ("has_episode_reference", "is_spoiler_discussion")):
            return True
        full_text = " ".join(cls._post_text_parts(ctx, post_data))
        return any(
            domain in full_text
            for domain in ("novelpia.com", "munpia.com", "series.naver.com", "page.kakao.com")
        )

    @classmethod
    def _find_curated_alias_hint(
        cls,
        ctx: "ConversationContext",
        *,
        gk: Optional[Dict[str, Any]] = None,
        disc: Optional[Dict[str, Any]] = None,
        post_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            from .decoder import KNOWN_ABBREVIATIONS
            from .utils import KNOWN_TITLE_ABBREVIATIONS
            from .orchestrator import ExpertType
        except ImportError:
            return None

        post_data = post_data or getattr(ctx, "post_data", None) or {}
        gk = gk or ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        disc = disc or ctx.get_expert_output(ExpertType.DISCOURSE) or {}
        key_terms = [
            str(term).strip()
            for term in (gk.get("key_terms") or [])
            if isinstance(term, str) and term.strip()
        ]
        surfaces = cls._post_text_parts(ctx, post_data) + key_terms
        registries = (
            ("KNOWN_ABBREVIATIONS", KNOWN_ABBREVIATIONS or {}),
            ("KNOWN_TITLE_ABBREVIATIONS", KNOWN_TITLE_ABBREVIATIONS or {}),
        )
        for registry_name, mapping in registries:
            for alias, canonical in mapping.items():
                alias_text = str(alias or "").strip()
                if not alias_text:
                    continue
                if any(cls._contains_alias_surface(surface, alias_text) for surface in surfaces):
                    no_work = cls._semantic_seed_denies_work(ctx, disc)
                    work_anchor = cls._has_independent_work_anchor(
                        ctx,
                        gk=gk,
                        disc=disc,
                        post_data=post_data,
                    )
                    return {
                        "alias": alias_text,
                        "canonical": str(canonical or ""),
                        "registry": registry_name,
                        "eligible": bool(work_anchor and not no_work),
                        "work_anchor": bool(work_anchor),
                        "semantic_no_work": bool(no_work),
                    }
        return None

    @classmethod
    def build_curated_alias_prompt_note(
        cls,
        ctx: "ConversationContext",
        *,
        gk: Optional[Dict[str, Any]] = None,
        disc: Optional[Dict[str, Any]] = None,
        post_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        hint = cls._find_curated_alias_hint(ctx, gk=gk, disc=disc, post_data=post_data)
        if not hint or not hint.get("eligible"):
            return ""
        return (
            "\n\n🔑 **등록 약칭 후보 (검토용 힌트)**:\n"
            f"- 표면 약칭: '{hint['alias']}'\n"
            f"- 후보 정식명: '{hint['canonical']}'\n"
            f"- 출처 registry: {hint['registry']}\n"
            "- 이 매핑은 작품 후보 recall 힌트이며, 단독 확정 근거가 아닙니다.\n"
            "- 원문/댓글/공식 URL/검색 snippet/VLM-OCR 등 독립 작품 앵커가 같은 작품을 지지할 때만 판정 보조로 사용하세요.\n"
            "- 독립 앵커가 약하거나 잡담/no-work 문맥이면 title=null 또는 HOLD를 우선 고려하세요.\n"
        )

    # 감점 요인
    PENALTIES = {
        "gatekeeper_noise": -2.0,      # Gatekeeper가 noise로 판단
        "discourse_non_novel": -2.0,   # Discourse가 non-novel 도메인
        "verifier_irrelevant": -3.0,   # Verifier가 irrelevant
        "decoder_none": -3.0,          # Decoder confidence=None
        "decoder_low": -1.5,           # Decoder confidence=Low
        "no_text_content": -1.0,       # 텍스트 콘텐츠 없음
        "multi_work_detected": -1.0,   # 다작품 컨텍스트 감지
        "hypothesis_invalidated": -1.0, # 가설이 무효화된 적 있음
        # Phase31: 새로운 충돌 신호
        "gatekeeper_noise_overridden": -2.0,  # GK가 원래 noise였는데 override 됨
        "verifier_critical_counter": -1.5,    # Verifier의 critical severity 반론
        "decoder_genre_collision": -2.0,      # Decoder에서 장르용어+소설명 동시 발견
    }

    @classmethod
    def compute(cls, ctx: "ConversationContext") -> Dict[str, Any]:
        """
        증거 점수를 계산하여 상세 보고서 반환.

        Returns:
            {
                "total_score": float,
                "relevance_probability": str,  # "very_high" | "high" | "medium" | "low" | "very_low"
                "positive_signals": [...],
                "negative_signals": [...],
                "expert_agreement": float,  # 0.0 ~ 1.0
                "conflict_detected": bool,
                "conflict_details": [...],
                "recommendation": str,
            }
        """
        from .orchestrator import ExpertType

        gk = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        dc = ctx.get_expert_output(ExpertType.DECODER) or {}
        vf = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vr = vf.get("verification_result") or {}
        cr = ctx.get_expert_output(ExpertType.CRITIC) or {}
        disc = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
        synth = ctx.get_expert_output(ExpertType.SYNTHESIZER) or {}

        positives: List[Dict[str, Any]] = []
        negatives: List[Dict[str, Any]] = []
        conflicts: List[str] = []

        total = 0.0

        # ─── Gatekeeper signals ───
        gk_noise = gk.get("is_noise", False)
        gk_type = str(gk.get("post_type", "")).lower()
        # Phase31: 원래 noise였는데 override된 경우 감점 + 충돌 등록
        _original_gk_noise = getattr(ctx, "original_gatekeeper_noise", False)
        if _original_gk_noise and not gk_noise:
            # GK가 noise라고 했지만 orchestrator가 취소함
            negatives.append({
                "signal": "gatekeeper_noise_overridden",
                "detail": f"original_reason={getattr(ctx, 'original_gatekeeper_noise_reason', 'unknown')}, "
                         f"override={getattr(ctx, 'noise_override_reason', 'unknown')}",
            })
            total += cls.PENALTIES["gatekeeper_noise_overridden"]
        if gk_noise:
            negatives.append({"signal": "gatekeeper_noise", "detail": f"type={gk_type}"})
            total += cls.PENALTIES["gatekeeper_noise"]
        elif gk_type in ("novel_discussion", "novel_review", "novel_spoiler"):
            positives.append({"signal": "gatekeeper_novel", "detail": gk_type})
            total += cls.WEIGHTS["gatekeeper_novel"]

        # ─── Discourse signals ───
        disc_domain = str(ctx.primary_domain or "").lower()
        if "novel" in disc_domain or "fiction" in disc_domain:
            positives.append({"signal": "discourse_novel", "detail": disc_domain})
            total += cls.WEIGHTS["discourse_novel"]
        elif disc_domain and disc_domain not in ("", "unknown"):
            if any(kw in disc_domain for kw in ("meme", "humor", "daily", "game", "real", "off_topic")):
                negatives.append({"signal": "discourse_non_novel", "detail": disc_domain})
                total += cls.PENALTIES["discourse_non_novel"]

        # ─── Decoder signals ───
        dc_conf = str(dc.get("overall_confidence", "")).lower()
        dc_title = None
        dc_best = dc.get("overall_best_match") or {}
        if isinstance(dc_best, dict):
            dc_title = dc_best.get("title")

        if dc_conf in ("high", "max"):
            positives.append({"signal": "decoder_high", "detail": f"title={dc_title}, conf={dc_conf}"})
            total += cls.WEIGHTS["decoder_high"]
        elif dc_conf == "medium":
            positives.append({"signal": "decoder_medium", "detail": f"title={dc_title}"})
            total += cls.WEIGHTS["decoder_medium"]
        elif dc_conf in ("none", ""):
            negatives.append({"signal": "decoder_none", "detail": "no identification"})
            total += cls.PENALTIES["decoder_none"]
        elif dc_conf == "low":
            negatives.append({"signal": "decoder_low", "detail": f"title={dc_title}"})
            total += cls.PENALTIES["decoder_low"]

        # Decoder platform URL check
        for term in (dc.get("decoded_terms") or []):
            if not isinstance(term, dict):
                continue
            bm = term.get("best_match") or {}
            if isinstance(bm, dict):
                platform = bm.get("platform") or bm.get("url") or ""
                if cls._is_novel_platform(str(platform)):
                    positives.append({"signal": "platform_url", "detail": str(platform)[:80]})
                    total += cls.WEIGHTS["platform_url"]
                    break
                if "namu.wiki" in str(platform) or "namuwiki" in str(platform):
                    positives.append({"signal": "wiki_url", "detail": str(platform)[:80]})
                    total += cls.WEIGHTS["wiki_url"]
                    break

        # ─── Verifier signals ───
        vf_relevant = vr.get("is_relevant")
        vf_conf = str(vr.get("final_confidence") or vr.get("confidence") or "").lower()
        vf_anchor = (vr.get("grounding_check") or {}).get("anchor_found", False)
        vf_title = (vr.get("novel_identity") or {}).get("official_novel_title") or \
                   (vr.get("novel_identity") or {}).get("official_title")

        if vf_relevant is True:
            positives.append({"signal": "verifier_relevant", "detail": f"title={vf_title}"})
            total += cls.WEIGHTS["verifier_relevant"]
            if vf_conf in ("high", "max"):
                positives.append({"signal": "verifier_high_conf", "detail": vf_conf})
                total += cls.WEIGHTS["verifier_high_conf"]
        elif vf_relevant is False:
            negatives.append({"signal": "verifier_irrelevant", "detail": f"conf={vf_conf}"})
            total += cls.PENALTIES["verifier_irrelevant"]

        if vf_anchor:
            positives.append({"signal": "verifier_anchor", "detail": "anchor found"})
            total += cls.WEIGHTS["verifier_anchor"]

        # ─── Critic signals ───
        cr_titles = cr.get("detected_titles") or []
        if cr_titles:
            positives.append({"signal": "critic_title", "detail": str(cr_titles[:3])})
            total += cls.WEIGHTS["critic_title"]

        # ─── Synthesizer agreement ───
        synth_title = (synth.get("primary_candidate") or {}).get("title")
        if synth_title and dc_title:
            s_norm = re.sub(r"\s+", "", str(synth_title)).lower()
            d_norm = re.sub(r"\s+", "", str(dc_title)).lower()
            if s_norm == d_norm:
                positives.append({"signal": "synthesizer_agree", "detail": synth_title})
                total += cls.WEIGHTS["synthesizer_agree"]

        # ─── Decoder + Verifier consensus ───
        if dc_title and vf_title:
            d_norm = re.sub(r"\s+", "", str(dc_title)).lower()
            v_norm = re.sub(r"\s+", "", str(vf_title)).lower()
            if d_norm == v_norm:
                positives.append({"signal": "dv_consensus", "detail": dc_title})
                total += cls.WEIGHTS["dv_consensus"]

        # ─── Curated abbreviation hint ───
        # A registry hit is a recall hint. It becomes a weak positive only when
        # the packet also has an independent work anchor and no semantic no-work
        # signal.
        _alias_hint = cls._find_curated_alias_hint(ctx, gk=gk, disc=disc)
        if _alias_hint and _alias_hint.get("eligible"):
            positives.append({
                "signal": "abbreviation_match",
                "detail": (
                    f"{_alias_hint.get('alias')}→{_alias_hint.get('canonical')} "
                    f"({ _alias_hint.get('registry') }, hint_with_work_anchor)"
                ),
            })
            total += cls.WEIGHTS["abbreviation_match"]
        elif _alias_hint:
            conflicts.append(
                "curated alias hint lacks independent work anchor or is blocked by semantic no-work"
            )

        # ─── 🆕 댓글 작품명 언급 ───
        # Critic이 감지한 제목이 댓글에서도 언급되면 추가 신호
        if cr_titles:
            _comments_text_ev = " ".join(
                str(c) for c in (getattr(ctx, "comments", None) or [])
                if isinstance(c, str)
            ).lower()
            for _ct in cr_titles[:3]:
                _ct_norm = str(_ct).replace(" ", "").lower()
                if _ct_norm and _ct_norm in _comments_text_ev.replace(" ", ""):
                    positives.append({"signal": "comment_title", "detail": _ct})
                    total += cls.WEIGHTS["comment_title"]
                    break

        # ─── Penalty: hypothesis invalidation ───
        if hasattr(ctx, 'hypothesis_history') and ctx.hypothesis_history:
            invalidated = [h for h in ctx.hypothesis_history if h.get("invalidated")]
            if invalidated:
                negatives.append({"signal": "hypothesis_invalidated", "detail": f"{len(invalidated)} invalidated"})
                total += cls.PENALTIES["hypothesis_invalidated"]

        # ─── Conflict detection ───
        # Decoder vs Verifier relevance conflict
        if dc_conf in ("high", "max") and vf_relevant is False:
            conflicts.append("Decoder=High but Verifier=irrelevant")
        if dc_conf in ("none", "") and vf_relevant is True:
            conflicts.append("Decoder=None but Verifier=relevant")
        # Gatekeeper vs Verifier conflict
        if gk_noise and vf_relevant is True:
            conflicts.append("Gatekeeper=noise but Verifier=relevant")
        if not gk_noise and vf_relevant is False and dc_conf in ("high", "max"):
            conflicts.append("Gatekeeper=OK, Decoder=High but Verifier=irrelevant")

        # Phase31: Gatekeeper noise override 충돌 (GK가 원래 반대했음)
        if _original_gk_noise and not gk_noise:
            conflicts.append(
                f"Gatekeeper=originally_noise (overridden by {getattr(ctx, 'noise_override_reason', '?')})"
            )

        # Phase31: Verifier critical counter_argument 충돌
        _vf_counters = (vr.get("counter_arguments") or [])
        _has_vf_critical = any(
            isinstance(ca, dict)
            and str(ca.get("severity", "")).lower() == "critical"
            for ca in _vf_counters
        )
        if _has_vf_critical:
            _critical_issues = [
                str(ca.get("issue", ""))[:80]
                for ca in _vf_counters
                if isinstance(ca, dict) and str(ca.get("severity", "")).lower() == "critical"
            ]
            negatives.append({
                "signal": "verifier_critical_counter",
                "detail": "; ".join(_critical_issues),
            })
            total += cls.PENALTIES["verifier_critical_counter"]
            conflicts.append(f"Verifier critical counter: {'; '.join(_critical_issues)[:120]}")

        # Phase31: Decoder 장르 충돌 (genre_term + novel_title 동시 발견)
        _decoder_genre_collision = False
        for _dterm in (dc.get("decoded_terms") or []):
            if not isinstance(_dterm, dict):
                continue
            _interps = _dterm.get("interpretations") or []
            _has_novel_interp = any(
                isinstance(i, dict) and str(i.get("type", "")).lower() in ("novel_title", "abbreviation")
                for i in _interps
            )
            _has_genre_interp = any(
                isinstance(i, dict) and str(i.get("type", "")).lower() in ("genre_term", "slang", "trope")
                for i in _interps
            )
            if _has_novel_interp and _has_genre_interp:
                _decoder_genre_collision = True
                _collision_term = _dterm.get("original", "?")
                negatives.append({
                    "signal": "decoder_genre_collision",
                    "detail": f"'{_collision_term}' = novel_title + genre_term 동시 등장",
                })
                total += cls.PENALTIES["decoder_genre_collision"]
                conflicts.append(
                    f"Decoder genre collision: '{_collision_term}' 은 장르용어이자 동명 소설이 존재"
                )
                break  # 하나만 발견해도 충분

        # ─── Expert agreement ───
        # Phase31: 원본 GK 투표를 사용 (override 전 반대 의견 반영)
        votes_relevant: List[bool] = []
        if _original_gk_noise:
            # GK가 원래 noise라고 했으니 반대 투표
            votes_relevant.append(False)
        elif gk_noise is not None:
            votes_relevant.append(not gk_noise)
        if dc_conf in ("high", "max", "medium"):
            votes_relevant.append(True)
        elif dc_conf in ("none", "", "low"):
            votes_relevant.append(False)
        if vf_relevant is not None:
            votes_relevant.append(vf_relevant)

        if votes_relevant:
            majority = sum(1 for v in votes_relevant if v) / len(votes_relevant)
        else:
            majority = 0.5

        # ─── Relevance probability ───
        if total >= 12:
            prob = "very_high"
        elif total >= 7:
            prob = "high"
        elif total >= 3:
            prob = "medium"
        elif total >= 0:
            prob = "low"
        else:
            prob = "very_low"

        # ─── Recommendation ───
        if total >= 7 and not conflicts:
            recommendation = "STRONG_RELEVANT: 증거가 압도적으로 관련성을 지지합니다."
        elif total >= 7 and conflicts:
            recommendation = "LIKELY_RELEVANT_WITH_CONFLICT: 증거는 강하나 전문가 충돌이 있습니다. 증거를 우선하세요."
        elif total >= 3:
            recommendation = "MODERATE: 관련성 증거가 중간 수준입니다. 추가 맥락 분석이 필요합니다."
        elif total >= 0:
            recommendation = "WEAK: 관련성 증거가 약합니다. 신중한 판단이 필요합니다."
        else:
            recommendation = "UNLIKELY_RELEVANT: 관련성 증거가 매우 약하거나 반증이 강합니다."

        return {
            "total_score": round(total, 2),
            "relevance_probability": prob,
            "positive_signals": positives,
            "negative_signals": negatives,
            "expert_agreement": round(majority, 2),
            "conflict_detected": len(conflicts) > 0,
            "conflict_details": conflicts,
            "recommendation": recommendation,
        }

    @classmethod
    def format_for_prompt(cls, score_result: Dict[str, Any]) -> str:
        """EvidenceScorer 결과를 Arbiter 프롬프트에 주입할 텍스트로 포맷."""
        lines = [
            "\n\n=== EVIDENCE SCORER (코드레벨 객관적 증거 분석) ===",
            f"📊 총 증거 점수: {score_result['total_score']} (관련성 확률: {score_result['relevance_probability']})",
            f"📊 전문가 합의도: {score_result['expert_agreement']:.0%}",
            f"📊 추천: {score_result['recommendation']}",
        ]

        if score_result["positive_signals"]:
            lines.append("\n✅ 긍정 신호:")
            for sig in score_result["positive_signals"][:8]:
                lines.append(f"  + {sig['signal']}: {sig['detail']}")

        if score_result["negative_signals"]:
            lines.append("\n❌ 부정 신호:")
            for sig in score_result["negative_signals"][:8]:
                lines.append(f"  - {sig['signal']}: {sig['detail']}")

        if score_result["conflict_detected"]:
            lines.append("\n⚠️ 전문가 충돌 감지:")
            for c in score_result["conflict_details"]:
                lines.append(f"  ⚡ {c}")
            lines.append("→ 충돌이 있을 때는 증거 점수와 맥락을 기반으로 판단하세요.")

        lines.append(
            "\n⚠️ 위 점수는 코드 레벨에서 계산된 객관적 지표입니다. "
            "LLM 판단의 보조 근거로 활용하되, 본문 맥락 분석과 함께 종합 판단하세요."
        )

        return "\n".join(lines)

    @staticmethod
    def _is_novel_platform(url: str) -> bool:
        """소설 플랫폼 URL인지 확인."""
        platforms = [
            "novelpia.com", "munpia.com", "joara.com", "kakaopage.com",
            "series.naver.com", "ridibooks.com", "bookcube.com",
            "novel.naver.com", "page.kakao.com", "tapas.io",
        ]
        url_lower = url.lower()
        return any(p in url_lower for p in platforms)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# A: Jury Panel (3× 병렬 Arbiter 호출 + 다수결)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Jury member별 관점 프롬프트 추가문구
JURY_PERSPECTIVES = [
    # Juror 1: 증거 중심 (Evidence-focused)
    (
        "\n\n=== YOUR PERSPECTIVE: EVIDENCE ANALYST (증거 분석가) ===\n"
        "당신은 증거 중심 분석가입니다. 객관적 증거에 가장 높은 가중치를 두세요:\n"
        "- 소설 플랫폼 URL 존재 여부 (가장 강력한 증거)\n"
        "- 검색 결과에서의 작품 확인\n"
        "- 본문/댓글에서의 작품 고유 정보 (캐릭터명, 줄거리)\n"
        "- Verifier의 confidence level: High=신뢰, Medium=참고, Low=매우 의심\n"
        "- 커뮤니티 게시글에서만 발견되고 소설 플랫폼에 없는 제목은 증거 불충분\n"
        "추측이나 간접 추론보다 직접 증거를 우선하세요.\n"
    ),
    # Juror 2: 맥락 중심 (Context-focused)
    (
        "\n\n=== YOUR PERSPECTIVE: CONTEXT SPECIALIST (맥락 전문가) ===\n"
        "당신은 맥락 분석 전문가입니다. 담론적 연결에 가장 높은 가중치를 두세요:\n"
        "- 본문/댓글의 어휘 클러스터 (소설 세계 vs 현실 세계)\n"
        "- 게시글의 화행 유형 (리뷰, 추천 요청, 잡담)\n"
        "- 제목과 본문의 담론 영역 일치 여부\n"
        "표면적 키워드 매칭보다 실제 대화의 맥락을 우선하세요.\n"
    ),
    # Juror 3: 보수적 판단 (Conservative)
    (
        "\n\n=== YOUR PERSPECTIVE: SKEPTICAL REVIEWER (회의적 검증자) ===\n"
        "당신은 보수적 검증자입니다. False Positive를 최소화하는 것이 목표입니다:\n"
        "- '의심스러우면 비관련'이 기본 원칙\n"
        "- 키워드 우연 일치 가능성을 항상 고려\n"
        "- 커뮤니티 은어와 소설 용어의 혼동 주의\n"
        "확실한 증거가 있을 때만 is_relevant=true로 판정하세요.\n"
    ),
]


class JuryPanel:
    """
    3명의 Arbiter를 다른 관점으로 병렬 호출하고 다수결로 최종 판정.
    """

    def __init__(self, arbiter_expert: "ArbiterExpert"):
        self.arbiter = arbiter_expert

    @staticmethod
    def _resolve_jury_max_tokens() -> int:
        try:
            global_cap = int(os.getenv("LLM_EXPERT_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "32768")))
        except Exception:
            global_cap = 32768
        try:
            configured = int(os.getenv("LLM_JURY_MAX_TOKENS", "2048"))
        except Exception:
            configured = 2048
        return max(512, min(configured, global_cap, 8192))

    def deliberate(
        self,
        user_prompt: str,
        ctx: "ConversationContext",
        gatekeeper_result: Dict[str, Any],
        decoder_result: Dict[str, Any],
        verifier_result: Dict[str, Any],
        discourse_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        3× 병렬 Arbiter 호출 → 다수결 판정.

        Returns:
            {
                "jury_results": [result1, result2, result3],
                "jury_votes": {"relevant": N, "irrelevant": N},
                "jury_titles": {"title": count, ...},
                "majority_decision": final_merged_result,
                "dissent_reasons": [...],
            }
        """
        from ..prompts.prompt_router import build_arbiter_system_prompt
        from ..prompts.expert_prompts import PLATFORM_ABBREVIATION_MAP

        print(f"[{_ts()}][⚖️🗳️] Jury Panel 시작: 3명 병렬 호출", file=sys.stderr)

        # 각 juror에게 다른 관점 프롬프트 추가
        # 🆕 Phase40: Arbiter _title_deliberately_null 사유 + Verifier confidence 경고를 Jury에 주입
        _jury_extra_context = ""
        _primary_arbiter = getattr(ctx, '_primary_arbiter_result', None)
        if _primary_arbiter:
            _p_dec = _primary_arbiter.get('final_decision', {})
            if _p_dec.get('_title_deliberately_null'):
                _arb_reasoning = _primary_arbiter.get('final_reasoning', '')
                _arb_reasoning_short = _arb_reasoning[:500] if _arb_reasoning else '(사유 미기재)'
                _jury_extra_context += (
                    "\n\n=== ⚠️ ARBITER NULL-TITLE 판정 (중요) ===\n"
                    "Primary Arbiter가 이 게시글에 대해 **의도적으로 제목=null**로 판정했습니다.\n"
                    f"Arbiter 판정 사유: {_arb_reasoning_short}\n"
                    "이는 Arbiter가 '본문에서 특정 작품을 식별할 수 없다'고 신중하게 결론 내린 것입니다.\n"
                    "이 판정을 뒤집으려면 **구체적이고 직접적인 증거**(소설 플랫폼 URL, 작가명+작품명 등)가 필요합니다.\n"
                    "Verifier가 Low confidence로 제안한 제목만으로는 뒤집기에 **불충분**합니다.\n"
                )
        # Verifier confidence 경고
        from .orchestrator import ExpertType
        _vf_out_jury = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        _vf_result_jury = _vf_out_jury.get('verification_result') or {}
        _vf_ni_jury = _vf_result_jury.get('novel_identity') or {}
        _vf_conf_jury = str(_vf_ni_jury.get('confidence', '')).lower()
        _vf_title_jury = _vf_ni_jury.get('official_novel_title') or _vf_ni_jury.get('official_title')
        if _vf_conf_jury == 'low' and _vf_title_jury:
            _jury_extra_context += (
                f"\n\n=== ⚠️ VERIFIER LOW-CONFIDENCE (중요) ===\n"
                f"Verifier가 '{_vf_title_jury}'를 Low confidence로 제안했습니다.\n"
                f"Low confidence = 확실하지 않은 추정. 이것만으로 is_relevant=True를 확정하지 마세요.\n"
                f"특히 해당 제목이 소설 플랫폼(novelpia, munpia, series.naver.com)에서 확인되지 않고 "
                f"커뮤니티 게시글에서만 발견된 경우, **소설이 아닌 밈/캐릭터 그룹명일 가능성**이 높습니다.\n"
            )

        prompts = []
        for perspective in JURY_PERSPECTIVES:
            prompts.append(user_prompt + _jury_extra_context + perspective)

        # 시스템 프롬프트 구성
        from .arbiter import ARBITER_SYSTEM, PLATFORM_ABBREVIATION_MAP as PAM
        base_system = ARBITER_SYSTEM.replace("{platform_map}", PAM)
        system_content = build_arbiter_system_prompt(
            base_system,
            gatekeeper_result=gatekeeper_result,
            decoder_result=decoder_result,
            verifier_result=verifier_result,
            discourse_result=discourse_result,
            ctx=ctx,
        )

        max_tokens = self._resolve_jury_max_tokens()

        results = [None, None, None]

        def _call_juror(idx: int, prompt: str) -> Dict[str, Any]:
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ]
            tag = f"arbiter_jury_{idx}"
            response_text = self.arbiter.llm._stream_chat_http(
                messages=messages,
                tag=tag,
                use_grammar=True,
                max_tokens=max_tokens,
                quiet=True,
            )
            return self.arbiter._parse_json_response(response_text)

        # 병렬 실행 (ThreadPoolExecutor)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for i, prompt in enumerate(prompts):
                fut = executor.submit(_call_juror, i, prompt)
                futures[fut] = i

            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    result = fut.result()
                    results[idx] = result
                    _decision = (result or {}).get("final_decision", {})
                    _relevant = _decision.get("is_relevant")
                    _title = _decision.get("official_novel_title") or _decision.get("official_title")
                    print(
                        f"[{_ts()}][⚖️🗳️] Juror {idx} 완료: "
                        f"relevant={_relevant}, title={_title}",
                        file=sys.stderr,
                    )
                except Exception as e:
                    print(
                        f"[{_ts()}][⚖️🗳️] Juror {idx} 오류: {e}",
                        file=sys.stderr,
                    )
                    results[idx] = None

        # 투표 집계
        valid_results = [r for r in results if r and "final_decision" in r]
        if not valid_results:
            print(f"[{_ts()}][⚖️🗳️] Jury Panel 실패: 유효한 결과 없음", file=sys.stderr)
            return {"jury_failed": True}

        votes_relevant = sum(
            1 for r in valid_results
            if r.get("final_decision", {}).get("is_relevant") is True
        )
        votes_irrelevant = len(valid_results) - votes_relevant

        # 제목 투표
        title_counts: Dict[str, int] = {}
        for r in valid_results:
            dec = r.get("final_decision", {})
            t = dec.get("official_novel_title") or dec.get("official_title")
            if t:
                t_norm = re.sub(r"\s+", "", str(t)).lower()
                # 정규화된 제목으로 투표하되, 원본 유지
                title_counts[t] = title_counts.get(t, 0) + 1

        # 다수결 결정
        majority_relevant = votes_relevant > votes_irrelevant

        # 다수파 중 가장 좋은 결과 선택
        if majority_relevant:
            majority_results = [
                r for r in valid_results
                if r.get("final_decision", {}).get("is_relevant") is True
            ]
        else:
            majority_results = [
                r for r in valid_results
                if r.get("final_decision", {}).get("is_relevant") is not True
            ]

        # 다수파의 첫 번째 결과를 기본으로 사용
        majority_decision = majority_results[0] if majority_results else valid_results[0]

        # 제목: 가장 많이 투표된 제목 사용
        if title_counts and majority_relevant:
            best_title = max(title_counts, key=title_counts.get)
            majority_decision.setdefault("final_decision", {})["official_novel_title"] = best_title

        # 소수파 의견 수집 (dissent)
        dissent_reasons = []
        for r in valid_results:
            dec = r.get("final_decision", {})
            is_rel = dec.get("is_relevant")
            if is_rel != majority_relevant:
                reason = r.get("final_reasoning", "") or dec.get("reasoning", "")
                dissent_reasons.append(reason[:200])

        print(
            f"[{_ts()}][⚖️🗳️] Jury Panel 결과: "
            f"relevant={votes_relevant}, irrelevant={votes_irrelevant} "
            f"→ 다수결={'관련' if majority_relevant else '비관련'}",
            file=sys.stderr,
        )

        return {
            "jury_results": results,
            "jury_votes": {
                "relevant": votes_relevant,
                "irrelevant": votes_irrelevant,
            },
            "jury_titles": title_counts,
            "majority_decision": majority_decision,
            "dissent_reasons": dissent_reasons,
            "jury_failed": False,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# B: Debate Pattern (Advocate → Skeptic → Judge)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ADVOCATE_SYSTEM = """\
You are the ADVOCATE (옹호자) in a deliberation about whether a community post discusses a specific web novel.

YOUR ROLE: Argue FOR relevance (is_relevant=true).
- Present all evidence supporting the post's connection to a specific novel
- Highlight Decoder matches, Verifier confirmations, platform URLs
- Interpret ambiguous signals favorably for relevance
- Consider community slang/abbreviations as potential novel references
- Before arguing, internally classify the post into one of these scope types:
  1) direct_work_discussion
  2) adjacent_meta_or_fandom
  3) multi_work_reference
  4) work_internal_concept (song, martial art, in-universe object, review title)
  5) generic_or_off_topic
- If the post is 2), argue for relevance with official title null unless there is a direct work anchor.
- If the post is 3), do not force a single title unless one work is clearly the main subject.
- If the post is 4), require a bridge from the internal concept to the parent work; community/review page title alone is not enough.

You must output valid JSON only:
{{
  "argument": "string (Korean, your argument for relevance)",
  "key_evidence": ["string"],
  "proposed_title": "string | null",
  "confidence": "High" | "Medium" | "Low",
  "strongest_point": "string (Korean, single most compelling evidence)"
}}
"""

SKEPTIC_SYSTEM = """\
You are the SKEPTIC (회의론자) in a deliberation about whether a community post discusses a specific web novel.

You have seen the Advocate's argument. YOUR ROLE: Challenge it and argue against relevance.
- Point out weaknesses in the evidence
- Identify keyword coincidences vs genuine references
- Highlight community banter, genre tropes, or off-topic signals
- Note if Decoder matches are based on weak morphological similarity only
- Check if the post discusses the novel or just mentions it in passing
- **CRITICAL**: If DISSENT information is provided (Gatekeeper originally said noise, \
Verifier raised critical counter-arguments, or genre collision detected), \
treat these as STRONG evidence for your skeptical position. \
A term that is BOTH a genre trope AND a novel title is especially suspicious — \
"existence of a same-named novel" ≠ "the post discusses that novel".
- **CRITICAL**: If the proposed title exists ONLY in community posts (DC갤, 아카라이브, 에펨코리아) \
and NOT on any novel platform (novelpia, munpia, series.naver.com, kakaopage, joara), \
consider whether it might be a community meme, character group abbreviation, or inside joke. \
However, DO NOT automatically reject it — community-specific terms can still be relevant \
if they refer to specific novels, characters from specific novels, or well-known abbreviations. \
Use the SEARCH RESULTS to determine what the term actually means in context.
- Explicitly test these failure modes:
  1) review/arena/community post title mistaken for a novel title
  2) fanart/cover/release meta mistaken for direct plot discussion
  3) multiple works used as examples but one title over-promoted
  4) in-work concept (song, technique, slogan, nickname) mistaken for the parent work without direct bridge
  5) generic trope/concept mistaken for a specific title
- If the post is still novel-related but not direct-work discussion, prefer the conclusion “relevant but title should remain null/adjacent”.

You must output valid JSON only:
{{
  "rebuttal": "string (Korean, your counter-argument)",
  "weaknesses_found": ["string"],
  "alternative_interpretation": "string (Korean)",
  "confidence_against": "High" | "Medium" | "Low",
  "strongest_counterpoint": "string (Korean)"
}}
"""

JUDGE_SYSTEM = """\
You are the JUDGE (판사) in a deliberation. You have heard both the Advocate and the Skeptic.

YOUR ROLE: Make the final, balanced decision.
- Weigh the Advocate's evidence against the Skeptic's counter-arguments
- Consider the objective Evidence Score provided
- Make a fair, evidence-based judgment
- **IMPORTANT**: If DISSENT information shows the Gatekeeper originally flagged this as noise \
but was overridden, or the Verifier raised critical counter-arguments, \
give significant weight to these signals. Pipeline overrides can introduce false positives.
- If a keyword is both a genre trope and a novel title, require STRONG direct evidence \
(author name, chapter numbers, platform URL, plot-specific details) to confirm the post discusses the novel. \
"The same-named novel exists" alone is NOT sufficient evidence.
- **IMPORTANT**: A title that appears ONLY in community posts (DC갤러리, 아카라이브) \
but NOT on any novel platform (novelpia, munpia, series.naver.com) is likely NOT a real novel title. \
Community-only titles are often memes, character group abbreviations, or inside jokes.
- First, internally classify the discourse scope:
  1) direct_work_discussion
  2) adjacent_meta_or_fandom
  3) multi_work_reference
  4) work_internal_concept
  5) generic_or_off_topic
- Decision policy:
  - 1) can be relevant + single title
  - 2) can be relevant, but official_novel_title should usually be null
  - 3) can be relevant, but official_novel_title should usually be null unless one work is clearly central
  - 4) require an explicit bridge from the concept/review page/song/technique to the parent work before assigning title
  - 5) should usually be irrelevant
- Treat review pages, arena posts, fanart pages, cover posts, and community summaries as weak evidence for title promotion unless they directly link and ground the parent work in the post body.
- If a generic/trope-like token could match a standalone title, but another interpretation explains the post via character/IP anchors more coherently, do NOT output the trope-matched title. Prefer relevant + official_novel_title=null.
- If the final_reasoning concludes “작품 주변 메타/팬아트/플랫폼 주변 담론” then do NOT collapse it to irrelevant by default.

You must output valid JSON matching the standard Arbiter output schema:
{{
  "final_decision": {{
    "is_relevant": boolean,
    "is_novel_discussion": boolean,
    "official_novel_title": "string | null",
    "confidence": "Max" | "High" | "Medium" | "Low" | "None",
    "discussion_type": "string"
  }},
  "judge_reasoning": "string (Korean, explain how you weighed both sides)",
  "advocate_strength": "strong" | "moderate" | "weak",
  "skeptic_strength": "strong" | "moderate" | "weak",
  "final_reasoning": "string (Korean)"
}}
"""


class DebateDeliberation:
    """
    Advocate → Skeptic → Judge 3단계 토론으로 최종 판정.
    """

    def __init__(self, llm_client: "LLMClient"):
        self.llm = llm_client

    @staticmethod
    def _resolve_debate_max_tokens() -> int:
        try:
            global_cap = int(os.getenv("LLM_EXPERT_MAX_TOKENS", os.getenv("LLM_MAX_TOKENS", "32768")))
        except Exception:
            global_cap = 32768
        try:
            configured = int(os.getenv("LLM_DEBATE_MAX_TOKENS", "2048"))
        except Exception:
            configured = 2048
        return max(512, min(configured, global_cap, 8192))

    def deliberate(
        self,
        post_summary: str,
        expert_summary: str,
        evidence_score_text: str,
        initial_arbiter_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Advocate→Skeptic→Judge 순차 토론.

        Args:
            post_summary: 게시글 요약 (제목, 본문 미리보기, 댓글 수)
            expert_summary: 전문가 판정 요약
            evidence_score_text: EvidenceScorer 포맷 텍스트
            initial_arbiter_result: 기본 Arbiter 결과 (참고용)

        Returns:
            Judge의 최종 판정 dict
        """
        max_tokens = self._resolve_debate_max_tokens()

        # ── Step 1: Advocate ──
        print(f"[{_ts()}][⚖️💬] Debate Step 1: Advocate (옹호자) 발언", file=sys.stderr)

        advocate_user = (
            f"=== POST SUMMARY ===\n{post_summary}\n\n"
            f"=== EXPERT ANALYSIS ===\n{expert_summary}\n\n"
            f"{evidence_score_text}\n\n"
            "이 게시글이 특정 웹소설 작품에 대해 이야기하고 있다고 옹호하세요. "
            "모든 가능한 증거와 논거를 제시하세요."
        )

        if initial_arbiter_result:
            init_dec = initial_arbiter_result.get("final_decision", {})
            advocate_user += (
                f"\n\n=== 초기 Arbiter 판정 (참고) ===\n"
                f"is_relevant={init_dec.get('is_relevant')}, "
                f"title={init_dec.get('official_novel_title')}, "
                f"confidence={init_dec.get('confidence')}"
            )

        advocate_result = self._call_role(ADVOCATE_SYSTEM, advocate_user, "advocate", max_tokens)
        if not advocate_result:
            print(f"[{_ts()}][⚖️💬] Advocate 실패 → 토론 중단", file=sys.stderr)
            return {"debate_failed": True}

        print(
            f"[{_ts()}][⚖️💬] Advocate: conf={advocate_result.get('confidence')}, "
            f"title={advocate_result.get('proposed_title')}",
            file=sys.stderr,
        )

        # ── Step 2: Skeptic ──
        print(f"[{_ts()}][⚖️💬] Debate Step 2: Skeptic (회의론자) 반론", file=sys.stderr)

        skeptic_user = (
            f"=== POST SUMMARY ===\n{post_summary}\n\n"
            f"=== EXPERT ANALYSIS ===\n{expert_summary}\n\n"
            f"{evidence_score_text}\n\n"
            f"=== ADVOCATE'S ARGUMENT ===\n"
            f"{json.dumps(advocate_result, ensure_ascii=False, indent=2)}\n\n"
            "위 옹호자의 주장을 검토하고 반론을 제기하세요. "
            "증거의 약점, 대안적 해석, 키워드 우연 일치 가능성을 분석하세요."
        )

        skeptic_result = self._call_role(SKEPTIC_SYSTEM, skeptic_user, "skeptic", max_tokens)
        if not skeptic_result:
            print(f"[{_ts()}][⚖️💬] Skeptic 실패 → 토론 중단", file=sys.stderr)
            return {"debate_failed": True}

        print(
            f"[{_ts()}][⚖️💬] Skeptic: conf_against={skeptic_result.get('confidence_against')}",
            file=sys.stderr,
        )

        # ── Step 3: Judge ──
        print(f"[{_ts()}][⚖️💬] Debate Step 3: Judge (판사) 최종 판정", file=sys.stderr)

        judge_user = (
            f"=== POST SUMMARY ===\n{post_summary}\n\n"
            f"=== EXPERT ANALYSIS ===\n{expert_summary}\n\n"
            f"{evidence_score_text}\n\n"
            f"=== ADVOCATE'S ARGUMENT ===\n"
            f"{json.dumps(advocate_result, ensure_ascii=False, indent=2)}\n\n"
            f"=== SKEPTIC'S REBUTTAL ===\n"
            f"{json.dumps(skeptic_result, ensure_ascii=False, indent=2)}\n\n"
            "양측의 주장을 모두 검토하고 최종 판정을 내리세요. "
            "객관적 증거와 맥락을 기반으로 공정한 판단을 하세요."
        )

        if initial_arbiter_result:
            init_dec = initial_arbiter_result.get("final_decision", {})
            judge_user += (
                f"\n\n=== 초기 Arbiter 판정 (참고) ===\n"
                f"is_relevant={init_dec.get('is_relevant')}, "
                f"title={init_dec.get('official_novel_title')}, "
                f"confidence={init_dec.get('confidence')}"
            )

        judge_result = self._call_role(JUDGE_SYSTEM, judge_user, "judge", max_tokens)
        if not judge_result:
            print(f"[{_ts()}][⚖️💬] Judge 실패 → 토론 중단", file=sys.stderr)
            return {"debate_failed": True}

        judge_dec = judge_result.get("final_decision", {})
        print(
            f"[{_ts()}][⚖️💬] Judge 판정: "
            f"relevant={judge_dec.get('is_relevant')}, "
            f"title={judge_dec.get('official_novel_title')}, "
            f"conf={judge_dec.get('confidence')}",
            file=sys.stderr,
        )

        return {
            "advocate": advocate_result,
            "skeptic": skeptic_result,
            "judge": judge_result,
            "debate_failed": False,
        }

    def _call_role(
        self, system_prompt: str, user_prompt: str, tag: str, max_tokens: int
    ) -> Optional[Dict[str, Any]]:
        """LLM을 특정 역할로 호출."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response_text = self.llm._stream_chat_http(
                messages=messages,
                tag=f"debate_{tag}",
                use_grammar=True,
                max_tokens=max_tokens,
            )
            if not response_text:
                return None
            # parse JSON
            from .utils import parse_json_with_think_removal
            return parse_json_with_think_removal(response_text)
        except Exception as e:
            print(f"[{_ts()}][⚖️💬] {tag} LLM 호출 오류: {e}", file=sys.stderr)
            return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Multi-Expert Deliberation Orchestrator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class DeliberationOrchestrator:
    """
    A+B+C 세 가지 접근법을 통합 관리하는 오케스트레이터.

    흐름:
      1. EvidenceScorer 실행 (항상)
      2. 기본 Arbiter 호출 (1회)
      3. conflict_score 계산
      4. conflict 시: Jury Panel + Debate 병렬 실행
      5. 최종 합성
    """

    # conflict 감지 임계값
    CONFLICT_THRESHOLD = 0.4  # expert_agreement가 이 이하이면 conflict

    def __init__(self, arbiter_expert: "ArbiterExpert", llm_client: "LLMClient"):
        self.arbiter = arbiter_expert
        self.llm = llm_client
        self.evidence_scorer = EvidenceScorer()
        self.jury_panel = JuryPanel(arbiter_expert)
        self.debate = DebateDeliberation(llm_client)

    def _title_mentioned_in_post_main_context(
        self,
        ctx: "ConversationContext",
        title: Optional[str],
    ) -> bool:
        """제목/본문(댓글 제외)에 정식 제목 또는 안정적 축약어가 등장하는지 확인."""
        if not ctx or not title:
            return False

        post_data = getattr(ctx, "post_data", None) or {}
        chunks: List[str] = [str(post_data.get("title") or "")]
        for block in post_data.get("content_blocks", []) or []:
            if isinstance(block, dict):
                chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                chunks.append(block)

        raw_text = " ".join(chunks)
        if not raw_text.strip():
            return False

        def _norm(text: str) -> str:
            return re.sub(r"[^\w가-힣]", "", str(text or "")).lower()

        norm_title = _norm(title)
        norm_text = _norm(raw_text)
        if norm_title and norm_title in norm_text:
            return True

        from .orchestrator import ExpertType

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        for term in decoder_out.get("decoded_terms", []) or []:
            if not isinstance(term, dict):
                continue
            best = term.get("best_match") or {}
            matched_title = str(best.get("title") or "").strip()
            if _norm(matched_title) != norm_title:
                continue
            original = str(term.get("original") or "").strip()
            if original and len(original) >= 2 and original.lower() in raw_text.lower():
                return True
        return False

    def _should_preserve_deliberate_null(
        self,
        ctx: Optional["ConversationContext"],
        primary_decision: Dict[str, Any],
        best_title: Optional[str],
        verifier_result: Dict[str, Any],
        jury_votes: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, str]:
        """작가 신작/약한 앵커 케이스에서는 deliberation이 null-title을 되살리지 않게 한다."""
        if not ctx or not best_title or not primary_decision.get("_title_deliberately_null"):
            return False, ""

        null_reasons = {
            str(x).strip()
            for x in (primary_decision.get("_title_null_block_reasons") or [])
            if str(x or "").strip()
        }
        if "temporal_reference_guard" not in null_reasons:
            return False, ""

        title_in_main = self._title_mentioned_in_post_main_context(ctx, best_title)
        if title_in_main:
            return False, ""

        post_title = str((getattr(ctx, "post_data", None) or {}).get("title") or "")
        post_title_compact = re.sub(r"\s+", "", post_title.lower())
        shinwork_kws = ("신작", "최신작", "새작품", "이번작", "차기작", "신간")
        launch_kws = ("스타트", "초반", "초반부", "첫인상", "첫화", "도입", "출발")
        has_author_new_work_context = (
            any(kw in post_title_compact for kw in shinwork_kws)
            or any(kw in post_title_compact for kw in launch_kws)
        )

        from .orchestrator import ExpertType

        decoder_out = ctx.get_expert_output(ExpertType.DECODER) or {}
        has_author_anchor = False
        for term in decoder_out.get("decoded_terms", []) or []:
            if not isinstance(term, dict):
                continue
            grounding = term.get("grounding") or {}
            anchor_type = str(grounding.get("anchor_type") or "").strip().lower()
            if term.get("is_author_name") or anchor_type == "author_mention":
                has_author_anchor = True
                break

        vf_grounding = verifier_result.get("grounding_check") or {}
        vf_anchor = str(vf_grounding.get("anchor_found") or "").strip().lower()
        weak_anchor = vf_anchor in {"title_mention", "search_only", "none", ""}
        jury_votes = jury_votes or {}
        jury_relevant = int(jury_votes.get("relevant", 0) or 0)
        jury_irrelevant = int(jury_votes.get("irrelevant", 0) or 0)
        jury_prefers_null = jury_irrelevant > jury_relevant

        if (has_author_new_work_context or has_author_anchor) and (weak_anchor or jury_prefers_null):
            reason_bits = []
            if weak_anchor:
                reason_bits.append(f"weak_anchor={vf_anchor or 'none'}")
            if jury_prefers_null:
                reason_bits.append(f"jury={jury_relevant}:{jury_irrelevant}")
            return True, (
                f"temporal_reference_guard + author_new_work + weak_anchor"
                f"({', '.join(reason_bits)}, title_in_post_main=false)"
            )
        return False, ""

    def run(self, ctx: "ConversationContext") -> Dict[str, Any]:
        """
        전체 심의 프로세스 실행.

        Returns:
            최종 Arbiter 결과 (표준 형식) + deliberation metadata
        """
        start_time = time.time()

        print(f"\n[{_ts()}][⚖️🔮] ═══ Multi-Expert Deliberation 시작 ═══", file=sys.stderr)

        # ── Step 1: EvidenceScorer (항상 실행, 0 cost) ──
        evidence_result = self.evidence_scorer.compute(ctx)
        evidence_text = self.evidence_scorer.format_for_prompt(evidence_result)

        print(
            f"[{_ts()}][⚖️🔮] EvidenceScorer: score={evidence_result['total_score']}, "
            f"prob={evidence_result['relevance_probability']}, "
            f"agreement={evidence_result['expert_agreement']:.0%}, "
            f"conflicts={len(evidence_result['conflict_details'])}",
            file=sys.stderr,
        )

        # ── Step 2: EvidenceScorer 결과를 ctx에 저장 ──
        ctx.evidence_score = evidence_result  # type: ignore

        # ── Step 3: 기본 Arbiter 호출 (EvidenceScorer 주입) ──
        # Arbiter analyze()가 이미 호출되었으므로, 여기서는 _inject_evidence_and_call을 사용
        primary_result = self._call_arbiter_with_evidence(ctx, evidence_text)

        if not primary_result or "final_decision" not in primary_result:
            print(f"[{_ts()}][⚖️🔮] 기본 Arbiter 실패 → EvidenceScorer 기반 폴백", file=sys.stderr)
            primary_result = self.arbiter._fallback_decision(ctx, "Primary arbiter failed in deliberation")

        primary_dec = primary_result.get("final_decision", {})
        print(
            f"[{_ts()}][⚖️🔮] 기본 Arbiter 결과: "
            f"relevant={primary_dec.get('is_relevant')}, "
            f"title={primary_dec.get('official_novel_title')}, "
            f"conf={primary_dec.get('confidence')}",
            file=sys.stderr,
        )

        # ── Step 4: Conflict 감지 ──
        need_deliberation = self._should_deliberate(evidence_result, primary_result, ctx)

        if not need_deliberation:
            elapsed = time.time() - start_time
            print(
                f"[{_ts()}][⚖️🔮] 전문가 합의 충분 → 추가 심의 불필요 ({elapsed:.1f}s)",
                file=sys.stderr,
            )
            primary_result["_deliberation"] = {
                "method": "evidence_scorer_only",
                "evidence_score": evidence_result,
                "conflict_detected": False,
                "elapsed": round(elapsed, 1),
            }
            return primary_result

        # ── Step 5: Jury Panel + Debate 실행 (conflict 감지됨) ──
        # Phase40: Primary Arbiter 결과를 ctx에 저장 (Jury가 null 사유 참조)
        ctx._primary_arbiter_result = primary_result
        print(
            f"[{_ts()}][⚖️🔮] ⚡ 전문가 충돌 감지 → Jury Panel + Debate 실행",
            file=sys.stderr,
        )

        # 게시글 요약 구성
        post_data = ctx.post_data or {}
        post_summary = self._build_post_summary(post_data, ctx.comments or [])
        expert_summary = self._build_expert_summary(ctx)

        # Jury Panel과 Debate (순차 실행 — LLM 서버 부하 고려)
        # Jury Panel 먼저 (3× 병렬)
        from .orchestrator import ExpertType
        gk = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        dc = ctx.get_expert_output(ExpertType.DECODER) or {}
        vf = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        disc = ctx.get_expert_output(ExpertType.DISCOURSE) or {}

        # Arbiter user_prompt 재구성
        arbiter_user_prompt = self._rebuild_arbiter_user_prompt(ctx, evidence_text)

        jury_result = self.jury_panel.deliberate(
            arbiter_user_prompt, ctx, gk, dc, vf, disc
        )

        # Debate — curated alias hint. This is not standalone proof.
        _debate_expert_summary = expert_summary
        _alias_note = EvidenceScorer.build_curated_alias_prompt_note(
            ctx,
            gk=gk,
            disc=disc,
            post_data=post_data,
        )
        if _alias_note:
            _debate_expert_summary += _alias_note
            print(
                f"[{_ts()}][⚖️💬] 🔑 Debate에 등록 약칭 힌트 주입(확정 근거 아님)",
                file=sys.stderr,
            )

        # Phase31: Debate에 dissent 정보 (원본 GK noise + Verifier critical) 주입
        _dissent_lines: List[str] = []
        _orig_gk_noise = getattr(ctx, "original_gatekeeper_noise", False)
        if _orig_gk_noise:
            _orig_gk_reason = getattr(ctx, "original_gatekeeper_noise_reason", "unknown")
            _override_reason = getattr(ctx, "noise_override_reason", "unknown")
            _dissent_lines.append(
                f"⚠️ **Gatekeeper 원본 판단**: 이 게시글을 noise로 판단했습니다. "
                f"(사유: {_orig_gk_reason})\n"
                f"   하지만 파이프라인에서 '{_override_reason}' 이유로 override되었습니다.\n"
                f"   **원본 Gatekeeper 의견을 진지하게 고려하세요.**"
            )
        _vf_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        _vf_counters_dissent = (_vf_out.get("verification_result") or {}).get("counter_arguments") or []
        _critical_counters = [
            ca for ca in _vf_counters_dissent
            if isinstance(ca, dict) and str(ca.get("severity", "")).lower() == "critical"
        ]
        if _critical_counters:
            _crit_issues = [str(ca.get("issue", ""))[:100] for ca in _critical_counters]
            _dissent_lines.append(
                f"⚠️ **Verifier Critical 반론**: Verifier가 중대한(critical) 반론을 제기했습니다:\n"
                + "\n".join(f"  - {issue}" for issue in _crit_issues)
                + "\n   **이 반론들이 해소되지 않으면 is_relevant=false를 적극 고려하세요.**"
            )
        # Genre collision from EvidenceScorer
        _ev_conflicts = (evidence_result.get("conflict_details") or [])
        _genre_collision_in_ev = [c for c in _ev_conflicts if "genre collision" in str(c).lower()]
        if _genre_collision_in_ev:
            _dissent_lines.append(
                f"⚠️ **장르용어-소설명 충돌**: Decoder가 동일 단어를 장르 용어이자 소설 제목으로 해석했습니다.\n"
                f"   '{_genre_collision_in_ev[0]}'\n"
                f"   **본문이 \"장르 밈/트로프\"를 논하는 것인지, 특정 소설을 논하는 것인지 구분하세요.**"
            )
        # Phase40: _title_deliberately_null 사유를 Debate에도 전달
        _p_dec_for_debate = primary_result.get("final_decision", {})
        if _p_dec_for_debate.get("_title_deliberately_null"):
            _arb_reasoning_debate = str(primary_result.get("final_reasoning", ""))[:400]
            _dissent_lines.append(
                f"⚠️ **Arbiter NULL-TITLE 판정**: Primary Arbiter가 의도적으로 title=null 판정.\n"
                f"   사유: {_arb_reasoning_debate}\n"
                f"   이 판정을 뒤집으려면 소설 플랫폼 URL, 작가명+작품명 등 **구체적 직접 증거**가 필요합니다.\n"
                f"   Verifier Low-confidence 제안만으로는 불충분합니다."
            )
        if _dissent_lines:
            _debate_expert_summary += (
                "\n\n=== ⚠️ DISSENT 정보 (반대 의견 요약) ===\n"
                + "\n\n".join(_dissent_lines)
            )
            print(
                f"[{_ts()}][⚖️💬] Phase31: Debate에 dissent 정보 주입 ({len(_dissent_lines)}건)",
                file=sys.stderr,
            )

        debate_result = self.debate.deliberate(
            post_summary, _debate_expert_summary, evidence_text,
            initial_arbiter_result=primary_result,
        )

        # ── Step 6: 최종 합성 ──
        self._last_ctx = ctx  # Phase40: _synthesize에서 Verifier conf 참조용
        final_result = self._synthesize_deliberation(
            primary_result, jury_result, debate_result, evidence_result
        )

        elapsed = time.time() - start_time
        final_result["_deliberation"] = {
            "method": "full_deliberation_ABC",
            "evidence_score": evidence_result,
            "conflict_detected": True,
            "jury_votes": jury_result.get("jury_votes"),
            "debate_advocate_conf": (debate_result.get("advocate") or {}).get("confidence"),
            "debate_skeptic_conf": (debate_result.get("skeptic") or {}).get("confidence_against"),
            "elapsed": round(elapsed, 1),
        }

        print(
            f"[{_ts()}][⚖️🔮] ═══ Multi-Expert Deliberation 완료 ({elapsed:.1f}s) ═══",
            file=sys.stderr,
        )

        return final_result

    def _should_deliberate(
        self,
        evidence: Dict[str, Any],
        primary: Dict[str, Any],
        ctx: "ConversationContext",
    ) -> bool:
        """심의가 필요한지 판단."""
        if self._should_skip_deliberation_for_clear_non_novel(primary, ctx):
            print(
                f"[{_ts()}][⚖️🔮] 심의 스킵: 명백한 비관련/플랫폼 메타 합의",
                file=sys.stderr,
            )
            return False

        if self._should_skip_deliberation_for_settled_veto(evidence, primary, ctx):
            print(
                f"[{_ts()}][⚖️🔮] 심의 스킵: Verifier critical veto + 음수 evidence로 비관련 확정",
                file=sys.stderr,
            )
            return False

        if self._should_skip_deliberation_for_memory_query_unresolved(primary, ctx):
            print(
                f"[{_ts()}][⚖️🔮] 심의 스킵: memory-query unresolved null-title",
                file=sys.stderr,
            )
            return False

        if self._should_skip_deliberation_for_title_lead_alias_resolved(evidence, primary, ctx):
            print(
                f"[{_ts()}][⚖️🔮] 심의 스킵: title-lead alias search bridge resolved",
                file=sys.stderr,
            )
            return False

        # Condition 1: 전문가 충돌 감지
        if evidence.get("conflict_detected"):
            print(f"[{_ts()}][⚖️🔮] 심의 트리거: 전문가 충돌 감지", file=sys.stderr)
            return True

        # Condition 2: 전문가 합의도 낮음
        agreement = evidence.get("expert_agreement", 1.0)
        if agreement <= self.CONFLICT_THRESHOLD:
            print(f"[{_ts()}][⚖️🔮] 심의 트리거: 합의도 {agreement:.0%} ≤ {self.CONFLICT_THRESHOLD:.0%}", file=sys.stderr)
            return True

        # Condition 3: 증거 점수와 Arbiter 판정 모순
        score = evidence.get("total_score", 0)
        primary_relevant = (primary.get("final_decision") or {}).get("is_relevant")
        if score >= 7 and primary_relevant is False:
            print(f"[{_ts()}][⚖️🔮] 심의 트리거: 증거점수={score} 높지만 Arbiter=비관련", file=sys.stderr)
            return True
        if score <= -1 and primary_relevant is True:
            print(f"[{_ts()}][⚖️🔮] 심의 트리거: 증거점수={score} 낮지만 Arbiter=관련", file=sys.stderr)
            return True

        # Condition 4: Arbiter confidence가 Low/None인데 suspected_titles가 있음
        primary_conf = str((primary.get("final_decision") or {}).get("confidence", "")).lower()
        suspected = getattr(ctx, 'suspected_titles', []) or []
        high_suspected = [
            t for t in suspected
            if str(t.get("confidence", "")).lower() in ("high", "max")
               or (isinstance(t.get("confidence"), (int, float)) and t.get("confidence", 0) >= 0.7)
        ]
        if primary_conf in ("low", "none") and high_suspected:
            print(f"[{_ts()}][⚖️🔮] 심의 트리거: Arbiter=Low/None이지만 고신뢰 suspected_titles 존재", file=sys.stderr)
            return True

        return False

    @staticmethod
    def _compact_match_text(text: Any) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]", "", str(text or "")).lower()

    @classmethod
    def _title_lead_alias_terms(cls, ctx: "ConversationContext", title: str) -> List[str]:
        post_data = getattr(ctx, "post_data", None) or {}
        post_title = str(post_data.get("title") or "").strip()
        if not post_title:
            return []

        first = post_title.split()[0] if post_title.split() else post_title
        first = re.split(r"[\]\)\},.!?;:/\\|\"'`~]+", first, maxsplit=1)[0]
        first = first.strip()
        if not first:
            return []

        suffixes = (
            "으로서는",
            "으로써는",
            "에게서는",
            "에서는",
            "이라는",
            "이라고",
            "이라면",
            "이라서",
            "으로도",
            "로도",
            "부터",
            "까지",
            "에게",
            "한테",
            "으로",
            "랑",
            "하고",
            "은",
            "는",
            "이",
            "가",
            "을",
            "를",
            "의",
            "에",
            "와",
            "과",
            "도",
            "만",
            "로",
        )
        candidates = [first]
        for suffix in suffixes:
            if len(first) > len(suffix) + 1 and first.endswith(suffix):
                candidates.append(first[: -len(suffix)])
                break

        title_norm = cls._compact_match_text(title)
        out: List[str] = []
        seen: set[str] = set()
        for cand in candidates:
            norm = cls._compact_match_text(cand)
            if len(norm) < 2 or norm == title_norm or norm in seen:
                continue
            seen.add(norm)
            out.append(cand)
        return out

    @classmethod
    def _search_results_support_title_lead_alias(
        cls,
        ctx: "ConversationContext",
        *,
        title: str,
        aliases: List[str],
        require_title_field: bool = False,
    ) -> bool:
        title_norm = cls._compact_match_text(title)
        if not title_norm or not aliases:
            return False
        alias_norms = [cls._compact_match_text(alias) for alias in aliases if cls._compact_match_text(alias)]
        if not alias_norms:
            return False

        for result in getattr(ctx, "search_results", []) or []:
            if not isinstance(result, dict):
                continue
            query_norm = cls._compact_match_text(result.get("query"))
            title_text_norm = cls._compact_match_text(result.get("title"))
            content_norm = cls._compact_match_text(
                " ".join(
                    str(result.get(key) or "")
                    for key in ("content", "snippet", "summary")
                )
            )
            merged_norm = f"{title_text_norm} {content_norm}"
            has_alias_edge = any(
                alias_norm
                and (
                    alias_norm in query_norm
                    or alias_norm in title_text_norm
                    or alias_norm in content_norm
                )
                for alias_norm in alias_norms
            )
            has_title_edge = title_norm in title_text_norm
            if require_title_field:
                if has_alias_edge and has_title_edge:
                    return True
                continue
            if has_alias_edge and (has_title_edge or title_norm in merged_norm):
                return True

        return False

    def _should_skip_deliberation_for_title_lead_alias_resolved(
        self,
        evidence: Dict[str, Any],
        primary: Dict[str, Any],
        ctx: "ConversationContext",
    ) -> bool:
        """Skip expensive Jury/Debate when a title-leading alias already bridges to one work.

        This is deliberately narrower than general conflict suppression. It only
        handles cases where the sole conflict is Decoder=None versus Verifier
        relevant, while the post title's leading alias is directly bridged by
        search evidence to the same work title chosen by Arbiter/Verifier.
        """
        if str(getattr(ctx, "search_budget_profile", "") or "") == "memory_query_lookup":
            return False
        if getattr(ctx, "original_gatekeeper_noise", False):
            return False

        primary_decision = primary.get("final_decision") or {}
        if primary_decision.get("is_relevant") is not True:
            return False
        title = (
            primary_decision.get("official_novel_title")
            or primary_decision.get("official_title")
        )
        title = str(title or "").strip()
        if not title:
            return False

        from .orchestrator import ExpertType

        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        verifier_result = verifier_out.get("verification_result") or {}
        if verifier_result.get("is_relevant") is not True:
            return False
        novel_identity = verifier_result.get("novel_identity") or {}
        verifier_title = (
            novel_identity.get("official_novel_title")
            or novel_identity.get("official_title")
        )
        if verifier_title and self._compact_match_text(verifier_title) != self._compact_match_text(title):
            return False
        verifier_conf = str(
            novel_identity.get("confidence")
            or verifier_result.get("final_confidence")
            or verifier_result.get("confidence")
            or ""
        ).strip().lower()
        if verifier_conf in {"none", "low"}:
            return False

        counters = verifier_result.get("counter_arguments") or []
        if any(
            isinstance(counter, dict)
            and str(counter.get("severity") or "").strip().lower() == "critical"
            for counter in counters
        ):
            return False

        conflict_details = [str(item or "") for item in (evidence.get("conflict_details") or [])]
        allowed_conflicts = {"Decoder=None but Verifier=relevant"}
        if conflict_details and not all(item in allowed_conflicts for item in conflict_details):
            return False

        try:
            score = float(evidence.get("total_score", 0) or 0)
        except Exception:
            score = 0.0
        if score < 2:
            return False

        disc = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
        disc_analysis = disc.get("discourse_analysis") or {}
        domain = str(disc_analysis.get("primary_domain") or getattr(ctx, "primary_domain", "") or "").lower()
        intent = str(disc_analysis.get("intent") or getattr(ctx, "discourse_intent", "") or "").lower()
        target_kind = str(disc_analysis.get("target_kind") or "").lower()
        if "novel" not in domain and "fiction" not in domain:
            return False
        if intent in {"request_recommendation", "ask_recommendation"}:
            return False
        if target_kind in {"author", "trope", "genre"}:
            return False

        aliases = self._title_lead_alias_terms(ctx, title)
        if not aliases:
            return False
        strong_title_field_bridge = self._search_results_support_title_lead_alias(
            ctx,
            title=title,
            aliases=aliases,
            require_title_field=True,
        )
        if score < 3 and not strong_title_field_bridge:
            return False
        return self._search_results_support_title_lead_alias(ctx, title=title, aliases=aliases)

    def _should_skip_deliberation_for_settled_veto(
        self,
        evidence: Dict[str, Any],
        primary: Dict[str, Any],
        ctx: "ConversationContext",
    ) -> bool:
        """이미 충분히 거부된 low-evidence memory/search-only 케이스는 추가 LLM 심의를 생략한다."""
        from .orchestrator import ExpertType

        final_decision = primary.get("final_decision") or {}
        if final_decision.get("is_relevant") is not False:
            return False
        if final_decision.get("official_novel_title") or final_decision.get("official_title"):
            return False
        if not final_decision.get("_title_deliberately_null"):
            return False

        try:
            score = float(evidence.get("total_score", 0) or 0)
        except Exception:
            score = 0.0
        if score > 0:
            return False

        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        verifier_result = verifier_out.get("verification_result") or {}
        if verifier_result.get("is_relevant") is not False:
            return False

        grounding = verifier_result.get("grounding_check") or {}
        anchor = str(grounding.get("anchor_found") or "").strip().lower()
        counters = verifier_result.get("counter_arguments") or []
        has_critical_counter = any(
            isinstance(counter, dict)
            and str(counter.get("severity") or "").strip().lower() == "critical"
            for counter in counters
        )
        has_search_only_rejection = anchor in {"", "none", "search_only"}
        if not (has_critical_counter or has_search_only_rejection):
            return False

        # 직접 원문 제목 앵커가 있는 high suspected title은 비싼 심의를 유지한다.
        for item in getattr(ctx, "suspected_titles", []) or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            conf = item.get("confidence")
            try:
                high_numeric = float(conf) >= 0.7
            except Exception:
                high_numeric = False
            high_text = str(conf or "").strip().lower() in {"high", "max", "very_high", "very high"}
            if title and (high_numeric or high_text) and self._title_mentioned_in_post_main_context(ctx, title):
                return False

        conflict_details = " | ".join(str(x) for x in (evidence.get("conflict_details") or []))
        if "Verifier critical counter" in conflict_details or has_critical_counter:
            return True
        return has_search_only_rejection and evidence.get("relevance_probability") in {"very_low", "low"}

    def _should_skip_deliberation_for_memory_query_unresolved(
        self,
        primary: Dict[str, Any],
        ctx: "ConversationContext",
    ) -> bool:
        """Skip expensive Jury/Debate when a memory-query has already settled to null-title."""
        from .orchestrator import ExpertType

        if str(getattr(ctx, "search_budget_profile", "") or "").strip().lower() != "memory_query_lookup":
            return False

        final_decision = primary.get("final_decision") or {}
        if final_decision.get("is_relevant") is not False:
            return False
        if final_decision.get("official_novel_title") or final_decision.get("official_title"):
            return False
        if not final_decision.get("_title_deliberately_null"):
            return False

        verifier_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        verifier_result = verifier_out.get("verification_result") or {}
        if not isinstance(verifier_result, dict):
            return False

        novel_identity = verifier_result.get("novel_identity")
        verifier_title = None
        if isinstance(novel_identity, dict):
            verifier_title = (
                novel_identity.get("official_novel_title")
                or novel_identity.get("official_title")
                or novel_identity.get("title")
                or novel_identity.get("resolved_title")
            )
        verifier_title = verifier_title or verifier_result.get("official_novel_title") or verifier_result.get("official_title")

        grounding = verifier_result.get("grounding_check") or {}
        if not isinstance(grounding, dict):
            grounding = {}
        anchor = str(grounding.get("anchor_found") or "").strip().lower()
        if anchor in {
            "quote_source",
            "direct_quote_source",
            "official_url",
            "post_official_url",
            "character_work_link",
            "character_title_link",
            "direct_title",
        }:
            return False

        relation = verifier_result.get("relation_judgment") or {}
        if not isinstance(relation, dict):
            relation = {}
        promotion = str(relation.get("promotion_decision") or "").strip().lower()
        target = str(relation.get("discussion_target") or "").strip().lower()
        post_direct_grounding = bool(relation.get("post_direct_grounding"))
        bridge_quality = ""
        support_summary = relation.get("search_support_summary") or {}
        if isinstance(support_summary, dict):
            bridge_quality = str(support_summary.get("bridge_quality") or "").strip().lower()
        else:
            support_summary = {}
        explicit_bridge_count = int(support_summary.get("explicit_alias_bridge_count") or 0)
        closed_bridge = bool(support_summary.get("closed_bridge"))
        converged_official_signal = bool(support_summary.get("converged_official_signal"))

        counters = verifier_result.get("counter_arguments") or []
        has_nullifying_counter = any(
            isinstance(counter, dict)
            and str(counter.get("severity") or "").strip().lower() in {"critical", "major"}
            and str(counter.get("action") or "").strip().lower()
            in {"reject", "nullify_title", "downgrade_confidence"}
            for counter in counters
        )
        title_confidence = ""
        if isinstance(novel_identity, dict):
            title_confidence = str(novel_identity.get("confidence") or "").strip().lower()
        if not title_confidence:
            title_confidence = str(
                verifier_result.get("confidence")
                or verifier_out.get("final_confidence")
                or ""
            ).strip().lower()
        confidence_rank = {"none": 0, "low": 1, "medium": 2, "high": 3, "max": 4}.get(
            title_confidence,
            0,
        )
        relation_reason = str(
            relation.get("reason")
            or verifier_result.get("relation_hold_reason")
            or verifier_result.get("reason")
            or verifier_out.get("reason")
            or ""
        )
        weak_bridge_for_titled_memory_query = bool(
            not post_direct_grounding
            and not explicit_bridge_count
            and not closed_bridge
            and not converged_official_signal
            and (
                bridge_quality in {"", "weak", "thematic_overlap_only", "supporting"}
                or str(relation.get("relation_type") or "").strip().lower() in {
                    "",
                    "thematic_overlap_only",
                    "work_specific_nickname",
                    "mixed_or_uncertain",
                }
                or bool(
                    re.search(
                        r"(직접|명시|bridge|브릿지|브리지|검증|확정).{0,24}(부족|불충분|불가|없)",
                        relation_reason,
                    )
                )
            )
        )
        weak_titled_memory_query = bool(
            verifier_title
            and weak_bridge_for_titled_memory_query
            and confidence_rank <= 2
            and (
                verifier_result.get("is_relevant") is False
                or promotion in {"hold", "reject", "nullify", "nullify_title"}
                or has_nullifying_counter
            )
        )
        if verifier_title and not weak_titled_memory_query:
            return False

        if target == "memory_query" or has_nullifying_counter:
            return True
        return bool(
            promotion in {"hold", "reject", "nullify", "nullify_title"}
            and not post_direct_grounding
            and (
                anchor in {"", "none", "search_only", "title_mention"}
                or bridge_quality in {"", "weak", "thematic_overlap_only"}
            )
            or weak_titled_memory_query
        )

    def _should_skip_deliberation_for_clear_non_novel(
        self,
        primary: Dict[str, Any],
        ctx: "ConversationContext",
    ) -> bool:
        """
        이미 '비관련/메타'로 충분히 정리된 케이스는 Jury/Debate를 생략한다.

        예:
        - 네이버 시리즈 광고/다운로드 불만
        - 제목-본문 불일치 일상 뻘글
        """
        from .orchestrator import ExpertType

        final_decision = primary.get("final_decision") or {}
        if final_decision.get("is_relevant") is not False:
            return False
        if final_decision.get("official_novel_title") or final_decision.get("official_title"):
            return False

        gk = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        dc = ctx.get_expert_output(ExpertType.DECODER) or {}
        vf = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vr = vf.get("verification_result") or {}

        vf_irrelevant = vr.get("is_relevant") is False
        if not vf_irrelevant:
            return False

        gk_type = str(gk.get("post_type", "")).lower()
        disc_type = str(final_decision.get("discussion_type", "")).lower()
        rejection_reason = str(vr.get("rejection_reason", "") or "")
        inference = vr.get("inference") or {}
        inference_type = str(inference.get("type", "")).lower()
        reasoning = str(primary.get("final_reasoning", "") or "")
        decoder_notes = str(dc.get("notes", "") or "").lower()
        author_info = vr.get("author_info") or {}
        strong_author_meta_rejection = bool(
            vf_irrelevant
            and (
                bool(author_info.get("is_author_criticism"))
                or gk_type in {"author_criticism", "author_discussion"}
                or disc_type in {"author_talk"}
                or inference_type in {"author_criticism", "author_talk", "author_discussion"}
            )
        )
        if strong_author_meta_rejection:
            return True

        dc_title = None
        dc_best = dc.get("overall_best_match") or {}
        if isinstance(dc_best, dict):
            dc_title = dc_best.get("title")
        if not dc_title:
            for term in (dc.get("decoded_terms") or []):
                if not isinstance(term, dict):
                    continue
                best = term.get("best_match") or {}
                if isinstance(best, dict) and best.get("title"):
                    dc_title = best.get("title")
                    break
        if dc_title:
            return False

        suspected = getattr(ctx, "suspected_titles", None) or []
        if suspected:
            return False

        meta_markers = (
            "platform",
            "플랫폼",
            "meta",
            "메타",
            "다운로드",
            "광고",
            "기능",
            "오류",
            "association",
            "뻘글",
            "일상",
            "daily life",
        )
        meta_signal_count = 0
        if gk_type in ("meta_platform", "platform_meta", "noise", "daily_life", "community_banter", "off_topic"):
            meta_signal_count += 1
        if disc_type in ("meta", "platform_meta", "daily_life", "association", "noise", "community_banter", "off_topic"):
            meta_signal_count += 1
        if inference_type in ("platform_meta_talk", "meta_platform", "association_post", "daily_life", "community_banter", "off_topic", "noise"):
            meta_signal_count += 1
        if any(marker in rejection_reason for marker in meta_markers):
            meta_signal_count += 1
        if any(marker in reasoning for marker in meta_markers):
            meta_signal_count += 1

        if (
            disc_type in {"noise", "community_banter", "off_topic", "meta"}
            and (
                gk_type in {"community_banter", "noise", "off_topic", "daily_life"}
                or inference_type in {"community_banter", "noise", "off_topic", "daily_life", "association_post"}
            )
        ):
            return True
        if inference_type in {"genre_opinion", "trope_discussion", "genre_discussion"}:
            return True
        generic_term_markers = (
            "장르 용어",
            "장르용어",
            "일반 용어",
            "일반적 표현",
            "genre term",
            "generic term",
            "specific work title",
            "특정 작품 제목",
        )
        if any(marker in rejection_reason for marker in generic_term_markers):
            return True
        if any(marker in decoder_notes for marker in ("장르 클리셰", "장르 용어", "특정 작품 제목이나 작가명, 플랫폼 url 등 고유 정보 없음")):
            return True

        return meta_signal_count >= 2

    def _call_arbiter_with_evidence(
        self, ctx: "ConversationContext", evidence_text: str
    ) -> Dict[str, Any]:
        """EvidenceScorer 결과를 주입한 Arbiter 호출."""
        # Arbiter의 analyze()를 살짝 변형 — evidence_text를 user_prompt 끝에 추가
        # 실제로는 Arbiter.analyze()를 직접 호출하되, _inject_evidence 플래그로 주입
        ctx._deliberation_evidence_text = evidence_text  # type: ignore
        result = self.arbiter.analyze(ctx)
        return result

    def _rebuild_arbiter_user_prompt(self, ctx: "ConversationContext", evidence_text: str) -> str:
        """Jury Panel용 Arbiter user_prompt 재구성."""
        from .orchestrator import ExpertType
        from .arbiter import ARBITER_PROMPT

        gk = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        dc = ctx.get_expert_output(ExpertType.DECODER) or {}
        vf = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vr = vf.get("verification_result") or {}
        cr = ctx.get_expert_output(ExpertType.CRITIC) or {}

        post_data = ctx.post_data or {}
        content_blocks = post_data.get("content_blocks", [])
        body_preview = " / ".join(
            str(b.get("text") if isinstance(b, dict) else b)
            for b in content_blocks[:4]
        )[:400]
        comments = ctx.comments or []

        gk_verdict = f"noise={gk.get('is_noise')}, type={gk.get('post_type')}, conf={gk.get('confidence')}"

        dc_title = None
        dc_best = dc.get("overall_best_match") or {}
        if isinstance(dc_best, dict):
            dc_title = dc_best.get("title")
        dc_verdict = f"title={dc_title}, conf={dc.get('overall_confidence')}"

        vf_verdict = (
            f"relevant={vr.get('is_relevant')}, "
            f"title={(vr.get('novel_identity') or {}).get('official_novel_title')}, "
            f"conf={vr.get('final_confidence') or vr.get('confidence')}"
        )
        verifier_veto = ""
        if vr.get("is_relevant") is False:
            verifier_veto = " 🚨 [VETO: 거부권 발동]"

        # [Phase28] Critic 통합 — cr_verdict 제거

        suspected_titles_str = "None"
        suspected = getattr(ctx, 'suspected_titles', []) or []
        if suspected:
            items = []
            for st in suspected[:3]:
                items.append(f"- {st.get('title')} (conf={st.get('confidence')})")
            suspected_titles_str = "\n".join(items)

        # 댓글 미리보기 생성 (Arbiter 프롬프트에 필요)
        _max_comment_preview = 7
        _comment_texts = []
        for c in comments[:_max_comment_preview]:
            if isinstance(c, str) and c.strip():
                _ct = c.strip()
                if len(_ct) > 80:
                    _ct = _ct[:80] + "..."
                _comment_texts.append(_ct)
            elif isinstance(c, dict):
                _ct = str(c.get('text') or c.get('content') or '').strip()
                if _ct:
                    if len(_ct) > 80:
                        _ct = _ct[:80] + "..."
                    _comment_texts.append(_ct)
        _comment_preview = "\n".join(f"  - {ct}" for ct in _comment_texts) if _comment_texts else "(댓글 없음)"

        user_prompt = ARBITER_PROMPT.format(
            post_id=ctx.post_id,
            title=post_data.get("title", ""),
            body_preview=body_preview,
            comment_count=len(comments),
            comment_preview=_comment_preview,
            gk_verdict=gk_verdict,
            dc_verdict=dc_verdict,
            vf_verdict=vf_verdict,
            verifier_veto=verifier_veto,
            key_evidence="(see evidence scorer below)",
            suspected_titles=suspected_titles_str,
        )

        # Curated alias hint for Jury. Keep it weaker than direct evidence.
        user_prompt += EvidenceScorer.build_curated_alias_prompt_note(
            ctx,
            gk=gk,
            disc=disc,
            post_data=post_data,
        )

        user_prompt += evidence_text
        return user_prompt

    def _build_post_summary(self, post_data: Dict, comments: List) -> str:
        """게시글 요약 구성."""
        title = post_data.get("title", "")
        blocks = post_data.get("content_blocks", [])
        body = " / ".join(
            str(b.get("text") if isinstance(b, dict) else b)
            for b in blocks[:3]
        )[:300]
        return (
            f"제목: {title}\n"
            f"본문: {body}\n"
            f"댓글 수: {len(comments)}"
        )

    def _build_expert_summary(self, ctx: "ConversationContext") -> str:
        """전문가 판정 요약."""
        from .orchestrator import ExpertType

        lines = []
        gk = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
        lines.append(f"Gatekeeper: noise={gk.get('is_noise')}, type={gk.get('post_type')}")

        dc = ctx.get_expert_output(ExpertType.DECODER) or {}
        dc_title = (dc.get("overall_best_match") or {}).get("title")
        lines.append(f"Decoder: title={dc_title}, conf={dc.get('overall_confidence')}")

        vf = ctx.get_expert_output(ExpertType.VERIFIER) or {}
        vr = vf.get("verification_result") or {}
        vf_title = (vr.get("novel_identity") or {}).get("official_novel_title")
        lines.append(f"Verifier: relevant={vr.get('is_relevant')}, title={vf_title}")

        disc = ctx.get_expert_output(ExpertType.DISCOURSE) or {}
        lines.append(f"Discourse: domain={ctx.primary_domain}, intent={ctx.discourse_intent}")

        return "\n".join(lines)

    def _synthesize_deliberation(
        self,
        primary: Dict[str, Any],
        jury: Dict[str, Any],
        debate: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        기본 Arbiter + Jury Panel + Debate 결과를 합성.
        
        가중 투표 (🆕 Smart Deliberation):
          - Primary Arbiter: 2표 (후처리 가드 뒤집힌 경우 LLM 원본 판정으로 투표)
          - Jury 다수결: 3표 (각 juror 1표)
          - Debate Judge: 2표
          - EvidenceScorer: 차등 보정 (≥10→+2, ≥5→+1, ≤-3→+2, ≤-1→+1)
        """
        print(f"[{_ts()}][⚖️🔮] 최종 합성 시작", file=sys.stderr)

        votes_for = 0  # 관련성 지지
        votes_against = 0  # 비관련성 지지
        title_votes: Dict[str, int] = {}
        all_reasonings: List[str] = []
        _blocked_title_vote_logged: set[str] = set()

        _ctx_ref = getattr(self, "_last_ctx", None)
        try:
            from .orchestrator import ExpertType as _RuntimeExpertType
        except Exception:
            _RuntimeExpertType = None  # type: ignore[assignment]
        _vf_out_final = (
            _ctx_ref.get_expert_output(_RuntimeExpertType.VERIFIER)
            if (_ctx_ref and _RuntimeExpertType is not None)
            else {}
        )
        _vf_out_final = _vf_out_final or {}
        _vf_res_final = (_vf_out_final.get("verification_result") or {}) if isinstance(_vf_out_final, dict) else {}
        _vf_relation_final = (_vf_res_final.get("relation_judgment") or {}) if isinstance(_vf_res_final, dict) else {}
        _vf_relation_type_final = str(_vf_relation_final.get("relation_type") or "").strip().lower()
        _vf_relation_target_final = str(_vf_relation_final.get("discussion_target") or "").strip().lower()
        _vf_relation_promotion_final = str(_vf_relation_final.get("promotion_decision") or "").strip().lower()
        if _vf_relation_promotion_final in {"promote", "accept", "keep"}:
            _vf_relation_promotion_final = "allow"
        elif _vf_relation_promotion_final in {"defer", "pending"}:
            _vf_relation_promotion_final = "hold"
        _vf_relation_summary = (
            _vf_relation_final.get("evidence_summary") if isinstance(_vf_relation_final.get("evidence_summary"), dict) else {}
        )
        _vf_explicit_bridge_count = int((_vf_relation_summary or {}).get("explicit_alias_bridge_count") or 0)
        _vf_official_detail_count = int((_vf_relation_summary or {}).get("official_detail_count") or 0)
        _vf_post_direct_grounding = bool(_vf_relation_final.get("post_direct_grounding"))
        _block_title_votes_on_hold = bool(
            _vf_relation_promotion_final in {"hold", "reject"}
            and _vf_res_final.get("is_relevant") is False
            and _vf_relation_type_final in {"thematic_overlap_only", "community_slang_or_meta", "unknown"}
            and _vf_relation_target_final in {"mixed_or_uncertain", "community_banter", "platform_meta", ""}
            and _vf_explicit_bridge_count <= 0
            and _vf_official_detail_count <= 0
            and not _vf_post_direct_grounding
        )

        def _can_cast_title_vote(_candidate_title: Any, source: str) -> bool:
            _cand = str(_candidate_title or "").strip()
            if not _cand:
                return False
            if not _block_title_votes_on_hold:
                return True
            if _cand not in _blocked_title_vote_logged:
                print(
                    f"[{_ts()}][⚖️🔮] 심의 title vote 차단: "
                    f"source={source}, relation={_vf_relation_type_final}/{_vf_relation_promotion_final}, "
                    f"target={_vf_relation_target_final}, title='{_cand}'",
                    file=sys.stderr,
                )
                _blocked_title_vote_logged.add(_cand)
            return False

        # ── Primary Arbiter (2표) ──
        # 🆕 Smart Deliberation: 후처리 가드가 LLM 원본 판정을 뒤집은 경우,
        # LLM 원본 판단을 primary 투표에 반영 (밈 가드/multi_work 가드 등이
        # 올바른 LLM 판정을 무력화하는 문제 해결)
        p_dec = primary.get("final_decision", {})
        _raw_llm_relevant = p_dec.get("_raw_llm_relevant")
        _raw_llm_title = p_dec.get("_raw_llm_title")
        _raw_llm_confidence = p_dec.get("_raw_llm_confidence")
        p_rel = p_dec.get("is_relevant")

        # 후처리로 뒤집어진 경우: LLM 원본 판단 사용
        _primary_used_raw = False
        if _raw_llm_relevant is not None and _raw_llm_relevant != p_rel:
            _primary_used_raw = True
            print(
                f"[{_ts()}][⚖️🔮] ⚡ Primary: 후처리 가드가 LLM 판정을 뒤집음 "
                f"(raw={_raw_llm_relevant} → post={p_rel}) → LLM 원본으로 투표",
                file=sys.stderr,
            )
            if _raw_llm_relevant is True:
                votes_for += 2
            else:
                votes_against += 2
            if _raw_llm_title and _can_cast_title_vote(_raw_llm_title, "primary_raw"):
                title_votes[_raw_llm_title] = title_votes.get(_raw_llm_title, 0) + 2
        else:
            if p_rel is True:
                votes_for += 2
            else:
                votes_against += 2
            p_title = p_dec.get("official_novel_title") or p_dec.get("official_title")
            if p_title and _can_cast_title_vote(p_title, "primary"):
                title_votes[p_title] = title_votes.get(p_title, 0) + 2
        if primary.get("final_reasoning"):
            all_reasonings.append(f"[Primary] {str(primary['final_reasoning'])}")

        # ── Jury Panel (3표) ──
        if not jury.get("jury_failed"):
            jury_votes = jury.get("jury_votes", {})
            votes_for += jury_votes.get("relevant", 0)
            votes_against += jury_votes.get("irrelevant", 0)
            for t, cnt in jury.get("jury_titles", {}).items():
                if _can_cast_title_vote(t, "jury"):
                    title_votes[t] = title_votes.get(t, 0) + cnt
            for reason in jury.get("dissent_reasons", []):
                all_reasonings.append(f"[Jury dissent] {reason}")

            # Jury majority decision의 reasoning
            jury_maj = jury.get("majority_decision", {})
            if jury_maj.get("final_reasoning"):
                all_reasonings.append(f"[Jury majority] {str(jury_maj['final_reasoning'])}")

        # ── Debate Judge (2표) ──
        if not debate.get("debate_failed"):
            judge = debate.get("judge", {})
            j_dec = judge.get("final_decision", {})
            j_rel = j_dec.get("is_relevant")
            if j_rel is True:
                votes_for += 2
            else:
                votes_against += 2
            j_title = j_dec.get("official_novel_title")
            if j_title and _can_cast_title_vote(j_title, "debate_judge"):
                title_votes[j_title] = title_votes.get(j_title, 0) + 2
            if judge.get("judge_reasoning"):
                all_reasonings.append(f"[Judge] {str(judge['judge_reasoning'])}")

        # ── EvidenceScorer 보정 (🆕 구간별 차등 투표) ──
        # 기존: ±1표 (score ≥7 또는 ≤-1)만 반영 → 너무 약함
        # 개선: 점수 구간별 차등 투표로 반영
        ev_score = evidence.get("total_score", 0)
        if ev_score >= 10:
            votes_for += 2
            print(f"[{_ts()}][⚖️🔮] EvidenceScorer 관련 강보정 +2 (score={ev_score})", file=sys.stderr)
        elif ev_score >= 5:
            votes_for += 1
            print(f"[{_ts()}][⚖️🔮] EvidenceScorer 관련 보정 +1 (score={ev_score})", file=sys.stderr)
        elif ev_score <= -3:
            votes_against += 2
            print(f"[{_ts()}][⚖️🔮] EvidenceScorer 비관련 강보정 +2 (score={ev_score})", file=sys.stderr)
        elif ev_score <= -1:
            votes_against += 1
            print(f"[{_ts()}][⚖️🔮] EvidenceScorer 비관련 보정 +1 (score={ev_score})", file=sys.stderr)

        # ── 최종 결정 ──
        total_votes = votes_for + votes_against
        is_relevant = votes_for > votes_against

        print(
            f"[{_ts()}][⚖️🔮] 투표 결과: 관련={votes_for}, 비관련={votes_against} "
            f"→ {'관련' if is_relevant else '비관련'}",
            file=sys.stderr,
        )

        # 최종 제목: 가장 많이 투표된 제목
        best_title = None
        if title_votes and is_relevant:
            best_title = max(title_votes, key=title_votes.get)

        jury_votes = jury.get("jury_votes", {}) if isinstance(jury, dict) else {}
        jury_relevant = int(jury_votes.get("relevant", 0) or 0)
        jury_irrelevant = int(jury_votes.get("irrelevant", 0) or 0)
        _jury_unanimous_irrelevant = jury_irrelevant >= 3 and jury_relevant == 0
        _suppress_title_on_hold = bool(
            best_title
            and is_relevant
            and _jury_unanimous_irrelevant
            and _vf_res_final.get("is_relevant") is False
            and _vf_relation_promotion_final == "hold"
            and _vf_relation_type_final in {"thematic_overlap_only", "community_slang_or_meta", "unknown"}
            and _vf_relation_target_final in {"mixed_or_uncertain", "community_banter", "platform_meta", ""}
        )
        if _suppress_title_on_hold:
            print(
                f"[{_ts()}][⚖️🔮] 심의 title 확정 억제: "
                f"jury=0:3 비관련 + relation={_vf_relation_type_final}/{_vf_relation_promotion_final} "
                f"→ title='{best_title}' 보류",
                file=sys.stderr,
            )
            best_title = None

        # confidence 결정 (투표 비율 기반)
        if total_votes > 0:
            ratio = max(votes_for, votes_against) / total_votes
        else:
            ratio = 0.5

        if ratio >= 0.85:
            confidence = "High"
        elif ratio >= 0.7:
            confidence = "Medium"
        else:
            confidence = "Low"

        # 기본 결과에서 다른 필드 복사
        final = copy.deepcopy(primary)
        final_dec = final.get("final_decision", {})
        final_dec["is_relevant"] = is_relevant
        final_dec["official_novel_title"] = best_title
        final_dec["official_title"] = best_title
        final_dec["confidence"] = confidence

        # 🛡️ Fix E-3: 심의 결과 관련+제목 확정 시 _title_deliberately_null 해제
        # primary에서 복사된 null 플래그가 심의 결과를 override하는 문제 방지
        # 🛡️ Fix E-3b: 근소 차이(margin ≤ 2)에서는 해제하지 않음
        # 🛡️ Fix E-3c(Phase40): Verifier Low conf이면 더 높은 margin 필요
        #   - Verifier Low conf: margin > 5 필요 (사실상 만장일치에 가까워야)
        #   - Verifier Medium/High conf: margin > 2 (기존 유지)
        #   - best_title이 소설 플랫폼에서 확인 불가 시: margin > 5 필요
        _vote_margin = votes_for - votes_against
        if is_relevant and best_title and final_dec.get("_title_deliberately_null"):
            # Verifier confidence 확인
            _vf_conf_for_margin = "low"
            _title_on_platform = False
            _ctx_ref = getattr(self, '_last_ctx', None)
            try:
                if _ctx_ref and _RuntimeExpertType is not None:
                    _vf_out_m = _ctx_ref.get_expert_output(_RuntimeExpertType.VERIFIER) or {}
                    _vf_r_m = _vf_out_m.get('verification_result') or {}
                    _vf_ni_m = _vf_r_m.get('novel_identity') or {}
                    _vf_conf_for_margin = str(_vf_ni_m.get('confidence', 'low')).lower()
                    # 소설 플랫폼 URL 존재 여부 확인
                    _h_url = _vf_ni_m.get('heretic_url', '')
                    if _h_url and any(p in str(_h_url) for p in (
                        'novelpia.com', 'munpia.com', 'series.naver.com',
                        'page.kakao.com', 'joara.com', 'ridibooks.com',
                    )):
                        _title_on_platform = True
            except Exception:
                pass

            _preserve_null, _preserve_reason = self._should_preserve_deliberate_null(
                _ctx_ref,
                final_dec,
                best_title,
                _vf_r_m if '_vf_r_m' in locals() else {},
                jury.get("jury_votes") if isinstance(jury, dict) else None,
            )

            # margin 기준 결정
            if _title_on_platform:
                _required_margin = 2  # 플랫폼 확인된 제목 → 기존 기준
            elif _vf_conf_for_margin == 'low':
                _required_margin = 5  # Low conf → 사실상 만장일치
            else:
                _required_margin = 3  # Medium/High conf + 비플랫폼 → 약간 높임

            if _preserve_null:
                final_dec["official_novel_title"] = None
                final_dec["official_title"] = None
                if str(final_dec.get("confidence") or "").lower() in {"high", "medium", "max"}:
                    final_dec["confidence"] = "Low"
                print(
                    f"[{_ts()}][⚖️🔮] 심의 _title_deliberately_null 유지 "
                    f"(author-new-work 보호): title='{best_title}' 차단, {_preserve_reason}",
                    file=sys.stderr,
                )
            elif _vote_margin > _required_margin:
                final_dec["_title_deliberately_null"] = False
                final_dec["official_title"] = best_title
                print(
                    f"[{_ts()}][⚖️🔮] 심의 결과 _title_deliberately_null 해제: "
                    f"투표={votes_for}/{votes_against} (margin={_vote_margin}>{_required_margin}), "
                    f"title='{best_title}', vf_conf={_vf_conf_for_margin}, platform={_title_on_platform}",
                    file=sys.stderr,
                )
            else:
                print(
                    f"[{_ts()}][⚖️🔮] 심의 _title_deliberately_null 유지 "
                    f"(margin={_vote_margin} ≤ {_required_margin}): "
                    f"투표={votes_for}/{votes_against}, title='{best_title}' 차단, "
                    f"vf_conf={_vf_conf_for_margin}, platform={_title_on_platform}",
                    file=sys.stderr,
                )

        # discussion_type 결정
        if not is_relevant and final_dec.get("discussion_type") in (
            "review", "spoiler", "anticipation", "meme", "character_talk", "general"
        ):
            # relevant 전용 타입이었는데 비관련으로 바뀜 → noise로 변경
            final_dec["discussion_type"] = "noise"
        elif is_relevant and final_dec.get("discussion_type") in (
            "noise", "meta", "recommendation", "community_banter", "off_topic"
        ):
            # 비관련 전용 타입이었는데 관련으로 바뀜 → general로 변경
            final_dec["discussion_type"] = "general"

        final["final_decision"] = final_dec

        # 합성된 reasoning
        combined_reasoning = (
            f"[Multi-Expert Deliberation] "
            f"투표: 관련={votes_for}/비관련={votes_against}, "
            f"증거점수={ev_score}, "
            f"최종={'관련' if is_relevant else '비관련'}(confidence={confidence}).\n"
        )
        if all_reasonings:
            combined_reasoning += "\n".join(all_reasonings[:5])

        final["final_reasoning"] = combined_reasoning

        return final
