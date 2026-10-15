> **정리 전 이력 문서 — 2026-10-15 보존.** 원래 위치는 `goal.md`, 원형 SHA-256은 `27fa75f72c514f9af9ffd8bff8655ca39cdbecaa0e78009284cfb4a72865c3e2`이다. 현재 상태는 [현재 상태 문서](../../CURRENT_STATUS_KO.md), 실행법은 [README](../../../../README.md)를 따른다. 아래 상태·명령·수치는 당시 기록이며 상대 링크만 새 위치에 맞췄다. 로컬 `out/` 증거는 Git에 포함되지 않는다.

# 현재 작업 목표

<!-- r5-resolution-current:start -->

## 2026-10-15 현재80 범위 개발·검증 완료

최신 사용자 지시인 “R5 실패 원인을 해결하고 현재80으로 가능한 검증을 마무리”한 범위는 **CURRENT80_SCOPED_VALIDATION_COMPLETE**다. [최종 보고서](../../../../out/r5_resolution_20261014_v2/REPORT_KO.md)와 [통합 검산](../../../../out/r5_resolution_20261014_v2/finalization/completed_current80_001/CHECK_KO.md)을 기준으로 한다. 아래 날짜별 문단은 당시 이력으로 보존한다.

- [x] 기존80 저장자료·두 모델 검토 결속 및 DEV48 독립 재검산.
- [x] R5 혼합 매체·후보 관계/상태 수리,398개 최종 제품 회귀와 실패 사례의 native→main→WAL 재생.
- [x] 동일 설정 A/A 두 실행 종료와 원장 판독,64번 source475 ACCEPT,55번 source483 최종1/1·exit0·ACCEPT 및 UI 확인.
- [x] 원문·실패·서로 다른 소스 버전을 보존하고, 최종483파일·실행·UI 근거 검산 오류0 확인.

최종55 `20261015_005606_489420`은 요청12/실효1·대시보드ON·저부하에서 false/context_only/none/HOLD로 저장됐다. 검색·후보 관측0이어서 새 proposal/delta 분기의 실제 효과는 미관측이며, 그 경계는 저장 실패의 제품 재생으로 검증했다. A/A의39/45호출·682,095/737,254토큰과 최종 단건5호출·85,175토큰은 관측량이다. 정식 개선율·정답률·최신 전체80 재실행으로 해석하지 않는다.

독립 자료·재사용 근거·정식 TRAIN/CAL/FROZEN·일반화 성능과 R7 production은 보류한다. 기존 확대시험5개 실패도 [판독과 후속 항목](../../../../out/r5_resolution_20261014_v2/finalization/broad5_triage_v1/TRIAGE_KO.md)으로 남긴다.14번은 판본 계약/시험 기대 차이,35번은 원래 행·현재 가설 차단에는 재현되지 않은 보조 전언 경계 누락이다. 전체 회귀 PASS·제품 무결함·전체80 의미 승인은 주장하지 않으며 의미 게이트 REVIEW를 유지한다.

Goal API 상태: complete.

<!-- r5-resolution-current:end -->

<!-- research-completion-current:start -->

## 2026-10-14 source462 단계 이력 — 최신 상태는 위 완료 기록 참조

[최종 결과와 남은 수용 조건](../../../../out/research_completion_20261014_v1/REPORT_KO.md)는 당시 단계의 근거다. 기존80의 개발용 회수48관측,50번 수리·실제1건 검토, JSONL 댓글 생략 호환성·시작 전 실패·상대경로 이력·화면 전환 수리를 마쳤다. source462를 고정한 R6 실제1건은 원래 HOLD와 별도 native PUBLISH를 보존하며 HTTP9회·230.172초로 종료했고 원장 검산을 통과했다. 실제 화면과 관련 회귀도 확인했다.

R5 기준3건은 정상 종료했으나 BEFORE에서64번 공개 판정이 PUBLISH→HOLD로 달라 strict 비교가 거절됐다. runner exit1·DRAINED, AFTER 미시작, formal KPI는 NOT_ESTIMABLE이다. 기존 실패·원문·참조는 보존했다. 현재 실행 정책 차단은 없었다.

별도 자료가 없다는 사용자 답변에 따라 기존80으로 수행 가능한 DEV 연구를 끝냈다. MODEL_REFERENCE는 허용하지만 재사용 근거·미노출 평가 자료·TRAIN/CAL/FROZEN 조건은 미충족이다. R6 의미 검토는 원본 픽셀 미확인으로 HOLD/Medium이며 일반화 성능 승인이 아니다. **Goal 전체 완료 조건은 미충족으로, 조회된 blocked 상태를 complete로 바꾸지 않았다.** 요청 병렬12·대시보드 ON·저부하와 R7 보류를 유지한다. 아래 날짜별 기록은 당시 이력이다.

- [x] 기존80 자료 연결·개발용48관측과 반례 판독.
- [x] 50번 수리·실제 검토, 입력·대시보드 수리와 회귀·실제 화면 검증.
- [x] R6 실제 복구1건의 실행·예산·원본 보존·별도 guard 검산.
- [x] R5 실제 BEFORE 실패·AFTER 미시작·최종 종료 및 원인 판독.
- [ ] 같은 공개 결정에 결속되는 실제 paired 비교와 정식 지표 산출.
- [ ] 적격 자료에 근거한 정식 R2–R4 및 R6 일반화 품질 수용.

<!-- research-completion-current:end -->

<!-- source-quality-current:start -->

## 2026-10-14 최신 실측: 실제12 정상 종료·의미 품질 REVIEW

**현재 정책 거절은 없었다.** 검색3354 중지로 사전점검이 멈췄으나 기존 컨테이너3개를 기동한 뒤 `20261014_144947_200849`가 current source454·parallel12/12·대시보드ON·저부하 조건으로 정상 종료했다. completed/flushed12·failed/pending0·exit0, 결과/체크포인트12/12와 보호소스454/454 불변을 확인했다. [최종 실행·협업 평가](../../../../out/source_remaining12_actual_20261014_search_restored01/RUN_STATUS_KO.md)가 현재 상태다. 아래의 정책차단/미시작/실행중 문장은 당시 이력으로 보존한다.

새12 평가: Sol A7/H4/R1, Opus A9/H2/R1.24 무관참조 제거·44 self/own 및 embedded 상태 교정을 관측했다.65는 후보가 회복됐지만 High 경로라 Low 보존분기 효과는 미입증이다. **50번은 양측 REPROCESS**로 분류·후보 소실 원인 판독이 남는다.13·33은 검토 범위 차이가 있고 전체 의미는 REVIEW다. 전체80 승인·R5 paired·R2–R6 실제 연구 품질·사람정답/권리/holdout은 미완료이며 formal KPI는 NOT_ESTIMABLE이다. 제품코드 변경0.

- [x] 현재 코드 실제12 실행·종료·원본 결속·두 모델 전행 평가 완료.
- [x] 과거 정책거절과 이번 검색 서비스 중지의 구분 및 복구 확인.
- [ ] 50번 분류/후보 소실 원인 판독과 남은 작품 근거·실제 연구 수용.



## 2026-10-14 실행 재확인: 정책 거절 없이 실제12 분석 시작

**현재 실행 명령은 허용됐다.** 첫 호출은 검색3354 연결 거부로 사전점검에서 멈췄고, 기존 중지 검색 컨테이너3개를 시작해 query probe1/1·degraded0을 확인했다. 이후 `20261014_144947_200849`가 현재source454·parallel12/12·대시보드ON·저부하 조건으로 시작했다. [현재 실행 상태와 근거](../../../../out/source_remaining12_actual_20261014_search_restored01/RUN_STATUS_KO.md)를 따른다. 아래 과거 정책차단·미시작 기록은 당시 이력이며 현재 진행 상태가 아니다. 최종 품질·R5paired·연구 수용 완료는 아직 주장하지 않는다.

