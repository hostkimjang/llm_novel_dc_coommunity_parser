# LLM Judgment Review

## 2026-06-01 v485 정정: registry-only provenance는 reason/packet에서 끝까지 보여야 한다

- `registry_anchor_only`, `promotion_confidence=Medium`, `confidence_demoted_without_hard_evidence`는 내부 로그가 아니라 최종 리뷰 근거다.
- `NovelIdentity.alias_resolution_sources`, qualitative review packet, LLM judgment review packet 모두 alias provenance를 보존해야 한다.
- registry + work anchor만 있는 resolved title은 `Strong`으로 쓰지 않는다. official/detail/direct hard support가 없으면 `HOLD/re_judge` 또는 `Medium` 범위다.
- `_apply_known_abbreviation_title_guard()`가 `KNOWN_*` source를 쓰는 경우에도 suspected/decoder/search 반복 같은 soft support만으로 final title을 바꾸면 안 된다.
- 비공식 search/wiki/community 반복에서 만든 title-lead alias inferred candidate는 score가 높아도 `High`가 아니라 `Medium`이다.
- 이 정정은 metadata/review-packet 품질 gate이며, hardcoded alias 전체 승인이나 10만 semantic approval이 아니다.

## 2026-06-01 v484 정정: registry + work anchor는 High 확정 근거가 아니다

- 등록 약칭 surface와 post-side work anchor가 함께 있어도 이는 후보 승격 검토 조건이다.
- Agentic `_try_promote_best_candidate()`에서 `High` final rescue를 열려면 official/detail URL, fetched official title, 원문 full title 직접 표면, VLM/OCR direct work title, verified character-work link 같은 독립 hard support가 추가로 필요하다.
- hard support 없는 registry promotion은 `Medium`, `HOLD`, 재검색/재판정 후보로 남긴다. 이를 `Strong` 또는 semantic approval evidence로 올리지 않는다.
- 이 규칙은 positive alias recall을 막는 것이 아니라, 작품 맥락은 있어 보이지만 evidence가 약한 경우 reason/confidence가 evidence보다 세게 말하지 못하게 하는 natural-language quality gate다.
- v484는 Agentic targeted confidence gate다. hardcoded alias 전체 승인과 10만 semantic approval은 계속 별도 `REVIEW-LOCKED`다.

## 2026-06-01 v483 정정: alias-only anchor는 actual guard 면제 근거가 아니다

- Arbiter actual decision-path에서도 `title_abbrev_mention` / `body_abbrev_mention`만으로 `multi_work`, `meme/noise`, `low-confidence` guard를 면제하지 않는다.
- 공식 검색 결과가 작품 존재를 지지하더라도, 원문이 비교/나열/잡담/no-work이고 post-side work anchor가 없으면 단일 `official_title` 확정 근거가 아니다.
- `multi_work` 비교/추천/나열 문맥에서는 등록 약칭 하나가 보여도 단일 작품 강제승격을 보류한다. 회차/스포/캐릭터/줄거리처럼 packet 안의 작품 토론 앵커가 있을 때만 예외를 검토한다.
- `meme` 또는 `low-confidence` guard에서 alias-only anchor가 살아남으려면 `_has_curated_alias_guard_exception()`에 해당하는 직접 title 표면, verified character-work link, 등록 약칭 surface + work anchor, non-character anchor support가 필요하다.
- 이 규칙은 특정 alias나 post id를 막는 규칙이 아니라, 후단 검색/registry rescue가 자연어 no-work 판단을 뒤집지 못하게 하는 evidence boundary다.

## 2026-06-01 v482 정정: official evidence는 official detail 증거만이다

