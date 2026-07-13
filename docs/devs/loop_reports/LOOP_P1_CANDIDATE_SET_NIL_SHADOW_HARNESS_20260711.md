# P1 여러 후보·작품 없음 그림자 하네스 보고서

> 후속 최신 상태: P1 구조 정본은 v6로 갱신됐고, 제목 cap 6·serializer cap 24·전문가 후보 상태 cap 7곳의 잘림 진단은 completeness v4에서 검증됐다. 최신 경계와 산출물은 `LOOP_P1_CANDIDATE_GENERATION_COMPLETENESS_20260711.md`, `out/candidate_set_nil_shadow_harness_20260711/v6/`, `out/candidate_generation_completeness_harness_20260711/v4/`를 우선한다. 아래 v3 내용은 선행 CandidateSet/NIL 단계의 역사적 기록이다.

## 결론

P1은 기존 공개 결과에 손대지 않고 **여러 작품 후보와 ‘후보 중 정답 없음’을 함께 기록하는 구조**까지 구현·검증했다. Golden18 저장본에서 게시글 완전성·후보 묶음 무결성·공개 결과 무영향은 모두 `18/18 GO`다. 작품 후보 정답 9건은 확률 사건 후보 안에서 `9/9` 관측됐고, NIL 정답 원장 6행에는 공통 NIL 선택지가 `6/6` 존재했다. NIL은 전체 18행에 공통 선택지로 붙으므로 두 비율은 정확도 검사가 아니라 사건 공간 구조 검사다. 단일 정답을 만들 수 없는 3건은 `UNJUDGED`로 남겼다.

이 수치는 정확도 100%나 후보 재현율 100%가 아니다. 저장본의 후보 생성 완전성이 `UNKNOWN`이므로 후보 목록 재현율은 `NOT_EVALUABLE`, 후보/NIL 확률은 전부 `null`, 실제 선택 행동은 `NOT_EVALUATED`다. 실제 새 런타임은 `NOT_RUN`, 의미 품질은 `REVIEW-LOCKED`, 운영 전체 승인은 `full_scan_approval=false`다.

종합 판정은 `GO_SAVED_ARTIFACT_SHADOW_ONLY`다.

## 기능 설명

| 기능 | 하는 일 | 이번 단계의 안전 경계 |
| --- | --- | --- |
| 여러 작품 후보 묶음 (`CandidateSet`) | 한 작품을 너무 일찍 고르지 않고 가능한 작품들을 함께 보존한다. | 기존 공개 계약 밖의 frozen shadow에만 존재한다. |
| 후보 중 정답 없음 (`NIL`) | 작품 이야기가 아니거나 준비된 후보 중 정답이 없는 사건을 나타낸다. | 모든 사건 목록 끝에 정확히 한 번 들어간다. |
| 판단 보류 (`ABSTAIN`) | 검색 실패·후보 무결성 문제로 지금 답하지 않는 행동이다. | 정답 확률 사건에 넣지 않는다. |
| 비사건 약칭 (`UNLINKED_SURFACE`) | `아생갤` 같은 약칭을 보존하되 별도 작품으로 중복 계산하지 않는다. | 약칭은 확률 사건에서 제외하고 provenance로 남긴다. |
| 후보 생성 완전성 | 후보 목록이 전부인지, 잘렸는지, 모르는지 기록한다. | `UNKNOWN/TRUNCATED`이면 후보 재현율 계산을 금지한다. |
| 확률 그림자 | 향후 후보별 확률과 NIL 확률을 담는다. | 보정 전에는 값을 만들지 않고 모두 `null`로 둔다. |

## 실제 Golden18 결과

| 확인 항목 | 결과 | 해석 |
| --- | ---: | --- |
| 게시글 ID·순서·집합 | `18/18 GO` | 누락·추가·중복 없이 같은 저장본을 비교했다. |
| 후보 묶음 무결성 | `18/18 GO` | 후보 ID·두 종류 지문·원본 공개 판정 재현이 맞았다. |
| 작품 후보 정답의 사건 후보 내 관측 | `9/9` | 구조 검사는 통과했지만 재현율·정확도 퍼센트가 아니다. |
| NIL 정답 원장 행의 공통 선택지 | `6/6` | 사건 공간 구조 검사이며 NIL 선택 능력·정확도 검증은 아니다. |
| 단일 정답 미지정 | `3` | 복합 작품·미상 가설·이미지 단서를 억지 라벨로 만들지 않았다. |
| 작품 후보 사건 | `34` | 향후 후보별 확률을 계산할 사건이다. |
| 비사건 약칭 표면 | `13` | 보존하지만 확률 사건에는 넣지 않았다. |
| 후반 관측 표면 | `6` | 권위 원천이 아니어서 사건에서 제외했다. |
| 후보/NIL 확률 | `18/18 모두 null` | `NOT_AVAILABLE_UNCALIBRATED`다. |
| 선택된 라벨 | `18/18 null` | 기존 결과에 새 선택을 적용하지 않았다. |
| 그림자 행동 | `NOT_EVALUATED 18` | 실제 RESOLVE/NIL 선택을 하지 않았다. |
| 기존 공개 계약 | `18/18 불변` | title·URL·decision·gate state/evidence·trace·fingerprint·version·bypass가 그대로다. |

