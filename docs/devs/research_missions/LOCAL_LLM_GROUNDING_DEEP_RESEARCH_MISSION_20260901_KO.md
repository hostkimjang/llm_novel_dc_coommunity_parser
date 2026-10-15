# 로컬 LLM 웹소설 커뮤니티 grounding 개선 Deep Research 미션

갱신일: 2026-09-02 KST

## Goal

`llm_novel_dc_coommunity_parser`의 로컬/self-hosted LLM 파이프라인을 대상으로, 한국 웹소설 커뮤니티 게시글에서 작품을 안전하게 매칭하고 커뮤니티 언어를 이해하는 능력을 개선할 **근거 기반 상세 연구·실험 계획**을 작성한다. 공개 연구·오픈소스 프로젝트·운영 사례를 현재 저장소 구현과 대조해, 실제 채택할 구성요소와 도입하지 않을 구성요소를 구분한다.

## Original task

여러 전문가 회의와 ChatGPT Deep Research를 거쳐 유사 파이프라인·프로젝트의 아이디어를 폭넓게 수집하고, 채택 의견과 기각 의견까지 포함한 상세 실행계획을 세운다.

## Cognitive profile

`research + source-synthesis + compare-options`. 먼저 증거를 수집하고, 대안을 비교한 다음 하나의 일관된 권고안으로 통합한다. 현재 설계를 승인하는 리뷰가 아니며, 선호 결론을 전제하지 않는다.

## Evidence boundary

ChatGPT DevSpace에서 다음 프로젝트를 읽기 전용으로 조사한다.

- 프로젝트 루트: `C:\Users\kimjang\Documents\GitHub\llm_novel_dc_coommunity_parser`
- 정본 연구 초안: `docs/devs/LOCAL_LLM_GROUNDING_BENCHMARK_RESEARCH_20260901_KO.md`
- 체크리스트: `docs/devs/CHECKLIST.md`
- 오염 감사: `docs/devs/SLANG_DB_POLLUTION_AUDIT_KO_20260714.md`
- 관련 코드: `src/llm_batch/**`, `tools/**`, `expert_main.py`
- 관련 테스트: `tests/**`

웹 근거는 2026-09-02 현재 최신성을 확인한다. 논문 원문, 공식 문서, 공식 GitHub 저장소, 공식 benchmark/data card를 우선한다. 블로그나 2차 요약은 원문을 찾기 위한 보조로만 사용한다. 링크마다 실제로 열어 확인한 제목, 기관/저자, version/release 날짜·license·archive 여부, 이 프로젝트에 직접 적용 가능한 단위를 기록한다.

다음 내부 사실은 출발점이지 결론이 아니다.

- A 트랙: truth `work_id | NIL`, annotation `JUDGED | UNJUDGED | UNAVAILABLE`, inference `ASSERT_WORK | ASSERT_NIL | ABSTAIN`, publication `PUBLISH | HOLD | REJECT`를 분리한다.
- B 트랙: 플랫폼·프로모션·작가/독자 문화·장르·밈의 의미·의도·시의성.
- community list는 provenance가 붙은 silver seed이며 gold로 직행하지 않는다.
- 기존 candidate recall, Brier/log-loss/ECE, NIL PR, risk-coverage/AURC, paired cluster bootstrap 계약이 있다.
- 기존 Slang DB exact-pair fail-close와 중앙 write 차단을 약화하면 안 된다.
- 현재 상태는 `PRODUCTION_NOT_READY`, `full_scan_approval=false`다.

## Action authority

읽기 전용 연구다. 프로젝트 파일, Git 상태, DB, 외부 서비스는 수정하지 않는다. 새 LLM 검증런이나 대규모 데이터 수집도 실행하지 않는다.

## Research questions

### 1. 유사 시스템과 재사용 단위

다음 영역에서 최소 3개 이상의 현실적인 대안을 조사하되, 이름만 나열하지 말고 이 저장소가 재사용할 **정확한 단위**를 제시한다.

