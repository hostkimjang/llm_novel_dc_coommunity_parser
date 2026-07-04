# Promotion Gate Architecture Migration

Date: 2026-06-30

Status: `PARTIALLY_IMPLEMENTED_AS_SHARED_LAYER / LOOP179_UNITTEST_GO / LOOP182_PARENT_RUNTIME_GO / LOOP184_TARGETED_RUNTIME_GO_NO_DELTA / LOOP185_EXACT_ALIAS_CANDIDATE_HOLD_GO_NO_DELTA / LOOP186_COLLATERAL_FOLLOWUP_GO_NO_DELTA / LOOP187_NESTED_SCRUB_GO_UNIT_ONLY_NO_DELTA / LOOP189_PACKET_SEMANTIC_NO_GO / LOOP190_PUBLISH_TRACE_GO_UNIT_ONLY / LOOP191_192_TRACE_COVERAGE_GO_PACKET_NO_GO / LOOP195_ACK_PREVIOUS_WORK_SCOPE_GATE_GO_UNIT_ONLY / LOOP196_BATCH_ALIAS_SCOPE_GATE_GO_UNIT_ONLY / LOOP197_DIRECT_OCR_SCOPE_GATE_GO_UNIT_ONLY / LOOP198_199_PACKET_RUNTIME_GO_SEMANTIC_NO_GO / LOOP200_202_FINAL_LEDGER_CONSISTENCY_GO / LOOP203_204_UPSTREAM_GATE_GO / LOOP205_208_PACKET_VARIANCE_REVIEW_GO_NO_DELTA / LOOP209_211_PREVIOUS_WORK_PRESERVED_GO_NO_DELTA / LOOP212_213_TITLE_LED_ALIAS_GUARD_GO_NO_DELTA / LOOP214_217_EXACT_ALIAS_IMAGE_CONTEXT_TRACE_GO_NO_DELTA / LOOP218_CHARACTER_BRIDGE_SCOPE_TRACE_GO_NO_DELTA / LOOP219_SHARED_GATE_UNCONFIRMED_ALIAS_GO_NO_DELTA / LOOP220_DIRECT_ALIAS_PROBE_GO_PACKET_POSITIVE_DELTA_REPLAY_REQUIRED / LOOP221_PARENT_REPLAY_RUNTIME_GO_SEMANTIC_REVIEW_LOCKED_NO_DELTA / LOOP222_SAFE_LOSS_SOURCE_NATIVE_REVIEW_NO_DELTA / LOOP223_FOCUSED_PATCH_GO_NO_DELTA / LOOP224_PARENT_RUNTIME_GO_SEMANTIC_NO_GO_NO_DELTA / LOOP225_ENVELOPE_TITLE_GATE_RUNTIME_GO_SEMANTIC_NO_GO_NO_DELTA / LOOP230_TITLE_LED_SERIALIZER_PARTIAL_GO / LOOP231_PARENT_RUNTIME_GO_SEMANTIC_NO_GO_NO_DELTA / LOOP232_SOURCE_NATIVE_VARIANCE_REVIEW_NO_DELTA / LOOP233_DIRECT_IMAGE_CHARACTER_GATE_GO_UNIT_ONLY_NO_DELTA / LOOP234_DIRECT_IMAGE_RUNTIME_GO_PUBLICATION_NO_GO_NO_DELTA / LOOP235_CHARACTER_PARENT_BRIDGE_RUNTIME_GO_PUBLICATION_NO_GO_URL_TITLE_CONTRACT_REQUIRED / LOOP236_URL_TITLE_DIRECT_SUPPORT_GUARD_TARGETED_GO_NO_DELTA / LOOP237_PARENT_RUNTIME_GO_SEMANTIC_NO_GO_NO_DELTA / LOOP239_TITLE_LED_PROBE_RUNTIME_GO_SEMANTIC_NO_GO_NO_DELTA / LOOP277_CANDIDATE_PUBLICATION_CONTRACT_REQUIRED_REVIEW_LOCKED / LOOP293_FINAL_SCOPE_ORDER_GO_UNIT_RUNTIME_REVIEW_LOCKED / LOOP296_SAFE_LOSS_N5_WRAPPER_GO_PLAN_READY / LOOP304_SAFE_LOSS_ALIAS_CONTRACT_GO_UNIT / LOOP307_SAFE_LOSS_ALIAS_CONTRACT_GO_UNIT_FLIP_NO_GO / LOOP308_UNSAFE_PROMOTION_TRIAGE_COMPLETE / LOOP309_BACKGROUND_HANDOFF_QUEUE_RECONCILED / LOOP310_SAFE_LOSS_SOURCE_NATIVE_PARTIAL / LOOP311_RUNTIME_REFRESH_DISPATCHED_NOT_APPROVAL / LOOP312_SAFE_LOSS_SOURCE_NATIVE_PARTIAL_59_OF_147 / LOOP313_SAFE_LOSS_ALIAS_CONTRACT_GO_UNIT_RUNTIME_NOT_RUN / LOOP314_CURRENT_HEAD_RUNTIME_DISPATCHED_NOT_APPROVAL / LOOP315_CHARACTER_SETTING_BRIDGE_GO_UNIT_RUNTIME_NOT_RUN / LOOP316_SAFE_LOSS_SOURCE_NATIVE_PARTIAL_74_OF_147 / LOOP317_SAFE_LOSS_SOURCE_NATIVE_PARTIAL_89_OF_147 / LOOP318_SAFE_LOSS_SOURCE_NATIVE_PARTIAL_104_OF_147 / LOOP319_OVERRIDE_AUDIT_ROW_GO / LOOP320_SAFE_LOSS_SOURCE_NATIVE_PARTIAL_119_OF_147 / LOOP349_CANONICAL_VARIANT_QUARANTINE_RESIDUAL_120 / LOOP350_REPAIR_AFTER_WRONG_WORK_STALL_NO_DELTA / GOAL_NOT_COMPLETE`

Latest addendum: `LOOP428_DIRECT_ALIAS_DISCOURSE_PROBE_GO_UNIT / RUNTIME_NOT_RUN_AFTER_PATCH / EXPECTED_ANSWER_INHERITED_NO_GO_15_OF_18 / SEARCH_P0_REVIEW_DEGRADED / FULL375_NOT_OPEN / GOAL_NOT_COMPLETE / REVIEW_LOCKED`

