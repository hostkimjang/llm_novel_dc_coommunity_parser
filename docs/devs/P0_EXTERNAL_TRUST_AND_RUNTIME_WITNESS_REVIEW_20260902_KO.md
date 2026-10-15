# P0 외부 trust store·Windows runtime witness 구현 및 재회의

작성일: 2026-09-02 KST

기존 seal-id registry의 exact dataclass clone 소비 문제는 후속 [`P0_EXTERNAL_TRUST_STATE_IDENTITY_HARDENING_REVIEW_20260902_KO.md`](P0_EXTERNAL_TRUST_STATE_IDENTITY_HARDENING_REVIEW_20260902_KO.md)에서 실제 재현한 뒤 object-identity registry로 교체했다. 후속 전체 P0 `439/439 PASS`에도 external trust/owner authority와 P0 Exit은 계속 `NO-GO`다.

후속 parser process·Job component 상태는 [`P0_PARSER_PROCESS_JOB_COMPONENT_REVIEW_20260902_KO.md`](P0_PARSER_PROCESS_JOB_COMPONENT_REVIEW_20260902_KO.md)를 따른다. 최신 비대칭 서명 수학 successor는 [`P0_EXTERNAL_OWNER_ASYMMETRIC_SIGNATURE_REVIEW_20260902_KO.md`](P0_EXTERNAL_OWNER_ASYMMETRIC_SIGNATURE_REVIEW_20260902_KO.md)를 따른다. ECDSA 수학은 통과했지만 pin이 caller-presented 후보이므로 이 문서의 external authority/P0 NO-GO 경계는 유지된다.

## 결론

이번 tranche는 caller key를 받지 않는 trust-store key 검증, 원자적 single-use nonce 소비, Windows QPC·USN·directory watch·restricted-token probe, 기존 7단계 authority supervisor를 같은 호출에서 감싸는 결합 executor를 구현했다. 당시 module-issued trust/runtime state는 같은 프로세스에서 한 번만 소비됐고 `SimpleNamespace` 위조·비동일 타입 복제·receipt 변조·재소비를 거부했지만, exact private dataclass clone은 막지 못했다. 이 제한은 위 successor에서 교정했다.

채택 범위는 `ADOPT_COMPONENT_ONLY`다. trust store와 시간은 여전히 caller가 선택할 수 있고, HMAC secret도 verifier가 읽는 anchor 안에 있다. Windows 현 호스트에서는 QPC와 root/parent watch가 통과했지만 6개 category 모두 USN volume open이 `error_code=5`라 interval은 실패했다. 제한 토큰은 현재 thread에만 적용되므로 process/job 전체 쓰기 금지나 실제 parser sandbox 증거가 아니다. 따라서 다음 강한 주장은 모두 false다.

- `external_trust_store_verified=false`
- `revocation_current_verified=false`
- `trusted_time_verified=false`
- `external_owner_trust_verified=false`
- `external_root_identity_pin_verified=false`
- `os_write_deny_verified=false`
- `runtime_noninterference_verified=false`
- `parser_runtime_execution_verified=false`
- `actual_authority_granted=false`
- `p0_phase_exit=false`
- `production_approval=false`
- `full_scan_approval=false`

현재 gate는 `EXTERNAL_STORE_KEY_AND_NONCE_EXECUTED / BOUNDED_WINDOWS_WITNESS_COMPONENT_ONLY / EXTERNAL_OWNER_TIME_REVOCATION_NO_GO / PARSER_JOB_RUNTIME_NO_GO / ACTUAL_EVIDENCE_0_OF_40_0_OF_20 / PRODUCTION_NO_GO`다.

## 구현 범위

### 외부 trust-store executor

`src/llm_batch/grounding/p0_external_owner_trust_execution.py`는 다음을 수행한다.

- run·packet·6개 보호 root 밖의 exact 2-file trust store와 nonce ledger를 검사한다.
- canonical UTF-8 JSON+LF, duplicate/BOM/non-finite/trailing, symlink/reparse/hardlink와 비정상 inventory를 거부한다.
- trust anchor의 store key로 owner preauthorization HMAC을 검증하되 caller에게 key 인자를 받지 않는다.
- anchor·revocation·session·run·nonce·packet root·parser provenance·원문 SHA를 receipt와 nonce record에 결속한다.
- `O_EXCL` 원자 생성과 file fsync/readback을 사용해 동시 16개 소비자 중 정확히 하나만 성공시킨다.
- Windows에서는 delete-share 없는 held directory handle로 nonce ledger rename/delete 교체를 막고, POSIX에서는 directory fd 상대 생성을 사용한다.
- 발급 state의 key는 registry seal과 receipt/key/nonce hash를 다시 검증한 뒤 한 번만 반환하고 즉시 bytearray를 zeroize한다.

