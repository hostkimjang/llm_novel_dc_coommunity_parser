# P1 후보 목록 잘림·전문가 단계 영수증 v4 보고서 (이전 단계)

> 최신 단계는 query/search/fetch bounded producer proof를 추가한 v5다. 현재 기능 설명과 게이트는 `docs/devs/loop_reports/LOOP_P1_PRODUCER_COMPLETION_PROOF_20260711.md`, 정본 수치는 `out/candidate_generation_completeness_harness_20260711/v5/comparison.md`를 우선한다. 이 문서는 로컬 cap·전문가 단계 영수증 v4의 역사적 근거로 보존한다.

## 한눈에 보는 결론

후보 목록이 제한 때문에 잘렸는지 최종 장부 2곳과 전문가 내부 7곳에서 기록하도록 개선했다.

- 상류 제목 순위 단계: 정책 필터 뒤 고유 제목이 6개를 넘는지 확인한다.
- serializer 보존 단계: 후반 후보 보정까지 끝난 로컬 후보가 24개를 넘는지 확인한다.
- 전문가 내부 단계: Gatekeeper 1곳, Decoder 1곳, Verifier 2곳, Arbiter 3곳에서 후보를 5개 또는 8개로 자르기 직전 고유 후보 손실을 진단한다.

합성 사례에서 고유 제목 7개는 `TRUNCATED 7→6`, serializer 고유 후보 25개는 `TRUNCATED 25→24`로 검출됐다. 전문가 내부 cap+1 사례도 `7/7 TRUNCATED`로 검출했다. cap과 정확히 같거나 cap 밖 항목이 앞 후보의 중복인 경우는 `UNKNOWN(고유 후보 손실 없음·상류 완전 여부 모름)`으로 남겼다.

이 변화는 **모델 정확도 향상이 아니라 목록 잘림을 추적할 수 있게 된 구조 개선**이다. 최종 장부와 단계별 영수증 모두 `COMPLETE(전체 후보를 다 봄)`를 만들지 않는다. 단계별 영수증은 다른 경로의 후보 회복 가능성이 있어 CandidateSet 상태에 합성하지 않는다. 따라서 후보 목록 재현율은 `NOT_EVALUABLE`, 후보별 정확도 퍼센트는 `NOT_AVAILABLE_UNCALIBRATED`다.

Golden18 저장본의 공개 작품명·주소·승격 판정·추적 지문은 `18/18` 불변이었다. 실제 새 LLM/MCP 실행은 `NOT_RUN`, 의미 품질은 `REVIEW-LOCKED`, 전체 스캔 승인은 `full_scan_approval=false`다.

## 각 기능이 실제로 하는 일

| 기능 | 쉬운 설명 | 기록 위치 | 안전 경계 |
| --- | --- | --- | --- |
| 제목 순위 잘림 장부 | 내부 정책 필터가 끝난 뒤 7번째 제목이 cap 6 때문에 사라지는지 기록한다. | `candidate_ledger.title_candidate_generation` | 후속 필터·rescue 전 시점이다. 최종 CandidateSet과 같은 목록이라는 뜻이 아니다. |
| serializer 잘림 장부 | 최종 결과에 최대 24개만 보존하기 전에 25번째 후보가 있는지 기록한다. | `candidate_ledger.candidate_generation` | 상류에서 애초에 만들지 못한 후보까지 완전하다고 증명하지 않는다. |
| 합성 상태 | 어느 한 단계라도 `TRUNCATED`면 전체 후보 생성 상태를 `TRUNCATED`로 보수적으로 내린다. | CandidateSet shadow의 `generation_status` | 둘 다 cap 이하이면 `COMPLETE`가 아니라 `UNKNOWN`이다. |
| 전문가 단계 영수증 | 각 전문가가 공유 후보를 자르기 직전 관측·유지 고유 수와 순서 해시를 남긴다. | `candidate_ledger.candidate_stage_receipts` | 어디서 후보가 사라졌는지 찾는 진단 전용이다. CandidateSet 상태·확률·공개 판정에 합성하지 않는다. |
| 지문 검증 | 관측 목록·보존 목록·메타데이터가 나중에 바뀌지 않았는지 SHA로 확인한다. | 각 frozen v1 장부 | cap·수·필드·지문·root 혼입이 틀리면 fail-close한다. |
| 공개 결과 비간섭 | 새 장부를 결과 옆에만 기록한다. | nested `candidate_ledger` | 공개 title/URL·승격 입력·publication fingerprint에는 넣지 않는다. |

