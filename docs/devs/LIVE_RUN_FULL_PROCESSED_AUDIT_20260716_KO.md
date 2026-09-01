# `expert_main` 라이브 런 처리행 전수 회계·의미 검토 보고서

## 결론

질문에 대한 답은 **“처리된 행은 하나도 빠뜨리지 않고 구조·회계 검사를 돌렸지만, 1,000여 건 모두를 독립적인 사람 수준의 의미 정답 판정까지 완료했다고 말할 수는 없다”**이다.

따라서 현재 게이트는 다음과 같다.

| 게이트 | 상태 | 의미 |
|---|---|---|
| 처리행 ID/중복/집합 회계 | `PASS` (rolling snapshot) | result, checkpoint, journal, pending을 행 단위로 대조했으며 중복·orphan은 관찰되지 않음 |
| ordered flush | `IN_PROGRESS` | 런이 살아 있고 ordered result와 journal 사이에 진행 중 gap이 있음 |
| semantic coverage | `REVIEW-LOCKED` | browser/direct visual, 검색 저하, 댓글 대화·attribution 한계가 남음 |
| dashboard 표시 정합성 | `조건부 PASS` | 공통 표시 필드 mismatch는 0이지만 evidence·publish gate 필드는 API에 노출되지 않음 |
| full-run semantic approval | `NO-GO` | 전체 입력 104,502건은 아직 완료되지 않았고 독립 의미 재판정 전수도 아님 |

이 문서는 런을 중지하거나 `expert_main.py`와 기존 dirty 변경을 수정하지 않고 작성했다.

## 1. 범위와 “전수”의 정확한 정의

대상 런은 `20260715_143806_848671`이며 `--parallel 16 --vlm on --ocr on --slang-db on`으로 실행 중이다. 입력 모집단은 unique post `104,502`건이다.

이번 검토의 전수 범위는 다음처럼 분리한다.

1. **구조 전수**: 관찰 시점의 모든 ordered result 행에 대해 `post_id`, 중복, promotion 상태·공식 제목, `is_relevant`, `is_novel_related`, title/work resolution, 주제 유형, 검색 상태, 이미지·댓글 증거, flags를 순회했다.
2. **회계 전수**: checkpoint, publication journal/WAL, ordered result, pending, live dashboard ID 집합을 대조했다.
3. **의미 검수 큐**: 비소설 오채택, OCR/최종 제목 충돌, cross-media, 검색·댓글·이미지 증거 누락, candidate-only FN 후보를 분리해 전문가가 재검토했다.
4. **독립 의미 전수**: 모든 입력 104,502건에 대해 사람이 직접 원문·이미지·공식 근거를 보고 정답을 확정한 것은 아니다. 이 항목은 아직 `NOT_DONE`이다.

## 2. 동일 런의 rolling snapshot

런이 계속 쓰이고 있어 아래 수치를 한 개의 원자적 snapshot으로 합치면 안 된다. 각 행은 관찰 시각과 분모를 함께 기록한다.

| 관찰 시각(KST) | ordered result | checkpoint/journal | pending | dashboard | 해석 |
|---|---:|---:|---:|---:|---|
| 03:14:55 | 1,450 | 1,464 | 14 | 1,465 | Data Analytics artifact 기준. result 외 journal 행은 pending과 일치 |
| 03:18:16 | 1,455 | 1,466 | 11 | - | 병렬 회계 전문가 기준. `result ∪ pending = journal = checkpoint` |

03:18:16 기준으로 확인된 회계 결과는 다음과 같다.

- `ordered result` 1,455건, 고유 `post_id` 1,455건, 중복 0.
- checkpoint/journal 1,466건, 고유 ID 중복 0.
- pending 11건, result와의 교집합 0.
- `ordered result ∪ pending = checkpoint = journal`이며 집합 차이 0.
- ordered result는 `input_index 1..1455` prefix로 관찰됐고, pending은 아직 뒤쪽 진행행이다.
- failed 0건이나, 프로세스가 살아 있고 `terminal_artifacts_finalized=false`, `large_run_complete=false`이므로 최종 완료로 볼 수 없다.
- 현재 처리 범위는 전체 unique post의 약 `1.40%`다.

### 보고서 작성 직전 health readback

