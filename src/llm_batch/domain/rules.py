"""LLM 실행과 독립적인 문자열·장르·근거 판정 규칙.

규칙은 도메인 모델만 사용한다. 검색이나 원장 상태가 필요해지는 판단은 이 파일에
추가하지 않고 상위 grounding 계층에서 처리한다.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Evidence, Inference, NovelIdentity, OutputItem, SlangInsight


# ━━ 3단계 증거등급 (강/중/약) ━━━━━━━━━━━━━━━━━━━━━
# anchor_score 수치화(0~1)는 튜닝 지옥을 유발하므로,
# 이산값 3단계로 유지보수 가능한 증거등급 체계를 사용.
# Gatekeeper→Decoder→Verifier 전 과정에서 사용.

EVIDENCE_GRADE_STRONG = "strong"   # 강: 제목 직접 언급, 플랫폼 URL, 작가명+작품명 동시
EVIDENCE_GRADE_MEDIUM = "medium"   # 중: 캐릭터명+맥락, 약칭 해독 성공, 회차 번호
EVIDENCE_GRADE_WEAK = "weak"       # 약: 장르 키워드만, 마스킹 제목, 단일 캐릭터명

# 등급별 대응하는 앵커 타입 매핑
EVIDENCE_GRADE_MAP = {
    # strong
    "title_mention": EVIDENCE_GRADE_STRONG,
    "author_mention": EVIDENCE_GRADE_STRONG,
    "character_title_link": EVIDENCE_GRADE_STRONG,
    "plot_mention": EVIDENCE_GRADE_STRONG,
    # medium
    "title_abbrev_mention": EVIDENCE_GRADE_MEDIUM,
    "body_abbrev_mention": EVIDENCE_GRADE_MEDIUM,
    "character_mention": EVIDENCE_GRADE_MEDIUM,
    "episode_reference": EVIDENCE_GRADE_MEDIUM,
    "genre_prefix": EVIDENCE_GRADE_MEDIUM,
    "search_confirmed": EVIDENCE_GRADE_MEDIUM,
    # weak
    "search_only": EVIDENCE_GRADE_WEAK,
    "genre_keyword": EVIDENCE_GRADE_WEAK,
    "none": EVIDENCE_GRADE_WEAK,
}


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

# 담론 도메인 정규화용 상수
NOVEL_DOMAINS: Tuple[str, ...] = (
    "novel_literature",
    "novel_work",
    "web_novel",
)

# 웹소설이 아닌 도메인들
# (DiscourseAnalyzer의 primary_domain 값과 연동)
NON_NOVEL_DOMAINS: Tuple[str, ...] = (
    "manga_comics",
    "anime",
    "game",
    "aa_work",
    "vocaloid",
    "vocaloid_song",
    "daily_life",
    "community_banter",
    "memes_humor",
    "real_world",
    "medical_health",
    "technology",
    "sports",
    "off_topic",
    "other",
)


def normalize_domain_tag(domain: str) -> str:
    return str(domain or "").strip().lower()


def is_novel_domain(domain: str) -> bool:
    d = normalize_domain_tag(domain)
    return d in NOVEL_DOMAINS


def is_non_novel_domain(domain: str) -> bool:
    d = normalize_domain_tag(domain)
    if not d:
        return False
    if is_novel_domain(d):
        return False
    if d in NON_NOVEL_DOMAINS:
        return True
    # 명시 목록 외에도, novel이 아닌 확정 도메인은 비소설로 간주
    return d not in {"unknown", "ambiguous", "mixed"}


SURFACE_EXPRESSION_REREAD_PUBLIC_LABEL = "표현 오타/축약 패턴(범용)"
SURFACE_EXPRESSION_REREAD_PUBLIC_STATEMENT = (
    f"{SURFACE_EXPRESSION_REREAD_PUBLIC_LABEL}으로만 보며, "
    "packet-local 원문 재검토 신호이지 특정 정상형이나 작품명/별칭 근거가 아니다."
)
SURFACE_EXPRESSION_REREAD_PUBLIC_NOTE = (
    f"{SURFACE_EXPRESSION_REREAD_PUBLIC_LABEL}으로만 보고, "
    "결정적 치환/전역 규칙/작품명 근거로 쓰지 않는다."
)


SURFACE_EXPRESSION_REREAD_CANDIDATE_RE = re.compile(
    r"(?P<surface>"
    r"(?=[0-9A-Za-z가-힣]{2,24}(?![0-9A-Za-z가-힣]))"
    r"(?:\d+[A-Za-z가-힣]{1,14}|[A-Za-z가-힣]{1,14}\d+[A-Za-z가-힣]{0,14})"
    r"(?:인?\s*줄|인?\s*지|줄|지|같(?:음|다)?|듯|몰랐(?:음)?)?"
    r")"
    r"(?![A-Za-z0-9가-힣])"
)


def surface_expression_reread_notes(text: str) -> List[Dict[str, str]]:
    """Return packet-local non-title semantic hints for rereading surface text.

    These notes are not title/alias block rules and must not be reused as a
    global lexical mapping. They only tell the semantic reread step that a
    surface phrase may be an expression typo, abbreviation, or spacing break in
    the current packet.
    """
    out: List[Dict[str, str]] = []
    seen: set[str] = set()
    for match in SURFACE_EXPRESSION_REREAD_CANDIDATE_RE.finditer(str(text or "")):
        surface = re.sub(r"\s+", "", match.group("surface") or "").strip()
        if not surface:
            continue
        if len(surface) < 2 or surface in seen:
            continue
        seen.add(surface)
        out.append(
            {
                "kind": "expression_typo_abbreviation_or_spacing_candidate",
                "source_surface": surface,
                "role": "non_title_semantic_context",
                "interpretation": "packet_local_expression_reread_candidate",
                "scope": "packet_local_reread_hint",
                "evidence_role": "not_title_or_alias_evidence",
                "pattern_scope": "generic_expression_typo_abbreviation_spacing_pattern",
                "rule_scope": "not_surface_specific_rule",
                "note": SURFACE_EXPRESSION_REREAD_PUBLIC_NOTE,
            }
        )
    return out


def surface_expression_reread_public_notes(notes: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """Return public prompt/reason-safe reread hints without deterministic rewrites.

    Older packets may still carry a ``paraphrase`` field such as a concrete
    ``X -> Y`` reading. For semantic review prompts we expose only the local
    surface and the generic pattern contract so the model does not learn or
    reuse a surface-specific rule.
    """
    out: List[Dict[str, str]] = []
    seen: set[str] = set()
    for note in notes or []:
        if not isinstance(note, dict):
            continue
        source = re.sub(r"\s+", "", str(note.get("source_surface") or "")).strip()
        if not source or source in seen:
            continue
        seen.add(source)
        out.append(
            {
                "kind": str(note.get("kind") or "expression_typo_abbreviation_or_spacing_candidate"),
                "source_surface": source,
                "role": "non_title_semantic_context",
                "interpretation": "packet_local_expression_reread_candidate",
                "scope": "packet_local_reread_hint",
                "evidence_role": "not_title_or_alias_evidence",
                "pattern_scope": "generic_expression_typo_abbreviation_spacing_pattern",
                "rule_scope": "not_surface_specific_rule",
                "note": SURFACE_EXPRESSION_REREAD_PUBLIC_NOTE,
            }
        )
    return out


def has_surface_expression_reread_candidate(text: str) -> bool:
    return bool(surface_expression_reread_notes(text))

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
    # "즉사무림": "즉사기 들고 무림에 떨어지다",
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
# ⚠️ 여기에 없는 "X물" 패턴도 is_genre_물_pattern()으로 자동 감지됨
GENRE_ARCHETYPE_TERMS: Tuple[str, ...] = (
    # ── 캐릭터 역할/속성 ──
    "초대남", "금태양", "거근쇼타", "거근", "쇼타",
    "빌런", "흔막", "먼치킨", "사이다", "고구마",
    "마검사", "파이어볼",
    # ── 장르 약칭 (작품명이 아닌 장르/시취 패턴) ──
    "현판", "로판", "판무",  # 현대판타지, 로맨스판타지, 판타지무협
    "다크판", "하이판",  # 다크판타지, 하이판타지
    "NTR", "네토라레", "순애", "하렘",
    "에로", "19금", "성인",
    "백합난입",  # 백합에 남자 난입 시취
    "농",  # 농(NTR 파생 은어)
    "후타",  # 후타나리 (장르)
    "암타",  # 암컷타입 TS (장르)
    "난입",  # 장르 트로프
    "ts", "TS",  # TS(성전환) 장르
    "bl", "BL", "gl", "GL",
    # ── 장르 통칭 + "물" 형태 (포괄 목록) ──
    # ※ 이 목록에 없어도 is_genre_물_pattern()이 "X물" 자동 감지
    "회귀물", "환생물", "빙의물", "전생물", "루프물",
    "막내아들물", "아카데물", "아카데미물",
    "무협물", "이세계물", "헌터물", "던전물", "타워물", "게임물",
    "현판물", "로판물", "판무물", "빌런물",
    "ts물", "TS물", "암타물", "백합물",
    "일상물", "힐링물", "개그물", "연애물",  # 분위기/톤 장르
    "능력물", "각성물", "성장물", "귀환물", "솔플물",  # 성장/각성 계열
    "학원물", "학교물", "군대물", "궁정물",  # 배경 계열
    "추리물", "미스터리물", "공포물", "호러물", "스릴러물",  # 서스펜스 계열
    "좀비물", "괴수물", "생존물", "디스토피아물",  # 재난/서바이벌 계열
    "재벌물", "정치물", "범죄물", "복수물",  # 사회/복수 계열
    "액션물", "모험물", "전쟁물",  # 액션 계열
    "소년물", "소녀물", "요리물", "음악물", "스포츠물",  # 소재 계열
    "사극물", "시대물", "왕조물",  # 시대극 계열
    "드라마물", "SF물", "먼치킨물",  # 기타 장르+물
    "계략물", "두뇌물", "전략물",  # 지략 계열
    "육성물", "경영물", "건설물",  # 시뮬 계열
    "로맨스물", "로코물", "순정물",  # 로맨스 계열
    "라노벨물", "오버로드물",  # 매체/스타일 계열
    # ── 일반 명사/장르 트로프 ("물" 없는 형태) ──
    "시스템", "상태창", "만담", "스텟", "스킬",
    "타임슬립",
    "스릴러", "호러", "미스터리",
    "드라마", "코미디", "로코",  # 로맨틱코미디
    "하극상", "성장", "복수극", "각성",
    "공략", "육성",
    "라노벨", "라이트노벨",
    # ── 비교/일반 용어 ──
    "하위호환", "상위호환",
    "리뷰", "리뷰어",
    "웹소", "웹소설",
)


def is_genre_물_pattern(term: str) -> bool:
    """한글 1~5자 + '물' 패턴인지 판별 (자동 장르 감지).

    '회귀물', '일상물', '힐링물' 등 GENRE_ARCHETYPE_TERMS에 없는
    새로운 장르명도 패턴으로 자동 차단.
    단, 실제 소설 제목과 충돌할 수 있는 긴 형태(6자+물)는 제외.
    """
    import re
    if not isinstance(term, str):
        return False
    clean = re.sub(r"[^가-힣]", "", term)
    # 1~5자 한글 + "물" 패턴
    if re.fullmatch(r"[가-힣]{1,5}물", clean):
        return True
    return False


# ── DC 커뮤니티 의견 접두사 (작품명이 아닌 게시글 태그 키워드) ──
# "소신발언))" 등에서 추출되는 키워드. 이 키워드가 제목의 '본체'이면 작품명이 아님
DC_OPINION_KEYWORDS: Tuple[str, ...] = (
    "소신발언", "소신", "핫테", "핫테이크",
    "스포", "스포주의", "질문", "잡담", "추천",
    "후기", "리뷰", "정보", "공지", "속보", "토론",
    "궁금", "ㅈㄴ", "어그로",
)

# ── 추천 요청 패턴 키워드 ──
# "X를 보고싶구나", "X 추천좀" 등 추천 요청 게시글 감지
RECOMMENDATION_REQUEST_SUFFIXES: Tuple[str, ...] = (
    "보고싶구나", "보고싶다", "읽고싶다", "읽고싶구나",
    "보고싶은데", "읽고싶은데", "추천좀", "추천해줘", "추천해주세요",
    "추천부탁", "읽을만한거", "볼만한거", "없나", "없냐", "있나", "있냐",
    "찾고있다", "찾고있는데", "알려줘", "알려주세요",
)

# ── 장르 일반론 제목 패턴 (정규식) ──
# "X이나 Y에서 Z", "X에서 Z은", "X에 Y이" 등 장르 토론 구조
# 아래 패턴이 제목에 매칭되면 genre_discussion 가능성 높음
GENRE_DISCUSSION_TITLE_INDICATORS: Tuple[str, ...] = (
    "이나 ",   # "로판이나 웹소에서" → 복수 장르/매체 병렬
    "에서 ",   # 장르 일반론 "X에서 Y은..."
    "의 공통점", "의 차이점", "의 특징",  # 장르 비교/분석
    "에 대해", "에 대한",  # "X에 대한 생각"
    "본적없", "본적 없", "본 적 없", "못봤", "못 봤",  # 부정: 해당 장르 작품 경험 없음
    "있긴한디", "높긴한디", "높긴한데",  # 소재 잠재력 논의
    "왜 없", "왜없",  # "왜 이런 소재 작품이 없는지"
)

# ── 커뮤니티 게시글 접두어 패턴 (작품명이 아닌 게시글 태그/접두어) ──
# 이 패턴으로 시작하는 텍스트에서 접두어를 제거해야 함
COMMUNITY_PREFIX_PATTERNS: Tuple[str, ...] = (
    "소신발언)", "소신발언))", "소신발언 )",
    "스포)", "스포))", "스포 )",
    "추천)", "추천))",
    "질문)", "질문))",
    "정보)", "정보))",
    "후기)", "후기))",
    "잡담)", "잡담))",
    "리뷰)", "리뷰))",
    "토론)", "토론))",
    "공지)", "공지))",
    "속보)", "속보))",
    "ㅈㄴ)",
)

# ── 장르 접두사 태그 (DC 갤러리 사용자 자발적 장르 태그) ──
# 게시글 제목 앞에 "TS)" "챗생사)" 등 장르/작품 접두 태그를 붙이는 관행
# 이 태그는 제목 후보에서 분리하되, 장르 힌트로 보존해야 함
GENRE_PREFIX_TAGS: Tuple[str, ...] = (
    # 장르 태그
    "TS)", "ts)",
    "BL)", "bl)",
    "GL)", "gl)",
    "SF)", "sf)",
    "판무)",
    "현판)",
    "로판)",
    "무협)",
    "헌터)",
    # 작품 약칭 접두 태그 (자주 반복 출현하는 패턴)
    # 이 패턴은 ")" 앞까지를 작품 약칭으로 추출
)

# ── 회차 번호 패턴 (작품 연재 논의 강력 앵커) ──
# "550화", "1234회", "1034일차", "23화차", "100ep" 등
# 이 패턴이 제목/본문에 있으면 특정 작품 연재 논의가 거의 확실
import re as _re
EPISODE_NUMBER_PATTERN = _re.compile(
    r'(\d{1,5})\s*(?:화|회|일차|화차|ep|EP|편|장|권|부|절|챕터|chapter)',
    _re.IGNORECASE,
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
    "수정", "삭제", "내리", "내려",
    "뚱라니", "캐시", "쿠폰", "이벤트",
    "고닉", "유동", "갤",
)

# ── 연상 패턴 (제목에서 "X라는 단어가 떠올랐" 등 연상글 감지) ──
# 이 패턴이 제목에 있으면 X는 소설 제목이 아니라 일반 용어일 가능성 높음
# ── 제목 마스킹 패턴 (ㅁㅁ, ■■ 등 의도적 제목 은폐) ──
# 이 패턴이 제목에 있으면 작품명이 의도적으로 숨겨진 것
# 해독 불가능하므로 Decoder에 과도한 기대를 하지 않아야 함
TITLE_MASKING_PATTERNS: Tuple[str, ...] = (
    "ㅁㅁ", "ㅇㅇ세계", "■■", "□□", "●●", "○○",
    "XX", "xx", "OO",
)

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
                official_title=None,
                confidence="None",
            ),
            slang_insight=SlangInsight(
                detected_term=slang[0],
                decoded_term=slang[1],
                decode_verified=False,
                store_in_slang_db=False,
                store_reason="curated_dictionary_hint_requires_independent_evidence",
            ),
            reason="Unknown",
            reason_lines=[
                "SLANG_DICTIONARY hit is an alias hint, not standalone title evidence.",
            ],
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

