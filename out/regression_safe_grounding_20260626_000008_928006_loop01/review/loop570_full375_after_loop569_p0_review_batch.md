# Loop570 full375 after Loop569 P0 collateral blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `117`

## 입력

- triage: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop569_source_native_safe_loss_collateral_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop569_source_native_safe_loss_projection_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `56`
- `unsafe_promotion_from_hold`: `28`
- `wrong_work_title_flip`: `33`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop570 full375 after Loop569 P0 collateral 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11660232` `resolved_to_different_title` post=`괴담텔 이번 전개는 괴담동이 살짝 생각나네` options: C1=괴담 동아리, C2=괴담 호텔 탈출기
- `11660237` `resolved_to_different_title` post=`테라포밍 볼만함?` options: C1=이세계 테라포밍 With편의점, C2=테라포밍
- `11660241` `resolved_to_different_title` post=`난 이티알은 현실파트가 너무 불호라 하차했는데` options: C1=[ 이티알 ] 이 세계 TRPG 마스터, C2=이세계 TRPG 게임마스터
- `11660262` `resolved_to_different_title` post=`머여 로파민 완결났네` options: C1=그렇게, 그 괴물과 두 번 결혼했다, C2=로판에 도파민을 풀었다
- `11660273` `resolved_to_different_title` post=`장빙이들 그리즐리 주면 키울거임?` options: C1=그리즐리 그랑, C2=마도서를 줍다 마법사가 되다
- `11663514` `resolved_to_different_title` post=`슬라임의 올바른 사용법` options: C1=마탄 속의 제국, C2=올바른 슬라임 사용법
- `11663521` `resolved_to_different_title` post=`TS) 시스터즈 퍼스트 정신머리 고치려면` options: C1=어떤 마술의 금서목록, C2=초전자포] 시스터즈가 되었다
- `11663540` `resolved_to_different_title` post=`TS) 주서연 전차랑 줄다리기 하면 이길까?` options: C1=방구석 여신이 되었다, C2=전 버튜버가 하고 싶은데요

### unsafe_promotion_from_hold
- `11657047` `null_to_resolved` post=`베지테리언이 정육점 사장이 됐다 이런 소설 보고잡네` options: C1=사이버펑크 베지테리언 매드니스
- `11658621` `null_to_resolved` post=`아니 변명이 아니라 진짜였다고` options: C1=무능한게 아니라 전설이였다고?
- `11658637` `null_to_resolved` post=`재막아)영기는 진짜 답이 없구나` options: C1=재벌집 막내아들
- `11660238` `null_to_resolved` post=`오늘 림조 한서진 청월한테 말하는 게 개웃기네` options: C1=무림마조
- `11668324` `null_to_resolved` post=`니생들이랑 김괴라리 장갤픽 아니였음?` options: C1=니들 생각 다 들린다
- `11669928` `null_to_resolved` post=`탑성좌애호 노벨피아 이거 연중했었네` options: C1=탑의 성좌들이 날 애호한다
- `11671501` `null_to_resolved` post=`판초법사 막 게이트열린 시점아님?` options: C1=판초우의의 마법사
- `11671538` `null_to_resolved` post=`여우비의 신 마커스 많이 아끼나보네` options: C1=망한 교단의 성기사

### safe_loss_resolved_to_null
- `11660254` `resolved_to_null` post=`노피아 애니메이션은 뭐임?` options: C1=푸푸푸 랜드의 두가지 일상
- `11661856` `resolved_to_null` post=`오늘에 맘마는~~~` options: C1=너랑은 절! 대! 안 사Kill거니까!
- `11661857` `resolved_to_null` post=`로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다` options: C1=아카데미 개망나니 교수가 되었다
- `11661863` `resolved_to_null` post=`두개 써서 동시에 올리나보네` options: C1=저주받은 영애가 되었습니다
- `11665110` `resolved_to_null` post=`사이키델리아 읽었던 사람 있냐?` options: C1=낭만적인 초능력을 위하여
- `11665124` `resolved_to_null` post=`난 시리즈 댓글은 정말 많이 달았었음` options: C1=화산파(화산귀환)
- `11666725` `resolved_to_null` post=`아 이거 재밌어 보이는데 남주가 매력적임` options: C1=학대받던 11살 고마가 각성한 이유
- `11666741` `resolved_to_null` post=`별품소 웹툰 가끔씩 보는데` options: C1=별을 품은 소드마스터

## Gate 해석

이 산출물은 Loop570 full375 after Loop569 P0 collateral를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
