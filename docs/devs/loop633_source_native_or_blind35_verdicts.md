# Loop633 source-native_or_blind residual35 판결

35건 전수를 `ACCEPT/HOLD/REPROCESS`로 판결했다. `ACCEPT`는 adjusted collateral 면제 후보이며 full375 GO나 full_scan approval이 아니다. `HOLD/REPROCESS`는 다음 residual lane으로 넘긴다.

## 요약
- reviewed rows: `35`
- label counts: `{'REPROCESS': 14, 'HOLD': 10, 'ACCEPT': 11}`
- action counts: `{'repair_safe_loss_restore_supported_title': 6, 'shared_promotion_gate_wiring_required': 6, 'native_web_or_image_evidence_required': 9, 'image_native_review_required': 2, 'exclude_from_regression_count_after_gate_wiring': 11, 'repair_unsafe_promotion': 4, 'intent_guard_review': 4, 'canonical_title_cleanup_required': 2, 'native_web_or_alias_relation_review_required': 3, 'repair_after_wrong_work': 6, 'candidate_set_rebuild_required': 6}`
- residual follow-up rows: `24`
- gate: `REVIEW-LOCKED`
- completion gate: `adjusted full375 collateral GO + full_scan path`
- raw 2026-06-26 baseline diff는 진단용이며 완료 기준이 아니다.

## Bucket별 회계
- `safe_loss_resolved_to_null`: rows `11`, labels `{'REPROCESS': 6, 'HOLD': 4, 'ACCEPT': 1}`, exclusion candidates `1`, residual follow-up `10`
- `unsafe_promotion_from_hold`: rows `9`, labels `{'HOLD': 4, 'ACCEPT': 4, 'REPROCESS': 1}`, exclusion candidates `4`, residual follow-up `5`
- `wrong_work_title_flip`: rows `15`, labels `{'REPROCESS': 7, 'ACCEPT': 6, 'HOLD': 2}`, exclusion candidates `6`, residual follow-up `9`

## 판결 목록
### `11660241` REPROCESS
- bucket: `safe_loss_resolved_to_null`
- selected: `이세계 TRPG 게임마스터`
- actions: `['repair_safe_loss_restore_supported_title', 'shared_promotion_gate_wiring_required']`
- rationale: 제목의 `이티알`과 본문 TRPG/현실 파트 감상, after blocked title `이세계 TRPG 게임마스터`가 같은 작품을 가리킨다. null 해소는 정당 제거가 아니라 shared gate를 통한 restore 대상이다.

### `11660268` REPROCESS
- bucket: `safe_loss_resolved_to_null`
- selected: `■■을 위한 세계는 없다`
- actions: `['repair_safe_loss_restore_supported_title', 'shared_promotion_gate_wiring_required']`
- rationale: 제목의 `ㅁㅁ세계`와 초대용사/운명/스탈린전 대화가 blocked title `■■을 위한 세계는 없다` 후보와 이어진다. after null은 raw safe-loss이며 restore gate로 넘긴다.

### `11663511` REPROCESS
- bucket: `safe_loss_resolved_to_null`
- selected: `부캐 키우는 황태자님`
- actions: `['repair_safe_loss_restore_supported_title', 'shared_promotion_gate_wiring_required']`
- rationale: 게시글 제목 `부캐황태자99화`가 prior 공식 제목 `부캐 키우는 황태자님`을 직접 약칭한다. after의 `문피아 새 창 열림` 차단은 후보 오염이므로 null 상태를 복구 대상으로 본다.

### `11669924` HOLD
- bucket: `safe_loss_resolved_to_null`
- selected: `None`
- actions: `['native_web_or_image_evidence_required']`
- rationale: `사일런트 루리드래곤`은 비교/감상 표면이고 원문만으로 `용인족의 아카데미 생존기` 공식 제목을 확정하기 부족하다. blocked title은 보존하되 native/이미지 근거 전 publish하지 않는다.

### `11669926` HOLD
- bucket: `safe_loss_resolved_to_null`
- selected: `None`
- actions: `['image_native_review_required', 'native_web_or_image_evidence_required']`
- rationale: 텍스트는 마녀/보추/미적분 맥락뿐이고 `싸울아비 룬`은 OCR/후보에 의존한다. 이미지 또는 native evidence 없이 safe-loss restore로 밀지 않는다.

