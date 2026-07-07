# Loop544 current full375 after Loop543 projection P0 blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `136`

## 입력

- triage: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop544_current_full375_after_loop543_projection_collateral_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop543_title_mismatch_publish_contract_projection_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `83`
- `unsafe_promotion_from_hold`: `28`
- `wrong_work_title_flip`: `25`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop544 current full375 after Loop543 projection P0 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11660232` `resolved_to_different_title` post=`괴담텔 이번 전개는 괴담동이 살짝 생각나네` options: C1=괴담 동아리, C2=괴담 호텔 탈출기
- `11660241` `resolved_to_different_title` post=`난 이티알은 현실파트가 너무 불호라 하차했는데` options: C1=[ 이티알 ] 이 세계 TRPG 마스터, C2=이세계 TRPG 게임마스터
- `11660262` `resolved_to_different_title` post=`머여 로파민 완결났네` options: C1=그렇게, 그 괴물과 두 번 결혼했다, C2=로판에 도파민을 풀었다
- `11663514` `resolved_to_different_title` post=`슬라임의 올바른 사용법` options: C1=마탄 속의 제국, C2=올바른 슬라임 사용법
- `11663554` `resolved_to_different_title` post=`TS) 주서연 영화개봉 했는데 1엄복동도 못되면` options: C1=전 버튜버가 하고 싶은데요, C2=주서연 ( 전 버튜버가 하고 싶은데요 )
- `11665099` `resolved_to_different_title` post=`옥천마 출정 ㅇㅈㄹ하는 부분부터 대가리 봉합됐음` options: C1=옥천마 출정, C2=옥탑방의 천재 마물 소환사
- `11666700` `resolved_to_different_title` post=`내고향무림 최신화 댓글창에도 벌레새끼가 있네` options: C1=내 고향엔 무림인이 산다, C2=하남자의 탑 공략법
- `11669907` `resolved_to_different_title` post=`이거 중간에 뱉길 잘했네` options: C1=마법 좋아좋아좋아, C2=약스포) 마법 좋아좋아좋아

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
- `11660273` `resolved_to_null` post=`장빙이들 그리즐리 주면 키울거임?` options: C1=마도서를 줍다 마법사가 되다
- `11661856` `resolved_to_null` post=`오늘에 맘마는~~~` options: C1=너랑은 절! 대! 안 사Kill거니까!
- `11661863` `resolved_to_null` post=`두개 써서 동시에 올리나보네` options: C1=저주받은 영애가 되었습니다
- `11663511` `resolved_to_null` post=`부캐황태자99화) 몸은 검으로 되어있다` options: C1=부캐 키우는 황태자님
- `11663535` `resolved_to_null` post=`퇴마록에 온갖 능력 다나오네 생각해보니` options: C1=퇴마록
- `11663557` `resolved_to_null` post=`퇴마록 생각해보니 올해 예능프로그램으로 나오지 않나` options: C1=퇴마록
- `11665110` `resolved_to_null` post=`사이키델리아 읽었던 사람 있냐?` options: C1=낭만적인 초능력을 위하여

## Gate 해석

이 산출물은 Loop544 current full375 after Loop543 projection P0를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
