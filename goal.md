# 현재 작업 목표

## 완료한 목표

2026-10-15, 사용자가 요청한 “R5 비교 실패 원인부터 해결하고 현재 80건으로 가능한 검증까지 마무리” 범위를 완료했다. 네이티브 Goal은 `complete`, 저장 문서의 판정은 **CURRENT80_SCOPED_VALIDATION_COMPLETE**다.

완료 범위·수치·남은 조건은 [현재 상태](docs/devs/CURRENT_STATUS_KO.md)에 모아 관리한다. 원래 요구사항은 [개발 계획](docs/devs/EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md), 구현 경로는 [구현 기록](docs/devs/EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md)을 따른다.

- [x] 대시보드와 `expert_main` 개선을 기본 프로젝트에 통합했다.
- [x] 현재 80건의 저장자료·두 모델 검토·DEV 관측을 검산했다.
- [x] R5 실패 원인을 수리하고 관련 제품 회귀 398개와 저장 실패의 전체 경로 재생을 확인했다.
- [x] 동일 설정 A/A, 64번·55번의 국소 실측과 대시보드 표시를 확인했다.
- [x] 원문·실패·소스 버전·원장을 보존하고 완료 응답을 기록했다.

## 후속 작업

- [ ] 기존 확대시험 실패 5건과 35번 보조 전언 경계를 별도 수리한다.
- [ ] 새 proposal/delta 분기의 실제 효과를 관측한다.
- [ ] 적격 자료와 재사용 근거를 확보한 뒤 독립 성능평가·TRAIN/CAL/FROZEN을 진행한다.
- [ ] 별도 수용 조건을 충족한 뒤 R7 production 전환을 판단한다.

전체 80건의 의미 게이트는 `REVIEW`, 정식 KPI는 `NOT_ESTIMABLE`을 유지한다. 현재 범위 완료가 전체 회귀 통과·모든 행 ACCEPT·일반화 성능 승인을 뜻하지 않는다.

## 문서·커밋 정리

Claude Opus 5.5의 두 차례 검토를 반영해 누적 Git 변경과 README·문서의 진입점을 정리했다. 검토·검증·커밋 범위는 [문서·커밋 정리 기록](docs/devs/DOCS_GIT_CLEANUP_20261015_KO.md)에 남긴다.

## 이력과 증거

정리 전 목표와 당시 상태는 [목표 이력](docs/devs/archive/20261015/GOAL_KO.md), 기존 연구 목표는 [9월 이력](goal.history.20260906.md)에 보존했다. 로컬 최종 보고서는 `out/r5_resolution_20261014_v2/REPORT_KO.md`, Goal 완료 응답은 같은 폴더의 `finalization/goal_completion.json`이다.