`2026-07-16 03:24:50 KST`에 다시 읽은 health artifact는 `result=1,456`, `checkpoint=1,477`, `pending=21`, `failed=0`이었다. `result_rows=flushed_count`, `checkpoint_completed=manifest_completed`, `pending=completed-flushed` 정합성은 맞았지만 `ordered_flush_gap_in_progress`이며 `approval_ready=false`다. 이 readback은 위 03:18:16 전문가 snapshot을 대체하지 않고 더 늦은 rolling 상태로만 기록한다.

같은 health readback에서 `search_evidence=REVIEW`였다. row search health가 있는 1,193행 중 `SEARCH_DEGRADED` 760행, `ok` 433행이었고, publication contract는 위반 0으로 `GO`였지만 이는 semantic 승인이나 전체 런 완료를 의미하지 않는다.

## 3. 처리행 전체 구조 집계

03:18:16에 독립 전문가가 ordered result 1,455행을 다시 계산한 값이다.

| 항목 | 건수 |
|---|---:|
| `is_relevant=true` | 482 |
| `is_novel_related=true` | 1,381 |
| `is_novel_related=false` | 69 |
| `title_resolution_state=resolved` | 185 |
| `work_resolution=resolved` | 185 |
| `work_resolution=multi_work` | 15 |
| `promotion=publish` | 185 |
| `promotion=candidate_only` | 776 |
| `promotion=reject` | 489 |
| publish + `is_novel_related=false` | 0 |
| publish + 제목 없음 | 0 |
| publish + `primary_subject_type=cross_media` | 1 (`11684403`) |
| publish + 비소설 media flag의 엄격한 predicate | 3 (`11705257`, `11703669`, `11684372`) |
| publish + 비작품 주제 불일치 전체 | 23 |
| 보수적 candidate-only FN 후보 | 101 |

`publish + is_novel_related=false = 0`은 모델 자기 라벨과의 모순이 없다는 뜻일 뿐 실제 비소설 여부의 정답 증명이 아니다. 그래서 `11684372`처럼 모델이 `true`로 잘못 라벨링한 경우를 별도 의미 큐로 검사했다.

## 4. 확정·고위험 판정

### P0 — 비소설 프로그램을 작품으로 채택한 확정 후보: `11684372`

- 입력: `밀리언클래스 공지보고 웃음`
- publish 제목: `밀리언 클래스`
- 이미지/OCR: `APPLICATION GUIDE`, 학생 대상·신청 자격·모집 기간·강의 장소·`메타크래프트` 등 프로그램/모집 공지 표면
- 결과에는 direct image work surface와 OCR title이 근거로 남았지만, 동시에 `non_novel_media_title_kept_by_specific_work_alias`, `direct_image_suspect_preserved` 경고도 남음

판정: **`FP_NONWORK_AS_NOVEL / REJECT·REPROCESS`**. “이미지에 제목이 있다”를 “웹소설 작품 제목이다”로 승격한 사례로 본다.

### P1 — 최종 제목과 OCR 표면 충돌: `11718099`

`빌환 표지변경됨`을 `빌어먹을 환생`으로 publish했지만 OCR은 `불어먹을 황제`로 읽혔고 search는 degraded/accepted 0이다. 본문 약칭·캐릭터 근거가 `빌어먹을 환생`을 지지할 가능성도 있어 wrong-work로 확정하지 않고 **`EVIDENCE_CONFLICT / REVIEW-LOCKED`**로 둔다.

### P1 — cross-media identity 충돌: `11684403`

`primary_subject_type=cross_media`인데 작품명이 publish됐다. 독립 검토에서는 “게임하다 왔는데”가 작품 대상이 아니라 시간적 배경일 가능성을 지적했다. 따라서 제목 오채택 확정이 아니라 **identity field misclassification 후보**로 유지하고 원문 주절·대상 span을 재판정한다.

### P1 — 이미지·작품 유형 충돌: `11676330`, `11681172`

- `11676330`: `전생검왕`으로 publish됐지만 이미지 표면에 `咆哮`, 애니/만화 계열 단서가 있고 정식 제목이 불완전하다. non-novel/cross-media 고위험.
- `11681172`: `헌터갤러리의 국가권력급 기계공주`로 publish됐으나 OCR 제목과 최종 제목이 충돌하고 댓글 대화 맥락도 부족하다. **hold**가 필요하다.

