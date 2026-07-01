# GPT Pro Pipeline Research Context - 2026-06-14

목적: 2026-06-14 GPT Pro judge 전수 결과와 현재 코드/프롬프트/운영 계약을 묶어, 다음 파이프라인 개선 연구 방향과 goal tree를 도출하기 위한 압축 컨텍스트다.

## 1. 현재 진단 대상

- 대상 repo: `llm_novel_dc_coommunity_parser`
- 주요 실행 엔트리포인트: `expert_main.py`
- 핵심 파이프라인: `src/llm_batch/agentic_pipeline.py`
- 전문가 체인:
  - `src/llm_batch/experts/gatekeeper.py`
  - `src/llm_batch/experts/discourse.py`
  - `src/llm_batch/experts/decoder.py`
  - `src/llm_batch/experts/verifier.py`
  - `src/llm_batch/experts/arbiter.py`
  - `src/llm_batch/experts/orchestrator.py`
- 프롬프트 계층:
  - 대형 정적 prompt: `src/llm_batch/prompts/expert_prompts.py`
  - 동적 overlay/router: `src/llm_batch/prompts/prompt_router.py`
- 공유 메모리/사전:
  - `src/llm_batch/batch_context.py`
  - `src/llm_batch/slang_db.py`
- 결과 schema: `src/llm_batch/models.py`

## 2. GPT Pro judge 결과 요약

출처:

- `docs/devs/JUDGE3905_REPORT.md`
- `out/_judge3905_gpt_pro_v2/_result.json`
- `out/_judge3905_gpt_pro_v2/post_ids_by_type.json`

커버리지:

- `3874 / 3874` post 전수 완료
- `155 / 155` batch 완료
- `agree=2303`, `disagree=1571`, `invalid_batches=[]`
- 일치율 `59.4%`, 불일치율 `40.6%`
- severity: `high=292`, `med=693`, `low=2889`

불일치 유형:

| type | total | high | med | low | 해석 |
|---|---:|---:|---:|---:|---|
| `under_resolved_false_negative` | 644 | 198 | 438 | 8 | 가장 큰 recall 손실. 작품/작품 관련 글을 none/noise/trope로 놓침 |
| `wrong_discussion_type` | 549 | 0 | 71 | 478 | relevance는 대체로 맞지만 라벨 위생이 흔들림 |
| `wrong_relevance` | 169 | 2 | 139 | 28 | 추천/작가/플랫폼/웹소설 메타를 noise로 내리는 문제 |
| `uncertain` | 66 | 0 | 2 | 64 | 첨부 증거만으로 확정 어려움 |
| `cross_media_or_famous_mismatch` | 52 | 29 | 20 | 3 | 게임/웹툰/애니/고전/유명작 오매칭 |
| `wrong_work` | 39 | 29 | 9 | 1 | 다른 작품으로 확정 |
| `over_resolved` | 22 | 20 | 2 | 0 | 일반 표현/비교/인물/공지 등을 작품으로 확정 |
| `title_noisy_ocr` | 20 | 6 | 10 | 4 | OCR/토큰 오염 |
| `garbage_title` | 10 | 8 | 2 | 0 | URL/일반어/불완전 문자열을 제목으로 채택 |

초기 해석:

- recall 최대 손실은 약칭, 캐릭터명, OCR 표제, 댓글 제목 응답, 작가 신작/연재 대기 맥락 보존 실패에서 나온다.
- precision 고위험은 cross-media/famous, wrong_work, over_resolved, garbage_title처럼 수는 적지만 high 비율이 매우 높다.
- 따라서 한 개의 단순 prompt 보강보다, `specific-work recall`과 `title promotion precision`을 분리한 실험 설계가 필요하다.

## 3. 운영 계약과 승인 경계

반드시 지켜야 할 운영 계약:

