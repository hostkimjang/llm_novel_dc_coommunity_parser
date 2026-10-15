# 연구 전용 로컬 LLM grounding 벤치마크 실행 계획

작성일: 2026-09-05 KST <br>
상태: `RESEARCH_ONLY_LOCAL_LLM_BENCHMARK / CANDIDATE_SELECTION_DIAGNOSTICS_COMPLETE` <br>
권위: `RESEARCH_EVIDENCE_ONLY / OFFLINE_SHADOW / P0_PRODUCTION_FULL_SCAN_AUTHORITY_FALSE`

> 2026-09-14 갱신: 첫 합성 tranche 계약을 보존한 채 후보 회수·선택 진단 단위를 구현·실측했다. 현재 범위와 다음 단위는 [goal.md](../../goal.md), 오케스트레이션 근거는 [진단 보고서](RESEARCH_CANDIDATE_SELECTION_DIAGNOSTICS_20260914_KO.md)와 [Astra 인계 문서](GPT6_ASTRA_RESEARCH_HANDOFF_20260906_KO.md)를 따른다. 실제 로컬 LLM 품질 미측정은 계속 구분한다.

## 1. 범위 재정의

현재 활성 목표는 권리 안전 데이터로 로컬 LLM grounding 후보 회수·재순위화·NIL 판정을 비교하는 재현 가능한 연구 벤치마크다. 외부 fixed store, owner key/signature, trusted time/revocation/durable nonce, native runtime/write-deny witness, 외부 review authority/key/lease/CAS, primary terminal 80건, owner-signed numerical policy는 **생산 승격용 `DEFERRED_P0_AUDIT_TRACK`**에 보존한다. 해당 항목의 미충족은 이 연구 실행을 막지 않는다.

과거 P0 결과는 폐기하거나 성공으로 바꾸지 않는다. 향후 production/publication/full-scan 전환을 검토할 때만 다시 gate로 적용한다.

## 2. 전문가 회의 채택안

문서·코드·측정 세 분과의 독립 감사를 종합해 다음을 채택했다.

1. 기존 `expert_main.py`와 production WAL에는 벤치마크를 연결하지 않고 `research.*.offline_shadow` namespace의 별도 runner를 둔다.
2. 출처가 불분명한 기존 산출물 대신 저장소에서 직접 만든 16건 합성 fixture를 사용한다. 각 행에 source와 retention을 기록한다.
3. single-curator gold-lite를 허용하되 결과를 보지 않은 별도 blind recheck를 전체의 최대 25%로 제한한다.
4. 단순 lexical baseline, 순수 Python BM25, lexical reranker+NIL/ABSTAIN, 로컬 OpenAI-compatible LLM의 네 arm을 같은 입력에서 비교한다.
5. Pyserini·sentence-transformers·모델 weights는 필수 dependency로 추가하지 않는다. 없는 arm은 자동 대체하지 않고 `UNAVAILABLE_*`로 남긴다.
6. `ERROR`, `UNAVAILABLE`, `ABSTAIN`, `NIL`을 headline 분모에서 제외하지 않는다. evaluable-only 수치는 보조 진단으로만 둔다.
7. 실제 validation run은 standalone 웹 대시보드가 응답해야 시작하고, requested `--parallel 16`, effective `min(16,input_count)`를 manifest에 기록한다.
8. 입력/gold/config/prompt/구현/runner/pyproject SHA, Git commit+dirty, 모델 ID 또는 unavailable 상태, seed, Python/OS/dependency 버전을 고정한다.
9. output은 `out/research/` 아래 새 디렉터리에만 기록하며 중앙 Slang DB, production/publication journal에는 쓰지 않는다.

## 3. 구현 산출물

- 실행 코어: `src/llm_batch/grounding/research_local_benchmark.py`
- CLI: `tools/run_research_local_benchmark.py`
- 권리 안전 fixture: `tests/fixtures/research_local_benchmark_v1.jsonl`
- 계약 테스트: `tests/test_research_local_benchmark.py`
- 런 산출물: `out/research/<run>/manifest.json`, `predictions.json`, `metrics.json`, `report_ko.md`

## 4. 단계별 실험

