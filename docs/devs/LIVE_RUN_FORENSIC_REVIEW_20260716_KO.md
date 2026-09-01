# 2026-07-16 `expert_main` 라이브 런 전수 감사 리뷰

## 1. 결론과 게이트

관찰 대상은 `20260715_143806_848671` 런이다. 입력은 `104,502`건이며, 이 문서의 수치는 런이 계속 진행 중인 시점의 스냅샷이다. 최신 관찰(`2026-07-16 01:37:35 KST`)에서 `checkpoint/publication journal=1,260`, ordered result `1,248`건을 구조적으로 대조했지만, 전체 입력의 최종 품질을 승인한 것은 아니다.

현재 게이트는 다음과 같다.

| 게이트 | 상태 | 근거 |
|---|---|---|
| runtime completion | `NO-GO` | `pending`, `COMPLETED_COUNT_MISMATCH`, terminal artifact 미확정 |
| semantic approval | `REVIEW-LOCKED` | semantic coverage audit가 browser/direct visual 및 고위험 semantic 항목을 잠금 |
| publication contract convergence | 현재 관찰 `GO` | violations `0`; 단, 런 종료 전 상태 |
| full-run approval | `NO-GO` | 104,502건 중 약 1.2%만 처리 |
| dashboard title mapping | 현재 committed snapshot `0 mismatch` | journal과 API 행의 현재 필드 대조 결과 |

핵심 결론은 “대시보드의 현재 title 매핑 누락은 확인되지 않았지만, 의미 판정에는 확정 비소설 publish 1건과 작품 오인 고위험 1건이 있으며, 대시보드가 durable publication ledger의 정본 read model이 아닌 구조적 위험이 있다”이다.

## 2. 관찰 범위와 증거

- 실행: `expert_main.py --parallel 16 --vlm on --ocr on --slang-db on`
- `requested/effective/active parallel`: `16/16/16`
- dashboard: embedded, `http://127.0.0.1:8082`
- VLM/OCR: ON; 이미지 입력 약 `55,259`건
- `failed=0`; 로그상 `ReadTimeout` 및 LLM 재시도는 있었음
- Slang work artifact와 promotion/writeback은 미완료
- 런 프로세스와 기존 `expert_main.py` 변경은 조사 중 중지·수정하지 않음

주요 산출물:

- manifest: `out/expert_result_20260715_143806_848671_manifest.json`
- ordered result: `out/expert_result_20260715_143806_848671.json`
- checkpoint: `out/expert_result_20260715_143806_848671_checkpoint.jsonl`
- pending: `out/expert_result_20260715_143806_848671_pending_snapshot.json`
- publication journal: `out/publication_commit_journals/aca96a362b90a1425befa01b2325200c51a27a34cac0376ebda5ef54a3b95655.jsonl`
- run health: `/tmp/live_run_health_20260716_final.json`
- semantic coverage: `/tmp/live_semantic_coverage_20260716_final.json`, `/tmp/live_semantic_coverage_20260716_final.md`

## 3. 수량 및 정합성 감사

최신 스냅샷(`2026-07-16 01:37:35 KST`)은 다음과 같다.

| 자료 | 건수 | 해석 |
|---|---:|---|
| dashboard `done_count` | 1,260 | 진행 이벤트 기준 |
| checkpoint | 1,260 | completed 기록 |
| publication journal | 1,260 | commit 기록 |
| ordered result JSON | 1,248 | flush된 prefix |
| pending | 12 | 진행 중/ordered gap 인접 상태 |
| failed | 0 | 실행 실패 기록 없음 |

`result JSON`만 읽으면 journal보다 9건이 빠진다. 이는 현재 런의 ordered flush gap이며, 런 중간의 정상적인 materialized-view 차이일 수 있지만 최종 산출물로 승인할 수 없는 상태다. 직전 health audit도 `IN_PROGRESS/ordered_flush_gap_in_progress`로 판정했다. 읽기 중 파일이 갱신될 수 있으므로 각 파일을 단일 시점 정본으로 섞어 사용하면 안 된다.

현재 API `/api/results`의 committed page와 publication journal을 `post_id`, `title`, `official_title`, `is_relevant`, `work_resolution`, `topicality`, `relevance_scope`로 대조한 범위에서는 mismatch `0`이었다. 이는 현재 스냅샷의 필드 일치 결과이지, semantic 정답 보증이나 런 전체 보증이 아니다.

## 4. 확정·고위험 semantic findings

### P0 — 확정 비소설 프로그램을 소설로 publish: `11684372`

