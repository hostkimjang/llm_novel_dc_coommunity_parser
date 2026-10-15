# expert_main 통합·대시보드 구현과 검증 기록

> 현재 상태는 [현재 상태 문서](CURRENT_STATUS_KO.md)를 따른다. 날짜별 기록과 `out/`·`logs/` 링크는 로컬 보존 자료이며 Git checkout에 포함되지 않을 수 있다.

<!-- r5-resolution-current:start -->

## 현재 상태 안내 — 2026-10-15

현재80 범위 개발·검증과 Goal 완료 상태는 [현재 상태와 남은 작업](CURRENT_STATUS_KO.md)에서 관리한다. 전체 의미 `REVIEW`·기존5개 실패·독립 평가/R7 보류·새 분기 실측 미관측을 함께 확인한다. 아래 날짜별 실행·시험·미완료 표기는 당시 이력이다.

<!-- r5-resolution-current:end -->

## 2026-10-14 시작 전 실패와 기존 상대경로 결과 표시

생성자 단계에서 실패해 `batch_start`가 없으면 `batch_prepare`로 새 시도의 run·output·분모를 결속한 뒤 FAILED를 전달한다. 이미 실행 중인 배치는 준비 이벤트로 덮어쓰지 않으며, 같은 run의 다른 output/scope도 거절한다. 프런트엔드는 준비 이벤트에서 이전 결과·복원 캐시를 비우고 이전 요청의 늦은 응답을 폐기한다. 실패 기록의 프로세스 종료 미확인과 실제 runner 종료값은 구분한다.

기존 manifest의 repo 상대 `out/...` 출력은 정확한 sidecar와 결과 루트 안에 결속될 때만 읽는다. 기존 out 기준 상대경로와 절대경로는 유지하며, 모호한 두 경로·부모 이동·symlink 탈출·다른 sidecar는 거절한다. 원본 manifest는 고치지 않는다. 실제50·12의 이력과 상세 BOUND, 메모·NSFW·요청/실효 병렬도 표시를 확인했다. 탐색 상한 안내는 유지한다.

최종 시험과 실제 화면 확인 범위는 [현재 연구 기록](../../out/research_completion_20261014_v1/REPORT_KO.md), [이력 결속 수리](../../out/research_completion_20261014_v1/dashboard_manifest_path/REPORT_KO.md), [시작 전 실패 수리](../../out/research_completion_20261014_v1/dashboard_prestart_failure/REPORT_KO.md)를 따른다. 아래 기록은 당시 이력이다.

## 2026-10-10 최신 진행: 전체 진입점과 완료 표시

80건 검토 자료 준비를 유지하면서 일반 `expert_main` 전체 진입점의 합성 입력 OFF·재생 ON·최초 분석 ON을 검증했다. 최초 ON은 provider1회·native7회를 거쳐 원래 HOLD와 별도 결과를 보존했다. 대시보드의 완료 상태·부분집합·실패·저장 대기와 이력 건수 표시를 수리했다.

관련 Python 3파일은 **71 passed, 40 subtests passed in 10.17s**, **Node 84개 통과·실패 0개·skip 0개**다. 일반 CLI 검증과 이후 UI/API 변경의 시험 범위를 분리한다. [현재 검증·남은 개발](EXPERT_ENTRY_COMPLETION_REVIEW_20261010_KO.md)을 따른다. 아래 수치와 당시 미완료 설명은 이전 단계 기록이다.

후속으로 semantic NIL/CAL→actual readback·baseline 연결을 구현하고 합성 로컬 검증을 마쳤다. **271 passed, 9 subtests passed in 167.12s (0:02:47)**이며 [R4 연결 검증](R4_ACTUAL_BRIDGE_20261010_KO.md)에 범위와 한계를 기록했다. 적격 실제 자료의 전체 성공 경로, 실제80·새 브라우저·사람 판정·실자료 품질·R5 실측은 미완료다. Goal active·formal KPI NOT_ESTIMABLE·R7 보류를 유지한다.

## 이전 검증: 기존 회귀 수리와 80건 검토 준비

기존 rework 실패 33개는 이름 변경 대응표와 실제 JUnit을 대조해 모두 통과했다. 마지막 3개 파일 실행은 **494 passed, 55 subtests passed in 181.10s (0:03:01)**다. 앞선 9개 파일 실행의 **5 failed, 578 passed, 64 subtests passed in 572.95s (0:09:32)**에서 시험 의존 파일 누락 4건과 최종 후보 단계의 기대 불일치 1건을 확인하고 보완했다. 제품 소스는 두 실행 사이에 그대로이며, 앞선 나머지 6개 파일의 통과를 따로 보존한다. 서로 다른 실행 수치를 합산하지 않으며 전체 저장소 회귀나 전체 CLI 검증 완료로 해석하지 않는다. [현재 수리 기록](LEGACY_REWORK_REPAIR_20261010_KO.md)과 [최종 실행 검산](../../out/development_plan_20261010/r6_rework_phase4_reconciled.json)을 따른다.

원형 본문에 결속된 별칭은 비권한 후보로 보존하고, 일반 화자 발화는 명시적인 작성자 복귀 전까지 보류한다. URL·시각 예외, OCR 작가 검색, 추천 보류와 최종 설명 봉인을 검증했다. 후보 제목·URL 보존과 최종 공개 title/URL을 따로 확인하며, 검색 후보만으로 공개 권한을 만들지 않는다.

