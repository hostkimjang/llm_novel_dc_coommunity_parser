# P4 재승인 실행 운영 인계

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

### 실행 식별과 종료 시점

END는 `2026-10-12T04:57:53.758722+00:00`, v2 종료 관측은 `2026-10-12T04:59:22.471144+00:00`이다. supervisor 세션/PID `93109/58804`, 실제 Python/가상환경 PID `60232/18848`은 이 종료한 실행의 식별자다. dashboard 세션/PID `3663/102652`, `http://127.0.0.1:18863`은 최종 화면 확인에 사용하는 기존 서버 기록이며 현재 health를 재검증했다고 주장하지 않는다. 실행 당시 BelowNormal·affinity2·논리 CPU1·수치 thread 5종 각1이었다. [PROCESS](../../out/p4_semantic_regression12_20261012/PROCESS.json)와 [END](../../out/p4_semantic_regression12_20261012/END_RECEIPT.json)를 보존한다.

## 실행 전 검색 서비스 복구 (13:35 KST 관측)

13:35 KST의 [서비스 확인 수령증](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/service_health.json)에서 지정 모델 `nvidia/Gemma-4-26B-A4B-NVFP4`, MCP 3352의 `readyz(status=ok, searxng=true)`, 검색 결과 3건을 확인했다. 앞선 timeout은 [복구 전 진단](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/docker_recovery_before.json)의 Docker WSL 엔진 연결 종료와 함께 발생했다. 사용자 승인 거절로 분류하지 않는다.

root의 복구 기록에 따르면 `Start-Service WSLService`는 권한 오류로 서비스 변경 없이 끝났다. 이후 DockerCli 종료와 기존 Desktop/backend 종료를 확인하고, 대기 중이던 root 조회 클라이언트 PID6836만 정리한 뒤 Docker Desktop을 숨김 재기동(PID71008)했다. 정상 재기동 뒤 WSLService Running·Docker Server 27.3.1을 확인했고, Exited255였던 이 프로젝트의 기존 MCP3352·SearchXNG19000·Crawl21235 컨테이너 3개만 `docker start`했다. 새 이미지·볼륨·컨테이너 생성과 설정 변경은 없다. [복구 후 기록](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/docker_recovery_after.json)은 이 작업 보고와 저장 health 판독을 구분한다. 다른 서비스나 Crawl 전체 기능의 정상 동작까지 검증한 것은 아니다.

13:35 KST 복구 기록 당시에는 v3 보완 중이고 새12는 미시작이었다. 이후 수정·시험·소스 동결과 [실행 직전 health](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_regression_v1/service_health_launch.json)의 10분 유효기간을 확인해 위 새 런을 시작했다. 복구 시점 수령증은 그대로 보존하며 서비스 복구를 의미 품질·정식 KPI 성공으로 바꾸지 않는다.

## 완료된 기존80의 기술 판독과 의미 검토

실행 `20261010_210300_688879`는 **80/80 처리·저장, 실패0·대기0, 종료 코드0**으로 완료됐다. `terminal_artifacts_finalized=true`이며 [종료 기술 수령증](../../out/development_plan_20261010/p4_reapproval_v1/terminal_readback_v1.json)은 **PASS_TECHNICAL_ONLY·5,289개 검사**다. END의 원본 보존 검산도 PASS다. 종료 UTC는 원본 수령증의 `2026-10-10T16:10:26.912677+00:00`이고, 독립 종료 판독은 `2026-10-12T03:38:52.286089+00:00`이다. 두 시점을 혼합하지 않는다.

80행을 원문과 대조한 네 에이전트 리뷰의 합계는 **ACCEPT32·HOLD36·REPROCESS7·INFO_MISSING5·REJECT0**다. 중복·누락은 없으며 [전행 검토·후속 조치](../../out/development_plan_20261010/p4_reapproval_v1/actual_review_packets_v1/REVIEW_SUMMARY_KO.md)에 정확한 결과 SHA·JSON 좌표와 행별 조치를 기록했다. **gate REVIEW**, 사람 정답0·학습 준비0·권리 UNKNOWN·전 행 기존 개발 노출을 유지한다. 의미 검토를 완료했다는 말은 모든 판단을 수용했다는 뜻이 아니다. 실제 품질 수용·정식 KPI는 **NOT_ESTIMABLE**다.