Current status override (Loop428): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop427 golden18 실패 `11698880`은 Gatekeeper가 `search_requests=[]`와 image-only `possible_characters`로 판단하고, Discourse `search_suggestions`의 `가챠펑크 세드릭` query가 자연어 purpose 때문에 non-novel early exit 전에 probe로 쓰이지 못한 경로로 좁혔다. `src/llm_batch/experts/orchestrator.py`는 Gatekeeper/Discourse 검색 제안을 먼저 합치고, Discourse suggestion을 `discourse_suggestion` probe로 정규화하며, Gatekeeper character set이 비어 있으면 worklike query token 중 본문 직접 토큰이고 alias가 아닌 값만 character 후보로 보강한다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 추가하지 않았다. 검증은 py_compile PASS, focused non-novel early-exit `3` PASS, title-lead guard 전체 `213` PASS다. Runtime replay after patch는 `NOT_RUN_AFTER_PATCH`이고 Loop427 runtime `18/18`은 생산성 상속 근거로만 사용한다. Gate는 code contract `GO_UNIT`, runtime production `GO_INHERITED_LOOP427_ONLY`, expected-answer `NO-GO / inherited Loop427 15 of 18`, search recovery `P0 / REVIEW`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4 / residual 105`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop427): Loop426 커밋 `4849c538` 이후 full375, bounded 1000~1500, N5 flip probe, 동일 38-row parent packet replay는 발주하지 않고 golden18 단일 search 포함 non-light 런만 실행했다. Run `20260704_222456_555589`는 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, `large_run_complete=true`, `ordered_flush_blocked=false`, MCP health `include_search=true`, `light_mode=false`, ok/failure `8/0`, VLM/OCR `READY`로 완료됐다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 추가하지 않았다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract convergence는 `GO / 0 violations`지만 search evidence는 `REVIEW / search_degraded_observed`다. Golden expected-answer는 `NO-GO / 15 of 18`이고 실패는 `11694019`, `11660237`, `11698880`이다. Loop426 단건 `11698880` safe_resolved는 Loop427 mixed-input에서 positive unresolved로 떨어져 hard-hold 완화 근거가 아니다. Golden shared collateral은 `NO-GO / 4`, full375 collateral은 `NOT_OPEN`이다. Gate는 runtime production `GO / 18 of 18`, expected-answer `NO-GO / 15 of 18`, search recovery `P0 / REVIEW`, collateral active lane `reclassified 74 / runtime-verified 4 / residual 105`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop414): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. `11698897` 단일 search 포함 non-light 런만 실행했고 run `20260704_183852_026609`은 input/completed/flushed/pending/failed `1/1/1/0/0`, checkpoint/result rows `1/1`, `large_run_complete=true`, `ordered_flush_blocked=false`, MCP health `include_search=true`, `light_mode=false`, ok/failure `1/0`로 row 생산성을 확인했다. `src/llm_batch/agentic_pipeline.py`는 title-led alias gate에서 competing official detail 후보를 `title_led_alias_contextual_official_detail_competes`로 기록해 wrong public publish를 막고, `expert_main.py`는 gate competing candidate를 `publish_contract_trace.pre_gate_candidate` 대표 후보로 보존한다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry, slang DB write-back은 추가하지 않았다. Runtime result는 `official_title=null`, `candidate_ledger_status=promotion_blocked`, `safe_resolved=false`, `promotion_decision.status=candidate_only`, `publish_allowed=false`이며 wrong candidate `쳇바퀴의 생쥐 사도가 되었다`는 public output에서 제거됐다. Current-code projection은 `변방계에서 회귀자로 살아남기` / `https://novelpia.com/novel/382324`를 `promotion_gate_competing_candidate`로 보존한다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract convergence는 runtime/projected 모두 `GO / 0 violations`다. Golden expected-answer는 `NO-GO / inherited Loop413 16 of 18`, search recovery는 broader `P0 / REVIEW`, full375 collateral은 `NOT_OPEN`이다. Gate는 targeted runtime `GO / 1 of 1`, wrong publish closure `GO_TARGETED`, candidate trace `GO_CODE_AND_PROJECTION`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop413): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Current HEAD `d95f1a57`에서 golden18 단일 search 포함 non-light 런만 실행했고 run `20260704_174823_875969`은 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, pending snapshot `0`, `large_run_complete=true`, `ordered_flush_blocked=false`, MCP health `include_search=true`, `light_mode=false`, ok/failure `8/0`로 row 생산성을 확인했다. 코드 변경과 R1 hardcoded cue/title list 확장은 없다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract convergence는 `GO / 0 violations`지만 search evidence는 `REVIEW / search_degraded_observed`다. Golden expected-answer는 `NO-GO / 16 of 18`이고 실패는 `11698897` wrong title, `11698880` positive unresolved다. Golden shared collateral은 `NO-GO / 9`, full375 collateral은 `NOT_OPEN`이다. Runtime 불필요 `11708445` OVERRIDE AUDIT는 completed-source/source-native blind judge로 `ACCEPT / candidate_only_block_is_correct`를 재확인했고 public contract는 `official_title=null`, `official_url=null`, `candidate_ledger_status=promotion_blocked`, `safe_resolved=false`, `promotion_decision.status=candidate_only`, `publish_allowed=false`다. Collateral 105는 `reclassified 74 / runtime-verified 4 / residual 105`로 분리 보고하고, survey triage anchor는 `136` errors의 `wrong_work_among_aliases=27`, `recall_miss=49`로 재정렬한다. Gate는 runtime production `GO / 18 of 18`, expected-answer `NO-GO / 16 of 18`, search recovery `P0 / REVIEW`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop412): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop412는 `11698880` 단건만 실행했고 run `20260704_172216_712128`은 input/completed/flushed/pending/failed `1/1/1/0/0`, pending snapshot `0`, `large_run_complete=true`, `ordered_flush_blocked=false`로 row 생산성을 확인했다. `src/llm_batch/agentic_pipeline.py`는 title-led public gate에서도 `_has_unresolved_body_compound_character_anchor(...)`를 경유해 본문 `가챠펑크 세드릭` unresolved anchor가 current title body bridge 없이 남으면 `unresolved_body_character_work_anchor` / `missing_body_work_bridge`로 publish를 막는다. `expert_main.py`는 promotion-blocked scrub에서 blocked title이 stale `candidate_ledger.title_candidates` 요약에 빠져 있으면 요약에도 보존한다. R1 hardcoded cue/title list, `post_id` 예외, 작품 전용 registry는 추가하지 않았다. Loop411 wrong publish `아카데미 생존 갤러리`는 public output에서 제거됐고 final public contract는 `official_title=null`, `candidate_ledger_status=promotion_blocked`, `promotion_decision.status=candidate_only`, `publish_allowed=false`다. 정답 후보 `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`는 identity 후보와 publish trace pre-gate에 보존됐다. 저장된 Loop412 result의 ledger 요약 stale은 코드 계약으로 보정했지만 public title은 아직 HOLD라 expected-answer pass가 아니다. 검증은 py_compile PASS, ExpertMainCommentMetadata `63` PASS, title-lead guard `202` PASS다. Gate는 targeted runtime `GO / 1 of 1`, wrong publish closure `GO_TARGETED`, correct candidate preservation `GO_CANDIDATE_ONLY`, golden expected-answer `NO-GO / inherited Loop411 17 of 18`, golden shared collateral `NO-GO / inherited Loop411 6`, search recovery `P0 / ROW_LEVEL_EVIDENCE_WITH_PREFLIGHT_LIGHT_CAVEAT`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop411): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop411은 golden18 단일 search 포함 non-light 런 `20260704_163610_473354`만 실행했고 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, pending snapshot rows `0`, `large_run_complete=true`, `ordered_flush_blocked=false`로 row 생산성을 증명했다. `src/llm_batch/experts/orchestrator.py`는 title-led compact alias에 `시리즈 {term} 작가` platform probe를 추가하고 Naver Series official detail result가 rerank budget에서 보존되도록 했다. R1 hardcoded cue/title list, `post_id` 예외, `빛세구` 전용 registry는 추가하지 않았다. `11668307`은 `시리즈 빛세구 작가` query와 Naver Series URL `https://series.naver.com/novel/detail.series?productNo=13598334` 근거로 `빚을 져서라도 세상은 구해야 할 거 아니야` safe_resolved에 도달했다. Expected-answer audit는 `NO-GO / 17 of 18`이고 남은 실패는 `11698880` expected `가챠 중독자의 퓨전펑크 생활`, actual `아카데미 생존 갤러리`다. Golden shared collateral은 `NO-GO / 6`, search recovery는 `P0 / REVIEW / search_timeout_observed + search_degraded_observed`, full375 collateral은 `NOT_OPEN`이다. 검증은 focused title-led `3` PASS, title-lead guard 전체 `201` PASS, py_compile PASS, health audit `GO`, publication contract `GO / violations 0`, Data Analytics artifact validate/render PASS다. Gate는 runtime production `GO / 18 of 18`, code contract `GO_UNIT`, golden expected-answer `NO-GO / 17 of 18`, golden shared collateral `NO-GO / 6`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop410): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop410 targeted runtime run `20260704_160456_941367`은 input/completed/flushed/pending/failed `1/1/1/0/0`로 row 생산성은 증명했지만 첫 live 결과는 `11705245`를 `하남자의 탑 공략법`으로 잘못 publish했다. 원인은 `batch_alias_public_title_bridge + official_detail_url`이 `title_in_post=false`, `image_ocr_title_evidence=false`, `post_spans=0`, `search_snippets=0`, `official_urls=1` 조건에서도 public ledger를 열어준 것이다. `expert_main.py` final publication ledger는 title-only alias counterevidence와 batch alias URL-only counterevidence를 `candidate_only`로 내리고, 새 demote flag를 restore hard-negative로 처리한다. R1 hardcoded cue/title 리스트, slang registry, `post_id` 예외는 추가하지 않았다. 저장된 Loop410 row projection은 `promotion_blocked`, `safe_resolved=false`, public title `null`로 닫히며, Loop409 golden18 저장 결과 projection audit는 `NO-GO / 17 of 18`이다. `11705245`는 expected-null pass로 이동했고 남은 실패는 `11668307` positive unresolved다. Golden shared collateral projection은 `NO-GO / 5`, full375 collateral은 `NOT_OPEN`이다. 검증은 py_compile PASS, focused contract `3` PASS, ExpertMainCommentMetadataTest `62` PASS, publication/work-bridge/title-lead bundle `206` PASS, Data Analytics artifact validate/render PASS다. Gate는 targeted runtime `GO / 1 of 1`, code contract `GO_UNIT`, golden expected-answer projection `NO-GO / 17 of 18`, golden shared collateral projection `NO-GO / 5`, search recovery `P0 / REVIEW`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop409): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Current worktree의 contextual exact-title 보강 뒤 golden18 단일 search 포함 non-light 런만 실행했고 run `20260704_150836_336421`은 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, `large_run_complete=true`, `ordered_flush_blocked=false`로 완료됐다. Health audit는 flush integrity `GO / clean_completed_source`, publication contract convergence `GO / violations 0`이지만 search evidence는 `REVIEW / search_degraded_observed`다. Expected-answer audit는 `NO-GO / 16 of 18`이고 `11694019`는 `이세계에서 사이비로 살아남기`로 회복했지만 실패 `11705245`, `11668307`이 남았다. Golden shared collateral regression candidates는 `11698880`, `11705231`, `11705245` 3건이고 full375 collateral은 `NOT_OPEN`이다. R1 hardcoded cue/title 리스트 확장은 없고, wiki/community exact-title evidence는 official-detail gap seed로만 쓰며 community 제목 substring 확장은 금지한다. `11708445` OVERRIDE AUDIT는 Loop407 `ACCEPT / candidate_only_block_is_correct`로 닫혀 queue 재등재 대상이 아니다. Gate는 runtime production `GO / 18 of 18`, expected-answer `NO-GO / 16 of 18`, search recovery `P0 / REVIEW / SEARCH_BLIND_CONDITIONAL`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop407): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Runtime 불필요한 `11708445` OVERRIDE AUDIT를 current HEAD `6681f10b`에서 source-native로 다시 고정했다. Worker log에는 `OVERRIDE AUDIT post_id=11708445: LLM=False -> final=True`가 있지만, completed-source result/checkpoint의 최종 public contract는 `official_title=null`, `official_url=null`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `bypassed_gate=false`, `candidate_ledger_status=promotion_blocked`, `safe_resolved=false`다. Web 확인상 댓글 `제냥꾼`은 `제국사냥꾼` 후보와 연결될 수 있으나 추천성 부차 참조라 public title publish 근거가 아니다. `11708445`는 `ACCEPT / candidate_only_block_is_correct`, `GO_ROW_CONTRACT_ONLY`로 닫고 다시 OVERRIDE AUDIT queue로 재등재하지 않는다. Gate는 Loop406 runtime production `GO / 18 of 18`을 유지하되 expected-answer `NO-GO / 16 of 18`, golden shared collateral `NO-GO / 3`, search recovery `P0 / REVIEW / SEARCH_BLIND_CONDITIONAL`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop405): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop401에서 단위 계약으로 막은 Loop399 `11713212` unexpected public title leak를 current HEAD 단건 runtime으로 갱신했다. 코드 변경과 R1 hardcoded cue/title 리스트 확장은 없다. Run `20260704_132624_502514`은 input/completed/flushed/pending/failed `1/1/1/0/0`, checkpoint/result rows `1/1`, `large_run_complete=true`, `ordered_flush_blocked=false`, VLM/OCR `READY`다. Final public title/url은 `null/null`이고 `candidate_ledger_status=promotion_blocked`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `bypassed_gate=false`다. 로그에서 `가장`, `절대`, `무한`, `in`, `sss급` alias rescue가 `semantic_seed_no_work_context`로 차단됐다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract `GO / violations 0`이다. Row search는 `ok`, queries `6`, degraded `0`, unrecovered degraded `0`이지만 manifest preflight가 include_search `false`, light_mode `true`라 broader search recovery는 닫지 않는다. Gate는 targeted runtime `GO / 1 of 1`, targeted semantic `GO_ROW_ONLY_PUBLIC_TITLE_BLOCKED`, golden expected-answer `NOT_REFRESHED_AFTER_LOOP405 / inherited Loop399 NO-GO 14 of 18`, broader search recovery `P0 / ROW_LEVEL_OK_WITH_PREFLIGHT_LIGHT_CAVEAT / search-blind conditional`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop404): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop399 `11668307` positive unresolved를 title-led work consumption compact alias 계약으로 좁혔고, `_has_title_led_work_consumption_signal(ctx)` 기반 일반 술어만 사용했다. `빛세구` 전용 registry/R1 hardcoded cue/title list 확장은 없다. Run `20260704_130002_186429`은 input/completed/flushed/pending/failed `1/1/1/0/0`, result/checkpoint rows `1/1`, `large_run_complete=true`, `ordered_flush_blocked=false`, VLM/OCR `READY`다. Final public title은 `빚을 져서라도 세상은 구해야 할 거 아니야`, URL은 `https://series.naver.com/novel/detail.series?productNo=13598334`이며 `candidate_ledger_status=safe_resolved`, `promotion_decision.status=publish`, `publish_allowed=true`, `bypassed_gate=false`, publication contract convergence `GO / violations 0`이다. Row search는 `ok`, queries `20`, degraded `0`, unrecovered degraded `0`이지만 manifest preflight가 include_search `false`, light_mode `true`라 broader search recovery는 닫지 않는다. Gate는 targeted runtime `GO / 1 of 1`, targeted semantic `GO_ROW_ONLY`, golden expected-answer `NOT_REFRESHED_AFTER_LOOP404 / inherited Loop399 NO-GO 14 of 18`, broader search recovery `P0 / ROW_LEVEL_OK_WITH_PREFLIGHT_LIGHT_CAVEAT / search-blind conditional`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop403): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop402 direct-image/OCR canonical 계약이 runtime 직렬화까지 도달하는지 `11663540` 단건만 search 포함 non-light로 실행했다. Run `20260704_123503_819467`은 input/completed/flushed/pending/failed `1/1/1/0/0`, result/checkpoint rows `1/1`, `large_run_complete=true`, `ordered_flush_blocked=false`, VLM/OCR `READY`다. MCP health preflight는 include_search `true`, light_mode `false`, required `2`, ok `2`이며 row search는 `SEARCH_DEGRADED_RECOVERED`, unrecovered degraded `0`이다. Final public title은 `전 버튜버가 하고 싶은데요`, URL은 `https://novelpia.com/novel/275975`이고 OCR 표면 `전 버두비가 하고 싶은데요`는 후보로 보존되지만 public title을 덮지 않는다. `candidate_ledger_status=safe_resolved`, `promotion_decision.status=publish`, `publish_allowed=true`, `bypassed_gate=false`, publication contract convergence `GO / violations 0`이다. Gate는 targeted runtime `GO / 1 of 1`, targeted semantic `GO_ROW_ONLY`, golden expected-answer `NOT_REFRESHED_AFTER_LOOP403 / inherited Loop399 NO-GO 14 of 18`, broader search recovery `P0 / ROW_LEVEL_RECOVERED_ONLY / search-blind conditional`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop402): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop399 `11663540` wrong title은 URL 없는 direct-image/OCR 표면 `전 버두바가 하고 싶으데요`가 검색 결과 `주서연(전 버튜버가 하고 싶은데요)` public character-parenthetical bridge보다 먼저 publish 후보로 선택된 경로로 좁혔다. `src/llm_batch/agentic_pipeline.py`는 `_select_public_canonical_direct_image_ocr_variant(...)`와 `_is_near_ocr_title_variant(...)`를 추가했고, OCR work-surface가 post-mentioned character의 public parenthetical title과 near-variant로 맞을 때만 canonical title로 치환한다. 전역 title similarity를 낮추지 않았고 R1 hardcoded cue/title 리스트 확장은 없다. `tests/test_title_lead_search_inferred_guard.py`에는 `11663540` positive와 no-bridge negative control을 추가했다. 검증은 py_compile PASS, focused direct-image `3` PASS, title-lead guard 전체 `199` PASS다. 참고로 ignored `tests.test_agentic_pipeline_rework` 전체는 481개 중 batch alias/search-intent/recommendation 별도 실패 `5`개라 이번 gate로 세지 않는다. Gate는 code contract `GO_UNIT`, runtime replay after patch `NOT_RUN_AFTER_PATCH`, inherited expected-answer `NO-GO / Loop399 14 of 18`, broader search recovery `P0 / GOLDEN18_SEARCH_GO_ONLY / search-blind conditional`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop400): 신규 full375/bounded/N5/golden18 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Loop399 `11698880` wrong publish는 정답 후보가 final `title_candidates`에 보존되지 않은 상태에서 `resolved_public_title_scope`가 post-title alias `아생갤`과 search official detail만으로 `아카데미 생존 갤러리`를 publish한 경로로 좁혔다. `src/llm_batch/agentic_pipeline.py`는 `_has_unresolved_body_compound_character_anchor(...)`를 추가했고, `_record_resolved_public_title_gate_decision(...)`가 verified body competition 및 unresolved body compound character anchor를 `context_only` scope block으로 기록한다. Current title/alias가 body에 없고 strong verified current link도 없는데 body-local modifier+character anchor가 남으면 `unresolved_body_character_work_anchor` / `missing_body_work_bridge`로 publish를 막는다. `tests/test_title_lead_search_inferred_guard.py`에는 `11698880` negative 계약과 current-alias-in-body positive control을 추가했다. 검증은 py_compile PASS, focused `4` PASS, related gate `5` PASS, work-bridge `3` PASS, promotion gate `22` PASS, title-lead guard `196` PASS, `git diff --check` PASS(CRLF warning only)다. R1 hardcoded cue 리스트 확장은 없다. Gate는 code contract `GO_UNIT`, runtime replay after patch `NOT_RUN_AFTER_PATCH`, inherited expected-answer `NO-GO / Loop399 14 of 18`, golden shared collateral `NO-GO / 7`, broader search recovery `P0 / GOLDEN18_SEARCH_GO_ONLY / search-blind conditional`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop399): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 계속 동결했다. 현 HEAD `d7b7fa11`에서 golden18 단일 런만 search 포함 non-light로 재실행했고 run `20260704_105814_374640`은 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, `large_run_complete=true`, `ordered_flush_blocked=false`로 완료됐다. MCP health preflight는 `mcp_health_include_search=true`, `mcp_health_light_mode=false`, required `2`, ok `2`이며 shard 검색 응답도 `2/2 OK`였다. Run health audit는 `flush_integrity=GO / clean_completed_source`, search evidence `GO`, publication contract convergence `GO / violations 0`이다. Expected-answer audit는 `NO-GO / 14 of 18`이고 실패는 `11663540` wrong title `전 버두바가 하고 싶으데요`, `11668307` positive unresolved, `11713212` unexpected title `SSS급 죽어야 사는 헌터`, `11698880` wrong title `아카데미 생존 갤러리`다. `11660237`은 이번 런에서 `테라포밍`으로 통과했지만 N>=5 flip probe 대체 증거가 아니며, `11698880` 오귀속 때문에 hard-hold 완화 근거도 아니다. Golden shared collateral은 shared `18`, changed `17`, regression candidates `7`이고 full375 collateral은 `NOT_OPEN`이다. R1 hardcoded cue 리스트 확장은 없다. Gate는 golden18 runtime `GO_GOLDEN18_RUNTIME_ONLY`, golden expected-answer `NO-GO / 14 of 18`, golden shared collateral `NO-GO / 7`, broader search recovery `P0 / GOLDEN18_SEARCH_GO_ONLY`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop396-398): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 계속 동결한다. Current HEAD `66e27ff5` golden18 Loop396 run `20260704_095205_277619`는 search 포함 non-light health preflight `2/2 OK`로 시작했지만 input/completed/flushed/pending/failed `18/17/12/5/0`, checkpoint rows `17`, `next_save_idx=13`, `ordered_flush_blocked=true`, blocker `11700470`로 끝나 golden18 18/18 생산성을 증명하지 못했다. `src/llm_batch/agentic_pipeline.py`는 image/OCR scene HOLD에서 local title bridge 없는 late canonical rescue scan을 스킵하도록 보강했고, 검색 공식 후보나 non-promotable OCR 제목 조각만으로 직접 title support를 인정하지 않는다. Loop397 `11700470` 단건은 `1/1/0/0`로 flush됐지만 첫 helper가 canonical rescue를 실제로 스킵하지 못했다. Loop398 같은 행 재실행은 `1/1/0/0`, `ordered_flush_blocked=false`, serialized public title `null`, 후보 `무당파 둔재의 엘프환생/교수형` 보존으로 row 생산과 title HOLD를 확인했다. 다만 Loop398 MCP health preflight는 light로 기록되어 search-health proof가 아니며, golden18 after patch는 `NOT_PROVEN`이다. 검증은 py_compile PASS, focused contract `3` PASS, broader guard `10` PASS다. R1 hardcoded cue 리스트 확장은 없다. Gate는 current golden18 runtime `NO-GO_RUNTIME_STALL`, targeted `11700470` runtime `GO_SINGLE_ROW_FLUSH`, search recovery `P0 / SEARCH_BLIND_CONDITIONAL`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop394-395): 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 계속 동결한다. 현 HEAD `8328c009` golden18 단일 search 포함 non-light Loop394 run `20260704_084824_952454`는 input/completed/flushed/pending/failed `18/18/18/0/0`, result/checkpoint rows `18/18`, `large_run_complete=true`로 완료되어 row 생산성은 증명했다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract convergence `GO / violations 0`이지만 search evidence는 `REVIEW / search_degraded_observed`다. Expected-answer는 `NO-GO / 13 of 18`, 실패는 `11705245`, `11663521`, `11663540`, `11700470`, `11698880`이다. Collateral은 shared `18`, changed `17`, regression candidates `8`이고 full375 collateral은 `NOT_OPEN`이다. Loop395 `11700470` patch-after 단건 runtime은 decoder/verifier/arbiter 후 `OVERRIDE AUDIT post_id=11700470 LLM=False -> final=True` 로그까지 도달했지만 result/checkpoint flush 전 stall로 끝나 manifest `1/0/0/0/0`, checkpoint `0`, result 없음이다. `src/llm_batch/agentic_pipeline.py`는 runtime 직렬화 전 `image_enrichment`에서 fallback image evidence catalog를 구성해 image-scope public publish gate에 투입한다. R1 hardcoded cue 리스트 확장은 없다. `11708445` OVERRIDE AUDIT는 Loop394 산출물로 다시 고정했고 `ACCEPT / candidate_only_block_is_correct`, `GO_ROW_CONTRACT_ONLY`다. Gate는 runtime production `GO_GOLDEN18_ONLY`, targeted replay `NO-GO_RUNTIME_STALL`, search recovery `P0 / REVIEW / SEARCH_BLIND_CONDITIONAL`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop390): 신규 full375/bounded/N5/golden18 runtime은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. Loop389 실패 `11698880`의 wrong publish 경로는 `가챠펑크` competing candidate가 보존됐지만 URL 없는 `llm_only` 후보라 기존 body-verified competition override를 통과하지 못하고, `아생갤` title-led gate가 `row_discusses_work_as_work=true`로 `아카데미 생존 갤러리`를 publish한 것이다. `expert_main.py` final publication ledger는 title-led alias public 후보가 source text alias support와 `confirmed_alias:*` 또는 explicit alias/work-lock을 가진 competing preserved work와 충돌하면 competing work로 재수렴한다. R1 hardcoded cue 리스트 확장은 없다. 저장된 Loop389 `11698880` 결과 직접 재동기화는 `official_title=가챠 중독자의 퓨전펑크 생활`, `official_url=null`, `publication_source=verified_alias_work_competition`, `changed=true`로 통과했다. 검증은 py_compile PASS, focused expert tests `4` PASS, publication/comment metadata bundle `62` PASS, title-led guard focused `3` PASS다. Gate는 code contract `GO_UNIT`, runtime replay after patch `NOT_RUN_AFTER_PATCH`, expected-answer `NO-GO / inherited 15 of 18`, search recovery `P0 / SEARCH_BLIND_CONDITIONAL`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop389): 신규 full375/bounded/N5 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. 현 HEAD `6349197e`에서 golden18 단일 search non-light runtime만 실행했고 run `20260704_062721_209425`는 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, VLM/OCR `READY`, `large_run_complete=true`로 완료됐다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract convergence `GO / violations 0`이지만 search evidence는 `REVIEW / search_degraded_observed`, unrecovered degraded total `4`다. Expected-answer audit는 `NO-GO / 15 of 18`이고 실패는 `11698897`, `11700470`, `11698880`이다. `11660237`은 `테라포밍`으로 통과했지만 N>=5 flip probe를 대체하지 않는다. `11698880`은 expected `가챠 중독자의 퓨전펑크 생활` 대신 `아카데미 생존 갤러리`로 오귀속되어 hard-hold 완화 근거가 아니다. `11694019`는 Loop388 단건 safe_resolved가 golden18 mixed input에서는 evidence-preserved unresolved로 내려갔다. Golden shared collateral은 changed `5`, regression candidates `3`, full375 collateral은 `NOT_OPEN`이다. `11708445` OVERRIDE AUDIT는 Loop373 `ACCEPT / candidate_only_block_is_correct`, `GO_ROW_CONTRACT_ONLY` 완료 상태다. Gate는 runtime production `GO / 18 of 18`, expected-answer `NO-GO / 15 of 18`, search recovery `P0 / SEARCH_BLIND_CONDITIONAL`, golden shared collateral `NO-GO / 3`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop388): 신규 full375/bounded/N5/golden18 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. Loop387은 `11694019` 단건 search 포함 non-light runtime에서 input/completed/flushed/pending/failed `1/1/1/0/0`, search health `queries=8/degraded=0/unrecovered=0`, publication contract `GO / violations 0`로 row 생산성을 증명했지만, 다른 공식 상세 URL이 존재한다는 이유로 author_bridge 제목의 exact official detail gap이 닫혀 `혼후순결` candidate-only 상태로 남았다. Loop388은 author_bridge title hint별 official detail page title exact match가 없으면 `no_official_url` gap을 유지하도록 `src/llm_batch/experts/orchestrator.py`를 보강했고, 같은 입력 재실행에서 `https://novelpia.com/novel/181771`을 fetch해 `official_title=이세계에서 사이비로 살아남기`, `candidate_ledger_status=safe_resolved`, `publish_allowed=true`, `bypassed_gate=false`로 수렴했다. R1 hardcoded cue 확장은 없다. Gate는 runtime production `GO / 1 of 1`, row-level semantic/search recovery `GO`, broader search recovery `P0 / SEARCH_BLIND_CONDITIONAL`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop385): 신규 full375/bounded/N5 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. Loop384의 postprocess-only 한계를 닫기 위해 current-code golden18 단일 runtime replay만 search 포함 non-light로 실행했다. Run `20260704_045605_759573`은 input/completed/flushed/pending/failed `18/18/18/0/0`, health audit `GO / clean_completed_source`, publication contract `GO / violations 0`로 row 생산성을 증명했다. 그러나 search evidence는 `REVIEW / search_degraded_observed`, unrecovered degraded total `3`이고 runtime expected-answer는 `NO-GO / 15 of 18`이다. 실패는 `11668307`, `11700470`, `11698880`이다. `expert_main.py`는 locked official-detail 후보가 direct source와 search support를 갖고 있으면 URL 없는 title-only gate 후보가 public identity를 덮지 못하게 했고, 이미 wrong public으로 덮인 결과도 locked 경쟁 후보로 재수렴하게 했다. Postprocess projection은 `11698880`을 `가챠 중독자의 퓨전펑크 생활`로 회복해 expected-answer `NO-GO / 16 of 18`, golden shared collateral `NO-GO / 4`로 개선했지만 `runtime_replay_after_patch=NOT_RUN_POSTPROCESS_ONLY`라 approval 근거가 아니다. `11668307`과 `11700470`은 hardcoded alias/cue 없이 unresolved로 유지한다. Gate는 runtime production `GO / 18 of 18`, runtime semantic `NO-GO / 15 of 18`, projection semantic `NO-GO / 16 of 18`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, search recovery `P0 / PARTIAL_RUNTIME_GO / UNRECOVERED_DEGRADED_OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop384): 신규 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. Loop382 golden18 완료 결과를 current-code publication contract 후처리로 다시 동기화했다. `expert_main.py`는 runtime 직렬화 경로에서도 `_sync_allowed_publication_result_contract(..., post_title=post_title)`가 caller post title을 source text로 보게 하며, 이 배선으로 `11663540`의 OCR 오독 `전 버디가 하고 싶은데요`가 runtime-like payload에서도 `전 버튜버가 하고 싶은데요`로 수렴한다. Official postprocess audit는 expected-answer `PASS / 18 of 18`이지만 manifest가 `runtime_replay_after_patch=NOT_RUN_POSTPROCESS_ONLY`라 current-code runtime proof가 아니다. `11663521`은 `expected_work_evidence_preserved_unresolved`로 통과하고 public title은 `null / promotion_blocked`라 forced publish가 아니다. Golden shared collateral은 `NO-GO / 6 regression candidates`, full375 collateral은 `NOT_OPEN`이다. Gate는 code contract `GO_UNIT`, postprocess golden audit `PASS / 18 of 18`, runtime replay `NOT_RUN_POSTPROCESS_ONLY`, collateral active lane `reclassified 74 / runtime-verified 4`, search recovery `P0 / PARTIAL_RUNTIME_GO / FULL_SCAN_NOT_OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop383): 신규 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. Loop382 golden18 실패 2건만 저장 결과에 현재 후처리 계약을 dry 적용했다. `expert_main.py`는 `official_detail_url_missing_direct_source_support`가 붙은 title-only official/detail 후보를 직접 source support 없이 publish 복구하지 않으며, direct image/OCR URL-less title은 검색 공식 제목과 캐릭터 괄호 bridge가 맞을 때 canonical title로 수렴한다. `11663521`은 `성기사는 버생을 산다` wrong publish를 `null / promotion_blocked`로 내렸지만 expected `어떤 마술의 금서목록 / 어떤 과학의 초전자포` positive는 아직 unresolved다. `11663540`은 `전 버디가 하고 싶은데요` OCR 오독을 `전 버튜버가 하고 싶은데요`로 보정한다. Targeted dry audit는 expected-answer projection `NO-GO / 17 of 18`, remaining minimal failure `11663521`이다. Runtime replay는 `NOT_RUN_AFTER_PATCH`라 approval, hard-hold 완화, full375 collateral 승격 근거가 아니다. Gate는 code contract `GO_UNIT`, targeted dry proof `GO_DRY / 2 rows`, golden expected-answer `NO-GO / projected 17 of 18`, golden shared collateral inherited `NO-GO / 7 regressions`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, search recovery `P0 / PARTIAL_RUNTIME_GO / FULL_SCAN_NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop379-382): 신규 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. Loop379/380은 `11698880`에서 middle evidence `가챠펑크/세드릭 -> 가챠 중독자의 퓨전펑크 생활`이 late `batch_memory`/`known_title_abbreviation -> 아카데미 생존 갤러리` rescue로 덮이는 실패를 재현했다. `src/llm_batch/agentic_pipeline.py`는 `batch_memory`, `batch_memory:alias_affix_stripped`, `known_title_abbreviation` rescue가 body-verified character-work competition을 만나면 context-only gate로 수렴하도록 보강했고, `expert_main.py`는 final publication contract가 body-verified competing candidate로 재수렴할 수 있게 했다. Loop381 `11698880` 단건 run `20260704_033149_190416`은 public title/url `null/null`, `promotion_blocked`, publication contract `GO`라 wrong publish는 차단됐지만 expected safe-resolved는 아니다. Loop382 golden18 run `20260704_033413_208076`은 input/completed/flushed/pending/failed `18/18/18/0/0`, health audit `GO / clean_completed_source`, search evidence `GO`, publication contract `GO / violations 0`이다. Expected-answer audit는 `NO-GO / 16 of 18`이고 실패는 `11663521`, `11663540`이다. `11698880`은 evidence-preserved unresolved라 hard-hold 완화 근거가 아니며, golden shared collateral regression 후보는 `7`건이다. Gate는 new large runs `FROZEN`, same parent packet replay `STOPPED`, runtime proof `GO / 18 of 18`, golden expected-answer `NO-GO / 16 of 18`, golden shared collateral `NO-GO / 7 regressions`, full375 collateral `NOT_OPEN`, search recovery `P0 / PARTIAL_RUNTIME_GO / FULL_SCAN_NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop378): 신규 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. Loop377 golden18 실패 `11698880`에서 Verifier `matched_alias=가챠펑크`가 현재 후보 `아카데미 생존 갤러리`의 publish evidence로 재사용되는 경로를 확인했다. `가챠펑크`는 본문 검증 후보 `가챠 중독자의 퓨전펑크 생활`의 표면이므로, 현재 후보와 맞지 않는 verifier alias는 title-led alias public-title gate evidence에서 제외하도록 `src/llm_batch/agentic_pipeline.py`를 보강했다. 새 테스트는 경쟁 본문 검증 후보가 있을 때 `candidate_only`, `publish_allowed=false`, `scope_kind=context_only`가 유지됨을 고정한다. 검증은 focused 3 tests PASS, promotion gate contract 22 PASS, `py_compile` PASS, `git diff --check` PASS다. Post-patch runtime replay는 `NOT_RUN_AFTER_PATCH`라 expected-answer 개선이나 hard-hold 완화 근거로 세지 않는다. Gate는 new large runs `FROZEN`, same parent packet replay `STOPPED`, code contract `GO_UNIT`, targeted runtime `NOT_RUN_AFTER_PATCH`, golden expected-answer `NO-GO / inherited 15 of 18`, golden shared collateral `NO-GO / inherited 7 regressions`, full375 collateral `NOT_OPEN`, search recovery `P0 / PARTIAL_RUNTIME_GO / FULL_SCAN_NOT_OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop372): 신규 대형 런은 계속 동결한다. Loop371 실패 `11663521`만 단건으로 실행했고 run `20260703_224934_380230`은 input/completed/flushed/pending/failed `1/1/1/0/0`, checkpoint/result rows `1/1`, VLM/OCR `READY`로 완료됐다. `expert_main.py`는 URL 없는 title-only `official_detail/page_type=novel_page` candidate support를 public publish 복구 근거로 쓰지 않도록 보강했다. `tools/audit_expert_run_health.py`는 manifest-declared `output_file/checkpoint_jsonl/pending_snapshot` 경로와 completed frontier `next_save_idx=N+1`을 처리한다. Health audit는 `flush_integrity=GO / clean_completed_source`, frontier `complete_after_last_index`, publication contract convergence `GO`, violations `0`, row-level search evidence `GO`, unrecovered degraded `0`을 기록했다. 다만 manifest `mcp_health_light_mode=true` caveat가 남아 전체 search recovery 완료는 아니다. `11663521`은 previous wrong publish `성기사는 버생을 산다`가 public title에서 제거됐고 final은 `null / promotion_blocked / publish_allowed=false / safe_resolved=false`다. 이는 wrong-publish closure이며 golden expected `어떤 마술의 금서목록 / 어떤 과학의 초전자포` pass가 아니다. Gate는 new large runs `FROZEN`, targeted runtime `GO / 1 of 1`, wrong-publish closure `GO_TARGETED`, audit harness `GO_UNIT`, golden expected-answer `NO-GO / inherited 14 of 18`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop366): 신규 대형 런은 계속 동결한다. Loop364 code 보강과 Loop365 expected 교정 뒤 현 HEAD `5fd0ec99`에서 golden18 단일 런만 search 포함 non-light로 재실행했다. Run `20260703_194927_961030`은 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint `18`, result rows `18`, VLM/OCR `READY`, search preflight `2/2 OK`로 완료되어 runtime production은 `GO / 18 of 18`이다. Health audit는 publication contract convergence `GO`, violations `0`을 기록했지만 pending snapshot 부재로 `flush_integrity=NO-GO / artifact_count_mismatch`이며, search evidence는 `REVIEW / search_degraded_observed`, unrecovered degraded total `28`이다. Expected-answer audit는 pass `11/18`, fail `7/18`, `canary_semantic_gate=NO-GO`이고 실패는 `11694035`, `11698897`, `11661857`, `11694019`, `11700470`, `11705231`, `11698880`이다. `11713222` expected correction은 유지됐고 `11660237`은 `테라포밍`으로 통과했지만 단일 런으로 hard-hold 완화를 열지 않는다. Golden shared collateral regression 후보는 `9`건이라 full-panel collateral approval은 `NO-GO`다. Gate는 new large runs `FROZEN`, golden18 runtime `GO / 18 of 18`, golden expected-answer `NO-GO / 11 of 18`, golden shared collateral `NO-GO / 9 regressions`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop365): 신규 대형 런은 계속 동결한다. Loop364 잔여 충돌 `11713222`를 blind/source-native로 재판정했고, 본문 직접 표면 `잘생인방`은 현재 작품 `잘생기면 편해지는 인방 생활`, 댓글의 `잘생인편`은 `전작도 ...` / `안봐서 까먹어버림` 문맥상 이전 작품 `잘생기면 인생이 편하다` mentioned-work로 확정했다. 따라서 Loop364 runtime publish는 정당하며, 코드 변경이나 R1 하드코딩 cue 확장 없이 `out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_manifest.json`의 `11713222` expected를 `잘생기면 편해지는 인방 생활`로 교정했다. 기존 Loop363 golden18 결과를 재감사한 결과 expected-answer pass는 `13/18 -> 14/18`, fail은 `5/18 -> 4/18`이지만 `canary_semantic_gate=NO-GO`는 유지된다. 남은 실패는 `11698897`, `11694019`, `11700470`, `11698880`이다. `11708445` OVERRIDE AUDIT는 Loop319 `ACCEPT / candidate_only_block_is_correct` 완료 산출물로 계속 고정한다. Gate는 golden18 runtime `GO / reused Loop363 18 of 18`, golden expected-answer `NO-GO / 14 of 18`, collateral active lane `REVIEW-LOCKED / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop364): 신규 대형 런은 계속 동결한다. Loop363 golden18 expected-answer 실패 중 wrong-publish 3건만 shared promotion gate 일반 술어로 좁혔다. `src/llm_batch/agentic_pipeline.py`는 직접 경쟁 official 후보 표면과 image/search-only 후보 표면 부재를 context-only scope block으로 전파하고, `expert_main.py`는 URL 없는 verified-alias title-only 복구에 distinct alias bridge를 요구한다. R1 하드코딩 cue 리스트 확장은 하지 않았다. Targeted run `20260703_190831_536951`은 input/completed/flushed/pending/failed `3/3/3/0/0`, checkpoint `3`, result rows `3`으로 완료됐고 publication contract convergence는 `GO`, violations `0`이다. `11694019`, `11700470`은 wrong publish 차단이 확인됐지만 `11713222`는 `잘생기면 편해지는 인방 생활` publish가 유지되어 blind/source-native judge가 필요하다. Search evidence는 `REVIEW / search_degraded_observed`, unrecovered degraded total `6`이다. `11708445` OVERRIDE AUDIT는 Loop319 `ACCEPT / candidate_only_block_is_correct` 완료 산출물로 재고정한다. Gate는 code contract `GO_UNIT`, targeted runtime `GO / 3 of 3`, wrong-publish closure `PARTIAL_GO / 2 of 3`, collateral active lane `REVIEW-LOCKED / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop363): 신규 대형 런은 계속 동결한다. 현 HEAD `b7b85936`에서 golden18 단일 실행만 수행했고 manifest input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint `18`, result rows `18`로 runtime proof는 `GO`다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract convergence `GO`, violation `0`을 기록했다. 그러나 expected-answer audit는 pass `13/18`, fail `5/18`, `canary_semantic_gate=NO-GO`다. 실패 행은 `11698897`, `11694019`, `11700470`, `11713222`, `11698880`이며, 이는 shared promotion gate / 일반 술어 수렴 대상이지 R1 hardcoded cue 확장 대상이 아니다. Search evidence는 `REVIEW / search_degraded_observed`, `unrecovered_degraded_total=19`라서 search recovery는 `P0 / OPEN`이다. `11660237`, `11698880`은 runtime completed지만 public title은 둘 다 `null`이므로 hard-hold 완화를 열지 않는다. Gate는 golden18 runtime `GO / 18 of 18`, golden expected-answer `NO-GO / 13 of 18`, full375 collateral `NOT_OPEN`, new large runs `FROZEN`, collateral active lane `REVIEW-LOCKED / residual_action_queue_rows=105`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override (Loop362): 신규 대형 런은 동결한다. Loop361 golden18 단일 실증은 input/completed/flushed/pending/failed `18/0/0/0/0`, checkpoint `0`이라 Loop360 watchdog-off가 row 생산을 증명하지 못했다. 레거시 `expert_main.py` 프로세스는 정지했고 잔여 프로세스는 `0`이다. Runtime stall guard는 `expert_main.py` CLI `--llm-stream-first-token-timeout`, `--llm-stream-idle-timeout`와 helper 기본 `45/45` 계약으로 보강했지만, golden18 `18/18` 재실증 전까지 approval이나 hard-hold 완화는 금지한다. Collateral current lane은 `reclassified 74 / runtime-verified 4 / residual 105`로 보고하고, survey triage anchor는 `docs/devs/detection_survey_20260626_errors.json`의 `136` errors (`wrong_work_among_aliases=27`, `recall_miss=49`)로 재정렬한다. Gate는 new large runs `FROZEN`, golden18 proof `NO-GO / 0 of 18`, runtime production `NO-GO / checkpoint 0`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

