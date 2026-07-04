# 아키텍처 전반 진단 + 유사 분야 사례연구 (2026-07-04)

> 목적: 현 파이프라인 아키텍처(특히 "작품으로 해소할지 말지" = 판단유무 결정)가 원리적인지 진단하고, 추가/개선할 수밖에 없는 것을 확정하며, 이런 류 프로젝트(Entity Linking/Resolution + NIL abstention + 학습형 alias + RAG grounding + LLM-judge + 회귀안전 self-improvement)가 학계·산업에서 어떻게 되어 있는지 사례연구로 대조한다.
> 방법: 내부 코드 진단 2 + 외부 웹 사례연구 4 병렬 + 종합(에이전트 7). 코드 근거는 file:line, 외부는 논문/시스템+URL.
> 관련: [[detection-survey-20260626-rootcause]] 단일 근본원인("표면 겹침=결속") · [[codex-loop-midcheck-20260701]] 개선루프 상태.

---

## 0. TL;DR

- **판단유무(resolve/abstain) 결정 레이어는 원리적이지 않다.** 최종 게이트 `can_publish_title`(promotion_gate.py:166-223)는 캘리브레이션된 확률 판정이 아니라 **veto 누산 캐스케이드**(불리언 `row_discusses_work` + enum `scope_kind` + reason-code 집합 교집합). **"이 글이 후보 C를 작품으로 논한다"는 확률이 시스템에 단 하나도 없다.** `confidence`는 `scope_kind`에서 파생된 라벨(가짜)이고 게이트가 참조조차 안 한다.
- **이 결정 결함이 비용·harness 실패의 상류 원인이다.** 결정을 소비할 값싼 게이트가 없으니 모든 post가 7-expert 풀 캐스케이드(~7분)를 통과 → 104k 전수 ~2주 → collateral 게이트 루프당 실행 불가 → 405+ 루프가 단건 replay로 퇴화 = goal이 없애려던 seed-only 측정으로 회귀. **Q1(비용)·Q3(harness)은 Q0(결정 부재)의 하류.**
- **답은 백지 재작성이 아니라 결정 재정식화(reformulation):** referential grounding을 **캘리브레이션된 확률 + selective prediction(NIL 1급)** 으로 바꾸면 비용이 난이도에 비례 배분되고, harness가 실행 가능해지며, whack-a-mole이 축 단위 개선으로 바뀐다.
- **분야 표준이 정확히 이 답을 지지한다:** BLINK(candidate-conditioned scoring, 표면겹침은 recall 신호일 뿐), Self-RAG(관련≠groundedness), Learn-to-Not-Link(NIL 1급·학습셋 필수), Conformal abstention(오류율 ε 보증), PoLL(disjoint judge 패널), Sculley CACE·Shumailov model collapse(slang_db 자기오염 위험).

---

## 1. 내부 진단 — 판단유무 설계는 원리적인가: **아니오(partly_principled)**

### 1.1 결정 경로의 실체 (코드)
- 최종 게이트 `can_publish_title`(promotion_gate.py:166-223): `publish_allowed = (status=="publish")`. 결정 신호 = (a) 불리언 `row_discusses_work_as_work`, (b) 불리언 `official_title_exists`, (c) enum `scope_kind`, (d) `BLOCKING_REASON_CODES.intersection`(:193) — **전부 범주형**.
- 상류 `_record_resolved_public_title_gate_decision`/`_can_promote_title_after_semantic_no_work`(agentic_pipeline.py:33498-34177)가 `scope_block_flags`(차단 사유 코드 리스트)를 손으로 쌓고 `scope_kind = "context_only" if flags else "current_work"`, `supports_publish = not flags`로 환원 = **"차단 플래그 하나라도 있으면 유보"라는 veto 누산**.
- `row_discusses_work` 자체는 `_post_discusses_work_as_work`(30858-30964)의 bridge_source별 sub-predicate **거대 OR**(strict_direct_work_anchor / known_title_abbreviation / verified_alias_official_detail_anchor / batch_memory_exact_alias_rescued …).
- 유일 연속 점수(arbiter `_build_hypothesis_scores` 1228+, 손튜닝 상수 0.08/0.14/0.36)는 magic threshold(margin≥0.18, single≤0.78)로 잘려 `is_relevant` **라벨만** 하향 → **publish 게이트와 분리된 죽은 신호**.
- `classify_candidate_audit`(candidate_audit.py:4560-4594)는 결정자가 아닌 **라벨 투영기**. `promotion_decision`이 없으면 여전히 **`if title: return safe_resolved`(4578-4579) fallback** 잔존(거짓 기본값이 제거된 게 아니라 앞단 게이트가 있을 때만 우회).

