# 2,712행 개선 아키텍처 전문가 회의록

- 일자: 2026-07-19 KST
- 목적: 기존 정상 정답을 최대한 보존하면서 남은 의미 오류를 개선할 수 있는 다음 아키텍처와 검증 순서를 결정한다.
- 작업 성격: 읽기 전용 연구·검토. production code, 실행 중인 `20260715_143806_848671`, public WAL, slang DB는 변경하지 않았다.

> 2026-09-03 후속: 본 회의의 “공개 경로 불변·shadow 우선” 원칙에 따라 annotation packet/Windows/preauthorization/supervisor V2를 runtime 밖 additive component로 구현했다. 전체 P0 `836/836`, 보호 endpoint `6/6` 불변이며 실제 semantic/production gate는 계속 `NO_GO`다. 최신 판단은 [`P0_OWNER_ROOT_PREAUTHORIZATION_V2_SUPERVISOR_REVIEW_20260903_KO.md`](P0_OWNER_ROOT_PREAUTHORIZATION_V2_SUPERVISOR_REVIEW_20260903_KO.md)를 따른다.

## 참석자와 실제 실행 범위

| 역할 | 실제 모델·추론 | 이번 회의 범위 | 결과 사용 범위 |
|---|---|---|---|
| 아키텍처 진화 검토 | `gpt-5.6-terra/high` | 현재 publication·shadow·router·P1·recovery 구조와 결합 위험 | 전체 구조 제안 |
| 의미 품질·정답 보존 검토 | `anthropic/claude-opus-4-8/high` | `semantic_recovery_plan` 계약·테스트 중심 | P1 모듈 품질에 한정 |
| 계측·검색·운영 검토 | `gpt-5.6-luna/max` | 2,712 replay, 32×3 grouped run, measurement/search/cost gate | 운영·계측 판정 |
| shadow 설계 선행 검토 | `gpt-5.6-sol/ultra` | 과거 strict fresh equivalence가 stochastic 관측을 막던 seam | 이미 구현된 observation mode의 설계 배경으로만 사용 |
| 독립 Pro 검토 | 정확한 `GPT-5.6 Sol + Pro` | 과거 2,590행 답변 복구·현재 task 1회 제출/복구 | 과거 범위의 축 분리 의견만 보조 사용; 현재 답변 미확보 |
| 통합 검증 | Codex root | 로컬 코드·정본 문서·분석 JSON 교차검증 | 최종 합의·이견 정리 |

서브에이전트 이름에는 사용자 요청대로 모델·추론을 표시했다. 실제 hidden override도 각 행의 모델·추론으로 지정했다. 동시 thread limit 때문에 처음에는 Opus/Luna 동시 생성이 실패했으나, 자리가 난 뒤 각각 실제 지정 모델로 실행했다.

## 독립 의견

### 1. 아키텍처 진화 검토 (`gpt-5.6-terra/high`)

- 현재 공개 정본은 `PublicationCommitRegistry`의 exact-once WAL이며, fresh observation·router·P1·recovery는 모두 non-writer라는 점을 가장 강한 안전성으로 평가했다.
- 2,712 replay의 receipt coverage·공개 비간섭은 구조적 안전 근거지만 의미 효과 근거는 아니라고 판정했다.
- 가장 큰 위험은 `expert_main._commit_final_result`가 preview, ledger, router, P1, shadow, recovery, batch learning의 순서와 mutable `run_meta`를 함께 소유하는 결합이다.
- router, P1, recovery가 서로 다른 whitelist/source projection으로 같은 결과를 재해석해 lineage drift를 한 곳에서 설명하기 어렵다고 지적했다.
- 권고 순서는 동작 불변 `PublicationFinalizer` 추출, 공통 immutable observation envelope, public writer와 분리된 shadow intervention simulator다.
- 전체 판정은 `NO-GO`, `full_scan_approval=false`다.

### 2. 의미 품질·정답 보존 검토 (`anthropic/claude-opus-4-8/high`)

- `semantic_recovery_plan.py`가 `PLAN_ONLY`, `public_apply=false`, self-hash, publication binding, typed relation/media/canonical identity, degraded-search query zero, raw OCR 렌더 금지 계약을 fail-close로 구현했다고 확인했다.
- focused `12/12` 테스트와 compile을 확인하고 P1 모듈 계약에는 조건부 PASS를 부여했다.
- typed non-novel 후보가 primary가 아니어도 전체 row를 HOLD로 보낼 수 있는 과잉 HOLD 가능성과 blocker advisory noise를 모니터링 항목으로 남겼다.
- 이 PASS는 P1 모듈의 계약 준수에 한정한다. 883 HOLD, PASS HOLD 117/230, plan-only, 실제 search/network 0/0이므로 system-level semantic effectiveness나 자동 activation PASS로 확대하지 않는다.

