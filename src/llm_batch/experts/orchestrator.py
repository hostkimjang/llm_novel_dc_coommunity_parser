"""
Orchestrator - 전문가 간 협력적 워크플로우 시스템
전문가들의 요청을 해석하고, 필요한 전문가를 실행하며, 결과를 조율합니다.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from ..rules import OFFICIAL_PLATFORMS
from .decoder import KNOWN_ABBREVIATIONS

# 이벤모니(lazy import, 없으면 무시)
import threading as _orch_threading
_orch_thread_local = _orch_threading.local()

def _emit_monitor(event_type: str, data: dict = None, post_id: int = None):
    try:
        from ..monitor.event_bus import monitor
        d = dict(data or {})
        # 병렬 모드에서 post_id 인수 포함 (다중 포스트추적
        if post_id is not None:
            d["post_id"] = post_id
        monitor.emit(event_type, d)
    except Exception:
        pass

# 한국어 형태소 분석기 (lazy loading)
_kiwi_instance = None

def _get_kiwi():
    """Kiwi 형태소 분석기 인스턴스(lazy loading)"""
    global _kiwi_instance
    if _kiwi_instance is None:
        try:
            from kiwipiepy import Kiwi
            _kiwi_instance = Kiwi()
        except ImportError:
            print("[warn] kiwipiepy not installed, using fallback", file=sys.stderr)
            _kiwi_instance = False  # 설치 안됨 표시
    return _kiwi_instance if _kiwi_instance else None


def _extract_nouns(text: str) -> List[str]:
    """
    한국어텍스트에서 명사만 추출 (kiwipiepy 사용)
    
    추출하는 품사:
    - NNG: 일반 명사 (소설 게임, 작품)
    - NNP: 고유 명사 (죽깨, 스마트, 이유반)
    - NNB: 의존 명사 (것 등) - 제외
    - NR: 수사 - 제외
    - SL: 외국어(Genshin, Impact) - 포함
    """
    kiwi = _get_kiwi()
    if not kiwi:
        # Fallback: 공백 기준 분리 후 2글자 이상만
        return [w for w in text.split() if len(w) >= 2]
    
    nouns = []
    try:
        result = kiwi.tokenize(text)
        for token in result:
            tag = token.tag
            form = token.form
            # 일반명사(NNG), 고유명사(NNP), 외국SL) 만추출
            # 2글자 이상만(너무 짧은 건 제외)
            if tag in ("NNG", "NNP", "SL") and len(form) >= 2:
                nouns.append(form)
    except Exception:
        # 에러 시 fallback
        return [w for w in text.split() if len(w) >= 2]
    
    return nouns


def _ts() -> str:
    wid = getattr(_orch_thread_local, 'worker_id', None)
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    if wid is not None and getattr(_orch_thread_local, 'parallel', 1) > 1:
        return f"{ts}|W{wid}"
    return ts


class ExpertType(Enum):
    GATEKEEPER = "gatekeeper"
    DISCOURSE = "discourse"  # NEW: 담론 분석가 - domain/intent analyzer
    DECODER = "decoder"
    VERIFIER = "verifier"
    CRITIC = "critic"
    SYNTHESIZER = "synthesizer"  # NEW: 증거 기반 재해석기
    ARBITER = "arbiter"


@dataclass
class ExpertMessage:
    """전문가 간 메시지"""
    from_expert: ExpertType
    to_expert: Optional[ExpertType]  # None이면 다음 스테이지에게
    message_type: str  # "analysis", "request", "question", "answer", "final"
    content: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_expert.value,
            "to": self.to_expert.value if self.to_expert else "orchestrator",
            "type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class ConversationContext:
    """전문가 컨텍스트"""
    post_id: int
    post_data: Dict[str, Any]
    comments: List[str]
    search_results: List[Dict[str, Any]] = field(default_factory=list)
    messages: List[ExpertMessage] = field(default_factory=list)
    expert_outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 12
    
    # NEW: 추정/후보 작품 목록 (Decoder 이상의 전문가가 각자 공유)
    suspected_titles: List[Dict[str, Any]] = field(default_factory=list)
    
    # 단계 1: DiscourseAnalyzer 결과 저장 (도메인 교차 검증용)
    primary_domain: Optional[str] = None  # "novel_work", "real_world", "meta", etc.
    discourse_intent: Optional[str] = None  # "discussion", "recommendation", "meme", etc.
    
    # ⚡ Discourse Override: non-novel 도메인(high) 경고
    discourse_warning: Optional[str] = None  # e.g. "memes_humor(high)"
    
    # ⚡ 연상기호 판정: is_association_not_discussion + title_body_consistency=false
    is_association_post: bool = False
    
    # 단계 2: 전문가별 신뢰도추적 (Arbiter 가중 평가용)
    expert_confidence: Dict[str, float] = field(default_factory=dict)  # {"gatekeeper": 0.6, "verifier": 0.95}
    
    # 단계 4: 불확실성 요인 축적 (카운터 및low-confidence 판정
    uncertainty_sources: List[str] = field(default_factory=list)
    
    # 검색 쿼리 이력 추적 (중복 검색 방지)
    searched_queries: set = field(default_factory=set)
    
    # ── 개선: candidate evidence bucket 분리 (증거 누수 방지) ──
    # 후보 제목별로 증거를 분리 저장하여 후보 A의 증거가 후보 B에 유입되는 것을 방지
    # 구조: {"작품제목": {"post_spans": [...], "search_snippets": [...], "official_urls": [...]}}
    candidate_evidence: Dict[str, Dict[str, List[Any]]] = field(default_factory=dict)
    
    # ── 개선: 가설 상태머신 (hypothesis invalidation) ──
    # 현재 활성 가설과 버전 추적. 새 증거가 충돌하면 invalidate하고 재시작
    active_hypothesis: Optional[Dict[str, Any]] = field(default=None)
    # {"version": 1, "title": "...", "confidence": "high", "supporting_evidence": [...], "created_at_step": 3}
    hypothesis_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # ── 개선: 소스 신뢰도 가중치 ──
    # 검색 결과 소스별 신뢰도 점수 (공식 플랫폼 > 위키 > 커뮤니티/블로그)
    source_trust_scores: Dict[str, float] = field(default_factory=dict)
    
    # 토큰 사용추적
    token_usage: Dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    })
    
    def add_message(self, msg: ExpertMessage) -> None:
        self.messages.append(msg)
    
    def add_evidence_for_candidate(self, candidate_title: str, evidence_type: str, evidence: Any) -> None:
        """
        특정 후보 제목에 대한 증거를 분리 저장.
        
        Args:
            candidate_title: 후보 작품 제목
            evidence_type: 'post_span' | 'search_snippet' | 'official_url'
            evidence: 증거 데이터
        """
        if candidate_title not in self.candidate_evidence:
            self.candidate_evidence[candidate_title] = {
                "post_spans": [],
                "search_snippets": [],
                "official_urls": [],
            }
        bucket = self.candidate_evidence[candidate_title]
        if evidence_type == "post_span":
            bucket["post_spans"].append(evidence)
        elif evidence_type == "search_snippet":
            bucket["search_snippets"].append(evidence)
        elif evidence_type == "official_url":
            bucket["official_urls"].append(evidence)
    
    def get_candidate_evidence(self, candidate_title: str) -> Dict[str, List[Any]]:
        """특정 후보의 증거 bucket 반환."""
        return self.candidate_evidence.get(candidate_title, {
            "post_spans": [], "search_snippets": [], "official_urls": [],
        })
    
    def update_hypothesis(self, title: str, confidence: str, evidence: List[str], step: int) -> bool:
        """
        가설 상태머신: 새 가설을 설정하거나 기존 가설과 충돌 시 무효화.
        
        Returns:
            True: 가설이 유지/갱신됨, False: 기존 가설이 무효화되어 리셋됨
        """
        from .utils import _ts
        new_hyp = {
            "version": (self.active_hypothesis["version"] + 1) if self.active_hypothesis else 1,
            "title": title,
            "confidence": confidence,
            "supporting_evidence": evidence,
            "created_at_step": step,
        }
        
        if self.active_hypothesis is None:
            # 첫 가설 설정
            self.active_hypothesis = new_hyp
            self.hypothesis_history.append(new_hyp)
            print(f"[{_ts()}][🎯] 🧪 가설 v{new_hyp['version']} 수립: '{title}' (conf={confidence})", file=sys.stderr)
            return True
        
        old_title = self.active_hypothesis["title"]
        if old_title and title and old_title.replace(' ', '') != title.replace(' ', ''):
            # 가설 충돌: 다른 작품으로 전환 → 이전 가설 무효화
            old_version = self.active_hypothesis["version"]
            self.active_hypothesis["invalidated"] = True
            self.active_hypothesis["invalidated_by"] = title
            self.active_hypothesis["invalidated_at_step"] = step
            self.hypothesis_history.append(self.active_hypothesis.copy())
            
            # 이전 후보의 증거를 새 후보에 재사용하지 않도록 분리
            print(
                f"[{_ts()}][🎯] ⚠️ 가설 충돌: v{old_version} '{old_title}' → v{new_hyp['version']} '{title}'"
                f" (이전 증거 격리, 새 증거로 재시작)",
                file=sys.stderr,
            )
            self.active_hypothesis = new_hyp
            self.hypothesis_history.append(new_hyp)
            self.uncertainty_sources.append(
                f"가설 전환: '{old_title}' → '{title}' (step {step}, 이전 증거 무효화)"
            )
            return False
        else:
            # 같은 작품 → 가설 강화
            self.active_hypothesis["confidence"] = confidence
            self.active_hypothesis["supporting_evidence"].extend(evidence)
            return True
    
    def score_source_trust(self, url: str) -> float:
        """
        URL 기반 소스 신뢰도 점수 반환.
        공식 플랫폼(1.0) > 위키(0.8) > 커뮤니티/블로그(0.4) > 기타(0.2)
        """
        if not url:
            return 0.2
        url_lower = url.lower()
        # 공식 소설 플랫폼
        official_domains = (
            "novelpia.com", "munpia.com", "page.kakao.com", "kakao.page",
            "joara.com", "series.naver.com", "ridibooks.com",
        )
        for domain in official_domains:
            if domain in url_lower:
                return 1.0
        # 위키 (준공식)
        if "namu.wiki" in url_lower or "wikipedia.org" in url_lower:
            return 0.8
        # 커뮤니티 (신뢰도 중간)
        community_domains = ("dcinside.com", "ruliweb.com", "fmkorea.com", "theqoo.net", "arca.live")
        for domain in community_domains:
            if domain in url_lower:
                return 0.4
        # 블로그 (신뢰도 낮음)
        if "blog.naver.com" in url_lower or "tistory.com" in url_lower:
            return 0.3
        return 0.2
    
    def add_search_results(self, new_results: List[Dict[str, Any]]) -> int:
        """
        검색 결과 추가 (URL 기반 중복 제거 + 자기 참조 방지)
        
        Returns:
            추가된 결과 수
        """
        if not new_results:
            return 0
        
        # 기존 URL 추출
        existing_urls = {r.get("url") for r in self.search_results if r.get("url")}
        
        # 현재 분석 중인 post의 URL 패턴 생성 (자기 참조 방지)
        current_post_id = str(self.post_data.get("post_id", ""))
        current_post_url = str(self.post_data.get("url", ""))
        
        # 카운더 자기 참조 필터 정보 로깅 (처음 번만)
        if not hasattr(self, '_logged_self_ref_filter'):
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{ts}][🎯] 📋 자기참조 필터: post_id='{current_post_id}'", file=sys.stderr)
            self._logged_self_ref_filter = True
        
        # 중복 제거하며 추가
        added_count = 0
        skipped_self_ref = 0
        skipped_duplicate = 0
        
        # DC갤러리 게시판URL에서 게시글 번호 추출 패턴
        import re
        _board_no_re = re.compile(r'[?&]no=(\d+)')
        # 현재 포스트의 게시글 번호 (DC갤 ?no=XXXXX)
        current_board_no = None
        if current_post_url:
            m = _board_no_re.search(current_post_url)
            if m:
                current_board_no = m.group(1)
        
        # 현재 포스트제목 (snippet 기반 자기참조 필터
        current_post_title = str(self.post_data.get("title", ""))
        
        for result in new_results:
            url = str(result.get("url", ""))
            
            # 자기 참조 체크: URL현재 post_id 또는 현재 URL 포함하면 제외
            is_self_ref = False
            if current_post_id and current_post_id in url:
                is_self_ref = True
            elif current_post_url and len(current_post_url) > 10 and current_post_url in url:
                is_self_ref = True
            # DC갤 게시글 번호 비교 (m.dcinside vs gall.dcinside 도메인 차이 처리)
            elif current_board_no and 'dcinside.com' in url:
                m = _board_no_re.search(url)
                if m and m.group(1) == current_board_no:
                    is_self_ref = True
            # snippet 제목에 현재 포스트 제목이 그대로 들어간 경우
            elif current_post_title and len(current_post_title) >= 8:
                sr_title = str(result.get("title", ""))
                if current_post_title in sr_title or sr_title in current_post_title:
                    # dcinside URL이면 거의 뺤떎자기참조
                    if 'dcinside.com' in url:
                        is_self_ref = True
            
            if is_self_ref:
                skipped_self_ref += 1
                # print(f"[{self._ts()}][🎯]   ⚠️ 자기참조 스킵: {url[:80]}...", file=sys.stderr)
                continue  # 자기 참조 스킵
            
            if url and url in existing_urls:
                skipped_duplicate += 1
                continue  # 중복 스킵
            
            self.search_results.append(result)
            if url:
                existing_urls.add(url)
                # ━━ 개선: 검색 결과에 소스 신뢰도를 자동 부여 ━━
                trust = self.score_source_trust(url)
                result["_trust_score"] = trust
                self.source_trust_scores[url] = trust
            added_count += 1
        
        # 결과 로깅
        if skipped_self_ref > 0:
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{ts}][ℹ️] self-reference filtered: {skipped_self_ref}", file=sys.stderr)
        if skipped_duplicate > 0:
            from datetime import datetime
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{ts}][ℹ️] duplicate filtered: {skipped_duplicate}", file=sys.stderr)
        
        return added_count
    
    def get_time_status(self) -> Dict[str, Any]:
        """분석 시간 상태 반환"""
        remaining = self.max_iterations - self.iteration
        if remaining <= 2:
            urgency = "CRITICAL"
            message = "⚠️ 분석 시간 거의 다진! 즉시 최종 결론꾩텧해야 합니"
        elif remaining <= 4:
            urgency = "HIGH"
            message = "⚡ 분석 시간쇰쭏 많지 않은븯습니다 카테고리정리하고 결론을 준비하세요."
        else:
            urgency = "NORMAL"
            message = "충분분석 시간있습니다. 필요다른 Expert먭쾶 협력요청하세"
        
        return {
            "current_step": self.iteration,
            "remaining_steps": remaining,
            "urgency": urgency,
            "message": message,
        }
    
    def get_conversation_summary(self, compact: bool = False) -> str:
        """요약 생성 (LLM 프롬프트 - 시간 상태 포함
        
        Args:
            compact: True면 최소 정보만(토큰 압축)
        """
        lines = []
        
        # 시간 상태 먼저 표시
        time_status = self.get_time_status()
        lines.append(f"=== 분석 상태: Step {time_status['current_step']}/{time_status['current_step'] + time_status['remaining_steps']} ===")
        lines.append(f"[{time_status['urgency']}] {time_status['message']}")
        
        if compact:
            # 간소모드: 핵심 결론만
            lines.append("")
            for expert_name, output in self.expert_outputs.items():
                if output is None:
                    continue
                if expert_name == "decoder":
                    if not isinstance(output, dict):
                        continue
                    decoded = output.get("decoded_terms") or []
                    conf = output.get("overall_confidence")
                    best_titles = [t.get("best_match", {}).get("title") for t in decoded[:2] if t.get("best_match", {}).get("title")]
                    best_anchors = []
                    for t in decoded[:2]:
                        if not isinstance(t, dict):
                            continue
                        grounding = t.get("grounding") or {}
                        anchor = grounding.get("anchor_type") or (t.get("best_match") or {}).get("anchor_evidence")
                        if anchor:
                            best_anchors.append(anchor)
                    lines.append(f"[decoder] conf={conf}, titles={best_titles}, anchors={best_anchors}")
                elif expert_name == "verifier":
                    if not isinstance(output, dict):
                        continue
                    vr = output.get("verification_result") or {}
                    if not isinstance(vr, dict):
                        vr = {}
                    novel_id = vr.get("novel_identity") or {}
                    if not isinstance(novel_id, dict):
                        novel_id = {}
                    title = novel_id.get("official_novel_title") or novel_id.get("official_title")
                    grounding = vr.get("grounding_check") or {}
                    lines.append(
                        f"[verifier] relevant={vr.get('is_relevant')}, title={title}, "
                        f"anchor={grounding.get('anchor_found')}, grounded={grounding.get('decoder_grounded')}"
                    )
            if self.discourse_warning:
                lines.append(f"[warning] discourse={self.discourse_warning}")
            return "\n".join(lines)
        
        # 이전 전문가 분석 결과 요약
        lines.append("\n=== 이전 전문가 분석 결과 ===")
        for expert_name, output in self.expert_outputs.items():
            # None 체크
            if output is None or not isinstance(output, dict):
                continue

            lines.append(f"\n[{expert_name}]:")
            # 핵심 정보만 추출
            if expert_name == "gatekeeper":
                entities = output.get("detected_entities") or {}
                is_noise = output.get("is_noise", False)
                possible_titles = entities.get("possible_titles") or []
                lines.append(f"  - 노이즈: {is_noise}")
                lines.append(f"  - 후보 제목: {possible_titles[:3]}")
            elif expert_name == "discourse":
                disc = output.get("discourse_analysis") or {}
                domain = disc.get("primary_domain")
                intent = disc.get("intent")
                lines.append(f"  - 도메 {domain}")
                lines.append(f"  - 의도: {intent}")
            elif expert_name == "decoder":
                decoded = output.get("decoded_terms") or []
                conf = output.get("overall_confidence")
                lines.append(f"  - 전체 신뢰도 {conf}")
                for term in decoded[:2]:  # 처음 2개만
                    original = term.get("original")
                    best = term.get("best_match") or {}
                    grounding = term.get("grounding") or {}
                    anchor = grounding.get("anchor_type") or best.get("anchor_evidence")
                    lines.append(
                        f"    * {original} -> {best.get('title')} "
                        f"(conf={best.get('confidence')}, grounded={grounding.get('is_grounded')}, anchor={anchor})"
                    )
            elif expert_name == "verifier":
                vr = output.get("verification_result") or {}
                if not isinstance(vr, dict):
                    vr = {}
                is_rel = vr.get("is_relevant")
                novel_id = vr.get("novel_identity") or {}
                if not isinstance(novel_id, dict):
                    novel_id = {}
                title = novel_id.get("official_novel_title")
                conf = novel_id.get("confidence")
                grounding = vr.get("grounding_check") or {}
                lines.append(f"  - 관련⑥꽦: {is_rel}")
                lines.append(f"  - 작품: {title} (conf={conf})")
                lines.append(
                    f"  - 접지: anchor={grounding.get('anchor_found')}, "
                    f"decoder_grounded={grounding.get('decoder_grounded')}"
                )
        
        # 기록 compact 모드가 아닐 때만
        if self.messages:
            lines.append("\n=== 이전 기록 ===")
            for msg in self.messages[-3:]:  # 최근 3개만 (5->3)
                lines.append(
                    f"[{msg.from_expert.value}->{msg.to_expert.value if msg.to_expert else 'all'}] "
                    f"{msg.message_type}: {json.dumps(msg.content, ensure_ascii=False)[:100]}"  # 150->100
                )
        
        return "\n".join(lines)
    
    def get_expert_output(self, expert: ExpertType) -> Optional[Dict[str, Any]]:
        return self.expert_outputs.get(expert.value)
    
    def set_expert_output(self, expert: ExpertType, output: Dict[str, Any]) -> None:
        self.expert_outputs[expert.value] = output
        # 로그pretty-print결과 출력
        import json as _json, sys as _sys
        from datetime import datetime as _dt
        _ts = _dt.now().strftime("%H:%M:%S.%f")[:-3]
        _pretty = _json.dumps(output, ensure_ascii=False, indent=2)
        print(f"\n[{_ts}][📊 {expert.value}] 결과 JSON:\n{_pretty}\n", file=_sys.stderr, flush=True)


class Orchestrator:
    """
    🎯 Orchestrator - 전문가 조율
    
    븷:
    - 전문가들의 분석 결과 요청해석
    - ?ㅼ쓬대뼡 전문가를 실행유지 결정
    - 검색 요청 처리
    - 종료 조건 판단
    
    협력 제한:
    - 같은 전문가 간의 협력 최대 1회
    - 전체 협력 요청 최대 3회
    """
    
    def __init__(
        self,
        experts: Dict[ExpertType, Any],
        search_fn: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
        fetch_fn: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        max_iterations: int = 12,  # 협력 3회 + 여유 사이클 확보
        worker_id: int = 0,
        parallel_count: int = 1,
    ):
        self.experts = experts
        self.search_fn = search_fn
        self.fetch_fn = fetch_fn
        self.max_iterations = max_iterations
        self.worker_id = worker_id
        self.parallel_count = parallel_count
        self.name = "Orchestrator"
        self.emoji = "🎯"
    
    def _try_fast_path(
        self,
        ctx: ConversationContext,
        rules_config: Dict[str, Any],
    ) -> Optional[ConversationContext]:
        """
        ⚡ Fast-Path 경량 사전판별
        
        LLM 실행 놁씠 룰 기반으로 명확한 포스트를 빠른 처리합니다.
        
        Returns:
            - ConversationContext: Fast-Path로 처리 완료된 결과
            - None: Fast-Path 불가 시 정규 파이프라인 진행
        """
        import re
        
        post_data = ctx.post_data or {}
        title = post_data.get("title", "")
        
        # 본문 텍스추출
        content_texts = []
        for block in post_data.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        content_joined = " ".join(content_texts[:5])[:300]  # 상위 300자만
        
        title_stripped = title.strip()
        
        # ───>Fast-Path 1: 제목+본문 모두 비어있음 ───>
        if not title_stripped and not content_joined.strip():
            print(f"[{_ts()}] {self.emoji} ⚡Fast-Path NOISE: 제목+본문 비어있음", file=sys.stderr)
            return self._build_fast_noise_ctx(ctx, "제목과 본문이 비어있습니다.")
        
        # ───>Fast-Path 2: 자음/모음/특수문자만(이벤트숈꽌) ───>
        if title_stripped and re.fullmatch(r'[\u3131-\u314e\u314f-\u3163\s!?.~,;:\u314b\u314e\u3160\u315c]+', title_stripped):
            if len(content_joined.strip()) < 10:
                print(
                    f"[{_ts()}] {self.emoji} ⚡ Fast-Path NOISE: non-semantic title + short body ({len(content_joined.strip())})",
                    file=sys.stderr,
                )
                return self._build_fast_noise_ctx(ctx, f"이벤트입력 패턴: '{title_stripped}'")
        
        # ───>Fast-Path 3: 반복/반복 패턴 ───>
        if content_joined.strip():
            unique_chars = set(content_joined.replace(" ", ""))
            if len(unique_chars) <= 3 and len(content_joined.strip()) > 5:
                print(f"[{_ts()}] {self.emoji} ⚡Fast-Path NOISE: 반복 패턴 (고유 문자 {len(unique_chars)}개)", file=sys.stderr)
                return self._build_fast_noise_ctx(
                    ctx,
                    f"반복 패턴 노이즈: unique_chars={len(unique_chars)}",
                )
        
        # ───>Fast-Path 불가 시 정규 파이프라인───>
        return None
    
    def _build_fast_noise_ctx(
        self,
        ctx: ConversationContext,
        reason: str,
    ) -> ConversationContext:
        """Fast-Path 노이즈 결과의 ConversationContext 생성"""
        ctx.set_expert_output(ExpertType.GATEKEEPER, {
            "is_noise": True,
            "noise_reason": reason,
            "post_type": "noise",
            "detected_entities": {
                "possible_titles": [],
                "possible_authors": [],
                "possible_characters": [],
                "platforms_mentioned": [],
            },
            "key_terms": [],
            "context_clues": {},
            "search_requests": [],
            "confidence": "high",
            "notes": f"Fast-Path 노이즈 판정: {reason}",
        })
        
        ctx.set_expert_output(ExpertType.ARBITER, {
            "final_decision": {
                "is_relevant": False,
                "official_novel_title": None,
                "discussion_type": "noise",
                "confidence": "High",
            },
            "final_reasoning": f"Fast-Path 판정: {reason}",
            "metadata_synthesis": {},
        })
        
        ctx.add_message(ExpertMessage(
            from_expert=ExpertType.GATEKEEPER,
            to_expert=None,
            message_type="final",
            content={"decision": "noise", "reason": reason, "fast_path": True},
        ))
        
        print(f"[{_ts()}] {self.emoji} ⚡ Fast-Path 완료: LLM 호출 0회, 검색 0회", file=sys.stderr)
        return ctx
    
    def process(
        self,
        post_data: Dict[str, Any],
        comments: List[str],
        rules_config: Dict[str, Any],
    ) -> ConversationContext:
        """
        전문가ㅼ쓣 조율섏뿬 포스트분석 완료
        
        Returns:
            ConversationContext with all expert outputs and messages
        """
        ctx = ConversationContext(
            post_id=post_data.get("post_id", 0),
            post_data=post_data,
            comments=comments,
            max_iterations=self.max_iterations,
        )
        
        # 쓰레드로컬 워커 ID 설정 (_ts() 로그 prefix용)
        _orch_thread_local.worker_id = self.worker_id
        _orch_thread_local.parallel = self.parallel_count
        
        print(f"\n[{_ts()}] {self.emoji} Orchestrator 시작: post_id={ctx.post_id}", file=sys.stderr)
        self._prev_expert = ''  # 이전 전문가 초기화 (파이프라인 흐름 추적)
        
        # ⚡ Fast-Path: 경량 사전판별, 명확한 포스트는 빠른 처리
        fast_path = self._try_fast_path(ctx, rules_config)
        if fast_path is not None:
            _emit_monitor("expert_phase", {"expert": "fast_path", "status": "done"}, post_id=ctx.post_id)
            self._last_ctx = fast_path
            return fast_path
        
        # Phase 1: Gatekeeper 초기 분석
        gatekeeper_result = self._call_expert(
            ExpertType.GATEKEEPER, ctx, rules_config
        )
        
        # 노이즈 판정 시 DiscourseAnalyzer로 2차 확인
        # Gatekeeper가 author_talk/trope_discussion을 noise로 오분류할 수 있음
        # DiscourseAnalyzer가 novel_literature 도메인이면 noise 판정 취소
        if gatekeeper_result.get("is_noise"):
            discourse_override = False
            if ExpertType.DISCOURSE in self.experts:
                print(f"[{_ts()}] {self.emoji} 🔍 노이즈 후보 → DiscourseAnalyzer 2차 확인", file=sys.stderr)
                discourse_result = self._call_expert(
                    ExpertType.DISCOURSE, ctx, rules_config
                )
                discourse_analysis = discourse_result.get('discourse_analysis', {})
                domain = discourse_analysis.get('primary_domain')
                domain_conf = discourse_analysis.get('domain_confidence')
                ctx.primary_domain = domain
                ctx.discourse_intent = discourse_analysis.get('intent')
                print(f"[{_ts()}] {self.emoji} 🔖 담론 분석 완료: domain={domain}, confidence={domain_conf}", file=sys.stderr)
                
                # novel_literature 도메인이면 noise 취소 후 전문가 루프 진행
                # ⚡ Gatekeeper가 genre_discussion이고 엔티티0개이면 → 장르 일반론
                #    이 이 경우 Discourse가 novel_literature여도 noise 취소 금지
                #    (예: "창작물에 나오는 모든 형식이 아님" 등 장르 일반론)
                gk_entities = gatekeeper_result.get("detected_entities") or {}
                gk_has_entities = bool(
                    (gk_entities.get("possible_titles") or [])
                    or (gk_entities.get("possible_authors") or [])
                    or (gk_entities.get("possible_characters") or [])
                )
                gk_post_type = gatekeeper_result.get("post_type", "")
                discourse_intent = discourse_analysis.get('intent', '')
                
                # genre_discussion + 엔티티없음 + intent가 discuss_work가 아닌 경우 → noise 유지
                is_genre_general = (
                    gk_post_type == "genre_discussion"
                    and not gk_has_entities
                    and discourse_intent != "discuss_work"
                )

                # ⚡Discourse 근거 접지(lexical grounding) 검사                # Discourse가 표시핵심 근거(domain_evidence/title_novel_terms)가
                # 실제 제목/본문/댓글 텍스트에 존재하는지 확인한다.
                # (모델 환각 근거로 noise를 취소하는 것을 방지)
                _post_title = str((ctx.post_data or {}).get("title") or "")
                _post_body = " ".join(
                    (
                        b.get("text", "") if isinstance(b, dict)
                        else (str(b) if isinstance(b, str) else "")
                    )
                    for b in (ctx.post_data or {}).get("content_blocks", [])
                )
                _comment_text = " ".join(ctx.comments or [])
                _full_text_norm = f"{_post_title} {_post_body} {_comment_text}".lower().replace(" ", "")

                _raw_disc_terms = (
                    (discourse_analysis.get("title_novel_terms") or [])
                    + (discourse_analysis.get("domain_evidence") or [])
                )
                _disc_terms_norm: List[str] = []
                for _term in _raw_disc_terms:
                    if not isinstance(_term, str):
                        continue
                    _norm = _term.lower().replace(" ", "").strip()
                    if len(_norm) >= 2:
                        _disc_terms_norm.append(_norm)

                _disc_hit_terms = sorted({
                    _term for _term in _disc_terms_norm
                    if _term and _term in _full_text_norm
                })
                _disc_hit_count = len(_disc_hit_terms)

                # Gatekeeper가 노이즈 커뮤니티 컨텐츠로 본 경우에는
                # noise 취소 기준을 더 엄격하게 적용 (모호한 1개 의심스럽고 불충분)
                _gk_context = gatekeeper_result.get("context_clues") or {}
                _has_url_clue = bool(_gk_context.get("has_url_in_comments"))
                _strict_noise_types = {"community_banter", "noise"}
                _requires_strict_grounding = gk_post_type in _strict_noise_types
                _min_discourse_hits = 1 if _has_url_clue else 2
                
                # ⚡manga_comics 도메몄씠면noise 유지 (소설아닌 비관련 매체)
                # 단, Gatekeeper가 possible_titles를 감지한 경우 → 검증 후 판단해야 하므로 면제
                _gk_has_titles = bool(gk_entities.get("possible_titles") or [])
                if domain == 'manga_comics' and domain_conf in ('high', 'medium') and not _gk_has_titles:
                    print(
                        f"[{_ts()}] {self.emoji} ⚡Discourse=manga_comics({domain_conf})"
                        f" 비소설 매체(만화/동인지), noise 유지",
                        file=sys.stderr
                    )
                    # manga_comics 경고를컨텍스트
                    ctx.discourse_warning = f"manga_comics({domain_conf})"
                    ctx.uncertainty_sources.append(
                        f"DiscourseAnalyzer: domain=manga_comics({domain_conf}) 만화/동인지 매체, 소설 아님"
                    )
                elif domain == 'manga_comics' and _gk_has_titles:
                    # manga_comics이지만possible_titles가 있음 검증으로확인 필요
                    print(
                        f"[{_ts()}] {self.emoji} ⚠️ Discourse=manga_comics BUT possible_titles={gk_entities.get('possible_titles')}"
                        f" → noise 취소, 검증 판단",
                        file=sys.stderr
                    )
                    gatekeeper_result["is_noise"] = False
                    gatekeeper_result["noise_reason"] = None
                    if gatekeeper_result.get("post_type") == "noise":
                        gatekeeper_result["post_type"] = "work_discussion"
                    ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper_result)
                    # manga_comics 경고유지 (Decoder에서 참고)
                    ctx.discourse_warning = f"manga_comics({domain_conf}):possible_titles_exist"
                    discourse_override = True
                elif domain == 'novel_literature' and domain_conf in ('high', 'medium') and not is_genre_general:
                    # community_banter/noise에서 나와ㅻ뒗 케댁뒪                    # Discourse 근거가 실제 텍스트에 충분히 접지되었는지 확인 후 취소
                    if _requires_strict_grounding and _disc_hit_count < _min_discourse_hits:
                        print(
                            f"[{_ts()}] {self.emoji} ⚡Gatekeeper=noise + Discourse 근거 불충분: "
                            f"hits={_disc_hit_count}<{_min_discourse_hits}, "
                            f"terms={_disc_hit_terms[:4]} → noise 유지",
                            file=sys.stderr
                        )
                        if not ctx.discourse_warning:
                            ctx.discourse_warning = "weak_discourse_grounding(novel_literature)"
                        ctx.uncertainty_sources.append(
                            f"DiscourseAnalyzer: novel_literature대굹 근거 접지 쏀븿 "
                            f"(hits={_disc_hit_count}, post_type={gk_post_type})"
                        )
                    else:
                        print(f"[{_ts()}] {self.emoji} ⚠️ Gatekeeper=noise BUT Discourse=novel_literature → noise 취소, 분석 계속", file=sys.stderr)
                        gatekeeper_result["is_noise"] = False
                        gatekeeper_result["noise_reason"] = None
                        # post_type이 noise면 work_discussion으로 대체
                        if gatekeeper_result.get("post_type") == "noise":
                            gatekeeper_result["post_type"] = "work_discussion"
                        ctx.set_expert_output(ExpertType.GATEKEEPER, gatekeeper_result)
                        discourse_override = True
                elif is_genre_general:
                    print(
                        f"[{_ts()}] {self.emoji} ⚡Gatekeeper=genre_discussion(엔티티0) + Discourse intent={discourse_intent}"
                        f" → noise 취소 차단, 장르 일반론으로 유지",
                        file=sys.stderr
                    )
            
            if not discourse_override:
                print(f"[{_ts()}] {self.emoji} 노이즈 감지 → 조기 종료", file=sys.stderr)
                ctx.add_message(ExpertMessage(
                    from_expert=ExpertType.GATEKEEPER,
                    to_expert=None,
                    message_type="final",
                    content={"decision": "noise", "reason": gatekeeper_result.get("noise_reason")},
                ))
                return ctx
        
        # Phase 1.5: Discourse Analysis (도메의도 뚯븙)
        # Gatekeeper가 엔티티를 추출했지만 진짜 도메인 컨텍스트가 필요
        # (noise 2차 확인에서 이미 수행한 경우 스킵)
        if ExpertType.DISCOURSE in self.experts and not ctx.primary_domain:
            discourse_result = self._call_expert(
                ExpertType.DISCOURSE, ctx, rules_config
            )
            # 단계 1: DiscourseAnalyzer 결과를 ctx에 저장하여 Verifier/Arbiter가 활용
            discourse_analysis = discourse_result.get('discourse_analysis', {})
            ctx.primary_domain = discourse_analysis.get('primary_domain')
            ctx.discourse_intent = discourse_analysis.get('intent')
            print(f"[{_ts()}] {self.emoji} 🔖 담론 분석 완료: domain={ctx.primary_domain}, intent={ctx.discourse_intent}", file=sys.stderr)
        
        # ⚡ 연상기호 감지: is_association_not_discussion + title_body_consistency 불일치
        # 제목이 작품명처럼 보이는 것이 있어도, 본문과 전혀 무관하면 → 작품 검색 강도를 더 축소
        disc_out_assoc = ctx.get_expert_output(ExpertType.DISCOURSE)
        if disc_out_assoc:
            d_assoc = disc_out_assoc.get('discourse_analysis', {})
            is_assoc = d_assoc.get('is_association_not_discussion', False)
            title_body_ok = d_assoc.get('title_body_consistency', True)
            is_coherent = d_assoc.get('is_coherent', True)
            
            if is_assoc and not title_body_ok:
                ctx.is_association_post = True
                assoc_evidence = d_assoc.get('association_evidence', '')
                print(
                    f"[{_ts()}] {self.emoji} ❗연상기호 감지: "
                    f"is_association=true, title_body_consistency=false"
                    f" 작품매칭 강도 축소",
                    file=sys.stderr,
                )
                # discourse_warning 설정 (Decoder 자동
                if not ctx.discourse_warning:
                    ctx.discourse_warning = "association_post(title_body_mismatch)"
                ctx.uncertainty_sources.append(
                    f"DiscourseAnalyzer: 연상기 판정 (제목 유사 문구. {assoc_evidence[:100]}"
                )
            elif not is_coherent and not title_body_ok:
                # is_association은 아니지만 비일관 + 제목-본문 불일치 시 약한 연상기호
                ctx.is_association_post = True
                print(
                    f"[{_ts()}] {self.emoji} ❗비일관 글 감지: "
                    f"is_coherent=false, title_body_consistency=false"
                    f" 작품매칭 강도 축소",
                    file=sys.stderr,
                )
                if not ctx.discourse_warning:
                    ctx.discourse_warning = "incoherent_post(title_body_mismatch)"
        
        # ⚡ Discourse 갑Override: non-novel 도메high)이면 경고 설정
        # Decoder/Verifier/Arbiter가 이 경고를 받아서 과잉 근거를 방지
        NOVEL_DOMAINS = {"novel_literature", "novel_work"}
        if ctx.primary_domain and ctx.primary_domain not in NOVEL_DOMAINS:
            discourse_output = ctx.get_expert_output(ExpertType.DISCOURSE)
            d_conf = "high"
            if discourse_output:
                d_conf = discourse_output.get("discourse_analysis", {}).get("domain_confidence", "medium")
            if d_conf in ("high", "medium"):
                ctx.discourse_warning = f"{ctx.primary_domain}({d_conf})"
                ctx.uncertainty_sources.append(
                    f"DiscourseAnalyzer: domain={ctx.primary_domain}({d_conf}), intent={ctx.discourse_intent} 소설 관련 포스트가 아닐 가능성 높음스트가 아닐 가능성 높음"
                )
                print(f"[{_ts()}] {self.emoji} ⚠️ Discourse 경고: {ctx.discourse_warning} → Decoder/Arbiter 전달", file=sys.stderr)
                
                # ⚡manga_comics 도메강제 noise: 소설아닌 비관련 매체
                # Gatekeeper가 noise=false여도 Discourse가 manga_comics(high/medium)이면 조기 종료
                # 단, Gatekeeper가 possible_titles를 감지한 경우 → 검증 후 판단해야 하므로 면제
                _gk2 = (ctx.get_expert_output(ExpertType.GATEKEEPER) or {}).get("detected_entities") or {}
                _gk2_has_titles = bool(_gk2.get("possible_titles") or [])
                if ctx.primary_domain == "manga_comics" and d_conf == "high" and not _gk2_has_titles:
                    # 본문에 비소설 매체 의심어가 실제로 있는지 한번 더 확인
                    from ..rules import NON_NOVEL_MEDIA_KEYWORDS
                    post_title = (ctx.post_data.get("title") or "").lower()
                    post_texts = " ".join(
                        (b.get("text", "") if isinstance(b, dict) else str(b))
                        for b in ctx.post_data.get("content_blocks", [])
                    ).lower()
                    all_text = f"{post_title} {post_texts} {' '.join(ctx.comments).lower()}"
                    
                    has_media_keyword = any(kw in all_text for kw in NON_NOVEL_MEDIA_KEYWORDS)
                    has_media_term = "만화" in all_text or "동인지" in all_text or "동인" in all_text
                    
                    if has_media_keyword or has_media_term:
                        print(
                            f"[{_ts()}] {self.emoji} ⚡manga_comics 강제 noise: "
                            f"Discourse=manga_comics({d_conf}) + 비소설 매체 의심어 감지 → 조기 종료",
                            file=sys.stderr
                        )
                        ctx.add_message(ExpertMessage(
                            from_expert=ExpertType.DISCOURSE,
                            to_expert=None,
                            message_type="final",
                            content={
                                "decision": "noise",
                                "reason": f"비소설 매체(manga_comics): 만화/동인지 관련 글",
                            },
                        ))
                        return ctx

        # ⚡ 장르/트로프 일반론 감지: discuss_genre intent면 특정 작품 근거 무효
        if ctx.discourse_intent == "discuss_genre" and not ctx.discourse_warning:
            discourse_output = ctx.get_expert_output(ExpertType.DISCOURSE)
            d_conf = "high"
            if discourse_output:
                d_conf = discourse_output.get("discourse_analysis", {}).get("intent_confidence", "medium")
            if d_conf in ("high", "medium"):
                ctx.discourse_warning = f"discuss_genre({d_conf})"
                ctx.uncertainty_sources.append(
                    f"DiscourseAnalyzer: intent=discuss_genre({d_conf}) -> generic genre discussion, title grounding uncertain"
                )
                print(f"[{_ts()}] {self.emoji} genre-generalization warning: {ctx.discourse_warning} -> decoder rerun", file=sys.stderr)

        # Phase 2: 검색 수행
        search_requests = gatekeeper_result.get("search_requests", [])
        
        # ⚡ 개선A: Gatekeeper 실패 시 key_terms 복구
        # Gatekeeper가 JSON 파싱 에러 형식으로 _default_result를 반환하면 key_terms=[] (falsy)
        # DiscourseAnalyzer가 novel_literature 도메인을 감지한 경우, title_novel_terms를 key_terms로 복구
        gk_key_terms = gatekeeper_result.get("key_terms") or []
        if not gk_key_terms and ctx.primary_domain == "novel_literature":
            discourse_output = ctx.get_expert_output(ExpertType.DISCOURSE)
            if discourse_output:
                d_analysis = discourse_output.get("discourse_analysis", {})
                novel_terms = d_analysis.get("title_novel_terms") or []
                recovered_terms = list(dict.fromkeys(novel_terms))  # 순서 유지 중복 제거
                
                if recovered_terms:
                    gatekeeper_result["key_terms"] = recovered_terms
                    print(f"[{_ts()}] {self.emoji} 🔗 Gatekeeper key_terms 복구 (Discourse에서): {recovered_terms}", file=sys.stderr)
                else:
                    # Discourse에서도 못 찾으면 포스트제목에서 기본 추출
                    post_title = ctx.post_data.get("title", "") if ctx.post_data else ""
                    if post_title and len(post_title) >= 2:
                        gatekeeper_result["key_terms"] = [post_title.strip()]
                        print(f"[{_ts()}] {self.emoji} 🔗 Gatekeeper key_terms 복구 (포스트제목): [{post_title.strip()}]", file=sys.stderr)
        
        # noise 취소 후 search_requests가 비어있으면 key_terms에서 자동 생성
        if not search_requests and gatekeeper_result.get("key_terms"):
            key_terms = gatekeeper_result["key_terms"]
            print(f"[{_ts()}] {self.emoji} 🔍 검색 요청 없음 → key_terms에서 자동 생성: {key_terms[:4]}", file=sys.stderr)
            for term in key_terms[:4]:
                if len(term) >= 2:  # 최소 2글자 이상
                    search_requests.append({
                        "query": f"{term} 소설",
                        "purpose": "official_title_verify",
                        "priority": 1,
                    })
                    search_requests.append({
                        "query": f"{term} 작가",
                        "purpose": "author_verify",
                        "priority": 2,
                    })
        
        if search_requests and self.search_fn:
            # ⚡ Phase28: Discourse-Informed 스마트 검색 생성
            # 기존 기계적 split을 Discourse의 이해를 기반으로 한 검색으로 대체
            
            discourse_output = ctx.get_expert_output(ExpertType.DISCOURSE)
            discourse_novel_terms: set = set()
            discourse_suggestions: list = []
            
            if discourse_output:
                d_analysis = discourse_output.get("discourse_analysis", {})
                # Discourse가 근거한 소설 관련 단어만 split 대상
                discourse_novel_terms = set(d_analysis.get("title_novel_terms") or [])
                # Discourse LLM의 단계적 검색 쿼리
                discourse_suggestions = d_analysis.get("search_suggestions") or []
            
            # Step A: Discourse search_suggestions 우선 적용 (LLM맥락 이해 단계쿼리)
            existing_queries = {r.get("query", "") for r in search_requests}
            if discourse_suggestions:
                for sugg in discourse_suggestions[:3]:
                    if not isinstance(sugg, dict):
                        continue
                    q = sugg.get("query", "").strip()
                    if q and q not in existing_queries and len(q) <= 50:
                        search_requests.append({
                            "query": q,
                            "purpose": f"discourse_suggestion: {sugg.get('purpose', '')}",
                            "priority": sugg.get("priority", 1),
                        })
                        existing_queries.add(q)
                print(f"[{_ts()}] {self.emoji} 📌 Discourse 스마트 검색 {len(discourse_suggestions)}개 추가", file=sys.stderr)
            
            # Step B: 합성어 분리 검색을 Discourse novel_terms에만 적용 (기존 전체 key_terms 대신)
            # Discourse가 확고한 novel_terms가 비어있으면 기존 방식으로 fallback
            import re as _re
            gk_key_terms_for_split = gatekeeper_result.get("key_terms") or []
            
            for term in gk_key_terms_for_split:
                # ⚡ LLM이 리스트/숫자 등 비문자열을 반환할 수 있으므로 str만 처리
                if not isinstance(term, str):
                    continue
                term_clean = _re.sub(r'[^\uac00-\ud7a3]', '', term)
                if len(term_clean) < 5:
                    continue
                
                # ⚡ Discourse 필터: novel_terms에 포함된 것만 split (아니면 스킵)
                # Discourse가 없으면 모든 5글자+ 단어를 분리 (기존 방식)
                if discourse_novel_terms:
                    # term이 novel_terms 중 하나에 포함되거나 겹치는지 확인
                    # ⚡ LLM이 글자를 반환할 수 있으므로 str만 필터
                    is_novel_term = any(
                        nt in term or term in nt
                        for nt in discourse_novel_terms
                        if isinstance(nt, str)
                    )
                    if not is_novel_term:
                        print(f"[{_ts()}] {self.emoji} ⚡ 합성어분리 스킵: '{term}' (Discourse novel_terms없음)", file=sys.stderr)
                        continue
                
                # 3글자/4글자 분리
                for sp in [3, 4]:
                    if sp >= len(term_clean):
                        continue
                    front = term_clean[:sp]
                    back = term_clean[sp:]
                    
                    # 앞부분 검색(줄임 부분)
                    q_front = f"{front} 소설"
                    if q_front not in existing_queries:
                        search_requests.append({
                            "query": q_front,
                            "purpose": "abbreviation_split_search",
                            "priority": 2,
                        })
                        existing_queries.add(q_front)
                    
                    # 앞부분을 더 분리 (4글자 시 2+2 검색)
                    if sp == 4 and len(front) == 4:
                        q_split = f"{front[:2]} {front[2:]} 소설"
                        if q_split not in existing_queries:
                            search_requests.append({
                                "query": q_split,
                                "purpose": "abbreviation_deep_split_search",
                                "priority": 3,
                            })
                            existing_queries.add(q_split)
                
                print(f"[{_ts()}] {self.emoji} ⚡ 합성어 분리 검색 추가: '{term}' ({len(term_clean)}글자)", file=sys.stderr)
            
            # ⚡ Fix C: key_terms 중 search_requests에 커버 안 된 것에 대해
            # "{term} 소설" 검색 자동 추가 (개돌 같은 게임단어 dead-end 방지)
            # ⚠️ 캐릭터명/일반어는 제외 (주인공 빈도수, 아까움 등 불필요 검색 방지)
            gk_all_key_terms = gatekeeper_result.get("key_terms") or []
            gk_entities = gatekeeper_result.get("detected_entities") or {}
            gk_characters = set()
            for c in (gk_entities.get("possible_characters") or []):
                if isinstance(c, str):
                    gk_characters.add(_re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', c))
            gk_titles = set()
            for t in (gk_entities.get("possible_titles") or []):
                if isinstance(t, str):
                    gk_titles.add(_re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', t))
            gk_authors = set()
            for a in (gk_entities.get("possible_authors") or []):
                if isinstance(a, str):
                    gk_authors.add(_re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', a))
            # 일반필터 (작품명·작가명이 될 수 없는 범용 한국어
            _GENERIC_TERMS = {
                "소개", "내용", "후기", "추천", "스포", "리뷰", "소설", "작가",
                "주인공", "캐릭터", "결말", "장르", "완결", "연재", "소설가",
                "작품", "설정", "스토리", "플롯", "세계관", "먼치킨",
            }
            for kt in gk_all_key_terms:
                if not isinstance(kt, str) or len(kt) < 2:
                    continue
                kt_clean = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', kt)
                if not kt_clean or len(kt_clean) < 2:
                    continue
                # ⚡ 캐릭터명 제외 (possible_characters에 있으면 캐릭터이고 작품 검색 불필요
                if kt_clean in gk_characters:
                    continue
                # ⚡ 일반제외
                if kt_clean in _GENERIC_TERMS:
                    continue
                # 이미 existing_queries에 "소설" 조합이 있는지 확인
                q_novel = f"{kt} 소설"
                if q_novel not in existing_queries:
                    # 해당 key_term이 이미 다른 검색에서 커버하는지 확인
                    already_has_novel = any(kt_clean in eq.replace(' ', '') and '소설' in eq for eq in existing_queries)
                    if not already_has_novel:
                        search_requests.append({
                            "query": q_novel,
                            "purpose": "key_term_novel_search",
                            "priority": 2,
                        })
                        existing_queries.add(q_novel)
            
            # 초기 검색 쿼리 이력 기록
            for req in search_requests:
                q = req.get("query", "").strip()
                if q:
                    ctx.searched_queries.add(q)
            initial_results = self._execute_searches(search_requests, ctx.post_id)
            ctx.search_results = initial_results  # 초기 검색을 직접 할당 (중복 없음)
            _emit_monitor("expert_phase", {"expert": "search", "status": "done"}, post_id=ctx.post_id)
            
            # 🔬 Deep Search: snippet 분석 + URL 페치 + 추가 검색
            if initial_results:
                gk_key = gatekeeper_result.get("key_terms") or []
                safe_key = [t for t in gk_key if isinstance(t, str)]
                self._deep_search_enrich(
                    ctx, safe_key, initial_results,
                    post_data=ctx.post_data or {},
                    gatekeeper_result=gatekeeper_result,
                )
        
        # Phase 3: 력적 전문가 루프 (Agentic Collaboration)
        while ctx.iteration < ctx.max_iterations:
            ctx.iteration += 1
            # max_iterations에 안전장치일 뿐, 실제로는 보통 3-5번만종료
            print(f"\n[{_ts()}] {self.emoji} --- Step {ctx.iteration} ---", file=sys.stderr)
            
            # ?ㅼ쓬 ?≪뀡 결정
            next_action = self._decide_next_action(ctx, rules_config)
            
            if next_action["action"] == "call_expert":
                # null/None expert 방어: LLM의 request_expert가 null로 오는 경우 대비
                raw_expert = next_action.get("expert")
                if not raw_expert or raw_expert == "null":
                    print(f"[{_ts()}] {self.emoji} ⚠️ null expert 요청 무시, finalize로 전환", file=sys.stderr)
                    next_action = {"action": "finalize"}
                    break
                expert_type = ExpertType(raw_expert)
                is_collaboration = next_action.get("collaboration", False)
                
                if is_collaboration:
                    print(f"[{_ts()}] {self.emoji} 🔄 협력 실행: {expert_type.value}", file=sys.stderr)
                
                result = self._call_expert(expert_type, ctx, rules_config)
                
                # ⚡ Fix: 협력 Gatekeeper 실행 후 key_terms 병합 + 미발견 단어 보충 검색
                # 2차GK가 반환한 key_terms 중 search_requests에 없는 단어를 자동 검색
                if is_collaboration and expert_type == ExpertType.GATEKEEPER and result and self.search_fn:
                    import re as _re_collab
                    collab_key_terms = result.get("key_terms") or []
                    collab_search_queries = {r.get("query", "") for r in (result.get("search_requests") or [])}
                    print(f"[{_ts()}] {self.emoji} 🔍 보충 검색 진입: key_terms={collab_key_terms[:6]}, search_queries={list(collab_search_queries)[:4]}", file=sys.stderr)
                    supplementary_searches = []
                    for kt in collab_key_terms:
                        if not isinstance(kt, str) or len(kt) < 2:
                            continue
                        kt_clean = _re_collab.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', kt)
                        if not kt_clean or len(kt_clean) < 2:
                            continue
                        # 이미 search_requests포함⑹뼱몄 확인
                        already_covered = any(kt_clean in sq.replace(' ', '') for sq in collab_search_queries)
                        if already_covered:
                            continue
                        # 이미 이전 검색에서 커버된 단어인지 확인
                        already_searched = any(kt_clean in sq.replace(' ', '') for sq in ctx.searched_queries)
                        if already_searched:
                            print(f"[{_ts()}] {self.emoji} 🔍 보충 스킵 (이미 검색됨): '{kt_clean}'", file=sys.stderr)
                            continue
                        # 미발견 key_term 에 보충 검색 생성
                        print(f"[{_ts()}] {self.emoji} 🔍 보충 검색: '{kt}' (clean='{kt_clean}')", file=sys.stderr)
                        q_novel = f"{kt} 소설"
                        if q_novel not in ctx.searched_queries:
                            supplementary_searches.append({"query": q_novel, "purpose": "key_term_supplement", "priority": 1})
                            ctx.searched_queries.add(q_novel)
                        q_author = f"{kt} 작가"
                        if q_author not in ctx.searched_queries:
                            supplementary_searches.append({"query": q_author, "purpose": "key_term_supplement", "priority": 2})
                            ctx.searched_queries.add(q_author)
                    if supplementary_searches:
                        print(f"[{_ts()}] {self.emoji} 🔍 key_terms 보충 검색{len(supplementary_searches)}개 {[s['query'] for s in supplementary_searches[:4]]}", file=sys.stderr)
                        sup_results = self._execute_searches(supplementary_searches, ctx.post_id)
                        if sup_results:
                            added = ctx.add_search_results(sup_results)
                            print(f"[{_ts()}] {self.emoji} 🔍 보충 검색 결과 {added}개추가", file=sys.stderr)
                            # 결과에서 snippet_hints 재추출
                            safe_kt = [t for t in collab_key_terms if isinstance(t, str)]
                            new_hints = self._extract_hints_from_snippets(sup_results, safe_kt)
                            if hasattr(ctx, 'snippet_hints') and ctx.snippet_hints:
                                self._merge_snippet_hints(
                                    ctx,
                                    new_hints,
                                    safe_kt,
                                    post_data=ctx.post_data,
                                )
                    else:
                        print(f"[{_ts()}] {self.emoji} 🔍 보충 검색 필요 없음 (모든 key_terms 이미 커버됨", file=sys.stderr)
                
                # ⚡CRITICAL: 협력 실행이든 일반 실행이든, verification_search는 무조건 수행!
                # 추가 검색 요청 확인 (search_requests 또는 verification_search)
                if result.get("search_requests") and self.search_fn:
                    # 검색 쿼리 이력 기록
                    for req in result["search_requests"]:
                        q = req.get("query", "").strip()
                        if q:
                            ctx.searched_queries.add(q)
                    new_results = self._execute_searches(result["search_requests"], ctx.post_id)
                    added = ctx.add_search_results(new_results)
                    if added < len(new_results):
                        print(f"[{_ts()}] {self.emoji} 🔍 중복 {len(new_results) - added}개제거", file=sys.stderr)
                    
                    # ⚡ Fix B: 협력 GK search_requests 수행 후 snippet_hints 재추출
                    # 새 검색 결과에서 prefix matching 형식을 다시 수행하여 개돌→개돌전쟁같은 매핑 발견
                    if is_collaboration and expert_type == ExpertType.GATEKEEPER and new_results:
                        collab_kt = result.get("key_terms") or []
                        safe_collab_kt = [t for t in collab_kt if isinstance(t, str)]
                        if safe_collab_kt:
                            sr_hints = self._extract_hints_from_snippets(new_results, safe_collab_kt)
                            if hasattr(ctx, 'snippet_hints') and ctx.snippet_hints:
                                self._merge_snippet_hints(
                                    ctx,
                                    sr_hints,
                                    safe_collab_kt,
                                    post_data=ctx.post_data,
                                )
                            if sr_hints.get("title_hints") or sr_hints.get("author_hints") or sr_hints.get("abbreviation_hints"):
                                print(
                                    f"[{_ts()}] {self.emoji} 🔍 협력 검색 후 snippet_hints 갱신: "
                                    f"title={len(sr_hints.get('title_hints', []))}개 "
                                    f"author={len(sr_hints.get('author_hints', []))}개 "
                                    f"abbrev={len(sr_hints.get('abbreviation_hints', []))}",
                                    file=sys.stderr
                                )
                
                # Decoder/Verifier의 verification_search 처리
                # ⚡특별: 검색 후 해당 전문가를 다시 실행하여 새 결과로 리벨런스
                if result.get("verification_search") and self.search_fn:
                    verification_queries = result["verification_search"]
                    
                    # 배열 또는 ?⑥씪 문자처리
                    if isinstance(verification_queries, str):
                        verification_queries = [verification_queries]
                    elif not isinstance(verification_queries, list):
                        verification_queries = []
                    
                    if verification_queries:
                        # 이미 검증한 쿼리 필터링
                        new_queries = [q for q in verification_queries if q not in ctx.searched_queries]
                        skipped = len(verification_queries) - len(new_queries)
                        if skipped > 0:
                            print(f"[{_ts()}] {self.emoji} 🔍 이미 검증한 쿼리 {skipped}개스킵", file=sys.stderr)
                        if not new_queries:
                            print(f"[{_ts()}] {self.emoji} 🔍 모든 verification_search 쿼리가 이미 검색됨 → 스킵", file=sys.stderr)
                        
                        verification_queries = new_queries
                    
                    if verification_queries:
                        print(f"[{_ts()}] {self.emoji} 🔍 축약어 후보 재검증{len(verification_queries)}가 {verification_queries[:2]}...", file=sys.stderr)
                        ctx.searched_queries.update(verification_queries)  # 검색 이력 기록
                        
                        # 다중 쿼리를 검색 요청 정식으로 변환
                        search_requests = [
                            {"query": q, "purpose": "abbreviation_verification", "priority": 1}
                            for q in verification_queries
                        ]
                        
                        # 🏷️ "근거된 작품 제목 + 캐릭터/단어" 조합 검색 자동 추가
                        # ⚡KNOWN_ABBREVIATIONS를 최우선으로 확인 (가장 신뢰도 높음)
                        _identified_title = None
                        _gk_out_v = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
                        _gk_entities_v = (_gk_out_v.get("detected_entities") or {}) if isinstance(_gk_out_v, dict) else {}
                        _gk_titles_v = _gk_entities_v.get("possible_titles", []) or []
                        _post_title_v = (ctx.post_data or {}).get("title", "")
                        for _kt in (_gk_titles_v + [_post_title_v]):
                            if isinstance(_kt, str):
                                import re as _re_v
                                _kt_clean = _re_v.sub(r'[^\uac00-\ud7a3]', '', _kt)
                                if _kt_clean in KNOWN_ABBREVIATIONS:
                                    _identified_title = KNOWN_ABBREVIATIONS[_kt_clean]
                                    break
                        
                        # KNOWN_ABBREVIATIONS에 없으면 snippet_hints에서 확인
                        if not _identified_title and hasattr(ctx, 'snippet_hints') and ctx.snippet_hints:
                            _abbrev_hints = ctx.snippet_hints.get("abbreviation_hints", [])
                            # 줄임 매핑에서 full title 추출 (abbreviation_hints만 사용 시 title_hints와 시너지 가능)
                            if _abbrev_hints:
                                _identified_title = _abbrev_hints[0].get("full", "")
                        
                        # suspected_titles에서도 확인 (Decoder가 이미 근거한 제목)
                        if not _identified_title and ctx.suspected_titles:
                            for _st in ctx.suspected_titles:
                                if isinstance(_st, dict) and _st.get("title") and _st.get("confidence", 0) >= 0.7:
                                    _identified_title = _st["title"]
                                    break
                        
                        if _identified_title:
                            _gk_out_c = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
                            _gk_entities_c = (_gk_out_c.get("detected_entities") or {}) if isinstance(_gk_out_c, dict) else {}
                            _gk_chars = _gk_entities_c.get("possible_characters", []) or []
                            
                            for _char in _gk_chars[:3]:
                                if isinstance(_char, str) and len(_char) >= 2:
                                    combo_q = f"{_identified_title} {_char}"
                                    if combo_q not in ctx.searched_queries and len(combo_q) <= 50:
                                        search_requests.append({
                                            "query": combo_q,
                                            "purpose": "title_character_verification",
                                            "priority": 1,
                                        })
                                        ctx.searched_queries.add(combo_q)
                                        print(f"[{_ts()}] {self.emoji} 🔑 조합 검색 추가: '{combo_q}'", file=sys.stderr)
                        
                        new_results = self._execute_searches(search_requests, ctx.post_id)
                        
                        if new_results:
                            added = ctx.add_search_results(new_results)
                            print(f"[{_ts()}] {self.emoji} 🔗 새 검색 결과 {added}개 추가 (중복 {len(new_results) - added}개 제거)", file=sys.stderr)
                            print(f"[{_ts()}] {self.emoji} 🔗 새 검색 결과로 전문가 리콜 시작", file=sys.stderr)
                        
                        # ⚡축약어 재검증 후 Decoder 와 Verifier 리콜 사이클
                        # 1. Decoder 리콜(새 검색 결과로 리해석)
                        print(f"[{_ts()}] {self.emoji} 🔗 1단계: Decoder 리콜(새 검색 결과)", file=sys.stderr)
                        gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
                        decoder_expert = self.experts.get(ExpertType.DECODER)
                        if decoder_expert:
                            _emit_monitor(
                                "expert_phase",
                                {
                                    "expert": "decoder",
                                    "status": "running",
                                    "recall": True,
                                    "from": "verifier",
                                    "reason": "verifier requested decoder recall after additional evidence",
                                },
                                post_id=ctx.post_id,
                            )
                            decoder_result = decoder_expert.analyze(
                                gatekeeper_out,
                                ctx.search_results,
                                rules_config.get("slang_dictionary", {}),
                                conversation_context=ctx.get_conversation_summary(),
                                ctx=ctx,  # suspected_titles 낅뜲댄듃
                            )
                            ctx.set_expert_output(ExpertType.DECODER, decoder_result)
                            _emit_monitor("expert_phase", {"expert": "decoder", "status": "done", "recall": True, "from": "verifier"}, post_id=ctx.post_id)
                            
                            # 토큰 사용량 출력
                            llm = getattr(decoder_expert, 'llm', None)
                            if llm and llm.last_usage:
                                usage = llm.last_usage
                                prompt_tok = usage.get("prompt_tokens", 0)
                                completion_tok = usage.get("completion_tokens", 0)
                                total_tok = usage.get("total_tokens", prompt_tok + completion_tok)
                                print(f"[{_ts()}][{self.emoji}] Decoder(리콜) 토큰 사용량", file=sys.stderr)
                                print(f"  입력: {prompt_tok:,} tokens", file=sys.stderr)
                                print(f"  출력: {completion_tok:,} tokens", file=sys.stderr)
                                print(f"  총합: {total_tok:,} tokens", file=sys.stderr)
                                if not hasattr(ctx, 'token_usage'):
                                    ctx.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                                ctx.token_usage["prompt_tokens"] += prompt_tok
                                ctx.token_usage["completion_tokens"] += completion_tok
                                ctx.token_usage["total_tokens"] += total_tok
                            
                            # ⚡2차 Decoder의 verification_search에 추가 검색
                            recall_vs = decoder_result.get("verification_search")
                            if recall_vs and self.search_fn:
                                if isinstance(recall_vs, str):
                                    recall_vs = [recall_vs]
                                elif not isinstance(recall_vs, list):
                                    recall_vs = []
                                if recall_vs:
                                    # 이미 검증한 쿼리 필터링
                                    recall_vs = [q for q in recall_vs if q not in ctx.searched_queries]
                                if recall_vs:
                                    print(f"[{_ts()}] {self.emoji} 🔍 리콜 Decoder 추가 검색{len(recall_vs)}가 {recall_vs[:2]}...", file=sys.stderr)
                                    ctx.searched_queries.update(recall_vs)  # 검색 이력 기록
                                    recall_reqs = [
                                        {"query": q, "purpose": "decoder_recall_verification", "priority": 1}
                                        for q in recall_vs
                                    ]
                                    
                                    # 🏷️ 2차 리콜에서도 조합 검색 추가
                                    # (1차에볦낀거나 덈줈 근거제목+캐릭조합)
                                    _id_title_r = None
                                    # KNOWN_ABBREVIATIONS 우선
                                    for _kt_r in (_gk_titles_v + [_post_title_v]):
                                        if isinstance(_kt_r, str):
                                            import re as _re_r
                                            _kt_r_clean = _re_r.sub(r'[^\uac00-\ud7a3]', '', _kt_r)
                                            if _kt_r_clean in KNOWN_ABBREVIATIONS:
                                                _id_title_r = KNOWN_ABBREVIATIONS[_kt_r_clean]
                                                break
                                    # suspected_titles에서확인
                                    if not _id_title_r and ctx.suspected_titles:
                                        for _st_r in ctx.suspected_titles:
                                            if isinstance(_st_r, dict) and _st_r.get("title") and _st_r.get("confidence", 0) >= 0.7:
                                                _id_title_r = _st_r["title"]
                                                break
                                    if _id_title_r:
                                        _gk_chars_r = _gk_entities_v.get("possible_characters", []) or []
                                        for _char_r in _gk_chars_r[:3]:
                                            if isinstance(_char_r, str) and len(_char_r) >= 2:
                                                combo_q_r = f"{_id_title_r} {_char_r}"
                                                if combo_q_r not in ctx.searched_queries and len(combo_q_r) <= 50:
                                                    recall_reqs.append({
                                                        "query": combo_q_r,
                                                        "purpose": "title_character_verification",
                                                        "priority": 1,
                                                    })
                                                    ctx.searched_queries.add(combo_q_r)
                                                    print(f"[{_ts()}] {self.emoji} 🔑 조합 검색 추가 (2차: '{combo_q_r}'", file=sys.stderr)
                                    
                                    recall_new = self._execute_searches(recall_reqs, ctx.post_id)
                                    if recall_new:
                                        added_r = ctx.add_search_results(recall_new)
                                        print(f"[{_ts()}] {self.emoji} 🔗 추가 검색 결과 {added_r}개추가 (중복 {len(recall_new) - added_r}개제거)", file=sys.stderr)
                            
                            # ⚡2차 Decoder에서 정식 제목 미발견 시 플랫폼특정 검색 자동 추가
                            # 커뮤니티 줄임말만 나오고 공식 플랫폼URL이 없을 때 보완
                            decoder_2_conf = str(decoder_result.get("overall_confidence", "")).lower()
                            if decoder_2_conf in ("none", "low", "") and self.search_fn:
                                # Gatekeeper possible_titles에서 가장 짧은 축약어 후보 추출
                                _gk_entities = gatekeeper_out.get("detected_entities") or {}
                                gk_titles = (_gk_entities.get("possible_titles") or []) if isinstance(_gk_entities, dict) else []
                                # key_terms에서후보 추출
                                gk_terms = gatekeeper_out.get("key_terms") or []
                                abbrev_candidates = []
                                for t in (gk_titles + gk_terms):
                                    if isinstance(t, str):
                                        import re as _re2
                                        t_clean = _re2.sub(r'[^\uac00-\ud7a3]', '', t)
                                        if 2 <= len(t_clean) <= 6:  # 2~6뚯젅 축약
                                            abbrev_candidates.append(t_clean)

                                # 🏷️ Decoder best_match/suspected_titles 제목을 플랫폼검색 대상에 포함
                                for dt in (decoder_result.get("decoded_terms") or []):
                                    if not isinstance(dt, dict):
                                        continue
                                    bm = dt.get("best_match") or {}
                                    bm_title = bm.get("title")
                                    if bm_title and isinstance(bm_title, str):
                                        t_clean = _re2.sub(r'[^\uac00-\ud7a3]', '', bm_title)
                                        if 2 <= len(t_clean) <= 10:  # Decoder 제목은 더 긴 것도 허용
                                            abbrev_candidates.append(t_clean)
                                    # morphemes에서 제목 부분 morpheme도 추출
                                    morphs = dt.get("morphemes") or []
                                    for m in morphs:
                                        if isinstance(m, str):
                                            m_clean = _re2.sub(r'[^\uac00-\ud7a3]', '', m)
                                            if 2 <= len(m_clean) <= 6:
                                                abbrev_candidates.append(m_clean)
                                # ctx.suspected_titles에서추출
                                for st in ctx.suspected_titles:
                                    st_title = st.get("title", "") if isinstance(st, dict) else ""
                                    if st_title:
                                        st_clean = _re2.sub(r'[^\uac00-\ud7a3]', '', st_title)
                                        if 2 <= len(st_clean) <= 10:
                                            abbrev_candidates.append(st_clean)

                                # 중복 제거 + 상위 4개(Decoder 후보 포함으로 확장)
                                abbrev_candidates = list(dict.fromkeys(abbrev_candidates))[:4]
                                
                                if abbrev_candidates:
                                    platform_searches = []
                                    for abbr in abbrev_candidates:
                                        for platform in ("노벨피아", "문피아"):
                                            q = f"{abbr} {platform}"
                                            if q not in ctx.searched_queries:
                                                platform_searches.append({
                                                    "query": q,
                                                    "purpose": "platform_title_search",
                                                    "priority": 1,
                                                })
                                                ctx.searched_queries.add(q)
                                    if platform_searches:
                                        print(f"[{_ts()}] {self.emoji} 🔍 정식 제목 플랫폼검색{len(platform_searches)}가 {[s['query'] for s in platform_searches[:3]]}", file=sys.stderr)
                                        plat_results = self._execute_searches(platform_searches, ctx.post_id)
                                        if plat_results:
                                            added_p = ctx.add_search_results(plat_results)
                                            print(f"[{_ts()}] {self.emoji} 🔗 플랫폼검색 결과 {added_p}개추가", file=sys.stderr)
                            
                            # 3차 Decoder 실행 여부 결정
                            # (recall 검색 또는 플랫폼검색에서 새 결과가 추가되었으면 리콜
                            total_sr_count = len(ctx.search_results)
                                        
                            # ⚡2차 Decoder 추가 검색 결과 포함하여 3차 Decoder 리콜
                            # (새 검색 결과에 정식 제목이 있을 수 있음)
                            if decoder_expert:
                                # ⚡2차 Decoder 결과 기록 (급조 매칭 감지용)
                                prev_decoder_conf = str(decoder_result.get("overall_confidence", "")).lower()
                                prev_decoder_title = None
                                for dt in (decoder_result.get("decoded_terms") or []):
                                    bm = dt.get("best_match") or {}
                                    if bm.get("title"):
                                        prev_decoder_title = bm["title"]
                                        break
                                
                                # ⚡연상기호이면 3차 Decoder 실행 차단 (토큰 낭비 방지)
                                # is_association_post=true이면 1~2차에서 이미 충분한 정보를 가졌음
                                # 제목과 본문이 무관한 글에서 3차까지 급조 매칭 시도는 자원 낭비
                                _skip_3rd = getattr(ctx, 'is_association_post', False)
                                if _skip_3rd:
                                    print(
                                        f"[{_ts()}] {self.emoji} ⚡연상기호 → Decoder 3차 실행 스킵 "
                                        f"(작품매칭 강박 방지, 토큰 압축)",
                                        file=sys.stderr,
                                    )
                                
                                # 🆕 2차 Decoder가 이미 medium/high 결과를 냈으면 3차 스킵
                                # 3차 LLM 호출은 일관성이 떨어져 2차의 정답을 퇴행시키는 경향이 있음
                                # 예: '즉사무림' → 2차에서 '즉사기 들고 무림에 떨어지다'(high)를
                                #     3차에서 '즉사무림 사실상 이번편까지가 프롤로그군'(커뮤니티 글)로 교체
                                if not _skip_3rd and prev_decoder_conf in ("medium", "high") and prev_decoder_title:
                                    print(
                                        f"[{_ts()}] {self.emoji} ⚡Decoder 2차 이미 {prev_decoder_conf} 결과 → "
                                        f"3차 실행 스킵 (퇴행 방지, title='{prev_decoder_title}')",
                                        file=sys.stderr,
                                    )
                                    _skip_3rd = True
                                
                                if not _skip_3rd:
                                    print(f"[{_ts()}] {self.emoji} 🔗 1.5단계: Decoder 3차 실행 (추가 검색 결과 포함하여", file=sys.stderr)
                                
                                    # 🏷️ 3차 실행 시 context overflow 방지: search_results 축소
                                    _sr_for_3rd = ctx.search_results
                                    _sr_chars = sum(
                                        len(str(sr.get("title", ""))) + len(str(sr.get("content", "")))
                                        for sr in _sr_for_3rd
                                    )
                                    # Gatekeeper JSON + 시스템 프롬프트 + 샘플링 등 고정 비용 추정 (~30K자)
                                    _gk_json_chars = len(json.dumps(gatekeeper_out, ensure_ascii=False))
                                    _total_chars = _sr_chars + _gk_json_chars + 30000  # 고정 프롬프트 비용
                                    _MAX_TOTAL_CHARS = 55000  # ~27.5K 토큰 (모델 32K 자 제한 덉쟾 마진)
                                    
                                    if _total_chars > _MAX_TOTAL_CHARS:
                                        print(
                                            f"[{_ts()}] {self.emoji} ⚠️ 3차 실행 context 축소: "
                                            f"총 추정 {_total_chars:,}자 > {_MAX_TOTAL_CHARS:,}자 제한 "
                                            f"(SR={_sr_chars:,}, GK={_gk_json_chars:,}, 고정=30K)",
                                            file=sys.stderr,
                                        )
                                        # 1) URL 기반 중복 제거 (동일 URL 중 가장 긴 content만 유지)
                                        _url_best: Dict[str, Dict[str, Any]] = {}
                                        _no_url = []
                                        for sr in _sr_for_3rd:
                                            _u = sr.get("url", "")
                                            if _u:
                                                if _u not in _url_best or len(str(sr.get("content", ""))) > len(str(_url_best[_u].get("content", ""))):
                                                    _url_best[_u] = sr
                                            else:
                                                _no_url.append(sr)
                                        _sr_deduped = list(_url_best.values()) + _no_url
                                        
                                        # 2) content 길이 축소 (각 결과의 content를 300자로 제한)
                                        _sr_trimmed = []
                                        for sr in _sr_deduped:
                                            sr_copy = dict(sr)
                                            _content = str(sr_copy.get("content", ""))
                                            if len(_content) > 300:
                                                sr_copy["content"] = _content[:300] + "..."
                                            _sr_trimmed.append(sr_copy)
                                        
                                        # 3) 최대 20개 결과만 유지
                                        _sr_trimmed = _sr_trimmed[:20]
                                        
                                        _new_sr_chars = sum(
                                            len(str(sr.get("title", ""))) + len(str(sr.get("content", "")))
                                            for sr in _sr_trimmed
                                        )
                                        print(
                                            f"[{_ts()}] {self.emoji} context trim complete: "
                                            f"SR {len(ctx.search_results)} ({_sr_chars:,} chars) -> "
                                            f"{len(_sr_trimmed)} ({_new_sr_chars:,} chars)",
                                            file=sys.stderr,
                                        )
                                        _sr_for_3rd = _sr_trimmed
                                    
                                    _emit_monitor(
                                        "expert_phase",
                                        {
                                            "expert": "decoder",
                                            "status": "running",
                                            "recall": True,
                                            "from": "search",
                                            "reason": "additional search evidence triggers decoder recall",
                                        },
                                        post_id=ctx.post_id,
                                    )
                                    decoder_result_3 = decoder_expert.analyze(
                                        gatekeeper_out,
                                        _sr_for_3rd,
                                        rules_config.get("slang_dictionary", {}),
                                        conversation_context=ctx.get_conversation_summary(),
                                        ctx=ctx,
                                    )
                                    
                                    # ⚡Decoder 급조 매칭 방지: 1차 2차에서 null이었는데
                                    # 3차에서 갑자기 매칭하면 discourse_warning 강화
                                    # 단, 2차까지 파싱 에러(빈 결과)인 경우는 "시도된 null"이 아니므로 제외
                                    _prev_has_decoded = bool(decoder_result.get("decoded_terms"))
                                    _prev_is_parse_error = not _prev_has_decoded and prev_decoder_conf in ("", "none")
                                    if prev_decoder_conf in ("none", "low") and prev_decoder_title is None and not _prev_is_parse_error:
                                        new_conf = str(decoder_result_3.get("overall_confidence", "")).lower()
                                        if new_conf not in ("none", "low"):
                                            # 3차에서 갑자기 매칭 시도 → 신뢰도후보
                                            forced_match = False
                                            for dt3 in (decoder_result_3.get("decoded_terms") or []):
                                                bm3 = dt3.get("best_match") or {}
                                                if bm3.get("title") and bm3.get("confidence", "").lower() not in ("none", "low"):
                                                    forced_match = True
                                                    break
                                            if forced_match:
                                                print(
                                                    f"[{_ts()}] {self.emoji} ⚡Decoder 급조 매칭 감지: "
                                                    f"1차 2차 null → 3차{new_conf} → discourse_warning 강화",
                                                    file=sys.stderr
                                                )
                                                if not ctx.discourse_warning:
                                                    ctx.discourse_warning = "decoder_forced_match(3rd_attempt)"
                                                ctx.uncertainty_sources.append(
                                                    "Decoder가 1차 2차에서 매칭 실패 후 3차에서 갑자기 매칭 → 신뢰도후보"
                                                )
                                    
                                    ctx.set_expert_output(ExpertType.DECODER, decoder_result_3)
                                    _emit_monitor("expert_phase", {"expert": "decoder", "status": "done", "recall": True, "from": "search"}, post_id=ctx.post_id)
                                    
                                    # 토큰 사용
                                    llm3 = getattr(decoder_expert, 'llm', None)
                                    if llm3 and llm3.last_usage:
                                        u3 = llm3.last_usage
                                        p3 = u3.get("prompt_tokens", 0)
                                        c3 = u3.get("completion_tokens", 0)
                                        t3 = u3.get("total_tokens", p3 + c3)
                                        print(f"[{_ts()}][{self.emoji}] Decoder(3차) 토큰 사용량", file=sys.stderr)
                                        print(f"  입력: {p3:,} tokens", file=sys.stderr)
                                        print(f"  출력: {c3:,} tokens", file=sys.stderr)
                                        print(f"  총합: {t3:,} tokens", file=sys.stderr)
                                        if not hasattr(ctx, 'token_usage'):
                                            ctx.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                                        ctx.token_usage["prompt_tokens"] += p3
                                        ctx.token_usage["completion_tokens"] += c3
                                        ctx.token_usage["total_tokens"] += t3
                                    # 3차에서는 추가 검색 없음 (무한 루프 방지)
                        
                        # 2. Verifier 리콜(새 Decoder 결과로 재검증)
                        print(f"[{_ts()}] {self.emoji} 🔗 2단계: Verifier 리콜(새 Decoder 결과)", file=sys.stderr)
                        verifier_expert = self.experts.get(ExpertType.VERIFIER)
                        if verifier_expert:
                            _emit_monitor(
                                "expert_phase",
                                {
                                    "expert": "verifier",
                                    "status": "running",
                                    "recall": True,
                                    "from": "decoder",
                                    "reason": "decoder recall completed, verifier re-validation",
                                },
                                post_id=ctx.post_id,
                            )
                            verifier_result = verifier_expert.analyze(
                                ctx.post_data,
                                ctx.comments,
                                ctx.get_expert_output(ExpertType.GATEKEEPER) or {},
                                ctx.get_expert_output(ExpertType.DECODER) or {},
                                ctx.search_results,
                                conversation_context=ctx.get_conversation_summary(),
                                ctx=ctx,
                            )
                            ctx.set_expert_output(ExpertType.VERIFIER, verifier_result)
                            _emit_monitor("expert_phase", {"expert": "verifier", "status": "done", "recall": True, "from": "decoder"}, post_id=ctx.post_id)
                            result = verifier_result  # 현재 result 낅뜲댄듃
                            
                            # 토큰 사용량 출력
                            llm = getattr(verifier_expert, 'llm', None)
                            if llm and llm.last_usage:
                                usage = llm.last_usage
                                prompt_tok = usage.get("prompt_tokens", 0)
                                completion_tok = usage.get("completion_tokens", 0)
                                total_tok = usage.get("total_tokens", prompt_tok + completion_tok)
                                print(f"[{_ts()}][{self.emoji}] Verifier(리콜) 토큰 사용량", file=sys.stderr)
                                print(f"  입력: {prompt_tok:,} tokens", file=sys.stderr)
                                print(f"  출력: {completion_tok:,} tokens", file=sys.stderr)
                                print(f"  총합: {total_tok:,} tokens", file=sys.stderr)
                                if not hasattr(ctx, 'token_usage'):
                                    ctx.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                                ctx.token_usage["prompt_tokens"] += prompt_tok
                                ctx.token_usage["completion_tokens"] += completion_tok
                                ctx.token_usage["total_tokens"] += total_tok
                        
                        print(f"[{_ts()}] {self.emoji} → 전문가 리콜 완료", file=sys.stderr)
                
                # ⚡Decoder unresolved_terms 처리 (미해결 단어 자동 재검색)
                if expert_type == ExpertType.DECODER and self.search_fn:
                    unresolved = result.get("unresolved_terms", [])
                    if unresolved:
                        # needs_search=true인 미해결 단어만 필터링
                        terms_to_search = [
                            t for t in unresolved
                            if t.get("needs_search", False) and t.get("term")
                        ]
                        
                        if terms_to_search:
                            print(
                                f"[{_ts()}] {self.emoji} unresolved terms found: {len(terms_to_search)} (auto-search)",
                                file=sys.stderr,
                            )
                            for t in terms_to_search[:3]:  # 최대 3가
                                print(f"[{_ts()}] {self.emoji}    붴 '{t.get('term')}' ({t.get('possible_types', ['unknown'])})", file=sys.stderr)
                            
                            # 미해결 단어 검색 쿼리 생성
                            unresolved_searches = []
                            for t in terms_to_search[:3]:
                                term = t.get("term", "")
                                possible_types = t.get("possible_types", ["unknown"])
                                
                                # 추정 유형에 따라 검색 쿼리 조정
                                if "novel" in possible_types:
                                    unresolved_searches.append({
                                        "query": f'"{term}" 소설',
                                        "purpose": "unresolved_term_novel",
                                        "priority": 1
                                    })
                                if "author" in possible_types:
                                    unresolved_searches.append({
                                        "query": f'"{term}" 작가',
                                        "purpose": "unresolved_term_author",
                                        "priority": 1
                                    })
                                if "slang" in possible_types or "unknown" in possible_types:
                                    unresolved_searches.append({
                                        "query": f'"{term}" 뜻',
                                        "purpose": "unresolved_term_slang",
                                        "priority": 2
                                    })
                            
                            if unresolved_searches:
                                new_results = self._execute_searches(unresolved_searches, ctx.post_id)
                                if new_results:
                                    added = ctx.add_search_results(new_results)
                                    print(f"[{_ts()}] {self.emoji} 🔍 미해결 단어 검색{added}개추가", file=sys.stderr)
                                    
                                    # 미해결 단어 정보를 컨텍스트에 저장(Verifier에서 활용)
                                    if not hasattr(ctx, 'unresolved_terms_info'):
                                        ctx.unresolved_terms_info = []
                                    ctx.unresolved_terms_info.extend(terms_to_search[:3])
                
                # ⚡Decoder confidence가 낮으면 자동으로 핵심 단어 추가 검색
                if expert_type == ExpertType.DECODER and self.search_fn:
                    overall_conf = str(result.get("overall_confidence", "")).lower()
                    has_verification = bool(result.get("verification_search"))
                    
                    # confidence가 low/none이고 verification_search를 요청하지 않은 경우
                    if overall_conf in ("low", "none") and not has_verification:
                        # decoded_terms에서 핵심 단어 추출
                        # (1) 원래 단어 (original) 그대로 사용 → kiwipiepy가 커뮤니티 축약어를 이미 더 분석 못하므로
                        # (2) 형태소 분석 결과를 보조적으로 사용
                        key_terms = []
                        for dt in (result.get("decoded_terms") or []):
                            original = dt.get("original", "").strip()
                            import re as _re_auto
                            original_clean = _re_auto.sub(r'[^\uac00-\ud7a3a-zA-Z0-9]', '', original)
                            # 원래 단어 우선 추가 (2글자 이상)
                            if len(original_clean) >= 2 and original_clean not in key_terms:
                                key_terms.append(original_clean)
                            # 형태분석으로 명사 추출 (보조)
                            nouns = _extract_nouns(original)
                            for noun in nouns:
                                if noun not in key_terms and noun != original_clean:
                                    key_terms.append(noun)
                        
                        # 핵심 단어로 추가 검색 수행: 소설류 + 플랫폼검색
                        if key_terms:
                            print(f"[{_ts()}] {self.emoji} 🔍 Decoder confidence={overall_conf} → 자동 추가 검색(단어: {key_terms[:3]})", file=sys.stderr)
                            auto_searches = []
                            for term in key_terms[:3]:  # 최대 3개 단어
                                auto_searches.append({
                                    "query": f"{term} 소설",
                                    "purpose": "auto_verification",
                                    "priority": 1
                                })
                                # 플랫폼특정 검색도 추가
                                for platform in ("노벨피아", "문피아"):
                                    q = f"{term} {platform}"
                                    if q not in ctx.searched_queries:
                                        auto_searches.append({
                                            "query": q,
                                            "purpose": "auto_platform_verification",
                                            "priority": 2
                                        })
                                        ctx.searched_queries.add(q)
                            new_results = self._execute_searches(auto_searches, ctx.post_id)
                            if new_results:
                                added = ctx.add_search_results(new_results)
                                print(f"[{_ts()}] {self.emoji} 🔍 자동 검색{added}개추가", file=sys.stderr)
                                # 새 검색 결과로 Decoder 리콜
                                print(f"[{_ts()}] {self.emoji} additional results -> decoder recall", file=sys.stderr)
                                result = self._call_expert(expert_type, ctx, rules_config)
                
                # 전문가가 다른 전문가 요청있는지 확인 (Agentic 협력)
                requested = result.get("request_expert")
                if requested and isinstance(requested, str) and requested.lower() not in ("none", "null", ""):
                    reason = result.get("request_reason", "추가 분석 필요")
                    question = (result.get("request_context") or {}).get("question", "")
                    
                    try:
                        to_expert = ExpertType(requested)
                    except ValueError:
                        print(
                            f"[{_ts()}] {self.emoji} ⚠️ 존재하지 않는 전문가 유형 무시: '{requested}'",
                            file=sys.stderr,
                        )
                        to_expert = None
                    
                    if to_expert:
                        ctx.add_message(ExpertMessage(
                            from_expert=expert_type,
                            to_expert=to_expert,
                            message_type="request",
                            content={"reason": reason, "context": result.get("request_context", {})},
                        ))
                        print(f"[{_ts()}] {self.emoji} ➡️ {expert_type.value} 의 {requested} 협력 요청", file=sys.stderr)
                        print(f"[{_ts()}] {self.emoji}    └ 이유: {reason}", file=sys.stderr)
                        if question:
                            print(f"[{_ts()}] {self.emoji}    └ 질문: {question[:100]}", file=sys.stderr)
            
            elif next_action["action"] == "search":
                query = next_action.get("query", "")
                if query and self.search_fn:
                    new_results = self._execute_searches(
                        [{"query": query, "purpose": "refinement", "priority": 1}],
                        ctx.post_id
                    )
                    ctx.add_search_results(new_results)
            
            elif next_action["action"] == "finalize":
                print(f"[{_ts()}] {self.emoji} 종료 조건 충족 → Arbiter 실행", file=sys.stderr)
                break
        
        # Phase 3.5: Synthesizer (증거 기반 재해석)
        # 모든 전문가 분석 완료 후, 축적된 증거로 원문을 재해석
        if ExpertType.SYNTHESIZER in self.experts:
            # 스킵 조건: Fast-Path noise이거나, Gatekeeper/Verifier가 명확히 noise 판정
            _skip_synth = False
            _gk_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
            _vf_out = ctx.get_expert_output(ExpertType.VERIFIER) or {}
            _dc_out = ctx.get_expert_output(ExpertType.DECODER) or {}
            _vf_result = _vf_out.get("verification_result", {}) or {}
            
            # Gatekeeper noise + Decoder 미실행 → 명백한 noise, 재해석 불필요
            if _gk_out.get("is_noise") and not _dc_out:
                _skip_synth = True
                print(f"[{_ts()}] {self.emoji} 🔬 Synthesizer 스킵: Gatekeeper noise + Decoder 미실행", file=sys.stderr)
            
            # Decoder confidence=None + Verifier is_relevant=False → 작품 미식별, 재해석 불필요
            if not _skip_synth:
                _dc_conf = str(_dc_out.get("overall_confidence", "")).lower()
                if _dc_conf in ("none", "") and _vf_result.get("is_relevant") is False:
                    _skip_synth = True
                    print(f"[{_ts()}] {self.emoji} 🔬 Synthesizer 스킵: Decoder none + Verifier irrelevant", file=sys.stderr)
            
            if not _skip_synth:
                print(f"[{_ts()}] {self.emoji} 🔬 Synthesizer: 증거 기반 재해석 시작", file=sys.stderr)
                self._call_expert(ExpertType.SYNTHESIZER, ctx, rules_config)
            else:
                print(f"[{_ts()}] {self.emoji} 🔬 Synthesizer 스킵됨", file=sys.stderr)
                _emit_monitor("expert_phase", {"expert": "synthesizer", "status": "done", "skipped": True}, post_id=ctx.post_id)
        
        # Phase 4: Final Arbiter
        if ExpertType.ARBITER in self.experts:
            self._call_expert(ExpertType.ARBITER, ctx, rules_config)
        
        print(f"\n[{_ts()}] {self.emoji} Orchestrator 완료: {ctx.iteration} iterations", file=sys.stderr)
        self._last_ctx = ctx
        return ctx
    
    def _call_expert(
        self,
        expert_type: ExpertType,
        ctx: ConversationContext,
        rules_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call an expert and persist result into the shared context."""
        expert = self.experts.get(expert_type)
        if not expert:
            print(f"[{_ts()}] {self.emoji} ⚠️ {expert_type.value} 전문가 없음", file=sys.stderr)
            return {}
        
        # 뱤 이벤 전문가 단계 시작
        _emit_monitor("expert_phase", {"expert": expert_type.value, "status": "running", "from": getattr(self, '_prev_expert', '')}, post_id=ctx.post_id)
        self._prev_expert = expert_type.value
        
        # 토큰 사용량 추적 시작 - LLM이 마지막 사용량 기록
        llm = getattr(expert, 'llm', None)
        if llm:
            prev_usage = llm.last_usage.copy() if llm.last_usage else None
        else:
            prev_usage = None
        
        try:
            # post_data, comments None 체크
            post_data = ctx.post_data or {}
            comments = ctx.comments or []

            # 토큰 압축: CONVERSATION HISTORY에 기본 compact 사용 (환경변수로 opt-out 가능)
            use_compact_ctx = os.getenv("LLM_CONTEXT_COMPACT", "1") != "0"
            conv_summary = ctx.get_conversation_summary(compact=use_compact_ctx)
             
            # 전문가별 실행 방식
            if expert_type == ExpertType.GATEKEEPER:
                result = expert.analyze(post_data, comments, rules_config, ctx=ctx)
            elif expert_type == ExpertType.DISCOURSE:
                result = expert.analyze(post_data, comments)
            elif expert_type == ExpertType.DECODER:
                gatekeeper_out = ctx.get_expert_output(ExpertType.GATEKEEPER) or {}
                result = expert.analyze(
                    gatekeeper_out,
                    ctx.search_results or [],
                    rules_config.get("slang_dictionary", {}),
                    conversation_context=conv_summary,
                    ctx=ctx,  # suspected_titles initialization/update context
                )
            elif expert_type == ExpertType.VERIFIER:
                # 토큰 다이어트: Decoder가 실제 사용한 검색 결과만 전달
                # Decoder의 decoded_terms에서 사용된 URL 추출
                search_results = ctx.search_results or []
                decoder_output = ctx.get_expert_output(ExpertType.DECODER) or {}
                decoded_terms = decoder_output.get("decoded_terms") or []
                
                # Decoder가 참조한 URL 수집
                used_urls = set()
                for term in decoded_terms:
                    best_match = term.get("best_match", {})
                    if best_match and best_match.get("url"):
                        used_urls.add(best_match["url"])
                    # supporting_evidence에서URL 가졌
                    for evidence in term.get("supporting_evidence", []):
                        if evidence.get("url"):
                            used_urls.add(evidence["url"])
                
                # 사용된 결과만 필터링 + 상위 8개 제한 (중복 제거)
                if used_urls:
                    limited_search = [r for r in search_results if r.get("url") in used_urls][:8]
                else:
                    # Decoder가 아무것도 사용하지 않았으면 상위 5개만 전달
                    limited_search = search_results[:5]
                
                result = expert.analyze(
                    post_data,
                    comments,
                    ctx.get_expert_output(ExpertType.GATEKEEPER) or {},
                    decoder_output,
                    limited_search,
                    conversation_context=conv_summary,
                    ctx=ctx,
                )
            elif expert_type == ExpertType.CRITIC:
                result = expert.analyze(
                    post_data,
                    comments,
                    ctx.get_expert_output(ExpertType.VERIFIER) or {},
                    conversation_context=conv_summary,
                    ctx=ctx,
                )
            elif expert_type == ExpertType.SYNTHESIZER:
                result = expert.analyze(ctx)
            elif expert_type == ExpertType.ARBITER:
                result = expert.analyze(ctx)
            else:
                result = {}
            
            # 토큰 사용량 출력
            if llm and llm.last_usage:
                usage = llm.last_usage
                prompt_tok = usage.get("prompt_tokens", 0)
                completion_tok = usage.get("completion_tokens", 0)
                total_tok = usage.get("total_tokens", prompt_tok + completion_tok)
                
                print(f"[{_ts()}][{self.emoji}] {expert_type.value} 토큰 사용", file=sys.stderr)
                print(f"  입력: {prompt_tok:,} tokens", file=sys.stderr)
                print(f"  출력: {completion_tok:,} tokens", file=sys.stderr)
                print(f"  총합: {total_tok:,} tokens", file=sys.stderr)
                
                # 컨텍스트에 토큰 사용량 축적
                if not hasattr(ctx, 'token_usage'):
                    ctx.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                ctx.token_usage["prompt_tokens"] += prompt_tok
                ctx.token_usage["completion_tokens"] += completion_tok
                ctx.token_usage["total_tokens"] += total_tok
            
            # ⚡ Fix: 협력 Gatekeeper 리콜 시 key_terms/detected_entities 병합
            # 2차 GK 결과가 1차보다 빈약하거나 누락되면 1차의 key_terms/entities가 유실됨
            if expert_type == ExpertType.GATEKEEPER:
                prev_gk = ctx.get_expert_output(ExpertType.GATEKEEPER)
                if prev_gk and isinstance(prev_gk, dict) and isinstance(result, dict):
                    # key_terms 병합 (순서 유지 중복 제거)
                    prev_kt = prev_gk.get("key_terms") or []
                    new_kt = result.get("key_terms") or []
                    merged_kt = list(dict.fromkeys(new_kt + prev_kt))  # 새 검색 우선, 기존 보충
                    result["key_terms"] = merged_kt
                    # detected_entities 병합
                    prev_ent = prev_gk.get("detected_entities") or {}
                    new_ent = result.get("detected_entities") or {}
                    for ent_key in ("possible_titles", "possible_authors", "possible_characters"):
                        prev_list = prev_ent.get(ent_key) or []
                        new_list = new_ent.get(ent_key) or []
                        merged = list(dict.fromkeys(new_list + prev_list))
                        if not new_ent:
                            result["detected_entities"] = {}
                            new_ent = result["detected_entities"]
                        new_ent[ent_key] = merged
            
            # 결과 저장
            ctx.set_expert_output(expert_type, result)
            ctx.add_message(ExpertMessage(
                from_expert=expert_type,
                to_expert=None,
                message_type="analysis",
                content=result,
            ))
            
            # 뱤 이벤 전문가 단계 완료
            _emit_monitor("expert_phase", {"expert": expert_type.value, "status": "done"}, post_id=ctx.post_id)
            
            return result
            
        except Exception as e:
            import traceback
            print(f"[{_ts()}] {self.emoji} ⚠️ {expert_type.value} 에러: {e}", file=sys.stderr)
            print(f"[{_ts()}] {self.emoji} 📋 Traceback:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            error_result = {"error": str(e)}
            # 에러 결과도 저장하여 다른 전문가가 상황 파악하도록
            ctx.set_expert_output(expert_type, error_result)
            return error_result
    
    def _decide_next_action(
        self,
        ctx: ConversationContext,
        rules_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Decide next orchestrator action for the current iteration.

        Priority:
        1) Process valid expert-to-expert collaboration requests.
        2) Trigger targeted search when evidence is insufficient.
        3) Finalize when stop conditions are satisfied.

        Returns:
            {"action": "call_expert|search|finalize", ...}
        """
        gk = ctx.get_expert_output(ExpertType.GATEKEEPER)
        dc = ctx.get_expert_output(ExpertType.DECODER)
        vf = ctx.get_expert_output(ExpertType.VERIFIER)
        cr = ctx.get_expert_output(ExpertType.CRITIC)
        
        # 전체 협력 횟수 추적
        total_collaborations = getattr(ctx, '_total_collaborations', 0)
        MAX_TOTAL_COLLABORATIONS = 3  # 전체 협력 최대 3회
        
        # === 1. Expert 협력 요청 처리 (횟수 제한) ===
        for expert_type in [ExpertType.VERIFIER, ExpertType.DECODER, ExpertType.GATEKEEPER]:
            output = ctx.get_expert_output(expert_type)
            if output and output.get("request_expert"):
                requested = output["request_expert"]
                reason = output.get("request_reason", "협력 요청")
                request_context = output.get("request_context") or {}
                question = request_context.get("question", "")
                
                # ⚡협력 요청 필드 즉시 클리어(무한 루프 방지)
                output["request_expert"] = None
                output["request_reason"] = None
                output["request_context"] = None
                
                # 이미 처리요청몄 확인
                request_key = f"{expert_type.value}::{requested}"
                processed_requests = getattr(ctx, '_processed_requests', set())
                
                # ⚡전체 협력 횟수 초과 시 무시
                if total_collaborations >= MAX_TOTAL_COLLABORATIONS:
                    print(f"[{_ts()}] {self.emoji} 🚫 협력 요청 무시 (전체 {total_collaborations}전달): {request_key}", file=sys.stderr)
                    continue
                
                # ⚡같은 유형의 협력은 1번만
                if request_key in processed_requests:
                    print(f"[{_ts()}] {self.emoji} collaboration request ignored (already processed): {request_key}", file=sys.stderr)
                    continue
                
                print(f"[{_ts()}] {self.emoji} 🔄 협력 요청 ({total_collaborations+1}/{MAX_TOTAL_COLLABORATIONS}): {request_key}", file=sys.stderr)
                print(f"[{_ts()}] {self.emoji}    이유: {reason}", file=sys.stderr)
                if question:
                    print(f"[{_ts()}] {self.emoji}    질문: {question[:100]}", file=sys.stderr)
                
                # 협력 처리 기록
                ctx._processed_requests = processed_requests | {request_key}
                ctx._total_collaborations = total_collaborations + 1
                
                return {"action": "call_expert", "expert": requested, "collaboration": True}
        
        # 메시지 기반 요청 확인은 제거 (위 로직으로 충분)
        
        # === 2. 순차 진행 ===
        if dc and not vf:
            return {"action": "call_expert", "expert": "verifier"}
        
        # Critic은 is_relevant=True 때만 실행
        if vf and not cr:
            # 에러 결과 무시
            if "error" in vf:
                print(f"[{_ts()}] {self.emoji} ⚠️ Verifier 에러로 인해 Critic 실행 스킵", file=sys.stderr)
            else:
                vf_result = vf.get("verification_result", {})
                if vf_result and vf_result.get("is_relevant"):
                    return {"action": "call_expert", "expert": "critic"}
        
        # === 3. 쒖감 실행 (꾩쭅 실행 전문가) ===
        if not dc and gk:
            return {"action": "call_expert", "expert": "decoder"}
        
        # === 4. 모든 전문가 완료 종료 ===
        # is_relevant=False면 Critic 없이도 종료 가능
        if gk and dc and vf:
            # 에러 결과면 즉시 종료
            if "error" in vf:
                return {"action": "finalize"}
            
            vf_result = vf.get("verification_result", {})
            if not vf_result or not vf_result.get("is_relevant"):
                # is_relevant=False이면 Critic 불필
                return {"action": "finalize"}
            elif cr:
                # is_relevant=True이고 Critic완료
                return {"action": "finalize"}
        
        # 5. 최대 반복 전달
        if ctx.iteration >= ctx.max_iterations:
            return {"action": "finalize"}
        
        return {"action": "finalize"}
    
    def _prioritize_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """검색 결과 우선순위 재정렬
        
        우선순위:
        1. 공식 플랫폼 URL (munpia, novelpia, naver, kakao 등)
        2. 작가 패턴 포함 ("[작가명] 작가의 대표작")
        3. 커뮤니티 포럼 (fmkorea, dcinside, arca 등)
        4. 기타
        """
        def get_priority(result: Dict[str, Any]) -> int:
            url = str(result.get("url", "")).lower()
            content = result.get("content", "")
            title = result.get("title", "")
            
            # 1순위: 공식 플랫폼
            if any(platform in url for platform in OFFICIAL_PLATFORMS):
                # 작가 패턴있으면믪 우선순위
                if "작가" in content or "작가" in title:
                    return 0  # 최우
                return 1
            
            # 2순위: 작가 패턴 포함
            if "작가의 대표작" in content or "작가가 쓴" in content or "작가" in content:
                return 2
            
            # 3순위: 커뮤니티 포럼
            community_sites = [
                "fmkorea.com", "dcinside.com", "arca.live",
                "ruliweb.com", "clien.net"
            ]
            if any(site in url for site in community_sites):
                return 3
            
            # 4순위: 기타
            return 4
        
        # 우선순위로 정렬 (작은 글자가 우선)
        return sorted(results, key=get_priority)
    
    def _is_relevant_result(self, result: Dict[str, Any], query: str) -> bool:
        """검색 결과가 현재 쿼리와 충분히 관련 있는지 판단"""
        url = str(result.get("url", "")).lower()
        title = str(result.get("title", "")).lower()
        content = str(result.get("content", "")).lower()
        text = title + " " + content

        query_words = [w.strip().lower() for w in query.replace('"', "").split() if len(w.strip()) >= 2]
        query_norm = self._normalize_hint_text(query)
        text_norm = self._normalize_hint_text(text)
        url_norm = self._normalize_hint_text(url)

        # 1) 명확히 무관한 도메인 제외
        irrelevant_domains = [
            "huggingface.co", "github.com", "scribd.com",
            "wikipedia.org", "wikisource.org", "wiktionary.org",
            "youtube.com", "twitter.com", "facebook.com",
            "instagram.com", "tiktok.com",
            ".pdf", ".txt", ".csv", ".json",
            "adversec.com", "snuaa.org", "cau.ac.kr", "kitla.or.kr",
            "nl.go.kr",
        ]
        if any(domain in url for domain in irrelevant_domains):
            return False

        # 2) 공식 플랫폼은 우선 통과
        high_trust_domains = [
            "munpia.com", "novelpia.com", "joara.com", "ridibooks.com",
            "kakaopage.com", "series.naver.com", "bookcube.com",
        ]
        if any(domain in url for domain in high_trust_domains):
            return True

        # 3) 커뮤니티/위키는 쿼리와의 겹침이 있을 때만 통과
        medium_trust_domains = [
            "dcinside.com", "fmkorea.com", "arca.live", "ruliweb.com", "namu.wiki",
        ]
        if any(domain in url for domain in medium_trust_domains):
            query_overlap = any(word and (word in title or word in content) for word in query_words)
            norm_overlap = bool(query_norm and (query_norm in text_norm or query_norm in url_norm))
            token_overlap = False
            for word in query_words:
                word_norm = self._normalize_hint_text(word)
                if len(word_norm) >= 2 and (word_norm in text_norm or word_norm in url_norm):
                    token_overlap = True
                    break
            return bool(query_overlap or norm_overlap or token_overlap)

        # 4) 텍스트 기반 보조 판단
        novel_keywords = [
            "소설", "웹소설", "웹툰", "작가", "연재", "완결",
            "문피아", "노벨피아", "로판", "판타지", "장르", "빙의",
            "리뷰", "추천", "스포", "독자",
        ]
        if any(kw in text for kw in novel_keywords):
            return True

        # 5) 쿼리 단어가 제목에 있으면 통과
        for word in query_words:
            if len(word) >= 2 and word in title:
                return True

        return False

    # ========================================================================
    # 🔬 Deep Search: snippet 분석 + URL 페치 + 은어/작가 추가 검색
    # ========================================================================
    
    # snippet에서 제목/작가/약칭 후보를 미리 추출해 LLM 기반 분석을 보강
    _SNIPPET_TERM_CHAR = r"\uac00-\ud7a3A-Za-z0-9"
    _SNIPPET_TITLE_TERM_CLASS = rf"[{_SNIPPET_TERM_CHAR}]"
    _SNIPPET_TITLE_TERM_SPACE_CLASS = rf"[{_SNIPPET_TERM_CHAR}\s]"
    _SNIPPET_TITLE_TERM_UNDER_CLASS = rf"[{_SNIPPET_TERM_CHAR}_]"
    _SNIPPET_WORK_TAG = rf"(?:\uc791\ud488|\uc18c\uc124|\uc6f9\uc18c\uc124|\uc2dc\ub9ac\uc988|\uc5f0\uc7ac)"
    _SNIPPET_WORK_TAG_SIMPLE = rf"(?:\uc791\ud488|\uc18c\uc124|\uc2dc\ub9ac\uc988)"
    _SNIPPET_TITLE_PATTERNS = [
        re.compile(
            r'(?:^|[\s"\',;.!?])({term}{{2,20}}(?:\s{term}{{1,10}}){{0,5}})(?:\s+{work_tag})'.format(
                term=_SNIPPET_TITLE_TERM_CLASS,
                work_tag=_SNIPPET_WORK_TAG,
            ),
            re.UNICODE,
        ),
        re.compile(
            r'["\']?({term_space}{{2,40}})["\']?(?:\s*\(?\s*{work_tag_simple}\s*\)?)'.format(
                term_space=_SNIPPET_TITLE_TERM_SPACE_CLASS,
                work_tag_simple=_SNIPPET_WORK_TAG_SIMPLE,
            ),
            re.UNICODE,
        ),
        re.compile(
            r'(?:{work_tag})\s*[:]?\s*["\']?({term_space}{{2,40}})["\']?'.format(
                work_tag=_SNIPPET_WORK_TAG,
                term_space=_SNIPPET_TITLE_TERM_SPACE_CLASS,
            ),
            re.UNICODE,
        ),
        re.compile(
            r'({term_under}{{2,15}}),?\s+({term_under}{{2,8}}(?:\s{term_under}{{1,8}}){{0,6}})(?:\s*\.)?'.format(
                term_under=_SNIPPET_TITLE_TERM_UNDER_CLASS,
            ),
            re.UNICODE,
        ),
    ]
    _SNIPPET_AUTHOR_PATTERNS = [
        # "~ 작가곕퇃대표작/작품"
        re.compile(
            r'["\']?({_author_term}{{2,15}})["\']?\s*{author}\s*(?:{best}|{novel}|{serial})?'.format(
                _author_term=_SNIPPET_TITLE_TERM_UNDER_CLASS,
                author=r"\uc791\uac00",
                best=r"\ub300\ud45c\uc791",
                novel=r"\uc791\ud488",
                serial=r"\uc5f0\uc7ac\uc791",
            ),
            re.UNICODE,
        ),
        # "작가명 ~", "작가의 ~"
        re.compile(
            r'{author}(?:\uba85)?\s+["\']?({_author_term}{{2,15}})["\']?'.format(
                author=r"\uc791\uac00",
                _author_term=_SNIPPET_TITLE_TERM_UNDER_CLASS,
            ),
            re.UNICODE,
        ),
        # "~ 작가 꾨챸"
        re.compile(
            r'({_author_term}{{2,15}})\s*{author}\s*{penname}'.format(
                _author_term=_SNIPPET_TITLE_TERM_UNDER_CLASS,
                author=r"\uc791\uac00",
                penname=r"\ud544\uba85",
            ),
            re.UNICODE,
        ),
        # "~ 작가 ~대표작 최고의 필력" 등 커뮤니티에서 "?ㅻ뒛필요 작가 최고 사용
        re.compile(
            r'(?:^|[\s])({_author_term}{{2,15}})\s+{author}\s+(?:{best}|{author}|{serial})'.format(
                _author_term=_SNIPPET_TITLE_TERM_UNDER_CLASS,
                author=r"\uc791\uac00",
                best=r"\ucd5c\uace0",
                serial=r"\uc5f0\uc7ac",
            ),
            re.UNICODE,
        ),
        # "X작가 Y" 붙여곌린 ("즉사무림작가" 줄임+작가 분리)
        re.compile(
            r'({_author_term}{{2,10}}){author}(?:[{kr}])?'.format(
                _author_term=_SNIPPET_TITLE_TERM_UNDER_CLASS,
                author=r"\uc791\uac00",
                kr=_SNIPPET_TERM_CHAR,
            ),
            re.UNICODE,
        ),
        # "?ㅻ뒛필요 총 53화' 등 문피아 검색결과에서 작가명 추출
        re.compile(
            r'(?:^|[\s])({_author_term}{{2,10}})\s+{cnt}\s+\d+\s*{chapter}'.format(
                _author_term=_SNIPPET_TITLE_TERM_UNDER_CLASS,
                cnt=r"\ucd1d",
                chapter=r"\ud654",
            ),
            re.UNICODE,
        ),
    ]
    
    # 공식 소설플랫폼도메
    _OFFICIAL_PLATFORM_DOMAINS = {
        "novelpia.com", "munpia.com", "mm.munpia.com", "m.munpia.com",
        "series.naver.com", "ridibooks.com", "kakaopage.com",
        "joara.com", "bookcube.com",
    }
    
    def _llm_analyze_snippets(
        self,
        post_data: Dict[str, Any],
        key_terms: List[str],
        search_results: List[Dict[str, Any]],
        gatekeeper_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """📌 검색 결과 snippet들을 LLM에 보내고, 게시글과 관련된 정보를 판별한다.

        기계적 정규식(`_extract_hints_from_snippets`)은 문맥을 모르기 때문에
        '즉사기하고 게임 형식으로' 작가(갸올)와 '즉사기하고 무림에 떨어졌다' 작가를
        구분하지 못한다. LLM이 snippet 문맥을 보고 게시글에 해당하는 작품/작가만
        골라낸다.

        Returns:
            {
                "identified_title": str | None,  # 이 게시글에 해당하는 정식 제목
                "identified_author": str | None,  # 해당 작품의 작가
                "relevant_authors": [str],        # 관련작가 목록
                "irrelevant_authors": [str],      # 무관작가 (다른 작품)
                "abbreviation_mappings": [{"abbrev": str, "full": str}],
                "relevant_characters": [str],     # 해당 작품등장캐릭터
            }
            또는 LLM 실행 실패 시 None
        """
        # LLM 객체 획득 (Gatekeeper의 LLM 빌림)
        llm = None
        for expert_type in (ExpertType.GATEKEEPER, ExpertType.DECODER, ExpertType.VERIFIER):
            expert = self.experts.get(expert_type)
            if expert and hasattr(expert, 'llm'):
                llm = expert.llm
                break
        if not llm:
            return None

        # ── snippet 요약 텍스트 구성 (토큰 압축: 제목+내용 핵심만) ──
        snippet_lines = []
        for i, sr in enumerate(search_results[:15], 1):  # 최대 15건
            title = (sr.get("title") or "")[:80]
            content = (sr.get("content") or "")[:200].replace("\n", " ")
            snippet_lines.append(f"[{i}] {title}\n    {content}")
        if not snippet_lines:
            return None
        snippets_text = "\n".join(snippet_lines)

        # ── 게시글 핵심 정보 정리 ──
        post_title = post_data.get("title", "")
        content_texts = []
        for block in post_data.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        post_body = " / ".join(content_texts[:5])[:300]

        entities = gatekeeper_result.get("detected_entities") or {}
        gk_chars = ", ".join(entities.get("possible_characters") or [])
        gk_titles = ", ".join(entities.get("possible_titles") or [])

        system_msg = (
            "당신은 소설형 커뮤니티 검색 결과 분석 전문가입니다. "
            "게시글과 검색 결과 snippet들을 꼼꼼히 보내고, 이 게시글에 해당하는 특정 작품과"
            "관련된 정보만 정확히 근거하세요. "
            "동명의 다른 시리즈나 무관한 작품의 정보를 혼동하지 마세요. "
            "snippet에 정식 제목이나 작가명이 등장하면 반드시 추출하세요\n\n"
            "⚠️ 중요: 검색 결과가 소설이 아닌 다른 매체(VOCALOID 곡, 애니메이션, 게임, 만화, 영화 등)를"
            "가리키는 경우, 함부로 소설로 매칭하지 마세요. "
            "검색 결과 다수가 특정 비소설 매체를 가리키면 identified_category에 그 매체를 기입하고, "
            "identified_title/identified_author를 null로 놓으세요. "
            "예: 검색 결과 6건이 VOCALOID 곡을 가리키고 1건이 AA작품을 가리키면 →"
            "다수를 따라 identified_category='vocaloid_song'으로 판단하세요\n\n"
            "⚠️ 가중요: 게시글이 '장르/트로프 일반론'인지 '특정 작품 언급'인지 반드시 먼저 판별하세요\n"
            "검색에서 의심스럽게 매칭하는 소설을 발견하더라도, 게시글 자체가 그 소설을 언급하는지 확인해야 합니다\n\n"
            "⚠️ [인수] 인터넷유행반줄임말확인:\n"
            "검색 결과에서 특정 단어가 '~의 줄임말', '~류', 'MZ세대 유행어', '인터넷 유행어' 형식으로"
            "언급하는 경우, 그 단어는 작가명이나 작품명이 아니라 **범용적 한국어 표현**입니다.\n"
            "예: '감다' → 검색 결과 '감이 다 없어졌네의 줄임말' → 비유적 표현이지 작가명이 아님!\n"
            "    '작가 감다' 미쳤고' = '작가(의) 감각이 다 없어져서 미쳤다는 칭찬 표현\n"
            "이런 경우 identified_author에 해당 유행어를 작가명으로 넣지 마세요\n\n"
            "장르 일반론 판별 기준 (하나라도 해당 시 identified_category='genre_discussion'):\n"
            "- 게시글 제목의 주제어가 특정 작품의 고유명사가 아니라 장르/트로프를 다루는 일반 개념인 경우\n"
            "- 제목이 '[일반 개념]/[일반 서식]' 구조인 경우\n"
            "- 본문에 작품 고유 정보(캐릭터 고유명, 줄거리, 작가명, 화/감상)가 없고 장르 일반론만 있음\n"
            "- 복수 일반 표현 사용: '~하는 소설', '~하는 작가', '~구조' 등\n"
            "- 의심어가 장르 자체를 다루는 일반 개념으로 사용됨(고유명사가 아님)\n"
            "- 커뮤니티 관용 말머리나 카테고리 표시 말머리이고 작품명이 아님\n\n"
            "이 판별은 검색 결과 분석보다 선행해야 합니다. "
            "게시글이 장르 일반론이면, 검색에서 동명의 소설을 찾더라도 매칭하지 마세요\n\n"
            "⚠️ 주의: 검색 결과에서 게시글 의심어가 특정 작품의 '줄임/줄임말'로 확인되거나, "
            "본문에 특정 캐릭터 고유명이 등장하면, 그것은 장르 일반론이 아니라 특정 작품 언급입니다. "
            "줄임 여부를 검색 결과에서 반드시 확인하세요"
        )

        user_msg = f"""## 게시글
