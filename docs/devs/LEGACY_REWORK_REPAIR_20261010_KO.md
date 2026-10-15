# 기존 회귀 실패 수리 기록

## 2026-10-10 최신 진행: 전체 진입점과 완료 표시

80건 검토 자료 준비를 유지하면서 일반 `expert_main` 전체 진입점의 합성 입력 OFF·재생 ON·최초 분석 ON을 검증했다. 최초 ON은 provider1회·native7회를 거쳐 원래 HOLD와 별도 결과를 보존했다. 대시보드의 완료 상태·부분집합·실패·저장 대기와 이력 건수 표시를 수리했다.

관련 Python 3파일은 **71 passed, 40 subtests passed in 10.17s**, **Node 84개 통과·실패 0개·skip 0개**다. 일반 CLI 검증과 이후 UI/API 변경의 시험 범위를 분리한다. [현재 검증·남은 개발](EXPERT_ENTRY_COMPLETION_REVIEW_20261010_KO.md)을 따른다. 아래 수치와 당시 미완료 설명은 이전 단계 기록이다.

후속으로 semantic NIL/CAL→actual readback·baseline 연결을 구현하고 합성 로컬 검증을 마쳤다. **271 passed, 9 subtests passed in 167.12s (0:02:47)**이며 [R4 연결 검증](R4_ACTUAL_BRIDGE_20261010_KO.md)에 범위와 한계를 기록했다. 적격 실제 자료의 전체 성공 경로, 실제80·새 브라우저·사람 판정·실자료 품질·R5 실측은 미완료다. Goal active·formal KPI NOT_ESTIMABLE·R7 보류를 유지한다.

현재 상태는 **선택 회귀 수리 로컬 검증 완료, 실제 품질 미완료**다. 기존 실패 33개는 최종 대응표에서 모두 통과했다. 이전 자동 native 복구의 로컬 검증 결과는 당시 소스의 기록으로 보존한다. 제품·시험 변경의 검증 범위는 아래 실행별 근거를 따른다. 전체 저장소 회귀를 실행한 것은 아니다. Goal은 active이고 R7 production 전환은 보류다.

## 확인한 실행 결과

| 실행 | 통과 | 실패 | 하위 시험 통과 | 해석 |
|---|---:|---:|---:|---|
| 이전 빈 캐시 baseline/current | 450 | 33 | 10 | 같은 격리 조건에서 실패 node·예외·정규화 메시지가 같았다. |
| 시험 계약 4개 정정 후 첫 실행 | 452 | 31 | 10 | 2개 통과, 2개는 다음 검산 지점으로 이동, 새 실패 node 0개다. |
| 7개 파일 수정 묶음 `phase2b` | 556 | 10 | 45 | pytest 원문 수치다. rework 실패 case 9개와 격리 의존 파일 누락 1개가 남았다. |

첫 실행은 현재 소스를 복제한 빈 캐시에서 외부 연결을 차단하고 수행했다. 논리 CPU 1개·낮은 우선순위·수치 연산 thread 1개를 시작과 끝에 확인했다. 고정 사본의 source 변경·외부 socket 시도·쓰기 이탈·첫 프로젝트 import 이탈은 0건이다. 원시 근거는 [실행 수령증](../../out/development_plan_20261010/r6_rework_phase1/run_first/receipt.json), [JUnit](../../out/development_plan_20261010/r6_rework_phase1/run_first/junit.xml), [이전 실패와 비교](../../out/development_plan_20261010/r6_rework_phase1_comparison.json)에 있다. 시험을 정정했으므로 동일 소스의 전후 성능 비교로 해석하지 않는다.

`phase2`는 지정 시험 파일 누락으로 수집 전에 종료되어 실행 시험이 0개였다. 지정 파일을 포함한 새 `phase2b`에서 [7개 파일 묶음](../../out/development_plan_20261010/r6_rework_phase2b/run_first/receipt.json)을 실행했다. 추천/OCR 최종 공개 보류·최종 SI 문맥·저장 설명 변조 검산 16개가 통과했고, 최종 source 설명·재검토·공개 계약의 함께 실행한 회귀도 통과했다. native base capture 1개는 의존 파일 `tools/recover_expert_run_from_checkpoint.py`가 사본에 없어 import에서 멈췄다. 이를 제품 실패나 통과로 해석하지 않는다. 고정 소스 변경·외부 socket 시도는 없었다.

당시 본문 별칭의 일반 화자 라벨 처리에 정적 P2가 발견되어 후속 수리 후보를 준비했다. 당시 미검증이던 별칭 추가 시험 4개도 최종 phase4에서 통과했다. 실행 간 통과 수를 합산하지 않으며, 이름을 바꾼 시험은 원래 node와의 대응표를 확인한다.

## 최종 후속 검증

`phase3` 9개 파일은 **5 failed, 578 passed, 64 subtests passed in 572.95s (0:09:32)**였다. 기존 33개 실패 계보는 32개 통과·1개 실패이며, 별도 4개 실패는 시험용 도구 1건·R25 fixture 3건의 사본 누락이었다. 새 화자 경계 23개 하위 사례와 native 복구 workflow 8개는 통과했다. 최초 집계의 다른 클래스 6개 누락은 집계 코드 오류였고 [독립 재판독](../../out/development_plan_20261010/r6_rework_phase3_node_readback_v1_KO.md)에서 32/1을 확인했다. 최초 집계는 이력으로 보존한다.

