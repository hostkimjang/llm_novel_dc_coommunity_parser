"""같은 native claim의 발화 구조를 공개 설명으로 합성한다.

행 번호/작품 사전/생성 요지/공식명은 사용하지 않는다. 기존 actor/object/event와
원절의 terminal/operator 문법만 소비한다. 이 설명은 core/공개 작품 권한이 아니다.
"""
from dataclasses import replace
from functools import lru_cache
import re
from .source_context_grammar import exact_unit, _frag, _get
from .context_projection_contract import _new_work_head_match

_APP = re.compile(r"\s*-\s*dc\s*(?:official\s*)?App\s*$", re.I)
_END = r"(?:[.!?？~…ㅋㅎㅠㅜ ]|ㅇㅇ)*$"
_REPORT = re.compile(r"(?P<content>.+?)(?:라고|다고|라|다)\s*(?:함|한다|하더라|들었|들음|던데|는데|더라)" + _END)
_CONDITION = re.compile(r"^(?P<condition>.+?(?:라면|다면|으면|였으면|했으면|할\s*경우|일\s*경우))\s+(?P<content>.+)$")
_NEGATED_CLAIM = re.compile(r"(?P<content>.+?)(?:다는|라는)\s*(?:말|주장)(?:은|는)?\s*(?:ㄴㄴ|아니(?:다|야|라고)|틀렸(?:다|음)|동의\s*안\s*함)" + _END)
_NOTICE = re.compile(r"(?:(?P<topic>.+?)\s+)?(?P<object>[^\s.!?]+?)(?P<change>변경|수정|교체|갱신|공개|발표)(?:됐(?:다|음)?|되었(?:다|음)?|됨)" + _END)
_VS = re.compile(r"(?P<left>[^?？\n]+?)\s*(?:(?i:vs\.?)|(?<=\s)대(?=\s))\s*(?P<right>[^?？\n]+?)" + _END)
_COMPARISON_RESULT_REPLY = re.compile(
    r"(?P<result>이기긴\s*했(?:네|음|다)|이겼(?:네|음|다|구나)|지긴\s*했(?:네|음|다)|졌(?:네|음|다|구나)|비기긴\s*했(?:네|음|다)|비겼(?:네|음|다|구나))" + _END)
_MODAL_Q = re.compile(r"(?P<content>.+?)\s*(?P<modal>가능(?:함|한가|한지)|할\s*수\s*있(?:나|냐)|할\s*수\s*없(?:나|냐))" + _END)
_WH_Q = re.compile(r"(?P<before>.*?)\s*(?P<wh>왜|어째서|어떻게|어케|언제|누가|어디|무엇|뭐가|뭘|뭐)\s*(?P<after>.+?)" + _END)
_Q_END = re.compile(r"(?P<content>.+?)(?:인가|이냐|냐|(?<!니)까|는가|은가|일까|아닐까|있나|없나|맞나|였나|(?:있|없|되|하|않|찮|려|았|었|였|했|겠|는|가|오|보|봤|기|치|읽|쓰|먹|맞|싶|좋|싫)(?:나|니|나요))" + _END)
_Q_QUALITY = {"재밌": "재미있는지", "재미있": "재미있는지", "좋": "좋은지", "괜찮": "괜찮은지", "맞": "맞는지", "싫": "싫은지"}
_Q_QUALITY_END = re.compile(r"(?:^|\s)(?P<stem>재미있|재밌|괜찮|좋|맞|싫)(?:나|니|나요|냐)$")
_WH_BARE_QUESTION_END = re.compile(r"(?:지|냐|니|(?<!니)까|나|됨|되나요|되냐|되나|될까|할까|함|해요|해야\s*함|해야\s*됨)" + _END)
_CONDITION_MODAL_RESULT = re.compile(r"(?:겠|(?:것|거)\s*같|듯|지도\s*모르|일지도|아마)")
_CONDITION_REQUEST_RESULT = re.compile(r"(?:말해|알려|추천해|골라|제안해|답해)\s*(?:줘|주오|주세요|주셈|달라|주라|줘요|줘라|라|오|요)" + _END)
_EMPATHY_PREDICATE = re.compile(r"불쌍|안타깝|안타까|슬프|슬픈|연민|동정")
_EVALUATION_OBLIGATION = re.compile(r".+?(?:아|어|여)야\s*하(?:는\s*(?:거|것)(?:임|이다|이야|지)?|ㅁ|다)$")
_ALLOWANCE = re.compile(r".+(?:이라도|라도|여도|이어도)\s+(?:좋아|좋음|좋다|괜찮아|괜찮음|상관없어|상관없음|됨)" + _END)
_REPORTED_QUESTION = re.compile(r"[?？]\s*(?:이?라고|라며|냐고)\s*(?:물|묻|질문|말|했|하)")
_DIRECT_EVALUATION_OBJECT = re.compile(
    r"(?P<object>[가-힣A-Za-z0-9]+(?:\s+[가-힣A-Za-z0-9]+)?)(?:\([^()\n]{1,80}\))?(?:을|를)\s*$")
_EDITION_TOPIC = re.compile(r"^(?P<edition>[가-힣A-Za-z0-9]+판)(?:은|는)\s")
_PLAN = re.compile(r"(?P<action>.+?)\s*(?:할|쓸|읽을|볼|물어볼)\s*(?:계획|예정|의향)(?:이다|임|이야|입니다)?" + _END)
_PARTIAL = re.compile(r"(?P<drop>(?:중도)?하차)|(?P<early>초반(?:부)?.{0,20}(?:읽|보))|(?P<not_reached>(?:거기|그\s*부분|그\s*지점).{0,20}안\s*읽)")
_MEMORY = re.compile(r"가물가물|기억.{0,8}(?:안|못|않|불확실)|잘\s*모르")
_READ = re.compile(r"읽(?:었|어\s*봤|어봤)|보긴\s*했|봤(?:는데|음|다)")
_READ_EXPERIENCE_Q = re.compile(
    r"(?P<scope>.*?)(?:(?<![가-힣A-Za-z0-9])(?P<negative>안|못)\s*)?"
    r"(?P<reading>읽어?\s*봤|읽었|보았|봤)(?:나|냐|니|나요|는가)" + _END)
