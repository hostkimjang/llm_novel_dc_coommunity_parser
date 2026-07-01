# Scan Result Review Guide

스캔 결과 디렉터리를 받았을 때 런타임 안정성, 검색 품질, 최종 판단 품질, `slang_db` 품질을 분리해서 리뷰하기 위한 운영 지침이다. 이 문서는 특정 런 하나를 잘 읽는 것보다, 반복 가능한 리뷰 절차와 이슈 전환 기준을 고정하는 데 목적이 있다.

## 1. 작업 모드

- `GUIDE_MODE`: 재사용 가능한 리뷰 지침, 체크리스트, 이슈 템플릿을 설계한다. 사용자가 scan result directory를 제공하지 않았으면 기본 모드다.
- `RUN_REVIEW_MODE`: 사용자가 제공한 특정 scan result directory를 실제 분석한다.
- `MIXED_MODE`: 특정 런 분석 결과를 바탕으로 리뷰 지침과 문서 개선안을 함께 작성한다.
- `QUALITATIVE_SEMANTIC_REVIEW_LOOP`: 자동 감사 이후 자연어 판정 품질을 별도 루프로 검토한다. `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`를 따른다.
- 대형 scan review에서는 `run integrity`, `semantic/VLM/browser`, `slang_db/BatchContext`, `runtime/shard/process`처럼 독립 축을 Codex `spawn_agent` subagent로 기본 병렬 검토한다. 단, random/high-risk label과 최종 `GO/REVIEW/NO-GO` gate는 메인 Codex가 통합해 한 번만 판정한다.

## 1-1. Codex goal 전문 subagent 병렬 운영

이 절은 Codex 앱의 goal 진행 방식에 대한 지침이다. repo 내부 `expert_main.py --parallel`, 내부 LLM 전문가 호출 수, shard/worker 수를 늘리라는 뜻이 아니다.

- 사용자가 goal 작업에서 "subagent", "여러 전문가", "병렬 검토"를 말하면 기본 해석은 Codex `spawn_agent` 기반 분업이다.
- 이 경우 메인 Codex는 먼저 subagent 분해 축을 선언하고 실제 subagent를 배정한다. `expert_main.py --parallel` 값을 늘리거나 같은 small run을 반복 실행하는 것으로 대체하지 않는다.
- 메인 Codex는 coordinator로 남아 작업 분해, write-scope 배정, subagent 결과 통합, 최종 gate 판정을 맡는다.
- subagent는 서로 독립적인 축만 맡긴다. 예: `run integrity/manifest`, `runtime/shard/process`, `semantic/VLM/browser`, `slang_db/BatchContext`, `prompt/orchestration limits`, `docs/checklist sync`.
- 여기서 "전문가 subagent"는 Codex goal 운영의 별도 검토자다. repo 내부 `src/llm_batch/experts/*` 전문가 체인, `expert_main.py` worker, shard 수, `--parallel` 값과 같은 실행 병렬도와 섞지 않는다.
- 10만 건/대량 semantic review 또는 targeted rerun을 goal로 진행할 때는 기본적으로 아래 축을 병렬로 띄운다.
  - `source/preflight` 전문가: 원본 result, checkpoint, manifest, 입력 JSONL, post/comment metadata, 중복 제거와 source completeness를 확인한다.
  - `runtime/shard/process` 전문가: `requested_parallel`, `effective_parallel`, shard/endpoint health, VLM/OCR 옵션, `reuse-shards-only`, completion/flush/pending 정합성을 확인한다.
  - `semantic/gate` 전문가: random baseline과 high-risk bucket을 분리하고, search-only/intent permit/final semantic reread/candidate drift를 라벨링한다.
  - `VLM/OCR/browser/comment` 전문가: image evidence catalog, Browser image loading counter, screenshot, `content_blocks`, comment attribution/dialogue evidence를 확인한다.
  - `slang_db/BatchContext` 전문가: alias provenance, saved/blocked/pending/family/noise, BatchContext rescue와 public display 상태를 분리한다.
  - `prompt/orchestration/hardcode` 전문가: 후단 rescue 우회, prompt wording drift, hardcoded alias registry, output hygiene를 감사한다.
  - `docs/checklist/gate` 전문가: 가이드/TODO/CHECKLIST 반영 여부와 `runtime GO`, `targeted canary GO`, `10만 semantic REVIEW-LOCKED/NO-GO` 분리를 확인한다.
- subagent 보고는 그대로 승인하지 않는다. 메인 Codex가 보고된 파일 경로, line, `post_id`, `run_id`, manifest/checkpoint/review packet 근거를 직접 다시 열어 확인한 뒤, 확인된 증거만 `GO/REVIEW/NO-GO` gate에 반영한다.
- random baseline과 high-risk oversample은 계속 분리 보고한다. 같은 `post_id`가 양쪽에 보여도 gate 표와 오류율을 합산하지 않고, baseline 대표성과 high-risk 재발률을 따로 기록한다.
- 브라우저/VLM/OCR 사례는 이미지 로딩 상태와 직접 시각 증거를 별도 gate로 둔다. 텍스트 match, OCR 문자열, subagent 요약만으로 `Strong` evidence나 semantic `GO`를 열지 않는다.
- 이미지 로딩 실패/대기 상태에서 resolved title, OCR/reason, search-only/text match가 결론 근거로 쓰이면 `image_loading_failed_or_pending_text_match_used` issue로 기록한다.
- 입력/리뷰 packet의 이미지 block은 `url`, `image_url`, `src`를 모두 동등한 image URL alias로 취급한다. 원본에 이미지 URL alias가 있는데 manifest의 `image_post_count=0`이면 VLM/OCR gate evidence missing으로 보고 loader/source 보존을 먼저 감사한다.
- 472건 initial triage, random baseline 1000/2400, high-risk expansion, targeted canary는 source와 목적이 다르다. 표본 수와 label 분포는 `run_id`, source path, bucket별로 분리 기록하고 서로 섞어 전체 오류율이나 승인 근거처럼 말하지 않는다.
- Codex subagent 병렬 검토 완료, runtime `GO`, targeted canary `GO`는 모두 semantic approval과 별개다. completed VLM/OCR-on source, fail-on-locked preflight, random baseline, P0/P1 expansion, Browser visual/image-loading gate가 닫히기 전까지 10만 gate는 `NO-GO / REVIEW-LOCKED`다.
- completed source 후보가 불명확하면 `tools/build_completed_source_candidate_audit.py --manifest-root out --random-target 1000`로 먼저 후보를 감사한다. 후보 감사 `GO/REVIEW`는 approval이 아니라 `preflight_qualitative_large_scale_review.py --fail-on-locked`를 실행할 입력 후보가 있는지 확인하는 단계다.
- 읽기 전용 explorer는 파일을 수정하지 않고 evidence gap, blocker, 다음 action만 보고한다.
- 작은 targeted rerun은 범위에 맞춰 위 축을 3~4개로 줄일 수 있지만, `expert_main.py --parallel`을 높이는 것을 Codex subagent 검토 보강으로 취급하지 않는다.
- subagent 검토가 부족하면 Codex `spawn_agent` 축과 담당 scope를 늘린다. runtime worker, shard count, 내부 LLM 전문가 호출 수를 늘리는 것은 별도 runtime 최적화일 뿐 리뷰 병렬 보강이 아니다.
- Codex worker-type subagent를 쓸 때는 담당 파일/모듈을 명시하고, 다른 subagent나 사용자의 변경을 되돌리지 않는다.
- 같은 문제를 여러 subagent가 중복 구현하게 하지 않는다. 메인 Codex는 즉시 필요한 blocking patch를 직접 맡고, 병렬 subagent에는 sidecar audit, disjoint implementation, 문서 위치 점검처럼 독립 업무를 준다.
- 메인 Codex가 코드를 직접 패치하는 동안 subagent는 같은 파일을 수정하지 않는 읽기 전용 감사 축으로 둘 수 있다. 이 경우 subagent finding은 다음 패치 후보이며, 현재 패치와 충돌하지 않게 메인 Codex가 재확인 후 반영한다.
- subagent 결과는 한국어로 요약하고, 최종 산출물에는 어떤 축을 누가 봤는지와 메인 Codex의 통합 판정을 분리해 남긴다.
- Codex subagent 병렬 운영 성공은 scan 결과 semantic approval이 아니다. runtime `GO`, targeted canary `GO`, semantic approval `REVIEW-LOCKED`를 계속 분리한다.

### 1-2. Subagent 보고 계약

각 Codex subagent 보고는 한국어로 작성하고 아래 필드를 포함한다. JSON key, enum, 파일명, 명령어, 코드 심볼은 원문을 유지할 수 있다.

- `role`: 담당 축.
- `scope`: 읽은 파일, 디렉터리, packet, post_id, run_id 범위.
- `write_scope`: `read_only` 또는 명시된 disjoint write scope.
- `evidence_refs`: file path, line, post_id, run_id, packet_id, manifest/checkpoint field.
- `findings`: 확인된 사실과 재현 가능한 관측.
- `blockers`: `Missing`/`Weak` evidence 또는 gate blocker.
- `proposed_action`: `no_action`, `re_search`, `re_judge`, `re_run`, `human_review`, `slang_db_review`, `docs_issue`.
- `gate_effect`: `GO`, `REVIEW`, `NO-GO`, `REVIEW-LOCKED` 제안. 최종 gate가 아니라 메인 Codex 통합 입력이다.
- `no_revert_confirmation`: 다른 worker/사용자 변경을 되돌리지 않았는지.

병렬 검토를 수행한 라운드는 아래 산출물을 남긴다.

- `qualitative_review/<run_id>/subagent_review_manifest.json`: subagent role, assigned scope, read/write scope, inspected files, output path, main verification status.
- `qualitative_review/<run_id>/subagent_review_summary_ko.md`: subagent별 요약, 메인 Codex 재확인 결과, gate 반영 여부.

## 2. 필수 참고 문서

리뷰 시작 전 아래 문서를 확인한다.

- `docs/devs/LLM_JUDGMENT_REVIEW.md`
- `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`
- `docs/devs/OPERATION_QUALITY_CHECKLIST.md`
- `docs/devs/IMPROVEMENT_REGISTER.md`
- `docs/slang_db_improvement_todo.md`
- `docs/devs/VERIFICATION_RESULTS.md`
- `docs/devs/HISTORY.md`
- `docs/devs/TODO.md` 또는 `docs/devs/FEATURE_IMPROVEMENT_TODO.md`

## 3. 필수 입력

- scan result directory
- manifest: `out/*manifest*.json`
- checkpoint JSONL: `out/*checkpoint*.jsonl`
- run audit JSON: `out/run_audit_*.json`
- expert run log: `logs/expert_run_*.log`
- comparison output: `out/comparisons/*.md`, `out/comparisons/*.json`
- LLM judgment review packet: `out/llm_judgment_reviews/*`
- run 당시 `slang_db` snapshot
- 현재 repo의 `slang_db/slang_db.json`

누락 파일은 생략하지 말고 `Missing` evidence로 기록한다.

## 4. 증거 정책

