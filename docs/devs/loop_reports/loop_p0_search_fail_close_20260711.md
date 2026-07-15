# Loop P0 - typed 검색 fail-close 테스트구동 개선 (2026-07-11)

## 무엇을

연구 보고서 `LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md` 1단계(필수 검색 미복구 시 공개 금지)를
개선 전/후 측정이 있는 테스트구동 루프로 구현했다. 게이트 opt-in 단계이며 라이브 판정/런은 비침습이다.

## 한계(개선 전)

검색 실패가 per-row 공개 게이트에 typed 입력으로 배선되지 않아, 상류 단계가 `search_evidence_missing`
이유코드를 남겼는지에 의존했다. 코드가 누락되면 필수 검색이 미복구/하드블록이어도 공개 제목이 promote됐다
(Loop643: 검색 하드블록 5, 미복구 unsafe publish 1).

## 개선

- `src/llm_batch/promotion_gate.py`: typed `RetrievalState`(required/attempted/recovered/hard_blocked) 추가.
- `GroundingState.retrieval` optional 필드 추가(기본 None). `_state_reason_codes`에서
  `required and not recovered` 또는 `hard_blocked`이면 `search_evidence_missing`/`search_blind_condition`을
  파생 → 기존 `CONTRACT_BLOCKING_REASON_CODES` 경로로 `candidate_only` fail-close.
- 기본값(no-op)일 때 dict/fingerprint에서 제외해 `promotion_contract_v2` 완전 호환.

## 측정(개선 전 → 개선 후)

| 지표 | before | after |
| --- | ---: | ---: |
| unsafe publish (필수검색 미복구/하드블록 공개) | 5 | 0 |
| correct publish (정상 공개 보존) | 2 | 2 |
| lost correct publish | 0 | 0 |
| fingerprint 안정(none==default) | - | true |
| fingerprint(populated!=none) | - | true |

하네스: `tools/search_fail_close_probe.py` (frozen 7행). 산출물 JSON:
`docs/devs/loop_reports/search_fail_close_probe_20260711.json`, `PROBE_RESULT=PASS`.

## 회귀 증명

- `tests.test_retrieval_state_fail_close` -> PASS / 8
- `tests.test_promotion_gate_contract` -> PASS / 104
- `tests.test_build_search_recovery_composite_gate tests.test_candidate_audit tests.test_publication_contract_convergence_audit` -> PASS / 156

## 게이트 상태

- P0 typed 검색 fail-close `GO(gate-only)`
- 라이브 파이프라인 배선(`GroundingState.retrieval` 채우기) `NOT_WIRED` (별도 승인)
- `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`

## 다음

`GOAL_PIPELINE_IMPROVEMENT_TESTDRIVEN_20260711.md`의 P1(CandidateSet + NIL 동시 비교)로 이어진다.
