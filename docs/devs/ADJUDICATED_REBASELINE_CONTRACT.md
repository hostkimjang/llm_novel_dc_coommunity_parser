# Adjudicated Re-baseline Contract

## 목적

Loop620/Loop621 계열 full375 결과의 raw diff는 2026-06-26 bootstrap baseline 대비 변화이므로, 정당한 FP 제거와 의도된 recall/wrong-work 복구가 모두 판결된 뒤에도 raw가 0이 될 필요가 없다. 전 행 판결이 끝나면 판결된 결과를 새 baseline으로 재동결해 이후 collateral을 "옛 버그 대비 변화"가 아니라 "올바른 행동 대비 drift"로 측정한다.

## Re-baseline 허용 조건

- `true triage 57` 전 행이 `ACCEPT`, `REPROCESS`, `HOLD`, `expected_fp_removal_exempt`, `fixed` 등 명시 decision으로 닫혀야 한다.
- intended recovery blind/title correctness 판정이 전 행 끝나야 한다. 제목 정답성 미판정 행은 re-baseline 대상에 넣지 않는다.
- current search non-ok hard blocker가 `0`이어야 한다. `SEARCH_DEGRADED`, unrecovered degraded, required-search/publication 행의 `MISSING search_health`가 남은 결과는 re-baseline source가 아니다. 검색을 쓰지 않고 공개 제목도 없는 null/FP 제거 관측은 hard blocker가 아니라 별도 observation으로 회계한다.
- publication contract가 `GO`여야 한다.
- source/baseline/after missing, duplicate post_id, runtime count mismatch가 없어야 한다.
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false` 상태는 re-baseline 준비 중 계속 유지한다.

## 재동결 산출물

- `adjudicated_baseline_result`: 판결 반영 후 375행 결과.
- `adjudication_ledger`: 각 post_id의 decision, 근거 파일, exemption/fix 이유, reviewer/source.
- `adjusted_baseline_manifest`: source run id, projection id, commit, row count, search/publication gate, ledger hash.
- `historical_raw_compare`: 2026-06-26 baseline 대비 raw diff. 참고용이며 완료 blocker가 아니다.

## 이후 Collateral 판정

- 완료 gate와 매 run blocker는 `adjusted_drift` 기준으로 판단한다.
- `raw_vs_20260626`은 역사적 이동량과 회계 설명용으로만 남긴다. 6/26 baseline 대비 raw는 정당 제거/복구 때문에 영구히 0이 아닐 수 있다.
- re-baseline 이후 새 run에서 `adjusted_drift > 0`, unreviewed adjusted row, search hard blocker, publication contract violation이 나오면 `NO-GO`다.
- re-baseline 이전에는 raw를 approval blocker처럼 쓰지 말고, raw 행을 expected FP removal, intended recovery, search hold, true triage로 분해한 adjusted 회계로만 다룬다.

## 완료 Gate 문구

완료 기준은 `full375 collateral GO + full_scan 경로 검증`이지만, collateral GO의 수치는 re-baseline 전후 모두 adjusted 기준이다. Raw count는 2026-06-26 bootstrap 대비 참고 수치이며, full_scan approval을 여닫는 기준이 아니다.
