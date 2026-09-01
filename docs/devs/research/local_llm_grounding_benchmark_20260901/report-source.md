# 로컬 LLM 커뮤니티·웹소설 grounding 벤치마크 연구 — 정본 소스

- 작성일: 2026-09-01 KST
- 독자: 로컬 LLM batch/grounding 파이프라인 기술 담당자
- 결정 질문: 정제·수집·작품/커뮤니티 판정 품질을 무엇으로 벤치마킹하고, 정답 회수율과 안전한 자동 판정 정확도를 어떻게 올릴 것인가?
- 시간 범위: 2026-09-01까지 확인 가능한 공개 연구·공식 문서와 저장소 실제 산출물
- 지리/언어 범위: 한국어 우선, 다국어·영어 벤치마크는 구조적 대리 지표로만 사용
- 제외: 새 LLM/VLM 실런, 전체 데이터 정확도 추정, 모델 가격 비교, production 승인

## 직접 결론

단일 공개 벤치마크로 이 파이프라인을 평가할 수는 없다. 가장 타당한 방식은 다음 3층을 결합하는 것이다.

1. `MTEB(kor, v2)·MIRACL-ko·NoMIRACL-ko·KLUE`로 한국어 검색·관련성·NER/RE의 외부 smoke benchmark를 돌린다.
2. 저장소 도메인에서 immutable work ID, alias relation, `primary/mentioned/comparison`, 공식 근거와 NIL을 이중 주석한 qrels/gold set으로 후보 생성·근거 검색·역할 판정을 따로 측정한다.
3. 기존 P3의 candidate recall, top-label/NIL, Brier/log-loss/ECE, risk-coverage/AURC, 그룹 bootstrap 계약을 `FROZEN_ACTUAL` 자료로 실제화하고, end-to-end unsafe publish와 correct-title recovery를 별도 hard gate로 둔다.

현재 가장 큰 공백은 지표 구현이 아니라 실제 정답 자료다. 저장소에는 관련 계산·결속·신뢰구간 기반이 이미 있지만 Golden18은 producer `COMPLETE 0/18`, actual ready `0/18`이라 headline 값이 `null`이다. 최신 고위험 32행 결과도 어려운 회귀 cohort의 신호일 뿐 모집단 정확도가 아니다.

## 현재 근거 재판독

| 지표 | 관측 | 95% Wilson 구간 | 해석 |
| --- | ---: | ---: | --- |
| 고위험 의미 compliance | `18/32 = 56.25%` | `39.33%–71.83%` | `NO-GO`; 전체 데이터 정확도 아님 |
| correct-title recovery | `1/11 = 9.09%` | `1.62%–37.74%` | 회수 능력 매우 부족, 구간도 넓음 |
| review-router recall | `43/66 = 65.15%` | `53.11%–75.52%` | 고위험 누락이 큼 |
| HOLD integrity | `4/5 = 80%` | `37.55%–96.38%` | 분모가 너무 작아 승인 불가 |
| unsafe publish any-run | `1/32 = 3.13%` | `0.55%–15.74%` | 상한이 넓어 자동 공개 안전성 입증 불가 |
| candidate recall/calibration | `null / NOT_EVALUABLE` | 해당 없음 | actual gold와 producer COMPLETE가 없음 |

Wilson 계산은 게시글을 독립 단위로 사용했다. 3회 반복 `96`개 출력을 독립 표본처럼 세지 않는다. 반복은 게시글 cluster 내부 안정성/flip 측정에 사용한다.

## 답해야 할 주장과 격차 행렬

