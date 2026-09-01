# P1 recovery plan receipt 독립 리뷰 (2026-07-20)

리뷰어: `/root/p1_review_plan_fable5_high` (독립 리뷰 lane, 구현과 분리)
과업 정본: `out/regression_safe_2712_remaining_improvements_20260718/p1_review_plan_task_ko.md`

## 결론

- 모듈 계약: **PASS**. `semantic_recovery_plan_receipt_v1`은 과업 정본의 receipt 계약 항목을 모두 충족한다.
- 공개 비간섭: **PASS**. attach 전후 `decision_id/stable_result_sha256/public_projection_sha256` 불변이 테스트와 2,712행 replay(드리프트 `0/0/0`)로 입증됐다.
- 게이트 상태 유지: **적절**. integrity `GO`, semantic effectiveness `NO-GO`, `full_scan_approval=false` 분리는 과업 경계와 일치한다.
- 범위 일탈: **경미, 문서화됨**. 원 과업의 수정 허용 4항목을 넘는 `expert_main.py` attach 배선과 frozen2712 analyzer가 추가됐으나, fail-close 드리프트 검증과 CHECKLIST 기록이 있어 승인 경계 침범은 없다.

## 검증 근거

### 1. 재실행 검증 (2026-07-20)

- focused `tests/test_semantic_recovery_plan.py` — `12/12 OK`
- analyzer `tests/test_analyze_semantic_recovery_plan_frozen2712.py` — `5/5 OK`
- 인접 `tests/test_semantic_review_router.py` + `tests/test_promotion_gate_contract.py` — `112 OK`
- `py_compile` — 모듈/테스트/analyzer/`publication_commit.py` 전부 PASS

### 2. receipt 계약 대조 (src/llm_batch/measurement/semantic_recovery_plan.py)

- `mode=PLAN_ONLY`, `public_apply=false`: build가 상수로 고정하고 validate가 위반 시 `SemanticRecoveryPlanError`로 거부한다.
- exact self-hash: `source_view_sha256`/`plan_sha256`/`receipt_sha256`를 canonical JSON으로 재계산 대조하며, deterministic recompute(`plan != _plan(source, errors)`)와 top-level exact field set 검사로 forged/extra/변조를 fail-close한다.
- publication 결속: `validate_publication_result_commit` 경유로 scope/index/post/attempt/decision/stable/public projection 7개 필드를 결속하고 mismatch를 즉시 거부한다.
- 관계 role: `primary|previous|mentioned|comparison`만 허용. `secondary/candidate/recommendation*` 계열은 `mentioned`로만 강등되고 primary 승격 경로가 없다. missing/multiple/ambiguous primary는 HOLD blocker, typed input 부재는 `UNKNOWN`.
- media quarantine: typed `semantic_publication.media_domain_class` 또는 typed `page_type`(news/program/game/comic/webtoon)만 근거로 사용한다. title surface·host 단독 분류 없음, cross-media는 `HOLD_CROSS_MEDIA`.
- canonical binding: HTTPS 공식 detail만 인정 — Kakao `/content/<digits>`, Naver `detail.series?productNo=<digits>`(단일 param), Novelpia `/novel/<digits>`. slug/hash/listing/deleted/query 오염 거부. `source_tier=official_detail` + `page_type=novel_page` + active 계열 `content_status` + display title이 모두 있어야 결속한다. one ID↔multi display 충돌은 `CANONICAL_ID_DISPLAY_COLLISION`으로 binding을 비운다.
- OCR raw title: `raw_ocr_evidence_count`로 계수만 하고 display로 렌더하지 않는다(테스트로 부재 확인).
- query plan: blocker→bounded purpose 매핑, `max_queries<=2`. degraded/unknown이면 `query_execution_allowed=false`, `max_queries=0`. healthy여도 plan-only로 `search_calls_executed=network_calls_executed=0`을 validator가 강제하고, 테스트가 `socket.create_connection` 미호출을 검증한다.
- 금지어: 특정 title/alias/post_id hardcode 없음. `아생갤`/`갤러리` 표면 기반 분류 없음(AGENTS.md 도메인 규칙 준수).
- frozen/manual label·judge seed 차단: injection 테스트에서 source_view/plan 불변 확인.

### 3. 공개 비간섭

- `src/llm_batch/ledger/publication_commit.py`의 `_ATTEMPT_LOCAL_RUN_META_KEYS`에 `semantic_recovery_plan_receipt` 포함 → stable publication payload에서 제외.
- 테스트가 attach 전후 `stable_result_sha256/decision_id/public_projection_sha256` 동일, `result_sha256`만 변화함을 검증.
- `expert_main.py`의 `_attach_semantic_recovery_plan_receipt`(1322행) 및 호출부(13781행)는 부착 직후 publication decision을 재계산해 세 hash 동일성을 비교하고 불일치 시 `PublicationCommitError`로 hard-fail한다.
- 2,712행 frozen replay: coverage `2712/2712`, missing/duplicate `0`, drift `0/0/0`, `public_apply=true 0`, search/network 실호출 `0/0` — `out/regression_safe_2712_remaining_improvements_20260718/semantic_recovery_plan_frozen2712_replay/summary.json`.

## 지적 사항

1. (범위 일탈, 경미) 과업 정본은 수정 허용을 4항목으로 한정하고 `expert_main.py`/analyzer 수정을 금지했으나, 실제로는 `expert_main.py` attach 배선과 `tools/analyze_semantic_recovery_plan_frozen2712.py`(+테스트, .gitignore 항목)가 추가됐다. 모두 non-writer·fail-close이고 CHECKLIST(15188~15203행 인접)에 회귀 근거와 함께 기록돼 실질 위험은 낮지만, 이후 과업 정본에는 확장된 allowlist를 명시해 정본-구현 간 불일치를 남기지 않기를 권고한다.
2. (경미) `_identity_key`가 display key를 canonical ID보다 우선하므로, 동일 normalized display의 미검증 primary 2건은 `primary_identity_count=1`로 계수될 수 있다. 다만 이 경우 `PRIMARY_CANONICAL_ID_UNBOUND` blocker로 여전히 HOLD가 되어 fail-close는 유지된다. 후속 rule version에서 verified ID 우선 계수를 고려할 만하다.
3. (경미) `_HEALTHY_SEARCH_STATUSES`가 `healthy` 외 `ok/search_ok`를 포함한다. 현행 producer 상태 문자열과의 대응을 문서에 한 줄 남기면 좋다.
4. (참고) `publish_allowed=true`이고 blocker가 없으면 `NOT_APPLICABLE`로 blocker/binding을 비우는 설계는 "이미 공개 성공한 행은 recovery 불필요"라는 보수적 해석으로 타당하다.

## 승인 경계 재확인

- 본 리뷰는 P1 plan-only receipt의 계약·무결성 검증이며, semantic effectiveness `NO-GO`, 자동 query 실행·자동 publish·P2 early route·`full_scan_approval` 승격 근거가 아니다.
- `query_execution_allowed`/`max_queries`는 계획 필드일 뿐 실행 권한이 아니라는 CHECKLIST 상태 그대로를 유지한다.
