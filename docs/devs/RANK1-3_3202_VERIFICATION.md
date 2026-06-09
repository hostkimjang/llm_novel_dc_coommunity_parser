# rank1-3 검증 기록 — 3202 슬라이스 근본원인 직격 (precision↔recall)

작성: 2026-06-09 / surface = primary repo / 작업 브랜치 `goal/3202-slice-rank1-3`

이 문서는 `docs/devs/GOAL_PROMPT_rank1-3.md`의 Task C(rank1~3) 구현·검증 자족 기록이다. 상위 계약·전수 분포·백로그는
`docs/devs/HANDOFF_3202_SLICE.md`, 원본은 `out/_handoff_analysis/_synth.json`. 포팅 판단은
`docs/devs/EXPERT_CHAIN_DIFF_PORT_DECISION_3202.md`.

> **과대주장 금지:** 3202는 104k full scan의 **순차 head slice**다. 아래 수치는 discovery + 일반화 gate의 runtime
> 검증 근거이며 **모집단 오류율 / 10만 semantic approval / population approval로 환산하지 않는다.** package build /
> runtime execution은 품질 승인·semantic 승인이 아니다.

## 0. 커밋 (focused, 브랜치 `goal/3202-slice-rank1-3`)
- `99b385f` docs: 3202 인수 계약 + 백로그 + rank1-3 goal (Task A)
- `2830d5b` docs: expert 체인 diff + v740/v741 포팅 판단 (Task B)
- `614a2b8` rank1(precision/원인B): alias/stability lock 승격 앞 음수정합·verifier critical 차단 게이트
- `ddf8820` rank3(precision/원인B): lock을 title_alias 단독 표면일치에서 분리(하드앵커 요구) + displace 보호 + 적대결함 3건
- `c9cef00` rank2(recall/원인A): OCR 카탈로그 상세 official_title_evidence 승격(precision-safe) + 적대결함 5건

## 1. 구현 요약 (전부 hardcode-free 구조 신호로만 동작)
### rank1 (precision / 근본원인 B) — `_abbrev_alias_lock_block_signal`
alias/stability 복구 lock chokepoint(`_resolve_batch_memory_alias_candidate`, `locked=rank>=3`)에서, 승격 전
**음수 정합(decoder best_match `_title_anchor_conflict`/`_abbr_mismatch_downgrade`, 정합 decoder 매칭 rank≥2 부재 &
lexical_overlap<0.45) OR Verifier critical 반론(counter_arguments severity=="critical" & action reject/nullify/downgrade)**
탐지 시 `rank=2`로 한 단계 강등(confidence High→Medium, locked True→False). title은 candidate로 그대로 반환 → resolved 보존.
`matched_url`(official_detail 1차 앵커) 동반 시 면제.

### rank3 (precision / 근본원인 B) — lock 하드앵커 요구 + `_has_image_explicit_title_anchor`
lock 부여를 'title_alias 단독 표면일치'에서 분리: `locked=(rank>=3) and _lock_hard_anchor`, 여기서
`_lock_hard_anchor = matched_url(공식URL) OR 본문 직앵커(_title_mentioned_in_post_main_context) OR OCR 공식표제
(_has_image_explicit_title_anchor) OR 큐레이션 별칭+작품논의 컨텍스트(_has_curated_alias_contextual_work_anchor)`.
하드앵커 부재 시 locked만 False, official_title·confidence·source_tier 보존(recall 손실 0).
**displace 보호:** 신규 `DetectedTitle.resolved_recall_anchor`(게이트 전 lock 가능성)를 남기고 다운스트림
`has_official_candidate`(15791)에 OR로 배선 → lock(precision)과 final-semantic-reread displace 보호(recall)를 분리.

