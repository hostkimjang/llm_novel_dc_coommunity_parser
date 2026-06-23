"""
Stage 2: Decoder Expert - 한글 슬랭 해독 전문가
Korean abbreviation/slang restoration specialist.
"""

from __future__ import annotations

import json
import os
import sys
import time
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from .prompts import (
    DECODER_SYSTEM,
    DECODER_PROMPT,
    build_decoder_system_prompt,
)
from ..prompts.expert_prompts import PLATFORM_ABBREVIATION_MAP
from ..rules import (
    OFFICIAL_PLATFORMS, GENRE_KEYWORDS, GENRE_ARCHETYPE_TERMS,
    PLATFORM_ABBREVIATIONS, PLATFORM_FEATURE_TERMS, ASSOCIATION_PATTERNS,
    is_genre_물_pattern,
)
from .utils import (
    parse_json_with_think_removal, _ts,
    _norm_domain_text, _detect_domain_groups, _has_domain_conflict_for_mapping,
    get_kiwi,
)
import re as _re

_NORMALIZE_ALNUM_KOR_RE = re.compile(r"[^\uac00-\ud7a3A-Za-z0-9]")

# 검색 결과 host 판별용 도메인 집합.
# `OFFICIAL_PLATFORMS`에는 wiki까지 섞여 있어, host 비교용은 플랫폼 도메인만 분리한다.
OFFICIAL_PLATFORM_DOMAINS = tuple(
    site for site in OFFICIAL_PLATFORMS
    if site and site != "namu.wiki"
)


@lru_cache(maxsize=65536)
def _normalize_alnum_kor_cached(text: str) -> str:
    return _NORMALIZE_ALNUM_KOR_RE.sub("", str(text or "")).lower().strip()


# ============================================================
# 알려진 약어 사전 (모듈 수준 상수)
# ============================================================
KNOWN_ABBREVIATIONS = {
    # === 사용자 검증 약칭 ===
    "주전무": "주무시기 전에 무엇을 하셨나요?",
    "히집악": "히어로가 집착하는 악당이 되었다",
}


# ============================================================
# 한글 자모(Jamo) 구조 기반 비작품-약어 판별
# ────────────────────────────────────────────────────────────
#  기존: 초성 비속어를 하드코딩 → 한계 명확
#  개선: 유니코드 음절 분해로 초성 패턴 자동 생성 + 초성 비율 휴리스틱
#        핵심 프레임: "비속어인가?" 가 아니라 "작품 약어일 가능성이 있는가?"
# ============================================================

# 한글 초성 19자 (유니코드 한글 음절 분해 표준 순서)
_CHOSUNG_JAMO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'

# 겹자음(호환 자모) → 단자음 분리 매핑
_COMBINED_JAMO_NORMALIZE: dict[str, str] = {
    'ㄳ': 'ㄱㅅ', 'ㄵ': 'ㄴㅈ', 'ㄶ': 'ㄴㅎ',
    'ㄺ': 'ㄹㄱ', 'ㄻ': 'ㄹㅁ', 'ㄼ': 'ㄹㅂ', 'ㄽ': 'ㄹㅅ',
    'ㄾ': 'ㄹㅌ', 'ㄿ': 'ㄹㅍ', 'ㅀ': 'ㄹㅎ',
    'ㅄ': 'ㅂㅅ', 'ㅆ': 'ㅅㅅ',
}


def _is_jamo_consonant(ch: str) -> bool:
    """단일 문자가 한글 호환 자모 자음인지 (ㄱ~ㅎ, U+3131~U+314E)."""
    return '\u3131' <= ch <= '\u314E'


