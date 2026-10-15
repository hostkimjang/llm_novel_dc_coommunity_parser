"""작품·장르 발화의 목적과 태도를 exact 원문에서 읽는다.

entry에 제품 grammar의 exact_unit/_frag/praise_scope를 callback으로 넘긴다.
입력은 기존 _bound_units의 동일 객체여야 한다. core/공식 권한을 부여하지 않는다.
"""
import re

_END = r"[.!?？~…ㅋㅇㅠㅜ ]*$"
_APP = re.compile(r"\s*-\s*dc\s*(?:official\s*)?App\s*$", re.I)
_REPORT = re.compile(r"(?:라고|다고)\s*(?:함|한다|들었)|라는데|다는데|다던데|다더라|다함")
_PAST_Q = re.compile(r"[?？].{0,30}(?:물어본|물었|질문했)|과거.{0,20}질문")
_CONDITION = re.compile(r"라면|다면|으면|(?<!화)면\s*(?:좋|재밌|읽)|했을\s*때")
_NARRATIVE = re.compile(r"작품|소설|주인공|히로인|장면|서사|전개|회차|이번화|빌런|하렘|빙의|회귀|웹툰|만화|판본")
_VAGUE = re.compile(r"^(?:이거|그거|저거|그냥|좀|너무|뭔가|최근|나는|난|ㄹㅇ|계속|정말|다들|지금)[은는이가도 ]*$")
_READ = re.compile(r"읽(?:었|어\s*봤|어봤|는\s*중)|(?:초반부?|이번화|막화|최신화|회차).{0,25}(?:보|읽)|(?:보는\s*중|보는중|보는중인)|하차|접었|손\s*떼")
_NOT_READ = re.compile(r"(?:안|못)\s*(?:읽|봤|보았)|읽.{0,10}않|봤.{0,10}않")
_PARTIAL_READ = re.compile(r"(?:초반부?|이번화|막화|최신화|회차).{0,25}(?:보|읽)|(?:보는\s*중|보는중)|하차|접었|손\s*떼")
_COMPLETED_READ = re.compile(r"완독|끝까지\s*(?:다\s*)?읽|다\s*읽었")
_REQUEST = re.compile(r"(?P<wanted>.+?)\s*추천\s*(?:좀|해\s*(?:줘|조)|부탁(?:해)?|요청(?:함)?)" + _END)


def is_recommendation_request_text(text):
    """인용 표현의 뜻을 묻는 질문과 실제 추천 요청의 어미를 구분한다."""
    return bool(_REQUEST.fullmatch(text) or re.fullmatch(r".*?(?:작품|소설|글).{0,20}없냐" + _END, text))


def surface_role_predicate(text, surface, role):
    """명시된 표면 바로 뒤의 술어만 연결해 다른 대상의 독서 경험을 붙이지 않는다."""
    predicates = {
        "read": r"(?:이미\s*)?(?:읽었|봤|보았)",
        "exclude": r"(?:제외|빼\s*(?:줘|주|달라))",
        "reference": r"(?:비슷한\s*(?:느낌|누낌)|같은\s*느낌|처럼)",
    }
    predicate = predicates.get(role)
    if not surface or predicate is None or text.count(surface) != 1:
        return None
    if role in {"read", "exclude", "reference"} and re.search(r"[?？]", text):
        return None
    return re.search(r"(?<![0-9A-Za-z가-힣])" + re.escape(surface)
                     + r"(?:은|는|이|가|도|와|랑)?\s*" + predicate, text)


def _get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _text(u):
    # view는 원 claim의 연속 구간이다. emit이 유일 occurrence와 raw offset을 검산한다.
    return _APP.sub("", u.text).strip()


def _own(u, exact):
    return (exact(u) and u.role == "author" and u.current_own
            and u.proof.claim_kind == "own" and u.proof.final_support is True
            and u.proof.claimant == "self")


def _plain(u):
    t = _text(u)
    return not (_REPORT.search(t) or _PAST_Q.search(t)
                or re.search(r"취소|철회|정정", t) or u.record_kind == "past_recollection")


def _named_content(t):
    return bool(t.strip() and not _VAGUE.fullmatch(t.strip()))


