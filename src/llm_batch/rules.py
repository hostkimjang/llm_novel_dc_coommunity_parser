from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Evidence, Inference, NovelIdentity, OutputItem, SlangInsight


URL_PATTERN = re.compile(r"(https?://[^\s)]+)")
# 커뮤니티 밈/문장 속 [단어]를 제목으로 오인하지 않도록, "댓글 전체가 [제목]인 경우"만 제목으로 취급.
TITLE_ONLY_PATTERN = re.compile(r"^\s*\[([^\[\]]{2,60})\]\s*$")

NOVEL_SITES = (
    "novelpia.com",
    "munpia.com",
    "page.kakao.com",
    "kakao.page",
    "joara.com",
    "series.naver.com",
    "ridibooks.com",
)

# 공식 플랫폼 + 위키 (제목 추출 신뢰 소스)
OFFICIAL_PLATFORMS = NOVEL_SITES + (
    "namu.wiki",
)

# 비-소설 매체 플랫폼 (만화/동인지/일러스트 등 — 이 플랫폼 언급이면 noise 시그널)
# 키워드 기반: 본문/제목에 이 단어가 있으면 소설이 아닌 다른 매체를 논하는 글
NON_NOVEL_MEDIA_KEYWORDS: Tuple[str, ...] = (
    # 성인 만화/동인지 플랫폼명
    "히토미", "엔헨", "이헨",
    # 만화/웹툰 플랫폼
    "마루마루", "뉴토끼",
    # 매체명 (만화 관련은 NOISE_TERMS에도 있지만, 여기서는 context와 함께 판단)
)

# 비-소설 매체 URL 도메인 패턴 (검색 결과 URL에 이 도메인이 있으면 비-소설 매체)
NON_NOVEL_MEDIA_DOMAINS: Tuple[str, ...] = (
    "hitomi.la",
    "nhentai.net",
    "e-hentai.org",
    "exhentai.org",
    "pixiv.net",
)

SLANG_DICTIONARY: Dict[str, str] = {
    # 음절 두문자 (첫 글자만 따온 형태) - 형태소 분석으로 유추 불가능한 것들만
    "아카살": "아카데미에서 살아남기",
    "전독시": "전지적 독자 시점",
    # "빌환": "빌어먹을 환생",
    # "죽깨수": "죽었다 깨어도 수선",
    "죽신성": "죽은 신의 성기사",
    "로나좋": "로판 속 주인공이 나만 좋아함",
    "나혼렙": "나 혼자만 레벨업",
    # 아래는 키워드 압축형이므로 Decoder가 검색 결과에서 유추해야 함
    # "즉사무림" → 검색에서 "즉사기 들고 무림에 떨어지다" 찾아서 매칭
    # "회레전" → 검색에서 "회귀한 레전드급 전사" 찾아서 매칭
}

TROPE_TERMS = {
    "학폭 악역": "School Violence Villain (학폭 악역)",
    "똥 안싸는 선협": "Poopless Cultivator (똥 안싸는 선협)",
    "사파 복지": "Evil Sect Welfare (사파 복지)",
}

# ── 장르 키워드 사전 (본문에서 장르를 추출하기 위한 코드 레벨 사전) ──
# 각 장르에 대해 본문에 등장할 수 있는 키워드 목록
# 후보 작품의 장르와 포스트 본문의 장르가 불일치하면 매칭 차단
GENRE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "fantasy": (
        "마왕", "용사", "마법사", "대마법사", "마법", "마나", "드래곤", "엘프",
        "던전", "오크", "몬스터", "기사단", "길드", "아카데미",
        "스킬", "레벨업", "레벨", "각성", "헌터", "게이트",
        "이세계", "빙의", "회귀", "환생", "전생", "소환",
        "도적단", "마탑", "정령", "검성", "검신",
    ),
    "martial_arts": (
        "무림", "무공", "내공", "기연", "사파", "정파", "마교",
        "강호", "문파", "협객", "검법", "장문인", "도법",
        "무림맹", "흑도", "백도", "사형", "제자", "수련",
        "절정고수", "화경", "현경", "천하제일",
    ),
    "romance": (
        "연인", "남주", "여주", "사내", "공작", "후작", "황제",
        "궁전", "무도회", "약혼", "결혼", "이혼", "로맨스",
        "로판", "계약결혼", "빌런",
    ),
    "modern": (
        "회사", "사장", "대표", "직장인", "현대", "서울",
        "아파트", "카페", "학교", "대학",
    ),
}

# ── 장르 아키타입 용어 (작품 제목이 아니라 장르 내 역할/속성 용어) ──
# 이 용어들이 key_terms에 있으면 소설 제목 후보에서 제외해야 함
GENRE_ARCHETYPE_TERMS: Tuple[str, ...] = (
    "초대남", "금태양", "거근쇼타", "거근", "쇼타",
    "NTR", "네토라레", "순애", "하렘",
    "먼치킨", "사이다", "고구마",
    "빌런", "흔막",
    # 장르 약칭 (작품명이 아닌 장르/시취 패턴)
    "현판", "현판물",  # 현대판타지
    "백합난입",  # 백합에 남자 난입 시취
    "회귀물", "환생물", "빙의물", "전생물",
    "막내아들물", "아카데물",
    "무협물", "이세계물", "헌터물",
    "로판", "판무",  # 로맨스판타지, 판타지무협
)