### rank2 (recall / 근본원인 A) — `_has_ocr_catalog_official_title_evidence`
`_has_official_title_evidence`에 OCR 카탈로그 분기 추가(`allow_ocr_catalog` 파라미터로 게이트). 명시 seed 게이트:
기존 이미지 1차 승격 계약(`_has_image_primary_promotion_signal`: promotion_eligible+focus_role+title_role+
explicit_work_title==title) 재사용 + (작가명 라벨 OR 메트릭/시놉시스/플랫폼 강구조신호) 공기 시에만 official 인정.
본문이 플랫폼/연재 메타 OR 커뮤니티 잡담/밈이면 제외. **verifier promotion 게이트 불변:**
`_has_verifier_title_repromotion_veto`는 `allow_ocr_catalog=False`로 호출해 OCR-only가 거부권을 우회 못하게 보존.

## 2. 적대적 검증 (워크플로우 — 독립 다차원 리뷰 → 적대적 반증 → 확정만 수정)
모든 구현을 배포 전 적대적 검증했고, 확정 결함을 전부 수정·회귀테스트화했다.
- **rank1+rank3 리뷰**(5차원·12에이전트): 확정 3건(MAJOR) — 모두 수정.
  1. rank3 unlock이 `has_official_candidate`(15791)를 통해 final-semantic-reread가 정당 resolved title을 **displace**
     → `resolved_recall_anchor` 신호로 lock과 displace 보호 분리(recall 손실 0). load-bearing 회귀테스트 추가.
  2. rank3 하드앵커가 curated 확정 별칭(KNOWN_ABBREVIATION, URL 없음) 정당 lock을 **과대강등**
     → `_has_curated_alias_contextual_work_anchor`를 하드앵커에 추가.
  3. rank1 decoder conflict 판정이 canonical drift 로직의 `lexical_overlap<0.45` 가드 **누락(over-trigger)** → 가드 추가.
- **rank2 리뷰**(4차원·16에이전트): 확정 5건(1 CRITICAL + 4 MAJOR) — 모두 수정.
  1. (CRITICAL) OCR-only가 verifier nullify 거부권 **우회** → `allow_ocr_catalog=False`로 게이트 불변 보존.
  2~5. title_role 미필터·promotion_eligible 미요구·구조마커 남발·meme 가드 약화 → 기존 이미지-승격 계약 재사용 +
     community_meta_banter 제외로 전부 정합화(기존 직접-이미지-제목 경로와 동형의 precision 계약).

## 3. focused unittest (결정적 검증) — `.venv312/Scripts/python.exe -m unittest`
- `tests.test_agentic_pipeline_rank1_lock_block` — 11/11 (헬퍼 신호판정·lexical_overlap 억제·chokepoint 강등/면제·title 보존)
- `tests.test_agentic_pipeline_rank3_lock_anchor` — 11/11 (하드앵커 lock·OCR/URL/curated 보존·**displace load-bearing**·title 보존)
- `tests.test_agentic_pipeline_rank2_ocr_catalog_evidence` — 17/17 (2종 공기·vetting 필수·item_name/community-banter 제외·**veto 불변성**·구조마커)
- 통합 3 rank: **39/39 OK**.
- 회귀: 기존 alias/arbiter/abbrev/final-reread 스위트(`test_agentic_pipeline_alias_contract`,
  `test_agentic_pipeline_search_evidence`, `test_arbiter_curated_alias_guard`, `test_known_title_abbreviation_support`,
  `test_deliberation_curated_alias_guard`, `test_arbiter_memory_query_null_restore_guard`,
  `test_final_semantic_reread_gate`, `test_decoder_known_abbreviation_guard`) — 무신규실패.
  (`test_agentic_pipeline_rework`의 6건 실패는 **base 커밋 f7e18e9에서도 동일** = 사전 실패, 본 변경과 무관 — 격리 검증함.)
- hardcode scan: production 추가분에 post id/제목/별칭 리터럴 0 (테스트 픽스처만 tests/). git diff --check: whitespace 0(CRLF 기록만).

## 4. 대상 모집단 신호 분포 (3202 결과 = before snapshot, 실데이터)
원본 `out/expert_result_20260608_141239_048970.json` (N=3202) 전수 집계:
- 전수: resolved 432 / locked 341 / confidence High 401 / anchor_type title_alias 114.
- **rank1·rank3 대상**: `anchor_type=title_alias & locked & source_tier!=official_detail` = **32건**(전부 confidence High,
  source_tier mixed 31/community 1). 이 32건 reason 분석: **31/32 음수 스코어 컴포넌트 보유, 9/32 critical 마커** →
  근본원인 B(음수 정합·critical 무시한 과대확정 lock) 실데이터 확증. → rank1(음수신호 강등)·rank3(하드앵커 요구)의 대상.
