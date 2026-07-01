# Qualitative Semantic Review Loop

대량 테스트 런의 자연어 판정 품질을 검증하기 위한 표본 리뷰 규격이다.

이 문서는 `result_scan`, `run_audit`, 로그 카운트 요약을 품질 승인으로 오해하지 않도록, 자동 감사와 자연어 판정 품질 리뷰를 분리하는 데 목적이 있다.

## 1. Hard Gate

중요:

- `result_scan`, `run_audit`, count summary는 자동 감사와 런 정합성 리뷰로만 취급한다.
- 자동 감사 완료는 `런은 돌아갔다`는 증거이지, `판정이 말이 된다`는 증거가 아니다.
- 대량 런 `GO`는 run integrity와 semantic decision quality가 모두 통과했을 때만 가능하다.
- hidden chain-of-thought는 요구하거나 추정하지 않는다.
- 공개된 `title`, `body`, `comments`, `reason`, `decision`, `evidence`, `search flags`, `checkpoint fields`만 사용한다.
- 대형 review에서 독립 위험축이 2개 이상이면 Codex `spawn_agent` subagent를 기본 병렬 투입한다. 다만 각 subagent는 읽기 전용 감사 또는 명시된 disjoint write scope만 맡고, 최종 label/gate 통합은 메인 Codex가 한국어 산출물로 한 번만 수행한다.
- 이 subagent 병렬은 Codex goal 운영 방식이다. repo 내부 `expert_main.py --parallel`, shard/worker 수, `src/llm_batch/experts/*` 전문가 체인 병렬을 늘리라는 뜻이 아니다.
- subagent 부족은 `expert_main.py --parallel` 재실행으로 해결하지 않는다. 필요한 경우 `semantic`, `VLM/browser`, `runtime/log`, `prompt/pipeline`, `docs/checklist` 축을 추가 spawn하고, 각 subagent의 read/write scope를 분리한다.
- `runtime_contract=GO` 또는 targeted canary `GO`가 나와도 completed VLM/OCR-on source, Browser visual/image-loading gate, random baseline 1000건 이상, P0/P1 high-risk expansion이 닫히기 전까지 10만 semantic approval은 `NO-GO / REVIEW-LOCKED`로 둔다.
- initial 472건 정성 리뷰, random 1000/2400, high-risk expansion, targeted canary는 반드시 `run_id`와 source path별로 분리 기록한다. 다른 source의 승인 근거로 이월하지 않는다.

## 1-1. Review Artifact Language

리뷰, 분석, 검토, 피드백 목적의 사람이 읽는 문서는 한국어로 작성한다.

- Markdown 본문, summary, rationale, reviewer note, gate decision, action queue 설명은 한국어로 쓴다.
- 보고서는 간략하게 쓰되 의미, 근거, 산출물 경로, gate 상태를 생략하지 않는다.
- JSON key, enum label, action id, bucket id, 파일명, 명령어, 로그 원문, 코드 심볼은 기존 영문/원문 표기를 유지한다.
- 원문 evidence나 snippet이 한국어가 아니면 필요한 만큼만 인용하고, 해석과 판단은 한국어로 요약한다.
- 자동 생성 도구가 Markdown을 만들 때도 heading과 설명 문장은 한국어를 기본값으로 둔다.
- 기존 과거 산출물의 영문 문구는 이력으로 보존할 수 있지만, 새 리뷰/재검토/피드백 산출물은 한국어 기준을 적용한다.

## 2. Three-Layer Review Model

### 1층: Mechanical Run Audit

- manifest
- checkpoint
- completed/failed/pending/flushed
- timeout/error/fatal
- worker/shard/search degradation
- VLM/OCR request/failure/skip
- `slang_db` load/store/block counts

### 2층: Risk-Bucket Semantic Sampling