- Arbiter `_has_strong_title_support()`와 `_has_official_title_evidence()`는 같은 의미가 아니다.
- strong support는 공식 상세, fetch 정보, trust score를 포함한 넓은 source-quality 판단이다.
- official evidence는 공식 플랫폼 상세 URL과 fetched official detail title match처럼 공개 evidence가 직접 작품을 지지할 때만 `true`다.
- `known_abbreviation`, `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, snippet abbreviation hint는 official evidence가 아니다.
- deleted/unavailable page, community post, listing/search page는 title text가 겹쳐도 official evidence가 아니다.
- 짧은 제목은 다른 제목 내부 substring만으로 official evidence가 될 수 없다. raw token boundary 또는 동등한 직접 표면이 필요하다.
- helper 테스트 통과는 actual final decision-path 승인이나 10만 semantic approval이 아니다.

## 2026-06-01 v481 정정: Arbiter guard exception도 registry hit만으로 열지 않는다

- Arbiter `multi_work`, `meme/noise`, `low-confidence`, title veto exception은 등록 약칭 surface만으로 열면 안 된다.
- guard exception에는 post-side work anchor, 정식 title 직접 표면, verified character-work link, non-character decoder/verifier anchor support 중 하나가 필요하다.
- comment-only alias, bare alias, semantic no-work/context-only 글은 registry provenance가 있어도 Arbiter guard 면제 근거가 아니다.
- `등록 약칭 + 독립 작품 앵커 확인` 수준의 공개 근거가 없으면 해당 packet은 `HOLD/REJECT/re_judge` 후보로 둔다.
- v481은 Arbiter targeted guard다. actual decision-path 테스트와 10만 semantic approval은 별도다.

## 2026-06-01 v480 정정: 등록 약칭 surface는 강한 alias support가 아니다

- 등록 약칭이 원문 title/body에 보이는 것과, 그 약칭을 작품 판정의 강한 support로 쓰는 것은 다르다.
- Agentic `_has_alias_title_support()`는 post-side work anchor 또는 compound title-character bridge가 없으면 known abbreviation alias만으로 `True`가 될 수 없다.
- `_collect_title_support_kinds()`는 약칭 surface만으로 `post_main_mention`을 추가하지 않는다. 실제 full title이 원문에 있을 때만 `post_main_mention`이다.
- 약칭 positive는 `known_abbreviation_alias + curated_alias_work_anchor`처럼 surface와 작품 맥락 앵커를 분리해 기록한다.
- 이 규칙은 `담텔기` 같은 positive canary를 막으려는 것이 아니라, `11718080`류 bare alias/social lament/context-only 글에서 후단 support가 부풀어 오르는 것을 막는 규칙이다.

## 2026-06-01 v479 정정: Agentic promotion/stability/lock도 post-side work anchor가 필요하다

- `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS` hit는 Agentic direct `High` promotion, abbreviation stability, title lock의 단독 근거가 아니다.
- 등록 약칭 surface가 원문 title/body에 보여도 post-side work anchor가 없으면 작품 확정으로 승격하지 않는다.
- post-side work anchor는 원문 직접 작품 토론, 회차/스포/작가의 말/캐릭터-작품 bridge, 직접 이미지/OCR 작품 표면처럼 packet 안에서 작품을 가리키는 신호여야 한다.
- comment-only alias는 대화 흐름 검토 대상일 수 있지만, 그 자체만으로 title lock을 열지 않는다.
- `담텔기`처럼 work-context와 official/platform evidence가 함께 있는 positive는 유지하되, `11718080`류 social lament/context-only 글은 검색/별칭 후보로 되살리지 않는다.
- v479는 Agentic runtime guard를 강화한 targeted fix다. Arbiter guard exception과 전체 10만 semantic approval은 계속 별도 `REVIEW-LOCKED` gate로 둔다.

## 2026-06-01 v476 정정: 등록 약칭은 Jury/Debate에서도 확정 근거가 아니다

- `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS` hit는 LLM/Jury/Debate에 `확정적`이라고 전달하지 않는다.
- 등록 약칭은 recall hint이며, no-work 또는 독립 work anchor 부재 문맥에서는 positive signal로 쓰지 않는다.
- 독립 work anchor가 있을 때도 `abbreviation_match`는 약한 보조 신호다. 최종 승격에는 원문 직접 title/alias, 공식 플랫폼 URL, strict snippet/content, VLM/OCR 직접 작품 제목, verified character-work link 같은 별도 evidence가 필요하다.
- prompt에는 `is_relevant=true로 판정하세요`처럼 결론을 강제하는 문구를 넣지 않는다. 대신 `독립 앵커가 약하거나 잡담/no-work 문맥이면 title=null 또는 HOLD를 우선 고려`라고 쓴다.
- v476은 prompt pressure와 audit noise를 줄였지만, `Decoder._rescue_null_title`, `AgenticPipeline._try_promote_best_candidate`, Arbiter guard exception 경로가 남아 hardcoded alias risk는 계속 `REVIEW`다.

## 2026-06-01 v474 정정: SLANG_DICTIONARY는 recall hint이며 독립 확정 근거가 아니다

- `SLANG_DICTIONARY` hit는 작품 후보 recall을 돕는 힌트일 뿐, `official_title`, `resolved_title`, `best_match.title`, `confidence=high`를 단독으로 만들 수 없다.
- Decoder가 dictionary match를 발견해도 `slang_dictionary_hint` candidate로만 남긴다. post 원문, 댓글, 공식 URL, strict search snippet, VLM/OCR 직접 제목처럼 독립 evidence가 있어야 title 승격이 가능하다.
- LLM이 프롬프트를 어기고 dictionary mapped title을 high로 출력해도, 독립 URL/플랫폼/비사전 evidence가 없으면 후처리에서 `best_match.title=null`, `confidence=none`으로 되돌린다.
- `decoded_term`이나 dictionary candidate가 남아 있는 것과 semantic approval은 다르다. dictionary-only packet은 `HOLD` 또는 재검색/재판정 후보로 둔다.
- v474 기준 `SLANG_DICTIONARY`는 hardcoded alias positive blocker에서 빠졌지만, `KNOWN_ABBREVIATIONS`와 `KNOWN_TITLE_ABBREVIATIONS`는 여전히 final title rescue/High/guard exception 경로에 닿는 registry blocker다.
- 이 정정은 hardcoded alias 전체 승인이나 10만 semantic approval이 아니다. completed source와 expanded random/high-risk review 전까지 전체 gate는 계속 `NO-GO/REVIEW-LOCKED`다.

## 2026-06-01 v470 정정: tooling marker와 runtime positive registry를 분리한다

- `tools/build_semantic_coverage_audit.py`의 `TITLE_ALIAS_SUPPORT_MARKERS` 같은 coverage scanner marker tuple은 hardcoded alias runtime registry가 아니다.
- audit 도구는 이런 marker tuple을 발견할 수는 있지만, `positive_resolution/REVIEW` blocker가 아니라 `tooling_marker/INFO`로 분리해야 한다.
- `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY`는 여전히 final title rescue, High 승격, guard 예외에 닿을 수 있는 runtime positive registry라 별도 review blocker다.
- hardcoded alias packet review는 raw artifact count와 unique post-context alias coverage를 분리한다. 같은 post/alias가 여러 intermediate JSON/JSONL에 반복된 raw 40건이어도, post-side direct alias가 1종이면 closure 기준은 unique post-context 1건이다.
- 후속 labels가 unique post-context coverage를 모두 `ACCEPT`로 닫으면 packet review effective gate는 `GO`로 낮출 수 있다. 이때도 registry risk 전체와 10만 semantic approval은 닫지 않는다.
- 자연어 구조 리스크는 별개다. `11718080`형 social lament/no-work는 검색/별칭 후보가 있어도 작품 확정이 아니며, `11718082`형 image anchored post는 VLM/OCR catalog와 Browser visual/loading evidence가 결론을 직접 지지해야 한다.

## 2026-06-01 v467 정정: raw packet REVIEW와 effective packet GO를 분리한다

- v407 같은 raw packet review artifact는 `matched packet이 있으니 라벨링하라`는 의미로 `REVIEW`일 수 있다.
- 후속 label review가 동일 matched packet 수 이상을 모두 `ACCEPT`로 닫고, 최신 canary가 `source_registry`, `alias_resolution_source`, `matched_surface_kind`, official/platform evidence를 공개하면 packet review의 effective gate는 `GO`로 낮출 수 있다.
- 이때 raw gate를 수정했다고 말하지 않는다. `raw_gate=REVIEW`, `effective_gate=GO`, `closed_by_packet_labels=true`처럼 reconciliation 상태를 분리해서 남긴다.
- packet effective `GO`는 positive hardcoded registry 전체 승인이 아니다. `KNOWN_ABBREVIATIONS`, `KNOWN_TITLE_ABBREVIATIONS`, `SLANG_DICTIONARY` 전체 경로는 별도 registry review가 필요하다.
- v467 기준 `담텔기 -> 괴담 호텔 탈출기` packet 요구사항은 닫혔지만, hardcoded alias registry risk와 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-06-01 v466 정정: historical packet label closure와 hardcoded alias 전체 승인은 다르다

- v409처럼 같은 post/alias의 historical packet labels가 HOLD/REJECT를 포함하더라도, 최신 canary가 provenance와 official/platform evidence를 공개하면 label follow-up은 닫을 수 있다.
- closure 기준은 final title이 맞는지만이 아니다. `source_registry`, `alias_resolution_source`, `matched_surface_kind`, post-side alias surface, official/platform URL, reason score가 함께 있어야 한다.
- v450 `11718120`은 `담텔기 -> 괴담 호텔 탈출기`를 `KNOWN_TITLE_ABBREVIATIONS` provenance와 `post_title` surface로 공개했고, `official_urls=7`, `post_spans=4`를 남겼으므로 v409의 weak/provenance missing label은 최신 기준으로 닫혔다.
- 다만 label follow-up `GO`는 hardcoded alias registry 전체 승인과 다르다. positive registry가 final title rescue/High 승격/guard 예외에 닿으면 별도 registry review가 계속 필요하다.
- v466 action queue처럼 `hardcoded_alias_packet_label_gate=GO`와 `hardcoded_alias_gate=REVIEW`, `hardcoded_alias_packet_gate=REVIEW`를 분리해서 보고한다.
- targeted canary가 historical label을 닫아도 10만 semantic approval은 completed source와 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-06-01 v460 정정: 이미지 OCR 변형은 final anchor도 image로 남긴다

- 공개 reason이 `title_in_post=false`, `image_ocr_variant=true`라면 final `anchor_type=title_exact`는 불일치다. 직접 작품 표면이 이미지 OCR/표지에서 온 경우 final anchor도 `image`로 둔다.
- 이때 `image_ocr_variant_not_title_in_post` flag를 남겨, 원문 직접 title 언급과 이미지 OCR 보정을 같은 evidence로 합치지 않는다.
- `slang_insight.cultural_context`가 이미지 OCR 표면을 `특정 웹소설의 일부 인용`, `작품의 설정`, `캐릭터 관계`, `세계관/배경`, `비표준적인 커뮤니티 약칭 또는 OCR 오인`처럼 말하면 output hygiene `HOLD`다.
- 안전한 public wording은 packet-local OCR/표기 변형 단서, 이미지 표지/장면의 작품 식별 보조 단서 정도다. 지속 alias, 공식 제목, 작품 설정 근거로 단정하지 않는다.
- v460 `11718082`는 `anchor_type=image`, `image_ocr_variant_not_title_in_post`, `slang_insight=null`로 이 경계를 만족했다. `11718080`은 계속 `official_title=null`, `work_resolution=none`이다.
- 이 판정은 targeted canary용이다. Browser visual과 10만 semantic approval은 별도 gate다.

## 2026-06-01 v458 정정: 이미지 OCR 변형은 score board에서도 원문 title 가산점이 아니다

- 이미지 OCR/표지 후보가 최종 제목과 유사하지만 exact가 아니고, non-image title/body/comment에는 공식 제목이 직접 보이지 않으면 reason score board도 `title_in_post:+2`를 주지 않는다.
- 공개 reason의 `[근거 요약]`과 `[근거 스코어]`는 서로 충돌하면 안 된다. `title_in_post=false`와 `title_in_post:+2`가 동시에 나오면 output hygiene `HOLD`다.
- `slang_insight.cultural_context`는 이미지 OCR 표면을 `게시글/제목에 사용된`, `일반적인 오타 또는 축약`, `공식적인 제목으로 확인`, `고유 명칭`처럼 말하지 않는다.
- 허용되는 표현은 packet-local OCR/표기 변형 단서, 또는 해당 packet 안에서만 작품 식별을 보조하는 표면이라는 경계다.
- `store_in_slang_db=false`가 함께 남더라도 public context가 지속 alias처럼 읽히면 충분하지 않다. reason/context 문구 자체도 낮춰야 한다.
- v458 targeted canary에서 이 축은 `GO`지만, Browser visual과 10만 semantic approval gate는 계속 별도다.

## 2026-06-01 v454 정정: 이미지 OCR 변형은 원문 title 언급과 분리한다

- VLM/OCR이 이미지에서 읽은 제목 후보가 최종 공식 제목과 유사하지만 exact가 아니면 `title_in_post=true`로 쓰지 않는다.
- 이 경우 공개 reason은 `image_ocr_variant=true`와 `official_search_resolution=true`를 분리해, OCR 변형 표면과 공식 검색/URL 보정을 구분한다.
- slang/cultural context에서 이미지 OCR 표면을 `게시글 제목에 사용된 축약어/오타`라고 쓰지 않는다. `이미지 OCR/표지에서 감지된 일회성 표면`처럼 근거 위치와 지속 alias 아님을 드러낸다.
- 이 규칙은 특정 오타를 정상형으로 고정하는 규칙이 아니다. OCR/표지 표면은 packet-local work identifier clue일 수 있지만, persistent alias나 `slang_db` 저장 근거가 되려면 별도 안정 alias 근거가 필요하다.
- v454 live result는 reason의 `title_in_post=false`, `image_ocr_variant=true`, `official_search_resolution=true` 분리를 확인했지만, 그 산출물은 후속 sanitizer 패치 전이라 `slang_insight.cultural_context`에 old wording이 남아 있다. 최신 코드는 이 문구를 packet-local OCR/표기 변형 단서로 낮추며, v460 live canary에서 runtime output까지 재확인했다.
- VLM/OCR run-ready는 per-image success가 아니다. Browser visual/loading evidence 또는 image evidence catalog가 없으면 이미지 row approval은 계속 `HOLD/REPROCESS/INFO_MISSING` 후보로 둔다.

## 2026-06-01 v453 정정: no-work 판정은 후단 URL/alias/BatchContext rescue보다 우선한다

- `semantic_seed_review.is_specific_work_discussion=false`, `title_resolution_allowed=false`, `context_only/nonwork/adjacent` 같은 신호가 있으면 후단 corrected-title URL recovery나 alias support helper가 검색 결과만으로 작품 확정을 되살리면 안 된다.
- 예외는 packet 안에 독립 작품 앵커가 있을 때만 허용한다. 기준은 원문 직접 작품명, VLM/OCR direct work title, image primary promotion, verified character-work link 같은 post/visual/local evidence다.
- decoder alias, gatekeeper possible title, verifier slang term, search snippet은 no-work intent를 단독으로 뒤집는 근거가 아니다. 이들은 direct anchor가 있을 때 보조 근거로만 쓴다.
- BatchContext와 slang seed는 final identity의 `title_resolution_state`, `title_resolution_allowed`, `consistency_flags`를 반드시 함께 받아야 한다. 이 필드 없이 alias/title만 학습하면 no-work/context-only가 다음 포스트에서 resolved seed로 오염될 수 있다.
- `_search_with_meta()` 같은 raw search helper는 context-free escape hatch다. 새 직접 호출부는 반드시 intent/no-work guard를 호출부 앞에서 증명해야 하며, static regression allowlist 갱신 전 focused test가 필요하다.
- v453 `11718080`은 특정 작품 매칭이 아니라 장르·트로프/일상 잡담이므로 `official_title=null`, `work_resolution=none`이 맞다.
- v453 `11718082`는 이미지 OCR에 작품명/작가/회차가 있는 직접 작품 앵커 케이스이므로 VLM/OCR evidence와 공식 URL이 결합될 때 resolved가 맞다.
- 이 규칙은 특정 post id, 작품명, 오타 표면을 외워 막는 hardcode가 아니라 no-work intent와 direct evidence boundary를 후단 구조 전체에 전파하는 규칙이다.
- targeted canary가 통과해도 전체 10만 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-06-01 v450 정정: no-work, alias surface, adjacent drift를 같은 evidence boundary로 묶는다

- `semantic_seed_review.is_specific_work_discussion=false` 또는 동등한 no-work 신호가 있으면 회차/스포/작가의 말 같은 표현만으로 known title abbreviation promotion을 다시 열지 않는다.
- curated abbreviation은 원문에 보이는 alias surface여야 한다. 짧은 alias가 일반 단어 내부 substring으로 우연히 들어간 경우에는 promotion/stability 근거가 아니다.
- 작품군 토큰을 hardcode해서 drift를 무효화하지 않는다. 서로 일반 토큰을 일부 공유해도 decoder anchor conflict, 낮은 lexical overlap, 미언급 adjacent candidate가 있으면 `HOLD` 또는 drift 후보로 본다.
- v450 `11718120`은 positive seed, visible alias `담텔기`, 공식 플랫폼 URL, plot mention이 같은 title을 지지해 targeted canary 기준 `GO`다.
- 같은 run에서 검색 원천에 인접 작품명이 보이는 것과 final candidate에 보존되는 것은 다르다. 인접 검색 결과가 후보로 승격되지 않으면 candidate pollution은 닫힌 것으로 본다.
- 단, 이 판정은 targeted canary에 한정한다. 10만 건 semantic approval은 expanded random/high-risk review 전까지 `REVIEW-LOCKED`다.

## 2026-06-01 v448 정정: curated abbreviation 회복과 인접 파생 후보 오염을 분리한다

- 원문 title/body에 curated title abbreviation이 있고 회차/스포/작가의 말/positive work intent 같은 packet-local work anchor가 있으면 known title abbreviation 회복은 허용할 수 있다.
- 그러나 final title과 다른 canonical rescue 후보가 원문 main context에 직접 언급되지 않았고, alias support도 없고, verified character-work link도 없으면 그 후보는 confirmed work 후보로 남기지 않는다.
- v448 `11718120`은 `담텔기 -> 괴담 호텔 탈출기` 회복 자체는 확인됐지만, `title_candidates`에 미언급 인접 파생 후보 `괴담 학교 탈출기`가 남아 semantic label은 `HOLD`다.
- final title이 맞아도 후보 목록, reason, URL/evidence state가 인접 파생 후보를 같이 강화하면 `curated_alias_adjacent_candidate_pollution`, `multi_work_or_adjacent_risk`, `reason_evidence_state_mismatch`로 본다.
- v450 live canary와 focused regression에서 후속 adjacent candidate guard가 targeted 기준 통과했다.
- 이 규칙은 특정 작품명 hardcode가 아니라, curated alias primary와 충돌하는 unmentioned adjacent derivative candidate를 낮추는 범용 evidence-boundary 규칙이다.

## 2026-05-31 v408 정정: 검색 전 intent permit 없이는 resolved title로 되살리지 않는다

- intent-first 구조가 있어도 검색 suppression 기본 off, `key_terms` 자동 검색, Verifier 검색 우선 문구가 결합되면 잡담/한탄/트로프 표면이 작품 검색으로 되살아날 수 있다.
- 현재 구조의 문제는 no-work intent 장치 부재가 아니라 위치와 우선순위다. Gatekeeper가 `possible_titles/key_terms/search_requests`를 먼저 만들고 Discourse/semantic seed review/final reread가 뒤에서 낮추는 흐름에서는, 한 번 검색 seed가 열리면 alias rescue/key-term supplementary search가 다시 resolution을 올릴 수 있다.
- `11718080`류 친구/한탄/일상 글은 소설이라는 단어가 있어도 직접 작품 토론이 아니다. 먼저 글 의도가 작품 찾기/작품 감상/직접 작품 앵커인지 확인한다.
- `official_title_verify` 검색 전에 `intent_permit_for_title_search` 또는 동등 구조 필드가 있어야 한다. 허가 조건은 직접 작품명/공식 별칭/작가+작품/이미지 OCR 직접 제목/회차/플랫폼 작품 URL 같은 direct anchor다.
- `intent_permit_for_title_search=false`이면 검색 budget cap이 아니라 hard permit으로 `official_title_verify`, `platform_title_search`, `alias_raw_probe`, `key_term_supplement`, `auto_search_seed` 및 late/adaptive/title-like 목적 검색을 막아야 한다.
- 현재 구현은 실행 직전 검색 gate에서 permit false 상태를 닫힌 기본값으로 처리한다. `term_definition` 등 안전 목적만 통과하고 unknown purpose는 기본 차단한다. `adaptive_wiki`, `author_works_search` 직접 검색도 중앙 gate를 타게 했다. 후단 `BatchContext`/known alias/slang_db seed 및 deliberation/canonical rescue 경로도 구조화된 `semantic_seed_review` no-work, `title_resolution_allowed=false`, `context_only` 신호를 읽어 독립 작품 evidence처럼 되살리지 않도록 회귀를 추가했다.
- audit에서는 `intent_denied_title_present`를 별도 blocker로 본다. `resolved` 상태가 아니더라도 `title_resolution_allowed=false`, `context_only/no_work`, `intent_permit_for_title_search=false`와 `official_title`이 함께 남으면 no-work 판단과 title 출력이 충돌한 것이다.
- `search_only` evidence는 weak다. `community_banter`, `trope_discussion`, `author_talk`, `recommendation` intent에서는 직접 작품 앵커 없이 `resolved_title`을 확정하지 않는다.
- comment author/IP/context는 대화 흐름 힌트이며 독립 작품 evidence가 아니다. 익명/동일 닉네임이더라도 IP나 구조 근거가 없으면 `author_match_unverified`로 둔다.
- VLM/OCR image row는 manifest, `content_blocks/image_urls`, `image_evidence_catalog`, final reason/flags, Browser visual/loading evidence를 함께 확인해야 한다. text-only run은 image semantic approval 근거가 아니다.
- hardcoded alias registry가 관여한 packet은 registry provenance가 남아야 한다. `source_registry`, `alias_resolution_source`, `hardcoded_registry_name` 같은 필드 없이 `slang_db/BatchContext/search`와 섞이면 `HOLD/human_review`다.

## 2026-05-31 v392 정정: 재해독 label 뒤 콜론 payload도 금지한다

- 재해독 public label은 `표현 오타/축약 패턴(범용)` 하나로만 쓴다.
- `표현 오타/축약 패턴(범용): X; Y`처럼 label 뒤에 표면값, 복원 후보, 설명 payload를 붙이지 않는다.
- public reason은 `표현 오타/축약 패턴(범용)은 packet-local 원문 재검토 신호`처럼 문장형 경계만 남긴다.
- scanner는 `표현 오타/축약 패턴(범용):` 자체를 output-hygiene drift로 잡는다.
- 과거 문서/로그의 구체 정상형 복원 표현은 historical observation으로만 보고, 새 prompt/reason/report/checklist에는 옮기지 않는다.

## 2026-05-31 v389 정정: 재해독 표현은 active label 하나만 쓴다

- 재해독 public label은 `표현 오타/축약 패턴(범용)` 하나로만 쓴다.
- 이전 확장 label이나 더 긴 설명형 label은 새 prompt/reason/report/checklist의 active wording으로 쓰지 않는다.
- 이 label은 packet-local 원문 재검토 신호이지 특정 정상형 복원, 계열 일반규칙, 검색 seed, 작품명/별칭 근거가 아니다.
- hygiene scanner는 legacy drift를 잡기 위해 금지 문구를 내부 패턴으로 가질 수 있지만, 사용자-facing reason/report에는 노출하지 않는다.
- 과거 known-bad 표면형은 회귀 입력이나 historical observation으로만 보며, 새 지침에는 `표현 오타/축약 패턴(범용)`로 정규화한다.

## 2026-05-31 v385 정정: 재해독은 `표현 오타/축약 패턴(범용)`로만 말한다

- 재해독 공개 문구와 LLM prompt/report의 active wording은 `표현 오타/축약 패턴(범용)`로 고정한다.
- 사람이 특정 정상형을 떠올릴 수 있어도 새 reason/report/prompt에는 그 복원값을 쓰지 않는다.
- 특정 표면 범주를 자동 차단/허용 규칙처럼 부르지 않고, 해당 packet의 title/body/comment/comment_dialogue와 direct evidence를 다시 읽는 신호로만 쓴다.
- `표현 오타/축약 패턴(범용)`보다 긴 확장 label은 최신 active wording에서는 쓰지 않는다.
- 과거 history의 구체 표면형/복원 표현은 historical observation이며, 현재 active rule이나 회귀 기대 문구가 아니다.
- public-output hygiene scan에서 old wording drift, `X -> Y`, 원문에 없는 정규화 값이 잡히면 최신 승인 근거로 쓰지 않는다.

## 2026-05-31 v379 정정: platform meta/no-anchor 비관련 글은 context-only로 둔다

- `노피아` 같은 플랫폼 맥락이 있어도, 원문 의도가 UI/아이콘/콘 잡담이고 단일 작품 title/author/회차/줄거리 앵커가 없으면 `unresolved_matchable`로 남기지 않는다.
- VLM/OCR 이미지가 platform catalog/background listing이면 작품명 evidence가 아니라 시각 보조 evidence다.
- character visual only image도 별도 title/alias/OCR 직접 근거가 없으면 resolved title evidence가 아니다.
- 공개 reason의 `단정하기 어려움할` 같은 suffix drift는 semantic 결론이 맞아도 output-hygiene `HOLD` 사유다.
- 이 규칙은 특정 post id/string hardcode가 아니라, 비관련/no-title/no-anchor 결과의 scope field와 public reason을 evidence boundary에 맞추는 가드다.

## 2026-05-31 v376 정정: 재해독 공개 문구는 exact generic pattern만 쓴다

- 재해독 공개 문구는 `표현 오타/축약 패턴(범용)`로만 쓴다.
- old wording drift는 새 prompt/report/reason/checklist에서 쓰지 않는다.
- 이 label은 packet-local 원문 재검토 신호이지 특정 raw surface, 정상형 복원, 작품 seed, 계열별 자동 차단/허용 규칙이 아니다.
- reason hygiene scanner의 `reread_wording_drift` hit는 approval blocker로 본다.

## 2026-05-31 v372 정정: 검색/랭킹 경로도 `표현 오타/축약 패턴(범용)` seed를 열거하지 않는다

- no-search 조기 종료 경로뿐 아니라 검색/랭킹 경로에서도 `표현 오타/축약 패턴(범용)`는 raw seed 목록으로 되살리지 않는다.
- 장르 조합, 클리셰, 커뮤니티 조어, 작품 앵커 부족 계열의 topic은 특정 작품명/별칭 evidence가 아니므로 public reason에 `작품 seed 제외:`로 나열하지 않는다.
- `해석 주제`가 장르/클리셰 감상처럼 남는 것은 가능하지만, 그것이 특정 표면어를 작품 seed로 검토했다는 뜻이 되면 안 된다.
- 이 규칙은 특정 장르어 hardcode가 아니라, `표현 오타/축약 패턴(범용)` 신호가 작품 매칭 evidence처럼 보이지 않게 하는 output hygiene이다.
- v372 `11718085` canary에서 VLM/OCR on, context-only/title-null 유지, forbidden scan 0건을 확인했지만 10만 semantic approval은 계속 `REVIEW-LOCKED`다.

## 2026-05-31 v370 정정: 축약/장르 surface도 raw seed 목록으로 되살리지 않는다

- 재해독 공개 문구는 계속 `표현 오타/축약 패턴(범용)`로 쓴다.
- 장르 약칭, 비표준 조합, 작품 앵커 확정 어려움처럼 semantic seed review가 context-only로 낮춘 표면은 public reason에서 `seed 후보(...)`나 `작품 seed 제외:`로 다시 열거하지 않는다.
- 원문 title/body/comment에는 raw surface가 남을 수 있지만, 판정/해석 문장에서는 `작품명/별칭 근거가 아니다`라는 evidence boundary만 공개한다.
- 이 규칙은 특정 장르어 또는 특정 post id를 외워 막는 hardcode가 아니다. 공개 reason이 `표현 오타/축약 패턴(범용)` 신호를 다시 작품 seed처럼 보이게 만드는 것을 막는 output hygiene guard다.
- targeted guard가 통과해도 10만 semantic approval은 expanded review 전까지 `REVIEW-LOCKED`다.

## 2026-05-31 v359 정정: 재해독 문구는 `표현 오타/축약 패턴(범용)`로 고정한다

- 재해독 공개 문구는 `표현 오타/축약 패턴(범용)`로 쓴다.
- 여기서 `패턴`은 해당 packet을 다시 읽어야 한다는 신호이지, 특정 정상형 복원이나 특정 계열 자동 차단/허용 규칙이 아니다.
- 사람이 떠올린 구체 설명 범주도 prompt/report/reason의 판정 조건으로 반복하지 않는다. 필요한 경우에는 `작품 고유 앵커가 부족한 원문 반응/문장 일부`처럼 evidence boundary로만 쓴다.
- 공개 reason/report에는 표면어 후보 목록, `X -> Y`, 원문에 없는 정규화 값, 계열별 deterministic rule을 쓰지 않는다.
- 실제 의미 판단은 title/body/comment/comment_dialogue와 direct evidence를 함께 읽은 packet-local 자연어 재검토 결과로만 둔다.

## 2026-05-31 v356/v357 보강: 원문에 없는 정규화 해석 괄호도 공개하지 않는다

- `X -> Y` 직접 치환이 아니어도, 공개 reason에 원문에 없는 정규화 값이나 compact interpretation payload가 괄호로 들어가면 특정 정상형 복원처럼 읽힐 수 있다.
- `표현 오타/축약 패턴(범용)` 신호가 있는 경우 공개 reason은 packet-local 원문 재검토 신호라는 경계만 남기고, 숫자/slash/arrow가 들어간 해석성 괄호를 쓰지 않는다.
- 이 가드는 특정 숫자, 나이, 외모 규칙이 아니다. 원문 title/body/comment에 없는 해석 값을 공개 reason의 결론처럼 남기지 않는 public-output hygiene이다.
- v357 `11718091` 단건 canary에서 `official_title=null`, `title_resolution_state=context_only`를 유지하면서 해당 괄호 회귀가 제거됨을 확인했다.

## 2026-05-31 v355 정정: 공개 reason은 표면어 후보를 다시 나열하지 않는다

- 재해독은 `표현 오타/축약 패턴(범용)`라는 경계만 공개한다.
- 공개 reason/report에서 `표현 오타/축약 패턴(범용): X; Y`처럼 표면어 후보를 따로 나열하지 않는다.
- `표현 오타/축약 패턴(범용)` 신호는 원문 title/body/comment/comment_dialogue 안에서 확인되는 packet-local 맥락일 뿐, 공개 `작품 seed 제외` 목록에 다시 올리지 않는다.
- legacy packet에 남아 있는 `paraphrase`/`X -> Y` 값은 historical observation으로만 보고, sanitizer나 prompt 근거로 재사용하지 않는다.
- 리뷰어는 원문 맥락과 direct evidence를 읽어 ACCEPT/HOLD/REPROCESS/REJECT/INFO_MISSING을 붙이되, 표면어 자체를 정답 치환이나 계열 규칙으로 삼지 않는다.

## 2026-05-31 v352 재정정: 재해독은 범용 패턴이지 일반규칙이 아니다

- 재해독에서 말하는 것은 `표현 오타/축약 패턴(범용)`이라는 뜻이다.
- 특정 표면어의 정상형 복원도 금지하지만, 비슷한 계열을 자동 차단/허용하는 일반규칙으로 만드는 것도 금지한다.
- 이런 범주는 예시적 위험 신호일 뿐이며, 실제 판단은 항상 해당 packet의 title/body/comment/comment_dialogue와 direct evidence를 함께 읽는 packet-local 자연어 재검토로만 둔다.
- 새 prompt/report/reason에는 `X -> Y`식 복원 결과, 특정 계열 규칙, post id/string hardcode를 쓰지 않는다.
- 공개 label은 계속 `표현 오타/축약 패턴(범용)`로만 남긴다.

## 2026-05-31 v348 정정: 표현 오타/축약 패턴 자체가 범용 후보다

- 재해독은 `표현 오타/축약 패턴(범용)`을 세우는 단계다.
- 공개 label은 계속 `표현 오타/축약 패턴(범용)`를 사용한다.
- 이 label은 "특정 표면어를 특정 정상형으로 복원했다"는 뜻이 아니다.
- 특정 정상형이 자연스러워 보여도 새 prompt/report/reason에는 `X -> Y`식 복원 결과처럼 쓰지 않는다.
- 실제 의미 판단은 해당 packet의 title/body/comment/comment_dialogue와 direct evidence를 함께 읽은 packet-local 자연어 재검토 결과로만 둔다.

## 2026-05-31 v345 추가 규칙: memory-query는 후보 페이지와 quote alignment를 분리한다

- `무슨 소설`, `기억이 안남`, `본 대사`, 장면/구절 회수류 post는 공식 후보 페이지 hit만으로 Strong evidence가 되지 않는다.
- 후보 작품 페이지가 있어도 원문 대사/장면 fragment를 직접 지지하는 search snippet, OCR/VLM direct text, 또는 source anchor가 없으면 `quote_alignment_missing_for_memory_query`로 `HOLD/human_review`에 둔다.
- `title_candidates`, `entity_mentions`, `analysis.detected_titles`처럼 LLM이 원문 표면을 재기록한 필드는 quote/source alignment support로 세지 않는다.
- 이 규칙은 특정 quote나 post id를 외워 막는 것이 아니라, memory-query resolved 판정의 evidence boundary를 분리하는 정성 리뷰 bucket이다.

## 2026-05-31 v344 정정: 재해독은 범용 패턴이지 특정 의미 복원이 아니다

- 재해독 단계에서는 `표현 오타/축약 패턴(범용)`만 공개 label로 사용한다.
- 여기서 말하는 재해독은 `표현 오타/축약 패턴`을 범용 후보로 세우는 것이며, 특정 표면어의 정상형을 정답처럼 복원하는 작업이 아니다.
- 특정 표면어를 특정 정상 표현으로 복원하는 규칙, 나이/외모 전용 규칙, `X -> Y`식 전역 치환 규칙을 만들지 않는다.
- 실제 의미 판단은 해당 packet의 title/body/comment/comment_dialogue와 direct evidence를 함께 읽는 LLM 재검토 결과로만 둔다.
- 과거 항목에 남은 구체 표면어 해석 예시는 당시 known-bad packet의 historical observation이며, 현재 prompt/report/reason의 active rule이 아니다.

## 2026-05-31 v336 추가 규칙: 말머리와 exact-title surface는 alias가 아니다

- 커뮤니티 검색 결과의 `스포)`, `질문)`, `소신발언))`, `후기`, `리뷰`는 게시글 말머리/글 성격 표지이며 작품명 일부로 승격하지 않는다.
- VLM/OCR direct title과 공식 플랫폼 URL이 말머리 없는 작품명을 지지하면, final title도 말머리 없는 작품명이어야 한다.
- exact-title surface는 작품명 direct evidence일 수는 있지만 community alias evidence가 아니다. distinct clean alias가 없으면 `slang_insight`/Slang DB 저장 후보로 표시하지 않는다.
- author surface는 author mapping으로만 보고, 작품 alias나 `slang_db` confirmed alias로 승격하지 않는다.
- 문장형/합성형 surface가 `store_in_slang_db=false`이면 리뷰 보고서에서는 `저장 차단 후보`로 적고 confirmed alias처럼 요약하지 않는다.

## 2026-05-31 v330 추가 규칙: 표현 재해독은 범용 후보 label로만 공개한다

- 표현 오타/축약 재해독은 `표현 오타/축약 패턴(범용)`로 기록한다.
- public prompt/reason/report에서 `X -> Y`식 deterministic paraphrase를 쓰지 않는다. 특정 표면어를 전역 규칙으로 만들면 semantic review가 다시 문자열 치환기로 퇴화한다.
- `surface_paraphrase_notes`의 source surface는 해당 packet 안의 검토 대상이며, `paraphrase`가 있어도 LLM review payload에는 넘기지 않는다.
- labeler는 이 신호를 작품명/별칭 evidence로 보지 말고, `semantic_seed_review`, `final_semantic_reread`, direct title/alias/evidence와 함께 `HOLD/REJECT/REPROCESS` 여부를 판단한다.

## 2026-05-31 v329 추가 규칙: OCR 충돌 후보는 cultural_context에서도 낮춰야 한다

- final reason이 OCR 후보를 보조 제목 근거에서 제외하더라도, `slang_insight.cultural_context`가 그 후보를 "본문에 병기된 다른 제목", "해당 작품 설정", "2차 창작 단서"처럼 설명하면 자연어 품질 리뷰에서 근거가 과장된다.
- VLM/OCR 표지 후보가 final title과 충돌하면 공개 필드 전체에서 해당 후보의 role을 `OCR/표지 충돌 후보`로 낮춘다. 본문/별칭/공식 제목 evidence로 승격하지 않는다.
- 이는 특정 OCR 오타를 고치는 규칙이 아니다. final title, official URL/search evidence, image evidence catalog의 direct title 후보가 서로 충돌할 때 evidence boundary를 정리하는 후단 sanitizer다.
- 대표 확인: v329 `11718099`는 `빌환 -> 빌어먹을 환생`을 유지하면서 OCR 후보 `붉여먹을 혼성명`을 `promotion_eligible=false`, `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias`로 낮췄다. `slang_insight.cultural_context`도 OCR 후보를 본문/별칭/공식 제목 근거로 승격하지 않는다고 명시한다.

## 2026-05-30 v325 정정: 표현 재해독 힌트는 치환 결과를 코드가 만들지 않는다

- `표현 오타/축약 패턴(범용)` 재해독은 `surface_paraphrase_notes`가 정답 paraphrase를 만들어 주는 방식이 아니다.
- 최신 계약은 `expression_typo_abbreviation_or_spacing_candidate`를 packet-local 힌트로 남기고, 실제 의미 해석은 `discourse_semantic_seed_guard`와 `final_semantic_reread`가 원문 title/body/comment/comment_dialogue를 읽어 판단하는 것이다.
- 예전 문서에 있는 구체 표면어 치환 문구는 known-bad packet에서 리뷰/LLM이 읽은 대표 해석 예시로만 본다. 코드나 prompt가 이 치환을 다른 post에 전역 적용하면 안 된다.
- 이 힌트만으로 검색 seed를 만들거나 `slang_db`/BatchMem alias를 저장하지 않는다. 직접 작품명/공식 별칭/작가/회차/플랫폼 URL/강한 캐릭터-작품 edge가 별도로 필요하다.
- 긴 OCR/VLM 표면형 또는 공식 제목 prefix도 community alias가 아니라 title surface variant일 수 있으므로 BatchMem/slang alias 저장 전에 별도 차단/검토한다.

## 2026-05-30 v311 추가 규칙: OCR/VLM 표면형은 official detail보다 우선하지 않는다

- VLM/OCR이 작품명처럼 보이는 텍스트를 읽었더라도, 같은 official detail URL의 locked 공식 후보가 다른 제목을 직접 지지하면 OCR/VLM 표면형은 alias/variant 후보로 낮춘다.
- 이는 특정 오타를 자동 치환하는 규칙이 아니다. `표현 오타/축약 패턴(범용)` 신호를 packet-local 후보 해석으로 다루고, final title은 공식 상세 URL/search evidence와 정합되는 제목을 따른다.
- 같은 URL의 OCR/VLM 표면형이 `mentioned_works`, `comparison_target`, `recommendation_candidates`, `future_watch_target`에 별도 작품처럼 남으면 duplicate reference 오염으로 본다.
- 대표 확인: v311 `11718082`는 OCR/VLM 표면형 `재벌가 차녀의 2회차 결그룹`을 alias/variant로 낮추고, final title은 locked official detail 후보 `재벌가 차녀의 2회차 걸그룹`으로 확정했다. flags는 `official_detail_title_preferred_over_surface_form`, `surface_form_duplicate_reference_pruned`다.

## 2026-05-30 v308 추가 규칙: author_match_unverified는 독립 작품 근거가 아니다

- `author_match_unverified`는 원글 작성자와 같은 닉네임/익명 표면이지만 post IP가 없어 동일 인물로 확정할 수 없는 상태다.
- 이 상태를 `post_author`로 승격하지 않는다. 동시에 짧은 캐릭터/외모/나이 반응글에서는 독립 댓글 evidence처럼 세게 쓰지 않는다.
- 댓글이 `author_match_unverified`뿐이고 직접 작품명/별칭/작가/회차/공식 URL/고유 설정 앵커가 없으면 `context_only` 또는 `HOLD/REJECT` 후보로 본다.
- 대표 확인: v308 `11718091`은 댓글 metadata가 `post_author_match_unverified=true`였고, final은 `official_title=null`, `title_resolution_state=context_only`, flag `comment_author_match_unverified_not_independent_evidence`로 종료됐다.

## 2026-05-30 v303 정정: 오타/축약 재해독은 packet-local 후보 해석이다

- 구체 표면어 치환처럼 보이는 재해독은 특정 표면어를 항상 같은 뜻으로 읽으라는 규칙이 아니다.
- 리뷰 문서와 prompt에는 오타/축약 재해독을 일괄 적용 규칙, 항상 적용되는 선행 해석, 고정된 재판독 계약처럼 보이게 쓰지 않는다.
- 올바른 표현은 "해당 packet의 title/body/comment/comment_dialogue와 공개 evidence를 함께 볼 때 가능한 자연어 후보 해석"이다.
- 이 가설은 작품명/별칭 evidence가 아니다. 단일 작품 확정에는 별도 direct title/alias, 공식 URL, 작가/회차/고유 설정, OCR/VLM explicit work title 같은 독립 근거가 필요하다.
- 과거 문서의 `23센줄` 예시는 해당 known-bad packet에서의 대표 사례로만 읽고, 새 표면어를 차단/허용하는 deterministic rule로 확장하지 않는다.

## 2026-05-30 v297 추가 규칙: targeted 회복을 전체 품질 승인으로 승격하지 않는다

- 원본 run artifact가 partial이면, known-bad 회복 증거와 10만 건 품질 승인 증거를 분리한다.
- `11718097`, `11718099`처럼 targeted review에서 `ACCEPT`가 나와도, 같은 run family의 `11718083`, `11718091`이 `HOLD`로 남으면 active goal 전체는 닫지 않는다.
- `HOLD`는 실패가 아니라 "근거가 약해 자동 승인에 쓰지 않음"이라는 별도 상태다. memory-query/quote recall, anonymous author/IP dialogue, VLM/OCR weak public state는 이 상태를 유지할 수 있다.
- 10만 건 semantic approval은 expanded random baseline과 P0/P1 high-risk expansion이 분리 보고되기 전까지 `REVIEW-LOCKED`로 둔다.

## 2026-05-30 v287 추가 규칙: 2차 의미 재독해도 LLM 단독 판단으로 끝내지 않는다

- `11718091` packet에서는 title/body/comment 맥락상 표현 오타/축약 패턴(범용)가 강했다. 이 표면은 작품명/별칭 evidence가 아니라 원문 의도 이해 힌트다.
- 1차 LLM이 과거 known-bad 표면을 seed로 올리거나 `표현 오타/축약 패턴(범용)` 신호를 검색어로 확장할 수 있다. 이때 바로 검색하지 말고 `discourse_semantic_seed_guard`가 title/body/comment를 다시 읽었는지 확인한다.
- 2차 LLM도 특정 인명/캐릭터 표면을 `keep/medium`으로 남길 수 있으므로, 최종 판단은 LLM 답변만 보지 말고 `surface_paraphrase_context_terms`, `semantic_seed_review_context_terms`, warnings, final `title_resolution_state`를 같이 본다.
- 직접 작품 앵커나 공식 URL이 없으면 최종은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`가 맞다.
- 대표 확인: v287 `11718091`은 1차 seed/search 제안이 있었지만, 2차 meaning pass와 sanitizer 이후 `title_novel_terms=[]`, `search_suggestions=[]`, final null-title/context-only로 종료됐다.

