# Collateral 139 regression triage

- source compare: `docs/devs/loop609_runtime_full375_after_loop608_collateral_compare.json`
- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- changed rows: `195`
- regression rows: `139`

## Regression buckets

- `safe_loss_resolved_to_null`: `84`
- `unsafe_promotion_from_hold`: `24`
- `wrong_work_title_flip`: `31`

## Priority

- `P0`: `139`

## 대표 샘플

### safe_loss_resolved_to_null
- `11658626` `resolved_to_null` `아카데미 선비의 생활일지` -> `None` (safe_resolved -> promotion_blocked)
- `11660241` `resolved_to_null` `이세계 TRPG 게임마스터` -> `None` (safe_resolved -> promotion_blocked)
- `11660264` `resolved_to_null` `빚을 져서라도 세상은 구해야 할 거 아니야` -> `None` (safe_resolved -> promotion_blocked)
- `11660268` `resolved_to_null` `을 위한 세계는 없다` -> `None` (safe_resolved -> promotion_blocked)
- `11660271` `resolved_to_null` `월야의 여인들` -> `None` (safe_resolved -> promotion_blocked)
- `11660277` `resolved_to_null` `아카메디 아카데미 본 사람?` -> `None` (safe_resolved -> promotion_blocked)
- `11661856` `resolved_to_null` `너랑은 절! 대! 안 사Kill거니까!` -> `None` (safe_resolved -> promotion_blocked)
- `11661863` `resolved_to_null` `저주받은 영애가 되었습니다` -> `None` (safe_resolved -> promotion_blocked)
- `11661881` `resolved_to_null` `여신이 나만 애호함` -> `None` (safe_resolved -> promotion_blocked)
- `11663511` `resolved_to_null` `부캐 키우는 황태자님` -> `None` (safe_resolved -> promotion_blocked)
- `11663521` `resolved_to_null` `초전자포] 시스터즈가 되었다` -> `None` (safe_resolved -> promotion_blocked)
- `11665110` `resolved_to_null` `낭만적인 초능력을 위하여` -> `None` (safe_resolved -> promotion_blocked)
- `11665121` `resolved_to_null` `후회 안 하는 프로듀서` -> `None` (safe_resolved -> promotion_blocked)
- `11665124` `resolved_to_null` `화산파(화산귀환)` -> `None` (safe_resolved -> promotion_blocked)
- `11666699` `resolved_to_null` `여동생이 맛있다` -> `None` (safe_resolved -> promotion_blocked)
- `11666725` `resolved_to_null` `학대받던 11살 고마가 각성한 이유` -> `None` (safe_resolved -> promotion_blocked)
- `11666741` `resolved_to_null` `별을 품은 소드마스터` -> `None` (safe_resolved -> promotion_blocked)
- `11668278` `resolved_to_null` `짜장면` -> `None` (safe_resolved -> promotion_blocked)
- `11668300` `resolved_to_null` `즉사기 들고 게임 속 으로` -> `None` (safe_resolved -> promotion_blocked)
- `11668305` `resolved_to_null` `Fate/stay night` -> `None` (safe_resolved -> promotion_blocked)
### unsafe_promotion_from_hold
- `11657045` `null_to_resolved` `None` -> `금태양과 음침녀` (promotion_blocked -> safe_resolved)
- `11657047` `null_to_resolved` `None` -> `베지테리언 블러드` (promotion_blocked -> safe_resolved)
- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11668324` `null_to_resolved` `None` -> `니들 생각 다 들린다` (promotion_blocked -> safe_resolved)
- `11669928` `null_to_resolved` `None` -> `탑의 성좌들이 날 애호한다` (promotion_blocked -> safe_resolved)
- `11671501` `null_to_resolved` `None` -> `판초우의의 마법사` (promotion_blocked -> safe_resolved)
- `11671538` `null_to_resolved` `None` -> `망한 교단의 성기사` (promotion_blocked -> safe_resolved)
- `11676317` `null_to_resolved` `None` -> `마도서를 줍다 마법사가 되다` (promotion_blocked -> safe_resolved)
- `11677919` `null_to_resolved` `None` -> `내 누나가 아니었음 좋겠어` (promotion_blocked -> safe_resolved)
- `11677957` `null_to_resolved` `None` -> `음악 천재가 불륜을 못 숨김` (promotion_blocked -> safe_resolved)
- `11681177` `null_to_resolved` `None` -> `격투 천재 여고생이 되었다` (promotion_blocked -> safe_resolved)
- `11681180` `null_to_resolved` `None` -> `아카데미 패드립 면역` (promotion_blocked -> safe_resolved)
- `11682768` `null_to_resolved` `None` -> `마법소녀ㄴ은 은퇴하고 싶다` (promotion_blocked -> safe_resolved)
- `11685995` `null_to_resolved` `None` -> `가챠 중독자의 퓨전펑크 생활` (promotion_blocked -> safe_resolved)
- `11687618` `null_to_resolved` `None` -> `아카데미 생존 갤러리` (promotion_blocked -> safe_resolved)
- `11694067` `null_to_resolved` `None` -> `괴담에 휘말렸다` (promotion_blocked -> safe_resolved)
- `11695639` `null_to_resolved` `None` -> `준우승 세 번 했더니 미소녀 됨` (promotion_blocked -> safe_resolved)
- `11697231` `null_to_resolved` `None` -> `아카데미 생존 갤러리` (promotion_blocked -> safe_resolved)
- `11697234` `null_to_resolved` `None` -> `검귀가 환생했더니` (promotion_blocked -> safe_resolved)
- `11702081` `null_to_resolved` `None` -> `게임 속 재해병 이야기` (promotion_blocked -> safe_resolved)
### wrong_work_title_flip
- `11660254` `resolved_to_different_title` `푸푸푸 랜드의 두가지 일상` -> `양판 애니 속으로 들어와 버렸다` (safe_resolved -> safe_resolved)
- `11660257` `resolved_to_different_title` `암흑가 보스요? 제가요?` -> `그룹을 위해 당연한 일을 했을 뿐인데. 정체불명의 암흑가 보스 니 검은 자본이니. 다들 호들갑이 심하다니까` (safe_resolved -> safe_resolved)
- `11660262` `resolved_to_different_title` `그렇게, 그 괴물과 두 번 결혼했다` -> `로판에 도파민을 풀었다` (safe_resolved -> safe_resolved)
- `11660273` `resolved_to_different_title` `마도서를 줍다 마법사가 되다` -> `그리즐리 그랑` (safe_resolved -> safe_resolved)
- `11663514` `resolved_to_different_title` `마탄 속의 제국` -> `올바른 슬라임 사용법` (safe_resolved -> safe_resolved)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11663557` `resolved_to_different_title` `퇴마록` -> `퇴마록 1` (safe_resolved -> safe_resolved)
- `11665099` `resolved_to_different_title` `옥천마 출정` -> `옥탑방의 천재 마물 소환사` (safe_resolved -> safe_resolved)
- `11666700` `resolved_to_different_title` `하남자의 탑 공략법` -> `내 고향엔 무림인이 산다` (safe_resolved -> safe_resolved)
- `11666713` `resolved_to_different_title` `21세기 무림세가` -> `21세기 현대무림 레거시` (safe_resolved -> safe_resolved)
- `11669907` `resolved_to_different_title` `마법 좋아좋아좋아` -> `약스포) 마법 좋아좋아좋아` (safe_resolved -> safe_resolved)
- `11669926` `resolved_to_different_title` `싸울아비 룬` -> `싸울 할 비 문` (safe_resolved -> safe_resolved)
- `11669929` `resolved_to_different_title` `기계공주` -> `헌터갤러리의 국가권력급 기계공주` (safe_resolved -> safe_resolved)
- `11671500` `resolved_to_different_title` `악당도 살고 싶다` -> `악당은 살고 싶다 - 판타지 웹소설` (safe_resolved -> safe_resolved)
- `11671514` `resolved_to_different_title` `악신에게 총애받는 자` -> `악신이 총애하는 모험가` (safe_resolved -> safe_resolved)
- `11673096` `resolved_to_different_title` `삼국지` -> `이문열 삼국지 1` (safe_resolved -> safe_resolved)
- `11676314` `resolved_to_different_title` `소설 속 엑스트라` -> `마도서를 줍다 마법사가 되다` (safe_resolved -> safe_resolved)
- `11677926` `resolved_to_different_title` `재앙급 막내 공자의 회귀` -> `무영자` (safe_resolved -> safe_resolved)
- `11682749` `resolved_to_different_title` `주인공인데 주인공이 아님` -> `묵향 다크레이디` (safe_resolved -> safe_resolved)
- `11682791` `resolved_to_different_title` `피아조아 <시간을 달리는 소설가>` -> `시간을 달리는 소설가` (safe_resolved -> safe_resolved)

## Gate 해석

이 triage는 full375 collateral diff의 남은 작업을 정렬하는 산출물이다. regression row가 남아 있으므로 full collateral approval은 열리지 않는다.

- background full375/bounded run은 완료 감사 전까지 monitoring evidence다.
- P0 bucket은 blind judge 또는 source-native review가 필요하다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