### 오경고와 실제 오채택을 구분해야 하는 사례

`11713220`, `11705257`, `11703669`, `11685994` 등은 비소설 경고 flag가 있으나 구체 alias·작품 detail·이미지 작품 표면이 남아 있어 flag만으로 FP 확정하면 안 된다. 특히 `아생갤`은 현실 DC 갤러리 표면으로만 단정하지 않고 explicit alias, specific-work target, 공식/커뮤니티 근거, 경쟁 작품 근거를 함께 봐야 한다.

반대로 candidate-only 중 보수적 FN 후보 101건은 작품 근거가 있어도 title/work resolution이 unresolved인 큐다. 확정 FN이 아니라 런 종료 후 별도 재심사 대상으로 둔다. `11698880`, `11698894`는 `아생갤` 경쟁 후보·댓글 맥락 문제 때문에 대표 REVIEW-LOCKED 사례다.

## 5. 이미지·댓글·검색 evidence 전수 coverage

03:18:16 전문가 snapshot의 ordered result 1,455행 분모 기준이다.

| 증거 항목 | 결과 | 게이트 해석 |
|---|---:|---|
| image-dependent | 854행 | image catalog 854/854 존재 |
| catalog unreviewable/source URL 누락 | 8행/8 item | `11687624`, `11687655`, `11689254`, `11692459`, `11698858`, `11700488`, `11714874`, `11716482` |
| browser/direct visual artifact | 0/854 | 이미지 truth를 직접 시각 확인할 수 없음 |
| OCR conflict flag | 17행 | 최종 title과 OCR 충돌 큐 |
| 명시 OCR title ≠ 최종 title | 22행 | 직접 이미지 재확인 필요 |
| comment-dependent | 1,140행 | metadata는 모두 존재 |
| comment dialogue context 누락 | 49행 | 댓글 기반 resolution 재검토 필요 |
| `SEARCH_DEGRADED` | 744행 | 검색 evidence gate `REVIEW` |
| search health 자체 누락 | 279행 | search-dependent 중 93행은 health도 없음 |
| degraded + accepted 0 | 85행 | 자동 publish 승인 금지 후보 |
| resolved title + valid detail URL 없음 | 27행 | 공식 근거 재확인 필요 |
| structured `identity.evidence` | 0/1,455 | reason과 별도 구조 evidence의 parity 부족 |
| `promotion_gate_evidence` | 1,455/1,455 | gate trace는 존재하나 semantic truth와 동일하지 않음 |

browser artifact가 0이므로 VLM/OCR catalog가 존재해도 실제 이미지 로딩·crop·placeholder·표시 위치·동일 artifact 여부는 검증되지 않는다.

## 6. 웹 대시보드·ledger 누락/오표시 검토

### 현재 관찰에서 확인된 것

03:13:54~03:14:06 API/journal/checkpoint 감사 window에서는 live API 1,458행, journal 1,458행, checkpoint 1,458행이었고, journal과 `result ∪ pending` 집합이 일치했다. 공통 행의 `title`, `official_title`, `is_relevant`, `work_resolution`, `topicality`, `relevance_scope`, `primary_work`, `consistency_flags` mismatch는 0이었다.

따라서 **관찰된 공통 snapshot에서 “소설 판정은 맞는데 dashboard에 소설명이 누락된” 필드 mismatch는 확인되지 않았다.**

### 그러나 dashboard가 완전한 정본은 아님

API는 `is_novel_related`, `publish_allowed`, `primary_subject_type`, `primary_subject_text`, evidence ID를 노출하지 않는다. authoritative result 기준 evidence ID가 있는 1,254행도 dashboard projection에서 evidence 식별 정보가 보이지 않았다. 즉 제목 표시가 맞아도 “왜 publish됐는지”, “소설/비소설 gate가 통과됐는지”, “이미지·검색 근거가 무엇인지”를 dashboard에서 전수 검토할 수 없다.

또한 `post_complete`가 durable journal commit보다 먼저 monitor에 들어오는 순서, offset 기반 page, snapshot token/generation 부재 때문에 live race에서 잠깐의 누락·stale 표시가 가능하다. 역사 조회가 flushed result만 읽으면 pending 행을 누락할 수 있다.

성능 전문가가 측정한 운영 위험도 있다.

