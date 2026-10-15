# P0 presented dual-blind review campaign precommit v1 검토

작성일: 2026-09-03 KST
판정: `ADOPT_COMPONENT_ONLY / RESULT_FREE_PRECOMMIT_STRUCTURE_PASS / EXTERNAL_REVIEW_AUTHORITY_NO_GO / RESULT_AND_METRIC_NO_GO`

## 결론

기존 presented review 40건을 실제 사람 검토로 소급 승격하지 않고, 새 캠페인의 결과를 보기 전에 reviewer·task·분모·불일치 규칙을 고정하는 별도 precommit component를 채택했다. 입력 40개마다 서로 다른 `PRIMARY_A`, `PRIMARY_B`, `DISAGREEMENT_ADJUDICATOR_RESERVE`를 배정해 primary 80개, reserve capacity 40개, 총 120개 assignment를 봉인한다.

이 결과는 실행된 사람 심사나 권위 있는 gold가 아니다. 현재 primary terminal은 `P=0/80`, two-terminal pair coverage는 `T=0/40`, both-`JUDGED` pair는 `J=0/40`, 실제 adjudication은 `0`, final judged input은 `F=0/40`이다. required adjudication denominator `D`는 결과 전에 `null`이며, 80개 primary terminal이 모두 동결된 뒤 양쪽이 authority-qualified `JUDGED`인 pair 중 canonical full-gold set이 다른 입력 수로만 계산한다. 통계 기여는 `NONE`, P0·production·full scan·Pyserini BM25·gold-lite·reranker/NIL A/B는 계속 `NO_GO`다.

## 구현 산출물

- `src/llm_batch/grounding/p0_presented_dual_blind_review_campaign_precommit_v1_contract.py`
  - fixed guideline과 response schema를 canonical bytes로 생성한다.
  - campaign policy·review lease·final attestation singleton pin 3개와 human reviewer pin 3~16개를 exact raw JSONL로 결속한다.
  - key ID·RFC 5480 fingerprint·principal commitment·raw pin은 전역 distinct, 동일 입력의 reviewer·pin·key·fingerprint·principal·declared group은 3-way distinct다.
  - evaluator-private 120-map에는 upstream lineage와 parser projection을 보존하고, reviewer-facing task에는 opaque task ID·payload·fixed guideline/response hash만 남긴다.
  - reviewer task inventory는 private input-major triad 순서를 버리고 opaque ID 순서로 고정한다. 전체 inventory 공개는 금지하고 task별 전달만 정책으로 봉인한다.
  - 기존 signature-math의 `CAMPAIGN_POLICY_PREAUTHORIZATION`으로 precommit payload를 서명 검증하지만 private signer나 파일·네트워크·프로세스 I/O는 제공하지 않는다.
- `src/llm_batch/grounding/p0_presented_dual_blind_review_campaign_precommit_v1_parent_validator.py`
  - producer contract를 import하지 않는다.
  - upstream plan→bridge→batch precommit→parser result→batch receipt→unreviewed inventory→review unit을 독립 parent 경로로 재생한다.
  - actor·assignment·private map·blind task·precommit·signature subject와 child receipt를 별도 strict parser와 exact recomputation으로 검증한다.
  - component manifest SHA를 literal로 고정하고 producer/parent 수용 경계를 bridge `16 MiB`, results `32 MiB`, unreviewed `32 MiB`로 일치시킨다.
- `tests/test_p0_presented_dual_blind_review_campaign_precommit_v1.py`
  - 정상 40×3/120 bundle과 producer/parent replay를 검증한다.
  - cardinality laundering, metadata leak, key/group collision, malformed type, canonical framing, chronology, manifest/receipt/authority 변조를 공격한다.

component manifest SHA-256은 `9b48da05a67eae4db3190c6443cb949462c53a799309a862818693cd9366c302`다.

## 결과 전 고정한 실험 규칙

| 구분 | 고정값 | 현재 실제값 |
| --- | ---: | ---: |
| selected-input ITT denominator | 40 | 0 reviewed / 40 unreviewed |
| planned primary opportunities | 80 | 0 terminal |
| primary-pair input denominator | 40 | terminal coverage `T=0`, both-judged `J=0` |
| maximum reserve capacity | 40 | 0 activated |
| required adjudication denominator `D` | primary 동결 뒤 불일치 수 | `null` |
| planned final judged denominator | 40 | 0 judged |

standby는 양 primary가 모두 external-authority-qualified `JUDGED`이고, 검증·정렬된 canonical full-gold set이 다를 때만 활성화한다. `UNAVAILABLE` 또는 `UNJUDGED` primary를 standby로 대체하지 않으며 pair는 `INCOMPLETE_NO_FINAL_JUDGED_RESULT_PRIMARY_TERMINALS_RETAINED`로 남긴다.

gold-set 비교는 payload SHA, line/character/UTF-8 byte span, evidence, surface, presented definition, relation kind의 identity tuple을 검증한 뒤 lexicographic sort한 canonical array bytes로 한다. 입력 순서는 무시하고 duplicate는 거부하며 empty set은 완전한 `JUDGED` 결과로 허용한다. parser observation은 비교 입력으로 사용할 수 없다.

