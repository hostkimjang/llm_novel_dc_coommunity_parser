# Loop497 current Loop496 full375 P0 collateral blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `137`

## 입력

- triage: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop496_full375_current_head_collateral_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop496_full375_current_head_4fd250f7_search_nonlight_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `84`
- `unsafe_promotion_from_hold`: `28`
- `wrong_work_title_flip`: `25`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop497 current Loop496 full375 P0 collateral 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11660262` `resolved_to_different_title` post=`머여 로파민 완결났네` options: C1=그렇게, 그 괴물과 두 번 결혼했다, C2=로판에 도파민을 풀었다
- `11661863` `resolved_to_different_title` post=`두개 써서 동시에 올리나보네` options: C1=용의 신부로 바쳐지고 말았다, C2=저주받은 영애가 되었습니다
- `11663514` `resolved_to_different_title` post=`슬라임의 올바른 사용법` options: C1=마탄 속의 제국, C2=올바른 슬라임 사용법
- `11663554` `resolved_to_different_title` post=`TS) 주서연 영화개봉 했는데 1엄복동도 못되면` options: C1=전 버튜버가 하고 싶은데요, C2=주서연 ( 전 버튜버가 하고 싶은데요 )
- `11665099` `resolved_to_different_title` post=`옥천마 출정 ㅇㅈㄹ하는 부분부터 대가리 봉합됐음` options: C1=옥천마 출정, C2=옥탑방의 천재 마물 소환사
- `11666700` `resolved_to_different_title` post=`내고향무림 최신화 댓글창에도 벌레새끼가 있네` options: C1=내 고향엔 무림인이 산다, C2=하남자의 탑 공략법
- `11669929` `resolved_to_different_title` post=`기계공주 재밌네` options: C1=기계공주, C2=헌터갤러리의 국가권력급 기계공주
- `11671500` `resolved_to_different_title` post=`말투 바뀌는 거 악살싶에서는 호평받았었는데` options: C1=악당도 살고 싶다, C2=악당은 살고 싶다

### unsafe_promotion_from_hold
- `11657047` `null_to_resolved` post=`베지테리언이 정육점 사장이 됐다 이런 소설 보고잡네` options: C1=사이버펑크 베지테리언 매드니스
- `11658621` `null_to_resolved` post=`아니 변명이 아니라 진짜였다고` options: C1=무능한게 아니라 전설이였다고?
- `11658637` `null_to_resolved` post=`재막아)영기는 진짜 답이 없구나` options: C1=재벌집 막내아들
- `11668324` `null_to_resolved` post=`니생들이랑 김괴라리 장갤픽 아니였음?` options: C1=니들 생각 다 들린다
- `11669911` `null_to_resolved` post=`S급 헌터 결혼 보는 사람?` options: C1=S급 헌터도 결혼이 하고 싶다
- `11669928` `null_to_resolved` post=`탑성좌애호 노벨피아 이거 연중했었네` options: C1=탑의 성좌들이 날 애호한다
- `11671501` `null_to_resolved` post=`판초법사 막 게이트열린 시점아님?` options: C1=판초우의의 마법사
- `11671538` `null_to_resolved` post=`여우비의 신 마커스 많이 아끼나보네` options: C1=망한 교단의 성기사

### safe_loss_resolved_to_null
- `11660254` `resolved_to_null` post=`노피아 애니메이션은 뭐임?` options: C1=푸푸푸 랜드의 두가지 일상
- `11660271` `resolved_to_null` post=`아이돌 히로인 나오는 야설 어디 없나` options: C1=월야의 여인들
- `11660273` `resolved_to_null` post=`장빙이들 그리즐리 주면 키울거임?` options: C1=마도서를 줍다 마법사가 되다
- `11660277` `resolved_to_null` post=`완결난 아카메디 지금당장봐` options: C1=아카메디 아카데미 본 사람?
- `11661856` `resolved_to_null` post=`오늘에 맘마는~~~` options: C1=너랑은 절! 대! 안 사Kill거니까!
- `11663521` `resolved_to_null` post=`TS) 시스터즈 퍼스트 정신머리 고치려면` options: C1=초전자포] 시스터즈가 되었다
- `11663535` `resolved_to_null` post=`퇴마록에 온갖 능력 다나오네 생각해보니` options: C1=퇴마록
- `11663540` `resolved_to_null` post=`TS) 주서연 전차랑 줄다리기 하면 이길까?` options: C1=방구석 여신이 되었다

## Gate 해석

이 산출물은 Loop497 current Loop496 full375 P0 collateral를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
