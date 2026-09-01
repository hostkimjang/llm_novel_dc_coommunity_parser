# 동결 2,712건 회귀 cohort·bundle 계약

## 결론

동결 전수 판정 ledger와 raw `expert_main` 결과를 `post_id`로 exact join하는 재사용 도구를 추가했다. 등록한 11개 cohort의 수는 `35/339/107/72/36/91/7/64/230/1,580/188`로 정본 보고서와 일치한다. raw 결과의 3,107행 중 ledger에 속한 2,712행만 사용하며, 누락·중복 또는 중재 coverage 불일치가 있으면 산출물을 승인하지 않는다.

- Builder: `tools/build_frozen_2712_cohorts.py`
- Paired comparator: `tools/compare_frozen_2712_pair.py`
- Repeat consensus analyzer: `tools/analyze_frozen_2712_repeat_consensus.py`
- 기본 산출물: `out/frozen_2712_regression_cohorts_20260716/`
- 정본 manifest: `out/frozen_2712_regression_cohorts_20260716/manifest.json`
- 현재 builder 게이트: `GO`
- 실제 AFTER·개선 효과 게이트: `NOT_RUN / REVIEW-LOCKED / full_scan_approval=false`

## Cohort 정의

| 이름 | 술어 요약 | 건수 |
| --- | --- | ---: |
| `published_intervention` | pipeline publish이며 최종 action이 `KEEP` 아님 | 35 |
| `fn_title_missing` | `FN_TITLE_MISSING` | 339 |
| `fn_direct_ocr` | FN이며 explicit OCR title 존재 | 107 |
| `fp_non_novel` | `FP_NONNOVEL` | 72 |
| `wrong_work` | `WRONG_WORK` | 36 |
| `multiwork` | `MULTIWORK_HOLD_CORRECT` | 91 |
| `dashboard_title_mismatch` | `DASHBOARD_TITLE_MISMATCH` | 7 |
| `arbitration` | 교차검토 `REQUIRES_ARBITRATION`이며 중재 verdict에 정확히 1회 존재 | 64 |
| `pass` | `PASS` | 230 |
| `safe_no_title` | `NOISE_CORRECT/CONTEXT_ONLY_CORRECT` + `NOT_APPLICABLE` | 1,580 |
| `ultra_safe_no_title` | safe no-title이며 이미지·OCR·후보·댓글 모두 없음 | 188 |

게시글 ID, 제목, 작품명, 약칭은 선정 코드에 넣지 않는다. exact predicate 문자열, 결과 수, 파일 SHA-256, `post_id` 순서 SHA-256은 manifest에 기록한다. `fn_direct_ocr`는 FN의 부분집합이고 ultra-safe는 safe no-title의 부분집합이다. 다른 cohort도 겹칠 수 있으므로 합산하지 않는다.

## 실행 입력과 bundle

각 `cohorts/*.jsonl`은 해당 cohort 전체의 실제 재실행 입력이다. raw 결과 행에서 `analysis_result`와 `run_meta`만 제거해 BEFORE 판정이 AFTER 입력으로 누출되지 않게 했다. 행 순서는 최종 ledger 순서다.

기본 bundle은 무작위 표본을 만들지 않는다. 각 stratum에서 한 행씩 round-robin으로 선택하고 `post_id` 중복을 제거한 뒤 ledger 순서를 복원한다.

| Bundle | Strata | 기본 cap | 현재 수 |
| --- | --- | ---: | ---: |
| `publication_safety` | 공개 개입·FP·wrong-work·multiwork·mismatch·중재 | 192 | 192 |
| `title_recovery` | direct OCR FN·나머지 FN | 192 | 192 |
| `retention_controls` | PASS·ultra-safe·나머지 safe no-title | 192 | 192 |
| `cross_family` | 위 세 family | 256 | 256 |

모든 실제 검증런의 manifest는 `requested_parallel=16`을 사용하고, 각 입력의 `effective_parallel=min(input_count,16)`을 확인해야 한다. dashboard를 끄지 않는다.

