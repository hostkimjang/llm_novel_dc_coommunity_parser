# Codex Goal — official-url recall gate: 실행 → 확인 → 리뷰 → 개선 → 재실행 루프

이 문서는 Codex goal/agent가 종료 보고에서 멈추지 않고, IMP-278 official-url recall 승격 게이트(+genre-surface 가드)를 **실제 파이프라인에서 실행(canary)** 해 게이트가 진짜로 승격한 행을 emit하고, 그 승격 전수를 **적대적으로 확인·리뷰**해 over-promotion을 찾고, **일반화 가능하게 개선**한 뒤 **재실행으로 수렴**시키는 단일 루프를 돌게 하는 자립형 목표다. 날짜 비의존·재실행 가능.

## Objective

게이트의 **실제 런타임 승격 set**(저장-결과 probe로는 일부만 재현됨, ~14/47)을 canary로 확정하고, 그 승격이 precision-safe(장르/wrong-work/over-resolved 과승격 0)이면서 recall 회수(시드 deterministic_catchable)를 보존하는지 전수 검증한다. over-promotion이 보이면 일반화 가능한 가드로 개선하고 재실행해, 아래 **수용 게이트**를 충족할 때까지 루프한다.

목표는 full scan approval이 아니다. semantic quality는 `REVIEW-LOCKED`, full scan approval은 `false`로 유지한다. 보조 기준선이며 사람 검수 gold/승인을 대체하지 않는다.

## Current State (전제)

- 게이트 구현: `src/llm_batch/grounding/candidate_audit.py::official_url_recoverable`(공식 DETAIL URL + post-side anchor 필수), `agentic_pipeline.py` official-url recall gate(승격 연결부), `_can_promote_title_after_semantic_no_work()` 통과 요구.
- genre-surface 가드: `candidate_audit.GENRE_DESCRIPTOR_SURFACES` + `_is_genre_descriptor_surface()`가 약-anchor(full_title_surface/bracket_alias/official_page_alias_tag/title_unique_rare_token)를 장르/서술어 표면에서 차단(강-anchor OCR/confirmed-alias/in-body URL은 통과). 회귀 테스트 `tests/test_candidate_audit.py`에 genre 차단/통과 2건 포함(현재 23 tests OK).
- 시드/풀: `out/full_post_judge_20260616_224555_632905/recall_recovery_seed.jsonl`(124행, deterministic_catchable 101), `_recall_rerun_pool.json`(`all_ordered` 1772 = ACCEPT-미해소, `high_recovery` score≥5 = 629), 저장-결과 probe `_gate_promotions_patched.json`(14건).
- precision false-accept 예시(비승격 확인용 negative): over-resolved 11652201·11655387, wrong-work 11657013·11657016·11660235·11660257. 확정 genre 누수(수정됨, 비승격 확인용): 11716479(ts인방물).

## Required Reading

- `docs/devs/GOAL_RECALL_URL_GATE.md`(§A 구현·검증, Phase A.4/A.5), `docs/devs/IMPROVEMENT_REGISTER.md`(IMP-278), `docs/devs/VERIFICATION_RESULTS.md`(2026-06-18 독립검증), `docs/devs/FULL_POST_JUDGE_RUNBOOK.md`(§0.7 게이트 분리, §6)
- `src/llm_batch/grounding/candidate_audit.py`(`official_url_recoverable`:383, `_official_recall_anchor`, `_is_genre_descriptor_surface`, `GENRE_DESCRIPTOR_SURFACES`, `OFFICIAL_DETAIL_URL_RE`/`NON_DETAIL_URL_RE`), `src/llm_batch/agentic_pipeline.py`(`_derive_resolution_scope_fields`:11341, official-url gate 연결부, `_can_promote_title_after_semantic_no_work`)
- `src/llm_batch/slang/slang_db.py`의 `_is_generic_term` 장르 목록(genre stoplist 일반화 시 재사용), `expert_main.py`(입력 로더·CLI 플래그), `tests/test_candidate_audit.py`