| 단계 | arm | 목적 | 부재/실패 처리 |
|---|---|---|---|
| R0 | `lexical_baseline` | exact title·alias·token overlap 기준선 | 예외는 `ERROR` |
| R1 | `bm25_fixture_corpus_retriever` | 고정 tokenizer와 fixture 전체 공통 corpus BM25 회수 | 예외는 `ERROR` |
| R2 | `bm25_reranker_nil` | BM25+lexical 재순위와 threshold/margin | `NIL` 또는 `ABSTAIN` 명시 |
| R3 | `local_llm` | loopback 또는 명시적으로 허용한 `expert_main.py` configured vLLM OpenAI-compatible endpoint A/B | 모델/endpoint 부재는 `UNAVAILABLE` |

첫 diagnostic run에서는 검증된 endpoint가 없어 R3를 `UNAVAILABLE`로 보존했다. 이후 `expert_main.py`에 이미 기록된 `LLM_SERVER_TYPE=vllm`, endpoint `http://10.20.0.101:8000/`, model `unsloth/gemma-4-26B-A4B-it-NVFP4`를 읽고 `/v1/models`(`owned_by=vllm`)와 benchmark completion을 검증했다. runner는 기본적으로 loopback 이외 endpoint를 거부하며, 이번 endpoint는 `--allow-configured-remote-vllm` 명시적 opt-in과 `enable_thinking=false` 요청 계약으로만 사용했다. 별도 로컬 PC `llama-server` 기동이나 모델 설치는 정본 실행에 포함하지 않았다. 현재 BM25는 각 query의 행별 후보가 아니라 fixture 전체 후보를 합친 공통 corpus에서 회수한다. 다만 외부 open corpus가 아닌 `FIXTURE_CORPUS_RETRIEVAL`이므로 실제 웹 검색 성능으로 확대 해석하지 않는다.

## 5. acceptance gate

- [x] fixture 16건 전부 `SYNTHETIC`, source·retention, gold-lite 메타데이터를 가진다.
- [x] blind recheck 4/16으로 최대 25%를 넘지 않으며 gold와 일치한다.
- [x] 네 arm이 입력마다 정확히 한 terminal 결과를 반환한다.
- [x] 기본 실행에서는 loopback이 아닌 LLM endpoint를 거부하고, configured remote vLLM은 명시적 opt-in으로만 허용한다.
- [x] 중앙 DB·publication 권위가 코드·manifest에서 false/0으로 고정된다.
- [x] actual validation에서 dashboard pre/post health가 기록된다.
- [x] actual validation manifest의 requested/effective parallel이 `16/16`이다.
- [x] metrics에서 각 arm 분모가 16이고 `UNAVAILABLE/ABSTAIN/NIL/ERROR` 보존을 확인한다.
- [x] focused tests, 재현성 검사, P0 protected endpoint 비간섭 감사를 통과한다.

첫 terminal tranche의 정본 run은 `out/research/research_local_benchmark_20260905_v10`이다. manifest `e0e1a726…7b0c`, semantic output `13bbe5b8…d83c`이며 V9/V10 반복 semantic hash가 일치했다. dashboard `http://127.0.0.1:8765`, requested/effective `16/16`, terminal 합계는 `RESOLVED 44 / NIL 4 / ABSTAIN 0 / UNAVAILABLE 16 / ERROR 0`이다. 독립 terminal validator와 hash 변조 회귀를 통과했고 protected central Slang DB 1개와 publication journal 5개는 `6/6` byte/SHA 불변이다.

구현·측정/manifest·문서 세 분과의 최종 독립 재감사 결론은 모두 `PASS / acceptance blocker 0`이다.

## 5-1. 2026-09-14 후보 회수·선택 진단 acceptance

- [x] 기존 `research_local_benchmark_v1.jsonl` 16건과 bytes를 보존하고, 4건 challenge를 `CANDIDATE_MISS`·`COMPARISON_SELECTION`·`ACTUAL_NIL`·`AMBIGUOUS`로 검증한다.
- [x] 기존 score semantics를 유지하면서 공통 BM25 top-5 retrieval trace, arm별 selection trace, gold 포함 여부와 `failure_stage`를 저장한다.
- [x] WORK truth 기준 Recall@1/3/5와 정답 포함 조건부 selection을 전체 terminal accuracy와 분리한다.
- [x] baseline run `out/research/research_candidate_diagnostics_20260914_baseline`은 requested/effective `16/16`, challenge run `out/research/research_candidate_diagnostics_20260914_challenge`는 `16/4`다.
- [x] 두 run의 dashboard pre/post receipt가 `CONNECTED`, 독립 terminal validator와 artifact self-hash 검증이 `PASS`다.
- [x] focused `tests.test_research_local_benchmark` `10/10 PASS`, 변경 Python 세 파일 `py_compile PASS`를 확인한다.

