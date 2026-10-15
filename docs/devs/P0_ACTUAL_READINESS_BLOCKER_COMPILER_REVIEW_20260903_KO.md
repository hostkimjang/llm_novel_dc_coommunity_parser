# P0 actual readiness blocker compiler 구현·전문가 재회의

## 결론

`zero-input host preflight → blocker-only readiness compiler → external signed provisioning → actual 40+20` 순서의 두 번째 단계를 구현했다. 판정은 **`ADOPT_COMPONENT_ONLY / ACTUAL_READINESS_AUTHORITY_NO_GO`**다.

새 compiler는 actual 실행기가 아니다. 공개 함수 `compile_fixed_p0_actual_readiness_blockers()`는 인자를 받지 않고, 같은 호출에서 Windows owner provisioning preflight를 정확히 한 번 읽은 뒤 현재 blocker를 self-hash receipt로 정리한다. all-green Python mock, 재봉인 receipt, 구조적으로 유효한 synthetic 40+20도 actual 권한이나 credit으로 바꾸지 않는다.

현재 Windows 호스트 결과는 다음과 같다.

| 항목 | 결과 |
| --- | --- |
| compiler gate | `ACTUAL_READINESS_BLOCKERS_COMPILED_AUTHORITY_NO_GO` |
| compiler receipt | `104d7c58271c7d7ae20d00badeb09185023eff344f37fe05eef1867d2c93a501` |
| child preflight | `FIXED_STORE / NO_GO` |
| child receipt | `bbed3cdd9d309f22db22fe9607b9000f31d924b8ed3c677b9dbbfadf2351a172` |
| actual selected source unit | credited `0/40` |
| actual A sampling unit | credited `0/20` |
| P0 Exit·production·full scan | `false / false / false` |
| 다음 단계 | `EXTERNAL_OWNER_PROVISIONING_REQUIRED` |

fixed store 실패에서 관측이 끝났으므로 이 결과만으로 service·image가 실제로 없다고 단정하지 않는다. SCM과 image 단계는 실행되지 않았다.

## 전문가 회의와 채택안

구현 전 검색·통계/데이터·시스템/MLOps·red-team 세 축을 독립 회의로 분리했다. 구현 뒤 같은 축으로 반대검토를 반복했다.

| 제안 | 판정 | 반영 |
| --- | --- | --- |
| zero-arg same-call child observation | `ADOPT` | caller receipt/path/key/time/nonce/callback 입력을 두지 않고 public preflight를 1회만 호출 |
| self-hash를 authority로 사용 | `REJECT` | child와 compiler SHA는 checksum일 뿐 freshness·서명·replay 방지가 아님을 false truth table로 고정 |
| compiler에서 actual runtime 실행 | `REJECT` | supervisor/parser/service start/nonce consumption/WAL/Slang writer를 호출·import하지 않음 |
| current endpoint 보호 | `ADOPT_NARROW` | 중앙 Slang DB와 publication journal의 두 point-in-time path/bytes/mtime/SHA projection만 비교 |
| endpoint 비교를 runtime 비간섭으로 승격 | `REJECT` | `POINT_IN_TIME_PRE_POST_ONLY`; transient write·continuous watch·runtime noninterference는 모두 false |
| synthetic/structural observed 40+20 credit | `REJECT` | observed·credited를 모두 0으로 고정하고 `BLOCKER_ONLY_COMPILER_NOT_AUTHORITY`를 마지막 blocker로 유지 |
| 40 source 분모 | `ADOPT` | raw claim row가 아니라 label-blind unique selected source claim unit 40, source snapshot에서 profile 10×4 역산 |
| A 20 분모 | `ADOPT` | annotation event 수가 아니라 unique sampling unit 20과 각 unit의 bound primary human journal |
| UNJUDGED/UNAVAILABLE 삭제 | `REJECT` | coverage는 selected 20 전체, terminal accuracy는 JUDGED-only, worst-case는 selected 20 전체로 분리 |
| P1 retrieval/reranker/NIL 시작 | `DEFER` | P0 Exit 전에는 blocker 유지 |

## 구현 경계

### blocker compiler

`src/llm_batch/grounding/p0_actual_readiness_blocker_compiler.py`는 다음을 수행한다.

1. fixed repository endpoint인 `slang_db/slang_db.json`과 `out/publication_commit_journals/*.jsonl`의 첫 projection을 읽는다.
2. zero-input owner provisioning preflight를 정확히 한 번 호출한다.
3. child의 exact field inventory, schema/gate/decision, bool/int type, 5개 stage truth table, blocker 순서, service/image projection, self-hash를 재검증한다.
4. 같은 endpoint의 두 번째 projection을 읽고 inventory·bytes·mtime·SHA 일치를 기록한다.
5. actual execution과 권한을 항상 닫은 blocker-only receipt를 메모리에서 반환한다.

child가 malformed/resealed이면 raw receipt를 반향하지 않고 `HOST_PREFLIGHT_RECEIPT_NOT_VERIFIED`, 호출이 일반 예외로 실패하면 `HOST_PREFLIGHT_EXECUTION_FAILED`를 최상위 blocker에도 추가한다. `KeyboardInterrupt`와 `SystemExit`은 삼키지 않는다.

필수 보호 범주는 actual authority/runtime 정본과 같은 순서다.

1. `CENTRAL_SLANG_DB`
2. `CHECKPOINT`
3. `DECISION_LEDGER`
4. `PUBLICATION_JOURNAL`
5. `RECOVERY`
6. `RESULT`

