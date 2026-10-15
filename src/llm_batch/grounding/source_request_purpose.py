"""현재 추천 요청의 목적을 비교·제외·허용·독서·감정 맥락과 분리한다.

exact/emit은 기존 native grammar helper, current는 기존 현재 요청 검사다.
조건 목록 전체가 구체 소재라는 가정이나 _QUESTION 필터를 사용하지 않는다.
"""
from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class RequestPlan:
    primary: str = ""
    fragments: tuple = ()
    roles: tuple = ()
    unresolved: tuple = ()
    supported: bool = False
    counts_as_core: bool = False
    publication_authority: bool = False
    units: tuple = field(default=(), compare=False, repr=False)


_END = r"[.!?？~…ㅋㅠㅜ ]*$"
_APP = re.compile(r"\s*-\s*dc\s*(?:official\s*)?App\s*$", re.I)
_REQUEST = re.compile(r"(?P<wanted>.*?)\s*추천\s*(?:좀|점|해\s*(?:줘|조|주)|부탁(?:해)?|요청(?:함)?|바람|pl[sz])" + _END, re.I)
_EXISTS = re.compile(r"(?P<wanted>.+?)(?:소설|작품|글|웹소설)\s*(?:있냐|없냐|있나|없나)" + _END)
_DESIRE = re.compile(r"(?P<wanted>.+?)\s*(?:보고\s*싶(?:다|어|음)|읽고\s*싶(?:다|어|음)|원함|찾고\s*있음|땡김)" + _END)
_REPORT = re.compile(r"(?:라고|다고)\s*(?:함|한다|들었)|라는데|다는데|다던데|다더라")
_NONCURRENT = re.compile(r"(?:쓸|할|물어볼)\s*(?:계획|예정)|(?:요청|부탁).{0,8}(?:철회|취소)|(?:했다|한)면")
_CONDITION = re.compile(r"으면|다면|라면|한다고\s*치면")
_QUESTION_END = re.compile(r"(?:않나요|인가요|나요|냐|니|까|는가|은가)" + _END)
_FINITE = re.compile(r"(?:한다|했음|봤음|읽었음|임|네요|하네|이다|구나|같음|좋다|좋아|싶다|싶어|있음|없음|거부해|아니었음)" + _END)
_QUANTITY = re.compile(r"\d+\s*(?:화|회|권|편)\s*(?:이상|이하|넘|미만|정도)")
_ALLOW = re.compile(r"(?P<range>.+?)(?:이라도|라도|여도|이어도|도)\s*(?:좋아|좋다|괜찮(?:다|음)?|상관\s*없(?:음|다))" + _END)
_BARE_MEDIUM = re.compile(r"(?:웹)?소설|작품|글")


def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _view(u):
    return _APP.sub("", u.text).strip()


def _eligible(u, exact):
    return bool(exact(u) and u.role == "author" and u.current_own
                and u.proof.claim_kind == "own" and u.proof.claimant == "self"
                and u.proof.final_support is True)


def _role_span(text, surface, predicate):
    if not surface or text.count(surface) != 1:
        return None
    return re.search(r"(?<![0-9A-Za-z가-힣])" + re.escape(surface)
                     + r"(?:은|는|이|가|도)?\s*(?:" + predicate + r")", text)


def _roles(u, projection):
    t = _view(u)
    result = []
    for surface, role, basis in _get(projection, "work_roles", ()):
        if role == "reference":
            m = _role_span(t, surface, r"(?:와\s*)?(?:그나마\s*)?(?:비슷한\s*(?:느낌|누낌)|같은\s*(?:느낌|거|것)|처럼)")
        elif role == "excluded" and not (_CONDITION.search(t) or _QUESTION_END.search(t) or "?" in t or "？" in t):
            m = _role_span(t, surface, r"(?:이미\s*)?(?:읽었|봤|보았)|(?:제외|빼\s*(?:줘|주|달라))")
        else:
            continue
        if m:
            result.append((role, surface, m))
    return tuple(result)


def _nominal_condition(text):
    # 내용어의 존재와 명사구/분량 구조를 요구한다. 감정 기호·완결 문장은 조건이 아니다.
    return bool(re.search(r"[가-힣]{2,}|[A-Za-z]{2,}", text)
                and not _QUESTION_END.search(text) and not _FINITE.search(text)
                and not any(x in text for x in ("?", "？"))
                and (len(text.split()) >= 2 or _QUANTITY.search(text)))


