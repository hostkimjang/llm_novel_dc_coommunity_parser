# Expert 대시보드 디자인과 운영

> 현재 상태는 [현재 상태 문서](CURRENT_STATUS_KO.md)를 따른다. 날짜별 기록과 `out/`·`logs/` 링크는 로컬 보존 자료이며 Git checkout에 포함되지 않을 수 있다.

## 2026-10-10 최신 진행: 전체 진입점과 완료 표시

80건 검토 자료 준비를 유지하면서 일반 `expert_main` 전체 진입점의 합성 입력 OFF·재생 ON·최초 분석 ON을 검증했다. 최초 ON은 provider1회·native7회를 거쳐 원래 HOLD와 별도 결과를 보존했다. 대시보드의 완료 상태·부분집합·실패·저장 대기와 이력 건수 표시를 수리했다.

관련 Python 3파일은 **71 passed, 40 subtests passed in 10.17s**, **Node 84개 통과·실패 0개·skip 0개**다. 일반 CLI 검증과 이후 UI/API 변경의 시험 범위를 분리한다. [현재 검증·남은 개발](EXPERT_ENTRY_COMPLETION_REVIEW_20261010_KO.md)을 따른다. 아래 수치와 당시 미완료 설명은 이전 단계 기록이다.

후속으로 semantic NIL/CAL→actual readback·baseline 연결을 구현하고 합성 로컬 검증을 마쳤다. **271 passed, 9 subtests passed in 167.12s (0:02:47)**이며 [R4 연결 검증](R4_ACTUAL_BRIDGE_20261010_KO.md)에 범위와 한계를 기록했다. 적격 실제 자료의 전체 성공 경로, 실제80·새 브라우저·사람 판정·실자료 품질·R5 실측은 미완료다. Goal active·formal KPI NOT_ESTIMABLE·R7 보류를 유지한다.

## 이전 검증: 기존 회귀 수리와 80건 검토 준비

기존 rework 실패 33개는 이름 변경 대응표와 실제 JUnit을 대조해 모두 통과했다. 마지막 3개 파일 실행은 **494 passed, 55 subtests passed in 181.10s (0:03:01)**다. 앞선 9개 파일 실행의 **5 failed, 578 passed, 64 subtests passed in 572.95s (0:09:32)**에서 시험 의존 파일 누락 4건과 최종 후보 단계의 기대 불일치 1건을 확인하고 보완했다. 제품 소스는 두 실행 사이에 그대로이며, 앞선 나머지 6개 파일의 통과를 따로 보존한다. 서로 다른 실행 수치를 합산하지 않으며 전체 저장소 회귀나 전체 CLI 검증 완료로 해석하지 않는다. [현재 수리 기록](LEGACY_REWORK_REPAIR_20261010_KO.md)과 최종 실행 검산 (`out/development_plan_20261010/r6_rework_phase4_reconciled.json`, 로컬 증거)을 따른다.

원형 본문에 결속된 별칭은 비권한 후보로 보존하고, 일반 화자 발화는 명시적인 작성자 복귀 전까지 보류한다. URL·시각 예외, OCR 작가 검색, 추천 보류와 최종 설명 봉인을 검증했다. 후보 제목·URL 보존과 최종 공개 title/URL을 따로 확인하며, 검색 후보만으로 공개 권한을 만들지 않는다.

80건 검토 자료 (`out/development_plan_20261010/actual80_review_queue_v1/review_guide.md`, 로컬 증거)는 원문·저장 관측 112개와 참조를 연결했고 독립 재판독 (`out/development_plan_20261010/r6_rework_actual80_preparation_readback_v1_KO.md`, 로컬 증거)에서 원문·참조 52개 파일의 존재와 SHA 일치를 확인했다. 사람 정답 0건·학습 준비 0건·전 행 개발 노출·권한 UNKNOWN이며 후보 누락 3행, 미검토 이미지 25개는 남아 있다.

현재 상태는 **REWORK_LOCAL_VERIFIED_ACTUAL_PENDING**이다. 아래 자동 복구 수치와 33개 실패·NOT_PASS 표기는 이전 단계 이력이다. 실제80 모델 실행·새 브라우저는 자동 승인 검토의 `blocked by policy` 거절 이후 재시도하지 않았다. 실제 품질·사람 판정·적격 분할 자료·R5 실측·formal KPI는 미완료이며 formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다.

## 이전 자동 연결 단계: 일반 main 자동 복구의 로컬 검증 (2026-10-10)

일반 `expert_main`의 같은 호출 문맥을 원래 guard·commit·AUDIT·최종 저장 이후 제한된 복구로 연결하고, 별도 결과를 대시보드 live/history API와 표시까지 로컬 검증했다. 기본값은 OFF이며 ON에는 고정 정책·예산과 대시보드가 필요하다. 원래 결과·manifest·WAL은 보존하며 공개 적용·권한·중앙 DB 쓰기는 false다.