Current status override: collateral183 source-native queue는 `183/183` 완료됐지만 Loop333 review-adjusted collateral regression count가 `126`이라 collateral approval은 `NO-GO`였다. Loop343에서 Loop342 패치 후 동일 alias packet을 현 HEAD `9daf715f`로 재실행해 `11703624`, `11705251` 모두 runtime `safe_resolved`가 됐고, stop-condition evaluator는 actionable queue `126 -> 124`, same packet safe_resolved `0/2 -> 2/2`, gate `GO`를 기록했다. Loop344는 검색 예산 폭주를 줄이고 `presearch` 기본 제외를 적용한 뒤 `11705230` 단건 canary를 완료해 `월야환담 : 신월야` safe_resolved를 확인했다. Loop346은 `tools/split_collateral_action_queue.py --exclude-post-ids`로 닫힌 3건을 current queue에서 재현 가능하게 제외했고 residual artifact를 `123`, `REPROCESS=92`, `HOLD=31`, validation issue `0`으로 고정했다. Loop348은 현 HEAD `462ec714`에서 N5/full375/bounded1200/golden18을 forced non-light background로 다시 발주하고, `11698880`을 primary/secondary scope variance로 `variance_quarantine` 처리해 residual action queue를 `123 -> 122`로 낮췄다. Loop349는 `canonical_title_policy_review` HOLD 2건(`11663535`, `11706871`)을 canonical variant quarantine으로 분리해 residual action queue를 `122 -> 120`, `REPROCESS=92`, `HOLD=28`, validation issue `0`으로 갱신했다. Loop350은 `repair_after_wrong_work=5`를 current HEAD `44de6d74` search 포함 non-light로 발주했지만 초기 LLM/VLM stall로 중단되어 queue delta는 없다. Loop351은 Loop348 background 런 최신 상태가 N5 first `1/0/0/0/0`, full375 `375/1/1/0/0`, bounded1200 `1200/4/0/4/0`, golden18 `18/1/1/0/0`라서 stale flip/golden/full375 근거를 대체하지 않고 대형 런을 background 감시로 내렸다. Collateral 전체는 여전히 `NO-GO / residual_action_queue_rows=120`다. Search-blind promotion blocker는 canary/bounded run에서 `unrecovered_degraded=0`이 입증될 때까지 conditional로 유지한다.

Current status addendum: Loop357은 `known_alias_runtime_replay_required=3`를 동일 stalled replay로 반복하지 않고 contract audit로 전환했다. `괴담텔 ... 괴담동이 생각나네`에서 뒤쪽 comparison alias `괴담동 -> 괴담 동아리`가 current-work anchor로 release되는 실패를 재현했고, comparison-only alias release를 차단했다. 최신 residual action queue는 `105`, queue delta `0`이며, 최신 gate는 code contract `GO_UNIT`, runtime replay `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=105`이다.

## 2026-07-03 Loop357 Known-alias Comparison Boundary

- Loop357은 approval 회차가 아니다. `known_alias_runtime_replay_required=3` lane을 runtime stall 반복 대신 unit contract audit로 전환했다.
- Evidence: report `docs/devs/loop_reports/LOOP_357_REPORT_20260703.md`, state `docs/devs/loop357_known_alias_comparison_boundary_20260703.json`.
- Failure: `괴담텔 이번 전개는 괴담동이 살짝 생각나네`에서 뒤쪽 comparison alias `괴담동 -> 괴담 동아리`가 current-work anchor로 release됐다.
- Code: `src/llm_batch/agentic_pipeline.py`에 `_known_title_abbreviation_alias_is_comparison_only_reference`를 추가했다.
- Tests: `tests/test_known_title_abbreviation_safe_loss_contract.py`에 comparison target negative와 primary alias positive control을 고정했다.
- Gate: code contract `GO_UNIT`, runtime replay `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop356 Current HEAD Background Dispatch

- Loop356은 approval 회차가 아니다. 현 HEAD `4ebe824b`에서 stale flip-rate `0.333`, 2026-06-28 golden `GO`, 과거 full375 근거를 대체할 실행을 새 prefix로 발주했다.
- Evidence: report `docs/devs/loop_reports/LOOP_356_REPORT_20260703.md`, state `docs/devs/loop356_current_head_background_dispatch_20260703.json`.
- Shard audit: `35/44` OK, bad shard `1`, `37-44`. Loop345의 `3369-3376` shard는 이번 current HEAD 발주에서 제외했다.
- Runs: safe-loss N5 PID `120600`, full375 PID `67072`, bounded1200 PID `140096`, golden18 PID `113216`.
- Initial manifests: N5 first health `1/0`, full375 `3/0`, bounded1200 `6/0`, golden18 `2/0`; all `mcp_health_include_search=true`, `mcp_health_light_mode=false`.
- Gate: dispatch `GO_CURRENT_HEAD_BACKGROUND_DISPATCH`, runtime completion `IN_PROGRESS / NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop355 Wrong-work Alias Contract Reinforcement

- Loop355는 approval 회차가 아니다. `repair_after_wrong_work=5` 중 세 행의 빈 계약면을 보강했지만 runtime replay와 queue 감소는 아직 없다.
- Evidence: report `docs/devs/loop_reports/LOOP_355_REPORT_20260703.md`, state `docs/devs/loop355_wrong_work_alias_contract_20260703.json`.
- Code: `src/llm_batch/experts/utils.py` curated alias work cue에 `장면`, `전개`, `최강자`, `강자라인`을 추가했다.
- Contract: `tests/test_known_title_abbreviation_support.py`가 `댓천마 -> 댓글창의 천재 마법사`, `전1시 -> 전지적 1인칭 시점`, `탐재 -> 탐식의 재림`을 alias+work-cue+official detail recall 경로로 확인한다.
- Gate: contract `GO_UNIT_CONTRACT_ONLY`, runtime closure `NOT_RUN_AFTER_PATCH`, queue delta `NO_DELTA`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop354 Current Residual Forced Action Lane

- Loop354는 approval 회차가 아니다. 대형 forced non-light N5/full375/bounded1200/golden18은 background 감시로 두고 active loop를 current residual action lane으로 강제 전환했다.
- Evidence: report `docs/devs/loop_reports/LOOP_354_REPORT_20260703.md`, state `docs/devs/loop354_current_residual_forced_action_lane_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop354_current_residual_forced_action_lane.json`.
- Queue: residual action queue `105`, `REPROCESS=77`, `HOLD=28`, `safe_loss_resolved_to_null=100`, `wrong_work_title_flip=5`, validation issue `0`.
- Next forced lanes: `repair_after_wrong_work=5` source-native/stall-root-cause review 또는 `known_alias_runtime_replay_required=3` contract/runtime replay.
- Gate: forced action lane `GO_QUEUE_RESHAPE_NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop353 11708470 Non-light Row Closure

- Loop353은 approval 회차가 아니다. Loop324 non-light runtime에서 search degraded 없이 `safe_resolved`된 `11708470`만 Loop352 residual queue에서 제외했다.
- Evidence: report `docs/devs/loop_reports/LOOP_353_REPORT_20260703.md`, state `docs/devs/loop353_11708470_nonlight_row_closure_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop353_current_residual_action_queue_after_11708470_nonlight_runtime_closure.json`.
- Queue transition: residual action queue `106 -> 105`, `REPROCESS=78 -> 77`, `HOLD=28`, validation issue `0`, `repair_safe_loss=73 -> 72`.
- Gate: row closure `GO_ROW_NONLIGHT_RUNTIME_NOT_APPROVAL`, packet semantic `NO-GO`, collateral `NO-GO / residual_action_queue_rows=105`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop352 Unsafe Promotion Contract Exclusion

- Loop352는 approval 회차가 아니다. Loop349 current residual `120`에서 Loop300/309 current contract replay로 이미 `promotion_blocked=14/14` 수렴한 `repair_unsafe_promotion=14`를 제외했다.
- Evidence: report `docs/devs/loop_reports/LOOP_352_REPORT_20260703.md`, state `docs/devs/loop352_unsafe_promotion_contract_exclusion_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop352_current_residual_action_queue_after_unsafe_promotion_contract_exclusion.json`.
- Queue transition: residual action queue `120 -> 106`, `REPROCESS=92 -> 78`, `HOLD=28`, validation issue `0`, `repair_unsafe_promotion=14 -> 0`.
- Gate: queue delta `GO_QUEUE_DELTA_NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=106`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop351 Stale Evidence Background Audit

- Loop351은 approval 회차가 아니다. Loop348 forced non-light N5/full375/bounded1200/golden18을 재감사했지만 완료 증거가 부족해 stale flip/golden/full375 근거를 대체하지 않는다.
- HEAD `462ec714..2e1d09b0` diff는 docs only라 runtime code는 동일하지만, 완료 판단은 manifest/result 기준으로만 한다.
- Evidence: report `docs/devs/loop_reports/LOOP_351_REPORT_20260703.md`, state `docs/devs/loop351_stale_evidence_background_audit_20260703.json`.
- Background snapshot: N5 first `1/0/0/0/0`, full375 `375/1/1/0/0`, bounded1200 `1200/4/0/4/0`, golden18 `18/1/1/0/0`. 모두 `NOT_APPROVAL`이다.
- Golden18 files와 bootstrap/golden 도구는 git 추적 중이고, Loop351에서 search recovery probe `tools/run_search_query_expansion_probe.py`를 추적 예외에 추가했다.
- Gate: stale evidence refresh `INCOMPLETE / NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=120`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop350 Repair After Wrong Work Runtime Stall

- Loop350은 approval 회차가 아니다. `repair_after_wrong_work=5` current HEAD runtime closure를 확인하려 했지만, result가 생성되지 않은 runtime stall 회차다.
- Run `20260703_140627_312360`: input `5`, requested/effective parallel `4/4`, health `4/0`, `mcp_health_include_search=true`, `mcp_health_light_mode=false`, VLM/OCR ready.
- Stall evidence: W0 gatekeeper LLM stream start 후 정체, W1/W2/W3 VLM chunk request 후 정체, manifest completed/flushed/pending/failed `0/0/0/0`.
- Artifacts: `docs/devs/loop_reports/LOOP_350_REPORT_20260703.md`, `docs/devs/loop350_repair_after_wrong_work_runtime_stall_20260703.json`.
- Gate: runtime health `GO_SEARCH_NONLIGHT_HEALTH`, targeted completion `ABORTED_RUNTIME_STALL / NOT_APPROVAL`, queue delta `NO_DELTA`, collateral `NO-GO / residual_action_queue_rows=120`, search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop349 Canonical Variant HOLD Quarantine

- Loop349는 approval 회차가 아니다. Loop348 current residual `122` 중 `canonical_title_policy_review` HOLD 2건을 policy quarantine으로 분리한 회차다.
- `11663535`는 Loop82-83과 Loop251에서 public title/url `null`, `promotion_blocked`, `publish_allowed=false`로 고정됐고, 남은 쟁점은 `퇴마록` 계열 canonical variant다.
- `11706871`은 Loop83에서 `파우스트 1` public 승격을 final title/url `null`, `promotion_blocked`로 내렸고, 남은 쟁점은 `파우스트`/`파우스트 1` canonical variant다.
- Queue artifact는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop349_current_residual_action_queue_after_canonical_variant_quarantine.json`이며 residual `120`, `REPROCESS=92`, `HOLD=28`, validation issue `0`이다.
- Artifacts: `docs/devs/loop_reports/LOOP_349_REPORT_20260703.md`, `docs/devs/loop349_canonical_variant_quarantine_20260703.json`.
- Gate: canonical variant quarantine `GO_QUEUE_DELTA_NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=120`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop348 Current HEAD Forced Non-light Dispatch And Variance Quarantine

- Loop348은 approval 회차가 아니다. stale flip/golden/full375 증거를 대체할 current HEAD `462ec714` forced non-light background 런을 발주한 회차다.
- 초기 light-mode 오발주는 중단했고, 새 forced non-light manifest는 모두 `mcp_health_include_search=true`, `mcp_health_light_mode=false`다.
- Runs: safe-loss N5 PID `137688`, full375 PID `16352`, bounded1200 PID `40088`, golden18 PID `138056`.
- `11698880`은 primary title `아생갤`과 secondary comparison work `가챠펑크`가 섞인 variance row라 safe-loss repair 또는 hard-hold 완화 근거로 쓰지 않는다.
- Current residual artifact는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop348_current_residual_action_queue_after_11698880_variance_quarantine.json`이며 residual `122`, `REPROCESS=92`, `HOLD=30`, validation issue `0`이다.
- Artifacts: `docs/devs/loop_reports/LOOP_348_REPORT_20260703.md`, `docs/devs/loop348_current_head_forced_nonlight_dispatch_and_variance_quarantine_20260703.json`.
- Gate: dispatch `GO_FORCED_NONLIGHT_BACKGROUND`, runtime completion `IN_PROGRESS / NOT_APPROVAL`, collateral `NO-GO / residual_action_queue_rows=122`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop346 Current Residual Queue Rebase

- Loop346은 approval 회차가 아니다. Loop340 residual queue `126`에서 Loop343/344 closure `11703624`, `11705230`, `11705251`을 재현 가능하게 제외하는 도구 계약 회차다.
- `tools/split_collateral_action_queue.py`는 `--exclude-post-ids`를 지원하고 generated queue의 `actions` 필드도 다시 읽는다.
- Current residual artifact는 residual `123`, `REPROCESS=92`, `HOLD=31`, validation issue `0`이다.
- Loop345 bounded1200은 관찰 시점 `4/0/4/0`, `IN_PROGRESS / NOT_APPROVAL`이다.
- Artifacts: `docs/devs/loop_reports/LOOP_346_REPORT_20260703.md`, `docs/devs/loop346_current_residual_queue_rebase_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop346_current_residual_action_queue_after_loop343_344_closure.json`.
- Gate: current residual queue rebase `GO_CONTRACT_AND_ARTIFACT`, collateral `NO-GO / residual_action_queue_rows=123`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop344 Search Budget Partial Recovery

- Loop344는 approval 회차가 아니다. 먼저 remaining known-alias 4건 replay를 시도했지만 run `20260703_111621_199545`가 result flush 없이 중단되어 동일 묶음 반복을 멈췄다.
- Search budget patch는 bridge/client/generated compose 기본값을 `max_retries=1`, `max_pages=2`, default engines `google,bing,webcrawler,naver`로 낮췄다. `presearch`는 access denied가 반복되어 모든 검색을 degraded로 만들 수 있어 기본값에서 제외했다.
- Live shard 1 probe `월야환담 노벨피아`는 attempts `2`, pages `1`, degraded `false`, health `ok=1/1`이다.
- Loop344a targeted run `20260703_114207_032135`는 `11705230`을 completed/flushed/pending/failed `1/1/0/0`으로 끝냈고 public contract는 `official_title=월야환담 : 신월야`, URL `null`, `safe_resolved`, publish `true`다.
- Search health는 queries `16`, degraded `11`, unrecovered degraded `7`이라 search recovery는 `P0 / PARTIAL_RUNTIME_GO / UNRECOVERED_DEGRADED_OPEN`이다.
- Artifacts: `docs/devs/loop_reports/LOOP_344_REPORT_20260703.md`, `docs/devs/loop344_search_budget_partial_recovery_20260703.json`, result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop344a_known_alias_11705230_search_budget_result.json`.
- Gate: search budget `GO_UNIT_AND_LIVE_SHARD1`, targeted row `GO_ROW_PUBLIC_CONTRACT`, collateral `NO-GO / residual_action_queue_rows=123`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop343 Post-patch Verified Alias Runtime Replay