- 재해독 active wording은 `표현 오타/축약 패턴(범용)`로만 쓴다. 특정 표면형을 어떤 정상 표현으로 읽는다는 문장, 특정 계열 자동 차단/허용 규칙, `X -> Y` 복원은 새 reason/prompt/report에 쓰지 않는다.
- `표현 오타/축약 패턴(범용): X; Y`처럼 label 뒤에 표면값이나 복원 payload를 붙이지 않는다. 공개 reason/report는 `표현 오타/축약 패턴(범용)은 packet-local 원문 재검토 신호`처럼 경계만 남긴다.
- 오타/축약 재해독은 hardcoded alias 규칙이나 특정 post/string 전용 예외가 아니다. packet의 title/body/comment/comment_dialogue를 다시 읽는 범용 자연어 이해 신호이며, 직접 title/alias/evidence와 결합될 때만 작품 판정 검토에 쓴다.
- 검색 전 intent permit을 확인한다. `community_banter`, `trope_discussion`, `author_talk`, `recommendation`, 친구/일상 한탄류 intent는 직접 작품명/별칭/작가+작품/이미지 OCR 직접 제목/회차/플랫폼 작품 URL 없이는 `resolved_title` 확정 근거가 아니다.
- 검색 이후 후보 생성과 검색 기반 support/stability 판정도 같은 intent permit을 다시 적용한다. title-lead alias나 search-inferred alias가 있어도 semantic seed가 no-work/intent-denied이면, 원문 직접 title mention이나 직접 이미지/플랫폼 작품 앵커 없이 support score, stability signal, candidate pool에 넣지 않는다.
- `semantic_seed_review`, `discourse_semantic_seed_guard`, `final_semantic_reread`, `title_resolution_allowed=false`, `title_resolution_state=context_only` 또는 동등 공개 필드가 no-work/context-only/intent-denied를 표시한 경우, 후단 `search`, known alias, `slang_db`, `BatchContext`, canonical/deliberation rescue는 direct hard anchor 없이 `resolved_title`을 되살릴 수 없다.
- 여기서 no-work/context-only 해제용 direct hard anchor는 원문 title/body/comment의 직접 작품명/안정 별칭, VLM/OCR 직접 작품명, verified character-work link처럼 packet-local 직접 작품 표면이다. 회차/스포/작가의 말, 검색 결과, 공식 URL은 작품 존재/맥락 보조 증거일 수 있지만, 위 직접 근거와 결합되지 않으면 no-work/context-only 발화 의도를 자동으로 특정 작품 토론으로 바꾸는 증거가 아니다.
- decoder `original` 약칭, snippet abbreviation mapping, canonical lock, stable-hold rescue는 원문 raw title mention이 아니다. semantic no-work/context-only 상태에서는 raw title surface, 직접 이미지 제목/OCR/프로모션, 검증된 character-work link 없이 이런 후단 alias/canonical 신호만으로 `Strong` support나 resolved title을 되살리지 않는다.
- 후단 최종 검증기, 후보 승격, unresolved 단일 후보 승격, recommendation guard 해제도 같은 no-work 단조성 gate를 따른다. official detail URL, canonical convergence, Decoder alias mapping, episode ref 단독은 no-work/context-only 해제용 direct hard anchor가 아니다.
- no-work/context-only 해제 여부를 볼 때 `_title_mentioned_in_post_main_context()`처럼 Decoder alias를 포함할 수 있는 helper 결과만으로 직접 언급이라고 보지 않는다. raw post surface 또는 VLM/OCR/verified link 같은 packet-local direct evidence가 필요하다.
- curated title abbreviation이 final title을 올바르게 회복해도, 같은 packet의 후보 목록에 원문 main context 미언급 인접 파생 후보가 남으면 `curated_alias_adjacent_candidate_pollution`으로 분리한다. 충돌 후보가 raw title/body/comment에 없고, alias support도 없고, verified character-work link도 없으면 `title_candidates`, `mentioned_works`, `secondary_reference_works`에 confirmed work처럼 남기지 않는다.
- no-work semantic seed가 있으면 회차/스포/작가의 말 같은 표현만으로 curated abbreviation promotion을 다시 열지 않는다. direct title surface, 직접 이미지/OCR 작품 표면, 강한 character-work link처럼 별도 독립 앵커가 있어야 한다.
- curated abbreviation은 원문에 보이는 alias surface여야 한다. 짧은 alias가 일반 단어 내부 substring으로 우연히 들어간 경우에는 `known_abbreviation_alias`, abbreviation stability, promotion 근거로 쓰지 않는다.
- Agentic direct promotion, abbreviation stability, title lock도 같은 규칙을 따른다. 등록 약칭 surface가 보여도 post-side work anchor 또는 compound title-character bridge가 없으면 `High`, stability, lock을 열지 않는다.
- post-side work anchor가 있어도 registry alias만으로 `High` final rescue를 열지 않는다. `High`에는 official/detail URL, fetched official title, 원문 full title 직접 표면, VLM/OCR direct work title, verified character-work link 같은 독립 hard support가 추가로 필요하다.
- registry surface + work anchor만 있는 경우는 `registry_anchor_only`, `weak_evidence_but_strong_resolution`, `hardcoded_alias_confidence_overreach` 후보로 라벨링하고 `Medium/HOLD/re_judge` 범위에서 검토한다.
- `registry_anchor_only`, `promotion_confidence`, `confidence_demoted_without_hard_evidence`는 최종 output/reason/review packet에서 유지되어야 한다. packet에 `alias_resolution_sources`가 없으면 provenance missing으로 보고 approval 근거로 쓰지 않는다.
- `_apply_known_abbreviation_title_guard()` 같은 후단 title rewrite도 registry alias + suspected/decoder/search 반복만으로 열면 안 된다. hardcoded registry source rewrite에는 official/detail/direct hard support가 필요하다.
- title-lead alias search inferred candidate가 비공식 search/wiki/community 반복으로 만들어졌다면 score가 높아도 `High`가 아니라 `Medium`이다. `source_tier != official_detail`인 inferred candidate를 Strong evidence로 보지 않는다.
- `weak_evidence_but_strong_resolution` row가 `registry_anchor_only` provenance를 갖고 있으면 기본 label은 `HOLD/re_judge`다. 이 row를 random/control 전체 품질의 `ACCEPT`로 섞지 않는다.
- comment-only known title abbreviation은 attribution/대화 맥락 review 대상일 수 있지만 단독 title lock 근거가 아니다.
- 등록 약칭 surface 발견은 `post_main_mention`이 아니다. 실제 full title이 원문 title/body/comment에 직접 보일 때만 `post_main_mention`으로 본다.
- Agentic alias support helper는 `known_abbreviation_alias`와 `curated_alias_work_anchor`를 분리해야 한다. surface만 있고 work anchor가 없으면 `alias_support=false`, `explicit_title_support=false`가 맞다.
- Arbiter `multi_work`, `meme/noise`, `low-confidence`, title veto exception도 Registry Alias Evidence Rule 적용 대상이다. registry hit만 있으면 guard exception 근거로 보지 않고 `HOLD/REJECT/re_judge` 후보로 둔다.
- Arbiter guard exception이 열렸다면 정식 title 직접 표면, verified character-work link, 등록 약칭 surface + post-side work anchor, non-character decoder/verifier anchor support 중 무엇으로 열렸는지 packet/reason/log에서 확인한다.
- `title_abbrev_mention` / `body_abbrev_mention`만 있고 post-side work anchor가 없으면 actual Arbiter decision-path에서도 `multi_work`, `meme/noise`, `low-confidence` guard 면제 근거로 보지 않는다. 공식 검색 결과가 있더라도 이는 작품 존재 증거이지 no-work/context-only 발화 의도 전환 증거가 아니다.
- 비교/나열/추천 질문에서 여러 작품 후보가 보이면 단일 `official_title` 강제승격보다 `multi_work_guard` 또는 보류가 우선이다. 등록 약칭은 회차/스포/캐릭터/줄거리 같은 packet-local 작품 앵커와 결합될 때만 예외 후보가 된다.
- Arbiter `_has_official_title_evidence()` 또는 동등 official evidence field는 공식 플랫폼 상세 URL과 fetched official detail title match가 직접 final title을 지지할 때만 Strong 후보로 본다. `known_abbreviation`, `KNOWN_*`, snippet abbreviation hint, deleted/unavailable page, community post, listing/search page는 official evidence가 아니다.
- 짧은 제목은 다른 공식 제목 내부 substring만으로 official evidence가 될 수 없다. token boundary 또는 동등한 raw direct surface가 없으면 `weak_evidence_but_strong_resolution` 또는 `HOLD/re_judge` 후보로 둔다.
- Jury/Debate/EvidenceScorer도 curated alias를 확정 근거로 쓰지 않는다. 등록 약칭은 recall hint이며, 독립 work anchor가 있을 때만 약한 보조 신호로 전달한다. `확정적`, `is_relevant=true`처럼 결론을 강제하는 prompt 문구는 금지한다.
- `SLANG_DICTIONARY`는 recall hint다. dictionary hit, `decoded_term`, `slang_dictionary_hint` candidate만으로 `official_title`, `resolved_title`, `best_match.title`, `confidence=high`를 확정하지 않는다. no-work가 아닌 상태의 독립 URL/플랫폼 + strict snippet, VLM-OCR 직접 제목, verified character-work evidence 없이 dictionary mapped title이 high로 남으면 `HOLD` 또는 후처리 null 대상이다. no-work/context-only 상태에서는 URL/search match 단독으로 dictionary mapped title을 되살리지 않는다.
- adjacent drift 검토에서 특정 작품군 토큰 묶음 hardcode나 공유 토큰 1~2개만으로 안전하다고 보지 않는다. decoder anchor conflict, 낮은 lexical overlap, 미언급 파생 후보가 있으면 `multi_work_or_adjacent_risk` 또는 `curated_alias_adjacent_candidate_pollution`으로 남긴다.
- final title이 맞더라도 `heretic_url=null`, `official_title_evidence=false`, 충돌 canonical suspect log, mixed/adjacent candidate가 함께 있으면 packet label은 `ACCEPT`가 아니라 `HOLD`다. 단건 canary run integrity `GO`와 semantic candidate hygiene `HOLD`를 분리한다.
- `search_only` evidence는 weak다. 검색 snippet이 비슷한 단어를 포함해도 원문 intent와 direct anchor가 없으면 `weak_evidence_but_strong_resolution`, `reason_overstates_context_only`, `intent_permit_missing_for_title_search` 후보로 기록한다.
- 결과 row에서 `search_only`, `official_search_only_without_post_anchor`, `search_only_title_promotion` 신호가 있는데 resolved title이 남으면 `search_only_resolved_title`로 기록한다.
- `search_only_resolved_title`은 원문 title/body/comment에 직접 title/안정 alias가 없고, official/platform detail evidence 또는 안정 `slang_db`/BatchContext provenance 없이 검색 결과만으로 final title을 세운 경우 hard approval blocker다.
- 단, 원문에 직접 title/안정 alias가 있고 official/platform detail URL, strict snippet/content match, stable alias provenance가 같은 final title을 별도로 지지하면 `search_only_resolved_title_review_only`로 낮춘다. 이 경우 search-only marker만으로 `REJECT/NO-GO`하지 않지만, packet-level human/quality confirmation 전에는 approval 근거도 아니다.
- `community_banter`, `trope_discussion`, `author_talk`, `recommendation` intent에서 resolved title이 남으면 `blocked_intent_resolved_title`로 기록한다. 단, `specific_work + hold/allow + direct anchor`가 같이 있으면 `*_review_only`로 낮춰 사람이 원문/evidence를 확인한다.
- comment author/IP/context는 대화 흐름 힌트다. `author_match_unverified` 또는 익명 동일 닉네임만으로 원글 작성자 발화나 독립 작품 evidence로 승격하지 않는다.
- 댓글 맥락이 resolved title 판정에 관여했는데 `comment_metadata`와 `comment_dialogue_context_lines`가 없으면 `comment_context_resolution_without_attribution`으로 분리한다. 이는 댓글 내용 자체의 진위 문제가 아니라 speaker attribution과 대화 흐름 검토 불가 상태다.
- `author_match_unverified`, `post_author_match_unverified` 신호가 있는 댓글 맥락은 작품명/별칭 direct evidence가 아니다. 해당 댓글 attribution이 final title의 유일하거나 주된 bridge이면 `comment_author_match_unverified_used_for_resolution` hard blocker로 두고 `HOLD/human_review` 또는 `REVIEW-LOCKED` 후보에 둔다.
- 단, comment-author attribution과 별개로 원문 title/alias, 검색 snippet/content, official/platform URL, stable alias provenance가 같은 final title을 독립적으로 지지하면 `comment_author_match_unverified_resolution_review_only`로 낮춘다. 이 경우 unverified author marker는 packet-level 확인 대상이지만 comment-author resolution hard blocker는 아니다.
- `comment_author_match_unverified_resolution_review_only` 같은 `REVIEW` 전용 coverage issue는 packet review label로 닫을 수 있다. label은 `post_id`, `issue_code`, `review_label=ACCEPT`, `action=no_action`, 한국어 근거를 포함해야 하며, 댓글 author 동일성이 final title의 필수 근거가 아니라는 독립 direct/official evidence를 밝혀야 한다. `REVIEW-LOCKED` hard blocker는 label로 닫지 않는다.
- 댓글이 Novelpia/Munpia/KakaoPage/Series/Joara 등 작품 상세 URL만 제공하는 추천 답변이면, 그 URL을 원글의 단일 final title로 자동 승격하지 않는다. 명시적인 제목 질문, 작성자 확인/감사, 댓글 답변 관계처럼 강한 title-answer 신호가 있을 때만 resolved title 복구를 허용한다. 다만 URL이 실제 작품 페이지로 확인되면 `noise/unrelated`로 낮추지 말고 `recommendation_request`, `adjacent_relevant`, `comment_url_candidate`, `recommendation_candidates` 같은 주변 작품 후보 맥락으로 보존한다.
- 댓글 URL이 실제 작품 페이지인지 확인되지 않았으면 `comment_url_verify`로 남기고, 확인되었는데도 output에 추천 후보/댓글 URL candidate가 없으면 `comment_url_recommendation_context_underclassified`로 기록한다.
- 검색 결과의 등장인물/캐릭터 페이지 제목은 원문 title/body/comment 직접 앵커가 아니다. verifier가 `community_banter` 또는 `promotion_decision=reject`로 본 짧은 캐릭터 반응에서 캐릭터명만 검색 결과에 연결되면 `character_page_rescue_blocked_by_verifier_veto` 또는 동등 issue로 남기고 resolved title 승격을 막는다.
- hardcoded alias registry가 관여한 packet은 `source_registry`, `alias_resolution_source`, `hardcoded_registry_name` 같은 provenance 필드를 확인한다. provenance 없이 `slang_db/BatchContext/search`와 섞이면 `HOLD/human_review`다.
- `tools/` 아래 coverage/audit용 `*_MARKERS` tuple은 runtime hardcoded alias registry가 아니다. 감사 도구가 이를 발견하면 `tooling_marker/INFO`로 분리하고, positive blocker에는 `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY`처럼 final title rescue/High 승격 경로에 닿는 runtime registry만 포함한다.
- hardcoded alias packet review는 raw artifact duplicate count와 unique post-context registry match count를 분리한다. 같은 post/alias가 여러 intermediate artifact에 반복되면 raw `matched_packets`를 approval blocker 기준으로 쓰지 말고 `unique_post_context_registry_match_count`와 후속 labels를 대조한다.
- LLM 전문가 출력의 `best_match`, `matched_alias`, `synthesis_summary`, `final_reasoning`은 판단 artifact이지 원문 direct evidence가 아니다. 원문 title/body/comment, evidence URL/snippet, VLM/OCR 추출 필드, 안정 `slang_db`/BatchContext hit와 분리해 본다.
- 특정 title이 원문에 직접 언급됐는지 볼 때는 이전 Decoder alias mapping으로 대신하지 않는다. raw title/body/comment strict match 또는 독립 evidence URL/snippet으로 확인한다.
- late title correction이 발생하면 final title, `heretic_url`, `official_title_evidence`, `official_urls` reason counter를 다시 맞춘다. title만 고치고 URL/evidence가 이전 상태에 머물면 `reason_evidence_state_mismatch`로 기록한다.
- `batch_memory_exact_alias_rescued` 같은 일반 exact alias rescue도 late title correction의 한 형태다. stable alias conflict/canonical base correction만 보지 말고 exact alias rescue 후 URL/evidence state도 확인한다.
- 공식 URL 검토 시 검색 result title만 보지 않는다. 플랫폼 검색 결과 title이 generic할 수 있으므로 URL이 작품 상세 페이지이고 snippet/content/description에 final title이 strict match되는지 확인한다. 단, validator/fetch가 실패한 `validated=false` 회복은 evidence grade를 별도 표시한다.
- 공식 플랫폼 URL fetch title이 `웹소설의 유토피아, 글세상 문피아`처럼 플랫폼 브랜딩이면 URL-title mismatch로 보지 않는다. 같은 URL의 search title/snippet/content가 final title을 직접 지지하는지 별도로 확인한다.
- VLM/OCR direct title 후보가 final title과 충돌하면 reason 설명뿐 아니라 `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias` 같은 구조 flag가 있는지 확인한다. 구조 flag가 없으면 high-risk bucket 누락으로 기록한다.
- VLM/OCR 충돌 후보는 `reason`뿐 아니라 `slang_insight.cultural_context`, `notes`, review packet 요약에서도 낮춰져야 한다. OCR 후보를 "본문에 병기된 다른 제목", "해당 작품 설정/2차 창작 단서"처럼 말하면 `ocr_conflict_context_overstated`로 기록한다.
- VLM/OCR 표면형과 같은 official detail URL의 locked 공식 후보가 충돌하면 표면형을 자동 치환 규칙으로 보지 말고 alias/variant 후보로 낮춘다. final title은 공식 상세 URL/search evidence와 정합되는 제목을 우선하며, 표면형이 `mentioned_works`/`comparison_target` 등에 별도 작품처럼 남으면 `surface_form_duplicate_reference_pruned` 누락으로 기록한다.
- `집착/의존/혐오/피폐`처럼 추상 명사 또는 감정 키워드가 공식 제목과 우연히 겹친 경우, 검색 결과 존재만으로 Strong evidence로 보지 않는다. 이미지 OCR의 캐릭터/작가/회차/플랫폼이 해당 공식 작품과 직접 맞는지 확인하고, 약하면 `generic_abstract_title_collision`으로 분리한다.
- OCR이 `작품명 작가 | 회차 ... PLATFORM` 형태의 명시 작품 단서를 읽었는데 final title이 unresolved면 `ocr_explicit_title_unresolved`로 분리한다. 검색 실패와 OCR 오타 가능성을 같이 기록하되, text-only 결과처럼 취급하지 않는다.
- OCR/VLM이 `작품명 + 작가 + PLATFORM`을 직접 읽고 `promotion_eligible=true`인 경우, 해당 title/author 공식 검증 검색이 image-only pruning으로 제거됐는지 확인한다. 제거됐다면 `ocr_explicit_title_search_pruned` 또는 `image_platform_url_preference_missing`으로 기록한다.
- 이미지나 OCR에 보이는 플랫폼 cue와 final title이 같은 작품을 지지하면 해당 플랫폼 official detail URL을 우선 검토한다. 플랫폼 URL이 다른 official URL보다 낮게 선택된 경우 `image_platform_url_preference` bucket으로 본다.
- 검색 결과나 커뮤니티 링크 제목에 붙은 `스포)`, `질문)`, `소신발언))`, `후기`, `리뷰` 말머리/꼬리가 final title에 섞였는지 확인한다. VLM/OCR direct title 또는 공식 상세 URL title이 말머리 없는 작품명을 지지하면 `title_prefix_contamination`으로 기록한다.
- exact-title surface는 title evidence이지 slang alias evidence가 아니다. distinct clean alias가 없는데 `slang_insight.alias_scope=pure_work_alias`처럼 보이거나 public UI가 confirmed alias처럼 표시하면 `exact_title_slang_surface_overexposed`로 기록한다.
- 작가명 surface가 `slang_db` confirmed/pending alias 또는 BatchMem abbreviation으로 승격된 경우 `author_surface_as_alias`로 분류한다. author mapping 자체는 허용하되 작품 약칭 저장과 분리한다.
- 단독 `원작` 문자열은 파생/팬픽 marker로 단정하지 않는다. `원작 주인공`, `원작 세계`는 웹소설 소개문 안의 서사 표현일 수 있고, `원작 소설 기반 웹툰`, `패러디`, `팬픽`, `2차 창작`, `크로스오버`처럼 강한 파생 문맥과 분리한다.
- VLM/OCR이 결론에 쓰였으면 `identity.image_evidence_catalog` 또는 review packet의 동등 필드에 `source_url`, `ocr_text`, `visual_summary`, `explicit_work_title`, `explicit_author_name`, `work_cues`가 남아야 한다. 이미지 근거가 reason/worker log에만 있으면 `image_evidence_catalog_missing`으로 기록한다.
- VLM/OCR이 결론에 쓰였으면 catalog와 별도로 public result row에 `vlm_enabled`, `ocr_enabled`, `vlm_enrichment_used`, `image_fetch_count`, `image_fetch_success`, `vlm_chunks_sent`, `vlm_total_bytes`, `image_enrichment_limitations` 또는 동등한 실행 counter/status가 남아야 한다. catalog는 있는데 counter가 없으면 `image_catalog_present_but_vlm_counter_missing` 또는 `image_ocr_reason_without_public_vlm_counter`로 기록한다.
- `vlm_enrichment_used=true` 또는 이미지 첨부가 있다는 사실만으로 `anchor_type=image`를 Strong/Medium 작품 근거로 보지 않는다. `image_evidence_catalog`가 `character_visual_only`/`scene_inference_only`/`unknown`, `promotion_eligible=false`, direct OCR/title/author 없음이면 이미지는 `context_sources=image` 또는 visual 참고 근거일 뿐이다. 이 상태에서 `anchor_type=image`가 남으면 `weak_visual_only_promoted_to_image_anchor`로 기록한다.
- `screen_type=text_surface` 또는 `promotion_eligible=false`인 OCR/VLM 제목은 direct image title rescue 근거가 아니다. `explicit_work_title` 문자열이 있어도 `title_role=work_title`, `focus_role=work_anchor`, `promotion_eligible=true`, 또는 동등한 직접 작품 표면 조건이 없으면 final title/anchor 승격 대신 `HOLD` 또는 context evidence로 낮춘다.
- public result에는 원문 이미지 맥락을 재검토할 수 있도록 `content_blocks`, `image_urls`, `image_count`가 남는지 확인한다. 이미지가 없는 글에는 status-only image evidence를 대량으로 남기지 않는다.
- `discourse_semantic_seed_guard`가 seed를 문맥 표현으로 낮춘 경우 final reason만 보지 않는다. 직접 작품 앵커가 없으면 `title_resolution_state=context_only`, `context_only_no_work_anchor` 같은 공개 scope/flag가 남아야 하며, `unresolved_matchable`로 남으면 no-work-anchor scope mismatch로 기록한다.
- 단, `semantic_seed_review_non_title_terms_removed` 또는 `surface_paraphrase_non_title_terms_removed`는 항상 no-work가 아니다. `semantic_seed_review.is_specific_work_discussion=true`, `title_novel_terms` 잔존, 또는 `search_query_reviews.keep`가 같은 term을 지지하면 이는 "비제목 맥락어 제거"이지 "글 전체가 특정 작품 토론이 아님"이 아니다.
- 반대로 `semantic_seed_review` no-work 근거가 없고 gatekeeper가 캐릭터/작품 표면을 보존한 짧은 반응은 자동 `context_only`로 과접지하지 않는다. 작품 확정은 금지하되, `is_novel_related=true`, `is_resolved_work_discussion=false`, `title_resolution_state=unresolved_matchable` 같은 범위 분리 상태를 허용한다.
- positive seed와 keep-query가 있는데 `semantic_seed_review_specific_work_denied`, `semantic seed demotion 조기종료`, `batch alias rescue blocked: semantic_seed_no_work_context`가 이어지면 `positive_alias_overblock_after_semantic_seed_review`로 기록한다.
- 반대로 `semantic_seed_review.is_specific_work_discussion=false`이거나 직접 작품 앵커 없이 social lament/genre banter가 확인되면 context-term warning은 계속 no-work/context-only evidence로 사용한다. `11718080`류 사회적 한탄/장르 잡담 방어와 `11718098`류 positive alias 회복은 분리해서 본다.
- `[별명/작가] 신작`, `[별명] 대체 뭘 쓰...` 같은 author/new-work 문맥은 단일 작품 alias 관측과 분리한다. 앞단 Arbiter가 deliberate null을 냈거나 `discuss_genre/trope/community/no_work_anchor` 경고가 있고 raw title/body/comment 직접 title 증거, 강한 character-work edge, snippet alias lock이 없으면 `batch_memory`/`search_evidence_alias_inference` rescue가 final title을 되살리면 안 된다.
- `official_title=null`, `title_resolution_allowed=false`, `context_only`, `author_new_work_context` 같은 title-null 상태에서는 reason scoreboard가 `plot_mention`류를 `강한 앵커`로 말하는지 확인한다. 작품명 확정에 쓰지 않는 맥락 앵커라면 `Strong` evidence가 아니라 `Medium/Weak` 또는 review-signal issue로 분리한다.
- `slang_db`에 author/new-work 표면이 confirmed alias처럼 저장된 경우 `slang_db_author_alias_pollution`으로 분류하고, 해당 entry가 다음 run의 BatchContext seed로 주입되는지 확인한다.
- 숨겨진 chain-of-thought를 요구하거나 추정하지 않는다.
- 로그에 남은 `reason`, decision field, audit flag, prompt/result field, checkpoint field만 분석한다.
- 모든 결론은 가능한 한 파일 경로, run id, post id, 로그 라인, JSON field, timestamp와 연결한다.
- 증거가 부족하면 단정하지 말고 `근거 부족`, `확인 필요`, `추정`으로 표시한다.
- smoke/canary 성공을 대량 품질 승인으로 취급하지 않는다.
- approval 목적 대규모 정성 리뷰 자동화는 `preflight_qualitative_large_scale_review.py --fail-on-locked` 뒤에 random/round2 builder에도 `--preflight <json> --fail-on-locked-source`를 붙인다. preflight missing/source mismatch/`REVIEW-LOCKED`에서 builder가 artifact를 만들면 gate bypass로 기록한다.
- `result_scan`, `run_audit`, 로그 count summary는 자동 감사와 런 정합성 증거로만 취급한다.
- 자동 감사 완료를 자연어 판정 품질 승인으로 취급하지 않는다.
- 특정 post id/제목 하드코딩 해결책을 제안하지 않는다. 반복 가능한 실패 유형과 검증 기준으로 정리한다.
- `semantic_seed_review`가 no-work/context-only로 낮춘 상태에서는 실행 검색뿐 아니라 후단 `BatchContext`, known alias, `slang_db` seed, deliberation/canonical rescue가 official title을 되살리는지도 함께 본다.
- 이미지 post가 포함된 semantic quality review는 `VLM on + OCR on` 또는 Browser visual evidence가 있어야 한다. text-only run은 런타임/비이미지 회귀 증거로만 사용한다.
- `vlm_enabled=true`, `ocr_enabled=true`, `vlm_ocr_semantic_review_ready=true`는 run-level 준비 상태다. 각 이미지의 fetch 성공, vLLM/OCR response, `image_evidence_catalog`의 `source_url/ocr_text/visual_summary`, browser loaded/broken/placeholder counter가 별도로 확인되지 않으면 image evidence success로 보지 않는다.
- random control은 표본 출처일 뿐 안전 라벨이 아니다. random packet 내부에 `reason_says_no_anchor_but_resolved`, `batch_memory_exact_alias_rescued_no_anchor`, `image_evidence_catalog_missing` 같은 high-risk 조건이 있으면 해당 bucket policy로 라벨링한다.
- high-risk oversample은 random control과 분리 보고하지만, random에 이미 들어간 post라는 이유만으로 high-risk coverage에서 제외하지 않는다.
- action queue를 재런 입력으로 만들 때 source result JSON에 이미지 URL이나 댓글 metadata가 빠져 있으면 원본 input JSONL 또는 crawler source에서 `content_blocks`와 comment row를 복원한다. 이미지/VLM/OCR follow-up을 text-only 입력으로 재실행하지 않는다.
- 같은 post가 random과 high-risk에 중복 등장하면 rerun 입력은 post 기준으로 중복 제거하되, `slang_db_review`, `human_review`, `browser_targets` 같은 action별 review packet은 잃지 않는다.
- post row와 comment row가 분리된 JSONL source에서는 `post_id` 타입이 숫자/문자열로 섞여도 같은 post로 병합되어야 한다. 같은 `comment_id`가 반복되면 대화 맥락 과증폭을 막기 위해 dedupe한다.
- search-only/blocked-intent follow-up after-run에서는 `regression_outcome`과 `final_label`을 분리한다. false-positive resolved title이 사라졌어도 comment URL 검증, quote/title recall, positive alias 과차단이 남으면 `ACCEPT`가 아니라 `HOLD` 또는 `REJECT`다.
- 자동 after-review가 `11/11 ACCEPT`처럼 낙관적으로 나오더라도 coverage audit, browser visual evidence, 수동 label이 충돌하면 자동 label을 gate 근거로 쓰지 않는다. v423 all-ACCEPT는 v425 manual label `ACCEPT=8/HOLD=2/REJECT=1`과 함께 보수적으로 해석한다.
- browser screenshot/snapshot이 외부 artifact로 확보됐더라도 result/review packet에 연결되지 않았으면 coverage audit의 `browser_visual_missing`은 해소된 것으로 보지 않는다. artifact path를 packet/result schema에 embed하거나 manifest에서 packet id와 명시적으로 연결해야 한다.
- external browser artifact manifest가 `output_path` JSONL을 가리키는 경우에도 각 row의 `visual_evidence_grade`, image loading counters, `visible_signals`를 함께 본다. `Weak`/`Missing` row는 screenshot path가 있어도 `browser_visual_available`로 세지 않는다. `Strong`/`Medium` row라도 `article_image_count`, `article_loaded_count`, pending/broken/placeholder/incomplete counter가 없으면 visual gate를 열지 않는다. counter가 있어도 `article_loaded_count < article_image_count`, lazy/data-original/placeholder/broken/incomplete pending 같은 실패 counter가 있으면 malformed artifact로 보고 visual gate를 열지 않는다.
- coverage 확인에는 `tools\audit_comment_metadata_coverage.py`를 사용한다. source JSONL의 post IP coverage, comment IP coverage, duplicate comment id, result JSON의 `comment_metadata`, `comment_dialogue_context_lines`, `image_evidence_catalog` coverage를 함께 기록한다.
- `tests\inputs\test01.jsonl` v277 기준 post row IP는 `0/104517`이었다. 이 상태에서는 익명 `ㅇㅇ` 댓글을 원글 작성자 댓글로 확정할 수 없고, `author_match_unverified`로 둬야 한다.
- `표현 오타/축약 패턴(범용)` 신호가 있는 표면은 검색 seed 문제가 아니라 meaning pass 문제로 먼저 다룬다. 이때 특정 설명 범주나 비슷한 계열을 자동 차단/허용 규칙으로 고정하지 말고, packet의 title/body/comment/comment_context를 읽어 단일 작품 토론인지 확인한 뒤 `re_judge` 또는 검색 재실행을 결정한다.
- 공개 reason/prompt/report에서는 `표현 오타/축약 패턴(범용)`로 적는다. 특정 표면어를 정답 표현으로 결정적 치환하거나 `X -> Y` 전역 규칙처럼 쓰지 않는다.
- 공개 reason/report에서는 `표현 오타/축약 패턴(범용): X; Y`처럼 표면어 후보를 다시 나열하지 않는다. 표면어는 원문 맥락 필드에서만 확인하고, 별도 direct evidence 없이 `작품 seed 제외` 목록에도 섞지 않는다.
- `X -> Y` 표기가 아니어도, 원문에 없는 정규화 값이나 숫자/slash/arrow가 들어간 해석성 괄호를 공개 reason에 남기지 않는다. 이는 특정 숫자/나이 규칙이 아니라, surface reread 후보를 정상형 복원처럼 보이게 만들지 않는 public-output hygiene이다.
- 재해독은 `표현 오타/축약 패턴(범용)` 자체를 올려 원문 의도를 다시 읽는 단계다. 리뷰어가 자연스럽다고 느끼는 특정 정상형도 새 prompt/report/reason에는 복원 결과처럼 쓰지 않는다.
- 단, 보고서나 prompt에서 이를 전역 규칙 또는 자동 치환 규칙처럼 쓰지 않는다. 모든 재해독은 해당 packet 안에서만 검토하는 후보 해석이며, 별도 direct evidence 없이 작품명/별칭 근거로 승격하지 않는다.
- 최신 코드 계약에서는 `surface_paraphrase_notes`가 정답 paraphrase를 생성하지 않는다. `expression_typo_abbreviation_or_spacing_candidate`는 LLM 재해독 입력 힌트이며, 실제 해석은 `semantic_seed_review`/`final_semantic_reread` 결과와 원문/evidence 정합성으로 판단한다.
- 과거 문서/테스트의 구체 표면어 복원 문구는 known-bad packet에서 사람이/LLM이 읽은 historical observation일 뿐이며, 리뷰 기준에서는 deterministic rule로 취급하지 않는다. 새 재검토 문서에는 예시로도 `X -> Y` 복원 표기를 쓰지 말고 범용 후보 label로 남긴다.
- 짧은 인명/캐릭터명처럼 보이는 seed와 일반어 검색 조합은 단독으로 작품 식별 근거가 아니다. 작품명, 공식 별칭, 작가, 회차, 플랫폼 작품 URL, 작품 고유 설정 앵커가 없으면 `context_only`/`HOLD`/`REJECT` 후보로 본다.
- 직접 작품 앵커가 없는데 reason이 `작품 속`, `원작`, `해당 작품`처럼 작품 존재를 확정하면 `reason_overstates_context_only` 후보로 보고, public reason은 "인명/캐릭터명처럼 보이는 표면", "대상", "댓글 반응"처럼 약한 표현으로 낮춘다.
- 이런 의미 재독해 이슈는 특정 문자열 하드코딩으로 해결하지 않는다. `surface_paraphrase_notes`, `semantic_seed_review`, `context_only_no_work_anchor`, `friend_social_lament_or_generic_discourse` 같은 구조 flag와 public evidence boundary로 검토한다.
- `표현 오타/축약 패턴(범용)`은 표면 패턴 확정 규칙으로 차단하지 않는다. 해당 packet의 title/body/comment 안에서만 후보 해석으로 검토하고, direct title/alias/evidence 없이 resolved title을 만들면 `weak_evidence_but_strong_resolution` 또는 `final_semantic_reread_missing_for_semantic_seed`로 본다.
- `surface_paraphrase_notes`만 있고 `semantic_seed_review`의 no-work/context-only 판단이 없으면 품질 리뷰에서 이를 확정 차단 근거로 보지 않는다. 해당 notes는 LLM 재해독 입력 힌트이며, 후단 sanitizer/라벨은 semantic review 결과와 evidence boundary를 같이 확인한다.
- 댓글 작성자/IP 맥락은 `comment_context_lines`, `comment_dialogue_context_lines`로 보존되어야 하며, LLM 재해독 payload에서는 `comment_context`, `comment_dialogue_context`로 실제 전달되는지 확인한다. key mismatch로 빈 배열이면 `comment_dialogue_payload_missing` 또는 `INFO_MISSING` 후보로 본다.
- `author_match_unverified`는 원글 작성자와 같은 닉네임/익명 표면이지만 IP 확정이 없는 상태다. 대화 흐름 힌트로는 사용하되, 원글 작성자 발화나 독립 작품 evidence로 승격하지 않는다.
- `author_match_unverified`만 있는 짧은 캐릭터/외모/나이 반응글은 댓글이 독립 작품 근거를 추가한 것으로 보지 않는다. 이 경우 `comment_author_match_unverified_not_independent_evidence`, `context_only_no_work_anchor`, `weak_character_reaction_unresolved_blocked` 같은 flag를 확인한다.
- `semantic_seed_review` 또는 `surface_paraphrase`가 context-only/no-work 위험을 표시했는데 final result가 resolved title이면 `final_semantic_reread` 결과 또는 `final_semantic_reread_*` flag가 있는지 확인한다. 없으면 search/Decoder 재승격 후 최종 의미 재독해 누락으로 기록한다.
- `final_semantic_reread_rejected_resolution`은 "검색은 돌아갔지만 원문/evidence가 후보 작품을 직접 지지하지 않음" 신호다. `ACCEPT/HOLD/REPROCESS/REJECT` 라벨 리뷰에서는 random/high-risk와 분리해 과차단/미차단을 같이 본다.
- final freeze 또는 URL validator가 제거한 `heretic_url`이 BatchContext/slang_db alias rescue 뒤 다시 붙으면 `stale_official_url_reintroduced`로 기록한다. title은 맞아도 URL 대표 제목이 다르면 `Strong` evidence가 아니며, `official_detail_url_title_mismatch_cleared`, `batch_memory_alias_stale_official_url_cleared`, `official_detail_url_repaired_from_search` flag를 함께 확인한다.
- reason에 `고유 앵커 부족` 또는 `캐릭터/줄거리 앵커 부족`이 있어도, 원문 title/body/comment에 제목 약칭 또는 직접 제목 표면이 있고 공식 상세 URL/catalog evidence가 final title을 직접 지지하면 `reason_says_no_anchor_but_resolved`로 기계적 REJECT하지 않는다. 이 경우 약한 plot/character anchor와 강한 title/official evidence를 분리해 `ACCEPT` 또는 `HOLD`로 검토한다.
- 반대로 제목 약칭/직접 제목 표면 없이 검색어만 비슷하거나, 공식 URL 없이 `고유 앵커 부족` 문구가 남은 resolved result는 계속 `reason_says_no_anchor_but_resolved`, `weak_evidence_but_strong_resolution`, `final_semantic_reread_missing_for_semantic_seed` 후보로 본다.
- memory-query/대사·장면 회수 글에서는 공식 작품 페이지 hit와 quote/source alignment를 분리한다. 검색 catalog에 후보 공식 URL이 있어도 원문 대사/장면 fragment를 직접 지지하는 snippet, OCR, VLM, 원문 source anchor가 없으면 `quote_alignment_missing_for_memory_query`로 `HOLD/human_review`에 둔다.
- `title_candidates`, `entity_mentions`, `analysis.detected_titles`처럼 LLM이 원문 표면을 다시 적은 필드는 quote alignment support로 세지 않는다. quote alignment는 `identity.search_evidence_catalog`, `identity.image_evidence_catalog`, `identity.evidence` 같은 direct evidence catalog에서만 센다.