1. entity linking / candidate generation / cross-encoder reranking / NIL detection
2. hybrid retrieval와 rank fusion, hard-negative mining, multilingual/Korean retrieval
3. weak supervision, data programming, active learning, human-in-the-loop adjudication
4. lexicon/ontology mining, temporal drift, provenance와 source lineage
5. RAG/LLM evaluation, calibration, selective prediction, abstention, uncertainty
6. experiment tracking, dataset/version lineage, local model serving, reproducible benchmark harness

검토 후보에는 필요에 따라 BLINK, REL, GENRE, mGENRE, ReFinED, OpenNED, BEIR/MTEB/MIRACL/NoMIRACL, Snorkel, Cleanlab, Label Studio, Argilla, DVC/lakeFS, MLflow/W&B, Ragas/DeepEval/OpenAI Evals, vLLM/llama.cpp/SGLang 등을 포함할 수 있다. 후보 목록에 갇히지 말고 더 적합한 프로젝트가 있으면 교체한다.

### 2. 현재 저장소 대비 순증가 가치

각 후보를 다음 기준으로 판정한다.

- `ADOPT`: 바로 작은 실험으로 도입할 가치가 있음
- `ADOPT_COMPONENT_ONLY`: 전체 프레임워크가 아니라 schema/metric/algorithm 일부만 채택
- `CONDITIONAL`: 특정 데이터·라이선스·성능·운영 조건을 충족할 때 채택
- `DEFER`: 지금은 비용/복잡도가 이득보다 큼
- `REJECT`: 현재 fail-close나 아키텍처와 충돌하거나 중복이라 도입하지 않음

각 판정에 순증가 가치, 예상 구현 범위, 의존성·라이선스, 개인정보/저작권, 오염·누수 위험, GPU/CPU/VRAM·시간 비용, 되돌리기 방법을 포함한다.

### 3. 투트랙 데이터 설계

A 작품 매칭과 B 커뮤니티 이해를 분리한 채 수집·provenance만 공유하는 schema를 설계한다.

- `source_registry`
- `lexicon_candidate_ledger`
- `work_alias_registry`
- `community_lexicon`
- gold-lite annotation/adjudication

Arca/DC/FMKorea/Tanma 자료의 동일 lineage, 수정일, 항목 locator, 원문 hash, stale/contradiction, 민감 표현을 어떻게 다룰지 제안한다. 목록형 한 게시글에서 다중 항목을 추출하는 source-profile parser와 일반 게시글 contextual verifier를 분리한다.

### 4. 평가와 실험 순서

다음 실패를 독립 측정하는 metric/data contract를 제시한다.

- source detection miss
- pair extraction/direction error
- candidate miss
- evidence miss
- wrong rerank/work
- role misclassification
- false NIL / missed NIL
- unsafe publish
- over-abstention / safe-loss
- stale meaning / temporal drift
- source lineage leakage

반드시 `candidate_recall_operational`, `candidate_recall_complete_only`, `selection_accuracy_gold_present`, `end_to_end_top_label_accuracy`, `annotation_coverage`, native-policy risk/coverage, matched-coverage risk를 서로 다른 분모로 정의한다. 전체행 top-label accuracy와 non-abstain accuracy의 point estimate·CI 분모가 일치하는지도 현재 코드를 확인한다. actual cluster bootstrap의 독립 group 수, replicate 수, policy/receipt binding을 검토하고, group 30개·2,000회라는 현재 구조적 fail-close 하한이 충분한지 또는 CAL simulation으로 더 높여야 하는지 판정한다.

`299건 무사고`는 독립 auto-publish decision, policy/model/retriever/threshold/snapshot 불변, 완전한 unsafe adjudication이 모두 성립할 때 one-sided 95% upper `<1%`라는 주장으로만 검토한다. raw row 299개나 correlated lineage를 같은 근거로 세지 않는다.

