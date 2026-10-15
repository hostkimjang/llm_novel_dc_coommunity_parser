"""커뮤니티 발화의 문맥(발화 유형·대상·조건·매체·요지·인물 역할)을 원문 결속 범위로 투영하는 순수 계약.

파이프라인이 전문가 출력과 최종 상태를 값으로 넘기면, 이 모듈은 원문(title·body)과 맞는 부분만
typed 투영으로 돌려준다. 제목·URL·공개 권한은 다루지 않는다. 근거가 부족하면 fallback 또는 None을
돌려 호출자가 기존의 '원문+불확실성' 출력을 그대로 쓰게 한다.

원칙
- 전문가(Decoder/Synthesizer) 문장은 문장 안의 내용어가 빠짐없이 원문 절·공개 제목·근거에 묶일 때만
  요지로 쓴다. claim_scope의 no_scoped_claim은 '검사 대상 주장이 없음'일 뿐 지지 근거가 아니다.
  묶인 술어는 원문과 부정·양태가 같아야 하고, 숫자·확정 표현·역할(인물/작가)도 원문 또는 개체별 근거가
  있어야 한다. 묶이지 않는 자유 해석은 held_meaning으로 보류한다.
- 원문 표면 하나(평가 술어 앞 토큰, 비교 문형의 X)만으로 작품·후보·관련성 권한을 만들지 않는다.
  작품 역할은 named_work_surfaces 또는 작품형 비교('X 비슷한 소설/거/느낌')로만 준다.
- 작품 표면의 관계는 (작품, 관계, 근거, 원문 구간)으로 남긴다. 이미지·차용 맥락의 현재 작품 단서는 행위 대상 자리
  (독서 동사의 목적어, 평가 술어의 주어, 내용 명사의 소유자)에 그 작품이 올 때만 결속한다. 단서 단어의 존재만으로는 아니다.
- 인물 역할은 행 전체의 작품 앵커가 아니라 그 인물 표면마다의 근거로만 유지한다.
- 매체어나 성적 어근 같은 단어의 존재만으로 범위를 바꾸지 않는다.
- 작성자 소유 절만 요청 조건으로 쓰고, 인용 조사가 붙은 전언·댓글은 조건으로 쓰지 않는다.
- 특정 게시글·작품 이름에 대한 분기를 두지 않는다. 네트워크·모델·파이프라인 상태에 의존하지 않는다.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass, field as _dc_field, fields as _dc_fields, replace
from functools import lru_cache
from threading import Lock
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

from .claim_scope_contract import ClaimScopeSource, check_note_sentence, split_clauses

# B32 native 기록에서 caller·parser가 값을 판단하지 못한 자리. 추정값이나 빈 문자열로 채우지 않는다.
_NOT_OBSERVED = "NOT_OBSERVED"
_NATIVE_VERSION = "context_projection_native_v33"

__all__ = [
    "ExpertSignals",
    "RowState",
    "ContextProjection",
    "project_context",
    "render_context_block",
    "filter_entity_roles",
    # B33 typed input·same-pass proof·projection channel 출처 API
    "NativeRawLine",
    "NativeSourceCarrier",
    "NativeLineOrigin",
    "NativeDroppedLine",
    "NativeSourceManifest",
    "NativeSignalOrigin",
    "NativeSignalOriginCheck",
    "NativeAuthorClause",
    "NativeAuthorClauseSkip",
    "NativeSourceLocation",
    "NativeChannelValue",
    "NativeLifecycleEvent",
    "NativeSupportClaim",
    "NativeTokenLocation",
    "NativeSupportWindow",
    "NativeStanceSupport",
    "NativeBindProof",
    "NativeCoreDecision",
    "NativeProjectionCollector",
    "NativeProjectionResult",
    "native_source_manifest",
    "project_context_native",
]


@dataclass(frozen=True)
class ExpertSignals:
    gatekeeper_post_type: Optional[str] = None
    discourse_intent: Optional[str] = None
    discourse_domain: Optional[str] = None
    # Discourse의 speech_act·target_kind는 원문 판정과 충돌할 때 쓰지 않는 보조 신호다.
    discourse_speech_act: Optional[str] = None
    discourse_target_kind: Optional[str] = None
    synthesis_summary: Optional[str] = None
    post_intent: Optional[str] = None
    entity_mentions: Tuple[Mapping[str, Any], ...] = ()
    # 원문에 실제로 나오고 최종 상태에서 거절되지 않은 작품 별칭·후보 표면만 넘긴다.
    # 이 표면은 작품 대상 판정에서 커뮤니티 단서보다 우선한다('아생갤'처럼 갤러리형 작품명).
    named_work_surfaces: Tuple[str, ...] = ()
    # 검증 전, 전문가가 작품·기준작으로 타입을 붙인 원문 표면(Discourse title_novel_terms, Decoder decoded_terms 중
    # novel_title/work_alias 해석의 original, snippet work_alias). Gatekeeper possible_titles(n-gram)와 해독된 제목은 넣지 않는다.
    # 단독으로는 작품 권한이 없고, 원문의 작품형 비교('X 비슷한 느낌')와 겹칠 때만 비공개 미검증 기준작 표면을 만든다.
    title_term_surfaces: Tuple[str, ...] = ()
    # 검색 catalog 등에서 인물임을 보여 주는 문장(선택).
    character_evidence: Tuple[str, ...] = ()
    # 검증된 개체별 역할 근거 (표면, 'character'|'author'|'work') (선택).
    role_evidence: Tuple[Tuple[str, str], ...] = ()
    # claim_scope 역할 검사에 넘길 인물 이름(파이프라인의 claim_person_names).
    person_names: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RowState:
    discussion_type: Optional[str] = None
    subtype: Optional[str] = None
    topicality: Optional[str] = None
    work_resolution: Optional[str] = None
    is_novel_related: Optional[bool] = None
    # 공개가 허용된 공식 제목(있을 때만). 요지 문장의 작품명 허용 판단에만 쓴다.
    resolved_title: Optional[str] = None


@dataclass(frozen=True)
class ContextProjection:
    speech_act: str
    target_kind: str
    target_surface: Optional[str]
    target_span: Optional[str]
    request_conditions: Tuple[str, ...]
    reference_works: Tuple[str, ...]
    # 추천 요청에서 작성자가 이미 읽었거나 빼 달라고 한 작품 표면.
    excluded_works: Tuple[str, ...]
    # 작품 표면별 역할과 근거 (표면, 역할, 근거).
    #   역할: evaluation_target / discussed / reference / excluded
    #   근거: named_work_surface(저장·후보 보존 가능) / work_typed_comparison+title_term(URL 없는 미검증 표면으로만 저장)
    #         / work_typed_comparison, already_read, source_span(표시 전용)
    work_roles: Tuple[Tuple[str, str, str], ...]
    target_media: str
    media_span: Optional[str]
    scope_hint: Optional[str]
    core_meaning: Tuple[str, ...]
    # 원문·근거에 묶이지 않아 보류한 전문가 해석 (사유, 문장).
    held_meaning: Tuple[Tuple[str, str], ...]
    entity_role_drops: Tuple[Tuple[str, str, str], ...]
    kept_entities: Tuple[Mapping[str, Any], ...]
    allow_character_reaction_phrase: bool
    reasons: Tuple[str, ...]
    fallback: bool
    # 작품 표면마다 대표 관계 근거 (표면, 관계, 근거, 원문 구간).
    #   관계: current_work / image_source / unresolved
    #   근거 예: named_mention, story_event:<행위자>:<단서>, image_context_cue:<단서 종류>:<단서>:<explicit|deictic|implicit>,
    #            image_context_cue_unbound:<단서 종류>:<단서>-><대상 분류>, borrow_without_story_event, image_borrowed_from
    work_relation_evidence: Tuple[Tuple[str, str, str, str], ...] = ()


# ---------------------------------------------------------------------------
# 작성자 소유 절
# 인용 조사가 뒤따르는 인용문만 전언으로 보고 뗀다. "'가짜 장례식' 씬"처럼 장면·작품 이름을 묶은 따옴표는 남긴다.
_QUOTED = re.compile(
    r"(?:[\"“][^\"”]*[\"”]|[‘'][^’']*[’']|「[^」]*」|『[^』]*』)\s*(?:이?라고|이?라며|이?라는|이?라길래|이?래서|하고|하길래|하더라|카더라)"
)
_REPORTED_SPEAKER = re.compile(r"^(?:친구|지인|댓글|타인|누군가|누가|다른\s*사람|사람들)\S*\s")
# 과거형 '했다'는 작성자 본인 서술이다. 인용 조사가 앞에 붙은 '…라고/다고 했다'만 전언으로 본다.
_REPORTED_TAIL = re.compile(r"(?:라고|라며|라더라|다더라|카더라|(?:라고|다고|자고|냐고)\s*했다|했대|하더라|하던데)\s*[.!?。~]*$")
_APP_TAIL = re.compile(r"-\s*dc\s*(?:official\s*)?app\s*$", re.I)

# 화자 어휘의 존재와 실제 전언 시작을 분리한다. 목적격·수혜격·조건문의
# 친구는 언급 대상일 수 있다. 원래 어휘 패턴은 명사 분석용으로 유지한다.
_REPORT_SOURCE_HEAD = re.compile(
    r"^\s*(?P<speaker>(?:친구|지인|댓글|타인|누군가|누가|다른\s*사람|사람들)(?:분|님|들)?)"
    r"(?P<case>께서는|께서|에서는|에선|에서|에는|의|은|는|이|가|도)?"
    r"(?:(?P<label>\s*[:：])\s*|\s+|$)"
)
_REPORT_SOURCE_PREFIX = re.compile(
    r"(?:(?:그러(?:는데|더라(?:고)?|던데|길래)|(?:말|얘기|이야기)"
    r"(?:하(?:는데|더라(?:고)?|던데|길래|길)|했(?:는데|더라(?:고)?|어요|어|대|다)|한다|함))(?=\s|[,，:：.!?？]|$)"
    r"|(?:말|얘기|이야기)(?:로는|에\s*따르면)(?=\s|$))"
)


def _report_subject_remains_lead(text: str, lead, predicate_start: int) -> bool:
    """전언 내용 안의 주어와, 접속절 뒤 새로 시작한 바깥 발화 주어를 구분한다.

    '친구는 내가 ... 온다고 말했다'의 내가만으로 lead를 버리지 않는다. 인용
    어미가 아닌 접속·구두점 뒤에서 별도의 명시 주어가 선택됐을 때만 재귀속한다.
    """
    words = list(_PLAIN_TOKEN.finditer(text, lead.end(), predicate_start))
    boundary = -1
    for previous, current in zip(words, words[1:]):
        word = previous.group(0)
        if ((_SEG_CONNECTIVE.search(word) and word not in _EXCLUDE_MARK
             and not _ACT_QUOTATIVE_END.search(word))
                or re.search(r"[,，;]", text[previous.end():current.start()])):
            boundary = current.start()
    if boundary < 0:
        return True
    subject, span = _clause_subject_detail(text, predicate_start)
    if span[0] < boundary:
        return True
    speaker = re.sub(r"\s+", "", lead.group("speaker"))
    return subject == "other:" + _stem_of(speaker)


def _reported_speaker_lead(text: str):
    """첫 인물·댓글 명사에 실제 발화·출처 표지가 결속될 때만 전언 prefix다."""
    lead = _REPORT_SOURCE_HEAD.match(text)
    if lead is None:
        return None
    rest = text[lead.end():]
    if lead.group("label") or (
        lead.group("speaker") == "댓글" and lead.group("case") in {"에서는", "에선", "에서", "에는"}
    ):
        return lead
    if _REPORT_SOURCE_PREFIX.match(rest):
        return lead
    for marker in (_THIRD_PRED.search(rest), _HEARSAY_TAIL.search(rest)):
        if marker and _report_subject_remains_lead(text, lead, lead.end() + marker.start()):
            return lead
    return None


def _unasserted_role_lead(text: str) -> bool:
    """이전의 넓은 화자 어휘 분기가 잡던 자기 질문·조건을 확정 주장으로 바꾸지 않는다."""
    if not _REPORTED_SPEAKER.match(text.lstrip()) or _reported_speaker_lead(text):
        return False
    without_terminal = text.rstrip(" .!?？。~…")
    return bool(_is_question(text) or _UNCERTAIN_SRC.search(text)
                or _governing_frame(without_terminal, len(without_terminal)) == "conditional")

# B33 R3(E2/E3): 작성자 절 선별에서만 쓰는 인용 범위 규칙. 전역 _QUOTED·_REPORTED_SPEAKER는 바꾸지 않는다.
# 인용 조사 없이 닫힌 여러 어절 발화 인용(버튼 문구·전재·화면 시안), 화자 표지 인용 뒤의 독립 작성자 절, 바로 다음 줄에서
# 닫히는 인용의 이어진 부분을 다룬다.
_SPEECH_QUOTE = re.compile(r"“([^”\n]*)”|\"([^\"\n]*)\"")
# 발화로 끝난 인용 내용: 요청·명령·질문 어미로 끝나거나 종결부호로 문장이 닫혔다. 명사구·제목 인용은 아니다.
_SPEECH_FINAL = re.compile(r"(?:줘|주세요|주라|주셈|줄래|해요|해라|하자|까|냐|니|죠)\s*[.!?~。]*\s*$|[.!?。]\s*$")
# 닫는 따옴표 바로 뒤가 조사·인용 보문 '고'·비교어면 그 인용은 문장 성분(제목·명사구·전언 보문)이라 남긴다.
_QUOTE_NOUN_USE = re.compile(r"(?:고|의|은|는|이|가|을|를|도|만|과|와|랑|이랑|에서|에|으로|로|보다|인|처럼|같은|같이|마냥|류|계열)"
                             r"|\s+(?:같은|같이|비슷한|처럼|마냥|류의|계열)")
_QUOTE_COMPLEMENT = re.compile(r"(?:이?라고|이?라며|이?라는|이?라길래|하고|하며|하길래|하더라|카더라)")
_LEAD_SPEAKER = re.compile(r"(?:친구|지인|댓글|타인|누군가|누가|다른\s*사람|사람들)\S*\s*(?=[“\"])")
# B33 R3d(E3): 닫는 따옴표 뒤의 공백·구분 부호. 그 뒤에 인용 보문 조사('라며' 등)가 오면 보고 연결이다.
_QUOTE_GAP = re.compile(r"[\s,，、·;；:：\-–—~]*")


def _speech_quote_body(m: "re.Match[str]") -> str:
    return m.group(1) if m.group(1) is not None else (m.group(2) or "")


def _quote_complement_end(raw: str, end: int) -> int:
    """닫는 인용 end 뒤 공백·구분 부호를 건너뛰고 인용 보문 조사가 오면 그 조사 끝, 아니면 -1(B33 R3d, E3)."""
    m = _QUOTE_COMPLEMENT.match(raw, _QUOTE_GAP.match(raw, end).end())
    return m.end() if m else -1


def _author_transition_at(raw: str, at: int) -> bool:
    """at에서 독립 작성자 절이 시작하는가(B33 R3d, E3). 첫 어절이 자기 지칭 주어('나는' 등)이거나, 절 머리 접속어('그래서' 등)
    바로 뒤 어절이 자기 지칭 주어여야 한다."""
    words = re.findall(r"[가-힣A-Za-z0-9]+", raw[at:])[:2]
    return bool(words) and (words[0] in _SELF_SUBJECT or (len(words) == 2 and words[0] in _CLAUSE_LEAD and words[1] in _SELF_SUBJECT))


def _author_quote_spans(raw: str, prefix_end: int = 0, suffix_start: int = -1) -> List[Tuple[int, int]]:
    """작성자 절 원문에서 지울 인용 구간을 겹치지 않게 시작 순으로 돌려준다(B33 R3/R3d).

    1) 여러 줄 인용이 이 절의 앞부분(prefix_end까지)이나 뒷부분(suffix_start부터)을 차지하면 그 부분, 2) 기존 _QUOTED(인용 조사가
    붙은 전언), 3) 절 머리의 화자 표지 + 발화 인용 뒤에 보고 연결 없이 독립 작성자 절(자기 지칭 주어)이 이어지면 화자 표지부터 그
    절 앞까지, 4) 인용 조사 없이 닫힌 여러 어절 발화 인용(공백·구분 부호 뒤에 보고 조사가 붙으면 그 조사까지). 해당이 없으면 기존
    _QUOTED 구간과 같다. 화자 표지 인용 뒤에 보고 연결이 있거나 작성자 전환 근거가 없으면 기존처럼 전언 절로 빠진다.
    """
    spans: List[Tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= x or y <= a for x, y in spans)
    if prefix_end > 0:
        spans.append((0, min(prefix_end, len(raw))))
    if 0 <= suffix_start < len(raw) and free(suffix_start, len(raw)):
        spans.append((suffix_start, len(raw)))
    for m in _QUOTED.finditer(raw):
        if free(m.start(), m.end()):
            spans.append((m.start(), m.end()))
    lead = _LEAD_SPEAKER.match(raw)
    quote = _SPEECH_QUOTE.match(raw, lead.end()) if lead else None
    lead_quote_start = quote.start() if quote else -1
    if quote:
        rest = _QUOTE_GAP.match(raw, quote.end()).end()
        if (rest < len(raw) and free(0, rest) and _SPEECH_FINAL.search(_speech_quote_body(quote))
                and not _QUOTE_NOUN_USE.match(raw, quote.end()) and _quote_complement_end(raw, quote.end()) < 0
                and _author_transition_at(raw, rest)):
            spans.append((0, rest))
    for m in _SPEECH_QUOTE.finditer(raw):
        body = _speech_quote_body(m)
        if (m.start() != lead_quote_start and free(m.start(), m.end()) and len(body.split()) >= 2
                and _SPEECH_FINAL.search(body) and not _QUOTE_NOUN_USE.match(raw, m.end())):
            complement = _quote_complement_end(raw, m.end())
            end = complement if complement >= 0 else m.end()
            if free(m.start(), end):
                spans.append((m.start(), end))
    return sorted(spans)


# B33 F249: 제목 머리의 맨 화자 명사('친구 말 뒤에 내 질문'의 '친구')는 보고 주체가 아니라 명사구 수식어다. 조사·쌍점 없이 쓰였고
# 인용·전언·보고·요청 표지가 없을 때만 작성자 머리말로 남긴다. 보고 문형('친구가 …', '친구: “…”', '친구 왈 …', '친구 말로는 …대')과
# 본문 절은 기존 _REPORTED_SPEAKER 판정을 그대로 받는다.
_BARE_SPEAKER_HEAD = re.compile(r"^(?:친구|지인|댓글|타인|다른\s*사람|사람들)\s+(?=[가-힣A-Za-z0-9])")
_HEADER_REPORT_MARK = re.compile(
    r"[“”\"'‘’「」『』:：]|왈|曰|말로는|말론|피셜|카더라|따르면|그러(?:더라|던데|는데|길래|대|래)"
    r"|(?:다|라|자|냐)(?:고|며|는|길래)\s|(?:대|래|더라|던데|다던데|다더라)\s*[.!?~]*$"
)


def _nominal_header(text: str) -> bool:
    """제목 절이 맨 화자 명사로 시작해도 작성자 머리말인가(B33 F249). 화자 명사 뒤에 조사·쌍점이 없고, 인용 부호·전언·보고 표지와
    요청 어휘가 없으며, 끝 어절이 서술형이 아닐 때만 참이다."""
    if (not _BARE_SPEAKER_HEAD.match(text) or _HEADER_REPORT_MARK.search(text) or _REQUEST.search(text)
            or _REPORTED_TAIL.search(text)):
        return False
    words = re.findall(r"[가-힣A-Za-z0-9]+", text)
    return bool(words) and not _PRED_LIKE.search(words[-1])


def _author_clause_cut(raw: str, prefix_end: int = 0, suffix_start: int = -1, header: bool = False):
    """작성자 절 하나의 제거 결과 (남긴 원문 위치, 지운 인용 구간, 앱 꼬리 match, 앞 공백 수, 끝 위치, 문자열, 제외 사유)(B33 R3/R3d).

    _author_clauses와 native 작성자 절 기록이 같은 함수를 써서 문자열과 좌표가 어긋나지 않는다. R3d: 여러 줄 인용의 뒷부분을 지운
    뒤 화자 표지('친구:')만 남으면 전언 절이다. F249: 제목 절(header)이 _nominal_header면 화자 명사로 시작해도 전언 절이 아니다.
    F249 r2: 그 제목 예외는 인용 제거 전 실제 원절 raw(앱 꼬리만 떼고 strip)로 판정한다. 지운 전언 인용·보문 조사의 표지가 raw에
    남아 있으면 예외가 아니다. 남긴 위치·좌표와 제외 사유 밖의 계산은 바꾸지 않는다.
    """
    quotes = _author_quote_spans(raw, prefix_end, suffix_start)
    kept = [i for i in range(len(raw)) if not any(a <= i < b for a, b in quotes)]
    without_quotes = "".join(raw[i] for i in kept)
    tail = _APP_TAIL.search(without_quotes)
    without_tail = without_quotes[:tail.start()] if tail else without_quotes
    lead, end = len(without_tail) - len(without_tail.lstrip()), len(without_tail.rstrip())
    text = without_tail[lead:end]
    speaker_only = 0 <= suffix_start < len(raw) and bool(_REPORTED_SPEAKER.match(text + " "))
    speaker_lead = bool(_reported_speaker_lead(text) or (quotes and _REPORTED_SPEAKER.match(text))) and not (header and _nominal_header(_APP_TAIL.sub("", raw).strip()))
    reason = ("empty_after_removal" if not text else "reported_speaker_lead" if speaker_lead or speaker_only
              else "reported_tail" if _REPORTED_TAIL.search(text) else "unasserted_author_clause" if _unasserted_role_lead(text) else "")
    return kept, quotes, tail, lead, end, text, reason


def _carried_quote_ranges(lines: Sequence[str]) -> List[Tuple[int, int]]:
    """본문 줄마다 여러 줄에 걸친 인용이 차지하는 (앞부분 끝, 뒷부분 시작)(B33 R3d, E2). 해당이 없으면 (0, -1).

    “를 열고 ”로 닫는 깊이를 본문 줄 사이에 이어서 센다. 한 줄에서 연 인용이 뒤 줄에서 실제로 닫히면 연 줄은 그 “부터 끝까지,
    사이 줄은 전체, 닫는 줄은 그 ”까지가 인용이다. 끝까지 닫히지 않은 인용은 여러 줄 인용으로 보지 않는다(줄 안 처리만 남는다).
    """
    out: List[Tuple[int, int]] = [(0, -1)] * len(lines)
    depth, opened = 0, None
    for li, line in enumerate(lines):
        for pos, ch in enumerate(line):
            if ch == "“":
                if depth == 0:
                    opened = (li, pos)
                depth += 1
            elif ch == "”" and depth > 0:
                depth -= 1
                if depth == 0:
                    if opened is not None and opened[0] < li:
                        oli, opos = opened
                        out[oli] = (out[oli][0], opos)
                        for mid in range(oli + 1, li):
                            out[mid] = (len(lines[mid]), -1)
                        out[li] = (pos + 1, out[li][1])
                    opened = None
    return out


def _author_line_clauses(source: ClaimScopeSource):
    """작성자 글의 비지 않은 줄마다 (출처, 줄 index, 줄, split_clauses 결과, 절 좌표, 절별 여러 줄 인용 (앞부분 끝, 뒷부분 시작))
    (B33 R3/R3d).

    본문 줄 사이 인용은 _carried_quote_ranges가 실제 닫힘까지 이어서 본다. 제목은 본문과 따로 본다.
    """
    lines = ([("post_title", 0, source.post_title)] if source.post_title else []) + \
        [("body_line", k, line) for k, line in enumerate(source.body_lines) if line]
    carried = iter(_carried_quote_ranges([line for origin, _, line in lines if origin == "body_line"]))
    for origin, index, line in lines:
        prefix_end, suffix_start = next(carried) if origin == "body_line" else (0, -1)
        parts = split_clauses(line)
        boundaries = _native_boundary_spans(line, [clause.text for clause in parts])
        prefix: List[Tuple[int, int]] = []
        for (a, b), _ in boundaries:
            if (a, b) == (-1, -1):
                prefix.append((0, -1))
                continue
            prefix.append((min(prefix_end, b) - a if prefix_end > a else 0,
                           max(suffix_start, a) - a if 0 <= suffix_start < b else -1))
        yield origin, index, line, parts, boundaries, prefix


def _author_clause_items(source: ClaimScopeSource) -> Tuple[Tuple[str, bool], ...]:
    """작성자 소유 절 (문자열, 지운 인용이 요청 발화였는가)(B33 R3/R3b). _author_clauses와 _request_condition_clauses가 쓴다.

    R3b: 인용을 뗐다는 사실만으로 조건에서 빼지 않는다. 지운 구간에 요청 어휘·다음 독서 질문이 있을 때만 참이다
    ('“황제”라는 단어가 들어갔으면'처럼 낱말·이름을 인용한 조건 절은 거짓이다).
    """
    out: List[Tuple[str, bool]] = []
    for origin, _index, _line, parts, _boundaries, prefix in _author_line_clauses(source):
        for clause, cut in zip(parts, prefix):
            _kept, quotes, _tail, _lead, _end, text, reason = _author_clause_cut(clause.text, *cut, header=origin == "post_title")
            if not reason:
                out.append((text, any(_REQUEST.search(clause.text[a:b]) or _REQUEST_QUESTION.search(clause.text[a:b])
                                      for a, b in quotes)))
    return tuple(out)


def _author_clauses(source: ClaimScopeSource) -> Tuple[str, ...]:
    return tuple(text for text, _ in _author_clause_items(source))


def _request_condition_clauses(source: ClaimScopeSource, clauses: Sequence[str], *,
                               trace: Optional[list] = None) -> Tuple[str, ...]:
    """추천 요청의 작성자 조건(B33 R3/R3b/R3d, E6). 같은 pass 작성자 절 순서와 원문 문자열을 그대로 쓴다.

    현재 요청이 없는 절 중 부인·계획·반사실 요청 표현이 있는 절과, 지운 인용이 요청 발화였던 틀 절(전언·가정·화면 문구)은
    조건이 아니다. 비현재 요청 표현 뒤 tail로 현재 요청을 고른 절은 그 tail 범위만 조건이다(_request_tail_range). 그 밖의 작성자
    절(조건·맥락)은 기존처럼 남긴다. trace(list)를 주면 조건마다 (작성자 절 index, 절 안 시작, 끝)을 같은 pass에서 적는다. 기록이
    같은 pass clauses와 다르면 기존처럼 clauses 전체를 쓴다.
    """
    items = _author_clause_items(source)
    if tuple(text for text, _ in items) != tuple(clauses):
        if trace is not None:
            trace.extend((ci, 0, len(text)) for ci, text in enumerate(clauses))
        return tuple(clauses)
    out: List[str] = []
    for ci, (text, quoted_request) in enumerate(items):
        if _current_request_clause(text):
            start, end = _request_tail_range(text)
        elif quoted_request or _REQUEST_NOT_CURRENT.search(text):
            continue
        else:
            start, end = 0, len(text)
        out.append(text[start:end])
        if trace is not None:
            trace.append((ci, start, end))
    return tuple(out)


def _post_clauses(source: ClaimScopeSource) -> Tuple[str, ...]:
    return tuple(c.text for line in source.post_lines for c in split_clauses(line) if c.text.strip())


# ---------------------------------------------------------------------------
# 발화 유형
_REQUEST = re.compile(
    r"추천\s*(?:좀|점|해|해줘|해조|해주|부탁|받|바람|ㄱ|plz|pls)|추천\s*[?!.~]*$"
    r"|(?:소설|작품|글|웹소설|거|것|물)\s*(?:있냐|없냐|있나|없나|있음|없음|없니|있니)\s*[?!.~]*$"
)
_REQUEST_NEGATED = re.compile(r"추천\s*(?:안|못|하지\s*마|ㄴㄴ)")
# B33 R3(E1)/R3d: 요청 어휘가 있어도 요청 술어에 붙은 부인('…달라는 게 아니다'·'…줘라는 요청을 한 게 아니다')·계획('…달라고 새
# 글을 쓸 예정이다')·반사실('…줘라고 했다면')이면 현재 요청이 아니다. 요청 명사를 부인·철회한 표현('추천 부탁을 부인함')도 같다.
# _REQUEST_PRED는 요청 술어와 그 보문·관형 어미('달라는/달라고', '줘라는/줘라고')다. 부인·계획 범위는 어미 변형과 중간 명사구(계획은
# 세 어절까지)에 걸쳐 잡고, 뒤의 실제 요청 범위는 _request_tail_range가 따로 고른다.
_REQUEST_PRED = r"(?:추천\s*(?:좀\s*)?(?:해\s*)?(?:달라(?:는|고)|(?:줘|주세요|주라|조)\s*(?:라는|라고|란))|달라(?:는|고))"
_REQUEST_NOT_CURRENT = re.compile(
    _REQUEST_PRED + r"\s*(?:(?:요청|부탁|말|글|뜻|의미)\s*(?:을|를|이|가|은|는|도)?\s*)?(?:(?:한|했던|하는|하던|쓴|올린)\s*)?"
    r"(?:게|거|건|것이|것은|것도)?\s*(?:아니|아님|아냐|아닌)(?:라|고|지만|며|다|야|요|에요|어요)?"
    r"|" + _REQUEST_PRED + r"\s*(?:\S+\s*){0,3}?(?:쓸|올릴|남길|할|물어볼)\s*(?:예정|계획|생각)"
    r"(?:이다|이고|인데|이지만|이며|임|이야|이었는데|이었다|은|는|도)?"
    r"|" + _REQUEST_PRED + r"\s*(?:했|한|하였)다면"
    r"|(?:추천\s*)?(?:부탁|요청)(?:을|를)?\s*(?:부인|철회|취소)(?:하고|했고|하며|한다|했다|함|합니다)?"
)
# B33 R3(E4): 다음에 무엇을 읽을지 묻는 질문은 현재 추천 요청이다('…다음에 뭐 읽으면 좋을까?'). R3b: source_spans 공동 helper의
# next_reading_question과 같은 좁은 표현만 받는다.
_REQUEST_QUESTION = re.compile(r"(?:뭐|무엇을)\s*읽으면\s*좋을까")


def _request_tail_start(clause: str) -> int:
    """절에서 마지막 부인·계획·반사실 요청 표현이 끝난 위치. 없으면 0(B33 R3b)."""
    ends = [m.end() for m in _REQUEST_NOT_CURRENT.finditer(clause)]
    return ends[-1] if ends else 0


def _request_tail_range(clause: str) -> Tuple[int, int]:
    """현재 요청을 고른 절 안 범위 [시작, 끝)(B33 R3d, E1/E6). 비현재 요청 표현이 없으면 절 전체, 있으면 그 뒤에서 공백·구분 부호를
    건너뛴 tail이다. tail이 비면 절 전체다."""
    start = _request_tail_start(clause)
    if start:
        start = _QUOTE_GAP.match(clause, start).end()
    end = len(clause.rstrip())
    return (start, end) if start < end else (0, len(clause))


def _current_request_clause(clause: str) -> bool:
    """작성자 절이 현재 추천 요청인가(B33 R3/R3b). 부정 요청 절은 아니다. 부인·계획·반사실 요청 표현이 있으면 그 뒤에 요청 어휘나
    다음 독서 질문이 있어야 한다('A 같은 걸 추천해 달라는 게 아니라 B 같은 거 추천해 줘'의 뒤 요청은 현재 요청이다)."""
    if _REQUEST_NEGATED.search(clause):
        return False
    rest = clause[_request_tail_start(clause):]
    return bool(_REQUEST.search(rest) or (_REQUEST_QUESTION.search(rest) and _is_question(clause)))
_EVAL_PRED = re.compile(r"(?:볼\s*만|읽을\s*만|할\s*만|재밌|재미있|재미 있|괜찮|어떰|어때|어떠|꿀잼|노잼)")
# 질문 판정: 물음표, 또는 의문 어미. '나/니'는 의문형 어간 뒤에서만 인정한다
# ('좋구나', '친구쟈나', '죽는다니', '알았더니', '화나'는 질문이 아니다).
_Q_MARK = re.compile(r"[?？]")
_Q_END = re.compile(
    r"(?:냐|(?<!니)까|냐고|는가|은가|(?<!라)던가)\s*[!.~]*$"
    r"|(?:있|없|되|하|않|찮|려|았|었|였|했|겠|는|가|오|보|봤|기|치|읽|쓰|먹|맞|싶|좋|싫)(?:나|니)\s*[!.~]*$"
)
_Q_INHERENT = re.compile(r"어떰|어때|어떤가|어떠냐|어떻냐")
_PRONOUN_TARGETS = {"이거", "그거", "저거", "이것", "그것", "이", "그", "저", "요즘", "이번", "이번화", "님들", "너네"}
_PARTICLE_END = re.compile(r"(?:은|는|이|가|도|을|를|이랑|랑)$")
# 평가 대상 표면에서는 '이'를 떼지 않는다('헌터대장장이'처럼 작품명 일부일 수 있음).
# '가'는 받침 없는 음절 뒤에서만 조사로 보고 뗀다.
_EVAL_PARTICLE_END = re.compile(r"(?:은|는|도|을|를|이랑|랑)$")
_TROPE_CUE = re.compile(
    r"클리셰|전개|주인공|빌런|히로인|회귀|빙의|환생|설정|트로프|장르|상태창|상점창|헌터|이세계"
    r"|(?:회귀|빙의|환생|헌터|아카데미|현판|무협|로판|피폐|착각|육아|하렘|역하렘|시스템|게임|성좌|탑등반|던전|괴담|대역|대체역사"
    r"|학원|전생|복수|계약|집착|후회|연예계|재벌|스포츠|먼치킨|튜토리얼|마법소녀|TS|ts)물"
)
_GENRE_WORDS = {"하렘", "역하렘", "순애", "피폐", "힐링", "개그", "로맨스", "무협", "판타지", "현판", "로판", "TS", "ts", "NTR", "ntr", "후회", "집착"}
# 작품명 등 더 긴 표면 안의 '파딱'만으로 커뮤니티를 대상으로 단정하지 않는다.
_COMMUNITY_CUE = re.compile(r"갤(?:러리)?|념글|완장|(?<![가-힣A-Za-z0-9])파딱|디시|장붕|장갤|분탕|첫글")
# '장갤에서 주운 짤'처럼 커뮤니티가 출처 장소일 뿐인 표현은 커뮤니티 대상 단서가 아니다.
_COMMUNITY_LOCATIVE = re.compile(r"(?:장갤|갤러리|갤|디시|념글)에서")
_TITLE_ASK = re.compile(r"제목\s*(?:이|은|좀)?\s*(?:뭘까|뭐|머|뭔|알려|아는|아시는|찾)")
_LAUGH = re.compile(r"ㅋ{2,}|ㅎ{2,}|lol|\^\^", re.I)
_OPINION_INTENTS = {"express_opinion", "discuss_genre", "discuss_work"}


def _is_question(clause: str) -> bool:
    # '좋나요?라고 물어본'의 물음표는 현재 질문의 종결이 아니다.
    current = re.sub(r"[?？]+[ \t]*(?=(?:이?라고|라며|냐고|하고)(?:\s|물|묻|질문|말|했|하))", " ", clause)
    return bool(_Q_MARK.search(current) or _Q_END.search(current))


def _mask(text: str, surfaces: Sequence[str]) -> str:
    for s in surfaces:
        if s:
            text = text.replace(s, " ")
    return text


def _cue_kind(cue_text: str) -> str:
    if _COMMUNITY_CUE.search(_COMMUNITY_LOCATIVE.sub(" ", cue_text)):
        return "community"
    if _TROPE_CUE.search(cue_text):
        return "trope"
    return "unknown"


def _is_genre(token: str) -> bool:
    return bool(token in _GENRE_WORDS or _TROPE_CUE.fullmatch(token) or (len(token) >= 2 and token.endswith("물")))


def _strip_eval_particle(token: str) -> str:
    stripped = _EVAL_PARTICLE_END.sub("", token)
    if stripped != token:
        return stripped
    if len(token) >= 3 and token.endswith("가"):
        prev = token[-2]
        if "가" <= prev <= "힣" and (ord(prev) - 0xAC00) % 28 == 0:
            return token[:-1]
    return token


# 부정·반박된 인용('A 아니고', 'A 말고')이나 짤·이미지 출처 절('짤 출처는 A')에만 나온 작품 표면은
# 현재 대상의 근거가 아니다. 이런 표면은 대상 후보에서 뺀다.
# 'A 아님?'처럼 부정어 뒤 물음표가 붙은 추정 질문은 반박이 아니다.
_SURFACE_NEGATED_AFTER = re.compile(
    r"^\s*(?:은|는|이|가)?\s*(?:아님(?!\s*[?？])|아니고|아니라|아닌(?!가|지|\s*[?？])|아냐(?!\s*[?？])|말고|빼고|없|틀렸|잘못|오타)"
)
_ATTRIBUTION_CLAUSE = re.compile(r"(?:짤|사진|이미지|그림|움짤|캡처|캡쳐)\s*(?:의\s*)?(?:출처|저작권|원작)|(?:출처|저작권)\s*(?:은|는|:|：)")
# '짤은 A 거임'처럼 이미지 주제어 바로 뒤(최대 2어절) 서술어 자리에 작품이 오는 경우.
_IMAGE_TOPIC_BEFORE = re.compile(r"(?:짤|사진|이미지|그림|움짤|캡처|캡쳐|스샷|표지|삽화)(?:은|는)\s+(?:\S+\s+){0,2}$")
_IMAGE_TOPIC_AFTER = re.compile(r"^\s*(?:거|꺼|것)?\s*(?:임|이다|다|야|이야|입니다|이고|이며)?\s*[.!?~]*\s*$")


_IMAGE_WORD = r"(?:짤|이미지|스샷|캡처|캡쳐|그림|표지|삽화|사진|움짤)"
# 'A에서/로부터 가져온·퍼온·빌린·인용한·참고한 짤', 'A의 표지/짤만 참고·사용·가져옴'은 이미지 출처 관계다(작품 토론 근거 아님).
_BORROW_ADNOMINAL = r"(?:가져온|퍼온|빌린|빌려온|인용한|참고한|따온|차용한|캡처한|캡쳐한)"
_BORROW_FINITE = r"(?:가져왔|가져옴|퍼왔|퍼옴|빌려왔|빌려옴|인용했|참고했|따왔|따옴|차용했|차용함)"
_SOURCE_PARTICLE = re.compile(r"^\s*(?:으로부터|로부터|에게서|에서)(?![가-힣])")
_IMAGE_IN_CLAUSE = re.compile(_IMAGE_WORD)
_IMAGE_OF = re.compile(r"^\s*(?:의|꺼|거)?\s*" + _IMAGE_WORD + r"(?:만|도)?\s*(?:을|를|은|는)?\s*(?:참고|사용|가져|퍼|빌려|씀|썼|인용)")
_GAP_PUNCT = re.compile(r"[.!?。/;,，]")
_GAP_NEW_SUBJECT = re.compile(r"(?:이|가|께서)$|(?<!에)(?<!에서)(?<!로)(?<!때)(?:은|는)$")
_GAP_CONNECTIVE = re.compile(r"(?:고|며|지만|는데|인데|면서|으며|서)$")


def _image_source_after(clause: str, end: int, named: Sequence[str]) -> bool:
    """작품 표면 뒤가 '출처 조사 + 수식 어절(최대 3개) + 차용 동사 (+ 이미지)'로 이어지는 같은 절의 출처 관계인가(Sol A v8과 같은 계약).

    수식 어절 사이에 새 주어·다른 출처 조사·다른 작품 표면·연결 어미·문장 부호가 끼면 관계를 잇지 않는다.
    관형형 차용 동사('가져온')는 바로 뒤에 이미지 단어가 오거나 '것' 뒤에 절 앞쪽 이미지 단어가 있어야 하고,
    종결형('따왔다')은 같은 절 앞쪽에 이미지 단어가 있어야 한다.
    """
    rest = clause[end:]
    m = _SOURCE_PARTICLE.match(rest)
    if not m:
        return False
    tail = rest[m.end():]
    toks = list(re.finditer(r"\S+", tail))
    for i, tk in enumerate(toks[:4]):
        word = tk.group(0)
        ad = re.match(_BORROW_ADNOMINAL, word)
        fin = re.match(_BORROW_FINITE, word)
        if not (ad or fin):
            if (_GAP_PUNCT.search(word) or _GAP_NEW_SUBJECT.search(word) or _GAP_CONNECTIVE.search(word)
                    or re.search(r"(?:으로부터|로부터|에게서|에서)$", word) or any(s and s in word for s in named)):
                return False
            continue
        # 역순의 앞 이미지 명사는 작품 표면과 같은 연결 구간('짤은 A에서…') 안에 있어야 한다. 뒤에 나오는 이미지 명사는 잇지 않는다.
        seg_start = max([0] + [b.end() for b in _SEG_BOUNDARY.finditer(clause, 0, end)])
        before = clause[seg_start:end]
        if ad:
            after = tail[tk.start() + len(ad.group(0)):]
            if re.match(r"^\s*" + _IMAGE_WORD, after):
                return True
            return bool(re.match(r"^\s*(?:것|거|걸|건)", after) and _IMAGE_IN_CLAUSE.search(before))
        return bool(_IMAGE_IN_CLAUSE.search(before))
    return False


# 이미지 맥락에서 현재 작품을 다룬다는 별도 긍정 단서(독서·평가·작품 내용).
_CURRENT_WORK_CUE = re.compile(
    r"읽|정주행|정독|완독|완결|연재|구독|결제|하차|찍먹|복습|재탕|화까지|편까지|권까지|재밌|재미|꿀잼|노잼|명작|띵작"
    r"|결말|전개|설정|주인공|캐릭터|캐릭|작가|인물"
)
_BORROW_ANY = re.compile(_BORROW_ADNOMINAL + "|" + _BORROW_FINITE)
# 단서마다 행위 대상의 자리가 다르다. 독서 동사는 목적어, 평가 술어는 주어·주제, 내용 명사는 소유자다.
# 단서 단어가 있다는 사실만으로는 권한이 없고, 그 자리에 해당 작품 표면(또는 유일한 작품을 가리키는 지시어)이 올 때만 결속한다.
_CUE_READING = re.compile(r"읽|정주행|정독|완독|구독|결제|하차|찍먹|복습|재탕")
_CUE_EVALUATION = re.compile(r"재밌|재미|꿀잼|노잼|명작|띵작")
# 작품·이미지·기기 어디에나 붙는 명사('그림 작가', '폰 설정')는 명시 소유자가 그 작품일 때만 작품 단서다.
_CUE_SHARED_NOUN = re.compile(r"설정|작가")
_SURF_MARK, _OTHER_MARK = "\ue000", "\ue001"
_CUE_TOKEN = re.compile("[가-힣A-Za-z0-9" + _SURF_MARK + _OTHER_MARK + "]+")
_TOKEN_PARTICLE = re.compile(r"(?:께서|에서|에게|한테|으로|이랑|하고|부터|까지|처럼|보다|을|를|이|가|은|는|도|만|의|에|로|와|과|랑)$")
_ADVERBIAL_TOKEN = re.compile(r"(?:에서|에게|한테|으로|부터|까지|처럼|보다|만에|에|로|와|과|랑|이랑)$")
_ARG_TOKEN = re.compile(r"(?:께서|이|가|은|는|도|을|를)$")
# 새 절이 시작됐다고 볼 수 있는 어절(연결·종결 어미). 이 앞은 단서의 목적어·소유자 자리가 아니다.
# 빈 자리를 추정해 권한을 주는 쪽이라 좁게 둔다(명사 끝 글자와 겹치는 한 글자 어미는 용언 어간 뒤일 때만).
_CLAUSE_END_TOKEN = re.compile(
    r"(?:인데|은데|는데|다가|니까|지만|면서|해서|어서|아서|라서|이고|이며)$"
    r"|(?:[보읽찾하되봐]|봤|었|았|였|했|됐|왔|갔)(?:고|서|며|니|다|음|함|네|요)$"
    r"|(?:했|었|았|였|겠|봤|왔|갔|됐|줬|났|졌)"
)
# 명사 단서 뒤 어절이 서술어인지(수식 관계가 아닌지) 가르는 넓은 검사.
_PRED_LIKE = re.compile(r"(?:다|음|함|임|둠|됨|씀|옴|줌|봄|네|요|죠|냐|나|니|까|지|군|중|ㅋ+|ㅎ+|ㅠ+)$|(?:했|었|았|였|겠|봤|왔|갔|됐|줬|났|졌)")
_WORK_GENERIC = {"작품", "소설", "웹소설", "웹툰", "만화"}
_DEICTIC_DET = {"이", "그", "저", "해당"}
_OTHER_DET = {"다른", "딴", "타"}
_GENERIC_DEICTIC = {"이거", "그거", "저거", "이걸", "그걸", "저걸", "이것", "그것", "저것", "이건", "그건", "저건"}
_CUE_ADVERBS = {"바로", "쭉", "밤새", "또", "다", "전부", "처음부터", "끝까지", "한번에", "드디어", "방금", "이제", "어제", "지금",
                "같이", "함께", "직접", "몰래", "예전에", "전에", "옛날에", "처음", "안", "못", "더"}
# 작품 속 행위자(작품 속 사건 판정용). 조사까지 한 어절로 본다.
_STORY_AGENT = re.compile(r"^(?:주인공|히로인|악역|빌런|캐릭터|등장인물|주연|조연|남주|여주)(?:이|가|은|는|께서|도)?$")
# 작품 밖 대상(채널·앱·계정)에도 쓰는 소비 행위. 명시 목적어가 그 작품일 때만 결속한다.
_CUE_SHARED_ACT = re.compile(r"구독|결제")
# 단서가 문장에서 실제로 맡은 성분을 가리는 닫힌 문법 부류(경동사·상 어절, 용언 어미, 명사 꼬리 조사).
_READ_STEM_REST = re.compile(r"^(?:었|은|는|고|어|을|음|기|다|자|으|히|혀|힌)")
_NOUN_TAIL_OK = re.compile(
    r"(?:님|들|님들)?(?:을|를|이|가|은|는|도|만|의|에|에서|에게|한테|으로|로|와|과|랑|이랑|까지|부터|처럼|보다"
    r"|이다|이야|이고|이며|이라|인데|이지|이네|이었|였|임|다|야|고|며|라)?")
_EVAL_NOUN = {"명작", "띵작", "꿀잼", "노잼"}
_ADNOMINAL_END = re.compile(r"(?:는|던|을|난|운|은)$")
# 관형형 뒤에 와도 서술 구성인 의존 명사('재밌을 것 같다', '재밌는 편').
_AUX_NOUNS = {"것", "거", "게", "건", "걸", "듯", "수", "줄", "만", "편", "모양", "척", "뿐", "중", "적", "지"}
# 경동사 어절의 세 모양. 동사형('했다', '시작했다', '끝났다')은 행위를 서술하고, 명사형('시작', '완료')은 구성이 거기서 끝나거나
# 동사형 경동사가 이어질 때만 행위다. 뒤에 명사가 오면('읽기 시작 버튼', '정주행 완료 표시') 행위 이름을 붙인 명사구다.
# 경동사 어간과 그 뒤에 올 수 있는 활용 어미 첫 음절(닫힌 문법 부류). 어간 뒤가 비었거나 이 음절로 시작할 때만 활용형이다.
# '하단', '해설', '할인', '합본', '마침내'처럼 어간 모양만 같은 다른 명사·부사는 활용형이 아니다.
_LV_TAILS = {
    "하": "다고며면는던지게기자니여세시려러라든죠네나냐", "했": "다고는어음지던습네으을었더대잖거구길기", "함": "",
    "해": "서도요야봤본보버줘주라놓두있", "한": "다데거건게지", "할": "게거때수래까지듯려만", "합": "니시",
    "됨": "", "된": "다거", "되": "다고는어었면지서니기던려네", "됐": "다고어음는네",
    "마쳤": "다고음는어습", "마침": "", "달렸": "다고음어는습", "달림": "", "달리": "고는다면며던자",
}
# 명사형 경동사('끝') 뒤에만 오는 동사 어간('끝나고', '끝냈다').
_LV_TAILS_AFTER_NOUN = dict(_LV_TAILS, **{"나": "고서면는지니요", "났": "다고어음는습네", "내": "고서면는지야요주", "냈": "다고어음는습네",
                                          "남": "", "냄": ""})
_LV_COPULA = re.compile(r"(?:이다|이야|임|이고|이라|이었|인)")
_ASPECT_TAIL = re.compile(r"(?:에|에는|에도|엔|이다|이야|임|이고|이며|이라|이었|이지|이네|인데|이니까|이라서|인|이던)")
_LIGHT_NOUN = re.compile(r"^(시작|완료|끝|마무리|중|각)(.*)$")
# 행위가 관형형으로 끝났는가('정주행한', '읽은', '구독하던'). 뒤 명사가 의존 명사가 아니면 관형절이다.
_ACTION_ADNOMINAL = re.compile(r"(?:한|하는|하던|했던|할|된|되는|되던|됐던|은|는|을|던|중인|중이던)$")


def _segment_around(clause: str, start: int, end: int) -> Tuple[int, int]:
    s0 = max([0] + [b.end() for b in _SEG_BOUNDARY.finditer(clause, 0, start)])
    nxt = _SEG_BOUNDARY.search(clause, end)
    return s0, (nxt.start() if nxt else len(clause))


def _is_adverb(tok: str) -> bool:
    return tok in _CUE_ADVERBS or tok in _ADVERBS or tok.isdigit()


def _unmark(text: str) -> str:
    return text.replace(_SURF_MARK, "<surface>").replace(_OTHER_MARK, "<other_work>")


def _cue_kind_of(cue: str) -> str:
    if _CUE_SHARED_ACT.fullmatch(cue):
        return "shared_act"
    if _CUE_READING.fullmatch(cue):
        return "reading"
    if _CUE_EVALUATION.fullmatch(cue):
        return "evaluation"
    return "shared_noun" if _CUE_SHARED_NOUN.fullmatch(cue) else "work_noun"


def _stem_of(tok: str) -> str:
    return _TOKEN_PARTICLE.sub("", tok) or tok


def _cue_form(toks: Sequence[str], k: int, rest: str, cue: str, kind: str, breaks: Set[int] = frozenset()) -> Tuple[bool, str]:
    """단서가 문장에서 그 종류의 행위·평가·명사로 실제 쓰였는가: (예/아니오, 사유).

    독서·소비 행위는 용언 어미('읽었다'), 행위 명사 + 경동사('정주행했다', '정주행 중', '정주행을 시작했다'),
    절 끝의 명사 서술어('바로 정주행')일 때만 행위다. 파생 명사('구독자', '구독료')와 명사 수식('구독 버튼')은 행위가 아니다.
    평가어가 뒤 명사를 꾸미면('꿀잼 짤', '재밌는 짤') 그 명사를 평가한 것이다. 내용 명사는 조사·높임·복수·서술격 꼬리만 붙어야
    같은 명사다('설정창', '인물화'는 다른 명사).
    """
    tok = toks[k]
    nxt = toks[k + 1] if k + 1 < len(toks) else ""

    def light_after(i: int) -> Tuple[bool, str]:
        """i부터 경동사 구성이 행위로 완결되는가: (예/아니오, 행위 이름을 받은 뒤 명사)."""
        if (i - 1) in breaks:
            return True, ""
        while i < len(toks) and _is_adverb(toks[i]):
            i += 1
        if i >= len(toks):
            return True, ""
        shape = _light_shape(toks[i])
        if shape in ("verbal", "aspect"):
            head = _relative_head_at(toks, i)
            return (False, head) if head else (True, "")
        if shape in ("bare", "bare_particle", "aspect_bare"):
            return _light_noun_closed(toks, i + 1, shape, breaks)
        return False, _stem_of(toks[i])

    def relative_head() -> Optional[str]:
        # 관형형 행위('정주행한 작품', '읽은 짤')는 뒤 명사를 꾸미는 관형절이다. 의존 명사('읽은 적', '정주행한 거')는 서술 구성이다.
        return _relative_head_at(toks, k)

    def after_noun(start: int) -> Tuple[bool, str]:
        # 행위 명사('정주행', '읽기') 뒤: 절 끝이면 명사 서술어, 아니면 경동사 구성이 완결돼야 한다.
        ok, head = light_after(start)
        return (True, "") if ok else (False, f"modifier:{head or _stem_of(nxt)}")

    def in_token_light(tail: str) -> Tuple[bool, str]:
        # 행위 명사와 같은 어절에 붙은 경동사('정주행했다', '정주행시작', '읽기시작버튼').
        shape = _light_shape(tail)
        if shape in ("verbal", "aspect"):
            head = relative_head()
            return (False, f"relative:{head}") if head else (True, "")
        if shape in ("bare", "bare_particle", "aspect_bare"):
            ok, head = _light_noun_closed(toks, k + 1, shape, breaks)
            return (True, "") if ok else (False, f"modifier:{head}")
        return False, f"derived:{tok}"

    if kind in ("reading", "shared_act"):
        if cue == "읽":
            if not _READ_STEM_REST.match(rest):
                return False, f"derived:{tok}"
            inner = re.match(r"(?:었|았)?(?:은|는|을|던)(.+)$", rest)
            # 어절 안에서 관형형 뒤에 다른 명사가 붙으면('읽을거리') 파생 명사다.
            if inner and _stem_of(inner.group(1)) not in _AUX_NOUNS:
                return False, f"derived:{tok}"
            if rest.startswith("기"):
                tail = rest[1:]
                if tail == "":
                    return after_noun(k + 1)
                if re.fullmatch(r"을|를|이|가|은|는|도", tail):
                    return (True, "") if k + 1 < len(toks) and light_after(k + 1)[0] else (False, f"noun_without_action:{tok}")
                return in_token_light(tail)
            head = relative_head()
            return (False, f"relative:{head}") if head else (True, "")
        if rest and _light_shape(rest) is not None:
            return in_token_light(rest)
        if rest == "":
            return after_noun(k + 1)
        if re.fullmatch(r"을|를|이|가|은|는|도", rest):
            # 조사가 붙은 행위 명사('정주행을')는 뒤에 경동사 구성이 와야 행위다('정주행을 시작했다').
            return (True, "") if k + 1 < len(toks) and light_after(k + 1)[0] else (False, f"noun_without_action:{tok}")
        return False, f"derived:{tok}"
    if kind == "evaluation" and cue not in _EVAL_NOUN:
        # 용언 평가어('재밌다'): 관형형이 뒤 명사를 꾸미면 그 명사가 평가 대상이다.
        if _ADNOMINAL_END.search(tok) and nxt and not (_PRED_LIKE.search(nxt) or _is_adverb(nxt) or _stem_of(nxt) in _AUX_NOUNS):
            return False, f"modifier:{_stem_of(nxt)}"
        return True, ""
    if rest and _lv_conj(rest) and kind != "evaluation":
        # 명사가 동사로 쓰였다('설정했다' = 기기를 설정함). 작품에만 있는 명사('연재했다', '완결됨')는 작품 서술로 둔다.
        return (True, "") if kind == "work_noun" else (False, f"verb:{tok}")
    if rest and not _NOUN_TAIL_OK.fullmatch(rest):
        return False, f"derived:{tok}"
    if kind == "evaluation" and rest == "" and nxt and not (_PRED_LIKE.search(nxt) or _is_adverb(nxt) or _SURF_MARK in nxt
                                                            or _POS_CUE.search(nxt) or _NEG_CUE.search(nxt)):
        return False, f"modifier:{_stem_of(nxt)}"
    return True, ""


def _lv_conj(s: str, after_noun: bool = False) -> bool:
    """s가 경동사 활용형인가. 가장 긴 어간을 찾고, 그 뒤가 비었거나 그 어간의 활용 어미 첫 음절로 시작해야 한다."""
    table = _LV_TAILS_AFTER_NOUN if after_noun else _LV_TAILS
    for stem in sorted(table, key=len, reverse=True):
        if s.startswith(stem):
            rest = s[len(stem):]
            return rest == "" or rest[0] in table[stem]
    return False


def _light_shape(tok: str) -> Optional[str]:
    """경동사 어절 모양: verbal(했다·시작했다) / aspect(중이다·중에) / aspect_bare(중) / bare(시작) / bare_particle(시작을) /
    compound(시작버튼) / None(경동사가 아님: '중단', '하단', '해설').

    진행상 '중'은 꼬리가 없거나 문법 꼬리('이다', '에', '인')일 때만이다. 다른 음절이 붙으면('중단', '중독') 다른 명사다.
    """
    if _lv_conj(tok):
        return "verbal"
    m = _LIGHT_NOUN.match(tok)
    if not m:
        return None
    root, tail = m.group(1), m.group(2)
    if root == "중":
        if not tail:
            return "aspect_bare"
        return "aspect" if _ASPECT_TAIL.fullmatch(tail) else None
    if not tail:
        return "bare"
    if _lv_conj(tail, after_noun=True) or _LV_COPULA.fullmatch(tail):
        return "verbal"
    if re.fullmatch(r"을|를|이|가|은|는|도|만", tail):
        return "bare_particle"
    return "compound"


def _light_noun_closed(toks: Sequence[str], j: int, shape: str, breaks: Set[int] = frozenset()) -> Tuple[bool, str]:
    """명사형 경동사('시작', '완료', 꼬리 없는 '중') 뒤에서 구성이 끝나거나 동사형 경동사가 이어지는가: (예/아니오, 뒤 명사).

    문장 부호(쉼표·마침표)는 구성의 끝이다. 뒤에 명사가 오면('읽기 중 표시', '정주행 시작 버튼') 행위 이름을 붙인 명사구다.
    """
    if (j - 1) in breaks:
        return shape in ("bare", "aspect_bare"), ""
    while j < len(toks) and _is_adverb(toks[j]):
        j += 1
    if j >= len(toks):
        return shape in ("bare", "aspect_bare"), ""
    if _light_shape(toks[j]) == "verbal":
        head = _relative_head_at(toks, j)
        return (False, head) if head else (True, "")
    return False, _stem_of(toks[j])


def _relative_head_at(toks: Sequence[str], k: int) -> Optional[str]:
    """어절 k가 관형형 행위이고 뒤 어절이 의존 명사가 아닌 명사면 그 명사(관형절의 머리)."""
    tok = toks[k]
    nxt = toks[k + 1] if k + 1 < len(toks) else ""
    if _ACTION_ADNOMINAL.search(tok) and nxt and not (_stem_of(nxt) in _AUX_NOUNS or _PRED_LIKE.search(nxt) or _is_adverb(nxt)):
        return _stem_of(nxt)
    return None


# 이름을 모르는 새 작품을 들여오는 지칭('다른 작품', '딴 웹툰', '어떤 소설인지', '무슨 작품').
_WORK_TOPIC_NOUNS = ("웹소설", "작품", "소설", "웹툰", "만화", "애니", "드라마", "영화", "게임", "원작")
_NEW_WORK_DET = {"다른", "딴", "타", "어떤", "무슨", "어느"}
# 작품 명사 뒤에 붙어도 같은 명사인 꼬리(조사·서술격·복수). '소설가'처럼 다른 명사 성분이 붙으면 작품 명사가 아니다.
_WORK_NOUN_TAIL = re.compile(
    r"(?:들)?(?:을|를|이|가|은|는|도|만|의|에|에서|로|으로|과|와|이랑|랑|인지는|인지|인데|인가|이고|이며|이라|이야|이다|임|인|이었|였)?")
_WORK_NOUN_RE = re.compile(r"^(" + "|".join(_WORK_TOPIC_NOUNS) + r")(.*)$")


def _is_work_noun(tok: str) -> bool:
    m = _WORK_NOUN_RE.match(tok)
    return bool(m and _WORK_NOUN_TAIL.fullmatch(m.group(2)))


def _gap_modifier(tok: str) -> bool:
    """관형사와 명사 사이에 낀 관형어인가. 목록의 관형사·관형어 외에 끝 음절 받침이 ㄴ인 관형형('재밌는', '읽은', '좋던')도 본다.
    주제 조사가 붙은 명사와 겹칠 수 있으나 그 경우 판정은 보류 쪽으로 기운다."""
    if tok in _DETERMINERS or (len(tok) >= 2 and _ADNOMINAL_MODIFIER.search(tok) and not tok.endswith("의")):
        return True
    last = tok[-1] if tok else ""
    return len(tok) >= 2 and "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 == 4


def _introduces_other_work(toks: Sequence[str]) -> bool:
    """어절 목록 안에 이름 모를 다른 작품을 들여오는 명사구가 있는가(관형사와 작품 명사 사이의 관형어는 3개까지 건너뛴다)."""
    for j, w in enumerate(toks):
        glued = next((d for d in _NEW_WORK_DET if w.startswith(d) and _is_work_noun(w[len(d):])), None)
        if glued:
            return True
        if not _is_work_noun(w):
            continue
        i = j - 1
        for _ in range(4):
            if i < 0:
                break
            if toks[i] in _NEW_WORK_DET:
                return True
            if _gap_modifier(toks[i]):
                i -= 1
                continue
            break
    return False


def _det_before(toks: Sequence[str], j: int) -> str:
    """어절 j 앞의 지시·타칭 관형사('이/그/저/해당', '다른/딴/타'). 사이의 관형어·관형사는 3개까지 건너뛴다."""
    i = j - 1
    for _ in range(4):
        if i < 0:
            return ""
        w = toks[i]
        if w in _DEICTIC_DET or w in _OTHER_DET:
            return w
        if _gap_modifier(w):
            i -= 1
            continue
        return ""
    return ""


def _owner_phrase(prev: Sequence[str]) -> Tuple[str, str, int]:
    """항목 앞 어절들(가까운 것이 끝)의 소유자 구: (종류, 값, 어절 위치).

    종류: deictic(이/그/저/해당 [작품·소설] [수식어] 항목, 이거 항목) / other_ref(다른 작품의 항목) / omitted(소유자 자리 없음) /
    token(그 밖의 어절 — 호출자가 명시 소유자인지 가린다). 관형어('새로운')·관형사('이번')는 3개까지 건너뛴다.
    관계 판정과 요지 소유 작품 판정이 같은 함수를 쓴다.
    """
    i = len(prev) - 1
    for _ in range(3):
        if i < 0:
            return "omitted", "", -1
        w = prev[i]
        if w in _DEICTIC_DET:
            return "deictic", w, i
        if w in _DETERMINERS or (len(w) >= 2 and _ADNOMINAL_MODIFIER.search(w) and not w.endswith("의")):
            i -= 1
            continue
        break
    if i < 0:
        return "omitted", "", -1
    w = prev[i]
    stem = w[:-1] if w.endswith("의") and len(w) >= 2 else w
    before = _det_before(prev, i)
    if stem in _WORK_GENERIC:
        if before in _OTHER_DET:
            return "other_ref", f"{before} {stem}", i
        return "deictic", (f"{before} {stem}" if before in _DEICTIC_DET else stem), i
    if w in _GENERIC_DEICTIC or stem in _GENERIC_DEICTIC:
        return "deictic", w, i
    return "token", w, i


def _cue_token_class(toks: Sequence[str], j: int) -> Tuple[str, str]:
    """어절 하나가 가리키는 대상 종류: surface(뒤 조사) / other_work / deictic_work / deictic_generic / other(줄기)."""
    t = toks[j]
    prev = toks[j - 1] if j > 0 else ""
    if _SURF_MARK in t:
        return "surface", t.split(_SURF_MARK, 1)[1]
    if _OTHER_MARK in t:
        return "other_work", t
    stem = _TOKEN_PARTICLE.sub("", t) or t
    det = _det_before(toks, j) if stem in _WORK_GENERIC else ""
    if det in _OTHER_DET:
        return "other_work", f"{det} {stem}"
    if det in _DEICTIC_DET:
        return "deictic_work", f"{det} {stem}"
    if t in _GENERIC_DEICTIC or stem in _GENERIC_DEICTIC:
        return "deictic_generic", t
    return "other", stem


def _noun_owner(toks: Sequence[str], k: int) -> Tuple[str, str]:
    """명사 단서 어절 k의 소유자: 바로 앞 어절이 맨 명사·소유격이면 그것, 절 경계·논항·부사면 빈 자리(implicit)."""
    kind, val, i = _owner_phrase(toks[:k])
    if kind == "omitted":
        return "implicit", ""
    if kind == "other_ref":
        return "other_work", val
    if kind == "deictic":
        return ("deictic_work", val) if (" " in val or val in _WORK_GENERIC) else ("deictic_det", val)
    prev = toks[i]
    cls, d = _cue_token_class(toks, i)
    if cls == "surface":
        return ("surface", d) if d in ("", "의") else ("implicit", "")
    if cls in ("other_work", "deictic_work"):
        return cls, d
    if _is_adverb(prev) or _CLAUSE_END_TOKEN.search(prev) or _ARG_TOKEN.search(prev) or _ADVERBIAL_TOKEN.search(prev):
        return "implicit", ""
    # 맨 명사·소유격 명사('그림 작가', '짤의 설정', '폰 설정', '검의 설정')가 소유자다.
    return "other", d


def _cue_target(toks: Sequence[str], k: int, prefix: str, kind: str, cue: str) -> Tuple[str, str]:
    """단서 어절 k의 행위 대상 (분류, 세부). 독서 동사는 목적어, 평가 술어는 주어·주제, 내용 명사는 소유자를 찾는다."""
    if prefix and not re.fullmatch(r"[0-9]+|안|못|재|또|첫", prefix):
        # 단서 어절 안의 앞부분('달빛기사결말', '폰설정')이 소유자·대상이다.
        if _SURF_MARK in prefix:
            return "surface", ""
        return ("other_work", prefix) if _OTHER_MARK in prefix else ("other", prefix)
    if kind in ("work_noun", "shared_noun"):
        owner = _noun_owner(toks, k)
        # 결속될 소유자일 때만 수식 관계를 본다: 수식어로 쓰인 명사('설정 버튼', '작가 연락처')는 뒤 명사가 대상이다.
        bindable = ("surface", "deictic_work") if kind == "shared_noun" else ("surface", "deictic_work", "deictic_det", "implicit")
        if owner[0] in bindable and toks[k] == cue and k + 1 < len(toks):
            nxt = toks[k + 1]
            head = _TOKEN_PARTICLE.sub("", nxt) or nxt
            # 뒤 어절이 평가어('작가 최고', '결말 별로')면 서술어 자리다.
            if not (_PRED_LIKE.search(nxt) or _is_adverb(nxt) or head in _DOMAIN_NOUNS or _CURRENT_WORK_CUE.fullmatch(head)
                    or _POS_CUE.search(nxt) or _NEG_CUE.search(nxt) or _SURF_MARK in nxt or _OTHER_MARK in nxt):
                return "modifier", head
        return owner
    ok_suffix = ("", "을", "를", "도", "만", "은", "는") if kind == "reading" else ("", "이", "가", "은", "는", "도", "을", "를", "만")
    seen = False
    for j in range(k - 1, -1, -1):
        t = toks[j]
        cls, d = _cue_token_class(toks, j)
        if cls == "surface":
            if d in ok_suffix:
                return "surface", d
            seen = True
            continue
        if cls in ("other_work", "deictic_work", "deictic_generic"):
            return cls, d
        if _is_adverb(t) or t in _DEICTIC_DET or t in _OTHER_DET:
            continue
        if _CLAUSE_END_TOKEN.search(t):
            return "implicit", ""
        if t.endswith(("을", "를")):
            return "other", d
        if kind == "evaluation" and re.search(r"(?:이|가|은|는|도)$", t):
            return "other", d
        if _ADVERBIAL_TOKEN.search(t) or _ARG_TOKEN.search(t):
            seen = True
            continue
        if not seen:
            # 조사 없이 단서 바로 앞에 놓인 명사('무협지 정주행', '짤 재밌다')가 대상이다.
            return "other", d
    return "implicit", ""


def _token_breaks(marked: str, spans) -> Set[int]:
    """어절 i와 i+1 사이에 문장 부호가 있는 i의 집합(경동사 구성의 끝 판정용)."""
    return {i for i in range(len(spans) - 1) if re.search(r"[.,!?;~…/，。]", marked[spans[i].end():spans[i + 1].start()])}


def _mark_tokens(region: str, surface: str, others: Sequence[str]):
    """작품 표면을 표지 문자로 바꾼 구간과 어절 목록. 긴 표면부터 바꿔 포함 관계(A2 ⊃ A)를 지킨다."""
    marked = region
    for s in sorted({surface, *[o for o in others if o]}, key=len, reverse=True):
        marked = marked.replace(s, _SURF_MARK if s == surface else _OTHER_MARK)
    spans = list(_CUE_TOKEN.finditer(marked))
    return marked, spans, [m.group(0) for m in spans]


def _evaluation_subject_is(clause: str, surface: str, others: Sequence[str]) -> bool:
    """평가 술어('볼만', '재밌')의 주어·주제 자리에 이 작품 표면이 오는가."""
    marked, spans, toks = _mark_tokens(clause, surface, others)
    m = _EVAL_PRED.search(marked)
    if not m:
        return False
    k = next((i for i, sp in enumerate(spans) if sp.start() <= m.start() < sp.end()), None)
    if k is None:
        return False
    return _cue_target(toks, k, marked[spans[k].start():m.start()], "evaluation", m.group(0))[0] == "surface"


def _bind_cue(region: str, surface: str, others: Sequence[str]) -> Tuple[Optional[str], str]:
    """이미지 맥락의 현재 작품 단서가 그 작품 표면을 행위 대상으로 삼는가: (결속 근거, 거절 사유).

    대상이 작품 표면이면 명시 결속, 유일한 작품을 가리키는 지시어면 지시 결속이다. 대상 자리가 비었을 때는
    작품에만 성립하는 행위·명사(정주행, 결말)만 구간의 유일한 작품으로 잇고, 평가 술어·공용 명사(재밌다, 작가, 설정)는 잇지 않는다.
    """
    marked, spans, toks = _mark_tokens(region, surface, others)
    breaks = _token_breaks(marked, spans)
    first_surface = next((i for i, tk in enumerate(toks) if _SURF_MARK in tk), None)
    uniq = not any(_OTHER_MARK in tk for tk in toks) and not _introduces_other_work(toks)
    rejected: List[str] = []
    for m in _CURRENT_WORK_CUE.finditer(marked):
        k = next((i for i, sp in enumerate(spans) if sp.start() <= m.start() < sp.end()), None)
        if k is None:
            continue
        cue, kind = m.group(0), _cue_kind_of(m.group(0))
        prefix = marked[spans[k].start():m.start()]
        if first_surface is None or k < first_surface or (k == first_surface and _SURF_MARK not in prefix):
            rejected.append(f"{kind}:{cue}->before_surface")
            continue
        # 단서 어근이 문장에서 그 종류의 행위·평가·명사로 쓰였는지 먼저 본다(대상 결속은 그다음).
        formed, form_why = _cue_form(toks, k, marked[m.end():spans[k].end()], cue, kind, breaks)
        if not formed:
            rejected.append(f"{kind}:{cue}->form:{_unmark(form_why)}")
            continue
        target, detail = _cue_target(toks, k, prefix, kind, cue)
        how = None
        if target == "surface":
            how = "explicit"
        elif target == "deictic_work" and uniq:
            how = "deictic"
        elif target == "deictic_generic" and kind == "reading" and uniq:
            how = "deictic"
        elif target in ("implicit", "deictic_det") and kind in ("reading", "work_noun") and uniq:
            how = "implicit"
        if how:
            return f"{kind}:{cue}:{how}", ""
        rejected.append(f"{kind}:{cue}->{target}" + (f":{_unmark(detail)}" if detail else ""))
    return None, ";".join(rejected[:3])


def _story_event(gap: str, after_verb: str, others: Sequence[str]) -> Optional[str]:
    """'A에서 주인공이 가져온 검이 멋있다'처럼 차용 동사가 작품 속 사건인가: (행위자:단서) 또는 None.

    차용 동사의 참여자가 작품 속 행위자뿐이어야 한다(현실 인물·동반 부사어 '친구와'·'친구가'가 끼지 않음).
    동사 바로 뒤 명사를 사건 대상으로 보고, 내용·평가 단서가 그 대상을 행위 대상으로 삼아야 한다
    ('검이 멋있다', '검의 설정이 좋다'). 행위자 단어 자체('주인공이 가져온 문구다')나 다른 행위의 평가
    ('대사를 서명으로 써서 좋다')는 사건 근거가 아니다.
    """
    toks = re.findall(r"[가-힣A-Za-z0-9]+", gap)
    agents = [tk for tk in toks if _STORY_AGENT.match(tk)]
    if not agents:
        return None
    for tk in toks:
        if tk in agents or _is_adverb(tk) or re.search(r"(?:에|때)$", tk):
            continue
        return None
    head = re.match(r"\s*([가-힣A-Za-z0-9]+)", after_verb)
    if not head:
        return None
    obj = _TOKEN_PARTICLE.sub("", head.group(1)) or head.group(1)
    marked = after_verb
    for o in sorted((o for o in others if o), key=len, reverse=True):
        marked = marked.replace(o, _OTHER_MARK)
    marked = re.sub(r"^\s*" + re.escape(obj), _SURF_MARK, marked, count=1)
    if not marked.startswith(_SURF_MARK):
        return None
    spans = list(_CUE_TOKEN.finditer(marked))
    ev_toks = [m.group(0) for m in spans]
    uniq = not any(_OTHER_MARK in tk for tk in ev_toks)
    # 극성 단서는 모듈 뒤쪽에서 정의되므로 호출 시점에 묶는다.
    story_cue = re.compile(_CURRENT_WORK_CUE.pattern + "|" + _POS_CUE.pattern + "|" + _NEG_CUE.pattern)
    for m in story_cue.finditer(marked):
        k = next((i for i, sp in enumerate(spans) if sp.start() <= m.start() < sp.end()), None)
        if not k:
            continue
        cue = m.group(0)
        kind = _cue_kind_of(cue) if _CURRENT_WORK_CUE.fullmatch(cue) else "evaluation"
        if not _cue_form(ev_toks, k, marked[m.end():spans[k].end()], cue, kind, _token_breaks(marked, spans))[0]:
            continue
        target, _ = _cue_target(ev_toks, k, marked[spans[k].start():m.start()], kind, cue)
        if target == "surface" or (target in ("implicit", "deictic_det") and kind == "work_noun" and uniq):
            return f"{agents[0]}:{cue}"
    return None


def _surface_relation(clauses: Sequence[str], ci: int, start: int, end: int, surface: str, named: Sequence[str]) -> Tuple[str, str, str]:
    """작품 표면 한 출현의 (관계, 근거, 원문 구간). 관계는 'image_source' | 'unresolved' | 'current_work'.

    출처 판정이 거짓이라고 곧 현재 작품이 되지 않는다. 이미지·차용 맥락에서 관계를 잇지 못하면 미해결(권한 없음)이고,
    현재 작품이라는 단서가 그 작품을 행위 대상으로 삼을 때만 current_work가 된다.
    """
    c = clauses[ci]
    others = [x for x in named if x and x != surface]
    rest = c[end:]
    for basis, hit in (
        ("negated_or_corrected", lambda: _SURFACE_NEGATED_AFTER.match(rest)),
        ("attribution_clause", lambda: _ATTRIBUTION_CLAUSE.search(c)),
        ("image_of_surface", lambda: _IMAGE_OF.match(rest)),
        ("image_topic_copula", lambda: _IMAGE_TOPIC_BEFORE.search(c[:start]) and _IMAGE_TOPIC_AFTER.match(rest)),
        ("image_borrowed_from", lambda: _image_source_after(c, end, others)),
    ):
        if hit():
            return "image_source", basis, c.strip()
    s0, s1 = _segment_around(c, start, end)
    seg = c[s0:s1]
    after = c[end:s1]
    has_image = bool(_IMAGE_IN_CLAUSE.search(seg))
    src = _SOURCE_PARTICLE.match(rest)
    if src:
        tail = c[end + src.end():]
        # 'A에서.'처럼 출처 조사로 끝나고 다음 절이 이미지·차용을 말하면 미해결이다.
        if not re.search(r"[가-힣A-Za-z0-9]", tail):
            nxt = clauses[ci + 1] if ci + 1 < len(clauses) else ""
            if _IMAGE_IN_CLAUSE.search(nxt) or _BORROW_ANY.search(nxt):
                return "unresolved", "dangling_source_then_image_or_borrow", f"{c} {nxt}".strip()
            return "current_work", "dangling_source_without_image", c.strip()
        b = _BORROW_ANY.search(after)
        if b:
            event = None if has_image else _story_event(after[src.end():b.start()], after[b.end():], others)
            if event:
                return "current_work", f"story_event:{event}", seg.strip()
            return "unresolved", "borrow_without_story_event", seg.strip()
    # 현재 작품 단서는 해당 연결 구간과 바로 이어지는 구간('A 짤 보고 / 정주행했다')까지 보되, A를 대상으로 한 단서만 인정한다.
    nxt = _SEG_BOUNDARY.search(c, s1 + 1) if s1 < len(c) else None
    region = c[s0:(nxt.start() if nxt else len(c))]
    bound, why = _bind_cue(region, surface, others)
    if not has_image:
        # 이미지·차용이 없는 언급은 기존대로 현재 작품이다. 단서가 이 작품을 대상으로 삼으면 대상 선택에서 앞세운다.
        return ("current_work", f"named_mention+cue:{bound}", region.strip()) if bound else ("current_work", "named_mention", seg.strip())
    if bound:
        return "current_work", f"image_context_cue:{bound}", region.strip()
    return "unresolved", (f"image_context_cue_unbound:{why}" if why else "image_context_without_cue"), region.strip()


# 작품 표면 바로 뒤에 붙어도 같은 표면으로 보는 문법 꼬리의 시작. 조사가 아닌 한글이 이어지면 더 긴 다른 이름일 수 있다.
_SURFACE_TAIL = re.compile(r"(?:의|은|는|이|가|을|를|도|만|에|에서|에게|한테|로|으로|과|와|랑|이랑|처럼|보다|까지|부터|라는|이라는|인|이다|임|이야|야"
                           r"|이고|이며|말고|빼고|대신|꺼|거|쪽|같은|같이)")


def _work_spans(text: str, works: Sequence[str]) -> List[Tuple[str, int, int]]:
    """원문 속 작품 표면 출현 (표면, 시작, 끝). 긴 표면부터 찾고, 더 긴 작품 표면 안에 든 짧은 표면은 따로 세지 않는다
    ('달빛기사전' 안의 '달빛기사')."""
    spans: List[Tuple[str, int, int]] = []
    for w in sorted({w for w in works if w}, key=len, reverse=True):
        for m in re.finditer(re.escape(w), text):
            if not any(a <= m.start() and m.end() <= b for _, a, b in spans):
                spans.append((w, m.start(), m.end()))
    return spans


def _works_in(text: str, works: Sequence[str], strict_tail: bool = False) -> Set[str]:
    """원문에 완전한 표면으로 나온 작품. strict_tail이면 표면 뒤가 비었거나 문법 꼬리로 시작할 때만 인정한다
    (입력에 없는 더 긴 이름 '달빛기사전'의 앞부분을 '달빛기사'로 세지 않는다)."""
    out: Set[str] = set()
    for w, _, b in _work_spans(text, works):
        tail = re.match(r"[가-힣]*", text[b:]).group(0)
        if strict_tail and tail and not _SURFACE_TAIL.match(tail):
            continue
        out.add(w)
    return out


def _covered_by_longer(text: str, start: int, end: int, surface: str, works: Sequence[str]) -> bool:
    """[start, end)의 표면 출현이 더 긴 다른 작품 표면 출현 안에 드는가."""
    for o in works:
        if o and len(o) > len(surface) and surface in o:
            for m in re.finditer(re.escape(o), text):
                if m.start() <= start and end <= m.end():
                    return True
    return False


def _relation_table(named: Sequence[str], clauses: Sequence[str]) -> Tuple[Tuple[str, str, str, str], ...]:
    """작품 표면마다 대표 관계 근거 (표면, 관계, 근거, 원문 구간). 현재 작품 근거가 하나라도 있으면 그것, 없으면 미해결, 그다음 출처.
    더 긴 작품 표면 안에 든 출현('달빛기사전'의 '달빛기사')은 그 작품의 출현이 아니다."""
    return _relation_table_detail(named, clauses)[0]


def _new_work_head_match(surface: str, clause: str):
    """원문 앞쪽 표면과 신작 head의 결속. 이 일치 자체는 작가 역할 근거가 아니다."""
    return re.match(r'\s*(?P<surface>' + re.escape(surface) + r')(?:의)?\s+'
                    r'(?P<role>작가|센세|선생|님)?\s*'
                    r'(?P<head>신작|최신작|새\s*작품|차기작|신간|후속작)'
                    r'(?=\s|[은는이가]|$)', clause)


def _author_new_work_span(surface: str, clause: str) -> Optional[Tuple[int, int]]:
    """원문 신작 head 앞쪽 표면의 위치. 사람/작품 역할은 소비자가 별도로 검산한다."""
    match = _new_work_head_match(surface, clause)
    return match.span(1) if match else None


def _author_head_span(surface: str, clause: str) -> Optional[Tuple[int, int]]:
    """같은 원절의 사람→그 사람의 소설 head. 새 이름이나 작품 권한을 추론하지 않는다."""
    match = re.match(r'\s*(' + re.escape(surface) + r')\s*<{2,}\s*'
                     r'(?:이분|이\s*작가)(?:의)?\s+(?:소설|작품|글)(?=\s|[은는이가]|$)', clause)
    return match.span(1) if match else None


def _relation_table_detail(named: Sequence[str], clauses: Sequence[str]
                           ) -> Tuple[Tuple[Tuple[str, str, str, str], ...], Tuple[Tuple[str, int, int, int], ...]]:
    """_relation_table과 같은 표와, 표 행마다 대표 관계를 낸 실제 출현 (표면, 절 index, 시작, 끝)(B33).

    대표 출현은 min이 고르는 첫 최소 원소와 같은 위치다. 절 index는 호출자가 넘긴 clauses 기준이다.
    """
    out = []
    where = []
    order = {"current_work": 0, "unresolved": 1, "image_source": 2}
    for s in named:
        if not s:
            continue
        occurrences = [(ci, m.start(), m.end()) for ci, c in enumerate(clauses) for m in re.finditer(re.escape(s), c)
                       if not _covered_by_longer(c, m.start(), m.end(), s, named)
                       and _author_head_span(s, c) != m.span()
                       and _author_new_work_span(s, c) != m.span()]
        rels = [_surface_relation(clauses, ci, start, end, s, named) for ci, start, end in occurrences]
        if rels:
            best = min(range(len(rels)), key=lambda k: (order[rels[k][0]], not _cue_backed(rels[k][1])))
            out.append((s,) + rels[best])
            where.append((s,) + occurrences[best])
    return tuple(out), tuple(where)


def _cue_backed(basis: str) -> bool:
    """현재 작품 근거가 행위 대상 결속(단서·작품 속 사건)으로 뒷받침되는가. 단순 언급·출처 조사 단독은 아니다."""
    return basis not in ("named_mention", "dangling_source_without_image")


def _surface_relations(named: Sequence[str], clauses: Sequence[str]) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
    """(현재 작품 근거가 있는 표면, 이미지 출처·부정에만 나온 표면, 관계 미해결 표면)."""
    table = _relation_table(named, clauses)
    pick = lambda rel: tuple(s for s, r, _, _ in table if r == rel)  # noqa: E731
    return pick("current_work"), pick("image_source"), pick("unresolved")


def _live_surfaces(named: Sequence[str], clauses: Sequence[str]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """(현재 작품 권한을 줄 표면, 권한을 주지 않는 표면=출처·부정·미해결)."""
    live, dead, unresolved = _surface_relations(named, clauses)
    return live, dead + unresolved


def _pick_target(live: Sequence[str], focus: Sequence[str], universe: Sequence[str] = ()) -> Optional[str]:
    return _pick_target_detail(live, focus, universe)[0]


def _pick_target_detail(live: Sequence[str], focus: Sequence[str], universe: Sequence[str] = ()
                        ) -> Tuple[Optional[str], int, Tuple[Tuple[int, int], ...]]:
    """_pick_target과 같은 선택과, 표면을 찾은 focus 위치·그 안 표면 출현 좌표(B33). 첫 live 표면 fallback이면 위치는 -1이다."""
    for k, clause in enumerate(focus):
        spans = _work_spans(clause, tuple(universe) + tuple(live))
        found = {w for w, _, _ in spans}
        for s in live:
            if s in found:
                return s, k, tuple((a, b) for w, a, b in spans if w == s)
    return (live[0] if live else None), -1, ()


def _find_eval_target(clause: str, named: Sequence[str], universe: Sequence[str] = ()) -> Tuple[Optional[str], str]:
    return _find_eval_target_detail(clause, named, universe)[:2]


def _find_eval_target_detail(clause: str, named: Sequence[str], universe: Sequence[str] = ()
                             ) -> Tuple[Optional[str], str, Tuple[Tuple[int, int], ...]]:
    """_find_eval_target과 같은 판정과 대상 표면의 절 안 좌표(B33). 작품 표면이면 그 표면의 모든 출현, 원문 토큰이면 그 토큰 구간이다."""
    spans = _work_spans(clause, tuple(universe) + tuple(named))
    found = {w for w, _, _ in spans}
    present = [s for s in named if s and s in found]

    def located(surface: str) -> Tuple[Tuple[int, int], ...]:
        return tuple((a, b) for w, a, b in spans if w == surface)
    if present:
        # 한 절에 작품이 여럿이면 평가 술어의 주어인 작품이 대상이다('A 대신 B 볼만함?' → B).
        if len(present) > 1:
            for s in present:
                if _evaluation_subject_is(clause, s, [o for o in named if o and o != s]):
                    return s, "named_work_surfaces", located(s)
        return present[0], "named_work_surfaces", located(present[0])
    m = _EVAL_PRED.search(clause)
    if not m:
        return None, "", ()
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", clause[:m.start()].strip())
    if len(tokens) != 1:
        return None, "", ()
    token = _strip_eval_particle(tokens[0])
    if len(token) < 2 or token in _PRONOUN_TARGETS:
        return None, "", ()
    run = re.search(r"[가-힣A-Za-z0-9]+", clause[:m.start()])
    return token, "source_span", ((run.start(), run.start() + len(token)),)


def _speech_act(source: ClaimScopeSource, signals: ExpertSignals, clauses: Sequence[str], *, trace: Optional[dict] = None):
    """발화 유형·대상 판정. B33: trace(dict)를 주면 반환 분기, target_span의 작성자 절 index, 대상 표면의 실제 출현 위치를
    같은 pass에서 적는다. 판정과 반환값은 trace 유무와 무관하다."""
    table, table_where = _relation_table_detail(tuple(s for s in signals.named_work_surfaces if s), clauses)
    # 같은 절에 현재 작품이 여럿이면 단서가 그 작품을 대상으로 삼는 표면을 앞세운다('A 대신 B를 정주행했다' → B).
    named = tuple(s for s, r, b, _ in table if r == "current_work" and _cue_backed(b)) + \
        tuple(s for s, r, b, _ in table if r == "current_work" and not _cue_backed(b))
    dead = tuple(s for s, r, _, _ in table if r == "image_source")
    unresolved = tuple(s for s, r, _, _ in table if r == "unresolved")
    title_line = source.post_lines[0] if source.post_lines else ""
    text = " ".join(clauses)
    intent = str(signals.discourse_intent or "").lower()
    reasons: List[str] = [f"named_surface_not_target:{s}" for s in dead] + [f"named_surface_unresolved:{s}" for s in unresolved]
    # 1) 작품 표면을 대상으로 한 평가 질문. 원문 토큰 하나만 있는 평가 대상은 일반 평가 대상으로 남긴다.
    def mark(rule: str, span_index: int = -1, locations: Sequence[Tuple[str, int, Tuple[int, int]]] = ()) -> None:
        if trace is not None:
            trace.update(rule=rule, span_index=span_index, surface_locations=tuple(locations))
    proven_authors = tuple(dict.fromkeys(tuple(source.author_names)
        + tuple(s for s, role in signals.role_evidence if role == 'author')
        + tuple(str(e.get('text') or '') for e in signals.entity_mentions
                if e.get('entity_type') == 'author' or e.get('role') == 'author_focus')))
    authors = tuple(dict.fromkeys(tuple(signals.named_work_surfaces) + proven_authors))
    characters = _character_names(signals)
    new_work_heads = tuple(dict.fromkeys(authors + tuple(
        str(e.get('text') or '').strip() for e in signals.entity_mentions
        if e.get('entity_type') == 'work')))

    def author_new_work_head(clause: str):
        occurrences = _work_spans(clause, tuple(signals.named_work_surfaces) + tuple(named))
        for person in sorted(new_work_heads, key=len, reverse=True):
            if not person or person in characters:
                continue
            match = _new_work_head_match(person, clause)
            span = match.span('surface') if match else None
            if span is not None and not any(
                work in named and (work != person or (a, z) != span)
                for work, a, z in occurrences
            ):
                # '신작' 표면만으로 작품 후보를 사람으로 재분류하지 않는다.
                # '님'도 작품의 의인화일 수 있어 단독 작가 proof로 쓰지 않는다.
                author_role = person in proven_authors or match.group('role') in {'작가', '센세', '선생'}
                return person, span, 'author_new_work' if author_role else 'work_new_work'
        return None

    def author_head(clause: str):
        for author in sorted((s for s in authors if s and s not in characters), key=len, reverse=True):
            span = _author_head_span(author, clause)
            if span is not None:
                return author, span
        return None

    eval_item = None
    for ci, clause in enumerate(clauses):
        if _EVAL_PRED.search(clause) and (_is_question(clause) or _Q_INHERENT.search(clause)):
            relation = author_new_work_head(clause)
            if relation:
                mark('evaluation_question_' + relation[2], ci, [('author_clause', ci, relation[1])])
                return 'evaluation_question', relation[2], relation[0], clause, reasons + ['source_' + relation[2] + '_relation']
            author = author_head(clause)
            if author:
                mark('evaluation_question_author_target', ci, [('author_clause', ci, author[1])])
                return 'evaluation_question', 'author', author[0], clause, reasons + ['source_author_head']
            surface, origin, surface_spans = _find_eval_target_detail(clause, named,
                                                                      tuple(s for s in signals.named_work_surfaces if s))
            if surface and origin == "named_work_surfaces":
                mark("evaluation_question_named_work", ci, [("author_clause", ci, sp) for sp in surface_spans])
                return "evaluation_question", "named_work", surface, clause, reasons + ["evaluation_question_target:named_work_surfaces"]
            if surface and eval_item is None:
                eval_item = (surface, clause, ci, surface_spans)
    # 2) 작성자 추천 요청
    # B33 R3(E1/E4): 부인·계획·반사실 요청 절은 빼고 질문형 현재 요청은 넣는다.
    request_at = [i for i, c in enumerate(clauses) if _current_request_clause(c)]
    request = [clauses[i] for i in request_at]
    if request:
        mark("recommendation_request", request_at[0])
        return "recommendation_request", "conditions", None, request[0], reasons + ["author_owned_request"]
    question_at = [i for i, c in enumerate(clauses) if _is_question(c)]
    questions = [clauses[i] for i in question_at]
    universe = tuple(s for s in signals.named_work_surfaces if s)
    focus_at = [("author_clause", i) for i in question_at] + [("title_line", -1)] + [("author_clause", i) for i in range(len(clauses))]
    named_in_text, focus_index, focus_spans = _pick_target_detail(named, questions + [title_line] + list(clauses), universe)

    def surface_locations() -> List[Tuple[str, int, Tuple[int, int]]]:
        # 대상 표면을 찾은 focus(질문 절·제목 줄·작성자 절)의 실제 출현. focus에서 못 찾은 첫 현재 작품 fallback이면 관계표 대표 출현이다.
        if focus_index >= 0:
            kind, at = focus_at[focus_index]
            return [(kind, at, sp) for sp in focus_spans]
        return [("author_clause", ci, (a, b)) for s, ci, a, b in table_where if s == named_in_text][:1]
    # 의견·작품 논의로 판정된 글에서 제목·첫 절이 아닌 곳의 질문은 반어로 본다('…쎄야 하는 거 아니?').
    if questions and intent in _OPINION_INTENTS and not any(q in clauses[:2] for q in questions):
        reasons.append("rhetorical_question_in_opinion")
        questions = []
        question_at = []
    # 3) 작품 표면이 있는 질문: 커뮤니티 단어는 출처·맥락 역할로만 남긴다('재획 장갤발 작품이었음?').
    for ci in question_at[:1]:
        relation = author_new_work_head(clauses[ci])
        if relation:
            mark('question_' + relation[2], ci, [('author_clause', ci, relation[1])])
            return 'question', relation[2], relation[0], clauses[ci], reasons + ['source_' + relation[2] + '_relation']
        author = author_head(clauses[ci])
        if author:
            mark('question_author_target', ci, [('author_clause', ci, author[1])])
            return 'question', 'author', author[0], clauses[ci], reasons + ['source_author_head']
    if questions and named_in_text:
        reasons += ["author_question", "target_named_surface_in_source"]
        if _cue_kind(_mask(questions[0] + " / " + title_line, named)) == "community":
            reasons.append("community_cue_as_context")
        mark("question_named_work", question_at[0], surface_locations())
        return "question", "named_work", named_in_text, questions[0], reasons
    if eval_item:
        mark("evaluation_question_evaluated_item", eval_item[2], [("author_clause", eval_item[2], sp) for sp in eval_item[3]])
        return "evaluation_question", "evaluated_item", eval_item[0], eval_item[1], reasons + ["evaluation_target_unverified"]
    # 4) 그 밖의 질문
    if questions:
        reasons.append("author_question")
        if any(_TITLE_ASK.search(c) for c in questions):
            reasons.append("title_identification_question")
            mark("question_title_identification", question_at[0])
            return "question", "unknown", None, questions[0], reasons
        # 대상 단서는 질문 절과 제목에서만 찾는다(본문 곳곳의 '주인공' 같은 단어로 트로프가 되지 않게).
        mark("question_cue_kind", question_at[0])
        return "question", _cue_kind(questions[0] + " / " + title_line), None, questions[0], reasons
    if intent == "make_joke" and _LAUGH.search(text):
        mark("joke_discourse_intent")
        return "joke", "unknown", None, None, reasons + ["discourse_make_joke"]
    if intent in _OPINION_INTENTS:
        for ci, clause in enumerate(clauses):
            relation = author_new_work_head(clause)
            if relation and (named_in_text is None or named_in_text == relation[0]):
                mark('opinion_' + relation[2], ci, [('author_clause', ci, relation[1])])
                return 'opinion', relation[2], relation[0], clause, reasons + ['source_' + relation[2] + '_relation']
        if named_in_text:
            mark("opinion_named_work", -1, surface_locations())
            return "opinion", "named_work", named_in_text, None, reasons + [f"discourse_{intent}", "target_named_surface_in_source"]
        kind = _cue_kind(text)
        if kind == "unknown" and intent == "discuss_genre":
            kind = "trope"
        mark("opinion_cue_kind")
        return "opinion", kind, None, None, reasons + [f"discourse_{intent}"]
    mark("unknown")
    return "unknown", "unknown", None, None, reasons


# ---------------------------------------------------------------------------
# 기준작·제외작: 비교 문형은 작품·인물·장르·행동을 모두 받으므로 작품 역할의 독립 근거가 있어야 한다.
_SIMILAR = re.compile(
    r"([가-힣A-Za-z0-9]{2,}?)\s*(?:이|가|은|는)?\s*(?:그나마\s*)?(비슷한|같은|처럼|같이|마냥|류의|계열|류)\s*([가-힣A-Za-z]*)"
)
_WORK_NOUN = re.compile(r"^(?:소설|작품|글|거|것|걸|건|느낌|누낌|분위기|감성|스타일|웹소설|작|계열|류)")
_DEMONSTRATIVE = re.compile(r"(?:이런|그런|저런)(?:거|건|것)?|이거|그거|저거|이건|그건|저건")
_ALREADY_READ = re.compile(r"([가-힣A-Za-z0-9]{2,})\s*(?:이미|벌써|다|전에)\s*(?:봤|읽었|봄|읽음|정주행)")
_NOT_THIS = re.compile(r"([가-힣A-Za-z0-9]{2,})\s*(?:말고|빼고|제외)")
_NON_WORK_TOKENS = re.compile(r"소설|웹소설|웹툰|만화|애니|작품|장르|추천|나는|난|내가")
# 'X 비슷한 거 말고', 'X 같은 건 싫어'처럼 비교 뒤에서 부정·배제하면 기준작이 아니다.
_NEGATED_COMPARISON = re.compile(r"^\s*(?:은|는)?\s*(?:말고|말구|빼고|제외|싫|별로|ㄴㄴ|노노|아닌|아니)")


def _character_names(signals: ExpertSignals) -> Set[str]:
    names = {str(e.get("text") or "").strip() for e in signals.entity_mentions or ()
             if str(e.get("entity_type") or "") == "character" or str(e.get("role") or "") == "character_focus"}
    names |= {s for s, role in signals.role_evidence if role == "character"}
    return {n for n in names if n}


# B33 R3(E5): 원문에 괄호로 표시한 제목 표면(《…》·『…』·「…」·〈…〉).
_TITLE_MARK = re.compile(r"《([^》\n]+)》|『([^』\n]+)』|「([^」\n]+)」|〈([^〉\n]+)〉")
# B33 R3b(E5): 비교 명사구 앞에 오는 문장 부사·시간 명사 중 기존 부사형 판정(_object_gap_adverb)에 없는 닫힌 집합. 명사구에
# 넣지 않고, 주어·절 머리와 명사구 사이에서는 부사형 어절처럼 건너뛴다.
_COMPARISON_NP_HALT = {"혹시", "제발", "일단", "차라리", "어차피", "딱히", "아마", "아마도", "꼭", "그럼", "그러면", "이왕",
                       "이왕이면", "기왕", "기왕이면", "아무래도", "오히려", "원래", "사실", "요새", "최근", "예전", "옛날", "나중",
                       "지난", "올해", "작년", "매일", "가끔", "자주", "보통", "주로", "빨리", "얼른", "제대로", "다들", "여러분"}
_NP_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
# B33 R3b(E5): 작성자가 같은 글에서 밝힌 작품 약어 관계('X은 … Y의 작품 약어다'). 약어·줄임말·약칭·준말을 서술한 절만 받는다.
_ALIAS_DECL = re.compile(
    r"(?<![가-힣A-Za-z0-9])([가-힣A-Za-z0-9]{2,})(?:은|는|이|가)\s+([가-힣A-Za-z0-9][가-힣A-Za-z0-9 ]*?)의\s*"
    r"(?:(?:작품|소설|웹소설|웹툰|만화|제목)\s*)?(?:약어|줄임말|약칭|준말)\s*(?:이다|다|임|입니다|이야|야)?\s*[.!?。]*\s*$"
)


def _marked_titles(clauses: Sequence[str]) -> Tuple[str, ...]:
    out: List[str] = []
    for clause in clauses:
        for m in _TITLE_MARK.finditer(clause):
            surface = next(g for g in m.groups() if g is not None).strip()
            if surface and surface not in out:
                out.append(surface)
    return tuple(out)


def _comitative_stem(token: str) -> str:
    """'사서와'·'여관과'처럼 앞 음절 받침에 맞는 공동격 조사 '와/과'로 끝나면 그 조사를 뗀 줄기(B33 R3b, E5).

    받침과 맞지 않는 '무화과'나 두 음절 어절('사과')은 그대로 둔다. 비교어 앞 '이랑/랑'은 기존 _PARTICLE_END가 뗀다.
    """
    if len(token) >= 3 and token[-1] in ("와", "과"):
        prev = token[-2]
        if "가" <= prev <= "힣" and ((ord(prev) - 0xAC00) % 28 == 0) == (token[-1] == "와"):
            return token[:-1]
    return token


def _comparison_np_halts(tok: str) -> bool:
    """비교 명사구에 넣지 않는 어절인가(B33 R3b, E5). 기존 판정을 그대로 쓴다: 자기 지칭·지시·시간·부사형 어절, 일반 작품·장르·
    영역 명사, 화자 단어, 관형절 용언, 독서·평가·요청·비교 단서."""
    return bool(not _NP_TOKEN.fullmatch(tok) or tok in _SELF_WORDS or tok in _SELF_SUBJECT or tok in _SELF_STEMS
                or tok in _PRONOUN_TARGETS or tok in _RECENT_DEICTIC or tok in _DEMONSTRATIVE_SUBJ or tok in _DEICTIC_DET
                or tok in _OTHER_DET or tok in _NEW_WORK_DET or tok in _DETERMINERS or tok in _GENERIC_DEICTIC
                or tok in _EXCLUDE_MARK or tok in _CLAUSE_LEAD or tok in _GENERIC_WORDS or tok in _DOMAIN_NOUNS
                or tok in _COMPARISON_NP_HALT or _object_gap_adverb(tok) or _is_work_noun(tok) or _is_genre(tok)
                or _STORY_AGENT.match(tok) or _REPORTED_SPEAKER.match(tok + " ") or _ADNOMINAL_VERB.search(tok)
                or _CUE_READING.search(tok) or _CUE_EVALUATION.search(tok) or _EVAL_PRED.search(tok) or _REQUEST.search(tok)
                or re.search(r"비슷|같|처럼|마냥", tok))


def _comparison_np_kind(tok: str, right: str) -> str:
    """비교 명사구 어절 종류(B33 R3b/R3c, E5): genitive('탑의') / lead(맨 앞에만 두는 관형어: 관형어 목록 '작은'과 '-은/-는' 끝
    '검은') / adnominal(그 밖의 받침 ㄴ 어절 '푸른'·'생존') / bare('겨울') / ''(밖).

    right는 오른쪽 이웃 어절의 종류다. 한 음절 맨 명사('강')는 바로 뒤가 소유격일 때만 받는다. adnominal은 맨 앞이면 관형어,
    안쪽이면 명사로 둔다. '-은/-는' 끝 어절은 주제어('작성자는'·'민지는')와 겹치므로 lead로 맨 앞에만 둔다(_source_comparison_np).
    """
    if _comparison_np_halts(tok):
        return ""
    if len(tok) >= 2 and tok.endswith("의"):
        stem = tok[:-1]
        return "" if _comparison_np_halts(stem) or _complex_coda(stem) else "genitive"
    last = tok[-1]
    hangul = "가" <= last <= "힣"
    if len(tok) >= 2 and (_ADNOMINAL_MODIFIER.search(tok) or last in ("은", "는")):
        return "lead"
    if len(tok) >= 2 and hangul and (ord(last) - 0xAC00) % 28 == 4:
        return "adnominal"
    if _bare_object(tok):
        return "bare"
    if len(tok) == 1 and right == "genitive" and hangul and (ord(last) - 0xAC00) % 28 not in (4, 8):
        return "bare"
    return ""


def _source_comparison_np(clause: str, start: int, end: int, floor: int = 0) -> Optional[Tuple[str, int, int, str]]:
    """비교 토큰 [start, end) 앞의 원문 명사구가 구문상 분명할 때 그 전체 표면 (표면, 시작, 끝, "source_np")(B33 R3b/R3c, E5).

    같은 절에서 토큰 앞 어절을 거꾸로 걸으며 소유격('탑의')·조사 없는 명사('겨울'·'눈꽃')·관형어('검은')만 명사구로 받는다.
    명사구 앞은 자기 지칭 주어('나는'·'저는' 등) 또는 절 머리여야 하고, 둘 사이에는 부사형 어절('지금'·'실제로')만 올 수 있다.
    맨 앞 관형어(lead·adnominal)는 주어·절 머리 바로 뒤에서만 받는다('새로 나온 X'·'재밌게 본 X'의 관형절은 받지 않는다).
    lead('-은/-는' 끝·관형어 목록)를 만나면 거기서 멈춘다. 절 머리에서 시작하면 맨 앞이 소유격, 그 밖의 받침 ㄴ 관형어, 관형어
    목록 lead, 소유격 바로 앞 lead·맨 명사여야 한다('작성자는 달빛기사'처럼 주제어로 시작하면 받지 않는다). 하나라도 어긋나거나
    토큰 앞 명사가 없으면 None이고 호출자는 기존 토큰을 쓴다. 원문 명사구는 작품 표면 입력이 아니므로 공개 기준작 권한이 없다.
    R3d: floor가 있으면 그 앞 어절(같은 절의 비현재 요청 범위)은 보지 않고 floor를 절 머리로 본다.
    """
    if start <= 0 or not clause[start - 1].isspace() or _comparison_np_halts(clause[start:end]):
        return None
    words = [(m.group(), m.start()) for m in re.finditer(r"\S+", clause[:start]) if m.start() >= floor]
    kinds: List[str] = []
    i = len(words) - 1
    while i >= 0 and len(kinds) < 6:
        kind = _comparison_np_kind(words[i][0], kinds[-1] if kinds else "head")
        if not kind:
            break
        kinds.append(kind)
        i -= 1
        if kind == "lead":
            break
    if not kinds:
        return None
    first, lead_word, np_start = kinds[-1], words[i + 1][0], words[i + 1][1]
    before_genitive = len(kinds) >= 2 and kinds[-2] == "genitive"
    j = i
    if first not in ("lead", "adnominal"):
        while j >= 0 and (_object_gap_adverb(words[j][0]) or words[j][0] in _COMPARISON_NP_HALT):
            j -= 1
    if j >= 0:
        if words[j][0] not in _SELF_SUBJECT:
            return None
    elif not (first in ("genitive", "adnominal") or (first == "bare" and before_genitive)
              or (first == "lead" and (bool(_ADNOMINAL_MODIFIER.search(lead_word)) or before_genitive))):
        return None
    return clause[np_start:end], np_start, end, "source_np"


def _declared_aliases(clauses: Sequence[str]) -> Mapping[str, Tuple[str, int, int, int]]:
    """작성자 절에서 명시한 작품 약어 관계 {약어: (전체 표면, 절 index, 시작, 끝)}(B33 R3b, E5).

    'X은 … Y의 작품 약어다'처럼 약어 관계를 서술한 절에서만 뽑는다. Y 앞의 매체·작품 명사('웹소설')와 지시 관형사는 떼고, Y가
    원문에 그대로 있는 구간만 쓴다. 공식 작품 확인이 아니며, 처음 밝힌 관계 하나만 쓴다.
    """
    out: dict = {}
    for ci, clause in enumerate(clauses):
        for m in _ALIAS_DECL.finditer(clause):
            alias, base = m.group(1), m.start(2)
            words = [(w.group(), base + w.start()) for w in re.finditer(r"\S+", m.group(2))]
            while words and (_is_work_noun(words[0][0]) or words[0][0] in _DEICTIC_DET):
                words.pop(0)
            if (not words or alias in out or alias in _PRONOUN_TARGETS or alias in _SELF_WORDS
                    or _comparison_np_halts(words[0][0])):
                continue
            a, b = words[0][1], words[-1][1] + len(words[-1][0])
            full = clause[a:b]
            if full != alias and not _REQUEST.search(full):
                out[alias] = (full, ci, a, b)
    return out


def _aligned_comparison_surface(clause: str, start: int, end: int, named: Sequence[str], title_terms: Sequence[str],
                                marked: Sequence[str], ends: Sequence[int] = (), floor: int = 0
                                ) -> Optional[Tuple[str, int, int, str]]:
    """비교 토큰 [start, end)를 덮는 같은 절의 실제 출현 중 고른 표면 (표면, 시작, 끝, 출처)(B33 R3/R3b).

    작품 표면 입력(named)이 맞으면 그중 가장 긴 것을 쓴다. 없으면 제목어 신호(title_term)·원문 괄호 제목(marked)·구문상 분명한
    원문 명사구(source_np) 중 가장 긴 것이고 같은 길이면 앞 출처다. 신호 출현은 토큰 끝 또는 ends(떼어 낸 조사 앞뒤 위치)에서
    끝나고 어절 경계에서 시작해야 하며, 첫 어절이 화자·지시어·부사(나는·지금·실제로 등)면 제목으로 보지 않는다. 원문에 그대로
    나온 표면 하나만 쓰고 여러 출처나 절을 이어 붙이지 않는다.
    """
    stops = (end,) + tuple(e for e in ends if e != end)
    found: List[Tuple[str, int, int, str]] = []
    for origin, surfaces in (("named", named), ("title_term", title_terms), ("marked", marked)):
        for surface in surfaces:
            s = str(surface or "").strip()
            if not s:
                continue
            first = s.split()[0]
            if (first in _SELF_SUBJECT or first in _PRONOUN_TARGETS or first in _RECENT_DEICTIC or first in _DEMONSTRATIVE_SUBJ
                    or _object_gap_adverb(first) or _REQUEST.search(s) or re.search(r"비슷한|같은", s)):
                continue
            for stop in stops:
                a = stop - len(s)
                if a < floor or a > start or clause[a:stop] != s or (a > 0 and (clause[a - 1].isalnum() or clause[a - 1] == "_")):
                    continue
                found.append((s, a, stop, origin))
    pool = [item for item in found if item[3] == "named"]
    if not pool:
        pool = found + [item for item in (_source_comparison_np(clause, start, end, floor),) if item]
    best: Optional[Tuple[str, int, int, str]] = None
    for item in pool:
        if best is None or item[2] - item[1] > best[2] - best[1]:
            best = item
    return best


def _reference_works(clauses: Sequence[str], named: Sequence[str], characters: Set[str], title_terms: Sequence[str] = (), *,
                     trace: Optional[list] = None):
    """(표면, 근거) 목록과 보류 사유를 돌려준다. B33: trace(list)를 주면 결과 표면마다 (표면, 근거, 절 index, 비교 토큰 시작, 끝)을
    같은 pass에서 적는다.

    B33 R3/R3b(E5): 비교 토큰을 덮는 작품 표면 입력·제목어 신호·원문 괄호 제목, 또는 구문상 분명한 원문 명사구가 같은 절에 그대로
    있으면 그 전체 표면과 실제 구간을 쓴다(_aligned_comparison_surface). 작품 표면 입력이 아니면 공개 기준작 권한은 없다. 없으면
    기존처럼 비교 토큰이고, 구간은 떼어 낸 조사를 뺀 실제 표면 구간이다. '와/과 비슷한·같은'의 공동격 조사는 받침이 맞을 때만
    뗀다. 장르·인물·행동 비교·부정 비교·작품 유형 검사는 기존처럼 비교 토큰에 먼저 한다. 부인·계획·반사실 요청 표현 앞의 비교는
    기준작이 아니다. 작성자가 같은 글에서 그 토큰의 작품 약어 관계를 밝혔으면 전체 이름도 원문 비교 표면으로 두고, held에
    reference_source_alias:<약어>-><전체>를 남긴다.
    """
    out: List[Tuple[str, str]] = []
    held: List[str] = []
    marked = _marked_titles(clauses)
    aliases = _declared_aliases(clauses)
    for ci, clause in enumerate(clauses):
        cut = _request_tail_start(clause)
        # B33 R3d(E1/E5): 비현재 요청 범위 뒤의 실제 요청은 별도 원범위다. 원문 명사구는 그 tail 시작(floor) 앞으로 넓히지 않는다.
        floor = _request_tail_range(clause)[0] if cut else 0
        for m in _SIMILAR.finditer(clause):
            comparator, follow = m.group(2), m.group(3) or ""
            token = _PARTICLE_END.sub("", m.group(1))
            if comparator in {"비슷한", "같은", "같이"}:
                token = _comitative_stem(token)
            if not token or token in _PRONOUN_TARGETS or _DEMONSTRATIVE.fullmatch(token):
                continue
            head = token
            span = (m.start(1), m.start(1) + len(token))
            ends = (m.end(1), m.end(1) + 1) if clause[m.end(1):m.end(1) + 1] in ("이", "가", "은", "는") else (m.end(1),)
            # B33 R3d(E5): 조사를 뗀 끝 토큰이 짧아도 전체 표면 정렬을 먼저 한다. 그 정렬은 원래 어절 끝에서 하고('바람의 지도'), 공동격
            # '이랑'을 뗀 경우만 뗀 끝에서 한다('푸른 사막의 왕'). 정렬 근거가 없을 때만 조사를 뗀 토큰을 길이로 버린다.
            align_end = span[1] if len(token) >= 2 or m.group(1)[len(token):] == "이랑" else m.end(1)
            aligned = _aligned_comparison_surface(clause, span[0], align_end, named, title_terms, marked, ends, floor)
            if aligned and len(aligned[0]) < 2:
                aligned = None
            if len(token) < 2 and not aligned:
                continue
            if _NEGATED_COMPARISON.match(clause[m.end():]):
                held.append(f"reference_hold:negated_comparison:{token}")
                continue
            if m.start(1) < cut:
                held.append(f"reference_hold:not_current_request:{token}")
                continue
            if aligned and aligned[3] == "named":
                named_hit, span = aligned[0], (aligned[1], aligned[2])
            else:
                # B33 R3d(E5): 기존 부분 일치 fallback도 어절 경계에서 시작해 비교 토큰 끝(또는 떼어 낸 조사 자리)까지 덮는 표면만 받는다.
                at = m.start(1)
                boundary = at == 0 or not (clause[at - 1].isalnum() or clause[at - 1] == "_")
                named_hit = next((s for s in named if s and boundary
                                  and any(clause[at:stop] == s for stop in (span[1],) + tuple(ends))), None)
                if named_hit:
                    span = (at, at + len(named_hit))
            action = comparator in {"처럼", "같이", "마냥"}
            if action and token in characters:
                # 인물을 행동 비교에 쓴 표면은 작품 표면 입력이 있어도 기준작이 아니다.
                held.append(f"reference_hold:character_action_comparison:{token}")
                continue
            if named_hit:
                token = named_hit
                basis = "named_work_surface"
            elif token in characters:
                held.append(f"reference_hold:character_entity:{token}")
                continue
            elif action:
                held.append(f"reference_hold:action_comparison:{token}")
                continue
            elif _is_genre(token):
                held.append(f"reference_hold:genre:{token}")
                continue
            elif not _WORK_NOUN.match(follow):
                held.append(f"reference_hold:not_work_typed:{token}")
                continue
            else:
                hinted = any(t and (t == head or t in m.group(1)) for t in title_terms)
                if aligned:
                    token, span = aligned[0], (aligned[1], aligned[2])
                    hinted = hinted or aligned[3] == "title_term"
                basis = "work_typed_comparison+title_term" if hinted else "work_typed_comparison"
            if token not in [t for t, _ in out]:
                out.append((token, basis))
                if trace is not None:
                    trace.append((token, basis, ci, span[0], span[1]))
            # B33 R3b(E5): 같은 글에서 작성자가 이 비교 토큰의 작품 약어 관계를 밝혔으면 그 전체 표면도 같은 비교 대상의 원문
            # 표면으로 둔다. 작품 표면 입력이 아니면 공개 권한이 없고, 관계는 held(사유 목록)에 reference_source_alias로 남긴다.
            alias = aliases.get(head)
            if alias and alias[0] not in [t for t, _ in out]:
                full, alias_ci, alias_start, alias_end = alias
                alias_basis = ("named_work_surface" if full in named else "work_typed_comparison+title_term"
                               if any(t and t == full for t in title_terms) else "work_typed_comparison")
                out.append((full, alias_basis))
                held.append(f"reference_source_alias:{head}->{full}")
                if trace is not None:
                    trace.append((full, alias_basis, alias_ci, alias_start, alias_end))
    return tuple(out), held


def _excluded_works(clauses: Sequence[str], named: Sequence[str], characters: Set[str], *, trace: Optional[list] = None):
    """제외 표면 (표면, 근거)와 보류 사유. B33: trace(list)를 주면 결과 표면마다 (표면, 근거, 절 index, 토큰 시작, 끝, 문형)을 적는다."""
    out: List[Tuple[str, str]] = []
    held: List[str] = []
    for ci, clause in enumerate(clauses):
        for pattern, needs_named in ((_ALREADY_READ, False), (_NOT_THIS, True)):
            for m in pattern.finditer(clause):
                token = _strip_eval_particle(m.group(1))
                if (len(token) < 2 or token in _PRONOUN_TARGETS or _DEMONSTRATIVE.fullmatch(token)
                        or _NON_WORK_TOKENS.fullmatch(token)):
                    continue
                named_hit = next((s for s in named if s and s in m.group(1)), None)
                if named_hit:
                    token = named_hit
                    basis = "named_work_surface"
                elif token in characters or _is_genre(token) or needs_named:
                    held.append(f"excluded_hold:{'needs_work_surface' if needs_named else 'not_work'}:{token}")
                    continue
                else:
                    basis = "already_read"
                if token not in [t for t, _ in out]:
                    out.append((token, basis))
                    if trace is not None:
                        trace.append((token, basis, ci, m.start(1), m.end(1),
                                      "already_read" if pattern is _ALREADY_READ else "not_this"))
    return tuple(out), held


# ---------------------------------------------------------------------------
# 논의 대상 매체
_MEDIA_WORDS = {"만화": "manga", "웹툰": "webtoon", "애니": "anime", "영화": "film", "게임": "game"}
_MEDIA_PRED = re.compile(r"(만화|웹툰|애니|영화|게임)(?:인데|이다|임|이야|야|네|였|이었|이던데)")
_MEDIA_TOPIC = re.compile(r"(?:^|\s)(?:소년|소녀|성인|순정|일본)?(만화|웹툰)(?:도|들|는|은)(?=\s|$)")
_MEDIA_LOCATIVE = re.compile(r"(만화|웹툰|애니)(?:에서|에서는|속)(?=\s|$)")
_MEDIA_EDITION = re.compile(r"(?:만화|웹툰|애니|소설)판")
_NOVEL_TARGET = re.compile(r"(?:웹소설|소설)(?:인데|이다|임|이야|야|도|은|는|들)(?=\s|$)")
# 소설을 논의 장소로 두는 절('소설에도 많냐', '소설에서도')이 있으면 다른 매체로 옮기지 않는다.
_NOVEL_LOCATIVE = re.compile(r"(?:웹소설|소설)(?:에서|에서도|에도|에선|에는|로는|계|판)(?=\s|$|[?!.~])")


def _target_media(clauses: Sequence[str], *, trace: Optional[dict] = None) -> Tuple[str, Optional[str]]:
    """논의 대상 매체와 그 절. B33: trace(dict)를 주면 고른 문형·절 index·매체어 구간을 같은 pass에서 적는다."""
    text = " / ".join(clauses)
    if _MEDIA_EDITION.search(text) or _NOVEL_TARGET.search(text) or _NOVEL_LOCATIVE.search(text):
        return "unknown", None
    for rule, pattern in (("media_predicate", _MEDIA_PRED), ("media_topic", _MEDIA_TOPIC), ("media_locative", _MEDIA_LOCATIVE)):
        for ci, clause in enumerate(clauses):
            m = pattern.search(clause)
            if m:
                if trace is not None:
                    trace.update(rule=rule, span_index=ci, word_span=m.span(1))
                return _MEDIA_WORDS.get(m.group(1), "unknown"), clause
    return "unknown", None


# ---------------------------------------------------------------------------
# 사건 틀: 술어·주어·목적어·여격을 격조사로 뽑아 요지와 원문 출현을 대조한다(범용 구문 분석기가 아님).
_SEG_BOUNDARY = re.compile(r"[,，;]|(?:며|고|지만|는데|면서|으며)\s")
_DATIVE_TAIL = re.compile(r"(?:에게는|한테는|에게도|한테도|께는|에게|한테|께)$")
_NON_ARG_TAIL = re.compile(r"(?:로는|으로는|에서는|에는|로서는|에서|으로|로|에|의)$")
_ADVERBIAL_AFTER_OBJ = re.compile(r"^\s*(?:위해|위한|위하여|통해|통한|대해|대한|두고|향해|따라)")
# 관형형(-은/-는)과 주제 조사를 가르기 위해, 흔한 용언 어간 끝으로 끝나는 줄기는 논항에서 뺀다.
_VERBAL_STEM_END = re.compile(r"(?:하|되|했|됐|었|았|였|겠|던|있|없|않|싶|같|좋|싫|많|크|쁘|롭|답|스럽|엽|춥|덥|낮|높|짧|길|넓|좁)$")
_BARE_VERBAL_TAIL = re.compile(r"(?:다|음|함|임|냐|나|니|까|게|고|서|며|지|는|은|던|을|를|의|에|로|와|과|ㅋ+|ㅠ+)$")
_CAUSATIVE_NEXT = set("이였여")
_NON_EVENT_PRED = {"않", "못", "없", "있", "하", "되", "이"}
_EVENT_PARAPHRASE = {"희생", "죽음", "사망", "조화", "어울림", "읽"}
_PRED_REST = re.compile(r"^(?:다|었|았|였|했|한다|하는|하고|하며|하여|해서|된|되|는다|던|지$|지\s|고|며|어서|아서|음$|기$|게$)")
# 어떤 경로로 원문과 맞았든, 이런 모양의 어절은 사실 술어로 보고 사건 틀 검사를 거친다.
_LOOKS_PRED = re.compile(r"(?:다|다는|다고|다며|는다|던|고|며)$|(?:었|았|였|했|줬|봤|왔|갔|났|졌|됐)")
_DEMONSTRATIVE_SUBJ = {"이게", "이거", "이건", "그게", "그거", "그건", "저게", "저거", "이것", "그것", "이", "그"}
# 조사가 붙은 한 음절 명사(검을, 돈이)도 논항이다. 의존 명사는 뺀다.
# 영역 명사(전개·설정·결말 등)는 결속 수에는 세지 않지만 사건 논항·태도 대상으로는 대조한다. 메타어만 논항에서 뺀다.
_DOMAIN_NOUNS = {"서사", "이야기", "내용", "설정", "전개", "분량", "화수", "부분", "측면", "방식", "요소", "상황", "장면", "씬",
                 "캐릭터", "인물", "등장인물", "작가", "유형", "주제", "대상", "결말"}
_BOUND_NOUNS_1 = {"것", "수", "등", "때", "곳", "데", "바", "줄", "척", "듯", "뿐", "만", "점", "말", "일", "게", "건", "걸"}
_INTERROGATIVES = {"뭐", "뭣", "무엇", "누구", "누가", "어디", "언제", "왜", "어느"}
_EXIST_NEEDLE = r"(?<![가-힣])(?:있|없)(?=[가-힣]|$)"
_AUX_BEFORE_EXIST = re.compile(r"(?:고|수|어|아|여|해|져|워|게)\s*$")
_PASSIVE_AFTER = re.compile(r"^(?:해지|해졌|해져|당하|당했|당해|받았|받는|받고|되었|됐|되어|되는|된다|히|혀|려서|려졌)")


def _is_meta(stem: str) -> bool:
    return stem in _GENERIC_WORDS and stem not in _DOMAIN_NOUNS


def _args_in(text: str) -> Tuple[List[str], List[str], List[str]]:
    """(주어, 목적어, 여격) 줄기."""
    subj: List[str] = []
    obj: List[str] = []
    dat: List[str] = []
    toks = list(re.finditer(r"[가-힣A-Za-z0-9]+", text))
    for i, m in enumerate(toks):
        t = m.group(0)
        if len(t) < 2:
            continue
        if _DATIVE_TAIL.search(t):
            stem = _DATIVE_TAIL.sub("", t)
            if (len(stem) >= 2 or (len(stem) == 1 and stem not in _BOUND_NOUNS_1)) and not _is_meta(stem):
                dat.append(stem)
            continue
        if _NON_ARG_TAIL.search(t):
            continue
        stem = re.sub(r"(?:께서|이|가|은|는|을|를|도|와|과|랑|이랑|하고)$", "", t)
        # 한 음절 줄기에 은/는이 붙으면 관형형 용언(사는·가는)과 가를 수 없어 논항으로 받지 않는다. 의문사도 논항이 아니다.
        if stem in _INTERROGATIVES or (len(stem) == 1 and re.search(r"(?:은|는)$", t)):
            continue
        if not stem or (len(stem) == 1 and (stem in _BOUND_NOUNS_1 or not "가" <= stem <= "힣")) or _is_meta(stem) \
                or _VERBAL_STEM_END.search(stem) or (len(stem) == 1 and len(t) < 2):
            continue
        if re.search(r"(?:을|를)$", t):
            if not _ADVERBIAL_AFTER_OBJ.match(text[m.end():]):
                obj.append(stem)
        elif re.search(r"(?:께서|이|가|은|는|도)$", t):
            subj.append(stem)
        elif re.search(r"(?:와|과|랑|이랑|하고)$", t) and i + 1 < len(toks) and re.search(r"(?:께서|이|가|은|는)$", toks[i + 1].group(0)):
            subj.append(stem)
    return subj, obj, dat


_ADVERBS = {"진짜", "정말", "너무", "완전", "존나", "좀", "약간", "그냥", "아주", "매우", "엄청", "되게", "걍", "레알", "솔직히",
            "역시", "확실히", "특히", "결국", "오늘", "요즘", "이번", "다시", "벌써", "아직", "계속", "그래도", "근데", "그리고"}


def _bare_initial(seg: str) -> Optional[str]:
    toks = re.findall(r"[가-힣A-Za-z0-9]+", seg)
    if toks and len(toks[0]) >= 2 and toks[0] not in _GENERIC_WORDS and toks[0] not in _ADVERBS and not _BARE_VERBAL_TAIL.search(toks[0]) and not _DATIVE_TAIL.search(toks[0]):
        return toks[0]
    return None


def _clause_args(clause: str) -> Tuple[List[str], List[str], List[str]]:
    m = _reported_speaker_lead(clause)
    c = clause[m.end():] if m else clause
    subj, obj, dat = _args_in(c)
    toks = re.findall(r"[가-힣A-Za-z0-9]+", c)
    if not subj and len(toks) >= 2:
        b = _bare_initial(c)
        if b:
            subj.append(b)
    return subj, obj, dat


def _local_args(text: str, pos: int, bare_initial: bool = True) -> Tuple[List[str], List[str], List[str]]:
    """pos(술어 시작) 바로 앞 연결 절의 논항. 그 절에 주어가 없으면 앞 연결 절의 주어를 이어받는다."""
    bounds = [0] + [m.end() for m in _SEG_BOUNDARY.finditer(text, 0, pos)]
    seg = text[bounds[-1]:pos]
    subj, obj, dat = _args_in(seg)
    if not subj and bare_initial and bounds[-1] == 0:
        b = _bare_initial(seg)
        if b:
            subj.append(b)
    if not subj:
        for b0, b1 in reversed(list(zip(bounds[:-1], bounds[1:]))):
            prev, _, _ = _args_in(text[b0:b1])
            if not prev and b0 == 0 and bare_initial:
                b = _bare_initial(text[b0:b1])
                prev = [b] if b else []
            if prev:
                subj = prev
                break
    return subj, obj, dat


def _expert_frame(body: str, start: int) -> Tuple[List[str], List[str], List[str]]:
    seg_start = 0
    for m in _SEG_BOUNDARY.finditer(body, 0, start):
        seg_start = m.end()
    seg = body[seg_start:start]
    subj, obj, dat = _local_args(body, start, bare_initial=False)
    # 사건 명사 앞 소유격('민우의 죽음')은 사건의 주체다.
    g = re.search(r"([가-힣A-Za-z0-9]{2,})['’\"”]?의\s*$", seg)
    if g and not _is_meta(g.group(1)):
        subj.append(g.group(1))
    return subj, obj, dat


def _source_frames(clause: str, needle: str, exist: bool = False):
    """원문 절의 술어 출현마다 (논항, 부정, 어간 뒤 글자, 피동, 불확실, 존재값, 앞 구간, 성립 문맥)을 돌려준다.

    B33(H10): 성립 문맥은 원장 평가 사건과 같은 _agreement_act_detail 판정이다(조건 'X면'은 conditional).
    """
    m0 = _reported_speaker_lead(clause)
    c = clause[m0.end():] if m0 else clause
    uncertain = bool((_is_question(c) or _UNCERTAIN_SRC.search(c)) and not _RHETORICAL.search(c))
    out = []
    for m in re.finditer(needle, c, re.I):
        if exist and _AUX_BEFORE_EXIST.search(c[:m.start()]):
            continue
        args = _local_args(c, m.start())
        neg = _negated_at(c, m.start(), m.end())
        stem_end = m.start() + 1 if (exist or needle.startswith("(?<![가-힣])")) else m.end()
        exist_val = (c[m.start()] == "있") != neg if exist else None
        seg_start = max([0] + [b.end() for b in _SEG_BOUNDARY.finditer(c, 0, m.start())])
        realization = _agreement_act_detail(c, m.start(), m.end()).realization
        out.append((args, neg, c[stem_end:stem_end + 1], bool(_PASSIVE_AFTER.match(c[stem_end:])), uncertain, exist_val, c[seg_start:m.start()],
                    realization))
    return out


def _same_arg(a: str, b: str) -> bool:
    """같은 논항인가. 기본은 같은 표면이다. 짧은 쪽이 영역 명사이고 긴 쪽이 그 명사로 끝날 때만(애증서사 ↔ 서사) 허용한다.
    인명·직책(검사 ↔ 검사장, 민우 ↔ 김민우)에는 부분 일치를 쓰지 않는다."""
    if a == b:
        return True
    short, longer = sorted((a, b), key=len)
    return short in _DOMAIN_NOUNS and len(longer) > len(short) and longer.endswith(short)


def _title_ambiguous(name: str, title: str) -> bool:
    esc = re.escape(name)
    return bool(re.search(esc + r"(?:와|과|랑|이랑|하고|,)\s*[가-힣A-Za-z0-9]{2,}", title)
                or re.search(r"[가-힣A-Za-z0-9]{2,}(?:와|과|랑|이랑|하고|,)\s*" + esc, title))


def _bare_in(a: str, seg: str) -> bool:
    return bool(re.search(r"(?<![가-힣A-Za-z0-9])" + re.escape(a) + r"(?![가-힣A-Za-z0-9])", seg))


def _args_aligned(e_args, c_args, clause: str, title: str) -> bool:
    e_subj, e_obj, e_dat = e_args
    c_subj, c_obj, c_dat = c_args
    others = {"subj": c_subj, "obj": c_obj, "dat": c_dat}
    for role, expected, actual in (("subj", e_subj, c_subj), ("obj", e_obj, c_obj), ("dat", e_dat, c_dat)):
        for a in expected:
            if any(_same_arg(a, x) for x in actual):
                continue
            # 다른 격으로 원문에 있으면 역할이 뒤바뀐 것이다.
            if any(_same_arg(a, x) for r, xs in others.items() if r != role for x in xs):
                return False
            # 조사 없이 쓴 맨 어절은 술어 바로 앞 연결 절 안에 있을 때만 그 자리 논항으로 인정한다.
            if not actual and _bare_in(a, clause):
                continue
            # 제목은 원문 절에 주어가 없을 때만, 제목 속 이름이 하나로 특정될 때만 주어를 채운다.
            if role == "subj" and not actual and a in title and not _title_ambiguous(a, title):
                continue
            return False
    return True


# 이름별 인물 역할: 인용·반박 속 부정은 작성자의 부정이 아니다. 명시 긍정·검증 근거가 약한 비인물 서술보다 우선한다.
_ROLE_NEGATION_AFTER = r"(?:은|는|이|가)?\s*(?:아니|아님|아냐|아닌)"
# 현실 역할(작품 속 직업 '작가'와 구분: 현실 저자는 '이 글/이 작품/실제/현실/원작'과 함께 쓸 때만).
_REAL_WORLD_ROLE = (r"(?:작성자|글쓴이|본인|유저|닉네임|고닉|갤러|스트리머|(?:이\s*글|이\s*작품|실제|현실|원작)\s*(?:의\s*)?작가)"
                    r"(?:다|임|이다|입니다|이야|야|이고|이며|라서|인데)?(?=\s|$|[.!?])")


def _first_person_clause(clause: str) -> str:
    if _reported_speaker_lead(clause):
        return ""
    return _QUOTED.sub(" ", clause)


def _character_role_status(name: str, source: ClaimScopeSource, signals: ExpertSignals) -> Tuple[Optional[str], Optional[str]]:
    """('negated'|'positive'|None, 근거).

    순서: 작성자 본인의 명시 부정 → 원문의 명시 긍정 → 작성자 본인의 현실 역할 서술 → 외부 검증·위치 근거.
    인용·전언 속 부정은 작성자의 부정이 아니고, 작품 속 직업 '작가'는 현실 저자 서술이 아니다.
    """
    esc = re.escape(name)
    clauses = [c for c in (_first_person_clause(x) for x in _post_clauses(source)) if c and name in c]
    for c in clauses:
        if re.search(esc + r"(?:은|는|이|가)?\s*(?:캐릭|캐릭터|등장인물|인물)" + _ROLE_NEGATION_AFTER, c):
            return "negated", "explicit_negation"
    for c in clauses:
        if _is_question(c) or _UNCERTAIN_SRC.search(c):
            continue
        if re.search(r"(?:등장인물|캐릭터|주인공|히로인|악역)\s*['‘\"“]?" + esc, c) or re.search(
            esc + r"(?:은|는|이|가)\s+(?:\S+\s+){0,2}?(?:등장인물|캐릭터|인물|주인공)(?:이다|다|임|입니다|이야|야|이고|이며|이지|인데)?(?=\s|$|[.!?])", c
        ) or re.search(esc + r"(?:이|가|은|는)?\s*(?:캐릭|캐릭터|등장인물)", c):
            return "positive", "explicit_character_word"
    for c in clauses:
        if re.search(esc + r"(?:은|는|이|가)\s+(?:\S+\s+){0,4}?" + _REAL_WORLD_ROLE, c):
            return "negated", "real_world_role"
    if (name, "character") in set(signals.role_evidence):
        return "positive", "role_evidence"
    if any(name in e and _CHARACTER_WORDS.search(e) and not re.search(r"아니|아님|아냐", e) for e in signals.character_evidence):
        return "positive", "character_evidence"
    live, _ = _live_surfaces(tuple(s for s in signals.named_work_surfaces if s), _author_clauses(source))
    works = list(live) + ["신작", "작품"]
    for c in clauses:
        if _is_question(c) or _UNCERTAIN_SRC.search(c):
            continue
        for w in works:
            for m in re.finditer(re.escape(w) + r"(?:의|에서|에\s*나오는)?\s*" + esc, c):
                if not re.match(r"^(?:이|가|은|는)?\s*(?:아니|아님|아냐|아닌|말고)", c[m.end():]):
                    return "positive", "work_adjacent"
        if re.search(esc + r"\s*(?:처럼|같이|마냥)\s*" + _NON_WORK_AFTER_COMPARISON + r"[가-힣]", c):
            return "positive", "agent_comparison"
    return None, None


# ---------------------------------------------------------------------------
# 인물·작가 역할의 개체별 근거
_CHARACTER_WORDS = re.compile(r"캐릭터|등장인물|주인공|인물|히로인")
_GENERIC_ROLE_NOUNS = {
    "주인공", "여주", "남주", "히로인", "악역", "빌런", "손주", "손자", "손녀", "엄마", "아빠", "부모", "친구",
    "동생", "형", "누나", "언니", "오빠", "작가", "독자", "용사", "마왕", "대마법사", "성녀", "여고생쟝",
}
_NON_WORK_AFTER_COMPARISON = r"(?!(?:소설|작품|글|거|것|걸|건|느낌|누낌|분위기|웹툰|만화|애니))"


def _character_basis(name: str, source: ClaimScopeSource, signals: ExpertSignals) -> Optional[str]:
    """이름 하나가 인물 역할이라는 근거를 돌려준다. 행 전체의 작품 앵커는 근거가 아니다."""
    status, basis = _character_role_status(name, source, signals)
    return basis if status == "positive" else None


def _author_basis(name: str, source: ClaimScopeSource, signals: ExpertSignals) -> Optional[str]:
    if (name, "author") in set(signals.role_evidence):
        return "role_evidence"
    if name in (source.author_names or ()):
        return "source_author_names"
    esc = re.escape(name)
    for clause in _post_clauses(source):
        if re.search(esc + r"\s*(?:님\s*)?(?:신작|작가|작품|선생)", clause) or re.search(r"작가\s*(?:님\s*)?" + esc, clause):
            return "source_author_pattern"
    return None


def filter_entity_roles(
    entities: Iterable[Mapping[str, Any]],
    source: ClaimScopeSource,
    state: RowState,
    signals: Optional[ExpertSignals] = None,
) -> Tuple[Tuple[Mapping[str, Any], ...], Tuple[Tuple[str, str, str], ...]]:
    """인물(character) 역할은 그 이름마다의 근거가 있을 때만 유지한다(행 상태 state는 근거로 쓰지 않는다)."""
    signals = signals or ExpertSignals()
    kept, dropped = [], []
    for ent in entities or ():
        text = str(ent.get("text") or "").strip()
        role = str(ent.get("role") or "")
        is_character = str(ent.get("entity_type") or "") == "character" or role == "character_focus"
        if not is_character:
            kept.append(ent)
            continue
        if not text:
            dropped.append((text, role, "empty_surface"))
        elif text in _GENERIC_ROLE_NOUNS:
            dropped.append((text, role, "generic_role_noun"))
        else:
            status, _ = _character_role_status(text, source, signals)
            if status == "negated":
                dropped.append((text, role, "character_role_negated"))
            elif status == "positive":
                kept.append(ent)
            else:
                dropped.append((text, role, "character_role_without_entity_evidence"))
    return tuple(kept), tuple(dropped)


# ---------------------------------------------------------------------------
# 전문가 요지의 원문 결속
_TEMPLATE_PHRASES = re.compile(
    r"장르/트로프 일반론|특정 작품으로 잠기지|추천 요청, 감상 순서|정식 제목|공식 제목|검색 결과|검색 증거|근거가|증거|grounding"
    r"|E\d{3}|판정|메인 화제|앵커|후보|표현 오타/축약|확인이 필요"
)
_QUOTED_TITLE = re.compile(r"['‘“\"<《「『]([^'’”\">》」』]{2,40})['’”\">》」』]")
# 추측을 표시한 괄호 덧말('(… 추정)')은 원문 해석이 아니므로 떼고 쓴다.
_HEDGED_PAREN = re.compile(r"\s*\([^()]*(?:추정|추측|아마|으로 보임|로 보임|가능성)[^()]*\)")
_PARTICLES = re.compile(r"(?:은|는|이|가|을|를|의|에|에서|으로|로|와|과|도|만|까지|부터|처럼|보다|이랑|랑|이다|입니다|임|함|했다|한다|하는|했던|하고|하며)$")
_ENDINGS = sorted({
    "했습니다", "하였다", "되었다", "있습니다", "입니다", "합니다", "습니다", "했다는", "었다고", "았다고", "였다고", "었다는",
    "았다는", "였다는", "으로써", "에서는", "에게서", "으로는", "이라는", "이라고", "스러운", "스럽게", "적으로", "하여", "해서",
    "하고", "하며", "하는", "하던", "했던", "한다", "했다", "됐다", "되어", "되는", "된다", "이다", "적인", "적이", "었다",
    "았다", "였다", "었던", "았던", "는다", "는지", "인지", "은지", "을지", "겠다", "지만", "는데", "은데", "니다", "다고",
    "다는", "다며", "으며", "으면", "고자", "에서", "에게", "으로", "처럼", "보다", "이랑", "과의", "와의", "에는", "에도",
    "이며", "이고", "이나", "이란", "라는", "라고", "까지", "부터", "들이", "들은", "들의", "들을", "들", "은", "는", "이",
    "가", "을", "를", "의", "에", "로", "와", "과", "도", "만", "랑", "음", "기", "고", "며", "던", "다", "지", "게", "서",
    "어", "아", "여", "해", "한", "할", "함", "된", "될", "됨", "적", "임",
}, key=len, reverse=True)
_VERBAL_REST = re.compile(r"^(?:었|았|였|는|은|음|지|고|어|아|다|을|기|게|여|했|해|으)")
# 사실을 더하지 않는 메타·영역 일반어와 기능 동사.
_GENERIC_WORDS = {
    "웹소설", "소설", "작품", "글", "포스트", "게시글", "게시물", "해당", "대한", "대해", "관련", "관한", "특정", "개인적",
    "개인", "작성자", "글쓴이", "독자", "커뮤니티", "장르", "장르소설", "서사", "이야기", "내용", "설정", "전개", "분량",
    "화수", "부분", "측면", "방식", "경우", "정도", "유형", "요소", "상황", "장면", "씬", "약칭", "줄임말", "표현", "태도",
    "입장", "주제", "대상", "화제", "관점", "캐릭터", "인물", "등장인물", "작가", "언급된", "위한", "통한", "위해", "통해",
    "및", "또는", "그리고", "하지만", "한편", "또한", "역시", "매우", "너무", "더", "가장", "주로", "특히", "다소", "약간",
    "함께", "모두", "서로", "자신", "같은", "같이", "처럼", "때문", "때문에", "따라", "대신", "본문", "제목", "작성",
    "일반", "전반", "스스로", "기타", "대하여", "관하여", "댓글", "점", "작성자들", "글쓴이들", "말",
}
# 보고 동사와 경동사만 둔다. 있다/없다·갖다 같은 내용 동사는 여기서 빠져 사실 주장으로 검사된다.
_FUNCTION_STEMS = {
    "하", "되", "이", "담", "나타내", "위하", "대하", "관하", "통하", "언급", "설명", "표현",
    "말하", "다루", "소개", "표", "표하", "표출", "전하", "공유", "묻", "물어", "작성", "보여주",
    "제시", "강조", "토로", "등장", "한", "했", "함",
}
_EVAL_DIMENSIONS = {"유용성", "효용", "성능", "장단점", "장점", "단점", "강함", "약함", "밸런스", "완성도", "개연성", "매력",
                    "퀄리티", "선호도", "호불호", "필요성", "비교", "우열"}
_STANCE = {
    "neg": ("불만", "불쾌", "비판", "분노", "혹평", "아쉬움", "아쉬운", "아쉽", "슬픔", "슬픈", "안타까", "안타깝",
            "연민", "동정", "비극", "실망", "짜증", "불평", "거부감", "혐오", "우려", "걱정", "답답"),
    "surprise": ("당혹", "충격", "놀람", "놀라", "경악", "황당", "어이없"),
    "pos": ("칭찬", "호평", "감탄", "기대", "선호", "호감", "만족", "즐거움", "흥미", "관심", "욕구", "애정", "호의", "좋아"),
    "q": ("질문", "궁금", "의문", "문의", "물음"),
    "req": ("요청", "추천", "부탁", "찾는", "찾고", "찾으", "찾아"),
    "joke": ("농담", "드립", "유머", "장난", "조롱", "비꼼", "풍자", "자조"),
    "neutral": ("감상", "의견", "견해", "평가", "소감", "반응", "인상", "해석", "느낌"),
}
_NEG_CUE = re.compile(
    r"불쌍|슬프|슬퍼|슬픈|안타|좆같|불쾌|싫|별로|왜\s*이러|화나|짜증|ㅡㅡ|노잼|최악|오글|실망|아쉽|아쉬|억까|못\s*보겠|ㅠ"
    r"|시발|씨발|개같|어이없|빡|열받|답답|황당|구리|노답|망했|망함|개판|좆밥"
)
_POS_CUE = re.compile(r"좋|재밌|재미|꿀잼|최고|갓|명작|기대|보고\s*싶|꼴리|꼴림|사랑|귀엽|멋지|멋있|대박|굿|(?<![가-힣])행복|웃기|땡김|땡긴|끌리|취향")
# 원문 단서에 묶이는 좁은 환언(표현만 바뀌고 새 사실을 더하지 않는 경우).
_PARAPHRASE = {
    "희생": r"위해\s*죽|목숨|바치|대신\s*죽",
    "죽음": r"(?<![가-힣])죽[가-힣]|사망",
    "사망": r"(?<![가-힣])죽[가-힣]|사망",
    "조화": r"어울리|어울림|궁합",
    "어울림": r"어울리|어울림",
    "외형": r"생겨|생긴|생김|외모|얼굴|잘생|못생",
    "외모": r"생겨|생긴|생김|외모|얼굴|잘생|못생",
    "결말": r"결말|엔딩|완결|막화|마지막",
    "읽": r"읽|봤|봄|보는|본\s",
    "원하": r"싶|원해|원하|바라|좋겠|했으면",
    "바라": r"싶|원해|원하|바라|좋겠|했으면",
    "생각": r"생각|같|듯|느낌|느껴",
    "느끼": r"생각|같|듯|느낌|느껴",
}
_SURPRISE_CUE = re.compile(r"왜\s*이러|뭐다이|이게\s*뭐|뭐냐|헐|ㄷㄷ|ㅁㅊ|(?<![가-힣])미친(?=\s*(?:[!?？。.…~,，、]|[ㅋㅎ]{2,}|$))|어이|황당|충격|놀랐|놀람|경악|\?\?|!!|;;")
_JOINT_SPEAKER = re.compile(r"(?:작성자|글쓴이)(?:와|과|및|랑|하고)\s*(?:댓글|독자|이용자)")
_COMMENTER_SPEAKER = re.compile(r"댓글|독자들|이용자들|다른\s*(?:사람|이용자|독자)|갤러들|사람들이")
_CERTAINTY = re.compile(r"확정|확실히|분명히|밝혀|드러났|판명|사실로|결국")
_UNCERTAIN_SRC = re.compile(r"모르|인지\s*모|일지|일까|아닐까|듯|같은데|궁금|려나|잘\s*모")
# '왜 이러냐', '뭐다이'처럼 불평·감탄을 담은 반어 질문은 불확실성 절로 보지 않는다.
_RHETORICAL = re.compile(r"왜\s*(?:이러|저러|그러|이럼|이래|저럼)|뭐다이|이게\s*뭐|뭐냐\s*이게")
_UNCERTAIN_EXPERT = re.compile(r"질문|궁금|의문|여부|인지|일지|일까|추측|가능성|모르|묻|물음|확인하|불확실|아닐까|듯")
_NEG_AFTER = re.compile(r"^[가-힣]{0,4}\s*(?:지\s*(?:않|못|마|말)|않|못하)")
_NEG_BEFORE = re.compile(r"(?:(?<![가-힣])안|(?<![가-힣])못)\s*$")
_ROLE_BEFORE = re.compile(r"(등장인물|캐릭터|히로인|악역|작가)(?:\s+['‘\"“]?|\s*['‘\"“])([가-힣A-Za-z0-9]{2,})")
_ROLE_AFTER = re.compile(r"['‘\"“]([가-힣A-Za-z0-9]{2,20})['’\"”]\s*(?:이라는\s*|라는\s*)?(캐릭터|등장인물|작가)")
# '은영은 즉사무림의 작가로서'처럼 따옴표 없이 이름에 역할을 서술하는 문형.
_ROLE_PRED = re.compile(
    r"([가-힣A-Za-z0-9]{2,})(?:은|는|이|가)\s+(?:\S+\s+)?(작가|캐릭터|등장인물|히로인|악역)(?:로서|으로서|이다|이며|인|이라|라|로|으로)"
)
_ROLE_WORD_ANY = re.compile(r"등장인물|캐릭터|히로인|악역|작가")
# 인용 범위의 표면. 발화·이름·표시 문구 역할은 바깥 격·인용 서술 틀과 함께 _marked_spans에서 정한다.
_QUOTE_SPAN = re.compile(r"[\"“]([^\"”]+)[\"”]|[‘']([^’']+)[’']|「([^」]+)」|『([^』]+)』")
_BRACKET_SPAN = re.compile(r"\[([^\]\n]+)\]")
_SENTENCE_END = re.compile(r"(?:다|요|음|함|임|네|지|죠|까|냐|라|자|야|군|듯|ㅋ+|ㅎ+)\s*[.!?~…]*$")
# 동의·반박: 인용·전언을 화자의 태도로 받아들이는지. 반박은 동의어에 부정이 붙은 것이다.
# 동의어. 문서·수동 표현('동의서', '공감대', '인정받다')과 어절 중간의 '나도 그렇게'('누나도 그렇게')는 동의 행위가 아니다.
_AGREE = re.compile(r"동의(?!서)|동감|공감(?!대)|맞는\s*말|맞말|인정(?!받|사정)|(?<![가-힣])나도\s*그렇게|같은\s*생각|ㅇㅈ")
_RETRACT_VERB = re.compile(r"^(?:취소|철회|정정|번복)")
_RETRACT_OBJ = {"아", "방금", "위", "앞", "내", "제", "그", "이", "말", "발언", "평가", "얘기", "이야기", "거", "건", "것", "그말", "이말"}
# B33(H11): 철회 목적어가 될 수 있는 평가 명사와 그 극성, 본인 소유 관형어, 직전 지시어.
_EVALUATION_RETRACT_OBJ = {"호평": "pos", "극찬": "pos", "칭찬": "pos", "찬사": "pos", "혹평": "neg", "악평": "neg", "비판": "neg", "비난": "neg"}
_SELF_POSSESSIVE = {"내", "제", "나의", "저의", "우리", "우리의"}
_RECENT_DEICTIC = {"방금", "아까", "앞의", "앞서", "직전의", "위의"}
_JOKE_COPULA = re.compile(r"^(?:농담|구라|뻥)(?:이다|임|이야|이고|입니다|이었|ㅋ+|$)")


def _is_retraction(text: str) -> bool:
    """자기 발화를 거두는 절인가('아 취소', '방금 말 취소', '정정합니다', '농담임'). '구독 취소'처럼 행위 명사 뒤의 취소는 아니다."""
    toks = re.findall(r"[가-힣A-Za-z0-9ㄱ-ㅎ]+", text)
    for i, w in enumerate(toks):
        if _JOKE_COPULA.match(w):
            return True
        if _RETRACT_VERB.match(w):
            prev = toks[i - 1] if i > 0 else ""
            if not prev or prev in _RETRACT_OBJ or (_TOKEN_PARTICLE.sub("", prev) or prev) in _RETRACT_OBJ:
                return True
    return False


_SELF_WORDS = {"나", "내가", "나는", "난", "나도", "저", "제가", "저는", "전", "저도", "내", "제"}
_SPEECH_NOUNS = {"말", "평가", "의견", "얘기", "이야기", "생각", "주장", "리뷰", "후기", "말씀", "감상"}


@dataclass
class _Utterance:
    """화자 단위 안의 발화 하나: 원문 절 위치, 발화자('self' 또는 전언 화자), 종류, 본문, 원문 절, 현재 채택 상태."""
    pos: int
    speaker: str
    kind: str  # own | reported | denied(부정된 인용 틀) | uncertain(질문·가정 인용 틀)
    text: str
    source: str
    adopted: bool


def _quote_speaker(p: str, m) -> str:
    """인용문의 발화자. 따옴표 앞 주어('친구는 "…"')나 뒤의 'X의 말'('"…"는 친구 말이다', '"…"라고 친구가 말했다')에서 찾는다."""
    return _quote_speaker_detail(p, m)[0]


def _quote_speaker_detail(p: str, m) -> Tuple[str, str, Tuple[int, int]]:
    """_quote_speaker와 같은 판정. (발화자, 판정 경로, 결정 어절의 절 좌표)를 함께 돌려준다(B32)."""
    before = list(re.finditer(r"[가-힣A-Za-z0-9]+", p[:m.start()]))
    skipped = False
    # B33: 인용 바로 앞의 처소·여격 주제('독서일기에는', '버튼에는', '친구에게는')는 발화자가 아니므로 건너뛰고 그 앞 주어를 본다.
    # 출처 표지('민지에게서는', '친구한테서')는 그 앞 명사가 발화자다. 그 밖의 어절에서는 기존처럼 멈춘다.
    for token in reversed(before):
        w = token.group(0)
        if w in _SELF_WORDS:
            return "self", "quote_preceding_self_word", token.span()
        source_marker = _QUOTE_SOURCE_MARKER.fullmatch(w)
        if source_marker and len(source_marker.group(1)) >= 2:
            s = source_marker.group(1)
            return ("self" if s in _SELF_WORDS else s), "quote_preceding_source_marker", token.span()
        if len(w) >= 2 and _QUOTE_LOCATIVE_TOPIC.search(w):
            skipped = True
            continue
        if len(w) >= 2 and re.search(r"(?:은|는|이|가|께서|도)$", w):
            s = _stem_of(w)
            return (("self" if s in _SELF_WORDS else s),
                    "quote_preceding_subject_after_topic" if skipped else "quote_preceding_subject", token.span())
        break
    after = p[m.end():]
    first = re.match(r"\s*(?:는|은|이|가|이라는|라는)?\s*([가-힣A-Za-z0-9]+?)(?:의)?\s*(?:말|평가|의견|얘기|이야기|주장|말씀)", after)
    a = first or re.match(r"\s*(?:이?라고|고)\s*([가-힣A-Za-z0-9]+?)(?:이|가|는|은|께서|도)\s", after)
    if a and not first and _QUOTE_LOCATIVE_TOPIC.search(re.match(r"\s*(?:이?라고|고)\s*([가-힣A-Za-z0-9]+)", after).group(1)):
        a = None
    if a:
        route = "quote_following_speech_owner" if first else "quote_following_subject"
        return ("self" if a.group(1) in _SELF_WORDS else a.group(1)), route, (m.end() + a.start(1), m.end() + a.end(1))
    return "other", "quote_default_other", (-1, -1)


def _quote_body_offset(m: "re.Match[str]") -> Tuple[str, int]:
    """인용 내용(앞뒤 공백 제외)과 그 절 안 시작 좌표. _speaker_ledger의 기존 계산식 그대로다(B32 view 기록 공용)."""
    body = next(g for g in m.groups() if g).strip()
    offset = next(m.start(i) for i, group in enumerate(m.groups(), 1) if group is not None)
    offset += len(next(g for g in m.groups() if g) or "") - len((next(g for g in m.groups() if g) or "").lstrip())
    return body, offset


# B33: 인용 발화자 판정에서 건너뛰는 처소·여격 주제와 발화자를 직접 가리키는 출처 표지.
_QUOTE_LOCATIVE_TOPIC = re.compile(r"(?:에|에게|한테|께|에서|에다)(?:는|도|만)$")
_QUOTE_SOURCE_MARKER = re.compile(r"(.+?)(?:에게서|한테서|으로부터|로부터)(?:는|도|만)?")


# 이름 비교용 꼬리(조사·소유격·높임). 인물 이름은 이 꼬리를 뗀 전체 이름이 같을 때만 같은 사람이다('민수정' ≠ '민수').
_NAME_TAIL = re.compile(r"(?:님의|씨의|의|님|씨|에게|한테|께서|께|에만|에는|에도|에|와|과|이랑|랑|은|는|이|가|도|만|을|를)$")
# 동의의 명시 목적어 머리: 동의어 바로 앞의 여격·공동격 어절('평가에만', '일정에', '친구에게')과 타동사 '인정'의 목적격 어절('평가를').
_OBJ_HEAD_TAIL = re.compile(r"(?:에|에는|에만|에도|과|와|이랑|랑|한테|에게|께|을|를|만)$")
_UNIVERSAL = re.compile(r"모두|전부|모든")
# 동의 목적어 안의 제외 표지('달빛기사 말고 별빛용사 평가에만', 'A가 아니라 B 평가에', 'A보다 B 평가에').
_EXCLUDE_MARK = {"말고", "빼고", "제외하고", "제외", "대신", "아니라", "아니고", "아닌", "빼놓고", "제쳐두고", "차치하고"}
# 포함 개체가 여럿일 때 함께 고른 것임을 밝히는 공동격·접속 표지. 없으면 둘의 관계(선택·제외)를 확정할 수 없다.
_COORD_TAIL = re.compile(r"(?:와|과|랑|이랑|하고)$")
_EXCLUDE_SUFFIX = re.compile(r"(?:말고|빼고|대신|보다)$")
_OBJ_TRAILING = {"모두", "전부", "다", "둘", "전적으로", "적극", "완전히", "완전", "진짜", "정말", "좀", "그냥"}
# 인용 바깥 틀(따옴표 뒤 인용 서술부)의 극성·양태. 부정·질문·가정이면 그 인용은 현재 발화 사실이 아니다.
_FRAME_LEAD = re.compile(r"\s*(?:이?라고|다고|고|이라는|라는|는|은|이|가)?\s*")
_FRAME_NEG = re.compile(r"없|않|아니|아닌|안\s*(?:했|함|한|하|해|말)|못\s*(?:했|함|한|하|해)")
_FRAME_Q = re.compile(r"[?？]|(?:나|니|냐|까|는지|던가|는가)\s*[.!~…]*$")
_FRAME_COND = re.compile(r"(?:라고|이라고|고|다고)\s*(?:하면|한다면|했다면|말하면|말한다면|치면|쳐도|해도|한들)")


def _name_stems(tok: str) -> Set[str]:
    """어절에서 조사·소유격·높임·붙여 쓴 발언 명사('친구말에')를 떼어 낸 후보 어간들. 전체 이름의 정확한 비교에 쓴다."""
    out, frontier = {tok}, [tok]
    for _ in range(3):
        nxt = []
        for s in frontier:
            cands = []
            m = _NAME_TAIL.search(s)
            if m and m.start() > 0:
                cands.append(s[:m.start()])
            cands += [s[:-len(sn)] for sn in _SPEECH_NOUNS if s.endswith(sn) and len(s) > len(sn)]
            for c in cands:
                if c not in out:
                    out.add(c)
                    nxt.append(c)
        frontier = nxt
    return out


_FRAME_REPORT = re.compile(r"(?:했|말했|한|하였)다고\s*(?:알려|전해|들었|하더|한다|하던|소문|보도|기사|나왔|떠돌|퍼졌)|라고\s*(?:알려|전해|소문)"
                           r"|했다더라|했다던데|했대|했다는\s*(?:소문|말|얘기|기사)")
_FRAME_CONTRAST = re.compile(r"지만|는데|은데|으나|그러나|하지만|근데|그런데")
_FRAME_PAST_SHIFT = re.compile(r"했었|말했었|했던\s*적|예전엔|예전에는|전에는|한때|당시")
_FRAME_REAFFIRM = re.compile(r"지금도|여전히|아직도|그대로|변함없")


def _quote_frame_status(after: str, is_self: bool = False) -> str:
    """인용 바깥 틀의 상태. 인용 뒤부터 그 절 끝(또는 다음 인용 앞)까지를 본다.

    affirmed만 확정이다. conditional('라고 하면'), reported('했다고 알려졌지만' 같은 남의 전언), negated('말한 적이 없다', '말이 아니다'),
    question('했나?')은 확정이 아니다. 과거 전환('했었다', '예전에는')과, 현재 동의('지금도', '여전히') 없이 대조로 이어지는 경우
    ('했지만 지금은 …')도 확정하지 않는다. 틀의 뒤를 잘라 보지 않으므로 잘린 틀의 기본값으로 확정하는 일이 없다.
    is_self는 호출 쪽 기록용이며 판정은 발화자와 무관하게 같다.
    """
    lead = _FRAME_LEAD.match(after)
    rest = after[lead.end():] if lead else after
    if _FRAME_COND.search(after):
        return "conditional"
    if _FRAME_REPORT.search(after):
        return "reported"
    if _FRAME_NEG.search(rest):
        return "negated"
    if _FRAME_Q.search(rest.strip()):
        return "question"
    # 과거 전환과 현재 동의 없는 대조는 자기 인용이든 타인 인용이든 현재 채택 근거를 확정하지 못한다.
    if _FRAME_PAST_SHIFT.search(rest):
        return "past"
    if _FRAME_CONTRAST.search(rest) and not _FRAME_REAFFIRM.search(rest):
        return "contrast"
    return "affirmed"


# 동의 행위(v14). 동의어 하나를 행위 하나로 보고 주체·양태·대상을 함께 결속한다.
# 주체는 동의어(또는 제3자 서술어) 앞을 접속 구간으로 나눠 가까운 구간부터 찾는다. 명시적 자기 주어('나는', '나도', '내가')면 화자 본인,
# 그 밖의 인물·집단 주어('동생은', '민수가', '다들')면 다른 사람이다. 부사어 주제('평가에는', '입장에서는'), 용언 연결형('생각해도'),
# 시간·틀 명사('지금은'), 사물·발언·작품 주제어는 주어가 아니다. 관형절 속 주어('동생이 한 말에'), 이름과 어미를 가를 수 없는 어절('정아도'),
# 동의어 바로 앞의 조사 없는 인물형 명사('동생 동의함')는 주체를 확정하지 못한다(unknown). 주어가 없으면(생략) 화자 본인이다.
_SUBJ_PARTICLE = re.compile(r"(?:은|는|이|가|께서|도)$")
_SELF_SUBJECT = {"나는", "나도", "내가", "난", "나만", "저는", "저도", "제가", "전", "저만", "우리는", "우리도", "우리가", "우린", "우리만"}
_SELF_BARE = {"나", "내", "저", "제", "우리"}
_SELF_STEMS = {"나", "내", "저", "제", "우리", "난", "전"}
_SELF_COORD = re.compile(r"^(?:나|저|우리)(?:와|랑|하고|이랑)$")
_GROUP_SUBJECTS = {"다들", "모두들", "사람들", "남들", "애들", "대부분"}
_NONPERSON_TOPIC = {"이거", "그거", "저거", "이건", "그건", "저건", "이게", "그게", "저게", "이것", "그것"}
_PERSON_DOMAIN = {"작가", "캐릭터", "인물", "등장인물", "주인공", "히로인", "악역"}
_FRAME_NOUNS = {"지금", "이제", "오늘", "어제", "요즘", "요새", "최근", "이번", "처음", "나중", "예전", "옛날", "원래", "당시", "그때",
                "이때", "아까", "방금", "사실", "현재", "평소", "과거", "결국", "일단", "우선"}
_CLAUSE_LEAD = {"그리고", "근데", "그래서", "하지만", "그런데", "또", "그러니까", "암튼", "아무튼", "그러나", "게다가"}
_ADVERBIAL_TOPIC = re.compile(r"(?:에|에게|한테|께|에서|에게서|으로|로|로서|으로서|로써|보다|처럼|까지|부터|만큼|와|과|랑|이랑|하고)(?:는|은|도|만|이|가)?$")
_I_ADVERB = {"같이", "많이", "깊이", "굳이", "곰곰이", "틈틈이", "깨끗이", "일찍이", "없이", "높이", "새삼", "진심"}
_ACT_ADVERBS = {"무조건", "적극", "절대", "백퍼", "일부", "부분", "어느정도", "살짝", "항상", "언제나", "늘", "그대로", "또한",
                "역시나", "당연", "당연히", "전혀", "완전히", "전적으로", "충분히", "십분"}
# 용언 연결형('생각해도', '다시 봐도', '그래도'). -아도/-어도/-여도는 이름('정아도')과 가를 수 없다.
_VERB_CONCESSIVE = re.compile(r"(?:해|봐|돼|라|래|더라|워|쳐|져|려)도$")
_VERB_CONCESSIVE_AMBIG = re.compile(r"(?:아|어|여|와)도$")
# 관형절 속 주어를 가리는 관형형 용언('동생이 한 말', '내가 좋아하는 작품').
_ADNOMINAL_VERB = re.compile(r"(?:하는|한|할|하던|했던|된|되는|될|되던|쓴|본|보는|봤던|남긴|올린|단|적은|읽은|읽는|말한|던)$")
# 조사 없는 인물형 명사를 가를 때 부사·격 어형으로 보는 꼬리('격하게', '백번', '적극적으로', '말에').
_ADVERB_FORM = re.compile(r"(?:게|히|로|으로|번|껏|대로|만큼|처럼|까지|부터|에|에서|에게|한테|을|를|의|와|과|랑|요|다|고|서|면|지)$")
_SEG_CONNECTIVE = re.compile(r"(?:고|며|으며|지만|는데|은데|면서|니까|어서|아서|해서|는데도|더니|다가|거나|으나)$")
# B33: 후치사·연결 어미에 주제·보조사가 붙은 어절('결말에 대해서는', '생각해서는', '그에 따라서는')은 주어가 아니다.
_CONNECTIVE_TOPIC = re.compile(r"(?:해서|따라서|하여서?)(?:는|도|만)$")
_PLAIN_TOKEN = re.compile(r"[가-힣A-Za-z0-9]+")
# 제3자 주어의 인지·발화 서술('동생은 결말이 좋다고 생각한다', '동생은 결말을 좋아한다')은 그 사람의 전언이다.
_THIRD_PRED = re.compile(r"(?:다고|라고|냐고|자고)\s*(?:했|말했|하더|하던|생각|본다|봤|여긴|느낀|주장|평가)|(?:좋아|싫어)(?:하|한|함|해|했|합)"
                         r"|생각한다|생각해|생각했|생각함|평가한다|평가했")
# 전해 들은 말('결말이 좋다고 한다', '좋다고 들었다')은 주어와 상관없이 화자 본인의 평가가 아니다.
_HEARSAY_TAIL = re.compile(r"(?:다고|라고|이라고|다더라|라더라)\s*(?:한다|함|합니다|하네|하더라|하던데|하더라고|들었|들음|들었다|들었음)[.!?。~…\s]*$")
# 전언 화자 이름으로 시작한 절이라도 그 앞에 전언 서술이 없고 이름이 동의 목적어 자리면('친구 말에 동의한다') 화자 본인의 동의 절이다.
_LEAD_REPORT_MARK = re.compile(r"다고|라고|냐고|더라|했대|한대|그러더|말했|했다|하던데|카더라")
# 정정 절: 바로 앞 절에서 채택한 발화를 거둔다. 맨 '아니 '는 감탄사로도 쓰여 제3자 주체 절에서만 정정으로 본다.
_CORRECTION_LEAD = re.compile(r"^\s*(?:아\s+)?(?:아니[,，]|아니다|아니지|아냐|정정|정확히는|정확히\s*말하면)")
_CORRECTION_WEAK = re.compile(r"^\s*(?:아\s+)?아니\s")
# 반박한 발화를 목적어 없는 동의로 다시 채택할 수 있는 생각 바꿈 표지.
_MIND_CHANGE = re.compile(r"다시\s*(?:보니|생각|읽어|봐도)|생각해\s*보니|생각이\s*바뀌|마음이\s*바뀌|번복|정정")
# 청자 소유격. 앞선 전언의 발화자로 이름이 나오지 않은 사람의 발언이다.
_ADDRESSEE = {"네", "니", "너", "너의", "님", "님의", "당신", "당신의", "너네", "니네", "댁"}


def _complex_coda(tok: str) -> bool:
    """끝 음절 받침이 ㅆ·겹받침인가(용언 어간 '재밌', '없', '읽'). 명사 끝에는 드물다."""
    last = tok[-1] if tok else ""
    return "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 in (3, 5, 6, 9, 10, 11, 12, 13, 14, 15, 18, 20)


# 주체 선택·제외('내가 아니라 동생이', '나 말고 동생이')는 앞 어절을 주체에서 빼고 뒤 주어를 고른다. '뿐·만' 뒤의 '아니라'('나뿐 아니라
# 동생도')는 함께 포함한다. 주어로 보이는 어절을 제외했는데 고른 주어가 없으면 주체를 확정하지 못한다.
_SUBJ_EXCLUDE_NEXT = {"아니라", "아니고", "아닌", "말고", "대신", "빼고", "제외하고"}
_SUBJ_INCLUSIVE = re.compile(r"(?:뿐|뿐만|만)$")
_SELF_INCLUSIVE = re.compile(r"^(?:나|저|우리)(?:뿐|뿐만|만)$")


def _subject_excluded(toks: Sequence[str], i: int) -> bool:
    """toks[i]가 주체 자리에서 제외되는가('내가 아니라', '나 말고', '동생 대신'). '나뿐 아니라'처럼 포함하는 '아니라'는 제외가 아니다."""
    tk, nxt = toks[i], toks[i + 1] if i + 1 < len(toks) else ""
    if _SUBJ_INCLUSIVE.search(tk) and nxt in ("아니라", "아니고"):
        return False
    return nxt in _SUBJ_EXCLUDE_NEXT or bool(re.search(r".(?:말고|대신|빼고)$", tk))


def _segment_subject(toks: Sequence[str], lo: int, hi: int, works: Sequence[str], bare_check: bool) -> str:
    """toks[lo:hi] 구간의 주체: 'self' / 'other:<이름>' / 'unknown' / ''(주어 없음). 관형절 판정의 뒤 어절은 구간 밖(서술어)까지 본다.

    선택·제외를 먼저 반영한다: 제외 표지 앞 어절은 주체가 아니고, 그 뒤에서 고른 주어가 주체다.
    """
    return _segment_subject_detail(toks, lo, hi, works, bare_check)[0]


def _segment_subject_detail(toks: Sequence[str], lo: int, hi: int, works: Sequence[str],
                            bare_check: bool, skip: frozenset = frozenset()) -> Tuple[str, int]:
    """_segment_subject와 같은 판정에 주체를 정한 어절 index를 함께 돌려준다(B32). 결정 어절이 없으면 -1이다.

    B33: skip은 caller가 named-work 표면 안이라고 판정한 어절 index다. 작품 제목의 일부('회귀자는 웃는다'의 '회귀자는')는
    사건의 사람 주체가 아니다.
    """
    def word(i: int) -> str:
        return toks[i] if 0 <= i < len(toks) else ""
    excluded = False
    for i in range(lo, hi):
        if i in skip:
            continue
        tk, nxt = toks[i], word(i + 1)
        if _subject_excluded(toks, i):
            if tk in _SELF_WORDS or tk in _SELF_BARE or (len(tk) >= 2 and _SUBJ_PARTICLE.search(tk)):
                excluded = True
            continue
        if _SELF_INCLUSIVE.match(tk) and nxt in ("아니라", "아니고"):
            return "self", i
        if tk in _SELF_SUBJECT and not (tk.endswith("가") and _ADNOMINAL_VERB.search(nxt)):
            return "self", i
        if _SELF_COORD.match(tk) and i + 1 < hi and _SUBJ_PARTICLE.search(nxt):
            return "self", i
    unknown = excluded
    for i in range(lo, hi):
        if i in skip:
            continue
        tk, nxt = toks[i], word(i + 1)
        if _subject_excluded(toks, i) or tk in _SUBJ_EXCLUDE_NEXT:
            continue
        if (_is_adverb(tk) or tk in _CLAUSE_LEAD or tk in _I_ADVERB or tk in _ACT_ADVERBS or tk in _OBJ_TRAILING or tk in _TRUTH_SKIP
                or tk in _DEGREE_WORDS or tk in _LEX_SKIP_NEXT):
            continue
        if tk in _SELF_BARE:
            # 맨 자기 지칭('나 동의함')은 화자 본인이고, 뒤에 주어가 오면('내 동생은', '저 사람은') 소유격·관형사다.
            if not (i + 1 < hi and len(nxt) >= 2 and _SUBJ_PARTICLE.search(nxt)):
                return "self", i
            continue
        if tk in _GROUP_SUBJECTS or (re.search(r"들(?:이|은|는|도|께서)$", tk) and not tk.startswith("우리")):
            return "other:" + tk, i
        if len(tk) < 2 or not _SUBJ_PARTICLE.search(tk):
            if (bare_check and i == hi - 1 and len(tk) >= 2 and not _TOKEN_PARTICLE.search(tk) and not _ADVERB_FORM.search(tk) and not _PRED_LIKE.search(tk)
                    and tk not in _SPEECH_NOUNS and tk not in _AGREEMENT_NOUNS and tk not in _DOMAIN_NOUNS and tk not in _FRAME_NOUNS and tk not in _GENERIC_DEICTIC
                    and tk not in _NONPERSON_TOPIC and not _is_work_noun(tk) and not _works_in(tk, works) and not _complex_coda(tk)):
                unknown = True
            continue
        if _ADVERBIAL_TOPIC.search(tk) or _VERB_CONCESSIVE.search(tk) or _CONNECTIVE_TOPIC.search(tk):
            continue
        if _VERB_CONCESSIVE_AMBIG.search(tk):
            unknown = True
            continue
        stem = _stem_of(tk)
        base = re.sub(r"님$", "", stem)
        if base not in _PERSON_DOMAIN and (
                stem in _FRAME_NOUNS or stem in _SPEECH_NOUNS or stem in _AGREEMENT_NOUNS or stem in _DOMAIN_NOUNS or stem in _NONPERSON_TOPIC or tk in _NONPERSON_TOPIC
                or tk in _GENERIC_DEICTIC or _is_work_noun(tk) or _works_in(tk, works) or _VERBAL_STEM_END.search(stem)
                or _complex_coda(stem) or (len(stem) == 1 and tk[-1] in "은는")):
            continue
        if tk[-1] in "이가" and _ADNOMINAL_VERB.search(nxt):
            unknown = True
            continue
        if stem in _SELF_STEMS:
            return "self", i
        return "other:" + stem, i
    return ("unknown" if unknown else ""), -1


def _clause_subject(text: str, end: int, works: Sequence[str] = (), bare_check: bool = False) -> str:
    """text[:end] 뒤에 오는 행위의 주체: 'self'(자기 지칭·생략), 'other:<이름>'(그 밖의 인물·집단), 'unknown'(확정 불가).

    인물 이름 목록이 아니라 주어 자리로 판정한다. 접속 어미·쉼표로 나눈 구간을 행위에 가까운 쪽부터 보고, 가까운 구간이 확정하지 못하면
    (unknown) 더 거슬러 올라가지 않는다. bare_check면 행위 바로 앞의 조사 없는 인물형 명사('동생 동의함')를 unknown으로 둔다.
    """
    return _clause_subject_detail(text, end, works, bare_check)[0]


def _clause_subject_detail(text: str, end: int, works: Sequence[str] = (),
                           bare_check: bool = False) -> Tuple[str, Tuple[int, int]]:
    """_clause_subject와 같은 판정. 주체를 정한 어절의 좌표를 함께 돌려주며 생략·미확정이면 (-1, -1)이다(B32)."""
    spans = list(_PLAIN_TOKEN.finditer(text))
    toks = [m.group(0) for m in spans]
    n = sum(1 for m in spans if m.end() <= end)
    bounds = [0]
    for i in range(n - 1):
        if (_SEG_CONNECTIVE.search(toks[i]) and toks[i] not in _EXCLUDE_MARK) or re.search(r"[,，;]", text[spans[i].end():spans[i + 1].start()]):
            bounds.append(i + 1)
    bounds.append(n)
    # B33(F01): caller가 공급한 named-work 표면과 겹치는 어절은 주체 후보에서 뺀다.
    inside = [(a, b) for _, a, b in _work_spans(text, works)] if works else []
    skip = frozenset(i for i, m in enumerate(spans) if any(a < m.end() and m.start() < b for a, b in inside))
    for s in range(len(bounds) - 2, -1, -1):
        verdict, index = _segment_subject_detail(toks, bounds[s], bounds[s + 1], works, bare_check and s == len(bounds) - 2, skip)
        if verdict:
            return verdict, (spans[index].span() if index >= 0 else (-1, -1))
    return "self", (-1, -1)


# 동의 행위의 극성과 성립 문맥(v15). 동의어(또는 참·거짓 판단어)가 든 어절부터 그 동사 구성(부정어·경동사·보조 용언·의존 명사)만
# 걷는다. 종결·문장 부호에서 멈추고, 연결 어미('동의했지만', '동의한다면')에서 멈추며, 관형형 뒤 내용 명사('동의하는 사람')는 관형절 속
# 동의다. 극성(긍정·부정)과 성립 문맥(실제·질문·가정·전언·가능/의향·관형절·과거·대조)은 따로 정한다. 이중 부정('할 수밖에 없다',
# '하지 않을 수 없다')은 극성만 긍정으로 바꾸고, 그 구성을 뗀 나머지 구성·앞 절의 조건/전언 틀·뒤의 전언 서술로 성립 문맥을 본다.
_ACT_TOKEN = re.compile(r"[가-힣A-Za-z0-9ㄱ-ㅎ]+")
_ACT_NEG_PREFIX = re.compile(r"(?:비|미|불|무|반)$")
_ACT_NEG_BEFORE = {"안", "못", "절대안", "전혀안"}
_ACT_FORCED = re.compile(r"수\s*밖에\s*없|(?:안\s*할|않을|안\s*될)\s*수\s*(?:가\s*)?없|(?:안|않)\s*하고는\s*못|않고는\s*못|않을\s*도리")
_ACT_NEG = re.compile(r"않|안(?=\s|$|함|해|한|하|할|됨|돼|되|했|합|[?？!.~…])|못|아니|아님|없|반대|불가|ㄴㄴ|노노|어렵|힘들|곤란|싫")
_ACT_Q = re.compile(r"[?？]|(?:(?<!구)나|니|냐|(?<!니)까|는가|던가|나요|까요)(?=[.!~…\s]*$)|냐고|느냐고|는지|을지|할지|인지|모르겠|모름|글쎄|애매|헷갈")
_ACT_COND = re.compile(r"면(?=[\s.!?？~…]|$)|해도|하더라도|할\s*경우|하거든|이라면|라면|하든|하건|치면|해봤자|더라도")
_ACT_MODAL = re.compile(r"(?:할|될)\s*(?:수|지도|것|듯|거|게|까|만|지)|싶|할게|할래|하려|겠|해야|하자|합시다|하길|할\s*뻔|척|체하|체했"
                        r"|(?:것|거)\s*같|듯|해라|하라|해줘|하세요|해\s*주|해\s*볼|해볼|지\s*마")
_ACT_REPORT = re.compile(r"(?:한|했|하였|된|됐|하는)다고|한대|했대|한다더라|했다더라|한다던|했다던|한단다|한다나|한다며|했다며|한다면서|했다면서"
                         r"|하라고|하자고|이라고|라고|했다는|한다는")
# 구성 끝의 인용 어미('없다고', '한다는')는 그 동의가 다른 서술(알려졌다·들었다·생각한다)의 내용이라는 뜻이다.
_ACT_QUOTATIVE_END = re.compile(r"(?:다|라|냐|자)고$|(?:다|라)는$|(?:다|라)며$|(?:다|라)면서$|단다$|다더라$|라더라$")
# 동의 뒤의 전언 서술: '…, 라고 알려졌다', '동의하는 것으로 알려졌다'.
_REPORT_AFTER = re.compile(r"^[\s,，\"”’']*(?:이?라고|고)\s*(?:알려|전해|들었|들리|보도|소문|하더|한다|했다|카더|말했|주장)")
_REPORT_AFTER_OPEN = re.compile(r"^\s*(?:(?:것|걸|거)\S*\s*)?(?:알려|전해|보도|보인|보여|보였|들린|들렸)")
_ACT_PAST_IN = re.compile(r"했었|하였었|됐었|었었|했던|하던")
_ACT_PAST_BEFORE = re.compile(r"예전엔|예전에는|예전에|전에는|옛날엔|옛날에는|옛날에|한때|당시|과거엔|과거에는|처음엔|처음에는|원래는")
_ACT_PRESENT = re.compile(r"지금|이제|여전히|아직도|아직|현재|요즘|요새|오늘")
_ACT_CONTRAST_CONN = re.compile(r"(?:지만|는데|은데|으나|더니)$")
_ACT_CHANGE = re.compile(r"바뀌|바꿨|달라|변했|변함|철회|취소|생각이\s*다르")
_ACT_CONNECTIVE = re.compile(r"(?:지만|는데|은데|으나|더니|다가|면서|으며|며|니까|어서|아서|해서|거나|는데도|고|서|면|게|도록|려고|려면|자마자"
                             r"|(?:해|어|아|여|라|워)도)$")
_ACT_AUX_NEXT = re.compile(r"^(?:싶|있|계|말|만|보|봤|버|두|놓|주|줘|왔|가|않|못|마|되|됐|된|됨|돼)")
_ACT_TERMINAL = re.compile(r"(?:다|요|함|임|음|됨|셈|듯|네|죠|지|야|나|니|냐|까|래|라|해|돼|군|걸|ㅇㅇ|ㅇㅈ|ㅋ+|ㅎ+|ㅠ+|ㅜ+)$")
_ACT_ADNOMINAL = re.compile(r"(?:하는|한|할|하던|했던|했을|된|되는|될|되던|한다는|했다는|하신|하실|맞는|같은|가는|가던)$")
_ACT_AUX_NOUN = re.compile(r"^(?:수|적|것|거|게|건|걸|듯|줄|편|척|체|뿐|바|리|지|모양|만큼|때)")
_ACT_CONTINUE = re.compile(r"^(?:안|못|않|하|했|한|할|함|해|합|되|됐|된|될|됨|돼|표하|표한|표할|표했|표합|표함|보내|보낸|보냈|보냅|없|있|싶|같|어렵|힘들|싫|수|적|것|거|척|듯|편|바|불가|ㄴㄴ|노노"
                           r"|아니|아님|이다|이야|입니다|임|인가|인지|요|ㅇㅇ|ㅋ|ㅎ|좀|생각|가능|불가능)")
# 동의 행위를 지배하는 앞 절 틀. 조건 연결형('사실이라면', '보면')과 조건 부사('만약')는 가정, 전언 틀('소문에 따르면')은 전언이다.
# 행위와 틀 사이에 다른 연결 어미('좋겠지만')나 문장 부호가 있으면 그 틀은 이 행위에 미치지 않는다. 담화 접속어('그러면', '그럼')와
# '-면'으로 끝나는 명사('장면', '측면')는 조건이 아니다.
_GOV_COND_ADV = {"만약", "만일", "가령", "혹여"}
_GOV_DISCOURSE = {"그러면", "그럼", "그러면서", "왜냐면", "왜냐하면", "요약하면", "정리하면", "말하자면", "보자면", "정리하자면", "요컨대",
                  "알고보면", "따지고보면", "어찌보면", "어떻게보면", "그러고보면"}
# 말하기·보기 틀('솔직히 말하면', '생각해 보면', '돌이켜 보면', '따지고 보면')은 조건이 아니라 담화 틀이다. 목적어 뒤('결말을 보면')는 조건이다.
_GOV_FRAME_VERB = {"말하면", "따지면", "보면"}
_GOV_FRAME_LEAD = re.compile(r"(?:히|게|해|켜|고|로|이)$|^(?:다시|한마디로|지금|알고|따지고|곰곰|어찌|어떻게|이렇게|그렇게)$")
_GOV_COND_NOUN = {"장면", "측면", "화면", "정면", "표면", "이면", "라면", "국면", "전면", "후면", "내면", "외면", "반면", "방면", "지면",
                  "단면", "냉면", "수면", "체면", "가면", "평면", "서면", "대면", "당면", "일면"}
_GOV_REPORT_TOKEN = re.compile(r"^(?:따르면|듣기로는|듣기론|듣자하니|듣자니|말로는|말론|얘기로는|소문으로는|소문엔|전언으로는)$")
_GOV_BREAK = re.compile(r"(?:지만|는데|은데|으나|더니|고|며|으며|서|니까|면서|다가|거나)$")
# 앞선 발언의 참·거짓 판단('친구의 평가는 사실이다', '그 말이 맞다', '친구 말은 틀렸다')도 그 발언에 대한 동의·반박 행위다.
# 발언 명사 주어·주제 바로 뒤(부사는 건너뜀)의 판단어만 본다. 자기 발언('내 말이 맞다')은 남의 발언에 대한 판단이 아니다.
_TRUTH_NOUNS = {"평가", "말", "의견", "얘기", "이야기", "주장", "리뷰", "후기", "말씀", "감상", "분석", "지적"}
_TRUTH_POS = re.compile(r"^(?:사실(?:이|임|일|인|$)|맞(?!춤|춰|추|벌|선|은편|대|붙|서|이|먹|혀|히|장구)|옳|정확(?:하|함|해|했)|타당|팩트|정답|일리)")
_TRUTH_NEG = re.compile(r"^(?:틀(?:리|렸|린|림|려)|거짓|잘못(?:됐|된|되|이|임)|과장(?:이|임|됐|된)|헛소리|구라)")
_TRUTH_SKIP = {"다", "전부", "모두", "사실상", "대체로", "거의", "어느정도", "전적으로"}
_SELF_POSSESSIVE = {"내", "제", "나의", "저의", "우리", "우리의"}


def _governing_frame(text: str, end: int) -> str:
    """text[:end] 뒤에 오는 행위를 지배하는 앞 절 틀: 'conditional' / 'reported' / ''."""
    spans = [m for m in _PLAIN_TOKEN.finditer(text) if m.end() <= end]
    for k in range(len(spans) - 1, -1, -1):
        tk = spans[k].group(0)
        if re.search(r"[.!?？。…;]", text[spans[k].end():spans[k + 1].start() if k + 1 < len(spans) else end]):
            return ""
        if tk in _GOV_DISCOURSE or tk in _GOV_COND_NOUN:
            continue
        if tk in _GOV_FRAME_VERB and k > 0 and _GOV_FRAME_LEAD.search(spans[k - 1].group(0)):
            continue
        if (tk == "말하면" and k >= 2 and spans[k - 2].group(0) in _SELF_POSSESSIVE
                and spans[k - 1].group(0).endswith(("을", "를"))
                and _stem_of(spans[k - 1].group(0)) in _SPEECH_NOUNS):
            # '내 평가를 말하면'은 현재 자기 생각을 꺼내는 담화 틀이다. 작품/항목 목적어의 조건은 그대로 둔다.
            continue
        if tk in _GOV_COND_ADV or (len(tk) >= 2 and tk.endswith("면") and not tk.endswith("면서")) or tk.endswith("거든"):
            return "conditional"
        if _GOV_REPORT_TOKEN.match(tk):
            return "reported"
        if _GOV_BREAK.search(tk) and tk not in _EXCLUDE_MARK:
            return ""
    return ""


def _truth_acts(text: str) -> List[Tuple[int, int, bool]]:
    """앞선 발언의 참·거짓 판단 (판단어 시작, 끝, 거짓 판단어 여부). '사실 나는 …'처럼 발언 명사 주어가 없는 부사 '사실'은 판단이 아니다."""
    toks = list(_PLAIN_TOKEN.finditer(text))
    out: List[Tuple[int, int, bool]] = []
    for i, m in enumerate(toks):
        w = m.group(0)
        if not re.search(r"(?:은|는|이|가|도)$", w) or re.sub(r"(?:은|는|이|가|도)$", "", w) not in _TRUTH_NOUNS:
            continue
        if i > 0 and toks[i - 1].group(0) in _SELF_POSSESSIVE:
            continue
        j = i + 1
        while j < len(toks) and (_is_adverb(toks[j].group(0)) or toks[j].group(0) in _ACT_ADVERBS or toks[j].group(0) in _TRUTH_SKIP):
            j += 1
        if j < len(toks) and (_TRUTH_POS.match(toks[j].group(0)) or _TRUTH_NEG.match(toks[j].group(0))):
            out.append((toks[j].start(), toks[j].end(), bool(_TRUTH_NEG.match(toks[j].group(0)))))
    return out


@dataclass(frozen=True)
class _ActModeDetail:
    """_agreement_act_mode의 같은 계산에서 나온 구간·극성·성립과 시제 판정 근거(B32)."""
    start: int
    end: int
    polarity: str
    realization: str
    temporal_scope: str = _NOT_OBSERVED
    temporal_evidence_span: Tuple[int, int] = (-1, -1)


def _forced_core_span(span_text: str, match: "re.Match[str]", base: int) -> Tuple[int, int]:
    """_ACT_FORCED 치환 view(core)의 일치 구간을 원문 좌표로 되돌린다. 치환 공백과 겹치면 (-1, -1)이다."""
    pieces = []
    core_pos = text_pos = 0
    for forced in _ACT_FORCED.finditer(span_text):
        keep = forced.start() - text_pos
        pieces.append((core_pos, core_pos + keep, text_pos))
        core_pos += keep + 1
        text_pos = forced.end()
    pieces.append((core_pos, core_pos + len(span_text) - text_pos, text_pos))
    for lo, hi, origin in pieces:
        if lo <= match.start() and match.end() <= hi:
            return base + origin + match.start() - lo, base + origin + match.end() - lo
    return -1, -1


def _agreement_act_mode(text: str, lex_start: int, lex_end: int, region_start: int = 0, false_word: bool = False,
                        ga: bool = False, construction: Optional["_AgreementConstruction"] = None) -> Tuple[int, int, str, str]:
    """동의 행위 하나의 (시작, 끝, 극성, 성립 문맥).

    극성은 positive / negative다. 동의어 앞의 '안·못', 접두 '비·미·불·무·반', 구성 안의 부정은 부정이고, 이중 부정은 긍정이다.
    거짓 판단어('틀렸다')는 부정 극성에서 시작한다('틀리지 않았다'는 긍정). 성립 문맥은 actual / question / conditional / reported /
    modal(가능·의향·지시·위장·추측) / embedded(관형절 속) / past / contrast(동의했지만 지금은 아니다)다. 이중 부정 구성을 뗀 나머지로 질문·
    가정·전언·가능을 보고, 앞 절의 조건·전언 틀(_governing_frame)과 뒤의 전언 서술('…다고 알려졌다', '…것으로 알려졌다')도 본다.
    과거 표지('예전엔', '했었')는 뒤에 현재 표지('지금도', '이제')가 없을 때만 과거다. ga면 '공감이 간다'의 '가다'도 구성에 넣는다.
    """
    detail = _agreement_act_detail(text, lex_start, lex_end, region_start, false_word, ga, construction)
    return detail.start, detail.end, detail.polarity, detail.realization


def _agreement_act_detail(text: str, lex_start: int, lex_end: int, region_start: int = 0, false_word: bool = False,
                          ga: bool = False, construction: Optional["_AgreementConstruction"] = None) -> "_ActModeDetail":
    """_agreement_act_mode와 같은 판정. 성립 문맥과 별개인 과거·현재 재확인 표지와 원문 좌표를 함께 남긴다(B32)."""
    spans = list(_ACT_TOKEN.finditer(text))
    k0 = next((i for i, t in enumerate(spans) if t.start() <= lex_start < t.end()), None)
    if k0 is None:
        return _ActModeDetail(lex_start, lex_end, "positive", "actual")
    k = next((i for i, t in enumerate(spans) if t.start() <= lex_end - 1 < t.end()), k0)
    j, stop = k, ""
    while j + 1 < len(spans) and j - k < 6:
        w, nxt = spans[j].group(0), spans[j + 1].group(0)
        if re.search(r"[.!?？。…~,，;]", text[spans[j].end():spans[j + 1].start()]):
            break
        # 유효성 판정이 건너뛴 강조어와 확인한 서술어까지 같은 구성으로 읽는다.
        if construction is not None and j < construction.support_token:
            j += 1
            continue
        # 짧은 응답형 동의어 뒤의 부정('ㅇㅈ 못 함')은 같은 구성이다.
        if w == "그렇게" or (ga and j < k + 3 and _LEX_GA.match(nxt)) or (j == k and _LEX_NEG_NEXT.match(nxt)):
            j += 1
            continue
        if _ACT_CONNECTIVE.search(w):
            if re.search(r"(?:고|어|아|해|게)$", w) and _ACT_AUX_NEXT.match(nxt):
                j += 1
                continue
            stop = "connective"
            break
        if w.endswith("지") and re.match(r"(?:않|못|말|마|도|는|만)", nxt):
            j += 1
            continue
        if _ACT_TERMINAL.search(w):
            break
        if _ACT_ADNOMINAL.search(w):
            if _ACT_AUX_NOUN.match(nxt):
                j += 1
                continue
            stop = "embedded"
            break
        if _ACT_CONTINUE.match(nxt):
            j += 1
            continue
        break
    start, end = spans[k0].start(), spans[j].end()
    end += len(re.match(r"[?？!.~…]*", text[end:]).group(0))
    if construction is not None and construction.start >= 0:
        # 유효성 단계가 봉인한 원문 구간을 극성·성립 문맥도 그대로 사용한다.
        start, end = construction.start, construction.end
    span = text[start:end]
    core = _ACT_FORCED.sub(" ", span)
    last = spans[j].group(0)
    after = text[end:]
    prev = spans[k0 - 1].group(0) if k0 > 0 else ""
    nm = _AGREE.search(text, end)
    rest = text[end:nm.start() if nm else len(text)]
    # 평가 어근 자체가 부정 의미일 수 있다('싫어해서'). 어근은 극성 기준이고
    # 그 밖의 부정 연산자('싫지 않다')만 극성을 뒤집는다.
    outside_lexeme = span[:lex_start - start] + " " + span[lex_end - start:]
    negated = bool(_ACT_NEG_PREFIX.search(text[start:lex_start]) or prev in _ACT_NEG_BEFORE
                   or _ACT_NEG.search(_ACT_FORCED.sub(" ", outside_lexeme)))
    polarity = "negative" if negated != false_word else "positive"
    frame = _governing_frame(text, start)
    past_before = list(_ACT_PAST_BEFORE.finditer(text, region_start, start))
    if _ACT_Q.search(core):
        realization = "question"
    elif _ACT_COND.search(core) or frame == "conditional":
        realization = "conditional"
    elif (_ACT_REPORT.search(core) or _ACT_QUOTATIVE_END.search(last) or frame == "reported" or _REPORT_AFTER.match(after)
          or (not _ACT_TERMINAL.search(last) and _REPORT_AFTER_OPEN.match(after))):
        realization = "reported"
    elif _ACT_MODAL.search(core):
        realization = "modal"
    elif stop == "embedded":
        realization = "embedded"
    elif _ACT_PAST_IN.search(core) or (past_before and not _ACT_PRESENT.search(text, past_before[-1].end(), end)):
        realization = "past"
    elif stop == "connective" and _ACT_CONTRAST_CONN.search(last) and (_ACT_NEG.search(rest) or _ACT_CHANGE.search(rest)):
        realization = "contrast"
    else:
        realization = "actual"
    # B32: 과거 성립 판정과 같은 표지를 성립 우선순위와 독립으로 남긴다. 성립값은 위 분기 그대로다.
    past_marker = _ACT_PAST_IN.search(core)
    if past_marker:
        temporal, evidence = "past", _forced_core_span(span, past_marker, start)
    elif past_before and not _ACT_PRESENT.search(text, past_before[-1].end(), end):
        temporal, evidence = "past", past_before[-1].span()
    elif past_before:
        temporal, evidence = "present_reaffirmed", _ACT_PRESENT.search(text, past_before[-1].end(), end).span()
    else:
        temporal, evidence = "unmarked", (-1, -1)
    return _ActModeDetail(start, end, polarity, realization, temporal, evidence)


# 동의 행위의 유효성(v16). 동의어가 서술어 구성이나 짧은 독립 응답으로 쓰였을 때만 동의 행위다. 명사 수식('동의 버튼', '공감 수'),
# 파생·합성 명사('동의어', '공감능력', '인정욕구'), 다른 서술어의 논항('동의를 구했다', '공감을 눌렀다', '동의가 필요하다'), 수치 관측
# ('공감 10개')은 동의 행위가 아니다. 대상 연결(목적어 생략 시 단일 인용 복원 포함)은 유효한 행위에만 적용한다.
_LEX_PARTICLE_TAIL = {"은", "는", "이", "가", "을", "를", "도", "만", "까지", "조차", "마저"}
_LEX_COPULA_TAIL = re.compile(r"^(?:요|임|이다|이야|입니다|이에요|예요|이지|이죠|이고|이며|이긴|이네|이요|이라|ㅇㅇ|ㅇㅈ|ㅋ+|ㅎ+|ㅠ+|ㅜ+)$")
_LEX_NEG_NEXT = re.compile(r"^(?:않|아니|아님|불가|ㄴㄴ|노노|(?:안|못)(?:$|함|해|한|하|할|됨|돼|되|했))")
# 동의어 명사와 어울리는 경동사: 하다·되다, 그리고 '동의를 표한다', '공감을 보낸다'의 표하다·보내다.
_LEX_LIGHT_NEXT = re.compile(
    r"^(?:하(?:다|고|지|면|나|네|네요|죠|니|냐|자|라|게|려|도록|지만|는데|더라|세요|십시오|겠다|겠|듯|기는|기|는|던|며|면서|더라도|더니|더군|더군요)"
    r"|한(?:다|다고|다는|다면|다니까|대|단다|데|데요)|할(?:게|래|까|지|수|때|뿐|것|거|듯|만|려고)?|함"
    r"|해(?:요|라|도|서|야|줘|봤다|본다|보자)?|했(?:다|다고|다는|다며|다면|어요|었지만|었|지만|는데|던|을|다더라|나|니|냐|는지|는가|을까|을지)?|합(?:니다|니까|시다|세요)"
    r"|되(?:다|는|면|지|네요|어서|니까|었|지만)|된(?:다|다고|다는|다면|대)|될(?:까|게|것|거|듯|수)|됨"
    r"|돼(?:요|도|서|야|야지)?|됐(?:다|어요|으면|지만)?|표하(?:다|고|지|면|는|네)|표한(?:다|다고)|표할(?:게|까)|표했(?:다|어요)|표합(?:니다|니까)|표함"
    r"|보내(?:다|고|지|면|는|요)|보낸(?:다|다고)|보냈(?:다|어요)|보냅(?:니다|니까)|요|임|입니다|이요|ㅇㅇ|ㅇㅈ|ㅋ+|ㅎ+|ㅠ+|ㅜ+)$"
)
_LEX_REACTION_NEXT = re.compile(r"^(?:ㅇㅇ|ㅇㅈ|ㅋ|ㅎ|ㅠ|ㅜ)")
# '공감'은 '가다'와 어울려 서술어가 된다('공감이 간다', '공감 가는').
_LEX_GA = re.compile(r"^(?:가(?:다|고|지|면|나|네|요|는|던)?|간(?:다|다고|다면|다며|다더라)?|감|갑(?:니다|니까)?|갔(?:다|어요)?|가는|가네|가요|가던)$")
# 동의어 뒤에 와도 서술 구성을 끊지 않는 강조 부사('완전 동의 ㅋㅋ'는 '완전' 앞, '공감 백배'는 뒤).
_LEX_SKIP_NEXT = {"좀", "진짜", "정말", "완전", "적극", "격하게", "심히", "매우", "너무", "그냥", "또", "ㄹㅇ", "레알", "백배", "천배", "만배", "백퍼"}
# 명사 서술어형 동의('맞는 말이다', '맞말'). 경동사 구성('맞는 말을 했다')은 말한 행위이지 동의가 아니다.
_LEX_NOMINAL = re.compile(r"^(?:맞는\s*말|맞말)$")
_LEX_NEW_CLAUSE = re.compile(r"^(?:그리고|그러나|하지만|그래서|그런데|나는|나도|내가|저는|저도|제가|우리는|우리가|동생은|친구는)$")


@dataclass(frozen=True)
class _AgreementConstruction:
    """동의 행위의 확인된 서술어와 완결 원문 구간."""

    support_token: int
    start: int = -1
    end: int = -1


def _agreement_support_is_clause(text: str, spans: Sequence[re.Match[str]], support_token: int) -> bool:
    """모든 어형의 서술어 뒤에서 명사 수식과 새 절의 경계를 똑같이 판정한다."""
    if support_token + 1 >= len(spans):
        return True
    boundary = text[spans[support_token].end():spans[support_token + 1].start()]
    if re.search(r"[.!?？。…~,，;:]", boundary):
        return True
    next_word = spans[support_token + 1].group(0)
    if (re.match(r"(?:이견|반대)\s+없(?:음|다)", text[spans[support_token + 1].start():])
            or _LEX_REACTION_NEXT.match(next_word) or _LEX_NEG_NEXT.match(next_word)
            or _LEX_NEW_CLAUSE.fullmatch(next_word)):
        return True
    # 연결어미는 뒤 절을 잇지만 종결형 직후의 명사구는 라벨 수식일 수 있다.
    return not _ACT_TERMINAL.search(spans[support_token].group(0))


def _agreement_construction(text: str, lex_start: int, lex_end: int) -> Optional[_AgreementConstruction]:
    """text[lex_start:lex_end]의 동의어가 이룬 완결 서술 구성을 돌려준다.

    동의어가 든 어절의 나머지(꼬리)와 강조 부사를 건넌 다음 어절로 판정한다. 경동사·부정이 붙은 꼬리('동의한다', '동의안함')는
    행위다. 꼬리가 없거나 서술격·반응 꼬리('동의요', '인정임', '동의ㅋㅋ')면 절 끝이거나 뒤가 경동사·부정·반응('동의 못 함',
    '완전 동의 ㅋㅋ')일 때 행위다. 격조사 꼬리('동의는', '공감이')는 뒤가 경동사·부정('동의는 한다', '공감이 간다')일 때만 행위다.
    그 밖의 꼬리('동의어', '공감능력')와 뒤에 다른 명사가 오는 맨 동의어('동의 버튼', '공감 수가')는 행위가 아니다.
    """
    spans = list(_ACT_TOKEN.finditer(text))
    k = next((i for i, t in enumerate(spans) if t.start() <= lex_end - 1 < t.end()), None)
    if k is None:
        return None
    lexeme = re.sub(r"\s+", " ", text[lex_start:lex_end])
    tail = text[lex_end:spans[k].end()]
    nominal = bool(_LEX_NOMINAL.match(lexeme))
    ga = lexeme == "공감"
    def complete(support_token: int) -> _AgreementConstruction:
        pending = _AgreementConstruction(support_token)
        start, end, _, _ = _agreement_act_mode(text, lex_start, lex_end, ga=ga, construction=pending)
        return _AgreementConstruction(support_token, start, end)

    def validated(support_token: int) -> Optional[_AgreementConstruction]:
        return complete(support_token) if _agreement_support_is_clause(text, spans, support_token) else None

    nxt, j, support = "", k, k
    while j + 1 < len(spans):
        if re.search(r"[.!?？。…~,，;:]", text[spans[j].end():spans[j + 1].start()]):
            break
        w = spans[j + 1].group(0)
        if w in _LEX_SKIP_NEXT:
            j += 1
            continue
        nxt = w
        support = j + 1
        break
    if "그렇게" in lexeme:
        return validated(support if not tail else k) if (tail or nxt).startswith("생각") else None
    if _LEX_LIGHT_NEXT.fullmatch(tail) or _LEX_NEG_NEXT.fullmatch(tail) or (ga and _LEX_GA.fullmatch(tail)):
        if nominal:
            return None
        return validated(k)
    if tail == "" or _LEX_COPULA_TAIL.match(tail):
        if not nxt or tail:
            return validated(k)
        if nominal:
            return validated(support) if (_LEX_NEG_NEXT.match(nxt) or _LEX_REACTION_NEXT.match(nxt)) else None
        return validated(support) if (_LEX_LIGHT_NEXT.fullmatch(nxt) or _LEX_NEG_NEXT.match(nxt) or (ga and _LEX_GA.match(nxt))) else None
    if tail in _LEX_PARTICLE_TAIL and nxt and not nominal:
        return validated(support) if (_LEX_LIGHT_NEXT.fullmatch(nxt) or _LEX_NEG_NEXT.match(nxt) or (ga and _LEX_GA.match(nxt))) else None
    return None


def _agreement_valid(text: str, lex_start: int, lex_end: int) -> bool:
    """기존 bool 경계: 실제 행위 구성이 있을 때만 참."""
    return _agreement_construction(text, lex_start, lex_end) is not None


@dataclass(frozen=True)
class _AgreementAct:
    """절 안의 동의 행위 하나: 원문 구간, 대상 탐색 시작 위치(앞 행위의 끝), 주체, 극성, 성립 문맥, 동의어 시작, 참·거짓 판단 여부.

    채택(adopt)은 긍정 극성이 실제로 성립했을 때, 거둠(withdraw)은 부정 극성이 실제로 성립했거나 긍정이 대조로 뒤집혔을 때다.
    주체·대상은 최종 적용(_speaker_utterances)에서 따로 확인한다.
    """
    start: int
    end: int
    region: int
    subject: str
    polarity: str
    realization: str
    lex: int = 0
    truth: bool = False
    # B32: 같은 _agreement_act_detail 계산의 시제 근거, 주체 결정 어절, 성립 문맥 출처, 주체 판정 경로.
    temporal_scope: str = _NOT_OBSERVED
    temporal_evidence_span: Tuple[int, int] = (-1, -1)
    subject_evidence_span: Tuple[int, int] = (-1, -1)
    realization_source: str = "own_construction"
    subject_source: str = "clause_subject"

    @property
    def mode(self) -> str:
        if self.realization == "actual":
            return "negated" if self.polarity == "negative" else "actual"
        return self.realization

    @property
    def effect(self) -> str:
        if self.realization == "actual":
            return "withdraw" if self.polarity == "negative" else "adopt"
        if self.realization == "contrast" and self.polarity == "positive":
            return "withdraw"
        return ""


@dataclass(frozen=True)
class _BoundAgreementEvent:
    """한 동의 술어의 원문 범위·주체·극성·성립·대상을 함께 적용하는 내부 사건."""

    start: int
    end: int
    subject: str
    polarity: str
    realization: str
    effect: str
    targets: Tuple[int, ...]
    target_relation: str  # targets_utterance | no_object | ambiguous | unrelated 등
    binding_kind: str
    object_relations: Tuple[_ObjectRelation, ...]
    kind: str = "agree"
    event_id: str = ""
    target_event_ids: Tuple[str, ...] = ()
    source_id: str = ""
    parent_event_id: str = ""
    predicate: str = ""
    predicate_span: Tuple[int, int] = (-1, -1)
    grammatical_subject: Optional[_NativeSubject] = None
    object_tokens: Tuple[_ObjectToken, ...] = ()
    objects: Tuple[_NativeObject, ...] = ()
    # B32: 같은 act 판정의 시제 근거·성립 문맥 출처·주체 결정 어절·주체 판정 경로와 reducer 전 철회 범위 판단.
    temporal_scope: str = _NOT_OBSERVED
    temporal_evidence_span: Tuple[int, int] = (-1, -1)
    realization_source: str = _NOT_OBSERVED
    subject_evidence_span: Tuple[int, int] = (-1, -1)
    subject_source: str = _NOT_OBSERVED
    withdrawal_scope: str = _NOT_OBSERVED
    withdrawal_scope_evidence_span: Tuple[int, int] = (-1, -1)


def _agreement_acts(text: str, works: Sequence[str] = ()) -> List[_AgreementAct]:
    """절의 동의 행위(동의어·참거짓 판단)를 순서대로. 앞 행위의 동사 구성 안에 든 것, 작품 표면 안의 동의어('약관동의'), 서술어·짧은 응답을
    이루지 못한 동의어(_agreement_valid: '동의 버튼', '동의어', '공감 수')는 행위가 아니다. 명사 서술어형 동의('맞는 말이다')는 참·거짓 판단처럼
    주어·주제 조사가 붙은 발언 명사를 대상 머리로 쓴다.
    """
    inside = [(a, b) for _, a, b in _work_spans(text, works)]
    cands = [(m.start(), 0, m.end(), bool(_LEX_NOMINAL.match(re.sub(r"\s+", " ", m.group(0)))), False, construction)
             for m in _AGREE.finditer(text)
             if not any(a <= m.start() < b for a, b in inside)
             if (construction := _agreement_construction(text, m.start(), m.end())) is not None]
    cands += [(s, 1, e, True, neg, None) for s, e, neg in _truth_acts(text)]
    acts: List[_AgreementAct] = []
    region, last_end = 0, -1
    for s, _, e, truth, false_word, construction in sorted(cands, key=lambda item: (item[0], item[1])):
        if s < last_end:
            continue
        mode = _agreement_act_detail(text, s, e, region, false_word, ga=text[s:e] == "공감", construction=construction)
        start, end, polarity, realization = mode.start, mode.end, mode.polarity, mode.realization
        subject, subject_span = _clause_subject_detail(text, start, works, bare_check=True)
        acts.append(_AgreementAct(start, end, region, subject, polarity, realization, s, truth,
                                  mode.temporal_scope, mode.temporal_evidence_span, subject_span))
        region, last_end = end, max(end, e)
    return acts


def _unknown_speech_owner(phrase: Sequence[str], speakers: Set[str], works: Sequence[str]) -> bool:
    """발언 명사 머리 바로 앞 명사구의 소유자가 앞선 전언의 발화자가 아닌 인물인가('동생 말에', '동생의 평가에', '동생이 한 말에').

    머리 앞에서 거꾸로 소유격·조사 없는 명사·공동격 어절과 관형절 주어만 본다. 발화자·작품·평가 항목·발언 명사·지시어면 통과하고,
    주어·주제 어절, 자기 지칭, 연결 어미에서 명사구가 끝난다. 관형형 수식어('좋은')는 건너뛴다.
    """
    i = len(phrase) - 2
    while i >= 0:
        tk = phrase[i]
        if _ADNOMINAL_VERB.search(tk) and i > 0 and len(phrase[i - 1]) >= 2 and re.search(r"(?:이|가|께서)$", phrase[i - 1]):
            owner = phrase[i - 1]
            o = _stem_of(owner)
            return not (o in speakers or o in _SELF_STEMS or _works_in(owner, works))
        base = _EXCLUDE_SUFFIX.sub("", tk) or tk
        stems = _name_stems(base)
        # 청자 소유격('네 말이', '님 말에')은 앞선 전언의 발화자가 아니다.
        if i == len(phrase) - 2 and tk in _ADDRESSEE:
            return True
        if tk in _SELF_WORDS or (_SEG_CONNECTIVE.search(tk) and not stems & speakers):
            return False
        if (len(tk) < 2 or tk in _EXCLUDE_MARK or tk in _DEICTIC_DET or tk in _OTHER_DET or tk in _OBJ_TRAILING or _is_adverb(tk)
                or tk in {"나머지", "모든", "전체", "각각의", "두", "사람의", "앞의", "직전의", "방금", "지금"}
                or stems & speakers or _works_in(base, works) or _is_work_noun(base) or stems & _DOMAIN_NOUNS or stems & _SPEECH_NOUNS):
            i -= 1
            continue
        stem = _stem_of(tk)
        if _SUBJ_PARTICLE.search(tk) and len(stem) >= 2 and not _complex_coda(stem) and not _VERBAL_STEM_END.search(stem):
            return False
        if _gap_modifier(tk) or _ADNOMINAL_VERB.search(tk):
            i -= 1
            continue
        return bool(re.search(r"(?:의|와|과|랑|이랑|하고)$", tk) or not _TOKEN_PARTICLE.search(tk))
    return False


# 동의어 앞에서 목적어로 보지 않는 정도 표현('어느 정도 동의', '일부 동의').
_DEGREE_WORDS = {"정도", "일부", "부분", "어느", "어느정도", "대부분"}


def _domain_item_pattern(item: str) -> re.Pattern[str]:
    """평가 항목 명사구의 조사·공동격과 머리 경계. 도면 수식은 평가 항목이 아니다."""
    return re.compile(r"(?<![가-힣])" + re.escape(item)
                      + r"(?:(?:에서|에게|까지|만큼|부터|으로|보다|처럼|하고|이랑|랑|은|는|이|가|을|를|에|의|도|만|과|와)(?:은|는|도|만)?)*(?![가-힣])"
                      + r"(?!\s+(?:도면|설계도|도안)(?:은|는|이|가|을|를|의|도|만)?(?:\s|$))")


def _bare_object(tk: str) -> bool:
    """조사 없는 목적어 명사인가. 부사형('격하게', '백번'), 서술어·연결형, 지시어('이건', '그거'), 발언 명사('말') 밖의 한 음절 어절은 아니다."""
    return ((len(tk) >= 2 or tk in _SPEECH_NOUNS) and not _TOKEN_PARTICLE.search(tk) and not _ADVERB_FORM.search(tk) and not _PRED_LIKE.search(tk)
            and not _SEG_CONNECTIVE.search(tk) and tk not in _GENERIC_DEICTIC and tk not in _NONPERSON_TOPIC and not _is_adverb(tk)
            and tk not in _CLAUSE_LEAD and not _complex_coda(tk))


def _object_gap_adverb(tk: str) -> bool:
    """목적어·표시 내용과 술어 사이의 부사형 어절인가."""
    return bool(_is_adverb(tk) or tk in _OBJ_TRAILING or tk in _ACT_ADVERBS
                or re.search(r"(?:히|게|로|으로)$", tk)
                or re.fullmatch(r"(?:오늘|어제|내일|지금|방금|그때|다시)(?:도|는)?", tk))


@dataclass(frozen=True)
class _ObjectToken:
    start: int
    end: int
    text: str
    quoted: bool = False


@dataclass(frozen=True)
class _ObjectRelation:
    kind: str  # speaker | work | item
    values: frozenset[str]
    members: Tuple[Tuple[int, int], ...]
    relation: str  # selects | excludes
    marker: Tuple[int, int]
    phrase_span: Tuple[int, int] = (-1, -1)  # 조사와 발언 명사 머리를 포함한 명사구
    speaker_work_pairs: Tuple[Tuple[str, str], ...] = ()
    speaker_item_pairs: Tuple[Tuple[str, str], ...] = ()
    speaker_work_item_triples: Tuple[Tuple[str, str, str], ...] = ()
    # 각 평가 명사구의 부분 제약. 빈 작품/항목은 그 명사구에 명시되지 않았다는 뜻이다.
    speaker_constraints: Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...] = ()
    # 소유자마다의 모든 평가 명사구(형제 포함)가 화자·작품·항목 한 결합으로 완결되었는가.
    scoped_triples_complete: bool = False


def _agreement_object_spans(prefix: str, base_offset: int = 0) -> List[_ObjectToken]:
    """인용 안 이름과 인용 밖 조사를 같은 원문 좌표의 토큰으로 보존한다."""
    tokens: List[_ObjectToken] = []
    offset = 0
    for match in _QUOTE_SPAN.finditer(prefix):
        tokens.extend(_ObjectToken(base_offset + offset + m.start(), base_offset + offset + m.end(), m.group(0))
                      for m in re.finditer(r"[가-힣A-Za-z0-9]+", prefix[offset:match.start()]))
        tokens.append(_ObjectToken(base_offset + match.start(), base_offset + match.end(), next(g for g in match.groups() if g).strip(), True))
        offset = match.end()
    tokens.extend(_ObjectToken(base_offset + offset + m.start(), base_offset + offset + m.end(), m.group(0))
                  for m in re.finditer(r"[가-힣A-Za-z0-9]+", prefix[offset:]))
    return tokens


def _agreement_object_tokens(prefix: str) -> List[str]:
    """기존 텍스트 호출 경계. 내부 선택·제외는 원문 위치 기록을 사용한다."""
    return [token.text for token in _agreement_object_spans(prefix)]


def _trailing_speech_object(tokens: Sequence[_ObjectToken]) -> Optional[_ObjectToken]:
    """원문 좌표를 유지하며 부사어 앞의 마지막 명시 발언 목적어를 찾는다."""
    for token in reversed(tokens):
        if _name_stems(token.text) & _SPEECH_NOUNS and _OBJ_HEAD_TAIL.search(token.text):
            return token
        if not _object_gap_adverb(token.text):
            break
    return None


def _object_joint(phrase: Sequence[str], left: int, right: int, works: Sequence[str] = ()) -> bool:
    """두 개체 사이의 인용 밖 공동격·접속을 원래 명사구 관계로 읽는다."""
    between = phrase[left + 1:right]
    content = between[1:] if between and between[0] == "의" else between if phrase[left].endswith("의") else []
    scoped_coordination = bool(content and (
        (_name_stems(content[-1]) & _SPEECH_NOUNS and _COORD_TAIL.search(content[-1]))
        or (len(content) >= 2 and content[-1] == "및" and _name_stems(content[-2]) & _SPEECH_NOUNS))
        and all(_gap_modifier(word) or _name_stems(word) & (_DOMAIN_NOUNS | _SPEECH_NOUNS)
                or _works_in(word, works, strict_tail=True) for word in content[:-1]))
    relative_head = _object_phrase_head(phrase, left, works)
    relative_coordination = (relative_head > left and relative_head == right - 1
                             and _name_stems(phrase[relative_head]) & _SPEECH_NOUNS
                             and _COORD_TAIL.search(phrase[relative_head]))
    return bool(relative_coordination or (not between and _COORD_TAIL.search(phrase[left]))
                or (len(between) == 1 and (between[0] == "및" or _COORD_TAIL.fullmatch(between[0])))
                or scoped_coordination)


# 전칭 관형사 뒤의 일반 작품 명사('모든 작품의')는 특정 작품 제약이 아니라 작품 차원 전체를 가리키는 수량 표현이다.
_UNIVERSAL_DET = {"모든", "전체", "각", "각각의"}


def _universal_work_noun(phrase: Sequence[str], j: int) -> bool:
    """phrase[j]가 전칭 관형사 바로 뒤의 일반 작품 명사('모든 작품의')인가."""
    return j > 0 and phrase[j - 1] in _UNIVERSAL_DET and _stem_of(phrase[j]) in _WORK_GENERIC


def _works_between(phrase: Sequence[str], lo: int, hi: int, works: Sequence[str]) -> Set[str]:
    return set().union(*(_works_in(phrase[k], works, strict_tail=True) for k in range(lo, hi + 1)))


def _items_between(phrase: Sequence[str], lo: int, hi: int) -> Set[str]:
    return {item for item in _DOMAIN_NOUNS if _domain_item_pattern(item).search(" ".join(phrase[lo:hi + 1]))}


def _object_phrase_head(phrase: Sequence[str], pos: int, works: Sequence[str] = ()) -> int:
    """개체에서 소유격·평가 항목·발언 명사·격조사까지 잇는 명사구 끝. '모든 작품의'는 명사구 안의 전칭 작품 범위다."""
    # 관형절 subject와 평가 머리는 사이의 작품·항목·관형 술어를 포함한 한 NP다.
    if re.search(r"(?:이|가|께서)$", phrase[pos]):
        relative = False
        for k in range(pos + 1, len(phrase)):
            word = phrase[k]
            if _name_stems(word) & _SPEECH_NOUNS and relative:
                return k + 1 if k + 1 < len(phrase) and phrase[k + 1] in {"에", "에는", "에만", "을", "를"} else k
            if word in _SELF_SUBJECT or (k > pos + 1 and _SUBJ_PARTICLE.search(word)
                    and not (_name_stems(word) & _DOMAIN_NOUNS or _works_in(word, works))):
                break
            if _ADNOMINAL_VERB.search(word):
                relative = True
            elif _SEG_CONNECTIVE.search(word) and word not in {"대한", "관한"} and not _COORD_TAIL.search(word):
                break
    j = pos + 1
    if ((j < len(phrase) and phrase[j] == "의") or phrase[pos].endswith("의")
            or phrase[j:j + 2] == ["두", "사람의"]):
        if j < len(phrase) and phrase[j] == "의":
            j += 1
        while j < len(phrase) and (_gap_modifier(phrase[j]) or phrase[j] in {"나머지", "모든", "전체", "각각의", "두", "사람의", "대한", "관한"}
                                   or _name_stems(phrase[j]) & _DOMAIN_NOUNS
                                   or _works_in(phrase[j], works, strict_tail=True)
                                   or _universal_work_noun(phrase, j)):
            j += 1
        if j < len(phrase) and _name_stems(phrase[j]) & _SPEECH_NOUNS:
            j += 1
            if j < len(phrase) and phrase[j] in {"에", "에는", "에만", "을", "를", "은", "는"}:
                j += 1
    elif j < len(phrase) and phrase[j] in {"가", "이", "는", "은", "을", "를"}:
        j += 1
    return j - 1


def _coordinated_evaluation_heads(phrase: Sequence[str], head: int, works: Sequence[str],
                                  speakers: Set[str]) -> List[Tuple[int, int]]:
    """소유자 평가 명사구 머리 뒤에 공동격으로 이어진 형제 평가 명사구의 (시작, 머리) 목록.

    머리가 발언 명사이고 공동격(와·과·랑·이랑·하고)으로 끝나거나 뒤에 '및'이 올 때, 다음 명사구가 자기 소유자 없이 작품·항목·
    관형어와 발언 명사 머리로 끝나면 같은 부모 소유자의 형제다('민지의 결말 평가와 전개 평가'). 다음 명사구에 화자가 있으면
    독립 평가이므로 멈춘다('민지의 A 평가와 민수의 B 평가'). 작품·항목이 없는 발언 명사만의 형제는 받지 않는다.
    """
    out: List[Tuple[int, int]] = []
    while 0 <= head < len(phrase) and _name_stems(phrase[head]) & _SPEECH_NOUNS:
        k = head + 1
        if k < len(phrase) and phrase[k] == "및":
            k += 1
        elif not _COORD_TAIL.search(phrase[head]):
            break
        start = k
        while k < len(phrase) and not (_name_stems(phrase[k]) & speakers) and (
                _gap_modifier(phrase[k]) or phrase[k] in {"나머지", "모든", "전체", "각각의"}
                or _name_stems(phrase[k]) & _DOMAIN_NOUNS or _works_in(phrase[k], works, strict_tail=True)
                or _universal_work_noun(phrase, k)):
            k += 1
        if k == start or k >= len(phrase) or not (_name_stems(phrase[k]) & _SPEECH_NOUNS):
            break
        if not (_works_between(phrase, start, k, works) or _items_between(phrase, start, k)):
            break
        out.append((start, k))
        head = k
    return out


def _object_exclusion_marker(phrase: Sequence[str], pos: int, works: Sequence[str] = ()) -> Optional[int]:
    """개체 명사구의 격·발언 머리를 지나 적용되는 제외·정정 표지 위치."""
    if _EXCLUDE_SUFFIX.search(phrase[pos]):
        return pos
    j = _object_phrase_head(phrase, pos, works) + 1
    return j if j < len(phrase) and phrase[j] in _EXCLUDE_MARK else None


def _object_excluded(phrase: Sequence[str], pos: int) -> bool:
    return _object_exclusion_marker(phrase, pos) is not None


def _object_relation_ledger(tokens: Sequence[_ObjectToken], speakers: Set[str], works: Sequence[str]) -> List[_ObjectRelation]:
    """공동격으로 묶인 명사구에 선택·제외 범위를 붙인 원문 좌표 기록.

    소유자(화자) 명사구 머리 뒤에 공동격으로 이어진 소유자 없는 평가 명사구('민지의 결말 평가와 전개 평가')는 같은 부모 소유자의
    형제 평가다(_coordinated_evaluation_heads). 형제마다 부분 제약을 따로 둔다. 형제가 항목만 밝히면 앞 명사구의 작품까지, 작품을
    밝히면 소유자만 이어 받는다. 이때 부모 명사구는 마지막 형제 머리까지이고 제외 표지도 그 뒤에서 읽는다.
    """
    phrase = [token.text for token in tokens]
    mentions: dict = {"speaker": [], "work": [], "item": []}
    for i, tk in enumerate(phrase):
        if tk in _EXCLUDE_MARK:
            continue
        base = _EXCLUDE_SUFFIX.sub("", tk) or tk
        stems = _name_stems(base)
        found = {"speaker": {s for s in speakers if s in stems}, "work": _works_in(base, works, strict_tail=True),
                 "item": {st for st in stems if st in _DOMAIN_NOUNS
                          and _domain_item_pattern(st).search(" ".join(phrase[i:i + 2]))}}
        for key, vals in found.items():
            if vals:
                mentions[key].append((i, vals))
    relations: List[_ObjectRelation] = []
    for key, entries in mentions.items():
        groups: List[List[Tuple[int, Set[str]]]] = []
        for entry in entries:
            if groups and _object_joint(phrase, groups[-1][-1][0], entry[0], works):
                groups[-1].append(entry)
            else:
                groups.append([entry])
        for group in groups:
            marker_index = _object_exclusion_marker(phrase, group[-1][0], works)
            head_index = _object_phrase_head(phrase, group[-1][0], works)
            values = frozenset(value for _, vals in group for value in vals)
            pairs = []
            item_pairs = []
            triples = []
            constraints = []
            complete_scopes = key == "speaker"
            if key == "speaker":
                span_end = head_index
                for pos, owners in group:
                    phrase_end = _object_phrase_head(phrase, pos, works)
                    lo, hi = pos + 1, phrase_end
                    # '민지와 민수의 A 결말 평가'의 앞 이름만 뒤 수식어를 공유한다.
                    # 독립된 '민지의 A 평가와 민수의 B 전개 평가'는 부분 제약 그대로 둔다.
                    if phrase_end == pos and pos != group[-1][0]:
                        # 가까운 공유 머리까지만 잇는다. 뒤 독립 평가의 머리로 건너뛰지 않는다.
                        shared_pos = next((p for p, _ in group if p > pos
                                           and _object_phrase_head(phrase, p, works) > p), group[-1][0])
                        shared_end = _object_phrase_head(phrase, shared_pos, works)
                        if not any(_name_stems(phrase[k]) & _SPEECH_NOUNS for k in range(pos + 1, shared_pos)):
                            lo, hi = shared_pos + 1, shared_end
                    first_works = _works_between(phrase, lo, hi, works)
                    first_items = _items_between(phrase, lo, hi)
                    scopes = [(first_works, first_items)]
                    for sibling_lo, sibling_hi in _coordinated_evaluation_heads(phrase, hi, works, speakers):
                        sibling_works = _works_between(phrase, sibling_lo, sibling_hi, works)
                        sibling_items = _items_between(phrase, sibling_lo, sibling_hi)
                        # 형제가 작품을 밝히면 소유자만, 항목만 밝히면 소유자와 앞 명사구의 작품까지 공유한다.
                        scopes.append((sibling_works, sibling_items) if sibling_works else (first_works, sibling_items))
                        span_end = max(span_end, sibling_hi)
                    for named_works, named_items in scopes:
                        constraints.extend((owner, tuple(sorted(named_works)), tuple(sorted(named_items)))
                                           for owner in sorted(owners))
                        if len(owners) == len(named_works) == 1:
                            pairs.append((next(iter(owners)), next(iter(named_works))))
                        if len(owners) == len(named_items) == 1:
                            item_pairs.append((next(iter(owners)), next(iter(named_items))))
                        if len(owners) == len(named_works) == len(named_items) == 1:
                            triples.append((next(iter(owners)), next(iter(named_works)), next(iter(named_items))))
                        else:
                            complete_scopes = False
                if span_end > head_index:
                    # 형제 평가까지 한 부모 명사구다. 제외·정정 표지는 마지막 형제 머리 뒤에서 읽는다.
                    head_index = span_end
                    after = head_index + 1
                    marker_index = (group[-1][0] if _EXCLUDE_SUFFIX.search(phrase[group[-1][0]])
                                    else after if after < len(phrase) and phrase[after] in _EXCLUDE_MARK else None)
            marker = ((tokens[marker_index].start, tokens[marker_index].end) if marker_index is not None else (-1, -1))
            relations.append(_ObjectRelation(key, values, tuple((tokens[pos].start, tokens[pos].end) for pos, _ in group),
                                             "excludes" if marker_index is not None else "selects", marker,
                                             (tokens[group[0][0]].start, tokens[head_index].end), tuple(pairs),
                                             tuple(item_pairs), tuple(triples), tuple(constraints), complete_scopes))
    # 평가 명사구 안의 작품·항목은 부모의 선택/제외를 상속한다. 토큰만
    # 따로 세어 제외된 평가의 작품·항목을 새 선택으로 되살리지 않는다.
    parents = [relation for relation in relations if relation.kind == "speaker"]
    nested = []
    for relation in relations:
        parent = next((p for p in parents if relation.kind != "speaker"
                       and p.phrase_span[0] <= relation.members[0][0]
                       and relation.members[-1][1] <= p.phrase_span[1]), None)
        # 자식에 비교·제외 표지가 직접 붙었으면 부모 평가의 선택보다 우선한다.
        nested.append(replace(relation, relation=parent.relation)
                      if parent and relation.marker == (-1, -1) else relation)
    return nested


def _agreement_targets(text: str, prior: Sequence[int], utts: Sequence[_Utterance], works: Sequence[str] = (),
                        at: Optional[int] = None, truth: bool = False,
                        object_tokens: Optional[Sequence[_ObjectToken]] = None,
                        relations: Optional[Sequence[_ObjectRelation]] = None) -> Tuple[List[int], str]:
    """동의·반박 절이 가리키는 앞선 인용·전언 발화 번호와 연결 방식.

    동의어 앞 목적어 구 전체를 본다. 머리(동의어 바로 앞 여격·공동격 어절)가 발언 명사('평가에만')면 수식어의 발화자·작품·평가 항목을,
    발화자 자체('친구에게')면 그 발화자를 제약으로 삼고, 그 밖의 명사('친구의 배송 일정에')면 발화자 이름이 있어도 무관한 동의다.
    수식어 뒤에 제외 표지('말고', '빼고', '대신', '아니라')가 오면 그 개체는 제외 제약이다. 후보 발화는 포함 제약을 모두 만족하고 제외 제약에
    걸리지 않아야 하며, 포함 작품 밖의 작품도 함께 평가한 발화는 가를 수 없어 빠진다. 작품은 완전한 표면 경계로만 비교하고('달빛기사전'
    ≠ '달빛기사'), 인물 이름은 전체 이름으로 비교한다. 같은 발화자의 발화가 여럿 남으면 포함 작품 제약이나 전칭('모두')이 있을 때만 모두
    잇는다. 명시 목적어가 없거나 제약이 없으면 앞선 인용·전언이 하나일 때만 연결한다. at은 동의어(판단어) 시작 위치이고,
    truth면 참·거짓 판단이라 머리는 주어·주제 조사가 붙은 발언 명사('평가는', '말이')다.
    """
    if at is None:
        m = _AGREE.search(text)
        at = m.start() if m else None
    object_tokens = list(object_tokens) if object_tokens is not None else (_agreement_object_spans(text[:at]) if at is not None else [])
    speakers = {utts[i].speaker for i in prior if utts[i].speaker not in ("other", "self")}
    relations = list(relations) if relations is not None else _object_relation_ledger(object_tokens, speakers, works)
    while object_tokens and object_tokens[0].text in _SELF_WORDS:
        object_tokens = object_tokens[1:]
    while object_tokens and (object_tokens[-1].text in _OBJ_TRAILING or _is_adverb(object_tokens[-1].text)
                             or object_tokens[-1].text in _SELF_WORDS or object_tokens[-1].text in _TRUTH_SKIP
                             or object_tokens[-1].text in _I_ADVERB or object_tokens[-1].text in _ACT_ADVERBS
                             or object_tokens[-1].text in _LEX_SKIP_NEXT or object_tokens[-1].text in _DEGREE_WORDS
                             or (len(object_tokens[-1].text) >= 3 and object_tokens[-1].text not in _EXCLUDE_MARK
                                 and _SEG_CONNECTIVE.search(object_tokens[-1].text))):
        object_tokens = object_tokens[:-1]
    toks = [token.text for token in object_tokens]
    head = toks[-1] if toks and (_OBJ_HEAD_TAIL.search(toks[-1])
                               or (toks[-1].endswith("도") and _name_stems(toks[-1]) & _SPEECH_NOUNS) or (truth and re.search(r"(?:은|는|이|가|도)$", toks[-1]))) else None
    # 조사 없이 동의어 바로 앞에 온 명사('약관 동의', '친구 말 동의')도 명시 목적어다. 부사·지시어·서술어형 어절은 목적어가 아니다.
    if head is None and toks and _bare_object(toks[-1]):
        head = toks[-1]
    # 표시 관계와 같은 원문 목적어·부사 범위를 사용한다. 선택 원장이 있으면 그 명사구 끝과도 대조한다.
    if head is None:
        speech = _trailing_speech_object(object_tokens)
        selected_ends = {r.phrase_span[1] for r in relations if r.relation == "selects"}
        if speech and (not selected_ends or speech.end in selected_ends):
            head = speech.text
    if head is None:
        return (list(prior), "no_object") if len(prior) == 1 else ([], "ambiguous" if prior else "none")
    phrase = toks
    head_stems = _name_stems(head)
    # 수량 head는 같은 선행 평가 NP에 결속한다. 평가 없는 '두 개에'는 그대로 unrelated다.
    counted_speech = (bool(head_stems & {"개", "건"})
                      and len(toks) >= 3 and bool(re.fullmatch(r"두|세|네|한|[0-9]+", toks[-2]))
                      and bool(_name_stems(toks[-3]) & _SPEECH_NOUNS))
    if counted_speech:
        head_stems |= _SPEECH_NOUNS
    inc: dict = {"speaker": set(), "work": set(), "item": set()}
    exc: dict = {"speaker": set(), "work": set(), "item": set()}
    inc_at: dict = {"speaker": [], "work": [], "item": []}
    selected_pairs: Set[Tuple[str, str]] = set()
    excluded_pairs: Set[Tuple[str, str]] = set()
    selected_item_pairs: Set[Tuple[str, str]] = set()
    excluded_item_pairs: Set[Tuple[str, str]] = set()
    selected_triples: Set[Tuple[str, str, str]] = set()
    excluded_triples: Set[Tuple[str, str, str]] = set()
    selected_constraints = [c for relation in relations if relation.relation == "selects"
                            for c in relation.speaker_constraints]
    excluded_constraints = [c for relation in relations if relation.relation == "excludes"
                            for c in relation.speaker_constraints]
    parents = [relation for relation in relations if relation.kind == "speaker"]
    scoped_excluded_works = {work for relation in relations if relation.relation == "excludes"
                             for _, work in relation.speaker_work_pairs}
    scoped_excluded_items = {item for relation in relations if relation.relation == "excludes"
                             for _, item in relation.speaker_item_pairs}
    for relation in relations:
        parent = next((p for p in parents if relation.kind != "speaker"
                       and p.phrase_span[0] <= relation.members[0][0]
                       and relation.members[-1][1] <= p.phrase_span[1]), None)
        # 부모 평가 명사구에 결속한 자식 작품·항목은 독립 집합으로 다시 넓히지 않는다.
        if parent and ((relation.kind == "work" and parent.speaker_work_pairs)
                       or (relation.kind == "item" and parent.speaker_item_pairs)):
            continue
        bucket = exc if relation.relation == "excludes" else inc
        # 소유자+작품/평가항목 한 쌍의 제외는 그 쌍에만 적용한다.
        scoped_speakers = ({speaker for speaker, _ in relation.speaker_work_pairs}
                           | {speaker for speaker, _ in relation.speaker_item_pairs})
        scoped_exclusion = (relation.relation == "excludes" and
                            ((relation.kind == "speaker" and scoped_speakers == relation.values)
                             or (relation.kind == "work" and relation.values <= scoped_excluded_works)
                             or (relation.kind == "item" and relation.values <= scoped_excluded_items)))
        if not scoped_exclusion:
            bucket[relation.kind] |= relation.values
        complete_triples = relation.kind == "speaker" and (len(relation.speaker_work_item_triples) == len(relation.members)
                                                           or relation.scoped_triples_complete)
        if complete_triples:
            (excluded_triples if relation.relation == "excludes" else selected_triples).update(
                relation.speaker_work_item_triples)
        else:
            (excluded_pairs if relation.relation == "excludes" else selected_pairs).update(relation.speaker_work_pairs)
            (excluded_item_pairs if relation.relation == "excludes" else selected_item_pairs).update(relation.speaker_item_pairs)
        if relation.relation == "selects":
            inc_at[relation.kind].extend(next(i for i, token in enumerate(object_tokens) if token.start == start and token.end == end)
                                         for start, end in relation.members)
    # 같은 종류의 포함 개체가 여럿이면 앞 개체들이 공동격('와·과·랑·하고')이나 '및'으로 이어져 있어야 함께 고른 것이다.
    # 이어짐이 없으면('A는 논외로 하고 B 평가에만') 선택·제외 관계를 확정할 수 없어 연결하지 않는다.
    for key, positions in inc_at.items():
        if len(inc[key]) > 1:
            # 두 평가 명사구가 각각 화자와 작품을 짝지으면 작품명끼리 직접 인접할 필요는 없다.
            if (key == "work" and selected_constraints and all(len(ws) == 1 for _, ws, _ in selected_constraints)
                    and {work for _, ws, _ in selected_constraints for work in ws} == inc["work"]):
                continue
            for left, right in zip(positions, positions[1:]):
                # 따옴표 뒤의 조사는 별도 토큰이다: '"민지"와 "민수"의 평가'.
                if not _object_joint(phrase, left, right, works):
                    return [], "ambiguous_" + key
    if head_stems & _SPEECH_NOUNS:
        kind = "speech"
    elif head_stems & speakers:
        kind = "speaker"
    elif _works_in(head, works, strict_tail=True):
        kind = "work"
    else:
        return [], "unrelated"
    if kind == "speech" and _unknown_speech_owner(phrase, speakers, works):
        return [], "unknown_speaker"
    # 소유자+대상을 제외하고 다른 대상만 명시했으면 그 소유자와 같은 발화 안에서만
    # 후속 선택을 찾는다. 다른 사람의 같은 작품으로 화자를 바꿔 추론하지 않는다.
    scoped_owner = ({speaker for speaker, _ in excluded_pairs}
                    | {speaker for speaker, _ in excluded_item_pairs}
                    | {speaker for speaker, _, _ in excluded_triples}) if not inc["speaker"] else set()
    if not any(inc.values()) and not any(exc.values()):
        return (list(prior), kind) if len(prior) == 1 else ([], "ambiguous" if prior else "none")

    def fits(i: int) -> bool:
        u = utts[i]
        uw = _works_in(u.text, works, strict_tail=True)
        def matches_constraint(constraint: Tuple[str, Tuple[str, ...], Tuple[str, ...]]) -> bool:
            speaker, named_works, named_items = constraint
            return (u.speaker == speaker
                    and (not named_works or (bool(uw & set(named_works)) and not (uw - set(named_works))))
                    and (not named_items or any(_domain_item_pattern(item).search(u.text) for item in named_items)))
        if selected_constraints and not any(matches_constraint(c) for c in selected_constraints):
            return False
        if any(matches_constraint(c) for c in excluded_constraints):
            return False
        if scoped_owner and u.speaker not in scoped_owner:
            return False
        if not selected_constraints and selected_triples and not any(speaker == u.speaker and work in uw and _domain_item_pattern(item).search(u.text)
                                        for speaker, work, item in selected_triples):
            return False
        if any(speaker == u.speaker and work in uw and _domain_item_pattern(item).search(u.text)
               for speaker, work, item in excluded_triples):
            return False
        if not selected_constraints and selected_pairs and {speaker for speaker, _ in selected_pairs} == inc["speaker"] and not any(
                (u.speaker, work) in selected_pairs for work in uw):
            return False
        if any((u.speaker, work) in excluded_pairs for work in uw):
            return False
        if (not selected_constraints and selected_item_pairs and {speaker for speaker, _ in selected_item_pairs} == inc["speaker"]
                and not any(speaker == u.speaker and _domain_item_pattern(item).search(u.text) for speaker, item in selected_item_pairs)):
            return False
        if any(speaker == u.speaker and _domain_item_pattern(item).search(u.text) for speaker, item in excluded_item_pairs):
            return False
        if inc["speaker"] and u.speaker not in inc["speaker"]:
            return False
        if u.speaker in exc["speaker"]:
            return False
        if inc["work"] and (not (uw & inc["work"]) or (uw - inc["work"])):
            return False
        if uw & exc["work"]:
            return False
        if inc["item"] and not any(_domain_item_pattern(d).search(u.text) for d in inc["item"]):
            return False
        if any(_domain_item_pattern(d).search(u.text) for d in exc["item"]):
            return False
        return True

    cands = [i for i in prior if fits(i)]
    if not cands:
        return [], "no_match"
    # 같은 발화자의 발화가 여럿 남으면 포함 작품 제약('달빛기사 평가')이나 전칭('모두')이 있을 때만 모두 잇는다.
    if not inc["work"] and not any(c[1] for c in selected_constraints) and not _UNIVERSAL.search(text):
        counts: dict = {}
        for i in cands:
            counts[utts[i].speaker] = counts.get(utts[i].speaker, 0) + 1
        if any(n > 1 for n in counts.values()):
            return [], "ambiguous_speaker"
    return cands, kind


def _bind_agreement_events(acts: Sequence[_AgreementAct], target_text: str, prior: Sequence[int],
                           utts: Sequence[_Utterance], works: Sequence[str]) -> List[_BoundAgreementEvent]:
    """한 행위의 주체·양태와 원문 명사구 관계·대상 발화를 같은 사건에 결속한다."""
    speakers = {utts[i].speaker for i in prior if utts[i].speaker not in ("other", "self")}
    events: List[_BoundAgreementEvent] = []
    for act in acts:
        tokens = _agreement_object_spans(target_text[act.region:act.lex], act.region)
        relations = tuple(_object_relation_ledger(tokens, speakers, works))
        targets, how = _agreement_targets(target_text[act.region:], prior, utts, works, act.lex - act.region, act.truth,
                                          tokens, relations)
        events.append(_BoundAgreementEvent(act.start, act.end, act.subject, act.polarity, act.realization, act.effect,
                                           tuple(targets), "targets_utterance" if targets else how, how, relations))
    return events


@dataclass(frozen=True)
class _MarkedSpan:
    """표시 구간의 원문 위치와 바깥 절에서 맡는 역할."""

    start: int
    end: int
    kind: str  # quote | bracket
    role: str  # reported_utterance | nominal_argument | display_label | connected_action | recorded_content
    case_role: str = ""  # subject | object | none
    relation: str = ""  # label_of | next_event | nominal_argument | reported_utterance
    target_start: int = -1
    target_end: int = -1
    event_start: int = -1
    event_end: int = -1


def _quote_span_role(text: str, match: re.Match[str], works: Sequence[str], speakers: Set[str]) -> str:
    """인용 내용의 끝 음절보다 인용 바깥의 발화·격 관계를 먼저 읽는다."""
    body = next(g for g in match.groups() if g).strip()
    after = text[match.end():]
    if re.match(r"^\s*(?:이?라고|다고|고)(?=\s|[가-힣]|$)", after):
        return "reported_utterance"
    if re.match(r"^\s*(?:이?라는)\s+", after) and _AGREE.search(body):
        return "display_label"
    if re.match(r"^\s*(?:는|은|이|가)\s+\S+\s+(?:말|평가|의견|얘기|주장)(?:이다|였다|임|이었)", after):
        return "reported_utterance"
    if re.match(r"^\s*(?:의|에게|한테|께|에|을|를|와|과|은|는|이|가|도|보다|말고|대신)", after):
        return "nominal_argument"
    if body in works or body in speakers:
        return "nominal_argument"
    return "reported_utterance" if _SENTENCE_END.search(body) else "nominal_argument"


_DISPLAY_HEADS = {"버튼", "스위치", "문구", "메뉴", "항목", "옵션", "라벨", "표시", "글씨", "텍스트", "안내", "배너"}
_CONTENT_EVENT_HEADS = {"생각", "반박문", "주장", "댓글", "의견", "입장", "판단", "평가", "독서"}
_REPRESENTATION_EVENT = re.compile(r"^(?:추가|제작|만들|수정|편집|고치|고쳤|바꾸|바꿨|지우|지웠|삭제|붙이|붙였|달아|달았|교체|등록|입력|인쇄|표시|적어|적었|써|썼)")
_USE_EVENT = re.compile(r"^(?:누르|눌|닫|열|클릭|선택|사용|유지|이어|읽)")
_EXPLICIT_DISPLAY_CONTENT = re.compile(
    r"^\s*(?:(?:이?라는)\s+(?:(?:글자|문구)(?:가|로|를|을)\s+(?:[가-힣]+\s+){0,3}"
    r"(?:적힌|쓰인|표시된|적은|쓴|표시한|적히지\s+않은|쓰이지\s+않은|표시되지\s+않은)\s+|이름의\s+)"
    r"|(?:이?라고)\s+(?:[가-힣]+\s+){0,3}(?:적힌|쓰인|표시된|적은|쓴|표시한)\s+)"
)


def _display_object_head(token: str) -> bool:
    """표시 문구를 담는 명사구 머리인가. 뒤 편집 동사의 어형은 역할 근거로 쓰지 않는다."""
    head = re.sub(r"(?:의|을|를|이|가|은|는|도|만)$", "", token)
    return head in _DISPLAY_HEADS


def _bracket_relation(text: str, match: re.Match[str]) -> _MarkedSpan:
    """표시 내용과 다음 명사구·절 사건을 원문 좌표로 잇는다."""
    if not _AGREE.search(match.group(1)):
        return _MarkedSpan(match.start(), match.end(), "bracket", "nominal_argument", relation="nominal_argument")
    boundary = re.search(r"[.!?。;\n]", text[match.end():])
    clause_end = match.end() + boundary.start() if boundary else len(text)
    after = list(_ACT_TOKEN.finditer(text, match.end(), clause_end))
    if not after:
        return _MarkedSpan(match.start(), match.end(), "bracket", "connected_action", relation="next_event")
    # 인용 내용을 담는 명사구 관계는 표시 술어의 부정·미래·부재와 독립이다.
    # [동의하고]라고 적히지 않은 스위치도 같은 label_of이지 실제 동의가 아니다.
    content_marker = re.match(r"^\s*이?(?:라는|라고)\b", text[match.end():clause_end])
    display_target = next((m for m in after if _display_object_head(m.group(0))), None) if content_marker else None
    if display_target:
        event = next((m for m in after if m.start() > display_target.start()
                      and (_REPRESENTATION_EVENT.match(m.group(0)) or _USE_EVENT.match(m.group(0)))), None)
        return _MarkedSpan(match.start(), match.end(), "bracket", "display_label", relation="label_of",
                           target_start=display_target.start(), target_end=display_target.end(),
                           event_start=event.start() if event else -1, event_end=event.end() if event else -1)
    display_frame = _EXPLICIT_DISPLAY_CONTENT.match(text[match.end():clause_end])
    if display_frame:
        target = next((m for m in after if m.start() >= match.end() + display_frame.end()), None)
        event = next((m for m in after if target and m.start() > target.start()
                      and (_REPRESENTATION_EVENT.match(m.group(0)) or _USE_EVENT.match(m.group(0)))), None)
        return _MarkedSpan(match.start(), match.end(), "bracket", "display_label", relation="label_of",
                           target_start=target.start() if target else -1, target_end=target.end() if target else -1,
                           event_start=event.start() if event else -1, event_end=event.end() if event else -1)
    j = 0
    while j < len(after) - 1 and j < 3:
        word = after[j].group(0)
        if word in _SELF_WORDS:
            return _MarkedSpan(match.start(), match.end(), "bracket", "connected_action", relation="next_event")
        if _SUBJ_PARTICLE.search(word) and _PRED_LIKE.search(after[j + 1].group(0)):
            return _MarkedSpan(match.start(), match.end(), "bracket", "connected_action", relation="next_event",
                               event_start=after[j + 1].start(), event_end=after[j + 1].end())
        if not _gap_modifier(word):
            break
        j += 1
    head_match = after[j]
    head = head_match.group(0)
    stem = re.sub(r"(?:의|을|를)$", "", head)
    event = next((m for m in after[j + 1:] if _REPRESENTATION_EVENT.match(m.group(0)) or _USE_EVENT.match(m.group(0))), None)
    event_kind = ("representation_edit" if event and _REPRESENTATION_EVENT.match(event.group(0))
                  else "object_use" if event else "unknown")
    case = bool(re.search(r"(?:의|을|를)$", head))
    deictic = any(m.group(0) in _DEICTIC_DET for m in after[:j])
    speech_target = _trailing_speech_object(_agreement_object_spans(text[:match.start()]))
    explicit_speech_target = speech_target is not None
    label = (case and not deictic and stem not in _CONTENT_EVENT_HEADS
             and ((event_kind == "representation_edit" and
                   (not explicit_speech_target or _display_object_head(head)))
                  or (head.endswith("의") and _display_object_head(head))))
    return _MarkedSpan(match.start(), match.end(), "bracket", "display_label" if label else "connected_action",
                       relation="label_of" if label else "next_event", target_start=head_match.start(), target_end=head_match.end(),
                       event_start=event.start() if event else -1, event_end=event.end() if event else -1)


def _bracket_span_role(text: str, match: re.Match[str]) -> str:
    """기존 역할 호출 경계. 원문 관계는 _bracket_relation이 보존한다."""
    return _bracket_relation(text, match).role


# 기록 내용: 인용·대괄호 내용이 기록 술어의 내용 논항이면('[…]라는 문장만 필사했다', '"…"라고 적었다') 누구의 현재 평가·동의도 아니다.
_RECORD_CONTENT_NOUNS = {"문장", "문구", "글", "글자", "말", "구절", "대사", "표현", "내용", "메모", "한줄", "줄"}
_RECORD_EVENT = re.compile(r"^(?:필사|베껴|베꼈|옮겨|옮겼|받아|적었|적어|적고|적는다|썼|써|쓴다|쓰고|기록|메모|필기)")
_RECORD_ADNOMINAL = re.compile(r"(?:힌|인|은|는|던|을)$")


def _record_content(text: str, match: re.Match[str]) -> bool:
    """인용·대괄호 구간이 기록 술어의 내용 논항인가.

    '(이)라는' 뒤 내용 명사(문장·문구·글·말 …)가 기록 술어의 목적어이거나 '(이)라고' 뒤에 기록 술어가 오면 기록 내용이다. 기록
    술어가 관형형으로 뒤 표시물을 꾸미면('[…]라는 문구가 적힌 버튼') 표시 라벨 관계이므로 기록 내용으로 보지 않는다.
    """
    boundary = re.search(r"[.!?。;\n]", text[match.end():])
    clause = text[match.end():match.end() + boundary.start()] if boundary else text[match.end():]
    words = _ACT_TOKEN.findall(clause)
    if not words:
        return False
    if words[0] in ("라는", "이라는") and len(words) >= 2:
        if re.sub(r"(?:만|을|를|도|은|는|이|가)$", "", words[1]) not in _RECORD_CONTENT_NOUNS:
            return False
        following = words[2:5]
    elif words[0] in ("라고", "이라고"):
        following = words[1:4]
    else:
        return False
    for word in following:
        if _RECORD_EVENT.match(word):
            return not _RECORD_ADNOMINAL.search(word)
    return False


def _marked_spans(text: str, works: Sequence[str], speakers: Set[str]) -> List[_MarkedSpan]:
    marked = [_MarkedSpan(m.start(), m.end(), "quote",
                          "recorded_content" if _record_content(text, m) else _quote_span_role(text, m, works, speakers),
                          "subject" if re.match(r"^\s*(?:은|는|이|가)(?=\s|[가-힣]|$)", text[m.end():]) else "object")
              for m in _QUOTE_SPAN.finditer(text)]
    marked += [_MarkedSpan(m.start(), m.end(), "bracket", "recorded_content", relation="recorded_content")
               if _record_content(text, m) else _bracket_relation(text, m) for m in _BRACKET_SPAN.finditer(text)]
    return sorted(marked, key=lambda span: (span.start, span.end))


# 같은 줄 인용 틀 뒤의 화자 본인 절. 인용 틀 술어('라고 했는데')까지가 전언이다.
_FRAME_PREDICATE = re.compile(r"(?:이?라고|고)\s*(?:했|말했|하더|하던|그러|말하)")
_FRAME_CONTINUATION_END = re.compile(r"(?:는데|은데|지만|으나|고|며|으며|니까|어서|아서|해서|더니)$")
_BACK_REFERENCE = re.compile(r"(?:그|이|저|그런|이런)\s*(?:말|평가|얘기|이야기|주장|의견)")


def _frame_continuation(text: str, quotes: Sequence[re.Match[str]]) -> str:
    """인용 틀 절 뒤에 연결 어미로 이어진 화자 본인의 절. 없으면 빈 문자열.

    '친구는 "…"라고 했는데 비슷한 작품 추천해 주세요'의 뒤 절은 새 주어가 없으므로 작성자·댓글 작성자의 직접 발화다. 뒤 절이 다시
    인용·전언·다른 주체의 서술이거나 앞 인용을 가리키면('그 말은', '그런 말을') 떼지 않는다.
    """
    return _frame_continuation_detail(text, quotes)[0]


def _frame_continuation_detail(text: str, quotes: Sequence[re.Match[str]]) -> Tuple[str, int]:
    """_frame_continuation과 같은 판정. 이어진 절과 그 act view 안 실제 시작 좌표를 돌려준다(없으면 "", -1, B32)."""
    frame = _FRAME_PREDICATE.search(text, quotes[-1].end())
    if not frame:
        return "", -1
    word = next((m for m in _ACT_TOKEN.finditer(text) if m.start() <= frame.end() - 1 < m.end()), None)
    if word is None:
        return "", -1
    if not (_FRAME_CONTINUATION_END.search(word.group(0)) or re.match(r"\s*[,，]", text[word.end():])):
        return "", -1
    rest = text[word.end():].lstrip(" ,，")
    if (not _ACT_TOKEN.search(rest) or _QUOTE_SPAN.search(rest) or _reported_speaker_lead(rest)
            or _BIND_REPORTED_TAIL.search(rest) or _HEARSAY_TAIL.search(rest) or _BACK_REFERENCE.search(rest)
            or re.search(r"(?:다고|라고|냐고|자고)\s*(?:했|말했|하더|하던|한다|합니다)", rest)):
        return "", -1
    if _clause_subject(rest, len(rest)) != "self":
        return "", -1
    return rest.strip(), word.end() + (len(text) - word.end() - len(rest)) + (len(rest) - len(rest.lstrip()))


def _mask_marked(text: str, spans: Sequence[_MarkedSpan], roles: Set[str], *, quotes_only: bool = False,
                  keep_nominal_subject: bool = False, nominal_placeholder: bool = False) -> str:
    return _mask_marked_detail(text, spans, roles, quotes_only=quotes_only, keep_nominal_subject=keep_nominal_subject,
                               nominal_placeholder=nominal_placeholder)[0]


def _mask_marked_detail(text: str, spans: Sequence[_MarkedSpan], roles: Set[str], *, quotes_only: bool = False,
                        keep_nominal_subject: bool = False, nominal_placeholder: bool = False
                        ) -> Tuple[str, Tuple[Tuple[int, int, str, str], ...]]:
    """_mask_marked와 같은 가림. 실제로 가린 (시작, 끝, 역할, 치환 방식)을 함께 돌려준다(B32)."""
    out = list(text)
    applied: List[Tuple[int, int, str, str]] = []
    for span in spans:
        if (span.role in roles and (not quotes_only or span.kind == "quote")
                and not (keep_nominal_subject and span.role == "nominal_argument" and span.case_role == "subject"
                         and not _AGREE.search(text[span.start:span.end]))):
            following = _ACT_TOKEN.search(text, span.end)
            if (nominal_placeholder and span.role == "nominal_argument" and span.case_role != "subject"
                    and following and following.group(0) in _EXCLUDE_MARK):
                out[span.start:span.end] = ("대상" + " " * (span.end - span.start - 2)) if span.end - span.start >= 2 else " "
                applied.append((span.start, span.end, span.role, "placeholder" if span.end - span.start >= 2 else "space"))
            else:
                out[span.start:span.end] = " " * (span.end - span.start)
                applied.append((span.start, span.end, span.role, "space"))
    return "".join(out), tuple(applied)


# 철회 목적어가 동의 명사('내 동의만', '동의를')인 경우. 동의 명사 자체는 평가가 아니므로 그 동의가 가리키는 평가를 따로 읽는다.
_AGREEMENT_NOUNS = {"동의", "공감", "동감", "인정"}
_AGREEMENT_NOUN_COMPLEMENT = {"대한", "관한"}
_OWN_AGREEMENT_LEAD = {"방금", "아까", "앞의", "앞서", "직전의", "지금", "그", "이", "이번", "위의", "위"}


def _agreement_noun_token(tok: str) -> bool:
    """어절이 동의 명사인가('동의', '동의만', '공감을', '인정은'). '동의'의 끝 음절은 소유격 조사가 아니므로 원형을 먼저 본다."""
    return tok in _AGREEMENT_NOUNS or (_TOKEN_PARTICLE.sub("", tok) or tok) in _AGREEMENT_NOUNS


def _retraction_positions(text: str) -> List[Tuple[int, int]]:
    """취소 술어 후보 위치. 앞 어절이 발언 명사·지시어이거나 동의 명사('내 동의만 취소한다')일 때만 후보이며, 실제 철회인지는
    _retraction_acts의 완결 구성 판정이 정한다. 표시 문구와 구독 취소 같은 별개 목적어는 후보가 아니다."""
    tokens = list(re.finditer(r"[가-힣A-Za-z0-9ㄱ-ㅎ]+", text))
    correction = _CORRECTION_LEAD.match(text)
    result = []
    for index, token in enumerate(tokens):
        if correction and token.start() < correction.end():
            continue
        word = token.group(0)
        previous = ""
        for prior in reversed(tokens[:index]):
            candidate = prior.group(0)
            if candidate in _SELF_SUBJECT or _object_gap_adverb(candidate):
                continue
            previous = candidate
            break
        if (_JOKE_COPULA.match(word) or (_RETRACT_VERB.match(word)
                and (not previous or previous in _RETRACT_OBJ
                     or (_TOKEN_PARTICLE.sub("", previous) or previous) in _RETRACT_OBJ
                     or (_TOKEN_PARTICLE.sub("", previous) or previous) in _EVALUATION_RETRACT_OBJ
                     or _agreement_noun_token(previous)))):
            result.append((token.start(), token.end()))
    return result


def _retraction_acts(text: str, works: Sequence[str]) -> List[_AgreementAct]:
    """철회도 동의와 같은 완결 술어 구성(_agreement_construction)·극성·성립 문맥·주체 판정을 거친다.

    취소 어근이 완결 서술어를 이루지 못하고 뒤 명사를 꾸미면('취소 버튼을 눌렀다', '철회 문구') 철회가 아니다. 구성이 봉인한
    원문 구간을 극성·성립 문맥도 그대로 쓴다.
    """
    acts: List[_AgreementAct] = []
    inside = [(a, b) for _, a, b in _work_spans(text, works)]
    for start, end in _retraction_positions(text):
        if any(a <= start < b for a, b in inside):
            continue
        lexeme = _RETRACT_VERB.match(text[start:end])
        if lexeme:
            construction = _agreement_construction(text, start, start + lexeme.end())
            if construction is None:
                continue
            mode = _agreement_act_detail(text, start, start + lexeme.end(), construction=construction)
        else:
            mode = _agreement_act_detail(text, start, end)
        a, b, polarity, realization = mode.start, mode.end, mode.polarity, mode.realization
        actor, actor_span = _clause_subject_detail(_nominal_speech_view(text), a, works, bare_check=True)
        acts.append(_AgreementAct(a, b, 0, actor, polarity, realization, start, False,
                                  mode.temporal_scope, mode.temporal_evidence_span, actor_span))
    return acts


def _agreement_noun_object(target_text: str, region: int, lex: int) -> Optional[Tuple[str, int]]:
    """철회 목적어가 동의 명사면 (종류, 평가 명사구 창의 끝). 동의 명사가 아니면 None.

    'X 평가에 대한 (내) 동의'·'X 평가 동의'는 X 평가 명사구가 대상(complement)이다. 수식어 없이 자기 지칭·지시어만 있는 '내 동의'·
    '그 동의'는 화자의 앞선 동의(own)다. 그 밖의 명사가 꾸미는 '약관 동의'·'개인정보 동의'는 평가 동의가 아니다(unrelated).
    """
    detail = _agreement_noun_object_detail(target_text, region, lex)
    return None if detail is None else (detail[0], detail[1])


def _agreement_noun_object_detail(target_text: str, region: int, lex: int
                                  ) -> Optional[Tuple[str, int, Tuple[int, int]]]:
    """_agreement_noun_object와 같은 판정에 동의 명사 어절의 좌표를 함께 돌려준다(B32)."""
    tokens = _agreement_object_spans(target_text[region:lex], region)
    while tokens and (tokens[-1].text in _SELF_SUBJECT or _object_gap_adverb(tokens[-1].text)):
        tokens = tokens[:-1]
    if not tokens or tokens[-1].quoted or not _agreement_noun_token(tokens[-1].text):
        return None
    noun = (tokens[-1].start, tokens[-1].end)
    rest = tokens[:-1]
    while rest and rest[-1].text in _SELF_POSSESSIVE:
        rest = rest[:-1]
    if len(rest) >= 2 and rest[-1].text in _AGREEMENT_NOUN_COMPLEMENT and rest[-2].text.endswith("에"):
        return "complement", rest[-1].start, noun
    if rest and not rest[-1].quoted and _name_stems(rest[-1].text) & _SPEECH_NOUNS:
        return "complement", rest[-1].end, noun
    if all(t.text in _SELF_WORDS or t.text in _SELF_SUBJECT or t.text in _OWN_AGREEMENT_LEAD or _object_gap_adverb(t.text)
           for t in rest):
        return "own", lex, noun
    return "unrelated", lex, noun


# 등위 연결 어미로 이어진 앞 술어가 뒤 술어와 함께 받는 비실제 성립 문맥.
_COORDINATE_END = re.compile(r"(?:고|며|으며|거나)$")
_SHARED_REALIZATIONS = {"question", "conditional", "reported", "modal", "embedded", "past"}


def _coordinated_realization(text: str, ordered: Sequence[Tuple[int, str, _AgreementAct]]) -> List[Tuple[int, str, _AgreementAct]]:
    """쉼표 없이 등위 연결 어미(-고·-며·-거나)로 이어진 같은 주체의 앞 술어는 뒤 술어의 비실제 성립 문맥(질문·조건·전언·의향·
    관형절·과거)을 함께 받는다. '내가 A를 취소하고 B를 취소한다면'의 두 철회는 모두 조건이다. 뒤 술어가 실제면 바꾸지 않고,
    쉼표·문장 경계나 주체 전환('나는 A를 취소하고 동생은 …')이 있으면 각자 성립한다."""
    result = list(ordered)
    for index in range(len(result) - 2, -1, -1):
        position, kind, act = result[index]
        _, next_kind, following = result[index + 1]
        if ("correct" in (kind, next_kind) or act.realization != "actual"
                or following.realization not in _SHARED_REALIZATIONS):
            continue
        words = _ACT_TOKEN.findall(text[act.start:act.end])
        if (not words or not _COORDINATE_END.search(words[-1])
                or re.search(r"[.!?？。…;,，]", text[act.end:following.start]) or act.subject != following.subject):
            continue
        result[index] = (position, kind, replace(act, realization=following.realization,
                                                 realization_source="coordinated_with_following"))
    return result


def _nominal_speech_view(text: str) -> str:
    """발언 명사를 수식하는 인용 술어를 주체·목적어 머리로 오인하지 않는 좌표 view."""
    spans = list(_ACT_TOKEN.finditer(text))
    out = list(text)
    for index, span in enumerate(spans):
        if (_ACT_QUOTATIVE_END.search(span.group(0))
                and (_AGREE.search(span.group(0)) or _RETRACT_VERB.match(span.group(0)))
                and any(_name_stems(next_span.group(0)) & _SPEECH_NOUNS for next_span in spans[index + 1:index + 4])):
            out[span.start():span.end()] = " " * (span.end() - span.start())
    return "".join(out)


def _source_bound_events(text: str, target_text: str, utts: Sequence[_Utterance], works: Sequence[str],
                         last_adopted: Set[int], correction: bool = False, source_prefix: str = "clause:0",
                         previous_adoption_events: Tuple[str, ...] = (), raw_text: Optional[str] = None,
                         adoption_history: Sequence[Tuple[str, Tuple[int, ...]]] = (),
                         own_evaluations: Sequence[Tuple[int, str, Tuple[str, ...], Tuple[str, ...], str]] = ()
                         ) -> List[_BoundAgreementEvent]:
    """공통 위치순 사건 원장을 만든다. 모든 술어가 다음 사건의 목적어 범위를 전진시킨다.

    등위 연결 술어는 뒤 술어의 비실제 성립 문맥을 함께 받는다(_coordinated_realization). 동의 명사를 목적어로 한 철회는
    _agreement_noun_object가 정한 평가 명사구·앞선 동의·무관 대상에만 결속한다.
    """
    specs = [(act.start, "agree", act) for act in _agreement_acts(text, works)]
    specs += [(act.start, "retract", act) for act in _retraction_acts(text, works)]
    if correction:
        match = _CORRECTION_LEAD.match(text) or _CORRECTION_WEAK.match(text)
        if match:
            word = next(_ACT_TOKEN.finditer(text), None)
            if word:
                mode = _agreement_act_detail(text, word.start(), word.end())
                a, b, polarity, realization = mode.start, mode.end, mode.polarity, mode.realization
                mode_source = "own_construction"
                if word.group(0) == "아니":
                    # 정정 접속어의 니는 의문 어미가 아니다. 뒤 주체 절을 정정하는 담화 구성이다.
                    realization = "actual"
                    mode_source = "correction_marker_override"
                if not any(start <= a < act.end for start, _, act in specs):
                    # B32: 정정 행위의 주체는 절 주어 판정이 아니라 화자 단위 본인으로 고정된 값이다.
                    specs.append((a, "correct", _AgreementAct(a, b, 0, "self", polarity, realization, a, False,
                                                             mode.temporal_scope, mode.temporal_evidence_span, (-1, -1),
                                                             mode_source, "correction_unit_speaker_fixed")))
    prior = [i for i, u in enumerate(utts) if u.kind == "reported"]
    speakers = {utts[i].speaker for i in prior if utts[i].speaker not in ("other", "self")}
    events: List[_BoundAgreementEvent] = []
    region = 0
    nominal_edges: List[Tuple[int, int]] = []
    for _, kind, original in _coordinated_realization(text, sorted(specs, key=lambda entry: entry[0])):
        act = replace(original, region=max(region, original.region))
        noun_object = _agreement_noun_object_detail(target_text, act.region, act.lex) if kind == "retract" else None
        agreement_object = (noun_object[0], noun_object[1]) if noun_object else None
        # B33(H11): 동의 명사가 아닌 평가 명사('내 결말 호평은 취소한다')를 목적어로 한 철회.
        evaluation_object = (_own_evaluation_object(target_text, act, own_evaluations, works)
                             if kind == "retract" and not agreement_object else None)
        if evaluation_object is not None and evaluation_object[5]:
            # 주어 근거가 철회 목적어 명사구 안의 토큰('호평은', '작가 칭찬은')이면 철회 주체는 화자 본인이다.
            act = replace(act, subject="self", subject_evidence_span=(-1, -1), subject_source="evaluation_object_unit_speaker")
        window_end = agreement_object[1] if agreement_object and agreement_object[0] == "complement" else act.lex
        tokens = _agreement_object_spans(_nominal_speech_view(target_text[act.region:window_end]), act.region)
        relations = tuple(_object_relation_ledger(tokens, speakers, works))
        local = target_text[act.region:act.end]
        targets, how = _agreement_targets(local, prior, utts, works, window_end - act.region, act.truth,
                                          tokens, relations)
        effect = (act.effect if not act.subject.startswith("other:") else "") if kind == "agree" else (
            "withdraw" if act.realization == "actual" and act.polarity == "positive" and act.subject == "self" else "")
        target_event_ids: Tuple[str, ...] = ()
        # B32: reducer 전 parser의 철회 범위 판단. 효과가 없는 성립 문맥이어도 계산한 범위 분기를 남긴다.
        token_span = (tokens[0].start, tokens[-1].end) if tokens else (-1, -1)
        if kind == "agree":
            scope, scope_span = ("agreement_object_targets", token_span) if effect == "withdraw" else ("not_withdrawal", (-1, -1))
        else:
            scope, scope_span = "constrained_object_targets", token_span
        if kind == "correct":
            scope, scope_span = "previous_adoption_by_correction", (act.start, act.end)
            # 담화 정정은 실제 성립할 때만 바로 앞 채택에 결속한다.
            effect = "withdraw" if act.realization == "actual" and (
                act.polarity == "positive" or text[act.start:act.end].startswith("아니")) else ""
            targets, how = sorted(last_adopted), "previous_adoption"
            target_event_ids = previous_adoption_events
        elif kind == "retract" and agreement_object:
            scope, scope_span = "agreement_noun_complement_prior_adoptions", token_span
            if agreement_object[0] == "complement":
                # B33: 'X 평가에 대한 내 동의'는 X에 대한 앞선 자기 동의 사건을 가리킨다. 동의한 적 있는 전언 중에서 X 제약으로 고르고
                # 그 동의 사건을 참조로 남긴다. 동의한 적 없는 전언을 철회 대상으로 넓히지 않는다.
                targets, how, target_event_ids = _prior_adoption_targets(local, utts, works, window_end - act.region, act.truth,
                                                                         tokens, relations, adoption_history, events)
            if agreement_object[0] == "own":
                scope, scope_span = "own_agreement_previous_adoption", noun_object[2]
                # '내 동의를 취소한다': 수식 없는 자기 동의는 이 절 또는 직전 절의 가장 가까운 동의 사건을 가리킨다.
                preceding = next((e for e in reversed(events) if e.effect == "adopt" and e.kind == "agree"), None)
                targets, how = (sorted(preceding.targets) if preceding else sorted(last_adopted)), "previous_adoption"
                target_event_ids = (preceding.event_id,) if preceding else previous_adoption_events
            elif agreement_object[0] == "unrelated":
                scope, scope_span = "unrelated_agreement_noun", noun_object[2]
                targets, how = [], "unrelated"
        elif kind == "retract" and evaluation_object is not None:
            if evaluation_object[0] == "own":
                # 본인 평가 철회는 같은 화자 단위의 앞선 본인 현재 평가 claim을 거둔다(극성·명사구 항목·작품으로 선택).
                scope, scope_span = "own_evaluation_prior_claims", evaluation_object[3]
                targets, how, target_event_ids = list(evaluation_object[1]), evaluation_object[2], evaluation_object[4]
            else:
                # 다른 사람 소유이거나 본인·직전 지시가 없는 평가 명사 철회는 무엇도 거두지 않는다(일반 철회로 넓히지 않는다).
                scope, scope_span = "unrelated_evaluation_noun", evaluation_object[3]
                targets, how = [], "unrelated"
        elif kind == "retract" and any(act.region <= a and b <= act.lex for a, b in nominal_edges):
            # B33: 'X에 동의했다는 앞의 말'의 철회는 그 동의 진술을 가리킨다. 앞선 자기 동의 사건 중 X 제약에 맞는 것에 결속한다.
            scope, scope_span = "embedded_agreement_statement_prior_adoptions", token_span
            targets, how, target_event_ids = _prior_adoption_targets(local, utts, works, window_end - act.region, act.truth,
                                                                     tokens, relations, adoption_history, events)
        elif kind == "retract":
            constrained = any(r.values for r in relations)
            if not constrained:
                # 명시된 무제약 철회는 이 시점까지의 채택만 거둔다. 미래 사건은 포함하지 않는다.
                active_ids = {i for i, u in enumerate(utts) if u.adopted}
                for preceding in events:
                    if preceding.effect == "adopt":
                        active_ids.update(preceding.targets)
                    elif preceding.effect == "withdraw":
                        active_ids.difference_update(preceding.targets)
                targets, how = sorted(active_ids), "prior_adopted"
                scope, scope_span = "all_prior_adopted", (-1, -1)
                preceding_adoption = next((e.targets for e in reversed(events) if e.effect == "adopt"), ())
                previous_ids = set(preceding_adoption) or last_adopted
                deictic = re.search(r"(?:앞|방금|직전|지금\s*한)(?:의)?\s*(?:말|발언|평가)", local)
                if deictic and previous_ids:
                    scope, scope_span = "previous_adoption_by_deictic_speech", (act.region + deictic.start(), act.region + deictic.end())
                    targets, how = sorted(previous_ids), "previous_adoption"
                    target_event_ids = ((next(e.event_id for e in reversed(events) if e.effect == "adopt"),)
                                        if preceding_adoption else previous_adoption_events)
                if how not in ("previous_adoption",) and not tokens:
                    target_event_ids = tuple(e.event_id for e in events if e.effect == "adopt") + previous_adoption_events
            elif how in ("ambiguous_speaker", "speech", "speaker", "work"):
                # 철회 명사구의 명시 부분 제약은 선택의 모호함을 전체 철회로 확장하지 않는다.
                pass
        events.append(_BoundAgreementEvent(act.start, act.end, act.subject, act.polarity, act.realization,
                                           effect, tuple(targets), "targets_utterance" if targets else how,
                                           how, relations, kind, f"{source_prefix}:{act.start}:{act.end}:{kind}", target_event_ids,
                                           source_prefix, source_prefix, (raw_text or text)[act.start:act.end], (act.start, act.end),
                                           _native_subject(raw_text or text, act.start, works), tuple(tokens),
                                           _native_objects(raw_text or target_text, tokens, relations, works),
                                           temporal_scope=act.temporal_scope, temporal_evidence_span=act.temporal_evidence_span,
                                           realization_source=act.realization_source, subject_evidence_span=act.subject_evidence_span,
                                           subject_source=act.subject_source, withdrawal_scope=scope,
                                           withdrawal_scope_evidence_span=scope_span))
        suffix_tokens = [m.group(0) for m in _ACT_TOKEN.finditer(text[act.end:])]
        nominal_edge = (kind == "agree" and act.realization in ("reported", "embedded")
                        and _ACT_QUOTATIVE_END.search(text[act.start:act.end].strip())
                        and any(_name_stems(word) & _SPEECH_NOUNS for word in suffix_tokens[:3]))
        # 'A 평가에 동의했다는 앞의 말만 취소한다'의 인용 술어는 바깥 철회의 목적어를 수식한다.
        # 하위 관형/인용 사건의 끝으로 바깥 명사구의 시작 좌표를 잘라 버리지 않는다.
        if not nominal_edge:
            region = max(region, act.end)
        else:
            nominal_edges.append((act.start, act.end))
    return events


def _own_evaluation_index(claims: Sequence[_NativeClaim], evaluations: Sequence[_EvaluationEvent]
                          ) -> Tuple[Tuple[int, str, Tuple[str, ...], Tuple[str, ...], str], ...]:
    """B33(H11): 지금까지 지지되는 본인 claim의 실제 평가 사건 (발화 index, 평가 극성, 목적어 문자열, 작품 표면, 사건 ID)."""
    out = []
    for index, claim in enumerate(claims):
        if claim.kind != "own" or not claim.final_support:
            continue
        for event in evaluations:
            if event.claim_id == claim.claim_id and event.realization == "actual" and event.evaluation_polarity in ("pos", "neg"):
                objects = " ".join(o.text for o in event.objects) or claim.text
                surfaces = tuple(dict.fromkeys(w for o in event.objects for w in o.works))
                out.append((index, event.evaluation_polarity, objects, surfaces, event.event_id))
    return tuple(out)


def _own_evaluation_object(target_text: str, act: _AgreementAct,
                           own_evaluations: Sequence[Tuple[int, str, str, Tuple[str, ...], str]],
                           works: Sequence[str]) -> Optional[Tuple[str, Tuple[int, ...], str, Tuple[int, int], Tuple[str, ...], bool]]:
    """B33(H11): 철회 술어 바로 앞 목적어가 평가 명사면 (종류, 대상 발화 index, 결속 이유, 평가 명사 구간, 대상 평가 사건 ID).

    철회 주체가 화자 본인이면 본인이 거둘 수 있는 평가는 본인 평가뿐이다. 평가 명사 앞 명사구에 다른 사람 소유자('친구의')가 있을
    때만 종류 unrelated이고, 그 밖에는 종류 own이다. 평가 명사 극성이 같고, 명사구의 내용어(본인 소유·직전 지시·지시 관형어 제외)가
    모두 대상 평가 사건의 목적어 문자열에 있는 본인 현재 평가 claim만 고른다. 작품 표면도 같은 사건의 작품이어야 한다. 직전
    지시어가 있으면 가장 최근 claim이다. 목적어가 평가 명사가 아니면 None이다. 마지막 값은 철회 행위의 주어 근거가 이 목적어 명사구
    안(평가 명사 자체, 조사 없는 수식 명사, 조사를 떼면 한 음절만 남는 명사 끝음절 오분절 '작가')에 있는지다. 그때 그 토큰은 주어가 아니다.
    H11d: 명시 본인 주어('나는'·'저는'·'나도'·'내가')는 내용어에서 빼고, 목적어 밖 실제 주어가 다른 사람이면 종류 unrelated다.
    """
    region = target_text[act.region:act.lex]
    tokens = list(_ACT_TOKEN.finditer(region))
    head = next((t for t in reversed(tokens) if t.group(0) not in _SELF_SUBJECT and not _object_gap_adverb(t.group(0))), None)
    if head is None:
        return None
    polarity = _EVALUATION_RETRACT_OBJ.get(_TOKEN_PARTICLE.sub("", head.group(0)) or head.group(0))
    if polarity is None:
        return None
    span = (act.region + head.start(), act.region + head.end())
    before = [t.group(0) for t in tokens if t.end() <= head.start()]
    lo, hi = act.subject_evidence_span
    subject_in_object = lo >= 0 and any(
        act.region + t.start() <= lo and hi <= act.region + t.end()
        and (t is head or (t.end() <= head.start() and len(_TOKEN_PARTICLE.sub("", t.group(0)) or t.group(0)) in (1, len(t.group(0)))))
        for t in tokens)
    if act.subject.startswith("other:") and not subject_in_object:
        # 철회 행위의 실제 주어가 목적어 명사구 밖의 다른 사람이면 그 평가 명사는 그 사람의 평가다. 본인 평가를 거두지 않는다.
        return "unrelated", (), "unrelated", span, (), subject_in_object
    surfaces = {w for w, _, _ in _work_spans(region[:head.start()], works)}
    deictic = any(w in _RECENT_DEICTIC for w in before)
    content: List[str] = []
    for word in before:
        # 명시 본인 주어는 철회 주체이지 목적어 명사구 내용어가 아니다.
        if (word in _SELF_POSSESSIVE or word in _SELF_SUBJECT or word in _RECENT_DEICTIC or word in _DEICTIC_DET
                or word in _UNIVERSAL_DET or _object_gap_adverb(word)):
            continue
        stem = _TOKEN_PARTICLE.sub("", word) or word
        if word.endswith("의") and stem not in _DOMAIN_NOUNS and not any(stem == s or stem.startswith(s) for s in surfaces):
            return "unrelated", (), "unrelated", span, (), subject_in_object
        content.append(stem)
    candidates = [entry for entry in own_evaluations
                  if entry[1] == polarity and all(stem in entry[2] for stem in content) and surfaces <= set(entry[3])]
    if deictic and candidates:
        latest = max(entry[0] for entry in candidates)
        candidates = [entry for entry in candidates if entry[0] == latest]
    targets = tuple(sorted({entry[0] for entry in candidates}))
    return "own", targets, ("targets_utterance" if targets else "no_match"), span, tuple(entry[4] for entry in candidates), subject_in_object


def _prior_adoption_targets(local: str, utts: Sequence[_Utterance], works: Sequence[str], offset: int, truth: bool,
                            tokens: Sequence[_ObjectToken], relations: Sequence[_ObjectRelation],
                            adoption_history: Sequence[Tuple[str, Tuple[int, ...]]],
                            events: Sequence[_BoundAgreementEvent]) -> Tuple[List[int], str, Tuple[str, ...]]:
    """B33: 앞선 자기 동의 사건(앞 절의 적용된 채택과 같은 절의 앞 동의)이 채택한 발화 중 철회 목적어 제약에 맞는 것과 그 사건 ID.

    후보 선택은 기존 _agreement_targets의 화자·작품·항목 제약과 모호성 규칙을 그대로 쓴다. 후보가 없으면 no_match다.
    """
    history = list(adoption_history) + [(e.event_id, e.targets) for e in events
                                        if e.kind == "agree" and e.effect == "adopt" and e.subject == "self"]
    adopted = sorted({i for _, targets in history for i in targets})
    if not adopted:
        return [], "no_match", ()
    targets, how = _agreement_targets(local, adopted, utts, works, offset, truth, tokens, relations)
    chosen = set(targets)
    return list(targets), how, tuple(eid for eid, ids in history if chosen & set(ids))


def _speaker_ledger(parts: Sequence[str], works: Sequence[str] = (), source_id: str = "unit:0",
                    unit_input: Optional["_NativeUnitInput"] = None) -> _SpeakerLedger:
    """화자 단위(작성자 글 전체, 댓글 한 개)의 절을 순서대로 발화 목록으로 만들고, 동의·반박·철회를 적용한 현재 채택 상태를 매긴다.

    직접 발화는 채택, 바깥 인용 틀과 결속한 reported_utterance 및 전언은 미채택으로 시작한다. 인용마다 바깥 틀의 극성·양태를 보고,
    부정('라고 말한 적이 없다')이면 denied, 질문·가정이면 uncertain으로 두어 채택하지 않고 동의로도 되살리지 않는다(자기 인용도 같다).
    긍정 틀의 자기 인용만 직접 발화로 채택한다.

    동의 행위(_agreement_acts)마다 극성·성립 문맥·주체·대상을 따로 확인한다. 긍정 극성이 실제로 성립했고(effect adopt) 주체가 화자
    본인일 때만 _agreement_targets가 가리킨 발화를 채택한다. 부정 극성이 실제로 성립했거나 긍정이 대조로 뒤집히면(effect withdraw) 주체가
    본인이거나 확정되지 않았을 때 가리킨 발화를 미채택으로 두고 반박 목록에 올린다(무관한 대상은 그대로, 대상 불명확이면 앞선 인용·전언
    전부). 질문·가정·가능·의향·전언·과거·관형절 속 동의는 극성과 상관없이 아무것도 바꾸지 않는다. 반박한 발화는 뒤의 목적어 없는
    동의('나는 동의한다')로 되살리지 않고, 생각을 바꾼 표지('다시 보니', '생각이 바뀌')나 명시 목적어가 있을 때만 다시 채택한다.
    정정 절('아니, 동생이 동의한다', '정정: …')은 바로 앞 절에서 채택한 발화를 먼저 거둔다. 동의 행위의 주체가 모두 제3자이거나,
    동의가 없고 제3자 주어의 인지·발화 서술('동생은 결말이 좋다고 생각한다')이면 그 절은 그 사람의 전언이다. 철회는 그 시점까지 채택된
    발화를 모두 거두고, 그 뒤의 새 동의는 다시 적용된다.
    """
    utts: List[_Utterance] = []
    sources: List[_NativeSource] = []
    claims: List[_NativeClaim] = []
    applications: List[_NativeEventApplication] = []
    evaluations: List[_EvaluationEvent] = []
    assertions: List[_NativeAssertion] = []
    integrity: List[str] = []
    # B32: caller metadata는 절 문자열이 parts와 같을 때만 절마다 붙인다. 다르거나 없으면 NOT_OBSERVED다.
    if unit_input is None:
        clause_inputs: Tuple[_NativeClauseInput, ...] = ()
        alignment = _NOT_OBSERVED
    elif tuple(c.text for c in unit_input.clauses) == tuple(parts):
        clause_inputs, alignment = unit_input.clauses, "caller_clauses_equal_parts"
    else:
        clause_inputs, alignment = (), "caller_clauses_differ_parts"

    def claim_state(index: int) -> _NativeClaimState:
        claim = claims[index]
        return _NativeClaimState(claim.claim_id, claim.active_adoption_event_ids, claim.final_support)

    def append_claim(pos, speaker, kind, content, original, adopted, span, candidates, evidence_offset=None, binding_text=None, binding_offset=None,
                     *, attribution=_NOT_OBSERVED, speaker_source=_NOT_OBSERVED, attribution_span=(-1, -1),
                     frame_status="not_quote", text_view_id="", text_offset=-1, binding_view_id="", matrix_subject=None):
        index = len(utts)
        clause_id = f"{source_id}:clause:{pos}"
        cid = f"{clause_id}:claim:{index}"
        binding_text = content if binding_text is None else binding_text
        binding_offset = (span[0] if evidence_offset is None else evidence_offset) if binding_offset is None else binding_offset
        ids = []
        for candidate in candidates:
            event = replace(candidate, speaker=speaker, claim_id=cid, evidence_text=content,
                            evidence_offset=span[0] if evidence_offset is None else evidence_offset,
                            binding_text=binding_text, binding_offset=binding_offset,
                            parent_event_id=(candidate.parent_event_id if candidate.assertion_span != (-1, -1) else cid),
                            claim_attachment="claim", evidence_view_id=text_view_id, binding_view_id=binding_view_id)
            if kind in ("reported", "denied", "uncertain") and speaker != "self":
                event = replace(event, actor="other:" + speaker, attribution="reported_claim_speaker",
                                attribution_evidence_span=attribution_span)
            evaluations.append(event)
            ids.append(event.event_id)
            if event.assertion_span != (-1, -1):
                lo, hi = event.assertion_span
                head = re.search(r"(?:내|제|나의|저의)\s+(?:답|입장|평가|결론|생각)(?:은|는|이|가)", original[lo:hi])
                predicate = re.search(r"(?:것|거)(?:이)?(?:다|입니다|야|예요|임)[.!。~…]*$", original[lo:hi])
                if head and predicate:
                    sub = _NativeSubject("self", head.group(0), (lo + head.start(), lo + head.end()), True)
                    ps = (lo + predicate.start(), lo + predicate.end())
                    assertion = _NativeAssertion(clause_id, event.parent_event_id, (lo, hi), sub,
                                                 original[ps[0]:ps[1]], ps, "actual", "positive")
                    known = next((a for a in assertions if a.event_id == assertion.event_id), None)
                    # B32: 같은 상위 단언을 여러 평가가 가리키면 정의는 하나다. 같은 ID의 다른 정의는 보존하고 실패로 남긴다.
                    if known is None:
                        assertions.append(assertion)
                    elif known != assertion:
                        assertions.append(assertion)
                        integrity.append("ID_COLLISION:assertion:" + assertion.event_id)
        initial = (f"{cid}:direct",) if adopted else ()
        claims.append(_NativeClaim(cid, clause_id, source_id, index, speaker, kind, content, span,
                                   matrix_subject or _native_subject(original, span[1], works, bare_check=False), tuple(ids), adopted, initial, adopted, binding_text, binding_offset,
                                   attribution=attribution, speaker_source=speaker_source, attribution_evidence_span=attribution_span,
                                   quote_frame_status=frame_status, text_view_id=text_view_id, text_offset=text_offset,
                                   binding_view_id=binding_view_id))
        utts.append(_Utterance(pos, speaker, kind, content, original, adopted))
    rejected: Set[int] = set()
    last_adopted: Set[int] = set()
    last_adoption_events: Tuple[str, ...] = ()
    reaffirmed: dict = {}
    for pos, p in enumerate(parts):
        clause_id = f"{source_id}:clause:{pos}"
        # B33(F03): '이는 내 현재 평가다'는 바로 앞 절의 자기 기록·판단 술어에 걸린 평가 명제를 현재 자기 평가로 단언한다.
        affirm = _SELF_REAFFIRMATION.fullmatch(p.strip()) if pos else None
        if affirm and _CURRENT_MARK.search(p):
            lead = len(p) - len(p.lstrip())
            holder = re.search(r"(?:내|제|나의|저의)\s", p)
            copula = re.search(r"(?:평가|생각|의견|입장)(?:이)?(?:다|입니다|이다|예요|이에요|임)[.!。~…]*\s*$", p)
            previous = f"{source_id}:clause:{pos - 1}"
            antecedents = [c for c in claims if c.source_id == previous and c.kind == "own" and c.final_support]
            targets = [e for e in evaluations if any(e.claim_id == c.claim_id for c in antecedents) and e.realization == "reported"
                       and _self_governed_report(parts[pos - 1], e, works)]
            if holder and copula and targets:
                span = (lead, len(p.rstrip()))
                assertion = _NativeAssertion(clause_id, f"{clause_id}:{span[0]}:{span[1]}:self_assertion", span,
                                             _NativeSubject("self", holder.group(0).strip(), (holder.start(), holder.start() + len(holder.group(0).strip())), True),
                                             p[copula.start():copula.end()].rstrip(), (copula.start(), copula.start() + len(p[copula.start():copula.end()].rstrip())),
                                             "actual", "positive")
                assertions.append(assertion)
                for e in targets:
                    reaffirmed[e.event_id] = assertion.event_id
        speakers = {u.speaker for u in utts if u.speaker not in ("self", "other")}
        marked = _marked_spans(p, works, speakers)
        reported_spans = {(s.start, s.end) for s in marked if s.kind == "quote" and s.role == "reported_utterance"}
        quotes = [m for m in _QUOTE_SPAN.finditer(p) if (m.start(), m.end()) in reported_spans]
        # 행위 추출에서는 인용 속 어형을 가린다. 목적어 결속에서는 작품·화자명
        # 인용을 보존하고 완결 발화 인용만 가린다. 두 view의 원문 위치는 같다.
        target_text, binding_masks = _mask_marked_detail(p, marked, {"reported_utterance", "display_label"}, quotes_only=True)
        # 기록 내용(필사·적은 문장)은 누구의 현재 평가·동의도 아니므로 목적어·행위·공개 근거 어디에도 쓰지 않는다.
        target_text, recorded_masks = _mask_marked_detail(target_text, marked, {"recorded_content"})
        text, act_masks = _mask_marked_detail(p, marked, {"reported_utterance", "nominal_argument", "display_label"},
                                              quotes_only=True, keep_nominal_subject=True, nominal_placeholder=True)
        text, late_masks = _mask_marked_detail(text, marked, {"display_label", "recorded_content"})
        # B32: parser가 실제로 읽은 raw·가린 행위 view·결속 view·인용 내용 view를 같은 절 기록에 남긴다.
        quote_parts = [_quote_body_offset(m) for m in quotes]
        act_view_id, binding_view_id = f"{clause_id}:view:act", f"{clause_id}:view:binding"
        views = [_NativeParserView(f"{clause_id}:view:raw", "raw_clause", p, 0),
                 _NativeParserView(act_view_id, "act_masked", text, 0, act_masks + late_masks),
                 _NativeParserView(binding_view_id, "binding_masked", target_text, 0, binding_masks + recorded_masks)]
        views += [_NativeParserView(f"{clause_id}:view:quote:{qi}", "quote_body", body, offset)
                  for qi, (body, offset) in enumerate(quote_parts)]
        sources.append(_native_source(clause_id, source_id, pos, p, clause_inputs[pos] if clause_inputs else None, tuple(views)))
        for qi, m in enumerate(quotes):
            body, offset = quote_parts[qi]
            speaker, speaker_route, speaker_span = _quote_speaker_detail(p, m)
            status = _quote_frame_status(p[m.end():(quotes[qi + 1].start() if qi + 1 < len(quotes) else len(p))], speaker == "self")
            quote_view_id = f"{clause_id}:view:quote:{qi}"
            quote_events = [_offset_evaluation(e, offset) for e in _source_evaluation_events(body, works, clause_id)]
            if status != "affirmed":
                append_claim(pos, speaker, "denied" if status == "negated" else "uncertain", body, p, False,
                             (offset, offset + len(body)), quote_events,
                             attribution="quote_denied" if status == "negated" else "quote_uncertain",
                             speaker_source=speaker_route, attribution_span=speaker_span, frame_status=status,
                             text_view_id=quote_view_id, text_offset=offset, binding_view_id=quote_view_id)
            else:
                append_claim(pos, speaker, "own" if speaker == "self" else "reported", body, p, speaker == "self",
                             (offset, offset + len(body)), quote_events,
                             attribution="quote_self_affirmed" if speaker == "self" else "quote_other_affirmed",
                             speaker_source=speaker_route, attribution_span=speaker_span, frame_status=status,
                             text_view_id=quote_view_id, text_offset=offset, binding_view_id=quote_view_id)
        frame = bool(quotes) and bool(_REPORTED_SPEAKER.match(text.strip()) or re.search(r"(?:라고|이라고|고)\s*(?:했|말했|하더|하던)", text))
        acts = _agreement_acts(text, works)
        own_acts = [a for a in acts if not a.subject.startswith("other:")]
        third_subject = acts[0].subject if acts and not own_acts else ""
        third_route, third_span = ("agreement_act_subject", acts[0].subject_evidence_span) if third_subject else ("", (-1, -1))
        nominal_judgment = _nominal_judgment_binding(text, works) if not quotes and not acts else None
        matrix_subject = None
        if not acts:
            tp = _THIRD_PRED.search(text)
            s, s_span = _clause_subject_detail(text, tp.start(), works) if tp else ("", (-1, -1))
            if nominal_judgment is not None and (tp is None or
                    nominal_judgment["copula_span"][0] <= tp.start() < nominal_judgment["governor_span"][1]):
                s, s_span = nominal_judgment["actor"], nominal_judgment["actor_span"]
                matrix_subject = _NativeSubject(s, text[s_span[0]:s_span[1]] if s_span[0] >= 0 else "",
                                                s_span, s_span[0] >= 0)
            third_subject = s if s.startswith("other:") else ""
            third_route, third_span = ("third_party_predicate_subject", s_span) if third_subject else ("", (-1, -1))
        evaluation_acts = _evaluation_events(text, works, clause_id)
        source_evaluations = [replace(e, objects=_evaluation_objects(target_text, e.start, works))
                              for e in _source_evaluation_events(text, works, clause_id)]
        if not acts and evaluation_acts:
            matrix_subject = None  # 독립 명시 평가 행위의 기존 주체 우선순위는 유지한다.
            actor = evaluation_acts[-1].actor
            third_subject = actor if actor.startswith("other:") else ""
            third_route, third_span = (("evaluation_actor", evaluation_acts[-1].attribution_evidence_span) if third_subject
                                       else ("", (-1, -1)))
        correction = bool(_CORRECTION_LEAD.match(text) or (third_subject and _CORRECTION_WEAK.match(text)))
        adopted_now: Set[int] = set()
        # B33(H9): 첫 어절이 전언 화자 어휘('친구의 …')여도 화자 본인의 철회 행위가 절에 있으면 전언 틀이 아니다. 동의 행위 예외와
        # 같은 조건(본인 주체, 그 앞에 전언 표지 없음)이며, 철회의 극성·성립 문맥은 아래 사건 적용이 그대로 정한다.
        lead_report = bool(_reported_speaker_lead(text)) and not (
            (own_acts and own_acts[0].subject == "self" and not _LEAD_REPORT_MARK.search(text[:own_acts[0].start]))
            or (evaluation_acts and evaluation_acts[-1].actor == "self"
                and not _LEAD_REPORT_MARK.search(text[:evaluation_acts[-1].start]))
            or any(act.subject == "self" and not _LEAD_REPORT_MARK.search(text[:act.start])
                   for act in _retraction_acts(text, works)))
        if not quotes and not correction and (lead_report or _BIND_REPORTED_TAIL.search(text) or _HEARSAY_TAIL.search(text) or third_subject):
            first = re.findall(r"[가-힣A-Za-z0-9]+", text)
            # B33: 첫 어절을 화자로 쓰는 것은 전언 화자 어휘('친구가 그러는데')로 시작할 때뿐이다. 꼬리 표지만 있는 전언
            # ('결말이 좋다더라')의 첫 어절은 내용이므로 화자를 미확정 other로 둔다.
            speaker = third_subject[len("other:"):] if third_subject else (_stem_of(first[0]) if first and lead_report else "other")
            first_token = re.search(r"[가-힣A-Za-z0-9]+", text) if lead_report else None
            trigger = ("lead_report_speaker" if lead_report else "reported_tail" if _BIND_REPORTED_TAIL.search(text)
                       else "hearsay_tail" if _HEARSAY_TAIL.search(text) else "third_party_subject")
            route, route_span = ((third_route, third_span) if third_subject
                                 else ("first_token_stem", first_token.span()) if first_token else ("default_other", (-1, -1)))
            append_claim(pos, speaker, "reported", text.strip(), p, False, (0, len(p)), source_evaluations,
                         attribution="report_clause_" + trigger, speaker_source=route, attribution_span=route_span,
                         text_view_id=act_view_id, text_offset=len(text) - len(text.lstrip()), binding_view_id=act_view_id,
                         matrix_subject=matrix_subject)
            last_adopted = adopted_now
            continue
        prior = [i for i, u in enumerate(utts) if u.kind == "reported"]
        events = _source_bound_events(text, target_text, utts, works, last_adopted,
                                      correction or bool(third_subject and _CORRECTION_WEAK.match(text)),
                                      clause_id, last_adoption_events, raw_text=p,
                                      adoption_history=tuple((a.event.event_id, a.event.targets) for a in applications
                                                             if a.applied_effect == "adopt"),
                                      own_evaluations=_own_evaluation_index(claims, evaluations))
        for event in events:
            fallback = not (event.effect != "withdraw" or event.kind != "agree" or event.targets
                            or event.binding_kind in ("unrelated", "no_match"))
            target_indices = event.targets if not fallback else tuple(prior)
            before = tuple(claim_state(i) for i in target_indices)
            target_adoptions = tuple(sorted(set(event.target_event_ids)
                                            | {eid for state in before for eid in state.adoption_event_ids}))
            applied = event.effect
            reason = "event_effect_applied"
            if not event.effect or (event.effect == "adopt" and event.subject != "self"):
                applied = ""
                reason = "no_event_effect" if not event.effect else "adopt_subject_not_self"
            elif event.effect == "adopt":
                if event.binding_kind == "no_object" and set(event.targets) <= rejected and not _MIND_CHANGE.search(text):
                    applied = ""
                    reason = "no_object_targets_previously_rejected"
                else:
                    for i in event.targets:
                        utts[i].adopted = True
                        claims[i] = replace(claims[i], final_support=True,
                                            active_adoption_event_ids=tuple(sorted(set(claims[i].active_adoption_event_ids) | {event.event_id})))
                        rejected.discard(i)
                        adopted_now.add(i)
            else:
                for i in target_indices:
                    utts[i].adopted = False
                    claims[i] = replace(claims[i], final_support=False, active_adoption_event_ids=())
                    rejected.add(i)
                    adopted_now.discard(i)
            after = tuple(claim_state(i) for i in target_indices)
            applications.append(_NativeEventApplication(event, tuple(claims[i].claim_id for i in target_indices),
                                                        target_adoptions, before, applied, after,
                                                        reducer_target_source="all_prior_reported_fallback" if fallback else "event_targets",
                                                        applied_effect_reason=reason,
                                                        changed_claim_ids=tuple(state.claim_id for state, prior_state in zip(after, before)
                                                                                if state != prior_state)))
        last_adopted = adopted_now
        last_adoption_events = tuple(e.event_id for e in events
                                     if e.effect == "adopt" and set(e.targets) & adopted_now)
        # 같은 줄에서 인용 틀 술어 뒤에 이어진 화자 본인의 절은 전언이 아니라 직접 발화다.
        continuation, continuation_start = _frame_continuation_detail(text, quotes) if quotes and (frame or third_subject) else ("", -1)
        if third_subject:
            if continuation:
                span = (text.find(continuation), text.find(continuation) + len(continuation))
                append_claim(pos, "self", "own", continuation, p, True, span,
                             [e for e in source_evaluations if span[0] <= e.start < span[1]],
                             attribution="frame_continuation", speaker_source="unit_speaker",
                             text_view_id=act_view_id, text_offset=continuation_start, binding_view_id=act_view_id)
            known_events = {e.event_id for e in evaluations}
            evaluations.extend(replace(e, claim_attachment="unattached_third_party_clause")
                               for e in source_evaluations if e.event_id not in known_events)
            continue
        if text.strip() and not frame:
            unasserted = _unasserted_role_lead(text)
            append_claim(pos, "self", "uncertain" if unasserted else "own", text.strip(), p, not unasserted, (0, len(p)), source_evaluations,
                         len(text) - len(text.lstrip()), target_text.strip(), len(target_text) - len(target_text.lstrip()),
                         attribution="direct_clause", speaker_source="unit_speaker",
                         text_view_id=act_view_id, text_offset=len(text) - len(text.lstrip()), binding_view_id=binding_view_id,
                         matrix_subject=matrix_subject)
        elif continuation:
            span = (text.find(continuation), text.find(continuation) + len(continuation))
            append_claim(pos, "self", "own", continuation, p, True, span,
                         [e for e in source_evaluations if span[0] <= e.start < span[1]],
                         attribution="frame_continuation", speaker_source="unit_speaker",
                         text_view_id=act_view_id, text_offset=continuation_start, binding_view_id=act_view_id)
    claims = [replace(c, support_attribution=_support_attribution(c.active_adoption_event_ids, c.final_support)) for c in claims]
    by_claim = {c.claim_id: c for c in claims}
    evaluations = [replace(e, realization="actual", realization_source="self_reaffirmation", parent_event_id=reaffirmed[e.event_id])
                   if e.event_id in reaffirmed else e for e in evaluations]
    # 실제 동의로 채택한 전언의 내부 평가 명제는 자기 평가 근거다. 전언 표면은 surface_realization으로 남긴다.
    evaluations = [replace(e, realization="actual", realization_source="adopted_report_cue") if e.claim_id in by_claim
                   and by_claim[e.claim_id].kind == "reported" and by_claim[e.claim_id].final_support
                   and e.evidence_kind == "cue" and e.realization == "reported" else e for e in evaluations]
    evaluations = [replace(e, support_adoption_event_ids=by_claim[e.claim_id].active_adoption_event_ids,
                           final_support=(by_claim[e.claim_id].final_support and e.realization == "actual"
                                          and e.polarity == "positive")) if e.claim_id in by_claim else e for e in evaluations]
    applications = [replace(a, final_support=tuple(_NativeClaimState(cid, by_claim[cid].active_adoption_event_ids,
                                                                    by_claim[cid].final_support) for cid in a.target_claim_ids))
                    for a in applications]
    evaluations = [replace(e, support_attribution=_support_attribution(e.support_adoption_event_ids, e.final_support))
                   for e in evaluations]
    nodes, edges, failures = _native_graph(source_id, sources, claims, evaluations, assertions, applications)
    unit = unit_input if unit_input is not None else _NativeUnitInput()
    return _SpeakerLedger(source_id, tuple(sources), tuple(utts), tuple(claims), tuple(applications),
                          tuple(evaluations), tuple(assertions), native_version=_NATIVE_VERSION,
                          source_role=unit.source_role, speaker_unit_origin=unit.speaker_unit_origin, source_index=unit.source_index,
                          input_caller=unit.caller, input_alignment=alignment,
                          graph_nodes=nodes, graph_edges=edges, graph_failures=tuple(integrity) + failures)


# B33(F03): 바로 앞 절을 현재 자기 평가로 다시 단언하는 절. 지시 주어·자기 소유·평가 명사·긍정 계사와 현재 표지를 함께 요구한다.
_SELF_REAFFIRMATION = re.compile(
    r"(?:이는|이것은|이건|그것은|그건|이게|그게|(?:이|그)\s+(?:말|문장|문구|기록|평가|글)은)\s+(?:(?:지금|현재)(?:도)?\s+)?"
    r"(?:내|제|나의|저의)\s+(?:(?:현재|지금)(?:의)?\s+)?(?:평가|생각|의견|입장)(?:이)?(?:다|입니다|이다|예요|이에요|임)\s*[.!。~…]*")
_CURRENT_MARK = re.compile(r"현재|지금")


def _self_governed_report(text: str, event: "_EvaluationEvent", works: Sequence[str]) -> bool:
    """평가 술어가 인용 어미로 상위 기록·판단 술어에 걸렸고, 그 상위 술어가 화자 본인의 실제 긍정 행위인가(B33)."""
    tokens = list(_ACT_TOKEN.finditer(text))
    k = next((i for i, t in enumerate(tokens) if t.start() <= event.end - 1 < t.end()), None)
    if k is None or not _ACT_QUOTATIVE_END.search(tokens[k].group(0)):
        return False
    j = k + 1
    while j + 1 < len(tokens) and _object_gap_adverb(tokens[j].group(0)):
        j += 1
    if j >= len(tokens) or re.search(r"[.!?？。…;,，]", text[tokens[k].end():tokens[j].start()]):
        return False
    governor = tokens[j]
    if not (_GOVERNING_RECORD.match(governor.group(0)) or _GOVERNING_JUDGMENT.match(governor.group(0))):
        return False
    mode = _agreement_act_detail(text, governor.start(), governor.end())
    return mode.realization == "actual" and mode.polarity == "positive" and _clause_subject(text, governor.start(), works) == "self"


def native_evidence_ledger(parts: Sequence[str], works: Sequence[str] = (), *, source_id: str = "unit:0",
                           unit_input: Optional["_NativeUnitInput"] = None) -> _SpeakerLedger:
    """별도 관측 API. 제품과 같은 speaker pass의 후보·NP·주체·채택/철회 edge를 돌려준다. gold를 받지 않는다.

    B32: unit_input은 caller가 아는 역할·출처·원문 줄 metadata다. 없으면 NOT_OBSERVED로 남긴다. 공개 pass 자체의 원장은
    native_binder_capture로 같은 _Binder 객체에서 읽는다.
    """
    return _speaker_ledger(parts, works, source_id, unit_input)


def _speaker_utterances(parts: Sequence[str], works: Sequence[str] = ()) -> List[_Utterance]:
    return list(_speaker_ledger(parts, works).utterances)


def _speaker_units(parts: Sequence[str], works: Sequence[str] = ()) -> Tuple[List[str], List[str], List[str], List[str]]:
    """(채택된 직접 발화, 인용·전언 전체(부인·불확실 인용 제외), 채택된 인용·전언, 철회·반박으로 거둔 직접 발화의 원문 절)."""
    utts = _speaker_utterances(parts, works)
    own = [u.text for u in utts if u.kind == "own" and u.adopted]
    reported = [u.text for u in utts if u.kind == "reported"]
    endorsed = [u.text for u in utts if u.kind == "reported" and u.adopted]
    retracted = [u.source for u in utts if u.kind == "own" and not u.adopted]
    return own, reported, endorsed, retracted


_REPORTED_MARK = re.compile(r"라고|라며|전언|들었|친구|지인|소문|카더라|다더라|라더라|했대")
_BIND_REPORTED_TAIL = re.compile(r"(?:라고|라며|라더라|다더라|카더라|했대|하더라)\s*[.!?。~]*$")
_EXPERT_EXIST = re.compile(r"(?<!고\s)(?<!고)있(?:다|는|음|었|습|으|어)")
_EXPERT_NONEXIST = re.compile(r"없(?:다|는|음|었|습|으|이|어)")
_SRC_EXIST = re.compile(r"있")
_SRC_NONEXIST = re.compile(r"없")


def _content_tokens(text: str) -> set:
    out = set()
    for tok in re.findall(r"[가-힣A-Za-z0-9]{2,}", text):
        stem = _PARTICLES.sub("", tok)
        if len(stem) >= 2:
            out.add(stem)
    return out


def _stems(token: str) -> Tuple[str, ...]:
    seen = [token]
    frontier = [token]
    for _ in range(3):
        nxt = []
        for t in frontier:
            for e in _ENDINGS:
                if len(t) > len(e) and t.endswith(e):
                    c = t[: -len(e)]
                    if c not in seen and c not in nxt:
                        nxt.append(c)
        seen += nxt
        frontier = nxt
    return tuple(seen)


def _negated_at(text: str, start: int, end: int) -> bool:
    return bool(_NEG_AFTER.search(text[end:end + 12]) or _NEG_BEFORE.search(text[max(0, start - 4):start]))


def _cue_polarity(text: str) -> Set[str]:
    """태도 단서의 극성. 부정된 긍정 어근('좋지 않다', '안 좋다', '재미없다')은 부정 쪽, 부정된 부정 어근('싫지 않다')은 긍정 쪽이다."""
    pols: Set[str] = set()
    for m in _POS_CUE.finditer(text):
        negated = _negated_at(text, m.start(), m.end()) or bool(re.match(r"^[가-힣]{0,2}\s*없", text[m.end():]))
        pols.add("neg" if negated else "pos")
    for m in _NEG_CUE.finditer(text):
        pols.add("pos" if _negated_at(text, m.start(), m.end()) else "neg")
    if _SURPRISE_CUE.search(text):
        pols.add("surprise")
    return pols


_ASPECT_TOPIC = re.compile(r"(?:([가-힣A-Za-z0-9]{2,})['’\"”]?의\s*)?([가-힣A-Za-z0-9]+?)(?:에|을|를)?\s*(?:대해|대한|관해|관한)")


def _aspect_needle(aspect: str) -> str:
    """평가 항목의 원문 검색식. 사건 명사(죽음·희생)는 원문 단서 환언으로 찾는다."""
    return _aspect_needle_detail(aspect)[0]


def _aspect_needle_detail(aspect: str) -> Tuple[str, str]:
    """_aspect_needle의 검색식과 그 검색식을 고른 NP parser 분류(event_paraphrase / domain_item / literal_argument, B32)."""
    key = next((k for k in _PARAPHRASE if aspect.startswith(k) and k in _EVENT_PARAPHRASE), None)
    if key:
        return _PARAPHRASE[key], "event_paraphrase"
    if aspect in _DOMAIN_NOUNS:
        return _domain_item_pattern(aspect).pattern, "domain_item"
    return r"\s*".join(re.escape(ch) for ch in aspect), "literal_argument"


def _evaluation_segments(text: str) -> List[str]:
    """공동격 항목의 하고를 술어 연결 고로 잘라 태도·대상을 분리하지 않는다."""
    boundaries = list(re.finditer(r"[,，;]|(?:며|고|지만|는데|면서|으며)\s|\s/\s", text))
    result: List[str] = []
    start = 0
    for boundary in boundaries:
        word = re.search(r"[가-힣]+$", text[:boundary.start()])
        if boundary.group(0).startswith("고") and word and word.group(0).endswith("하"):
            item = word.group(0)[:-1]
            if item in _DOMAIN_NOUNS:
                continue
        result.append(text[start:boundary.start()])
        start = boundary.end()
    result.append(text[start:])
    return result


# 관형어는 흔한 관형형과 여러 음절 어미로만 판정한다(한 음절 어미 -은/-는/-한은 인명 하은·수인과 겹쳐 쓰지 않는다).
_ADNOMINAL_MODIFIER = re.compile(r"(?:로운|스러운|다운|적인|같은|없는|있는|좋은|나쁜|짧은|작은|슬픈|예쁜|멋진|이상한|황당한|허무한|완벽한|뻔한|새로운|놀라운)$")
_DETERMINERS = {"이번", "저번", "다음", "마지막", "첫", "새", "옛", "헌", "큰", "긴", "모든", "전체", "진짜", "그", "이", "저", "그런", "이런"}


def _owner_before(text: str, pos: int) -> Optional[str]:
    """항목 앞의 소유 작품·수식 명사('달빛기사의 결말', '달빛기사 결말', '달빛기사의 새로운 결말').

    항목 바로 앞의 관형어('새로운')·관형사('이번')는 최대 2개까지 건너뛰고 그 앞 어절을 본다.
    """
    prefix = text[:pos]
    for _ in range(2):
        m = re.search(r"([가-힣A-Za-z0-9]+)\s*$", prefix)
        if m and (m.group(1) in _DETERMINERS or (len(m.group(1)) >= 2 and _ADNOMINAL_MODIFIER.search(m.group(1))
                                                 and not m.group(1).endswith("의"))):
            prefix = prefix[:m.start()]
            continue
        break
    m = re.search(r"([가-힣A-Za-z0-9]+)(['’\"”]?)(의)?\s*$", prefix)
    if not m:
        return None
    tok = m.group(1)
    if m.group(3):
        pass  # 따옴표 속 소유격('은영'의)
    elif re.fullmatch(r"[가-힣](?:은|는)", tok):
        # 줄기가 한 음절인 '○은/○는'(지은·하은)은 조사 없이 쓴 이름으로 둔다. 주제어('나는')와 겹치면 더 엄격한 쪽(보류)으로 기운다.
        return tok
    elif len(tok) >= 3 and tok.endswith("의"):
        tok = tok[:-1]
    elif re.search(r"(?:은|는|이|가|을|를|에|에서|로|와|과|도|만)$", tok) or _BARE_VERBAL_TAIL.search(tok):
        return None
    if len(tok) < 2 or _is_meta(tok) or tok in _DEMONSTRATIVE_SUBJ:
        return None
    return tok


def _stance_aspects(body: str, start: int) -> List[Tuple[str, Optional[str]]]:
    """요지 태도어가 평가하는 (세부 항목, 소유 작품) 쌍. 가장 가까운 논항 있는 연결 절에서 찾는다."""
    bounds = [0] + [m.end() for m in _SEG_BOUNDARY.finditer(body, 0, start)] + [start]
    for b0, b1 in reversed(list(zip(bounds[:-1], bounds[1:]))):
        seg = body[b0:b1]
        subj, obj, dat = _args_in(seg)
        items = obj + dat + subj + [m.group(2) for m in _ASPECT_TOPIC.finditer(seg) if m.group(2)]
        g = re.search(r"([가-힣A-Za-z0-9]{2,})['’\"”]?의\s*$", seg)
        if g:
            items.append(g.group(1))
        items = [x for x in dict.fromkeys(items) if x and not _is_meta(x)]
        if not items:
            continue
        pairs = []
        for it in items:
            pos = seg.rfind(it)
            pairs.append((it, _owner_before(seg, pos) if pos >= 0 else None))
        owners = {o for _, o in pairs if o}
        return [(i, o) for i, o in pairs if i not in owners]
    return []


def _source_owner(seg: str, pos: int) -> Tuple[str, str]:
    """원문 항목 앞 소유자: ('explicit', 소유 명사) / ('deictic', 지시 구) / ('other_ref', '다른 작품') / ('omitted', '')."""
    kind, val, _ = _owner_phrase(re.findall(r"[가-힣A-Za-z0-9]+", seg[:pos]))
    if kind in ("deictic", "other_ref"):
        return kind, val
    # 공동격 항목의 뒤 항목은 앞 항목의 소유 작품을 공유한다. 공동격 표면을 작품명으로 보지 않는다.
    prefix = seg[:pos]
    coordinated = re.search(r"([가-힣]+?)(?:하고|이랑|랑|과|와)\s*$", prefix)
    if coordinated and coordinated.group(1) in _DOMAIN_NOUNS:
        return _source_owner(seg, coordinated.start())
    own = _owner_before(seg, pos)
    return ("explicit", own) if own else ("omitted", "")


def _implied_owner(seg: str, pos: int, live: Sequence[str], named: Sequence[str]) -> Optional[str]:
    """지시어·생략 소유자가 가리키는 작품. 같은 연결 절에서 항목 앞에 나온 작품 표면이 있으면 그것(현재 작품일 때만),
    없으면 그 화자 단위의 현재 작품이 하나일 때 그 작품이다. 둘 이상이거나 없으면 확인할 수 없다(None)."""
    spans = _work_spans(seg[:pos], named)
    if spans:
        s = max(spans, key=lambda x: x[1])[0]
        return s if s in live else None
    return live[0] if len(live) == 1 else None


def _target_in(seg: str, item: str, owner: Optional[str], live: Sequence[str] = (), named: Sequence[str] = ()) -> bool:
    """seg에 같은 항목이 있고, 원문의 소유 작품이 요지의 소유 작품과 같다고 확인되는가.

    명시 소유자는 같은 표면이어야 한다. 지시어('이 작품의 새로운 결말', '그 결말')와 생략('결말은 좋다')은 요지가 소유 작품을
    밝힌 경우 _implied_owner로 풀린 작품이 같을 때만 인정한다. 관계 미확정을 소유자 생략 허용으로 바꾸지 않는다.
    """
    for m in re.finditer(_aspect_needle(item), seg, re.I):
        kind, src = _source_owner(seg, m.start())
        if kind == "explicit":
            if owner and not _same_arg(owner, src):
                continue
            return True
        if not owner:
            return True
        if kind == "other_ref":
            continue
        resolved = _implied_owner(seg, m.start(), live, named)
        if resolved and _same_arg(owner, resolved):
            return True
    return False


# 직접 평가 술어. 동의 행위와 같은 완결 구성·성립 문맥·주체 판정을 거친 현재 실제 자기 평가만 태도 단서다.
_EVALUATION_LEXEME = re.compile(r"호평|극찬|칭찬|찬사|혹평|악평|비판|비난")
_EVALUATION_NEGATIVE = {"혹평", "악평", "비판", "비난"}
# 인용 보문(…좋다고)을 거느리는 상위 술어. 기록 술어는 늘 현재 평가가 아니고, 판단·발화 술어는 실제로 성립할 때만 평가다.
_GOVERNING_RECORD = re.compile(r"^(?:필사|베껴|베꼈|옮겨|옮겼|받아|적었|적어|적고|썼|써|쓴다|쓰고|기록|메모|필기)")
_GOVERNING_JUDGMENT = re.compile(r"^(?:평가|생각|판단|느끼|느낀|느꼈|본다|봤|보았|보고|여긴|여겼|믿|말하|말했|말한|말할|주장|언급)")


def _mask_spans(text: str, spans: Sequence[Tuple[int, int]]) -> str:
    out = list(text)
    for start, end in spans:
        out[start:end] = " " * (end - start)
    return "".join(out)


@dataclass(frozen=True)
class _NativeSubject:
    actor: str
    text: str
    span: Tuple[int, int]
    explicit: bool


@dataclass(frozen=True)
class _NativeObject:
    text: str
    span: Tuple[int, int]
    head: str
    head_span: Tuple[int, int]
    works: Tuple[str, ...]
    subaspects: Tuple[str, ...]
    speakers: Tuple[str, ...] = ()
    relation: str = "selects"
    parent_span: Tuple[int, int] = (-1, -1)
    # B32: NP parser가 실제로 쓴 분류·사전·근거 좌표·소유자·works 경로·부모 산출 여부·생성 경로. works는 기존 제약 표면 그대로다.
    object_kind: str = _NOT_OBSERVED
    object_kind_lexicons: Tuple[str, ...] = ()
    object_kind_evidence_span: Tuple[int, int] = (-1, -1)
    owner: str = ""
    owner_span: Tuple[int, int] = (-1, -1)
    works_source: str = _NOT_OBSERVED
    parent_status: str = _NOT_OBSERVED
    producer: str = _NOT_OBSERVED
    # B33: 소유자를 정한 parser 경로(stance_aspect_owner / coordinated_shared_owner / named_work_surface / speech_possessor).
    owner_source: str = _NOT_OBSERVED


@dataclass(frozen=True)
class _EvaluationEvent:
    source_id: str
    event_id: str
    parent_event_id: str
    start: int
    end: int
    predicate: str
    predicate_span: Tuple[int, int]
    actor: str
    grammatical_subject: _NativeSubject
    objects: Tuple[_NativeObject, ...]
    polarity: str
    evaluation_polarity: str
    realization: str
    assertion_span: Tuple[int, int]
    kind: str = "evaluate"
    evidence_kind: str = "lexical"
    speaker: str = "self"
    claim_id: str = ""
    evidence_text: str = ""
    support_adoption_event_ids: Tuple[str, ...] = ()
    final_support: bool = False
    surface_realization: str = "actual"
    evidence_offset: int = 0
    binding_text: str = ""
    binding_offset: int = 0
    # B32: 같은 판정의 시제 근거, 성립 문맥 출처·틀, 행위자 결정 경로·어절, 최종 근거 귀속, claim 부착, 실제 parser view ID.
    temporal_scope: str = _NOT_OBSERVED
    temporal_evidence_span: Tuple[int, int] = (-1, -1)
    realization_source: str = _NOT_OBSERVED
    realization_frame: str = _NOT_OBSERVED
    attribution: str = _NOT_OBSERVED
    attribution_evidence_span: Tuple[int, int] = (-1, -1)
    support_attribution: str = "none"
    claim_attachment: str = _NOT_OBSERVED
    evidence_view_id: str = ""
    binding_view_id: str = ""


@dataclass(frozen=True)
class _NativeSource:
    source_id: str
    parent_source_id: str
    clause_index: int
    text: str
    span: Tuple[int, int]
    # B32: caller가 넘긴 입력 역할·출처·원문 줄 좌표와 W13 split_clauses 반환 근거, parser가 실제로 읽은 view.
    source_role: str = _NOT_OBSERVED
    source_origin: str = _NOT_OBSERVED
    source_index: int = -1
    line_clause_index: int = -1
    raw_line: str = ""
    raw_span: Tuple[int, int] = (-1, -1)
    raw_boundary_proof: str = _NOT_OBSERVED
    parser_quotes: Tuple[Tuple[int, int], ...] = ()
    parser_terminal: str = ""
    parser_views: Tuple[_NativeParserView, ...] = ()
    # B33: caller carrier와 exact 대응한 원래 입력. source_index는 W13 정규화 뒤 index이고 original_index는 caller 원래 index다.
    # raw_text_offset은 정규화 줄이 caller raw_text에서 시작하는 위치(앞 공백 수), raw_text_span은 이 절의 caller raw_text 좌표다.
    original_index: int = -1
    raw_path: str = _NOT_OBSERVED
    selection_key: str = _NOT_OBSERVED
    raw_text_offset: int = -1
    raw_text_span: Tuple[int, int] = (-1, -1)
    line_occurrence: int = -1
    carrier_alignment: str = _NOT_OBSERVED


@dataclass(frozen=True)
class _NativeClaim:
    claim_id: str
    source_id: str
    parent_source_id: str
    utterance_index: int
    speaker: str
    kind: str
    text: str
    span: Tuple[int, int]
    grammatical_subject: _NativeSubject
    evaluation_event_ids: Tuple[str, ...]
    initial_support: bool
    active_adoption_event_ids: Tuple[str, ...]
    final_support: bool
    binding_text: str = ""
    binding_offset: int = 0
    # B32: 제품이 고른 귀속 경로·화자 결정 경로와 어절·인용 틀 판정·최종 근거 귀속과 claim 문장의 실제 view 좌표.
    attribution: str = _NOT_OBSERVED
    speaker_source: str = _NOT_OBSERVED
    attribution_evidence_span: Tuple[int, int] = (-1, -1)
    quote_frame_status: str = "not_quote"
    support_attribution: str = "none"
    text_view_id: str = ""
    text_offset: int = -1
    binding_view_id: str = ""


@dataclass(frozen=True)
class _NativeClaimState:
    claim_id: str
    adoption_event_ids: Tuple[str, ...]
    supported: bool


@dataclass(frozen=True)
class _NativeEventApplication:
    event: _BoundAgreementEvent
    target_claim_ids: Tuple[str, ...]
    target_adoption_event_ids: Tuple[str, ...]
    prior_adoption: Tuple[_NativeClaimState, ...]
    applied_effect: str
    after_application: Tuple[_NativeClaimState, ...]
    final_support: Tuple[_NativeClaimState, ...] = ()
    # B32: reducer가 대상 집합을 정한 경로, 적용 효과의 판단 이유, 적용 전후 상태가 실제로 바뀐 claim.
    reducer_target_source: str = _NOT_OBSERVED
    applied_effect_reason: str = _NOT_OBSERVED
    changed_claim_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _NativeAssertion:
    source_id: str
    event_id: str
    span: Tuple[int, int]
    grammatical_subject: _NativeSubject
    predicate: str
    predicate_span: Tuple[int, int]
    realization: str
    polarity: str


@dataclass(frozen=True)
class _SpeakerLedger:
    source_id: str
    sources: Tuple[_NativeSource, ...]
    utterances: Tuple[_Utterance, ...]
    claims: Tuple[_NativeClaim, ...]
    applications: Tuple[_NativeEventApplication, ...]
    evaluations: Tuple[_EvaluationEvent, ...]
    assertions: Tuple[_NativeAssertion, ...]
    schema: str = "context_projection_native_v31"
    # B32: 원형 schema 값은 그대로 두고 확장 판을 따로 적는다. caller 단위 metadata와 원장 ID graph.
    native_version: str = _NOT_OBSERVED
    source_role: str = _NOT_OBSERVED
    speaker_unit_origin: str = _NOT_OBSERVED
    source_index: int = -1
    input_caller: str = _NOT_OBSERVED
    input_alignment: str = _NOT_OBSERVED
    graph_nodes: Tuple[_NativeGraphNode, ...] = ()
    graph_edges: Tuple[_NativeGraphEdge, ...] = ()
    graph_failures: Tuple[str, ...] = ()


@dataclass(frozen=True)
class _NativeClauseInput:
    """caller가 아는 절 입력 metadata(B32). 좌표 증명이 없으면 raw_span=(-1, -1), raw_boundary_proof=NOT_OBSERVED다."""
    text: str
    source_role: str = _NOT_OBSERVED
    source_origin: str = _NOT_OBSERVED
    source_index: int = -1
    line_clause_index: int = -1
    raw_line: str = ""
    raw_span: Tuple[int, int] = (-1, -1)
    raw_boundary_proof: str = _NOT_OBSERVED
    parser_quotes: Tuple[Tuple[int, int], ...] = ()
    parser_terminal: str = ""
    # B33: caller carrier와 exact 대응한 원래 입력. source_index는 W13 정규화 뒤 index이고 original_index는 caller 원래 index다.
    # raw_text_offset은 정규화 줄이 caller raw_text에서 시작하는 위치(앞 공백 수), raw_text_span은 이 절의 caller raw_text 좌표다.
    original_index: int = -1
    raw_path: str = _NOT_OBSERVED
    selection_key: str = _NOT_OBSERVED
    raw_text_offset: int = -1
    raw_text_span: Tuple[int, int] = (-1, -1)
    line_occurrence: int = -1
    carrier_alignment: str = _NOT_OBSERVED


@dataclass(frozen=True)
class _NativeUnitInput:
    """화자 단위를 만든 caller의 metadata(B32). source ID 문자열에서 역할을 추론하지 않는다."""
    source_role: str = _NOT_OBSERVED
    speaker_unit_origin: str = _NOT_OBSERVED
    source_index: int = -1
    caller: str = _NOT_OBSERVED
    clauses: Tuple[_NativeClauseInput, ...] = ()


@dataclass(frozen=True)
class _NativeParserView:
    """parser가 실제로 읽은 절 view(B32). offset은 절 원문 좌표이고 view 문자열은 원문이 아니다."""
    view_id: str
    view_kind: str
    text: str
    offset: int
    masked_spans: Tuple[Tuple[int, int, str, str], ...] = ()


@dataclass(frozen=True)
class _NativeGraphNode:
    """원장 안에서 실제로 정의된 ID와 정의 위치(B32)."""
    node_id: str
    node_type: str
    defined_by: str


@dataclass(frozen=True)
class _NativeGraphEdge:
    """원장 필드가 기록한 ID 참조와 그 필드 위치(B32)."""
    source_id: str
    relation: str
    target_id: str
    recorded_by: str


# B32 신규 native 값의 선언 범위. 검증은 관측값이 이 선언 안에 있는지만 본다(검토기 추가 허용 없음).
_NATIVE_B32_ENUMS = {
    "source_role": ("author", "comment", "NOT_OBSERVED"),
    "source_origin": ("post_title", "body_line", "comment", "NOT_OBSERVED"),
    "speaker_unit_origin": ("post_title_and_body_lines", "comment_line", "NOT_OBSERVED"),
    "input_caller": ("_Binder.__init__", "external_caller", "NOT_OBSERVED"),
    "input_alignment": ("caller_clauses_equal_parts", "caller_clauses_differ_parts", "NOT_OBSERVED"),
    "raw_boundary_proof": ("exact_sequential_whitespace_gap", "NOT_OBSERVED"),
    "temporal_scope": ("past", "present_reaffirmed", "unmarked", "NOT_OBSERVED"),
    "agreement_realization_source": ("own_construction", "coordinated_with_following", "correction_marker_override", "NOT_OBSERVED"),
    "evaluation_realization_source": ("own_construction", "embedded_plan_noun_modal", "self_answer_assertion", "cue_token_construction",
                                      "governing_predicate", "governing_record_predicate", "embedded_hedge_current",
                                      "governed_cue_blocked", "rhetorical_or_hedged_current", "adopted_report_cue", "self_reaffirmation",
                                      "negated_experience_scope", "nominal_cue_observation", "nominal_judgment_content",
                                      "NOT_OBSERVED"),
    "realization_frame": ("clause", "quote_body", "NOT_OBSERVED"),
    "subject_source": ("clause_subject", "correction_unit_speaker_fixed", "evaluation_object_unit_speaker", "NOT_OBSERVED"),
    "evaluation_attribution": ("clause_subject_token", "clause_subject_unresolved", "clause_subject_default_self",
                               "governing_subject_token", "governing_subject_unresolved", "governing_subject_default_self",
                               "third_party_subject_token", "third_party_subject_unresolved", "third_party_subject_default_self",
                               "unit_speaker_default", "reported_claim_speaker", "NOT_OBSERVED"),
    "claim_attribution": ("direct_clause", "frame_continuation", "quote_self_affirmed", "quote_other_affirmed", "quote_denied",
                          "quote_uncertain", "report_clause_lead_report_speaker", "report_clause_reported_tail",
                          "report_clause_hearsay_tail", "report_clause_third_party_subject", "NOT_OBSERVED"),
    "speaker_source": ("unit_speaker", "quote_preceding_self_word", "quote_preceding_subject", "quote_following_speech_owner",
                       "quote_following_subject", "quote_default_other", "agreement_act_subject", "third_party_predicate_subject",
                       "evaluation_actor", "first_token_stem", "default_other", "quote_preceding_source_marker",
                       "quote_preceding_subject_after_topic", "NOT_OBSERVED"),
    "quote_frame_status": ("affirmed", "negated", "question", "conditional", "reported", "past", "contrast", "not_quote"),
    "support_attribution": ("unit_speaker_direct", "unit_speaker_adoption", "none"),
    "claim_attachment": ("claim", "unattached_third_party_clause", "NOT_OBSERVED"),
    "object_kind": ("agreement_noun", "speech_noun", "domain_item", "count_head", "multi_lexicon_head", "unlexicalized_head",
                    "event_paraphrase", "literal_argument", "named_work", "NOT_OBSERVED"),
    "object_kind_lexicons": ("_AGREEMENT_NOUNS", "_SPEECH_NOUNS", "_DOMAIN_NOUNS", "_NATIVE_COUNT_HEADS"),
    "works_source": ("named_work_in_span", "owner_not_named_work", "none", "NOT_OBSERVED"),
    "parent_status": ("bounded_object_tokens", "evaluation_argument_phrase", "NOT_OBSERVED"),
    "object_producer": ("agreement_object_tokens", "evaluation_stance_aspect", "NOT_OBSERVED"),
    "withdrawal_scope": ("not_withdrawal", "agreement_object_targets", "previous_adoption_by_correction",
                         "own_agreement_previous_adoption", "unrelated_agreement_noun", "agreement_noun_complement_prior_adoptions",
                         "embedded_agreement_statement_prior_adoptions", "own_evaluation_prior_claims", "unrelated_evaluation_noun",
                         "constrained_object_targets", "all_prior_adopted", "previous_adoption_by_deictic_speech", "NOT_OBSERVED"),
    "reducer_target_source": ("event_targets", "all_prior_reported_fallback", "NOT_OBSERVED"),
    "applied_effect_reason": ("event_effect_applied", "no_event_effect", "adopt_subject_not_self",
                              "no_object_targets_previously_rejected", "NOT_OBSERVED"),
    "view_kind": ("raw_clause", "act_masked", "binding_masked", "quote_body"),
    "mask_role": ("reported_utterance", "nominal_argument", "display_label", "connected_action", "recorded_content"),
    "mask_replacement": ("space", "placeholder"),
    "graph_node_type": ("unit", "source", "claim", "direct_support", "evaluation", "assertion", "application_event"),
    "graph_relation": ("source_in_unit", "claim_in_source", "direct_support_of", "claim_evaluation", "claim_active_support",
                       "evaluation_in_source", "evaluation_parent", "evaluation_claim", "evaluation_support",
                       "assertion_in_source", "application_in_source", "application_target_claim",
                       "application_target_adoption", "event_target_event"),
    "graph_failure_prefix": ("UNKNOWN_REFERENCE", "DUPLICATE_DEFINITION", "ID_COLLISION"),
    # B31 필드 target_relation의 실제 코드 범위를 선언으로 남긴다(targets_utterance 또는 결속 이유).
    "target_relation": ("targets_utterance", "speech", "speaker", "work", "no_object", "none", "ambiguous", "ambiguous_speaker",
                        "ambiguous_work", "ambiguous_item", "unrelated", "unknown_speaker", "no_match", "previous_adoption",
                        "prior_adopted"),
    # B33 추가 선언(typed input·결속 proof·projection channel 출처). 끝이 *인 값은 접두 선언이다.
    "owner_source": ("stance_aspect_owner", "coordinated_shared_owner", "named_work_surface", "speech_possessor",
                     "speech_work_content", "none", "NOT_OBSERVED"),
    "carrier_alignment": ("exact_enumeration", "carrier_differs_source", "NOT_OBSERVED"),
    "caller_disposition": ("passed_to_source", "dropped_comment_cap", "dropped_non_text_block", "dropped_empty_by_caller"),
    "dropped_reason": ("dropped_comment_cap", "dropped_non_text_block", "dropped_empty_by_caller", "w13_empty_after_strip",
                       "unknown_origin"),
    "core_decision": ("kept", "held", "dropped", "skipped_length", "not_evaluated_after_two_kept"),
    "core_projection_field": ("core_meaning", "held_meaning", ""),
    "capture_status": ("single_binder", "binder_count_*"),
    "speaker_route": ("author_unit", "comment_units", "joint_author_and_comment_units", ""),
    "window_selection": ("author_first_person", "author_reported_by_summary_marker", "comment_adopted_unit"),
    "window_usage": ("endorsed_assertion", "attribution_only"),
    "window_why": ("own_claim_final_support", "reported_claim_adopted_final_support", "comment_claim_adopted",
                   "summary_reported_marker:*"),
    "window_modality": ("assertive", "question", "uncertain", "rhetorical"),
    "modality_basis": ("no_touched_window", "assertive_source", "uncertain_source_with_uncertain_summary",
                       "uncertain_source_without_uncertain_summary", "not_reached"),
    "token_location": ("clause", "title", "unlocated"),
    "claim_lifecycle": ("own_current", "own_withdrawn", "report_adopted_current", "report_adoption_withdrawn",
                        "report_not_adopted", "quote_denied", "quote_uncertain", "NOT_OBSERVED"),
    "stance_basis": ("lexical_event", "cue_event", "cue_lexicon", "stance_lexicon"),
    "stance_support_mode": ("actual_final_support", "uncertain_claim_supported", "lexicon_only"),
    "stance_scope": ("summary_window", "joint_comment_unit"),
    "channel": ("speech_act", "target", "request_condition", "reference_work", "excluded_work", "work_role", "media",
                "work_relation"),
    "channel_value_kind": ("parser_label", "author_clause_quote", "source_surface", "derived_relation"),
    "channel_rule": ("evaluation_question_named_work", "recommendation_request", "question_named_work",
                     "evaluation_question_author_target", "question_author_target",
                     "evaluation_question_author_new_work", "question_author_new_work", "opinion_author_new_work",
                     "evaluation_question_work_new_work", "question_work_new_work", "opinion_work_new_work",
                     "evaluation_question_evaluated_item", "question_title_identification", "question_cue_kind",
                     "joke_discourse_intent", "opinion_named_work", "opinion_cue_kind", "unknown",
                     "other_media_from_target_media", "author_clauses_first_six", "comparison_token", "already_read",
                     "not_this", "media_predicate", "media_topic", "media_locative", "relation_representative_occurrence",
                     "trace_missing", "NOT_OBSERVED"),
    "location_kind": ("author_clause", "title_line"),
    "author_clause_transform": ("identity", "reported_quote_removed", "app_tail_removed", "reported_quote_and_app_tail_removed"),
    "author_clause_removed": ("reported_quote", "app_tail"),
    "author_clause_skip": ("empty_after_removal", "reported_speaker_lead", "reported_tail", "unasserted_author_clause"),
    "author_clause_alignment": ("records_equal_clauses", "records_differ_clauses", "NOT_OBSERVED"),
}
_NATIVE_COUNT_HEADS = {"개", "건"}


def _native_lexicons(stem: str) -> Tuple[str, ...]:
    """NP 머리 줄기가 든 parser 사전 이름(B32, 판정 순서 고정)."""
    table = (("_AGREEMENT_NOUNS", _AGREEMENT_NOUNS), ("_SPEECH_NOUNS", _SPEECH_NOUNS),
             ("_DOMAIN_NOUNS", _DOMAIN_NOUNS), ("_NATIVE_COUNT_HEADS", _NATIVE_COUNT_HEADS))
    return tuple(name for name, lexicon in table if stem in lexicon)


def _native_head_kind(lexicons: Sequence[str]) -> str:
    """동의 목적어 NP 머리가 든 사전으로 정한 object_kind(B32). 여러 사전에 들면 따로 표시한다."""
    if len(lexicons) > 1:
        return "multi_lexicon_head"
    if not lexicons:
        return "unlexicalized_head"
    return {"_AGREEMENT_NOUNS": "agreement_noun", "_SPEECH_NOUNS": "speech_noun",
            "_DOMAIN_NOUNS": "domain_item", "_NATIVE_COUNT_HEADS": "count_head"}[lexicons[0]]


def _actor_attribution(route: str, actor: str, span: Tuple[int, int]) -> str:
    """행위자 판정 경로와 결정 어절 유무(B32). 결정 어절이 없으면 기본 자기 주체 또는 미확정이다."""
    if span != (-1, -1):
        return route + "_token"
    if actor in ("unknown", ""):
        return route + "_unresolved"
    return route + "_default_self"


def _support_attribution(ids: Sequence[str], supported: bool) -> str:
    """최종 근거의 귀속(B32). 채택 사건 ID가 있으면 화자 단위의 채택, direct만 있으면 직접 발화다."""
    if not supported:
        return "none"
    return "unit_speaker_adoption" if any(not value.endswith(":direct") for value in ids) else "unit_speaker_direct"


def _native_boundary_spans(line: str, texts: Sequence[str]) -> List[Tuple[Tuple[int, int], str]]:
    """절 문자열의 원문 줄 좌표(B32). 앞 절 끝부터 공백만 건너 정확히 이어질 때만 좌표를 두고, 한 번 끊기면 뒤도 미관측이다."""
    out: List[Tuple[Tuple[int, int], str]] = []
    cursor, broken = 0, False
    for text in texts:
        start = -1 if broken or not text else line.find(text, cursor)
        if start < 0 or line[cursor:start].strip():
            broken = True
            out.append(((-1, -1), _NOT_OBSERVED))
            continue
        out.append(((start, start + len(text)), "exact_sequential_whitespace_gap"))
        cursor = start + len(text)
    return out


def _native_line_inputs(line: str, role: str, origin: str, index: int, line_origin: Optional["NativeLineOrigin"] = None,
                        alignment: str = _NOT_OBSERVED) -> List[_NativeClauseInput]:
    """한 입력 줄에 대한 split_clauses 입력·반환 근거와 원문 줄 좌표(B32). 빈 절은 caller와 같이 뺀다.

    B33: line_origin은 같은 caller carrier와 exact 대응한 원래 입력이다. 있으면 원래 index·경로·선택 key·앞 공백 수와
    caller raw_text 안 절 좌표(raw_span + 앞 공백 수)를 함께 남긴다. 없으면 NOT_OBSERVED다.
    """
    kept = [(k, clause) for k, clause in enumerate(split_clauses(line)) if clause.text.strip()]
    spans = _native_boundary_spans(line, [clause.text for _, clause in kept])
    out: List[_NativeClauseInput] = []
    for (k, clause), (span, proof) in zip(kept, spans):
        extra: dict = {"carrier_alignment": alignment}
        if line_origin is not None:
            offset = line_origin.leading_trim_count
            extra.update(original_index=line_origin.original_index, raw_path=line_origin.raw_path,
                         selection_key=line_origin.selection_key, raw_text_offset=offset, line_occurrence=line_origin.occurrence,
                         raw_text_span=(span[0] + offset, span[1] + offset) if span != (-1, -1) else (-1, -1))
        out.append(_NativeClauseInput(clause.text, role, origin, index, k, line, span, proof, tuple(clause.quotes), clause.terminal,
                                      **extra))
    return out


def _manifest_lookup(manifest: Optional["NativeSourceManifest"]) -> Tuple[dict, str]:
    """manifest의 (origin, W13 정규화 index) 대응표와 대응 상태(B33). manifest가 없으면 NOT_OBSERVED다."""
    if manifest is None:
        return {}, _NOT_OBSERVED
    return {(o.origin, o.normalized_index): o for o in manifest.lines}, manifest.alignment


def _native_author_input(source: ClaimScopeSource, caller: str = "external_caller",
                         manifest: Optional["NativeSourceManifest"] = None) -> _NativeUnitInput:
    """작성자 단위(제목·본문 줄)의 caller metadata(B32). ClaimScopeSource.post_lines와 같은 순서·빈 줄 필터다.
    B33: manifest가 exact 대응이면 줄마다 caller의 원래 입력을 붙인다."""
    lookup, alignment = _manifest_lookup(manifest)
    clauses: List[_NativeClauseInput] = []
    if source.post_title:
        clauses += _native_line_inputs(source.post_title, "author", "post_title", 0, lookup.get(("post_title", 0)), alignment)
    for index, line in enumerate(source.body_lines):
        if line:
            clauses += _native_line_inputs(line, "author", "body_line", index, lookup.get(("body_line", index)), alignment)
    return _NativeUnitInput("author", "post_title_and_body_lines", -1, caller, tuple(clauses))


def _native_comment_input(line: str, index: int, caller: str = "external_caller",
                          manifest: Optional["NativeSourceManifest"] = None) -> _NativeUnitInput:
    """댓글 한 개 단위의 caller metadata(B32). index는 W13 정규화 뒤 댓글 index이고, 원래 index는 manifest에서 붙인다(B33)."""
    lookup, alignment = _manifest_lookup(manifest)
    return _NativeUnitInput("comment", "comment_line", index, caller,
                            tuple(_native_line_inputs(line, "comment", "comment", index, lookup.get(("comment", index)), alignment)))


def _native_source(clause_id: str, source_id: str, pos: int, text: str, clause_input: Optional[_NativeClauseInput],
                   views: Tuple[_NativeParserView, ...]) -> _NativeSource:
    """절 기록. caller metadata가 없으면 입력 필드는 NOT_OBSERVED 기본값이다(B32)."""
    if clause_input is None:
        return _NativeSource(clause_id, source_id, pos, text, (0, len(text)), parser_views=views)
    return _NativeSource(clause_id, source_id, pos, text, (0, len(text)), source_role=clause_input.source_role,
                         source_origin=clause_input.source_origin, source_index=clause_input.source_index,
                         line_clause_index=clause_input.line_clause_index, raw_line=clause_input.raw_line,
                         raw_span=clause_input.raw_span, raw_boundary_proof=clause_input.raw_boundary_proof,
                         parser_quotes=clause_input.parser_quotes, parser_terminal=clause_input.parser_terminal,
                         parser_views=views, original_index=clause_input.original_index, raw_path=clause_input.raw_path,
                         selection_key=clause_input.selection_key, raw_text_offset=clause_input.raw_text_offset,
                         raw_text_span=clause_input.raw_text_span, line_occurrence=clause_input.line_occurrence,
                         carrier_alignment=clause_input.carrier_alignment)


def _native_graph(source_id: str, sources: Sequence[_NativeSource], claims: Sequence[_NativeClaim],
                  evaluations: Sequence[_EvaluationEvent], assertions: Sequence[_NativeAssertion],
                  applications: Sequence[_NativeEventApplication]
                  ) -> Tuple[Tuple[_NativeGraphNode, ...], Tuple[_NativeGraphEdge, ...], Tuple[str, ...]]:
    """원장이 정의한 ID와 필드 참조의 graph(B32). 같은 ID의 반복 정의·다른 정의와 없는 대상 참조를 실패로 남긴다."""
    defined: dict = {}
    nodes: List[_NativeGraphNode] = []
    edges: List[_NativeGraphEdge] = []
    failures: List[str] = []

    def define(node_id: str, node_type: str, defined_by: str, content: Any) -> None:
        if node_id in defined:
            prefix = "DUPLICATE_DEFINITION:" if defined[node_id] == (node_type, content) else "ID_COLLISION:"
            failures.append(prefix + node_type + ":" + node_id)
            return
        defined[node_id] = (node_type, content)
        nodes.append(_NativeGraphNode(node_id, node_type, defined_by))

    def link(source: str, relation: str, target: str, recorded_by: str) -> None:
        edges.append(_NativeGraphEdge(source, relation, target, recorded_by))
        if target not in defined:
            failures.append(f"UNKNOWN_REFERENCE:{relation}:{source}->{target}")

    define(source_id, "unit", "source_id", source_id)
    for i, s in enumerate(sources):
        define(s.source_id, "source", f"sources[{i}].source_id", s)
    for i, c in enumerate(claims):
        define(c.claim_id, "claim", f"claims[{i}].claim_id", c)
        if c.initial_support:
            define(c.claim_id + ":direct", "direct_support", f"claims[{i}].initial_support", c.claim_id)
    for i, e in enumerate(evaluations):
        define(e.event_id, "evaluation", f"evaluations[{i}].event_id", e)
    for i, a in enumerate(assertions):
        define(a.event_id, "assertion", f"assertions[{i}].event_id", a)
    for i, a in enumerate(applications):
        define(a.event.event_id, "application_event", f"applications[{i}].event.event_id", a.event)
    for i, s in enumerate(sources):
        link(s.source_id, "source_in_unit", s.parent_source_id, f"sources[{i}].parent_source_id")
    for i, c in enumerate(claims):
        link(c.claim_id, "claim_in_source", c.source_id, f"claims[{i}].source_id")
        if c.initial_support:
            link(c.claim_id + ":direct", "direct_support_of", c.claim_id, f"claims[{i}].initial_support")
        for k, value in enumerate(c.evaluation_event_ids):
            link(c.claim_id, "claim_evaluation", value, f"claims[{i}].evaluation_event_ids[{k}]")
        for k, value in enumerate(c.active_adoption_event_ids):
            link(c.claim_id, "claim_active_support", value, f"claims[{i}].active_adoption_event_ids[{k}]")
    for i, e in enumerate(evaluations):
        link(e.event_id, "evaluation_in_source", e.source_id, f"evaluations[{i}].source_id")
        link(e.event_id, "evaluation_parent", e.parent_event_id, f"evaluations[{i}].parent_event_id")
        if e.claim_id:
            link(e.event_id, "evaluation_claim", e.claim_id, f"evaluations[{i}].claim_id")
        for k, value in enumerate(e.support_adoption_event_ids):
            link(e.event_id, "evaluation_support", value, f"evaluations[{i}].support_adoption_event_ids[{k}]")
    for i, a in enumerate(assertions):
        link(a.event_id, "assertion_in_source", a.source_id, f"assertions[{i}].source_id")
    for i, a in enumerate(applications):
        event_id = a.event.event_id
        link(event_id, "application_in_source", a.event.source_id, f"applications[{i}].event.source_id")
        for k, value in enumerate(a.target_claim_ids):
            link(event_id, "application_target_claim", value, f"applications[{i}].target_claim_ids[{k}]")
        for k, value in enumerate(a.target_adoption_event_ids):
            link(event_id, "application_target_adoption", value, f"applications[{i}].target_adoption_event_ids[{k}]")
        for k, value in enumerate(a.event.target_event_ids):
            link(event_id, "event_target_event", value, f"applications[{i}].event.target_event_ids[{k}]")
    return tuple(nodes), tuple(edges), tuple(failures)


@dataclass(frozen=True)
class NativeRawLine:
    """caller가 원문 container에서 열거한 입력 한 개(B33 typed input). W13 strip·빈 값 제거 전 값이다.

    origin은 post_title / body_line / comment다. original_index는 원래 container index(제목은 0)이고, raw_path·selection_key·
    raw_text는 caller가 실제로 읽은 경로·key·문자열(strip 전)이다. caller_disposition은 W13 전에 caller가 내린 처리다
    (passed_to_source / dropped_comment_cap / dropped_non_text_block / dropped_empty_by_caller). B는 경로를 해석하지 않는다.
    """
    origin: str
    original_index: int
    raw_path: str
    selection_key: str
    raw_text: str
    caller_disposition: str = "passed_to_source"


@dataclass(frozen=True)
class NativeSourceCarrier:
    """같은 caller가 ClaimScopeSource를 만들 때 쓴 원문 입력 전체(B33). lines 순서는 caller의 열거 순서다."""
    caller: str
    lines: Tuple[NativeRawLine, ...] = ()


@dataclass(frozen=True)
class NativeLineOrigin:
    """W13 정규화 줄 하나와 caller 원래 입력의 exact 대응(B33).

    normalized_index는 ClaimScopeSource 안 index(native source_index와 같은 기준)이고 original_index는 caller 원래 container
    index다. 둘을 섞지 않는다. normalized_raw_span은 raw_text 좌표의 [시작, 끝)이며 raw_text[시작:끝] == normalized_text다.
    leading_trim_count·trailing_trim_count는 앞뒤에서 지운 공백 문자 수다(끝점이 아니다). occurrence는 같은 origin 안에서
    같은 정규화 문자열의 몇 번째 출현인지(0부터)다.
    """
    origin: str
    normalized_index: int
    original_index: int
    raw_path: str
    selection_key: str
    raw_text: str
    normalized_text: str
    normalized_raw_span: Tuple[int, int]
    leading_trim_count: int
    trailing_trim_count: int
    occurrence: int


@dataclass(frozen=True)
class NativeDroppedLine:
    """W13 source에 들어가지 않은 caller 입력과 그 이유(B33)."""
    origin: str
    original_index: int
    raw_path: str
    selection_key: str
    raw_text: str
    reason: str


@dataclass(frozen=True)
class NativeSourceManifest:
    """carrier와 ClaimScopeSource의 대응 결과(B33). alignment가 carrier_differs_source면 lines는 비고 mismatch가 첫 이유다."""
    caller: str
    alignment: str
    lines: Tuple[NativeLineOrigin, ...] = ()
    dropped: Tuple[NativeDroppedLine, ...] = ()
    mismatch: str = ""


@dataclass(frozen=True)
class NativeSignalOrigin:
    """caller가 ExpertSignals 필드 하나에 넣은 값의 전문가 enum·실제 dict 경로·선택 분기(B33).

    branch는 nested / root / root_empty_nested_fallback / missing처럼 caller가 실제로 고른 분기다. B는 값 동일성만 검사하고
    경로를 추론하거나 채우지 않는다.
    """
    field: str
    expert: str
    path: str
    branch: str
    value: Any = None


@dataclass(frozen=True)
class NativeSignalOriginCheck:
    origin: NativeSignalOrigin
    field_known: bool
    value_equal: bool


@dataclass(frozen=True)
class NativeAuthorClause:
    """_author_clauses가 돌려준 작성자 소유 절 하나와 그 실제 원문 좌표(B33).

    clause_index는 _author_clauses 반환 순서이며 request_conditions index와 같은 기준이다. text는 그 반환 문자열이다. 인용 조사가
    붙은 인용문(_QUOTED)과 앱 꼬리(_APP_TAIL)를 지우고 strip한 값이라 원문 절(clause_text)과 다를 수 있다. text_runs는
    (text 시작, clause_text 시작, 길이) 연속 구간이다. text가 원문 절의 한 연속 구간일 때만 text_line_span(W13 정규화 줄 좌표)과
    text_raw_span(caller raw_text 좌표)이 관측된다. removed_spans는 clause_text 좌표의 지운 구간과 이유다.
    """
    clause_index: int
    text: str
    source_origin: str
    source_index: int
    line_clause_index: int
    clause_text: str
    clause_line_span: Tuple[int, int]
    raw_boundary_proof: str
    transform: str
    removed_spans: Tuple[Tuple[int, int, str], ...]
    text_runs: Tuple[Tuple[int, int, int], ...]
    text_line_span: Tuple[int, int]
    original_index: int = -1
    raw_path: str = _NOT_OBSERVED
    selection_key: str = _NOT_OBSERVED
    text_raw_span: Tuple[int, int] = (-1, -1)
    line_occurrence: int = -1
    carrier_alignment: str = _NOT_OBSERVED


@dataclass(frozen=True)
class NativeAuthorClauseSkip:
    """_author_clauses가 작성자 소유 절에서 뺀 원문 절과 그 이유(B33)."""
    source_origin: str
    source_index: int
    line_clause_index: int
    clause_text: str
    text: str
    reason: str


@dataclass(frozen=True)
class NativeSourceLocation:
    """projection 값이 실제로 나온 원문 위치(B33).

    kind가 author_clause면 clause_index는 NativeAuthorClause index이고 span은 그 절 text 좌표다. kind가 title_line이면
    _speech_act가 대상 표면을 제목 줄(source.post_lines[0], 작성자 소유 필터 전)에서 찾은 경우이며 clause_index는 -1, span은
    그 정규화 줄 좌표다. line_span은 W13 정규화 줄 좌표, raw_text_span은 caller raw_text 좌표다. 인용 제거로 끊긴 구간이거나
    manifest가 exact가 아니면 (-1, -1)이다.
    """
    kind: str
    clause_index: int
    span: Tuple[int, int]
    source_origin: str
    source_index: int
    line_span: Tuple[int, int]
    raw_text_span: Tuple[int, int]
    original_index: int = -1
    raw_path: str = _NOT_OBSERVED
    selection_key: str = _NOT_OBSERVED
    carrier_alignment: str = _NOT_OBSERVED


@dataclass(frozen=True)
class NativeChannelValue:
    """공개 ContextProjection의 원문 기반 값 하나와 그 producer(B33). 생성 요지(core_meaning·held_meaning)는 여기 없다.

    value_kind는 parser_label(분류 표지, 원문 아님) / author_clause_quote(작성자 소유 절 문자열 그대로, 생성 요지 아님) /
    source_surface(원문 표면, 작품 공식 권한 아님) / derived_relation(관계표 행)이다. value는 그 필드의 실제 값이다.
    """
    channel: str
    field: str
    index: int
    value: Any
    value_kind: str
    rule: str
    locations: Tuple[NativeSourceLocation, ...] = ()


@dataclass(frozen=True)
class NativeLifecycleEvent:
    """claim 하나에 적용된 동의·철회 적용 하나(B33). 원장 applications의 같은 기록에서 옮긴다."""
    event_id: str
    applied_effect: str
    applied_effect_reason: str
    supported_before: bool
    supported_after: bool


@dataclass(frozen=True)
class NativeSupportClaim:
    """결속 창 하나를 만든 실제 원장 claim과 그 현재 상태·이력(B33).

    claimant는 claim 내용의 발화자(claim.speaker, 화자 단위 본인이면 self)다. lifecycle은 own_current / own_withdrawn /
    report_adopted_current / report_adoption_withdrawn / report_not_adopted / quote_denied / quote_uncertain이다.
    source_*는 그 claim이 있는 원문 절의 caller 좌표다. span은 절 좌표이며 caller raw 좌표가 아니다.
    """
    claim_id: str
    source_id: str
    span: Tuple[int, int]
    kind: str
    claimant: str
    speaker_source: str
    attribution: str
    initial_support: bool
    final_support: bool
    active_adoption_event_ids: Tuple[str, ...]
    lifecycle: str
    lifecycle_events: Tuple[NativeLifecycleEvent, ...]
    source_origin: str = _NOT_OBSERVED
    source_index: int = -1
    original_index: int = -1
    raw_path: str = _NOT_OBSERVED
    selection_key: str = _NOT_OBSERVED
    source_raw_text_span: Tuple[int, int] = (-1, -1)
    carrier_alignment: str = _NOT_OBSERVED


@dataclass(frozen=True)
class NativeTokenLocation:
    """요지 결속 어절 하나를 창의 어디에서 찾았는지(B33). claim_ids는 그 위치의 실제 claim이다."""
    token: str
    location: str
    claim_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeSupportWindow:
    """Binder가 요지 하나에 쓴 결속 창 하나(B33). window_index는 bind의 창 순서다.

    selection은 창을 만든 Binder 목록(author_first_person / author_reported_by_summary_marker / comment_adopted_unit)이고
    claim은 그 목록 항목을 만든 실제 claim 하나다. usage가 endorsed_assertion이면 claim은 화자 단위 본인의 현재 주장(직접 발화
    또는 채택한 전언)이다. attribution_only면 요지에 전언 표지가 있어 전언 claim을 그대로 넣은 창이다. 이때 final_support는
    거짓일 수 있으며, 작성자의 현재 동의로 읽으면 안 된다. why는 선택 근거이고 window_modality는 Binder 양태 검사와 같은 판정이다.
    token_complete가 참인 창만 결속 어절을 모두 담는다(태도 검사 범위).
    """
    window_index: int
    unit_kind: str
    unit_source_id: str
    selection: str
    usage: str
    why: str
    clause_text: str
    title_window: str
    window_modality: str
    token_complete: bool
    touched: bool
    token_locations: Tuple[NativeTokenLocation, ...]
    claim: Optional[NativeSupportClaim]
    title_claims: Tuple[NativeSupportClaim, ...] = ()


@dataclass(frozen=True)
class NativeStanceSupport:
    """태도 어절 하나를 지지한 실제 근거(B33).

    scope가 summary_window면 window_index는 NativeSupportWindow.window_index이고, joint_comment_unit이면 공동 귀속 검사에서
    지지한 댓글 단위 순번이다. window_claim_id는 그 창이나 댓글 단위의 claim이다. support_mode가 actual_final_support면 사건
    final_support가 참이다. uncertain_claim_supported는 요지가 불확실성을 밝혀 현재 claim의 질문·양태·내포 사건을 쓴 경우다(사건
    final_support 거짓). lexicon_only는 사건 없이 어휘 판정만 쓴 경우다.
    """
    stance_token: str
    group: str
    scope: str
    window_index: int
    basis: str
    support_mode: str
    unit_kind: str
    window_claim_id: str = ""
    event_id: str = ""
    claim_id: str = ""
    source_id: str = ""
    evidence_kind: str = ""
    predicate: str = ""
    predicate_span: Tuple[int, int] = (-1, -1)
    realization: str = ""
    actor: str = ""
    final_support: bool = False
    claim_final_support: bool = False


@dataclass(frozen=True)
class NativeBindProof:
    """Binder.bind_with_proof 한 번의 판정과 그 판정이 실제로 쓴 근거(B33).

    ok·why·count는 bind와 같다. speaker_route는 author_unit / comment_units / joint_author_and_comment_units이고,
    reported_marker·uncertainty_marker는 요지에서 찾은 실제 표지 문자열(없으면 "")이며, modality_basis는 양태 검사 경로다.
    unresolved는 원장 대응을 찾지 못한 항목이다. 비어 있지 않으면 proof가 완전하지 않다.
    """
    sentence: str
    ok: bool
    why: str
    count: int
    speaker_route: str
    reported_marker: str
    uncertainty_marker: str
    modality_basis: str
    bound_tokens: Tuple[str, ...]
    windows: Tuple[NativeSupportWindow, ...]
    stance_support: Tuple[NativeStanceSupport, ...]
    unresolved: Tuple[str, ...]


@dataclass(frozen=True)
class NativeCoreDecision:
    """_core_meaning이 생성 요지 문장 하나에 내린 실제 판정(B33).

    field·sentence_index는 split 전 원래 필드와 그 split 순번이고 raw_span은 그 필드 문자열 안 [시작, 끝)이다. decision은 kept /
    held / dropped / skipped_length / not_evaluated_after_two_kept다. kept·held면 projection_field·projection_index가 공개
    core_meaning·held_meaning의 위치다.
    """
    field: str
    sentence_index: int
    raw_sentence: str
    raw_span: Tuple[int, int]
    normalized_sentence: str
    decision: str
    reason: str
    scope_reason: str = ""
    bound_count: int = -1
    hedged_stripped: bool = False
    projection_field: str = ""
    projection_index: int = -1
    proof: Optional[NativeBindProof] = None


@dataclass
class NativeProjectionCollector:
    """project_context(..., native=...)에 넘기는 호출별 수집기(B33).

    호출마다 새 객체를 쓴다(재사용하면 ValueError). B가 같은 pass의 manifest·source·signals·RowState·Binder·요지 판정·작성자 절
    좌표·channel 출처를 채운다. 모듈 전역 상태를 쓰지 않으므로 병렬 처리에서 다른 호출과 섞이지 않는다.
    """
    carrier: Optional[NativeSourceCarrier] = None
    signal_origins: Tuple[NativeSignalOrigin, ...] = ()
    manifest: Optional[NativeSourceManifest] = None
    source: Any = None
    signals: Any = None
    state: Any = None
    binders: List[Any] = _dc_field(default_factory=list)
    decisions: List[NativeCoreDecision] = _dc_field(default_factory=list)
    author_clauses: Tuple[NativeAuthorClause, ...] = ()
    author_clause_skips: Tuple[NativeAuthorClauseSkip, ...] = ()
    author_clause_alignment: str = _NOT_OBSERVED
    channel_values: Tuple[NativeChannelValue, ...] = ()
    projection: Any = None
    calls: int = 0

    def result(self) -> "NativeProjectionResult":
        binder = self.binders[0] if len(self.binders) == 1 else None
        status = "single_binder" if binder is not None else f"binder_count_{len(self.binders)}"
        names = {f.name for f in _dc_fields(ExpertSignals)}
        checks = tuple(NativeSignalOriginCheck(o, o.field in names, o.field in names and getattr(self.signals, o.field) == o.value)
                       for o in self.signal_origins)
        decisions = list(self.decisions)
        seen = {(d.field, d.sentence_index) for d in decisions}
        if self.signals is not None:
            for field_name, raw in (("post_intent", self.signals.post_intent), ("synthesis_summary", self.signals.synthesis_summary)):
                text = str(raw or "")
                spans = _core_sentence_spans(text)
                for index, sentence in enumerate(_CORE_SENTENCE_SPLIT.split(text)):
                    if (field_name, index) not in seen:
                        decisions.append(NativeCoreDecision(field_name, index, sentence,
                                                            spans[index] if index < len(spans) else (-1, -1), "",
                                                            "not_evaluated_after_two_kept", ""))
        order = {"post_intent": 0, "synthesis_summary": 1}
        decisions.sort(key=lambda d: (order.get(d.field, 2), d.sentence_index))
        return NativeProjectionResult(
            projection=self.projection, source=self.source, signals=self.signals, state=self.state, binder=binder,
            author_ledger=binder.author_ledger if binder else None,
            comment_ledgers=tuple(ledger for _, ledger in binder.comment_ledgers) if binder else (),
            manifest=self.manifest, signal_origins=checks, core_decisions=tuple(decisions), author_clauses=self.author_clauses,
            author_clause_skips=self.author_clause_skips, author_clause_alignment=self.author_clause_alignment,
            channel_values=self.channel_values, capture_status=status)


@dataclass(frozen=True)
class NativeProjectionResult:
    """project_context_native 한 번의 결과(B33). projection·원장·판정·좌표는 같은 호출의 같은 객체에서 왔다."""
    projection: Any
    source: Any
    signals: Any
    state: Any
    binder: Any
    author_ledger: Any
    comment_ledgers: Tuple[Any, ...]
    manifest: Optional[NativeSourceManifest]
    signal_origins: Tuple[NativeSignalOriginCheck, ...]
    core_decisions: Tuple[NativeCoreDecision, ...]
    author_clauses: Tuple[NativeAuthorClause, ...]
    author_clause_skips: Tuple[NativeAuthorClauseSkip, ...]
    author_clause_alignment: str
    channel_values: Tuple[NativeChannelValue, ...]
    capture_status: str


_CORE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_CARRIER_ORIGINS = ("post_title", "body_line", "comment")


def _core_sentence_spans(text: str) -> Tuple[Tuple[int, int], ...]:
    """_CORE_SENTENCE_SPLIT.split 조각마다 원래 문자열의 [시작, 끝)(B33). 조각이 split 결과와 다르면 빈 tuple이다."""
    spans: List[Tuple[int, int]] = []
    cursor = 0
    for m in _CORE_SENTENCE_SPLIT.finditer(text):
        spans.append((cursor, m.start()))
        cursor = m.end()
    spans.append((cursor, len(text)))
    if [text[a:b] for a, b in spans] != _CORE_SENTENCE_SPLIT.split(text):
        return ()
    return tuple(spans)


def native_source_manifest(source: ClaimScopeSource, carrier: NativeSourceCarrier) -> NativeSourceManifest:
    """carrier의 원래 입력을 W13 ClaimScopeSource 줄과 exact 순서로 대응한다(B33).

    W13 from_parts와 같은 규칙(문자열 변환·strip·빈 값 제거)을 caller가 넘긴 raw_text에 적용해, 남은 순서가 source의 제목·본문·
    댓글과 정확히 같을 때만 줄마다 원래 index·경로·key·좌표·occurrence를 붙인다. 하나라도 다르면 대응 전체를 버리고 이유를
    남긴다. 전역 find나 내용 dedup으로 원래 index를 되찾지 않는다.
    """
    expected = {"post_title": [source.post_title] if source.post_title else [], "body_line": list(source.body_lines),
                "comment": list(source.comments)}
    groups: dict = {origin: [] for origin in _CARRIER_ORIGINS}
    dropped: List[NativeDroppedLine] = []
    for line in carrier.lines:
        text = str(line.raw_text or "")
        if line.origin not in groups:
            reason = "unknown_origin"
        elif line.caller_disposition != "passed_to_source":
            reason = line.caller_disposition
        elif not text.strip():
            reason = "w13_empty_after_strip"
        else:
            groups[line.origin].append((line, text))
            continue
        dropped.append(NativeDroppedLine(line.origin, line.original_index, line.raw_path, line.selection_key, text, reason))
    mismatch = next((f"{origin}:normalized_sequence_differs" for origin in _CARRIER_ORIGINS
                     if [text.strip() for _, text in groups[origin]] != expected[origin]), "")
    if mismatch:
        return NativeSourceManifest(carrier.caller, "carrier_differs_source", (), tuple(dropped), mismatch)
    lines: List[NativeLineOrigin] = []
    for origin in _CARRIER_ORIGINS:
        seen: dict = {}
        for k, (line, text) in enumerate(groups[origin]):
            normalized = text.strip()
            start, end = len(text) - len(text.lstrip()), len(text.rstrip())
            lines.append(NativeLineOrigin(origin, k, line.original_index, line.raw_path, line.selection_key, text, normalized,
                                          (start, end), start, len(text) - end, seen.get(normalized, 0)))
            seen[normalized] = seen.get(normalized, 0) + 1
    return NativeSourceManifest(carrier.caller, "exact_enumeration", tuple(lines), tuple(dropped))


def _title_line_key(source: ClaimScopeSource) -> Tuple[str, int]:
    """source.post_lines[0]의 (origin, W13 정규화 index)(B33). 제목이 비면 첫 본문 줄이다."""
    if source.post_title:
        return "post_title", 0
    return next((("body_line", k) for k, line in enumerate(source.body_lines) if line), ("", -1))


def _position_runs(positions: Sequence[int]) -> Tuple[Tuple[int, int, int], ...]:
    """text 문자마다의 원래 절 위치를 (text 시작, 절 시작, 길이) 연속 구간으로 묶는다(B33)."""
    runs: List[Tuple[int, int, int]] = []
    for at, position in enumerate(positions):
        if runs and runs[-1][0] + runs[-1][2] == at and runs[-1][1] + runs[-1][2] == position:
            runs[-1] = (runs[-1][0], runs[-1][1], runs[-1][2] + 1)
        else:
            runs.append((at, position, 1))
    return tuple(runs)


def _map_text_span(runs: Sequence[Tuple[int, int, int]], start: int, end: int) -> Optional[Tuple[int, int]]:
    """text 좌표 [start, end)가 한 연속 구간 안에 있으면 원래 절 좌표를, 끊기면 None을 돌려준다(B33)."""
    for text_start, clause_start, length in runs:
        if text_start <= start < end <= text_start + length:
            return clause_start + start - text_start, clause_start + end - text_start
    return None


def _native_author_clause_records(source: ClaimScopeSource, clauses: Sequence[str], manifest: Optional[NativeSourceManifest]
                                  ) -> Tuple[Tuple[NativeAuthorClause, ...], Tuple[NativeAuthorClauseSkip, ...], str]:
    """_author_clauses와 같은 규칙(_author_line_clauses → _author_clause_cut: 인용 제거 → _APP_TAIL 제거 → strip → 전언 절 제외)을
    좌표와 함께 적는다(B33, R3 인용 범위 포함).

    결과 문자열 순서가 같은 pass의 clauses와 정확히 같을 때만 기록을 돌려준다. 다르면 모두 버리고 records_differ_clauses다.
    """
    lookup, carrier_alignment = _manifest_lookup(manifest)
    records: List[NativeAuthorClause] = []
    skips: List[NativeAuthorClauseSkip] = []
    for origin, index, line, parts, boundaries, prefix in _author_line_clauses(source):
        line_origin = lookup.get((origin, index))
        for k, (clause, (clause_span, boundary_proof), cut) in enumerate(zip(parts, boundaries, prefix)):
            raw = clause.text
            kept, quotes, tail, lead, end, text, reason = _author_clause_cut(raw, *cut, header=origin == "post_title")
            if reason:
                skips.append(NativeAuthorClauseSkip(origin, index, k, raw, text, reason))
                continue
            runs = _position_runs(kept[lead:end])
            removed = tuple((a, b, "reported_quote") for a, b in quotes)
            if tail:
                removed += ((kept[tail.start()], kept[-1] + 1, "app_tail"),)
            transform = ("reported_quote_and_app_tail_removed" if quotes and tail else "reported_quote_removed" if quotes
                         else "app_tail_removed" if tail else "identity")
            text_line_span = ((clause_span[0] + runs[0][1], clause_span[0] + runs[0][1] + runs[0][2])
                              if len(runs) == 1 and clause_span != (-1, -1) else (-1, -1))
            extra: dict = {"carrier_alignment": carrier_alignment}
            if line_origin is not None:
                offset = line_origin.leading_trim_count
                extra.update(original_index=line_origin.original_index, raw_path=line_origin.raw_path,
                             selection_key=line_origin.selection_key, line_occurrence=line_origin.occurrence,
                             text_raw_span=((text_line_span[0] + offset, text_line_span[1] + offset)
                                            if text_line_span != (-1, -1) else (-1, -1)))
            records.append(NativeAuthorClause(len(records), text, origin, index, k, raw, clause_span, boundary_proof, transform,
                                              removed, runs, text_line_span, **extra))
    if tuple(record.text for record in records) != tuple(clauses):
        return (), (), "records_differ_clauses"
    return tuple(records), tuple(skips), "records_equal_clauses"


def _native_channel_values(source: ClaimScopeSource, projection: "ContextProjection", records: Sequence[NativeAuthorClause],
                           manifest: Optional[NativeSourceManifest], act_trace: Optional[dict], kind_from_media: bool,
                           ref_trace: Optional[list], ex_trace: Optional[list], media_trace: Optional[dict],
                           relation_where: Sequence[Tuple[str, int, int, int]],
                           cond_trace: Optional[list] = None) -> Tuple[NativeChannelValue, ...]:
    """공개 projection의 원문 기반 channel 값마다 같은 pass의 producer 분기와 실제 원문 위치를 적는다(B33).

    작성자 절 기록(records)이 같은 pass clauses와 같을 때만 절 위치를 붙이고, 아니면 위치 없이 분기만 남긴다.
    core_meaning·held_meaning은 생성 요지라 여기 없고 NativeCoreDecision의 bind proof로 본다.
    """
    lookup, carrier_alignment = _manifest_lookup(manifest)
    title_key = _title_line_key(source)

    def raw_of(origin_key: Tuple[str, int], line_span: Tuple[int, int]):
        origin = lookup.get(origin_key)
        if origin is None or line_span == (-1, -1):
            return (-1, -1), origin
        return (line_span[0] + origin.leading_trim_count, line_span[1] + origin.leading_trim_count), origin

    def clause_location(ci: int, span: Optional[Tuple[int, int]] = None) -> Optional[NativeSourceLocation]:
        if not 0 <= ci < len(records):
            return None
        record = records[ci]
        span = (0, len(record.text)) if span is None else (span[0], span[1])
        mapped = _map_text_span(record.text_runs, span[0], span[1])
        line_span = ((record.clause_line_span[0] + mapped[0], record.clause_line_span[0] + mapped[1])
                     if mapped is not None and record.clause_line_span != (-1, -1) else (-1, -1))
        raw_span, origin = raw_of((record.source_origin, record.source_index), line_span)
        return NativeSourceLocation("author_clause", ci, span, record.source_origin, record.source_index, line_span, raw_span,
                                    origin.original_index if origin else -1, origin.raw_path if origin else _NOT_OBSERVED,
                                    origin.selection_key if origin else _NOT_OBSERVED, carrier_alignment)

    def title_location(span: Tuple[int, int]) -> NativeSourceLocation:
        span = (span[0], span[1])
        raw_span, origin = raw_of(title_key, span)
        return NativeSourceLocation("title_line", -1, span, title_key[0], title_key[1], span, raw_span,
                                    origin.original_index if origin else -1, origin.raw_path if origin else _NOT_OBSERVED,
                                    origin.selection_key if origin else _NOT_OBSERVED, carrier_alignment)

    values: List[NativeChannelValue] = []

    def add(channel: str, field_name: str, index: int, value: Any, value_kind: str, rule: str, locations=()) -> None:
        values.append(NativeChannelValue(channel, field_name, index, value, value_kind, rule,
                                         tuple(location for location in locations if location is not None)))

    act = act_trace or {}
    act_rule = act.get("rule", _NOT_OBSERVED)
    span_locations = [clause_location(act["span_index"])] if act.get("span_index", -1) >= 0 else []
    surface_locations = [clause_location(at, sp) if kind == "author_clause" else title_location(sp)
                         for kind, at, sp in act.get("surface_locations", ())]
    media = media_trace or {}
    media_rule = media.get("rule", _NOT_OBSERVED)
    media_word = [clause_location(media["span_index"], media["word_span"])] if "span_index" in media else []
    add("speech_act", "speech_act", -1, projection.speech_act, "parser_label", act_rule, span_locations)
    add("target", "target_kind", -1, projection.target_kind, "parser_label",
        "other_media_from_target_media" if kind_from_media else act_rule, media_word if kind_from_media else span_locations)
    if projection.target_surface is not None:
        add("target", "target_surface", -1, projection.target_surface, "source_surface", act_rule, surface_locations)
    if projection.target_span is not None:
        add("target", "target_span", -1, projection.target_span, "author_clause_quote", act_rule, span_locations)
    # B33 R3/R3d(E6): 조건은 작성자 절 중 고른 범위다. 같은 pass cond_trace의 (절 index, 시작, 끝)이 그 절 문자열에서 조건과 같으면
    # 그 범위를 쓰고, 없으면 같은 순서의 다음 같은 문자열 절을 찾는다.
    cursor = 0
    for i, condition in enumerate(projection.request_conditions):
        traced = cond_trace[i] if cond_trace is not None and i < len(cond_trace) else None
        if traced is not None and 0 <= traced[0] < len(records) and records[traced[0]].text[traced[1]:traced[2]] == condition:
            locations = [clause_location(traced[0], (traced[1], traced[2]))]
        else:
            at = next((k for k in range(cursor, len(records)) if records[k].text == condition), -1)
            if at >= 0:
                cursor = at + 1
            locations = [clause_location(at)] if at >= 0 else []
        add("request_condition", "request_conditions", i, condition, "author_clause_quote", "author_clauses_first_six", locations)
    ref_at = {entry[0]: entry for entry in ref_trace or ()}
    ex_at = {entry[0]: entry for entry in ex_trace or ()}

    def token_location(entry) -> list:
        return [clause_location(entry[2], (entry[3], entry[4]))] if entry else []
    for i, token in enumerate(projection.reference_works):
        entry = ref_at.get(token)
        add("reference_work", "reference_works", i, token, "source_surface", "comparison_token" if entry else "trace_missing",
            token_location(entry))
    for i, token in enumerate(projection.excluded_works):
        entry = ex_at.get(token)
        add("excluded_work", "excluded_works", i, token, "source_surface", entry[5] if entry else "trace_missing",
            token_location(entry))
    for i, row in enumerate(projection.work_roles):
        token, role, _ = row
        if role == "reference":
            entry = ref_at.get(token)
            add("work_role", "work_roles", i, row, "source_surface", "comparison_token" if entry else "trace_missing",
                token_location(entry))
        elif role == "excluded":
            entry = ex_at.get(token)
            add("work_role", "work_roles", i, row, "source_surface", entry[5] if entry else "trace_missing", token_location(entry))
        else:
            add("work_role", "work_roles", i, row, "source_surface", act_rule, surface_locations)
    if projection.target_media != "unknown":
        add("media", "target_media", -1, projection.target_media, "parser_label", media_rule, media_word)
    if projection.media_span is not None:
        add("media", "media_span", -1, projection.media_span, "author_clause_quote", media_rule,
            [clause_location(media["span_index"])] if "span_index" in media else [])
    for i, row in enumerate(projection.work_relation_evidence):
        where = relation_where[i] if i < len(relation_where) and relation_where[i][0] == row[0] else None
        add("work_relation", "work_relation_evidence", i, row, "derived_relation",
            "relation_representative_occurrence" if where else "trace_missing",
            [clause_location(where[1], (where[2], where[3]))] if where else [])
    return tuple(values)


def _claim_lifecycle(claim: Any, events: Sequence[NativeLifecycleEvent]) -> str:
    """claim 종류·최종 지지·적용 이력으로 정한 생애 상태(B33). 같은 원장 값에서만 읽는다."""
    if claim.kind == "denied":
        return "quote_denied"
    if claim.kind == "uncertain":
        return "quote_uncertain"
    if claim.kind == "own":
        return "own_current" if claim.final_support else "own_withdrawn"
    if claim.kind == "reported":
        if claim.final_support:
            return "report_adopted_current"
        return "report_adoption_withdrawn" if any(e.supported_after for e in events) else "report_not_adopted"
    return _NOT_OBSERVED


def _native_support_claim(ledger: Any, claim: Any) -> NativeSupportClaim:
    """원장 claim 하나를 결속 창 기록으로 옮긴다(B33). 이력은 같은 원장 applications에서 그 claim을 대상으로 한 적용만 순서대로 고른다."""
    events: List[NativeLifecycleEvent] = []
    for application in ledger.applications:
        for claim_id, before, after in zip(application.target_claim_ids, application.prior_adoption, application.after_application):
            if claim_id == claim.claim_id:
                events.append(NativeLifecycleEvent(application.event.event_id, application.applied_effect,
                                                   application.applied_effect_reason, before.supported, after.supported))
    source = next((s for s in ledger.sources if s.source_id == claim.source_id), None)
    return NativeSupportClaim(
        claim_id=claim.claim_id, source_id=claim.source_id, span=claim.span, kind=claim.kind, claimant=claim.speaker,
        speaker_source=claim.speaker_source, attribution=claim.attribution, initial_support=claim.initial_support,
        final_support=claim.final_support, active_adoption_event_ids=claim.active_adoption_event_ids,
        lifecycle=_claim_lifecycle(claim, events), lifecycle_events=tuple(events),
        source_origin=source.source_origin if source else _NOT_OBSERVED, source_index=source.source_index if source else -1,
        original_index=source.original_index if source else -1, raw_path=source.raw_path if source else _NOT_OBSERVED,
        selection_key=source.selection_key if source else _NOT_OBSERVED,
        source_raw_text_span=source.raw_text_span if source else (-1, -1),
        carrier_alignment=source.carrier_alignment if source else _NOT_OBSERVED)


def _window_modality(clause: str) -> str:
    """Binder 양태 검사와 같은 판정(B33). question·uncertain이면 그 창만으로는 확정 요지를 받치지 않는다."""
    question = _is_question(clause)
    uncertain = bool(_UNCERTAIN_SRC.search(clause))
    if (question or uncertain) and _RHETORICAL.search(clause):
        return "rhetorical"
    return "question" if question else "uncertain" if uncertain else "assertive"


def project_context_native(source: ClaimScopeSource, signals: "ExpertSignals", state: "RowState", *,
                           carrier: Optional[NativeSourceCarrier] = None,
                           signal_origins: Sequence[NativeSignalOrigin] = ()) -> NativeProjectionResult:
    """B33 제품 연결 hook용 단일 호출. project_context와 같은 공개 projection과, 그 호출이 만든 같은 Binder의 원장·manifest·
    RowState·요지 판정·결속 증거·작성자 절 좌표·channel 출처를 함께 돌려준다. 전역 capture를 쓰지 않는다."""
    collector = NativeProjectionCollector(carrier=carrier, signal_origins=tuple(signal_origins))
    project_context(source, signals, state, native=collector)
    return collector.result()


_NATIVE_BINDER_CAPTURES: List[List[Any]] = []


@contextmanager
def native_binder_capture() -> Iterator[List[Any]]:
    """공개 pass(project_context 등)가 만든 _Binder 객체를 그대로 모은다. 판정·반환값은 바꾸지 않는다(B32).

    B33: 모듈 전역 목록이라 동시 실행에서는 다른 호출의 Binder가 섞일 수 있다. 제품 경로는 호출별 수집기
    project_context(..., native=NativeProjectionCollector(...)) 또는 project_context_native를 쓴다.
    """
    captured: List[Any] = []
    _NATIVE_BINDER_CAPTURES.append(captured)
    try:
        yield captured
    finally:
        for index in range(len(_NATIVE_BINDER_CAPTURES) - 1, -1, -1):
            if _NATIVE_BINDER_CAPTURES[index] is captured:
                del _NATIVE_BINDER_CAPTURES[index]
                break


def _native_objects(text: str, tokens: Sequence[_ObjectToken], relations: Sequence[_ObjectRelation],
                    works: Sequence[str]) -> Tuple[_NativeObject, ...]:
    """실제 object ledger의 부모 NP, 머리와 하위 제약을 원문 좌표로 보존한다."""
    bounded = list(tokens)
    while bounded and (bounded[0].text in _SELF_SUBJECT or _object_gap_adverb(bounded[0].text)):
        bounded.pop(0)
    while bounded and (bounded[-1].text in _SELF_SUBJECT or _object_gap_adverb(bounded[-1].text)):
        bounded.pop()
    if not bounded:
        return ()
    parent = (bounded[0].start, bounded[-1].end)
    spans = sorted({r.phrase_span for r in relations if r.phrase_span != (-1, -1)} | {parent})
    objects = []
    for lo, hi in spans:
        within = [t for t in bounded if lo <= t.start and t.end <= hi]
        if not within:
            continue
        head = within[-1]
        if head.text in {"에", "에는", "에만", "을", "를", "은", "는"} and len(within) > 1:
            head = within[-2]
        stems = _name_stems(head.text)
        known = stems & (_AGREEMENT_NOUNS | _SPEECH_NOUNS | _DOMAIN_NOUNS | _NATIVE_COUNT_HEADS)
        stem = max(known, key=len) if known else (_TOKEN_PARTICLE.sub("", head.text) or head.text)
        head_start = text.find(stem, head.start, head.end) if head.quoted else head.start
        head_span = (head_start, head_start + len(stem))
        touched = [r for r in relations if r.phrase_span == (lo, hi)
                   or (lo == parent[0] and hi == parent[1])]
        speakers = sorted({s for r in touched for s, _, _ in r.speaker_constraints}
                          | {v for r in touched if r.kind == "speaker" for v in r.values})
        w = sorted(_works_in(text[lo:hi], works))
        items = sorted(item for item in _DOMAIN_NOUNS if _domain_item_pattern(item).search(text[lo:hi]))
        relation = "excludes" if any(r.relation == "excludes" for r in touched) else "selects"
        lexicons = _native_lexicons(stem) if known else ()
        objects.append(_NativeObject(text[lo:hi], (lo, hi), stem, head_span, tuple(w), tuple(items),
                                     tuple(speakers), relation, parent,
                                     object_kind=_native_head_kind(lexicons), object_kind_lexicons=lexicons,
                                     object_kind_evidence_span=head_span, works_source="named_work_in_span" if w else "none",
                                     parent_status="bounded_object_tokens", producer="agreement_object_tokens"))
    return tuple(objects)


def _native_subject(text: str, end: int, works: Sequence[str], *, bare_check: bool = True) -> _NativeSubject:
    return _native_subject_detail(text, end, works, bare_check=bare_check)[0]


def _native_subject_detail(text: str, end: int, works: Sequence[str], *,
                           bare_check: bool = True) -> Tuple[_NativeSubject, Tuple[int, int]]:
    """_native_subject와 같은 문법 주어 기록과, 행위자를 정한 실제 어절 좌표(B32). 두 값은 서로 다른 차원이다."""
    actor, decided = _clause_subject_detail(text, end, works, bare_check=bare_check)
    tokens = [m for m in _PLAIN_TOKEN.finditer(text) if m.end() <= end]
    for token in reversed(tokens):
        word = token.group(0)
        if ((actor == "self" and word in _SELF_SUBJECT)
                or (actor.startswith("other:") and _SUBJ_PARTICLE.search(word)
                    and _stem_of(word) == actor[len("other:"):])):
            return _NativeSubject(actor, word, (token.start(), token.end()), True), decided
    # 생략 주어는 실제 파서 결과다. 필드 부재와 구별하며 gold로 채우지 않는다.
    return _NativeSubject(actor, "", (-1, -1), False), decided


def _evaluation_objects(text: str, start: int, works: Sequence[str]) -> Tuple[_NativeObject, ...]:
    """평가 술어가 가리키는 대상 NP(B33 수리).

    _stance_aspects가 고른 (항목, 소유자)마다 원문 NP·머리·소유자를 기록한다. B33에서 다음을 바로잡았다.
    named-work 표면 안의 부분 어절은 별도 항목이 아니며, 표면 꼬리 어절이 소유자로 잡히면 표면 전체가 소유자다(F01).
    공동격 항목('전개랑 결말')은 앞 항목의 소유자를 공유한다. 항목 뒤 조사 잔여('전개만큼')는 영역 명사로 되돌린다.
    자기 대명사('내가')는 평가하는 사람이지 대상이 아니다. 사람 소유자가 있는 발언명사 NP('민지의 결말 평가')는 그 평가 발화를
    대상으로 한 메타 평가로 남기되 소유자를 작품으로 올리지 않는다(F02). works에는 입력 작품 표면만 넣는다.
    부모 구간은 같은 평가 술어의 대상 NP 전체를 덮는 논항 구간이다.
    """
    actor = _clause_subject(text, start, works)
    actor_name = actor[len("other:"):] if actor.startswith("other:") else ""
    spans = _work_spans(text[:start], works)

    def overlapping(lo: int, hi: int) -> Optional[Tuple[str, int, int]]:
        return next(((w, a, b) for w, a, b in spans if a < hi and lo < b), None)

    objects: List[_NativeObject] = []
    for raw_item, owner in _stance_aspects(text, start):
        if raw_item in {"답", "입장", "결론", actor_name} or raw_item in _SELF_STEMS or raw_item in _SELF_WORDS:
            continue
        item = _normalize_aspect_item(raw_item)
        speech = item in _SPEECH_NOUNS
        if speech and item in _DOMAIN_NOUNS:
            # 발언명사이면서 영역 명사인 항목('이야기')은 B32와 같이 대상으로 두지 않는다(발화/서사 구분 근거가 없다).
            continue
        hits = []
        for m in re.finditer(_aspect_needle(item), text[:start], re.I):
            cover = overlapping(m.start(), m.end())
            if cover and (cover[1], cover[2]) != (m.start(), m.start() + len(item)):
                continue
            hits.append(m)
        if not hits:
            continue
        match = hits[-1]
        lo, hi = match.start(), match.end()
        head_span = (match.start(), match.start() + len(item))
        named_item = overlapping(*head_span)
        owner_value, owner_span, owner_source = "", (-1, -1), "none"
        speakers: Tuple[str, ...] = ()
        subaspects: Tuple[str, ...] = () if named_item else (item,)
        if speech:
            content = owner if owner in _DOMAIN_NOUNS else None
            anchor = match.start()
            if content:
                found = list(re.finditer(re.escape(content), text[:match.start()]))
                anchor = found[-1].start() if found else anchor
            possessor = owner if owner and not content else _owner_before(text, anchor)
            if not possessor or possessor in _SELF_WORDS or possessor in _SELF_STEMS:
                continue
            found = list(re.finditer(re.escape(possessor), text[:anchor]))
            if not found:
                continue
            work_possessor = overlapping(*found[-1].span())
            if work_possessor:
                # 작품 표면이 소유한 평가('달빛기사의 평가')는 그 작품에 대한 평가 발화다. 작품을 화자로 올리지 않는다.
                owner_value, owner_span, owner_source = work_possessor[0], (work_possessor[1], work_possessor[2]), "speech_work_content"
            else:
                owner_value, owner_span, owner_source = possessor, found[-1].span(), "speech_possessor"
                speakers = (possessor,)
            subaspects = (content,) if content else ()
            lo = owner_span[0]
        else:
            if owner and re.fullmatch(r"[가-힣]+?(?:하고|이랑|랑|과|와)", owner) and _normalize_aspect_item(re.sub(r"(?:하고|이랑|랑|과|와)$", "", owner)) in _DOMAIN_NOUNS:
                kind, shared = _source_owner(text, match.start())
                owner, owner_source = ((shared, "coordinated_shared_owner") if kind == "explicit" and shared else (None, "none"))
            elif owner:
                owner_source = "stance_aspect_owner"
            if owner:
                occurrences = list(re.finditer(re.escape(owner), text[:lo]))
                if occurrences:
                    occurrence = occurrences[-1]
                    cover = overlapping(occurrence.start(), occurrence.end())
                    if cover and (cover[1], cover[2]) != occurrence.span():
                        owner_value, owner_span, owner_source = cover[0], (cover[1], cover[2]), "named_work_surface"
                    else:
                        owner_value, owner_span = owner, occurrence.span()
                    lo = owner_span[0]
                else:
                    owner_value = owner
        # 대상 머리 뒤의 조사와 '에 대해'도 같은 NP 좌표에 남긴다.
        following = re.match(r"(?:[은는이가을를에의도만과와]+)?(?:\s*(?:대해|대한|관해|관한))?", text[hi:start])
        hi += following.end() if following else 0
        explicit = tuple(sorted(_works_in(text[lo:hi], works)))
        if named_item:
            object_kind = "named_work"
        elif speech:
            object_kind = "speech_noun"
        else:
            object_kind = _aspect_needle_detail(item)[1]
        objects.append(_NativeObject(text[lo:hi], (lo, hi), item, head_span, explicit, subaspects, speakers,
                                     object_kind=object_kind, object_kind_lexicons=_native_lexicons(item),
                                     object_kind_evidence_span=match.span(), owner=owner_value, owner_span=owner_span,
                                     works_source=("named_work_in_span" if explicit else "owner_not_named_work" if owner_value else "none"),
                                     parent_status="evaluation_argument_phrase", producer="evaluation_stance_aspect",
                                     owner_source=owner_source))
    if objects:
        parent = (min(o.span[0] for o in objects), max(o.span[1] for o in objects))
        objects = [replace(o, parent_span=parent) for o in objects]
    return tuple(objects)


def _normalize_aspect_item(item: str) -> str:
    """항목 줄기 뒤에 남은 조사 잔여('전개만큼', '전개까지')를 영역 명사로 되돌린다(B33). 영역 명사가 아니면 그대로다."""
    if item in _DOMAIN_NOUNS:
        return item
    for noun in sorted(_DOMAIN_NOUNS, key=len, reverse=True):
        if item.startswith(noun) and len(item) > len(noun) and _domain_item_pattern(noun).fullmatch(item):
            return noun
    return item


def _self_answer_span(text: str, start: int, end: int) -> Tuple[int, int]:
    """자기 답 명사절의 상위 실제 단언 범위. 자기 소유·주제 머리·긍정 종결을 함께 요구한다."""
    heads = list(re.finditer(r"(?:내|제|나의|저의)\s+(?:답|입장|평가|결론|생각)(?:은|는|이|가)\s+", text[:start]))
    if not heads or _governing_frame(text, start):
        return (-1, -1)
    head = heads[-1]
    if re.search(r"[.!?？。;]", text[head.end():start]) or _ACT_PAST_BEFORE.search(text[:head.start()]):
        return (-1, -1)
    quoted = next((m for m in _ACT_TOKEN.finditer(text, start, end)
                   if _ACT_QUOTATIVE_END.search(m.group(0))), None)
    if quoted is None:
        return (-1, -1)
    tail = re.match(r"\s*(?:것|거)(?:이)?(?:다|입니다|야|예요|임)[.!。~…\s]*$", text[quoted.end():])
    return (head.start(), quoted.end() + tail.end()) if tail else (-1, -1)


def _evaluation_events(text: str, works: Sequence[str] = (), source_id: str = "clause:0") -> List[_EvaluationEvent]:
    """성립 여부와 무관하게 유효한 평가 술어 후보를 보존한다. 근거 채택은 사건 계약으로 따로 판정한다."""
    inside = [(a, b) for _, a, b in _work_spans(text, works)]
    out: List[_EvaluationEvent] = []
    for match in _EVALUATION_LEXEME.finditer(text):
        if any(a <= match.start() < b for a, b in inside):
            continue
        construction = _agreement_construction(text, match.start(), match.end())
        if construction is None:
            continue
        mode = _agreement_act_detail(text, match.start(), match.end(), construction=construction)
        start, end, polarity, realization = mode.start, mode.end, mode.polarity, mode.realization
        subject, actor_span = _native_subject_detail(text, start, works)
        surface_realization = realization
        realization_source = "own_construction"
        if realization == "embedded" and re.match(r"\s*(?:계획|예정|의향)(?:이|은|는|을|에|$)", text[end:]):
            realization = "modal"
            realization_source = "embedded_plan_noun_modal"
        assertion = _self_answer_span(text, start, end) if realization == "reported" else (-1, -1)
        if assertion != (-1, -1) and subject.actor == "self":
            realization = "actual"
            realization_source = "self_answer_assertion"
        event_id = f"{source_id}:{start}:{end}:evaluate"
        parent = f"{source_id}:{assertion[0]}:{assertion[1]}:self_assertion" if assertion != (-1, -1) else source_id
        out.append(_EvaluationEvent(source_id, event_id, parent, start, end, text[start:end], (start, end),
                                    subject.actor, subject, _evaluation_objects(text, start, works), polarity,
                                    "neg" if match.group(0) in _EVALUATION_NEGATIVE else "pos", realization, assertion,
                                    surface_realization=surface_realization,
                                    temporal_scope=mode.temporal_scope, temporal_evidence_span=mode.temporal_evidence_span,
                                    realization_source=realization_source, realization_frame="clause",
                                    attribution=_actor_attribution("clause_subject", subject.actor, actor_span),
                                    attribution_evidence_span=actor_span))
    return out


_CAUSAL_EVALUATION_END = re.compile(r"(?:아서|어서|여서|해서|다보니|보니)$")
_CONJECTURAL_RESULT_END = re.compile(r"(?:지도|듯|(?:것|거|걸)\s*같(?:다|음|아|은데)?)\s*[.!~… ]*$")
_PERSONAL_CAUSAL_PREDICATE = re.compile(r"사랑|좋아하|좋아해|싫어하|싫어해")

# 평가 수식어가 독서·관찰 경험의 부정 안에 있으면 그 평가를 실제 태도로 세지 않는다.
_NEGATED_EXPERIENCE = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:본|봤던|보았던|읽은|읽었던|접한|접했던)\s*적(?:이|은|도)?\s*"
    r"없(?:었)?(?:음|다|어|네|더라|는데|지만|어서|다고)?(?=$|[\s.!?？。~…])"
)


def _cue_in_negated_experience(text: str, start: int, end: int) -> bool:
    """같은 절의 평가 관형/부사어 → 명사화된 대상 → 경험 부정 관계만 본다."""
    if not re.search(r"(?:은|는|던|게)$", text[start:end]):
        return False
    for experience in _NEGATED_EXPERIENCE.finditer(text, end):
        between = text[end:experience.start()]
        # 독립 문장·인용 틀·새 절의 평가까지 앞선 경험 부정에 묶지 않는다.
        if re.search(r"[.!?？。…;\n\"“”‘’'「」『』]", between):
            return False
        words = [m.group(0) for m in _ACT_TOKEN.finditer(between)]
        if not words:
            continue
        # 목적어 명사구·'풀어내는걸' 같은 명사화 구성만 건넌다. 연결·종결
        # 술어가 있으면 다른 사건이다. 관형/명사화 토큰은 뒤 명사를 수식한다.
        if any((_ACT_CONNECTIVE.search(w) or _ACT_TERMINAL.search(w))
               and not re.search(r"(?:은|는|던|걸|것|거)(?:을|를)?$", w)
               for w in words):
            return False
        # '없지는 않다', '없는 것은 아니다'는 이 긍정 경험 대조에서 제외한다.
        if re.match(r"\s*(?:지는?\s*않|(?:건|것(?:은|이)?)\s*아니)", text[experience.end():]):
            return False
        return True
    return False


_CUE_NOMINAL_LOCK = Lock()


@lru_cache(maxsize=1)
def _cue_nominal_kiwi():
    # 기존 런타임의 형태소 분석기만 사용한다. 네트워크·사용자 사전·작품명 사전은 읽지 않는다.
    from kiwipiepy import Kiwi
    return Kiwi(num_workers=1)


def _cue_is_nominal_observation(text, token, cue, works):
    """원문 명명 범위·복합 명사 안의 어휘 관측을 실제 평가 술어와 구분한다."""
    # 기존 직접 평가 lexeme에도 쓰는 caller의 명명 표면이다. cue 자체와 같은
    # 짧은 이름만으로 정상 술어까지 가리지 않고, 더 큰 명명 구간 내부만 받는다.
    if any(a <= cue.start() and cue.end() <= b and (a < cue.start() or cue.end() < b)
           for _, a, b in _work_spans(text, works)):
        return True
    if cue.span() == token.span():
        return False  # '최고', '사랑' 같은 독립 단문 반응의 기존 계약은 유지한다.
    try:
        # 초기 병렬 호출도 분석기 하나만 만들고 num_workers=1로 읽는다.
        with _CUE_NOMINAL_LOCK:
            parsed = _cue_nominal_kiwi().tokenize(text)
    except Exception:
        return False  # 명사구임을 확인하지 못하면 이 좁은 제한을 새로 적용하지 않는다.
    nominal = {"NNG", "NNP", "NP", "NR", "SL", "SH", "SN"}
    owner_index = next((i for i, part in enumerate(parsed)
        if part.tag in nominal and token.start() <= part.start <= cue.start()
        and cue.end() <= part.start + part.len <= token.end()
        and text[part.start:part.start + part.len] == part.form), None)
    if owner_index is None:
        return False  # VA/VV의 정상 평가 어근은 명사 내부 관측이 아니다.
    owner = parsed[owner_index]
    owner_end = owner.start + owner.len
    compound = owner.start < cue.start() or cue.end() < owner_end
    if owner_index:
        previous = parsed[owner_index - 1]
        compound = compound or (previous.tag in nominal | {"MM", "XPN"}
            and token.start() <= previous.start and previous.start + previous.len == owner.start)
    if owner_index + 1 < len(parsed):
        following = parsed[owner_index + 1]
        compound = compound or (following.tag in nominal | {"XSN"} and following.start == owner_end
            and following.start + following.len <= token.end())
    if not compound:
        return False  # 단순 어미/조사만 붙은 cue에 전역적인 새 문법을 요구하지 않는다.
    # 복합 명사라도 해당 명사가 하다/서술격을 통해 직접 서술되면 기존 평가를 보존한다.
    j, end = owner_index + 1, owner_end
    if j < len(parsed) and parsed[j].tag == "JKO" and parsed[j].start == end:
        end = parsed[j].start + parsed[j].len
        j += 1
    if j < len(parsed):
        following = parsed[j]
        gap = text[end:following.start]
        if following.start >= end and (not gap or gap.isspace()):
            if following.tag in {"XSV", "XSA", "VCP"} or (
                    following.tag in {"VV", "VX"} and following.form == "하"):
                return False
    return True


def _nominal_judgment_binding(text: str, works: Sequence[str] = ()):
    """관형 평가→명사구→계사 보문과 바로 뒤 판단/질문 술어를 원문 좌표로 묶는다.

    내용 명사의 주격/보조사를 바깥 화자로 읽지 않는다. 분석 실패·다른 절·인용은
    기존 계약에 남기며, 이름/명사 목록이나 원문 밖의 작품 정보를 추가하지 않는다.
    """
    tokens = list(_ACT_TOKEN.finditer(text))
    possibilities = []
    for i, governor in enumerate(tokens):
        if i < 2 or not (_GOVERNING_JUDGMENT.match(governor.group(0))
                         or re.match(r"^(?:물었|물어|묻)", governor.group(0))):
            continue
        quotative = tokens[i - 1]
        if not text[quotative.end():governor.start()].isspace():
            continue
        copula = re.fullmatch(r"(?P<negative>아니)(?P<ending>라고|냐고)|(?P<head>.+?)(?:이?라고)", quotative.group(0))
        if copula is None:
            continue
        copula_start = quotative.start() + (len(copula.group("head")) if copula.group("head") else 0)
        possibilities.append((i, governor, quotative, copula_start, bool(copula.group("negative")),
                              copula.group("ending") == "냐고"))
    if not possibilities:
        return None
    try:
        with _CUE_NOMINAL_LOCK:
            parsed = _cue_nominal_kiwi().tokenize(text)
    except Exception:
        return None
    noun_tags = {"NNG", "NNP", "NP", "NR", "SL", "SH", "SN", "MM", "XPN", "XSN", "JKG"}
    for i, governor, quotative, copula_start, negated, questioned in possibilities:
        for modifier in reversed(tokens[:i - 1]):
            # 실제 평가 어휘가 있는 관형 용언만 받는다. 일반 명명/전언 전체를 재해석하지 않는다.
            if not (_POS_CUE.search(modifier.group(0)) or _NEG_CUE.search(modifier.group(0))):
                continue
            parts = [p for p in parsed if modifier.start() <= p.start and p.start + p.len <= modifier.end()]
            if not (any(p.tag.split('-')[0] in {"VA", "VV", "XSA", "XSV"} for p in parts)
                    and any(p.tag == "ETM" and p.start + p.len == modifier.end() for p in parts)):
                continue
            nominal = [p for p in parsed if modifier.end() <= p.start < copula_start
                       and p.start + p.len <= copula_start and p.len > 0]
            if not nominal or not any(p.tag in {"NNG", "NNP", "NP", "NR", "SL", "SH", "SN"} for p in nominal):
                continue
            covered, closed, valid = set(), False, True
            for part in nominal:
                if closed or part.tag not in noun_tags | {"JKS", "JKC", "JX"}:
                    valid = False
                    break
                covered.update(range(part.start, part.start + part.len))
                closed = part.tag in {"JKS", "JKC", "JX"}
            if not valid or any(not text[j].isspace() and j not in covered
                                for j in range(modifier.end(), copula_start)):
                continue  # 다른 술어/주체·문장부호·인용을 건너 이어 붙이지 않는다.
            # 원좌표를 유지한 채 내용 논항만 가려 기존 matrix 주체 판독을 재사용한다.
            masked = text[:modifier.start()] + " " * (quotative.end() - modifier.start()) + text[quotative.end():]
            actor, actor_span = _clause_subject_detail(masked, governor.start(), works)
            mode = _agreement_act_detail(text, governor.start(), governor.end())
            return {"modifier_span": modifier.span(), "content_span": (modifier.start(), quotative.end()),
                    "copula_span": (copula_start, quotative.end()), "governor_span": governor.span(),
                    "actor": actor, "actor_span": actor_span, "content_negated": negated,
                    "content_questioned": questioned, "governing_mode": mode}
    return None


def _source_evaluation_events(text: str, works: Sequence[str], source_id: str) -> List[_EvaluationEvent]:
    """명시 평가와 기존 태도 단서의 위치 후보. cue도 대상·지배 술어·주체·성립을 가진 사건으로 남긴다."""
    result = _evaluation_events(text, works, source_id)
    tokens = list(_ACT_TOKEN.finditer(text))
    blocked = _governed_cue_spans(text)
    nominal_judgment = _nominal_judgment_binding(text, works)
    for group, pattern in (("pos", _POS_CUE), ("neg", _NEG_CUE), ("surprise", _SURPRISE_CUE)):
        for cue in pattern.finditer(text):
            token_index = next((i for i, t in enumerate(tokens) if t.start() <= cue.start() < t.end()), None)
            if token_index is None or any(e.start <= cue.start() < e.end for e in result):
                continue
            token = tokens[token_index]
            mode = _agreement_act_detail(text, token.start(), token.end())
            start, end, polarity, realization = mode.start, mode.end, mode.polarity, mode.realization
            temporal = (mode.temporal_scope, mode.temporal_evidence_span)
            realization_source = "cue_token_construction"
            surface_realization = realization
            subject = _native_subject(text, start, works, bare_check=False)
            # 형용사 평가의 주격 항목('결말은 좋다')과 평가하는 사람은 서로 다른 자리다.
            raw_subject = next((t for t in reversed(tokens[:token_index]) if _SUBJ_PARTICLE.search(t.group(0))), None)
            if raw_subject is not None:
                subject = replace(subject, text=raw_subject.group(0), span=(raw_subject.start(), raw_subject.end()), explicit=True)
            actor = "self"
            actor_route, actor_span = "unit_speaker", (-1, -1)
            governor = None
            if _ACT_QUOTATIVE_END.search(token.group(0)) and token_index + 1 < len(tokens):
                j = token_index + 1
                while j + 1 < len(tokens) and _object_gap_adverb(tokens[j].group(0)):
                    j += 1
                following = tokens[j]
                if _GOVERNING_RECORD.match(following.group(0)) or _GOVERNING_JUDGMENT.match(following.group(0)):
                    governor = following
                    governing = _agreement_act_detail(text, governor.start(), governor.end())
                    gp, gr = governing.polarity, governing.realization
                    actor, actor_span = _clause_subject_detail(text, governor.start(), works)
                    actor_route = "governing_subject"
                    polarity, realization = gp, gr
                    temporal = (governing.temporal_scope, governing.temporal_evidence_span)
                    realization_source = "governing_predicate"
                    if _GOVERNING_RECORD.match(governor.group(0)):
                        realization = "reported"
                        realization_source = "governing_record_predicate"
            elif _THIRD_PRED.search(text[start:end]):
                actor, actor_span = _clause_subject_detail(text, start, works)
                actor_route = "third_party_subject"
            elif realization == "embedded" and not _governing_frame(text, start):
                # 기존의 형용사 완곡 평가('좋은 것 같다')는 현재 태도 단서로 보존한다.
                realization = "actual"
                realization_source = "embedded_hedge_current"
            # 말줄임표·문장 부호는 연결어미 뒤에 붙어도 인과절의 주어를 바꾸지 않는다.
            causal_surface = text[start:end].rstrip(" \t.!?？。~…")
            if _CAUSAL_EVALUATION_END.search(causal_surface):
                # '좋아하다보니'의 연결어미 '니'는 질문 종결이 아니다. 뒤 절의
                # '...한걸지도'는 그 인과 설명 전체를 추측으로 제한한다.
                conjecture = bool(_CONJECTURAL_RESULT_END.search(text[end:]))
                if (realization == "question" and not re.search(r"[?？]", text[start:end])
                        and not re.search(r"[?？][.!~… ]*$", text[end:])):
                    realization = "modal" if conjecture else "actual"
                    realization_source = "causal_connective_result"
                elif conjecture and realization == "actual":
                    realization = "modal"
                    realization_source = "causal_conjecture_result"
                if governor is None:
                    preceding_actor, preceding_span = _clause_subject_detail(text, start, works)
                    if (preceding_span != (-1, -1) and preceding_actor.startswith("other:")
                            and _PERSONAL_CAUSAL_PREDICATE.search(text[start:end])):
                        actor, actor_span = preceding_actor, preceding_span
                        actor_route = "causal_explicit_subject"
                    elif preceding_span == (-1, -1):
                        result_actor, result_span = _clause_subject_detail(text, len(text), works)
                        if (conjecture or (result_actor.startswith("other:") and result_span[0] >= end)):
                            # 생략된 인과절 주어를 글쓴이로 확정하지 않는다. 뒤 절의
                            # 타자 주어도 인과절 주어로 역전파하지 않는다.
                            actor, actor_span = "unknown", (-1, -1)
                            actor_route = "causal_implicit_subject"
            if any(a <= cue.start() < b for a, b in blocked) and realization == "actual":
                realization = "reported"
                realization_source = "governed_cue_blocked"
            # '재미없다'처럼 긍정 cue 어근 뒤에 부정 접사가 붙은 한 어절은
            # 같은 원문 사건에서도 부정 태도다. 뒤따르는 별도 부정 술어는
            # 기존 행위 극성 판정에 맡긴다.
            cue_group = "neg" if (group == "pos" and re.match(r"^[가-힣]{0,2}\s*없", text[cue.end():token.end()])) else group
            evaluation_group = ("neg" if cue_group == "pos" else "pos") if polarity == "negative" and cue_group in ("pos", "neg") else cue_group
            # 부정 형용사 자체는 반대 태도다. 행위 부정과 달리 평가를 하지 않았다는 뜻은 아니다.
            if governor is None:
                polarity = "positive"
                if (_RHETORICAL.search(text) or (realization == "modal"
                        and re.search(r"(?:것|거)\s*같", text[start:end]))):
                    # 반어 반응과 완곡한 형용사 판단은 현재 평가다. 표면 양태는 별도 보존한다.
                    realization = "actual"
                    realization_source = "rhetorical_or_hedged_current"
            if realization == "actual" and _cue_in_negated_experience(text, token.start(), token.end()):
                realization = "embedded"
                realization_source = "negated_experience_scope"
            if group == "pos" and realization == "actual" and _cue_is_nominal_observation(text, token, cue, works):
                # 원문·어휘 극성·predicate span은 남기고 실제 평가 사건 자격만 제한한다.
                realization = "embedded"
                realization_source = "nominal_cue_observation"
            if (nominal_judgment is not None
                    and nominal_judgment["modifier_span"][0] <= cue.start()
                    and cue.end() <= nominal_judgment["modifier_span"][1]):
                actor, actor_span = nominal_judgment["actor"], nominal_judgment["actor_span"]
                actor_route = "governing_subject"
                subject = _NativeSubject(actor, text[actor_span[0]:actor_span[1]] if actor_span[0] >= 0 else "",
                                         actor_span, actor_span[0] >= 0)
                governing = nominal_judgment["governing_mode"]
                temporal = (governing.temporal_scope, governing.temporal_evidence_span)
                if nominal_judgment["content_questioned"]:
                    realization = "question"
                elif governing.realization != "actual":
                    realization = governing.realization
                elif nominal_judgment["content_negated"] or governing.polarity == "negative":
                    realization = "embedded"
                if realization != "actual":
                    realization_source = "nominal_judgment_content"
            result.append(_EvaluationEvent(source_id, f"{source_id}:{start}:{end}:cue:{cue.start()}", source_id,
                                            start, end, text[start:end], (start, end), actor, subject,
                                            _evaluation_objects(text, start, works), polarity, evaluation_group,
                                            realization, (-1, -1), evidence_kind="cue", surface_realization=surface_realization,
                                            temporal_scope=temporal[0], temporal_evidence_span=temporal[1],
                                            realization_source=realization_source, realization_frame="clause",
                                            attribution=("unit_speaker_default" if actor_route == "unit_speaker"
                                                         else _actor_attribution(actor_route, actor, actor_span)),
                                            attribution_evidence_span=actor_span))
    return sorted(result, key=lambda e: (e.start, e.event_id))


def _offset_evaluation(event: _EvaluationEvent, offset: int) -> _EvaluationEvent:
    def span(value):
        return (value[0] + offset, value[1] + offset) if value != (-1, -1) else value
    parent = event.parent_event_id
    if event.assertion_span != (-1, -1):
        # B32: 인용 내용 좌표로 만든 상위 자기 단언 ID를 절 좌표로 옮긴다. assertion span과 같은 좌표계다.
        lo, hi = span(event.assertion_span)
        parent = f"{event.source_id}:{lo}:{hi}:self_assertion"
    return replace(event, start=event.start + offset, end=event.end + offset, predicate_span=span(event.predicate_span),
                   event_id=f"{event.event_id}:offset:{offset}", assertion_span=span(event.assertion_span), parent_event_id=parent,
                   grammatical_subject=replace(event.grammatical_subject, span=span(event.grammatical_subject.span)),
                   objects=tuple(replace(o, span=span(o.span), head_span=span(o.head_span), parent_span=span(o.parent_span),
                                         owner_span=span(o.owner_span), object_kind_evidence_span=span(o.object_kind_evidence_span))
                                 for o in event.objects),
                   temporal_evidence_span=span(event.temporal_evidence_span),
                   attribution_evidence_span=span(event.attribution_evidence_span), realization_frame="quote_body")


def _object_licenses(obj: "_NativeObject", item: str) -> bool:
    """B33(F02): 발언명사 머리 NP('민지의 결말 평가')는 그 평가 발화에 대한 메타 평가다. 같은 발언명사 항목만 지지하고,
    NP 안의 내용 항목('결말')이나 작품 호평으로 축약하지 않는다. 그 밖의 대상 NP는 기존 결속 규칙을 그대로 따른다."""
    if getattr(obj, "object_kind", "") != "speech_noun":
        return True
    return _same_arg(item, obj.head)


def _evaluation_act_spans(text: str, works: Sequence[str] = ()) -> List[Tuple[int, int, str]]:
    """기존 호출 경계: 같은 native 평가 사건 중 실제 긍정 자기 행위의 lexeme 위치만 돌려준다."""
    result = []
    for event in _evaluation_events(text, works):
        if event.realization == "actual" and event.polarity == "positive" and event.actor == "self":
            match = _EVALUATION_LEXEME.search(text, event.start, event.end)
            result.append((match.start(), match.end(), event.evaluation_polarity))
    return result


def _governed_cue_spans(text: str) -> List[Tuple[int, int]]:
    """인용 보문('…좋다고', '…좋다는')으로 상위 술어에 걸린 태도 단서 가운데 현재 자기 평가로 성립하지 않는 단서 구간.

    기록 술어('좋다고 적었다')는 늘 막는다. 판단·발화 술어('좋다고 평가한다', '좋다고 생각한다')는 그 술어가 실제 긍정으로 성립하지
    않으면('평가할 계획이다', '생각한다면', '생각하지 않는다', '말할 수 있을까') 막는다. 보문 없는 단서는 건드리지 않는다.
    """
    spans = list(_ACT_TOKEN.finditer(text))
    blocked: List[Tuple[int, int]] = []
    for cue in list(_POS_CUE.finditer(text)) + list(_NEG_CUE.finditer(text)):
        k = next((i for i, t in enumerate(spans) if t.start() <= cue.start() < t.end()), None)
        if k is None or k + 1 >= len(spans) or not _ACT_QUOTATIVE_END.search(spans[k].group(0)):
            continue
        if re.search(r"[.!?？。…;,，]", text[spans[k].end():spans[k + 1].start()]):
            continue
        governor = spans[k + 1]
        if _GOVERNING_RECORD.match(governor.group(0)):
            blocked.append((cue.start(), cue.end()))
        elif _GOVERNING_JUDGMENT.match(governor.group(0)):
            _, _, polarity, realization = _agreement_act_mode(text, governor.start(), governor.end())
            if realization != "actual" or polarity != "positive":
                blocked.append((cue.start(), cue.end()))
    return blocked


class _Binder:
    """요지 문장 하나를 원문 절·근거에 묶어 본다. 범용 함의 판정기가 아니라 좁은 결속 검사다."""

    def __init__(self, source: ClaimScopeSource, signals: ExpertSignals, state: RowState, act: str, clauses: Sequence[str], *,
                 native: Optional["NativeProjectionCollector"] = None):
        self.source, self.signals, self.act = source, signals, act
        # B33: 같은 pass의 실제 RowState와 호출별 native 수집기를 그대로 둔다. 다른 값에서 역추론하지 않는다.
        self.state = state
        self.native = native
        manifest = native.manifest if native is not None else None
        self.clauses = tuple(clauses)
        self.post_text = " ".join(source.post_lines)
        self.comment_text = " ".join(source.comments or ())
        titles = {s for s in signals.named_work_surfaces if s}
        if state.resolved_title:
            titles.add(state.resolved_title)
        self.allowed_titles = titles
        self.any_question = any(_is_question(c) for c in self.clauses)
        post_clauses = _post_clauses(source)
        self.title = source.post_lines[0] if source.post_lines else ""
        # 작성자 글 전체를 한 화자 단위로 보고 직접 발화·인용·전언·동의·철회를 나눈다.
        self.author_input = _native_author_input(source, "_Binder.__init__", manifest)
        self.author_ledger = _speaker_ledger(post_clauses, tuple(s for s in signals.named_work_surfaces if s), "author", self.author_input)
        author_utts = self.author_ledger.utterances
        own = [c.binding_text for c in self.author_ledger.claims if c.kind == "own" and c.final_support]
        reported = [c.binding_text for c in self.author_ledger.claims if c.kind == "reported"]
        endorsed = [c.binding_text for c in self.author_ledger.claims if c.kind == "reported" and c.final_support]
        retracted = [u.source for u in author_utts if u.kind == "own" and not u.adopted]
        self.reported = tuple(reported)
        self.first_person = tuple(own + [e for e in endorsed if e not in own])
        # B33: first_person·reported 문자열과 1:1로 같은 순서의 실제 claim. 공개 판정에는 쓰지 않는 proof 기록이다.
        self.first_person_claims = tuple([c for c in self.author_ledger.claims if c.kind == "own" and c.final_support]
                                         + [c for c in self.author_ledger.claims if c.kind == "reported" and c.final_support
                                            and c.binding_text not in own])
        self.reported_claims = tuple(c for c in self.author_ledger.claims if c.kind == "reported")
        self.post_clauses = post_clauses
        # 철회된 제목은 판정 창에 붙이지 않는다(제목의 평가를 본문에서 거둔 경우).
        # B33(H11): 제목 줄(제목이 없으면 첫 본문 줄)의 절 하나라도 철회된 본인 발화면 그 줄 전체를 판정 창에 붙이지 않는다.
        title_key = _title_line_key(source)
        title_sources = {s.source_id for s in self.author_ledger.sources if (s.source_origin, s.source_index) == title_key}
        title_withdrawn = any(c.kind == "own" and not c.final_support for c in self.author_ledger.claims if c.source_id in title_sources)
        self.window_title = "" if self.title and (self.title in retracted or title_withdrawn) else self.title
        # 지시어·생략 소유자 해석에 쓰는 화자 단위의 현재 작품 표면(이미지 출처·미해결 표면 제외).
        # 작성자는 작성자 절 전체, 댓글은 그 댓글 하나다. 작품을 전혀 말하지 않은 댓글만 글 제목의 현재 작품을 이어받는다
        # (댓글의 소유자 생략을 제목으로 푸는 기존 규칙과 같다). 다른 댓글의 작품은 빌려 오지 않는다.
        self.named = tuple(s for s in signals.named_work_surfaces if s)
        self.live_named = _live_surfaces(self.named, self.clauses)[0]
        self.author_ctx = ("author", tuple(self.clauses), tuple(post_clauses))
        # 댓글은 댓글 한 개가 화자 단위다. 직접 발화와 동의로 받아들인 인용·전언만 그 댓글의 태도 근거가 된다.
        # 문맥의 세 번째 값은 그 절까지의 원문 절이다(다른 작품을 들여온 절 이후에만 제목 상속·유일성을 막는다).
        units: List[str] = []
        unit_ctx: List[Tuple[str, Tuple[str, ...], Tuple[str, ...]]] = []
        unit_claims: List[Tuple[int, Any]] = []
        self.comment_ledgers = []
        for comment_index, line in enumerate(source.comments or ()):
            parts = tuple(c.text for c in split_clauses(line) if c.text.strip())
            # 채택 상태가 참인 발화(직접 발화, 동의로 채택된 인용·전언)만 그 댓글의 태도 근거다. 원문 위치를 문맥 범위로 쓴다.
            ledger = _speaker_ledger(parts, self.named, f"comment:{comment_index}",
                                     _native_comment_input(line, comment_index, "_Binder.__init__", manifest))
            self.comment_ledgers.append((parts, ledger))
            for u, claim in zip(ledger.utterances, ledger.claims):
                if u.adopted:
                    units.append(claim.binding_text)
                    unit_ctx.append(("comment", parts, parts[:u.pos + 1]))
                    unit_claims.append((comment_index, claim))
        self.comment_units = tuple(units)
        self.comment_unit_ctx = tuple(unit_ctx)
        # B33: comment_units와 1:1로 같은 순서의 (댓글 index, 실제 claim). 공개 판정에는 쓰지 않는 proof 기록이다.
        self.comment_unit_claims = tuple(unit_claims)
        self._live_cache = {}
        # 이미 알려진 인물·작가 이름: 역할어가 이 이름에 붙으면 이름마다 근거를 요구한다.
        self.known_names = _known_names(signals)
        # B32: 공개 pass가 만든 이 Binder와 그 원장을 capture 요청자에게 그대로 넘긴다.
        for captured in _NATIVE_BINDER_CAPTURES:
            captured.append(self)
        if native is not None:
            native.binders.append(self)

    def _live_for(self, ctx: Tuple[str, Tuple[str, ...]], owners: Sequence[str] = ()) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        """화자 단위 문맥의 (후보 작품 표면, 현재 작품 표면).

        후보에는 입력 작품 표면에 더해 요지가 밝힌 소유 표면을 넣는다(작품 표면 입력이 없어도 그 표면이 이 단위에서 현재 작품으로
        언급됐는지 같은 관계 판정으로 본다). 작품을 전혀 말하지 않은 댓글은 글 제목을 문맥으로 쓴다.
        """
        named = self.named + tuple(o for o in dict.fromkeys(owners) if o and o not in self.named)
        kind, clauses, upto = ctx
        # 이름을 몰라도 '다른 작품'·'어떤 소설'처럼 새 작품을 들여온 절 이후에는 그 작품이 문맥에 있다(제목 상속·유일성 차단).
        other = any(_introduces_other_work(re.findall(r"[가-힣A-Za-z0-9]+", c)) for c in upto)
        if kind == "comment" and not other and not any(s in c for s in named for c in clauses):
            clauses = (self.title,) if self.title else ()
        key = (clauses, named, other)
        if key not in self._live_cache:
            live = _live_surfaces(named, clauses)[0]
            self._live_cache[key] = live + ((_OTHER_MARK,) if other else ())
        return named, self._live_cache[key]

    def _author_ctx_for(self, clause: str) -> Tuple[str, Tuple[str, ...], Tuple[str, ...]]:
        kind, clauses, post = self.author_ctx
        upto = next((i for i, p in enumerate(post) if clause in p or p in clause), len(post) - 1)
        return kind, clauses, post[:upto + 1]

    def _stance_ok(self, group: str, binding: str) -> bool:
        if group in {"neg", "pos", "surprise"}:
            return group in _cue_polarity(binding)
        if group == "q":
            return self.any_question or "?" in binding
        if group == "req":
            return self.act == "recommendation_request" or bool(_REQUEST.search(binding)) or "찾" in binding
        if group == "joke":
            return bool(_LAUGH.search(binding))
        return True

    def _stance_supported(self, group: str, text: str, aspects: Sequence[Tuple[str, Optional[str]]], needles: Sequence[str],
                          allow_uncertain: bool = False, ctx: Optional[Tuple[str, Tuple[str, ...]]] = None,
                          proof: Optional[list] = None) -> bool:
        """태도 단서가 같은 평가 항목(없으면 결속 어절)을 가리키는 연결 절 안에 같은 극성으로 있는가.

        작품명 하나가 겹친다고 결말·전개 같은 다른 평가 항목을 같은 대상으로 보지 않는다. 대상을 생략한 반응은 허용한다.
        직접 평가 술어('결말을 호평한다')는 현재 실제로 성립한 화자 본인의 평가일 때만 단서다(_evaluation_act_spans). 인용 보문으로
        상위 기록·판단 술어에 걸린 단서('좋다고 적었다', '좋다고 평가할 계획이다')는 그 술어가 성립하지 않으면 단서가 아니다.
        """
        if group in {"q", "req", "neutral"}:
            ok = self._stance_ok(group, text)
            if ok and proof is not None:
                proof.append(("stance_lexicon", (ctx or self.author_ctx)[0], []))
            return ok
        named, live = self._live_for(ctx or self.author_ctx, [o for _, o in aspects if o])
        view = _mask_spans(text, _governed_cue_spans(text))
        clause_text = text.partition(" / ")[0]
        kind, parts, _ = ctx or self.author_ctx
        ledger = self.author_ledger if kind == "author" else next((l for p, l in self.comment_ledgers if p == parts), None)
        evidence_ledgers = [ledger] if ledger else []
        if self.author_ledger not in evidence_ledgers:
            evidence_ledgers.append(self.author_ledger)
        claim_by_id = {c.claim_id: c for l in evidence_ledgers for c in l.claims}
        native = [e for l in evidence_ledgers for e in l.evaluations
                  if e.binding_text in {clause_text, self.window_title}
                  and (e.final_support or (allow_uncertain and e.claim_id in claim_by_id
                       and claim_by_id[e.claim_id].final_support and e.realization in {"question", "modal", "embedded"}))]

        def evidence_position(event):
            position = event.start - event.binding_offset
            return position + len(clause_text) + 3 if event.binding_text == self.window_title and clause_text != self.window_title else position
        lexical = [e for e in native if e.evidence_kind == "lexical" and e.evaluation_polarity == group]

        def note(basis: str, events: list) -> None:
            if proof is not None:
                proof.append((basis, kind, events))

        def note_cue(at: int, seg: str) -> None:
            # B33: cue 판정이 쓴 같은 조건의 사건만 적는다. pos·neg는 사건이 반드시 있고, 그 밖의 태도는 어휘 판정이다.
            if proof is not None:
                events = [e for e in native if e.evidence_kind == "cue" and e.evaluation_polarity == group
                          and e.claim_id in claim_by_id and at <= evidence_position(e) < at + len(seg)]
                proof.append(("cue_event" if events else "cue_lexicon", kind, events))
        for event in lexical:
            if aspects and all(any(_target_in(obj.text, item, owner, live, named) for obj in event.objects
                                   if _object_licenses(obj, item))
                               for item, owner in aspects):
                note("lexical_event", [event])
                return True
            if not aspects and (not needles or all(re.search(needle, clause_text, re.I) for needle in needles)):
                note("lexical_event", [event])
                return True
        # lexical 술어는 cue fallback으로 우회하지 않는다. cue는 실제 원장의 동일 claim 사건만 쓴다.
        view = _mask_spans(view, [(e.start, e.end) for e in (ledger.evaluations if ledger else ())
                                  if e.evidence_kind == "lexical" and e.binding_text == clause_text
                                  and e.source_id in {s.source_id for s in ledger.sources if s.text == clause_text}])
        cursor = 0
        for seg in _evaluation_segments(view):
            at = view.find(seg, cursor) if seg else cursor
            at = cursor if at < 0 else at
            cursor = at + len(seg)
            cue_ok = self._stance_ok(group, seg)
            if group in ("pos", "neg"):
                cue_ok = cue_ok and any(e.evidence_kind == "cue" and e.evaluation_polarity == group
                                       and e.claim_id in claim_by_id
                                       and at <= evidence_position(e) < at + len(seg)
                                       for e in native)
            if not seg.strip() or not cue_ok:
                continue
            # 질문·불확실 절의 태도 단서는 요지가 불확실성을 밝힐 때만 근거가 된다(반어 불평은 예외).
            if (_is_question(seg) or _UNCERTAIN_SRC.search(seg)) and not _RHETORICAL.search(seg) and not allow_uncertain:
                continue
            # 항목 쌍이 있으면 같은 항목·소유 작품, 없으면 결속 어절로 본다. 목표가 전혀 없으면 단서만 본다.
            if aspects:
                if any(_target_in(seg, item, owner, live, named) for item, owner in aspects):
                    note_cue(at, seg)
                    return True
            elif not needles or any(re.search(n, seg, re.I) for n in needles):
                note_cue(at, seg)
                return True
            subj, obj, dat = _clause_args(seg)
            # 지시어·태도 단서 어절·요지의 소유 작품(대상 항목은 이미 결속 범위 안에 있음)은 다른 대상이 아니다.
            owners = [o for _, o in aspects if o]
            items = [i for i, _ in aspects]
            bare_domain = [w for w in re.findall(r"[가-힣]+", seg) if w in _DOMAIN_NOUNS and not any(_same_arg(w, i) for i in items)]
            other_owner = [m.group(1) for m in re.finditer(r"([가-힣A-Za-z0-9]{2,})['’\"”]?의(?![가-힣])", seg)
                           if owners and not any(_same_arg(m.group(1), o) for o in owners)]
            others = bare_domain + other_owner + [x for x in subj + obj + dat if x not in _DEMONSTRATIVE_SUBJ
                      and not any(x.startswith(dm) for dm in _DEMONSTRATIVE_SUBJ if len(dm) >= 2)
                      and not self._stance_ok(group, x) and not any(_same_arg(x, o) for o in owners)]
            if not others:
                # 대상을 생략한 반응('진짜 좋다')도 요지가 소유 작품을 밝혔다면 그 화자 단위의 문맥 작품이 같아야 한다.
                if owners and not any(_same_arg(o, r) for o in owners for r in [_implied_owner(seg, len(seg), live, named)] if r):
                    continue
                note_cue(at, seg)
                return True
        return False

    def bind(self, s: str) -> Tuple[bool, str, int]:
        """요지 문장 하나의 결속 판정. 반환 (ok, why, count)는 B32와 같다."""
        return self._bind_impl(s, None)

    def bind_with_proof(self, s: str) -> Tuple[bool, str, int, "NativeBindProof"]:
        """B33: bind와 같은 판정에, 그 판정이 실제로 쓴 결속 창·원장 claim·태도 사건을 함께 돌려준다."""
        record: dict = {}
        ok, why, count = self._bind_impl(s, record)
        return ok, why, count, self._bind_proof(s, ok, why, count, record)

    def _bind_proof(self, s: str, ok: bool, why: str, count: int, record: dict) -> "NativeBindProof":
        """bind 계산이 record에 남긴 창·출처·어절·태도 근거를 같은 Binder 원장 객체로 옮긴다. 원장을 다시 만들지 않는다."""
        unresolved: List[str] = []
        clauses = record.get("clauses", [])
        sources = record.get("sources", [])
        bound = record.get("bound", [])
        good, touched = set(record.get("good", [])), set(record.get("touched", []))
        if len(sources) != len(clauses) or any(claim.binding_text != clause for (_, claim, _), clause in zip(sources, clauses)):
            unresolved.append("window_claim_alignment_failed")
            sources = []
        ledgers = [self.author_ledger] + [ledger for _, ledger in self.comment_ledgers]
        claim_owner = {c.claim_id: (ledger, c) for ledger in ledgers for c in ledger.claims}
        title = self.window_title
        title_key = _title_line_key(self.source)
        title_ids = {src.source_id for src in self.author_ledger.sources if (src.source_origin, src.source_index) == title_key}
        title_claims = [c for c in self.author_ledger.claims if c.source_id in title_ids]
        windows: List[NativeSupportWindow] = []
        for i, (selection, claim, comment_index) in enumerate(sources):
            ledger = self.author_ledger if comment_index < 0 else self.comment_ledgers[comment_index][1]
            clause = clauses[i]
            locations: List[NativeTokenLocation] = []
            for token, needle in bound:
                if re.search(needle, clause, re.I):
                    locations.append(NativeTokenLocation(token, "clause", (claim.claim_id,)))
                elif title and re.search(needle, title, re.I):
                    locations.append(NativeTokenLocation(token, "title", tuple(c.claim_id for c in title_claims
                                                                            if re.search(needle, c.binding_text, re.I))))
                else:
                    locations.append(NativeTokenLocation(token, "unlocated"))
            uses_title = any(location.location == "title" for location in locations)
            if uses_title and not title_claims:
                unresolved.append(f"window:{i}:title_claims_not_observed")
            if selection == "author_reported_by_summary_marker":
                usage, why_text = "attribution_only", "summary_reported_marker:" + record.get("reported_marker", "")
            elif selection == "comment_adopted_unit":
                usage, why_text = "endorsed_assertion", "comment_claim_adopted"
            else:
                usage = "endorsed_assertion"
                why_text = "own_claim_final_support" if claim.kind == "own" else "reported_claim_adopted_final_support"
            windows.append(NativeSupportWindow(
                window_index=i, unit_kind="comment" if comment_index >= 0 else "author", unit_source_id=ledger.source_id,
                selection=selection, usage=usage, why=why_text, clause_text=clause, title_window=title,
                window_modality=_window_modality(clause), token_complete=i in good, touched=i in touched,
                token_locations=tuple(locations), claim=_native_support_claim(ledger, claim),
                title_claims=tuple(_native_support_claim(self.author_ledger, c) for c in title_claims) if uses_title else ()))
        support: List[NativeStanceSupport] = []
        for token, group, scope, at, found in record.get("stances", []):
            if scope == "summary_window":
                window_claim = sources[at][1].claim_id if 0 <= at < len(sources) else ""
            else:
                window_claim = self.comment_unit_claims[at][1].claim_id if 0 <= at < len(self.comment_unit_claims) else ""
            for basis, unit_kind, events in found or ():
                common = dict(stance_token=token, group=group, scope=scope, window_index=at, basis=basis, unit_kind=unit_kind,
                              window_claim_id=window_claim)
                if not events:
                    support.append(NativeStanceSupport(support_mode="lexicon_only", **common))
                for e in events:
                    owner = claim_owner.get(e.claim_id)
                    if owner is None:
                        unresolved.append(f"stance:{e.event_id}:claim_not_found")
                    support.append(NativeStanceSupport(
                        support_mode="actual_final_support" if e.final_support else "uncertain_claim_supported",
                        event_id=e.event_id, claim_id=e.claim_id, source_id=e.source_id, evidence_kind=e.evidence_kind,
                        predicate=e.predicate, predicate_span=e.predicate_span, realization=e.realization, actor=e.actor,
                        final_support=e.final_support, claim_final_support=bool(owner and owner[1].final_support), **common))
        return NativeBindProof(sentence=s, ok=ok, why=why, count=count, speaker_route=record.get("route", ""),
                               reported_marker=record.get("reported_marker", ""),
                               uncertainty_marker=record.get("uncertainty_marker", ""),
                               modality_basis=record.get("modality", "not_reached"),
                               bound_tokens=tuple(token for token, _ in bound), windows=tuple(windows),
                               stance_support=tuple(support), unresolved=tuple(unresolved))

    def _bind_impl(self, s: str, proof: Optional[dict]) -> Tuple[bool, str, int]:
        commenter = bool(_COMMENTER_SPEAKER.search(s))
        joint = commenter and bool(_JOINT_SPEAKER.search(s))
        if proof is not None:
            reported_marker = _REPORTED_MARK.search(s)
            uncertainty_marker = _UNCERTAIN_EXPERT.search(s)
            proof["route"] = ("comment_units" if commenter and not joint
                              else "joint_author_and_comment_units" if joint else "author_unit")
            proof["reported_marker"] = reported_marker.group(0) if reported_marker else ""
            proof["uncertainty_marker"] = uncertainty_marker.group(0) if uncertainty_marker else ""
        if commenter and not self.comment_units:
            return False, "core_hold:speaker_unbound", 0
        if commenter and not joint:
            # 댓글 화자 요지는 댓글마다 따로 근거를 찾는다. 본문 사실이나 여러 댓글의 조합을 댓글 주장으로 쓰지 않는다.
            clauses = list(self.comment_units)
            ctxs = list(self.comment_unit_ctx)
        else:
            # 전언(친구가 …더라) 절은 요지가 전언임을 밝힐 때만 근거로 쓴다.
            clauses = list(self.first_person) + (list(self.reported) if _REPORTED_MARK.search(s) else [])
            ctxs = [self._author_ctx_for(c) for c in clauses]
        if proof is not None:
            proof["clauses"], proof["ctxs"] = list(clauses), list(ctxs)
            if commenter and not joint:
                proof["sources"] = [("comment_adopted_unit", claim, comment_index) for comment_index, claim in self.comment_unit_claims]
            else:
                proof["sources"] = ([("author_first_person", claim, -1) for claim in self.first_person_claims]
                                    + ([("author_reported_by_summary_marker", claim, -1) for claim in self.reported_claims]
                                       if proof.get("reported_marker") else []))
        if not clauses:
            return False, "core_drop:not_source_bound", 0
        binding = " / ".join(clauses + ([self.title] if commenter and not joint else []))
        compact = re.sub(r"\s+", "", binding).lower()
        body = s
        for t in sorted(self.allowed_titles, key=len, reverse=True):
            if t not in self.post_text:
                body = body.replace(t, " ")
        for num in re.findall(r"\d+", body):
            if num not in binding:
                return False, f"core_hold:new_number:{num}", 0
        for m in _CERTAINTY.finditer(body):
            if m.group(0) not in binding:
                return False, f"core_hold:certainty_added:{m.group(0)}", 0
        # (어절, 원문 검색식, 시작, 끝, 술어 종류 None|'event'|'exist', 한 음절 어간 여부, 어간 길이)
        bound: List[Tuple[str, str, int, int, Optional[str], bool, int]] = []
        stances: List[Tuple[str, str, int]] = []
        unknown: List[str] = []
        for tm in re.finditer(r"[가-힣A-Za-z0-9]+", body):
            token = tm.group(0)
            if len(token) < 2:
                continue
            cands = _stems(token)
            # 존재·소유 술어 '있다/없다'는 보조 용언('~고 있다', '~ㄹ 수 있다')이 아니면 사실 주장으로 검사한다.
            if token[0] in "있없" and any(c in ("있", "없") for c in cands):
                if _AUX_BEFORE_EXIST.search(body[:tm.start()]):
                    continue
                if re.search(_EXIST_NEEDLE, binding):
                    bound.append((token, _EXIST_NEEDLE, tm.start(), tm.end(), "exist", False, 1))
                else:
                    unknown.append(token)
                continue
            # 평가 항목은 일반어이기도 하지만, 원문에 같은 항목이 명시되면 독립 근거다.
            # 작품명 하나만으로 통과시키지 않고 기존 최소 근거 수와 태도·대상 검사를 유지한다.
            domain = next((c for c in cands if c in _DOMAIN_NOUNS and c in _GENERIC_WORDS
                           and _domain_item_pattern(c).search(binding)), None)
            if domain:
                bound.append((token, _domain_item_pattern(domain).pattern, tm.start(), tm.end(), None, False, len(domain)))
                continue
            if any(c in _GENERIC_WORDS or c in _FUNCTION_STEMS for c in cands):
                continue
            evaluation = _EVALUATION_LEXEME.search(token)
            if evaluation and _agreement_construction(body, tm.start() + evaluation.start(), tm.start() + evaluation.end()) is not None:
                group = "neg" if evaluation.group(0) in _EVALUATION_NEGATIVE else "pos"
                stances.append((token, group, tm.start()))
                continue
            stance = next((g for g, words in _STANCE.items() for c in cands for w in words if c.startswith(w)), None)
            if stance:
                stances.append((token, stance, tm.start()))
                continue
            if any(c in _EVAL_DIMENSIONS for c in cands):
                if not (self.any_question or _EVAL_PRED.search(binding) or re.search(r"vs|뭐가\s*더|비교", binding)):
                    return False, f"core_hold:stance_unbound:{token}", 0
                continue
            looks_pred = bool(_LOOKS_PRED.search(token))
            para = next((k for c in cands for k in _PARAPHRASE if c.startswith(k)), None)
            if para and re.search(_PARAPHRASE[para], binding):
                bound.append((token, _PARAPHRASE[para], tm.start(), tm.end(), "event" if para in _EVENT_PARAPHRASE else None, False, 0))
                continue
            hit = None
            for c in cands:
                if len(c) >= 2 and c.lower() in compact:
                    # 술어 여부는 어떤 경로로 맞았는지가 아니라 어절 모양으로 정한다(어절 전체 일치도 사건 틀을 거친다).
                    kind = "event" if (_PRED_REST.match(token[len(c):]) or looks_pred) else None
                    hit = (r"\s*".join(re.escape(ch) for ch in c), kind, False, len(c))
                    break
                if len(c) == 1 and "가" <= c <= "힣" and _VERBAL_REST.match(token[1:]):
                    pattern = r"(?<![가-힣])" + re.escape(c) + r"[가-힣]"
                    if re.search(pattern, binding):
                        hit = (pattern, "event" if c not in _NON_EVENT_PRED else None, True, 1)
                        break
            if hit:
                bound.append((token, hit[0], tm.start(), tm.end(), hit[1], hit[2], hit[3]))
            else:
                unknown.append(token)
        if unknown:
            return False, "core_hold:unsupported_content:" + ",".join(unknown[:3]), len(bound)
        # 원문 절 하나를 거의 그대로 옮긴 문장은 해석이 아니라 복사다.
        tokens = _content_tokens(s)
        src_tokens = _content_tokens(self.post_text)
        if tokens and len(tokens - src_tokens) <= 1 and any(
            len(_content_tokens(c)) and tokens <= _content_tokens(c) | {"작성자", "글쓴이"} for c in self.clauses
        ):
            return False, "core_drop:source_copy", len(bound)
        # 부정: 묶인 어절의 부정 여부가 원문과 같아야 한다(존재 술어는 사건 틀에서 따로 본다).
        for token, needle, start, end, kind, _, _ in bound:
            if kind == "exist":
                continue
            occ = [(m.start(), m.end()) for m in re.finditer(needle, binding, re.I)]
            if not occ:
                continue
            e_neg = _negated_at(body, start, end)
            s_neg = [_negated_at(binding, a, b) for a, b in occ]
            if (e_neg and not any(s_neg)) or (not e_neg and all(s_neg)):
                return False, f"core_hold:polarity_mismatch:{token}", len(bound)
        # 절 결속: 묶인 어절은 한 근거 단위(원문 절 또는 댓글 하나)와 제목 안에 함께 있어야 한다.
        # 근거 단위(원문 절·댓글 절)마다 그 화자 단위의 현재 작품 문맥을 함께 둔다.
        windows = [(c + " / " + self.window_title, lv) for c, lv in zip(clauses, ctxs)]
        good = [(w, lv) for w, lv in windows if all(re.search(b[1], w, re.I) for b in bound)]
        if proof is not None:
            proof["bound"] = [(b[0], b[1]) for b in bound]
            proof["good"] = [i for i, (w, _) in enumerate(windows) if all(re.search(b[1], w, re.I) for b in bound)]
        if bound and not good:
            return False, "core_hold:cross_clause_composition", len(bound)
        scope_windows = good or windows
        # 태도: 태도 단서가 같은 대상을 가리키는 연결 절 안에 있어야 한다. 공동 귀속이면 댓글에서도 같은 대상이어야 한다.
        needles = [b[1] for b in bound]
        s_unc = bool(_UNCERTAIN_EXPERT.search(s))
        scope_index = (proof["good"] if good else list(range(len(windows)))) if proof is not None else []
        for token, group, t_start in stances:
            aspects = _stance_aspects(body, t_start)
            found: Optional[list] = [] if proof is not None else None
            hit = next((k for k, (w, lv) in enumerate(scope_windows)
                        if self._stance_supported(group, w, aspects, needles, s_unc, lv, proof=found)), None)
            if hit is None:
                return False, f"core_hold:stance_unbound:{token}", len(bound)
            if proof is not None:
                proof.setdefault("stances", []).append((token, group, "summary_window", scope_index[hit], found))
            # 같은 평가 목표에 반대 극성 단서도 있으면(작품 전체 호평인데 전개는 별로) 엇갈린 평가로 보고 보류한다.
            opposite = {"pos": "neg", "neg": "pos"}.get(group)
            if opposite and aspects:
                for w, lv in scope_windows:
                    for seg in _evaluation_segments(w):
                        if opposite in _cue_polarity(seg) and group not in _cue_polarity(seg) and any(
                                _target_in(seg, i, o, *reversed(self._live_for(lv, [o] if o else []))) for i, o in aspects):
                            return False, f"core_hold:stance_conflict:{token}", len(bound)
            joint_found: Optional[list] = [] if proof is not None else None
            joint_hit = (next((k for k, (u, lv) in enumerate(zip(self.comment_units, self.comment_unit_ctx))
                               if self._stance_supported(group, u, aspects, needles, s_unc, lv, proof=joint_found)), None)
                         if joint and group != "neutral" else -1)
            if joint and group != "neutral" and joint_hit is None:
                return False, f"core_hold:speaker_unbound:{token}", len(bound)
            if proof is not None and joint_hit is not None and joint_hit >= 0:
                proof.setdefault("stances", []).append((token, group, "joint_comment_unit", joint_hit, joint_found))
        # 존재 극성: '있다/없다'를 뒤집지 않는다.
        if _EXPERT_EXIST.search(body) and all(_SRC_NONEXIST.search(w) and not _SRC_EXIST.search(w) for w, _ in scope_windows):
            return False, "core_hold:polarity_mismatch:있다", len(bound)
        if _EXPERT_NONEXIST.search(body) and not any(_SRC_NONEXIST.search(w) for w, _ in scope_windows):
            return False, "core_hold:polarity_mismatch:없다", len(bound)
        # 양태(술어 없는 요지): 묶인 원문 절이 모두 질문·불확실이면 요지도 질문·불확실로 남아야 한다.
        touched = [c for c in clauses if any(re.search(b[1], c, re.I) for b in bound)]
        uncertain = [c for c in touched if (_is_question(c) or _UNCERTAIN_SRC.search(c)) and not _RHETORICAL.search(c)]
        if proof is not None:
            proof["touched"] = [i for i, c in enumerate(clauses) if any(re.search(b[1], c, re.I) for b in bound)]
            proof["modality"] = ("no_touched_window" if not touched else "assertive_source" if len(uncertain) != len(touched)
                                 else "uncertain_source_with_uncertain_summary" if _UNCERTAIN_EXPERT.search(s)
                                 else "uncertain_source_without_uncertain_summary")
        if touched and len(uncertain) == len(touched) and not _UNCERTAIN_EXPERT.search(s):
            return False, "core_hold:modality_mismatch", len(bound)
        # 사건 틀: 사실 술어(일반·존재)마다 주어·목적어·여격이 맞는 원문 출현에서 극성·태·양태를 비교한다.
        checked = 0
        for token, needle, start, end, kind, onechar, stem_len in bound:
            if not kind:
                continue
            e_args = _expert_frame(body, start)
            e_neg = _negated_at(body, start, end)
            e_val = (token[0] == "있") != e_neg if kind == "exist" else None
            e_next = body[start + stem_len:start + stem_len + 1] if stem_len else ""
            e_pass = bool(stem_len and kind == "event" and _PASSIVE_AFTER.match(body[start + stem_len:]))
            # B33(H10): 요지 어절의 성립 문맥(원문 출현과 같은 판정 함수).
            e_real = _agreement_act_detail(body, start, end).realization
            verdict = None
            for c in clauses:
                for c_args, c_neg, c_next, c_pass, c_unc, c_val, c_seg, c_real in _source_frames(c, needle, exist=(kind == "exist")):
                    if not _args_aligned(e_args, c_args, c_seg, self.title):
                        verdict = verdict or "event_relation_mismatch"
                        continue
                    if (kind == "exist" and e_val != c_val) or (kind == "event" and e_neg != c_neg):
                        verdict = "polarity_mismatch"
                        continue
                    if kind == "event" and stem_len and (
                        (onechar and (e_next in _CAUSATIVE_NEXT) != (c_next in _CAUSATIVE_NEXT)) or e_pass != c_pass
                    ):
                        verdict = "predicate_voice_mismatch"
                        continue
                    if c_unc and not _UNCERTAIN_EXPERT.search(s):
                        verdict = "modality_mismatch"
                        continue
                    # B33(H10): 원문 출현이 조건문 안의 술어면 요지도 같은 조건이거나 불확실성을 밝혀야 한다.
                    if c_real == "conditional" and e_real != "conditional" and not _UNCERTAIN_EXPERT.search(s):
                        verdict = "modality_mismatch"
                        continue
                    verdict = "ok"
                    break
                if verdict == "ok":
                    break
            if verdict != "ok":
                return False, f"core_hold:{verdict or 'event_relation_mismatch'}:{token}", len(bound)
            checked += 1
        # 검사 완료 추적: 사실 술어로 분류된 어절은 모두 사건 틀 검사를 통과해야 한다.
        if checked != sum(1 for b in bound if b[4]):
            return False, "core_hold:unchecked_claim", len(bound)

        # 역할: 요지가 붙인 인물·작가 역할은 그 이름마다의 근거가 있어야 한다.
        pairs = ([(m.group(1), m.group(2)) for m in _ROLE_BEFORE.finditer(s)]
                 + [(m.group(2), m.group(1)) for m in _ROLE_AFTER.finditer(s)]
                 + [(m.group(2), m.group(1)) for m in _ROLE_PRED.finditer(s)])
        if _ROLE_WORD_ANY.search(s):
            named_pairs = {n for _, n in pairs}
            pairs += [(rw.group(0), n) for rw in _ROLE_WORD_ANY.finditer(s) for n in self.known_names
                      if n in s and n not in named_pairs]
        for role_word, name in pairs:
            name = _PARTICLE_END.sub("", re.sub(r"(?:의|와|과)$", "", name))
            if len(name) < 2 or name in _GENERIC_WORDS or any(name in t for t in self.allowed_titles if t not in self.post_text):
                continue
            if role_word == "작가":
                basis = _author_basis(name, self.source, self.signals)
            else:
                basis = _character_basis(name, self.source, self.signals)
            if not basis:
                return False, f"core_hold:role_unbound:{name}", len(bound)
        count = len({b[0] for b in bound})
        if count < 2:
            return False, "core_drop:not_source_bound", count
        return True, "", count


def _known_names(signals: ExpertSignals) -> Tuple[str, ...]:
    names = [n for n in signals.person_names if n]
    names += [str(e.get("text") or "").strip() for e in signals.entity_mentions or ()
              if str(e.get("entity_type") or "") in {"character", "author"}
              or str(e.get("role") or "") in {"character_focus", "author_focus"}]
    names += [s for s, role in signals.role_evidence if role in {"character", "author"}]
    return tuple(dict.fromkeys(n for n in names if len(n) >= 2))


def _core_meaning(source: ClaimScopeSource, signals: ExpertSignals, state: RowState, clauses: Sequence[str], act: str, *,
                  native: Optional["NativeProjectionCollector"] = None):
    post_text = " ".join(source.post_lines)
    allowed_titles = {s for s in signals.named_work_surfaces if s}
    if state.resolved_title:
        allowed_titles.add(state.resolved_title)
    binder = _Binder(source, signals, state, act, clauses, native=native)
    person_names = _known_names(signals)
    kept: List[str] = []
    held: List[Tuple[str, str]] = []
    reasons: List[str] = []

    def record(field_name, index, raw_span, sentence, s, decision, reason, scope_reason="", count=-1, hedged=False, proof=None,
               projection_field="", projection_index=-1):
        # B33: 호출별 native 수집기가 있을 때만 생성 요지 문장의 실제 판정을 남긴다. 판정 흐름은 바꾸지 않는다.
        if native is not None:
            native.decisions.append(NativeCoreDecision(field_name, index, sentence, raw_span, s, decision, reason, scope_reason,
                                                       count, hedged, projection_field, projection_index, proof))

    for field_name, raw in (("post_intent", signals.post_intent), ("synthesis_summary", signals.synthesis_summary)):
        spans = _core_sentence_spans(str(raw or "")) if native is not None else ()
        for index, sentence in enumerate(_CORE_SENTENCE_SPLIT.split(str(raw or ""))):
            raw_span = spans[index] if index < len(spans) else (-1, -1)
            s = re.sub(r"^\[[^\]]{1,20}\]\s*", "", sentence.strip())
            hedged = False
            if _HEDGED_PAREN.search(s):
                s = _HEDGED_PAREN.sub("", s)
                reasons.append("core_strip:hedged_parenthetical")
                hedged = True
            if len(s) < 8 or len(s) > 200:
                record(field_name, index, raw_span, sentence, s, "skipped_length", "", hedged=hedged)
                continue
            if _TEMPLATE_PHRASES.search(s):
                reasons.append("core_drop:template_or_meta")
                record(field_name, index, raw_span, sentence, s, "dropped", "core_drop:template_or_meta", hedged=hedged)
                continue
            if any(t not in post_text and t not in allowed_titles for t in _QUOTED_TITLE.findall(s)):
                reasons.append("core_drop:title_not_in_source")
                record(field_name, index, raw_span, sentence, s, "dropped", "core_drop:title_not_in_source", hedged=hedged)
                continue
            # claim_scope는 필요조건일 뿐이다. no_scoped_claim은 지지 근거로 세지 않는다.
            scope = check_note_sentence(s, source, person_names)
            if not scope.supported:
                reasons.append("core_drop:claim_scope")
                record(field_name, index, raw_span, sentence, s, "dropped", "core_drop:claim_scope", scope.reason, hedged=hedged)
                continue
            if native is not None:
                ok, why, count, proof = binder.bind_with_proof(s)
            else:
                (ok, why, count), proof = binder.bind(s), None
            if not ok:
                reasons.append(":".join(why.split(":")[:2]))
                if why.startswith("core_hold"):
                    held.append((why, s))
                    record(field_name, index, raw_span, sentence, s, "held", why, scope.reason, count, hedged, proof,
                           "held_meaning", len(held) - 1)
                else:
                    record(field_name, index, raw_span, sentence, s, "dropped", why, scope.reason, count, hedged, proof)
                continue
            toks = _content_tokens(s)
            if any(len(toks & _content_tokens(k)) >= 0.6 * max(1, min(len(toks), len(_content_tokens(k)))) for k in kept):
                reasons.append("core_drop:duplicate")
                record(field_name, index, raw_span, sentence, s, "dropped", "core_drop:duplicate", scope.reason, count, hedged, proof)
                continue
            if s not in kept:
                kept.append(s)
                reasons.append(f"core_keep:bound={count};scope={scope.reason}")
                record(field_name, index, raw_span, sentence, s, "kept", f"core_keep:bound={count};scope={scope.reason}",
                       scope.reason, count, hedged, proof, "core_meaning", len(kept) - 1)
            else:
                record(field_name, index, raw_span, sentence, s, "dropped", "core_drop:already_kept_exact", scope.reason, count,
                       hedged, proof)
            if len(kept) >= 2:
                return tuple(kept), tuple(held), reasons
    return tuple(kept), tuple(held), reasons


# ---------------------------------------------------------------------------
def project_context(source: ClaimScopeSource, signals: ExpertSignals, state: RowState, *,
                    native: Optional["NativeProjectionCollector"] = None) -> ContextProjection:
    """공개 투영. B33: native는 keyword-only 호출별 수집기다. 없으면 기존과 같고, 있으면 같은 pass의 Binder·원장·manifest·
    RowState·요지 판정·결속 증거·작성자 절 좌표·channel 출처를 그 수집기에 남긴다. 공개 반환값은 native 유무와 무관하게 같다."""
    if native is not None:
        if native.calls:
            raise ValueError("NativeProjectionCollector는 project_context 호출마다 새로 만든다")
        native.calls += 1
        native.source, native.signals, native.state = source, signals, state
        native.manifest = native_source_manifest(source, native.carrier) if native.carrier is not None else None
    clauses = _author_clauses(source)
    named = tuple(s for s in signals.named_work_surfaces if s)
    live_named, _ = _live_surfaces(named, clauses)
    characters = _character_names(signals)
    # B33: native가 있을 때만 같은 pass의 producer 분기·원문 위치를 적는 기록이다. 판정에는 쓰지 않는다.
    act_trace: Optional[dict] = {} if native is not None else None
    ref_trace: Optional[list] = [] if native is not None else None
    ex_trace: Optional[list] = [] if native is not None else None
    media_trace: Optional[dict] = {} if native is not None else None
    cond_trace: Optional[list] = [] if native is not None else None
    act, kind, surface, span, reasons = _speech_act(source, signals, clauses, trace=act_trace)
    reasons = list(reasons)
    conditions: Tuple[str, ...] = ()
    references: Tuple[str, ...] = ()
    excluded: Tuple[str, ...] = ()
    roles: List[Tuple[str, str, str]] = []
    if surface and kind == "named_work":
        roles.append((surface, "evaluation_target" if act == "evaluation_question" else "discussed", "named_work_surface"))
    elif surface and kind == "evaluated_item":
        roles.append((surface, "evaluation_target", "source_span"))
    if act == "recommendation_request":
        # B33 R3/R3d(E6): 같은 pass 작성자 절 중 부인·계획·반사실 요청 절과 요청 인용의 틀 절을 뺀 조건 앞 6개다. 비현재 요청 표현
        # 뒤 tail로 현재 요청을 고른 절은 그 tail만 조건이고, cond_trace에 같은 범위(절 index, 시작, 끝)를 남긴다.
        conditions = _request_condition_clauses(source, clauses, trace=cond_trace)[:6]
        ex_pairs, ex_held = _excluded_works(clauses, named, characters, trace=ex_trace)
        title_terms = tuple(t for t in signals.title_term_surfaces if t)
        ref_pairs, ref_held = _reference_works(clauses, live_named, characters, title_terms, trace=ref_trace)
        excluded = tuple(t for t, _ in ex_pairs)
        ref_pairs = tuple((t, b) for t, b in ref_pairs if t not in excluded)
        # reference_works에는 작품 표면 입력으로 뒷받침되는 기준작만 둔다. 원문 비교 표현만 있는 표면은 work_roles로만 남긴다.
        references = tuple(t for t, b in ref_pairs if b == "named_work_surface")
        roles += [(t, "reference", b) for t, b in ref_pairs] + [(t, "excluded", b) for t, b in ex_pairs]
        reasons += ex_held + ref_held
    media, media_span = _target_media(clauses, trace=media_trace)
    kind_from_media = media != "unknown" and kind in {"trope", "unknown"}
    if kind_from_media:
        kind = "other_media"
    core, held, core_reasons = _core_meaning(source, signals, state, clauses, act, native=native)
    reasons += core_reasons
    kept, drops = filter_entity_roles(signals.entity_mentions, source, state, signals)
    allow_char = any(
        str(e.get("entity_type") or "") == "character" or str(e.get("role") or "") == "character_focus" for e in kept
    )

    scope_hint = None
    trope_state = str(state.subtype or "") == "genre_trope_discussion" or str(state.discussion_type or "") == "trope_discussion"
    if media != "unknown":
        scope_hint = "cross_media"
    elif act == "evaluation_question" and kind == "named_work":
        scope_hint = "core_unresolved"
    elif trope_state and state.is_novel_related is not False and str(state.topicality or "").lower() != "adjacent_relevant":
        scope_hint = "adjacent"
    elif live_named and str(state.topicality or "").lower() == "unrelated":
        scope_hint = "core_unresolved"

    fallback = act == "unknown" and not core and media == "unknown"
    if native is not None:
        relation_table, relation_where = _relation_table_detail(named, clauses)
    else:
        relation_table, relation_where = _relation_table(named, clauses), ()
    projection = ContextProjection(
        speech_act=act, target_kind=kind, target_surface=surface, target_span=span,
        request_conditions=conditions, reference_works=references, excluded_works=excluded,
        work_roles=tuple(roles),
        target_media=media, media_span=media_span, scope_hint=scope_hint,
        core_meaning=core, held_meaning=held, entity_role_drops=drops, kept_entities=kept,
        allow_character_reaction_phrase=allow_char, reasons=tuple(reasons), fallback=fallback,
        work_relation_evidence=relation_table,
    )
    if native is not None:
        native.projection = projection
        records, skips, alignment = _native_author_clause_records(source, clauses, native.manifest)
        native.author_clauses, native.author_clause_skips, native.author_clause_alignment = records, skips, alignment
        native.channel_values = _native_channel_values(source, projection, records, native.manifest, act_trace, kind_from_media,
                                                       ref_trace, ex_trace, media_trace, relation_where, cond_trace)
    return projection


_ACT_KO = {
    "evaluation_question": "평가 질문", "recommendation_request": "추천 요청", "question": "질문",
    "opinion": "의견", "joke": "농담",
}
_KIND_KO = {"trope": "장르·트로프", "community": "커뮤니티", "conditions": "요청 조건"}
_MEDIA_KO = {"manga": "만화", "webtoon": "웹툰", "anime": "애니", "film": "영화", "game": "게임"}


def render_context_block(projection: ContextProjection, *, include_conditions: bool = True,
                         target_label: Optional[str] = None,
                         target_surface_occurrence: Optional[Sequence[str]] = None) -> Optional[str]:
    """typed 투영을 독자용 한국어 블록으로 만든다. fallback이면 None.

    include_conditions=False는 호출자가 이미 작성자 조건 블록을 붙인 행에서 원문 조건 중복을 막는다.
    조건 줄은 원문 절을 그대로 옮긴 것이라 의미 개선으로 세지 않는다. 보류한 해석(held_meaning)은 싣지 않는다.
    """
    if projection.fallback:
        return None
    lines = ["[발화 해석]"]
    if projection.speech_act in _ACT_KO:
        lines.append(f"- 발화 유형: {_ACT_KO[projection.speech_act]}")
    if target_label:
        lines.append(f"- 대상: {target_label}")
    elif projection.target_kind == "named_work" and projection.target_surface:
        raw_words = ((target_surface_occurrence,) if isinstance(target_surface_occurrence, str)
                     else tuple(target_surface_occurrence or ()))
        if raw_words and any(word != projection.target_surface for word in raw_words):
            words = " / ".join(repr(word) for word in raw_words)
            lines.append(f"- 대상: 원문 어절 {words}(후보 표면 '{projection.target_surface}', 이름·조사 경계 미확정)")
        elif raw_words:
            lines.append(f"- 대상: 작품명 표면 '{projection.target_surface}'(원문 표면)")
        else:
            lines.append(f"- 대상: 후보 표면 '{projection.target_surface}'(원문 어절 경계 미확정)")
    elif projection.target_kind == "author_new_work" and projection.target_surface:
        lines.append(f"- 대상: {projection.target_surface}의 이름 미상 신작(원문 작가→신작 관계)")
    elif projection.target_kind == "work_new_work" and projection.target_surface:
        relation = _new_work_head_match(projection.target_surface, projection.target_span or '')
        head = relation.group('head') if relation else '신작'
        lines.append(f"- 대상: {projection.target_surface}에 연결된 제목 미상 {head}(원문 작품→신작 관계)")
    elif projection.target_kind == "author" and projection.target_surface:
        lines.append(f"- 대상: 작가 표면 '{projection.target_surface}'(원문 인물 관계)")
    elif projection.target_kind == "evaluated_item" and projection.target_surface:
        lines.append(f"- 대상: 평가 대상 표면 '{projection.target_surface}'(공식 작품 식별 미확정)")
    elif projection.target_kind == "other_media" and projection.target_media in _MEDIA_KO:
        lines.append(f"- 대상 매체: {_MEDIA_KO[projection.target_media]}")
    elif projection.target_kind in _KIND_KO:
        lines.append(f"- 대상: {_KIND_KO[projection.target_kind]}")
    if include_conditions and projection.request_conditions:
        lines.append("- 작성자 조건: " + " / ".join(projection.request_conditions)[:400])
    if projection.reference_works:
        lines.append("- 기준작 표면: " + ", ".join(f"'{r}'" for r in projection.reference_works) + "(작품 표면 입력)")
    unverified = [t for t, role, basis in projection.work_roles if role == "reference" and basis != "named_work_surface"]
    if unverified:
        lines.append("- 비교 기준 표면: " + ", ".join(f"'{r}'" for r in unverified) + "(작품 여부 미확인)")
    if projection.excluded_works:
        lines.append("- 제외(이미 읽음 등) 표면: " + ", ".join(f"'{r}'" for r in projection.excluded_works))
    for sentence in projection.core_meaning:
        lines.append(f"- 요지: {sentence}")
    # 대상·조건·요지 없이 발화 유형만 남는 질문·의견 블록은 정보가 없으므로 붙이지 않는다.
    if len(lines) == 2 and projection.speech_act in {"question", "opinion", "evaluation_question"}:
        return None
    return "\n".join(lines) if len(lines) > 1 else None