### `11676321` REPROCESS
- bucket: `safe_loss_resolved_to_null`
- selected: `마도서를 줍다 마법사가 되다`
- actions: `['repair_safe_loss_restore_supported_title', 'shared_promotion_gate_wiring_required']`
- rationale: 제목 `마도서줍 시리즈`가 blocked title `마도서를 줍다 마법사가 되다`와 직접 맞고 댓글도 연재 재개 맥락이다. null은 restore 대상이다.

### `11682761` HOLD
- bucket: `safe_loss_resolved_to_null`
- selected: `None`
- actions: `['native_web_or_image_evidence_required']`
- rationale: `목마` 작가 토크와 이미지/후보 맥락만으로 `그레이스 길들이기`를 확정하기 어렵다. 작가-작품 연결 또는 이미지 근거 확인 전 hard-hold를 유지한다.

### `11682767` REPROCESS
- bucket: `safe_loss_resolved_to_null`
- selected: `묵향`
- actions: `['repair_safe_loss_restore_supported_title', 'shared_promotion_gate_wiring_required']`
- rationale: 게시글 제목이 `묵향`을 직접 말하고 댓글도 태허무령심법/아르티어스/드래곤 하트 맥락을 이어간다. after의 `묵향 1권` 차단은 canonical variant 문제일 뿐 null 해소 근거가 아니다.

### `11695599` HOLD
- bucket: `safe_loss_resolved_to_null`
- selected: `None`
- actions: `['image_native_review_required', 'native_web_or_image_evidence_required']`
- rationale: 본문 텍스트는 `봐라/재밌다`뿐이라 `창관전생`을 텍스트로 확정할 수 없다. OCR 후보는 보존하되 이미지/native 확인이 먼저다.

### `11708432` ACCEPT
- bucket: `safe_loss_resolved_to_null`
- selected: `None`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 본문의 `전독시급`은 독창성 비교 기준이고 댓글 흐름도 다른 논쟁/잡담으로 흘러간다. prior의 `전지적 독자 시점` 확정은 비교 참조를 주 작품으로 올린 FP에 가까우므로 adjusted 회계에서 면제한다.

### `11708443` REPROCESS
- bucket: `safe_loss_resolved_to_null`
- selected: `괴담에 떨어져도 출근을 해야 하는구나`
- actions: `['repair_safe_loss_restore_supported_title', 'shared_promotion_gate_wiring_required']`
- rationale: 게시글 제목 `괴담출근`은 blocked official URL의 작품 약어로 직접 쓰였고 본문도 괴담물 독창성 평가다. null은 restore 대상이다.

### `11657038` HOLD
- bucket: `unsafe_promotion_from_hold`
- selected: `None`
- actions: `['repair_unsafe_promotion', 'intent_guard_review', 'native_web_or_image_evidence_required']`
- rationale: 댓글에는 별도 novelpia URL과 게임 `데스티니` 표면이 섞여 있고 after `레드 데스티니 [D]`는 직접 제목 근거가 부족하다. unsafe promotion은 no-publish hard-hold로 남긴다.

### `11657044` HOLD
- bucket: `unsafe_promotion_from_hold`
- selected: `None`
- actions: `['repair_unsafe_promotion', 'intent_guard_review', 'native_web_or_image_evidence_required']`
- rationale: 화은쌤/이준 캐릭터 표면만으로 after `웨딩드레스` 공식 제목을 확정하기 어렵다. 이미지 또는 native character bridge 확인 전 publish를 막는다.

### `11660238` ACCEPT
- bucket: `unsafe_promotion_from_hold`
- selected: `무림마조`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 제목의 `림조`, 본문 한서진/청월 맥락, 기존 blocked snippet의 공식 제목이 모두 `무림마조`를 지지한다. snippet 오염을 제거한 after 승격은 정당 복구로 보고 adjusted 면제한다.