- random control sample
- search degraded or timeout
- weak evidence but strong resolution
- reason overconfidence
- unresolved, multi_work, adjacent, trope, author_talk
- generic parenthetical bridge
- slang alias candidate/store/block/pending/family/noise
- VLM/OCR involved
- worker/shard degraded window
- regression-style targeted failure pattern

### 3층: Natural-Language Judgment Review

각 sample에서 아래를 확인한다.

- 이 글이 실제로 무엇을 말하는가?
- 모델이 무엇을 작품, 별칭, 용어로 해석했는가?
- evidence가 결론을 직접 지지하는가?
- reason이 evidence보다 세게 말하지 않는가?
- 재검색, 재판정, 재처리, 인간 리뷰, 폐기 중 어디로 보내야 하는가?
- 재해독이 필요한 표면은 `표현 오타/축약 패턴(범용)` 신호로만 둔다. 특정 정상형 복원이나 계열 자동규칙으로 고정하지 말고, 먼저 title/body/comment/comment_dialogue의 자연어 의도와 발화 행위를 재독해한다.
- 의미 재독해 실패는 특정 문자열 하드코딩이 아니라 `surface_paraphrase_notes`, `semantic_seed_review`, `context_only_no_work_anchor`, `friend_social_lament_or_generic_discourse` 같은 구조 신호와 공개 근거 부족으로 기록한다.
- no-work/context-only/intent-denied가 공개 필드에 남았는데 후단 search/known alias/`slang_db`/`BatchContext`/canonical rescue가 direct hard anchor 없이 title을 되살리면 `context_only_late_rescue_without_direct_anchor`로 기록한다.
- 후단 최종 검증기, 후보 승격, unresolved 단일 후보 승격, recommendation guard 해제가 Decoder alias + official URL/search evidence/canonical convergence/episode ref 단독으로 no-work를 뒤집으면 `decoder_alias_official_url_late_promotion` 하위 패턴으로 묶는다.
- 플랫폼/UI/메타 잡담처럼 broad novel/platform context는 있지만 direct title/alias/author/plot/round anchor가 없는 비관련 글은 `unresolved_matchable`가 아니라 `context_only` 후보로 검토한다. VLM/OCR 이미지가 background listing 또는 character visual only면 title evidence로 승격하지 않는다.

## 3. Review Labels

`ACCEPT`:

- post 원문, evidence, reason, final decision이 자연어적으로 정합적이다.
- 검색 evidence가 결론을 충분히 직접 지지한다.
- unresolved, adjacent, trope, author_talk 같은 경계 위험이 크지 않다.

`HOLD`:

- 결론이 그럴듯하지만 evidence가 부족하거나 reason이 약하다.
- 즉시 reject는 아니지만 대량 승인 근거로 쓰기 어렵다.
- 추가 검색 또는 인간 리뷰가 있으면 확정 가능하다.

`REPROCESS`:

- 검색 degraded, evidence 부족, OCR/VLM 실패, checkpoint/field 결손 등으로 재처리가 필요하다.
- 핵심 문제는 판단 자체보다 입력, 검색, 처리 품질이다.

`REJECT`:

- final decision이 명백히 틀렸거나 evidence와 reason이 결론을 지지하지 않는다.
- generic term, parenthetical bridge, 잘못된 alias, 인접 작품 혼동, trope/title 혼동 등으로 오판했다.

`INFO_MISSING`:

- 리뷰에 필요한 title/body/comment/evidence/reason/final field가 없다.
- 결론을 내릴 수 없으므로 품질 승인에 사용하지 않는다.

## 4. Per-Sample Review Questions

각 sample packet에 대해 아래 질문에 짧게 답한다.

1. Post intent:
   - 이 글은 자연어적으로 무엇을 말하는가?
   - 작품 찾기, 별칭 언급, 장르/트로프, 작가, 플랫폼, 잡담 중 무엇인가?
2. Model decision:
   - 모델의 `resolved_title`, `relevance`, final decision은 무엇인가?
3. Evidence alignment:
   - evidence URL/snippet이 결론을 직접 지지하는가?
   - 단순히 비슷한 단어만 잡은 것인가?
