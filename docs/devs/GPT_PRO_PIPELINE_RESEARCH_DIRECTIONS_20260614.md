# GPT Pro Pipeline Research Directions - 2026-06-14

작성: 2026-06-14
입력 근거:

- `docs/devs/GPT_PRO_PIPELINE_RESEARCH_CONTEXT_20260614.md`
- `docs/devs/JUDGE3905_REPORT.md`
- `out/_judge3905_gpt_pro_v2/post_ids_by_type.json`
- `src/llm_batch/models.py`
- `src/llm_batch/batch_context.py`
- `src/llm_batch/slang_db.py`
- `src/llm_batch/prompts/prompt_router.py`

주의:

- `agbrowse web-ai send --model pro --effort extended`는 ChatGPT UI model selector를 찾지 못해 requested model/effort 강제 확인이 실패했다. 세션은 ChatGPT에서 완료됐고 context zip은 정상 인식했지만, 이 문서는 “ChatGPT Pro 강제 검증 완료”가 아니라 “ChatGPT web-ai 심층 분석 결과”로 보존한다.
- 후속 재실행에서 `--model pro --effort extended --research deep`를 사용했고, 전송 전 UI snapshot에서는 `Pro 확장 모드`가 보였다. 그러나 `agbrowse`는 reasoning effort selector를 직접 찾지 못했고, 응답 본문도 실제 Deep Research/API 실행 상태가 아니라 zip 기반 정적 분석이라고 고지했다. 재실행 증거와 결과는 `docs/devs/GPT_PRO_DEEP_RESEARCH_RERUN_20260614.md`에 별도로 보존한다.
- 3905 judge라고 부르지만 실제 완료 집계는 `3874 / 3874` posts, `155 / 155` batches다.
- 이 head slice judge는 full scan approval 근거가 아니라 seed/diagnostic 근거다.

## 1. 핵심 결론

GPT 분석의 가장 중요한 결론은 다음 한 문장이다.

> 후보 보존 recall은 넓게, `official_title` promotion은 좁게.

즉 `under_resolved_false_negative` 644건을 줄인다고 바로 `official_title`을 더 많이 채우면 안 된다. 먼저 `candidate_ledger`, `title_candidates`, `entity_mentions`, `is_novel_related=true`, `title_resolution_state=unresolved_matchable` 같은 중간 상태를 넓혀야 한다. 반대로 `official_title` 승격은 direct hard anchor, media-domain evidence, relation-to-post attribution을 통과한 후보로 제한해야 한다.

## 2. Root Cause Hypotheses

| failure axis | GPT hypothesis | repo locus |
|---|---|---|
| `under_resolved_false_negative=644` | 후보 생성 실패와 promotion 차단이 섞여 있다. 후보가 없었는지, 있었지만 guard가 막았는지 분리해야 한다. | `Decoder`, `Verifier`, `AgenticPipeline._try_promote_best_candidate`, `title_candidates` |
| `wrong_discussion_type=549` | schema는 분리되어 있으나 final output/lint가 `discussion_type`, `topicality`, `work_resolution`을 안정적으로 정렬하지 못한다. | `models.py`, Arbiter/final shaping, output consistency lint |
| `wrong_relevance=169` | `is_relevant=false` legacy core boolean과 `is_novel_related/adjacent_relevant`가 충돌한다. 추천/작가/플랫폼/장르 메타가 noise로 낙하한다. | `PickvelIdentity`, `prompt_router.py`, final identity contract |
| `cross_media_or_famous_mismatch=52` | “작품 존재 증거”와 “웹소설 primary work 증거”가 분리되지 않는다. | media-domain gate, search evidence catalog |
| `wrong_work=39` | 후보 역할 attribution이 약하다. 댓글 추천작, 비교작, 배경 검색 이웃이 primary subject로 승격된다. | candidate evidence bucket, relation judge, `DetectedTitle.reference_role` |
| `over_resolved=22`, `garbage_title=10` | title string hygiene와 promotion decision이 분리되어 있지 않다. | `official_title_lint`, `TitlePromotionPolicy`, `slang_db` generic filters |
| `title_noisy_ocr=20` | OCR surface와 verified official title이 같은 슬롯으로 합쳐진다. | image evidence catalog, OCR candidate quarantine |

