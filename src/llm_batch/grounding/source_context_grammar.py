"""exact 원문 claim의 질문·전언·조건·평가 범위를 읽는 유한 문법."""

from __future__ import annotations

from dataclasses import dataclass, field

import re

from typing import Any, Tuple

def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

@dataclass(frozen=True)
class GapFragment:
    rule: str
    sentence: str
    destination: str                 # reason / note / suppress_praise
    evidence_quotes: Tuple[str, ...]
    predicate_spans: Tuple[Tuple[int, int], ...] = ()  # 각 claim raw_text 기준
    unresolved: Tuple[str, ...] = ()
    counts_as_core: bool = False
    publication_authority: bool = False
    unit_objects: Tuple[Any, ...] = field(default=(), compare=False, repr=False)
    proof_objects: Tuple[Any, ...] = field(default=(), compare=False, repr=False)
    primary_subject: str = ""
    primary_role: str = ""             # relation / purpose / reaction

_APP = re.compile(r"\s*-\s*dc\s*(?:official\s*)?App\s*$", re.I)

_PAST_Q = re.compile(r"(?:[?？]|라고|냐고).{0,45}(?:물어본|물었|물어봤|질문했|질문한).{0,25}(?:첫글|기억|예전|당시)|(?:첫글|예전|당시).{0,35}(?:물었|물어봤|질문했)")

_REPORT_SURFACE = re.compile(r"(?:라고|다고)\s*(?:한다|함|하더라|들었|들음)|(?:라는데|다는데|다던데|다더라|다함)(?=$|[\s.!?ㅋ])")

_CONDITION = re.compile(r"(?:라면|다면|으면|했으면|였으면|일\s*경우|할\s*경우|한다고\s*치면|했을\s*때)")

_QUESTION = re.compile(r"[?？]|(?:뭐임|뭐냐|뭘까|누가\s*있나|어떻게|어케|왜\s*이리|볼만함|재밌냐|재밌나|좋나요|좋나|좋냐|괜찮나|가능함|다름)\s*[.!~… ]*$")

_NEGATION = re.compile(r"(?:안|못)\s*(?:좋|재밌|읽|보겠|보았|봄|봤)|(?:좋|재밌|재미\s*있).{0,12}(?:않|아니)|(?:없|싫|별로|노잼)")

_RETRACT = re.compile(r"(?:취소|철회|정정)(?:함|한다|할게|할께|합니다)?|(?:그건|그거|그말|그\s*말)\s*(?:아니|틀렸)|아니\s*(?:방금|아까|앞서)")

_READ_LIMIT = re.compile(r"(?:중도)?하차|접었|손\s*떼|초반.{0,20}(?:읽|보)|(?:거기|그\s*부분|그\s*지점).{0,15}안\s*읽")

_EVAL_Q = re.compile(r"(?P<topic>.+?)\s*(?P<predicate>볼만함|재밌(?:냐|나|나요|음)|읽을\s*만(?:함|했|한)|괜찮(?:나|음)|좋(?:냐|나|나요))\s*[?？.!~… ]*$")

_ORIGIN_Q = re.compile(r"(?P<topic>.+?)\s+(?P<origin>[^\s?？]{1,25})발\s*(?:작품|소설)(?:이었|였|임|인가|맞)?(?:음|나|냐)?\s*[?？.!~… ]*$")

_FIRST_Q = re.compile(r"(?P<topic>.+?)\s*(?:뭐임|뭐였음|뭐였나|뭐였냐|뭐냐)\s*[?？.!~… ]*$")

_COMPARE_Q = re.compile(r"(?P<left>[^\s?？]+?)(?:이랑|랑|하고|와|과)\s+(?P<right>[^\s?？]+?)(?:이랑|랑|하고|와|과)?\s+(?:뭐가\s*다름|어떻게\s*다름|차이가\s*뭐|뭐가\s*더).*[?？]$")

_OTHER_ACTOR = re.compile(r"^(?:친구|지인|동생|형|누나|언니|그|그녀|댓글\s*작성자)(?:는|가|이|:|：)")

_THANKS = re.compile(r"고맙|고마워|감사")