### `11681180` HOLD
- bucket: `unsafe_promotion_from_hold`
- selected: `None`
- actions: `['repair_unsafe_promotion', 'intent_guard_review', 'native_web_or_image_evidence_required']`
- rationale: `아카엠창` 표면은 after `아카데미 패드립 면역` 후보와 연결될 수 있지만 별칭 관계가 소스만으로 확정되지 않는다. alias relation/native evidence 전 hard-hold한다.

### `11682768` REPROCESS
- bucket: `unsafe_promotion_from_hold`
- selected: `마법소녀는 은퇴하고 싶다`
- actions: `['canonical_title_cleanup_required', 'native_web_or_alias_relation_review_required']`
- rationale: 제목의 `마법소녀ㄴ`과 세진/세린 대화는 해당 작품 맥락을 지지하지만 after public title은 띄어쓰기/OCR 노이즈가 남아 있다. publish 전 canonical title cleanup이 필요하다.

### `11685995` ACCEPT
- bucket: `unsafe_promotion_from_hold`
- selected: `가챠 중독자의 퓨전펑크 생활`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 댓글 `이거 가챠펑크맛임`과 after 후보가 같은 작품을 지지한다. baseline hold 대비 after 승격은 정당 복구로 보고 adjusted 면제한다.

### `11702060` ACCEPT
- bucket: `unsafe_promotion_from_hold`
- selected: `괴담 호텔 탈출기`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 한가인/305호/죄수/위대한 자/명패 없는 방은 `괴담 호텔 탈출기` 내부 맥락으로 직접 이어진다. after 승격은 unsafe promotion이 아니라 정당 복구다.

### `11705257` ACCEPT
- bucket: `unsafe_promotion_from_hold`
- selected: `히어로 IN 히로인`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 제목 `히로히로`와 댓글 `시아루트`/연재 맥락이 after `히어로 IN 히로인`을 지지한다. 이미지 팬아트 행이지만 텍스트 약어가 있어 adjusted 면제 후보로 둔다.

### `11710045` HOLD
- bucket: `unsafe_promotion_from_hold`
- selected: `None`
- actions: `['repair_unsafe_promotion', 'intent_guard_review']`
- rationale: 본문 근거가 사실상 없고 baseline도 context-only였다. after `공주는 언니를 황제로 만든다` 승격은 current source만으로 정답성을 확인할 수 없어 no-publish hard-hold한다.

### `11660257` REPROCESS
- bucket: `wrong_work_title_flip`
- selected: `암흑가 보스요? 제가요?`
- actions: `['repair_after_wrong_work', 'candidate_set_rebuild_required']`
- rationale: 게시글 제목 `암흑가보스`는 prior `암흑가 보스요? 제가요?`를 직접 가리킨다. after는 검색결과식 다른 작품 제목으로 오염되어 prior title 복구가 필요하다.

### `11663554` ACCEPT
- bucket: `wrong_work_title_flip`
- selected: `전 버튜버가 하고 싶은데요`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: `주서연`은 작품 내 인물이고 after는 같은 URL의 공식 제목이다. prior의 캐릭터+작품 혼합 표면보다 after canonical title이 맞아 adjusted 면제한다.

### `11665110` ACCEPT
- bucket: `wrong_work_title_flip`
- selected: `사이키델리아`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 게시글 제목이 `사이키델리아`를 직접 묻고 댓글도 표지/엔트로피 기억을 말한다. prior `낭만적인 초능력을 위하여`보다 after가 맞다.

### `11666713` HOLD
- bucket: `wrong_work_title_flip`
- selected: `None`
- actions: `['native_web_or_image_evidence_required', 'native_web_or_alias_relation_review_required']`
- rationale: `21세기 무림` 표면만으로 `21세기 무림세가`와 `21세기 현대무림 레거시`를 확정 분리하기 부족하다. native title evidence 확인 전 wrong-work 판정을 보류한다.

### `11669933` ACCEPT
- bucket: `wrong_work_title_flip`
- selected: `회귀수선전(回歸修仙傳)`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 중경계/해방상제/서휼 맥락은 회귀수선전이며 after는 같은 작품의 한자 병기/플랫폼 variant다. raw flip은 wrong-work가 아니라 canonical variant 변화로 면제한다.

