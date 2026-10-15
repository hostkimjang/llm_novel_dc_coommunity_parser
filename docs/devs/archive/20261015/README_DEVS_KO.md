> **정리 전 이력 문서 — 2026-10-15 보존.** 원래 위치는 `docs/devs/README.md`, 원형 SHA-256은 `a7e4e514a3482a831bf2637c87471c8097ff236783fa25f3d6f30af4339cc617`이다. 현재 상태는 [현재 상태 문서](../../CURRENT_STATUS_KO.md), 실행법은 [README](../../../../README.md)를 따른다. 아래 상태·명령·수치는 당시 기록이며 상대 링크만 새 위치에 맞췄다. 로컬 `out/` 증거는 Git에 포함되지 않는다.

# 개발 문서 허브

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

## 이전 2026-10-10 재승인 당시: 실제80 진행·저장 화면 부분 검증

사용자 재승인 뒤 이번 실행 명령이 통과했고, `20261010_210300_688879`의 실제 모델 응답 시작이 확인됐다. P4 실행 업무는 진행 중이며 정상 종료·전행 의미 검토·품질 수용을 아직 완료하지 않았다. 운영 담당자가 `get_goal`에서 **active** 재개를 확인했다. 이전 실행 거절과 차단 감사는 당시 이력으로 보존한다. [현재 실행·종료 후 게이트](../../P4_REAPPROVAL_RUN_20261010_KO.md)를 따른다. 초기 IAB의 live/history 접속 관측은 전체 브라우저 검증 완료가 아니다. 사람 정답·사용 권리·실자료 품질과 formal KPI `NOT_ESTIMABLE` 제한은 유지한다.

현재 UI에서 [의미 관측 6화면](../../../../out/development_plan_20261010/p4_reapproval_v1/semantics_browser_v1/REPORT_KO.md), [P3 진단·설정 2화면](../../../../out/development_plan_20261010/p4_reapproval_v1/p3_browser_v1/report_KO.md), [일반 추론 2화면](../../../../out/development_plan_20261010/p4_reapproval_v1/inference_browser_v1/REPORT_KO.md), [native 복구 2화면](../../../../out/development_plan_20261010/p4_reapproval_v1/native_browser_v1/REPORT_KO.md), [R5 complete/partial 4화면](../../../../out/development_plan_20261010/p4_reapproval_v1/r5_browser_v1/report_KO.md), [독립 provider 2화면](../../../../out/development_plan_20261010/p4_reapproval_v1/provider_browser_v1/REPORT_KO.md)을 확인했다. 총 18화면이며 각 검증의 콘솔 오류·경고는 0건이다. P3는 현재 whitelist 투영·41개 기술 검사, R5는 최종 48개 검사를 통과했으며 검사수는 합산하지 않는다. R5 partial의 END는 null·관측 미완료다. 일반 추론·native는 고정 API payload 표시, provider는 row/bound와 합성 표시 manifest를 사용한 어댑터 표시 검증이며 새 producer·원래 생산 API/원장 결속의 재검증이 아니다. 의미 모델 소비 성공·전체 UI·실제80 종료·품질 수용으로 확대하지 않는다. 아래 차단 상태와 검증 수치는 각 기록 당시의 이력이다. [통합 검산](../../../../out/development_plan_20261010/p4_reapproval_v1/browser_round_v1/REPORT_KO.md)에서 source417·fixture48 불변과 소유 preview 7개 PID 소멸을 확인했다. 강제 종료 코드1·연결 해제 trace는 콘솔 오류 및 실제80 실패와 구분한다.

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

[R6 제한 복구 실행](../../BOUNDED_RECOVERY_EXECUTION_20261010_KO.md): 당시 상태 **LOCAL_ENTRYPOINT_UI_VERIFIED_ACTUAL_RECOVERY_PENDING**. 별도 `expert_main` 합성 복구 진입점과 검토·계획·AUDIT·복구 보고서의 API·live/history 표시를 연결했다. 변경 영향 Python 13파일의 382개 시험·45개 하위 시험과 Node 37개, 실제 브라우저 및 별도 main 프로세스 합성 검증을 통과했다. 실제 모델·검색 호출은 0회다. 실제 provider 전체 연결·자동 복구·품질 평가는 남았으며 앱 Goal은 active다.

[R5 저부하 paired 계측](../../PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md): **LOCAL_CONTRACTS_VERIFIED_ACTUAL_PAIRED_MEASUREMENT_PENDING**. R5 저부하 RunSpec v3·실제 실행 관측·계획 생성·판독·화면을 구현하고 Python51파일·1147개 시험·210개 하위 시험과 Node26개 PASS, reader 행 결속 보강 후 영향9파일·269개 시험·97개 하위 시험 PASS, 독립 반례18개와 합성 live/history 표시를 확인했다. 실제 모델·검색 실행0이며 비용·품질·formal KPI는 NOT_ESTIMABLE이다. 이 R5 수치는 해당 검증 범위의 기록이며 현재 R4 후속 수치와 합산하지 않는다.

[R4 학습 baseline과 평가](../../CANDIDATE_RERANKER_SHADOW_20261010_KO.md): R4 상태는 **GENERAL_INFERENCE_LOCAL_VERIFIED_BROWSER_AND_ACTUAL_DATA_PENDING**다. 일반 입력의 실제 R2 원문·후보 ID·작품/판본·출처 bytes를 고정 semantic NIL 모델 및 CAL 온도에 연결하고 expert_main 저장·API·대시보드 표시를 구현했다. 현재 원문·R2·모델 점수를 재생 검산하며, FROZEN 배정이나 정답을 만들지 않는다. 이번 로컬 회귀는 Python 38파일 `1440 passed, 42 subtests passed in 229.37s (0:03:49)`, Node 58개 PASS다. 실제 pipeline에서 저장한 live/history 자료를 Node 표시 시험으로 연결했다. 실제80 준비 묶음은 112관측/80고유행을 원문과 연결했으나 사람 정답0·학습 준비0이며 전 행이 개발 노출 자료다. 실제 TRAIN/CAL/FROZEN 품질, 새80 모델 실행, 새 화면의 브라우저 검증과 R6 실제 provider 복구는 남았다. 실제 모델 API·검색·source-backed 학습은 0회다. 실제80·Chrome의 자동 승인 검토가 blocked by policy로 차단한 실행은 재시도하지 않았다. formal KPI는 NOT_ESTIMABLE, Goal은 active다.

[R3 커뮤니티 지식 READ_ONLY](../../COMMUNITY_KNOWLEDGE_READ_ONLY_20261010_KO.md): 로컬 수집 후보·별칭·일반 의미 분리, 실제 소비·저장·표시 구현과 Python 37개 파일의 시험 726개와 하위 시험 132개, 화면 표시 시험 24개 PASS, 실제 corpus 품질 미평가를 구분한다.

## 현재 개발 계획

[expert_main 통합과 대시보드 후속 개발 계획](../../EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md): 최신 코드 통합, 메모·중첩 이력·R08 표시, 실행 설정·문맥 진단 저장, 최종 검증과 연구 확장의 순서·완료 기준이다. [적용 범위 점검](../../DASHBOARD_EXPERT_MAIN_COVERAGE_AUDIT_20261010_KO.md)의 누락 항목을 후속 개발로 연결한다.

[현재 구현·검증 기록](../../EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md): P0~P3 통합과 R1~R4 로컬 검증, P4 새80건 자동 승인 차단 2회 이후 미재시도, R2/R3 실제 품질 미평가를 확인한다. [R5 준비 계약](../../../../out/development_plan_20261010/r5_implementation_contract_KO.md)은 초기 설계이며 현재 R5 구현·실측 구분은 위 운영 기록을 따른다. R6 합성 실행·판독은 위 검증 기록을 따르며 실제 실행·품질 평가는 남았다. R7 보류·앱 Goal active를 유지한다. Git 제외에 걸렸던 회귀시험/helper13개는 명시 예외로 포함했다.

[R1 저장 결과 평가 snapshot](../../RESEARCH_EVALUATION_SNAPSHOT_20261010_KO.md): 정식 도구·시험28개·기존80/32 자료 검산 PASS, 실행별 관측112행과 고유80개 분리, reference 미결속과 원본 경로 미기록 한계를 확인한다.

[R2 고정 작품 후보 회수 SHADOW](../../CANDIDATE_RETRIEVAL_SHADOW_20261010_KO.md): corpus·원문 query·pipeline·저장·표시·평가기 계약, 통합608개＋subtests122개·표시23개와 독립 검토 PASS, 실제 자료 준비 상태를 확인한다.

## 현재 인계 진입점

[2026년 10월 10일 최근 채팅 통합 인계](../../PROJECT_CHAT_HANDOFF_20261010_KO.md)는 통합 전 사실을 보존한다. `233b`의 원래 G1~G7은 10월 8일 완료됐고, 현재 후속 코드는 기본 폴더에 통합했다. formal KPI 미추정과 마지막 B14 후 새 전체80 미실행은 별도 한계다. 아래 목록은 기본 폴더의 9월 연구 자료다.

## 2026-09-14 연구 자료

- [Expert 대시보드 디자인과 운영](../../EXPERT_DASHBOARD_DESIGN_KO.md): 화이트·다크 선택과 저장, 모바일 화면, 정적 자산 재생성; 서버 31개·테마 4개 테스트 및 브라우저 검증 PASS
- [현재 목표](../../../../goal.md) · [GPT-6 Astra 인계 정리](../../GPT6_ASTRA_RESEARCH_HANDOFF_20260906_KO.md): 문제→아이디어→구현·측정 상태, 후보 회수·선택·NIL 진단 완료
- [연구 전용 로컬 LLM grounding 벤치마크 실행 계획](../../RESEARCH_ONLY_LOCAL_LLM_BENCHMARK_PLAN_20260905_KO.md): 첫 tranche 보존, `CANDIDATE_SELECTION_DIAGNOSTICS_COMPLETE`
- [후보 회수·선택 진단 실측 보고서](../../RESEARCH_CANDIDATE_SELECTION_DIAGNOSTICS_20260914_KO.md): baseline 16건·challenge 4건, 행별 trace·Recall@K·조건부 selection·실패 단계
- [연구 개선 TODO](../../TODO.md) · [개발 체크리스트](../../CHECKLIST.md) · [검증 결과](../../VERIFICATION_RESULTS.md)
- `DEFERRED_P0_AUDIT_TRACK`: 아래 P0 문서들은 production/publication/full-scan 전환용 감사 이력이며 현재 연구 blocker가 아니다.