def _emit(emit, rule, sentence, units, match=None, destination="reason", unresolved=()):
    return emit(rule, sentence, destination, tuple(units),
                ((units[0], match),) if match else (), tuple(unresolved))


def sympathy(u, all_units, projection, exact, emit, scope):
    """인물·사건을 향한 안타까움. 인물 생사/원인 사실은 추가하지 않는다."""
    if not _own(u, exact) or not _plain(u) or scope(u, projection)[0] != "affirmative_candidate":
        return ()
    t = _text(u)
    if re.search(r"(?:불쌍|안타깝|안쓰럽|가엾).{0,12}(?:않|아니|겠)", t):
        return ()
    m = re.fullmatch(r"(?P<target>.+?)\s*(?:너무\s*)?(?:불쌍(?:해|하|다)|안타깝|안쓰럽|가엾).*", t)
    if not m or not _named_content(m.group("target")):
        return ()
    target = m.group("target").strip()
    # 원문 표면이 작품명인지 인물명인지 추가 분해하지 않는다.
    return (_emit(emit, "sympathy_toward_content", f"{target}에 안타까움을 보이는 독자 반응이다. 인물의 운명이나 사건 원인을 외부 사실로 확인한 설명은 아니다.", (u,), m,
                  unresolved=("U: 원문 표면의 공식 작품·인물 연결",)),)


def dissatisfaction(u, all_units, projection, exact, emit, scope):
    """명시된 불만과 같은 문장 안의 독서 범위·원인을 결합한다."""
    if not _own(u, exact) or not _plain(u) or _CONDITION.search(_text(u)) or u.source_question:
        return ()
    t = _text(u)
    if "?" in t or "？" in t:
        return ()
    m = re.search(r"(?P<negative>몰입\s*안(?:대|돼|됨)|루즈|오글|불쾌|아쉽|노잼|못\s*보겠|비중.{0,10}없|폼.{0,10}나락)", t)
    if not m:
        return ()
    if re.search(r"(?:불쾌|아쉽|루즈|오글|노잼).{0,8}(?:않|아니)", t):
        return ()
    state = scope(u, projection)[0]
    if state in {"reported_surface", "unresolved_attribution", "other_actor", "retracted", "event_scope_hold"}:
        return ()
    # 평가 술어 바로 앞의 명시 주어만 대상 표면으로 쓴다. 독서 절·감탄사는 대상이 아니다.
    aspect = re.search(r"(?P<target>[^\s.!?。！？:：]+?)(?:은|는|이|가)\s*$", t[:m.start()])
    reading_target = re.match(r"(?P<target>[^\s.!?。！？:：]+)\s+(?P<range>초반부?|이번화|막화|최신화|회차)\s*(?:보|읽)", t)
    target_description = f"원문 대상 「{aspect.group('target')}」에 대해 " if aspect else ""
    if reading_target:
        target_description = f"「{reading_target.group('target')}」의 {reading_target.group('range')} 독서 중 " + target_description
    reaction = f"{target_description}불만을 말한다(원문 표현: 「{m.group('negative')}」). "
    reading = _READ.search(t)
    if _COMPLETED_READ.search(t):
        sentence = reaction + "원문에서 끝까지 읽었다고 밝힌 경험이다. 실제 완독 여부를 외부 자료로 확인한 것은 아니다."
    elif _PARTIAL_READ.search(t):
        sentence = reaction + "같은 문장에 밝힌 초반·회차·부분 독서 범위의 경험으로 한정된다. 완독 평가로 확대하지 않는다."
    elif reading:
        sentence = reaction + "읽어본 경험을 말하며 명시되지 않은 독서 범위나 완독 여부를 추가하지 않는다."
    elif _NARRATIVE.search(t) or re.search(r"댓글.{0,25}(?:때문|대문)", t):
        sentence = reaction + "명시되지 않은 완독 경험이나 다른 작품의 평가를 붙이지 않는다."
    else:
        return ()
    return (_emit(emit, "bounded_dissatisfaction", sentence, (u,), m,
                  unresolved=("U: 구체 불만 대상·완독 여부의 외부 인증",)),)