## 4-1. Document Language Policy

리뷰 분석, 검토, 피드백 산출물은 한국어로 작성한다.

- Markdown 보고서의 결론, 증거 맵, 로그/처리 흐름 리뷰, 판단 품질 리뷰, `slang_db` 리뷰, 이슈 후보, action queue 설명은 한국어로 쓴다.
- 보고서는 간략하게 쓰되 의미, 근거, 산출물 경로, gate 상태를 생략하지 않는다.
- JSON key, enum label, action id, bucket id, 파일명, 명령어, 로그 원문, 코드 심볼은 원문을 유지한다.
- 영어 evidence/snippet은 필요한 경우 짧게 남기되, 의미 해석과 최종 판단은 한국어로 쓴다.
- 자동 생성된 Markdown이 영어 heading 또는 영어 설명을 만들면 후속 문서 갱신 작업에서 한국어로 고친다.
- 과거 실행 이력의 영문 산출물은 사실 기록으로 보존할 수 있지만, 새 재검토/피드백 문서는 한국어 기준을 따른다.

증거 등급:

- `Strong`: 파일 경로 + run id + post id + JSON field + 로그 라인/타임스탬프가 연결됨
- `Medium`: 파일 경로 + JSON field 또는 로그 라인이 있으나 일부 연결 정보가 부족함
- `Weak`: 요약 카운트나 정황만 있고 개별 post/field 증거가 부족함
- `Missing`: 필요한 파일/필드가 없음