## DEFERRED_P0_AUDIT_TRACK — P0 grounding production 전환 감사

- [P0 외부 provisioning blocked handoff](../../P0_EXTERNAL_PROVISIONING_BLOCKED_HANDOFF_20260904_KO.md): V3/V4 fixed store·actual package 3차 부재 확인, readiness `12/12`, endpoint `6/6`, Goal `BLOCKED_EXTERNAL_PROVISIONING_REQUIRED`
- [P0 lineage V2 다음 gate 전문가 재회의](../../P0_LINEAGE_V2_NEXT_GATE_EXPERT_COUNCIL_20260904_KO.md): current `FIXED_STORE / NO_GO` 재확인, owner-signed numerical policy interface 채택, 새 wrapper/V3 wiring 구현 보류와 외부 최소 패키지
- [P0 presented A-context lineage-capped full-frame V2 검토](../../P0_PRESENTED_A_CONTEXT_LINEAGE_CAPPED_FULL_FRAME_V2_REVIEW_20260904_KO.md): lineage 우선·context 후속 2단계 추첨, fixture `80→40→20`, focused `24/24`, P0 `1037/1037`, downstream wiring 0
- [P0 Windows owner policy V3→V4 전환과 readiness compiler V2 검토](../../P0_WINDOWS_OWNER_POLICY_V4_TRANSITION_AND_READINESS_COMPILER_V2_REVIEW_20260904_KO.md): 9-role parent replay, 21-role·9-file·3-watch observer, blocker compiler V2와 최종 red-team 보강; focused `40/40`, adjacent `149/149`, P0 `982/982`, current host `FIXED_STORE / NO_GO`
- [P0 seed8 권리·접근 준비도 검토](../../P0_SEED8_RIGHTS_ACCESS_READINESS_REVIEW_20260903_KO.md): 자동 capture 승인 0/8, Arca 조건부 후보 1건과 DC/FMK/Tanma permission-required 7건, timestamp·retention·privacy 후속 gate
- [P0 presented HTTP capture-intake V1 검토](../../P0_PRESENTED_HTTP_CAPTURE_INTAKE_V1_REVIEW_20260903_KO.md): seed 8개 HTTP envelope·decoded bytes locator·rights/retention candidate를 exact 결속하되 실제 capture/credit은 0
- [P0 Windows owner policy V4 epoch2 fixed-store 검토](../../P0_WINDOWS_OWNER_POLICY_V4_EPOCH2_FIXED_STORE_REVIEW_20260903_KO.md): zero-input held-handle observer, V4 signature math와 V3 structural replay 반대검토; current `FIXED_STORE / NO_GO`
- [P0 presented source seed candidate inventory V1 검토](../../P0_PRESENTED_SOURCE_SEED_CANDIDATE_INVENTORY_V1_REVIEW_20260903_KO.md): exact URL 8개·A/B 3/5·lineage family 4를 capture 전 후보로 봉인하고 actual/metric credit을 0으로 유지
- [P0 Windows owner policy V4 packet-V2 profile 검토](../../P0_WINDOWS_OWNER_POLICY_V4_PACKET_V2_PROFILE_REVIEW_20260903_KO.md): V3→packet V2 wire·pin·component 결속과 세 차례 red-team 수정, external authority는 NO-GO
- [P0 annotation packet V2 검토](../../P0_PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_REVIEW_20260903_KO.md): child15/member16 exact presented envelope, 통계·권한 0 경계와 component-only 채택
- [P0 packet V2 Windows fixed-directory 검토](../../P0_PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_WINDOWS_FIXED_DIRECTORY_REVIEW_20260903_KO.md): held-handle direct reader, identity/inventory/ADS/hardlink 공격과 bounded Windows 증거
- [P0 owner root preauthorization V2 검토](../../P0_OWNER_ROOT_PREAUTHORIZATION_V2_REVIEW_20260903_KO.md): canonical raw3, P-256 low-S CNG, ordered16/signed root와 manifest split-view 수정
- [P0 owner root preauthorization V2 supervisor 검토](../../P0_OWNER_ROOT_PREAUTHORIZATION_V2_SUPERVISOR_REVIEW_20260903_KO.md): exact child 재검증, lexical path/raw3/child output의 one-step seal과 최종 NO_GO
- [P0 presented A-context annotation-event V2 target precommit 검토](../../P0_PRESENTED_A_CONTEXT_ANNOTATION_EVENT_V2_TARGET_PRECOMMIT_REVIEW_20260903_KO.md): subject20→result-free target20, exact 15-raw composed parent, fixed response semantics·iid false와 red-team 6건 수정
- [P0 presented A-context annotation subject V2 precommit 검토](../../P0_PRESENTED_A_CONTEXT_ANNOTATION_SUBJECT_V2_PRECOMMIT_REVIEW_20260903_KO.md): source40·bridge40·A selected20에서 label-blind subject20을 봉인하고 독립 parent/red-team으로 구조적 계보를 재생한 component-only 채택
- [P0 presented A-context full frame V1 검토](../../P0_PRESENTED_A_CONTEXT_FULL_FRAME_V1_REVIEW_20260903_KO.md): pre-label A-context full census, profile 5×4 selected 20+exact surplus, 독립 parent와 actual/metric 0 경계
- [P0 이중맹검 외부 권한·dispatch 준비도 검토](../../P0_DUAL_BLIND_EXTERNAL_AUTHORITY_DISPATCH_READINESS_REVIEW_20260903_KO.md): current-host `FIXED_STORE / NO_GO`, immutable trust/mutable CAS 분리, CSPRNG task-ID 재결속부터 시작하는 dispatch 설계와 80→40→D→40 상태기계

- [P0 presented dual-blind review campaign precommit v1 검토](../../P0_PRESENTED_DUAL_BLIND_REVIEW_CAMPAIGN_PRECOMMIT_V1_REVIEW_20260903_KO.md): 결과 없는 40×3/120 사전등록, fixed guideline·private/public task 분리·canonical disagreement와 `D=null`; external dispatch/authority·metric은 NO-GO
- [P0 presented neutral review signature math v1 검토](../../P0_PRESENTED_NEUTRAL_REVIEW_SIGNATURE_MATH_V1_REVIEW_20260903_KO.md): 네 review 서명 역할·domain, canonical raw binding, P-256 low-S/CNG와 독립 parent replay; actual review authority·semantic·metric은 NO-GO
- [P0 presented neutral review accounting v1 검토](../../P0_PRESENTED_NEUTRAL_REVIEW_ACCOUNTING_V1_REVIEW_20260903_KO.md): 40입력 terminal review 회계, null semantics, 명시 분모, exact relation/gold span과 전문가 component-only 채택
- [P0 presented neutral batch exact-accounting v1 검토](../../P0_PRESENTED_BATCH_EXACT_ACCOUNTING_V1_REVIEW_20260903_KO.md): V2 40입력 exact ITT, non-error 독립 replay, `CORE_ERROR` presented-only 경계, unreviewed inventory와 전문가 component-only 채택
- [P0 full eligible sampling frame V2 검토](../../P0_FULL_ELIGIBLE_SAMPLING_FRAME_V2_REVIEW_20260903_KO.md): full census canonical seal, 고정 층·lineage·nominal fraction 독립 replay, 전문가 component-only 채택과 external owner/population/beacon NO-GO
- [P0 presented-capture neutral observation core 검토](../../P0_PRESENTED_CAPTURE_NEUTRAL_OBSERVATION_CORE_REVIEW_20260903_KO.md): COMMUNITY-only raw presented bytes grammar, 별도 parent replay, 통계 분모와 protocol 전 hard gate
- [P0 exact-envelope projector와 selection v2 검토](../../P0_EXACT_ENVELOPE_PROJECTOR_AND_SELECTION_V2_REVIEW_20260903_KO.md): explicit-definition 전체 문서 projection, parent replay, V1 archive/V2 source-first selection, 전문가 채택 및 actual parser 미구현 경계
- [로컬 LLM grounding 연구 개선 실행 계획](../../LOCAL_LLM_GROUNDING_RESEARCH_IMPROVEMENT_PLAN_20260901_KO.md): P0→P3 순서, 현 gate와 다음 단계

## Architecture V2 읽는 순서

