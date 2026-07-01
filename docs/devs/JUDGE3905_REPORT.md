# 3905 슬라이스 GPT Pro LLM-judge 전수 보고서

작성: 2026-06-14
대상 run: `expert_result_20260612_174715_296791` 완료 slice `3874`건
judge: ChatGPT GPT Pro via `agbrowse`
산출 위치: `out/_judge3905_gpt_pro_v2`

## 0. 커버리지와 주의

- 전수 완료: `3874 / 3874` posts, `155 / 155` batches.
- post_id 누락 검증: `verdict_000.json` ~ `verdict_154.json`, missing `0`.
- aggregate: `agree=2303`, `disagree=1571`, `invalid_batches=[]`.
- 이 결과는 104,502 full-scan 중 순차 head slice 성격이다. 모집단 오류율 또는 전체 품질 승인으로 환산하지 않는다.
- 이번 GPT Pro judge는 웹검색 없이 첨부 batch의 title/body/comments/image_ocr와 기존 모델 지식만 사용했다. `web_unverified` note가 붙은 항목은 공식 ground truth가 아니라 재검토 seed다.

## 1. 헤드라인

- 파이프라인과 GPT Pro judge 일치율: `2303 / 3874 = 59.4%`.
- 불일치: `1571 / 3874 = 40.6%`.
- severity: `high=292`, `med=693`, `low=2889`.
- 가장 큰 문제 축은 recall이다. `under_resolved_false_negative=644`로, 식별 가능한 작품/작품 관련 글을 none/noise/trope로 놓친 케이스가 최다다.
- precision 고위험 축도 선명하다. `cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title`은 수는 적지만 high 비율이 높다.

## 2. 불일치 유형 분포

| 유형 | 총건수 | high | med | low | 의미 |
|---|---:|---:|---:|---:|---|
| `under_resolved_false_negative` | 644 | 198 | 438 | 8 | 작품/작품 관련 글을 미해소 또는 비관련으로 떨어뜨림 |
| `wrong_discussion_type` | 549 | 0 | 71 | 478 | 관련/비관련 판단은 대체로 맞지만 의도 라벨이 틀림 |
| `wrong_relevance` | 169 | 2 | 139 | 28 | 웹소설 관련성을 noise/offtopic 등으로 잘못 봄 |
| `uncertain` | 66 | 0 | 2 | 64 | 첨부 증거만으로 확정 어려움 |
| `cross_media_or_famous_mismatch` | 52 | 29 | 20 | 3 | 게임/웹툰/애니/고전/유명작을 웹소설로 오인 |
| `wrong_work` | 39 | 29 | 9 | 1 | 다른 작품으로 확정 |
| `over_resolved` | 22 | 20 | 2 | 0 | 작품명이 아닌 표현/비교/인물/공지 등을 작품으로 확정 |
| `title_noisy_ocr` | 20 | 6 | 10 | 4 | 작품은 맞지만 제목 OCR/토큰 오염 |
| `garbage_title` | 10 | 8 | 2 | 0 | URL/일반어/불완전 문자열을 공식 제목으로 채택 |

## 3. 핵심 한계

### A. Recall: under-resolved false negative

최대 손실 축이다. 약칭, 캐릭터명, OCR 표제, 댓글의 제목 응답, 작가 신작 맥락이 있는데 `none`, `noise`, `trope_discussion`으로 남는 케이스가 많다.

대표 high/med seed:

- high: `11718107`, `11713221`, `11713205`, `11711629`, `11713200`, `11711598`, `11710038`, `11710043`, `11710049`, `11710036`.
- med: `11718095`, `11718089`, `11716505`, `11716500`, `11718057`, `11716478`, `11716480`, `11716459`, `11716472`, `11716479`.

개선 방향:

- 표준 약칭 및 갤러리 화제작 재식별 bridge 강화.
- 캐릭터명/회차/작가 신작 단서가 있을 때 단순 trope/noise로 내리지 않는 보수적 관련성 gate.
- OCR 표제와 댓글 제목 응답을 `low-confidence candidate`로라도 보존.

