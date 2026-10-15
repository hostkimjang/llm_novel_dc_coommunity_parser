"""독자용 notes·reason의 인물 역할·작가 주장을 원문 단언 범위로 검사하는 순수 계약.

역할 주장과 작가 주장은 같은 절 단언 판정을 공유한다. 원문 절이 글쓴이(댓글 귀속이면
해당 댓글 작성자)의 직접 긍정 단언일 때만 근거로 인정하고, 인용·질문·전언·추정·부정·
철회·직후 정정이 걸리거나 판정이 애매하면 단언이 아닌 것으로 본다. 걸러진 문장은
호출자가 원문과 함께 보존한다(with_source_fallback).

전문가 notes 후보 문장뿐 아니라 validator/후단이 덮어쓴 최종 analysis_notes나 reason 같은
임의 텍스트에도 같은 계약을 적용할 수 있다(check_note_text).
네트워크·모델·파이프라인 상태에 의존하지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Tuple

__all__ = [
    "ClaimScopeSource",
    "ScopeDecision",
    "NoteScopeResult",
    "Clause",
    "split_clauses",
    "clause_assertion",
    "extract_role_claims",
    "source_states_role",
    "author_claim_scope",
    "check_note_sentence",
    "check_note_text",
    "with_source_fallback",
    "contrast_relation_names",
]

# 절별 판정 사유
ASSERTED = "asserted"
QUOTED = "quoted"
QUESTION = "question"
REPORTED = "reported_speech"
SPECULATIVE = "speculative"
NEGATED = "negated"
RETRACTED = "retracted"
CORRECTED = "corrected_next_clause"
NO_STATEMENT = "no_direct_statement"
EXCEEDS = "claim_exceeds_source"
NO_COMMENT_EVIDENCE = "no_comment_evidence"


@dataclass(frozen=True)
class ClaimScopeSource:
    """판정에 쓰는 원문. 역할·작가 근거는 title+body, 댓글 귀속은 comments만 본다."""

    post_title: str = ""
    body_lines: Tuple[str, ...] = ()
    comments: Tuple[str, ...] = ()
    author_names: Tuple[str, ...] = ()

    @classmethod
    def from_parts(
        cls,
        *,
        title: Any = "",
        body_lines: Iterable[Any] = (),
        comments: Iterable[Any] = (),
        author_names: Iterable[Any] = (),
    ) -> "ClaimScopeSource":
        def _comment_text(item: Any) -> str:
            if isinstance(item, dict):
                return str(item.get("content") or "").strip()
            return str(item or "").strip()

        return cls(
            post_title=str(title or "").strip(),
            body_lines=tuple(s for s in (str(x or "").strip() for x in body_lines or ()) if s),
            comments=tuple(s for s in (_comment_text(x) for x in comments or ()) if s),
            author_names=tuple(s for s in (str(x or "").strip() for x in author_names or ()) if s),
        )

    @property
    def post_lines(self) -> Tuple[str, ...]:
        return tuple(x for x in (self.post_title, *self.body_lines) if x)


@dataclass(frozen=True)
class ScopeDecision:
    supported: bool
    reason: str
    kind: str = "none"
    detail: Tuple[str, ...] = ()
    evidence: Optional[str] = None


@dataclass(frozen=True)
class NoteScopeResult:
    text: str
    kept: Tuple[str, ...]
    dropped: Tuple[Tuple[str, ScopeDecision], ...]

    @property
    def filtered(self) -> bool:
        return bool(self.dropped)


@dataclass(frozen=True)
class Clause:
    text: str
    quotes: Tuple[Tuple[int, int], ...]
    terminal: str


# ---------------------------------------------------------------------------
# 절 분리: 인용부 안의 마침표·물음표에서는 끊지 않는다.
_QUOTE_SPAN = re.compile(
    r"“[^”\n]*”|‘[^’\n]*’|「[^」\n]*」|『[^』\n]*』|\"[^\"\n]*\"|'[^'\n]*'"
)
_TERMINATORS = ".!?。;；？！"


def split_clauses(line: str) -> list[Clause]:
    line = str(line or "")
    spans = [(m.start(), m.end()) for m in _QUOTE_SPAN.finditer(line)]

    def inside(k: int) -> bool:
        return any(a <= k < b for a, b in spans)

    clauses: list[Clause] = []

    def add(start: int, stop: int) -> None:
        raw = line[start:stop]
        lead = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if not text:
            return
        begin = start + lead
        body = text.rstrip(_TERMINATORS + " ")
        terminal = text[len(body):].replace(" ", "")
        quotes = tuple(
            (max(a, begin) - begin, min(b, begin + len(text)) - begin)
            for a, b in spans
            if a < begin + len(text) and b > begin
        )
        clauses.append(Clause(text=text, quotes=quotes, terminal=terminal))

    start = i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\n":
            add(start, i)
            start = i = i + 1
            continue
        numeric_dot = ch == "." and 0 < i < n - 1 and line[i - 1].isdigit() and line[i + 1].isdigit()
        # 숫자 표면과 보고된 질문의 보문을 한 절로 보존한다.
        reported_question = ch in "?？" and bool(re.match(
            r"[?？]+[ \t]*(?:이?라고|라며|냐고|하고)(?=\s|물|묻|질문|말|했|하)", line[i:]
        ))
        if ch in _TERMINATORS and not inside(i) and not numeric_dot and not reported_question:
            j = i
            while j < n and line[j] in _TERMINATORS and not inside(j):
                j += 1
            add(start, j)
            start = i = j
            continue
        i += 1
    add(start, n)
    return clauses


def _clauses_of(lines: Sequence[str]) -> list[list[Clause]]:
    return [split_clauses(line) for line in lines]


# ---------------------------------------------------------------------------
# 절 단언 판정. 범주별 형태 규칙이며 인명·작품명에 의존하지 않는다.
# 감탄 어미 '구나'는 질문이 아니다.
_QUESTION_TAIL = re.compile(r"(?:(?<!구)나|냐|니|까|는지|던가|려나|는가|인가|은가)(?:요)?$")
_SPEAKER_PREFIX = re.compile(
    r"댓글|전언|인용|소문|누군가|누가|어떤\s*(?:사람|분|놈|댓)|다른\s*(?:사람|독자|분)"
    r"|친구|지인|사람들|독자들|다들|남들|에\s*따르면|카더라"
)
_CONNECTOR = re.compile(r"^\s*(?:이)?(?:다|라)(?:고|는|며|던)")
_SELF_VIEW = re.compile(r"^(?:본다|봄|보는|봐|보고|보임|생각|느낀|느낌|느껴|판단|평가|감상|의견|믿|확신)")
_HEARSAY_END = re.compile(
    r"^\s*(?:이)?(?:다|라)?\s*(?:카더라|다더라|라더라|하더라|그러더라|하던데|그러던데|던데|더라|래|대)(?![가-힣])"
)
_SPECULATION = re.compile(r"^\s*(?:이)?(?:다|라)?\s*(?:싶|같|듯|줄\s*알|인\s*줄|는\s*줄|것\s*같|거\s*같)")
_NEGATION = re.compile(r"아니|않|없|못\s|(?<![가-힣])안\s|ㄴㄴ|노노")
_SEGMENT_END = re.compile(r"[,，]|지만|는데|은데|던데|으며|면서|고\s|며\s")
_RETRACTION = re.compile(
    r"착각|오해|잘못\s*(?:알|봤|읽)|잘못된\s*(?:말|정보|얘기)|아니었|사실무근|헛소리|낭설|거짓|틀렸"
    r"|틀린\s*(?:말|정보|얘기)|구라|뇌피셜"
)
_CORRECTION_START = re.compile(
    r"^\s*(?:(?:사실|근데|아|정정|수정|다시\s*보니|그건|그게|그거|이건|잠깐)\s*[,，]?\s*)*"
    r"(?:아니다|아님|아니야|아니요|아닙니다|아니었다|아니었음|아니고|아니라|아냐|틀렸다|틀림|틀렸음"
    r"|잘못됐다|잘못\s*알았|잘못된\s*(?:말|정보|얘기)|ㄴㄴ|노노|오해다|오해임|착각이다|착각임|착각했)"
)


def _is_question(clause: Clause) -> bool:
    if "?" in clause.terminal or "？" in clause.terminal:
        return True
    tokens = re.findall(r"[가-힣]+", clause.text)
    return bool(tokens and _QUESTION_TAIL.search(tokens[-1]))


def _reported_after(suffix: str) -> bool:
    if _HEARSAY_END.match(suffix):
        return True
    m = _CONNECTOR.match(suffix)
    if m is None:
        return False
    rest = suffix[m.end():].lstrip()
    word = re.match(r"[가-힣]+", rest)
    return not (word and _SELF_VIEW.match(word.group()))


def clause_assertion(
    clause: Clause,
    start: int,
    end: int,
    next_clause: Optional[Clause] = None,
    *,
    connective_end: bool = False,
) -> str:
    """clause.text[start:end]가 그 절 화자의 직접 긍정 단언인지 판정해 사유를 돌려준다."""
    if any(a <= start < b for a, b in clause.quotes):
        return QUOTED
    if _is_question(clause):
        return QUESTION
    text = clause.text
    prefix, suffix = text[:start], text[end:]
    if _SPEAKER_PREFIX.search(prefix):
        return REPORTED
    if _reported_after(suffix):
        return REPORTED
    if _SPECULATION.match(suffix):
        return SPECULATIVE
    if not connective_end:
        segment = _SEGMENT_END.split(suffix, maxsplit=1)[0]
        if _NEGATION.search(segment):
            return NEGATED
    if _RETRACTION.search(suffix):
        return RETRACTED
    if next_clause is not None and _CORRECTION_START.match(next_clause.text):
        return CORRECTED
    return ASSERTED


# ---------------------------------------------------------------------------
# 역할
_COP = (
    r"(?P<cop>이었다|이었음|였다|였음|이다|입니다|이에요|예요|이야|이고|이며|인데|이지만|이라서|이니까"
    r"|인\s*(?:인물|캐릭터|사람|놈|애)|임|다|야)"
)
# 계사 뒤에는 전언·추정·부정 판정이 볼 수 있는 어미/조사만 허용한다('촌장다운' 등은 제외).
_COP_BOUNDARY = r"(?=$|[^가-힣]|라|고|는|며|던|더|래|대|카|싶|같|듯|줄|이|가|은|을|를)"
_CONNECTIVE_COP = {"이고", "이며", "인데", "이지만", "이라서", "이니까"}
# 역할 앞 수식어: 관형절(목적어 포함) 최대 다섯 어절. 다른 주어·주제(이/가/은/는/도/만)는 제외한다.
_MOD = r"(?:(?:이|그|저|[가-힣]*[가-힣](?<![이가은는도만]))\s+){0,5}"
_NAME_END = r"(?=$|[^가-힣]|은|는|이|가|을|를|의|과|와|도|님)"
_ROLE_NOUN_END = ("자", "장", "사람", "인물", "대표", "주인", "악역", "주인공")


def _role_matches(name: str, role: str, text: str) -> Iterable[Tuple[int, int, bool]]:
    n, r = re.escape(name), re.escape(role)
    for m in re.finditer(r"(?<![가-힣])" + n + r"\s*\(\s*" + r + r"\s*\)", text):
        yield m.start(), m.end(), False
    # 수식어가 끼면 주제어(은/는)일 때만 본다. 'X가 이끄는 마을의 촌장이다'의 X는 관계절 주어다.
    for pattern in (
        r"(?<![가-힣])" + n + r"\s*(?:은|는)\s*" + _MOD + r + r"\s*" + _COP + _COP_BOUNDARY,
        r"(?<![가-힣])" + n + r"\s*(?:이|가)\s*" + r + r"\s*" + _COP + _COP_BOUNDARY,
    ):
        for m in re.finditer(pattern, text):
            yield m.start(), m.end(), m.group("cop") in _CONNECTIVE_COP
    for pattern in (
        r"(?<![가-힣])" + r + r"\s*인\s+" + n + _NAME_END,
        r"(?<![가-힣])" + r + r"\s+" + n + _NAME_END,
        r"(?<![가-힣])" + n + r"\s+" + r + _NAME_END,
    ):
        for m in re.finditer(pattern, text):
            yield m.start(), m.end(), False


def _role_status(name: str, role: str, source: ClaimScopeSource) -> Tuple[bool, list, Optional[str]]:
    reasons: list = []
    role = re.sub(r"\s+", " ", role).strip()
    tokens = role.split(" ")
    variants = [(role, ())]
    if len(tokens) > 1:
        # '마을 촌장' 같은 수식 역할은 핵심 명사 단언 + 같은 절의 수식어로 확인한다.
        variants.append((tokens[-1], tuple(re.sub(r"의$", "", t) for t in tokens[:-1])))
    for clauses in _clauses_of(source.post_lines):
        for index, clause in enumerate(clauses):
            nxt = clauses[index + 1] if index + 1 < len(clauses) else None
            for head, modifiers in variants:
                if modifiers and not all(mod and mod in clause.text for mod in modifiers):
                    continue
                for start, end, connective in _role_matches(name, head, clause.text):
                    status = clause_assertion(clause, start, end, nxt, connective_end=connective)
                    if status == ASSERTED:
                        return True, [ASSERTED], clause.text
                    reasons.append(status)
    return False, reasons or [NO_STATEMENT], None


def source_states_role(name: str, role: str, source: ClaimScopeSource) -> bool:
    return _role_status(name, role, source)[0]


def extract_role_claims(sentence: str, name: str) -> Tuple[str, ...]:
    """notes 문장이 name에 부여한 역할 표면을 뽑는다."""
    e = re.escape(name)
    found: list = []
    found += [m.group(1) for m in re.finditer(r"(?<![가-힣])" + e + r"\s*\(([^)]{1,30})\)", sentence)]
    found += [
        m.group(1)
        for m in re.finditer(
            r"(?<![가-힣])" + e + r"\s*(?:은|는|이|가)\s+([가-힣]+(?:\s+[가-힣]+){0,4}?)"
            r"(?:이었다|이었음|였다|였음|이다|입니다|임)(?=$|[^가-힣])",
            sentence,
        )
    ]
    found += [
        m.group(1)
        for m in re.finditer(
            r"(?<![가-힣])" + e + r"\s*(?:은|는|이|가)\s+([가-힣]+(?:\s+[가-힣]+){0,4}?)다(?=$|[^가-힣])",
            sentence,
        )
        if m.group(1).split()[-1].endswith(_ROLE_NOUN_END)
    ]
    found += [
        m.group(1)
        for m in re.finditer(
            r"(?<![가-힣])([가-힣]+(?:\s+[가-힣]+){0,4}?)인\s+" + e + r"(?=$|[^가-힣]|(?:은|는|이|가)\s)",
            sentence,
        )
    ]
    out: list = []
    for role in (re.sub(r"\s+", " ", x).strip() for x in found):
        if role and role != name and role not in out:
            out.append(role)
    return tuple(out)


def contrast_relation_names(source: ClaimScopeSource) -> Tuple[str, ...]:
    """본문의 'X는 … Y와의 입장 차이' 관계 주어(현재 파이프라인 W13 트리거)를 모은다."""
    names: list = []
    for line in source.body_lines:
        for m in re.finditer(
            r"(?<![가-힣])([가-힣]{2,12})(?:은|는|이|가)\s+"
            r"(?:(?![가-힣]{2,12}(?:은|는|이|가)\s).){2,70}?"
            r"(?:와|과)의\s+(?:입장|견해|의견|관점|가치관)\s*차이",
            line,
        ):
            if m.group(1) not in names:
                names.append(m.group(1))
    return tuple(names)


# ---------------------------------------------------------------------------
# 작가 주장
_COMMENT_ATTRIBUTION = re.compile(
    r"댓글(?:\s*반응)?(?:은|는|에서는|에서|에선|에\s*따르면|\s*작성자(?:는|들은)|러(?:들)?(?:은|는)|들(?:은|는)|\s*쪽은)"
)
# 의견 귀속 꼬리: 원문의 추정 표현을 의견으로 옮겨도 되는 경우.
_OPINION_TAIL = re.compile(
    r"(?:(?:(?:이?라|다)(?:는|고)\s*)?(?:감상|생각|의견|평가|판단|해석|추정)(?:이다|임|입니다)?"
    r"|(?:이?라|다)고\s*(?:본다|봄|봤다|보는\s*듯|생각한다|생각함|생각했다|느낀다|느낌|평가한다))"
    r"[\s.!?。…~]*$"
)
# 그 밖의 귀속 꼬리: 사실 전달로 옮기므로 추정 표현을 바꾸면 안 된다.
_REPORT_TAIL = re.compile(
    r"(?:(?:(?:이?라|다)(?:는|고)\s*)?(?:반응|지적|불만|아쉬움)(?:이다|임|입니다)?"
    r"|(?:이?라|다)고\s*(?:지적한다|말한다))"
    r"[\s.!?。…~]*$"
)
_STEM_END = re.compile(r"(?:다|음|임|네|요|지|죠)$")
# 핵심 술어 뒤는 비었거나, 문장부호·자모(ㄴㄴ, ㅋㅋ)이거나, 연결 어미여야 한다.
# 공백 뒤 새 어절('낸 듯 보이지만 …')은 범위를 넘는 것으로 본다.
_REMAINDER_OK = re.compile(
    r"^(?:$|\s*[^가-힣\s]|다|고|는데|은데|지만|으며|며|어서|아서|어|아|음|임|네|지|으니|니|면서)"
)
# 추정 표지는 빼거나 더하지 않고 같은 형태로 옮긴 경우만 같은 발화로 본다.
# 핵심 술어 끝의 '듯하/듯함/듯해/듯합니'는 '듯'으로 맞추고, 원문 쪽 '듯' 뒤의
# 같은 꼬리는 핵심 술어에 포함시켜 그 뒤의 전언·부정 판정이 그대로 걸리게 한다.
_HEDGE_TAIL = re.compile(r"듯\s*(?:하|함|해|합니)$")
_HEDGE_CONT = re.compile(r"^\s?(?:합니|하|함|해)")


def _normalize_hedge(text: str) -> str:
    """'거 같'과 '것 같'을 같은 추정 표지로 본다(글자 수 보존)."""
    return re.sub(r"거(?=\s*같)", "것", text)


# notes에서 빠져도 뜻을 넓힐 뿐 바꾸지 않는 원문 어절: 관형격 수식어, 관형사, 정도 부사.
_DETERMINERS = {"두", "세", "네", "한", "이", "그", "저", "몇", "여러", "모든", "각", "어느"}
_DEGREE_ADVERBS = {
    "너무", "좀", "조금", "매우", "정말", "진짜", "완전", "꽤", "되게", "많이", "약간", "살짝", "엄청", "아주", "참",
}


def _droppable(token: str) -> bool:
    return token in _DETERMINERS or token in _DEGREE_ADVERBS or (len(token) >= 2 and token.endswith("의"))


def _jamo(ch: str) -> Optional[Tuple[int, int, int]]:
    code = ord(ch) - 0xAC00
    if 0 <= code < 11172:
        return code // 588, (code % 588) // 28, code % 28
    return None


def _past_adnominal_pair(past: str, adnominal: str) -> bool:
    """'그렸'↔'그린', '냈'↔'낸'처럼 같은 동사의 과거 종결 어간과 과거 관형형인지 본다."""
    if not past or len(past) != len(adnominal) or past[:-1] != adnominal[:-1]:
        return False
    p, a = _jamo(past[-1]), _jamo(adnominal[-1])
    return bool(p and a and p[2] == 20 and a[2] == 4 and p[0] == a[0])  # 받침 ㅆ ↔ ㄴ, 같은 초성


def _author_subject(names: Sequence[str]) -> "re.Pattern[str]":
    # 소유격 '작가의 X'는 작가에 대한 서술 주장이 아니라 명사구 수식이다.
    # "작가 '오직재미'가"처럼 따옴표로 이름을 붙인 동격 주어도 같은 작가 주어로 본다.
    parts = [r"작가(?:가|는)\s+", r"작가\s*['‘“\"][^'’”\"\n]{1,20}['’”\"]\s*(?:이|가|은|는)\s+"]
    parts += [re.escape(x) + r"(?:이|가|은|는)\s+" for x in names if x]
    return re.compile(r"(?<![가-힣])(?:" + "|".join(parts) + ")")


def _claim_core(tail: str) -> Tuple[str, bool]:
    tail = tail.strip()
    opinion = _OPINION_TAIL.search(tail)
    core = tail[:opinion.start()] if opinion else _REPORT_TAIL.sub("", tail)
    core = re.sub(r"[\s.!?。…~ㅋㅎ]+$", "", core)
    core = _STEM_END.sub("", core)
    core = _HEDGE_TAIL.sub("듯", re.sub(r"\s+", " ", core).strip())
    return _normalize_hedge(core), opinion is not None


def _align(core: str, tail: str, opinion: bool) -> Optional[Tuple[int, str, bool]]:
    """core 어절이 tail 앞부분과 순서대로 맞는지 본다.

    생략 가능한 원문 어절만 건너뛰고, 마지막 core 어절은 원문 어절의 앞부분(어간)과 같아야 한다.
    의견 귀속이면 원문의 '과거 관형형 + 듯/것 같'을 과거 종결 어간과 같은 발화로 본다.
    반환값은 (tail 안의 원문 끝 위치, 그 뒤 정규화 나머지, 추정 표지로 끝났는지)다.
    """
    want = core.split(" ")
    toks = [(m.start(), m.group()) for m in re.finditer(r"\S+", _normalize_hedge(tail))]

    def rest(i: int) -> str:
        return "".join(" " + t for _s, t in toks[i:])

    ci = ti = 0
    while ti < len(toks):
        start, tok = toks[ti]
        if ci == len(want) - 1:
            if tok.startswith(want[ci]):
                return start + len(want[ci]), tok[len(want[ci]):] + rest(ti + 1), want[ci].endswith("듯")
            if opinion and _past_adnominal_pair(want[ci], tok) and ti + 1 < len(toks):
                h_start, h_tok = toks[ti + 1]
                if h_tok.startswith("듯"):
                    return h_start + 1, h_tok[1:] + rest(ti + 2), True
                if h_tok == "것" and ti + 2 < len(toks) and toks[ti + 2][1].startswith("같"):
                    g_start, g_tok = toks[ti + 2]
                    return g_start + 1, g_tok[1:] + rest(ti + 3), False
        elif tok == want[ci]:
            ci += 1
            ti += 1
            continue
        if _droppable(tok):
            ti += 1
            continue
        return None
    return None


def _supported_in(
    core: str, opinion: bool, lines: Sequence[str], subject: "re.Pattern[str]"
) -> Tuple[bool, list, Optional[str]]:
    reasons: list = []
    for clauses in _clauses_of(lines):
        for index, clause in enumerate(clauses):
            m = subject.search(clause.text)
            if m is None:
                continue
            nxt = clauses[index + 1] if index + 1 < len(clauses) else None
            aligned = _align(core, clause.text[m.end():], opinion)
            if aligned is None:
                reasons.append(EXCEEDS)
                continue
            end_rel, remainder, hedged = aligned
            hedge_cont = _HEDGE_CONT.match(remainder) if hedged else None
            if not (hedge_cont or _REMAINDER_OK.match(remainder)):
                reasons.append(EXCEEDS)
                continue
            end = m.end() + end_rel
            if hedge_cont is not None:
                while end < len(clause.text) and clause.text[end].isspace():
                    end += 1
                end += len(hedge_cont.group().strip())
            status = clause_assertion(clause, m.start(), end, nxt)
            if status == ASSERTED:
                return True, [ASSERTED], clause.text
            reasons.append(status)
    return False, reasons, None


def author_claim_scope(sentence: str, source: ClaimScopeSource) -> Optional[ScopeDecision]:
    """작가 주장 문장이 아니면 None. 댓글 귀속이면 실제 댓글만, 아니면 title+body만 근거로 본다."""
    subject = _author_subject(source.author_names)
    m = subject.search(sentence)
    if m is None:
        return None
    core, opinion = _claim_core(sentence[m.end():])
    comment_voice = bool(_COMMENT_ATTRIBUTION.search(sentence[:m.start()]))
    kind = "comment_author" if comment_voice else "author"
    if not core:
        return ScopeDecision(False, kind + "_unsupported", kind, (NO_STATEMENT,))
    lines = source.comments if comment_voice else source.post_lines
    if comment_voice and not lines:
        return ScopeDecision(False, kind + "_unsupported", kind, (NO_COMMENT_EVIDENCE,))
    ok, reasons, evidence = _supported_in(core, opinion, lines, subject)
    if ok:
        return ScopeDecision(True, kind + "_supported", kind, (ASSERTED,), evidence)
    detail = tuple(dict.fromkeys(reasons)) or ((NO_COMMENT_EVIDENCE,) if comment_voice else (NO_STATEMENT,))
    return ScopeDecision(False, kind + "_unsupported", kind, detail)


# ---------------------------------------------------------------------------
# 문장·텍스트 단위 진입점
# 문장 끝, 줄바꿈(뒤따르는 글머리표 포함), 글머리표(' - '), 원문 줄·댓글 구분(' / ', ' | '),
# 섹션 머리표('[..] ') 앞에서 나눈다. 구분자는 보존해 걸러진 조각만 빼고 원래 서식을 유지한다.
_NOTE_SPLIT = re.compile(
    r"(\n+[ \t]*(?:-[ \t]+)?|[ \t]+-[ \t]+|[ \t]+/[ \t]+|[ \t]+\|[ \t]+"
    r"|[ \t]+(?=\[[^\]\n]{1,16}\][ \t])|(?<=[.!?。])[ \t]+)"
)


def _separator_rank(sep: str) -> int:
    if "\n" in sep:
        return 3
    if re.fullmatch(r"[ \t]+-[ \t]+", sep) or not sep.strip():
        return 2 if "-" in sep else (1 if sep else 0)
    return 1


def _inherits_label(sep: str) -> bool:
    """같은 글머리표 안의 문장·원문 줄·댓글 구분은 앞 조각의 인용 라벨을 이어받는다."""
    return "\n" not in sep and "-" not in sep and (
        "/" in sep or "|" in sep or bool(re.fullmatch(r"[ \t]+", sep))
    )


# 원문 인용 라벨. 라벨이 붙은 조각만, 그 내용이 원문 한 줄의 온전한 절 범위와 정확히 같을 때 인용으로 본다.
_QUOTE_LABEL = re.compile(
    r"^(?P<label>제목|본문(?:\s*요약)?|원문(?:\s*요약)?|댓글(?:\s*(?:힌트|요약|반응))?|인용)\s*[:：]\s*"
)


def _quote_lines(label: str, source: ClaimScopeSource) -> Tuple[str, ...]:
    if label.startswith("댓글"):
        return source.comments
    if label == "인용":
        return (*source.post_lines, *source.comments)
    return source.post_lines


def _is_whole_clause_quote(body: str, lines: Sequence[str]) -> bool:
    body = body.strip()
    if len(body) < 2:
        return False
    for line in lines:
        starts, ends, cursor = set(), set(), 0
        for clause in split_clauses(line):
            pos = line.find(clause.text, cursor)
            if pos < 0:
                continue
            starts.add(pos)
            ends.update({pos + len(clause.text), pos + len(clause.text.rstrip(_TERMINATORS + " "))})
            cursor = pos + len(clause.text)
        spans = [(m.start(), m.end()) for m in _QUOTE_SPAN.finditer(line)]
        pos = line.find(body)
        while pos >= 0:
            if pos in starts and pos + len(body) in ends and not any(a < pos < b for a, b in spans):
                return True
            pos = line.find(body, pos + 1)
    return False


def check_note_sentence(
    sentence: str, source: ClaimScopeSource, person_names: Sequence[str] = ()
) -> ScopeDecision:
    """한 문장을 판정한다. 역할 검사는 person_names에 준 이름에만 적용한다."""
    sentence = str(sentence or "").strip()
    checked_role = False
    for name in dict.fromkeys(x for x in person_names if x):
        if name not in sentence:
            continue
        for role in extract_role_claims(sentence, name):
            checked_role = True
            ok, reasons, _evidence = _role_status(name, role, source)
            if not ok:
                return ScopeDecision(False, "role_unsupported", "role", tuple(dict.fromkeys(reasons)))
    author = author_claim_scope(sentence, source)
    if author is not None:
        return author
    if checked_role:
        return ScopeDecision(True, "role_supported", "role", (ASSERTED,))
    return ScopeDecision(True, "no_scoped_claim")


def check_note_text(
    text: Any, source: ClaimScopeSource, person_names: Sequence[str] = ()
) -> NoteScopeResult:
    """임의 텍스트(전문가 notes, 최종 analysis_notes, 구조화된 reason)를 조각별로 판정한다.

    걸러진 조각만 빼고 나머지는 원래 구분자(줄바꿈·글머리표 등)와 함께 유지한다.
    '본문 요약:' 같은 인용 라벨 조각은 원문 절과 정확히 같으면 인용으로 보존하고,
    그렇지 않으면 일반 조각과 같은 계약으로 검사한다.
    """
    kept: list = []
    dropped: list = []
    rebuilt: list = []
    pending_sep = ""
    last_sep = ""
    label: Optional[str] = None
    pieces = _NOTE_SPLIT.split(str(text or "").strip())
    for index, piece in enumerate(pieces):
        if index % 2 == 1:
            if _separator_rank(piece) >= _separator_rank(pending_sep):
                pending_sep = piece
            last_sep = piece
            continue
        sentence = piece.strip()
        if not sentence:
            continue
        labelled = _QUOTE_LABEL.match(sentence)
        if labelled:
            label, body = labelled.group("label"), sentence[labelled.end():]
        elif label is not None and _inherits_label(last_sep):
            body = sentence
        else:
            label, body = None, sentence
        if label is not None and _is_whole_clause_quote(body, _quote_lines(label, source)):
            decision = ScopeDecision(True, "verbatim_source_quote", "quote", (ASSERTED,), body)
        else:
            decision = check_note_sentence(sentence, source, person_names)
        if decision.supported:
            kept.append(sentence)
            rebuilt.append((pending_sep if rebuilt else "") + sentence)
            pending_sep = ""
        else:
            dropped.append((sentence, decision))
    return NoteScopeResult(text="".join(rebuilt), kept=tuple(kept), dropped=tuple(dropped))


def with_source_fallback(
    result: NoteScopeResult, source: ClaimScopeSource, uncertainty_label: Optional[str] = None
) -> str:
    """걸러진 문장이 있으면 원문을 함께 남긴다(기존 '[원문] title / body' 형식)."""
    parts = [result.text] if result.text else []
    if result.filtered and source.post_lines:
        if uncertainty_label:
            parts.append(uncertainty_label)
        parts.append("[원문] " + " / ".join(source.post_lines))
    return "\n".join(parts)
