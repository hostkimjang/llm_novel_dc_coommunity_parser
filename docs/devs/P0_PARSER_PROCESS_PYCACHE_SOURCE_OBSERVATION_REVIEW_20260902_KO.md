# P0 parser process isolated pycache·source collision·directory watch 구현 검토

작성일: 2026-09-02 KST

상태: `ADOPT_BOUNDED_PROJECT_SOURCE_LOAD_CANDIDATE_CLOSURE_COMPONENT_ONLY / PARSER_DEPENDENCY_CLOSURE_NO_GO / PARSER_SANDBOX_NO_GO / ACTUAL_0_OF_40_0_OF_20 / METRICS_NOT_ESTIMABLE / REVIEW_LOCKED`

## 결론

이 tranche는 이전 handle-provenance 검토에서 남긴 세 blocker, 즉 정상 repository `__pycache__` 후보, import collision inventory 부재, source/parent/cache watcher 공백을 좁은 component 범위에서 닫았다. 실제 Windows component E2E에서 고유한 빈 per-execution pycache root, 정적 import-collision inventory, child 실행 전후를 잇는 세 directory watch를 결합해 `bounded_project_source_load_candidate_closure_verified=true`를 관측했다.

이 양성 필드는 고정 project-source 후보가 관측 구간에 다른 project-source load candidate로 바뀌지 않았다는 제한된 뜻뿐이다. Python runtime·stdlib·native loader/DLL의 완전한 dependency closure, 실제 loaded image file object, 외부 owner source identity pin, AppContainer/LPAC, network/protected-root write deny, 의미 parser 또는 actual authority를 증명하지 않는다. 따라서 다음 상위 필드는 계속 false다.

- `project_source_load_candidate_closure_verified=false`
- `parser_dependency_closure_verified=false`
- `trusted_cpython_runtime_prerequisite_verified=false`
- `python_runtime_dependency_closure_verified=false`
- `python_stdlib_dependency_closure_verified=false`
- `native_dll_dependency_closure_verified=false`
- `actual_loaded_image_file_object_verified=false`
- `external_project_source_identity_pin_verified=false`
- `parser_runtime_execution_verified=false`
- `runtime_noninterference_verified=false`
- `p0_phase_exit=false`
- `production_approval=false`
- `full_scan_approval=false`

actual·credited count는 source claim `0/40`, A-context `0/20`이다. 합성 fixture나 unittest component 통과를 actual evidence로 세지 않으며 실제 의미 지표는 `METRICS_NOT_ESTIMABLE`, 의미 품질은 `REVIEW_LOCKED`다.

## 구현 범위

### 고유한 빈 isolated pycache

Windows `FOLDERID_LocalAppData`를 `SHGetKnownFolderPath`로 조회해 로컬 cache anchor를 만들고, 실행마다 CSPRNG entropy와 request SHA를 결합한 고유 child directory를 생성한다. 이 anchor와 child는 held directory handle의 volume serial·file ID·volume-GUID final path로 관측한다.

- child argv는 `-I -S -B -X pycache_prefix=<per-execution-root>`로 고정한다.
- cache root는 생성 직후, process create 직전, resume 직전, child exit 뒤에 exact-empty인지 handle 기반으로 다시 열거한다.
- child runtime guard가 CPython implementation/cache tag/version, `optimize=0`, exact pycache prefix와 각 pinned source의 예상 optimization-0 cache path를 부모 기대값에 교차 결속한다.
- cleanup은 path 문자열 삭제가 아니라 held handle의 delete disposition을 `SetFileInformationByHandle`로 설정하고 handle close 뒤 path 부재를 확인한다.
- disposition 설정, handle close 또는 path 부재 확인이 실패하면 bounded closure는 false다.

`LocalAppData` anchor는 이 host에서 잡은 **로컬 held identity**다. verifier 밖 external owner가 사전 승인한 root pin이 아니므로 `external_project_source_identity_pin_verified=false`를 유지한다. 또한 현 packaged 환경에서는 lexical `LocalAppData`와 열린 final path 사이의 MSIX redirection이 관측됐고, 구현은 이를 숨기지 않고 `known_folder_redirection_observed=true`로 receipt에 남긴다. 이 관측도 external owner pin이나 trusted namespace 승격 근거가 아니다.

