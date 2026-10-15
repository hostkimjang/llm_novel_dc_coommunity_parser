"""원문 native 객체에서만 공개 문맥 설명을 환원한다.

LLM prose, 공식명, 문화풀이를 입력으로 소비하지
않는다. 출처가 없는 관계는 U이며, 이 결과는 generated core나 공개 권한이 아니다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Iterable, Tuple
from .source_context_grammar import (praise_scope, neutral_attribution_note,
    current_question_fragment, platform_consequence_question_fragment,
    state_or_allowance_fragment, current_vs_past_question_fragment,
    current_propriety_question_fragment,
    exact_unit, exact_nominal_binding_text, _frag)
from .source_work_purpose import (work_genre_purpose_fragments,
    is_recommendation_request_text, surface_role_predicate, praise_relation_fragment)
from .source_everyday_purpose import everyday_purpose_fragments
from .source_request_purpose import reduce_request_roles
from .source_speech_structure import source_speech_fragments, _is_question as source_current_question


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _same_member(item: Any, items: Iterable[Any]) -> bool:
    return any(item is other for other in items)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SnippetProof:
    rule: str
    source_id: str
    claim_id: str
    raw_path: str
    raw_span: Tuple[int, int]
    sourcequote: str
    source_sha256: str
    claimant: str
    claim_kind: str
    final_support: bool
    predicate_spans: Tuple[Tuple[int, int], ...] = ()
    event_ids: Tuple[str, ...] = ()
    # eq=False: 동일 내용의 새 객체가 원래 객체 인증으로 대체되지 않는다.
    document_object: Any = field(default=None, compare=False, repr=False)
    manifest_object: Any = field(default=None, compare=False, repr=False)
    origin_object: Any = field(default=None, compare=False, repr=False)
    ledger_object: Any = field(default=None, compare=False, repr=False)
    source_object: Any = field(default=None, compare=False, repr=False)
    claim_object: Any = field(default=None, compare=False, repr=False)
    comment_object: Any = field(default=None, compare=False, repr=False)
    event_objects: Tuple[Any, ...] = field(default=(), compare=False, repr=False)
    claim_view: str = "claim"


@dataclass(frozen=True)
class SourceExplanation:
    primary_subject: str = ""
    reason_sentences: Tuple[str, ...] = ()
    note_sentences: Tuple[str, ...] = ()
    proofs: Tuple[SnippetProof, ...] = ()
    unresolved: Tuple[str, ...] = ()
    supported: bool = False
    counts_as_core: bool = False
    publication_authority: bool = False
    source_kind: str = "deterministic_source_context"
    input_identity: Tuple[int, ...] = ()
    input_fingerprint: str = ""


@dataclass(frozen=True)
class _Unit:
    text: str
    role: str
    original_index: int
    current_own: bool
    reported: bool
    record_kind: str
    source_question: bool
    proof: SnippetProof


_TAIL = re.compile(r"\s*(?:-\s*dc\s*(?:official\s*)?App|(?:ㅇㅇ|ㅋㅋ|ㄷㄷ)+)\s*$", re.I)
_QUESTION = re.compile(r"(?:어떻게|어케|없냐|추천(?:해|좀)|볼만함|궁금|어떰|어때|[?？]|(?:좋|재밌)(?:나|냐|니|나요|은가|습니까)[.!~ ]*$)")
_REPORT = re.compile(r"(?:라는데|다는데|다던데|다더라|다고\s*(?:함|하|들)|생긴다함|전해|들었)")
_CONDITIONAL = re.compile(r"(?:라면|다면|으면|했으면|였으면|한다면|보면|쓰면|할\s*수\s*있으면)")
_NEG_PRAISE = re.compile(r"(?:안\s*(?:좋|재밌)|좋[^.!?]{0,8}(?:않|아니)|재밌[^.!?]{0,8}(?:않|아니))")
_SURPRISE = re.compile(r"의외(?:였|임|다|네|였음)|놀(?:랐|라)")
_PRAISE = re.compile(r"좋(?:구나|다|음|네|았|아)|재밌(?:다|네|음|었)|재미\s*있")
_THANKS = re.compile(r"고맙|고마워|감사")
_NOT_READ = re.compile(r"(?:거기|그기|그\s*부분|그\s*지점).*?안\s*읽|(?:안|못)\s*읽어?\s*봤|안\s*읽었")
_READ = re.compile(r"읽어?\s*봤|읽었|봤는데")
_NOT_WRITE = re.compile(r"(?:안\s*써\s*봤|안써봐|안\s*써봐|아얘안써|아예\s*안\s*써)")
_OTHER_ACTOR = re.compile(r"^(?:친구|지인|동생|형|누나|언니|그|그녀|댓글\s*작성자)(?:는|가|이|:|：)")
_WORK_QUOTE = r'(?P<open>[「『“\"\'])(?P<surface>[^「」『』“”\"\'\n]+)(?P<close>[」』”\"\'])'
_EXPLICIT_COMMENT_RECOMMENDATION = (
    re.compile(r"\s*(?:추천\s*작품|추천작|추천\s*소설)(?:은|는|:|：)\s*" + _WORK_QUOTE + r"(?:이다|입니다|임)?[.!。 ]*"),
    re.compile(r"\s*" + _WORK_QUOTE + r"(?:이라는|라는)\s*(?:작품|소설)(?:을|를)?\s*추천(?:한다|합니다|함)[.!。 ]*"),
)


def source_explicit_comment_recommendation(unit):
    """exact 댓글의 작품 naming과 긍정 추천 술어가 함께 있을 때만 관계를 읽는다."""
    p = unit.proof
    if (not exact_unit(unit) or unit.role != "comment" or not unit.current_own
            or unit.reported or unit.source_question or p.comment_object is None
            or p.claim_kind != "own" or p.claimant != "self" or not p.final_support):
        return None
    if any(_get(e, "realization") in {"question", "modal", "reported", "conditional", "embedded"}
           or _get(e, "actor") not in {None, "", "self"}
           or _get(e, "final_support") is not True for e in p.event_objects):
        return None
    pairs = {"「": "」", "『": "』", "“": "”", '"': '"', "'": "'"}
    for pattern in _EXPLICIT_COMMENT_RECOMMENDATION:
        hit = pattern.fullmatch(unit.text)
        if hit and pairs[hit.group("open")] == hit.group("close"):
            return hit.group("surface").strip() or None
    return None


def _clean(text: str) -> str:
    cleaned = _TAIL.sub("", text).strip()
    # 독립된 익명 표면 'ㅇㅇ'도 실제 내용이다. 꼬리 제거로 빈 값이 되면 보존한다.
    return cleaned if cleaned else text.strip()


def _topic(text: str) -> str:
    """내용을 더하지 않는 유한 어미 환원. 완결 부정/조건 절은 자르지 않는다."""
    text = _clean(text).rstrip(".!?。！？~… ")
    return re.sub(r"(?:한게|한\s*게)$", "한 점", text)


def _has_conditional(text: str) -> bool:
    """관용적인 재고 표현의 '보면'은 조건절로 취급하지 않는다."""
    return bool(_CONDITIONAL.search(re.sub(r"생각해\s*보면", "", text)))


def _source_headline_desire_fragment(units):
    """제목의 정도 부사를 제외하고 명시된 주인공 유형과 선호 술어를 묶는다."""
    title = next((u for u in units if u.role == "author" and u.current_own and not u.reported
                  and u.proof.source_object.source_origin == "post_title"
                  and _get(u.proof.claim_object, "quote_frame_status") in (None, "not_quote")
                  and exact_unit(u)), None)
    if title is None or title.source_question:
        return None
    text = _clean(title.text)
    if _REPORT.search(text) or _has_conditional(text) or _QUESTION.search(text):
        return None
    match = re.fullmatch(
        r"(?:(?:뭔가|좀|왠지|괜히)\s+)?(?P<wanted>[^.!?。！？\n]{2,80}?\s*주인공)(?:이|가)\s+"
        r"(?:땡김|끌림|보고\s*싶음)[.!。 ]*", text)
    if match is None:
        return None
    wanted = match.group("wanted").strip()
    if not wanted or re.search(r"(?:안|못)\s*(?:보고|좋|땡)|[「『“\"']", wanted):
        return None
    sentence = (f"글쓴이는 제목에서 {wanted}에 대한 선호를 밝힌다. "
                "원문의 선호를 특정 작품의 설정이나 이미 읽은 경험으로 확정하지 않는다.")
    return _frag("source_exact_headline_desire", sentence, "reason", (title,), ((title, match),),
                 primary_subject=f"{wanted}에 대한 선호.", primary_role="purpose")


def _source_adjacent_shock_recollection(units):
    """원문 제목의 회상, 인접 본문 내용, 충격과 책임 부정 단서를 함께 읽는다."""
    author = [u for u in units if u.role == "author" and u.current_own and not u.reported
              and _get(u.proof.claim_object, "quote_frame_status") in (None, "not_quote")
              and exact_unit(u)]
    title = next((u for u in author if u.proof.source_object.source_origin == "post_title"
                  and re.search(r"(?:생각나|기억나|떠오르)", _clean(u.text))
                  and not (u.source_question or _QUESTION.search(u.text)
                           or _REPORT.search(u.text) or _has_conditional(u.text))), None)
    if title is None:
        return None
    body = [u for u in author if u.proof.source_object.source_origin == "body_line"]
    if len(body) != 2 or body[1].proof.source_object.source_index != body[0].proof.source_object.source_index + 1:
        return None
    content, reaction = body
    mention = re.fullmatch(r"(?P<scene>[^.!?。！？\n]{4,120}?(?:한|했던)\s+거)[.!。 ]*", _clean(content.text))
    caveat = re.fullmatch(
        r"(?P<denial>[^.!?。！？\n]{2,60}?\s+저지른\s+(?:일은|건)\s+아니(?:긴\s+한데|지만))\s+"
        r"(?P<shock>(?:너무\s+)?충격적이었(?:음|다|어))[.!。 ]*", _clean(reaction.text))
    if mention is None or caveat is None or any(
            _REPORT.search(u.text) or _has_conditional(u.text) or u.source_question for u in body):
        return None
    if not any("충격" in e.predicate and e.actor == "self" and e.final_support is True
               and e.realization in {"actual", "past", "contrast"} for e in reaction.proof.event_objects):
        return None
    scene = mention.group("scene").strip()
    denial = caveat.group("denial").strip()
    sentence = (f"글쓴이는 제목에서 떠오른 일을 본문의 「{scene}」로 가리키고 충격적이었다고 회고한다. "
                f"그러면서 「{denial}」라는 단서를 두어 지칭 인물이 저질렀다는 판단은 부정한다. "
                "작품·인물의 정체와 사건의 실제 발생은 이 말로 확인되지 않는다.")
    return _frag("source_adjacent_shock_recollection", sentence, "reason", (title, content, reaction),
                 ((content, mention), (reaction, caveat)),
                 ("U: 지칭 인물·작품 정체와 사건의 외부 사실 여부",),
                 primary_subject=f"본문에 언급한 「{scene}」에 대한 충격과 행위자 책임 부정.",
                 primary_role="relation")


def _source_new_work_critique_fragment(units):
    """작가→신작 관계 아래에 원문 비판이 이어지면 관계명보다 비판 요지를 앞세운다."""
    title = next((u for u in units if u.role == "author" and u.current_own and not u.reported
                  and u.proof.source_object.source_origin == "post_title" and exact_unit(u)), None)
    if title is None:
        return None
    head = re.fullmatch(
        r"(?P<author>[0-9A-Za-z가-힣]{2,20})\s+신작\s+"
        r"(?P<target>[0-9A-Za-z가-힣]{2,30})(?:이|가|은|는)\s+너무\s+"
        r"(?P<evaluation>좆같|불쾌|싫|별로|아쉽)[^?？\n]{0,20}", _clean(title.text))
    if head is None:
        return None
    body = [u for u in units if u.role == "author" and u.current_own and not u.reported
            and u.proof.source_object.source_origin == "body_line" and exact_unit(u)]
    appearance = next((u for u in body if u.proof.source_object.source_index == 0
                       and re.search(r"(?:생겨|보여)야지|못생|안\s*생|(?:외모|얼굴|모습).{0,18}(?:별로|불쾌|싫|아쉽|좆같)", u.text)), None)
    target = head.group("target")
    other_character = next((u for u in body if re.search(r"남주|주인공", u.text)
                            and not re.search(re.escape(target) + r"(?:은|는|이|가|도)?\b", u.text)
                            and re.search(r"싫|병신|불쾌|별로|아쉽", u.text)), None)
    rationale = next((u for u in body if re.search(r"(?:개연성|설득력).{0,12}(?:없|부족|떨어|모자라)|그래야.{0,100}(?:개연성|설득력).{0,12}생기", u.text)), None)
    if appearance is None or other_character is None or rationale is None:
        return None
    # 첫 본문 줄이 다른 인물을 명시하면 제목 대상의 외모로 전이하지 않는다.
    appearance_text = _clean(appearance.text)
    appearance_hit = re.search(r"(?:생겨|보여)야지|못생|안\s*생|외모|얼굴|모습", appearance_text)
    appearance_prefix = appearance_text[:appearance_hit.start()] if appearance_hit else appearance_text
    named_other = re.search(r"(?<![0-9A-Za-z가-힣])(?P<name>남주|주인공|여주|히로인|빌런|조연|서브남)(?:은|는|이|가|도|의)?(?=\s|$)", appearance_prefix)
    if named_other and named_other.group("name") != target:
        return None
    evidence = []
    for unit in (title, appearance, other_character, rationale):
        if not any(unit is seen for seen in evidence):
            evidence.append(unit)
    author = head.group("author")
    sentence = (f"글쓴이는 {author}의 원문에 제목을 쓰지 않은 신작에서 {target}의 외모·묘사를 비판하고, "
                "다른 주요 인물의 묘사와 전개의 개연성에도 불만을 말한다. "
                "이는 작성자의 평가이며 작품의 실제 설정이나 공식 제목을 확인한 사실은 아니다.")
    return _frag("source_new_work_critique", sentence, "reason", tuple(evidence), ((title, head),),
                 primary_subject=f"{author}의 원문에 제목을 쓰지 않은 신작에서 {target}의 묘사와 다른 주요 인물·개연성에 대한 비판적 감상.",
                 primary_role="relation")


def _source_headline_fragment(units):
    """생성 요지가 없어도 exact 작성자 제목의 발화 기능을 설명한다.

    제목의 사실관계·작품명은 확정하지 않는다. 본문은 같은 화자의 exact own claim일 때만
    명시적인 감정 표지에 한해 보조 근거로 쓴다.
    """
    title = next((u for u in units if u.role == "author" and u.current_own and not u.reported
                  and _get(u.proof.claim_object, "quote_frame_status") in (None, "not_quote")
                  and u.proof.source_object.source_origin == "post_title" and exact_unit(u)), None)
    if title is None:
        return None
    text = _clean(title.text)
    if len(text) < 5 or len(text) > 120:
        return None
    reason_question = bool(re.search(r"(?:왜|어째서).{0,30}(?:많|적|늘|줄)", text))
    if (_REPORT.search(text) or _OTHER_ACTOR.search(text)
            or (_has_conditional(text) and not source_current_question(title))):
        return None
    own_body = [u for u in units if u.role == "author" and u.current_own
                and u is not title and exact_unit(u)]
    body = next((u for u in own_body if re.search(
        r"사랑해|ㄷㄷ|싫어|못보겠|좀\s*그렇|미친|중독|병신|보게\s*생겼|설마|아니겠지|혐짤.{0,8}참았|있는\s*듯",
        u.text)), None)
    support_body = body
    if source_current_question(title) or reason_question:
        if re.search(r"\d+\s*연참", text):
            subject = "연속 연재 가능성을 묻는 질문."
            explanation = "글쓴이는 제목에서 연속 연재의 가능성을 묻는다. 본문의 애정 표현이 실제 연재 소식을 확인해 주지는 않는다."
        elif re.search(r"가성비|비용|가격", text):
            subject = "비용·가성비에 관한 질문."
            explanation = "글쓴이는 제목에서 비용이나 가성비에 대한 평가를 묻는다. 본문에 금액이 있어도 가성비 결론을 내린 것으로 바꾸지 않는다."
        elif reason_question:
            subject = "제목에서 제기한 수량·변화의 이유 질문."
            explanation = "글쓴이는 제목에서 자신이 본 수량이나 변화의 이유를 묻는다. 그 수량이나 변화가 객관적으로 확인됐다고 단정하지 않는다."
        elif _has_conditional(text) or re.search(r"(?:오면|되면|가면|하면)", text):
            subject = "가정 속 가능성을 묻는 질문."
            explanation = "글쓴이는 제목에서 조건을 둔 가능성을 묻는다. 조건의 결과를 이미 일어난 사실로 확정하지 않는다."
        else:
            subject = "제목에서 제기한 질문."
            explanation = "글쓴이는 제목에서 답을 묻는다. 질문의 전제를 확인된 사실로 채택하지 않는다."
    elif re.search(r"\d+\s*연참", text) and body is not None and "사랑해" in body.text:
        subject = "연속 연재 소식에 대한 환호와 애정 표현."
        explanation = "글쓴이는 제목의 연속 연재 횟수에 환호하고 본문에서 애정을 표현한다. 이미지 내용이나 호명된 사람의 공식 역할은 이 문장만으로 확정하지 않는다."
    elif re.search(r"미래.{0,8}보이|벌써.{0,12}보이", text) and body is not None and "ㄷㄷ" in body.text:
        subject = "앞으로의 전개를 예상하며 놀라는 반응."
        explanation = "글쓴이는 제목에서 앞으로의 흐름을 예상하고 본문의 감탄 표현으로 놀라움을 드러낸다. 실제 전개나 복선의 내용은 확정하지 않는다."
    elif (re.search(r"비중.{0,14}없.{0,16}(?:웃겼|어이없|황당|아쉽)", text)
          and (re.search(r"좆도|어이없|황당|아쉽", text)
               or any(not u.reported
                      and re.search(r"(?:했|였|인데|였는)는데", u.text)
                      and re.search(r"(?:전적|활약|역할|비중).{0,32}(?:끝|뿐|없|적)", u.text)
                      for u in own_body))):
        subject = "작중 인물의 적은 비중을 비꼬거나 비판하는 의견."
        contrast = next((u for u in own_body if not u.reported
                         and re.search(r"(?:했|였|인데|였는)는데", u.text)
                         and re.search(r"(?:전적|활약|역할|비중).{0,32}(?:끝|뿐|없|적)", u.text)), None)
        support_body = contrast
        explanation = "글쓴이는 제목에서 작중 인물의 비중이 적다는 점을 웃겼다고 표현하며 비판한다. "
        if contrast is not None:
            explanation += "본문에서는 큰 설정에 견줘 전적·활약이 제한됐다는 이유를 덧붙인다. "
        explanation += "이는 글쓴이의 평가이며 인물 설정이나 전적의 외부 사실 여부는 확인하지 않는다."
    elif ((re.search(r"또\s+\S+.{0,8}(?:세우|하)", text)
           and body is not None and re.search(r"싫어|못보겠|미친|중독|병신", body.text))
          or re.search(r"나락|싫어|못보겠|좀\s*그렇|병신", text)):
        subject = "제목에 나타난 비판적 의견."
        explanation = "글쓴이는 제목에서 대상을 비판적으로 평가한다. 평가의 외부 사실 여부나 원문에 없는 동기는 확정하지 않는다."
    elif re.search(r"가성비|비용|가격|만원", text):
        subject = "비용과 가성비에 관한 작성자의 평가."
        amount = next((u for u in own_body if re.search(r"\d+\s*(?:만\s*원|원)", u.text)), None)
        support_body = amount
        explanation = ("글쓴이는 제목에서 취미 비용의 가성비를 평가하고 본문에서 자신이 쓴 금액을 근거로 든다. "
                       if amount is not None else "글쓴이는 제목에서 비용에 대한 자신의 평가를 제시한다. ")
        explanation += "비용의 실제 수준이나 다른 사람의 동의는 이 표현만으로 확정하지 않는다."
    elif re.search(r"(?:느낌|같[음다은]|듯)", text):
        subject = "제목에 나타난 비유·인상."
        contrast = next((u for u in own_body if re.search(r"이미\s*아는|다른\s*플레이|다른\s*감상", u.text)), None)
        support_body = contrast
        explanation = ("글쓴이는 제목에서 비유로 의견을 표현하고 본문에서 이미 아는 내용과 다른 경험을 대비한다. "
                       if contrast is not None else "글쓴이는 제목에서 비유나 인상으로 의견을 표현한다. ")
        explanation += "비유의 내용을 실제 동일성이나 확인된 사실로 바꾸지 않는다."
    elif re.search(r"(?:설마|아니겠지|려나|될까|이면|오면)", text):
        subject = "가정이나 가능성에 관한 생각."
        explanation = "글쓴이는 제목에서 가정이나 가능성을 제시한다. 가정의 결과를 이미 일어난 사실로 확정하지 않는다."
    elif re.search(r"(?:!{2,}|사랑해|ㄷㄷ)", text):
        subject = "제목의 강조·감탄 표현."
        explanation = "글쓴이는 제목에서 감탄이나 강조를 드러낸다. 강조만으로 사건의 진위나 작품의 정체를 확정하지 않는다."
    elif re.search(r"(?:보통임|많[음다]|좋[음다]|그렇긴|듯)", text):
        subject = "제목에 나타난 작성자의 의견."
        explanation = "글쓴이는 제목에서 자신의 의견을 밝힌다. 다른 사람에게도 그대로 적용되는 사실로 확정하지 않는다."
    elif re.search(r"(?:보렴|와서|해줘|해주세요)", text):
        subject = "제목에서 상대를 부르거나 요청하는 발화."
        explanation = "글쓴이는 제목에서 상대를 부르거나 행동을 요청한다. 상대의 실제 반응이나 첨부 이미지의 내용은 확정하지 않는다."
    elif body is not None and re.search(r"(?:보게\s*생겼|설마|아니겠지)", body.text):
        subject = "본문에 나타난 추측·상상."
        explanation = "글쓴이는 본문에서 가능성을 상상한다. 첨부 이미지의 내용이나 상상 속 사건을 확인된 사실로 확정하지 않는다."
    elif body is not None and re.search(r"혐짤.{0,8}참았", body.text):
        subject = "이미지에 관한 작성자의 자제 표현."
        explanation = "글쓴이는 본문에서 혐짤을 참았다고 말한다. 게시를 자제했는지 보기를 참았는지, 실제 첨부 이미지의 내용은 이 표현만으로 알 수 없다."
    elif body is not None and re.search(r"많은데|많지만", text) and re.search(r"더\s*많", body.text):
        subject = "제목과 본문을 이은 비교 의견."
        explanation = "글쓴이는 제목의 수량 표현을 본문에서 다른 대상으로 비교한다. 그 수량이나 평가가 객관적으로 확인됐다고 단정하지 않는다."
    elif body is not None and re.search(r"몰라도|모르겠지만", text) and re.search(r"있는\s*듯", body.text):
        subject = "앞뒤 내용을 대비한 추측."
        explanation = "글쓴이는 제목의 판단을 유보하고 본문에서 다른 가능성을 추측한다. 두 판단의 내용을 확인된 사실로 확정하지 않는다."
    else:
        return None
    # 원문 표면을 남겨 독자가 어떤 발화를 환원했는지 확인할 수 있게 한다.
    sentence = f"{explanation} 근거가 된 제목 표현은 「{text}」이다."
    evidence = (title, support_body) if support_body is not None else (title,)
    return _frag("source_exact_headline_speech", sentence, "reason", evidence,
                 primary_subject=subject, primary_role="purpose")


def _source_title_body_relation(units):
    """같은 작성자의 제목과 인접 본문이 함께 밝힌 발화 관계만 읽는다."""
    def uncorrected(unit):
        tail = unit.proof.origin_object.raw_text[unit.proof.raw_span[1]:]
        return not re.match(r"^[\s.!?…。]*?(?:아니|아냐|취소|철회|사실은)(?:\s|[.!?]|$)", tail)

    title = next((u for u in units if u.role == "author" and u.current_own
                  and not u.reported and exact_unit(u)
                  and u.proof.source_object.source_origin == "post_title"
                  and _get(u.proof.claim_object, "quote_frame_status") in (None, "not_quote")), None)
    if title is None:
        return None
    body = [u for u in units if u.role == "author" and u.current_own
            and not u.reported and exact_unit(u)
            and u.proof.source_object.source_origin == "body_line"
            and u.original_index in (0, 1)
            and uncorrected(u)
            and _get(u.proof.claim_object, "quote_frame_status") in (None, "not_quote")]
    if not body or _REPORT.search(title.text):
        return None
    title_text = _clean(title.text)

    # 제목의 비교 대상이 본문에서 생략된 경우에도, 동일 화자의 인접 조건절에만 묶는다.
    fictional_gods = re.search(r"((?:창작물|작품|소설|만화)(?:에|에서| 속).{0,12}?(?:신들|신격들|신))", title_text)
    ai = next((u for u in body if re.search(r"(?:초인공지능|인공지능|AI).{0,20}\d+\s*년만\s*있으면\s*따위로\s*만들듯", u.text)), None)
    negated_weakness = re.search(r"(?:좆밥|약하|하찮)\s*(?:이|은|가|도|지)\s*(?:아니|않|아님|아닌)", title_text)
    if (fictional_gods and ai is not None and not negated_weakness
            and re.search(r"(?:좆밥|약하|하찮|별거\s*아니)", title_text)):
        target = fictional_gods.group(1)
        return _frag("source_title_body_conditional_comparison",
            f"글쓴이는 제목의 「{target}」을 낮게 평가하며, 본문에서는 미래 초인공지능이 그 대상을 하찮게 만들 수 있다고 가정·추측한다. 이는 실제 미래에 관한 확인된 사실이 아니다.",
            "reason", (title, ai), primary_subject=f"{target}과 미래 초인공지능을 비교한 가정적 의견.",
            primary_role="relation")

    # 취향의 대상은 마지막 성격 평가 하나가 아니라, 앞줄의 행위 관계까지 포함한다.
    pretext = next((u for u in body if re.search(
        r"수\s*핑계로\s*공\s*협박해서\s*따먹는\s*게.{0,12}(?:꼴려|좋|맛있)", u.text)
        and not source_current_question(u)
        and not re.search(r"(?:안|못|별로|싫).{0,8}(?:꼴려|좋|맛있)|(?:꼴리|좋|맛있).{0,8}(?:않|아니|못)", u.text)), None)
    if (pretext is not None and re.search(r"공을\s*따먹는\s*게.{0,12}(?:맛있|좋|꼴리)", title_text)
            and not source_current_question(title)):
        trait = next((u for u in body if u is not pretext and re.search(r"공들은?.{0,28}(?:좋|꼴리)", u.text)), None)
        evidence = (title, pretext, trait) if trait is not None else (title, pretext)
        detail = " 공들의 성격이 더 좋다는 평가도 덧붙인다." if trait is not None else ""
        return _frag("source_title_body_preference_relation",
            "글쓴이는 수를 핑계로 공을 협박해서 따먹는 관계 구도를 선호한다고 말한다."
            + detail + " 이는 서사 취향에 관한 표현이다.",
            "reason", evidence, primary_subject="수를 핑계로 공을 협박하는 관계 구도에 대한 취향 표현.",
            primary_role="relation")

    religion = re.search(r"(?P<name>[가-힣]{2,12})\s+또\s+종교\s+세우(?:네|나|냐|는)", title_text)
    cult = next((u for u in body if re.search(r"사이비\s*교주", u.text)
                 and re.search(r"미친|중독|싫|병신|좆", u.text)
                 and not re.search(r"사이비\s*교주.{0,24}(?:아니|아님|않|아닙)", u.text)), None)
    if religion and cult is not None and not source_current_question(title):
        name = religion.group("name")
        explicit_subject = re.search(
            r"(?<![가-힣A-Za-z0-9])(?P<subject>[가-힣A-Za-z0-9]{2,15})(?:은|는|이|가)\s+(?:\S+\s+){0,3}사이비\s*교주",
            cult.text)
        if explicit_subject is None or explicit_subject.group("subject") == name:
            return _frag("source_title_body_repeated_religion_critique",
                f"글쓴이는 제목에서 「{name}」이 또 종교를 세운다고 말하고, 본문에서 사이비 교주라는 표현으로 그 반복 행동을 비판한다. 작중 사실이나 인물의 공식 역할은 이 발화만으로 확정하지 않는다.",
                "reason", (title, cult), primary_subject=f"{name}의 반복적인 종교 설립을 비판하는 글쓴이의 의견.",
                primary_role="relation")

    contest = re.search(r"(?:소설\s*)?리뷰\s*대회.{0,24}(?:아무도\s*관심\s*안\s*주|관심(?:이|을)?\s*없)", title_text)
    enjoyed = next((u for u in body if re.fullmatch(
                        r"(?:(?:이\s*)?(?:소설\s*)?리뷰\s*대회(?:는|가)?\s*)?재밌(?:는데|다|음|어)",
                        _topic(u.text))
                    and not _NEG_PRAISE.search(u.text)
                    and not source_current_question(u)), None)
    why = next((u for u in body if re.search(r"왜\s*안\s*보", u.text)
                and source_current_question(u)
                and enjoyed is not None and u.original_index == enjoyed.original_index), None)
    if contest and enjoyed is not None and why is not None and not source_current_question(title):
        return _frag("source_title_body_attention_lament",
            "글쓴이는 소설 리뷰대회에 관심이 없다고 아쉬워하며, 본문에서는 재미있다는 자신의 평가를 덧붙이고 왜 보지 않느냐고 되묻는다. 실제 관심도나 그 이유가 확인된 것은 아니다.",
            "reason", (title, enjoyed, why),
            primary_subject="소설 리뷰대회에 관심을 주지 않는다는 한탄과 긍정적 감상.",
            primary_role="relation")

    ranking = re.search(r"^(?P<surface>[가-힣A-Za-z0-9]{2,20})\s+고증이\s+.{0,35}?(?:노피아|노벨피아).{0,20}?(?:하더만|했더니|하다가)\s*(?P<rank>\d+)\s*위\s*(?:먹었|했|됐)", title_text)
    if ranking and not source_current_question(title):
        surface = ranking.group("surface")
        rank = ranking.group("rank")
        cheer = next((u for u in body if re.fullmatch(r"(?:캬|와|오|ㄷㄷ|ㅋㅋ)+[!~. ]*", _clean(u.text))), None)
        evidence = (title, cheer) if cheer is not None else (title,)
        reaction = " 본문에서도 짧게 감탄한다." if cheer is not None else ""
        return _frag("source_title_body_rank_reaction",
            f"글쓴이는 「{surface}」에 관한 앞선 고증·노피아 언급과 대비해 {rank}위에 올랐다고 반응한다.{reaction} 순위의 종류와 공식 작품명은 이 원문만으로 확정하지 않는다.",
            "reason", evidence,
            primary_subject=f"{surface}의 순위 소식과 앞선 고증·플랫폼 언급에 대한 반응.",
            primary_role="relation")
    return None


def _source_cost_comment_fragments(units):
    """비용 평가에 붙은 exact 댓글의 반례·예외를 댓글 화자에게만 귀속한다."""
    title = next((u for u in units if u.role == "author" and u.current_own
                  and u.proof.source_object.source_origin == "post_title" and exact_unit(u)
                  and re.search(r"가성비|비용|가격", u.text)
                  and not source_current_question(u)), None)
    if title is None:
        return ()
    # 댓글이 본문 지출 대상을 다시 가리키면 어휘 사전에 없어도 같은 비용 화제다.
    # 숫자만 같은 경우나 다른 화자의 본문은 연결 근거가 아니다.
    amount_target = re.compile(
        r"(?<![가-힣A-Za-z0-9])([가-힣A-Za-z0-9]{2,20}?)(?:은|는|이|가|도|에서|에)?\s+"
        r"\d+\s*(?:만\s*(?:\d+\s*천)?|천)?\s*원")
    source_targets = []
    for author_unit in units:
        if (author_unit.role != "author" or not author_unit.current_own or author_unit.reported
                or author_unit.proof.source_object.source_origin != "body_line" or not exact_unit(author_unit)):
            continue
        for hit in amount_target.finditer(author_unit.text):
            source_targets.append((hit.group(1), author_unit))
    fragments = []
    for unit in units:
        if unit.role != "comment" or not unit.current_own or unit.reported or not exact_unit(unit):
            continue
        text = _clean(unit.text)
        repeated = next(((surface, author_unit) for surface, author_unit in source_targets
                         if re.search(r"(?<![가-힣A-Za-z0-9])" + re.escape(surface)
                                      + r"(?:은|는|이|가|을|를|도|만|에서|에)?(?![가-힣A-Za-z0-9])", text)), None)
        # 같은 대상의 영업시간·상태 주장과 비용 계산의 예외는 다른 관계다.
        cost_exclusion = re.search(
            r"제외|(?:빼|제하).{0,8}(?:계산|가성비|비용)|(?:계산|가성비|비용).{0,8}(?:빼|제하)", text)
        if (cost_exclusion
                and (repeated is not None
                     or re.search(r"가성비|비용|가격|지출|결제|게임|겜|소설\b|취미|가챠|뽑기", text))):
            meaning = "예외를 제시한다"
        elif re.search(r"가성비.{0,6}(?:좀|별로)|(?:가챠|뽑기).{0,20}\d+\s*만\s*원", text):
            meaning = "다른 비용 경험이나 반론을 제시한다"
        else:
            continue
        sentence = f"댓글 {unit.original_index + 1}의 화자는 비용 평가에 대해 {meaning}. 이는 댓글의 말이며 글쓴이의 지출 경험으로 합치지 않는다."
        evidence = (title, repeated[1], unit) if repeated is not None else (title, unit)
        fragments.append(_frag("source_exact_cost_comment_role", sentence, "note", evidence))
    return tuple(fragments)


def _source_fingerprint(native: Any) -> str:
    manifest = native.manifest
    ledgers = (native.author_ledger, *native.comment_ledgers)
    return _digest({
        "lines": [(x.origin, x.normalized_index, x.original_index, x.raw_path,
                   x.selection_key, x.raw_text, x.normalized_text, x.occurrence)
                  for x in manifest.lines],
        "ledger": [(
            l.source_id, tuple(_get(l, "graph_failures", ())),
            [(s.source_id, s.text, s.source_role, s.source_origin, s.source_index,
              s.original_index, s.raw_path, s.selection_key, s.raw_line,
              tuple(s.raw_text_span), s.line_occurrence, s.carrier_alignment,
              tuple((_get(v, "view_id"), _get(v, "view_kind"), _get(v, "text"),
                     _get(v, "offset"), tuple(_get(v, "masked_spans", ())))
                    for v in _get(s, "parser_views", ()))) for s in l.sources],
            [(c.claim_id, c.source_id, c.kind, c.speaker, c.text, tuple(c.span),
              c.final_support, _get(c, "attribution"),
              tuple(_get(c, "active_adoption_event_ids", ())), _get(c, "binding_text"),
              _get(c, "binding_offset"), _get(c, "text_view_id"), _get(c, "binding_view_id"),
              _get(c, "text_offset"), _get(c, "quote_frame_status")) for c in l.claims],
            [(e.event_id, e.claim_id, e.source_id, e.predicate, tuple(e.predicate_span),
              e.realization, _get(e, "actor"), e.final_support, _get(e, "temporal_scope"),
              _get(e, "attribution"), _get(e, "surface_realization"))
             for e in l.evaluations]) for l in ledgers],
        "projection": {
            k: _get(native.projection, k) for k in
            ("speech_act", "target_kind", "target_surface", "request_conditions",
             "reference_works", "excluded_works", "work_roles", "target_media")},
    })


def _input_identity(native: Any) -> Tuple[int, ...]:
    refs = (native, native.source, native.manifest, native.projection, native.signals,
            native.binder, native.author_ledger, *native.comment_ledgers)
    return tuple(map(id, refs))


def _bound_units(native: Any, records: Iterable[Any], comments: Iterable[Any]):
    units, unresolved = [], []
    if (_get(native, "capture_status") != "single_binder"
            or _get(native, "manifest") is None
            or native.manifest.alignment != "exact_enumeration"
            or native.binder is None
            or native.binder.author_ledger is not native.author_ledger
            or native.binder.source is not native.source
            or native.binder.signals is not native.signals):
        return (), ("U: same-pass native 입력 결속 미확인",)
    native_comment_pairs = _get(native.binder, "comment_ledgers", ())
    if (len(native_comment_pairs) != len(native.comment_ledgers)
            or any(pair[1] is not ledger for pair, ledger in
                   zip(native_comment_pairs, native.comment_ledgers))):
        return (), ("U: 댓글 원장 객체 결속 미확인",)
    origins = {(x.origin, x.normalized_index): x for x in native.manifest.lines}
    if len(origins) != len(native.manifest.lines):
        return (), ("U: 원문 occurrence 모호",)
    kinds = {}
    for record in records:
        clause, origin = _get(record, "clause"), _get(record, "origin")
        if not _same_member(clause, native.author_clauses):
            unresolved.append("U: 작성자 절 객체 불일치")
            continue
        if origin is not origins.get((clause.source_origin, clause.source_index)):
            unresolved.append("U: 작성자 절 origin 객체 불일치")
            continue
        lo, hi = clause.text_raw_span
        if not (0 <= lo < hi <= len(origin.raw_text)
                and origin.raw_text[lo:hi] == clause.text
                and _get(record, "text") == clause.text):
            unresolved.append("U: 작성자 절 exact 원문 span 미확인")
            continue
        kinds[(clause.raw_path, tuple(clause.text_raw_span))] = (
            _get(record, "kind", ""), _get(record, "question", False) is True)
    comment_records = {_get(x, "normalized_index"): x for x in comments}
    for ledger in (native.author_ledger, *native.comment_ledgers):
        if _get(ledger, "graph_failures", ()):
            unresolved.append("U: 원장 graph 결속 실패")
            continue
        sources = {s.source_id: s for s in ledger.sources}
        if (len(sources) != len(ledger.sources)
                or len({c.claim_id for c in ledger.claims}) != len(ledger.claims)):
            unresolved.append("U: 원문 source/claim ID 모호")
            continue
        for claim in ledger.claims:
            source = sources.get(claim.source_id)
            if source is None:
                continue
            origin = origins.get((source.source_origin, source.source_index))
            if origin is None or source.carrier_alignment != "exact_enumeration":
                continue
            lo, hi = source.raw_text_span
            if not (source.original_index == origin.original_index
                    and source.raw_path == origin.raw_path
                    and source.selection_key == origin.selection_key
                    and source.line_occurrence == origin.occurrence
                    and source.raw_line == origin.normalized_text
                    and 0 <= lo < hi <= len(origin.raw_text)
                    and origin.raw_text[lo:hi] == source.text):
                continue
            a, z = claim.span
            if not (0 <= a < z <= len(source.text)):
                continue
            claim_text, claim_view = claim.text, "claim"
            if source.text[a:z] != claim.text:
                claim_text = exact_nominal_binding_text(source, claim)
                if claim_text is None:
                    continue
                claim_view = "nominal_binding"
            raw_span = (lo + a, lo + z)
            if origin.raw_text[raw_span[0]:raw_span[1]] != claim_text:
                continue
            comment_object = None
            if source.source_origin == "comment":
                record = comment_records.get(source.source_index)
                comment_object = _get(record, "comment_object")
                if (record is None or _get(record, "ledger_object") is not ledger
                        or _get(record, "raw_text") != origin.raw_text
                        or _get(record, "raw_path") != origin.raw_path
                        or not isinstance(comment_object, dict)
                        or str(comment_object.get(origin.selection_key) or "") != origin.raw_text):
                    unresolved.append("U: 댓글 document 객체 결속 미확인")
                    continue
            events = tuple(e for e in ledger.evaluations
                           if e.claim_id == claim.claim_id and e.source_id == source.source_id
                           and e.event_id in _get(claim, "evaluation_event_ids", ()))
            # 모든 술어 좌표는 source 절의 실제 구간이어야 한다. 다른 event는 인용하지 않는다.
            events = tuple(e for e in events if
                           0 <= e.predicate_span[0] < e.predicate_span[1] <= len(source.text)
                           and source.text[e.predicate_span[0]:e.predicate_span[1]].startswith(e.predicate))
            proof = SnippetProof(
                "source_claim", source.source_id, claim.claim_id, source.raw_path,
                raw_span, claim_text, hashlib.sha256(claim_text.encode()).hexdigest(),
                claim.speaker, claim.kind, claim.final_support,
                tuple((lo + e.predicate_span[0], lo + e.predicate_span[1]) for e in events),
                tuple(e.event_id for e in events), native.source, native.manifest, origin,
                ledger, source, claim, comment_object, events, claim_view)
            record_kind, source_question = kinds.get((source.raw_path, raw_span), ("", False))
            units.append(_Unit(claim_text, source.source_role, source.original_index,
                               claim.kind == "own" and claim.speaker == "self"
                               and claim.final_support, claim.kind == "reported",
                               record_kind, source_question, proof))
    return tuple(units), tuple(dict.fromkeys(unresolved))


def reduce_source_context(native: Any, author_records=(), comments=(), signals=None, *, source_only=False) -> SourceExplanation:
    """목적/관계가 원문에 명시된 경우만 환원한다. 입력 객체를 변경하지 않는다."""
    if signals is not None and signals is not _get(native, "signals"):
        return SourceExplanation(unresolved=("U: ExpertSignals 객체 불일치",))
    units, unresolved = _bound_units(native, author_records, comments)
    if not units:
        return SourceExplanation(unresolved=unresolved or ("U: exact 원문 claim 없음",))
    identity, fingerprint = _input_identity(native), _source_fingerprint(native)
    own = [u for u in units if u.role == "author" and u.current_own]
    other = [u for u in units if u.role == "comment" and u.current_own]
    reasons, notes, proofs, unknown = [], [], [], list(unresolved)
    primary = ""
    structural = source_speech_fragments(units, None if source_only else native.projection)
    title_body_relation = _source_title_body_relation(own)
    body_units = [u for u in own if u.proof.source_object.source_origin == "body_line"]
    pointed_question = next((fragment for before in body_units for question in body_units
        if (fragment := current_propriety_question_fragment(before, question)) is not None), None)
    specific_relation = pointed_question or title_body_relation
    if specific_relation is not None:
        anchored = specific_relation.unit_objects[-1]
        if specific_relation.rule == "source_title_body_conditional_comparison":
            structural = tuple(f for f in structural if not (
                f.rule == "source_condition_structure"
                and any(u is anchored for u in f.unit_objects)))
        elif specific_relation.rule in {"source_title_body_attention_lament", "current_pointed_harassment_question"}:
            structural = tuple(f for f in structural if not (
                f.rule == "source_wh_question_structure"
                and any(u is anchored for u in f.unit_objects)))
    desire = _source_headline_desire_fragment(own)
    shock_recollection = _source_adjacent_shock_recollection(own)
    new_work_critique = _source_new_work_critique_fragment(own)
    if desire is not None:
        title_unit = desire.unit_objects[0]
        structural = tuple(fragment for fragment in structural if not (
            fragment.rule == "source_event_structure"
            and any(unit is title_unit for unit in fragment.unit_objects)))

    def add(bucket, sentence, evidence, rule):
        if sentence in bucket:
            return
        bucket.append(sentence)
        for u in evidence:
            p = u.proof
            copied = SnippetProof(**{**p.__dict__, "rule": rule})
            if not any(x.rule == rule and x.claim_object is p.claim_object for x in proofs):
                proofs.append(copied)

    def add_fragment(fragment):
        if fragment is None:
            return
        add(reasons if fragment.destination == "reason" else notes,
            fragment.sentence, fragment.unit_objects, fragment.rule)
        unknown.extend(fragment.unresolved)

    if specific_relation is not None:
        add_fragment(specific_relation)
        primary = specific_relation.primary_subject

    if source_only:
        for source_fragment in (desire, shock_recollection, new_work_critique):
            if source_fragment is not None:
                add_fragment(source_fragment)
                primary = source_fragment.primary_subject
        for fragment in structural:
            add_fragment(fragment)
        if not primary:
            chosen = next((f for role in ("relation", "purpose", "reaction") for f in structural
                           if f.destination == "reason" and f.primary_role == role and f.primary_subject), None)
            primary = chosen.primary_subject if chosen else ""
        if not primary:
            headline = _source_headline_fragment(own)
            if headline is not None:
                add_fragment(headline)
                primary = headline.primary_subject
        for fragment in _source_cost_comment_fragments(units):
            add_fragment(fragment)
        return SourceExplanation(primary, tuple(reasons), tuple(notes), tuple(proofs),
            tuple(dict.fromkeys(unknown)), bool(primary and reasons),
            input_identity=identity, input_fingerprint=fingerprint)

    # 본문 질문이 작품 내 설정의 제목보다 현재 대상을 명시할 때 본문을 우선한다.
    reader_q = next((u for u in own if
                     (u.record_kind == "reader_behavior_question"
                      or re.search(r"소설\s*(?:보고|보는|읽고|읽은).*댓글\s*(?:쓰|작성)", u.text))
                     and _QUESTION.search(u.text) and not _REPORT.search(u.text)), None)
    if reader_q:
        primary = "소설을 읽은 실제 독자의 댓글 작성 습관을 묻는 글."
        add(reasons, "소설을 읽고 댓글을 쓰는지 실제 독자에게 묻는다.", [reader_q], "reader_behavior_question")
        for u in own:
            if _NOT_WRITE.search(u.text):
                add(notes, "글쓴이는 댓글을 써 본 적이 없다고 말한다.", [u], "own_no_writing_experience")
        background = [u for u in own if "빙의" in u.text and u is not reader_q]
        if background:
            add(notes, "제목의 빙의 설정은 질문을 꺼낸 배경이며 현재 질문은 독자의 행동에 관한 것이다.",
                [background[0], reader_q], "background_vs_current_question")

    if not primary:
        question = next((fragment for unit in own
            if (fragment := platform_consequence_question_fragment(unit)) is not None), None)
        if question is None:
            question = next((fragment for unit in own
                if (fragment := current_question_fragment(unit, native.projection)) is not None
                and fragment.destination == "reason"), None)
        if question is not None:
            primary = question.sentence.split(". ", 1)[0].rstrip(".") + "."
            add_fragment(question)
    for unit in own:
        question_note = current_question_fragment(unit, native.projection)
        if question_note is not None and question_note.destination == "note":
            add_fragment(question_note)
        add_fragment(current_vs_past_question_fragment(unit, own))
        add_fragment(state_or_allowance_fragment(unit, native.projection))

    request_units = [u for u in own if not _REPORT.search(u.text)
                     and is_recommendation_request_text(_clean(u.text))]
    request = _get(native.projection, "speech_act") == "recommendation_request" and bool(request_units)
    if request:
        plan = reduce_request_roles(units, native.projection, exact=exact_unit, emit=_frag,
                                    current=is_recommendation_request_text)
        if plan.supported:
            primary = plan.primary
        for fragment in plan.fragments:
            add_fragment(fragment)
        unknown.extend(plan.unresolved)
    for surface, role, _basis in _get(native.projection, "work_roles", ()):
        evidence = [u for u in own if surface in u.text]
        if role == "reference" and request and any(surface_role_predicate(_clean(u.text), surface, "reference") for u in evidence):
            add(notes, f"{surface}를 원하는 느낌의 비교 기준으로 든다.", evidence, "source_reference_role")
        elif role == "excluded" and request and evidence and any(
                not u.source_question and not _CONDITIONAL.search(u.text)
                and not _NOT_READ.search(u.text)
                and (surface_role_predicate(_clean(u.text), surface, "read")
                     or surface_role_predicate(_clean(u.text), surface, "exclude")) for u in evidence):
            add(notes, f"{surface}는 원문에서 읽었다고 밝히거나 빼 달라고 한 추천의 제외 조건이다. 명시되지 않은 완독 경험을 붙이지 않는다.", evidence, "source_exclusion_role")

    # 현실 관계 고민: 동일 화자의 질문과 관심사 충돌 절을 결합한다.
    friend_q = next((u for u in own if re.search(r"(?:찐친|친구).*어떻게|어떻게.*친구", u.text)), None)
    interests = [u for u in own if re.search(r"관심\s*(?:분야|학문)|잘\s*안\s*맞|사이가\s*멀어", u.text)]
    if not primary and friend_q and interests:
        primary = "관심사를 함께 이야기할 친구를 어떻게 만들지 고민하는 일상 대화."
        add(reasons, "관심 분야가 맞지 않으면 대화나 관계가 어려울까 걱정하며 친구를 만드는 방법을 묻는다.",
            [friend_q, *interests], "friend_question_and_interest_conflict")

    # 친구로 호명하는 농담은 실재 인원/동일인 인증을 하지 않는다.
    friend_joke = next((u for u in own if re.search(r"너희.*내\s*친구", u.text)), None)
    online = [u for u in own if re.fullmatch(r"(?:\d+(?:\.\d+)+|ㅇㅇ|[가-힣]{1,15}쨩)", _clean(u.text))]
    if not primary and friend_joke and online:
        listing = "·".join(_clean(u.text) for u in online)
        primary = "온라인 표면들을 친구로 부르는 농담."
        add(reasons, f"{listing}을 친구로 부르며 익명 온라인 표면을 사람 친구처럼 세는 농담이다.",
            [friend_joke, *online], "online_surfaces_as_friends")
        unknown.append("U: 온라인 표면의 동일인·실제 인원·친구 관계 인증")

    arrival = next((u for u in own if re.search(r"올\s*때\s*(?:됐|됬|됐다)", u.text)
                    and not (u.source_question or _REPORT.search(u.text)
                             or _CONDITIONAL.search(u.text) or _QUESTION.search(u.text))), None)
    cheer = next((u for u in own if re.match(r"\s*가자\s+[^!?]+", u.text)
                  and not (_REPORT.search(u.text) or _CONDITIONAL.search(u.text))), None)
    if not primary and arrival and cheer:
        target = re.sub(r"^(?:이제는|이제|슬슬)\s*", "", arrival.text)
        target = re.split(r"\s*올\s*때", target, maxsplit=1)[0].strip()
        addressed = re.sub(r"^\s*가자\s+", "", _topic(cheer.text)).strip()
        primary = f"{target}가 오기를 기다리며 {addressed}을 응원하는 글."
        add(reasons, f"{target}가 올 때가 됐다고 기다리면서 {addressed}에게 응원을 보낸다.",
            [arrival, cheer], "waiting_and_cheering")
        unknown.append("U: 호칭의 공식 작가 역할·휴재 종료·연재 재개·강조 정도")

    # 실제 source predicate의 태도 환원. 조건/전언/질문/부정은 호평으로 승격하지 않는다.
    affect = []
    surprises = [u for u in own if praise_scope(u, native.projection)[0] == "affirmative_candidate"
                 and _SURPRISE.search(_clean(u.text))
                 and not (_REPORT.search(u.text) or _CONDITIONAL.search(u.text)
                          or u.source_question or _QUESTION.search(u.text) or _OTHER_ACTOR.search(u.text))]
    for u in own:
        expectation = re.match(r"\s*(?:생각보다|예상보다)\s+(.+)", _clean(u.text))
        if (praise_scope(u, native.projection)[0] != "affirmative_candidate"
                or not expectation or not surprises or u.source_question or _QUESTION.search(u.text)
                or _OTHER_ACTOR.search(u.text) or _REPORT.search(u.text) or _CONDITIONAL.search(u.text)):
            continue
        # 접속절을 내용 명사구로 바꾸는 작은 문법. 대상 이름이나 작품별 규칙은 없다.
        content = _topic(expectation.group(1))
        endings = (("죽이고", "죽이는"), ("끝내고", "끝내는"), ("나오고", "나오는"),
                   ("등장하고", "등장하는"), ("끝나고", "끝나는"), ("진행되고", "진행되는"))
        ending = next(((old, new) for old, new in endings if content.endswith(old)), None)
        if ending:
            old, new = ending
            content = content[:-len(old)] + new
            add(reasons, f"{content} 전개가 예상과 달랐다는 반응이다.",
                [u, surprises[0]], "expected_difference_with_explicit_surprise")
            affect.append(u)
    for u in own:
        text = _clean(u.text)
        if praise_scope(u, native.projection)[0] != "affirmative_candidate":
            continue
        if u.source_question or _REPORT.search(text) or _CONDITIONAL.search(text) or _QUESTION.search(text):
            continue
        if _OTHER_ACTOR.search(text) or any(
                _get(e, "realization") in {"question", "modal", "reported", "conditional", "embedded"}
                or _get(e, "actor") not in {None, "", "self"}
                or _get(e, "final_support") is not True
                for e in u.proof.event_objects):
            continue
        if _NEG_PRAISE.search(text):
            continue
        surprise, praise = _SURPRISE.search(text), _PRAISE.search(text)
        if surprise:
            target = _topic(text[:surprise.start()])
            if target:
                add(reasons, f"{target}에 놀라움을 보인다.", [u], "source_surprise_predicate")
                affect.append(u)
        if praise:
            fragment, unresolved_praise = praise_relation_fragment(u, native.projection,
                exact=exact_unit, scope=praise_scope, emit=_frag)
            if fragment is not None:
                add_fragment(fragment)
                affect.append(u)
            elif unresolved_praise:
                unknown.append(unresolved_praise)
    if not primary and affect:
        target = _get(native.projection, "target_surface")
        # target_surface는 원문 표면으로 직접 확인될 때만 쓴다.
        evidence = [u for u in own if target and target in u.text]
        if evidence:
            primary = f"{target}의 내용에 대한 독자 반응."
            add(notes, "본문에 드러난 감상이며 작품 사건의 외부 사실 확인과는 별개다.",
                [*evidence, *affect], "source_target_and_reaction")
        else:
            primary = reasons[0]

    # 조건/전언을 긍정 평가로 만들지 않고, 화자와 내용의 한계를 설명한다.
    for u in units:
        speaker = "글쓴이" if u.role == "author" else f"댓글 {u.original_index + 1}의 화자"
        if u.reported or (u.current_own and _REPORT.search(u.text)):
            fragment = neutral_attribution_note(u)
            if fragment is not None and fragment.rule != "enum_attribution_unresolved":
                add_fragment(fragment)
            elif fragment is not None:
                unknown.extend(fragment.unresolved)
        if not u.current_own:
            continue
        if _CONDITIONAL.search(u.text) and (_PRAISE.search(u.text) or _QUESTION.search(u.text)):
            is_question = u.source_question or bool(_QUESTION.search(u.text))
            mode = "질문" if is_question else "서술"
            add(notes, f"{speaker}의 {_topic(u.text)}는 조건을 둔 {mode}이다. 조건이 실제 특정 사건으로 성립했는지는 이 표현만으로 알 수 없다.",
                [u], "source_conditional_question_scope" if is_question else "source_conditional_scope")
    for u in other:
        label = f"댓글 {u.original_index + 1}의 화자"
        clean = _clean(u.text)
        asserted = not (
            source_current_question(u) or u.reported
            or _REPORT.search(clean) or _CONDITIONAL.search(clean)
            or any(_get(event, "realization") in {"question", "conditional", "modal", "embedded", "reported"}
                   or _get(event, "final_support") is not True for event in u.proof.event_objects)
        )
        explicit = source_explicit_comment_recommendation(u) if request else None
        if explicit:
            add(notes, f"{label}는 「{explicit}」를 작품으로 명시해 추천한다.",
                [*request_units, u], "comment_explicit_work_recommendation")
            unknown.append("U: 댓글 추천 표면의 공식 작품명·특정 판본 인증")
        elif request:
            unknown.append(f"U: 댓글 {u.original_index + 1}의 작품 후보·추천 의도 관계")
        if asserted and _NOT_READ.search(clean):
            add(notes, f"{label}는 언급된 지점까지는 읽지 않았다고 말한다.", [u], "partial_reading_limit")
            unknown.append("U: 지시된 지점의 특정 작품 대상·완독 여부")
        elif asserted and _READ.search(clean) and re.search(r"바라.*아니|원하.*아니|기대.*아니", clean):
            add(notes, f"{label}는 읽어본 내용이 기대하던 느낌과 다르다고 말한다.", [u], "reading_expectation_mismatch")
            unknown.append("U: 읽어본 대상의 특정 작품·완독 여부")
        elif asserted and _READ.search(clean):
            add(notes, f"{label}는 읽어본 경험을 언급하며 완독 여부는 확인되지 않는다.", [u], "reading_experience_not_completion")
        if asserted and _THANKS.search(clean):
            add(notes, f"{label}는 감사를 전한다. 감사만으로 추천 내용에 완전히 동의했다고 볼 수 없다.",
                [u], "gratitude_not_full_agreement")
        chapter = re.search(r"(?:한\s*)?(\d+\s*화)\s*(?:부터|이후)(.+)", clean)
        if asserted and chapter:
            add(notes, f"{label}는 {chapter.group(1)} 이후 {chapter.group(2).rstrip('.')}라고 설명한다. 이는 해당 댓글의 주장이다.",
                [u], "comment_chapter_scoped_report")
    established_primary = bool(primary)
    work_purpose = work_genre_purpose_fragments(units, native.projection,
        exact=exact_unit, emit=_frag, scope=praise_scope)
    if desire is not None:
        title_unit = desire.unit_objects[0]
        work_purpose = tuple(fragment for fragment in work_purpose if not (
            fragment.rule == "desired_narrative_content"
            and any(unit is title_unit for unit in fragment.unit_objects)))
    source_fragments = tuple(f for f in (desire, shock_recollection, new_work_critique) if f is not None)
    purpose_fragments = (*source_fragments, *work_purpose,
                         *everyday_purpose_fragments(units), *structural)
    for fragment in purpose_fragments:
        add_fragment(fragment)
    # 제목의 열린 질문 뒤에 작성자가 실제 비교 평가를 적으면 후자의 요지를 주대상으로 둔다.
    comparison = next((f for f in structural if f.rule == "source_later_quality_limit_structure"
                       and f.destination == "reason" and f.primary_subject), None)
    if comparison is not None and primary and any(source_current_question(u) for u in own):
        primary = comparison.primary_subject
        established_primary = True
    if new_work_critique is not None:
        primary = new_work_critique.primary_subject
        established_primary = True
    if not established_primary:
        chosen = next((f for role in ('relation', 'purpose', 'reaction') for f in purpose_fragments
                       if f.destination == 'reason' and f.primary_role == role and f.primary_subject), None)
        if chosen is not None:
            primary = chosen.primary_subject
        else:
            first = next((f for f in purpose_fragments if f.destination == 'reason'), None)
            if first is not None:
                primary = first.sentence.split('. ', 1)[0].rstrip('.') + '.'
    if not primary:
        headline = _source_headline_fragment(own)
        if headline is not None:
            add_fragment(headline)
            primary = headline.primary_subject
        else:
            unknown.append("U: 유한 환원 규칙으로 구체적 현재 목적·대상 관계를 확정하지 못함")
    for fragment in _source_cost_comment_fragments(units):
        add_fragment(fragment)
    return SourceExplanation(primary, tuple(reasons), tuple(notes), tuple(proofs),
                             tuple(dict.fromkeys(unknown)), bool(primary and reasons),
                             input_identity=identity, input_fingerprint=fingerprint)


def verify_source_context(explanation: SourceExplanation, native: Any,
                          author_records=(), comments=(), signals=None, *, source_only=False) -> bool:
    """동일 원문 document/ledger 객체와 전체 환원 결과를 재계산해서 대조한다."""
    if not explanation.supported or explanation.counts_as_core or explanation.publication_authority:
        return False
    try:
        recomputed = reduce_source_context(native, author_records, comments, signals, source_only=source_only)
        if explanation != recomputed or explanation.input_identity != _input_identity(native):
            return False
        for before, after in zip(explanation.proofs, recomputed.proofs):
            for key in ("document_object", "manifest_object", "origin_object", "ledger_object",
                        "source_object", "claim_object", "comment_object"):
                if getattr(before, key) is not getattr(after, key):
                    return False
            if len(before.event_objects) != len(after.event_objects) or any(
                    a is not b for a, b in zip(before.event_objects, after.event_objects)):
                return False
        return True
    except (AttributeError, IndexError, TypeError, ValueError):
        return False