제목 순위 장부는 **정규화 제목** 기준이고 serializer 장부는 **정규화 제목·주소·역할 조합** 기준이다. 두 count는 의미가 달라 합산하지 않는다. 동일 정규화 제목에 URL이나 역할만 다른 두 관측은 제목 순위 단계에서는 한 사건으로 센다.

## 개선 전·후 비교

| 사례 | 개선 전 | 개선 후 | 뜻 |
| --- | --- | --- | --- |
| 상류 고유 제목 7개 | 앞 6개만 반환, 잘림 기록 없음 | `TRUNCATED`, 7개 관측·6개 보존 | cap 6으로 사라진 후보 존재를 기록한다. |
| 상류 고유 제목 정확히 6개 | 6개 반환 | `UNKNOWN`, 6개 관측·6개 보존 | 6개라고 전체 열거 완료를 주장하지 않는다. |
| 상류 원본 7개·고유 제목 6개 | 중복 여부 설명 없음 | `UNKNOWN`, 고유 6개 | 중복을 잘림으로 오탐하지 않는다. |
| 같은 정규화 제목·다른 URL/역할 | 제목 기준 한 후보 | `UNKNOWN`, 고유 1개 | 선언한 title-only 기준과 실제 계산이 일치한다. |
| serializer 고유 후보 25개 | 앞 24개에서 조기 반환, 잘림 기록 없음 | `TRUNCATED`, 25개 관측·24개 보존 | 25번째 후보 존재를 잃지 않는다. |
| serializer 고유 후보 정확히 24개 | 24개 반환 | `UNKNOWN`, 24개 관측·24개 보존 | cap과 같다고 `COMPLETE`로 오판하지 않는다. |
| serializer 원본 25개·고유 24개 | 중복 여부 설명 없음 | `UNKNOWN`, 고유 24개 | 중복을 잘림으로 오탐하지 않는다. |

최종 장부의 합성 잘림 검출은 개선 전 `0건`에서 개선 후 `2건`으로 바뀌었고, 일곱 합성 사례의 기존 보존 항목·순서는 모두 그대로였다. 전문가 단계는 cap+1 `7/7`을 검출했고, 정확히 cap·cap 밖 중복 경계 오탐은 `0`, 기존 유지 출력은 `9/9` 불변이었다. `0→2`와 `0→7`은 정확도 수치가 아니다.

### 전문가 내부 7개 경계

| 단계 | 하는 일 | cap | 합성 cap+1 |
| --- | --- | ---: | --- |
| `gatekeeper.comment_title_candidates` | 댓글 제목 후보를 메인 후보 생성기로 넘기기 직전 | 8 | `TRUNCATED 9→8` |
| `decoder.new_suspected_titles` | Decoder 신규 후보를 공유 목록에 더하기 직전 | 5 | `TRUNCATED 6→5` |
| `verifier.ranked_update` | 증거 반영 후 후보 재정렬 직후 | 5 | `TRUNCATED 6→5` |
| `verifier.comment_boost` | 댓글 확인 신호 반영 후 재정렬 직후 | 5 | `TRUNCATED 6→5` |
| `arbiter.critic_filter` | 낮은 신뢰도 후보 필터 직후 | 5 | `TRUNCATED 6→5` |
| `arbiter.candidate_merge` | 기존 후보와 Arbiter 신규 후보 병합 직후 | 5 | `TRUNCATED 6→5` |
| `arbiter.llm_candidate_merge` | 근거 검사를 통과한 LLM 후보 병합 직후 | 5 | `TRUNCATED 6→5` |

