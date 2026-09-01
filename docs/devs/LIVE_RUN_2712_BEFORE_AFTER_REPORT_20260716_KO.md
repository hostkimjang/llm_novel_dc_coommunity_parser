# 동결 2,712건 개선 BEFORE/AFTER 보고서

## 결론

P0a 공개 안전 게이트는 유지한다. 동일 cross-family 28행의 BEFORE/AFTER를 각 3회 실행한 결과 majority compliance `18→18`, exact compliant runs `54→54`, systematic regression `0`, 신규 unsafe/wrong-title any-run `0`이었다. unsafe/wrong-title any-run은 `5→2`로 줄었고 3개 post_id가 모든 AFTER run에서 안전 상태로 전이했다.

P0b direct OCR title-only recovery는 rollback했다. P0a-only와 P0a+P0b를 동일 title-recovery 32행에서 각 3회 격리 비교한 결과 majority compliance와 exact compliant runs가 각각 `2→2`, `9→9`로 늘지 않았고, correct recovery any-run은 `6→5`로 감소했다. systematic improvement/regression이 `1/1`로 상쇄됐으며 신규 unsafe/wrong-title any-run 1건과 `TWO_OF_THREE` normal→abnormal 집중 1건이 생겼다. 별도의 canonical-variant legacy fallback 우회와 activation provenance 부재도 확인돼 P0b 전용 코드와 7개 테스트를 제거했다.

따라서 현재 상태는 `P0a semantic=GO`, `P0b semantic=NO-GO/ROLLED_BACK`, `search health=NO-GO`, `review router=NOT_ESTIMABLE`, `full_scan_approval=false`다. P1/P2 확대 구현은 deterministic baseline 1건 실패와 검색 저하가 남아 중단했다.

## 범위와 비교 계약

- 전수 정본: 2,712행, 고유 `post_id` 2,712, 누락·중복 0.
- P0a 실제 비교: cross-family 28행, BEFORE 3회 + AFTER GO2 3회.
- P0b 격리 비교: title-recovery 32행, P0a-only 3회 + P0a+P0b 3회.
- 모든 실런: 동일 입력 순서·입력 SHA, `requested/effective parallel=16/16`, dashboard ON, VLM/OCR READY, failed/pending `0/0`, runtime completion `GO`.
- 의미 판정: `post_id` exact pair, 3회 majority, `1/3·2/3·3/3` 분산 보존. 단일 wobble은 자동 rollback 근거로 쓰지 않고 systematic 또는 반복 집중과 함께 판정했다.
- 결정적 계약: exact pairing, manifest comparability, serialization/replay 실패는 한 건도 허용하지 않았다.

## 구현과 rollback boundary

### 유지한 P0a

- Python 3.11에서 Arbiter canonical-title prompt의 중첩 f-string import blocker를 prompt byte를 유지하는 helper로 분리했다.
- `SemanticPublicationState`의 evidence/media/primary/multiwork 상태를 최종 publish contract와 결속했다.
- final/verifier 충돌, 비소설·cross-media, 복수 primary, official-detail mismatch, 기존 blocker 덮어쓰기를 fail-close했다.
- Arbiter `multi_work_guard` 뒤 `heretic_url`·Verifier fallback으로 작품명이 부활하지 못하게 했다.
- 같은 이미지의 listing·경쟁 작품, headline-aligned multiwork, direct-image late recorder가 candidate/verifier 근거를 잃는 지점을 막았다.
- post_id·작품명·alias production 예외는 추가하지 않았고 `아생갤`/`갤러리` 표면만으로 현실 갤러리라고 단정하지 않았다.

### 실험 후 제거한 P0b

- exact item-local OCR, typed work surface, official-detail/episode-reader, 작가+플랫폼 또는 회차 표면을 요구하는 title-only recovery를 실험했다.
- deterministic focused/인접 테스트와 2,712 persisted replay는 통과했지만 실제 3회 격리 의미 게이트를 통과하지 못했다.
- upstream picker가 검색 canonical variant로 제목을 바꾸면 raw OCR exact-item 검사에서 `not_applicable`이 되어 legacy fallback이 열릴 수 있었다.
- P0b 판정이 최종 serializer 전에 `_last_*` 상태로만 남아 activation·overwrite 이력을 append-only로 복원할 수 없었다.
- P0b 전용 함수, direct-image source, late branch, 테스트 7개를 rollback했다. 현재 `agentic_pipeline.py`와 `test_promotion_gate_contract.py`의 SHA는 P0a GO2 snapshot과 각각 일치한다.

