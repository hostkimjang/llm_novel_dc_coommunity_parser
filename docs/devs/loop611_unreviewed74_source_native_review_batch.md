# loop611_unreviewed74_publication_sync_projection blind/source-native 검토 배치

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- search recovery gate: `P0_OPEN`
- promotion_blocked 해석: `search-blind conditional`
- selected review rows: `74`
- excluded post_id rows: `0`
- excluded P0 candidate rows: `0`

## 입력

- triage: `docs/devs/loop611_full375_after_loop610_publication_sync_projection_collateral_triage.json`
- panel_input: `out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl`
- baseline_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/baseline_result.json`
- after_result: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop611_full375_after_loop610_publication_sync_projection_result.json`

## Bucket

- `safe_loss_resolved_to_null`: `50`
- `unsafe_promotion_from_hold`: `10`
- `wrong_work_title_flip`: `14`

## Blind judge 운영 지침

- judge에는 `source_native_packet`, `blind_judge_options`, `blind_judge_hold_option`만 전달한다.
- `comparison_private_not_for_blind_judge`는 전후 회귀 추적용이므로 judge 입력에서 제외한다.
- native web 확인 전까지 `needs_native_web_check=true`를 유지한다.
- 이 배치는 loop611_unreviewed74_publication_sync_projection 정답성 검토 입력이며 승인 산출물이 아니다.

## 대표 행

### wrong_work_title_flip
- `11660257` `resolved_to_different_title` post=`암흑가보스<<이거 재밋네` options: C1=그룹을 위해 당연한 일을 했을 뿐인데. 정체불명의 암흑가 보스 니 검은 자본이니. 다들 호들갑이 심하다니까, C2=암흑가 보스요? 제가요?
- `11663514` `resolved_to_different_title` post=`슬라임의 올바른 사용법` options: C1=마탄 속의 제국, C2=올바른 슬라임 사용법
- `11663557` `resolved_to_different_title` post=`퇴마록 생각해보니 올해 예능프로그램으로 나오지 않나` options: C1=퇴마록, C2=퇴마록 1
- `11666713` `resolved_to_different_title` post=`21세기 무림 이거 재미네 ㅋㅋㅋ` options: C1=21세기 무림세가, C2=21세기 현대무림 레거시
- `11669907` `resolved_to_different_title` post=`이거 중간에 뱉길 잘했네` options: C1=마법 좋아좋아좋아, C2=약스포) 마법 좋아좋아좋아
- `11669926` `resolved_to_different_title` post=`미적분 공식 외우면 발동되는 마법` options: C1=싸울 할 비 문, C2=싸울아비 룬
- `11673077` `resolved_to_different_title` post=`즉사무림 판초우의 빚세구 다 봄` options: C1=즉사기 들고 무림에 떨어지다, C2=판초우의의 마법사
- `11673096` `resolved_to_different_title` post=`오누레 맘마임` options: C1=삼국지, C2=이문열 삼국지 1

### unsafe_promotion_from_hold
- `11657045` `null_to_resolved` post=`누렁이들아` options: C1=금태양과 음침녀
- `11657047` `null_to_resolved` post=`베지테리언이 정육점 사장이 됐다 이런 소설 보고잡네` options: C1=베지테리언 블러드
- `11668324` `null_to_resolved` post=`니생들이랑 김괴라리 장갤픽 아니였음?` options: C1=니들 생각 다 들린다
- `11677919` `null_to_resolved` post=`창작물 성유진은 갑자기 능력 얻었어도 비호감은 아니었음ㅋㅋㅋㅋㅋㅋ` options: C1=내 누나가 아니었음 좋겠어
- `11681180` `null_to_resolved` post=`아카엠창 감정선 맛있네` options: C1=아카데미 패드립 면역
- `11685995` `null_to_resolved` post=`관우도 울고갈 근들갑 실력 ㄷㄷㄷㄷ` options: C1=가챠 중독자의 퓨전펑크 생활
- `11695639` `null_to_resolved` post=`TS해서 인방하는데 아빠가 내 방송을 봄` options: C1=준우승 세 번 했더니 미소녀 됨
- `11697234` `null_to_resolved` post=`목마꺼 이번에 스타트 좋네` options: C1=검귀가 환생했더니

### safe_loss_resolved_to_null
- `11658626` `resolved_to_null` post=`아카선비는 좀 더 쎄지 않았나` options: C1=아카데미 선비의 생활일지
- `11660241` `resolved_to_null` post=`난 이티알은 현실파트가 너무 불호라 하차했는데` options: C1=이세계 TRPG 게임마스터
- `11660264` `resolved_to_null` post=`빚세구 근데 주인공이 은발에 아이돌 출신이란 게 좀 신경쓰이네` options: C1=빚을 져서라도 세상은 구해야 할 거 아니야
- `11660268` `resolved_to_null` post=`ㅁㅁ세계 초대용사전의 문제점` options: C1=을 위한 세계는 없다
- `11660271` `resolved_to_null` post=`아이돌 히로인 나오는 야설 어디 없나` options: C1=월야의 여인들
- `11661881` `resolved_to_null` post=`여신애호) 잉잉이의 정체...` options: C1=여신이 나만 애호함
- `11663511` `resolved_to_null` post=`부캐황태자99화) 몸은 검으로 되어있다` options: C1=부캐 키우는 황태자님
- `11663521` `resolved_to_null` post=`TS) 시스터즈 퍼스트 정신머리 고치려면` options: C1=초전자포] 시스터즈가 되었다

## Gate 해석

이 산출물은 loop611_unreviewed74_publication_sync_projection를 blind/source-native 검토 가능한 입력으로 고정한다. 정답 라벨이 채워지기 전까지 full collateral approval은 열리지 않는다.