- Loop343은 approval 회차가 아니다. Loop342 패치 후 같은 2-row alias packet을 search 포함 non-light 조건으로 다시 실행해 실제 public contract 반영 여부를 확인했다.
- Artifacts: `docs/devs/loop_reports/LOOP_343_REPORT_20260703.md`, `docs/devs/loop343_post_patch_alias_runtime_replay_20260703.json`, result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop343_known_alias_seed_post_patch_9daf715f_search_nonlight_result.json`, convergence `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop343_goal_convergence_after_runtime_replay.json`.
- Runtime: run `20260703_093839_730466`, HEAD `9daf715f`, counts `2/2/0/0`, search 포함 non-light, VLM/OCR ready.
- Result: `11703624`는 `판초우의의 마법사`와 Munpia URL로 safe_resolved, `11705251`은 `월야환담 창월야` title-only safe_resolved다.
- Gate: targeted packet convergence `GO / queue 126 -> 124 / safe_resolved 0 -> 2`, collateral `NO-GO / residual_action_queue_rows=124`, search recovery `P0 / OPEN / SEARCH_DEGRADED observed`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop342 Verified Alias Title-only Publication Gate

- Loop342는 approval 회차가 아니다. Loop341 alias seed 2건을 search 포함 non-light targeted runtime으로 확인하고, official URL title mismatch 때문에 막힌 verified alias는 title-only로만 공개하는 shared gate를 추가했다.
- Artifacts: `docs/devs/loop_reports/LOOP_342_REPORT_20260703.md`, `docs/devs/loop342_verified_alias_title_only_publication_20260703.json`, result `out/regression_safe_grounding_20260626_000008_928006_loop01/canary/loop342r2_known_alias_seed_targeted_current_head_71e27ce0_search_nonlight_result.json`.
- Runtime: run `20260703_075717_945280`, counts `2/2/0/0`, search 포함 non-light, VLM/OCR ready.
- Result: `11705251`은 패치 후 preview에서 `월야환담 창월야` title-only safe_resolved로 복구된다. `11703624`는 generic/adjacent evidence 때문에 계속 `promotion_blocked`다.
- Verification: py_compile PASS, focused title-only/publication `4` PASS, comment metadata `48` PASS, known abbreviation bundle `38` PASS, title-led guard `185` PASS, promotion/candidate audit `128` PASS, work-bridge/convergence/flip-rate/always-on bundle `26` PASS.
- Gate: targeted runtime completion `GO`, targeted contract preview `PARTIAL_GO`, collateral `NO-GO / residual_action_queue_rows=126`, search recovery `P0 / OPEN`, promotion blocked `search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop341 Known Alias Safe-loss Contract Seed

- Loop341은 approval 회차가 아니다. Loop340 `known_alias_runtime_replay_required=6` 중 2건을 shared alias/work-cue 계약으로 고정했다.
- Artifacts: `docs/devs/loop_reports/LOOP_341_REPORT_20260703.md`, `docs/devs/loop341_known_alias_safe_loss_contract_20260703.json`.
- Code: `판초법사 -> 판초우의의 마법사`, `창월야 -> 월야환담 창월야`, work cue `게이트/정보통제/경찰력/파워밸런스/서열/강한/강함/강캐/약캐`.
- Deferred rows: `11705230`, `11706827`, `11708443`, `11714907`은 runtime/search recovery 또는 policy review 대상으로 유지한다.
- Verification: py_compile PASS, safe-loss contract `9` PASS, abbreviation support `29` PASS, arbiter curated alias guard `21` PASS.
- Gate: code contract `GO_UNIT`, runtime replay `NOT_RUN_AFTER_PATCH`, collateral `NO-GO / residual_action_queue_rows=126`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop340 Collateral183 Residual Action Queue

- Loop340은 approval 회차가 아니다. Loop332/333 collateral183 근거에서 residual `126`을 실행 가능한 action group으로 나눈 회차다.
- Artifacts: `docs/devs/loop_reports/LOOP_340_REPORT_20260703.md`, `docs/devs/loop340_collateral183_residual_action_queue_20260703.json`, queue `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop340_collateral183_residual_action_queue.json`.
- Result: source rows `183`, residual `126`, labels `REPROCESS=95`, `HOLD=31`, action groups `30`, validation issues `0`.
- Main groups: `repair_safe_loss=76`, `repair_unsafe_promotion=14`, `native_image_or_source_review_required=14`, `known_alias_runtime_replay_required=6`, `repair_after_wrong_work=5`.
- Gate: queue split `GO`, collateral `NO-GO / residual_action_queue_rows=126`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop339 Current HEAD Runtime Dispatch

- Loop339는 approval 회차가 아니다. Loop338 이후 stale current-HEAD 증거를 갱신하기 위해 search 포함 non-light background 런을 발주한 회차다.
- Artifacts: `docs/devs/loop_reports/LOOP_339_REPORT_20260703.md`, `docs/devs/loop339_current_head_runtime_dispatch_20260703.json`.
- Runtime: `mcp-bridge-13..25`를 build/recreate했고 ports `3345..3357` search health preflight는 OK다.
- Active runs: full375 PID `131976` run `20260703_071219_478271`, bounded1200 r2 PID `49024` run `20260703_071356_731873`, golden18 r2 PID `130412` run `20260703_071359_476753`, safe-loss N5 PID `134636`.
- Caveat: 최초 bounded/golden 발주는 expert log run-id를 공유해 증거에서 제외했다. 현재 bounded/golden 증거 대상은 r2 경로뿐이다.
- Gate: all launched runs `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop338 Live Shard Search Recovery Canary

- Loop338 is not an approval loop. It verifies that Loop337 code is actually present in a running shard and then runs a single search-included non-light replay.
- Artifacts: `docs/devs/loop_reports/LOOP_338_REPORT_20260703.md`, `docs/devs/loop338_search_recovery_live_shard1_replay_20260703.json`, audit `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop338_override_11705250_search_recovery_live_shard1_health_audit.json`.
- Runtime: run `20260703_061749_804510`, counts `1/1/1/0/0`, `large_run_complete=true`.
- Row: `official_title=심해의 마법사`, URL `https://m.munpia.com/novel/detail/483667`, `candidate_ledger_status=safe_resolved`, publish allowed.
- Search: direct fallback live and partially recovered, but `SEARCH_DEGRADED` remains with `unrecovered_degraded=13`.
- Gate: live shard apply `GO`, row contract `GO_ROW_PUBLIC_CONTRACT`, search recovery `P0 / PARTIAL_RUNTIME_GO / UNRECOVERED_DEGRADED_OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

## 2026-07-03 Loop337 Search Degraded Recovery Contract

- Loop337 is not an approval loop. It converts search degraded from a single blocker bit into recovered/unrecovered contract fields.
- Root cause evidence: Loop336 showed upstream zero and bridge filter collapse while `/readyz` stayed ok.
- Code paths: `src/llm_batch/mcp_bridge/server.py`, `src/llm_batch/agentic_pipeline.py`, `src/llm_batch/experts/orchestrator.py`, `tools/audit_expert_run_health.py`.
- Verification: py_compile PASS, recovery/direct tests `10` PASS, audit tests `16` PASS.
- Gate: code contract `GO_UNIT`, live shard `NOT_APPLIED_TO_RUNNING_CONTAINERS`, search recovery `P0 / PARTIAL_CODE_ONLY / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`.

This note visualizes the current parser-improvement architecture and the additive architecture now promoted into the active regression-safe grounding goal. The current contract is `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`: architecture integration comes before the next ordinary residual-queue reduction. The goal remains `NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, and `full_scan_approval=false`.

## Source References

## 2026-07-03 Loop335 Consumption Title-lead Alias Repair

- Loop335는 approval 회차가 아니라 Loop334의 `11705250` false negative를 코드 계약으로 수리한 회차다.
- `심해법사 묵혀둔거...`처럼 제목 첫 토큰 약칭 뒤에 작품 소비 cue가 오는 경우를 title-lead alias로 보존한다.
- 새 계약은 semantic no-work 기본 support를 열지 않고, `allow_semantic_no_work=True`와 batch alias verified release context가 함께 성립할 때만 release 가능성을 열도록 검증했다.
- Verification은 py_compile PASS, targeted test PASS, `tests.test_regression_safe_work_bridge_contract` `3` tests PASS, `tests.test_title_lead_search_inferred_guard` `185` tests PASS다.
- Artifacts: `docs/devs/loop_reports/LOOP_335_REPORT_20260703.md`, `docs/devs/loop335_consumption_title_lead_alias_repair_20260703.json`.
- Gate는 code contract `GO_UNIT_AND_BROADER_TITLE_LEAD`, runtime replay `NOT_RUN`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop334 Override Audit 11705250 False Negative

- Loop334는 approval 회차가 아니라 `11705250` current HEAD non-light 결과를 old light/public contract/prior native web judge/live web 근거로 판정한 회차다.
- current HEAD result는 `1/1/0/0` 완료됐지만 `is_relevant=false`, `work_resolution=none`, `official_title=null`, `SEARCH_DEGRADED`다.
- 독립 정답은 `심해의 마법사`이며 official URL은 `https://m.munpia.com/novel/detail/483667`이다.
- Public title/url leak은 없으므로 publication leak gate는 `GO_NO_LEAK`다. 다만 row는 `REPROCESS_FALSE_NEGATIVE`로 relation work-context overblock 수리 큐다.
- Artifacts: `docs/devs/loop_reports/LOOP_334_REPORT_20260703.md`, `docs/devs/loop334_override_audit_11705250_current_head_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop334_override_audit_11705250_current_head_blind_source_review.json`.
- Gate는 override audit `NO-GO / REPROCESS_FALSE_NEGATIVE / SEARCH_DEGRADED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop333 Collateral Gate Accounting

- Loop333은 approval 회차가 아니라 Loop332 source-native summary를 상시 375 collateral gate accounting에 배선한 회차다.
- raw `collateral_regression_count=183`에서 clean review summary의 `exclude_from_regression_count_after_gate_wiring=57`만 차감했고, adjusted collateral regression count는 `126`이다.
- current HEAD golden18은 `NOT_AUDITED_CURRENT_HEAD`이고 runtime complete가 `false`라 golden gate는 `NO-GO`다.
- Artifacts: `docs/devs/loop_reports/LOOP_333_REPORT_20260703.md`, `docs/devs/loop333_collateral_gate_accounting_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop333_always_on_collateral183_adjusted_gate.json`.
- Gate는 always-on `NO-GO`, golden `NO-GO`, collateral `NO-GO / adjusted_regression_count=126`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop332 Collateral183 Combined Action Queue

- Loop332는 approval 회차가 아니라 코드 변경 없는 대형 run 대기 흐름을 active collateral triage로 전환한 회차다.
- `loop291`, `loop300`, `loop321` verdict를 `loop290` batch 기준으로 합산해 `183/183`, validation issue `0`, `ACCEPT=57`, `REPROCESS=95`, `HOLD=31`을 산출했다.
- Artifacts: `docs/devs/loop_reports/LOOP_332_REPORT_20260703.md`, `docs/devs/loop332_collateral183_combined_queue_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop332_collateral183_combined_source_native_queue.json`.
- Gate는 collateral source-native queue `REVIEW-LOCKED / COMPLETE_183_OF_183 / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.

## 2026-07-03 Loop331 Current HEAD Partial Runtime NO-GO Refresh

- Loop331은 approval 회차가 아니라 현 HEAD `c033dd97` evidence refresh다.
- post-patch `11668283`은 `1/1/0/0` 완료됐지만 `official_title=null`, `blocked_official_title=중세`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=adjacent`, `SEARCH_DEGRADED`로 끝났다. Loop328 guard patch runtime 수렴 실패이며, promotion blocked는 `search-blind conditional`이다.
- full375는 `6/1/5/0` of `375`, bounded1200 completed-source는 `14/6/8/0` of `1200`, golden18은 `2/2/0/0` of `18`, safe-loss N5는 `1/15` result, override `11705250`은 result missing이다.
- safe-loss N5 partial은 `11674712` r01만 완료됐고 blind judge expected match가 false/incomplete라 hard-hold 완화가 닫혔다. `11660237`, `11698880`은 current result가 아직 없다.
- Artifacts: `docs/devs/loop_reports/LOOP_331_REPORT_20260703.md`, `docs/devs/loop331_current_head_partial_runtime_no_go_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop331_*_health_audit.json`.
- Gate는 targeted `11668283` `NO-GO`, large/background runs `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop330 Current HEAD Health and Override Audit Transition

- Loop330은 approval 회차가 아니라 Loop329 background run health를 최신 감사하고, 대형 런 대기만 반복되는 흐름을 `OVERRIDE AUDIT(LLM=False->final=True)` 단건 current HEAD non-light 검증으로 전환한 회차다.
- Loop329 최신 snapshot은 post-patch `11668283` `0/0/0/0`, full375 `3/1/2/0`, bounded1200 `7/2/5/0`, golden18 `1/1/0/0`, safe-loss N5 first run `0/0/0/0`이다. 모두 완료 전이라 approval 근거가 아니다.
- post-patch `11668283` health audit는 `search_degraded_detected=7`, `search_upstream_zero=5`를 기록해 search recovery는 계속 `P0 / OPEN`이다.
- old light run `20260702_065642_030743`에서 `LLM=False -> final=True` 후보 `93`건, 이미 검토한 `11708445/11668283` 제외 checkpoint-matched 미검토 후보 `91`건을 확인했다.
- 선택 후보 `11705250 / 심해법사 묵혀둔거 간만에 보니까 ㄹㅇ 맛있네`는 old light에서 `safe_resolved=true`였지만 public contract는 `candidate_only / publish_allowed=false / post_gate_official_title=null`이었다.
- current HEAD non-light 단건 run은 PID `93016`, run `20260703_034549_939485`, health `include_search=true`, `light_mode=false`, `1/1` OK로 발주했다. 결과 JSON은 아직 없고, 검색 단계에서 `search_degraded_detected=6`, `search_upstream_zero=2`가 관측됐다.
- Artifacts: `docs/devs/loop_reports/LOOP_330_REPORT_20260703.md`, `docs/devs/loop330_current_head_health_override_audit_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop330_*_health_audit.json`.
- Gate는 Loop329 runtime `IN_PROGRESS / NOT_APPROVAL`, override audit `11705250` `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD / SEARCH_DEGRADED_OBSERVED`, safe-loss flip `RUNNING_BACKGROUND / NOT_ANALYZED`, golden18 `APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop329 Current HEAD c033dd97 Runtime Dispatch

- Loop329은 Loop328 guard patch 커밋 `c033dd97` 이후 stale Loop314/Loop326 background 프로세스를 중단했다.
- 기존 Loop314/326 산출물은 현 HEAD approval evidence가 아니라 `reference-only / NOT_APPROVAL`이다.
- 새 background run은 post-patch `11668283` PID `75828`, full375 PID `3232`, bounded1200 PID `119924`, golden18 PID `95980`, safe-loss N5 PID `107596`이다.
- post-patch single/full375/bounded/golden18 manifest 모두 `mcp_health_include_search=true`, `mcp_health_light_mode=false`이며 초기 health는 각각 `1/1`, `12/12`, `12/12`, `2/2` OK다.
- N5 plan은 `15` planned runs이며 first marker를 생성했다.
- Artifacts: `docs/devs/loop_reports/LOOP_329_REPORT_20260703.md`, `docs/devs/loop329_current_head_c033dd97_runtime_dispatch_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop329_current_head_c033dd97_runtime_dispatch_review.json`.
- Gate는 launch health `GO_SEARCH_NONLIGHT_INITIAL`, post-patch single/N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop328 Known-abbreviation Exact-title Guard Repair

- Loop328은 `11668283 / 게임 마인드의 중세 현대인 좋았다...` post-patch targeted replay를 완료했다.
- run `20260703_020949_643836`는 `1/1/0/0`, search 포함 non-light였다.
- Runtime은 정답 후보를 회복했지만 final public output은 `official_title=null`, `title_resolution_state=unresolved_matchable`, blocker `weak_source_exact_title_without_official_support_public_title_bridge`였다.
- Guard repair는 `known_abbreviation_title_guard:*` current-work scope, exact title surface, work consumption marker, row work discussion, title/body/search context가 모두 있을 때만 weak-source guard를 면제한다.
- Verification은 py_compile PASS, focused guard `2/2` PASS, existing controls `2/2` PASS, related bundle `33/33` PASS다.
- Artifacts: `docs/devs/loop_reports/LOOP_328_REPORT_20260703.md`, `docs/devs/loop328_known_abbreviation_exact_title_guard_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop328_known_abbreviation_exact_title_guard_review.json`.
- Gate는 code contract `GO_UNIT`, runtime replay `PRE_PATCH_REPRODUCED_OVERBLOCK / NOT_APPROVAL`, post-patch runtime replay `NOT_RUN_AFTER_GUARD_PATCH`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop327 Override Audit Middle-age-modern Alias Repair

- Loop327은 `OVERRIDE AUDIT(LLM=False->final=True)` 확장 중 `11668283 / 게임 마인드의 중세 현대인 좋았다...` false negative를 확인했다.
- 최신 light run `20260702_065642_030743`는 `off_topic / context_only / official_title=null`였고, 과거 독립 run `20260423_170321_250907`는 official detail URL resolved였다.
- Partial current canary는 health `include_search=true`, `light_mode=false`, Gatekeeper `work_discussion`, Discourse `review`였지만 semantic seed guard가 `중세 현대인`을 일반어로 drop했다.
- `중세현대인`, `중세 현대인`, `게임마인드중세`, `게임마인드 중세 현대인`을 shared curated alias registry에 추가하고, `좋았다` 계열 감상 cue를 gate에 추가했다.
- Verification은 py_compile PASS, focused unit `9` PASS, related bundle `62` PASS다.
- Artifacts: `docs/devs/loop_reports/LOOP_327_REPORT_20260703.md`, `docs/devs/loop327_override_audit_middle_age_modern_alias_20260703.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop327_override_audit_middle_age_modern_alias_review.json`.
- Gate는 row contract `GO_UNIT_REPAIR`, runtime replay `NOT_RUN_AFTER_PATCH`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop326 Current HEAD Runtime Dispatch

- Loop326은 Loop325 커밋 `1095d447` 이후 current HEAD 기준 runtime evidence를 새 output 경로로 발주한 회차다.
- 발주: safe-loss N5 PID `73076`, full375 PID `106428`, bounded1200 completed-source PID `34796`, golden18 PID `124704`.
- Initial health: full375/bounded search non-light `12/12` OK, golden18 search non-light `2/2` OK, N5 first marker 생성.
- Artifacts: `docs/devs/loop_reports/LOOP_326_REPORT_20260703.md`, `docs/devs/loop326_current_head_runtime_dispatch_20260703.json`.
- Gate는 launch health `GO_SEARCH_NONLIGHT_INITIAL`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `APPROVAL_NOT_OPEN`, safe-loss N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-03 Loop325 Curated Alias Work-cue Contract

- Loop325는 Loop324 `11708443 / 괴담출근` 회귀를 Pipeline bridge와 Arbiter curated-alias null guard의 작품 담론 cue 불일치로 분해했다.
- `_has_curated_alias_work_discussion_cue`를 추가하고 known-title abbreviation bridge와 Arbiter contextual work anchor가 함께 쓰도록 배선했다.
- `11708443` 독창성/SCP cue와 `11718099` 표지변경 cue를 positive 계약으로 추가했다.
- comparison-only negative `괴담텔 ... 괴담동`은 계속 blocked다.
- Verification은 known-title abbreviation safe-loss contract `8` PASS, Arbiter curated alias guard `21` PASS, py_compile PASS, related work-bridge/title-lead bundle `214` PASS다.
- Artifacts: `docs/devs/loop_reports/LOOP_325_REPORT_20260703.md`, `docs/devs/loop325_curated_alias_work_cue_contract_20260703.json`.
- Gate는 code contract `GO_UNIT_AND_BROADER_214`, runtime replay `NOT_RUN_CURRENT_PATCH`, targeted canary `LOOP324_NO-GO`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop322 Safe-loss Alias Shared Contract

- Loop322는 Loop321 `repair_safe_loss=76` 중 직접 별칭과 작품 소비 cue가 함께 있는 7건을 shared `KNOWN_TITLE_ABBREVIATIONS` 계약으로 올렸다.
- 추가 alias는 `괴담출근`, `절꺾않`, `무마`, `아카엄창`, `성좌안무서움`, `빌환`, `지구온라인`이다.
- known-title abbreviation work cue에 `표절`, `보러감`을 추가했다.
- `주전무`는 실제 packet cue가 강하지만 shared cue 폭을 더 넓혀야 하므로 이번 registry 승격에서 보류했다.
- Verification은 py_compile PASS, safe-loss contract `4` PASS, related alias/arbiter/title-lead bundle `230` PASS, always-on/convergence `12` PASS다.
- Actual packet helper check는 선택 7건 allowed, held `주전무=false`다.
- Artifacts: `docs/devs/loop_reports/LOOP_322_REPORT_20260702.md`, `docs/devs/loop322_safe_loss_alias_contract_20260702.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop322_safe_loss_alias_contract_review.json`.
- Gate는 contract `GO_UNIT_CONTRACT_ONLY`, runtime replay `NOT_RUN`, residual closure `NOT_COUNTED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop321 Safe-loss Source-native Queue Closure

- Loop321은 Loop301 `safe_loss_resolved_to_null` batch의 source-native review를 `119/147`에서 `147/147`로 닫았다.
- Delta 결과는 `REPROCESS=15`, `ACCEPT=9`, `HOLD=4`, validation issues `0`이다.
- 누적 결과는 `REPROCESS=76`, `ACCEPT=42`, `HOLD=29`, unreviewed `0`이다.
- 초기 작업 메모의 `16/8/4` 총계는 원문 packet 재확인 후 `15/9/4`로 정정했다.
- `REPROCESS=76`은 shared gate 또는 targeted runtime replay 전까지 residual closure가 아니다.
- `ACCEPT=42`는 collateral gate wiring 전까지 regression count 제외 후보일 뿐이며 approval이 아니다.
- `HOLD=29`는 native image/OCR/source/scope 확인 전까지 닫지 않는다.
- Artifacts: `docs/devs/loop_reports/LOOP_321_REPORT_20260702.md`, `docs/devs/loop321_safe_loss_source_native_verdicts_delta_28.json`, `docs/devs/loop321_safe_loss_source_native_verdicts_cumulative_147.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop321_safe_loss_source_native_review.json`.
- Gate는 source-native review `REVIEW-LOCKED / COMPLETE_SOURCE_NATIVE_QUEUE`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop320 Safe-loss Source-native Next Slice