# ── 플랫폼 약칭 (코드 레벨 - 소설 제목이 아닌 플랫폼명) ──
PLATFORM_ABBREVIATIONS: Tuple[str, ...] = (
    "노피아", "노벨피아", "노블피아", "노벨쨩", "피아쨩",
    "문피", "문피아",
    "카카페", "카페이지",
    "시리즈",
    "리디", "리디북스",
    "조아라", "조라",
    "부기피아",
)

# ── 플랫폼 UI/기능 용어 (소설 제목이 아닌 플랫폼 기능) ──
# 플랫폼 약칭 + 이 용어 조합이면 → meta (소설이 아님)
PLATFORM_FEATURE_TERMS: Tuple[str, ...] = (
    "콘", "이모티콘", "스티커", "뱃지", "마크", "칭호",
    "빔", "이펙트", "프사", "표지",
    "뚱라니", "캐시", "쿠폰", "이벤트",
    "고닉", "유동", "갤",
)

# ── 연상 패턴 (제목에서 "X라는 단어가 떠올랐" 등 연상글 감지) ──
# 이 패턴이 제목에 있으면 X는 소설 제목이 아니라 일반 용어일 가능성 높음
ASSOCIATION_PATTERNS: Tuple[str, ...] = (
    "이란 단어가 떠올",
    "라는 단어가 떠올",
    "란 단어가 떠올",
    "이란 말이 떠올",
    "라는 말이 떠올",
    "이 떠올랐",
    "이 생각났",
    "이 생각나",
    "연상됐",
    "연상되",
    "생각나더라",
)

NOISE_TERMS = (
    "글카",
    "채굴",
    "날씨",
    "음식",
    "애니",
    "만화",
    "장붕",
    "완장",
    # 커뮤니티 잡담/메타(웹소설 식별과 무관한 경우가 매우 많음)
    "찐친",
    "찐따",
    "통피",
    "고닉",
    "dc app",
    "dc official app",
    "ip",
)


def _iter_text_sources(
    post_title: str,
    post_texts: Iterable[str],
    comments: Iterable[str],
) -> Iterable[str]:
    yield post_title
    for text in post_texts:
        yield text
    for comment in comments:
        yield comment


def _extract_url_or_title(comments: Iterable[str]) -> Optional[Tuple[str, str]]:
    for comment in comments:
        comment = (comment or "").strip()
        if not comment:
            continue
        url_match = URL_PATTERN.search(comment)
        if url_match:
            url = url_match.group(1)
            if any(site in url for site in NOVEL_SITES):
                return ("url", url)
        # 제목 답변으로 인정하는 패턴: 댓글이 "[제목]" 단독인 경우
        title_match = TITLE_ONLY_PATTERN.match(comment)
        if title_match:
            return ("title", title_match.group(1))
    return None


def _detect_slang(texts: Iterable[str]) -> Optional[Tuple[str, str]]:
    for text in texts:
        for slang, decoded in SLANG_DICTIONARY.items():
            if slang in text:
                return slang, decoded
    return None


def _detect_trope(texts: Iterable[str]) -> Optional[str]:
    for text in texts:
        for term in TROPE_TERMS:
            if term in text:
                return TROPE_TERMS[term]
    return None


def _is_noise(texts: Iterable[str]) -> bool:
    for text in texts:
        for term in NOISE_TERMS:
            if term in text:
                return True
    return False


def apply_rules(
    post_id: int,
    post_title: str,
    post_texts: Iterable[str],
    comments: List[str],
    search_title: Optional[str] = None,
) -> OutputItem:
    text_sources = list(_iter_text_sources(post_title, post_texts, comments))

    evidence = _extract_url_or_title(comments)
    if evidence:
        kind, value = evidence
        official = value
        decoded_term = None
        slang = _detect_slang([post_title])
        if slang:
            decoded_term = (
                f"Linked Novel ({search_title})"
                if search_title
                else f"Linked Novel ({slang[1]})"
            )
        return OutputItem(
            post_id=post_id,
            is_relevant=True,
            novel_identity=NovelIdentity(
                official_title=official,
                confidence="Max",
            ),
            evidence=Evidence(
                found_in_comment=True,
                source_text=value,
            ),
            slang_insight=SlangInsight(
                detected_term=slang[0] if slang else post_title[:10],
                decoded_term=decoded_term,
            )
            if slang
            else None,
        )

    slang = _detect_slang(text_sources)
    if slang:
        return OutputItem(
            post_id=post_id,
            is_relevant=True,
            novel_identity=NovelIdentity(
                official_title=slang[1],
                confidence="High",
            ),
            slang_insight=SlangInsight(
                detected_term=slang[0],
                decoded_term=slang[1],
            ),
        )

    trope = _detect_trope(text_sources)
    if trope:
        return OutputItem(
            post_id=post_id,
            is_relevant=True,
            novel_identity=NovelIdentity(
                official_title=None,
                confidence="None",
            ),
            inference=Inference(
                type="Concept Request",
                topic=trope,
            ),
        )

    if _is_noise(text_sources):
        return OutputItem(
            post_id=post_id,
            is_relevant=False,
            reason="Noise",
        )

    return OutputItem(
        post_id=post_id,
        is_relevant=False,
        reason="Unknown",
    )