| 주장 | 근거 | 신뢰도 | 반대/한계 | 남은 격차와 다음 확인 |
| --- | --- | --- | --- | --- |
| 공개 벤치마크는 component smoke에는 유용하지만 도메인 end-to-end 정답을 대신하지 못한다. | BEIR/MTEB/MIRACL/KLUE/NoMIRACL의 task·corpus 정의 | 높음 | 공개셋은 Wikipedia·뉴스·QA 중심이며 웹소설 약칭/경쟁작 target을 직접 라벨하지 않음 | 저장소 전용 time-split gold 필요 |
| 후보 생성과 최종 선택은 별도 지표여야 한다. | BLINK 2단 retrieval→cross-encoder, KILT provenance, 저장소 P1/P3 계약 | 높음 | BLINK/KILT는 Wikipedia entity 중심 | work ID·alias·role qrels로 이식 검증 |
| 한국어 검색 smoke는 MIRACL-ko/MTEB(kor,v2)가 가장 직접적이다. | MIRACL 공식 qrels와 MTEB Korean benchmark 목록 | 높음 | 웹소설 커뮤니티 문체·동적 웹 검색과 도메인 차이 | 외부 점수는 모델 선별에만 사용 |
| 보류/NIL 성능은 accuracy가 아니라 coverage-risk와 NIL PR로 함께 측정해야 한다. | SelectiveNet, NoMIRACL, 저장소 P3 metric contract | 높음 | threshold는 운영 비용/위험 선호에 의존 | 사전등록 CAL/FROZEN 정책 확정 |
| raw LLM confidence는 그대로 확률로 쓰면 안 된다. | Guo et al. calibration, 저장소 temperature-scaling 설계 | 높음 | 원 논문은 일반 neural classifier이며 LLM/domain transfer는 검증 필요 | CAL split에서 Brier/log-loss/ECE 비교 |
| LLM judge는 대량 prelabel/triage에는 쓸 수 있으나 sole gold가 될 수 없다. | MT-Bench bias, NIST TREC 2024 relevance study | 중간~높음 | NIST 결과는 system ranking correlation이며 row-level exact gold 보장은 아님 | 10–20% human double-label audit와 judge confusion matrix |
| 현재 32행 수치는 production 오류율을 입증하기에 작다. | NIST Wilson CI, 현재 계산 | 높음 | hard cohort는 의도적 oversample이라 모집단 prevalence와 다름 | random/time-later 모집단 표본 별도 구축 |
| unsafe publish 1% 미만을 무오류로 입증하려면 적어도 299개 자동 공개 결정이 필요하다. | binomial `P(0 failures)=(1-p)^n`, alpha `.05` | 높음(수학적) | 독립·동일분포 가정; cluster/time drift 시 더 필요 | coverage에 따라 총 입력 수를 늘리고 cluster CI 병행 |
| 이중 독립 주석+제3자 adjudication이 gold 품질을 높인다. | CLEF annotation workflow, 2024 annotation quality review | 높음 | agreement만 높아도 validity가 보장되지는 않음 | guideline pilot, adjudication error audit 포함 |
| NIKL entity-linking 자원은 한국어 EL 사전학습/진단에 유용하다. | 국립국어원 2022 보고서·corpus catalog | 높음 | Wikipedia 7개 범주 중심, 신청·공개 제한, 웹소설 플랫폼 ID와 불일치 | license 확인 후 smoke/feature 학습에만 사용 |

## 권고 benchmark stack

### 1. 외부 smoke

- `MTEB(kor, v2)`: 한국어 retrieval/reranking/STS 등 모델 선별. 이 파이프라인에서는 retrieval task 점수만 별도 보고한다.
- `MIRACL-ko`: BM25, dense, hybrid/RRF, reranker의 `nDCG@10`, `Recall@10/100` 비교.
- `NoMIRACL-ko`: 관련 근거가 없을 때 답하지 않는 능력과 관련 근거를 놓치는 능력을 각각 hallucination/error rate로 비교.
- `KLUE-NER/RE`: 한국어 span/relation encoder의 smoke. 작품 ID linking이나 게시글 주작품 판정 점수로 오해하지 않는다.
- `NIKL entity linking`: 라이선스가 허용하는 범위에서 Korean EL smoke 또는 초기 representation 학습. 최종 도메인 gold와 분리한다.

### 2. 저장소 전용 component benchmark

Gold row의 최소 필드:

