# P0 parser process handle provenance 구현·전문가 재회의

작성일: 2026-09-02 KST

## 결론

parser process component의 실행 파일·worker·protocol 신원 관측을 경로 재오픈 SHA에서 Windows held-handle 기반으로 교체했다. 채택 판정은 `ADOPT_HANDLE_PROVENANCE_COMPONENT / PROJECT_SOURCE_CANDIDATE_MANIFEST_ONLY / PARSER_SANDBOX_NO_GO`다.

> 후속 상태: 아래 source-closure blocker와 next gate는 이 보고서 작성 시점의 역사다. unique empty pycache, collision inventory, bounded source/parent/cache watcher는 후속 tranche에서 좁게 완료되어 `bounded_project_source_load_candidate_closure_verified=true`가 됐다. 그러나 broad `project_source_load_candidate_closure_verified=false`, `parser_dependency_closure_verified=false`, `PARSER_SANDBOX_NO_GO`는 유지한다. successor는 [`P0_PARSER_PROCESS_PYCACHE_SOURCE_OBSERVATION_REVIEW_20260902_KO.md`](P0_PARSER_PROCESS_PYCACHE_SOURCE_OBSERVATION_REVIEW_20260902_KO.md)다.

실제 Windows E2E에서 다음 좁은 사실을 확인했다.

- caller/base Python과 필수 project-source 후보 4개를 `ReadFile(HANDLE)`로 읽어 SHA-256을 계산했다.
- 각 파일의 volume serial, 128-bit file ID, volume-GUID final path, 크기·시간·link·stream·reparse 상태를 같은 held handle에서 읽었다.
- 각 lexical parent chain을 drive root부터 즉시 부모까지 directory handle로 고정하고 reparse·volume/descendant 이탈을 거부했다.
- CreateProcess 직전, Job assign 뒤 ResumeThread 직전, child 종료 뒤 held-handle hash와 lexical path reopen identity를 다시 확인했다.
- suspended child의 PID·creation FILETIME을 읽고, `QueryFullProcessImageNameW`가 보고한 경로를 다시 열어 pinned base executable의 file ID와 handle SHA에 결속한 뒤에만 resume했다.

이것은 loaded image section 자체의 file object 증명, Python runtime/stdlib/DLL closure, source-only import closure, AppContainer, network/write deny 또는 의미 parser 증명이 아니다. actual·credited는 계속 source claim `0/40`, A-context `0/20`이며 P0 Exit·Pyserini·gold-lite·A/B·production/full scan은 닫혀 있다.

## 구현 범위

### held-handle identity와 hash

기존 `_sha_file(path)`와 종료 후 path SHA 비교를 제거했다. 파일 handle을 `FILE_SHARE_READ`만 허용해 열고 다음 projection을 실행 전부터 종료 후까지 비교한다.

- `GetFileInformationByHandleEx`: `FileIdInfo`, basic, standard, stream, attribute-tag 정보
- `GetFinalPathNameByHandleW`: volume-GUID normalized final path
- `SetFilePointerEx(0)` + `ReadFile`: held object의 exact byte SHA-256과 EOF 확인
- single hardlink, unnamed data stream 하나, regular file, non-reparse, non-delete-pending 조건

SHA의 근거는 lexical path가 아니라 처음부터 유지한 handle이다. lexical path reopen은 그 path가 동일 `(volume serial, file ID)`와 동일 stable metadata/SHA의 object를 다시 가리키는지 확인하는 보조 namespace 검증이다.

### parent namespace guard

실제 argv/import 후보에 쓰는 resolved local DOS path별로 volume root부터 즉시 부모까지 unique directory chain을 연다. 각 directory는 `FILE_READ_ATTRIBUTES`, `FILE_SHARE_READ`, `OPEN_REPARSE_POINT | BACKUP_SEMANTICS`로 열고 실행 종료까지 유지한다. 인접 component는 동일 volume의 정확한 한 단계 descendant여야 한다.

현재 watcher 연속성이나 directory member inventory까지 결합한 것은 아니다. 따라서 swap/restore 전 구간 무변조 또는 external authorized identity pin을 주장하지 않는다.

### suspended process identity

실행 순서는 다음과 같다.

1. launch handles·paths 재검증
2. `CreateProcessAsUserW(... CREATE_SUSPENDED ...)`
3. Job assign과 `IsProcessInJob`
4. `GetProcessId == PROCESS_INFORMATION.dwProcessId`
5. `GetProcessTimes` creation FILETIME 관측
6. `QueryFullProcessImageNameW` 경로 reopen 후 pinned base executable file ID/SHA 비교
7. launch handles·paths 두 번째 재검증
8. `ResumeThread` 반환값이 정확히 `1`일 때만 실행

receipt의 양성 필드는 `reported_child_image_path_reopened_to_pinned_executable_before_resume_verified`다. 이는 API가 보고한 경로를 같은 파일 identity로 다시 열었다는 뜻이며 `actual_loaded_image_file_object_verified=false`는 유지한다.

## project-source 후보 manifest 보정

정적 repository source 후보는 다음 4개다.

1. `llm_batch/__init__.py`
2. `llm_batch/grounding/__init__.py`
3. `p0_parser_process_worker.py`
4. `p0_parser_process_protocol.py`

전문가 반대검토에서 `python -I -S -B`도 기존 `__pycache__`의 `.pyc`를 읽을 수 있음을 확인했다. `-B`는 bytecode 쓰기를 막지만 source-only load를 보장하지 않는다. 따라서 `required_project_source_candidate_manifest_exact_verified=true`만 채택하고 다음을 모두 false로 유지했다.