### B. Discussion type drift

`wrong_discussion_type=549`로 매우 많다. 다만 high는 없고 대부분 low다. 실제로는 noise/offtopic인데 trope로 남거나, 작가/신작 메타인데 character_talk로 붙는 식이다.

대표 seed:

- med: `11718121`, `11718084`, `11718096`, `11718051`, `11714891`, `11706863`, `11706856`, `11708448`, `11706866`, `11705255`.
- low: `11718066`, `11718056`, `11716493`, `11718059`, `11716474`, `11718104`, `11714908`.

개선 방향:

- 작품 식별과 discussion_type을 분리 검증한다.
- `is_relevant=false`인 row에 `trope_discussion`이 붙는 라벨 위생을 별도 lint로 잡는다.

### C. Relevance miss

`wrong_relevance=169` 중 med가 139건이다. 추천 요청, 작가 작품 순서 질문, 웹소설 커뮤니티 메타가 noise로 떨어지는 케이스가 많다.

대표 seed:

- med: `11718085`, `11718091`, `11718087`, `11716488`, `11718061`, `11716475`, `11716473`, `11714901`, `11714903`, `11714877`.
- high: `11602367`, `11600689`.

개선 방향:

- 추천 요청/작가 작품 순서/플랫폼 독서 맥락은 작품명이 없어도 relevant로 유지한다.
- 특정 작품 해소 실패와 관련성 실패를 분리한다.

### D. Cross-media and famous-title mismatch

빈도는 `52`건이지만 high가 `29`건이다. 탑툰/게임/애니/고전/실사 기사/유명 캐릭터가 웹소설 공식 제목으로 승격되는 오류다.

대표 high seed:

- `11718055`, `11706871`, `11697244`, `11694068`, `11692433`, `11690864`, `11690860`, `11687652`, `11686008`, `11682761`.

개선 방향:

- 플랫폼/도메인 gate: 게임 스토어, 위키, 웹툰, 출판 고전, 방송/기사 화면은 웹소설 확정 전에 차단.
- OCR/검색 source tier가 웹소설 플랫폼인지 확인하지 못하면 `resolved`를 보류.

### E. Wrong work / over-resolved / garbage title

수는 적지만 high 비율이 높아 사용자 체감 품질을 크게 해친다.

대표 wrong_work high:

- `11718105`, `11716503`, `11714912`, `11711610`, `11708453`, `11705271`, `11692441`, `11682791`, `11682751`, `11674733`.

대표 over_resolved high:

- `11700504`, `11697224`, `11695600`, `11695593`, `11685995`, `11684402`, `11684372`, `11677932`, `11676310`, `11671538`.

대표 garbage_title high:

- `11710063`, `11695594`, `11661857`, `11660265`, `11653841`, `11652198`, `11648985`, `11629691`.

개선 방향:

- 비교 인용작과 대상작을 분리한다.
- 인물명, 성격 묘사어, 부제, URL, 도메인, 광고/공지 일반어를 official title로 채택하지 않는다.
- OCR 표제 후보가 있더라도 제목 토큰이 비문/도메인/일반어면 `title_noisy_ocr` 또는 unresolved로 보류한다.

## 4. 산출물

- 최종 집계: `out/_judge3905_gpt_pro_v2/_result.json`
- 유형별 post_id 전체 목록: `out/_judge3905_gpt_pro_v2/post_ids_by_type.json`
- post_id별 전수 리뷰 JSONL: `out/_judge3905_gpt_pro_v2/post_reviews.jsonl`
- post_id별 전수 리뷰 Markdown: `out/_judge3905_gpt_pro_v2/post_reviews.md`
- batch별 GPT Pro verdict: `out/_judge3905_gpt_pro_v2/verdict_000.json` ~ `verdict_154.json`

## 5. 다음 작업 우선순위

