# 로컬 LLM 커뮤니티·웹소설 grounding 벤치마크 연구

작성일: 2026-09-01 KST

대상: 로컬/self-hosted LLM 기반 커뮤니티 게시글 정제·수집·웹소설 작품/약칭/주작품 판정 파이프라인

## 결론

벤치마킹할 공개 자원은 있다. 다만 **이 파이프라인을 한 번에 평가하는 단일 공개 벤치마크는 없다.** 가장 타당한 구성은 다음 3층이다.

1. `MTEB(kor, v2)·MIRACL-ko·NoMIRACL-ko·KLUE`로 한국어 검색·관련성·NER/RE의 외부 smoke benchmark를 수행한다.
2. 저장소 전용 gold에서 `canonical work ID`, alias relation, `primary/mentioned/comparison`, 공식/커뮤니티/경쟁 작품 근거를 따로 라벨링해 후보 회수와 오작품 판정을 분리한다.
3. 이미 구현된 candidate recall, top-label/NIL, Brier/log-loss/ECE, risk-coverage/AURC, paired cluster bootstrap을 `FROZEN_ACTUAL` 자료로 실제화하고 end-to-end unsafe publish를 별도 hard gate로 둔다.

지금 가장 큰 공백은 평가 공식을 새로 만드는 일이 아니다. **실제 DEV/CALIBRATION/FROZEN 정답 자료와 producer `COMPLETE` 증거가 없는 것**이다. Golden18은 actual ready `0/18`이라 정확도 지표가 `null`이고, 최신 고위험 32행은 회귀 challenge 신호일 뿐 모집단 정확도가 아니다.

따라서 권고 순서는 `도메인 gold 구축 → 후보 회수 측정 → role-aware reranking → calibrated abstention → 동일 frozen A/B`다. 프롬프트나 모델부터 바꾸면 어느 단계가 정답을 잃었는지 계속 알 수 없다.

## 현재 결과를 새 기준으로 다시 읽기

최신 실제 기준선은 2026-07-23의 `unsloth/gemma-4-26B-A4B-it-NVFP4`, requested/effective parallel `16/16`, dashboard ON인 v7 qualified run이다. 이번 연구에서는 이 결과를 재판독했고 새 모델 run은 실행하지 않았다.

비율의 95% 구간은 [NIST가 설명하는 Wilson 방식](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm)으로 계산했다. 3회 반복 출력은 독립 96행으로 부풀리지 않고 게시글을 표본 단위로 사용했다.

| 지표 | 현재 관측 | 95% Wilson 구간 | 판정 |
| --- | ---: | ---: | --- |
| 고위험 의미 compliance | `18/32 = 56.25%` | `39.33%–71.83%` | `NO-GO`; 모집단 정확도 아님 |
| correct-title recovery | `1/11 = 9.09%` | `1.62%–37.74%` | 회수 병목 |
| review-router recall | `43/66 = 65.15%` | `53.11%–75.52%` | 고위험 누락 큼 |
| HOLD integrity | `4/5 = 80%` | `37.55%–96.38%` | 분모 부족, conflict 실패 지속 |
| unsafe publish any-run | `1/32 = 3.13%` | `0.55%–15.74%` | 자동 공개 안전성 입증 불가 |
| candidate recall/calibration | `null / NOT_EVALUABLE` | 해당 없음 | actual gold·COMPLETE producer 없음 |

핵심 해석은 다음과 같다.

- `18/32`는 낮을 뿐 아니라 구간도 넓다. 전체 운영 정확도로 일반화할 수 없다.
- `1/11`은 “검색이 못 찾았는지, 후보는 찾았지만 reranker/router가 버렸는지”가 분해되지 않았다.
- unsafe가 1건 남아 있으므로 threshold를 완화해 회수율만 높이는 방식은 위험하다.
- 현재 P3 계약은 candidate recall, top-label/NIL, Brier/log-loss/ECE, risk-coverage/AURC와 CI를 이미 구현했다. 실제 라벨 자료를 결속하지 못해 숫자를 만들지 않는 것이 올바른 fail-close다.