현재 상태는 **AUTOMATIC_NATIVE_LOCAL_VERIFIED_ACTUAL_AND_LEGACY_REWORK_PENDING**이다. [운영 계약](NATIVE_RECOVERY_AUTOMATION_20261010_KO.md)과 실행별 검증·수리 기록 (`out/development_plan_20261010/r6_auto_reconciled_receipt.json`, 로컬 증거)을 따른다. 검증은 합성 HTTP 응답으로 실제 전문가·guard·AST로 추출한 실제 main 함수 본문·원장·API·Node 표시를 통과한 범위다. 전체 CLI 기동과 실제 브라우저 통과를 뜻하지 않는다. 실행별 시험 수는 합산하지 않으며 마지막 수리 뒤 최초 전체 파일을 모두 다시 실행한 결과도 아니다.

최종 HOLD의 OCR 근거 누락은 새 `strict_evidence_v2` 검토 규칙으로 수리했고 기존 v1 영수증 판독은 보존했다. 실제80 모델 실행·새 브라우저·사람 정답·적격 실제 TRAIN/CAL/FROZEN 품질·R5 실측과 기존 rework 33개 실패는 남아 있다. 전체 회귀는 NOT_PASS, formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다. 아래 단계별 수치와 미완료 설명은 당시 이력이며 현재 범위는 이 절을 따른다.

## 이전 단계: 명시 native 복구 연결과 당시 남은 자동화

R6의 **명시 same-call native 복구 연결을 합성 응답·HTTP mock으로 로컬 검증했다**. 현재 검증 상태는 `PASS_NATIVE_EXISTING_REWORK_FAILURES_PENDING`이며 기존 rework 시험 실패는 미해결이다. `run_native_recovery`는 같은 분석 호출에서 보존한 pre-final 문맥을 원래 입력·저장 provider 근거에 결속하고, 실제 Decoder·Verifier·Synthesizer·Arbiter와 기존 native 공개 guard를 호출한다. 원래 결과·manifest·WAL을 덮어쓰지 않고 별도 scope의 새 publication WAL과 결과를 저장·재판독한다. guard 판정 기록은 공개 반영이 아니며 `public_apply`, `publication_authority`, `central_db_write`는 false다.

native 추가 LLM·검색·fetch는 하나의 영속 호출·byte·시간 예산을 공유하며 먼저 예약하고 전송한다. 완료 job만 저장 결과를 0회 호출로 재생하고, 미완료·불확실 요청은 재시작 후 재발송하지 않는다. upstream provider 수집은 별도 앞 단계로 합계에 표시하며, MCP 내부 원격 검색 횟수·취소·가격은 확정하지 않는다. 과거 actual80/32 저장 JSON을 살아 있는 native 문맥으로 복원하는 기능은 없다.

최초 Python 16개 파일의 원시 결과는 시험 893개 통과·32개 실패와 하위 시험 21개 통과다 (`32 failed, 893 passed, 21 subtests passed in 1228.60s (0:20:28)`, 최초 전체 수령증 (`out/development_plan_20261010/r6_native_final_receipt.json`, 로컬 증거)). 합성 응답 fixture만 보정한 뒤 workflow 1개 파일의 시험 7개가 통과하고 실패는 1개, 하위 시험은 0개다 (`1 failed, 7 passed in 657.84s (0:10:57)`, 보정 후 수령증 (`out/development_plan_20261010/r6_native_repair_receipt.json`, 로컬 증거)). 그 뒤 실제 fetch 응답의 identity 캐시를 복제하는 제품 코드를 수리하고 context·workflow 2개 파일을 재검증해 시험 67개와 하위 시험 0개가 통과했고 실패는 0개다 (`67 passed in 701.00s (0:11:41)`, 캐시 수리 후 수령증 (`out/development_plan_20261010/r6_native_capture_final_receipt.json`, 로컬 증거)). **세 실행의 시험은 겹치므로 합산하지 않는다. 마지막 수리 뒤 전체 16파일을 다시 실행한 결과도 아니다.** 재조정 수령증 (`out/development_plan_20261010/r6_native_reconciled_receipt.json`, 로컬 증거)은 새 native 경로의 실패가 수리됐음을 기록하며 최초 전체 실행을 PASS로 바꾸지 않는다.

기존 rework 시험은 전체 실행에서 31개가 실패했다. 동일한 빈 캐시·단일 파일 격리 조건의 이전 baseline과 현재 소스에서는 각각 33개 실패가 재현됐고, 33개의 예외 종류·정규화 메시지가 같았다. 비교상 남은 차이는 0개지만 시험 상태는 `FAILED`다 (격리 비교 근거 (`out/development_plan_20261010/r6_native_isolated_rework_comparison_v1.json`, 로컬 증거)). **실패 33건은 해결되지 않았으며 전체 회귀 통과나 모든 OFF 동작의 동등성을 뜻하지 않는다.** API·검증 범위 (`out/development_plan_20261010/r6_native_api_KO.md`, 로컬 증거), 현재 코드·캐시 수리 독립 검토 (`out/development_plan_20261010/r6_native_capture_cache_review.json`, 로컬 증거)와 I/O 독립 검토 (`out/development_plan_20261010/r6_native_io_closure_review.json`, 로컬 증거)를 따른다. fixture 수정 독립 검토 (`out/development_plan_20261010/r6_native_fixture_repair_review.json`, 로컬 증거)는 앞선 수리 이력으로 보존한다. 이번에는 Node·브라우저 시험을 실행하지 않았다. 화면 소스는 이전 provider 단계의 Node 66개 통과 기록 (`out/development_plan_20261010/r6_provider_node_receipt.json`, 로컬 증거)과 같으며, 그 기록은 새 native 화면이나 브라우저 통과 증거가 아니다. 이전 probe 실패와 simulation/provider 시험도 별도 이력으로 보존한다.

