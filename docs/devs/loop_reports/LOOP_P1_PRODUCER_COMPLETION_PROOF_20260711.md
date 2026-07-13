# P1 검색·문서 가져오기 완료 증명 v6 보고서

## 한눈에 보는 결론

후보를 몇 개 보존했는지만 기록하던 구조에 **검색과 문서 가져오기가 애초에 계획대로 끝났는지 증명하는 기능**을 추가했다.

- 실행 전에 고정한 정상 search+fetch 계획 한 사례만 `COMPLETE`가 됐다.
- 원 실행 영수증·해시에 결합되지 않은 cache replay, 계획된 fetch 영수증 누락, 저하·오류 검색, 검색 조기 종료 네 사례는 `UNKNOWN`으로 닫혔다.
- 검색 결과 11개를 관측하고 10개만 보존한 사례는 producer `TRUNCATED`, 최종 CandidateSet `UNKNOWN`이 됐다.
- 계획·영수증·결과 지문을 바꿔 거짓 `COMPLETE`를 만드는 사례는 `0`이었다.
- `COMPLETE`는 **미리 정한 제한 범위를 빠짐없이 수행했다**는 뜻이다. 웹 전체 후보를 모두 찾았다는 뜻도, 모델이 정답이라는 뜻도 아니다.
- Golden18은 이 기능 추가 전 저장본이므로 producer 영수증이 없다. 따라서 실제 18행은 계속 `UNKNOWN`, 후보 재현율은 `NOT_EVALUABLE`이다.
- 실제 새 LLM/MCP 실행은 `NOT_RUN`, 확률은 `null`, 의미 품질은 `REVIEW-LOCKED`, 전체 승인은 `full_scan_approval=false`다.

## 새 기능은 무엇을 하는가

| 기능 | 쉬운 설명 | 실패하면 |
| --- | --- | --- |
| 실행 계획 영수증 | 검색어 원문 대신 입력 해시와 실행하기로 한 search/fetch 작업 수를 실행 전에 고정한다. | 나중에 일부 작업을 빼고도 모두 끝났다고 주장할 수 있다. |
| 작업 결과 영수증 | 각 작업의 시작·종료, upstream 관측 수, 실제 보존 수, cache provenance, 저하·throttle·오류와 결과 해시를 기록한다. | 결과 손실이나 검색 장애를 정상 완료로 오인할 수 있다. |
| 계획-결과 결합 증명 | 계획한 작업과 실제 영수증이 정확히 일치하는지 재계산한다. | 누락·중복·다른 실행의 영수증을 섞어 거짓 완료를 만들 수 있다. |
| CandidateSet 연결 | producer 증명이 정상이고 로컬 cap 장부도 손실이 없을 때만 평가 준비 상태로 올린다. | 후보 목록이 불완전한데 정확도 평가를 시작할 수 있다. |
| 공개 결과 비간섭 | 새 증명은 내부 장부에만 저장하고 기존 작품명·주소·승격 판정에는 넣지 않는다. | 구조 시험이 실제 사용자 결과를 몰래 바꿀 수 있다. |

계획과 영수증에는 query·URL·후보 제목 원문을 새로 복사하지 않고 해시와 개수만 기록한다. 현재 cache hit는 원 실행의 영수증·결과 해시와 직접 결합하는 기능이 아직 없으므로 항상 `UNKNOWN`이다. 이 결합 기능이 구현되고 재검증되기 전에는 cache를 정상 완료로 승격하지 않는다.

## 합성 전·후 비교

| 합성 사례 | 개선 전 | 개선 후 producer 상태 | CandidateSet 상태 |
| --- | --- | --- | --- |
| 정상 search+fetch bounded plan | 완료 근거 없음 | `COMPLETE` | `COMPLETE` |
| 원 실행 영수증·해시가 없는 cache replay | 완료 근거 없음 | `UNKNOWN` | `UNKNOWN` |
| 계획된 fetch 영수증 누락 | 완료 근거 없음 | `UNKNOWN` | `UNKNOWN` |
| degraded 또는 throttle 검색 | 완료 근거 없음 | `UNKNOWN` | `UNKNOWN` |
| raw 11개 중 10개만 보존 | 손실 근거 없음 | `TRUNCATED` | `UNKNOWN` |
| 검색 계획 조기 종료 | 완료 근거 없음 | `UNKNOWN` | `UNKNOWN` |