1. [시스템 아키텍처](../../../ARCHITECTURE.md): 현재 공개 경로와 기본 OFF인 shadow·측정 계층
2. [Architecture V2 내부 재감사](../../ARCHITECTURE_V2_INTERNAL_REAUDIT_KO_20260713.md): 내부 통합 범위와 검증 근거
3. [Actual packet 입력 인벤토리](../../ACTUAL_PACKET_INPUT_INVENTORY_KO_20260712.md): 실제 효과 검증의 external blocker와 재개 조건
4. [검증 결과](../../VERIFICATION_RESULTS.md): 실행한 테스트와 증거 경계
5. [실제 입력 준비와 출시 판정 런북](../../LAUNCH_READINESS_RUNBOOK_KO.md): packet, preflight, fresh pair 순서
6. [LLM 파이프라인 개선 현황](../../LLM_PIPELINE_IMPROVEMENT_STATUS_KO_20260712.md): P2/P3/P4 계보와 정확도·비용 지표 설명
7. [2026-07-14 라이브 런 중간 감사](../../LIVE_PIPELINE_RUN_REVIEW_KO_20260714.md): 현재 104,502행 실행의 적용 경로, 검색 저하, 의미 blocker, bounded stop/repair 판정
8. [2026-07-14 Slang DB 오염 감사](../../SLANG_DB_POLLUTION_AUDIT_KO_20260714.md): 일반명사·비별칭 work delta, exact alias-pair write/seed fail-close, 중앙 승격 gate
9. [Goal 코드 산출물 정리 정책](../../CODE_ARTIFACT_CLEANUP_POLICY_KO.md): 일회성 smoke/builder 수명주기, Git allowlist 승격 기준, 2026-07-15 정리 결과
10. [`src/llm_batch` 소스 구조](../../SOURCE_LAYOUT_KO.md): 기능별 패키지 경계, import 이동 표, 한국어 주석·프롬프트 규칙
11. [동결 2,712건 회귀 cohort·bundle 계약](../../FROZEN_2712_REGRESSION_COHORTS_KO_20260716.md): exact cohort, 결정적 실행 bundle, paired transition 지표와 현재 게이트
12. [동결 2,712건 개선 BEFORE/AFTER](../../LIVE_RUN_2712_BEFORE_AFTER_REPORT_20260716_KO.md): P0a actual GO, P0b 격리 NO-GO·rollback, 검색·router·runtime·full-scan 분리 판정
13. [동결 2,712건 recovery sidecar 구현·검증](../../LIVE_RUN_2712_RECOVERY_SIDECAR_IMPLEMENTATION_REPORT_20260717_KO.md): 기존 공개 projection 불변, direct OCR review-only provenance, 남은 fresh/search/activation 게이트
14. [동결 2,712건 recovery sidecar 실제 묶음 검증](../../LIVE_RUN_2712_RECOVERY_SIDECAR_GROUPED_AB_REPORT_20260718_KO.md): 32행 양 arm 각 3회, 192 receipt·실제 WAL 비간섭, 개선·회귀·변동성, 자동 activation NO-GO
15. [동결 2,712건 남은 개선 BEFORE/SHADOW-AFTER](../../LIVE_RUN_2712_REMAINING_IMPROVEMENTS_BEFORE_SHADOW_AFTER_REPORT_20260718_KO.html): exact 2,712 paired receipt, 새 32행×3회 release-candidate 관측, router/P1/search/P2 분리 판정
16. [2,712건 개선 아키텍처 전문가 회의](../../ARCHITECTURE_IMPROVEMENT_EXPERT_COUNCIL_REPORT_20260719_KO.html): 실제 Terra/Opus/Luna 전문가 의견, 현 아키텍처·개선/미미/실패 분류, 기존 정답 보존 우선 P0/P1/P2 연구 순서
17. [계측 완결성 개선과 다음 아키텍처 계획](../../MEASUREMENT_USAGE_DRAIN_IMPROVEMENT_REPORT_20260720_KO.html): hard-cap 뒤 provider usage drain-only 구현, 과거 문제 2행 실제 canary 2/2 GO, 2,712행 replay, PublicationFinalizer·ObservationEnvelope 다음 계획
18. [구조·계측 후속 구현과 3회 묶음 회귀](../../NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_REPORT_20260722_KO.html): Synth quarantine·verifier shape guard·repeat-stop usage drain, 32행×양 arm×3회 runtime/measurement/semantic 분리 판정, 2,712행 최종 replay
19. [v7 qualified 최종 BEFORE/AFTER 보고서](../../NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_REPORT_20260723_KO.html): 사전 고정 semantic-blind replacement를 포함한 exact `192/192` 계측, cohort별 개선·미미·실패, 실제 호출·토큰·시간, 2,712 contract replay와 semantic/full-scan `NO-GO` 경계. [검증문](../../NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_VALIDATION_20260723_KO.md)과 [portable artifact](../../NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_ARTIFACT_20260723.json)를 함께 본다.
20. [로컬 LLM grounding 벤치마크 심층 연구](../../LOCAL_LLM_GROUNDING_BENCHMARK_RESEARCH_20260901_KO.md): MTEB/MIRACL/NoMIRACL/KLUE/EL·selective prediction 사례를 현 P3 계약에 대조하고, domain gold schema·stage metric·표본 수·정답 회수 개선 A/B와 승격 gate를 제안한다. 커뮤니티 축약어·은어·용어집 8개 source 감사와 `소설 매칭 / 커뮤니티 이해` 투트랙 silver-mining 설계를 포함한다. 새 actual run은 없으며 `FROZEN_ACTUAL NOT_READY`, semantic/full-scan `NO-GO`를 유지한다.
21. [전문가 회의 기반 grounding 연구 개선 실행 계획](../../LOCAL_LLM_GROUNDING_RESEARCH_IMPROVEMENT_PLAN_20260901_KO.md): 검색·평가, lexicon·데이터, MLOps 전문가의 독립 제안과 반례 회의를 합쳐 아키텍처 채택·component-only·보류·기각 목록, single-curator gold-lite, P0~P3 실행 gate, adapter·dependency·rollback 계약을 정리한다. P0 synthetic 40+20 계약은 focused `44 PASS`·인접 `192 PASS`, actual registry/B/event schema example은 focused `26 PASS`·인접 `237 PASS`, authority v2는 `28 PASS`, event-byte verifier는 `9 PASS`다. 후속 key-less packet은 A-context `18 PASS`, route `27 PASS`, packet `19 PASS`, focused `64 PASS`, 당시 selected adjacent `285 PASS`다. 실제 외부 40+20·parser runtime·owner policy는 미시작이다.
22. [2026-09-02 grounding 연구 개선 전문가 회의](../../LOCAL_LLM_GROUNDING_EXPERT_COUNCIL_20260902_KO.md): 유사 프로젝트의 최신 유지·license를 공식 출처로 재검증하고, truth/annotation/inference/publication 4축, 지표 분모, 299건 안전성 주장, P0~P3를 반대검토했다. top-label point/CI 분모와 actual bootstrap protocol을 policy v4·receipt SHA에 결속한 P0 측정 계약 patch는 focused `34 PASS`; broader는 선행 ledger SHA drift로 blocked이고 실제 semantic 지표는 계속 `NOT_ESTIMABLE`이다.
23. [P0 actual owner authority 입력 템플릿](../../P0_ACTUAL_AUTHORITY_INTAKE_TEMPLATE_KO.md): run root 밖의 trust anchor, capture·rights·sampling·annotation·journal·watch 정책과 pre-capture authorization/post-run attestation 범위를 owner가 확정하기 위한 입력 문서다. authority v2와 key-less packet structural contract는 구현됐지만 문서 자체·self-hash·supplied HMAC·controlled test packet은 승인이 아니다. 실제 외부 anchor/signature·trusted fixed directory/OS witness·40+20 전에는 authority와 P0 Exit을 열지 않는다.
24. [P0 key-less actual packet 구현·재검토](../../P0_KEYLESS_ACTUAL_PACKET_IMPLEMENTATION_REVIEW_20260902_KO.md): A-context/A-event, parser route, 13-child+manifest byte inventory와 최종 red-team 일곱 축 수정을 정리한다. focused `64 PASS`, selected adjacent `285 PASS`지만 controlled example/test bytes뿐이고 external actual·credited count는 `0/40`, `0/20`, gate는 `NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED`다.
25. [P0 authority raw·결합 supervisor 구현 및 전문가 재회의](../../P0_AUTHORITY_RAW_AND_COMBINED_SUPERVISOR_REVIEW_20260902_KO.md): authority 14 raw/event 직접 실행, packet·authority private immutable state, owner preauth부터 final bridge까지 고정 7단계를 정리한다. raw `19 PASS`, packet `20 PASS`, combined `12 PASS`, direct adjacent `75 PASS`, selected adjacent `385 PASS`지만 외부 trust/revocation/replay/time/root/OS witness와 실제 40+20은 없어 `EXTERNAL_TRUST_NO_GO`다.
26. [P0 external trust·Windows runtime witness 구현 및 재회의](../../P0_EXTERNAL_TRUST_AND_RUNTIME_WITNESS_REVIEW_20260902_KO.md): caller-keyless trust store, held-ledger `O_EXCL` nonce, one-shot trust/runtime state, QPC·parent/root watcher·USN·restricted current-thread probe와 7단계 supervisor 결합을 정리한다. 신규 `55 PASS`, direct adjacent `130 PASS`, selected adjacent `440 PASS`, 기존 상태 `6/6` 불변이지만 owner key/time/revocation·USN broker·parser job sandbox가 없어 authority/P0/production은 NO-GO다.
27. [P0 parser 별도 프로세스·Job component 구현 및 재회의](../../P0_PARSER_PROCESS_JOB_COMPONENT_REVIEW_20260902_KO.md): canonical capture-byte protocol, restricted primary token, Job assign-before-resume, 3-handle allowlist, bounded pipe/timeout과 부모 exact cross-binding을 정리한다. focused `20 PASS`, 전체 P0 `379 PASS`, 기존 상태 `6/6` 불변이지만 AppContainer/network/write deny·dependency closure·semantic parser가 없어 `PARSER_SANDBOX_NO_GO`다.
28. [P0 isolated pycache·source collision·directory watch 구현 검토](../../P0_PARSER_PROCESS_PYCACHE_SOURCE_OBSERVATION_REVIEW_20260902_KO.md): per-execution empty pycache, exact collision inventory, source/parent/cache watcher를 결합한 좁은 project-source load-candidate closure를 정리한다. focused `48/48 PASS`, 전체 P0 `407/407 PASS`, 기존 상태 `6/6` 불변이며 parser dependency/sandbox/actual/production은 NO-GO다.
29. [P0 외부 owner 비대칭 서명 수학 컴포넌트 검토](../../P0_EXTERNAL_OWNER_ASYMMETRIC_SIGNATURE_REVIEW_20260902_KO.md): Windows CNG ECDSA P-256/SHA-256과 RFC 5480 fingerprint, exact canonical preauthorization binding을 정리한다. focused `15/15`, adjacent `78/78`, 전체 P0 `422/422 PASS`, 기존 상태 `6/6` 불변이지만 caller-presented pin은 external provisioning/authority가 아니며 owner state/time/revocation/durable nonce/sandbox는 NO-GO다.
30. [P0 외부 owner one-shot `OWNER_STATE` 구현·재회의](../../P0_EXTERNAL_OWNER_ONESHOT_STATE_REVIEW_20260902_KO.md): same-call raw3 fresh validation, object-identity registry와 exact-once atomic consume을 정리한다. focused `25/25`, adjacent `91/91`, 전체 P0 `432/432 PASS`, 기존 상태 `6/6` 불변이지만 artifact replay/external provisioning/time/revocation/durable nonce/authority/sandbox는 NO-GO다.
31. [P0 external-trust state object-identity 강화·재회의](../../P0_EXTERNAL_TRUST_STATE_IDENTITY_HARDENING_REVIEW_20260902_KO.md): legacy seal-id exact clone key-consume 공격 재현과 `id+weakref` registry, atomic pop, recursive freeze, failure-burn 수정을 정리한다. focused `37/37`, direct adjacent `137/137`, 전체 P0 `439/439 PASS`, 기존 상태 `6/6` 불변이지만 caller-selected trust/time/revocation/durability/authority는 NO-GO다.
32. [P0 Windows external public-key pin candidate 구현·재회의](../../P0_WINDOWS_EXTERNAL_PUBLIC_KEY_PIN_CANDIDATE_REVIEW_20260902_KO.md): fixed-name held pin, effective-token ACL deny, signed packet/protected parent/category root handle과 same-call CNG/`OWNER_STATE`를 정리한다. focused `14/14`, adjacent `73/73`, 전체 P0 `453/453 PASS`, 기존 상태 `6/6` 불변이다. 정상 success는 controlled hold mock이고 실제 Windows는 current-user-owned/parent-overlap store의 fail-close라 external provisioning/authority는 NO-GO다.
33. [P0 Windows bootstrap policy 서명 수학 후보 구현·재회의](../../P0_WINDOWS_BOOTSTRAP_POLICY_SIGNATURE_CANDIDATE_REVIEW_20260902_KO.md): exact 9-field transcript와 held raw body SHA를 컴파일 공개키 후보로 CNG 검증하고 fixed-store child receipt 소비를 fail-close로 강화했다. focused `47/47`, Windows 인접 `117/117`, 전체 P0 `497/497 PASS`, 기존 상태 `6/6` 불변이다. 서명 수학만 PASS이며 owner-approved key·trusted code/provider deployment·rollback state·actual/production은 NO-GO다.
34. [P0 Windows owner deployment projection v2 구현·재회의](../../P0_WINDOWS_OWNER_DEPLOYMENT_PROJECTION_V2_REVIEW_20260902_KO.md): v1 호환을 보존한 별도 정책 v2에 native service·결정적 SID, verifier PE/resource·Authenticode, WDAC/UMCI와 loaded CNG provider identity를 결속했다. SID split을 재현·수정해 focused `34/34`, 인접 `56/56`, 전체 P0 `509/509 PASS`, 기존 상태 `6/6` 불변이다. presented contract만 PASS이며 live host/external provisioning/actual/production은 NO-GO다.
35. [P0 Windows owner provisioning preflight candidate 구현·재회의](../../P0_WINDOWS_OWNER_PROVISIONING_PREFLIGHT_CANDIDATE_REVIEW_20260902_KO.md): zero-input fixed-store/v2/SCM config/held-image candidate와 downgrade·receipt swap 방어를 구현했다. preflight `11/11`, direct adjacent `67/67`, 전체 P0 `520/520 PASS`이며 current host는 fixed store 단계 `NO_GO`다. native token/resource/WDAC/provider/time/signed observer/external provisioning은 미검증이다.
36. [P0 actual readiness blocker compiler 구현·재회의](../../P0_ACTUAL_READINESS_BLOCKER_COMPILER_REVIEW_20260903_KO.md): zero-input child exact validation, 중앙 DB/publication journal point-in-time projection, source selected unit 40(profile 10×4)·A sampling unit 20 분모와 red-team 수정을 정리한다. focused `22/22`, 전체 P0 `531/531`, endpoint `6/6` 불변이지만 항상 authority `NO_GO`, credited `0/40·0/20`이다.
37. [P0 Windows native observer v3 component 구현·재회의](../../P0_WINDOWS_NATIVE_OBSERVER_V3_COMPONENT_REVIEW_20260903_KO.md): v1/v2 receipt 의미를 보존한 v3 component와 분리 key 역할, 재현 가능한 native PE, current-host negative 관측을 정리한다. 전체 P0 `552/552`이며 component-only `NO_GO`다.
38. [P0 Windows owner policy v3 successor preflight 구현·최종 재회의](../../P0_WINDOWS_OWNER_POLICY_V3_SUCCESSOR_PREFLIGHT_REVIEW_20260903_KO.md): 별도 v3-only 상태기계, raw signature private handoff, negative/no-explicit-negative positive rejection을 정리한다. 전체 P0 `564/564`, endpoint `6/6` 불변이며 current host `FIXED_STORE / NO_GO`, actual credit `0/40·0/20`이다.
39. [P0 Windows owner policy v3 CNG 재실행 구현·재회의](../../P0_WINDOWS_OWNER_POLICY_V3_CNG_REEXECUTION_REVIEW_20260903_KO.md): same-snapshot raw signature CNG 재실행, fresh receipt exact 계약·producer equality, red-team truth-table 보정을 정리한다. 관련 `48/48`, 전체 P0 `568/568`, endpoint `6/6` 불변이며 current receipt v2 `da914d27…a1b1ad`, actual credit `0/40·0/20`이다.
40. [P0 Windows owner policy V3→V4 전환과 readiness compiler V2 검토](../../P0_WINDOWS_OWNER_POLICY_V4_TRANSITION_AND_READINESS_COMPILER_V2_REVIEW_20260904_KO.md): supplied V4 replay·V3 10-field pin·signed/live identity를 검증하는 parent, 21-role·9-file·3-watch observer와 always-NO_GO compiler V2를 정리한다. stable-digest 1,000회, 각 2회 결정성, focused `40/40`, adjacent `149/149`, 전체 P0 `982/982`; current host `FIXED_STORE / NO_GO`, actual `0/40·0/20`이다.

