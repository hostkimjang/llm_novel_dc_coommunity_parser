# 개발 문서 허브

프로젝트 사용법은 [루트 README](../../README.md), 현재 완료 범위와 후속 작업은 [현재 상태](CURRENT_STATUS_KO.md)에서 확인합니다. 이 문서는 설계·운영·검증 문서의 입구입니다. 날짜가 있는 보고서는 해당 시점의 기록입니다.

## 처음 읽는 순서

1. [현재 상태](CURRENT_STATUS_KO.md): 현재 80건 범위 완료, 검증 한계와 후속 작업
2. [전문가 실행 안내](../../expert_readme.md): `expert_main`의 역할과 저장 결과
3. [아키텍처](../ARCHITECTURE.md)와 [소스 구조](SOURCE_LAYOUT_KO.md): 실행 경로와 패키지 경계
4. [개발 계획](EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md)과 [구현 기록](EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md): 요구사항과 적용 근거
5. [체크리스트](CHECKLIST.md)와 [검증 결과](VERIFICATION_RESULTS.md): 작업 절차와 증거

## 문서 맵

| 주제 | 문서 |
| --- | --- |
| 목표·작업 목록 | [현재 목표](../../goal.md) · [TODO](TODO.md) · [개발 TODO](DEV_TODO.md) · [기능 개선 TODO](FEATURE_IMPROVEMENT_TODO.md) |
| 적용·인계 | [프로젝트 채팅 인계](PROJECT_CHAT_HANDOFF_20261010_KO.md) · [진입점 완료 검토](EXPERT_ENTRY_COMPLETION_REVIEW_20261010_KO.md) |
| 대시보드 | [디자인·운영](EXPERT_DASHBOARD_DESIGN_KO.md) · [적용 점검](DASHBOARD_EXPERT_MAIN_COVERAGE_AUDIT_20261010_KO.md) |
| 실행·계측 | [병렬 시험 안내](SAMPLING_AND_PARALLEL_TEST_GUIDE.md) · [저부하 비교 계측](PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md) |
| 복구 | [native 자동 복구](NATIVE_RECOVERY_AUTOMATION_20261010_KO.md) · [복구 실행](BOUNDED_RECOVERY_EXECUTION_20261010_KO.md) |
| 후보 연구 | [후보 회수](CANDIDATE_RETRIEVAL_SHADOW_20261010_KO.md) · [재정렬·교정](CANDIDATE_RERANKER_SHADOW_20261010_KO.md) · [R4 연결](R4_ACTUAL_BRIDGE_20261010_KO.md) |
| 커뮤니티 지식 | [읽기 전용 지식 연결](COMMUNITY_KNOWLEDGE_READ_ONLY_20261010_KO.md) · [slang 개선](../slang_db_improvement_todo.md) |
| 결과 검토 | [스캔 결과 리뷰](SCAN_RESULT_REVIEW_GUIDE.md) · [운영 품질 체크](OPERATION_QUALITY_CHECKLIST.md) |
| 변경 추적 | [개선 등록부](IMPROVEMENT_REGISTER.md) · [개발 이력](HISTORY.md) |
| 코드·산출물 관리 | [코드 산출물 정책](CODE_ARTIFACT_CLEANUP_POLICY_KO.md) · [이번 문서·커밋 정리](DOCS_GIT_CLEANUP_20261015_KO.md) |

## 운영 원칙

- 테스트·검증 실행은 요청 `--parallel 12`와 대시보드 ON을 사용하고 manifest의 실제 병렬도를 확인합니다.
- 변경 범위에 맞는 회귀시험을 실행하고 관련 문서·체크리스트를 함께 갱신합니다. 문서만 바꿀 때는 링크·명령·표현·변경 보존을 확인합니다.
- 정상 종료, 회귀시험, 의미 품질, 정식 KPI, production 승인은 각각 근거를 남깁니다. 겹치는 시험 수를 합산하지 않습니다.
- 원문·실패 실행·참조·원장을 보존합니다. 실패 원형을 성공 결과로 고치지 않습니다.
- 현재 상태 설명은 `CURRENT_STATUS_KO.md`에 모읍니다. README와 체크리스트에는 요약·링크를 두고 상세 진행 기록을 반복해서 붙이지 않습니다.

## 상태 규격

| 표기 | 의미 |
| --- | --- |
| `CURRENT80_SCOPED_VALIDATION_COMPLETE` | 현재 80건으로 가능한 개발·저장자료·DEV·국소 실측 검증 완료 |
| `REVIEW` / `HOLD` | 의미 품질 또는 개별 작품 근거의 검토가 남아 있음 |
| `NOT_OBSERVED` | 해당 분기나 효과가 실제 실행에서 관측되지 않음 |
| `NOT_ESTIMABLE` | 필요한 자료·분모·대조가 없어 정식 지표를 산출할 수 없음 |
| `full_scan_approval=false` | 전체 스캔·production 전환 승인 상태가 아님 |

## 이전 연구와 기록

9월 연구와 P0 외부 권한·Windows observer 계약은 [정리 전 문서 색인](archive/20261015/README_DEVS_KO.md)에 남겼습니다. P0 production 전환은 계속 보류 범위이며 관련 파일을 커밋해도 실제 provisioning이나 운영 승인을 뜻하지 않습니다.

Architecture V2의 이전 검증은 [내부 재감사](ARCHITECTURE_V2_INTERNAL_REAUDIT_KO_20260713.md), 실제 입력 조건은 [입력 인벤토리](ACTUAL_PACKET_INPUT_INVENTORY_KO_20260712.md)와 [출시 판정 런북](LAUNCH_READINESS_RUNBOOK_KO.md)을 참고합니다. 과거 상태가 현재 설명과 다르면 문서의 날짜와 적용 소스를 확인합니다.

[정리 전 README·목표·전문가 설명](archive/20261015/README.md)은 내용과 원래 위치를 기록해 보존했습니다. 로컬 실행 증거는 `out/`·`logs/`에 있어 Git checkout만으로 모두 제공되지는 않습니다.
