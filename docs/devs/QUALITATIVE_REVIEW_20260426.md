# Qualitative Review - 2026-04-26

대상 run: `20260423_170321_250907`

리뷰 패킷:

- JSONL: `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201809.jsonl`
- Markdown: `out/llm_judgment_reviews/llm_judgment_review_20260423_170321_250907_20260426_201809.md`

## 패킷 구성

- 전체 checkpoint rows: `20,532`
- 리뷰 패킷 선정: `300`
- 주요 risk tags:
  - `search_degraded=267`
  - `search_degraded_majority=258`
  - `relevant_without_official_title=113`
  - `slang_insight=105`
  - `consistency_flag_review=87`
  - `slang_not_stored=70`
  - `unresolved_or_ambiguous_work=69`
  - `resolved_low_anchor=55`
  - `possible_false_negative_anchor=50`
  - `boundary_adjacent_or_meta=44`
  - `possible_false_negative_novel_cue=40`
  - `high_confidence_weak_evidence=40`
  - `multi_work_review=40`

이번 패킷은 정상 대표 샘플이 아니라 위험군 집중 샘플이다. 따라서 전체 run 정확도 추정이 아니라 오류 패턴 발견과 개선 우선순위 도출에 사용한다.

## 샘플 크기 해석

20k 전체 처리 결과에서 300건만 본 것은 최종 품질 승인 기준으로는 부족하다. 이번 300건은 위험군에서 어떤 오류 유형이 반복되는지 찾기 위한 1차 정성 리뷰다.

후속 검토는 다음처럼 확장한다.

- 위험군 집중 샘플을 1,000건 이상으로 확대한다.
- 검색 정상 대조군을 별도로 뽑아 false positive/false negative 기준선을 본다.
- `slang_insight`, `slang_not_stored`, `relevant_without_official_title`, `possible_false_negative_*`, `unresolved_or_ambiguous_work` bucket별 최소 표본을 확보한다.
- 검색 안정화/쿼리 개선 후 같은 post id를 재처리해 개선 전후 판정 변화를 비교한다.
- 이 단계가 끝나기 전까지 20k run은 `REVIEW` 상태로 유지한다.

## 전문가 A - 검색/근거 품질

검토 범위:

- 직접 훑은 표본: 고위험 90건
- 수동 판정 부여: 81건

분포:

- `ACCEPT`: 48건, 약 59%
- `HOLD`: 14건, 약 17%
- `RESEARCH`: 5건, 약 6%
- `REPROCESS`: 9건, 약 11%
- `REJECT`: 5건, 약 6%

판정:

- 검색 저하 flag가 있다고 전부 폐기할 수준은 아니다.
- 원문 직접 약칭, 플랫폼 URL, 댓글 맥락이 같이 있으면 꽤 안정적이다.
- 다만 표본의 약 40%가 `HOLD/RESEARCH/REPROCESS/REJECT`라 자동 품질 승인은 위험하다.

대표 문제:

- 검색 근거 0인데 `resolved_title` 확정:
  - `11628077`: `official_title=중국`, evidence 0. 팬픽/밈을 작품 제목처럼 확정.
  - `11669933`: 중경계/해방상제. 실제 맥락은 있으나 공식 제목 확정 불안정.
  - `11663531`: 공식 제목이 `피마새, 눈마새 재밌나요?`처럼 질문문으로 오염.
- 댓글 URL/추천 댓글을 원글 주제로 과잉 승격:
  - `11718049`: 후타 암타물. 댓글 URL만으로 특정 작품 확정.
  - `11713205`: 역사/대역 설정 불만인데 댓글 문피아 URL로 작품 확정.
  - `11636132`: 장르 클리셰 일반론인데 댓글 URL 예시를 primary로 승격.
- 비웹소설/타매체 수용:
  - `11690864`: 블루 아카이브.
  - `11653795`: Fate/Grand Order.
  - `11718070`: ECT 의료 잡담.
- reason 내부 모순:
  - `11692436`: reason은 제목을 못 찾았다고 하나 최종은 resolved/high.
  - `11561992`: reason은 후보 작품을 말하지만 `official_title`은 빈 값.
  - `11532899`: 괴담텔 약칭이 명확한데 unresolved.

개선 제안:

- `search_snippets=0 AND official_urls=0`이면 직접 title/OCR/platform URL 근거가 없는 한 `resolved_title` 금지.
- 댓글 URL은 원글 주제 식별과 댓글 추천/예시를 분리하고, 후자는 `secondary_reference`로 낮춘다.
- `블아`, `페그오`, 현실 의학/영화/연예인 등 off-domain media gate를 추가한다.
- reason과 최종 필드 불일치 validator를 추가한다.

## 전문가 B - Slang / 커뮤니티 용례 / DB

검토 범위:

- `slang_insight`, `slang_not_stored`, `slang_unclear_canonical_alias` 대상: 105건

대략 분포:

- `confirmed_alias`: 약 52건
- `pending_alias`: 약 19건
- `secondary_reference`: 약 6건
- `comparison_only`: 약 1건
- `noise`: 약 27건

좋은 confirmed alias:

- `즉사무림` -> `즉사기 들고 무림에 떨어지다`: `11718077`, `11718119`, `11718076`, `11705253`
- `괴담텔` -> `괴담 호텔 탈출기`: `11702058`, `11599094`, `11594304`, `11663553`
- `기계공주`, `망겜성`, `담텔기`, `세따먹`, `악영교`, `A헌살`, `가챠펑크`, `기타수기`, `사펑드래곤`, `아카생존`, `눈마새`, `림조`

보류/개선 필요:

- `11718064`: `즉사무림이유백`은 `즉사무림 + 이유백`. 저장 후보는 `즉사무림`.
- `11718075`: 실제 약칭은 `죽깨수`.
- `11679541`: `주여뺏봐볼려는데`는 `주여뺏 + 봐볼려는데`.
- `11663518`: 실제 후보는 `무친년`.
- `11629706`: `괴담텔이 뭔데`는 조사/문장 결합 제거 필요.
- `11600689`: 실제 후보는 `전능뇌`.
- `11708471`: `아생갤 + 엘리` 결합.
- `11653841`: `수선전`/`회선전`/`회귀수선전()` 정규화 흔들림.

noise/오판:

- `11713205`: `대역물`은 장르어.
- `11706848`: `괴이`는 일반 표현 가능성이 큼.
- `11636132`: `히로인들`은 일반어.
- `11714879`: `NTR물`은 장르어.
- `11705268`: `쇼타 나데나데물`은 설명/장르 조각.
- `11690864` `블아`, `11653795` `페그오`는 off-domain alias.
- `11647387`: `천 여명`은 문장 조각.

핵심 리스크:

- `slang_not_stored` 중 상당수는 저장하면 안 되는 노이즈가 아니라, 표면 문자열이 너무 넓게 잡혀 저장 실패한 confirmed/pending alias다.
- `11692432` `겜속바바`는 decoded term과 DB context official title이 충돌한다.
- `11718058` `고향무림`은 DB confirmed와 canonical alias가 흔들린다.
- `11716453` `마학간`은 conflict라 자동 승격보다 수동 확인이 맞다.

개선 제안:

- `detected_term` 전체 phrase와 별도로 `alias_span`을 추출한다.
- 조사/어미/캐릭터 결합 제거 규칙을 추가한다.
- `pending`을 `pending_alias`, `secondary_reference`, `comparison_only`, `genre_or_phrase_noise`, `off_domain_alias`로 쪼갠다.
- 이미 DB confirmed인 alias는 `already_confirmed`로 분리해 risk tag를 낮춘다.
- `family_alias`를 대시보드/API에서 confirmed/pending과 함께 보여준다.

## 전문가 C - Relevance / Discussion Type / Work Resolution

검토 범위:

- 요청 플래그 중심 95건 직접 원문/모델 판정 대조.

분포:

- `ACCEPT`: 32
- `HOLD`: 8
- `RESEARCH`: 25
- `REPROCESS`: 25
- `REJECT`: 5

주요 오분류:

- false negative가 큼. 작품/장르/추천/작가 신작 단서가 있는데 공식 제목 미확정을 이유로 비관련 처리한 케이스 반복.
- 대표 post_id:
  - `11718087`, `11718110`, `11716448`, `11714907`, `11714870`
  - `11718105`, `11718089`, `11716478`, `11718083`, `11716475`
- 특히 `11718105`는 시리즈 작품 목록 OCR과 댓글 작품명이 있는데 `False/noise`라 재처리 대상.

과잉 관련 판정:

- `11718070`: ECT 의료 잡담.
- `11718090`: 일본 멜로영화 추천.
- `11718104`: 여자 연예인 외모 비교.
- `11711635`, `11711604`: reason은 커뮤니티 잡담/비직접 앵커라고 하나 최종은 relevant.

work resolution 문제:

- `multi_work`/`unresolved`가 과하게 쓰임.
- OCR/댓글/검색 근거상 단일 작품이 거의 확정되는 경우에도 `official_title`이 비어 있음.
- 대표 REPROCESS/RESEARCH:
  - `11697263`, `11695614`, `11532899`, `11561992`, `11710036`, `11713225`, `11702086`
- `11695614`는 작가명 `커리우유`를 작품명처럼 다루는 OCR title/author 혼동.

개선 제안:

- `relevant_without_official_title`을 두 유형으로 분리한다:
  - 장르/추천/메타라 제목 불필요
  - 제목을 찾아야 하는데 실패
- `trope_discussion`, `recommendation`, `author_talk`는 공식 제목 없이도 relevant가 될 수 있게 고정 규칙을 둔다.
- `mentioned_works`에 official URL/high confidence가 있으면 primary 후보 승격 검사를 한 번 더 수행한다.
- reason과 최종 필드 불일치가 있으면 REPROCESS 큐로 보낸다.
- `possible_false_negative_*` 중 작품 단서가 있는 것은 재검색 후 재처리 우선.

## 통합 판정

전체 판정: `REVIEW`

이유:

- 검색 shard는 정상화됐지만, 이번 20k run은 장애가 섞인 baseline이다.
- 위험군 정성 리뷰에서 자동 승인하기 어려운 `HOLD/RESEARCH/REPROCESS/REJECT` 비중이 높다.
- slang DB는 오염 차단은 어느 정도 작동하지만 alias span/정규화/분류 문제가 회수율을 낮춘다.
- relevance/work resolution은 false negative와 reason-field 불일치가 개선 우선순위다.

## 우선 개선 TODO

1. `search_snippets=0 AND official_urls=0` 상태에서 resolved_title 승격 제한.
2. 댓글 URL을 primary evidence와 secondary reference로 분리.
3. off-domain media gate 추가 (`블아`, `페그오`, 의료/영화/연예인 등).
4. reason과 최종 필드 불일치 validator 추가.
5. `alias_span` 추출 도입.
6. 조사/어미/캐릭터 결합 제거.
7. pending bucket 세분화.
8. `relevant_without_official_title` 위험군 분리.
9. `mentioned_works` 기반 primary 승격 후처리.
10. 다음 run부터 search evidence 필드 저장 강화.
11. 300건 리뷰를 20k 품질 승인으로 오해하지 않도록 계층 샘플/재처리 비교 리뷰를 추가.
