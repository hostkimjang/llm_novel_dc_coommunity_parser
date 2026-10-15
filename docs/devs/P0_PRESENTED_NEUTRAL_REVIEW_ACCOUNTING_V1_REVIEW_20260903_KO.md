# P0 presented neutral review accounting v1 검토

작성일: 2026-09-03 KST
상태: `ADOPT_COMPONENT_ONLY / ACTUAL_HUMAN_REVIEW_NO_GO / METRICS_NOT_ESTIMABLE`

## 결론

presented neutral batch exact-accounting v1의 40개 입력과 미검토 inventory를 입력 단위 review terminal로 닫는 별도 pure component를 채택했다. 각 입력은 사전 봉인된 reviewer assignment 아래 `JUDGED`, `UNAVAILABLE`, `UNJUDGED` 중 정확히 하나로 끝난다. `JUDGED`는 해당 입력의 모든 emitted observation 판정과 caller-presented full gold-span set을 담고, 나머지 두 상태는 gold·TP·FP·FN을 `0`이 아닌 `null`로 보존한다.

이 채택은 제출된 bytes의 구조 회계에만 적용된다. reviewer 신원·독립성·blinding, 시각, 사람 판정, gold 의미·완전성은 외부에서 입증되지 않았다. 따라서 actual human review는 `0/40`, actual source/context credit은 `0/40·0/20`, 모든 품질 metric은 `NOT_ESTIMABLE`, P0 exit·production·full scan은 `NO_GO`다.

세 전문가의 최종 판정은 모두 `ADOPT_COMPONENT_ONLY`였다.

| 관점 | 최종 판정 | 핵심 확인 |
| --- | --- | --- |
| 검색·parser | `ADOPT_COMPONENT_ONLY` | plan부터 unreviewed까지 계보, exact relation projection, 65-span 수용과 5,042-line review-domain 경계 |
| 통계 | `ADOPT_COMPONENT_ONLY` | ITT 40, 6개 분모 exact replay, partial `null`, all-UNAVAILABLE truth boundary |
| 데이터·MLOps | `ADOPT_COMPONENT_ONLY` | 공개 API fail-close, standalone parent, manifest exact, runtime·packet 비간섭 |

## 구현 범위

- `src/llm_batch/grounding/p0_presented_neutral_review_accounting_v1_contract.py`
- `src/llm_batch/grounding/p0_presented_neutral_review_accounting_v1_parent_validator.py`
- `tests/test_p0_presented_neutral_review_accounting_v1.py`

artifact 순서는 다음과 같다.

1. predecessor sampling plan→bridge→batch precommit→40 result→batch receipt→unreviewed inventory
2. pseudonymous reviewer roster
3. 40개 input review unit
4. 입력별 exactly-one assignment
5. guideline hash와 roster/unit/assignment를 묶는 review precommit
6. 40개 physical-order review result
7. review accounting receipt

producer는 caller가 별도로 제출한 sampling-plan raw SHA와 batch-precommit raw SHA를 확인하고 predecessor standalone parent를 다시 실행한다. review precommit을 만들 때도 이 검증을 반복한다. review standalone parent는 `llm_batch`나 producer를 import하지 않고 plan selected set→bridge→batch precommit→results→batch receipt→unreviewed inventory 결속을 독립 재생한다. `{}` plan/precommit, 다른 유효 plan의 candidate 교체, raw/hash/order/lineage swap은 거부된다.

## 입력 terminal과 gold 경계

| 상태 | 의미 | gold·산술 |
| --- | --- | --- |
| `JUDGED` | caller가 full-payload 검토를 완료했다고 제시 | exact list와 TP·FP·FN 정수 |
| `UNAVAILABLE` | payload 또는 검토 조건 때문에 완료 판정을 제시할 수 없음 | 모두 `null` |
| `UNJUDGED` | 검토가 완료되지 않음 | 모두 `null` |

`presented_terminal_review_accounting_exhaustive=true`는 40개가 `JUDGED` 또는 `UNAVAILABLE`로 terminal 처리됐다는 구조적 뜻이다. 이것은 `exhaustive_human_review_verified`가 아니다. 40개가 모두 `UNAVAILABLE`이어도 전자는 true일 수 있지만, `presented_all_full_payload_inputs_judged=false`, judged-subset verified=false, actual human review=0을 유지한다.

gold span은 non-empty whole line, character span, UTF-8 byte span, evidence slice, NFC, payload SHA, exact 문형의 surface/definition projection을 함께 재생한다. definition 최대 길이는 parser와 같은 4,096자다. `아생갤`도 이 raw surface로만 보존하며 작품·sense·alias·NIL·route·publication을 만들지 않는다.

parser의 최대 emitted observation 64개는 full-payload gold 상한이 아니다. review-domain은 strict UTF-8로 해석한 최대 64 Ki character 문서이고, 최소 12-character relation line과 LF를 기준으로 이론상 최대 gold span은 5,041개다. 65개 span은 수용한다. 5,042개 최소 relation line은 65,545 characters이므로 upstream 256 KiB payload 안에 들어오더라도 `JUDGED`로는 거부하며 `UNAVAILABLE` terminal이 필요하다.