요약은 `COMPLETE 1 / UNKNOWN 4 / TRUNCATED 1 / 거짓 COMPLETE 0`이다. 이 여섯 건은 계약 경계용 합성 사례이며 모델 정확도 표본이 아니다.

추가 공격형 시험에서는 필수 producer를 search 하나로 몰래 줄이기, 빈 계획, 사후에만 만든 direct 계획, 부분 검색 엔진 실패, blocked·일반 오류·형식이 깨진 응답, fetch fallback, raw 관측 수 축소 보고, 계획·영수증 변조·중복을 모두 완료가 아닌 상태로 닫았다.

## 단계별 잘림 영수증과의 차이

Gatekeeper·Decoder·Verifier·Arbiter 내부의 `candidate_stage_receipt_v1`은 후보가 어느 cap에서 사라졌는지 찾는 진단 장치다. 다른 검색·댓글·공식 URL 경로가 같은 후보를 복구할 수 있으므로 이 영수증만으로 CandidateSet을 `COMPLETE`나 `TRUNCATED`로 만들지 않는다.

반면 producer proof는 **실행 전에 고정된 search+fetch 계획 전체**의 완료 여부를 검사한다. 따라서 정상 합성 계획에는 `COMPLETE`를 허용하지만, 계획 밖의 웹 전체를 열거했다는 주장은 허용하지 않는다.

## 왜 아직 정확도 퍼센트를 표시하지 않는가

현재 확인한 `18/18`, `COMPLETE 1`, `TRUNCATED 1`은 각각 공개 결과 비간섭과 계약 경계 검사다. 정답률 100%, 후보 재현율 100%, 신뢰도 90% 같은 의미가 아니다.

퍼센트 도입 순서는 다음과 같다.

1. 실제 runtime에서 producer proof가 생성되는지 검증한다.
2. 정답이 CandidateSet 안에 들어온 비율인 **후보 목록 재현율(candidate-set recall)**을 위험 유형별로 측정한다.
3. 데이터를 규칙을 만드는 **개발용(DEV)**, 퍼센트를 실제 적중률에 맞추는 **보정용(CALIBRATION)**, 마지막에 한 번만 확인하는 **최종 동결 평가용(FROZEN-HOLDOUT)**으로 겹치지 않게 나눈다.
4. 후보와 `NIL`의 원점수를 temperature scaling 같은 단순 보정법으로 실제 적중률에 맞춘다.
5. 말한 퍼센트와 실제 적중률의 간격(ECE), 확률 오답 벌점(Brier·log loss), 작품 없음 성능(NIL precision·recall), 자동 처리 비율과 오답 위험의 관계(coverage-risk·AURC), 95% 신뢰구간을 함께 통과할 때만 퍼센트를 그림자 기록으로 표시한다.

`ABSTAIN`은 정답 종류가 아니라 위험할 때 답하지 않는 행동이다. `coverage`는 보류하지 않고 자동 선택한 행 비율, `risk`는 그 선택 중 오답 비율로 따로 본다. Golden18은 작고 일부 행이 UNJUDGED이며 새 producer 증명도 없어 보정·승인 표본으로 사용할 수 없다. 첫 표본 설계는 개발용 300건 이상, 보정용 300건 이상, 최종 동결 평가용 500건 이상을 시작점으로 삼고, 검색 실패·다작품·약칭·이미지·NIL 같은 주요 위험군을 가능하면 각각 50~100건 이상 확보한다. 표본이 부족한 계층은 퍼센트를 억지로 만들지 않고 `NOT_ESTIMABLE`로 둔다.

## 검증 결과

- P1 구조 산출물 v8: Golden18 공개 작품명·주소·판정 `18/18` 불변, 확률 전부 `null`.
- Producer 합성: `COMPLETE 1 / UNKNOWN 4 / TRUNCATED 1 / 거짓 COMPLETE 0`.
- Producer·CandidateSet·하네스 집중 시험: `62/62 tests OK`.
- 관련 영향 범위 14개 모듈 시험: `529/529 tests OK`.
- Python 문법 검사: 변경된 구현·하네스·시험 `PASS`.
- 실제 새 runtime: `NOT_RUN`.
- 기존 broader suite의 선행 red 2건과 full `8F+1E` 묶음은 변경 전에도 있던 별도 baseline debt이며 전체 테스트 초록으로 표현하지 않는다.

