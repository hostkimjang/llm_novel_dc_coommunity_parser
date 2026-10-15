# P0 Windows external-owner policy 계약·binary ACL 재검토

## 결론

후속 `contract-only` 계층을 구현했다. `p0_windows_owner_policy_contract.py`는 strict canonical policy body와 detached signature envelope, policy epoch/predecessor, owner·verifier SID, operational key projection, 고정 generation 배치와 각 객체의 exact ACE 정책을 결속한다. `p0_windows_binary_acl_projection.py`는 held Windows handle의 binary security descriptor를 `GetSecurityInfo`, `IsValidSecurityDescriptor`, `IsValidAcl`, `GetAclInformation`, `GetAce`로 직접 읽는다. SDDL 문자열 해시는 exact ACE 증거로 사용하지 않는다.

게이트는 `OWNER_POLICY_CONTRACT_PASS_BOOTSTRAP_AND_PROVISIONING_NO_GO`다. presented body와 임의의 구조상 유효한 low-S 서명은 bootstrap signature 수학, 독립 public-key pin, 실제 store 발견·provisioning, live owner authority를 증명하지 않는다. actual·credited는 계속 `0/40`, `0/20`이며 `p0_phase_exit=false`, `production_approval=false`, `full_scan_approval=false`다.

## 전문가 재회의 판정

| 의견 | 판정 | 이유·반영 |
| --- | --- | --- |
| 기존 pin candidate receipt를 runtime supervisor 앞에 연결 | `REJECT` | candidate 호출이 끝나면 handle/watch가 닫히고 기존 runtime은 nonce를 먼저 소비하므로 TOCTOU와 receipt replay를 닫지 못함 |
| bootstrap policy key, signed policy, operational key, rollback state 분리 | `ADOPT` | offline bootstrap은 policy를, operational key는 preauthorization을 서명하고 epoch/revocation은 별도 durable broker가 보유 |
| caller가 policy path/bytes, bootstrap key, SID·ACE, expected context를 supervisor에 입력 | `REJECT` | caller가 trust root를 고르는 순환을 다시 만듦. 현재 함수는 presented-byte component validator일 뿐 successor authority API가 아님 |
| protected DACL과 현재 effective-token deny만 exact policy로 간주 | `REJECT` | 추가·inherited·callback·object ACE, linked elevated token, 다른 process principal을 배제하지 못함 |
| binary ACE type·flags·mask·SID·순서 exact 비교 | `ADOPT` | 첫 profile은 explicit standard `ACCESS_ALLOWED_ACE_TYPE` 두 개만 허용 |
| junk policy가 valid nonce를 먼저 소진 | `REJECT` | 실제 successor는 policy/pin/CNG/time/revocation/key-epoch preflight 뒤 durable nonce를 reserve해야 함 |
| nonce reserve 뒤 실패 시 rollback | `REJECT` | reserve 뒤 runtime·combined·cleanup 실패는 모두 영구 burn. commit 불명확도 재실행하지 않고 broker 상태를 조회 |

## 구현 계약

정책은 같은 volume serial의 다음 8개 role을 exact 순서로 선언한다.

1. `policy_store`
2. `generations_directory`
3. `generation_directory`
4. `policy_directory`
5. `pin_directory`
6. `policy_body_file`
7. `policy_signature_file`
8. `public_key_pin_file`

경로는 volume-GUID namespace, lowercase GUID와 path component, ASCII-safe component, DOS reserved device-name 거부, 고정 `generations/<20-digit epoch>/policy|pin` layout을 사용한다. case-sensitive NTFS의 별도 대문자 subtree를 같은 layout으로 간주하지 않는다. volume serial과 128-bit file ID, owner/group SID, DACL control bits, ordered ACE를 각 role에 결속한다. 중간 `generations`, `policy`, `pin` 디렉터리를 생략하지 않아 parent `DELETE_CHILD`·replacement 경계를 후속 live verifier가 검사할 수 있게 했다.

첫 ACL profile은 inherited/object/callback/conditional/resource/scoped/unknown ACE, generic rights, `MAXIMUM_ALLOWED`, duplicate/extra principal을 표현할 수 없다. 객체마다 다음 explicit ACE 두 개만 허용한다.

- owner: concrete `FILE_ALL_ACCESS=0x001F01FF`
- verifier file: concrete read-only `0x00120089`
- verifier directory: concrete list/traverse/read-only `0x001200A9`