- 이 3905건 judge는 104,502 full scan의 head slice 성격이다. 모집단 오류율 또는 전체 품질 승인으로 환산하지 않는다.
- GPT Pro judge는 웹검색 없이 첨부된 batch/title/body/comments/image_ocr 및 모델 지식으로 판정했다. `web_unverified` note는 ground truth가 아니라 재검토 seed다.
- full approval은 별도 random baseline, high-risk expansion, source-grounded verification, VLM/OCR/browser visual gate가 필요하다.
- `expert_main.py --parallel`은 repo runtime worker cap이다. Codex subagent 병렬 검토와 혼동하지 않는다.
- no-work/context-only 신호가 있으면 후단 search/known alias/slang_db/BatchContext rescue는 packet-local direct hard anchor 없이 title을 되살리면 안 된다.
- official detail URL/search title match는 작품 존재 증거일 수 있지만, no-work/context-only 발화 의도를 특정 작품 토론으로 바꾸는 direct hard anchor는 아니다.
- direct hard anchor 예: raw title/body/comment의 직접 작품명/안정 별칭, VLM/OCR 직접 작품명, image primary work anchor, verified character-work link, compound title-character bridge.
- VLM/OCR ready는 run-level 상태다. per-image approval에는 image evidence catalog, fetch/chunk/OCR status, browser article loaded counter, placeholder/incomplete/broken/lazy pending counter, screenshot alignment가 필요하다.

## 4. 코드 구조 관찰

### `expert_main.py`

역할:

- JSONL 입력 로드, public comment metadata/dialogue context, image block 추출
- CLI/environment toggle 정리
- LLM/MCP endpoint pool, shard lifecycle, health check
- `AgenticPipeline` 생성 및 post 단위 처리
- parallel worker cap: `--parallel`은 max이며 small input에서는 `effective_parallel=min(input_count, requested_parallel)`로 축소
- checkpoint, completed subset, pending snapshot, manifest 기록
- VLM/OCR required gate 및 이미지 post counter 보존

관련 line anchor:

- arg parser: `expert_main.py:34`
- parallel policy cap: `expert_main.py:123-186`
- post count effective parallel: `expert_main.py:186`
- public comment context: `expert_main.py:193-394`
- main run and pipeline creation: `expert_main.py:1400`, `expert_main.py:2490`
- worker process/checkpoint/manifest: `expert_main.py:2509-3106`
- JSONL loader: `expert_main.py:3345`
- VLM/OCR semantic review gates: `expert_main.py:3557-3620`

### `src/llm_batch/models.py`

역할:

- `PickvelIdentity`가 `is_relevant`, `is_novel_related`, `is_resolved_work_discussion`, `title_resolution_state`, `title_resolution_allowed`를 분리한다.
- `discussion_type`, `topicality`, `relevance_scope`, `subtype`, `work_resolution`, `anchor_type`, `anchor_strength`, evidence catalogs를 통해 resolved title과 broader novel-community relevance를 분리하려는 설계가 있다.

중요한 연구 포인트:

- judge의 `wrong_relevance`와 `wrong_discussion_type`은 schema가 이미 분리한 축을 후단에서 일관되게 채우지 못한 문제일 가능성이 크다.
- `recommendation`, `author_talk`, `trope_discussion`, `meta`, `community_banter`가 항상 `is_relevant=false`처럼 주석화되어 있으나, 현재 judge는 “웹소설권 주변 관련성”을 noise와 분리해야 한다고 본다.

### `src/llm_batch/prompts/prompt_router.py`

역할:

- 대형 prompt 위에 동적 Korean understanding overlay를 붙인다.
- relevance contract는 `official_title`에는 작품 정식명만 허용하고, 작가/플랫폼/추천/장르 일반론을 noise로 단순 압축하지 말라고 지시한다.
- 기억 회수/제목 찾기 글에서 소설 관련성과 단일 작품 매칭 가능성을 분리하라고 지시한다.
- 일반명사/트로프/장면용어/코스튬+인명 조합은 작품 고유 bridge 없이는 약칭 승격하지 말라고 지시한다.
- 감상어/질문/상태 접미사를 `detected_term`에 포함하지 말고, pure alias와 상태/감상어를 분리하라고 지시한다.