## 2026-05-30 v286 추가 규칙: VLM/OCR on 검증은 entrypoint image limit도 evidence다

- VLM/OCR on이라고 해도 이미지 byte limit 때문에 VLM chunk가 전송되지 않으면 image evidence는 Missing 또는 Weak다.
- `expert_main.py`의 기본 VLM 이미지 제한은 pipeline 기본보다 작으면 안 된다. 현재 기준은 `16777216` bytes다.
- `image_too_large`가 보이면 모델 판단보다 먼저 run config, manifest, log의 `max_image_bytes`, `VLM chunk request/result`를 확인한다.
- 대표 확인: v286 `11718114`는 limit 정렬 후 VLM chunk가 전송됐고, direct OCR title이 없는 visual-only 이미지라 final title null/adjacent가 유지됐다.

## 2026-05-30 v259 추가 규칙: VLM/OCR 근거는 구조화된 public field로 남겨야 한다

- 이미지 기반 결론은 reason이나 worker log에만 남기면 대형 정성 리뷰에서 `Strong` evidence로 쓰기 어렵다.
- `identity.image_evidence_catalog` 또는 review packet의 동등 field에 `source_url`, `ocr_text`, `visual_summary`, `explicit_work_title`, `explicit_author_name`, `work_cues`가 남는지 확인한다.
- public result에는 원문 `content_blocks`, `image_urls`, `image_count`가 있어야 브라우저/비전 재검토가 가능하다.
- 이미지가 없는 글에는 status-only image catalog를 만들지 않는다. 대형 result에서 노이즈 field가 10만 건에 붙으면 VLM/OCR evidence gap을 더 보기 어렵다.
- 대표 확인: v259 `11718082`는 이미지 OCR catalog와 KakaoPage evidence로 `재벌가 차녀의 2회차 걸그룹`을 확정했고, `11718080`은 이미지 없는 social-lament 글이라 image catalog가 없다.