```bash
python3 tools/build_frozen_2712_cohorts.py

# 예: 실제 런은 별도 승인 뒤 dashboard ON으로 수행
python3 expert_main.py \
  out/frozen_2712_regression_cohorts_20260716/bundles/cross_family.jsonl \
  --parallel 16 \
  --vlm on --ocr on --require-vlm-ocr-for-images
```

이 작업에서는 `expert_main.py`를 실행하지 않았다.

## 3회 반복 consensus 분석

반복 실행은 `--parallel 16`, dashboard ON의 동일 입력ㆍ동일 model lineage에서 각 arm을 정확히 3회 수행한 뒤 분석한다. 도구는 각 JSON 배열의 unique `post_id` 집합과 ledger coverage를 exact 검증한다. manifest를 주면 `input_post_count`, `completed/flushed`, `failed/pending=0`, terminal artifact, runtime gate `GO`, requested/effective parallel, dashboard, model, input snapshot hash를 검증한다.

```bash
python3 tools/analyze_frozen_2712_repeat_consensus.py \
  --ledger path/to/frozen_ledger.jsonl \
  --before before_1.json --before before_2.json --before before_3.json \
  --after after_1.json --after after_2.json --after after_3.json \
  --before-manifest before_1_manifest.json --before-manifest before_2_manifest.json --before-manifest before_3_manifest.json \
  --after-manifest after_1_manifest.json --after-manifest after_2_manifest.json --after-manifest after_3_manifest.json \
  --post-jsonl out/repeat_consensus/posts.jsonl \
  --summary-json out/repeat_consensus/summary.json
```

결정적 계약 실패는 산출물 승인 없이 `HARD_FAILURE`다. 의미 평가는 3-run 다수결이며 `1/3`은 wobble, `2/3`과 `3/3`은 consensus 강도로 기록한다. any-run unsafe publish 또는 wrong title은 반드시 표면화한다. 다만 단발 wobble은 반복 집중 또는 systematic regression 근거 없이는 자동 rollback이 아니다.

## 저장된 publish contract 결정적 리플레이

`tools/replay_frozen_2712_publish_contract.py`는 위 정본 ledger와 같은 raw result를 `post_id`로 exact join한 뒤, 각 행에 저장된 authoritative v2 `promotion_gate_state`/`promotion_gate_evidence`/`promotion_decision`을 현재 serializer와 `evaluate_publish_contract`로 다시 계산한다. 네트워크와 `expert_main.py`는 사용하지 않으며, 결과 JSONL과 summary는 호출자가 준 `--output-dir` 아래에만 쓴다.

```bash
python3 tools/replay_frozen_2712_publish_contract.py \
  --output-dir out/frozen_2712_publish_contract_replay_20260716
```

root identity가 v2 schema를 명시한 경우만 우선 사용하고, 없을 때에도 `candidate_ledger`가 `promotion_contract_v2`를 명시한 경우에만 fallback한다. 중복·누락 `post_id`는 즉시 실패한다. 필수 persisted input이 없거나 현재 serializer가 해석할 수 없으면 값을 보완하지 않고 해당 행을 `NOT_ESTIMABLE`로 남긴다.

summary에는 exact coverage, 의미 판정의 verdict/action cohort(집계 전용), 저장/재계산 projection·reason code·fingerprint 비교, 내부 contract invalidity와 내부 normal→abnormal regression을 기록한다. 이는 의미 안전과 다른 축이다. action이 `KEEP/CORRECT`이면 `recommended_title`/`dashboard_title_expected`의 정확한 공개를, `HOLD/REMOVE/NOT_APPLICABLE`이면 미공개를 사후 채점해 저장/재계산 `adjudicated_unsafe_publish`, compliant/noncompliant/`NOT_ESTIMABLE`, compliant→noncompliant semantic regression도 별도 집계한다. 이 채점은 production decision에 입력되지 않는다. 이 리플레이는 **결정적 저장 contract 호환성 검증**이며 semantic LLM effectiveness 측정이 아니다. 과거 행의 `SemanticPublicationState` 부재는 레거시 중립 호환으로 예상되며, reviewer ledger 라벨은 production decision 입력에 절대 주입하지 않는다.

