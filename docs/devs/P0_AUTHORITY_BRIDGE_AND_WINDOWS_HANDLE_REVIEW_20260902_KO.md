# P0 authority bridge·Windows handle 구현·재검토

작성일: 2026-09-02 KST
상태: `HISTORICAL_TRANCHE / A_EVENT_13_PASS / WINDOWS_14_PASS / BRIDGE_24_PASS / CURRENT_TRANCHE_FOCUSED_115_PASS / AUTHORITY_ADJACENT_134_PASS / CURRENT_SELECTED_ADJACENT_299_PASS / HANDLE_BINDING_PASS / STRUCTURAL_PRESENTED_RECEIPT_BINDINGS_ONLY / EXTERNAL_TRUST_NO_GO`

## 결론

A-event 원문 바이트, packet receipt v2, authority one-way bridge, Windows fixed-directory handle reader를 구현하고 두 차례 독립 red-team을 거쳤다. 동일 handle 집합에서 읽은 14개 packet member와 manifest inventory의 결속, packet/A/authority/Windows receipt 사이의 terminal cross-binding은 채택한다.

채택 범위는 구조적이다. Windows bounded reader receipt만 `filesystem_handle_binding_verified=true`이고, serialized bridge는 제시된 receipt 사이의 일관성만 확인한다. caller가 직전 관측한 root tuple을 다시 넣을 수 있고 bridge가 모든 하위 validator 실행 provenance를 직접 증명하지 않으므로 `filesystem_handle_trust_verified=false`, `external_root_identity_pin_verified=false`, `underlying_validator_execution_verified=false`다.

외부 actual source claim과 사람 A-context review는 `0/40`, `0/20`, credited count도 `0/40`, `0/20`이다. OS write-deny·USN/watch·runtime noninterference·owner authority·P0 Exit·production·full scan은 모두 false다.

## 구현

| 구성요소 | 구현 내용 | 증명하지 않는 것 |
| --- | --- | --- |
| A-event raw verifier | source claim/context/event/subject seal canonical UTF-8/LF, duplicate key, event chain, latest head 20개 재계산. context 20개와 event 최소 20개를 분리해 21번째 recheck 허용 | durable predecessor, append-only OS ledger, owner/runtime authority |
| packet receipt v2 | receipt self-hash와 route/parser/A-context/A-seal/source plan/sampling frame/parser manifest·version·launch·capture projection | owner-authorized parser provenance |
| authority bridge | parser preauthorization과 terminal attestation으로 packet v2, A-event, registry event, authority final, Windows composite/root tuple을 교차 결속 | 하위 validator 실행 provenance, 외부 trust, credit/승인 |
| Windows reader | ancestor/root/14 member handle 동시 유지, volume-GUID final path, volume serial, 128-bit file ID, reparse/hardlink/ADS, entry↔handle metadata, before/after와 second inventory | OS ACL write-deny, 과거·미래 write 부재, USN continuity |
| Windows composite | handle member와 packet manifest의 14개 `{role,path,bytes,sha256}` exact projection, declared receipt hash와 full canonical hash 분리 | external owner root pin |

Windows 구현은 `GetFileInformationByHandleEx`의 file ID/extended directory information과 `CreateFile`의 `OPEN_REPARSE_POINT`·sharing semantics를 사용한다. 참고한 공식 문서는 [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex), [FILE_ID_EXTD_DIR_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_extd_dir_info), [CreateFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea)다.

child는 root handle을 `RootDirectory`로 쓰는 native relative open이 아니다. root handle inventory를 얻은 뒤 absolute volume-GUID path로 reopen하고 enumeration의 128-bit file ID와 child handle ID를 교차검증한다. 문서와 receipt에서 이를 root-handle-relative open으로 부르지 않는다.

## 전문가 재회의

첫 Windows red-team은 caller 관측 root tuple을 다시 pin할 수 있는데 초기 receipt가 `filesystem_handle_trust_verified=true`를 반환한 것을 과대 주장으로 판정했다. 이를 다음처럼 수정했다.

- Windows bounded reader: `filesystem_handle_binding_verified=true`
- 외부 authority 층: `filesystem_handle_trust_verified=false`
- owner root provision: `external_root_identity_pin_verified=false`
- OS/runtime 층: `os_write_deny_verified=false`, `runtime_noninterference_verified=false`