compiler가 직접 비교하는 현재 endpoint는 1번과 4번뿐이다. 따라서 six-category owner pin/watch, process-wide write deny, continuous runtime noninterference는 계속 blocker다.

### 분모 계약

40과 20을 machine-readable grain으로 분리했다.

- `required_actual_selected_source_claim_unit_count=40`: label-blind seal의 unique selected input unit이다. 1:N typed claim row가 생겨도 unit credit은 늘지 않는다.
- `required_actual_a_sampling_unit_count=20`: unique context/sampling unit이다. 재검토 event가 늘어도 sampling-unit credit은 늘지 않는다.
- `observed_actual_source_claim_row_count=0`, `observed_actual_a_annotation_event_count=0`: unit 분모와 raw row/event 수를 혼합하지 않는다.
- `annotation_coverage_denominator=ALL_SELECTED_20_INCLUDING_UNJUDGED_UNAVAILABLE`
- `terminal_accuracy_denominator=JUDGED_ONLY`
- `worst_case_denominator=ALL_SELECTED_20`

route의 profile/quota/input 상수와 packet의 A-context 상수를 테스트에서 교차검증한다. synthetic fixture, schema example, self-hash, local HMAC, Python all-green receipt는 credit 근거가 아니다.

## 구현 중 발견·수정한 선행 결함

전문가 재회의가 기존 preflight receipt의 관측 모순 두 건을 찾았다.

1. service 설정 검증 후 image 단계가 실패하면 `service_configuration_candidate_verified=true`인데 service projection이 빈 객체로 사라졌다. `_StageNoGo`와 일반 image 예외 경로 모두에서 검증된 projection을 보존하도록 수정했다.
2. generic malformed v2 실패도 `v1_future_authority_hard_rejected=true`로 기록됐다. coherent v1 body/receipt identity가 실제로 결속된 경우에만 true가 되도록 분리했다.

compiler 쪽에서는 snapshot 실패의 빈 projection 두 개를 stable로 오판하던 반례와 mtime-only 변경을 닫았다. usable snapshot과 필수 endpoint 종류가 모두 있을 때만 inventory/content/mtime equality를 true로 만들며, 이름도 `compiler_pre_post_endpoint_projection_match_observed`로 축소했다.

## 공격 검증

다음 공격을 독립 literal oracle로 고정했다.

- public API 인자·environment/cwd/home/argv/shell/subprocess/network selector
- missing/extra/custom field와 non-dict child
- decision/authority/production/count/stage/observation 재봉인
- bool-as-int, blocker 누락·중복·재정렬
- service/image projection 불일치와 path hash swap
- fully green self-hashed Python receipt
- observer 일반 예외와 BaseException 구분
- endpoint 추가·삭제·content SHA·mtime-only 변경, snapshot 실패
- synthetic/structural count의 actual credit 세탁
- output self-hash·blocker order·모든 authority/action false 전수 검사

최종 독립 red-team 판정은 `ADOPT_BLOCKER_ONLY`다. path stat/open/stat 사이 ABA는 native held-handle/continuous watch가 아니므로 non-authoritative residual risk로 남기고, receipt의 transient/continuous/runtime 증거는 false다.

## 검증 결과

| 검증 | 결과 |
| --- | --- |
| compiler + preflight focused | `22/22 PASS` |
| 전체 `test_p0*.py` | `531/531 PASS` (`40.466s`) |
| 관련 module/test `py_compile` | `PASS` |
| current compiler 2회 | receipt 동일 `104d7c58…a501` |
| current endpoint projection | 중앙 DB 1 + publication journal 5 = `6/6` pre/post 일치 |
| 좁은 fixture noninterference audit | receipt `6033c6d0…98204e`, `6/6` SHA 불변 |

이 검증은 component unittest와 read-only point-in-time audit이다. regression-safe grounding actual run이 아니므로 dashboard와 `--parallel 16` manifest 대상이 아니다. `tools/audit_p0_grounding_noninterference.py`도 2개 endpoint 종류만 보는 좁은 audit이므로 전체 runtime 비간섭으로 확대하지 않는다.

## 잔여 blocker와 다음 순서

현재 Goal은 완료되지 않았다. 다음 순서를 고정한다.

1. 후속 v3 회의 결과에 따라 외부 owner가 signed v3 successor, native verifier service/image, Authenticode·WDAC/UMCI·provider policy를 저장소 밖 권한 경계에서 provision한다. v2는 positive authority에 부족하다.
2. native signed observer가 service process token, embedded resource, active code integrity, loaded provider/catalog, trusted time/revocation, durable nonce와 single observation interval을 결속한다.
3. protected 6-category owner pin/watch, process-wide OS write deny, annotation predecessor/append-only, rights/sampling/guideline/reviewer policy를 owner authority에 결속한다.
4. 별도 새 version의 positive readiness gate를 구현·공격 검증한다. 현재 blocker compiler를 GO compiler로 확장하지 않는다.
5. 위 gate가 모두 닫힌 뒤에만 dashboard ON·요청 `--parallel 16`으로 actual selected source unit 40(profile 10×4)과 A sampling unit 20을 실행한다.
6. post-run raw/event/owner final attestation/runtime 비간섭을 별도 credit compiler에서 확인한 뒤 P0 Exit을 재회의한다.
7. P0 Exit 뒤에만 Pyserini/gold-lite/RRF·reranker/NIL shadow A/B를 시작한다.