- [x] 현재 도구 호출·프로세스 기동·검색 복구·실모델 응답 확인.
- [ ] 실제12 종료·결과 결속·수정 효과 판독.



## 2026-10-14 후속: Opus 5.5·Sol 6.1 협업 평가 완료

[저장80 협업 평가와 최종 검증 상태](../../../../out/collaborative_final_eval_20261014_v1/root/REPORT_KO.md)가 이번 후속의 통합 결론이다. Opus 5.5 새 채팅과 Sol 6.1 서브에이전트가 각각80행을 독립 평가한 뒤 교차검토했다. 초기 판정은 Opus A60/H18/R1/I1, Sol A33/H37/R6/I4이며 일치50·불일치30이다. 일치율은 정확도가 아니다. 71의 Sol REPROCESS와 후보 URL·역할 누락 관련 과장된 근거를 정정했고 최초 라벨은 보존했다.

과거24·44·55·57·65 문제의 기존 수리를 확인했으며 **새롭게 확정한 현재 코드의 미수리 결함은0건**이다. 보호소스454/454·release253/253은 마지막 적용 SHA와 같다. 기존754 PASS·하위22, Node94 PASS·선택3 SKIP 및 저장 이력 화면 확인을 유지하되 이번에 새 시험이나 expert_main 모델 실행은 하지 않았다. 55/57의 과거 직접 시험을 최신754에 포함된 것으로 소급하지 않는다.

**의미 품질 REVIEW·최신 source454 모델 효과 NOT_OBSERVED·formal KPI NOT_ESTIMABLE**이다. 최신 실측, R5 paired, 실제 corpus/정답/권리/holdout·R2–R6 품질 수용은 남아 있다. 네이티브 Goal 조회값은 blocked이며 완료로 변경하지 않았다. 이전 실행 차단의 세부 이유는 미제공이고 콘텐츠 검열로 확정하지 않는다. 사용자 승인·parallel12·대시보드 ON·저부하 정책과 R7 보류를 유지한다.

- [x] 두 모델80행 결속·독립 평가·교차검토와 과거 문제/현재 수리 분리 완료.
- [x] 평가자 오류 정정, 원본 보존, 연구 지표 산출 범위와 다음 조건 기록 완료.
- [ ] 최신 코드 실제 모델 효과·R5 대조실행·실자료 연구 품질 수용.

아래 구현·시험·차단 기록은 원래 근거와 함께 보존한다.



## 2026-10-14 현재: 최종 754 PASS·19파일 적용·source454·저장 이력 화면 확인

**44번 화자/부정·65번 후보 보존·사건 카드/진단 저장·캐시 이력 탐색 수리를 적용했다.** [29개 전체 파일 754 PASS·하위22 PASS](../../../../out/r5_attempt_failure_validation_v1/run_final44_65_ui_history_v4_001/receipt.json) 후 [검증 바이트 19파일](../../../../out/source_final_application_v1/application_001/receipt.json)을 정확 적용했다. 제품6(기존5·신규1)·시험9(Python8·Node1)·fixture4이며 신규14파일, 기존5파일 백업, gitignore 시험 예외9와 기존 prefix·index 보존을 확인했다. [적용 후 검사](../../../../out/source_final_application_v1/application_001/post_apply_check.json)는 diff check0·신규 무시 없음이다. 현재 보호 소스는 **454개**다. [적용 보고서](../../../../out/source_final_application_v1/application_001/REPORT_KO.md)에 구현·적용·화면 확인 범위를 모았다.

| 적용 범위 | 검증된 동작과 범위 |
|---|---|
| 44번 내용절·부정 | [원문·바깥 주체와 부정 범위](../../../../out/source44_compound_speaker_review_v1/REPORT_KO.md)를 결속해 내용절 명사를 화자로 올리지 않는다. 긍정 어휘·원문 좌표를 남기며 최종 근거 채택과 구분한다. |
| 65번 후보 회수 | [F1–F4와 동일 문서 encoded URL 반증 경계](../../../../out/source65_candidate_preservation_review_v4/REPORT_KO.md)를 수리했다. 검산된 인물-작품 관계만 Low/noURL/noalias 후보로 보존하며 후단에서 같은 원자료를 재검산한다. 공개·학습 권한을 만들지 않는다. |
| 사건 카드·exporter | [성립 상태·성립 근거·평가 방향·최종 채택](../../../../out/source_context_event_state_ui_repair_v2/HANDOFF_KO.md)을 저장값으로 표시한다. native 근거 필드 하나를 기존 상한 안에서 저장하고 과거 미기록을 추정하지 않는다. |
| 실행 이력 탐색 | [전용 URL 캐시의 50,000항목 예산 선점](../../../../out/history_latest_discovery_audit_v1/REPORT_KO.md)을 분리했다. [root 직계 캐시 하위만 제외](../../../../out/history_cache_scan_review_v1/REPORT_KO.md)하며 디렉터리 자체 집계·깊은 동명·안전한 current-output·기존 상한을 유지한다. |

동일 presentation 제품의 [Node 97수집·94 PASS·기존 선택3 SKIP](../../../../out/source_context_event_state_ui_validation_v2/node_001/receipt.json)에서 새 카드6은 모두 PASS다. [74번 시험 후손](../../../../out/source_context_event_state_test_repair_v3/HANDOFF_KO.md)은 구·신 exporter에 공통인 graph edge1건 생략(`TRUNCATED/FIELD_LIMIT`)을 정확히 요구하고 사건 전체/native/bytes 상한 검사를 유지한다. 중간566·610·100과 최종754 및 Node 수를 합산해 고유 시험 수나 모델 정답률로 쓰지 않는다. **이 결과는 명시 파일의 오프라인 기능 검증이며 실제 모델 개선 효과·전체80 품질 승인이 아니다.**

[현재 디스크 source 결속](../../../../out/source_final_application_v1/application_001/source_binding.json)의 release는 `19de4b231ece83ec9c780f722433cdda501be12d7a450232eefc2a919e52df6d`, selected runtime source는 `c6065808971154a0ce6023776b78e8facbfa88d8888a2729968d43601a31c1bf`다. 모델 runtime generation 실측은 없다. [적용 후 실제 화면 확인](../../../../out/source_final_ui_validation_v1/receipt.json)은 로컬18868(PID51484, BelowNormal·affinity2)에서 최근80·24 이력 복구, 80건 상세와 저장 병렬12/12를 확인했다. 목록75·전체 탐색 상한 안내는 유지돼 무제한 전체 이력 복구를 뜻하지 않는다. 과거44 카드는 `actual / 성립 근거 미기록 / pos / 최종 근거 채택 false`와 저장 당시 화자 `마무리`를 그대로 표시한다. 새 코드의 모델 재실행 결과가 아니다. 콘솔 오류·경고 관측0이며 CUA 캡처는 도구로 관측했지만 파일로 저장하지 않았다. 제공 presentation은 적용 바이트와 같고 실제80 원본 SHA는 변하지 않았다.

**실제12는 미시작이다.** [자동 승인 검토가 실행 명령을 `blocked by policy`로 거절](../../../../out/source_remaining12_launch_prep_v1/rejected_attempt_001.json)했고 세부 이유는 제공되지 않았다. 기존 사용자 승인은 유지되며 재승인 요청·우회·재시도는 하지 않았다. [과거 source440 실행 ready](../../../../out/source_remaining12_launch_prep_v1/launch_plan.ready.json)는 당시 준비물로 보존하며 현재 source454의 실행 명세가 아니다. requested parallel12·dashboard ON·저부하 원칙은 유지하지만 새 actual run/scope·모델 결과는 없다.