4. Reason quality:
   - reason이 evidence보다 과하게 확정했는가?
   - 가능성 수준인데 확정처럼 썼는가?
5. Boundary risk:
   - unresolved, multi_work, adjacent, trope, author_talk, generic term, alias confusion 위험이 있는가?
6. `slang_db` effect:
   - slang alias/term이 판정에 도움을 줬는가?
   - 오염, 일반어, 문장형 term, title 동일 alias, 표시 혼선 위험이 있는가?
7. Final review label:
   - `ACCEPT`, `HOLD`, `REPROCESS`, `REJECT`, `INFO_MISSING` 중 무엇인가?
8. Action:
   - `no_action`, `re_search`, `re_judge`, `re_run`, `human_review`, `slang_db_review`, `docs_issue` 중 무엇인가?

## 5. Sampling Requirements

무작위 표본과 위험 bucket 과표집을 반드시 병행한다.

주의:

- 이 절의 random `100~300`건, bucket `30~100`건은 initial semantic triage 최소 기준이다.
- 10만 건 scan approval, semantic `GO`, systemic issue 해소 판단에는 이 최소 표본만 사용하지 않는다.
- 10만 건 규모에서는 Large-scale expansion 기준을 적용한다. 최소 random baseline `1000`건 이상, P0/P1 high-risk bucket별 `200~500`건, bucket population/selected/coverage ratio, `target_satisfied=true`를 별도로 기록한다.
- initial triage, random baseline, high-risk expansion, targeted canary는 source path와 `run_id`별로 분리 보고하며 오류율을 섞지 않는다.

### A. Random Control Sample

- 전체 결과에서 무작위 `100~300`건.
- 목적: 일반적인 오판율과 근거 품질 기준선을 확인한다.

### B. High-Risk Semantic Buckets

각 bucket에서 `30~100`건씩 과표집한다. 런 규모나 비용이 제한되면 sample 수를 줄이되, 줄인 사유를 `sample_manifest.json`에 기록한다.

- `search_degraded_or_timeout`
- `weak_evidence_but_strong_resolution`
- `generic_parenthetical_bridge`
- `generic_abstract_title_collision`
- `ocr_explicit_title_unresolved`
- `context_only_late_rescue_without_direct_anchor`
- `decoder_alias_official_url_late_promotion`
- `unresolved_to_resolved`
- `multi_work_or_adjacent_risk`
- `trope_or_author_talk_risk`
- `reason_decision_contradiction`
- `final_semantic_reread_missing_for_semantic_seed`
- `final_semantic_reread_reviewed`
- `official_url_synopsis_or_branding_mismatch`
- `role_or_honorific_alias_rescue_blocked`
- `topic_particle_title_lead_alias_anchor`
- `slang_db_store_block_pending_family_noise`
- `VLM_OCR_involved`
- `VLM_OCR_direct_image_title`
- `worker_or_shard_degraded_window`
- `random_control`

### C. Regression-Style Targeted Sample

- 이전 `TODO`, `HISTORY`, `VERIFICATION_RESULTS`, `IMPROVEMENT_REGISTER`에 기록된 실패 유형과 유사한 케이스를 추출한다.
- 특정 post id 하드코딩이 아니라 실패 유형 기준으로 묶는다.

## 6. Required Packet Fields

`review_packets.jsonl`의 각 row는 가능한 한 아래 field를 포함한다.