현재 상태는 범위별로 다르다.

| 범위 | 상태 | 설명 |
| --- | --- | --- |
| 아키텍처 통합 | `COMPLETE_SAFE_TERMINAL / ARCHITECTURE_V2_INTEGRATED` | Stage runtime adapter, DecisionLedgerV2 dual-write/rollback, CandidateSet/NIL, typed confidence 계약과 reader, packet 도구의 내부 통합을 닫았다. |
| 실제 효과·M2 | `ACTUAL_BLOCKED_HANDOFF / NOT_COMPLETE` | 신규 actual policy v4, source-backed DEV/CAL/FROZEN, 10+6 packet, fresh pair가 없어 동일 external blocker가 3회 확인됐다. |
| 실제 지표 | `null / NOT_ESTIMABLE` | 정확도·비용·지연 개선률을 주장할 actual artifact가 없다. |
| 운영 승인 | `REVIEW-LOCKED / full_scan_approval=false` | cheap routing과 전체 스캔은 열지 않는다. |
| 2026-07-14 라이브 런 | `RUNNING_DEGRADED / NO-GO` | 저장 무결성은 진행 중 정합이지만 검색 저하와 의미·비용 blocker 때문에 현재 full run 계속은 권고하지 않는다. |
| current Slang work artifact | `NO-GO / QUARANTINE` | 중앙 DB는 미변경이며 patched fresh canary 전에는 work artifact를 승격하지 않는다. |
| 동결 2,712건 targeted 개선 | `P0a GO / P0b ROLLED_BACK` | 3회 exact consensus에서 P0a systematic regression 0, P0b regression 1·신규 unsafe 1. search/router/P1/P2/full scan은 미승인이다. |
| 동결 2,712건 recovery sidecar | `DETERMINISTIC GO / REVIEW-ONLY / SEMANTIC NO-GO` | 공개 WAL·192 receipt 비간섭, proposal `68`·provenance 100%. 실제 32행 3회에서 source 반복 회귀 2행, search/router/measurement NO-GO라 자동 publish와 P1/P2는 미승인이다. |
| 동결 2,712건 남은 개선 | `INTEGRITY GO / SHADOW-AFTER / AUTO-ACTIVATION NO-GO` | router/P1 receipt `2,712/2,712`, public drift `0`; 새 grouped majority `17→18`이지만 measurement `4/6`, router recall `74.2%`, normal false-review `20.0%`, search degraded로 P2 188건은 미실행이다. |
| 2026-07-19 아키텍처 회의 | `P0 RESEARCH READY / IMPLEMENTATION NOT STARTED` | 권고안은 byte-equivalent `PublicationFinalizer`, 공통 `ObservationEnvelope`, shadow intervention simulator다. 새 Pro 답변은 recovery lock으로 미확보했고 자동 activation/full scan은 계속 NO-GO다. |
| 2026-07-20 계측 P0 | `TARGETED MEASUREMENT GO / SEMANTIC NO-GO` | HTTP vLLM hard-cap usage drain-only를 구현했다. 과거 unlinked 2행의 새 canary는 measurement `2/2 GO`, provider usage `27/27`, public drift `0`, 2,712 deterministic normal→abnormal `0`이다. 기존 32행×3회 전체 재실행·semantic/search/router/P2는 미승인이고 `full_scan_approval=false`다. |
| 2026-07-22 구조·계측 후속 | `RUNTIME 6/6 GO / MEASUREMENT 4/6 NO-GO / SEMANTIC NO-GO` | v6 192행은 runtime 실패 0·public WAL 비간섭이지만 usage link `190/192`, majority compliant `19→17`, systematic regression 2다. Synth quarantine·shape guard·repeat-stop drain은 focused 31·인접 263·실 canary·2,712 replay를 통과했으나 자동 activation과 full scan은 미승인이다. |
| 2026-09-01 grounding benchmark·community silver 연구 | `RESEARCH COMPLETE / EXTRACTOR NOT_IMPLEMENTED / PRODUCTION NO-GO` | 공개 benchmark는 component smoke로만 쓴다. 커뮤니티 목록은 `work_alias_registry`와 `community_lexicon`의 silver seed이며 gold나 중앙 DB write가 아니다. 실제 승인은 source-backed DEV/CAL/FROZEN과 문맥 gold가 필요하고, P3 headline은 계속 `null/NOT_EVALUABLE`이다. |
| 2026-09-01~02 전문가 회의 기반 연구 개선 계획 | `ARCHITECTURE_PLAN_ADOPTED / P0_MEASUREMENT_CONTRACT_PATCHED_FOCUSED_34_PASS / BROADER_BLOCKED_PREEXISTING_LEDGER_SHA / ACTUAL_POLICY_PENDING / DEEP_RESEARCH_BLOCKED / FROZEN_ACTUAL_NOT_RUN` | 규칙 parser·hybrid retrieval·immutable-ID reranker·4축 decision·temporal snapshot을 단계별 shadow로 채택했다. point/CI 분모와 actual bootstrap v4 fail-close·fixture 성공 경로를 focused 검증했다. 첫 probe 미제출 확인은 받았지만 하네스 settlement가 막혀 새 ChatGPT 제출은 하지 않는다. |
| 2026-09-02 P0 source 합성 계약 | `GO_P0_CONTRACT_FIXTURE_ONLY / FOCUSED_44_PASS / ADJACENT_192_PASS / ACTUAL_SOURCE_CONTEXT_NOT_STARTED / p0_phase_exit=false` | strict source/claim·lineage·4축·hash/receipt·publication source-to-work·profile/parser·claim kind/direction·status/reason gate를 구현했다. 기존 중앙 DB 1개+publication journal 5개는 validator 전후 불변이다. actual/B/parser/runtime/production 증거는 아니다. |
| 2026-09-02 actual P0 schema foundation | `PASS_ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY / FOCUSED_26_PASS / ADJACENT_237_PASS / gate_status=ACTUAL_NO_GO / p0_phase_exit=false` | 독립 source registry·capture/payload exact span·temporal lineage·권리 5축, B sense 의미/4축·candidate/evidence cutoff·sensitive/temporal, immutable annotation subject와 event hash-chain, claim-set/decision payload 및 orphan 차단을 구현했다. 실제 40+20과 각 authority·runtime 전체 비간섭은 아직 없다. |
| 2026-09-02 actual owner authority v2 | `PASS_ACTUAL_AUTHORITY_SCHEMA_EXAMPLE_ONLY / AUTHORITY_28_PASS / EVENT_BYTES_9_PASS / P0_COMBINED_107_PASS / SELECTED_ADJACENT_221_PASS / NO_GO_ACTUAL_P0_NOT_STARTED` | 14-file v2의 preauth→manifest→final-attestation DAG와 byte-exact event prefix/head reconstruction을 구현했다. key-less 구조 계약은 후속 완료됐지만 실제 signature/trusted fixed directory/OS witness·외부 actual 40+20이 없어 authority·credited count·P0 exit은 닫혀 있다. |
| 2026-09-02 key-less actual packet | `STRUCTURAL_CONTRACT_IMPLEMENTED / FOCUSED_64_PASS / SELECTED_ADJACENT_285_PASS / EXAMPLE_BYTES_ONLY / NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED` | A-context/A-event, pre-capture plan, label-blind seal, exact-one route, 13-child+manifest 재계산과 red-team 일곱 축 우회를 닫았다. 외부 actual·credited 40+20, owner/OS/handle/journal/watch/runtime authority는 없다. |
| 2026-09-02 authority raw·결합 supervisor | `DIRECT_LOCAL_AUTHORITY_BRIDGE_PASS / AUTHORITY_RAW_19_PASS / PACKET_SUPERVISOR_20_PASS / COMBINED_SUPERVISOR_12_PASS / DIRECT_ADJACENT_75_PASS / SELECTED_ADJACENT_385_PASS / EXTERNAL_TRUST_NO_GO` | authority 14 raw/event와 packet/authority private state, parser byte exact binding, 고정 7단계 direct invocation을 구현했다. controlled 40+20/Windows e2e는 test-only이고 actual·credited count는 `0/40`, `0/20`; external trust와 P0 Exit은 false다. |
| 2026-09-02 external trust·runtime witness | `EXTERNAL_STORE_KEY_AND_NONCE_EXECUTED / BOUNDED_WINDOWS_WITNESS_COMPONENT_ONLY / NEW_55_PASS / DIRECT_ADJACENT_130_PASS / SELECTED_ADJACENT_440_PASS / EXTERNAL_OWNER_TIME_REVOCATION_NO_GO / PARSER_JOB_RUNTIME_NO_GO` | exact store·atomic nonce·one-shot states와 QPC/root-parent watch/USN/probe를 결합했다. 현 USN은 error 5×6, process/job write deny와 actual 40+20은 없어 P0 Exit·production/full scan은 false다. |
| 2026-09-02 parser process·Job component | `CAPTURE_HASH_PROTOCOL_PASS / JOB_COMPONENT_OBSERVED / FOCUSED_20_PASS / ALL_P0_379_PASS / PARSER_SANDBOX_NO_GO` | restricted primary token과 Job/3-handle/timeout/cross-binding component는 실제 Windows E2E를 통과했다. AppContainer/network/root deny·dependency closure·semantic parser가 없어 actual·credited `0/40`, `0/20`, P0/production/full scan은 false다. |
| 2026-09-02 isolated pycache·source observation | `ADOPT_BOUNDED_PROJECT_SOURCE_LOAD_CANDIDATE_CLOSURE_COMPONENT_ONLY / PARSER_DEPENDENCY_CLOSURE_NO_GO / PARSER_SANDBOX_NO_GO / FOCUSED_48_PASS / ALL_P0_407_PASS` | local held `LocalAppData` anchor와 MSIX redirection 관측, empty per-run cache, collision inventory, 세 watcher의 좁은 component closure다. runtime/stdlib/native/authority/semantic/actual gate는 false이며 actual `0/40`, `0/20`, metrics `NOT_ESTIMABLE`, 품질 `REVIEW_LOCKED`다. |
| 2026-09-02 external owner asymmetric signature math | `ASYMMETRIC_SIGNATURE_MATH_PASS / PRESENTED_PIN_ONLY / EXTERNAL_PROVISIONING_NO_GO / OWNER_STATE_NOT_YET_BOUND / ALL_P0_422_PASS` | CNG ECDSA P-256/SHA-256, RFC 5480 pin fingerprint와 exact preauth 결속만 채택한다. attacker 전체 대체도 self-consistent math는 true일 수 있어 authority·trusted time/revocation/durable nonce·sandbox·actual은 false다. |
| 2026-09-02 Windows external public-key pin candidate | `ACL_BOUND_PIN_CANDIDATE_CONTRACT_PASS / CONTROLLED_SUCCESS_ONLY / ACTUAL_EXTERNAL_PROVISIONING_NO_GO / ALL_P0_453_PASS` | fixed-name held pin, effective-token mutation deny, signed packet/protected parent/category handle과 same-call CNG/`OWNER_STATE`를 채택한다. exact owner SID/ACE policy와 actual external positive store/key가 없어 actual `0/40`, `0/20`, P0/production/full scan은 false다. |
| 2026-09-02 Windows owner deployment projection v2 | `OWNER_DEPLOYMENT_PROJECTION_V2_CONTRACT_PASS_HOST_AND_EXTERNAL_PROVISIONING_NO_GO / FOCUSED_34_PASS / ADJACENT_56_PASS / ALL_P0_509_PASS` | v1은 호환용으로 보존하고 future authority 후보만 v2 body/signature/anchor/receipt와 fixed service SID·PE/resource·Authenticode·WDAC/UMCI·loaded provider projection을 요구한다. live host와 external signed provisioning이 없어 actual `0/40`, `0/20`, P0/production/full scan은 false다. |
| 2026-09-02 Windows owner provisioning preflight candidate | `HOST_PREFLIGHT_CANDIDATE_IMPLEMENTED / CURRENT_HOST_FIXED_STORE_NO_GO / DIRECT_67_PASS / ALL_P0_520_PASS` | fixed v2 store 통과 뒤에만 direct SCM config와 held image identity를 관측한다. current host receipt는 `NO_GO`; native token/resource/Authenticode/WDAC/provider/time/signed observer/external provisioning과 actual `40+20`은 없다. |
| 2026-09-03 actual readiness blocker compiler | `ADOPT_BLOCKER_ONLY / ACTUAL_READINESS_AUTHORITY_NO_GO / FOCUSED_22_PASS / ALL_P0_531_PASS` | same-call preflight exact validation과 point-in-time endpoint `6/6` 일치를 기록한다. source selected unit/A sampling unit credited `0/40·0/20`; transient/continuous/runtime 비간섭과 P0/production/full scan은 false다. |
| 2026-09-03 Windows native observer v3 component | `ADOPT_COMPONENT_ONLY / BOUNDED_NATIVE_OBSERVER_CANDIDATE_NO_GO / ALL_P0_552_PASS` | v3 presented transcript와 native diagnostic은 external trust·freshness·replay·authority를 증명하지 않으며 actual `0/40·0/20`이다. |
| 2026-09-03 Windows owner policy v3 successor | `ADOPT_REJECTION_ONLY / POSITIVE_REJECTED / ALL_P0_564_PASS` | v3-only preflight와 raw signature binding은 receipt reseal을 닫지만 current host는 `FIXED_STORE / NO_GO`; positive/P0/production/full scan은 false다. |
| 2026-09-03 Windows owner policy v3 CNG 재실행 | `ADOPT_SAME_PROCESS_CNG_REEXECUTION_REJECTION_ONLY / ALL_P0_568_PASS` | producer-only coordinated low-S reseal은 실제 CNG에서 거부한다. 동일 프로세스 두 실행 일관성일 뿐 external code/provider/owner trust는 아니며 actual `0/40·0/20`이다. |

