# 동결 2,712행 남은 개선 BEFORE/SHADOW-AFTER 검산

## 판정

- 산출물 무결성: `GO`
- 공개 비간섭: `GO`
- grouped runtime/comparability: `GO`
- grouped call measurement: `NO_GO`
- review-router/search/semantic auto activation: `NO_GO`
- P2 188 early route: `NOT_RUN / NO_GO`
- `full_scan_approval=false`

이번 AFTER는 recovery를 실제 공개 적용한 인과 arm이 아니라 fresh `SHADOW-AFTER`다. 따라서 32행×3회 수치는 의미 변동을 보여주지만 sidecar 인과 효과를 증명하지 않는다.

## 전수 paired 검산

- ledger/router/P1 plan exact `post_id` join: `2,712/2,712`
- 각 입력 duplicate/missing: `0/0`
- router/P1 receipt coverage: `2,712/2,712`
- decision/stable/public projection drift: `0/0/0`
- `public_apply=true`: `0`
- P1 search/network executed calls: `0/0`
- paired JSONL SHA-256: `ab4d5552326b2d95deb8468840c36e08b5b82a6129b7bcea200d10936628a4df`

## 32행×3회 grouped 검산

- 6개 arm runtime/noninterference: `6/6 GO`
- exact pairing: `32 rows × BEFORE/AFTER × 3 repeats`
- requested/effective parallel: 전 arm `16/16`
- dashboard: 전 arm ON
- measurement: `4/6 GO`; repeat 1 BEFORE와 repeat 2 AFTER에서 각 1행 unlinked/estimated
- majority compliance: `17/32 → 18/32`
- correct-title majority: `0/11 → 1/11`
- FP majority: `0/3 → 0/3`
- HOLD integrity majority: `5/5 → 5/5`
- PASS retention majority: `1/2 → 1/2`
- unsafe any-run: `2 → 3`, majority는 양 arm `0`
- WRONG_WORK unrecovered majority: `3/3 → 3/3`
- descriptive normal→abnormal: `0`
- new recurrent unsafe/wrong-title: `0/0`
- variable posts: `4 → 5`

한 건의 majority 개선(`11716480`)은 관측했지만 양 arm 모두 variance가 있고, `11718099`와 `11716479`의 AFTER 단발 unsafe, `11718097`의 mixed correct/wrong 결과, PASS `11718120`의 1/3 회복을 함께 보존한다. 자동 활성화는 하지 않는다.

## Router·P1·검색

- grouped router receipt: `192/192`, UNKNOWN `0`
- AFTER high-risk recall: `49/66 = 74.2%`
- AFTER normal-control false-review: `6/30 = 20.0%`
- 2,712 replay high-risk recall: `462/872 = 53.0%`
- 2,712 replay PASS false-review: `42/230 = 18.3%`
- P1 grouped plan receipt: `192/192`, `public_apply=true 0`, executed search/network `0/0`
- P1 2,712 plan: `HOLD 883`, `NOT_APPLICABLE 1,829`; PASS HOLD `117/230`
- grouped AFTER search: `SEARCH_DEGRADED 51/96`, `NOT_APPLICABLE 15/96`, `UNKNOWN 0`

## Data Analytics 산출물 검증

- canonical artifact validation: `passed`
- portable HTML package: `passed`
- structural verification: `passed`에 해당하는 `structural_only`
- browser/source interaction QA: `not_verified`
- 원인: packaged Chromium headless-shell 미설치. 일반 `/usr/bin/google-chrome`은 verifier의 chart-extraction 환경과 달라 `browser_environment_mismatch`로 fail-close했다.
- HTML은 self-contained payload/runtime marker를 포함하고 외부 런타임 없이 fallback을 렌더한다.

산출물:

- `LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_REPORT_20260718_KO.html`
- `LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_ARTIFACT_20260718.json`
- `LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_ANALYSIS_20260718.ipynb`
- `LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_PAIRED_20260718.jsonl`
- `LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_DELIVERY_RECEIPT_20260718.json`

## 운영 경계

- P2 early route는 실행하지 않았다.
- automatic recovery publish, deploy, commit, push, central slang promotion을 수행하지 않았다.
- 실행 중인 104,502-input run `20260715_143806_848671`은 읽기 전용으로 유지했다.
- 정확한 GPT-5.6 Sol + Pro lane은 `recovery_required`에서 중복 제출하지 않았고 새 검증 답변을 로컬 근거로 사용하지 않았다.