[80건 검토 자료](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)는 원문·저장 관측 112개와 참조를 연결했고 [독립 재판독](../../out/development_plan_20261010/r6_rework_actual80_preparation_readback_v1_KO.md)에서 원문·참조 52개 파일의 존재와 SHA 일치를 확인했다. 사람 정답 0건·학습 준비 0건·전 행 개발 노출·권한 UNKNOWN이며 후보 누락 3행, 미검토 이미지 25개는 남아 있다.

현재 상태는 **REWORK_LOCAL_VERIFIED_ACTUAL_PENDING**이다. 아래 자동 복구 수치와 33개 실패·NOT_PASS 표기는 이전 단계 이력이다. 실제80 모델 실행·새 브라우저는 자동 승인 검토의 `blocked by policy` 거절 이후 재시도하지 않았다. 실제 품질·사람 판정·적격 분할 자료·R5 실측·formal KPI는 미완료이며 formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다.

## 이전 자동 연결 단계: 일반 main 자동 복구의 로컬 검증 (2026-10-10)

일반 `expert_main`의 같은 호출 문맥을 원래 guard·commit·AUDIT·최종 저장 이후 제한된 복구로 연결하고, 별도 결과를 대시보드 live/history API와 표시까지 로컬 검증했다. 기본값은 OFF이며 ON에는 고정 정책·예산과 대시보드가 필요하다. 원래 결과·manifest·WAL은 보존하며 공개 적용·권한·중앙 DB 쓰기는 false다.

현재 상태는 **AUTOMATIC_NATIVE_LOCAL_VERIFIED_ACTUAL_AND_LEGACY_REWORK_PENDING**이다. [운영 계약](NATIVE_RECOVERY_AUTOMATION_20261010_KO.md)과 [실행별 검증·수리 기록](../../out/development_plan_20261010/r6_auto_reconciled_receipt.json)을 따른다. 검증은 합성 HTTP 응답으로 실제 전문가·guard·AST로 추출한 실제 main 함수 본문·원장·API·Node 표시를 통과한 범위다. 전체 CLI 기동과 실제 브라우저 통과를 뜻하지 않는다. 실행별 시험 수는 합산하지 않으며 마지막 수리 뒤 최초 전체 파일을 모두 다시 실행한 결과도 아니다.

최종 HOLD의 OCR 근거 누락은 새 `strict_evidence_v2` 검토 규칙으로 수리했고 기존 v1 영수증 판독은 보존했다. 실제80 모델 실행·새 브라우저·사람 정답·적격 실제 TRAIN/CAL/FROZEN 품질·R5 실측과 기존 rework 33개 실패는 남아 있다. 전체 회귀는 NOT_PASS, formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다. 아래 단계별 수치와 미완료 설명은 당시 이력이며 현재 범위는 이 절을 따른다.

## 이전 단계: 명시 native 복구 연결과 당시 남은 자동화

R6의 **명시 same-call native 복구 연결을 합성 응답·HTTP mock으로 로컬 검증했다**. 현재 검증 상태는 `PASS_NATIVE_EXISTING_REWORK_FAILURES_PENDING`이며 기존 rework 시험 실패는 미해결이다. `run_native_recovery`는 같은 분석 호출에서 보존한 pre-final 문맥을 원래 입력·저장 provider 근거에 결속하고, 실제 Decoder·Verifier·Synthesizer·Arbiter와 기존 native 공개 guard를 호출한다. 원래 결과·manifest·WAL을 덮어쓰지 않고 별도 scope의 새 publication WAL과 결과를 저장·재판독한다. guard 판정 기록은 공개 반영이 아니며 `public_apply`, `publication_authority`, `central_db_write`는 false다.

native 추가 LLM·검색·fetch는 하나의 영속 호출·byte·시간 예산을 공유하며 먼저 예약하고 전송한다. 완료 job만 저장 결과를 0회 호출로 재생하고, 미완료·불확실 요청은 재시작 후 재발송하지 않는다. upstream provider 수집은 별도 앞 단계로 합계에 표시하며, MCP 내부 원격 검색 횟수·취소·가격은 확정하지 않는다. 과거 actual80/32 저장 JSON을 살아 있는 native 문맥으로 복원하는 기능은 없다.

최초 Python 16개 파일의 원시 결과는 시험 893개 통과·32개 실패와 하위 시험 21개 통과다 (`32 failed, 893 passed, 21 subtests passed in 1228.60s (0:20:28)`, [최초 전체 수령증](../../out/development_plan_20261010/r6_native_final_receipt.json)). 합성 응답 fixture만 보정한 뒤 workflow 1개 파일의 시험 7개가 통과하고 실패는 1개, 하위 시험은 0개다 (`1 failed, 7 passed in 657.84s (0:10:57)`, [보정 후 수령증](../../out/development_plan_20261010/r6_native_repair_receipt.json)). 그 뒤 실제 fetch 응답의 identity 캐시를 복제하는 제품 코드를 수리하고 context·workflow 2개 파일을 재검증해 시험 67개와 하위 시험 0개가 통과했고 실패는 0개다 (`67 passed in 701.00s (0:11:41)`, [캐시 수리 후 수령증](../../out/development_plan_20261010/r6_native_capture_final_receipt.json)). **세 실행의 시험은 겹치므로 합산하지 않는다. 마지막 수리 뒤 전체 16파일을 다시 실행한 결과도 아니다.** [재조정 수령증](../../out/development_plan_20261010/r6_native_reconciled_receipt.json)은 새 native 경로의 실패가 수리됐음을 기록하며 최초 전체 실행을 PASS로 바꾸지 않는다.

