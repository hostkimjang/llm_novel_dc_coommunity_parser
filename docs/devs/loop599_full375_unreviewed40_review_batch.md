# Loop599 full375 unreviewed40 after residual46 blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `40`
- excluded post_id rows: `46`
- excluded P0 candidate rows: `33`

## 입력

- triage: `docs/devs/loop599_full375_after_residual46_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop598_remaining4_native_hold_projection_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `9`
- `unsafe_promotion_from_hold`: `20`
- `wrong_work_title_flip`: `11`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop599 full375 unreviewed40 after residual46 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11660262` `resolved_to_different_title` post=`머여 로파민 완결났네` options: C1=그렇게, 그 괴물과 두 번 결혼했다, C2=로판에 도파민을 풀었다
- `11665099` `resolved_to_different_title` post=`옥천마 출정 ㅇㅈㄹ하는 부분부터 대가리 봉합됐음` options: C1=옥천마 출정, C2=옥탑방의 천재 마물 소환사
- `11666700` `resolved_to_different_title` post=`내고향무림 최신화 댓글창에도 벌레새끼가 있네` options: C1=내 고향엔 무림인이 산다, C2=하남자의 탑 공략법
- `11669929` `resolved_to_different_title` post=`기계공주 재밌네` options: C1=기계공주, C2=헌터갤러리의 국가권력급 기계공주
- `11671500` `resolved_to_different_title` post=`말투 바뀌는 거 악살싶에서는 호평받았었는데` options: C1=악당도 살고 싶다, C2=악당은 살고 싶다
- `11676314` `resolved_to_different_title` post=`마도줍 완결이 빠를까` options: C1=마도서를 줍다 마법사가 되다, C2=소설 속 엑스트라
- `11681152` `resolved_to_different_title` post=`이거 살아날수 있을까` options: C1=[포켓몬] 체육관 챌린지에서 살아남기, C2=체육관 챌린지에서 살아남기
- `11694044` `resolved_to_different_title` post=`즉사무림 유료화 카운트 들어갔네` options: C1=즉사기 들고 무림에 떨어지다, C2=판초우의의 마법사

### unsafe_promotion_from_hold
- `11658637` `null_to_resolved` post=`재막아)영기는 진짜 답이 없구나` options: C1=재벌집 막내아들
- `11660238` `null_to_resolved` post=`오늘 림조 한서진 청월한테 말하는 게 개웃기네` options: C1=무림마조
- `11669928` `null_to_resolved` post=`탑성좌애호 노벨피아 이거 연중했었네` options: C1=탑의 성좌들이 날 애호한다
- `11671501` `null_to_resolved` post=`판초법사 막 게이트열린 시점아님?` options: C1=판초우의의 마법사
- `11673086` `null_to_resolved` post=`랫따싶 칸시가 정실이엿으면` options: C1=[림월드]변방계에서 회귀자로 살아남기
- `11674703` `null_to_resolved` post=`도굴왕은 애니화 난이도 다른거 보단 괜찮을거 같은데` options: C1=도굴왕
- `11676317` `null_to_resolved` post=`마도서줍 그거 같아` options: C1=마도서를 줍다 마법사가 되다
- `11677957` `null_to_resolved` post=`페도부이 진짜 천재같네` options: C1=음악 천재가 불륜을 못 숨김

### safe_loss_resolved_to_null
- `11660254` `resolved_to_null` post=`노피아 애니메이션은 뭐임?` options: C1=푸푸푸 랜드의 두가지 일상
- `11668278` `resolved_to_null` post=`요즘 짜장면에 오이 넣는 집을 못본듯` options: C1=짜장면
- `11668305` `resolved_to_null` post=`급식때 마파두부 ㅈㄴ 맛있는집 있었는데` options: C1=Fate/stay night
- `11695609` `resolved_to_null` post=`랫따싶이 머 퍼리말하는거임?` options: C1=쳇바퀴의 생쥐 사도가 되었다
- `11697239` `resolved_to_null` post=`우우 장붕이 이런거 받았다` options: C1=조혈모세포 기증 궁금해요
- `11697249` `resolved_to_null` post=`버거피아 합석 머임????` options: C1=버거피아
- `11698904` `resolved_to_null` post=`타락한 ts녀가 참한 파릇파릇한 마법소녀타락시키는소설 추천좀` options: C1=타락
- `11703640` `resolved_to_null` post=`부기피아 재밋네` options: C1=헌터갤러리의 국가권력급 기계공주

## Gate 해석

이 산출물은 Loop599 full375 unreviewed40 after residual46를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
