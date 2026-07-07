# Collateral 73 regression triage

- source compare: `docs/devs/loop598_remaining4_native_hold_full375_collateral_compare.json`
- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- changed rows: `152`
- regression rows: `73`

## Regression buckets

- `safe_loss_resolved_to_null`: `31`
- `unsafe_promotion_from_hold`: `21`
- `wrong_work_title_flip`: `21`

## Priority

- `P0`: `73`

## 대표 샘플

### safe_loss_resolved_to_null
- `11660254` `resolved_to_null` `푸푸푸 랜드의 두가지 일상` -> `None` (safe_resolved -> promotion_blocked)
- `11661863` `resolved_to_null` `저주받은 영애가 되었습니다` -> `None` (safe_resolved -> promotion_blocked)
- `11668278` `resolved_to_null` `짜장면` -> `None` (safe_resolved -> promotion_blocked)
- `11668305` `resolved_to_null` `Fate/stay night` -> `None` (safe_resolved -> promotion_blocked)
- `11671512` `resolved_to_null` `삼시세끼, 심아식당` -> `None` (safe_resolved -> promotion_blocked)
- `11671514` `resolved_to_null` `악신에게 총애받는 자` -> `None` (safe_resolved -> promotion_blocked)
- `11681178` `resolved_to_null` `재벌가 차녀의 2회차 걸그룹` -> `None` (safe_resolved -> promotion_blocked)
- `11682749` `resolved_to_null` `주인공인데 주인공이 아님` -> `None` (safe_resolved -> promotion_blocked)
- `11687661` `resolved_to_null` `약혼녀가 소천마였다` -> `None` (safe_resolved -> promotion_blocked)
- `11694035` `resolved_to_null` `시로코의 제멋대로 일상 단편선` -> `None` (safe_resolved -> promotion_blocked)
- `11694041` `resolved_to_null` `격투 소설 엑스트라가 타격 천재임` -> `None` (safe_resolved -> promotion_blocked)
- `11695609` `resolved_to_null` `쳇바퀴의 생쥐 사도가 되었다` -> `None` (safe_resolved -> promotion_blocked)
- `11697239` `resolved_to_null` `조혈모세포 기증 궁금해요` -> `None` (safe_resolved -> promotion_blocked)
- `11697249` `resolved_to_null` `버거피아` -> `None` (safe_resolved -> promotion_blocked)
- `11698859` `resolved_to_null` `귤부인 대롱대롱` -> `None` (safe_resolved -> promotion_blocked)
- `11698865` `resolved_to_null` `나츠키 스바루/작중 행적/5~8장` -> `None` (safe_resolved -> promotion_blocked)
### unsafe_promotion_from_hold
- `11658637` `null_to_resolved` `None` -> `재벌집 막내아들` (promotion_blocked -> safe_resolved)
- `11660238` `null_to_resolved` `None` -> `무림마조` (promotion_blocked -> safe_resolved)
- `11669928` `null_to_resolved` `None` -> `탑의 성좌들이 날 애호한다` (promotion_blocked -> safe_resolved)
- `11671501` `null_to_resolved` `None` -> `판초우의의 마법사` (promotion_blocked -> safe_resolved)
- `11673086` `null_to_resolved` `None` -> `[림월드]변방계에서 회귀자로 살아남기` (promotion_blocked -> safe_resolved)
- `11674703` `null_to_resolved` `None` -> `도굴왕` (promotion_blocked -> safe_resolved)
- `11676317` `null_to_resolved` `None` -> `마도서를 줍다 마법사가 되다` (promotion_blocked -> safe_resolved)
- `11677957` `null_to_resolved` `None` -> `음악 천재가 불륜을 못 숨김` (promotion_blocked -> safe_resolved)
- `11681177` `null_to_resolved` `None` -> `격투 천재 여고생이 되었다` (promotion_blocked -> safe_resolved)
- `11682768` `null_to_resolved` `None` -> `마법소녀ㄴ은 은퇴하고 싶다` (promotion_blocked -> safe_resolved)
- `11687618` `null_to_resolved` `None` -> `아카데미 생존 갤러리` (promotion_blocked -> safe_resolved)
- `11687635` `null_to_resolved` `None` -> `아포칼립스의 던전주가 되었다` (promotion_blocked -> safe_resolved)
- `11694067` `null_to_resolved` `None` -> `괴담에 휘말렸다` (promotion_blocked -> safe_resolved)
- `11695611` `null_to_resolved` `None` -> `여신이 나만 애호함` (promotion_blocked -> safe_resolved)
- `11697231` `null_to_resolved` `None` -> `아카데미 생존 갤러리` (promotion_blocked -> safe_resolved)
- `11705256` `null_to_resolved` `None` -> `하남자의 탑 공략법` (promotion_blocked -> safe_resolved)
### wrong_work_title_flip
- `11660232` `resolved_to_different_title` `괴담 동아리` -> `괴담 호텔 탈출기` (safe_resolved -> safe_resolved)
- `11660262` `resolved_to_different_title` `그렇게, 그 괴물과 두 번 결혼했다` -> `로판에 도파민을 풀었다` (safe_resolved -> safe_resolved)
- `11661856` `resolved_to_different_title` `너랑은 절! 대! 안 사Kill거니까!` -> `너랑은 절! 대! 안 사갈거니까!` (safe_resolved -> safe_resolved)
- `11663554` `resolved_to_different_title` `주서연 ( 전 버튜버가 하고 싶은데요 )` -> `전 버튜버가 하고 싶은데요` (safe_resolved -> safe_resolved)
- `11665099` `resolved_to_different_title` `옥천마 출정` -> `옥탑방의 천재 마물 소환사` (safe_resolved -> safe_resolved)
- `11665110` `resolved_to_different_title` `낭만적인 초능력을 위하여` -> `사이키델리아` (safe_resolved -> safe_resolved)
- `11665124` `resolved_to_different_title` `화산파(화산귀환)` -> `화산귀환` (safe_resolved -> safe_resolved)
- `11666700` `resolved_to_different_title` `하남자의 탑 공략법` -> `내 고향엔 무림인이 산다` (safe_resolved -> safe_resolved)
- `11669929` `resolved_to_different_title` `기계공주` -> `헌터갤러리의 국가권력급 기계공주` (safe_resolved -> safe_resolved)
- `11671500` `resolved_to_different_title` `악당도 살고 싶다` -> `악당은 살고 싶다` (safe_resolved -> safe_resolved)
- `11676314` `resolved_to_different_title` `소설 속 엑스트라` -> `마도서를 줍다 마법사가 되다` (safe_resolved -> safe_resolved)
- `11681152` `resolved_to_different_title` `체육관 챌린지에서 살아남기` -> `[포켓몬] 체육관 챌린지에서 살아남기` (safe_resolved -> safe_resolved)
- `11682791` `resolved_to_different_title` `피아조아 <시간을 달리는 소설가>` -> `시간을 달리는 소설가` (safe_resolved -> safe_resolved)
- `11685994` `resolved_to_different_title` `무한을 이해한 나는 외신의 사제가 되었습니다` -> `교황님 아하세요 마왕 들어 가요` (safe_resolved -> safe_resolved)
- `11694044` `resolved_to_different_title` `판초우의의 마법사` -> `즉사기 들고 무림에 떨어지다` (safe_resolved -> safe_resolved)
- `11703631` `resolved_to_different_title` `나의 악당들` -> `이블 파티 대 헌터` (safe_resolved -> safe_resolved)

## Gate 해석

이 triage는 full375 collateral diff의 남은 작업을 정렬하는 산출물이다. regression row가 남아 있으므로 full collateral approval은 열리지 않는다.

- background full375/bounded run은 완료 감사 전까지 monitoring evidence다.
- P0 bucket은 blind judge 또는 source-native review가 필요하다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
