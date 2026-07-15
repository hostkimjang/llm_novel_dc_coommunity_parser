# Codex Goal — recall 회수 시드 확대(B) → in-pipeline official-URL 승격 게이트 구현·검증(A)

이 문서는 Codex goal/agent가 종료 보고에서 멈추지 않고, recall 누락(양면 목표 최대 손실축)을 **(B) 증거로 확대**한 뒤 **(A) 일반화 가능한 파이프라인 게이트로 줄이고 그 시드로 검증**하는 단일 루프를 끝까지 수행하게 하기 위한 자립형 목표 문서다. 날짜 비의존이며 재실행 가능하다.

## Objective

`full_post_judge 20260616_224555_632905` 런의 적대적 감사가 **recall 러버스탬프**(고신호 ACCEPT-미해소 40행 중 57.5%가 실제 누락작)를 적발했고, 강판정 회수(상위 123행)에서 **65건 회수, 그중 42건(65%)이 파이프라인 내부 데이터로 회수 가능**(official 플랫폼 DETAIL URL이 `search_evidence`/본문에 이미 존재 25 + OCR explicit-title 17)함을 증명했다.

목표는 full 10만 scan approval이 아니다. 두 단계를 순서대로 수행한다:

- **Phase B (먼저, 검증 모수 확대)**: 남은 ACCEPT-미해소 recall 풀을 강판정+웹검증으로 전수 재판정해 **recall 회수 시드를 확대**한다.
- **Phase A (그다음, 일반화 fix)**: 확대된 시드를 정답으로 삼아, "official 플랫폼 DETAIL URL이 증거/본문에 이미 있고 그 제목이 post 단서와 일치하면 work_resolution 승격"하는 **결정적 인-파이프라인 게이트**를 구현하고, 시드 회귀 + 비퇴행 + 테스트로 검증한다.

semantic quality는 `REVIEW-LOCKED`, full scan approval은 `false`로 유지한다. 이 작업은 보조 기준선이며 사람 검수 gold/승인을 대체하지 않는다.

## Current State (증거)

- 전수 판정 산출: `out/full_post_judge_20260616_224555_632905/` (구조 무결성 GO / 의미 recall NO-GO — `docs/devs/VERIFICATION_RESULTS.md` 2026-06-18 정정 섹션 참조).
- recall 풀(우선순위 점수): `out/full_post_judge_20260616_224555_632905/_recall_rerun_pool.json`
  - `all_ordered` = ACCEPT-미해소 1772행(점수 내림차순). `high_recovery` = score≥5(629행).
  - 점수 = OCR explicit_title(+5) / official_url_in_search(+5) / official_url_in_body(+4) / slang_term(+1) / core_relevant(+2) / trs_ocr_unresolved(+2) / trs_matchable(+1).
- 이미 회수된 상위 123행(score≥7): `_recall_recovery_ids.json`, 결과 `recall_recovery/rr_*.json`, 시드 `recall_recovery_seed.jsonl`(65행, `deterministic_catchable` 42), 리포트 `report/recall_recovery_report.md`.
- 회수 시드 행 스키마: `{post_id, disagreement_type:under_resolved_false_negative, judge_seed_group:recall, expected_official_title, expected_heretic_url, source_tier, confidence, recovery_evidence, deterministic_catchable, note, provenance}`.

## Required Reading (편집/실행 전)

