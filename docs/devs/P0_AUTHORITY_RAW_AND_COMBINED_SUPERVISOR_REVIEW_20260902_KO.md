# P0 authority raw·결합 supervisor 구현 및 전문가 재회의

일자: 2026-09-02
상태: `AUTHORITY_RAW_19_PASS / PACKET_SUPERVISOR_20_PASS / COMBINED_SUPERVISOR_12_PASS / DIRECT_ADJACENT_75_PASS / SELECTED_ADJACENT_385_PASS / DIRECT_LOCAL_AUTHORITY_BRIDGE_PASS / EXTERNAL_TRUST_NO_GO`

후속 tranche의 caller-keyless trust store·atomic nonce·Windows runtime witness 판정은 [`P0_EXTERNAL_TRUST_AND_RUNTIME_WITNESS_REVIEW_20260902_KO.md`](P0_EXTERNAL_TRUST_AND_RUNTIME_WITNESS_REVIEW_20260902_KO.md)를 우선한다.

## 결론

authority v2의 고정 14개 JSON 원문과 annotation event 원문을 같은 프로세스에서 직접 검증하는 executor를 추가했다. 이어 packet supervisor와 authority executor가 원문·parsed row·하위 validator 결과를 직렬화하지 않은 private immutable state로 보존하도록 바꾸고, owner root preauthorization → packet → authority → parser byte 결속 → provenance → terminal → final bridge를 고정 7단계로 직접 호출하는 결합 supervisor를 구현했다.

별도 coordinated ACTUAL fixture는 authority launch artifact SHA를 먼저 만든 뒤 동일 parser receipt를 packet과 authority 양쪽에 byte-for-byte 넣는다. controlled source 40건과 A-context 20건의 구조 검증, 실제 Windows handle capture를 포함한 결합 실행은 통과했다. 그러나 이 fixture와 HMAC key, 시간, root pin은 모두 테스트 호출자가 만들 수 있다. 따라서 실제 source evidence와 사람 판정은 계속 `0/40`, `0/20`, credited count도 `0/40`, `0/20`이다.

## 구현 범위

### Authority raw executor

- exact 14 filename/role inventory를 즉시 snapshot하고 각 원문의 bytes·SHA·순서를 결속한다.
- UTF-8 BOM, invalid UTF-8, nested duplicate key, non-finite constant, trailing JSON, non-object와 role swap을 fail-close한다.
- `validate_authority_foundation_bundle`과 `verify_annotation_event_bytes_from_bytes`를 serialized receipt 입력 없이 직접 호출한다.
- 하위 결과의 schema/origin/gate/authority/effect/count를 다시 검사해 self-rehashed fake `GO`, bool-as-int count와 capability injection을 거부한다.
- presented receipt validator는 구조만 확인하고 direct execution과 authority를 모두 false로 낮춘다.

Frozen authority example JSON은 사람이 읽는 pretty JSON이라 raw executor는 이를 재직렬화하거나 canonical bytes라고 주장하지 않는다. 대신 strict parse와 exact raw SHA를 보존한다. 결합 ACTUAL fixture의 preauth/provenance/terminal 및 새 authority raw는 별도 canonical JSON+LF 정책을 사용한다.

### Private execution state

- packet executor는 handle-captured manifest+13 child 원문, packet/Windows/A-event 결과와 public receipt를 private frozen state로 보존한다.
- authority executor는 14 raw 원문, parsed rows, foundation/event full result와 public receipt를 private frozen state로 보존한다.
- 두 private state는 `__all__`에 노출하지 않고 caller input으로 받지 않는다. 공개 API는 내부 참조가 없는 일반 `dict/list` receipt 사본만 반환한다.
- 따라서 presented receipt를 다시 제출해 직접 실행 증거로 승격하는 경로가 없다.

### 결합 supervisor

고정 실행 순서는 다음과 같다.

1. owner root preauthorization raw 검증
2. packet private supervisor 실행
3. authority raw private executor 실행
4. packet/authority parser receipt bytes·SHA·parsed object exact 결속
5. parser provenance authorization raw 검증
6. terminal bridge attestation raw 검증
7. 위 in-process 결과만 사용한 final authority bridge 직접 호출

public input은 packet directory/root tuple, authority/event/preauth/provenance/terminal raw, origin·foundation·session/run/nonce·measurement pin과 caller key뿐이다. packet/Windows/A-event/foundation/event/bridge receipt 또는 private state를 입력받지 않는다. step trace는 genesis, local measurement, input/output binding과 이전 step SHA를 결속한다.

## 전문가 회의 채택 판정