### 1.2 세 가지 원리적 결함
1. **selective prediction이 아니다** — 목표 precision을 맞추는 임계(Chow's rule)·risk-coverage 곡선·calibration 부재. golden18 pass/fail 스냅샷만 있고 coverage↔risk 트레이드오프 측정 없음.
2. **NIL이 1급 예측이 아니라 승격 실패의 잔여물** — `PromotionDecision.status`에서 "작품 없음 확신"과 "불확실 유보"가 `candidate_only` 한 버킷으로 붕괴. `_state_reason_codes`가 유보를 결핍(`row_discussion_missing`)으로 프레이밍. (단 `title_resolution_state`에 `nonwork`/`context_only`/`unresolvable_memory_query`가 이미 1급으로 존재 — models.py:115-126, 배선만 필요.)
3. **결정 권한이 불변·단일이 아니다** — rescue가 결합면을 넘나듦(`candidate_audit.py:2819-2863` post-gate publish flip, expert_main 최종 ledger 재수렴 Loop389/390), 하류가 `promotion_decision` 변조. **감사 가능한 단일 진실원 없음.** ARCHITECTURE_PROMOTION_GATE_MIGRATION.md의 Loop179~409 전체가 "rescue 누출→차단 플래그 추가"의 두더지잡기 로그 = 결합면 투과성의 직접 증거.

### 1.3 앙상블 비용 + harness
- 7-expert 직렬(gatekeeper→discourse→검색+page-analyzer→agentic loop(decoder/verifier/critic, 3-5회)→synthesizer→arbiter/deliberation). Deliberation 최악 = 1+3(jury)+3(debate). post당 **12-20회 직렬 LLM 생성** → ~7분/post. cheap-first 재료(EvidenceScorer=결정적 0-LLM)가 Phase4 내부에만 갇혀 전역 triage에 안 쓰임.
- slang_db: 표면 필터 휴리스틱만, **버저닝/스냅샷/롤백/provenance/decay 부재**, `flush_posts=1` 즉시 영속화 + 자기학습 write-back = feedback-loop 오염 노출.
- harness 설계(단일 술어·3중 회귀축·blind judge·frozen canary)는 **교과서적으로 견고하나 경제성이 깨져** collateral 게이트가 실행 불가.

---

## 2. 분야 표준 대비 격차

| 축 | 이 프로젝트 현재 | 분야 표준 (사례) | 격차 |
|---|---|---|---|
| 단계 분리 | recall 신호(부분문자열)를 precision 결정에 직결, rescue가 다층 침범 | candidate gen(recall)→ranking(precision)→NIL 3단 엄격 분리 (**BLINK, Magellan/Papadakis blocking**) | 결합면 투과, 게이트가 retroactive veto 층 |
| 결속 판정 | 표면 부분문자열=결속 (`if title→safe_resolved`) | "멘션 문맥↔엔티티 설명" 조건화 semantic 점수 (**BLINK cross-encoder, ReFinED**), IsSUP=NLI-entailment (**Self-RAG, RAGAS**) | 근거가 표준과 정반대 |
| 판단유보(NIL) | 승격 실패 부산물, `candidate_only` 단일 버킷 | NIL 1급 클래스, Missing vs Non-Entity 2분류, 학습셋 필수 (**Learn to Not Link/CLINK**) | 예측 대상 아님 |
| 임계 설정 | magic threshold(0.18/0.78) 손튜닝 | τ 학습·calibrate, split conformal ε 보증 (**Conformal LM**) | 임의적·통계보증 없음 |
| 신뢰도 | confidence=가짜 라벨, ECE 미측정 | Temperature Scaling/토큰확률 가중 (**G-Eval, LLM-EM calibration**) | 캘리브레이션 자료 없음 |
| 비용 배분 | 전 post 동일 캐스케이드(~7분) | 값싼 blocker→비싼 matcher는 생존자만, 모호대역만 재검색 (**BLINK 2단, CRAG/SURE-RAG**), conformal early-exit | 전역 triage·early-exit 부재 |
| 결정 권한 | 다중 write, post-gate flip, ledger 재수렴 | 캐노니컬 ID + write-once audit + 전역 Select (**OpenSanctions, ComEM Select**) | 단일 진실원 없음 |
| alias/피드백루프 | 표면 필터만, 버저닝/provenance/decay 없음, 즉시 write-back | provenance 계층·신뢰 가중·붕괴방지 reset (**OpenSanctions, Shumailov, Data Cascades**) | 구조적 안전장치 없음 |
| 평가/회귀 | pass/fail 스냅샷(golden18 과소·노후), 단건 replay | risk-coverage/AURC + 슬라이스 + 행동 MFT/INV/DIR + 동적셋 (**El-Yaniv, CheckList, Dynabench**) | coverage-risk·행동셋 전무 |
| LLM-judge | 단일 저지 경향, decoder=judge 오염, hard label | disjoint 패널 다수결, human κ 선검증 (**PoLL/RoPoLL, G-Eval**) | 패널·편향완화·meta-eval 미비 |
| 결정성 | replay flip_rate 0.4, jury/debate가 분산 덧댐 | greedy(temp=0)+seed+캐시 | 비결정성이 golden verdict까지 누출 |

---

## 3. 추가/개선할 수밖에 없는 것 (우선순위)

### P0 — 결정을 캘리브레이션된 selective prediction으로 재정식화 (유일한 지렛대)
`can_publish_title`의 불리언 veto 캐스케이드를 **`p(discusses_as_work | post, C)` 하나로 대체.** `_post_discusses_work_as_work`(sub-predicate OR)를 강한 결정적/retrieval-scored 스코어러로 재구현, LLM/MCP 검색은 feature(anchor/alias/작품 설명·시놉시스·타입)만 공급. `scope_block_flags`/reason-code는 이 확률의 feature로 강등. 게이트는 posterior 임계. 〔BLINK, Self-RAG IsSUP, RAGAS, El-Yaniv risk-coverage, Chow〕

### P0 — NIL을 1급 예측 클래스로 (2유형)
`resolve(C) / abstain-uncertain / assert-NIL` **3-way 헤드** + 각 캘리브레이션 신뢰도. NIL 2유형 = (a) Non-referential(작품 실존하나 "작품으로서" 안 논함), (b) Missing/wrong entity. `candidate_ledger_status`·`PromotionDecision.status`에 **positive `confident_nil` 추가**, `title_resolution_state`의 `nonwork`/`context_only`를 결정 outcome까지 배선(절반 이미 존재). golden에 두 NIL 유형 라벨링. 〔Learn to Not Link 핵심: 학습셋에 NIL 예시 없으면 abstain 붕괴〕

### P1 — 2단 캐스케이드 + selective compute (비용을 난이도에 비례)
EvidenceScorer(결정적 0-LLM)+후보 retrieval을 **전역 triage 게이트로 승격.** high-confidence-exact 즉시 resolve, 명백 noise/no-work 즉시 abstain(expert 생략). 7-expert deliberation은 진짜 모호한 ~15-20%에만. **자릿수 비용절감이 collateral/golden 게이트를 실행 가능하게 만들어 harness 결함 C 봉합.** 〔BLINK 2단, ER blocking, CRAG 3-way, Conformal stopping〕

### P1 — 단일 권위 결정점 + write-once 결정 계약
모든 rescue(official_url_recoverable, batch/title_led alias, expert_main 재수렴)를 게이트 **이전** evidence 주입으로만. 게이트 **이후** 변조(candidate_audit:2819 flip, ledger 재수렴) 제거. `promotion_decision` write-once. "결측≠차이" — 맥락 근거 부재를 매칭 근거로 쓰지 말고 **긍정적 referential 근거 요구**(최근 'Guard body-verified work from stale alias publish' 커밋과 정합). 〔Sculley CACE, OpenSanctions, ComEM Select〕

### P1 — 결정성 + 측정을 coverage-risk로
judge/canary replay에 temp=0(greedy)+고정 seed, expert 출력을 `(post_id,model,prompt-hash)` 캐시 → 진짜 결정적 replay(flip을 jury/debate로 가리지 말고 소스 제거). golden을 **calibration set**으로 split conformal → "오승격율 ≤ ε" 보증. 개선루프 지표를 golden18 N/18 대신 **risk-coverage/precision@coverage/ECE**. 〔conformal abstention, G-Eval, AURC/ECE〕

### P2 — slang_db 구조적 재설계 (자기오염·model collapse 방지)
**append-only event log + materialized view**(버저닝/스냅샷/롤백), **provenance 계층 격리**(self_inferred/url_verified/cross_run_independent/human), slang 승격을 1런 `is_confirmable`가 아니라 **독립·다중런 증거**에서만. `flush_posts=1` → 지연 flush staging + TTL/confidence decay + **DB write가 golden/panel 행을 뒤집으면 차단하는 shadow-diff 게이트**. 프로덕션도 canary와 동일 frozen-then-review. 〔Shumailov model collapse, Data Cascades, OpenSanctions provenance, gazetteer noise-filter〕

### P2 — harness 경제성 + 회귀셋 대표성
104k 전수 collateral → **6개 오류클래스+rank1/2/3+recall alias 덮는 동결·층화·검정력 있는 회귀 패널(1-2k).** baseline expert 출력 캐싱으로 **변경경로 post만 재실행(incremental collateral)**. golden 18→수백 + 주기 refresh. 저지 불일치 23.6% 마이닝→새 golden. full_post_judge를 **disjoint 패널(PoLL)**(decoder≠judge, 순서 스왑), human κ 선검증으로 "저지 오류 vs 파이프라인 오류" 분리. **수렴/정지 메타게이트**(N루프 무개선 자동정지). 〔CheckList, Dynabench, Overton, PoLL〕

### P0-선결 — retrieval substrate health 게이트
검색 P0 flaky(Docker/WSL portproxy)에서 "search-blind conditional"로 진행 금지 — health 게이트가 루프를 **실패**시키게. 증거층이 flaky하면 파이프라인과 blind judge가 동시에 부당. 〔When Not to Trust LMs〕

---

## 4. 근본 재설계 옵션 + 권고

**권고: 하이브리드 — B(retrieval+rerank+calibrated-abstain)를 기본 척추로, A(7-expert 앙상블)를 모호대역 에스컬레이션 계층으로.**

- 근본원인이 "결정적 grounding 게이트 부재"이지 LLM 역량 부족이 아니므로 정답은 확률 앙상블이 아니라 **결정적/캘리브레이션 게이트**(B)에 있다.
- 앙상블은 버리지 말고 **"상시 직렬 융합"에서 "모호대역 조건부 uncertainty 신호원"으로 강등** — expert 불일치(semantic dispersion)가 conformal abstention/PoLL식 **캘리브레이션 feature**가 된다(직렬 융합보다 가치↑). = BLINK 2단 + CRAG 3-way + conformal early-exit.
- **매핑:** decoder=Match, arbiter/deliberation=Compare/Select, synthesizer=cluster/canonicalize로 형식화하되 **생존 후보에만** 적용.

---

## 5. 사례연구 (분야별 핵심 + 출처)

### Entity Linking / NED / NIL
- **BLINK** (Wu et al., EMNLP 2020, Facebook) — bi-encoder 후보생성 + cross-encoder 재랭킹, 점수는 항상 "멘션 문맥↔엔티티 설명" 조건화. 표면 겹침은 recall 신호일 뿐. https://arxiv.org/abs/1911.03814 · https://github.com/facebookresearch/BLINK
- **Zero-Shot EL / ZESHEL** (Logeswaran et al., ACL 2019) — 엔티티를 텍스트 설명만으로 독해 해소, 도메인이동 DAP. https://arxiv.org/abs/1906.07348
- **GENRE/mGENRE** (De Cao et al., ICLR 2021) — autoregressive EL(엔티티명 생성). **ReFinED** (Ayoola et al., NAACL 2022) — 타입+설명 활용 효율 EL.
- **Learn to Not Link / CLINK** — NIL을 Missing Entity vs Non-Entity Phrase 2유형 1급 모델링. 교훈: **학습/golden에 NIL 예시 없으면 abstain 붕괴.**

### Entity Resolution / Record Linkage / Matching
- **Ditto** (Li et al., VLDB 2020) — EM을 sequence-pair classification(BERT), 도메인지식 span 태깅 + TF-IDF 요약 + augmentation. https://arxiv.org/abs/2004.00584 · https://github.com/megagonlabs/ditto
- **DeepMatcher** (SIGMOD 2018), **Magellan** (VLDB 2016) — blocking→matching→label→debug end-to-end.
- **Papadakis blocking survey** (2020) — inverted index + char n-gram(철자변형) + meta-blocking + DeepBlocker(dense ANN/LSH). recall을 precision과 분리 측정. https://arxiv.org/abs/1905.06167
- **ComEM "Match, Compare, or Select?"** — 독립 이진판정보다 **Select(전역 일관성 후보 선택)**가 최고. **OpenSanctions** — precision 우선 비대칭 threshold, "결측≠차이", 캐노니컬 audit trail.

### RAG grounding / abstention / selective prediction
- **Self-RAG** (Asai et al., 2023) — reflection token: IsREL(관련)≠IsSUP(groundedness)≠IsUSE. https://arxiv.org/abs/2310.11511
- **CRAG** (Yan et al., 2024) — retrieval evaluator가 Correct/Ambiguous/Incorrect 3-way, Incorrect면 웹폴백. https://arxiv.org/abs/2401.15884
- **FLARE** (Jiang et al., EMNLP 2023) — 토큰확률<θ면 능동 재검색. https://arxiv.org/abs/2305.06983
- **Conformal abstention / selective classification** (El-Yaniv risk-coverage, Chow's rule, split conformal) — 오류율 ε 분포무관 보증. **When Not to Trust LMs / PopQA** (Mallen et al., 2023) — 롱테일은 검색 필수. https://arxiv.org/abs/2212.10511

### LLM-as-judge / KB-drift / CACE
- **MT-Bench / Chatbot Arena** (Zheng et al., NeurIPS 2023) — position/verbosity/self-enhancement bias 체계화 + position-swap 완화. https://arxiv.org/abs/2306.05685
- **PoLL (Panel of LLM evaluators)** (Verga et al., 2024) — disjoint 모델 패밀리 배심원 다수결로 self-preference 제거(단일 큰 저지보다 저비용). **G-Eval** (Liu et al., EMNLP 2023) — rubric+CoT+토큰확률 가중 연속점수. **RAGAS** — reference-free faithfulness.
- **Model collapse** (Shumailov et al., Nature 2024) — 생성물 재학습 시 분포 꼬리 소실·비가역 붕괴 → slang_db self write-back 직접 위험. https://www.nature.com/articles/s41586-024-07566-y
- **ML 기술부채/CACE** (Sculley et al., NeurIPS 2015) — Changing Anything Changes Everything, 다중 expert+공유 slang_db entanglement = whack-a-mole 구조적 원인. **Data Cascades** (Sambasivan et al., CHI 2021). **CheckList** (Ribeiro et al., ACL 2020, MFT/INV/DIR 행동테스트), **Dynabench**(동적 적대셋).

---

## 6. 지금 잘 가고 있는 점 (버리지 말 것)

1. **근본원인 진단 자체가 정확·희귀** — "표면 겹침=결속" 거짓 기본값을 스스로 찾음. 대부분 팀은 여기 못 온다.
2. **올바른 아키텍처의 재료가 이미 존재** — EvidenceScorer(결정적 0-LLM), retrieval/MCP substrate, conflict-gating, short_post_fast_path = BLINK/CRAG 조각들. **재작성이 아니라 재배선.**
3. **harness 설계는 교과서적으로 견고** — 단일 공유술어, 3중 회귀축, blind judge, 결정적 replay, frozen+off canary. 설계는 옳고 경제성만 깨짐(P1이 되살림).
4. **NIL 원시타입 절반 이미 존재** — `title_resolution_state`의 `nonwork`/`context_only`, 결정 outcome까지 배선만.
5. **최근 커밋 방향이 표준과 정합** — 'Constrain title-only restore to URL-backed support'(독립 corroboration), 'Guard body-verified work from stale alias publish'(전역 일관성), 'Suppress degraded-zero search probes'(검색위생). 전부 EL/ER/RAG가 지지하는 positive-evidence·provenance 방향. **계속 가라.**
6. **slang_db 위생 본능은 옳다** — 필터를 더 쌓지 말고 **구조(버저닝/provenance/decay/shadow-diff)로 승격.**
