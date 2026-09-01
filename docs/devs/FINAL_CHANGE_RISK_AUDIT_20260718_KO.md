# 최종 변경 위험 감사 (2026-07-18)

대상: 작업트리(uncommitted working tree)의 전체 변경 세트. 목적은 변경 위험 판정과 잔여 조치 식별이다. 감사자 실행 설정은 `anthropic/claude-opus-4-8` / `reasoning_effort=medium`이다.

## 종합 판정

**조건부 GO (변경 세트 위험 감사 기준, 자동 활성화·배포 승인이 아님).** 변경은 additive·fail-closed·legacy-호환 중심이며, 변경 영역 대상 테스트가 통과하고 docs/CHECKLIST가 코드와 정합한다. 신규 회귀는 감지되지 않았다. 다만 (1) 사전 존재(pre-existing) deterministic 실패가 남아 있고, (2) `unittest discover -s tests`가 import-time argv 파싱 충돌로 신뢰 불가하며, (3) `git diff --check` trailing whitespace 1건이 있다. 운영 공개 축은 이 변경 범위 밖이며 `full_scan_approval=false`, recovery/자동 publish `NO-GO`가 유지된다.

## 검증 실행 결과 (명령어 + 요약)

- 환경: 시스템 `python`/`python3`(3.12)에는 pytest 미설치. 대상 테스트는 전부 `unittest` 기반이므로 프로젝트 venv `venv/bin/python -m unittest`로 실행.
- 변경 영역 대상 묶음 PASS:
  `venv/bin/python -m unittest -q tests.test_promotion_gate_contract tests.test_semantic_publication_authority_contract tests.test_recovery_activation_ledger tests.test_publication_shadow_observation tests.test_semantic_recovery_plan tests.test_semantic_review_router tests.test_arbiter_canonical_lock_prompt tests.test_arbiter_curated_alias_guard tests.test_decision_tracing_llm tests.test_expert_main_input_loader tests.test_search_recovery_contract tests.test_replay_frozen_2712_publish_contract`
  → **Ran 299 tests, OK**.
- 바이트 컴파일: 변경/신규 py(핵심 6개 + 신규 모듈 4개 + 신규 tools 10개) `py_compile` **COMPILE_OK**.
- 시크릿/PII 스캔: `git diff` 및 신규 measurement/ledger 모듈 대상 정규식 스캔 → **탐지 0건**.
- 전체 `venv/bin/python -m unittest discover -s tests -q`: Ran 1759, `FAILED (failures=20, errors=86, skipped=3)`. **이 수치는 이번 변경의 품질 신호로 그대로 쓸 수 없다**(아래 근거 참조).
  - errors=86 다수: import-time argv 충돌 아티팩트. `discover -s tests`의 `-s`가 `expert_main`의 `--server-type/-s`(choices=`llama`,`vllm`) argparse와 충돌해 `argparse.ArgumentError: invalid choice: 'tests'`로 import 자체가 실패. 동일 모듈을 명시 경로로 부르면 통과(위 299 PASS에 `test_recovery_activation_ledger`, `test_publication_shadow_observation` 등 포함).
  - failures 표본 2개 모듈은 baseline 재현 확인(회귀 아님, 아래).
- 회귀 격리(가장 중요): 변경된 tracked source 6개를 `git stash push`로 잠시 되돌리고 동일 모듈 재실행 후 `git stash pop`으로 복원(비파괴·가역).
  - `tests.test_known_title_abbreviation_support` + `tests.test_title_lead_search_inferred_guard`: 변경본 4 failures, **baseline도 동일 4 failures**(`test_gallery_homage_title_abbreviation_is_preserved_as_candidate`, `test_official_detail_gallery_homage_survives_semantic_no_work_seed`, `test_registry_anchor_only_medium_is_serialized_in_final_output_alias_sources`, `test_title_led_gate_canonicalizes_alias_surface_to_official_detail_title`).
  - `tests.test_build_post_verdict_promotion_gate_contract_plan`(promotion_gate 반경): 변경본 2 failures, **baseline도 동일 2 failures**(`test_c1_recovered_expected_title_becomes_restore_contract_case`, `test_shared_gate_projection_publish_row_becomes_restore_contract_case`).
  → 두 대표 클러스터(총 6건) 모두 변경 이전에도 동일 재현 = **이번 변경이 유발한 회귀 아님**. CHECKLIST도 `title_led_alias_official_detail_canonicalization`를 미완료(`[ ]`) open gate로 명시.