def exact_nominal_binding_text(source, claim):
    """명사 인용만 가린 own claim의 기존 binding view를 검산한다.

    전언·화면 문구·기록 인용을 복원하지 않는다. 원장/claim은 변경하지 않는다.
    """
    text = source.text
    if (claim.kind != "own" or claim.speaker != "self" or not claim.final_support
            or _get(claim, "attribution") != "direct_clause"
            or _get(claim, "quote_frame_status") != "not_quote"
            or tuple(claim.span) != (0, len(text))
            or _get(claim, "binding_text") != text or _get(claim, "binding_offset") != 0):
        return None
    views = tuple(_get(source, "parser_views", ()))
    by_id = {_get(v, "view_id"): v for v in views}
    if len(by_id) != len(views):
        return None
    act = by_id.get(_get(claim, "text_view_id"))
    binding = by_id.get(_get(claim, "binding_view_id"))
    raw = next((v for v in views if _get(v, "view_kind") == "raw_clause"), None)
    if (act is None or binding is None or raw is None
            or _get(act, "view_kind") != "act_masked"
            or _get(binding, "view_kind") != "binding_masked"
            or any(_get(v, "offset") != 0 for v in (act, binding, raw))
            or raw.text != text or binding.text != text
            or _get(raw, "masked_spans") or _get(binding, "masked_spans")):
        return None
    masks = tuple(_get(act, "masked_spans", ()))
    quotes = tuple(tuple(span) for span in _get(source, "parser_quotes", ()))
    if not masks:
        return None
    expected, end = list(text), 0
    for start, stop, role, replacement in masks:
        if (role != "nominal_argument" or replacement != "space"
                or not (end <= start < stop <= len(text)) or (start, stop) not in quotes):
            return None
        expected[start:stop] = " " * (stop - start)
        end = stop
    masked = "".join(expected)
    if (act.text != masked or claim.text != masked.strip()
            or _get(claim, "text_offset") != len(masked) - len(masked.lstrip())):
        return None
    return text

def exact_unit(unit) -> bool:
    """원후보의 검증 결과 위에 raw span과 원장/claim 객체를 다시 확인한다."""
    try:
        p = unit.proof
        origin, source, claim, ledger = p.origin_object, p.source_object, p.claim_object, p.ledger_object
        lo, hi = p.raw_span
        a, z = claim.span
        view_ok = (source.text[a:z] == claim.text == unit.text
                   if _get(p, "claim_view", "claim") == "claim" else
                   _get(p, "claim_view") == "nominal_binding"
                   and exact_nominal_binding_text(source, claim) == unit.text)
        return bool(p.document_object is not None and p.manifest_object is not None
                    and any(origin is x for x in p.manifest_object.lines)
                    and any(source is x for x in ledger.sources)
                    and any(claim is x for x in ledger.claims)
                    and p.source_id == source.source_id == claim.source_id
                    and p.claim_id == claim.claim_id
                    and p.raw_path == source.raw_path == origin.raw_path
                    and 0 <= lo < hi <= len(origin.raw_text)
                    and origin.raw_text[lo:hi] == p.sourcequote == unit.text
                    and 0 <= a < z <= len(source.text) and view_ok)
    except (AttributeError, IndexError, TypeError, ValueError):
        return False

def _text(unit):
    return _APP.sub("", unit.text).strip()

def _frag(rule, sentence, destination, units, matches=(), unresolved=(), *,
          primary_subject="", primary_role=""):
    # matches=(unit, re.Match)라서 술어 좌표는 exact claim의 raw 좌표로 환원된다.
    spans = []
    for u, m in matches:
        start = u.text.find(m.string)
        if start < 0 or start != u.text.rfind(m.string):
            raise ValueError("exact contiguous grammar view is ambiguous")
        spans.append((u.proof.raw_span[0] + start + m.start(),
                      u.proof.raw_span[0] + start + m.end()))
    return GapFragment(rule, sentence, destination, tuple(u.text for u in units), tuple(spans),
                       tuple(unresolved), unit_objects=tuple(units),
                       proof_objects=tuple(u.proof for u in units),
                       primary_subject=primary_subject, primary_role=primary_role)

