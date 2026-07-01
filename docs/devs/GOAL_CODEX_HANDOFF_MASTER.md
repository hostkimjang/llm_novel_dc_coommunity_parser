# Codex 마스터 핸드오프 — official-url recall gate 후속 fix를 끝까지 자율 실행

이 문서는 Codex가 **사람 개입 없이 끝까지** official-url recall gate 후속 개선(Track A 가드레일 / B precision / C no-work anchor)을 구현·검증·문서화하도록 하는 단일 진입점이다. 중간에 사람에게 묻지 말고, 각 단계의 수용 게이트를 스스로 충족하며 루프를 진행한다. 막히면(인프라 등) 정확한 preflight 실패 + resume 명령을 남기고 다음 가능한 항목으로 넘어간다(approval은 절대 주장하지 않음).

## 0. 지금까지의 상태 (검증 완료 — 다시 하지 말 것)

- **anchor_type literal_error 버그: 수정·런타임 검증됨.** `agentic_pipeline._apply_official_url_recall_promotion`가 `anchor_type="official_url_recall"`(Literal 밖)을 써서 게이트 승격이 전부 깨지던 것을, `matched_clue`→유효 enum 매핑(`_recall_anchor_type`: ocr→image/full_title_surface→title_exact/official_url_in_body→platform/else→title_alias)으로 수정. 재-canary literal_error 0.
- **genre-surface 과승격 가드: 적용·검증됨.** `candidate_audit.GENRE_DESCRIPTOR_SURFACES` + `_is_genre_descriptor_surface()`가 약-anchor(full_title_surface/bracket/page_alias/rare_token)를 장르 표면에서 차단(강-anchor OCR/confirmed-alias/in-body URL은 통과). 회귀 테스트 2건 포함, **`unittest tests.test_candidate_audit tests.test_judge_seed_registry` = 23 OK**.
- **게이트 자체: healthy search에서 작동·precision-safe 확인.** v3(degraded)→v5(healthy): official URL 잔존 23→35, via_gate 3→9(×3), title==expected 12→18. 게이트의 과해소는 0(컨트롤의 과해소는 전부 `via_gate=False`=정상경로=Track B).
- **근본 함정(이미 해소): search 백엔드 degraded.** 원인은 Docker 엔진 정지 + `--reuse-shards-only`가 복구 차단. 복구는 Docker Desktop 엔진 기동 + expert_main 복구 플래그(아래 §2).
- **운영 모델 교체:** `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4` (이전 E4B). 엔드포인트 `http://10.20.0.101:8000`, `--server-type vllm`.

## 1. 따라야 할 스펙 문서 (이 순서로 실행)

1. `docs/devs/GOAL_RECALL_GATE_CANARY_VERIFY.md` — **메인**. §"2026-06-19 3-트랙 진단 + 적용 순서"에 0순위(인프라)~5순위(통합 canary)와 Track A/B/C 정확한 수술지점·조건·테스트핀·충돌순서가 고정돼 있다.
2. `docs/devs/GOAL_RECALL_URL_GATE.md` — 게이트 본체 스펙(Phase A 구현은 완료, Phase A.4/A.5 후속).
3. `docs/devs/FULL_POST_JUDGE_RUNBOOK.md` — 판정 하네스(모델 26B-A4B 반영). 전수 재판정이 필요할 때.
4. `docs/devs/IMPROVEMENT_REGISTER.md` (IMP-20260618-278) / `docs/devs/VERIFICATION_RESULTS.md` — 전체 이력·검증 기록. 매 라운드 갱신.

## 2. 운영 must-know (canary 실행 전 필수)

