# P0 presented A-context annotation-event V2 target precommit 구현·재회의

작성일: 2026-09-03 KST

상태: `ADOPT_COMPONENT_ONLY / RESULT_FREE_TARGET20_PRECOMMITTED / ALL_AUTHORITY_AND_METRIC_NO_GO`

## 결론

annotation subject V2의 20개 선택 단위를 실제 판정값 없이 future primary review target 20개에 1:1 결속하는 additive component를 채택했다. 기존 post-annotation A-context/A-event/packet V1은 수정하거나 입력으로 재사용하지 않았다. target은 `PRIMARY_REVIEW / NO_EVENT_RECORDED` opportunity일 뿐 event, review, 독립 관측 또는 metric denominator가 아니다.

producer는 predecessor의 upstream 11개 raw와 subject rows/precommit 2개를 검증하고 target JSONL 20행과 target precommit JSON 1개를 만든다. parent는 current producer를 import하지 않는다. 대신 이미 producer-free인 subject parent를 정확히 한 번 실행하고 receipt 전체를 재검증한 뒤, current target ID·journal genesis commitment·precommit을 별도 literal로 재생한다. 따라서 이 parent는 `producer-free composed parent`이며 standalone oracle이나 동일 프로세스 code-tamper 방어라고 주장하지 않는다.

## 계약과 계보

```text
source/A upstream raw 11
  + annotation subject rows/precommit 2
  = predecessor input 13
      ↓
  target rows 20 + target precommit 1
  = output raw 2 / transitive bound raw 15
```

- subject 물리 순서 `1..20`을 그대로 유지하며 deterministic target ID와 journal genesis commitment를 domain-separated SHA로 만든다.
- target은 subject ID·subject row SHA·annotation subject SHA·subject rows/precommit raw SHA와 precommit artifact SHA를 결속한다.
- target precommit ID는 13-input raw map, target rows raw SHA, response taxonomy SHA와 strict RFC3339 `precommitted_at`을 결속한다.
- parent는 caller가 pin한 exact 15-role raw SHA map을 hash 전 role cap 검사 뒤 검증하고, map과 aggregate SHA를 receipt에 보존한다.
- role별 cap, target line 64 KiB, canonical UTF-8/LF, duplicate key·nonfinite·BOM·CRLF·oversize 거부를 producer/parent manifest에 고정한다.
- chronology는 subject precommit보다 target precommit이 엄격히 뒤다. caller timestamp는 trusted time 증거가 아니다.

## 결과 없는 response 사전등록

공통 taxonomy만 결과 전에 고정하고 per-target 값은 넣지 않는다.

- `JUDGED → WORK_ID | NIL`
- `UNJUDGED → UNRESOLVED`
- `UNAVAILABLE → UNRESOLVED`
- `WORK_ID`만 work ID가 필요하고, `NIL`만 NIL reason이 필요하다.
- `UNRESOLVED`와 `UNAVAILABLE`은 NIL·negative·gold가 아니다.
- NIL은 future candidate enumeration completeness가 별도로 입증돼야 한다.
- 초기 `NO_EVENT_RECORDED`는 result object 자체가 없는 상태이며 terminal `UNJUDGED`와 다르다.

target/opportunity/unstarted는 `20/20/20`이지만 event, assignment, journal head, result, actual review와 credit은 모두 `0`이다. `GENERIC_FALLBACK` 5개도 제외하거나 NIL로 바꾸지 않고 target에 포함한다. target 행에는 source profile과 unresolved disposition을 복제하지 않는다.

동일 source에서 여러 surface opportunity가 나올 수 있으므로 `iid_independence_assumed=false`를 precommit·manifest·parent receipt에 고정했다. future inferential cluster unit은 `UPSTREAM_SOURCE_FRAME_CANDIDATE_ID`다. 현재 통계 분모 기여는 `NONE`, metric은 `NOT_ESTIMABLE`이다.