이 성공은 현재 caller-selected pinned store 안에서 nonce가 소비됐다는 뜻이다. `nonce_ledger_action_applied=true`와 `security_control_state_mutated=true`지만 `protected_pipeline_state_mutated=false`, `action_applied=false`다. Windows directory-entry flush, reboot/power-loss durability, cross-process immutable ledger는 증명하지 않았으므로 `power_loss_durable_replay_verified=false`다.

### Windows bounded runtime witness

`src/llm_batch/grounding/p0_windows_runtime_evidence.py`는 exact ordered 6 category에 대해 다음 구간을 관측한다.

1. 모든 parent namespace watcher와 root watcher를 먼저 arm한다.
2. PRE final path·volume serial·file ID·recursive inventory·USN을 캡처한다.
3. restricted current-thread token으로 비변경 write-open probe를 수행한다.
4. callback을 실행하고 POST identity·inventory·USN을 캡처한다.
5. 두 watcher를 종료해 event·overflow·gap을 판정한다.

rename-aside→replacement→restore 공격은 parent namespace watcher에서 `NO_GO`로 닫는다. QPC는 순서만 증명하며 UTC trusted time은 아니다. callback이 validator인 결합 executor는 `impersonate_operation=false`를 사용한다. 이는 validator source read를 허용하기 위한 probe-only 경계이고 parser sandbox가 아니다.

`bounded_runtime_noninterference_verified`는 제한된 현재 호출의 진단 필드다. `current_thread_restricted_token_write_open_denial_verified`와 별개로 process/job-wide 이름인 `os_write_deny_verified`와 `runtime_noninterference_verified`는 항상 false다.

### 결합 supervisor

`src/llm_batch/grounding/p0_external_authority_runtime_supervisor_execution.py`는 다음 순서를 고정한다.

1. canonical owner preauthorization과 6개 root map을 검사한다.
2. 외부 trust executor가 nonce를 먼저 소비한다.
3. module-issued trust state를 한 번 소비해 key를 얻는다.
4. Windows watcher가 기존 7단계 combined validator 호출을 감싼다.
5. module-issued runtime state를 한 번 소비해 raw↔receipt self-hash coherence를 확인한다.
6. trust/runtime/combined child receipt의 실제 self-hash와 known schema를 다시 계산한다.
7. session·run·nonce·preauthorization bytes와 final-path projection을 교차 결속한다.

nonce 소비 뒤 하위 실행이 실패해도 nonce를 삭제하지 않는다. retry가 combined operation에 재진입하지 않는 fail-closed 동작을 회귀로 고정했다. trust state 발급 뒤 consume 전 invariant가 실패할 때도 key-bearing registry entry를 폐기한다. serialized presented receipt는 exact outer field inventory·child schema·aggregate hash·root projection·고정 false invariant를 검사한 뒤 모든 execution truth를 다시 false로 내린다.

## 전문가 재회의 판정

| 의제 | 판정 | 근거와 제한 |
| --- | --- | --- |
| canonical JSON·exact inventory·alias 방어 | `ADOPT` | 입력·저장소 구조 계약으로 사용 |
| store-key 검증과 one-shot trust state | `ADOPT_COMPONENT_ONLY` | same-process 결속에는 유효하지만 caller-selected HMAC store는 외부 owner authority가 아님 |
| `O_EXCL` nonce 소비와 실패 시 burn | `ADOPT_COMPONENT_ONLY` | replay fail-close는 유효하나 Windows directory-entry/power-loss·cross-process durability 미증명 |
| QPC·root/parent watch·identity/inventory·USN 수집 | `ADOPT_COMPONENT_ONLY` | bounded witness이며 trusted time·root별 USN record 귀속이 아님 |
| restricted-token write-open probe | `ADOPT_DIAGNOSTIC_ONLY` | current thread probe이며 process/job 전체 쓰기 금지가 아님 |
| `impersonate_operation=false` validator wrapper | `ADOPT_COMPONENT_ONLY` | validator 실행 가능성을 보존하지만 parser sandbox 증거는 아님 |
| 외부 trust+runtime+7단계 결합 receipt | `ADOPT_COMPONENT_ONLY` | self-hash·one-shot·cross-binding은 채택, authority는 계속 NO-GO |
| caller store·local wall clock·revocation math의 외부 권한 승격 | `REJECT` | 독립 trust root·trusted time·rollback protection이 없음 |
| validator callback을 실제 parser execution으로 간주 | `REJECT` | parser provenance와 별도 process/job sandbox가 없음 |
| actual 40+20·P0 Exit·production/full scan 승격 | `REJECT` | 실제/credited 모두 `0/40`, `0/20` |
| Pyserini·gold-lite·retrieval/reranker/NIL A/B 시작 | `DEFER` | P0 전체 Exit 뒤 별도 shadow로 시작 |