_NOMINAL_COPULA = re.compile(
    r"^(?P<topic>[가-힣A-Za-z0-9]{2,})(?:은|는)\s+"
    r"(?P<value>[가-힣A-Za-z0-9]{2,})인\s*것(?:이다|이야)" + _END)
_MEDIA_FRAME = re.compile(r"(?P<description>.+?)\s*(?P<media>웹툰|만화|소설|작품)(?:인데|임|이다)" + _END)
_COMPARE_PREMISE = re.compile(r"(?P<reference>.+?)보다\s+(?P<quality>.+?)다고\s*해서" + _END)
_NEGATED_CONCLUSION = re.compile(r"(?P<result>.+?)(?:은|는)?\s*아니(?:라고\s*생각(?:해요|함|한다)|다|라고)" + _END)
_EXCLUDE = re.compile(r"(?P<except>.+?)\s*(?:경우\s*)?말고" + _END)
_GUILD_NAME_FRAME = re.compile(
    r"(?P<frame>[^\"“”「」'\n]{1,100}?길드)\s*(?P<open>[\"“「])(?P<name>[^\"“”「」'\n]{2,50})(?P<close>[\"”」])"
    r"(?:이|가)?(?:다|야|임|입니다)[!.~ ]*$")
_GUILD_IMPRESSION = re.compile(r"(?P<impression>[^\"“”「」'\n?!]{4,120}?길드)\s+느낌(?:임|이다|이야|이네)?[!.~ ]*$")
_GUILD_OTHER_TARGET = re.compile(
    r"(?:다른|별개(?:의)?|라이벌(?:인)?|경쟁(?:하는)?|상대|적대)\s*"
    r"(?:[A-Za-z0-9가-힣]{1,12}\s+)?길드")
_GUILD_EXPLICIT_NAME = re.compile(r"(?P<name>[A-Za-z0-9가-힣]{2,50})(?:이라는|라는|이란)\s+길드")
_GUILD_EXCLUSION = re.compile(
    r"(?:^|\s)(?:아닌|아니었던|아니던|아닐|말고|외의|제외(?:한|된|하고)?|빼고)(?=\s|$)")
_MEDIA_ABSENCE = re.compile(
    r"^(?P<media>(?:(?:웹툰|웹소설|소설|만화|애니|영화)도\s+){2,3})"
    r"(?P<missing>[^?？.!\n]{2,35}?\s+없(?:구나|네|다|음|어|었[다음네])?)" + _END)
_QUALITY_LIMIT = re.compile(
    r"^(?:절대\s+)?(?P<baseline>[^?？.!\n]{2,40}?)의\s*"
    r"(?P<quality>재미|완성도|몰입감|긴장감)(?:을|를)\s*"
    r"(?:넘|이기|따라잡)[^?？.!\n]{0,18}?(?:없|못)[^?？.!\n]{0,12}" + _END)
_LATER_READING_LIMIT = re.compile(r"^후반.{0,16}(?:재밌|재미있).{0,40}본\s*적(?:이)?\s*없(?:음|다|어|었[다음네])?" + _END)
_NAMED_EXCEPTION = re.compile(r"^(?P<exception>[^?？.!\n]{2,40}?)(?:정도)?만\s+예외" + _END)
_COMMENT_TIME_SHIFT = re.compile(
    r"^(?P<earlier>[^?？.!\n]{4,90}?까지는\s+[^?？.!\n]{2,70}?)\s+"
    r"생각했는데\s+(?P<later>[^?？.!\n]{2,50}?\s+보니까\s+[^?？.!\n]{2,50})" + _END)
_DOUBTFUL_NEGATIVE_INSCRIPTION = re.compile(r"설마\s+.+?(?:건|것은|거는)\s+아니겠지[?？!.~… ]*$")
_REBUTTAL_WH = re.compile(r"^(?:뭔|무슨)\s+.+?\s+(?:왜|어째서)\s+.+[?？]$")
_REBUTTAL_REASON = re.compile(
    r"^(?:거기|그쪽|그곳|해당\s+\S+)\s+.+?"
    r"(?:(?<![가-힣])안\s*[가-힣]+|(?<![가-힣])못\s*[가-힣]+|않|없)"
    r".{0,12}(?:는데|으니|니까|잖아|거든)[.!~… ]*$"
)


def _text(unit):
    return _APP.sub("", unit.text).strip()


def _is_question(unit):
    text = _text(unit)
    return bool(unit.source_question or re.search(r"[?？](?:[.!~…ㅋㅎㅠㅜ ]|ㅇㅇ)*$", text)
                or _Q_END.fullmatch(text.rstrip("?？.!~… ")))


def _voice(unit, event=None):
    label = "글쓴이" if unit.role == "author" else f"댓글 {unit.original_index + 1}의 화자"
    if event is not None:
        actor = _get(event, "actor", "")
        if actor.startswith("other:"):
            return f"{label}가 언급한 {actor[6:]}"
        if actor != "self":
            return None
    return label


def _plain_own(unit):
    p = unit.proof
    return bool(exact_unit(unit) and unit.current_own and not unit.reported
                and p.claim_kind == "own" and p.claimant == "self" and p.final_support
                and _get(p.claim_object, "quote_frame_status") == "not_quote")


def _argument(value):
    """논항을 원문 표면 그대로 쓴다. 문장/미완 인용/감정 기호는 NP로 대체하지 않는다."""
    value = value.strip(" ,，.。!?？~…")
    if not value or not re.search(r"[가-힣A-Za-z0-9]", value):
        return ""
    if re.search(r"[\n?？]|(?:라고|다고)\s*(?:함|했다)|[\"“”]", value):
        return ""
    return value


def _case_bare_target(value, head):
    """검증된 명사 머리 뒤에 붙은 조사만 떼고 이름 내부의 마지막 음절은 보존한다."""
    if head and len(head) >= 2 and value in {head + particle for particle in ("이", "가", "은", "는", "을", "를")}:
        return head
    return value


def _particle(value, consonant, vowel):
    """원문 논항의 마지막 한글 음절에 맞는 조사를 고른다."""
    last = value.rstrip()[-1:] if value else ''
    return consonant if last and '\uac00' <= last <= '\ud7a3' and (ord(last) - 0xac00) % 28 else vowel


