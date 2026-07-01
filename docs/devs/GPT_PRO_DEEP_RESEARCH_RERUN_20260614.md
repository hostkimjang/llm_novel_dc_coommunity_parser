# GPT Pro Deep Research Rerun - 2026-06-14

작성: 2026-06-14

## 1. 실행 결론

이번 재실행은 `agbrowse web-ai send`에 `--model pro --effort extended --research deep`를 붙여 ChatGPT에 전송했다. 전송 자체와 응답 수집은 성공했지만, 결과는 "검증된 GPT Pro Extended Deep Research"로 확정하지 않는다.

판정:

- ChatGPT 로그인 상태: 확인됨.
- 전송 전 화면 모델 pill: `Pro 확장 모드`로 확인됨.
- `agbrowse` 전송: 성공, session `01KV31C9QFS5YN3SZF7BBJNHZ9`.
- conversation URL: `https://chatgpt.com/c/6a2e9d3e-458c-83ee-b3ea-5485161b92e8`.
- 사용 context zip: `out/gpt_pro_deep_research_context_20260614_2.zip`.
- 응답 저장: `out/agbrowse_deep_research_poll_20260614.json`.
- 전송 로그: `out/agbrowse_deep_research_send_20260614.log`.
- caveat: `agbrowse`가 reasoning effort selector를 직접 찾지 못해 `extended` 강제 확인에는 실패했다.
- caveat: ChatGPT 응답 본문도 "실제 Pro Extended / Deep Research API 실행 상태가 아니라 로컬 zip 기반 정적 분석 환경"이라고 고지했다.

따라서 이 문서는 "Deep Research 요청 플래그로 재실행한 ChatGPT Pro 탭 기반 zip 분석 결과"로 보존한다. 이후 보고서나 의사결정에서 "검증된 Deep Research 완료"라고 쓰지 않는다.

## 2. 실행 증거

전송 명령의 핵심 옵션:

```powershell
node $agb web-ai send `
  --vendor chatgpt `
  --url https://chatgpt.com/ `
  --new-tab `
  --model pro `
  --effort extended `
  --research deep `
  --file out/gpt_pro_deep_research_context_20260614_2.zip `
  --allow-copy-markdown-fallback `
  --timeout 3600 `
  --json
```

전송 결과:

- `ok=true`
- `status=sent`
- `sessionId=01KV31C9QFS5YN3SZF7BBJNHZ9`
- `model selected: pro (already selected)`
- warning: `reasoning effort extended was not enforced: ChatGPT reasoning effort selector not found for pro`

수집 결과:

- `ok=true`
- `status=complete`
- `usedFallbacks=["copy-markdown"]`
- `responseStableMs` 약 31.6초
- URL: `https://chatgpt.com/c/6a2e9d3e-458c-83ee-b3ea-5485161b92e8`

## 3. 투입 자료

수동 zip으로 묶은 주요 파일:

- `docs/devs/LLM_JUDGE_ANALYSIS_SPEC_FOR_CODEX.md`
- `docs/devs/JUDGE3905_REPORT.md`
- `docs/devs/GPT_PRO_PIPELINE_RESEARCH_CONTEXT_20260614.md`
- `docs/devs/GPT_PRO_PIPELINE_RESEARCH_DIRECTIONS_20260614.md`
- `out/_judge3905_gpt_pro_v2/_result.json`
- `out/_judge3905_gpt_pro_v2/post_ids_by_type.json`
- `out/_judge3905_gpt_pro_v2/post_reviews.jsonl`
- `out/expert_result_20260612_160543_315727_manifest.json`
- `out/expert_result_20260612_160543_315727_completed_subset.json`
- `out/expert_result_20260612_160543_315727_pending_snapshot.json`
- `src/llm_batch/models.py`
- `src/llm_batch/batch_context.py`
- `src/llm_batch/slang_db.py`
- `src/llm_batch/prompts/prompt_router.py`

