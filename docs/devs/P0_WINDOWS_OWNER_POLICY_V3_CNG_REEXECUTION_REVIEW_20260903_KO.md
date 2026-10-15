# P0 Windows owner policy v3 CNG 재실행 구현 및 재회의

## 결론

아키텍처·Windows·red-team 재회의 결과, 이번 변경은 **`ADOPT_SAME_PROCESS_CNG_REEXECUTION_REJECTION_ONLY / POSITIVE_REJECTED / NO_GO`**로 채택한다. v3 successor는 fixed-store producer의 bootstrap 성공 receipt만 믿지 않고, 같은 held-handle snapshot에서 전달된 canonical body bytes와 raw detached-signature bytes로 bootstrap verifier와 Windows CNG를 한 번 더 실행한다. 새 receipt가 exact 계약을 통과하고 producer receipt와 canonical bytes 단위로 완전히 일치해야만 composite `bootstrap_signature_mathematics_verified=true`가 된다.

이는 동일 Python 프로세스·동일 코드·동일 source-compiled candidate key·동일 provider 선택 경계의 두 실행 일관성이다. 독립 verifier, trusted code/provider provenance, external owner authority 또는 actual semantic evidence가 아니다.

| 구분 | 최종 상태 |
| --- | --- |
| 현재 호스트 | receipt v2 `da914d27db0f1694c6d1fc65953bd74e8b93e186693847b493ab6c4196a1b1ad`, `FIXED_STORE / NO_GO`, CNG 재실행 미호출 |
| controlled signed v3 | 실제 Windows CNG 두 실행 일치 뒤 `POSITIVE_PROFILE / NO_GO` |
| coordinated low-S reseal | `BOOTSTRAP_CNG_REEXECUTION / NO_GO` |
| 기존 blocker compiler | `104d7c58271c7d7ae20d00badeb09185023eff344f37fe05eef1867d2c93a501`, credit `0/40·0/20` |
| P0 Exit / production / full scan | `false / false / false` |

## 재현된 기존 반례

수정 전에는 private producer를 교체해 다음 tuple을 반환하면 successor가 수용했다.

1. v3 raw signature envelope의 `signature_rs_base64`를 구조적으로 유효한 low-S `(r=3, s=4)`로 교체한다.
2. signature artifact와 raw signature SHA를 다시 계산한다.
3. contract, bootstrap, fixed receipt를 모두 self-consistent하게 재봉인한다.
4. fixed-store private triple handoff를 monkeypatch한다.

실제 재현 결과는 `POSITIVE_PROFILE`, `owner_policy_v3_contract_verified=true`, `bootstrap_signature_mathematics_verified=true`, receipt `6dfc5cb69d395db44ab884ff33ac545ce4f339cd07b90bb0f20827ac4b57b210`이었다. 구조·hash 일관성만 확인하고 compiled key에 대한 CNG 수학을 successor가 다시 실행하지 않은 것이 원인이었다.

## 구현한 상태기계와 truth table

`src/llm_batch/grounding/p0_windows_owner_policy_v3_preflight_candidate.py`의 receipt schema를 v2로 올리고 상태를 분리했다.

```text
FIXED_STORE
  → OWNER_POLICY_V3
  → BOOTSTRAP_CNG_REEXECUTION
  → POSITIVE_PROFILE / NO_GO
```

`_ValidatedV3Snapshot`은 검증된 canonical body bytes, exact raw signature bytes, producer bootstrap receipt canonical bytes만 frozen private context로 보존한다. 파일을 다시 열지 않으므로 snapshot bytes는 같지만 handles와 watches가 닫힌 뒤이며 store-host 단일 관찰 구간을 주장하지 않는다.

| 경로 | attempted | receipt contract | succeeded | exact match | composite math |
| --- | ---: | ---: | ---: | ---: | ---: |
| fixed store 부재 또는 v1/v2 hard reject | false | false | false | false | false |
| verifier 예외·invalid receipt | true | false | false | false | false |
| exact-shape/self-hash receipt지만 producer와 불일치 | true | true | false | false | false |
| 실제 CNG success receipt가 producer와 exact 일치 | true | true | true | true | true |

