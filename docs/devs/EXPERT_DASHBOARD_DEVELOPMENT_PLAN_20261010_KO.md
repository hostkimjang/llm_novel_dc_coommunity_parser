# expert_main 통합과 대시보드 후속 개발 계획

> 현재 상태는 [현재 상태 문서](CURRENT_STATUS_KO.md)를 따른다. 날짜별 기록과 `out/`·`logs/` 링크는 로컬 보존 자료이며 Git checkout에 포함되지 않을 수 있다.

<!-- r5-resolution-current:start -->

## 현재 상태 안내 — 2026-10-15

현재80 범위 개발·검증과 Goal 완료 상태는 [현재 상태와 남은 작업](CURRENT_STATUS_KO.md)에서 관리한다. 전체 의미 `REVIEW`·기존5개 실패·독립 평가/R7 보류·새 분기 실측 미관측을 함께 확인한다. 아래 날짜별 실행·시험·미완료 표기는 당시 이력이다.

<!-- r5-resolution-current:end -->

<!-- research-completion-current:start -->

## 2026-10-14 source462 단계 이력 — 최신 상태는 위 완료 기록 참조

[최종 결과와 남은 수용 조건](../../out/research_completion_20261014_v1/REPORT_KO.md)는 당시 단계의 근거다. 기존80의 개발용 회수48관측,50번 수리·실제1건 검토, JSONL 댓글 생략 호환성·시작 전 실패·상대경로 이력·화면 전환 수리를 마쳤다. source462를 고정한 R6 실제1건은 원래 HOLD와 별도 native PUBLISH를 보존하며 HTTP9회·230.172초로 종료했고 원장 검산을 통과했다. 실제 화면과 관련 회귀도 확인했다.

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

**현재 정책 거절은 없었다.** 검색3354 중지로 사전점검이 멈췄으나 기존 컨테이너3개를 기동한 뒤 `20261014_144947_200849`가 current source454·parallel12/12·대시보드ON·저부하 조건으로 정상 종료했다. completed/flushed12·failed/pending0·exit0, 결과/체크포인트12/12와 보호소스454/454 불변을 확인했다. [최종 실행·협업 평가](../../out/source_remaining12_actual_20261014_search_restored01/RUN_STATUS_KO.md)가 현재 상태다. 아래의 정책차단/미시작/실행중 문장은 당시 이력으로 보존한다.

새12 평가: Sol A7/H4/R1, Opus A9/H2/R1.24 무관참조 제거·44 self/own 및 embedded 상태 교정을 관측했다.65는 후보가 회복됐지만 High 경로라 Low 보존분기 효과는 미입증이다. **50번은 양측 REPROCESS**로 분류·후보 소실 원인 판독이 남는다.13·33은 검토 범위 차이가 있고 전체 의미는 REVIEW다. 전체80 승인·R5 paired·R2–R6 실제 연구 품질·사람정답/권리/holdout은 미완료이며 formal KPI는 NOT_ESTIMABLE이다. 제품코드 변경0.

- [x] 현재 코드 실제12 실행·종료·원본 결속·두 모델 전행 평가 완료.
- [x] 과거 정책거절과 이번 검색 서비스 중지의 구분 및 복구 확인.
- [ ] 50번 분류/후보 소실 원인 판독과 남은 작품 근거·실제 연구 수용.



## 2026-10-14 실행 재확인: 정책 거절 없이 실제12 분석 시작

**현재 실행 명령은 허용됐다.** 첫 호출은 검색3354 연결 거부로 사전점검에서 멈췄고, 기존 중지 검색 컨테이너3개를 시작해 query probe1/1·degraded0을 확인했다. 이후 `20261014_144947_200849`가 현재source454·parallel12/12·대시보드ON·저부하 조건으로 시작했다. [현재 실행 상태와 근거](../../out/source_remaining12_actual_20261014_search_restored01/RUN_STATUS_KO.md)를 따른다. 아래 과거 정책차단·미시작 기록은 당시 이력이며 현재 진행 상태가 아니다. 최종 품질·R5paired·연구 수용 완료는 아직 주장하지 않는다.

- [x] 현재 도구 호출·프로세스 기동·검색 복구·실모델 응답 확인.
- [ ] 실제12 종료·결과 결속·수정 효과 판독.



## 2026-10-14 후속: Opus 5.5·Sol 6.1 협업 평가 완료

[저장80 협업 평가와 최종 검증 상태](../../out/collaborative_final_eval_20261014_v1/root/REPORT_KO.md)가 이번 후속의 통합 결론이다. Opus 5.5 새 채팅과 Sol 6.1 서브에이전트가 각각80행을 독립 평가한 뒤 교차검토했다. 초기 판정은 Opus A60/H18/R1/I1, Sol A33/H37/R6/I4이며 일치50·불일치30이다. 일치율은 정확도가 아니다. 71의 Sol REPROCESS와 후보 URL·역할 누락 관련 과장된 근거를 정정했고 최초 라벨은 보존했다.

과거24·44·55·57·65 문제의 기존 수리를 확인했으며 **새롭게 확정한 현재 코드의 미수리 결함은0건**이다. 보호소스454/454·release253/253은 마지막 적용 SHA와 같다. 기존754 PASS·하위22, Node94 PASS·선택3 SKIP 및 저장 이력 화면 확인을 유지하되 이번에 새 시험이나 expert_main 모델 실행은 하지 않았다. 55/57의 과거 직접 시험을 최신754에 포함된 것으로 소급하지 않는다.

**의미 품질 REVIEW·최신 source454 모델 효과 NOT_OBSERVED·formal KPI NOT_ESTIMABLE**이다. 최신 실측, R5 paired, 실제 corpus/정답/권리/holdout·R2–R6 품질 수용은 남아 있다. 네이티브 Goal 조회값은 blocked이며 완료로 변경하지 않았다. 이전 실행 차단의 세부 이유는 미제공이고 콘텐츠 검열로 확정하지 않는다. 사용자 승인·parallel12·대시보드 ON·저부하 정책과 R7 보류를 유지한다.

- [x] 두 모델80행 결속·독립 평가·교차검토와 과거 문제/현재 수리 분리 완료.
- [x] 평가자 오류 정정, 원본 보존, 연구 지표 산출 범위와 다음 조건 기록 완료.
- [ ] 최신 코드 실제 모델 효과·R5 대조실행·실자료 연구 품질 수용.

아래 구현·시험·차단 기록은 원래 근거와 함께 보존한다.



## 2026-10-14 현재: 최종 754 PASS·19파일 적용·source454·저장 이력 화면 확인

**44번 화자/부정·65번 후보 보존·사건 카드/진단 저장·캐시 이력 탐색 수리를 적용했다.** [29개 전체 파일 754 PASS·하위22 PASS](../../out/r5_attempt_failure_validation_v1/run_final44_65_ui_history_v4_001/receipt.json) 후 [검증 바이트 19파일](../../out/source_final_application_v1/application_001/receipt.json)을 정확 적용했다. 제품6(기존5·신규1)·시험9(Python8·Node1)·fixture4이며 신규14파일, 기존5파일 백업, gitignore 시험 예외9와 기존 prefix·index 보존을 확인했다. [적용 후 검사](../../out/source_final_application_v1/application_001/post_apply_check.json)는 diff check0·신규 무시 없음이다. 현재 보호 소스는 **454개**다. [적용 보고서](../../out/source_final_application_v1/application_001/REPORT_KO.md)에 구현·적용·화면 확인 범위를 모았다.

| 적용 범위 | 검증된 동작과 범위 |
|---|---|
| 44번 내용절·부정 | [원문·바깥 주체와 부정 범위](../../out/source44_compound_speaker_review_v1/REPORT_KO.md)를 결속해 내용절 명사를 화자로 올리지 않는다. 긍정 어휘·원문 좌표를 남기며 최종 근거 채택과 구분한다. |
| 65번 후보 회수 | [F1–F4와 동일 문서 encoded URL 반증 경계](../../out/source65_candidate_preservation_review_v4/REPORT_KO.md)를 수리했다. 검산된 인물-작품 관계만 Low/noURL/noalias 후보로 보존하며 후단에서 같은 원자료를 재검산한다. 공개·학습 권한을 만들지 않는다. |
| 사건 카드·exporter | [성립 상태·성립 근거·평가 방향·최종 채택](../../out/source_context_event_state_ui_repair_v2/HANDOFF_KO.md)을 저장값으로 표시한다. native 근거 필드 하나를 기존 상한 안에서 저장하고 과거 미기록을 추정하지 않는다. |
| 실행 이력 탐색 | [전용 URL 캐시의 50,000항목 예산 선점](../../out/history_latest_discovery_audit_v1/REPORT_KO.md)을 분리했다. [root 직계 캐시 하위만 제외](../../out/history_cache_scan_review_v1/REPORT_KO.md)하며 디렉터리 자체 집계·깊은 동명·안전한 current-output·기존 상한을 유지한다. |