연구 포인트:

- prompt는 이미 “분리하라”고 말하지만, judge 결과에서는 분리 실패가 많다. 따라서 prompt보다 post-processing/state-machine/lint의 문제인지 점검해야 한다.
- 반대로 prompt가 recommendation을 `is_relevant=false`로 고정하는 부분과 judge의 “웹소설권 관련성 유지” 요구가 충돌할 수 있다. `is_relevant`와 `is_novel_related`의 정의를 다시 정렬해야 한다.

### `src/llm_batch/agentic_pipeline.py`

역할:

- `AgenticPipeline`은 expert instance, search cache, orchestrator, rules, VLM/OCR, reason synthesis, active learning queue를 묶는 최상위 post processor다.
- 내부에 title acceptance, no-work gate, known abbreviation guard, alias/search rescue, non-novel media gate, final output shaping이 매우 길게 존재한다.

핵심 line anchor:

- `class AgenticPipeline`: `agentic_pipeline.py:105`
- `_semantic_seed_no_work_signal`: `agentic_pipeline.py:22446`
- `_compute_title_acceptance`: `agentic_pipeline.py:28992`
- `_try_promote_best_candidate`: `agentic_pipeline.py:31197`
- `_apply_known_abbreviation_title_guard`: `agentic_pipeline.py:31888`
- `_has_direct_post_or_visual_work_anchor_for_no_work_search_rescue`: `agentic_pipeline.py:36881`
- `_has_explicit_webnovel_work_evidence_for_title`: `agentic_pipeline.py:43297`
- `_has_non_novel_media_evidence_for_title`: `agentic_pipeline.py:43668`
- `run_agentic_pipeline`: `agentic_pipeline.py:44110`

관찰:

- `_semantic_seed_no_work_signal`은 discourse semantic seed, warning flags, final/verification consistency flags, `title_resolution_allowed=false`, `context_only/nonwork/unresolvable_memory_query`를 결합해 no-work/context-only 상태를 판단한다.
- `_can_promote_title_after_semantic_no_work`는 direct anchor가 없으면 late title promotion을 차단하고 `semantic_seed_no_work_direct_anchor_missing`을 기록한다.
- `_compute_title_acceptance`는 title commitment, candidate class, grounding anchor, alias support, character link, relation judgment, official URL count, non-novel warning, platform meta, search-only/generic/bridge-only 여부를 함께 본다.
- `_try_promote_best_candidate`는 official_title이 비어 있을 때 curated abbreviation, verifier, decoder, suspected_titles에서 후보 승격을 시도한다. registry alias는 독립 work anchor가 없으면 막고, hard support가 없으면 confidence를 `Medium`으로 낮춘다.
- `_apply_known_abbreviation_title_guard`는 제목 표면의 등록 약칭 rewrite 후보를 모아 evidence-aware rewrite를 시도한다. registry alias는 hard support 없이 rewrite하지 않도록 guard가 있다.
- `_has_direct_post_or_visual_work_anchor_for_no_work_search_rescue`는 no-work 해제 direct anchor를 title surface, direct image title, image primary, verified character-work link, curated alias contextual work anchor로 제한한다.
- `_has_explicit_webnovel_work_evidence_for_title`과 `_has_non_novel_media_evidence_for_title`은 웹소설 근거와 게임/만화/애니/웹툰/고전 계열 evidence를 분리하려고 한다.

연구 포인트:

- recall FN 644건은 guard가 과도하게 닫힌 케이스와, guard로 들어가기 전 후보 생성 자체가 실패한 케이스를 분리해야 한다.
- precision high error는 guard가 없어서라기보다, guard의 hard anchor 정의가 “직접 제목/이미지/캐릭터 bridge”를 충분히 검증하지 못하거나, 비교/댓글/배경 catalog evidence가 primary subject로 새어 들어온 케이스일 수 있다.
- giant post-processing이 단일 파일/단일 흐름에 너무 많은 상충 목표를 담고 있어, 연구상으로는 `candidate generation`, `evidence attribution`, `promotion decision`, `public output hygiene`, `review queue`를 분리하는 것이 좋아 보인다.