## Operating Rules (양면 가드레일 — 절대 준수)

- run 무결성 / semantic 품질(REVIEW-LOCKED) / full-scan approval(false)을 분리 보고. approval 주장 금지.
- 과승격 금지: URL 존재만으로 승격 금지(DETAIL + 제목↔post 단서 일치 필수). no-work 단조성(context_only/memory_query/nonwork/`title_resolution_allowed=false`)은 늦은 URL로 작품화 금지.
- candidate 보존(삭제 금지). post_id 하드코딩 금지(규칙은 일반화·증거 기반). slang_db write-back 금지(`--slang-db off`).
- 개선은 단독 셋 하드코딩보다 일반 규칙(genre 접미사 패턴 + `slang_db._is_generic_term` 장르목록 재사용)으로 수렴. 추가마다 회귀 테스트(차단 negative + 강-anchor 통과 positive) 동반.
- 인터프리터 `.venv312\Scripts\python.exe`, 테스트 `unittest`. 소규모 canary는 `--parallel min(input_count,36)`.

## 루프 절차 (실행 → 확인 → 리뷰 → 개선 → 재실행)

### 1) 실행 (canary)
- canary 입력 구성: `_recall_rerun_pool.json`의 `high_recovery`(629행) post_id에 대응하는 **원천 post 행**(`out/expert_result_20260616_224555_632905.json`의 gallery_id/title/content_blocks/image_urls/comments)을 입력 JSONL로 만든다(기존 `tools/full_post_judge_codex_driver.py` projection 또는 expert_main 입력 로더 재사용). 가능하면 시드 deterministic_catchable 101 + precision negative 예시 + genre negative(11716479)를 포함.
- 게이트가 기존 search_evidence/OCR로 발화하도록 **검색 재호출 없이 shard 재사용**으로 실행:
  ```powershell
  .venv312\Scripts\python.exe expert_main.py --input <canary_input.jsonl> `
    --llm-endpoint http://10.20.0.101:8000 --llm-model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4 `
    --server-type vllm --reuse-shards-only --no-dashboard --slang-db off --vlm on --ocr on `
    --parallel <min(input,36)> --out out/recall_gate_canary_<ts>.json
  ```
  실행 불가 시 정확한 preflight 실패 사유 + resume 명령을 기록(중단 금지 사유 명시).
- run_id/input/result/checkpoint/manifest/log/effective_parallel/VLM·OCR readiness를 기록.

### 2) 확인 (coverage·승격 set·비퇴행)
- canary 결과에서 **게이트가 실제 승격한 행** = 원본에서 work_resolution in {none,unresolved,hold_unresolved}였다가 canary에서 resolved가 된 행. 이 **승격 set 전수**(post_id, official_title, heretic_url, matched_clue/anchor, confidence, source_tier)를 `out/recall_gate_canary_<ts>/_promotions.json`으로 emit한다.
- 승격 수, anchor 분포(ocr/full_title_surface/confirmed_alias/title_abbrev/in-body), confidence 분포를 집계. (저장-결과 probe 14건과 비교 — 런타임이 더 많이 잡는 게 정상.)
- 비퇴행: 원본 `safe_resolved`(345)가 canary에서 resolution을 잃지 않는지, **새 over-promotion이 없는지** 확인.

### 3) 리뷰 (적대적 over-promotion 감사 — 전수)
- 승격 set **전수**를 독립 적대적 재판정(웹 확인)으로 검수: 각 승격이 (a) 그 작품이 실재(official 플랫폼 DETAIL 페이지)하고 (b) post가 실제로 그 작품을 가리키는가. over-promotion 유형 분류: `genre_or_descriptor_surface`(장르어→동명작), `wrong_work`(다른작품), `over_resolved`(특정작 아님), `weak_anchor_coincidence`.
- recall 측 확인: 시드 deterministic_catchable 101 중 몇 건이 게이트로 승격됐나(회수율) — 미승격은 사유(no compact evidence/no-work guard/non-platform/weak anchor) 기록.
- negative 확인: precision false-accept 예시 + 11716479(ts인방물)이 **승격되지 않았는지** 확정.
- 결과를 `_promotion_audit.json` + `report/recall_gate_canary_review.md`(영어 enum+한글 병기)로 기록.