남은 본문 별칭 사례는 직접 helper의 무URL 반환과 후기 검색 recall 후보를 동일하게 기대한 시험 오류였다. 후보가 사라지지 않았고 공개도 보류됐다. helper 제약을 유지하면서 최종 검색 제목·URL·query·snippet·비권한 후보·공개 HOLD를 검사하도록 정정했다. 이후 제품 코드 변경은 없다. 누락 도구와 자료를 추가한 `phase4` 3개 파일은 **494 passed, 55 subtests passed in 181.10s (0:03:01)**이며, [원래 33개 계보가 전부 통과](../../out/development_plan_20261010/r6_rework_phase4_reconciled.json)했다.

현재 제품 소스가 `phase3`와 같음을 대조해 그 실행의 나머지 6개 파일 통과도 유효한 별도 근거로 유지한다. 이번 변경 범위의 최종 source 설명·공개 계약·native 복구·R25 경계 검증이며, 저장소 전체나 전체 CLI를 다시 실행한 결과가 아니다. 실행별 수는 합산하지 않는다. 외부 socket·쓰기 이탈·첫 프로젝트 import 이탈·실행 중 소스 변경은 0건이며 논리 CPU 1개·우선순위 16384·수치 스레드 1개를 시작/끝에 확인했다.

화자 수리는 일반 라벨의 다음 줄/block 보류와 명시 작성자 복귀를 포함한다. URL 전체를 원문과 같은 길이의 분석용 공백으로 보호하고 시각 token만 제외해 뒤 화자를 놓치지 않도록 했다. 원문은 변경하지 않는다. 이전 정적 P2와 후속 반례는 이 범위에서 수리·검증됐으며 신규 관측 후보에 공개 권한을 부여하지 않는다.

## 수정 범위와 판단 근거

- **작성자 귀속과 mock 계약:** 닉네임·IP 일치는 인증된 작성자 근거가 아니다. 미인증 표시와 원문 보존을 검사하고, 현재 함수의 `candidate_url`·`final_decision` 인자를 시험에서도 받도록 했다. 기존 공개 guard의 반환값을 새로 강제하지 않는다.
- **등급과 설명:** catalog는 관측한 댓글 탭 URL을 그대로 표시한다. 공식 URL 정규화와 catalog 등급을 구분한다. 선택 URL이 없는 모델 후보는 `llm_only`로 남긴다. 최종 설명은 제목 미확정·URL 보류와 원문을 검사한다.
- **후보와 공개 결과:** 기존 실행의 실제 serializer에서 이미지의 `non_novel_media` 판정, 공식 상세 응답 부재, 합의만 있는 미결속 후보가 HOLD로 남았다. 후보·후보 URL 보존과 공식 공개쌍의 null, gate 비우회를 별도로 검사하도록 정정한다. 바뀐 시험 이름의 대응표도 보존한다.
- **OCR 검색:** 내부 인용부호와 원시 제목을 보존하고, 근거 종류·제목 역할 누락을 `promotion_eligible` 하나로 보충하지 않는다. 적격 이미지 한 항목의 원시 OCR에 제목·작가가 함께 있는 정확한 작가 확인 질의가 앞선 제거 분기에서 사라지던 코드를 수리했다. 기존 양성과 추가 음성 15사례가 `phase2b`에서 통과했다.
- **별칭·댓글 fetch:** 댓글 URL 시험의 가짜 응답이 실제 fetch 경로에 닿지 않는 차이를 확인했다. 본문 약칭은 원형 입력에 결속된 비권한 후보로 보존하는 경로와 공개 승격을 나누어 검토한다. 선행 장르 거절의 진단 누락도 대상이다.
- **추천·다작품·OCR 설명:** 추천 보류가 OCR 적격성만으로 해제되는 조건, 실제 후보 주석 단계를 생략한 다작품 시험, 최종 `slang_insight.cultural_context`의 근거 없는 설명 가능성을 검토하고 있다. 최종 직렬화 관측 없이 문구 차이로 닫지 않는다.

적용 근거는 [인자·작성자 후속 정정](../../out/development_plan_20261010/r6_rework_fixture_followup_v1/application_receipt.json), [등급·설명 정정](../../out/development_plan_20261010/r6_rework_display_fixture_v1/application_receipt.json), [후보/공개 보류 정정](../../out/development_plan_20261010/r6_rework_public_hold_fixture_v1/application_receipt.json), [OCR 검색 후보 병합](../../out/development_plan_20261010/r6_rework_search_applied_v1/application_receipt.json), [작가 질의 제품 수리](../../out/development_plan_20261010/r6_rework_author_query_fix_v1/implementation_receipt.json)에서 확인한다. 각 파일의 원본·수정본·지문을 남겼다.

## 계속 남아 있는 조건

80건은 [검토 준비 자료](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)로 정리되어 있다. 80개 글에 저장 관측 112개를 연결했으며, 사람 정답과 학습 적격 행은 각각 0개다. 기존 개발에 노출된 자료이므로 독립 holdout으로 취급하지 않는다. 작품·역할·NIL 및 사용 권리 판정을 기존 참조로 대신하지 않는다.

실제80 모델 실행과 새 브라우저 실행은 이전 자동 승인 검토의 `blocked by policy` 거절 이후 재시도하지 않았다. 실제 품질, R5 전후 실측, 적격 TRAIN/CAL/FROZEN 자료, formal KPI는 여전히 미완료·NOT_ESTIMABLE이다. 로컬 mock 회귀의 통과가 이 조건을 충족하지 않는다.

이전 [자동 복구 전달 수령증](../../out/development_plan_20261010/R6_AUTO_DELIVERY_RECEIPT.json)과 원시 실행 증거는 수정하지 않는다. 후속 변경은 새 수령증으로 기록하며 기존 미커밋 변경·보호 worktree·index를 보존한다.
