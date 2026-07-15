# Goal 코드 산출물 정리 정책

## 2026-07-15 정리 결과

프로젝트의 주력 실행 코드(`expert_main.py`, `src/llm_batch/**`)와 현재 Architecture V2 acceptance/readback 경로는 유지했다. 과거 goal에서 생성된 뒤 현재 코드·문서의 정식 실행 경로에서 참조되지 않는 completed779/JUDGE3905 builder·테스트와 Git 비추적 smoke/driver만 제거했다.

| 구분 | 정리 전 | 정리 후 | 변화 |
| --- | ---: | ---: | ---: |
| `tests/`, `tools/`, `scratch/` Python | 339 | 297 | -42 |
| goal workflow JavaScript | 1 | 0 | -1 |
| 코드 줄 수 | - | - | 약 -18,707 |

- Git 추적 파일 제거: 과거 completed779/JUDGE3905/native-web residual builder 4개와 대응 테스트 4개.
- Git 비추적·ignored 파일 제거: 3~6월 일회성 audit/exit-action/full-post-judge/smoke와 v2로 대체된 terminal-ledger v1 계열 33개.
- dangling test 제거: 이미 삭제된 도구만 import하던 2개 테스트·2,661줄과 `.gitignore` allowlist 예외.
- 보존: 현재 수정 중인 always-on gate가 import하는 Loop641~643 adjudication/trust-anchor 체인, Slang governance/transaction, Architecture V2의 181-test commit-scoped acceptance 경로.
- 게이트 영향: 아키텍처·runtime·semantic·운영 승인 상태를 변경하지 않는다. `REVIEW-LOCKED / full_scan_approval=false`, actual metric `null/NOT_ESTIMABLE`을 유지한다.

과거 문서가 제거된 파일명을 인용하더라도 당시 증거 설명은 유효하다. 실행 코드는 Git history에서 재현하고, 현재 정식 명령으로 오해하지 않는다.

## 영구 보존 기준

`tests/` 또는 `tools/`의 Git allowlist에 올리려면 다음을 모두 만족해야 한다.

1. 현재 `src/llm_batch/**` 또는 운영 run/preflight/readback 경로가 직접 사용한다.
2. loop 번호·날짜·특정 산출물 경로에 고정되지 않고 새 입력으로 재사용할 수 있다.
3. deterministic contract test와 실패 시 의미가 문서에 있다.
4. runtime 통과, semantic 품질, 운영 승인을 분리해 보고한다.

## Goal 전용 코드 수명주기

1. 최초 probe/smoke/builder는 `scratch/goal_<id>/` 또는 `out/<run_id>/`에서 시작한다.
2. 검증이 끝나면 보고서·JSON·manifest만 증거로 보존하고 일회성 실행 코드는 제거한다.
3. 반복 사용이 확인된 코드만 loop/date 의존성을 제거한 뒤 `tools/` 또는 정식 `tests/`로 승격한다.
4. 합성 smoke PASS는 실제 runtime·semantic approval 근거로 승격하지 않는다.
5. 분기별 또는 대형 goal 종료 시 `tracked / untracked / ignored` 코드 수와 역참조를 다시 감사한다.

## 다음 정리 후보

- 현재 활성 gate 의존성이 있는 untracked Loop641~643 도구 체인은 보존하되, 자기 테스트 외 참조가 없고 v2로 대체된 terminal-ledger v1 쌍만 제거했다.
- Architecture V2 harness/canary는 현재 정식 acceptance이므로 유지했다. 외부 M2 종료 뒤 reader/runner 공통화는 별도 리팩터링으로 진행한다.
- ignored 대형 `tests/test_agentic_pipeline_rework.py`는 smoke가 아니라 장기 회귀 모음이다. 삭제 대신 테스트 책임 단위 분할을 별도 작업으로 다룬다.
- 주력 source의 기능별 재배치는 [`src/llm_batch` 소스 구조](SOURCE_LAYOUT_KO.md)를 따른다.

## 검증

- 삭제 파일명 Python 역참조: `0`.
- `PYTHONPATH=src .\.venv312\Scripts\python.exe -m compileall -q expert_main.py src tools tests`: PASS.
- core/운영 묶음: pipeline stage, candidate audit, bootstrap, dashboard attach/standalone `160 tests PASS`.
- publication gate: `tests.test_promotion_gate_contract 101 tests PASS`.
- terminal-ledger v2: `tests.test_build_search_terminal_consensus_ledger_v2 9 tests PASS`.
- M1 정식 선택 120개: `119 PASS / 1 ERROR`. 오류는 현재 작업 중 `agentic_pipeline.py`가 `_collect_expert_urls(..., selected_title=...)`를 호출하지만 기존 search-evidence test mock이 해당 keyword를 받지 않는 signature mismatch다. 삭제 파일 import나 cleanup 회귀는 아니다.
- `git diff --check`: PASS. Windows LF/CRLF 경고만 있었다.
