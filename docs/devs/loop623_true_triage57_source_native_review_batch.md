# Loop623 current-head true triage 57 blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `57`
- excluded post_id rows: `0`
- excluded P0 candidate rows: `0`
- include all priorities: `true`

## 입력

- triage: `docs/devs/loop623_loop620_current_head_projection_collateral_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop621_loop620_current_head_publication_sync_projection_result.json`

## Bucket

- `new_resolution_promotion`: `1`
- `safe_loss_resolved_to_null`: `29`
- `unsafe_promotion_from_hold`: `8`
- `wrong_work_title_flip`: `19`

## Priority

- `P0`: `56`
- `P1`: `1`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop623 current-head true triage 57 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11661857` `resolved_to_different_title` post=`로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다` options: C1=두바이의 쫀득한 여초딩 재벌 9세, C2=아카데미 개망나니 교수가 되었다
- `11663514` `resolved_to_different_title` post=`슬라임의 올바른 사용법` options: C1=마탄 속의 제국, C2=올바른 슬라임 사용법
- `11663521` `resolved_to_different_title` post=`TS) 시스터즈 퍼스트 정신머리 고치려면` options: C1=초전자포] 시스터즈가 되었다, C2=카미조 토우마가 IS세계관에 떨어지는 이야기. 꽤 예전에 썼던 글인데 저쪽에선 읽기 힘들어서 여기에 재업합니다
- `11663554` `resolved_to_different_title` post=`TS) 주서연 영화개봉 했는데 1엄복동도 못되면` options: C1=전 버튜버가 하고 싶은데요, C2=주서연 ( 전 버튜버가 하고 싶은데요 )
- `11663557` `resolved_to_different_title` post=`퇴마록 생각해보니 올해 예능프로그램으로 나오지 않나` options: C1=퇴마록, C2=퇴마록 1
- `11665099` `resolved_to_different_title` post=`옥천마 출정 ㅇㅈㄹ하는 부분부터 대가리 봉합됐음` options: C1=옥천마 출정, C2=옥탑방의 천재 마물 소환사
- `11665110` `resolved_to_different_title` post=`사이키델리아 읽었던 사람 있냐?` options: C1=낭만적인 초능력을 위하여, C2=사이키델리아
- `11669907` `resolved_to_different_title` post=`이거 중간에 뱉길 잘했네` options: C1=마법 좋아좋아좋아, C2=약스포) 마법 좋아좋아좋아

### unsafe_promotion_from_hold
- `11682768` `null_to_resolved` post=`근데 마법소녀ㄴ 일란성 쌍둥이라는거 뭔소리임` options: C1=마법소녀는 은퇴하고 싶다
- `11684370` `null_to_resolved` post=`왜 단아엔딩인 것이지?` options: C1=목표는 엔딩 요정 - 판타지 웹소설
- `11687618` `null_to_resolved` post=`아생갤 떡밥 나오니까 좀 재밌네` options: C1=아카데미 생존 갤러리
- `11687627` `null_to_resolved` post=`렛따싶 풀네임이 뭐임?` options: C1=변방계에서 회귀자로 살아남기
- `11690855` `null_to_resolved` post=`림버스 저게 의외로 유저수 씹덕겜 3등인가 함` options: C1=[림버스] 혈귀를 미치게 하는 피를 가져버렸다.
- `11697231` `null_to_resolved` post=`아생갤 어렵네` options: C1=아카데미 생존 갤러리
- `11702060` `null_to_resolved` post=`한가인 4문장 어느정도일지 잘 모르겠음` options: C1=괴담 호텔 탈출기
- `11710045` `null_to_resolved` post=`섹스다섹스` options: C1=공주는 언니를 황제로 만든다

### safe_loss_resolved_to_null
- `11660229` `resolved_to_null` post=`로판 속 미친 북부대공이 되었다 하차함` options: C1=로판 속 미친 북부대공이 되었다
- `11660264` `resolved_to_null` post=`빚세구 근데 주인공이 은발에 아이돌 출신이란 게 좀 신경쓰이네` options: C1=빚을 져서라도 세상은 구해야 할 거 아니야
- `11660268` `resolved_to_null` post=`ㅁㅁ세계 초대용사전의 문제점` options: C1=을 위한 세계는 없다
- `11660271` `resolved_to_null` post=`아이돌 히로인 나오는 야설 어디 없나` options: C1=월야의 여인들
- `11661863` `resolved_to_null` post=`두개 써서 동시에 올리나보네` options: C1=저주받은 영애가 되었습니다
- `11663535` `resolved_to_null` post=`퇴마록에 온갖 능력 다나오네 생각해보니` options: C1=퇴마록
- `11666725` `resolved_to_null` post=`아 이거 재밌어 보이는데 남주가 매력적임` options: C1=학대받던 11살 고마가 각성한 이유
- `11666741` `resolved_to_null` post=`별품소 웹툰 가끔씩 보는데` options: C1=별을 품은 소드마스터

### new_resolution_promotion
- `11682800` `null_to_resolved` post=`갤질의사 최태수랑 비교하면 어떰` options: C1=갤질하는 천재 의사

## Gate 해석

이 산출물은 Loop623 current-head true triage 57를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