- `post_id`, `content_fingerprint`, `source_time`, `source_group_id`
- `is_novel_related`, `gold_work_id | NIL | UNJUDGED`
- `alias_surface`, `alias_relation=EXPLICIT_ALIAS|WORK_NICKNAME|NO_RELATION|AMBIGUOUS`
- 후보별 `relation_to_post=PRIMARY|MENTIONED|COMPARISON|RECOMMENDATION|BACKGROUND|NON_WORK`
- `official_evidence_url`, `community_evidence_url`, `evidence_span`, `evidence_sufficiency`
- `competing_work_ids`, `adjudication_status`, `annotator_ids`, `guideline_version`

단계별 지표:

| 단계 | 필수 지표 | 핵심 실패 |
| --- | --- | --- |
| 후보 생성 | `Recall@1/5/10/20`, candidate coverage, truncation/UNKNOWN rate | 정답 후보 자체 누락 |
| 근거 검색 | evidence `Recall@5/10`, `nDCG@10`, official-provenance coverage, unrecovered degraded | 후보는 있으나 근거 없음 |
| ranking/linking | top-1 accuracy, `MRR@10`, candidate-conditional accuracy | 정답 후보가 있는데 오선택 |
| relation | role macro-F1, class별 recall, confusion(`PRIMARY→MENTIONED/COMPARISON`) | 경쟁/언급 작품을 주작품으로 승격 |
| NIL/보류 | NIL precision/recall, coverage, selective risk 상한, AURC | 오답 공개 또는 과도 HOLD |
| calibration | multiclass Brier, log loss, fixed-bin ECE | confidence 숫자 과신 |
| end-to-end | correct-publish precision/recall, correct-title recovery, unsafe publish, wrong-work, HOLD integrity | 사용자 노출 최종 오류 |
| 안정성/비용 | post-cluster flip rate, calls/tokens, p50/p95 wall | 반복 불안정·비용 증가 |

오류 분해식은 다음처럼 보고한다.

`end_to_end_correct_recall = candidate_recall × selection_accuracy_given_gold_present × publish_recall_given_correct_selection`

이 값은 각 조건부 분모를 별도로 함께 제시해야 한다. 곱만 보고하면 어느 단계가 정답을 잃었는지 알 수 없다.

### 3. end-to-end promotion benchmark

- 기존 정책 A를 actual shadow의 시작점으로 사용한다: candidate recall one-sided lower `≥.95`, NIL precision/recall lower `≥.90`, coverage `≥.10`, selective-risk upper `≤.05`, paired 비열화 없음.
- 자동 공개 승격은 더 엄격하게 분리한다: search unrecovered `0`, critical wrong-work `0`, evidence-conflict unsafe `0`, hard regression `0`, unsafe-publish one-sided 95% upper `≤1%`.
- 무오류 조건에서 마지막 기준은 자동 공개 결정 `n≥299`가 필요하다. coverage가 10%이면 총 입력은 약 2,990행까지 필요할 수 있으므로 총 행 수가 아니라 실제 auto-publish 분모를 gate에 결속한다.

## Gold set과 표본 설계

세 층을 섞지 않는다.

1. `DEV`: guideline/feature/error taxonomy 개발. 120행 이상, truth class별 40행 이상을 시작점으로 한다.
2. `CALIBRATION`: temperature/threshold만 설정. DEV와 work/source/content group이 겹치지 않는 120행 이상.
3. `FROZEN_HOLDOUT`: 한 번만 최종 평가. 초기 shadow 계약은 200행·truth class별 60행을 시작점으로 하되 production 승인 표본으로 과장하지 않는다.
4. `TIME_LATER_RANDOM`: 이후 기간 무작위 표본. 모집단 prevalence와 drift를 본다.
5. `CHALLENGE`: alias, `아생갤`, wrong-work, competing-work, non-novel, OCR, search-degraded를 층화한 고난도 세트. 모집단 정확도와 분리 보고한다.

정량 목표에 따른 추가 분모:

- 비율을 95% 신뢰수준에서 최악조건 ±5%p로 추정하려면 약 385개의 해당 truth/decision 사례가 필요하다.
- unsafe publish가 0건일 때 실제 오류율 상한을 1%/0.5%/0.1% 아래로 두려면 독립 auto-publish 사례가 각각 약 `299/598/2,995`개 필요하다.
- BEFORE/AFTER는 같은 게시글에 대한 paired 설계로 두고 binary correctness는 McNemar, 연속/비율 지표는 post/work/source group bootstrap CI로 비교한다.

