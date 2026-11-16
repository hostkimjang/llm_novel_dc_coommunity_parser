# 전문가 실행 안내

`expert_main.py`는 커뮤니티 원문·댓글을 읽고 여러 전문가의 판단과 검색 근거를 모아 작품·담론 분석 결과를 저장합니다. 설치와 기본 실행은 [README](README.md)를 참고하세요.

## 처리 흐름

1. 입력과 실행 설정을 확인하고 대시보드·checkpoint·manifest를 준비합니다.
2. Gatekeeper와 Discourse가 원문의 주제, 발화 역할, 작품 관련성을 판단합니다.
3. Decoder가 약어·제목 후보를 만들고 Verifier가 검색·공식 출처와 원문의 관계를 확인합니다.
4. Synthesizer가 흩어진 근거를 재해석하고(근거가 없으면 생략) Arbiter가 최종 판단을 정리합니다.
5. `agentic_pipeline`이 문맥·후보·상태 일관성과 공개 조건을 확인하고, `expert_main`이 결과·원장을 저장합니다.

Orchestrator가 상황과 예산에 따라 다음 전문가·검색을 선택하므로 모든 게시글이 같은 순서나 호출 수로 처리되지는 않습니다.

## 전문가 역할

| 구성원 | 주요 역할 |
| --- | --- |
| Orchestrator | 전문가·검색 라우팅, 협업 문맥과 반복 예산 관리 |
| Gatekeeper | 원문 분류, 관련성, 엔티티·노이즈 판단 |
| Discourse | 발화·도메인·대상 작품과 인용·비유·질문 역할 분석 |
| Decoder | 약어·초성·별칭에서 작품 후보 생성 |
| Verifier | 원문과 후보의 관계, 공식 제목·URL 및 출처 검증 |
| Critic | 다른 전문가 분석의 메타 검토. 기본 경로에서는 Arbiter가 이 역할을 처리하고, 협력 요청 같은 일부 경로에서만 따로 호출 |
| Synthesizer | 분산된 근거·댓글·참조 종합 |
| Arbiter | 전문가 판단을 종합해 최종 분석안 작성 |

구현은 [`src/llm_batch/experts/`](src/llm_batch/experts/)와 [`agentic_pipeline.py`](src/llm_batch/agentic_pipeline.py)에 있습니다.

## 입력·저장 계약

- 본문·댓글의 원문과 화자·발화 역할을 구분합니다. 댓글에서 찾은 근거를 게시글 작성자의 발언으로 바꾸지 않습니다.
- 작품 후보, 문맥상 언급, 공식 제목·URL, 실제 공개 판정을 나눠 저장합니다. 형태 유사도나 후보 점수만으로 원문의 작품 관계를 확정하지 않습니다.
- `아생갤` 같은 `갤러리` 표면도 실제 작품 제목·약어일 수 있습니다. 명시 alias 관계, 구체적인 작품 대상과 공식·커뮤니티 근거를 함께 확인합니다.
- NSFW 판정은 규칙에 걸린 경우, 모델이 판단한 경우, 평가하지 않은 경우를 구분합니다. OCR 텍스트를 읽었다고 이미지 자체를 검토했다고 보지 않습니다.
- 과거 결과에 없는 필드는 `미기록`으로 표시하고, 새 코드의 해석으로 과거 원본을 덮어쓰지 않습니다.

## 실행 옵션

테스트·검증은 다음 예시를 기준으로 합니다.

```powershell
python expert_main.py tests/inputs/sample.jsonl --parallel 12 --execution-profile low-load-validation --output out/example/result.json
```

