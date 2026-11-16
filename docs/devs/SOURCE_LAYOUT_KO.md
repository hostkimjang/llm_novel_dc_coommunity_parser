# `src/llm_batch` 소스 구조와 개발 규칙

이 문서는 `src/llm_batch`의 모듈 배치와 패키지 책임, 실제로 관측되는 교차 의존, 코드를 바꿀 때 지킬 규칙을 설명한다. 실행 흐름은 [아키텍처](../ARCHITECTURE.md)를 따른다.

## 루트 모듈

`src/llm_batch` 바로 아래에는 다음 모듈이 있다.

| 모듈 | 역할 |
| --- | --- |
| `__init__.py` | 패키지 표식 |
| `agentic_pipeline.py` | 주력 `AgenticPipeline`. 게시글 한 건의 분석과 공개 전 출력 정리를 조정한다. |
| `cli.py` | 레거시 batch/staged 실행용 `llm-batch` CLI 어댑터 |
| `promotion_gate.py` | 공개 제목·URL의 최종 승격을 하나로 모은 공개 계약 |
| `edition_lexical_caller.py` | 검증된 원문 inventory와 공개 계약 전달 helper |
| `edition_lexical_pipeline_api.py` | 판본 어휘 원장을 한 번 만들고 같은 관계를 직렬화까지 전달하는 API |
| `kakao_routes.py` | 카카오 URL의 경로 역할 판별 |
| `record_role_lexical_producer.py` | native parser 근거를 불변 typed packet으로 만드는 producer |
| `record_role_normalizer.py` | typed carrier 직렬화 필드 소비 |
| `record_role_transport.py` | 명시 producer carrier 전달 후보 |
| `record_role_types.py` | 향후 버전 typed 선언 초안. 제품 클래스나 실제 생산값이 아니다. |

`agentic_pipeline.py`는 많은 회귀시험이 `llm_batch.agentic_pipeline` 모듈 전역 심볼을 직접 patch한다. 예를 들어 `import llm_batch.agentic_pipeline as module` 뒤 `monkeypatch.setattr(module, "GatekeeperExpert", ...)`처럼 쓴다. 이 모듈을 옮기거나 쪼개면 patch 대상이 조용히 빗나갈 수 있으므로, 계약 분해와 시험 갱신 없이 물리 이동하지 않는다. `promotion_gate.py`도 저장소 전반의 공개 경계라서 루트에 둔다.

## 패키지

| 패키지 | 책임 |
| --- | --- |
| `domain/` | 공유 도메인 모델(`models`), 정적 규칙(`rules`), `BatchContextMemory`, 별칭 학습, 제목 무결성 |
| `experts/` | 전문가 역할, `Orchestrator`와 `ConversationContext`, 원문 span 유틸리티(`source_spans`, `utils`) |
| `prompts/` | 전문가·파이프라인 프롬프트와 router |
| `grounding/` | 후보 보존, 근거 결속, 화자·발화 역할, 선택 관측 계약 |
| `ledger/` | 공개 결정 commit, framed WAL, 호출·복구 원장과 재판독 |
| `runtime/` | 실행 설정·프로필, 선택 실행 지문, budget·limiter·cache·singleflight, 선택 관측 adapter, `expert_main` CLI 정의(`expert_cli`) |
| `measurement/` | 실제 효과를 읽고 비교하는 측정 계약, 복구 실행 readback |
| `slang/` | Slang DB 조회와 승인된 변경의 governance·transaction |
| `monitor/` | 이벤트 버스, 대시보드 API·정적 화면, 실행 이력 색인, Slang DB 화면 변환(`slang_view`) |
| `pipelines/` | 레거시·staged 실행 파이프라인 |
| `llm/`, `search/`, `mcp_bridge/`, `browser_search/` | LLM 호출, MCP 검색·fetch 클라이언트와 bridge, headless 브라우저 검색 fallback |
| `audit/` | 감사 실행기 |

`expert_main`의 CLI 정의는 `runtime/expert_cli.py`의 `build_arg_parser`에 있다. `expert_main._build_arg_parser`는 이 함수를 그대로 돌려주는 wrapper이며, 옵션 이름·기본값·help 문구는 이 파일에서 바꾼다. 대시보드의 `/api/slang-db` 화면 변환은 `monitor/slang_view.py`의 `build_slang_db_payload`가 맡고, Slang DB 조회에서 `server.py`는 파일 읽기와 route만 담당한다. 서버 전체는 그 밖에도 live·history API, SSE, LLM 재개 같은 기능을 맡는다.

## 관측된 교차 의존