## 정확도·정답 회수 개선 우선순위

### P0. actual gold와 stage receipt를 먼저 완성

- 현재 `Golden18 ready 0/18`을 actual DEV/CAL/FROZEN packet으로 대체한다.
- producer plan/receipt가 `COMPLETE`가 아닌 행은 후보 recall/calibration headline에서 제외하는 기존 fail-close를 유지한다.
- 전체 수치보다 `candidate_miss / evidence_miss / wrong_rerank / relation_misread / publish_abstain` 원인 카운트를 먼저 만든다.

### P1. 후보 회수율 확대

- exact lexical/BM25, Korean dense retrieval, 공식 플랫폼/작가/등장인물 검색을 병렬 후보원으로 두고 union 또는 RRF로 합친다.
- alias query는 표면만 확장하지 말고 `약칭 + 캐릭터/작가/플랫폼/본문 고유어` 조합을 만든다.
- `K=1/5/10/20` recall curve와 비용을 함께 측정해 cap을 정한다.
- hard negative는 같은 작가 타작, 한 토큰 차이 유사 제목, 본문 비교작, 댓글 추천작, 비소설 동명작을 의도적으로 넣는다.

### P1. role-aware reranking

- BLINK식으로 1단 후보 회수와 2단 `(post context, canonical work description)` cross-encoder/로컬 LLM scoring을 분리한다.
- free-form 제목 생성보다 immutable candidate ID+NIL 선택을 우선하고, 별도 head에서 `PRIMARY/MENTIONED/COMPARISON`을 판정한다.
- 상위 후보가 competing 본문 작품과 충돌하면 정답 후보가 있어도 자동 공개하지 않는다.

### P1. evidence와 결정 분리

- 후보 존재 근거와 이 게시글의 주작품 근거를 별도 필드로 유지한다.
- 공식 detail URL, explicit alias relation, specific-work target, competing-work evidence를 각각 라벨·metric으로 만든다.
- `SEARCH_DEGRADED`/증거 conflict는 confidence를 낮추는 숫자 feature가 아니라 먼저 hard abstain 조건으로 둔다.

### P2. calibrated selective cascade

- 낮은 위험 exact ID/official evidence는 cheap path, 모호대역만 전체 expert council로 보낸다.
- CAL split에서 temperature scaling과 threshold를 정하고 FROZEN에서 고정한다.
- 3회 반복 다수결 자체를 정답으로 쓰지 말고 disagreement/flip을 abstain feature로 쓴다.
- 비용 절감은 accuracy/risk hard gate 통과 뒤에만 평가한다.

### P2. judge와 active learning

- LLM judge는 source-only blind packet, 후보 순서 swap, decoder와 다른 judge family로 triage한다.
- 최소 10–20%를 사람 이중 독립 주석+제3자 adjudication하고 judge-vs-human confusion을 공개한다.
- active learning queue는 낮은 margin, judge disagreement, new alias, search-degraded, competing-work conflict, drifted surface를 우선한다.
- gold가 안정된 뒤에야 reranker/LoRA 학습을 검토한다. self-generated label을 그대로 slang/alias 정답으로 승격하지 않는다.

## 실험 순서

1. `A0`: 현재 pipeline, 동일 frozen input, `--parallel 16`, dashboard ON.
2. `A1`: hybrid/RRF candidate generation만 변경.
3. `A2`: role-aware reranker만 변경.
4. `A3`: official/alias/specific-target/competing evidence contract만 변경.
5. `A4`: calibrated abstention threshold만 변경.
6. `A5`: A1–A4 조합.

각 arm은 동일 post/work/source cluster와 동일 retrieval snapshot을 사용한다. candidate recall이 오르지 않으면 reranker/프롬프트 튜닝으로 넘어가지 않고, wrong-work/unsafe가 한 건이라도 새로 생기면 조합 승격을 중단한다.

## 한계