## 3. P0 Goal Tree

### P0.1 Judge Seed Registry

목표: GPT Pro judge 결과를 실행 가능한 seed registry로 고정한다.

Acceptance criteria:

- `under_resolved_false_negative` 644건을 recall seed로 등록한다.
- `cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title` 총 123건을 precision seed로 등록한다.
- `wrong_discussion_type=549`, `wrong_relevance=169`, `title_noisy_ocr=20`을 hygiene/OCR seed로 등록한다.
- report는 항상 `head_slice_seed_metric`과 `full_scan_approval`을 분리한다.

### P0.2 Candidate Retention Without Promotion

목표: false negative를 바로 resolved title로 올리지 않고 후보 보존율부터 높인다.

Acceptance criteria:

- recall seed의 최소 90%가 `resolved`, `hold_unresolved`, `reject_with_reason` 중 하나로 분류된다.
- 후보가 없었던 케이스는 `candidate_generation_miss`, 후보는 있었지만 막힌 케이스는 `promotion_blocked`로 분리된다.
- precision seed 123건에서 direct hard anchor 없는 신규 `official_title` 승격은 0건이어야 한다.

### P0.3 Title Promotion Hard Gate

목표: `official_title` 승격을 deterministic policy로 통제한다.

Acceptance criteria:

- `cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title` seed에서 `official_title`이 남으려면 `direct_anchor_type != none`이고 `media_domain_class`가 webnovel 계열이어야 한다.
- no-work/context-only + official detail URL/search title match 단독이면 `hold` 또는 `reject`다.
- URL/도메인/일반어/문장형/OCR 노이즈는 `garbage_title_lint` 또는 `title_noisy_ocr`로 막힌다.

### P0.4 Output Consistency Lint

목표: 다량의 discussion/relevance drift를 title resolution과 분리해서 자동 감사한다.

Acceptance criteria:

- `title_resolution_allowed=false`인데 `official_title`이 있으면 lint error.
- `work_resolution=none`인데 `official_title`이 있으면 lint error.
- `is_relevant=false`인데 core discussion type이 있으면 lint warning 또는 자동 정정.
- `topicality=adjacent_relevant`인데 `is_novel_related=false`이면 lint warning.
- lint 결과는 `consistency_flags` 또는 별도 review artifact에 남는다.

## 4. P1 Goal Tree

### P1.1 Candidate Ledger

목표: 모든 후보를 role/evidence와 함께 보존한다.

권장 field:

```text
candidate_ledger:
  surface:
  normalized_surface:
  candidate_title:
  source_location: title | body | comment | image_ocr | image_vlm | search | batch_memory
  source_role: primary_surface | mentioned | comparison | recommendation | background_search | alias_hint
  reference_role: primary | mentioned | comparison_target | recommendation_candidate | secondary_reference | background_search_hit | ocr_surface
  relation_to_post: primary_subject | reference_only | comparison_only | recommendation_only | context_only | unknown
  direct_anchor_type:
  media_domain_class:
  negative_evidence:
```

Acceptance criteria:

- `wrong_work` 39건에서 primary subject attribution diff가 자동 출력된다.
- `recommendation_candidates`, `comparison_target`, `mentioned_works`가 primary로 승격된 케이스를 high-risk expansion이 잡는다.

### P1.2 Alias Lifecycle Governance

목표: `BatchContext`/`slang_db`를 정답 사전이 아니라 evidence lifecycle manager로 운영한다.

권장 lifecycle:

```text
observed_surface -> candidate_hint -> pending_alias -> verified_alias -> promotable_alias
```

Acceptance criteria:

- `slang_insight` 단독 관측은 바로 promotable이 될 수 없다.
- `slang_db_alias_seed_is_safe()`가 false인 entry는 BatchContext preload 금지.
- affix-stripped alias match는 기본적으로 `candidate_hint`이며, no-work/context-only에서는 direct hard anchor 없으면 `hold_unresolved`.
- non-novel media 오염은 hardcoded blocklist 확장이 아니라 `media_domain_class` quarantine으로 처리한다.