1. `under_resolved_false_negative` high/med seed부터 약칭·캐릭터명·OCR 표제·댓글 제목 응답 bridge를 개선한다.
2. `cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title` high seed를 precision regression set으로 묶는다.
3. discussion_type은 quality lint로 분리해, `is_relevant=false`와 `trope_discussion` 공존 같은 저위험 다량 오류를 자동 감사한다.
4. 전수 judge는 진단/seed 생성물로만 쓰고, full-scan approval은 별도 random/high-risk expansion과 실제 source-grounded verification 후 판단한다.

## 6. P0 seed registry / expert_main canary 후속

2026-06-14 후속으로 `tools/build_judge_seed_registry.py`를 추가해 이 judge 결과를 실행 가능한 P0 seed registry로 포장했다.

- registry seed: `1505`건, source missing `0`.
- group count: `recall=644`, `precision=123`, `hygiene=738`.
- shadow label: `candidate_generation_miss=164`, `hold_unresolved=480`, `identity_consistency_lint=94`, `output_consistency_lint=738`, `review_only=29`.
- 24건 canary를 `.venv312` + `expert_main.py`로 실제 실행했다. run id `20260614_230245_886140`, input/completed/flushed/pending/failed `24/24/24/0/0`.
- manifest-scope compare 기준 expected/result/compared `24/24/24`, missing `0`, run integrity `GO`.
- after shadow label: `safe_resolved=3`, `promotion_blocked=3`, `hold_unresolved=2`, `review_only=6`, `output_consistency_lint=8`, `identity_consistency_lint=2`.
- 한계: judge batch source에는 원본 image URL이 없어 canary 24건 중 image seed without URL이 `18`건이고, 실행 manifest의 `image_post_count=0`, VLM/OCR skip reason은 `no_image_blocks`다.

상세 기록은 `docs/devs/JUDGE3905_P0_SEED_REGISTRY_CANARY_20260614.md`에 남겼다. 이 canary는 run integrity 확인과 regression seed 관측이며, full scan approval은 아니다.

## 7. 2026-06-15 source-enriched VLM/OCR canary 후속

기존 24건 canary의 가장 큰 한계였던 image URL 누락을 원본 checkpoint에서 복원했다.