def reduce_request_roles(units, projection, *, exact, emit, current):
    """같은 native 요청을 한 번 환원한다. 역할별 fragment와 primary를 같이 반환."""
    units = tuple(units)
    if _get(projection, "speech_act") != "recommendation_request":
        return RequestPlan(unresolved=("U: 현재 추천 요청 native gate 미충족",))
    own = tuple(u for u in units if _eligible(u, exact))
    requests = tuple(u for u in own if current(_view(u)))
    if not requests:
        return RequestPlan(unresolved=("U: exact 현재 요청 원문 없음",))
    fragments, purpose, references, role_records, unknown = [], [], [], [], []

    def add(role, u, value, match=None, destination="note"):
        role_records.append((role, value, u.proof.raw_path, u.proof.raw_span))
        if role == "wanted":
            purpose.append((value, u, match))
        elif role == "reference":
            references.append((value, u, match))
        elif role == "excluded":
            fragments.append(emit("request_excluded_role", f"{value}는 추천에서 제외하려는 원문 대상이다. 이미 읽음·명시적 제외의 근거와 완독 범위는 따로 유지한다.", destination, (u,), ((u, match),) if match else ()))
        elif role == "allowance":
            fragments.append(emit("request_allowance_role", f"{value}도 요청의 허용 범위에 포함한다. 원하는 소재나 읽고 호평한 작품으로 바꾸지 않는다.", destination, (u,), ((u, match),) if match else ()))

    for u in own:
        t = _view(u)
        if _REPORT.search(t) or _NONCURRENT.search(t) or u.record_kind == "past_recollection":
            role_records.append(("noncurrent_or_reported", t, u.proof.raw_path, u.proof.raw_span))
            continue
        roles = _roles(u, projection)
        if roles:
            for role, surface, m in roles:
                add(role, u, surface, m)
            # 대상 역할 문장의 전체를 소재로 바꾸지 않는다. 복합 대상은 기존 gate에 남긴다.
            continue
        allowance = _ALLOW.fullmatch(t)
        if allowance:
            add("allowance", u, allowance.group("range").strip(), allowance)
            continue
        if _QUESTION_END.search(t) and u not in requests:
            role_records.append(("evaluation_or_affective_question", t, u.proof.raw_path, u.proof.raw_span))
            continue
        desired = _DESIRE.fullmatch(t)
        if desired and not re.search(r"(?:안|못)\s*(?:보고|읽고)|(?:보고|읽고)\s*싶지", t):
            add("wanted", u, desired.group("wanted").strip(), desired)
            continue
        request = _REQUEST.fullmatch(t) if u in requests else None
        exists = _EXISTS.fullmatch(t) if u in requests else None
        wanted = request.group("wanted").strip() if request else exists.group("wanted").strip() if exists else ""
        if wanted and not _BARE_MEDIUM.fullmatch(wanted):
            # 요청 앞의 독립 명령 절은 조건이 아니다. 접속 명령 꼬리 뒤 현재 목적만 쓴다.
            wanted = re.split(r"(?:하지\s*말고|멈추고|그만하고|접고)\s*", wanted)[-1].strip()
            if wanted and not _BARE_MEDIUM.fullmatch(wanted):
                add("wanted", u, wanted, request or exists)
                continue
        if request or exists:
            # 소재가 없는 매체 일반 요청은 다른 줄의 구체 조건을 기다린다.
            continue
        # projection은 조건과 맥락을 함께 담는다. 무술어 명사구/분량만 보충 조건으로 인정.
        for condition in _get(projection, "request_conditions", ()):
            if condition == t and _nominal_condition(condition):
                add("wanted", u, condition)
                break

    values = tuple(dict.fromkeys(x[0] for x in purpose))
    if values:
        content = "·".join(values)
        primary = f"「{content}」 조건을 충족하는 작품 추천 요청."
        evidence = tuple(dict((id(u), u) for _, u, _ in purpose).values()) + requests
        matches = tuple((u, m) for _, u, m in purpose if m is not None)
        fragments.insert(0, emit("request_purpose_and_content", f"「{content}」 조건을 충족하는 작품을 찾는다.", "reason", evidence, matches))
    elif references:
        content = "·".join(dict.fromkeys(x[0] for x in references))
        primary = f"{content}와 비슷한 느낌의 작품 추천 요청."
        evidence = tuple(x[1] for x in references) + requests
        fragments.insert(0, emit("request_reference_only_purpose", f"{content}를 느낌의 비교 기준으로 삼아 비슷한 작품을 찾는다. 비교 기준 자체를 새 추천 후보나 공식 제목으로 확정하지 않는다.", "reason", evidence,
                                 tuple((u, m) for _, u, m in references)))
    else:
        return RequestPlan(fragments=tuple(fragments), roles=tuple(role_records),
                           unresolved=("U: 현재 요청은 있으나 구체 목적·조건의 exact span을 환원하지 못함",), units=units)
    for value, u, m in references:
        fragments.append(emit("request_reference_separate", f"{value}는 찾는 작품의 비교 기준이다.", "note", (u,), ((u, m),)))
    return RequestPlan(primary, tuple(fragments), tuple(role_records), tuple(unknown), True, units=units)