기존 rework 시험은 전체 실행에서 31개가 실패했다. 동일한 빈 캐시·단일 파일 격리 조건의 이전 baseline과 현재 소스에서는 각각 33개 실패가 재현됐고, 33개의 예외 종류·정규화 메시지가 같았다. 비교상 남은 차이는 0개지만 시험 상태는 `FAILED`다 ([격리 비교 근거](../../out/development_plan_20261010/r6_native_isolated_rework_comparison_v1.json)). **실패 33건은 해결되지 않았으며 전체 회귀 통과나 모든 OFF 동작의 동등성을 뜻하지 않는다.** [API·검증 범위](../../out/development_plan_20261010/r6_native_api_KO.md), [현재 코드·캐시 수리 독립 검토](../../out/development_plan_20261010/r6_native_capture_cache_review.json)와 [I/O 독립 검토](../../out/development_plan_20261010/r6_native_io_closure_review.json)를 따른다. [fixture 수정 독립 검토](../../out/development_plan_20261010/r6_native_fixture_repair_review.json)는 앞선 수리 이력으로 보존한다. 이번에는 Node·브라우저 시험을 실행하지 않았다. 화면 소스는 이전 provider 단계의 [Node 66개 통과 기록](../../out/development_plan_20261010/r6_provider_node_receipt.json)과 같으며, 그 기록은 새 native 화면이나 브라우저 통과 증거가 아니다. 이전 probe 실패와 simulation/provider 시험도 별도 이력으로 보존한다.

[80건 검토 큐](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)는 그대로 보존했다. 입력 80행·저장 관측 112개·중복 게시물 32개이며, 사람 정답과 학습 준비는 모두 0건이다. 기존 WORK/NIL 참조를 사람 정답으로 승격하거나 새 독립 분모로 세지 않았다.

**일반 main의 자동 복구 스케줄과 native 결과의 대시보드 live/history 연결은 아직 미완료다.** 실제 외부 모델·검색 호출은 0회이며 실제 복구 품질·비용·formal KPI는 `NOT_ESTIMABLE`이다. P4 실제80 실행과 새 Chrome 검증은 기존 자동정책 차단을 재시도하지 않았다. 실제 자료·사람 판정·R4 학습/교정 품질·R5 실측도 남아 있다. R6 전체 완료로 처리하지 않으며 Goal은 active, R7은 보류다.

## 이전 단계: provider 근거 수집과 80건 검토 준비 (2026-10-10)

당시 R6 상태는 **PROVIDER_EVIDENCE_LOCAL_VERIFIED_NATIVE_GUARD_AND_ACTUAL_RECOVERY_PENDING**였다. 원본 HOLD·AUDIT에 결속한 명시 계획 → 영속 예약 → 단일 HTTP → 원시 응답 저장·독립 판독 → `expert_main`·대시보드 연결을 구현했다. 완료된 요청은 0회 전송으로 재생하고, 완료 여부가 불명확한 요청은 재발송하지 않는다. 최초 fresh source 검사부터 응답 저장·재판독까지 같은 시간 제한을 적용한다. 마지막 `REQUEST_FINALIZED` 자체의 저장은 이 시간 범위에서 제외한다. 저장 성공은 `PROVIDER_EVIDENCE_STORED`, 공개 guard는 `GUARD_NOT_EVALUATED`이며 일반 실행의 자동 복구는 아직 연결하지 않았다.

이전 provider 단계의 변경 영향 Python 23파일 `779 passed, 163 subtests passed in 654.67s (0:10:54)`, Node 66개 PASS다. 실제 파일 원장과 HTTP mock, 저장 결과의 API·Node 표시를 확인했다. 실제 외부 모델·검색 호출과 새 브라우저 검증은 0회다. [실행 계약·한계](../../out/development_plan_20261010/r6_provider_api_KO.md), [Python 검증](../../out/development_plan_20261010/r6_provider_final_receipt.json), [Node 검증](../../out/development_plan_20261010/r6_provider_node_receipt.json)을 따른다. 아래 이전 단계의 수치는 당시 증거이며 이번 수치와 합산하지 않는다.

[80건 검토 큐](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)를 준비했다. 원래 입력 순서 80행에 112관측·관측별 후보 기록 121개를 연결했고 중복 게시물 32개를 별도 표본으로 세지 않았다. WORK 2·NIL 6은 기존 모델 참조, UNJUDGED는 72건이다. 사람 정답·학습 준비는 모두 0건이며 전 행이 개발에 노출됐다. 후보 결손 3행과 미검토 이미지 21행을 검토 순서에 반영했지만 정답·역할·사용 권리를 채우지 않았다. [검산 수령증](../../out/development_plan_20261010/actual80_review_queue_v1/verification_receipt.json)에 원본 46개·이전 준비 파일 5개의 보존 근거를 남겼다.

