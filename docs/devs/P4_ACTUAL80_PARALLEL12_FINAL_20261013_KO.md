# 병렬 12 실제80 실행 결과와 후속 개발

새 실행 `20261013_060126_882644`은 parallel 12/12·대시보드 ON으로 80/80 저장 완료했다. 최종 검토는 A27/H25/R28/I0이며 품질 REVIEW다. 아래 초반의 A23/H41/R10/I6과 종료 근거는 직전 `233800` 실행의 기록이다. 최신 결속과 후속 수리는 현재 상태 구역을 따른다.

실행 `20261012_233800_447943`은 **요청·실효 병렬도 12/12, 대시보드 ON**으로 종료했다. 종료 코드0, 저장80/80, 대기0, 실패0이다. 실제 사용한 pipeline은 `68c13db8…`다. 통합 회귀를 통과한 후속 후보도 이 실행에 적용된 코드로 계산하지 않는다.

## 실행·저장·화면 확인

- [종료 검증](../../out/p4_quality_followup_20261012/actual80_source_quality_parallel12_v2/end_check_prep_v1/end_verification.json): 44개 통과. 실제 Python·launcher·supervisor 종료, 원본 입력·실행 소스293개·결과/WAL 결속을 확인했다.
- [이력 API 대조](../../out/p4_quality_followup_20261012/actual80_source_quality_parallel12_v2/history_check_prep_v1/run_first/receipt.json): 80행·13 GET·842개 검사 통과. 원시 NSFW 값/평가 상태, 메모, 설정, 저장된 결과를 대조했다.
- [실제 화면](../../out/p4_quality_followup_20261012/actual80_source_quality_parallel12_v2/browser_final_readback_v1/receipt.json): live100%·80/80·12 workers, 최종 이력80행·병렬12/12, 74번의 메모·규칙 양성 NSFW·구조화 진단·행별 장부와 종료 계측 분리를 확인했다. 콘솔 오류0이며 선택된 화면의 검증이다. 이미지 픽셀 또는 모든 상세 화면 검증으로 확대하지 않는다.
- [공개 값 비교](../../out/p4_quality_followup_20261012/actual80_source_quality_parallel12_v2/publication_delta_inventory_v1/REPORT_KO.md): 직전 실행 대비 동일77·변경3(1·12·72번). 변경은 정확도나 인과 효과의 증거가 아니다.