### `11673102` REPROCESS
- bucket: `wrong_work_title_flip`
- selected: `갤질하는 천재 의사`
- actions: `['repair_after_wrong_work', 'candidate_set_rebuild_required']`
- rationale: 본문이 `갤질의사`를 랭킹 추천작으로 직접 열거한다. after `방송했더니 천재 의사로 착각당했다`는 후보 표면이 비슷한 다른 작품으로 보여 prior title 복구가 필요하다.

### `11674731` REPROCESS
- bucket: `wrong_work_title_flip`
- selected: `여자아이 만들기`
- actions: `['canonical_title_cleanup_required']`
- rationale: before/after가 같은 URL을 가리키지만 after에는 `새 창 열림`과 띄어쓰기 노이즈가 남아 있다. wrong-work raw는 canonical cleanup으로 처리한다.

### `11676309` REPROCESS
- bucket: `wrong_work_title_flip`
- selected: `갤질하는 천재 의사`
- actions: `['repair_after_wrong_work', 'candidate_set_rebuild_required']`
- rationale: 제목 `갤질의사 정실일러`가 prior `갤질하는 천재 의사`를 직접 지지한다. after `댓글 보는 천재 의사`는 비슷한 의사/댓글 표면 오염이므로 복구 대상이다.

### `11692426` ACCEPT
- bucket: `wrong_work_title_flip`
- selected: `절대타경 [독점]`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 게시글은 `절대타경` 자체를 말하며 before/after는 같은 작품의 플랫폼/독점 표기 차이에 가깝다. raw flip은 regression이 아니라 canonical/platform variant로 adjusted 면제한다.

### `11694065` REPROCESS
- bucket: `wrong_work_title_flip`
- selected: `아카데미에서 살아남기`
- actions: `['repair_after_wrong_work', 'candidate_set_rebuild_required']`
- rationale: 제목 `아카살 아니스`는 `아카데미에서 살아남기`와 인물 맥락을 직접 가리킨다. after `[아카살] 아무 관계도 아니라고!`는 제목 검색/2차 창작 표면으로 보이며 원 작품 복구가 필요하다.

### `11698877` REPROCESS
- bucket: `wrong_work_title_flip`
- selected: `괴담 호텔 탈출기`
- actions: `['repair_after_wrong_work', 'candidate_set_rebuild_required']`
- rationale: `괴담텔 1층/2층` 감상은 prior `괴담 호텔 탈출기`의 층 구조를 말한다. after `괴담텔 속 마술사`는 alias collision이므로 복구 대상이다.

### `11702094` ACCEPT
- bucket: `wrong_work_title_flip`
- selected: `댓글창의 천재 마법사`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 게시글 제목이 `댓글창`을 직접 말하고 본문 `더블오 정체`는 작품 내 요소로 보인다. prior `#더블오`보다 after 공식 제목이 정답에 가까워 adjusted 면제한다.

### `11703631` REPROCESS
- bucket: `wrong_work_title_flip`
- selected: `나의 악당들`
- actions: `['repair_after_wrong_work', 'candidate_set_rebuild_required']`
- rationale: after `피카레스크`는 장르어이고 작품 제목으로 publish하기 부적절하다. 댓글의 승수/인성 논의가 prior `나의 악당들` 맥락을 지지하므로 복구 또는 후보 재구축이 필요하다.

### `11705269` HOLD
- bucket: `wrong_work_title_flip`
- selected: `None`
- actions: `['native_web_or_image_evidence_required', 'native_web_or_alias_relation_review_required']`
- rationale: 월야환담/베놈/실베스테르 맥락은 작품군을 지지하지만 generic `월야환담`과 subseries `월야환담 : 신월야` 중 어느 공표 title이 맞는지는 native evidence가 필요하다.

### `11714903` ACCEPT
- bucket: `wrong_work_title_flip`
- selected: `괴담 호텔 탈출기`
- actions: `['exclude_from_regression_count_after_gate_wiring']`
- rationale: 본문에 `괴담텔`, 아리/가인/심판자, 댓글 한가인 맥락이 직접 있어 after `괴담 호텔 탈출기`가 맞다. prior `온 세상이 정신이상자다`는 제목 표면 오인으로 보고 adjusted 면제한다.