권장 방향은 `domain`이 가장 아래에 있고, `grounding`·`measurement`·`slang`이 그 위, `experts`·`agentic_pipeline`·`pipelines`가 이들을 조합하는 구조다. 현재 코드에는 이 방향을 벗어난 import가 있다. 새 코드는 이 목록을 늘리지 않는 것을 원칙으로 한다.

| 의존 | 실제 위치 |
| --- | --- |
| `domain` → `experts`, `grounding` | `domain/batch_context.py`가 `experts.utils`, `grounding.munpia_author_byline`을, `domain/alias_learning.py`가 `grounding.anticipation_search_probe`를 가져온다. |
| `grounding` → `experts.source_spans` | 여러 grounding 모듈이 원문 span 유틸리티를 `experts`에서 가져온다. |
| `grounding` → `slang`, `runtime` | `candidate_audit`이 `slang.slang_db`를, `candidate_reranker_capture`가 `runtime.candidate_reranker`를 쓴다. |
| `slang` → `experts`, `ledger` | `slang_db`가 `experts.decoder`·`experts.utils`의 약어 표를, `slang_transaction`이 `ledger.framed_wal`의 파일 잠금을 쓴다. |
| `measurement` → `ledger`, `runtime` | 측정 readback과 복구 계약이 원장·transport를 읽는다. |
| `runtime` → `agentic_pipeline`, `experts` | native 복구 문맥·workflow와 shadow canary가 파이프라인과 Orchestrator를 다시 사용한다. |
| `ledger` → `grounding` | `recovery_activation`이 이미지 제목 충돌 판정을 쓴다. |

`grounding → experts.source_spans → verifier → grounding` 순환을 피하려고 `experts/__init__.py`는 전문가 클래스를 lazy export한다. `from llm_batch.experts import Orchestrator`처럼 쓰면 처음 접근할 때 해당 모듈을 import한다. 반면 `audit/`, `prompts/`, `monitor/`의 `__init__.py`는 하위 모듈을 바로 import한다. 예를 들어 `llm_batch.monitor`를 import하면 `server`도 함께 로드된다. 새 패키지는 eager re-export를 두지 않는다.

## 변경 규칙

- **선택 실행 지문:** `runtime/execution_config.py`의 `source_snapshot`은 선택한 소스 파일 목록(`relative_files`)의 SHA-256으로 실행 지문을 만든다. 이 목록은 실행 판단과 설정 경계에 속한 파일만 담으며 저장소 전체의 완전성을 보장하지 않는다. 코드를 새 모듈로 옮길 때는 옮긴 코드가 이 경계에 속하는지 검토하고, 속하면 목록에 추가한다(예: CLI 정의를 옮긴 `runtime/expert_cli.py`). 대시보드 표시 전용 코드는 목록에 넣지 않고 변경 기록에 파일별 SHA로 관리한다(예: `monitor/slang_view.py`). 목록이 바뀌면 같은 코드라도 실행 지문이 달라지므로 이전 실행과 지문을 비교할 때 이 차이를 함께 확인한다.
- **CLI 계약:** 옵션 이름, dest, 기본값, choices, help 문구는 사용자와 도구가 의존하는 계약이다. 구조만 옮길 때는 `--help` 출력 바이트와 parse 결과가 같아야 한다. 일부 help는 영어로 되어 있으며, 구조 정리만으로 바꾸지 않는다.
- **줄바꿈 보존:** 저장소는 CRLF·LF 파일이 섞여 있고 일부 파일은 한 파일 안에서도 섞여 있다. 편집할 때 파일의 기존 줄바꿈을 그대로 유지한다. 줄바꿈만 바뀐 diff를 만들지 않는다.
- **분리 전후 동등성:** 함수나 모듈을 옮기는 정리는 docstring을 뺀 AST가 같은지 확인하고, 관련 기능 시험을 함께 실행한다. 판정 규칙이나 기본값을 바꾸는 변경과 섞지 않는다.
- **docstring과 주석:** 패키지·핵심 모듈 docstring은 한국어로 책임, 의존 경계, 보수적으로 닫는 이유를 설명한다. 주석은 코드가 하는 일을 반복하지 않고 유지해야 할 불변식이나 이유를 적는다.
- **프롬프트:** 실제 LLM 입력에는 장식용 emoji, box drawing, variation selector를 쓰지 않는다. JSON key, enum, 의미 규칙은 유지한다. 로그·대시보드 상태 아이콘은 LLM 입력이 아니므로 별개다.
- **옛 경로:** 과거 loop 보고서의 이전 import 경로는 당시 증거 위치를 설명하므로 일괄 수정하지 않는다. 현재 실행·개발 문서와 import에는 현재 경로만 쓴다.

소스 정리와 단위 시험 통과는 분석 품질 개선 근거가 아니다. 성능·품질 평가는 별도 측정 계약을 따른다.