- 원문 제목: `밀리언클래스 공지보고 웃음`
- 본문: `대학원생이 시간이 남아..?`
- 최종: `official_title=밀리언 클래스`, `is_novel_related=true`, `is_resolved_work_discussion=true`, `publish=true`
- OCR: `APPLICATION GUIDE`, 모집 인원·학생 대상·신청 자격·모집 기간·강의 장소·`메타크래프트`
- visual summary: 노벨피아의 교육·모집 프로그램 공지
- 결과 내부에도 “소설 제목이 아닌 이벤트/프로그램”, “웹소설 작품이 아닌 플랫폼 메타 정보”라는 critical 반론이 있음
- 그런데 `direct_image_work_surface_bridge`, `ocr_catalog_official_title`를 근거로 publish했고 `non_novel_media_title_kept_by_specific_work_alias`, `direct_image_suspect_preserved` 플래그가 남아 있음

판정: `FP_NONWORK_AS_NOVEL / REJECT·REPROCESS` 확정. 이미지에 제목이 보인다는 사실만으로 소설 작품 표면으로 승격했으며, 프로그램·모집·교육 공지의 media type veto가 publish gate보다 뒤에 있다.

### P1 — 직접 OCR 작품명 충돌 상태에서 최종 title을 publish: `11718099`

- 원문 제목/본문: `빌환 표지변경됨` / `시엘이랑 세냐 빼고 아니스티나랑 매르만 있어도 된다는 말은 ㄴㄴ`
- 최종: `빌어먹을 환생`, `resolved/publish`, URL 없음
- 경쟁 후보: `불어먹을 황제`
- 이미지 OCR: `불어먹을 황제, MUNPIA, 목마 퓨전판타지 소설`
- 검색: 4건 모두 degraded zero, accepted `0`
- flags: `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias`

본문의 캐릭터명과 `빌환` 약칭이 최종 작품을 지지할 가능성도 있으므로, 현재 자료만으로 `불어먹을 황제`로 잘못 확정됐다고 단정하지 않는다. 정확한 분류는 `WRONG_WORK_RISK / EVIDENCE_CONFLICT / REVIEW-LOCKED`다. 직접 이미지를 확인하기 전에는 최종 title을 자동 교체하지 않되, 충돌을 해소하지 않은 publish는 잠가야 한다. “reason에 충돌을 기록했다”는 것은 충돌을 차단했다는 뜻이 아니다.

### P1 — intent 필드가 cross-media인데 작품명 publish는 유지된 사례: `11684403`

- 원문 제목: `아니 게임하다 왓는데 판초법사 ㅇㄷ감`
- 본문: `우우우`
- 최종: `판초우의의 마법사`, `resolved/publish`
- identity: `primary_subject_type=cross_media`, 주제 설명은 비소설 타 매체/게임 담론이라고 명시
- 동시에 `is_novel_related=true`, `discussion_type=general`, official detail anchor로 작품명을 확정
- semantic coverage audit의 `blocked_intent_resolved_title` 대상

Pro 독립 검토는 “게임하다 왔는데”를 시간적 배경으로 보고 `판초법사`가 작품 질문의 대상일 가능성이 높다고 판단했다. 따라서 title publish 자체는 유지 가능하지만 `primary_subject_type=cross_media`가 잘못된 identity 필드일 가능성이 높다. 분류는 `IDENTITY_FIELD_MISCLASSIFICATION / REVIEW-LOCKED`로 두고, 원문 주절·대상 span을 재판정한 뒤 `novel/work`로 교정할지 결정한다.

### 자동 FN으로 세지 않은 보류 사례: `아생갤`

다음은 title이 표시되지 않은 것이 곧 누락이라고 볼 수 없는 hold다.

- `11694035`: `아생갤` community-only 후보, 공식 근거 없음 → `candidate_only` 유지가 타당
- `11698880`: `아카데미 생존 갤러리`와 `가챠 중독자의 퓨전펑크 생활` 경쟁 후보, conflict unresolved → 자동 확정 금지 타당
- `11698894`: 작품 후보는 있으나 row dialogue missing → candidate-only 유지 필요
- `11694023`: off-topic/noise, OCR은 Hatsune Miku/Vocaloid → 작품명 복구 대상 아님
- 양성 대조군 `11714907`, `11716448`: `아카데미 생존 갤러리`, 공식 Novelpia URL과 캐릭터/플롯 근거로 정상 publish