- Loop320은 Loop301 `safe_loss_resolved_to_null` batch의 source-native review를 `104/147`에서 `119/147`로 확장했다.
- Delta 결과는 `REPROCESS=8`, `ACCEPT=5`, `HOLD=2`, validation issues `0`이다.
- 누적 결과는 `REPROCESS=61`, `ACCEPT=33`, `HOLD=25`, unreviewed `28`이다.
- `REPROCESS=61`은 shared gate 또는 targeted runtime replay 전까지 residual closure가 아니다.
- `ACCEPT=33`은 collateral gate wiring 전까지 regression count 제외 후보일 뿐이며 approval이 아니다.
- Artifacts: `docs/devs/loop_reports/LOOP_320_REPORT_20260702.md`, `docs/devs/loop320_safe_loss_source_native_verdicts_delta_15.json`, `docs/devs/loop320_safe_loss_source_native_verdicts_cumulative_119.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop320_safe_loss_source_native_review.json`.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop319 OVERRIDE AUDIT 11708445

- Loop319은 코드 변경 없는 대형 run 감시/문서 회차 반복 조건에 따라 ordinary safe-loss reduction 대신 `OVERRIDE AUDIT(LLM=False->final=True)` 행을 검증한 회차다.
- 대상 `11708445`는 source run `20260702_065642_030743`에서 completed로 flush됐다.
- Final public contract는 `official_title=null`, `official_url=null`, `candidate_ledger_status=promotion_blocked`, `promotion_decision.status=candidate_only`, `publish_allowed=false`, `candidate_preserved=true`, `bypassed_gate=false`다.
- Blind/source-native verdict는 `ACCEPT / candidate_only_block_is_correct`다. `제냥꾼` 후보는 보존하지만 public title로 publish하지 않는다.
- Artifacts: `docs/devs/loop_reports/LOOP_319_REPORT_20260702.md`, `docs/devs/loop319_override_audit_11708445_20260702.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop319_override_audit_11708445_review.json`.
- Gate는 override audit `GO_ROW_CONTRACT_ONLY`, runtime source `BACKGROUND_LIGHT_RUN_NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop318 Safe-loss Source-native Next Slice

- Loop318은 Loop301 `safe_loss_resolved_to_null` batch의 source-native review를 `89/147`에서 `104/147`로 확장했다.
- Delta 결과는 `REPROCESS=5`, `ACCEPT=7`, `HOLD=3`, validation issues `0`이다.
- 누적 결과는 `REPROCESS=53`, `ACCEPT=28`, `HOLD=23`, unreviewed `43`이다.
- `REPROCESS=53`은 shared gate 또는 targeted runtime replay 전까지 residual closure가 아니다.
- `11698880`은 `가챠펑크` bridge가 있어도 known variance/secondary comparison control이라 repair나 hard-hold 완화 근거로 세지 않는다.
- Artifacts: `docs/devs/loop_reports/LOOP_318_REPORT_20260702.md`, `docs/devs/loop318_safe_loss_source_native_verdicts_delta_15.json`, `docs/devs/loop318_safe_loss_source_native_verdicts_cumulative_104.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop318_safe_loss_source_native_review.json`.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop317 Safe-loss Source-native Next Slice

- Loop317은 Loop301 `safe_loss_resolved_to_null` batch의 source-native review를 `74/147`에서 `89/147`로 확장했다.
- Delta 결과는 `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`, validation issues `0`이다.
- 누적 결과는 `REPROCESS=48`, `ACCEPT=21`, `HOLD=20`, unreviewed `58`이다.
- `REPROCESS=48`은 shared gate 또는 targeted runtime replay 전까지 residual closure가 아니다.
- Artifacts: `docs/devs/loop_reports/LOOP_317_REPORT_20260702.md`, `docs/devs/loop317_safe_loss_source_native_verdicts_delta_15.json`, `docs/devs/loop317_safe_loss_source_native_verdicts_cumulative_89.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop317_safe_loss_source_native_review.json`.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop316 Safe-loss Source-native Next Slice

- Loop316은 Loop301 `safe_loss_resolved_to_null` batch의 source-native review를 `59/147`에서 `74/147`로 확장했다.
- Delta 결과는 `REPROCESS=7`, `ACCEPT=6`, `HOLD=2`, validation issues `0`이다.
- 누적 결과는 `REPROCESS=41`, `ACCEPT=15`, `HOLD=18`, unreviewed `73`이다.
- `REPROCESS=41`은 shared gate 또는 targeted runtime replay 전까지 residual closure가 아니다.
- Artifacts: `docs/devs/loop_reports/LOOP_316_REPORT_20260702.md`, `docs/devs/loop316_safe_loss_source_native_verdicts_delta_15.json`, `docs/devs/loop316_safe_loss_source_native_verdicts_cumulative_74.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop316_safe_loss_source_native_review.json`.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop315 Character-setting Bridge Contract

- Loop315는 Loop312의 `11669933` `회귀수선전` 후보를 shared work bridge 계약 테스트로 고정한 회차다.
- 원문 cluster는 `중경계`, `서휼`, `해방상제`이며, source-native verdict는 `repair_safe_loss + character_bridge_contract_required`다.
- `회귀수선전`은 전역 alias registry가 아니라 `_has_deliberated_character_setting_work_convergence(...)`와 `_post_discusses_work_as_work(...)` 경유로만 release한다.
- 추가 테스트는 positive bridge, conflicting hidden work negative control, shared predicate ownership contract다.
- Verification은 py_compile PASS, targeted `3` PASS, related promotion/work-bridge bundle `32` PASS다.
- Artifacts: `docs/devs/loop_reports/LOOP_315_REPORT_20260702.md`, `docs/devs/loop315_character_setting_bridge_contract_20260702.json`.
- Gate는 character bridge `GO_UNIT_CONTRACT_ONLY`, runtime replay `NOT_RUN`, residual closure `NOT_COUNTED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop314 Current-HEAD Runtime Dispatch

- Loop314는 Loop313 이후 stale/mixed runtime evidence를 current HEAD `64864278` 경로로 분리한 회차다.
- 기존 Loop288/Loop302 프로세스는 Loop313 이전 코드로 시작됐으므로 approval 근거에서 제외하고 중단했다.
- 새 background run은 safe-loss N5 PID `111032`, full375 PID `75828`, bounded1200 PID `9908`, golden18 PID `43208`이다.
- full375/bounded/golden18/N5 first manifest 모두 `mcp_health_include_search=true`, `mcp_health_light_mode=false`다.
- `tools/run_independent_plan.py`를 추가해 N5 plan runner를 안정화했다.
- Artifacts: `docs/devs/loop_reports/LOOP_314_REPORT_20260702.md`, `docs/devs/loop314_current_head_runtime_dispatch_20260702.json`.
- Gate는 N5 `RUNNING_BACKGROUND / NOT_ANALYZED_CURRENT_HEAD`, golden18 `APPROVAL_NOT_OPEN`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop313 Safe-loss Alias Contract Repair

- Loop313은 Loop312 `repair_safe_loss=34` 중 `악살싶`과 `전독시`를 shared known-title abbreviation 계약으로 올린 `GO_UNIT` 회차다.
- `악살싶` canonical title은 `악당은 살고 싶다`로 정정했고, `전독시`는 `전지적 독자 시점`으로 추가했다.
- `전독시 영화 나왔었지` 같은 adaptation 맥락을 위해 curated alias work-cue에 `영화/극장판/실사화/애니화/드라마화/원작/각색`을 추가했다.
- `악신총애`는 동음 후보 위험 때문에 registry 추가를 보류했고, `회귀수선전`은 Loop313 시점에 character-setting bridge 계약 후보로 남긴 뒤 Loop315에서 shared bridge 계약 테스트로 고정했다.
- Verification은 py_compile PASS, focused alias `3` PASS, promotion/work-bridge `23` PASS, related bundle `266` PASS, Data Analytics validate/render PASS다.
- Artifacts: `docs/devs/loop_reports/LOOP_313_REPORT_20260702.md`, `docs/devs/loop313_safe_loss_alias_contract_repair_20260702.json`.
- Gate는 code/unit contract `GO_UNIT`, runtime replay `NOT_RUN`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED` result `1/15`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop312 Safe-loss Source-native 다음 Slice

- Loop312는 Loop310 이후 남은 `safe_loss_resolved_to_null` 미검토분에서 15건을 추가 판정한 회차다.
- Delta 결과는 `REPROCESS=7`, `ACCEPT=3`, `HOLD=5`다.
- 누적 결과는 `59/147` reviewed, unreviewed `88`, validation issues `0`, labels `REPROCESS=34`, `ACCEPT=9`, `HOLD=16`이다.
- `REPROCESS=34`는 shared gate 또는 targeted runtime replay 전까지 residual closure가 아니며, `HOLD=16`은 native image/web/source/canonical policy 확인 전까지 닫지 않는다.
- Loop311 N5는 아직 result JSON `0/15`라 current HEAD flip-rate 갱신 근거가 아니다.
- Artifacts: `docs/devs/loop_reports/LOOP_312_REPORT_20260702.md`, `docs/devs/loop312_safe_loss_source_native_verdicts_delta_15.json`, `docs/devs/loop312_safe_loss_source_native_verdicts_cumulative_59.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop312_safe_loss_source_native_review.json`.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop311 Current HEAD Runtime Refresh Dispatch

- Loop311은 current HEAD runtime 증거 갱신 회차다. search shard `/api/health`는 `3333/3334` 모두 HTTP 200으로 확인했다.
- safe-loss N5 `15`개 독립 반복 plan을 background runner로 발주했다. PID는 `90532`, 로그는 `logs/loop311_safe_loss_independent_n5_plan/`에 남는다.
- report 시점 N5 result JSON은 `0/15`이므로 flip rate는 아직 갱신되지 않았다.
- Golden18은 rows `18`이며 `11660237`, `11698880`을 포함한다. tracked 상태는 확인됐지만 golden approval은 아직 열지 않는다.
- full375 최신 health는 checkpoint/result `135/105`, pending `30`이고 bounded1200은 `205/188`, pending `17`이다. 둘 다 search 포함 non-light이지만 `IN_PROGRESS/ordered_flush_gap_in_progress`와 blockers `search_timeout_observed`, `search_degraded_observed`가 남았다.
- Artifacts: `docs/devs/loop_reports/LOOP_311_REPORT_20260702.md`, `docs/devs/loop311_current_head_runtime_refresh_20260702.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop311_full375_search_nonlight_current_health_audit.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop311_bounded1200_search_nonlight_current_health_audit.json`.
- Gate는 N5 `RUNNING_BACKGROUND / NOT_ANALYZED`, full375/bounded `IN_PROGRESS / NOT_APPROVAL`, golden18 `TRACKED / APPROVAL_NOT_OPEN`, search recovery `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop310 Safe-loss Source-native 다음 Slice

- Loop310은 Loop306 이후 남은 `safe_loss_resolved_to_null` 미검토분에서 15건을 추가 판정한 회차다.
- Delta 결과는 `REPROCESS=4`, `ACCEPT=2`, `HOLD=9`다.
- 누적 결과는 `44/147` reviewed, unreviewed `103`, validation issues `0`, labels `REPROCESS=27`, `ACCEPT=6`, `HOLD=11`이다.
- `REPROCESS=27`은 shared gate 또는 targeted runtime replay 전까지 residual closure가 아니며, `HOLD=11`은 native image/web/canonical policy 확인 전까지 닫지 않는다.
- Artifacts: `docs/devs/loop_reports/LOOP_310_REPORT_20260702.md`, `docs/devs/loop310_safe_loss_source_native_verdicts_delta_15.json`, `docs/devs/loop310_safe_loss_source_native_verdicts_cumulative_44.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop310_safe_loss_source_native_review.json`.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, runtime replay `NOT_RUNTIME_VERIFIED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop309 백그라운드 전환 및 큐 정합성

- Loop309은 current HEAD evidence를 다시 맞추고, Loop308의 `repair_unsafe_promotion=14` 중복 queue 표기를 정정한 회차다.
- Loop300 current contract replay가 이미 `unsafe_promotion_from_hold=26` 전체를 `26/26` match로 검증했고, `REPROCESS=14`는 `14/14 promotion_blocked`로 수렴했다. 따라서 이 bucket은 새 코드 queue로 다시 등재하지 않는다.
- 최신 background health는 full375 checkpoint/result `129/105`, bounded1200 `190/177`이다. 둘 다 search 포함 non-light이지만 `IN_PROGRESS/ordered_flush_gap_in_progress`이며 blockers `search_timeout_observed`, `search_degraded_observed`가 남았다.
- N5 safe-loss flip gate는 계속 `NO-GO`다. `11674712`와 `11698880`은 flip_rate `0.4`, `11660237`은 stable blind judge confirmed다.
- 다음 actionable queue는 Loop306 기준 `safe_loss_resolved_to_null` 누적 `29/147` reviewed, `118` unreviewed, `repair_safe_loss=23`이다. 대형 run 대기만 반복되면 `OVERRIDE AUDIT(LLM=False->final=True)` blind judge 검증으로 전환한다.
- Artifacts: `docs/devs/loop_reports/LOOP_309_REPORT_20260702.md`, `docs/devs/loop309_background_handoff_20260702.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop309_full375_search_nonlight_current_health_audit.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop309_bounded1200_search_nonlight_current_health_audit.json`.
- Gate는 background full375/bounded `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, promotion blocked interpretation `search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop308 Collateral Unsafe-promotion Triage

- Loop308은 collateral183 P0 `unsafe_promotion_from_hold` bucket을 source-native 기준으로 `26/26` 판정한 회차다.
- 결과는 `ACCEPT=12`, `REPROCESS=14`, validation issues `0`이다.
- Loop309 정정 기준, `REPROCESS=14`는 Loop300 current contract replay에서 이미 `14/14 promotion_blocked`로 수렴했으므로 새 shared promotion gate repair queue로 중복 등재하지 않는다. 다만 search degraded와 run incomplete 때문에 residual closure나 approval은 아니다.
- full375/bounded1200은 각각 `120/105`, `180/167`로 `IN_PROGRESS`이고 blockers `search_timeout_observed`, `search_degraded_observed`가 남았다.
- Artifacts: `docs/devs/loop_reports/LOOP_308_REPORT_20260702.md`, `docs/devs/loop308_unsafe_promotion_from_hold_source_native_verdicts.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop308_unsafe_promotion_from_hold_source_native_review.json`.
- Gate는 collateral triage `REVIEW-LOCKED`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop307 Safe-loss Alias Contract Expansion

- Loop307은 Loop306 source-native alias 후보 일부를 shared known-abbreviation 계약으로 올린 `GO_UNIT` 회차다.
- 추가 alias는 `럽코빙의`, `빚세구`, `마줍`, `여신애호`, `별품소`다.
- `가챠펑크`와 `즉사기`는 search-blind registry release에서 제외했다. 전자는 search/detail evidence 의존 및 nonwork hold 계약, 후자는 무림/게임 속으로 다중작 충돌 때문이다.
- N5 current HEAD 분석은 gate `NO-GO`다. `11674712`와 `11698880`은 flip_rate `0.4`, `11660237`만 stable blind judge confirmed다.
- full375/bounded1200은 각각 `118/105`, `172/167`로 아직 `IN_PROGRESS`이며 search blocker `search_degraded_observed`가 남았다.
- Artifacts: `docs/devs/loop_reports/LOOP_307_REPORT_20260702.md`, `docs/devs/loop307_safe_loss_alias_contract_expansion_20260702.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop307_safe_loss_flip_rate_n5_current_head_review.json`.
- Gate는 code contract `GO_UNIT`, safe-loss flip `NO-GO`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop306 Safe-loss Source-native Next Slice Review

- Loop306은 promotion gate migration의 residual accounting 보조 회차다. code path를 새로 열지 않고, Loop301 `safe_loss_resolved_to_null=147`의 source-native 판정 범위를 `15/147`에서 `29/147`로 넓혔다.
- 누적 결과는 `REPROCESS=23`, `ACCEPT=4`, `HOLD=2`, unreviewed `118`, validation issue `0`이다.
- `REPROCESS`는 shared gate/runtime replay 전까지 residual closure가 아니며, `ACCEPT`는 collateral gate wiring 전까지 regression count 제외 후보일 뿐이다.
- Artifacts: `docs/devs/loop_reports/LOOP_306_REPORT_20260702.md`, `docs/devs/loop306_safe_loss_source_native_verdicts_cumulative_29.json`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop306_safe_loss_source_native_review.*`.
- Gate는 source-native review `REVIEW-LOCKED / PARTIAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop305 Safe-loss Alias Targeted Replay Handoff

- Loop305는 Loop304의 unit-only alias repair를 실제 panel 입력 replay로 넘긴 회차다.
- 입력은 `11`행이며 positive alias seed `7`, comparison-only negative `1`, safe-loss core control `3`으로 구성했다.
- Replay run id는 `20260702_181813_388157`, PID는 `16380`이다.
- 현재 결과는 `completed=0`, `flushed=0`, `failed=0`이라 runtime success나 queue 감소로 세지 않는다.
- Small-run health가 `include_search=false`, `light_mode=true`이므로 search recovery approval 증거가 아니다.
- Gate는 targeted runtime `IN_PROGRESS / NOT_APPROVAL`, search recovery `P0 / OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 2026-07-02 Loop304 Safe-loss Known-Alias Contract Repair

- Loop304는 Loop301 `repair_safe_loss=14` 중 일부를 shared known-abbreviation work-cue 계약으로 전환한 `GO_UNIT` 회차다.
- 추가 alias는 `암흑가보스/암보스`, `기계공주`, `약먹마`, `악살싶`, `마도줍`, `괴담동`, `즉사무림`, `밀리언클래스`다.
- release cue는 직접 작품 소비/평가/작가/공지/표지 표면으로 제한했다. registry 자체는 public publish 권한이 아니며, 기존 `_known_title_abbreviation_update_question_anchor(...)`와 promotion gate를 통과해야 한다.
- Negative control: `괴담텔 ... 괴담동이 살짝 생각나네`는 adjacent 비교라 `괴담 동아리`로 release되지 않는다.
- Verification: py_compile PASS, focused `2` tests PASS, related bundle `217` tests PASS, `git diff --check` PASS.
- Runtime replay는 Loop305에서 발주했지만 아직 `IN_PROGRESS / NOT_APPROVAL`이다. full375/bounded는 background `IN_PROGRESS / NOT_APPROVAL`, search recovery는 `P0 / OPEN`, goal은 `ACTIVE / NOT_COMPLETE`다.
- Artifacts: `docs/devs/loop_reports/LOOP_304_REPORT_20260702.md`, `docs/devs/loop304_safe_loss_alias_contract_repair_20260702.json`.

## 2026-07-02 Loop296 Safe-loss N5 Independent Run Wrapper

- Loop294의 중복 입력 방식은 `post_id` de-dupe로 `N>=5` 증거가 아니었다.
- `tools/safe_loss_flip_rate_probe.py build-run-plan`은 반복마다 단일행 JSONL과 독립 `expert_main.py` command를 생성한다.
- 새 plan manifest는 planned runs `15`, repeat_count_by_post `5/5/5`, missing post_ids `[]`, dedupe guard `one_post_per_process`다.
- 현재 실제 N5 evidence는 Loop288이며 gate는 `NO-GO`다. Loop296은 실행 계획 계약 `GO_UNIT`이고 아직 새 15-run 결과가 아니다.
- Artifacts: `docs/devs/loop_reports/LOOP_296_REPORT_20260702.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop296_safe_loss_independent_n5_run_plan.json`.

## 2026-07-02 Loop293 Final Scope Ordering Contract

- `_has_verified_contextual_alias_work_bridge`는 이미 `_post_discusses_work_as_work(..., source="verified_contextual_alias_work_bridge")`를 경유한다. 이번 회차의 남은 결함은 shared predicate가 아니라 final publication ledger의 scope fallback 순서였다.
- `expert_main.py`는 이제 promotion-blocked 후보에서 `current_work` scope를 먼저 평가하고, 그 다음에 nonpromotable image context의 `context_only` fallback을 평가한다.
- noise/off-topic hard negative는 current scope를 만들지 못하게 보존했다.
- Loop293 runtime은 `11698890` targeted resolved, `11716448` candidate preserved/context_only를 보였지만 두 행 모두 `SEARCH_DEGRADED`라 approval이 아니다.
- Loop294 flip probe는 post_id de-dupe로 `N>=5` 증거가 아니며 무효다. Loop296에서 독립 실행 wrapper를 추가했다.
- Loop295 smoke는 search degraded와 긴 fallback 경로 때문에 `completed=0`에서 중단했으므로 runtime verdict가 없다.
- Artifacts: `docs/devs/loop_reports/LOOP_293_REPORT_20260702.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop293_295_publication_scope_contract_review.json`.

## 2026-07-02 Loop292 Known-Alias Guard Before Promotion Gate

- Loop292는 shared `PromotionDecision` 이후 단계가 아니라, 그 전에 Gatekeeper low-specific guard가 source-native alias search를 지우는 문제를 보강했다.
- `댓천마`, `전1시`, `탐재`는 `KNOWN_TITLE_ABBREVIATIONS`에 추가했지만, registry 자체는 public publish 권한이 아니다. public title은 기존 known-abbreviation work-cue, official URL recall, promotion gate를 통과해야 한다.
- `11698890` pre-fix 로그는 `Gatekeeper continuation-fragment guard`가 `댓천마`/`한별`을 `noise/community_banter`로 내리는 경로를 보여줬다. 이 경로는 search 전에 source-native 후보를 잃게 만든다.
- `11716448`은 `아생갤` alias와 `히로인/괴이/인간/라나` 내부 설정 토론이 결속될 때 known-abbreviation recall work-cue를 통과하도록 계약 테스트를 추가했다.
- Unit contract는 `GO`지만 post-patch 5-row runtime replay는 아직 `NOT_RUN`이다. 따라서 `repair_after_wrong_work` queue 감소와 full collateral approval은 계속 보류한다.
- Artifacts: `docs/devs/loop_reports/LOOP_292_REPORT_20260702.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop292_known_alias_guard_contract_review.json`.

