# 후보 회수·선택 진단 실측 보고서

작성일: 2026-09-14 KST <br>
판정: `CANDIDATE_SELECTION_DIAGNOSTICS_COMPLETE / RESEARCH_EVIDENCE_ONLY` <br>
범위: `research.synthetic.offline_shadow`

## 목적

기존 합성 16건의 회계·재현성 계약을 보존하면서 후보 회수 실패, 후보가 포함된 뒤의 선택 실패, 실제 `NIL`, `ABSTAIN`을 분리한다. 기존 fixture와 challenge fixture는 코퍼스와 분모가 섞이지 않도록 독립 실행했다.

## 오케스트레이션과 커넥터

- 웹 ChatGPT를 오케스트레이션 헤드로 사용했고, 앱 이름은 `Codex-kimjang-home`, 실제 선택 모델은 `6 Pro`, effort는 `pro`였다.
- 전체 오케스트레이션 결과는 `C:\Users\kimjang\.codex\state\chatgpt-oracle\ordinary\projects\fd17873b4a678ceb71f41b12\runs\20260914T122929Z-f576a8f56de8\output.md`에 보존했다.
- `C:\Users\kimjang\.codex\chatgpt-workspace.json`의 앱 alias와 `.devspace` 허용 root를 확인했다. 저장소 root는 이미 허용 목록에 있어 계정 설정·앱 등록·권한을 임의 변경하지 않았다.
- 최초 `@codex` alias 시도는 root 접근 오류로 중단됐고, 올바른 `Codex-kimjang-home` alias로 dry-run 후 재실행해 실제 결과를 캡처했다.

## 구현

- `src/llm_batch/grounding/research_local_benchmark.py`: case/action 계약, 공통 BM25 top-5 retrieval trace, arm별 selection trace, Recall@K, 조건부 selection, failure stage, terminal validator를 추가했다.
- `tools/run_research_local_benchmark.py`: partition·diagnostic schema·artifact/manifest/report 기록을 추가했다. 기존 fixture bytes는 변경하지 않았다.
- `tests/fixtures/research_local_benchmark_challenge_v1.jsonl`: 후보 누락·비교작 선택·실제 NIL·모호함 4건을 추가했다.
- `tests/test_research_local_benchmark.py`: challenge 분리, 회수/선택 분리, action/failure stage, manifest 보존 회귀를 추가했다.

## 실측 결과

| run | 입력 | requested/effective | lexical | BM25 | reranker+NIL | local LLM |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 16 | `16/16` | `14/16` | `12/16` | `14/16` | `UNAVAILABLE 16/16` |
| challenge | 4 | `16/4` | `1/4` | `0/4` | `0/4` | `UNAVAILABLE 4/4` |

- baseline의 공통 WORK Recall@5는 각 arm `12/12`, 조건부 selection은 local LLM을 제외한 각 arm `12/12`다.
- challenge의 공통 WORK Recall@5는 각 arm `2/3`이다. 조건부 selection은 lexical `1/2`, BM25와 reranker `0/2`, local LLM은 `NOT_ESTIMABLE`이다.
- challenge의 failure stage는 `SELECTION_FAILURE_WRONG_CANDIDATE`, `NIL_MISCLASSIFICATION`, `AMBIGUOUS_NON_ABSTAIN`, `CORRECT_ABSTAIN`, `UNAVAILABLE`로 구분된다.
- `ERROR`, `UNAVAILABLE`, `ABSTAIN`, `NIL`은 전체 입력 분모에서 제거하지 않았다. local LLM의 `UNAVAILABLE`은 품질 점수가 아니다.

## 게이트와 산출물

- `python -m unittest tests.test_research_local_benchmark -v`: `10/10 PASS`.
- `python -m py_compile` 대상인 코어·runner·test 세 파일: `PASS`.
- baseline과 challenge의 독립 `validate_terminal_manifest(..., research_root=out/research)`: `PASS`.
- standalone dashboard `http://127.0.0.1:8765`: 두 run 모두 pre/post `ok=true`, `standalone=true`, `CONNECTED`.
- 산출물: `out/research/research_candidate_diagnostics_20260914_baseline/manifest.json`, `predictions.json`, `metrics.json`, `report_ko.md`; challenge도 같은 파일 구성을 가진다.
- 중앙 Slang DB·production/publication journal 쓰기: `0`.

## 실행 workflow 후속

- `tools/run_research_local_benchmark_workflow.py`가 dashboard 준비, baseline·challenge 실행, child manifest validator, focused test, workflow report를 묶는다.
- 실제 산출물: `out/research/research_workflow_20260914_automated_e2e`.
- 결과: baseline requested/effective `16/16`, challenge `16/4`, dashboard `CONNECTED`, child validator `PASS`, focused `14/14 PASS`.
- workflow는 local LLM weights를 설치하지 않았고 `UNAVAILABLE`을 그대로 보존했다. 기존 두 diagnostic run은 덮어쓰지 않았다.

## expert_main configured vLLM 연결 후속 실측

앞선 `UNAVAILABLE`은 endpoint 부재 시의 정직한 baseline 기록이다. 2026-09-14에 `expert_main.py`의 기존 vLLM 설정을 사용해 별도 새 output에서 연결을 검증했다.

- endpoint: `http://10.20.0.101:8000/`
- model: `unsloth/gemma-4-26B-A4B-it-NVFP4`
- provider/model 확인: `/v1/models` `owned_by=vllm`, system fingerprint `vllm-0.26.0-tp2-ep-d96fcb7f`
- endpoint scope: `CONFIGURED_REMOTE_VLLM` (기본 loopback guard를 유지한 명시적 opt-in)
- request contract: `enable_thinking=false`, `chat_template_kwargs.enable_thinking=false`
- 산출물: `out/research/research_workflow_20260914_expert_main_vllm`