### 정적 source collision inventory

`src`, `llm_batch`, `llm_batch/grounding` 세 directory의 handle-based inventory를 고정하고 import suffix universe를 source, bytecode, extension 후보 전체로 계산한다. Unicode NFC/case-fold collision, unsafe name, alternate package directory, legacy/normal `.pyc`, ABI extension 후보 등 고정 import graph와 충돌하는 항목을 fail-close한다.

필수 project-source 후보는 기존과 같은 네 파일이다.

1. `llm_batch/__init__.py`
2. `llm_batch/grounding/__init__.py`
3. `p0_parser_process_worker.py`
4. `p0_parser_process_protocol.py`

이 inventory와 source import graph는 parser manifest v3·launch v3에 결속된다. 다만 inventory 범위 밖 Python runtime/stdlib/native dependency는 포함하지 않으므로 이를 parser dependency closure로 확대하지 않는다.

### bounded directory-change observation

다음 세 watch를 process create 전 pre-inventory보다 먼저 arm하고 post-inventory와 child exit 뒤까지 유지한다.

| role | 범위 | 목적 |
| --- | --- | --- |
| `source_parent_nonrecursive` | `src`의 즉시 부모 | source root 자체의 rename/replacement 관측 |
| `source_root_recursive` | `src` subtree | project-source·package·collision 후보 변화 관측 |
| `pycache_root_recursive` | per-execution cache root | cache entry 생성·변경 관측 |

observer는 `ReadDirectoryChangesExW`의 extended information과 하나의 pending overlapped request를 사용한다. create 직전·resume 직전·post inventory barrier에서 request가 계속 pending인지 확인한다. delivered event, overflow, malformed record, premature completion, wait/poll error, cleanup gap은 모두 NO-GO다. 정상 종료는 interval 끝까지 pending이던 request를 `CancelIoEx`로 취소하고 `GetOverlappedResultEx`로 terminal completion을 drain한 뒤 handle close까지 확인한 경우에만 인정한다.

이 결과는 `SINGLE_PENDING_REQUEST_SPANNED_INTERVAL_WITHOUT_DELIVERED_NOTIFICATION_OBSERVED` 범위의 관측이다. USN journal, OS write-deny, power-loss durability 또는 filesystem 전체 비간섭을 추론하지 않으며 receipt도 `filesystem_noninterference_inferred=false`로 고정한다.

## component closure의 양성 조건

`bounded_project_source_load_candidate_closure_verified=true`는 다음을 모두 만족한 한 실행에서만 나온다.

- 정적 collision inventory와 import graph가 exact다.
- 세 watch가 arm부터 post inventory까지 event/overflow/gap 없이 종료되고 취소·drain·close된다.
- pycache가 create 전·resume 전·exit 후 비어 있으며 exact-handle cleanup 뒤 경로가 없다.
- launch/source held handle과 lexical reopen identity가 create 전·resume 전·exit 후 일치한다.
- Job assign-before-resume, exact stdio handle list, child exit 0, stderr 0을 확인한다.
- child runtime guard와 canonical response가 부모 request에 exact cross-binding된다.

하나라도 실패하면 receipt는 blocker를 남기고 양성 필드를 열지 않는다. broad security·authority 필드는 성공 경로에서도 false다.

## red-team과 검증 경계

- alternate `.pyc` 후보를 source directory에 넣으면 collision inventory 단계에서 거부한다.
- child가 보고한 ABI/cache path가 부모 기대값과 다르면 runtime guard cross-binding을 거부한다.
- pycache handle close 실패나 cleanup 부재는 bounded closure를 false로 만든다.
- watcher가 nested change를 받으면 event 이름을 보존한 채 관측을 실패시킨다.
- overflow, wait/poll error, cleanup timeout, close failure, abandoned watcher는 성공으로 재해석하지 않는다.
- reparse directory와 unsafe lexical path/options는 Win32 watch open 전 또는 identity 단계에서 fail-close한다.