80건 검토 큐 (`out/development_plan_20261010/actual80_review_queue_v1/review_guide.md`, 로컬 증거)는 그대로 보존했다. 입력 80행·저장 관측 112개·중복 게시물 32개이며, 사람 정답과 학습 준비는 모두 0건이다. 기존 WORK/NIL 참조를 사람 정답으로 승격하거나 새 독립 분모로 세지 않았다.

**일반 main의 자동 복구 스케줄과 native 결과의 대시보드 live/history 연결은 아직 미완료다.** 실제 외부 모델·검색 호출은 0회이며 실제 복구 품질·비용·formal KPI는 `NOT_ESTIMABLE`이다. P4 실제80 실행과 새 Chrome 검증은 기존 자동정책 차단을 재시도하지 않았다. 실제 자료·사람 판정·R4 학습/교정 품질·R5 실측도 남아 있다. R6 전체 완료로 처리하지 않으며 Goal은 active, R7은 보류다.

## 이전 단계: provider 근거 수집과 80건 검토 준비 (2026-10-10)

당시 R6 상태는 **PROVIDER_EVIDENCE_LOCAL_VERIFIED_NATIVE_GUARD_AND_ACTUAL_RECOVERY_PENDING**였다. 원본 HOLD·AUDIT에 결속한 명시 계획 → 영속 예약 → 단일 HTTP → 원시 응답 저장·독립 판독 → `expert_main`·대시보드 연결을 구현했다. 완료된 요청은 0회 전송으로 재생하고, 완료 여부가 불명확한 요청은 재발송하지 않는다. 최초 fresh source 검사부터 응답 저장·재판독까지 같은 시간 제한을 적용한다. 마지막 `REQUEST_FINALIZED` 자체의 저장은 이 시간 범위에서 제외한다. 저장 성공은 `PROVIDER_EVIDENCE_STORED`, 공개 guard는 `GUARD_NOT_EVALUATED`이며 일반 실행의 자동 복구는 아직 연결하지 않았다.

이전 provider 단계의 변경 영향 Python 23파일 `779 passed, 163 subtests passed in 654.67s (0:10:54)`, Node 66개 PASS다. 실제 파일 원장과 HTTP mock, 저장 결과의 API·Node 표시를 확인했다. 실제 외부 모델·검색 호출과 새 브라우저 검증은 0회다. 실행 계약·한계 (`out/development_plan_20261010/r6_provider_api_KO.md`, 로컬 증거), Python 검증 (`out/development_plan_20261010/r6_provider_final_receipt.json`, 로컬 증거), Node 검증 (`out/development_plan_20261010/r6_provider_node_receipt.json`, 로컬 증거)을 따른다. 아래 이전 단계의 수치는 당시 증거이며 이번 수치와 합산하지 않는다.

80건 검토 큐 (`out/development_plan_20261010/actual80_review_queue_v1/review_guide.md`, 로컬 증거)를 준비했다. 원래 입력 순서 80행에 112관측·관측별 후보 기록 121개를 연결했고 중복 게시물 32개를 별도 표본으로 세지 않았다. WORK 2·NIL 6은 기존 모델 참조, UNJUDGED는 72건이다. 사람 정답·학습 준비는 모두 0건이며 전 행이 개발에 노출됐다. 후보 결손 3행과 미검토 이미지 21행을 검토 순서에 반영했지만 정답·역할·사용 권리를 채우지 않았다. 검산 수령증 (`out/development_plan_20261010/actual80_review_queue_v1/verification_receipt.json`, 로컬 증거)에 원본 46개·이전 준비 파일 5개의 보존 근거를 남겼다.

당시 남은 범위는 P4 실제80·새 브라우저, 실제 corpus·사람 판정·TRAIN/CAL/FROZEN 품질, R5 실측, R6 native 공개 guard·자동 복구·실제 품질이었다. 현재 native 연결과 미완료 범위는 위 최신 기록을 따른다. 당시 R6 후속 계획은 native guard 개발 메모 (`out/development_plan_20261010/r6_native_guard_next_steps_KO.md`, 로컬 증거)를 따른다. 기존 자동 승인 차단을 재시도하지 않았으며 formal KPI는 `NOT_ESTIMABLE`, Goal은 active, R7은 보류다.

NIL 학습·저장·화면 표시와 CAL 온도 학습·FROZEN 소비의 최신 상태는 [R4 운영 기록](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)을 따른다. 명시적 FROZEN 재관측 교정·capture 저장·화면 표시를 연결했다. 의미 역할·검증 자료의 별칭 관측과 저장·화면 표시를 추가했다. 새 의미 관측을 버전별 학습·모델·CAL에 연결하고 합성 로컬 회귀로 검증했다. 일반 R2 graph 자동 공급과 새 입력의 고정 교정 추론을 로컬 검증했다. 실제 자료 품질 평가와 새 소비 화면의 브라우저 확인은 남아 있다. 이전 단계 시험 수는 합산하지 않는다.

