# P0 presented neutral batch exact-accounting v1 검토

작성일: 2026-09-03 KST
상태: `ADOPT_COMPONENT_ONLY / ACTUAL_AUTHORITY_NO_GO / METRICS_NOT_ESTIMABLE`

## 결론

full eligible sampling frame V2가 고른 40개 입력을 caller-presented registry/capture와 연결하고, 실행 전 inventory를 봉인한 뒤 입력마다 정확히 한 번 neutral core를 호출해 40개 terminal result와 미검토 inventory를 만드는 별도 pure component를 채택했다. 기존 actual route·protocol·worker·Windows sandbox·packet·ledger·publication·중앙 Slang DB에는 연결하지 않았다.

세 전문가의 최종 판정은 다음과 같다.

| 관점 | 최종 판정 |
| --- | --- |
| 검색·parser | `ADOPT_COMPONENT_ONLY / PRESENTED_EXACT_ITT_AND_NON_ERROR_1:N_REPLAY_PASS / ACTUAL_EXECUTION_AND_CREDIT_NO_GO` |
| 통계 | `ADOPT_COMPONENT_ONLY / FIXED_ITT_40_AND_NONESTIMABLE_BOUNDARY_PASS / ACTUAL_NO_GO` |
| 데이터·MLOps | `ADOPT_COMPONENT_ONLY / PRESENTED_EXACT_ACCOUNTING_AND_INDEPENDENT_NON_ERROR_REPLAY_PASS / ACTUAL_AUTHORITY_NO_GO` |

이 component가 증명하는 것은 제출된 40개 입력의 exact accounting과 non-error neutral core 결과의 독립 replay다. 외부 모집단 완전성, registry/capture 사실성, 실제 runtime 실행, 숨은 retry 부재, `CORE_ERROR` 사실성, code/dependency identity, 사람 전수 검토는 증명하지 않는다. 따라서 actual·credited source/context는 계속 `0/40·0/20`, `p0_phase_exit=false`, production/full scan은 `NO_GO`다.

## 채택 이유와 범위

기존 semantic route의 exact-one 계약은 이미 가공된 claim을 대상으로 하며, V2 frame 후보에서 raw payload·neutral 0:N observation으로 이어지는 물리적 40입력 ITT 회계를 대신하지 못한다. 특히 한 입력에서 observation이 여러 개 생겨도 source credit이나 표본 수가 늘지 않아야 하고, unsupported·invalid·no-match·error도 분모에서 사라지면 안 된다. 그래서 기존 route를 확장하지 않고 다음 세 파일로 격리했다.

- `src/llm_batch/grounding/p0_presented_batch_exact_accounting_v1_contract.py`
- `src/llm_batch/grounding/p0_presented_batch_exact_accounting_v1_parent_validator.py`
- `tests/test_p0_presented_batch_exact_accounting_v1.py`

artifact chronology는 다음으로 고정된다.

1. V2 `sampling_plan` selection seal
2. exact 40행 presented registry/capture bridge JSONL
3. batch precommit
4. 입력별 neutral core 1회 시도
5. exact 40행 physical result JSONL과 ITT receipt
6. contextual observation 및 full-payload missed-span 미검토 inventory seal

bridge의 `candidate_id`는 V2 frame 후보 ID이고 `registry_record_id`는 caller-presented registry ID다. 두 값은 반드시 달라야 하며, 동일 ID를 쓰는 coordinated bundle은 producer와 parent가 모두 거부한다. bridge는 V2 physical order, locator/lineage/adapter/profile/platform/day/stratum identity, registry commitment, capture metadata, strict base64 payload와 payload SHA를 결속한다. 입력당 payload는 최대 256 KiB, 전체는 최대 10 MiB다.

precommit은 plan raw/artifact SHA, selected-set SHA, bridge raw/inventory SHA, core version/manifest, exact `40`, profile별 `10×4`, retry/replacement/backfill/spill 금지를 함께 봉인한다. result는 입력마다 `attempt_count=1`이고 다음 terminal taxonomy 중 하나만 가진다.

- `MATCHED`
- `NO_MATCH`
- `UNSUPPORTED_PROFILE`
- `INVALID_CAPTURE`
- `CORE_ERROR`

누락·중복·추가·재정렬·재순번, profile/candidate/registry/payload swap은 거부된다. 한 입력이 실패해도 다음 입력을 계속 처리하며 `CORE_ERROR`도 ITT 40 분모에 포함한다. error에는 고정된 `CORE_EXECUTION / UNEXPECTED_CORE_EXCEPTION`만 남기고 raw exception·trace·message는 반향하지 않는다.

## 독립 parent와 권위 경계

standalone parent는 `llm_batch`와 producer/core를 import하지 않는다. caller가 반드시 제출하는 `expected_sampling_plan_raw_sha256`와 `expected_precommit_raw_sha256` pin을 확인한 뒤 V2 plan의 구조와 bridge/precommit/result/receipt/inventory를 독립 검증한다. non-error 결과는 payload bytes부터 neutral core를 별도 구현으로 재생하므로 observation 삭제·복제·재정렬·span 이동과 fully resealed `NO_MATCH` 세탁을 거부한다.

다만 이 pin은 caller-presented 값이지 외부 owner 권위가 아니다. parent도 V2 full census와 frame 전체를 재실행하지 않으므로 `upstream_full_frame_replay_verified=false`다. fully resealed 정상 행을 `CORE_ERROR`로 바꾼 새 bundle은 구조적으로 “제출된 오류 회계”로 수용할 수 있다. 이 경우에도 `core_error_presented_only=true`, `core_error_factuality_verified=false`, runtime authority false로 고정되며 실제 error rate·성능·실행 증거로 사용할 수 없다.