- source-enriched input: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_input.jsonl`
- restore report: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_restore_report.json`
- result: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_result.json`
- manifest: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_result_manifest.json`
- compare: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_compare.json`
- runtime audit: `out/judge3905_p0_seed_registry/judge3905_p0_source_enriched_canary_runtime_audit.json`

복원 결과:

- 기존 24건 중 image seed는 `18`건이고, 누락 image URL `18`건을 모두 복원했다.
- unrecovered post는 `0`이다.
- source-enriched input 기준 image posts `18`, image URLs `27`이다.

pipeline 연결:

- `expert_main.py` 결과의 `analysis_result.identity`에 `candidate_ledger`, `candidate_ledger_status`, promotion/lint flags를 기록한다.
- `under_resolved_false_negative`는 `official_title` 강제 승격보다 후보 보존/보류 상태를 `candidate_ledger`에 남긴다.
- precision seed(`cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title`)는 resolved title이 남으면 `identity_consistency_lint`, title이 차단되면 `promotion_blocked`로 관측한다.
- hygiene seed(`wrong_discussion_type`, `wrong_relevance`, `title_noisy_ocr`)는 `output_consistency_lint`로 분리한다.

실행 결과:

- run id: `20260615_001642_376095`
- input/completed/flushed/pending/failed: `24/24/24/0/0`
- requested/effective parallel: `24/24`
- MCP health: `8/8`
- `image_post_count=18`
- VLM/OCR semantic gate: `READY`
- 이미지 post 18/18에 `image_evidence_catalog`, `vlm_enrichment_used`, image fetch counters가 남았다.

compare:

- expected/result/compared: `24/24/24`
- missing result: `0`
- after shadow labels: `safe_resolved=3`, `promotion_blocked=7`, `hold_unresolved=4`, `output_consistency_lint=8`, `identity_consistency_lint=2`
- `candidate_ledger` present: `24/24`
- gate: run integrity `GO`, semantic quality `REVIEW-LOCKED`

해석:

- 개선됨: 기존 `image_post_count=0` / `no_image_blocks` 한계는 이 24건 canary 범위에서 닫혔다.
- 개선됨: shadow artifact가 실제 pipeline output field로 연결되어 compare가 실제 result row의 candidate/lint 상태를 읽는다.
- 불확실: `safe_resolved=3`과 OCR title cleanup 계열은 source/VLM 증거가 생겼지만, judge seed 자체가 head-slice 진단용이므로 정답 승인으로 환산하지 않는다.
- 회귀 가능/새 버그 후보: `identity_consistency_lint=2`와 `output_consistency_lint=8`은 후속 semantic spot review 또는 P0/P1 expansion으로 닫아야 한다.

이 후속도 full 10만 scan approval이 아니다. run integrity와 source/VLM coverage는 `GO`지만 semantic quality는 계속 `REVIEW-LOCKED`다.

## 8. 2026-06-15 high-risk expansion / slang DB guard 후속

source-enriched 24건 canary 이후, 기존 canary와 겹치지 않는 source-backed high-risk expansion을 추가 실행했다.

산출물:

- expansion input: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_input.jsonl`
- expansion manifest: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_manifest.json`
- expansion restore report: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_restore_report.json`
- expansion result: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_result.json`
- expansion result manifest: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_result_manifest.json`
- expansion compare: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_compare.json`
- expansion runtime audit: `out/judge3905_p0_seed_registry/judge3905_p0_highrisk_expansion_runtime_audit.json`
- slang focused result: `out/judge3905_p0_seed_registry/judge3905_p0_slang_guard_focus_result.json`
- slang focused compare: `out/judge3905_p0_seed_registry/judge3905_p0_slang_guard_focus_compare.json`
- slang focused runtime audit: `out/judge3905_p0_seed_registry/judge3905_p0_slang_guard_focus_runtime_audit.json`

high-risk input:

- selected: `36`
- excluded previous canary post: `24`
- missing source: `0`
- group count: `recall=12`, `precision=16`, `hygiene=8`
- disagreement types: `under_resolved_false_negative=12`, `cross_media_or_famous_mismatch=16`, `wrong_relevance=1`, `title_noisy_ocr=7`
- image post count: `36`
- restore status: `restored=36`

high-risk 실행 결과:

- run id: `20260615_012056_067394`
- input/completed/flushed/pending/failed: `36/36/36/0/0`
- effective parallel: `36`
- MCP health: `8/8`
- `image_post_count=36`
- VLM/OCR semantic gate: `READY`

high-risk compare:

- expected/result/compared: `36/36/36`
- missing result: `0`
- after shadow labels: `safe_resolved=7`, `promotion_blocked=12`, `hold_unresolved=3`, `output_consistency_lint=8`, `identity_consistency_lint=5`, `official_title_lint=1`
- official title changed: `23`
- official title lint after: `1`
- identity consistency lint after: `14`
- gate: run integrity `GO`, semantic quality `REVIEW-LOCKED`

새로 확인한 문제:

- `novel -> novel.munpia.com`, `dc -> 내가 주인공인 줄 알았다`, `그리고 -> 괴담에 휘말린 피해자가 되었다`가 slang DB flush observation으로 남는 저정보 alias 오염이 확인됐다.
- `src/llm_batch/slang_db.py`에 URL/domain/platform token 및 Korean connective surface guard를 추가했다.
- post-patch focused canary run id `20260615_021205_542965`에서 3/3 completed, `image_post_count=3`, VLM/OCR `READY`, finalize flush `buffered_observations=0`, titles `0`으로 재발하지 않음을 확인했다.

당시 남은 한계:

- `11663514`는 focused run에서도 `official_title=novel.munpia.com`으로 남아 `official_title_lint`가 유지됐다. 이번 패치는 slang DB 재사용 오염을 막은 것이며, URL/domain official title 승격 자체는 별도 promotion guard로 닫아야 하는 상태였다.
- random baseline은 이 시점에는 아직 실행하지 않았다.
- 따라서 이 단계의 JUDGE3905 loop는 pipeline-level instrumentation, source restoration, high-risk expansion, slang DB guard verification까지 진행했지만 full 10만 scan approval은 아니었다. semantic quality는 계속 `REVIEW-LOCKED`다.

## 9. 2026-06-15 URL/domain promotion guard / random50 p32 baseline 후속

section 8에서 남긴 `11663514` domain-title blocker와 random baseline 미실행 blocker를 후속으로 닫았다.

코드 조치:

- `src/llm_batch/candidate_audit.py`에 `apply_official_title_promotion_guard()`를 추가했다.
- URL/domain/platform/generic label이 `official_title`로 들어오면 `official_title`, `official_novel_title`, `resolved_title`, `novel_identity.official_title`, `heretic_url`을 demote하고 `promotion_blocked` 상태로 남긴다.
- 차단된 표면은 `blocked_official_title`, `blocked_official_title_url`, `promotion_blocked_reasons`와 `candidate_ledger`에 보존한다.
- `expert_main.py`는 candidate audit fields 생성 전에 promotion guard를 적용한다.

focused regression canary:

- input: `out/judge3905_p0_seed_registry/judge3905_p0_domain_guard_lint_focus_input.jsonl`
- result: `out/judge3905_p0_seed_registry/judge3905_p0_domain_guard_lint_focus_result.json`
- manifest: `out/judge3905_p0_seed_registry/judge3905_p0_domain_guard_lint_focus_result_manifest.json`
- compare: `out/judge3905_p0_seed_registry/judge3905_p0_domain_guard_lint_focus_compare.json`
- runtime audit: `out/judge3905_p0_seed_registry/judge3905_p0_domain_guard_lint_focus_runtime_audit.json`
- run id: `20260615_105502_850042`
- expected/result/compared: `15/15/15`, missing `0`
- after labels: `promotion_blocked=4`, `identity_consistency_lint=3`, `output_consistency_lint=8`
- official title lint after: `0`
- `11663514`: `official_title=null`, `promotion_blocked`; domain label is no longer an official title.

random baseline:

- input: `out/judge3905_p0_seed_registry/judge3905_p0_random50_baseline_input.jsonl`
- p32 result: `out/judge3905_p0_seed_registry/judge3905_p0_random50_baseline_p32_result.json`
- p32 runtime audit: `out/judge3905_p0_seed_registry/judge3905_p0_random50_baseline_p32_runtime_audit.json`
- p32 quality summary: `out/judge3905_p0_seed_registry/judge3905_p0_random50_baseline_p32_quality_summary.json`
- run id: `20260615_120734_501402`
- completed/failed: `50/0`
- `image_post_count=30`, VLM/OCR semantic gate `READY`
- runtime contract: `GO`
- candidate ledger status: `safe_resolved=10`, `review_only=2`, `hold_unresolved=31`, `promotion_blocked=7`
- official/identity/output lint counts: all `{}`
- domain/URL official title rows: `[]`

해석:

- 개선됨: `11663514`의 domain/title 승격 blocker는 focused canary 기준 닫혔다.
- 개선됨: random baseline 미실행 blocker는 p32 run/audit/quality summary로 닫혔다.
- 불확실/보류: focused canary의 `identity_consistency_lint=3`(`11634549`, `11657028`, `11673108`)은 cross-media/famous mismatch 수동 semantic review가 필요하다.
- 불확실/보류: focused canary의 `output_consistency_lint=8`은 OCR/title hygiene row라 다음 targeted patch 또는 사람 리뷰로 닫는다.
- 최종 gate: run integrity는 focused/p32 모두 `GO`지만 semantic quality는 계속 `REVIEW-LOCKED`다. 이 후속도 full 10만 scan approval이 아니다.

## 10. 2026-06-15 remaining-lint focused closure 후속

section 9의 remaining target 11건을 post_id별로 재검토하고, 즉시 일반화 가능한 guard를 추가했다.

산출물:

- input: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_input.jsonl`
- evidence table: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_evidence_table.json`
- result/checkpoint: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_result.json`, `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_result_checkpoint.jsonl`
- recovery summary: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_recovery_summary.json`
- final postprocessed result: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_result_recovered_14_postprocessed.json`
- compare: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_compare.json`
- runtime audit: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_runtime_audit.json`
- quality summary: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_quality_summary.json`

코드 조치:

- precision judge seed(`cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title`)에서 official title이 남으면 platform URL이 있어도 `promotion_blocked`로 내려 후보 ledger에 보존한다.
- `title_noisy_ocr` safe 판정은 official search title match가 있어야 한다. `primary_work` self-claim과 URL만으로는 safe 처리하지 않는다.

실행 결과:

- run id: `20260615_165906_220298`
- input/completed/flushed/pending/failed: `15/14/8/6/0`
- `image_post_count=15`, VLM/OCR semantic gate `READY`
- runtime contract: `NO-GO`
- 실제 미완료 row: control `11639284`
- target 11건은 checkpoint/recovered subset에 모두 존재한다.

final postprocess target status:

- `promotion_blocked`: `11634549`, `11657028`, `11673108`
- `safe_resolved`: `11605540`, `11628058`, `11629688`
- `hold_unresolved`: `11602334`
- `output_consistency_lint`: `11602367`, `11632915`, `11636134`, `11650591`

해석:

- 개선됨: precision/famous mismatch 3건은 official title을 public resolved로 두지 않고 candidate ledger에 보존한다.
- 개선됨: `11636134`처럼 official search title과 final title이 다른 OCR/title row는 safe로 닫지 않는다.
- 보류: `11602367`, `11632915`, `11636134`, `11650591`은 사람 semantic review 또는 별도 OCR/title evidence patch가 필요하다.
- run integrity: original 15-row run은 `NO-GO`이고, recovered subset은 semantic target evidence로만 사용한다.
- semantic quality: 계속 `REVIEW-LOCKED`; full 10만 scan approval이 아니다.

## 11. 2026-06-15 remaining output-lint manual closure / control cleanup

section 10의 open item 중 패치 가능한 OCR/title evidence guard와 미완료 control runtime gap을 닫았다. 이 후속도 full scan approval이 아니라 targeted evidence closure다.

산출물:

- control input/result/manifest: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_control_11639284_input.jsonl`, `out/judge3905_p0_seed_registry/judge3905_p0_remaining_control_11639284_result.json`, `out/judge3905_p0_seed_registry/judge3905_p0_remaining_control_11639284_result_manifest.json`
- control runtime audit: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_control_11639284_runtime_audit.json`
- combined postprocessed result: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_lint_focus_result_combined15_postprocessed.json`
- closure compare: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_closure_compare.json`
- closure summary: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_closure_summary.json`
- manual evidence packets: `out/judge3905_p0_seed_registry/judge3905_p0_remaining_output_lint_manual_evidence_packets.json`

