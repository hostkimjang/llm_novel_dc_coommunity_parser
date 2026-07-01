# 전수 조사 · 근본원인 · 개선/연구 방향 (run 20260626_000008)

> 작성: 2026-06-26. 대상: 진행 중 런 `expert_result_20260626_000008_928006`의 체크포인트 스냅샷(시점 flushed≈1918, 추출 1934 POST).
> 방법: (1) 결정적 스냅샷 추출 → (2) Claude 워크플로 전수 독립 재판정(앵커링 방지) 577 POST + 오류 후보 적대적 웹검증 → (3) 코드 6갈래 근본원인 추적 + 종합.
> **게이트 분리 준수**: 이 보고는 보조 기준선이다. 동결 gold 게이트도 full-scan approval도 아니다. semantic 품질은 REVIEW-LOCKED, full-scan approval=false 유지.

---

## 0. TL;DR

- **전수 판정 577건 중 파이프라인과 불일치 136건(23.6%).** precision축(resolved 405건) 오류율 **22.0%(89건)**, recall축 표본(164건) recall_miss **28%(46건)**, slang 저장(148건) pollution_risk **5.4%(8건)**.
- **6개 오류 클래스는 별개 버그가 아니라 한 개의 누락된 추상화다**: "표면이 겹치면 결속됐다"(`title_norm in full_norm` 부분문자열)를 결속으로 간주. **맥락 결속(referential grounding) 게이트 부재**. precision 오류 89건 중 **73건이 이 계열**(wrong_work 27 + over_resolved_nonwork 19 + generic_phrase_substring 16 + image 11).
- 모든 승격 경로의 종착점 `candidate_audit.classify_candidate_audit`가 `if title: return "safe_resolved"` — **실존/위생만 검사, 맥락은 안 봄**. FP들이 전부 `safe_resolved + heretic_url=True`로 통과한 이유.
- **자동개선 루프가 회귀를 내는 메타 원인**: (B) 비단조 rescue 결합면이 단일지점 패치를 우회(whack-a-mole) + (C) seed-only 측정이 비-seed 회귀를 정의상 못 봄(`IMP-300` 자백: rank1/2/3 모듈이 focused suite에 없어 loop16 회귀를 놓침).
- **수정 순서: FIX-0(측정 게이트) → FIX-1(공통 work-bridge 술어) → FIX-2~4(표면별 배선).** 모든 가드는 비-LLM(기존 술어 재사용)이라 호출 수 불변 + early-exit로 오히려 효율 개선.

---

## 1. 전수 조사 정량 결과

판정 대상 = resolved 406 ∪ slang-store 148 ∪ recall위험 표본 164 = **578 POST (판정 577, 누락 1)**. 배치 6, 97 judge 에이전트 + 적대검증 29건(세션 한도로 일부 미완).

### 1.1 전체 분포

| judge_label | 건수 | | disagreement_type | 건수 |
|---|---|---|---|---|
| ACCEPT | 437 (75.7%) | | none | 437 |
| REPROCESS | 70 | | under_resolved_false_negative | 48 |
| REJECT | 54 | | wrong_work | 36 |
| HOLD | 16 | | over_resolved | 31 |
| | | | garbage_title | 9 |
| **불일치** | **136 (23.6%)** | | cross_media/famous | 6 / wrong_relevance 6 / 기타 4 |

### 1.2 축별 (precision ↔ recall 양면)

| 축 | 모집단 | 결과 |
|---|---|---|
| **precision** (resolved) | 405 | ACCEPT 313, **오류 89 (22.0%)** |
| **pollution** (slang store) | 148 | ok 140, **pollution_risk 8 (5.4%)** |
| **recall** (unresolved 표본) | 164 | ACCEPT 119, **recall_miss 46 (28%)** |

### 1.3 오류 failure_class 분포 (전체 136)