## 4-2. VLM/OCR 및 브라우저 시각 증거 정책

이미지 첨부 post가 있는 run은 아래 기준을 추가로 확인한다.

- 테스트/재검증 기본값은 `--vlm on --ocr on`이다. `--vlm off --ocr off`는 text-only guard, crash isolation, non-image canary 전용이다.
- VLM 서버가 사용 가능한 상태에서 semantic regression을 돌릴 때는 `--vlm on --ocr on`을 명령에 명시한다. 옵션이 누락된 run은 먼저 설정 누락/manifest 상태를 확인하고, 이미지 포함 품질 승인 근거로 쓰지 않는다.
- 이미지 post가 있는 semantic regression에서는 `--require-vlm-ocr-for-images` 또는 `LLM_REQUIRE_VLM_OCR_FOR_IMAGES=1`을 붙여 VLM/OCR 누락을 시작 전 실패로 처리할 수 있다. 이 guard가 exit code 2로 멈춘 run은 설정 실패 증거이며 semantic 품질 증거가 아니다.
- manifest에서 `vlm_enabled=true`, `ocr_enabled=true`, `image_post_count>0`, `vlm_ocr_semantic_review_ready=true`를 확인한다.
- manifest의 `vlm_ocr_semantic_review_skip_reasons`를 확인한다. `no_image_blocks`는 이미지가 없어 not-applicable, `vlm_disabled`/`ocr_disabled`는 image semantic approval blocker다.
- image block이 있는데 위 조건이 아니면 해당 post의 semantic label은 `INFO_MISSING` 또는 `REPROCESS` 후보로 둔다.
- image block이 있고 VLM/OCR이 결론에 쓰였는데 `image_evidence_catalog` 또는 packet의 구조화된 VLM/OCR field가 없으면 `HOLD` 또는 `REPROCESS` 후보로 둔다. 로그에만 남은 VLM evidence는 대형 정성 리뷰의 `Strong` evidence가 아니다.
- `11718082`처럼 세대별 산출물이 갈릴 수 있다. `v179`처럼 이미지 입력은 있지만 VLM-ready manifest와 `VLM chunk request`가 없으면 이미지 품질 승인 근거가 아니며, 반대로 로그에는 VLM/OCR이 있어도 result/packet의 `image_evidence_catalog`가 비어 있으면 대량 리뷰에서는 `Strong`이 아니다.
- DC 이미지 로딩이 걸리거나 브라우저에서 실제 이미지가 늦게 뜨는 경우, Codex in-app Browser 또는 Playwright로 post URL을 열어 이미지 렌더링 상태와 스크린샷을 확인한다.
- 이미지/VLM/OCR 케이스의 `Strong` evidence는 브라우저 실열람, 이미지 로딩 완료, screenshot/vision 관찰, 그리고 그 이미지 내용이 final title/reason/decision을 직접 지지한다는 packet-level 설명이 모두 있어야 한다.
- `article_image_count > 0`인데 `article_loaded_count != article_image_count`, `image_loading_pending`, `article_lazy_pending_count`, `data_original_pending_count`, `placeholder_current_src_count`, `article_incomplete_count`, `article_broken_count` 중 하나라도 있으면 Browser visual evidence는 `Strong`이 아니라 `Weak` 또는 `Missing`이다. sidecar가 `visual_evidence_grade=Strong`을 달고 있어도 loading counter 실패가 있으면 해당 grade를 신뢰하지 않는다. 이 상태에서는 `ACCEPT/GO` 근거로 쓰지 말고 `HOLD/REPROCESS/human_review`로 보낸다.
- `browser_visual_*`, screenshot path, manifest path가 있어도 이미지 로딩 완료 증거가 아니다. `article_loaded_count == article_image_count`, `article_lazy_pending_count=0`, `data_original_pending_count=0`, `placeholder_current_src_count=0`, `article_incomplete_count=0`, `article_broken_count=0` 또는 동등한 직접 visual review가 있어야 한다.
- fallback browser capture에서 screenshot은 성공했지만 `article_image_count=0`, `article_image_gate_passed_rows=0`, `visual_evidence_grade=Weak`이면 visual gate는 닫히지 않는다. 이런 sidecar는 접근 시도 evidence일 뿐 semantic approval evidence가 아니다.
- fallback capture에서 `playwright-cli eval`이 stdout error만 남기거나 `eval_path=null`이면 JS/daemon/command-wrapper 문제를 먼저 의심한다. 가능한 경우 installed Chromium revision이 있는 cached Playwright `node_modules`를 사용하는 direct Node Playwright fallback으로 재캡처하고, `eval_payload_source`, stdout/stderr excerpt, `capture_engine`을 row에 남긴다.
- DC 페이지의 일반 UI 단어 `차단`은 blocked evidence가 아니다. 실제 접근 제한/삭제/성인인증/로그인 필요 문구와 구분하지 못하면 정상 이미지 row가 `Missing`으로 오탐될 수 있다.
- `browser_visual_available=true`나 `visual_evidence_grade=Medium`은 coverage sanity 신호일 수 있지만 packet-level semantic approval은 아니다. 해당 이미지/스크린샷 내용이 final decision, title, reason을 직접 지지한다는 자연어 alignment가 별도로 있어야 `ACCEPT/GO` 후보가 된다.
- 텍스트 검색이나 OCR 문자열만으로 이미지를 본 것처럼 처리하지 않는다. 브라우저에서 원문 이미지/첨부 이미지가 실제 크기로 로드된 화면을 확인하지 못하면 `Strong`이 아니라 최대 `Medium`, 보통 `Weak/Missing`으로 둔다.
- VLM/OCR catalog가 있더라도 브라우저 이미지 로딩 완료를 증명하지는 않는다. 반대로 브라우저 로딩 완료만으로 작품명 판정을 `Strong`으로 만들 수 없고, 이미지 내용이 title/author/episode/platform URL 등 결론을 직접 지지해야 한다.
- Browser에서 이미지가 보이지만 VLM/OCR packet에 반영되지 않았으면 `vlm_ocr_input_missing`, `image_fetch_timeout`, `browser_visual_required` risk로 분리한다.
- action queue에서 image catalog/browser loading/context catalog가 Missing/Weak인 source는 `vlm_ocr_browser_visual_gate`를 P0 approval blocker로 둔다. 별도 action이 `ready`여도 semantic approval은 열지 않는다.
- `context_sources=["image"]` 또는 `anchor_type=image`만으로는 VLM/OCR evidence가 아니다. `image_evidence_catalog`, `vlm_enrichment_used`, fetch/chunk count, OCR/title/author/work cue 같은 구조 필드가 없으면 `image_context_without_vlm_catalog` 후보로 둔다.
- `vlm_enrichment_used`, `image_fetch_success`, `vlm_chunk_count` 계열 값이 `failed`, `timeout`, `pending`, `skipped`, `unsupported`, `disabled`이면 VLM/OCR evidence로 세지 않는다. 이 값들은 `REPROCESS` 또는 `REVIEW-LOCKED` 후보이며, image context claim을 Strong/Medium으로 승격하지 않는다.
- VLM/OCR이 돌았더라도 이미지가 팬아트/짤/표지만 있고 작품명, 작가, 회차, 직접 인용 같은 작품 앵커가 없으면 `Strong` evidence로 승격하지 않는다.
- VLM/OCR이 작품명처럼 보이는 텍스트를 읽었더라도 final title과 normalized/similar match되지 않으면 해당 OCR text는 conflict/weak visual evidence다. final title이 안정 alias/공식 URL로 맞더라도 OCR 후보 자체를 Strong evidence로 쓰지 않는다.
- `11718082`처럼 이미지 안에 작품명/회차/OCR 텍스트가 보이는 케이스는 VLM/OCR 또는 Browser visual evidence가 직접 결론을 지지해야 한다.
- `11716486`처럼 이미지가 캐릭터/팬아트 시각 자료일 뿐 title/author/episode 근거가 없으면 이미지가 있다는 사실만으로 resolved title을 확정하지 않는다.