판정: `CANDIDATE_SELECTION_DIAGNOSTICS_COMPLETE / RESEARCH_EVIDENCE_ONLY`. challenge는 설계된 synthetic diagnostic이며 외부 open-corpus 검색 성능이나 P0·production·publication·full-scan 승인을 주장하지 않는다.

## 5-2. 2026-09-14 실행·검증 workflow acceptance

- [x] `tools/run_research_local_benchmark_workflow.py`가 standalone dashboard 재사용/기동, baseline·challenge runner, terminal manifest validator, focused unittest를 한 번에 묶는다.
- [x] workflow는 요청 병렬도 `--parallel 16`을 강제하고 입력 수에 따라 baseline `16`, challenge `4`의 effective parallel을 기록한다.
- [x] 기존 산출물을 덮어쓰지 않고 새 `out/research/research_workflow_20260914_automated_e2e` 아래에 child artifact, 로그, workflow manifest, 한국어 report를 기록했다.
- [x] 실제 end-to-end 실행에서 dashboard `CONNECTED`, child validator `PASS`, focused `14/14 PASS`, workflow manifest self-hash `PASS`를 확인했다.
- [x] local LLM 인자를 제공하지 않은 실행은 `UNAVAILABLE_MODEL_IDENTITY`와 `UNAVAILABLE` terminal을 유지했으며 모델 설치·대체를 하지 않았다.

판정: `RESEARCH_WORKFLOW_AUTOMATION_COMPLETE / RESEARCH_EVIDENCE_ONLY`. 이 wrapper는 연구 runner의 score semantics를 재구현하지 않으며 P0·production·publication·full-scan 승인 근거가 아니다.

## 5-3. 2026-09-14 expert_main configured vLLM 연결 acceptance

- [x] `expert_main.py`의 vLLM endpoint `http://10.20.0.101:8000/`와 model `unsloth/gemma-4-26B-A4B-it-NVFP4`를 읽고 `/v1/models`에서 `owned_by=vllm`을 확인한다.
- [x] `enable_thinking=false`와 `chat_template_kwargs.enable_thinking=false`를 benchmark request에 넣어 vLLM의 reasoning-only 응답을 방지한다.
- [x] `--allow-configured-remote-vllm`을 명시한 새 workflow를 실행하고, dashboard `CONNECTED`, requested/effective `16/16`, `16/4`, child validator `PASS`를 기록한다.
- [x] 정본 산출물 `out/research/research_workflow_20260914_expert_main_vllm`에서 baseline local_llm `16/16`, challenge local_llm `1/4`, 두 arm 모두 `UNAVAILABLE=0`을 확인한다.
- [x] focused test `16 tests OK`, 대상 파일 `py_compile PASS`, 중앙 Slang DB·production/publication 쓰기 `0`을 확인한다.

판정: `CONFIGURED_VLLM_RESEARCH_RUN_COMPLETE / RESEARCH_EVIDENCE_ONLY`. baseline·challenge 정확도는 synthetic fixture 관측치이며 일반화된 성능 향상이나 production 승격 근거가 아니다.

## 6. 해석 한계와 후속

합성 16건 결과는 기능·회계·재현성 smoke evidence다. 실제 DC 커뮤니티 성능, P0 actual 40+20, production 안전성 또는 full scan 승인을 뜻하지 않는다. 관측 정확도는 lexical `14/16`, fixture-corpus BM25 `12/16`(WORK truth Hit@3 `12/12`), reranker+NIL `14/16`; local LLM은 weights 부재로 `UNAVAILABLE 16/16`이고 A/B delta는 `NOT_ESTIMABLE`이다. reranker의 baseline 대비 delta도 `0`이므로 품질 개선을 입증했다고 쓰지 않는다.

후속 단위는 검증된 local LLM weights/endpoint A/B, 권리 확인 데이터 확대, 필요 시 open-corpus/dense/RRF·학습 reranker 비교다. 이번 진단에서 local LLM `UNAVAILABLE`을 품질 점수로 바꾸거나 P0 authority를 확장하지 않는다.

권리 확인 데이터 추가, 실제 로컬 모델 fingerprint 고정과 비교, 외부 open-corpus/dense/RRF·학습 reranker는 각각 별도 후속이다. 현재 완료조건에 함께 묶지 않는다. 생산 승격이 필요해질 때에만 `DEFERRED_P0_AUDIT_TRACK`을 다시 활성화한다.