- `git diff --check`: **1건** `expert_main.py:11280` trailing whitespace(사용자 보존 model-default 라인). CHECKLIST에 known dirty로 기록됨.

## 영역별 위험 표

| 파일/영역 | 위험도 | 근거 | 조치 필요 |
| --- | --- | --- | --- |
| `promotion_gate.py` — `SemanticPublicationState` 신규 fail-closed 권위 | Med | empty=legacy no-op, publishable 값만 allow-list, unexpected-field 거부, default는 fingerprint 제외. 신규 `CONTRACT_BLOCKING_REASON_CODES` 다수 추가 → 상류 producer가 필드를 채우기 시작하면 기존 공개행이 차단될 수 있음(설계상 의도, but 활성화 시 영향 큼). 계약 테스트 `test_promotion_gate_contract`(+388줄), `test_semantic_publication_authority_contract` PASS | 상류 producer 활성화 시 별도 canary/영향 측정 후 진행 |
| `arbiter.py` — canonical-lock helper 분리 + null-block guard 확장 | Med | 중첩 f-string 백슬래시 제거로 Python 3.11 import 위험 해소(실질 버그 픽스). strong null-block/URL fallback 억제에 `multi_work_guard`, `curated_alias_missing_contextual_work_anchor` 추가 → null-block 시 URL 부여 억제(정합 강화). `test_arbiter_curated_alias_guard`, `test_arbiter_canonical_lock_prompt` PASS | 없음(테스트 커버) |
| `publication_commit.py` — attempt-local run-meta 키 3종 추가 | Low | 신규 measurement/shadow/router/recovery receipt를 `decision_id` 안정 해시에서 제외. 공개 결정 재현성 계약 불변. replay contract `GO` | 없음 |
| `decision_tracing_llm.py` — `comment_answer_judge`→`VERIFIER` 매핑 | Low | additive role 정규화. `test_decision_tracing_llm` PASS | 없음 |
| `agentic_pipeline.py` — `_derive_semantic_publication_state`, background-listing VLM 감지 확대 | Med | 신규 semantic state 배선 + `작품/소설 목록 + 서로 다른 회차 2개 이상` catalog 격리(의도적으로 좁힘, 단일작 회차목록은 유효 유지). 광범위 정규식 → 오탐 여지 존재하나 대상 테스트 통과 | 대량 라이브에서 오탐율 모니터 |
| 신규 `ledger/recovery_activation.py`(1181줄) | Med | AUDIT_ONLY·`public_apply=false` sidecar, 최종 WAL receipt/result exact 재검증 후에만 append, 0600 HMAC, append-only hash chain, 16-way CAS idempotence, corruption fail-close. fresh measurement에서는 skip. `test_recovery_activation_ledger` PASS. 공개 mutating 아님 | 자동 activation은 `NO-GO` 유지 |
| 신규 `measurement/publication_shadow_observation.py`(275줄) | Low | `FRESH_SEMANTIC_OBSERVATION_REQUIRED` 추가 경로, self-hashed receipt, public WAL write 금지. 기존 strict `FRESH_EXECUTION_REQUIRED` 계약 유지. `test_publication_shadow_observation` PASS | 없음 |
| 신규 `measurement/semantic_recovery_plan.py`(926줄), `semantic_review_router.py`(586줄) + tools | Low | review-only/측정 산출물, 공개 승격 없음. `test_semantic_recovery_plan`, `test_semantic_review_router` PASS | router/measurement gate `NO-GO` 유지 |
| `expert_main.py` — 측정/env/finalization hook(+866줄) | Med | 신규 measurement env·config, fresh execution authoritative reference, recovery hook(post-commit 재검증 뒤·batch learning 전). 대상 테스트 통과, compile OK. 라인 다수라 line-by-line 전수 미검(아래 감사 범위) | trailing whitespace 정리 |
| 사전 존재 실패 — official-detail/restore-contract 계약 | High(기존 부채) | discover FAILs 다수가 이 영역. 대표 6건 baseline 재현 확인 = 회귀 아님. 그러나 deterministic hard failure로 미해결 | open gate로 추적, 이번 커밋과 분리 |
| 테스트 하버스 — `discover -s tests` argv 충돌 | Med | import-time argparse가 `sys.argv`를 파싱해 discover 인자와 충돌, 86 errors 유발. CI 신뢰성 저하 | argv 파싱을 `__main__` 가드/명시 모듈 목록/pytest로 이전 권고 |
| docs/CHECKLIST/README 정합 | Low | CHECKLIST(+189줄), README 목차 1~14 갱신이 코드 변경(canonical-lock, SemanticPublicationState, multi_work_guard, recovery_activation_ledger_v2, shadow observation, tools)과 정합. 게이트 상태(`P0a GO / P0b ROLLED_BACK`, recovery `DETERMINISTIC GO / REVIEW-ONLY / SEMANTIC NO-GO`, `full_scan_approval=false`) 명시 | 없음 |