### 현재 계약을 읽을 때의 구분

- `confidence_percentage`: 행별 보정 확률. 전체 정확도가 아니다.
- `ARCHITECTURE_V2_INTEGRATED`: 내부 코드·rollback·비간섭·clean-export 완료. 실제 성능 승인이 아니다.
- `WAITING_EXTERNAL_INPUT`: external blocker를 처음 확인한 역사 상태다. 최신 actual lane은 `ACTUAL_BLOCKED_HANDOFF`다.
- `FULL_EXPERT_REQUIRED`/`CHEAP_RULE_ELIGIBLE`: shadow 관측 값이며 운영 라우팅 허가가 아니다.
- 실제 run은 `--parallel 16`, dashboard ON을 기본으로 하고 manifest의 requested/effective parallel을 함께 확인한다.

이 디렉터리는 개발 TODO, 기능 개선, 런 리뷰, 체크리스트, 검증 결과를 추적하는 문서 허브다. 최신 독자용 정본은 위 1~35번이며, `LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`는 P3/P4 v14 시점의 역사적 설명으로만 사용한다.

## 이전 개선 상태 — 2026-07-12 P4 선택적 비용 라우팅 그림자 v3

- 기능: 기존 공개 판정을 바꾸지 않고 각 행이 전체 전문가 경로를 요구하는지 그림자로 관측
- Golden18: `FULL_EXPERT_REQUIRED 18 / CHEAP_RULE_ELIGIBLE 0`, 공개 결과·CandidateSet `18/18` 불변
- 실제 KPI: safe auto coverage, calls/post, call avoidance, after wall time 모두 `null/NOT_ESTIMABLE`; escalation `1.0`은 shadow 경로 분포일 뿐 절감률이 아님
- 진단 로그: expert prompt `191`, VLM `14`, token `2,269,227`; canonical 행별 비용 영수증이 아니므로 KPI 승격 금지
- 합성 검증: 호출 산술 `16→8`, 50% 회피는 `SYNTHETIC_CONTRACT_ONLY_NOT_ACTUAL_SAVINGS`
- 공격 검증: `20/20`, false cheap `0`; 구현 집합 축소+재해시 공격 차단; P4 집중 `30/30`, publication `33/33`
- 현재와의 차이: typed expert call event·독립 reader·P3 actual readback 계산 기반은 이후 구현됐다. 다만 실제 artifact와 fresh paired runtime이 없어 actual cheap route는 계속 fail-close한다.
- 판정: `GO_P4_SHADOW_CONTRACT_FOUNDATION_ONLY / NOT_RUN / REVIEW-LOCKED / full_scan_approval=false / ACTIVE_NOT_COMPLETE`
- 기능 중심 한국어 보고서: `loop_reports/LOOP_P4_SELECTIVE_COMPUTE_SHADOW_20260712.md`
- 정본 실행 명세·비교: `../../out/selective_compute_shadow_harness_20260712/v3/run_spec.json`, `comparison.md`