이전80 `20261013_181711_146907`의 [A39/H33/R8/I0·END44·history842](../../../../out/p4_quality_followup_20261013/actual80_current_followup_parallel12_v1/final_review_80_v1/REPORT_KO.md)와 의미 **REVIEW**를 유지한다. 이번 적용으로 과거 라벨을 바꾸지 않는다. [R5 BEFORE exit1·FAILED/DRAINED](../../../../out/r5_actual24_pair_after_failure_repair_001/end_observation_001/receipt.json)·AFTER 미시작·동일 reference/WAL 결정 계약의 paired 미완료도 유지한다. guard 완화·참조 재봉인·실행 반복으로 완료를 주장하지 않는다.

준비80 관측192·HUMAN_GOLD0·권리UNKNOWN·training ready0·독립 holdout0, 실제 연구 품질·R2–R6 수용 미확정, 49번 full-context 진단2·69번10 미완료를 보존한다. **Goal blocked·formal KPI NOT_ESTIMABLE·R7 보류**다. 전체80 ACCEPT나 새 전체80 자동 재실행을 완료 조건으로 추가하지 않는다.

- [x] 29전체파일754 PASS·하위22 PASS와 source454 정확 적용을 확인했다.
- [x] Node94 PASS·기존 선택3 SKIP, 원형 실패와 시험 기대 정정 근거를 구분했다.
- [x] 저장80·24 이력, 80건 상세와 과거44 사건 카드의 실제 표시를 확인했다.
- [ ] 실제12 모델 효과·R5 paired·사람 정답/권리/실자료 품질은 미완료다.

[v33 후속 원형](../../../../out/p4_quality_followup_20261013/docs_integration_update_v33_followup_v1/REPORT_KO.md)을 보존하고 [v34 갱신 보고서](../../../../out/p4_quality_followup_20261013/docs_integration_update_v34/REPORT_KO.md)에 CURRENT 전후와 검산을 기록한다.

2026-10-14 같은 미해결 실행 차단과 자료 조건을 세 목표 턴 연속 확인해 Goal을 blocked로 전환했다. 추가로 진행할 확정 로컬 수리는 확인되지 않았다. 사용자 승인은 유지하며, [재개 조건과 보존 근거](../../../../out/goal_blocked_20261014_v1/HANDOFF_KO.md)를 따른다. 구현·로컬 시험·저장 화면 확인과 실제 모델·연구 평가의 미완료를 구분한다.

<!-- source-quality-current:end -->

## 직전 단계 기록: 191128 실행 종료와 첫 통합 후보 시험

> 아래 후보 미완료·실패 원인·진행 문장은 그때의 기록이다. 최신 수리 및 검증 상태는 위 현재 구역을 따른다.

실행 `20261012_191128_106718`은 **exit0·80/80 저장·실패0·대기0·terminal 확정**, 요청·실효 병렬도 **12/12**로 종료했다. [종료 검산](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/end_check_prep_v1/end_verification_02.json)은 **44개 PASS_TECHNICAL_ONLY**이며 실제 Python·venv launcher·supervisor 세 PID 종료를 확인했다. 실행 소스288개와 보호 목록6,279개의 보존은 해당 수령증 범위다. 시작 전 PREPARED 및 실행 중 RUNNING 기록은 당시 이력으로 보존한다.

[이력 API](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/history_check_prep_v1/run_first/receipt.json)는 **80행·11 GET·820개 검사 PASS**로 저장 원시 필드·BOUND·새 NSFW 상태·parallel12를 대조했다. [실제 화면](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/browser_final_readback_v1/receipt.json)은 **PASS_SCOPED_FINAL_LIVE_HISTORY_UI**다. live 100%·80/80·활성0, 최종 이력80건·12/12와 74번 live/history, 10·15·49·61번 history의 선택된 상세를 확인했다. NSFW 미평가/모델 false/규칙 양성 표시와 메모·댓글 귀속을 구분했고, 74번의 행별 장부 상태와 종료 manifest 요약을 덮어쓰지 않았다. 관측 콘솔 오류·경고0이며 이력 탐색 상한 경고는 유지한다. API 검사 수와 UI 관측·과거 Python/Node 시험 수를 합산하지 않는다.

[최종 행 결속·59행 리뷰 재사용](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_prep_v1/run_first/final_reconciliation_receipt.json)은 기존 **ACCEPT20·HOLD31·REPROCESS2·INFO_MISSING6**을 보존했다. [남은21행 리뷰](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_remaining21_v1/REVIEW_KO.md)와 [21행 결속 수령증](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_remaining21_v1/reviewer_receipt.json)은 **ACCEPT10·HOLD9·REPROCESS1·INFO_MISSING1**이다. **80행 검토는 완료했으며 인계용 합계는 ACCEPT30·HOLD40·REPROCESS3·INFO_MISSING7**이다. [전행 통합 결속](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_reconciled_v1/receipt.json)은 80행 원문·typed ID·전체 결과 SHA와 중복·누락0을 확인했고 [최종 종합](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_reconciled_v1/SUMMARY_KO.md)에 남겼다. REPROCESS는 **8·55·57번**이다. 55번 [정적 원인 조사](../../../../out/p4_quality_followup_20261012/semantic_state55_followup_v1/REPORT_KO.md)는 초기 제목 힌트와 작품성을 부정한 표면 anchor가 별도 제목 상태 계산에 남는 경로를 확인했다. 57번과 같은 질문 규칙이 아니며, 동일 문맥 동작 재현·수리는 미실행이고 신규 코드 회귀 귀속도 미확정이다. 74번 SOURCE_RULE_POSITIVE는 원문 댓글에 결속된 좁은 수리 효과를 ACCEPT로 검토했으며 전체 NSFW 정답으로 확대하지 않는다. 픽셀을 보지 않은 49번의 규칙 양성도 이미지 정답을 뜻하지 않는다. 전체 품질은 REVIEW다. [직전80 대비 공개 값 목록](../../../../out/p4_quality_followup_20261012/actual80_parallel12_v1/publication_delta_inventory_v1/REPORT_KO.md)은 145104→191128의 공식 제목·URL 변경0·동일80(제목+URL10·제목만1·null69)을 확인했다. 1·12·14번도 직전과 같으며, 더 오래된 변화와 구분한다. 값 동일성은 오공개0이나 공개 적격성 증명이 아니다.

8번 [명명 표현 v3 후보](../../../../out/p4_quality_followup_20261012/slang_role_expression_candidate_v3/SOURCE_FROZEN.json)와 57번 [제목 상태 후보](../../../../out/p4_quality_followup_20261012/semantic_state57_candidate_v1/SOURCE_FROZEN.json)는 AST·독립 정적 검토를 거쳐 [통합 후보 동결](../../../../out/p4_quality_followup_20261012/source_quality_bundle_validation_v1/SOURCE_FROZEN.json)에 결합됐다. [통합 후보 첫 시험](../../../../out/p4_quality_followup_20261012/source_quality_bundle_validation_v1/run_first/validation_receipt.json)은 **13파일 411 PASS·104 subtest PASS·2 FAIL, 오류·스킵0**이다. 정상57 serializer·main wrapper·WAL과 역할3 경로는 통과했지만, 57번 payload 제목 상태 및 candidate ledger의 입력 fingerprint 변조를 거절하지 못한 두 시험이 실패했다. **57번 optional scope seal을 별도 v2 후보에서 수리 중이며 통합 후보는 primary 미적용**이다. 실패 원본은 보존한다. 기존 pipeline `ee9088f6…`로 끝난 이번80은 이 두 후보의 실측 증거가 아니다. 이후 후보가 적용되면 이번 결과는 수리 전 기준 실행으로 남기며, 새 코드의 실측 여부를 별도로 표시해야 한다. 기존 수리 Python12파일251 PASS·104 subtest와 별도 Node87 PASS는 당시 로컬 증거로 유지한다.