## fresh 검증

| 범위 | 결과 |
| --- | --- |
| external owner trust | `30 PASS` |
| Windows runtime evidence | `14 PASS` |
| external+runtime 결합 supervisor | `11 PASS` |
| 신규 focused 합계 | `55 PASS` (`6.233s`) |
| 기존 75 direct-adjacent 포함 | `130 PASS` (`9.870s`) |
| selected-adjacent | 기존 core `260 PASS` + 측정·publication·신규 `180 PASS` = `440 PASS` |
| Python compile | 신규 3개 모듈·테스트 `py_compile PASS` |
| 기존 상태 비간섭 | 중앙 Slang DB 1개+publication journal 5개 `6/6` byte·SHA 불변 |

현 Windows 진단 receipt는 `qpc=true`, `continuous_watch=true`, `usn_interval=false`, 6개 `pre_usn.error_code=[5,5,5,5,5,5]`, `bounded=false`, `os_write_deny=false`, `runtime_noninterference=false`, gate `NO_GO_RUNTIME_EVIDENCE_INCOMPLETE`다. 이번 검증은 unittest·read-only audit이며 actual parser run이 아니므로 `--parallel 16`/dashboard 실행 대상이 아니다.

## 공식 API 근거와 해석

- Microsoft의 [CreateFile 문서](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea)는 `CREATE_NEW`의 기존 파일 실패와 `FILE_FLAG_WRITE_THROUGH` 의미를 설명한다. 현재 구현은 원자 생성·file flush를 사용하지만 hardware/metadata durability를 별도 false로 둔다.
- [File Caching](https://learn.microsoft.com/en-us/windows/win32/fileio/file-caching)은 metadata가 cache될 수 있고 명시적 flush가 필요함을 설명한다. Windows directory entry power-loss durability를 true로 올리지 않은 근거다.
- [ReadDirectoryChangesExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-readdirectorychangesexw)는 buffer overflow 시 내용을 버리고 zero bytes를 반환할 수 있음을 명시한다. 구현은 overflow/gap을 fail-close한다.
- [FSCTL_QUERY_USN_JOURNAL](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_query_usn_journal)은 NTFS volume handle을 요구한다. 현 호스트 access denied는 성공으로 대체하지 않는다.
- [고해상도 timestamp 지침](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)은 QPC가 외부 시간 기준과 동기화되지 않는다고 설명한다. QPC chronology와 trusted UTC time을 분리한다.
- [Windows access token 개요](https://learn.microsoft.com/en-us/windows/win32/secauthz/access-tokens)는 restricted token의 SID/privilege 제한을 설명한다. current-thread impersonation을 process-wide sandbox로 간주하지 않는다.

## 다음 P0 순서

1. verifier 밖의 비대칭 owner signing key와 독립 read-only public-key fingerprint pin을 provision한다.
2. trusted time, signed revocation monotonic sequence와 rollback 방지 owner를 분리한다.
3. ACL broker나 transactional journal로 cross-process nonce ledger와 crash/reboot durability를 검증하고 downstream success/failure outcome을 append-only 기록한다.
4. owner가 6개 category의 volume GUID·serial·file ID를 사전 서명하고 held handle·root별 USN record를 전체 interval에 결속한다.
5. elevated least-privilege USN broker와 별도 parser process의 Job Object/AppContainer·network deny·write deny·provenance를 구현한다.
6. root swap, watch overflow, journal reset, sibling noise, process/thread escape, crash/reboot adversarial Windows E2E를 수행한다.
7. owner numerical policy SHA를 결과 전에 확정한 뒤에만 dashboard ON·`--parallel 16`으로 actual source claim 40건+A-context 20건을 수집·사람 판정한다.

그 전에는 actual·credited `0/40`, `0/20`, `P0_PHASE_EXIT=false`, `METRICS_NOT_ESTIMABLE`, `REVIEW_LOCKED`, `full_scan_approval=false`를 유지한다.