### 4) 개선 (일반화·테스트 동반)
- over-promotion이 보이면 원인별로 일반화 가능한 가드를 추가/강화:
  - genre/descriptor → `GENRE_DESCRIPTOR_SURFACES` 확장 또는 `_is_genre_descriptor_surface` 일반화(접미사 패턴 + `slang_db._is_generic_term` 장르목록 재사용).
  - weak-anchor 우연일치 → 약-anchor 조건 강화(제목 specificity·토큰수·source_tier).
  - wrong-work/over-resolved → DETAIL/제목일치 요건 강화, no-work 단조성 재확인.
- recall이 과소(시드 회수율 급감)면 가드가 과교정인지 점검(강-anchor 통과는 유지). **precision 우선, 단 candidate 보존으로 recall 손실 흡수.**
- 모든 변경에 회귀 테스트(차단 negative + 강-anchor 통과 positive) 추가. post_id 하드코딩 금지.

### 5) 재실행 (수렴 루프)
- 개선 후 1)~3)을 재실행해 over-promotion·recall·비퇴행을 재측정. 멱등(같은 입력 재실행 시 산출 덮어쓰기). before/after compare(`_promotion_compare.json`)로 변화 기록.
- 아래 수용 게이트를 충족할 때까지 루프. 매 라운드 docs/IMP-278·VERIFICATION_RESULTS 갱신.

## 수용 게이트 (모두 충족 시 이 루프 종료)

- canary 승격 set 전수가 emit되고 적대적 감사됨(top-N 금지·전수).
- **high-severity over-promotion = 0** (genre/wrong-work/over-resolved 확정 0). 약-anchor 승격은 전부 특정 작품 정합.
- precision negative(over/wrong 예시 + 11716479) **비승격 확정**, 기존 `safe_resolved` **비퇴행**.
- 시드 deterministic_catchable 회수율 기록(미승격은 사유). 회수율이 직전 라운드 대비 비합리적으로 떨어지지 않음(과교정 아님).
- 검증 명령 통과:
  ```powershell
  .venv312\Scripts\python.exe -m py_compile src\llm_batch\grounding\candidate_audit.py src\llm_batch\agentic_pipeline.py tests\test_candidate_audit.py
  .venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry -v
  git diff --check
  ```
- docs/checklist/history/IMP-278 갱신. semantic quality REVIEW-LOCKED, full scan approval false 유지. 미자동화 케이스 사유 기록.

미충족 항목이 있으면 현재 라운드를 최종으로 취급하지 말고 4)→5) 루프를 계속한다. canary 실행이 불가하면(파이프라인/엔드포인트 부재) 정확한 preflight 실패와 resume 명령을 남기고, 그 시점까지의 확인/리뷰/개선만으로 부분 종료한다(approval 금지).

---

## 2026-06-19 — 26B-A4B canary 3-트랙 진단 결과 + 적용 순서 (백엔드 복구 후 실행)

55-row controlled canary(26B-A4B) 후 3-트랙 진단 결과. **전제: search 백엔드(warp/SearXNG) DEGRADED — recall 측정/검증의 절대 선행조건은 인프라 복구다.**

### 0순위(인프라, 코드 아님) — search 백엔드 복구
warp-1..15:8080(SearXNG)이 500/connection-refused/29.5s 레이턴시로 degraded. 복구 전엔 어떤 recall canary도 무효. 복구 후 lost URL live re-probe로 반환성 확인.

