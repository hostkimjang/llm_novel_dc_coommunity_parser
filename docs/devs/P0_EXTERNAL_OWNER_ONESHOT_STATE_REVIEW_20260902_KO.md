# P0 외부 owner one-shot `OWNER_STATE` 구현·재회의

작성일: 2026-09-02 KST

후속 [`P0_EXTERNAL_TRUST_STATE_IDENTITY_HARDENING_REVIEW_20260902_KO.md`](P0_EXTERNAL_TRUST_STATE_IDENTITY_HARDENING_REVIEW_20260902_KO.md)에서 아래 재현 debt를 object-identity registry로 교체하고 exact clone·failure-burn·PID/seal·GC·16-way race 회귀를 닫았다. 후속 전체 P0은 `439/439 PASS`이며 상위 authority 경계는 변하지 않는다.

## 결론

공개 asymmetric receipt를 downstream 실행 증거로 재입력하지 않고, 같은 호출의 `public_key_pin_bytes`, `signature_envelope_bytes`, `owner_root_preauthorization_bytes`를 CNG로 새로 검증한 뒤 module-issued private object identity를 정확히 한 번 소비하는 `OWNER_STATE` supervisor를 구현했다.

최종 판정은 다음과 같다.

`OWNER_STATE_PROCESS_LOCAL_HANDOFF_PASS / PUBLIC_RECEIPT_REENTRY_REJECTED / ARTIFACT_REPLAY_NO_GO / EXTERNAL_PROVISIONING_NO_GO / TRUSTED_TIME_REVOCATION_DURABLE_NONCE_NO_GO / ACTUAL_0_OF_40_0_OF_20 / PARSER_SANDBOX_NO_GO`

이 state는 **한 번의 fresh validation 결과를 같은 프로세스의 downstream 한 소비로 전달**한다. 같은 raw 3종을 다시 검증하면 새 state를 발급할 수 있으므로 signature artifact replay 방지나 durable nonce가 아니다. caller-held expected context도 독립 policy authority가 아니다. 따라서 owner authority, P0 Exit, production/full scan은 열리지 않는다.

## 구현 범위

대상은 다음 두 모듈이다.

- `src/llm_batch/grounding/p0_external_owner_asymmetric_signature.py`
- `src/llm_batch/grounding/p0_external_owner_state_supervisor.py`

구현 계약은 다음과 같다.

1. 공개 supervisor는 raw 3종과 exact fixed-field `expected_context`만 받는다. public receipt, state, seal, signer, callback, trusted-result 입력은 없다.
2. state는 canonical parse·self-hash·pin/envelope/preauthorization 교차결속·CNG signature 검증이 모두 성공한 뒤에만 발급한다.
3. `frozen=True, eq=False` private state, 재귀 동결 receipt, `id(state) → weakref(original)` registry를 사용한다. exact private dataclass clone도 원본 object identity가 아니면 거부한다.
4. 소비는 exact type 확인 뒤 lock 안에서 `state_ref() is state`를 확인하고 같은 lock에서 atomic pop한다. genuine state가 pop된 뒤 raw/context/seal/PID/receipt 검증이 실패해도 재사용할 수 없다.
5. registry는 raw 3종의 mutable 사본, 별도 random seal, receipt SHA, fixed context projection SHA와 issuer PID를 보관한다. 성공·실패·discard·GC finalizer에서 보관 buffer를 best-effort zeroing한다.
6. raw 역할·길이·SHA와 receipt SHA를 domain-separated binding으로 묶고 exact bytes도 constant-time 비교한다.
7. supervisor receipt의 `module_issued_owner_state_consumed_once=true`는 process-local 제어흐름 사실뿐이다. `single_use_replay_consumed=false`, `signature_freshness_verified=false`, `secure_memory_erasure_verified=false`를 유지한다.

## 전문가 재회의와 채택 판정