## BEFORE/AFTER exact transition

Comparator는 BEFORE/AFTER JSON 배열의 중복 없는 `post_id` 집합이 정확히 같고 모든 ID가 정본 ledger에 있을 때만 행별 table을 만든다.

```bash
python3 tools/compare_frozen_2712_pair.py \
  --ledger out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl \
  --before <before_result.json> \
  --after <after_result.json> \
  --transition-jsonl <paired_transitions.jsonl> \
  --summary-json <paired_summary.json>
```

행 스키마 `frozen_2712_post_id_exact_transition_v1`은 다음을 보존한다.

- `post_id`, 정본 `review_verdict/dashboard_action/recommended_title/expected_public_title`
- BEFORE/AFTER의 publish 여부·공개 제목·system/identity state
- review router와 search health
- expert/search calls, prompt/completion/total tokens, row wall time
- unsafe publish, correct title recovery, FP, wrong-work, HOLD integrity, PASS retention
- 각 arm의 `adjudication_compliant`: `KEEP/CORRECT`는 정본 expected title을 정확히 공개한 경우만, `HOLD/REMOVE/NOT_APPLICABLE`는 미공개인 경우만 `COMPLIANT`다. 알 수 없는 action이나 expected title 누락은 `NOT_ESTIMABLE`이며 compliant/false로 세지 않는다.
- `normal_to_abnormal_regression`은 adjudication-compliant BEFORE가 AFTER에 noncompliant가 된 semantic 회귀다. 기존 runtime 오류 전이는 `runtime_normal_to_abnormal_regression`으로 별도 보존한다. 두 arm 중 하나라도 compliance를 모르면 semantic 회귀는 `NOT_ESTIMABLE` 관측으로 남긴다.
- review router는 high-risk verdict의 `high_risk_recall`(routed/known routed+not_routed)과 정상 control(`PASS`, `NOISE_CORRECT`, `CONTEXT_ONLY_CORRECT`)의 `normal_control_false_review_rate`(routed/known routed+not_routed)를 낸다. `UNKNOWN` router 상태는 분자·분모에서 제외하고 `unknown_rows`로 명시한다.

요약은 위 의미 지표와 review router coverage/recall/false-review rate의 numerator·denominator·unknown_rows, search status/queries/unrecovered degraded, calls/tokens/wall의 known·unknown coverage를 함께 낸다. 필드가 없는 과거 결과는 0으로 만들지 않고 `PARTIAL` 또는 `NOT_ESTIMABLE`로 남긴다. 결과 게이트 `MEASURED_NOT_AUTOMATICALLY_APPROVED`는 비교표 생성 성공을 뜻하며 자동 운영 승인이 아니다.

## 검증

- `python3 -m py_compile tools/build_frozen_2712_cohorts.py tools/compare_frozen_2712_pair.py tests/test_frozen_2712_cohorts.py`: PASS
- `python3 -m unittest tests.test_frozen_2712_cohorts -v`: `8 tests`, PASS
- 현재 자료 exact join: ledger `2,712/2,712`, raw `3,107/3,107`, missing `0`, raw extra `395`
- 중재 exact coverage: cross-review `221`, required `64`, verdict `64`, missing/extra `0`
- 기본 bundle: `192/192/192/256`, 모두 requested/effective parallel `16/16`

합성 CLI 검증은 결정성, source projection, cap, duplicate/missing raw 차단, 중재 mismatch 차단, paired ID mismatch 차단과 모든 요구 지표를 확인한다. 실제 AFTER 런은 없으므로 개선 효과는 아직 확정하지 않는다.