[R6 제한 복구 실행](BOUNDED_RECOVERY_EXECUTION_20261010_KO.md): 당시 상태 **LOCAL_ENTRYPOINT_UI_VERIFIED_ACTUAL_RECOVERY_PENDING**. 별도 `expert_main` 합성 복구 진입점과 검토·계획·AUDIT·복구 보고서의 API·live/history 표시를 연결했다. 변경 영향 Python 13파일의 382개 시험·45개 하위 시험과 Node 37개, 실제 브라우저 및 별도 main 프로세스 합성 검증을 통과했다. 실제 모델·검색 호출은 0회다. 실제 provider 전체 연결·자동 복구·품질 평가는 남았으며 앱 Goal은 active다.

## 2026-10-10 고정 후보 재정렬 SHADOW 표시

`run_meta.candidate_reranker_shadow`를 live/history 상세에서 표시한다. 합성 점수 상태, backend·자료 종류, 원문/후보/생성/scorer 지문, 고정 후보 ID와 점수, 미교정 확률·NIL 미판정, 원문별 역할 관측, 행 결속을 저장된 값으로 보여준다. 실행 정책은 `candidate_reranker_policy`에 있다. 큰 receipt는 목록/SSE에 넣지 않으며 과거 미저장 값을 추론하지 않는다.

현재 backend는 v1 SYNTHETIC_FIXED_SCORES_V1, v2 PAIRWISE_LINEAR_V1, v3 NIL_AUGMENTED_LINEAR_V1이다. v3는 NIL head 유무·원시 NIL 점수·고정 후보 순서의 event_logits와 마지막 __NIL__·기저 모델 SHA를 표시한다. 미교정 점수 안내를 함께 표시하고 nil_probability와 최종 선택은 null로 둔다. 미점수 상태에서는 nil_score=null, event_logits=[]를 유지한다. SCORED_LEARNED는 학습된 선형 파라미터로 점수화했다는 뜻이다. 자료 종류·모델 SHA·품질 미검증을 함께 표시하며 실제 성능 완료로 해석하지 않는다. SCORED_SYNTHETIC은 계약 시험 결과이고 학습 모델의 성공이 아니다. NOT_SCORED_GENERATION_TRUNCATED·빈 순위·ERROR/UNAVAILABLE·NOT_AVAILABLE_UNCALIBRATED를 구분한다. scope 미기록과 미결속 값은 PARTIAL로 유지하며 후보 회수 실패를 NIL로 표시하지 않는다. 기본 OFF는 새 관측을 만들지 않고, source-only 조기 경로에는 이전 행 receipt를 복사하지 않고 PIPELINE_NOT_EXECUTED를 저장한다.

초기 v1 통합 검증은 Python44파일916개 시험·139개 하위 시험, Node 표시/테마25개 PASS다. 합성v3 실제 브라우저의 live/history 점수 결과와 TRUNCATED·빈 순위를 확인했고 콘솔 경고·오류0, 1280px 뷰포트에서 가로 넘침이 없었다. 화면 수령증 (`out/development_plan_20261010/r4_browser_receipt.json`, 로컬 증거), live 화면 (`out/development_plan_20261010/r4_browser_final_live.png`, 로컬 증거), 부분 후보 화면 (`out/development_plan_20261010/r4_browser_final_history_partial.png`, 로컬 증거)을 따른다. [R4 운영 문서](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)의 LOCAL_CONTRACTS_VERIFIED_MODEL_AND_ACTUAL_DATA_PENDING 당시 상태다. 현재 학습 baseline의 기능 검증은 R4 운영 문서 상단을 따르며 실제 자료의 품질 평가는 남아 있다.

## 2026-10-10 커뮤니티 지식 READ_ONLY 표시

`run_meta.community_knowledge_readback`이 있는 새 결과의 live/history 상세에 조회·소비 상태, snapshot/query SHA, 원문 위치, 경쟁 sense·정의·커뮤니티·유효기간·검토·별칭/일반어 분류·출처·행 결속을 표시한다. 공개 권한과 중앙 DB 쓰기는 false다. QUERY_ONLY와 실제 prompt 포함을 구분하며 후보 없음은 NIL로 표시하지 않는다. 큰 진단은 목록/SSE에 넣지 않는다.

R3 완료 당시 Python 37개 파일의 시험 726개와 하위 시험 132개, 화면 표시 시험 24개, 합성 builder 산출물의 실제 브라우저 live/history·콘솔0을 확인했다. [R3 운영 문서](COMMUNITY_KNOWLEDGE_READ_ONLY_20261010_KO.md)에 실제 Decoder 모의시험과 화면 QUERY_ONLY의 차이, 실제 품질 미평가를 기록했다. 자산 버전을 갱신해 이전 JavaScript 캐시를 구분한다.

## 2026-10-10 후보 회수 SHADOW 표시

`--candidate-retrieval SHADOW`로 저장한 새 관측은 live/history 상세의 `작품 후보 회수 · SHADOW`에 표시한다. corpus/query 지문, 자료 종류와 출처 검증 여부, 후보 ID·점수·작품·판본·매체·출처, 실행·행 결속을 확인할 수 있다. 빈 결과는 NIL 판정으로 표현하지 않으며 공개 권한 false를 표시한다. 기본 OFF와 과거 미저장 자료에는 이 구역을 만들지 않는다. 큰 관측은 목록/SSE에 보내지 않는다.