### `src/llm_batch/experts/orchestrator.py`

역할:

- `ConversationContext`가 post data, comments, search results, expert outputs, suspected_titles, primary_domain, discourse_warning, uncertainty_sources, candidate_evidence, bridge profiles, search stats, final flags를 공유한다.
- `Orchestrator`는 gatekeeper/discourse/decoder/verifier/arbiter 협업, search/fetch, budget trim, strong work anchor 탐지를 맡는다.

핵심 line anchor:

- `ConversationContext`: `orchestrator.py:132`
- `Orchestrator`: `orchestrator.py:968`
- `_has_strong_work_anchor`: `orchestrator.py:1090` 근방

연구 포인트:

- `candidate_evidence` bucket과 `candidate_bridge_profiles`가 이미 존재하므로, failure taxonomy별로 “어느 candidate가 어떤 evidence를 가져갔는지”를 산출물에 더 명시하면 judge/리뷰가 쉬워진다.
- `suspected_titles`와 `candidate_evidence`가 많아질수록 비교작/댓글 추천작/배경 catalog 후보가 primary로 승격되는 누수를 audit해야 한다.

### `src/llm_batch/experts/decoder.py`

역할:

- Gatekeeper key terms + possible_titles + session knowledge + slang dictionary + search results를 바탕으로 decoded terms/candidates를 만든다.
- possible_titles를 key_terms에 병합하되 n-gram garbage, 문장 조각, 비속어, token cap을 걸어준다.
- 검색 결과 content를 trim해 prompt에 넣는다.
- discourse warning이나 genre discussion flag를 받으면 candidate title hallucination을 억제한다.

핵심 line anchor:

- `DecoderExpert`: `decoder.py:519`
- `analyze`: `decoder.py:636`
- `_call_llm`: `decoder.py:2117`

연구 포인트:

- under-resolved FN은 key term extraction/token cap/filtering에서 약칭/캐릭터/댓글 응답 후보가 탈락했는지 먼저 나눠야 한다.
- `session_knowledge`와 `slang_dictionary`는 recall에 강하지만 precision 오염 가능성이 있으므로, `hint`, `candidate`, `promotion`을 별도 단계로 강제해야 한다.

### `src/llm_batch/experts/verifier.py`

역할:

- Decoder 후보와 검색/댓글/본문을 검증해 final identity를 만든다.
- LLM verifier가 false negative를 내면 `_recover_false_negative_with_code_anchor`로 제한적 복구를 시도한다.
- `relation_judge` bootstrap을 통해 `promotion_decision`, `discussion_target`, `relation_type`을 판단한다.
- LLM 제목 환각을 검색/decoder evidence와 대조해 교정한다.
- platform branding, archetype, post title theft 등 후처리 guard가 많다.

핵심 line anchor:

- `VerifierExpert`: `verifier.py:29`
- `analyze`: `verifier.py:1167`
- `_call_llm`: `verifier.py:2679`
- `_fallback_result`: `verifier.py:2741`
- `_RELATION_JUDGE_PROMPT`: `verifier.py:2854`
- `_should_run_relation_judge`: `verifier.py:4016`
- `_apply_relation_judgment`: `verifier.py:4224`
- `_recover_false_negative_with_code_anchor`: `verifier.py:4648`

연구 포인트:

- relation judge의 output을 promotion decision에 쓰는 방식이 recall/precision tradeoff의 중심일 가능성이 높다.
- false negative 복구가 “작품 관련성은 보존하되 title은 unresolved”라는 중간 상태를 충분히 만들고 있는지 확인해야 한다.
- high precision error 방지를 위해 `wrong_work`, `over_resolved`, `garbage_title` high seed에서 relation target attribution을 재검토해야 한다.

### `src/llm_batch/experts/arbiter.py`

역할:

- 여러 expert output과 evidence score를 종합해 final decision을 만든다.
- known abbreviation, alias guard, multi-work/noise/low-confidence guard exception, fallback decision이 있다.

핵심 line anchor:

- `ARBITER_SYSTEM`: `arbiter.py:37`
- `ARBITER_PROMPT`: `arbiter.py:420`
- `ArbiterExpert`: `arbiter.py:785`
- `analyze`: `arbiter.py:1443`
- `_call_llm`: `arbiter.py:7001`
- `_fallback_decision`: `arbiter.py:8807`

연구 포인트:

- Arbiter가 `is_relevant`, `official_title`, `discussion_type`, `title_resolution_state`를 최종적으로 어떻게 정렬하는지 judge error별로 추적해야 한다.
- discussion_type drift 549건은 Arbiter/final output hygiene 문제로 별도 lint화할 수 있다.

### `src/llm_batch/batch_context.py`와 `src/llm_batch/slang_db.py`

역할:

- BatchContextMemory는 alias/author/character hints를 batch 내에서 공유하고, resolved result에서 새 alias를 학습한다.
- generic inline alias, OCR/오타 변형 alias, low evidence slang seed, context-only/no-work polluted seed를 보류/차단한다.
- slang DB는 pending kind, alias candidate, exact title alias, low information alias, polluted alias seed signal, safe seed 여부를 관리한다.

연구 포인트:

- recall FN high 중 “같은 batch/근방에서 이미 확인된 약칭”을 놓친 경우가 있는지 측정해야 한다.
- 동시에 wrong_work/cross-media high는 polluted alias seed 또는 registry alias가 primary subject를 잘못 덮은 것인지 측정해야 한다.
- `slang_db`는 학습 저장소라기보다 evidence lifecycle manager로 취급하고, `observed surface -> candidate -> verified alias -> promotable alias` 단계가 필요하다.

## 5. GPT Pro에게 물어볼 연구 질문

1. 현재 구조에서 실패 유형별 root cause를 어떤 코드/프롬프트/운영 gate로 맵핑할 수 있는가?
2. `under_resolved_false_negative` 644건을 줄이기 위해, false positive high error를 늘리지 않는 candidate generation/retention 전략은 무엇인가?
3. `cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title` high seed를 막기 위해, title promotion/evidence attribution을 어떻게 재설계해야 하는가?
4. `is_relevant`, `is_novel_related`, `is_resolved_work_discussion`, `title_resolution_state`, `discussion_type`, `topicality`, `subtype`의 contract를 어떻게 재정렬해야 하는가?
5. prompt 개선이 필요한 부분과 code/state-machine/lint 개선이 필요한 부분을 어떻게 나눌 것인가?
6. 다음 1주/2주/장기 roadmap에서 어떤 regression set, random/high-risk expansion, ablation, metric을 운영할 것인가?
7. 거대한 `agentic_pipeline.py` 후단을 어떤 작은 경계로 쪼개면 reviewability와 회귀 방지가 좋아지는가?

## 6. 원하는 산출 형식

한국어로 작성한다. 다음 섹션을 포함한다.

1. 현재 아키텍처 mental model
2. 실패 taxonomy별 root cause hypothesis
3. 코드/프롬프트/문서별 개선 locus
4. P0/P1/P2 goal tree와 acceptance criteria
5. 실험 설계: seed set, random baseline, high-risk expansion, ablation
6. prompt/orchestration/schema refactor 제안
7. slang_db/BatchContext/alias governance 제안
8. Search/VLM/OCR/browser evidence strategy
9. 1주, 2주, 장기 roadmap
10. risk/tradeoff/non-goal

제약:

- judge head slice를 전체 품질 승인 근거로 쓰지 말 것.
- post-specific hardcoding을 제안하지 말 것.
- 단순 “프롬프트를 더 강화” 같은 추상 조언보다, 코드 경계와 측정 가능한 acceptance criteria를 제안할 것.
- direct hard anchor, no-work/context-only monotonic gate, browser/VLM evidence gate를 깨지 않는 방향으로 제안할 것.