정적 worker 검사는 실제 control-flow graph 증명이 아니라 필수 호출의 수와 소스 행 순서를 확인하는 검사다. 또한 parent policy source SHA는 현재 parent code object나 unchecked bytecode를 외부 주체가 독립 인증한 증거가 아니다. 그래서 CPython·stdlib·OS와 parent observer를 신뢰하는 전제는 `trusted_cpython_runtime_prerequisite_verified=false`로 남기고, 이 self-observation 한계를 좁은 component 주장 밖으로 확대하지 않는다.

최종 fresh 검증은 protocol `12`, directory-watch `16`, Windows sandbox `20`, 합계 `48/48 PASS` (`4.500s`)다. 전체 `test_p0_*.py`는 `407/407 PASS` (`22.218s`), 변경 Python compile은 `PASS`다. 중앙 Slang DB 1개와 publication journal 5개는 `6/6` byte·SHA 불변이며 noninterference receipt는 `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`, fixture receipt는 `d94e1de3c5b4f8cd801804467fe82efed68ead1ec1b1abb986f48861a734545c`, 중앙 Slang DB SHA는 `a8c3fb9b083f6914e24bbede5adbbce73372f834dee4271611eefaaeeebcf10a`다. cache anchor 최종 `item_count=0`도 확인했다.

이번 실행은 component unittest·Windows E2E다. regression-safe grounding dataset run이나 actual 40+20 run이 아니므로 dashboard와 `--parallel 16` manifest 대상이 아니다.

## 전문가 채택표

| 의제 | 판정 | 근거와 제한 |
| --- | --- | --- |
| per-execution empty pycache + exact-handle cleanup | `ADOPT_COMPONENT_ONLY` | 정상 repository cache lookup을 좁은 실행에서 제외하지만 trusted external cache root는 아님 |
| static source/import collision inventory | `ADOPT_COMPONENT_ONLY` | 고정 project-source import 후보를 닫지만 stdlib/native closure는 아님 |
| source/parent/cache pending-request watcher | `ADOPT_COMPONENT_ONLY` | bounded interval의 delivered change 부재 관측이며 OS write-deny·USN·durability는 아님 |
| bounded project-source load-candidate closure | `ADOPT_COMPONENT_ONLY` | 한 고정 component 실행의 후보 closure만 인정 |
| parser dependency/runtime/stdlib/native closure | `REJECT` | 전체 dependency·loaded image·owner pin 증거가 없음 |
| parser sandbox·actual/P0·production/full scan | `REJECT` | AppContainer/network/write deny·semantic parser·external authority·actual 40+20이 없음 |

## 공식 API 근거

- Python [Command line and environment](https://docs.python.org/3/using/cmdline.html): `-I`, `-S`, `-B`, `-X pycache_prefix`의 실행 의미를 확인한다.
- Microsoft [ReadDirectoryChangesExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-readdirectorychangesexw): extended directory change notification과 overlapped request 계약의 근거다.
- Microsoft [CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex): exact overlapped request 취소 절차의 근거다.
- Microsoft [GetOverlappedResultEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getoverlappedresultex): 취소 뒤 terminal completion drain의 근거다.
- Microsoft [SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)와 [KNOWNFOLDERID](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid): `FOLDERID_LocalAppData` 조회의 근거다.
- Microsoft [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle): held directory handle에 delete disposition을 설정하는 근거다.

## 남은 gate

1. trusted CPython executable/runtime prerequisite와 stdlib import closure를 별도 frozen bundle로 결속한다.
2. native loader DLL closure와 실제 loaded image file object를 독립 관측한다.
3. verifier 밖 external owner가 project source/cache/root identity를 사전 승인·pin한다.
4. AppContainer/LPAC no-capability, controlled IPv4/IPv6 network deny와 protected-root write/rename/ADS/reparse deny를 actual child에서 검증한다.
5. 실제 source-profile semantic parser와 generic queue exact accounting을 연결한다.
6. external owner/time/revocation/root/USN/runtime authority와 owner numerical policy가 닫힌 뒤에만 dashboard ON·`--parallel 16` actual 40+20을 시작한다.

그 전 판정은 `PARSER_DEPENDENCY_CLOSURE_NO_GO / PARSER_SANDBOX_NO_GO / ACTUAL_0_OF_40_0_OF_20 / METRICS_NOT_ESTIMABLE / REVIEW_LOCKED`다.