def praise_scope(unit, projection=None) -> Tuple[str, str]:
    """원 reducer의 일반 praise loop 이전에 사용할 보수적인 admission 판단."""
    if not exact_unit(unit):
        return "unsupported", "U: exact 원문 결속 없음"
    text = _text(unit)
    if _PAST_Q.search(text) or _get(unit, "record_kind") == "past_recollection":
        return "past_question", "과거에 물었던 질문을 회상한 내용"
    if _QUESTION.search(text) or _get(unit, "source_question", False):
        return "question", "현재 평가를 단정하지 않는 질문"
    if _RETRACT.search(text):
        return "retracted", "앞선 판단을 정정·철회하는 표현"
    if _CONDITION.search(text):
        return "conditional", "조건이나 가정을 둔 표현"
    if _REPORT_SURFACE.search(text):
        return "reported_surface", "원문에서 전하는 형태로 표현한 내용"
    if unit.proof.claim_kind == "reported" or not _get(unit, "current_own", False):
        return "unresolved_attribution", "U: 원장의 귀속 라벨만으로 전해들은 사실·현재 태도 확정 불가"
    if _OTHER_ACTOR.search(text):
        return "other_actor", "글쓴이 자신의 현재 평가인지 불명확"
    # '이라도 좋아/도 괜찮다'의 좋아는 작품에 대한 질 평가가 아니라 허용 범위다.
    allowance = re.search(r"(?:이라도|라도|여도|이어도|도)\s*(?:좋아|좋다|괜찮|상관\s*없|가능)", text)
    if allowance and _get(projection, "speech_act") == "recommendation_request":
        return "request_allowance", "추천 대상으로 허용하는 범위"
    if re.search(r"(?:기분|컨디션|몸\s*상태|마음)\s*(?:이|은|가)?\s*(?:좋|나쁘)", text):
        return "personal_state", "화자 자신의 기분·상태"
    if _THANKS.search(text):
        return "gratitude", "감사 표현이며 평가·전면 동의와 별개"
    if _NEGATION.search(text):
        return "negated", "부정된 평가·미독서·싫다는 표현"
    if _READ_LIMIT.search(text):
        return "reading_limit", "부분 독서·하차로 한정된 경험"
    # 서술형 검증을 통과한 이후에만 원모듈의 구체 내용+평가 술어 규칙을 적용한다.
    for event in unit.proof.event_objects:
        if (_get(event, "realization") in {"question", "modal", "reported", "conditional", "embedded"}
                or _get(event, "final_support") is not True
                or _get(event, "actor") not in {None, "", "self"}):
            return "event_scope_hold", "U: native 평가 event의 화자·성립 범위"
    return "affirmative_candidate", "구체 내용의 affirmative 평가 후보; 이후 원문 술어 검증 필요"

def neutral_attribution_note(unit):
    """reported enum만으로 실제 청취·전달 사건을 덧붙이지 않는다."""
    if not exact_unit(unit):
        return None
    text = _text(unit)
    evidence = (unit,)
    if _PAST_Q.search(text):
        return _frag("past_embedded_question", "과거에 물었던 내용을 회상한 문장으로, 지금 같은 질문을 다시 했다고 확정하지 않는다.", "note", evidence)
    q, condition, report = _QUESTION.search(text), _CONDITION.search(text), _REPORT_SURFACE.search(text)
    if q:
        subject = text.rstrip("?？.!~… ")
        return _frag("neutral_question_frame", f"{subject}라는 질문을 제시한다. 이 질문을 전해 들은 사실로 확정하지 않는다.", "note", evidence, ((unit, q),))
    if condition:
        return _frag("neutral_condition_frame", f"{text.rstrip('.')}는 조건을 둔 생각이다. 이미 일어난 일이나 화자의 확정 평가로 바꾸지 않는다.", "note", evidence, ((unit, condition),))
    if report:
        return _frag("explicit_report_surface", f"{text.rstrip('.')}는 원문에서 전하는 형태로 표현한 내용이다. 직접 경험이나 외부 사실의 확인은 별개다.", "note", evidence, ((unit, report),))
    if unit.proof.claim_kind == "reported":
        return _frag("enum_attribution_unresolved", "이 구간은 원장에 reported로 표시되지만 원문 표면만으로 전언 사건·화자 관계를 확정할 수 없다.", "note", evidence,
                     unresolved=("U: 귀속 라벨과 원문 문법의 관계",))
    return None

def platform_consequence_question_fragment(unit):
    """명시된 플랫폼 처리 질문을 vague 제목의 읽기 평가보다 우선한다."""
    if not exact_unit(unit) or not unit.current_own or unit.reported:
        return None
    text = _text(unit)
    if (_PAST_Q.search(text) or unit.record_kind == "past_recollection"
            or _REPORT_SURFACE.search(text) or _CONDITION.search(text)):
        return None
    m = re.search(r"(?:플랫폼|연재처|서비스)(?:에서|가|은|는)\s*불이익(?:을)?\s*(?:안\s*)?(?:주|받)[^.!?？]*[?？]", text)
    if m is None:
        return None
    return _frag("current_platform_consequence_question",
        f"「{m.group(0)}」라고 플랫폼의 처리나 불이익 가능성을 묻는다. 실제 제재가 발생했다고 확정하지 않는다.",
        "reason", (unit,), ((unit, m),), ("U: 실제 플랫폼 정책·불이익 발생·공식 작품",))


