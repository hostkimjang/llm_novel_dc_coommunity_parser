# P0 Windows owner policy v3 successor preflight 구현 및 최종 재회의

## 결론

아키텍처·Windows 경계·red-team 재회의 결과, 이번 변경은 **`ADOPT_REJECTION_ONLY_V3_SUCCESSOR / POSITIVE_REJECTED / NO_GO`**로 채택한다. 채택 대상은 owner policy v3의 구조와 서명 바인딩을 더 엄격히 확인하는 별도 preflight 및 presented native observer component를 positive로 사용하지 못하게 하는 거부 분류기다. 이는 owner authority, actual semantic evidence 또는 P0 통과를 추가한 변경이 아니다.

> 2026-09-03 후속: 이 문서에서 남겼던 producer CNG 결과 신뢰 부채는 successor receipt v2의 same-snapshot CNG 재실행과 fresh receipt exact equality로 닫았다. 이는 동일 프로세스 두 실행 일관성일 뿐 독립 code/provider/owner trust는 아니다. 최신 판정과 검증은 [`P0_WINDOWS_OWNER_POLICY_V3_CNG_REEXECUTION_REVIEW_20260903_KO.md`](P0_WINDOWS_OWNER_POLICY_V3_CNG_REEXECUTION_REVIEW_20260903_KO.md)를 따른다.

| 구분 | 최종 상태 |
| --- | --- |
| 현재 호스트 | `FIXED_STORE / NO_GO` |
| 유효 v3 fixture | `POSITIVE_PROFILE / NO_GO` |
| presented component | negative와 selected no-explicit-negative 모두 `POSITIVE_REJECTED` |
| actual credit | source claim `0/40`, A-context review `0/20` |
| P0 Exit / production / full scan | `false / false / false` |
| operational effect | rejection-only, protected state mutation 없음 |

## 별도 v3-only 상태기계

`src/llm_batch/grounding/p0_windows_owner_policy_v3_preflight_candidate.py`는 기존 v2 preflight 및 blocker compiler와 분리된 zero-input 상태기계다.

1. `FIXED_STORE`: 고정 ProgramData store를 private same-call handoff로 한 번만 관측한다. store가 없거나 exact receipt·inventory·watch·credit truth table이 맞지 않으면 즉시 `FIXED_STORE / NO_GO`다.
2. `OWNER_POLICY_V3`: v1/v2 입력을 hard reject하고, v3 body/signature/contract/bootstrap receipt의 exact key set, canonical hash, schema/domain, body-derived identity, deployment/profile, 네 key role 분리를 교차 검증한다. 실패하면 `OWNER_POLICY_V3 / NO_GO`다.
3. `POSITIVE_PROFILE`: 현 v3 contract의 `future_authority_policy_version_eligible=false`와 `positive_native_observer_policy_profile_complete=false`를 정확히 요구한다. 유효 v3를 확인해도 SCM·native IPC·actual launch를 시도하지 않고 `POSITIVE_PROFILE / NO_GO`에서 정지한다.

실패 receipt의 gate status는 component verified를 선행 주장하지 않는 중립적인 `WINDOWS_OWNER_POLICY_V3_PREFLIGHT_EXECUTED_POSITIVE_NO_GO`다. v3를 읽지 못한 경로는 `POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_NOT_VERIFIED`, 유효 v3를 읽은 경로만 `POSITIVE_NATIVE_OBSERVER_POLICY_PROFILE_INCOMPLETE`를 기록한다.

## positive rejection 경계

`src/llm_batch/grounding/p0_windows_native_observer_positive_predicate_candidate.py`의 public API는 이름부터 `reject_presented_windows_native_observer_component_candidate`로 고정했다. 같은 호출에서 strict component validator를 실행하고 exact receipt truth table을 다시 확인하지만, 결과를 authority로 승격하지 않는다.

- service 미실행, Authenticode 실패, UMCI 미강제, TPM/nonce/trusted-time 미관측 등 명시적 negative projection은 `PRESENTED_NEGATIVE_RUNTIME_EVIDENCE / POSITIVE_REJECTED`다.
- 선택된 runtime flag에서 명시적 negative가 보이지 않는 transcript도 expected image·catalog·WDAC·provider·owner state의 독립 신뢰를 증명하지 못하므로 `PRESENTED_COMPONENT_ONLY / POSITIVE_REJECTED`다.
- serialized component receipt, self-hash, 서명 수학 성공은 positive input이나 actual credit이 아니다.

따라서 component validator 성공은 “presented 구조와 두 서명 수학이 일치한다”는 뜻에 한정되며, negative와 no-explicit-negative 어느 쪽도 GO 경로가 없다.

## raw detached-signature private handoff

`src/llm_batch/grounding/p0_windows_fixed_owner_policy_store_candidate.py`는 v3 successor 전용 private triple handoff에서 held handle로 읽은 raw detached-signature bytes를 body 및 fixed receipt와 함께 보존한다. successor는 이 raw bytes로 다음을 독립 재계산한다.

- signature byte length와 SHA-256
- canonical v3 signature envelope와 body hash/domain/key binding
- signature artifact SHA
- contract, nested bootstrap receipt, fixed receipt 사이의 byte/artifact hash 일치