## 2026-07-02 Loop277 Completed Source Candidate Publication Contract Requirement

- `build_completed_source_candidate_audit.py` now requires `publication_contract_convergence_gate=GO` before a source can become an approval source candidate.
- Latest candidate audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop277_completed_source_candidate_publication_contract_audit.md/json`.
- Result: manifest_count `733`, approval_source_candidate_count `0`, clean_vlm_ocr_source_count `429`, clean_vlm_ocr_random_shortfall_count `9`, clean_vlm_ocr_search_health_not_ready_count `420`, clean_vlm_ocr_publication_contract_not_ready_count `0`.
- Interpretation: publication contract is now enforced at candidate selection time. Current approval remains blocked because no clean completed source reaches random target `1000`; this is not semantic approval or full-scan approval.

## 2026-07-02 Loop276 Integrated Health Audit Gate

- `audit_expert_run_health.py` now includes `publication_contract_convergence` as a top-level gate.
- Latest integrated health audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop276_health_audit_with_publication_contract_gate.json`.
- Result: result_rows `164`, checkpoint_rows `208`, publication contract gate `GO`, violation_row_count `0`, but run integrity remains `IN_PROGRESS` and search evidence remains `REVIEW`.
- Interpretation: architecture contract visibility is now part of completed-source health auditing, but approval is still blocked by incomplete source/search evidence gates.

## 2026-07-02 Loop275 Publication Contract Artifact Gate

- `tools/audit_publication_contract_convergence.py` adds an artifact-level gate for `PromotionDecision`, `publish_contract_trace`, `publish_ledger`, and serialized public identity convergence.
- Latest partial flushed result audit: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop275_publication_contract_convergence_audit.md/json`.
- Result: row_count `162`, gate `GO`, violation_row_count `0`.
- Interpretation: this clears publication-contract convergence for audited flushed rows only. It is not completed source, semantic approval, residual decrement, or full-scan approval.

## 2026-07-02 Loop239 11660237 Title-Led Probe Update

- Loop239 did not rerun the same 38-row parent packet.
- It focused on `11660237`, the Loop238 `nondeterminism_unresolved` row.
- The new code lets a title-led current-work gate replace prior `candidate_only/context_only` gate decisions, but only publish-safe current-work evidence can bypass the generic genre bridge demotion.
- Runtime run04 is clean: `20260702_003226_807802`, completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`.
- Semantic result is still `NO-GO`: public title `null`, `candidate_ledger_status=promotion_blocked`, `title_resolution_state=unresolved_matchable`.
- Search preservation worked, but the exact official detail `https://novelpia.com/novel/61947` was not recovered; included-title candidates created wrong-publish pressure and the final publication contract held them.
- Accounting remains `NO_DELTA_TARGETED_CANARY_NO_GO`; `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.
- Artifacts: `docs/devs/loop_reports/LOOP_239_REPORT_20260702.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop239_11660237_title_led_probe_review.md/json`.

## 2026-07-01 Loop237 Parent Replay After Loop236 Update

- Loop237 reran the 38-row parent/representative packet after Loop236.
- Runtime is clean: run `20260701_215903_177630`, completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, MCP health ok/failure `36/0`.
- Parent semantic result is still `NO-GO / MIXED_MOVEMENT`: Loop231 safe/public counts `11->9`, promotion_blocked `25->28`.
- `11663540` proves the architecture gap remains: focused canary restored `전 버튜버가 하고 싶은데요`, but parent replay held it as `promotion_blocked` with public title `null`.
- Safe losses `11660237`, `11674712`, `11698880` require source/native and `publish_contract_trace` comparison before any approval claim.
- Accounting remains `NO_DELTA_PARENT_REPLAY_AFTER_LOOP236_MIXED_MOVEMENT`; `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.
- Artifacts: `docs/devs/loop_reports/LOOP_237_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop237_parent_replay_after_loop236_url_title_direct_support_guard_review.md/json`.

## 2026-07-01 Loop236 URL-Title Direct Support Guard Update

- Loop236 implements the URL-title precondition exposed by Loop235.
- Same-URL page title support is no longer sufficient for public publish; the candidate must also have direct post/OCR/alias support.
- The original Loop236 canary exposed unsafe publish for `두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)` / `https://novelpia.com/novel/427233`.
- The new demotion contract converts that unsafe path to `promotion_blocked` with `official_detail_url_missing_direct_source_support`.
- Loop236b patched canary completed `1/1/0/0`, VLM/OCR `READY`, and published `전 버튜버가 하고 싶은데요` / `https://novelpia.com/novel/275975`.
- Accounting remains no-delta: parent replay is `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
- Artifacts: `docs/devs/loop_reports/LOOP_236_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_review.md/json`.

## 2026-07-01 Loop235 Character-Parenthetical Bridge NO-GO Update

- Loop235 extended the direct-image branch with `search_character_parenthetical_bridge` and `direct_image_work_surface_bridge`.
- Runtime evidence is mixed but not approval: the first run was stopped as incomplete after tool-output pipe loss; Loop235b completed `1/1/0/0`, VLM/OCR `READY`.
- Internal expert decision resolved `전 버튜버가 하고 싶은데요`, but serialized public identity stayed `null`.
- The architecture gap is now sharper: title resolution state can be internally resolved while final publication contract remains candidate-only.
- Loop235b also observed URL-title mismatch for `https://novelpia.com/novel/311328`, so the next architecture layer must require URL-title verified official detail before public publish.
- Accounting remains `NO_DELTA_TARGETED_CANARY_NO_GO`; parent replay is `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
- Artifacts: `docs/devs/loop_reports/LOOP_235_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop235_character_parenthetical_bridge_no_go_review.md/json`.

## 2026-07-01 Loop234 Direct-Image Cover-Title Runtime Canary Update

- Loop234 ran the actual `11663540` focused payload twice after Loop233 exposed the direct-image branch.
- Runtime integrity is clean: both runs completed `1/1/0/0`, VLM/OCR `READY`.
- Public publication is still `NO-GO`: both runs serialized `official_title=null` and `candidate_ledger_status=promotion_blocked`.
- The exact-cover unit contract is now represented by `test_direct_image_exact_cover_title_restores_precision_seed_hold`, but the actual runtime repeated with OCR variance: `전 버튜버가 하고 싶은데요` in run `20260701_202952_860752`, `전 버두바가 하고 싶은데요` in run `20260701_203559_843860`.
- The key architecture gap is no longer simple title detection. Official detail URL, structured image work surface, and character-page bridge can exist while final serializer still applies `precision_seed_official_title_requires_review` and `serialized_public_identity_scrubbed`.
- Next architecture step: converge candidate preservation, `scope_state`, `publish_contract_trace`, and serializer output through a shared `PromotionDecision` re-evaluation state before public title publication.
- Accounting remains `NO_DELTA_TARGETED_CANARY_NO_GO`; parent replay is `NOT_RUN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
- Artifacts: `docs/devs/loop_reports/LOOP_234_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop234_direct_image_cover_title_runtime_canary_review.md/json`.

## 2026-07-01 Loop233 Direct-Image Character Shared Gate Update

- Loop233 implements the first code/test patch from the Loop232 `11663540` branch.
- The final publication ledger restore now recognizes a direct-image character path only when candidate title equals promotion-eligible OCR/work-title evidence and verified character bridge connects to the post-side surface.
- Positive contract: `11663540` style `전 버튜버가 하고 싶은데요` + `주서연` + official detail URL restores to `safe_resolved`.
- Negative contract: wrong-work candidate `방구석 여신이 되었다` remains `promotion_blocked` when OCR title does not match candidate.
- Verification is unit/contract only: focused tests 2 PASS, `tests.test_expert_main_comment_metadata` 26 OK, `tests.test_promotion_gate_contract + tests.test_candidate_audit` 128 OK, `py_compile` PASS.
- Accounting remains `NO_DELTA_UNIT_CONTRACT_ONLY`; targeted canary and parent replay are still `NOT_RUN`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.
- Artifacts: `docs/devs/loop_reports/LOOP_233_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop233_direct_image_character_shared_gate_review.md/json`.

## 2026-07-01 Loop232 Source/Native Variance Update

- Loop232 did not run new code; it decomposed Loop231 focus rows before choosing the next architecture patch.
- `11661876` and `11663540` are the next patch candidates, but both require shared `PromotionDecision` convergence and negative controls.
- `11695637` is not an old-title recovery candidate; keep old `도네하지 마라` restore blocked and retarget lane open.
- `11706832` is not a safe gain for accounting; it reopens the accepted caveated demotion from Loop145.
- `11660237` remains a targeted/parent variance replay target despite official `테라포밍` page confirmation.
- This reinforces the migration rule: official page existence, candidate preservation, and final public-title publish must remain separate states until the authoritative promotion ledger converges.
- Artifacts: `docs/devs/loop_reports/LOOP_232_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_review.md/json`.

## 2026-07-01 Loop231 Parent Replay After Loop230 Update

- Loop231 reran the 38-row parent/representative packet after Loop230.
- Runtime is clean: run `20260701_190002_650661`, completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, MCP health `36/36`.
- `11660257` survived as `암흑가 보스요? 제가요?`, so the title-led serializer/gate path has parent-scope positive evidence.
- The parent semantic result is still `NO-GO / MIXED_MOVEMENT`: Loop225 public title `12` moved to Loop231 public title `11`; safe gain `2`, safe loss `3`, safe identity drift `2`.
- `11660237` is targeted/parent variance because Loop230 held it as `context_only`, while Loop231 publishes `테라포밍`.
- This keeps the migration focus on authoritative promotion-state convergence and safe-loss decomposition, not residual decrement.
- Artifacts: `docs/devs/loop_reports/LOOP_231_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop231_parent_replay_after_loop230_title_led_serializer_gate_review.md/json`.



## 2026-07-01 Loop228 Safe-Loss Source/Native Update

- Loop227 safe-loss 4건은 source/native 검토에서 `likely_overblock=3`, `false_safe_title_retarget_required=1`로 갈렸다.
- `11660237`/`11660257`은 title-led evaluation bridge 후보이고, `11705231`은 character/comment/native seed convergence 재발 후보다.
- `11695637`은 old safe title `도네하지 마라` 복구 금지다. source/native character cluster는 `[림월드]변방계에서 회귀자로 살아남기` retarget lane을 요구한다.
- 이 결과는 architecture migration이 단순 publish restore가 아니라 authoritative promotion state와 retarget/false-safe 분리를 함께 가져야 함을 보여준다.
- Artifacts: `docs/devs/loop_reports/LOOP_228_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop228_loop227_safe_loss_source_native_review.md/json`.

## 2026-07-01 Loop227 Composite Parent Replay Update

- Parent 원 런은 `37/38` partial이므로 단독 runtime approval이 아니다.
- Missing `11698897` 단건 보강으로 composite 38/38 분석은 가능해졌다.
- Loop225 대비 safe gain 4건과 safe loss 4건이 상쇄되어 `NO_DELTA_COMPOSITE_PARENT_REPLAY_MIXED_MOVEMENT`다.
- 이 결과는 final scrub trace 개선만으로 parent semantic movement를 닫을 수 없음을 재확인한다. 다음 architecture work는 upstream authoritative promotion state convergence에 둔다.
- Artifacts: `docs/devs/loop_reports/LOOP_227_REPORT_20260701.md`, `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop227_composite_parent_replay_after_trace_candidate_priority_review.md/json`.
- `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`: active goal contract, work-bridge gate, collateral/golden gates.
- `docs/devs/DETECTION_SURVEY_AND_ROOTCAUSE_20260626.md`: FIX-0/FIX-1/FIX-2~4 root-cause plan.
- `docs/devs/IMPROVEMENT_REGISTER.md`: common `GroundingState` / `PromotionDecision` / `can_publish_title(...)` proposal.
- `docs/devs/VERIFICATION_RESULTS.md`: existing `_post_discusses_work_as_work(...)` first-cut verification.
- `docs/devs/TODO.md`: open item to introduce the common semantic layer before more broad single-post guard accumulation.
- `docs/devs/loop_reports/LOOP_176_REPORT_20260630.md`: latest evidence that the broader unittest gate is now explicitly failing.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop176_broader_unittest_gate_audit.md`: concrete failure clusters that define the first architecture-integrated repair surface.
- `docs/devs/loop_reports/LOOP_179_REPORT_20260630.md`: first shared promotion gate implementation and broader unittest recovery evidence.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_review.md`: Loop179 implementation/review artifact.
- `docs/devs/loop_reports/LOOP_180_REPORT_20260630.md`: first post-architecture residual queue canary.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop180_p1_recall_loss_image_anchor_gate_review.md`: Loop180 residual-return review artifact.
- `docs/devs/loop_reports/LOOP_181_REPORT_20260701.md`: Bridge-only rerun of the Loop180 residual canary.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop181_p1_recall_loss_image_anchor_gate_bridge_health_review.md`: Loop181 runtime-GO / semantic-review artifact.
- `docs/devs/loop_reports/LOOP_182_REPORT_20260701.md`: architecture-integrated parent/representative replay.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop182_parent_representative_after_architecture_review.md`: Loop182 runtime-GO / parent movement review artifact.
- `docs/devs/loop_reports/LOOP_183_REPORT_20260701.md`: source/native review of Loop182 safe gains/losses.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop183_loop182_movement_source_native_review.md`: Loop183 movement review artifact.
- `docs/devs/loop_reports/LOOP_184_REPORT_20260701.md`: targeted follow-up of Loop183 movement rows.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop184_loop183_source_native_followup_review.md`: Loop184 targeted runtime-GO / semantic-review artifact.
- `docs/devs/loop_reports/LOOP_185_REPORT_20260701.md`: exact-alias candidate-hold repair for `11660257`.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop185_11660257_exact_alias_candidate_hold_review.md`: Loop185 candidate-preservation GO / no-delta artifact.
- `docs/devs/loop_reports/LOOP_186_REPORT_20260701.md`: five-row follow-up after Loop185 candidate-hold patch.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop186_loop184_followup_after_candidate_hold_patch_review.md`: Loop186 runtime-GO / semantic-movement no-delta artifact.
- `docs/devs/loop_reports/LOOP_187_REPORT_20260701.md`: nested promotion-gate scrub follow-up after Loop186 collision.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop187_loop186_followup_after_nested_gate_scrub_review.md`: Loop187 runtime-GO / nested scrub unit-GO / semantic-movement no-delta artifact.
- `docs/devs/loop_reports/LOOP_189_REPORT_20260701.md`: packet replay after Loop188 title-led bridge, exposing publish-contract gap.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop189_loop184_followup_after_title_led_bridge_review.md`: Loop189 runtime-GO / packet semantic NO-GO / all-promotion-blocked artifact.
- `docs/devs/loop_reports/LOOP_190_REPORT_20260701.md`: publish-contract trace unit checkpoint after Loop189.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop190_publish_contract_trace_unit_review.md`: Loop190 `GO_UNIT_ONLY` publish trace review artifact.
- `docs/devs/loop_reports/LOOP_191_192_REPORT_20260701.md`: packet replay after publish trace instrumentation and candidate-ledger source fallback.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop192_after_candidate_ledger_trace_source_fix_review.md`: Loop191/192 runtime-GO / trace-coverage-GO / packet semantic NO-GO artifact.
- `docs/devs/loop_reports/LOOP_193_REPORT_20260701.md`: first scope-state promotion gate contract checkpoint.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop193_scope_state_contract_review.md`: Loop193 `GO_UNIT_ONLY` scope-state contract artifact.
- `docs/devs/loop_reports/LOOP_194_REPORT_20260701.md`: scope propagation from promotion gate state into publish-contract trace.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop194_publish_trace_scope_propagation_review.md`: Loop194 `GO_UNIT_ONLY` publish-trace scope propagation artifact.
- `docs/devs/loop_reports/LOOP_195_REPORT_20260701.md`: acknowledged previous-work override path wired through the shared scope gate.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop195_acknowledged_previous_work_scope_gate_review.md`: Loop195 `GO_UNIT_ONLY` previous-work scope gate artifact.
- `docs/devs/loop_reports/LOOP_196_REPORT_20260701.md`: batch-alias public-title path wired through the shared scope gate.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop196_batch_alias_scope_gate_review.md`: Loop196 `GO_UNIT_ONLY` batch-alias scope gate artifact.
- `docs/devs/loop_reports/LOOP_197_REPORT_20260701.md`: direct OCR work-surface lock path wired through the shared scope gate.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop197_direct_ocr_scope_gate_review.md`: Loop197 `GO_UNIT_ONLY` direct OCR scope gate artifact.
- `docs/devs/loop_reports/LOOP_198_199_REPORT_20260701.md`: five-row packet replay after Loop193-197 scope-gate wiring and Loop199 title-led gate recorder.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop199_title_led_gate_packet_replay_review.md`: Loop198/199 runtime-GO / packet semantic NO-GO / final-publication ledger gap artifact.
- `docs/devs/loop_reports/LOOP_200_202_REPORT_20260701.md`: final-publication ledger unification checkpoint after Loop199.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop202_final_publication_ledger_review.md`: Loop202 runtime-GO / final-ledger consistency-GO / residual no-delta artifact.
- `docs/devs/loop_reports/LOOP_203_204_REPORT_20260701.md`: upstream resolved public-title gate checkpoint.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop204_resolved_public_title_gate_review.md`: Loop204 runtime-GO / inferred decisions closed / packet variance open artifact.
- `docs/devs/loop_reports/LOOP_205_208_REPORT_20260701.md`: packet variance scope-block review after Loop203/204.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop205_208_packet_variance_scope_block_review.md`: Loop205-208 runtime-GO / semantic review-lock / residual no-delta artifact.
- `docs/devs/loop_reports/LOOP_209_211_REPORT_20260701.md`: previous-work candidate preservation after Loop205-208.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop211_previous_work_candidate_preservation_review.md`: Loop211 current-work public title preserved / previous-work candidate-only / residual no-delta artifact.
- `docs/devs/loop_reports/LOOP_212_213_REPORT_20260701.md`: title-led unconfirmed-alias guard repeat evidence after Loop209-211.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop212_213_title_led_unconfirmed_alias_bridge_review.md`: Loop212/213 `11669928` repeat-publish / packet variance no-delta artifact.
- `docs/devs/loop_reports/LOOP_214_217_REPORT_20260701.md`: exact-alias image/OCR context trace after Loop212-213.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop214_217_exact_alias_image_context_trace_review.md`: Loop214-217 `11660257` candidate-only reason trace / residual no-delta artifact.
- `docs/devs/loop_reports/LOOP_218_REPORT_20260701.md`: character bridge scope trace after Loop214-217.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop218_character_bridge_scope_trace_review.md`: Loop218 `11674712` recovery plus `11669928` regression / residual no-delta artifact.
- `docs/devs/loop_reports/LOOP_219_REPORT_20260701.md`: shared gate unconfirmed-alias follow-up after Loop218.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop219_shared_gate_unconfirmed_alias_review.md`: Loop219 `11669928` recovery plus `11713222`/`11674712` regression / residual no-delta artifact.
- `docs/devs/loop_reports/LOOP_220_REPORT_20260701.md`: direct body alias probe follow-up after Loop219.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop220_direct_alias_probe_review.md`: Loop220 `11713222` and `11674712` recovery / packet-positive-delta but replay-required artifact.
- `docs/devs/loop_reports/LOOP_221_REPORT_20260701.md`: parent replay after Loop220 direct alias probe.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop221_parent_replay_after_direct_alias_probe_review.md`: Loop221 parent runtime-GO / direct-alias target recovery / mixed movement no-delta artifact.
- `docs/devs/loop_reports/LOOP_222_REPORT_20260701.md`: source/native review of Loop221 safe-loss rows.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop222_loop221_safe_loss_source_native_review.md`: Loop222 six-row safe-loss decomposition / no-delta artifact.
- `docs/devs/loop_reports/LOOP_223_REPORT_20260701.md`: focused publish-contract/title-field patch for `11661876` and `11705231`.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop223_publish_contract_title_field_review.md`: Loop223 focused recovery / parent replay required artifact.
- `docs/devs/loop_reports/LOOP_224_REPORT_20260701.md`: parent replay after Loop223 patch.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop224_parent_replay_after_loop223_title_field_patch_review.md`: Loop224 runtime-GO / semantic mixed movement / no-delta artifact.
- `docs/devs/loop_reports/LOOP_225_REPORT_20260701.md`: envelope title gate fix parent replay after Loop224.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop225_parent_replay_after_envelope_title_gate_fix_review.md`: Loop225 runtime-GO / targeted deterministic recovery / semantic mixed movement / no-delta artifact.
- `docs/devs/loop_reports/LOOP_226_REPORT_20260701.md`: safe-loss trace candidate priority after Loop225 mixed movement.
- `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop226_trace_candidate_priority_review.md`: Loop226 deterministic trace-GO / publish still blocked / residual no-delta artifact.

## Loop226 Safe-Loss Trace Candidate Priority Update

Loop226는 Loop225 safe-loss rows의 trace 품질을 보강했다. final publication ledger sync가 `promotion_blocked` 행에서 `comment_surface`/`hold_without_promotion` 후보를 그대로 pre-gate candidate로 쓰지 않고, 더 강한 `candidate_preservation_sources`, `title_candidates`, `primary_work` 후보를 우선한다.

Deterministic replay result: `11668288` trace candidate becomes `가챠 중독자의 퓨전펑크 생활` / `https://novelpia.com/novel/387014`; `11674712` becomes `이 무림의 미친년은 나야` / `https://novelpia.com/novel/217943?sid=main5`; `11706832` becomes `황제분충`. All three remain `promotion_blocked` with `publish_allowed=false`.