당시 남은 범위는 P4 실제80·새 브라우저, 실제 corpus·사람 판정·TRAIN/CAL/FROZEN 품질, R5 실측, R6 native 공개 guard·자동 복구·실제 품질이었다. 현재 native 연결과 미완료 범위는 위 최신 기록을 따른다. 당시 R6 후속 계획은 [native guard 개발 메모](../../out/development_plan_20261010/r6_native_guard_next_steps_KO.md)를 따른다. 기존 자동 승인 차단을 재시도하지 않았으며 formal KPI는 `NOT_ESTIMABLE`, Goal은 active, R7은 보류다.

NIL 학습·저장·화면 표시와 CAL 온도 학습·FROZEN 소비의 최신 상태는 [R4 운영 기록](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)을 따른다. 명시적 FROZEN 재관측 교정·capture 저장·화면 표시를 연결했다. 의미 역할·검증 자료의 별칭 관측과 저장·화면 표시를 추가했다. 새 의미 관측을 버전별 학습·모델·CAL에 연결하고 합성 로컬 회귀로 검증했다. 일반 R2 graph 자동 공급과 새 입력의 고정 교정 추론을 로컬 검증했다. 실제 자료 품질 평가와 새 소비 화면의 브라우저 확인은 남아 있다. 이전 단계 시험 수는 합산하지 않는다.

[R6 제한 복구 실행](BOUNDED_RECOVERY_EXECUTION_20261010_KO.md): 당시 상태 **LOCAL_ENTRYPOINT_UI_VERIFIED_ACTUAL_RECOVERY_PENDING**. 별도 `expert_main` 합성 복구 진입점과 검토·계획·AUDIT·복구 보고서의 API·live/history 표시를 연결했다. 변경 영향 Python 13파일의 382개 시험·45개 하위 시험과 Node 37개, 실제 브라우저 및 별도 main 프로세스 합성 검증을 통과했다. 실제 모델·검색 호출은 0회다. 실제 provider 전체 연결·자동 복구·품질 평가는 남았으며 앱 Goal은 active다.

2026년 10월 10일, 승인된 [개발 계획](EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md)의 P0~P3 구현을 기본 프로젝트 폴더에 반영했다. R1 읽기 전용 snapshot, R2 후보 회수 SHADOW, R3 커뮤니티 지식 READ_ONLY와 R4 고정 후보 scorer·학습 분할 계약도 구현하고 로컬 통합 검증을 통과했다. R4의 최신 상태는 아래 학습 baseline 기록을 따른다. **P4 최종 코드의 새80건 실행·의미 검토, R2/R3 실제 자료 평가, R4 실제 source-backed 학습·평가와 NIL 확률 교정, R5 실제 paired 계측과 R6 실제 복구 실행·품질 검증은 남아 있으며 앱 Goal은 active다.** 원래 G1~G7 완료와 R7 production 전환 보류를 유지한다.

## R5 후속 구현

R5 저부하 RunSpec v3·실제 실행 관측·계획 생성·판독·화면을 구현하고 Python51파일·1147개 시험·210개 하위 시험과 Node26개 PASS, reader 행 결속 보강 후 영향9파일·269개 시험·97개 하위 시험 PASS, 독립 반례18개와 합성 live/history 표시를 확인했다. 실제 모델·검색 실행0이며 비용·품질·formal KPI는 NOT_ESTIMABLE이다. 상태는 **LOCAL_CONTRACTS_VERIFIED_ACTUAL_PAIRED_MEASUREMENT_PENDING**다. [운영 계약과 검증 근거](PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md)에 원본 참조·새 arm·관측·정식 KPI를 구분했다. 기존 시험 수치는 해당 시점의 기록이다.

## 적용과 보존

통합 대상은 `C:/Users/kimjang/Documents/GitHub/llm_novel_dc_coommunity_parser`, 최신 원본은 `C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser`다. 최신 runtime41개, dashboard3개, 도구4개, 관련 시험·fixture를 포함한 고유67개 파일을 선별 반영했다. 이 중34개는 기본 폴더에 새로 생겼다. 이후 P2/P3 기능과 아래 호환성 수리를 추가했다.

수정 전 파일 바이트와 전체 dirty 상태·staged/unstaged patch는 `out/development_plan_20261010/integration_backup_01/`에 있다. [최초 적용 수령증](../../out/development_plan_20261010/integration_apply_receipt.json)은 적용 당시 전후 해시이며 후속 수정의 최종 해시와 구분한다. [사전 명세](../../out/development_plan_20261010/integration_selection_plan.json)의 `PLAN_ONLY_NOT_APPLIED`는 당시 조사 상태로 보존했다.

primary의 연구 benchmark·workflow 6개, HEAD와 staged 내용, `233b` 원본과 저장 결과를 보존했다. Git index의 원시 바이트 변경은 아래 보존 기록에 구분했다. 기본 폴더 CWD·PYTHONPATH와 실제 `module.__file__`를 검사했으며, 시험에서는 `233b/.venv/Scripts/python.exe`를 interpreter로만 재사용했다. 소스가 이전 worktree를 참조하도록 연결하지 않았다.