owner anchor는 policy ID·epoch·predecessor뿐 아니라 store/project/trust/environment/purpose/bootstrap key ID, bootstrap fingerprint, verifier SID, 8개 object identity projection, ACL template, operational key, revocation floor, lifecycle를 함께 hash-bound한다. signature envelope는 완성된 policy body bytes SHA와 canonical 64-byte low-S P1363 구조를 결속한다. Base64 pad bits도 재인코딩 일치로 정규화한다. bootstrap key와 signature 수학은 아직 검증하지 않는다.

binary reader는 실제 Windows temp file의 owner/group/control/ordered standard allow ACE를 투영했다. pointer-width 밖 정수, pseudo handle과 non-disk handle을 거부하고 ACE pointer가 `AclBytesInUse`를 연속해서 exact 채우는지 확인한다. DACL present/defaulted control과 API projection의 불일치, platform/ctypes 예외도 fail-close한다. 현재 사용자 소유 파일은 외부 owner policy와 exact 비교할 때 거부됐다. reader가 caller handle을 받는 현재 계층은 live evidence 수집 부품일 뿐 독립 provisioning receipt가 아니다.

## 독립 red-team 반영

초기 구현은 focused test를 통과했지만 다음 반례를 수락했다. 최종 구현은 모두 fail-close 회귀로 고정했다.

- `False == 0`, `True == 1`을 이용한 ACE/signature epoch 타입 혼동
- 같은 64-byte signature로 해석되는 비정규 Base64 pad bits
- object별 상충 volume serial
- Backup Operators 등 `BUILTIN` alias SID와 SID revision 1 이외 값
- uppercase volume GUID, trailing-dot, Unicode 확장 `casefold()` 경로 alias
- project/store/trust/environment/purpose/object identity/revocation floor를 바꿔도 같았던 owner anchor
- unpaired surrogate, 5,000-digit integer, 1,500-depth JSON에서 계약 예외 대신 런타임 예외 누출
- non-inheriting ACL인데 `generations`, `policy`, `pin` 중간 디렉터리가 정책 role에서 빠진 문제
- `CON/NUL/COM1/LPT9` 예약명, 대소문자 별도 subtree, pointer truncation과 process/thread pseudo handle
- ACL 밖 ACE pointer, DACL present/defaulted projection 불일치와 platform 예외 누출

`LocalSystem` 또는 existing service SID는 policy owner의 구조상 후보로 남겨 둔다. 이는 external·narrow owner 증명이 아니다. 실제 positive gate는 independently pinned owner SID와 actual account type, verifier token의 user SID·group·privilege·elevation 상태를 live 검증해야 한다. local administrator/SYSTEM까지 공격자로 포함하면 ACL만으로 불변성을 증명할 수 없으며 WDAC/Authenticode와 TPM 또는 remote broker가 필요하다.

## 현재 Windows 감사

- 현재 user SID: `S-1-5-21-2702747403-714458307-1173059523-1001`
- token: medium integrity, `TokenElevationType=Limited`, `TokenIsElevated=0`
- Administrators: deny-only, 별도 linked elevated token 존재
- `SeRestorePrivilege`, `SeTakeOwnershipPrivilege`, `SeImpersonatePrivilege` 없음
- C: NTFS이지만 `HealthStatus=Warning`, `OperationalStatus=Full Repair Needed`
- 기존 externally-owned fixed-name pin/policy artifact와 privileged broker 없음

따라서 이 세션에서 current-user 밖 owner로 genuine positive store를 무승격 provision할 수 없다. OS account/ACL을 임의로 바꾸지 않았고 current-user temp fixture를 external positive로 세지 않았다.

## 검증

- focused owner-policy/binary ACL: `22/22 PASS` (`0.124s`)
- pin candidate·asymmetric·fixed-directory·directory-watch 인접: `95/95 PASS` (`11.974s`)
- 전체 `test_p0*.py`: `475/475 PASS` (`32.374s`)
- 신규 Python compile: PASS
- scoped `git diff --check`: PASS, `.gitignore` CRLF 경고만 존재
- 중앙 Slang DB 1개와 publication journal 5개: `6/6` byte·SHA 불변
- noninterference receipt: `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`
- fixture receipt: `d94e1de3c5b4f8cd801804467fe82efed68ead1ec1b1abb986f48861a734545c`