다만 Pro 독립 검토는 `11698880`을 제목의 `아생갤`이 주대상이고 `가챠펑크`가 비교·secondary mention일 가능성이 높은 `likely FN`, `11698894`를 `클레어`와 공식 작품 근거가 결합된 `likely FN`으로 올렸다. 이 둘은 원문 이미지·attribution을 확인하기 전까지 확정 FN으로 집계하지 않고 `REVIEW-LOCKED`로 별도 재심사한다.

따라서 `아생갤`은 현실 DC 갤러리명으로 자동 해석해서도 안 되고, 반대로 단순 표면만으로 소설로 자동 확정해서도 안 된다. explicit alias relation, specific-work target, 공식/커뮤니티 근거, 경쟁 작품 근거를 함께 유지해야 한다.

## 5. semantic coverage 및 댓글 증거 잠금

`build_semantic_coverage_audit.py` 최종 관찰(`2026-07-16 01:37 KST`, 결과 1,245건) 기준 다음 항목이 확인됐다.

- 이미지 evidence catalog: `734/734` 존재
- browser/direct visual artifact missing: `734`
- catalog unreviewable: `8` (`11716482`, `11714874`, `11700488`, `11698858`, `11692459`, `11689254`, `11687655`, `11687624`)
- `comment_context_resolution_without_attribution`: `1` (`11681172`)
- unverified author signal이 resolution에 사용: `5` (`11714891`, `11708470`, `11703658`, `11686018`, `11682791`)
- 댓글 대화 맥락 누락: `47`

이는 catalog가 존재한다는 뜻과 사람이 재검토 가능한 직접 visual evidence가 있다는 뜻을 분리한다. 이미지/OCR이 publish 근거이면 source URL, OCR text, visual summary, title/author, promotion eligibility와 실제 browser/direct artifact를 함께 보존해야 한다.

## 6. dashboard/API/read-model 감사

### 현재 snapshot의 표시값

현재 `/api/results`와 journal의 작품명·판정 필드 mismatch는 `0`이다. 따라서 “소설로 맞게 판정됐는데 dashboard에 title이 누락된 사례”는 관찰된 committed snapshot에서는 확인되지 않았다.

### 구조적 stale/read-model 위험

코드상 `post_complete` 이벤트가 durable commit보다 먼저 방출되고, monitor summary가 publication receipt/WAL의 `decision_id`, `outcome`, `publish_allowed`, `input_index`, `publication_scope_id`, receipt hash를 보존하지 않는다. `/api/results` 및 detail도 journal/receipt를 정본으로 조회하지 않는다. UI는 `work_resolution=resolved` 또는 identity resolved이면 `official_title`을 표시하며, `publish_allowed`나 WAL outcome을 확인하지 않는다.

따라서 현재 mismatch `0`과 별개로 commit reject, replay, stale event가 발생하면 dashboard가 시도 결과나 잘못된 작품명을 계속 표시할 수 있다. monitor의 중복 키가 `post_id` 중심이고, 표시 순서도 authoritative `input_index`가 아닌 completion 도착 순서라는 점도 함께 수정 대상이다.

### dashboard 성능

`/api/runs`는 과거 final result 파일을 전체 read/`json.loads`해 이력 건수를 계산하며, 저장소의 대형 과거 result 파일 때문에 timeout 위험이 확인됐다. `/api/results`도 summary 보강 경로에서 현재 result JSON을 동기 파싱한다. 현재 title mismatch는 없지만, 대시보드 자체가 진행 상황을 안정적으로 보여주지 못하는 P1 운영 결함이다.

## 7. GPT Pro 독립 검토

호출: `ask-chatgpt-pro`, lane `review`, task-id `live-run-forensic-dashboard-review-20260716`, `GPT-5.6 Sol + Pro`.

### Pro verdict

GPT Pro는 최종 게이트를 `NO-GO`로 판정했다. `dashboard mismatch 0`은 현재 committed snapshot과 선택 필드에만 적용되며 전체 104,502건, terminal artifact, API 안정성, 모든 semantic 필드의 정합성을 뜻하지 않는다는 점에 동의했다.

### 로컬 결과와의 대조