## 이전 개선 상태 — 2026-07-11 P3 정확도 퍼센트 계약 기반 v4(역사)

- 기능: 후보 작품 ID들과 `작품 없음(NIL)`에 확률을 나누되, 근거 없는 숫자·분할 누수·저장본 위조는 숫자를 만들기 전에 차단
- Golden18: 생산 완료·분리 평가 자료가 없어 실제 headline 지표 전부 `null`, 후보 재현율 `NOT_EVALUABLE`
- 개선 전·후: 무결속 보정 숫자 claim `1→0`; 기존 공개 결과 `18/18` 불변
- 합성 검증: 공격 `20/20`, false GO `0`; 합성 4행 수치는 수식 방향 시험이며 실제 모델 성능 아님
- 회귀: 계약 `15`, 하네스 `5`, 합계 `20 tests OK`; Sol 시간차 Mapping·검색 blocker·보고서 승인 위조 3건 재공격 차단
- 현재와의 차이: 파일 바이트·producer coverage·prediction payload 재판독과 그룹 bootstrap 계산 기반은 P3 v7 이후 구현됐다. 실제 DEV/CAL/FROZEN 자료·실행·배포 구간 판정은 여전히 없다.
- 판정: `GO_P3_CONTRACT_FOUNDATION_ONLY / NOT_RUN / REVIEW-LOCKED / full_scan_approval=false / ACTIVE_NOT_COMPLETE`
- 기능 중심 한국어 보고서: `loop_reports/LOOP_P3_CALIBRATION_CONTRACT_FOUNDATION_20260711.md`
- 재결속 정본 비교: `../../out/candidate_set_calibration_shadow_harness_20260711/v4/comparison.md`

## 이전 개선 상태 — 2026-07-11 P2 최종 공개 판정 한 번만 기록 v4

- 기능: 같은 실행 범위·같은 게시글은 첫 정상 공개 판정과 결과 행을 WAL에 한 번만 확정하고 재시도는 그 정본을 재사용
- 막는 문제: 재시도 덮어쓰기, 다른 입력·설정·코드 범위 혼합, `HOLD/ERROR_HOLD` 중첩 필드의 작품명·주소 누출, 저장 중 끊긴 마지막 줄의 오인
- Golden18 저장본: 유효 판정 영수증 `0→18`, 신규 기록 `18`, 재시작 무쓰기 `18`, 공개 결과·전체 행 `18/18` 불변
- 공격 검증: 합성 `21/21`, false GO `0`; 16개 동시 기록자는 신규 commit `1`, WAL line `1`
- 검증: P2 집중 묶음 `169 tests OK`, publication `33`, recovery `36`
- 증거 분리: 저장본·합성 `GO`; 실제 runtime `NOT_RUN`; 의미 품질 `REVIEW-LOCKED`; production `full_scan_approval=false`
- 기능 중심 한국어 보고서: `loop_reports/LOOP_P2_PUBLICATION_EXACT_ONCE_20260711.md`
- 재결속 정본 비교: `../../out/publication_exact_once_harness_20260711/v4/comparison.md`

## 최신 개선 상태 — 2026-07-11 P1 상류 검색·fetch 완료 증명 v6

- 기능: 실행 전에 고정한 query/search/fetch 계획과 실제 작업 영수증을 대조해 후보 생성 앞단이 정해 둔 범위를 빠짐없이 수행했는지 증명
- `COMPLETE` 의미: 계획한 bounded 범위를 손실 없이 끝냈다는 뜻이며 웹 전체 후보를 모두 열거했다는 뜻은 아님
- 합성 결과: 사전 고정 정상 search+fetch `COMPLETE 1`, cache provenance 미결합·영수증 누락·저하/오류·조기 종료 `UNKNOWN 4`, raw `11→10` 손실 `TRUNCATED 1`, 거짓 `COMPLETE 0`
- 실제 Golden18: 새 producer receipt가 없는 과거 저장본이므로 `UNKNOWN`, 후보 재현율 `NOT_EVALUABLE`
- 공개 비간섭: 작품명·주소·판정 `18/18` 불변, 확률 전부 `null`
- fail-close: explicit completion 누락, 부분 엔진 실패, generic error/blocked/malformed, fetch fallback, posthoc direct plan, required producer 축소를 완료로 인정하지 않음
- 검증: P1 v8, completeness v6, 집중 `62/62`, 영향 범위 `529/529 tests OK`
- 실제 runtime: `NOT_RUN`; 배선 상태 `IMPLEMENTED_NOT_RUNTIME_VALIDATED`; 의미 품질 `REVIEW-LOCKED`; production `full_scan_approval=false`
- 기능 중심 보고서: `loop_reports/LOOP_P1_PRODUCER_COMPLETION_PROOF_20260711.md`
- P1 구조 정본: `../../out/candidate_set_nil_shadow_harness_20260711/v8/comparison.md`
- 완료 증명 정본: `../../out/candidate_generation_completeness_harness_20260711/v6/comparison.md`

## 이전 개선 상태 — 2026-07-11 P1 후보 생성 잘림·전문가 단계 영수증 v4

- 기능: 작품 후보 여러 개 + `NIL` 사건을 보존하고, 제목 순위 cap 6·serializer cap 24·전문가 후보 상태 cap 7곳의 잘림을 서로 다른 장부/진단 영수증으로 기록
- Golden18: post_id·후보 무결성·공개 계약 불변 `18/18 GO`
- 라벨 원장: 작품 후보 `9`, NIL `6`, 단일 정답 미지정 `3`
- 구조 검사: 작품 후보 정답의 사건 후보 내 관측 `9/9`, NIL 정답 원장 행의 공통 NIL 선택지 `6/6`; 정확도 검사가 아님
- 후보 구성: 작품 사건 `34`, 비사건 약칭 `13`, 후반 관측 표면 `6`
- 확률: 모두 `null`, `NOT_AVAILABLE_UNCALIBRATED`
- 후보 생성: 제목 고유 7개 `TRUNCATED 7→6`, serializer 고유 25개 `TRUNCATED 25→24`; cap 이하·중복 제거 cap 이하는 `UNKNOWN`, `COMPLETE` 생성 금지
- 전문가 단계: Gatekeeper1·Decoder1·Verifier2·Arbiter3 cap+1 `7/7 TRUNCATED`, 경계 오탐 `0`, 유지 출력 `9/9`; CandidateSet·확률·공개 판정에는 미합성
- 후보 목록 재현율: cap 6/24의 로컬 잘림은 보이지만 상류 producer 완전성이 미증명이라 `NOT_EVALUABLE`
- 영향 회귀: 집중 `71 tests OK`, candidate generation/P1 harness/promotion/retrieval/P0 harness/publication/serializer/Decoder/Arbiter 묶음 `518 tests OK`; broader 554의 선행 red 2는 별도 부채
- 실제 runtime: `NOT_RUN`; 의미 품질 `REVIEW-LOCKED`; production `full_scan_approval=false`
- 기능 중심 설명: `LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`
- P1 구조 정본: `../../out/candidate_set_nil_shadow_harness_20260711/v6/comparison.md`
- 잘림 탐지 정본: `../../out/candidate_generation_completeness_harness_20260711/v4/comparison.md`
- 루프 보고서: `loop_reports/LOOP_P1_CANDIDATE_GENERATION_COMPLETENESS_20260711.md`

