# P0 Windows 고정 owner-policy 저장소 후보 구현·재회의

## 결론

`SHGetKnownFolderPath(FOLDERID_ProgramData, 0, NULL, ...)`에서 출발하는 인자 없는 고정 저장소 observer를 구현했다. 공개 함수 `observe_fixed_windows_owner_policy_store_candidate()`는 path, epoch, key, SID, expected identity, receipt/state/callback을 받지 않는다. 컴파일된 상대 경로는 `llm-novel-dc\p0-owner-policy-v1`이고, 이번 후보가 읽는 generation은 genesis `00000000000000000001` 하나뿐이다.

채택 상태는 `OWNER_POLICY_FIXED_STORE_CANDIDATE_PASS_AUTHORITY_NO_GO`다. 통제 fixture에서는 known-folder 선택 이후 lexical ancestor와 정책 8개 role을 동시에 handle로 유지하면서 exact layout·inventory·identity·bytes·pin 교차결속·binary ACL 전후 비교·watch interval·lexical reopen과 컴파일 공개키 후보의 bootstrap signature 수학을 확인한다. 그러나 현재 머신에는 fixed suffix가 없고 외부 owner provisioning, bootstrap key의 독립 pin·trusted code deployment, rollback-resistant epoch가 없다. 따라서 `fixed_policy_store_discovery_verified=false`, actual/P0/production/full scan은 계속 false다.

## 전문가 재회의와 채택 결정

API 설계, Windows 보안 감사, 구현 후 코드 red-team, 테스트 독립 감사 네 갈래로 검토했다.

| 논점 | 채택 | 이유 |
| --- | --- | --- |
| ProgramData 선택 | `FOLDERID_ProgramData` API만 사용 | 환경변수·registry·cwd·caller path를 trust root로 쓰지 않는다. |
| 고정 suffix | `llm-novel-dc\p0-owner-policy-v1` exact lowercase | OS가 소유한 `ProgramData` 접두부 casing은 handle final path 그대로 보존한다. |
| generation 선택 | 컴파일된 genesis epoch 1 | 최고 epoch scan이나 caller epoch는 rollback/ambiguity를 만든다. rotation은 별도 durable broker가 필요하다. |
| positive 의미 | candidate observation만 true | 고정 이름은 누구나 선점할 수 있으며 독립 provisioning 증거가 아니다. |
| owner anchor | core identity만 결속 | pin transport hash를 anchor에서 제외해 순환 해시를 없애고, full policy identity는 policy body bytes SHA로 구분한다. |
| ACL 표현 | `held_role_acl_projection_matches_presented_template_observed` | 실제 handle ACL을 읽지만 bootstrap key가 독립 pin되지 않았으므로 `live_windows_binary_acl_verified`로 승격하지 않는다. |
| watcher | parent와 store subtree 두 개 | parent→store 순서로 arm하고 store→parent 순서로 finalize한다. event/overflow/gap/cleanup 불확실성은 모두 fail-close한다. |

기각한 안은 `%ProgramData%` 환경변수, HKLM 문자열을 직접 trust root로 사용, generations 중 최대 숫자 자동 선택, public test-injection parameter, receipt 재입력으로 authority 복원, 현 세션에서 current-user ACL을 외부 owner positive로 세는 방식이다.

## 선행 계약 결함과 수정

첫째, 기존 policy contract는 volume-GUID 경로의 모든 component를 소문자로 강제해 실제 `...\ProgramData\...` handle final path를 거부했다. volume GUID lowercase canonical, ASCII-safe component, DOS reserved name·dot·NUL·trailing dot/space 거부는 유지하되 OS prefix casing은 보존하고 application suffix부터 exact lowercase layout으로 검증하도록 수정했다.

둘째, owner anchor가 `pin_bytes_sha256`를 포함하고 pin이 다시 `owner_anchor_sha256`를 포함해 실제 artifact를 만들 수 없는 순환 해시가 있었다. owner anchor의 operational-key projection은 key id/epoch/algorithm/fingerprint/domain만 사용하고, exact pin byte/artifact hash는 bootstrap-signed policy body에 남겼다. receipt에는 `owner_anchor_scope=CORE_POLICY_IDENTITY_EXCLUDING_PIN_TRANSPORT_HASHES`와 `full_policy_identity_sha256`를 함께 기록한다. owner anchor 단독을 full policy identity로 사용하면 안 된다.

셋째, 공용 held-handle helper가 `CloseHandle` 반환값을 무시했다. 이제 primary 오류가 없을 때 close 실패·예외를 전용 오류로 올려 성공 receipt를 차단한다.

## 구현 범위