_POINTED_HARASSMENT_QUESTION = re.compile(
    r"^(?:<-|←)\s*(?:이러면|이거(?:는|도)?|이\s*말(?:은|도)?)\s+"
    r"성희롱(?:임|인가|이냐|이야|인가요|에\s*해당함|에\s*해당하나|되는\s*거임)"
    r"\s*[?？][\sㅋㅎ]*$"
)


def current_propriety_question_fragment(preceding, question):
    """바로 앞 작성자 문장을 가리키는 성희롱 여부 질문만 결속한다."""
    if not all(exact_unit(unit) and unit.current_own and not unit.reported
               and unit.role == "author" for unit in (preceding, question)):
        return None
    before_source, question_source = preceding.proof.source_object, question.proof.source_object
    if (before_source.source_origin != "body_line" or question_source.source_origin != "body_line"
            or before_source.source_index + 1 != question_source.source_index
            or preceding.proof.document_object is not question.proof.document_object
            or preceding.proof.manifest_object is not question.proof.manifest_object
            or preceding.proof.ledger_object is not question.proof.ledger_object
            or _get(preceding.proof.claim_object, "quote_frame_status") not in (None, "not_quote")
            or _get(question.proof.claim_object, "quote_frame_status") not in (None, "not_quote")):
        return None
    before, pointed = _text(preceding), _text(question)
    if (not 2 <= len(before) <= 120 or preceding.source_question or _QUESTION.search(before)
            or _REPORT_SURFACE.search(before) or _CONDITION.search(before)
            or _PAST_Q.search(pointed) or _REPORT_SURFACE.search(pointed)
            or _CONDITION.search(pointed)):
        return None
    match = _POINTED_HARASSMENT_QUESTION.fullmatch(pointed)
    if match is None:
        return None
    sentence = (f"글쓴이는 바로 앞 표현 「{before}」이 성희롱에 해당하는지 묻는다. "
                "질문만으로 실제 성희롱 여부를 확정하지 않는다.")
    return _frag("current_pointed_harassment_question", sentence, "reason",
                 (preceding, question), ((question, match),),
                 ("U: 실제 성희롱 여부",),
                 primary_subject="앞 표현의 성희롱 해당 여부를 묻는 질문.", primary_role="relation")


def current_question_fragment(unit, projection=None):
    """현재 질문의 구체 목적만 설명한다. title만 있어도 exact own claim이면 가능."""
    if not exact_unit(unit) or not _get(unit, "current_own", False):
        return None
    text = _text(unit)
    if _PAST_Q.search(text) or _get(unit, "record_kind") == "past_recollection":
        return None
    if _REPORT_SURFACE.search(text) or _CONDITION.search(text):
        return None
    m = _ORIGIN_Q.fullmatch(text)
    if m and (_QUESTION.search(text) or _get(unit, "source_question", False)):
        topic = re.sub(r"^(?:아니|근데)\s+", "", m.group("topic"))
        origin = m.group("origin")
        return _frag("work_origin_question", f"{topic}가 {origin}에서 나온 작품인지 확인하려는 질문이다. 질문의 전제만으로 그 출처를 확정하지 않는다.", "reason", (unit,), ((unit, m),),
                     ("U: 공식 작품명과 실제 기원",))
    m = _EVAL_Q.fullmatch(text)
    # bare '재밌음'은 질문 표지가 없으면 평가 질문으로 바꾸지 않는다.
    if m and (_QUESTION.search(text) or _get(unit, "source_question", False)):
        if m.group("predicate").startswith(("괜찮", "좋")):
            return _frag("current_appropriateness_question",
                f"「{m.group(0)}」라고 적절성을 묻는다. 판단 기준이나 읽기 목적은 이 질문만으로 확정하지 않는다.",
                "note", (unit,), ((unit, m),), ("U: 적절성의 기준·행동 대상",))
        return _frag("current_evaluation_question", f"「{m.group(0)}」라고 읽기·재미 판단을 구한다. 질문 자체는 호평이나 이미 읽었다는 증거가 아니다.", "reason", (unit,), ((unit, m),),
                     ("U: 공식 제목·답변의 대표성",))
    m = _FIRST_Q.fullmatch(text)
    if m and re.search(r"첫글|첫\s*글|경험", m.group("topic")):
        topic = re.sub(r"^(?:님들은|너희는|다들)\s*", "", m.group("topic")).strip()
        return _frag("personal_experience_question", f"다른 참여자의 {topic} 경험을 묻는다.", "reason", (unit,), ((unit, m),))
    m = _COMPARE_Q.fullmatch(text)
    if m:
        return _frag("explicit_comparison_question", f"「{m.group('left').strip()}」, 「{m.group('right').strip()}」 두 표면의 차이를 묻는다. 두 대상을 같은 것으로 확정하는 말은 아니다.", "reason", (unit,), ((unit, m),))
    return None