- `/api/runs`: 15초 client timeout 관찰
- `/api/results?limit=1000`: 약 0.167초
- post detail: 약 1.726초
- 대형 result/log 전체 parse와 동기 파일 I/O가 event loop를 막을 가능성

따라서 dashboard title mismatch `0`은 **현재 read-model의 선택 필드 정합성**이지 semantic 승인·전체 런 완료 증명이 아니다.

## 7. 전문가·GPT Pro·Data Analytics 결과

### 병렬 전문가

읽기 전용 전문가 6개 lane을 요청했고, 현재 5개가 완료됐다(회계/집합, 구조 predicate, evidence coverage, dashboard/API, 문서·gate QA). 완료 전문가들은 모두 `NO-GO / REVIEW-LOCKED / full_scan_approval=false`에 합의했다. 남은 title/alias lane은 결과에 영향을 주지 않으며 계속 대기 중이다.

### GPT Pro

이번 fresh Pro 호출은 `agbrowse preflight`에서 **`required ChatGPT capabilities are not confirmed ok: response-streaming=warn`**으로 fail-closed 됐다. 따라서 새 답변을 받았다고 가장하지 않는다. 이전 같은 repository의 GPT-5.6 Sol + Pro `review` 결과는 보조 의견으로만 재사용했으며, 그 결론도 `NO-GO`였고 `11684372` 확정 FP, `11718099` evidence conflict, `11684403` identity misclassification 가능성, `11698880/11698894` likely FN 후보라는 현재 로컬 결과와 대체로 일치한다.

### Data Analytics

03:14:55 snapshot을 대상으로 report artifact를 `validate_artifact=PASS`, `render_artifact=PASS`로 처리했다. 산출물은 [Data Analytics artifact JSON](./LIVE_RUN_FULL_PROCESSED_DATA_ANALYTICS_ARTIFACT_20260716.json)이며, promotion 분포와 고위험 큐를 별도 dataset으로 보존한다. 이 artifact는 rolling snapshot이므로 런 종료 후 재생성해야 한다.

## 8. 승인 조건과 다음 조치

런 종료 후 다음을 모두 만족해야 full-scan approval을 검토한다.

1. `terminal_artifacts_finalized=true`, `large_run_complete=true`, `pending=0`, `failed=0`.
2. `input scope = checkpoint completed ∪ pending ∪ failed = result rows = publication receipts` exact-set 대조, duplicate/orphan/index hole `0`.
3. 모든 수치에 `numerator / denominator / as-of / source artifact`를 붙인 immutable report snapshot 생성.
4. browser/direct visual artifact와 OCR conflict 직접 확인, 댓글 dialogue/author attribution, search degraded/missing health 큐를 닫음.
5. publish가 `non-work indicator`, `cross-media intent`, OCR/final title conflict, `llm_only + URL 없음 + accepted=0`을 통과하지 못하도록 quarantine.
6. dashboard read-model에 `snapshot_id`, `journal_offset`, `input_index`, `publish_allowed`, primary subject, flags, evidence IDs를 노출.
7. candidate-only 101건과 high-risk oversample을 확정 FN/정상으로 각각 판정하고, 그 결과를 전체 정확도로 외삽하지 않음.

## 산출물

- [기존 live 구조·Pro 보고서](./LIVE_RUN_FORENSIC_REVIEW_20260716_KO.md)
- [Data Analytics artifact](./LIVE_RUN_FULL_PROCESSED_DATA_ANALYTICS_ARTIFACT_20260716.json)
- [run manifest](/home/kimjang/llm_novel_dc_coommunity_parser/out/expert_result_20260715_143806_848671_manifest.json)
- [ordered result](/home/kimjang/llm_novel_dc_coommunity_parser/out/expert_result_20260715_143806_848671.json)
- [checkpoint](/home/kimjang/llm_novel_dc_coommunity_parser/out/expert_result_20260715_143806_848671_checkpoint.jsonl)
- [pending snapshot](/home/kimjang/llm_novel_dc_coommunity_parser/out/expert_result_20260715_143806_848671_pending_snapshot.json)
- [publication journal](/home/kimjang/llm_novel_dc_coommunity_parser/out/publication_commit_journals/aca96a362b90a1425befa01b2325200c51a27a34cac0376ebda5ef54a3b95655.jsonl)