## 미검토 inventory와 통계 경계

각 emitted observation의 review unit ID는 candidate, registry, selected-input SHA, bridge row, payload, core result, observation 순번·hash에 결속된다. observation 유무와 무관하게 40개 모든 입력에는 full-payload missed-span review unit을 하나씩 만든다. 현재는 inventory만 봉인했으며 사람 판정은 `0`, `exhaustive_human_review_verified=false`다.

component manifest, batch receipt, parent receipt는 다음 값을 exact하게 고정한다.

```text
metric_status = NOT_ESTIMABLE_PRESENTED_ACCOUNTING_ONLY
inferential_metrics_allowed = false
complete_case_metrics_allowed = false
observation_rows_are_sampling_units = false
sampling_unit = SELECTED_INPUT_LINEAGE
```

따라서 1:N observation 수, complete-case subset, `CORE_ERROR` 제외 subset으로 정확도·재현율·오류율·credit을 계산할 수 없다. 테스트 fixture의 disposition 수는 계약 검증용일 뿐 실제 데이터 분포나 metric이 아니다. `아생갤`도 neutral `surface_text`로만 보존하며 작품/현실 갤러리 target, alias relation, retrieval query, route, credit을 만들지 않는다.

## 사후 반대검토에서 닫은 결함

| 결함 | 조치 |
| --- | --- |
| empty payload와 unsupported profile 판정 순서가 core/parent에서 달랐음 | empty payload를 양쪽에서 먼저 `INVALID_CAPTURE`로 판정하고 공개 회귀 추가 |
| `candidate_id == registry_record_id` 허용 | producer와 parent 양쪽 exact 분리 강제 |
| 큰 정수·잘못된 달력 시각에서 raw 예외 가능 | 양쪽 custom validation error로 정규화 |
| 5,000-depth JSON에서 `RecursionError` 누출 | parse와 canonical re-encode 양쪽을 custom error로 정규화하고 direct/public 회귀 추가 |
| parent bool/int scalar 혼동 | exact integer/boolean validator 적용 |
| V2 plan 구조 검증 부족 | nominal fraction, stratum shape, gate status, surplus count 검증 강화 |
| 통계 금지 표면 누락 | metric status, inferential/complete-case false, observation non-sampling, lineage sampling unit을 manifest·receipt에 결속 |

검색 검토는 core-parent 조합 1,000건 추가 대조에서 mismatch 0을 확인했다. MLOps 검토는 조합 256건과 무작위 Unicode payload 2,000건에서 exact parity를 확인했다. 통계 검토는 metric/sampling-unit 다섯 coordinated reseal 공격을 모두 parent가 거부함을 확인했다.

## 검증과 비간섭

| 검증 | 결과 |
| --- | --- |
| focused 신규 회귀 | `22/22 PASS` |
| frame/core/route/protocol/sandbox/packet 인접 회귀 | `150/150 PASS` |
| 전체 `test_p0_*.py` | `640/640 PASS` |
| producer·parent·test `py_compile` | `PASS` |
| producer/parent manifest | `c7beb367d62a4af025643d42caddf20caccb4938cd5a68dac8b649ee49b165c1` exact |
| 기존 runtime 파일 successor token | `0` |
| 기존 packet inventory | `CHILD_FILES == 13` |
| 중앙 Slang DB 1개 + publication journal 5개 | bytes/SHA `6/6` 불변 |

이번 검증은 pure unittest·정적 불변성 감사이며 actual test/validation run이 아니다. 그래서 dashboard를 띄우거나 `--parallel 16` runtime을 시작하지 않았다. actual run을 열 때만 저장소 정책대로 dashboard ON과 요청 병렬도 16을 적용한다.

## 다음 gate

2026-09-03 후속 갱신: 아래에서 제안한 입력별 terminal review 구조는 별도 [`P0 presented neutral review accounting v1`](P0_PRESENTED_NEUTRAL_REVIEW_ACCOUNTING_V1_REVIEW_20260903_KO.md)로 구현하고 세 전문가가 component-only로 채택했다. 다만 그것도 caller-presented 회계이며 실제 reviewer·human judgment·gold completeness 권위는 없으므로 `actual_human_review_count=0`과 metric/actual/P0 NO-GO는 바뀌지 않았다.

구현된 successor는 입력 40개 각각에 정확히 한 review terminal을 요구하고 `JUDGED/UNAVAILABLE/UNJUDGED`를 분리한다. neutral gold span의 exact emitted set과 missed span을 함께 판정하며 `UNAVAILABLE`은 0점이 아니라 null이다. 다음 gate는 이 구조에 외부 reviewer·owner 권위를 공급해 실제 `JUDGED` 40/40과 gold completeness를 증명하는 일이다. successor도 semantic work target을 발명하거나 actual source credit을 주지 않는다.

그 뒤에도 external enumeration completeness, signed owner precommit, trusted beacon/time/revocation/durable nonce, 별도 A-context full frame, registry/capture authority, protocol/worker/sandbox/code identity, route/packet/parent-ledger successor가 모두 필요하다. 이 gate들을 통과하기 전에는 actual 40+20, Pyserini BM25, gold-lite metric, retrieval/reranker/NIL shadow A/B를 시작하지 않는다.