### 3. 계측·검색·운영 검토 (`gpt-5.6-luna/max`)

- 2,712 exact join·receipt coverage·공개 비간섭·deterministic replay는 신뢰 가능하나, grouped AFTER는 실제 recovery 적용군이 아니라 fresh shadow이므로 인과효과·일반화 주장은 불가능하다고 판정했다.
- 6개 arm 중 repeat 1 BEFORE와 repeat 2 AFTER에 각각 unlinked/estimated 1행이 있어 measurement는 arm 기준 `4/6 GO`, 전체는 `NO_GO`다.
- expert calls `932→883`, total tokens `8,353,838→8,450,423`, wall `3,645.8s→3,467.5s`는 `observational_partial/NOT_ESTIMABLE`이며 비용·속도 개선으로 말할 수 없다고 확인했다.
- search는 AFTER `SEARCH_DEGRADED 51/96`, `NOT_APPLICABLE 15/96`, `ok 30/96`, UNKNOWN 0이다. 상태 coverage는 좋아졌지만 search-quality는 `NO-GO`다.
- 원자적 row seal·external ledger link·independent readback, 공통 authority binding, row/query 분모가 분리된 search receipt, 독립 gate matrix를 권고했다.
- 비용 최적화는 measurement 완결 → search/cache provenance → router/search 품질 → P2 canary → prompt/token/model/concurrency 순서가 안전하다고 판정했다.

### 4. 선행 shadow 검토 (`gpt-5.6-sol/ultra`)

- 과거 코드는 fresh 결과와 authoritative `decision_id` 완전 일치를 강제해 stochastic divergence를 관측하기 전에 실패했다.
- public WAL을 쓰지 않는 additive observation mode와 구조화 drift receipt를 권고했다.
- 현재 소스에는 `FRESH_SEMANTIC_OBSERVATION_REQUIRED`와 `publication_shadow_observation`이 구현돼 있으므로, 과거 문제 설명은 현행 결함으로 재사용하지 않는다. 권고가 실제 구현으로 이어진 설계 이력으로만 기록한다.

### 5. 정확한 GPT-5.6 Sol + Pro 상태

- `agbrowse_bridge.py preflight --require-upload`에서 exact contract `family=gpt-5.6-sol`, `model=pro`, `effort=null`, composer/model/streaming/upload capability가 모두 `ok`였다.
- 기존 review lane은 2026-07-18의 `remaining-improvements-measurement-20260718` turn이 `provider.commit-not-verified` 뒤 `recovery_required`였다.
- 같은 turn을 재전송하지 않고 기록 session `01KXMBZAQJFVZBF2JYS3GMRS8N`만 복구했다. 초기 ownership lock 뒤 최종 복구는 성공했고 exact `GPT-5.6 Sol Pro` model picker evidence와 과거 2,590행 답변 hash `01349e44…e6a728c`를 확인했다.
- 과거 답변은 semantic verdict, dashboard status, evidence status를 분리하고, alias surface만으로 작품을 확정/거부하지 않으며, targeted snapshot을 전체 104,502행 승인으로 확대하지 말라는 의견이었다. 이는 현행 독립 gate·typed evidence·`full_scan_approval=false`와 일치하지만 2,590행 과거 범위이므로 현재 2,712 개선 효과의 새 독립 검토로 사용하지 않는다.
- lane active 복구 뒤 새 task `architecture-improvement-council-20260719`를 hard boundary와 verified selected bundle `13 files / 1,002,127 bytes`로 정확히 한 번 제출했다. provider transport가 `fetch failed`로 종료돼 `recovery_required`가 됐다.
- 동일 prompt를 재전송하지 않고 기록 session만 복구했으나 CDP 부재, headless 금지, 전용 headed Xvfb 재기동 뒤 provider status 미검증으로 끝났다. 현재 task의 검증된 새 Pro 답변은 없으므로 보고서의 현재 아키텍처 합의에는 계수하지 않는다.

## 합의

1. 공개 경로 비간섭·deterministic receipt 무결성은 GO다.
2. 의미 자동 activation, P1 실제 적용, P2 early route, full scan 승인은 NO-GO다.
3. AFTER의 변화는 descriptive signal이지 sidecar 적용 효과가 아니다.
4. 다음 구현은 의미 판정을 직접 바꾸기보다 finalizer seam과 공통 provenance를 동작 불변으로 먼저 분리해야 한다.
5. 실제 recovery 효과는 public WAL 복사본에만 가상 action을 적용하는 simulator arm에서 측정해야 한다.
6. 비용·속도 최적화는 계측·검색·semantic guardrail이 green 뒤에 수행한다.

## 이견과 범위 차이

