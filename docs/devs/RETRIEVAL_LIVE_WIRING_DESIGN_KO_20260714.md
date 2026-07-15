# 2026-07-14 RetrievalState live wiring 설계 (retrieval_live_design)

## 결론

이 문서는 설계 산출물이다. 구현·런타임·승인 상태는 바꾸지 않는다.

- 설계 상태: `DESIGN_READY_FOR_IMPLEMENTATION`
- 구현/런타임: `NOT_IMPLEMENTED / NOT_RUN`
- 상위 게이트: `NO-GO / REVIEW-LOCKED / full_scan_approval=false` 유지
- 범위: `docs/devs/LIVE_PIPELINE_RUN_REVIEW_KO_20260714.md`의 bounded repair 4항목 중 "RetrievalState live wiring" 1개 항목만 다룬다. model/cap binding, BatchContext post-commit learning, dashboard validation fail-close는 별도 항목이다.

## 배경과 격차

정적 계약은 이미 존재하고 검증됐다.

- `src/llm_batch/promotion_gate.py:179` `RetrievalState(required/attempted/recovered/hard_blocked/reason_codes)`
- `blocks_publish()` = `hard_blocked or (required and not recovered)` (`:214`)
- 게이트 소비: `_state_reason_codes`가 populated retrieval에서 `search_blind_condition` / `search_evidence_missing`을 파생 (`:431`)
- default(None/no-op)는 지문 중립: `GroundingState.to_dict`가 default retrieval을 제거 (`:170`)
- 저장/복원 roundtrip: `retrieval_state_from_dict` (`:615`), `grounding_state_from_dict` (`:660`)
- 회귀: `tests/test_retrieval_state_fail_close.py` `10 PASS`, harness v5 실제 저장본 unsafe publish `1→0` (`out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/before_after_comparison.md`)

live 격차는 다음과 같다.

- `src/llm_batch/agentic_pipeline.py`와 `expert_main.py`의 `GroundingState(` 생성 지점(약 19곳) 어디에서도 `retrieval=`을 전달하지 않는다.
- row별 검색 상태는 `_build_search_health_public_fields` (`agentic_pipeline.py:16318`)가 `ctx.search_query_stats`에서 `search_health`(`ok / SEARCH_DEGRADED / SEARCH_DEGRADED_RECOVERED`)로 직렬화하지만(`:15742`, `expert_main.py:12901`), typed publication gate에는 연결되지 않는다.
- 결과: run `20260714_160355_054970`에서 flushed row의 `SEARCH_DEGRADED 115/162`(`71.0%`)이 게이트를 자동으로 닫지 못했고, P0 사례 `post_id=11716475`(context_only/unresolved + SEARCH_DEGRADED + publish)가 발생했다.
- 선행 문서의 남은 작업 정의: "`agentic_pipeline`/`orchestrator`가 실제 검색 상태를 `GroundingState.retrieval`로 채우고, 104k 종료 뒤 별도 runtime에서 검증한다" (`docs/devs/LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md:647`).

## 목표 / 비목표

목표:

1. live row가 실제 검색 상태를 typed `RetrievalState`로 최종 publish 계약에 전달한다.
2. 외부 근거가 필요한 행에서 검색이 미복구(degraded unrecovered)이거나 hard block이면 public title을 typed 입력만으로 fail-close한다.
3. 차단 행은 `candidate_only`로 후보를 보존하고 `blocked_official_title`에 기록해 REPROCESS로 회수 가능하게 한다.

비목표:

- 검색 품질 자체 개선(SEARCH_DEGRADED 비율 감소)은 이 배선의 범위가 아니다.
- P1 CandidateSet/NIL 선택의 public 적용은 금지 상태를 유지한다 (`docs/devs/TODO.md` P0 선행 규칙).
- 진행 중이던 104,502행 run에 대한 개입이나 동일 입력 전체 자동 재실행은 하지 않는다.

## 설계

### 원칙 1 — 단일 빌더 (single-writer)

`RetrievalState`는 row당 정확히 한 번, `search_health`와 동일한 소스(`ctx.search_query_stats`)에서 파생한다.