두 번째 bridge red-team은 terminal 서명 범위, declared/full receipt hash, packet/A/Windows swap 방어는 닫혔다고 평가했다. 다만 bridge는 serialized receipt를 받아 self-hash와 projection을 검사할 뿐, owner anchor/launch/route/registry event를 포함한 모든 하위 strict validator를 raw bytes/handle에서 직접 다시 실행하지 않는다. 따라서 다음 의미 축소를 채택한다.

- `binding_scope=STRUCTURAL_PRESENTED_RECEIPT_BINDINGS_ONLY`
- `presented_receipt_cross_bindings_verified=true`
- `underlying_validator_execution_verified=false`
- `untrusted_observation=true`
- bridge 자체의 `filesystem_handle_binding_verified=false`

이 잔여점은 현재 privilege escalation이 아니다. bridge 결과의 credit·authority·승인 필드가 항상 false/0이기 때문이다. 다만 future authority 승격 전에는 raw bytes/handle에서 하위 validator를 supervisor가 직접 실행하거나, 독립 verifier code measurement/key가 서명한 receipt만 받아야 한다.

## 검증

정본 환경은 `.venv312`다.

| 묶음 | 결과 |
| --- | --- |
| A-event raw verifier | `13 PASS` |
| Windows integration/composite | `14 PASS` |
| authority bridge unit | `24 PASS` |
| A-context+route+packet+A-event+Windows+bridge | `Ran 115 tests in 5.001s / OK` |
| authority v2+registry event+route+packet+A-event+Windows+bridge | `Ran 134 tests in 5.315s / OK` |
| expanded selected-adjacent | `Ran 299 tests in 13.520s / OK` |

expanded selected-adjacent는 actual registry/authority/A/route/packet/Windows/bridge, observation envelope, framed WAL, publication shadow/decision/finalizer, Slang governance/transaction, calibration actual readback/contract를 포함한다. calibration dataset readiness를 추가한 확대 시도는 선행 label-ledger SHA drift로 setup fail-close했다. frozen artifact는 재생성하지 않았다.

선행 key-less packet의 `285 PASS`는 `PRE_TRANCHE_SELECTED_ADJACENT_285_PASS` 역사 값이다. 신규 test 수와 단순 합산하지 않는다.

## 보존된 정본 SHA

authority v2와 fixture는 변경하지 않았다.

- authority manifest: `1a6e4af406dc687e5335773a443987703be0669478e4c4671bfe705f827985ed`
- unsigned final attestation: `b21e0e6ee2c180568d78bbda3602fccfad838c0ae873b67bdc4343e0146f9a5b`
- authority receipt: `3f692bc338dfecf9f7f721c4872c6240e2b6817a88d42e7957e84f4855df2d35`
- registry event-byte receipt: `d62553a2042902b65403543e265fff3b65604dedc73615ff9306598971082dbe`

이 SHA는 example/schema foundation의 정본이지 실제 owner authority가 아니다.

## 남은 P0 순서

1. raw packet/A-event/registry-event/authority/Windows 입력에서 strict validator를 실제 실행한 supervisor 또는 독립 verifier provenance를 결속한다.
2. run root 밖 trust store에서 owner anchor/key fingerprint/revocation을 조회하고 root tuple·category→root·expected manifest/parser provenance를 capture 전에 서명한다.
3. 독립 OS write-deny와 USN/journal/watch interval을 구현한다.
4. `PRE auth/root pin → capture → handles/inventory/read → validators → final → terminal`을 boot/session·monotonic sequence·nonce ledger로 결속한다.
5. 그 뒤 전용 shadow에서만 실제 40+20을 수집한다.

현재 판정은 `NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED / p0_phase_exit=false / production_approval=false / full_scan_approval=false`다. Pyserini, gold-lite, reranker/NIL A/B는 P0 Exit 뒤에만 시작한다.

## 후속 supersession

이 문서의 `115/134/299`는 bridge·Windows handle tranche 종료 시점의 역사 결과다. 이후 owner root preauthorization supplement, Windows observation bind helper, authority-event bytes core와 packet-side supervisor를 구현·red-team 보정했다. 최신 결과와 다음 순서는 [P0 owner preauth·packet supervisor 구현·재회의](P0_OWNER_PREAUTH_AND_PACKET_SUPERVISOR_REVIEW_20260902_KO.md)를 따른다. 최신 gate도 external trust·authority·credit을 열지 않는다.