- `docs/devs/FULL_POST_JUDGE_RUNBOOK.md` (§0.1a 검색 클라이언트, §4/§5/§5b 프롬프트, §4.3b 스키마, §6)
- `docs/devs/VERIFICATION_RESULTS.md` (2026-06-18 정정 섹션), `docs/devs/IMPROVEMENT_REGISTER.md` (IMP-20260618-278), `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md` (§4 증거정책·§13 게이트)
- `src/llm_batch/agentic_pipeline.py`: `_derive_resolution_scope_fields`(:11341), `_build_search_evidence_catalog`/`_source_tier`(:11095/:11121), `_build_image_evidence_catalog`(:11189), `has_official_candidate`(:15780), official_detail→community 강등(~:19759), negative 신호 `missing_official_url_for_official_detail`/`url_is_community_post`(~:23507)
- `src/llm_batch/grounding/candidate_audit.py`: `OFFICIAL_TITLE_SOURCE_TIERS`(:61), `WEAK_PRIMARY_SOURCE_TIERS`(:60), `official_search_supports_title`(:202), `_explicit_image_work_titles`(:230), `_titles_match`/`_compact_title`(:162/:157, fuzzy: compact 동일 or prefix len≥8 & ratio≥0.65), `apply_official_title_promotion_guard`(:514), `classify_candidate_audit`(:741)
- `src/llm_batch/search/client.py`: `MCPClient.search/fetch` (라이브 `http://127.0.0.1:3333`, `health_check(include_search=True)`)
- `src/llm_batch/domain/models.py` (식별 스키마), `tests/test_candidate_audit.py`

## Operating Rules (양면 가드레일)

- run 무결성 / semantic 품질(REVIEW-LOCKED) / full-scan approval(false)을 모든 보고에서 분리한다. approval 주장 금지.
- **과승격 금지(precision 가드)**: URL 존재만으로 승격 금지. 정밀 감사에서 ACCEPT-resolved의 26.7%가 false-accept(over-resolved/wrong-work)였다. DETAIL 페이지 + 제목↔post 단서 fuzzy 일치를 반드시 요구한다.
- **no-work 단조성 유지**: memory-query/사회적 푸념/장르 잡담/문맥-only(`title_resolution_allowed=false`, `unresolvable_memory_query`, `context_only`, `nonwork`)는 늦은 URL/검색으로 작품화하지 않는다.
- candidate-preservation은 그대로: 승격 안 되는 행은 `candidate_ledger`/`hold_unresolved` 보존(삭제 금지).
- post_id 하드코딩 금지. 규칙은 일반화 가능하고 증거 기반이어야 한다.
- 소규모 targeted 실행은 `--parallel min(input_count,36)`. Codex subagent 병렬과 `expert_main.py --parallel`을 혼동하지 말 것.
- 인터프리터 `.venv312\Scripts\python.exe`, 테스트 `unittest`. docs/checklist를 루프 중 갱신.

---

## Phase B — recall 회수 exhaustive 확장 (먼저)

### B1. 모집단
`_recall_rerun_pool.json`의 `high_recovery`(score≥5, 629행)에서 **이미 처리한 123행(`_recall_recovery_ids.json`)을 뺀 ~506행**을 1차 대상으로 한다. 여유가 되면 score 1–4 잔여(~333행)까지 확장하되, **score 0(810행)은 회수신호 없는 진성 무앵커일 가능성이 높으므로 후순위**(표본 점검만).

### B2. 재판정 (강판정 + 웹)
- 각 행의 컴팩트 projection(§2.3, `_audit_input`/`_recall_recovery_input` 추출 로직 재사용)으로 배치를 만들고, **§5b 강화 recall 프롬프트**(아래 회수 레버 포함)로 배치당 1회 판정한다.
- 회수 레버(순서대로): (1) image OCR이 작품 DETAIL 스샷(제목+작가+조회수/시놉시스)이면 그게 작품 — 웹 1회 확인 후 회수. (2) `search_evidence`/본문에 munpia/novelpia/page.kakao/series.naver/ridibooks **DETAIL URL**이 이미 있으면 열어(WebFetch) 제목↔post 단서 대조 후 회수. (3) 약칭/슬랭/캐릭터명 공격적 decode + 웹검색(munpia/novelpia/kakao/naver/ridi/namu.wiki/arca.live/fmkorea).
- **과회수 가드**: 회수=true는 official 플랫폼/위키 페이지 or 강한 커뮤니티 합의로 **이 post의 구체 단서가 한 작품에 매칭**될 때만. 일반 장르론·플랫폼이전 반응·앵커없는 memory-query는 회수 안 함(confidence=low는 회수 아님).
- 백엔드: Codex 네이티브 웹(권장) 또는 vLLM+`MCPClient` evidence 주입. 루프 전 `MCPClient().health_check(include_search=True)['ok']` 확인.