def feature_or_event_question(u, all_units, projection, exact, emit, scope):
    """현재 특성/사건/행위자 질문. 본문·제목의 전제를 실제 사건으로 세지 않는다."""
    if not _own(u, exact) or not _plain(u):
        return ()
    t = _text(u)
    if not (u.source_question or "?" in t or "？" in t):
        return ()
    if _CONDITION.search(t):
        return ()
    m = re.fullmatch(r"(?P<target>.+?)\s*(?:이거\s*)?(?P<feature>하렘|TS|ts|빙의|회귀|NTR|NTL|ntr|ntl)(?:임|인가|맞음|맞나)" + _END, t)
    if m:
        return (_emit(emit, "current_narrative_feature_question", f"{m.group('target').strip()}가 {m.group('feature')} 성격의 작품인지 확인하려는 질문이다. 질문만으로 그 특성을 확정하지 않는다.", (u,), m),)
    m = re.fullmatch(r"(?P<event>.+?)\s*(?:맞는거임|맞는\s*거임|사실임|맞음|맞나)" + _END, t)
    if m and _named_content(m.group("event")):
        # event는 이미 조사·관형형·의존명사로 끝날 수 있다. 어미를 더 붙이지 않고
        # 원문 질문 전체를 인용해 질문의 기능만 설명한다.
        return (_emit(emit, "current_event_interpretation_question",
                      f"글쓴이는 사건 해석이 맞는지 묻는다(원문 질문: 「{m.group(0)}」). "
                      "실제 발생과 인물 관계를 확정한 진술은 아니다.", (u,), m),)
    m = re.fullmatch(r"(?P<action>.+?)\s*(?:애가\s*)?누가\s*있나" + _END, t)
    if m and _named_content(m.group("action")):
        return (_emit(emit, "possible_actor_question", f"「{m.group(0)}」라고 해당 행동을 할 인물이 누구인지 묻는다. 앞으로의 가능성을 이미 일어난 사건으로 바꾸지 않는다.", (u,), m,
                      unresolved=("U: 생략된 인물·능력 관계",)),)
    return ()


def genre_preference(u, all_units, projection, exact, emit, scope):
    """원하는 장면/유형 또는 비교된 서사 취향. 특정 작품 권한은 별개."""
    if not _own(u, exact) or not _plain(u) or u.source_question or _CONDITION.search(_text(u)):
        return ()
    t = _text(u)
    if re.search(r"(?:안|못)\s*(?:보고\s*싶|좋아)|좋아.{0,8}않", t):
        return ()
    m = re.fullmatch(r"(?P<wanted>.+?)\s*(?:보고\s*싶(?:다|어)|땡김|원함|좋아함|취향임|끌림)" + _END, t)
    if m and _NARRATIVE.search(m.group("wanted")):
        return (_emit(emit, "desired_narrative_content", f"{m.group('wanted').strip()} 같은 장면·유형을 보고 싶다는 취향을 말한다. 특정 작품에서 이미 보았다는 독서 사실과는 별개다.", (u,), m),)
    m = re.fullmatch(r"(?P<narrative>.+?)\s*(?:은|는)\s*(?P<character>.+?)(?:한테|에게)\s*더\s*어울리(?:더라|는듯|는\s*듯|다)" + _END, t)
    if m and _NARRATIVE.search(m.group("narrative")):
        return (_emit(emit, "narrative_character_fit", f"{m.group('narrative').strip()}를 {m.group('character').strip()} 유형의 캐릭터에 더 잘 맞는 서사로 보는 취향이다. 이를 특정 작품의 실제 설정으로 확정하지 않는다.", (u,), m),)
    return ()