- 외부 benchmark는 이 저장소의 dynamic web search, DCinside 문체, 플랫폼 작품 ID, 약칭 생태계를 직접 포함하지 않는다.
- 현재 수치는 고위험 표본이며 모집단 prevalence 추정이 아니다.
- 새 LLM/VLM 실행을 하지 않았으므로 external benchmark score와 actual FROZEN metric은 `NOT_RUN/NOT_EVALUABLE`이다.
- 표본 수 산식은 독립 binomial 근사/정확식의 설계 기준이다. 동일 작품·동일 게시판·반복 run 상관은 cluster/time split으로 보수적으로 처리해야 한다.

## Claim-to-source ledger

| ID | 자료 | 저자/발행처 | 날짜 | URL | 사용과 접근 메모 |
| --- | --- | --- | --- | --- | --- |
| I1 | 로컬 LLM 파이프라인 품질 현황 검증 | 저장소 | 2026-08-29 | `docs/devs/LOCAL_LLM_PIPELINE_QUALITY_ASSESSMENT_VALIDATION_20260829_KO.md` | 현재 32행/66행 지표와 gate; local readback |
| I2 | P3 정확도 퍼센트 계약 기반 구현 보고서 | 저장소 | 2026-07-11/12 | `docs/devs/loop_reports/LOOP_P3_CALIBRATION_CONTRACT_FOUNDATION_20260711.md` | 구현 metric과 actual null 경계 |
| I3 | P3 실제 정확도 정책 숫자 결정안 | 저장소 | 2026-07-12 | `docs/devs/P3_ACTUAL_POLICY_DECISION_KO_20260712.md` | 기존 A/B threshold·표본 제안 |
| S1 | BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models | Thakur et al., NeurIPS | 2021 | https://openreview.net/forum?id=wCu6T5xFjeJ | retrieval generalization·BM25/reranking 비교; 2026-09-01 확인 |
| S2 | MTEB available benchmarks — Korean v2 | MTEB project | 지속 갱신 | https://docs.mteb.org/overview/available_benchmarks/ | Korean task 목록·20-task 설명; 2026-09-01 확인 |
| S3 | Making a MIRACL | Zhang et al., TACL/WSDM Cup | 2023 | https://arxiv.org/abs/2210.09984 | 18-language IR benchmark, Korean 포함 |
| S4 | MIRACL official repository | MIRACL project | 지속 갱신 | https://github.com/project-miracl/miracl | Korean query/qrels counts·공식 loader |
| S5 | NoMIRACL | Thakur et al., EMNLP Findings | 2024 | https://aclanthology.org/2024.findings-emnlp.730/ | Korean 포함 relevant/non-relevant와 hallucination/error rate |
| S6 | KLUE | Park et al. | 2021 | https://openreview.net/forum?id=q-8h8-LZiUm | Korean NER/RE 등 8 tasks; direct EL 아님 |
| S7 | 2022년 말뭉치 개체명 분석 및 개체 연결 보고서 | 국립국어원 | 2022/2023 공개 | https://www.korean.go.kr/common/download.do?c_file_name=6cb5bfe5-a6e8-4bd1-8b4d-27bfb58ca3bb.pdf&file_path=reportData&o_file_name=2022%EB%85%84%20%EB%A7%90%EB%AD%89%EC%B9%98%20%EA%B0%9C%EC%B2%B4%EB%AA%85%20%EB%B6%84%EC%84%9D%20%EB%B0%8F%20%EA%B0%9C%EC%B2%B4%20%EC%97%B0%EA%B2%B0%20%EC%9A%A9%EC%97%AD%20%EB%B3%B4%EA%B3%A0%EC%84%9C_v7.0_%EC%B5%9C%EC%A2%85.pdf | 한국어 online dialogue/news EL, Wikipedia 7범주 |
| S8 | 모두의 말뭉치 corpus catalog/FAQ | 국립국어원 | 지속 갱신 | https://kli.korean.go.kr/corpus/openapi/corpusList.do?lang=en | 신청·활용·외부 공개 제한 확인 |
| S9 | KILT | Petroni et al., NAACL | 2021 | https://aclanthology.org/2021.naacl-main.200/ | entity linking+provenance의 unified evaluation |
| S10 | Scalable Zero-shot Entity Linking with Dense Entity Retrieval (BLINK) | Wu et al., EMNLP | 2020 | https://arxiv.org/abs/1911.03814 | bi-encoder candidate retrieval→cross-encoder reranking |
| S11 | Reciprocal Rank Fusion | Cormack, Clarke, Büttcher, SIGIR | 2009 | https://research.google/pubs/reciprocal-rank-fusion-outperforms-condorcet-and-individual-rank-learning-methods/ | heterogeneous rank-list fusion 근거 |
| S12 | SelectiveNet | Geifman, El-Yaniv, PMLR | 2019 | https://proceedings.mlr.press/v97/geifman19a.html | coverage-specific selective risk |
| S13 | On Calibration of Modern Neural Networks | Guo et al., ICML/PMLR | 2017 | https://proceedings.mlr.press/v70/guo17a.html | temperature scaling과 calibration |
| S14 | NIST confidence intervals | NIST/SEMATECH | 지속 갱신 | https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm | Wilson proportion CI 권고·공식 |
| S15 | Computing confidence intervals for common IR measures | NIST | 2014 | https://www.nist.gov/publications/computing-confidence-intervals-common-ir-measures | IR metric CI와 bootstrap |
| S16 | Approximate Statistical Tests for Comparing Supervised Classification Learning Algorithms | Dietterich | 1998 | https://pubmed.ncbi.nlm.nih.gov/9744903/ | paired binary comparison에 McNemar 근거 |
| S17 | Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | Zheng et al., NeurIPS | 2023 | https://arxiv.org/abs/2306.05685 | human agreement와 position/verbosity/self bias |
| S18 | A Large-Scale Study of Relevance Assessments with LLMs | Upadhyay et al., NIST | 2025 | https://www.nist.gov/publications/large-scale-study-relevance-assessments-large-language-models-initial-look | 77 runs system-ranking correlation; sole row gold 근거는 아님 |
| S19 | Analyzing Dataset Annotation Quality Management in the Wild | Klie et al., Computational Linguistics | 2024 | https://direct.mit.edu/coli/article/50/3/817/120233/Analyzing-Dataset-Annotation-Quality-Management-in | agreement 외 guideline/adjudication/error audit 필요 |
| S20 | CLEF Corpus annotation process | Roberts et al. | 2009 | https://pmc.ncbi.nlm.nih.gov/articles/PMC2655900/ | independent double annotation+third adjudication |
| S21 | Robust Candidate Generation for Entity Linking on Short Social Media Texts | Hebert et al., W-NUT/ACL | 2022 | https://aclanthology.org/2022.wnut-1.8/ | lookup+dense candidate source의 상보성; 영어 Twitter라는 한계 |
| S22 | Inter-Coder Agreement for Computational Linguistics | Artstein, Poesio, Computational Linguistics | 2008 | https://aclanthology.org/J08-4004/ | chance-corrected agreement와 task별 계수 선택 |
| S23 | JudgeBench | Tan et al., ICLR | 2025 | https://proceedings.iclr.cc/paper_files/paper/2025/hash/9e720fce64f91114c49cfd640d821da3-Abstract-Conference.html | 어려운 객관적 response pair의 LLM judge 취약성 |

## 검색 기록과 중단 기준

- 검색군: IR benchmark/metric, Korean retrieval/NER/RE/EL, NIL/abstention, calibration/selective prediction, LLM judge validity, annotation quality, paired statistical inference, hybrid/reranking.
- 우선순위: 공식 benchmark repository/documentation, 원 논문, NIST/국립국어원 자료, 그 다음 독립 방법론 논문.
- 제외: 제품 마케팅 점수, Reddit anecdote, 라이선스가 불명확한 비공식 재배포본, 영어 QA 점수를 곧바로 웹소설 성능으로 환산하는 주장.
- 중단 이유: 모든 보고서 섹션에 1차/공식 근거가 있고, consequential claim의 반례·도메인 한계를 명시했으며, 추가 검색이 핵심 결론인 “외부 smoke+도메인 gold+actual P3”를 바꿀 가능성이 낮아졌다.
