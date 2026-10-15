# P0 Windows external public-key pin candidate 구현·재회의

작성일: 2026-09-02 KST
상태: `ADOPT_COMPONENT_ONLY / ACL_BOUND_PIN_CANDIDATE_CONTRACT_PASS / CONTROLLED_SUCCESS_ONLY / ACTUAL_EXTERNAL_PROVISIONING_NO_GO / ACTUAL_0_OF_40_0_OF_20 / P0_PHASE_EXIT_FALSE`

## 결론

고정 파일명 `p0_external_owner_public_key_pin_v1.json`을 전용 디렉터리에서 Windows handle로 읽고, 그 exact bytes를 같은 호출의 CNG ECDSA 검증과 `OWNER_STATE` 소비에 넘기는 후보 supervisor를 구현했다. public API에는 pin raw bytes·receipt·expected owner SID·expected hash/file ID/final path·trusted callback/state를 받는 주입면이 없다.

이 구현은 다음의 좁은 실행 사실만 채택한다.

- pin file, store와 모든 lexical ancestor, caller run root, 서명된 packet root, 서명된 protected parent 및 6개 category root handle을 검증 구간 동안 유지한다.
- pin은 single-link·non-reparse·unnamed stream, 전용 fixed-name inventory, local volume-GUID path, persistent ACL filesystem 조건을 만족해야 한다.
- pin file과 store DACL은 present·non-NULL·protected여야 하며, 실제 effective thread impersonation token을 우선 사용해 mutation right별 `AccessCheck`가 모두 deny이고 owner membership도 false여야 한다. thread token이 없다는 `ERROR_NO_TOKEN`일 때만 process token으로 후퇴한다.
- packet은 서명된 final path·volume serial·file ID와 exact 일치해야 한다. protected parent도 같은 세 identity를 exact 일치시키고, category는 서명된 effective final path와 parent volume에 결속한다.
- store와 parent의 `ReadDirectoryChangesExW` interval, pre/post ACL·identity·inventory, path reopen을 함께 확인한다. token·watch·`LocalFree` 정리는 모두 시도하며 primary 오류를 정리 오류로 가리지 않는다.
- handle-read pin bytes, preauthorization raw SHA, signed root expectation, CNG/`OWNER_STATE` receipt를 같은 supervisor에서 교차 결속한다.

그러나 이것은 독립 owner 정책이 아니다. caller가 pin store 경로를 선택하며 실제로 verifier 밖에서 provision한 owner SID·ACE allowlist·key lifecycle 정책이 없다. 따라서 정상 후보 receipt도 `independent_owner_policy_state_verified=false`, `external_public_key_pin_provisioning_verified=false`, `owner_authority_verified=false`다.

## 실제 증거와 controlled 증거의 구분

| 증거 | 결과 | 해석 |
| --- | --- | --- |
| low-level hold mock을 사용한 same-call raw pin→CNG/`OWNER_STATE` | PASS | 후보 supervisor의 contract success. 실제 ACL/provisioning success가 아님 |
| current-user-owned Windows temp store | fail-close | 실제 root projection을 temp 경로에 맞춰 다시 결속한 뒤 DACL/owner 경계에서 거부 |
| signed protected parent 안의 sibling pin store | fail-close | 실제 Windows handle에서 parent overlap을 거부 |
| packet path/serial/file ID, protected parent file ID, category path/volume 변조 | fail-close | decoy root substitution 거부 |
| attacker가 key·pin·signature를 self-consistent하게 모두 교체 | 수학 PASS 가능, authority false | 독립 provisioning이 없으면 공격자 묶음을 owner authority로 승격하지 않음 |

실제 externally provisioned read-only store/key의 positive OS fixture는 아직 없다. present/protected DACL과 effective-token deny도 ACE 의미 allowlist나 독립 owner SID 정책을 증명하지 않는다.

## 전문가 재회의

| 의견 | 판정 | 반영 |
| --- | --- | --- |
| caller raw pin/receipt/expected SID·hash·identity를 policy로 수용 | `REJECT` | public API에서 제거 |
| process token만으로 `AccessCheck` | `REJECT` | effective thread token 우선, `ERROR_NO_TOKEN`만 process fallback |
| signed category path만 비교 | `REJECT` | packet 및 protected parent path·serial·file ID exact hold, category path·volume 결속 |
| pin store와 caller dummy root만 overlap 검사 | `REJECT` | signed packet/protected parent/category held roots까지 포함 |
| fixed-name inventory, held raw bytes, same-call CNG/`OWNER_STATE` | `ADOPT_COMPONENT_ONLY` | 후보 receipt에 실행 범위를 명시하고 authority 필드는 false 유지 |
| protected non-NULL DACL+effective deny를 exact owner policy로 간주 | `REJECT` | 독립 owner SID/ACE policy 미구현으로 기록 |
| candidate를 기존 nonce/runtime authority successor에 즉시 연결 | `DEFER` | 실제 external provisioning·time/revocation/durable nonce state plane 뒤에만 검토 |

Windows API 해석은 Microsoft의 [`GetSecurityInfo`](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo), [`AccessCheck`](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck), [File Security and Access Rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights), [`CreateFile`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea), [`GetFinalPathNameByHandle`](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlea)를 기준으로 삼았다. `GetSecurityInfo` 자체는 race protection을 제공하지 않으므로 held handle·pre/post snapshot·watch를 함께 사용했고, NULL DACL과 parent `FILE_DELETE_CHILD` 가능성을 명시적으로 거부했다.

## 검증

- focused: `14/14 PASS` (`3.791s`)
- asymmetric·fixed-directory·directory-watch 인접: `73/73 PASS` (`11.993s`)
- 전체 `test_p0*.py`: `453/453 PASS` (`32.457s`)
- `python -m compileall -q src/llm_batch/grounding tests`: PASS
- 중앙 Slang DB 1개와 publication journal 5개: `6/6` byte·SHA 불변
- noninterference receipt: `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`
- fixture receipt: `d94e1de3c5b4f8cd801804467fe82efed68ead1ec1b1abb986f48861a734545c`

이번 실행은 component unittest와 read-only audit이다. actual dataset run이 아니므로 dashboard와 `--parallel 16` manifest 적용 대상이 아니다.

## 다음 gate

presented-byte owner SID/ACE 계약과 binary ACL reader는 [후속 재검토](P0_WINDOWS_OWNER_POLICY_CONTRACT_REVIEW_20260902_KO.md)에서 구현했다. 이는 아래 1·2번의 실제 external provisioning/positive OS fixture를 충족하지 않으며 bootstrap signature·fixed live store·linked-token·rollback state도 계속 false다.

1. verifier와 현재 사용자가 소유하지 않는 전용 store, owner SID 및 exact ACE 정책, verifier 밖 private key를 실제 provision한다.
2. 실제 external positive OS fixture에서 effective-token deny·owner policy·key fingerprint와 rollback-resistant key epoch를 확인한다.
3. trusted time, revocation high-watermark, crash/reboot durable cross-process nonce를 같은 독립 state plane에 결속한다.
4. 그 뒤에만 pin+CNG 검증을 legacy nonce 소비보다 앞선 runtime successor에 연결한다.
5. parser AppContainer/LPAC, protected-root write/network deny, trusted runtime dependency closure와 actual semantic parser를 닫은 뒤 dashboard ON·`--parallel 16` 실제 40+20을 수행한다.

그 전 actual·credited는 `0/40`, `0/20`, `p0_phase_exit=false`, `production_approval=false`, `full_scan_approval=false`다. Pyserini, gold-lite, RRF/reranker/NIL A/B는 계속 P0 Exit 뒤로 보류한다.
