# 2,712행 개선 아키텍처 전문가 회의 보고서 검증

## 전체 판정: 제한사항과 함께 공유 가능

보고서의 핵심 수치·인과 한계·아키텍처 판정은 정본 산출물과 일치한다. canonical Data Analytics artifact validation과 portable packaging은 통과했다. 다만 설치된 Chromium headless-shell이 없어 최종 HTML 브라우저 상호작용 QA는 `structural_only`이며, 정확한 GPT-5.6 Sol + Pro의 과거 답변은 복구했지만 현재 task의 새 답변은 1회 제출 뒤 transport/recovery 문제로 확보하지 못했다. 이 두 제한을 숨기지 않는 조건으로 공유 가능하다.

## 질문·범위·정본

- 질문: 기존 정상 정답을 최대한 보존하면서 남은 의미 오류를 개선할 다음 아키텍처와 연구 순서는 무엇인가.
- 정량 정본:
  - `docs/devs/LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_VALIDATION_20260718_KO.md`
  - `out/regression_safe_2712_remaining_improvements_20260718/release_candidate_grouped_ab_v1/grouped_analysis/report.json`
  - `out/regression_safe_2712_remaining_improvements_20260718/semantic_review_router_frozen2712_replay/summary.json`
  - `out/regression_safe_2712_remaining_improvements_20260718/semantic_recovery_plan_frozen2712_replay/summary.json`
- 구조 정본: `docs/ARCHITECTURE.md`, `docs/devs/SOURCE_LAYOUT_KO.md`, `expert_main.py`, `src/llm_batch/ledger/publication_commit.py`, `src/llm_batch/ledger/recovery_activation.py`, `src/llm_batch/measurement/*`, `src/llm_batch/promotion_gate.py`.
- 전문가 의견 정본: `docs/devs/ARCHITECTURE_IMPROVEMENT_EXPERT_COUNCIL_MINUTES_20260719_KO.md`.
- 시간 기준: 2026-07-19 KST. 실행 중 104,502-input run은 읽기 전용으로만 취급했다.

## 방법론 검토

- 2,712 deterministic replay, 2,712 router/P1 offline replay, 32행×2 arm×3 repeats를 서로 다른 증거 등급으로 분리했다.
- grouped AFTER가 실제 recovery intervention arm이 아니라 `FRESH SHADOW-AFTER`임을 본문 앞부분과 제한 표에 표시했다.
- cohort가 중첩되므로 routed/hold 건수를 합산하지 않았다.
- deterministic 비간섭은 단 한 번의 drift도 hard failure로, stochastic 품질은 majority·any-run·recurrent·variance를 분리했다.
- calls/tokens/wall은 measurement `4/6 GO` 때문에 `NOT_ESTIMABLE`로 유지했다. 부분 관측치를 비용 개선 결론에 사용하지 않았다.
- 모듈 contract PASS와 system semantic effectiveness GO를 분리했다.

## 계산 spot-check

- exact pairing: grouped `row_count=32`, `repeat_count=3`, status `EXACT`; 본문 `32×2×3`과 일치.
- majority compliance: source `17→18`; 보고서와 일치.
- correct-title majority: source `0/11→1/11`; 보고서와 일치.
- unsafe any-run: source `2→3`, majority `0→0`; 보고서가 개선으로 과장하지 않음.
- WRONG_WORK unrecovered: source `3/3→3/3`; 보고서와 일치.
- router high-risk union: `462/872=52.98%`, 표시 `53.0%` 적정.
- router PASS false-review: `42/230=18.26%`, 표시 `18.3%` 적정.
- router safe no-title false-review: `187/1,580=11.84%`, 표시 `11.8%` 적정.
- router ultra-safe false-review: `3/188=1.60%`, 표시 `1.6%` 적정.
- search AFTER 분해: `51 SEARCH_DEGRADED + 15 NOT_APPLICABLE + 30 ok = 96`, UNKNOWN `0`; 보고서와 일치.
- partial cost: expert calls `932→883`, total tokens `8,353,838→8,450,423`, wall `3,645.8s→3,467.5s`; source status가 `NOT_ESTIMABLE`이며 보고서도 같은 caveat를 유지.
- public noninterference: 기존 validation의 decision/stable/projection drift `0/0/0`, `public_apply=true 0`을 그대로 사용.