- **rank2 대상**: `title_resolution_state=ocr_explicit_title_unresolved` = **100건**(제목을 OCR로 읽고도 미해소) → rank2 recall 대상.

## 5. before/after 신호 분포 (대표 부분집합 재실행)
입력: rank1/3 대상 32건 ∪ rank2 대상(R2) 100건 = **132건**(3202 슬라이스 내 해당 rank의 전체 대상 모집단, 샘플 아님).
재실행: `expert_main.py out/_rank_rerun/combined_input.jsonl -p 16 --reuse-shards-only --vlm on --ocr on`,
model `bg-digitalservices/Gemma-4-E4B-it-NVFP4`, endpoint `10.20.0.101:8000`, MCP/WARP 16 shard healthy,
effective_parallel = min(132,16,16) = **16**.

> **재실행 LLM 비결정성 주의:** 동일 슬라이스 재실행은 LLM(verifier/decoder/VLM) 출력이 매 run 달라질 수 있어
> before(원본 run)/after(신규 run)는 게이트 효과 + LLM 변동이 섞인다. 게이트의 **결정적 정확성은 §3 unittest**가
> 권위 있는 근거이고, 아래 재실행 분포는 그 보완(end-to-end 무크래시 + 분포 방향 + displace 무손실 경험적 확인)이다.

재실행 완주: my-code(committed rank1+2+3) 132/132, error 0. **rank1 gate 발화 0 / rank3 gate 발화 0**
(신규 run의 main 파이프라인이 이 글들을 batch-alias rescue chokepoint **진입 전에 직접 해소** → 게이트 entry 조건
미충족. 게이트의 결정적 효과는 §3 unittest가 입증; 라이브 재실행은 게이트를 격리하지 못함을 이 0 발화가 보여줌).

**LLM run-to-run 변동 분리(대조군):** 동일 132 입력을 게이트 없는 base 코드(f7e18e9)로도 재실행해(132/132, err 0)
순수 LLM 변동 baseline을 측정했다.

| 집단 | 지표 | BEFORE(원본) | MYCODE(게이트有) | BASECTL(게이트無) |
|---|---|---|---|---|
| rank1/3 32 | resolved | 32 | 20 | 15 |
|            | locked   | 32 | 14 | 10 |
|            | High     | 32 | 17 | 14 |
|            | title 소실/교체(vs before) | — | **12 / 3** | **17 / 1** |
| rank2 R2 100 | resolved | 0 | **47** | 25 |
|              | ocr_explicit_unresolved | 100 | **46** | 66 |
|              | title 소실/교체 | — | **0 / 0** | 0 / 0 |
| combined 132 | resolved | 32 | 67 | 40 |
|              | title 소실/교체 | — | 12 / 3 | 17 / 1 |

해석(과대주장 없이):
- **rank2(recall) 순효과 ≈ +22 resolved** (MYCODE 47 − BASECTL 25), ocr_explicit_unresolved 100→46(BASECTL 66 대비 -20),
  **displace 0**. → OCR 카탈로그 recall이 LLM 변동 baseline 위에 실재 증가를 만들고 title 손실은 없다. precision-safe.
- **rank1/3(precision) recall 손실 0**: 게이트 발화 0인데 32 집단의 title 소실이 MYCODE 12 < BASECTL 17 →
  소실은 전적으로 LLM run-to-run 변동이며, 게이트가 있는 쪽이 오히려 **더 많이 보존**(게이트가 recall을 깎지 않음).
  게이트의 precision 효과(음수신호 강등·하드앵커 없는 lock 해제·title 보존)는 §3 결정적 unittest로 입증(라이브 재실행은 LLM 변동으로 격리 불가).