- `bounded_project_source_load_candidate_closure_verified=false`
- `project_source_load_candidate_closure_verified=false`
- `parser_dependency_closure_verified=false`
- `python_runtime_dependency_closure_verified=false`
- `python_stdlib_dependency_closure_verified=false`
- `native_dll_dependency_closure_verified=false`

receipt에는 `normal_repository_pycache_lookup_not_excluded`, `import_collision_inventory_not_watched`, `project_source_namespace_watch_continuity_not_verified` 세 blocker를 명시한다.

## 전문가 재회의 채택표

| 의견 | 결정 | 근거 |
| --- | --- | --- |
| path SHA를 held-handle SHA로 교체 | `ADOPT` | path swap과 original object read를 구분한다. |
| volume serial + 128-bit file ID를 primary identity로 사용 | `ADOPT` | final path 문자열만으로 object identity를 대신하지 않는다. |
| 모든 lexical ancestor directory handle 유지 | `ADOPT_COMPONENT_ONLY` | component rename 방어는 강화하지만 watcher 없는 swap/restore 전체 증명은 아니다. |
| suspended child PID/time/image path를 resume 전에 검증 | `ADOPT_COMPONENT_ONLY` | process handle correlation과 보고 image path 결속이며 loaded image section 증명은 아니다. |
| 4개 `.py`를 source closure로 선언 | `REJECT` | 정상 `__pycache__`, collision package/`.pyd`, watcher 공백이 남는다. |
| isolated pycache prefix + empty inventory + continuous watcher | `DEFER_NEXT_GATE` | source-candidate closure를 주장하려면 별도 구현·공격 테스트가 필요하다. |
| AppContainer/P0/production 승인 | `REJECT` | network/write deny, semantic parser, external owner authority, actual 40+20가 없다. |

## red-team과 fresh 검증

- reported child image를 worker source로 바꾸면 ResumeThread는 호출되지 않고 suspended child를 종료·대기한다.
- ResumeThread 반환 suspend count가 `2`이면 재개 성공으로 처리하지 않고 child를 종료한다.
- assignment 실패 child도 resume 없이 direct termination 한다.
- held source leaf가 살아 있는 동안 `os.replace`는 실패하고, handle을 닫은 뒤에만 교체된다.
- process time/image query가 ResumeThread보다 먼저 호출됨을 proxy call-order로 확인했다.
- path-based `_sha_file`와 `Path.open("rb")` hash 구현이 source에 없음을 정적으로 확인했다.

| 검증 | 결과 |
| --- | --- |
| Windows sandbox focused | `15 PASS` |
| protocol + Windows sandbox focused | `25 PASS` (`1.776s`) |
| 전체 `test_p0_*.py` | `384 PASS` (`19.836s`) |
| compile | 변경 모듈·테스트 `PASS` |
| diff whitespace | `PASS` |
| 기존 상태 비간섭 | 중앙 Slang DB 1개 + publication journal 5개 `6/6` byte·SHA 불변, audit `6033c6d0…204e` |

이번 실행은 unittest/component E2E와 read-only audit이다. actual 40+20 pipeline run이 아니므로 dashboard와 `--parallel 16` manifest 대상이 아니다.

## 공식 API 근거

- Microsoft [ReadFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile)은 지정 handle과 현재 file pointer에서 동기 read가 수행됨을 설명한다.
- [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex)는 handle에서 `FileIdInfo`, basic, standard, stream, attribute-tag 정보를 읽는 API다.
- [GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)는 handle의 resolved final path와 `VOLUME_NAME_GUID` 형식을 제공한다.
- [QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew)는 process handle이 가리키는 executable image name을 조회한다.
- [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)은 process creation FILETIME을 반환한다.
- [ResumeThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-resumethread)은 이전 suspend count를 반환하며 실패값은 `0xFFFFFFFF`다.

## 역사적 다음 gate와 successor

1. owner-pinned 전용 empty `pycache_prefix`, before/after exact-empty inventory와 cleanup을 설계한다.
2. `llm_batch`, `grounding`, protocol stem의 package directory·`.pyc`·ABI `.pyd` collision inventory를 fail-close한다.
3. watcher를 handle open 전 arm하고 child exit 뒤까지 유지해 source/parent/cache namespace의 add·delete·rename·swap/restore와 overflow/gap을 모두 NO-GO로 만든다.
4. 위 세 조건을 adversarial E2E에서 통과한 뒤에만 `bounded_project_source_load_candidate_closure_verified`를 검토한다.
5. 그 다음 AppContainer/LPAC, protected-root write deny, controlled IPv4/IPv6 deny, 실제 semantic parser와 external owner authority를 순차 구현한다.
6. 모든 gate 통과 전 actual 40+20, Pyserini, gold-lite, retrieval/reranker/NIL A/B, production/full scan을 시작하지 않는다.

1~4의 bounded project-source candidate gate는 successor에서 component-only로 완료했다. 현재 다음 parser gate는 trusted CPython/stdlib/native DLL/loaded-image closure와 external owner pin, AppContainer/LPAC·network/protected-root write deny, brokered escape/handle/namespace adversarial E2E, 실제 semantic parser다. actual·credited `0/40`, `0/20`과 P0/production/full scan NO-GO는 변하지 않는다.