동일 presentation 제품의 [Node 97수집·94 PASS·기존 선택3 SKIP](../../out/source_context_event_state_ui_validation_v2/node_001/receipt.json)에서 새 카드6은 모두 PASS다. [74번 시험 후손](../../out/source_context_event_state_test_repair_v3/HANDOFF_KO.md)은 구·신 exporter에 공통인 graph edge1건 생략(`TRUNCATED/FIELD_LIMIT`)을 정확히 요구하고 사건 전체/native/bytes 상한 검사를 유지한다. 중간566·610·100과 최종754 및 Node 수를 합산해 고유 시험 수나 모델 정답률로 쓰지 않는다. **이 결과는 명시 파일의 오프라인 기능 검증이며 실제 모델 개선 효과·전체80 품질 승인이 아니다.**

[현재 디스크 source 결속](../../out/source_final_application_v1/application_001/source_binding.json)의 release는 `19de4b231ece83ec9c780f722433cdda501be12d7a450232eefc2a919e52df6d`, selected runtime source는 `c6065808971154a0ce6023776b78e8facbfa88d8888a2729968d43601a31c1bf`다. 모델 runtime generation 실측은 없다. [적용 후 실제 화면 확인](../../out/source_final_ui_validation_v1/receipt.json)은 로컬18868(PID51484, BelowNormal·affinity2)에서 최근80·24 이력 복구, 80건 상세와 저장 병렬12/12를 확인했다. 목록75·전체 탐색 상한 안내는 유지돼 무제한 전체 이력 복구를 뜻하지 않는다. 과거44 카드는 `actual / 성립 근거 미기록 / pos / 최종 근거 채택 false`와 저장 당시 화자 `마무리`를 그대로 표시한다. 새 코드의 모델 재실행 결과가 아니다. 콘솔 오류·경고 관측0이며 CUA 캡처는 도구로 관측했지만 파일로 저장하지 않았다. 제공 presentation은 적용 바이트와 같고 실제80 원본 SHA는 변하지 않았다.

**실제12는 미시작이다.** [자동 승인 검토가 실행 명령을 `blocked by policy`로 거절](../../out/source_remaining12_launch_prep_v1/rejected_attempt_001.json)했고 세부 이유는 제공되지 않았다. 기존 사용자 승인은 유지되며 재승인 요청·우회·재시도는 하지 않았다. [과거 source440 실행 ready](../../out/source_remaining12_launch_prep_v1/launch_plan.ready.json)는 당시 준비물로 보존하며 현재 source454의 실행 명세가 아니다. requested parallel12·dashboard ON·저부하 원칙은 유지하지만 새 actual run/scope·모델 결과는 없다.

이전80 `20261013_181711_146907`의 [A39/H33/R8/I0·END44·history842](../../out/p4_quality_followup_20261013/actual80_current_followup_parallel12_v1/final_review_80_v1/REPORT_KO.md)와 의미 **REVIEW**를 유지한다. 이번 적용으로 과거 라벨을 바꾸지 않는다. [R5 BEFORE exit1·FAILED/DRAINED](../../out/r5_actual24_pair_after_failure_repair_001/end_observation_001/receipt.json)·AFTER 미시작·동일 reference/WAL 결정 계약의 paired 미완료도 유지한다. guard 완화·참조 재봉인·실행 반복으로 완료를 주장하지 않는다.

준비80 관측192·HUMAN_GOLD0·권리UNKNOWN·training ready0·독립 holdout0, 실제 연구 품질·R2–R6 수용 미확정, 49번 full-context 진단2·69번10 미완료를 보존한다. **Goal blocked·formal KPI NOT_ESTIMABLE·R7 보류**다. 전체80 ACCEPT나 새 전체80 자동 재실행을 완료 조건으로 추가하지 않는다.

- [x] 29전체파일754 PASS·하위22 PASS와 source454 정확 적용을 확인했다.
- [x] Node94 PASS·기존 선택3 SKIP, 원형 실패와 시험 기대 정정 근거를 구분했다.
- [x] 저장80·24 이력, 80건 상세와 과거44 사건 카드의 실제 표시를 확인했다.
- [ ] 실제12 모델 효과·R5 paired·사람 정답/권리/실자료 품질은 미완료다.

[v33 후속 원형](../../out/p4_quality_followup_20261013/docs_integration_update_v33_followup_v1/REPORT_KO.md)을 보존하고 [v34 갱신 보고서](../../out/p4_quality_followup_20261013/docs_integration_update_v34/REPORT_KO.md)에 CURRENT 전후와 검산을 기록한다.

2026-10-14 같은 미해결 실행 차단과 자료 조건을 세 목표 턴 연속 확인해 Goal을 blocked로 전환했다. 추가로 진행할 확정 로컬 수리는 확인되지 않았다. 사용자 승인은 유지하며, [재개 조건과 보존 근거](../../out/goal_blocked_20261014_v1/HANDOFF_KO.md)를 따른다. 구현·로컬 시험·저장 화면 확인과 실제 모델·연구 평가의 미완료를 구분한다.

<!-- source-quality-current:end -->

## 직전 단계 기록: 191128 실행 종료와 첫 통합 후보 시험

> 아래 후보 미완료·실패 원인·진행 문장은 그때의 기록이다. 최신 수리 및 검증 상태는 위 현재 구역을 따른다.

실행 `20261012_191128_106718`은 **exit0·80/80 저장·실패0·대기0·terminal 확정**, 요청·실효 병렬도 **12/12**로 종료했다. [종료 검산](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/end_check_prep_v1/end_verification_02.json)은 **44개 PASS_TECHNICAL_ONLY**이며 실제 Python·venv launcher·supervisor 세 PID 종료를 확인했다. 실행 소스288개와 보호 목록6,279개의 보존은 해당 수령증 범위다. 시작 전 PREPARED 및 실행 중 RUNNING 기록은 당시 이력으로 보존한다.

[이력 API](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/history_check_prep_v1/run_first/receipt.json)는 **80행·11 GET·820개 검사 PASS**로 저장 원시 필드·BOUND·새 NSFW 상태·parallel12를 대조했다. [실제 화면](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/browser_final_readback_v1/receipt.json)은 **PASS_SCOPED_FINAL_LIVE_HISTORY_UI**다. live 100%·80/80·활성0, 최종 이력80건·12/12와 74번 live/history, 10·15·49·61번 history의 선택된 상세를 확인했다. NSFW 미평가/모델 false/규칙 양성 표시와 메모·댓글 귀속을 구분했고, 74번의 행별 장부 상태와 종료 manifest 요약을 덮어쓰지 않았다. 관측 콘솔 오류·경고0이며 이력 탐색 상한 경고는 유지한다. API 검사 수와 UI 관측·과거 Python/Node 시험 수를 합산하지 않는다.

