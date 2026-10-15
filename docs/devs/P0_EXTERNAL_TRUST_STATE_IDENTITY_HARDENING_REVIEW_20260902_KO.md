# P0 external-trust state object-identity 강화·재회의

작성일: 2026-09-02 KST

## 결론

기존 external-trust one-shot state의 `seal_id → key secret` registry를 제거하고, 원본 Python object identity와 weak reference를 결속한 exact-once state로 교체했다. 재회의에서 `dataclasses.replace(state)`로 만든 exact private clone이 기존 57-byte store key를 가져가고 genuine state를 소모하는 공격을 실제 재현했으며, 강화 뒤에는 clone consume/discard가 genuine registry 항목에 영향을 주지 않는다.

판정은 다음과 같다.

`TRUST_STATE_OBJECT_IDENTITY_PASS / EXACT_CLONE_REJECTED / PROCESS_LOCAL_KEY_HANDOFF_ONLY / PRESENTED_STORE_NONCE_SCOPE_ONLY / EXTERNAL_TRUST_AUTHORITY_NO_GO / TRUSTED_TIME_REVOCATION_DURABILITY_NO_GO / ACTUAL_0_OF_40_0_OF_20 / PARSER_SANDBOX_NO_GO`

이번 변경은 같은 프로세스에서 방금 실행한 caller-keyless trust-store 검증 결과와 key를 downstream 한 번에 전달하는 제어흐름 결함을 닫는다. trust store·HMAC key·wall clock·revocation snapshot이 caller-selected라는 기존 사실은 바뀌지 않는다. `single_use_replay_consumed=true`도 현재 pinned presented-store nonce ledger 범위일 뿐 external immutable ledger나 crash/reboot durability가 아니다.

## 재현된 결함

기존 state는 frozen private dataclass였지만 보이는 `_seal_id`만 보유했다. registry와 discard/consume도 exact type 검사 뒤 `_seal_id`로 secret을 pop했다. 따라서 다음 exact clone은 type 검사와 모든 receipt/key/nonce 결속을 통과했다.

```text
clone = dataclasses.replace(original_state)
same_private_type = true
different_object_identity = true
same_seal_id = true
clone_consumed_store_key = true
original_after_clone = already consumed
```

private 이름과 frozen dataclass는 object authenticity가 아니다. unkeyed receipt self-hash도 clone을 구별하지 못한다. 이 공격은 external authority를 새로 열지는 않았지만 `module-issued exact object`와 same-process key handoff 주장을 반박하므로 P0 수정 대상으로 채택했다.

## 구현 계약

대상 모듈은 `src/llm_batch/grounding/p0_external_owner_trust_execution.py`다.

1. state는 `@dataclass(frozen=True, eq=False)`이며 recursively frozen public receipt와 random `_execution_seal`만 보유한다. key는 state에 없다.
2. registry는 `dict[id(state), record]`이고 record의 `weakref.ref(original_state) is state`를 같은 lock 안에서 확인한다.
3. consume은 exact type 확인 → lock 내부 exact identity 확인+atomic pop → lock 해제 → PID/seal/receipt/context/expected receipt/nonce/key fingerprint 검증 → `finally` burn 순서다.
4. exact clone·copy·namespace는 registry miss로 거부하되 genuine state를 burn하지 않는다. genuine state가 pop된 뒤 malformed expected value나 receipt/seal/PID 결속이 실패하면 재사용할 수 없다.
5. receipt는 nested mapping/list까지 `MappingProxyType`/tuple로 동결한다. 강제 `object.__setattr__` 변조는 consume에서 receipt self-hash와 private context digest 불일치로 검출한다.
6. registry secret은 key와 별도 seal을 mutable bytearray로 보관한다. success/failure/discard/GC finalizer에서 두 buffer를 0으로 덮는다.
7. finalizer는 state를 strong capture하지 않고 state id·secret·당시 registry/lock만 보존한다. callback은 같은 record인지 lock 안에서 확인하고, interpreter 종료 lock 순서를 피하려 `atexit=false`다.
8. issuer PID가 현재 PID와 다르면 inherited/forked state를 pop·burn·거부한다. Windows-first component이므로 별도 fork broker 권한은 주장하지 않는다.

## 전문가 재회의 판정

