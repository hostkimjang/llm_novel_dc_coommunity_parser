# Expert Orchestration Limitations

이 문서는 현재 전문가 오케스트레이션 구조의 한계와 운영 계약을 정리한다. 목적은 특정 post나 문자열을 외워 막는 것이 아니라, 자연어 이해, evidence boundary, 후단 재승격, VLM/OCR, 댓글 메타, `slang_db`가 서로 충돌할 때 어떤 기준으로 보수 판정할지 고정하는 것이다.

참고: Codex goal 자체를 여러 subagent로 병렬 진행하는 운영 지침은 `docs/devs/OPERATION_QUALITY_CHECKLIST.md`의 "Codex goal subagent 병렬 운영" 항목을 따른다. 이 문서는 repo 내부 LLM 전문가 오케스트레이션과 판정 한계를 다루며, Codex 앱의 `spawn_agent` 운영과 혼동하지 않는다.

## Active Contract

- 재해독 단계의 공개 label은 `표현 오타/축약 패턴(범용)`로만 쓴다.
- 재해독은 `표현 오타/축약 패턴`을 범용 재검토 신호로 올려 원문 의도를 다시 읽는 단계다. 특정 표면어를 특정 정상형이나 작품 seed로 고쳐 쓰는 계약이 아니다.
- 새 산출물에서는 old wording drift도 쓰지 않는다.
- 새 prompt, reason, review report, checklist에는 `X -> Y`식 복원 예시를 쓰지 않는다.
- 특정 post id, 특정 제목, 특정 오타 표면을 hardcode rule로 만들지 않는다.
- 기존 hardcoded alias/abbreviation map은 bootstrap 또는 legacy compatibility로만 다루고, final title 복구, `High` 승격, guard 예외에 닿는 경로는 `audit_hardcoded_alias_risk.py`와 packet 표본으로 별도 검토한다.
- 실제 의미 판단은 해당 packet의 `title`, `body`, `comment`, `comment_dialogue_context`, 공개 evidence, search/VLM/OCR field를 함께 읽은 결과로만 둔다.
- 표현 재해독 후보는 작품명, 별칭, 검색 seed, `slang_db` 저장 근거가 아니다. 직접 작품명, 공식 별칭, 작가, 회차, 플랫폼 작품 URL, 작품 고유 설정, OCR/VLM explicit work title 같은 독립 근거가 별도로 필요하다.

## Structural Limits

0. 비단조 rescue 구조
   - 앞단에서 `official_title=null`, `context_only`, `title_resolution_allowed=false`, no-work/social lament로 낮춰도 뒤쪽 search, alias, BatchContext, slang rescue가 final title을 다시 되살릴 수 있다.
   - `11718080`형 글은 "같이 소설 볼 친구가 있었으면"이라는 사회적 한탄/장르 잡담으로 읽어야 하며, 검색 후보가 있더라도 작품 확정으로 승격하지 않는다.
   - `11718082`형 글은 이미지 안에 작품명/작가/회차/플랫폼 단서가 있는 image-anchored work discussion으로 읽을 수 있지만, 이 경우 VLM/OCR catalog 또는 Browser visual/loading evidence가 구조화되어야 한다.
   - 이 한계는 특정 post id를 hardcode하라는 뜻이 아니다. no-work intent, direct post/visual anchor, evidence catalog, final reason이 같은 방향으로 보존되는지 보는 범용 구조 계약이다.

1. 1차 전문가 seed 과수집
   - 짧은 자연어 반응, 인명처럼 보이는 표면, 일반어, 말머리, 감상 표현이 `title_novel_terms`나 search suggestion으로 올라갈 수 있다.
   - 해결은 금칙어가 아니라 `semantic_seed_review`, `surface_paraphrase_notes`, `context_only_no_work_anchor`, `final_semantic_reread`의 조합이다.

2. 후단 비단조성
   - 앞단에서 `official_title=null`, `context_only`, `title_resolution_allowed=false`가 나와도 Decoder/search/BatchContext/Slang DB rescue가 뒤에서 다시 title을 되살릴 수 있다.
   - final freeze 이후 URL, alias, title을 되살리는 경로는 title-compatible direct evidence를 다시 확인해야 한다.