[최종 행 결속·59행 리뷰 재사용](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_prep_v1/run_first/final_reconciliation_receipt.json)은 기존 **ACCEPT20·HOLD31·REPROCESS2·INFO_MISSING6**을 보존했다. [남은21행 리뷰](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_remaining21_v1/REVIEW_KO.md)와 [21행 결속 수령증](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_remaining21_v1/reviewer_receipt.json)은 **ACCEPT10·HOLD9·REPROCESS1·INFO_MISSING1**이다. **80행 검토는 완료했으며 인계용 합계는 ACCEPT30·HOLD40·REPROCESS3·INFO_MISSING7**이다. [전행 통합 결속](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_reconciled_v1/receipt.json)은 80행 원문·typed ID·전체 결과 SHA와 중복·누락0을 확인했고 [최종 종합](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/final_review_reconciled_v1/SUMMARY_KO.md)에 남겼다. REPROCESS는 **8·55·57번**이다. 55번 [정적 원인 조사](../../out/p4_quality_followup_20261012/semantic_state55_followup_v1/REPORT_KO.md)는 초기 제목 힌트와 작품성을 부정한 표면 anchor가 별도 제목 상태 계산에 남는 경로를 확인했다. 57번과 같은 질문 규칙이 아니며, 동일 문맥 동작 재현·수리는 미실행이고 신규 코드 회귀 귀속도 미확정이다. 74번 SOURCE_RULE_POSITIVE는 원문 댓글에 결속된 좁은 수리 효과를 ACCEPT로 검토했으며 전체 NSFW 정답으로 확대하지 않는다. 픽셀을 보지 않은 49번의 규칙 양성도 이미지 정답을 뜻하지 않는다. 전체 품질은 REVIEW다. [직전80 대비 공개 값 목록](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/publication_delta_inventory_v1/REPORT_KO.md)은 145104→191128의 공식 제목·URL 변경0·동일80(제목+URL10·제목만1·null69)을 확인했다. 1·12·14번도 직전과 같으며, 더 오래된 변화와 구분한다. 값 동일성은 오공개0이나 공개 적격성 증명이 아니다.

8번 [명명 표현 v3 후보](../../out/p4_quality_followup_20261012/slang_role_expression_candidate_v3/SOURCE_FROZEN.json)와 57번 [제목 상태 후보](../../out/p4_quality_followup_20261012/semantic_state57_candidate_v1/SOURCE_FROZEN.json)는 AST·독립 정적 검토를 거쳐 [통합 후보 동결](../../out/p4_quality_followup_20261012/source_quality_bundle_validation_v1/SOURCE_FROZEN.json)에 결합됐다. [통합 후보 첫 시험](../../out/p4_quality_followup_20261012/source_quality_bundle_validation_v1/run_first/validation_receipt.json)은 **13파일 411 PASS·104 subtest PASS·2 FAIL, 오류·스킵0**이다. 정상57 serializer·main wrapper·WAL과 역할3 경로는 통과했지만, 57번 payload 제목 상태 및 candidate ledger의 입력 fingerprint 변조를 거절하지 못한 두 시험이 실패했다. **57번 optional scope seal을 별도 v2 후보에서 수리 중이며 통합 후보는 primary 미적용**이다. 실패 원본은 보존한다. 기존 pipeline `ee9088f6…`로 끝난 이번80은 이 두 후보의 실측 증거가 아니다. 이후 후보가 적용되면 이번 결과는 수리 전 기준 실행으로 남기며, 새 코드의 실측 여부를 별도로 표시해야 한다. 기존 수리 Python12파일251 PASS·104 subtest와 별도 Node87 PASS는 당시 로컬 증거로 유지한다.

R2/R3/R4 candidate 기능·community knowledge·native recovery는 OFF였으므로 연구 기능 ON 실측을 대체하지 않는다. 사람 정답0·학습 준비0·권리 UNKNOWN·formal KPI **NOT_ESTIMABLE**·품질 **REVIEW**·Goal active·R7 보류를 유지한다. 이후 Expert-main 실행 기본은 `--parallel 12`·대시보드 ON·기존 저부하 정책이다.

## 2026-10-12 이전 단계: 병렬12 전체80 정상 종료·전행 검토 완료, 품질 수용 REVIEW

실행 `20261012_145104_574531`은 **요청12·실효12·대시보드 ON**, exit0·80/80 저장·실패0·대기0·terminal 확정으로 종료했다. [종료 검산](../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/end_verification.json)27개와 [이력 API 대조](../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/history_api_receipt.json)499개가 통과했고 실행 종료 시점의 보호 파일4,718개에 변경이 없었다. 최종 코드의 토큰·검색 집계는 실제 검증을 마쳤다. 문맥 이벤트 토큰6,288,623과 검색74 hits/395 misses가 저장 trace·CLI·12워커 합계에 일치한다. manifest 관측9,059,040토큰은 별도 범위이며 모두 정식 KPI·전체 청구 비용이 아니다.

