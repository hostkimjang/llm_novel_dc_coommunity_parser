# 커뮤니티 분류와 댓글 NSFW 품질 수리

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

## 이전 적용·검증 기록

아래 SHA·수치·미완료 문장은 해당 수리 당시의 이력이다.

후속으로 [인물 역할 설명 수리](P4_SOURCE_SLANG_ROLE_REPAIR_20261012_KO.md)를 적용하고 통합 149개·하위59개를 검증했다. 아래 97개 시험과 SHA는 두 수리 적용 시점의 이력이다.

기존 실제80의 후속 수리 두 건을 기본 프로젝트 코드에 적용했다. **로컬 통합 검증 완료, 수정 후 전체80 실측과 의미 품질 수용은 미완료**다. Expert-main 테스트는 사용자 지시에 따라 `--parallel 12`·대시보드 ON을 유지한다.

## 달라진 동작

| 대상 | 수리 전 관측 | 적용한 동작과 제한 |
|---|---|---|
| 10·61번 커뮤니티 발화 | 원문 설명은 농담·커뮤니티 의견인데 최종 분류는 미해독 작품 참조 | 같은 작성자의 원문 위치·객체·범위·SHA가 검산된 설명을 좁은 분류 fallback에 연결했다. 각각 `community_banter/pure_meme`, `community_banter/realworld_social_talk`로 정합화한다. 작품 후보·약어·인용·댓글·이미지 경쟁 단서가 있으면 기존 경로를 유지한다. |
| 74번 댓글 NSFW | 최초 Arbiter false가 명시적인 댓글 표현과 충돌 | 원문의 전개/클리셰 주제와 추가 예시 요청, 유일한 typed ID를 가진 원댓글의 직접 성폭력 명사구를 함께 검산할 때 최종 NSFW를 true로 계산한다. 기존 Arbiter 응답은 보존한다. 모든 댓글이나 이미지 NSFW를 해결하는 규칙은 아니다. |
| NSFW 저장 검산 | 기존 final-source 필드 봉인에는 NSFW 값이 없었음 | 새 출력에만 별도 NSFW 값·근거 결정문을 결속한다. 실제 모델 값과 저장 payload의 false/null/문자열/키 삭제/analysis 삭제 변조를 거절한다. 과거 봉인 정의와 원본 결과는 그대로 둔다. |

원문은 전문가 호출 전에 고정한다. 정상 문자열+dict 혼합 댓글을 지원하며, 댓글 ID·순서·원문 변경과 서로 다른 content/text·HTML 선택은 분리한다. 인용·부정·질문·비유·검색 요약을 이 좁은 NSFW 양성 규칙으로 승격하지 않는다. 댓글 표현의 민감도를 판단하며 작성자의 지지, 현실 사건, 특정 작품이나 새로운 공개 권한은 추론하지 않는다. 기존16번의 명시 false도 유지했다.

공개 결과 schema와 대시보드 코드는 바꾸지 않았다. 기존 `analysis.is_nsfw` 표시를 사용하고, 원문 위치와 적용 전후 값은 기존 final-source 검산 로그의 `nsfw_content_observation`에 남긴다. 별도 근거 패널은 추가하지 않았다. [18864 화면](http://127.0.0.1:18864/)은 수정 전 완료80의 결과이며 이번 수리 결과를 새로 생성한 화면이 아니다.

## 적용과 검증 근거

- [통합 검증](../../out/p4_quality_followup_20261012/combined_v1/REPORT_KO.md): 6파일 **97 PASS·59 subtest PASS·실패/오류/스킵0**, pytest 10.52초. 기존 커뮤니티 단독 시험 수와 합산하지 않는다.
- 실제 serializer, expert_main의 결과 운반 클래스, 공개 WAL 생성·재개봉·저장 재판독을 사용했다. 원문 verifier·공개 guard·WAL 검산을 mock하지 않았으며 74번의 true와 공개 HOLD/null을 함께 확인했다.
- 커뮤니티 실제 저장 전문가 재현과 짧은 작품 감상·아생갤·인용·댓글·이미지/OCR 경쟁 경계를 확인했다. 이미지 시험은 합성 관측이며 실제 픽셀이나 OCR 정확성 검증이 아니다.
- 통합 시험 종료 시 보호 파일 **6,297개 불변**, 외부 네트워크·모델·검색·자식 프로세스 호출0. BelowNormal16384·affinity2·숫자 스레드5종 각1·동시 시험 프로세스1 조건을 지켰다.
- [커뮤니티 검토](../../out/p4_quality_followup_20261012/community_independent_review_v3/REPORT_KO.md), [NSFW 검토](../../out/p4_quality_followup_20261012/nsfw_independent_review_v2/REPORT_KO.md), [통합 독립 검토](../../out/p4_quality_followup_20261012/combined_independent_review_v1/REPORT_KO.md), [적용 수령증](../../out/p4_quality_followup_20261012/primary_applied_v1/receipt.json)에 검토 근거와 검증한 후보·적용 바이트의 일치를 기록했다.

현재 pipeline SHA는 `e277b85c09a1c537b3a9d12726a30519087d8c27a61c37785a0f2d781e4ae6b0`다. 기존 dirty 변경은 적용 전 백업으로 보존했고 새 시험 두 개와 실제74 전문가 fixture를 추가했다. 새 시험 두 개는 `.gitignore` 추적 예외를 추가했다. 시험은 격리된 제품 사본에서 수행했으며 적용 후 파일이 검증한 사본과 같은 바이트임을 확인했다.

## 실제80와 남은 작업

수정 전 실행 `20261012_145104_574531`의 요청12·실효12, 80/80·exit0 및 [최종 인계](../../out/development_plan_20261010/p4_reapproval_v1/final80_parallel12_v1/REVIEW_SUMMARY_KO.md)는 그대로 유효하다. **그 실행을 이번 수정 후 코드의 실측으로 소급하지 않는다.** 기존 리뷰 ACCEPT32·HOLD33·REPROCESS8·INFO_MISSING7과 48건 후속 조치도 덮어쓰지 않았다. 이번 10·61·74의 국소 수리 검증은 별도 증거다.

- [x] 커뮤니티 분류와 좁은 댓글 NSFW 수리, 원문/저장 경계 회귀, 검증 후보 적용.
- [x] 기존 명시 false·작품 공개 guard·과거 원본/봉인과 자료 준비 상태 보존.
- [ ] 8번의 근거 없는 인물 역할 설명과 18·49·57·58 등 나머지 품질 검토/수리.
- [ ] 남은 수리 범위 확정 후 최신 코드의 전체80 실행·대시보드 확인·전행 의미 검토.
- [ ] 사람 정답·권리·독립 holdout 및 R2~R6의 실제 자료/평가 선행 조건 충족.

사람 정답0·학습 준비0·권리 UNKNOWN·독립 holdout 없음·formal KPI NOT_ESTIMABLE이다. 품질 gate REVIEW와 Goal active를 유지하며 R7 production 전환은 보류다.