## 2026-05-30 v250/v251 추가 규칙: VLM/OCR 표지 title도 검색/원문과 충돌하면 약한 근거다

- 이미지가 있다고 해서 VLM/OCR이 읽은 title을 곧바로 Strong evidence로 쓰지 않는다.
- 표현 오타/축약 패턴(범용)처럼, 표지 OCR도 글 제목/본문/댓글/검색 evidence와 함께 다시 읽는다.
- 글 제목의 안정 별칭, 본문 캐릭터/맥락, official detail URL, 검색 snippet이 한 작품을 지지하고 VLM/OCR title만 다른 작품처럼 보이면, VLM/OCR title은 conflict evidence다.
- Verifier가 `search_absent_verified_title`, `nullify_title`, critical counter를 낸 image/OCR-only title은 후단 Arbiter/suspected title이 다시 확정 title로 올리지 못해야 한다.
- final title이 안정 alias/official URL로 따로 뒷받침되면 `vlm_ocr_title_conflict_with_final_title`, `ocr_title_conflict_with_stable_alias`를 남긴다.
- 브라우저로 실제 post 이미지 로딩 완료 화면을 볼 수 있으면, lazy-load 실패나 OCR 오독 여부를 별도 evidence로 남긴다.
- 대표 확인: v250 `11718099`는 VLM/OCR 오독으로 `검은 여왕의 혼성명`이 final title이 되는 회귀였고, v251은 `빌환 -> 빌어먹을 환생` 안정 alias/official URL로 회복됐으며 OCR conflict flags가 남았다.
- 주의: v251 live 회복은 batch-memory exact alias rescue 경로다. weak-image canonical rescue branch는 focused unittest로 증명됐으므로, 대형 리뷰에서는 실제 trigger 빈도를 별도 bucket으로 확인한다.

## 2026-05-30 v248 추가 규칙: 소설 일반어 + 친구/한탄은 단일 작품 seed가 아니다

- 표현 오타/축약 패턴(범용)처럼, `소설 보는 친구 있으면 좋음`류도 먼저 자연어 의도를 읽는다.
- 제목/본문에 `소설`, `TS`, `갈드컵` 같은 단어가 있어도, 글의 핵심이 "밥 먹으며 장르 얘기를 같이 할 친구가 있었으면"이라는 사회적 한탄이면 단일 작품 찾기/리뷰가 아니다.
- 이런 글은 `is_novel_related=true`일 수 있지만 `official_title=null`, `is_resolved_work_discussion=false`, `title_resolution_allowed=false`가 정상일 수 있다.
- `TS`, `갈드컵`, `주류` 같은 장르/커뮤니티 용어가 title/search seed로 올라오면 `discourse_semantic_seed_guard`가 한 번 더 읽어 `context_only/drop`으로 낮춘다.
- 이 재독해는 seed가 아예 없을 때만 도는 보조 장치가 아니다. `소설`, `TS 주류 소설`, `갈드컵 TS 소설`처럼 이미 title/search seed가 만들어진 뒤에도 사회적 한탄/장르 잡담 신호가 있으면 다시 읽는다.
- 단, `무슨 소설`, `기억 안남`, `대사`, `장면`, `찾...`처럼 작품 찾기/기억 회수 신호가 있으면 같은 "친구" 단어가 있어도 social-lament로 단정하지 않는다.
- 대표 확인: v249 `11718080`은 semantic seed review 후 `title_novel_terms=["소설"]`, `search_suggestions=["TS 주류 소설","갈드컵 TS 소설"]`이 `[]`로 내려갔고, final `discussion_type=trope_discussion`, `official_title=null`로 확인됐다.

## 2026-05-30 v246 추가 규칙: 댓글 author/IP는 대화 메타이지 title evidence가 아니다

- `comment.author == post.author`만으로 원글 작성자의 이어쓰기라고 단정하지 않는다.
- `ㅇㅇ` 같은 익명/공통 author는 IP가 있으면 IP까지 같이 보고 speaker를 분리한다.
- post IP와 comment IP가 모두 있고 서로 다르면 익명 author match만으로 `role=post_author`를 부여하지 않는다.
- 댓글 author/ip/comment_id/reply_to는 대화 흐름을 읽기 위한 메타이며, 작품명/별칭/공식 URL 근거가 아니다.
- 대표 확인: v246 focused regression에서 같은 `ㅇㅇ`이라도 IP가 다른 댓글은 `post_author`가 아닌 `user1`로 분리됐다.
- 대량 리뷰에서는 `comment_author_ip_mismatch_dialogue`, `post_author_comment_not_independent_evidence`, `comment_answer_side_conversation`을 별도 high-risk bucket으로 본다.

## 2026-05-30 v245 추가 규칙: title-null reason score는 strong evidence처럼 말하지 않는다

- `official_title=null`이고 `title_resolution_allowed=false`인 결과에서 reason scoreboard가 `plot_mention`, `character_mention`, `author_mention`을 `강한 앵커`로 표시하면 reason-evidence alignment 이슈로 본다.
- 이런 앵커는 작품명 확정 근거가 아니라 원문 맥락 단서일 수 있다. 비관련/title-null이면 `작품명 확정에는 쓰지 않는 맥락 앵커`, 관련/title-null이면 `정식 제목 미확정` 맥락 앵커로 표현해야 한다.
- 대표 확인: v244 `11718089`는 final scope가 `author_new_work_context`였지만 scoreboard가 `강한 앵커(plot_mention)`를 남겼고, v245 focused regression에서 이를 차단했다.

## 2026-05-30 v240 추가 규칙: 자연어 재독해가 내린 seed는 final scope에도 반영한다

- 표현 오타/축약 패턴은 범용 신호로 먼저 읽는다. 이 이해는 reason에만 남기면 부족하다.
- `discourse_semantic_seed_guard`가 seed를 `context_only` 또는 `drop`으로 낮췄고, 직접 작품 앵커가 없으면 final `title_resolution_state`는 `unresolved_matchable`이 아니라 `context_only`여야 한다.
- `context_only`는 게시글이 소설 커뮤니티/캐릭터 맥락을 가질 수 있어도, 그 공개 정보만으로 단일 작품을 찾을 수 없다는 뜻이다.
- `context_only_no_work_anchor` flag가 있으면 검색/Decoder/BatchContext가 후단에서 다시 작품명을 끌어올리지 않았는지 확인한다.
- 대표 확인: v240 `11718091`은 `official_title=null`, `title_resolution_state=context_only`, `title_resolution_allowed=false`로 확인됐다.

