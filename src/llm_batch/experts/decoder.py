"""
Stage 2: Decoder Expert - 한글 슬랭 해독 전문가
Korean abbreviation/slang restoration specialist.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any, Dict, List, Optional

from .prompts import DECODER_SYSTEM, DECODER_PROMPT
from ..prompts.expert_prompts import PLATFORM_ABBREVIATION_MAP
from ..rules import (
    OFFICIAL_PLATFORMS, GENRE_KEYWORDS, GENRE_ARCHETYPE_TERMS,
    PLATFORM_ABBREVIATIONS, PLATFORM_FEATURE_TERMS, ASSOCIATION_PATTERNS,
)
from .utils import parse_json_with_think_removal, _ts
import re as _re


# ============================================================
# 알려진 약어 사전 (모듈 수준 상수)
# ============================================================
KNOWN_ABBREVIATIONS = {
    "아생갤": "아카데미에서 생존하기",
    "아생": "아카데미에서 생존하기",
    "괴담텔": "괴담 호텔 탈출기",
    "괴담동": "괴담 동아리",
    "망겜성": "망겜의 성기사",
    "성좌안무서움": "나만 성좌들이 안 무서움",
    "지구판역": "판타지에 지구 역사를 풀었다",
    "즉사무림": "즉사기 들고 무림에 떨어지다",
    "숨흑재": "숨겨진 흑막이 되었다",
    "재벌집막": "재벌집 막내아들",
    "나혼렙": "나 혼자만 레벨업",
    "전독시": "전지적 독자 시점",
    "전지적독자": "전지적 독자 시점",
    "신화급": "신화급 귀속 아이템을 손에 넣었다",
    "학전무": "학교전쟁 무한 레벨업",
}


# ============================================================
# 약어-제목 매칭 스코어 (LLM 불필요, 코드 레벨 검증)
# ============================================================

def abbreviation_match_score(abbr: str, candidate_title: str) -> float:
    """
    약어가 후보 제목에서 파생될 수 있는지 0.0~1.0 스코어로 반환.

    세 가지 패턴을 모두 시도하고, 가장 높은 점수를 반환:
      패턴A (음절추출형): 죽깨수 ← 죽(었다) 깨(어도) 수(선)
      패턴B (핵심어결합형): 즉사무림 ← 즉사(기) + 무림
      패턴C (접두사형): 숨흑 ← (숨겨진 흑막...)
    """
    if not abbr or not candidate_title:
        return 0.0

    abbr_clean = abbr.strip()
    title_clean = candidate_title.strip()
    title_no_space = title_clean.replace(" ", "")

    # 한글 음절만 추출
    abbr_syllables = [c for c in abbr_clean if '가' <= c <= '힣']
    if not abbr_syllables:
        return 0.0

    # 🔧 영문자 첫글자 → 한글 매핑 (K-문화의 제왕 → 케문제 등)
    _ALPHA_TO_KOR: dict[str, str] = {
        'K': '케', 'k': '케',
        'S': '에스', 's': '에스',
        'A': '에이', 'a': '에이',
    }

    scores: list[float] = []

    # 🚨 Verbatim 차단: 약어가 그대로 제목에 들어있으면 "디코딩"이 아님
    # 예: "즉사무림" → "즉사무림 소년심사재강호" = 커뮤니티 글제목 (약칭 그대로 + 다른 텍스트)
    # 약어가 제목에 변환없이 나타나면, 그건 디코딩된 게 아님 → early return
    abbr_joined = "".join(abbr_syllables)
    if abbr_joined in title_no_space:
        if abbr_joined == title_no_space:
            return 0.0  # 동일 문자열
        return 0.3      # 커뮤니티 글제목 패턴 (약칭+다른텍스트)

    # --- 패턴 A: 음절추출형 (각 음절 = 제목 내 각 단어의 첫 음절) ---
    # 🔧 "K-문화의" → ["K", "문화의"] 분리 (영문+하이픈+한글 결합 토큰)
    import re as _re_local
    _raw_words = title_clean.split()
    title_words: list[str] = []
    for rw in _raw_words:
        # 영문자(+숫자) 뒤에 하이픈+한글이 오는 패턴 분리
        parts = _re_local.split(r'(?<=[A-Za-z0-9])[-](?=[가-힣])', rw)
        title_words.extend(parts)

    # 🔧 반복 약어 패턴 대응: "좋아좋아좋아" 같은 단어를 반복 단위로 분할
    # "마좋좋좋" → ["마","좋","좋","좋"] vs ["마법","좋아좋아좋아"] → 2 < 4 실패 방지
    if len(title_words) < len(abbr_syllables) and len(abbr_syllables) >= 3:
        expanded_words: list[str] = []
        for tw in title_words:
            tw_korean = [c for c in tw if '가' <= c <= '힣']
            if len(tw_korean) >= 4:
                # 반복 패턴 감지: 2~3음절 단위 반복 여부 확인
                tw_str = "".join(tw_korean)
                split_done = False
                for unit_len in (2, 3):
                    unit = tw_str[:unit_len]
                    if len(tw_str) % unit_len == 0 and all(
                        tw_str[i:i+unit_len] == unit
                        for i in range(0, len(tw_str), unit_len)
                    ):
                        # 반복 단위 분할: "좋아좋아좋아" → ["좋아","좋아","좋아"]
                        for i in range(0, len(tw_str), unit_len):
                            expanded_words.append(tw_str[i:i+unit_len])
                        split_done = True
                        break
                if not split_done:
                    expanded_words.append(tw)
            else:
                expanded_words.append(tw)
        if len(expanded_words) > len(title_words):
            title_words = expanded_words

    if len(title_words) >= len(abbr_syllables) and len(abbr_syllables) >= 2:
        match_count = 0
        word_idx = 0
        for syl in abbr_syllables:
            # 이 음절로 시작하는 단어를 순서대로 찾기
            found = False
            while word_idx < len(title_words):
                word = title_words[word_idx]
                korean_chars = [c for c in word if '가' <= c <= '힣']
                word_idx += 1
                if korean_chars and korean_chars[0] == syl:
                    match_count += 1
                    found = True
                    break
                # 🔧 영문 시작 단어: 알파벳 → 한글 발음 매칭
                if word and word[0].isascii() and word[0].isalpha():
                    mapped = _ALPHA_TO_KOR.get(word[0])
                    if mapped and mapped[0] == syl:
                        match_count += 1
                        found = True
                        break
            if not found:
                break
        if match_count == len(abbr_syllables):
            scores.append(0.95)  # 완벽 매치
        elif match_count >= len(abbr_syllables) - 1 and len(abbr_syllables) >= 3:
            scores.append(0.7)   # 1개 빗나감

    # --- 패턴 B: 핵심어결합형 (연속 음절 그룹이 제목에 부분문자열로 존재) ---
    if len(abbr_syllables) >= 3:
        best_b = _pattern_b_score(abbr_syllables, title_no_space)
        if best_b > 0:
            scores.append(best_b)

    # 패턴 B를 2음절 약어에도 적용 (단순 포함 체크)
    if len(abbr_syllables) == 2:
        seg = "".join(abbr_syllables)
        if seg in title_no_space:
            scores.append(0.8)

    # --- 패턴 C-2: 선두 글자 축약형 (각 단어의 앞 N글자 조합) ---
    # 예: "사펑" ← 사이버(펑크), "담텔" ← 괴(담) 호(텔)
    # 약어의 각 음절이 제목 내 서로 다른 단어의 선두에서 연속으로 추출될 수 있는지
    if len(abbr_syllables) >= 2 and not scores:
        # 제목을 공백 분리 후, 각 단어에서 선두 1~3글자를 추출
        _title_words_c2 = [w for w in title_clean.split() if any('가' <= c <= '힣' for c in w)]
        if _title_words_c2:
            # 각 단어의 한글 음절 추출
            _word_syllables = []
            for w in _title_words_c2:
                kor = [c for c in w if '가' <= c <= '힣']
                if kor:
                    _word_syllables.append(kor)
            
            # 연속 매칭: 약어 음절이 단어들의 선두 부분에서 순서대로 매칭되는지
            # 예: 사(이버)펑(크) 드래곤 → "사펑드래곤" = [사,펑,드,래,곤]
            #     word1=[사,이,버,펑,크] → "사"=word1[0], "펑"=word1[3]
            # 이 경우 한 단어 내에서 여러 음절이 추출될 수 있음
            # 전략: 각 약어 음절이 어떤 단어의 어떤 위치에서 오는지 그리디 매칭
            _abbr_idx = 0
            _word_idx = 0
            _matched_c2 = 0
            while _abbr_idx < len(abbr_syllables) and _word_idx < len(_word_syllables):
                _w = _word_syllables[_word_idx]
                _consumed_from_word = 0
                # 현재 단어에서 연속 음절 매칭 시도
                _w_pos = 0
                while _abbr_idx < len(abbr_syllables) and _w_pos < len(_w):
                    if abbr_syllables[_abbr_idx] == _w[_w_pos]:
                        _matched_c2 += 1
                        _abbr_idx += 1
                        _consumed_from_word += 1
                    _w_pos += 1
                _word_idx += 1
            
            if _matched_c2 == len(abbr_syllables) and len(abbr_syllables) >= 2:
                # 모든 약어 음절이 제목 단어들에서 순서대로 매칭됨
                ratio = _matched_c2 / max(len(title_no_space), 1)
                # 커버율에 따라 점수 조정 (너무 적은 커버는 낮은 점수)
                if ratio >= 0.3:
                    scores.append(0.90)
                elif ratio >= 0.15:
                    scores.append(0.80)

    return max(scores) if scores else 0.0


def _pattern_b_score(abbr_syllables: list[str], title_no_space: str) -> float:
    """
    패턴 B 상세: 약어를 가능한 모든 분할로 나누어
    각 세그먼트가 제목에 순서대로 존재하는지 확인.

    예: "즉사무림" → ("즉사","무림"), ("즉","사무림"), ("즉사무","림"), ...
        → "즉사기 들고 무림에 떨어지다"에서 ("즉사","무림") 둘 다 존재 → 0.9
    """
    n = len(abbr_syllables)
    if n < 2:
        return 0.0

    best = 0.0

    # 2~3개 세그먼트 분할 시도
    for num_splits in range(1, min(n, 3)):  # 1컷(2조각), 2컷(3조각)
        for split_points in _combinations(range(1, n), num_splits):
            segments = []
            prev = 0
            for sp in split_points:
                segments.append("".join(abbr_syllables[prev:sp]))
                prev = sp
            segments.append("".join(abbr_syllables[prev:]))

            # 모든 세그먼트가 제목에 (순서대로) 존재하는지
            all_found = True
            search_from = 0
            for seg in segments:
                if len(seg) < 1:
                    all_found = False
                    break
                idx = title_no_space.find(seg, search_from)
                if idx == -1:
                    all_found = False
                    break
                search_from = idx + len(seg)

            if all_found:
                # 세그먼트가 적을수록(=더 큰 덩어리) 높은 점수
                seg_score = 0.95 - 0.05 * len(segments)
                # 각 세그먼트 최소 2글자면 보너스
                if all(len(s) >= 2 for s in segments):
                    seg_score += 0.05
                best = max(best, min(seg_score, 1.0))

    return best


def _combinations(iterable, r):
    """itertools.combinations 대체 (가벼운 내장 구현)"""
    pool = list(iterable)
    n = len(pool)
    if r > n:
        return
    indices = list(range(r))
    yield [pool[i] for i in indices]
    while True:
        for i in reversed(range(r)):
            if indices[i] != i + n - r:
                break
        else:
            return
        indices[i] += 1
        for j in range(i + 1, r):
            indices[j] = indices[j - 1] + 1
        yield [pool[i] for i in indices]


def kiwi_nouns(kiwi_instance, text: str) -> list[str]:
    """Kiwi로 텍스트에서 명사(NNG, NNP)만 추출. 실패 시 빈 리스트."""
    if not kiwi_instance or not text:
        return []
    try:
        tokens = kiwi_instance.tokenize(text)
        return [t.form for t in tokens if t.tag in ('NNG', 'NNP') and len(t.form) >= 2]
    except Exception:
        return []


class DecoderExpert:
    """
    🔤 Decoder - Korean Slang Decoder
    
    Responsibilities:
    - Morphological analysis of abbreviations
    - Match search results to potential titles
    - Score candidates by decode quality
    - Identify author names vs work titles
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
        self.name = "Decoder"
        self.emoji = "🔤"
        # Kiwi 형태소 분석기 (후보 제목 명사 추출용)
        try:
            from kiwipiepy import Kiwi as _Kiwi
            self._kiwi = _Kiwi()
        except ImportError:
            self._kiwi = None
    
    def analyze(
        self,
        gatekeeper_result: Dict[str, Any],
        search_results: List[Dict[str, Any]],
        slang_dictionary: Dict[str, str],
        conversation_context: Optional[str] = None,
        session_knowledge: Optional[Dict[str, Any]] = None,  # NEW
        ctx: Optional[Any] = None,  # ConversationContext - suspected_titles 공유용
    ) -> Dict[str, Any]:
        """
        Decode detected terms using search results.
        
        Args:
            gatekeeper_result: Output from Gatekeeper stage
            search_results: Combined search results from all queries
            slang_dictionary: Pre-defined slang → title mappings
            conversation_context: Optional conversation history from other experts
            session_knowledge: Session-wide learned terms from previous posts
            
        Returns:
            DecoderResult with candidates, confidence scores, verification needs
            May include request_expert/request_reason for dynamic routing
        """
        start_time = time.time()
        
        # None 체크
        gatekeeper_result = gatekeeper_result or {}
        search_results = search_results or []
        slang_dictionary = slang_dictionary or {}
        session_knowledge = session_knowledge or {}
        
        post_id = gatekeeper_result.get("_post_id", "?")
        
        # Quick check: if no key terms, nothing to decode
        key_terms = gatekeeper_result.get("key_terms", [])
        if not key_terms:
            print(f"[{_ts()}][{self.emoji}] {self.name} 스킵: key_terms 없음", file=sys.stderr)
            return self._empty_result("key_terms 없음")
        
        # 🆕 Gatekeeper possible_titles를 key_terms에 병합
        # 복합어(예: '즉사무림이유백')가 key_terms에 없어도 해독 대상에 포함
        # ⚠️ OPT: n-gram 쓰레기 유입 방지 — 엄격한 품질 필터링
        _gk_entities = gatekeeper_result.get("detected_entities") or {}
        _gk_possible = _gk_entities.get("possible_titles") or [] if isinstance(_gk_entities, dict) else []
        existing_terms_set = set(key_terms)
        # 일반 어미/접미사 패턴 — 작품명이 아닌 문장 조각
        _SENTENCE_ENDINGS = ('하지만', '이지만', '했지만', '되지만', '겠지만',
                             '긴하지', '했는데', '인데', '인거', '했으면',
                             '는데', '지만', '해서', '인데')
        _SENTENCE_EXACT = {'예상된', '상된', '긴하', '하지', '지만', '스포'}
        for pt in _gk_possible:
            if not isinstance(pt, str):
                continue
            pt_clean = pt.strip()
            # 3글자 미만 스킵
            if len(pt_clean) < 3:
                continue
            # 공백/구두점 포함 → n-gram 쓰레기 → key_terms에는 넣지 않음
            if any(c in pt_clean for c in ' \t)(!?.,;:'):
                continue
            # 한글 2음절 이상 포함 요구
            korean_count = sum(1 for c in pt_clean if ord('가') <= ord(c) <= ord('힣'))
            if korean_count < 2:
                continue
            # 이미 있는 key_term의 부분문자열이면 스킵 (예: '즉사무' ⊂ '즉사무림')
            if any(pt_clean in existing for existing in existing_terms_set):
                continue
            # 기존 key_term을 포함하는 확장이면 스킵 (예: '전개긴하지' ⊃ '전개')
            if any(existing in pt_clean for existing in existing_terms_set if len(existing) >= 2):
                continue
            # 일반 문장 조각 패턴 스킵 (정확 매칭 또는 어미로 끝남)
            if pt_clean in _SENTENCE_EXACT:
                continue
            if any(pt_clean.endswith(ending) for ending in _SENTENCE_ENDINGS):
                continue
            # Kiwi로 명사 포함 여부 확인 — 명사 없으면 문장 조각
            if self._kiwi:
                try:
                    _tokens = self._kiwi.tokenize(pt_clean)
                    _has_noun = any(t.tag in ('NNG', 'NNP') and len(t.form) >= 2 for t in _tokens)
                    if not _has_noun:
                        continue
                except Exception:
                    pass
            if pt_clean not in existing_terms_set:
                key_terms.append(pt_clean)
                existing_terms_set.add(pt_clean)
        
        # 🆕 P0-4 v2: 축약어 경계 분리 전처리 (Kiwi + GK entity 기반)
        tagged_terms = self._try_split_abbreviation_boundary(key_terms, gatekeeper_result)
        
        # 🆕 P1-4: 반복 패턴 확장 전처리 (priority 2로 태그)
        plain_for_rep = [t for t, _ in tagged_terms]
        rep_expanded = self._expand_repetition_patterns(plain_for_rep)
        # 반복 패턴에서 새로 추가된 term에 priority 2 부여
        existing_set = {t for t, _ in tagged_terms}
        for rt in rep_expanded:
            if rt not in existing_set:
                tagged_terms.append((rt, 2))
                existing_set.add(rt)
        
        # 🆕 OPT-3: 우선순위 기반 토큰 관리
        # priority 0 = GK 원본 key_terms (최우선)
        # priority 1 = GK possible_titles
        # priority 2 = 분리/확장 후보 (가장 낮음)
        MAX_EXPANDED_TERMS = 12  # 원본 보존 위해 10→12로 소폭 확대
        if len(tagged_terms) > MAX_EXPANDED_TERMS:
            # priority 오름차순 정렬 후 상위 N개 선택
            tagged_terms.sort(key=lambda x: x[1])
            dropped = tagged_terms[MAX_EXPANDED_TERMS:]
            tagged_terms = tagged_terms[:MAX_EXPANDED_TERMS]
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ 토큰 수 제한: "
                f"{len(tagged_terms) + len(dropped)}개 → {MAX_EXPANDED_TERMS}개 "
                f"(dropped: {[t for t, _ in dropped]})",
                file=sys.stderr,
            )
        key_terms = [t for t, _ in tagged_terms]
        
        # NEW: Check session knowledge first (최우선)
        session_matches = self._check_session_knowledge(key_terms, session_knowledge)
        if session_matches:
            print(f"[{_ts()}][{self.emoji}] 🎯 세션 지식 매칭: {len(session_matches)}건", file=sys.stderr)
        
        # Check dictionary first for direct matches
        dict_matches = self._check_dictionary(key_terms, slang_dictionary)
        
        # ── 프롬프트 토큰 예산 관리 ──
        # 서버: -c 65536 -np 1 → 슬롯당 65,536 토큰
        # 한영 혼합 기준 ~2.2자/토큰, max_tokens=512 출력 예약
        # → 입력 = (65,536 - 512) × 2.2 ≈ 143,053자
        # 시스템 프롬프트 ~18,138자 제외 → user_prompt ≈ 125,000자
        # 다만 너무 긴 프롬프트는 LLM 품질 저하 → 실용적 상한 60,000자
        _USER_PROMPT_BUDGET = 60_000
        
        def _truncate_search_results(results: list, max_snippet_len: int, max_results: int) -> list:
            """검색 결과 snippet 길이와 건수를 제한"""
            truncated = []
            for r in results[:max_results]:
                r_copy = dict(r)
                snippet = r_copy.get("snippet", "") or r_copy.get("content", "") or ""
                if len(snippet) > max_snippet_len:
                    r_copy["snippet"] = snippet[:max_snippet_len] + "..."
                    if "content" in r_copy:
                        r_copy["content"] = r_copy["content"][:max_snippet_len] + "..."
                truncated.append(r_copy)
            return truncated
        
        _gk_json = json.dumps(gatekeeper_result, ensure_ascii=False, indent=2)
        _dict_json = json.dumps(slang_dictionary, ensure_ascii=False, indent=2)
        
        # DECODER_PROMPT 템플릿 고정 텍스트 크기 측정 (변수 제외)
        _template_fixed_len = len(DECODER_PROMPT) - len("{gatekeeper_json}") - len("{search_results_json}") - len("{slang_dictionary}")
        # 검색 결과에 쓸 수 있는 예산 (추가 섹션은 최종 가드에서 관리)
        _sr_budget = _USER_PROMPT_BUDGET - _template_fixed_len - len(_gk_json) - len(_dict_json)
        print(f"[{_ts()}][{self.emoji}] 토큰 예산: user_budget={_USER_PROMPT_BUDGET:,}, "
              f"tpl_fixed={_template_fixed_len:,}, gk={len(_gk_json):,}, dict={len(_dict_json):,} "
              f"→ sr_budget={_sr_budget:,}", file=sys.stderr)
        
        # 검색 결과를 예산에 맞게 단계적 축소
        _LEVELS = [
            (300, 15),  # snippet 300자, 최대 15건
            (200, 10),
            (150, 8),
            (100, 6),
            (80, 5),
        ]
        _sr_for_prompt = search_results[:15]
        _sr_json = json.dumps(_sr_for_prompt, ensure_ascii=False, indent=2)
        
        for _max_snip, _max_n in _LEVELS:
            if len(_sr_json) <= max(1, _sr_budget):
                break
            _sr_for_prompt = _truncate_search_results(search_results, _max_snip, _max_n)
            _sr_json = json.dumps(_sr_for_prompt, ensure_ascii=False, indent=2)
        
        if len(_sr_json) > max(1, _sr_budget):
            # 최후 수단: snippet 60자, 3건
            _sr_for_prompt = _truncate_search_results(search_results, 60, 3)
            _sr_json = json.dumps(_sr_for_prompt, ensure_ascii=False, indent=2)
            print(f"[{_ts()}][{self.emoji}] ⚠️ 검색 결과 최소화: {len(search_results)}→3건, "
                  f"snippet≤60자 (예산={_sr_budget:,}, 실제={len(_sr_json):,})", file=sys.stderr)
        
        # Format prompt
        context_section = ""
        if conversation_context:
            context_section = f"\n\n=== CONVERSATION HISTORY ===\n{conversation_context}\n"
        
        # NEW: Add session knowledge section
        session_section = ""
        if session_knowledge.get("resolved_slang"):
            session_section = f"\n\n=== SESSION KNOWLEDGE (이미 학습된 용어) ===\n"
            session_section += "이번 배치에서 이미 확인된 약칭들:\n"
            for slang, info in session_knowledge["resolved_slang"].items():
                session_section += f"  - '{slang}' → '{info['official_title']}' (confidence: {info['confidence']})\n"
            session_section += "\n⚠️ 위 약칭이 나오면 즉시 매칭하세요. 다시 검색할 필요 없습니다.\n"
        
        user_prompt = DECODER_PROMPT.format(
            gatekeeper_json=_gk_json,
            search_results_json=_sr_json,
            slang_dictionary=_dict_json,
        ) + context_section + session_section
        
        # 🔥 Discourse 역방향 경고: non-novel 도메인 판정 시 Decoder에게 경고
        if ctx and getattr(ctx, 'discourse_warning', None):
            _dw = getattr(ctx, 'discourse_warning', '')
            _is_genre_disc = 'genre_discussion' in _dw or 'discuss_genre' in _dw
            user_prompt += f"\n\n=== ⚠️ DISCOURSE DOMAIN WARNING ===\n"
            user_prompt += f"DiscourseAnalyzer 판정: {_dw}\n"
            user_prompt += f"의도(intent): {getattr(ctx, 'discourse_intent', 'unknown')}\n\n"
            if _is_genre_disc:
                # 장르/트로프 일반론 경고 — 특화 메시지
                user_prompt += "🚨 이 포스트는 특정 소설이 아니라 '장르/트로프/클리셰'에 대한 일반적 토론일 가능성이 높습니다.\n"
                user_prompt += "제목이나 본문의 주제어가 장르·트로프 관련 일반 개념어인 경우,\n"
                user_prompt += "검색에서 우연히 비슷한 키워드의 소설이 발견되더라도 그것이 이 포스트의 실제 주제인지 엄격히 확인하세요.\n"
                user_prompt += "판단 기준: 본문/댓글에 해당 소설의 고유 정보(작가명, 플랫폼, 회차, 캐릭터 고유명, 줄거리)가 있는가?\n"
                user_prompt += "고유 정보가 없으면 → best_match.title=null, confidence=none으로 판정하세요.\n"
            else:
                user_prompt += "🚨 이 포스트는 소설/웹소설과 무관한 밈/유머/일상 포스트일 가능성이 높습니다.\n"
                user_prompt += "핵심 키워드가 커뮤니티 자체 은어(예: 장붕=장르소설갤 유저, 겜붕=게임갤 유저, 완장=갤러리 관리자)일 수 있습니다.\n"
                user_prompt += "검색 결과에서 해당 단어가 소설 '캐릭터 이름'으로 나오더라도, 그것이 이 포스트의 맥락과 일치하는지 엄격히 확인하세요.\n"
                user_prompt += "본문/댓글에 작품 줄거리·작가명·플랫폼 URL이 전혀 없으면 → best_match.title=null, confidence=none으로 판정하세요.\n"

        # 🆕 BUG-4: 복합 축약어 분리 힌트
        # "즉사무림이유백" = 작품약어+캐릭터명 결합 — LLM에게 분리 시도 안내
        user_prompt += "\n\n=== COMPOUND TERM HINT ===\n"
        user_prompt += "키워드가 4음절 이상이고 공백이 없으면, [작품 약어 + 캐릭터/작가명]이 결합된 형태일 수 있습니다.\n"
        user_prompt += "예: '즉사무림이유백' → '즉사무림'(작품 약어) + '이유백'(캐릭터명)\n"
        user_prompt += "예: '망겜성황건욱' → '망겜성'(작품 약어) + '황건욱'(캐릭터명)\n"
        user_prompt += "이 경우 morphemes를 ['즉사무림', '이유백'] 형태로 분리하여 보고하세요.\n"
        user_prompt += "'갤' 접미사는 DC인사이드 갤러리 약어일 수 있습니다 (예: 아생갤 → 아카데미에서 생존하기 갤러리).\n"
        
        # 이전 검색 쿼리 이력 전달 (중복 검색 방지)
        if ctx and hasattr(ctx, 'searched_queries') and ctx.searched_queries:
            searched_list = sorted(ctx.searched_queries)
            user_prompt += f"\n\n=== PREVIOUS SEARCHES (이미 실행된 검색 쿼리) ===\n"
            for q in searched_list:
                user_prompt += f"  - {q}\n"
            user_prompt += "\n⚠️ verification_search 요청 시 위 쿼리는 이미 실행되었으므로 중복 요청하지 마세요.\n"
            user_prompt += "다른 관점/키워드로 새로운 쿼리를 작성하세요.\n"
        
        # 🔬 Deep Search Hints: snippet/URL 페칭에서 추출한 제목/작가/약칭 정보 제공
        if ctx and hasattr(ctx, 'snippet_hints') and ctx.snippet_hints:
            hints = ctx.snippet_hints
            has_hints = hints.get("title_hints") or hints.get("author_hints") or hints.get("abbreviation_hints")
            if has_hints:
                user_prompt += "\n\n=== 🔬 DEEP SEARCH HINTS (검색 결과 코드 분석) ===\n"
                user_prompt += "아래는 검색 결과의 snippet/페이지에서 코드가 자동 추출한 정보입니다.\n"
                user_prompt += "이 정보를 참고하여 약칭 해석 정확도를 높이세요.\n\n"
                
                if hints.get("title_hints"):
                    user_prompt += "📖 발견된 소설 제목 후보:\n"
                    seen = set()
                    for h in hints["title_hints"][:8]:
                        t = h.get("title", "")
                        if t and t not in seen:
                            seen.add(t)
                            src = h.get("source", "")
                            user_prompt += f"  - \"{t}\" (출처: {src})\n"
                    user_prompt += "\n"
                
                if hints.get("author_hints"):
                    user_prompt += "✍️ 발견된 작가명 후보:\n"
                    seen = set()
                    for h in hints["author_hints"][:5]:
                        n = h.get("name", "")
                        if n and n not in seen:
                            seen.add(n)
                            user_prompt += f"  - \"{n}\"\n"
                    user_prompt += "\n"
                
                if hints.get("abbreviation_hints"):
                    user_prompt += "📌 발견된 약칭 매핑:\n"
                    for h in hints["abbreviation_hints"][:5]:
                        user_prompt += f"  - '{h.get('abbrev', '')}' → '{h.get('full', '')}'\n"
                    user_prompt += "\n"
                
                user_prompt += "⚠️ 위 힌트는 코드 자동 추출이므로 오류가 있을 수 있습니다. 검색 결과 원문과 교차 확인하세요.\n"
        
        # 🔄 증거 기반 맥락 추론 (Evidence-Based Context Reasoning)
        # 검색으로 발견한 사실(약칭→제목, 인물=캐릭터/작가)을 토대로
        # 본문/댓글을 다시 읽고, 글의 실제 맥락을 LLM이 자유롭게 추론하도록 유도
        _do_reasoning = False
        _resolved_mappings = []
        _gk_characters = []
        _gk_authors = []
        _post_title_r = ""
        
        if ctx:
            post_data = getattr(ctx, 'post_data', {}) or {}
            _post_title_r = post_data.get('title', '')
            gk_out = getattr(ctx, 'gatekeeper_result', None)
            if not gk_out:
                gk_out = gatekeeper_result
            _gk_entities = (gk_out.get('detected_entities') or {}) if isinstance(gk_out, dict) else {}
            _gk_characters = _gk_entities.get('possible_characters', []) or []
            _gk_titles = _gk_entities.get('possible_titles', []) or []
            _gk_authors = _gk_entities.get('possible_authors', []) or []
            
            # 약칭 매핑 수집
            if hasattr(ctx, 'snippet_hints') and ctx.snippet_hints:
                for ah in ctx.snippet_hints.get('abbreviation_hints', []):
                    abbrev = ah.get('abbrev', '')
                    full = ah.get('full', '')
                    if abbrev and full:
                        _resolved_mappings.append((abbrev, full))
            
            for term in (_gk_titles + [_post_title_r]):
                if isinstance(term, str):
                    import re as _re_reinterpret
                    t_clean = _re_reinterpret.sub(r'[^\uac00-\ud7a3]', '', term)
                    if t_clean and t_clean in KNOWN_ABBREVIATIONS:
                        full_title = KNOWN_ABBREVIATIONS[t_clean]
                        if (t_clean, full_title) not in _resolved_mappings:
                            _resolved_mappings.append((t_clean, full_title))
            
            _do_reasoning = True  # 상시 활성화: 매핑 없어도 LLM이 자체 추론
        
        # 🆕 _resolved_mappings를 ctx에 저장 (suspected_titles 폴백용)
        if ctx:
            ctx._resolved_mappings = _resolved_mappings
            ctx._resolved_authors = _gk_authors
        
        if _do_reasoning:
            # --- 본문/댓글 원문 텍스트 수집 ---
            _body_parts = []
            for block in post_data.get('content_blocks', []):
                if isinstance(block, dict) and block.get('text'):
                    _body_parts.append(block['text'])
            _body_text = " ".join(_body_parts).strip()
            _comments_raw = getattr(ctx, 'comments', []) or []
            _comments_text = " / ".join(c for c in _comments_raw if isinstance(c, str) and c.strip())
            
            # --- 로그 ---
            _entities_info = []
            if _gk_characters:
                _entities_info.append(f"캐릭터={_gk_characters[:3]}")
            if _gk_authors:
                _entities_info.append(f"작가={_gk_authors[:3]}")
            _mappings_str = str(_resolved_mappings[:3]) if _resolved_mappings else "없음"
            print(f"[{_ts()}][{self.emoji}] 🔄 증거 기반 맥락 추론 주입: 매핑={_mappings_str}, {', '.join(_entities_info) if _entities_info else '엔티티 없음'}", file=sys.stderr)
            
            # --- 프롬프트 구성: 자유 추론 방식 ---
            user_prompt += "\n\n=== 🔄 증거 기반 맥락 추론 (Evidence-Based Context Reasoning) ===\n"
            user_prompt += "검색을 통해 아래 사실들이 발견되었습니다.\n"
            user_prompt += "이 사실들을 원문에 대입하여, 글의 실제 의미와 맥락을 추론하세요.\n\n"
            
            # 발견된 사실 정리
            user_prompt += "📌 발견된 사실:\n"
            if _resolved_mappings:
                for abbrev, full in _resolved_mappings[:3]:
                    user_prompt += f"  • '{abbrev}' = '{full}' (약칭 → 정식 제목)\n"
            if _gk_characters:
                user_prompt += f"  • 본문/제목에서 감지된 인물명: {_gk_characters}\n"
            if _gk_authors:
                user_prompt += f"  • 본문/제목에서 감지된 작가명 후보: {_gk_authors}\n"
            if not _resolved_mappings and not _gk_characters and not _gk_authors:
                user_prompt += "  • (사전 발견된 매핑/인물 없음 — 검색 결과와 본문을 직접 대조하여 스스로 추론하세요)\n"
            
            # 원문 텍스트 다시 제시
            user_prompt += f"\n📝 원문 다시 읽기:\n"
            user_prompt += f"  제목: {_post_title_r}\n"
            if _body_text:
                user_prompt += f"  본문: {_body_text[:300]}\n"
            if _comments_text:
                user_prompt += f"  댓글: {_comments_text[:300]}\n"
            
            # 자유 추론 지시
            user_prompt += "\n🧠 **추론 과제 (매우 중요!):**\n"
            user_prompt += "위 사실들을 원문에 대입하여 다음을 단계별로 추론하세요:\n\n"
            user_prompt += "**Pre-Step — 제목+본문 연결 읽기 (MANDATORY):**\n"
            user_prompt += "커뮤니티 게시글의 제목과 본문은 하나의 연속된 발화입니다.\n"
            user_prompt += "제목에는 핵심 주제(작품명/캐릭터명/작가명), 본문에는 관련 감정/의견/내용이 담깁니다.\n"
            user_prompt += "예시: 제목='즉사무림 은영이 너무 불쌍해' + 본문='어렵게 생긴 가족을 위해 죽는다니'\n"
            user_prompt += "→ '즉사무림'이라는 작품의 '은영'이라는 캐릭터가 불쌍하다. 가족을 어렵게 얻었는데 죽는다니.\n"
            user_prompt += "제목만 보고 판단하지 말고, 제목+본문을 하나로 이어서 읽으세요.\n\n"
            user_prompt += "**Step 0 — 다중 해석 열거 (MANDATORY):**\n"
            user_prompt += "각 key_term에 대해, 검색 결과에서 발견된 **모든 가능한 해석**을 열거하세요.\n"
            user_prompt += "한 가지 해석에 고착하지 마세요!\n"
            user_prompt += "같은 용어가 작가명이자 일반 명사일 수 있고, 작품 약칭이자 장르 용어일 수 있습니다.\n"
            user_prompt += "각 해석별로 본문 맥락과의 적합도(context_fit)를 평가하세요.\n"
            user_prompt += "→ interpretations 배열에 모든 해석을 기록하세요.\n\n"
            user_prompt += "**Step 1 — 용어 치환 읽기:**\n"
            user_prompt += "약칭/인물명을 실제 의미로 치환하면 이 글이 무슨 뜻인가?\n"
            user_prompt += "발견된 사실(약칭→정식제목, 인물→작가/캐릭터)을 원문에 대입하여 읽으세요.\n\n"
            user_prompt += "**Step 2 — 맥락 추론:**\n"
            user_prompt += "치환 후 글 전체를 다시 읽고, 글쓴이의 **의도**를 추론하라.\n"
            user_prompt += "- 작품의 줄거리/캐릭터에 대한 논의인가?\n"
            user_prompt += "- 작가에 대한 팬 반응(응원, 연재 기원, 불만 등)인가?\n"
            user_prompt += "- 작품 추천/비교인가?\n"
            user_prompt += "- 작품과 무관한 밈/은어인가?\n"
            user_prompt += "- 본문+댓글의 전체 분위기에서 어떤 해석이 가장 자연스러운가?\n\n"
            user_prompt += "**Step 3 — 인물 역할 판정:**\n"
            user_prompt += "검색 결과를 참고하여 인물명의 역할을 확인하라.\n"
            user_prompt += "- 등장인물로 확인 → anchor_type='character_mention', is_grounded=true\n"
            user_prompt += "- 작가로 확인 → is_author_name=true, author_info 기록\n"
            user_prompt += "- 작가명이 본문에 있고 + 해당 작품 약칭도 있으면 → is_grounded=true (작품 식별 증거)\n\n"
            user_prompt += "**Step 4 — 결론:**\n"
            user_prompt += "추론 결과를 notes 필드에 '치환 읽기 → 맥락 추론 → 결론' 형태로 간결하게 기록하세요.\n"
        
        # �🌐 Fetched Page Info: URL 페칭으로 얻은 구조적 정보
        if ctx and hasattr(ctx, 'fetched_page_info') and ctx.fetched_page_info:
            user_prompt += "\n\n=== 🌐 FETCHED PAGE INFO (공식 페이지 분석) ===\n"
            user_prompt += "아래는 나무위키/공식 플랫폼 페이지에서 추출한 정보입니다.\n\n"
            for fi in ctx.fetched_page_info[:3]:
                url = fi.get("url", "")
                structured = fi.get("structured_info", {})
                preview = fi.get("text_preview", "")
                user_prompt += f"URL: {url}\n"
                if structured:
                    for k, v in structured.items():
                        if v and k != "text_preview":
                            user_prompt += f"  {k}: {v}\n"
                if preview:
                    user_prompt += f"  내용 미리보기: {preview[:300]}\n"
                user_prompt += "\n"
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 분석 시작: terms={key_terms}", file=sys.stderr)
        
        # ── 최종 프롬프트 크기 가드 ──
        # user_prompt가 예산을 초과하면 추가 섹션부터 점진적으로 제거
        if len(user_prompt) > _USER_PROMPT_BUDGET:
            _over = len(user_prompt) - _USER_PROMPT_BUDGET
            print(f"[{_ts()}][{self.emoji}] ⚠️ user_prompt 초과 ({len(user_prompt):,}자 > "
                  f"{_USER_PROMPT_BUDGET:,}), {_over:,}자 초과 → 재축소", file=sys.stderr)
            
            # 검색 결과를 최소화하여 user_prompt 재구성
            _sr_for_prompt = _truncate_search_results(search_results, max_snippet_len=80, max_results=5)
            _sr_json_min = json.dumps(_sr_for_prompt, ensure_ascii=False, indent=2)
            user_prompt = DECODER_PROMPT.format(
                gatekeeper_json=_gk_json,
                search_results_json=_sr_json_min,
                slang_dictionary=_dict_json,
            )
            # 핵심 정보만 최소한으로 추가
            if ctx and getattr(ctx, 'discourse_warning', None):
                user_prompt += f"\n\n⚠️ DISCOURSE WARNING: {getattr(ctx, 'discourse_warning', '')}\n"
            # Deep Search Hints는 가장 중요한 약칭 매핑만
            if _resolved_mappings:
                user_prompt += "\n📌 약칭 매핑:\n"
                for abbrev, full in _resolved_mappings[:2]:
                    user_prompt += f"  • '{abbrev}' = '{full}'\n"
            if _gk_characters:
                user_prompt += f"📌 감지된 인물명: {_gk_characters[:3]}\n"
            
            # 그래도 초과하면 최후 수단
            if len(user_prompt) > _USER_PROMPT_BUDGET:
                _sr_for_prompt = _truncate_search_results(search_results, 50, 3)
                _sr_json_min = json.dumps(_sr_for_prompt, ensure_ascii=False, indent=2)
                user_prompt = DECODER_PROMPT.format(
                    gatekeeper_json=_gk_json,
                    search_results_json=_sr_json_min,
                    slang_dictionary=_dict_json,
                )
                print(f"[{_ts()}][{self.emoji}] ⚠️ 최후 축소: user_prompt={len(user_prompt):,}자", file=sys.stderr)
        
        print(f"[{_ts()}][{self.emoji}] 최종 user_prompt={len(user_prompt):,}자 "
              f"(budget={_USER_PROMPT_BUDGET:,})", file=sys.stderr)
        
        try:
            result = self._call_llm(user_prompt)
            elapsed = time.time() - start_time
            
            # Merge dictionary matches with LLM result
            # 🔥 ctx 전달: 사전값도 검색 결과로 교정 가능하도록
            result = self._merge_dict_matches(result, dict_matches, ctx)
            
            # 🔥 decoded_terms 타입 안전 정제: LLM이 깨진 JSON을 반환하면
            # decoded_terms에 dict가 아닌 str 등이 섞일 수 있음 → 제거
            raw_terms = result.get("decoded_terms", [])
            if raw_terms:
                cleaned = [t for t in raw_terms if isinstance(t, dict)]
                if len(cleaned) < len(raw_terms):
                    print(f"[{_ts()}][{self.emoji}] ⚠️ decoded_terms 타입 정제: "
                          f"{len(raw_terms)}건 → {len(cleaned)}건 (비-dict 항목 제거)",
                          file=sys.stderr)
                    result["decoded_terms"] = cleaned
            
            # 제안 2: Decoder의 신뢰도를 ctx에 저장
            if ctx:
                confidence_str = result.get("overall_confidence", "medium")
                confidence_map = {"high": 0.85, "max": 0.95, "medium": 0.6, "low": 0.3}
                ctx.expert_confidence["decoder"] = confidence_map.get(confidence_str, 0.6)
            
            # 🔥 커뮤니티 제목 방어: LLM이 dcinside/arca 게시글 제목을 공식 제목으로 착각한 경우 교정
            if ctx:
                result = self._guard_community_title(result, ctx)
            
            # 🔥 플랫폼 URL 기반 제목 교정: candidate URL의 공식 제목과 불일치 시 교정
            if ctx:
                result = self._correct_title_from_platform_url(result, ctx)
            
            # 🔥 플랫폼 기능 가드: 노피아+콘/뱃지 조합이면 meta 강제 (소설 아님)
            if ctx:
                result = self._guard_platform_feature_as_title(result, ctx)
            
            # 🔥 연상 패턴 가드: "X이란 단어가 떠올랐" → X는 제목 아님
            if ctx:
                result = self._guard_association_pattern(result, ctx)
            
            # 🔥 장르 교차검증: 본문 장르와 후보 작품 장르 불일치 시 confidence 하향
            if ctx:
                result = self._validate_genre_cross_match(result, ctx)
            
            # 🔥 작가명=약칭 rescue: is_author_name인데 검색 결과에서 작품 약칭 증거 발견 시 전환
            if ctx:
                result = self._rescue_author_as_work_abbreviation(result, ctx)
            
            # 🔥 형태소 매칭 검증: 축약어의 형태소가 후보 제목에 실제 포함되는지 확인
            if ctx:
                result = self._validate_morpheme_in_title(result, ctx)
            
            # 🔥 작가+신작 안전처리: 작가는 식별했지만 제목이 장르 용어/아키타입인 경우 차단
            if ctx:
                result = self._guard_archetype_as_title(result, ctx)
            
            # 🔥 Discourse 역방향 Override: non-novel 도메인(high)이면 Decoder 신뢰도 강제 하향
            if ctx and getattr(ctx, 'discourse_warning', None):
                result = self._apply_discourse_warning(result, ctx)
            
            # 🔥 본문 증거 검증: best_match가 있지만 본문에 작품 관련 증거가 전혀 없으면 confidence 하향
            if ctx:
                result = self._guard_no_body_evidence(result, gatekeeper_result, ctx)
            
            best = self._get_best_candidate(result)
            print(f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
                  f"best_match={best}, confidence={result.get('overall_confidence')}", 
                  file=sys.stderr)
            
            # ⭐ suspected_titles 초기 생성 (Decoder가 첫 번째로 생성)
            if ctx:
                self._init_suspected_titles(result, ctx)
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{_ts()}][{self.emoji}] {self.name} 오류 ({elapsed:.1f}s): {e}", file=sys.stderr)
            return self._empty_result(str(e))
    
    def _check_session_knowledge(self, terms: List[str], session_knowledge: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        NEW: Check if any term exists in session knowledge (learned from previous posts)
        세션 지식에서 이미 학습된 약칭 확인
        """
        matches = []
        resolved_slang = session_knowledge.get("resolved_slang", {})
        
        for term in terms:
            term_lower = term.lower().strip()
            if term_lower in resolved_slang:
                info = resolved_slang[term_lower]
                matches.append({
                    "slang": term,
                    "official_title": info["official_title"],
                    "confidence": info.get("confidence", "medium"),
                    "source": "session_knowledge"
                })
        
        return matches
    
    # ── OPT-4: 외래어(한글 표기 일본어 등) 탐지용 패턴 ──
    # 카타카나→한글 전사에서 자주 나타나는 음절 조합
    _FOREIGN_SYLLABLE_PAIRS = {
        "쿠가", "소우", "도쿠", "스케", "스카", "시키", "루카", "카이",
        "미야", "사키", "나기", "하루", "유키", "나루", "사쿠", "마루",
        "타이", "키리", "테루", "노아", "코우", "스이", "츠키", "카미",
        "아오", "이치", "오카", "시마", "모토", "카와", "무라",
    }

    def _is_likely_foreign_transcription(self, term: str) -> bool:
        """
        OPT-4: 한글로 표기된 외래어(일본어/영어 등) 감지.
        이런 단어는 분리하면 의미 없는 쓰레기만 생기므로 분리 스킵.

        판정 기준:
        1. Kiwi가 단일 NNP(고유명사)로 인식 → 외래어 가능성 높음
        2. 카타카나 전사 특유의 음절쌍이 2개 이상 포함
        """
        # 기준 1: Kiwi 형태소 분석 — 단일 NNP면 분리 불필요
        if self._kiwi:
            try:
                tokens = self._kiwi.tokenize(term)
                # 실질 형태소(조사/어미 제외)가 1개뿐이면 단일 고유명사
                content_tokens = [t for t in tokens if t.tag.startswith('N') or t.tag.startswith('V')]
                if len(content_tokens) <= 1:
                    return True
            except Exception:
                pass

        # 기준 2: 외래어 전사 음절쌍 빈도
        foreign_hit = 0
        for i in range(len(term) - 1):
            pair = term[i:i+2]
            if pair in self._FOREIGN_SYLLABLE_PAIRS:
                foreign_hit += 1
        # 전체 길이 대비 30% 이상이면 외래어 판정
        if len(term) >= 4 and foreign_hit >= max(2, len(term) * 0.3):
            return True

        return False

    def _try_split_abbreviation_boundary(
        self, terms: List[str], gatekeeper_result: Dict[str, Any] | None = None,
    ) -> List[tuple]:
        """
        🆕 P0-4 v2: 축약어 경계 분리 알고리즘 (Kiwi + GK entity 기반)

        반환값: [(term_str, priority)] 리스트
          priority: 0 = GK 원본, 1 = GK possible_title, 2 = 분리 후보

        개선 사항 (OPT-1~4):
        - OPT-1: Kiwi 형태소 분석으로 명사 경계에서만 분리
        - OPT-2: GK possible_characters 기반 정밀 분리
        - OPT-3: priority 태그로 토큰 관리 (호출부에서 정렬)
        - OPT-4: 외래어 탐지로 불필요 분리 차단
        """
        gatekeeper_result = gatekeeper_result or {}
        gk_entities = gatekeeper_result.get("detected_entities") or {}
        gk_characters = set(gk_entities.get("possible_characters") or [])

        # priority 0 = 원본 GK key_term
        expanded: list[tuple] = []

        for term in terms:
            term_clean = term.strip()
            if not term_clean:
                continue

            # 한글만 처리 (영문/숫자 혼합은 Skip)
            if not all(ord('가') <= ord(c) <= ord('힣') or c.isspace() for c in term_clean):
                expanded.append((term_clean, 0))
                continue

            syllable_count = len(term_clean)

            # 5음절 미만이면 분리 불필요
            if syllable_count < 5:
                expanded.append((term_clean, 0))
                continue

            # ── OPT-4: 외래어 감지 → 분리 스킵 ──
            if self._is_likely_foreign_transcription(term_clean):
                expanded.append((term_clean, 0))
                print(
                    f"[{_ts()}][{self.emoji}] 🌐 외래어 감지 스킵: '{term_clean}'",
                    file=sys.stderr,
                )
                continue

            split_found = False

            # ── OPT-2: GK possible_characters 기반 분리 ──
            # 뒷부분이 GK가 감지한 캐릭터 이름과 일치하면 정밀 분리
            for char_name in gk_characters:
                if len(char_name) < 2:
                    continue
                if term_clean.endswith(char_name) and len(term_clean) > len(char_name):
                    abbrev_part = term_clean[: -len(char_name)]
                    if len(abbrev_part) >= 2:
                        expanded.append((term_clean, 0))  # 원본 보존
                        expanded.append((abbrev_part, 2))
                        expanded.append((char_name, 2))
                        split_found = True
                        print(
                            f"[{_ts()}][{self.emoji}] 🎯 GK캐릭터 분리: "
                            f"'{term_clean}' → '{abbrev_part}' + '{char_name}'",
                            file=sys.stderr,
                        )
                        break

            if split_found:
                continue

            # ── OPT-1: Kiwi 형태소 분석 기반 분리 ──
            # 핵심: 조사(JKS/JX/JKO..), 접미사(XSN), 어미(E*) 위치가
            # 실제 단어 경계를 나타냄 (예: "즉사무림이유백" → 이/JKS at 4)
            if self._kiwi:
                try:
                    tokens = self._kiwi.tokenize(term_clean)

                    # 전략 1: 조사/접미사/어미 경계에서 분리
                    # 조사(J*) → 조사의 start가 분리점 (조사는 뒤쪽 단어의 일부)
                    # 접미사(XSN/XSA/XSV) → 접미사 뒤(start+len)가 분리점 (접미사는 앞 단어에 붙음)
                    josa_tags = {'JKS', 'JKO', 'JKB', 'JKG', 'JKC', 'JKV', 'JX', 'JC'}
                    suffix_tags = {'XSN', 'XSA', 'XSV'}
                    split_positions: list[int] = []
                    for t in tokens:
                        if t.tag in josa_tags:
                            # 조사의 시작 = 앞 단어의 끝 = 분리점
                            sp = t.start
                            if 2 <= sp <= syllable_count - 2:
                                split_positions.append(sp)
                        elif t.tag in suffix_tags:
                            # 접미사 뒤 = 분리점 ("전지적" 뒤에서 분리)
                            sp = t.start + len(t.form)
                            if 2 <= sp <= syllable_count - 2:
                                split_positions.append(sp)

                    # 중복 제거 & 정렬
                    split_positions = sorted(set(split_positions))

                    for sp in split_positions:
                        abbrev_part = term_clean[:sp]
                        remainder = term_clean[sp:]
                        if len(abbrev_part) >= 2 and len(remainder) >= 2:
                            expanded.append((term_clean, 0))
                            expanded.append((abbrev_part, 2))
                            expanded.append((remainder, 2))
                            split_found = True
                            tag_info = [f'{t.form}/{t.tag}' for t in tokens]
                            print(
                                f"[{_ts()}][{self.emoji}] 🔬 Kiwi 경계 분리: "
                                f"'{term_clean}' → '{abbrev_part}' + '{remainder}' "
                                f"(형태소: {tag_info})",
                                file=sys.stderr,
                            )
                            break  # 첫 번째 유효 경계만 사용

                    # 전략 2: 조사가 없으면 명사 경계로 폴백
                    if not split_found:
                        noun_tokens = [
                            t for t in tokens
                            if t.tag in ('NNG', 'NNP') and len(t.form) >= 2
                        ]
                        if len(noun_tokens) >= 2:
                            # 두 번째 명사의 시작점에서 분리
                            sp2 = noun_tokens[1].start
                            if 2 <= sp2 <= syllable_count - 2:
                                abbrev_part = term_clean[:sp2]
                                remainder = term_clean[sp2:]
                                if len(abbrev_part) >= 2 and len(remainder) >= 2:
                                    expanded.append((term_clean, 0))
                                    expanded.append((abbrev_part, 2))
                                    expanded.append((remainder, 2))
                                    split_found = True
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔬 Kiwi 명사경계 분리: "
                                        f"'{term_clean}' → '{abbrev_part}' + '{remainder}'",
                                        file=sys.stderr,
                                    )

                except Exception as e:
                    print(
                        f"[{_ts()}][{self.emoji}] ⚠️ Kiwi 분리 실패: '{term_clean}' → {e}",
                        file=sys.stderr,
                    )

            # ── 폴백: 기존 위치 기반 분리 (Kiwi 없거나 실패 시) ──
            if not split_found:
                # Kiwi가 없거나 분리점을 못 찾은 경우에만 기계적 분리
                fallback_candidates = []
                for split_at in [3, 4]:
                    if split_at >= syllable_count:
                        continue
                    abbrev_part = term_clean[:split_at]
                    remainder = term_clean[split_at:]
                    if 2 <= len(remainder) <= 4:
                        fallback_candidates.append((abbrev_part, remainder))

                if fallback_candidates:
                    expanded.append((term_clean, 0))
                    for abbrev, char_name in fallback_candidates:
                        expanded.append((abbrev, 2))
                        if len(char_name) >= 3:
                            expanded.append((char_name, 2))
                    print(
                        f"[{_ts()}][{self.emoji}] 🔀 폴백 분리: '{term_clean}' "
                        f"({syllable_count}음절) → {len(fallback_candidates)}개 후보",
                        file=sys.stderr,
                    )
                else:
                    expanded.append((term_clean, 0))

        # 중복 제거 (term 기준, 더 높은 priority 유지)
        seen: dict[str, int] = {}
        for term_str, prio in expanded:
            if term_str not in seen or prio < seen[term_str]:
                seen[term_str] = prio
        return [(t, p) for t, p in seen.items()]
    
    def _expand_repetition_patterns(self, terms: List[str]) -> List[str]:
        """
        🆕 P1-4: 반복 패턴 확장 알고리즘
        
        [음절반복] → [단어 반복] 확장
        
        원칙 (PROMPT_GUIDELINES.md 준수):
        - 특정 패턴 하드코딩 금지
        - 언어학적 원리: 한글 음절 반복 패턴 감지
        - 반복 = 강조 표현 (consecutive same syllables)
        
        패턴 분석:
        - 연속 동일 음절 ≥ 2회 → 반복 패턴으로 인식
        - 음절 + "아" 형태로 확장 (일반적 어미 패턴)
        - 구조: [접두][음절×N] → [접두] [음절아]×N
        """
        expanded_terms = []
        
        for term in terms:
            # 한글만 처리
            if not all(ord('가') <= ord(c) <= ord('힣') or c.isspace() for c in term):
                expanded_terms.append(term)
                continue
            
            term_clean = term.strip()
            syllable_count = len(term_clean)
            
            # 3음절 이상만 처리 (너무 짧으면 패턴 판별 어려움)
            if syllable_count < 3:
                expanded_terms.append(term)
                continue
            
            # 연속된 동일 음절 감지
            repetition_found = False
            expanded_version = ""
            i = 0
            
            while i < syllable_count:
                current = term_clean[i]
                
                # 다음 음절이 같은지 확인
                consecutive_count = 1
                while i + consecutive_count < syllable_count and term_clean[i + consecutive_count] == current:
                    consecutive_count += 1
                
                # 2회 이상 반복이면 패턴으로 간주
                if consecutive_count >= 2:
                    repetition_found = True
                    # 첫 음절은 원래 단어일 가능성 높음
                    if i == 0:
                        # "좋좋좋" → 첫 "좋"은 원래 단어, 나머지는 반복
                        expanded_version += current  # 원래 위치
                        i += 1
                    else:
                        # "마좋좋좋" → "마" + "좋아 좋아 좋아"
                        # 연속 음절을 "X아 X아 X아" 형태로 확장
                        expanded_part = " ".join([current + "아"] * consecutive_count)
                        expanded_version += " " + expanded_part
                        i += consecutive_count
                else:
                    expanded_version += current
                    i += 1
            
            # 원본 보존
            expanded_terms.append(term_clean)
            
            # 반복 패턴이 있으면 확장 버전도 추가
            if repetition_found:
                # 확장 버전을 검색 쿼리로 추가
                expanded_clean = expanded_version.strip()
                
                # 간단한 휴리스틱: 반복 패턴 → 단어 확장으로도 검색
                # (실제 검색 결과가 이를 검증할 것)
                if len(expanded_clean) > 0:
                    expanded_terms.append(expanded_clean)
                    
                    # 추가 변형: 반복 없는 버전도 시도
                    # [접두][음절반복] → [접두][음절] (축약어 가능성)
                    if i > 1:
                        base_part = term_clean[0] + term_clean[1]
                        expanded_terms.append(base_part)
                
                print(f"[{_ts()}][{self.emoji}] 🔁 반복 패턴 감지: '{term_clean}' ({syllable_count}음절) → {len(expanded_clean)}자 확장", 
                      file=sys.stderr)
        
        return list(set(expanded_terms))  # 중복 제거
    
    def _check_dictionary(
        self, 
        terms: List[str], 
        slang_dict: Dict[str, str]
    ) -> Dict[str, str]:
        """Check terms against slang dictionary for direct matches."""
        matches = {}
        for term in terms:
            term_lower = term.lower().strip()
            # Direct match
            if term_lower in slang_dict:
                matches[term] = slang_dict[term_lower]
            # Check without spaces
            term_nospace = term_lower.replace(" ", "")
            if term_nospace in slang_dict:
                matches[term] = slang_dict[term_nospace]
        return matches
    
    def _merge_dict_matches(
        self, 
        result: Dict[str, Any], 
        dict_matches: Dict[str, str],
        ctx: Any = None,
    ) -> Dict[str, Any]:
        """Merge dictionary matches into result with high confidence.
        
        🔥 사전값도 검색 결과의 공식 플랫폼 제목으로 교정 가능.
        """
        if not dict_matches:
            return result
        
        # 🔥 검색 결과에서 공식 제목 추출 (사전값 교정용)
        official_titles = []
        if ctx:
            official_titles = self._extract_official_titles_from_search(ctx)
        
        decoded_terms = result.get("decoded_terms", [])
        
        for term, title in dict_matches.items():
            # 🔥 사전값을 검색 결과의 공식 제목으로 교정
            corrected_title = self._correct_title_with_search_result(title, official_titles)
            if corrected_title != title:
                print(f"[{_ts()}][{self.emoji}] ⚠️ 사전값 교정: '{title}' → '{corrected_title}' (검색 결과 기반)", file=sys.stderr)
                title = corrected_title
            
            # Find existing entry or create new
            existing = next((d for d in decoded_terms if d.get("original") == term), None)
            
            if existing:
                # Add dictionary match as top candidate
                existing["candidates"].insert(0, {
                    "official_title": title,
                    "url": None,
                    "platform": None,
                    "decode_logic": "사전 매칭",
                    "morphological_score": 1.0,
                    "search_evidence": "slang_dictionary",
                })
                existing["best_match"] = {"title": title, "confidence": "high"}
            else:
                decoded_terms.append({
                    "original": term,
                    "candidates": [{
                        "official_title": title,
                        "url": None,
                        "platform": None,
                        "decode_logic": "사전 매칭",
                        "morphological_score": 1.0,
                        "search_evidence": "slang_dictionary",
                    }],
                    "best_match": {"title": title, "confidence": "high"},
                    "is_author_name": False,
                    "author_info": None,
                })
        
        result["decoded_terms"] = decoded_terms
        
        # Upgrade confidence if we have dictionary matches
        if dict_matches and result.get("overall_confidence") in ("low", "none"):
            result["overall_confidence"] = "high"
        
        return result
    
    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        system_content = DECODER_SYSTEM.replace("{platform_map}", PLATFORM_ABBREVIATION_MAP)
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
        
        response_text = self.llm._stream_chat_http(
            messages=messages,
            tag="decoder",
            use_grammar=True,
        )
        
        return self._parse_json_response(response_text)
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response, removing <think> blocks."""
        result = parse_json_with_think_removal(text)
        
        # Safety: verification_search 처리 (문자열 → 배열 변환)
        vs = result.get("verification_search")
        if vs:
            if isinstance(vs, str):
                # 단일 문자열을 배열로 변환
                result["verification_search"] = [vs.strip()]
            elif isinstance(vs, list):
                # 이미 배열이면 각 항목 정리
                result["verification_search"] = [
                    q.strip() for q in vs if isinstance(q, str) and q.strip()
                ][:5]  # 최대 5개로 제한
        
        return result
    
    def _empty_result(self, reason: str) -> Dict[str, Any]:
        """Return empty result."""
        return {
            "decoded_terms": [],
            "needs_verification": False,
            "verification_search": None,
            "overall_confidence": "none",
            "notes": reason,
        }
    
    def _init_suspected_titles(self, result: Dict[str, Any], ctx: Any) -> None:
        """
        ⭐ suspected_titles 초기 생성 (Decoder가 첫 번째로 생성)
        Verifier, Critic이 이 목록을 참조하고 수정할 수 있음
        
        🔥 CRITICAL: 검색 결과에서 공식 플랫폼(novelpia, namu.wiki, munpia)의
        정확한 제목을 추출하여 LLM 생성 제목을 교정해야 함!
        """
        suspected = []
        decoded_terms = result.get("decoded_terms", [])
        
        # 🔥 Step 0: 검색 결과에서 공식 플랫폼의 정확한 제목 추출
        official_titles_from_search = self._extract_official_titles_from_search(ctx)
        
        for term in decoded_terms:
            if not term:
                continue
            
            # 작가명은 제외
            if term.get("is_author_name"):
                continue
            
            # best_match에서 title 확인
            best_match = term.get("best_match") or {}
            if not best_match.get("title"):
                continue
            
            # candidates에서 후보 추출
            candidates = term.get("candidates", [])
            for cand in candidates[:2]:  # 상위 2개까지
                if not cand or not isinstance(cand, dict):
                    continue
                
                title = cand.get("official_novel_title") or cand.get("official_title")
                if not title:
                    continue
                
                # 🔥 CRITICAL: LLM 생성 제목을 검색 결과의 공식 제목과 비교하여 교정
                title = self._correct_title_with_search_result(title, official_titles_from_search)
                
                # 중복 체크
                if any(s.get("title") == title for s in suspected):
                    continue
                
                suspected.append({
                    "title": title,
                    "confidence": cand.get("morphological_score", 0.5),
                    "source_term": term.get("original", "Unknown"),
                    "source_expert": "decoder",
                    "status": "suspected",  # suspected → verified → confirmed
                })
        
        # 🆕 interpretations에서 작가명 약칭(author_abbreviation) 해석 활용
        # LLM이 interpretations에 author_abbreviation 해석을 기록한 경우,
        # 해당 작가의 작품을 검색 결과에서 찾아 suspected_titles에 추가
        for term in decoded_terms:
            if not term or not isinstance(term, dict):
                continue
            
            # 🔥 아키타입 차단된 term이면 multi-interp도 건너뜀
            # _guard_archetype_as_title에서 confidence="none"으로 설정된 경우
            best_match_for_term = term.get("best_match") or {}
            if best_match_for_term.get("confidence") == "none":
                original_term = term.get("original", "")
                if original_term.strip() in GENRE_ARCHETYPE_TERMS:
                    continue
            
            interps = term.get("interpretations") or []
            for interp in interps:
                if not isinstance(interp, dict):
                    continue
                interp_type = interp.get("type", "")
                context_fit = interp.get("context_fit", "low")
                interp_value = interp.get("value", "")
                
                # 작가명/작가약칭 해석이 있고 본문 맥락 적합도가 medium 이상이면
                if interp_type in ("author_name", "author_abbreviation") and context_fit in ("high", "medium") and interp_value:
                    # ctx._resolved_authors에 추가 (downstream에서 활용)
                    if ctx and not hasattr(ctx, '_multi_interp_authors'):
                        ctx._multi_interp_authors = []
                    if interp_value not in ctx._multi_interp_authors:
                        ctx._multi_interp_authors.append(interp_value)
                        print(
                            f"[{_ts()}][{self.emoji}] 🧠 다중해석: '{term.get('original')}' → "
                            f"작가 '{interp_value}' (fit={context_fit})",
                            file=sys.stderr,
                        )
                
                # 작품 약칭 해석이 있고 best_match가 비어있는 경우 → suspected_titles 보충
                if interp_type == "novel_title" and context_fit in ("high", "medium") and interp_value:
                    if not any(s.get("title") == interp_value for s in suspected):
                        conf = 0.75 if context_fit == "high" else 0.55
                        suspected.append({
                            "title": interp_value,
                            "confidence": conf,
                            "source_term": term.get("original", "Unknown"),
                            "source_expert": "decoder_multi_interp",
                            "status": "suspected",
                        })
                        print(
                            f"[{_ts()}][{self.emoji}] 🧠 다중해석: '{term.get('original')}' → "
                            f"작품 '{interp_value}' (fit={context_fit})",
                            file=sys.stderr,
                        )
        
        # ctx에 저장 (기존 것과 병합)
        existing = getattr(ctx, "suspected_titles", []) or []
        
        # 🆕 decoded_terms에서 제목을 못 찾았지만 _resolved_mappings에 매핑이 있으면 보충
        # 핵심: LLM이 이미 해독된 약칭을 decoded_terms에 반복하지 않는 경우 대비
        if not suspected and ctx:
            _resolved = getattr(ctx, '_resolved_mappings', []) or []
            if _resolved:
                # 검색 결과에서 공식 제목 확인
                official_titles_from_search = self._extract_official_titles_from_search(ctx)
                existing_titles = {s.get('title') for s in existing}
                
                for abbrev, full_title in _resolved:
                    # 검색 결과의 공식 제목으로 교정
                    corrected = self._correct_title_with_search_result(full_title, official_titles_from_search)
                    if corrected in existing_titles:
                        continue
                    
                    # 이 매핑이 검색에서 확인된 것인지 체크 (snippet_hints 기반)
                    from_snippet = hasattr(ctx, 'snippet_hints') and ctx.snippet_hints
                    
                    suspected.append({
                        "title": corrected,
                        "confidence": 0.85 if from_snippet else 0.7,
                        "source_term": abbrev,
                        "source_expert": "decoder_mapping",
                        "status": "suspected",
                    })
                    existing_titles.add(corrected)
                
                if suspected:
                    print(
                        f"[{_ts()}][{self.emoji}] 📋 resolved_mappings 폴백: "
                        f"decoded_terms 비어있음 → _resolved_mappings에서 {len(suspected)}건 보충",
                        file=sys.stderr,
                    )
        
        ctx.suspected_titles = existing + suspected[:5]  # 최대 5개
        
        if suspected:
            print(f"[{_ts()}][{self.emoji}] 📋 suspected_titles 초기화: {len(suspected)}건", file=sys.stderr)
            for i, st in enumerate(suspected[:5], 1):
                title = st.get('title', 'N/A')
                conf = st.get('confidence', 'N/A')
                source = st.get('source_expert', 'decoder')
                print(f"[{_ts()}][{self.emoji}]    [{i}] {title} (conf={conf}, from={source})", file=sys.stderr)
    
    def _guard_community_title(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 커뮤니티 제목 방어 후처리
        
        LLM이 best_match.title로 반환한 제목이 검색 결과에서
        커뮤니티 URL(dcinside, arca.live, fmkorea 등)에서만 나온 경우:
        1. 공식 플랫폼 content에서 추출한 대안 제목이 있으면 교체
        2. 없으면 신뢰도를 low로 강제 하향 + verification_search 재요청
        """
        import re
        from difflib import SequenceMatcher
        
        community_domains = [
            "dcinside.com", "fmkorea.com", "arca.live", "ruliweb.com",
            "theqoo.net", "clien.net", "arcalive.com",
        ]
        
        search_results = getattr(ctx, "search_results", []) or []
        if not search_results:
            return result
        
        # 공식 플랫폼 content에서 추출한 제목
        official_from_content = self._extract_official_titles_from_search(ctx)
        content_only_titles = [t for t in official_from_content if t.get("source") == "content_field"]
        
        decoded_terms = result.get("decoded_terms", [])
        changed = False
        
        for term in decoded_terms:
            best_match = term.get("best_match") or {}
            title = best_match.get("title", "")
            if not title:
                continue
            
            # 이 제목이 검색 결과에서 어디서 나왔는지 확인
            title_norm = title.strip().lower()
            found_in_official = False
            found_in_community = False
            
            for sr in search_results:
                sr_url = sr.get("url", "").lower()
                sr_title = (sr.get("title", "") or "").lower()
                sr_content = (sr.get("content", "") or sr.get("snippet", "") or "").lower()
                
                # 이 검색 결과에 해당 제목이 언급되는지 확인
                if title_norm not in sr_title and title_norm not in sr_content:
                    # 유사도로도 확인 (부분 일치)
                    sim_t = SequenceMatcher(None, title_norm, sr_title).ratio()
                    sim_c = SequenceMatcher(None, title_norm, sr_content[:100]).ratio() if sr_content else 0
                    if sim_t < 0.7 and sim_c < 0.5:
                        continue
                
                is_community = any(cd in sr_url for cd in community_domains)
                if is_community:
                    found_in_community = True
                else:
                    found_in_official = True
            
            # 커뮤니티에서만 발견되고 공식 플랫폼에서는 없는 경우
            if found_in_community and not found_in_official:
                original_term = term.get("original", "")
                
                # 🆕 복합어 보정: morphemes에서 제목 부분만 추출
                effective_term = original_term
                morphs = term.get("morphemes") or []
                if morphs and len(morphs) >= 2 and title:
                    title_n = title.replace(" ", "")
                    title_morphs = [m for m in morphs if m in title_n or m in title]
                    if title_morphs and len(title_morphs) < len(morphs):
                        effective_term = "".join(title_morphs)
                
                # content_field에서 추출한 대안 제목 중 원본 약칭과 매칭되는 것 찾기
                best_alt = None
                best_alt_score = 0.0
                
                for alt in content_only_titles:
                    alt_title = alt["title"]
                    score = abbreviation_match_score(effective_term, alt_title)
                    
                    if score > best_alt_score:
                        best_alt_score = score
                        best_alt = alt
                
                # 🔥 Fallback: 약칭 bigram 매칭 실패 시 LLM 제목 vs 공식 제목 유사도 비교
                if (not best_alt or best_alt_score < 0.3) and content_only_titles:
                    for alt in content_only_titles:
                        alt_title = alt["title"]
                        sim = SequenceMatcher(None, title_norm, alt_title.lower()).ratio()
                        if sim > best_alt_score and sim >= 0.35:
                            best_alt_score = sim
                            best_alt = alt
                
                # 🔥 Fallback 2: 전체 공식 제목 (content_field 이외)과도 비교
                if (not best_alt or best_alt_score < 0.3):
                    all_officials = self._extract_official_titles_from_search(ctx)
                    for alt in all_officials:
                        alt_title = alt["title"]
                        sim = SequenceMatcher(None, title_norm, alt_title.lower()).ratio()
                        if sim > best_alt_score and sim >= 0.35:
                            best_alt_score = sim
                            best_alt = alt
                
                if best_alt and best_alt_score >= 0.3:
                    # 대안 제목으로 교체
                    old_title = title
                    new_title = best_alt["title"]
                    best_match["title"] = new_title
                    best_match["confidence"] = "medium"
                    
                    # candidates에도 추가
                    candidates = term.get("candidates", [])
                    candidates.insert(0, {
                        "official_title": new_title,
                        "url": best_alt.get("url"),
                        "platform": best_alt.get("platform"),
                        "decode_logic": "커뮤니티 제목 교정 → 공식 플랫폼 content 추출",
                        "morphological_score": best_alt_score,
                        "search_evidence": f"content_field ({best_alt.get('platform')})",
                    })
                    term["candidates"] = candidates
                    
                    print(f"[{_ts()}][{self.emoji}] 🛡️ 커뮤니티 제목 방어: '{old_title}' → '{new_title}' "
                          f"(community_only=True, alt_score={best_alt_score:.2f}, platform={best_alt.get('platform')})",
                          file=sys.stderr)
                    changed = True
                else:
                    # 대안이 없으면 신뢰도 강제 하향 + 약칭 기반 재검색 유도
                    if best_match.get("confidence") in ("high", "medium"):
                        best_match["confidence"] = "low"
                        print(f"[{_ts()}][{self.emoji}] ⚠️ 커뮤니티 제목 의심: '{title}' → confidence=low "
                              f"(커뮤니티 URL에서만 발견됨, 공식 플랫폼 증거 없음)",
                              file=sys.stderr)
                        changed = True
                    
                    # 재검색 쿼리 추가: 원본 약칭으로 공식 플랫폼 검색
                    if original_term:
                        vs = result.get("verification_search") or []
                        if isinstance(vs, str):
                            vs = [vs]
                        # 약칭 분리하여 검색 (예: "즉사무림" → "즉사 무림 웹소설")
                        orig_clean = re.sub(r'[^\uac00-\ud7a3]', '', original_term)
                        if len(orig_clean) >= 4:
                            split_q = orig_clean[:3] + " " + orig_clean[3:] + " 웹소설"
                            if split_q not in vs:
                                vs.append(split_q)
                        else:
                            fallback_q = orig_clean + " 웹소설 공식"
                            if fallback_q not in vs:
                                vs.append(fallback_q)
                        result["verification_search"] = vs
                        result["needs_verification"] = True
        
        return result
    
    def _correct_title_from_platform_url(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 플랫폼 URL 기반 제목 교정
        
        Decoder LLM이 candidate URL은 공식 플랫폼(novelpia, munpia 등)으로 올바르게
        설정했지만, 제목은 커뮤니티 리뷰 제목을 채택한 경우를 교정.
        
        예: URL=novelpia.com/novel/326040 검색결과 제목="마법 좋아좋아좋아"
            Decoder가 "마법 좋아, 마법과 좋아" (arca.live 리뷰 제목) 반환
            → "마법 좋아좋아좋아"로 교정
        """
        import re
        from difflib import SequenceMatcher
        
        search_results = getattr(ctx, "search_results", []) or []
        if not search_results:
            return result
        
        # 1. 공식 플랫폼 URL → 추출 제목 맵 생성
        url_title_map: Dict[str, str] = {}
        for sr in search_results:
            sr_url = sr.get("url", "")
            if not any(p in sr_url for p in OFFICIAL_PLATFORMS):
                continue
            
            raw_title = sr.get("title", "")
            extracted = None
            
            # 방법A: "사이트명 - 작품제목" 패턴 분리
            if " - " in raw_title:
                parts = raw_title.split(" - ")
                candidate = parts[-1].strip()
                # 불필요한 접미사 제거
                candidate = re.sub(r'\s*\(r\d+\s*판\)$', '', candidate)
                if 2 <= len(candidate) <= 50:
                    extracted = candidate
            
            # 방법B: namu.wiki URL 디코딩
            if not extracted and "namu.wiki/w/" in sr_url:
                import urllib.parse
                try:
                    path = sr_url.split("/w/")[-1].split("?")[0]
                    decoded = urllib.parse.unquote(path)
                    decoded = re.sub(r'\s*\(r\d+\s*판\)$', '', decoded)
                    # 🆕 하위 페이지 필터: '/등장인물' 등 제거
                    if "/" in decoded:
                        decoded = decoded.split("/")[0]
                    if 2 <= len(decoded) <= 50:
                        extracted = decoded
                except Exception:
                    pass
            
            if extracted:
                # URL 정규화 (trailing slash, query params 제거)
                norm_url = sr_url.split("?")[0].rstrip("/")
                url_title_map[norm_url] = extracted
        
        if not url_title_map:
            return result
        
        # 2. 각 decoded_term의 candidates URL과 교차 확인
        decoded_terms = result.get("decoded_terms", [])
        changed = False
        
        for term in decoded_terms:
            best = term.get("best_match") or {}
            bm_title = best.get("title", "")
            if not bm_title:
                continue
            
            for cand in term.get("candidates", []):
                cand_url = cand.get("url", "")
                if not cand_url:
                    continue
                
                # URL 정규화 후 매칭
                cand_norm = cand_url.split("?")[0].rstrip("/")
                official_title = url_title_map.get(cand_norm)
                
                if not official_title:
                    continue
                
                # 제목이 이미 동일하면 스킵
                if official_title == bm_title:
                    continue
                
                # 유사도 확인 (너무 다르면 오교정 방지)
                sim = SequenceMatcher(
                    None, bm_title.lower(), official_title.lower()
                ).ratio()
                
                # 유사도 0.25 이상이면 교정 (같은 작품의 다른 표기일 가능성)
                # 또는 공유 형태소가 있으면 교정
                shared_morphemes = sum(
                    1 for ch in set(bm_title.replace(" ", ""))
                    if ch in official_title
                )
                shared_ratio = shared_morphemes / max(
                    len(set(bm_title.replace(" ", ""))), 1
                )
                
                if sim >= 0.25 or shared_ratio >= 0.4:
                    # 🆕 BUG-A 방어: 약어 스코어 역검증
                    # 현재 제목의 약어 매칭이 교정 후보보다 높으면 교정 거부
                    # (예: "즉사무림" → "즉사기 들고 무림에 떨어지다"(0.9) vs "즉사기 들고 게임 속으로"(0.0))
                    original_term = term.get("original", "")
                    if original_term and len(original_term) >= 2:
                        old_abbr_score = abbreviation_match_score(original_term, bm_title)
                        new_abbr_score = abbreviation_match_score(original_term, official_title)
                        if old_abbr_score > new_abbr_score + 0.1:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 플랫폼 URL 제목 교정 거부: "
                                f"'{bm_title}'(abbr={old_abbr_score:.2f}) → '{official_title}'(abbr={new_abbr_score:.2f}) "
                                f"약어 스코어 역전 → 교정 안함",
                                file=sys.stderr,
                            )
                            continue
                    
                    old_title = bm_title
                    best["title"] = official_title
                    cand["official_novel_title"] = official_title
                    
                    # confidence 유지 또는 상향
                    if best.get("confidence") in ("low", "none"):
                        best["confidence"] = "medium"
                    
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 플랫폼 URL 제목 교정: "
                        f"'{old_title}' → '{official_title}' "
                        f"(url={cand_url}, sim={sim:.2f}, shared={shared_ratio:.2f})",
                        file=sys.stderr,
                    )
                    changed = True
                    # best_match 제목이 바뀌었으므로 이 term 루프 종료
                    break
        
        if changed:
            # overall_confidence 재계산: 교정 후 신뢰도 상향 가능
            confs = []
            for term in decoded_terms:
                bm = term.get("best_match") or {}
                c = bm.get("confidence", "none")
                confs.append(c)
            if "high" in confs:
                result["overall_confidence"] = "high"
            elif "medium" in confs:
                result["overall_confidence"] = "medium"
        
        return result
    
    def _validate_genre_cross_match(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 장르 교차검증: 포스트 본문의 장르와 후보 작품의 장르 불일치 시 차단
        
        예: 본문에 "마왕, 대마법사, 용사, 도적단" → fantasy
            후보 작품 "초대남 B" → romance
            → 장르 불일치 → confidence 하향
        """
        # 1. 본문에서 장르 키워드 추출
        post_data = getattr(ctx, 'post_data', {}) or {}
        content_texts = []
        post_title = post_data.get("title", "")
        for block in post_data.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        all_text = post_title + " " + " ".join(content_texts + (getattr(ctx, 'comments', []) or []))
        
        # 각 장르별 키워드 히트 수 계산
        genre_hits: Dict[str, int] = {}
        for genre, keywords in GENRE_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in all_text)
            if hits > 0:
                genre_hits[genre] = hits
        
        if not genre_hits:
            return result  # 본문에서 장르 키워드 없음 → 검증 불가
        
        # 가장 많이 히트된 장르
        post_genre = max(genre_hits, key=genre_hits.get)
        post_genre_hits = genre_hits[post_genre]
        
        if post_genre_hits < 2:
            return result  # 키워드 1개만 히트 → 장르 확정 불가
        
        # 2. 후보 작품의 장르 확인 (검색 결과 snippet에서)
        decoded_terms = result.get("decoded_terms", [])
        for term in decoded_terms:
            if term.get("is_author_name"):
                continue
            
            best_match = term.get("best_match") or {}
            title = best_match.get("title")
            if not title or best_match.get("confidence") in ("none", "low"):
                continue
            
            # 후보 작품의 장르 추출: candidates의 genre_match 또는 검색 결과에서
            candidate_genres = set()
            for cand in term.get("candidates", []):
                gm = cand.get("genre_match") or {}
                tg = gm.get("target_genre", "")
                if tg:
                    # target_genre 문자열을 우리 장르 키에 매핑
                    tg_lower = tg.lower()
                    for genre, keywords in GENRE_KEYWORDS.items():
                        if tg_lower in [kw.lower() for kw in keywords] or tg_lower == genre:
                            candidate_genres.add(genre)
                    # 직접 매핑
                    genre_map = {
                        "로맨스": "romance", "romance": "romance", "로판": "romance",
                        "판타지": "fantasy", "fantasy": "fantasy", "현대판타지": "fantasy",
                        "무협": "martial_arts", "martial_arts": "martial_arts",
                        "현대": "modern", "modern": "modern",
                    }
                    if tg_lower in genre_map:
                        candidate_genres.add(genre_map[tg_lower])
            
            if not candidate_genres:
                continue
            
            # 3. 장르 불일치 판정
            if post_genre not in candidate_genres:
                old_conf = best_match.get("confidence", "medium")
                best_match["confidence"] = "low"
                
                # overall_confidence도 하향
                if result.get("overall_confidence") in ("high", "medium"):
                    result["overall_confidence"] = "low"
                
                print(f"[{_ts()}][{self.emoji}] 🚨 장르 교차검증 실패: "
                      f"'{title}' 장르={candidate_genres} vs 본문 장르={post_genre}"
                      f"(hits={post_genre_hits}) → confidence={old_conf}→low",
                      file=sys.stderr)
        
        return result
    
    def _validate_morpheme_in_title(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 약어-제목 매칭 검증 (코드 레벨 + LLM morphemes 병행)

        1단계: abbreviation_match_score()로 약어↔현재 후보 스코어 계산
        2단계: 스코어가 낮으면 검색 결과에서 더 높은 스코어의 후보 탐색
        3단계: LLM morphemes도 보조 검증으로 활용 (있는 경우)

        LLM이 morphemes를 잘못 분절해도 코드 레벨 스코어가 독립적으로 검증.
        """
        decoded_terms = result.get("decoded_terms", [])
        if not decoded_terms:
            return result

        # 검색 결과에서 후보 제목 수집
        all_search_titles = self._extract_official_titles_from_search(ctx)
        search_results = getattr(ctx, "search_results", []) or []

        # 검색 결과 snippet/title에서 잠재적 작품 제목 추출
        raw_title_pool: list[str] = []  # (제목 후보, 출처) 쌍
        for official in all_search_titles:
            raw_title_pool.append(official["title"])
        for sr in search_results:
            sr_title = sr.get("title", "")
            sr_content = sr.get("content", "") or sr.get("snippet", "")
            if sr_title:
                # 🆕 BUG-B 방어: 검색결과 제목에서 사이트명/게시판 접두어 정제
                # "블라인드 | 웹소설 종토방: 오늘도요 - 즉사기 들고 무림에 떨어지다"
                # → "즉사기 들고 무림에 떨어지다" 등으로 분리하여 추가
                cleaned_titles = self._clean_search_result_title(sr_title)
                raw_title_pool.extend(cleaned_titles)
            # content에서 Kiwi 명사 조합 또는 구문 추출
            if sr_content:
                self._extract_title_candidates_from_text(sr_content, raw_title_pool)

        # ── Gatekeeper possible_titles 통합 (댓글 추출 제목 포함) ──
        gk_out = ctx.expert_outputs.get("gatekeeper") or {}
        gk_entities = gk_out.get("detected_entities") or {}
        gk_possible = gk_entities.get("possible_titles") or []
        for gk_title in gk_possible:
            if isinstance(gk_title, str) and len(gk_title) >= 2:
                raw_title_pool.append(gk_title)
        if gk_possible:
            print(
                f"[{_ts()}][{self.emoji}] 📥 Gatekeeper possible_titles → title_pool: "
                f"{gk_possible}",
                file=sys.stderr,
            )

        # 중복 제거
        seen_titles: set[str] = set()
        title_pool: list[str] = []
        for t in raw_title_pool:
            t_stripped = t.strip()
            if t_stripped and t_stripped not in seen_titles:
                seen_titles.add(t_stripped)
                title_pool.append(t_stripped)

        changed = False

        for term in decoded_terms:
            if term.get("is_author_name"):
                continue

            original = term.get("original", "")
            if not original or len(original) < 2:
                continue

            # 🆕 interpretations에 author_name이 high fit으로 있으면 약어 가드 스킵
            # LLM이 is_author_name=false로 설정했지만 interpretations에 작가명 해석이 있는 모순 방어
            # 예: "뇌조" → interpretations에 type="author_name", context_fit="high" 있는데
            #     is_author_name=false + best_match.title="미국 레트로 소설가가 되었다" → score=0.00
            #     → 이것은 약어 불일치가 아니라 작가→대표작 매핑이므로 약어 가드 대상이 아님
            _interps = term.get("interpretations", [])
            _has_author_interp = any(
                (i.get("type") == "author_name" and i.get("context_fit") in ("high", "medium"))
                for i in _interps
                if isinstance(i, dict)
            )
            if _has_author_interp:
                print(
                    f"[{_ts()}][{self.emoji}] ℹ️ 작가명 해석 존재 '{original}' → 약어 가드 스킵 "
                    f"(is_author_name=false이지만 interpretations에 author_name 있음)",
                    file=sys.stderr,
                )
                continue

            # 🆕 캐릭터명은 약어 가드 대상이 아님 — 스킵
            # Decoder가 anchor_type="character_mention"으로 식별한 term은
            # 제목 약어가 아니라 캐릭터 이름이므로 abbreviation_match_score 검증 불필요
            grounding_info = term.get("grounding") or {}
            is_character_term = (
                grounding_info.get("anchor_type") == "character_mention"
                or (len(original) <= 3 and any(
                    (term.get("original") or "") in (c or "")
                    for c in (ctx.expert_outputs.get("gatekeeper") or {}).get("detected_entities", {}).get("possible_characters", [])
                ))
            )
            if is_character_term:
                print(
                    f"[{_ts()}][{self.emoji}] ℹ️ 캐릭터명 '{original}' → 약어 가드 스킵 "
                    f"(anchor_type={grounding_info.get('anchor_type')})",
                    file=sys.stderr,
                )
                continue

            best_match = term.get("best_match") or {}
            current_title = best_match.get("title")

            # ── 🆕 Rescue: LLM이 title=null을 반환한 경우, 검색 결과에서 자동 매칭 시도 ──
            if not current_title:
                if len(original) >= 3:
                    rescue_title, rescue_score, rescue_src = self._rescue_null_title(
                        original, term, title_pool, all_search_titles,
                        search_results, ctx,
                    )
                    if rescue_title:
                        best_match["title"] = rescue_title
                        best_match["confidence"] = "medium"
                        # candidates에도 추가
                        cands = term.get("candidates") or []
                        cands.insert(0, {
                            "official_novel_title": rescue_title,
                            "url": None,
                            "platform": rescue_src,
                            "decode_logic": f"코드 레벨 rescue: abbreviation_match_score={rescue_score:.2f}",
                            "morphological_score": rescue_score,
                            "search_evidence": f"rescue from {rescue_src}",
                        })
                        term["candidates"] = cands
                        current_title = rescue_title
                        changed = True
                        # overall_confidence도 상향 (null→rescue 성공)
                        if result.get("overall_confidence") in ("none", "low"):
                            result["overall_confidence"] = "medium"
                        print(
                            f"[{_ts()}][{self.emoji}] 🚀 Null→Rescue 매칭: "
                            f"'{original}' → '{rescue_title}' "
                            f"(score={rescue_score:.2f}, src={rescue_src})",
                            file=sys.stderr,
                        )
                        # 🆕 rescue 결과도 코드레벨 힌트로 저장
                        if ctx:
                            if not hasattr(ctx, 'code_level_hints'):
                                ctx.code_level_hints = []
                            ctx.code_level_hints.append({
                                "type": "rescue_match",
                                "original_term": original,
                                "effective_keyword": original,
                                "corrected_title": rescue_title,
                                "abbreviation_score": round(rescue_score, 2),
                                "source": rescue_src or "search_pool",
                                "reasoning": f"LLM이 제목을 식별하지 못했으나, 코드 레벨 약어 분석에서 '{original}'이 '{rescue_title}'과 높은 매칭을 보임 (score={rescue_score:.2f})",
                            })
                if not current_title:
                    continue

            # ── 1단계: 현재 후보의 약어 매칭 스코어 ──
            current_score = abbreviation_match_score(original, current_title)

            # LLM morphemes 보조 검증 (있으면 추가 체크)
            morphemes = term.get("morphemes", [])
            morpheme_ok = True
            effective_original = original  # 복합어 보정용
            if morphemes and len(morphemes) >= 2:
                title_norm = current_title.replace(" ", "")
                morpheme_ok = all(
                    m in title_norm or m in current_title
                    for m in morphemes
                )

                # 🆕 복합어 보정: original이 [제목부분 + 캐릭터/작가명]으로 구성된 경우
                # morphemes 중 title에 포함되는 부분만 추출하여 스코어 재계산
                # 예: original='즉사무림이유백', morphemes=['즉사무림','이유백'], title='즉사무림'
                if current_score < 0.2 and len(original) > len(current_title.replace(" ", "")):
                    title_morphemes = [m for m in morphemes if m in title_norm or m in current_title]
                    non_title_morphemes = [m for m in morphemes if m not in title_morphemes]
                    if title_morphemes and non_title_morphemes:
                        # 제목 부분 morpheme를 합쳐서 effective_original 생성
                        effective_abbr = "".join(title_morphemes)
                        comp_score = abbreviation_match_score(effective_abbr, current_title)
                        if comp_score > current_score:
                            current_score = comp_score
                            effective_original = effective_abbr
                            # non_title_morphemes가 캐릭터/작가명인지 확인
                            morpheme_ok = True  # 제목 부분만 비교하므로 OK
                            print(
                                f"[{_ts()}][{self.emoji}] 🔀 복합어 보정: "
                                f"'{original}' → effective='{effective_abbr}' "
                                f"(non_title={non_title_morphemes}, score={comp_score:.2f})",
                                file=sys.stderr,
                            )

            # 🆕 복합 제목 전처리: GK entities의 캐릭터/작가를 original에서 제거하여 순수 작품 키워드로 재시도
            # 예: "망겜성 황건욱 ts된거" → 황건욱(캐릭터) 제거 → "망겜성"으로 재매칭
            # 예: "즉사무림이유백" → 유백(작가) → morpheme "이유백" 확장 제거 → "즉사무림"
            if current_score < 0.5:
                gk_out_m = ctx.expert_outputs.get("gatekeeper") or {}
                gk_ent_m = gk_out_m.get("detected_entities") or {}
                gk_chars = set(gk_ent_m.get("possible_characters") or [])
                gk_authors = set(gk_ent_m.get("possible_authors") or [])
                entities_to_remove = gk_chars | gk_authors

                # 🆕 BUG-2: 공백 분리 복합어 보정 — GK가 캐릭터를 감지 못 해도 공백 기준 분리 시도
                # "망겜성 황건욱" → ["망겜성", "황건욱"] → 각 부분으로 점수 계산, 최선 선택
                if " " in original and not entities_to_remove:
                    parts = original.split()
                    if len(parts) >= 2:
                        best_part_score = current_score
                        best_part = None
                        for part in parts:
                            part_clean = part.strip()
                            if len(part_clean) >= 2:
                                pscore = abbreviation_match_score(part_clean, current_title)
                                if pscore > best_part_score:
                                    best_part_score = pscore
                                    best_part = part_clean
                        if best_part and best_part_score > current_score:
                            print(
                                f"[{_ts()}][{self.emoji}] 🔀 공백분리 복합어 보정: "
                                f"'{original}' → '{best_part}' "
                                f"(score: {current_score:.2f}→{best_part_score:.2f})",
                                file=sys.stderr,
                            )
                            current_score = best_part_score
                            effective_original = best_part
                            if best_part_score >= 0.8:
                                morpheme_ok = True

                if entities_to_remove:
                    # 🆕 morphemes 기반 entity 확장 제거:
                    # GK entity "유백"이 morpheme "이유백"에 포함되면, "이유백" 전체를 제거 대상에 추가
                    # 이유: "즉사무림이유백" → GK "유백" 제거 → "즉사무림이" (이 잔여 '이'가 매칭 방해)
                    #       morpheme ["즉사", "무림", "이유백"] 참조 → "이유백" 전체 제거 → "즉사무림" (정확)
                    expanded_entities = set(entities_to_remove)
                    if morphemes and len(morphemes) >= 2:
                        for ent in entities_to_remove:
                            for morph in morphemes:
                                # entity가 morpheme의 suffix이고, morpheme이 entity보다 길면 확장
                                if morph.endswith(ent) and len(morph) > len(ent) and morph != original:
                                    expanded_entities.add(morph)
                                # entity가 morpheme과 동일하면 이미 포함
                    
                    # original에서 entity 제거하여 순수 작품 키워드 추출
                    # 확장된 entity부터 먼저 제거 (더 긴 것부터 제거해야 정확)
                    sorted_entities = sorted(expanded_entities, key=len, reverse=True)
                    stripped = original
                    for ent in sorted_entities:
                        stripped = stripped.replace(ent, "")
                    # 공백/특수문자 정리: 중간 이중공백 제거 + 양쪽 trim
                    stripped = _re.sub(r"\s+", " ", stripped).strip()
                    # 제거 후 남은 문자열이 2글자 이상이면 재시도
                    if stripped and len(stripped) >= 2 and stripped != original:
                        stripped_score = abbreviation_match_score(stripped, current_title)
                        # 🔧 entity 제거로 생성된 stripped는 2단계 탐색에서 중요하므로
                        # current_title에 대한 score 개선 여부와 무관하게 effective_original 채택
                        # (현재 제목이 이미 틀린 경우, 2단계 title_pool에서 올바른 매칭이 나올 수 있음)
                        if stripped_score >= current_score:
                            if stripped_score > current_score:
                                actually_removed = expanded_entities & set(
                                    e for e in sorted_entities if e in original
                                )
                                print(
                                    f"[{_ts()}][{self.emoji}] 🔀 복합 제목 분리: "
                                    f"'{original}' → entity 제거 → '{stripped}' "
                                    f"(score: {current_score:.2f}→{stripped_score:.2f}, "
                                    f"removed={actually_removed})",
                                    file=sys.stderr,
                                )
                                current_score = stripped_score
                            effective_original = stripped
                            if stripped_score >= 0.8:
                                morpheme_ok = True
                        
                        # 🆕 progressive suffix trimming: stripped에서도 매칭 실패 시
                        # 끝에서 한 글자씩 제거하며 재시도 (잔여 조사 "이", "의" 등 제거)
                        if current_score < 0.5 and len(stripped) >= 3:
                            for trim_len in range(1, min(3, len(stripped) - 2)):
                                trimmed = stripped[:-trim_len]
                                if len(trimmed) < 2:
                                    break
                                trim_score = abbreviation_match_score(trimmed, current_title)
                                if trim_score > current_score:
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔀 suffix trim: "
                                        f"'{stripped}' → '{trimmed}' "
                                        f"(score: {current_score:.2f}→{trim_score:.2f})",
                                        file=sys.stderr,
                                    )
                                    current_score = trim_score
                                    effective_original = trimmed
                                    if trim_score >= 0.8:
                                        morpheme_ok = True
                                    break  # 가장 작은 trim으로 성공하면 중단

            # 현재 후보가 충분히 좋으면 스킵 (스코어는 항상 로그)
            print(
                f"[{_ts()}][{self.emoji}] 📊 약어스코어: '{original}' → "
                f"'{current_title}' [score={current_score:.2f}, morpheme_ok={morpheme_ok}]",
                file=sys.stderr,
            )
            if current_score >= 0.8 and morpheme_ok:
                continue

            # ── 🔒 아이디어 C: 명시적 약칭 증거 앵커 ──
            # 검색 결과에 "약칭은 X다", "통칭 X" 등이 있으면 LLM 결과 보호
            has_explicit_alias = False
            alias_patterns = [
                _re.compile(rf'약칭[은이가]?\s*{_re.escape(original)}'),
                _re.compile(rf'통칭\s*{_re.escape(original)}'),
                _re.compile(rf'줄여서\s*{_re.escape(original)}'),
                _re.compile(rf'줄임말[은이가]?\s*{_re.escape(original)}'),
            ]
            for sr in search_results:
                sr_content = sr.get("content", "") or sr.get("snippet", "")
                sr_title_text = sr.get("title", "")
                combined = sr_title_text + " " + sr_content
                if any(p.search(combined) for p in alias_patterns):
                    has_explicit_alias = True
                    break

            if has_explicit_alias:
                # 검색 결과에 명시적으로 "약칭은 original"이라고 나옴 → 현재 제목 보호
                print(
                    f"[{_ts()}][{self.emoji}] 🔒 명시적 약칭 증거 발견: "
                    f"'{original}' = '{current_title}' → 약어 스코어 교정 스킵",
                    file=sys.stderr,
                )
                continue

            # ── 2단계: 검색 결과에서 더 높은 스코어 후보 탐색 ──
            missing_info = ""
            if not morpheme_ok:
                missing = [m for m in morphemes if m not in current_title.replace(" ", "") and m not in current_title]
                missing_info = f", morpheme누락={missing}"

            print(
                f"[{_ts()}][{self.emoji}] ⚠️ 약어 매칭 낮음: '{original}' → "
                f"'{current_title}' (score={current_score:.2f}{missing_info})",
                file=sys.stderr,
            )

            best_alt_title = None
            best_alt_score = current_score
            best_alt_source = None

            # 🔧 아이디어 A-3: 커뮤니티 게시글 제목 출처 구분
            _COMMUNITY_DOMAINS = (
                "ruliweb.com", "fmkorea.com", "dcinside.com",
                "arca.live", "x.com", "twitter.com", "reddit.com",
                "theqoo.net", "instiz.net", "mlbpark.donga.com",
                "clien.net", "todayhumor.co.kr", "ppomppu.co.kr",
                "inven.co.kr", "gall.dcinside.com",
                "teamblind.com", "threads.net", "threads.com",
            )
            # 커뮤니티 출처 제목 식별용 세트
            community_titles: set[str] = set()
            for sr in search_results:
                sr_url = sr.get("url", "")
                if any(cd in sr_url for cd in _COMMUNITY_DOMAINS):
                    sr_title_raw = sr.get("title", "").strip()
                    if sr_title_raw:
                        community_titles.add(sr_title_raw)
                        # " - " 분할된 제목 부분도 추가
                        if " - " in sr_title_raw:
                            for part in sr_title_raw.split(" - "):
                                community_titles.add(part.strip())

            for candidate in title_pool:
                if candidate == current_title:
                    continue
                # 후보 제목이 너무 짧거나 길면 스킵
                if len(candidate) < 3 or len(candidate) > 40:
                    continue

                # 🚫 커뮤니티 게시글 제목은 공식 제목 후보에서 제외
                if candidate in community_titles:
                    continue

                score = abbreviation_match_score(effective_original, candidate)

                # morphemes 보조: morphemes도 모두 포함하면 보너스
                if morphemes and len(morphemes) >= 2:
                    cand_norm = candidate.replace(" ", "")
                    if all(m in cand_norm or m in candidate for m in morphemes):
                        score = min(score + 0.1, 1.0)

                if score > best_alt_score:
                    best_alt_score = score
                    best_alt_title = candidate
                    # 출처 판별
                    best_alt_source = "search_pool"
                    for official in all_search_titles:
                        if official["title"] == candidate:
                            best_alt_source = f"platform:{official.get('platform', '?')}"
                            break

            # ── 3단계: 교체 또는 confidence 하향 ──
            # 🔧 현재 제목이 공식 플랫폼 출처면 교정 기준 강화
            current_from_official = any(
                official["title"] == current_title
                for official in all_search_titles
            )
            replace_margin = 0.30 if current_from_official else 0.15

            if best_alt_title and best_alt_score >= 0.7 and best_alt_score > current_score + replace_margin:
                old_title = current_title
                best_match["title"] = best_alt_title

                # candidates도 업데이트
                for cand in term.get("candidates", []):
                    if cand.get("official_novel_title") == old_title:
                        cand["official_novel_title"] = best_alt_title

                print(
                    f"[{_ts()}][{self.emoji}] 🔧 약어 스코어 기반 제목 교정: "
                    f"'{old_title}'(score={current_score:.2f}) → "
                    f"'{best_alt_title}'(score={best_alt_score:.2f}) "
                    f"(source={best_alt_source})",
                    file=sys.stderr,
                )
                changed = True

                # 🆕 코드레벨 힌트를 ctx에 저장 → Verifier/Arbiter가 참고
                if ctx:
                    if not hasattr(ctx, 'code_level_hints'):
                        ctx.code_level_hints = []
                    ctx.code_level_hints.append({
                        "type": "abbreviation_correction",
                        "original_term": original,
                        "effective_keyword": effective_original,
                        "old_title": old_title,
                        "corrected_title": best_alt_title,
                        "abbreviation_score": round(best_alt_score, 2),
                        "source": best_alt_source or "search_pool",
                        "reasoning": f"약어 '{effective_original}'의 각 음절이 '{best_alt_title}'의 단어 첫 글자와 순차 매칭됨 (score={best_alt_score:.2f})",
                    })
            elif current_score < 0.2 and not has_explicit_alias:
                # 🛡️ 약어스코어 극단적 저조 (0.2 미만) → 할루시네이션 의심
                # 작가 필명을 작품명으로 매칭하는 등의 오류 방지
                # morpheme_ok 여부와 무관하게 강제 하향/무효화
                # ⚠️ 단, 검색 결과에 명시적 약칭 증거가 있으면 스킵
                # 🆕 BUG-2: effective_original이 보정되어 높은 점수를 가지면 가드 우회
                effective_score = abbreviation_match_score(effective_original, current_title) if effective_original != original else current_score
                if effective_score >= 0.5:
                    print(
                        f"[{_ts()}][{self.emoji}] ℹ️ 약어 가드 우회: "
                        f"original '{original}' score={current_score:.2f} < 0.2이지만, "
                        f"effective '{effective_original}' score={effective_score:.2f} ≥ 0.5 "
                        f"→ confidence 유지",
                        file=sys.stderr,
                    )
                else:
                    old_conf = best_match.get("confidence", "medium")
                    best_match["confidence"] = "low"
                    if result.get("overall_confidence") in ("high", "medium"):
                        result["overall_confidence"] = "low"
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 약어 스코어 극단적 저조 (score={current_score:.2f}): "
                        f"'{original}' → '{current_title}' → confidence: {old_conf}→low "
                        f"(할루시네이션 의심)",
                        file=sys.stderr,
                    )
                changed = True
            elif current_score < 0.5 and not morpheme_ok:
                # 약어 스코어도 낮고 morpheme도 불일치 → confidence 하향
                old_conf = best_match.get("confidence", "medium")
                if old_conf == "high":
                    best_match["confidence"] = "medium"
                    if result.get("overall_confidence") == "high":
                        result["overall_confidence"] = "medium"
                    print(
                        f"[{_ts()}][{self.emoji}] ⚠️ 약어 스코어 낮음+morpheme 불일치 → "
                        f"confidence: {old_conf}→medium (대안 없음)",
                        file=sys.stderr,
                    )

        return result

    def _rescue_null_title(
        self,
        original: str,
        term: Dict[str, Any],
        title_pool: list[str],
        official_titles: list[Dict[str, str]],
        search_results: list[Dict[str, Any]],
        ctx: Any,
    ) -> tuple:
        """
        🚀 LLM이 best_match.title=null을 반환한 경우, 검색 결과에서 코드 레벨로 자동 매칭.

        1) 공식 플랫폼(official_titles)에서 abbreviation_match_score가 가장 높은 제목
        2) 검색 결과 content에서 "문피아에 X란 소설" 패턴으로 추출된 제목
        3) 검색 결과 제목에서 " - 작품명" 패턴 (블라인드 등 커뮤니티도 포함 - 공식명칭 인용)

        Returns:
            (rescue_title, score, source) or (None, 0.0, None)
        """
        # ── 커뮤니티 은어 사전 (BUG-5, BUG-6) ──
        _COMMUNITY_SLANG = {
            "파딱", "완장", "고닉", "장붕이", "장붕", "장갤", "고로시", "탈갤",
            "뿜명어", "설레발", "무개념", "악플러", "겹채", "닭판",
            "반바기", "본덕", "다링", "찬모리",
            "웹연갤", "노벨피아", "문피아", "카케페", "시리즈",
            "장판갤", "로판갤", "무협갤", "판갤",
        }

        # ── 장르 트로프/클리셰 키워드 (BUG-1) ──
        _GENRE_TROPE_KEYWORDS = {
            "회귀", "환생", "무림", "아카데미", "습격", "테러", "던전",
            "히로인", "분양", "하렘", "성좌", "회귀자", "각성",
            "소환", "마법사", "용병", "검사", "성기사", "데마계",
            "법사", "마계", "천재", "암타", "역행", "빌런",
            "영지", "영주", "재벌", "서바이벌", "리셋",
        }

        # 🆕 BUG-5/6: 커뮤니티 은어는 Rescue 대상에서 제외
        original_clean = original.strip().replace(" ", "")
        if original_clean in _COMMUNITY_SLANG:
            print(
                f"[{_ts()}][{self.emoji}] 🚫 Rescue 스킵: "
                f"'{original}'은 커뮤니티 은어 (COMMUNITY_SLANG)",
                file=sys.stderr,
            )
            return (None, 0.0, None)

        # 🆕 BUG-1: 장르 트로프 키워드만으로 구성된 약어는 Rescue 제한
        # ⚠️ 단, KNOWN_ABBREVIATIONS에 등록된 약칭이거나,
        #    검색 결과에서 작품 약칭으로 사용되는 증거가 있으면 통과
        _KNOWN_ABBREVIATIONS_PRECHECK = set(KNOWN_ABBREVIATIONS.keys())
        original_words = set(_re.sub(r'[^\w]', ' ', original_clean).split())
        trope_words_in_original = {
            w for w in original_words
            if w and any(t in w or w in t for t in _GENRE_TROPE_KEYWORDS)
        }
        if original_words and trope_words_in_original == original_words and len(original_words) >= 1:
            # 🔥 알려진 약칭이면 트로프 체크 무시
            if original_clean in _KNOWN_ABBREVIATIONS_PRECHECK:
                print(
                    f"[{_ts()}][{self.emoji}] ✅ 트로프 체크 통과: "
                    f"'{original}'은 KNOWN_ABBREVIATIONS에 등록됨",
                    file=sys.stderr,
                )
            else:
                # 🔥 검색 결과에서 이 용어가 작품 약칭으로 쓰이는 증거 확인
                search_evidence_found = False
                for sr in search_results:
                    sr_text = (sr.get("title", "") + " " + (sr.get("content") or "")).lower()
                    # "즉사무림 작가", "즉사무림 리뷰", "즉사무림 추천" 등 → 작품으로 사용
                    if original_clean in sr_text:
                        for indicator in ("작가", "리뷰", "추천", "연재", "재밌", "읽", "작품"):
                            if indicator in sr_text:
                                search_evidence_found = True
                                break
                    if search_evidence_found:
                        break
                
                if search_evidence_found:
                    print(
                        f"[{_ts()}][{self.emoji}] ✅ 트로프 체크 통과: "
                        f"'{original}'은 검색 결과에서 작품 약칭 증거 발견",
                        file=sys.stderr,
                    )
                else:
                    # 본문에 작품 플랫폼 URL이 있는지 확인
                    post_data = getattr(ctx, 'post_data', {}) or {}
                    post_body_parts = []
                    for block in post_data.get("content_blocks", []):
                        if isinstance(block, dict) and block.get("text"):
                            post_body_parts.append(block["text"])
                        elif isinstance(block, str):
                            post_body_parts.append(block)
                    post_body = " ".join(post_body_parts)
                    comments_text = " ".join(getattr(ctx, 'comments', []) or [])
                    full_text = f"{post_data.get('title', '')} {post_body} {comments_text}"
                    has_platform_url = any(
                        d in full_text for d in ("novelpia.com", "munpia.com", "series.naver.com", "page.kakao.com")
                    )
                    if not has_platform_url:
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 Rescue 스킵: "
                            f"'{original}'은 장르 트로프 키워드만으로 구성 "
                            f"(words={original_words}, trope_match={trope_words_in_original}) "
                            f"+ 본문에 플랫폼 URL 없음 + 검색 증거 없음",
                            file=sys.stderr,
                        )
                        return (None, 0.0, None)

        # 🆕 BUG-1: discourse_warning이 있으면 rescue 스코어 기준 상향 (0.75 → 0.85)
        has_discourse_warning = bool(getattr(ctx, 'discourse_warning', None)) if ctx else False
        rescue_min_score = 0.85 if has_discourse_warning else 0.75

        # 🆕 P1-2: 포스트가 플랫폼 일반 논의/장르 트로프 논의인 경우 Rescue 스킵
        # "탑툰은 비처녀 아닌 히로인..." 같은 플랫폼 전반 논의에서 우연 매칭 방지
        discourse_out = None
        if ctx:
            discourse_out = getattr(ctx, 'expert_outputs', {}).get('discourse_analyzer') or {}
        if discourse_out:
            disc_type = (discourse_out.get("discourse_type") or "").lower()
            if disc_type in ("platform_general", "trope_discussion", "community_meta"):
                return (None, 0.0, None)
        # 커뮤니티 글 제목은 후보에서 제외 (약칭 자체가 들어있는 글은 false positive)
        _COMMUNITY_DOMAINS = (
            "ruliweb.com", "fmkorea.com", "dcinside.com",
            "arca.live", "theqoo.net", "clien.net",
            "inven.co.kr", "ppomppu.co.kr", "todayhumor.co.kr",
        )
        community_titles: set[str] = set()
        for sr in search_results:
            sr_url = sr.get("url", "")
            if any(cd in sr_url for cd in _COMMUNITY_DOMAINS):
                sr_t = (sr.get("title") or "").strip()
                if sr_t:
                    community_titles.add(sr_t)

        best_title = None
        best_score = 0.0
        best_source = None

        # ── 🆕 BUG-5: 알려진 약어 사전 직접 매핑 (LLM 실패 시 코드레벨 보정) ──
        # (KNOWN_ABBREVIATIONS는 모듈 수준 상수 참조)
        known_title = KNOWN_ABBREVIATIONS.get(original_clean)
        if known_title:
            # 검증: 검색 결과에 해당 제목이 있는지 확인 (환각 방지)
            found_in_search = False
            for sr in search_results:
                sr_text = (sr.get("title", "") + " " + (sr.get("content") or sr.get("snippet") or ""))
                if known_title.replace(" ", "") in sr_text.replace(" ", ""):
                    found_in_search = True
                    break
            if found_in_search or known_title in [ot["title"] for ot in official_titles]:
                print(
                    f"[{_ts()}][{self.emoji}] 📘 Known abbreviation: "
                    f"'{original}' → '{known_title}' (KNOWN_ABBREVIATIONS)",
                    file=sys.stderr,
                )
                return known_title, 0.95, "known_abbreviation"
            else:
                # 검색 결과에 없어도 높은 신뢰도로 후보 제시
                print(
                    f"[{_ts()}][{self.emoji}] 📘 Known abbreviation (미검증): "
                    f"'{original}' → '{known_title}' (검색 결과에서 미확인, 후보로 설정)",
                    file=sys.stderr,
                )
                best_title = known_title
                best_score = 0.80
                best_source = "known_abbreviation_unverified"

        # 🆕 작가 페이지 패턴: "~님의 작품", "작품 목록" 등은 작품명이 아님
        _AUTHOR_PAGE_PATTERNS = (
            "님의 작품", "의 작품 목록", "작품 목록", "프로필",
            "작가 정보", "작가 페이지", "님의 웹소설", "작가의 작품",
            "작품활동", "작품 활동", "작가 소개",
        )

        # ── Pass 1: 공식 플랫폼 제목 우선 ──
        for ot in official_titles:
            candidate = ot["title"]
            if len(candidate) < 4 or len(candidate) > 40:
                continue
            # 🆕 작가 페이지 제목은 작품명이 아님 → 스킵
            if any(p in candidate for p in _AUTHOR_PAGE_PATTERNS):
                continue
            score = abbreviation_match_score(original, candidate)
            if score > best_score:
                best_score = score
                best_title = candidate
                best_source = f"platform:{ot.get('platform', '?')}"

        # ── Pass 2: 전체 title_pool (커뮤니티 제외) ──
        for candidate in title_pool:
            if candidate in community_titles:
                continue
            if len(candidate) < 4 or len(candidate) > 40:
                continue
            # 🆕 작가 페이지 제목은 작품명이 아님 → 스킵
            if any(p in candidate for p in _AUTHOR_PAGE_PATTERNS):
                continue
            score = abbreviation_match_score(original, candidate)
            if score > best_score:
                best_score = score
                best_title = candidate
                best_source = "title_pool"

        # ── Pass 3: 검색 결과 content에서 "X란 소설" / "X라는 작품" 패턴 ──
        import re as _re_rescue
        content_title_patterns = [
            _re_rescue.compile(
                r'(?:문피아|노벨피아|카카오페이지|네이버\s*시리즈|조아라)(?:에)?\s+'
                r'(.{3,25}?)(?:란|라는|이란|이라는)\s*(?:소설|작품|웹소설)'
            ),
            _re_rescue.compile(
                r'(?:소설|작품|웹소설)\s*["\']?(.{3,25}?)["\']?\s*(?:이라는|라는|이란|란)'
            ),
        ]
        for sr in search_results:
            content = (sr.get("content") or sr.get("snippet") or "")
            for pat in content_title_patterns:
                for m in pat.finditer(content):
                    candidate = m.group(1).strip()
                    candidate = _re_rescue.sub(r'[\.\s]+$', '', candidate)
                    if 3 <= len(candidate) <= 30:
                        score = abbreviation_match_score(original, candidate)
                        if score > best_score:
                            best_score = score
                            best_title = candidate
                            best_source = "content_pattern"

        # ── Pass 4: "블라인드 | 웹소설 종토방: 제목" 등 제목 패턴 ──
        title_suffix_patterns = [
            _re_rescue.compile(r'[-:|]\s*(.{4,30})$'),
        ]
        for sr in search_results:
            sr_title = (sr.get("title") or "").strip()
            if not sr_title:
                continue
            for pat in title_suffix_patterns:
                m = pat.search(sr_title)
                if m:
                    candidate = m.group(1).strip()
                    if 4 <= len(candidate) <= 30 and candidate not in community_titles:
                        score = abbreviation_match_score(original, candidate)
                        if score > best_score:
                            best_score = score
                            best_title = candidate
                            best_source = "title_suffix"

        # ── Pass 5: Morpheme 기반 부분 매칭 ──
        # LLM이 morphemes로 분리한 세그먼트 중, 인명(캐릭터)을 제외한 핵심 키워드만
        # 조합하여 abbreviation_match_score 재시도.
        # 예: "즉사무림이유백" → morphemes=["즉사","무림","이유백"]
        #     "이유백"은 character → 제외 → "즉사무림"으로 재검색
        if best_score < 0.75:
            morphemes = term.get("morphemes") or []
            if morphemes and len(morphemes) >= 2:
                # 후보에서 character/author로 추정되는 morpheme 제거
                gk_out = ctx.expert_outputs.get("gatekeeper") or {}
                gk_entities = gk_out.get("detected_entities") or {}
                char_names = set(gk_entities.get("possible_characters") or [])
                author_names = set(gk_entities.get("possible_authors") or [])
                exclude_names = char_names | author_names

                # grounding에서 character_mention인 경우도 확인
                grounding = term.get("grounding") or {}
                if grounding.get("anchor_type") == "character_mention":
                    # anchor_evidence에서 인명 추출
                    evidence = grounding.get("anchor_evidence", "")
                    for morph in morphemes:
                        if morph in evidence and len(morph) >= 2:
                            exclude_names.add(morph)

                # Decoder가 is_author_name으로 마킹한 다른 term도 참고
                for other_term in (term.get("_sibling_terms") or []):
                    if other_term.get("is_author_name"):
                        ai = other_term.get("author_info") or {}
                        an = ai.get("name") or other_term.get("original")
                        if an:
                            exclude_names.add(an)

                # 🆕 같은 term의 author_info에서도 인명 추출
                # Gatekeeper가 인명 분류 못 했어도 Decoder가 식별한 경우
                term_author = term.get("author_info") or {}
                if term_author.get("name"):
                    exclude_names.add(term_author["name"])
                # is_author_name=false여도, 검색 결과에서 캐릭터로 확인된 morpheme 탐지
                # 검색 결과에서 "이유백은", "이유백이" 등 인명 패턴 확인
                if not exclude_names:
                    import re as _re_char
                    for morph in morphemes:
                        if len(morph) >= 2:
                            char_pattern = _re_char.compile(
                                rf'{_re_char.escape(morph)}[은는이가을를의도]'
                            )
                            for sr in search_results:
                                sr_content = (sr.get("content") or sr.get("snippet") or "")
                                sr_title_text = sr.get("title", "")
                                combined = sr_title_text + " " + sr_content
                                if char_pattern.search(combined):
                                    # 이 morpheme이 인명(캐릭터/작가)일 가능성 확인
                                    # 다른 morpheme도 같은 검색결과에 제목으로 나오는지 확인
                                    other_morphs = [m for m in morphemes if m != morph]
                                    other_in_title = any(
                                        om in sr_title_text for om in other_morphs
                                    )
                                    if other_in_title:
                                        exclude_names.add(morph)
                                        break

                # 인명 제외한 morphemes 조합
                core_morphemes = [m for m in morphemes if m not in exclude_names]
                if core_morphemes and len(core_morphemes) < len(morphemes):
                    abbr_from_morphemes = "".join(core_morphemes)
                    if len(abbr_from_morphemes) >= 3:
                        # 이 축소된 약어로 전체 풀 재스캔
                        all_candidates = list(set(
                            [ot["title"] for ot in official_titles]
                            + [c for c in title_pool if c not in community_titles]
                        ))
                        for candidate in all_candidates:
                            if len(candidate) < 4 or len(candidate) > 40:
                                continue
                            score = abbreviation_match_score(abbr_from_morphemes, candidate)
                            if score > best_score:
                                best_score = score
                                best_title = candidate
                                best_source = f"morpheme_rescue({abbr_from_morphemes})"

                        # content 패턴도 재시도
                        for sr in search_results:
                            content = (sr.get("content") or sr.get("snippet") or "")
                            for pat in content_title_patterns:
                                for m_pat in pat.finditer(content):
                                    candidate = m_pat.group(1).strip()
                                    candidate = _re_rescue.sub(r'[\.\s]+$', '', candidate)
                                    if 3 <= len(candidate) <= 30:
                                        score = abbreviation_match_score(abbr_from_morphemes, candidate)
                                        if score > best_score:
                                            best_score = score
                                            best_title = candidate
                                            best_source = f"morpheme_content({abbr_from_morphemes})"

                        # title suffix 패턴도 재시도
                        for sr in search_results:
                            sr_title = (sr.get("title") or "").strip()
                            if not sr_title:
                                continue
                            for pat in title_suffix_patterns:
                                m_pat = pat.search(sr_title)
                                if m_pat:
                                    candidate = m_pat.group(1).strip()
                                    if 4 <= len(candidate) <= 30 and candidate not in community_titles:
                                        score = abbreviation_match_score(abbr_from_morphemes, candidate)
                                        if score > best_score:
                                            best_score = score
                                            best_title = candidate
                                            best_source = f"morpheme_suffix({abbr_from_morphemes})"

                        if best_score >= rescue_min_score:
                            print(
                                f"[{_ts()}][{self.emoji}] 🧩 Morpheme rescue: "
                                f"'{original}' → morphemes={morphemes} → "
                                f"core='{abbr_from_morphemes}' → '{best_title}' "
                                f"(score={best_score:.2f}, min={rescue_min_score})",
                                file=sys.stderr,
                            )

        # 🆕 BUG-6: rescue 후보의 출처 검증 — 소설 플랫폼 도메인이 아니면 거부
        _NOVEL_PLATFORM_DOMAINS = (
            "novelpia.com", "munpia.com", "series.naver.com", "page.kakao.com",
            "joara.com", "namu.wiki", "ridibooks.com", "bookoa.com",
            "novelupdates.com", "syosetu.com",
        )
        if best_title and best_source and best_source.startswith("title_"):
            # title_pool/title_suffix 출처 — 공식 플랫폼 도메인 여부 확인
            has_novel_platform_src = False
            for sr in search_results:
                sr_title_raw = (sr.get("title") or "").strip()
                sr_url = sr.get("url", "")
                if best_title in sr_title_raw or best_title == sr_title_raw:
                    if any(d in sr_url for d in _NOVEL_PLATFORM_DOMAINS):
                        has_novel_platform_src = True
                        break
            if not has_novel_platform_src:
                # 커뮤니티 글 제목을 소설 제목으로 오인하는 것 방지
                print(
                    f"[{_ts()}][{self.emoji}] 🚫 Rescue 거부: "
                    f"'{best_title}' 출처({best_source})가 소설 플랫폼 도메인이 아님",
                    file=sys.stderr,
                )
                best_title = None
                best_score = 0.0

        # 최소 기준: score ≥ rescue_min_score (BUG-1: discourse 경고 시 0.85, 기본 0.75)
        if best_title and best_score >= rescue_min_score:
            return best_title, best_score, best_source
        return None, 0.0, None

    # 🆕 BUG-B 방어: 검색 결과 제목에서 사이트명/게시판 접두어 정제
    _SITE_PREFIX_PATTERNS = [
        # "블라인드 | 웹소설 종토방: 오늘도요 - 즉사기 들고 무림에 떨어지다"
        # → "즉사기 들고 무림에 떨어지다"
        _re.compile(r'^.+?\|\s*.+?:\s*.+?\s*-\s*'),
        # "블라인드 | 웹소설 종토방 - 작품명"
        _re.compile(r'^.+?\|\s*.+?\s*-\s*'),
        # "[문피아]작품명 > 작품소개 - 타입문넷"
        _re.compile(r'^\[.+?\]\s*'),
        # "작품명 > 작품소개 - 타입문넷" 에서 뒷부분
        _re.compile(r'\s*>\s*.+?(?:\s*-\s*.+)?$'),
        # "문피아 신작 무협소설 - 작품명 독후감." 에서 접두사
        _re.compile(r'^.+?\s*신작\s*.+?\s*-\s*'),
    ]

    # 사이트명으로 잘 쓰이는 접두어 리스트
    _KNOWN_SITE_PREFIXES = (
        "블라인드", "에펨코리아", "루리웹", "인벤", "클리앙", "디시인사이드",
        "아카라이브", "에펨", "뽐뿌", "오늘의유머", "더쿠", "인스티즈",
        "치지직", "웹소설로 꿈꾸는 세상!", "나무위키",
        "종토방", "웹소설 종토방", "웹소설종토방",
        "팬시", "리디북스", "리디", "카카오페이지",
        "네이버 시리즈", "시리즈", "조아라", "문피아",
        "오늘도요",
    )

    # 사이트명 오염 패턴 (제목 내부에서도 감지)
    _SITE_NOISE_PATTERNS = (
        "종토방:", "웹소설 종토방", "블라인드 |",
        "마이너 갤러리", "| 웹소설", "| 장르소설",
        "> 작품소개", "- 나무위키", "- 네이버 블로그",
        "- 리디", "- 예스24", "- 에펨코리아",
        "- 웹툰/웹소설", "오늘도요 -",
    )

    def _clean_search_result_title(self, raw_title: str) -> list[str]:
        """검색 결과 제목에서 사이트명/게시판 접두어를 정제하여 작품명 후보 목록 반환.
        
        "블라인드 | 웹소설 종토방: 오늘도요 - 즉사기 들고 무림에 떨어지다"
        → ["블라인드 | 웹소설 종토방: 오늘도요 - 즉사기 들고 무림에 떨어지다",
            "즉사기 들고 무림에 떨어지다",
            "오늘도요 - 즉사기 들고 무림에 떨어지다"]
        
        원본 제목은 항상 포함하고, 분리된 부분도 후보로 추가.
        """
        # 원본에 사이트명 오염이 있으면 원본을 결과에서 제외
        _has_site_noise = any(p in raw_title for p in self._SITE_NOISE_PATTERNS)
        results: list[str] = [] if _has_site_noise else [raw_title]
        
        # " - " 구분자로 분할 (가장 흔한 패턴)
        if " - " in raw_title:
            parts = raw_title.split(" - ")
            for part in parts:
                part = part.strip()
                # 너무 짧은 사이트명이나 카테고리만 있는 부분은 제외
                if len(part) < 3:
                    continue
                # 알려진 사이트명 접두어면 제외
                if any(part.startswith(sp) for sp in self._KNOWN_SITE_PREFIXES):
                    continue
                # " | " 등 사이트 구분자가 포함된 부분은 제외
                if " | " in part:
                    continue
                if part not in results and len(part) <= 50:
                    results.append(part)
        
        # " | " 구분자로 분할 (블라인드 등)
        if " | " in raw_title:
            parts = raw_title.split(" | ")
            for part in parts:
                part = part.strip()
                if len(part) < 3 or len(part) > 50:
                    continue
                if any(part.startswith(sp) for sp in self._KNOWN_SITE_PREFIXES):
                    continue
                if " - " in part:
                    # "웹소설 종토방: 오늘도요 - 작품명" → 마지막 " - " 이후
                    sub = part.split(" - ")[-1].strip()
                    if sub and sub not in results and 3 <= len(sub) <= 50:
                        results.append(sub)
                if part not in results:
                    results.append(part)
        
        # ": " 구분자 (게시판: 제목)
        if ": " in raw_title:
            after_colon = raw_title.split(": ")[-1].strip()
            if after_colon and after_colon not in results and 3 <= len(after_colon) <= 50:
                results.append(after_colon)
        
        return results

    def _extract_title_candidates_from_text(
        self, text: str, pool: list[str],
    ) -> None:
        """
        검색 결과 content/snippet에서 잠재적 작품 제목을 추출하여 pool에 추가.

        패턴:
        1. "제목 그대로 X" → X
        2. 플랫폼명 + 작품명 구문
        3. 장르 접두사 + 작품명 (munpia 검색 페이지)
        4. Kiwi 명사 2~4개 연결 구문
        """
        # 패턴 1: "제목 그대로 X"
        for m in _re.finditer(r'제목\s*그대로\s+(.+?)(?:인|의|을|를|이|가|에)\s', text):
            cand = m.group(1).strip()
            if 3 <= len(cand) <= 30:
                pool.append(cand)

        # 패턴 2: "문피아에 X란" / "X란 소설"
        for m in _re.finditer(
            r'(?:문피아|노벨피아|카카오페이지|네이버시리즈|조아라)(?:에)?\s+(.+?)'
            r'(?:란|라는|이란|이라는|\.)', text
        ):
            cand = m.group(1).strip()
            if 3 <= len(cand) <= 30:
                pool.append(cand)

        # 패턴 3: munpia 검색 페이지 장르 접두사
        genre_prefixes = [
            "무협", "판타지", "현대판타지", "로맨스", "로판", "SF",
            "게임", "퓨전", "BL", "라이트노벨", "대체역사", "스포츠",
            "미스터리", "호러", "드라마", "액션", "모험", "학원",
        ]
        for genre in genre_prefixes:
            for m in _re.finditer(
                rf'{genre}\.\s*(?:NEW\s*)?(.+?)(?:\.\s*총\s*\d+화|\.\s*\d+|$)',
                text, _re.DOTALL,
            ):
                cand = _re.sub(r'[.\s]+$', '', m.group(1)).strip()
                if 3 <= len(cand) <= 30:
                    pool.append(cand)

        # 패턴 4: Kiwi 명사 연결 (후보 제목 내 명사 추출)
        nouns = kiwi_nouns(self._kiwi, text)
        # 인접 명사 2~3개 연결을 후보로 추가
        for wlen in range(2, min(4, len(nouns) + 1)):
            for start in range(len(nouns) - wlen + 1):
                phrase = " ".join(nouns[start:start + wlen])
                if 4 <= len(phrase) <= 25:
                    pool.append(phrase)
    
    def _guard_platform_feature_as_title(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 Phase27-C: 플랫폼 기능 용어 가드

        포스트 제목에 플랫폼 약칭(노피아, 문피아 등)과 기능 용어(콘, 뱃지, 이모티콘 등)가
        함께 등장하면 → 소설 제목이 아니라 플랫폼 메타 글.

        예: "노피아 가운데에서 빔 나오는 콘이 있는거보소" → meta (소설 아님)
            "부기피아 뚱라니 뱃지 개쳐귀엽네" → meta (소설 아님)
        """
        post_title = ""
        gk = ctx.expert_outputs.get("gatekeeper") or {}
        raw_post = getattr(ctx, 'raw_post', None)
        if raw_post:
            post_title = raw_post.get("title", "") if isinstance(raw_post, dict) else ""
        if not post_title:
            # Gatekeeper의 notes에서 제목 추출 시도
            post_title = gk.get("notes", "")

        if not post_title:
            return result

        title_lower = post_title.lower()

        # 플랫폼 약칭이 제목에 있는지 확인
        has_platform = any(pa in title_lower for pa in PLATFORM_ABBREVIATIONS)
        if not has_platform:
            return result

        # 플랫폼 기능 용어가 제목에 있는지 확인
        feature_hits = [ft for ft in PLATFORM_FEATURE_TERMS if ft in title_lower]
        if not feature_hits:
            return result

        # 둘 다 있으면 → 소설이 아닌 플랫폼 메타 글
        print(
            f"[{_ts()}][{self.emoji}] 🛡️ 플랫폼 기능 가드: "
            f"제목에 플랫폼 약칭 + 기능 용어({feature_hits}) 동시 존재 "
            f"→ 모든 후보 title=null, confidence=none",
            file=sys.stderr
        )

        for term in result.get("decoded_terms", []):
            best_match = term.get("best_match") or {}
            if best_match.get("title"):
                best_match["title"] = None
                best_match["confidence"] = "none"
            for cand in term.get("candidates", []):
                cand["official_novel_title"] = None

        result["overall_confidence"] = "none"
        result["notes"] = (result.get("notes", "") or "") + \
            f" [플랫폼 기능 가드] 제목에 플랫폼 약칭+기능 용어({feature_hits}) → meta 판정."

        return result

    def _guard_association_pattern(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 Phase27-B: 연상 패턴 가드

        제목에 "X이란 단어가 떠올랐는데", "X 생각났" 등 연상 패턴이 있으면
        X를 소설 제목으로 매칭하지 못하도록 차단.

        예: "이거 보고 도태한남이란 단어가 떠올랐는데" → "도태한남"은 일반 용어 연상
        """
        post_title = ""
        raw_post = getattr(ctx, 'raw_post', None)
        if raw_post:
            post_title = raw_post.get("title", "") if isinstance(raw_post, dict) else ""

        if not post_title:
            return result

        # 연상 패턴 매칭
        matched_pattern = None
        for pattern in ASSOCIATION_PATTERNS:
            if pattern in post_title:
                matched_pattern = pattern
                break

        if not matched_pattern:
            return result

        # 본문에 작품 고유 정보(캐릭터명, 줄거리 등)가 있는지 확인
        # Gatekeeper가 감지한 entities 중 possible_characters가 있으면 실제 작품 토론일 수 있음
        gk = ctx.expert_outputs.get("gatekeeper") or {}
        gk_entities = gk.get("detected_entities") or {}
        has_characters = bool(gk_entities.get("possible_characters"))

        # DiscourseAnalyzer가 novel_literature가 아닌 도메인으로 판정했는지 확인
        discourse_out = ctx.expert_outputs.get("discourse") or {}
        discourse_analysis = discourse_out.get("discourse_analysis") or {}
        domain = discourse_analysis.get("primary_domain", "")
        is_novel_domain = domain == "novel_literature"

        # 연상 패턴이 있고, 소설 도메인도 아니고, 캐릭터도 없으면 → 차단
        if not is_novel_domain and not has_characters:
            print(
                f"[{_ts()}][{self.emoji}] 🛡️ 연상 패턴 가드: "
                f"제목에 '{matched_pattern}' 패턴 감지 + "
                f"domain={domain}(≠novel_literature) + 캐릭터 없음 "
                f"→ 모든 후보 confidence=low",
                file=sys.stderr
            )

            for term in result.get("decoded_terms", []):
                best_match = term.get("best_match") or {}
                if best_match.get("title"):
                    best_match["confidence"] = "low"

            if result.get("overall_confidence") in ("high", "medium"):
                result["overall_confidence"] = "low"

            result["notes"] = (result.get("notes", "") or "") + \
                f" [연상 패턴 가드] '{matched_pattern}' → 일반 용어 연상글로 추정."

        return result

    def _rescue_author_as_work_abbreviation(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 작가명=약칭 rescue: Decoder가 is_author_name=true로 판단한 term이
        실제로는 작품의 약칭인 경우를 검색 결과에서 감지하여 작품 식별로 전환.
        
        예: "담텔기" → Decoder가 작가명으로 판단 → 검색에서 
        "괴담 호텔 탈출기 — 약칭은 괴담텔" 발견 → 작가판정 취소, 작품 제목 설정
        """
        decoded_terms = result.get("decoded_terms", [])
        search_results = getattr(ctx, 'search_results', []) or []
        
        if not search_results:
            return result
        
        import re as _re_rescue
        
        for term in decoded_terms:
            if not term.get("is_author_name"):
                continue
            
            original = (term.get("original") or "").strip()
            if not original or len(original) < 2:
                continue
            
            # 이미 다른 term이 작품을 High confidence로 식별했으면 스킵
            other_has_high_title = any(
                t.get("best_match", {}).get("title")
                and t.get("best_match", {}).get("confidence") == "high"
                and not t.get("is_author_name")
                for t in decoded_terms
                if t is not term
            )
            if other_has_high_title:
                continue
            
            # original에서 핵심 이름 추출 (예: "담텔기 작가" → "담텔기")
            author_info = term.get("author_info") or {}
            author_name = (author_info.get("name") or original).strip()
            # "작가" 접미사 제거
            if author_name.endswith("작가") and len(author_name) > 2:
                author_name = author_name[:-2].strip()
            author_clean = author_name.replace(" ", "")
            
            found_title = None
            found_url = None
            found_platform = None
            
            for sr in search_results:
                sr_title = sr.get("title", "")
                sr_content = sr.get("content", "") or sr.get("snippet", "")
                sr_combined = f"{sr_title} {sr_content}"
                sr_url = sr.get("url", "")
                
                # 패턴 1: "약칭은 X" → X가 author_name과 유사
                abbr_match = _re_rescue.search(
                    r'약칭[은이가]?\s*([가-힣]{2,8})',
                    sr_combined,
                )
                if abbr_match:
                    detected_abbr = abbr_match.group(1)
                    # author_clean과 detected_abbr 유사도
                    overlap = sum(1 for c in author_clean if c in detected_abbr)
                    similarity = overlap / max(len(author_clean), len(detected_abbr), 1)
                    if similarity >= 0.5:
                        # 이 검색 결과에서 정식 제목 추출
                        if "namu.wiki" in sr_url:
                            found_title = sr_title.strip()
                            found_url = sr_url
                        elif not found_title:
                            # sr_title에서 " - " 이전 부분
                            if " - " in sr_title:
                                candidate = sr_title.split(" - ")[0].strip()
                                if len(candidate) >= 3 and candidate != author_name:
                                    found_title = candidate
                                    found_url = sr_url
                
                # 패턴 2: "줄여서 X", "X라고 줄인" 
                if not found_title:
                    abbr_match2 = _re_rescue.search(
                        rf'줄여서\s*{_re_rescue.escape(author_name)}',
                        sr_combined,
                    )
                    if abbr_match2 and " - " in sr_title:
                        found_title = sr_title.split(" - ")[0].strip()
                        found_url = sr_url
                
                # 패턴 3: "X라는 글/소설" + 같은 페이지에 정식 제목
                if not found_title:
                    ref_match = _re_rescue.search(
                        rf'{_re_rescue.escape(author_name)}[이라]?(라고|이라고)\s*(부르|줄)',
                        sr_combined,
                    )
                    if ref_match:
                        # sr_combined에서 정식 작품명 후보 추출
                        title_match = _re_rescue.search(
                            r'([가-힣][가-힣\s]{2,18}[가-힣])',
                            sr_title,
                        )
                        if title_match:
                            candidate = title_match.group(1).strip()
                            if (len(candidate) > len(author_name) + 2
                                and candidate != author_name
                                and not candidate.endswith("갤러리")
                                and not candidate.endswith("채널")):
                                found_title = candidate
                                found_url = sr_url
                
                # 패턴 4: 공식 플랫폼에서 author_name의 핵심 음절이 제목에 포함
                if not found_title:
                    platform_domains = ("novelpia.com", "munpia.com", "page.kakao.com", "series.naver.com")
                    if any(d in sr_url for d in platform_domains):
                        if " - " in sr_title:
                            potential = sr_title.split(" - ")[0].strip()
                            # author_clean 음절의 60% 이상이 정식 제목에 포함
                            potential_clean = potential.replace(" ", "")
                            char_overlap = sum(1 for c in author_clean if c in potential_clean)
                            if (char_overlap >= len(author_clean) * 0.6 
                                and len(potential) > len(author_name)
                                and potential != author_name):
                                found_title = potential
                                found_url = sr_url
                                found_platform = next(
                                    (d.split(".")[0] for d in platform_domains if d in sr_url),
                                    None,
                                )
                
                if found_title:
                    break
            
            if found_title:
                # author → abbreviation으로 전환
                term["is_author_name"] = False
                best_match = term.get("best_match") or {}
                old_title = best_match.get("title")
                best_match["title"] = found_title
                best_match["confidence"] = "medium"
                term["best_match"] = best_match
                
                if not term.get("candidates"):
                    term["candidates"] = []
                term["candidates"].insert(0, {
                    "official_novel_title": found_title,
                    "url": found_url,
                    "platform": found_platform,
                    "decode_logic": (
                        f"[작가명=약칭 rescue] '{author_name}'(is_author) "
                        f"→ 검색에서 작품 약칭 증거 → '{found_title}'"
                    ),
                    "morphological_score": 0.6,
                })
                
                if result.get("overall_confidence") in ("none", "low"):
                    result["overall_confidence"] = "medium"
                
                print(
                    f"[{_ts()}][{self.emoji}] 🔄 작가명=약칭 rescue: "
                    f"'{author_name}'(is_author) → '{found_title}' 작품 식별 전환",
                    file=sys.stderr,
                )
        
        return result

    def _guard_archetype_as_title(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 장르 아키타입 용어 방어: "초대남", "금태양", "거근쇼타" 같은
        장르 역할 용어를 소설 제목으로 매칭하지 못하도록 차단.
        
        추가로, 작가명은 식별했지만 제목이 아키타입 용어인 경우
        → 제목을 null로 변경 (작가는 맞지만 제목 미확인)
        """
        # 작가 식별 여부 확인
        has_author = False
        author_name = None
        for term in result.get("decoded_terms", []):
            if term.get("is_author_name"):
                has_author = True
                ai = term.get("author_info") or {}
                author_name = ai.get("name") or term.get("original")
                break
        
        decoded_terms = result.get("decoded_terms", [])
        for term in decoded_terms:
            if term.get("is_author_name"):
                continue
            
            best_match = term.get("best_match") or {}
            title = best_match.get("title")
            if not title:
                continue
            
            original = term.get("original", "")
            
            # 원본 키워드가 장르 아키타입 용어인지 확인
            is_archetype = original.strip() in GENRE_ARCHETYPE_TERMS
            
            if not is_archetype:
                continue
            
            # 아키타입 용어가 제목 후보의 일부로 들어간 경우
            # (예: "초대남" → "초대남 B"로 매칭) → 차단
            old_conf = best_match.get("confidence", "medium")
            best_match["title"] = None
            best_match["confidence"] = "none"
            
            # overall_confidence도 하향
            if result.get("overall_confidence") in ("high", "medium"):
                result["overall_confidence"] = "low"
            
            reason = f"아키타입 용어 '{original}'은 제목이 아님"
            if has_author:
                reason += f" (작가 '{author_name}' 식별됨, 제목 미확인)"
            
            print(f"[{_ts()}][{self.emoji}] 🛡️ 아키타입 제목 차단: "
                  f"'{title}' → null ({reason}, confidence={old_conf}→none)",
                  file=sys.stderr)
        
        return result
    
    def _apply_discourse_warning(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🔥 Discourse 역방향 Override: non-novel 도메인 또는 장르 일반론 경고 시 Decoder 신뢰도 강제 제동
        
        DiscourseAnalyzer가 memes_humor/daily_life 등으로 판정했거나,
        discuss_genre(장르/트로프 일반론)로 판정한 경우,
        Decoder가 작품을 식별했더라도 본문/댓글에 실제 작품 관련 증거가 있는지 확인.
        증거 없으면 신뢰도 강제 하향.
        
        author_talk(작가 비평)은 코드 강제 제동 없이 LLM 프롬프트 이해력으로 처리.
        """
        discourse_warning = getattr(ctx, 'discourse_warning', None)
        if not discourse_warning:
            return result
        
        # Decoder가 실제로 무언가를 식별했는지 확인
        has_match = False
        for term in result.get("decoded_terms", []):
            best = term.get("best_match") or {}
            if best.get("title") and best.get("confidence") in ("high", "medium"):
                has_match = True
                break
        
        if not has_match:
            return result  # 이미 식별 실패 → 추가 처리 불필요
        
        # 본문/댓글에 소설 관련 구체적 증거가 있는지 확인
        post_data = getattr(ctx, 'post_data', {}) or {}
        content_texts = []
        for block in post_data.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                content_texts.append(block["text"])
            elif isinstance(block, str):
                content_texts.append(block)
        all_text = " ".join(content_texts + (getattr(ctx, 'comments', []) or []))
        all_text_lower = all_text.lower()
        
        # 소설 관련 키워드 존재 여부 확인
        novel_evidence_keywords = [
            "작가", "연재", "완결", "웹소설", "소설", "문피아", "노벨피아",
            "카카오페이지", "네이버시리즈", "조아라", "리디북스",
            "신작", "후기", "리뷰", "스포", "스포일러",
            "주인공", "히로인", "빌런", "먼치킨",
            "회귀", "환생", "전생", "이세계", "헌터",
        ]
        
        is_genre_warning = discourse_warning and ("discuss_genre" in discourse_warning or "genre_discussion" in discourse_warning)
        
        if is_genre_warning:
            # 장르 일반론 경고: 더 엄격한 기준 — 역할명/장르키워드는 증거 불충분
            # 작품 고유 정보(작가명, 플랫폼, 회차, 스포일러 등)만 인정
            novel_evidence_keywords = [
                "작가", "연재", "완결", "문피아", "노벨피아",
                "카카오페이지", "네이버시리즈", "조아라", "리디북스",
                "신작", "스포", "스포일러",
                "화", "편", "권",  # 회차 표현
            ]
        
        evidence_found = any(kw in all_text_lower for kw in novel_evidence_keywords)
        
        # 🆕 검색에서 확인된 작가명이 본문/댓글에 존재하면 → 강력한 소설 증거
        # (예: "돌마늘"이 본문에 있고 검색에서 "죽었다 깨어도 수선"의 작가로 확인)
        if not evidence_found:
            _snippet_hints = getattr(ctx, 'snippet_hints', {}) or {}
            _snippet_authors = _snippet_hints.get("author_hints", []) or []
            # Decoder의 decoded_terms에서 is_author_name인 term의 original도 포함
            _decoder_authors = set()
            for _dt in result.get("decoded_terms", []):
                if _dt.get("is_author_name"):
                    _ao = (_dt.get("author_info") or {}).get("name", "")
                    if _ao:
                        _decoder_authors.add(_ao.lower().replace(" ", ""))
                    _orig = _dt.get("original", "")
                    if _orig:
                        _decoder_authors.add(_orig.lower().replace(" ", ""))
            _all_authors = set(
                (a.get("name") if isinstance(a, dict) else str(a)).lower().replace(" ", "")
                for a in _snippet_authors
                if a and len((a.get("name") if isinstance(a, dict) else str(a))) >= 2
            )
            _all_authors |= _decoder_authors
            
            if any(a in all_text_lower.replace(" ", "") for a in _all_authors if a):
                evidence_found = True
                _matched = [a for a in _all_authors if a and a in all_text_lower.replace(" ", "")]
                print(
                    f"[{_ts()}][{self.emoji}] 🔒 Discourse 역방향 제동 면제: "
                    f"검색 확인 작가명이 본문에 존재 (작가: {_matched})",
                    file=sys.stderr,
                )
        
        # 본문/댓글에 소설 관련 증거 전무 → 신뢰도 강제 하향
        # (evidence_found=True이면 면제)
        if not evidence_found:
            for term in result.get("decoded_terms", []):
                best = term.get("best_match") or {}
                if best.get("title") and best.get("confidence") in ("high", "medium"):
                    old_conf = best["confidence"]
                    best["confidence"] = "low"
                    print(f"[{_ts()}][{self.emoji}] 🚨 Discourse 역방향 제동: '{best.get('title')}' "
                          f"confidence={old_conf}→low (discourse_warning={discourse_warning}, "
                          f"본문에 소설 관련 증거 없음)", file=sys.stderr)
            
            # overall_confidence도 하향
            if result.get("overall_confidence") in ("high", "medium"):
                result["overall_confidence"] = "low"
        
        return result
    
    def _get_best_candidate(self, result: Dict[str, Any]) -> Optional[str]:
        """Get the best decoded title from result."""
        for term in result.get("decoded_terms", []):
            best = term.get("best_match", {})
            if best.get("title") and best.get("confidence") in ("high", "medium"):
                return best["title"]
        return None
    
    def needs_verification_search(self, result: Dict[str, Any]) -> bool:
        """Check if decoder requests additional verification search."""
        return result.get("needs_verification", False)
    
    def get_verification_query(self, result: Dict[str, Any]) -> Optional[List[str]]:
        """Get the verification search queries if needed."""
        vs = result.get("verification_search")
        if vs and isinstance(vs, list):
            return vs
        return None
    
    def get_best_candidates(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all candidates with confidence >= medium."""
        candidates = []
        for term in result.get("decoded_terms", []):
            best = term.get("best_match", {})
            if best.get("title") and best.get("confidence") in ("high", "medium"):
                candidates.append({
                    "original_term": term.get("original"),
                    "title": best["title"],
                    "confidence": best["confidence"],
                    "is_author": term.get("is_author_name", False),
                })
        return candidates

    def _extract_official_titles_from_search(self, ctx: Any) -> List[Dict[str, str]]:
        """
        🔥 검색 결과에서 공식 플랫폼(novelpia, namu.wiki, munpia)의 정확한 제목 추출
        
        Returns:
            List of {"title": str, "platform": str, "url": str}
        """
        import re
        official_titles = []
        
        search_results = getattr(ctx, "search_results", []) or []
        official_platforms = OFFICIAL_PLATFORMS
        
        for result in search_results:
            url = result.get("url", "")
            title_from_result = result.get("title", "")
            snippet = result.get("snippet", "")
            
            # 공식 플랫폼인지 확인
            platform = None
            for p in official_platforms:
                if p in url:
                    platform = p
                    break
            
            if not platform:
                continue
            
            # 방법 1: 검색 결과의 title에서 직접 추출 (novelpia 형식)
            # 예: "웹소설로 꿈꾸는 세상! - 죽었다 깨어도 수선"
            if " - " in title_from_result:
                parts = title_from_result.split(" - ")
                if len(parts) >= 2:
                    extracted_title = parts[-1].strip()
                    # 불필요한 접미사 제거
                    extracted_title = re.sub(r'\s*\(r\d+\s*판\)$', '', extracted_title)
                    if len(extracted_title) >= 3 and len(extracted_title) <= 50:
                        official_titles.append({
                            "title": extracted_title,
                            "platform": platform,
                            "url": url,
                        })
                        continue
            
            # 방법 2: namu.wiki URL에서 직접 추출
            # 예: https://namu.wiki/w/죽었다%20깨어도%20수선
            if "namu.wiki/w/" in url:
                import urllib.parse
                try:
                    path = url.split("/w/")[-1]
                    # URL 디코딩
                    decoded_path = urllib.parse.unquote(path)
                    # (r숫자 판) 형식 제거
                    decoded_path = re.sub(r'\s*\(r\d+\s*판\)$', '', decoded_path)
                    # 🆕 나무위키 하위 페이지 필터: '/등장인물', '/설정' 등은 상위 작품명만 추출
                    _NAMU_SUBPAGE_SUFFIXES = (
                        "/등장인물", "/설정", "/스토리", "/줄거리",
                        "/에피소드", "/평가", "/논란", "/디스코그래피",
                        "/OST", "/안내", "/발매 현황", "/작중 행위",
                        "/발매현황", "/작중행위",
                    )
                    for suffix in _NAMU_SUBPAGE_SUFFIXES:
                        if decoded_path.endswith(suffix):
                            decoded_path = decoded_path[:-len(suffix)]
                            break
                    # '/' 남은 하위 페이지도 제거 (예: "신의 탑/등장인물/2부")
                    if "/" in decoded_path:
                        decoded_path = decoded_path.split("/")[0]
                    if len(decoded_path) >= 3 and len(decoded_path) <= 50:
                        official_titles.append({
                            "title": decoded_path,
                            "platform": platform,
                            "url": url,
                        })
                        continue
                except Exception:
                    pass
            
            # 방법 3: 제목만 있는 경우 (예: "죽었다 깨어도 수선")
            clean_title = re.sub(r'\s*\(r\d+\s*판\)$', '', title_from_result).strip()
            if len(clean_title) >= 3 and len(clean_title) <= 50 and " - " not in clean_title:
                official_titles.append({
                    "title": clean_title,
                    "platform": platform,
                    "url": url,
                })
        
        # 🔥 방법 4: munpia/novelpia 검색 페이지의 content 필드에서 개별 작품 제목 추출
        # munpia 검색 결과 URL: ?menu=detailSearchV2&action=search...
        # content 형식: "무협. NEW즉사기 들고 무림에 떨어지다. 총 38화..."
        # title에는 "즉사기로 무한성장" (페이지 최상단 작품)이 있지만,
        # content에 실제 매칭되는 다른 작품이 포함되어 있을 수 있음
        for result in search_results:
            url = result.get("url", "")
            content = result.get("content", "") or result.get("snippet", "")
            
            # 검색 페이지인지 확인 (munpia/novelpia)
            is_search_page = False
            platform = None
            for p in official_platforms:
                if p in url:
                    platform = p
                    break
            
            if not platform:
                continue
            
            # 검색 페이지 URL 패턴 감지
            if any(kw in url for kw in ["search", "detailSearch", "searchKey", "keyword"]):
                is_search_page = True
            
            if not is_search_page or not content:
                continue
            
            # content에서 작품 제목 추출 패턴:
            # "장르. [NEW]제목. 총 N화" 또는 "장르. 제목. 작가명"
            genre_prefixes = [
                "무협", "판타지", "현대판타지", "로맨스", "로판", "SF",
                "게임", "퓨전", "BL", "라이트노벨", "대체역사", "스포츠",
                "미스터리", "호러", "드라마", "액션", "모험", "학원",
            ]
            
            for genre in genre_prefixes:
                # 패턴: "무협. NEW제목. " 또는 "무협. 제목. "
                pattern = re.compile(
                    rf'{genre}\.\s*(?:NEW\s*)?(.+?)(?:\.\s*총\s*\d+화|\.\s*\d+|\.\s*[가-힣]{{2,4}}(?:\s*작가)?|$)',
                    re.DOTALL
                )
                for m in pattern.finditer(content):
                    extracted = m.group(1).strip()
                    # 정리: 앞뒤 공백, 마침표 제거
                    extracted = re.sub(r'[\.\s]+$', '', extracted).strip()
                    if 3 <= len(extracted) <= 30:
                        # 이미 title 필드와 같은 제목이면 스킵
                        title_from_result = result.get("title", "")
                        if extracted != title_from_result.strip():
                            official_titles.append({
                                "title": extracted,
                                "platform": platform,
                                "url": url,
                                "source": "content_field",
                            })
        
        # 중복 제거 (제목 기준)
        seen = set()
        unique_titles = []
        for t in official_titles:
            if t["title"] not in seen:
                seen.add(t["title"])
                unique_titles.append(t)
        
        return unique_titles
    
    def _correct_title_with_search_result(self, llm_title: str, official_titles: List[Dict[str, str]]) -> str:
        """
        🔥 LLM이 생성한 제목을 검색 결과의 공식 제목과 비교하여 교정
        
        문제 상황:
        - LLM 생성: "죽었다 깨어나도 수선" (잘못된 조사 "나")
        - 검색 결과: "죽었다 깨어도 수선" (정확한 제목)
        
        🔥 best-match 방식: 모든 후보 중 가장 높은 유사도 선택 (first-match 아님)
        🔥 LLM 제목이 검색 결과에 정확히 존재하면 교정하지 않음
        🔥 빈도 가중치: 같은 제목이 여러 검색 결과에 등장하면 우선
        
        Args:
            llm_title: LLM이 생성한 제목
            official_titles: 검색 결과에서 추출한 공식 제목 목록
            
        Returns:
            교정된 제목 (일치하는 공식 제목이 있으면 그것, 없으면 원본)
        """
        if not official_titles:
            return llm_title
        
        from difflib import SequenceMatcher
        from collections import Counter
        
        llm_title_normalized = llm_title.strip()
        
        # 🔥 Step 0: LLM 제목이 검색 결과에 정확히 존재하면 교정 불필요
        for official in official_titles:
            if llm_title_normalized == official["title"].strip():
                return llm_title_normalized
        
        # 🔥 Step 1: 빈도 계산 — 같은 제목이 여러 검색 결과에 등장하면 신뢰도↑
        title_freq = Counter(o["title"].strip() for o in official_titles)
        
        # 🔥 Step 2: best-match 방식 — 모든 후보를 평가하고 최고 점수 선택
        best_candidate = None
        best_score = 0.0
        
        for official in official_titles:
            official_title = official["title"].strip()
            
            min_len = min(len(llm_title_normalized), len(official_title))
            if min_len < 3:
                continue
            
            # 길이 차이가 너무 크면 스킵 (완전히 다른 제목)
            if abs(len(llm_title_normalized) - len(official_title)) > 4:
                continue
            
            similarity = SequenceMatcher(None, llm_title_normalized, official_title).ratio()
            
            # 빈도 보너스: 같은 제목이 N번 등장하면 +0.02*N (최대 +0.10)
            freq_bonus = min(title_freq[official_title] * 0.02, 0.10)
            adjusted_score = similarity + freq_bonus
            
            if adjusted_score > best_score:
                best_score = adjusted_score
                best_candidate = official
        
        # 🔥 Step 3: 임계값 0.80 이상일 때만 교정 (0.70→0.80 상향)
        if best_candidate and best_score >= 0.80:
            corrected = best_candidate["title"].strip()
            if corrected != llm_title_normalized:
                print(f"[{_ts()}][{self.emoji}] ⚠️ 제목 교정: LLM='{llm_title}' → 공식='{corrected}' "
                      f"(score={best_score:.2f}, platform={best_candidate['platform']})", file=sys.stderr)
                return corrected
        
        return llm_title

    def _guard_no_body_evidence(
        self,
        result: Dict[str, Any],
        gatekeeper_result: Dict[str, Any],
        ctx: Any,
    ) -> Dict[str, Any]:
        """
        🔥 본문 증거 가드: Decoder가 title을 매칭했지만 본문/댓글에 
        해당 작품의 구체적 증거가 전혀 없으면 confidence 하향.
        
        FP 핵심 패턴 대응:
        - "아카데미 습격할꺼면" (장르 일반론) → 검색→"아카데미의 습격자" 매칭 → FP
        - "장붕씨 무릉도원이세요?" (은어/밈) → 검색→"선협세상에서 슬라임이 살아남는 법" 매칭 → FP
        - "F급으로 주워서 S급" (밈/유머) → 검색→"웹소설로 꿈꾸는 세상!" → FP
        
        핵심 원리:
        게시글 본문/제목에 매칭된 작품의 고유 정보(캐릭터, 줄거리, 작가, 회차)가
        하나도 없으면, 해당 매칭은 키워드 우연 일치일 가능성이 높다.
        """
        decoded_terms = result.get("decoded_terms", [])
        if not decoded_terms:
            return result
        
        # 게시글 본문+제목+댓글 텍스트 수집
        post_data = getattr(ctx, 'post_data', {}) or {}
        post_title = post_data.get("title", "")
        post_body_parts = []
        for block in post_data.get("content_blocks", []):
            if isinstance(block, dict) and block.get("text"):
                post_body_parts.append(block["text"])
        post_body = " ".join(post_body_parts)
        
        comments_text = " ".join(getattr(ctx, 'comments', []) or [])
        full_text = f"{post_title} {post_body} {comments_text}".strip()
        full_text_lower = full_text.lower().replace(" ", "")
        
        if not full_text:
            return result
        
        # Gatekeeper가 감지한 엔티티 확인
        gk_entities = gatekeeper_result.get("detected_entities", {}) or {}
        gk_characters = gk_entities.get("possible_characters", []) or []
        gk_authors = gk_entities.get("possible_authors", []) or []
        
        # 🆕 범용 시간참조 가드: 게시글 제목에 "신작/최신작/전작" 등이 있는지 사전 감지
        # is_author_name 여부와 무관하게, 시간참조 키워드가 게시글 제목에 있으면
        # 특정 작품이 어떤 것인지 시점에 따라 달라지므로 확정 불가
        _temporal_keywords_universal = [
            "신작", "최신작", "새작품", "이번작", "전작", "차기작", "신간",
            "올라온것", "올라온거", "올린거", "나온거", "나온것",
            "최근연재", "요즘쓰는", "지금연재",
        ]
        _post_title_lower = post_title.lower().replace(" ", "")
        _has_temporal_in_post_title = any(
            tk in _post_title_lower for tk in _temporal_keywords_universal
        )
        
        changed = False
        title_clean = ""  # 🔧 방어적 초기화: 모든 term이 continue할 경우 대비
        for term in decoded_terms:
            best = term.get("best_match") or {}
            title = best.get("title")
            confidence = best.get("confidence", "none")
            
            if not title or confidence in ("none", "low"):
                continue
            
            # 🔧 title_clean을 루프 상단에서 미리 계산 (is_author_name 블록에서도 사용)
            title_clean = title.replace(" ", "").lower()
            
            # 🆕 범용 시간참조 가드 (is_author_name 무관)
            # 게시글 제목에 시간참조 키워드가 있고, 매칭된 작품 제목이 본문+제목에 직접 없으면 차단
            # 예: "개돌 신작 초대남이..." → "개돌"이 작가인지 LLM이 모르더라도
            #     "신작"이 제목에 있고, 매칭된 "NTR게임의 함장이 되었다"가 본문에 없으면 차단
            if _has_temporal_in_post_title:
                _matched_title_clean = title.replace(" ", "").lower()
                _title_in_full_text = _matched_title_clean in full_text_lower
                
                # 매칭된 제목의 알려진 약칭도 체크
                _known_abbrevs_for_title = set()
                for _ka_key, _ka_val in KNOWN_ABBREVIATIONS.items():
                    if _ka_val.replace(" ", "").lower() == _matched_title_clean:
                        _known_abbrevs_for_title.add(_ka_key.lower().replace(" ", ""))
                _abbrev_in_full_text = any(
                    ab in full_text_lower for ab in _known_abbrevs_for_title if ab
                )
                
                # 검색 결과에서 "신작"과 해당 작품이 명시적으로 연결되는 증거가 있는지
                _temporal_search_confirmed = False
                search_results_temp = getattr(ctx, 'search_results', []) or []
                for sr in search_results_temp:
                    sr_combined = f"{sr.get('title', '')} {sr.get('content', '')}".lower().replace(" ", "")
                    # 검색 결과에 매칭된 제목 + "신작" 등이 함께 나타나면 = 검색이 이 작품을 신작으로 확인
                    if _matched_title_clean in sr_combined and any(
                        tk in sr_combined for tk in _temporal_keywords_universal
                    ):
                        _temporal_search_confirmed = True
                        break
                
                if not _title_in_full_text and not _abbrev_in_full_text and not _temporal_search_confirmed:
                    old_conf = confidence
                    best["confidence"] = "none"
                    best["title"] = None
                    result["overall_confidence"] = "none"
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 범용 시간참조 가드: "
                        f"'{term.get('original')}' → '{title}' 매칭 차단 "
                        f"(게시글 제목에 시간참조 키워드 + 매칭 작품이 본문/검색에서 미확인, "
                        f"{old_conf}→none)",
                        file=sys.stderr,
                    )
                    changed = True
                    continue
            
            # 🆕 0) is_author_name=true인 term은 본문에 작가명(original)이 있으면 스킵
            # 핵심: "돌마늘"이 is_author_name=true이고 best_match.title="죽었다 깨어도 수선"일 때,
            # 본문에 "돌마늘"이 존재하면 그 자체가 작품 고유 증거 (작가=작품 식별)
            # 🔥 예외: "작가명 + 시간적 지칭(신작/최신작 등)"만 있고 제목/약칭이 본문에 없으면 → 가드 통과
            if term.get("is_author_name"):
                _orig_lower = (term.get("original") or "").replace(" ", "").lower()
                _author_name_lower = ((term.get("author_info") or {}).get("name") or "").replace(" ", "").lower()
                if (_orig_lower and _orig_lower in full_text_lower) or \
                   (_author_name_lower and _author_name_lower in full_text_lower):
                    # 작가명이 본문에 존재 — 그러나 시간적 지칭만으로 연결된 경우 스킵하면 안 됨
                    _temporal_keywords = ["신작", "최신작", "새작품", "이번작", "전작",
                                          "올라온것", "올라온거", "올린거", "나온거", "나온것",
                                          "최근연재", "요즘쓰는", "지금연재"]
                    _has_temporal = any(tk in full_text_lower for tk in _temporal_keywords)
                    # 매칭된 제목이나 그 약칭이 본문에 직접 언급되는지 확인
                    _title_in_text = title_clean in full_text_lower
                    # 제목의 커뮤니티 약칭도 체크 (예: "애호뉴비")
                    _snippet_abbrevs = []
                    for sr in (getattr(ctx, 'search_results', []) or []):
                        _sr_text = f"{sr.get('title', '')} {sr.get('content', '')}".lower()
                        if title_clean in _sr_text.replace(" ", ""):
                            import re as _re_abbr
                            for m in _re_abbr.findall(r"약칭[은는이가]?\s*['\"]?([가-힣a-zA-Z0-9]{2,6})['\"]?", _sr_text):
                                _snippet_abbrevs.append(m.lower().replace(" ", ""))
                    _abbrev_in_text = any(ab in full_text_lower for ab in _snippet_abbrevs if ab)
                    
                    if _has_temporal and not _title_in_text and not _abbrev_in_text:
                        # 시간적 지칭만 있고 제목/약칭 미등장 → 가드 통과 (스킵하지 않음)
                        print(
                            f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 적용: "
                            f"'{term.get('original')}' → '{title}' "
                            f"(is_author_name=true, 시간적 지칭만 존재, 제목/약칭 본문 미등장)",
                            file=sys.stderr,
                        )
                        # 가드 통과 → confidence 하향 처리 (아래 로직으로 계속)
                    else:
                        print(
                            f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵: "
                            f"'{term.get('original')}' → '{title}' (is_author_name=true, 본문에 작가명 존재)",
                            file=sys.stderr,
                        )
                        continue
            
            # 매칭된 제목의 핵심 키워드가 본문에 있는지 확인
            # (title_clean은 루프 상단에서 이미 할당됨)
            
            # 1) 제목 자체가 본문에 명시적으로 존재하면 OK
            if title_clean in full_text_lower:
                continue
            
            # 2) 검색 결과에서 이 작품의 캐릭터/작가 정보 추출
            work_specific_evidence = []
            search_results = getattr(ctx, 'search_results', []) or []
            for sr in search_results:
                sr_text = f"{sr.get('title', '')} {sr.get('content', '')}".lower()
                sr_url = sr.get("url", "").lower()
                
                # 공식 플랫폼에서 이 작품 정보가 있으면 캐릭터/작가 추출
                if title_clean in sr_text.replace(" ", ""):
                    # 이 검색 결과에서 작가명 패턴 추출
                    import re as _re_local
                    author_patterns = _re_local.findall(
                        r'작가[:\s]+([가-힣]{2,5})|([가-힣]{2,5})\s*작가',
                        sr_text,
                    )
                    for match in author_patterns:
                        name = match[0] or match[1]
                        if name:
                            work_specific_evidence.append(("author", name))
            
            # 3) Gatekeeper 엔티티 중 이 작품과 관련된 것이 본문에 있는지 확인
            has_character_evidence = any(
                ch.lower().replace(" ", "") in full_text_lower
                for ch in gk_characters
                if ch and len(ch) >= 2
            )
            has_author_evidence = any(
                au.lower().replace(" ", "") in full_text_lower
                for au in gk_authors
                if au and len(au) >= 2
            )
            
            # 🆕 3-B) Decoder가 is_author_name=true로 식별한 다른 term의 작가명도 체크
            # 핵심: "돌마늘"이 is_author_name=true이고 best_match.title="죽었다 깨어도 수선"이면,
            # "죽깨수" term의 본문증거 가드에서 "돌마늘"은 작품 고유 증거로 취급
            has_author_verified_by_decoder = False
            for other_term in decoded_terms:
                if other_term is term:
                    continue
                if not other_term.get("is_author_name"):
                    continue
                # 이 작가 term이 현재 term과 같은 작품을 가리키는지 확인
                other_title = (other_term.get("best_match") or {}).get("title", "")
                if not other_title:
                    continue
                if other_title.replace(" ", "").lower() == title_clean:
                    # 같은 작품! 작가명이 본문에 있는지 확인
                    author_original = (other_term.get("original") or "").replace(" ", "").lower()
                    author_name_from_info = ((other_term.get("author_info") or {}).get("name") or "").replace(" ", "").lower()
                    if (author_original and author_original in full_text_lower) or \
                       (author_name_from_info and author_name_from_info in full_text_lower):
                        has_author_verified_by_decoder = True
                        has_author_evidence = True  # 기존 플래그도 세팅
                        print(
                            f"[{_ts()}][{self.emoji}] 🔒 작가-작품 연결 검증: "
                            f"'{other_term.get('original')}' (작가) ∈ '{title}' "
                            f"(Decoder가 is_author_name으로 확인, 본문에 작가명 존재)",
                            file=sys.stderr,
                        )
                        break
            
            # 🆕 작가가 Decoder에 의해 검증되었으면 본문증거 가드 스킵
            if has_author_verified_by_decoder:
                print(
                    f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵: "
                    f"'{original_term}' → '{title}' (본문 작가명이 해당 작품의 작가로 Decoder 검증됨)",
                    file=sys.stderr,
                )
                continue
            
            # 🆕 4-A) snippet_hints에서 작가명이 확인되고, 그 작가명이 본문에 있으면 본문증거 가드 스킵
            # 핵심: 검색에서 '돌마늘'=작가, '죽깨수'=작품이 확인되었고, 본문에 '돌마늘'이 있으면
            # 작가명 자체가 작품 고유 증거 (LLM decoded_terms에 의존하지 않음)
            if not has_author_evidence and ctx:
                _snippet_hints = getattr(ctx, 'snippet_hints', None)
                if _snippet_hints:
                    # author_hints에서 본문에 있는 작가명 찾기
                    _author_hints = _snippet_hints.get('author_hints', []) or []
                    for _ah in _author_hints:
                        _ah_name = (_ah.get('name') or '').replace(' ', '').lower()
                        if _ah_name and _ah_name in full_text_lower:
                            # 이 작가가 현재 매칭된 작품과 관련있는지:
                            # 검색 결과에서 작가명 + 작품 제목이 같은 결과에 나타나는지 확인
                            for sr in search_results:
                                sr_combined = f"{sr.get('title', '')} {sr.get('content', '')}".replace(' ', '').lower()
                                if _ah_name in sr_combined and title_clean in sr_combined:
                                    has_author_evidence = True
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵: "
                                        f"'{_ah.get('name')}' (snippet_hints 작가) ∈ 본문, 작품='{title}'",
                                        file=sys.stderr,
                                    )
                                    break
                            if has_author_evidence:
                                break
                
                # _resolved_mappings에서 매핑된 약칭의 작가가 본문에 있는 경우
                if not has_author_evidence:
                    _resolved_authors = getattr(ctx, '_resolved_authors', []) or []
                    for _ra in _resolved_authors:
                        _ra_clean = str(_ra).replace(' ', '').lower()
                        if _ra_clean and _ra_clean in full_text_lower:
                            # 이 작가명이 검색에서 현재 작품과 함께 나타나는지 확인
                            for sr in search_results:
                                sr_combined = f"{sr.get('title', '')} {sr.get('content', '')}".replace(' ', '').lower()
                                if _ra_clean in sr_combined and title_clean in sr_combined:
                                    has_author_evidence = True
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵: "
                                        f"'{_ra}' (Gatekeeper 작가) ∈ 본문, 검색에서 작품 연결 확인",
                                        file=sys.stderr,
                                    )
                                    break
                            if has_author_evidence:
                                break
            
            # 🆕 4-A-2) 본문 캐릭터 + 검색에서 해당 작품의 등장인물로 확인 → 강한 증거
            # 핵심: "서무량"이 본문에 있고, 검색 결과에서 "즉사기 들고 무림에 떨어지다" + "서무량"이
            # 함께 나타나면, 캐릭터가 해당 작품에 속한다는 것이 검증됨
            has_character_verified_in_search = False
            original_term = (term.get("original") or "").replace(" ", "").lower()
            # 약칭→정식제목 매핑이 있으면, 약칭으로도 검색 결과 매칭 시도
            _title_aliases = {title_clean}
            if original_term:
                _title_aliases.add(original_term)
            # KNOWN_ABBREVIATIONS 역매핑도 추가
            for _ka_key, _ka_val in KNOWN_ABBREVIATIONS.items():
                if _ka_val.replace(" ", "").lower() == title_clean:
                    _title_aliases.add(_ka_key.lower())
            
            if has_character_evidence and search_results:
                for ch in gk_characters:
                    if not ch or len(ch) < 2:
                        continue
                    ch_clean = ch.lower().replace(" ", "")
                    if ch_clean not in full_text_lower:
                        continue
                    # 이 캐릭터명이 검색 결과에서 매칭된 작품(또는 약칭)과 함께 나타나는지 확인
                    for sr in search_results:
                        sr_text = f"{sr.get('title', '')} {sr.get('content', '')}".lower().replace(" ", "")
                        # 작품 제목이나 약칭과 캐릭터명이 같은 검색 결과에 있으면 검증됨
                        if any(alias in sr_text for alias in _title_aliases) and ch_clean in sr_text:
                            has_character_verified_in_search = True
                            print(
                                f"[{_ts()}][{self.emoji}] 🔒 캐릭터-작품 연결 검증: "
                                f"'{ch}' ∈ '{title}' (검색 결과에서 확인)",
                                file=sys.stderr,
                            )
                            break
                    if has_character_verified_in_search:
                        break
            
            # 🆕 캐릭터가 검색으로 검증되었으면 본문증거 가드 스킵
            if has_character_verified_in_search:
                print(
                    f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵: "
                    f"'{original_term}' → '{title}' (본문 캐릭터가 작품 등장인물로 검색 검증됨)",
                    file=sys.stderr,
                )
                continue
            
            # 4) 검색에서 추출한 작가명이 본문에 있는지
            has_work_specific = any(
                name.lower().replace(" ", "") in full_text_lower
                for etype, name in work_specific_evidence
            )
            
            # 5) 원본 키워드(약어)와 매칭 제목의 형태소 겹침 확인
            original_term = (term.get("original") or "").replace(" ", "").lower()
            
            # 5-1) 검색 결과에 명시적 약칭 증거가 있으면 본문증거 가드 스킵
            import re as _re_alias
            _alias_patterns = [
                _re_alias.compile(rf'약칭[은이가]?\s*{_re_alias.escape(original_term)}'),
                _re_alias.compile(rf'통칭\s*{_re_alias.escape(original_term)}'),
                _re_alias.compile(rf'줄여서\s*{_re_alias.escape(original_term)}'),
                _re_alias.compile(rf'줄임말[은이가]?\s*{_re_alias.escape(original_term)}'),
            ]
            has_explicit_alias_evidence = False
            for sr in search_results:
                sr_combined = f"{sr.get('title', '')} {sr.get('content', '')}".lower()
                if any(p.search(sr_combined) for p in _alias_patterns):
                    has_explicit_alias_evidence = True
                    break
            
            if has_explicit_alias_evidence:
                print(
                    f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵: "
                    f"'{original_term}' → '{title}' (검색 결과에 명시적 약칭 증거 있음)",
                    file=sys.stderr,
                )
                continue
            
            # 원본 키워드가 장르 키워드 패턴인지 확인
            from ..rules import GENRE_KEYWORDS, GENRE_ARCHETYPE_TERMS
            is_genre_keyword = (
                original_term in {g.lower().replace(" ", "") for g in GENRE_KEYWORDS}
                or original_term in {g.lower().replace(" ", "") for g in GENRE_ARCHETYPE_TERMS}
                or any(original_term.startswith(g.lower()[:2]) and len(original_term) <= len(g) + 2
                       for g in GENRE_KEYWORDS if len(g) >= 2)
            )
            
            # 본문에 작품 고유 증거가 하나도 없으면 confidence 하향
            if (not has_character_evidence
                and not has_author_evidence
                and not has_work_specific):
                
                # 추가 조건: 본문이 매우 짧거나 이미지 위주인 경우 더 엄격
                body_len = len(post_body.strip())
                
                if is_genre_keyword:
                    # 장르 키워드 → 작품 매칭은 거의 항상 FP
                    old_conf = confidence
                    best["confidence"] = "none"
                    best["title"] = None
                    result["overall_confidence"] = "none"
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 가드 (장르→작품 차단): "
                        f"'{original_term}' → '{title}' 매칭 차단 "
                        f"(장르 키워드 + 본문에 작품 증거 없음, {old_conf}→none)",
                        file=sys.stderr,
                    )
                    changed = True
                elif body_len < 50:
                    # 매우 짧은 본문 + 증거 없음 → 높은 FP 가능성
                    # 🆕 예외: 제목 약어 매칭 score ≥ 0.85이면 medium 유지
                    # ("즉사무림"→0.90, "빌환"→0.95 등 명확한 축약어는 보호)
                    abbr_score = abbreviation_match_score(original_term, title)
                    if abbr_score >= 0.85:
                        # 약어 매칭이 강력하면 짧은 본문이어도 medium 유지
                        old_conf = confidence
                        if old_conf == "high":
                            best["confidence"] = "medium"
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 가드 (짧은 본문+강한 약어): "
                                f"'{original_term}' → '{title}' confidence 하향 "
                                f"(본문 {body_len}자, abbr_score={abbr_score:.2f}, {old_conf}→medium)",
                                file=sys.stderr,
                            )
                            changed = True
                        # medium 이하는 유지
                    else:
                        old_conf = confidence
                        best["confidence"] = "low"
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 가드 (짧은 본문): "
                            f"'{original_term}' → '{title}' confidence 하향 "
                            f"(본문 {body_len}자 + 작품 증거 없음, {old_conf}→low)",
                            file=sys.stderr,
                        )
                        changed = True
                elif confidence in ("high",):
                    # High confidence인데 본문 증거 없음 → Medium으로 하향
                    # 🆕 예외: 약어 매칭이 강력하면(score≥0.85) 하향 안함
                    abbr_score_high = abbreviation_match_score(original_term, title)
                    if abbr_score_high >= 0.85:
                        print(
                            f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵 (강한 약어): "
                            f"'{original_term}' → '{title}' "
                            f"(abbr_score={abbr_score_high:.2f}≥0.85 → high 유지)",
                            file=sys.stderr,
                        )
                        # high 유지, 변경 없음
                    else:
                        best["confidence"] = "medium"
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 가드 (증거 미약): "
                            f"'{original_term}' → '{title}' confidence 하향 "
                            f"(본문에 작품 고유 정보 없음, abbr_score={abbr_score_high:.2f}, high→medium)",
                            file=sys.stderr,
                        )
                        changed = True
        
        if changed:
            # overall_confidence도 재계산
            all_confs = [
                t.get("best_match", {}).get("confidence", "none")
                for t in decoded_terms
                if t.get("best_match", {}).get("title")
            ]
            if all_confs:
                conf_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
                max_conf = max(all_confs, key=lambda c: conf_rank.get(c, 0))
                result["overall_confidence"] = max_conf
        
        return result