- **Docker 엔진이 살아 있어야 한다.** `docker info`가 ServerVersion을 반환해야 함. 죽어 있으면(Internal Server Error) Docker Desktop 기동 후 엔진 ready까지 대기(`docker version`의 server 채워질 때까지).
- **샤드 복구가 필요하면 `--reuse-shards-only`를 쓰지 말 것.** 대신 `--auto-up-shards --auto-recreate-shards --allow-goal-shard-lifecycle` 로 expert_main이 docker compose up/recreate 하게 한다.
- **recall canary는 `MCP_HEALTH_INCLUDE_SEARCH=1` 필수.** default(light/reuse)는 bridge-only라 degraded search 샤드가 새어든다. 헬스가 `Search <ms>`를 찍고 16샤드 OK(저레이턴시 ~2s)인지 확인. 29.5s 같은 응답이면 degraded — 결과 신뢰 말 것.
- **healthy canary 명령 템플릿:**
  ```
  MCP_HEALTH_INCLUDE_SEARCH=1 .venv312/Scripts/python.exe expert_main.py --input <jsonl> \
    --server-type vllm --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 \
    --auto-up-shards --auto-recreate-shards --allow-goal-shard-lifecycle --no-dashboard --slang-db off --vlm on --ocr on \
    --parallel 16 -o <out.json>
  ```
- 인터프리터 `.venv312\Scripts\python.exe`. 산출물 `out/`(gitignored). 회귀 시드 `out/recall_gate_canary/recall_recovery_seed.jsonl`, 입력 `out/recall_gate_canary/canary_input_v3.jsonl`(55행), 메타 `v3_meta.json`, 타깃 `track_targets.json`.

## 3. 적용 순서 (충돌 조율됨 — 반드시 이 순서)

### A. search-health 게이트 강화 + degraded 쿼런틴 (저위험, 먼저)
- expert_main 헬스 소비부(`_health_include_search` ~2025-2054, `_mcp_health_required_ok_count`): "응답 여부"가 아니라 **search 레이턴시 floor(예: <8s) + 결과수>0** 기준으로 healthy 판정. 29.5s/0건이 OK로 통과하면 안 됨.
- `agentic_pipeline._build_search_evidence_catalog`: degraded-zero가 임계 초과면 빈 카탈로그가 기존 retained official URL을 **덮어쓰지 못하게** reuse-evidence 폴백(SEARCH_DEGRADED 쿼런틴). + per-post search-health 카운터(queries_issued/upstream_zero/degraded/accepted)를 run_meta/identity에 persist.
- 검증: 단위테스트(threshold 로직) + healthy 백엔드에서 정상 통과 확인 + (가능하면) degraded 시뮬레이션.

### B. normal-path precision over-resolution 가드 (Track B, 진짜 leak 3건)
- 수술지점: `agentic_pipeline._resolve_batch_memory_alias_candidate` (후보 생성·반환 `:36448-36466`, title-lead 표면 캡처 `:36185-36199`). 기존 헬퍼 `_title_surface_candidate_has_broad_topic_installment_risk`(`:36469`)를 **반환 전에 연결**.
- 규칙: alias hit이 **title-lead 숫자/넘버링 표면**(lead_surface)에서 왔고 AND `not _title_mentioned_in_post_main_context(title)` AND (경쟁 본문 title_candidate 존재 OR verification_result `relation_judge:thematic_overlap_only/major`)이면 그 surface를 block(continue). `_mark_batch_alias_rescue_flags`(`:9856`)가 relation/multi_work demotion 플래그를 stripping하지 않게(title_in_post=false + 경쟁후보 시). `_pick_safe_single_candidate_unresolved_promotion`(`:40399`)의 title_lead/author 분기에 비교-프레이밍 negative gate.
- 테스트핀: **11661847→unresolved**, 11657013·11666700→unresolved-or-comparison, **11648980·11650585·11682781→resolved**(recall 경계 무손상). 정답 약칭(다녀왔어/괴담에 휘말렸다 = title_in_post=true)은 건드리지 말 것.
- 검증: 단위테스트 + **canary ≥2회**(비결정성) — 11660235·11655387 과해소 차단 + 게이트 recall(via_gate) 무손상 확인.

