# Collateral 141 regression triage

- source compare: `docs/devs/loop623_loop620_current_head_projection_collateral_compare.json`
- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- changed rows: `212`
- regression rows: `141`

## Regression buckets

- `new_resolution_promotion`: `1`
- `safe_loss_resolved_to_null`: `85`
- `unsafe_promotion_from_hold`: `25`
- `wrong_work_title_flip`: `30`

## Priority

- `P0`: `140`
- `P1`: `1`

## 대표 샘플

### new_resolution_promotion
- `11682800` `null_to_resolved` `None` -> `갤질하는 천재 의사` (hold_without_candidates -> safe_resolved)
### safe_loss_resolved_to_null
- `11660229` `resolved_to_null` `로판 속 미친 북부대공이 되었다` -> `None` (safe_resolved -> promotion_blocked)
- `11660254` `resolved_to_null` `푸푸푸 랜드의 두가지 일상` -> `None` (safe_resolved -> promotion_blocked)
- `11660257` `resolved_to_null` `암흑가 보스요? 제가요?` -> `None` (safe_resolved -> promotion_blocked)
- `11660258` `resolved_to_null` `괴담 호텔 탈출기` -> `None` (safe_resolved -> promotion_blocked)
- `11660262` `resolved_to_null` `그렇게, 그 괴물과 두 번 결혼했다` -> `None` (safe_resolved -> promotion_blocked)
- `11660264` `resolved_to_null` `빚을 져서라도 세상은 구해야 할 거 아니야` -> `None` (safe_resolved -> promotion_blocked)
- `11660268` `resolved_to_null` `을 위한 세계는 없다` -> `None` (safe_resolved -> promotion_blocked)
- `11660271` `resolved_to_null` `월야의 여인들` -> `None` (safe_resolved -> promotion_blocked)
- `11661863` `resolved_to_null` `저주받은 영애가 되었습니다` -> `None` (safe_resolved -> promotion_blocked)
- `11663535` `resolved_to_null` `퇴마록` -> `None` (safe_resolved -> promotion_blocked)
- `11665121` `resolved_to_null` `후회 안 하는 프로듀서` -> `None` (safe_resolved -> promotion_blocked)
- `11665124` `resolved_to_null` `화산파(화산귀환)` -> `None` (safe_resolved -> promotion_blocked)
### unsafe_promotion_from_hold
- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11668324` `null_to_resolved` `None` -> `니생들이랑 김괴라리 장갤픽 아니였음?` (promotion_blocked -> safe_resolved)
- `11669928` `null_to_resolved` `None` -> `탑의 성좌들이 날 애호한다` (promotion_blocked -> safe_resolved)
- `11671501` `null_to_resolved` `None` -> `판초우의의 마법사` (promotion_blocked -> safe_resolved)
- `11671538` `null_to_resolved` `None` -> `망한 교단의 성기사` (promotion_blocked -> safe_resolved)
- `11673086` `null_to_resolved` `None` -> `[림월드]변방계에서 회귀자로 살아남기` (promotion_blocked -> safe_resolved)
- `11676317` `null_to_resolved` `None` -> `마도서를 줍다 마법사가 되다` (promotion_blocked -> safe_resolved)
- `11681177` `null_to_resolved` `None` -> `격투 천재 여고생이 되었다` (promotion_blocked -> safe_resolved)
- `11682768` `null_to_resolved` `None` -> `마법소녀는 은퇴하고 싶다` (promotion_blocked -> safe_resolved)
- `11684370` `null_to_resolved` `None` -> `목표는 엔딩 요정 - 판타지 웹소설` (promotion_blocked -> safe_resolved)
- `11687618` `null_to_resolved` `None` -> `아카데미 생존 갤러리` (promotion_blocked -> safe_resolved)
- `11687627` `null_to_resolved` `None` -> `변방계에서 회귀자로 살아남기` (promotion_blocked -> safe_resolved)
### wrong_work_title_flip
- `11661856` `resolved_to_different_title` `너랑은 절! 대! 안 사Kill거니까!` -> `다녀왔어` (safe_resolved -> safe_resolved)
- `11661857` `resolved_to_different_title` `아카데미 개망나니 교수가 되었다` -> `두바이의 쫀득한 여초딩 재벌 9세` (safe_resolved -> safe_resolved)
- `11663514` `resolved_to_different_title` `마탄 속의 제국` -> `올바른 슬라임 사용법` (safe_resolved -> safe_resolved)
- `11663521` `resolved_to_different_title` `초전자포] 시스터즈가 되었다` -> `카미조 토우마가 IS세계관에 떨어지는 이야기. 꽤 예전에 썼던 글인데 저쪽에선 읽기 힘들어서 여기에 재업합니다` (safe_resolved -> safe_resolved)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11663557` `resolved_to_different_title` `퇴마록` -> `퇴마록 1` (safe_resolved -> safe_resolved)
- `11665099` `resolved_to_different_title` `옥천마 출정` -> `옥탑방의 천재 마물 소환사` (safe_resolved -> safe_resolved)
- `11665110` `resolved_to_different_title` `낭만적인 초능력을 위하여` -> `사이키델리아` (safe_resolved -> safe_resolved)
- `11666700` `resolved_to_different_title` `하남자의 탑 공략법` -> `내 고향엔 무림인이 산다` (safe_resolved -> safe_resolved)
- `11669907` `resolved_to_different_title` `마법 좋아좋아좋아` -> `약스포) 마법 좋아좋아좋아` (safe_resolved -> safe_resolved)
- `11669929` `resolved_to_different_title` `기계공주` -> `헌터갤러리의 국가권력급 기계공주` (safe_resolved -> safe_resolved)
- `11671514` `resolved_to_different_title` `악신에게 총애받는 자` -> `악신의 총애를 받는 성직자가 되었다` (safe_resolved -> safe_resolved)

## Gate 해석

이 triage는 full375 collateral diff의 남은 작업을 정렬하는 산출물이다. regression row가 남아 있으므로 full collateral approval은 열리지 않는다.

- background full375/bounded run은 완료 감사 전까지 monitoring evidence다.
- P0 bucket은 blind judge 또는 source-native review가 필요하다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