- 신규 헬퍼 `_build_retrieval_state(ctx) -> Optional[RetrievalState]`를 `_build_search_health_public_fields` 옆에 추가하고 같은 카운터를 읽는다.
- 계산 결과는 ctx에 캐시하고(예: `ctx._typed_retrieval_state`), 최종 계약 경로의 모든 `GroundingState` 생성에 동일 인스턴스를 주입한다.
- 직렬화된 `search_health.status`와 typed `retrieval`이 서로 모순되면 안 된다. 이 정합성은 단위 테스트와 감사 도구로 고정한다.

### 원칙 2 — 신호 매핑

| RetrievalState 필드 | live 신호 (`ctx.search_query_stats` 파생) |
| --- | --- |
| `attempted` | `queries_issued > 0` (`total`) |
| `recovered` | `attempted`이고 status가 `ok` 또는 `SEARCH_DEGRADED_RECOVERED` (즉 `unrecovered_degraded == 0` 이고 `degraded_zero <= degraded_recovered`) |
| `hard_blocked` | `attempted`이고 `accepted == 0`이며 `unrecovered_degraded > 0` — D2에서 확정 |
| `required` | D1 술어 (아래) |
| `reason_codes` | 상태 요약 코드 (예: `search_degraded_unrecovered`, `degraded_zero_exceeds_recovered`) |

stats가 없거나 전부 0인 행은 `None`을 유지한다. default 지문 중립 계약에 따라 기존 판정과 지문이 바뀌지 않는다.

### 결정 지점 D1 — `required` 술어

| 옵션 | 정의 | 위험 |
| --- | --- | --- |
| A (권장) | `attempted`이고, 검색-독립 강한 official anchor(본문/OCR 직접 확인된 `official_detail_url` 등 supports_publish 강근거가 검색 산출이 아닌 경우)가 없을 때 | 판정에 anchor 출처 분류가 필요 |
| B | `required = attempted` (검색을 시도한 모든 행) | 검색 없이도 공개 가능했던 행 과차단. 후보 보존이라 데이터 손실은 없지만 publish recall 하락 |
| C | `title_resolution_state`/scope 상태에서 파생 | 상태 오염 시 우회 — P0 `11716475`가 보여준 실패 모드와 동형 |

권장: A를 기본으로 구현하고, canary에서 B 대비 차단률 차이를 shadow 필드로만 기록한다. C 단독은 채택하지 않는다.

### 결정 지점 D2 — `hard_blocked` 판정

search-blind 조건(모든 provider 실패, accepted 0)의 정확한 live 신호는 구현 시 search stage의 blind-condition 플래그 존재 여부를 확인한 뒤 확정한다. 1차 후보는 `accepted == 0 and unrecovered_degraded > 0`이다. `hard_blocked`는 `required`와 무관하게 publish를 차단하므로 과차단 방향으로만 보수적으로 정의한다.

### 원칙 3 — 주입 지점

규칙: "publish_allowed를 개방(확대)할 수 있는 모든 `evaluate_publish_contract` 평가에는 동일 row-level `RetrievalState`를 주입한다."

- 최초 평가: `agentic_pipeline.py:15486` 부근의 최종 계약 생성.
- 재평가 계열: serializer inventory-only(`:15966`), mismatch(`:16055`), url-adjusted(`:15636`) 등. 이들은 fail-close 방향 재계약이라 주입 없이도 안전 방향이지만, `search_health`/`retrieval` 직렬화 일관성을 위해 동일 주입을 권장한다.
- `expert_main.py:9333` `safe_state`(typed_contract mismatch 복구 경로)도 동일 규칙을 적용한다. 이 경로는 이미 `official_title_exists=False` fail-close이므로 회귀 위험이 낮다.
- 구현 방식은 생성 지점 나열 수정보다, 계약 평가 직전에 `state`에 retrieval을 채워 넣는 주입 헬퍼(예: `_with_row_retrieval(ctx, state)`) 1개를 두고 모든 평가 경로가 그 헬퍼를 통과하게 한다.

### 원칙 4 — 직렬화와 감사

