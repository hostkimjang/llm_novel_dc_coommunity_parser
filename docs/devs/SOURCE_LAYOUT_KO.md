# `src/llm_batch` 소스 구조와 이동 규칙

## 2026-07-15 정리 결과

`src/llm_batch` 루트의 Python 파일을 40개에서 4개로 줄이고, 36개 모듈을 책임별 패키지로 이동했다. 저장소 내부의 import와 unittest patch target도 새 경로로 함께 갱신했다. 이 작업은 코드 탐색성과 소유권을 정리하는 리팩터링이며 runtime·semantic 품질·운영 승인을 변경하지 않는다.

```text
src/llm_batch/
  __init__.py
  cli.py                       CLI 진입점
  agentic_pipeline.py          주력 agentic 조정기
  promotion_gate.py            공개 판정의 공통 fail-close 경계
  domain/                      순수 모델, 규칙, BatchContext, 제목 무결성
  grounding/                   후보 생성·감사·보정·confidence 계약
  ledger/                      decision event, WAL, 원장, publication commit
  runtime/                     stage budget, cache, singleflight, shadow adapter
  measurement/                 early route, paired readback, selective compute
  slang/                       slang DB, governance, transaction
  pipelines/                   legacy·staged 실행기
  experts/                     전문가 역할과 orchestration
  prompts/                     실제 전문가 프롬프트
  llm/, search/, mcp_bridge/   외부 호출 adapter
  audit/, monitor/             감사와 관측
```

루트의 `agentic_pipeline.py`는 다수의 회귀가 모듈 전역 심볼을 monkeypatch하고 있어 이번 단계에서는 이동하지 않았다. `promotion_gate.py`도 저장소 전반의 공개 판정 경계이므로 루트에 유지했다. 둘은 별도 계약 분해 없이 물리 이동하지 않는다.

## 의존 방향

1. `domain`은 runtime·ledger·experts를 참조하지 않는다.
2. `grounding`, `measurement`, `slang`은 필요한 `domain` 계약만 가져온다.
3. `runtime`과 `ledger`는 실행·저장 안전 계약을 제공하며 공개 판정을 임의로 바꾸지 않는다.
4. `pipelines`, `experts`, `agentic_pipeline`이 위 계층을 조합한다.
5. 패키지 `__init__.py`는 import 부작용을 막기 위해 eager re-export를 두지 않는다.

대표 이동 경로는 다음과 같다.

| 이전 경로 | 현재 경로 |
| --- | --- |
| `llm_batch.models` | `llm_batch.domain.models` |
| `llm_batch.rules` | `llm_batch.domain.rules` |
| `llm_batch.candidate_audit` | `llm_batch.grounding.candidate_audit` |
| `llm_batch.confidence_report` | `llm_batch.grounding.confidence_report` |
| `llm_batch.decision_ledger_v2` | `llm_batch.ledger.decision_ledger_v2` |
| `llm_batch.framed_wal` | `llm_batch.ledger.framed_wal` |
| `llm_batch.stage_budget` | `llm_batch.runtime.stage_budget` |
| `llm_batch.pipeline_stage_runtime_adapter` | `llm_batch.runtime.pipeline_stage_runtime_adapter` |
| `llm_batch.slang_db` | `llm_batch.slang.slang_db` |
| `llm_batch.pipeline` | `llm_batch.pipelines.legacy` |
| `llm_batch.staged_pipeline` | `llm_batch.pipelines.staged` |

과거 loop 보고서의 이전 경로는 당시 증거 위치를 설명하므로 일괄 재작성하지 않는다. 현재 실행·개발 문서와 import에는 새 경로만 사용한다.

## 주석과 프롬프트 규칙

- 패키지·핵심 모듈 docstring은 한국어로 책임, 의존 경계, fail-close 이유를 설명한다.
- 주석은 코드가 무엇을 하는지 반복하지 않고, 보수적으로 닫는 이유나 유지해야 할 invariant를 기록한다.
- 실제 LLM 입력 프롬프트에서는 장식용 emoji, box drawing, variation selector를 사용하지 않는다. JSON key, enum, 의미 규칙은 유지한다.
- 로그·대시보드의 상태 아이콘은 LLM 입력 토큰이 아니므로 프롬프트 정리와 분리한다.
- 참조되지 않던 `LINGUISTIC_FRAMEWORK` 대형 source 상수 15,780자를 제거했고, 실제 입력 prompt의 장식 Unicode `So`는 0개로 정리했다. 이 상수는 원래 전송 경로에서 참조되지 않았으므로 token 절감량으로 합산하지 않는다. 실제 provider token BEFORE/AFTER는 아직 `NOT_MEASURED`다.

## 테스트 정리와 잔여 작업

- 이미 제거된 도구만 import하던 `test_browser_visual_targets_from_result.py`, `test_qualitative_review_packet_tools.py`와 allowlist 예외를 제거했다.
- 장기 회귀 자산인 `test_agentic_pipeline_rework.py`는 삭제하지 않는다. 후속 작업에서 책임별 파일로 분할한다.
- `agentic_pipeline.py` 자체의 기능 분해는 이번 물리 이동과 섞지 않고 별도 계약 리팩터링으로 진행한다.

## 승인 경계

소스 정리와 단위 테스트 통과는 실제 성능 개선 자료가 아니다. actual metrics는 `null/NOT_ESTIMABLE`, semantic quality는 `REVIEW-LOCKED`, production `full_scan_approval=false`를 유지한다.