### P1.3 Search/VLM/OCR Evidence Catalog

목표: evidence existence와 primary-subject support를 분리한다.

Search catalog field:

```text
search_hit:
  title:
  url:
  source_tier:
  page_type:
  media_domain_class:
  matched_surface:
  matched_span_location:
  is_official_detail:
  is_community_or_review_namespace:
  supports_existence:
  supports_primary_subject:
```

Image catalog field:

```text
image_evidence:
  image_index:
  fetch_status:
  ocr_status:
  vlm_status:
  screenshot_alignment:
  candidate_titles:
  primary_work_anchor:
  limitations:
```

Acceptance criteria:

- OCR-only + official source 없음은 `ocr_explicit_title_unresolved`.
- OCR title + official detail 정렬 + no negative media일 때만 resolved 가능.
- `title_noisy_ocr` 20건 seed에서 OCR 오염 문자열이 `official_title`로 남는 케이스 0건.

## 5. P2 Refactor Direction

장기적으로 `agentic_pipeline.py` 후단을 다음 모듈로 분리한다.

```text
candidate_ledger.py
evidence_attribution.py
promotion_policy.py
identity_lint.py
review_queue.py
```

목표는 바로 동작 변경이 아니라 shadow output/diff 기반의 점진적 이행이다.

Acceptance criteria:

- 각 모듈은 seed test를 독립 실행할 수 있다.
- 기존 output과 신규 shadow output diff가 batch 단위로 저장된다.
- full scan approval report는 “모집단 품질 추정”, “seed regression”, “source-grounded subset”, “image subset”을 분리한다.

## 6. Experiment Plan

Seed groups:

- Recall: `under_resolved_false_negative` 644건.
- Precision: `cross_media_or_famous_mismatch` 52, `wrong_work` 39, `over_resolved` 22, `garbage_title` 10.
- Hygiene: `wrong_discussion_type` 549, `wrong_relevance` 169.
- OCR: `title_noisy_ocr` 20.

Ablation:

1. `A0 baseline`: current pipeline.
2. `A1 candidate retention only`: 후보 보존만 추가.
3. `A2 promotion hard gate only`: title promotion만 strict.
4. `A3 schema/lint only`: output consistency lint만 적용.
5. `A4 alias governance only`: BatchContext/slang_db seed policy만 변경.
6. `A5 OCR/browser evidence gate only`.
7. `A6 combined P0`.
8. `A7 combined P0+P1 shadow`.

Metrics:

- `recall_seed_candidate_retention_rate`
- `recall_seed_safe_resolution_rate`
- `precision_seed_false_promotion_rate`
- `no_work_gate_violation_count`
- `garbage_title_lint_escape_count`
- `cross_media_resolved_count`
- `wrong_role_primary_promotion_count`
- `discussion_type_lint_violation_rate`
- `random_baseline_high_error_rate`

Random baseline:

- full scan 104,502에서 random 1,000.
- image 포함 oversample 300.
- 댓글 많은 post oversample 300.
- 짧은 title/body oversample 300.
- platform URL 포함 oversample 200.
- head slice agreement bucket에서 300.

## 7. Immediate Next Actions

1. `post_ids_by_type.json`에서 seed registry JSON을 생성하는 도구를 만든다.
2. `official_title_lint`를 `slang_db.py`의 generic/sentence-like/low-information 필터를 재사용해 별도 utility로 뽑는다.
3. `identity_consistency_lint`를 추가해 current result와 judge seed에 대해 dry-run 리포트를 생성한다.
4. `candidate_ledger` shadow artifact 설계를 시작한다. 첫 단계는 final output 변경 없이 expert output에서 후보/role/evidence를 수집하는 것이다.
5. 1주 P0 ablation을 먼저 돌리고, P1 alias lifecycle 변경은 shadow metric이 생긴 뒤 진행한다.