def _directional_particle(value):
    """한글 받침과 숫자·영문 끝 글자의 통상적인 한국어 읽기로 '으로/로'를 고른다."""
    last = value.rstrip()[-1:] if value else ""
    if last and '\uac00' <= last <= '\ud7a3':
        coda = (ord(last) - 0xac00) % 28
        return "으로" if coda not in {0, 8} else "로"
    # 숫자는 한자어 수 읽기(영·일·이·삼·사·오·육·칠·팔·구),
    # 영문자는 알파벳 이름 읽기의 마지막 받침을 기준으로 한다.
    return "으로" if last.upper() in {"0", "3", "6", "M", "N"} else "로"


@lru_cache(maxsize=1)
def _nominal_kiwi():
    from kiwipiepy import Kiwi
    return Kiwi(num_workers=1)


def _has_topic_particle(text, match):
    """첫 어절의 끝 '은/는'이 주제 조사(JX)인지, 관형형 어미(ETM)인지 판별한다."""
    boundary = match.end("topic")
    try:
        tokens = _nominal_kiwi().tokenize(text)
    except Exception:
        return False  # 품사 판정이 없으면 명사 지목을 새로 만들지 않는다.
    return any(token.start == boundary and token.len == 1
               and token.form == text[boundary] and token.tag == "JX"
               for token in tokens)


def _affirmed_partial_hit(text, hit):
    """부정·계획·고민 속의 하차와 미독을 실제 독서 범위로 쓰지 않는다."""
    tail = text[hit.end():]
    if hit.lastgroup == "early" and re.search(r"(?:안|못)\s*(?:읽|보)$", hit.group()):
        return False
    if hit.lastgroup == "drop" and re.match(
        r"^\s*(?:하지\s*(?:않|못)|(?:(?:은|는|을|를)\s*)?(?:안|못)\s*했|한\s*(?:건|게|것은)\s*아니)",
        tail,
    ):
        return False
    if hit.lastgroup == "drop" and re.match(
        r"^\s*(?:할(?:까|지|까봐)|하려|할\s*(?:계획|예정|생각|듯)|하고\s*싶|해야)", tail,
    ):
        return False
    if re.match(r"^\s*(?:(?:은|는|이|가)\s*(?:(?:건|게|것은|것도)\s*)?)?아니", tail):
        return False
    if re.match(r"^\s*지\s*(?:않|못)", tail):
        return False
    return True


def _verified_subject_target(source_text, subject):
    """원문 주어가 명사+격/주제 조사일 때만 평가 대상 머리를 돌린다."""
    a, z = _get(subject, "span", (-1, -1))
    if not (0 <= a < z <= len(source_text) and source_text[a:z] == subject.text):
        return ""
    try:
        tokens = _nominal_kiwi().tokenize(source_text)
    except Exception:
        return ""
    nominal_tags = {"NNG", "NNP", "NP", "NR", "SL", "SH", "SN"}
    first = next((i for i, token in enumerate(tokens) if token.start == a and token.tag in nominal_tags), None)
    if first is None:
        return ""
    cursor, nominals, particle = a, [], None
    for token in tokens[first:]:
        if token.start != cursor or token.len <= 0 or token.start + token.len > z:
            return ""  # 공백·소유격·다른 절을 건너뛰어 명사구를 합치지 않는다.
        if token.tag in nominal_tags:
            nominals.append(token)
            cursor += token.len
            continue
        if token.tag in {"JX", "JKS", "JKO"} and nominals and token.start + token.len == z:
            particle = token
        break
    if particle is None:
        return ""
    # 단일 명사의 기존 형태소 반환은 유지한다. 새 복합 대상은 원 span과
    # 각 명사 토큰의 원형이 정확히 이어질 때만 회수한다. 대명사 소유자는 합치지 않는다.
    target = nominals[0].form if len(nominals) == 1 else source_text[a:cursor]
    if len(nominals) > 1 and (any(t.tag == "NP" for t in nominals)
                             or "".join(t.form for t in nominals) != target):
        return ""
    actor = _get(subject, "actor", "")
    if actor.startswith("other:") and actor[6:] != target:
        return ""
    return target


def _target(unit, event):
    source = unit.proof.source_object
    lo, hi = unit.proof.claim_object.span
    if re.match(r"(?:싫|좋아|미워|혐오|선호)", event.predicate):
        # 평가 술어 바로 앞 목적어가 있으면 멀리 있는 주제어나 관형 부정어보다 우선한다.
        direct = _DIRECT_EVALUATION_OBJECT.search(source.text[lo:event.predicate_span[0]])
        if direct:
            target = _argument(direct.group("object"))
            if target:
                return target
    targets = []
    for obj in _get(event, "objects", ()):
        a, z = _get(obj, "span", (-1, -1))
        h, j = _get(obj, "head_span", (-1, -1))
        if not (lo <= a < z <= hi and a <= h < j <= z
                and source.text[a:z] == obj.text and source.text[h:j] == obj.head):
            continue
        # 한 술어의 원 NP다. 같은 원 span을 여러 view에서 중복하지 않는다.
        target = _argument(_case_bare_target(obj.text, obj.head))
        if target and target not in targets:
            targets.append(target)
    if targets:
        return "·".join(targets)
    subject = _get(event, "grammatical_subject")
    a, z = _get(subject, "span", (-1, -1))
    if (subject is not None and _get(subject, "explicit") and lo <= a < z <= hi
            and source.text[a:z] == subject.text and _get(event, "actor") == "self"
            and not re.fullmatch(r"나는|내가|난|저는|제가", subject.text)):
        return _argument(_verified_subject_target(source.text, subject))
    return ""


def _event_valid(unit, event):
    p = unit.proof
    a, z = _get(event, "predicate_span", (-1, -1))
    lo, hi = p.claim_object.span
    return bool(any(event is x for x in p.ledger_object.evaluations)
                and event.claim_id == p.claim_id and event.source_id == p.source_id
                and event.event_id in p.claim_object.evaluation_event_ids
                and lo <= a < z <= hi and p.source_object.text[a:z] == event.predicate
                and _get(event, "actor") and _get(event, "realization")
                and _get(event, "attribution") not in {None, "", "NOT_OBSERVED"})