## 전문가 회의와 채택 수정

### 사전회의

- 검색 전문가는 기존 review-unit이 parser disposition·registry·emitted observation을 포함하므로 reviewer packet 재사용을 기각했다. evaluator-private lineage와 reviewer-facing task를 분리하고 과거 presented result 기여를 `NONE`으로 두라고 권고했다.
- 통계 전문가는 ITT 40, primary 80, pair 40, reserve capacity 40을 분리하고 incomplete pair 대체 금지와 final `40/40` 전 metric 금지를 제안했다.
- MLOps 전문가는 singleton 3개와 reviewer pin의 exact raw 결속, 역할별 signature domain, 3~16 reviewer bound, no signer/I/O, producer-import 없는 parent를 채택했다.

### 1차 사후 반대검토

- input-major blind-task order가 같은 입력의 세 slot 위치를 노출해 opaque-ID order로 변경했다.
- actor ID 전역 distinct와 모든 pin의 공통 caller-presented authority anchor를 강제했다.
- 임의 guideline instruction이 parser·peer·작품/alias/sense/NIL 힌트의 우회 채널이 될 수 있어 5문장 exact fixed template로 바꿨다. `아생갤`은 해석되지 않은 payload 표면으로만 취급한다.
- assignment 수와 분석 분모를 분리하고 `D=null` 및 derivation, terminal null semantics, canonical disagreement profile, result-stage false gate 6개를 precommit/response/receipt/manifest에 고정했다.
- custom self-hash domain이 actor의 `domain` 필드에 덮이던 문제를 `{self_hash_domain,self_hash_material}` wrapper로 수정했다. legacy review-unit hash는 기존 규약 그대로 유지했다.

### 2차 MLOps 반대검토

- malformed `reviewer_id=[]`와 actor/task ID가 raw `TypeError`를 내던 dict lookup을 식별자 검증 뒤로 옮겨 producer/parent 계약 예외로 정규화했다.
- producer/parent의 upstream byte bound를 `16/32/32 MiB`로 명시적으로 일치시키고 manifest에 JSONL line, instruction count/length, text length를 포함한 모든 강제 한도를 기록했다.
- 최종 재감사 판정은 세 축 모두 `ADOPT_COMPONENT_ONLY`; in-scope 잔여 결함은 발견되지 않았다.

## 검증

- focused campaign: `21/21 PASS`.
- review-accounting + signature-math + campaign: `65/65 PASS`.
- 전체 P0: `$env:PYTHONPATH=(Resolve-Path 'src').Path; python -m unittest discover -s tests -p "test_p0_*.py"` → `705/705 PASS` (`51.639s`, 최종 재실행).
- producer·parent·test `py_compile PASS`; scoped `git diff --check PASS`.
- production/runtime external reference `0`; actual packet `CHILD_FILES=13`.
- 중앙 Slang DB 1개와 publication journal 5개는 bytes/SHA `6/6` 불변이다.
- 이 실행은 pure unittest와 read-only hash 감사다. actual grounding run이 아니므로 dashboard와 `--parallel 16` manifest 적용 대상이 아니다.

첫 전체 실행의 3건 실패는 `PYTHONPATH` 누락에 따른 import/subprocess 환경 오선택이었다. `PYTHONPATH=src`를 명시한 정본 재실행은 `705/705 PASS`이며 product regression으로 계산하지 않는다.

## 명시적으로 증명하지 않은 것

- caller-presented pin·anchor·principal/group label의 외부 provision과 사실성
- trusted time, revocation freshness, key epoch, rollback-resistant nonce·lease 소비
- opaque ID의 암호학적 예측 불가능성, mapping 기밀성, reviewer별 단일-task 접근 통제와 실제 blinding
- human judgment·gold span 의미 사실성, 80개 primary result와 disagreement adjudication
- final attestation, actual source/context credit, 품질 metric, P0 exit와 운영 승인

따라서 `whole_inventory_reviewer_release_policy=FORBIDDEN_DISPATCH_ONE_TASK_AT_A_TIME`은 서명된 정책일 뿐 집행 증거가 아니다. reviewer-facing inventory 전체가 공개되면 동일 payload 3개를 서로 연결할 수 있으므로 실제 dispatch successor 전에는 전달하면 안 된다.

## 다음 순서

1. 외부 fixed key store에서 policy·lease·final signer와 reviewer별 distinct key/principal/group을 provision한다.
2. trusted time·revocation·key epoch와 rollback-resistant nonce/lease 소비를 결속한다.
3. 암호학적으로 무작위인 opaque ID와 reviewer별 단일-task ACL/dispatch receipt로 실제 blinding을 증명한다.
4. 80개 primary signed terminal을 모두 동결한다. nonjudged primary는 대체하지 않는다.
5. canonical gold-set 불일치 `D`만 계산해 exact `D`건의 reserve adjudication을 수행한다.
6. final attestation과 final judged `40/40`을 닫은 뒤에만 사람 gold·통계 분모 기여를 검토한다.
7. 나머지 source/frame/runtime/owner gate까지 닫힌 뒤에만 P1 Pyserini BM25·gold-lite와 P2 retrieval/reranker/NIL shadow A/B를 순차 검토한다.