| 제안 | 판정 | 근거 |
| --- | --- | --- |
| authority 14 raw + event direct executor | `ADOPT_COMPONENT_ONLY` | 원문/결과 교차결속과 fake GO 차단은 유효하지만 external authority는 아님 |
| packet/authority private immutable state | `ADOPT` | serialized receipt 재입력으로 실행 사실을 위조하지 않고 final bridge가 같은 호출의 결과만 소비함 |
| coordinated ACTUAL 40+20 결합 fixture | `ADOPT_TEST_ONLY` | launch/parser/route/authority DAG 결속 회귀에는 유효하지만 테스트 작성자가 전체 bundle과 key를 만들 수 있음 |
| caller-local code measurement와 HMAC | `ADOPT_DIAGNOSTIC_ONLY` | 함수 교체와 수학 불일치는 잡지만 subordinate dependency, 외부 신원·trust store·revocation을 증명하지 않음 |
| combined local trace를 actual authority로 승격 | `REJECT` | trusted time, nonce 소비, 외부 root pin, OS witness, 실제 의미 증거가 없음 |
| Pyserini/gold-lite/A/B 착수 | `DEFER` | P0 Exit과 실제 40+20 전에는 시작하지 않음 |

## 명시적 신뢰 경계

결합 receipt가 true로 둘 수 있는 것은 exact raw inventory/SHA, strict parse, 같은 호출의 직접 validator invocation, fixed step trace, parser byte/semantic binding뿐이다. 다음은 모두 명시적으로 false다.

- `external_code_authority_verified`, `supervisor_runtime_trust_verified`
- `trusted_time_verified`, `nonce_uniqueness_verified`, `single_use_replay_consumed`
- `external_trust_store_verified`, `revocation_current_verified`, `external_owner_trust_verified`
- `filesystem_handle_binding_verified`, `filesystem_handle_trust_verified`, `external_root_identity_pin_verified`
- `windows_handle_capture_execution_provenance_verified`, `handles_held_across_validator_execution`
- `continuous_watch_verified`, `authority_journal_watch_bundle_verified`, `os_write_deny_verified`
- `parser_runtime_execution_verified`, `runtime_noninterference_verified`
- `durable_predecessor_verified`, `annotation_append_only_verified`, `actual_semantic_evidence_verified`
- `owner_authority_verified`, `actual_authority_granted`, `production_approval`, `full_scan_approval`, `p0_phase_exit`, `action_applied`

Packet parser receipt 내부의 `runtime_noninterference_verified=true`는 현재 route-complete 구조 계약을 위한 self-claim이다. 결합 supervisor는 이를 OS witness나 실제 parser 실행으로 승격하지 않고 최상위 두 필드를 false로 고정한다. 실제 Windows handle e2e가 통과해도 authority 14 raw와 보호 root 전체가 같은 handle/watch interval에 결속된 것은 아니므로 combined `filesystem_handle_binding_verified=false`다.

## Fresh 검증

| 범위 | 결과 |
| --- | --- |
| authority raw executor | `19 PASS` |
| packet supervisor, private-state/Windows e2e 포함 | `20 PASS` |
| combined supervisor, 실제 Windows handle e2e 포함 | `12 PASS` |
| packet supervisor + authority raw + bridge + combined | `Ran 75 tests in 3.654s / OK` |
| P0·observation·publication·Slang·calibration selected-adjacent | `Ran 385 tests in 32.665s / OK` |
| 관련 `py_compile` / `git diff --check` | `PASS` |

Authority v2 frozen SHA는 불변이다.

- manifest: `1a6e4af406dc687e5335773a443987703be0669478e4c4671bfe705f827985ed`
- final attestation: `b21e0e6ee2c180568d78bbda3602fccfad838c0ae873b67bdc4343e0146f9a5b`
- foundation receipt: `3f692bc338dfecf9f7f721c4872c6240e2b6817a88d42e7957e84f4855df2d35`
- event receipt: `d62553a2042902b65403543e265fff3b65604dedc73615ff9306598971082dbe`

이번 실행은 unittest/contract 검증이며 실제 데이터 수집·검증 run이 아니다. 따라서 `--parallel 16`·웹 dashboard 대상 런을 새로 시작하지 않았다. 기존 calibration readiness의 label-ledger 기대 SHA drift도 재생성하거나 현재 값에 재결속하지 않았다.

## 다음 작업

1. run root 밖의 owner trust store에서 key ID·anchor·validity를 읽고 revocation snapshot과 single-use nonce를 원자적으로 소비한다.
2. QPC monotonic chain, NTFS USN interval, `ReadDirectoryChangesExW` overflow/gap, restricted parser token write-open denial을 하나의 terminal runtime evidence bundle로 결속한다.
3. authority 14 raw와 6개 보호 category까지 trusted root/handle/watch 범위에 포함한다.
4. 위 외부 권위 gate가 통과한 전용 capture/parse shadow에서만 실제 source 40건과 사람 A-context 20건을 수집한다.
5. P0 Exit 전에는 중앙 Slang DB, publication WAL, production/full scan을 변경하지 않고 Pyserini·gold-lite·retrieval/reranker/NIL A/B를 시작하지 않는다.

현재 최종 판정은 `DIRECT_LOCAL_AUTHORITY_BRIDGE_PASS_EXTERNAL_TRUST_NO_GO / ACTUAL_EVIDENCE_0_OF_40_0_OF_20 / CREDIT_0_OF_40_0_OF_20 / p0_phase_exit=false / full_scan_approval=false`다.