def _make(rule, sentence, unit, match=None, *, primary="", role="purpose", others=()):
    evidence = (unit, *others)
    if any(not exact_unit(u) for u in evidence):
        return None
    # reported는 전언 범위만 사용한다. 채택되지 않은 다른 own claim은 사용하지 않는다.
    if not _plain_own(unit) and not unit.reported:
        return None
    destination = "reason" if unit.role == "author" else "note"
    return _frag(rule, sentence, destination, evidence,
                 ((unit, match),) if match is not None else (),
                 primary_subject=primary if unit.role == "author" else "", primary_role=role)


def _event_fragment(unit, event, projection=None):
    if not _plain_own(unit) or not _event_valid(unit, event):
        return None
    if unit.role == "comment" and event.actor.startswith("other:"):
        # 제3자의 평가·선호를 댓글 화자의 반응으로 옮기지 않는다. 원문 댓글 인용은 별도 보존된다.
        return None
    target, voice = _target(unit, event), _voice(unit, event)
    if not target or voice is None:
        return None
    # 대상 회수로 새로 노출된 '나빠야 하는 것은 아니다'를 호평으로 뒤집지 않는다.
    # native의 원래 어휘 극성/사건은 보존하고, 이 당위 부정에서 현재 평가 설명만 만들지 않는다.
    denied_obligation = re.fullmatch(
        r"(?P<content>.+?)(?:은|는)?\s*(?:아님|아니다|아니야|아닙니다)[.!~ ]*", event.predicate)
    if denied_obligation and _EVALUATION_OBLIGATION.fullmatch(denied_obligation.group("content")):
        return None
    mode = event.realization
    if _is_question(unit):
        mode = "question"
    if event.realization == "reported" or unit.reported or _REPORT.fullmatch(_text(unit)):
        return None  # 원문의 report operator 경로만 허용한다.
    if _REPORTED_QUESTION.search(_text(unit)) and "?" in event.predicate:
        return None  # 회상 속 질문을 현재 화자의 질문으로 옮기지 않는다.
    if (_get(projection, "speech_act") == "recommendation_request"
            and event.evaluation_polarity == "pos" and _ALLOWANCE.fullmatch(_text(unit))):
        return None  # 추천 허용 범위를 이미 읽은 대상의 호평으로 옮기지 않는다.
    if (event.evaluation_polarity == "neg" and event.polarity != "negative"
            and not _is_question(unit) and _EVALUATION_OBLIGATION.fullmatch(event.predicate)
            and re.search(re.escape(event.predicate) + _END, _text(unit))):
        # 부정 평가 어휘가 당위 범위 안에 있다. 현재 불만으로 뒤집지 않는다.
        sentence = (f"{voice}는 원문의 「{_text(unit)}」에서 필요·당위 의견을 말한다. "
                    f"이 표현만으로 {target}에 현재 불만을 보인다고 단정하지 않는다.")
        return _make("source_evaluation_obligation_structure", sentence, unit)
    if (event.evaluation_polarity == "neg" and re.search(r"(?:않는|없는)\s*$", event.predicate)
            and re.search(r"(?:을|를)\s*싫", unit.proof.source_object.text[event.predicate_span[1]:unit.proof.claim_object.span[1]])):
        return None  # 뒤의 명시적 거부 술어가 받는 관형 부정어를 별도 평가로 중복하지 않는다.
    polarity = event.evaluation_polarity
    action = {"pos": "긍정적인 반응", "neg": "불만·부정적인 반응", "surprise": "놀라움"}.get(polarity)
    if polarity == "neg" and _EMPATHY_PREDICATE.search(event.predicate):
        action = "안타까움·연민"
    if action is None:
        return None
    if mode == "question":
        sentence = f"{voice}는 {target}에 대한 평가를 질문한다. 질문 안의 부정 표현도 본인의 부정 진술이나 확정 평가로 세지 않는다."
    elif mode in {"conditional", "modal", "embedded"}:
        sentence = f"{voice}는 {target}에 대한 {action}을 조건·가능성 범위에서 표현한다. 실제 발생이나 확정 평가가 아니다."
    elif mode in {"actual", "past", "contrast"} and event.final_support:
        tense = "과거의 " if event.temporal_scope == "past" else ""
        source = unit.proof.source_object.text
        tail = source[event.predicate_span[1]:unit.proof.claim_object.span[1]]
        edition = _EDITION_TOPIC.match(_text(unit))
        if (polarity == "neg" and event.polarity != "negative"
                and event.predicate.startswith("싫") and re.match(r"^\s*(?:접었|하차했)", tail)):
            subject = f"{edition.group('edition')}의 {target}" if edition else target
            sentence = f"{voice}는 {subject}{_particle(subject, '을', '를')} 싫어해 읽기를 중단했다고 말한다."
        else:
            sentence = (f"{voice}는 {target}에 대해 {tense}{action}을 부정한다."
                        if event.polarity == "negative" else f"{voice}는 {target}에 {tense}{action}을 보인다.")
        if mode == "contrast":
            sentence += " 뒤의 대조·정정을 별도로 보존한다."
    else:
        return None
    subject = (f"{target}에 대한 {action}" + ("의 부정." if event.polarity == "negative" else ".")) if (mode == "actual" and event.final_support and event.actor == "self") else ""
    fragment = _make("source_event_structure", sentence, unit, primary=subject, role="reaction")
    if fragment is not None:
        a, z = event.predicate_span
        base = unit.proof.raw_span[0] - unit.proof.claim_object.span[0]
        fragment = replace(fragment, predicate_spans=((base + a, base + z),))
    return fragment


def _reported_doubt_fragment(unit, event):
    """타자 modal 사건의 원문 부정 의문만 기록한다. 선호·행동의 사실성은 채택하지 않는다."""
    if (unit.role != "author" or not unit.reported or unit.current_own
            or not _event_valid(unit, event) or event.final_support
            or event.realization not in {"modal", "question"}
            or not event.actor.startswith("other:")
            or event.actor[6:] != unit.proof.claim_object.speaker):
        return None
    text = _text(unit)
    hit = _DOUBTFUL_NEGATIVE_INSCRIPTION.fullmatch(text)
    if hit is None or "아니겠지" not in event.predicate:
        return None
    actor = event.actor[6:]
    sentence = (f"글쓴이의 본문에는 '{text}'라는 {actor}에 관한 추측성 부정 의문이 적혀 있다. "
                f"{actor}의 실제 선호나 앞 절 행동을 확인한 사실로 확정하지 않는다.")
    return _make(
        "source_reported_modal_doubt_inscription", sentence, unit, hit,
        primary=f"본문에 적힌 {actor}에 관한 추측성 부정 의문.", role="relation",
    )