root는 원래 18859 서버의 실제 live **100%·80/80**을 관측했다. 현재 output 한 건을 우선 포함하는 수리 뒤, 새 코드의 별도 18862 서버에서 full out 이력 목록에 해당 run·완료80건·병렬1/1이 표시되는 것을 확인했다. [이력 복구 API 수령증](../../out/development_plan_20261010/p4_reapproval_v1/history_current_run_fix_v1/receipt.json)은 **493개 검사·80행 원문/analysis_result 불변·API BOUND**, dashboard 단위시험은 **75개 통과**, [독립 정적 리뷰](../../out/development_plan_20261010/p4_reapproval_v1/history_current_run_fix_v1/independent_review.json)는 PASS다. pytest 초기 시도는 미설치로 실행되지 않았으며 unittest 결과로 기록한다.

상세 화면은 11718077의 NSFW=false·진단 STORED, 8403713의 NSFW=true·진단 TRUNCATED, 마지막 8212001의 80/80·분석 메모·BOUND·정식 KPI 미산정을 root CUA로 확인했다. 콘솔 오류·경고는 0이다. 첫 두 상세는 API 수령증에도 있고, 마지막 상세는 root의 후속 관측 메시지를 근거로 별도 기록했다. 로컬 스크린샷 파일이 생성됐다고 주장하지 않는다.

**원래 18859 프로세스는 이전 코드이고, 18862는 새 코드 검증용 서버다.** 배포·기존 프로세스 갱신 또는 영구 운영 전환을 완료한 것이 아니다. 전체 탐색 상한·경고는 유지되며 모든 과거 이력이 빠짐없이 표시된다는 뜻도 아니다. 종료 당시 actual inference의 source417과 이후 UI/API 개발 소스를 구분한다. 이전 통합 리뷰의 history 미통과 표기는 그 문서 작성 시점이며, 이번 후속 기록으로 갱신한다.

[후보·역할 결함](../../out/development_plan_20261010/p4_reapproval_v1/candidate_findings_v1/REPORT_KO.md)과 [의미 상태·NSFW 결함](../../out/development_plan_20261010/p4_reapproval_v1/semantic_state_findings_v1/findings_KO.md)의 확정 결함 중 이번 수리 범위는 위 로컬 시험·독립 리뷰를 통과했고 새12 회귀로 확인 중이다. 후속48행 전체 또는 실제 의미 품질의 수리가 완료됐다는 뜻은 아니며, 기존 실제80 결과와 원본 리뷰는 변경하지 않는다.

이번 실행은 병렬1/1·dashboard ON·R2/R3/R4/native OFF다. 계측 LLM dispatch/terminal 658쌍은 원격 내부·MCP/OCR 전체 호출 수나 가격이 아니다. fresh paired 결속이 없어 formal KPI는 산정하지 않는다. 자원 근거는 START 관측과 최종 저장 설정 범위다. [향후 병렬12 정책](../../out/development_plan_20261010/p4_reapproval_v1/parallel12_policy_v1/receipt.json)은 다음 검증런의 요청12·실효 min(input_count,12)·dashboard ON이며 이번 완료 런에 소급하지 않는다.

Goal active를 유지한다. 이전 차단 기록과 아래 진행 snapshot·합성18화면은 각 단계의 원형 이력으로 남긴다.

## 이전 실행 시작·진행 관측 (당시 기록)