이번 검증은 component unittest와 read-only audit이다. actual dataset run이 아니므로 dashboard와 `--parallel 16` manifest 적용 대상이 아니다.

## 다음 gate

1. `SHGetKnownFolderPath(FOLDERID_ProgramData)` 또는 HKLM/service bootstrap으로 caller-injection-free fixed store discovery를 구현한다.
2. verifier/current-user 밖 owner가 bootstrap-signed policy·operational pin을 실제 provision하고 8개 role 및 모든 lexical ancestor를 held handle·watch로 감싼다.
3. binary ACL projection과 signed template를 exact 비교하고 actual verifier SID, process primary/effective/linked token, dangerous privilege와 mutator group membership을 fail-close한다.
4. independently pinned bootstrap key로 detached policy signature를 CNG 검증하고 policy→pin→preauthorization owner anchor/key epoch를 같은 호출에서 결속한다.
5. TPM/LocalSystem/remote broker의 trusted time, revocation·policy/key epoch high-watermark, crash/reboot durable nonce를 하나의 state plane으로 구현한다.
6. 위 preflight가 모두 끝난 뒤 nonce를 reserve하고 runtime/combined supervisor를 private authority lease로 호출한다. 그 전 legacy HMAC key/receipt 연결은 하지 않는다.
7. parser sandbox와 actual semantic evidence가 닫힌 뒤에만 dashboard ON·`--parallel 16` 실제 40+20을 수행한다.

Pyserini, gold-lite, RRF/reranker/NIL A/B는 계속 actual P0 전체 Exit 뒤로 보류한다.

## fixed-store 후속 재회의 정정

후속 live candidate 구현에서 두 계약 결함을 발견해 정정했다. 첫째, volume-GUID 경로 전체 lowercase 강제는 실제 `ProgramData` casing과 충돌했다. OS-owned prefix는 handle final path casing을 보존하고 `llm-novel-dc\p0-owner-policy-v1` 이하만 exact lowercase로 검증한다. 둘째, owner anchor에 pin byte hash를 넣고 pin에 owner anchor를 넣은 순환을 제거했다. owner anchor는 stable operational-key core만 포함하며 exact pin bytes/artifact는 signed policy body가 결속한다. 따라서 owner anchor는 core identity이고 full policy identity는 policy body bytes SHA다.

zero-input fixed-store candidate, held 8-role observation, ACL pre/post 16회, two-level watch와 lexical reopen은 [P0 Windows 고정 owner-policy 저장소 후보 구현·재회의](P0_WINDOWS_FIXED_OWNER_POLICY_STORE_CANDIDATE_REVIEW_20260902_KO.md)에 기록했다. 후속 [bootstrap policy 서명 수학 후보](P0_WINDOWS_BOOTSTRAP_POLICY_SIGNATURE_CANDIDATE_REVIEW_20260902_KO.md)는 math component를 통과했지만 actual external provisioning·독립 key pin·trusted code/provider와 authority는 계속 NO-GO다.

이후 [owner deployment projection v2](P0_WINDOWS_OWNER_DEPLOYMENT_PROJECTION_V2_REVIEW_20260902_KO.md)는 v1 의미를 바꾸지 않고 별도 v2 body/signature/owner-anchor/receipt로 trusted verifier 배포 계약을 추가했다. policy ACL verifier SID와 fixed service SID 분리 수락은 독립 감사에서 재현된 뒤 exact cross-binding으로 닫혔다. 이는 presented contract만 통과한 것이며 live SCM/token/image/WDAC/provider 관측과 external provisioning은 다음 gate다.

## 근거

- Microsoft [`AccessCheck`](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck)
- Microsoft [`GetSecurityInfo`](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- Microsoft [Access Control Lists](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-lists)
- Microsoft [ACE Strings](https://learn.microsoft.com/en-us/windows/win32/secauthz/ace-strings)
- Microsoft [Automatic Propagation of Inheritable ACEs](https://learn.microsoft.com/en-us/windows/win32/secauthz/automatic-propagation-of-inheritable-aces)
- Microsoft [Local accounts](https://learn.microsoft.com/en-us/windows/security/identity-protection/access-control/local-accounts)
- Microsoft [`SetNamedSecurityInfo`](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-setnamedsecurityinfow)