## 최신 개선 상태 — 2026-07-11 P0 검색 미복구 공개 차단 하네스 v5

- 게이트 기능: typed `RetrievalState` 구현, 기본 no-op, live 검색 상태 배선은 `NOT_WIRED`
- 실제 저장본 정적 비교: baseline gate replay `5/5`, unsafe publish `1→0`, candidate missing `0`
- 합성 계약 시험: unsafe publish `5→0`, correct publish `2→2`; 실제 저장본 수치와 합산하지 않음
- 검색 근거: hard blocker `5→5`, `NO-GO`
- 실제 개선 후 runtime: `NOT_RUN_STATIC_PROJECTION / BLOCKED_ACTIVE_PRODUCTION_RUN`
- 정확도 퍼센트: `NOT_AVAILABLE_UNCALIBRATED`
- 결정적 회귀 시험: `275 tests OK`
- 정본 실행 명세: `../../out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/run_spec.json`
- 보고서: `loop_reports/LOOP_P0_RETRIEVAL_FAILCLOSE_HARNESS_20260711.md`
- 목표 프롬프트: `GOAL_PIPELINE_IMPROVEMENT_TESTDRIVEN_20260711.md`
- 의미 품질 `REVIEW-LOCKED`, production `full_scan_approval=false`

## 최신 상태 — 2026-07-11 Loop643 limit handoff

- 판정: `LIMIT_REACHED_HANDOFF`
- Golden18: run `20260711_062543_156139`, runtime `18/18/18/0/0`, semantic `18/18 PASS`
- search: required hard blocker `5`, terminal `4`, unreviewed `0`
- N=5/fresh375: `NOT_RUN_AFTER_GOLDEN_HARD_FAIL`
- production `full_scan_approval=false`
- 요약: `loop_reports/LOOP_643_REPORT_20260711.md`
- convergence: `loop643_convergence_state.json/.md`
- resume: `loop643_limit_reached_handoff_20260711_071812.json`

## 문서 맵

- `TODO.md`: 개발/기능개선 TODO 전체 색인
- `DEV_TODO.md`: 코드, 인프라, 테스트, 도구 중심 개발 TODO
- `FEATURE_IMPROVEMENT_TODO.md`: 검색 품질, slang DB, 대시보드 UX 같은 기능 개선 TODO
- `CHECKLIST.md`: 변경 전/중/후에 반드시 확인할 공통 체크리스트
- `OPERATION_QUALITY_CHECKLIST.md`: 대량 런 품질 승인용 GO/REVIEW/NO-GO 게이트
- `SCAN_RESULT_REVIEW_GUIDE.md`: scan result directory를 받았을 때의 리뷰 모드, 증거 등급, 실패 taxonomy, action queue 지침
- `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md`: 자동 감사와 분리된 자연어 판정 품질 리뷰 루프, 라벨, packet 산출물 규격
- `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`: 수백만 건 운영을 위한 smoke/canary/risk/validation 샘플 규모 기준
- `LLM_JUDGMENT_REVIEW.md`: LLM/전문가가 결과를 직접 읽고 판단하는 정성 리뷰 프로토콜
- `EXPERT_ORCHESTRATION_LIMITATIONS.md`: 전문가 오케스트레이션, 후처리 rescue, 프롬프트 계약 한계와 개선 우선순위
- `GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`: regression-safe grounding loop의 현재 운영 계약과 완료 조건
- `GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`: Loop176 이후 아키텍처 보강을 active goal에 편입한 최신 실행 계약
- `ARCHITECTURE_PROMOTION_GATE_MIGRATION.md`: 기존 title promotion/rescue 구조와 추가 `GroundingState`/`PromotionDecision`/`can_publish_title` 구조를 Mermaid로 비교한 migration 설계
- `REGRESSION_SAFE_GROUNDING_BOUNDED_CONVERGENCE_PROTOCOL.md`: fingerprint, progress vector, 실행 예산, terminal ledger, plateau, 최종 상태 계약
- `loop643_convergence_state.json/.md`: Loop643 새 fingerprint Golden exact-once, search hard blocker, terminal consensus, limit handoff state
- `loop_reports/LOOP_643_REPORT_20260711.md`: multi-work subject conflict 구현, exact-once Golden, PLATEAU_AUDIT_ONLY 최종 보고
- `loop641_convergence_state.json/.md`: Loop640 immutable recovery와 Loop641 residual continuation의 fingerprint/progress/blocker state
- `loop641_gate_tool_independent_audit.json/.md`: merge/adjudication/search/always-on fail-open 재현과 actual artifact/hash/readback 보강, focused 86 tests 근거
- `loop_reports/LOOP_641_REPORT_20260710.md`: recovered75/residual300 실행과 deterministic merge/adjudication/search gate 도구 보고
- `LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md`: 처음 읽는 사람용 0~5장과 개발자용 기술 부록을 분리한 최신 아키텍처 보고서. 가상의 다작품·검색 실패 글이 현재와 개선 구조에서 어떻게 처리되는지 보여 주고, 개선 기능 9개를 `하는 일 / 예시 / 기대 효과` 순서로 한국어 설명
- `GOAL_PIPELINE_IMPROVEMENT_TESTDRIVEN_20260711.md`: 동일 입력의 개선 전·후 비교를 반복하는 복사·붙여넣기용 목표 프롬프트와 P0~P5 상태
- `loop_reports/LOOP_P0_RETRIEVAL_FAILCLOSE_HARNESS_20260711.md`: 실제 Loop643 저장본 정적 비교와 합성 계약 시험을 분리한 P0 v5 보고서
- `loop_reports/LOOP_P1_PRODUCER_COMPLETION_PROOF_20260711.md`: query/search/fetch 계획·영수증의 bounded 완료 증명, 합성 `1/4/1/false0`, 실제 runtime·확률·승인 경계를 한국어로 설명한 P1 v6 보고서
- `loop_reports/LOOP_P3_CALIBRATION_CONTRACT_FOUNDATION_20260711.md`: 정확도 퍼센트의 분자·분모, readiness v2, 무쓰기 actual preflight, source/replay 구조 결속, 6개 paired CI 정책 판정과 실제 자료 부재를 설명한 P3 v18 보고서
- `loop_reports/LOOP_P3_P4_DENOMINATOR_EXECUTION_ENVELOPE_20260712.md`: 2026-07-12의 P3 policy v3 분모 hash-binding 역사와 현재 v4 supersession, P4 source-bound batch execution envelope·p50/p95 paired CI, reference-copy 제외를 설명한다.
- `P3_ACTUAL_POLICY_DECISION_KO_20260712.md`: 실제 결과를 보기 전에 고정해야 할 정확도·위험·비열화 숫자의 A/B 선택안, 표본 산식, 미판정 3행 유지 근거
- `loop_reports/LOOP_P4_SELECTIVE_COMPUTE_SHADOW_20260712.md`: 선택적 비용 라우팅, parent/label lineage, 물리 호출 독립 재판독, recovered-arm witness, paired source replay, reference-copy 비실측 경계와 다음 actual runtime 조건을 설명한 P4 v19 보고서
- `LLM_IMPROVEMENT_ARCHITECTURE_REVIEW_20260710.md`: Claude 공동설계 provenance, 현재 shared gate의 단일-writer/확률·NIL/투영-런타임 한계, Loop640 partial drift 증거, 단계별 개선·검증 체크리스트
- `CODEX_KICKOFF_SURVEY_AND_LOOP.md`: Codex 세션 시작 시 현재 상태/다음 loop를 재구성하는 kickoff 절차
- `FULL_POST_JUDGE_RUNBOOK.md`: full-post judge 실행, 재시작, 산출물 계약
- `COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`: completed779 remaining queue를 subagent/model/tool fan-out으로 반복 개선하는 copy-paste goal prompt
- `loop_reports/`: loop별 실행 보고서와 gate 판정 기록
- `QUALITATIVE_REVIEW_20260426.md`: 20k run 300건 전문가 정성 리뷰 결과
- `IMPROVEMENT_REGISTER.md`: 개선안의 문제 정의, 결정, 결과, 후속 검증 기록
- `VERIFICATION_RESULTS.md`: 감사 명령, 지표, 판정, 재검증 결과 누적
- `HISTORY.md`: 날짜별 개발/운영 히스토리와 확인 결과

개별 상세 문서는 기존 위치를 유지한다. 예를 들어 검색 shard 사건은 `docs/search_reliability_review_20260426.md`, WARP 구성은 `docs/warp_sharding.md`, slang DB 작업은 `docs/slang_db_improvement_todo.md`에 상세를 둔다.