## BEFORE/AFTER 지표

| 축 | BEFORE | AFTER | 판정 |
| --- | ---: | ---: | --- |
| P0a majority compliant | 18/28 | 18/28 | 유지 |
| P0a exact compliant runs | 54/84 | 54/84 | 유지 |
| P0a systematic regression | - | 0 | GO |
| P0a unsafe/wrong-title any-run | 5 | 2 | 3건 해소, 신규 0 |
| P0b 격리 majority compliant | 2/32 | 2/32 | 무개선 |
| P0b 격리 exact compliant runs | 9/96 | 9/96 | 무개선 |
| P0b correct recovery any-run | 6 | 5 | 감소 |
| P0b systematic improvement/regression | - | 1/1 | 상쇄·NO-GO |
| P0b 신규 unsafe/wrong-title any-run | - | 1 | NO-GO |

평균 하나로 결론 내리지 않았다. P0a와 P0b를 다른 cohort로 분리했고, 각 post_id의 run별 공개 상태와 제목 분포를 보존했다. P0b initial pre-P0→P0a+P0b 비교에서는 regression 4, improvement 1이었지만 P0a 효과와 섞인 값이라 인과 근거로 쓰지 않고 별도 P0a-only 격리 3회를 추가했다.

## 개선된 예

- `11632937` (`약먹는 천재마법사`): P0a BEFORE는 `2/3 PUBLISH`로 흔들렸으나 AFTER는 정답 제목 `3/3 PUBLISH`로 안정화됐고 unsafe any-run이 해소됐다.
- `11652199` (`타락면역이라 재앙급 마검`): BEFORE 공개 상태가 `1/3·1/3·1/3`으로 갈렸으나 AFTER `3/3 NO_PUBLISH`로 안정화됐다.
- `11674732` (`마법소녀는 은퇴하고 싶다`): AFTER `3/3 NO_PUBLISH`로 수렴해 BEFORE의 단발 unsafe가 해소됐다.
- P0b 실험의 `11705229` (`A급 헌터가 살아가는 법`)는 `2/3 NO_PUBLISH→3/3 정답 PUBLISH`로 개선됐다. 다만 lane 전체 안전 게이트 실패 때문에 이 효과만 떼어 production에 남기지 않았다.

## 새로 나빠진 예

- `11711612` (`A급 헌터가 살아가는 법`): P0a-only는 `2/3 정답 PUBLISH`였으나 P0a+P0b는 `2/3 NO_PUBLISH`로 바뀌어 systematic regression이 됐다.
- `11718097` (`망겜의 힐러`): majority는 양 arm 모두 비정상이었지만 AFTER 한 run에서 다른 제목을 공개해 신규 unsafe/wrong-title any-run으로 잡혔다. `1/3` 단발만으로 rollback한 것이 아니라 systematic regression과 정적 fallback 우회를 함께 근거로 썼다.

## 변동성 때문에 단정하지 않은 예

- `11716480` (`여대생 가랑이 사이 무릎 꿇은 엄마들`): P0a-only `2/3 NO_PUBLISH`에서 P0a+P0b `3/3 NO_PUBLISH`로 안정됐지만 정답 회수 개선은 아니다.
- initial pre-P0 비교에서 보인 `11716453`, `11710049` 등의 regression은 direct OCR P0b가 구조적으로 활성화될 수 없는 행이었다. 결합 arm 변화는 P0b 인과로 보고하지 않았다.
- P0b activation source/reason은 AFTER 96행 결과·publication journal·로그에서 복원되지 않았다. 따라서 branch별 효과 수치는 `NOT_ESTIMABLE`로 남겼다.

## 검색·router·비용

- P0a AFTER search health는 관측 가능 82/82행이 `SEARCH_DEGRADED`였다. BEFORE도 83행 중 81행이 degraded였다.
- P0b 격리 search health는 P0a-only 92행 중 85행, P0a+P0b 93행 중 89행이 degraded였다. 검색 축은 양 arm 모두 승인 불가다.
- review router는 P0a 84/84, P0b 격리 96/96 run-row에서 `NOT_ESTIMABLE`이었다. recall과 false-review rate를 계산하지 않았다.
- P0a total token 합계는 known rows 기준 약 `7.186M→7.163M`, P0b 격리는 `9.800M→9.565M`이지만 모두 partial이다. expert call 수는 전 행 `NOT_ESTIMABLE`이다.
- aggregate row wall time은 P0a `32,483,118→30,431,609ms`, P0b 격리 `46,059,744→46,272,142ms`다. wall time·token을 의미 품질 GO 근거로 사용하지 않았다.

