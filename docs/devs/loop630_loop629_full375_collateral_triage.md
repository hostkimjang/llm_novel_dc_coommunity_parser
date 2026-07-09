# Collateral 137 regression triage

- source compare: `docs/devs/loop629_full375_after_loop628_collateral_compare.json`
- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- changed rows: `206`
- regression rows: `137`

## Regression buckets

- `safe_loss_resolved_to_null`: `79`
- `unsafe_promotion_from_hold`: `26`
- `wrong_work_title_flip`: `32`

## Priority

- `P0`: `137`

## 대표 샘플

### safe_loss_resolved_to_null
- `11660241` `resolved_to_null` `이세계 TRPG 게임마스터` -> `None` (safe_resolved -> promotion_blocked)
- `11660254` `resolved_to_null` `푸푸푸 랜드의 두가지 일상` -> `None` (safe_resolved -> promotion_blocked)
- `11660268` `resolved_to_null` `을 위한 세계는 없다` -> `None` (safe_resolved -> promotion_blocked)
- `11660271` `resolved_to_null` `월야의 여인들` -> `None` (safe_resolved -> promotion_blocked)
- `11660273` `resolved_to_null` `마도서를 줍다 마법사가 되다` -> `None` (safe_resolved -> promotion_blocked)
- `11661856` `resolved_to_null` `너랑은 절! 대! 안 사Kill거니까!` -> `None` (safe_resolved -> promotion_blocked)
- `11663511` `resolved_to_null` `부캐 키우는 황태자님` -> `None` (safe_resolved -> promotion_blocked)
- `11663521` `resolved_to_null` `초전자포] 시스터즈가 되었다` -> `None` (safe_resolved -> promotion_blocked)
- `11663557` `resolved_to_null` `퇴마록` -> `None` (safe_resolved -> promotion_blocked)
- `11665121` `resolved_to_null` `후회 안 하는 프로듀서` -> `None` (safe_resolved -> promotion_blocked)
- `11665124` `resolved_to_null` `화산파(화산귀환)` -> `None` (safe_resolved -> promotion_blocked)
- `11666725` `resolved_to_null` `학대받던 11살 고마가 각성한 이유` -> `None` (safe_resolved -> promotion_blocked)
### unsafe_promotion_from_hold
- `11657038` `null_to_resolved` `None` -> `레드 데스티니 [D]` (promotion_blocked -> safe_resolved)
- `11657044` `null_to_resolved` `None` -> `웨딩드레스` (promotion_blocked -> safe_resolved)
- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11660238` `null_to_resolved` `None` -> `무림마조` (promotion_blocked -> safe_resolved)
- `11669928` `null_to_resolved` `None` -> `탑의 성좌들이 날 애호한다` (promotion_blocked -> safe_resolved)
- `11671501` `null_to_resolved` `None` -> `판초우의의 마법사` (promotion_blocked -> safe_resolved)
- `11671538` `null_to_resolved` `None` -> `망한 교단의 성기사` (promotion_blocked -> safe_resolved)
- `11674712` `null_to_resolved` `None` -> `이 무림의 미친년은 나야` (promotion_blocked -> safe_resolved)
- `11676317` `null_to_resolved` `None` -> `마도서를 줍다 마법사가 되다` (promotion_blocked -> safe_resolved)
- `11681177` `null_to_resolved` `None` -> `격투 천재 여고생이 되었다` (promotion_blocked -> safe_resolved)
- `11681180` `null_to_resolved` `None` -> `아카데미 패드립 면역` (promotion_blocked -> safe_resolved)
- `11682768` `null_to_resolved` `None` -> `마법소녀ㄴ 은 은퇴하고 싶다` (promotion_blocked -> safe_resolved)
### wrong_work_title_flip
- `11660257` `resolved_to_different_title` `암흑가 보스요? 제가요?` -> `고수위.국제마약카르텔. 암흑가 의 보스 들 새 창 열림` (safe_resolved -> safe_resolved)
- `11660262` `resolved_to_different_title` `그렇게, 그 괴물과 두 번 결혼했다` -> `로판에 도파민을 풀었다` (safe_resolved -> safe_resolved)
- `11663514` `resolved_to_different_title` `마탄 속의 제국` -> `올바른 슬라임 사용법` (safe_resolved -> safe_resolved)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11665099` `resolved_to_different_title` `옥천마 출정` -> `옥탑방의 천재 마물 소환사` (safe_resolved -> safe_resolved)
- `11665110` `resolved_to_different_title` `낭만적인 초능력을 위하여` -> `사이키델리아` (safe_resolved -> safe_resolved)
- `11666700` `resolved_to_different_title` `하남자의 탑 공략법` -> `내 고향엔 무림인이 산다` (safe_resolved -> safe_resolved)
- `11666713` `resolved_to_different_title` `21세기 무림세가` -> `21세기 현대무림 레거시` (safe_resolved -> safe_resolved)
- `11669907` `resolved_to_different_title` `마법 좋아좋아좋아` -> `약스포) 마법 좋아좋아좋아` (safe_resolved -> safe_resolved)
- `11669929` `resolved_to_different_title` `기계공주` -> `헌터갤러리의 국가권력급 기계공주` (safe_resolved -> safe_resolved)
- `11669933` `resolved_to_different_title` `회귀수선전` -> `회귀수선전(回歸修仙傳)` (safe_resolved -> safe_resolved)
- `11671500` `resolved_to_different_title` `악당도 살고 싶다` -> `악당은 살고 싶다` (safe_resolved -> safe_resolved)

## Gate 해석

이 triage는 full375 collateral diff의 남은 작업을 정렬하는 산출물이다. regression row가 남아 있으므로 full collateral approval은 열리지 않는다.

- background full375/bounded run은 완료 감사 전까지 monitoring evidence다.
- P0 bucket은 blind judge 또는 source-native review가 필요하다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
