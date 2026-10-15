# 제한된 복구 실행기 개발 기록

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

이전 합성 연결 단계의 상태는 **LOCAL_ENTRYPOINT_UI_VERIFIED_ACTUAL_RECOVERY_PENDING**였다. 별도 `expert_main` 합성 복구 진입점과 검토·계획·AUDIT·복구 보고서의 API·live/history 표시를 연결했다. 변경 영향 Python 13파일의 382개 시험·45개 하위 시험과 Node 37개, 실제 브라우저 및 별도 main 프로세스 합성 검증을 통과했다. 실제 모델·검색 호출은 0회다. 실제 provider 전체 연결·자동 복구·품질 평가는 남았으며 앱 Goal은 active다.

## 별도 실행과 화면 연결

`expert_main`에 아래 네 옵션을 함께 주면 일반 분석 준비 전에 고정 합성 계획 실행으로 분기한다. 일반 입력·모델 옵션, `--no-dashboard`, fresh/paired 계측과 혼합하면 거절한다. 기존 OFF와 정상 분석 동작은 유지한다. 기존 감사 키는 읽기만 하며 만들거나 권한을 바꾸지 않는다.

```powershell
python tools/dashboard_server.py --port 8080
python expert_main.py --recovery-simulation-plan <계획.json> --recovery-hmac-key-file <기존키.hex> --recovery-attempt-id <별도시도ID> --recovery-session-id <별도세션ID>
```

대시보드는 별도 터미널에서 먼저 실행한다. 다른 포트는 `DASHBOARD_URL` 또는 `DASHBOARD_PORT`에 지정한다. 워크플로우는 기존 loopback standalone의 시작·종료 health를 확인하며, BelowNormal·affinity 2·수치 라이브러리 5종 thread 1을 적용·관측한다. 기본 `out` 내부의 결과·manifest·보고서만 화면에 연결한다.

보고서는 고정 계획의 `output_dir/reports`에 새로 저장한다. 원본 결과 옆의 `<result.stem>_recovery_view.json`은 파일 참조만 담으며 result·manifest·WAL을 덮어쓰지 않는다. 현재는 원본 결과당 명시 보고서 하나를 연결하며 같은 attempt/session의 동일 기록만 재생할 수 있다. 다른 보고서로 자동 교체하지 않는다.

GET은 고정 참조의 경로·크기·raw SHA와 선택 행의 scope·typed post ID·원래 판정 지문을 확인한다. 대시보드의 `BOUND`는 `FILE_AND_BASE_BINDING_ONLY`이며 HMAC·원장 재생 검산이 아니다. `VERIFIED_LOCAL_CONTRACT`는 저장 reader가 남긴 결과로 구분한다. 미연결·손상·다른 행의 `NO_PLAN_PROVIDED`와 합성 완료를 별도 표시한다. 전체 행 조회에서는 파일을 한 번 읽고 행별 결속만 대조한다.

실제 provider용 `recovery_transport.py`는 명시 예약 회신 이후 재검사하고 HTTP 요청을 한 번만 보낸다. retry·redirect·환경 proxy는 끄고 응답 크기·누적 호출·시간을 관측한다. timeout이나 로컬 close는 원격 취소 확인이 아니다. 이 모듈의 성공은 HTTP JSON 수신 완료이며 실제 복구 성공이 아니다. 이전 단계에서는 provenance·durable 원장·재시작 복원이 미연결이었다. 당시 명시 provider 경로 다음에는 native 공개 guard와 정규 자동 복구가 남아 있었다. 현재 native 연결과 남은 범위는 위 최신 기록을 따른다.

## 연결 변경의 검증 근거

Python13파일 382개·하위45개 통과, Node37개 통과다. 이전 코어405개와 합산하지 않는다. [통합 회귀 수령증](../../out/development_plan_20261010/r6_integration_final_receipt.json), [브라우저 기록](../../out/development_plan_20261010/r6_integration_browser_receipt.json), [main 프로세스 합성 실행](../../out/development_plan_20261010/r6_entrypoint_smoke_v1_KO.md)을 기준으로 한다. 브라우저는 live/history에서 같은 보고서와 원래 검토·계획·AUDIT 필드가 보이는 것을 확인했다. main 프로세스는 합성 dispatch 1회·저장·판독·history 결속을 완료했고 모델·검색 호출은 0회다.

첫 통합 회귀는 353 통과·29 실패였다. 제품 변경 없이 검증 스크립트가 Windows asyncio의 내부 socketpair까지 막은 원인을 수정했다. 후속 실행은 stdlib의 정확한 자체 연결만 구분하고 외부 연결 차단을 유지했다. [첫 로그](../../out/development_plan_20261010/r6_integration_initial_tests.log)는 보존한다. 최초 브라우저 합성 fixture는 수령증의 판정 지문 불일치로 거절됐고, v2에서 수령증을 다시 생성해 통과했다. 이를 실제 결과의 수리나 모델 품질 증거로 사용하지 않는다.