def _guild_impression_compatible(name, description):
    """본문이 다른 길드를 명시하면 제목·본문을 함께 설명하지 않는다."""
    if _GUILD_OTHER_TARGET.search(description) or _GUILD_EXCLUSION.search(description):
        return False
    named_body = _GUILD_EXPLICIT_NAME.search(description)
    if named_body is not None and named_body.group("name") != name:
        return False
    before_guild = description[:-len("길드")].rstrip()
    if not before_guild:
        return False
    last_word = before_guild.split()[-1]
    if last_word == name:
        return True
    try:
        tokens = _nominal_kiwi().tokenize(last_word)
    except Exception:
        return False
    # `실패하지않은 길드`는 속성 서술이고 `검은달 길드`는 별도 명칭일 수 있다.
    # 품사로 관형 어미를 확인할 수 없는 bare 명사는 같은 대상이라고 추정하지 않는다.
    return bool(tokens and tokens[-1].tag == "ETM"
                and tokens[-1].start + tokens[-1].len == len(last_word))


def _guild_name_impression_fragment(units):
    """한 제목의 유일한 길드 이름 소개와 첫 본문의 길드 인상만 연결한다."""
    titles, bodies = [], []
    for unit in units:
        if unit.role != "author" or not _plain_own(unit):
            continue
        source = unit.proof.source_object
        if source.source_origin == "post_title":
            hit = _GUILD_NAME_FRAME.fullmatch(_text(unit))
            if hit and {"\"": "\"", "“": "”", "「": "」"}[hit.group("open")] == hit.group("close"):
                titles.append((unit, hit))
        elif source.source_origin == "body_line" and source.source_index == 0 and source.line_clause_index == 0:
            hit = _GUILD_IMPRESSION.fullmatch(_text(unit))
            if hit:
                bodies.append((unit, hit))
    if len(titles) != 1 or len(bodies) != 1:
        return None
    title, named = titles[0]
    body, impression = bodies[0]
    if (title.proof.ledger_object is not body.proof.ledger_object
            or title.proof.manifest_object is not body.proof.manifest_object
            or title.proof.source_object.source_index != 0
            or len(re.findall(r"[\"“「][^\"“”「」'\n]+[\"”」]", _text(title))) != 1):
        return None
    name = _argument(named.group("name"))
    description = _argument(impression.group("impression"))
    if not name or not description or not _guild_impression_compatible(name, description):
        return None
    sentence = (f"글쓴이는 제목에서 '{name}'를 길드 이름으로 소개하고, 본문 첫 줄에서 그 길드에 대해 "
                f"'{description}'라는 인상을 이어 적는다. "
                "이는 글 안의 화제 연결이며 실제 집단의 정체나 공략 기록, 공식 작품 제목을 확인한 사실은 아니다.")
    return _frag("source_guild_name_impression_relation", sentence, "reason", (title, body),
                 ((title, named), (body, impression)),
                 primary_subject="제목의 길드 이름 소개와 첫 본문의 길드 인상.", primary_role="relation")


def _media_absence_fragment(unit):
    """병렬 매체의 부재 평가를 단일 event 목적어로 줄이지 않는다."""
    if unit.role != "author" or not _plain_own(unit) or _is_question(unit):
        return None
    hit = _MEDIA_ABSENCE.fullmatch(_text(unit))
    if hit is None:
        return None
    media = re.findall(r"(웹툰|웹소설|소설|만화|애니|영화)도", hit.group("media"))
    if len(media) < 2 or len(set(media)) != len(media):
        return None
    subjects = "·".join(media)
    missing = hit.group("missing").strip()
    sentence = (f"글쓴이는 {subjects} 모두에 대해 「{missing}」라고 평가한다. "
                "한 매체만의 평가나 특정 작품의 완독 경험으로 좁히지 않는다.")
    return _make("source_coordinated_media_absence", sentence, unit, hit,
                 primary=f"{subjects} 모두에서 {missing}라는 평가.", role="reaction")


def _later_quality_limit_fragment(author):
    """초반 대비 후반의 평가와 명시된 예외를 같은 작성자 원절에 한정한다."""
    limits = [(u, m) for u in author if not _is_question(u)
              and (m := _QUALITY_LIMIT.fullmatch(_text(u))) is not None]
    if len(limits) != 1:
        return None
    limit, matched = limits[0]
    later = next((u for u in author if u is not limit and
                  (u.proof.source_object.source_origin == "body_line") and
                  _LATER_READING_LIMIT.fullmatch(_text(u))), None)
    if later is None or limit.proof.ledger_object is not later.proof.ledger_object:
        return None
    baseline, quality = _argument(matched.group("baseline")), matched.group("quality")
    if not baseline:
        return None
    exception = next(((u, m) for u in author if u not in (limit, later)
                      and (m := _NAMED_EXCEPTION.fullmatch(_text(u))) is not None
                      and u.proof.ledger_object is limit.proof.ledger_object), None)
    evidence = (limit, later) + ((exception[0],) if exception else ())
    sentence = (f"글쓴이는 {baseline}의 {quality}를 후반 전개가 넘기 어렵다고 평가하고, "
                f"「{_text(later)}」라는 독서 경험을 덧붙인다.")
    matches = ((limit, matched), (later, _LATER_READING_LIMIT.fullmatch(_text(later))))
    if exception:
        name = _argument(exception[1].group("exception"))
        if not name:
            return None
        sentence += f" 「{name}」{_particle(name, '은', '는')} 예외로 든다."
        matches += ((exception[0], exception[1]),)
    sentence += (" 작품별 후반 전개와 예외의 객관적 사실 여부는 확정하지 않는다."
                 if exception else " 작품별 후반 전개의 객관적 사실 여부는 확정하지 않는다.")
    return _frag("source_later_quality_limit_structure", sentence, "reason", evidence, matches,
                 primary_subject=(f"{baseline}의 {quality}를 기준으로 한 후반 전개 평가와 예외."
                                  if exception else f"{baseline}의 {quality}를 기준으로 한 후반 전개 평가."),
                 primary_role="relation")


