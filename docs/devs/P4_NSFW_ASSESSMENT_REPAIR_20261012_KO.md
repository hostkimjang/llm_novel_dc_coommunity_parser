# NSFW 평가 상태 구분 수리

<!-- source-quality-current:start -->

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

## 저장·표시 계약

새 optional 필드는 `analysis.nsfw_assessment_status`다. `MODEL_REPORTED`는 Arbiter의 유효 bool 보고, `SOURCE_RULE_POSITIVE`는 기존 원문/같은 이미지 fallback 또는 74번 source-bound 규칙 양성, `NOT_EVALUATED`는 유효 모델 bool이 없고 기존 규칙도 false인 경우다. legacy null·키 누락은 미기록으로 남긴다. 모델 false 보고도 이미지 전체가 안전하다는 검증은 아니다.

`type(value) is bool`인 모델값만 소비한다. 문자열 `"false"`, `"true"`, 숫자, null 등은 기존 fallback으로 보내며 모델 양성으로 강제변환하지 않는다. 유효 false/true 우선순위, 74번 예외, fallback의 어휘·조건과 작품 공개 guard는 그대로다. analysis가 원래 None이면 상태를 위해 새 객체를 만들지 않는다.

새 `source_bound_nsfw_v2` 결정문과 live receipt는 bool과 평가 상태를 함께 고정한다. 실제 serializer, main 결과 운반, publication WAL 재판독에서 상태 삭제·null·문자열·잘못된 enum·다른 유효 상태·bool 변조를 거절한다. 과거 receipt에는 새 검산을 소급 적용하지 않고 기존 final4 seal 계산을 보존한다. 새 상태는 공개 권한이나 작품 근거가 아니다.

## 확인한 범위

- [Python 통합 검증](../../out/p4_quality_followup_20261012/nsfw_assessment_validation_v1/REPORT_KO.md): **12파일 251 PASS·104 subtest PASS**, 실패·오류·스킵0, pytest 41.05초. 기존 slang/community/NSFW 회귀를 포함하며 과거 149개와 합산하지 않는다.
- 49번 [저장 원문·전문가 fixture](../../out/p4_quality_followup_20261012/nsfw_assessment_source49_v1/HANDOFF_KO.md)의 Gatekeeper/Discourse 두 출력과 같은 이미지 catalog만 부분 재구성했다. Arbiter를 만들어 넣지 않았고 false/NOT_EVALUATED·HOLD·WAL 재판독과 거짓 MODEL_REPORTED 변조 거절을 확인했다. 전체 당시 메모리 문맥·VLM 원응답·픽셀·공식 검색 전경로의 재생은 아니다.
- live/history 실제 파일 기반 ASGI API에서 상태 3종·legacy null·키 누락을 그대로 전달하고 BOUND를 유지했다. [별도 Node 검증](../../out/p4_quality_followup_20261012/nsfw_assessment_ui_validation_v1/receipt.json)은 **87 PASS·실패/스킵0**이며 합성 표시 범위다. 두 시험 수는 합산하지 않고 실제 브라우저 확인으로 부르지 않는다.
- [제품 독립 검토](../../out/p4_quality_followup_20261012/nsfw_assessment_independent_review_v1/REPORT_STATIC_KO.md)와 [UI 검토](../../out/p4_quality_followup_20261012/nsfw_assessment_ui_validation_v1/root_review.json)는 구체적 미해결 finding 없이 완료했다. [적용 수령증](../../out/p4_quality_followup_20261012/primary_applied_assessment_v1/receipt.json)은 시험한 8파일과 `.gitignore` 예외의 적용을 기록한다.
- 로컬 통합 시험에서 보호 파일6,307개 및 격리 소스 변경0, 외부 네트워크·모델·검색 호출0이었다. 이 호출0은 로컬 시험 범위이며 현재 실제80 실행을 뜻하지 않는다. 시작·끝 BelowNormal16384·affinity2·수치 스레드5종 각1·한 시험 프로세스를 확인했다. 기존 dirty 변경과 과거 실제80 두 실행·실제12·원문·리뷰는 보존했다.

적용 pipeline SHA는 `ee9088f69437617e613c382566b0d7a9a01abe6283a595eeffc5fc18a7c06d07`, models SHA는 `3747c35824ccbd43ee967aa2356d4e6e4fee2bab7ac069fe71e73508fefd625e`다. 표시 자산은 `20261012-nsfw-assessment-v1`이다. 이전 실제80 `20261012_145104_574531`의 80/80 기술 종료 및 ACCEPT32·HOLD33·REPROCESS8·INFO_MISSING7을 수정 후 판정으로 바꾸지 않는다.

## 시작·실행 중 live 화면의 이전 관측

[시작 live 상세 수령증](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/browser_start_readback.json)에서 root가 실제 CUA로 10번 `11718086`의 메모·원문 발화·`community_banter/pure_meme` 표시, 진단 `TRUNCATED`, 병렬12/12, manifest `BOUND`와 종료 false를 확인했다. [세 가지 NSFW 라벨 수령증](../../out/p4_quality_followup_20261012/actual80_parallel12_v1/browser_nsfw_states_readback.json)은 아래 실제 live 행 상세의 DOM 표시만 확인한 범위다.

| post_id | 관측한 live 라벨 |
|---|---|
|11718086|미평가 · NSFW 여부 미확인|
|11718092|true · NSFW 해당 · 규칙 양성|
|11718123|false · NSFW 해당 없음 · 모델 보고값|

두 관측의 콘솔 오류·경고는 0이다. 이는 **실행 중 선택한 live 화면의 표시 검산**이며 모델 판정의 정답·이미지 픽셀·최종 이력·전체80 종료·전행 의미 품질을 검증한 것은 아니다. 모델 false도 이미지 전체 안전 확인을 뜻하지 않는다. 이 관측 당시에는 실행 중이었고 최종/history·종료 검산이 미완료였다. 이후 종료·선택 화면 확인은 상단 근거를 따르며 품질 수용은 여전히 미완료다. 로컬 Node 합성 표시 시험과 이번 실제 live 관측은 별도 증거로 유지한다.

## 남은 작업

- [x] 49번의 미평가 상태 구분, strict bool 소비, legacy 호환, 저장/표시 계약을 로컬 검증 후 적용.
- [x] 적용 코드 ee9088f6의 전체80 기술 종료·선택된 최종 실제 대시보드 확인. 요청·실효12, 대시보드 ON, 기존 저부하 정책.
- [x] 최종 결과의59행 재사용 및 나머지21행 의미 검토 수행.
- [ ] 후속 조치·품질 수용. 전행 결속은 상단 수령증으로 확인했다. 후속 후보 실측 증거와 분리.
- [ ] 18·57번 잔여 제목 탐색/분류 축의 상태 정리 후보. 57번 NSFW true는 보존 대상이다.
- [ ] 58번 별칭·대상 역할·NSFW 해석 자료 보류. 약어 가능성으로 작품을 확정하거나 NSFW false를 강제하지 않는다.
- [ ] 사람 정답·재사용 권리·적격 TRAIN/CAL/FROZEN·R2~R6 실제 평가 조건과 품질 수용.

[남은 사례 조사](../../out/p4_quality_followup_20261012/remaining_semantic_triage_v1/REPORT_KO.md)는 조사 당시 근거로 보존한다. 이 중 49번의 상태 공백만 이번에 로컬 수리 완료이며 이미지 정답 확인은 아니다. HUMAN0·학습 준비0·권리 UNKNOWN·formal KPI NOT_ESTIMABLE·품질 REVIEW·Goal active·R7 보류를 유지한다.
