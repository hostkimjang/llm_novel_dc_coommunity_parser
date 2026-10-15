# R4 고정 NIL·CAL 모델의 actual 평가 연결

최신 semantic NIL·CAL의 개선 후 모델과 baseline을 기존 actual 자료 검산기에 연결했다. 제품 모듈 1개, CLI 1개와 시험 2개를 추가했다. 구현과 합성 로컬 검증을 마쳤으며 적격 실제 자료의 전체 평가 성공·품질 수용은 미검증이다. Goal은 active, formal KPI는 NOT_ESTIMABLE, R7은 보류다.

## 동작과 사용 범위

`prepare_actual_pair()`는 양쪽의 고정 학습·분할·모델·CAL·전체 FROZEN 관측을 검산한다. 모델별 원시 점수와 온도 교정 결과를 따로 보존하고 원문 bytes·정확한 UTF-8 span·후보집합·generation proof·전체 순서를 결속한다. CLI는 저장된 성공 관측을 각각의 고정 모델로 재계산한 뒤 기존 actual builder와 독립 reader/evaluator에 전달한다. 평가 중 재학습이나 임계값 재선택은 하지 않는다.

```powershell
python tools/run_candidate_reranker_actual_evaluation.py --bundle <bundle.json> --bundle-sha256 <raw-SHA256> --output-dir <bundle-폴더-아래-새-폴더>
```

이 명령은 적격 입력을 준비한 뒤 사용하는 API 안내다. 현재 80건으로 실행한 명령이 아니다. 정확한 bundle 필드와 source envelope는 [API 계약](../../out/development_plan_20261010/goal_completion_audit_v1/r4_bridge_candidate_v1/HANDOFF_KO.md), 후속 시험 범위는 [최종 후보 인계](../../out/development_plan_20261010/goal_completion_audit_v1/r4_bridge_candidate_v3/HANDOFF_KO.md)를 따른다. 기존 descriptive CLI는 유지한다.

성공한 저장 결과는 `pair_report.json`, `evaluation_report.json`, 마지막 `workflow_receipt.json`이다. 실제 평가 진입이 허용되면 별도 producer·양쪽 prediction·여섯 재생 artifact와 `readback/`도 생성한다. 일반 텍스트 원문은 원래 bytes를 보존하는 JSON 보관물로 결속한다. 출력은 새 폴더에만 쓰며 마지막 수령증 확정 전 읽기·쓰기 실패가 나면 성공 수령증을 만들지 않는다.

실제 평가 진입에는 SOURCE_BACKED 모델, 모든 행의 HUMAN_GOLD, 모든 출처의 REUSE_PERMITTED, v4 사전등록 정책이 필요하다. 그 뒤에도 기존 P1·라벨 원장·준비도·원문·전체 분모·baseline·구간 검산을 통과해야 한다. 파일의 선언과 SHA는 사람 판정이나 권리의 사실을 독립 인증하지 않는다. `GO_FROZEN_ACTUAL_SHADOW_ONLY`도 운영 품질 수용으로 승격하지 않는다. 공개 적용·공개 권한·중앙 DB 쓰기는 false다.

## 이번 검증

고정 복사본에서 관련 Python 8개 파일을 한 묶음으로 실행했다. 결과는 **271 passed, 9 subtests passed in 167.12s (0:02:47)**다. [시험 수령증](../../out/development_plan_20261010/r4_actual_bridge_validation_v3/phase_first/run/receipt.json)에 소스 시작/끝 SHA, 실제 import 경로, 자원 관측과 원본 보존 검산을 남겼다. CPU 1개·BelowNormal·수치 연산 스레드 1개를 유지했다. pytest 안에서 합성 TRAIN/CAL fixture를 만들었으며 실제 자료 학습·외부 모델·브라우저·웹 서버 실행은 없었다. 실제 모델 런의 대시보드 ON 정책과 별도 범위다.

앞선 실행에서 pytest가 복사본 밖의 설정 파일을 탐색해 읽기 방어에 걸렸다. 복사본 설정·루트를 명시해 수리한 뒤에는 신규 시험의 parameterize 인자 누락으로 수집이 중단돼 시험 인자를 보완했다. 그 뒤 실행은 **2 failed, 269 passed, 9 subtests passed in 176.75s**였다. 두 실패는 Windows의 subprocess audit에서 executable 값이 None인 경우를 실행기가 처리하지 못해 도움말 자식 기동 전에 발생했다. 제품 소스는 그대로 두고 정확한 명령·경로·환경 검산을 유지하며 실행기만 수정했다. 앞선 실패 기록은 보존하고 마지막 통과 수치와 합산하지 않는다. 실행별 SHA와 판정은 최종 전달 수령증에 기록한다.

- 같은 사건 공간에서 독립 학습·교정한 서로 다른 두 모델의 score·확률·fit을 각 arm에 대조했다. after 결과를 baseline에 복사하는 반례도 거절했다.
- 미실행·미가용·잘못된 입력, EMPTY·TRUNCATED·gold miss의 전체 분모를 보존하고 부분 prediction 생성을 막았다. EMPTY/TRUNCATED 경계 시험은 기존 v1 NIL 실제 scorer를 썼다. 유효 ABSTAIN의 확률은 유지했다.
- UNJUDGED를 새 정답으로 바꾸지 않았다. 현재 전체 분할 계약에서는 trainer와 기존 model/fit 재사용이 먼저 거절된다. 정상 actual CLI로 UNJUDGED 보고서를 끝까지 저장했다는 뜻은 아니다.
- 새 하위 연결부가 실제 P1 검산을 거쳐 준비도 **0/18**에서 거절되는 것을 확인했다. 그 경로가 저장한 예측·모델 재생 artifact를 기존 parser로 다시 검산했다. 합성 자료의 등급이나 성공 게이트를 mock으로 바꾸지 않았다.
- 새 CLI와 기존 평가 CLI의 실제 `--help` 자식 실행, 원문·점수·ID·순서 변조, 출력 덮어쓰기 방지와 마지막 수령증 실패를 확인했다.

적격 실제 입력이 없어 `evaluate_bound_actual_readback_bundle()`의 전체 성공 경로는 이번에 실행하지 않았다. 하위 구조 왕복·준비도 거절과 실제 평가 성공을 구분한다. 전체 저장소 회귀나 실제 품질·처리 비용 검증 완료도 아니다.

## 80건 준비와 남은 조건

[80건 검토 안내](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)의 원문·112개 저장 관측·참조는 보존했다. 사람 정답 0건, 학습 준비 0건, 재사용 권한 UNKNOWN이며 80건 모두 개발에 노출됐다. 후보 누락 3행과 이미지 25개 미검토가 남아 있다. 독립 holdout으로 간주하지 않는다.

2026-10-10 이 연결부를 전달할 당시 실제80·Chrome 실행은 자동 승인 검토의 `blocked by policy`로 차단돼 있었다. 이후 재승인 실행·의미 검토와 제한된 현재 UI 관측은 [P4 운영 인계](P4_REAPPROVAL_RUN_20261010_KO.md)를 따른다. 그 후속 실행·화면 확인으로 actual bridge의 적격 실자료 전체 성공을 대신하지 않는다. 사람 판정·권리·적격 TRAIN/CAL/FROZEN 자료, 실제 품질과 R5 계측은 계속 미완료다. 원래 미커밋 변경·HEAD·빈 staging 및 과거 실행 증거의 보존 검산은 이 문서의 전달 당시 범위다.
