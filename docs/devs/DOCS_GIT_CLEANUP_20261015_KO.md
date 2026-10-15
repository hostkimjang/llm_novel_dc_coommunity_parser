# README·문서·커밋 정리 기록

2026-10-15 사용자 요청에 따라 **Claude Opus 5.5와 두 차례 읽기 전용 검토를 진행하고 README·문서·누적 Git 변경을 정리했다.** 제품·시험·도구의 기존 바이트와 실제 실행 원본은 보존했다.

## 문서 구조

| 문서 | 정리한 내용 |
| --- | --- |
| `README.md` | 578→92줄. 기능·현재 상태 요약·설치·실행·입출력·문서 입구 |
| `expert_readme.md` | 1,073→77줄. 현재 전문가 역할·저장 계약·옵션·대시보드 안내 |
| `docs/devs/README.md` | 559→52줄. 읽는 순서·문서 지도·운영 원칙·상태 규격 |
| `goal.md` | 완료 목표·후속 범위·문서 정리 결과 |
| `docs/devs/CURRENT_STATUS_KO.md` | 현재80 완료 범위·관측 한계·남은 작업의 현재 설명 |
| `docs/devs/archive/20261015/` | 정리 전 README·허브·목표·전문가 설명과 원형 SHA 보존 |

현재 상태를 README·체크리스트에 반복해서 붙이지 않고 `CURRENT_STATUS_KO.md`에서 관리한다. 관련 문서10개의 중복 현재 블록도 요약 링크로 바꿨다. 병렬12·대시보드ON, 실제 유효한 서버 설정과 코드 위치를 안내하며 레거시 문서는 맨 위에서 구분한다.

날짜별 보고서의 `out/`·`logs/`는 로컬 증거임을 명시했다. 대시보드 운영 문서의 로컬 증거 링크는 경로 텍스트로 바꿨다. 정리 전 정확한 바이트는 로컬 `out/docs_git_cleanup_20261015_v1/preimage/`, Git의 보존본은 상대 링크·표시용 줄끝 공백을 정리한 버전이다.

## 커밋 구성과 재현 파일

| 순서 | 범위 |
| --- | --- |
| 1 | P0 권한·원문 계보 계약, Windows observer 연구 후보·marker resource, 계약에 필요한 빈 rows와 대응 시험·문서 |
| 2 | `expert_main`·pipeline·전문가·출처/후보·복구/계측 경로와 시험·fixture |
| 3 | 대시보드 API·이력·정적 자산·스타일 입력과 관련 회귀 |
| 4 | README·개발 허브·현재 상태·목표·체크리스트·검증·인계 문서 |

첫 세 커밋은 `9be412530c702a1fb199731dd806cd8bfcec65b7`, `cb85dbdff9f7bdacb279e4aafa2fc8ea347db9fe`, `216214632c9a36440a0e6ee9e128825e1a9c8f7e`다. 이 문서를 포함한 네 번째 커밋의 해시는 Git 이력과 로컬 종합 수령증에 기록한다.

기존 ignore 때문에 빠져 있던 재사용 시험·지원 파일57개를 명시 allowlist에 추가했다. 최종398 회귀에 필요한 `test_source_general_context_state.py`·`test_source_scope_state_current_run.py`와 지원 import·fixture를 포함한다. 특정 저장 경로에 고정된 진단2개·egg-info6개는 로컬 보존하며 제품으로 승격하지 않았다.

`native`의 55바이트 `.bin`은 marker resource이고 빈 rows2개도 계약이 고정한 자원이다. 원문 재생 fixture는 Git 개행 변환을 막고 CRLF를 정상 줄끝으로 취급하도록 했다. 로컬 `.ai-bridge/`·`_workspace/`는 삭제하지 않고 `.git/info/exclude`로 제외했다.

## 검토·검증 결과

- Opus 초기 검토와 정리본 검토에서 중복·과거 상태·병렬16·절대경로·로컬 증거·미추적 링크·서버 설정 문제를 확인하고 반영했다. Opus 서브에이전트 전달 오류 이후 기존 “Opus 5.5 최종 독립 평가” 채팅에서 검토를 완료했다. 이전 최종55 실측의 Opus 검토로 소급하지 않는다.
- 현재 진입 문서7개의 링크84개를 Git index에서 확인했고, 보존본을 포함한 로컬 링크535개에서 누락0을 확인했다. fixture118개의 Git blob과 작업 파일은 바이트가 같다.
- 후보 Python495파일의 구문 검사 오류0. 문서에 안내한 CLI11개를 실제 parser와 대조했다.
- 명시 stage 트리를 별도 폴더로 내보내 **기존 관련 회귀398개를 재실행해 398 PASS·실패/오류/skip0**을 확인했다. 소요233.98초, 제품 모듈의 원본 작업트리 유입0, 네트워크 금지·모델 호출0이다. 이는 지정10개 시험 파일의 새 checkout 재현이며 전체 저장소 시험이 아니다. 과거398과 합산하지 않는다.
- pytest 경고1개는 기존 임시 폴더 정리 중의 Windows `WinError 145`다. 테스트 실패가 아니며 다른 작업의 임시 폴더를 삭제하지 않았다.
- 기존 보호 소스483개·기술 근거986개를 검산했다. 제품·시험·도구 변경0이며 Git index·ignore는 이번 커밋 작업에 따라 의도적으로 달라졌다. 이전 실행 수령증은 고치지 않았다.
- 문서와 P0 단계의 staged 공백 검사는 통과했다. runtime·UI에서는 작업 전부터 있던 EOF 빈줄7곳·줄끝 공백1곳을 원형 해시 보존을 위해 유지했다. 기본 `git diff --cached --check`의 해당 단계 종료값은2이며, 이8개 파일을 제외한 변경 범위의 공백 검사는0이다. 전체 공백 검사가 무경고라고 표시하지 않는다.

현재80 범위 Goal `complete`, 전체 의미 `REVIEW`, 정식 KPI `NOT_ESTIMABLE`, 기존5개 확대시험 실패·독립 평가 조건·R7 보류·새 proposal/delta 실측 미관측을 유지한다. 제품 수리나 새 모델 실측을 추가한 작업으로 해석하지 않는다.

## 로컬 상세 근거

`out/docs_git_cleanup_20261015_v1/`에 원형·인벤토리·검사·내보낸 시험·커밋 수령증을 보관한다. 이 폴더는 Git에 포함하지 않는다.

- `opus55/REVIEW_KO.md` — SHA `9b4da77eeb2d3b99ebe04e222665443f845311148fc4a3d1fa0d756aced86023`
- `opus55/FINAL_REVIEW_KO.md` — SHA `02d8e99f2b95748e01edc7a33baa508f191331e7c66c0a93f4fab083052de527`
- `commit_plan.json`, `commits.json`, `commit_inventory.json`
- `validation_before_commits.json`, `staged_links_and_fixtures.json`, `evidence_preservation.json`
- `clean_export_receipt.json`, `clean_export_junit.xml`, `clean_export_test.log`
- `FINAL_RECEIPT.json` — 최종 커밋·작업트리 상태와 산출물 해시