현재 active operating contract는 repository root의 `goal.md`, `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`, 그리고 최신 변경 계약인 `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`를 기준으로 한다. 아래 Loop179 설명은 2026-06-30 공통 promotion gate 도입 시점의 역사적 확정 기록이며, 현재 상태는 이 문서 맨 위의 Loop643/P0 v5 항목을 우선한다. Loop179은 Loop176 broader unittest failure cluster를 아키텍처 보강 phase로 흡수해 `src/llm_batch/promotion_gate.py`의 공통 `GroundingState`/`EvidenceRecord`/`PromotionDecision`/`GateReport`/`can_publish_title` layer를 추가했고, selected high-risk public-title publish paths를 shared gate로 배선했다. Loop179 authoritative broader unittest result는 `.venv312\Scripts\python.exe -m unittest discover --start-directory tests` 기준 `1299` tests, `0` failures, `0` errors, `OK`다. Artifacts는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_review.md/json`, Data Analytics artifact `loop179_promotion_gate_architecture_data_analytics_artifact.json`, report `docs/devs/loop_reports/LOOP_179_REPORT_20260630.md`다. 이것은 architecture-phase unittest gate 통과이며 semantic/full-scan approval이 아니다. Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal completion `NOT_COMPLETE`를 유지한다.

2026-07-01 최신 focused runtime/code-test patch는 Loop236이다. Loop236은 Loop235가 노출한 URL-title mismatch를 `url_title_verified_official_detail` publish precondition으로 좁혔다. 원 canary `20260701_212908_967986`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`였지만 wrong public title `두 문명과의 충돌은, 그 누구도 예상하지 못하게 일어난다 (필력 구림)` / URL `https://novelpia.com/novel/427233` publish 가능성을 드러냈다. 새 가드의 resync preview는 같은 산출물을 `promotion_blocked`로 내렸고, patched canary `20260701_214126_569050`은 completed/flushed/pending/failed `1/1/0/0`, VLM/OCR `READY`, public title `전 버튜버가 하고 싶은데요`, URL `https://novelpia.com/novel/275975`, `candidate_ledger_status=safe_resolved`다. Report는 `docs/devs/loop_reports/LOOP_236_REPORT_20260701.md`, review는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop236_url_title_direct_support_guard_review.md/json`, Data Analytics artifact는 `loop236_url_title_direct_support_guard_data_analytics_artifact.json`이다. Residual accounting은 `NO_DELTA_TARGETED_URL_TITLE_DIRECT_SUPPORT_GUARD`이며 active goal은 계속 `NOT_COMPLETE`다.

2026-07-01 최신 source/native review는 Loop232다. Loop232는 Loop231 이후 focus 5건을 review-only로 분해했고 `11661876`/`11663540`은 다음 architecture patch 후보, `11695637`은 old `도네하지 마라` 복구 금지/retarget open, `11660237`은 targeted/parent variance, `11706832`은 Loop145 caveat 재개방으로 기록했다. Report는 `docs/devs/loop_reports/LOOP_232_REPORT_20260701.md`, review는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop232_loop231_safe_loss_variance_review.md/json`, Data Analytics artifact는 `loop232_loop231_safe_loss_variance_data_analytics_artifact.json`이다. Residual accounting은 `NO_DELTA_SOURCE_NATIVE_VARIANCE_REVIEW_ONLY`이며 active goal은 계속 `NOT_COMPLETE`다.

2026-07-01 최신 parent replay report는 Loop231이다. Loop231은 Loop230 title-led serializer/gate 복구를 38-row parent/representative packet에서 재검증했고 runtime은 `GO`, completed/flushed/pending/failed `38/38/0/0`, VLM/OCR `READY`, MCP health `36/36`이다. `11660257`은 `암흑가 보스요? 제가요?`로 parent survival을 확인했지만, Loop225 대비 public title count가 `12->11`로 줄고 safe loss `11661876`, `11663540`, `11695637`이 생겨 parent semantic result는 `NO-GO / MIXED_MOVEMENT`다. Report는 `docs/devs/loop_reports/LOOP_231_REPORT_20260701.md`, review는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop231_parent_replay_after_loop230_title_led_serializer_gate_review.md/json`, Data Analytics artifact는 `loop231_parent_replay_after_loop230_title_led_serializer_gate_data_analytics_artifact.json`이다. Residual accounting은 `NO_DELTA_PARENT_REPLAY_AFTER_LOOP230_MIXED_MOVEMENT`이며 active goal은 계속 `NOT_COMPLETE`다.

## 운영 원칙

- 기능 변경, 검색/런 품질 개선, slang DB 규칙 변경 시 `DEV_TODO.md` 또는 `FEATURE_IMPROVEMENT_TODO.md`와 관련 상세 문서를 함께 갱신한다.
- 대량 런 후에는 `HISTORY.md`에 run id, 핵심 지표, 문제, 조치, 재검증 결과를 남긴다.
- 4~20건 테스트는 `SMOKE ONLY`로만 기록한다. 품질 승인에는 100% 자동 감사와 10,000건 이상 validation 샘플 또는 그에 준하는 대형 표본이 필요하다.
- 기능/품질 개선은 구현 후 자동 테스트 런, run audit, 개선 전후 비교 문서, 필요 시 LLM 리뷰 패킷까지 한 묶음으로 남긴다.
- 완료 처리 전에는 `CHECKLIST.md`와 `OPERATION_QUALITY_CHECKLIST.md`의 관련 항목을 확인하고, 확인한 명령/결과를 `VERIFICATION_RESULTS.md`에 적는다.
- scan result directory를 리뷰할 때는 `SCAN_RESULT_REVIEW_GUIDE.md`의 `GUIDE_MODE`/`RUN_REVIEW_MODE`/`MIXED_MODE`, 증거 등급, action queue를 먼저 적용한다.
- `result_scan`, `run_audit`, count summary는 run integrity 증거로만 취급하고, 대량 판정 품질 승인은 `QUALITATIVE_SEMANTIC_REVIEW_LOOP.md` 기준 semantic review 산출물까지 있어야 한다.
- 통계 감사만으로 판단할 수 없는 케이스는 `LLM_JUDGMENT_REVIEW.md` 절차에 따라 정성 리뷰 패킷을 만든다.
- 전문가 판단과 최종 JSON이 충돌하는 케이스는 `EXPERT_ORCHESTRATION_LIMITATIONS.md`의 후처리 rescue/프롬프트 한계 기준으로 검토한다.
- targeted canary에서 final JSON이 회복됐더라도 중간 후처리 guard가 title을 흔들거나 삭제한 로그가 있으면 별도 회귀 seed와 action queue로 남긴다.
- 단건 post fix 후에는 바로 다음 단건으로 넘어가지 않는다. parent lane/representative mini-lane, recent controls, golden controls, affected tests, collateral movement를 확인한 뒤 residual accounting을 줄인다.
- 역할/호칭성 alias, memory-query/no-anchor, generic bridge처럼 후단 rescue가 오삽입을 만들 수 있는 패턴은 targeted canary 통과 후에도 high-risk bucket에서 재검증한다.
- 큰 개선은 `IMPROVEMENT_REGISTER.md`에 먼저 등록하고 상태를 `proposed -> in_progress -> verified` 순서로 이동한다.
- 문서에는 추측과 확인 결과를 분리해서 쓴다. 확인한 숫자에는 run id와 생성 파일 경로를 붙인다.
- 신규/갱신 보고서, loop report, review Markdown, Data Analytics reader-facing 산출물은 한국어로 작성한다. 간략하게 쓰되 의미, 근거, 산출물 경로, 게이트 상태는 생략하지 않는다.

## 2026-09-02 최신 P0 external trust 문서

- [Windows external public-key pin candidate](../../P0_WINDOWS_EXTERNAL_PUBLIC_KEY_PIN_CANDIDATE_REVIEW_20260902_KO.md): held pin bytes, effective-token ACL deny와 signed-root overlap을 검증하지만 독립 policy/provisioning은 false다.
- [Windows owner-policy 계약·binary ACL 재검토](../../P0_WINDOWS_OWNER_POLICY_CONTRACT_REVIEW_20260902_KO.md): strict signed-policy 구조, 고정 8-role layout, exact ACE comparator와 binary ACL reader를 다룬다. 현재 판정은 `OWNER_POLICY_CONTRACT_PASS_BOOTSTRAP_AND_PROVISIONING_NO_GO`다.
- [Windows 고정 owner-policy 저장소 후보](../../P0_WINDOWS_FIXED_OWNER_POLICY_STORE_CANDIDATE_REVIEW_20260902_KO.md): zero-input ProgramData/genesis selection, held 8-role observation, hash-cycle 수정과 독립 red-team 결과를 다룬다. 현재 판정은 `OWNER_POLICY_FIXED_STORE_CANDIDATE_PASS_AUTHORITY_NO_GO`다.
- [Windows bootstrap policy 서명 수학 후보](../../P0_WINDOWS_BOOTSTRAP_POLICY_SIGNATURE_CANDIDATE_REVIEW_20260902_KO.md): exact transcript·held raw body SHA·CNG 검증과 fixed-store child receipt fail-close를 다룬다. 수학만 PASS다.
- [Windows owner deployment projection v2](../../P0_WINDOWS_OWNER_DEPLOYMENT_PROJECTION_V2_REVIEW_20260902_KO.md): future authority policy가 서명할 native service·PE/resource·WDAC/UMCI·loaded provider projection과 SID split 수정, 다음 zero-input host preflight를 다룬다.
- 실제 owner-approved bootstrap key와 trusted code/provider provisioning, fixed live store, linked-token·privilege 검사, time/revocation/rollback-resistant state가 없으므로 actual/P0/production은 계속 NO-GO다.

## 상태 규격

- `proposed`: 문제와 방향만 정리됨
- `in_progress`: 코드/설정/문서 변경 진행 중
- `implemented`: 변경은 반영됐지만 충분한 검증 전
- `verified`: 명령 또는 재런으로 개선 확인
- `deferred`: 지금은 보류
- `rejected`: 검토 후 채택하지 않음

## 품질 판정 규격

- `GO`: shard 100% 정상, run audit 정합성 통과, slang 오염 0, 필요한 정성 리뷰 완료, semantic decision quality 승인, 문서/검증 결과 갱신 완료
- `REVIEW`: 운영은 가능하지만 검색 저하율 상승, 실제 약칭 후보 미검토, pending/flush 차이, LLM/전문가 정성 리뷰 필요
- `NO-GO`: bad shard 존재, `/readyz` 실패, SearchXNG UI 실패, fatal traceback 증가, slang DB 오염 발생

## 변경 기록 템플릿

```markdown
## YYYY-MM-DD - 짧은 제목

- 상태: proposed | in_progress | implemented | verified | deferred | rejected
- 관련 run id:
- 관련 파일:
- 문제:
- 조치:
- 확인:
- 남은 위험:
- 다음 작업:
```

명시 FROZEN 재관측의 설정·저장·화면 계약과 검증 근거는 [운영 기록](../../CANDIDATE_RERANKER_SHADOW_20261010_KO.md)을 따른다.