| failure_class | 건수 | 1차 수정 축 |
|---|---|---|
| recall_miss | 50 | resolution_promotion_gate |
| **wrong_work_among_aliases** | 27 | wrong_work_disambiguation |
| **over_resolved_nonwork** | 19 | relevance_context_gate |
| **generic_phrase_substring** | 16 | resolution_promotion_gate |
| **image_anchor_spurious** | 13 | image_anchor_gate |
| homonym_cross_domain | 4 | relevance_context_gate |
| batch_context_bleed | 4 | batch_context |
| slang_pollution | 1 | slang_store_gate |
| other | 5 | — |

severity: high 90 / med 48 / low 439. recommended_fix_axis: resolution_promotion_gate 69, wrong_work_disambiguation 39, relevance_context_gate 19, image_anchor_gate 8, search_correctness 7, slang_store_gate 4.

> **검증 주의**: 적대적 웹검증은 세션 한도(19:10 리셋)로 29/130여건만 완료. 완료분은 대부분 오류를 **확정**(마파두부/짜장면/로파민/괴담텔/노피아애니 등), 2건 기각(#11663514, #11663521 과민). recall_miss의 `correct_title_hypothesis`는 judge 웹검색 기반 추정이며 적대검증 미완 — 채택 전 별도 확인 권장.

---

## 2. 오류 클래스별 대표 사례 (실증)

### 2.1 맥락 결속 실패 (precision 핵심, 73/89)

**일반어/일반구절이 제목 표면과 겹쳐 과해소** (generic_phrase_substring + over_resolved_nonwork + homonym):

| post | 글 성격 | 오해소 작품 | verify |
|---|---|---|---|
| 11668278 "짜장면에 오이 넣는 집" | 음식 | **짜장면** | 확정 |
| 11718057 "컵라면 이ㅅㄲ 또 딸을" | 잡담 | **컵라면** | — |
| 11668305 "급식때 마파두부 맛집" | 음식 | **Fate/stay night** | 확정 |
| 11673082 "용사파티 << 비겁한 암살단" | 트로프잡담 | **용사 파티** | 확정 |
| 11713222 "현대 하렘물 잘쓰는 작가" | 장르잡담 | 하렘으로 장르를 착각함 | — |
| 11718114 "시스템 딸깍 설정 별로" | 설정불평 | 설정값 딸깍으로 판타지... | — |
| 11700470 "어케 주인공 죄목이" | 잡담 | **가스라이팅** | — |
| 11698904 "타락한 ts녀가 마법소녀 타락" | 트로프 | **타락** | — |
| 11665110 "사이키델리아 읽었던 사람" | 작품(동음) | 낭만적인 초능력을 위하여 | 확정(정답=사이케델리아) |
| 11660254 "노피아 애니메이션은 뭐임?" | 플랫폼메타 | 푸푸푸 랜드의 두가지 일상 | 확정 |

**이미지 앵커 오승격** (현실/공지 OCR → 작품): 11697239 "우우 장붕이"(골수기증) → 조혈모세포 기증 궁금해요, 11697249 "버거피아 합석"→버거피아, 11676314 "마도줍 완결"→소설 속 엑스트라(오답), 11714891 "클릭 잘못했는데"→전생마왕의 합리적인 생존전략.

**BatchContext 번짐** (본문 단서 없는데 이웃 글 별칭으로 해소): 11684371, 11694035, 11698897.

### 2.2 다중 후보 중 오답 선택 (wrong_work, 27건)

부분일치/별칭 충돌로 **틀린 작품** 선택. 정답이 명확:

| post | 오답 | 정답(웹확인) |
|---|---|---|
| 11660262 "로파민 완결났네" | 그렇게, 그 괴물과 두 번 결혼했다 | **로판에 도파민을 풀었다** |
| 11660232 "괴담텔 전개...괴담동 생각나네" | 괴담 동아리(비교대상) | **괴담 호텔 탈출기**(주제) |
| 11666700 "내고향무림 최신화" | 하남자의 탑 공략법 | **내 고향엔 무림인이 산다** |
| 11666699 "남매역전 외전쓰다 짤린거지" | 여동생이 맛있다 | **남매역전** |
| 11682749 "TS주인공 힘 쎄지는 템플릿" | 주인공인데 주인공이 아님 | **묵향(다크레이디)** |
| 11674694 "21세기무림 할매 꼬셔" | 21세기 무림세가 | **21세기무림** |

### 2.3 Recall miss (28%, 양면성)

파이프라인이 official_title='' 로 둔 글에 명확한 약칭 단서가 있음(judge 웹검색 추정): 이티알→이세계 TRPG 게임마스터, 마도서줍→마도서를 줍다, 탑성좌애호→탑의 성좌들이 날 애호한다, 격투천재 재밌다→격투 천재 여고생이 되었다, S급헌터결혼→S급 헌터도 결혼이 하고 싶다 등. **precision 게이트(rank lock) 강화가 정당 약칭까지 억제한 가능성** — FIX와 함께 recall 회귀 모니터 필요.

### 2.4 영구 slang_db 오염 (결정적 감사, 런 간 잔존)

- 작품명 키 545개 중 **~7개 garbage**: `'약칭은 림조 . 2. 줄거리 "내 심마를..."'`(229자), `'하위, 세부 장르 제목과 작품 소개문...3.1.남성향'`(210자, 나무위키 장르 문서 본문), 시놉시스(97/90자), `'회귀수선전/등장인물/수계'`(위키 페이지).
- **family_aliases 일반어 다중매핑**: `마법소녀`→3개 별개작품, `격투천재`→5개 별개작품.
- 한 번 저장되면 이후 런에서 rescue로 재유입 → 코드 개선의 순효과를 가림(회귀의 한 축).

---

## 3. 근본원인 (코드 추적, file:line)

### 핵심결함 A — 맥락 결속 게이트 부재 (전 클래스 관통)

6갈래 추적이 **모두 같은 종착점**을 독립 지목: `candidate_audit.classify_candidate_audit`(candidate_audit.py:2158) → `if title: return "safe_resolved"`. **작품 실존/제목 위생만 검사, "이 글이 그 작품을 논하는가"는 안 봄.** 부분문자열 포함(`X in Y`)이 4개 클래스의 공통 무기:

| 클래스 | 결속 대신 보는 것 | load-bearing primitive |
|---|---|---|
| 과해소 | `title_norm in full_norm` | `_title_directly_in_post`(arbiter.py:8186), `_title_supported_in_text`(7392) |
| 동음이의 | 표면 경계매칭 | `_title_mentioned_in_post_main_context`(33803) |
| slang 오염 | 표면유사 0.45+위생 | `_term_aligns_with_title`(slang_db.py:425) |
| 이미지앵커 | UI/작가토큰 regex | `_infer_vlm_title_role`(agentic_pipeline.py:1308, `if explicit_author: return "work_title"`) |
| 오답선택 | `conf*10+substring보너스` | `_select_decoder_title_candidates`(verifier.py:3270), `_pick_embedded_anchor_token`(decoder.py:8106) |
| 종착(공통) | `official_title+lint` | `classify_candidate_audit`(2158) |

### 핵심결함 B — 비단조 rescue 결합면 + 임계값 게이트 우회

결속 게이트가 일부 있으나 둘 다 무력화: `_apply_hypothesis_guard`(arbiter.py:1475)는 `single_score<=0.78`일 때만 다운시프트(강한 부분일치에 뚫림, trope/genre 전용 가드 없음); `_can_promote_title_after_semantic_no_work`(agentic_pipeline.py:26822)는 상류 `_semantic_seed_no_work_signal`이 없으면 `return True`(no-op). search/alias/BatchContext/slang rescue가 null화 제목을 비단조 복원 → `EXPERT_ORCHESTRATION_LIMITATIONS.md` L20-32 명문화, `LLM_JUDGMENT_REVIEW.md`가 v474~v484에서 동일 원칙 8회 반복 정정 = **단일지점 패치가 다른 rescue 표면으로 우회(whack-a-mole)**.

### 핵심결함 C — seed-only 측정이 회귀를 정의상 못 봄 (자동개선 루프 회귀의 메타 원인)

`build_judge_seed_registry.compare_canary`(597-602)·`run_integrity`(666)는 judge가 플래그한 **seed 포스트만** before/after 비교 = coverage 게이트지 regression 게이트 아님. 패치가 seed 1건 고치며 비-seed N건 깨도 안 잡힘. `IMP-20260623-300`(L42) 자백: *"focused suite did not include rank1/2/3 modules, so the regression was missed."* (= 메모리의 loop16 rank1 회귀). `slang_db.record_result/flush`(857-894) 디스크 영구화 + `session_knowledge` 병렬 의존 → canary 비결정적·full-run 비대표.

---

## 4. 우선순위 Fix 로드맵

순서 원칙: **측정 먼저(C) → 공통 술어(A) → 표면 배선/봉합(B).** 측정 없이는 A·B의 회귀를 검증 불가.

### FIX-0 (선행 필수) — 회귀 측정 게이트 + 동결 골든셋 + 결정적 replay
- `compare_*`에 **non-seed 회귀 축** 추가: 직전 full-run baseline 대비 seed 밖 official_title 변화(resolved→다른title, null→resolved) diff → `collateral_regression_count`. `run_integrity = 'seed coverage AND collateral_delta<=0'`.
- **동결 골든셋**: positive(정답 resolved) + negative(no-work) 동결 집합을 모든 canary에 상시 포함. 1건이라도 회귀 시 FAIL.
- **결정적 replay**: canary는 동결 slang_db 스냅샷(read-only) + 고정 parallel 모드. `record_result` 격리.
- *안전장치*: 단순 변화량 게이트 금지 — baseline diff를 골든셋/판단 정답과 대조해 "정답 방향 변화"는 면제.

### FIX-1 (최고 영향) — 공통 work-bridge 술어 + 모든 승격/복구 진입점 배선
막는 클래스: over_resolved/generic/homonym/image (73/89 precision 오류). 신규 LLM 호출 0.
- 신설 `_post_discusses_work_as_work(ctx, title)`: 약칭사전 일치 ∨ official_detail URL ∨ decoder `anchor_type ∈ {title_mention, character_title_link, plot_mention}` ∨ work_consumption_markers(연재/완결/회차/작가/주인공/플랫폼) 중 하나 필수. 순수 substring(title이 본문 generic phrase의 substring)은 `_is_generic_topic_title` 역방향으로 배제.
- 배선(우회 방지 위해 *모두*): `_apply_hypothesis_guard`(1475, substring-only면 점수 무관 다운시프트), `_title_directly_in_post`/`_title_supported_in_text`(`require_work_context=True` opt-in), `_infer_vlm_title_role`(1308, 작가토큰 단독 불충분→work_surface_score>=3 동반 요구), J10b escape hatch(7738).
- *안전장치*: 토큰경계+고유성 높은 긴 제목 면제, `cover_title` 증거는 work-surface로 인정, FIX-0 골든셋으로 rank1-3 정당해소 보존 확인.

### FIX-2 — 동음이의/타도메인 negative-evidence
`discourse.py` 프롬프트(248-292)에 homonym 지시 + `homonym_collision_with_domain` 신호 필드; `discourse.py:1178-1206` override 가드(타도메인 강신호 시 novel 강제덮어쓰기 금지); `deliberation.py:458-483` `decoder_genre_collision`을 임의 비소설 도메인(food/sport/game/real)으로 확장 + soft 패널티를 하드 보류로 승격.

### FIX-3 (좁고 안전) — slang_db decode-정합 인입 게이트
`slang_db.py:1753-1762` append 직전 `decode_verified is True` 요구(`is_confirmable` 예외); `agentic_pipeline.py:22835-22844` pure_work_alias 자동승격에 `and decode_verified is True`; `_prune_unreviewable_entries`(1361)에 family_aliases evict(decode_verified 한 번도 True 아닌 entry). **`decode_verified`는 실재 필드(models.py:59) — 신규 신호 아닌 미사용 교정이라 저위험.**

### FIX-4 (med confidence) — 랭커에서 정확약칭 vs substring 분리
`verifier.py:3270` 점수식에 정확약칭 +5(`_is_exact_title_alias`/KNOWN_ABBREVIATIONS), substring-only -3(`abbreviation_match_score==0.3`); `decoder.py:8106` 'substring→0.80 강제'를 `_has_explicit_alias_signal` True일 때만; 동률 tiebreaker로 본문 고유 캐릭터/작가/플랫폼 증거 우선. FIX-3(사전 정화) 선행 권장.

---

## 5. 파이프라인 처리 효율

- **현 병목**: ~7분/POST/워커(16워커). 로그상 POST당 snippet_analyzer/gatekeeper/discourse/verifier(47s)/arbiter(49s) 다수 expert 직렬 스트리밍. 전체 104,502건이면 현 속도로 ~34일.
- **비-LLM 가드**: FIX-1~2의 모든 work-bridge 술어가 기존 string/regex(`_is_structural_nonwork_title`, `work_consumption_markers` 등) 재사용 → 호출 수 불변.
- **early-exit 재배치**: 현재 `classify_candidate_audit`(safe_resolved)가 가장 늦게 가장 약한 검사. work-bridge 사전필터를 **승격 진입점 앞으로** 당기면(이미지의 `_collect_direct_image_titles` 1451이 모범) 명백한 비결속(substring-only + 도메인명사 + work-surface 부재)을 decoder/verifier LLM 호출 *전*에 컷 → 동음이의/일반구절의 비싼 LLM 왕복 절약.
- **상태/캐시**: canary용 동결 slang_db read-only(비결정성 제거), `abbreviation_match_score` 등 순수함수 메모이즈.

---

## 6. 연구 방안 (가능성 높은 순)

- **R1 맥락 결속 일반 술어화 [최우선]**: "표면 겹침=결속" 거짓 등식을 검증 신호의 분리합으로 대체. **substring 위험도 스펙트럼 학습** — 제목 길이/고유성(엔트로피)/토큰경계/도메인명사 동반을 feature로 점수화(짧고 흔한 "고능아/프로모션/짜장면"=고위험, 길고 고유=저위험). 4개 클래스가 단일 술어로 수렴하는지 실증.
- **R2 동음이의 판별**: 닫힌 하드코딩 사전(`_is_generic_topic_title`)을 본문 도메인 분류 + 제목-도메인 충돌 검출로 일반화. 도메인 분류기 false-negative(작품명 표면에 끌린 novel 오태깅)가 병목.
- **R3 slang_db 정화·버저닝**: `decode_verified` 신뢰도 실측(false-negative율)으로 인입 예외 폭 캘리브레이션. 오염 alias를 evict가 아닌 **quarantine + 버저닝**(decode_verified 이력/source 기록)으로 재유입 차단(`title_resolution_allowed=false` 동반).
- **R4 회귀안전 루프**: 공유 게이트(`_has_alias_title_support` 30+ 호출부) 의미론 전파를 정적 지도화(loop16류 의미충돌 방지), 같은 입력신호를 소비하는 게이트가 1곳뿐임을 계약 테스트로 고정, `LLM_JUDGMENT_REVIEW` v474~v484 반복 정정을 데이터로 whack-a-mole 재발률 추적.

---

## 7. 방법론·재현

- 스냅샷 추출: `scratchpad/extract_snapshot.py`(checkpoint.jsonl 안전 읽기), 배치: `build_batches.py`(§2.3 projection), 판정 워크플로: `survey.workflow.js`(97 judge+verify), 근본원인: `rootcause.workflow.js`(7 trace+synth), 집계: `aggregate.py`.
- 한계: (1) 진행 중 런의 1934 POST 슬라이스(전체 104k 아님) — 오류 *클래스*는 동일하나 *비율*은 full-run 재집계 권장. (2) 적대검증 29/130여건만 완료(세션 한도) — REJECT/high는 신뢰, recall_miss 정답추정은 미확정. (3) judge는 Claude Opus, 운영 파이프라인은 vLLM Gemma-4-26B-A4B — 판정 분포는 보조 기준선.