### B3. 산출
- 회수 결과를 `recall_recovery_seed.jsonl`에 **append**(중복 post_id 멱등 갱신), `recovery_evidence`/`deterministic_catchable`/`confidence`/`expected_official_title`/`expected_heretic_url` 포함.
- 누락 0(모집단 전 행이 recovered true/false verdict를 가짐), 커버리지 표를 `report/recall_recovery_report.md`에 갱신(회수율·근거유형·deterministic_catchable 합계).

### B4. Phase B 완료 조건
확대된 시드(목표: deterministic_catchable ≥ 100행 규모)와 회수율 갱신 리포트가 존재. 이 시드가 Phase A의 정답·회귀 모수가 된다.

---

## Phase A — in-pipeline official-URL 승격 게이트 구현·검증 (그다음, IMP-278)

### A1. 구현 (일반화·과승격 가드 필수)
`agentic_pipeline.py`의 work_resolution 승격 경로(`_derive_resolution_scope_fields` 및 그 입력을 만드는 candidate/primary_work 결정부)에 **recall 회수 게이트**를 추가한다. 핵심은 기존 강등 로직(official_detail→community when no url ~:19759, negative `missing_official_url_for_official_detail`/`url_is_community_post` ~:23507)의 **역방향**이다:

- 조건(모두 충족 시에만 승격): work_resolution이 none/unresolved/hold로 떨어질 행에서,
  1. `search_evidence_catalog`에 catalog `source_tier in {official_detail, novel_platform}`(=`_source_tier` 분류, `novel_platform`/`platform_reader_page`는 platform이되 **DETAIL만**; `/viewer/`·`/community/`·`/arena/`·`/review/`·작가/검색/랭킹/장르/목록 탭 제외) 엔트리가 있거나, 본문에 동일 기준의 작품 DETAIL URL이 있고,
  2. 그 엔트리/페이지 제목이 post 단서(post title / OCR `_explicit_image_work_titles` / decoded alias / 본문)와 **`_titles_match`(fuzzy)** 일치한다.
  → work_resolution=resolved, official_title/heretic_url 설정, source_tier=official_detail|novel_platform, confidence는 기존 rank 로직 따름. 가능하면 `official_search_supports_title`/`_explicit_image_work_titles`를 그대로 재사용.
- OCR explicit-title 경로: `_explicit_image_work_titles(identity)`가 비어있지 않고 official/플랫폼 검색으로 재확인되면 동일 게이트로 해소(단독 OCR 표면만으로는 lock 금지 — 재확인 필수).
- **과승격 가드**: URL 존재만으로 승격 금지(제목 일치 필수). no-work 단조성 행(memory-query/context_only/nonwork/`title_resolution_allowed=false`)은 승격 제외. 승격 안 되는 행은 candidate 보존.
- 필요 시 `candidate_audit.py`에 헬퍼(예: `official_url_recoverable(identity)->Optional[dict]`) 추가. promotion guard와 분리(게이트는 recall 승격, guard는 precision 강등).

### A2. 검증
- **시드 회귀**: `recall_recovery_seed.jsonl`의 `deterministic_catchable=true` 행을 게이트로 재평가해, expected_official_title/heretic_url로 **승격되는지** 확인(회수율 측정). 비-catchable(웹-only) 행은 게이트가 회수 못 해도 정상(웹 의존).
- **비퇴행(precision)**: 기존 `safe_resolved`(345)가 resolution을 잃지 않는지, 그리고 **새 over-promotion이 없는지** 확인 — 정밀 감사 false-accept 예시(over-resolved 11652201·11655387, wrong-work 11657013·11657016·11660235·11660257 부류)가 이 게이트로 잘못 승격되지 않아야 한다.
- **단위 테스트**(`tests/test_candidate_audit.py` 또는 신규): (양성) official DETAIL url in evidence + 제목일치 → resolved; (음성) url 있으나 제목 불일치 → 미승격; (음성) community/viewer/작가 탭 url → 미승격; (음성) memory-query/context_only → 미승격; (음성) OCR 표면만·재확인 실패 → 미승격.
- **canary**: seed post_ids 일부로 `expert_main.py` targeted 재실행(`--reuse-shards-only --no-dashboard --slang-db off`) 후 before/after compare(work_resolution 승격 수, official_title 과/미승격, candidate 보존).