### `아생갤` 특수 사례

- `11694035`: `아카데미 생존 갤러리` 1개를 작품 후보 사건으로, `아생갤`은 비사건 약칭으로 보존했다.
- `11698880`: `아카데미 생존 갤러리`와 `가챠 중독자의 퓨전펑크 생활`을 서로 다른 작품 후보 사건으로, `아생갤`은 비사건 약칭으로 보존했다.
- `11663521`: 같은 작품명이 서로 다른 URL 두 개에 묶여 있어 두 후보 사건을 유지했으며, 정답 원장은 복합 작품 부분 보존이라 `UNJUDGED`다.

## 구현·하네스 계약

- `src/llm_batch/candidate_set_shadow.py`
  - frozen `CandidateOption`, `CandidateSet`, `SelectiveShadowDecision` 추가
  - 후보 ID·후보 정체성 지문·관측 지문·shadow 지문 자체 검증
  - 동일 URL의 제목/alias는 한 후보로 묶고, 동일 제목·서로 다른 URL은 별도 사건으로 유지
  - root/ledger 계약이 불완전하거나 서로 다르면 fail-close
  - malformed evidence·ID·boolean·확률 합·지문을 거절
- `src/llm_batch/candidate_audit.py`
  - 기존 `candidate_ledger` 내부에만 `candidate_set_shadow`를 부착
  - 계약 실패는 별도 unavailable schema로 기록하고 공개 결과는 바꾸지 않음
- `tools/run_candidate_set_nil_shadow_harness.py`
  - P0 v5 RunSpec 전체 재검증
  - P0 parent·Golden18 결과·기대 감사·P1 정답 원장·현재 구현 SHA 결속
  - 실제 `apply_candidate_audit_fields()` 부착 결과와 직접 생성 shadow의 동일성 확인
  - 게시글별 공개 계약 전후 hash 불변 확인
  - 기존 출력 덮어쓰기 거절

## 시험 결과

- P1 후보 계약·하네스 focused: `36 tests OK`
- candidate/P1 harness/completed-source/promotion/retrieval/P0 harness/publication 영향 회귀: `199 tests OK`
- py_compile: `PASS`
- P0 부모 RunSpec status: `GO`, row `18`, runtime `false`
- P1 v3 RunSpec status: `GO`, row `18`, runtime `NOT_RUN`
- Sol xhigh 독립 v3 코드·SHA 재실행 감사: blocker `0 / PASS`

세부 테스트 모듈과 게이트 결과는 `docs/devs/VERIFICATION_RESULTS.md`에 보존한다.

## 정확도 퍼센트로 넘어가기 전 남은 조건

1. 실제 후보 생성 지점에서 `COMPLETE/TRUNCATED/UNKNOWN`을 기록한다.
2. `COMPLETE` 표본으로 위험 유형별 후보 목록 재현율과 신뢰구간을 확인한다.
3. 개발·확률 보정·최종 동결 시험셋을 겹치지 않게 나눈다.
4. ECE·classwise Brier 또는 log loss·NIL PR·risk-coverage를 사전 고정 기준으로 측정한다.
5. 검색 실패 차단 위반 0, 기존 안전 게이트 비열화 0일 때만 실제 선택 적용을 검토한다.

## 정본 산출물

- RunSpec: `out/candidate_set_nil_shadow_harness_20260711/v3/run_spec.json`
- JSON 비교: `out/candidate_set_nil_shadow_harness_20260711/v3/before_after_comparison.json`
- 한국어 비교 보고서: `out/candidate_set_nil_shadow_harness_20260711/v3/before_after_comparison.md`
- 정답 원장: `docs/devs/p1_candidate_set_nil_golden18_label_ledger_20260711.json`
- 기능 중심 독자용 설명: `docs/devs/LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`

## 승인 경계

- active production read-only snapshot (`2026-07-11 16:52:52 KST`): input/completed/flushed/pending/failed `104502/553/542/11/0`, parallel `16/16`, `large_run_complete=false`, dashboard health `ok=true`. 이동 중인 진행 수치이며 P1 승인 근거가 아니다.
- runtime validation: `NOT_RUN`
- candidate-set recall: `NOT_EVALUABLE`
- probability: `NOT_AVAILABLE_UNCALIBRATED`
- semantic quality: `REVIEW-LOCKED`
- production: `full_scan_approval=false`
- 전체 goal: `ACTIVE / NOT_COMPLETE`
- Git durability: 신규 module/harness/tests/v3 artifacts는 아직 untracked라 clean clone/CI 재현성은 커밋 전까지 미확정