def recommendation_and_exclusion(u, all_units, projection, exact, emit, scope):
    """추천 어미와 원문 기준/이미 읽은 제외를 별도 역할로 다룬다."""
    if not _own(u, exact) or not _plain(u):
        return ()
    t = _text(u)
    result = []
    # 현재 요청의 목적은 별도 request plan에서 역할별로 한 번만 선택한다.
    requests = tuple(x for x in all_units if _own(x, exact) and _plain(x)
                     and is_recommendation_request_text(_text(x)))
    if not requests:
        return tuple(result)
    roles = _get(projection, "work_roles", ())
    for surface, role, basis in roles:
        if not surface or surface not in t:
            continue
        if role == "reference" and surface_role_predicate(t, surface, "reference"):
            result.append(_emit(emit, "request_comparison_reference", f"{surface}는 찾는 작품의 느낌을 설명하는 비교 기준이다. 추천 대상이나 공식 제목을 새로 확정하는 표면은 아니다.", (u, *requests),
                                destination="note"))
        if role != "excluded" or _CONDITION.search(t) or _NOT_READ.search(t) or u.source_question:
            continue
        read = surface_role_predicate(t, surface, "read")
        exclude = surface_role_predicate(t, surface, "exclude")
        if read:
            result.append(_emit(emit, "already_read_exclusion", f"{surface}는 이미 읽거나 보았다고 밝힌 제외 대상이다. 완독 여부와 다른 판본까지는 확정하지 않는다.", (u, *requests), read, "note",
                                ("U: 완독·판본 연결",)))
        elif exclude:
            result.append(_emit(emit, "explicit_requested_exclusion", f"{surface}는 추천에서 빼 달라는 조건이다. 제외 요청만으로 이미 읽었다고 단정하지 않는다.", (u, *requests), exclude, "note"))
    return tuple(result)


def counterfactual_preference(u, all_units, projection, exact, emit, scope):
    """실제 전개와 '그랬어야/그랬으면 좋겠다'의 선호를 분리한다."""
    if not _own(u, exact) or not _plain(u) or u.source_question:
        return ()
    t = _text(u)
    m = re.fullmatch(r"(?P<wanted>.+?)(?:이었어야|였어야|했어야)(?:돼|됨|해|했다|되는데)?" + _END, t)
    if m and _NARRATIVE.search(t):
        return (_emit(emit, "counterfactual_narrative_preference", f"{m.group('wanted').strip()}라는 방향으로 전개되었어야 한다는 반사실적 선호를 말한다. 실제 작품이 그렇게 전개되었다는 주장은 아니다.", (u,), m),)
    m = re.fullmatch(r"(?P<condition>.+?(?:으면|면))\s*(?:더\s*)?(?:좋겠(?:다|음)|좋지|재밌겠(?:다|음)|나았을\s*듯)" + _END, t)
    if m and (_NARRATIVE.search(t) or re.search(r"일기|연재|올리", t)):
        return (_emit(emit, "conditional_narrative_wish", f"{m.group('condition').strip()} 좋겠다는 조건부 취향·희망이다. 실제 발생이나 앞으로의 실행을 확정하지 않는다.", (u,), m),)
    return ()


def work_genre_purpose_fragments(units, projection, *, exact, emit, scope):
    """동일 native units를 여섯 유한 family에 한 번 통과시킨다."""
    units = tuple(units)
    families = (sympathy, dissatisfaction, feature_or_event_question,
                genre_preference, recommendation_and_exclusion, counterfactual_preference)
    result = []
    for u in units:
        for family in families:
            result.extend(family(u, units, projection, exact, emit, scope))
    return tuple(result)

# 긍정 어미를 문장 말미에서 완결된 술어로만 읽는다. 부분 substring은 쓰지 않는다.
# 이 목록은 강도 부사의 문법 역할이며, prefix를 지우는 blacklist가 아니다.
_EVALUATION = re.compile(
    r"(?P<reaction>(?:(?:더|아주|매우|정말|진짜|ㄹㅇ|존나|무척|꽤|참)\s*)*"
    r"(?P<predicate>좋(?:구나|다|음|네|았음|았다|았네|아)|"
    r"재밌(?:다|네|음|었음|었다|었네)|재미\s*있(?:다|네|음|었다|었음)|"
    r"(?:맘|마음)에\s*(?:듦|든다|들었음)))\s*[.!。！~…]*\s*$"
)
_SUBJECT = re.compile(r"(?P<target>[^.!?。！？:：\n]+?)(?P<particle>은|는|이|가)\s+")
_CAUSE = re.compile(r"(?P<cause>.+(?:아서|어서|여서|져서|줘서|해서|이라서|라서))\s*$")
_LOW_EXPECTATION_READ = re.compile(
    r"(?P<expectation>(?:별|큰)?\s*기대\s*(?:안\s*하고|하지\s*않고|없이))\s*"
    r"(?P<reading>본\s*건데|봤는데|보았는데|읽었는데|읽은\s*건데)\s*$"
)
_COORDINATED_DESCRIPTION = re.compile(r".+고\s*$")
_EMOTE_TAIL = re.compile(r"\s+(?:ㅇㅇ|ㅋㅋ|ㄷㄷ)+\s*$")