독립 검토에서 manifest 배열/null을 API 500으로 보내는 경우를 찾아 객체 검사와 반례로 수정했다. [API 후속 검토](../../out/development_plan_20261010/r6_recovery_view_repair_review_receipt.json), [진입점 검토](../../out/development_plan_20261010/r6_simulation_workflow_independent_review_KO.md), [전송 계층 검토](../../out/development_plan_20261010/r6_transport_independent_review_KO.md)는 정적 검토이며 실행 시험과 구분한다.

## 개발 범위와 기존 동작

기존 `REVIEW_ONLY`, `PLAN_ONLY`, `AUDIT_ONLY`는 각각 검토·계획·감사 기록의 의미를 유지한다. 복구 실행 기록은 새 원장에 저장하고 원본 result·manifest·WAL·중앙 DB를 변경하지 않는다. `expert_main`의 기존 OFF와 fresh measurement의 감사 쓰기 생략 동작도 유지한다.

첫 개발 단위는 `LOCAL_SIMULATION_ONLY`와 `SYNTHETIC_CONTRACT_ONLY`로 표시한 고정 fixture 실행이다. 외부 호출 예산은 0이며 공개 적용과 중앙 DB 쓰기는 허용하지 않는다. 실제 provider 연결, 대상 표본, 참조 라벨, 측정 예산과 품질 수용 기준은 후속 구현·평가 항목으로 남아 있다. R7 production 전환은 기존 보류 상태를 유지한다.

## 원본과 제안의 연결

공개 결과 전체의 publication commit, router receipt, semantic plan, 원래 OCR proposal을 같은 scope·입력 순서·post ID 타입·base attempt·decision에 결속한다. 파일의 원시 SHA, OCR catalog 항목의 canonical JSON SHA, 원문 field와 span을 구분한다. 과거 제안의 누락된 source SHA를 현재 파일 값으로 채우지 않는다.

semantic query plan에는 검색 목적과 상한만 있다. 실제 query는 명시 원문과 연결하며 목적 이름으로 임의 생성하지 않는다. 역할 미상·미결속 근거와 기존 공개 완료 결과는 새 실행 가능 상태로 바꾸지 않는다. `아생갤` 같은 표면은 실제 작품 약칭이나 작품 안 커뮤니티 서사일 수 있으므로 기존 작품·역할·경쟁 근거를 그대로 보존한다.

JSONL의 별도 댓글과 내장 댓글은 기존 로더의 순서·내용 투영을 그대로 따르며 원래 결과의 `comments`와 비교한다. 부모 ID의 타입, 중복 댓글 ID와 댓글 순서도 검산한다. 원본 파일의 SHA를 다시 계산해 맞춘 경우에도 댓글을 누락하거나 다른 부모로 옮긴 모순은 허용하지 않는다. 역할은 `primary`, `previous`, `mentioned`, `comparison`, `candidate`, `ambiguous`만 인정하고 해당 역할을 그대로 유지한다.

## 실행과 기록의 수용 기준

- 원본 감사 원장은 읽기 전용으로 검산하며 registry 생성자의 꼬리 수리를 호출하지 않는다.
- 각 호출은 예산과 취소 상태를 확인한 뒤 먼저 실행 원장에 예약한다. 저장 실패 시 호출하지 않는다.
- 실패·취소·재시도도 누적 예산에 포함한다. 새 attempt를 발급해 예산을 초기화하지 않는다.
- 완료된 attempt 재생은 호출 0회다. 예약만 남은 중단은 미확정으로 남기고 자동 재호출하지 않는다.
- 완료 판정 전에 출력 저장·재판독과 명시 보호 파일의 원시 SHA를 다시 확인한다.
- 시도 종결 후보의 저장·재판독 이후 시간을 별도 최종화 기록에 결속한다. 최종화 기록이 없으면 완료로 재생하거나 새 시도로 자동 재호출하지 않는다. 시간 관측 범위는 `THROUGH_ATTEMPT_TERMINAL_DURABLE_READBACK`이며 마지막 관측 기록 자체의 저장은 보고서 I/O로 구분한다.
- 입력·base·attempt 분모, 합성 호출과 실제 호출을 분리한다. 실제 비용·품질·formal KPI는 측정 조건 충족 전 `NOT_ESTIMABLE`이다.

## 진행 체크

첫 15파일 묶음 시험은 112 실패·274 통과·14 setup 오류·101 하위 시험 통과다. 신규 fixture의 적격 상태 결속과 기존 하네스의 참조 지문 불일치 때문에 **REVIEW_REQUIRED**로 남겼다. [원본 실행 수령증](../../out/development_plan_20261010/r6_initial_validation_receipt.json)과 [실패 로그](../../out/development_plan_20261010/r6_initial_validation_tests.log)를 보존한다. 실행 중 지정 소스 변경과 socket 연결 시도는 없었고 시작·종료 저부하 자원 조건을 유지했다.