후보 이름 원문은 새 영수증에 넣지 않고 정규화 key의 해시와 개수만 기록한다. 같은 단계가 반복 실행되면 `occurrence`를 증가시켜 앞선 잘림 기록을 덮어쓰지 않는다.

## 정확도 퍼센트 제안은 어떻게 연결되는가

한 게시글의 정답은 `후보 작품 A`, `후보 작품 B`, ..., `작품 없음(NIL)` 중 정확히 하나로 정의한다. 보정이 완료되면 `p(A) + p(B) + ... + p(NIL) = 100%`가 된다. `판단 보류(ABSTAIN)`는 정답 종류가 아니라, 지금 답하면 위험해서 시스템이 멈추는 운영 행동이므로 이 100% 합에 넣지 않는다.

현재는 후보 목록이 완전하다는 증거와 분리된 보정·최종 동결 정답셋이 없다. 따라서 모든 후보 확률과 `p(NIL)`은 `null`, 상태는 `NOT_AVAILABLE_UNCALIBRATED`다. 이번 `0→2`, `0→7`, `18/18`, `9/9`, `6/6`은 구조·비간섭 검사 수치이며 정확도 퍼센트가 아니다. 나중에 퍼센트를 표시하려면 먼저 위험 유형별 CandidateSet 재현율을 확인하고, 겹치지 않는 holdout에서 ECE·Brier 또는 log loss·NIL PR·risk-coverage와 신뢰구간을 통과해야 한다.

## Golden18에서 확인한 구조

| 확인 항목 | 결과 | 해석 |
| --- | ---: | --- |
| 게시글·후보 묶음 무결성 | `18/18` | RunSpec, 코드 SHA, 게시글 순서·집합, 후보 지문을 재검증했다. |
| 공개 계약 불변 | `18/18` | 작품명·주소·판정·trace·fingerprint가 바뀌지 않았다. |
| 작품 후보 정답의 사건 공간 내 관측 | `9/9` | 구조 검사이며 후보 목록 재현율 100%가 아니다. |
| NIL 정답 원장 행의 공통 NIL 선택지 | `6/6` | NIL 선택 정확도가 아니라 사건 공간 구조 검사다. |
| 단일 정답 미지정 | `3` | 복합 작품·미상 가설·이미지 HOLD를 억지 라벨링하지 않았다. |
| 후보별 확률·선택 라벨 | 전부 `null` | 보정 정답셋이 없어 숫자를 만들지 않았다. |

## 구현 경계

- `src/llm_batch/candidate_generation.py`
  - `title_candidate_generation_v1`: 정규화 제목 기준, cap 6, `UNKNOWN/TRUNCATED`만 허용
  - `candidate_generation_v1`: 정규화 제목·주소·역할 기준, cap 24, `UNKNOWN/TRUNCATED`만 허용
  - 장부 필드·수·reason·source/observed/retained/metadata 지문 strict 검증
  - `candidate_stage_receipt_v1`: producer/stage/cap 고정, `UNKNOWN/TRUNCATED`만 허용, 원문 비노출 hash, 반복 occurrence 보존
- `src/llm_batch/agentic_pipeline.py`
  - main `_build_title_candidates`의 정책 필터 뒤 전체 ranked row를 세고 기존 상위 6개만 `DetectedTitle`로 만든다.
  - cap 밖 낮은 순위 row는 공개 모델로 materialize하지 않아 기존 예외 경계를 보존한다.
  - max 12 alias probe와 max 8 character helper의 임시 snapshot은 폐기하며 main cap 6 장부를 덮어쓰지 않는다.
  - serializer 후보 source는 전체 순회하되 기존과 같은 앞 24개를 보존한다.
  - private context의 단계별 영수증을 prompt/expert output에 넣지 않고 최종 nested ledger에만 복사한다.