`agbrowse web-ai context-dry-run`은 `508833/196000` tokens로 over-budget이어서 자동 context package 대신 zip 파일 업로드를 사용했다.

## 4. 재실행 응답의 핵심 내용

ChatGPT 응답은 기존 방향성 문서와 대체로 같은 결론을 냈다. 단, 이전 문서의 "candidate-ledger / promotion-policy" 표현보다 더 단순한 "entity recovery pipeline" 관점으로 압축했다.

주요 문제:

- `under_resolved_false_negative=644`가 가장 큰 recall 붕괴 축이다.
- `wrong_discussion_type=549`는 entity는 찾았지만 taxonomy가 흔들린 classification 축이다.
- `wrong_relevance=169`, `wrong_work=39`, `cross_media_or_famous_mismatch=52`, `over_resolved=22`, `garbage_title=10`, `title_noisy_ocr=20`은 recall 보강과 precision guard를 동시에 요구한다.
- 현재 시스템은 단순 분류기라기보다 `entity recovery + disambiguation system`으로 다뤄야 한다.

즉시 개선 제안:

- title/comment/OCR fragment를 후보로 보존하는 recall trigger expansion.
- multi-IP/cross-media 후보는 단일 canonical work로 즉시 확정하지 않는 guardrail.
- confidence threshold 이하 canonicalization 금지.
- `slang_db`와 `BatchContext`의 alias/context 정보를 분리 저장이 아니라 연결 구조로 다루기.
- `prompt_router`에서 no-work rescue path를 별도 routing/policy 단계로 분리.

로드맵:

- 2주: recall trigger, slang/context merge, cross-media guardrail, OCR/title promotion rule.
- 4주: routing redesign, entity resolution module 분리, prompt_router policy engine화.
- 8주: retrieval/entity graph, judge-driven self-training loop, dashboard/human review loop.

## 5. 기존 방향성 문서와의 차이

기존 `GPT_PRO_PIPELINE_RESEARCH_DIRECTIONS_20260614.md`는 더 실행 가능한 형태의 P0 goal tree를 제시했다.

- seed registry
- candidate retention without promotion
- title promotion hard gate
- output consistency lint
- ablation matrix

이번 재실행 응답은 더 상위 레벨이다.

- recall collapse
- entity recovery/disambiguation
- routing redesign
- slang/context merge
- dashboard/human loop

따라서 구현 지시에는 기존 방향성 문서를 계속 1차로 쓰고, 이번 재실행은 그 방향이 크게 틀리지 않았음을 확인한 보조 근거로 둔다.

## 6. Codex 다음 구현 방향

P0 구현은 다음 순서가 적절하다.

1. `post_ids_by_type.json`과 `post_reviews.jsonl`에서 seed registry를 생성한다.
2. `under_resolved_false_negative`는 바로 `official_title`로 승격하지 않고 `candidate_ledger` shadow artifact로 먼저 보존한다.
3. `cross_media_or_famous_mismatch`, `wrong_work`, `over_resolved`, `garbage_title`는 promotion hard gate regression set으로 묶는다.
4. `wrong_discussion_type`, `wrong_relevance`, `title_noisy_ocr`는 output consistency lint와 OCR/title quarantine regression set으로 묶는다.
5. 이후 `official_title_lint`, `identity_consistency_lint`, `candidate_generation_miss` vs `promotion_blocked` 분류를 구현한다.

## 7. 남은 한계

- 이번 산출물은 post-by-post 전수 재판정이 아니다.
- Deep Research 플래그는 사용했지만, UI/응답 증거 기준으로 검증된 Deep Research 완료라고 보지 않는다.
- ground truth가 없으므로 judge 결과는 approval metric이 아니라 regression seed다.
- `3905`라는 이름과 달리 실제 완료 집계는 기존 보고서 기준 `3874 / 3874` posts다.
- full 104k population으로 성능 수치를 환산하지 않는다.