def _subject(prefix):
    """공백으로 닫힌 조사 경계가 단 하나일 때만 표면 대상을 채택한다."""
    candidates = list(_SUBJECT.finditer(prefix))
    if len(candidates) != 1 or candidates[0].start() != 0:
        return None
    match = candidates[0]
    target = match.group("target").strip()
    return (target, prefix[match.end():].strip()) if target else None


def praise_relation_fragment(unit, projection, *, exact, scope, emit):
    """(fragment, U reason). emit은 기존 _frag; 동일 native 객체를 전달한다.

    원 claim 밖 제목/작가/공식명/LLM prose 또는 projection 대상의 복원은 하지 않는다.
    관계 해석이 실패하면 None이며 원 prefix를 새 목적어로 바꾸는 fallback이 없다.
    """
    if not exact(unit):
        return None, "U: exact native 원문 결속 없음"
    if not _get(unit, "current_own", False) or _get(unit, "reported", False):
        return None, "U: 현재 작성자 평가 귀속 아님"
    if _get(unit, "source_question", False):
        return None, "U: 질문"
    if scope(unit, projection)[0] != "affirmative_candidate":
        return None, "U: 기존 질문·조건·전언·부정·허용·독서 범위 gate"
    for event in unit.proof.event_objects:
        if (_get(event, "realization") in {"question", "modal", "reported", "conditional", "embedded"}
                or _get(event, "actor") not in {None, "", "self"}
                or _get(event, "final_support") is not True):
            return None, "U: native event 화자·성립 범위"
    text = _EMOTE_TAIL.sub("", _APP.sub("", unit.text)).strip()
    reaction = _EVALUATION.search(text)
    if not reaction:
        return None, "U: 완결된 평가 술어 없음"
    # 부분 단어를 붙잡는 것을 막는다. '안좋다', '미좋다' 등의 내부 시작 불허.
    if reaction.start() and not text[reaction.start() - 1].isspace():
        return None, "U: 평가 술어 시작 경계 불명확"
    prefix = text[:reaction.start()].strip()
    predicate = reaction.group("reaction")
    if not prefix:
        return None, "U: 구체적 대상·이유 관계 없음"
    expectation = _LOW_EXPECTATION_READ.fullmatch(prefix)
    if expectation:
        sentence = (f"‘{expectation.group('expectation')}’라고 밝힌 독서 전 기대와 "
                    f"읽은 뒤의 ‘{predicate}’라는 감상을 대비한다.")
        rule = "praise_after_low_expectation_reading"
        matches = ((unit, expectation), (unit, reaction))
    else:
        cause = _CAUSE.fullmatch(prefix)
        subject = _subject(prefix)
        if cause:
            # 이유절 자체는 원문의 화자 평가 근거다. 작품 속 확정 사실로 승격하지 않는다.
            target = f"대상 ‘{subject[0]}’에 대해 " if subject else ""
            sentence = f"{target}‘{cause.group('cause')}’라는 이유로 좋게 평가한다(원문 반응: 「{predicate}」)."
            rule = "praise_with_source_cause"
            matches = ((unit, cause), (unit, reaction))
        elif subject:
            target, description = subject
            if description and not _COORDINATED_DESCRIPTION.fullmatch(description):
                return None, "U: 대상 뒤 묘사·평가 연결 문법 불명확"
            detail = f"‘{description}’라는 묘사와 함께 " if description else ""
            sentence = f"원문 대상 ‘{target}’에 대해 {detail}좋게 평가한다(원문 반응: 「{predicate}」)."
            rule = "praise_with_explicit_subject"
            boundary = _SUBJECT.match(prefix)
            matches = ((unit, boundary), (unit, reaction))
        else:
            return None, "U: 칭찬 대상·이유·양보 경계 불명확"
    # emit(_frag)의 raw_span 환원은 claim 전체와 predicate substring이 단일 대응일 때만 가능.
    fragment = emit(rule, sentence, "reason", (unit,), matches=matches)
    return fragment, ""