현재 운영 판정은 그대로 `SHADOW_READY / PRODUCTION_NOT_READY`, `full_scan_approval=false`다.

## 공개 벤치마크 중 실제로 쓸 만한 것

| 자원 | 이 저장소에서의 용도 | 주 지표 | 직접 쓸 수 없는 부분 |
| --- | --- | --- | --- |
| [MTEB Korean v2](https://docs.mteb.org/overview/available_benchmarks/) | 한국어 embedding/retriever 사전 선별 | retrieval `nDCG@10`, Recall 계열 | 웹소설 작품 linking end-to-end 점수가 아님 |
| [MIRACL-ko](https://github.com/project-miracl/miracl) | 한국어 BM25/dense/hybrid/reranker smoke | `nDCG@10`, `Recall@k` | Wikipedia 질의·문단이며 커뮤니티 약칭이 아님 |
| [NoMIRACL-ko](https://github.com/project-miracl/nomiracl) | 근거 없음 감지와 보류 능력 | hallucination rate, relevant error rate | 작품 ID·주작품 관계를 평가하지 않음 |
| [KLUE NER/RE](https://openreview.net/forum?id=q-8h8-LZiUm) | 한국어 span·relation encoder smoke와 주석 설계 참고 | entity F1, RE F1/AUPRC | 작품명·alias/오마주/경쟁 관계 ontology 없음 |
| [국립국어원 개체명/개체 연결 말뭉치](https://kli.korean.go.kr/corpus/openapi/corpusList.do?lang=en) | 한국어 온라인 문체·EL 사전학습/진단 | span/link 성능 | Wikipedia 중심, 신청·재배포 제한, 플랫폼 work ID 불일치 |
| [BEIR](https://openreview.net/forum?id=wCu6T5xFjeJ) | BM25·dense·reranking 비교 틀과 qrels 형식 | `nDCG@10`, `Recall@100` | 주로 영어·정적 corpus, 도메인 승인 불가 |
| [KILT](https://aclanthology.org/2021.naacl-main.200/) | 정답과 provenance를 함께 채점하는 구조 | downstream+provenance | Wikipedia snapshot 중심 |
| [BLINK](https://aclanthology.org/2020.emnlp-main.519/) | 후보 회수와 cross-encoder disambiguation의 2단 baseline | candidate recall, linking accuracy | 명시 mention/KB 설명을 전제 |

공개 benchmark의 역할은 **모델·검색기 사전 선별과 구현 smoke**다. production 승인 정답은 반드시 저장소 전용 gold에서 나온다. 공개셋 점수가 좋아도 `아생갤`, 동명작, 같은 작가 타작, 댓글 추천작, 비교작을 주작품으로 오인하는 문제를 입증하지 못한다.

## 권장 3층 benchmark

### 1층 — 외부 smoke

- BM25, Korean dense retriever, `BM25 ∪ dense`, RRF, reranker를 동일 MIRACL-ko/MTEB retrieval task에서 비교한다.
- BEIR 연구는 BM25가 강한 zero-shot 기준선이고 reranking/late interaction이 평균적으로 강하지만 비싸다는 점을 보였다. dense 하나만 두고 비교하지 않는다.
- 서로 다른 rank list의 결합은 [Reciprocal Rank Fusion](https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/)을 가장 단순한 baseline으로 둔다.
- NoMIRACL-ko로 “근거가 없을 때 답함”과 “근거가 있는데도 모름”을 분리한다.
- 이 층의 결과는 `EXTERNAL_SMOKE_ONLY`이며 저장소 semantic gate를 열지 않는다.

### 2층 — 저장소 전용 component benchmark

한 gold row에 최소한 다음을 저장한다.

- `post_id`, `content_fingerprint`, `source_time`, `source_group_id`
- `is_novel_related`, `gold_work_id | NIL | UNJUDGED`
- `alias_surface`, `alias_relation=EXPLICIT_ALIAS|WORK_NICKNAME|NO_RELATION|AMBIGUOUS`
- 후보별 `relation_to_post=PRIMARY|MENTIONED|COMPARISON|RECOMMENDATION|BACKGROUND|NON_WORK`
- `official_evidence_url`, `community_evidence_url`, `evidence_span`, `evidence_sufficiency`
- `competing_work_ids`, `adjudication_status`, `guideline_version`

`아생갤` 같은 표면은 `작품 약칭`, `작중 갤러리/서사 장치`, `현실 DC 갤러리`, `일반명`, `모호` 후보를 병렬로 유지한다. explicit alias, specific-work target, 공식 근거, 커뮤니티 근거, competing-work 본문 근거를 합계 점수 하나로 숨기지 않는다.

### 3층 — end-to-end promotion benchmark

- 후보·근거·작품 ID가 모두 맞고 실제 공개한 경우만 correct publish로 센다.
- 정답 후보가 있어도 `MENTIONED/COMPARISON`이면 주작품 정답으로 세지 않는다.
- 검색 저하, evidence conflict, multiple primary, competing direct anchor는 confidence 숫자와 무관하게 먼저 HOLD한다.
- 같은 frozen post를 BEFORE/AFTER에서 exact pairing하고, 반복은 post/work cluster 내부 안정성으로 취급한다.

## 커뮤니티 지식 발굴은 투트랙으로 분리

커뮤니티가 직접 정리한 축약어·은어·웹소설 용어 문서는 사람이 모든 정답을 처음부터 쓰는 부담을 줄일 수 있다. 다만 한 `slang` 저장소에 합치면 플랫폼 용어·작가 문화·작품 별칭이 서로 오염되므로, 수집과 provenance만 공유하고 판정·저장·평가는 다음 두 트랙으로 분리한다.

### A — 소설 매칭

- 목표: `surface → canonical work ID | NIL`과 게시글 내 `PRIMARY/Mentioned/COMPARISON` 역할 판정
- 저장: 별도 `work_alias_registry`와 미승격 `lexicon_candidate_ledger`
- 승격 근거: 커뮤니티 목록의 명시 pair, 공식 작품명 실재, 독립된 실제 게시글 사용례를 따로 보존
- 평가: candidate Recall@K, canonical-ID accuracy/MRR, NIL F1, role macro-F1, wrong-work·unsafe publish

### B — 소설 커뮤니티 이해

- 목표: `기다무`, `투베`, `연독`, `글먹`, `망생이`처럼 작품 하나가 아니라 플랫폼·프로모션·작가/독자 문화·장르·밈을 해석
- 저장: 별도 `community_lexicon`; 작품 alias registry를 직접 변경하지 않음
- 필드: `term_type`, `definition`, `community_scope`, `platform_scope`, `discourse_function`, `valid_from/valid_to`, `sensitive`, `related_terms`, provenance
- 평가: 용어 span precision/recall, category F1, 문맥 의미·의도 정확도, 시의성/ambiguity coverage

B 트랙은 A 트랙에 음성·문맥 feature만 제공한다. 예를 들어 `장마갤`은 커뮤니티명이고 `아생갤`은 작품 약칭일 수 있으므로, `갤` 표면 규칙만으로 한 sense에 강제 배정하지 않는다. B의 자동 판정을 A의 중앙 alias memory write 허가로 사용하지 않는다.

### 확인한 community silver source

| 출처 | 주 용도 | 구조·주의 | 등급 |
| --- | --- | --- | --- |
| [Arca 소설 축약어](https://arca.live/w/novelchannel/%EC%86%8C%EC%84%A4%20%EC%B6%95%EC%95%BD%EC%96%B4) | 작품 alias | 공동편집 목록; Cloudflare로 자동 수집 안정성 낮음 | `SILVER_A_MINUS` |
| [DC 장르소설갤 축약어 백업](https://gall.dcinside.com/mgallery/board/view?id=genrenovel&no=7614173) | 작품 alias | `정식 작품명 - alias`; Arca 계열 백업이므로 독립 corroboration으로 중복 계수 금지 | `SILVER_B` |
| [FMKorea 웹소설 줄임말 모음](https://www.fmkorea.com/9330585139) | 밈형 작품 alias·어원 | `alias = 작품명`; 비하·정치 밈은 `sensitive` 분리 | `SILVER_B` |
| [DC 웹연갤 은어 정리](https://gall.dcinside.com/mgallery/board/view/?id=tgijjdd&no=217475) | 작가·플랫폼 문화 용어 | 자유문단; 2019년 설명의 시의성 재검증 필요 | `SILVER_B_MINUS` |
| [Tanma 가나다라](https://tanma.kr/data/webnovel_terms_ganadala.html)·[마바사](https://tanma.kr/data/webnovel_terms_mabasa.html)·[아자차](https://tanma.kr/data/webnovel_terms_ajacha.html)·[카타파하](https://tanma.kr/data/webnovel_terms_katapaha.html) | 업계·플랫폼·장르·커뮤니티 용어 | 표제어·정의·카테고리·관련어가 분리되어 parser profile에 가장 적합 | `SILVER_A_TO_B_PLUS` |

모두 공식 gold가 아니라 시점·커뮤니티·작성자에 귀속된 claim이다. source post의 `URL`, 작성/수정일, community, author, content hash, source lineage, 항목 locator를 보존하고 원문 정의의 대량 재배포는 피한다.

### 필요한 source-mining lane

현재 `SlangInsight`는 게시글당 단일 객체이고 Slang DB write는 검증된 exact pair만 받는다. 따라서 사전형 게시글을 현재 일반 배치에 넣으면 대표 표현 일부만 남거나 `multi_work/community_banter`로 격리될 수 있다. 기존 exact-pair fail-close는 유지하고, 다음 shadow-only 다중 항목 extractor를 별도로 둔다.

1. 제목·본문의 `축약어/은어/용어/정리/모음/백업` 신호와 반복 pair 구조로 source post를 탐지한다.
2. source profile별 방향을 분리한다: `작품명 - alias`, `alias = 작품명`, `표제어 + 정의`.
3. 각 항목을 `work_alias/platform_alias/promotion_abbrev/industry_term/genre_tag/community_slang`으로 routing한다.
4. `OBSERVED → CORROBORATED → TITLE_VERIFIED → HUMAN_CONFIRMED`로 승격하고 `CONFLICT/STALE`를 별도 보존한다.
5. 중앙 Slang DB와 public title에는 쓰지 않고, 충돌·미확인·고위험 항목만 사람 review queue로 보낸다.

이 구조에서는 수백 개 목록 항목을 사람이 전부 gold로 만드는 대신 자동 silver registry를 만들고, 실제 문맥 challenge 50~80행과 충돌/신규 항목만 사람이 판정하면 된다. 이번 연구에서는 source 구조 감사와 설계만 수행했으며 extractor 구현, 새 LLM run, 중앙 DB mutation은 하지 않았다.

## 단계별 필수 지표

| 단계 | 지표 | 답하는 질문 |
| --- | --- | --- |
| 후보 생성 | `Recall@1/5/10/20`, candidate coverage, truncation/UNKNOWN | 정답 작품을 후보에 넣었는가? |
| 근거 검색 | evidence `Recall@5/10`, `nDCG@10`, official provenance coverage | 공개 근거를 찾았는가? |
| ranking/linking | canonical-ID top-1, `MRR@10`, gold-present conditional accuracy | 후보가 있는데 올바르게 골랐는가? |
| 관계 판정 | role macro-F1와 confusion | 언급/비교 작품을 주작품으로 올렸는가? |
| NIL/보류 | NIL precision/recall, coverage, selective risk upper, AURC | 오답 공개와 all-HOLD를 함께 막았는가? |
| 확률 | multiclass Brier, log loss, fixed-bin ECE/reliability table | 말한 confidence가 실제 적중률인가? |
| 최종 | correct-title recovery, unsafe publish, wrong-work, HOLD integrity, PASS retention | 사용자 노출 결과가 안전하고 유용한가? |
| 안정성/비용 | any-run/majority/flip, calls/tokens, p50/p95 wall | 반복 안정성과 비용이 어떤가? |

정답 회수는 다음처럼 분해해 보고한다.

`end_to_end_correct_recall = candidate_recall × selection_accuracy_given_gold_present × publish_recall_given_correct_selection`

곱만 제시하지 말고 세 조건부 분모를 함께 공개해야 한다. 그래야 `1/11`이 search/alias 문제인지, reranker 문제인지, publish gate 과차단인지 구분할 수 있다.

## Gold set·표본 설계

### 데이터 분할

1. `DEV`: guideline과 feature 개발. 시작점 `120+`, truth class별 `40+`.
2. `CALIBRATION`: temperature/threshold 설정 전용. DEV와 work/source/content group이 겹치지 않는 `120+`.
3. `FROZEN_HOLDOUT`: 기준을 바꾸지 않고 1회 평가. 초기 shadow foundation `200+`, truth class별 `60+`.
4. `TIME_LATER_RANDOM`: 이후 기간 무작위 표본으로 prevalence와 drift 측정.
5. `CHALLENGE`: alias, wrong-work, competing-work, non-novel, OCR, search-degraded 고난도 표본. 모집단 정확도와 분리 보고.

개발용 최소 challenge smoke는 기존 32행을 포함한 80행 정도로 시작할 수 있다. 다만 이는 오류 유형 회귀용이지 production 오류율 추정용이 아니다.

### 주석 품질

- 최소 2인 blind independent annotation, 복잡한 relation/evidence는 3인 주석을 권장한다.
- span/link/relation/evidence의 agreement를 따로 보고한다. 단순 percent agreement 하나로 합치지 않는다.
- 불일치는 제3자 adjudication으로 닫고 원래 라벨·근거·guide rule을 보존한다. [Inter-Coder Agreement for Computational Linguistics](https://aclanthology.org/J08-4004/)와 KLUE의 독립 다중 주석 절차가 참고점이다.
- thread/URL/content hash뿐 아니라 동일 작품·alias family·공식 synopsis 복제까지 split leakage를 막는다.
- test는 `seen-work/new-time`, `unseen-work/unseen-alias`로 나눠 memorization과 일반화를 분리한다.

### 오류율 주장에 필요한 분모

- 최악조건에서 비율을 95% 신뢰수준 ±5%p로 추정하려면 약 385개의 해당 truth/decision 사례가 필요하다.
- unsafe publish 0건일 때 실제 오류율의 one-sided 95% 상한을 1%/0.5%/0.1% 아래로 두려면 독립 auto-publish 사례가 각각 약 `299/598/2,995`개 필요하다.
- 따라서 188행 canary도 auto-publish 분모가 작으면 `<1%` 안전 인증이 아니다. 전체 입력 수가 아니라 실제 공개 결정 분모를 gate에 결속한다.

## 정확도와 정답 회수율을 올리는 방법

### P0 — 실제 gold와 stage receipt부터 완성

- Golden18을 actual 평가 자료로 억지 승격하지 않는다.
- `candidate_miss / evidence_miss / wrong_rerank / relation_misread / publish_abstain`을 각각 카운트한다.
- producer `COMPLETE`, immutable candidate ID, evidence snapshot이 결속되지 않으면 해당 headline은 계속 `null`로 둔다.

기대 효과: 프롬프트 변경이 어느 실패를 실제로 줄였는지 처음으로 측정 가능해진다.

### P1 — hybrid 후보 생성으로 recall을 넓힌다

- exact alias lookup, BM25, Korean dense, 공식 플랫폼/작가/등장인물 검색을 병렬 후보원으로 둔다.
- `lookup ∪ BM25 ∪ dense`의 oracle recall과 각 lane의 unique-gold contribution을 기록한다. 짧고 노이즈가 큰 social text에서 lookup+dense의 상보성은 [TweetNERD 후보 생성 연구](https://aclanthology.org/2022.wnut-1.8/)에서도 확인됐다.
- `K=1/5/10/20` recall curve로 cap을 정하고, cap 증가를 accuracy 개선으로 오해하지 않는다.
- hard negative는 같은 작가 타작, 한 토큰 차이 유사 제목, 비교작, 댓글 추천작, 비소설 동명작으로 만든다.

기대 효과: correct-title `1/11` 중 “후보 자체 누락”을 직접 줄인다.

### P1 — role-aware reranker로 wrong-work를 줄인다

- BLINK처럼 1단 후보 회수와 2단 `(post context, canonical work description)` reranking을 분리한다.
- free-form title generation보다 immutable candidate ID+NIL 선택을 우선한다.
- 별도 relation head에서 `PRIMARY/MENTIONED/COMPARISON`을 판정하고 class confusion을 gate에 넣는다.
- 정답 후보가 top-1이어도 competing direct anchor와 충돌하면 자동 공개하지 않는다.

기대 효과: 현재 wrong-work 미회복 `3/5`의 핵심인 주작품 귀속 오류를 줄인다.

### P1 — 존재 근거와 게시글 주작품 근거를 분리한다

- “이 작품이 실재한다”와 “이 글이 이 작품을 주제로 한다”를 다른 score/receipt로 둔다.
- official detail, explicit alias, specific-work target, competing-work evidence를 각각 보존한다.
- search unrecovered는 숫자 confidence로 덮지 않고 hard abstain한다.
- KILT처럼 정답 ID와 provenance가 함께 맞아야 downstream 성공으로 센다.

기대 효과: evidence-conflict unsafe와 검색 실패 상태의 과확정을 막는다.

### P2 — calibrated selective cascade를 연다

- 쉬운 exact-ID/official-evidence 행만 cheap path로 처리하고 모호대역만 전체 expert council에 보낸다.
- CAL split에서 temperature scaling 또는 작은 error calibrator를 학습하고 FROZEN에서 고정한다. [Guo et al.](https://proceedings.mlr.press/v70/guo17a.html)은 temperature scaling이 강한 단순 기준선임을 보였지만, 이 도메인에서는 반드시 actual CAL/FROZEN으로 재검증한다.
- threshold는 risk-coverage 곡선과 selective-risk 상한으로 정한다. [SelectiveNet](https://proceedings.mlr.press/v97/geifman19a.html)의 핵심도 target coverage에서의 selective risk다.
- 반복 만장일치는 공개 근거가 아니라 stability feature다. semantic disagreement는 REVIEW/HOLD 신호로 쓰되, 모든 반복이 같은 오답을 내는 실패는 verifier와 근거 gate로 막는다.

기대 효과: unsafe를 늘리지 않고 자동 처리 coverage를 점진적으로 높인다.

### P2 — LLM judge는 triage하고 사람 gold가 승인한다

- source-only blind packet, 후보 순서 swap, generator와 다른 judge family를 사용한다.
- MT-Bench 연구는 높은 평균 human agreement와 함께 position/verbosity/self-enhancement bias를 보고했다. [JudgeBench](https://proceedings.iclr.cc/paper_files/paper/2025/hash/9e720fce64f91114c49cfd640d821da3-Abstract-Conference.html)는 어려운 객관식 pair에서 강한 judge도 취약할 수 있음을 보였다.
- LLM judge는 prelabel·우선순위·disagreement mining에만 쓰고, 최소 10–20% human double-label audit와 축별 confusion matrix를 둔다.
- active-learning 우선순위는 `uncertainty × 예상 피해 × novelty`로 둔다. unsafe/wrong-work/conflict/search-degraded publish가 최우선이다.

기대 효과: 사람 예산을 어려운 alias/wrong-work에 집중하면서 judge bias를 gold에 고착시키지 않는다.

## 권장 gate

### Actual shadow 시작 gate

기존 정책 A의 방향을 유지하되 결과를 보기 전에 소유자가 수치를 확정해야 한다.

- candidate recall one-sided lower `≥.95`
- NIL precision/recall lower `≥.90`
- coverage `≥.10`
- selective-risk upper `≤.05`
- paired top-label accuracy 비열화 없음
- paired Brier/log-loss/ECE/selective-risk/AURC 비열화 없음

### 자동 공개 승격 gate

- required-evidence search unrecovered `0`
- critical wrong-work/evidence-conflict unsafe `0`
- HOLD conflict sentinel `5/5`
- PASS/stable-control loss `0`
- unsafe publish one-sided 95% upper `≤1%`
- hard regression `0`
- 위 기준을 coverage 하락만으로 달성하면 correct-title recovery와 unnecessary-HOLD gate가 실패하도록 한다.

## 실행 가능한 A/B 순서

| Arm | 변경 | 주요 질문 |
| --- | --- | --- |
| `A0` | 현재 pipeline | 기준선 |
| `A1` | hybrid/RRF 후보 생성만 | candidate recall이 오르는가? |
| `A2` | role-aware reranker만 | gold-present accuracy와 wrong-work가 좋아지는가? |
| `A3` | evidence contract만 | unsafe/conflict가 줄고 recovery가 보존되는가? |
| `A4` | calibrated abstention만 | 같은 risk에서 coverage가 오르는가? |
| `A5` | A1–A4 조합 | end-to-end 순개선인가? |

새 실제 pipeline run은 동일 frozen input·retrieval snapshot·cache 조건을 쓰고 요청 병렬도 `--parallel 16`, dashboard ON으로 수행한다. candidate recall이 개선되지 않으면 reranker/프롬프트 튜닝으로 넘어가지 않고, wrong-work/unsafe가 한 건이라도 새로 생기면 해당 arm은 승격하지 않는다.

## 게이트 상태와 한계

| 항목 | 상태 |
| --- | --- |
| 외부 benchmark 조사 | `COMPLETE` |
| 저장소 metric/contract 대조 | `COMPLETE` |
| 현재 수치 CI 재산출 | `COMPLETE` |
| 외부 benchmark actual 실행 | `NOT_RUN` |
| domain DEV/CAL/FROZEN 구축 | `NOT_READY` |
| actual candidate recall/calibration | `NOT_EVALUABLE` |
| semantic auto activation | `NO-GO` |
| production/full scan | `NO-GO / full_scan_approval=false` |

외부 benchmark는 dynamic web search, DCinside 문체, 플랫폼 작품 ID, 약칭 생태계를 직접 포함하지 않는다. 이번 연구에서는 새 LLM/VLM 실행을 하지 않았으므로 모델 점수나 accuracy 개선을 주장하지 않는다. 다음 의미 있는 작업은 **80행 challenge smoke가 아니라 source-backed DEV/CAL/FROZEN packet을 실제로 만드는 것**이다.

## 저장소 근거

- `docs/devs/LOCAL_LLM_PIPELINE_QUALITY_ASSESSMENT_VALIDATION_20260829_KO.md`
- `docs/devs/P3_ACTUAL_POLICY_DECISION_KO_20260712.md`
- `docs/devs/loop_reports/LOOP_P3_CALIBRATION_CONTRACT_FOUNDATION_20260711.md`
- `src/llm_batch/grounding/candidate_set_calibration_shadow.py`
- `src/llm_batch/grounding/confidence_report.py`
- `tools/run_candidate_generation_completeness_harness.py`
- `tools/run_calibration_dataset_readiness.py`
- `tools/run_candidate_set_calibration_shadow_harness.py`