| 옵션 | 용도 |
| --- | --- |
| `--parallel 12` | 요청 병렬도. 실제 병렬도는 manifest에서 확인 |
| `--execution-profile low-load-validation` | 프로세스를 CPU 하나·낮은 우선순위로 제한하고 VLM·OCR, 호출 원장 기록(`SHADOW`), 문맥 진단을 기본으로 켬. `--parallel`을 주지 않으면 요청 병렬도 1 |
| `--llm-endpoint`, `--llm-model` | HTTP LLM 서버·모델 지정 |
| `--vlm on --ocr on --require-vlm-ocr-for-images` | 이미지 게시글을 VLM·OCR로 처리. 이미지 게시글이 있는데 VLM·OCR 중 하나라도 꺼져 있으면 시작 전에 실패 |
| `--context-diagnostics on` | 원문 문맥·발화 구조 진단을 크기 제한 안에서 저장 |
| `--decision-call-ledger SHADOW` | 실제 LLM 호출과 사용량을 호출 원장에 기록 |
| `--decision-call-ledger REQUIRED` | 비교 계측용. 미리 정한 실행 계획(RunSpec·pair·arm)과 연결돼야 실행되고, 계측이 실패하면 실행도 실패로 처리 |
| `--native-recovery ON` | 분석이 끝난 뒤, 정책 파일에 정한 예산 안에서 native 복구를 별도로 실행 |

실제로 적용되는 설정은 CLI, 환경 변수, 프로필, 기본값 순서로 정해집니다. 선택할 수 있는 값과 필요한 정책 파일은 `python expert_main.py --help`, [자동 복구](docs/devs/NATIVE_RECOVERY_AUTOMATION_20261010_KO.md), [계측 안내](docs/devs/PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md)를 확인하세요.

## 대시보드와 이력

기본 주소는 `http://127.0.0.1:8080`입니다. standalone 서버를 먼저 띄우면 실행이 끝난 뒤에도 이력을 볼 수 있습니다. 서버 포트와 `DASHBOARD_PORT` 또는 `DASHBOARD_URL`을 맞춥니다.

화면에서는 진행률·활성 작업·로그, 분석 메모, NSFW 상태, 문맥 진단, 중첩 이력, 실행 설정과 종료 계측을 확인합니다. 실시간 이벤트로 합산한 토큰 수와 manifest의 호출 원장 사용량은 집계 범위가 달라 서로 다를 수 있습니다.

이력 탐색에는 상한이 있습니다. 서버가 현재 실행(current)의 출력으로 확인한 위치는 최근 24개까지 서버 메모리에만 보존되므로, 서버를 재시작하면 사라집니다. `BOUND`는 결과 파일과 연결된 저장 자료가 서로 일치한다는 표시이며 품질 승인이 아닙니다. 테마와 재시작 절차는 [대시보드 운영 문서](docs/devs/EXPERT_DASHBOARD_DESIGN_KO.md)에 있습니다.

## 후보 연구·복구 기능

후보 회수·재정렬·의미 역할·교정·inference 기능은 미리 고정한 corpus·모델·bundle로 결과를 계산해 기록만 합니다. 기본값은 `OFF`이고, `SHADOW`로 켜도 공개 판정에는 반영되지 않습니다. 이 기능을 켰다고 정식 학습이나 독립 성능 평가를 마친 것은 아닙니다.

관련 문서는 [후보 회수](docs/devs/CANDIDATE_RETRIEVAL_SHADOW_20261010_KO.md), [재정렬·교정](docs/devs/CANDIDATE_RERANKER_SHADOW_20261010_KO.md), [R4 연결](docs/devs/R4_ACTUAL_BRIDGE_20261010_KO.md), [커뮤니티 지식](docs/devs/COMMUNITY_KNOWLEDGE_READ_ONLY_20261010_KO.md)에 있습니다.

## 검증과 문제 조사

manifest에서 실행 ID, 입력, 요청·실제 병렬도, 종료 상태를 먼저 확인합니다. 개별 문제는 worker 로그, 원문·후보·출처, checkpoint·공개 원장을 함께 대조합니다. 같은 설정으로 두 번 돌린 결과(A/A)나 정상 종료만으로 개선율·정답률을 계산하지 않습니다.

패키지별 구현은 [소스 구조](docs/devs/SOURCE_LAYOUT_KO.md), 순차 실행기는 [레거시 안내](README_legacy_pipeline.md)를 참고하세요.