3. LLM 단독 재독해 한계
   - LLM이 한 번 더 읽었다는 사실만으로 충분하지 않다.
   - 재독해 결과는 public scope field, risk flag, evidence catalog, final reason까지 같은 방향으로 보존되어야 한다.

4. 후보 페이지와 source alignment 분리
   - memory-query/대사/장면 회수 글에서 공식 후보 페이지 hit는 source alignment evidence가 아니다.
   - 원문 quote/source anchor를 직접 지지하는 snippet, OCR/VLM direct text, 원문 source anchor가 없으면 `quote_alignment_missing_for_memory_query`로 `HOLD/human_review`에 둔다.

5. VLM/OCR evidence boundary
   - VLM/OCR이 실행됐다는 사실과 이미지가 작품 식별 근거라는 사실은 다르다.
   - direct title/author/platform/episode/quote가 없고 visual-only이면 `Strong` title evidence로 승격하지 않는다.
   - 이미지 로딩 지연, lazy-load 실패, 브라우저에는 보이지만 packet에 없는 이미지는 Codex in-app Browser로 직접 확인하고 `browser_visual_required`/`vlm_ocr_input_missing`으로 분리한다.

6. 댓글 author/IP 한계
   - 익명/공통 author 표면이 같아도 IP나 comment metadata가 없으면 원글 작성자 댓글로 확정하지 않는다.
   - `author_match_unverified`는 dialogue understanding 보조 정보이며 작품 identity evidence가 아니다.

7. `slang_db`/BatchMem 오염
   - exact title surface, 작가명 surface, 일반어, 문장형 표현, 공식 제목 prefix는 confirmed alias처럼 저장하지 않는다.
   - extraction, pending, block, persistence, dashboard display를 분리해 본다.

8. hardcoded alias/abbreviation 경로
   - `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY` 같은 positive map이 final title rescue, `High` confidence, correction lock, prompt pressure로 쓰이면 semantic approval blocker다.
   - blocklist/quarantine/prompt-hint registry는 positive alias blocker와 분리한다.
   - 감사 결과가 `REVIEW`여도 대형 semantic approval은 아니며, 실제 packet 원문/evidence/reason 검토가 별도로 필요하다.

9. Partial run gate
   - runtime smoke 또는 targeted canary 성공은 대량 semantic approval이 아니다.
   - 원본 run이 partial이면 known-bad 재현/회복 근거로만 쓰고, 10만 건 semantic gate는 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## Review Buckets To Keep Separate

- `surface_expression_reread_candidate`
- `final_semantic_reread_missing_for_semantic_seed`
- `context_only_no_work_anchor`
- `reason_overstates_context_only`
- `quote_alignment_missing_for_memory_query`
- `weak_evidence_but_strong_resolution`
- `reason_decision_contradiction`
- `generic_parenthetical_bridge`
- `image_evidence_catalog_missing`
- `vlm_ocr_public_state_weak`
- `ocr_conflict_context_overstated`
- `comment_author_match_unverified_dialogue`
- `batch_memory_exact_alias_rescued_no_anchor`
- `slang_db_noise_or_alias_pollution`

## Historical Note Policy

- 과거 history/result 산출물에는 특정 packet을 사람이 어떻게 읽었는지에 대한 구체 표현이 남아 있을 수 있다.
- 그런 표현은 historical observation으로만 본다. 새 prompt/report/reason/checklist로 옮길 때는 `표현 오타/축약 패턴(범용)`로 정규화한다.
- raw input surface를 evidence로 보존해야 할 때는 `source_surface`로만 남기고, 정상형 복원 문자열이나 `X -> Y` paraphrase를 만들지 않는다.

## Gate

- targeted known-bad canary: 대표 회귀 확인에는 유용하지만 대량 승인 근거가 아니다.
- review tooling guard: focused unittest와 py_compile로 도구 회귀를 막는다.
- semantic quality gate: random baseline과 high-risk oversample이 분리 보고되고, P0/P1 issue queue가 닫히기 전까지 `REVIEW-LOCKED`를 유지한다.