코드 조치:

- `title_noisy_ocr` seed에서 current official title이 URL을 갖고 있고, image explicit work title과 official/platform search evidence가 같은 URL에서 일치할 때만 `official_title`을 재정렬한다.
- URL 없는 OCR-only 또는 partial/ellipsis title은 자동 correction하지 않고 manual/OCR review로 남긴다.

실행 결과:

- control rerun id: `20260615_194903_574111`
- control input/completed/flushed/pending/failed: `1/1/1/0/0`
- control runtime contract: `GO`
- combined15 compare expected/result/compared: `15/15/15`, missing `0`
- combined15 after labels: `safe_resolved=4`, `promotion_blocked=7`, `hold_unresolved=1`, `output_consistency_lint=3`

post_id 판정:

- `11636134`: `불패의 명장으로 착각당했다`로 title hygiene correction, `safe_resolved`.
- `11639284`: single control rerun으로 runtime gap closed, semantic status는 cross-media/famous precision control `promotion_blocked`.
- `11602367`: official title/candidate evidence 부족으로 `output_consistency_lint` 유지.
- `11632915`: image OCR title surface는 있으나 official/platform correction 근거 부족으로 `output_consistency_lint` 유지.
- `11650591`: partial/ellipsis OCR title이며 official/platform 근거 부족으로 `output_consistency_lint` 유지.