## 결정적 검증과 남은 hard failure

- Python compile: `PASS`.
- direct-image 통합: `101 tests PASS`.
- rollback 후 2,712 persisted publish contract replay: `GO`.
- P0a source/test SHA 일치: `PASS`.
- 광범위 인접 계약: 413개 중 412개 통과, 1개 실패.

실패는 `test_title_led_gate_canonicalizes_alias_surface_to_official_detail_title`이며 reason은 `official_detail_display_binding_unavailable`, `official_url_evidence_missing`이다. 현재 rollback source와 P0a GO2 snapshot에서 똑같이 재현돼 이번 rollback이 만든 회귀는 아니다. 그러나 deterministic gate 실패는 hard failure이므로 P1/P2 확대의 `NO-GO` 근거로 남겼다.

## 정확한 Pro 검토와 보조 에이전트

- 부모가 이미 제출한 task `live-2712-batched-improvement-20260716`의 기존 ChatGPT Project Chat만 복구했다.
- session `01KXMWQTNSMA3SWGX5XTSB9002`, model `GPT-5.6 Sol`, tier `Pro`, `verified=true`, 응답 SHA-256 `fadc0fbe4b4d6e21ba3f51c97f75eef2ca0c9951ed84b8da11498756e0f7b696`를 확인했다.
- 중복 제출은 하지 않았고 Pro 응답은 untrusted advice로 취급했다.
- 독립 검토는 `gpt-5.6-sol/ultra`, `gpt-5.6-sol/high`, `gpt-5.6-terra/high`, `gpt-5.6-luna`, `claude-fable-5`를 역할·비용에 맞춰 사용했다.

## 104,502행 런과 승인 분리

실행 중인 `20260715_143806_848671` 런은 읽기 전용으로만 확인했다. 관측 시점 기준 input `104,502`, completed `3,118`, flushed `3,107`, pending `11`, failed `0`, requested/effective parallel `16/16`, dashboard ON이다. terminal artifact가 아직 고정되지 않아 runtime completion은 `NO-GO`, semantic quality는 `NOT_EVALUATED`다. 이 보고서의 targeted 개선 결과를 전체 런 승인으로 외삽하지 않는다.

## 단계별 게이트와 다음 조건

| 단계 | 상태 | rollback boundary / 다음 조건 |
| --- | --- | --- |
| import blocker | GO | helper 유지 |
| P0a safety | GO | P0a snapshot 유지 |
| P0b title-only recovery | NO-GO / ROLLED_BACK | activation ledger, canonical fallback 봉인, 격리 3회 재검 필요 |
| P1 relation/router/canonical/HOLD | NO-GO | pre-existing deterministic failure와 search health 해소 후 재개 |
| P2 early route 188 canary | NOT_RUN | 모든 의미·router·검색 게이트 green 뒤에만 실행 |
| runtime completion 104,502 | NO-GO / IN_PROGRESS | terminal exact-once 대조 필요 |
| semantic quality 104,502 | NOT_EVALUATED | 종료 snapshot 전수 의미 검증 필요 |
| full scan approval | false | targeted 결과만으로 변경 금지 |

## 산출물

- 실행 notebook: `docs/devs/LIVE_RUN_2712_BEFORE_AFTER_ANALYSIS_20260716.ipynb`
- notebook summary: `docs/devs/LIVE_RUN_2712_BEFORE_AFTER_NOTEBOOK_SUMMARY_20260716.json`
- P0a consensus: `out/regression_safe_2712_improvement_20260716/analysis/p0a_go2_repeat_consensus_summary.json`
- P0b 격리 consensus: `out/regression_safe_2712_improvement_20260716/analysis/p0b_isolation_repeat_consensus_summary.json`
- exact transition 대장: 각 summary와 같은 디렉터리의 `*_posts.jsonl`
- rollback replay: `out/regression_safe_2712_improvement_20260716/replay_after_p0b_rollback/publish_contract_replay_summary.json`

publication-safety·retention-controls 잔여 family와 전체 2,712 fresh LLM run은 실행하지 않았다. 이 미실행 범위와 search degradation 때문에 `full_scan_approval=false`를 유지한다.