## 2026-05-30 v239 추가 규칙: 플랫폼 브랜딩 title은 작품 URL mismatch가 아니다

- 공식 플랫폼 URL을 fetch했을 때 `<title>` 또는 page title이 `웹소설의 유토피아, 글세상 문피아`처럼 플랫폼 브랜딩이면 작품 title evidence로도, 작품 title mismatch로도 쓰지 않는다.
- 같은 URL의 검색 title/snippet/content가 final title을 직접 지지하면 그 검색 evidence를 우선한다.
- 반대로 fetched title이 브랜딩이 아니라 다른 작품명이고, 검색 evidence도 final title을 직접 지지하지 않으면 `official_url_fetch_title_mismatch`로 HOLD/REPROCESS 후보에 둔다.
- 대표 확인: v239 `11718097`은 `망겜의 힐러 - 문피아 웹소설 - Munpia` 검색 evidence와 `https://novel.munpia.com/328421` final URL이 맞았고, 브랜딩 fetch title false mismatch 경고는 사라졌다.

## 2026-05-30 v238 추가 규칙: OCR/VLM 충돌은 reason뿐 아니라 구조 flag로 남긴다

- VLM/OCR이 직접 읽은 표지 title 후보가 final official title과 다르면, 최종 판단 reason에만 설명하고 끝내지 않는다.
- `vlm_ocr_title_conflict_with_final_title`를 남겨 정성 리뷰 builder가 해당 row를 high-risk bucket으로 과표집할 수 있어야 한다.
- final title이 안정 alias, locked official candidate, official detail URL로 따로 뒷받침되면 `ocr_title_conflict_with_stable_alias`도 남긴다.
- 이 flag는 OCR 후보를 무조건 버리는 뜻이 아니라, OCR 후보가 final title의 Strong evidence로 쓰이면 안 된다는 감사 신호다.
- 대표 확인: v238 `11718099`는 `불먹을 혼성명` OCR 후보와 final `빌어먹을 환생`이 충돌해 두 구조 flag가 남았고, final URL은 `https://novel.munpia.com/222360`으로 유지됐다.
- 같은 원칙으로 표현 오타/축약 패턴(범용)도 "작품 seed 제거"만 남기지 않고, 특정 치환이 아니라 원문 이해 힌트라는 경계를 공개 reason에 남긴다.

## 2026-05-30 v237 추가 규칙: exact alias rescue도 URL/evidence까지 닫아야 한다

- `batch_memory_exact_alias_rescued`로 final title이 회복됐더라도, `heretic_url`, `official_title_evidence`, `official_urls`가 비어 있으면 품질 완료가 아니다.
- stable alias conflict/canonical base correction뿐 아니라 일반 exact alias rescue 경로도 corrected title official URL recovery 대상이다.
- URL이 회복되면 final title, candidate, `primary_work`, public reason counter가 같은 작품을 가리키는지 확인한다.
- VLM/OCR 표지 후보가 최종 title과 다르면 "이미지가 있다"는 사실만으로 Strong title evidence가 아니다. `11718099`의 `붉여먹을 혼성명`처럼 OCR 후보가 충돌하면 conflict/weak visual evidence로 남긴다.
- 대표 확인: v237 `11718099`는 동일 4건 batch에서도 `official_title=빌어먹을 환생`, `heretic_url=https://novel.munpia.com/222360`, `official_title_evidence=true`, `official_urls=1`로 정합화됐다.
- 같은 run의 `11718091`은 `표현 오타/축약 패턴(범용)` 신호로 처리되어 `official_title=null`, `title_resolution_allowed=false`를 유지했다. 이는 기계적 차단이 아니라 검색 전 자연어 의미 재독해 결과다.

## 2026-05-30 v234 추가 규칙: late title correction 후 official URL/evidence를 다시 맞춘다

- stable alias, VLM/OCR, 댓글 대화, semantic reread 등으로 final title이 늦게 교정되면 기존 search/evidence counter를 그대로 믿지 않는다.
- corrected title 기준으로 official detail URL을 다시 찾고, final `heretic_url`, `official_title_evidence`, `official_urls` reason counter가 서로 맞는지 확인한다.
- 검색 result title이 `네이버 시리즈`, `novel.munpia.com`처럼 generic해도 snippet/content/description에 corrected title이 strict match되면 official detail URL 후보가 될 수 있다.
- 단, validator/fetch가 실패한 `validated=false` 회복은 보수적으로 evidence grade를 분리한다. title-matched official detail URL은 도움이 되지만, 이것만으로 10만 건 semantic approval을 올리지 않는다.
- 대표 확인: v234 `11718077`은 `즉사기 들고 무림에 떨어지다`로 교정된 뒤 `https://series.naver.com/novel/detail.series?productNo=14041321`을 회복했고, reason은 `official_title_evidence: true`, `official_urls=1`로 동기화됐다.

## 2026-05-30 v230 추가 규칙: 이전 전문가 해석은 원문 direct evidence가 아니다

- `11718077`에서 확인한 것처럼, Decoder/Verifier가 `즉사무림 -> 즉사수선전`으로 한 번 오판하면 Synthesizer/Arbiter가 그 오판을 더 강한 말로 재확인할 수 있다.
- 후단 보정이나 리뷰는 `best_match`, `matched_alias`, `synthesis_summary`를 원문 증거로 취급하지 않는다.
- direct evidence는 공개 원문 `title/body/comment`, VLM/OCR 원문 추출 필드, evidence URL/snippet, `slang_db`/BatchContext의 안정 alias hit처럼 출처가 분리된 필드여야 한다.
- 안정 alias와 검색 title이 충돌하면, "현재 title이 원문에 직접 쓰였는가"는 raw title/body/comment strict match로 확인한다. 이전 Decoder가 만든 alias mapping은 current title 직접 언급으로 세지 않는다.
- 이 규칙은 `표현 오타/축약 패턴(범용)` 재독해와 같은 원칙이다. 자연어 재이해는 필요하지만, 재이해 결과가 이전 오판을 다시 증거로 먹으면 품질이 좋아지지 않는다.

## 2026-05-29 v216 추가 규칙: 검색 직전 의미 재판독도 댓글 대화 흐름을 읽는다

- `discourse_semantic_seed_guard`는 단순 seed 필터가 아니라 검색 전 자연어 의미 재판독 단계다.
- 이 단계는 title/body/comment뿐 아니라 `comment_dialogue_context`를 함께 읽어, 본문 작성자와 댓글 작성자의 발화 흐름을 확인한다.
- `23센줄` 같은 과거 예시는 특정 정답 치환 규칙이 아니라 `표현 오타/축약 패턴(범용)` 신호로만 읽는다. 그 의미가 나이/외모/잡담인지 여부도 해당 packet의 title/body/comment/comment_dialogue와 direct evidence를 함께 다시 읽어 판단한다.
- `speaker`, `author`, `ip`, `comment_id`, `reply_to`는 대화 흐름 메타이며, 그 자체를 작품 identity evidence로 쓰지 않는다.
- 대표 확인: v216 `11718091`은 1차 Discourse가 `은영이`를 seed로 올렸지만, `discourse_semantic_seed_guard`가 이를 `context_only`로 낮춰 검색/Decoder 재승격 없이 `official_title=null`로 종료했다.
- 이 규칙은 특정 post id나 `은영이` 문자열을 외워 막는 것이 아니라, 짧은 인명 + 나이/외모/잡담 + 직접 작품 앵커 부재 상태에서 해당 packet을 다시 읽는 의미 재판독 절차다.

## 2026-05-29 v214 추가 규칙: 댓글 대화는 `speaker + text`로 읽되 identity evidence와 분리한다

- `comment_context_lines`는 speaker/author/ip/reply 메타만 보여주므로, 본문 작성자가 댓글에서 이어 말하는지 LLM이 직접 이해하려면 `comment_dialogue_context_lines`처럼 같은 #번호에 댓글 text excerpt를 붙인 대화 재구성이 필요하다.
- `comment_dialogue_context_lines`의 `speaker=post_author`, `author=`, `ip=`, `reply_to=`는 대화 흐름 해석용이다. 그 자체를 작품명/별칭/공식 근거로 쓰면 안 된다.
- 댓글 원문이 직접 제목, 안정 별칭, 캐릭터-작품 연결, 줄거리, 공식 URL을 제공할 때만 작품 identity evidence로 계산한다.
- memory-query 글은 “소설 관련 기억 회수/작품 찾기”일 수 있지만, 댓글/본문에 직접 해답이 없으면 `official_title=null`, `title_resolution_allowed=false`가 정상이다.
- 대표 확인: v213 `11718097`은 댓글 5건의 post_author/user speaker와 text excerpt를 보존했고, `망겜의 힐러`로 회복됐다. v214 `11718083`은 `is_relevant=false`, `discussion_type=recommendation`, `title_resolution_state=unresolvable_memory_query`로 내려갔다.

## 2026-05-29 v212 추가 규칙: 주변어 official hit와 resolved title 검증을 분리한다

- `망겜힐 -> 망겜의 힐러`처럼 자연어/검색으로 정식 제목이 풀렸다면, 주변어(`오행복` 등)에서 이미 official-looking URL이 잡혔다는 이유만으로 resolved title 공식 검증 검색을 생략하지 않는다.
- `단행본`은 단독으로는 비소설/웹툰 의심 신호일 수 있지만, 같은 title/snippet에 `웹소설`, `#NOVEL`, `novel`, `장르소설` 표지가 있으면 non-novel media evidence로 쓰지 않는다.
- 반대로 `웹툰`, `만화`, `COMIC`, `manga`, `anime` 표지가 있으면 `단행본` 여부와 무관하게 non-novel media 후보로 둔다.
- 대표 확인: v212 `11718097`은 `망겜의 힐러 [단행본] - 웹소설 - 카카오페이지`와 문피아/네이버 시리즈 URL을 공식 evidence로 확보했고, final `heretic_url=https://m.munpia.com/novel/detail/328421`로 회복됐다.

## 2026-05-29 v210 추가 규칙: 자연어 이해 결과와 slang DB 저장 결과를 분리한다

- 표현 오타/축약 패턴이 있는 표면은 LLM 의미 재검토가 packet-local 범용 표현 재독해 신호로 읽고 reason에 경계를 남겨야 한다.
- 그러나 final title이 null로 내려갔다고 품질이 끝난 것은 아니다. slang DB 저장 계층이 `너에겐` 같은 대명사+조사 표면을 alias로 남기면 다음 run에서 batch memory가 오염을 되살릴 수 있다.
- `너에겐`, `나에게`, `네가` 같은 대명사+조사 표면과 `있어`, `있어도`, `그냥`, `이거` 같은 일반 술어/담화 표면은 slang alias가 아니다.
- `title_resolution_allowed=false` 및 `unresolvable_memory_query`인 글은 소설 관련 기억 회수일 수 있지만 단일 작품 alias 관측으로 저장하지 않는다.
- 대표 확인: v210 `11718091`은 당시 known-bad packet에서 `표현 오타/축약 패턴(범용)` 신호를 작품 seed에서 제외하고 title null을 유지했으며, 기존 DB 오염 `너에겐` 계열은 cleanup 후 match 0건으로 확인됐다. 최신 공개 보고에서는 구체 치환 대신 범용 label을 쓴다.

## 2026-05-29 v209 추가 규칙: OCR-only conflict는 검색뿐 아니라 심의 근거에서도 낮춘다

- OCR/VLM이 읽은 제목 후보가 stable alias 또는 브라우저 시각 근거와 충돌하면, 그 후보는 title evidence가 아니라 `conflict_ocr_title`이다.
- 검색 query pruning만으로는 부족하다. OCR-only 후보가 Gatekeeper/Discourse/Decoder/Deliberation 입력에서 `작품 단서`, `비공식 명칭`, `정식 제목 후보`로 강하게 쓰이면 reason 품질은 여전히 `HOLD`다.
- stable alias가 있는 글에서는 alias와 공식 플랫폼/작품 상세 evidence를 우선하고, OCR-only 후보는 직접 매핑되기 전까지 `Weak`로 둔다.
- 대표 확인: v209 `11718099`는 최종 title `빌어먹을 환생`과 URL `https://novel.munpia.com/222360`으로 회복됐지만, VLM/OCR의 `불먹을 혼성명`이 내부 심의 reason에 남아 semantic evidence quality는 `REVIEW`다.

## 2026-05-29 보강 원칙: 표현 오타/축약 후보는 기계 차단이 아니라 LLM 의미 재검토로 설명한다

- 특정 표면어를 외워 막거나 복원하지 말고, 표현 오타/축약 패턴이 있는 표면은 packet-local 범용 표현 재독해 신호로 표시한다.
- 이런 유형은 단순 정규식 차단만 남기면 사용자가 말한 것처럼 기계적으로 보인다.
- 따라서 `discourse_semantic_seed_guard`는 title/body/comment와 1차 seed를 다시 읽고, `post_intent`, `content_interpretation`, seed별 `keep/context_only/drop` 근거를 공개 필드에 남겨야 한다.
- 그 결과가 non-title이면 검색/Decoder 재승격도 막고, final reason에는 `표현 오타/축약 패턴(범용)`와 evidence boundary를 같이 남긴다.

## 2026-05-29 v208 추가 규칙: 안정 alias, 상태어, OCR 충돌을 분리한다

- `빌환 표지변경됨` 같은 제목에서 첫 토큰이 BatchContext/검색 근거로 안정 alias라면, 뒤의 `표지변경됨` 상태어와 VLM/OCR 후보가 함께 있어도 alias를 버리지 않는다.
- `표지변경`, `표지변경됨`, `수정됨`, `리메이크됨` 같은 상태/행동어는 작품명 seed가 아니다.
- `있어`, `있어도`, `없어` 같은 술어/어미 조각은 search evidence 근처에 있어도 alias로 저장하거나 rescue하지 않는다.
- VLM/OCR 후보가 브라우저 시각 근거와 충돌하면 OCR 후보는 Strong title evidence가 아니라 conflict/weak evidence다.
- 대표 확인: v208 `11718099`는 final title `빌어먹을 환생`으로 회복됐지만, VLM/OCR이 `검은 여왕을 혼성명`으로 오독했고 595.8s long-tail이 남아 semantic evidence quality는 `REVIEW`다.
- 이 규칙은 title correctness targeted recovery이지 10만 건 semantic approval 근거가 아니다.