## 발견한 문제와 영향

1. [High] Pro 새 답변 미확보
   - exact GPT-5.6 Sol + Pro preflight는 통과했다.
   - 기존 review lane의 `remaining-improvements-measurement-20260718` 기록 세션은 최종 복구됐고 exact model evidence와 과거 2,590행 답변을 확인했다.
   - 새 `architecture-improvement-council-20260719` prompt와 selected bundle은 정확히 한 번 제출했다. `fetch failed` 뒤 lane을 `recovery_required`로 보존했고 같은 prompt를 재전송하지 않았다.
   - 기록 session 복구는 CDP/headless/provider status 문제로 완료되지 않았다. 보고서는 과거 Pro 의견 중 현행 로컬 근거와 일치하는 축 분리·full-scope 과장 금지만 역사적 보조 의견으로 표시하고, 현재 task 의견으로 계수하지 않았다.
2. [Medium] HTML verification이 `structural_only`
   - canonical validation/package는 passed.
   - installed Chromium headless-shell 부재로 enhanced reader의 desktop/narrow viewport, source dialog, interaction은 검증되지 않았다.
   - semantic fallback과 exact embedded payload는 검증됐으며 HTML은 self-contained다.
3. [Medium] `docs/ARCHITECTURE.md` 최신성
   - 2026-07-18에 추가된 fresh observation/router/P1/recovery sidecar 층이 정본 문서에 충분히 통합되지 않았다.
   - 보고서는 현 소스를 우선해 구조를 재구성했고, 문서 갱신을 후속 작업으로 남겼다.
4. [Low] source query 표현
   - portable artifact의 source UI를 위해 기존 20260718 artifact와 동일한 local snapshot query `SELECT * FROM source_rows`를 사용했다.
   - 실제 정본 identity는 각 source의 relative file path와 `tables_used`에 보존했다. 외부 warehouse 실행이나 인과 분석 SQL로 해석하면 안 된다.

## 시각화 검토

- chart는 1개만 사용했다. `review-router cohort 비율`은 9개 cohort의 exact numerator/denominator를 함께 제공한다.
- 위험군 recall과 정상군 false-review는 좋은 방향이 반대임을 인접 설명·kind field·subtitle에 명시했다.
- cohort 중첩 때문에 합산 금지를 표시했다.
- canonical artifact는 chart 1, metric cards 4, tables 8, blocks 25를 검증했다.
- browser QA가 불가능해 실제 SVG·label collision·source dialog는 미검증이다. semantic fallback 표는 모든 9개 행을 읽을 수 있다.

## 결론·권고 검토

- `PublicationFinalizer + ObservationEnvelope + simulator` 권고는 현재 코드 결합과 non-writer 경계를 바탕으로 한 설계 판단이며, 이미 효과가 입증된 사실로 쓰지 않았다.
- P0 동작 불변 추출 → P1 simulated intervention → P2 188 canary 순서는 현재 gate 상태와 일치한다.
- `full_scan_approval=false`를 유지하고 runtime/search/semantic/full scan을 분리했다.
- title/post/alias hardcode나 `아생갤`/`갤러리` 표면 추론을 권고하지 않았다.

## 필수 caveat

- 현재 의미 개선 수치는 causal effect가 아니다.
- measurement·search·router·semantic activation은 NO-GO다.
- Pro의 현재 task 새 답변은 검증되지 않아 아키텍처 대안 합의에 포함되지 않았다. 복구한 과거 2,590 답변은 범위를 명시한 보조 의견이다.
- HTML은 `structural_only` QA다.

## 산출물

- primary report: `docs/devs/ARCHITECTURE_IMPROVEMENT_EXPERT_COUNCIL_REPORT_20260719_KO.html`
- canonical artifact: `docs/devs/ARCHITECTURE_IMPROVEMENT_EXPERT_COUNCIL_ARTIFACT_20260719.json`
- expert minutes: `docs/devs/ARCHITECTURE_IMPROVEMENT_EXPERT_COUNCIL_MINUTES_20260719_KO.md`
- validation: 이 문서