## 구현한 동작

| 범위 | 변경 내용 | 현재 근거 |
|---|---|---|
| P1 실행 코드 | 최신 문맥·발화·별칭·OCR·호출 장부 및 운영 도구 통합 | 핵심 회귀, primary import 경로 확인 |
| P2 판정 상세 | 사유와 메모 독립 표시, NSFW boolean·미기록·형식 오류 구분 | 표시 시험22개, 원본 B14 live/history 화면 |
| P2 실행 이력 | 중첩 manifest와 기존 filename 조회, 불투명 run_key, 부분집합·최종·미확인 상태 | 백엔드61개＋subtests12개, 실제32 이력 선택·로그 |
| P2 R08 | 행 저장 당시 receipt와 manifest 종료 계측 분리, null·NOT_ESTIMABLE 유지 | 원본32 API·브라우저, 결속 불일치 시험 |
| P3 유효 설정 | general·low-load-validation·paired-measurement 프로필, CLI/환경/프로필 출처와 실제 자원 관측 | 설정·CLI·계측 회귀와 합성 화면 |
| P3 문맥 진단 | 최종 producer receipt에서 구조·원문 위치·proof를 선택 저장하고 화면 표시 | producer 시험, 64KiB 상한·공개 결과 불변 시험, live/history 화면 |

이력 탐색은 breadth-first와30초 캐시를 사용한다. 기본 상한은 항목50,000개·manifest2,000개·깊이12다. 실제 원본 out에서101개 실행을 발견했으며 최초6.512초, 캐시0.102초였다. 상한에 도달하면 일부 이력 생략을 화면에 알린다. 전체 이력이 모두 열거됐다는 뜻은 아니다. 선택 결과는128MiB, manifest는2MiB 상한이며 잘못된 경로·symlink·실행 불일치를 거부한다.

P3의 일반 실행은 기존 VLM OFF·OCR ON·장부 OFF를 유지한다. 최근 검증은 `--execution-profile low-load-validation --parallel 1`을 사용한다. 이 프로필은 VLM/OCR ON·장부 SHADOW·진단 ON을 기본으로 삼고 실제 CPython 프로세스의 BelowNormal·단일 CPU·numeric threads1을 검증한다. 개별 CLI가 환경변수보다, 환경변수가 프로필보다 우선한다. paired 프로필은 기존 RunSpec·실측 조건을 대신하지 않는다.

진단 스키마는 `source_context_diagnostics_v1`이고 OFF·NOT_AVAILABLE·STORED·TRUNCATED를 구분한다. 전체 canonical UTF-8 JSON64KiB, 컬렉션24개, 문자열512자 상한과 생략 사유가 있다. `publication_authority=false`이며 새 진단·설정 메타는 durable public payload digest에서 제외해 공개 판정과 분리했다. 과거 결과의 구조를 화면에서 추론해 채우지 않는다.

## 통합 중 수정한 호환성 문제

Windows는 POSIX0600 모드만으로 키 파일 접근을 판정할 수 없었다. 현재 소유자와 SYSTEM만 허용하는 보호 DACL을 파일 생성 시점부터 적용하고 기존 파일 소유자·hardlink·reparsepoint도 검사한다. 원본 키를 덮어쓰지 않으며 제한 실패 때 비밀값을 쓰지 않는다. [독립 검토](../../out/development_plan_20261010/private_file_review_initial.md)의 초기 지적2건을 수정했고 후속 정적 검토는 PASS다.

`experts` 패키지의 eager import는 일부 모듈을 먼저 import할 때 순환을 만들었다. 공개 export 이름을 보존하는 lazy import와 내부 상대 import로 수정했고 `llm_batch`·`src.llm_batch` 두 namespace를 새 프로세스에서 검사했다. paired 계측 시험의 오래된 fixture는 현행 v2 binding·envelope 계약에 맞췄다. legacy 계약과 실패 검사는 보존했다.

## 검증 상태