### C. no-work 가드 완화 — URL-present 전용 신규 anchor (Track C, B 뒤에만)
- `_has_strict_direct_work_anchor_for_no_work_rescue`(`~22762`)는 건드리지 말고, 신규 `_has_verified_alias_official_detail_anchor` 추가: exact official-DETAIL-URL+exact-title AND 검증 alias-bridge(slang_insight.decode_verified+alias_scope=='pure_work_alias' 또는 verifier가 약칭=그 제목 확인) AND 의도 not recommendation/memory-recall AND 도메인=novel_literature AND 단일후보, **5가드 전부** 충족 시에만 `_can_promote_title_after_semantic_no_work` 통과. **반드시 B 가드 통과 후 발화**(URL 존재만으로 불충분 — 게임모드 collision 11695607이 exact URL 있어도 FP).
- 테스트핀: 11652175·11661853·11677911→resolved / 11687635·11695607·11705276·11665081→held.
- 검증: 단위테스트 + canary ≥2회 — 정확히 3개만 promote, 4개 hold 유지.

### D. (복구 후) 통합 canary 1회
healthy engine에서 v3 입력(55행) 재실행 → A 효과 + B 3 leak 차단 + C +3을 **한 run에서 동시 확인**. v3(degraded)/v5(healthy) 대비표 갱신.

## 4. 자율 루프 규칙 (사람 개입 없이)

각 항목(A→B→C→D)마다: 구현 → `py_compile` + `unittest tests.test_candidate_audit tests.test_judge_seed_registry`(+신규 테스트) → **실제 expert_main canary로 런타임 검증**(B/C는 비결정성으로 ≥2회) → before/after compare → docs(IMP-278/VERIFICATION_RESULTS) 갱신 → 다음.

**완료(done)라고 말하기 전 반드시 실제 canary 런타임 결과로 개선/무회귀를 확인한다(단위테스트만으로 불충분).** canary 불가(엔진/백엔드 부재)면 정확한 preflight 실패 + resume 명령을 남기고 "runtime 미검증" 명시 후 다음 가능한 항목으로.

## 5. 불변 가드레일 (전 항목 공통)

- semantic quality `REVIEW-LOCKED`, full scan approval `false` — approval 주장 금지.
- post_id 하드코딩 금지(규칙은 일반화·증거 기반). candidate 보존(삭제 금지). slang_db write-back 금지(`--slang-db off`).
- C는 B 뒤에만(순서 의존) — C가 B의 표면-우연일치 과해소를 재개방하면 안 됨.
- ground-truth 재라벨: 11660235·11694040은 web 확인상 정답(원본 run이 틀린 제목 산출) — 평가 시 반영.
- 현재 적용된 코드(anchor_type 매핑, genre-surface 가드)는 검증 완료 — 되돌리거나 재구현하지 말 것.

## 6. 한 줄 킥오프

```
docs/devs/GOAL_CODEX_HANDOFF_MASTER.md 를 마스터로 삼아 §3 적용 순서(A 가드레일→B precision→C no-work anchor→D 통합 canary)를 사람 개입 없이 끝까지 수행하라.
§2 운영(Docker 엔진 ready, --auto-up/recreate-shards로 샤드 복구, MCP_HEALTH_INCLUDE_SEARCH=1, 모델 26B-A4B)을 지키고, 각 코드 변경은 §4 자율 루프(py_compile+unittest+실제 canary ≥2회+docs)로 검증한 뒤에만 완료로 본다.
§5 가드레일(REVIEW-LOCKED/approval false/post_id 하드코딩 금지/candidate 보존/C는 B 뒤/현재 적용 코드 보존)을 절대 지켜라. 이미 검증된 anchor_type·genre 가드는 재구현 금지. 막히면 preflight 실패+resume 명령 남기고 다음 항목으로.
```