[대시보드](http://127.0.0.1:18866/)의 이력에서 직전 실행의 최종 결과를 볼 수 있다. live 화면은 새 실행을 표시한다. BelowNormal·1 logical CPU·수치 스레드 각1·HTTP admission4·압축OFF를 유지했다. HTTP admission 상한4는 요청/실효 worker 병렬도12와 별도 값이다.

## 최종 의미 검토

[최종80 검토](../../out/p4_quality_followup_20261012/actual80_source_quality_parallel12_v2/final_review_reconciled_v1/REVIEW_KO.md)는 **ACCEPT23·HOLD41·REPROCESS10·INFO_MISSING6**, 품질 게이트 **REVIEW**다. 사전76행은 같은 실행의 원문·댓글·전체 결과 canonical 바이트가 최종본과 정확히 일치할 때만 재사용했고 남은4행은 새로 읽었다. 중복·누락0이다. [계획 요약 필드 정정](../../out/p4_quality_followup_20261012/actual80_source_quality_parallel12_v2/final_review_reconciled_v1/PLAN_METADATA_CORRECTION_KO.md)은 원본 보조 필드의 옛 수치를 바로잡으며 실제76+4 결속과 라벨은 유지한다.

| 재처리 대상 | 확인된 문제 | 후속 개발 상태 |
|---|---|---|
| 18·32 | 요청·응답 관계가 없는 댓글 반응이 작품 후보로 남음 | 댓글 v5 적용 완료. 새 18번은 후보 오염 미관측이나 broad 근거 보류로 잠정 HOLD, 32번 새 검토 대기 |
| 34·35 | 문두 표면과 가설 풀이가 작품 후보로 남음 | 표면 수리 회귀 통과; v7의 비교 경계 2건은 시험 교정, 적용 완료·새 런 진행, 의미 검토 대기 |
| 39 | 인물·동명 작가·작품 비교 역할 혼합 | 작가 품평 v3·native NP v4 지정 회귀 통과, 실제 39 의미 수용 미확정 |
| 55·57 | 이전 로컬 수리가 실제 런의 unresolved 상태를 해결하지 못함 | 일반 문맥·scope 통합시험 통과, 적용 완료·새 런 진행, 의미 검토 대기 |
| 69 | 댓글 성적 폭력 표현이 false/MODEL_REPORTED로 남음 | run_003 NSFW 시험군 통과; 후속 코드 적용 완료·실측 효과 미확인 |
| 70·77 | 일반 장르 발화와 제목 상태/관련성 분류 충돌 | general v3 114개 통합시험 통과, 실제 라벨 보존 |

41건 HOLD에는 이미지 픽셀·약어 관계·정상 작품 회수·구조화 진단 역할·무관 검색 진단의 재사용 경계가 포함된다. 모두 오답으로 계산하지 않으며 공개 null이나 로컬 시험 통과만으로 ACCEPT로 바꾸지 않는다.

## 다음 검증과 완료 기준

직전 검증본 31개 파일의 primary 적용과 새 parallel 12 실제80 검토를 마쳤다. 확인된 의미 결함은 현재 상태 구역의 과제표에 따라 격리 후보에서 수리 중이다. 기존 결과를 소급 수정하지 않으며 전체 개발 완료로 처리하지 않는다.

## 이전 준비와 시험 이력

아래 수리 중·진행 문장은 당시 기록이며 현재 판정은 다음 현재 상태 구역을 따른다.

첫 통합 준비는 일부 후보의 CRLF와 baseline LF 차이를 전체 파일 충돌로 처리해 중단됐다. [준비 실패와 진단](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v1/prepared_001/ROOT_DIAGNOSIS.json)을 보존했으며 제품 시험은 시작하지 않았다. v2는 raw SHA를 유지하고 UTF-8 개행 차이만 기록한다. 실제 겹침은21830행의 scope 진단/일반 문맥 삽입 한 곳으로 좁혀 양쪽을 보존하도록 별도 검토했다. [통합 준비](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v2/prepared_002/preparation.json)가 통과했고 run_001의 단일pytest를 시작했다. [첫 시험 수령증](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v2/run_001/validation_receipt.json)은28파일·1,211개 수집,11 PASS·14 하위 시험 PASS·2 FAIL(maxfail2 중단)이다. 정상 quoted 작품명 두 경우를 가설 풀이로 제외하는 회귀이며 surface v4에서 수리한다. 기존 시험의 기대값은 유지한다. v4는 독서 부정 문맥의 명명 후보 과차단이 추가 발견돼 CHANGES_REQUIRED이며 v5에서 제품 의미를 수리한다. 전체1211개 실행·통과가 아니며 기존 PASS 수치와 합산하지 않는다. 보호 원본과 복사본 변경0, 외부 호출·자식프로세스·밖쓰기 시도0이다.

시험 도우미의 nodeid 전체 역슬래시 치환도 한글 매개변수 ID37개를 경로처럼 바꿨다. [관측 오류 진단](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v2/run_001/NODEID_OBSERVER_DIAGNOSIS.json)을 보존했고 v3 도우미는 파일 prefix만 정규화한다. 기존503개 시험의 raw ID와 새 raw ID를 보존해 대조하며 제품2FAIL을 숨기지 않는다.

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

## 이전 기록: helper v5 run_002 종료와 당시 수리 계획

아래는 run_002 종료 당시의 기록이다. 현재 상태는 위 run_003 구역을 따른다.

[helper v5 run_002 수령증](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v5/run_002/validation_receipt.json)은 **34개 전체 파일 + 별도 지정 3개 사례**를 끝까지 실행했다. 본 시험 **1,405개 중 1,399 PASS·6 FAIL**, 하위 시험 **204 PASS·0 FAIL**, 스킵·오류 0이다. 기존 503개 사례는 모두 통과했고 모든 본 시험의 setup·call·teardown을 한 번씩 실행했다. 전체 판정은 **FAILED_PRESERVED**다. 원본·사본 변경, 외부 연결·자식 프로세스·범위 밖 쓰기 audit 시도는 모두 0이다. 수령증 SHA는 `4f0edd12694f2e066b579b839dd3dc398e0b10e44eee24a4fb19311768033d82`다.

| 남은 시험군 | 실패 | 확인한 현상과 후속 작업 |
|---|---:|---|
| 표면·가설 후보의 실제 34·35 부분 재생 | 2 | 금지 가설의 작품 역할·공개 유입 검사는 통과했다. candidate_generation_miss가 원래 저장본 False와 달리 None이어서, 재생 입력의 producer 자료 누락과 제품 문제를 구분한다. |
| 작가 품평의 원문 귀속 | 1 | 두 본문 블록에 걸친 인용을 작성자 진술로 받아들였다. 원문 필드와 인용 범위를 함께 보존하는 수리를 진행한다. |
| native 명사구의 인용·가정 표현 | 3 | 친구의 인용 발화 1건과 작가/집필자 소유 표현의 희망·가정 2건이 현재 작품 지지로 남았다. 원래 양성 제목 회수와 화자·서법 경계를 함께 유지한다. |

[실패 원문과 관측](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v5/run_002/ROOT_FAILURE_GROUPS.json)을 보존했다. 현재 단계에는 실행 중인 모델·pytest 프로세스가 없다. 일반 문맥 v3 114개, scope adapter, 댓글 답변, 짧은 약어·인용 제목 회수, NSFW·OCR 설명·별칭 검색 정책과 관련 최종 공개 경계 시험은 이 묶음에서 통과했다. 이 결과만으로 기존 실제 80건을 새로 판정하거나 사람 정답으로 채택하지 않는다.

[제목 공개 adapter 검토](../../out/p4_quality_followup_20261013/title_gate_baseline_adapter_review_v1/REVIEW_KO.md)는 수정 전 코드에서도 실패했던 8개를 분리한다. fetched 입력을 보완한 4개는 기존 기대를 유지했고, 나머지 4개는 명시 hold·작성자 관계·미확인 OCR 계약에 맞춰 기대를 교정하면서 별도 합성 양성을 추가했다. 바뀐 기대와 합성 입력의 한계를 명시하며 제품 수리 8건으로 집계하지 않는다. 아생갤 등 실제 작품일 수 있는 표현에 대한 의미 검토는 별도로 남아 있다.

control SHA `9abb0150112c3126dca748ae78f1aa3d149e34f82d8cd8468c1857ea42b1779f`, 준비 SHA `c61b5b74e68721f7654bb63485b2e8f4c9225daba251fde83c367dee6421da0d`, 격리 pipeline SHA `50f66d60396a3cd485e4963f874ec0e6025dd67d6051013e5568658f1bd53ce6`다. primary `68c13db8…`와 Git index `98ad941c…`는 바꾸지 않았다.

실제 80건의 **A23·H41·R10·I6**, 품질 REVIEW와 Goal active를 유지한다. UI 후보의 별도 Node 85 PASS·3 선택 SKIP은 새 producer·브라우저 실측이 아니다. 다음 expert_main 실행은 **parallel 12·대시보드 ON·저부하**다.

## 이전 통합 시험·표시·관측 기록

아래는 각 시점의 결과와 당시 후속 계획이다. 현재 진행 여부는 위 최신 상태를 따른다.

[세 번째 시험](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v4/run_001/validation_receipt.json)은 **31파일 전체 + 기존1파일의 선택3사례**,1,278개 수집·9 PASS·18 하위 PASS·2 FAIL이다. 새 시험을 먼저 실행해49번의 `이거 작가 그림체 아는데`가 제목 후보로 남는 문제를 확인했다. 댓글 후보v4에서 수리하며 정상 답변 회수와 원문을 보존한다. maxfail2 중단으로 나머지 사례는 미실행이며 이전 수치와 합산하지 않는다. 선택3개는 정확하게 수집됐지만 실행·통과한 것은 아니다. 원본·사본 변경 및 audit 외부 시도는0이다. 수령증 SHA는 `3cbac12ed3f6e64989cc68f80ddfff01194396f529e82c3cfd9f261b45690b39`다. OCR 설명·별칭 검색 수리도 독립 정적 검토 후 통합했으나 해당 시험까지 실행되지 않았다.

[surface v5 독립 검토](../../out/p4_quality_followup_20261013/surface_hypothesis_review_v5/REVIEW_KO.md) 후 [두 번째 시험](../../out/p4_quality_followup_20261013/source_quality_followup_validation_v3/run_001/validation_receipt.json)은 **29파일·1,252개 수집,642 PASS·107 하위 PASS·2 FAIL**로 종료했다. maxfail2 조기 중단이므로 새 후보 전체가 실행·통과한 것은 아니다. 기존 인용 표제 회귀2건은 통과했다. 남은 실패는 `test_image_ocr_variant_reason_does_not_overstate_title_in_post`와 `test_raw_search_with_meta_call_sites_stay_guarded`이며 각각 OCR 설명의 원문 귀속과 raw 검색 호출 통제 경로를 조사·수리한다. 기대값은 유지한다. helper v3는 raw nodeid를 보존하고 파일 prefix만 정규화했다. 원본·사본 변경과 외부호출 시도는 없다. 수령증 SHA는 `0ae322803387b9fdc27de8df14400368de77373bda1551fe83f6dbe1ae2ced73`이다.

[대시보드 표시 후보](../../out/p4_quality_followup_20261013/source_scope_guard_display_candidate_v1/DESIGN_KO.md)는 JSON에만 보이던 상태 보정 guard의 검사 단계, 마지막 상태·사유, 진입 수, 첫 거절, 누적 적용 기록과 공개 권한을 개별 표시한다. [독립 검토](../../out/p4_quality_followup_20261013/source_scope_guard_display_review_v1/REPORT_KO.md)와 [Node 결과](../../out/p4_quality_followup_20261013/source_scope_guard_display_validation_v1/run_001/receipt.json)는 **85 PASS·3 SKIP·0 FAIL**이다. 3개는 별도 NATIVE/PROVIDER/INFERENCE readback 자료가 미설정된 선택 시험이다. 새 producer 실측이나 실제 브라우저 관측이 아니며 primary 미적용이다.

39번은 [부분 문맥 진단](../../out/p4_quality_followup_20261013/source_role39_author_trace_validation_v1/run_001/receipt.json)에서 최종 author_talk가 재관측됐다. 실제 네트워크0·원본/전문가 변경0이지만 NoExternal 검색 시도4건으로 진단 시험은 실패했다. [추적 도구 결함](../../out/p4_quality_followup_20261013/source_role39_author_trace_validation_v1/run_001/ROOT_OBSERVER_DIAGNOSIS.json)도 확인됐다. Python3.13 FrameLocalsProxy를 dict로만 검사해 지역 discussion_type의 전환을 놓쳤다. 부모 함수 반환후 값만으로 최초 대입 위치를 확정하지 않으며 관측 도구를 별도 v3로 수리한다. 미저장 fetch·최종 snippet 문맥을 발명하거나39 의미 품질이 수리됐다고 표시하지 않는다.

검증한 코드만 보존 절차를 거쳐 적용한다. 후속 expert_main 실측도 **`--parallel 12`·대시보드 ON·저부하**를 사용하고 manifest의 요청/실효값을 함께 확인한다. 새 결과의 의미 효과가 확인되기 전까지 현재10건 재처리 라벨을 유지한다.

Goal active, HUMAN GOLD0·학습 준비0·권리 UNKNOWN·독립 holdout 없음·formal KPI NOT_ESTIMABLE이다. 이번80은 R2/R3/R4/native OFF 실행이므로 해당 기능 ON 실측을 대신하지 않는다. R1~R6 수용 조건과 R7 production 보류도 유지한다.