## 5. 분석 순서

1. repo 문서와 기존 TODO/checklist를 확인한다.
2. scan result directory inventory를 작성한다.
3. manifest/checkpoint/run audit/log/comparison/review packet/slang DB snapshot 존재 여부를 확인한다.
4. run option, run id, input/output directory, `slang_db` path, snapshot hash 또는 주요 key count를 확인한다.
5. checkpoint/completed/failed/pending/flushed 정합성을 확인한다.
6. fatal/error/timeout/degraded/VLM/OCR/slang DB 관련 이벤트를 집계한다.
7. 가장 이른 최초 실패와 이후 fanout 증상을 분리한다.
8. 공개 판단 근거 샘플과 위험 케이스를 자동 필드 기준으로 1차 분류한다.
9. `QUALITATIVE_SEMANTIC_REVIEW_LOOP` 필요 여부를 판정한다. 대량 결과 품질 승인에는 이 루프가 필요하다.
10. `slang_db` 적재/선택/저장/차단/표시 상태를 리뷰한다.
11. run integrity와 semantic decision quality를 분리해 `GO`/`REVIEW`/`NO-GO` 판정을 남긴다.
12. 이슈 후보와 docs/checklist 개선안을 작성한다.

## 6. Inventory Checklist

- [ ] scan result directory 절대 경로
- [ ] run id
- [ ] 입력 JSONL 또는 원본 데이터 경로
- [ ] result/checkpoint/manifest 경로
- [ ] run audit 경로
- [ ] expert run log 경로
- [ ] shard/search audit 경로
- [ ] comparison 경로
- [ ] review packet 경로
- [ ] run 당시 `slang_db` snapshot 경로
- [ ] 현재 `slang_db/slang_db.json`과 snapshot 차이
- [ ] 누락 파일과 영향

## 7. Run Completeness and Integrity

확인 항목:

- `completed_count`
- `failed_count`
- `pending_count`
- `flushed_count`
- final result row count
- checkpoint row count
- checkpoint completed row count
- pending snapshot row count
- reason error count
- fatal/trace/error count
- search timeout/degraded/upstream zero
- VLM/OCR request, skip, failure count
- worker별 stuck/long-tail/retry

정합성이 깨지면 결과 품질 리뷰보다 run integrity를 먼저 판정한다. final result에 없는 checkpoint completed row가 pending snapshot과 정확히 일치하면 `recoverable_pending_flush_gap`으로 분류하고, 원본 result를 덮어쓰지 않는 recovered completed subset을 별도 산출물로 남긴다. 다만 `pending_count>0`, `flushed_count<completed_count`, clean completion summary 부재, 또는 `input_post_count` 대비 completed 부족이 있으면 전체 run completion과 semantic approval은 `GO`로 두지 않는다.