[실제 화면](../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/browser_receipt.json)은 live100%·80/80·활성0, 최종 이력80건·병렬12/12, 메모·NSFW·구조화 문맥·유효 설정·주변 관련 배지와 원시 진단 구분을 확인했다. 관측 콘솔 오류·경고0이며 이력 탐색 상한 경고는 유지한다. 현재 renderer의 [합성 저장자료84 PASS·0 FAIL·0 SKIP](../../out/development_plan_20261010/p4_reapproval_v1/ui_final_optional_readback_v1/receipt.json)은 별도 시험이며 검사 수를 합산하지 않는다. [대시보드](http://127.0.0.1:18864/)는 완료 결과를 표시한다.

[80행 최종 리뷰](../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/review_reconciled_v1/review_receipt.json)는 원문·댓글·최종 행 전체 SHA에 결속됐으며 **ACCEPT32·HOLD33·REPROCESS8·INFO_MISSING7**, gate **REVIEW**다. 나머지48건을 오류율로 계산하지 않는다. 새 제목 공개12·14번은 HOLD다.74번은 전문가 최초 응답부터 NSFW가 달랐으며, 새 저장 코드 회귀는 입증되지 않았다. 댓글 NSFW 검산 공백으로 REPROCESS를 유지한다. 미판정 근거를 두고 전체80의 새 오공개0이나 품질 통과를 선언하지 않는다. [종합 인계와 후속 개발](../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/REVIEW_SUMMARY_KO.md)에 근거·범위·미완료 조건을 정리했다.

[새80 snapshot](../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/final_snapshot_v1/receipt.json)은 저장 관측80·고유 원문80, VERIFIED / COMPLETE_WITH_LIMITS다. 기존80·실제12·112관측 준비물은 보존했다. 사람 정답0·학습 준비0·권리 UNKNOWN·독립 holdout 없음·formal KPI **NOT_ESTIMABLE**을 유지한다. R2/R3/R4/native는 OFF였으므로 실제 연구 기능 검증을 대체하지 않는다. **P4 기술 검증과 전행 리뷰 수행은 완료, 의미 품질 수용과 R2~R6 실제 평가 조건은 미완료이며 Goal은 active**다. 이후 Expert-main 테스트는 `--parallel 12`·대시보드 ON을 따른다.

아래 실제12·차단·미실행 등 설명은 해당 시점 이력이다. 이전 RUNNING 구역의 바이트는 이번 문서 갱신 백업에 보존했다.

## 이전 2026-10-12 단계: 병렬12 기술 종료·12행 리뷰와 제한된 UI 확인

실행 `20261012_134614_949602`는 **exit0·12/12 저장·실패0·대기0·terminal=true**, 요청12·실효12로 종료했다. [종료 기술 검산](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/end_verification_v2.json)은 **PASS_TECHNICAL_ONLY·21개 검사**, [이력 API](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/history_api_receipt.json)는 **84개 검사·12행 원시 저장값 일치·BOUND·병렬12/12**다. 초기 검산 실패는 병렬 체크포인트의 완료 순서를 입력 순서로 가정한 것으로, 원본 기록을 보존하고 v2에서 고유행·최종 입력 순서·WAL 결속을 확인했다. 이력 탐색 상한 경고는 유지한다.

[3개 에이전트 리뷰 종합](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/REVIEW_SUMMARY_KO.md)은 고유 12행에 중복·누락 없이 **ACCEPT9·HOLD3**, gate **REVIEW**다. 약먹마의 비교 역할·별칭 source 연결, 회모장의 이미지·작품 결속, 추천 글의 구조화된 비교·추천 표면 보존이 남아 있다. CF01 및 의미 상태 v3의 독립 검토는 각 수리 당시 소스 범위에서 통과했다. CF03은 새 Decoder가 이전 오염 제목을 만들지 않아 이번 실측만으로 필터의 직접 효과를 입증하지 않는다.

[실제 화면 확인](../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/browser_receipt.json)은 **PASS_SCOPED_UI_WITH_METRICS_PENDING**이다. root가 18863의 live 100%·12/12·활성 worker0, 이력의 현재 run 최상단·최종 저장12건, 11718092의 NSFW true·메모·진단 STORED·BOUND 및 8670967의 adjacent 상태를 확인했다. 11663522는 live/history 모두 **주변 관련**과 원래 `is_relevant=false` 진단을 보존하면서 중복 무관 배지를 제거했다. 관측 콘솔 오류·경고는 0이며 로컬 스크린샷 파일은 만들지 않았다. [Node 판독](../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/node_readback.json)은 **81 PASS·3 SKIP·실패0·총84**로, native/provider/inference 환경 자료 미설정 선택 시험 3개는 이번에 실행되지 않았다. JavaScript 캐시 때문에 자산 버전 한 줄을 갱신한 뒤 실제 화면을 확인했으며 [최종 자산](../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/final_static_receipt.json)과 [독립 검토 v2](../../out/development_plan_20261010/p4_reapproval_v1/related_label_fix_v1/independent_review_v2.json)는 기능 코드 동일성을 결속한다. 전체 UI·전체 기능 검증 PASS로 확대하지 않는다.

[토큰 context 수리](../../out/development_plan_20261010/p4_reapproval_v1/token_context_fix_v1/SOURCE_FROZEN.json)는 7파일 **104개·하위59개**, [검색 통계 worker 합산](../../out/development_plan_20261010/p4_reapproval_v1/cache_stats_fix_v1/validation_receipt.json)은 7파일 **115개·하위54개** 로컬 통과다. [토큰 독립 리뷰](../../out/development_plan_20261010/p4_reapproval_v1/token_context_fix_v1/independent_review.json)와 [캐시 독립 리뷰](../../out/development_plan_20261010/p4_reapproval_v1/cache_stats_fix_v1/independent_review.json)도 PASS이며 두 집계 상태는 **LOCAL_VERIFIED_ACTUAL_PENDING**이다. **18863의 Python 프로세스는 집계 수리 전 코드이고 정적 UI만 갱신했다.** 실제12의 token 965.2K·cache 0% 및 CLI hits20/misses96 관측을 소급 보정하지 않는다. 실제12 자체도 token/cache/UI 최종 수정 전 소스다. [후속 조치](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/action_queue.json)에 남은 범위를 구분했으며 서로 겹치는 시험·기술 검사 수를 합산하지 않는다.

기존80의 기술 종료와 전행 리뷰는 보존하며 **최종 코드의 새 전체80 재실행은 아직 하지 않았다.** 실제12는 개발 노출80의 부분집합이고 독립 holdout·R5 paired 실측이 아니다. R2/R3/R4/native OFF였으므로 해당 기능의 실제 성공 근거로 쓰지 않는다. 사람 정답0·학습 준비0·권리 UNKNOWN·formal KPI **NOT_ESTIMABLE**·Goal **active**를 유지한다. 새 Expert-main 실행 기본은 요청12·실효 `min(input_count,12)`·대시보드 ON이다. 아래 단계별 기록은 당시 이력이며 현재 운영은 [P4 인계](P4_REAPPROVAL_RUN_20261010_KO.md)를 따른다.

## 이전 차단 이력: 2026-10-10 blocked 전환 당시

같은 실행 차단과 자료 선행 조건 미충족을 세 차례 연속 확인해 Goal을 **blocked**로 전환했다. 실제80·최신 브라우저·사람 판정과 사용 권리·실자료 품질·R5 실측은 미완료이며, formal KPI는 NOT_ESTIMABLE, R7은 보류다. [재개 조건과 인계](GOAL_BLOCKED_HANDOFF_20261010_KO.md)를 따른다. 아래 Goal active 표기와 전달 문서 SHA는 각 단계 작성 당시 기록이다.

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

- [x] 같은 호출의 원문·provider 근거를 실제 native 전문가·guard·별도 WAL·완료 재생에 연결하고 로컬 검증했다.
- [ ] 비교 환경에서 재현된 기존 rework 실패 33건을 해결한다. 새 native 경로의 로컬 통과와 구분한다.
- [ ] 일반 main 자동 복구 스케줄과 native 결과의 API·대시보드 연결을 구현한다.
- [ ] 원문·사용 권리·사람 판정·수용 기준을 확보하고 실제 복구 품질·비용을 평가한다.

## 이전 단계: provider 근거 수집과 80건 검토 준비 (2026-10-10)

당시 R6 상태는 **PROVIDER_EVIDENCE_LOCAL_VERIFIED_NATIVE_GUARD_AND_ACTUAL_RECOVERY_PENDING**였다. 원본 HOLD·AUDIT에 결속한 명시 계획 → 영속 예약 → 단일 HTTP → 원시 응답 저장·독립 판독 → `expert_main`·대시보드 연결을 구현했다. 완료된 요청은 0회 전송으로 재생하고, 완료 여부가 불명확한 요청은 재발송하지 않는다. 최초 fresh source 검사부터 응답 저장·재판독까지 같은 시간 제한을 적용한다. 마지막 `REQUEST_FINALIZED` 자체의 저장은 이 시간 범위에서 제외한다. 저장 성공은 `PROVIDER_EVIDENCE_STORED`, 공개 guard는 `GUARD_NOT_EVALUATED`이며 일반 실행의 자동 복구는 아직 연결하지 않았다.

이전 provider 단계의 변경 영향 Python 23파일 `779 passed, 163 subtests passed in 654.67s (0:10:54)`, Node 66개 PASS다. 실제 파일 원장과 HTTP mock, 저장 결과의 API·Node 표시를 확인했다. 실제 외부 모델·검색 호출과 새 브라우저 검증은 0회다. [실행 계약·한계](../../out/development_plan_20261010/r6_provider_api_KO.md), [Python 검증](../../out/development_plan_20261010/r6_provider_final_receipt.json), [Node 검증](../../out/development_plan_20261010/r6_provider_node_receipt.json)을 따른다. 아래 이전 단계의 수치는 당시 증거이며 이번 수치와 합산하지 않는다.

[80건 검토 큐](../../out/development_plan_20261010/actual80_review_queue_v1/review_guide.md)를 준비했다. 원래 입력 순서 80행에 112관측·관측별 후보 기록 121개를 연결했고 중복 게시물 32개를 별도 표본으로 세지 않았다. WORK 2·NIL 6은 기존 모델 참조, UNJUDGED는 72건이다. 사람 정답·학습 준비는 모두 0건이며 전 행이 개발에 노출됐다. 후보 결손 3행과 미검토 이미지 21행을 검토 순서에 반영했지만 정답·역할·사용 권리를 채우지 않았다. [검산 수령증](../../out/development_plan_20261010/actual80_review_queue_v1/verification_receipt.json)에 원본 46개·이전 준비 파일 5개의 보존 근거를 남겼다.

당시 남은 범위는 P4 실제80·새 브라우저, 실제 corpus·사람 판정·TRAIN/CAL/FROZEN 품질, R5 실측, R6 native 공개 guard·자동 복구·실제 품질이었다. 현재 native 연결과 미완료 범위는 위 최신 기록을 따른다. 당시 R6 후속 계획은 [native guard 개발 메모](../../out/development_plan_20261010/r6_native_guard_next_steps_KO.md)를 따른다. 기존 자동 승인 차단을 재시도하지 않았으며 formal KPI는 `NOT_ESTIMABLE`, Goal은 active, R7은 보류다.

- [x] 원본에 결속한 provider 근거 수집·영속 예산·재시작·독립 판독·명시 main/API/화면을 로컬 검증했다.
- [x] 현재 80건의 원문·저장 후보·기존 참조를 보존한 검토 큐를 만들고 바이트 결속을 검산했다.
- [ ] 원문 근거와 사용 권리를 검토하고 작품 ID·역할·NIL 사람 판정을 별도 자료로 확정한다.
- [x] R6 일반 main 자동 복구와 native 대시보드의 로컬 연결을 검증했다.
- [ ] R6 적격 실제 자료의 복구 품질·비용을 평가한다. 로컬 합성 검증은 실제 품질 수용이 아니다.

2026년 10월 10일 기준 개발 순서는 **최신 실행 코드 통합 → 대시보드 누락 보완 → 실행 설정과 문맥 진단 저장 → 실제 결과 검증 → 연구 기능 확장**으로 정한다. 첫 번째 배포 단위는 기본 프로젝트 폴더에서 최신 `expert_main.py`를 실행하고, 해당 실행의 분석 내용과 설정·측정 상태를 대시보드에서 빠짐없이 확인할 수 있게 만드는 것이다.

원래 G1~G7은 완료 상태를 유지한다. 이 계획의 새 작업은 [적용 범위 점검](DASHBOARD_EXPERT_MAIN_COVERAGE_AUDIT_20261010_KO.md)에서 확인한 통합·표시 누락과 후속 연구 범위를 다룬다. 기존32는 기존80의 부분집합이므로 두 결과를 합쳐 독립 표본112로 계산하지 않는다. 최종 B14 수정 뒤 새 전체80 실행이 없다는 한계도 유지한다.

## 2026-10-10 최신 진행 상태

R4 상태는 **GENERAL_INFERENCE_LOCAL_VERIFIED_BROWSER_AND_ACTUAL_DATA_PENDING**다. 일반 입력의 실제 R2 원문·후보 ID·작품/판본·출처 bytes를 고정 semantic NIL 모델 및 CAL 온도에 연결하고 expert_main 저장·API·대시보드 표시를 구현했다. 현재 원문·R2·모델 점수를 재생 검산하며, FROZEN 배정이나 정답을 만들지 않는다. 이번 로컬 회귀는 Python 38파일 `1440 passed, 42 subtests passed in 229.37s (0:03:49)`, Node 58개 PASS다. 실제 pipeline에서 저장한 live/history 자료를 Node 표시 시험으로 연결했다. 실제80 준비 묶음은 112관측/80고유행을 원문과 연결했으나 사람 정답0·학습 준비0이며 전 행이 개발 노출 자료다. 실제 TRAIN/CAL/FROZEN 품질, 새80 모델 실행, 새 화면의 브라우저 검증과 R6 실제 provider 복구는 남았다. 실제 모델 API·검색·source-backed 학습은 0회다. 실제80·Chrome의 자동 승인 검토가 blocked by policy로 차단한 실행은 재시도하지 않았다. formal KPI는 NOT_ESTIMABLE, Goal은 active다.

R5 저부하 RunSpec v3·실제 실행 관측·계획 생성·판독·화면을 구현하고 Python51파일·1147개 시험·210개 하위 시험과 Node26개 PASS, reader 행 결속 보강 후 영향9파일·269개 시험·97개 하위 시험 PASS, 독립 반례18개와 합성 live/history 표시를 확인했다. 실제 모델·검색 실행0이며 비용·품질·formal KPI는 NOT_ESTIMABLE이다. 상태는 **LOCAL_CONTRACTS_VERIFIED_ACTUAL_PAIRED_MEASUREMENT_PENDING**다. [R5 운영 기록](PAIRED_LOW_LOAD_MEASUREMENT_20261010_KO.md)을 우선하고 다음 R4 수치는 과거 검증으로 구분한다.

P0~P3와 R1~R3 기능에 이어 R4의 고정 후보 SHADOW·학습 분할 검산·하네스 경로·저장·화면을 구현했다. 초기 v1 당시 상태는 **LOCAL_CONTRACTS_VERIFIED_MODEL_AND_ACTUAL_DATA_PENDING**이었다. 초기 v1 검증은 Python44파일·916개 시험·139개 하위 시험과 Node25개 PASS, 독립 검토·합성 live/history PASS다. [R4 운영 기록](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)에 정확한 API·명령 옵션·한계를 기록했다. 아래 목표는 로컬 완료 항목과 남은 실제 모델/데이터 작업을 함께 포함한다.

P4 새80은 자동 승인 차단 2회 뒤 재시도하지 않았다. R2/R3 실제 품질, R4 실제 source-backed TRAIN/CAL/FROZEN과 NIL 학습·확률 교정은 남아 있다. R5는 로컬 계약 구현을 마쳤으나 실측은 남아 있다. R6 [제한 복구 실행기](BOUNDED_RECOVERY_EXECUTION_20261010_KO.md)의 합성 실행·판독은 구현·검증됐다. 별도 main 합성 진입점·웹 연결과 단일 HTTP 요청 제어를 추가했다. 실제 provider 전체 연결·자동 실행·품질 평가는 남았다. R7은 보류다. 앱 Goal은 active다.

이전 R6 합성 연결 검증: 당시 상태 **LOCAL_ENTRYPOINT_UI_VERIFIED_ACTUAL_RECOVERY_PENDING**. 별도 `expert_main` 합성 복구 진입점과 검토·계획·AUDIT·복구 보고서의 API·live/history 표시를 연결했다. 변경 영향 Python 13파일의 382개 시험·45개 하위 시험과 Node 37개, 실제 브라우저 및 별도 main 프로세스 합성 검증을 통과했다. 실제 모델·검색 호출은 0회다. 실제 provider 전체 연결·자동 복구·품질 평가는 남았으며 앱 Goal은 active다.

## 작업 위치와 보존 원칙

| 구분 | 경로와 용도 |
|---|---|
| 통합 대상 | `C:/Users/kimjang/Documents/GitHub/llm_novel_dc_coommunity_parser` |
| 최신 구현 원본 | `C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser` |
| 공통 기준 커밋 | `007c9d40a62dbd24b062cd317fa780c8d743ba24` |
| 이번 개발 기록 | 기본 폴더의 `out/development_plan_20261010/` |
| 선행 인계 | [최근 채팅 통합 인계](PROJECT_CHAT_HANDOFF_20261010_KO.md) |

두 폴더 모두 미커밋 변경이 있으므로 폴더 전체 덮어쓰기와 일괄 stage·reset은 사용하지 않는다. 공통 커밋과 양쪽 파일을 대조하고, 실제 적용 대상의 원본 바이트·SHA-256·Git 상태와 충돌 해소 결과를 남긴다. 환경설정·인증정보·모델·DB·로그·기존 실행 결과를 소스와 함께 복사하지 않는다. `233b`의 최종 검증에 묶인 소스와 수령증은 그대로 보존하고, 기본 폴더의 후속 변경에는 새 검증 기록을 만든다.

## 단계와 완료 기준

| 단계 | 개발 내용 | 완료 기준 | 선행 조건 |
|---|---|---|---|
| P0 변경 보존과 통합 명세 | 양쪽 변경·의존성·충돌 조사, 적용 파일 목록과 백업 방식 확정 | primary 전용 변경 누락0, 미해결 충돌 목록 명시, 복구 가능한 적용 단위 | 완료된 인계·점검 |
| P1 실행 코드 통합 | 최신 문맥·발화·별칭·OCR·호출 장부와 필요한 시험·도구 통합 | 기본 폴더 import가 자기 `src`를 사용하고 핵심 회귀 통과, 외부 worktree 의존0 | P0 |
| P2 대시보드 표시 보완 | 사유·메모 분리, NSFW 상태, 중첩 실행 이력, R08 관측 표시 | live·history 양쪽에서 같은 실행의 데이터 조회, 누락·오인 표시 회귀 통과 | P1 |
| P3 실행 설정과 문맥 진단 | 실행 프로필·유효 설정 기록, 선택적 문맥·발화 구조 저장 및 표시 | 기본 실행과 검증 실행의 차이가 명확하고 producer→저장→API→UI 연결 확인 | P1, P2 계약 |
| P4 통합 검증과 운영 인계 | 저장 결과 화면 검증, 최종 소스 실제 실행, 문서 정리 | 시험·화면·실제 실행·의미 검토를 구분한 완료 보고서 | P1~P3 |
| R 후속 연구 | 회수·재정렬·NIL·지속 지식·계측·선택 실행 개선 | 각 단계별 고정 입력·비교 기준·독립 성능 판정 | P1~P3 이후 데이터 조건별 착수; 로컬 개발은 P4 실측과 독립 진행 |

P1~P4를 첫 번째 개발 묶음으로 삼는다. R 단계 전체 완료를 첫 배포의 조건으로 추가하지 않는다. P4 모델 실행이 차단된 동안에도 모델 호출 없이 수행할 수 있는 R 단계 구현·합성 검증은 계속한다. 실제 자료의 성능 평가와 P4 완료 조건은 그대로 유지한다. 구현, 로컬 시험, 실제 모델 실행, 의미 품질, formal KPI의 상태는 각각 기록한다.

## P0와 P1 최신 코드를 기본 폴더에 통합

1. `expert_main.py`, `src`, 관련 `tests`·`tools`·의존성 파일을 공통 커밋 기준으로 분류한다. 줄바꿈 차이와 코드 차이를 구분하고 원본 바이트 해시는 별도로 보존한다.
2. 최신 쪽에만 있는 필수 런타임 모듈을 먼저 선정한다. `context_projection_contract.py`, `source_context_explanation.py`, `source_speech_structure.py`와 실제 import 의존성이 포함돼야 한다. 일회성 조사·보고서 생성 도구는 실행 코드와 구분한다.
3. 양쪽에서 바뀐 파일은 3-way 병합 후보를 만들고 의미를 검토한다. 특히 primary의 CLI import 경계·대시보드 정적 자산·기존 연구 runner 변경을 보존한다. 충돌 마커가 없다는 사실만으로 검토 완료를 선언하지 않는다.
4. 적용 직전 백업과 적용 명세를 확정한 뒤 기본 폴더에 반영한다. 원본 worktree, Git index, 기존 결과 파일은 변경하지 않는다.
5. 기본 폴더에서 CLI import, 최종 source context, B14, reader state, 대시보드 현재 런 결속 시험을 묶어서 실행한다. 최신 디렉터리의 절대 경로를 코드에 넣어 동작시키는 임시 연결은 만들지 않는다.

완료 산출물은 적용 파일별 이전·이후 해시, primary 전용 변경 보존 근거, 필요한 의존성 목록, 실행 명령과 시험 결과다. 되돌릴 때는 해당 적용 명세의 파일만 복구하며 다른 작업의 변경을 되돌리지 않는다.

사전 조사에서는 대상904개 중 최신 쪽만 변경326개, 기본 폴더만 변경2개, 양쪽 변경10개, 내용 동일566개로 분류했다. 최신 쪽 변경326개를 일괄 복사하지 않는다. P1의 첫 후보는 최신 `src` 변경40개와 `expert_main.py`이며, monitor의 양쪽 차이3개는 P2와 함께 다룬다. `expert_main.py`와 `monitor/server.py`의 3-way 후보는 충돌이 없고 최신 내용과 같지만, 기본 폴더의 research benchmark·workflow6개는 스키마가 달라 별도 보존한다. 관련 시험은 자립 실행 가능한 것만 선정하며 옛 `out` 수령증 의존 시험이 섞인280개를 무조건 옮기지 않는다.

도구 후보는 `run_independent_plan.py`, `run_measurement_prereq_canary.py`, `run_paired_measurement_readback.py`, `run_recovery_sidecar_grouped_ab.py`다. 의존성과 실행 정책을 적용 단계에서 다시 확인한다. 측정 도구가 있다는 사실은 formal KPI 사용 조건 충족을 뜻하지 않는다. 통합 시험에는 설치된 Python을 재사용할 수 있지만 기본 폴더의 `src`와 실제 `module.__file__`를 확인해 이전 editable 설치가 최신 worktree를 몰래 참조하지 않도록 한다.

[통합 조사 보고서](../../out/development_plan_20261010/REPORT_KO.md)와 [정확한 적용 후보·보존 목록](../../out/development_plan_20261010/integration_selection_plan.json)에 runtime41개, 보존6개, dashboard3개, 도구4개, P1 시험15개와 fixture1개, P2 시험3개를 기록했다. ignore된 파일도 별도 조사했으며 추가 runtime src는 없었다. 승인 후 백업·해시 검사를 거쳐 고유67개 파일을 적용했고 primary import와 관련 회귀·화면을 검증했다. 사전 명세의 `PLAN_ONLY_NOT_APPLIED`는 당시 기록으로 유지하며 실제 적용은 [적용 수령증](../../out/development_plan_20261010/integration_apply_receipt.json), 후속 수정과 검증은 [구현 기록](EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md)을 따른다.

## P2 대시보드에서 누락 없이 확인

### 판정 사유와 분석 메모

`identity.reason`과 `reason_lines`는 판정 사유의 대체 관계로 유지하고, `analysis.notes`는 별도 분석 메모 구역에 표시한다. reason이 있어도 notes를 숨기지 않는다. notes만 있는 과거 결과도 읽을 수 있어야 하며 빈 값은 미기록으로 안내한다. 긴 내용은 펼침 기능을 제공하고 HTML escape를 유지한다.

NSFW는 boolean true, boolean false, 미기록·형식 불일치를 구분한다. 문자열 `"false"`를 true로 표시하거나, 미기록을 false로 바꾸지 않는다. 판정·메모·NSFW 모두 live와 history 상세에 같은 표시 함수를 사용한다.

### 중첩 실행 이력

기존 `out/expert_result_*.json`과 중첩된 실행 manifest가 가리키는 결과를 함께 조회한다. 임의 JSON 전체를 실행 결과로 간주하지 않는다. 목록에는 실행 ID, 결과 상대 경로, 완료 상태, 저장 건수와 설정 요약을 제공하고 기존 filename API는 호환성을 유지한다.

- 중첩 결과는 서버가 발견·검증한 인덱스의 불투명 `run_key`로 조회한다. 클라이언트가 전달한 절대 경로나 임의 상대 경로를 직접 열지 않는다.
- 경로를 해석한 뒤 `out` 내부인지 확인하고 manifest의 `output_file`과 대상 파일을 결속한다. 외부 symlink·경로 탈출·잘못된 키는 거부한다.
- 동일 basename, 같은 파일의 여러 manifest, 손상 manifest, pending snapshot, 부분 저장과 최종 완료를 구분한다. 정렬·탐색 상한·캐시 갱신 정책을 두어 대시보드 새로고침마다 큰 결과 파일을 모두 읽지 않는다.
- 동일 post ID가 여러 실행에 있어도 선택한 실행의 상세·로그를 유지한다. 최신 파일로 임의 대체하지 않는다.
- actual/replay 구분은 명시된 실행 모드에서 읽는다. 경로명으로 추측하지 않으며 미기록은 미확인으로 표시한다.

### R08 호출 기록과 측정 상태

live 상세 API에 필요한 `run_meta` 키와 실행 manifest 요약을 전달한다. 목록·SSE에는 큰 행 진단을 싣지 않는다. 화면에서 행별 저장 시점의 호출 장부·비용 trace와 실행 종료 시점의 계측 요약을 분리한다.

manifest는 `output_file`과 함께 존재하는 `run_id`·`publication_scope_id`를 행 기록과 대조한다. 값이 서로 다르면 종료 요약을 섞지 않고 결속 불일치로 표시한다. 경로를 재사용했지만 manifest가 이전 실행인 경우를 회귀 시험에 포함한다.

후속32 원본은 행별 receipt가 `PENDING_EXTERNAL_LEDGER_LINK`인 반면 종료 manifest의 linked count는32다. 두 값을 덮어써 하나의 성공 상태로 만들지 않는다. 관측 토큰도 집계 출처와 범위를 붙인다. 토큰 카드 합계, provider 관측, 정식 비교 KPI를 혼용하지 않고 `NOT_ESTIMABLE`, null, `UNBOUND_PARTIAL`을 그대로 설명한다.

변경 대상은 `src/llm_batch/monitor/server.py`, `static/index.html`, `static/presentation.js`와 대시보드 계약 시험이다. 완료 조건은 notes 동시 표시, 중첩 후속32 이력 선택, 행별·실행별 R08 구분, NSFW false·미기록 구분을 실제 브라우저에서 확인하는 것이다.

## P3 실행 설정과 문맥 진단을 저장

### 실행 프로필과 유효 설정

현재 VLM 기본 OFF·OCR 기본 ON·`PIPELINE_DECISION_CALL_LEDGER_MODE=OFF`를 무조건 모두 ON으로 바꾸지 않는다. 일반 실행, 최근 저부하 검증 실행, 정식 paired 측정을 구분하는 실행 설정을 명시한다. CLI·환경변수·프로필의 우선순위는 기존 개별 옵션의 동작을 보존하도록 설계하고 충돌 시 최종 유효값과 출처를 기록한다.

실행 시작 요약과 manifest·대시보드에 코드 위치와 revision 또는 source hash, VLM/OCR, ledger mode, dashboard 연결, requested/effective parallel, 압축 설정, 출력 위치를 표시한다. 인증정보와 endpoint의 비밀 query는 포함하지 않는다. 이미지 입력인데 VLM/OCR이 꺼진 경우 현재 의미 검토 준비 상태를 명확히 보여준다.

2026-10-12 사용자 지시에 따라 이후 expert_main 및 regression-safe grounding 계열 테스트런·검증런의 기본 요청 병렬도는 --parallel 12이며, 입력이 12건 미만이면 effective_parallel=min(input_count,12)로 줄어든다. BelowNormal, 실제 CPython 자식 단일 CPU, numeric threads1, 압축 OFF, 대시보드 ON의 저부하 조건은 유지하고 manifest의 requested/effective parallel을 함께 확인한다. 과거 R5 paired 측정의 parallel1 계약은 당시 이력으로 별도 보존한다.

### 구조화 문맥과 발화 진단

현재 원본 결과에는 전체 projection·speech graph가 저장돼 있지 않다. 다음 순서로 구현한다.

1. producer가 만든 문맥·발화 구조에서 진단용 필드를 선정하고 스키마 버전·크기 상한·생략 사유·원문 연결을 정의한다.
2. 기존 reason·reason_lines·primary subject·notes와 별도로 선택 저장한다. 저장 payload는 제목 확정이나 공식 URL 공개 권한을 갖지 않는다.
3. API와 대시보드에 발화자, 대상, 관계, 근거 위치를 표시하고 원본 진단은 접어서 제공한다. 오래된 결과에는 ‘이 실행에는 구조화 진단 미저장’이라고 표시한다.
4. 진단 ON/OFF에서 공개 결과가 같고 저장량 상한을 지키는지 검증한다. 없는 구조를 화면에서 새로 추론하지 않는다.

## P4 검증과 인계

| 검증 층 | 방법 | 통과 기준 |
|---|---|---|
| 소스 통합 | 적용 명세·import·선택 회귀를 묶어 검사 | 누락 의존성·충돌 마커0, primary 전용 변경 보존 |
| API와 표시 | 실제 저장32·과거 형식·누락 값·경로 예외를 사용 | 같은 런 결속, notes·상태 표시, 경로 경계와 호환성 통과 |
| 실제 화면 | 임시 loopback 대시보드에서 live와 history 확인 | 상세·이력·설정·측정 표시 일치, 콘솔 오류0, 원본 해시 불변 |
| 최종 코드 실제 실행 | 코드·입력·설정 고정 후 기존80을 새 산출물로 실행 | 정상 종료·저장/실패/대기 분모 기록, 마지막 B14 효과 확인 |
| 의미 품질 | 기존 MODEL_REFERENCE·UNJUDGED·확정 회귀 상태를 보존하고80 전행의 공개결과·원문을 대조하며 변경 행을 집중 검토 | 새 잘못된 작품 공개0을 대조한 범위에서 판정하고 미판정 행은 별도 기록, 회귀가 있으면 수정 또는 영향 기능 되돌림 |
| 정식 KPI | 아래 R5의 버전 계약과 비교 조건 충족 후 판독 | 충족 전에는 `NOT_ESTIMABLE` 유지 |

최종80 실행은 기존 원본을 재사용한 새 실행이며 독립 신규 표본 검증은 아니다. 첫 통합·UI 수정은 원격 모델 없이 시험하고, 새 실제 실행은 코드가 고정된 뒤 한 번의 검증 묶음으로 진행한다. 모든 모델 검증런에는 대시보드를 붙인다. 재생 결과를 새 실제 실행으로 부르거나 과거 result·manifest를 최신 코드 결과처럼 고치지 않는다.

원본32는 `233b/out`에 있으므로 기본 폴더 서버의 허용 경계 밖이다. 화면 시험은 테스트 프로세스의 결과 루트를 해당 원본 `out`으로 명시하는 읽기 전용 구성을 사용하거나 별도 임시 fixture로 수행한다. 원본 manifest의 절대 경로를 바꾸거나 API에서 외부 경로를 허용하는 방식으로 해결하지 않는다.

회귀 시험은 변경 영역별로 묶어서 실행한다. 작은 함수마다 시험을 반복하지 않으며 통과 후에는 새 변경·실패·미해결 우려가 있을 때만 넓힌다. 기존 점검의 서버37개·화면12개·문맥/진입46개와 subtests12개는 출발점이며 후속 코드 통과의 증거를 대신하지 않는다.

## 후속 연구 기능 개발 순서

아래 단계는 [연구 로드맵](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/docs/research/IMPROVEMENT_ROADMAP.md)의 잔여 범위다. 각 단계는 데이터와 비교 기준을 고정한 다음 착수한다. BM25·reranker·NIL·검색 정책을 한 번에 바꿔 효과 원인을 잃지 않는다.

| 순서 | 개발할 기능 | 산출물과 수용 기준 |
|---|---|---|
| R1 평가 기반 정리 | 후보·출처·선택·실패 단계의 재현 가능한 snapshot | 코드·corpus·입력·설정 버전, 80/32/재생 분모 분리, 기존 근거 보존 |
| R2 BM25 실제 후보 회수 | 작품 corpus용 연구 검색 adapter를 분리해 pipeline에 SHADOW 연결. 기존 제품의 BM25 본문 트리밍과 구분 | immutable candidate ID·출처 유지, lineage 중복 제거, Recall@K·candidate miss·lane별/union 회수율 비교. 후보 추가가 공개 권한을 만들지 않음 |
| R3 지속 커뮤니티 지식 | 수집 후보 ledger, 작품 별칭 registry, 일반 community lexicon을 분리하고 READ_ONLY snapshot 소비 | surface/sense/time/source/lineage와 경쟁 의미 보존, 수집→저장→소비 추적, 중앙 Slang DB 직접 승격 없이 작은 corpus로 품질 확인 |
| R4 학습 reranker와 NIL | 학습/평가 분리 → 후보 ID 재정렬 SHADOW → CAL 임계값 고정 → FROZEN 평가 | 새 후보 생성 금지, primary/previous/mentioned/comparison 역할 구분, backend 장애·candidate miss·ABSTAIN·UNAVAILABLE·NIL 분리. MRR·gold-present accuracy·coverage·selective risk와 전체 terminal 분모 병기 |
| R5 paired 계측 | 저부하 실행에 맞는 버전 계약과 BEFORE/AFTER RunSpec, 실제 호출·저장 연결 | dispatch/terminal/seal/link 결속, provider 관측·동일 mutable context 조건. 실제 비교 조건 충족 전 비용·품질 개선율 주장 금지 |
| R6 선택 계산과 복구 | 기존 REVIEW_ONLY/PLAN_ONLY 관측·source-only AFTER 측정·AUDIT_ONLY 복구 원장을 재사용해 제한된 recovery executor 구현 | 별도 attempt·명시 호출/시간 예산·중단 조건·동일 공개 guard, 회귀와 계측 확인 뒤 활성 범위 결정 |
| R7 production 전환 | 외부 authority와 full-scan 요건 검토 | 기존 `DEFERRED_P0_AUDIT_TRACK` 유지. 이번 통합·UI 개발의 선행 blocker로 복원하지 않음 |

OCR와 검색 근거 경계는 모든 확장 단계의 회귀 조건이다. 원시 OCR→검색 질의→근거→후보→공식 제목/URL 소비 경로를 기록하고 진단 검색과 제목 공개 권한을 구분한다. 검색 서비스가 정상이라는 사실과 공식 작품 근거가 확보됐다는 사실도 분리한다. `아생갤`·`갤러리`를 현실 커뮤니티명으로 일괄 처리하지 않는다.

R4는 학습 자료·모델·계산 자원을, R2/R3는 corpus 범위·출처·시간성과 재사용 근거를 먼저 정해야 한다. 기존 문서의 recall·NIL·risk 제안값은 확정된 완료 기준으로 복사하지 않는다. 수치 기준은 평가 결과를 보기 전에 고정한다.

통합 후 [R1~R6 코드 대조와 다음 구현 설계](../../out/development_plan_20261010/research_next_steps.md)를 작성했다. 기존 source-only AFTER 실행과 WAL reference-copy는 이미 연결돼 있으나 새로운 NIL 정답·운영 절감 근거가 아니다. recovery의 AUDIT_ONLY 제안·capability 원장도 실행기와 구별한다. 구형 구현 지문 경로는 R4에서 수리했고 새 합성 graph를 기본 검산기로 재생했다. 과거 ledger byte 불일치의 명시 거절은 보존했다. 원본 Golden18 정상 재생이나 실제 데이터 준비 완료를 뜻하지 않는다.

R5의 기존 v1/v2 parallel16·healthy search shard16 계약은 보존했다. 새 v3만 명시 policy·parallel1·START/END 관측을 검산한다. 원본은 REFERENCE_WAL_ONLY_NOT_A_MEASURED_ARM이며 이전 parallel1 결과를 새 paired 실측으로 소급 승격하지 않는다. 실제 소비자는 Slang OFF만 지원한다.

## 개발 진행 기록

- [x] 선행 점검과 최신 코드·저장 결과를 바탕으로 개발 단계와 수용 기준을 작성했다.
- [x] 기본 폴더와 `233b`의 코드 차이를 읽기 전용으로 조사하고 [파일 인벤토리](../../out/development_plan_20261010/integration_inventory.json)를 만들었다.
- [x] 대시보드와 연구 범위를 독립 검토하고 manifest 결속·원본 시험 경로·의미 검토 범위를 보완했다.
- [x] 사용자 승인 후 앱 Goal을 active로 등록했다.
- [x] P0 적용 대상·백업·충돌 해소 명세를 확정했다.
- [x] P1 기본 폴더에 최신 실행 코드를 통합하고 primary import·관련 회귀를 확인했다.
- [x] P2 메모·NSFW·중첩 이력·R08 표시를 구현하고 원본32의 API·실제 화면을 확인했다.
- [x] P3 유효 설정과 문맥 진단 저장·표시를 구현하고 producer→저장→API→live/history 연결을 확인했다.
- [ ] P4 전체 수용을 확정한다. 기존 기준 `20261013_181711_146907`의 병렬12 전체80 실행과 전행 리뷰는 완료했으며 의미 품질은 REVIEW다. 현재 source454의 통합·저장 이력 화면 검증과 문서 인계는 완료했지만 실제 모델 실행·효과는 미검증이고 대상12 명령은 차단으로 미시작이다.
- [x] R1 읽기 전용 평가 snapshot 모듈·CLI·시험28개와 저장80/32 검산을 완료했다. [운영 문서](RESEARCH_EVALUATION_SNAPSHOT_20261010_KO.md)에 원본·참조 미기록 한계를 남겼다.
- [x] R2의 고정 corpus BM25 adapter·pipeline SHADOW·저장·표시·명시 ID mapping 평가기를 구현하고 통합 회귀·브라우저·독립 검토를 통과했다. [R2 기록](CANDIDATE_RETRIEVAL_SHADOW_20261010_KO.md)을 따른다.
- [ ] R2 실제 corpus·reference ID 대응 자료와 실제 회수 성능 평가를 완료한다. 현재 FUNCTIONAL_VERIFIED / ACTUAL_DATA_PENDING이다.
- [x] [R3 커뮤니티 지식 READ_ONLY](COMMUNITY_KNOWLEDGE_READ_ONLY_20261010_KO.md)의 저장·조회·실제 Decoder 소비·설정·화면을 구현하고 Python 37개 파일의 시험 726개와 하위 시험 132개, 화면 표시 시험 24개·브라우저·독립 검토를 통과했다.
- [ ] R3 실제 source-backed corpus·sense 참조를 고정하고 품질을 평가한다.
- [x] R4 로컬 계약·SHADOW 연결·split/role/bridge 검산·하네스·대시보드를 구현하고 초기 v1 44파일916개＋하위139개·Node25개·독립 검토·브라우저를 통과했다. 당시 상태는 LOCAL_CONTRACTS_VERIFIED_MODEL_AND_ACTUAL_DATA_PENDING이었다.
- [x] Git 제외에 걸리던 회귀시험/helper13개에 명시 예외를 추가했다.
- [x] R4 학습 선형 baseline·optimizer·CLI와 CAL/FROZEN raw-score 평가기를 구현하고 합성 자료로 검증했다.
- [x] R4 일반 R2 실행의 제목 출현 MENTIONED 관측·저장·화면 표시를 연결하고 로컬 회귀를 통과했다.
- [x] R4 NIL head 학습·manifest v3·raw score 저장/표시·명시적 FROZEN event 변환을 합성 자료로 검증했다.
- [x] R4 CAL 전체 행 온도 학습·v2 artifact 재판독·로컬 CLI·기존 FROZEN 확률 소비를 합성 자료로 검증했다.
- [x] R4 명시적 FROZEN 재관측을 expert_main·저장·웹 화면에 연결했다.
- [x] R4 NIL 후보 순위·전체 terminal 분모·FROZEN 교정 평가와 로컬 보고서 CLI를 연결해 합성 자료로 검증했다.
- [x] R4 일반 source/ID/graph 자동 공급과 새 입력 추론을 로컬 검증했다.
- [x] R4 최신 semantic NIL/CAL의 actual readback·baseline 연결을 구현하고 합성 로컬 검증을 완료했다.
- [ ] R4 적격 실제 입력의 bound actual 전체 성공과 실제 교정 품질 수용을 완료한다.
- [x] R4 명시 원문 관계와 검증 자료의 별칭 관측을 expert_main·capture·화면 소스에 연결하고 Python·Node 합성 회귀로 검증했다.
- [x] R4 합성 저장 의미 관측 3사례의 live/history 6화면을 현재 IAB에서 확인했다. 정상 관측·미실행·capture 실패, API=저장값과 콘솔 오류·경고0을 검산했다. [새 화면 근거](../../out/development_plan_20261010/p4_reapproval_v1/semantics_browser_v1/receipt.json). 이전 Chrome 차단은 이력으로 보존하며 의미 모델 소비 성공·실자료 품질은 별도다.
- [x] R4 새 의미 정책을 pairwise/NIL 학습·실제 점수·전체 CAL·고정 FROZEN·실행 저장에 연결하고 합성 로컬 회귀로 검증했다.
- [ ] R4 실제 자료의 별칭·역할과 TRAIN/CAL/FROZEN 품질 수용을 완료한다. 합성 로컬 소비 검증으로 품질 목표를 완료하지 않는다.
- [ ] R4 적격 실제 TRAIN/CAL/FROZEN 및 NIL 실제 학습·확률 교정·품질 수용 판정을 완료한다.
- [x] R5 v3의 로컬 계약·실행 연결·화면을 구현·검증했다. 실제 paired 계측과 비용·품질은 미평가다.
- [x] R6 합성 복구 실행과 독립 판독을 구현·검증했다. Python 15파일의 405개 시험·179개 하위 시험을 저부하 조건에서 통과했다.
- [x] R6 별도 main 합성 진입점과 웹 live/history 표시를 연결했다.
- [x] R6 일반 main 자동 복구와 native 대시보드의 로컬 연결을 검증했다.
- [ ] R6 적격 실제 자료의 복구 품질·비용을 평가한다. 로컬 합성 검증은 실제 품질 수용이 아니다.

개발 결과는 이 진행 기록과 [TODO](TODO.md)·[CHECKLIST](CHECKLIST.md)에 함께 반영한다. 과거 점검 문서는 당시 사실을 보존하고 후속 결과 링크를 추가한다. 완료하지 않은 구현·실측을 체크하지 않는다.

명시 FROZEN 재관측의 설정·저장·화면 계약과 검증 근거는 [운영 기록](CANDIDATE_RERANKER_SHADOW_20261010_KO.md)을 따른다.


## 일반 입력 교정의 실행·저장·표시

`--candidate-inference SHADOW --inference-bundle <bundle.json> --inference-bundle-sha256 <raw-SHA>`를 기존 R2·고정 NIL 모델 옵션과 함께 사용한다. 기본 OFF이며 v2 의미 모델에는 의미 관측 SHADOW도 필요하다. 새 bundle은 명시된 source raw bytes·corpus·기존 CAL artifact를 묶으며 새 학습을 수행하지 않는다. 온도 수치 재생 검산과 새 온도 fit을 구분한다.

성공은 TEMPERATURE_APPLIED_BOUND_INFERENCE, 현재 고정 모델의 수치 검산, 저장 참조 SAVED를 함께 요구한다. 행의 candidate_reranker_inference/candidate_inference_capture와 manifest의 candidate_inference_policy를 보존한다. 화면은 현재 게시글·run/scope·CAL/model/원문 지문까지 대조한다. 후보가 비거나 잘렸거나 저장/검산에 실패하면 확률은 null이다. NIL 제안은 정답이나 공개 판정이 아니며 전체 웹 recall도 주장하지 않는다.

[정확한 API·bundle 구성·한계](../../out/development_plan_20261010/r4_general_inference_api_KO.md)와 [실제80 준비 보고서](../../out/development_plan_20261010/actual80_preparation_v1/report_ko.md)를 따른다. P4·실제 자료 품질·R6는 계속 미완료이며 Goal은 active다.
