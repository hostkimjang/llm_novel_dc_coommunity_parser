"""일상·플랫폼 발화의 목적과 조건을 exact 원문에서 읽는다."""
import re
from .source_context_grammar import exact_unit, _text, _frag

def _everyday_author(u):
    return exact_unit(u) and u.role == "author"


def _everyday_pair(a, b):
    # 표시명이 아니라 기존 native 문서와 저자 원장 객체로만 결속한다.
    same_carrier = (_everyday_author(a) and _everyday_author(b)
            and a.proof.document_object is b.proof.document_object
            and a.proof.manifest_object is b.proof.manifest_object
            and a.proof.ledger_object is b.proof.ledger_object)
    if not same_carrier:
        return False
    sources = a.proof.ledger_object.sources
    positions = {id(source): index for index, source in enumerate(sources)}
    # 제목/본문의 별도 index를 합치지 않고 같은 원장의 바로 다음 절만 잇는다.
    return positions.get(id(b.proof.source_object), -2) - positions.get(id(a.proof.source_object), -1) == 1


def meal_constraint_fragment(units):
    # 식사 계획 + 대안 요청. 병명/섭취 제한은 진술 그대로 별도 설명한다.
    for a in units:
        if not (_everyday_author(a) and a.current_own):
            continue
        ma = re.fullmatch(r"(?:그냥\s*)?(?P<plan>.+?(?:사서|먹고|먹을지|때릴지).+?)(?:려는데|고민중)[.!… ]*", _text(a))
        if not ma or not re.search(r"(?:먹|떼우|때우|때리|식사하)(?:으)?$", ma.group("plan")):
            continue
        for b in units:
            if not (_everyday_pair(a, b) and b.current_own):
                continue
            mb = re.fullmatch(r"(?:이보다\s*)?(?:나은|다른)\s*(?:대안|메뉴)\s*(?:있으면|있다면)\s*(?:말해주오|알려줘|추천해줘)[.!? ]*", _text(b))
            if mb:
                return _frag("meal_alternative_request",
                    f"작성자는 ‘{ma.group('plan')}’라는 식사 계획을 말하고 더 나은 대안을 묻는다.",
                    "reason", (a,b), ((a,ma),(b,mb)),
                    ("식사 실행·건강 효과·안전성은 확인하지 않음",))
    for u in units:
        if not (_everyday_author(u) and u.current_own):
            continue
        m = re.fullmatch(r"(?P<state>.+?)(?:걸려서|아파서)\s*(?P<food>.+?)(?:건|것은)\s*못\s*먹(?:음|는다)[.! ]*", _text(u))
        if m:
            return _frag("self_reported_food_constraint",
                f"작성자는 ‘{m.group('state')}’ 때문에 ‘{m.group('food')}’을 먹지 못한다고 말한다.",
                "note", (u,), ((u,m),), ("본인의 이유 진술이며 진단·섭취 금기 근거가 아님",))
    return None


def life_assumption_fragment(units):
    for u in units:
        if not _everyday_author(u):
            continue
        t = _text(u)
        m = re.fullmatch(r"(?:근데\s*)?(?P<condition>.+?)(?:하면|라면|이라고\s*치면)\s*(?:어케됨|어떻게\s*됨|어떻게\s*될까)[?？.! ]*", t)
        if (m and u.proof.claim_kind == "own" and u.proof.claimant == "self"
                and u.record_kind != "past_recollection"):
            return _frag("life_condition_question",
                f"작성자는 ‘{m.group('condition')}’라는 조건을 가정하고 어떤 상태가 되는지 묻는다.",
                "reason", (u,), ((u,m),), ("실제 인물·신체 상태·가능성을 확정하지 않음",))
        m = re.fullmatch(r"(?:와\s*)?(?P<relative>부모님|어머니|아버지|엄마|아빠|이모|삼촌)\s*(?:이번에\s*)?(?P<event>.+?)\s*(?:겪었다네|겪었다함|겪었다고\s*함)[.!ㅋ ]*", t)
        if m:
            return _frag("relative_reported_event",
                f"본문에는 ‘{m.group('relative')}’이 ‘{m.group('event')}’을 겪었다는 전언이 있다.",
                "reason", (u,), ((u,m),), ("실제 사건·전달 경로·가족 동일성은 미확인",))
    return None


