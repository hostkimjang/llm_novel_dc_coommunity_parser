# 전문가 실행 안내

`expert_main.py`는 커뮤니티 원문·댓글을 읽고 여러 전문가의 판단과 검색 근거를 모아 작품·담론 분석 결과를 저장합니다. 설치와 기본 실행은 [README](README.md), 완료 범위는 [현재 상태](docs/devs/CURRENT_STATUS_KO.md)를 기준으로 합니다.

## 처리 흐름

1. 입력과 실행 설정을 확인하고 대시보드·checkpoint·manifest를 준비합니다.
2. Gatekeeper와 Discourse가 원문의 주제, 발화 역할, 작품 관련성을 판단합니다.
3. Decoder가 약어·제목 후보를 만들고 Verifier가 검색·공식 출처와 원문의 관계를 확인합니다.
4. 필요한 경로에서 Critic·Synthesizer·Arbiter가 담론, 근거, 최종 판단을 정리합니다.
5. `agentic_pipeline`이 문맥·후보·상태 일관성과 공개 조건을 확인하고 결과·원장을 저장합니다.

Orchestrator가 상황과 예산에 따라 다음 전문가·검색을 선택하므로 모든 게시글이 같은 순서나 호출 수로 처리되지는 않습니다.

## 전문가 역할

| 구성원 | 주요 역할 |
| --- | --- |
| Orchestrator | 전문가·검색 라우팅, 협업 문맥과 반복 예산 관리 |
| Gatekeeper | 원문 분류, 관련성, 엔티티·노이즈 판단 |
| Discourse | 발화·도메인·대상 작품과 인용·비유·질문 역할 분석 |
| Decoder | 약어·초성·별칭에서 작품 후보 생성 |
| Verifier | 원문과 후보의 관계, 공식 제목·URL 및 출처 검증 |
| Critic | 담론·감성·NSFW 등 분석 |
| Synthesizer | 분산된 근거·댓글·참조 종합 |
| Arbiter | 전문가 판단을 종합해 최종 분석안 작성 |

구현은 [`src/llm_batch/experts/`](src/llm_batch/experts/)와 [`agentic_pipeline.py`](src/llm_batch/agentic_pipeline.py)에 있습니다. 오래된 코드 줄 수나 고정 반복 횟수를 현재 계약으로 사용하지 않습니다.

## 입력·저장 계약

- 본문·댓글의 원문과 화자·발화 역할을 구분합니다. 댓글에서 찾은 근거를 게시글 작성자의 발언으로 바꾸지 않습니다.
- 작품 후보, 문맥상 언급, 공식 제목·URL, 실제 공개 판정을 나눠 저장합니다. 형태 유사도나 후보 점수만으로 원문의 작품 관계를 확정하지 않습니다.
- `아생갤` 같은 `갤러리` 표면도 실제 작품 제목·약어일 수 있습니다. 명시 alias 관계, 구체적인 작품 대상과 공식·커뮤니티 근거를 함께 확인합니다.
- NSFW의 규칙 양성, 모델 판단, 미평가 상태를 구분합니다. OCR 텍스트를 이미지 픽셀 검토로 간주하지 않습니다.
- 과거 결과에서 저장하지 않은 필드는 미기록으로 표시합니다. 새 코드의 해석으로 과거 원형을 덮어쓰지 않습니다.

## 실행 옵션

테스트·검증은 다음 예시를 기준으로 합니다.

```powershell
python expert_main.py tests/inputs/sample.jsonl --parallel 12 --execution-profile low-load-validation --output out/example/result.json
```

| 옵션 | 용도 |
| --- | --- |
| `--parallel 12` | 요청 병렬도. 실제 병렬도는 manifest로 확인 |
| `--execution-profile low-load-validation` | CPU 부하 제한·문맥 진단·호출 관측 기본값 적용 |
| `--llm-endpoint`, `--llm-model` | HTTP LLM 서버·모델 지정 |
| `--vlm on --ocr on --require-vlm-ocr-for-images` | 이미지가 있는 회귀에서 VLM/OCR 요구 명시 |
| `--context-diagnostics on` | 크기 제한이 있는 문맥·발화 진단 저장 |
| `--decision-call-ledger SHADOW` | 실제 호출·사용량 관측 |
| `--decision-call-ledger REQUIRED` | 기존 측정 결속 조건을 요구하는 실행 |
| `--native-recovery ON` | 명시 정책·예산에 따른 native 복구 연결 |

CLI·환경 변수·프로필·기본값 순서로 유효 설정이 정해집니다. 세부 선택값과 필요한 정책 파일은 `python expert_main.py --help`, [자동 복구](docs/devs/NATIVE_RECOVERY_AUTOMATION_20261010_KO.md), [계측 안내](docs/devs/PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md)를 확인하세요.

## 대시보드와 이력

기본 주소는 `http://127.0.0.1:8080`이며 standalone 서버를 먼저 띄우면 실행 종료 후에도 이력을 조회할 수 있습니다. 서버 포트와 `DASHBOARD_PORT` 또는 `DASHBOARD_URL`을 맞춥니다.

진행률·활성 작업·로그, 분석 메모, NSFW 상태, 문맥 진단, 중첩 이력, 실행 설정과 종료 계측을 확인합니다. live 이벤트 토큰 합계와 manifest의 호출 원장 사용량은 수집 범위가 다르므로 각각의 표시를 따릅니다.

이력 탐색에는 상한이 있습니다. 최근 current 런 24개 좌표 보존은 서버 메모리 범위이며 재시작 후 영구 복원을 보장하지 않습니다. `BOUND` 표시는 해당 저장 자료와의 결속을 뜻하며 품질 승인을 뜻하지 않습니다. [대시보드 운영 문서](docs/devs/EXPERT_DASHBOARD_DESIGN_KO.md)에 테마와 재시작 절차가 있습니다.

## 후보 연구·복구 기능

후보 회수·재정렬·의미 역할·교정·inference는 명시적으로 고정한 corpus·모델·bundle로 관측합니다. `OFF`·`SHADOW` 상태와 공개 판단에 실제 반영되는 경로를 구분합니다. 설정했다고 정식 학습·독립 성능평가가 완료되는 것은 아닙니다.

관련 문서는 [후보 회수](docs/devs/CANDIDATE_RETRIEVAL_SHADOW_20261010_KO.md), [재정렬·교정](docs/devs/CANDIDATE_RERANKER_SHADOW_20261010_KO.md), [R4 연결](docs/devs/R4_ACTUAL_BRIDGE_20261010_KO.md), [커뮤니티 지식](docs/devs/COMMUNITY_KNOWLEDGE_READ_ONLY_20261010_KO.md)에 있습니다.

## 검증과 문제 조사

manifest의 실행 ID·입력·요청/실제 병렬도·종료 상태를 먼저 확인합니다. 개별 문제는 worker 로그, 원문·후보·출처, checkpoint·공개 원장을 함께 대조합니다. 같은 설정의 A/A 관측이나 정상 종료만으로 개선율·정답률을 만들지 않습니다.

변경 범위에 맞는 회귀시험과 문서 링크를 확인하고 [검증 결과](docs/devs/VERIFICATION_RESULTS.md)에 범위를 남깁니다. 과거 상세 설명은 [정리 전 전문가 문서](docs/devs/archive/20261015/EXPERT_README_KO.md), 순차 실행기는 [레거시 안내](README_legacy_pipeline.md)에서 볼 수 있습니다.
