# 웹 ChatGPT 오케스트레이션 헤드 미션

## 목적

이 저장소의 현재 연구 목표를 기준으로 다음 구현·검증 일감을 분해하고 우선순위를 판단한다. 너는 실행 담당자가 아니라 오케스트레이션 헤드이며, 최종 산출물은 근거가 있는 작업 배분안이다.

## 읽기 범위

정확한 프로젝트 루트에서 적용되는 AGENTS.md를 먼저 읽고, 다음 파일을 실제로 확인한다.

- goal.md
- docs/devs/GPT6_ASTRA_RESEARCH_HANDOFF_20260906_KO.md
- docs/devs/RESEARCH_ONLY_LOCAL_LLM_BENCHMARK_PLAN_20260905_KO.md
- docs/devs/TODO.md
- docs/devs/CHECKLIST.md
- src/llm_batch/grounding/research_local_benchmark.py
- tools/run_research_local_benchmark.py
- tests/test_research_local_benchmark.py
- tests/fixtures/research_local_benchmark_v1.jsonl

필요하면 위 범위의 인접 코드와 문서를 추가로 읽되, 저장소 밖 자료나 외부 웹 검색으로 결론을 보강하지 않는다.

## 현재 요청

기존 16건 합성 fixture의 회계·재현성 계약을 보존하면서 후보 회수 실패, 후보가 포함된 뒤의 선택 실패, 실제 NIL, ABSTAIN을 분리 측정하는 다음 단위를 계획한다. 기존 fixture와 별도 challenge fixture의 분모를 분리하고, 각 arm의 전체 terminal 분모와 행별 실패 원인을 보존해야 한다. 로컬 LLM weights가 없을 때 UNAVAILABLE을 정직하게 유지하며, P0 authority·production·publication·full-scan 승인으로 확장하지 않는다.

## 판단할 내용

1. 현재 저장소 상태와 목표 대비 남은 작업을 짧게 요약한다.
2. 구현, fixture/데이터 계약, 테스트, dashboard 실행·검증, 한국어 문서 갱신을 서로 의존성이 드러나는 작업 패키지로 나눈다.
3. 각 패키지에 우선순위, 선행 조건, 담당 실행 주체(현재 coding agent 또는 후속 담당), 수정 대상, 산출물, acceptance gate를 지정한다.
4. 가장 작은 안전한 다음 실행 단위와 그 이유를 선택한다. 불필요한 모델 weights 설치, 외부 open corpus, production/P0 wiring은 제외한다.
5. 현재 코드 계약을 깨지 않기 위한 회귀 위험, 기존 16건 보존 방법, requested/effective --parallel 16, dashboard ON, RESEARCH_EVIDENCE_ONLY 경계를 명시한다.
6. 권장 실행 순서와 검증 명령을 제안한다. 결과 문서는 자연스러운 한국어로 작성하고, 근거가 없는 수치나 완료 선언은 하지 않는다.

## 출력 형식

다음 순서로 간결하지만 실행 가능한 한국어 답변을 작성한다.

1. 판단 요약
2. 우선순위 작업 패키지 표
3. 즉시 실행할 한 단위
4. 검증·문서 게이트
5. 보류·금지 범위

파일을 만들거나 수정하지 말고, 명령을 실행하거나 외부 상태를 변경하지 말라. 읽기 전용 분석과 작업 배분 판단만 수행한다.
