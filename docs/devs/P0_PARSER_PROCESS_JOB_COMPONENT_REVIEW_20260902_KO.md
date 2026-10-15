# P0 parser 별도 프로세스·Job component 구현 및 재회의

작성일: 2026-09-02 KST

## 결론

이번 tranche는 actual parser 실행을 흉내 내지 않고, 향후 parser를 넣기 위한 별도 프로세스 골격을 구현했다. 채택 판정은 `ADOPT_COMPONENT_ONLY / PARSER_SANDBOX_NO_GO`다.

구현된 양성 증거는 path-less capture byte protocol, 부모의 request/response exact 재계산, privilege-stripped restricted primary token readback, `CREATE_SUSPENDED` 뒤 Job 편입과 membership 확인, stdio 3개 handle allowlist, bounded pipe·timeout 종료, 고정 interpreter/worker/protocol path hash 관측이다. 현재 worker operation은 `CAPTURE_HASH_PROBE`뿐이며 source-to-claim 의미 parser가 아니다.

다음 강한 주장은 모두 false다.

- `network_deny_verified=false`
- `appcontainer_verified=false`
- `filesystem_write_deny_verified=false`
- `os_write_deny_verified=false`
- `runtime_noninterference_verified=false`
- `parser_dependency_closure_verified=false`
- `parser_runtime_execution_verified=false`
- `semantic_parser_executed=false`
- `actual_semantic_evidence_verified=false`
- `actual_authority_granted=false`
- `p0_phase_exit=false`
- `production_approval=false`
- `full_scan_approval=false`

actual·credited count는 계속 source claim `0/40`, A-context 사람 검토 `0/20`이다. 현재 gate는 `EXTERNAL_STORE_KEY_AND_NONCE_EXECUTED / BOUNDED_WINDOWS_WITNESS_COMPONENT_ONLY / PARSER_PROCESS_JOB_COMPONENT_OBSERVED / APPCONTAINER_NETWORK_WRITE_DENY_NO_GO / PARSER_RUNTIME_NO_GO / ACTUAL_EVIDENCE_0_OF_40_0_OF_20 / PRODUCTION_NO_GO`다.

## 구현 범위

### canonical capture-byte protocol

`p0_parser_process_protocol.py`와 `p0_parser_process_worker.py`는 다음을 고정한다.

- stdin/stdout은 canonical UTF-8 JSON 한 개와 마지막 LF 한 개만 허용한다.
- BOM, duplicate key, non-finite number, trailing frame, path 필드, 비정규 base64, byte/SHA 불일치를 거부한다.
- capture는 `1..40`, 개별 `256 KiB`, decoded 합계 `4 MiB`, stdin `8 MiB`, stdout `256 KiB`로 제한한다.
- request는 launch/parser manifest/version, capture manifest, input registry와 각 payload의 bytes/SHA를 결속한다.
- child 출력은 `child_reported_*` 진단으로만 표현한다. self-hash를 실행 진실로 사용하지 않는다.
- 부모 `validate_response_against_request()`가 모든 echo, observation, count와 SHA를 독립 재계산한다.
- 오류 stderr는 입력 원문을 반사하지 않고 고정 prefix와 digest만 출력한다.

### Windows process/Job component

`p0_windows_parser_process_sandbox.py`는 caller가 executable·command·worker·environment를 바꿀 수 없는 고정 API다.

1. `sys._base_executable`, caller `sys.executable`, worker와 protocol path를 고정하고 path SHA를 계산한 뒤 write/delete share 없는 read handle을 실행 종료까지 유지한다.
2. 현재 TokenUser와 enabled·non-deny-only TokenGroups의 중복 제거 projection을 restricting SID로 사용하고 `DISABLE_MAX_PRIVILEGE`를 적용한다.
3. TokenType primary, `IsTokenRestricted`, restricting SID exact set, 남은 privilege `SeChangeNotifyPrivilege`를 다시 읽는다.
4. Job에 `KILL_ON_JOB_CLOSE | ACTIVE_PROCESS`, active process limit `1`을 설정하고 Query roundtrip으로 확인한다.
5. child를 `CREATE_SUSPENDED`로 만들고 Job assign·`IsProcessInJob`을 확인한 뒤에만 primary thread를 resume한다.
6. `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`에는 stdin/stdout/stderr child end 정확히 3개만 넣는다. token·job·pinned file·parent pipe handle은 상속하지 않는다.
7. stdout/stderr를 동시에 bounded drain하고 timeout/overflow면 Job을 종료한다. Job 밖 suspended child 가능성이 있는 assign 전 실패는 `TerminateProcess`로 직접 닫는다.
8. exit `0`, stderr empty, canonical response와 parent exact cross-binding, launch path의 실행 전후 SHA가 모두 맞을 때만 component receipt를 반환한다.

venv redirector는 내부적으로 base Python process를 추가 생성해 active process limit `1`과 충돌하므로 실제 application image는 고정 `sys._base_executable`을 사용한다. caller redirector도 별도 path/hash로 receipt에 남긴다.

enabled-SID projection은 현재 token의 DACL 접근을 사실상 보존한다. 따라서 `restricted_primary_token_verified=true`는 token 형식·정책 readback의 좁은 사실이고 보호 root write deny나 network deny가 아니다.

## red-team 재회의