## 분모와 metric 경계

receipt와 parent는 결과 합계에서 역산하지 않고 sealed review unit에서 다음 분모를 다시 계산한다.

| 필드 | 규칙 |
| --- | --- |
| `selected_input_itt_denominator` | 항상 40 |
| `contextual_review_denominator` | 40개 unit의 모든 emitted observation 수 |
| `full_payload_review_denominator` | 항상 40 |
| `judged_subset_emitted_observation_denominator` | `JUDGED` 입력의 emitted observation 수 |
| `judged_subset_gold_span_denominator` | `JUDGED` 입력의 caller-presented gold 수 |
| `all_input_emitted_observation_denominator` | 40개 모두 `JUDGED`일 때만 정수, 아니면 `null` |
| `all_input_gold_span_denominator` | 40개 모두 `JUDGED`일 때만 정수, 아니면 `null` |

fixture partial 경계는 `(전체 emitted, judged emitted, TP+FP, gold)=(9,9,9,9)`, all-JUDGED 경계는 `(10,10,10,10)`이다. 각 분모를 `+1` 또는 `null→0`으로 바꾼 뒤 전면 재봉인한 공격은 parent가 모두 거부했다. 이 수치는 계약 테스트용이며 실제 정확도·재현율이 아니다.

고정 정책은 다음과 같다.

```text
metric_status = NOT_ESTIMABLE_PRESENTED_REVIEW_ONLY
descriptive_quality_metrics_allowed = false
inferential_metrics_allowed = false
complete_case_metrics_allowed = false
semantic_metrics_allowed = false
observation_rows_are_sampling_units = false
sampling_unit = SELECTED_INPUT_LINEAGE
```

## 전문가 반대검토에서 닫은 문제

| 문제 | 조치 |
| --- | --- |
| precommit이 plan/predecessor precommit을 raw SHA만 기록 | expected raw pin과 predecessor full replay를 producer에 추가하고 parent에서 계보 독립 재생 |
| surface/definition substring 검사로 뒤집기 허용 | exact relation fullmatch와 capture projection 일치 강제 |
| definition 512자 제한 | parser 계약과 같은 4,096자로 정렬 |
| gold 상한 64로 `INVALID_CAPTURE` payload의 full review 불가 | 별도 64 Ki-char review domain과 5,041 상한, 65 수용, overlong `UNAVAILABLE_REQUIRED` 고정 |
| partial subset의 분모 불명확 | 6개 분모를 receipt·manifest·parent에 추가하고 all-input conditional-null 강제 |
| JUDGED 0인데 gold verified=true | judged-subset 이름으로 한정하고 JUDGED 0이면 false |
| mapping 대신 `None`/`{}`에서 raw `TypeError` | roster·assignment·decision·gold 공개 입구를 custom contract error로 정규화 |
| 큰 정수·deep JSON·oversize artifact 공격 | bounded parser와 exact scalar validation으로 fail-close |

## 검증과 비간섭

| 검증 | 결과 |
| --- | --- |
| focused 신규 회귀 | `25/25 PASS` |
| parser core + predecessor batch + review accounting | `62/62 PASS` |
| 전체 `test_p0_*.py` | `665/665 PASS` |
| producer·parent·test `py_compile` | `PASS` |
| producer/parent manifest | `05ea2cf7301c770b6f3ead9e894df59d447523a1964b85a72bb68f0f1a63ef76` exact |
| 기존 runtime 파일 successor token | `0` |
| 기존 packet inventory | `CHILD_FILES == 13` |
| 중앙 Slang DB 1개 + publication journal 5개 | bytes/SHA `6/6` 불변 |

이번 검증은 pure unittest와 정적 hash 감사다. actual 수집·검증 run이 아니므로 dashboard나 `--parallel 16` runtime을 시작하지 않았다.

## 다음 gate

내부 구조 successor는 완료됐지만 실제 human review는 시작하지 않았다. 다음 단계에는 외부 owner가 reviewer identity·독립성·blinding, guideline, trusted time, signed assignment/precommit/result와 full-payload review 범위를 권위 있게 제공해야 한다. 모든 40개 terminal 중 `UNAVAILABLE/UNJUDGED`가 없어지고 parent가 actual judgment와 gold completeness를 별도 증명하기 전에는 품질 metric을 계산하지 않는다.

그 뒤에도 external enumeration completeness, signed owner precommit, beacon/time/revocation/durable nonce, A-context full frame, registry/capture authority, protocol/worker/sandbox/code identity와 parent-only ledger가 필요하다. 이 gate 전에는 actual 40+20, Pyserini BM25, gold-lite, retrieval/reranker/NIL shadow A/B를 시작하지 않는다.