R2 완료 시점의 통합 회귀는 Python608개＋subtests122개·표시23개 PASS다. 합성 adapter 결과를 live/history에서 확인했고 콘솔0이었다. 실제 source-backed corpus의 성능은 아직 미평가다. [운영·검증 문서](CANDIDATE_RETRIEVAL_SHADOW_20261010_KO.md)와 [최신 구현 기록](EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md)을 따른다. 아래 P2/P3 수치는 해당 완료 시점의 기록이다.

## 2026-10-10 실행 이력·관측·설정 표시

기본 폴더에 최신 실행 코드와 대시보드 후속 기능을 통합했다. 상세창은 판정 사유와 분석 메모를 따로 표시하고 NSFW true·false·미기록·형식 오류를 구별한다. 중첩 manifest 실행은 실행 키로 선택하며 같은 실행의 상세와 로그를 유지한다. 부분 저장·최종 저장·완료 미확인, 명시 모드와 미기록 상태를 구분한다.

호출·측정 구역은 행 저장 당시 ledger와 실행 종료 manifest를 각각 보여준다. 관측 토큰을 formal KPI로 바꾸지 않으며 `NOT_ESTIMABLE`·null·`UNBOUND_PARTIAL`을 보존한다. 실행 유효 설정은 CLI/환경/프로필 출처, 코드 지문, VLM/OCR·장부·병렬도·대시보드·프로세스 자원·압축 상태를 표시한다. `source_context_diagnostics_v1`이 저장된 새 결과에서는 발화자·행위자·대상·관계·원문 근거와 graph를 펼쳐볼 수 있다. 과거 실행은 진단 미저장을 안내한다.

목록 탐색은 항목50,000개·manifest2,000개·깊이12 상한과30초 캐시를 사용한다. 탐색 상한에 걸리면 일부 이력 생략 안내를 확인한다. 명시적으로 선택한 결과는128MiB까지 읽으며 제한을 넘거나 손상된 결과를 다른 최신 결과로 대체하지 않는다. API는 허용된 out 경로 밖을 열지 않는다.

최근 저부하 검증 실행은 다음 옵션을 사용한다. 일반 검증의 parallel16 정책과 구분되는 사용자 예외다.

```powershell
python expert_main.py --execution-profile low-load-validation --parallel 1 --input <고정입력.jsonl> --output <새결과.json>
```

저부하 프로필은 VLM/OCR ON·장부 SHADOW·문맥 진단 ON을 기본으로 선택하고 실제 Python 프로세스의 BelowNormal·단일 CPU·numeric threads1을 검사한다. 개별 CLI와 환경변수가 프로필보다 우선하므로 시작 로그·manifest의 유효값을 확인한다. `--no-dashboard`는 검증런에 사용하지 않는다. 일반 실행의 VLM OFF·장부 OFF 기본은 유지한다. paired 프로필만 선택해 정식 비교 측정 조건이 충족되는 것은 아니다.

최종 선택 회귀는 Python468개＋subtests84개·표시22개 PASS다. 원본32와 합성 producer 결과의 live/history, notes·NSFW false·R08 시점 구분·새 설정·구조화 진단을 실제 브라우저에서 확인했고 콘솔 오류·경고는0이었다. 이 화면 검증은 새 모델 실측이나 의미 품질 완료를 뜻하지 않는다. [구현·검증 기록](EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md)에 수령증과 남은 P4 검증을 연결했다. 변경 적용에는 대시보드 서버 재시작과 페이지 새로고침이 필요하다.

## 2026-09-22 판정 사유와 로그 표시 개선

현재 결과 형식에 맞춰 상세 화면과 로그를 정리했다. 판정 결과 다음에 사유가 나오고, 판정 범위·확정 상태·후보 검토·검색 상태·근거 자료·분석 상세가 이어진다. 원본 게시글과 댓글은 별도로 펼쳐본다. 이전의 화이트·다크 테마와 탐색 메뉴는 그대로 사용한다.

판정 사유는 한 줄로 합쳐진 기록과 여러 줄 기록을 모두 구역별 카드로 나눈다. `전문가별 판단`, `미확정 사유`, `후보 제목`, `범위 분리`, `LLM 검토`를 포함하며, 처음 보는 독립 구역 제목도 버리지 않는다. `[이미지 OCR]`, `[E001]` 같은 본문 표시는 유지한다. 긴 구역만 접고, `판정 사유 원문 보기`에서 저장된 문장을 그대로 확인한다.

상세 API는 저장 결과의 `identity` 필드 전체를 전달한다. 화면에는 `is_novel_related`, `is_resolved_work_discussion`, `title_resolution_state`, `title_resolution_allowed` 등 현재 판정 범위와 검색·이미지 근거를 표시한다. 후보 기록, 제목 확정 검토, 출력 점검 기록은 `상세 진단 기록`에서 JSON으로 펼친다. 값이 `false`나 `0`이어도 숨기지 않으며, 저장하지 않은 정보는 추정해서 채우지 않는다. 목록과 SSE에는 판정 범위의 작은 필드만 추가하고 대형 진단 기록은 넣지 않는다.

