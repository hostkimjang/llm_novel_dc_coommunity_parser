# Developer Docs Hub

이 디렉터리는 개발 TODO, 기능 개선, 런 리뷰, 체크리스트, 검증 결과를 한곳에서 추적하기 위한 운영 문서 허브다.

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
- `CODEX_KICKOFF_SURVEY_AND_LOOP.md`: Codex 세션 시작 시 현재 상태/다음 loop를 재구성하는 kickoff 절차
- `FULL_POST_JUDGE_RUNBOOK.md`: full-post judge 실행, 재시작, 산출물 계약
- `COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md`: completed779 remaining queue를 subagent/model/tool fan-out으로 반복 개선하는 copy-paste goal prompt
- `loop_reports/`: loop별 실행 보고서와 gate 판정 기록
- `QUALITATIVE_REVIEW_20260426.md`: 20k run 300건 전문가 정성 리뷰 결과
- `IMPROVEMENT_REGISTER.md`: 개선안의 문제 정의, 결정, 결과, 후속 검증 기록
- `VERIFICATION_RESULTS.md`: 감사 명령, 지표, 판정, 재검증 결과 누적
- `HISTORY.md`: 날짜별 개발/운영 히스토리와 확인 결과

개별 상세 문서는 기존 위치를 유지한다. 예를 들어 검색 shard 사건은 `docs/search_reliability_review_20260426.md`, WARP 구성은 `docs/warp_sharding.md`, slang DB 작업은 `docs/slang_db_improvement_todo.md`에 상세를 둔다.

현재 active operating contract는 repository root의 `goal.md`, `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`, 그리고 최신 변경 계약인 `docs/devs/GOAL_ARCHITECTURE_INTEGRATED_REGRESSION_SAFE_GROUNDING.md`를 기준으로 한다. 2026-06-30 최신 확정 report는 regression-safe grounding Loop179이다. Loop179은 Loop176 broader unittest failure cluster를 아키텍처 보강 phase로 흡수해 `src/llm_batch/promotion_gate.py`의 공통 `GroundingState`/`EvidenceRecord`/`PromotionDecision`/`GateReport`/`can_publish_title` layer를 추가했고, selected high-risk public-title publish paths를 shared gate로 배선했다. Loop179 authoritative broader unittest result는 `.venv312\Scripts\python.exe -m unittest discover --start-directory tests` 기준 `1299` tests, `0` failures, `0` errors, `OK`다. Artifacts는 `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop179_promotion_gate_architecture_review.md/json`, Data Analytics artifact `loop179_promotion_gate_architecture_data_analytics_artifact.json`, report `docs/devs/loop_reports/LOOP_179_REPORT_20260630.md`다. 이것은 architecture-phase unittest gate 통과이며 semantic/full-scan approval이 아니다. Source full completion `OPEN`, full-panel collateral approval `NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, overall goal completion `NOT_COMPLETE`를 유지한다.

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