fresh receipt는 exact key set, self-hash, boolean/int truth table, 정수 credit 0, authority/action false, contract/hash/key/provider material을 다시 검증한다. 마지막으로 `hmac.compare_digest`를 사용해 canonical receipt bytes 전체를 producer receipt와 비교한다. 오류 메시지와 예외 종류는 public receipt에 반향하지 않는다.

## 전문가 회의 채택·기각

| 의견 | 판정 | 이유 |
| --- | --- | --- |
| producer receipt의 `bootstrap_signature_mathematics_verified`만 신뢰 | 기각 | producer-only coordinated reseal을 막지 못함 |
| same snapshot body/raw signature로 bootstrap verifier 재실행 | 채택 | private producer만 교체한 구조적 low-S 공격을 실제 CNG에서 차단 |
| verifier가 예외 없이 반환하면 성공으로 간주 | 기각 | forged/non-dict/credit/bool receipt와 monkeypatch 경계를 숨김 |
| fresh receipt exact 계약 + producer receipt canonical equality | 채택 | 실행 결과와 producer projection을 완전히 결속 |
| receipt contract validation을 CNG success로 기록 | 기각·수정 | red-team이 의미 과장을 발견해 `receipt_contract_validated`와 `succeeded`를 분리 |
| `independent/trusted CNG verification`으로 명명 | 기각 | 같은 프로세스·코드·compiled key·provider 선택의 반복일 뿐 독립 trust가 아님 |
| 기존 fixed-store 첫 CNG 실행 제거 | 기각 | v2/public fixed receipt 의미와 기존 producer 계약을 변경함 |

## 검증 근거

| 검증 | 결과 |
| --- | --- |
| v3 successor 단독 | `21/21 PASS` |
| fixed-store + native profile + v3 관련 | `48/48 PASS` |
| bootstrap + v3 | `32/32 PASS` |
| 전체 `test_p0*.py` | `568/568 PASS` |
| compile | 관련 source/test `PASS` |
| current v3 receipt | v2 `da914d27…a1b1ad`, 2회 결정적 |
| blocker compiler | `104d7c58…a501`, 2회 결정적 |
| 보호 엔드포인트 | 중앙 Slang DB 1개 + publication journal 5개 bytes·SHA `6/6` 기준 일치 |

controlled valid test는 ephemeral P-256 signer로 v3 signature material을 실제 low-S 서명한다. 테스트 범위에서 compiled key selector와 상수만 controlled key에 맞추고 bootstrap verifier 및 CNG primitive는 mock하지 않는다. 별도 공격 test는 production compiled candidate key에 대해 `(r=3,s=4)` coordinated receipt reseal을 실제 CNG로 거부한다.

이 검증은 component unittest와 read-only host preflight다. regression-safe grounding actual run이 아니므로 dashboard manifest나 `--parallel 16` 실행은 없으며 actual credit은 계속 `0/40 · 0/20`이다.

## 잔여 경계와 다음 gate

private producer와 bootstrap verifier 코드를 같은 프로세스에서 동시에 교체해 동일 forged receipt를 반환시키는 code-execution은 Python receipt 검증으로 막을 수 없다. 또한 source-compiled public key는 externally provisioned immutable owner trust root가 아니며 loaded CNG provider DLL/catalog, Python/PE code identity, Authenticode, active WDAC UMCI identity도 검증되지 않았다.

다음 positive gate 전에는 별도 owner 경계에서 signed v3 policy·native service·WDAC policy를 provision하고, TPM/KSP attestation·non-exportability, trusted time·revocation high-watermark, durable cross-process nonce/replay, single-interval store/service/token/image/provider 관찰을 닫아야 한다. 그 전까지 SCM/native IPC/actual launch, actual 40+20, Pyserini/gold-lite/reranker/NIL shadow, P0 Exit·production·full scan을 열지 않는다.