def _comment_time_shift_fragment(unit):
    """한 댓글 안의 이전 판단과 뒤의 감정 변화를 단일 event로 축소하지 않는다."""
    if unit.role != "comment" or not _plain_own(unit) or _is_question(unit):
        return None
    hit = _COMMENT_TIME_SHIFT.fullmatch(_text(unit))
    if hit is None:
        return None
    earlier, later = hit.group("earlier").strip(), hit.group("later").strip()
    if not re.search(r"울컥|슬프|안타깝|놀랐|충격|감동|좋았|싫었", later):
        return None
    voice = _voice(unit)
    sentence = (f"{voice}는 「{earlier} 생각했는데」라는 앞선 판단을 소개하고, "
                f"뒤이어 「{later}」라고 반응한다. 뒤의 감정 변화를 앞부분의 평가 하나로 줄이지 않는다.")
    return _make("source_comment_temporal_evaluation_shift", sentence, unit, hit)


def _operator_fragments(unit, projection=None):
    text, voice = _text(unit), _voice(unit)
    is_question = _is_question(unit)
    if voice is None:
        return ()
    out = []

    def add(rule, sentence, hit, primary="", role="purpose"):
        fragment = _make(rule, sentence, unit, hit, primary=primary, role=role)
        if fragment is not None:
            out.append(fragment)

    report = _REPORT.fullmatch(text)
    if report:
        # 보고 어미를 떼면 '흔들렸다함'이 '흔들렸'으로 잘릴 수 있다.
        # 원절 전체를 인용해 서술어·조사를 새로 조합하지 않는다.
        sentence = (f"{voice}는 원문의 「{text}」라는 전언 표현이 있는지 묻는다. 전언의 존재나 내용을 확인된 사실·직접 경험으로 채택하지 않는다."
                    if is_question else f"{voice}는 원문의 「{text}」라는 전언 표현을 소개한다. 전언의 내용을 직접 경험이나 확인된 사실로 확정하지 않는다.")
        add("source_report_structure", sentence, report,
            f"「{text}」라는 전언" + (" 여부 질문." if is_question else " 표현."))
        return tuple(out)  # 내부 질문·조건·계획을 현재 화자 발화로 승격하지 않는다.
    if not _plain_own(unit):
        return tuple(out)
    reading_question = _READ_EXPERIENCE_Q.fullmatch(text)
    if reading_question and is_question:
        scope = _argument(reading_question.group("scope"))
        target = f"{scope} " if scope else ""
        experience = "읽어본 경험" if reading_question.group("reading").startswith("읽") else "본 경험"
        existence = "없는지" if reading_question.group("negative") else "있는지"
        add("source_reading_experience_question_structure",
            f"{voice}는 {target}{experience}이 {existence} 묻는다. 질문만으로 화자나 상대의 경험·미경험·완독 여부를 확정하지 않는다.",
            reading_question, f"{target}{experience}이 {existence} 묻는 질문.")
    negative = _NEGATED_CLAIM.fullmatch(text)
    if negative:
        content = _argument(negative.group("content"))
        if content:
            sentence = (f"{voice}는 {content}라는 주장을 부정하는지 묻는다. 질문을 본인의 반대 진술로 확정하지 않는다."
                        if is_question else f"{voice}는 {content}라는 주장을 부정한다. 주장 속의 조건이나 제외를 본인의 확정 평가로 채택하지 않는다.")
            add("source_negated_claim_structure", sentence, negative,
                f"{content}라는 주장에 대한 " + ("부정 여부 질문." if is_question else "반대."), "relation")
        return tuple(out)
    notice = _NOTICE.fullmatch(text)
    if notice:
        topic, item = _argument(notice.group("topic") or ""), _argument(notice.group("object"))
        if item:
            change = notice.group("change")
            target = f"{topic}의 {item}" if topic else item
            sentence = (f"{voice}는 {target} {change} 여부를 묻는다. 질문의 변경 전제를 확인된 소식으로 확정하지 않는다."
                        if is_question else f"{voice}는 {target} {change} 소식을 알린다. 원문 알림이며 외부 사실 확인과는 별개다.")
            add("source_change_notice_structure", sentence, notice,
                f"{target} {change} " + ("여부 질문." if is_question else "알림."))
    versus = _VS.fullmatch(text)
    if versus:
        left, right = _argument(versus.group("left")), _argument(versus.group("right"))
        if left and right:
            pair = f"{left}{_particle(left, '과', '와')} {right}"
            add("source_comparison_structure", f"{voice}는 {pair}{_particle(right, '을', '를')} 비교하는 화제를 꺼낸다.", versus,
                f"{pair}의 비교.")
    modal = _MODAL_Q.fullmatch(text)
    if modal and (is_question):
        content = _argument(modal.group("content"))
        if content:
            add("source_possibility_question_structure", f"{voice}는 {content}의 가능 여부를 묻는다. 가능하다는 결론이나 실행 사실은 아니다.", modal,
                f"{content}의 가능 여부 질문.")
    condition = _CONDITION.fullmatch(text)
    if condition:
        prerequisite = _argument(condition.group("condition"))
        if prerequisite:
            q = is_question
            result = condition.group("content").strip()
            if q or _CONDITION_MODAL_RESULT.search(result):
                act = "질문" if q else "생각·추측"
                sentence = (f"{voice}는 {prerequisite} 조건을 둔 {act}을 제시한다: 「{result}」라는 {act}이다. "
                            "조건의 성립이나 이후 결과를 실제 사건으로 단정하지 않는다.")
            elif _CONDITION_REQUEST_RESULT.search(result):
                act = "요청"
                sentence = f"{voice}는 {prerequisite} 경우에 응답을 요청한다. 조건이 실제 성립했다고 단정하지 않는다."
            else:
                act = "일반적 평가·설명"
                sentence = f"{voice}는 '{prerequisite} {result}'라고 설명한다. 조건이 실제 특정 사건으로 성립했다고 단정하지 않는다."
            add("source_condition_structure", sentence, condition,
                f"{prerequisite} 조건에서 「{result}」라는 {act}.", "relation")
    wh = _WH_Q.fullmatch(text)
    if wh and (is_question or _WH_BARE_QUESTION_END.search(text)):
        focus = "이유" if wh.group("wh") in {"왜", "어째서"} else "결과" if wh.group("wh") in {"어떻게", "어케"} and re.match(r"^(?:됨|되나|되냐|될까)", wh.group("after")) else "방법" if wh.group("wh") in {"어떻게", "어케"} else "시점" if wh.group("wh") == "언제" else "대상"
        add("source_wh_question_structure", f"{voice}는 '{text}'라고 {focus}{_particle(focus, '을', '를')} 묻는다. 질문의 전제를 확인된 사실로 확정하지 않는다.", wh,
            f"'{text}'의 {focus} 질문.")
    question = _Q_END.fullmatch(text.rstrip("?？.!~… "))
    if question and is_question and not (modal or wh or condition or reading_question):
        content = _argument(question.group("content"))
        if content:
            quality_end = _Q_QUALITY_END.search(text.rstrip("?？.!~… "))
            quality = _Q_QUALITY[quality_end.group("stem")] if quality_end else ""
            sentence = (f"{voice}는 '{text}'라고 물어 {quality} 확인하려 한다."
                        if quality else f"{voice}는 '{text}'라고 묻는다.")
            add("source_proposition_question_structure", sentence + " 질문을 확정 진술로 바꾸지 않는다.", question,
                f"'{text}'라는 확인 질문.")
    plan = _PLAN.fullmatch(text)
    if plan:
        action = _argument(plan.group("action"))
        if action:
            sentence = (f"{voice}는 {action}의 실행 계획이 있는지 묻는다. 계획이나 실행 경험을 확정하지 않는다."
                        if is_question else f"{voice}는 {action}의 실행 계획을 밝힌다. 이미 실행했다는 경험으로 바꾸지 않는다.")
            add("source_plan_structure", sentence, plan,
                f"{action}에 관한 " + ("계획 여부 질문." if is_question else "실행 계획."))
    copula = _NOMINAL_COPULA.fullmatch(text)
    if copula and not (condition or report or plan):
        topic, value = _argument(copula.group("topic")), _argument(copula.group("value"))
        if topic and value and _has_topic_particle(text, copula):
            sentence = (f"{voice}는 {topic}{_particle(topic, '을', '를')} {value}{_directional_particle(value)} 볼 수 있는지 묻는다. 질문을 본인의 지목이나 확인된 사실로 채택하지 않는다."
                        if is_question else f"{voice}는 {topic}{_particle(topic, '을', '를')} {value}{_directional_particle(value)} 지목한다. 원문 화자의 주장이고 외부 사실이나 다른 화자의 동의를 확정한 설명은 아니다.")
            add("source_nominal_predication_structure", sentence, copula,
                f"{topic}에 대한 {value} " + ("지목 여부 질문." if is_question else "지목."))
    media = _MEDIA_FRAME.fullmatch(text)
    if media and not (condition or report):
        description = _argument(media.group("description"))
        if description:
            sentence = (f"{voice}는 {description} 구도가 {media.group('media')}의 내용인지 묻는다. 질문의 내용을 작품 속 사실이나 화자의 경험으로 확정하지 않는다."
                        if is_question else f"본문은 {description} 구도를 {media.group('media')}의 내용으로 소개한다. 현실 작성자의 행위나 제목 미상 매체의 공식 식별로 바꾸지 않는다.")
            add("source_media_content_structure", sentence, media)
    partials = tuple(hit for hit in _PARTIAL.finditer(text) if _affirmed_partial_hit(text, hit))
    if partials:
        partial = partials[0]
        ranges = tuple(dict.fromkeys(
            hit.group('drop') if hit.lastgroup == 'drop' else
            ('초반부' if hit.group('early').startswith('초반부') else '초반') if hit.lastgroup == 'early' else
            '언급된 지점까지의 미독' for hit in partials))
        reading_range = '·'.join(ranges)
        if is_question:
            sentence = f"{voice}의 질문에는 {reading_range} 범위 표현이 있다. 질문만으로 화자의 독서 경험·미독·완독을 확정하지 않는다."
        elif any(hit.lastgroup == 'not_reached' for hit in partials):
            sentence = f"{voice}는 언급된 지점까지는 읽지 않았다고 밝힌다. 다른 지점까지의 독서나 완독 여부는 이 표현으로 확정하지 않는다."
        elif condition or report:
            sentence = f"{voice}는 조건·전언 속에서 {reading_range} 범위를 언급한다. 이를 현재 본인의 독서 경험으로 확정하지 않는다."
        else:
            sentence = f"{voice}의 독서 경험은 {reading_range}로 명시된 범위에 한정된다. 완독이나 다른 판본의 경험을 추가하지 않는다."
        add("source_reading_range_structure", sentence, partial)
    memory = _MEMORY.search(text)
    if memory:
        reading = _READ.search(text)
        if is_question:
            sentence = f"{voice}는 기억·판단의 불확실성에 관해 묻는다. 질문을 본인의 독서 경험이나 불확실한 기억 상태로 확정하지 않는다."
        else:
            sentence = f"{voice}는 읽거나 본 경험이 있더라도 내용에 관한 기억은 불확실하다고 표현한다." if reading else f"{voice}는 내용에 관한 기억·판단의 불확실성을 표현한다."
        add("source_uncertain_memory_structure", sentence, memory)
    person = _get(projection, "target_surface")
    relation_kind = _get(projection, "target_kind")
    relation = (_new_work_head_match(person, text)
                if relation_kind in {'author_new_work', 'work_new_work'} and person else None)
    if relation is not None:
        action = "묻는다" if is_question else "이야기한다"
        head = relation.group('head')
        if relation_kind == 'author_new_work':
            target = f"{person}의 이름 미상 {head}"
            sentence = f"{voice}는 {person}의 {head}에 관해 {action}. {person}{_particle(person, '은', '는')} 이 원문의 작가→신작 관계에서 앞쪽 표면이며 신작의 제목을 뜻하지 않는다."
        else:
            target = f"{person}에 연결된 제목 미상 {head}"
            sentence = f"{voice}는 {target}에 관해 {action}. 원문의 앞쪽 작품 표면을 작가 이름이나 뒤쪽 작품의 공식 제목으로 확정하지 않는다."
        fragment = _make("source_" + relation_kind + "_structure", sentence, unit,
            primary=target + "에 관한 " + ("질문." if is_question else "글."), role="relation")
        if fragment is not None:
            out.append(fragment)
    return tuple(out)