- `run_id`
- `packet_id`
- `bucket`
- `post_id`
- `gallery_id`
- `post_author`
- `source_path`
- `checkpoint_row_index` 또는 `line_number`
- `title`
- `body_excerpt`
- `content_blocks`: 원문 block 순서. text/image 구분과 image URL을 유지한다.
- `image_urls`
- `image_count`
- `comment_excerpt`
- `comment_metadata`: `comment_id`, `author`, `ip`, `speaker`, `is_post_author`, `reply_to_comment_id`, `reply_level`
- `comment_context_lines`: 댓글 본문과 분리된 공개 작성자/대화 맥락. 가능한 경우 `speaker`, `author`, `role=post_author`, `ip`, `reply_level`, `reply_to`, `comment_id`를 포함한다. author/IP를 댓글 텍스트에 직접 섞지 않는다.
- `comment_dialogue_context_lines`: `#번호 + speaker/author/ip/reply + 댓글 text excerpt`를 같은 줄에 둔 대화 재구성. 본문 작성자 댓글 이어쓰기와 타 유저 답변 흐름을 자연어로 검토하기 위한 필드이며, speaker/author/ip 자체는 작품명 근거가 아니다.
- `resolved_title`
- `relevance`
- `final_decision_fields`
- `reason`
- `risk_tags`
- `search_health_flags`
- `evidence_urls`
- `evidence_snippets`
- `prompt_public_fields`
- `result_public_fields`
- `vlm_ocr_fields`: `identity.image_evidence_catalog`, `image_enrichment`, OCR/VLM summary, conflict flags, fetch/failure counters
- `browser_visual_fields`, VLM/OCR 시각 확인이 필요한 경우
- `slang_db_fields`
- `worker`
- `shard`
- `timestamp`

`title/body/comment`가 빠지면 자연어 리뷰가 아니라 결과 필드 리뷰로 취급한다.

### VLM/OCR Browser Visual Verification

`VLM_OCR_involved`, `image_evidence_catalog_missing`, `vlm_ocr_evidence_gap`, `ocr_explicit_title_unresolved`, OCR-derived title/resolved title, image-only evidence, OCR conflict/corruption, screenshot/webtoon panel 기반 판정은 log/result field만 보고 `ACCEPT`하지 않는다.

브라우저 실행 지침:

- 기본 브라우저는 Codex 내장 Browser plugin의 in-app browser `iab`다. 사용자가 `@browser` 또는 코덱스 내장 브라우저를 지정하면 반드시 이 표면으로 진행한다.
- 내장 브라우저에서는 현재 URL, page title, visible text, screenshot, DOM snapshot 또는 화면 관찰을 packet에 남긴다.
- Playwright CLI, 외부 Chrome, headless script는 내장 브라우저 연결이 실제로 불가능하거나 대량 배치 캡처 자동화가 필요한 경우의 fallback이다.
- fallback 사용 시 `browser_surface`, `fallback_reason`, `attempted_in_app_browser`, `capture_command`, `stdout/stderr path`를 manifest에 기록한다.
- fallback으로 얻은 screenshot은 증거로 보존할 수 있지만, 내장 브라우저/사람 판독의 직접 관찰 없이 `ACCEPT`로 승격하지 않는다.

필수 절차:

- 원문 post URL, image URL, evidence URL 중 접근 가능한 원본을 실제 브라우저로 연다.
- packet에 `content_blocks`, `image_urls`, `image_count`, `identity.image_evidence_catalog` 또는 동등한 `vlm_ocr_fields.image_evidence_catalog`가 있는지 먼저 확인한다.
- `post_id`, source URL, capture time, viewport, reviewer, screenshot path를 기록한다.
- DCInside처럼 lazy-load가 있는 원문은 본문 이미지 영역까지 스크롤하고 대기한 뒤 이미지 로딩 상태를 다시 기록한다.
- 본문 이미지 선택자(`.writing_view_box`, `.write_div`, `.imgwrap`)에서 `article_image_count`, `article_loaded_count`, `article_incomplete_count`, `article_placeholder_count`, `article_broken_count`를 남긴다.
- 본문 인라인 이미지가 0개라도 `원본 첨부파일`, `download.php`, `viewimagePop.php` 링크가 있으면 `article_attachment_file_count`, `article_attachment_links`를 남기고, Codex 내장 브라우저 `iab`에서 첨부 팝업 또는 직접 이미지 URL을 별도 확인한다.
- 브라우저 스크린샷 또는 캡처 이미지를 비전/수동 시각 판독으로 확인한다.
- visible text, title, character/work cue, panel context가 `ocr_text`, `resolved_title`, `reason`, final decision을 직접 지지하는지 기록한다.
- 브라우저 접근 실패, 삭제, 로그인/성인 인증, 404, blocked response는 `browser_access_failed`로 남기고 `INFO_MISSING`, `HOLD`, 또는 `REPROCESS`로 둔다. 이 경우 OCR 로그만으로 `ACCEPT`하지 않는다.
- 페이지가 열렸더라도 본문 이미지가 `gallview_loading` placeholder, incomplete, broken 상태로 남으면 `Strong`이 아니다. VLM/OCR 판단은 `REPROCESS` 또는 `INFO_MISSING`으로 보낸다.
- 첨부 팝업 이미지가 로드됐더라도 이미지 내용이 `resolved_title`/reason/final decision을 직접 지지하지 않으면 `ACCEPT`하지 않고 `HOLD/human_review`로 둔다.
- 스크린샷이 OCR 또는 모델 reason과 충돌하면 `REJECT` 또는 `REPROCESS` 후보로 둔다.
- 스크린샷이 작품 단서를 보여도 검색 evidence가 약하면 직접 작품 evidence가 보강되기 전까지 `HOLD`로 둔다.
- VLM/OCR이 `explicit_text|cover_title`, `title_role=work_title`, `promotion_eligible=true`로 단일 작품 표면을 읽은 경우는 검색 URL 부족만으로 `noise` 처리하지 않는다. 단, official detail URL evidence는 별도 grade로 둔다.
- 다른 작품 대표 제목을 가진 URL이 붙으면 `url_title_mismatch`로 제거하고, title correctness와 URL evidence strength를 분리해 라벨링한다.
- 스크린샷은 리뷰에 필요한 최소 범위만 보존하고, 공개 관찰 요약만 남긴다. hidden chain-of-thought는 요구하거나 기록하지 않는다.

VLM/OCR packet 추가 field:

- `browser_visual_required`
- `image_evidence_catalog`
- `image_evidence_catalog_missing`
- `vlm_enabled`, `ocr_enabled`, `vlm_enrichment_used`
- `image_fetch_count`, `image_fetch_success`, `vlm_chunks_sent`, `vlm_total_bytes`
- `image_enrichment_limitations`, 있으면
- `content_blocks`
- `image_urls`
- `image_count`
- `browser_surface`
- `fallback_reason`, fallback을 쓴 경우
- `browser_url`
- `browser_access_status`
- `screenshot_path`
- `article_image_count`
- `article_loaded_count`
- `article_incomplete_count`
- `article_placeholder_count`
- `article_broken_count`
- `article_attachment_file_count`
- `article_attachment_links`
- `attachment_popup_screenshot_path`, 첨부 팝업 또는 직접 이미지를 연 경우
- `attachment_image_natural_width`, `attachment_image_natural_height`
- `image_lazy_load_scroll_attempts`
- `vision_observation`
- `visual_evidence_grade`: `Strong`, `Medium`, `Weak`, `Missing`
- `visual_review_label`

## 7. Generic Parenthetical Bridge Bucket

`generic_parenthetical_bridge`는 반드시 별도 bucket으로 추출한다.

조건:

- 괄호 안 설명이 작품명, 별칭, 고유명사가 아니라 장르, 용어, 일반 분류다.
- 예: `오러(판타지 용어)` -> `판타지 용어`.
- 이 bridge가 `resolved_title`, `relevance`, `reason`을 강화했는지 확인한다.
- generic bridge만으로 작품 판정을 확정한 케이스는 `HOLD` 또는 `REJECT` 후보로 둔다.
- 반복되면 search quality와 judgment quality 이슈로 승격한다.

## 8. Role/Honorific Alias Rescue Bucket

`role_or_honorific_alias_rescue_blocked`는 별도 bucket으로 추출한다.