## 게이트 상태 요약

- 변경 영역 대상 테스트: `299 PASS`.
- 신규 회귀: **0**(대표 클러스터 baseline 격리로 확인).
- 사전 존재 deterministic 실패: official-detail/restore-contract 영역에 존재(미해결, open gate).
- 공개 안전: recovery sidecar `AUDIT_ONLY/public_apply=false`, shadow observation public WAL write 금지, 자동 publish/full scan `NO-GO`, `full_scan_approval=false`.

## 잔여 우선 조치 (우선순위)

1. (선택·경미) `expert_main.py:11280` trailing whitespace 제거 또는 known-dirty로 의도 확정. `git diff --check` clean화.
2. (권고) `unittest discover -s tests` 신뢰성 복구: import 시 `sys.argv` argparse 실행을 `if __name__ == "__main__"` 가드로 이동하거나, CI를 명시 모듈 목록/pytest로 고정. 현재 discover의 `errors=86`은 실패가 아니라 하버스 아티팩트임을 CI 문서에 명시.
3. (추적) official-detail canonicalization / restore-contract deterministic 실패를 이번 커밋과 분리된 open gate 티켓으로 유지. CHECKLIST의 `[ ]` 항목과 연결. 이 게이트가 닫히기 전 P1 관계/router/canonical/HOLD 및 P2 early route는 승인·구현하지 않는다.
4. (활성화 시) `SemanticPublicationState` 상류 producer를 켤 경우, 신규 blocking reason이 기존 공개행을 차단하는 영향을 동일조건 canary로 측정한 뒤 진행.

## 감사 범위·한계

- diff 전량 검토 + 신규 모듈은 compile·대상 테스트·CHECKLIST 설계 근거로 판정했고, `expert_main.py`(+866)와 신규 모듈(총 ~2,968줄)은 line-by-line 전수 대신 통합 지점·계약 seam 위주로 검토했다.
- 회귀 판정은 tracked source 6개에 대한 `git stash` 격리(2개 대표 모듈, 6 failures)로 근거화했다. discover의 나머지 FAIL/ERROR는 동일 격리 절차 시 baseline 재현 가능성이 높으나 개별 전수 확인은 하지 않았다(하버스 argv 아티팩트 때문). 명시 모듈 실행이 정본이다.
- 실제 라이브 런/`--parallel 16` grounding 런은 수행하지 않았다(코드 변경 위험 감사 범위). 운영 승인은 기존 게이트를 따른다.

## 운영 메모

본 감사 에이전트는 hidden model override가 적용된 `anthropic/claude-opus-4-8` / `reasoning_effort=medium`으로 실행됐다. 감사 결과는 독립 조언으로 취급하며, 최종 판정에는 root의 로컬 diff·테스트·실제 grouped run 검증만 사용한다.