| 항목 | 현재 값 |
| --- | --- |
| supervisor 세션 / PID | `17644` / `77004` |
| 실제 Python / 가상환경 실행기 PID | `85764` / `32560` |
| 대시보드 세션 / PID | `76572` / `90388` |
| 대시보드 | [loopback 실시간 화면](http://127.0.0.1:18859) |
| 새 산출물 폴더 | [out/p4_primary_actual80_20261010](../../out/p4_primary_actual80_20261010/) |
| 실행 manifest | [run/result_manifest.json](../../out/p4_primary_actual80_20261010/run/result_manifest.json) |
| 최종 결과 예정 경로 | `out/p4_primary_actual80_20261010/run/result.json` |
| 실행기 | [p4_supervisor_reapproved.py](../../out/development_plan_20261010/p4_supervisor_reapproved.py) |

`2026-10-10T12:08:51.749469+00:00` UTC 기준 manifest는 입력 80건, 처리 1건, 저장 1건, 저장 대기 0건, 실패 기록 0건이며 `terminal_artifacts_finalized=false`다. 이는 그 시점의 진행 snapshot이고 완료·실패 총계를 확정한 수치가 아니다. 최신 진행은 살아 있는 manifest와 대시보드에서 확인한다.

실제 Python의 priority class 16384(BelowNormal), affinity mask 2·논리 CPU 1개·숫자 스레드 5종 각 1, 요청/실효 병렬 1/1을 확인했다. 대시보드는 ON·standalone forwarding, VLM/OCR는 ON이며 이미지 검토 준비 `ready=true`, 압축은 OFF다. 준비 상태가 이미지의 실제 처리 완료나 의미 품질을 뜻하지 않는다. 시작 전 source·시험 417개 지문이 고정됐고 이번 문서 갱신 중에도 제품·시험은 수정하지 않는다.

이번 preflight 범위는 `P4_CURRENT_SOURCE_EXISTING80_PARALLEL1_DASHBOARD_ON_R2_R3_R4_NATIVE_OFF`다. R2·R3·R4·native를 모두 켠 통합 실행이나 R5 paired 실측으로 확대해석하지 않는다. [시작 전 검산](../../out/development_plan_20261010/p4_reapproval_v1/preflight.json)의 `MODEL_RUN_NOT_STARTED`는 시작 전 시점이며 현재 실행 미시작을 뜻하지 않는다. [프로세스 기록](../../out/p4_primary_actual80_20261010/PROCESS.json)과 [진행 snapshot](../../out/development_plan_20261010/p4_reapproval_v1/docs/progress_snapshot.json)을 함께 본다.

운영 담당자는 IAB 탭 6에서 초기 live 0/80·history 접속과 콘솔 오류 0을 관측했다. 이 기록은 초기 접근 확인이며 전체 80건 화면·완료 상태·모든 기능의 실제 브라우저 검증 완료가 아니다. 이전 Chrome 차단 이력도 그대로 보존한다.

## 별도 합성 저장자료 화면 검증 (실제80 완료 검증과 구분)

[의미 관측 수령증](../../out/development_plan_20261010/p4_reapproval_v1/semantics_browser_v1/receipt.json)은 정상 관측·미실행·capture 실패 3사례의 live/history 6화면을 현재 IAB에서 확인한 근거다. API의 의미 관측·capture 필드가 저장값과 일치하며 콘솔 오류·경고는 0건이다. 관측 상태와 점수/교정 입력 미사용을 구분했다.

[P3 수령증](../../out/development_plan_20261010/p4_reapproval_v1/p3_browser_v1/receipt.json)은 기존 post123의 live/history 2화면과 41개 기술 검사 PASS를 기록한다. 분석 메모·판정 사유·NSFW false·진단·실행 설정을 표시했고, 미기록 scope는 PARTIAL, 완료 상태는 UNKNOWN으로 보존했다. 현재 whitelist 투영과 비교했으며 저장 run_meta 전체 객체 동일성으로 확대하지 않는다.

[일반 추론 수령증](../../out/development_plan_20261010/p4_reapproval_v1/inference_browser_v1/receipt.json)과 [native 복구 수령증](../../out/development_plan_20261010/p4_reapproval_v1/native_browser_v1/receipt.json)에서 각각 live/history 2화면을 확인했다. 이 두 경로는 저장된 API payload를 탐색용 어댑터로 전달한 현재 UI 검증이며, 새 producer나 생산 API 회귀 검증이 아니다. 일반 추론은 UNJUDGED·ABSTAIN·SHADOW 확률과 공개 권한 false를 구분했다. Native는 원래 미해결 결과와 별도 PUBLISH, 완료 행과 INCOMPLETE batch, 원격 UNKNOWN·가격 null을 구분했다. Native 내부 provider 영수증과 별도 전용 provider 화면의 검증 범위는 아래처럼 구분한다.

[R5 최종 수령증](../../out/development_plan_20261010/p4_reapproval_v1/r5_browser_v1/receipt.json)은 complete/partial의 live/history 4화면을 확인했다. complete는 행·manifest의 START/END를, partial은 START와 END null·관측 미완료를 보존했다. 상단 fixture 로드 완료를 paired 측정 완료로 해석하지 않는다. 최종 48개 검사는 PASS이며 앞선 complete 57개·partial 30개와 합산하지 않는다. 실제 paired 성공·비용·품질은 미평가다.

[독립 provider 수령증](../../out/development_plan_20261010/p4_reapproval_v1/provider_browser_v1/receipt.json)은 전용 live/history 2화면을 확인했다. 고정 row/bound는 보존하고 표시 manifest는 report.base에서 합성한 어댑터다. 원래 생산 API·companion·manifest·원장의 결속을 새로 검산한 것이 아니다. 입력 분모2에서 post101은 PROVIDER_EVIDENCE_STORED, post202는 NO_PLAN_PROVIDED로 남았다. GUARD_NOT_EVALUATED, 원격 UNKNOWN·가격 null·공개 권한 false를 유지하며 저장 성공을 native 공개 guard 성공으로 바꾸지 않았다.

총 화면 수는 의미 관측6 + P3 2 + 일반 추론2 + native2 + R5 4 + 독립 provider2 = 18이다. 각 검증의 콘솔 오류·경고는 0건이다. 소스 417개와 기존 fixture/payload 바이트는 보존됐고 새 producer·모델 호출이나 실제80 결과 본문 판독은 없다. 스크린샷은 대화 도구 이미지에만 있고 로컬 파일은 없다. 저장 capture 원문과 native 원장·결과를 이번 화면 검증에서 다시 열거나 재생한 것은 아니다. 의미 모델 소비 성공·전체 UI·실제80 기술적 종료·전행 의미 검토·실제 결과 최종 화면·품질 수용은 별도 게이트다. [화면 통합 검산](../../out/development_plan_20261010/p4_reapproval_v1/browser_round_v1/receipt.json)은 source417·fixture48 불변과 소유 preview 7개 PID 소멸을 확인했다. 실제80 Python85764·dashboard90388은 종료 대상에서 제외했다. 실제80의 종료 시 보존 검산은 별도다.

[미리보기 정리 기록](../../out/development_plan_20261010/p4_reapproval_v1/browser_round_v1/cleanup_note.json)에 따라 소유 프로세스는 명령행과 PID를 확인한 뒤 강제 종료했고 수거된 exec 종료 코드는1이다. 정상 종료/finally 수령증으로 주장하지 않는다. 탭·연결 종료 뒤 inference/native/provider helper 출력에서 관측한 `WinError 10053` trace는 화면 콘솔 오류0과 구분하며 제품 API·실제80의 실행 실패로 분류하지 않는다. 최초 정리 검사에서는 PID32912가 남아 수령증을 쓰지 않았고, exec 종료 수거 후 7개 모두 PID_NOT_FOUND를 확인했다. 상세 trace의 전체 로컬 로그는 없고 대화 도구의 일부 출력에 남아 있다.

`2026-10-10T14:02:59.557728+00:00` UTC의 manifest 진행 메타데이터는 입력 80건, 처리 46건, 저장 46건, 저장 대기 0건, 실패 기록 0건, `terminal_artifacts_finalized=false`다. [이번 진행 snapshot](../../out/development_plan_20261010/p4_reapproval_v1/docs_current_ui_v1/progress_snapshot_ui18.json)을 별도로 보존했다. 실제 결과 본문과 프로세스 상태는 이 문서 갱신에서 다시 읽거나 조회하지 않았으며, 실행 중 수치를 최종 종료 수치로 확정하지 않는다.

## 현재 남은 게이트

- [x] 수리 범위의 로컬 회귀·독립 리뷰 후 새12의 요청/실효12·저부하·dashboard ON 시작을 검산했다.
- [ ] 새12 종료 후 최종 기술 결속과 실제 의미 회귀를 검토한다.
- [x] 종료 코드0·80/80·최종 manifest·결과·체크포인트·새 WAL·원본 및 종료 당시 source417 보존을 독립 검산했다.
- [x] 새 결과80 전행의 에이전트 의미 검토 및 중복·누락 없는 통합을 완료했다. 의미 수용 게이트는 REVIEW다.
- [ ] 후속48행의 후보·역할·분류·NSFW·시각 근거 문제를 처리한다. 원본 리뷰를 덮어쓰지 않는 후속 기록으로 남긴다.
- [x] 현재 run의 history 복구를 API493·unittest75·독립 리뷰와 새 코드 18862의 목록/세 상세 관측으로 확인했다. 기존 18859 프로세스 업데이트·배포·전체 과거 이력 완전성은 수용 범위가 아니다.
- [ ] 사람 정답0·학습 준비0·권리 UNKNOWN·독립 holdout·R5 정식 paired 실측의 선행 조건을 충족한다. formal KPI NOT_ESTIMABLE·R7 보류는 유지한다.

이전 진행 문서와 기계 상태의 원본 바이트는 [이번 갱신 전 백업](../../out/development_plan_20261010/p4_reapproval_v1/docs_terminal_review_v1/backup_receipt.json)에 보존했다. 종료 당시 `END_RECEIPT.semantic_review=PENDING` 및 `PROCESS.status=RUNNING`은 이력 파일이며 수정하지 않았다. 현재 기계 상태는 [DEVELOPMENT_STATUS](../../out/development_plan_20261010/DEVELOPMENT_STATUS.json)를 따른다.

후속 변경 전 문서·상태는 [이력 관측 갱신 백업](../../out/development_plan_20261010/p4_reapproval_v1/docs_history_followup_v1/backup_receipt.json)에 보존했다. 앞선 문서·리뷰 수령증은 덮어쓰지 않았다.