## 2026-05-29 v204 추가 규칙: 표면 오타 해석은 reason에 직접 남긴다

- 표현 오타/축약 패턴이 있는 표현은 검색 seed를 막는 데서 끝내지 않고, 공개 reason에 특정 치환이 아니라 범용 신호라는 경계를 남긴다.
- `surface_paraphrase_notes.role=non_title_semantic_context`는 작품명/별칭 evidence가 아니라 원문 이해 힌트다.
- 짧은 인명 + 나이/외모 감상 글에서 마지막 seed가 제거되면 `semantic_seed_review.is_specific_work_discussion=false`로 내부 semantic flag도 낮춘다.
- 대표 확인: v204 `11718091`은 당시 산출물에서 표면 표현 해석과 `작품 seed 제외: 은영이`, `official_title=null`을 남겼다. 최신 지침에서는 이 해석을 `표현 오타/축약 패턴(범용)`로 보고한다.

## 2026-05-29 v201 추가 규칙: seed demotion은 reason에도 설명되어야 한다

- semantic seed review로 title/search seed를 낮췄다면 final reason은 `작품 고유 근거 부족` 같은 일반 문구만 남기지 않는다.
- 공개 reason에는 최소한 다음을 포함한다.
  - 글을 자연어적으로 어떻게 읽었는지
  - 어떤 표면이 작품명/별칭 seed에서 제외됐는지
  - 왜 공식 제목을 미확정으로 두는지
- `is_novel_related=true`와 `official_title=null`이 같이 있는 경우, reason은 "소설 커뮤니티/캐릭터 감상 가능성"과 "단일 작품 identity 미확정"을 분리해야 한다.
- 대표 확인: v201 `11718091`은 당시 산출물에서 seed demotion과 `official_title=null`을 설명했다. 최신 공개 reason에서는 `표현 오타/축약 패턴(범용)` 신호를 seed 제외 목록에 다시 나열하지 않는다.

## 2026-05-29 v199 추가 규칙: 검색 전에 LLM semantic seed review를 한 번 더 본다

- 짧은 반응글에서 1차 Discourse가 뽑은 `title_novel_terms`와 `search_suggestions`는 그대로 검색 seed로 쓰지 않는다.
- 후속 LLM semantic seed review는 공개 title/body/comment와 1차 seed만 보고 아래를 분리한다.
  - 작품명/안정 별칭/작품 본체 토론 seed
  - 캐릭터/나이/외모/잡담/오타/문장 일부 같은 자연어 문맥 seed
- semantic seed review가 seed를 `context_only`, `drop`, `non_title`로 낮추면 해당 seed와 그 seed에서 파생된 검색 제안은 제거한다.
- known alias, 직접 작품명, 작가/회차/공식 URL, 이미지 OCR/VLM title 같은 strong anchor가 별도로 있으면 이 규칙만으로 무조건 차단하지 않는다.
- 모든 title seed가 demote됐고 이미지/OCR/VLM 또는 강한 작품 앵커가 없으면 검색과 Decoder로 다시 작품명을 찾으려 하지 않는다. 이 경우 `official_title=null`, `work_resolution=none`, `title_resolution_allowed=false`가 정상이다.
- `is_novel_related=true`일 수 있어도, 단일 작품 identity가 없으면 `is_resolved_work_discussion=false`로 둔다.
- 대표 확인: v199 `11718091`은 semantic seed review가 해당 표면을 작품 seed가 아닌 표현 오타/축약 패턴(범용)로 낮췄고, 검색/Decoder 없이 `is_relevant=false`, `official_title=null`로 종료됐다.

## 2026-05-29 v195 추가 규칙: 표면 오타/축약 표현은 검색 seed가 아니라 문맥 힌트다

- 특정 표면어/숫자 패턴을 특정 정상 표현으로 복원하지 않는다. 표현 오타/축약 패턴이 보이면 `표현 오타/축약 패턴(범용)`로만 표시하고, 실제 의미는 해당 packet의 title/body/comment/comment_dialogue에서 다시 판단한다.
- 이런 표면은 `title_novel_terms`, alias 후보, slang 후보, 검색 seed로 승격하지 않는다.
- 제목/본문/댓글이 캐릭터 외모/나이 감상만 말하고 직접 작품명, 안정 별칭, 줄거리, 작가, 회차, 공식 URL이 없으면 `official_title=null`이 정상이다.
- Discourse/검색 제안이 `인명 + 나이`, `인명 + 정식 제목`, `인명 + 캐릭터`, `담화표지 + 인명` 쿼리를 만들면 weak-character/context-noise로 보고 제거한다.
- known alias 또는 strong work anchor가 별도로 있으면 이 규칙만으로 무조건 차단하지 않는다. 단, 그 경우에도 expression-reread 표면 자체는 title evidence가 아니다.
- 대표 확인: v195 `11718091`은 당시 known-bad packet에서 `표현 오타/축약 패턴(범용)` 신호를 작품 seed에서 제외했고, 실제 검색 실행 없이 `is_relevant=false`, `official_title=null`, `discussion_type=noise`로 종료됐다. 최신 문서/프롬프트에서는 `X -> Y`식 표현을 쓰지 않는다.

## 2026-05-29 v149 reason-final contradiction rule

- 공식 플랫폼 검색 hit 또는 `official_title_evidence=true`는 단독 Strong evidence가 아니다.
- 다음 조건이 겹치면 final title은 `HOLD`가 아니라 우선 demotion/reject 후보로 본다.
  - 원문 title/body/comment에 후보 title 또는 검증된 alias가 없다.
  - candidate evidence bucket의 `post_spans`, `search_snippets`, `official_urls`가 모두 비어 있다.
  - verifier/reason에 thematic overlap, no specific work anchor, absent grounding, critical counter-argument가 있다.
  - anchor가 `none`, `search_only`, `decoder_grounded_official` 계열이다.
- 이미지/스크린샷/VLM 의존 케이스는 브라우저/VLM 직접 확인 전까지 Strong evidence로 승격하지 않는다.

Protocol

## 2026-05-29 v148 추가 규칙: evidence 없는 공식 title 확정은 실패로 본다

- `official_title_evidence=true`라도 `post_spans=0`, `search_snippets=0`, `official_urls=0`이면 Strong evidence가 아니다.
- 특정 작품 없는 장르/트로프/비소설 추천 글이 웹소설 title로 resolved되면 `REJECT` 또는 `HOLD` 후보로 둔다.
- `11718082`처럼 제목 표면의 일반 phrase가 title slot에 들어간 경우 generic/title-surface false positive로 본다.
- `11718090`처럼 영화 추천 글이 웹소설 title로 resolved되는 경우 매체 경계 오판으로 본다.
- `11716486`처럼 이미지 의존 post는 브라우저/VLM 확인 없이는 Strong evidence로 승격하지 않는다.
- `11718097`처럼 같은 입력이 v147과 v148에서 resolved/null로 흔들리면 alias recall 비단조성으로 보고 re_search/re_judge한다.

## 2026-05-29 v147 추가 규칙: weak-character preserve/rescue는 원문 직접 앵커 없으면 차단한다

- `11718091`류 제목/본문/댓글이 캐릭터 나이, 외모, 묘사에 대한 짧은 반응이면 검색 후보나 batch memory alias support만으로 `is_relevant=true` 또는 `official_title`을 되살리지 않는다.
- Verifier가 `community_banter/reject`이고 `grounding_anchor=none/search_only/community_mention`이면 `unresolved_worklike_preserve`보다 weak-character block이 우선한다.
- post author 댓글은 작성자가 자기 글에 이어 붙인 맥락으로 볼 수 있으나, 직접 작품명·안정 별칭·작품 내부 전개·공식 URL을 제공하지 않으면 independent identity evidence가 아니다.
- 이런 케이스는 `official_title=null`, `is_resolved_work_discussion=false`, `title_resolution_allowed=false`가 정상이다. `is_novel_related=true`는 "소설 커뮤니티 담론 가능성"이지 단일 작품 매칭 승인이 아니다.
- 대표 증거: v147 `11718091`은 `is_relevant=false`, `title_resolution_state=unresolved_matchable`, flags=`weak_character_reaction_unresolved_blocked`, `post_author_comment_not_independent_evidence`로 확인됐다.

## 2026-05-29 v145 추가 규칙: title null/noise 성공과 flag taxonomy를 분리한다

- v145 targeted rerun에서 `11718091`은 `official_title=null`, `is_relevant=false`, `discussion_type=noise`로 내려가 과확정은 막혔다.
- 같은 결과에서 `is_novel_related=true`, `is_resolved_work_discussion=false`, `title_resolution_state=unresolvable_memory_query`가 함께 남았다. 이는 "소설 커뮤니티 반응일 수 있음"과 "단일 작품 매칭은 불가"를 분리한 정상 방향이다.
- 다만 weak-character 전용 flag가 live 결과에 항상 노출되지는 않았다. 따라서 title null 성공만으로 `ACCEPT`하지 말고, reason/flag taxonomy가 일관되는지는 `HOLD/docs_issue`로 별도 확인한다.
- `post_author` 댓글은 대화 흐름 해석에는 유효하지만, 원문/댓글이 직접 작품명·안정 별칭·공식 URL·강한 캐릭터-작품 edge를 제공하지 않으면 independent identity evidence가 아니다.
- v145도 5건 targeted regression이므로 10만 건 semantic approval 근거가 아니다.

## 2026-05-29 v138 추가 규칙: 짧은 작품 약칭 + 캐릭터/등장인물 페이지 evidence를 하드코딩 없이 본다

- `빌환`, `망겜힐`처럼 제목 첫머리의 짧은 약칭은 단독으로 작품 확정 근거가 아니다.
- 다만 같은 post/comment에 여러 캐릭터명 또는 설정 앵커가 있고, 검색 evidence가 공식 detail 또는 `<작품명>/등장인물`류 문서로 연결되면 `character_page_title_resolved` 후보로 볼 수 있다.
- 이 규칙은 특정 약칭을 하드코딩하지 않는다. 원문 title-leading span, 캐릭터/설정 앵커, 검색 URL/snippet의 작품명 연결을 함께 요구한다.
- 등장인물 페이지나 wiki snippet은 공식 플랫폼 detail보다 약한 evidence다. 공식 detail이 없으면 `Medium` 이하로 두고, reason에는 원문 span과 evidence URL/snippet 연결을 남긴다.
- 상태어/행동어/표지변경/일반어가 title slot에 들어가면 `status_action_not_title` 또는 `generic_surface` 위험으로 보고 `HOLD/REJECT` 후보로 둔다.
- 대표 확인: v138 `11718099`는 `빌환 -> 빌어먹을 환생`, v138 `11718097`은 `망겜힐 -> 망겜의 힐러`로 회복됐다. v138 `11718091`은 title null이지만 reason/schema 혼선이 남아 계속 `HOLD/docs_issue`다.

## 2026-05-28 v134 추가 규칙: relevance와 title resolution scope를 별도 필드로 본다

- `PickvelIdentity.is_relevant=false`만 보고 "소설 관련성이 없다"고 단정하지 않는다. `is_novel_related=true`이면 소설/웹소설 커뮤니티 담론이지만 단일 작품 identity 확정은 실패한 케이스일 수 있다.
- `is_resolved_work_discussion=true`와 `title_resolution_state=resolved`가 함께 있을 때만 단일 작품 본체 토론으로 본다.
- `title_resolution_allowed=false`이면 후처리 rescue가 title을 되살린 경우 `override_audit`와 evidence edge를 요구한다. 직접 title/안정 alias/캐릭터-작품 강연결/quote-source/공식 detail edge가 없으면 `HOLD` 또는 `REJECT` 후보로 둔다.
- `title_resolution_state=unresolved_matchable`은 회수율 개선 대상이지 `ACCEPT` 근거가 아니다. `unresolvable_memory_query`는 작품 찾기/기억 회수 글로 보고 `official_title=null`을 정상 출력으로 둔다.
- reason에 `[범위 분리]` 섹션이 있으면 해당 공개 필드를 review packet에 그대로 남기고, reason-final contradiction 여부를 별도로 라벨링한다.
- 1차 구현은 schema 표현력 보강이다. `title_lock_state`, `evidence_edges`, `reason_decision_contradiction` detector가 없으면 10만 건 semantic gate는 계속 `REVIEW-LOCKED`다.

## 2026-05-28 v133 추가 규칙: null-title 성공과 relevance/schema 혼선을 분리한다

- known-bad targeted rerun에서 `official_title=null`이 맞더라도, `discussion_type`과 reason이 `noise/review/관련/비관련` 사이에서 흔들리면 완전 `ACCEPT`로 보지 않는다.
- `11718091` 유형처럼 특정 작품명은 확정할 수 없지만 소설 커뮤니티/캐릭터 반응일 수 있는 글은 `resolved_work_identity=false`와 `is_novel_related` 가능성을 분리해 기록한다.
- v134 이후 schema는 이 둘을 분리할 수 있다. 다만 기존 결과나 새 필드가 없는 packet은 `HOLD/docs_issue`로 두고, final title 오염과 reason/schema 혼선을 별도 이슈로 추적한다.
- comment metadata가 결과 내부에 보존돼도, 댓글 원문이 직접 작품명/별칭/캐릭터-작품 연결을 제공하지 않으면 작품 identity evidence로 승격하지 않는다.
- 대표 증거: v133 `11718097`은 `comment_metadata` 5건이 보존됐고 title도 맞았으므로 targeted `ACCEPT`; v133 `11718091`은 null-title은 안전하지만 reason/schema 혼선 때문에 `HOLD`.

## 2026-05-28 v132 추가 규칙: title canary와 대화 메타 검증을 분리한다