R2/R3/R4 candidate 기능·community knowledge·native recovery는 OFF였으므로 연구 기능 ON 실측을 대체하지 않는다. 사람 정답0·학습 준비0·권리 UNKNOWN·formal KPI **NOT_ESTIMABLE**·품질 **REVIEW**·Goal active·R7 보류를 유지한다. 이후 Expert-main 실행 기본은 `--parallel 12`·대시보드 ON·기존 저부하 정책이다.

## 2026-10-12 이전 단계: 병렬12 전체80 정상 종료·전행 검토 완료, 품질 수용 REVIEW

실행 `20261012_145104_574531`은 **요청12·실효12·대시보드 ON**, exit0·80/80 저장·실패0·대기0·terminal 확정으로 종료했다. [종료 검산](../../../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/end_verification.json)27개와 [이력 API 대조](../../../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/history_api_receipt.json)499개가 통과했고 실행 종료 시점의 보호 파일4,718개에 변경이 없었다. 최종 코드의 토큰·검색 집계는 실제 검증을 마쳤다. 문맥 이벤트 토큰6,288,623과 검색74 hits/395 misses가 저장 trace·CLI·12워커 합계에 일치한다. manifest 관측9,059,040토큰은 별도 범위이며 모두 정식 KPI·전체 청구 비용이 아니다.