최종 해석:

- run integrity: control-only cleanup은 `GO`; original 15-row run은 historical `NO-GO` 유지.
- semantic quality: `REVIEW-LOCKED`.
- remaining manual output lint: `11602367`, `11632915`, `11650591`.
- full scan approval: `false`.

## 12. 2026-06-16 continuous improvement loop / runtime and OCR hold guards

section 11의 remaining 3건과 controls를 대상으로 `goal.md` 기반 continuous improvement loop를 실행했다. 이번 단계의 핵심은 “9건 run completeness”와 “runtime exception 여부”를 분리하고, OCR/title overpromotion을 public title 대신 candidate ledger/hold로 보존하는 것이다.

산출물:

- targeted input/result: `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_targeted_input.jsonl`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_targeted_result.json`
- targeted compare/audit: `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_targeted_compare.json`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_targeted_runtime_audit.json`
- runtime fix result/compare/audit: `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_runtime_fix_result.json`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_runtime_fix_compare.json`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_runtime_fix_audit.json`
- title mismatch fix result/compare/audit: `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_title_mismatch_fix_result.json`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_title_mismatch_fix_compare.json`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_title_mismatch_fix_audit.json`
- summary: `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_summary.json`, `out/judge3905_p0_seed_registry/judge3905_p0_continuous_loop_summary_ko.md`