| 검증 | 결과 | 산출물 |
|---|---|---|
| 초기 통합 시험 | 318 PASS·34 FAIL·subtests43 PASS; 당시 발견한 오류는 후속 수리 | `p1_tests.log` |
| 계측·키 파일·import 수리 | 65 PASS·subtests26 PASS | `p1_repairs_tests_v4.log` |
| P2 백엔드 | 61 PASS·subtests12 PASS | `backend_tests_receipt.json` |
| 프런트엔드 최종 묶음 | 22 PASS | `final_node_tests.txt` |
| P3 | 75 PASS·subtests21 PASS, 추가 publication53 PASS·subtests17 PASS, 마지막 경계6개·CLI12개 PASS | `p3_verification_receipt.json` |
| 수정 영역 통합 회귀 | Python25파일468 PASS＋subtests84 PASS, 실패·오류·건너뜀0 | `final_focused_receipt.json`, `final_focused_tests.log` |
| 브라우저 | PASS, 콘솔 오류·경고0 | `browser_verification_receipt.json` |
| R1 정식 snapshot 도구 | 시험28 PASS, 저장80·32의 관측112행/고유80개 검산 PASS | `r1_package_verification_receipt.json` |
| R2 포함 최종 통합 회귀 | Python33파일608 PASS＋subtests122 PASS, 표시23 PASS, 변경 중 소스0 | `r2_validation_receipt.json` |
| R2 독립 검토·화면 | scope 결함 수리 후14개 확인 PASS, live/history PASS·콘솔0 | `r2_integration_final_review_receipt.json`, `r2_browser_receipt.json` |
| R3 포함 최종 통합 회귀 | Python 37개 파일의 시험 726개와 하위 시험 132개, 화면 표시 시험 24개 PASS, 시험 중 소스 변경0 | `r3_validation_receipt.json` |
| R3 독립 검토·화면 | runtime21개·pipeline5개 묶음 PASS, live/history PASS·콘솔0 | `r3_runtime_independent_final_review_receipt.json`, `r3_pipeline_independent_final_review_receipt.json`, `r3_browser_receipt.json` |
| 초기 v1 R4 통합 회귀 | Python44파일916 PASS＋하위139 PASS, Node25 PASS, 시험 중 소스 변경0·외부 socket0 | [수령증](../../out/development_plan_20261010/r4_validation_receipt.json) |
| R4 독립 검토 | adapter·runtime·split 후속 PASS, 하네스 정적 검토 PASS·기존98개 assertion 호출 보존 | `r4_reranker_independent_final_review_receipt.json`, `r4_runtime_independent_final_review_receipt.json`, `r4_split_independent_final_review_receipt.json`, `r4_harness_independent_review_receipt.json` |
| R4 브라우저 | 합성v3 live/history SCORED_SYNTHETIC·TRUNCATED와 빈 순위 구분, 콘솔0 | [화면 수령증](../../out/development_plan_20261010/r4_browser_receipt.json) |
| 최종 코드 새80건·의미 검토 | 당시 실행 준비 후 자동 승인 차단으로 미시작; 재개 전 최신 소스·서비스 재검증 필요 | `p4_launch_preflight.md`, `p4_launch_rejection.json` |
| formal KPI | NOT_ESTIMABLE | paired 조건 충족 전 유지 |

시험 묶음이 겹치므로 위 수치를 합산해 고유 시험 수로 주장하지 않는다. 초기 P1 시험은 Windows HANDLE 선언 오류로 자원 제한 적용을 확인하지 못했다. 이후 수리·P2/P3 시험과 임시 서버는 실제 PID의 priority16384·단일 affinity2·numeric threads1을 확인했다.

P0~P3 완료 시점의 통합 회귀는67.51초, 실제 CPython PID82308에서 수행했다. 주요 모듈6개의 primary import, 소스·선택 시험·fixture224개 해시 불변, 외부 socket 시도0을 확인했다. JUnit552건은468개 시험과84개 subtests를 포함한 값이다. 경고1개는 사전 import 검사로 인해 anyio의 assertion rewrite를 적용하지 못했다는 안내다.

브라우저는 기본 폴더 서버·정적 자산을 사용했다. 테스트 프로세스의 결과·로그 루트만 `233b`로 지정해 원본32를 읽었으며 live/history 양쪽에서 B14 사유·메모·NSFW false·구조 미저장·같은 실행 로그를 확인했다. 행의 `PENDING_EXTERNAL_LEDGER_LINK`, manifest의 연결32건과 `UNBOUND_PARTIAL/NOT_ESTIMABLE`, formal 값 null을 구분했다. 원본 메모의 과거 의미 오류는 수정하지 않았다.

새 설정·발화 진단은 순수 producer로 만든 `SYNTHETIC_DISPLAY_FIXTURE`를 통해 저장→API→화면을 확인했다. 실제 모델 검증을 대신하지 않으며 fixture의 source SHA는 생성 당시 값이다. 1280×720에서 구조 펼침과 가로 넘침 없음도 확인했다. 임시 서버18765·18766과 탭은 종료했다.

원본 result SHA-256은 `f244caa640c7799daf982cac0a99bd87d6a5dd661a39dbec74f6b5d95f36c153`, manifest는 `93b0873a3a2f777a25d38b273b7635d40e407767361c993ec289c1d5871ba46c`로 화면 검사 후에도 동일했다. 관련 근거는 모두 `out/development_plan_20261010/`에 있다.

![중첩 실행 이력 확인](../../out/development_plan_20261010/browser_history_list.png)

## 남은 작업

R2는 별도 고정 corpus를 조회하는 BM25 관측기를 OFF 기본값으로 추가했다. 원래 제목·본문·댓글의 위치를 보존하고 모델·검색 호출이나 공개 후보 ledger에 관측 후보를 넣지 않는다. 실제 pipeline·원래 publication payload 비간섭과 저장→대시보드 연결을 검증했다. [R2 운영·검증 문서](CANDIDATE_RETRIEVAL_SHADOW_20261010_KO.md)에48KiB 관측/64KiB 저장 상한·실행 옵션·corpus/평가 계약을 기록했다. 실제 source-backed corpus와 참조 ID 대응은 준비되지 않아 회수 성능은 NOT_ESTIMABLE이다. 기존 benchmark6파일은 보존했다.

