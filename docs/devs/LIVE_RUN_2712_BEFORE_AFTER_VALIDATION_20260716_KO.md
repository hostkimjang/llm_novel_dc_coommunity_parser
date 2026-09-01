# 동결 2,712건 개선 BEFORE/AFTER 검산

## 판정

- notebook 실행: `PASS`.
- Data Analytics artifact schema validation: `PASS` (`ok=true`).
- Data Analytics artifact render: `PASS` (`ok=true`).
- P0a semantic: `GO`.
- P0b semantic: `NO-GO / ROLLED_BACK`.
- search health: `NO-GO`.
- review router: `NOT_ESTIMABLE`.
- 104,502 runtime: `NO-GO / IN_PROGRESS`.
- 104,502 semantic quality: `NOT_EVALUATED`.
- `full_scan_approval=false`.

## notebook 검산

`LIVE_RUN_2712_BEFORE_AFTER_ANALYSIS_20260716.ipynb`의 code cell 6개를 top-to-bottom 실행했다. execution count는 `1..6`, output type은 모두 `stream`, error output은 0개다. 다음 assertion을 실행 셀에서 확인했다.

- P0a/P0b pairing `EXACT`, repeat count 3.
- 양 lane manifest comparability `GO`.
- P0a systematic regression 0.
- P0b isolated systematic regression 1.
- rollback 후 2,712 persisted replay `GO`.
- `full_scan_approval=false`.

환경에 Jupyter·nbformat이 없어 Python 표준 라이브러리 실행기로 동일 namespace에서 cell을 순서대로 실행하고 stdout·execution count를 notebook JSON에 기록했다. 실행 중 예외가 발생하면 error output을 기록하고 non-zero로 종료하도록 했다.

## artifact 검산

artifact는 report surface, snapshot status `ready`다. bounded snapshot은 5개 dataset, 총 21행으로 한도 이내다.

| dataset | 행 |
| --- | ---: |
| headline | 1 |
| unsafe_metrics | 4 |
| lane_metrics | 2 |
| transitions | 7 |
| validation | 7 |

manifest는 block 13개, chart 1개, table 3개, manifest source 4개를 갖는다. 첫 block은 manifest title과 같은 H1이고, chart는 `x/y/color` encoding을 사용하며, 모든 table은 `defaultSort`가 있다. source-backed widget에는 실제 SQLite CTE query를 포함했다.

첫 validation은 `full_scan` card가 actual SQL query가 없는 source를 가리켜 fail-closed됐다. card source를 query-backed source로 교정하고 transition/validation/observability source에 재현 SQL을 추가한 뒤 두 번째 validation이 `ok=true`로 통과했다. validation 통과 전에는 render를 호출하지 않았고, 통과한 동일 payload의 render가 `ok=true`였다.

## 수치 교차 검산

P0a:

- majority compliant `18→18`, exact compliant runs `54→54`.
- systematic improvement/regression `0/0`.
- unsafe/wrong-title any-run `5→2`.
- introduced/persistent/resolved `0/2/3`.

P0b 격리:

- majority compliant `2→2`, exact compliant runs `9→9`.
- systematic improvement/regression `1/1`.
- correct recovery any-run `6→5`.
- unsafe/wrong-title any-run `2→2`, introduced/persistent/resolved `1/1/1`.
- normal→abnormal 반복 집중 `TWO_OF_THREE=1`.

P0b initial pre-P0→P0a+P0b 비교의 regression 4, improvement 1은 P0a 효과와 섞여 인과 결론에서 제외했다. 최종 rollback 판정은 P0a-only 3회와 P0a+P0b 3회의 exact 격리 consensus를 사용했다.

## 결정적 검증 교차 확인

- Python compile `PASS`.
- `tests.test_expert_main_comment_metadata` 101개 `PASS`.
- rollback 후 persisted 2,712 replay `GO`.
- `src/llm_batch/agentic_pipeline.py`와 `tests/test_promotion_gate_contract.py`는 P0a GO2 snapshot SHA와 일치.
- 광범위 인접 계약 413개 중 412개 통과, 1개 실패.

인접 실패는 `title_led_alias_official_detail_canonicalization`이며 현재 source와 P0a GO2 snapshot에서 모두 재현됐다. 이번 rollback이 만든 regression은 아니지만 deterministic hard failure이므로 P1/P2를 승인하지 않았다.

## 파일 해시

| 파일 | SHA-256 |
| --- | --- |
| `LIVE_RUN_2712_BEFORE_AFTER_ANALYSIS_20260716.ipynb` | `8b20d768a6b7962259c4e5a485779b14d5e2c50a9fccf9632f793a0a431b0d29` |
| `LIVE_RUN_2712_BEFORE_AFTER_NOTEBOOK_SUMMARY_20260716.json` | `3179bc284b7b41569551c82eb4df9b2f4f0cd01b4718734908f796909c505dd0` |
| `LIVE_RUN_2712_BEFORE_AFTER_REPORT_20260716_KO.md` | `e6f626825d9c8492cf70202f9eaa3dba9aa96b34b4220264bff40dc563f926af` |
| `LIVE_RUN_2712_BEFORE_AFTER_DATA_ANALYTICS_ARTIFACT_20260716.json` | `103dea24b6e84a43c986d24638f5fde5ad96bf3ee7e75e880fa5763b33bc6e55` |
| `p0a_go2_repeat_consensus_summary.json` | `1a85aaab0d6a35c80a2a30ccdaff72788767cb5c68658fc694d196e6d0a3a21b` |
| `p0b_isolation_repeat_consensus_summary.json` | `a1df4175d53643857783c4e1968448fca927b54b0b8ad6fb964b48beaf8facea` |

validation 보고서 자체를 작성한 뒤에는 위 입력 파일을 다시 수정하지 않았다. artifact는 17,869 bytes, notebook은 15,892 bytes, reader-facing 보고서는 10,790 bytes다.

## 미승인 범위

publication-safety·retention-controls 잔여 family, 전체 2,712 fresh LLM run, 104,502 terminal snapshot 전수 의미 검증은 미실행이다. search degraded와 review-router 비관측도 남아 있다. 따라서 targeted P0a 결과를 전체 품질 또는 배포 승인으로 승격하지 않는다.