조건:

- 역할, 지위, 호칭, 관계 표현이 검색 추론 alias 또는 batch memory alias rescue에 사용됐다.
- 예: `족장님`, `대족장님`, `선생`, `마왕님`, `작가님`처럼 단독으로는 안정된 작품 별칭이라고 보기 어려운 표현.
- 원문 title/body/comment에 직접 작품명, 안정 별칭, 캐릭터-작품 연결, quote-source, 공식 detail edge가 없는데 final title이 확정됐는지 확인한다.
- 공식 detail edge, 회차/스포/작가의 말, 공식 플랫폼 URL은 일반 후보 검토의 보조 evidence일 수 있다. 단, no-work/context-only를 해제하려면 raw title/alias 표면, VLM/OCR 직접 작품 표면, verified character-work link처럼 packet-local direct anchor와 결합되어야 하며, 단독으로는 resolved title을 되살릴 수 없다.
- Arbiter/Verifier가 `official_title=null` 또는 `anchor=none`을 냈는데 후처리 rescue가 title을 되살린 경우는 `HOLD` 또는 `REJECT` 우선이다.
- final 삽입이 차단됐더라도 canonical suspect 단계에서 같은 후보가 반복 생성되면 후보 노이즈로 기록한다.

## 9. Topic-Particle Title Lead Alias Bucket

`topic_particle_title_lead_alias_anchor`는 별도 bucket으로 추출한다.

조건:

- 제목 첫 토큰에 조사가 붙은 표현에서 clean alias를 분리했다.
- 예: `망겜힐은 -> 망겜힐`, `빌환이 -> 빌환`.
- 이 clean alias가 검색 앵커, `search_evidence_alias_inference`, batch memory alias seed, final title correction 중 어디에 쓰였는지 기록한다.
- clean alias 보존은 final 확정 근거가 아니라 recall 보강이다. 원문 span과 검색 evidence가 직접 연결되지 않으면 `HOLD` 우선이다.
- 일반어, 역할·호칭성 표현, 저정보 표현이 이 bucket을 통해 title로 승격되면 `REJECT` 또는 `slang_db_review` 후보로 둔다.

## 10. Review Rounds

### Round 1

- random control `100~300`건.
- high-risk bucket별 초기 표본.
- 각 sample에 label과 action을 부여한다.
- 반복 실패 유형 taxonomy를 만든다.

### Round 2

- Round 1에서 발견된 상위 실패 유형별로 추가 표본을 추출한다.
- 실패가 단발인지 systemic인지 확인한다.
- post id가 아니라 failure pattern으로 묶는다.

### Round 3

- P0/P1 가능성이 있는 유형을 집중 재검토한다.
- `slang_db` 오염, generic bridge, overconfident resolution, search degraded 후 확정 판정 여부를 확인한다.

## 11. Stop Conditions

전수 판독 완료가 아니라 failure pattern saturation을 종료 조건으로 사용한다.

종료 조건:

- 최근 2개 round에서 새로운 실패 유형이 거의 나오지 않는다.
- 주요 위험 bucket별 대표 사례를 확보했다.
- random control과 high-risk bucket 결과가 분리 보고됐다.
- `ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING` 분포가 기록됐다.
- P0/P1/P2 이슈 후보가 issue template으로 정리됐다.
- GO/REVIEW/NO-GO 근거가 `Strong`, `Medium`, `Weak`, `Missing` evidence로 분류됐다.

## 12. Output Artifacts

런별 자연어 품질 리뷰 산출물은 아래 경로를 기본으로 한다.

- `qualitative_review/<run_id>/sample_manifest.json`
- `qualitative_review/<run_id>/review_packets.jsonl`
- `qualitative_review/<run_id>/review_labels.jsonl`
- `qualitative_review/<run_id>/pattern_summary.md`
- `qualitative_review/<run_id>/gate_decision.md`
- `qualitative_review/<run_id>/action_queue.md`
- `qualitative_review/<run_id>/round<N>_manifest.json`, 필요한 경우
- `qualitative_review/<run_id>/round<N>_packets.jsonl`, 필요한 경우
- `qualitative_review/<run_id>/round<N>_labels.jsonl`, 필요한 경우
- `qualitative_review/<run_id>/round<N>_summary.md`, 필요한 경우