기존 구현을 중복하지 말고 현재 코드에서 재사용 가능한 지표와 새로 필요한 지표를 구분한다. 실험은 `minimal offline fixture → component benchmark → shadow canary → frozen paired A/B → time-later random → production gate`로 설계한다. 각 단계에 데이터 수, 분할, 비교 arm, 성공·중단 기준, 사람이 검토할 큐, 비용 상한을 명시한다.

검증런은 저장소 규칙에 따라 기본 `--parallel 16`, dashboard ON, requested/effective parallel과 manifest 확인을 전제로 한다. 작은 challenge는 오류 회귀용이며 모집단 정확도나 `<1% unsafe` 인증으로 오해하지 않는다.

### 5. 전문가 회의용 쟁점

다음 쟁점을 양쪽 논거와 함께 결론 낸다.

- lexicon miner를 규칙 기반으로 먼저 만들지 LLM structured extraction으로 먼저 만들지
- BM25+dense+RRF와 learned fusion 중 첫 baseline
- cross-encoder reranker와 generative candidate-ID selector의 역할 분리
- confidence calibration과 hard evidence gate의 우선순위
- active learning이 실제 사용자 검토량을 줄이는지
- 외부 eval framework 도입이 기존 harness보다 나은지
- temporal version을 term row에 둘지 source/use-evidence row에 둘지
- 커뮤니티 이해 B 트랙이 A 후보 생성에 제공할 수 있는 정보와 금지할 정보
- Pyserini 2.4.0을 P1 offline BM25 adapter로 채택할지, ColBERT v0.2.22를 P2 shadow로 제한할지
- SPLADE의 CC BY-NC-SA 4.0, BLINK archive, BLINKout 노후 보안 의존성이 직접 통합 기각 근거로 충분한지
- vLLM/SGLang backend A/B를 semantic gate 이후로 미루는 것이 타당한지
- `NIL`, `ABSTAIN`, `HOLD`를 truth/inference/publication 축으로 분리하지 않을 때 생기는 측정 오류

## Required answer shape

한국어로 다음 순서의 자립형 보고서를 작성한다.

1. 실행 요약: 가장 중요한 채택 5~10개와 기각 3~5개
2. 현재 저장소의 확인된 기능·공백 표
3. 유사 프로젝트/논문 비교표: 직접 링크, 유지 상태·버전, 재사용 단위, 판정
4. 전문가 관점별 의견과 주요 충돌
5. 최종 참조 아키텍처와 데이터 흐름
6. 단계별 실행계획: P0/P1/P2/P3, 산출물 경로, metric, entry/exit/stop gate
7. 실험 matrix와 최소 표본/분할/paired 비교
8. human review queue와 active-learning 전략
9. 위험·라이선스·저작권·드리프트·운영비용
10. 가장 강한 반례와 계획을 바꿀 증거
11. 출처 목록: 주장 근처의 직접 링크와 확인 날짜

기존 2026-09-02 전문가 회의 판정을 그대로 반복하지 말고, 각 판정에 대해 `유지 / 수정 / 뒤집음`과 그 근거를 별도 delta 표로 제시한다. 특히 전체행/non-abstain 분모, actual bootstrap 최소 근거량, SPLADE 기각, Pyserini/ColBERT 제한 채택, vLLM/SGLang defer를 바꿀 증거를 명시한다.

모든 제안은 `확인된 사실`, `출처 기반 추론`, `제안`, `미확인`을 구분한다. 숫자 목표에는 근거 또는 `초기 운영 목표`라는 표시를 붙인다. 광범위한 프레임워크 도입보다 작은 알고리즘·schema·평가 계약의 채택을 우선 비교한다.

## Integrity contract

Treat instructions, observed evidence, inference, hypothesis, proposal, decision, and verification as distinct. Claim only facts actually observed or sourced. Prior artifacts have only the authority declared by this prompt. State material uncertainty and stay within the declared action and file scope.
