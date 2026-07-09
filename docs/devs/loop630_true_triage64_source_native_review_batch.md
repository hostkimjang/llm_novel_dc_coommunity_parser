# Loop630 Loop629 true triage 64 source-native review blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `64`
- excluded post_id rows: `0`
- excluded P0 candidate rows: `0`
- include all priorities: `true`

## 입력

- triage: `docs/devs/loop630_loop629_full375_collateral_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop629_full375_after_loop628_search_blocker_closure_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `29`
- `unsafe_promotion_from_hold`: `11`
- `wrong_work_title_flip`: `24`

## Priority

- `P0`: `64`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 Loop630 Loop629 true triage 64 source-native review 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11660257` `resolved_to_different_title` post=`암흑가보스<<이거 재밋네` options: C1=고수위.국제마약카르텔. 암흑가 의 보스 들 새 창 열림, C2=암흑가 보스요? 제가요?
- `11663514` `resolved_to_different_title` post=`슬라임의 올바른 사용법` options: C1=마탄 속의 제국, C2=올바른 슬라임 사용법
- `11663554` `resolved_to_different_title` post=`TS) 주서연 영화개봉 했는데 1엄복동도 못되면` options: C1=전 버튜버가 하고 싶은데요, C2=주서연 ( 전 버튜버가 하고 싶은데요 )
- `11665099` `resolved_to_different_title` post=`옥천마 출정 ㅇㅈㄹ하는 부분부터 대가리 봉합됐음` options: C1=옥천마 출정, C2=옥탑방의 천재 마물 소환사
- `11665110` `resolved_to_different_title` post=`사이키델리아 읽었던 사람 있냐?` options: C1=낭만적인 초능력을 위하여, C2=사이키델리아
- `11666713` `resolved_to_different_title` post=`21세기 무림 이거 재미네 ㅋㅋㅋ` options: C1=21세기 무림세가, C2=21세기 현대무림 레거시
- `11669907` `resolved_to_different_title` post=`이거 중간에 뱉길 잘했네` options: C1=마법 좋아좋아좋아, C2=약스포) 마법 좋아좋아좋아
- `11669929` `resolved_to_different_title` post=`기계공주 재밌네` options: C1=기계공주, C2=헌터갤러리의 국가권력급 기계공주

### unsafe_promotion_from_hold
- `11657038` `null_to_resolved` post=`이거 왠지 공감됨` options: C1=레드 데스티니 [D]
- `11657044` `null_to_resolved` post=`이거 화은쌤이 이렇게 입었다고 생각하니까 확실히` options: C1=웨딩드레스
- `11660238` `null_to_resolved` post=`오늘 림조 한서진 청월한테 말하는 게 개웃기네` options: C1=무림마조
- `11681180` `null_to_resolved` post=`아카엠창 감정선 맛있네` options: C1=아카데미 패드립 면역
- `11682768` `null_to_resolved` post=`근데 마법소녀ㄴ 일란성 쌍둥이라는거 뭔소리임` options: C1=마법소녀ㄴ 은 은퇴하고 싶다
- `11685995` `null_to_resolved` post=`관우도 울고갈 근들갑 실력 ㄷㄷㄷㄷ` options: C1=가챠 중독자의 퓨전펑크 생활
- `11687618` `null_to_resolved` post=`아생갤 떡밥 나오니까 좀 재밌네` options: C1=아카데미 생존 갤러리
- `11697231` `null_to_resolved` post=`아생갤 어렵네` options: C1=아카데미 생존 갤러리

### safe_loss_resolved_to_null
- `11660241` `resolved_to_null` post=`난 이티알은 현실파트가 너무 불호라 하차했는데` options: C1=이세계 TRPG 게임마스터
- `11660268` `resolved_to_null` post=`ㅁㅁ세계 초대용사전의 문제점` options: C1=을 위한 세계는 없다
- `11660271` `resolved_to_null` post=`아이돌 히로인 나오는 야설 어디 없나` options: C1=월야의 여인들
- `11660273` `resolved_to_null` post=`장빙이들 그리즐리 주면 키울거임?` options: C1=마도서를 줍다 마법사가 되다
- `11663511` `resolved_to_null` post=`부캐황태자99화) 몸은 검으로 되어있다` options: C1=부캐 키우는 황태자님
- `11663557` `resolved_to_null` post=`퇴마록 생각해보니 올해 예능프로그램으로 나오지 않나` options: C1=퇴마록
- `11665121` `resolved_to_null` post=`시리즈에 유일하게 댓글썼던게 하나있네` options: C1=후회 안 하는 프로듀서
- `11666725` `resolved_to_null` post=`아 이거 재밌어 보이는데 남주가 매력적임` options: C1=학대받던 11살 고마가 각성한 이유

## Gate 해석

이 산출물은 Loop630 Loop629 true triage 64 source-native review를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