def source_speech_fragments(units, projection=None):
    """같은 source unit의 event/operator를 합성한다. 모호한 관계만 남기고 무관한 정보는 추가하지 않는다."""
    units = tuple(u for u in units if exact_unit(u))
    result = []
    comment_rebuttals = []
    for before, after in zip(units, units[1:]):
        first, second = before.proof, after.proof
        if (before.role != "comment" or after.role != "comment"
                or not (_plain_own(before) and _plain_own(after))
                or before.original_index != after.original_index
                or first.origin_object is not second.origin_object
                or first.comment_object is None or first.comment_object is not second.comment_object
                or first.raw_path != second.raw_path
                or not (first.raw_span[1] < second.raw_span[0])
                or first.origin_object.raw_text[first.raw_span[1]:second.raw_span[0]].strip()
                or not (_is_question(before) and not _is_question(after))
                or _REBUTTAL_WH.fullmatch(_text(before)) is None
                or _REBUTTAL_REASON.fullmatch(_text(after)) is None):
            continue
        voice = _voice(before)
        fragment = _frag(
            "source_comment_rhetorical_rebuttal_structure",
            f"{voice}는 「{_text(before)}」라고 반문하고 「{_text(after)}」를 이유로 들어 "
            "그 댓글 안에서 거론한 일을 할 이유가 없다는 취지로 반박한다. "
            "뒤 절은 댓글 화자의 주장이지 외부 사실 확인은 아니다.",
            "note", (before, after),
        )
        comment_rebuttals.append((before, fragment))
    for unit in units:
        operators = _operator_fragments(unit, projection)
        if any(before is unit for before, _ in comment_rebuttals):
            operators = tuple(f for f in operators if f.rule != "source_wh_question_structure")
        result.extend(operators)
        media_absence = _media_absence_fragment(unit)
        if media_absence is not None:
            result.append(media_absence)
        time_shift = _comment_time_shift_fragment(unit)
        if time_shift is not None:
            result.append(time_shift)
        for event in unit.proof.event_objects:
            doubt = _reported_doubt_fragment(unit, event)
            if doubt is not None:
                result.append(doubt)
            fragment = None if (media_absence is not None or time_shift is not None) else _event_fragment(unit, event, projection)
            if fragment is not None:
                result.append(fragment)
    guild_impression = _guild_name_impression_fragment(units)
    if guild_impression is not None:
        result.append(guild_impression)
    author = [u for u in units if u.role == "author" and _plain_own(u) and not _REPORT.fullmatch(_text(u))]
    later_quality = _later_quality_limit_fragment(author)
    if later_quality is not None:
        result = [f for f in result if not (f.rule == "source_event_structure"
                  and any(u is later_quality.unit_objects[0] for u in f.unit_objects))]
        result.append(later_quality)
    for before, after in zip(author, author[1:]):
        # 같은 원 block/인접 원 line만 연결한다. 생략 주어를 다른 화자/멀리 떨어진 문장으로 잇지 않는다.
        a, b = before.proof.source_object, after.proof.source_object
        if not (a.source_origin == b.source_origin and a.source_index <= b.source_index <= a.source_index + 1):
            continue
        premise = _COMPARE_PREMISE.fullmatch(_text(before))
        conclusion = _NEGATED_CONCLUSION.fullmatch(_text(after))
        if premise and conclusion:
            ref = _argument(premise.group("reference"))
            quality = _argument(premise.group("quality"))
            outcome = _argument(conclusion.group("result"))
            if ref and quality and outcome:
                q = _is_question(before) or _is_question(after)
                sentence = (f"글쓴이는 {ref}보다 {quality}다는 비교가 {outcome}{_particle(outcome, '을', '를')} 보장하지 않는지 묻는다. 질문을 최종 평가로 채택하지 않는다."
                            if q else f"글쓴이는 {ref}보다 {quality}다는 비교가 {outcome}{_particle(outcome, '을', '를')} 보장하지 않는다고 평가한다. 비교 우위와 최종 평가를 구분한다.")
                result.append(_frag("source_comparison_not_sufficient_structure", sentence, "reason", (before, after), ((before, premise), (after, conclusion)),
                    primary_subject=f"{ref}{_particle(ref, '과', '와')}의 비교와 {outcome}의 관계에 관한 " + ("질문." if q else "평가."), primary_role="relation"))
        exclusion = _EXCLUDE.fullmatch(_text(after))
        if exclusion and _is_question(before):
            scope = _argument(exclusion.group("except"))
            if scope:
                result.append(_frag("source_question_exclusion_structure", f"글쓴이는 앞의 질문 범위에서 {scope} 경우를 제외한다. 제외한 경우를 질문의 답이나 실제 사건으로 채택하지 않는다.", "note", (before, after), ((after, exclusion),)))
    comments = [u for u in units if u.role != "author" and _plain_own(u)]
    for before, after in zip(comments, comments[1:]):
        if after.original_index != before.original_index + 1 or not _VS.fullmatch(_text(before)):
            continue
        answer = _COMPARISON_RESULT_REPLY.fullmatch(_text(after))
        if answer is None:
            continue
        form = answer.group("result")
        outcome = "승리" if form.startswith(("이기", "이겼")) else "패배" if form.startswith(("지긴", "졌")) else "무승부"
        label = _voice(after)
        result.append(_frag(
            "source_comparison_result_reply_structure",
            f"{label}는 앞선 비교에 이어 '{form}'라고 {outcome} 쪽 답을 적는다. 이는 댓글의 반응이며 실제 대상의 승패를 외부 사실로 확인한 설명은 아니다.",
            "note", (before, after), ((after, answer),)))
    result.extend(fragment for _, fragment in comment_rebuttals)
    return tuple(dict((f.sentence, f) for f in result).values())