- `src/llm_batch/experts/{gatekeeper,decoder,verifier,arbiter}.py`
  - 실제 후보 상태 cap 7곳의 slice 직전에 영수증을 기록한다.
  - prompt 요약용 slice, Decoder term 후보 2개, Arbiter raw LLM 5개 같은 비권위 경계는 이번 계약에서 제외한다.
- `src/llm_batch/candidate_set_shadow.py`
  - 두 nested 장부와 retained source를 strict 재생한다.
  - 어느 단계든 잘리면 `TRUNCATED`, 그 외에는 v1에서 항상 `UNKNOWN`이다.
  - candidate-set recall은 계속 `NOT_EVALUABLE`이다.

## 검증 결과

- 집중 계약·하네스 시험: `71 tests OK`
- 영향 범위 시험: candidate generation, CandidateSet/NIL, completed-source audit, promotion, retrieval, P0/P1 harness, publication convergence, title-lead, Decoder·Arbiter 묶음 `518 tests OK`
- 더 넓은 약칭 묶음 포함 실행: `554 tests`, `552 pass + 선행 red 2`. 두 red는 변경 전 `tmp07/arch_i8_full_unittest_20260711.log`에 동일 이름·동일 단언으로 존재하고, 영수증 recorder를 no-op으로 바꿔도 그대로 재현돼 이번 변경 비인과다.
- P1 v6: integrity/public 불변 `18/18`, 작품 후보 구조 `9/9`, NIL 구조 `6/6`, UNJUDGED `3`, 확률·선택 `null`
- completeness v4: 최종 장부 합성 잘림 `0→2`, 전문가 단계 합성 잘림 `0→7`, 경계 오탐 `0`, 출력 호환 `7/7 + 9/9`, Golden18 public 불변 `18/18`
- RunSpec 상태: P1 v6 `GO / row 18 / runtime NOT_RUN`, completeness v4 `GO / row 18 / runtime NOT_RUN`

### 전체 테스트의 선행 red cluster

`tests.test_agentic_pipeline_rework`의 동일 `8 failures + 1 error`는 이번 cap 6 변경 약 11시간 49분 전인 `2026-07-11 06:00:46 KST` 로그에도 존재한다.

- 선행 로그: `tmp07/arch_i8_full_unittest_20260711.log`
- 동일 `candidate_url` monkeypatch `TypeError`: 로그 15312~15330
- 동일 alias/locked-official/title-intent/recommendation 실패: 로그 15756~15861
- 현재 9건 집중 재실행에서도 `8F+1E`; 새 title snapshot finalizer 호출은 각 실패에서 `0회`

따라서 이 red cluster는 이번 변경의 회귀가 아니다. 그러나 기대 동작이 맞는지는 별도 계약 판정이 필요하므로 “무시 가능한 실패”나 “전체 테스트 초록”으로 표현하지 않는다.

## 오케스트레이션 감사

- Sol ultra: 상류 cap 6의 안전한 판정은 `>6 → TRUNCATED`, `<=6 → UNKNOWN`이며 `COMPLETE`는 불가능하다고 확인했다. 선행 로그와 현재 실패를 대조해 `8F+1E` 비인과를 확정했고, cap 밖 후보 materialization 위험을 지적해 수정에 반영했다.
- Terra high: 제목 단계 count 기준을 `normalized title unique after policy prune`로 고정하고 URL·역할 차이가 false truncation을 만들지 않는지 builder·parser·`__post_init__`을 감사했다.
- Luna medium: 동일 제목·다른 URL/역할, cap 밖 invalid row, max 12/8 helper, cap 6/24 합성 상태를 교차검증했다.
- Claude Fable·Opus: 과제와 파일을 명시해 재호출했지만 이번에도 과제별 감사 결과를 반환하지 않았다. 모델 선택은 정상 적용했으나 일반 안내 응답은 근거로 채택하지 않았다.