## 진행 중 production은 어떻게 읽어야 하나

`2026-07-11 20:24:31 KST`에 읽기 전용으로 다시 확인한 별도 production run은 입력 `104,502`, 처리 완료 `979`, 최종 파일 반영 `964`, 순서 대기 `15`, 실패 `0`이었다. 요청·실제 병렬도는 `16/16`, 검색 endpoint는 정상 `16`·실패 `0`·light mode 아님, VLM/OCR은 준비 상태였다. 대시보드와 상태 API는 각각 HTTP `200`, `ok=true`였다.

다만 `large_run_complete=false`, `ordered_flush_blocked=true`이고 계속 움직이는 실행이다. 이 수치는 이 P1 코드를 실제 검증한 결과도, 의미 정확도나 전체 운영 승인도 아니다. 해당 process·result·checkpoint·pending·dashboard·endpoint·slang DB는 수정·중지·재시작하지 않았다.

## 게이트

| 게이트 | 상태 | 뜻 |
| --- | --- | --- |
| 합성 producer 계약 | `GO_SYNTHETIC_CONTRACT_ONLY` | 사전 고정 정상 계획 1건만 완료, cache 미결합·누락·저하·오류·손실은 fail-close했다. |
| Runtime 배선 코드 | `IMPLEMENTED_NOT_RUNTIME_VALIDATED` | search/fetch 경계에 연결했지만 새 실행은 하지 않았다. |
| Golden18 공개 비간섭 | `GO 18/18` | 기존 공개 결과는 바뀌지 않았다. |
| 실제 CandidateSet 완전성 | `UNKNOWN` | Golden18에 새 영수증이 없다. |
| 후보 재현율 | `NOT_EVALUABLE` | 실제 COMPLETE holdout이 없다. |
| 정확도 퍼센트 | `NOT_AVAILABLE_UNCALIBRATED` | 확률은 전부 `null`이다. |
| 의미 품질 | `REVIEW-LOCKED` | 합성 계약 통과는 품질 승인이 아니다. |
| 운영 전체 승인 | `full_scan_approval=false` | production 전환 근거가 없다. |
| 전체 goal | `ACTIVE / NOT_COMPLETE` | P0 live, P2 exact-once, P3 보정과 실제 runtime이 남았다. |

## 정본 산출물

- P1 v8 실행 명세·비교: `out/candidate_set_nil_shadow_harness_20260711/v8/`
- Producer v6 실행 명세·비교: `out/candidate_generation_completeness_harness_20260711/v6/`
- Producer 계약: `src/llm_batch/candidate_generation.py`
- Search/fetch 배선: `src/llm_batch/experts/orchestrator.py`, `src/llm_batch/agentic_pipeline.py`
- CandidateSet 합성: `src/llm_batch/candidate_set_shadow.py`
- 합성 하네스: `tools/run_candidate_generation_completeness_harness.py`
- 핵심 시험: `tests/test_candidate_producer_completion.py`, `tests/test_candidate_set_shadow_contract.py`, `tests/test_candidate_generation_completeness_harness.py`

## 다음 작업

1. 진행 중 production이 끝난 뒤 별도 output·dashboard ON·`--parallel 16`·slang off/read-only 조건으로 실제 receipt 생성과 재시작 경계를 검증한다.
2. cache 원 실행 영수증·결과 해시 결합 계약을 추가하고 재시작 뒤에도 다른 실행의 cache가 섞이지 않는지 검증한다.
3. 실제 producer COMPLETE 행을 포함하는 더 큰 최종 동결 평가셋을 만들고 후보 목록 재현율을 측정한다.
4. P2 게시글별 최종 공개 판정 exact-once와 우회 경로 `0`을 독립 감사한다.
5. P3 개발용·보정용·최종 동결 평가용 자료와 확률 보정 게이트를 만든다.
