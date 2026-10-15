# P0 owner preauth·packet supervisor 구현·재회의

작성일: 2026-09-02 KST
상태: `OWNER_PREAUTH_22_PASS / SUPERVISOR_17_PASS / CURRENT_FOCUSED_158_PASS / AUTHORITY_ADJACENT_182_PASS / SELECTED_ADJACENT_351_PASS / DIRECT_PACKET_EXECUTION_TRACE_PASS / EXTERNAL_TRUST_NO_GO`

후속 상태는 [authority raw·결합 supervisor 구현 및 전문가 재회의](P0_AUTHORITY_RAW_AND_COMBINED_SUPERVISOR_REVIEW_20260902_KO.md)를 따른다. 이 문서의 수치는 packet-only tranche 당시의 역사적 검증 기록이다.

## 결론

외부 owner가 capture 전에 허용할 root와 parser provenance를 표현하는 one-way supplement, 동일 Windows handle-captured packet bytes에서 validator를 직접 호출하는 packet-side supervisor를 구현했다. 기존 authority v2, bridge v1, fixture와 publication/WAL/Slang 경로는 수정하지 않았다.

채택 범위는 presented schema와 local execution observation이다. caller가 제시한 HMAC key와 code measurement는 외부 trust store나 독립 verifier가 아니다. Windows handles도 캡처·inventory 검사 뒤 닫히며 validator 실행 전 구간을 계속 감싸지 않는다. 따라서 external code/runtime/filesystem/owner trust, OS write-deny, runtime noninterference, authority와 credit은 모두 false/0이다.

## 구현

### Owner root preauthorization supplement

`p0_actual_owner_root_preauthorization.py`는 다음을 domain-separated HMAC material과 artifact self-hash에 포함한다.

- authority foundation/launch/기존 owner authorization/watch-spec SHA
- packet output root와 protected roots의 volume-GUID final path, volume serial, 128-bit file ID, access intent
- `CENTRAL_SLANG_DB`, `CHECKPOINT`, `DECISION_LEDGER`, `PUBLICATION_JOURNAL`, `RECOVERY`, `RESULT` exact 6 category map
- parser receipt schema, parser manifest/version, capture/input registry/source input plan/sampling frame
- manifest 1개와 child 13개, 총 14개 fixed packet member contract
- recursive watch, identity-per-member, journal continuity, overflow fail-close, independent observer 요구
- OS enforcement, parser principal write-deny, pre-watch 존재, terminal까지 유지 요구
- validity window, nonce, single-use 요구

성공 receipt는 `presented_internal_structure_verified=true`와 선택적인 `presented_observation_window_checked/match`만 올린다. external trust/revocation/replay/root-handle/namespace resolution/watch/write-deny/runtime authority는 false다.

### Raw 재사용 API

- Windows 모듈은 `read_windows_fixed_p0_packet_directory(...)`로 한 번 캡처한 raw와 handle receipt를 반환하고 `bind_windows_fixed_packet_observation(...)`가 filesystem 재접근 없이 packet validator 결과와 inventory를 결속한다.
- authority event 모듈은 `verify_annotation_event_bytes_from_bytes(...)`를 pure bytes core로 두고 기존 path API를 stable read wrapper로 유지한다.

### Packet-side supervisor

`execute_packet_supervisor_trace(...)`의 public 입력에는 serialized observation이나 child receipt가 없다. 실행 순서는 고정이다.

1. `READ_WINDOWS_FIXED_PACKET_DIRECTORY`
2. `VALIDATE_PACKET_BYTES`
3. `BIND_WINDOWS_FIXED_PACKET_OBSERVATION`
4. `VERIFY_A_EVENT_BYTES`

각 단계는 caller-pinned local module/callable measurement의 전후 일치, raw/result full/declared SHA, 이전 step SHA를 기록한다. execution genesis는 session, run, nonce commitment, root tuple, manifest pin, origin을 결속한다.

packet의 `source_claims.jsonl`은 전체 41개 claim이고 A-event validator는 선택된 Track A claim만 받는다. supervisor는 packet validator가 전체 raw를 통과한 뒤 A-context `source_claim_ids` union에서 선택 20개를 canonical JSONL로 파생한다. 현재 controlled packet의 projection은 전체 `41`, Track A `30`, 선택 `20`, 파생 `20`이다. 비선택 Track A 10개는 candidate pool로 보존하며 actual evidence로 세지 않는다.

## 전문가 적대 검토

### Owner preauth 회의

