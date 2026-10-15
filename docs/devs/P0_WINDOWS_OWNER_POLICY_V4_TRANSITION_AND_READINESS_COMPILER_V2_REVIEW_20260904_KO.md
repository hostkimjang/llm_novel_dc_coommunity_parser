# P0 Windows owner policy V3→V4 전환과 readiness compiler V2 검토

## 판정

`PASS_WITH_LIMITATIONS / ADOPT_COMPONENT_ONLY / CURRENT_HOST_FIXED_STORE_NO_GO / ACTUAL_0_OF_40_0_OF_20 / P0_PHASE_EXIT_FALSE / PRODUCTION_NO_GO / FULL_SCAN_NO_GO`.

이번 tranche는 live V3 정책과 V4 epoch2 정책 사이의 byte 연속성을 독립 재생하는 parent validator, 두 고정 저장소를 한 held-handle 구간에서 관찰하는 zero-input Windows observer, 그 결과를 항상 차단 판정으로 컴파일하는 actual readiness blocker compiler V2를 추가했다. 현재 호스트에는 요구되는 fixed store가 없어 `failure_stage=FIXED_STORE`, `decision=NO_GO`가 정상 결과다.

이 결과는 외부 owner authority, actual semantic evidence, production 승인 또는 full scan 승인이 아니다. actual selected source claim은 `0/40`, actual A-context review는 `0/20`이며 두 credited count도 동일하게 0이다.

## 구성요소와 책임 경계

### V3→V4 transition parent validator

`p0_windows_owner_policy_v4_transition_parent_validator.py`는 파일시스템을 직접 읽거나 producer를 호출하지 않는 pure replay다. live V3 body·signature·operational pin과 V4 bundle의 6개 raw를 합친 exact 9-role bundle을 검증한다.

- live V3 계약 receipt를 독립 재구성한다.
- live V3 body/signature가 V4에 포함된 predecessor body/signature와 byte-exact하게 같은지 확인한다.
- V3 operational pin의 10개 필드와 owner/scope/anchor 결속을 재검증한다.
- supplied V4 child receipt와 supplied V4 parent replay receipt를 raw에서 다시 계산한 결과와 대조한다.
- predecessor epoch 1과 successor epoch 2, canonical P-256 SPKI, low-S P1363 서명 수학을 확인한다.

component manifest는 `467bf7cd295640846c61405d18b7711fa426c45b1b96612cbd3d68951917ba4d`다. 성공하더라도 gate는 `NO_GO_V3_V4_TRANSITION_PARENT_COMPONENT_ONLY`, effect는 `NONE_PURE_REPLAY`다.

### 21-role·9-file·3-watch fixed-store observer

`p0_windows_owner_policy_v4_transition_fixed_store.py`는 caller selector가 없는 zero-input read-only observer다. V3 8-role과 V4 13-role, 총 21개 역할 handle을 첫 파일 read 전에 모두 열고 9개 file role을 같은 held interval에서 읽는다.

watch scope는 `common_parent`, `v3_store`, `v4_store` 세 곳이다. 세 watch가 겹치는 구간에서 role identity, signed V3/live object identity, exact inventory, binary ACL, pre/post/reopen 안정성과 V3→V4 raw 연속성을 검사한다. 성공 경로도 external trusted key·time·revocation·durable nonce·root/code authority·OS write deny·runtime noninterference를 참으로 만들지 않는다.

component manifest는 `58b7c10801e95a11c322457e3286a228435f50128336eb75dc2e143251420ae2`다. gate는 `NO_GO_OWNER_POLICY_V3_V4_TRANSITION_COMPONENT_ONLY`, effect는 `NONE_READ_ONLY_COMPONENT_OBSERVATION`이다.

현재 호스트에는 fixed store가 없으므로 21-role success 경로 자체는 실증되지 않았다. 현재의 `FIXED_STORE / NO_GO`는 외부 입력 부재를 fail-close한 증거이지 정상 store 전환을 관찰했다는 증거가 아니다.

### actual readiness blocker compiler V2