This is a ledger observability and candidate-priority architecture step, not a recall/publish expansion. Current accounting is `NO_DELTA_TRACE_LEDGER_ONLY`; `semantic_quality=REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, and `full_scan_approval=false` remain unchanged.

## Loop225 Envelope Title Gate Fix Update

Loop225 closes one concrete architecture gap: final publication ledger sync now receives the caller post title when the analyzed payload is only the inner `analysis_result`. Deterministic replay of the Loop224 `11661876` payload plus caller post title restores the row to `safe_resolved`.

Runtime is clean: run `20260701_151744_526664`, completed/flushed/pending/failed `38/38/0/0`, image_post_count `24`, VLM/OCR `READY`, MCP health `36/36`, and Data Analytics validate/render passed.

The semantic result is still `NO-GO / MIXED_MOVEMENT`. Loop225 counts are `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`, but Loop224 -> Loop225 changed rows are `21`. The target `11661876` recovers to `와인의 신`; however `11668288`, `11674712`, and `11706832` are safe-loss rows, while `11658615`, `11695637`, and `11705231` are safe identity drift rows.

This confirms that envelope/payload state propagation belongs in the shared publication ledger architecture, but it also confirms that final serialization repair is not enough for approval. Upstream PromotionDecision/GateReport convergence remains required. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop224 Parent Replay After Loop223 Patch Update

Loop224 ran the required parent replay for Loop223b. Runtime is clean: run `20260701_141454_629022`, completed/flushed/pending/failed `38/38/0/0`, image_post_count `24`, VLM/OCR `READY`, MCP health `36/36`, and runtime audit `GO` with issues `[]`. Data Analytics validate/render passed.

The semantic result is `NO-GO / MIXED_MOVEMENT`. Loop224 counts are `safe_resolved=10`, `promotion_blocked=26`, `hold_without_candidates=1`, `output_consistency_lint=1`. `11705231` survives as `탐식의 재림`, but `11661876` fails parent survival and returns to `promotion_blocked`. `11698880` regresses from the stable `가챠 중독자의 퓨전펑크 생활` result to candidate-only under `platform_meta_nonwork`.

This is the current architecture pressure point: final scrub restore is not enough when upstream `title_resolution_state`, `work_resolution`, `scope_state`, and `publish_contract_trace` disagree. The next architecture change should make an upstream authoritative promotion decision ledger the source of truth and make final serialization reflect that ledger. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop222 Loop221 Safe-Loss Source/Native Review Update

Loop222 reviewed the six Loop221 safe-loss rows before accepting any residual decrement. It did not run a new canary and did not change production code. Official/native evidence exists for all six, but the row dispositions are not uniform: `likely_overblock=3`, `ambiguous_hold=2`, and `title_field_bug=1`.

The architecture signals are strongest on `11661876` and `11705231`. `11661876` keeps current-work/high, work-discussion, and official detail evidence for `와인의 신`, so final publish-contract scrub is likely overblocking. `11705231` shows a field separation bug: character/entity surface `설지후` is being attached to the official `탐식의 재림` URL instead of preserving `탐식의 재림` as the official title.

Treat Loop222 as source/native decomposition only. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop221 Parent Replay After Direct Alias Probe Update

Loop221 ran the 38-row parent/representative packet after Loop220's direct alias search guard. Runtime is clean: completed/flushed/pending/failed `38/38/0/0`, effective/requested parallel `36/36`, image_post_count `24`, VLM/OCR required scope `READY`, and runtime audit `GO` with issues `[]`. Data Analytics validate/render also passed.

The semantic result is mixed and remains locked. Loop182 `safe_resolved=12,promotion_blocked=24,hold_without_candidates=1,output_consistency_lint=1` moved to Loop221 `safe_resolved=9,promotion_blocked=27,hold_without_candidates=1,output_consistency_lint=1`. `11713222` recovered to `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`, and `11674712` recovered to `이 무림의 미친년은 나야`, but six previous safe rows moved to `promotion_blocked`.

Treat Loop221 as parent replay executed, not approved. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop220 Direct Alias Probe Update

Loop220 adds a search-side architecture guard for direct worklike aliases in non-comment post text. `orchestrator.py` now collects direct alias probe norms from Gatekeeper/discourse/search request context, keeps those official/community/author/abbreviation queries through semantic no-work pruning, boosts them in search rerank, and defers broad official-hit early stop while an unprocessed direct alias probe remains.

Runtime is clean: completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, and runtime audit `GO` with issues `[]`. Verification is also clean: `py_compile` PASS, focused direct-alias test PASS, title-lead inferred guard suite `157 OK`, expert metadata + promotion bundle `39 OK`, candidate-audit `102 OK`, full unittest discover `1332 OK`, and Data Analytics validate/render PASS.

The semantic result is packet-positive but still replay-required. Loop219 `safe_resolved=1,promotion_blocked=4` improved to Loop220 `safe_resolved=3,promotion_blocked=2`: `11713222` recovered to `잘생기면 편해지는 인방 생활` with `https://novelpia.com/novel/384016`, `11674712` recovered to `이 무림의 미친년은 나야` with `https://novelpia.com/novel/217943?sid=main5`, and `11669928` stayed safe. Treat Loop220 as packet-local positive delta only. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, `semantic_quality=REVIEW-LOCKED`, and `full_scan_approval=false`.

## Loop219 Shared Gate Unconfirmed-Alias Update

Loop219 repairs the immediate `11669928` candidate-audit demotion exposed by Loop218. `candidate_audit.py` now exempts `unconfirmed_alias_official_detail_bridge` only when the shared promotion gate already recorded a publishable current-work decision with official-detail URL support, matching title/URL evidence, and no hard context-only or conflict flags.

Runtime is clean: completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, and runtime audit `GO` with issues `[]`. Verification is also clean: `py_compile` PASS, focused candidate-audit tests `4 OK`, full candidate-audit `102 OK`, expert metadata + promotion bundle `39 OK`, full unittest discover `1331 OK`, and Data Analytics validate/render PASS.

The semantic result is still no-delta. `11669928` recovers to `safe_resolved` with `탑의 성좌들이 날 애호한다` and `https://novelpia.com/novel/377032`, but `11713222` and `11674712` move from `safe_resolved` to `promotion_blocked`. Treat Loop219 as shared-gate unconfirmed-alias evidence only. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, `semantic_quality=REVIEW-LOCKED`, and `full_scan_approval=false`.

## Loop218 Character Bridge Scope Trace Update

Loop218 repairs the immediate `11674712` trace gap exposed by Loop217. The serialized result-contract scrub now recovers official-detail URLs from `search_evidence_catalog` and can infer `scope=current_work` for blocked character-bridge candidates only when official-detail evidence and row context converge without hard context-only flags.

Runtime is clean: completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, and runtime audit `GO` with issues `[]`. Verification is also clean: `py_compile` PASS, focused new tests `2 OK`, expert metadata + promotion bundle `39 OK`, title-led character bridge focused tests `2 OK`, full unittest discover `1329 OK`, and `git diff --check` PASS with CRLF warnings only.

The semantic result is still no-delta. `11674712` recovers to `safe_resolved` with `이 무림의 미친년은 나야` and `https://novelpia.com/novel/217943`, but `11669928` moves from `safe_resolved` to `promotion_blocked` under `unconfirmed_alias_official_detail_bridge`. Treat Loop218 as character-bridge trace evidence only. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, `semantic_quality=REVIEW-LOCKED`, and `full_scan_approval=false`.

## Loop179 Implementation Update

Loop179 promoted the design from documentation into the first shared layer:

- `src/llm_batch/promotion_gate.py` now defines the shared `GroundingState`, `EvidenceRecord`, `PromotionDecision`, `GateReport`, and `can_publish_title(...)` contract.
- Selected high-risk public-title publish paths in `src/llm_batch/agentic_pipeline.py` now route through the shared gate or preserve the gate decision on `final_decision`.
- `src/llm_batch/candidate_audit.py` treats `promotion_decision.publish_allowed=false` as `promotion_blocked`, preserving candidate evidence without leaking into `safe_resolved`.
- `tests/test_promotion_gate_contract.py` adds contract coverage for decision status, reason codes, candidate preservation, and `bypassed_gate=false`.
- Loop179 authoritative broader unittest result: `1299` tests, `0` failures, `0` errors, `OK`.

This update clears the architecture-phase unittest blocker only. The active goal remains `NOT_COMPLETE`, with `semantic_quality=REVIEW-LOCKED`, source full completion `OPEN`, full-panel collateral approval `NO-GO`, and `full_scan_approval=false`.

## Loop180 Residual Return Update

Loop180 applied the shared-gate architecture to the next residual P1 `image_anchor_gate` canary. Manifest completion is clean by counts (`9/9/0/0`, `large_run_complete=true`, VLM/OCR `READY`), but the strict runtime contract audit is `REVIEW` because search health was included in a small reuse-only run. The row ledger split is `safe_resolved=5` and `promotion_blocked=4`.

This is useful architecture evidence: candidates can be preserved while public `official_title` promotion is blocked. It is not residual accounting closure. Current accounting remains full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop181 Bridge-Only Runtime Update

Loop181 reran the same 9-row P1 `image_anchor_gate` canary with Bridge-only small-run health. This removes the Loop180 strict runtime caveat: manifest completion is `9/9/0/0`, `large_run_complete=true`, VLM/OCR `READY`, `mcp_health_include_search=false`, MCP health `2/2`, and runtime audit `GO` with issues `[]`.

The semantic gate remains locked. Loop181 produced `safe_resolved=6`, `promotion_blocked=3`, but `6/9` rows moved versus Loop180 and degraded search counters increased `57 -> 67`. Treat Loop181 as runtime evidence only, not residual accounting closure. Current accounting remains full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop182 Parent Replay Update

Loop182 applied the architecture-integrated code to the 38-row parent/representative packet used by Loop169. Runtime is clean: manifest completion `38/38/0/0`, `large_run_complete=true`, VLM/OCR `READY`, search-included MCP health `36/36`, and runtime audit `GO` with issues `[]`.

The semantic gate remains locked. Loop182 produced `safe_resolved=12`, `promotion_blocked=24`, `hold_without_candidates=1`, `output_consistency_lint=1`. Versus Loop169, `22/38` rows moved, including `promotion_blocked -> safe_resolved` 2 rows and `safe_resolved -> promotion_blocked` 3 rows; degraded search counters increased `166 -> 178`. Treat Loop182 as architecture-integrated parent runtime evidence only, not residual accounting closure. Current accounting remains full reviewed residual ledger `136`, quarantine/human_review `5`, next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop183 Source/Native Review Update

Loop183 reviewed the five Loop182 safe gain/loss movement rows before accepting any closure. It confirmed official/source existence and row-bridge shape for safe gains `11669928`, `11695623` and safe losses `11660257`, `11674712`, `11713222`.

The result is still review-only:

- `11660257`: likely recall regression where exact title alias `암흑가보스` lost to generic/platform-title drift.
- `11713222`: direct-body current-work alias `잘생인방` competes with comment previous-work alias `잘생인편`.
- `11695623`: new safe gain that should be repeated with VLM/OCR on before counting.
- `11669928` and `11674712`: keep as variance-attention controls.

Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. Semantic quality remains `REVIEW-LOCKED`; full scan approval remains `false`.

## Loop184 Targeted Follow-up Update

Loop184 reran the five Loop183 follow-up rows with VLM/OCR on, `--slang-db off`, and Bridge-only small-run health. Runtime is clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, MCP health `2/2`, and runtime audit `GO` with issues `[]`.

The semantic gate remains locked. Loop184 produced `safe_resolved=4` and `promotion_blocked=1`, but `11660257` still fails exact-alias recall, `11713222` publishes the previous-work candidate while retaining the current-work candidate, and `11674712` remains a character-bridge variance row. Treat Loop184 as targeted evidence only, not residual accounting closure. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop185 Exact-Alias Candidate-Hold Update

Loop185 patched the `11660257` failure mode without changing the public-promotion gate. The architecture now skips platform/listing/structural official alias candidates such as generic `노벨피아` surfaces and preserves blocked `search_evidence_alias_inference` candidates as hold-only candidate evidence.

The targeted canary is clean: completed/flushed/pending/failed `1/1/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `1/1`, and runtime audit `GO` with issues `[]`. The result keeps public `official_title=null` and `candidate_ledger_status=promotion_blocked`, while candidate preservation now records `암흑가 보스요? 제가요?` with `https://novelpia.com/novel/384111` and `promotion_policy=hold_without_promotion`.

Treat Loop185 as candidate-preservation evidence only. It is not residual accounting closure, source full completion, full-panel collateral approval, or full-scan approval. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop186 Collateral Follow-up Update

Loop186 reran the Loop184 five-row follow-up packet after the Loop185 patch. Runtime is clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, and runtime audit `GO` with issues `[]`.

The architecture result is mixed. `11660257` no longer preserves generic `노벨피아`; it keeps `암흑가 보스요? 제가요?` as a `hold_without_promotion` candidate with public title blocked. But the packet also moved from Loop184 `safe_resolved=4`, `promotion_blocked=1` to Loop186 `safe_resolved=2`, `promotion_blocked=3`. `11695623` becomes promotion-blocked under image/OCR and recommendation-context guards, and `11713222` retains a title value while reporting `candidate_ledger_status=promotion_blocked`.

Treat Loop186 as collateral follow-up review only. It confirms the candidate-hold repair surface but does not reduce residual accounting or unlock parent/full-panel/full-scan approval. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop187 Nested Scrub Follow-up Update

Loop187 repaired a serialization boundary exposed by Loop186. If `promotion_decision.publish_allowed=false` or the ledger marks the row `promotion_blocked`, nested `novel_identity` fields must not continue publishing `official_title` or public URL values. Focused verification passed via `py_compile` and a 10-test promotion-gate/result-contract bundle.

The runtime follow-up is clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, and runtime audit `GO` with issues `[]`.

The semantic result is still mixed. `11660257` keeps candidate-hold stability, `11695623` stays blocked, `11713222` returns to safe-resolved instead of reproducing Loop186's collision, and `11669928` newly moves to promotion-blocked. Treat Loop187 as nested scrub unit evidence only. It does not reduce residual accounting or unlock parent/full-panel/full-scan approval. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop189 Publish-Contract Gap Update

Loop188 recovered `11669928` with a targeted `title_led_consumption_bridge`, but Loop189 showed the single-row recovery does not survive packet replay. Loop189 reran the five-row Loop184 packet and runtime remained clean: completed/flushed/pending/failed `5/5/0/0`, `large_run_complete=true`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, and runtime audit `GO` with issues `[]`.

The semantic result is a hard packet `NO-GO`: `safe_resolved=0`, `promotion_blocked=5`, public title count `0`. The important observation is not just stricter promotion. Candidate evidence is still present in the packet rows, but final serialized public identity blocks all titles. For example, candidate fields preserve `탑의 성좌들이 날 애호한다`, `이 무림의 미친년은 나야`, `[림월드]변방계에서 회귀자로 살아남기`, and `잘생기면 편해지는 인방 생활`, while final public fields remain null.

This adds a second architecture requirement on top of the existing shared promotion gate:

- add a row-level publish trace: `pre_gate_candidate`, `gate_decision`, `post_gate_identity`, `reason_codes`, `bypassed_gate=false`
- split candidate preservation ledger from public publish ledger in artifacts and tests
- make scope explicit before `can_publish_title(...)`: current-work, previous-work, secondary-reference, author-new-work, image/OCR-derived work, and platform-meta/nonwork
- require stable packet replay before residual accounting can decrement

Treat Loop189 as architecture-gap evidence only. It does not reduce residual accounting or unlock source/full-panel/full-scan approval. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`.

## Loop190 Publish-Contract Trace Update

Loop190 implements the first unit-level observability required by the Loop189 gap. `expert_main._scrub_promotion_blocked_result_contract` now records a `publish_contract_trace` when a serialized result is promotion-blocked:

- `pre_gate_candidate`: candidate title/URL before publication is blocked
- `gate_decision`: normalized gate decision with `publish_allowed=false`, `candidate_preserved`, reason codes, and `bypassed_gate=false`
- `post_gate_identity`: public identity after the gate, with public title/URL null
- `reason_codes`: includes `serialized_public_identity_scrubbed`

It also writes `publish_ledger`, splitting `candidate_preservation` from `public_publish`, and mirrors both structures inside `candidate_ledger` for downstream artifact readers.

Verification is unit-only: `py_compile` PASS and focused unittest PASS (`11 tests OK`). This does not close the Loop189 packet semantic gap. Packet replay remains required before residual accounting can change.

## Loop191/192 Publish-Trace Packet Replay Update

Loop191 performed the required packet replay after Loop190 instrumentation. Runtime stayed clean, but the result showed a trace-source gap: `11660257` had a preserved candidate in `candidate_ledger`, while `pre_gate_candidate` was empty.

The follow-up patch makes the serialized result-contract scrub read candidate evidence from `candidate_ledger.candidate_preservation_sources` and string `title_candidates`. Focused verification now has `12 tests OK`.

Loop192 reran the same five-row packet after the patch:

- runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- trace coverage: `5/5`
- pre-gate title rows: `5/5`
- semantic packet: `safe_resolved=0`, `promotion_blocked=5`, public title count `0`

This closes the immediate publish-trace observability gap, but it does not close the packet semantic gate. The architecture now has better diagnostic evidence for why candidates remain candidate-only, especially `11669928` and `11713222`, but residual accounting cannot move until a stable packet/parent/collateral replay is achieved.

## 2026-07-01 Scope-State Delta

The next architecture addition is an explicit scope-state layer before `can_publish_title(...)`. Loop189-192 show that the system can now preserve candidate evidence and trace public-publish blocking, but it still cannot consistently explain whether a candidate is the current work discussed by the row, a previous work mentioned in comments, a secondary reference, an author-new-work context, an image/OCR-derived candidate, or platform/nonwork metadata.

This delta changes the next goal step:

- Stop treating each blocked row as a new isolated rescue condition.
- Classify candidate scope before public title publication.
- Feed scope into `PromotionDecision.reason_codes` and `publish_contract_trace`.
- Keep candidates preserved even when scope blocks public publication.
- Require packet replay before any residual accounting decrement.

Initial scope categories:

- `current_work`: direct title/body/comment/OCR bridge says the row discusses this candidate as the work.
- `previous_work`: candidate appears as acknowledged prior work, older work, or comment-side comparison.
- `secondary_reference`: character, author, recommendation, or discourse reference that is not the row's main work.
- `author_new_work`: evidence points to another/new work by the author rather than the row's target.
- `image_ocr_derived_work`: candidate is primarily from image/OCR and needs explicit row bridge before publish.
- `platform_meta_nonwork`: platform/listing/search UI title or structural metadata, not a work.
- `context_only`: title exists but the row only contains generic reaction, availability, recommendation, or nonwork context.
- `unknown`: insufficient scope evidence; default to candidate-only/HOLD.

Loop193 should start with contract tests for this scope layer, using `11669928`, `11713222`, and `11695623` as generalized fixtures. Do not add post_id/title-specific production branches for those rows.

## Loop193 Scope-State Contract Update

Loop193 adds the first code-level scope contract:

- `src/llm_batch/promotion_gate.py` defines `ScopeState` and the eight initial scope categories.
- `can_publish_title(...)` now emits scope reason codes and blocks public publishing when an explicit non-current-work scope is present.
- `src/llm_batch/agentic_pipeline.py` wires scope-state into `_can_promote_title_after_semantic_no_work`, preserving scope in `_promotion_gate_state`.
- `tests/test_promotion_gate_contract.py` covers:
  - `11669928` as unknown scope / candidate-only
  - `11713222` current-work as publishable
  - `11713222` previous-work as candidate-only
  - `11695623` image/OCR-derived scope as candidate-only

Verification: `py_compile` PASS for `promotion_gate.py` and `agentic_pipeline.py`; focused promotion gate contract suite PASS with `11 tests OK`; Data Analytics artifact validate/render PASS.

This remains `GO_UNIT_ONLY`; packet replay and residual accounting movement are still open.

## Loop194 Publish-Trace Scope Propagation Update

Loop194 carries the scope-state contract through the serialized publish boundary:

- `expert_main._scrub_promotion_blocked_result_contract` now reads `promotion_gate_state.scope` from `identity` or `candidate_ledger`.
- `publish_contract_trace.scope_state` records the blocked candidate's explicit scope.
- `publish_contract_trace.gate_decision.scope` mirrors the same scope payload.
- `publish_contract_trace.reason_codes` is backfilled with scope codes when the upstream decision omitted them.
- Focused result-contract tests now assert `scope_previous_work`, `scope_not_current_work`, and competing-current-work conflict preservation.

Verification: `py_compile` PASS for `expert_main.py`, `promotion_gate.py`, and `agentic_pipeline.py`; focused combined suite PASS with `23 tests OK`; Data Analytics artifact validate/render PASS.

This remains `GO_UNIT_ONLY`; the next acceptance gate is still a packet replay.

## Loop195 Acknowledged Previous-Work Scope Gate Update

Loop195 wires the first remaining high-risk public-title publish path into the shared scope-state gate:

- `_record_public_title_gate_decision(...)` is now a reusable helper, not only a semantic-no-work nested function.
- `acknowledged_previous_work_comment_override` records a `GroundingState` and `ScopeState` before it can replace the public title.
- direct current-work alias versus comment previous-work alias conflicts now use `scope_kind=previous_work`.
- when that gate returns `publish_allowed=false`, the override is cancelled and reason codes are preserved in `_title_null_block_reasons`.

Verification: `py_compile` PASS, focused combined suite PASS with `24 tests OK`, broader unittest discover PASS with `1309 tests OK`, and Data Analytics validate/render PASS.

This remains `GO_UNIT_ONLY`; batch alias rescue and direct OCR/canonical rescue publish paths still need scope-state wiring before the five-row packet replay can be treated as an acceptance gate.

## Loop196 Batch Alias Scope Gate Update

Loop196 wires the next high-risk public-title publish path into the shared scope-state gate:

- `_record_batch_alias_public_title_gate_decision(...)` records a `GroundingState`, `ScopeState`, and `PromotionDecision` for batch-alias public-title output.
- the pipeline remembers the last batch-alias candidate/hit only when a batch-alias branch actually produces public identity output.
- the final identity phase records the gate after demotion and semantic reread logic has settled, so stale demoted candidates do not receive publish traces.
- final candidate ledgers now preserve `promotion_gate_state.scope.scope_kind=current_work` and direct bridge sources such as `batch_alias_candidate_accepted`.

Verification: `py_compile` PASS, promotion-gate focused suite PASS with `13 tests OK`, targeted batch-alias rework PASS with `2 tests OK`, combined promotion/rework PASS with `15 tests OK`, known-title/title-lead suites PASS with `182 tests OK`, broader unittest discover PASS with `1310 tests OK`, and Data Analytics validate/render PASS.

This remains `GO_UNIT_ONLY`; the direct OCR work-surface lock / canonical rescue bypass path still needs scope-state wiring before the five-row packet replay can be treated as an acceptance gate.

## Loop197 Direct OCR Scope Gate Update

Loop197 wires the direct OCR work-surface lock path into the shared scope-state ledger:

- `_record_direct_image_work_surface_gate_decision(...)` records a `GroundingState`, `ScopeState`, and `PromotionDecision` for `direct_image_work_surface_lock` output.
- final candidate ledgers now preserve `promotion_gate_state.scope.scope_kind=current_work` and direct bridge sources such as `direct_image_work_surface_lock` and `ocr_catalog_official_title`.
- the existing direct OCR/canonical rescue bypass fixture still skips stale canonical rescue scanning, but now leaves a reviewable publish decision with `bypassed_gate=false`.

Verification: `py_compile` PASS, direct OCR contract PASS with `1 test OK`, direct OCR integration PASS with `1 test OK`, promotion-gate suite PASS with `14 tests OK`, direct OCR focused bundle PASS with `5 tests OK`, rank OCR/lock suites PASS with `30 tests OK`, expert metadata plus promotion suite PASS with `26 tests OK`, broader unittest discover PASS with `1311 tests OK`, and Data Analytics validate/render PASS.

This remains `GO_UNIT_ONLY`; the next acceptance gate is the five-row packet replay. If that packet exposes a broader canonical rescue path that still bypasses scope-state accounting, stay in architecture mode before decrementing the queue.

## Loop198/199 Packet Replay And Final-Publication Ledger Gap

Loop198 ran the required five-row packet replay after the acknowledged previous-work, batch-alias, and direct OCR scope-gate wiring.

- runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- packet counts: `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`
- exposed gap: `11669928` safe-resolved as `탑의 성좌들이 날 애호한다` without `publish_contract_trace`

Loop199 added `_record_title_led_alias_public_title_gate_decision(...)` and a focused title-led scope-gate contract, then reran the same packet.

- verification: `py_compile` PASS, title-led contract PASS, promotion-gate suite PASS with `15 tests OK`, title-led acceptance test PASS, full unittest discover PASS with `1312 tests OK`
- runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`
- packet counts: `safe_resolved=1`, `promotion_blocked=4`, public title count `1`, trace rows `4`
- Data Analytics artifact: `Loop199 Five-Row Packet Replay Review`, validate/render PASS

