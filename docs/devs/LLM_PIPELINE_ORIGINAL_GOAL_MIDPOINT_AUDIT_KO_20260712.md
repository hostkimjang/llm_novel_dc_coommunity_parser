# LLM 처리 파이프라인 최초 목표 중간점검

작성일: 2026-07-12 KST

## 결론

최초 목표의 진행 방향은 맞다. `검색 실패 시 공개 차단 → 여러 후보와 작품 없음 보존 → 최종 판정 한 번만 기록 → 보정된 정확도 퍼센트 → 선택적 비용 처리` 순서로 P0~P4를 구현했다. 안전 계약, 원본 재판독, 계보 결속, 변조·재시도 방지는 상당히 진척됐다.

그러나 실제 효과 검증은 아직 시작 전이다. 실제 DEV/CAL/FROZEN 자료와 동일 RunSpec의 fresh BEFORE/AFTER가 없으므로 의미 정확도, 후보 재현율, 호출 절감률, 배치 종단 지연 개선률은 모두 `null / NOT_ESTIMABLE`이다. 합성 수치와 저장본 재생 결과를 실제 개선 퍼센트로 읽으면 안 된다.

따라서 현재 판정은 다음 두 문장을 함께 써야 정확하다.

- 아키텍처·안전·측정 기반 구현: **중후반**
- 실제 정확도·비용·지연 효과 검증: **시작 전**

운영은 계속 `REVIEW-LOCKED`, `full_scan_approval=false`다.

## 최신 P3/P4 정적 계약 addendum