처리 로그는 입력, 이미지·OCR, 전문가 단계, 검색, 완료 결과로 묶는다. LLM·검색·JSON·주의 및 오류·결과 중 한 종류를 고른 뒤 내용 검색을 함께 적용할 수 있다. JSON과 긴 기록은 접어서 표시하며, 완료 로그의 판정 사유도 구역별로 읽는다. `원문 보기`는 줄바꿈과 내용을 보존한다. 정리한 화면은 200개 기록, 원문 화면은 200줄씩 나누며 검색이나 보기 방식이 바뀌면 첫 페이지로 돌아간다. 실시간·실행 이력 로그에도 같은 표시기를 사용한다. 실시간 로그에서 펼친 기록은 새 로그가 도착해도 표시 한도 안에 남아 있는 동안 유지한다.

화면의 항목명과 안내 문구를 한국어로 정리했다. `humanize-korean`의 의미 보존·번역투·이중 피동 점검을 적용했으며, 모델이 생성한 판정 사유, 작품명, 코드, 수치와 원본 로그는 윤문하지 않는다. 윤문 기록은 로컬 `_workspace/2026-09-22-001/final.md`에 남겼다.

### 검증과 적용

| 범위 | 상태 | 확인한 내용 |
| --- | --- | --- |
| 서버·이벤트 | PASS 33/33 | 정적 자산, 최신 identity 보존, 목록의 대형 진단 제외, 기존 API·이벤트 회귀 |
| 화면 표시·테마 | PASS 15/15 | 한 줄/여러 줄/구형 사유, JSON·잘린 로그·큰 정수 보존, 필터·검색·페이지, 스크립트 구문, 두 테마 |
| 실제 저장 결과 | PASS | `expert_result_20260714_231642_061728.json`의 게시글 `11718077`, `11718099`: 확정·미확정 사유와 현재 진단 표시 |
| 브라우저 | PASS | 실제 뷰포트 1422×904, 504×748에서 화이트·다크, 가로 넘침 없음, 2,164줄 로그의 JSON 필터·원문 페이지 전환 |
| UI 게이트 | PASS | Python 구문 검사, 관련 변경의 공백 검사, 실제 페이지에서 오류 없이 표시 |

```powershell
.venv312/Scripts/python.exe -m unittest tests.test_dashboard_standalone tests.test_monitor_event_bus
node --test tests/dashboard_presentation.test.cjs tests/dashboard_theme.test.cjs
.venv312/Scripts/python.exe -m py_compile expert_main.py src/llm_batch/monitor/server.py src/llm_batch/monitor/event_bus.py
```