def _syllable_to_chosung(ch: str) -> str | None:
    """한글 음절 한 글자 → 초성 자모. 음절 아니면 None."""
    cp = ord(ch)
    if 0xAC00 <= cp <= 0xD7A3:
        return _CHOSUNG_JAMO[(cp - 0xAC00) // (21 * 28)]
    return None


def _word_to_chosung(word: str) -> str:
    """'새끼' → 'ㅅㄲ', '씨발' → 'ㅅㅂ' — 유니코드 기반 자동 초성 추출."""
    result: list[str] = []
    for ch in word:
        cho = _syllable_to_chosung(ch)
        if cho:
            result.append(cho)
        elif _is_jamo_consonant(ch):
            result.append(ch)
    return ''.join(result)


def _normalize_jamo(text: str) -> str:
    """겹자음을 단자음으로 분리: 'ㅄ' → 'ㅂㅅ' (패턴 매칭 정규화)."""
    return ''.join(_COMBINED_JAMO_NORMALIZE.get(c, c) for c in text)


def chosung_ratio(text: str) -> float:
    """텍스트 내 한글 자음(초성) 문자 비율. 공백 제외."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if _is_jamo_consonant(c)) / len(chars)


# ── 비속어 원형 리스트 (유지보수: → 여기에 단어만 추가) ──
_PROFANITY_WORDS: list[str] = [
    "새끼", "씨발", "병신", "지랄", "꺼져", "존나",
    "미친", "좆밥", "빡라", "개새끼", "이새끼",
    "씹", "좆", "닥쳐", "꼴받",
]

# 쌍자음 → 단자음 간략화 (사람들이 타이핑 시 간략화: ㅆ→ㅅ, ㄲ→ㄱ 등)
_DOUBLE_TO_SINGLE: dict[str, str] = {
    'ㄲ': 'ㄱ', 'ㄸ': 'ㄷ', 'ㅃ': 'ㅂ', 'ㅆ': 'ㅅ', 'ㅉ': 'ㅈ',
}


def _simplify_double_consonant(text: str) -> str:
    """쌍자음을 단자음으로 간략화: 'ㅆㅂ' → 'ㅅㅂ' (타이핑 변형 대응)."""
    return ''.join(_DOUBLE_TO_SINGLE.get(c, c) for c in text)


# 자동 생성: {"ㅅㄲ": "새끼", "ㅅㅂ": "씨발", "ㅂㅅ": "병신", ...}
# 쌍자음 변형도 자동 추가: "씨발" → exact "ㅆㅂ" + simplified "ㅅㅂ"
_AUTO_CHOSUNG_PROFANITY: dict[str, str] = {}
for _pw in _PROFANITY_WORDS:
    _cho = _word_to_chosung(_pw)
    if len(_cho) >= 2:
        if _cho not in _AUTO_CHOSUNG_PROFANITY:
            _AUTO_CHOSUNG_PROFANITY[_cho] = _pw
        # 쌍자음 간략화 변형도 등록 (ㅆㅂ→ㅅㅂ, ㅅㄲ→ㅅㄱ 등)
        _cho_simple = _simplify_double_consonant(_cho)
        if _cho_simple != _cho and _cho_simple not in _AUTO_CHOSUNG_PROFANITY:
            _AUTO_CHOSUNG_PROFANITY[_cho_simple] = _pw

# 하위 호환: 기존 코드에서 import 하는 경우 대비
CHOSUNG_PROFANITY = _AUTO_CHOSUNG_PROFANITY


def contains_chosung_profanity(text: str) -> tuple[bool, str]:
    """
    텍스트가 작품 약어가 *아닐* 가능성을 구조적으로 판별.

    전략 (하드코딩 사전 → 구조 기반):
      1) 비속어 원형에서 자동 생성된 초성 패턴 서브스트링 매칭
      2) 겹자음 정규화 (ㅄ→ㅂㅅ) 후 재매칭
      3) 초성 비율 ≥50% 이면서 KNOWN_ABBREVIATIONS 미등록 → 비작품 약어 의심
         (웹소설 약어는 음절 조합이므로 자음만으로 구성될 수 없음)

    Returns:
        (발견 여부, 매칭된 비속어 원형 또는 사유 문자열)
    """
    text_clean = text.strip().replace(" ", "")
    if not text_clean:
        return False, ""

    # KNOWN_ABBREVIATIONS 화이트리스트 통과
    if text_clean in KNOWN_ABBREVIATIONS:
        return False, ""

    # 겹자음 정규화 (ㅄ→ㅂㅅ 등)
    text_normalized = _normalize_jamo(text_clean)

    # 1) 자동 생성 패턴 매칭 (longest-match-first)
    for pattern, expansion in sorted(
        _AUTO_CHOSUNG_PROFANITY.items(), key=lambda x: -len(x[0])
    ):
        if pattern in text_normalized:
            return True, expansion

    # 2) 초성 비율 휴리스틱: 자음이 절반 이상 → 비작품 약어
    #    웹소설 약어는 "전독시", "나혼렙" 처럼 음절로 구성되므로
    #    초성만 나열된 형태('ㅂㄹㅋ', 'ㅈㄹㅁ')는 작품명이 아님
    if len(text_normalized) >= 2:
        r = chosung_ratio(text_normalized)
        if r >= 0.5:
            return True, f"초성비율 {r:.0%} (비작품 약어 의심)"

    return False, ""


# ============================================================
# 약어-제목 매칭 스코어 (LLM 불필요, 코드 레벨 검증)
# ============================================================

def _strip_korean_particles(text: str) -> str:
    """한국어 조사(은/는/이/가/을/를/도/와/과/에/에서/으로/로 등)를 말미에서 제거."""
    import re as _re_p
    # 긴 조사부터 매칭 (에서, 으로 먼저 → 은, 는, 이 등 나중)
    return _re_p.sub(
        r'(에서|으로|이랑|에게|한테|부터|까지|처럼|만큼|보다|라는'
        r'|는|은|이|가|을|를|의|에|도|와|과|로|만|조차|마저|밖에)$',
        '', text,
    )


_KEEP_JAMO_TEXT_RE = re.compile(r"[^\u3131-\u314e\uac00-\ud7a3A-Za-z0-9]")
_JAMO_TAIL_FOLLOWERS = {"은", "는", "이", "가", "을", "를", "도", "만", "의", "에", "와", "과", "로"}


def _normalize_text_keep_jamo(text: str) -> str:
    return _KEEP_JAMO_TEXT_RE.sub("", str(text or "")).lower().strip()


def _is_trailing_jamo_abbreviation(text: str) -> bool:
    tok = _normalize_text_keep_jamo(text)
    if len(tok) < 3:
        return False
    return any("\uac00" <= ch <= "\ud7a3" for ch in tok[:-1]) and ("\u3131" <= tok[-1] <= "\u314e")


def _leading_jamo_title_direct_score(abbr: str, candidate_title: str) -> float:
    abbr_norm = _normalize_text_keep_jamo(abbr)
    title_norm = _normalize_text_keep_jamo(candidate_title)
    if not (_is_trailing_jamo_abbreviation(abbr_norm) and title_norm.startswith(abbr_norm)):
        return 0.0
    if len(title_norm) <= len(abbr_norm):
        return 0.0
    next_char = title_norm[len(abbr_norm)]
    if next_char in _JAMO_TAIL_FOLLOWERS:
        return 0.98
    return 0.0


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

    # 🆕 조사 제거: '망겜성은' → '망겜성', '해리포터가' → '해리포터' 등
    # 조사 포함/제거 양쪽을 모두 시도해 최고 점수를 반환한다.
    abbr_stripped = _strip_korean_particles(abbr.strip())
    if abbr_stripped != abbr.strip() and abbr_stripped:
        score_with_particle = _abbreviation_match_score_inner(abbr.strip(), candidate_title)
        score_without_particle = _abbreviation_match_score_inner(abbr_stripped, candidate_title)
        return max(score_with_particle, score_without_particle)

    return _abbreviation_match_score_inner(abbr.strip(), candidate_title)


def _abbreviation_match_score_inner(abbr_clean: str, candidate_title: str) -> float:
    """abbreviation_match_score 의 내부 구현."""
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

    best_score = max(scores) if scores else 0.0

    # 🛡️ 도메인 충돌 가드:
    # 약어의 세계관 신호와 후보 제목의 세계관 신호가 정면 충돌하면
    # 강한 점수 캡을 적용해 후속 단계에서 탈락하도록 유도한다.
    if _has_domain_conflict_for_mapping(abbr_clean, title_clean):
        best_score = min(best_score, 0.20)

    return best_score


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


# 도메인 충돌 감지 유틸: utils.py 에서 import (_norm_domain_text, _detect_domain_groups, _has_domain_conflict_for_mapping)


def _abbr_alignment_guard_score(abbr: str, title: str) -> float:
    """
    교정 가드용 정합성 점수.
    abbreviation_match_score는 약어==제목에서 0.0(자기참조) 처리하므로,
    교정/비교 가드 문맥에서는 동일 문자열을 높은 정합성으로 취급한다.
    """
    a_norm = _norm_domain_text(abbr)
    t_norm = _norm_domain_text(title)
    if a_norm and t_norm:
        if a_norm == t_norm:
            return 1.0
        if a_norm in t_norm:
            return 0.85
    return abbreviation_match_score(abbr, title)


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
        # Kiwi 형태소 분석기 (프로세스 전역 싱글톤)
        self._kiwi = get_kiwi()

    @staticmethod
    def _is_novel_platform_url(url: str) -> bool:
        if not url:
            return False
        url_l = str(url).lower()
        return any(site in url_l for site in OFFICIAL_PLATFORMS)

    @staticmethod
    def _is_novel_detail_url(url: str) -> bool:
        """공식 플랫폼 URL 중 작품 상세 URL만 허용한다."""
        if not isinstance(url, str) or not url:
            return False
        try:
            from urllib.parse import urlparse
            import re

            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()
            query = (parsed.query or "").lower()
        except Exception:
            return False

        if any(tok in path for tok in ("/arena/", "/community/", "/board/", "/forum/", "/review/", "/reviews/")):
            return False
        if any(tok in path for tok in ("/search", "/author", "/writers", "/ranking", "/best", "/genre", "/tag", "/list")):
            return False
        if any(tok in query for tok in ("search=", "q=", "query=", "keyword=", "writer=", "author=", "tag=", "genre=", "page=")):
            return False

        if "novelpia.com" in host and re.search(r"/novel/\d+", path):
            return True
        if "series.naver.com" in host and "/novel/detail.series" in path and "productno=" in query:
            return True
        if "ridibooks.com" in host and re.search(r"^/books/\d+", path):
            return True
        if "munpia.com" in host and (("action=view" in query and "id=" in query) or re.search(r"/novel/\d+", path)):
            return True
        if "joara.com" in host and ("/book/" in path or "book_no=" in query or "bookcode=" in query):
            return True
        if ("kakao.page" in host or "page.kakao.com" in host) and "/content/" in path:
            return True
        return False

    def _find_embedded_stable_alias(
        self,
        original_term: str,
        title: str,
        possible_characters: Optional[List[str]] = None,
    ) -> str:
        """
        긴 제목 표면 안에 작품 약칭이 묻혀 있는 경우 핵심 약칭을 복원한다.
        예: '즉사무림은영이너무불쌍해' -> '즉사무림'
            '즉사무림이유백미래가벌써보이네' -> '즉사무림'
        """
        original_norm = _normalize_alnum_kor_cached(original_term)
        title_norm = _normalize_alnum_kor_cached(title)
        if not original_norm or not title_norm or original_norm == title_norm:
            return ""

        char_norms = [
            _normalize_alnum_kor_cached(ch)
            for ch in (possible_characters or [])
            if isinstance(ch, str) and str(ch).strip()
        ]
        char_norms = [ch for ch in char_norms if 2 <= len(ch) <= 4]

        best_alias = ""
        best_score = 0.0
        for ch in char_norms:
            idx = original_norm.find(ch)
            if idx >= 3:
                prefix = original_norm[:idx].strip()
                score = max(
                    abbreviation_match_score(prefix, title),
                    _leading_jamo_title_direct_score(prefix, title),
                )
                if score >= 0.75 and score > best_score:
                    best_alias = prefix
                    best_score = score
        for cut in range(max(2, len(original_norm) - 10), len(original_norm) - 1):
            prefix = original_norm[:cut].strip()
            suffix = original_norm[cut:].strip()
            if len(prefix) < 3 or len(suffix) < 2:
                continue
            has_bound_character = any(ch and ch in suffix for ch in char_norms)
            if char_norms and (not has_bound_character):
                continue
            if (not char_norms) and len(suffix) > 10:
                continue
            score = max(
                abbreviation_match_score(prefix, title),
                _leading_jamo_title_direct_score(prefix, title),
            )
            if score >= 0.75 and score > best_score:
                best_alias = prefix
                best_score = score
        return best_alias
    
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
            # 🆕 괄호/구두점을 먼저 제거하여 "아생갤)" → "아생갤" 로 복원
            # 커뮤니티에서 "갤)" "갤]" 형식으로 약칭 뒤에 닫는 괄호를 붙이는 패턴이 흔함
            import re as _re_pt
            pt_stripped = _re_pt.sub(r'[)\]>!?.,;:\-~]+$', '', pt_clean)  # 후행 구두점 제거
            pt_stripped = _re_pt.sub(r'^[(\[<\-~]+', '', pt_stripped)      # 선행 구두점 제거
            pt_stripped = pt_stripped.strip()
            if pt_stripped and pt_stripped != pt_clean:
                pt_clean = pt_stripped
            # 3글자 미만 스킵
            if len(pt_clean) < 3:
                continue
            # 공백/탭 포함 → n-gram 쓰레기 → key_terms에는 넣지 않음
            # 🔧 괄호는 위에서 이미 제거했으므로 여기서는 공백/탭만 체크
            if any(c in pt_clean for c in ' \t'):
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

        # 🆕 P1-2: 초성 비속어 포함 term 필터링
        # "이ㅅㄲ" = "이 새끼" 같은 욕설을 작품 약어로 오해석하는 것을 방지
        _filtered_tagged = []
        for _tt, _tp in tagged_terms:
            _has_prof, _prof_exp = contains_chosung_profanity(_tt)
            if _has_prof:
                print(
                    f"[{_ts()}][{self.emoji}] 🚫 key_term 제외(초성 비속어): "
                    f"'{_tt}' → '{_prof_exp}'",
                    file=sys.stderr,
                )
                continue
            _filtered_tagged.append((_tt, _tp))
        tagged_terms = _filtered_tagged
        
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
        
        # ── 검색 결과 콘텐츠 트리밍 후 전달 ──
        # BM25 트리밍 + 항목당/전체 크기 제한으로 토큰 오버플로 방지
        from ..search.content_trim import trim_search_results_content
        
        _gk_json = json.dumps(gatekeeper_result, ensure_ascii=False, indent=2)
        _dict_json = json.dumps(slang_dictionary, ensure_ascii=False, indent=2)
        
        # 검색 결과 content 트리밍 (항목당 6K, 전체 40K 제한)
        _sr_for_prompt = trim_search_results_content(
            search_results,
            max_per_item=6000,
            max_total=40000,
        )
        _sr_json = json.dumps(_sr_for_prompt, ensure_ascii=False, indent=2)
        print(f"[{_ts()}][{self.emoji}] 검색 결과 트리밍 전달: {len(search_results)}건, "
              f"sr_json={len(_sr_json):,}자, gk={len(_gk_json):,}자, dict={len(_dict_json):,}자", file=sys.stderr)
        
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
                user_prompt += "🔑 '[한글1~5자]물' 패턴(일상물, 힐링물, 좀비물, 먹방물, 집착물 등)은 모두 장르 카테고리이며 소설 제목이 아닙니다.\n"
                user_prompt += "제목이나 본문의 주제어가 장르·트로프 관련 일반 개념어인 경우,\n"
                user_prompt += "검색에서 우연히 비슷한 키워드의 소설이 발견되더라도 그것이 이 포스트의 실제 주제인지 엄격히 확인하세요.\n"
                user_prompt += "판단 기준: 본문/댓글에 해당 소설의 고유 정보(작가명, 플랫폼, 회차, 캐릭터 고유명, 줄거리)가 있는가?\n"
                user_prompt += "고유 정보가 없으면 → best_match.title=null, confidence=none으로 판정하세요.\n"
            else:
                user_prompt += "🚨 이 포스트는 소설/웹소설과 무관한 밈/유머/일상 포스트일 가능성이 높습니다.\n"
                user_prompt += "핵심 키워드가 커뮤니티 자체 은어(예: 장붕=장르소설갤 유저, 겜붕=게임갤 유저, 완장=갤러리 관리자)일 수 있습니다.\n"
                user_prompt += "검색 결과에서 해당 단어가 소설 '캐릭터 이름'으로 나오더라도, 그것이 이 포스트의 맥락과 일치하는지 엄격히 확인하세요.\n"
                user_prompt += "본문/댓글에 작품 줄거리·작가명·플랫폼 URL이 전혀 없으면 → best_match.title=null, confidence=none으로 판정하세요.\n"
        
        # 🆕 Phase 11j: Gatekeeper 장르토론 감지 플래그 → Decoder 경고 주입
        # Discourse Warning이 없더라도, Gatekeeper가 장르 토론 패턴을 감지했으면 경고
        _gk_ctx_clues = {}
        if ctx:
            try:
                from ..models import ExpertType
                _gk_out = ctx.get_expert_output(ExpertType.GATEKEEPER) if hasattr(ctx, 'get_expert_output') else {}
            except Exception:
                _gk_out = {}
            _gk_ctx_clues = (_gk_out or {}).get("context_clues", {})
        
        _gk_genre_detected = _gk_ctx_clues.get("genre_discussion_detected", False)
        _gk_opinion_prefix = _gk_ctx_clues.get("dc_opinion_prefix", "")
        _gk_recommendation = _gk_ctx_clues.get("is_recommendation_request", False)
        _gk_comparison = _gk_ctx_clues.get("is_comparison_post", False)
        _gk_negation = _gk_ctx_clues.get("genre_negation_detected", False)
        _gk_multi_order = _gk_ctx_clues.get("multi_work_order_detected", False)
        _gk_order_hits = _gk_ctx_clues.get("order_keywords_found", [])
        _gk_arrow_chain = _gk_ctx_clues.get("has_arrow_chain", False)
        _gk_author_focus = _gk_ctx_clues.get("has_author_focus", False)
        _gk_title_body_cont = bool(_gk_ctx_clues.get("title_as_body_continuation"))
        _gk_title_body_joined = str(_gk_ctx_clues.get("title_body_joined_text") or "").strip()
        _gk_comment_secondary = list(dict.fromkeys(
            str(t).strip()
            for t in (_gk_ctx_clues.get("comment_title_candidates") or [])
            if isinstance(t, str) and t.strip()
        ))
        
        _gk_flags = _gk_ctx_clues.get("genre_discussion_flags", [])
        if _gk_flags and not getattr(ctx, 'discourse_warning', None):
            # Discourse Warning 없이도 Gatekeeper가 장르 토론을 감지한 경우
            user_prompt += "\n\n=== ⚠️ GATEKEEPER 장르 토론 감지 ===\n"
            user_prompt += f"감지된 패턴: {', '.join(_gk_flags)}\n"
            if _gk_genre_detected:
                user_prompt += "🚨 제목에 장르 아키타입 용어 + 장르 토론 지시어가 함께 감지됨.\n"
                user_prompt += "이 게시글은 장르/트로프 일반론일 가능성이 매우 높습니다.\n"
            if _gk_opinion_prefix:
                user_prompt += f"🚨 '{_gk_opinion_prefix}))'은 DC 의견 접두사이지 작품명이 아닙니다.\n"
                user_prompt += f"'{_gk_opinion_prefix}'을 작품 약칭으로 매칭하지 마세요.\n"
            if _gk_recommendation:
                user_prompt += "🚨 추천 요청 게시글입니다. 댓글의 URL/추천은 주제가 아닙니다.\n"
            if _gk_comparison:
                _comp_target = _gk_ctx_clues.get('comparison_target', '')
                _comp_type = _gk_ctx_clues.get('comparison_type', '')
                user_prompt += f"🚨 비교 패턴 감지: '{_comp_target} {_comp_type}'\n"
                user_prompt += "비교 대상(예: 'X 느낌이라', 'X 하위호환')의 X는 주제가 아닙니다.\n"
                user_prompt += "비교 대상 작품을 official_title로 올리지 마세요.\n"
                user_prompt += "주제 작품을 해독할 수 없으면 → best_match.title=null, confidence=none\n"
            if _gk_negation:
                user_prompt += "🚨 본문에 '본적없다/못봤다' 표현 감지. 소재 토론이지 작품 리뷰가 아닙니다.\n"
            user_prompt += "고유 정보가 없으면 → best_match.title=null, confidence=none으로 판정하세요.\n"

        if _gk_comment_secondary:
            user_prompt += "\n\n=== 🧭 COMMENT SECONDARY EXAMPLES ===\n"
            user_prompt += f"댓글의 작품 예시 후보: {', '.join(_gk_comment_secondary[:5])}\n"
            user_prompt += (
                "이 제목들은 장르 일반론/추천/비교 문맥의 보조 예시일 수 있습니다. "
                "본문 주제가 특정 작품으로 직접 잠기지 않으면 best_match.title로 승격하지 말고 "
                "secondary example/reference로만 취급하세요.\n"
            )

        # 🆕 숫자 작가 닉네임 경고
        _gk_numeric_author = _gk_ctx_clues.get("is_numeric_author_post", False)
        if _gk_numeric_author:
            _num_id = _gk_ctx_clues.get("numeric_author_id", "")
            _num_suffix = _gk_ctx_clues.get("numeric_author_suffix", "")
            user_prompt += f"\n\n=== 🔢 NUMERIC AUTHOR NICKNAME ===\n"
            user_prompt += f"제목의 '{_num_id}{_num_suffix}'에서 '{_num_id}'는 작가 닉네임입니다.\n"
            user_prompt += f"DC 장르소설 갤러리에서는 작가를 숫자로 부르는 관행이 있습니다.\n"
            user_prompt += f"'{_num_id}{_num_suffix}' = '{_num_id}' 작가의 {_num_suffix}\n"
            user_prompt += "본문에 비교 참조(예: 'X 느낌이라')가 있으면, X는 비교 대상이지 주제 작품이 아닙니다.\n"
            user_prompt += "주제는 '{0}' 작가의 작품이며, 작품 제목을 특정할 수 없으면 title=null로 두세요.\n".format(_num_id)

        # 🆕 제목+본문 연속문 힌트: 커뮤니티 문체에서 제목이 본문 1행 역할을 하는 경우
        if _gk_title_body_cont and _gk_title_body_joined:
            user_prompt += "\n\n=== 🧩 TITLE-BODY CONTINUATION HINT ===\n"
            user_prompt += "이 포스트는 제목이 본문 첫 문장의 일부(리드 문장)일 가능성이 높습니다.\n"
            user_prompt += "제목과 본문 첫 줄을 분리 해석하지 말고, 하나의 연속 발화로 먼저 해석하세요.\n"
            user_prompt += f"- joined_text: {_gk_title_body_joined}\n"
            user_prompt += "규칙: 작품 앵커/감상 문맥 판단 시 joined_text를 우선 증거로 사용하세요.\n"
        
        # 🆕 다작/순서 질문 경고: 단일 제목 강제 고정 방지
        if _gk_multi_order:
            user_prompt += "\n\n=== ⚠️ GATEKEEPER 다작/순서질문 감지 ===\n"
            user_prompt += f"order_keywords={_gk_order_hits}, arrow_chain={_gk_arrow_chain}, author_focus={_gk_author_focus}\n"
            user_prompt += "🚨 이 포스트는 작가 전작/작품군 소비 순서를 묻는 담화일 수 있습니다.\n"
            user_prompt += "단일 작품명으로 강제 확정하지 말고, 후보가 복수면 unresolved_terms에 순서질문 맥락을 기록하세요.\n"
            user_prompt += "원문이 특정 작품 리뷰가 아니라면 best_match.title=null, overall_confidence=low/none을 우선 검토하세요.\n"

        # 🆕 BUG-4: 복합 축약어 분리 힌트
        # "작품약어캐릭터명" = 작품약어+캐릭터명 결합 — LLM에게 분리 시도 안내
        user_prompt += "\n\n=== COMPOUND TERM HINT ===\n"
        user_prompt += "키워드가 4음절 이상이고 공백이 없으면, [작품 약어 + 캐릭터/작가명]이 결합된 형태일 수 있습니다.\n"
        user_prompt += "예: '작품약어캐릭터명' → '작품약어'(작품 약어) + '캐릭터명'(캐릭터명)\n"
        user_prompt += "예: '짧은약칭주인공이름' → '짧은약칭'(작품 약어) + '주인공이름'(캐릭터명)\n"
        user_prompt += "이 경우 morphemes를 ['작품약어', '캐릭터명'] 형태로 분리하여 보고하세요.\n"
        user_prompt += "'갤' 접미사는 DC인사이드 갤러리 약어일 수 있습니다 (예: 판타지갤 → 판타지 갤러리).\n"
        user_prompt += "단, 일부 작품은 제목 자체에 '갤러리'가 포함될 수 있으므로 커뮤니티 용어로 단정하지 마세요.\n"
        user_prompt += "커뮤니티 문장형 헤드라인(예: 지시어+연도+평가문, '...장갤픽임' 같은 표현)은 작품명이 아닙니다.\n"
        user_prompt += "그런 문장만 근거일 때는 best_match.title=null로 두고 verification_search를 요청하세요.\n"
        user_prompt += "⚠️ '웹소설로 꿈꾸는 세상!' 같은 플랫폼 슬로건은 작품명이 아닙니다. 해당 표현만 검색 증거로 있으면 title=null로 두세요.\n"

        # 🆕 밈 합성 약어 분해 힌트
        user_prompt += "\n=== 🏷️ MIM COMPOUND ABBREVIATION HINT (밈 합성 약어) ===\n"
        user_prompt += "장르소설 갤러리에서는 여러 작품의 약칭 첫 글자를 합쳐서 밈으로 부릅니다.\n"
        user_prompt += "예: '모리엘루깐' = 모닝글로리 + 리버스 + 엘루깐 + 루깐 (각각 다른 작품)\n"
        user_prompt += "\n"
        user_prompt += "🚨 핵심 규칙: 합성 밈 약어 전체(모리엘루깐)는 작품 묶음이지만,\n"
        user_prompt += "   각 구성 요소(예: '엘루깐')는 실제 존재하는 개별 작품의 커뮤니티 통용 약칭입니다.\n"
        user_prompt += "   게시글 제목에 구성 요소 중 하나가 사용되면 → 해당 개별 작품에 대한 논의입니다.\n"
        user_prompt += "\n"
        user_prompt += "판별 방법:\n"
        user_prompt += "1. 포스트 제목의 키워드가 밈 합성어의 일부 구성 요소와 일치하는지 확인\n"
        user_prompt += "2. 일치하면 → 그 구성 요소가 가리키는 개별 작품을 best_match.title에 기록\n"
        user_prompt += "3. 본문에 캐릭터 고유명(예: '엘황')이 언급되면 → 작품 토론이 맞음\n"
        user_prompt += "4. 검색 결과에서 '~를 일컫는 약어이자 밈', '~를 묶어 부르는 약칭' 등이 발견되면\n"
        user_prompt += "   각 구성 요소를 abbreviation_mappings에 개별적으로 기록하세요\n"
        user_prompt += "\n"
        user_prompt += "⚠️ 커뮤니티 약칭 → 공식 제목 매핑을 못 찾더라도:\n"
        user_prompt += "   - 커뮤니티 통용 약칭 자체를 best_match.title로 보고하세요 (confidence=low)\n"
        user_prompt += "   - '밈이라 작품이 아님' 또는 '공식 제목 확인 불가'라고 단정하지 마세요\n"
        user_prompt += "   - 커뮤니티에서 독립적으로 작품을 가리키는 약칭은 유효한 작품 식별자입니다\n"
        
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
                        src = h.get("source", "")
                        conf = h.get("confidence", "")
                        extra = ""
                        if src == "author_bridge":
                            extra = f" [🌉 작가 브릿지, 신뢰도: {conf}]"
                        elif conf:
                            extra = f" (신뢰도: {conf})"
                        user_prompt += f"  - '{h.get('abbrev', '')}' → '{h.get('full', '')}'{extra}\n"
                    user_prompt += "\n"
                
                # 🌉 작가 브릿지 정보 (삼단논법으로 추론된 작가 연결)
                _bridge_hints = hints.get("author_bridge_evidence") or []
                if not _bridge_hints and ctx and hasattr(ctx, 'snippet_hints'):
                    _bridge_hints = (ctx.snippet_hints or {}).get("author_bridge_evidence", [])
                if _bridge_hints:
                    user_prompt += "🌉 작가 브릿지 (삼단논법 추론):\n"
                    for bh in _bridge_hints[:3]:
                        user_prompt += f"  - {bh.get('evidence', '')}\n"
                    user_prompt += "⚠️ 위 브릿지는 검색 결과 자동 추론이므로, 원문 맥락과 교차 확인하세요.\n\n"
                
                user_prompt += "⚠️ 위 힌트는 코드 자동 추출이므로 오류가 있을 수 있습니다. 검색 결과 원문과 교차 확인하세요.\n"
        
        # 🔄 증거 기반 맥락 추론 (Evidence-Based Context Reasoning)
        # 검색으로 발견한 사실(약칭→제목, 인물=캐릭터/작가)을 토대로
        # 본문/댓글을 다시 읽고, 글의 실제 맥락을 LLM이 자유롭게 추론하도록 유도
        _do_reasoning = False
        _resolved_mappings = []
        _resolved_mapping_entries = []
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
            # 🔥 KNOWN_ABBREVIATIONS를 최우선으로 추가 (가장 신뢰할 수 있는 매핑)
            import re as _re_reinterpret
            _norm_local = lambda s: _re_reinterpret.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', str(s or '')).lower()
            _known_abbrev_norm_map = {
                _norm_local(k): _norm_local(v)
                for k, v in KNOWN_ABBREVIATIONS.items()
            }
            _official_title_norms = set()
            try:
                _official_title_norms = {
                    _norm_local(o.get("title", ""))
                    for o in (self._extract_official_titles_from_search(ctx) or [])
                    if isinstance(o, dict) and o.get("title")
                }
            except Exception:
                _official_title_norms = set()
            for term_k in (_gk_titles + [_post_title_r]):
                if isinstance(term_k, str):
                    t_clean = _re_reinterpret.sub(r'[^\uac00-\ud7a3]', '', term_k)
                    if t_clean and t_clean in KNOWN_ABBREVIATIONS:
                        full_title = KNOWN_ABBREVIATIONS[t_clean]
                        if not any(
                            _re.get("abbrev") == t_clean and _re.get("full") == full_title
                            for _re in _resolved_mapping_entries
                        ):
                            _resolved_mapping_entries.insert(0, {
                                "abbrev": t_clean,
                                "full": full_title,
                                "source": "known_abbreviation",
                            })
            
            # snippet_hints 매핑 추가 (junk + 약칭 정합성 필터링 적용)
            if hasattr(ctx, 'snippet_hints') and ctx.snippet_hints:
                _JUNK_FULL_INDICATORS = (
                    '갤러리', '마이너', '디시인사이드', '에펨코리아',
                    '커뮤니티', ' - ', '죽일 줄', '어떻게 될지',
                    '재밌', '참신', 'ㅈㄴ', 'ㄹㅇ',
                    '개존잼', '재미떠',
                )
                for ah in ctx.snippet_hints.get('abbreviation_hints', []):
                    abbrev = ah.get('abbrev', '')
                    full = ah.get('full', '')
                    if not (abbrev and full):
                        continue
                    # junk 필터: DC 게시글 제목이 full로 잡힌 경우 제거
                    if len(full) > 20 or any(ind in full for ind in _JUNK_FULL_INDICATORS):
                        continue
                    # 자기참조 필터: abbrev와 full이 거의 같은 경우
                    _a_norm = _re_reinterpret.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', abbrev).lower()
                    _f_norm = _re_reinterpret.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', full).lower()
                    if _a_norm == _f_norm:
                        continue
                    # 핵심 필터: 약칭-정식제목 정합성이 매우 낮은 매핑은 주입 금지
                    # (예: 즉사무림 -> 즉사기 들고 게임 속으로)
                    _abbr_score = abbreviation_match_score(abbrev, full)
                    _source = str(ah.get("source", "") or "")
                    _source_official = _source in {"url_fetch_platform", "platform_title", "author_bridge", "llm_snippet"}
                    _known_match = bool(_a_norm and _f_norm and _known_abbrev_norm_map.get(_a_norm) == _f_norm)
                    _official_match = bool(_f_norm and _f_norm in _official_title_norms)
                    _allow_low_score = (_source_official or _official_match) and _abbr_score >= 0.25
                    if not (_known_match or _abbr_score >= 0.45 or _allow_low_score):
                        print(
                            f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 스킵(약칭 정합성 낮음): "
                            f"'{abbrev}' → '{full}' (score={_abbr_score:.2f}, source={_source or 'unknown'})",
                            file=sys.stderr,
                        )
                        continue
                    # 🛡️ 짧은 약칭 가드: 2자 이하 약칭은 일반명사일 확률이 높으므로
                    # KNOWN_ABBREVIATIONS 확정쌍이 아니면 정합성 기준을 대폭 강화한다.
                    # (예: '초식' → '5000살 먹은 초식 드래곤' 같은 우연 매칭 방지)
                    if len(_a_norm) <= 2 and not _known_match:
                        _short_min = 0.70 if not _official_match else 0.55
                        if _abbr_score < _short_min:
                            print(
                                f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 스킵(짧은약칭 가드): "
                                f"'{abbrev}' → '{full}' (len={len(_a_norm)}, "
                                f"score={_abbr_score:.2f} < {_short_min:.2f})",
                                file=sys.stderr,
                            )
                            continue
                    if not any(
                        _re.get("abbrev") == abbrev and _re.get("full") == full
                        for _re in _resolved_mapping_entries
                    ):
                        _resolved_mapping_entries.append({
                            "abbrev": abbrev,
                            "full": full,
                            "source": _source or "snippet_hint",
                        })

            if _resolved_mapping_entries:
                try:
                    _resolved_mappings = self._refine_resolved_mappings(ctx, _resolved_mapping_entries)
                except Exception as _mapping_refine_err:
                    print(
                        f"[{_ts()}][{self.emoji}] ⚠️ resolved_mapping refinement 실패: "
                        f"{_mapping_refine_err}",
                        file=sys.stderr,
                    )
                    _resolved_mappings = [
                        (str(_re.get("abbrev") or "").strip(), str(_re.get("full") or "").strip())
                        for _re in _resolved_mapping_entries
                        if isinstance(_re, dict)
                        and str(_re.get("abbrev") or "").strip()
                        and str(_re.get("full") or "").strip()
                    ]
            
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
            _comment_context_lines = [
                str(line)
                for line in (post_data.get("comment_context_lines") or [])[:10]
                if str(line).strip()
            ]
            _comment_dialogue_lines = [
                str(line)
                for line in (post_data.get("comment_dialogue_context_lines") or [])[:10]
                if str(line).strip()
            ]
            
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
            if _comment_context_lines:
                user_prompt += (
                    "  댓글 작성자/대화 맥락: "
                    + " / ".join(_comment_context_lines)
                    + " (role=post_author는 본문 작성자의 댓글)\n"
                )
            if _comment_dialogue_lines:
                user_prompt += (
                    "  댓글 발화 재구성: "
                    + " / ".join(_comment_dialogue_lines)
                    + " (speaker/author/ip는 대화 흐름 추적용이며 작품명 증거가 아님)\n"
                )
            
            # 자유 추론 지시
            user_prompt += "\n🧠 **추론 과제 (매우 중요!):**\n"
            user_prompt += "위 사실들을 원문에 대입하여 다음을 단계별로 추론하세요:\n\n"
            user_prompt += "**Pre-Step — 제목+본문 연결 읽기 (MANDATORY):**\n"
            user_prompt += "커뮤니티 게시글의 제목과 본문은 하나의 연속된 발화입니다.\n"
            user_prompt += "제목에는 핵심 주제(작품명/캐릭터명/작가명), 본문에는 관련 감정/의견/내용이 담깁니다.\n"
            user_prompt += "예시: 제목='작품약어 주인공이 너무 불쌍해' + 본문='겨우 찾은 가족을 위해 죽는다니'\n"
            user_prompt += "→ '작품약어'라는 작품의 '주인공' 캐릭터에 대한 감상으로 읽을 수 있습니다.\n"
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
            user_prompt += "- **팬 요청/창작 요구인가?** (\"~같은거 써주셈\", \"X풍 써줘\"는 비교 참조용 언급이지, 해당 작품이 본문 주제인 것이 아님)\n"
            user_prompt += "- **비교 참조인가?** (\"A처럼 재밌는 거\", \"A랑 비슷한 느낌\", \"A 느낌이라\"는 A가 비교 대상이지, 글의 주제가 아님)\n"
            user_prompt += "  → 비교 대상 작품을 best_match.title에 올리지 마세요. 주제 작품이 불명이면 title=null\n"
            user_prompt += "- 본문+댓글의 전체 분위기에서 어떤 해석이 가장 자연스러운가?\n\n"
            user_prompt += "**Step 3 — 인물 역할 판정:**\n"
            user_prompt += "검색 결과를 참고하여 인물명의 역할을 확인하라.\n"
            user_prompt += "- 등장인물로 확인 → anchor_type='character_mention', is_grounded=true\n"
            user_prompt += "- 작가로 확인 → is_author_name=true, author_info 기록\n"
            user_prompt += "- 작가명이 본문에 있고 + 해당 작품 약칭도 있으면 → is_grounded=true (작품 식별 증거)\n\n"
            user_prompt += "**Step 4 — 결론:**\n"
            user_prompt += "추론 결과를 notes 필드에 '치환 읽기 → 맥락 추론 → 결론' 형태로 간결하게 기록하세요.\n"
        
        # 🌐 Fetched Page Info: URL 페칭으로 얻은 구조적 정보
        if ctx and hasattr(ctx, 'fetched_page_info') and ctx.fetched_page_info:
            # Phase 34: 삭제된 소설 제목 경고
            _dead_titles_list = getattr(ctx, '_deleted_titles_list', []) if ctx else []
            user_prompt += "\n\n=== 🌐 FETCHED PAGE INFO (crawl4ai 크롤링 결과) ===\n"
            user_prompt += (
                "아래는 crawl4ai로 실제 웹 페이지를 크롤링하여 얻은 본문 정보입니다.\n"
                "각 페이지의 전체 내용을 읽고, 이 페이지가 무엇인지(소설 작품 페이지인지, "
                "독자 커뮤니티 게시글인지, 위키 문서인지) 직접 판단하세요.\n\n"
                "📌 핵심 판단 규칙:\n"
                "1. page_type='community_post' → 독자들이 쓴 커뮤니티 게시글. "
                "이 페이지의 제목(page_title)은 게시글 제목이지 소설 제목이 아닙니다.\n"
                "   본문 내용을 읽고 실제로 어떤 소설을 논하고 있는지 파악하세요.\n"
                "2. page_type='novel_page' → 소설 플랫폼의 작품 페이지. "
                "title이 정식 소설 제목이며 가장 신뢰할 수 있습니다.\n"
                "3. page_type='wiki' → 위키 문서. 약칭, 등장인물, 줄거리 등 참고 가능.\n"
                "4. page_type='unknown'/'blog' → 본문 내용을 직접 읽어 맥락을 판단하세요.\n\n"
            )
            if _dead_titles_list:
                user_prompt += (
                    "⛔ 삭제/미존재 확인된 작품 목록 (실제 크롤링 결과 사라진 작품):\n"
                )
                for _dt in _dead_titles_list:
                    user_prompt += f"  - '{_dt}' (삭제됨 — 이 제목을 정답으로 선택하지 마세요)\n"
                user_prompt += (
                    "위 삭제된 작품과 유사한 제목의 다른 활성 작품을 우선 선택하세요.\n\n"
                )
            for fi in ctx.fetched_page_info[:5]:
                url = fi.get("url", "")
                structured = fi.get("structured_info", {})
                preview = fi.get("text_preview", "")
                _pt = structured.get("page_type", "unknown")
                user_prompt += f"--- 크롤링 페이지 ---\n"
                user_prompt += f"URL: {url}\n"
                user_prompt += f"  [page_type: {_pt}]\n"
                # Phase 34: content_status 표시 (삭제/미존재 작품 경고)
                _cs = structured.get("content_status", "active")
                if _cs in ("deleted", "unavailable"):
                    user_prompt += (
                        f"  ⛔ content_status: {_cs} — 이 페이지의 작품은 삭제/비공개/미존재 상태입니다.\n"
                        f"  ⚠️ 이 페이지에서 추출한 소설 제목을 정답으로 사용하지 마세요!\n"
                        f"  삭제된 작품과 유사한 제목의 다른 활성 작품을 우선 고려하세요.\n"
                    )
                if _pt == "community_post":
                    user_prompt += (
                        "  ⚠️ 커뮤니티 게시글: 이 페이지 제목은 독자가 쓴 글 제목입니다.\n"
                        "  본문을 읽고 실제 논의 대상 소설이 무엇인지 파악하세요.\n"
                    )
                if structured:
                    for k, v in structured.items():
                        if v and k not in ("text_preview", "page_type", "fetch_method"):
                            user_prompt += f"  {k}: {v}\n"
                if preview:
                    user_prompt += f"  📄 크롤링 본문:\n{preview[:1500]}\n"
                user_prompt += "\n"
        
        print(f"[{_ts()}][{self.emoji}] {self.name} 분석 시작: terms={key_terms}", file=sys.stderr)
        
        # 프롬프트 크기 로그 (제한 없음 — vLLM 서버가 최종 안전장치)
        print(f"[{_ts()}][{self.emoji}] 최종 user_prompt={len(user_prompt):,}자 (제한 없음)", file=sys.stderr)
        
        try:
            result = self._call_llm(
                user_prompt,
                gatekeeper_result=gatekeeper_result,
                ctx=ctx,
            )
            elapsed = time.time() - start_time
            
            # Merge dictionary matches with LLM result
            # 🔥 ctx 전달: 사전값도 검색 결과로 교정 가능하도록
            result = self._merge_dict_matches(result, dict_matches, ctx)
            result = self._sanitize_decoded_term_payload(result)
            # 사전 항목 간 유사어 오인 치환 방지
            result = self._sanitize_cross_term_dictionary_inference(result, slang_dictionary)
            
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
                confidence_map = {"high": 0.85, "max": 0.95, "medium": 0.6, "low": 0.3, "none": 0.0}
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
            
            # 🔥 작가 토론 감지: 다중 작가 비교/품평 게시글 → 작품 매칭 차단
            if ctx:
                result = self._detect_author_discussion(result, ctx)
            
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
            
            # 🆕 다중해석 자동 승격 (Multi-Interp Auto-Promotion)
            # best_match.title이 null이지만 interpretations에 novel_title + context_fit=high가 있으면
            # → best_match를 자동으로 승격 (Decoder가 결론을 내지 못한 것을 보충)
            result = self._auto_promote_high_fit_interpretation(result, ctx)

            # 🔥 커뮤니티 약칭 브리지 보류:
            # 공식 제목 브리지가 아직 안 붙은 상태에서 장르 일반화 후보로 굳는 것을 막는다.
            if ctx:
                result = self._guard_alias_bridge_pending(result, ctx, gatekeeper_result)

            # 🔥 약한 테마/캐릭터 연상으로 인한 작품명 환각 차단:
            # 약칭-정식명 연결 근거가 없는데, 줄거리 문구/캐릭터명만으로 unrelated title을
            # 올리는 경로를 막는다. (예: 망겜힐 -> 빌런 플레이어의 세계 정상화)
            if ctx:
                result = self._guard_weak_thematic_title_inference(result, ctx, gatekeeper_result)
            
            best = self._get_best_candidate(result)
            print(f"[{_ts()}][{self.emoji}] {self.name} 완료 ({elapsed:.1f}s): "
                  f"best_match={best}, confidence={result.get('overall_confidence')}", 
                  file=sys.stderr)
            
            # ⭐ suspected_titles 초기 생성 (Decoder가 첫 번째로 생성)
            if ctx:
                self._init_suspected_titles(result, ctx)
            
            # ━━ 개선: 가설 상태머신 업데이트 + candidate evidence bucket ━━
            if ctx and best:
                best_title = best if isinstance(best, str) else (best.get("title") if isinstance(best, dict) else None)
                if best_title:
                    # 가설 업데이트 (충돌 시 자동 무효화)
                    ev_list = []
                    for dt in result.get("decoded_terms", []):
                        bm = dt.get("best_match") or {}
                        if bm.get("title") == best_title:
                            gr = dt.get("grounding") or {}
                            if gr.get("anchor_type"):
                                ev_list.append(f"anchor:{gr['anchor_type']}")
                            if bm.get("confidence"):
                                ev_list.append(f"decoder_conf:{bm['confidence']}")
                    ctx.update_hypothesis(
                        title=best_title,
                        confidence=result.get("overall_confidence", "low"),
                        evidence=ev_list,
                        step=ctx.iteration,
                    )
                    
                    # candidate evidence bucket에 본문 근거 추가
                    for dt in result.get("decoded_terms", []):
                        bm = dt.get("best_match") or {}
                        if bm.get("title") == best_title:
                            gr = dt.get("grounding") or {}
                            if gr.get("anchor_type") and gr["anchor_type"] != "none":
                                ctx.add_evidence_for_candidate(best_title, "post_span", {
                                    "type": gr["anchor_type"],
                                    "source": "decoder_grounding",
                                    "original_term": dt.get("original", ""),
                                })
            
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
        import re

        matches = []
        resolved_slang = session_knowledge.get("resolved_slang", {})
        
        for term in terms:
            term_lower = term.lower().strip()
            term_norm = re.sub(r"[^0-9a-zA-Z가-힣]", "", term_lower)
            info = None

            if term_lower in resolved_slang:
                info = resolved_slang[term_lower]
            elif term_norm and term_norm in resolved_slang:
                info = resolved_slang[term_norm]

            if isinstance(info, dict) and info.get("official_title"):
                _official_title = info.get("official_title")
                if _has_domain_conflict_for_mapping(term, _official_title):
                    print(
                        f"[{_ts()}][{self.emoji}] 🚫 session_knowledge 매핑 스킵(도메인 충돌): "
                        f"'{term}' -> '{_official_title}'",
                        file=sys.stderr,
                    )
                    continue
                matches.append({
                    "slang": term,
                    "official_title": _official_title,
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
        """Merge dictionary matches as alias hints, not standalone title evidence.
        
        Curated dictionaries improve recall, but a dictionary hit by itself is
        not independent evidence that the post is about the mapped work.
        """
        if not dict_matches:
            return result
        
        # 🔥 검색 결과에서 공식 제목 추출 (사전값 교정용)
        official_titles = []
        if ctx:
            official_titles = self._extract_official_titles_from_search(ctx)
        
        decoded_terms = result.get("decoded_terms", [])
        # LLM 응답이 깨진 경우 decoded_terms가 None/str일 수 있음
        if not isinstance(decoded_terms, list):
            decoded_terms = []
        else:
            decoded_terms = [d for d in decoded_terms if isinstance(d, dict)]
        
        for term, title in dict_matches.items():
            # 🔥 사전값을 검색 결과의 공식 제목으로 교정
            corrected_title = self._correct_title_with_search_result(title, official_titles)
            if corrected_title != title:
                print(f"[{_ts()}][{self.emoji}] ⚠️ 사전값 교정: '{title}' → '{corrected_title}' (검색 결과 기반)", file=sys.stderr)
                title = corrected_title
            
            # Find existing entry or create new
            existing = next((d for d in decoded_terms if d.get("original") == term), None)
            
            if existing:
                # Add dictionary match as a reviewable hint. Do not override
                # best_match; independent search/post evidence must promote it.
                existing["candidates"].insert(0, {
                    "official_title": title,
                    "url": None,
                    "platform": None,
                    "decode_logic": "사전 매칭 힌트",
                    "morphological_score": 1.0,
                    "search_evidence": "slang_dictionary_hint",
                    "dictionary_alias_hint": True,
                })
                if not isinstance(existing.get("best_match"), dict):
                    existing["best_match"] = {"title": None, "confidence": "none"}
            else:
                decoded_terms.append({
                    "original": term,
                    "candidates": [{
                        "official_title": title,
                        "url": None,
                        "platform": None,
                        "decode_logic": "사전 매칭 힌트",
                        "morphological_score": 1.0,
                        "search_evidence": "slang_dictionary_hint",
                        "dictionary_alias_hint": True,
                    }],
                    "best_match": {"title": None, "confidence": "none"},
                    "is_author_name": False,
                    "author_info": None,
                    "resolution_note": "dictionary_alias_hint_requires_independent_evidence",
                })
        
        result["decoded_terms"] = decoded_terms
        
        return result

    def _sanitize_decoded_term_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Drop malformed nested decoder items so later passes can keep working."""
        decoded_terms = result.get("decoded_terms", [])
        if not isinstance(decoded_terms, list):
            result["decoded_terms"] = []
            return result

        cleaned_terms: List[Dict[str, Any]] = []
        removed_terms = 0
        removed_candidates = 0
        removed_interpretations = 0

        for term in decoded_terms:
            if not isinstance(term, dict):
                removed_terms += 1
                continue

            candidates = term.get("candidates", [])
            if isinstance(candidates, list):
                filtered_candidates = [cand for cand in candidates if isinstance(cand, dict)]
                removed_candidates += max(0, len(candidates) - len(filtered_candidates))
                term["candidates"] = filtered_candidates
            else:
                if candidates is not None:
                    removed_candidates += 1
                term["candidates"] = []

            interpretations = term.get("interpretations", [])
            if isinstance(interpretations, list):
                filtered_interps = [interp for interp in interpretations if isinstance(interp, dict)]
                removed_interpretations += max(0, len(interpretations) - len(filtered_interps))
                term["interpretations"] = filtered_interps
            else:
                if interpretations is not None:
                    removed_interpretations += 1
                term["interpretations"] = []

            if not isinstance(term.get("best_match"), dict):
                term["best_match"] = {"title": None, "confidence": "none"}

            cleaned_terms.append(term)

        if removed_terms or removed_candidates or removed_interpretations:
            print(
                f"[{_ts()}][{self.emoji}] ⚠️ decoder payload 정제: "
                f"terms -{removed_terms}, candidates -{removed_candidates}, "
                f"interpretations -{removed_interpretations}",
                file=sys.stderr,
            )

        result["decoded_terms"] = cleaned_terms
        return result

    def _sanitize_cross_term_dictionary_inference(
        self,
        result: Dict[str, Any],
        slang_dict: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        사전에 없는 약어를 다른 사전 항목으로 임의 치환하는 LLM 드리프트를 제거한다.

        예:
        - 입력 키워드: 죽깨수 (사전에 없음)
        - LLM 오인: 죽신성(사전 항목)으로 치환
        - 처리: dictionary 근거 해석만 제거하고 재검증 경로로 보낸다
        """
        decoded_terms = result.get("decoded_terms", [])
        if not isinstance(decoded_terms, list) or not isinstance(slang_dict, dict) or not slang_dict:
            return result

        norm_dict: Dict[str, str] = {}
        for k, v in slang_dict.items():
            if not isinstance(k, str) or not isinstance(v, str):
                continue
            kk = k.strip().lower()
            if not kk:
                continue
            norm_dict[kk] = v
            norm_dict.setdefault(kk.replace(" ", ""), v)

        def _is_dict_evidence(text: str) -> bool:
            t = (text or "").lower()
            return ("slang_dictionary" in t) or ("slang dictionary" in t) or ("사전" in t)

        def _title_text(value: Any) -> str:
            return str(value or "").strip()

        def _candidate_title(candidate: Dict[str, Any]) -> str:
            return _title_text(
                candidate.get("official_novel_title")
                or candidate.get("official_title")
                or candidate.get("title")
            )

        def _has_independent_title_support(term_entry: Dict[str, Any], title: str) -> bool:
            for cand in term_entry.get("candidates", []):
                if not isinstance(cand, dict):
                    continue
                cand_title = _candidate_title(cand)
                if cand_title and cand_title != title:
                    continue
                search_evidence = str(cand.get("search_evidence") or cand.get("evidence") or "")
                url = str(cand.get("url") or cand.get("source_url") or "")
                platform = str(cand.get("platform") or "")
                if cand.get("dictionary_alias_hint") is True:
                    continue
                if _is_dict_evidence(search_evidence):
                    continue
                if url or platform or search_evidence:
                    return True
            for interp in term_entry.get("interpretations", []):
                if not isinstance(interp, dict):
                    continue
                value = _title_text(interp.get("value") or interp.get("title"))
                if value and value != title:
                    continue
                evidence = str(interp.get("evidence") or "")
                if evidence and not _is_dict_evidence(evidence):
                    return True
            return False

        removed_total = 0

        for term_entry in decoded_terms:
            if not isinstance(term_entry, dict):
                continue

            original = str(term_entry.get("original") or "").strip().lower()
            original_nospace = original.replace(" ", "")
            allowed_titles = set()
            if original in norm_dict:
                allowed_titles.add(norm_dict[original])
            if original_nospace in norm_dict:
                allowed_titles.add(norm_dict[original_nospace])

            removed_titles: set[str] = set()

            # interpretations 정리
            interps = term_entry.get("interpretations", [])
            if isinstance(interps, list):
                kept_interps = []
                for interp in interps:
                    if not isinstance(interp, dict):
                        kept_interps.append(interp)
                        continue
                    evidence = str(interp.get("evidence") or "")
                    value = str(interp.get("value") or "").strip()
                    if _is_dict_evidence(evidence) and ((not allowed_titles) or (value and value not in allowed_titles)):
                        removed_total += 1
                        if value:
                            removed_titles.add(value)
                        continue
                    kept_interps.append(interp)
                term_entry["interpretations"] = kept_interps

            # candidates 정리
            candidates = term_entry.get("candidates", [])
            if isinstance(candidates, list):
                kept_candidates = []
                for cand in candidates:
                    if not isinstance(cand, dict):
                        continue
                    search_evidence = str(cand.get("search_evidence") or "")
                    cand_title = str(cand.get("official_novel_title") or cand.get("official_title") or "").strip()
                    if _is_dict_evidence(search_evidence) and ((not allowed_titles) or (cand_title and cand_title not in allowed_titles)):
                        removed_total += 1
                        if cand_title:
                            removed_titles.add(cand_title)
                        continue
                    kept_candidates.append(cand)
                term_entry["candidates"] = kept_candidates

            # best_match가 제거된 dictionary 오인 제목이면 초기화
            bm = term_entry.get("best_match")
            if isinstance(bm, dict):
                bm_title = str(bm.get("title") or "").strip()
                if bm_title and bm_title in removed_titles:
                    still_supported = False
                    for cand in term_entry.get("candidates", []):
                        if not isinstance(cand, dict):
                            continue
                        cand_title = str(cand.get("official_novel_title") or cand.get("official_title") or "").strip()
                        if cand_title and cand_title == bm_title:
                            still_supported = True
                            break
                    if not still_supported:
                        term_entry["best_match"] = {"title": None, "confidence": "none"}
                        removed_total += 1
                elif (
                    bm_title
                    and bm_title in allowed_titles
                    and not _has_independent_title_support(term_entry, bm_title)
                ):
                    term_entry["best_match"] = {
                        "title": None,
                        "confidence": "none",
                        "reason": "slang_dictionary_hint_requires_independent_evidence",
                    }
                    term_entry["resolution_note"] = "dictionary_alias_hint_requires_independent_evidence"
                    removed_total += 1

        if removed_total > 0:
            print(
                f"[{_ts()}][{self.emoji}] 🧹 사전 유사치환 오인 제거: {removed_total}건",
                file=sys.stderr,
            )

        result["decoded_terms"] = decoded_terms
        return result
    
    def _call_llm(
        self,
        user_prompt: str,
        *,
        gatekeeper_result: Optional[Dict[str, Any]] = None,
        ctx: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Call LLM and parse JSON response."""
        system_content = DECODER_SYSTEM.replace("{platform_map}", PLATFORM_ABBREVIATION_MAP)
        system_content = build_decoder_system_prompt(
            system_content,
            gatekeeper_result=gatekeeper_result,
            ctx=ctx,
        )
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ]
        
        response_text = self.llm._stream_chat_http(
            messages=messages,
            tag="decoder",
            use_grammar=True,
            max_tokens=self._resolve_max_tokens(),
        )
        
        return self._parse_json_response(response_text)

    def _resolve_max_tokens(self) -> int:
        """Bound decoder retries so recall loops cannot consume the full global cap."""
        raw = os.getenv("LLM_DECODER_MAX_TOKENS", os.getenv("LLM_EXPERT_MAX_TOKENS", "8192"))
        try:
            configured = int(raw)
        except Exception:
            configured = 8192
        try:
            llm_cap = int(getattr(self.llm, "max_tokens", configured) or configured)
        except Exception:
            llm_cap = configured
        try:
            hard_cap = int(os.getenv("LLM_DECODER_HARD_CAP", "12288"))
        except Exception:
            hard_cap = 12288
        return max(512, min(configured, llm_cap, max(512, hard_cap)))
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON from response, removing <think> blocks."""
        result = parse_json_with_think_removal(text)
        # Safety: decoded_terms는 항상 list[dict] 형태로 정규화
        _dt = result.get("decoded_terms", [])
        if not isinstance(_dt, list):
            result["decoded_terms"] = []
        else:
            result["decoded_terms"] = [d for d in _dt if isinstance(d, dict)]
        
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

    def _has_known_abbreviation_independent_anchor(
        self,
        ctx: Any,
        alias: str,
        title: str,
        *,
        official_titles: Optional[List[Dict[str, str]]] = None,
        search_results: Optional[List[Dict[str, Any]]] = None,
        term: Optional[Dict[str, Any]] = None,
        source_hint: str = "",
    ) -> bool:
        """Return true when a curated alias mapping has evidence beyond the registry pair."""
        title_norm = _normalize_alnum_kor_cached(title)
        alias_norm = _normalize_alnum_kor_cached(_strip_korean_particles(alias) or alias)
        if not title_norm:
            return False

        if source_hint in {"url_fetch_platform", "platform_title", "author_bridge"}:
            return True

        for ot in official_titles or []:
            if not isinstance(ot, dict):
                continue
            if _normalize_alnum_kor_cached(ot.get("title", "")) == title_norm:
                return True

        post_chunks: List[str] = []
        post_data = getattr(ctx, "post_data", {}) or {}
        if isinstance(post_data, dict):
            post_chunks.append(str(post_data.get("title") or ""))
            for block in post_data.get("content_blocks", []) or []:
                if isinstance(block, dict):
                    post_chunks.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    post_chunks.append(block)
        post_chunks.extend([
            str(c)
            for c in (getattr(ctx, "comments", []) or [])
            if isinstance(c, str) and c.strip()
        ])
        if title_norm and title_norm in _normalize_alnum_kor_cached(" ".join(post_chunks)):
            return True

        def _url_is_official(url: str) -> bool:
            url_l = str(url or "").lower()
            return any(p and p in url_l for p in OFFICIAL_PLATFORMS)

        for sr in search_results or getattr(ctx, "search_results", []) or []:
            if not isinstance(sr, dict):
                continue
            blob_norm = _normalize_alnum_kor_cached(
                f"{sr.get('title', '')} {sr.get('content', '')} {sr.get('snippet', '')}"
            )
            if title_norm and title_norm in blob_norm and _url_is_official(str(sr.get("url") or "")):
                return True
            if (
                title_norm
                and alias_norm
                and title_norm in blob_norm
                and alias_norm in blob_norm
                and _url_is_official(str(sr.get("url") or ""))
            ):
                return True

        if term:
            for cand in term.get("candidates", []) or []:
                if not isinstance(cand, dict):
                    continue
                cand_title = (
                    cand.get("official_novel_title")
                    or cand.get("official_title")
                    or cand.get("title")
                )
                if cand_title and _normalize_alnum_kor_cached(cand_title) != title_norm:
                    continue
                search_evidence = str(cand.get("search_evidence") or cand.get("evidence") or "")
                if cand.get("dictionary_alias_hint") is True:
                    continue
                if "slang_dictionary" in search_evidence or "사전" in search_evidence:
                    continue
                if cand.get("url") or cand.get("source_url") or cand.get("platform") or search_evidence:
                    return True

        return False
    
    def _init_suspected_titles(self, result: Dict[str, Any], ctx: Any) -> None:
        """
        ⭐ suspected_titles 초기 생성 (Decoder가 첫 번째로 생성)
        Verifier, Critic이 이 목록을 참조하고 수정할 수 있음
        
        🔥 CRITICAL: 검색 결과에서 공식 플랫폼(novelpia, namu.wiki, munpia)의
        정확한 제목을 추출하여 LLM 생성 제목을 교정해야 함!
        """
        suspected = []
        decoded_terms = result.get("decoded_terms", [])
        decoded_terms = [t for t in decoded_terms if isinstance(t, dict)]
        
        # 🔥 Step 0: 검색 결과에서 공식 플랫폼의 정확한 제목 추출
        official_titles_from_search = self._extract_official_titles_from_search(ctx)
        _decoded_original_norms = [
            _re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(t.get("original", ""))).lower()
            for t in decoded_terms
            if isinstance(t, dict) and t.get("original")
        ]

        def _looks_short_fragment_term(_term: Dict[str, Any], _candidate_title: str) -> bool:
            """
            제목 문맥에 붙어 나온 짧은 일반어 단어가 단일 작품명으로 승격되는 것을 방지한다.
            - 특정 작품 하드코딩 없이 구조적 특징만 사용
            - 짧은 토큰(<=3) + 비작품 해석(high) + 더 긴 복합 토큰에 포함 → 파편으로 간주
            """
            if not isinstance(_term, dict) or not _candidate_title:
                return False
            _orig_norm = _re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(_term.get("original", ""))).lower()
            _title_norm = _re.sub(r"[^\uac00-\ud7a3A-Za-z0-9]", "", str(_candidate_title)).lower()
            if not _orig_norm or not _title_norm or _orig_norm != _title_norm:
                return False
            if len(_title_norm) > 3:
                return False

            _non_title_high = False
            for _it in (_term.get("interpretations") or []):
                if not isinstance(_it, dict):
                    continue
                _itype = str(_it.get("type") or "").lower()
                _fit = str(_it.get("context_fit") or "").lower()
                if _fit in {"high", "medium"} and _itype in {"genre_term", "common_noun", "unknown"}:
                    _non_title_high = True
                    break
            if not _non_title_high:
                return False

            _embedded_in_longer = any(
                _orig_norm != _n
                and len(_n) >= len(_orig_norm) + 2
                and _orig_norm in _n
                for _n in _decoded_original_norms
            )
            return _embedded_in_longer
        
        for term in decoded_terms:
            if not term:
                continue
            
            # 작가명은 제외
            if term.get("is_author_name"):
                continue
            
            # best_match에서 title 확인
            best_match = term.get("best_match") or {}
            best_title = best_match.get("title")
            best_conf = str(best_match.get("confidence", "none") or "none").lower()
            # low/none으로 강등된 항목은 suspected_titles의 출발점으로 쓰지 않음
            if not best_title or best_conf not in ("high", "medium"):
                continue
            best_title = self._correct_title_with_search_result(best_title, official_titles_from_search)
            if _looks_short_fragment_term(term, best_title):
                print(
                    f"[{_ts()}][{self.emoji}] ⏭️ suspected 단일어 파편 스킵: "
                    f"term='{term.get('original', '')}', title='{best_title}'",
                    file=sys.stderr,
                )
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
                if _looks_short_fragment_term(term, title):
                    print(
                        f"[{_ts()}][{self.emoji}] ⏭️ candidate 단일어 파편 스킵: "
                        f"term='{term.get('original', '')}', cand='{title}'",
                        file=sys.stderr,
                    )
                    continue
                # best_match와 동떨어진 후보는 노이즈 가능성이 높으므로 제외
                if title != best_title:
                    cand_score = abbreviation_match_score(term.get("original", ""), title)
                    if cand_score < 0.45:
                        print(
                            f"[{_ts()}][{self.emoji}] ⏭️ suspected 후보 스킵(정합성 부족): "
                            f"term='{term.get('original', '')}', cand='{title}' "
                            f"(best='{best_title}', score={cand_score:.2f})",
                            file=sys.stderr,
                        )
                        continue
                
                # 중복 체크
                if any(s.get("title") == title for s in suspected):
                    continue
                cand_conf = cand.get("morphological_score", 0.5)
                # best_match가 medium이면 후보 신뢰도도 보수적으로 캡
                if best_conf == "medium":
                    cand_conf = min(cand_conf, 0.75)
                
                suspected.append({
                    "title": title,
                    "confidence": cand_conf,
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
                    interp_score = abbreviation_match_score(term.get("original", ""), interp_value)
                    _orig_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', str(term.get("original", ""))).lower()
                    _interp_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', str(interp_value)).lower()
                    _known_map = {
                        _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', k).lower():
                        _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', v).lower()
                        for k, v in KNOWN_ABBREVIATIONS.items()
                    }
                    _in_known = bool(_orig_norm and _known_map.get(_orig_norm) == _interp_norm)
                    if interp_score < 0.35 and not _in_known:
                        print(
                            f"[{_ts()}][{self.emoji}] ⏭️ 다중해석 suspected 스킵: "
                            f"'{term.get('original')}' → '{interp_value}' "
                            f"(score={interp_score:.2f})",
                            file=sys.stderr,
                        )
                        continue
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
        #
        # 🛡️ Genre Discussion Guard:
        # snippet_analyzer가 genre_discussion으로 판정 + decoder LLM도 best_match=None이면
        # _resolved_mappings 폴백으로 제목을 승격시키지 않는다.
        # (장르 클리셰 용어가 우연히 작품 제목에 포함된 경우 false positive 방지)
        _genre_discussion_block = False
        if ctx:
            _dw = getattr(ctx, 'discourse_warning', '') or ''
            _snippet_analysis = getattr(ctx, 'llm_snippet_analysis', None) or {}
            _snippet_cat = ''
            _snippet_intent = ''
            if isinstance(_snippet_analysis, dict):
                _snippet_cat = str(_snippet_analysis.get('identified_category') or '').lower()
                _snippet_intent = str(_snippet_analysis.get('post_intent') or '').lower()
            if (
                'genre_discussion' in _dw
                or _snippet_cat == 'genre_discussion'
                or _snippet_intent == 'genre_discussion'
            ):
                _genre_discussion_block = True
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ genre_discussion 감지 + decoder null → "
                    f"_resolved_mappings 폴백 차단 (discourse_warning='{_dw[:60]}', "
                    f"snippet_cat='{_snippet_cat}', snippet_intent='{_snippet_intent}')",
                    file=sys.stderr,
                )
        
        if not suspected and ctx and not _genre_discussion_block:
            _resolved = getattr(ctx, '_resolved_mappings', []) or []
            if _resolved:
                # 검색 결과에서 공식 제목 확인
                official_titles_from_search = self._extract_official_titles_from_search(ctx)
                existing_titles = {s.get('title') for s in existing}
                _norm = lambda s: _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', str(s or '')).lower()
                official_title_norms = {
                    _norm(o.get("title", ""))
                    for o in official_titles_from_search
                    if isinstance(o, dict) and o.get("title")
                }
                known_abbrev_norm_map = {
                    _norm(k): _norm(v) for k, v in KNOWN_ABBREVIATIONS.items()
                }
                snippet_abbrev_source: Dict[tuple[str, str], str] = {}
                if hasattr(ctx, "snippet_hints") and ctx.snippet_hints:
                    for ah in (ctx.snippet_hints.get("abbreviation_hints") or []):
                        if not isinstance(ah, dict):
                            continue
                        a_norm = _norm(ah.get("abbrev", ""))
                        f_norm = _norm(ah.get("full", ""))
                        if a_norm and f_norm:
                            snippet_abbrev_source[(a_norm, f_norm)] = str(ah.get("source", "") or "")
                
                # 🔧 Fix F: 제목 후보로 적합하지 않은 매핑 필터링
                # _resolved_mappings는 증거 기반 맥락 추론용이므로
                # 일반 명사, 욕설, 사전 항목 등이 포함될 수 있음
                _TITLE_BLOCKLIST_PATTERNS = {
                    '/', '(', ')', '국어사전', '나무위키', '위키',
                    '욕설', '표준어', '줄임', '뜻', '사전',
                    '장점과 단점', '보통 뭐라고', '찾는 법', '대표작',
                    '레전드 작가', '포텐', '갤러리', '커뮤니티',
                }
                
                for abbrev, full_title in _resolved:
                    # 검색 결과의 공식 제목으로 교정
                    corrected = self._correct_title_with_search_result(full_title, official_titles_from_search)
                    if corrected in existing_titles:
                        continue
                    abbrev_norm = _norm(abbrev)
                    full_norm = _norm(full_title)
                    corrected_norm = _norm(corrected)
                    
                    # 🔧 Fix F: 제목 후보 품질 검증
                    _skip = False
                    # 1) 약칭과 동일(자기참조) → 스킵
                    if corrected.strip() == abbrev.strip():
                        _skip = True
                    # 2) 차단 패턴 포함 → 스킵
                    elif any(pat in corrected for pat in _TITLE_BLOCKLIST_PATTERNS):
                        _skip = True
                    # 3) 너무 짧거나 한글이 없는 경우 → 스킵
                    elif len(corrected) < 2 or not any('\uac00' <= c <= '\ud7a3' or c.isascii() and c.isalpha() for c in corrected):
                        _skip = True
                    # 4) GENRE_ARCHETYPE_TERMS에 해당 → 스킵
                    elif corrected in GENRE_ARCHETYPE_TERMS:
                        _skip = True
                    
                    if _skip:
                        continue

                    # 🔒 공식/근거 기반 매핑만 suspected_titles에 반영
                    # - KNOWN_ABBREVIATIONS 직접 매핑
                    # - 공식 플랫폼 검색 제목과 일치
                    # - snippet_hints의 공식 소스(url_fetch_platform/platform_title/author_bridge)
                    source_hint = snippet_abbrev_source.get((abbrev_norm, corrected_norm))
                    if not source_hint:
                        source_hint = snippet_abbrev_source.get((abbrev_norm, full_norm), "")
                    source_is_official = source_hint in {"url_fetch_platform", "platform_title", "author_bridge"}
                    known_match = (
                        abbrev_norm in known_abbrev_norm_map
                        and known_abbrev_norm_map[abbrev_norm] == corrected_norm
                    )
                    official_match = corrected_norm in official_title_norms
                    known_match_has_anchor = known_match and self._has_known_abbreviation_independent_anchor(
                        ctx,
                        abbrev,
                        corrected,
                        official_titles=official_titles_from_search,
                        source_hint=source_hint,
                    )
                    if not (known_match_has_anchor or official_match or source_is_official):
                        print(
                            f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 스킵(공식근거 부족): "
                            f"'{abbrev}' → '{corrected}'",
                            file=sys.stderr,
                        )
                        continue

                    conf = 0.88 if known_match_has_anchor else (0.82 if official_match else 0.74)
                    suspected.append({
                        "title": corrected,
                        "confidence": conf,
                        "source_term": abbrev,
                        "source_expert": "decoder_mapping_official",
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
        post_title_raw = str((getattr(ctx, "post_data", {}) or {}).get("title", "") or "")
        post_title_norm = _norm_domain_text(post_title_raw)

        def _looks_sentence_like_title(text: str) -> bool:
            """
            커뮤니티 본문/리뷰 문장을 작품명으로 오인하는 패턴을 방어한다.
            - 규칙은 특정 작품/키워드가 아닌 문장 구조 기반으로만 판단
            - 단, 이 함수는 'community_only' 분기에서만 사용되어 과차단을 줄임
            """
            if not text or not isinstance(text, str):
                return False
            t = re.sub(r"\s+", " ", text).strip()
            if not t:
                return False

            token_count = len(re.findall(r"[가-힣A-Za-z0-9]+", t))
            has_clause_connector = bool(
                re.search(r"(는데|면서|해서|하며|라고|이라는|같은|처럼|듯이)", t)
            )
            has_meta_prefix = bool(
                re.match(r"^(제목|내용|스토리|줄거리)\s*(그대로|요약)", t)
            )

            # 긴 어절 + 서술/연결 어미를 가진 경우는 커뮤니티 문장일 가능성이 높다.
            if token_count >= 8 and (has_clause_connector or len(t) >= 30 or has_meta_prefix):
                return True
            return False
        
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
                
                grounding = term.get("grounding") or {}
                anchor_type = str(grounding.get("anchor_type") or "").lower()
                original_norm = _norm_domain_text(original_term)
                original_in_post_title = bool(
                    original_norm and post_title_norm and (original_norm in post_title_norm)
                )
                preserve_anchor_term = (
                    anchor_type in {"title_mention", "character_title_link"}
                    and original_in_post_title
                )

                # 🆕 복합어 보정: morphemes에서 제목 부분만 추출
                # 단, 제목 앵커로 직접 등장한 약칭은 원문 보존(과차단 방지)
                effective_term = original_term
                morphs = term.get("morphemes") or []
                if morphs and len(morphs) >= 2 and title and not preserve_anchor_term:
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
                
                current_abbr_score = abbreviation_match_score(
                    (original_term or effective_term),
                    title,
                ) if (original_term or effective_term) and title else 0.0

                if best_alt and best_alt_score >= 0.3:
                    # 현재 제목이 약칭 정합도가 충분히 높은 경우,
                    # 더 낮은 점수의 대체 제목으로 덮어쓰지 않는다.
                    if current_abbr_score >= 0.55 and (best_alt_score + 0.05) < current_abbr_score:
                        print(
                            f"[{_ts()}][{self.emoji}] ⏭️ 커뮤니티 제목 교정 스킵: "
                            f"현재 정합도 유지('{title}', cur={current_abbr_score:.2f} > alt={best_alt_score:.2f})",
                            file=sys.stderr,
                        )
                        continue
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
                    # 대안이 없으면 약칭 정합도를 재평가하여
                    # 커뮤니티 문장형 제목을 작품명으로 유지하지 않도록 방어한다.
                    _score_term = effective_term or original_term
                    _abbr_score = abbreviation_match_score(_score_term, title) if _score_term else 0.0
                    _sentence_like = _looks_sentence_like_title(title)
                    if _sentence_like:
                        old_title = best_match.get("title")
                        best_match["title"] = None
                        best_match["confidence"] = "none"
                        candidates = term.get("candidates", [])
                        if isinstance(candidates, list):
                            filtered = []
                            for cand in candidates:
                                cand_title = str(
                                    (cand or {}).get("official_novel_title")
                                    or (cand or {}).get("official_title")
                                    or ""
                                ).strip()
                                if cand_title and cand_title == title:
                                    continue
                                filtered.append(cand)
                            term["candidates"] = filtered
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 문장형 제목 제거: '{old_title}' "
                            f"(community_only=True, sentence_like=True, abbr_score={_abbr_score:.2f})",
                            file=sys.stderr,
                        )
                        changed = True
                    elif _abbr_score < 0.35:
                        old_title = best_match.get("title")
                        best_match["title"] = None
                        best_match["confidence"] = "none"
                        # 동일 제목 후보 제거
                        candidates = term.get("candidates", [])
                        if isinstance(candidates, list):
                            filtered = []
                            for cand in candidates:
                                cand_title = str(
                                    (cand or {}).get("official_novel_title")
                                    or (cand or {}).get("official_title")
                                    or ""
                                ).strip()
                                if cand_title and cand_title == title:
                                    continue
                                filtered.append(cand)
                            term["candidates"] = filtered
                        print(
                            f"[{_ts()}][{self.emoji}] 🚫 커뮤니티 제목 제거: '{old_title}' "
                            f"(community_only=True, abbr_score={_abbr_score:.2f}, 공식 플랫폼 근거 없음)",
                            file=sys.stderr,
                        )
                        changed = True
                    elif best_match.get("confidence") in ("high", "medium"):
                        best_match["confidence"] = "low"
                        print(f"[{_ts()}][{self.emoji}] ⚠️ 커뮤니티 제목 의심: '{title}' → confidence=low "
                              f"(커뮤니티 URL에서만 발견됨, 공식 플랫폼 증거 없음, abbr_score={_abbr_score:.2f})",
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
                if not isinstance(cand, dict):
                    continue
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

                # 🆕 BUG-C 방어: 파생작/2차창작 URL 교정 거부
                # 노벨피아 등에서 [원작약칭] 제목 패턴은 해당 원작의 팬픽/스핀오프
                # 예: "[망겜성] 여자가 되다." = 원작 "망겜의 성기사"의 2차창작
                _deriv_m = re.match(
                    r'^\[([가-힣A-Za-z0-9\s]+)\]\s*(.+)', official_title
                )
                if _deriv_m:
                    _bracket_tag = _deriv_m.group(1).strip()
                    _original_term = term.get("original", "").strip()
                    if _bracket_tag and _original_term:
                        _bt_n = _bracket_tag.replace(" ", "").lower()
                        _ot_n = _original_term.replace(" ", "").lower()
                        if (
                            _bt_n == _ot_n
                            or _bt_n in _ot_n
                            or _ot_n in _bt_n
                            or SequenceMatcher(
                                None, _bt_n, _ot_n
                            ).ratio() >= 0.7
                        ):
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 파생작(2차창작) URL 교정 거부: "
                                f"'{official_title}' (tag='{_bracket_tag}' "
                                f"≈ term='{_original_term}') — 원작 아님",
                                file=sys.stderr,
                            )
                            # 해당 URL의 검색결과에 파생작 플래그 설정
                            for _sr in search_results:
                                _sr_url_n = _sr.get("url", "").split("?")[0].rstrip("/")
                                if _sr_url_n == cand_norm:
                                    _sr["_is_derivative"] = True
                                    _sr["_derivative_of"] = _bracket_tag
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
                        # 동일 문자열(best=bm_title=약어 자체) 케이스도 보존 점수로 취급
                        # 해야 잘못된 플랫폼 URL 교정을 더 안정적으로 차단할 수 있다.
                        old_abbr_score = _abbr_alignment_guard_score(original_term, bm_title)
                        new_abbr_score = _abbr_alignment_guard_score(original_term, official_title)
                        if old_abbr_score > new_abbr_score + 0.1:
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 플랫폼 URL 제목 교정 거부: "
                                f"'{bm_title}'(abbr={old_abbr_score:.2f}) → '{official_title}'(abbr={new_abbr_score:.2f}) "
                                f"약어 스코어 역전 → 교정 안함",
                                file=sys.stderr,
                            )
                            continue

                        # 도메인 신호 충돌(예: 무림 약어 → 게임 제목) 차단
                        if _has_domain_conflict_for_mapping(original_term, official_title):
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 플랫폼 URL 제목 교정 거부(도메인 충돌): "
                                f"'{original_term}' → '{official_title}'",
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
                if not isinstance(cand, dict):
                    continue
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

    # ────────────────────────────────────────────────────────────
    # 🆕 검색 증거 기반 일반 어휘 탐지  (Generic — 하드코딩 아님)
    # ────────────────────────────────────────────────────────────
    def _detect_common_word_from_search(
        self,
        term_text: str,
        search_results: list,
        ctx: Any = None,
    ) -> str | None:
        """
        🔤 Gatekeeper가 캐릭터명/작품명 후보로 식별한 용어가 실제로는
        일반 어휘(감탄사·대명사·조사 등)인지 검색 결과에서 확인.

        확인 방법:
          1. 참고 사이트(namu.wiki, wikipedia, 사전 등) 중
             해당 용어 전용 문서(URL에 용어 포함)만 검토
          2. 전용 문서의 title+content에 언어학적 분류 카테고리가
             등장하면 "이 용어는 일반 어휘"로 판정
          3. 검색 snippet이 잘려서 분류 레이블이 누락되었을 수 있으므로
             crawl4ai fetched_page_info의 본문도 추가 확인

        Returns:
            감지된 어휘 분류 문자열 (예: "감탄사", "대명사") 또는 None
        """
        if not term_text or len(term_text) < 2:
            return None

        term_clean = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', term_text).lower()
        if not term_clean:
            return None

        # 언어학적 어휘 분류 카테고리 — 범용 목록
        # (하드코딩된 단어 목록이 아니라, 사전/위키가 사용하는 *분류 레이블*)
        _LINGUISTIC_CATEGORIES = (
            "감탄사", "대명사", "인칭대명사", "1인칭", "2인칭", "3인칭",
            "조사", "접미사", "부사", "의성어", "의태어", "접속사",
            "관용구", "관용어", "호칭", "존칭",
            "전치사", "관사", "수사", "종결어미", "어미", "접두사",
        )

        # 의미 설명 패턴 — "X는 ~를 뜻하는 Y" 등 사전/위키 정의문
        # (언어와 무관하게, 외국어 단어·표현을 설명하는 패턴)
        _MEANING_PATTERNS = (
            "을 뜻하는", "를 뜻하는", "라는 뜻", "이라는 뜻",
            "을 의미하", "를 의미하", "뜻을 가진",
            "일본어 표현", "일본어로 ", "일본어의 ",
            "영어 표현", "영어로 ", "영어의 ",
            "중국어 표현", "중국어로 ",
            "한자로 ", "한자어 ",
        )

        # 참고 사이트 도메인 (사전·백과사전·레퍼런스)
        _REFERENCE_DOMAINS = (
            "namu.wiki", "wikipedia.org", "ko.dict", "korean.go.kr",
            "jisho.org", "weblio.jp", "dic.daum.net", "dict.naver.com",
            "ko.wiktionary.org",
        )

        import urllib.parse as _urlparse

        def _check_text_for_signals(text: str) -> str | None:
            """텍스트에서 일반어휘 신호 탐지."""
            text_lower = text.lower()
            # 1차: 언어학적 분류 카테고리 직접 매칭
            for cat in _LINGUISTIC_CATEGORIES:
                if cat in text_lower:
                    return cat
            # 2차: 의미 설명 패턴 매칭
            for pat in _MEANING_PATTERNS:
                if pat in text_lower:
                    return f"어휘설명({pat.strip()})"
            return None

        # ── Pass A: 검색 결과 snippet에서 확인 ──
        _dedicated_urls: list[str] = []  # Pass B용 전용 문서 URL 목록
        for sr in search_results:
            sr_url = (sr.get("url") or "").lower()

            # 참고 사이트만 대상
            is_reference = any(d in sr_url for d in _REFERENCE_DOMAINS)
            if not is_reference:
                continue

            # URL에 용어가 직접 포함된 전용 문서만 체크
            try:
                decoded_url = _urlparse.unquote(sr_url)
            except Exception:
                decoded_url = sr_url
            url_norm = _re.sub(r'[^\uac00-\ud7a3a-z0-9]', '', decoded_url)
            if term_clean not in url_norm:
                continue

            _dedicated_urls.append(sr_url)

            # 검색 snippet에서 신호 탐지
            combined = (
                (sr.get("title") or "") + " " +
                (sr.get("content") or sr.get("snippet") or "")
            )
            result = _check_text_for_signals(combined)
            if result:
                return result

        # ── Pass B: 크롤링된 페이지 본문에서 확인 ──
        # 검색 snippet이 너무 짧아 분류 레이블이 잘린 경우,
        # crawl4ai가 페치한 전체 페이지에서 재확인
        if ctx and _dedicated_urls:
            fetched_pages = getattr(ctx, 'fetched_page_info', []) or []
            for fp in fetched_pages:
                if not isinstance(fp, dict):
                    continue
                fp_url = (fp.get("url") or "").lower()
                # 전용 문서 URL과 매칭되는 페치 결과만 확인
                if not any(du in fp_url or fp_url in du for du in _dedicated_urls):
                    continue
                # 구조적 정보 + 본문 미리보기 확인
                structured = fp.get("structured_info") or {}
                text_parts = [
                    str(structured.get("title") or ""),
                    str(structured.get("description") or ""),
                    str(fp.get("text_preview") or ""),
                ]
                page_text = " ".join(text_parts)
                result = _check_text_for_signals(page_text)
                if result:
                    return result

        return None

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
        gk_clues = gk_out.get("context_clues") or {}
        gk_post_type = str(gk_out.get("post_type") or "").strip().lower()
        gk_comment_candidates = gk_clues.get("comment_title_candidates") or []
        comment_secondary_examples: List[str] = []
        comment_secondary_mode = bool(
            gk_clues.get("is_recommendation_request")
            or gk_clues.get("is_comparison_post")
            or gk_clues.get("genre_discussion_detected")
            or gk_clues.get("genre_negation_detected")
            or gk_clues.get("multi_work_order_detected")
            or gk_post_type in {"genre_discussion", "trope_discussion", "genre_opinion", "recommendation"}
        )
        gk_comment_norms = {
            _re.sub(r"[^\w가-힣]", "", str(t)).lower()
            for t in gk_comment_candidates
            if isinstance(t, str) and t.strip()
        }
        _post_data_local = ctx.post_data or {}
        _post_main_parts = [str(_post_data_local.get("title") or "")]
        for _blk in _post_data_local.get("content_blocks", []) or []:
            if isinstance(_blk, dict):
                _post_main_parts.append(str(_blk.get("text") or ""))
            elif isinstance(_blk, str):
                _post_main_parts.append(_blk)
        _post_main_norm = _re.sub(r"[^\w가-힣]", "", " ".join(_post_main_parts)).lower()
        _official_norms = {
            _re.sub(r"[^\w가-힣]", "", str(o.get("title") or "")).lower()
            for o in all_search_titles
            if isinstance(o, dict)
        }
        _gk_title_norms = {
            _re.sub(r"[^\w가-힣]", "", str(t or "")).lower()
            for t in gk_possible
            if isinstance(t, str) and str(t or "").strip()
        }
        for gk_title in gk_possible:
            if not (isinstance(gk_title, str) and len(gk_title) >= 2):
                continue
            _gk_norm = _re.sub(r"[^\w가-힣]", "", gk_title).lower()
            _looks_like_speculative_expansion = bool(
                _gk_norm
                and len(_gk_norm) >= 6
                and _gk_norm not in _post_main_norm
                and _gk_norm not in _official_norms
                and any(
                    raw_norm != _gk_norm
                    and len(raw_norm) <= 5
                    and raw_norm in _post_main_norm
                    and _gk_norm.startswith(raw_norm)
                    for raw_norm in _gk_title_norms
                )
            )
            if _looks_like_speculative_expansion:
                print(
                    f"[{_ts()}][{self.emoji}] 🧹 speculative GK 제목 보류: "
                    f"'{gk_title}' (raw alias 우선)",
                    file=sys.stderr,
                )
                continue
            _is_comment_only = _gk_norm and (_gk_norm in gk_comment_norms) and (_gk_norm not in _post_main_norm)
            if _is_comment_only and comment_secondary_mode:
                comment_secondary_examples.append(gk_title)
                print(
                    f"[{_ts()}][{self.emoji}] 🧭 comment-only 제목 후보 secondary 분리: "
                    f"'{gk_title}' (genre/reco/compare context)",
                    file=sys.stderr,
                )
                continue
            if _is_comment_only and _gk_norm not in _official_norms:
                print(
                    f"[{_ts()}][{self.emoji}] ⚖️ comment-only 후보 보류: "
                    f"'{gk_title}' (post_main 미등장 + 공식 근거 없음)",
                    file=sys.stderr,
                )
                continue
            raw_title_pool.append(gk_title)
        if gk_possible:
            print(
                f"[{_ts()}][{self.emoji}] 📥 Gatekeeper possible_titles → title_pool: "
                f"{gk_possible}",
                file=sys.stderr,
            )

        # ── 🆕 snippet_analyzer 줄임 매핑의 full 제목을 title_pool에 통합 ──
        # snippet_analyzer가 "즉사무림 → 즉사기 들고 무림에 떨어지다" 매핑을 생성했으면
        # 해당 정식 제목을 title_pool에 추가하여 약어 가드 2단계에서 교정 후보로 사용
        _snippet_hints = getattr(ctx, 'snippet_hints', None) or {}
        _snippet_abbr_mappings = _snippet_hints.get('abbreviation_mappings') or []
        for _sam in _snippet_abbr_mappings:
            if isinstance(_sam, dict):
                _sam_full = _sam.get('full', '').strip()
                if _sam_full and len(_sam_full) >= 3:
                    raw_title_pool.append(_sam_full)
        # ctx에 직접 저장된 snippet abbreviation_mappings도 통합
        _ctx_abbr_map = getattr(ctx, 'abbreviation_mappings', None) or {}
        for _abbr_key, _abbr_val in _ctx_abbr_map.items():
            if isinstance(_abbr_val, str) and len(_abbr_val) >= 3:
                raw_title_pool.append(_abbr_val)

        # 중복 제거
        seen_titles: set[str] = set()
        title_pool: list[str] = []
        for t in raw_title_pool:
            t_stripped = t.strip()
            if t_stripped and t_stripped not in seen_titles:
                seen_titles.add(t_stripped)
                title_pool.append(t_stripped)

        # 🆕 제목 key_term → anchor_type 보정
        # 게시글 제목에 존재하는 key_term이 search_only로 표시된 경우 title_mention으로 보정
        # 예: "즉사무림"은 게시글 제목 "스포) 즉사무림 예상된 전개긴하지만"에 직접 존재
        #     → is_grounded=false, anchor_type=search_only는 잘못됨 → title_mention으로 보정
        post_data = ctx.post_data or {}
        _post_title_raw = (post_data.get("title") or "").replace(" ", "").lower()
        if _post_title_raw:
            for term in decoded_terms:
                if not isinstance(term, dict):
                    continue
                _orig = (term.get("original") or "").replace(" ", "").lower()
                if not _orig or len(_orig) < 2:
                    continue
                grounding = term.get("grounding")
                if not isinstance(grounding, dict):
                    continue
                _cur_anchor = (grounding.get("anchor_type") or "none").lower()
                # 게시글 제목에 해당 용어가 있고, anchor가 search_only/none이면 보정
                if _orig in _post_title_raw and _cur_anchor in ("search_only", "none"):
                    grounding["anchor_type"] = "title_mention"
                    grounding["is_grounded"] = True
                    grounding["anchor_evidence"] = f"게시글 제목에 '{term.get('original')}' 직접 존재"
                    print(
                        f"[{_ts()}][{self.emoji}] 🏷️ anchor_type 보정: "
                        f"'{term.get('original')}' search_only → title_mention "
                        f"(게시글 제목에 포함)",
                        file=sys.stderr,
                    )

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
                # 🔧 FIX: 작가명 해석이 있더라도, 약어↔제목 형태소가 극단적 불일치이고
                # title_pool에 형태소가 완전 매칭되는 경쟁 후보가 있으면 스킵하지 않음
                # 예: '즉사무림' → interpretations에 author_name "즉사무림작가" (medium)
                #     하지만 best_match.title="즉사기 들고 게임 속으로" (score=0.00, 무림 없음)
                #     title_pool에 "즉사기 들고 무림에 떨어지다" (score=0.90) 존재
                #     → 스킵하면 교정 기회 상실 → 스킵하지 않고 약어 가드 진행
                _cur_best_match = term.get("best_match") or {}
                _cur_title_for_skip = _cur_best_match.get("title") or ""
                _abbr_score_for_skip = abbreviation_match_score(original, _cur_title_for_skip) if _cur_title_for_skip else 0.0
                _morphemes_for_skip = term.get("morphemes", [])
                _morpheme_ok_for_skip = True
                if _morphemes_for_skip and len(_morphemes_for_skip) >= 2 and _cur_title_for_skip:
                    _tn = _cur_title_for_skip.replace(" ", "")
                    _morpheme_ok_for_skip = all(m in _tn for m in _morphemes_for_skip)
                
                # 형태소도 OK이고 약어 스코어 ≥ 0.5이면 → 원래대로 스킵 (작가→대표작 매핑)
                if _abbr_score_for_skip >= 0.5 or (_morpheme_ok_for_skip and _abbr_score_for_skip >= 0.3):
                    # 🆕 BUG-C 방어: snippet_analyzer가 더 우수한 매핑을 제공하면 스킵하지 않음
                    # 예: "망겜성" → Decoder="망겜성이 생각나는 게임이 현실이 된 소설"(0.30)
                    #     snippet="망겜의 성기사"(0.85) → 가드 진행하여 교정
                    _snippet_better = False
                    _sh_skip = getattr(ctx, 'snippet_hints', None) or {}
                    for _am_skip in (_sh_skip.get('abbreviation_mappings') or []):
                        if not isinstance(_am_skip, dict):
                            continue
                        _am_abbr = (_am_skip.get('abbrev') or _am_skip.get('abbr') or '').strip()
                        _am_full = (_am_skip.get('full') or '').strip()
                        if _am_abbr == original and _am_full and _am_full != _cur_title_for_skip:
                            _am_score = abbreviation_match_score(original, _am_full)
                            if _am_score > _abbr_score_for_skip + 0.15:
                                _snippet_better = True
                                print(
                                    f"[{_ts()}][{self.emoji}] ⚠️ snippet 매핑이 더 우수: "
                                    f"'{original}' → snippet='{_am_full}'(score={_am_score:.2f}) "
                                    f"vs decoder='{_cur_title_for_skip}'(score={_abbr_score_for_skip:.2f}) "
                                    f"→ 약어 가드 진행",
                                    file=sys.stderr,
                                )
                                break
                    # ctx.abbreviation_mappings도 확인
                    if not _snippet_better:
                        _ctx_am = getattr(ctx, 'abbreviation_mappings', None) or {}
                        _ctx_full = _ctx_am.get(original)
                        if _ctx_full and isinstance(_ctx_full, str) and _ctx_full != _cur_title_for_skip:
                            _ctx_am_score = abbreviation_match_score(original, _ctx_full)
                            if _ctx_am_score > _abbr_score_for_skip + 0.15:
                                _snippet_better = True
                                print(
                                    f"[{_ts()}][{self.emoji}] ⚠️ ctx 약칭 매핑이 더 우수: "
                                    f"'{original}' → ctx='{_ctx_full}'(score={_ctx_am_score:.2f}) "
                                    f"vs decoder='{_cur_title_for_skip}'(score={_abbr_score_for_skip:.2f}) "
                                    f"→ 약어 가드 진행",
                                    file=sys.stderr,
                                )
                    if not _snippet_better:
                        print(
                            f"[{_ts()}][{self.emoji}] ℹ️ 작가명 해석 존재 '{original}' → 약어 가드 스킵 "
                            f"(is_author_name=false이지만 interpretations에 author_name 있음, "
                            f"score={_abbr_score_for_skip:.2f})",
                            file=sys.stderr,
                        )
                        continue
                else:
                    # 형태소 불일치 + 약어 스코어 극단적 저조
                    # 🆕 FIX: 작가명→대표작 매핑이 snippet_analyzer로 검증된 경우 스킵
                    # 예: "뇌조"(작가) → "미국 레트로 소설가가 되었다"(대표작)
                    #     abbreviation_match_score = 0.00 (당연 — 작가명≠작품약칭)
                    #     약어 가드가 "뇌석 조각상"(원신) score=1.00으로 교정하는 것을 방지
                    # 🛡️ 단, 다른 decoded_term도 작가명이면 작가 비교 글 → 스킵하지 않음
                    _snippet_validated_author = False
                    _sh_local = getattr(ctx, 'snippet_hints', None) or {}
                    for _ah_src in ('abbreviation_hints', 'abbreviation_mappings'):
                        for _ah_item in (_sh_local.get(_ah_src) or []):
                            if isinstance(_ah_item, dict):
                                _ah_abbrev = (_ah_item.get('abbrev') or _ah_item.get('abbr') or '').strip()
                                _ah_full = (_ah_item.get('full') or '').strip()
                                if (_ah_abbrev == original and _ah_full
                                        and _ah_full == _cur_title_for_skip):
                                    _snippet_validated_author = True
                                    break
                        if _snippet_validated_author:
                            break

                    # 🛡️ 다중 작가 감지 시 스킵 금지
                    # "개돌도 후반 말아먹긴했지만 목마도 써라" → 작가 비교 글
                    # 작가 2명 이상이면 특정 대표작에 매칭하면 FP
                    if _snippet_validated_author:
                        _other_author_count = 0
                        for _other_t in decoded_terms:
                            if _other_t is term:
                                continue
                            if _other_t.get("is_author_name"):
                                _other_author_count += 1
                            else:
                                _oi = _other_t.get("interpretations", [])
                                if any(
                                    isinstance(i, dict)
                                    and i.get("type") == "author_name"
                                    and i.get("context_fit") in ("high", "medium")
                                    for i in _oi
                                ):
                                    _other_author_count += 1
                        if _other_author_count >= 1:
                            _snippet_validated_author = False
                            print(
                                f"[{_ts()}][{self.emoji}] ⚠️ 작가명→대표작 매핑이지만 "
                                f"다중 작가 감지({_other_author_count + 1}명) → "
                                f"'{original}' 약어 가드 진행 (작가 비교 글 가능성)",
                                file=sys.stderr,
                            )

                    if _snippet_validated_author:
                        print(
                            f"[{_ts()}][{self.emoji}] ℹ️ 작가명→대표작 매핑 검증됨: "
                            f"'{original}' → '{_cur_title_for_skip}' "
                            f"(snippet_analyzer 확인, 약어 가드 스킵)",
                            file=sys.stderr,
                        )
                        continue

                    # 🆕 FIX: interpretations에 work_abbreviation 해석이 없으면 순수 작가명
                    # → 약어 비교 자체가 무의미 (작가명은 작품 제목의 음절 축약이 아님)
                    _has_work_abbr_interp = any(
                        (i.get("type") in (
                            "work_abbreviation", "novel_abbreviation",
                            "abbreviation", "title_abbreviation",
                        ) and i.get("context_fit") in ("high", "medium"))
                        for i in _interps
                        if isinstance(i, dict)
                    )
                    if not _has_work_abbr_interp:
                        print(
                            f"[{_ts()}][{self.emoji}] ℹ️ 순수 작가명 해석 (work_abbreviation 없음): "
                            f"'{original}' → 약어 가드 스킵",
                            file=sys.stderr,
                        )
                        continue

                    # 경쟁 work_abbreviation 해석 존재 → 교정 기회 유지
                    print(
                        f"[{_ts()}][{self.emoji}] ⚠️ 작가명+작품약칭 혼합 해석: "
                        f"'{original}' → '{_cur_title_for_skip}' (score={_abbr_score_for_skip:.2f}, "
                        f"morpheme_ok={_morpheme_ok_for_skip}) → 약어 가드 진행 (교정 기회 유지)",
                        file=sys.stderr,
                    )

            # 🆕 캐릭터명은 약어 가드 대상이 아님 — 스킵
            # Decoder가 anchor_type="character_mention"으로 식별한 term은
            # 제목 약어가 아니라 캐릭터 이름이므로 abbreviation_match_score 검증 불필요
            grounding_info = term.get("grounding") or {}
            _primary_interps_for_skip = term.get("interpretations") or []
            _primary_type_for_skip = ""
            if _primary_interps_for_skip and isinstance(_primary_interps_for_skip[0], dict):
                _primary_type_for_skip = str(_primary_interps_for_skip[0].get("type") or "")
            _work_interp_types_for_skip = {
                "novel_title", "work_abbreviation", "abbreviation",
                "title_abbreviation", "novel_abbreviation",
            }
            is_character_term = (
                grounding_info.get("anchor_type") == "character_mention"
                or (len(original) <= 3 and any(
                    (term.get("original") or "") in (c or "")
                    for c in (ctx.expert_outputs.get("gatekeeper") or {}).get("detected_entities", {}).get("possible_characters", [])
                ))
            )
            _gk_possible_titles_for_skip = (
                ((ctx.expert_outputs.get("gatekeeper") or {}).get("detected_entities") or {}).get("possible_titles", [])
                if ctx else []
            )
            _original_base_for_skip = _strip_korean_particles(original) or original
            _original_base_norm_for_skip = _normalize_alnum_kor_cached(_original_base_for_skip)
            _is_title_candidate_for_skip = any(
                _normalize_alnum_kor_cached(str(_cand or "")) in {
                    _normalize_alnum_kor_cached(original),
                    _original_base_norm_for_skip,
                }
                or _normalize_alnum_kor_cached(_strip_korean_particles(str(_cand or ""))) in {
                    _normalize_alnum_kor_cached(original),
                    _original_base_norm_for_skip,
                }
                for _cand in (_gk_possible_titles_for_skip or [])
            )
            if is_character_term and _primary_type_for_skip in _work_interp_types_for_skip:
                is_character_term = False
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ 캐릭터 앵커 우회 취소: "
                    f"'{original}'은 anchor_type=character_mention 이지만 "
                    f"primary_interpretation={_primary_type_for_skip} → 약어 가드 정상 진행",
                    file=sys.stderr,
                )
            elif is_character_term and _is_title_candidate_for_skip and self._is_low_specificity_mapping_abbrev(original):
                is_character_term = False
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ 캐릭터 앵커 우회 취소: "
                    f"'{original}'은 Gatekeeper title 후보이자 저특이 약칭 → 약어 가드 정상 진행",
                    file=sys.stderr,
                )
            elif (
                is_character_term
                and _original_base_norm_for_skip
                and _original_base_norm_for_skip != _normalize_alnum_kor_cached(original)
                and self._is_low_specificity_mapping_abbrev(_original_base_for_skip)
            ):
                is_character_term = False
                print(
                    f"[{_ts()}][{self.emoji}] ⚠️ 캐릭터 앵커 우회 취소: "
                    f"'{original}'은 조사 제거형 '{_original_base_for_skip}' 기준 저특이 약칭 → 약어 가드 정상 진행",
                    file=sys.stderr,
                )
            # 🆕 검색 증거 기반 일반 어휘 필터 (Generic):
            # Gatekeeper가 캐릭터명으로 분류 했더라도, 검색 결과의 참고 사이트
            # (namu.wiki 등)에서 해당 용어가 감탄사/대명사 등 일반 어휘로
            # 분류되면 캐릭터 바이패스를 취소하고 약어 가드를 정상 진행.
            if is_character_term:
                _common_word_cat = self._detect_common_word_from_search(
                    original, search_results, ctx=ctx,
                )
                if _common_word_cat:
                    is_character_term = False
                    print(
                        f"[{_ts()}][{self.emoji}] 🔤 캐릭터→일반어휘 강등: "
                        f"'{original}'은 검색 증거상 '{_common_word_cat}'로 분류됨 "
                        f"→ 약어 가드 정상 진행",
                        file=sys.stderr,
                    )
            if is_character_term:
                # 🆕 Phase34.5: 커뮤니티 글제목 verbatim 오인 방어
                # anchor_type=character_mention이라도 약어가 제목에 그대로(verbatim) 포함되면
                # LLM이 커뮤니티 글제목을 소설 제목으로 오인한 것
                # → Rescue로 정식 제목 복원 시도
                _cm_match = term.get("best_match") or {}
                _cm_title = _cm_match.get("title")
                _cm_needs_rescue = False
                if _cm_title and len(original) >= 3:
                    # 약어가 제목에 그대로 포함되는지 확인 (verbatim 패턴)
                    _cm_orig_clean = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', original).lower()
                    _cm_title_clean = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', _cm_title).lower()
                    if _cm_orig_clean and _cm_orig_clean in _cm_title_clean and _cm_orig_clean != _cm_title_clean:
                        _cm_needs_rescue = True
                        _cm_score = abbreviation_match_score(original, _cm_title)
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 캐릭터명 '{original}' "
                            f"verbatim 제목 감지: '{_cm_title}' (score={_cm_score:.2f}) "
                            f"→ Rescue 시도",
                            file=sys.stderr,
                        )
                        rescue_title, rescue_score, rescue_src = self._rescue_null_title(
                            original, term, title_pool, all_search_titles,
                            search_results, ctx,
                        )
                        if rescue_title and rescue_score >= 0.75:
                            _cm_match["title"] = rescue_title
                            _cm_match["confidence"] = "medium"
                            # candidates에도 추가
                            cands = term.get("candidates") or []
                            cands.insert(0, {
                                "official_novel_title": rescue_title,
                                "url": None,
                                "platform": rescue_src,
                                "decode_logic": f"verbatim rescue: {_cm_score:.2f} → {rescue_score:.2f}",
                                "morphological_score": rescue_score,
                                "search_evidence": f"rescue from {rescue_src}",
                            })
                            term["candidates"] = cands
                            changed = True
                            print(
                                f"[{_ts()}][{self.emoji}] 🚀 Verbatim→Rescue 교정: "
                                f"'{original}' → '{rescue_title}' "
                                f"(score={rescue_score:.2f}, src={rescue_src})",
                                file=sys.stderr,
                            )
                            # code_level_hints 저장
                            if ctx:
                                if not hasattr(ctx, 'code_level_hints'):
                                    ctx.code_level_hints = []
                                ctx.code_level_hints.append({
                                    "type": "verbatim_rescue",
                                    "original_term": original,
                                    "corrected_title": rescue_title,
                                    "abbreviation_score": round(rescue_score, 2),
                                    "source": rescue_src or "search_pool",
                                    "reasoning": f"LLM이 커뮤니티 글제목 '{_cm_title}'을 반환했으나 verbatim 매칭(score={_cm_score:.2f})이므로 약어 rescue에서 '{rescue_title}'(score={rescue_score:.2f})로 교정",
                                })
                        else:
                            print(
                                f"[{_ts()}][{self.emoji}] ℹ️ Verbatim rescue 실패: "
                                f"'{original}' (best rescue={rescue_title}, "
                                f"score={rescue_score:.2f})",
                                file=sys.stderr,
                            )
                if not _cm_needs_rescue:
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
            current_score = max(
                abbreviation_match_score(original, current_title),
                _leading_jamo_title_direct_score(original, current_title),
            )

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
                if current_score < 0.2:
                    title_morphemes = []
                    for m in morphemes:
                        if m in title_norm or m in current_title:
                            title_morphemes.append(m)
                            continue
                        _m_score = max(
                            abbreviation_match_score(m, current_title),
                            _leading_jamo_title_direct_score(m, current_title),
                        )
                        if _m_score >= 0.65:
                            title_morphemes.append(m)
                    non_title_morphemes = [m for m in morphemes if m not in title_morphemes]
                    if title_morphemes and non_title_morphemes:
                        # 제목 부분 morpheme를 합쳐서 effective_original 생성
                        effective_abbr = "".join(title_morphemes)
                        comp_score = max(
                            abbreviation_match_score(effective_abbr, current_title),
                            _leading_jamo_title_direct_score(effective_abbr, current_title),
                        )
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
                                pscore = max(
                                    abbreviation_match_score(part_clean, current_title),
                                    _leading_jamo_title_direct_score(part_clean, current_title),
                                )
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
                        stripped_score = max(
                            abbreviation_match_score(stripped, current_title),
                            _leading_jamo_title_direct_score(stripped, current_title),
                        )
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
                                trim_score = max(
                                    abbreviation_match_score(trimmed, current_title),
                                    _leading_jamo_title_direct_score(trimmed, current_title),
                                )
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

            # 🆕 FIX: 약어와 제목이 정규화 기준으로 동일한 경우(예: "광마회귀"→"광마회귀"),
            # abbreviation_match_score의 verbatim 차단(0.00)로 인한 오강등을 방지한다.
            # 단, 제목 앵커가 있거나 공식 검색 제목으로 확인된 경우에만 적용한다.
            _orig_norm_exact = _normalize_text_keep_jamo(original)
            _title_norm_exact = _normalize_text_keep_jamo(str(current_title or ""))
            _anchor_type_exact = str(grounding_info.get("anchor_type") or "").lower()
            _has_title_anchor_exact = _anchor_type_exact in {
                "title_mention",
                "body_mention",
                "fulltext_mention",
            }
            _is_official_exact = any(
                _normalize_text_keep_jamo(str(o.get("title") or "")) == _title_norm_exact
                for o in all_search_titles
                if isinstance(o, dict)
            )
            _post_main_parts_exact = [str((ctx.post_data or {}).get("title") or "")]
            for _b_exact in ((ctx.post_data or {}).get("content_blocks", []) or []):
                if isinstance(_b_exact, dict):
                    _post_main_parts_exact.append(str(_b_exact.get("text") or ""))
                elif isinstance(_b_exact, str):
                    _post_main_parts_exact.append(_b_exact)
            _post_main_norm_exact = _normalize_text_keep_jamo(" ".join(_post_main_parts_exact))
            _title_in_post_main_exact = bool(_title_norm_exact and _title_norm_exact in _post_main_norm_exact)
            _comment_only_term_exact = False
            try:
                _gk_ctx_exact = ((ctx.expert_outputs.get("gatekeeper") or {}).get("context_clues") or {})
                _ctcs_exact = _gk_ctx_exact.get("comment_title_candidates") or []
                _comment_norms_exact = {
                    _normalize_text_keep_jamo(str(c))
                    for c in _ctcs_exact
                    if isinstance(c, str) and c.strip()
                }
                _comment_only_term_exact = bool(
                    _orig_norm_exact
                    and _orig_norm_exact in _comment_norms_exact
                    and _orig_norm_exact not in _post_main_norm_exact
                )
            except Exception:
                _comment_only_term_exact = False

            _same_string_guard_ok = (
                _orig_norm_exact
                and _title_norm_exact
                and _orig_norm_exact == _title_norm_exact
                and (
                    _is_official_exact
                    or _title_in_post_main_exact
                    or (_has_title_anchor_exact and not _comment_only_term_exact)
                )
            )

            if _same_string_guard_ok:
                _target_score_exact = 1.0 if (_is_official_exact or _title_in_post_main_exact) else 0.9
                if current_score < _target_score_exact:
                    _old_score_exact = current_score
                    current_score = _target_score_exact
                    print(
                        f"[{_ts()}][{self.emoji}] 🔒 동일문자열 예외 가드: "
                        f"'{original}' → '{current_title}' "
                        f"(score {_old_score_exact:.2f}→{_target_score_exact:.2f}, "
                        f"anchor={_anchor_type_exact or 'none'}, official={_is_official_exact}, "
                        f"post_main={_title_in_post_main_exact}, comment_only={_comment_only_term_exact})",
                        file=sys.stderr,
                    )
                morpheme_ok = True

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

            def _official_title_soft_matches(target_title: str, official_title: str) -> bool:
                target_norm = _normalize_text_keep_jamo(str(target_title or ""))
                official_raw = str(official_title or "").strip()
                official_norm = _normalize_text_keep_jamo(official_raw)
                if not target_norm or not official_norm:
                    return False
                if target_norm == official_norm:
                    return True
                split_parts = [official_raw]
                for sep in (" - ", " | ", " / ", " · ", " :: "):
                    if sep in official_raw:
                        split_parts.extend(p.strip() for p in official_raw.split(sep) if p.strip())
                seen_parts: set[str] = set()
                for part in split_parts:
                    part_norm = _normalize_text_keep_jamo(part)
                    if not part_norm or part_norm in seen_parts:
                        continue
                    seen_parts.add(part_norm)
                    if part_norm == target_norm:
                        return True
                platformish = any(
                    token in official_raw.lower()
                    for token in (
                        "카카오페이지",
                        "novelpia",
                        "노벨피아",
                        "문피아",
                        "series",
                        "시리즈",
                        "나무위키",
                        "thewiki",
                    )
                )
                if platformish and official_norm.startswith(target_norm):
                    tail = official_norm[len(target_norm):]
                    if tail and any(
                        token in tail
                        for token in (
                            "웹소설",
                            "카카오페이지",
                            "노벨피아",
                            "문피아",
                            "시리즈",
                            "나무위키",
                            "thewiki",
                        )
                    ):
                        return True
                return False

            for candidate in title_pool:
                if candidate == current_title:
                    continue
                # 후보 제목이 너무 짧거나 길면 스킵
                if len(candidate) < 3 or len(candidate) > 40:
                    continue

                # 🚫 커뮤니티 게시글 제목은 공식 제목 후보에서 제외
                if candidate in community_titles:
                    continue

                score = max(
                    abbreviation_match_score(effective_original, candidate),
                    _leading_jamo_title_direct_score(effective_original, candidate),
                )

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
                        if _official_title_soft_matches(candidate, str(official.get("title") or "")):
                            best_alt_source = f"platform:{official.get('platform', '?')}"
                            break

            # ── 3단계: 교체 또는 confidence 하향 ──
            # 🔧 현재 제목이 공식 플랫폼 출처면 교정 기준 강화
            current_from_official = any(
                _official_title_soft_matches(current_title, str(official.get("title") or ""))
                for official in all_search_titles
            )
            current_official_support_count = sum(
                1 for official in all_search_titles
                if _official_title_soft_matches(current_title, str(official.get("title") or ""))
            )
            best_alt_official_support_count = sum(
                1 for official in all_search_titles
                if best_alt_title and _official_title_soft_matches(best_alt_title, str(official.get("title") or ""))
            ) if best_alt_title else 0
            best_alt_from_official = bool(
                isinstance(best_alt_source, str) and best_alt_source.startswith("platform:")
            )
            current_has_official_keyword_support = False
            current_wiki_support_count = 0
            current_nonplatform_support_count = 0
            best_alt_wiki_support_count = 0
            best_alt_nonplatform_support_count = 0
            if effective_original:
                _eff_norm = _normalize_text_keep_jamo(str(effective_original or ""))
                _cur_norm = _normalize_text_keep_jamo(str(current_title or ""))
                if _eff_norm and _cur_norm:
                    for sr in search_results:
                        sr_url = str(sr.get("url", "") or "")
                        if not sr_url:
                            continue
                        sr_title = str(sr.get("title", "") or "")
                        sr_content = str(sr.get("content", "") or "")
                        _sr_title_norm = _normalize_text_keep_jamo(sr_title)
                        _sr_content_norm = _normalize_text_keep_jamo(sr_content)
                        if _cur_norm and (_cur_norm in _sr_title_norm or _cur_norm in _sr_content_norm):
                            sr_url_lower = sr_url.lower()
                            if "namu.wiki" in sr_url_lower or "thewiki.kr" in sr_url_lower:
                                current_wiki_support_count += 1
                            elif not self._is_novel_platform_url(sr_url):
                                current_nonplatform_support_count += 1
                        if current_official_support_count < 1:
                            continue
                        if not self._is_novel_platform_url(sr_url):
                            continue
                        if _cur_norm and _cur_norm not in _sr_title_norm and _cur_norm not in _sr_content_norm:
                            continue
                        if _eff_norm in _sr_title_norm or _eff_norm in _sr_content_norm:
                            current_has_official_keyword_support = True
                            break
            if best_alt_title:
                _alt_norm = _normalize_text_keep_jamo(str(best_alt_title or ""))
                if _alt_norm:
                    for sr in search_results:
                        sr_url = str(sr.get("url", "") or "")
                        if not sr_url:
                            continue
                        sr_title = str(sr.get("title", "") or "")
                        sr_content = str(sr.get("content", "") or "")
                        _sr_title_norm = _normalize_text_keep_jamo(sr_title)
                        _sr_content_norm = _normalize_text_keep_jamo(sr_content)
                        if _alt_norm not in _sr_title_norm and _alt_norm not in _sr_content_norm:
                            continue
                        sr_url_lower = sr_url.lower()
                        if "namu.wiki" in sr_url_lower or "thewiki.kr" in sr_url_lower:
                            best_alt_wiki_support_count += 1
                        elif not self._is_novel_platform_url(sr_url):
                            best_alt_nonplatform_support_count += 1
            current_has_structural_alias_support = bool(
                (current_from_official or current_official_support_count > 0 or current_wiki_support_count > 0)
                and morpheme_ok
                and (
                    current_has_official_keyword_support
                    or current_score >= 0.25
                    or _same_string_guard_ok
                )
            )
            current_support_strength = (
                (current_official_support_count * 3.0)
                + (current_wiki_support_count * 2.0)
                + (current_nonplatform_support_count * 1.0)
                + (2.0 if current_has_official_keyword_support else 0.0)
            )
            best_alt_support_strength = (
                (best_alt_official_support_count * 3.0)
                + (best_alt_wiki_support_count * 2.0)
                + (best_alt_nonplatform_support_count * 1.0)
                + (1.0 if best_alt_from_official else 0.0)
            )
            replace_margin = 0.30 if current_from_official else 0.15

            def _looks_sentence_like_title_local(text: str) -> bool:
                if not text or not isinstance(text, str):
                    return False
                t = re.sub(r"\s+", " ", text).strip()
                if not t:
                    return False
                token_count = len(re.findall(r"[가-힣A-Za-z0-9]+", t))
                has_clause_connector = bool(
                    re.search(r"(는데|면서|해서|하며|라고|이라는|같은|처럼|듯이)", t)
                )
                has_meta_prefix = bool(
                    re.match(r"^(제목|내용|스토리|줄거리)\s*(그대로|요약)", t)
                )
                return bool(
                    token_count >= 8 and (has_clause_connector or len(t) >= 30 or has_meta_prefix)
                )

            _best_alt_derivativeish = bool(
                best_alt_title
                and (
                    self._is_derivative_or_variant_title(current_title, best_alt_title)
                    or _looks_sentence_like_title_local(best_alt_title)
                    or bool(
                        re.search(
                            r"[\[\]<>]|(?:\b|[가-힣])x(?:\b|[가-힣])|크로스오버|세계관|팬픽|팬아트|리메이크|외전|패러디",
                            str(best_alt_title or ""),
                            re.IGNORECASE,
                        )
                    )
                )
            )

            if (
                best_alt_title
                and current_from_official
                and (not best_alt_from_official)
                and current_has_official_keyword_support
                and (not has_explicit_alias)
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ 공식제목 유지: "
                    f"'{current_title}' ←/→ '{best_alt_title}' "
                    f"(official_keyword_support=True, alt_source={best_alt_source or 'search_pool'})",
                    file=sys.stderr,
                )
                best_alt_title = None
            elif (
                best_alt_title
                and current_has_structural_alias_support
                and (not best_alt_from_official)
                and (best_alt_source or "search_pool") == "search_pool"
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ 공식/위키 약칭 제목 유지: "
                    f"'{current_title}' ←/→ '{best_alt_title}' "
                    f"(official_support_count={current_official_support_count}, "
                    f"score={current_score:.2f}, morpheme_ok={morpheme_ok}, "
                    f"alt_source={best_alt_source or 'search_pool'})",
                    file=sys.stderr,
                )
                best_alt_title = None
            elif (
                best_alt_title
                and _best_alt_derivativeish
                and current_has_structural_alias_support
                and current_official_support_count >= 1
                and current_wiki_support_count >= 1
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ canonical title 유지(파생작 교정 차단): "
                    f"'{current_title}' ←/→ '{best_alt_title}' "
                    f"(current_official={current_official_support_count}, "
                    f"current_wiki={current_wiki_support_count}, "
                    f"alt_source={best_alt_source or 'search_pool'}, "
                    f"alt_derivativeish=True)",
                    file=sys.stderr,
                )
                best_alt_title = None
            elif (
                best_alt_title
                and current_has_structural_alias_support
                and self._is_derivative_or_variant_title(current_title, best_alt_title)
                and (
                    current_official_support_count >= max(1, best_alt_official_support_count)
                    or current_wiki_support_count > best_alt_wiki_support_count
                    or current_nonplatform_support_count > best_alt_nonplatform_support_count
                    or (
                        current_official_support_count >= 1
                        and current_wiki_support_count >= 1
                        and best_alt_official_support_count == 0
                        and best_alt_wiki_support_count == 0
                    )
                )
                and (
                    current_has_official_keyword_support
                    or current_official_support_count >= 2
                    or current_wiki_support_count >= 1
                    or current_nonplatform_support_count >= 2
                )
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ 원작 canonical 제목 유지: "
                    f"'{current_title}' ←/→ '{best_alt_title}' "
                    f"(current_official={current_official_support_count}, "
                    f"alt_official={best_alt_official_support_count}, "
                    f"current_wiki={current_wiki_support_count}, "
                    f"alt_wiki={best_alt_wiki_support_count}, "
                    f"current_nonplatform={current_nonplatform_support_count}, "
                    f"alt_nonplatform={best_alt_nonplatform_support_count}, "
                    f"alt_source={best_alt_source or 'search_pool'}, "
                    f"alt_derivative=True)",
                    file=sys.stderr,
                )
                best_alt_title = None
            elif (
                best_alt_title
                and current_has_structural_alias_support
                and current_support_strength >= best_alt_support_strength + 2.0
                and (
                    current_official_support_count >= 1
                    and (
                        current_wiki_support_count >= 1
                        or current_nonplatform_support_count >= 2
                        or current_has_official_keyword_support
                    )
                )
                and (
                    best_alt_official_support_count < current_official_support_count
                    or best_alt_wiki_support_count < current_wiki_support_count
                    or best_alt_nonplatform_support_count < current_nonplatform_support_count
                    or not best_alt_from_official
                )
            ):
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ canonical support 우세 유지: "
                    f"'{current_title}' ←/→ '{best_alt_title}' "
                    f"(current_strength={current_support_strength:.1f}, "
                    f"alt_strength={best_alt_support_strength:.1f}, "
                    f"current_official={current_official_support_count}, "
                    f"alt_official={best_alt_official_support_count}, "
                    f"current_wiki={current_wiki_support_count}, "
                    f"alt_wiki={best_alt_wiki_support_count}, "
                    f"current_nonplatform={current_nonplatform_support_count}, "
                    f"alt_nonplatform={best_alt_nonplatform_support_count}, "
                    f"alt_source={best_alt_source or 'search_pool'})",
                    file=sys.stderr,
                )
                best_alt_title = None
            if best_alt_title and best_alt_score >= 0.7 and best_alt_score > current_score + replace_margin:
                old_title = current_title
                best_match["title"] = best_alt_title
                if str(best_match.get("url") or "").strip():
                    # 제목만 교체되면 기존 URL은 다른 작품을 가리킬 수 있으므로 초기화한다.
                    best_match["url"] = None

                # candidates도 업데이트
                for cand in term.get("candidates", []):
                    if not isinstance(cand, dict):
                        continue
                    if cand.get("official_novel_title") == old_title:
                        cand["official_novel_title"] = best_alt_title
                        if str(cand.get("url") or "").strip():
                            cand["url"] = None

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
                effective_score = (
                    max(
                        abbreviation_match_score(effective_original, current_title),
                        _leading_jamo_title_direct_score(effective_original, current_title),
                    )
                    if effective_original != original else current_score
                )
                if effective_score >= 0.5 or current_has_official_keyword_support:
                    print(
                        f"[{_ts()}][{self.emoji}] ℹ️ 약어 가드 우회: "
                        f"original '{original}' score={current_score:.2f} < 0.2이지만, "
                        f"effective '{effective_original}' score={effective_score:.2f}, "
                        f"official_keyword_support={current_has_official_keyword_support} "
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
        # ⚠️ 소설 약칭과 혼동되는 용어(아생갤 등)는 KNOWN_ABBREVIATIONS로 이동
        _COMMUNITY_SLANG = {
            "파딱", "완장", "고닉", "장붕이", "장붕", "장갤", "고로시", "탈갤",
            "뿜명어", "설레발", "무개념", "악플러", "겹채", "닭판",
            "반바기", "본덕", "다링", "찬모리",
            "웹연갤", "노벨피아", "문피아", "카케페", "시리즈",
            "장판갤", "로판갤", "무협갤", "판갤",
            "노피아",  # 노벨피아 약칭 (플랫폼명, 소설명 아님)
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

        known_title = KNOWN_ABBREVIATIONS.get(original_clean)

        def _has_known_abbreviation_evidence(_known_title: str | None) -> bool:
            if not _known_title:
                return False
            _known_norm = _normalize_alnum_kor_cached(_known_title)
            if not _known_norm:
                return False
            for _ot in official_titles or []:
                if not isinstance(_ot, dict):
                    continue
                if _normalize_alnum_kor_cached(_ot.get("title", "")) == _known_norm:
                    return True
            for _sr in search_results or []:
                if not isinstance(_sr, dict):
                    continue
                _sr_text = " ".join([
                    str(_sr.get("title") or ""),
                    str(_sr.get("content") or _sr.get("snippet") or ""),
                ])
                if _known_norm in _normalize_alnum_kor_cached(_sr_text):
                    return True
            return False

        known_abbreviation_has_evidence = _has_known_abbreviation_evidence(known_title)

        # 🆕 P1-2: 초성 비속어가 포함된 원본은 Rescue 대상에서 제외
        # "이ㅅㄲ" = "이 새끼" 같은 욕설을 작품 약어로 오해석하는 것을 방지
        _has_profanity, _profanity_expansion = contains_chosung_profanity(original_clean)
        if _has_profanity:
            print(
                f"[{_ts()}][{self.emoji}] 🚫 Rescue 스킵: "
                f"'{original}' 에 초성 비속어 포함 ('{_profanity_expansion}')",
                file=sys.stderr,
            )
            return (None, 0.0, None)

        # ── 🆕 LLM 의도(Intent) 기반 Rescue 스킵 ──
        # LLM이 structured output에서 "이건 제목이 아님"을 명시적으로 판단한 경우,
        # 코드가 그 결론을 뒤집지 않는다. 블랙리스트 없이 LLM의 분류 신호를 종합.
        #
        # 판단 신호:
        #   (A) interpretations[].type 이 모두 비-제목 유형인가
        #   (B) best_match.confidence 가 "none"인가
        #   (C) best_match.reason 에 "제목이 아닌" 등 부정 표현이 있는가
        #   (D) best_match.is_grounded 가 false인가
        # → 2개 이상 신호가 겹치면 LLM이 의도적으로 비-제목 판단한 것

        best_match = term.get("best_match") or {}

        _TITLE_LIKE_TYPES = {
            "title", "novel_title", "abbreviation", "work_abbreviation",
            "novel_abbreviation", "series_name", "book_title", "work_title",
            "manhwa_title", "webtoon_title", "webnovel_title",
        }
        _NON_TITLE_TYPES = {
            "setting_term", "plot_element", "plot_reference",
            "slang", "general_term", "cultural_reference",
            "cultural_term", "idiom", "expression", "reaction",
            "meme", "joke", "community_slang", "internet_slang",
            "general_expression", "colloquial", "proverb",
            "worldbuilding", "character_trait", "genre_term",
            "trope", "emotion", "onomatopoeia", "interjection",
        }

        interps = term.get("interpretations") or []
        interp_types = {
            (ip.get("type") or "").lower().replace(" ", "_")
            for ip in interps if isinstance(ip, dict)
        }
        # (A) 모든 interpretation이 비-제목 유형인가?
        has_title_interp = bool(interp_types & _TITLE_LIKE_TYPES)
        all_non_title = bool(interp_types) and interp_types <= _NON_TITLE_TYPES

        # (B) confidence가 "none"인가?
        bm_conf = (best_match.get("confidence") or "").lower()
        conf_none = bm_conf in ("none", "")

        # (C) reason에 "제목이 아닌" 등 부정 표현이 있는가?
        bm_reason = (best_match.get("reason") or "").lower()
        _NOT_TITLE_SIGNALS = (
            "제목이 아닌", "제목이 아님", "작품 제목이 아닌", "작품 제목이 아님",
            "작품명이 아닌", "작품명이 아님", "제목은 아님", "제목은 아닌",
            "특정 작품 제목은 아님", "특정 작품 제목이 아님", "특정 작품이 아닌",
            "작품 제목으로 보이지 않", "제목으로 보이지 않",
            "일반적인 표현", "관용적 표현", "일상 용어", "문화적 표현",
            "not a title", "not a novel", "not a work",
        )
        reason_says_not_title = any(sig in bm_reason for sig in _NOT_TITLE_SIGNALS)

        # (D) is_grounded가 false인가?
        not_grounded = best_match.get("is_grounded") is False

        # 종합 판단: 2개 이상 신호가 겹치면 LLM이 의도적으로 비-제목 판단한 것
        llm_intent_signals = sum([
            all_non_title and not has_title_interp,  # (A)
            conf_none,                                # (B)
            reason_says_not_title,                    # (C)
            not_grounded,                             # (D)
        ])
        # 등록 약칭도 검색/공식 근거가 없으면 LLM의 비-제목 판단을 뒤집지 않는다.
        is_verified_known = bool(known_title and known_abbreviation_has_evidence)

        if llm_intent_signals >= 2 and not is_verified_known:
            signals_detail = []
            if all_non_title:
                signals_detail.append(f"interp_types={interp_types}")
            if conf_none:
                signals_detail.append(f"confidence={bm_conf or 'none'}")
            if reason_says_not_title:
                signals_detail.append("reason='비제목'")
            if not_grounded:
                signals_detail.append("is_grounded=false")
            print(
                f"[{_ts()}][{self.emoji}] 🧠 Rescue 스킵 (LLM 의도 존중): "
                f"'{original}' — LLM이 비-제목으로 판단 "
                f"(signals={llm_intent_signals}/4: {', '.join(signals_detail)})",
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
            # 등록 약칭도 검색/공식 근거가 있어야 트로프 체크를 우회한다.
            if original_clean in _KNOWN_ABBREVIATIONS_PRECHECK and is_verified_known:
                print(
                    f"[{_ts()}][{self.emoji}] ✅ 트로프 체크 통과: "
                    f"'{original}'은 KNOWN_ABBREVIATIONS에 등록되고 독립 근거가 있음",
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
        if known_title:
            if known_abbreviation_has_evidence:
                print(
                    f"[{_ts()}][{self.emoji}] 📘 Known abbreviation: "
                    f"'{original}' → '{known_title}' (KNOWN_ABBREVIATIONS)",
                    file=sys.stderr,
                )
                return known_title, 0.95, "known_abbreviation"
            else:
                print(
                    f"[{_ts()}][{self.emoji}] 📘 Known abbreviation hint-only: "
                    f"'{original}' → '{known_title}' "
                    f"(검색/공식 근거 없음, rescue 후보 승격 안 함)",
                    file=sys.stderr,
                )

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
            score = max(
                abbreviation_match_score(original, candidate),
                _leading_jamo_title_direct_score(original, candidate),
            )
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
            score = max(
                abbreviation_match_score(original, candidate),
                _leading_jamo_title_direct_score(original, candidate),
            )
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
                        score = max(
                            abbreviation_match_score(original, candidate),
                            _leading_jamo_title_direct_score(original, candidate),
                        )
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
                        score = max(
                            abbreviation_match_score(original, candidate),
                            _leading_jamo_title_direct_score(original, candidate),
                        )
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
                            score = max(
                                abbreviation_match_score(abbr_from_morphemes, candidate),
                                _leading_jamo_title_direct_score(abbr_from_morphemes, candidate),
                            )
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
                                        score = max(
                                            abbreviation_match_score(abbr_from_morphemes, candidate),
                                            _leading_jamo_title_direct_score(abbr_from_morphemes, candidate),
                                        )
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
                                        score = max(
                                            abbreviation_match_score(abbr_from_morphemes, candidate),
                                            _leading_jamo_title_direct_score(abbr_from_morphemes, candidate),
                                        )
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

        # ── Pass 6: 다중 Verbatim 후보 맥락 재선별 (Generic) ──
        # 동일 약칭이 여러 소설 제목에 그대로(verbatim) 포함될 때,
        # 형태소 점수만으로는 올바른 작품을 고를 수 없음.
        # 게시글의 맥락 키워드(GK key_terms + 본문)와 각 후보의
        # 검색 증거(장르, 키워드)를 대조하여 맥락 적합도가 높은 후보를 승격.
        verbatim_candidates: list[tuple[str, float, str]] = []  # (title, score, source)
        for ot in official_titles:
            _vt = ot["title"]
            if len(_vt) < 4 or len(_vt) > 40:
                continue
            _vs = abbreviation_match_score(original, _vt)
            if 0.20 <= _vs <= 0.35:  # verbatim range
                verbatim_candidates.append((_vt, _vs, ot.get("platform", "")))
        for _vt in title_pool:
            if _vt in community_titles or len(_vt) < 4 or len(_vt) > 40:
                continue
            _vs = abbreviation_match_score(original, _vt)
            if 0.20 <= _vs <= 0.35:
                # 중복 제거 (같은 제목이 official_titles에도 있을 수 있음)
                if not any(_vt == vc[0] for vc in verbatim_candidates):
                    verbatim_candidates.append((_vt, _vs, "title_pool"))

        if len(verbatim_candidates) >= 2:
            # 맥락 키워드 풀 구성 (게시글 제목 + 본문 + GK key_terms)
            _post_data_ctx = getattr(ctx, 'post_data', {}) or {}
            _ctx_title = (_post_data_ctx.get('title') or '')
            _ctx_body_parts: list[str] = []
            for _blk in _post_data_ctx.get('content_blocks', []) or []:
                if isinstance(_blk, dict) and _blk.get('text'):
                    _ctx_body_parts.append(_blk['text'])
                elif isinstance(_blk, str):
                    _ctx_body_parts.append(_blk)
            _ctx_body = ' '.join(_ctx_body_parts)

            _gk_out_ctx = (ctx.expert_outputs.get('gatekeeper') or {}) if ctx else {}
            _gk_key_terms_ctx = _gk_out_ctx.get('key_terms') or []

            _context_words: set[str] = set()
            for _kw in _gk_key_terms_ctx:
                if isinstance(_kw, str) and len(_kw) >= 2:
                    _context_words.add(_re.sub(r'[^\uac00-\ud7a3a-z0-9]', '', _kw.lower()))
            for _txt in [_ctx_title, _ctx_body]:
                for _w in _re.findall(r'[\uac00-\ud7a3]{2,}', _txt.lower()):
                    _context_words.add(_w)
            # 약어 자체/약어 내 개별 음절 제거 (모든 후보에 공통 → 변별력 없음)
            _orig_norm_ctx = _re.sub(r'[^\uac00-\ud7a3]', '', original).lower()
            _context_words.discard(_orig_norm_ctx)
            for _seg in _orig_norm_ctx:
                _context_words.discard(_seg)
            # 너무 일반적인 단어 제거
            _context_words -= {"살짝", "이거", "이건", "좀", "진짜", "ㅋㅋ", "ㅎㅎ"}

            if _context_words:
                _best_ctx_cand = None
                _best_ctx_score = 0.0
                _best_ctx_overlap: set[str] = set()

                for _vc_title, _vc_morph, _vc_src in verbatim_candidates:
                    # 후보 키워드 = 제목 자체 + 이 후보를 언급하는 검색 결과의 키워드
                    _cand_words: set[str] = set(
                        _re.findall(r'[\uac00-\ud7a3]{2,}', _vc_title.lower())
                    )
                    _vc_norm = _re.sub(r'[^\uac00-\ud7a3]', '', _vc_title).lower()
                    for _sr in search_results:
                        _sr_combined = (
                            ((_sr.get('title') or '') + ' '
                             + (_sr.get('content') or _sr.get('snippet') or ''))
                        ).lower()
                        if _vc_norm not in _sr_combined.replace(' ', ''):
                            continue
                        for _sw in _re.findall(r'[\uac00-\ud7a3]{2,}', _sr_combined):
                            _cand_words.add(_sw)
                    # 약어 자체 단어 제거
                    _cand_words.discard(_orig_norm_ctx)

                    _overlap = _context_words & _cand_words
                    _ctx_score = len(_overlap) / max(len(_context_words), 1)
                    if _ctx_score > _best_ctx_score:
                        _best_ctx_score = _ctx_score
                        _best_ctx_cand = (_vc_title, _vc_morph, _vc_src)
                        _best_ctx_overlap = _overlap

                # 맥락 적합도가 25% 이상이고, 현재 best보다 유리하면 승격
                if _best_ctx_cand and _best_ctx_score >= 0.25:
                    _boosted = min(0.50 + _best_ctx_score * 0.45, 0.90)
                    if _boosted > best_score or (
                        _boosted >= best_score and best_source
                        and best_source.startswith("title_")
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🎯 Verbatim 맥락 재선별: "
                            f"'{original}' → '{_best_ctx_cand[0]}' "
                            f"(context_fit={_best_ctx_score:.2f}, overlap={_best_ctx_overlap}, "
                            f"boosted={_boosted:.2f} > prev={best_score:.2f})",
                            file=sys.stderr,
                        )
                        best_title = _best_ctx_cand[0]
                        best_score = _boosted
                        best_source = f"verbatim_context({_best_ctx_cand[2]})"
                    else:
                        print(
                            f"[{_ts()}][{self.emoji}] ℹ️ Verbatim 맥락 후보: "
                            f"'{_best_ctx_cand[0]}' "
                            f"(ctx={_best_ctx_score:.2f}, boosted={_boosted:.2f}) "
                            f"≤ current({best_title}, {best_score:.2f})",
                            file=sys.stderr,
                        )

        # 🆕 BUG-6: rescue 후보의 출처 검증 — 소설 플랫폼 도메인이 아니면 거부
        _NOVEL_PLATFORM_DOMAINS = (
            "novelpia.com", "munpia.com", "series.naver.com", "page.kakao.com",
            "joara.com", "namu.wiki", "ridibooks.com", "bookoa.com",
            "novelupdates.com", "syosetu.com",
        )
        if best_title and best_source and best_source.startswith("title_"):
            # title_pool/title_suffix 출처 — 공식 플랫폼 근거 확인
            # (제목 매치뿐 아니라 content/페치 보강 본문 매치까지 허용)
            has_novel_platform_src = False
            _best_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', best_title).lower()

            # 🆕 Phase34.5: best_title에서 핵심 제목 추출 (커뮤니티 접미사 제거)
            # "'사이버펑크 속 드래곤이 되었다' 표지 - 웹툰/웹소설/만화"
            # → 핵심 norm = "사이버펑크속드래곤이되었다" (따옴표+접미어 제거)
            _core_norms: dict[str, str] = {}  # norm → clean_title
            # (1) 따옴표/괄호 내부 텍스트 추출
            _QUOTED_CORE_RE = _re.compile(
                r"[\u2018\u201C\u300E\u300C\u3010'\"]"
                r"([\uac00-\ud7a3A-Za-z0-9\s]{3,40}?)"
                r"[\u2019\u201D\u300F\u300D\u3011'\"]"
            )
            for _qm in _QUOTED_CORE_RE.finditer(best_title):
                _core = _qm.group(1).strip()
                if len(_core) >= 3:
                    _c_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', _core).lower()
                    if _c_norm and _c_norm != _best_norm:
                        _core_norms[_c_norm] = _core
            # (2) 커뮤니티 접미사 제거: 표지/후기/리뷰/감상 + "- 웹툰/웹소설/만화" 등
            _stripped = _re.sub(
                r"\s*[-\u2013\u2014]\s*(?:웹툰|웹소설|만화|에펨코리아|루리웹|아카라이브|fmkorea).*$",
                "", best_title, flags=_re.IGNORECASE,
            ).strip()
            _stripped = _re.sub(
                r"\s+(?:표지|후기|리뷰|감상문?|독후감|스포일러|스포)\s*$",
                "", _stripped,
            ).strip()
            # 바깥 따옴표 제거
            _stripped = _re.sub(
                r"^[\u2018\u201C\u300E\u300C\u3010'\"]|[\u2019\u201D\u300F\u300D\u3011'\"]$",
                "", _stripped,
            ).strip()
            if len(_stripped) >= 3:
                _s_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', _stripped).lower()
                if _s_norm and _s_norm != _best_norm and _s_norm not in _core_norms:
                    _core_norms[_s_norm] = _stripped

            # 모든 후보 norm 통합: 원문 + 핵심 추출분
            _all_norms: list[tuple[str, str | None]] = [(_best_norm, None)]
            for _cn, _ct in _core_norms.items():
                _all_norms.append((_cn, _ct))

            for sr in search_results:
                sr_url = str(sr.get("url", "") or "")
                if not any(d in sr_url.lower() for d in _NOVEL_PLATFORM_DOMAINS):
                    continue
                sr_title_raw = str(sr.get("title", "") or "").strip()
                sr_content_raw = str(sr.get("content") or sr.get("snippet") or "")
                sr_title_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', sr_title_raw).lower()
                sr_content_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', sr_content_raw).lower()
                for _cn, _ct in _all_norms:
                    if _cn and (_cn in sr_title_norm or _cn in sr_content_norm):
                        has_novel_platform_src = True
                        # 핵심 norm으로 매칭되었으면 best_title을 정제된 제목으로 갱신
                        if _ct is not None:
                            print(
                                f"[{_ts()}][{self.emoji}] ✅ Rescue 핵심제목 추출: "
                                f"'{best_title}' → '{_ct}' (platform={sr_url[:60]})",
                                file=sys.stderr,
                            )
                            best_title = _ct
                        break
                if has_novel_platform_src:
                    break
            # URL 페치 보강(structured_info/text_preview)까지 확인
            if not has_novel_platform_src and ctx is not None:
                for fe in (getattr(ctx, "fetched_page_info", []) or []):
                    if not isinstance(fe, dict):
                        continue
                    fe_url = str(fe.get("url", "") or "")
                    if not any(d in fe_url.lower() for d in _NOVEL_PLATFORM_DOMAINS):
                        continue
                    st = fe.get("structured_info") or {}
                    if not isinstance(st, dict):
                        st = {}
                    fe_blob = " ".join([
                        str(st.get("title") or ""),
                        str(st.get("page_title") or ""),
                        str(fe.get("text_preview") or ""),
                    ])
                    fe_norm = _re.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', fe_blob).lower()
                    for _cn, _ct in _all_norms:
                        if _cn and _cn in fe_norm:
                            has_novel_platform_src = True
                            if _ct is not None:
                                print(
                                    f"[{_ts()}][{self.emoji}] ✅ Rescue 핵심제목 추출(fetch): "
                                    f"'{best_title}' → '{_ct}' (url={fe_url[:60]})",
                                    file=sys.stderr,
                                )
                                best_title = _ct
                            break
                    if has_novel_platform_src:
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

        # 🆕 도메인 충돌 최종 가드:
        # rescue가 잡은 제목이 원 약어와 세계관 신호가 충돌하면 반환 금지.
        if best_title and _has_domain_conflict_for_mapping(original, best_title):
            print(
                f"[{_ts()}][{self.emoji}] 🚫 Rescue 거부(도메인 충돌): "
                f"'{original}' → '{best_title}' (source={best_source}, score={best_score:.2f})",
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
    )

    # 사이트명 오염 패턴 (제목 내부에서도 감지)
    _SITE_NOISE_PATTERNS = (
        "종토방:", "웹소설 종토방", "블라인드 |",
        "마이너 갤러리", "| 웹소설", "| 장르소설",
        "> 작품소개", "- 나무위키", "- 네이버 블로그",
        "- 리디", "- 예스24", "- 에펨코리아",
        "- 웹툰/웹소설",
    )

    # 커뮤니티/블로그 글 제목의 꼬리 표현 (작품 정식 제목이 아님)
    _REVIEW_SUFFIX_PATTERN = _re.compile(
        r"\s*(?:독후감|리뷰|후기|감상(?:문)?|스포(?:일러)?)\s*[.!?…]*\s*$"
    )

    _PLATFORM_BRANDING_NORMS = {
        "웹소설로꿈꾸는세상",
        "웹소설의유토피아",
        "노벨피아",
        "문피아",
        "카카오페이지",
        "네이버시리즈",
        "리디",
    }

    @classmethod
    def _is_platform_branding_title(cls, title: str) -> bool:
        if not isinstance(title, str):
            return False
        norm = _re.sub(r"[^\w가-힣]", "", title).lower()
        if norm in cls._PLATFORM_BRANDING_NORMS:
            return True
        raw = str(title).strip()
        # 비소설 이벤트/스포츠 명칭 오염 (대문자 약어 + ...시리즈/리그/컵)
        if _re.match(r"^[A-Z]{2,6}\s*[가-힣A-Za-z]{1,12}(?:시리즈|리그|컵)\s*$", raw):
            return True
        return False

    def _clean_search_result_title(self, raw_title: str) -> list[str]:
        """검색 결과 제목에서 사이트명/게시판 접두어를 정제하여 작품명 후보 목록 반환.
        
        "블라인드 | 웹소설 종토방: 오늘도요 - 즉사기 들고 무림에 떨어지다"
        → ["블라인드 | 웹소설 종토방: 오늘도요 - 즉사기 들고 무림에 떨어지다",
            "즉사기 들고 무림에 떨어지다",
            "오늘도요 - 즉사기 들고 무림에 떨어지다"]
        
        원본 제목은 항상 포함하고, 분리된 부분도 후보로 추가.
        """
        if self._is_platform_branding_title(raw_title):
            return []

        def _normalize_candidate(cand: str) -> str:
            c = str(cand or "").strip()
            if not c:
                return ""
            # 접두/접미 패턴 정제
            for pat in self._SITE_PREFIX_PATTERNS:
                c = pat.sub("", c).strip()
            # 커뮤니티 리뷰 꼬리 제거
            c = self._REVIEW_SUFFIX_PATTERN.sub("", c).strip()
            c = _re.sub(r"\s+", " ", c).strip(" -|:;,.[]()'\"")
            return c

        # 원본에 사이트명 오염이 있으면 원본을 결과에서 제외
        _has_site_noise = any(p in raw_title for p in self._SITE_NOISE_PATTERNS) or bool(
            self._REVIEW_SUFFIX_PATTERN.search(raw_title)
        )
        results: list[str] = [] if _has_site_noise else [raw_title]

        # 원본 전체에도 정제를 적용해 별도 후보로 추가
        normalized_raw = _normalize_candidate(raw_title)
        if (
            normalized_raw
            and not self._is_platform_branding_title(normalized_raw)
            and 3 <= len(normalized_raw) <= 50
            and normalized_raw not in results
        ):
            results.append(normalized_raw)

        # " - " 구분자로 분할 (가장 흔한 패턴)
        if " - " in raw_title:
            parts = raw_title.split(" - ")
            for part in parts:
                part = _normalize_candidate(part)
                # 너무 짧은 사이트명이나 카테고리만 있는 부분은 제외
                if len(part) < 3:
                    continue
                if self._is_platform_branding_title(part):
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
                part = _normalize_candidate(part)
                if len(part) < 3 or len(part) > 50:
                    continue
                if self._is_platform_branding_title(part):
                    continue
                if any(part.startswith(sp) for sp in self._KNOWN_SITE_PREFIXES):
                    continue
                if " - " in part:
                    # "웹소설 종토방: 오늘도요 - 작품명" → 마지막 " - " 이후
                    sub = _normalize_candidate(part.split(" - ")[-1].strip())
                    if self._is_platform_branding_title(sub):
                        continue
                    if sub and sub not in results and 3 <= len(sub) <= 50:
                        results.append(sub)
                if part not in results:
                    results.append(part)
        
        # ": " 구분자 (게시판: 제목)
        if ": " in raw_title:
            after_colon = _normalize_candidate(raw_title.split(": ")[-1].strip())
            if self._is_platform_branding_title(after_colon):
                return results
            if after_colon and after_colon not in results and 3 <= len(after_colon) <= 50:
                results.append(after_colon)

        # 🆕 Phase34.5: 인용 부호 내 제목 추출
        # "'사이버펑크 속 드래곤이 되었다' 표지 - 웹툰/웹소설/만화"
        # → "사이버펑크 속 드래곤이 되었다" (핵심 작품명)
        _QUOTED_TITLE_RE = _re.compile(
            r"[\u2018\u201C\u300E\u300C\u3010'\"]"   # 열림 따옴표
            r"([\uac00-\ud7a3A-Za-z0-9\s]{3,40}?)"   # 작품명 (한글/영문/숫자/공백)
            r"[\u2019\u201D\u300F\u300D\u3011'\"]"    # 닫힘 따옴표
        )
        for _qm in _QUOTED_TITLE_RE.finditer(raw_title):
            _quoted = _qm.group(1).strip()
            if (
                3 <= len(_quoted) <= 40
                and not self._is_platform_branding_title(_quoted)
                and _quoted not in results
            ):
                results.append(_quoted)

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
        def _sanitize_candidate(cand: str) -> str:
            c = _re.sub(r"\s+", " ", str(cand or "")).strip(" -|:;,.[]()'\"")
            if not c:
                return ""
            if len(c) < 3 or len(c) > 30:
                return ""
            # 설명문/리뷰 꼬리로 보이는 문장형 후보 차단
            if c.count(" ") >= 6:
                return ""
            if any(ch in c for ch in ("\n", "\t")):
                return ""
            sentence_like_tokens = (
                "작가", "리뷰", "후기", "독후감", "감상", "추천",
                "있는데", "보면", "합니다", "입니다", "했는데", "라고",
            )
            if any(tok in c for tok in sentence_like_tokens):
                # 단어 수가 충분히 짧은 경우(예: 제목 자체에 일반어 포함)는 허용
                if len(c.split()) > 4:
                    return ""
            return c

        # 패턴 1: "제목 그대로 X"
        for m in _re.finditer(r'제목\s*그대로\s+(.+?)(?:인|의|을|를|이|가|에)\s', text):
            cand = _sanitize_candidate(m.group(1))
            if cand:
                pool.append(cand)

        # 패턴 2: "문피아에 X란" / "X란 소설"
        for m in _re.finditer(
            r'(?:문피아|노벨피아|카카오페이지|네이버시리즈|조아라)(?:에)?\s+(.+?)'
            r'(?:란|라는|이란|이라는|\.)', text
        ):
            cand = _sanitize_candidate(m.group(1))
            if cand:
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
                cand = _sanitize_candidate(_re.sub(r'[.\s]+$', '', m.group(1)))
                if cand:
                    pool.append(cand)

        # 패턴 4: Kiwi 명사 연결 (후보 제목 내 명사 추출)
        nouns = kiwi_nouns(self._kiwi, text)
        for wlen in range(2, min(4, len(nouns) + 1)):
            for start in range(len(nouns) - wlen + 1):
                phrase = _sanitize_candidate(" ".join(nouns[start:start + wlen]))
                if phrase and 4 <= len(phrase) <= 25:
                    pool.append(phrase)

    def _score_resolved_mapping_candidate(
        self,
        ctx: Any,
        abbrev: str,
        full: str,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """약칭 주입 전, 후보 정식명을 검색/증거 버킷 기준으로 재평가한다."""
        abbrev = str(abbrev or "").strip()
        full = str(full or "").strip()
        source_list = [str(s or "").strip() for s in (sources or []) if str(s or "").strip()]
        abbr_norm = _normalize_alnum_kor_cached(abbrev)
        full_norm = _normalize_alnum_kor_cached(full)
        if not abbr_norm or not full_norm:
            return {
                "title": full,
                "score": -99.0,
                "abbr_score": 0.0,
                "source_bonus": 0.0,
                "official_title_hits": 0,
                "search_hit_count": 0,
                "alias_joint_hits": 0,
                "bucket_score": 0,
                "official_url_count": 0,
                "official_search_hits": 0,
                "wiki_search_hits": 0,
                "domain_conflict": False,
                "low_specific_abbrev": False,
                "sources": source_list,
            }

        source_bonus_map = {
            "known_abbreviation": 3.2,
            "url_fetch_platform": 2.6,
            "platform_title": 2.3,
            "llm_snippet": 2.1,
            "author_bridge": 1.8,
            "snippet_hint": 1.3,
            "unknown": 1.0,
        }

        def _candidate_bucket() -> Dict[str, List[Any]]:
            bucket = {}
            try:
                if hasattr(ctx, "get_candidate_evidence"):
                    bucket = ctx.get_candidate_evidence(full) or {}
            except Exception:
                bucket = {}
            if bucket:
                return bucket
            store = getattr(ctx, "candidate_evidence", None) or {}
            if not isinstance(store, dict):
                return {}
            for key, value in store.items():
                if _normalize_alnum_kor_cached(key) == full_norm and isinstance(value, dict):
                    return value
            return {}

        def _uniq_count(items: Any) -> int:
            if not isinstance(items, list):
                return 0
            seen = set()
            for item in items:
                key = str(item or "").strip()
                if key:
                    seen.add(key)
            return len(seen)

        def _has_strong_author_signal_for_abbrev() -> bool:
            snippet_hints = getattr(ctx, "snippet_hints", None) or {}
            for hint in (snippet_hints.get("author_hints") or []):
                if not isinstance(hint, dict):
                    continue
                name = str(hint.get("name") or "").strip()
                if _normalize_alnum_kor_cached(name) == abbr_norm:
                    return True

            llm_snippet = getattr(ctx, "llm_snippet_analysis", None) or {}
            for role_hint in (llm_snippet.get("entity_role_hints") or []):
                if not isinstance(role_hint, dict):
                    continue
                role = str(role_hint.get("role") or "").strip().lower()
                if role not in {"author_name", "author_alias"}:
                    continue
                confidence = str(role_hint.get("confidence") or "").strip().lower()
                if confidence not in {"high", "medium"}:
                    continue
                for raw in (
                    role_hint.get("term"),
                    role_hint.get("resolved_to"),
                    role_hint.get("author"),
                ):
                    if _normalize_alnum_kor_cached(str(raw or "").strip()) == abbr_norm:
                        return True

            gk_result = getattr(ctx, "gatekeeper_result", None) or {}
            gk_entities = (gk_result.get("detected_entities") or {}) if isinstance(gk_result, dict) else {}
            for author in (gk_entities.get("possible_authors") or []):
                if _normalize_alnum_kor_cached(str(author or "").strip()) == abbr_norm:
                    return True
            return False

        def _has_explicit_work_alias_signal() -> bool:
            llm_snippet = getattr(ctx, "llm_snippet_analysis", None) or {}
            for role_hint in (llm_snippet.get("entity_role_hints") or []):
                if not isinstance(role_hint, dict):
                    continue
                role = str(role_hint.get("role") or "").strip().lower()
                if role not in {"work_alias", "work_title_alias", "explicit_work_alias"}:
                    continue
                confidence = str(role_hint.get("confidence") or "").strip().lower()
                if confidence not in {"high", "medium"}:
                    continue
                term_norm = _normalize_alnum_kor_cached(str(role_hint.get("term") or "").strip())
                resolved_norm = _normalize_alnum_kor_cached(str(role_hint.get("resolved_to") or "").strip())
                if term_norm == abbr_norm and resolved_norm == full_norm:
                    return True
            return False

        def _collect_related_anchor_terms() -> Dict[str, Dict[str, str]]:
            gk_result = getattr(ctx, "gatekeeper_result", None) or {}
            if (not gk_result) and hasattr(ctx, "get_expert_output"):
                try:
                    from .orchestrator import ExpertType as _ExpertTypeDecoder

                    gk_result = ctx.get_expert_output(_ExpertTypeDecoder.GATEKEEPER) or {}
                except Exception:
                    gk_result = {}

            entities = (gk_result.get("detected_entities") or {}) if isinstance(gk_result, dict) else {}
            post_data = getattr(ctx, "post_data", None) or {}
            main_context_chunks: List[str] = []
            for block in post_data.get("content_blocks") or []:
                if isinstance(block, dict):
                    main_context_chunks.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    main_context_chunks.append(block)
            main_context_chunks.extend(
                str(comment or "").strip()
                for comment in (getattr(ctx, "comments", None) or [])
                if str(comment or "").strip()
            )
            main_context_norm = _normalize_alnum_kor_cached(" ".join(main_context_chunks))

            llm_snippet = getattr(ctx, "llm_snippet_analysis", None) or {}
            snippet_role_map: Dict[str, str] = {}
            for role_hint in (llm_snippet.get("entity_role_hints") or []):
                if not isinstance(role_hint, dict):
                    continue
                term_norm = _normalize_alnum_kor_cached(str(role_hint.get("term") or "").strip())
                if not term_norm:
                    continue
                snippet_role_map[term_norm] = str(role_hint.get("role") or "").strip().lower()

            raw_terms: List[tuple[str, str]] = []
            for role_name, source_terms in (
                ("author", entities.get("possible_authors") or []),
                ("character", entities.get("possible_characters") or []),
                ("key_term", gk_result.get("key_terms") or []),
            ):
                for term in source_terms:
                    term_raw = str(term or "").strip()
                    if term_raw:
                        raw_terms.append((term_raw, role_name))

            deduped: Dict[str, Dict[str, str]] = {}
            for term_raw, role_name in raw_terms:
                term_norm = _normalize_alnum_kor_cached(term_raw)
                if not term_norm or len(term_norm) < 2:
                    continue
                if term_norm == abbr_norm or term_norm == full_norm:
                    continue
                if term_norm in full_norm:
                    continue
                if term_norm not in main_context_norm:
                    continue
                if role_name == "key_term":
                    if self._is_low_specificity_mapping_abbrev(term_raw, full_title=term_raw):
                        continue
                    if snippet_role_map.get(term_norm) in {"genre_term", "community_meta"}:
                        continue
                if term_norm not in deduped:
                    deduped[term_norm] = {
                        "surface": term_raw,
                        "role": role_name,
                    }
            return deduped

        def _post_has_author_status_context() -> bool:
            post_data = getattr(ctx, "post_data", None) or {}
            chunks: List[str] = [str(post_data.get("title") or "")]
            for block in post_data.get("content_blocks") or []:
                if isinstance(block, dict):
                    chunks.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    chunks.append(block)
            chunks.extend(
                str(comment or "").strip()
                for comment in (getattr(ctx, "comments", None) or [])
                if str(comment or "").strip()
            )
            joined_norm = _normalize_alnum_kor_cached(" ".join(chunks))
            if not joined_norm:
                return False
            author_context_markers = (
                "현생",
                "유학",
                "바쁠",
                "바쁘",
                "휴재",
                "복귀",
                "연재",
                "완결",
                "orpg",
                "trpg",
                "안오는가",
                "안오",
                "늦",
            )
            return any(marker in joined_norm for marker in author_context_markers)

        official_titles = self._extract_official_titles_from_search(ctx) if ctx else []
        official_title_urls = set()
        for ot in official_titles or []:
            if not isinstance(ot, dict):
                continue
            ot_title = str(ot.get("title") or "").strip()
            if _normalize_alnum_kor_cached(ot_title) == full_norm:
                _url = str(ot.get("url") or "").strip()
                if _url:
                    official_title_urls.add(_url)
        official_title_hits = len(official_title_urls)

        search_hit_count = 0
        alias_joint_hits = 0
        official_search_hits = 0
        wiki_search_hits = 0
        derivative_search_hits = 0
        purpose_support_keys: set[str] = set()
        alias_support_purpose_keys: set[str] = set()
        official_support_purpose_keys: set[str] = set()
        official_support_hosts: set[str] = set()
        weighted_purpose_support = 0.0
        weighted_alias_support = 0.0
        weighted_official_support = 0.0
        raw_anchor_query_support = 0.0
        self_expansion_query_support = 0.0
        related_anchor_term_map = _collect_related_anchor_terms()
        related_anchor_hits: set[str] = set()
        author_marker_anchor_hits: set[str] = set()
        post_has_author_status_context = _post_has_author_status_context()
        search_seen = set()

        def _purpose_key(raw: Any) -> str:
            key = str(raw or "").strip().lower()
            if ":" in key:
                key = key.split(":", 1)[0].strip()
            return key or "search"

        # resolved_mapping 단계에서 의미/작가/리콜 쿼리는 후보 선택을 보강할 수는 있지만,
        # canonical을 뒤집는 1차 증거로 쓰기에는 자기강화 루프가 되기 쉽다.
        purpose_weight_map = {
            "official_title_verify": 1.0,
            "platform_title_search": 1.0,
            "alias_raw_probe": 0.9,
            "title_search_community": 0.7,
            "community_site_probe": 0.7,
            "alias_bridge_search": 0.7,
            "abbreviation_meaning_search": 0.45,
            "abbreviation_fullname_search": 0.45,
            "author_verify": 0.2,
            "author_disambiguation": 0.2,
            "author_works_search": 0.15,
            "adaptive_author": 0.1,
            "abbreviation_verification": 0.15,
            "title_character_verification": 0.15,
            "decoder_recall_verification": 0.0,
        }

        for sr in (getattr(ctx, "search_results", None) or []):
            if not isinstance(sr, dict):
                continue
            sr_title = str(sr.get("title") or "").strip()
            sr_content = str(sr.get("content") or sr.get("snippet") or "").strip()
            sr_blob = f"{sr_title} {sr_content}".strip()
            sr_blob_norm = _normalize_alnum_kor_cached(sr_blob)
            if not sr_blob_norm:
                continue
            matched = full_norm in sr_blob_norm
            if not matched and sr_title:
                for cand in self._clean_search_result_title(sr_title):
                    if _normalize_alnum_kor_cached(cand) == full_norm:
                        matched = True
                        break
            if not matched:
                continue
            sr_url = str(sr.get("url") or "").strip()
            sr_key = _normalize_alnum_kor_cached(sr_url) or sr_blob_norm
            if sr_key in search_seen:
                continue
            search_seen.add(sr_key)
            search_hit_count += 1
            sr_purpose = _purpose_key(sr.get("_purpose") or sr.get("purpose"))
            sr_query_norm = _normalize_alnum_kor_cached(sr.get("_query") or "")
            if sr_purpose not in purpose_support_keys:
                purpose_support_keys.add(sr_purpose)
                weighted_purpose_support += purpose_weight_map.get(sr_purpose, 0.35)
            if abbr_norm and abbr_norm in sr_blob_norm:
                alias_joint_hits += 1
                if sr_purpose not in alias_support_purpose_keys:
                    alias_support_purpose_keys.add(sr_purpose)
                    weighted_alias_support += purpose_weight_map.get(sr_purpose, 0.35)
            if sr_query_norm:
                _weight = purpose_weight_map.get(sr_purpose, 0.35)
                if abbr_norm and abbr_norm in sr_query_norm:
                    raw_anchor_query_support += _weight
                elif full_norm and full_norm in sr_query_norm:
                    self_expansion_query_support += _weight
            sr_url_lower = sr_url.lower()
            if any(p in sr_url_lower for p in OFFICIAL_PLATFORMS):
                official_search_hits += 1
                if sr_purpose not in official_support_purpose_keys:
                    official_support_purpose_keys.add(sr_purpose)
                    weighted_official_support += purpose_weight_map.get(sr_purpose, 0.35)
                try:
                    from urllib.parse import urlparse as _urlparse_rm

                    _host = (_urlparse_rm(sr_url).hostname or "").lower()
                except Exception:
                    _host = ""
                if _host:
                    official_support_hosts.add(_host)
            if "namu.wiki" in sr_url_lower or "thewiki.kr" in sr_url_lower:
                wiki_search_hits += 1
            if sr.get("_is_derivative"):
                derivative_search_hits += 1
            if related_anchor_term_map:
                for anchor_norm, _anchor_meta in related_anchor_term_map.items():
                    if anchor_norm not in sr_blob_norm:
                        continue
                    related_anchor_hits.add(anchor_norm)
                    if any(
                        marker in sr_blob_norm
                        for marker in ("작가명", "작가", "저자", "연재자", "author")
                    ):
                        author_marker_anchor_hits.add(anchor_norm)

        bucket = _candidate_bucket()
        bucket_score = (
            (_uniq_count(bucket.get("post_spans")) * 2)
            + _uniq_count(bucket.get("search_snippets"))
            + (_uniq_count(bucket.get("official_urls")) * 3)
        )
        official_url_count = _uniq_count(bucket.get("official_urls"))
        post_span_count = _uniq_count(bucket.get("post_spans"))
        snippet_bucket_count = _uniq_count(bucket.get("search_snippets"))

        domain_conflict = _has_domain_conflict_for_mapping(abbrev, full)
        abbr_score = abbreviation_match_score(abbrev, full)
        low_specific_abbrev = self._is_low_specificity_mapping_abbrev(abbrev, full_title=full)
        derivative_title_like = bool(
            re.search(
                r"[\[\]<>]|(?:\b|[가-힣])x(?:\b|[가-힣])|크로스오버|세계관|팬픽|팬아트|리메이크|외전|패러디|도플갱어|전독시",
                str(full or ""),
                re.IGNORECASE,
            )
        )
        matched_related_anchor_terms = [
            related_anchor_term_map[norm]["surface"]
            for norm in sorted(related_anchor_hits)
            if norm in related_anchor_term_map
        ]
        author_context_anchor_terms = [
            related_anchor_term_map[norm]["surface"]
            for norm in sorted(author_marker_anchor_hits)
            if norm in related_anchor_term_map
        ]
        related_anchor_hit_count = len(related_anchor_hits)
        author_marker_hit_count = len(author_marker_anchor_hits)
        author_context_bridge = bool(
            post_has_author_status_context and author_marker_hit_count > 0
        )
        author_contamination = _has_strong_author_signal_for_abbrev()
        explicit_work_alias_signal = _has_explicit_work_alias_signal()
        source_bonus = 0.0
        if source_list:
            source_bonus = max(source_bonus_map.get(src, source_bonus_map["unknown"]) for src in source_list)
            source_bonus += 0.2 * max(0, len(set(source_list)) - 1)

        score = 0.0
        score += source_bonus
        score += abbr_score * 2.8
        score += official_title_hits * 2.8
        score += official_url_count * 1.8
        score += min(weighted_official_support, 3.0) * 1.3
        score += min(len(official_support_hosts), 3) * 0.8
        score += wiki_search_hits * 1.0
        score += min(weighted_purpose_support, 4.0) * 1.0
        score += min(search_hit_count, 8) * 0.2
        score += min(weighted_alias_support, 3.0) * 0.8
        score += min(bucket_score, 10) * 0.7
        score += min(post_span_count, 4) * 0.8
        score += min(snippet_bucket_count, 4) * 0.4
        score += min(related_anchor_hit_count, 4) * 1.1
        score += min(author_marker_hit_count, 2) * 1.8
        if author_context_bridge:
            score += 2.4
        if low_specific_abbrev:
            score -= 3.2
            if official_title_hits <= 0 and official_url_count <= 0:
                score -= 1.8
            if search_hit_count < 2:
                score -= 0.8

        if len(full_norm) <= len(abbr_norm):
            score -= 1.5
        if not official_title_hits and not official_url_count and search_hit_count <= 1:
            score -= 1.5
        if domain_conflict:
            score -= 4.0
        if derivative_search_hits > 0:
            score -= 3.4 + (0.4 * max(0, derivative_search_hits - 1))
        if derivative_title_like:
            score -= 2.2
            if official_title_hits <= 0 and official_url_count <= 0:
                score -= 1.2
        if author_contamination and not explicit_work_alias_signal:
            score -= 4.6
            if official_title_hits <= 1 and official_url_count <= 0 and post_span_count <= 0 and alias_joint_hits <= 1:
                score -= 2.4
        direct_grounded_support = (
            post_span_count
            + official_title_hits
            + official_url_count
            + (1 if explicit_work_alias_signal else 0)
        )
        weak_direct_support = direct_grounded_support <= 0
        closed_bridge = bool(
            author_context_bridge
            and (
                official_title_hits >= 1
                or official_url_count >= 1
                or weighted_official_support >= 1.0
            )
            and (
                explicit_work_alias_signal
                or post_span_count >= 1
                or bucket_score >= 2
                or abbr_score >= 0.55
            )
        )
        bridge_quality = (
            "closed"
            if closed_bridge
            else "supporting"
            if (author_context_bridge or related_anchor_hit_count > 0)
            else "weak"
        )
        if weak_direct_support and abbr_score < 0.45:
            low_value_reinforcement = max(
                0.0,
                weighted_purpose_support - max(weighted_official_support, 1.0),
            )
            if low_value_reinforcement > 0:
                score -= min(low_value_reinforcement, 2.5) * 1.1
        if (
            weak_direct_support
            and abbr_score < 0.45
            and self_expansion_query_support > raw_anchor_query_support + 0.4
        ):
            score -= min(4.0, (self_expansion_query_support - raw_anchor_query_support) * 2.0)

        return {
            "title": full,
            "score": round(score, 3),
            "abbr_score": round(abbr_score, 3),
            "source_bonus": round(source_bonus, 3),
            "official_title_hits": official_title_hits,
            "search_hit_count": search_hit_count,
            "alias_joint_hits": alias_joint_hits,
            "bucket_score": bucket_score,
            "official_url_count": official_url_count,
            "official_search_hits": official_search_hits,
            "wiki_search_hits": wiki_search_hits,
            "weighted_purpose_support": round(weighted_purpose_support, 3),
            "weighted_alias_support": round(weighted_alias_support, 3),
            "weighted_official_support": round(weighted_official_support, 3),
            "raw_anchor_query_support": round(raw_anchor_query_support, 3),
            "self_expansion_query_support": round(self_expansion_query_support, 3),
            "official_host_count": len(official_support_hosts),
            "derivative_search_hits": derivative_search_hits,
            "derivative_title_like": derivative_title_like,
            "related_anchor_hit_count": related_anchor_hit_count,
            "author_marker_hit_count": author_marker_hit_count,
            "author_context_bridge": author_context_bridge,
            "author_status_context": post_has_author_status_context,
            "matched_related_anchor_terms": matched_related_anchor_terms,
            "author_context_anchor_terms": author_context_anchor_terms,
            "direct_grounded_support": direct_grounded_support,
            "closed_bridge": closed_bridge,
            "bridge_quality": bridge_quality,
            "post_span_count": post_span_count,
            "snippet_bucket_count": snippet_bucket_count,
            "domain_conflict": domain_conflict,
            "low_specific_abbrev": low_specific_abbrev,
            "author_contamination": author_contamination,
            "explicit_work_alias_signal": explicit_work_alias_signal,
            "sources": sorted(set(source_list)),
        }

    def _is_low_specificity_mapping_abbrev(
        self,
        abbrev: str,
        *,
        full_title: Optional[str] = None,
    ) -> bool:
        raw = str(abbrev or "").strip()
        if not raw:
            return True

        norm = _normalize_alnum_kor_cached(raw)
        if not norm or len(norm) <= 1:
            return True

        generic_fragments = (
            "정식제목", "작품명", "작가", "후기", "리뷰", "장르", "뜻", "무슨소설", "어디나오는",
            "웹소설", "신작", "최신작", "전개", "내용", "주인공", "캐릭터",
        )
        if any(frag in norm for frag in generic_fragments):
            return True

        low_specific_suffixes = (
            "은", "는", "이", "가", "을", "를", "의", "도", "만", "에", "와", "과", "로",
            "인", "임", "다", "요", "냐", "까", "네", "군", "함", "됨", "중",
        )
        stripped_norm = norm
        for sfx in low_specific_suffixes:
            if len(stripped_norm) > len(sfx) + 1 and stripped_norm.endswith(sfx):
                stripped_norm = stripped_norm[: -len(sfx)]
                break

        generic_stems = {
            "이제", "이제는", "지금", "오늘", "이번", "그냥", "진짜", "가자",
            "됐다", "되었다", "예감", "무슨", "어디", "나오는", "저거", "이거",
            "불륜", "순애", "하렘", "ntr", "ts", "bl", "gl", "백합",
            "제정신", "농이", "장르", "후기", "리뷰", "작품", "작가",
        }
        generic_stems.update(
            _normalize_alnum_kor_cached(t)
            for t in GENRE_ARCHETYPE_TERMS
            if isinstance(t, str) and t.strip()
        )
        if norm in generic_stems or stripped_norm in generic_stems:
            return True
        if is_genre_물_pattern(raw) or (stripped_norm and is_genre_물_pattern(stripped_norm)):
            return True
        if len(norm) <= 6 and any(norm.endswith(sfx) for sfx in low_specific_suffixes):
            return True

        full_norm = _normalize_alnum_kor_cached(full_title or "")
        if full_norm and norm == full_norm:
            return False
        if (
            full_norm
            and stripped_norm
            and stripped_norm in full_norm
            and len(stripped_norm) <= max(4, len(full_norm) // 3)
            and (
                stripped_norm in generic_stems
                or len(norm) <= 6
                or any(norm.endswith(sfx) for sfx in low_specific_suffixes)
            )
        ):
            return True
        return False

    def _is_derivative_or_variant_title(
        self,
        base_title: str,
        candidate_title: str,
    ) -> bool:
        """
        원작 canonical title 위에 덧붙은 파생작/패러디/외전형 제목인지 느슨하게 판별한다.
        예:
        - "괴담 동아리" -> "[괴담동아리] 괴담 메이커"
        - "괴담 동아리" -> "괴담동아리 if"
        - "괴담 동아리" -> "괴담동아리 세계에 전생했다"
        """
        base_raw = str(base_title or "").strip()
        cand_raw = str(candidate_title or "").strip()
        if not base_raw or not cand_raw or base_raw == cand_raw:
            return False

        base_norm = _normalize_alnum_kor_cached(base_raw)
        cand_norm = _normalize_alnum_kor_cached(cand_raw)
        if not base_norm or not cand_norm or base_norm == cand_norm:
            return False
        if base_norm not in cand_norm:
            return False

        remainder = cand_norm.replace(base_norm, "", 1)
        if len(remainder) < 2:
            return False

        cand_compact = re.sub(r"\s+", "", cand_raw).lower()
        base_compact = re.sub(r"\s+", "", base_raw).lower()
        if not base_compact or base_compact == cand_compact:
            return False

        derivative_markers = (
            "if", "외전", "패러디", "빙의", "환생", "전생", "세계", "속",
            "메이커", "표절", "작가", "조력자", "리메이크", "스핀오프",
            "팬아트", "팬픽", "이미지", "짤", "리뷰", "분석", "감상", "후기",
            "괴담", "시즌", "세계관", "마왕", "주인공", "겨울",
            "크로스오버", "crossover",
        )
        if any(marker in cand_compact for marker in derivative_markers):
            return True
        if cand_raw.startswith("[") and "]" in cand_raw:
            return True
        if len(cand_norm) >= len(base_norm) + 4:
            return True
        return False

    def _refine_resolved_mappings(
        self,
        ctx: Any,
        mapping_entries: List[Dict[str, Any]],
    ) -> List[tuple[str, str]]:
        """같은 약칭의 경쟁 후보 중 검색/공식 근거가 더 강한 제목만 주입한다."""
        discourse_warning = str(getattr(ctx, "discourse_warning", "") or "").lower()
        llm_snippet_result = getattr(ctx, "llm_snippet_analysis", None) or {}
        snippet_category = str(llm_snippet_result.get("identified_category") or "").lower().strip()
        snippet_intent = str(llm_snippet_result.get("post_intent") or "").lower().strip()
        gk_result = getattr(ctx, "gatekeeper_result", None) or {}
        gk_post_type = str(gk_result.get("post_type") or "").lower().strip()
        genre_generalization_context = bool(
            (
                discourse_warning
                and any(
                    marker in discourse_warning
                    for marker in (
                        "genre_discussion",
                        "trope_discussion",
                        "genre_opinion",
                        "community_banter",
                        "title_body_mismatch",
                        "incoherent_post",
                    )
                )
            )
            or snippet_category == "genre_discussion"
            or snippet_intent == "genre_discussion"
            or gk_post_type in {"genre_discussion", "trope_discussion", "genre_opinion"}
        )

        _post_data_rm = getattr(ctx, "post_data", None) or {}
        _image_enrichment_rm = [
            item for item in (_post_data_rm.get("image_enrichment") or [])
            if isinstance(item, dict)
        ]
        _direct_image_titles_rm = [
            str(item.get("explicit_work_title") or "").strip()
            for item in _image_enrichment_rm
            if str(item.get("explicit_work_title") or "").strip()
            and str(item.get("title_role") or "").strip() in {"", "work_title"}
        ]
        _direct_image_title_norms_rm = {
            _normalize_alnum_kor_cached(title)
            for title in _direct_image_titles_rm
            if _normalize_alnum_kor_cached(title)
        }
        _ocr_text_rm = " ".join(
            str(item.get("ocr_text") or "")
            for item in _image_enrichment_rm
            if isinstance(item, dict)
        )

        def _mapping_conflicts_with_direct_image_title(abbrev: str, full: str) -> bool:
            abbr_norm_local = _normalize_alnum_kor_cached(abbrev)
            full_norm_local = _normalize_alnum_kor_cached(full)
            if not abbr_norm_local or not full_norm_local or not _direct_image_title_norms_rm:
                return False
            if any(
                full_norm_local == dt_norm
                or full_norm_local in dt_norm
                or dt_norm in full_norm_local
                for dt_norm in _direct_image_title_norms_rm
            ):
                return False

            if "/목록" in str(full or "") or str(full or "").endswith("목록"):
                return True
            if _is_genre_물_pattern(str(abbrev or "")) or self._is_low_specificity_mapping_abbrev(abbrev, full_title=full):
                return True
            if _ocr_text_rm and f"#{str(abbrev or '').strip()}" in _ocr_text_rm:
                return True
            if any(abbr_norm_local in dt_norm for dt_norm in _direct_image_title_norms_rm):
                return True
            return False

        grouped: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for entry in mapping_entries or []:
            if not isinstance(entry, dict):
                continue
            abbrev = str(entry.get("abbrev") or "").strip()
            full = str(entry.get("full") or "").strip()
            source = str(entry.get("source") or "unknown").strip() or "unknown"
            abbr_norm = _normalize_alnum_kor_cached(abbrev)
            full_norm = _normalize_alnum_kor_cached(full)
            if not abbr_norm or not full_norm:
                continue
            grouped.setdefault(abbr_norm, {})
            bucket = grouped[abbr_norm].setdefault(
                full_norm,
                {"abbrev": abbrev, "full": full, "sources": set()},
            )
            # 더 정보량 큰 표기를 유지
            if len(_normalize_alnum_kor_cached(full)) > len(_normalize_alnum_kor_cached(bucket["full"])):
                bucket["full"] = full
            if len(_normalize_alnum_kor_cached(abbrev)) > len(_normalize_alnum_kor_cached(bucket["abbrev"])):
                bucket["abbrev"] = abbrev
            bucket["sources"].add(source)

        refined: List[tuple[str, str]] = []
        for abbr_norm, candidate_map in grouped.items():
            scored: List[Dict[str, Any]] = []
            for candidate in candidate_map.values():
                if _mapping_conflicts_with_direct_image_title(candidate["abbrev"], candidate["full"]):
                    print(
                        f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 보류(direct_image_conflict): "
                        f"'{candidate['abbrev']}' 후보='{candidate['full']}'",
                        file=sys.stderr,
                    )
                    continue
                eval_info = self._score_resolved_mapping_candidate(
                    ctx,
                    candidate["abbrev"],
                    candidate["full"],
                    sources=sorted(candidate["sources"]),
                )
                eval_info["abbrev"] = candidate["abbrev"]
                if hasattr(ctx, "merge_candidate_bridge_profile"):
                    try:
                        ctx.merge_candidate_bridge_profile(
                            candidate["full"],
                            {
                                "title": candidate["full"],
                                "abbrev": candidate["abbrev"],
                                "bridge_quality": eval_info.get("bridge_quality"),
                                "closed_bridge": bool(eval_info.get("closed_bridge")),
                                "author_context_bridge": bool(eval_info.get("author_context_bridge")),
                                "author_status_context": bool(eval_info.get("author_status_context")),
                                "matched_related_anchor_terms": list(eval_info.get("matched_related_anchor_terms") or []),
                                "author_context_anchor_terms": list(eval_info.get("author_context_anchor_terms") or []),
                                "related_anchor_hit_count": int(eval_info.get("related_anchor_hit_count") or 0),
                                "author_marker_hit_count": int(eval_info.get("author_marker_hit_count") or 0),
                                "weighted_official_support": float(eval_info.get("weighted_official_support") or 0.0),
                                "weighted_purpose_support": float(eval_info.get("weighted_purpose_support") or 0.0),
                                "official_title_hits": int(eval_info.get("official_title_hits") or 0),
                                "official_url_count": int(eval_info.get("official_url_count") or 0),
                                "official_host_count": int(eval_info.get("official_host_count") or 0),
                                "post_span_count": int(eval_info.get("post_span_count") or 0),
                                "bucket_score": int(eval_info.get("bucket_score") or 0),
                                "explicit_work_alias_signal": bool(eval_info.get("explicit_work_alias_signal")),
                                "abbr_score": float(eval_info.get("abbr_score") or 0.0),
                                "score": float(eval_info.get("score") or 0.0),
                            },
                        )
                    except Exception:
                        pass
                scored.append(eval_info)

            scored.sort(
                key=lambda x: (
                    float(x.get("score", 0.0)),
                    int(x.get("official_title_hits", 0)),
                    int(x.get("bucket_score", 0)),
                    int(x.get("search_hit_count", 0)),
                    len(_normalize_alnum_kor_cached(x.get("title", ""))),
                ),
                reverse=True,
            )
            if not scored:
                continue

            top = scored[0]
            second = scored[1] if len(scored) > 1 else None

            def _looks_derivativeish_mapping_title(title: str) -> bool:
                raw = str(title or "").strip()
                norm = _normalize_alnum_kor_cached(raw)
                if not raw or not norm:
                    return False
                if (
                    "[" in raw or "]" in raw
                    or re.search(
                        r"(?:\b|[가-힣])x(?:\b|[가-힣])|크로스오버|세계관|팬픽|팬아트|리메이크|외전|패러디|도플갱어|전독시",
                        raw,
                        re.IGNORECASE,
                    )
                ):
                    return True
                if abbr_norm and abbr_norm in norm and len(norm) >= len(abbr_norm) + 4:
                    return True
                return False

            if bool(top.get("derivative_title_like")) or _looks_derivativeish_mapping_title(top.get("title") or ""):
                replacement = None
                for cand in scored[1:]:
                    cand_title = str(cand.get("title") or "").strip()
                    cand_norm = _normalize_alnum_kor_cached(cand_title)
                    cand_official_total = (
                        int(cand.get("official_title_hits", 0))
                        + int(cand.get("official_url_count", 0))
                        + int(cand.get("official_search_hits", 0))
                        + int(cand.get("wiki_search_hits", 0))
                    )
                    cand_structural = int(cand.get("bucket_score", 0)) + int(cand.get("post_span_count", 0))
                    cand_abbr_score = float(cand.get("abbr_score", 0.0))
                    cand_derivativeish = bool(cand.get("derivative_title_like")) or _looks_derivativeish_mapping_title(cand_title)
                    if cand_derivativeish:
                        continue
                    if not cand_title or not cand_norm:
                        continue
                    if cand_official_total <= 0 and cand_structural <= 0:
                        continue
                    if cand_abbr_score < 0.35 and (not abbr_norm or abbr_norm not in cand_norm):
                        continue
                    if float(cand.get("score", 0.0)) < 3.0:
                        continue
                    replacement = cand
                    break
                if replacement:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ resolved_mapping canonical 승격(파생작 억제): "
                        f"'{top.get('abbrev')}' top='{top.get('title')}' "
                        f"→ canonical='{replacement.get('title')}'",
                        file=sys.stderr,
                    )
                    top = replacement
                    second = None

            _snippet_title_raw = str(
                (getattr(ctx, "llm_snippet_analysis", None) or {}).get("identified_title") or ""
            ).strip()
            _snippet_title_norm = _normalize_alnum_kor_cached(_snippet_title_raw)
            _snippet_candidate = None
            if _snippet_title_norm:
                for cand in scored:
                    if _normalize_alnum_kor_cached(str(cand.get("title") or "")) == _snippet_title_norm:
                        _snippet_candidate = cand
                        break
            if _snippet_candidate and _normalize_alnum_kor_cached(str(top.get("title") or "")) != _snippet_title_norm:
                _snippet_official_total = (
                    int(_snippet_candidate.get("official_title_hits", 0))
                    + int(_snippet_candidate.get("official_url_count", 0))
                    + int(_snippet_candidate.get("official_search_hits", 0))
                    + int(_snippet_candidate.get("wiki_search_hits", 0))
                )
                _snippet_direct_support = (
                    int(_snippet_candidate.get("bucket_score", 0))
                    + int(_snippet_candidate.get("post_span_count", 0))
                )
                _top_direct_support = int(top.get("bucket_score", 0)) + int(top.get("post_span_count", 0))
                _top_official_title_hits = int(top.get("official_title_hits", 0))
                _top_low_abbr = float(top.get("abbr_score", 0.0)) < 0.45
                _top_indirect_only = (
                    _top_direct_support <= 0
                    and _top_official_title_hits <= 0
                    and int(top.get("official_url_count", 0)) <= 0
                    and not bool(top.get("explicit_work_alias_signal"))
                )
                _snippet_is_stable = (
                    _snippet_official_total >= 2
                    or _snippet_direct_support > 0
                )
                _snippet_not_derivative = not (
                    bool(_snippet_candidate.get("derivative_title_like"))
                    or _looks_derivativeish_mapping_title(_snippet_candidate.get("title") or "")
                )
                _top_self_expansion = float(top.get("self_expansion_query_support", 0.0))
                _top_raw_anchor = float(top.get("raw_anchor_query_support", 0.0))
                if (
                    _top_low_abbr
                    and _top_indirect_only
                    and _snippet_is_stable
                    and _snippet_not_derivative
                    and (
                        float(top.get("score", 0.0))
                        <= float(_snippet_candidate.get("score", 0.0)) + 3.5
                        or _top_self_expansion > _top_raw_anchor + 0.5
                        or (_top_official_title_hits <= 0 and _snippet_official_total >= 2)
                    )
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ resolved_mapping snippet canonical 보존: "
                        f"'{top.get('abbrev')}' top='{top.get('title')}' "
                        f"→ snippet='{_snippet_candidate.get('title')}' "
                        f"(top_abbr={float(top.get('abbr_score', 0.0)):.2f}, "
                        f"snippet_official={_snippet_official_total}, "
                        f"self_expand={_top_self_expansion:.2f}, raw_anchor={_top_raw_anchor:.2f})",
                        file=sys.stderr,
                    )
                    top = _snippet_candidate
                    second = None

            _lock_title_raw = str(getattr(ctx, "canonical_title_lock", "") or "").strip()
            _lock_title_norm = _normalize_alnum_kor_cached(_lock_title_raw)
            if _lock_title_norm and _normalize_alnum_kor_cached(str(top.get("title") or "")) != _lock_title_norm:
                _lock_candidate = None
                for cand in scored:
                    if _normalize_alnum_kor_cached(str(cand.get("title") or "")) == _lock_title_norm:
                        _lock_candidate = cand
                        break
                if _lock_candidate:
                    _top_low_abbr = float(top.get("abbr_score", 0.0)) < 0.45
                    _top_direct = int(top.get("direct_grounded_support", 0) or 0)
                    _top_official_hits = int(top.get("official_title_hits", 0) or 0)
                    _top_self_expand = float(top.get("self_expansion_query_support", 0.0) or 0.0)
                    _top_raw_anchor = float(top.get("raw_anchor_query_support", 0.0) or 0.0)
                    _lock_official_total = (
                        int(_lock_candidate.get("official_title_hits", 0))
                        + int(_lock_candidate.get("official_url_count", 0))
                        + int(_lock_candidate.get("official_search_hits", 0))
                        + int(_lock_candidate.get("wiki_search_hits", 0))
                    )
                    _lock_bridge = bool(
                        _lock_candidate.get("closed_bridge")
                        or _lock_candidate.get("author_context_bridge")
                    )
                    if (
                        _top_low_abbr
                        and _top_direct <= 0
                        and _top_official_hits <= 0
                        and (
                            _top_self_expand > _top_raw_anchor + 0.5
                            or float(top.get("score", 0.0)) <= float(_lock_candidate.get("score", 0.0)) + 4.0
                        )
                        and (_lock_official_total >= 2 or _lock_bridge)
                    ):
                        print(
                            f"[{_ts()}][{self.emoji}] 🔒 resolved_mapping canonical lock 유지: "
                            f"top='{top.get('title')}' → lock='{_lock_candidate.get('title')}' "
                            f"(top_abbr={float(top.get('abbr_score', 0.0)):.2f}, "
                            f"self_expand={_top_self_expand:.2f}, raw_anchor={_top_raw_anchor:.2f})",
                            file=sys.stderr,
                        )
                        top = _lock_candidate
                        second = None

            gap = float(top.get("score", 0.0)) - float((second or {}).get("score", 0.0))
            top_source_diversity = len(set(top.get("sources") or []))
            second_source_diversity = len(set((second or {}).get("sources") or []))
            top_support = (
                int(top.get("official_title_hits", 0))
                + int(top.get("official_url_count", 0))
                + int(top.get("bucket_score", 0))
            )
            second_support = (
                int((second or {}).get("official_title_hits", 0))
                + int((second or {}).get("official_url_count", 0))
                + int((second or {}).get("bucket_score", 0))
            )
            top_official_total = (
                int(top.get("official_title_hits", 0))
                + int(top.get("official_url_count", 0))
                + int(top.get("official_search_hits", 0))
                + int(top.get("wiki_search_hits", 0))
            )
            second_official_total = (
                int((second or {}).get("official_title_hits", 0))
                + int((second or {}).get("official_url_count", 0))
                + int((second or {}).get("official_search_hits", 0))
                + int((second or {}).get("wiki_search_hits", 0))
            )

            if float(top.get("score", 0.0)) < 3.0:
                print(
                    f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 보류(근거 약함): "
                    f"'{top.get('abbrev')}' 후보='{top.get('title')}' "
                    f"(score={float(top.get('score', 0.0)):.2f})",
                    file=sys.stderr,
                )
                continue

            if bool(top.get("low_specific_abbrev")):
                _top_official_support = (
                    int(top.get("official_title_hits", 0))
                    + int(top.get("official_url_count", 0))
                    + int(top.get("official_search_hits", 0))
                    + int(top.get("wiki_search_hits", 0))
                )
                _second_score = float((second or {}).get("score", 0.0))
                _second_title = str((second or {}).get("title") or "")
                if (
                    _top_official_support <= 0
                    and int(top.get("search_hit_count", 0)) < 3
                ) or (
                    second
                    and len(_normalize_alnum_kor_cached(_second_title)) > len(_normalize_alnum_kor_cached(str(top.get("title") or "")))
                    and float(top.get("score", 0.0)) <= (_second_score + 1.2)
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 보류(저특이 약칭): "
                        f"'{top.get('abbrev')}' 후보='{top.get('title')}' "
                        f"(score={float(top.get('score', 0.0)):.2f}, official={_top_official_support})",
                        file=sys.stderr,
                    )
                    continue

            if genre_generalization_context:
                _weak_contextual_mapping = (
                    bool(top.get("low_specific_abbrev"))
                    or len(_normalize_alnum_kor_cached(str(top.get("abbrev") or ""))) <= 4
                    or len(_normalize_alnum_kor_cached(str(top.get("title") or ""))) <= 8
                )
                _support_is_thin = (
                    top_official_total <= 1
                    and int(top.get("bucket_score", 0)) <= 0
                    and int(top.get("post_span_count", 0)) <= 0
                    and int(top.get("alias_joint_hits", 0)) <= 1
                )
                if _weak_contextual_mapping and _support_is_thin:
                    print(
                        f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 보류(장르 일반론 문맥): "
                        f"'{top.get('abbrev')}' 후보='{top.get('title')}' "
                        f"(official={top_official_total}, bucket={top.get('bucket_score', 0)}, "
                        f"alias_joint={top.get('alias_joint_hits', 0)})",
                        file=sys.stderr,
                    )
                    continue

            if (
                second
                and gap < 1.4
                and second_official_total >= top_official_total + 1
                and second_source_diversity >= top_source_diversity
                and int((second or {}).get("search_hit_count", 0)) >= int(top.get("search_hit_count", 0)) - 1
            ):
                print(
                    f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 보류(공식근거 경쟁): "
                    f"'{top.get('abbrev')}' top='{top.get('title')}' "
                    f"(score={float(top.get('score', 0.0)):.2f}, official={top_official_total}) vs "
                    f"'{second.get('title')}' (score={float(second.get('score', 0.0)):.2f}, official={second_official_total})",
                    file=sys.stderr,
                )
                continue

            if (
                second
                and gap < 0.9
                and top_support <= second_support + 1
                and int(top.get("official_title_hits", 0)) <= int(second.get("official_title_hits", 0)) + 1
            ):
                print(
                    f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 보류(경쟁후보 근접): "
                    f"'{top.get('abbrev')}' top='{top.get('title')}' "
                    f"(score={float(top.get('score', 0.0)):.2f}) vs "
                    f"'{second.get('title')}' (score={float(second.get('score', 0.0)):.2f})",
                    file=sys.stderr,
                )
                continue

            if (
                bool(top.get("author_contamination"))
                and not bool(top.get("explicit_work_alias_signal"))
                and int(top.get("post_span_count", 0)) <= 0
                and int(top.get("bucket_score", 0)) <= 0
                and int(top.get("alias_joint_hits", 0)) <= 1
                and float(top.get("abbr_score", 0.0)) < 0.45
            ):
                print(
                    f"[{_ts()}][{self.emoji}] ⏭️ resolved_mapping 보류(작가명 오염): "
                    f"'{top.get('abbrev')}' 후보='{top.get('title')}' "
                    f"(score={float(top.get('score', 0.0)):.2f}, author_contamination=True)",
                    file=sys.stderr,
                )
                continue

            refined.append((str(top.get("abbrev") or "").strip(), str(top.get("title") or "").strip()))
            print(
                f"[{_ts()}][{self.emoji}] ✅ resolved_mapping 채택: "
                f"'{top.get('abbrev')}' → '{top.get('title')}' "
                f"(score={float(top.get('score', 0.0)):.2f}, "
                f"official_titles={top.get('official_title_hits', 0)}, "
                f"bucket={top.get('bucket_score', 0)}, search_hits={top.get('search_hit_count', 0)})",
                file=sys.stderr,
            )
        return refined
    
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
                if not isinstance(cand, dict):
                    continue
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
                                # 🛡️ Phase37 Fix: 작가명이 제목에 연속 부분문자열로 포함되면
                                # 이것은 약칭 패턴이 아니라 '작가명 ⊂ 소설제목' 패턴
                                # 예: "컵라면"(작가) → "컵라면 먹다가 게임 속으로 들어간 썰 푼다"
                                # 이 경우 rescue하면 안 됨 (작가명≠약칭)
                                if author_clean in potential_clean:
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🛡️ 작가명=약칭 rescue P4 차단: "
                                        f"'{author_name}' 이 '{potential}' 에 연속 부분문자열로 포함 "
                                        f"→ 작가명⊂제목 패턴, 약칭 아님",
                                        file=sys.stderr,
                                    )
                                    continue
                                found_title = potential
                                found_url = sr_url
                                found_platform = next(
                                    (d.split(".")[0] for d in platform_domains if d in sr_url),
                                    None,
                                )
                
                if found_title:
                    # 🛡️ Phase37 통합 가드: 모든 패턴에 대해 "작가명⊂제목" 최종 검증
                    # 작가명이 found_title에 연속 부분문자열로 포함되면 약칭이 아닌 작가명
                    # 또한 1글자 오차 허용 (예: 컵라인 vs 컵라면 — 커뮤니티 오타 대응)
                    _ft_clean = found_title.replace(" ", "").replace("[독점]", "").replace("[완결]", "")
                    _author_is_in_title = author_clean in _ft_clean
                    # 퍼지 접두사 검사: 작가명이 제목 시작부분과 1글자 이내 차이
                    if not _author_is_in_title and len(author_clean) >= 2 and len(_ft_clean) >= len(author_clean):
                        _prefix = _ft_clean[:len(author_clean)]
                        _match_cnt = sum(1 for a, b in zip(author_clean, _prefix) if a == b)
                        if _match_cnt >= len(author_clean) - 1:
                            _author_is_in_title = True
                    if _author_is_in_title:
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 작가명=약칭 rescue 통합차단: "
                            f"'{author_name}' ⊂ '{found_title}' → 작가명이 제목에 포함, 약칭 아님",
                            file=sys.stderr,
                        )
                        found_title = None
                        found_url = None
                        found_platform = None
                        continue
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

    def _detect_author_discussion(self, result: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
        """
        🛡️ 작가 토론/비교 글 감지: 모든(또는 대부분) decoded_terms가 작가명이고
        서로 다른 작가를 가리키며, 작품 약칭 해석의 context_fit이 약할 때
        → 특정 작품이 아닌 '작가 비교/토론' 글로 판정.

        예: 게시글 "싱숑이랑 퉁구스카랑 같은 말 하는거 아닌"
          - "싱숑" → author_name (context_fit=high), 작품약칭 (context_fit=medium)
          - "퉁구스카" → author_name (context_fit=high), 작품약칭 (context_fit=medium)
          → 두 작가의 행동을 비교하는 글. 특정 1개 작품이 주제가 아님.

        처리:
        - best_match.title → null (특정 작품 비매칭)
        - result["author_discussion"] = True
        - overall_confidence → "low"
        - notes에 작가 토론 감지 기록
        """
        decoded_terms = result.get("decoded_terms", [])
        if not decoded_terms or len(decoded_terms) < 2:
            return result

        # 각 term이 작가명인지 / 작가명 해석이 primary인지 판별
        author_terms = []
        non_author_terms = []
        for term in decoded_terms:
            if not isinstance(term, dict):
                continue
            is_author = term.get("is_author_name", False)
            interps = term.get("interpretations", [])

            # LLM이 is_author_name=false로 설정했더라도
            # interpretations에서 author_name이 context_fit=high/medium이면 작가 후보
            author_interp_fit = None
            work_interp_fit = None
            for interp in interps:
                if not isinstance(interp, dict):
                    continue
                itype = interp.get("type", "")
                fit = interp.get("context_fit", "").lower()
                if itype == "author_name":
                    if fit in ("high", "medium"):
                        author_interp_fit = fit
                elif itype in (
                    "novel_title_abbreviation", "work_abbreviation",
                    "novel_abbreviation", "abbreviation", "title_abbreviation",
                ):
                    if fit in ("high", "medium"):
                        work_interp_fit = fit

            # 작가 해석이 primary (author_name 해석 >= work 해석)
            _author_primary = False
            if is_author:
                _author_primary = True
            elif author_interp_fit == "high" and work_interp_fit != "high":
                _author_primary = True
            elif author_interp_fit == "high" and work_interp_fit == "high":
                # 둘 다 high일 때 — interpretations 순서로 판단
                # 첫 번째 해석이 author_name이면 작가 primary
                for interp in interps:
                    if isinstance(interp, dict):
                        first_type = interp.get("type", "")
                        if first_type == "author_name":
                            _author_primary = True
                        break

            if _author_primary:
                author_terms.append(term)
            else:
                non_author_terms.append(term)

        # 조건: 작가 term이 2개 이상이고, 비-작가 term이 없어야 함
        if len(author_terms) < 2 or len(non_author_terms) > 0:
            return result

        # 추가 조건: 서로 다른 작가를 가리키는지 확인
        # (같은 작가명의 다른 표기라면 작가 토론이 아님)
        author_names = set()
        author_works = set()
        for term in author_terms:
            original = (term.get("original") or "").strip()
            if original:
                author_names.add(original)
            # 매핑된 작품도 수집
            bm = term.get("best_match") or {}
            bm_title = (bm.get("title") or "").strip()
            if bm_title:
                author_works.add(bm_title)

        if len(author_names) < 2:
            return result

        # 모든 조건 충족: 작가 토론글로 판정
        result["author_discussion"] = True

        # best_match.title을 null로 전환 (특정 작품 비매칭)
        cleared_titles = []
        for term in author_terms:
            bm = term.get("best_match") or {}
            old_title = bm.get("title")
            if old_title:
                cleared_titles.append(old_title)
                bm["title"] = None
                bm["confidence"] = "none"
                term["best_match"] = bm

        # overall_confidence 하향
        if result.get("overall_confidence") in ("high", "medium"):
            result["overall_confidence"] = "low"

        # notes 기록
        _authors_str = ", ".join(sorted(author_names))
        _works_str = ", ".join(sorted(author_works)) if author_works else "없음"
        _note = (
            f" [작가토론 감지] 다중 작가 비교글: 작가={_authors_str}, "
            f"매핑됐던 작품={_works_str} → 특정 작품 비매칭으로 전환."
        )
        result["notes"] = (result.get("notes", "") or "") + _note

        print(
            f"[{_ts()}][{self.emoji}] 🛡️ 작가 토론 감지: "
            f"작가 {len(author_terms)}명 ({_authors_str}) → "
            f"서로 다른 작품 {len(author_works)}개 ({_works_str}) 매핑 차단 "
            f"→ author_discussion=True, best_match.title=null",
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

    def _guard_alias_bridge_pending(
        self,
        result: Dict[str, Any],
        ctx: Any,
        gatekeeper_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        커뮤니티 약칭이 강하게 보이지만 공식 제목 브리지가 아직 붙지 않은 경우,
        Decoder가 장르/아키타입 일반화 제목으로 굳는 것을 차단한다.
        """
        gk_out = gatekeeper_result or {}
        if not isinstance(gk_out, dict):
            gk_out = {}
        gk_post_type = str(gk_out.get("post_type") or "").strip().lower()
        if gk_post_type in {"noise", "off_topic", "community_banter"}:
            return result

        gk_entities = gk_out.get("detected_entities") or {}
        alias_norms: set[str] = set()
        for raw in (gk_entities.get("possible_titles") or []):
            raw_norm = _normalize_alnum_kor_cached(str(raw or ""))
            if 2 <= len(raw_norm) <= 14:
                alias_norms.add(raw_norm)
        if not alias_norms:
            return result

        named_anchor_count = len(gk_entities.get("possible_characters") or []) + len(gk_entities.get("possible_authors") or [])
        snippet_hints = getattr(ctx, "snippet_hints", None) or {}
        bridge_activity = bool(getattr(ctx, "alias_bridge_queries_executed", 0))
        if snippet_hints.get("author_bridge_evidence"):
            bridge_activity = True
        for ah in (snippet_hints.get("abbreviation_hints") or []):
            if str(ah.get("source", "") or "") in {"author_bridge", "alias_bridge"}:
                bridge_activity = True
                break

        if (not bridge_activity) and named_anchor_count <= 0:
            return result

        generic_title_terms = {
            "장르", "클리셰", "트로프", "작품명추정", "작품추정",
            "무림물", "회귀물", "헌터물", "아카데미물", "판타지물",
        }
        official_sources = {"url_fetch_platform", "platform_title", "url_fetch", "author_bridge", "alias_bridge", "llm_snippet"}

        def _has_official_title_signal(title: str) -> bool:
            title_norm = _normalize_alnum_kor_cached(title)
            if not title_norm:
                return False
            for th in (snippet_hints.get("title_hints") or []):
                if not isinstance(th, dict):
                    continue
                if str(th.get("source", "") or "") not in official_sources:
                    continue
                if _normalize_alnum_kor_cached(str(th.get("title", "") or "")) == title_norm:
                    return True
            for ah in (snippet_hints.get("abbreviation_hints") or []):
                if not isinstance(ah, dict):
                    continue
                if str(ah.get("source", "") or "") not in official_sources:
                    continue
                if _normalize_alnum_kor_cached(str(ah.get("full", "") or "")) == title_norm:
                    return True
            for sr in (getattr(ctx, "search_results", None) or [])[:25]:
                sr_url = str(sr.get("url") or "")
                sr_title = str(sr.get("title") or "")
                sr_title_norm = _normalize_alnum_kor_cached(sr_title)
                if title_norm not in sr_title_norm:
                    continue
                try:
                    from urllib.parse import urlparse as _urlparse_d
                    host = (_urlparse_d(sr_url).hostname or "").lower()
                except Exception:
                    host = ""
                if "namu.wiki" in host:
                    return True
                if any(host == d or host.endswith("." + d) for d in OFFICIAL_PLATFORM_DOMAINS):
                    return True
            return False

        pending = False
        changed = False
        for term in (result.get("decoded_terms") or []):
            if not isinstance(term, dict):
                continue
            original = str(term.get("original") or "").strip()
            original_norm = _normalize_alnum_kor_cached(original)
            if not original_norm:
                continue
            if not any(original_norm == an or original_norm in an or an in original_norm for an in alias_norms):
                continue

            best_match = term.get("best_match") or {}
            title = str(best_match.get("title") or "").strip()
            if not title:
                term["_alias_bridge_pending"] = True
                pending = True
                continue

            title_clean = re.sub(r"\s*\([^)]*추정[^)]*\)\s*$", "", title).strip()
            title_norm = _normalize_alnum_kor_cached(title_clean)
            if not title_norm:
                continue
            abbr_score = max(
                abbreviation_match_score(original, title_clean),
                _leading_jamo_title_direct_score(original, title_clean),
            )
            is_generic_fallback = (
                title_norm in generic_title_terms
                or any(gt in title_norm for gt in ("작품명추정", "장르", "클리셰", "트로프"))
                or (len(title_norm) <= 12 and title_norm.endswith("물"))
            )
            if not is_generic_fallback:
                continue
            if _has_official_title_signal(title_clean):
                continue
            if abbr_score >= 0.72:
                continue

            old_conf = str(best_match.get("confidence") or "low")
            best_match["title"] = None
            best_match["confidence"] = "none"
            best_match["_alias_bridge_pending"] = True
            term["_alias_bridge_pending"] = True
            pending = True
            changed = True
            _overall_bm = result.get("overall_best_match") or {}
            if isinstance(_overall_bm, dict) and _normalize_alnum_kor_cached(str(_overall_bm.get("title") or "")) == title_norm:
                result["overall_best_match"] = {"title": None, "confidence": "none"}
            if result.get("overall_confidence") in ("high", "medium"):
                result["overall_confidence"] = "low"
            elif result.get("overall_confidence") in ("none", ""):
                result["overall_confidence"] = "low"
            print(
                f"[{_ts()}][{self.emoji}] 🌉 약칭 브리지 보류 가드: "
                f"'{original}' → '{title}' "
                f"(generic_fallback, score={abbr_score:.2f}, conf={old_conf}→none)",
                file=sys.stderr,
            )

        if pending:
            ctx.alias_bridge_pending = True
            if bridge_activity:
                ctx.alias_bridge_queries_executed = max(1, int(getattr(ctx, "alias_bridge_queries_executed", 0) or 0))
            if hasattr(ctx, "uncertainty_sources"):
                _msg = "community alias bridge pending: 공식 제목 브리지 탐색 중"
                if _msg not in ctx.uncertainty_sources:
                    ctx.uncertainty_sources.append(_msg)
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
        
        is_genre_warning = bool(
            discourse_warning
            and any(
                marker in str(discourse_warning).lower()
                for marker in (
                    "discuss_genre",
                    "genre_discussion",
                    "trope_discussion",
                    "genre_opinion",
                    "community_banter",
                    "title_body_mismatch",
                    "incoherent_post",
                    "non_novel(",
                )
            )
        )
        
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

        # 🆕 장르 경고가 있더라도, "제목/본문 앵커 + 공식 플랫폼 제목" 결속이 있으면 역제동을 면제
        # 목적: 약칭 중심 커뮤니티 글(제목 약칭 + 본문 전개/캐릭터)이 genre_warning으로 과도하게 low로 떨어지는 현상 완화
        if not evidence_found:
            post_data_local = getattr(ctx, "post_data", {}) or {}
            post_main_chunks = [str(post_data_local.get("title") or "")]
            for block in post_data_local.get("content_blocks", []) or []:
                if isinstance(block, dict):
                    post_main_chunks.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    post_main_chunks.append(block)
            post_main_norm = _re.sub(r"[^\w가-힣]", "", " ".join(post_main_chunks)).lower()
            official_titles = self._extract_official_titles_from_search(ctx)
            official_norms = {
                _re.sub(r"[^\w가-힣]", "", str(o.get("title") or "")).lower()
                for o in official_titles
                if isinstance(o, dict)
            }
            strong_anchor_types = {"title_mention", "plot_mention", "character_title_link", "character_mention"}
            for term in result.get("decoded_terms", []):
                if not isinstance(term, dict):
                    continue
                best = term.get("best_match") or {}
                title = str(best.get("title") or "").strip()
                conf = str(best.get("confidence") or "").lower()
                if not title or conf not in ("high", "medium"):
                    continue
                title_norm = _re.sub(r"[^\w가-힣]", "", title).lower()
                if not title_norm or title_norm not in official_norms:
                    continue
                orig_norm = _re.sub(r"[^\w가-힣]", "", str(term.get("original") or "")).lower()
                grounding = term.get("grounding") or {}
                anchor_type = str(grounding.get("anchor_type") or "").lower()
                in_post_main = (orig_norm and orig_norm in post_main_norm) or (title_norm in post_main_norm)
                strong_anchor = anchor_type in strong_anchor_types
                if in_post_main and (strong_anchor or len(orig_norm) >= 2):
                    evidence_found = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🔒 Discourse 역방향 제동 면제: "
                        f"공식제목+게시글앵커 결속 확인 ('{title}', anchor={anchor_type or 'none'})",
                        file=sys.stderr,
                    )
                    break

        # 🆕 밈/커뮤니티 반응 글이라도, 제목 약칭과 강한 canonical evidence가 결속되면 역제동을 면제
        # 목적: "괴담동", "죽깨수"처럼 본문은 팬 반응/밈 톤이지만 작품 식별은 명확한 경우 보호
        if not evidence_found and discourse_warning:
            _dw_lower = str(discourse_warning).lower()
            _is_banterish_warning = any(
                marker in _dw_lower
                for marker in ("memes_humor", "community_banter", "association_post", "non_novel(")
            )
            if _is_banterish_warning:
                _snippet_hints = getattr(ctx, "snippet_hints", None) or {}
                _official_sources = {
                    "url_fetch_platform",
                    "platform_title",
                    "url_fetch",
                    "author_bridge",
                    "alias_bridge",
                    "llm_snippet",
                }

                def _canonical_support_counts(_title: str) -> tuple[int, int, int]:
                    _title_norm = _normalize_alnum_kor_cached(_title)
                    if not _title_norm:
                        return 0, 0, 0
                    _hint_support = 0
                    for _th in (_snippet_hints.get("title_hints") or []):
                        if not isinstance(_th, dict):
                            continue
                        if str(_th.get("source", "") or "") not in _official_sources:
                            continue
                        if _normalize_alnum_kor_cached(str(_th.get("title", "") or "")) == _title_norm:
                            _hint_support += 1
                    for _ah in (_snippet_hints.get("abbreviation_hints") or []):
                        if not isinstance(_ah, dict):
                            continue
                        if str(_ah.get("source", "") or "") not in _official_sources:
                            continue
                        if _normalize_alnum_kor_cached(str(_ah.get("full", "") or "")) == _title_norm:
                            _hint_support += 1

                    _official_hits = 0
                    _wiki_hits = 0
                    for _sr in (getattr(ctx, "search_results", None) or [])[:60]:
                        _sr_title_norm = _normalize_alnum_kor_cached(str(_sr.get("title") or ""))
                        _sr_url = str(_sr.get("url") or "")
                        if not _sr_title_norm or _title_norm not in _sr_title_norm:
                            continue
                        try:
                            from urllib.parse import urlparse as _urlparse_dw
                            _host = (_urlparse_dw(_sr_url).hostname or "").lower()
                        except Exception:
                            _host = ""
                        if "namu.wiki" in _host:
                            _wiki_hits += 1
                        elif any(_host == d or _host.endswith("." + d) for d in OFFICIAL_PLATFORM_DOMAINS):
                            _official_hits += 1
                    return _hint_support, _official_hits, _wiki_hits

                for term in result.get("decoded_terms", []):
                    if not isinstance(term, dict):
                        continue
                    best = term.get("best_match") or {}
                    title = str(best.get("title") or "").strip()
                    conf = str(best.get("confidence") or "").lower()
                    if not title or conf not in ("high", "medium"):
                        continue
                    grounding = term.get("grounding") or {}
                    anchor_type = str(grounding.get("anchor_type") or "").lower()
                    orig_norm = _normalize_alnum_kor_cached(str(term.get("original") or ""))
                    title_norm = _normalize_alnum_kor_cached(title)
                    title_line_norm = _normalize_alnum_kor_cached(str(post_data_local.get("title") or ""))
                    alias_in_title = bool(
                        (orig_norm and orig_norm in title_line_norm)
                        or (title_norm and title_norm in title_line_norm)
                    )
                    hint_support, official_hits, wiki_hits = _canonical_support_counts(title)
                    if (
                        alias_in_title
                        and anchor_type in {"title_mention", "character_title_link", "character_mention"}
                        and (
                            (official_hits >= 1 and (wiki_hits >= 1 or hint_support >= 2))
                            or (official_hits >= 2)
                            or (hint_support >= 3 and wiki_hits >= 2)
                        )
                    ):
                        evidence_found = True
                        print(
                            f"[{_ts()}][{self.emoji}] 🔒 Discourse 역방향 제동 면제: "
                            f"밈/반응글이지만 canonical evidence 충분 "
                            f"('{title}', hints={hint_support}, official={official_hits}, wiki={wiki_hits}, anchor={anchor_type or 'none'})",
                            file=sys.stderr,
                        )
                        break

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
            best = term.get("best_match") or {}
            if not isinstance(best, dict):
                continue
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
                    if self._is_platform_branding_title(extracted_title):
                        continue
                    # 불필요한 접미사 제거
                    extracted_title = re.sub(r'\s*\(r\d+\s*판\)$', '', extracted_title)
                    _cleaned_candidates = self._clean_search_result_title(extracted_title)
                    _added = False
                    for _cand in _cleaned_candidates:
                        if len(_cand) >= 3 and len(_cand) <= 50 and (not self._is_platform_branding_title(_cand)):
                            official_titles.append({
                                "title": _cand,
                                "platform": platform,
                                "url": url,
                            })
                            _added = True
                    if _added:
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
                        if self._is_platform_branding_title(decoded_path):
                            continue
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
            if len(clean_title) >= 3 and len(clean_title) <= 80 and " - " not in clean_title:
                _cleaned_candidates = self._clean_search_result_title(clean_title)
                for _cand in _cleaned_candidates:
                    if len(_cand) >= 3 and len(_cand) <= 50 and (not self._is_platform_branding_title(_cand)):
                        official_titles.append({
                            "title": _cand,
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
                        if self._is_platform_branding_title(extracted):
                            continue
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

        official_titles = [
            o for o in official_titles
            if isinstance(o, dict)
            and isinstance(o.get("title"), str)
            and (not self._is_platform_branding_title(o.get("title", "")))
        ]
        if not official_titles:
            return "" if self._is_platform_branding_title(llm_title) else llm_title
        
        from difflib import SequenceMatcher
        from collections import Counter
        import re
        
        llm_title_normalized = llm_title.strip()
        llm_title_compact = re.sub(r"[^\w가-힣]", "", llm_title_normalized).lower()
        
        # 🔥 Step 0: LLM 제목이 검색 결과에 정확히 존재하면 교정 불필요
        for official in official_titles:
            if llm_title_normalized == official["title"].strip():
                return llm_title_normalized

        # 🔧 일반형 확장 보정:
        # LLM이 검색 키워드/짧은 축약(예: "즉사기")만 반환한 경우,
        # 공식 플랫폼에서 더 긴 정식 제목(예: "즉사기 들고 무림에 떨어지다")으로 확장한다.
        # 하드코딩 없이, "짧은 제목이 긴 공식 제목의 선두/핵심 부분과 일치"할 때만 적용.
        if 2 <= len(llm_title_normalized) <= 6 and llm_title_compact:
            expansion_candidates = []
            for official in official_titles:
                official_title = str(official.get("title") or "").strip()
                if not official_title:
                    continue
                official_compact = re.sub(r"[^\w가-힣]", "", official_title).lower()
                if len(official_compact) <= len(llm_title_compact):
                    continue

                first_token = official_title.split()[0] if official_title.split() else official_title
                first_token_compact = re.sub(r"[^\w가-힣]", "", first_token).lower()

                # 짧은 제목이 정식 제목의 첫 토큰 또는 선두 부분과 맞아야 함
                prefix_match = (
                    first_token_compact == llm_title_compact
                    or official_compact.startswith(llm_title_compact)
                )
                if not prefix_match:
                    continue

                # 검색 소스 신뢰도 반영 (공식 플랫폼 + content_field 우대)
                platform_bonus = 0.12 if any(
                    p in str(official.get("platform", "")).lower() for p in OFFICIAL_PLATFORMS
                ) else 0.0
                source_bonus = 0.12 if str(official.get("source", "")) == "content_field" else 0.0
                sim_bonus = 0.16 * SequenceMatcher(
                    None, llm_title_compact, first_token_compact
                ).ratio()
                score = 0.70 + platform_bonus + source_bonus + sim_bonus
                expansion_candidates.append((score, official_title))

            if expansion_candidates:
                expansion_candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_title = expansion_candidates[0]
                second_score = expansion_candidates[1][0] if len(expansion_candidates) > 1 else -1.0
                # 상위 후보가 충분히 강하고(>=0.82), 2위와 간격이 있으면 확정
                if best_score >= 0.82 and (best_score - second_score >= 0.08):
                    if best_title != llm_title_normalized:
                        print(
                            f"[{_ts()}][{self.emoji}] ⚠️ 짧은 제목 확장 교정: "
                            f"LLM='{llm_title_normalized}' → 공식='{best_title}' "
                            f"(score={best_score:.2f}, gap={best_score-second_score:.2f})",
                            file=sys.stderr,
                        )
                    return best_title
        
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
            # 단, 짧은 제목 확장 보정(위 블록)은 이미 처리했으므로 여기서는 기존 기준 유지.
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
        
        if self._is_platform_branding_title(llm_title):
            return ""
        return llm_title

    def _auto_promote_high_fit_interpretation(
        self,
        result: Dict[str, Any],
        ctx: Any,
    ) -> Dict[str, Any]:
        """
        다중해석 자동 승격: best_match가 비어있지만 interpretations에
        novel_title + context_fit=high인 해석이 있으면 자동 승격.
        
        문제 상황:
        - Decoder가 "즉사무림" → interpretations에 "즉사기 들고 무림에 떨어지다"(novel_title, fit=high)를
          기록하면서도 best_match.title=null을 반환하는 경우
        - 이 경우 downstream(Synthesizer)이 null을 보고 엉뚱한 작품 환각
        
        해결:
        - best_match.title이 null이고 interpretations에 novel_title+high가 있으면
          → best_match를 해당 해석으로 승격, confidence=medium
        """
        decoded_terms = result.get("decoded_terms", [])
        if not decoded_terms:
            return result
        
        for term in decoded_terms:
            if not isinstance(term, dict):
                continue
            
            best_match = term.get("best_match") or {}
            # best_match에 이미 제목이 있으면 스킵
            if best_match.get("title"):
                continue
            
            interps = term.get("interpretations") or []
            # novel_title + context_fit=high인 해석 찾기
            best_interp = None
            best_fit = None
            for interp in interps:
                if not isinstance(interp, dict):
                    continue
                if interp.get("type") != "novel_title":
                    continue
                fit = interp.get("context_fit", "low")
                value = interp.get("value", "")
                if not value:
                    continue
                if fit == "high":
                    best_interp = interp
                    best_fit = fit
                    break  # high가 있으면 바로 사용
                elif fit == "medium" and not best_interp:
                    best_interp = interp
                    best_fit = fit
            
            if best_interp and best_fit == "high":
                promoted_title = best_interp["value"]
                
                # 🛡️ 자기참조 차단: 약칭 자체를 정식 제목으로 승격하는 것은 무의미
                # 예: original="즉사무림", value="즉사무림" → 약칭을 디코딩하지 못한 것
                import re as _re_ap
                _orig_norm = _re_ap.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', str(term.get('original', ''))).lower()
                _prom_norm = _re_ap.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', promoted_title).lower()
                if _orig_norm and _prom_norm and (_orig_norm == _prom_norm or _prom_norm in _orig_norm or _orig_norm in _prom_norm):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 자동 승격 차단 (자기참조): "
                        f"'{term.get('original', '?')}' → '{promoted_title}' (약칭=값, 스킵)",
                        file=sys.stderr,
                    )
                    continue
                
                # 🛡️ 약칭 정합성 차단: 고적합 해석이라도 약칭 매칭이 낮으면 승격 금지
                # ("즉사무림" → "즉사기 들고 게임 속으로" 같은 드리프트 방지)
                _abbr_score = abbreviation_match_score(term.get("original", ""), promoted_title)
                _orig_norm = _re_ap.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', str(term.get('original', ''))).lower()
                _prom_norm = _re_ap.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', promoted_title).lower()
                _known_map = {
                    _re_ap.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', k).lower():
                    _re_ap.sub(r'[^\uac00-\ud7a3A-Za-z0-9]', '', v).lower()
                    for k, v in KNOWN_ABBREVIATIONS.items()
                }
                _known_match = bool(_orig_norm and _known_map.get(_orig_norm) == _prom_norm)
                _known_match_has_anchor = _known_match and self._has_known_abbreviation_independent_anchor(
                    ctx,
                    term.get("original", ""),
                    promoted_title,
                    search_results=getattr(ctx, "search_results", []) if ctx else [],
                    term=term,
                )

                # 🛡️ 도메인 충돌 차단: 약어의 세계관 신호와 승격 후보가 충돌하면 스킵
                if _has_domain_conflict_for_mapping(term.get("original", ""), promoted_title):
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 자동 승격 차단 (도메인 충돌): "
                        f"'{term.get('original', '?')}' → '{promoted_title}'",
                        file=sys.stderr,
                    )
                    continue

                if _abbr_score < 0.35 and not _known_match_has_anchor:
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 자동 승격 차단 (약칭 정합성 낮음): "
                        f"'{term.get('original', '?')}' → '{promoted_title}' "
                        f"(score={_abbr_score:.2f}, known_anchor={bool(_known_match_has_anchor)})",
                        file=sys.stderr,
                    )
                    continue
                
                promoted_conf = "medium"  # 자동 승격이므로 한 단계 낮은 confidence
                
                # best_match 승격
                term["best_match"] = {
                    "title": promoted_title,
                    "confidence": promoted_conf,
                    "is_grounded": best_match.get("is_grounded", False),
                    "_auto_promoted": True,
                    "_promotion_source": "high_fit_interpretation",
                }
                
                # overall_confidence도 비어있으면 설정
                if not result.get("overall_confidence") or result.get("overall_confidence") in ("none", ""):
                    result["overall_confidence"] = promoted_conf
                
                # overall_best_match도 비어있으면 설정
                if not result.get("overall_best_match") or not (result.get("overall_best_match") or {}).get("title"):
                    result["overall_best_match"] = {
                        "title": promoted_title,
                        "confidence": promoted_conf,
                    }
                
                print(
                    f"[{_ts()}][{self.emoji}] 🆙 다중해석 자동 승격: "
                    f"'{term.get('original', '?')}' → '{promoted_title}' "
                    f"(fit=high → conf={promoted_conf})",
                    file=sys.stderr,
                )
        
        return result

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

        # 🆕 제목 기준 앵커 토큰 추출 (드리프트 방지용)
        # - 게시글 제목에 실제로 등장하는 key_term 중 가장 긴 토큰을 우선 앵커로 사용
        # - "스포" 같은 접두 태그는 제외
        _gk_key_terms = gatekeeper_result.get("key_terms", []) or []
        _gk_clues = gatekeeper_result.get("context_clues", {}) or {}
        _prefix_tags = {
            str(t).lower().replace(" ", "")
            for t in (_gk_clues.get("genre_prefix_tags") or [])
            if isinstance(t, str)
        }
        _title_anchor_candidates: list[str] = []
        _post_title_norm = post_title.lower().replace(" ", "")
        # 역할어/메타어가 제목 앵커를 오염시키는 경우를 줄이기 위한 최소 stop set
        _anchor_stop_tokens = {
            "작가", "작가의", "작가가", "작가님", "작가님이",
            "스포", "스포일러",
        }
        for _kt in _gk_key_terms:
            if not isinstance(_kt, str):
                continue
            # "담텔기 작가" 같은 복합 키워드는 분해해서 앵커 후보를 만든다.
            # 결합어("담텔기작가") 하나로 쓰면 실제 작품 앵커가 약해질 수 있다.
            _parts = [_kt]
            if " " in _kt:
                _parts.extend([p for p in _kt.split() if p])
            for _part in _parts:
                _part_norm = str(_part).lower().replace(" ", "")
                if len(_part_norm) < 2:
                    continue
                if _part_norm in _prefix_tags:
                    continue
                if _part_norm in _anchor_stop_tokens:
                    continue
                if _part_norm in _post_title_norm:
                    _title_anchor_candidates.append(_part_norm)
        _title_anchor_candidates = sorted(set(_title_anchor_candidates), key=len, reverse=True)
        _title_anchor_term = _title_anchor_candidates[0] if _title_anchor_candidates else ""

        def _pick_embedded_anchor_token(raw_term: str, candidate_title: str) -> str:
            raw = str(raw_term or "").strip()
            if not raw or not candidate_title:
                return ""
            title_norm = _normalize_alnum_kor_cached(candidate_title)
            best_token = ""
            best_score = 0.0
            for tok in _re.findall(r"[가-힣A-Za-z0-9]{2,12}", raw):
                tok = str(tok or "").strip()
                tok_norm = _normalize_alnum_kor_cached(tok)
                if len(tok_norm) < 2:
                    continue
                score = max(
                    abbreviation_match_score(tok, candidate_title),
                    _leading_jamo_title_direct_score(tok, candidate_title),
                )
                if tok_norm in title_norm:
                    score = max(score, 0.80)
                if score >= 0.72 and score > best_score:
                    best_token = tok
                    best_score = score
            return best_token

        def _has_explicit_alias_signal(surface: str, candidate_title: str) -> bool:
            surface_norm = _normalize_alnum_kor_cached(surface)
            title_norm = _normalize_alnum_kor_cached(candidate_title)
            if not surface_norm or not title_norm:
                return False
            alias_cues = ("약칭", "통칭", "줄여서", "줄임말")
            for sr in (getattr(ctx, "search_results", []) or [])[:40]:
                if not isinstance(sr, dict):
                    continue
                sr_url = str(sr.get("url") or "").lower()
                sr_text_raw = f"{sr.get('title', '')} {sr.get('content', '')} {sr.get('snippet', '')}"
                sr_text_norm = _normalize_alnum_kor_cached(sr_text_raw)
                if surface_norm not in sr_text_norm or title_norm not in sr_text_norm:
                    continue
                if not any(cue in sr_text_raw for cue in alias_cues):
                    continue
                if self._is_novel_platform_url(sr_url) or "namu.wiki" in sr_url:
                    return True
            return False
        
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
            
            # 🔧 title_clean, original_term을 루프 상단에서 미리 계산
            title_clean = title.replace(" ", "").lower()
            original_term = (term.get("original") or "").replace(" ", "").lower()
            
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
            
            # 🆕 1-B) 게시글 제목 = 본문의 시작점 원칙
            # snippet_analyzer가 약칭 매핑을 확인하고, 그 약칭이 게시글 제목에 있으면
            # → 제목 자체가 작품 지칭이므로 본문증거 가드 스킵
            # 예: 제목 "즉사무림이유백 미래가 벌써 보이네" → snippet_analyzer가
            #     '즉사무림이유백'='즉사기 들고 무림에 떨어지다' 매핑 확인
            #     → 제목에서 작품을 직접 언급하므로 본문이 짧아도 작품 관련 게시글
            _snippet_abbrev_in_title = False
            if ctx and not _has_temporal_in_post_title:
                _sh = getattr(ctx, 'snippet_hints', None)
                if _sh:
                    _abbrev_hints = _sh.get('abbreviation_hints', []) or []
                    for _abh in _abbrev_hints:
                        _abh_abbrev = (_abh.get('abbrev') or '').replace(' ', '').lower()
                        _abh_full = (_abh.get('full') or '').replace(' ', '').lower()
                        # 약칭이 게시글 제목에 있고, 매핑된 정식 제목이 현재 매칭 제목과 일치하더라도
                        # 현재 term(original_term) 자체가 제목-origin 약칭일 때만 스킵 허용.
                        # (캐릭터 term까지 스킵되면 작품 드리프트가 고착됨)
                        if (_abh_abbrev and _abh_full
                                and _abh_abbrev in _post_title_lower
                                and _abh_full == title_clean
                                and original_term
                                and original_term in _post_title_lower
                                and (
                                    original_term == _abh_abbrev
                                    or _abh_abbrev in original_term
                                    or original_term in _abh_abbrev
                                )):
                            _snippet_abbrev_in_title = True
                            break
            
            if _snippet_abbrev_in_title:
                # 🛡️ 도메인 충돌(예: 무림↔게임)에서는 snippet 약칭 매핑 스킵을 허용하지 않음
                # 핵심: snippet_analyzer가 커뮤니티 잡음으로 잘못 만든 약칭 매핑이
                # 본문증거 가드를 우회해 오매칭을 고착시키는 경로 차단.
                _snippet_domain_conflict = _has_domain_conflict_for_mapping(original_term, title)
                if _snippet_domain_conflict:
                    print(
                        f"[{_ts()}][{self.emoji}] 🚫 본문증거 가드 스킵 거부 (도메인 충돌): "
                        f"'{original_term}' → '{title}' "
                        f"(snippet 약칭 매핑 존재하나 domain_conflict=True)",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵 (게시글 제목=본문 시작점): "
                        f"'{original_term}' → '{title}' "
                        f"(snippet_analyzer 약칭 매핑이 게시글 제목에 존재)",
                        file=sys.stderr,
                    )
                    continue

            # 🆕 1-C) 캐릭터 term이 제목 기준 앵커와 충돌하는 작품으로 매핑되면 강등+차단
            # 핵심: "즉사무림" 토론인데 캐릭터 term이 다른 작품으로 흘러가는 드리프트 차단
            grounding_info = term.get("grounding") or {}
            is_character_term = grounding_info.get("anchor_type") == "character_mention"
            # 🆕 BUG-C 방어: 작품 제목/약칭 term은 캐릭터 드리프트 대상이 아님
            # anchor_type=character_mention은 "이 term이 캐릭터 이름"이 아니라
            # "이 term은 캐릭터 언급에 의해 근거됨"을 의미할 수 있음
            # 예: "망겜성"은 작품 약칭이지만 "황건욱"(캐릭터) 언급으로 근거됨
            if is_character_term:
                _primary_interps = term.get("interpretations") or []
                _primary_type = ""
                if _primary_interps and isinstance(_primary_interps[0], dict):
                    _primary_type = _primary_interps[0].get("type", "")
                _work_interp_types = {
                    "novel_title", "work_abbreviation", "abbreviation",
                    "title_abbreviation", "novel_abbreviation",
                }
                if _primary_type in _work_interp_types:
                    is_character_term = False
            if is_character_term and _title_anchor_term and confidence in ("high", "medium"):
                _raw_original_surface = str(term.get("original") or "")
                _effective_title_anchor_term = ""
                _snippet_hints_local = getattr(ctx, "snippet_hints", None) or {}
                for _ah_local in (_snippet_hints_local.get("abbreviation_hints") or []):
                    if not isinstance(_ah_local, dict):
                        continue
                    _ab_local = str(_ah_local.get("abbrev") or "").strip()
                    _full_local = str(_ah_local.get("full") or "").strip()
                    if not _ab_local or not _full_local:
                        continue
                    if _normalize_alnum_kor_cached(_full_local) != _normalize_alnum_kor_cached(title):
                        continue
                    _ab_local_norm = _normalize_alnum_kor_cached(_ab_local)
                    if _ab_local_norm and (
                        _ab_local_norm in _normalize_alnum_kor_cached(_raw_original_surface)
                        or _ab_local_norm in _post_title_norm
                    ):
                        _effective_title_anchor_term = _ab_local
                        break
                if not _effective_title_anchor_term:
                    _effective_title_anchor_term = _pick_embedded_anchor_token(_raw_original_surface, title) or _title_anchor_term
                anchor_score = abbreviation_match_score(_effective_title_anchor_term, title)
                _explicit_alias_signal = _has_explicit_alias_signal(_effective_title_anchor_term, title)
                if (
                    _effective_title_anchor_term
                    and _effective_title_anchor_term in full_text_lower
                    and _explicit_alias_signal
                ):
                    print(
                        f"[{_ts()}][{self.emoji}] 🔒 캐릭터 드리프트 가드 스킵: "
                        f"term='{original_term}', title='{title}' "
                        f"(anchor='{_effective_title_anchor_term}', explicit_alias_signal=True)",
                        file=sys.stderr,
                    )
                    continue
                if anchor_score < 0.30:
                    old_conf = confidence
                    best["confidence"] = "none"
                    best["title"] = None
                    best["_title_anchor_conflict"] = True
                    # 같은 캐릭터 term의 candidate도 드리프트 제목이면 비활성화
                    for _cand in (term.get("candidates") or []):
                        if not isinstance(_cand, dict):
                            continue
                        _cand_title = _cand.get("official_novel_title")
                        if not _cand_title:
                            continue
                        _cand_score = abbreviation_match_score(_effective_title_anchor_term, _cand_title)
                        if _cand_score < 0.30:
                            _cand["official_novel_title"] = None
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 캐릭터 드리프트 가드: "
                        f"term='{original_term}', title='{title}' "
                        f"(title_anchor='{_effective_title_anchor_term}', score={anchor_score:.2f}) "
                        f"→ confidence {old_conf}→none, title 제거",
                        file=sys.stderr,
                    )
                    changed = True
                    # title이 제거되었으므로 이후 본문증거 가드 로직은 스킵
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
            _is_episode_like_term = bool(_re.fullmatch(r"\d{1,4}(?:화|호|회|회차)", original_term))
            _anchor_score_for_term = (
                abbreviation_match_score(_title_anchor_term, title)
                if _title_anchor_term else 1.0
            )
            _same_as_title_anchor = bool(
                _title_anchor_term and (
                    original_term == _title_anchor_term
                    or original_term in _title_anchor_term
                    or _title_anchor_term in original_term
                )
            )
            _anchor_conflict_for_term = bool(
                _title_anchor_term
                and not _same_as_title_anchor
                and _anchor_score_for_term < 0.45
            )
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
                # 회차형 토큰(예: 305호/12화)이 제목 앵커와 충돌하면
                # 캐릭터 동반 검색 히트만으로 단일 작품 확정하지 않는다.
                if _is_episode_like_term and _anchor_conflict_for_term:
                    old_conf = str(best.get("confidence", "none")).lower()
                    if old_conf in ("high", "max", "very_high"):
                        best["confidence"] = "low"
                    best["_title_anchor_conflict"] = True
                    print(
                        f"[{_ts()}][{self.emoji}] 🛡️ 회차형 약칭 충돌 가드: "
                        f"'{original_term}' → '{title}' "
                        f"(title_anchor='{_title_anchor_term}', score={_anchor_score_for_term:.2f}) "
                        f"→ 캐릭터검증 단독 승격 차단",
                        file=sys.stderr,
                    )
                    changed = True
                    if ctx:
                        if not hasattr(ctx, 'verified_character_work_links'):
                            ctx.verified_character_work_links = []
                        _link_entry = {
                            "abbreviation": original_term,
                            "title": title,
                            "source": "decoder",
                            "_weak_match": True,
                        }
                        _existing = [
                            v for v in ctx.verified_character_work_links
                            if str(v.get("title") or "").replace(" ", "").lower() == title_clean
                        ]
                        if not _existing:
                            ctx.verified_character_work_links.append(_link_entry)
                    # 본문증거 가드를 계속 적용하기 위해 스킵하지 않는다.
                    has_character_verified_in_search = False

            if has_character_verified_in_search:
                # 🔧 FIX: 캐릭터-작품 연결이 검증되었더라도, 약어↔제목 형태소가 불일치이면
                # "경쟁 작품 오매칭" 위험이 있으므로 경고 플래그를 남김
                # 예: "즉사무림 서무량" 검색 → n번째 결과에 "즉사기 들고 게임 속으로"와 함께 나옴
                #     → 서무량이 이 작품의 캐릭터로 검증됨
                #     → 하지만 "즉사무림"의 형태소 ['즉사','무림']이 제목에 맞지 않음
                #     → 실제로는 "즉사기 들고 무림에 떨어지다"의 캐릭터일 가능성이 높음
                _char_verify_abbr_score = abbreviation_match_score(original_term, title) if original_term else 0.0
                _char_verify_morphemes = []
                # original_term의 형태소를 best_match에서 가져오기
                for _dt in decoded_terms:
                    if _dt.get("original") == original_term:
                        _char_verify_morphemes = _dt.get("morphemes", [])
                        break
                _char_verify_morph_ok = True
                if _char_verify_morphemes and len(_char_verify_morphemes) >= 2:
                    _tn_cv = title.replace(" ", "")
                    _char_verify_morph_ok = all(m in _tn_cv for m in _char_verify_morphemes)
                
                if _char_verify_abbr_score < 0.3 and not _char_verify_morph_ok:
                    print(
                        f"[{_ts()}][{self.emoji}] ⚠️ 캐릭터-작품 연결 검증됨이지만 약어 불일치: "
                        f"'{original_term}' → '{title}' (abbr_score={_char_verify_abbr_score:.2f}, "
                        f"morpheme_ok={_char_verify_morph_ok}) → 경쟁 작품 오매칭 가능성 있음",
                        file=sys.stderr,
                    )
                    # 🔥 abbr_score=0.0이면 형태소 연결이 전혀 없음 → confidence 강제 하향
                    if _char_verify_abbr_score < 0.1:
                        for _dt in decoded_terms:
                            _bm = _dt.get("best_match") or {}
                            if str(_bm.get("title") or "").replace(" ", "").lower() == title_clean:
                                old_conf = _bm.get("confidence", "")
                                if old_conf in ("high", "max", "very_high"):
                                    _bm["confidence"] = "low"
                                    _bm["_abbr_mismatch_downgrade"] = True
                                    print(
                                        f"[{_ts()}][{self.emoji}] 🔒 약어 완전불일치 → confidence 강제하향: "
                                        f"'{original_term}' → '{title}' ({old_conf}→low)",
                                        file=sys.stderr,
                                    )
                        # overall_confidence도 하향
                        if result.get("overall_confidence") in ("high", "max", "very_high"):
                            result["overall_confidence"] = "low"
                    # 검증은 저장하되, confidence를 하향하여 경쟁 작품 탐색 유도
                    if ctx:
                        if not hasattr(ctx, 'verified_character_work_links'):
                            ctx.verified_character_work_links = []
                        _link_entry = {
                            "abbreviation": original_term,
                            "title": title,
                            "source": "decoder",
                            "_weak_match": True,  # 약어 불일치 플래그
                        }
                        _existing = [
                            v for v in ctx.verified_character_work_links
                            if str(v.get("title") or "").replace(" ", "").lower() == title_clean
                        ]
                        if not _existing:
                            ctx.verified_character_work_links.append(_link_entry)
                            print(
                                f"[{_ts()}][{self.emoji}] 📌 ctx.verified_character_work_links 저장 (약한 매칭): "
                                f"'{original_term}' → '{title}'",
                                file=sys.stderr,
                            )
                    # 가드 스킵하지 않고 계속 진행 → 나중에 본문증거 가드가 veto 가능
                else:
                    print(
                        f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵: "
                        f"'{original_term}' → '{title}' (본문 캐릭터가 작품 등장인물로 검색 검증됨)",
                        file=sys.stderr,
                    )
                    # 🆕 ctx에 검증 사실 영구 저장 (다중호출 시 마지막 결과가 덮어써도 유지)
                    if ctx:
                        if not hasattr(ctx, 'verified_character_work_links'):
                            ctx.verified_character_work_links = []
                        _link_entry = {
                            "abbreviation": original_term,
                            "title": title,
                            "source": "decoder",
                        }
                        # 중복 방지
                        _existing = [
                            v for v in ctx.verified_character_work_links
                            if str(v.get("title") or "").replace(" ", "").lower() == title_clean
                        ]
                        if not _existing:
                            ctx.verified_character_work_links.append(_link_entry)
                            print(
                                f"[{_ts()}][{self.emoji}] 📌 ctx.verified_character_work_links 저장: "
                                f"'{original_term}' → '{title}'",
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
            _effective_guard_term = str(locals().get("effective_original") or original_term).replace(" ", "").lower()
            _embedded_stable_alias = self._find_embedded_stable_alias(
                original_term,
                title,
                possible_characters=gk_characters,
            )
            if _embedded_stable_alias:
                _effective_guard_term = _embedded_stable_alias.replace(" ", "").lower()
                print(
                    f"[{_ts()}][{self.emoji}] 🧩 내장 약칭 복원: "
                    f"'{original_term}' → '{_effective_guard_term}' (title='{title}')",
                    file=sys.stderr,
                )

            # 5-1) 검색 결과에 명시적 약칭 증거가 있으면 본문증거 가드 스킵
            import re as _re_alias
            _alias_terms_for_guard = [original_term]
            if _effective_guard_term and _effective_guard_term not in _alias_terms_for_guard:
                _alias_terms_for_guard.append(_effective_guard_term)
            _alias_patterns = []
            for _alias_term in _alias_terms_for_guard:
                _alias_patterns.extend(
                    [
                        _re_alias.compile(rf'약칭[은이가]?\s*{_re_alias.escape(_alias_term)}'),
                        _re_alias.compile(rf'통칭\s*{_re_alias.escape(_alias_term)}'),
                        _re_alias.compile(rf'줄여서\s*{_re_alias.escape(_alias_term)}'),
                        _re_alias.compile(rf'줄임말[은이가]?\s*{_re_alias.escape(_alias_term)}'),
                    ]
                )
            has_explicit_alias_evidence = False
            for sr in search_results:
                sr_combined = f"{sr.get('title', '')} {sr.get('content', '')}".lower()
                if any(p.search(sr_combined) for p in _alias_patterns):
                    has_explicit_alias_evidence = True
                    break
            
            if has_explicit_alias_evidence:
                # 🛡️ 명시적 약칭 문구가 있어도 도메인 충돌이면 신뢰하지 않는다.
                # (커뮤니티 글의 오염된 "약칭" 설명이 다른 작품으로 드리프트시키는 사례 방지)
                _alias_domain_conflict = _has_domain_conflict_for_mapping(original_term, title)
                if _alias_domain_conflict or (_is_episode_like_term and _anchor_conflict_for_term):
                    print(
                        f"[{_ts()}][{self.emoji}] 🚫 명시적 약칭 스킵 거부: "
                        f"'{original_term}' → '{title}' "
                        f"(domain_conflict={_alias_domain_conflict}, "
                        f"episode_anchor_conflict={_is_episode_like_term and _anchor_conflict_for_term})",
                        file=sys.stderr,
                    )
                else:
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
                guard_term = _effective_guard_term or original_term
                
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
                    abbr_score = max(
                        abbreviation_match_score(original_term, title),
                        abbreviation_match_score(guard_term, title) if guard_term and guard_term != original_term else 0.0,
                    )
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
                    elif abbr_score < 0.01:
                        # 🆕 P1 강화: abbr_score≈0 + 짧은 본문 + 증거 없음 → title=None (모르면 모른다)
                        old_conf = confidence
                        best["confidence"] = "none"
                        best["title"] = None
                        result["overall_confidence"] = "none"
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 가드 (모르면 모른다): "
                            f"'{original_term}' → '{title}' 매칭 차단 "
                            f"(본문 {body_len}자, abbr_score={abbr_score:.2f}≈0, "
                            f"guard_term='{guard_term}', 증거 전무, {old_conf}→none)",
                            file=sys.stderr,
                        )
                        changed = True
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
                else:
                    # 🆕 P1 강화: 일반 본문 (≥50자) + 증거 없음
                    abbr_score_gen = max(
                        abbreviation_match_score(original_term, title),
                        abbreviation_match_score(guard_term, title) if guard_term and guard_term != original_term else 0.0,
                    )
                    if abbr_score_gen < 0.01:
                        # abbr_score≈0 + 본문 증거 0개 → title=None (모르면 모른다)
                        old_conf = confidence
                        best["confidence"] = "none"
                        best["title"] = None
                        result["overall_confidence"] = "none"
                        print(
                            f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 가드 (모르면 모른다/일반): "
                            f"'{original_term}' → '{title}' 매칭 차단 "
                            f"(abbr_score={abbr_score_gen:.2f}≈0 + 작품 증거 전무, {old_conf}→none)",
                            file=sys.stderr,
                        )
                        changed = True
                    elif confidence in ("high",):
                        # High confidence인데 본문 증거 없음 → Medium으로 하향
                        # 예외: 약어 매칭이 강력하면(score≥0.85) 하향 안함
                        if abbr_score_gen >= 0.85:
                            print(
                                f"[{_ts()}][{self.emoji}] 🔒 본문증거 가드 스킵 (강한 약어): "
                                f"'{original_term}' → '{title}' "
                                f"(abbr_score={abbr_score_gen:.2f}≥0.85 → high 유지)",
                                file=sys.stderr,
                            )
                            # high 유지, 변경 없음
                        else:
                            best["confidence"] = "medium"
                            print(
                                f"[{_ts()}][{self.emoji}] 🛡️ 본문증거 가드 (증거 미약): "
                                f"'{original_term}' → '{title}' confidence 하향 "
                                f"(본문에 작품 고유 정보 없음, abbr_score={abbr_score_gen:.2f}, high→medium)",
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

    def _guard_weak_thematic_title_inference(
        self,
        result: Dict[str, Any],
        ctx: Any,
        gatekeeper_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        약칭-정식명 연결 근거 없이, 테마/캐릭터/줄거리 유사성만으로 unrelated 작품명을
        best_match로 올리는 경로를 차단한다.

        핵심 기준:
        - 약칭 정합성 점수가 낮음
        - explicit alias mapping/bridge 근거 없음
        - 본문에 정식 제목 직접 언급 없음
        - grounding이 character/plot/search_only 같은 약한 축
        """
        decoded_terms = result.get("decoded_terms", []) or []
        if not decoded_terms:
            return result

        post_data = getattr(ctx, "post_data", {}) or {}
        comments = getattr(ctx, "comments", []) or []
        post_chunks: List[str] = [str(post_data.get("title") or "")]
        for block in (post_data.get("content_blocks") or []):
            if isinstance(block, dict):
                post_chunks.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                post_chunks.append(block)
        post_chunks.extend([c for c in comments if isinstance(c, str)])
        post_norm = _normalize_alnum_kor_cached(" ".join(post_chunks))
        gk_characters = []
        if isinstance(gatekeeper_result, dict):
            ents = gatekeeper_result.get("detected_entities") or {}
            if isinstance(ents, dict):
                gk_characters = ents.get("possible_characters") or []

        snippet_hints = getattr(ctx, "snippet_hints", None) or {}
        llm_snippet = getattr(ctx, "llm_snippet_analysis", None) or {}
        search_results = getattr(ctx, "search_results", None) or []

        def _has_explicit_alias_support(orig_norm: str, title_norm: str) -> bool:
            if not orig_norm or not title_norm:
                return False

            # Registry pair alone is only recall provenance. Explicit support
            # must come from snippet/search/post evidence below.

            for _ah in (snippet_hints.get("abbreviation_hints") or []):
                if not isinstance(_ah, dict):
                    continue
                if (
                    _normalize_alnum_kor_cached(_strip_korean_particles(str(_ah.get("abbrev") or ""))) == orig_norm
                    and _normalize_alnum_kor_cached(str(_ah.get("full") or "")) == title_norm
                ):
                    return True

            for _am in (llm_snippet.get("abbreviation_mappings") or []):
                if not isinstance(_am, dict):
                    continue
                if (
                    _normalize_alnum_kor_cached(_strip_korean_particles(str(_am.get("abbrev") or ""))) == orig_norm
                    and _normalize_alnum_kor_cached(str(_am.get("full") or "")) == title_norm
                ):
                    return True

            # 같은 검색 결과 blob 안에 약칭과 정식 제목이 같이 등장하면 explicit bridge로 본다.
            for _sr in search_results[:40]:
                _sr_title = str(_sr.get("title") or "")
                _sr_title_norm = _normalize_alnum_kor_cached(_sr_title)
                _sr_url = str(_sr.get("url") or "")
                try:
                    from urllib.parse import urlparse as _urlparse_d
                    _host = (_urlparse_d(_sr_url).hostname or "").lower()
                except Exception:
                    _host = ""
                _official_like = (
                    "namu.wiki" in _host
                    or any(_host == d or _host.endswith("." + d) for d in OFFICIAL_PLATFORM_DOMAINS)
                    or _sr_title_norm == title_norm
                )
                _blob = _normalize_alnum_kor_cached(
                    f"{_sr.get('title', '')} {_sr.get('content', '')} {_sr.get('snippet', '')}"
                )
                if _official_like and orig_norm in _blob and title_norm in _blob:
                    return True
            return False

        def _candidate_evidence_blob(term: Dict[str, Any], title_norm: str) -> str:
            parts: List[str] = []
            for _cand in (term.get("candidates") or []):
                if not isinstance(_cand, dict):
                    continue
                _cand_title_norm = _normalize_alnum_kor_cached(str(_cand.get("official_novel_title") or ""))
                if title_norm and _cand_title_norm and _cand_title_norm != title_norm:
                    continue
                parts.append(str(_cand.get("decode_logic") or ""))
                parts.append(str(_cand.get("search_evidence") or ""))
            for _interp in (term.get("interpretations") or []):
                if not isinstance(_interp, dict):
                    continue
                if _normalize_alnum_kor_cached(str(_interp.get("value") or "")) != title_norm:
                    continue
                parts.append(str(_interp.get("evidence") or ""))
            return _normalize_alnum_kor_cached(" ".join(parts))

        weak_anchor_types = {
            "character_mention",
            "plot_mention",
            "search_only",
            "association",
            "context_inference",
            "none",
        }
        changed = False

        for term in decoded_terms:
            if not isinstance(term, dict):
                continue
            if term.get("is_author_name"):
                continue

            best_match = term.get("best_match") or {}
            title = str(best_match.get("title") or "").strip()
            conf = str(best_match.get("confidence") or "").lower()
            if not title or conf not in ("high", "medium"):
                continue

            original = str(term.get("original") or "").strip()
            original_base = _strip_korean_particles(original) or original
            effective_original = self._find_embedded_stable_alias(
                original,
                title,
                possible_characters=gk_characters,
            ) or original_base
            orig_norm = _normalize_alnum_kor_cached(original_base)
            effective_orig_norm = _normalize_alnum_kor_cached(effective_original)
            title_norm = _normalize_alnum_kor_cached(title)
            if not title_norm or (
                (not orig_norm or len(orig_norm) < 2)
                and (not effective_orig_norm or len(effective_orig_norm) < 2)
            ):
                continue

            # 약칭 자체가 제목 내에 직접 들어 있거나, 본문에 정식 제목이 직접 있으면 유지.
            if (
                orig_norm in title_norm
                or effective_orig_norm in title_norm
                or title_norm in post_norm
                or (effective_orig_norm and effective_orig_norm in post_norm)
            ):
                continue

            abbr_score = max(
                abbreviation_match_score(original_base, title),
                _leading_jamo_title_direct_score(original_base, title),
                abbreviation_match_score(effective_original, title) if effective_original != original_base else 0.0,
                _leading_jamo_title_direct_score(effective_original, title) if effective_original != original_base else 0.0,
            )
            explicit_alias_support = _has_explicit_alias_support(orig_norm, title_norm) or (
                bool(effective_orig_norm) and _has_explicit_alias_support(effective_orig_norm, title_norm)
            )
            low_specific_orig = self._is_low_specificity_mapping_abbrev(original_base, full_title=title)
            if abbr_score >= 0.55:
                if not low_specific_orig:
                    continue

            if explicit_alias_support:
                continue

            grounding = term.get("grounding") or {}
            anchor_type = str(grounding.get("anchor_type") or "none").lower()
            if anchor_type not in weak_anchor_types:
                continue

            evidence_blob = _candidate_evidence_blob(term, title_norm)
            explicit_original_link = bool(orig_norm and orig_norm in evidence_blob)
            if low_specific_orig and not explicit_alias_support:
                explicit_original_link = False

            # 공식 제목이 검색에 존재해도, 약칭과의 explicit bridge가 없고
            # 증거가 줄거리/테마 설명뿐이면 unrelated title 환각으로 본다.
            if (
                (abbr_score < 0.35 and not explicit_original_link)
                or (
                    low_specific_orig
                    and abbr_score < 0.55
                    and not explicit_original_link
                )
            ):
                old_conf = best_match.get("confidence")
                best_match["title"] = None
                best_match["confidence"] = "none"
                best_match["_weak_thematic_rejected"] = True
                best_match["_weak_thematic_reason"] = (
                    f"abbr_score={abbr_score:.2f}, anchor={anchor_type}, low_specific={low_specific_orig}"
                )
                term["_weak_thematic_rejected"] = True
                term["_weak_thematic_reason"] = best_match["_weak_thematic_reason"]
                if isinstance(result.get("overall_best_match"), dict):
                    _overall_title_norm = _normalize_alnum_kor_cached(
                        str((result.get("overall_best_match") or {}).get("title") or "")
                    )
                    if _overall_title_norm == title_norm:
                        result["overall_best_match"] = {"title": None, "confidence": "none"}
                if result.get("overall_confidence") in ("high", "medium"):
                    result["overall_confidence"] = "low"
                print(
                    f"[{_ts()}][{self.emoji}] 🛡️ 약한 테마 추론 차단: "
                    f"'{original}' → '{title}' "
                    f"(score={abbr_score:.2f}, anchor={anchor_type}, conf={old_conf}→none)",
                    file=sys.stderr,
                )
                changed = True

        if changed and hasattr(ctx, "uncertainty_sources"):
            _msg = "decoder: weak thematic title inference rejected"
            if _msg not in ctx.uncertainty_sources:
                ctx.uncertainty_sources.append(_msg)
        return result