| 의제 | 판정 | 근거와 제한 |
| --- | --- | --- |
| exact type+seal id | `REJECT` | exact dataclass clone이 genuine key를 소비하는 공격 재현 |
| object identity+weakref | `ADOPT` | clone/copy와 genuine object를 구분하며 id reuse는 live original identity 확인으로 차단 |
| lock 밖 검증 뒤 pop | `REJECT` | 동시 consumer 둘이 성공할 수 있으므로 lock 안 atomic pop을 먼저 수행 |
| malformed expected를 pop 전에 거부 | `REJECT` | genuine capability probe가 재시도 oracle이 되므로 identity pop 뒤 failure-burn |
| recursive receipt freeze | `ADOPT` | honest integration의 nested mutation을 차단하고 forced replacement는 digest로 탐지 |
| internal bytearray zeroing | `ADOPT_COMPONENT_ONLY` | 보관 key/seal buffer만 best-effort zero. 반환 bytes·Python allocator 전체 secure erasure는 아님 |
| state 강화를 external trust로 승격 | `REJECT` | caller-selected HMAC store/time/revocation과 local path는 독립 owner authority가 아님 |
| nonce ledger를 durable replay로 승격 | `REJECT` | Windows directory-entry power-loss, cross-process immutable ledger, rollback-resistant owner 미검증 |

## fresh 검증

| 범위 | 결과 |
| --- | --- |
| external owner trust focused | `37/37 PASS` (`2.974s`) |
| trust+Windows runtime+결합 supervisor | `62/62 PASS` (`6.605s`) |
| 기존 authority 75개 포함 direct adjacent | `137/137 PASS` (`10.436s`) |
| 전체 P0 | `439/439 PASS` (`28.243s`) |
| state race | 정확히 `1 success / 15 already-consumed` |
| lifecycle | success/failure/discard/GC/PID mismatch에서 registry 기준값 복귀와 private key/seal buffer zero 확인 |
| Python compile | 변경 모듈·테스트 `py_compile PASS` |
| 기존 상태 비간섭 | 중앙 Slang DB 1개+publication journal 5개 `6/6` byte·SHA 불변 |

비간섭 receipt SHA는 `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`, fixture aggregate SHA는 `d94e1de3c5b4f8cd801804467fe82efed68ead1ec1b1abb986f48861a734545c`, 중앙 DB SHA는 `a8c3fb9b083f6914e24bbede5adbbce73372f834dee4271611eefaaeeebcf10a`다.

이 검증은 component unittest와 기존 파일 read-only audit다. actual regression-safe data run이 아니므로 dashboard와 `--parallel 16` 대상이 아니다. actual·credited는 계속 source claim `0/40`, A-context `0/20`이다.

## 계속 false인 상위 주장

- `external_trust_store_verified`
- `revocation_current_verified`
- `trusted_time_verified`
- `cross_process_immutable_nonce_ledger_verified`
- `power_loss_durable_replay_verified`
- `external_owner_trust_verified`
- `external_root_identity_pin_verified`
- `filesystem_handle_trust_verified`
- `runtime_noninterference_verified`
- `os_write_deny_verified`
- `parser_runtime_execution_verified`
- `owner_authority_verified`
- `actual_authority_granted`
- `p0_phase_exit`
- `production_approval`
- `full_scan_approval`

## 다음 P0 순서

1. run/protected root 밖 immutable read-only asymmetric public-key pin과 owner SID/ACL, verifier 밖 owner signing key를 실제 provision한다.
2. caller-selected HMAC state와 presented ECDSA component를 하나의 독립 owner state plane으로 대체한다. key epoch·signed revocation high-watermark·trusted time·rollback 방지·durable nonce를 함께 결속한다.
3. owner-signed root/USN, AppContainer/LPAC no-capability, network/protected-root write deny와 trusted CPython/stdlib/native provider provenance를 닫는다.
4. adversarial Windows E2E와 실제 source-profile semantic parser를 통과한다.
5. 그 뒤에만 dashboard ON·요청 `--parallel 16`으로 actual 40+20을 수집·사람 판정한다. Pyserini·gold-lite·RRF/reranker/NIL shadow A/B는 P0 Exit 전 시작하지 않는다.

Goal은 `ACTIVE / NOT_COMPLETE`다.