- `src/llm_batch/grounding/p0_windows_fixed_owner_policy_store_candidate.py`
  - 정확한 ProgramData GUID, flags `0`, token `NULL`
  - 실패 시에도 non-NULL known-folder allocation free call 시도
  - lexical ancestor와 8 role의 non-reparse/same-volume/direct-descendant/exact-case identity
  - store부터 pin directory까지 exact inventory
  - file single-link, unnamed stream only, exact handle read
  - signed object path/volume/file ID와 live handle exact 비교
  - pin key/fingerprint/owner anchor/byte hash/artifact hash 교차결속
  - 8 role ACL 전후 총 16회 비교와 ACL drift 거부
  - parent/store recursive watch, pre/post identity·inventory·ACL, role·ancestor reopen
  - 같은 held raw body/signature의 bootstrap CNG 검증과 child receipt 전체 계약 재검증
- `tests/test_p0_windows_fixed_owner_policy_store_candidate.py`
  - public zero-argument·금지 selector 부재
  - known-folder GUID/flags/null token/free call
  - API 실패+non-NULL allocation cleanup
  - 통제된 self-consistent fixed-store candidate positive
  - ACL drift, pin/anchor/bytes 변조, watcher partial-start cleanup, handle close failure
  - 현재 머신 fixed suffix 부재 fail-close와 non-Windows 선행 gate

통제 positive는 ACL projection API boundary를 role별로 주입해 orchestration을 검증한 것이다. 실제 외부 owner ACL positive나 bootstrap authority 증거가 아니다. bootstrap signature math는 true지만 독립 key pin, trusted code/provider provenance와 모든 authority 필드는 false로 고정한다.

## 현재 Windows 읽기 전용 감사

- `SHGetKnownFolderPath` 결과: `C:\ProgramData`
- handle final path: `\\?\Volume{42482404-81de-411a-be01-3a01d9534e56}\ProgramData`
- 64-bit volume serial: `0x01dc78aea5e89cc0`
- ProgramData file ID: `450d0000000001000000000000000000`
- fixed root `C:\ProgramData\llm-novel-dc\p0-owner-policy-v1`: 없음
- C: NTFS 상태: `Warning / Full Repair Needed`

ProgramData는 SYSTEM-owned/protected DACL이지만 현재 medium token은 `FILE_ADD_FILE`, `FILE_ADD_SUBDIRECTORY`, `FILE_WRITE_ATTRIBUTES`를 얻을 수 있다. 즉 빈 fixed name은 current user가 선점할 수 있다. 이번 세션은 directory/account/ACL을 생성·변경하지 않았다.

## 검증

- bootstrap + fixed-store + asymmetric focused: `47/47 PASS`
- Windows owner-policy 인접군: `117/117 PASS`
- 전체 `test_p0*.py`: `497/497 PASS`
- 중앙 Slang DB 1개와 publication journal 5개: `6/6` byte·SHA 불변
- noninterference receipt: `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`
- fixture receipt: `d94e1de3c5b4f8cd801804467fe82efed68ead1ec1b1abb986f48861a734545c`

이번 검증은 component unittest와 읽기 전용 OS 감사다. actual dataset run이 아니므로 `--parallel 16`과 dashboard manifest 적용 대상이 아니다. Python compile과 scoped diff check도 통과했다.

## 잔여 gate

1. elevated one-time provisioner, LocalSystem service 또는 외부 broker가 fixed name과 8-role owner/ACL을 원자적으로 만든다.
2. 현재 수학 후보를 실제 owner 승인 key로 교체하고 binary/service/TPM 등 정책 파일 밖에 독립 provision한 뒤 trusted code/provider provenance를 검증한다.
3. actual primary/effective/linked token, dangerous privilege, mutator membership과 parent delete-child 경계를 검증한다.
4. signed selector 또는 broker high-watermark로 policy/key epoch rollback을 막고 trusted time·revocation을 결속한다.
5. crash/reboot durable nonce와 private authority lease를 구현한 뒤에만 runtime supervisor에 연결한다.
6. 그 뒤에도 actual semantic 40+20과 owner numerical policy를 닫기 전에는 Pyserini, gold-lite, RRF/reranker/NIL A/B 및 full scan을 시작하지 않는다.

bootstrap transcript·CNG·receipt 소비자 재회의는 [P0 Windows bootstrap policy 서명 수학 후보 구현·재회의](P0_WINDOWS_BOOTSTRAP_POLICY_SIGNATURE_CANDIDATE_REVIEW_20260902_KO.md)에 기록했다.

## 근거

- Microsoft [`SHGetKnownFolderPath`](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)
- Microsoft [KNOWNFOLDERID](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)
- Microsoft [`GetSecurityInfo`](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)
- Microsoft [`AccessCheck`](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-accesscheck)
- Microsoft [Access Control Lists](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-control-lists)