def state_or_allowance_fragment(unit, projection=None):
    scope, _ = praise_scope(unit, projection)
    if scope not in {"request_allowance", "personal_state", "retracted", "reading_limit"}:
        return None
    text = _text(unit)
    if scope == "request_allowance":
        m = re.search(r"(.+?)(?:이라도|라도|여도|이어도|도)\s*(?:좋아|좋다|괜찮|상관\s*없|가능)", text)
        return _frag("allowance_not_work_praise", f"{m.group(1).strip()}도 추천 범위로 허용한다. 그 범주의 실제 작품을 읽고 좋게 평가했다는 뜻으로 확대하지 않는다.", "note", (unit,), ((unit, m),))
    if scope == "personal_state":
        # 기분 앞에 있는 비교 기준 등은 기존 work_roles가 별도 exact 검산한다.
        return _frag("personal_state_not_work_quality", "화자는 자신의 기분·상태를 말한다. 작품 내용에 대한 구체적인 질 평가와는 구분한다.", "note", (unit,),
                     unresolved=("U: 기분의 원인을 작품 평가로 연결하는 범위",))
    if scope == "retracted":
        return _frag("local_retraction", "이 구간은 앞선 판단의 정정·철회를 표현한다. 앞의 긍정 평가를 그대로 최종 태도로 세지 않는다.", "note", (unit,),
                     unresolved=("U: 철회 대상 span은 native adoption/lifecycle로 별도 결속",))
    media = re.search(r"웹툰판|소설판|만화판|번역판|원작", text)
    prefix = media.group(0) if media else "이 구간에 언급된 대상"
    return _frag("media_reading_limit", f"{prefix}의 읽기 경험을 초반·부분 독서·중도하차 범위로 말한다. 다른 판본이나 완독 감상으로 확대하지 않는다.", "note", (unit,),
                 unresolved=("U: 특정 작품·판본의 공식 연결 및 완독 여부",))

def current_vs_past_question_fragment(past_unit, all_units):
    """현재 질문과 본문의 과거 질문 회상을 같은 질문으로 합치지 않는다."""
    if not exact_unit(past_unit) or not _get(past_unit, "current_own", False):
        return None
    text = _text(past_unit)
    if not _PAST_Q.search(text) or "첫글" not in text:
        return None
    current = next((u for u in all_units if u is not past_unit and exact_unit(u)
                    and _get(u, "current_own", False) and "첫글" in u.text
                    and _FIRST_Q.fullmatch(_text(u)) and not _PAST_Q.search(u.text)), None)
    if current is None:
        return None
    # 장소·옛 질문 표면은 실제 문장에 명시된 경우에만 가져온다.
    m = re.search(r"(?P<place>[^\s?？]{1,25}(?:갤러리|갤))에\s*(?P<prompt>[^?？]{1,80}[?？])\s*라고\s*물어본", text)
    if m:
        sentence = (f"지금은 다른 참여자의 첫글 경험을 묻는다. 본문은 {m.group('place')}에 "
                    f"{m.group('prompt')}라고 물었던 글이 자신의 첫글이었다는 회상이며, "
                    "옛 질문을 현재의 작품 평가 질문으로 옮기지 않는다.")
        return _frag("current_vs_past_first_question", sentence, "reason", (current, past_unit), ((past_unit, m),))
    return _frag("current_vs_past_first_question", "지금은 다른 참여자의 첫글 경험을 묻고, 본문은 과거에 질문했던 글이 자신의 첫글이었다고 회상한다. 두 질문의 시점을 합치지 않는다.",
                 "reason", (current, past_unit), unresolved=("U: 과거 질문의 세부 대상·장소",))