### 1순위(A 가드레일 — search-health 관측·게이팅)
- **canary는 `MCP_HEALTH_INCLUDE_SEARCH=1` 필수**(현 default는 light/reuse에서 False → bridge-only, degraded shard가 새어듦). + health 게이트를 **응답여부가 아니라 레이턴시 floor + 결과수>0** 기준으로 강화(expert_main `_health_include_search` 소비부 ~2025-2054, `_mcp_health_required_ok_count`). 29.5s "응답"이 OK로 통과하면 안 됨.
- **SEARCH_DEGRADED 쿼런틴**: degraded-zero가 임계 초과면 빈 카탈로그가 기존 retained official URL을 **덮어쓰지 못하게** reuse-evidence 폴백(`agentic_pipeline._build_search_evidence_catalog`). precision-safe + recall-safe.
- **per-post search-health 카운터**(queries_issued/upstream_zero/degraded/accepted) → run_meta/identity persist(관측성).

### 2순위(B 정밀 가드 — 진짜 leak 3건)
- 대상: 11661847(batch_memory alias rescue가 title-lead 숫자/약칭 표면일치+official URL만 믿고 relation_judge:thematic_overlap/title_in_post=false/경쟁 본문 후보를 무시 승격), 11657013·11666700(비교프레이밍/단일후보 표면 승격).
- fix: 기존 `_title_surface_candidate_has_broad_topic_installment_risk`를 `_resolve_batch_memory_alias_candidate`(~36148-36400) 경로에 연결 — title_in_post=false AND (경쟁 본문 후보 OR relation_judge overlap)일 때 block. `_mark_batch_alias_rescue_flags`(~9856)가 relation/multi_work demotion 플래그를 stripping하지 않도록. `_pick_safe_single_candidate_unresolved_promotion`(~40399)의 title_lead/author 분기에 비교-프레이밍 negative gate.
- 단위테스트 핀: 11661847→unresolved / 11648980·11650585→resolved(recall 경계 무손상). recall-safe(정답 약칭은 title_in_post=true).

### 3순위(C no-work 가드 완화 — 신규 좁은 anchor, B 뒤에만)
- strict anchor(`_has_strict_direct_work_anchor_for_no_work_rescue` ~22762)가 full title 표면만 인정 → 약칭 posts 일괄 차단. 7건 중 3건 부당차단(11652175·11661853·11677911), 3건 정당(11687635·11695607·11705276), 1 모호(11665081).
- fix: 신규 `_has_verified_alias_official_detail_anchor` — exact detail-URL+title AND 검증 alias-bridge(slang_insight.decode_verified+pure_work_alias) AND 비추천 의도 AND novel_literature 도메인 AND 단일후보, **5가드 전부** 충족 시에만. **반드시 B 가드(title_in_post/경쟁후보/relation) 통과 후 발화** — 안 그러면 B가 막는 표면 우연일치 과해소를 재개방.
- 단위테스트 핀: 11652175·11661853·11677911→resolved / 11687635·11695607·11705276→held / 11665081→held.

### 충돌·검증 규칙
- **C ↔ B 순서 의존**: B 먼저 넣어야 C 완화의 안전 경계가 코드로 존재. C가 "URL+alias면 promote"를 넓히면 B 타깃을 재개방할 수 있음 — URL 존재만으론 불충분(C의 11695607 게임모드가 exact URL 보유에도 충돌 FP).
- **셋 다 `is_code_change_needed=true` + expert_main 런타임 재검증 필수**(단위테스트 불충분; B/C는 run-to-run 비결정성으로 복수 run). **백엔드 복구 전엔 검증 불가 → 코드변경 보류**(현재 미적용).
- 비코드: ground-truth 재라벨(11660235·11694040은 web 확인상 정답 — 원본 run이 틀린 제목 산출).
- **5순위(복구 후)**: healthy engine 통합 canary 1회로 A drift 소멸 + B 3 leak 차단 + C +3을 **동시에** 확인.