최신 `expert_main.py` 병렬 run은 ordered flush gap이 남으면 primary result JSON을 ordered flushed prefix로 유지하고, 같은 stem의 `_completed_subset.json`과 `_completed_subset_manifest.json`을 별도 생성할 수 있다. 이 artifact는 checkpoint recovery와 같은 성격의 triage/recovery source다. manifest의 `partial_flush_gap`, `ordered_flush_blocked`, `completed_subset_written`, `completed_subset_count`, `large_run_complete`를 함께 확인하고, `large_run_complete=false`이면 completed subset만으로 large-scale approval을 열지 않는다.

`tools/audit_expert_run_health.py`는 `flush_integrity` 섹션으로 manifest/checkpoint/result/pending count 정합성을 분류한다. `run_integrity_gate=GO`와 `classification=clean_completed_source`가 아니면 completed source로 쓰지 않는다. `IN_PROGRESS/ordered_flush_gap_in_progress`는 artifact mismatch가 아니라 진행 중 flush gap일 수 있지만, 그래도 `semantic_quality=REVIEW-LOCKED`와 `full_scan_approval=false`를 유지한다. `--input-jsonl`을 함께 주면 `flush_integrity.frontier.source_post`가 expert_main의 post/comment 분리 후 `global_idx`에 해당하는 source post를 기록한다. raw JSONL `source_line`과 `global_idx`는 comment row 때문에 다를 수 있으므로 혼동하지 않는다. `flush_integrity.frontier`에서 `next_save_idx`가 checkpoint/pending 양쪽에 없으면 해당 row가 아직 in-flight 또는 missing인 상태이므로, 같은 frontier가 장시간 유지될 때 worker log에서 해당 `global_idx/post_id` start/complete/error를 별도 감사한다. `NO-GO/artifact_count_mismatch`이면 먼저 result/checkpoint/pending 경로와 row count를 다시 확인한다.

후속 qualitative review 도구는 입력 source의 성격을 manifest/gate에 남긴다. 최소 필드는 `source_dataset_kind`, `source_integrity_classification`, `recovery_safe_to_use_as_completed_subset`, `large_run_complete`, `approval_policy`, 원본/복구 row count다. random control을 추가해 canonical labels가 바뀌면 `summary.json`, `sample_manifest.json`, `gate_decision.md`, `action_queue.md`를 같은 run id/seed 기준으로 재계산한다.

## 7-1. Goal/Test Runtime Evidence Rule

- goal/targeted run에서 느린 원인을 볼 때 Docker Compose lifecycle, MCP/search health, LLM 심의/검색 토큰 병목을 분리한다.
- Codex goal orchestration 병렬성과 `expert_main.py` runtime 병렬성을 분리 기록한다. Codex `spawn_agent`는 리뷰/감사/문서화 분업이고, `expert_main.py --parallel`은 실제 처리 worker cap이다.
- `--parallel 36`을 썼다면 `requested_parallel=36`과 `effective_parallel`을 함께 적는다. small input에서 `effective_parallel=min(input_count,36)`으로 줄어드는 것은 정상이며, 36 worker를 맞추려고 같은 소규모 테스트를 재실행하지 않는다.
- subagent 병렬 검토가 부족한 문제는 Codex `spawn_agent` 분해 축을 보강해서 풀고, runtime worker 수 부족 문제는 manifest/log의 `requested_parallel`, `effective_parallel`, endpoint health로 판단한다.
- manifest의 `mcp_auto_up_shards=false`, `mcp_auto_recreate_shards=false`, `mcp_local_shard_management_enabled=false`와 로그의 `docker compose`/`force-recreate`/`warp_shards.py`/`compose up` 부재가 확인되면 Compose 재시작 문제는 별도 해결된 것으로 본다.
- 그래도 단건 elapsed, `total_tokens`, search degraded/retry가 크면 semantic orchestration performance 이슈로 승격한다.
- Verifier critical veto + 음수 evidence + deliberate null-title + direct title proof 부재 케이스는 Jury/Debate 스킵 fast-path 후보로 본다.
- fast-path나 guard는 post id, 제목 문자열, known alias 하드코딩으로 만들지 않고 공개 필드와 evidence 조건으로 정의한다.
- targeted canary의 runtime/semantic 통과는 대량 10만 건 semantic approval 근거가 아니다. random baseline과 high-risk expansion gate는 계속 분리한다.

표본 목표는 요청값과 실제 선택값을 분리한다. random control은 `requested_sample_size`, `selected_sample_size`, `sample_shortfall`, `sample_target_satisfied`를 남긴다. high-risk bucket은 `target_total`, `selected_total`, `target_satisfied`, bucket별 `target_shortfalls`를 남긴다. 목표 미달 표본은 triage에는 쓸 수 있지만 large-scale semantic approval 근거가 아니며, gate에서는 `Weak` 또는 `Missing` evidence로 표시한다.

large-scale qualitative expansion을 실행하기 전에는 preflight를 먼저 수행한다. preflight는 source result row 수, manifest count, checkpoint completed row 수, pending snapshot row 수, source policy, random baseline feasibility, high-risk bucket population을 확인한다. preflight gate가 `REVIEW-LOCKED`이면 random/high-risk review를 실행해도 approval 근거가 아니라 source 부족 증거로만 취급한다.

## 8. 오류 리뷰 절차

1. run start 시점과 실행 옵션을 확인한다.
2. 가장 이른 fatal/error/timeout/degraded 이벤트를 찾는다.
3. 해당 이벤트 이전의 정상 처리 흐름을 확인한다.
4. 이후 반복되는 error/retry/failed/pending 증상이 같은 원인의 fanout인지 구분한다.
5. 최초 원인과 후속 증상을 별도 항목으로 기록한다.
6. 후속 증상만 보고 root cause로 단정하지 않는다.
7. 런타임 안정성 문제와 판단 품질 문제를 분리해서 기록한다.

## 9. Post Lifecycle Review

각 post 또는 샘플 케이스는 가능한 경우 아래 흐름으로 본다.

- `load`
- `search`
- `evidence filter`
- `LLM judgment`
- `VLM/OCR`
- `final fields`
- `checkpoint`
- `flush`

어느 단계에서 정보가 약해졌는지, 어느 단계에서 과잉 확정이 발생했는지 구분한다.

## 10. Judgment Quality Review

다음 field 간 정합성을 확인한다.

- `resolved_title`
- `relevance`
- `reason`
- `risk_tags`
- `search_health_flags`
- evidence URLs
- evidence snippets
- final decision fields
- `gallery_id`, `post_author`, `post_ip` 또는 공개 가능한 작성자 IP 필드
- `comment_metadata`: `comment_id`, `author`, `ip`, `speaker`, `is_post_author`, `reply_to_comment_id`, `reply_level`
- `comment_context_lines`: 댓글 본문과 분리된 공개 작성자/대화 맥락. 가능한 경우 `speaker`, `author`, `role=post_author`, `ip`, `reply_level`, `reply_to`, `comment_id`를 포함한다.
- `comment_dialogue_context_lines`: `comment_context_lines`와 댓글 text excerpt를 같은 #번호로 묶은 prompt/review용 대화 재구성. 본문 작성자 댓글 이어쓰기와 타 유저 답변 흐름을 읽기 위한 필드이며, `speaker/author/ip` 자체는 작품 identity evidence가 아니다.

댓글 작성자/IP는 댓글 본문에 합쳐 넣지 않는다. post row의 `author`는 `post_author`로, comment row의 `author`는 comment metadata와 `comment_context_lines`의 `author=`로 분리해서 보존하고, `role=post_author` 같은 공개 맥락만 판단 packet에 넣는다.
targeted 재실행 입력이나 review packet에서 이 메타가 빠지면 댓글 대화 흐름 검증은 `INFO_MISSING`으로 분리한다. title 판정이 맞더라도 author/comment dialogue-context 승인 근거로 쓰지 않는다.

검색 결과가 약하거나 degraded인데 final decision이 강한 경우 quality risk로 표시한다. `unresolved`, `multi_work`, `adjacent`, `trope`, `author_talk` 경계 케이스는 정성 리뷰 대상으로 분류한다.

### Automatic Audit vs Semantic Review

자동 감사와 자연어 품질 리뷰는 분리한다.

- 자동 감사: run count, manifest/checkpoint 정합성, 로그 오류, search/VLM/OCR/slang DB 지표를 본다.
- 자연어 리뷰: post 원문과 댓글, evidence, reason, final decision이 실제 의미상 맞는지 본다.
- 자동 감사가 `GO`여도 자연어 리뷰가 `REVIEW` 또는 `NO-GO`이면 대량 결과 품질은 `GO`가 아니다.
- 대량 run 품질 승인을 위해서는 `docs/devs/QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`의 packet, label, gate 산출물을 남긴다.
- 자연어 리뷰 라벨러는 reason 문자열의 `evidence_bucket` counter만 보지 않는다. `identity.search_evidence_catalog`, `evidence_catalog`, `title_candidates`, `primary_work`, `evidence_urls` 같은 공개 구조화 필드를 함께 세어야 한다.
- reason counter와 structured catalog가 충돌하면 structured catalog를 별도 count로 기록하고, stale counter 가능성을 `review_tooling` 이슈로 분리한다.

### Qualitative Semantic Review Requirements

자연어 리뷰 packet은 위험 bucket 과표집과 random control sample을 함께 포함해야 한다.

필수 bucket:

- `random_control`
- `search_degraded_or_timeout`
- `weak_evidence_but_strong_resolution`
- `generic_parenthetical_bridge`
- `author_new_work_alias_rescue_blocked`
- `slang_db_author_alias_pollution`
- `unresolved_to_resolved`
- `multi_work_or_adjacent_risk`
- `trope_or_author_talk_risk`
- `reason_decision_contradiction`
- `final_semantic_reread_missing_for_semantic_seed`
- `final_semantic_reread_reviewed`
- `official_url_synopsis_or_branding_mismatch`
- `batch_memory_exact_alias_missing_url`
- `ocr_title_conflict_with_stable_alias`
- `role_or_honorific_alias_rescue_blocked`
- `topic_particle_title_lead_alias_anchor`
- `slang_db_store_block_pending_family_noise`
- `VLM_OCR_involved`
- `worker_or_shard_degraded_window`
- `quote_alignment_missing_for_memory_query`
- `corrected_title_official_url_recovery`
- `reason_official_url_summary_sync`
- `generic_search_title_snippet_match`
- `platform_branding_fetch_title`
- `official_url_fetch_title_mismatch_false_positive`
- `context_only_no_work_anchor`
- `context_only_late_rescue_without_direct_anchor`
- `intent_denied_title_present`
- `decoder_alias_official_url_late_promotion`
- `semantic_seed_review_specific_work_denied`
- `reason_overstates_context_only`
- `character_name_only_search_keep`
- `weak_character_reaction_unresolved_blocked`
- `comment_context_missing_original_source`
- `batch_memory_exact_alias_rescue_pollution`
- `relevant_title_missing_url`

각 sample은 `ACCEPT`, `HOLD`, `REPROCESS`, `REJECT`, `INFO_MISSING` 중 하나로 라벨링한다.

각 sample에서 최소한 아래 질문에 답한다.

- post intent: 이 글은 자연어적으로 무엇을 말하는가?
- model decision: 모델의 resolved title/relevance/final decision은 무엇인가?
- evidence alignment: evidence가 결론을 직접 지지하는가?
- reason quality: reason이 evidence보다 과하게 확정했는가?
- boundary risk: unresolved/multi_work/adjacent/trope/author_talk/generic/alias 위험이 있는가?
- `slang_db` effect: alias가 도움, 오염, 누락, 표시 혼선을 만들었는가?
- final review label과 action은 무엇인가?

자연어 리뷰 기본 산출물:

- `qualitative_review/<run_id>/sample_manifest.json`
- `qualitative_review/<run_id>/review_packets.jsonl`
- `qualitative_review/<run_id>/review_labels.jsonl`
- `qualitative_review/<run_id>/pattern_summary.md`
- `qualitative_review/<run_id>/gate_decision.md`
- `qualitative_review/<run_id>/action_queue.md`
- 추가 round 수행 시 `round<N>_manifest.json`, `round<N>_packets.jsonl`, `round<N>_labels.jsonl`, `round<N>_summary.md`