- Opus의 P1 PASS와 Terra/Luna의 system NO-GO는 충돌이 아니다. 전자는 모듈 계약·unit test, 후자는 2,712 collateral과 32×3 effectiveness를 판정했다.
- Terra는 정상군 보호를 위해 다음 gate를 매우 보수적으로 잡았고, Luna는 measurement/search가 불완전한 동안 비용 수치 자체를 판단 보류했다. 최종 보고서는 둘 다 채택한다.
- 과거 Pro 의견은 verdict/dashboard/evidence 축 분리와 full-scope 과장 금지의 보조 근거로만 사용한다. 현재 task 답변은 미확보이므로 아키텍처 대안 표의 찬반에는 계수하지 않는다.

## 회의 결론

현재 구조는 “잘못된 새 결정을 공개하지 않게 막고 관측하는 능력”이 크게 좋아졌다. 반면 “위험한 의미 오류를 반복적으로 고치면서 정상 정답을 보존하는 능력”은 아직 입증되지 않았다. 권고안은 `PublicationFinalizer` 동작 불변 추출과 공통 observation envelope를 P0로, shadow intervention simulator를 P1로, 모든 gate가 green인 뒤 188건 P2 canary를 수행하는 것이다.

## 2026-09-02 P0 parser provenance 추가 재회의

Windows identity·process 격리 관점과 Python import-candidate 관점의 독립 검토를 다시 합쳤다. 경로 SHA를 held-handle SHA/128-bit file ID로 바꾸고 ancestor namespace guard, suspended child PID·creation time·reported image reopen을 ResumeThread 전에 확인하는 안은 `ADOPT_COMPONENT_ONLY`로 채택했다.

반면 고정 `.py` 4개를 source closure로 부르는 안은 기각했다. `-I -S -B`에서도 기존 `.pyc`가 load candidate이고, 같은 이름의 package directory·ABI `.pyd`·legacy `.pyc`, watcher arm 이전과 POST 이후의 swap 구간이 남기 때문이다. 다음 gate는 isolated empty pycache prefix, import collision exact inventory, source/parent/cache watcher continuity다. 상세 구현·검증은 [`P0_PARSER_PROCESS_HANDLE_PROVENANCE_REVIEW_20260902_KO.md`](P0_PARSER_PROCESS_HANDLE_PROVENANCE_REVIEW_20260902_KO.md)에 기록한다.

## 2026-09-02 P0 pycache·source observation successor 재회의

위 역사적 next gate는 후속 구현으로 좁게 닫혔다. local `LocalAppData` held anchor 아래 unique empty pycache, exact import collision inventory와 source parent·source/cache watcher를 결합해 `bounded_project_source_load_candidate_closure_verified=true`를 채택한다. 다만 MSIX redirection이 관측된 local anchor는 external owner pin이 아니고 watcher도 filesystem 비간섭 증명이 아니다. runtime/stdlib/native/loaded-image dependency closure, AppContainer/network/write deny, semantic parser와 actual 40+20은 미완료다. 판정은 `ADOPT_BOUNDED_PROJECT_SOURCE_LOAD_CANDIDATE_CLOSURE_COMPONENT_ONLY / PARSER_DEPENDENCY_CLOSURE_NO_GO / PARSER_SANDBOX_NO_GO`; 검증은 focused `48/48`, 전체 P0 `407/407`, 비간섭 `6/6`이다. 상세는 [`P0_PARSER_PROCESS_PYCACHE_SOURCE_OBSERVATION_REVIEW_20260902_KO.md`](P0_PARSER_PROCESS_PYCACHE_SOURCE_OBSERVATION_REVIEW_20260902_KO.md)를 따른다.

## 2026-09-02 external owner asymmetric signature 재회의

Windows CNG ECDSA P-256/SHA-256, RFC 5480 fingerprint, exact canonical preauthorization/domain/context와 low-S `r||s` 수학 검증을 좁은 컴포넌트로 채택했다. provider는 `Microsoft Primitive Provider`로 고정하지만 DLL/native provenance는 열지 않는다. pin·key·preauthorization 전체를 공격자가 일관되게 바꾸는 반례가 math true일 수 있으므로 external provisioning/owner authority는 기각한다. 판정은 `ASYMMETRIC_SIGNATURE_MATH_PASS / PRESENTED_PIN_ONLY / EXTERNAL_PROVISIONING_NO_GO / OWNER_STATE_NOT_YET_BOUND / TRUSTED_TIME_REVOCATION_DURABLE_NONCE_NO_GO / PARSER_SANDBOX_NO_GO`; 검증은 focused `15/15`, adjacent `78/78`, 전체 P0 `422/422`, 비간섭 `6/6`이다. 상세는 [`P0_EXTERNAL_OWNER_ASYMMETRIC_SIGNATURE_REVIEW_20260902_KO.md`](P0_EXTERNAL_OWNER_ASYMMETRIC_SIGNATURE_REVIEW_20260902_KO.md)를 따른다.