[실제 화면](../../../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/browser_receipt.json)은 live100%·80/80·활성0, 최종 이력80건·병렬12/12, 메모·NSFW·구조화 문맥·유효 설정·주변 관련 배지와 원시 진단 구분을 확인했다. 관측 콘솔 오류·경고0이며 이력 탐색 상한 경고는 유지한다. 현재 renderer의 [합성 저장자료84 PASS·0 FAIL·0 SKIP](../../../../out/development_plan_20261010/p4_reapproval_v1/ui_final_optional_readback_v1/receipt.json)은 별도 시험이며 검사 수를 합산하지 않는다. [대시보드](http://127.0.0.1:18864/)는 완료 결과를 표시한다.

[80행 최종 리뷰](../../../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/review_reconciled_v1/review_receipt.json)는 원문·댓글·최종 행 전체 SHA에 결속됐으며 **ACCEPT32·HOLD33·REPROCESS8·INFO_MISSING7**, gate **REVIEW**다. 나머지48건을 오류율로 계산하지 않는다. 새 제목 공개12·14번은 HOLD다.74번은 전문가 최초 응답부터 NSFW가 달랐으며, 새 저장 코드 회귀는 입증되지 않았다. 댓글 NSFW 검산 공백으로 REPROCESS를 유지한다. 미판정 근거를 두고 전체80의 새 오공개0이나 품질 통과를 선언하지 않는다. [종합 인계와 후속 개발](../../../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/REVIEW_SUMMARY_KO.md)에 근거·범위·미완료 조건을 정리했다.

[새80 snapshot](../../../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/final_snapshot_v1/receipt.json)은 저장 관측80·고유 원문80, VERIFIED / COMPLETE_WITH_LIMITS다. 기존80·실제12·112관측 준비물은 보존했다. 사람 정답0·학습 준비0·권리 UNKNOWN·독립 holdout 없음·formal KPI **NOT_ESTIMABLE**을 유지한다. R2/R3/R4/native는 OFF였으므로 실제 연구 기능 검증을 대체하지 않는다. **P4 기술 검증과 전행 리뷰 수행은 완료, 의미 품질 수용과 R2~R6 실제 평가 조건은 미완료이며 Goal은 active**다. 이후 Expert-main 테스트는 `--parallel 12`·대시보드 ON을 따른다.

아래 실제12·차단·미실행 등 설명은 해당 시점 이력이다. 이전 RUNNING 구역의 바이트는 이번 문서 갱신 백업에 보존했다.

## 이전 2026-10-12 단계: 병렬12 기술 종료·12행 리뷰와 제한된 UI 확인

실행 `20261012_134614_949602`는 **exit0·12/12 저장·실패0·대기0·terminal=true**, 요청12·실효12로 종료했다. [종료 기술 검산](../../../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/end_verification_v2.json)은 **PASS_TECHNICAL_ONLY·21개 검사**, [이력 API](../../../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/history_api_receipt.json)는 **84개 검사·12행 원시 저장값 일치·BOUND·병렬12/12**다. 초기 검산 실패는 병렬 체크포인트의 완료 순서를 입력 순서로 가정한 것으로, 원본 기록을 보존하고 v2에서 고유행·최종 입력 순서·WAL 결속을 확인했다. 이력 탐색 상한 경고는 유지한다.

[3개 에이전트 리뷰 종합](../../../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/REVIEW_SUMMARY_KO.md)은 고유 12행에 중복·누락 없이 **ACCEPT9·HOLD3**, gate **REVIEW**다. 약먹마의 비교 역할·별칭 source 연결, 회모장의 이미지·작품 결속, 추천 글의 구조화된 비교·추천 표면 보존이 남아 있다. CF01 및 의미 상태 v3의 독립 검토는 각 수리 당시 소스 범위에서 통과했다. CF03은 새 Decoder가 이전 오염 제목을 만들지 않아 이번 실측만으로 필터의 직접 효과를 입증하지 않는다.

[실제 화면 확인](../../../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/browser_receipt.json)은 **PASS_SCOPED_UI_WITH_METRICS_PENDING**이다. root가 18863의 live 100%·12/12·활성 worker0, 이력의 현재 run 최상단·최종 저장12건, 11718092의 NSFW true·메모·진단 STORED·BOUND 및 8670967의 adjacent 상태를 확인했다. 11663522는 live/history 모두 **주변 관련**과 원래 `is_relevant=false` 진단을 보존하면서 중복 무관 배지를 제거했다. 관측 콘솔 오류·경고는 0이며 로컬 스크린샷 파일은 만들지 않았다. [Node 판독](../../../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/node_readback.json)은 **81 PASS·3 SKIP·실패0·총84**로, native/provider/inference 환경 자료 미설정 선택 시험 3개는 이번에 실행되지 않았다. JavaScript 캐시 때문에 자산 버전 한 줄을 갱신한 뒤 실제 화면을 확인했으며 [최종 자산](../../../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/final_static_receipt.json)과 [독립 검토 v2](../../../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/independent_review_v2.json)는 기능 코드 동일성을 결속한다. 전체 UI·전체 기능 검증 PASS로 확대하지 않는다.

[토큰 context 수리](../../../../out/development_plan_20261010/p4_reapproval_v1/token_context_fix_v1/SOURCE_FROZEN.json)는 7파일 **104개·하위59개**, [검색 통계 worker 합산](../../../../out/development_plan_20261010/p4_reapproval_v1/cache_stats_fix_v1/validation_receipt.json)은 7파일 **115개·하위54개** 로컬 통과다. [토큰 독립 리뷰](../../../../out/development_plan_20261010/p4_reapproval_v1/token_context_fix_v1/independent_review.json)와 [캐시 독립 리뷰](../../../../out/development_plan_20261010/p4_reapproval_v1/cache_stats_fix_v1/independent_review.json)도 PASS이며 두 집계 상태는 **LOCAL_VERIFIED_ACTUAL_PENDING**이다. **18863의 Python 프로세스는 집계 수리 전 코드이고 정적 UI만 갱신했다.** 실제12의 token 965.2K·cache 0% 및 CLI hits20/misses96 관측을 소급 보정하지 않는다. 실제12 자체도 token/cache/UI 최종 수정 전 소스다. [후속 조치](../../../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/action_queue.json)에 남은 범위를 구분했으며 서로 겹치는 시험·기술 검사 수를 합산하지 않는다.

기존80의 기술 종료와 전행 리뷰는 보존하며 **최종 코드의 새 전체80 재실행은 아직 하지 않았다.** 실제12는 개발 노출80의 부분집합이고 독립 holdout·R5 paired 실측이 아니다. R2/R3/R4/native OFF였으므로 해당 기능의 실제 성공 근거로 쓰지 않는다. 사람 정답0·학습 준비0·권리 UNKNOWN·formal KPI **NOT_ESTIMABLE**·Goal **active**를 유지한다. 새 Expert-main 실행 기본은 요청12·실효 `min(input_count,12)`·대시보드 ON이다. 아래 단계별 기록은 당시 이력이며 현재 운영은 [P4 인계](../../P4_REAPPROVAL_RUN_20261010_KO.md)를 따른다.

## 이전 차단 이력: 2026-10-10 blocked 전환 당시

같은 실행 차단과 자료 선행 조건 미충족을 세 차례 연속 확인해 Goal을 **blocked**로 전환했다. 실제80·최신 브라우저·사람 판정과 사용 권리·실자료 품질·R5 실측은 미완료이며, formal KPI는 NOT_ESTIMABLE, R7은 보류다. [재개 조건과 인계](../../GOAL_BLOCKED_HANDOFF_20261010_KO.md)를 따른다. 아래 Goal active 표기와 전달 문서 SHA는 각 단계 작성 당시 기록이다.

## 2026-10-10 최신 진행: 전체 진입점과 완료 표시

80건 검토 자료 준비를 유지하면서 일반 `expert_main` 전체 진입점의 합성 입력 OFF·재생 ON·최초 분석 ON을 검증했다. 최초 ON은 provider1회·native7회를 거쳐 원래 HOLD와 별도 결과를 보존했다. 대시보드의 완료 상태·부분집합·실패·저장 대기와 이력 건수 표시를 수리했다.

관련 Python 3파일은 **71 passed, 40 subtests passed in 10.17s**, **Node 84개 통과·실패 0개·skip 0개**다. 일반 CLI 검증과 이후 UI/API 변경의 시험 범위를 분리한다. [현재 검증·남은 개발](../../EXPERT_ENTRY_COMPLETION_REVIEW_20261010_KO.md)을 따른다. 아래 수치와 당시 미완료 설명은 이전 단계 기록이다.

후속으로 semantic NIL/CAL→actual readback·baseline 연결을 구현하고 합성 로컬 검증을 마쳤다. **271 passed, 9 subtests passed in 167.12s (0:02:47)**이며 [R4 연결 검증](../../R4_ACTUAL_BRIDGE_20261010_KO.md)에 범위와 한계를 기록했다. 적격 실제 자료의 전체 성공 경로, 실제80·새 브라우저·사람 판정·실자료 품질·R5 실측은 미완료다. Goal active·formal KPI NOT_ESTIMABLE·R7 보류를 유지한다.

## 이전 검증: 기존 회귀 수리와 80건 검토 준비

기존 rework 실패 33개는 이름 변경 대응표와 실제 JUnit을 대조해 모두 통과했다. 마지막 3개 파일 실행은 **494 passed, 55 subtests passed in 181.10s (0:03:01)**다. 앞선 9개 파일 실행의 **5 failed, 578 passed, 64 subtests passed in 572.95s (0:09:32)**에서 시험 의존 파일 누락 4건과 최종 후보 단계의 기대 불일치 1건을 확인하고 보완했다. 제품 소스는 두 실행 사이에 그대로이며, 앞선 나머지 6개 파일의 통과를 따로 보존한다. 서로 다른 실행 수치를 합산하지 않으며 전체 저장소 회귀나 전체 CLI 검증 완료로 해석하지 않는다. [현재 수리 기록](../../LEGACY_REWORK_REPAIR_20261010_KO.md)과 [최종 실행 검산](../../../../out/development_plan_20261010/r6_rework_phase4_reconciled.json)을 따른다.

원형 본문에 결속된 별칭은 비권한 후보로 보존하고, 일반 화자 발화는 명시적인 작성자 복귀 전까지 보류한다. URL·시각 예외, OCR 작가 검색, 추천 보류와 최종 설명 봉인을 검증했다. 후보 제목·URL 보존과 최종 공개 title/URL을 따로 확인하며, 검색 후보만으로 공개 권한을 만들지 않는다.

[80건 검토 자료](../../../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)는 원문·저장 관측 112개와 참조를 연결했고 [독립 재판독](../../../../out/development_plan_20261010/r6_rework_actual80_preparation_readback_v1_KO.md)에서 원문·참조 52개 파일의 존재와 SHA 일치를 확인했다. 사람 정답 0건·학습 준비 0건·전 행 개발 노출·권한 UNKNOWN이며 후보 누락 3행, 미검토 이미지 25개는 남아 있다.

현재 상태는 **REWORK_LOCAL_VERIFIED_ACTUAL_PENDING**이다. 아래 자동 복구 수치와 33개 실패·NOT_PASS 표기는 이전 단계 이력이다. 실제80 모델 실행·새 브라우저는 자동 승인 검토의 `blocked by policy` 거절 이후 재시도하지 않았다. 실제 품질·사람 판정·적격 분할 자료·R5 실측·formal KPI는 미완료이며 formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다.

## 이전 자동 연결 단계: 일반 main 자동 복구의 로컬 검증 (2026-10-10)

일반 `expert_main`의 같은 호출 문맥을 원래 guard·commit·AUDIT·최종 저장 이후 제한된 복구로 연결하고, 별도 결과를 대시보드 live/history API와 표시까지 로컬 검증했다. 기본값은 OFF이며 ON에는 고정 정책·예산과 대시보드가 필요하다. 원래 결과·manifest·WAL은 보존하며 공개 적용·권한·중앙 DB 쓰기는 false다.

현재 상태는 **AUTOMATIC_NATIVE_LOCAL_VERIFIED_ACTUAL_AND_LEGACY_REWORK_PENDING**이다. [운영 계약](../../NATIVE_RECOVERY_AUTOMATION_20261010_KO.md)과 [실행별 검증·수리 기록](../../../../out/development_plan_20261010/r6_auto_reconciled_receipt.json)을 따른다. 검증은 합성 HTTP 응답으로 실제 전문가·guard·AST로 추출한 실제 main 함수 본문·원장·API·Node 표시를 통과한 범위다. 전체 CLI 기동과 실제 브라우저 통과를 뜻하지 않는다. 실행별 시험 수는 합산하지 않으며 마지막 수리 뒤 최초 전체 파일을 모두 다시 실행한 결과도 아니다.

최종 HOLD의 OCR 근거 누락은 새 `strict_evidence_v2` 검토 규칙으로 수리했고 기존 v1 영수증 판독은 보존했다. 실제80 모델 실행·새 브라우저·사람 정답·적격 실제 TRAIN/CAL/FROZEN 품질·R5 실측과 기존 rework 33개 실패는 남아 있다. 전체 회귀는 NOT_PASS, formal KPI는 NOT_ESTIMABLE, Goal은 active, R7은 보류다. 아래 단계별 수치와 미완료 설명은 당시 이력이며 현재 범위는 이 절을 따른다.

## 이전 단계: 명시 native 복구 연결과 당시 남은 자동화

R6의 **명시 same-call native 복구 연결을 합성 응답·HTTP mock으로 로컬 검증했다**. 현재 검증 상태는 `PASS_NATIVE_EXISTING_REWORK_FAILURES_PENDING`이며 기존 rework 시험 실패는 미해결이다. `run_native_recovery`는 같은 분석 호출에서 보존한 pre-final 문맥을 원래 입력·저장 provider 근거에 결속하고, 실제 Decoder·Verifier·Synthesizer·Arbiter와 기존 native 공개 guard를 호출한다. 원래 결과·manifest·WAL을 덮어쓰지 않고 별도 scope의 새 publication WAL과 결과를 저장·재판독한다. guard 판정 기록은 공개 반영이 아니며 `public_apply`, `publication_authority`, `central_db_write`는 false다.

native 추가 LLM·검색·fetch는 하나의 영속 호출·byte·시간 예산을 공유하며 먼저 예약하고 전송한다. 완료 job만 저장 결과를 0회 호출로 재생하고, 미완료·불확실 요청은 재시작 후 재발송하지 않는다. upstream provider 수집은 별도 앞 단계로 합계에 표시하며, MCP 내부 원격 검색 횟수·취소·가격은 확정하지 않는다. 과거 actual80/32 저장 JSON을 살아 있는 native 문맥으로 복원하는 기능은 없다.

최초 Python 16개 파일의 원시 결과는 시험 893개 통과·32개 실패와 하위 시험 21개 통과다 (`32 failed, 893 passed, 21 subtests passed in 1228.60s (0:20:28)`, [최초 전체 수령증](../../../../out/development_plan_20261010/r6_native_final_receipt.json)). 합성 응답 fixture만 보정한 뒤 workflow 1개 파일의 시험 7개가 통과하고 실패는 1개, 하위 시험은 0개다 (`1 failed, 7 passed in 657.84s (0:10:57)`, [보정 후 수령증](../../../../out/development_plan_20261010/r6_native_repair_receipt.json)). 그 뒤 실제 fetch 응답의 identity 캐시를 복제하는 제품 코드를 수리하고 context·workflow 2개 파일을 재검증해 시험 67개와 하위 시험 0개가 통과했고 실패는 0개다 (`67 passed in 701.00s (0:11:41)`, [캐시 수리 후 수령증](../../../../out/development_plan_20261010/r6_native_capture_final_receipt.json)). **세 실행의 시험은 겹치므로 합산하지 않는다. 마지막 수리 뒤 전체 16파일을 다시 실행한 결과도 아니다.** [재조정 수령증](../../../../out/development_plan_20261010/r6_native_reconciled_receipt.json)은 새 native 경로의 실패가 수리됐음을 기록하며 최초 전체 실행을 PASS로 바꾸지 않는다.

기존 rework 시험은 전체 실행에서 31개가 실패했다. 동일한 빈 캐시·단일 파일 격리 조건의 이전 baseline과 현재 소스에서는 각각 33개 실패가 재현됐고, 33개의 예외 종류·정규화 메시지가 같았다. 비교상 남은 차이는 0개지만 시험 상태는 `FAILED`다 ([격리 비교 근거](../../../../out/development_plan_20261010/r6_native_isolated_rework_comparison_v1.json)). **실패 33건은 해결되지 않았으며 전체 회귀 통과나 모든 OFF 동작의 동등성을 뜻하지 않는다.** [API·검증 범위](../../../../out/development_plan_20261010/r6_native_api_KO.md), [현재 코드·캐시 수리 독립 검토](../../../../out/development_plan_20261010/r6_native_capture_cache_review.json)와 [I/O 독립 검토](../../../../out/development_plan_20261010/r6_native_io_closure_review.json)를 따른다. [fixture 수정 독립 검토](../../../../out/development_plan_20261010/r6_native_fixture_repair_review.json)는 앞선 수리 이력으로 보존한다. 이번에는 Node·브라우저 시험을 실행하지 않았다. 화면 소스는 이전 provider 단계의 [Node 66개 통과 기록](../../../../out/development_plan_20261010/r6_provider_node_receipt.json)과 같으며, 그 기록은 새 native 화면이나 브라우저 통과 증거가 아니다. 이전 probe 실패와 simulation/provider 시험도 별도 이력으로 보존한다.

[80건 검토 큐](../../../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)는 그대로 보존했다. 입력 80행·저장 관측 112개·중복 게시물 32개이며, 사람 정답과 학습 준비는 모두 0건이다. 기존 WORK/NIL 참조를 사람 정답으로 승격하거나 새 독립 분모로 세지 않았다.

**일반 main의 자동 복구 스케줄과 native 결과의 대시보드 live/history 연결은 아직 미완료다.** 실제 외부 모델·검색 호출은 0회이며 실제 복구 품질·비용·formal KPI는 `NOT_ESTIMABLE`이다. P4 실제80 실행과 새 Chrome 검증은 기존 자동정책 차단을 재시도하지 않았다. 실제 자료·사람 판정·R4 학습/교정 품질·R5 실측도 남아 있다. R6 전체 완료로 처리하지 않으며 Goal은 active, R7은 보류다.

## 이전 단계: provider 근거 수집과 80건 검토 준비 (2026-10-10)

당시 R6 상태는 **PROVIDER_EVIDENCE_LOCAL_VERIFIED_NATIVE_GUARD_AND_ACTUAL_RECOVERY_PENDING**였다. 원본 HOLD·AUDIT에 결속한 명시 계획 → 영속 예약 → 단일 HTTP → 원시 응답 저장·독립 판독 → `expert_main`·대시보드 연결을 구현했다. 완료된 요청은 0회 전송으로 재생하고, 완료 여부가 불명확한 요청은 재발송하지 않는다. 최초 fresh source 검사부터 응답 저장·재판독까지 같은 시간 제한을 적용한다. 마지막 `REQUEST_FINALIZED` 자체의 저장은 이 시간 범위에서 제외한다. 저장 성공은 `PROVIDER_EVIDENCE_STORED`, 공개 guard는 `GUARD_NOT_EVALUATED`이며 일반 실행의 자동 복구는 아직 연결하지 않았다.

이전 provider 단계의 변경 영향 Python 23파일 `779 passed, 163 subtests passed in 654.67s (0:10:54)`, Node 66개 PASS다. 실제 파일 원장과 HTTP mock, 저장 결과의 API·Node 표시를 확인했다. 실제 외부 모델·검색 호출과 새 브라우저 검증은 0회다. [실행 계약·한계](../../../../out/development_plan_20261010/r6_provider_api_KO.md), [Python 검증](../../../../out/development_plan_20261010/r6_provider_final_receipt.json), [Node 검증](../../../../out/development_plan_20261010/r6_provider_node_receipt.json)을 따른다. 아래 이전 단계의 수치는 당시 증거이며 이번 수치와 합산하지 않는다.

[80건 검토 큐](../../../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)를 준비했다. 원래 입력 순서 80행에 112관측·관측별 후보 기록 121개를 연결했고 중복 게시물 32개를 별도 표본으로 세지 않았다. WORK 2·NIL 6은 기존 모델 참조, UNJUDGED는 72건이다. 사람 정답·학습 준비는 모두 0건이며 전 행이 개발에 노출됐다. 후보 결손 3행과 미검토 이미지 21행을 검토 순서에 반영했지만 정답·역할·사용 권리를 채우지 않았다. [검산 수령증](../../../../out/development_plan_20261010/actual80_review_queue_v1/verification_receipt.json)에 원본 46개·이전 준비 파일 5개의 보존 근거를 남겼다.

당시 남은 범위는 P4 실제80·새 브라우저, 실제 corpus·사람 판정·TRAIN/CAL/FROZEN 품질, R5 실측, R6 native 공개 guard·자동 복구·실제 품질이었다. 현재 native 연결과 미완료 범위는 위 최신 기록을 따른다. 당시 R6 후속 계획은 [native guard 개발 메모](../../../../out/development_plan_20261010/r6_native_guard_next_steps_KO.md)를 따른다. 기존 자동 승인 차단을 재시도하지 않았으며 formal KPI는 `NOT_ESTIMABLE`, Goal은 active, R7은 보류다.

NIL 학습·저장·화면 표시와 CAL 온도 학습·FROZEN 소비의 최신 상태는 [R4 운영 기록](../../CANDIDATE_RERANKER_SHADOW_20261010_KO.md)을 따른다. 명시적 FROZEN 재관측 교정·capture 저장·화면 표시를 연결했다. 의미 역할·검증 자료의 별칭 관측과 저장·화면 표시를 추가했다. 새 의미 관측을 버전별 학습·모델·CAL에 연결하고 합성 로컬 회귀로 검증했다. 일반 R2 graph 자동 공급과 새 입력의 고정 교정 추론을 로컬 검증했다. 실제 자료 품질 평가와 새 소비 화면의 브라우저 확인은 남아 있다. 이전 단계 시험 수는 합산하지 않는다.

R4 상태는 **GENERAL_INFERENCE_LOCAL_VERIFIED_BROWSER_AND_ACTUAL_DATA_PENDING**다. 일반 입력의 실제 R2 원문·후보 ID·작품/판본·출처 bytes를 고정 semantic NIL 모델 및 CAL 온도에 연결하고 expert_main 저장·API·대시보드 표시를 구현했다. 현재 원문·R2·모델 점수를 재생 검산하며, FROZEN 배정이나 정답을 만들지 않는다. 이번 로컬 회귀는 Python 38파일 `1440 passed, 42 subtests passed in 229.37s (0:03:49)`, Node 58개 PASS다. 실제 pipeline에서 저장한 live/history 자료를 Node 표시 시험으로 연결했다. 실제80 준비 묶음은 112관측/80고유행을 원문과 연결했으나 사람 정답0·학습 준비0이며 전 행이 개발 노출 자료다. 실제 TRAIN/CAL/FROZEN 품질, 새80 모델 실행, 새 화면의 브라우저 검증과 R6 실제 provider 복구는 남았다. 실제 모델 API·검색·source-backed 학습은 0회다. 실제80·Chrome의 자동 승인 검토가 blocked by policy로 차단한 실행은 재시도하지 않았다. formal KPI는 NOT_ESTIMABLE, Goal은 active다.

[R6 제한 복구 실행](../../BOUNDED_RECOVERY_EXECUTION_20261010_KO.md): 당시 상태 **LOCAL_ENTRYPOINT_UI_VERIFIED_ACTUAL_RECOVERY_PENDING**. 별도 `expert_main` 합성 복구 진입점과 검토·계획·AUDIT·복구 보고서의 API·live/history 표시를 연결했다. 변경 영향 Python 13파일의 382개 시험·45개 하위 시험과 Node 37개, 실제 브라우저 및 별도 main 프로세스 합성 검증을 통과했다. 실제 모델·검색 호출은 0회다. 실제 provider 전체 연결·자동 복구·품질 평가는 남았으며 앱 Goal은 active다.

> 2026-10-10 현재 Goal: 승인된 [개발 계획](../../EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md)의 P0~P3와 R1~R5 로컬 기능·계약 검증을 진행했다. R5 저부하 RunSpec v3·실제 실행 관측·계획 생성·판독·화면을 구현하고 Python51파일·1147개 시험·210개 하위 시험과 Node26개 PASS, reader 행 결속 보강 후 영향9파일·269개 시험·97개 하위 시험 PASS, 독립 반례18개와 합성 live/history 표시를 확인했다. 실제 모델·검색 실행0이며 비용·품질·formal KPI는 NOT_ESTIMABLE이다. R5 상태는 **LOCAL_CONTRACTS_VERIFIED_ACTUAL_PAIRED_MEASUREMENT_PENDING**다. P4 새80은 자동 승인 차단 2회 이후 미재시도다. R2/R3 실제 자료 평가, R4 실제 source-backed TRAIN/CAL/FROZEN·NIL 학습·확률 교정, R5 실제 두 arm 계측과 R6 실제 provider 전체 연결·자동 실행·품질 평가는 남았다. R6 합성 실행과 판독은 위 최신 검증 기록을 따르며 R7은 보류다. 앱 Goal은 active다. [현재 구현 기록](../../EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md)을 우선하며 아래9월 목표와 원래 G1~G7 완료는 과거 범위로 보존한다.

상단 인계 갱신일: 2026-10-10 KST. 아래 본문 갱신일: 2026-09-14 KST(과거 목표 기록).

## 현재 상태와 목적

기존 문제·개선 회의·구현 결과를 정리했고, 후보 회수·선택 진단 단위의 구현과 독립 실측까지 완료했다. 첫 합성 tranche의 기존 16건은 보존했으며, 별도 challenge 4건을 추가해 실제 로컬 LLM은 weights 부재에 따라 `UNAVAILABLE`로 정직하게 남겼다.

프로젝트 목적은 커뮤니티 글이 가리키는 웹소설을 더 정확하게 찾고, 근거 부족·비교작·모호함을 구분하는 것이다. 현재 실행 범위는 `RESEARCH_ONLY_LOCAL_LLM_BENCHMARK`다. GPT-6 Astra는 사용자가 지정한 후속 작업 모델이며, 모델 변경 자체를 품질 개선 근거로 삼지 않는다.

## 완료된 개선 단위

**후보 회수 실패, 정답 후보가 있을 때의 선택 실패, 실제 NIL, ABSTAIN을 구분해 측정한다.** (`CANDIDATE_SELECTION_DIAGNOSTICS_COMPLETE`)

- 입력: 기존 합성 16건과 후보 누락·비교작·실제 NIL·모호함을 구분하는 최소 challenge fixture. 기존 16건과 추가 challenge의 분모를 따로 유지한다.
- 변경 범위: 기존 연구 코어·runner·대응 fixture/test·결과 보고에 필요한 최소 수정. 별도 authority 또는 새 실행 프레임워크를 만들지 않는다.
- 산출물: 행별 후보 ID와 정답 포함 여부, 후보 Recall@K, 정답 포함 조건부 선택률, 전체 입력 기준 결과와 실패 원인 표.
- 실행: `baseline` 16건과 `challenge` 4건을 별도 output 디렉터리에서 dashboard ON·요청 `--parallel 16`으로 실행했다. effective parallel은 각각 `16`, `4`였다.
- 종료조건: 실패 단계가 구분되고, NIL과 후보 누락을 혼동하지 않으며, 관련 회귀검증과 비교 실행을 기록했다. 성능 향상 여부와 관계없이 해당 개선 단위를 닫는다.
- 재실행: 코드 변경·실패·새 증거가 있을 때 해당 범위만 재검증한다. 같은 질문으로 회의·전체 스위트·런을 계속 반복하지 않는다.

## 실행·검증 workflow 후속

2026-09-14에 기존 runner의 score semantics와 권위 경계를 변경하지 않는 얇은 실행 wrapper를 추가했다. `tools/run_research_local_benchmark_workflow.py`는 standalone dashboard를 재사용하거나 기동하고, baseline/challenge를 요청 `--parallel 16`으로 순차 실행한 뒤 각 terminal manifest validator와 focused unittest를 묶어 새 `out/research/` 하위 디렉터리에 기록한다. 이번 end-to-end 산출물은 `out/research/research_workflow_20260914_automated_e2e`이며 baseline `16/16`, challenge `16/4`, dashboard `CONNECTED`, focused `14/14 PASS`다.

이 wrapper는 모델을 설치하거나 local LLM `UNAVAILABLE`을 임의 대체하지 않는다. workflow 산출물도 `RESEARCH_EVIDENCE_ONLY / OFFLINE_SHADOW`이며 중앙 Slang DB·production·publication에는 쓰지 않는다.

2026-09-15 재개 검증에서 workflow builder는 configured remote vLLM의 endpoint·model·identity fingerprint를 부분적으로 받거나 opt-in만 단독으로 받지 않도록 fail-closed 계약을 보강했다. 실행 예시는 [검증 결과](../../VERIFICATION_RESULTS.md)의 2026-09-15 항목을 따른다.

후속 diagnostic propagation에서는 child metrics의 case/action/failure-stage/Recall@K/conditional-selection을 workflow manifest와 한국어 report에도 보존하도록 wrapper를 보강했다. 최종 output `out/research/research_workflow_20260915_diagnostics_manifest_vllm_v2`에서 challenge 네 failure stage, Recall@5 `2/3`, 조건부 selection `0/1`, child validator, self-hash, focused `18 tests OK`를 확인했다. baseline의 terminal은 `RESOLVED 56 / NIL 8 / ABSTAIN 0`, challenge는 `RESOLVED 14 / ABSTAIN 2`로 관측됐으며 이전 remote run과의 차이는 성능 변화로 일반화하지 않는다.

후속 `challenge-001` 후보 회수 분석에서는 gold가 현재 common BM25 top-5 밖이고 query와 gold text 사이 lexical anchor가 없음을 확인했다. 따라서 selection prompt를 retrieval 수정처럼 사용하지 않고, verified semantic candidate-generation arm을 별도 연구 단위로 보류했다. 분석 artifact는 `out/research/research_candidate_recall_20260915/analysis_ko.md`다.

상세 결과와 게이트는 [후보 회수·선택 진단 보고서](../../RESEARCH_CANDIDATE_SELECTION_DIAGNOSTICS_20260914_KO.md)에 기록했다. 실제 로컬 모델 연결, 데이터셋 확대, dense/RRF·학습 reranker 비교는 별도 후속이며 자동 완료조건이 아니다.

## 다음 후보 단위

weights 또는 검증된 loopback endpoint가 준비될 때에만 `local_llm` A/B를 별도 실행한다. `expert_main.py`에 이미 설정된 vLLM endpoint는 기본 loopback guard를 우회하지 않고 명시적 opt-in으로만 사용한다. 그 전의 `UNAVAILABLE` 진단과 실제 연결 후 결과를 섞어 품질 점수로 해석하지 않는다.

## expert_main vLLM 연결·실측

2026-09-14에 저장소 `expert_main.py`의 기존 설정(`LLM_SERVER_TYPE=vllm`, endpoint `http://10.20.0.101:8000/`, model `unsloth/gemma-4-26B-A4B-it-NVFP4`)을 읽고 `/v1/models`와 benchmark 형식 completion을 확인했다. 별도 PC 로컬 `llama-server`는 정본 경로로 사용하지 않았고, 모델 설치도 하지 않았다.

`tools/run_research_local_benchmark_workflow.py`에 configured remote vLLM 명시적 opt-in과 `expert_main`과 동일한 `enable_thinking=false` 요청 계약을 반영했다. 정본 산출물은 `out/research/research_workflow_20260914_expert_main_vllm`이다. baseline은 입력 `16`, requested/effective `16/16`, local_llm `RESOLVED 12 / NIL 4 / UNAVAILABLE 0`, 정확히 `16/16`; challenge는 입력 `4`, requested/effective `16/4`, local_llm `RESOLVED 3 / ABSTAIN 1 / UNAVAILABLE 0`, 정확히 `1/4`였다. dashboard `CONNECTED`, child validator `PASS`, focused test `16 tests OK`를 확인했다.

이는 synthetic fixture 연구 증거일 뿐 실제 DC 성능, production/publication/full-scan 승인 또는 일반화된 성능 향상 주장이 아니다. challenge의 후보 누락·선택 오류·NIL/ABSTAIN 진단은 전체 terminal 분모에 유지한다.

## 유지할 기준

권리 범위가 기록된 자체·허가·사용자 제공·합성 데이터, 입력/gold/code/model/prompt/seed/runtime fingerprint, 행별 retrieval·selection trace, 전체 terminal 분모, offline/shadow와 중앙 Slang DB·publication 비쓰기를 유지한다. 실제 테스트런·검증런은 dashboard ON과 요청 `--parallel 16`을 사용하고 effective parallel도 기록한다. 문서·정적 검토에 벤치마크를 억지로 실행하지 않는다.

새 발견은 TODO에 기록하고 현재 종료조건에 자동 추가하지 않는다. 리뷰는 현재 문제·변경·판정을 대상으로 하며 과거의 고정 분과 수나 구형 모델 배분을 계승하지 않는다.

## 보류 범위

`DEFERRED_P0_AUDIT_TRACK`의 fixed store·외부 서명·trusted runtime·owner numerical policy·외부 review authority는 보존한다. 해당 트랙의 `NO_GO`와 actual `0/40·0/20`은 연구 실행의 blocker가 아니며 연구 성과로 통과 처리하지 않는다. production/publication/full-scan 전환은 별도 범위 결정 때 재검토한다.

## 정본과 이력

1. 이 파일: 현재 범위와 다음 개선 단위.
2. [GPT-6 Astra 인계·범위 정리](../../GPT6_ASTRA_RESEARCH_HANDOFF_20260906_KO.md): 원래 문제, 아이디어, 구현·측정 상태와 인계 프롬프트.
3. [연구 실행 계획](../../RESEARCH_ONLY_LOCAL_LLM_BENCHMARK_PLAN_20260905_KO.md): 구현 계약과 첫 tranche의 완료 근거.
4. [후보 회수·선택 진단 보고서](../../RESEARCH_CANDIDATE_SELECTION_DIAGNOSTICS_20260914_KO.md): 구현·실측 산출물과 게이트.
5. [TODO](../../TODO.md) · [CHECKLIST](../../CHECKLIST.md): 현재 체크와 보류 항목.
6. [기존 goal 원본 보관](../../../../goal.history.20260906.md): 수정 전 870,401 bytes를 그대로 보존했다. SHA256 `b36b3302948bd3baaf77621b0c77bed238a05847625219e6704c2c03c0560f14`.

보관본 및 과거 문서의 `Active Objective`, `Active Next Prompt`, 반복 실행·모델 배분 지시는 역사 기록이다. 현재 사용자 지시와 이 파일의 실행 범위를 덮어쓰지 않는다. 과거 계획의 3/11 또는 P0 테스트 통과 수를 현재 연구 진행률로 재사용하지 않는다.

이 파일은 저장소 목표다. 이전 Codex 작업의 앱 Goal 레코드를 교체했다는 뜻은 아니다. 2026-09-15 현재 앱 Goal은 exact checkout의 `RESEARCH_ONLY_LOCAL_LLM_BENCHMARK` 실행 자동화·검증 workflow 후속으로 active이며, 별도 작업·자동 재개는 생성하지 않았다.

명시 FROZEN 재관측의 설정·저장·화면 계약과 검증 근거는 [운영 기록](../../CANDIDATE_RERANKER_SHADOW_20261010_KO.md)을 따른다.