- [x] [준비 계약](../../out/development_plan_20261010/r6_implementation_contract_KO.md)과 [보충 검토](../../out/development_plan_20261010/r6_contract_review_addendum_KO.md)를 확인했다.
- [x] 기존 문서·체크리스트·상태 10개 파일을 [개발 전 백업](../../out/development_plan_20261010/r6_backup/root_files_receipt.json)에 보존했다. R5 소스·시험 지문도 대조했다.
- [x] 계획과 근거 연결, 별도 실행 원장, 제한 합성 실행기, 독립 재판독을 구현했다.
- [x] 정상·오류·취소·예산·재시도·중단·동시 예약·원본 비간섭을 저부하 조건에서 검증했다.
- [x] 독립 소스 검토에서 원문 결속·예약·취소·최종화·판독 지적의 수리를 확인했다. 정적 검토와 실제 시험의 근거는 구분한다.
- [ ] 실제 provider·데이터·수용 기준을 확정하고 실행·품질을 평가한다.

현재 독립 판독 CLI는 이미 존재하는 감사 키의 hex 형식을 읽으며 키를 생성하거나 권한을 변경하지 않는다. 모든 호출 결과를 고정 fixture와 비교하므로 영구 실패를 일시 실패로 바꾸고 원장 해시를 다시 맞춘 기록도 거절한다. 현재 명시 합성 진입점과 R6 웹 표시는 연결했다. 실제 자동 복구와 provider 전체 연결은 별도 미완료 항목으로 유지한다.

P4 실제80은 사용자 승인 후 자동 승인 검토가 두 차례 `blocked by policy`로 차단했으며 재시도하지 않았다. 현재 모델 실행은 0회다. [전체 개발 계획](EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md)과 [TODO](TODO.md)·[CHECKLIST](CHECKLIST.md)의 미완료 상태를 함께 유지한다.

## 이전 코어 전달의 실행 근거

Python 15파일의 405개 시험·179개 하위 시험을 저부하 조건에서 통과했다. [실행 수령증](../../out/development_plan_20261010/r6_final_validation_receipt.json)과 [원본 로그](../../out/development_plan_20261010/r6_final_validation_tests.log)를 기준으로 한다. 처음 실패한 실행은 과거 기록으로 보존하며 후속 통과 수치와 합산하지 않는다. 기존 하네스의 이동 전 경로는 현재 위치로 수정했고, 부모 자료 시험은 원래 검산기를 사용하는 임시 합성 그래프로 옮겼다. 과거 ledger의 줄 끝이나 역사 RunSpec을 다시 쓰지 않았다.

앞서 수행한 신규 4파일 검증은 201개 시험·78개 하위 시험 통과이며 최종 15파일 검증에 포함된 범위다. 두 실행 수치를 합산하지 않는다. 각 실행의 임시 폴더 정리 경고 1건은 원본 로그에 보존했다. 검증 중 지정 소스 변경과 socket 연결 시도는 0회였고 시작·종료 시 BelowNormal, CPU affinity 2(논리 CPU 1개), 수치 연산 스레드 5종 모두 1을 확인했다.

| 구성 | 구현과 근거 |
|---|---|
| 계획·원문 결속 | [recovery_execution_contract.py](../../src/llm_batch/measurement/recovery_execution_contract.py), [후속 독립 검토](../../out/development_plan_20261010/r6_contract_verified_review_KO.md) |
| 별도 원장·제한 실행 | [recovery_execution_journal.py](../../src/llm_batch/ledger/recovery_execution_journal.py), [bounded_recovery.py](../../src/llm_batch/runtime/bounded_recovery.py), [독립 검토](../../out/development_plan_20261010/r6_execution_verified_review_KO.md) |
| 독립 판독·새 보고서 CLI | [recovery_execution_readback.py](../../src/llm_batch/measurement/recovery_execution_readback.py), [run_recovery_execution_readback.py](../../tools/run_recovery_execution_readback.py), [독립 검토](../../out/development_plan_20261010/r6_readback_final_review_KO.md) |
| 기존 하네스 경로·합성 자료 수리 | [수리 기록](../../out/development_plan_20261010/r6_legacy_harness_followup_KO.md), [독립 검토](../../out/development_plan_20261010/r6_legacy_harness_final_review_KO.md) |

적용 파일과 원본 보존 검산은 [최종 전달 수령증](../../out/development_plan_20261010/R6_DELIVERY_RECEIPT.json)과 [보존 수령증](../../out/development_plan_20261010/r6_preservation_receipt.json)에서 확인한다. 원본 233b, 기본 폴더의 기존 연구 변경, 원본80/32 자료와 DB를 별도 범위로 대조한다.

이전 코어 전달에서는 웹 제품을 바꾸지 않아 Node·브라우저 시험을 반복하지 않았다. 이번 연결 변경의 새 시험은 위 별도 근거를 따른다. R5 화면 검증은 그 당시 소스의 별도 기록이며 R6 웹 표시를 검증한 것으로 해석하지 않는다. 실제 호출·학습·복구 품질·비용은 미측정이며 formal KPI는 NOT_ESTIMABLE이다.