This is still packet semantic `NO-GO`. Loop199 shows the next architecture layer cannot be another isolated rescue condition. The final publication ledger must become authoritative:

- `11669928`: `candidate_ledger.promotion_decision.status=publish`, but serialized public identity is blocked/null.
- `11713222`: safe-resolved as `잘생기면 인생이 편하다` without `publish_contract_trace`, while competing `잘생기면 편해지는 인방 생활` evidence remains preserved.

Next architecture requirement: unify `promotion_decision`, `publish_contract_trace.gate_decision`, `publish_ledger.public_publish`, and serialized `novel_identity` so they cannot disagree. No residual queue decrement is allowed until that unification is implemented and the packet/parent replay gates stabilize.

## Loop200-202 Final-Publication Ledger Unification

Loop200-202 added the final publication ledger sync layer around the serialized result contract.

- `_sync_final_publication_ledger_contract(...)` now normalizes blocked and allowed publication outcomes before packet emission.
- blocked outcomes with stale `status=publish` are rewritten to `candidate_only`, `publish_allowed=false`, and matching `publish_contract_trace`, `publish_ledger`, and `promotion_decision` records.
- allowed serialized public titles now receive a matching final ledger trace when upstream gate records are absent, with `scope_state.scope_kind=current_work` inferred from the serialized public identity.
- Loop202 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop202 ledger coverage: trace rows `5/5`, final-ledger consistency `PASS`, missing public traces `0`, stale publish mismatches `0`, inferred publish decisions `2`.

This closes the packet-level final publication ledger mismatch exposed by Loop198/199. It does not close the architecture goal. The two inferred publish decisions prove that some public-title choices are still being finalized too late in the pipeline. The next architecture move is to replace those inferred records with explicit shared promotion-gate decisions upstream, then rerun the packet plus parent/collateral replay before any residual queue decrement.

## Loop203-204 Upstream Resolved Public-Title Gate

Loop203-204 replaced serialization-time safe-publication inference with an upstream shared promotion-gate record.

- `_record_resolved_public_title_gate_decision(...)` records `GroundingState`, `ScopeState(scope_kind=current_work)`, and `PromotionDecision(status=publish)` for already-resolved public titles that reach the final identity path.
- `build_candidate_audit_fields(...)` now preserves existing `candidate_ledger.promotion_gate_state` and `candidate_ledger.promotion_gate_evidence` when it regenerates the ledger.
- Loop204 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop204 ledger coverage: trace rows `5/5`, final-ledger consistency issues `0`, inferred publish decisions `0`.

This closes the packet-level upstream ledger source gap. It does not close semantic approval: Loop203 still showed repeat-run packet movement for `11695623`, `11713222`, and `11669928`. The next architecture move is packet-variance investigation before parent/collateral replay and any residual queue decrement.

## Loop205-208 Packet Variance Scope-Block Review

Loop205-208 performed that packet-variance investigation and added two small architecture hardenings:

- stronger official-detail candidates are preserved as hold-only review evidence before weak comment-only blocked labels;
- resolved public-title gate recording treats hard context-only / unresolved-worklike flags as `candidate_only` scope instead of public publish.

Loop208 also filters `@...` comment mentions from title candidates and restores the character-alias official-detail path for `11674712` when official search and current-work context agree.

- Loop208 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`.
- Loop208 packet result: `safe_resolved=3`, `promotion_blocked=2`, public title count `3`, inferred publish decisions `0`.
- Remaining review-lock: `11713222` publishes through previous-work/comment override flags while competing candidates remain.

This is `GO_PACKET_VARIANCE_REVIEW_ONLY`. Residual accounting remains unchanged: next actionable `131`, P0/P1/P2 `0/61/70`. The next architecture step is to stabilize `11713222` current-work versus previous-work alias precedence before parent/collateral replay or residual decrement.

## Loop209-211 Previous-Work Candidate Preservation

Loop209-211 stabilizes the immediate `11713222` current-work versus previous-work collision:

- current-work public title remains `잘생기면 편해지는 인방 생활` / `https://novelpia.com/novel/384016`;
- previous-work `잘생기면 인생이 편하다` / `https://novelpia.com/novel/300042` is preserved as candidate-only evidence;
- final-title correction no longer uses a verified-current-alias bypass to publish a conflicting previous-work comment candidate.

Loop211 runtime is clean: completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`, Bridge-only MCP health `2/2`, runtime contract `GO`. Verification is also clean: previous-work focused tests `4 OK`, focused architecture bundle `38 OK`, broad architecture bundle `290 OK`, and full unittest discover `1324 OK`.

This is `GO_PACKET_SCOPE_PRECEDENCE_ONLY`. It does not close residual accounting because packet variance remains: `11660257` and `11669928` moved between Loop210 and Loop211. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Loop212-213 Title-Led Unconfirmed-Alias Guard

Loop212-213 closes one specific gap exposed by Loop210-211: `11669928` can have a title-led work-consumption bridge (`탑성좌애호`, `연중`, official evidence) but still be demoted later by `candidate_audit.py` as `unconfirmed_alias_official_detail_bridge`.

The patch keeps the demotion guard, but exempts only the narrow combination of short title-led alias, title/search/body-or-comments context, work consumption/status token, and official evidence title/snippet support. Existing pollution cases still block.

- Loop212 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`; `11669928` publishes, but `11713222` and `11674712` temporarily move to candidate-only.
- Loop213 runtime: `GO`, completed/flushed/pending/failed `5/5/0/0`, VLM/OCR `READY`; `11669928`, `11713222`, and `11674712` publish.
- Verification: `py_compile` PASS, focused candidate-audit tests `3 OK`, `tests.test_candidate_audit` `100 OK`, title-led acceptance test `1 OK`.

This is `GO_TITLE_LED_ALIAS_GUARD_REPEAT_EVIDENCE_ONLY`. It does not close residual accounting because `11660257` remains candidate-only and Loop212 still showed packet movement. Current accounting remains next actionable `131`, P0/P1/P2 `0/61/70`, with `semantic_quality=REVIEW-LOCKED` and `full_scan_approval=false`.

## Current Architecture

The useful part of the current system is the runtime harness: `expert_main.py` already has manifest, checkpoint, pending/flush, shard lifecycle, VLM/OCR readiness, and restart evidence. That should be preserved.

The weak part is title publication. Public title / URL decisions can be influenced by multiple rescue and postprocess paths. Focused fixes can pass a single row and still move another row during parent replay.

```mermaid
flowchart TD
    A["Input post\n(title/body/comments/images/search)"] --> B["expert_main.py runtime harness\nmanifest/checkpoint/flush/shards"]
    B --> C["Experts and enrichers\nDecoder / Verifier / Arbiter / Orchestrator / VLM-OCR"]
    C --> D["agentic_pipeline.py\nalias rescue, weak bridge, batch rescue"]
    C --> E["candidate_audit.py\ncandidate ledger, promotion/demotion guards"]
    D --> F["expert_main.py postprocess\nserialized identity/public URL sync"]
    E --> F
    F --> G["Final public fields\nofficial_title / heretic_url / primary_work"]
    G --> H["Compare/audit tools\nseed movement, residual queue"]

    D -. "multiple local guards" .-> G
    E -. "safe_resolved can publish" .-> G
    F -. "late serialization can leak or scrub" .-> G
```

### Current Failure Shape

```mermaid
sequenceDiagram
    participant Seed as Targeted seed
    participant Guard as Local guard
    participant Parent as Parent replay
    participant Queue as Residual accounting

    Seed->>Guard: Fix one row/path
    Guard-->>Seed: Targeted result looks green
    Seed->>Parent: Broader replay
    Parent-->>Queue: Different row moves or prior HOLD reopens
    Queue-->>Guard: Add another local guard
```

This is the whack-a-mole pattern recorded in the active goal. Loop175 is a compact semantic example: `11668288` has strong official-title existence, but row-level work discussion is unstable, so it must not be forced into a stable positive-control closure. Loop176 turns the architecture pressure into a test gate: `1292` broader unittests ran with `8` failures across acknowledged previous-work override, batch alias rescue, direct OCR lock, community headline collision, and candidate-audit lint clusters.

## Proposed Additive Architecture

The proposed change is not a rewrite. Keep the runtime harness. Add a small semantic/promotion layer that every public-title publishing path must use.

```mermaid
flowchart TD
    A["Input post + existing expert evidence"] --> B["GroundingState"]
    B --> C["ScopeState\ncurrent / previous / secondary / author-new / OCR / platform / context"]
    C --> D["EvidenceRecord[]\nsource snippets, official detail, alias bridge,\nVLM/OCR, decoder anchors, nonwork signals"]
    D --> E["can_publish_title(...)\nshared work-bridge / promotion gate"]
    E --> F["PromotionDecision"]
    F --> G{"publish_allowed?"}
    G -- "yes" --> H["Publish official_title / URL\nwith reason_codes"]
    G -- "no" --> I["Preserve candidate/HOLD/quarantine\nwithout public title"]
    F --> J["GateReport\nruntime / targeted / semantic / full-scan separated"]
    J --> K["golden + collateral + parent replay"]
```

### Intended Interfaces

Names can change to match local style, but the shape should stay stable.

```text
GroundingState
  post_id
  source_title/body/comments
  candidate_title/url
  official_title_exists
  row_discusses_work_as_work
  nonwork_or_context_only_signals

ScopeState
  scope_kind: current_work | previous_work | secondary_reference | author_new_work | image_ocr_derived_work | platform_meta_nonwork | context_only | unknown
  confidence: high | medium | low
  direct_bridge_sources[]
  competing_candidates[]
  conflict_reason_codes[]

EvidenceRecord
  kind
  strength
  source_path_or_snippet
  supports_publish
  reason_code

PromotionDecision
  status: publish | hold | candidate_only | quarantine | reject
  publish_allowed: bool
  official_title
  official_url
  candidate_preserved: bool
  reason_codes[]
  bypassed_gate: bool

GateReport
  run_integrity
  targeted_canary_status
  semantic_quality
  full_scan_approval
  collateral_regression_count
  golden_gate
  next_actionable_queue
```

## Proposed Gate Placement

```mermaid
flowchart LR
    A["agentic_pipeline rescue paths"] --> G["can_publish_title(...)"]
    B["candidate_audit safe_resolved"] --> G
    C["official detail / URL rescue"] --> G
    D["batch alias rescue"] --> G
    E["expert_main postprocess serialization"] --> G
    F["primary_work promotion"] --> G

    G --> H["PromotionDecision"]
    H --> I["public title/url or candidate-only hold"]
    H --> J["contract-testable reason_codes"]
```

The active goal already names the important entrypoints in `GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md` section 7. Before implementation, refresh those symbols with `rg` because line numbers drift.

## Test Shape Before And After

Current tests often assert only the final public title shape. That misses why a row changed.

```mermaid
flowchart TD
    A["Current test"] --> B["Run pipeline or helper"]
    B --> C["Assert official_title == X or None"]
    C --> D["Hard to know which gate allowed/blocked publication"]

    E["Proposed test"] --> F["Build GroundingState/EvidenceRecord"]
    F --> G["Call can_publish_title(...)"]
    G --> H["Assert PromotionDecision.status"]
    H --> I["Assert reason_codes, candidate_preserved,\npublish_allowed, bypassed_gate=false"]
```

Minimum contract scenarios for the first migration:

- `11668288`: official title exists, but row-level work discussion is not stable; decision should be candidate/quarantine, not stable publish.
- `11706832`: caveated alias boundary; direct work-bridge evidence must be required before publish.
- `11658615`: URL/source-shape variance; do not let same-title movement imply approval.
- `11669928` / `11674712`: prior variance quarantine rows; a later safe-resolved movement is evidence, not approval.
- Golden negative controls such as `11694035`: public title publication must stay blocked unless direct work-bridge evidence is present.

## Migration Plan

1. Inventory public-title and URL publication paths.
   - `agentic_pipeline.py`
   - `candidate_audit.py`
   - `expert_main.py` postprocess
   - `arbiter.py`, `verifier.py`, `decoder.py`, `orchestrator.py`
   - compare/audit scripts that turn movement into queue status

2. Extend the shared objects with scope-state fields before broad residual fixes.

3. Reuse `_post_discusses_work_as_work(...)` inside the scope-aware gate. Do not discard the first-cut work-bridge predicate.

4. Add contract tests for scope classification and `bypassed_gate=false`.

5. Wire only the highest-risk 2-3 publishing paths first.

6. Run focused tests and affected-module tests.

7. Run targeted canary, then parent/representative replay or frozen regression controls.

8. Record `GateReport` style evidence in review JSON/MD, loop report, TODO/CHECKLIST/HISTORY/VERIFICATION_RESULTS/IMPROVEMENT_REGISTER.

## Non-Goals

- Do not replace `expert_main.py` runtime/checkpoint/shard machinery.
- Do not add post_id/title-specific production rules.
- Do not treat P0 `0`, queue `0`, or targeted green as semantic approval.
- Do not mark the active goal complete after this migration alone.

## Completion Signal For This Architecture-Integrated Phase

The migration phase can be considered ready to return to the original residual queue only when:

- at least one shared promotion gate exists,
- the selected high-risk publish paths route through it,
- contract tests prove `bypassed_gate=false` for representative rows,
- focused and affected tests pass or failures are explicitly dispositioned,
- Loop176 broader unittest failures are fixed or explicitly dispositioned,
- targeted/parent replay evidence is recorded,
- docs and checklists point back to the latest residual map.

Then the active goal should resume from the latest residual accounting, not restart from scratch.

## 2026-07-01 Loop229 Addendum - Title-Led Evaluation Bridge Gap

Loop229 showed a remaining architecture gap after the shared promotion gate migration started.

- `11660257` can now reach `PromotionDecision.scope.scope_kind=current_work` when a title-led evaluation marker and official detail candidate converge.
- The same row still ends as `candidate_only` because `weak_alias_surface_public_title_bridge` and `serialized_public_identity_scrubbed` remain active.
- `11660237` remains `context_only` because broad recommendation/non-novel force paths win before the title-led evaluation question can become a current-work scope candidate.

Next migration rule:

1. Treat title-led evaluation questions as a distinct scope route before broad recommendation/noise forcing.
2. Make final serialization consume the upstream `PromotionDecision` as the single publish contract instead of re-litigating scope with stale weak-alias scrub flags.
3. Add end-to-end tests that assert final JSON public identity, `publish_contract_trace`, and candidate ledger preservation together.

Gate remains `NO_DELTA_TITLE_LED_BRIDGE_CANARY_NO_GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, and active goal `NOT_COMPLETE`.

## 2026-07-01 Loop230 Addendum - Serializer/Gate Partial Recovery

Loop230 partially closed the Loop229 gap.

- `11660257` now reaches `PromotionDecision.status=publish`, `publish_allowed=true`, `scope_current_work`, and serialized public title `암흑가 보스요? 제가요?`.
- `11660237` remains `candidate_only`, `scope_context_only`, and public title null.
- The restored path is generalized around title-led consumption markers, alias compact keys, official detail evidence, and shared current-work scope. It is not a post_id/title-specific production rule.
- The remaining risk is stability: `11660257` still shows intermediate low-specific/noise force logs before final reread and serializer restore. Parent/representative replay must prove this does not oscillate.

Next migration rule:

1. Keep final serialization, candidate audit, `PromotionDecision`, `publish_contract_trace`, and `publish_ledger` synchronized as one publication contract.
2. Treat `public_title_count=1/2` as partial recovery only.
3. Require parent/representative replay before residual decrement.
4. Keep all reader-facing loop reports and Data Analytics artifacts in Korean, while preserving raw enum/path/command/URL evidence.

Gate remains `NO_DELTA_TITLE_LED_SERIALIZER_CANARY_PARTIAL_RECOVERY_PARENT_REPLAY_REQUIRED`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, and active goal `NOT_COMPLETE`.
Current status override (Loop392): 신규 full375/bounded/N5 대형 런은 계속 동결하고 동일 38-row parent packet replay도 실행하지 않는다. 현 HEAD `e3e71b16`에서 P0 runtime production을 확인하기 위해 golden18 단일 search non-light runtime만 실행했고 run `20260704_073804_410494`는 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, VLM/OCR `READY`, `large_run_complete=true`로 완료됐다. Health audit는 `flush_integrity=GO / clean_completed_source`, search evidence `GO`, publication contract convergence `GO / violations 0`, unrecovered degraded `0`이다. Expected-answer audit는 `NO-GO / 15 of 18`이고 실패는 `11663521`, `11700470`, `11698880`이다. `11660237`은 `테라포밍`으로 통과했지만 N>=5 flip probe를 대체하지 않는다. `11698880`은 Loop391 단건 HOLD와 달리 mixed golden18에서 expected `가챠 중독자의 퓨전펑크 생활` 대신 `아카데미 생존 갤러리`로 오귀속되어 hard-hold 완화 근거가 아니다. Golden shared collateral은 changed `17`, regression candidates `5`, full375 collateral은 `NOT_OPEN`이다. Gate는 runtime production `GO / 18 of 18`, search recovery `GO_GOLDEN18_ONLY / FULL375_NOT_OPEN`, expected-answer `NO-GO / 15 of 18`, golden shared collateral `NO-GO / 5`, full375 collateral `NOT_OPEN`, collateral active lane `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.
Current status override (Loop393): goal은 완료가 아니다. 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. `11700470`은 source-native/web 검증 결과 public title 확정이 아니라 이미지/OCR 장면 단서 HOLD로 교정했고, golden manifest는 `expected_no_public_title=true`가 됐다. `agentic_pipeline.py`는 `image_evidence_catalog` 또는 `post_data.image_enrichment` 자체를 image-driven scope 신호로 보며, 후보 제목/alias가 비이미지 본문/댓글이나 promotion-eligible 이미지 표면에 없으면 `image_scope_missing_candidate_surface`로 public publish를 막는다. Loop392 저장 결과 재감사는 `NO-GO / 15 of 18`이고 `11700470`은 expected HOLD 대비 `unexpected_resolved_title`이다. Runtime replay after patch는 `NOT_RUN_AFTER_PATCH`, code contract는 `GO_UNIT`, full375 collateral은 `NOT_OPEN`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.
Current status override (Loop406): goal은 완료가 아니다. 신규 full375/bounded/N5 대형 런과 동일 38-row parent packet replay는 발주하지 않았다. Current HEAD `7a76d748`에서 golden18 단일 runtime run `20260704_134739_880141`은 artifact 기준 input/completed/flushed/pending/failed `18/18/18/0/0`, checkpoint/result rows `18/18`, `large_run_complete=true`, `ordered_flush_blocked=false`로 완료되어 runtime production은 `GO / 18 of 18`이다. Health audit는 `flush_integrity=GO / clean_completed_source`, publication contract `GO / violations 0`을 확인했다. 단, manifest preflight가 include_search `false`, light_mode `true`였고 `search_degraded_observed`가 있어 search evidence는 `REVIEW`다. Expected-answer audit는 `NO-GO / 16 of 18`이고 실패는 `11705245`, `11694019`다. Golden shared collateral은 changed `7`, regression candidates `3`, full375 collateral은 `NOT_OPEN`이다. Collateral active lane은 계속 `reclassified 74 / runtime-verified 4`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.