## 전문가 회의와 red-team 수정

검색/아키텍처, 통계/annotation, MLOps 사전회의는 기존 V1 event/packet 재사용을 기각하고 별도 15-raw component를 채택했다. 구현 후 독립 red-team과 통계 재회의에서 material finding 6건을 재현해 닫았다.

| 발견 | 수정 |
| --- | --- |
| 서로 다른 valid 15-raw 묶음이 같은 parent receipt 생성 | exact 15-role raw SHA map과 aggregate를 receipt/self-hash에 결속 |
| enum 목록만 있어 `UNJUDGED+WORK_ID` 같은 후속 해석 가능 | status↔decision matrix, nullability, NIL/reason 의미를 exact taxonomy로 고정 |
| 공백 구분 timestamp를 RFC3339로 수용 | strict `T`/timezone regex와 calendar parse를 양쪽에 적용 |
| target20을 iid20으로 오해할 여지 | iid false와 upstream source cluster unit을 precommit/manifest/receipt에 고정 |
| parent가 oversize raw를 SHA한 뒤 cap 검사 | exact role cap을 모든 raw hash보다 먼저 검사 |
| 시각이 다른 precommit이 같은 ID 공유 | `precommitted_at`을 deterministic precommit ID material에 포함 |

최종 판정은 아키텍처·통계·MLOps·red-team 모두 `ADOPT_COMPONENT_ONLY`다. 테스트 안의 명시적 attack/reseal variant는 최소 48개이며 모두 거부됐다.

## 검증과 비간섭

| 검증 | 결과 |
| --- | --- |
| focused 신규 회귀 | `19/19 PASS` (`8.677s`, 최종) |
| predecessor subject + 신규 | `38/38 PASS` |
| source/A frame·subject·신규·actual A/packet 인접 | `133/133 PASS` (`19.067s`) |
| 전체 `test_p0_*.py` | `761/761 PASS` (`65.262s`) |
| producer·parent·test `py_compile` | `PASS` |
| component manifest parity | `ac99ac5544bbfa5d5e264eb93bc2086eb9eed2271e18534c173df1be0dc86ecd` |
| response taxonomy commitment | `3728334be85d5b53fd1b8f403c8471bad78817735271a301bab07590c063dd41` |
| 기존 actual packet | `CHILD_FILES=13`, 기존 runtime reference `0` |
| 중앙 Slang DB 1개 + publication journal 5개 | bytes/SHA 기존 기준 `6/6` exact 일치 |

protected endpoint의 최종 SHA는 DB `a8c3fb9b…cf10a`, journal 순서대로 `32c9cb6c…e8ff`, `a974bdf5…aee3`, `fe6b90e8…5603`, `d0a9891e…452e`, `206398b0…91a1`이다. 이번 검증은 pure unittest, static scan, read-only hash 감사다. 실제 grounding run이 아니므로 dashboard와 `--parallel 16` 적용 대상이 아니며 DB/WAL/publication에는 쓰지 않았다.

## 남은 gate와 다음 작업

다음 code-only tranche는 별도 packet V2/envelope다. 안전한 후보 inventory는 upstream 11 + subject 2 + target 2 = child 15, manifest 포함 fixed member 16이다. 이 수를 전문가 회의에서 확정한 뒤 별도 Windows reader/binder, preauthorization와 supervisor V2를 같은 version boundary로 설계해야 한다. 기존 packet V1의 13-child, preauth/Windows 14-member와 4-step supervisor는 그대로 둔다.

외부 enumeration·owner/rights/capture authority, trusted time/code identity, reviewer assignment, append-only journal과 실제 사람 결과가 없으므로 actual source/context credit은 `0/40·0/20`이다. Pyserini BM25, gold-lite, retrieval/reranker/NIL A/B, P0 Exit, production/full scan은 계속 `NO_GO`다. Goal은 `ACTIVE / NOT_COMPLETE`다.