- P3 actual 정책은 v3에서 `top_label_accuracy_denominator`를 `ALL_FROZEN_ROWS` 또는 `NON_ABSTAIN_ROWS`로 명시하고 policy payload와 `policy_sha256`에 결속한다. 기존 P3 v18의 legacy v2 정본은 그대로 유효하다.
- P4 paired reader는 각 행 `DecisionCostTrace`의 scope/run/input index/post ID를 RunSpec·arm과 대조해 batch execution envelope를 재구성하고, 동일 full-expert 행만으로 per-post E2E p50/p95와 paired bootstrap CI를 계산한다.
- `REFERENCE_COPY_COST_ONLY` 0-call 행은 production savings·latency 개선 KPI에서 계속 제외한다. 합성 fixture 숫자는 reader 계약 시험일 뿐 actual KPI가 아니다.
- 새 정본은 P3 v20 `0c6f96ec37a591356589a339699066f0d412e07322d6e8b2b5e6f0749ff36f21`, P4 v21 `ebbdec02f9db4c8801f403a39515a589847ede2c7683e0fbd76e3c0a5bd4e406`다. actual DEV/CAL/FROZEN·fresh BEFORE/AFTER는 여전히 없으므로 수치는 `null / NOT_ESTIMABLE`이며 `REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.

## Goal 재활성화 상태

기존 작업 `019f4f3f-4f46-78d1-8418-50834da44924`은 Goal API에 `blocked` 기록이 남아 있다. 이 API는 `blocked → active` 전환을 제공하지 않고, 기존 목표가 미완료라 같은 작업의 `create_goal`도 거부했다. 실제 완료되지 않은 목표를 `complete`로 바꾸는 우회는 사용하지 않았다.

사용자의 새 Goal 전환 지시에 따라 같은 프로젝트에 새 작업 `019f5532-580e-7d40-a3c3-ee8a208dadf8`을 만들었고, 그 작업에서 새 Goal이 `active`로 생성된 것을 확인했다. 새 Goal은 아래 잔여 목표를 처음부터 다시 하지 않고 현재 P2 v8 → P3 v18 → P4 v19 이후부터 이어간다.

## 최초 목표 대비 진행표

| 최초 의도 | 현재 구현·검증 | 실제 전후 증거 | 중간 판정 |
| --- | --- | --- | --- |
| 실행 입력·코드·모델·설정 봉인 | P0~P4 RunSpec과 parent/source path·bytes·SHA 결속 | actual pair 없음 | 기반 구현 |
| 필수 검색 실패 시 잘못된 공개 차단 | P0 저장본 unsafe publish `1→0`, 합성 `5→0` | 새 검색/runtime 없음, blocker `5→5` | 안전 개선, 실제 복구 미검증 |
| 여러 작품 후보와 `NIL` 보존 | CandidateSet/NIL, producer·잘림 영수증, Golden18 구조 검사 | 실제 candidate recall 없음 | 기반 구현 |
| `RESOLVE / NIL / ABSTAIN` 분리 | NIL 정답 사건과 ABSTAIN 행동을 계약에서 분리 | 실제 selector 없음 | 부분 구현 |
| 최종 공개 판정 exact-once·중단 복구 | P2 v8 WAL, exact recovery witness, 공격·복구 회귀 통과 | 실제 강제 중단·재시작 없음 | 계약 구현, runtime 미검증 |
| 정확도 판단을 보정된 `%`로 표시 | P3 v20에 v3 ABSTAIN 분모 정책 hash-binding과 paired CI 구현 | actual 지표 전부 `null` | 산식·게이트 구현, 성능 미측정 |
| 쉬운 글은 저비용, 위험 글은 전체 전문가 | P4 v21 그림자 라우터·물리 호출 원장·독립 reader·execution envelope 구현 | actual calls/post·회피율 없음 | 그림자 기반 구현 |
| 비용·처리시간 개선률 확인 | full-expert comparable p50/p95·paired CI 계산 경로 구현, 합성 호출 `16→8`은 산술 시험으로만 격리 | actual cost delta·E2E p50/p95 없음 | 실측 대기 |
| 행별 append-only 저장과 재시작 안전 | P2 WAL/checkpoint/pending·복구 witness | 104k 규모 새 구조·crash 검증 없음 | 작은 계약 검증만 완료 |
| 속어 DB 제안·승인·롤백 | 현재 별도 구현 근거 없음 | 없음 | 미구현 |
| DEV/CAL/FROZEN·shadow/high-risk 분리 | 정책·manifest·readiness 계약 구현 | 실제 평가 자료 `0/18 READY`, `UNJUDGED 3` | 자료 구축 전 |
| rate limit·공유 cache·singleflight | 현재 별도 구현 근거 없음 | 없음 | 미구현 |

## 정본 증거

| 단계 | 정본 | 현재 게이트 |
| --- | --- | --- |
| P0 검색 fail-close | `out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/` | `PARTIAL_SAFETY_IMPROVEMENT_NOT_RUNTIME_VALIDATED` |
| P1 후보/NIL | `out/candidate_set_nil_shadow_harness_20260711/v8/` | 실제 확률 없음, recall `NOT_EVALUABLE` |
| P1 생산 완전성 | `out/candidate_generation_completeness_harness_20260711/v6/` | 합성 계약만 통과 |
| P2 exact-once | `out/publication_exact_once_harness_20260711/v8/` | 저장본·합성 `GO`, runtime `NOT_RUN` |
| P3 정확도 퍼센트 | `out/candidate_set_calibration_shadow_harness_20260711/v20/` | `NO_GO_ACTUAL_DATASET_NOT_READY` |
| P4 선택적 비용 처리 | `out/selective_compute_shadow_harness_20260712/v21/` | `GO_P4_SHADOW_CONTRACT_FOUNDATION_ONLY`, actual `NOT_ESTIMABLE` |

최신 집중 회귀는 recovery/paired `71/71`, P2/P3 `58/58`, P4 `33/33`, 합계 `162/162 PASS`다. 이는 구현 회귀 시험이며 실제 모델 성능 시험이 아니다.

## 아이디어 출처 확인

저장소에서 확인되는 보정 확률, `RESOLVE/NIL/ABSTAIN`, cheap→expert, write-once 정본 아이디어는 Claude Opus 공동 연구다. Fable의 확인 가능한 역할은 Loop643 다작품 충돌 안전 감사다. Fable을 최초 설계자로 단정할 근거는 없다. 최근 Fable·Opus 호출은 구체 과제 결과를 반환하지 않아 구현 증거에서 제외했다.

## 현재 운영과 다음 순서

2026-07-12 16:19 KST 읽기 전용 스냅샷에서 production run `20260711_113712_379597`은 입력 `104,502`, completed `2,853`, flushed `2,814`, pending `39`, failed `0`, parallel `16`, `large_run_complete=false`였다. 대시보드는 정상이나 저장 순서가 막혀 있어 이 실행에 실험 코드를 주입하지 않는다.

다음 순서는 다음과 같다.

1. P3 actual 정책 A/B 또는 수정값을 소유자가 확정한다.
2. 실제 source-backed DEV/CAL/FROZEN 자료를 만들고 미판정 3행을 근거와 immutable candidate ID로 판결한다.
3. P3 v3 policy JSON에 `top_label_accuracy`의 ABSTAIN 분모를 소유자 선택값으로 명시한다. hash-binding 계산 경로는 구현됐지만 실제 정책 값은 아직 확정되지 않았다.
4. production 종료 뒤 별도 경로에서 `--parallel 16`, dashboard ON으로 fresh BEFORE/AFTER와 강제 중단·재시작을 실행한다.
5. 실제 정확도·후보 재현율·호출·token·배치 E2E p50/p95와 paired CI를 재판독한다. 계산 경로는 구현됐지만 fresh evidence가 없으면 모두 `null`이다.
6. hard regression 0, public/CandidateSet 비간섭을 모두 통과한 뒤에도 사람 검토 전에는 운영 routing을 열지 않는다.
7. 남은 구조 공백인 속어 DB 승인·롤백, rate limit·공유 cache·singleflight, 대규모 framed WAL을 후속 단계로 구현한다.