| 의견·공격 | 판정 | 반영 |
| --- | --- | --- |
| 기존 external-trust의 `seal_id → secret` 패턴 재사용 | `REJECT` | exact private dataclass clone이 보이는 seal id로 원본 secret을 대신 소비하는 공격을 실제 재현했다. 신규 state는 object identity+weakref로 변경했다. |
| `WeakKeyDictionary`만으로 동시 registry 관리 | `REJECT_AS_FINAL` | GC callback과 consume/discard의 registry 변경을 한 lock으로 직렬화하기 위해 `dict[id] + weakref.ref(original)`을 채택했다. |
| 검증 뒤 pop | `REJECT` | 두 thread 동시 성공 가능성이 있어 exact identity 확인과 atomic pop을 먼저 수행한다. |
| public receipt self-hash를 authority로 재입력 | `REJECT` | unkeyed hash는 공격자가 payload와 함께 재계산할 수 있다. 공개 supervisor 입력에서 receipt/state를 제거했다. |
| state 소비를 artifact replay 방지로 기록 | `REJECT` | 동일 raw 재검증으로 새 state가 생긴다. 별도 `module_issued_owner_state_consumed_once`만 true다. |
| raw 3종·receipt·security context 전체 결속 | `ADOPT` | project/session/run/parser-run, nonce, launch, key epoch/fingerprint, owner principal/anchor, root/provenance/watch/write-deny projection을 exact context로 고정했다. |
| arbitrary same-process attacker에 대한 보안 경계 주장 | `REJECT` | private registry를 읽거나 monkeypatch할 수 있는 임의 Python 코드 방어가 아니다. cooperative process-local control-flow seal로만 기록한다. |

재회의 중 기존 `p0_external_owner_trust_execution`의 seal-id state 복제 취약 패턴도 확인했다. 이 모듈은 상위 authority를 이미 false로 유지하지만 `module-issued exact object` 주장과 맞지 않았다. identity-hardening successor에서 같은 object-identity registry로 교체하고 clone 회귀를 추가해 닫았다.

## 공격·회귀 결과

| 범위 | 결과 |
| --- | --- |
| focused asymmetric+OWNER_STATE | `25/25 PASS` (`6.688s`) |
| direct adjacent | `91/91 PASS` (`10.531s`) |
| 전체 P0 | `432/432 PASS` (`27.928s`) |
| Python compile | 신규·변경 모듈과 테스트 `py_compile PASS` |
| 16-way state race | 정확히 `1 success / 15 already-consumed` |
| clone·namespace·serialized receipt | 모두 거부, genuine state는 이후 정상 소비 |
| raw/context/seal/PID tamper | 첫 시도 fail-close와 burn, 올바른 재시도도 already-consumed |
| lifecycle | success/failure/discard/GC에서 registry 기준값 복귀와 보관 buffer zero 확인 |
| 기존 상태 비간섭 | 중앙 Slang DB 1개+publication journal 5개 `6/6` byte·SHA 불변 |

비간섭 receipt SHA는 `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`, fixture aggregate SHA는 `d94e1de3c5b4f8cd801804467fe82efed68ead1ec1b1abb986f48861a734545c`, 중앙 DB SHA는 `a8c3fb9b083f6914e24bbede5adbbce73372f834dee4271611eefaaeeebcf10a`다.

이번 검증은 Windows component unittest와 기존 파일 read-only audit다. actual regression-safe pipeline run이 아니므로 dashboard와 `--parallel 16` 대상이 아니다. actual·credited는 계속 source claim `0/40`, A-context `0/20`이다.

## 계속 false인 상위 주장

- `signature_artifact_replay_prevented`
- `external_public_key_pin_provisioning_verified`
- `independent_readonly_public_key_pin_verified`
- `public_key_pin_rollback_protection_verified`
- `key_epoch_monotonicity_verified`
- `independent_context_policy_verified`
- `signature_freshness_verified`
- `external_owner_signing_key_verified`
- `private_key_outside_verifier_verified`
- `trusted_cng_provider_provenance_verified`
- `trusted_time_verified`
- `revocation_current_verified`
- `revocation_rollback_protection_verified`
- `durable_cross_process_nonce_verified`
- `power_loss_durable_replay_verified`
- `single_use_replay_consumed`
- `external_owner_trust_verified`
- `runtime_noninterference_verified`
- `owner_authority_verified`
- `actual_authority_granted`
- `p0_phase_exit`
- `production_approval`
- `full_scan_approval`

## 다음 P0 순서

1. `[완료]` 기존 external-trust one-shot state의 seal-id clone 문제를 object-identity registry로 교체하고 exact clone·16-way race·failure-burn 회귀를 추가했다.
2. run/protected root 밖 immutable read-only public-key pin, owner SID/ACL과 verifier 밖 owner signing key를 실제 provision한다.
3. signed revocation/key-epoch high-watermark, trusted time과 durable nonce를 하나의 rollback-resistant state plane에 결속한다.
4. owner-signed root/USN, AppContainer/LPAC, network/write deny, trusted CPython/stdlib/native provider provenance와 실제 semantic parser를 닫는다.
5. 그 뒤에만 dashboard ON·요청 `--parallel 16`으로 actual 40+20을 수집하고 사람 판정한다. Pyserini·gold-lite·RRF/reranker/NIL shadow A/B도 P0 Exit 전에 시작하지 않는다.

Goal은 `ACTIVE / NOT_COMPLETE`다.