### A3. 검증 명령
```powershell
.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py src\llm_batch\grounding\candidate_audit.py tests\test_candidate_audit.py
.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry -v
git diff --check
```

## Completion Criteria (이 루프 한정)

- Phase B: 잔여 recall 풀(score≥5 비처리분) 전 행이 회수 verdict를 가지며 `recall_recovery_seed.jsonl`이 확대됨(누락 0). 회수율 리포트 갱신.
- Phase A: 게이트가 구현되고, 시드 deterministic_catchable 회귀에서 측정된 회수율·과승격 0(또는 명시된 예외)·기존 safe_resolved 비퇴행이 확인됨. 단위 테스트 추가/통과, py_compile/unittest/`git diff --check` 통과.
- canary 재실행 또는 정확한 preflight 실패 기록 + before/after compare/quality summary 산출.
- docs/checklist/history/register 갱신(IMP-278 상태 진행).
- semantic quality REVIEW-LOCKED 유지, full scan approval false. 미자동화 케이스는 사유 기록.

미완 항목이 있으면 현재 슬라이스를 최종 승인으로 취급하지 말고 루프를 계속한다.

---

## 후속 재개선 루프 (2026-06-18, 적대적 검증 결과)

Phase A 게이트 독립 적대적 검증에서 **genre-surface 과승격 누수 1건**(`full_title_surface`가 "ts인방물" 같은 장르/서술어 표면을 동명 작품으로 승격)을 적발하고 **패치 완료**(IMP-278 재개선 블록 참조): `candidate_audit.GENRE_DESCRIPTOR_SURFACES` + `_is_genre_descriptor_surface()`로 약-anchor를 장르 표면에서 차단, 강-anchor(OCR/confirmed-alias/in-body URL)는 통과. 회귀 테스트 2건 추가(23 OK), false-block 0, 규모 probe(1772행) 장르 과승격 0.

### Phase A.4 — genre stoplist 확장 (선택, 일반화)
`GENRE_DESCRIPTOR_SURFACES`는 관측 기반 최소셋이다. 후속 코퍼스에서 장르/서술어 표면(…물/…판 계열, 장르 archetype)을 더 발견하면 셋에 추가하되, **단독 셋 하드코딩보다 일반 규칙**(genre 접미사 패턴 + slang_db `_is_generic_term` 장르 목록 재사용)으로 수렴시킨다. 추가마다 회귀 테스트(차단 negative + OCR 강-anchor 통과 positive)를 단다.

### Phase A.5 — 실제 승격 set 전수 over-promotion 감사 (필수 검증)
독립 probe는 저장 결과만 써서 런타임 `alias_clues`/`body_official_detail_candidates`를 복원 못 해 게이트의 **실제 승격 47건 전수가 아니다**(probe는 14건만 재현). 따라서:
1. seed/ACCEPT-미해소 풀에 대해 `expert_main.py` canary를 재실행해 게이트가 실제로 승격한 행과 그 anchor/근거를 emit한다.
2. 승격 전수를 적대적으로 재검증(웹 확인)해 over-promotion(genre/wrong-work/over-resolved)을 측정한다 — 목표: high-severity over-promotion 0, 약-anchor 승격은 전부 특정 작품 정합.
3. 기존 `safe_resolved`(345) 비퇴행 + precision false-accept 예시(11657013/11657016/11660235/11652201/11655387 부류) 비승격 동시 확인.
완료 시 게이트를 "precision-safe recall 회수"로 승인하되 semantic quality는 여전히 REVIEW-LOCKED, full scan approval은 false.