| partition | 입력 | requested/effective | local_llm terminal | local_llm 정확도 |
|---|---:|---:|---|---:|
| baseline | 16 | `16/16` | `RESOLVED 12 / NIL 4 / UNAVAILABLE 0` | `16/16 (1.0)` |
| challenge | 4 | `16/4` | `RESOLVED 3 / ABSTAIN 1 / UNAVAILABLE 0` | `1/4 (0.25)` |

전체 partition terminal도 baseline `RESOLVED 56 / NIL 8 / ABSTAIN 0 / UNAVAILABLE 0 / ERROR 0`, challenge `RESOLVED 14 / NIL 0 / ABSTAIN 2 / UNAVAILABLE 0 / ERROR 0`으로 manifest에 보존했다. dashboard `CONNECTED`, child validator `PASS`, focused `16 tests OK`, workflow self-hash `66d7efe9095e799b517685e17b6a74493346d61c5115ebf2a3d5f34a96b3cf9b`이다.

이 수치는 rights-safe synthetic fixture의 연구 evidence다. baseline `16/16`을 성능 향상으로 승격하지 않으며, challenge의 `CANDIDATE_RECALL_MISS`, `SELECTION_FAILURE_WRONG_CANDIDATE`, `NIL_MISCLASSIFICATION`, `AMBIGUOUS_NON_ABSTAIN`을 별도 실패 단계로 유지한다. 정본 workflow는 로컬 PC `llama-server`를 사용하지 않았고, 모델 설치·중앙 Slang DB·production/publication 쓰기도 없었다.

## 2026-09-15 workflow 재개 검증

configured vLLM endpoint와 모델 identity fingerprint를 모두 명시한 새 output `out/research/research_workflow_20260915_resume_vllm`을 실행했다. baseline은 전체 terminal `RESOLVED 55 / NIL 8 / ABSTAIN 1 / UNAVAILABLE 0 / ERROR 0`, challenge는 `RESOLVED 14 / NIL 0 / ABSTAIN 2 / UNAVAILABLE 0 / ERROR 0`이었다. requested/effective parallel은 각각 `16/16`, `16/4`, dashboard는 `CONNECTED`, child validator와 focused workflow test는 `PASS`였다.

이번 재개에서 workflow builder가 endpoint·model·fingerprint 일부만 받거나 configured remote opt-in만 단독으로 받지 않도록 fail-closed 회귀를 추가했다. baseline의 새 `ABSTAIN`은 이전 remote completion과 다른 관측이며 성능 변화로 일반화하지 않는다. challenge의 네 failure stage와 전체 terminal 분모는 그대로 보존한다.

## 2026-09-15 workflow-level 진단 보존

child `metrics.json`에 이미 존재하던 `case_type_counts`, `expected_action_counts`, `failure_stage_counts`, `candidate_recall`, `conditional_selection`을 workflow manifest의 arm별 `diagnostics`로 전달하고, `report_ko.md`의 `진단 보존` 절에 표시하도록 wrapper를 확장했다. score semantics나 child validator 계산은 바꾸지 않았다.

최종 output `out/research/research_workflow_20260915_diagnostics_manifest_vllm_v2`에서 baseline 전체 terminal은 `RESOLVED 56 / NIL 8 / ABSTAIN 0 / UNAVAILABLE 0 / ERROR 0`, challenge는 `RESOLVED 14 / NIL 0 / ABSTAIN 2 / UNAVAILABLE 0 / ERROR 0`이었다. requested/effective는 각각 `16/16`, `16/4`, dashboard는 `CONNECTED`였다.

workflow-level challenge `local_llm` 진단은 `CANDIDATE_RECALL_MISS`, `SELECTION_FAILURE_WRONG_CANDIDATE`, `NIL_MISCLASSIFICATION`, `AMBIGUOUS_NON_ABSTAIN` 각 1건, Recall@5 `2/3`, 조건부 selection `0/1`로 child metrics와 일치했다. workflow self-hash·child validator·focused `18 tests OK`를 통과했다. 이는 진단 보존 회귀이며 성능 향상 주장이 아니다. v1과 v2의 baseline terminal 차이는 remote completion 관측 변동으로 보존하며 일반화하지 않는다.

## 2026-09-15 challenge-001 후보 회수 경계 분석

새 artifact `out/research/research_candidate_recall_20260915/analysis_ko.md`에서 `challenge-001`의 18개 후보 전체를 대상으로 현재 BM25를 재계산했다. top-5는 `work-miss-blue-contract`, `work-miss-cargo-contract`, `work-miss-blue-comet`, `work-miss-comet-log`, `work-miss-captain-return`이고 gold `work-hidden-aurora-freighter`는 포함되지 않았다. gold text `고립된 항성계의 선박 일지`와 query 사이에도 현재 tokenizer가 사용할 lexical anchor가 없다.

따라서 이 known-bad case는 selection prompt 문제가 아니라 candidate-generation 경계의 `CANDIDATE_RECALL_MISS`로 확인했다. 이번 단위에서는 기존 BM25 score semantics를 변경하지 않았고, verified semantic candidate-generation arm을 기존 arm과 분리하는 별도 승인 단위로 보류했다.

## 제한과 보류

이 결과는 권리 메타데이터가 있는 synthetic fixture의 구조·회계·실패 단계 진단이다. fixture corpus는 외부 open corpus가 아니므로 실제 웹 검색 성능으로 확대 해석하지 않는다. local LLM weights/endpoint A/B, 권리 확인 데이터 확대, dense/RRF·학습 reranker 비교는 후속 단위다. `DEFERRED_P0_AUDIT_TRACK`의 external authority, production, publication, full-scan gate는 이번 결과로 열리지 않는다.
