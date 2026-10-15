# P0 presented A-context annotation subject V2 precommit 검토

작성일: 2026-09-03 KST

상태: `ADOPT_COMPONENT_ONLY / PREANNOTATION_SUBJECT20_SEALED / ACTUAL_AND_METRIC_NO_GO`

## 결론

presented source full-frame V2의 selected 40, registry/capture bridge 40, presented A-context full-frame V1의 selected 20을 하나의 label-blind annotation subject 계보로 묶는 별도 pure component를 채택했다. 기존 A-context V1은 annotation 이후 형식이고 fixed `5×4` A-frame을 알지 못하므로 수정하거나 증거로 재사용하지 않았다. 기존 actual packet V1의 13-child inventory, Windows reader, preauthorization, supervisor, authority bridge도 변경하거나 연결하지 않았다.

새 producer는 upstream 원문 11개에서 annotation subject JSONL 20행과 precommit JSON 1개를 만든다. standalone parent는 producer와 `llm_batch`를 import하지 않고 raw framing, 구조적 파생 ID, source/A deterministic selection·surplus partition, bridge payload, Unicode codepoint span, subject와 precommit을 독립 재생한다. A census의 community scope, capture receipt, source claim-set SHA는 caller-presented opaque commitment일 뿐 실제 capture·claim 권위가 아니다.

## 계약과 계보

입력 원문은 source `scope/census/frame/seed/plan` 5개, bridge JSONL 1개, A-context `scope/census/frame/seed/plan` 5개로 총 11개다. 출력은 subject JSONL과 precommit JSON 2개이며, parent가 결속하는 raw artifact는 총 13개다.

```text
source full-frame 5 → selected source 40 → bridge 40
                                      ↓
A-context full-frame 5 → selected A 20 → annotation subject 20 → precommit
```

- source selected 40과 bridge 40은 물리 순서와 candidate identity로 exact 1:1이다.
- A census의 selected·surplus·excluded 전체 행은 source selected/bridge 40 중 하나로 되돌아가야 한다. 한 source에서 여러 surface opportunity가 나오는 것은 허용한다.
- A selected 20은 plan의 물리 순서대로 subject 20에 exact 1:1로 투영한다.
- payload는 strict UTF-8로 decode하고 `surface_start/end`는 Unicode codepoint 단위로 replay한다. surface text와 SHA를 다시 계산한다.
- source frame과 A-context frame은 서로 다른 raw/artifact SHA domain으로 보존한다.
- subject digest는 11개 upstream raw SHA와 source/A/evidence identity를 직접 결속한다.
- 시간 순서는 source full chain·selection 다음 A scope, A full chain·selection 다음 subject precommit으로 엄격히 고정한다.

## label-blind·권한 경계

truth/work/NIL/annotation/reviewer/result/model prediction 필드는 top-level과 nested inventory에서 거부한다. `GENERIC_FALLBACK` 5개는 모두 `UNRESOLVED_PREANNOTATION_EVIDENCE`이며 Track A, gold 또는 특정 작품으로 승격하지 않는다. `아생갤` 표면도 작품·현실 갤러리·alias target을 만들지 않는다.

precommit은 annotation event/review/credit를 모두 0으로, 통계 분모 기여를 `NONE`으로 고정한다. inferential·complete-case metric, actual evidence/authority, runtime/write authority, P0 Exit, production/full scan은 모두 false다. parent는 두 selection/partition과 raw-chain 구조를 재생하지만 외부 enumeration·rights·capture·seed·owner 사실성을 재생했다고 주장하지 않는다. 따라서 `source_parent_full_frame_replay_verified=false`, `a_parent_full_frame_replay_verified=false`를 유지한다.

## 전문가 회의와 반대검토

사전 검색·아키텍처·통계·MLOps 회의는 기존 packet V1을 제자리 확장하는 안을 기각하고 별도 preannotation V2 component를 채택했다. 구현 후 반복 반대검토에서 아래 결함을 재현해 회귀로 닫았다.

| 발견 | 조치 |
| --- | --- |
| A selected↔surplus를 함께 재봉인하면 parent가 수용 | source/A seed rank와 selected·surplus exact partition을 parent가 독립 재계산 |
| plan/frame의 authority·metric 문자열과 nested label key 승격 | top-level·nested exact schema, false boundary, exact gate/metric/selection constants 고정 |
| `per_profile_counts`에 임의 semantic key 은닉 | exact profile 4키, exact-int, selected 역산, source `10×4`·A `5×4` 강제 |
| A context-unit/source candidate·lineage-group 파생 ID stale 재사용 | candidate/context/group ID, census eligibility, group canonical-root와 frame accounting 재계산 |
| bridge commitment/metadata 및 seed/scope ID·SHA 타입 누락 | bridge payload·metadata·SHA·ID bounds와 scope/seed semantic type 독립 검증 |
| `None`, lone surrogate, nested int, `Fraction(0,0)`, bool-as-int 예외/우회 | public component error 정규화와 모든 numeric exact-int 검증 |
| producer-valid offset precommit, fractional A timestamp, 300자 A ID를 parent가 거부 | source/A/successor의 서로 다른 timestamp·ID domain을 분리해 양방향 parity 확보 |
| parent manifest anchor 부재 | schemas, `11+2=13`, 1 MiB output cap, packet V1 미소비, authority `NONE`을 독립 pin |

최종 red-team 누적 coherent 공격 13종은 전부 거부됐고 producer-valid parity 3종은 통과했다. 아키텍처, 통계, MLOps, 최종 red-team 판정은 모두 `ADOPT_COMPONENT_ONLY`다.

## 검증과 비간섭

| 검증 | 결과 |
| --- | --- |
| focused 신규 회귀 | `19/19 PASS` (`3.365s`) |
| source-frame/bridge/A-frame/new/actual A/packet 인접 회귀 | `114/114 PASS` (`10.613s`) |
| 전체 `test_p0_*.py` | `742/742 PASS` (`57.281s`) |
| producer·parent·test `py_compile` | `PASS` |
| component manifest parity | `4f8e70e08f153886576fad2dbaa2a35e298a1e7438e58a047bdf00105a8f01b6`, producer=parent |
| 기존 actual packet | `CHILD_FILES=13`, 신규 schema/runtime reference `0` |
| 중앙 Slang DB 1개 + publication journal 5개 | bytes/SHA 기존 기준 `6/6` exact 일치 |

이번 검증은 pure unittest, static reference 검사와 read-only hash 감사다. 실제 grounding run이 아니므로 dashboard와 `--parallel 16` 적용 대상이 아니다. publication WAL과 중앙 Slang DB에는 쓰지 않았다.

## 남은 gate와 다음 작업

다음 code-only tranche는 subject 20에 대한 결과 없는 A-event V2 target/precommit 계약이다. 그 뒤에만 별도 packet V2/envelope에서 11 upstream raw pin과 2 output child, fixed-member manifest/hash, Windows exact-member identity, preauthorization/supervisor receipt와 parent replay를 함께 version-bump한다. 기존 packet V1을 재해석하거나 과거 A-context V1 event를 credit evidence로 가져오지 않는다.

외부 source enumeration completeness, owner/rights/capture authority, trusted seed/time/revocation, code/runtime identity, 사람 annotation과 exhaustive review가 실제로 제공되기 전 actual source/context credit은 `0/40·0/20`이다. Pyserini BM25, gold-lite, retrieval/reranker/NIL A/B, P0 Exit, production/full scan은 계속 `NO_GO`다. Goal은 `ACTIVE / NOT_COMPLETE`다.