종료 기준은 전수 판독 완료가 아니라 failure pattern saturation이다. 최근 round에서 새 실패 유형이 거의 나오지 않고, random control과 high-risk bucket 결과가 분리 보고되며, P0/P1/P2 후보가 정리되어야 한다.

### VLM/OCR Browser Visual Evidence Review

VLM/OCR이 판정에 영향을 준 샘플은 로그 필드와 OCR text만으로 품질 승인하지 않는다. `VLM_OCR_involved`, OCR-derived title, image-only evidence, screenshot/webtoon panel, `vlm_ocr_evidence_gap` 케이스는 원문 또는 이미지/evidence URL을 브라우저로 직접 열어 시각 증거를 확인한다.

브라우저 표면 우선순위:

1. Codex 내장 브라우저 `@browser` / Browser plugin의 in-app browser, 즉 `iab`를 1순위로 사용한다.
2. 내장 브라우저에서 원문 URL, 이미지 URL, evidence URL을 열고 DOM snapshot, screenshot, visible text, 현재 URL, 접근 실패/삭제/차단 상태를 packet/label에 기록한다.
3. 독립 Playwright CLI, 외부 브라우저, headless script는 내장 브라우저 연결이 실제로 불가능하거나 대량 배치 캡처가 필요한 경우의 fallback으로만 사용한다.
4. fallback을 쓰면 `browser_surface=fallback_playwright_cli`, fallback 사유, 실패한 내장 브라우저 연결 확인, 명령, stdout/stderr 경로를 manifest에 남긴다.
5. fallback 캡처만으로는 `ACCEPT` 승격을 금지한다. 내장 브라우저 또는 사람이 볼 수 있는 screenshot/vision 관찰로 `Strong` 또는 충분한 `Medium` 증거가 확인되어야 한다.

필수 기록:

- `post_id`, source URL, opened browser URL, access status
- `browser_surface`: `codex_in_app_browser_iab` 또는 fallback 표면
- screenshot path, capture timestamp, viewport
- visible title/text/work cue에 대한 짧은 vision/manual observation
- `ocr_text`, `resolved_title`, `reason`, final decision과 시각 관찰의 정합성
- visual evidence grade: `Strong`, `Medium`, `Weak`, `Missing`
- 본문 이미지 로딩 상태: `article_image_count`, `article_loaded_count`, `article_incomplete_count`, `article_placeholder_count`, `article_broken_count`
- lazy image 교체 상태: `article_lazy_pending_count`, `data_original_pending_count`, `placeholder_current_src_count`
- 본문 인라인 이미지가 0개일 때의 첨부 링크 상태: `article_attachment_file_count`, `article_attachment_links`, `download.php`, `viewimagePop.php` 탐지 여부
- 첨부 팝업 또는 직접 이미지 URL을 열었다면 attachment popup screenshot path, 실제 이미지 URL, `naturalWidth`, `naturalHeight`
- 스크롤/대기 여부: lazy-load를 트리거한 횟수와 스크롤 후 screenshot path

판정 규칙:

- 브라우저 접근 실패, 삭제, 로그인/성인 인증, 404, blocked response는 `Missing` 또는 `Weak` evidence로 기록하고 `ACCEPT`하지 않는다.
- VLM/OCR 대상에서 페이지 제목/본문 텍스트만 확인한 상태는 `Strong`이 아니다. 본문 이미지 선택자(`.writing_view_box`, `.write_div`, `.imgwrap`) 기준으로 검증 대상 이미지가 실제 크기(`naturalWidth`, `naturalHeight`)로 로드되어야 한다.
- DCInside 본문 이미지는 첫 화면 로드 후에도 `gallview_loading` placeholder가 남을 수 있으므로, 본문 이미지 영역까지 스크롤하고 `placeholder/incomplete/broken=0`을 확인하기 전에는 `ACCEPT`로 승격하지 않는다.
- `article_image_count=0`이어도 `원본 첨부파일`, `download.php`, `viewimagePop.php` 링크가 있으면 즉시 `Missing`으로 닫지 않는다. Codex 내장 브라우저 `iab`에서 첨부 팝업 또는 직접 이미지 URL을 열고 attachment count/link/screenshot/dimension을 별도 기록한다.
- 첨부 팝업 이미지가 로드된 것은 “시각 입력 복구” 증거일 뿐 작품 판정 승인 증거가 아니다. 이미지가 `resolved_title`/reason/final decision을 직접 지지하지 않으면 `ACCEPT`가 아니라 `HOLD/human_review`로 둔다.
- 첨부 링크는 있지만 팝업/직접 이미지가 삭제, 차단, blank response, 인증 필요 등으로 열리지 않으면 `Missing` 또는 `INFO_MISSING`으로 남기고 원본 source image URL 복구 가능성을 별도 action으로 둔다.
- `img.complete=true`와 `naturalWidth>0`만으로 로딩 완료를 판단하지 않는다. `gallview_loading_ori.gif`, `loading_btntype.gif` 같은 placeholder 자체도 complete 상태로 잡힐 수 있다.
- `data-original` 또는 lazy-load 원본 URL이 있으면 `currentSrc/src`가 실제 원본 URL로 교체됐는지 확인한다. 교체 전이면 `loaded`가 아니라 `placeholder_current_src` 또는 `data_original_pending`으로 기록한다.
- 스크린샷이 OCR/model reason과 충돌하면 `REJECT` 또는 `REPROCESS` 후보로 승격한다.
- 스크린샷은 작품 단서를 보여도 검색 evidence가 결론을 직접 지지하지 못하면 `HOLD`로 둔다.
- screenshot/vision 관찰은 공개 관찰 요약만 기록한다. hidden chain-of-thought를 요구하거나 재구성하지 않는다.

### Generic Parenthetical Bridge Risk

괄호 안 설명이 작품명/별칭/고유명사가 아니라 장르, 용어, 일반 분류인 경우를 별도 표시한다.

- 예: `오러(판타지 용어)` -> `판타지 용어`
- generic bridge가 `resolved_title`, `relevance`, `reason`을 과도하게 강화했는지 확인한다.
- generic bridge만으로 final work resolution을 확정하지 않는다.
- generic bridge만으로 확정한 케이스는 `HOLD` 또는 `REJECT` 후보로 둔다.
- 이 유형은 search risk와 judgment overconfidence risk에 모두 해당할 수 있다.

### Broad Topic and Character Composite Risk

넓은 원전/장르/소재 화제가 특정 작품명으로 승격되는 경우를 별도 표시한다.

- 예: `삼국지 떡밥`, `OO 얘기`, `OO 논쟁`, `OO 화제`, `OO 캐릭터`처럼 소재 전체를 말하는 title.
- 댓글에 캐릭터명, 원전 인물명, 밈성 답변이 있어도 원문에 특정 작품명/플랫폼 URL/고유 설정이 없으면 단일 `resolved_title`로 확정하지 않는다.
- `slang_insight.scope=work_plus_character` 또는 `store_reason=character_attached_composite`이면 broad topic bucket에서 `HOLD` 또는 `REPROCESS` 우선이다.
- body가 `OO?`처럼 추측형 alias이고 댓글이 다른 alias/작품 답변을 반복하면 body guess와 comment answer conflict로 기록한다.
- 대표 회귀: `10529582`는 `삼국지 떡밥`이 `삼국지 태사자`로 승격되면 오판이며, v94 기준 title null/off-topic으로 보정됐다.

## 11. Search Quality Review

확인 항목:

- weak evidence
- irrelevant evidence
- search degraded/timeout/upstream zero
- duplicate results
- source bias
- evidence filter overdrop
- evidence filter underfilter
- 검색 결과 0 또는 빈약한 상태에서 강한 final resolution이 발생했는지

## 12. `slang_db` Review

`저장 안 됨`을 한 가지 상태로 뭉뚱그리지 않는다. 아래 상태를 구분한다.

- `saved_confirmed_alias`
- `saved_pending_alias`
- `saved_family_alias`
- `saved_secondary_reference`
- `comparison_only`
- `blocked_noise`
- `blocked_unclear_canonical`
- `blocked_same_as_title`
- `blocked_sentence_like`
- `not_extracted`
- `extracted_not_persisted`
- `persisted_but_not_displayed`

확인 항목:

- 실행 옵션에서 `slang_db` on/off
- 사용한 `slang_db` 경로
- 로드 카운트
- run 당시 snapshot과 현재 repo `slang_db/slang_db.json` 차이
- insight/store/block counts
- `confirmed_alias`, `pending_alias`, `secondary_reference`, `comparison_only`, `noise`, `unclear_canonical_alias`, `family_aliases` 분포
- 실제 후보가 저장되지 않은 것인지, 보류/차단/패밀리 alias로 들어간 것인지
- 문장형 term, title과 동일 alias, 일반어 오염 여부
- dashboard/API에서 저장 안 된 것처럼 보이는 표시 문제

`extracted_not_persisted`는 저장 파이프라인 문제이고, `persisted_but_not_displayed`는 UI/API 표시 문제다. 두 이슈를 같은 원인으로 묶지 않는다.

## 13. GO / REVIEW / NO-GO Gate

`GO`:

- 핵심 파일이 존재하고 run integrity가 설명 가능하다.
- completed/failed/pending/flushed/checkpoint rows가 정합적이다.
- fatal/error/timeout/degraded 문제가 국소적이다.
- `QUALITATIVE_SEMANTIC_REVIEW_LOOP` 산출물이 존재하고 random control과 high-risk bucket 결과가 분리 보고됐다.
- 공개 판단 근거 샘플에서 과잉 확정, generic bridge, `slang_db` 오염이 심각하지 않다.
- run integrity와 semantic decision quality가 모두 `GO`다.

`REVIEW`:

- 런은 완료되었으나 일부 파일 누락, 카운트 불일치, 검색 degraded, 판단 과잉, `slang_db` 혼선이 있다.
- smoke/canary는 성공했으나 대량 결과 품질을 승인할 근거가 부족하다.
- dashboard/API 표시와 실제 저장 상태가 다를 가능성이 있다.
- 자동 감사는 완료됐지만 자연어 리뷰 packet, label, gate 산출물이 미완료다.
- 자연어 리뷰에서 `HOLD`, `REPROCESS`, `INFO_MISSING`가 남아 대량 승인 근거가 부족하다.

`NO-GO`:

- checkpoint/manifest/run audit/log 등 핵심 증거가 없어 런 검증이 불가능하다.
- completed/failed/pending/flushed 정합성이 깨졌다.
- 최초 실패가 worker/shard/search/VLM/OCR 전체 fanout으로 확산되었다.
- 약한 evidence로 강한 final work resolution이 반복된다.
- `slang_db`에 일반어, 문장형 term, title 동일 alias 등 대량 오염 가능성이 있다.
- 자연어 리뷰에서 generic/common surface promotion, canonical drift, false positive/false negative가 반복되어 semantic decision quality가 승인 불가다.
- 자동 감사 결과만으로 대량 결과를 `GO` 처리하려는 경우다.

## 14. Failure Taxonomy

Runtime:

- `process_crash`
- `worker_stuck`
- `shard_degraded`
- `checkpoint_mismatch`
- `flush_missing`
- `retry_exhausted`
- `timeout_fanout`
- `VLM/OCR_unavailable`
- `browser_visual_missing`
- `browser_access_failed`
- `visual_ocr_contradiction`
- `log_incomplete`

Search:

- `search_timeout`
- `search_degraded`
- `weak_evidence`
- `irrelevant_evidence`
- `generic_parenthetical_bridge`
- `role_or_honorific_alias_rescue_blocked`
- `topic_particle_title_lead_alias_anchor`
- `duplicate_results`
- `source_bias`
- `evidence_filter_overdrop`
- `evidence_filter_underfilter`

Judgment Quality:

- `overconfident_resolution`
- `unresolved_should_remain_unresolved`
- `multi_work_confusion`
- `adjacent_work_confusion`
- `trope_vs_title_confusion`
- `author_talk_misread`
- `title_alias_confusion`
- `role_or_honorific_alias_confusion`
- `reason_field_contradiction`
- `risk_tags_missing`

`slang_db`:

- `not_loaded`
- `wrong_path_loaded`
- `snapshot_mismatch`
- `candidate_not_stored`
- `candidate_blocked`
- `pending_alias_expected`
- `family_alias_expected`
- `comparison_only_expected`
- `noise_pollution`
- `sentence_like_term`
- `alias_same_as_title`
- `unclear_canonical_alias`
- `dashboard_display_gap`
- `api_display_gap`

Docs/Tooling:

- `missing_review_packet`
- `missing_run_audit`
- `insufficient_manifest`
- `issue_template_gap`
- `checklist_gate_gap`
- `missing_semantic_review_loop`
- `missing_sample_manifest`
- `missing_review_labels`
- `missing_gate_decision`

## 15. Issue Generation

규칙:

- 동일 원인으로 보이는 여러 post는 하나의 systemic issue로 묶는다.
- 개별 post id는 Evidence examples로만 사용한다.
- 특정 post id나 제목에 대한 하드코딩 수정을 제안하지 않는다.
- 단일 post 문제는 우선 재처리/정성 리뷰 대상으로 분류한다.
- 반복 패턴이 확인될 때만 개선 이슈로 승격한다.

Priority 기준:

- `P0`: 결과 전체 신뢰 불가, checkpoint/run audit/log 정합성 붕괴, 대량 오판 또는 `slang_db` 대량 오염 가능성
- `P1`: 특정 유형의 반복 오판, 검색 품질 저하가 final judgment에 영향, `slang_db` 저장/차단/표시 혼선 반복
- `P2`: 문서화 부족, dashboard/API 표시 개선, 리뷰 편의성/툴링 개선, 일부 edge case 품질 개선

이슈 템플릿:

```markdown
## IMP-YYYYMMDD-NNN - 짧은 제목

- Priority: P0 | P1 | P2
- Type: runtime | quality | slang_db | search | docs | tooling
- Status: proposed
- Evidence:
- Problem:
- Hypothesis:
- Proposed action:
- Verification:
- Docs to update:
- Done condition:
```

## 16. Action Queue

- `Re-run required`: 런타임 문제로 결과 신뢰 불가
- `Re-search required`: evidence가 약하거나 search degraded
- `Re-judge required`: evidence는 있으나 판단이 과잉/모순
- `Human qualitative review required`: `multi_work`, `adjacent`, `trope`, `author_talk` 등 경계 케이스
- `Semantic review loop required`: 자동 감사만 있고 자연어 품질 packet/label/gate 산출물이 없음
- `slang_db review required`: alias 저장/차단/오염 여부 확인 필요
- `Docs/checklist update required`: 반복 방지를 위한 문서 gate 추가 필요

## 17. Output Template

```markdown
## 1. 결론

- 전체 판정: GO | REVIEW | NO-GO
- run integrity 판정: GO | REVIEW | NO-GO
- semantic decision quality 판정: GO | REVIEW | NO-GO
- 가장 큰 위험 3개:
- 바로 해야 할 작업 3개:

## 2. 증거 맵

- run id:
- 입력/결과 디렉토리:
- 사용한 핵심 파일:
- 누락된 파일:
- 신뢰 가능한 증거:
- 추정에 가까운 부분:

## 3. 로그/처리 흐름 리뷰

- 최초 실패:
- 후속 증상:
- worker/shard/search/VLM/OCR/slang_db 관찰:
- 런타임 안정성 판정:

## 4. 판단 품질 리뷰

- 근거와 판정이 맞는 케이스:
- 근거 부족/과잉 확정 케이스:
- random control 결과:
- high-risk bucket 결과:
- qualitative review artifacts:
- 재검색 대상:
- 재처리 대상:
- 정성 리뷰 패킷이 필요한 대상:

## 5. slang_db 리뷰

- 로드/참조/저장/차단 상태:
- confirmed/pending/family_alias/blocked/noise 분류:
- 오염 위험:
- 회수율 손실 가능성:
- dashboard/API 표시 개선점:

## 6. 지침/문서 개선안

- 새 문서/기존 문서 수정 제안:
- 체크리스트 추가 항목:
- 이슈트래커 템플릿:

## 7. 이슈 후보

- IMP 후보:

## 8. Action queue

- Re-run required:
- Re-search required:
- Re-judge required:
- Human qualitative review required:
- slang_db review required:
- Docs/checklist update required:

## 9. Gate decision rationale

- GO/REVIEW/NO-GO 판정 근거:
- 판정에 사용한 Strong evidence:
- 판정에 영향을 준 Missing/Weak evidence:
- smoke/canary와 대량 품질 승인 사이의 차이:
```
## 2026-05-29 Official URL Evidence Rule

- `official_urls`는 작품 상세 URL만 센다.
- 작가 페이지, 검색/목록/랭킹/장르 페이지, 플랫폼 댓글 탭(`tab_type=comment`), 커뮤니티/위키 URL은 검색 참고 근거일 수는 있지만 official detail evidence가 아니다.
- `reason`의 `official_urls>0`와 최종 `heretic_url=null`이 충돌하면 `official_url_count_mismatch` 또는 `review_tooling` 이슈로 분리한다.
- URL 없는 resolved title은 title 판정과 official detail evidence strength를 분리해서 보고한다.

## 2026-05-30 VLM/OCR Direct Image Title Rule

- VLM/OCR이 `explicit_text|cover_title`, `title_role=work_title`, `promotion_eligible=true`로 단일 작품 표면을 읽으면 검색 URL 부족만으로 `noise` 처리하지 않는다.
- direct image title은 검색 snippet이 아니라 원문 이미지에서 나온 별도 evidence edge로 기록한다.
- 배경 목록, 추천/랭킹/검색 결과 화면, 다중 제목 카탈로그 이미지는 direct image title rescue 대상이 아니다.
- official detail URL은 여전히 별도 검증한다. URL 후보의 대표 제목이 선택 title과 다르면 `url_title_mismatch`로 제거한다.
- direct image evidence로 title은 `ACCEPT` 가능해도 URL evidence가 없으면 URL strength는 `Missing`으로 분리한다.
- 대표 사례: `11718117` v275는 `아카데미의 피해자`를 direct image evidence로 복구했지만 `heretic_url=null`을 유지했다.

## 2026-05-30 Final Meaning Reread / URL Synopsis Rule

- 표현 오타/축약 패턴(범용)처럼 표면어가 작품명/별칭이 아니라 오타, 축약, 감상 문장으로 읽히는 경우는 검색 후보를 올리기 전에만이 아니라 final candidate 이후에도 다시 읽는다.
- final semantic reread는 `title/body/comment`, `surface_paraphrase_notes`, discourse warning, search evidence, VLM/OCR evidence를 함께 보고 "원문이 실제로 이 작품을 말하는가"를 확인한다.
- 이 규칙은 특정 `post_id`, 특정 작품명, 특정 문자열을 하드코딩하지 않는다. `context_only`, `semantic_seed_review`, `surface_paraphrase`, `weak/missing evidence`, direct anchor 유무로 판단한다.
- 같은 official detail URL의 검색 결과 title/snippet이 최종 작품명을 직접 지지하면, fetch/page analyzer 대표 제목이 플랫폼 브랜딩이나 시놉시스 문장으로 잡혀도 URL mismatch로 즉시 제거하지 않는다.
- 반대로 같은 URL 검색 결과도 다른 작품명, 목록/검색/댓글 탭, 비소설 매체, 팬픽/파생 URL만 지지하면 stale URL로 제거한다.
- visual-only VLM 결과는 title grounding이 아니다. reason에는 "이미지/VLM은 보조 정보만 제공했고 최종 제목 확정 근거로 사용하지 않았다"고 분리한다.
- 대표 사례: `11718091` v282는 표현 오타/축약 패턴(범용)로 처리되어 `official_title=null`; `11718097` v282는 같은 URL 검색 title/snippet 근거로 `https://m.munpia.com/novel/detail/328421`을 보존했다.

## 2026-06-01 Known Title Abbreviation / Incomplete Canary Rule

- `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY`는 모두 provenance가 다른 alias source다. packet/review에는 어떤 registry가 어떤 surface에서 final title을 지지했는지 남긴다.
- `KNOWN_TITLE_ABBREVIATIONS`는 hardcoded single-case fix가 아니라 curated registry다. 다만 registry hit만으로 semantic `GO`를 열지 않고, 원문 title/body/comment와 work anchor를 함께 본다.
- known title abbreviation이 post title/body에 있고 회차/스포/작가의 말/positive work intent 같은 packet-local work anchor가 있으면 explicit alias support로 볼 수 있다.
- semantic no-work, community banter, context-only 상태에서는 direct post/visual work anchor 또는 위 contextual work anchor 없이 known abbreviation/search/snippet만으로 title을 되살리지 않는다.
- numeric/episode-like 후보, 일반명사 후보, character/surface 후보는 known abbreviation 후보와 provenance를 분리한다. 예: 안정 약칭 후보와 `305호`류 회차/장소/번호 후보를 같은 evidence로 합치지 않는다.
- 단건 canary라도 result JSON, checkpoint completed row, manifest completed/flushed/pending/failed, worker completion log가 모두 정합적이어야 완료 산출물이다.
- LLM 판단 로그가 `Orchestrator 완료`까지 있어도 output write/flush summary가 없고 result/checkpoint row가 없으면 `REPROCESS/runtime-incomplete`로 둔다.
- shard health가 OK이고 docker lifecycle restart가 없으면 runtime-incomplete 원인을 shard restart로 단정하지 않는다. run completion, infrastructure, semantic drift를 분리 보고한다.
- 대표 사례: v446 `11718120`은 shard OK와 semantic drift 로그가 있었지만 result/checkpoint completed row가 없어 approval source가 아니다. v447은 `KNOWN_TITLE_ABBREVIATIONS` support 경로를 targeted test로 닫았지만 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 Registry Alias Evidence Rule v477

- `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY` hit는 recall/provenance hint이며 단독 semantic evidence가 아니다.
- 등록 약칭만으로 `resolved_title`, `High`, `known_abbreviation_unverified`, stability/lock, Arbiter guard exception을 만들면 hardcoded alias positive path로 리뷰한다.
- 허용 조건은 `visible alias surface + semantic no-work 차단 통과 + 독립 work anchor`다.
- 독립 work anchor는 공식/detail URL, 검색 title/snippet의 정식 제목 직접 지지, 원문/댓글의 정식 제목 직접 언급, VLM/OCR 직접 작품명, verified character-work link, 회차/스포/작가의 말/연재/캐릭터 같은 packet-local 작품 토론 맥락 중 하나 이상이어야 한다.
- 주의: 이 절의 `독립 work anchor`는 일반 registry 후보 검토용 evidence tier다. semantic no-work/context-only 신호가 있으면 공식/detail URL, 검색 title/snippet, canonical convergence, episode ref 단독은 no-work 해제용 strict direct anchor가 아니다. 이 경우 `_can_promote_title_after_semantic_no_work()` 기준 raw post surface, 직접 VLM/OCR 작품 표면, verified packet-local work anchor만 인정한다.
- registry hit, alias 표면 단독, 검색 self-hit, prompt note, source registry provenance tuple은 독립 anchor가 아니다.
- `known_abbreviation_unverified` 같은 미검증 rescue source가 산출물에 남으면 `HOLD` 또는 `REJECT` 후보로 보고, 코드/packet 양쪽에서 action queue를 만든다.
- hardcoded alias audit와 packet label closure는 분리한다. packet labels가 `ACCEPT`로 닫혀도 registry positive path가 남으면 hardcoded alias gate는 계속 `REVIEW`다.

### v478 적용 범위 확장

- 같은 규칙은 final rescue뿐 아니라 suspected title, high-fit interpretation 자동 승격, weak thematic guard exception에도 적용한다.
- `ctx._resolved_mappings`가 registry pair를 포함해도 독립 anchor가 없으면 suspected title로 올리지 않는다.
- `novel_title + context_fit=high`는 공개 LLM 해석일 수 있지만, registry pair만으로 낮은 약칭 정합성 guard를 우회할 수는 없다.
- weak thematic/title drift guard는 registry pair가 아니라 snippet/search/post evidence가 alias-title 관계를 직접 지지할 때만 예외를 허용한다.

### v484 적용 범위 확장

- v479/v480이 registry alias의 anchor 존재 여부를 줄였다면, v484는 anchor가 있어도 `High` 확정으로 바로 올라가지 않게 confidence/evidence tier를 분리한다.
- post-side work anchor는 후보 검토 허용 조건이다. `High` final rescue에는 official/detail URL, fetched official title, strict full-title evidence, VLM/OCR direct work title, verified character-work link 같은 독립 hard support가 필요하다.
- registry+anchor만 있는 packet은 전체 승인 증거가 아니라 `Medium/HOLD/re_judge` 후보로 남긴다.
- 이 targeted guard가 통과해도 hardcoded alias positive path review, completed source, random 1000, P0/P1 expansion 전까지 10만 semantic approval은 `REVIEW-LOCKED`다.