새 표시기는 `src/llm_batch/monitor/static/presentation.js`, 화면 연결은 `index.html`, 구역별 스타일은 `dashboard.css`에 있다. 새 Tailwind 유틸리티를 추가하지 않아 CSS 재생성은 필요하지 않다. 서버의 상세 응답도 바뀌었으므로 기존 대시보드는 다음 재시작부터 최신 필드를 전달한다. 새로 연 검증 서버는 [8081](http://127.0.0.1:8081)을 사용하며, 화면 자산을 갱신하려면 브라우저를 새로고침한다. 실행 중인 분석을 중단할 필요는 없다.

화면 기록은 로컬 `out/dashboard-sections/`의 `detail-light.png`, `detail-dark-mobile.png`, `log-json-dark.png`에 보관한다. 이번 검증은 저장 결과와 로그를 읽는 UI 검증으로, 새 LLM 분석이나 grounding 테스트런은 실행하지 않았다. 새 grounding 검증런에는 기존 대시보드 ON·요청 `--parallel 12` 정책을 적용한다.

## 2026-09-06 테마 개편 기록

2026-09-06 기준으로 `expert_main` 웹 대시보드를 화이트·다크 두 테마로 개편했다. 서버·기존 기능 테스트 31개와 테마 생명주기 테스트 4개가 통과했고, 실제 브라우저에서 데스크톱·모바일 화면과 주요 동작을 확인했다. 이번 UI 변경의 최종 게이트는 **PASS**다.

## 화면과 테마

사이드바 하단의 장식 문구 영역은 사용자 요청에 따라 제거했다. 사이드바에는 브랜드와 탐색 메뉴만 표시한다.

화이트 모드는 밝은 회색 바탕·흰 패널·청록 강조색을, 다크 모드는 차콜 바탕·민트 강조색을 사용한다. 왼쪽 메뉴에서 실시간 모니터, 과거 실행 이력, Slang DB를 전환한다. 실시간 화면은 진행률, 6개 KPI, 9단계 파이프라인, 병렬 worker, 처리 결과, 로그 순서로 읽는다. 병렬 실행에서는 개별 카드가 단계와 재호출 상태를 표시하고 순차 타임라인은 접는다. 처리 결과와 로그는 각각 전체폭을 사용하고 작은 화면에서는 메뉴와 카드 배치가 모바일 너비에 맞게 바뀐다.

상단 해·달 버튼으로 화이트·다크 모드를 선택한다. 저장된 선택이 없으면 OS의 `prefers-color-scheme` 설정을 따르며, 이 상태에서는 OS 설정 변경도 반영한다. 사용자가 선택한 값은 브라우저 `localStorage`의 `lndc_theme` 키에 `light` 또는 `dark`로 저장한다. 같은 출처로 열린 다른 탭에는 `storage` 이벤트로 선택이 동기화된다. 저장소 사용이 차단되어도 현재 탭의 전환은 가능하지만 선택 보존은 보장되지 않는다.

## 실행과 최초 적용

저장소 루트에서 독립 대시보드를 실행한다.

```powershell
.venv312/Scripts/python.exe tools/dashboard_server.py --port 8081
```

[로컬 대시보드](http://127.0.0.1:8081)를 연다. 기존 실행의 `expert_main` 대시보드는 해당 실행에서 지정한 포트를 사용한다.

이번 변경에는 서버의 `/static` 경로 등록이 포함된다. 변경 전 코드로 실행 중인 서버에는 새 자산 경로가 없으므로 **최초 적용 시 대시보드 서버를 재시작**해야 한다. 재시작 이후 CSS만 수정했을 때는 페이지를 새로고침한다. 이전 스타일이 남으면 강력 새로고침으로 브라우저 캐시를 갱신한다.

이 문서의 독립 서버 실행은 UI 확인용이다. regression-safe grounding 테스트런·검증런은 2026-10-12 사용자 지시에 따라 대시보드를 켜고 요청 `--parallel 12`을 사용하며, manifest의 requested/effective parallel을 함께 확인한다.

## 자산과 재생성

브라우저의 Tailwind CDN 실행을 제거하고 저장소의 정적 자산을 제공한다. 런타임에는 CSS 생성을 위한 Node.js나 CDN 접속이 필요하지 않다. 유틸리티 클래스 변경 시 개발 환경에서 아래 명령으로 Tailwind 3.4.17 결과를 다시 생성한다. 최초 `npx` 실행은 패키지 다운로드가 필요할 수 있다.

```powershell
npx.cmd --yes --package tailwindcss@3.4.17 tailwindcss --config tools/dashboard/tailwind.config.cjs --input tools/dashboard/input.css --output src/llm_batch/monitor/static/utilities.css --minify
```

| 파일 | 역할 |
| --- | --- |
| [`index.html`](../../src/llm_batch/monitor/static/index.html) | 화면 구조와 기존 대시보드 동작 |
| [`dashboard.css`](../../src/llm_batch/monitor/static/dashboard.css) | 배치, 컴포넌트, 두 테마의 의미별 색상과 RGB 변수 |
| [`theme.js`](../../src/llm_batch/monitor/static/theme.js) | 초기 테마, 선택 저장, OS 변경과 탭 동기화 |
| [`presentation.js`](../../src/llm_batch/monitor/static/presentation.js) | 현재 판정 사유·진단 필드·단계별 로그와 JSON 표시 |
| [`utilities.css`](../../src/llm_batch/monitor/static/utilities.css) | 로컬 생성 Tailwind CSS; 직접 편집하지 않는다. |
| [`tailwind.config.cjs`](../../tools/dashboard/tailwind.config.cjs) · [`input.css`](../../tools/dashboard/input.css) | 생성 입력, HTML 스캔 경로, 동적 worker 클래스 safelist |
| [`server.py`](../../src/llm_batch/monitor/server.py) | HTML과 `/static` 자산 제공 |

기본 색상 팔레트는 `--color-COLOR-SHADE` RGB 변수로 연결된다. 기존 유틸리티와 실행 중 생성되는 worker 필터도 `dashboard.css`의 테마 값을 공유한다. 문자열로 조합하는 새 유틸리티를 추가하면 Tailwind 정적 스캔만으로 수집되지 않을 수 있으므로 config의 safelist도 확인한다.

아이콘은 공식 `lucide-static@0.468.0` 패키지의 SVG 원본을 [`static/icons`](../../src/llm_batch/monitor/static/icons)에 포함하고 CSS mask로 사용한다. 배포 시 동봉한 [Lucide 라이선스](../../src/llm_batch/monitor/static/icons/LICENSE)를 유지한다.

## 검증 상태

| 범위 | 상태 | 근거 또는 남은 확인 |
| --- | --- | --- |
| Tailwind 로컬 생성 | 완료 | 위 명령 실행 성공, 생성 CSS에서 slate·blue·purple·lime 색상 변수 확인 |
| SVG 자산 | 완료 | 공식 npm 0.468.0 패키지 원본 10개와 라이선스 복사 |
| 서버·기존 기능 | PASS 31/31 | 정적 자산 응답·MIME·본문, 누락 자산 404, ingest·결과·이벤트 회귀 |
| 테마 생명주기 | PASS 4/4 | OS 초기 설정, 수동 선택·재로딩, 탭 동기화·삭제, 저장소 예외 |
| 브라우저 확인 | PASS | 1440×1000 및 390×844, 두 테마·가로 넘침 없음, 검색+관련성 필터, 모달, 패널 토글, 워커별 실시간 로그, 실행 이력 상세 3행 |
| Slang DB | 빈 상태 확인 | 메뉴·페이지 크기 전환 확인. 로컬 데이터가 0건이어서 데이터가 있는 페이지 이동은 수동 검증하지 않음 |
| UI 변경 최종 게이트 | PASS | 콘솔 오류 0, HTML ID·구문 검사와 `git diff --check` 통과 |

검증 명령:

```powershell
.venv312/Scripts/python.exe -m unittest tests.test_dashboard_standalone tests.test_monitor_event_bus
node --test tests/dashboard_theme.test.cjs
```

브라우저의 병렬 화면은 8081 검증 서버에만 합성 이벤트 16건을 전달하여 완료 7개·진행 중 9개 상태로 확인했다. 실제 LLM 호출은 하지 않았다. 로컬 화면 기록은 `out/dashboard-design/light.png`, `out/dashboard-design/dark.png`이며 Git 추적 대상에서 제외된다. 기존 대시보드와 동일하게 새로고침 후 전체 최근 로그는 복구되지만 워커별 스트림 탭은 이후 들어온 이벤트를 표시한다.

완료 항목은 [개발 체크리스트](CHECKLIST.md)의 `2026-09-06 Expert 대시보드 화이트·다크 개편`에 기록했다. 대시보드 표시나 UI 검증 통과는 분석 결과의 의미 품질 또는 전체 스캔 승인 근거가 아니다.


## R5 저부하 비교 관측 표시

행과 실행 manifest의 START/END를 분리해 실제 PID·우선순위·CPU·수치 스레드·health 시각·시도 ID를 표시한다. 종료 누락은 관측 미완료로 남기며 저장 여부를 검산 PASS로 표현하지 않는다. 원본 JSON도 보존한다. API의 manifest/row allowlist에 두 private 관측 필드를 추가했다. [R5 운영 기록](PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md)에 실행 계약과 한계를 기록했다. 합성 live·완료 history·종료 누락 history 검증은 PASS이며 실제 모델·비용·품질 평가는 별도다.

## 로컬 CAL 교정과 일반 화면의 구분

명시적인 로컬 bundle은 CAL 전체 raw event로 temperature를 학습해 v2 artifact를 저장한다. 이 산출물은 기존 FROZEN SHADOW 소비 API에서만 결속된 확률로 검증했다. 당시 일반 실행은 NIL raw score·미교정 표시만 제공했다. 후속 구현은 raw 기록을 유지하며 별도 FROZEN 재관측 교정 카드와 capture 참조를 추가했다. 새 로컬 CAL 도구가 존재한다는 이유로 runtime receipt의 nil_probability를 채우거나 교정 완료로 표시하지 않는다.

## 명시 FROZEN 재관측 연결 후속

R4 상태는 **GENERAL_INFERENCE_LOCAL_VERIFIED_BROWSER_AND_ACTUAL_DATA_PENDING**다. 일반 입력의 실제 R2 원문·후보 ID·작품/판본·출처 bytes를 고정 semantic NIL 모델 및 CAL 온도에 연결하고 expert_main 저장·API·대시보드 표시를 구현했다. 현재 원문·R2·모델 점수를 재생 검산하며, FROZEN 배정이나 정답을 만들지 않는다. 이번 로컬 회귀는 Python 38파일 `1440 passed, 42 subtests passed in 229.37s (0:03:49)`, Node 58개 PASS다. 실제 pipeline에서 저장한 live/history 자료를 Node 표시 시험으로 연결했다. 실제80 준비 묶음은 112관측/80고유행을 원문과 연결했으나 사람 정답0·학습 준비0이며 전 행이 개발 노출 자료다. 실제 TRAIN/CAL/FROZEN 품질, 새80 모델 실행, 새 화면의 브라우저 검증과 R6 실제 provider 복구는 남았다. 실제 모델 API·검색·source-backed 학습은 0회다. 실제80·Chrome의 자동 승인 검토가 blocked by policy로 차단한 실행은 재시도하지 않았다. formal KPI는 NOT_ESTIMABLE, Goal은 active다.


## 일반 입력 교정의 실행·저장·표시

`--candidate-inference SHADOW --inference-bundle <bundle.json> --inference-bundle-sha256 <raw-SHA>`를 기존 R2·고정 NIL 모델 옵션과 함께 사용한다. 기본 OFF이며 v2 의미 모델에는 의미 관측 SHADOW도 필요하다. 새 bundle은 명시된 source raw bytes·corpus·기존 CAL artifact를 묶으며 새 학습을 수행하지 않는다. 온도 수치 재생 검산과 새 온도 fit을 구분한다.

성공은 TEMPERATURE_APPLIED_BOUND_INFERENCE, 현재 고정 모델의 수치 검산, 저장 참조 SAVED를 함께 요구한다. 행의 candidate_reranker_inference/candidate_inference_capture와 manifest의 candidate_inference_policy를 보존한다. 화면은 현재 게시글·run/scope·CAL/model/원문 지문까지 대조한다. 후보가 비거나 잘렸거나 저장/검산에 실패하면 확률은 null이다. NIL 제안은 정답이나 공개 판정이 아니며 전체 웹 recall도 주장하지 않는다.

정확한 API·bundle 구성·한계 (`out/development_plan_20261010/r4_general_inference_api_KO.md`, 로컬 증거)와 실제80 준비 보고서 (`out/development_plan_20261010/actual80_preparation_v1/report_ko.md`, 로컬 증거)를 따른다. P4·실제 자료 품질·R6는 계속 미완료이며 Goal은 active다.