R2 보존 검사에서 원본 선택67파일·기존32 결과·연구6파일·수정 전 백업이 동일했다. Git index의 byte SHA는 이전과 달라졌지만 HEAD와 staged binary patch는 동일하며 stage·reset·commit은 수행하지 않았다. index 바이트 불변과 staged 내용 보존을 구분해 [보존 수령증](../../out/development_plan_20261010/r2_preservation_receipt.json)에 기록했다.

R3는 [커뮤니티 지식 READ_ONLY](COMMUNITY_KNOWLEDGE_READ_ONLY_20261010_KO.md)로 구현했다. 로컬 capture→중립 parser→세 namespace→immutable query→실제 Decoder prompt→저장→화면을 연결했다. snapshot/config를 판정 범위에 결속하고 Slang DB·배치 학습·source-only early route를 차단한다. 후보만의 공식 제목/URL 공개 차단과 독립 근거 정상 경로, 조사 경계·오류 소비 상태를 검증했다. 전체 통합 Python 37개 파일의 시험 726개와 하위 시험 132개, 화면 표시 시험 24개와 두 독립 검토·브라우저가 PASS이며 actual corpus 품질은 NOT_ESTIMABLE이다. [R3 전달 수령증](../../out/development_plan_20261010/R3_DELIVERY_RECEIPT.json)을 따른다.

R1은 모델 실행과 독립된 읽기 전용 기능으로 먼저 구현했다. [운영·검증 문서](RESEARCH_EVALUATION_SNAPSHOT_20261010_KO.md)에 명세와 CLI, 과거 입력 경로 미기록2건, reference 미결속·UNJUDGED와 후속 typed 후보 연결을 명시했다. 이 snapshot은 새 실제 실행·의미 승인·정답을 만들지 않는다.

P0~P3 완료 뒤 P4 실행을 준비할 당시 기존 vLLM 모델 목록, MCP readyz와 실제 검색 3건, primary standalone 대시보드의 health를 확인했다. 입력은 80게시글·193댓글·이미지 블록 25개이며 원본 SHA가 일치했다. 새 출력은 `out/p4_primary_actual80_20261010/run/result.json`으로 준비했다. 그러나 자동 승인 검토가 실행 명령을 `blocked by policy`로 거절했고, 사용자의 명시적인 ‘해당80건 실행 승인’ 뒤에도 같은 거절이 발생했다. 세부 이유는 반환되지 않았다. 새 output이 생기지 않았고 실제 모델런은 시작되지 않았다. 자동 승인 차단 2회 뒤에는 재시도하지 않았다. [차단 수령증](../../out/development_plan_20261010/p4_launch_rejection.json)에 기록했다. 이 준비 기록은 현재 서비스 상태나 R3 추가 후 소스 고정을 보증하지 않는다. 실행 재개 전에는 최신 소스·설정·입력 지문과 서비스 상태를 다시 확인하고 새 실행 범위를 고정해야 한다.

P4는 최종 소스와 기존80 입력을 고정하고 새 출력에서 실제 실행한 뒤 저장·실패·대기 분모와80행의 원문·공개 결과를 검토한다. 기존32를 독립 표본으로 더하지 않는다. R1~R6은 기존 구현을 재사용하면서 평가 snapshot·corpus·학습/평가 분리·paired 조건을 먼저 고정한다. 구현과 로컬 시험 완료를 실제 품질·비용 개선으로 소급 해석하지 않는다.

[80행 참조 색인](../../out/development_plan_20261010/p4_semantic_reference_inventory.json)과 [검산 기록](../../out/development_plan_20261010/p4_semantic_reference_inventory_validation.json)을 준비했다. 기존16의 원본 등급은 `MODEL_REFERENCE`이며 WORK2·NIL6·UNJUDGED8이다. 추가64는 원본 참조 등급이 없어 UNKNOWN으로 기록했다. 전체 판정 분모는 WORK2·NIL6·UNJUDGED72, 채점 가능한 기존 모델 참조는8건이다. R25 전체80·R26 후속32와 확정 회귀11개를 별도 근거로 연결했고 원본35개 해시·JSON pointer787개의 불일치는0이었다. 새80의 판정은 전부 UNJUDGED이며 과거 결과를 새 정답으로 승격하지 않는다.


R4는 [고정 후보 재정렬·학습 분할 운영 문서](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)에 완료한 로컬 계약과 남은 실제 모델 작업을 구분했다. `--candidate-reranker SHADOW`는 R2 SHADOW를 요구하며 expert 이전 원문과 고정 corpus ID를 점수화한다. 기본 OFF는 로드·호출이 없고 SHADOW는 기존 모델·검색·공개 판정에 쓰지 않는다. 초기 v1 검증 당시에는 `SYNTHETIC_FIXED_SCORES_V1` 하나였다. 최신 learned baseline과 실제 자료의 미완료 상태는 아래 기록을 따른다.

초기 v1 R4 통합은 PID86872에서 146.344초 동안 실행했고 priority16384·affinity2·numeric5개=1을 시작·종료 시 확인했다. Python44파일의 시험916개·하위139개와 Node25개가 통과했고 소스 변경·외부 socket 시도는0이었다. 과거 R3의37/726/132/24는 당시 이력으로 유지하며 합산하지 않는다. 경고1개는 기존 Windows Temp 정리의 WinError145이며 시험 실패는0이고 공용 Temp를 별도 삭제하지 않았다. 하네스는 현재 소스의 합성 graph를 strict 검산했고 기존23개 publication/calibration 시험의 assertion 호출98개를 보존했다. 과거 원본 ledger SHA 불일치를 수정하거나 Golden18 정상 재생을 주장하지 않는다.