| 반례 | 조치 | 잔여 경계 |
| --- | --- | --- |
| child가 임의 response+self-hash를 위조 | child 필드를 `child_reported_*`로 축소하고 부모가 request 전체를 재계산 | process provenance·semantic authority는 false |
| assign 실패한 suspended child가 Job 밖에 남음 | membership 전 실패는 direct `TerminateProcess`+wait | brokered external process escape는 미검증 |
| child가 `STATUS_ACCESS_DENIED`를 내면 weaker token으로 자동 retry | zero-SID·normal process fallback을 전부 제거하고 exact policy 한 번만 실행 | exact policy 실패는 terminal NO-GO |
| venv redirector가 base Python child를 만들어 Job limit 위반 | `sys._base_executable`을 고정 image로 사용하고 caller redirector도 pin | Python dependency closure는 미봉인 |
| worker/protocol path swap | held no-share-write/delete handle과 pre/post path SHA를 관측 | handle-derived hash/file ID, parent namespace watch, sealed bundle 전 provenance 승격 금지 |
| timeout/pipe deadlock | concurrent drain, stream cap, Job terminate와 direct child fallback | process-tree/broker escape 종합 증거는 없음 |
| child stdout의 security boolean | parent OS receipt는 child boolean을 읽지 않고 broad false inventory를 고정 | serialized receipt는 execution proof로 재수용 금지 |

최종 독립 판정은 component 코드 범위에서 추가 finding 없음이다. 다만 pre-resume marker, direct/BREAKAWAY·WMI/Task Scheduler/COM broker escape, sensitive handle/parent duplication, same-user root write·rename·ADS·reparse, pipe flood, parent namespace swap, controlled IPv4/IPv6 network와 AppContainer readback은 다음 tranche의 필수 음성 gate다.

## fresh 검증

| 범위 | 결과 |
| --- | --- |
| protocol | `10 PASS` |
| Windows sandbox component | `10 PASS` |
| 신규 focused 합계 | `20 PASS` (`0.946s`) |
| 관련 external trust/runtime adjacent | `75 PASS` |
| 전체 `test_p0_*.py` | `379 PASS` (`17.670s`) |
| Python compile | 신규 3개 모듈·2개 테스트 `PASS` |
| 기존 상태 비간섭 | 중앙 Slang DB 1개+publication journal 5개 `6/6` byte·SHA 불변 |

현 Windows E2E는 base interpreter exact applicationName/argv, child exit `0`, stderr `0`, request/response cross-binding `true`, restricting SID `14`(TokenUser 1+enabled group 13), remaining privilege `SeChangeNotifyPrivilege`, Job limit roundtrip·membership-before-resume·handle list 3개를 확인했다. 이 수치는 현재 호스트 component 진단이며 실제 source/parser 성능이 아니다.

이번 검증은 unittest와 read-only audit이다. actual pipeline run이 아니므로 dashboard와 `--parallel 16` manifest 대상이 아니다.

## 공식 API 근거

- Microsoft [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken)은 output token type이 input과 같고 restricting SID가 별도 access check에 쓰이며 restricted caller-primary token을 `CreateProcessAsUser`에 사용할 수 있음을 설명한다.
- [CreateProcessAsUserW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessasuserw)는 primary token 권한, mutable command line, inheritable handle과 `STARTUPINFOEX` 경계를 규정한다.
- [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)의 `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`는 child가 상속할 handle의 명시 목록을 제공한다.
- [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject)와 [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)는 Job membership·nested/breakaway·일부 brokered creation 예외를 설명한다.
- [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)은 file, network, process 격리의 강한 경계다. 현재 component는 AppContainer가 아니므로 해당 주장을 false로 둔다.

## 다음 P0 순서

1. 고정 read-only staging 또는 sealed/frozen bundle을 만들고 handle-derived final path·file ID·hash와 suspended process image identity를 결속한다.
2. AppContainer/LPAC no-capability token을 적용하고 writable output root만 명시 ACL로 열어 보호 root write-deny와 network deny를 실제 child에서 검증한다.
3. direct/BREAKAWAY·brokered spawn, handle duplication, same-user namespace/ADS/reparse, pipe flood, timeout/crash·parent hard-kill E2E를 수행한다.
4. 실제 source-profile parser entrypoint와 parser v3/supplemental process provenance receipt를 구현한다. 현재 저장소의 route validator와 fixture builder는 parser가 아니다.
5. 외부 owner public-key pin, trusted time/revocation, durable nonce와 owner-signed root/USN을 결합한다.
6. 위 gate 전체 통과 뒤에만 dashboard ON·`--parallel 16` actual source claim 40건+A-context 20건을 시작한다.

그 전에는 Pyserini·gold-lite·retrieval/reranker/NIL A/B와 production/full scan을 열지 않는다.

## 후속 상태

위 문서의 다음 순서 1 가운데 held-handle final path·volume/file ID·SHA와 suspended child image path reopen은 후속 tranche에서 구현됐다. 다만 `.pyc`/import collision/watcher 공백 때문에 source/dependency closure는 여전히 false다. 최신 판정과 `384 PASS` 근거는 [`P0_PARSER_PROCESS_HANDLE_PROVENANCE_REVIEW_20260902_KO.md`](P0_PARSER_PROCESS_HANDLE_PROVENANCE_REVIEW_20260902_KO.md)를 따른다.