`sample_manifest.json`:

- random control sample 수
- high-risk bucket별 sample 수
- 각 bucket 추출 조건
- 중복 제거 기준
- seed 또는 deterministic ordering 기준

`review_packets.jsonl`:

- 원문 맥락, evidence, decision, reason, flags를 포함한다.
- VLM/OCR 시각 확인 대상은 `browser_url`, `browser_access_status`, `screenshot_path`, `vision_observation`, `visual_evidence_grade`를 포함한다.

`review_labels.jsonl`:

- label
- 짧은 자연어 근거
- action queue
- VLM/OCR 시각 확인 대상은 screenshot/vision 관찰이 final label을 어떻게 바꿨는지 포함한다.
- evidence grade

`pattern_summary.md`:

- 반복 실패 유형
- 대표 evidence
- systemic issue 여부

`gate_decision.md`:

- run integrity와 semantic decision quality를 분리한 `GO/REVIEW/NO-GO`
- `Strong/Medium/Weak/Missing` evidence
- random control 결과
- high-risk bucket 결과

`action_queue.md`:

- `re_run`
- `re_search`
- `re_judge`
- `human_review`
- `slang_db_review`
- `docs_issue`

## 13. Reproducible Tooling

대량 result JSON에서 추가 round를 만들 때는 재현 가능한 seed와 bucket 조건을 남긴다.

현재 server-poc Round 2 기준 구현:

- script: `tools/build_qualitative_round2_review.py`
- 입력: `server-poc/expert_result_20260505_214349_324347.json`
- 출력: `qualitative_review/20260505_214349_324347/round2_manifest.json`, `round2_packets.jsonl`, `round2_labels.jsonl`, `round2_summary.md`
- seed: `20260505_214349_324347:round2_failure_pattern_expansion:v1`
- 주의: `worker_or_shard_degraded_window`와 `unresolved_to_resolved`는 checkpoint/shard/timestamp lineage가 없으면 partial/proxy bucket으로만 기록한다.

현재 server-poc Round 3 후보 준비 및 after 검증 구현:

- script: `tools/build_qualitative_round3_targets.py`
- 입력: `review_labels.jsonl`, `review_packets.jsonl`, `action_queue.json`, 원본 result JSON
- 출력: `round3_p0p1_manifest.json`, `round3_p0p1_candidates.jsonl`, `round3_targeted_input.jsonl`, `round3_issue_templates.md`, `round3_action_plan.md`
- seed: `20260505_214349_324347:round3_p0p1_targets:v1`
- after 실행: `round3_targeted_input.jsonl` `584`건을 현재 코드로 targeted re-search/re-judge/re-run했다.
- after 출력: `round3_after_merged_result.json`, `round3_after_packets.jsonl`, `round3_after_labels.jsonl`, `round3_after_action_queue.json`, `round3_after_action_queue.md`
- after 결과: `ACCEPT=179`, `HOLD=268`, `REPROCESS=137`, `REJECT=0`
- residual rerun 이력: `round3_after_rerun_input_re_search_re_run.jsonl` `189`건을 당시 기준 Gemma 4 4B `--parallel 32`로 재처리했다.
- 최신 후속 실행 기준: Gemma 4 4B 재확인/재처리 run은 `MCP_SHARD_COUNT=36` 및 shard audit `36/36` 여부를 같이 기록하되, 실제 worker 병렬도는 `min(input_count, 36)`으로 잡는다. 36은 상한이며 7건/25건 같은 소규모 targeted run에 고정 적용하지 않는다.
- latest combined: `round3_after_rerun_combined_summary.md`, `ACCEPT=195`, `HOLD=288`, `REPROCESS=101`, `REJECT=0`
- 주의: hard `REJECT`는 제거됐지만 P0/P1 targeted set 안에 `HOLD/REPROCESS=389`가 남아 있으므로 semantic gate는 계속 `NO-GO`다.