- `gallery_id`, `post_author`, `comment_metadata`, `comment_context_lines`가 없는 targeted packet은 author/comment dialogue-context 검증에 사용할 수 없다.
- `comments`가 문자열 배열만 있고 작성자/IP/reply 메타가 없으면, 글쓴이의 추가 설명과 타인 댓글 답변을 구분했다는 증거가 아니다.
- title 회복 canary가 `ACCEPT`여도, 대화 메타가 없으면 dialogue-context approval은 `INFO_MISSING` 또는 `REVIEW-LOCKED`로 분리한다.
- review/targeted input builder는 원본 row에 있는 `gallery_id`, `post_author`, `comments_raw`, `comment_metadata`, `comment_context_lines`를 반드시 보존한다.
- `comment_metadata`와 `comment_context_lines`는 작품 identity evidence가 아니라 발화자/대화 흐름 해석용 공개 메타다. `comment_context_lines`는 가능한 경우 `speaker`, `author`, `role=post_author`, `ip`, `reply_level`, `reply_to`, `comment_id`를 포함한다. 댓글 원문이 직접 작품명/별칭/캐릭터/줄거리/URL을 말할 때만 작품 앵커로 계산한다.
- 대표 증거: v132 context audit에서 `11718097`, `11718118` packet 모두 `gallery_id=null`, `comment_metadata=0`, `comment_context_lines=0`으로 확인됐다.

## 2026-05-28 v131 추가 규칙: final 성공과 중간 guard 충돌을 분리한다

- v129 `11718097`처럼 final title이 맞아도 canonical suspect 단계가 다른 후보로 흔들렸다면 `ACCEPT`와 별도로 `post_arbiter_lock_preserved` 회귀 seed로 남긴다.
- v130 `11718097`처럼 canonical suspect를 막은 뒤 다른 후처리 guard가 locked title을 삭제할 수 있다. 따라서 guard 하나의 통과를 전체 lock propagation 완료로 보지 않는다.
- 작가앵커-후보작가 충돌 guard는 필요하지만, snippet/alias lock이나 filtered official detail이 같은 title을 지지하면 title 삭제보다 보존이 우선이다.
- filtered official detail은 `official_title_evidence=true`와 동일하게 보지 않는다. 다만 locked title과 같은 방향이면 `Weak/Medium` 보조 근거로 분리한다.
- 대표 회귀 post:
  - `11718097`: v131 기준 `망겜의 힐러` resolved로 회복. v130의 `작가앵커-후보작가 충돌 title 보류`는 별도 회귀 seed로 유지한다.
  - `11718118`: v131 기준 `trope_discussion/null title` 유지.

## 2026-05-28 v128 추가 규칙: 중간 전문가 판단과 최종 JSON을 별도 판정한다

- 전문가/Arbiter/Judge가 올바른 title 또는 null-title을 냈어도, `_context_to_output()` 후단에서 final correction, canonical suspect 보정, batch memory rescue, unverified alias demotion이 결과를 다시 바꿀 수 있다.
- 따라서 정성 리뷰는 "LLM이 자연어를 이해했는가"와 "최종 JSON이 그 이해를 보존했는가"를 분리한다.
- `search_evidence_alias_inference`가 작가명만 잡은 경우에는 특정 작품 하나를 final title로 rescue하지 않는다. 작가명은 작품군 context이지 단일 작품 identity edge가 아니다.
- `discuss_genre`, `trope_discussion`, `genre_opinion` 경고가 있으면 장르어/역할어가 wiki/community 문서 title로 검색되어도 `official_title=null`이 기본값이다.
- snippet canonical alias lock이 있고 원문 title lead alias와 연결되면, 후단 보정은 이 lock을 깨기 전에 더 강한 반대 evidence를 요구한다.
- filtered official detail(`token_mismatch:official`)은 무조건 폐기하지 말고, snippet alias lock과 같은 후보를 가리키는지 `weak_support`로 검토한다.
- 대표 회귀 post:
  - `11718097`: v126에서 `망겜의 힐러` 중간 판정이 후단에서 `게임4판타지`로 뒤집혔고, v128에서는 wrong title은 막았지만 `HOLD/unresolved`로 남았다.
  - `11718118`: v127에서 `대협 -> 장르소설 마이너 갤러리/밈` false positive가 발생했고, v128에서 `trope_discussion/null title`로 회복됐다.

## 2026-05-28 v124 추가 규칙: 제목 첫 토큰 + 조사 clean alias는 검색 앵커로 보존하되 final 확정과 분리한다

- `망겜힐은`, `탑매는`, `빌환이`처럼 제목 첫 토큰에 조사가 붙은 표면은 clean alias 후보로 분리해 검색 앵커에 포함할 수 있다.
- 이 규칙은 특정 작품명 하드코딩이 아니라 raw title span 보존 규칙이다.
- clean alias 보존은 recall 개선용이며, 그 자체가 `official_title` 확정 근거는 아니다.
- final 확정에는 원문 span과 검색 evidence가 직접 연결되는 edge가 필요하다. 검색 degraded, official evidence 약함, snippet-only 연결이면 `Medium` 이하 증거로 둔다.
- 역할·호칭성 표현(`족장님`, `대족장님` 등), 일반어, 장르어, 저정보 표현은 이 규칙으로도 title rescue 근거가 될 수 없다.
- 대표 회귀 post: `11718097`. v124에서는 `망겜힐은 -> 망겜힐` 검색 앵커 보존으로 `망겜의 힐러`를 회수했고, 기존 wrong-title rescue는 재발하지 않았다.

## 2026-05-28 v123 추가 규칙: 역할·호칭성 search-inferred alias는 단독 title 근거가 아니다

- `족장`, `족장님`, `대족장`, `대족장님`처럼 역할, 지위, 호칭, 관계를 나타내는 표현은 원칙적으로 작품 별칭이 아니라 담화/캐릭터 설명일 수 있다.
- 이런 표현이 `search_evidence_alias_inference`, batch memory, 검색 snippet 유사도만으로 작품명과 연결되면 `search_only` 또는 `weak_alias_candidate`로 본다.
- 원문 title/body/comment에 직접 작품명, 안정된 약칭, 캐릭터-작품 연결, quote-source, 공식 detail edge가 없으면 역할·호칭성 alias만으로 `official_title`을 확정하지 않는다.
- Arbiter/Verifier가 `official_title=null` 또는 `anchor=none`을 냈는데 후처리 rescue가 역할·호칭 alias로 title을 되살리면 `role_or_honorific_alias_rescue_blocked` bucket에 넣고 `HOLD` 또는 `REJECT` 우선으로 본다.
- final title 삽입이 차단됐더라도 canonical suspect 단계에서 역할·호칭 후보가 반복 생성되면 후보 노이즈로 따로 기록한다.
- 대표 회귀 post: `11718097`. v122에서는 `족장님 -> 두 번 각성하는 대족장님`으로 과확정되어 `REJECT`였고, v123에서는 wrong-title final 삽입이 차단됐지만 correct title recall은 `HOLD/re_search`로 남았다.

## 2026-05-28 v121 추가 규칙: 기억 회수/제목 찾기 글은 매칭 불가를 정상 출력으로 둔다

- `무슨 소설인지 기억 안남`, `대사만 기억남`, `뭐였지`, `옛날에 본 소설`처럼 사용자가 작품명을 찾는 글은 소설 관련일 수 있지만 단일 작품 확정 글은 아니다.
- 원문 title/body/comment에 직접 제목, 안정된 작품 약칭, 고유 대사 출처, 캐릭터-작품 연결이 없으면 `official_title=null`, `work_resolution=none` 또는 `unresolved`를 유지한다.
- 검색 결과가 원문 일부 단어와 겹치거나 공식 플랫폼 URL을 갖고 있어도, 원문 span과 후보 title을 직접 잇는 evidence edge가 없으면 `search_only`로 취급한다.
- reason 내부에 `search_only`, `anchor=none`, `official_title_evidence=false`, `post_spans=0`, `evidence_bucket: ... official_urls=0` 같은 반대 근거가 있는데 final title이 확정되면 `reason_decision_contradiction` bucket으로 보낸다.
- `_title_deliberately_null=true`, `recommendation`, `memory_query`, `association_post(title_body_mismatch)`가 나온 뒤 후처리 rescue가 title을 되살린 경우, `override_audit`/reason line을 확인하고 `HOLD` 또는 `REJECT` 우선으로 본다.
- comment author/ip/gallery metadata는 대화 참여자 추적 근거이며, 댓글 원문이 직접 작품명/별칭/캐릭터/줄거리를 말하지 않는 한 작품 identity evidence로 세지 않는다.
- 대표 회귀 post: `11718083`. v121 canary 기준 `official_title=null`, `novel_identity=null`, `work_resolution=none`, `anchor_type=none`, `discussion_type=recommendation`으로 내려갔다.

## 2026-05-28 구조 리뷰 규칙: 전문가 오케스트레이션 결과와 최종 JSON을 분리해서 본다

- 전문가 프롬프트가 `official_title=null` 또는 보류를 냈더라도, `AgenticPipeline._context_to_output()` 후처리에서 후보 승격, structural rescue, Verifier 우선, unresolved preserve가 다시 개입할 수 있다.
- 정성 리뷰는 최종 `official_title`만 보지 말고 Gatekeeper/Discourse/Decoder/Verifier/Synthesizer/Arbiter output, `reason_lines`, `consistency_flags`, search stats, title-null block reasons를 함께 본다.
- `is_relevant`는 "소설 관련성"과 "단일 작품 매칭 가능성"을 혼동하기 쉬우므로, 리뷰 라벨에는 `is_novel_related` 성격과 `resolved_work_identity` 성격을 분리해 기록한다.
- 세부 한계와 개선 계약은 `docs/devs/EXPERT_ORCHESTRATION_LIMITATIONS.md`를 기준으로 본다.

## 2026-05-27 v95 추가 규칙: structured evidence catalog 우선 확인

- `reason` 문자열의 `evidence_bucket: official_urls=0` 같은 counter가 있어도, `identity.search_evidence_catalog`에 resolved title과 직접 연결되는 플랫폼/공식 URL이 있으면 이를 별도 공개 근거로 계산한다.
- `reason` counter와 `search_evidence_catalog`가 충돌하면 판정 오판으로 단정하기 전에 review tooling counter mismatch로 분리한다.
- `evidence_catalog`의 `source_tier=novel_platform`, `official_detail`, 또는 문피아/노벨피아/네이버 시리즈/카카오페이지/조아라/리디 작품 URL은 title match가 있을 때 official URL evidence로 세며, 라벨 산출물에는 `catalog_official_urls`, `catalog_search_snippets`를 남긴다.
- 대표 회귀 post: `9803986`. v95 기준 structured catalog 반영 후 `REPROCESS/re_search -> ACCEPT/no_action`으로 전환됐다.

## 2026-05-27 v94 추가 규칙: broad topic + character composite 과잉 확정 금지

- `삼국지 떡밥`, `OO 얘기`, `OO 화제`, `OO 논쟁`처럼 넓은 원전/장르/소재를 말하는 title은 그 자체로 단일 작품 title 확정 근거가 아니다.
- 댓글에 캐릭터명이나 원전 인물명이 붙어도, 원문에 특정 작품명/플랫폼 URL/작품 고유 설정이 없으면 `OO + 캐릭터명` 형태의 작품명으로 승격하지 않는다.
- `slang_insight.store_reason=character_attached_composite` 또는 `scope=work_plus_character`가 보이면, broad topic bucket에서는 `HOLD` 또는 `REPROCESS` 우선이다.
- 질문형 post에서 body가 `괴담동?`처럼 추측형 alias이고 댓글이 `악엔/악역의 엔딩은`처럼 다른 답을 반복하면, body guess보다 댓글 답변 충돌을 우선 검토한다.
- 대표 회귀 post: `10529582`, `10870841`. v94 기준 `10529582`는 title null/off-topic으로 내려갔고, `10870841`은 title null/HOLD로 남았다.

## 2026-05-27 v92 추가 규칙: 명시적 비소설 disclaimer

- 제목/본문에 `소설얘기아닌데`, `소설 이야기는 아닌데`, `웹소설 얘기 아닌데`처럼 비소설 토론임을 직접 선언한 경우, 단순히 `소설` 토큰이 있다는 이유로 explicit webnovel context로 보지 않는다.
- 이때 verifier/arbiter/search evidence가 외부 TV 드라마, 게임, 만화, 웹툰, 리뷰집 등 비웹소설 매체를 가리키면 `official_title` 복구를 막고 `HOLD` 또는 `REPROCESS/REJECT` 후보로 둔다.
- `unresolved_worklike_preserve`, `title-surface primary candidate`, locked official/detail rescue 같은 후반 복구 경로에서도 동일한 disclaimer를 존중한다.
- 대표 회귀 post: `9197737`. v92 canary 기준 `is_relevant=false`, `official_title=null`, `discussion_type=off_topic`, `work_resolution=none`.

이 문서는 코드/통계 검토가 아니라 LLM/전문가가 결과를 직접 읽고 판단하는 정성 리뷰 절차다. 대량 런 결과의 최종 품질 승인은 숫자 감사와 이 정성 리뷰를 함께 본다.

## 목적

- 모델 판정이 원문과 근거에 맞는지 확인한다.
- 검색 저하가 결과 오판으로 이어졌는지 확인한다.
- slang DB 후보가 실제 약칭인지, 보류/비교/노이즈인지 판정한다.
- 재검색, 재처리, 프롬프트 수정, slang rule 수정을 구분한다.

## 리뷰 대상 우선순위

1. 검색 저하 flag가 있고 slang 후보가 생성된 케이스
2. 검색 결과가 0 또는 빈약하지만 LLM이 강한 작품 판단을 내린 케이스
3. `unclear_canonical_alias`로 차단된 회수율 손실 의심 케이스
4. `resolved_title`이지만 anchor가 약한 케이스
5. `unresolved_title`, `multi_work`, `adjacent_relevant`, `trope_discussion`, `author_talk` 같은 경계 케이스
6. 비관련 판정이지만 원문에 작품/작가/캐릭터 단서가 있는 케이스
7. 정상군 대조 샘플

## 과잉 확정 금지 규칙