이 경계는 contract와 nested receipts를 함께 self-consistent reseal해 signature hash를 바꾸던 감사 공격을 닫는다. 기존 v2 private pair API는 triple 결과에서 signature bytes만 제거해 동일한 `(receipt, body)`를 반환하며, public fixed-store receipt schema와 값도 변경하지 않았다.

다만 handle과 directory watch는 handoff 전에 닫힌다. 따라서 successor가 store·SCM·process·WDAC·provider를 하나의 atomic interval로 관찰했다고 주장하지 않는다.

## 전문가 회의 채택·기각 의견

| 의견 | 판정 | 이유 |
| --- | --- | --- |
| 기존 v2 preflight/blocker compiler에 v3를 묵시 수용 | 기각 | v2 exact 의미와 회귀 receipt를 오염시키며 v3 profile 경계를 표현하지 못함 |
| 별도 v3-only successor | 채택 | v1/v2 hard reject와 v3 불완전성을 독립 상태기계로 표현 |
| component validator 성공을 positive로 사용 | 기각 | negative projection도 구조적으로 유효할 수 있고 independent provisioning·freshness·replay를 증명하지 못함 |
| negative/no-explicit-negative를 모두 명시적으로 거부 | 채택 | 현재 schema에서 가능한 유일한 안전한 positive predicate |
| serialized receipt/self-hash를 authority로 사용 | 기각 | caller-controlled reseal과 replay를 막지 못함 |
| raw signature private same-call handoff와 독립 재계산 | 채택 | receipt-only mix-and-match 및 signature hash reseal 경계를 닫음 |
| profile incomplete 상태에서 SCM·IPC·launch 진행 | 기각 | 관찰 범위를 넓혀도 누락된 owner trust를 보충하지 못하고 상태 의미만 흐림 |
| component test 결과를 actual 40+20으로 credit | 기각 | actual source unit, A sampling unit, dashboard manifest가 없는 단위/경계 검증임 |

## 검증 근거

부모 task에서 최종 코드 기준으로 다음 결과를 확인했다.

| 검증 범위 | 결과 |
| --- | --- |
| 전체 P0 회귀 `test_p0*.py` | `564/564 PASS` |
| 초기 관련 인접 subset | `55/55 PASS` |
| 확장 인접 회귀 | `66/66 PASS` |
| 최종 raw-signature·rejection 경계 focused | `44/44 PASS` |
| 이 tranche 당시 호스트 zero-input 실행 | receipt v1 `1323f951bdf6ae9da3e7c9634719ed4634131eb68ab4d6d2c6a6ab1d09b4a2ac`, `FIXED_STORE / NO_GO`, 2회 결정적; 최신 v2는 후속 문서 참조 |
| 기존 blocker compiler | receipt `104d7c58271c7d7ae20d00badeb09185023eff344f37fe05eef1867d2c93a501`, 2회 결정적, credit `0/40·0/20` |
| 보호 엔드포인트 | 중앙 Slang DB 1개와 publication journal 5개 bytes·SHA `6/6` 기준 일치 |
| 유효 v3 fixture 상태기계 | `POSITIVE_PROFILE / NO_GO` |

이 검증은 Python component unittest와 read-only host preflight다. regression-safe grounding actual run이 아니며, 실제 입력 40+20, `--parallel 16` manifest 또는 웹 dashboard를 생성하지 않았다. 따라서 dashboard가 없다는 사실은 누락이 아니고 actual credit은 계속 `0/40 · 0/20`이다.

## 후속에서 보정된 producer·CNG trust boundary

이번 강화는 raw signature와 receipts의 내부 일관성을 닫았지만 독립 authority를 만들지는 않는다.

- 이 문서 채택 시점에는 bootstrap CNG 수학 검증을 fixed-store producer에 의존했다. 후속 receipt v2는 동일 snapshot bytes로 같은 프로세스 CNG를 재실행하고 producer receipt와 exact 비교한다. private producer만 조작하는 coordinated reseal은 닫혔지만 동일 프로세스의 producer와 verifier 코드를 함께 교체하는 침해는 여전히 신뢰 경계 밖이다.
- bootstrap key는 source-compiled candidate이며 외부 owner가 독립 provision한 immutable trust root가 아니다.
- Python producer와 현재 프로세스의 code identity, loaded CNG provider provenance, Authenticode/catalog membership, active WDAC UMCI policy identity가 독립 검증되지 않았다.
- TPM/KSP hardware backing·non-exportability·attestation, trusted time·revocation high-watermark, crash/reboot-safe durable nonce와 replay consume가 없다.
- fixed store, service PID/token/image, resource, WDAC, provider/catalog, owner state가 하나의 held/watch interval로 결속되지 않았다.

이 잔여 경계가 닫히기 전에는 `actual_authority_granted`, `actual_semantic_evidence_verified`, `p0_phase_exit`, `production_approval`, `full_scan_approval`, `action_applied`, `protected_pipeline_state_mutated`를 모두 `false`로 유지한다. 실제 40+20은 별도 전문가 재회의 후 dashboard ON·`--parallel 16` actual run으로만 시작할 수 있다.