제목: {post_title}
본문: {post_body}
Gatekeeper 추정 제목: {gk_titles}
Gatekeeper 추정 캐릭터: {gk_chars}
핵심 단어: {', '.join(str(t) for t in key_terms[:6])}

## 검색 결과 snippets
{snippets_text}

## 분석 지시
위 검색 결과 snippet들을 꼼꼼히 보고 아래 JSON을 출력하세요.

중요 규칙:
0. **[최우 post_intent_analysis: 게시글 제목과본문먼저 분석섏뿬, 글'특정 작품 언급'몄 '장르/트로프일반로몄 판별하세**
   판별 방법:
   - 제목에서 주제어를 추출 후 그것이 특정 작품의 고유명사인지, 장르/트로프 일반 개념인지
   - 본문작품 고유 정보(캐릭고유명 구체줄거리 작가명 화감 번호)가 있는가
   - 제목이 "[일반 개념]/[일반론적 서식]" 구조인 경우
   - 제목 첫머리에 커뮤니티 관용 말머리나 카테고리 표시인지 (작품명이 아님)
   장르 일반론이면post_intent="genre_discussion", identified_category="genre_discussion"으로 설정
   특정 작품 언급이면 post_intent="work_discussion"

   **⚠️ genre_discussion 판정 인수 확인:**
   검색 결과에서 게시글의 핵심 의심어가 특정 작품의 줄임/줄임말로 확인된다면, 장르 일반론이 아니라 특정 작품 언급입니다
   예: 검색 결과가 "A"라는 의심어를 "B라는 소설의 줄임"이라고 언급하면 → post_intent="work_discussion"
   또한: 본문/댓글에 특정 캐릭터 이름이 등장하면 특정 작품에 해당하는 것이므로 genre_discussion이 아님을 유의하라.
1. identified_title: snippet에서 이 게시글에 해당하는 작품의 "정식 제목"을 찾으세요. **만약 post_intent가 "genre_discussion"이면 identified_title=null로 놓으세요.** 검색에서 의심스럽게 이름이 겹치는 소설을 찾더라도, 게시글이 그 소설을 직접 언급하는 것이 아니면 매칭하지 마세요
2. identified_author: snippet에서 "~작가", "작가: ~", "~ 작가 작품" 형식의 패턴으로 작가명을 찾으세요. 해당 작품의 작가만 기입하세요
3. irrelevant_authors: 동명 시리즈의 다른 작가(예: "즉사기하고 게임 형식으로"의 작가와 "즉사기하고 무림에 떨어졌다"의 작가는 다름)를 반드시 구분하세요
4. abbreviation_mappings: 커뮤니티에서 사용하는 작품 줄임말과 정식 제목 매핑만 기입하세요. 게시글 제목의 문법적 축약(예: "아깝긴하지만 아까움이 길지만")은 줄임이 아닙니다.
5. relevant_characters: 작품에 등장하는 캐릭터명만 기입하세요
6. identified_category: **먼저 post_intent를 확인하세요**
   - post_intent가 "genre_discussion"이면: "genre_discussion" (장르/트로프일반로
   - 소설이면, "web_novel"
   - VOCALOID 곡이면 "vocaloid_song"
   - 애니메이션이면, "anime"
   - 만화/뱁댆이면: "manga"
   - 게임이면: "game"
   - AA작품이면: "aa_work"
   - 판단 불가: "unknown"

{{
  "post_intent": "work_discussion | genre_discussion",
  "post_intent_reason": "판별 근거 (한국어 최대 100자)",
  "identified_title": "정식 제목 (work_discussion이고 소설인 경우만, 그 외 null)",
  "identified_author": "작가명(소설인 경우만, 비소설이면 null)",
  "identified_category": "web_novel | genre_discussion | vocaloid_song | anime | manga | game | aa_work | unknown",
  "relevant_authors": ["이 작품 관련 작가명],
  "irrelevant_authors": ["snippet에 등장하지만 이 게시글 작품과 무관한 작가명],
  "abbreviation_mappings": [{{"abbrev": "커뮤니티 줄임", "full": "정식 제목"}}],
  "relevant_characters": ["등장 캐릭터명]
}}"""

        try:
            from .utils import parse_json_with_think_removal
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]
            response_text = llm._stream_chat_http(
                messages=messages,
                tag="snippet_analyzer",
                use_grammar=True,
            )
            result = parse_json_with_think_removal(response_text)
            
            # ── 후처리: 위험 줄임 매핑 제거 ──
            # key_terms에 없는 줄임, 문법적 축약(조사/어미 포함), 일반명사 등 필터링
            import re as _re_post
            valid_abbrevs = []
            _kt_set = {_re_post.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', str(t)) for t in key_terms if isinstance(t, str)}
            # 일반명사 블랙리스트 — 줄임 매핑의 abbrev 키로 사용 불가
            _SNIPPET_GENERIC_WORDS = frozenset({
                "작가", "작품", "소설", "웹소설", "연재", "신작", "전작", "최신작",
                "주인공", "히로인", "캐릭터", "장르", "스포", "결말", "후기",
                "리뷰", "감상", "추천", "비추", "평가", "댓글", "제목",
                "예상", "전개", "스토리", "설정", "세계관", "먼치킨",
                "회귀", "환생", "빙의", "각성", "레벨업", "시스템",
            })
            for am in (result.get("abbreviation_mappings") or []):
                abbr = am.get("abbrev", "").strip()
                full = am.get("full", "").strip()
                if not abbr or not full or len(abbr) < 2 or len(full) < 4:
                    continue
                abbr_clean = _re_post.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', abbr)
                # 일반명사는 줄임 매핑 키로 사용 불가
                if abbr_clean in _SNIPPET_GENERIC_WORDS:
                    print(
                        f"[{_ts()}] {self.emoji} 📌 일반명사 줄임 제거: '{abbr}' → '{full}'",
                        file=sys.stderr,
                    )
                    continue
                # 줄임이 key_terms에 없으면 위험 가능성 높음
                if abbr_clean not in _kt_set:
                    print(
                        f"[{_ts()}] {self.emoji} 📌 위험 줄임 제거: '{abbr}' → '{full}' "
                        f"(key_terms없음)",
                        file=sys.stderr,
                    )
                    continue
                # 줄임과 정식 제목이 동일하면 무의미
                if abbr_clean == _re_post.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', full):
                    continue
                valid_abbrevs.append(am)
            result["abbreviation_mappings"] = valid_abbrevs
            
            # ── 후처리: irrelevant_authors에서 작품명이 섞인 경우 제거 ──
            # LLM이 "정령의 경제학" 같은 작품명을 작가로 잘못 분류하는 경우 방어
            _irr_authors = result.get("irrelevant_authors") or []
            if _irr_authors and isinstance(_irr_authors, list):
                _identified_title = (result.get("identified_title") or "").strip()
                _valid_abbrev_fulls = {
                    _re_post.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', am.get("full", "")).lower()
                    for am in valid_abbrevs
                    if am.get("full")
                }
                _cleaned_irr = []
                for _ia in _irr_authors:
                    if not isinstance(_ia, str) or not _ia.strip():
                        continue
                    _ia_clean = _re_post.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', _ia).lower()
                    # 작품명과 동일하면 작가가 아님
                    if _identified_title and _ia_clean == _re_post.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', _identified_title).lower():
                        continue
                    # 줄임 매핑의 full(정식 제목)과 동일하면 작가가 아님
                    if _ia_clean in _valid_abbrev_fulls:
                        continue
                    # 5글자 이상이고 "의" 또는 공백이 포함되면 작품명일 가능성 높음
                    if len(_ia.strip()) >= 5 and ("의 " in _ia or " " in _ia.strip()):
                        # 작가명은 보통 2-4음절, 공백 없음. 5글자+공백은 작품명 패턴
                        # 추가 검증: 작가 패턴 접미사 확인
                        if not any(_ia.strip().endswith(s) for s in ("작가", "작", "님")):
                            print(
                                f"[{_ts()}] {self.emoji} 📌 irrelevant_authors에서 작품명 의심 제거: '{_ia}'",
                                file=sys.stderr,
                            )
                            continue
                    _cleaned_irr.append(_ia)
                result["irrelevant_authors"] = _cleaned_irr
            
            # ── 후처리: 비소설 매체 감지 시 작품 매칭 결과 무효화 ──
            category = (result.get("identified_category") or "unknown").lower()
            NON_NOVEL_CATEGORIES = {"vocaloid_song", "anime", "manga", "game", "aa_work"}
            if category in NON_NOVEL_CATEGORIES:
                print(
                    f"[{_ts()}] {self.emoji} 📌 비소매체 감지: category={category}"
                    f" -> identified_title/author invalidated",
                    file=sys.stderr,
                )
                result["identified_title"] = None
                result["identified_author"] = None
                result["abbreviation_mappings"] = []
                result["relevant_authors"] = []
            
            print(
                f"[{_ts()}] {self.emoji} 📌 LLM snippet 분석 완료: "
                f"title={result.get('identified_title')}, "
                f"author={result.get('identified_author')}, "
                f"category={category}, "
                f"irrelevant={result.get('irrelevant_authors', [])}",
                file=sys.stderr,
            )
            return result
        except Exception as e:
            print(f"[{_ts()}] {self.emoji} ⚠️ LLM snippet 분석 실패 (fallback→기계적): {e}", file=sys.stderr)
            return None

    def _extract_hints_from_snippets(
        self, search_results: List[Dict[str, Any]], key_terms: List[str]
    ) -> Dict[str, Any]:
        """검색 결과 snippet에서 제목/작가/줄임 후보를 코드로만 추출한다.
        
        LLM을 사용하지 않고, 정규식 패턴 매칭으로 동작.
        
        Returns:
            {
                "title_hints": [{"title": str, "source": str, "url": str}],
                "author_hints": [{"name": str, "source": str}],
                "abbreviation_hints": [{"abbrev": str, "full": str}],
                "fetchable_urls": [str]  -- 공식 플랫폼 URL (페치 대상)
            }
        """
        title_hints = []
        author_hints = []
        abbreviation_hints = []
        fetchable_urls = []
        
        seen_titles = set()
        seen_authors = set()
        
        # ── 일반명사 블랙리스트: 줄임 매핑 key로 사용 불가 ──
        _GENERIC_WORDS = frozenset({
            "작가", "작품", "소설", "웹소설", "연재", "신작", "전작", "최신작",
            "주인공", "히로인", "캐릭터", "장르", "스포", "결말", "후기",
            "리뷰", "감상", "추천", "비추", "평가", "댓글", "제목",
            "예상", "전개", "스토리", "설정", "세계관", "먼치킨",
            "회귀", "환생", "빙의", "각성", "레벨업", "시스템",
        })
        
        for r in search_results:
            content = r.get("content", "") or ""
            title = r.get("title", "") or ""
            url = r.get("url", "") or ""
            combined = f"{title} {content}"
            
            # 1) 제목 패턴 추출
            for pat in self._SNIPPET_TITLE_PATTERNS:
                for m in pat.finditer(combined):
                    found = m.group(1).strip()
                    if found and len(found) >= 2 and found not in seen_titles:
                        seen_titles.add(found)
                        title_hints.append({
                            "title": found,
                            "source": f"snippet_pattern",
                            "url": url,
                        })
            
            # 2) 작가 패턴 추출
            for pat in self._SNIPPET_AUTHOR_PATTERNS:
                for m in pat.finditer(combined):
                    found = m.group(1).strip()
                    if found and len(found) >= 2 and found not in seen_authors:
                        seen_authors.add(found)
                        author_hints.append({
                            "name": found,
                            "source": f"snippet_pattern",
                            "url": url,
                        })
            
            # 3) 줄임 매핑: "~줄임", "~줄여
            abbrev_match = re.search(
                r"([\uac00-\ud7a3A-Za-z0-9\s]{3,30})\s*(?:[:=(]?\s*)?([\uac00-\ud7a3A-Za-z0-9]{2,12})",
                combined
            )
            if abbrev_match:
                abbreviation_hints.append({
                    "full": abbrev_match.group(1).strip(),
                    "abbrev": abbrev_match.group(2).strip(),
                })
            # 갑 "줄임 ~ 또는 ~"
            abbrev_match2 = re.search(
                r"([\uac00-\ud7a3A-Za-z0-9\s]{3,35})(?:\s+([\uac00-\ud7a3A-Za-z0-9]{1,12}))?",
                combined
            )
            if abbrev_match2:
                # key_terms와 매칭하는 줄임 찾기
                for kt in key_terms:
                    if not isinstance(kt, str):
                        continue
                    for i in range(1, 3):
                        abbr = abbrev_match2.group(i)
                        if abbr and kt.replace(" ", "") == abbr.replace(" ", ""):
                            # snippet의 title에서 정식 제목 추출 시도
                            # "죽었다깨어났더니 - 나무위키" → "죽었다깨어났더니"
                            clean_title = re.sub(r'\s*[-\(\[].*$', '', title).strip()
                            if clean_title and len(clean_title) >= 3:
                                abbreviation_hints.append({
                                    "full": clean_title,
                                    "abbrev": abbr,
                                })
            
            # 4-pre) key_term이 snippet에서 줄임으로 사용되면 정식 제목과 같이 나오는 경우
            # 예: "즉사무림 이름이 그래서 그렇지" + content에 "즉사기하고 무림에 떨어졌다는 소설"
            for kt in key_terms:
                if not isinstance(kt, str) or len(kt) < 2:
                    continue
                kt_clean = kt.replace(" ", "")
                # ── 일반명사는 줄임 매핑 키로 사용 불가 ──
                if kt_clean in _GENERIC_WORDS:
                    continue
                # 이미 작가명으로 사용된 key_term은 줄임 매핑에서 제외
                if kt_clean in seen_authors:
                    continue
                # key_term이 title이나 content에 직접 등장하는지
                if kt_clean not in combined.replace(" ", ""):
                    continue
                # 같은 snippet에서 정식 제목 이상의 찾기
                # 패턴: "~ 하고 ~에 떨어졌다" 같은 긴 제목 (8자 이상)
                # 공식 플랫폼 URL결과에서 발견제목
                from urllib.parse import urlparse as _urlparse
                try:
                    _domain = _urlparse(url).hostname or ""
                except Exception:
                    _domain = ""
                is_platform = any(_domain == d or _domain.endswith("." + d) 
                                  for d in self._OFFICIAL_PLATFORM_DOMAINS) or "namu.wiki" in _domain
                
                if is_platform:
                    # 플랫폼결과title에서 정식 제목 추출
                    clean_t = re.sub(r'\s*[-\(\[].*$', '', title).strip()
                    # 시리즈 메뉴 제거: "NEW" 묐몢
                    clean_t = re.sub(r'^NEW\s*', '', clean_t).strip()
                    # 나무위키 리비전번호 제거: "죽었다깨어났더니 (r173 판)" → "죽었다깨어났더니"
                    clean_t = re.sub(r'\s*\(r\d+\s*\)\s*$', '', clean_t).strip()
                    if clean_t and len(clean_t) >= 5 and kt_clean != clean_t.replace(" ", ""):
                        # 줄임 정식 제목이면 매핑 생성
                        if clean_t not in seen_titles:
                            seen_titles.add(clean_t)
                            title_hints.append({
                                "title": clean_t,
                                "source": "platform_title",
                                "url": url,
                            })
                        abbreviation_hints.append({
                            "full": clean_t,
                            "abbrev": kt_clean,
                        })
                else:
                    # 커뮤니티 결과: content에서 정식 제목 패턴 찾기
                    # "~의 X라는 소설", "다른 필요 없고, X" 등
                    full_title_m = re.search(
                        r"([\uac00-\ud7a3A-Za-z0-9]{2,8}(?:\s[\uac00-\ud7a3A-Za-z0-9]{1,8}){1,6})",
                        combined
                    )
                    if full_title_m:
                        ft = full_title_m.group(1).strip()
                        if ft and len(ft) >= 5 and kt_clean != ft.replace(" ", ""):
                            if ft not in seen_titles:
                                seen_titles.add(ft)
                                title_hints.append({
                                    "title": ft,
                                    "source": "community_mention",
                                    "url": url,
                                })
                            abbreviation_hints.append({
                                "full": ft,
                                "abbrev": kt_clean,
                            })
            
            # 4-B) key_term 작가명 부분 매칭: key_term이 작가명의 접두사인 경우
            # 예: key_term '개돌'로 검색하여 '개돌전쟁' 작가 발견 시 작가 힌트 추가
            for kt in key_terms:
                if not isinstance(kt, str) or len(kt) < 2:
                    continue
                kt_clean = kt.replace(" ", "")
                # 이미 확실한 작가 힌트가 있으면 스킵
                if kt_clean in seen_authors:
                    continue
                # content/title에서 "kt+N글자" 패턴으로 작가명 후보 찾기
                # 예: '개돌전쟁', '개돌전생' 등
                _author_prefix_pat = re.compile(
                    rf'({re.escape(kt_clean)}[\uac00-\ud7a3A-Za-z0-9]{{1,4}})(?:\s*(?:작가|필명))?',
                    re.IGNORECASE,
                )
                for _m in _author_prefix_pat.finditer(combined):
                    _found_author = _m.group(1).strip()
                    if _found_author and _found_author not in seen_authors and _found_author != kt_clean:
                        seen_authors.add(_found_author)
                        author_hints.append({
                            "name": _found_author,
                            "source": "prefix_match",
                            "url": url,
                        })
                        # 줄임 매핑에 추가: '개돌' → '개돌전쟁(작가)'
                        abbreviation_hints.append({
                            "full": f"{_found_author}(작가)",
                            "abbrev": kt_clean,
                        })
            
            # 5) URL을 가진 fetch 대상: 공식 플랫폼 + 나무위키 + 유용한 커뮤니티
            if url:
                from urllib.parse import urlparse
                try:
                    domain = urlparse(url).hostname or ""
                    # 나무위키최우(줄임/작가/장르 구조정보)
                    if "namu.wiki" in domain:
                        fetchable_urls.insert(0, url)  # 맨 앞에
                    elif any(domain == d or domain.endswith("." + d) for d in self._OFFICIAL_PLATFORM_DOMAINS):
                        fetchable_urls.append(url)
                    elif any(kw in domain for kw in (
                        "tistory", "blog.naver", "arca.live", "dcinside",
                        "fmkorea", "ruliweb", "brunch", "wikipedia",
                    )):
                        # 블로그·커뮤니티의 본문에 유용한 정보 포함 가능
                        fetchable_urls.append(url)
                except Exception:
                    pass
        
        # ── 교차 검증: title_hints에도 있는 이름이 author_hints에 들어간 경우 제거 ──
        # 예: "즉사무림 작가" 패턴에서 "즉사무림"을 작가로 잡았지만,
        #     실제로는 작품 약칭 → title_hints에도 있으면 author에서 제거
        _title_norms = {
            re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', h.get("title", "")).lower()
            for h in title_hints if h.get("title")
        }
        # abbreviation_hints의 full/abbrev도 title 이름으로 간주
        for ah in abbreviation_hints:
            _ab_full = re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', ah.get("full", "")).lower()
            _ab_abbr = re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', ah.get("abbrev", "")).lower()
            if _ab_full:
                _title_norms.add(_ab_full)
            if _ab_abbr:
                _title_norms.add(_ab_abbr)
        
        if _title_norms:
            _before_authors = len(author_hints)
            author_hints = [
                ah for ah in author_hints
                if re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', ah.get("name", "")).lower()
                   not in _title_norms
            ]
            _removed = _before_authors - len(author_hints)
            if _removed > 0:
                print(
                    f"[_extract_hints] ⚠️ 작품명과 중복된 작가명 제거: {_removed}건",
                    file=sys.stderr,
                )
        
        return {
            "title_hints": title_hints,
            "author_hints": author_hints,
            "abbreviation_hints": abbreviation_hints,
            "fetchable_urls": list(dict.fromkeys(fetchable_urls)),  # 중복 제거, 순서 유지
        }

    @staticmethod
    def _normalize_hint_text(text: Any) -> str:
        """Normalize hint text for robust matching."""
        if text is None:
            return ""
        return re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(text)).lower()

    def _sanitize_deep_search_hints(
        self,
        hints: Dict[str, Any],
        key_terms: List[str],
        *,
        post_text_norm: str = "",
    ) -> Dict[str, Any]:
        """Drop low-signal hints and dedupe by normalized value."""
        if not isinstance(hints, dict):
            return {"title_hints": [], "author_hints": [], "abbreviation_hints": [], "fetchable_urls": []}

        key_terms_norm = {
            self._normalize_hint_text(term)
            for term in (key_terms or [])
            if isinstance(term, str) and self._normalize_hint_text(term)
        }

        generic_title_terms = {
            "일상", "작가", "등장인물", "캐릭터", "내용", "제목", "장르",
            "커뮤니티", "평가", "리뷰", "추천", "글", "댓글에서", "에서",
        }

        source_priority = {
            "url_fetch_platform": 5,
            "platform_title": 4,
            "url_fetch": 3,
            "llm_snippet": 3,
            "community_mention": 2,
            "snippet_pattern": 1,
        }

        sanitized_titles: Dict[str, Dict[str, Any]] = {}
        for th in (hints.get("title_hints") or []):
            if not isinstance(th, dict):
                continue
            title = th.get("title")
            title_norm = self._normalize_hint_text(title)
            if not title_norm:
                continue
            source = str(th.get("source", ""))
            source_score = source_priority.get(source, 0)

            # Low-signal snippet-only title hints are noisy unless tied to current post terms.
            tied_to_post = bool(
                title_norm in post_text_norm
                or any(kt and (kt in title_norm or title_norm in kt) for kt in key_terms_norm)
            )
            if source_score <= 2:
                if len(title_norm) < 3:
                    continue
                if title_norm in generic_title_terms and not tied_to_post:
                    continue
                if not tied_to_post and len(title_norm) <= 4:
                    continue

            existing = sanitized_titles.get(title_norm)
            if (not existing) or (source_score > source_priority.get(str(existing.get("source", "")), 0)):
                sanitized_titles[title_norm] = th

        sanitized_authors: Dict[str, Dict[str, Any]] = {}
        for ah in (hints.get("author_hints") or []):
            if not isinstance(ah, dict):
                continue
            name = ah.get("name")
            author_norm = self._normalize_hint_text(name)
            if len(author_norm) < 2:
                continue
            source = str(ah.get("source", ""))
            source_score = source_priority.get(source, 0)
            if source_score <= 1 and author_norm not in post_text_norm:
                continue
            existing = sanitized_authors.get(author_norm)
            if (not existing) or (source_score > source_priority.get(str(existing.get("source", "")), 0)):
                sanitized_authors[author_norm] = ah

        sanitized_abbrev: Dict[tuple[str, str], Dict[str, Any]] = {}
        for ab in (hints.get("abbreviation_hints") or []):
            if not isinstance(ab, dict):
                continue
            abbrev_norm = self._normalize_hint_text(ab.get("abbrev"))
            full_norm = self._normalize_hint_text(ab.get("full"))
            if len(abbrev_norm) < 2 or len(full_norm) < 3:
                continue
            tied_to_post = bool(
                abbrev_norm in key_terms_norm
                or abbrev_norm in post_text_norm
                or any(kt and (kt in abbrev_norm or abbrev_norm in kt) for kt in key_terms_norm)
            )
            if not tied_to_post:
                continue
            key = (abbrev_norm, full_norm)
            if key not in sanitized_abbrev:
                sanitized_abbrev[key] = ab

        return {
            "title_hints": list(sanitized_titles.values())[:12],
            "author_hints": list(sanitized_authors.values())[:10],
            "abbreviation_hints": list(sanitized_abbrev.values())[:15],
            "fetchable_urls": list(dict.fromkeys(hints.get("fetchable_urls") or [])),
        }

    def _merge_snippet_hints(
        self,
        ctx: "ConversationContext",
        hints: Dict[str, Any],
        key_terms: List[str],
        *,
        post_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Merge new deep-search hints into ctx with sanitization and dedupe."""
        post_text_parts: List[str] = []
        if isinstance(post_data, dict):
            post_text_parts.append(post_data.get("title", ""))
            for block in (post_data.get("content_blocks") or []):
                if isinstance(block, dict):
                    post_text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    post_text_parts.append(block)
        if hasattr(ctx, "comments") and ctx.comments:
            post_text_parts.extend([c for c in ctx.comments if isinstance(c, str)])
        post_text_norm = self._normalize_hint_text(" ".join(post_text_parts))

        sanitized = self._sanitize_deep_search_hints(
            hints,
            key_terms,
            post_text_norm=post_text_norm,
        )

        source_priority = {
            "url_fetch_platform": 5,
            "platform_title": 4,
            "url_fetch": 3,
            "llm_snippet": 3,
            "community_mention": 2,
            "snippet_pattern": 1,
        }

        if not hasattr(ctx, "snippet_hints") or not ctx.snippet_hints:
            ctx.snippet_hints = {
                "title_hints": [],
                "author_hints": [],
                "abbreviation_hints": [],
            }

        def _merge_by_key(existing_list: List[Dict[str, Any]], incoming_list: List[Dict[str, Any]], key_fn) -> List[Dict[str, Any]]:
            merged: Dict[Any, Dict[str, Any]] = {}
            for item in (existing_list or []):
                if not isinstance(item, dict):
                    continue
                k = key_fn(item)
                if not k or k == ("", ""):
                    continue
                merged[k] = item
            for item in (incoming_list or []):
                if not isinstance(item, dict):
                    continue
                k = key_fn(item)
                if not k or k == ("", ""):
                    continue
                prev = merged.get(k)
                if not prev:
                    merged[k] = item
                    continue
                prev_score = source_priority.get(str(prev.get("source", "")), 0)
                new_score = source_priority.get(str(item.get("source", "")), 0)
                if new_score >= prev_score:
                    merged[k] = item
            return list(merged.values())

        ctx.snippet_hints["title_hints"] = _merge_by_key(
            ctx.snippet_hints.get("title_hints", []),
            sanitized.get("title_hints", []),
            key_fn=lambda item: self._normalize_hint_text(item.get("title")),
        )[:12]
        ctx.snippet_hints["author_hints"] = _merge_by_key(
            ctx.snippet_hints.get("author_hints", []),
            sanitized.get("author_hints", []),
            key_fn=lambda item: self._normalize_hint_text(item.get("name")),
        )[:10]
        ctx.snippet_hints["abbreviation_hints"] = _merge_by_key(
            ctx.snippet_hints.get("abbreviation_hints", []),
            sanitized.get("abbreviation_hints", []),
            key_fn=lambda item: (
                self._normalize_hint_text(item.get("abbrev")),
                self._normalize_hint_text(item.get("full")),
            ),
        )[:15]
    
    def _deep_search_enrich(
        self,
        ctx: "AgenticContext",
        key_terms: List[str],
        search_results: List[Dict[str, Any]],
        *,
        post_data: Optional[Dict[str, Any]] = None,
        gatekeeper_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """초기 검색 결과를 분석하여 추가 검색·URL 페치으로 정보를 보강한다.
        
        1단계: snippet에서 제목/작가/줄임 힌트 추출 (기계정규
        1-B단계: LLM snippet 분석 (문맥 기반 힌트 필터링·보강)
        2단계: 공식 플랫폼 URL 페치 (나무위키, 노벨피아 등)
        3단계: 발견된 작가명으로 2차 검색
        4단계: 은어 활용 쿼리 추가 ("뜻", "정식명칭")
        """
        import re as _re
        
        hints = self._extract_hints_from_snippets(search_results, key_terms)
        _key_terms_norm = {
            self._normalize_hint_text(t)
            for t in (key_terms or [])
            if isinstance(t, str) and self._normalize_hint_text(t)
        }
        _post_text_parts: List[str] = []
        if isinstance(post_data, dict):
            _post_text_parts.append(post_data.get("title", ""))
            for _blk in (post_data.get("content_blocks") or []):
                if isinstance(_blk, dict):
                    _post_text_parts.append(_blk.get("text", ""))
                elif isinstance(_blk, str):
                    _post_text_parts.append(_blk)
        _post_text_parts.extend([c for c in (ctx.comments or []) if isinstance(c, str)])
        _post_text_norm = self._normalize_hint_text(" ".join(_post_text_parts))
        
        # ── 1-B단계: LLM snippet 분석 (문맥 기반 판별) ──
        # 기계적 추출로만 모은 힌트를 LLM에 문맥을 보내고 필터링·보강
        llm_snippet_result = None
        if post_data and gatekeeper_result:
            llm_snippet_result = self._llm_analyze_snippets(
                post_data, key_terms, search_results, gatekeeper_result
            )
        
        if llm_snippet_result:
            # LLM근거정식 제목 줄임 매핑 보강
            llm_title = llm_snippet_result.get("identified_title")
            llm_abbrevs = llm_snippet_result.get("abbreviation_mappings") or []
            if llm_title and llm_abbrevs:
                existing_abbrevs = {
                    (h.get("abbrev", ""), h.get("full", ""))
                    for h in hints.get("abbreviation_hints", [])
                }
                for am in llm_abbrevs:
                    pair = (am.get("abbrev", ""), am.get("full", ""))
                    if pair[0] and pair[1] and pair not in existing_abbrevs:
                        hints["abbreviation_hints"].append({
                            "abbrev": pair[0],
                            "full": pair[1],
                        })
                        print(
                            f"[{_ts()}] {self.emoji} 📌 LLM 줄임 매핑 추가: "
                            f"'{pair[0]}' → '{pair[1]}'",
                            file=sys.stderr,
                        )
            
            # LLM 근거 작가로 author_hints 보강
            llm_author = llm_snippet_result.get("identified_author")
            if llm_author:
                existing_authors = {h.get("name", "") for h in hints.get("author_hints", [])}
                if llm_author not in existing_authors:
                    hints["author_hints"].insert(0, {
                        "name": llm_author,
                        "source": "llm_snippet",
                    })
            
            # ⚡ 핵심: LLM이 무관하다고 판단한 작가 를 기계적 힌트에서 제거
            irrelevant_authors = set(llm_snippet_result.get("irrelevant_authors") or [])
            if irrelevant_authors:
                # 🔧 Fix G: Gatekeeper가 work_discussion + 캐릭터 3명 이상이면
                # snippet_analyzer의 irrelevant_authors 판단을 무시
                # (snippet_analyzer가 검색 결과만 보고 작가를 무관하다고 판단하는 오류 방지)
                _gk_result_snip = getattr(ctx, 'gatekeeper_result', None) or {}
                _gk_post_type_snip = _gk_result_snip.get("post_type", "") if isinstance(_gk_result_snip, dict) else ""
                _gk_ent_snip = (_gk_result_snip.get("detected_entities") or {}) if isinstance(_gk_result_snip, dict) else {}
                _gk_chars_snip = _gk_ent_snip.get("possible_characters") or []
                
                if _gk_post_type_snip == "work_discussion" and len(_gk_chars_snip) >= 3:
                    print(
                        f"[{_ts()}] {self.emoji} 🛡️ irrelevant_authors 무시: "
                        f"GK=work_discussion + 캐릭터 {len(_gk_chars_snip)}명 → "
                        f"snippet의 무관 작가 판단 차단 ({irrelevant_authors})",
                        file=sys.stderr,
                    )
                    irrelevant_authors = set()  # 무효화
                else:
                    before_count = len(hints["author_hints"])
                    hints["author_hints"] = [
                        ah for ah in hints["author_hints"]
                        if ah.get("name", "") not in irrelevant_authors
                        or ah.get("source") in ("url_fetch", "url_fetch_platform", "llm_snippet")
                    ]
                    removed = before_count - len(hints["author_hints"])
                    if removed > 0:
                        print(
                            f"[{_ts()}] {self.emoji} 📌 LLM 무관 작가 제거: "
                            f"{irrelevant_authors} ({removed}개",
                            file=sys.stderr,
                        )
            
            # LLM 결과를 ctx에 저장 (Decoder가 활용)
            ctx.llm_snippet_analysis = llm_snippet_result
            
            # ⚡snippet_analyzer가 비소설 매체 또는 장르 일반론으로 판단한 경우
            _snippet_category = (llm_snippet_result.get("identified_category") or "unknown").lower()
            _snippet_post_intent = (llm_snippet_result.get("post_intent") or "").lower()
            _NON_NOVEL_CATS = {"vocaloid_song", "anime", "manga", "game", "aa_work"}
            
            # 🏷️ 장르 일반론 감지: snippet_analyzer가 게시글 의도를 genre_discussion으로 판단
            if _snippet_category == "genre_discussion" or _snippet_post_intent == "genre_discussion":
                _intent_reason = llm_snippet_result.get("post_intent_reason", "")
                if not ctx.discourse_warning:
                    ctx.discourse_warning = f"genre_discussion(snippet_analyzer)"
                ctx.uncertainty_sources.append(
                    f"snippet_analyzer: 게시글 의도=장르 일반론({_intent_reason[:80]}) → 특정 작품 매칭 주의"
                )
                print(
                    f"[{_ts()}] {self.emoji} ⚠️ snippet_analyzer 장르 일반론 감지: "
                    f"post_intent=genre_discussion → Decoder/Arbiter에 경고 전달 "
                    f"(reason: {_intent_reason[:60]})",
                    file=sys.stderr,
                )
            elif _snippet_category in _NON_NOVEL_CATS:
                if not ctx.is_association_post:
                    ctx.is_association_post = True
                    print(
                        f"[{_ts()}] {self.emoji} ❗snippet_analyzer 비소설 매체({_snippet_category}) "
                        f"→ is_association_post=true 설정",
                        file=sys.stderr,
                    )
                if not ctx.discourse_warning:
                    ctx.discourse_warning = f"non_novel_content({_snippet_category})"
                ctx.uncertainty_sources.append(
                    f"snippet_analyzer: 검색 결과가 {_snippet_category}를 가리킴 → 소설이 아닐 가능성 높음"
                )
        
        # 결과 로깅 정리
        # 1) 줄임 매핑에서 작가명이 abbrev로 들어간 경우 제거
        _known_authors = {h.get("name", "").replace(" ", "") for h in hints.get("author_hints", []) if h.get("name")}
        if _known_authors:
            _before_abbr = len(hints["abbreviation_hints"])
            hints["abbreviation_hints"] = [
                ah for ah in hints["abbreviation_hints"]
                if ah.get("abbrev", "").replace(" ", "") not in _known_authors
            ]
            _removed_abbr = _before_abbr - len(hints["abbreviation_hints"])
            if _removed_abbr > 0:
                print(f"[{_ts()}] {self.emoji} ⚡작가명→줄임 매핑 제거: {_known_authors} ({_removed_abbr}개", file=sys.stderr)
        
        # 2) title_hints에서 나무위키 리비번호 정리
        for th in hints.get("title_hints", []):
            t = th.get("title", "")
            cleaned = re.sub(r'\s*\(r\d+\s*\)\s*$', '', t).strip()
            if cleaned != t:
                th["title"] = cleaned

        # 약한 힌트를 정리해 연쇄 오매칭을 줄인다.
        hints = self._sanitize_deep_search_hints(
            hints,
            key_terms,
            post_text_norm=_post_text_norm,
        )
        
        # 결과 로깅
        if hints["title_hints"]:
            titles_str = ", ".join(h["title"] for h in hints["title_hints"][:5])
            print(f"[{_ts()}] {self.emoji} 🔬 snippet 제목 힌트: [{titles_str}]", file=sys.stderr)
        if hints["author_hints"]:
            authors_str = ", ".join(h["name"] for h in hints["author_hints"][:3])
            print(f"[{_ts()}] {self.emoji} 🔬 snippet 작가 힌트: [{authors_str}]", file=sys.stderr)
        if hints["abbreviation_hints"]:
            for ah in hints["abbreviation_hints"][:3]:
                print(f"[{_ts()}] {self.emoji} 🔬 줄임 매핑: '{ah.get('abbrev')}' → '{ah.get('full')}'", file=sys.stderr)
        
        # ── 2단계: URL 페치 후 content 보강 + 구조정보 추출 ──
        fetch_fn = getattr(self, 'fetch_fn', None)
        fetched_info: List[Dict[str, Any]] = []
        
        # 🔬 검색 결과 URL 인덱스 맵(content 보강용)
        url_to_idx: Dict[str, int] = {}
        for i, sr in enumerate(search_results):
            u = sr.get("url", "")
            if u:
                url_to_idx[u] = i
        
        if fetch_fn and hints["fetchable_urls"]:
            # 🏷️ URL 관련성 필터링: 줄임 매핑에서 근거한 작품과 관련된 URL 우선
            _fetch_urls = list(hints["fetchable_urls"])
            
            # 신뢰 가능한 제목 앵커 수집
            _identified_titles_for_filter = set()
            for _ah in hints.get("abbreviation_hints", []):
                _full_norm = self._normalize_hint_text(_ah.get("full", ""))
                _abbr_norm = self._normalize_hint_text(_ah.get("abbrev", ""))
                if (
                    _full_norm
                    and len(_full_norm) >= 3
                    and (_abbr_norm in _key_terms_norm or _abbr_norm in _post_text_norm)
                ):
                    _identified_titles_for_filter.add(_full_norm)

            for _th in hints.get("title_hints", [])[:8]:
                _t_norm = self._normalize_hint_text(_th.get("title", ""))
                _source = str(_th.get("source", ""))
                if not _t_norm or len(_t_norm) < 3:
                    continue
                if _source in ("url_fetch_platform", "platform_title", "url_fetch", "llm_snippet"):
                    _identified_titles_for_filter.add(_t_norm)
                elif any(kt and (kt in _t_norm or _t_norm in kt) for kt in _key_terms_norm):
                    _identified_titles_for_filter.add(_t_norm)

            def _query_overlap_score(url: str) -> float:
                score = 0.0
                if url in url_to_idx:
                    _sr = search_results[url_to_idx[url]]
                    _sr_norm = self._normalize_hint_text(f"{_sr.get('title', '')} {_sr.get('content', '')}")
                    for _kt in _key_terms_norm:
                        if _kt and _kt in _sr_norm:
                            score += 2.0
                return score

            if _identified_titles_for_filter:
                def _url_relevance_score(url: str) -> float:
                    score = 0.0
                    url_lower = url.lower()
                    url_norm = self._normalize_hint_text(url)

                    for _ft in _identified_titles_for_filter:
                        _ft_tokens = re.findall(r"[a-z0-9]{2,}|[가-힣]{2,}", _ft)
                        if any(tok in url_norm for tok in _ft_tokens[:3]):
                            score += 2.0

                    if "namu.wiki" in url_lower:
                        score += 0.6
                    if any(p in url_lower for p in ("novelpia", "munpia", "kakaopage", "series.naver")):
                        score += 1.0

                    if url in url_to_idx:
                        _sr = search_results[url_to_idx[url]]
                        _sr_text = self._normalize_hint_text(f"{_sr.get('title', '')} {_sr.get('content', '')}")
                        for _ft in _identified_titles_for_filter:
                            if len(_ft) >= 3 and _ft in _sr_text:
                                score += 3.0
                                break
                    score += _query_overlap_score(url)
                    return score

                _scored_urls = [(u, _url_relevance_score(u)) for u in _fetch_urls]
                _scored_urls.sort(key=lambda x: x[1], reverse=True)
                _fetch_urls = [u for u, s in _scored_urls if s > 0][:3]
                if not _fetch_urls:
                    _fetch_urls = [u for u, _ in _scored_urls[:2]]

                if _scored_urls:
                    _top_scores = [(u.split("/")[-1][:30], f"{s:.1f}") for u, s in _scored_urls[:5]]
                    print(f"[{_ts()}] {self.emoji} 🎯 URL 관련성 필터링: {_top_scores}", file=sys.stderr)
            else:
                _scored_urls = [(u, _query_overlap_score(u)) for u in _fetch_urls]
                _scored_urls.sort(key=lambda x: x[1], reverse=True)
                _fetch_urls = [u for u, s in _scored_urls if s > 0][:3]
                if not _fetch_urls:
                    _fetch_urls = [u for u, _ in _scored_urls[:2]]

            for fetch_url in _fetch_urls[:3]:
                try:
                    result = fetch_fn(fetch_url)
                    if result and isinstance(result, dict):
                        structured = result.get("structured_info") or {}
                        text_preview = result.get("text") or ""
                        
                        if structured or text_preview:
                            fetched_info.append({
                                "url": fetch_url,
                                "structured_info": structured,
                                "text_preview": text_preview[:500],
                            })
                            
                            # 구조적 정보에서 추가 힌트 추출
                            # 나무위키 리비번호 정리 ?ы띁
                            def _clean_namu_rev(t: str) -> str:
                                return re.sub(r'\s*\(r\d+\s*\)\s*$', '', t).strip() if t else t
                            
                            if structured.get("page_title"):
                                _pt = _clean_namu_rev(structured["page_title"])
                                hints["title_hints"].append({
                                    "title": _pt,
                                    "source": "url_fetch",
                                    "url": fetch_url,
                                })
                            if structured.get("title"):
                                _st = _clean_namu_rev(structured["title"])
                                hints["title_hints"].append({
                                    "title": _st,
                                    "source": "url_fetch_platform",
                                    "url": fetch_url,
                                })
                            if structured.get("author"):
                                hints["author_hints"].append({
                                    "name": structured["author"],
                                    "source": "url_fetch",
                                })
                            if structured.get("abbreviations"):
                                _abbr_full = _clean_namu_rev(structured.get("page_title", ""))
                                for abbr in structured["abbreviations"]:
                                    hints["abbreviation_hints"].append({
                                        "full": _abbr_full,
                                        "abbrev": abbr,
                                    })
                            
                            domain = result.get("domain", "")
                            
                            # 🔬 핵심: fetch 본문으로 search_results의 content 보강
                            if fetch_url in url_to_idx and text_preview:
                                idx = url_to_idx[fetch_url]
                                old_content = search_results[idx].get("content", "")
                                # snippet(~200보다 fetch 본문띾하면 교체
                                if len(text_preview) > len(old_content) + 50:
                                    # 기존 snippet + fetch 본문⑹퀜보강
                                    enriched = old_content.rstrip()
                                    if enriched and not enriched.endswith("."):
                                        enriched += " "
                                    enriched += f"[본문] {text_preview}"
                                    search_results[idx]["content"] = enriched[:800]
                                    print(
                                        f"[{_ts()}] {self.emoji} 📝 content 보강: "
                                        f"{len(old_content)}자→{len(search_results[idx]['content'])}자({domain})",
                                        file=sys.stderr
                                    )
                            
                            print(
                                f"[{_ts()}] {self.emoji} ✅ URL 페치 완료: {domain} "
                                f"({'SearXNG fallback' if result.get('fallback') else '직접'}) "
                                f"(제목={structured.get('page_title') or structured.get('title', '?')}, "
                                f"작가={structured.get('author', '?')})",
                                file=sys.stderr
                            )
                except Exception as e:
                    print(f"[{_ts()}] {self.emoji} ⚠️ URL 페치 실패: {fetch_url} → {e}", file=sys.stderr)
        
        # 페치 정보를 ctx에 저장 (Decoder/Verifier가 활용)
        if fetched_info:
            if not hasattr(ctx, 'fetched_page_info'):
                ctx.fetched_page_info = []
            ctx.fetched_page_info.extend(fetched_info)
        
        # hints를 context에 병합 (정제 + 중복 제거)
        self._merge_snippet_hints(
            ctx,
            hints,
            key_terms,
            post_data=post_data,
        )
        
        # ── 3단계: 작가명으로 2차 검색 수행 ──
        # ⚠️ 줄임 매핑의 정식 제목과 같은 snippet에서 발견된 작가만 검색(무관 작가 방지)
        # 예: "즉사무림" → "즉사기하고 무림에 떨어졌다" 매핑 등
        #     "즉사기하고 게임 형식으로작가(갸올)무관 제외
        additional_searches = []
        
        if hints["author_hints"] and self.search_fn:
            # key_term/본문과 연결된 매핑만 신뢰 앵커로 사용
            _mapped_titles = set()
            for _ah in hints.get("abbreviation_hints", []):
                _full_norm = self._normalize_hint_text(_ah.get("full", ""))
                _abbr_norm = self._normalize_hint_text(_ah.get("abbrev", ""))
                if (
                    _full_norm
                    and len(_full_norm) >= 3
                    and (_abbr_norm in _key_terms_norm or _abbr_norm in _post_text_norm)
                ):
                    _mapped_titles.add(_full_norm)

            _fetched_authors_high = {
                ah["name"] for ah in hints["author_hints"]
                if ah.get("source") == "url_fetch_platform"
            }
            _fetched_authors_medium = {
                ah["name"] for ah in hints["author_hints"]
                if ah.get("source") in ("url_fetch", "llm_snippet")
            }

            for ah in hints["author_hints"][:4]:
                author_name = ah.get("name", "")
                author_norm = self._normalize_hint_text(author_name)
                if len(author_norm) < 2:
                    continue

                author_in_post = bool(author_norm and author_norm in _post_text_norm)
                author_source = str(ah.get("source", ""))

                if author_name in _fetched_authors_high:
                    pass
                elif author_name in _fetched_authors_medium:
                    if not author_in_post and not _mapped_titles:
                        print(
                            f"[{_ts()}] {self.emoji} 🔬 작가 힌트 스킵: '{author_name}' "
                            f"(본문 앵커/신뢰 매핑 없음, source={author_source})",
                            file=sys.stderr,
                        )
                        continue
                elif _mapped_titles:
                    is_relevant_author = False
                    for sr in search_results:
                        sr_text_norm = self._normalize_hint_text(
                            f"{sr.get('title', '')} {sr.get('content', '')}"
                        )
                        if author_norm in sr_text_norm:
                            for _mt in _mapped_titles:
                                if _mt in sr_text_norm:
                                    is_relevant_author = True
                                    break
                        if is_relevant_author:
                            break
                    if not is_relevant_author and not author_in_post:
                        print(
                            f"[{_ts()}] {self.emoji} 🔬 작가 힌트 스킵: '{author_name}' "
                            f"(작품 앵커 동시출현 없음)",
                            file=sys.stderr,
                        )
                        continue
                elif not author_in_post:
                    # 본문에 없는 저신뢰 작가명은 확장 검색 금지
                    continue

                q = f"{author_name} 작가 작품"
                if q not in ctx.searched_queries and len(q) <= 50:
                    additional_searches.append({
                        "query": q,
                        "purpose": "author_works_search",
                        "priority": 1,
                    })
                    ctx.searched_queries.add(q)        
        # ── 4단계: 은어 활용 쿼리 ──
        # key_terms 중 해석되지 않은 은어에 대해 "뜻" "정식명칭" 검색
        # ⚠️ 일반 동사/형용어 불변 명사는 은어가 아니므로 스킵
        # ⚠️ 캐릭터명은 은어가 아니므로 스킵 (Gatekeeper possible_characters 활용)
        _COMMON_WORDS_NOT_ABBREV = {
            "죽이고", "죽임", "죽인", "죽었", "이런", "저런", "그런", "하는", "되는",
            "소개", "결말", "스포", "일상", "작가", "캐릭터", "주인공", "내용",
            "리뷰", "추천", "연재", "완결", "후기", "설정", "스토리", "장르",
        }
        # Gatekeeper 캐릭터명 수집 후 은어 검색 제외 대상
        _gk_characters_for_abbrev = set()
        if gatekeeper_result:
            _gk_ent = gatekeeper_result.get("detected_entities") or {}
            for _ch in (_gk_ent.get("possible_characters") or []):
                if isinstance(_ch, str):
                    _gk_characters_for_abbrev.add(_re.sub(r'[^\uac00-\ud7a3]', '', _ch))
        # LLM snippet 분석에서 확인된 캐릭터도 추가
        if llm_snippet_result:
            for _ch in (llm_snippet_result.get("relevant_characters") or []):
                if isinstance(_ch, str):
                    _gk_characters_for_abbrev.add(_re.sub(r'[^\uac00-\ud7a3]', '', _ch))
        
        if self.search_fn:
            for term in key_terms[:3]:
                if not isinstance(term, str):
                    continue
                term_clean = _re.sub(r'[^\uac00-\ud7a3]', '', term)
                if len(term_clean) < 3 or len(term_clean) > 8:
                    continue
                # 이미 정식 제목처럼 긴 단어는 스킵
                if len(term_clean) > 6:
                    continue
                # ⚠️ 일반 어휘는 은어가 아닐 수 스킵
                if term_clean in _COMMON_WORDS_NOT_ABBREV:
                    continue
                # ⚡ 캐릭터명은 은어가 아닐 수 스킵 (주인공 빈도수 등)
                if term_clean in _gk_characters_for_abbrev:
                    print(
                        f"[{_ts()}] {self.emoji} 🔬 은어 검색 스킵: '{term_clean}' "
                        f"(캐릭곕챸)",
                        file=sys.stderr,
                    )
                    continue
                # 이미 줄임 매핑발견섏뿀쇰㈃ 스킵
                known_abbrevs = {h.get("abbrev", "") for h in hints.get("abbreviation_hints", [])}
                if term_clean in known_abbrevs:
                    continue
                
                q_meaning = f"{term_clean} 줄임"
                if q_meaning not in ctx.searched_queries:
                    additional_searches.append({
                        "query": q_meaning,
                        "purpose": "abbreviation_meaning_search",
                        "priority": 2,
                    })
                    ctx.searched_queries.add(q_meaning)
                
                q_fullname = f"{term_clean} 뜻 정식명칭"
                if q_fullname not in ctx.searched_queries:
                    additional_searches.append({
                        "query": q_fullname,
                        "purpose": "abbreviation_fullname_search",
                        "priority": 2,
                    })
                    ctx.searched_queries.add(q_fullname)
        
        # 추가 검색 수행
        if additional_searches:
            print(
                f"[{_ts()}] {self.emoji} 🔬 Deep Search 추가 검색{len(additional_searches)}개수행",
                file=sys.stderr
            )
            new_results = self._execute_searches(additional_searches, ctx.post_id)
            if new_results:
                added = ctx.add_search_results(new_results)
                print(
                    f"[{_ts()}] {self.emoji} 🔬 Deep Search 결과 {added}개추가",
                    file=sys.stderr
                )
                
                # 새 결과에서도 힌트 재추출
                new_hints = self._extract_hints_from_snippets(new_results, key_terms)
                self._merge_snippet_hints(
                    ctx,
                    new_hints,
                    key_terms,
                    post_data=post_data,
                )
    
    def _execute_searches(
        self,
        requests: List[Dict[str, Any]],
        post_id: int,
    ) -> List[Dict[str, Any]]:
        """검색 수행 (URL 기반 중복 제거 + 우선순위 재정렬 + content 축소)"""
        if not self.search_fn:
            return []
        
        all_results = []
        seen_urls = set()  # URL 중복 체크
        # 쿼리 수 제한: 기존 고정 5개를 환경변수로 열어놓음 (expert_main에서 LLM_MAX_SEARCH_QUERIES를 이미 설정함)
        try:
            max_q = int(os.getenv("LLM_MAX_SEARCH_QUERIES", "5"))
        except Exception:
            max_q = 5
        max_q = max(1, min(max_q, 20))

        # priority(쓣섎줉 우선) + stable sort(먮옒 순서 유지)
        sortable: list[tuple[int, int, dict]] = []
        for i, req in enumerate(requests or []):
            if not isinstance(req, dict):
                continue
            pr = req.get("priority", 999)
            try:
                pr_i = int(pr)
            except Exception:
                pr_i = 999
            sortable.append((pr_i, i, req))
        sortable.sort(key=lambda x: (x[0], x[1]))

        seen_queries: set[str] = set()
        for _, _, req in sortable:
            if len(seen_queries) >= max_q:
                break
            query = str(req.get("query", "")).strip()
            if not query:
                continue

            # 중복 쿼리 제거 (공백 정규+ lower)
            q_key = " ".join(query.split()).lower()
            if q_key in seen_queries:
                continue
            seen_queries.add(q_key)
            
            # ⚡쿼리 길이 방어: 50자 초과 시 스킵 (전체 문장을 쿼리로 넣어오는 LLM 에러 방지)
            if len(query) > 50:
                print(f"[{_ts()}] ⚠️ 검색 쿼리 너무 김 ({len(query)}자) → 스킵: {query[:40]}...", file=sys.stderr)
                continue
            
            purpose = req.get("purpose", "search")
            print(f"[{_ts()}] 🔍 검 {query} (목적: {purpose})", file=sys.stderr)
            try:
                results = self.search_fn(query)
                result_list = results if isinstance(results, list) else []
                
                # 중복 제거 + 관련성 필터링+ 자기참조 제거: URL 기반
                new_results = []
                filtered_count = 0
                self_ref_count = 0
                current_post_id_str = str(post_id) if post_id else ""
                for r in result_list:
                    url = r.get("url", "")
                    
                    # ⚡아이디어 E: 자기참조 URL 필터 (검색 결과에 자기 게시글이 포함된 경우 제거)
                    if current_post_id_str and url and current_post_id_str in url:
                        # dcinside 게시글 URL 패턴 확인 (genrenovel/11718111?page=2 등)
                        if 'dcinside.com' in url:
                            self_ref_count += 1
                            continue
                    
                    # 관련성 필터링
                    if not self._is_relevant_result(r, query):
                        filtered_count += 1
                        continue
                    
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        # content 축소 (500자) - fetch 보강된 content 보존
                        r_copy = r.copy()
                        content = r_copy.get("content", "")
                        if content and len(content) > 500:
                            r_copy["content"] = content[:500]
                        new_results.append(r_copy)
                    elif not url:  # URL 없는 결과는 그대로 추가
                        r_copy = r.copy()
                        content = r_copy.get("content", "")
                        if content and len(content) > 500:
                            r_copy["content"] = content[:500]
                        new_results.append(r_copy)
                
                all_results.extend(new_results)
                
                # 검색 결과 상세 출력
                duplicate_count = len(result_list) - len(new_results) - filtered_count - self_ref_count
                filter_info = f", 무관 {filtered_count}개 제외" if filtered_count > 0 else ""
                dup_info = f", 중복 {duplicate_count}개 제거" if duplicate_count > 0 else ""
                self_ref_info = f", 자기참조 {self_ref_count}개 제거" if self_ref_count > 0 else ""
                print(
                    f"[{_ts()}] search results: {len(new_results)}{filter_info}{dup_info}{self_ref_info}",
                    file=sys.stderr,
                )
                
                for i, r in enumerate(new_results[:7], 1):  # 최대 7개만 출력
                    title = r.get("title", "제목없음")[:60]
                    url = r.get("url", "")[:80]
                    content = r.get("content", "")[:100].replace("\n", " ")
                    print(f"[{_ts()}]    [{i}] {title}", file=sys.stderr)
                    if url:
                        print(f"[{_ts()}]        URL: {url}", file=sys.stderr)
                    if content:
                        print(f"[{_ts()}]        내용: {content}...", file=sys.stderr)
            except Exception as e:
                print(f"[{_ts()}] 🔍 검색 에러: {e}", file=sys.stderr)
        
        # 우선순위 재정렬적용
        if all_results:
            all_results = self._prioritize_search_results(all_results)
            print(f"[{_ts()}] 🎯 검색 결과 우선순위 재정렬 완료 (총{len(all_results)}개", file=sys.stderr)
        
        return all_results