- `search_only`, `title_mention`, `community_mention`, `character_mention` 수준의 약한 anchor는 단독으로 단일 작품명 확정 근거가 아니다.
- candidate evidence bucket에서 `post_spans=0`, `official_urls=0`, `official_nonwiki=0`이면 관련글로 남기더라도 `official_title`은 보류한다.
- `thin-bridge title` 위험이 있으면 직접 post span, official URL, non-wiki official evidence, 충분한 search snippet 중 최소 하나가 없이는 단일 title로 확정하지 않는다.
- `plot_mention`, `title_reaction_link`, `character_mention`에서 나온 후보라도 공식 title evidence나 사용 가능한 플랫폼 detail URL이 없고 full title이 원문에 직접 등장하지 않으면 LLM-only alias/비교작으로 보고 보류한다.
- 일반어, 장르어, 트로프, 캐릭터명, 괄호 안 일반 설명이 검색 결과의 작품명과 우연히 이어진 경우는 `HOLD` 또는 `REPROCESS`로 둔다.
- positive control처럼 별칭이 본문/검색/공식 URL에서 직접 지지되면 resolved를 유지할 수 있다.
- `generic_common_surface` 전수 회귀 결과 `HOLD=88/89`였으므로 이 bucket은 승인 완료가 아니라 계속 `HOLD`다.
- 과잉 확정 guard로 title이 제거된 뒤 `히집악`, `성녀 속마음`처럼 실제 별칭 recall이 빠지는 false negative는 별도 alias recall 문제로 분리해서 리뷰한다.

## 샘플링 단계

20k 이상 대량 run에서 300건 정성 리뷰는 품질 승인이 아니라 오류 유형 발견용 1차 패킷이다. 최종 품질 판단은 위험군 집중 샘플, 계층 샘플, 재처리 비교 샘플을 나눠서 본다.

- 1차 오류 발견: 위험군 중심 300건 이상
- 2차 커버리지 확인: 주요 bucket별 최소 표본 확보
  - 검색 저하
  - 검색 정상 대조군
  - slang 후보
  - slang 미저장/차단 후보
  - resolved 저근거
  - unresolved/multi_work
  - relevant_without_official_title
  - non-relevant false negative 의심군
- 3차 재처리 검증: 개선 코드/검색 안정화 후 같은 post id를 재처리해 판정 변화 비교
- 승인 기준: 각 bucket의 `HOLD/REPROCESS/REJECT/INFO_MISSING` 비중, DB 오염 위험, false negative 재발 여부를 같이 본다.

## 전문가 역할

- 검색 품질 리뷰어: 검색 근거가 충분한지, 검색 장애가 판단에 영향을 줬는지 본다.
- slang/커뮤니티 용례 리뷰어: 후보 term이 실제 약칭, 별칭, 밈, 오타, 문장 조각, 일반어 중 무엇인지 판정한다.
- LLM 판정 리뷰어: 모델 이유와 최종 필드가 일치하는지, 과잉 추론이 있는지 본다.
- 최종 조정자: 리뷰어 불일치를 정리하고 최종 판정을 확정한다.

## 판정 Rubric

- 검색 근거 충분성: `1..5`
  - `5`: 검색/원문 근거만으로 판단 가능
  - `3`: 일부 근거는 있으나 추가 확인 필요
  - `1`: 검색 결과가 비었거나 엉뚱함
- LLM 판단 정합성: `1..5`
  - `5`: 근거와 결론이 일관됨
  - `3`: 결론은 가능하나 설명이 약함
  - `1`: 근거와 결론이 불일치
- slang 후보 라벨:
  - `confirmed_alias`: 실제 약칭/별칭으로 반영 가능
  - `pending_alias`: 가능성 있으나 추가 표본 필요
  - `secondary_reference`: 주변 언급, 저장 보류
  - `comparison_only`: 비교 대상으로만 등장
  - `noise`: 문장 조각, 일반어, 오염
  - `not_applicable`: slang 판단 대상 아님
- DB 반영 위험: `low | medium | high | not_applicable`
- 처리 판정:
  - `ACCEPT`: 현재 결과 승인
  - `HOLD`: 결론은 그럴듯하지만 근거 부족 또는 추가 확인 필요
  - `REPROCESS`: 검색/처리/OCR/VLM/checkpoint 문제로 같은 입력 재처리 필요
  - `REJECT`: 오염/오판으로 폐기
  - `INFO_MISSING`: 공개 필드가 부족해 리뷰 불가
- action:
  - `no_action`
  - `re_search`
  - `re_judge`
  - `re_run`
  - `human_review`
  - `slang_db_review`
  - `docs_issue`

## 합의 방식

- 기본은 2인 독립 리뷰다.
- Codex `spawn_agent` subagent 리뷰는 semantic review 분업이다. repo runtime `expert_main.py --parallel` worker 수, 내부 전문가 체인 병렬도, runtime `GO`를 semantic approval로 대체하지 않는다.
- 두 리뷰어가 같은 최종 판정을 내리면 확정한다.
- 불일치 시 최종 조정자가 결정한다.
- 검색 flag가 있으면 보수적으로 `HOLD` 또는 `REPROCESS`를 우선 고려하고, action은 `re_search`로 둔다.
- slang DB 오염 가능성이 있으면 `HOLD`를 우선한다.
- 실제 약칭 가능성이 높지만 근거가 약하면 `pending_alias`로 분리한다.
- DB 반영 최종 결정은 LLM 단독 판단으로 확정하지 않는다.
- VLM/OCR이 단일 직접 작품 표면을 읽은 경우는 `검색 근거 부족`만으로 `noise`로 내리지 않는다. title 판단과 official URL evidence grade를 분리한다.
- URL 후보가 다른 작품 대표 제목을 가리키면 title이 맞아도 URL은 제거하고 `url_title_mismatch`로 기록한다.

## 리뷰 패킷 생성

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 300 --per-bucket 40
```

계층 샘플과 정상 대조군을 같이 넣는 확대 패킷:

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 1000 --per-bucket 80 --strategy stratified --control-count 120
```

기본 입력:

- checkpoint: `out/expert_result_<RUN_ID>_checkpoint.jsonl`
- run audit: `out/run_audit_<RUN_ID>.json`
- slang DB: `slang_db/slang_db.json`

기본 출력:

- `out/llm_judgment_reviews/llm_judgment_review_<RUN_ID>_<timestamp>.jsonl`
- `out/llm_judgment_reviews/llm_judgment_review_<RUN_ID>_<timestamp>.md`

패킷에는 원문, 댓글, 모델 최종 판정, reason, risk tags, sample bucket, risk score, worker/run audit 맥락, slang DB 맥락, 전문가 판정 입력란이 들어간다.

## 리뷰 배치 요약 템플릿

```markdown
## YYYY-MM-DD - Qualitative Review Batch

- 관련 run id:
- 대상 범위:
- 샘플링 기준:
- 리뷰어:
- 전체 판정: GO | REVIEW | NO-GO
- 검토 케이스 수:
- ACCEPT:
- HOLD:
- REPROCESS:
- REJECT:
- INFO_MISSING:
- 주요 발견:
- 검색 품질 이슈:
- slang DB 반영 후보:
- 보류 후보:
- 재처리 대상:
- 남은 위험:
- 다음 작업:
```

## 현재 20k Run 적용 상태

- 관련 run id: `20260423_170321_250907`
- 상태: REVIEW
- 이유: 검색 shard 장애가 섞인 baseline이라 단순 랜덤 표본으로는 위험 케이스를 놓칠 수 있음
- 우선 리뷰: 검색 저하 + slang 후보, resolved title 저근거, `unclear_canonical_alias` 차단 후보, non-relevant 경계
- 한계: 현재 checkpoint에는 최종 결과는 충분하지만 raw search snippet, used evidence URL, executed query별 상태가 제한적이다.
- 다음 run 개선: `search_health_flags`, `used_evidence_urls`, `raw/filtered search preview`, `executed_queries`, `degraded_queries`를 checkpoint에 직접 저장한다.
## 2026-05-30 v278 추가 규칙: 최종 후보도 high-risk면 meaning pass를 다시 탄다

- `discourse_semantic_seed_guard`는 검색 전 seed 재독해이고, `final_semantic_reread`는 검색/Decoder 이후 살아남은 final candidate 재독해다.
- `semantic_seed_review.is_specific_work_discussion=false`, `surface_paraphrase_*`, `context_only_no_work_anchor`, `genre_discussion` risk가 있는데 final title이 남으면 원문 title/body/comment와 evidence를 함께 다시 본다.
- `REJECT/HOLD/REPROCESS` 또는 `is_specific_work_discussion=false + Weak/Missing evidence`이면 final title을 null로 낮추고 `final_semantic_reread_rejected_resolution` 또는 `final_semantic_reread_reprocess_resolution`을 남겨야 한다.
- 표현 오타/축약 패턴은 packet-local 자연어 이해 문제이며, 검색 결과가 있더라도 직접 작품 앵커가 없으면 작품명/별칭 evidence가 아니다.
- 원문 직접 title+official evidence, direct image/VLM title promotion처럼 강한 앵커가 있으면 이 final reread gate는 건너뛰어 다른 evidence path를 보존한다.

## 2026-05-30 v285 추가 규칙: no-anchor 문구와 제목 약칭 공식 근거를 분리한다

- `고유 앵커 부족` 문구가 있다고 해서 resolved title을 자동 REJECT하지 않는다.
- 원문 title/body/comment에 제목 약칭 또는 직접 제목 표면이 있고, 공식 상세 URL/search catalog가 final title을 직접 지지하면 title identity evidence는 별도 strong layer로 본다.
- 이 경우 캐릭터/줄거리 앵커 부족은 reason 품질 또는 보조 근거 약점으로 남기되, `reason_says_no_anchor_but_resolved`로 기계적 오분류하지 않는다.
- 반대로 제목 약칭/직접 제목 표면 없이 검색어만 비슷하거나 공식 URL이 없으면 no-anchor resolved 위험으로 계속 리뷰한다.
- 표현 오타/축약 패턴은 여전히 작품 title evidence가 아니라 자연어 meaning pass 대상이다. 제목 약칭 evidence와 오타/감상 surface를 같은 규칙으로 섞지 않는다.

## 2026-05-30 v304 정정: 재해독 표현은 전역 규칙으로 말하지 않는다

- `표현 오타/축약 패턴(범용)` 재해독은 특정 표현을 전역 규칙이나 자동 치환 규칙으로 부르는 방식 자체를 피한다.
- 올바른 계약은 "해당 packet의 title/body/comment/comment_dialogue 안에서만 검토하는 후보 해석"이다.
- 후보 해석은 원문 의도 이해에는 쓸 수 있지만, 다른 post로 재사용하거나 slang alias/search seed/title evidence로 승격하지 않는다.
- 단일 작품 확정은 여전히 direct title/alias, 공식 URL, 작가/회차/고유 설정, `promotion_eligible=true`인 OCR/VLM explicit work title 같은 독립 근거가 필요하다.

## 2026-06-01 v447 추가 규칙: 안정 약칭과 숫자/회차 후보 provenance를 분리한다

- `KNOWN_TITLE_ABBREVIATIONS` hit는 curated alias provenance로 기록하되, LLM 단독 추론이나 검색 snippet self-hit와 섞지 않는다.
- 안정 약칭이 post title/body에 직접 있고, 회차/스포/작가의 말/positive work intent 같은 packet-local work anchor가 있으면 explicit alias support 후보가 될 수 있다.
- semantic no-work 또는 context-only 상태에서는 안정 약칭 표면만으로 final title을 되살리지 않는다. direct post/visual work anchor 또는 contextual work anchor가 필요하다.
- `305호`처럼 숫자/회차/장소/번호로도 읽히는 후보는 안정 약칭 후보와 별도 후보군으로 리뷰한다. 숫자 후보가 검색에서 작품명처럼 보여도 known title abbreviation provenance를 대체하지 않는다.
- result JSON/checkpoint completed row가 없는 canary는 자연어 판단 로그가 있어도 packet-level 품질 승인 근거가 아니다. 먼저 `REPROCESS/runtime-incomplete`로 닫고 새 output으로 재실행한다.

## 2026-06-01 v477 추가 규칙: 등록 약칭은 recall hint이며 미검증 rescue 근거가 아니다

- `KNOWN_ABBREVIATIONS`와 `KNOWN_TITLE_ABBREVIATIONS` hit는 독립 evidence가 아니라 recall/provenance hint다.
- 등록 약칭이 보였다는 사실만으로 LLM의 `비제목/비작품`, `context_only`, `community_banter`, semantic no-work 판단을 뒤집지 않는다.
- final title, `High`, stability/lock, guard exception을 열려면 최소한 visible alias surface와 독립 work anchor가 함께 있어야 한다.
- 독립 work anchor 예시는 공식/detail URL, 검색 결과의 정식 제목 직접 지지, 원문/댓글의 정식 제목 직접 언급, VLM/OCR의 직접 작품명, verified character-work link, 또는 회차/스포/작가의 말/연재/캐릭터 같은 packet-local 작품 토론 맥락이다.
- registry hit, alias 표면 단독, 검색 self-hit, semantic work 분위기 단독은 독립 anchor가 아니다.
- `담텔기`처럼 작품 토론 맥락이 있는 positive canary는 보존하되, `11718080`류 한탄/잡담/context-only 글은 registry/search term이 보여도 title을 되살리지 않는다.
- review packet에는 어떤 registry가 어떤 surface와 어떤 anchor로 쓰였는지 provenance를 분리해 남긴다.

## 2026-06-01 v478 추가 규칙: suspected/best_match/guard exception도 같은 evidence gate를 탄다

- 등록 약칭 evidence gate는 최종 rescue뿐 아니라 suspected title, high-fit interpretation, weak thematic guard exception에도 동일하게 적용한다.
- `_resolved_mappings`에 registry pair가 있더라도 공식 title/url, 공식 source hint, 원문 정식 제목 직접 언급, 공식 검색 blob 같은 독립 anchor가 없으면 suspected title로 올리지 않는다.
- LLM이 `novel_title + context_fit=high`를 반환해도 registry pair만으로 낮은 약칭 정합성 차단을 우회하지 않는다.
- weak thematic/title drift 차단에서 registry pair 자체를 explicit alias support로 보지 않는다. 예외는 snippet/search/post evidence가 alias와 title을 직접 연결할 때만 허용한다.
- 이 규칙은 Decoder 내부 규칙이며, Agentic promotion/stability/lock과 Arbiter guard exception도 같은 원칙으로 후속 정리해야 한다.