def platform_intent_fragment(units):
    for u in units:
        if not (_everyday_author(u) and u.current_own):
            continue
        t = _text(u)
        m = re.fullmatch(r"(?:나도\s*)?해지\s*(?:해야겠다|하겠어|할래)\s*(?P<surface>.+?)\s*완결\s*나면\s*(?:돌아옴|돌아올게)[.! ]*", t)
        if m:
            return _frag("cancel_and_conditional_return",
                f"작성자는 해지할 의사를 밝히고 ‘{m.group('surface')}’의 완결을 복귀 조건으로 든다.",
                "reason", (u,), ((u,m),), ("해지 완료·현재 완결·작품 공식 식별은 미확인",))
        m = re.fullmatch(r"(?P<surface>.+?)\s*연재\s*바라지도\s*않(?:음|는다)[.! ]*", t)
        if m:
            for b in units:
                if not (_everyday_pair(u,b) and b.current_own):
                    continue
                mb = re.fullmatch(r"(?:그냥\s*)?(?P<format>일기|근황)나\s*써서\s*올리면\s*좋겠다[.! ]*", _text(b))
                if mb:
                    return _frag("serialisation_wish_limit",
                        f"작성자는 ‘{m.group('surface')}’의 연재까지 바라지는 않으며 ‘{mb.group('format')}’라도 올라오기를 바란다.",
                        "reason", (u,b), ((u,m),(b,mb)), ("작성·연재·복귀 사실이나 작가 동일성은 미확인",))
        m = re.fullmatch(r"(?P<subject>.+?)\s*(?P<rank>[0-9]+)위\s*(?:먹었네|됐네|했네)[.!ㅋ ]*", t)
        if m and re.search(r"(?:노피아|노벨피아|문피아|시리즈|카카페|리디)", m.group('subject')):
            return _frag("platform_rank_remark",
                f"작성자는 ‘{m.group('subject')}’라는 맥락에서 ‘{m.group('rank')}위’가 되었다고 말한다.",
                "reason", (u,), ((u,m),), ("현재 순위·플랫폼 범위·대상 공식 식별은 미확인",))
    return None


def name_misreading_fragment(units):
    for a in units:
        if not (_everyday_author(a) and a.current_own):
            continue
        ma = re.fullmatch(r"(?P<context>.+?)\s*작가\s*이름인줄\s*알았더니[.! ]*", _text(a))
        if not ma:
            continue
        for b in units:
            if not (_everyday_pair(a,b) and b.current_own):
                continue
            mb = re.fullmatch(r"(?P<role>파딱|완장|관리자)\s*고로시였(?:누|네|음)[.! ]*", _text(b))
            if mb:
                return _frag("name_interpretation_revision",
                    f"작성자는 ‘{ma.group('context')}’를 작가 이름으로 이해했다가 ‘{mb.group('role')} 고로시’에 관한 내용으로 다시 이해한다.",
                    "reason", (a,b), ((a,ma),(b,mb)),
                    ("표시명·실명·직책·게시물 당사자의 동일성을 인증하지 않음",))
    return None


def comment_reading_effect_fragment(units):
    for a in units:
        if not (_everyday_author(a) and a.current_own):
            continue
        ma = re.fullmatch(r"(?P<request>.+?)\s*(?:적어달랬는데|적어달랫는대)\s*(?:걔네가|재네가)\s*(?:저렇게|저러케)\s*달아서[.! ]*", _text(a))
        if not ma:
            continue
        for b in units:
            if not (_everyday_pair(a,b) and b.current_own):
                continue
            mb = re.fullmatch(r"(?:지금|지굼)\s*초반부\s*(?:보는중인데|보는중인대)\s*(?:계속|게속)\s*(?P<feeling>.+?)하게\s*느껴(?:지잖아|지잔아)[.!… ]*", _text(b))
            if mb:
                return _frag("self_reported_comment_reading_effect",
                    f"작성자는 ‘{ma.group('request')}’라는 요청에 달린 댓글과 연결해 초반부가 ‘{mb.group('feeling')}’하게 느껴진다고 말한다.",
                    "reason", (a,b), ((a,ma),(b,mb)),
                    ("댓글 원문·작성자·실제 인과는 확인하지 않음",),
                    primary_subject=f"‘{ma.group('request')}’에 달린 댓글과 연결된 초반부의 ‘{mb.group('feeling')}’ 독서 반응.",
                    primary_role="relation")
    return None


def everyday_purpose_fragments(units):
    units = tuple(units)
    result = []
    for family in (meal_constraint_fragment, life_assumption_fragment,
                   platform_intent_fragment, name_misreading_fragment, comment_reading_effect_fragment):
        fragment = family(units)
        if fragment is not None:
            result.append(fragment)
    # 식사 대안과 섭취 제한은 같은 글에서도 서로 다른 발화다.
    for unit in units:
        fragment = meal_constraint_fragment((unit,))
        if fragment is not None and fragment.rule == 'self_reported_food_constraint':
            result.append(fragment)
    return tuple(result)