`p0_actual_readiness_blocker_compiler_v2.py`는 transition observer를 같은 호출에서 정확히 한 번 실행하고 child receipt를 exact schema·truth table·self-hash 기준으로 검증한다. 전후에는 중앙 Slang DB 1개와 publication journal 5개의 fixed local endpoint를 point-in-time으로 관찰하고 exact path, bytes, SHA, mtime, inventory 비교를 기록한다.

compiler는 service를 시작하거나 process를 생성하지 않고, WAL·중앙 DB·production state에 쓰지 않으며 action을 적용하지 않는다. child가 성공·실패·invalid 중 어느 상태여도 최상위 판정은 항상 `NO_GO`이고 actual `0/40·0/20`을 유지한다.

component manifest는 `0c13c08c46850f6e2288b001b03b448b6460a8b8e9d82e70cd9379a7ce24060e`다. gate는 `ACTUAL_READINESS_V3_V4_TRANSITION_COMPILED_AUTHORITY_NO_GO`, effect는 `NONE_BLOCKER_COMPILATION_ONLY`다.

## 독립 red-team 반영

독립 반대검토에서 다음 결함을 재현하고 보강했다.

1. caller가 공급한 V4 parent replay receipt를 raw 재계산 결과와 strict 대조한다.
2. V3 operational pin을 fingerprint 일부가 아니라 10개 필드 전체로 body·owner·scope·anchor에 결속한다.
3. signed V3 object identity와 실제 live handle identity를 role별로 대조한다.
4. Known Folder class, `ntpath`, Win32 constants와 경로·handle 관련 dependency를 무결성 핀에 포함한다.
5. endpoint projection에서 exact path와 backslash traversal을 검증하고 coordinated projection/hash 재봉인을 거부한다.
6. 세 watch의 expected scope·경로·고유성·identity·completion을 strict 검증한다.
7. count·size·timestamp와 receipt scalar에서 `bool`을 허용하지 않고 exact `int` type을 요구한다.
8. raw marshal bytes로 실행순서를 추정하던 오판을 제거하고 code-object identity+stable digest 검증으로 교체한다.
9. public store boundary와 compiler 외부 dependency pin을 추가해 transition integrity checker의 no-op 변조를 거부한다.

serialized receipt와 self-hash는 tamper-evidence를 위한 구조적 값일 뿐 authority가 아니다. Fable-5 반대검토 시도는 empty output이어서 근거로 채택하지 않았다.

## 검증 결과

- 실행순서 stable-digest 스트레스: `1,000/1,000 PASS`.
- stress 뒤 current-host store와 compiler 각 2회: byte-deterministic `PASS`.
- 최종 store receipt: `1012a6b351b7b8ae2c035704461108b7bd33b45fc5b2cc3d57ee68877f7b5475`.
- 최종 compiler receipt: `f3537ed24ed3c8a897ef252e218ae7b492ebae62ee9a823aef2d0c143eb18d42`.
- 신규 transition parent·fixed-store observer·readiness compiler V2 focused: `40/40 PASS`.
- 관련 adjacent: `149/149 PASS`.
- 전체 P0: `982/982 PASS`.
- endpoint: 중앙 Slang DB 1개+publication journal 5개 `6/6` stable.
- noninterference: 6파일 unchanged, receipt `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`.
- 현재 호스트: fixed store 없음, store `FIXED_STORE / NO_GO`.
- actual source/context와 credited count: `0/40·0/20`.
- `p0_phase_exit=false`, `production_approval=false`, `full_scan_approval=false`.

이번 검증은 unit test, static contract 검증과 read-only host observation이다. regression-safe grounding actual test run이 아니므로 웹 dashboard와 `--parallel 16` 적용 대상이 아니다.

## 남은 gate

1. 외부 owner가 exact V3/V4 fixed store, 독립 key/pin, trusted time·revocation·durable nonce, root/code authority와 OS write-deny policy를 provision한다.
2. 동일 21-role held interval의 성공 경로와 signed native runtime witness를 실제 호스트에서 관찰한다.
3. 권리·retention이 승인된 raw source를 별도 root에 수집하고 source 40·A-context 20을 이중맹검으로 검토한다.
4. 위 gate 뒤에만 P0 Exit과 Pyserini BM25·gold-lite·reranker/NIL shadow를 검토한다. production과 full scan은 별도 승인 전 계속 닫는다.
