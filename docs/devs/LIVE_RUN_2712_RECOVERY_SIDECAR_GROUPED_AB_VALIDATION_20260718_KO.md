# Recovery Sidecar 실제 묶음 분석 검산

## 판정

- 데이터 pairing·receipt·실제 WAL 비간섭: `GO`
- 보고서 수치 재현: `GO`
- Data Analytics artifact validation: `ok=true`
- Data Analytics artifact render: `ok=true`
- semantic auto activation: `NO-GO`
- P1/P2·production enable: `NOT_OPEN / false`
- full scan: `full_scan_approval=false`

## 검산 범위

`최종 승인 감사 (gpt-5.6-sol/ultra)`가 다음 정본을 읽기 전용으로 재검산했다.

- 6개 arm manifest/checkpoint와 source owner WAL
- `grouped_analysis/report.json`, `transitions.jsonl`, `run_summary.json`
- 동결 2,712 adjudication ledger
- 동결 2,712 recovery reconciliation summary
- grouped owner 32행 offline recovery summary
- `tools/analyze_recovery_sidecar_grouped_ab.py`

## 독립 재검산 결과

| 항목 | 결과 |
| --- | ---: |
| exact observation rows | `192/192` |
| unique post_id per arm | `32/32` |
| receipt/source coordinate mismatch | `0` |
| public_apply=true | `0` |
| actual WAL events | `32` |
| actual/manifest WAL SHA | `fb336f…c84d`, 일치 |
| sealed / linked / aborted·open attempts | `186 / 180 / 6` |
| runtime/noninterference | `6/6 GO` |
| call measurement | `6/6 NO-GO` |

Source-relative 반복 회귀 post는 `11718097`, `11716480` 두 개로 재현됐다. 신규 unsafe/wrong-title majority는 BEFORE의 `11716480` 한 개, AFTER는 0개다. AFTER sidecar는 `SKIPPED_FRESH_MEASUREMENT`라 이 차이를 인과 개선으로 판정하지 않았다.

## 지표 spot-check

- FN 11행: correct recovery majority `0/11` 양 arm, any-run은 `11718097` 1회뿐이다.
- PASS 2행: majority retention BEFORE `0/2`, AFTER `1/2`다.
- FP 3행: 양 arm publish `0/9`다.
- HOLD 5행: 양 arm `15/15` 보존이다.
- CORRECT가 필요한 WRONG_WORK 3행: 양 arm 전 `9/9` 미회복이다.
- frozen majority compliance: BEFORE `16/32`, AFTER `17/32`다.
- search: 양 arm degraded/unknown/ok `61/16/19`, router `96/96 UNKNOWN`이다.
- calls BEFORE/AFTER `897/912`, total tokens `7,834,692/8,601,017`, run wall `3,519.2/4,513.6s`는 `observational_partial`이다.

## 감사 지적과 반영

1. source-relative 악화만 보던 gate에 `RECOVERY_EFFECT_NOT_DEMONSTRATED`, `PASS_RETENTION_INCOMPLETE`, `WRONG_WORK_CORRECTION_UNRESOLVED`를 추가했다.
2. `variance`를 실제 변동 post `3/3`과 distinct-projection excess `4/3`으로 분리했다.
3. 각 품질 지표에 eligible denominator와 post_id 목록을 추가했다.
4. manifest anchor뿐 아니라 실제 WAL 파일을 다시 SHA-256/행수 검증한다.
5. measurement gate·ledger summary가 하나라도 없거나 불완전하면 fail-close하고, expert-call 관측치도 6개 manifest가 모두 있을 때만 합산한다.

보강 뒤 analyzer 전용 테스트 `7/7 PASS`, 실제 32행 분석 재실행 `NO-GO`가 동일하게 재현됐다.

최종 관련 회귀 묶음은 `256 tests PASS`다. Python 3.11 compileall과 Python 3.12 핵심 py_compile도 통과했다. 새 동결 2,712 persisted replay는 `GO`이며 public projection/fingerprint/reason mismatch와 normal→abnormal contract regression이 모두 `0`이다. 사용자의 선행 `expert_main.py` 바이트를 보존해 현재 release fingerprint는 실제 6-arm의 `9346b0…0265b`와 exact 일치한다. `git diff --check`는 그 선행 모델-default 줄의 trailing whitespace 1건을 그대로 보고하므로 PASS로 승격하지 않았다.

최종 재검증 중 같은 파일을 `llm_batch...`와 `src.llm_batch...`로 중복 로드하던 shadow observation 테스트 fixture의 클래스 identity 불일치를 확인했다. 테스트 import만 실제 `expert_main` active module로 통일했으며 production validator·WAL 수용 계약은 넓히지 않았다. 해당 단독 테스트와 전체 256개 묶음은 수정 뒤 모두 PASS다.

## Artifact QA

산출물 [`LIVE_RUN_2712_RECOVERY_SIDECAR_GROUPED_AB_DATA_ANALYTICS_ARTIFACT_20260718.json`](LIVE_RUN_2712_RECOVERY_SIDECAR_GROUPED_AB_DATA_ANALYTICS_ARTIFACT_20260718.json)은 report surface, 7 datasets, 4 source queries로 검증됐다.

- validation: `ok=true`
- render: `ok=true`
- snapshot: `ready`
- reader-facing chart/table/source query 포함

## 최종 해석

append-only review-only 구조와 공개 비간섭은 승인한다. 의미 효과, 자동 selector/publish, P1/P2, full scan은 승인하지 않는다. 2,712 reconciliation의 `GO`는 provenance journal 성공이지 proposal 의미 정확도 승인이 아니다.