코드 조치:

- `src/llm_batch/experts/deliberation.py`: `_rebuild_arbiter_user_prompt()`에서 discourse output을 복원해 `disc` NameError를 제거했다.
- `tools/audit_goal_test_run_contract.py`: `Traceback`, `NameError`, `Deliberation 오류`를 runtime log exception으로 스캔해 `NO-GO`로 분류한다.
- `src/llm_batch/candidate_audit.py`: `title_noisy_ocr` seed에서 direct image work title과 final public title이 충돌하면 official URL이 있어도 public `official_title`을 hold하는 `apply_judge_seed_title_image_mismatch_guard()`를 추가했다.
- `expert_main.py`: candidate audit field 생성 전에 새 guard를 실행한다.

targeted 9건 run:

- run id: `20260615_231925_533889`
- input/completed/flushed/pending/failed: `9/9/9/0/0`
- `image_post_count=9`, VLM/OCR semantic gate `READY`
- compare expected/result/compared: `9/9/9`, missing `0`
- after labels: `hold_unresolved=3`, `output_consistency_lint=2`, `safe_resolved=3`, `promotion_blocked=1`
- runtime audit: `NO-GO` because log has `Deliberation 오류`, `NameError`, `Traceback` on `11639284`.

focused fix reruns:

- `11639284` runtime fix run id `20260615_234526_746998`: input/completed/flushed/pending/failed `1/1/1/0/0`, runtime audit `GO`, compare `promotion_blocked`.
- `11650591` title mismatch fix run id `20260616_000415_830530`: input/completed/flushed/pending/failed `1/1/1/0/0`, runtime audit `GO`, compare `hold_unresolved`, public `official_title_after=null`, candidate count `3`.

post_id 판정:

- `11602367`: `wrong_relevance` semantic/manual review remains. current evidence is insufficient for safe official title promotion.
- `11632915`: public OCR title promotion is held as `hold_unresolved`; candidate/blocked title is preserved for review.
- `11650591`: 9건 run에서 wrong official title promotion was exposed; post-patch rerun holds public title unresolved while preserving candidates.
- `11639284`: Deliberation runtime bug fixed; precision/cross-media control remains `promotion_blocked`.

최종 gate:

- run integrity is per-run: targeted 9건 is historical `NO-GO`; two focused fix reruns are `GO`.
- semantic quality: `REVIEW-LOCKED`.
- full scan approval: `false`.