- `11684372`: Pro가 노벨피아의 공식 프로그램·특강 근거를 들어 확정 비소설 publish FP로 확인했다. 로컬 `FP_NONWORK_AS_NOVEL / REJECT·REPROCESS`와 일치한다.
- `11718099`: Pro는 `빌환`, 시엘·세냐·아니스·메르 및 작가 근거가 `빌어먹을 환생`을 지지할 가능성이 높다고 판단했다. 따라서 `불어먹을 황제` wrong-work 확정이 아니라 직접 OCR/시각 증거 충돌로 분류했다. 로컬 분류를 `WRONG_WORK_RISK / REVIEW-LOCKED`로 정정했다.
- `11684403`: Pro는 `게임하다 왔는데`가 주제 자체가 아니라 시간적 배경일 수 있고 `판초법사` 작품 해소는 타당할 가능성이 높다고 봤다. 로컬의 cross-media publish FP 의심을 `IDENTITY_FIELD_MISCLASSIFICATION / REVIEW-LOCKED`로 낮추고 title publish 유지 가능성을 반영했다.
- `11698880`, `11698894`: Pro는 각각 likely FN 후보로 보았지만 직접 artifact가 부족하므로 확정 FN으로 세지 않았다.

### Pro가 추가한 release predicate

Pro는 `non-work indicator`, `primary_subject_type != novel/work`, 미해결 OCR/final title 충돌, `llm_only + official_url 없음 + search accepted=0`, direct image artifact missing을 자동 publish 금지 또는 quarantine 조건으로 제안했다. 또한 `depicted_title`과 `discussed_work`를 분리하고, dashboard에 `snapshot_id`, `journal_offset`, `checkpoint_committed`, `ordered_result_count`, `pending/inflight/failed`, `last_flush_at`, `semantic_approval`을 함께 표시할 것을 제안했다.

Pro 응답의 외부 확인 링크: [노벨피아 프로그램 근거](https://novelpia.com/event/promotion/million_class_new_novel), [문피아 빌어먹을 환생](https://www.munpia.com/novel/detail/222360), [문피아 판초우의의 마법사](https://www.munpia.com/novel/detail/530500), [DCInside 원문 11698880](https://m.dcinside.com/board/genrenovel/11698880), [노벨피아 아카데미 생존 갤러리](https://novelpia.com/novel/380218).

Pro 답변은 외부 조언으로 취급했으며, material claim은 현재 결과 row·audit artifact와 다시 대조했다. Pro 호출은 `GPT-5.6 Sol + Pro`, `review` lane, task-id `live-run-forensic-dashboard-review-20260716`로 완료됐다.

## 8. 권고 조치 및 최종 승인 조건

우선순위는 다음과 같다.

1. `11684372`를 확정 reject/reprocess queue에 넣고, `program/event/recruitment/education/announcement/platform metadata` media-type veto를 promotion gate에 추가한다. `official_title_exists`와 OCR title만으로 publish하지 않는다.
2. `11718099`처럼 direct OCR title/author/platform이 final title과 충돌하고 독립 검색 근거가 없으면 title을 자동 교체하지 말고 `REVIEW-LOCKED`로 닫는다. `depicted_title`과 `discussed_work`를 분리 보존한다.
3. `primary_subject_type=cross_media`와 novel publish가 동시에 나오면 `cross_media_intent_conflict`를 hard review gate로 두되, `게임하다 왔는데`처럼 부사절일 가능성은 원문 주절 분석 후 identity만 교정할 수 있게 한다.
4. dashboard summary를 WAL/receipt 기반 read model로 바꾸고 `decision_id`, `outcome`, `publish_allowed`, `input_index`, `scope_id`, receipt hash를 노출한다. commit 후에만 publish title을 표시하거나, commit 전 행은 명시적으로 tentative로 표시한다.
5. `/api/runs`는 result JSON 전체 파싱 대신 manifest/sidecar count를 사용한다. `/api/results`도 매 요청 동기 전체 파일 파싱 대신 indexed/sidecar projection을 사용한다.
6. 런 종료 후 immutable snapshot을 만들고 `input scope = checkpoint completed ∪ pending ∪ failed = result rows = publication receipts`를 exact-once로 대조한다. 그 전에는 ordered gap을 최종 누락으로 확정하지 않는다.
7. browser/direct visual, 댓글 attribution/dialogue, search degraded row를 닫기 전까지 semantic approval은 `REVIEW-LOCKED`로 유지한다.
8. 전체 104,502건 완료 후 random baseline, high-risk oversample, image/OCR conflict, alias ambiguity, recommendation/context-only를 분리해 최종 report를 다시 생성한다.

## 9. 문서/checklist 반영 상태

- 이 보고서: 작성 중인 live snapshot 기준 `REVIEW-LOCKED`
- `docs/devs/CHECKLIST.md`: 본 보고서 경로와 현재 런의 full-scan 미승인 상태를 추가 기록해야 함
- 런 종료 전에는 `GO`, `full_scan_approval=true`, 전체 정확도 수치를 선언하지 않음
