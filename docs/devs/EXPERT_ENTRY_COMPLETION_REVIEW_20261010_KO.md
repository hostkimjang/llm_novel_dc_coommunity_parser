# 일반 실행 진입점과 대시보드 완료 표시 검증

80건의 원문·참조 검토 자료 준비는 완료했다. 이번에는 승인된 개발 계획의 남은 로컬 항목을 대조해 일반 `expert_main` 전체 진입점과 대시보드 완료 표시를 검증했다. 전체 개발 목표는 아직 완료되지 않았다.

## 일반 실행 검증

합성 게시글 1건과 로컬 HTTP 응답으로 원본 프로그램 전체를 `runpy(..., run_name="__main__")`에서 실행했다. 실제 argv·시작 설정·health·전문가·guard·최종 저장·standalone 대시보드·종료를 거쳤다. 함수 추출 시험과 구분하며, 실제 모델·실제80·브라우저 검증은 아니다.

| 실행 | 확인 결과 |
|---|---|
| `run_first` | Windows 가상환경 실행기와 실제 Python PID를 같다고 본 시험 도구 오류로 분석 전에 중단. 원본 기록 보존 |
| `run_second` OFF | 분석 1건 정상 종료, 원래 HOLD 저장, 대시보드 live/history 결속 |
| `run_second` ON | 같은 publication의 기존 판정을 재생. 살아 있는 문맥이 없어 복구 0회, 재생 방어 확인 |
| `run_third` ON | 새 폴더의 최초 분석. provider 1회·native 7회, 별도 guard PUBLISH와 새 WAL 검산. 원래 HOLD·manifest·WAL 보존 |

독립 재판독은 second의 검산 항목 83개와 third의 93개를 통과했다. HMAC·저장 응답 SHA·유한 예산·자원·종료 및 live/history 연결을 확인했다. CPU1·BelowNormal·병렬1·대시보드 ON·압축 OFF이며 금지 통신/쓰기 시도는 0이다. 전체 모델 응답은 합성이므로 호출 수는 로컬 HTTP 호출 수다. 제품 내부 `SOURCE_BACKED`는 저장 원문 결속 enum이고 실제 자료 품질 인증이 아니다. 두 폴더는 이미지 URL이 달라 같은 raw 입력의 R5 paired 평가로 쓰지 않는다. [실행별 검증 기록](../../out/development_plan_20261010/goal_cli_full_entry_v1/verification_KO.md)을 따른다.

## 대시보드 수정과 회귀

API의 완료 카운터를 상세 화면에 연결했다. 종료 산출물 확정, 실제 처리 완료, 실패 기록, 저장 대기, 부분집합, 미기록·잘못된 타입을 구분한다. 목록의 `completed_count`를 ‘저장 건수’로 부르던 부분도 출처에 맞게 ‘처리 결과’로 수정했다. 공개 승인·의미 품질·formal KPI를 처리 완료로 대신하지 않는다.

Python 3개 관련 파일: **71 passed, 40 subtests passed in 10.17s**. 화면 표시·테마: **Node 84개 통과·실패 0개·skip 0개**. native·provider·일반 추론의 기존 저장 payload 3종을 SHA로 고정해 함께 소비했다. [묶음 시험 수령증](../../out/development_plan_20261010/goal_dashboard_completion_v1/final_receipt.json)과 [적용 지문](../../out/development_plan_20261010/goal_completion_audit_v1/dashboard_completion_v2_applied.json)을 보존한다. 일반 CLI 시험 뒤 UI/API 제품 3개·시험 3개가 바뀌었으며, 해당 변경은 이 묶음 시험으로 검증했다. main/pipeline/native 실행 소스는 그대로다. 새 브라우저 화면을 확인한 증거는 아니다.

## 다음 개발과 자료 대기

이 문서 작성 뒤 [R4 actual 연결](R4_ACTUAL_BRIDGE_20261010_KO.md)의 구현·합성 로컬 검증을 완료했다. 다음 문장은 당시 후보 단계의 기록이다. 적격 실제 자료의 전체 성공과 품질 수용은 계속 미검증이다.

당시에는 최신 semantic NIL/CAL 평가 CLI에서 기존 actual readback·baseline 수용기로 이어지는 연결이 남아 있었다. [최소 통합 설계](../../out/development_plan_20261010/goal_completion_audit_v1/r4_bridge_design_KO.md)에 따라 별도 후보를 준비 중이며 primary 적용·시험 완료로 세지 않는다. 전체 분모, 모델 점수 재생, 원문 span과 source bytes 결속, baseline 및 기존 actual 게이트를 유지해야 한다.

[80건 검토 안내](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)의 80개 게시물·112개 저장 관측·원문/참조 파일52개는 그대로다. 사람 정답0·학습 준비0·전체80 개발 노출·재사용 권한 UNKNOWN이며 후보 누락3행·이미지25개 미검토가 남아 있다. WORK2/NIL6/UNJUDGED72는 기존 모델 참고 분류다. 독립 holdout이나 학습 정답으로 승격하지 않는다.

이 문서의 2026-10-10 검증 당시에는 실제80·Chrome 실행이 자동 승인 검토의 `blocked by policy`로 차단돼 있었다. 이후 재승인 실행·의미 검토와 현재 화면의 관측 범위는 [P4 운영 인계](P4_REAPPROVAL_RUN_20261010_KO.md)를 따른다. [native](../../out/development_plan_20261010/p4_reapproval_v1/native_browser_v1/receipt.json)와 [provider](../../out/development_plan_20261010/p4_reapproval_v1/provider_browser_v1/receipt.json)의 후속 IAB 확인은 저장 payload를 현재 UI에 표시한 검증이며 새 producer나 실자료 복구 품질 검증은 아니다. 실제 corpus·사람 판정·TRAIN/CAL/FROZEN 품질·R5 계측·formal KPI는 미완료다. Goal active·formal KPI NOT_ESTIMABLE·R7 보류를 유지한다. 기존 33개 회귀 실패는 이미 해결됐으며 실행 수치를 서로 합산하지 않는다.