대량 scan 승인용 확장 기준:

- 400건 미만 random control은 rough triage로만 본다.
- 10만 건 규모에서는 random baseline `1000`건 이상을 우선 기준으로 둔다.
- P0/P1 high-risk bucket은 bucket별 `200~500`건을 기본 목표로 둔다.
- 표본 목표는 요청값과 실제 선택값을 분리 보고한다. source가 부족해 `requested=1000`, `selected<1000`이면 `sample_shortfall`을 manifest와 gate에 기록하고, 전체 품질 기준선으로 사용하지 않는다.
- high-risk bucket도 target 대비 selected가 부족하면 bucket별 `target_shortfalls`를 남기고, `target_satisfied=false`인 상태에서는 systemic 해소 또는 GO 근거로 쓰지 않는다.
- large-scale expansion 전에는 preflight를 먼저 실행한다. source completeness, manifest/checkpoint/pending 정합성, random baseline feasibility, high-risk bucket population을 확인하고, preflight가 `REVIEW-LOCKED`이면 expansion 산출물은 approval 근거가 아니라 부족 증거로만 둔다.
- pattern별 `8`건 표본은 issue template seed로만 취급하고 systemic 판단에는 쓰지 않는다.
- large-scale expansion 산출물은 `random_control_v3_*`, `high_risk_expansion_*`, `pattern_coverage_summary.md`, `expanded_gate_decision.md`로 분리한다.
- random baseline과 high-risk oversample은 절대 합쳐서 전체 오류율처럼 말하지 않는다.
- random control packet이라도 내부 `risk_tags`/`bucket_reasons`에 P0/P1 high-risk 조건이 있으면 해당 bucket의 label policy를 적용한다. `random_control`이라는 표본 출처가 `ACCEPT` 사유가 되면 안 된다.
- 같은 review dir에서 random control과 high-risk oversample을 모두 만들 때, random control에 이미 들어간 post_id라는 이유만으로 high-risk bucket 후보에서 제외하지 않는다. 두 층은 분리 보고하되 high-risk coverage는 보존한다.
- action queue를 후속 재런 입력으로 바꿀 때는 원본 `content_blocks`, `image_urls`, 댓글 row, author/IP metadata가 살아 있는 source를 우선 사용한다. result artifact가 이 필드를 잃었다면 원본 input JSONL/crawler source에서 복원하고, 복원 실패 건은 `image_source_missing_post_ids` 또는 `comment_source_missing`으로 gate에 남긴다.
- action별 dedupe는 post_id 하나만 보지 않는다. rerun 입력은 post 기준으로 1회만 실행해도 되지만, 같은 post의 `slang_db_review`, `human_review`, `browser_visual_required` packet은 별도 review action으로 보존한다.
- `VLM_OCR_direct_image_title` bucket은 positive control과 negative control을 함께 둔다. positive는 단일 직접 작품 표면, negative는 배경 목록/랭킹/검색 화면/다중 제목 카탈로그/타매체 스크린샷이다.

## 14. Issue Escalation

단일 post 문제는 먼저 `HOLD`, `REPROCESS`, `human_review`로 둔다.

반복 패턴이 확인될 때만 이슈로 승격한다.

- `P0`: 대량 결과 신뢰 불가, 전반적 오판, run integrity 붕괴, 대량 `slang_db` 오염 가능성.
- `P1`: 특정 유형의 반복 오판, generic bridge 반복, canonical drift 반복, false positive/false negative 반복.
- `P2`: 문서/패킷/대시보드/리뷰 도구 보강.

개별 post id는 evidence example로만 사용하고, 수정안은 실패 유형과 검증 기준으로 작성한다.