대시보드는 합성v3의 live/history SCORED_SYNTHETIC과 NOT_SCORED_GENERATION_TRUNCATED·빈 순위·미교정 확률을 구분했다. 콘솔 경고·오류0이며 publication scope 미기록은 PARTIAL로 유지했다. [live](../../out/development_plan_20261010/r4_browser_final_live.png), [history 점수](../../out/development_plan_20261010/r4_browser_final_history_scored.png), [history 후보 일부](../../out/development_plan_20261010/r4_browser_final_history_partial.png)에 근거가 있다. 실제 품질 증거는 아니다. 확인용 실제 서버 PID35684와 wrapper PID82804를 종료했고18769 포트가 열려 있지 않음을 확인했다.

R1~R4 신규 회귀시험12개와 합성 helper1개가 `/tests/*` 규칙에 가려져 있던 문제는 `.gitignore`의 명시 예외13개로 해결했다. stage·commit 여부와는 별개다. 최종 전달·보존 근거는 [R4 전달 수령증](../../out/development_plan_20261010/R4_DELIVERY_RECEIPT.json)과 [보존 수령증](../../out/development_plan_20261010/r4_preservation_receipt.json)에 모은다. source·기존 자료의 보존 상태는 이 최종 수령증의 실제 관측값을 따른다.

[R5 준비 계약](../../out/development_plan_20261010/r5_implementation_contract_KO.md)은 초기 조사 결과다. 현재 v3 로컬 기능은 구현·검증됐으며 실제 paired 계측은 남아 있다. [R6 준비 계약](../../out/development_plan_20261010/r6_implementation_contract_KO.md)은 당시의 읽기 전용 설계다. 현재 합성 실행·판독과 남은 실제 실행 범위는 [R6 운영 기록](BOUNDED_RECOVERY_EXECUTION_20261010_KO.md)을 따른다. R7 production 전환은 보류한다.

## R4 학습·NIL 후속

R4 상태는 **GENERAL_INFERENCE_LOCAL_VERIFIED_BROWSER_AND_ACTUAL_DATA_PENDING**다. 일반 입력의 실제 R2 원문·후보 ID·작품/판본·출처 bytes를 고정 semantic NIL 모델 및 CAL 온도에 연결하고 expert_main 저장·API·대시보드 표시를 구현했다. 현재 원문·R2·모델 점수를 재생 검산하며, FROZEN 배정이나 정답을 만들지 않는다. 이번 로컬 회귀는 Python 38파일 `1440 passed, 42 subtests passed in 229.37s (0:03:49)`, Node 58개 PASS다. 실제 pipeline에서 저장한 live/history 자료를 Node 표시 시험으로 연결했다. 실제80 준비 묶음은 112관측/80고유행을 원문과 연결했으나 사람 정답0·학습 준비0이며 전 행이 개발 노출 자료다. 실제 TRAIN/CAL/FROZEN 품질, 새80 모델 실행, 새 화면의 브라우저 검증과 R6 실제 provider 복구는 남았다. 실제 모델 API·검색·source-backed 학습은 0회다. 실제80·Chrome의 자동 승인 검토가 blocked by policy로 차단한 실행은 재시도하지 않았다. formal KPI는 NOT_ESTIMABLE, Goal은 active다.

[운영 계약](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)에 v1/v2 구분, CLI와 평가 범위를 기록했다. 과거 수령증은 당시 소스의 증거로 보존한다.

명시 FROZEN 재관측의 설정·저장·화면 계약과 검증 근거는 [운영 기록](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)을 따른다.


## 일반 입력 교정의 실행·저장·표시

`--candidate-inference SHADOW --inference-bundle <bundle.json> --inference-bundle-sha256 <raw-SHA>`를 기존 R2·고정 NIL 모델 옵션과 함께 사용한다. 기본 OFF이며 v2 의미 모델에는 의미 관측 SHADOW도 필요하다. 새 bundle은 명시된 source raw bytes·corpus·기존 CAL artifact를 묶으며 새 학습을 수행하지 않는다. 온도 수치 재생 검산과 새 온도 fit을 구분한다.

성공은 TEMPERATURE_APPLIED_BOUND_INFERENCE, 현재 고정 모델의 수치 검산, 저장 참조 SAVED를 함께 요구한다. 행의 candidate_reranker_inference/candidate_inference_capture와 manifest의 candidate_inference_policy를 보존한다. 화면은 현재 게시글·run/scope·CAL/model/원문 지문까지 대조한다. 후보가 비거나 잘렸거나 저장/검산에 실패하면 확률은 null이다. NIL 제안은 정답이나 공개 판정이 아니며 전체 웹 recall도 주장하지 않는다.

[정확한 API·bundle 구성·한계](../../out/development_plan_20261010/r4_general_inference_api_KO.md)와 [실제80 준비 보고서](../../out/development_plan_20261010/actual80_preparation_v1/report_ko.md)를 따른다. P4·실제 자료 품질·R6는 계속 미완료이며 Goal은 active다.