- row identity에 `retrieval_state`(typed dict)를 `search_health`와 나란히 직렬화한다. 복원은 기존 `grounding_state_from_dict` 경로를 그대로 쓴다.
- `tools/audit_expert_run_health.py`에 정합 검사를 추가한다: `search_health.status == SEARCH_DEGRADED`인데 populated retrieval이 없거나 `recovered=true`인 행을 모순으로 카운트한다.
- 로그에 SEARCH_DEGRADED가 있는데 retrieval이 전부 None인 run은 배선 누락 신호로 blocker에 올린다.

### 원칙 5 — 지문(lineage) 영향

- retrieval이 None/default인 행: 지문 불변 (기존 테스트 보장).
- populated 행: `publish_contract_input_fingerprint`가 바뀐다. 이는 의도된 변화이며, BEFORE/AFTER 비교는 harness v5 방식(동일 입력 replay에 retrieval만 추가)으로 수행한다.
- checkpoint 재개 시 이미 flush된 행은 재평가하지 않으므로 기존 저장본 지문은 오염되지 않는다.

## 실패 모드와 완화

| 실패 모드 | 완화 |
| --- | --- |
| 과차단(false block) | `candidate_only` + 후보 보존 + `blocked_official_title` 기록으로 비파괴. REPROCESS로 회수 |
| `search_health`와 `retrieval` 불일치 | 단일 빌더 + 감사 정합 검사 |
| stats 부재 행의 fail-open | default None은 계약상 무해(기존 판정 유지). no-work/context-only 단조성 게이트가 별도 방어. 감사에서 잔여 카운트 |
| `search_query_stats`의 row-locality 오염 | ctx가 row-로컬임을 단위 테스트로 고정. 공유 누적이면 잘못된 fail-close가 병렬 행에 전파되므로 구현 전 필수 확인 |
| duplicate 행 상호작용 | identical duplicate는 첫 행 기준 멱등 처리이므로 retrieval_state도 첫 행 것을 따른다 |
| D1 오판으로 인한 우회 | 옵션 A 채택 + canary에서 B 대비 차단률 shadow 기록으로 사후 판별 |

## 검증 계획 (구현 pass에서 수행)

1. 정적: `py_compile` + 신규 `tests/test_retrieval_state_live_wiring.py` — 신호 매핑 표의 각 행, D1 옵션 A 술어, stats row-locality, `search_health`/`retrieval` 정합.
2. 기존 회귀: `tests.test_retrieval_state_fail_close` `10`, `tests.test_publication_contract_convergence_audit` `43`, publish contract 영향 테스트 전체.
3. targeted rerun 6건: known-bad `11716475`, `11718099`, `11716480`, `11716448` + positive control `11718077`, `11714907`.
   - 기대: `11716475`는 publish → 차단(후보 보존), positive 2건은 publish 유지.
   - 조건: `--parallel 16`, dashboard ON(standalone 서버 선행 후 forwarding), `--vlm on --ocr on --require-vlm-ocr-for-images`, Slang DB OFF 또는 read-only snapshot.
4. targeted 통과 뒤에만 200행 canary — 차단률, 후보 보존율, 정합 모순 0을 보고한다.
5. 그 뒤 random baseline `1,000+`를 별도 산출물·별도 오류율로 검토한다.
6. 각 단계 통과는 해당 단계의 완료일 뿐이다. runtime completeness, semantic quality, approval은 계속 분리해 판정하고 `full_scan_approval=false`는 새 근거로 게이트가 통과하기 전까지 유지한다.

## 연계 문서

- `docs/devs/LIVE_PIPELINE_RUN_REVIEW_KO_20260714.md` — P1 격차 정의와 bounded repair 순서
- `docs/devs/LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md` — step 1 typed gate와 남은 live 배선 정의
- `docs/devs/loop_reports/LOOP_P0_RETRIEVAL_FAILCLOSE_HARNESS_20260711.md` — 정적 하네스 v5 정본
- `docs/devs/TODO.md`, `docs/devs/CHECKLIST.md`, `docs/devs/IMPROVEMENT_REGISTER.md` — 상태 추적