- **재실행 한계 명시:** 동일 슬라이스 재실행은 verifier/decoder/VLM 출력이 매 run 달라 before/after가 게이트 효과+LLM
  변동의 합이다. 게이트 격리 근거는 unittest이고, 라이브 분포는 (a) end-to-end 무크래시, (b) rank2 recall 방향성,
  (c) displace 무손실(title 소실 0 on R2, 게이트有가 base보다 보존)을 보이는 보완 증거다.
- 산출물: `out/_rank_rerun/combined_before.json`(BEFORE), `final_after.json`(MYCODE), `base132_after.json`(BASECTL),
  `_attribute.py`(분석), `*.stderr.log`(런타임). 입력 `combined_input.jsonl`(132 = 32 ∪ 100).

## 5b. Ground-truth 정확성 검증 (본문+댓글+OCR 정독 + 웹검색 대조)
신호 분포(resolved 수)만으로는 "정답을 찾았는지" 알 수 없으므로, rank2가 **새로 해소한 R2 순증분 28건**에 대해
각 post의 본문+댓글+이미지 OCR을 정독하고 **웹검색으로 실제 작품을 규명**해 파이프라인 해석의 정답 여부를 판정했다
(워크플로우 28에이전트, 웹검색 기반).

판정: correct 10 / correct_work_title_noisy 7(작품 맞고 제목만 OCR 잡음) / wrong_work 2 / garbage_title 2 /
non_work_should_be_unresolved 6 / uncertain 1. → **작품 식별 정답 17/28(61%), 문제 10/28(36%)**.

**귀속(중요):** 문제 10건의 해소 경로를 보면 **6건은 rank2(OCR 카탈로그) 경로가 아님** — title_alias 5건
(URL 'novel.munpia.com', '광고', '림월드'(게임), '욕망의전차'/'빙의 생활로 창작물 속으로' 오매칭) + author 1건('마왕들의 각오').
이는 **title_alias/author 과매칭(기존 버그)**이며 rank2와 무관(원본 3202에도 URL-as-title 3건 전부 title_alias).
rank2(image-OCR) 도메인의 진짜 누출은 ~4건 중 명확한 2건: **'School Days'(일본 미연시 와이푸 밈)·'三才剣法精解'(실존 무공비급)**
— VLM이 비-웹소설 이미지를 표지로 오인했고 rank2가 '작가 OR 구조' 중 작가만으로 통과시킴.

**조치:**
- **rank2 v2 (커밋 616aea7)**: OCR official 인정에 **구조신호(플랫폼/메트릭/시놉시스) 필수화**(작가-only 배제).
  웹확인 정답 카탈로그는 전부 노벨피아/문피아+조회/추천 동반 → 유지, 플랫폼 마커 없는 비-웹소설(School Days/무공비급) → 배제.
  결정적 검증: unittest(작가-only 배제·작품명+구조 인정). rank2 도메인 정답률 추정 ↑(누출 2건 차단, 정답 17건 유지).
- **신규 백로그(다음 세션, rank2 범위 밖)**: ① **title_alias 과매칭** — 'novel.munpia.com'(URL)·게임명·무관작으로
  locked 확정(원본부터 존재, 본 슬라이스 빈도 낮으나 정밀도 영향 큼). official_title이 URL/도메인/플랫폼명 형태면
  거부하는 일반 가드 필요. ② **OCR 제목 토큰 위생**(누출어 '죽 ' 등, 백로그 R6) — 작품은 맞고 제목 문자열만 정정.

> 이 ground-truth는 **표본 spot-check**(rank2 순증분 28)이며 모집단 정답률/semantic approval로 환산하지 않는다(head slice).

## 6. 종료 상태 / 다음 세션
- Task A·B·C(rank1-3) **종료**. HANDOFF 백로그 R1·R2·R3 닫음(HANDOFF 문서에 표시).
- large-scale 진입 조건(HANDOFF 8절 ①②③): 본 작업은 discovery+gate 검증 단계이며 large-scale 미진입(미충족 명시).
- 다음 후보: 백로그 R4~R9(약칭 cardinality 게이트·검색 재시도·OCR 토큰 정합·캘리브레이션 ceiling 등). 다음 입력은
  random baseline 표본 설계(순차 슬라이스와 별도) 또는 다음 head slice.