## 활성 프로덕션 비간섭

- 읽기 전용 스냅샷: `2026-07-11 19:02:04 KST`
- run: `20260711_113712_379597`
- input/completed/flushed/pending/failed: `104502/790/779/11/0`
- requested/effective parallel: `16/16`
- search healthy/failure: `16/0`, light mode `false`
- VLM/OCR semantic review ready: `true`
- dashboard: root 및 `/api/health` HTTP `200`, health `ok=true`
- `large_run_complete=false`, `ordered_flush_blocked=true`

이는 이동 중인 운영 진행 상태이며 이번 개선의 승인 근거가 아니다. process, result, checkpoint, pending, dashboard, endpoint, `slang_db`를 수정·중지·재시작하지 않았다.

## 정본 산출물

- P1 v6 RunSpec: `out/candidate_set_nil_shadow_harness_20260711/v6/run_spec.json`
- P1 v6 한국어 비교: `out/candidate_set_nil_shadow_harness_20260711/v6/comparison.json`, `comparison.md`
- completeness v4 RunSpec: `out/candidate_generation_completeness_harness_20260711/v4/run_spec.json`
- completeness v4 한국어 비교: `out/candidate_generation_completeness_harness_20260711/v4/comparison.json`, `comparison.md`
- 기능 중심 한국어 안내: `docs/devs/LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`
- 구현: `src/llm_batch/candidate_generation.py`, `src/llm_batch/candidate_set_shadow.py`, `src/llm_batch/agentic_pipeline.py`
- 하네스: `tools/run_candidate_set_nil_shadow_harness.py`, `tools/run_candidate_generation_completeness_harness.py`
- 시험: `tests/test_candidate_generation_snapshot.py`, `tests/test_candidate_stage_receipts.py`, `tests/test_candidate_set_shadow_contract.py`, `tests/test_candidate_set_nil_shadow_harness.py`, `tests/test_candidate_generation_completeness_harness.py`

## 아직 끝나지 않은 것

1. Gatekeeper·Decoder·Verifier·Arbiter 후보 상태 7곳의 `pre_cap_count/truncated` 영수증은 생겼지만, 검색 query budget·MCP 결과·fetch URL 등 앞선 producer와 `enumeration_finished` 증거는 아직 없다.
2. 따라서 단계별 잘림 위치는 진단할 수 있어도 `COMPLETE` 표본과 candidate-set recall은 만들 수 없다.
3. 분리된 개발·보정·최종 동결 정답셋이 없어 ECE·Brier·log loss·NIL PR·risk-coverage와 정확도 퍼센트는 아직 없다.
4. 실제 새 LLM/MCP runtime은 실행하지 않았다. active production 종료 뒤 별도 경로, dashboard ON, `--parallel 16`, slang off/read-only로 검증해야 한다.
5. P0 live retrieval 배선과 P2 최종 공개 판정 single-writer/write-once는 별도 고위험 단계다.
6. 신규 모듈·하네스·시험·v6/v4 산출물은 아직 Git에 추적되지 않았으므로 clean clone/CI 내구성은 커밋 전까지 미확정이다.

## 게이트

- cap 6/24 로컬 잘림 탐지: `GO`
- 전문가 단계 7곳 잘림 진단: `GO_DIAGNOSTIC_ONLY`
- 거짓 `COMPLETE` 방지: `GO`
- 기존 보존 출력 호환: `GO 7/7`
- Golden18 공개 결과 무영향: `GO 18/18`
- 실제 runtime: `NOT_RUN`
- 후보 목록 재현율: `NOT_EVALUABLE`
- 확률 정확도: `NOT_AVAILABLE_UNCALIBRATED`
- 의미 품질: `REVIEW-LOCKED`
- production 승인: `full_scan_approval=false`
- 전체 goal: `ACTIVE / NOT_COMPLETE`