| 발견 | 보정 | 최종 경계 |
| --- | --- | --- |
| `str.isdecimal()`이 Unicode 동치 serial을 허용 | ASCII decimal regex와 canonical integer identity | Unicode serial reject |
| `observed_at` 생략 시 구조 성공을 시간 유효성으로 오해 | internal structure와 observation window checked/match 분리 | 미제공은 checked/match false |
| category `shared`와 `shared/nested` 허용 | effective root ancestor overlap 거부 | 문자열 기반 overlap만 증명 |
| 8.3/namespace alias를 문자열 비교로 해결 불가 | namespace resolution verified false | 실제 handle/external root verifier 전까지 미검증 |
| fixed inventory가 동적 목록에만 의존 | 총 14개 runtime assertion·test | manifest 1+child 13 |

재검토는 범위 제한 승인이다. HMAC math는 external owner identity가 아니며 nonce는 durable ledger에서 소비되지 않았다.

### Supervisor 회의

| 발견 | 보정 | 남은 경계 |
| --- | --- | --- |
| presented projection에 15번째 trailing member 수용 | `len(projection)==raw_member_count==14` | presented receipt는 여전히 실행 진실 아님 |
| nested `actual_authority_granted=true` 미탐지 | Mapping/list 재귀 forbidden-true 검사 | 악성 Python runtime 자체는 통제하지 않음 |
| root tuple/member와 A receipt/raw 교차결속 부족 | step0 root·14 member, step3 source/context/event/seal SHA·count·origin exact binding | authority-side raw는 아직 미실행 |
| session/run/nonce swap 후 reseal 가능 | execution genesis와 step0 input hash 결속 | nonce uniqueness는 외부 ledger 필요 |
| fake reader도 caller-self measurement로 local receipt 생성 가능 | `untrusted_local_execution_observation=true`, `caller_self_measurement_only=true` | owner-signed code pin·isolated runtime 전에는 external trust false |
| handle lifetime을 validator 실행 전체로 오해 | `handles_held_across_validator_execution=false` | OS/runtime noninterference false |

최종 판정은 `DIRECT_PACKET_EXECUTION_TRACE_PASS_EXTERNAL_TRUST_NO_GO`다. presented validator는 `PRESENTED_SUPERVISOR_RECEIPT_ONLY`이며 direct execution, underlying execution과 trust를 모두 false로 낮춘다.

## 검증

| 묶음 | 결과 |
| --- | --- |
| owner preauthorization | `22 PASS` |
| packet supervisor, Windows 실제 handle e2e 포함 | `17 PASS` |
| current focused | `Ran 158 tests in 6.423s / OK` |
| authority adjacent | `Ran 182 tests in 6.835s / OK` |
| expanded selected-adjacent | `Ran 351 tests in 29.853s / OK` |
| `py_compile` | `PASS` |
| `git diff --check` | `PASS`, CRLF 경고만 존재 |

calibration readiness 단독 테스트는 선행 label-ledger SHA drift로 setup fail-close했다. 기대 `717c6e…1102`, 현재 `b7e754…5998`이며 frozen artifact를 재생성하거나 새 SHA로 재결속하지 않았다.

authority v2 정본 SHA는 불변이다.

- manifest: `1a6e4af406dc687e5335773a443987703be0669478e4c4671bfe705f827985ed`
- final attestation: `b21e0e6ee2c180568d78bbda3602fccfad838c0ae873b67bdc4343e0146f9a5b`
- receipt: `3f692bc338dfecf9f7f721c4872c6240e2b6817a88d42e7957e84f4855df2d35`
- registry event receipt: `d62553a2042902b65403543e265fff3b65604dedc73615ff9306598971082dbe`

## 다음 채택 순서

1. authority v2 raw 14개, registry event, parser provenance와 terminal attestation을 같은 supervisor process에서 직접 검증해 packet trace와 결합한다.
2. run root 밖 owner trust store에서 key fingerprint·revocation·preauthorization을 확인하고 atomic single-use nonce reserve→consume ledger를 결속한다.
3. QPC monotonic phase chain, NTFS USN interval drain, `ReadDirectoryChangesExW` overflow witness, restricted parser-token write-open probe를 구현한다.
4. 실제 capture/parser shadow에서만 source claim 40건과 사람 A-context 20건을 수집한다.
5. 위 P0 Exit 뒤에만 Pyserini/gold-lite와 retrieval/reranker/NIL A/B를 시작한다.

현재 actual·credited count는 `0/40`, `0/20`이다. `p0_phase_exit=false`, `production_approval=false`, `full_scan_approval=false`를 유지한다.
