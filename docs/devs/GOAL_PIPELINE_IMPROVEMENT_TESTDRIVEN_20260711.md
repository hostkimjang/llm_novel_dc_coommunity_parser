# GOAL: LLM 파이프라인 개선 전·후 검증 루프 (2026-07-11)

> 2026-07-12 재개 상태: 사용자가 `goal 재개`를 명시해 전체 Goal은 `ACTIVE / NOT_COMPLETE`로 이어간다. 최신 계보는 P2 v8 → P3 v20 → P4 v21다. P3 readiness v2·actual preflight·policy v3 ABSTAIN 분모 hash-binding·정책/split/source/replay bound readback·6개 paired CI 정책 게이트, P4 cross-parent/label lineage·physical-call 독립 reader·exact recovered-arm witness·AFTER-only source route·source-bound execution envelope을 구현했다. 실제 DEV/CAL/FROZEN·동일 RunSpec fresh pair가 없어 `runtime_validation=NOT_RUN / semantic_quality=REVIEW-LOCKED / full_scan_approval=false`를 유지한다. 정책·자료·active production 자원 대기는 해당 actual 게이트만 보류하며 전체 Goal 종료가 아니다. 이전 `BLOCKED_HANDOFF`는 역사 상태이고 재개 뒤 blocker streak는 새 감사로 시작한다.

> 2026-09-02 supersession: 위 policy v3는 당시 분모 결속의 역사다. 신규 actual readiness/evaluation은 분모·최소 독립 group 30개·bootstrap 2,000회·percentile method를 hash-bound한 policy v4만 허용하며 v2/v3는 저장 정본 호환용이다.

> 2026-09-02 P0 실행 연속 상태: parser process launch provenance를 held-handle SHA·volume serial·128-bit file ID·ancestor namespace guard와 suspended child PID/time/reported image reopen에 결속했다. sandbox `15 PASS`, 전체 P0 `384 PASS`, 중앙 DB/journal `6/6` 불변이다. 그러나 `-B`도 기존 `.pyc`를 읽으므로 필수 `.py` 4개는 candidate manifest일 뿐 source closure가 아니다. actual·credited `0/40`, `0/20`, `PARSER_SANDBOX_NO_GO / ACTIVE_NOT_COMPLETE`를 유지한다.

> 2026-09-02 successor: unique empty pycache, source/import collision inventory, source parent·source/cache watcher로 좁은 `bounded_project_source_load_candidate_closure_verified=true`를 닫았다. focused `48/48`, 전체 P0 `407/407`, 비간섭 `6/6`이지만 parser dependency/runtime/stdlib/native/loaded-image closure와 external owner pin은 false다. 따라서 `ADOPT_BOUNDED_PROJECT_SOURCE_LOAD_CANDIDATE_CLOSURE_COMPONENT_ONLY / PARSER_DEPENDENCY_CLOSURE_NO_GO / PARSER_SANDBOX_NO_GO / ACTUAL_0_OF_40_0_OF_20 / METRICS_NOT_ESTIMABLE / REVIEW_LOCKED`를 유지한다.

> 2026-09-02 asymmetric successor: CNG ECDSA P-256/SHA-256과 RFC 5480 fingerprint, exact canonical preauthorization binding은 focused `15/15`, adjacent `78/78`, 전체 P0 `422/422`, 비간섭 `6/6`으로 통과했다. 다만 caller-presented pin 전체 대체 반례 때문에 `ASYMMETRIC_SIGNATURE_MATH_PASS / PRESENTED_PIN_ONLY / EXTERNAL_PROVISIONING_NO_GO / OWNER_STATE_NOT_YET_BOUND / ACTUAL_0_OF_40_0_OF_20 / PARSER_SANDBOX_NO_GO / ACTIVE_NOT_COMPLETE`다.

> 2026-09-02 OWNER_STATE successor: same-call raw3 fresh validation 뒤 object-identity+weakref private state를 atomic exact-once로 소비한다. clone/serialized receipt/raw·context·seal·PID tamper와 16-way race를 닫아 focused `25/25`, adjacent `91/91`, 전체 P0 `432/432`, 비간섭 `6/6`이다. 같은 raw 재검증은 새 state를 만들므로 `OWNER_STATE_PROCESS_LOCAL_HANDOFF_PASS / ARTIFACT_REPLAY_NO_GO / EXTERNAL_PROVISIONING_NO_GO / ACTUAL_0_OF_40_0_OF_20 / PARSER_SANDBOX_NO_GO / ACTIVE_NOT_COMPLETE`다. 다음은 기존 external-trust seal-id clone debt를 object-identity로 교체하는 것이다.

> 2026-09-02 trust-state successor: legacy external-trust exact clone이 seal id로 genuine key를 소비하는 공격을 재현하고 `dict[id]+weakref(original)`, recursive freeze, atomic pop과 failure-burn으로 교체했다. focused `37/37`, linked `62/62`, direct adjacent `137/137`, 전체 P0 `439/439`, 비간섭 `6/6`이다. `TRUST_STATE_OBJECT_IDENTITY_PASS / PROCESS_LOCAL_KEY_HANDOFF_ONLY / EXTERNAL_TRUST_AUTHORITY_NO_GO / ACTUAL_0_OF_40_0_OF_20 / ACTIVE_NOT_COMPLETE`이며 다음은 immutable asymmetric pin/owner key와 rollback-resistant time/revocation/durable nonce state plane이다.

> 2026-09-02 Windows pin candidate successor: fixed-name held pin, effective-token ACL deny, signed packet/protected parent/category handle와 store/parent watcher를 same-call CNG/`OWNER_STATE`에 결속했다. focused `14/14`, adjacent `73/73`, 전체 P0 `453/453`, 비간섭 `6/6`이다. positive는 controlled hold mock이고 실제 Windows는 current-user-owned/parent-overlap store fail-close뿐이므로 `ACL_BOUND_PIN_CANDIDATE_CONTRACT_PASS / ACTUAL_EXTERNAL_PROVISIONING_NO_GO / ACTUAL_0_OF_40_0_OF_20 / ACTIVE_NOT_COMPLETE`다.

> 2026-09-02 owner deployment projection v2 successor: v1 호환을 보존한 별도 body/signature/owner-anchor/receipt v2에 native service·결정적 SID, verifier PE/resource·Authenticode, WDAC/UMCI와 loaded CNG provider projection을 결속했다. 두 독립 감사가 최초 policy ACL verifier SID/service SID split을 재현했고 exact cross-binding으로 닫았다. focused `34/34`, bootstrap/fixed-store 포함 `56/56`, 전체 P0 `509/509`, 비간섭 `6/6`이다. 판정은 `OWNER_DEPLOYMENT_PROJECTION_V2_CONTRACT_PASS_HOST_AND_EXTERNAL_PROVISIONING_NO_GO / ACTUAL_0_OF_40_0_OF_20 / ACTIVE_NOT_COMPLETE`; 다음은 zero-input host preflight이고 그 뒤 blocker-only actual readiness compiler다.

> 2026-09-02 owner provisioning preflight successor: projection의 exact service config/resource selector와 fixed-store private v2 body handoff를 추가했다. zero-input preflight는 outer/contract/bootstrap/body/projection을 재검증한 뒤 direct SCM config와 held image identity만 candidate로 관측하며, v1·forged/resealed material은 SCM 전에 거부한다. independent audit의 bool/int·incomplete receipt·invalid-outer truth 결함을 닫아 preflight `11/11`, direct adjacent `67/67`, 전체 P0 `520/520`이다. current host는 `failure_stage=FIXED_STORE / NO_GO`; service token/resource/Authenticode/WDAC/provider/time/native observer/external provisioning과 actual `40+20`은 여전히 미완료다.

> 2026-09-03 annotation packet V2 successor: result-free subject/target을 child15/member16 packet으로 묶고 Windows held-handle reader, owner P-256 preauthorization, exact one-step supervisor를 같은 additive V2 경계로 닫았다. manifest split-view, packet-dir input collision과 callable check/use 교체 공격을 수정해 focused `15/26/16/18`, 전체 P0 `836/836`, 비간섭 `6/6`이다. 모든 단계는 `ADOPT_COMPONENT_ONLY / NO_GO_AUTHORITY`; external key/time/revocation/durable nonce/root/code/write-deny/runtime/semantic evidence 전 actual `0/40·0/20`, metric/P0/Pyserini/production/full scan `NO_GO / ACTIVE_NOT_COMPLETE`다.

> 이 목표는 Loop643을 같은 조건으로 다시 돌리는 목표가 아니다. 저장된 결과를 이용한 새 아키텍처·하네스 개선 흐름이다. 진행 중인 104,502건 실행에는 개입하지 않으며, 개선마다 `기준선 → 일반화 구현 → 동일 조건 개선 후 → 게시글별 비교 → 다음 결정`을 반복한다.

> 현재 P2 연속 상태: 최종 공개 판정 exact-once는 Golden18 저장본·합성 범위에서 `commit 0→18 / replay no-op 18 / public·full row 불변 18/18 / attacks 21/21 / false GO 0`으로 검증했다. 실제 새 runtime은 `NOT_RUN`, 의미 품질은 `REVIEW-LOCKED`, `full_scan_approval=false`이므로 목표는 계속 `ACTIVE / NOT_COMPLETE`다.

> 현재 P3 연속 상태 v18: readiness v2가 actual 정책 파일 path·raw SHA·bytes를 P1·라벨 원장과 함께 재생한다. `actual-preflight`는 쓰기·runtime 없이 필수 입력·replay 6종·readiness·bound readback 가능 여부를 회계한다. bound runner는 replay base shadow·score vector·보정 산출물·prediction의 parser·frozen coverage·split/policy 결속까지 검증한다. Golden18은 ready `0/18`이고 실제 지표는 전부 `null`이므로 판정은 `NO_GO_ACTUAL_DATASET_NOT_READY / IMPLEMENTED_READ_ONLY_NO_ACTUAL_PACKET / IMPLEMENTED_V2_BOUND_RUNNER_NO_ACTUAL_ARTIFACT / IMPLEMENTED_POLICY_BOUND_NO_ACTUAL_OUTPUT / NOT_RUN / REVIEW-LOCKED / full_scan_approval=false / ACTIVE_NOT_COMPLETE`다.

> 현재 P4 연속 상태 v19: physical-call 원장·writer 독립 reader, AFTER source-only 측정 라우터, paired RunSpec/source replay, authoritative-WAL fresh 복구 게이트, exact recovered-arm witness와 P3/P4 교차 부모·라벨 계보 검증을 구현했다. witness가 source manifest/result/checkpoint/pending·recovered output·claim·WAL·single-attempt ledger·AFTER route를 모두 재생하지 못하면 recovered arm을 거부한다. Golden18은 full-expert `18`, cheap `0`; actual safe coverage·calls/post·회피율·after wall time은 전부 `null/NOT_ESTIMABLE`이다. reference-copy 0-call과 합성 `16→8`·50%는 실제 절감률이 아니며 적대 공격 `20/20`, false cheap `0`이다. 판정은 `GO_P4_SHADOW_CONTRACT_FOUNDATION_ONLY / NOT_RUN / REVIEW-LOCKED / full_scan_approval=false / ACTIVE_NOT_COMPLETE`다.

## 복사해서 바로 쓰는 목표 프롬프트

```text
/goal
이 작업은 `llm_novel_dc_coommunity_parser`의 미완료 파이프라인 개선 전·후 검증 목표를 이어가는 것이다. 새 P1-only 목표나 Loop643 동일 fingerprint 재실행이 아니다. 저장된 실제 결과와 합성 계약 시험을 함께 쓰되 서로 다른 증거로 표시하고, 현재 진행 중인 104,502건 production 실행은 절대 중지·재시작·수정하지 않는다.

필독: `AGENTS.md`, `goal.md`, `docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md`, `docs/devs/REGRESSION_SAFE_GROUNDING_BOUNDED_CONVERGENCE_PROTOCOL.md`, `docs/devs/LLM_PIPELINE_ARCHITECTURE_RESEARCH_20260711.md`, `docs/devs/loop_reports/LOOP_643_REPORT_20260711.md`, 이 문서, `tools/run_pipeline_improvement_harness.py`, 최신 하네스 RunSpec/비교 산출물. 시작할 때 live manifest·process·dashboard를 다시 읽고 고정 수치로 믿지 않는다.

현재 증거:
- P0-A 게이트 기능: `promotion_gate.py`에 optional typed `RetrievalState`가 있으며 기본 None/default는 기존 v2 fingerprint와 판정을 바꾸지 않는다. 실제 검색 상태를 만드는 live 경로 배선은 아직 미완료다.
- P0-B 실제 저장본 정적 투영: Loop643 Golden18에서 post_id 18/18 완전성, 현재 게이트의 저장 baseline 판정 재현 5/5, 필수 검색 미복구 5건, unsafe public publish 1→0, candidate missing 0, 검색 blocker 5→5다. 결과는 `PARTIAL_SAFETY_IMPROVEMENT_NOT_RUNTIME_VALIDATED`이며 runtime/정확도/승인이 아니다.
- 합성 계약 probe 7행은 unsafe 5→0, 정상 공개 2→2다. 이 5를 실제 Loop643 unsafe 1과 섞지 않는다.
- P1 로컬 completeness: 상류 제목 순위 단계는 정책 필터 뒤 고유 제목을 cap 6 전까지 세고, serializer는 로컬 고유 후보를 끝까지 센 뒤 최대 24개만 보존한다. 제목 7개 `TRUNCATED 7→6`, serializer 후보 25개 `TRUNCATED 25→24`를 검출하며 이 로컬 장부만으로는 `COMPLETE`를 만들지 않는다. 이 합성 잘림 탐지 `0→2`는 정확도 향상이 아니다.
- P1 전문가 단계 진단: Gatekeeper 1곳, Decoder 1곳, Verifier 2곳, Arbiter 3곳의 실제 cap 직전에 `candidate_stage_receipt_v1`을 남긴다. 합성 cap+1 `7/7 TRUNCATED`, 정확히 cap·cap 밖 중복 오탐 `0`, 유지 출력 `9/9` 불변이다. 다른 경로가 후보를 회복할 수 있으므로 이 상태는 CandidateSet completeness나 확률에 합성하지 않는다.
- P1 producer completion proof: canonical query/search/fetch bounded plan과 실제 receipt를 결합했다. 사전 고정 정상 search+fetch 1건만 `COMPLETE(계획 범위 완료)`, cache provenance 미결합·누락·저하/오류·조기 종료 4건은 `UNKNOWN`, raw `11→10` 손실 1건은 `TRUNCATED`, 거짓 COMPLETE는 `0`이다. 웹 전체 열거·정확도·실제 runtime 증거가 아니다.
- P2 publication exact-once: 입력 SHA·post_id 순서·전체 판정 설정·release/slang provenance를 scope에 결속하고, scope/post_id 첫 정상 판정과 복구 행을 WAL에 한 번만 확정한다. Golden18 commit `0→18`, replay no-op `18`, public/full row 불변 `18/18`; 합성 공격 `21/21`, false GO `0`이다. 실제 runtime·의미 정확도 증거가 아니다.
- P3 정확도 퍼센트 기반: 정답 사건은 후보 ID 또는 NIL이고 ABSTAIN은 행동이다. 외부 예상 행과 producer·AFTER·baseline을 각각 읽고 P1-bound 라벨 원장에서 readiness를 재생한다. actual-preflight는 필수 입력과 replay 6종을 무쓰기 점검하고, bound runner는 실제 parser와 frozen coverage까지 재생한다. 여섯 paired CI 정책 게이트를 모두 통과해야 actual shadow GO이며, 실제 자료가 없으므로 Golden18 지표는 전부 null이다.
- P4 선택적 비용 측정: physical-call ledger와 독립 reader가 send·retry·terminal·token을 행별로 재계산한다. P3가 사용한 P1/P2 및 라벨 원장과 P4 입력이 같은지 exact path/bytes/SHA로 대조한다. `SOURCE_ONLY_V1` early route는 REQUIRED/FRESH/AFTER/`FROZEN_OFF`에서만 작동하며 위험 신호가 있으면 full, 신호가 없는 행만 `CHEAP_NIL_MEASUREMENT`로 분류한다. 이 cheap 결과는 authoritative WAL reference copy이므로 `REFERENCE_COPY_COST_ONLY` 반사실 수치이며 실제 production 절감이 아니다. actual paired run 전에는 비용 KPI가 null이다.
- `semantic_quality=REVIEW-LOCKED`, production `full_scan_approval=false`, 전체 goal은 ACTIVE/NOT_COMPLETE다.

비간섭 계약:
1. active 104k manifest/result/checkpoint/pending/log/slang DB/process/8080 dashboard에 쓰지 않는다. 같은 LLM/MCP 자원을 쓰는 새 runtime도 시작하지 않는다.
2. active run이 끝날 때까지 허용하는 것은 정적 비교, 합성 계약 시험, unit test, 문서·하네스 개선이다. 이때 runtime 상태는 `BLOCKED_ACTIVE_PRODUCTION_RUN`이지만 goal 자체를 blocked로 종료하지 않는다.
3. 후속 runtime은 별도 input/output/prefix와 별도 dashboard 연결을 사용한다. `--parallel 16`(effective=min), dashboard ON(`--no-dashboard` 금지), search non-light/healthy16, `--reuse-shards-only`, `--slang-db off` 또는 read-only snapshot, VLM/OCR 필요 행은 READY를 강제한다.

각 개선 회차:
1. immutable RunSpec을 만든다. input byte SHA, post_id order/set SHA, baseline/result/gate SHA, code/prompt/model/config/search/VLM/OCR/slang snapshot, requested/effective parallel, dashboard, 의도한 treatment를 기록한다. 의도한 변경 외 고정 조건이 다르면 비교를 중단한다.
2. 개선 전 기준선을 정확히 한 번 측정한다. 실제 저장 artifact 기반 수치와 합성 probe 수치를 별도 칸에 둔다.
3. post_id/title literal 없이 일반화 계약을 최소 변경으로 구현한다. 기본 no-op 호환을 유지하고 공개 차단 시 candidate를 보존한다.
4. py_compile, focused contract tests, 영향 모듈 tests, 기존 publication/search/candidate gates를 실행한다.
5. 동일 RunSpec으로 개선 후를 측정한다. input/baseline/after의 missing/extra/duplicate=0, 원 순서, artifact SHA를 검증한다.
6. post_id별로 IMPROVED/SAME/REGRESSED/UNJUDGED/RUNTIME_INVALID를 기록하고 품질·검색·publication·runtime·승인을 분리한다. hard regression 1건이면 채택하지 않는다.
7. 한국어 before/after 보고서와 goal/TODO/CHECKLIST/HISTORY/VERIFICATION/IMPROVEMENT 문서를 같은 회차에 갱신한다.

정확도 퍼센트 계약:
- 정답 사건은 상호배타적인 `Y ∈ {candidate_id, NIL}`로 정의하고 후보별 `p(candidate_i)`와 `p(NIL)`의 합을 1로 만든다. `ABSTAIN`은 정답 클래스가 아니라 위험 기준 초과 때의 운영 행동이며, 별도 위험값은 `p(error | chosen_action)`로 기록한다.
- 위 확률은 실제 결과를 바꾸지 않는 shadow 필드로만 시작한다. 정답 후보 누락은 calibration 실패가 아니라 candidate-set recall 실패로 분리한다.
- 고정 holdout 정답이 없으면 null과 `NOT_AVAILABLE_UNCALIBRATED`를 기록하며 숫자를 만들지 않는다.
- 개발·보정·최종 동결 표본을 게시글 그룹·본문·출처·후보 묶음·작품 단위로 겹치지 않게 나누고, 위험 계층별 candidate-set recall, 사전 고정 ECE 구간, Brier 또는 자연로그 손실, NIL 정밀도/재현율, risk-coverage와 신뢰구간을 측정한다. 실제 필요한 표본 수와 임계값은 목표 오차폭·허용 오류 위험을 먼저 정한 뒤 RunSpec에 고정한다.
- 평가 시작 시 입력 Mapping을 고정 snapshot으로 복제하고 원본 기본 shadow·score·artifact로 재생한다. 검색 blocker가 하나라도 있으면 headline 지표를 전부 null로 둔다. actual-readback v2가 있어도 실제 expected universe·producer·AFTER·baseline·metric output이 없으면 `NOT_ESTIMABLE`로 차단한다.
- 실제 coverage, 선택 위험 신뢰상한, retrieval fail-close와 정확도·Brier·log-loss·ECE·선택 위험·AURC의 paired CI 정책 게이트를 actual frozen output에서 모두 통과하기 전에는 전환 금지다. 검색 실패나 후보 생성 누락을 높은 퍼센트로 덮지 않는다.

선택적 비용 라우팅 계약:
- 라우터는 `FULL_EXPERT_REQUIRED` 또는 `CHEAP_RULE_ELIGIBLE`을 기록하지만 `action_applied=false`, `route_applied=false`, `operational_effect=NONE_SHADOW_ONLY`를 유지한다.
- 검색 실패·저하·미확인, 후보 UNKNOWN/TRUNCATED, 복수 작품·identity conflict, VLM/OCR 누락·충돌, HOLD·격리·미판결, scope/source/budget/calibration/terminal 불일치를 hard risk로 합친다.
- source reader 기반은 구현됐지만 actual paired artifact가 없으면 모든 실제 KPI를 `NOT_ESTIMABLE`로 닫는다. 합성 fixture와 reference-copy cheap 후보는 계산 산술만 허용하고 actual 성능 주장에는 사용하지 않는다.
- `DecisionCostTrace`는 publication scope/run/input index/post_id에 결속하고, 결측·bool·빈 문자열·음수 count는 0이 아니라 null로 둔다. expert call event가 없는 aggregate는 `PARTIAL_AGGREGATE_NO_CALL_EVENTS`다.
- RunSpec의 `implementation_contract`는 저장된 artifact map 내부 해시만 맞추는 것으로 충분하지 않다. 현재 하네스가 계산한 전체 artifact 이름·경로·파일 SHA 집합과 정확히 같아야 하며 항목 삭제·대체 후 self hash 재계산도 거부한다.
- actual headline은 safe auto coverage, expert escalation, calls/post, call avoidance, wall time과 정확도 guardrail을 분리한다. 가격표의 출처·시점·통화가 RunSpec에 고정되기 전에는 금액 비용을 만들지 않는다.
- 물리 호출 원장은 `run/scope/post/row_attempt/logical_call/call_id`, stage/model, retry parent, terminal, usage provenance를 결속한다. raw prompt/response는 저장하지 않으며 writer aggregate를 actual KPI로 직접 승격하지 않는다.
- REQUIRED 측정은 모든 행의 기존 authoritative WAL reference를 provider 호출 전에 요구하고, fresh 결과는 공개 WAL에 쓰지 않는다. fresh recovery 게이트는 구현됐지만 실제 중단·재시작 runtime 증거는 없다.
- actual 전환은 P3 `FROZEN_ACTUAL` bytes/coverage/payload/source readback, 독립 call-ledger readback, **fresh BEFORE와 fresh AFTER 양쪽 새 실행**, hard regression 0, public/CandidateSet 비간섭을 모두 통과해야 한다.
- 비용이 좋아도 candidate-set recall→top-label/NIL→calibration→risk-coverage 정확도 계약이 미통과면 cheap routing은 금지한다.

현재 P0 정적 fail-close, P1 CandidateSet/NIL·후보 잘림·bounded producer proof, P2 exact-once 저장본·합성 검증, P3 actual reader·bootstrap 기반, P4 bounded physical-call ledger·독립 reader·측정 라우터·paired source replay까지 진행했다. active 104k 종료 뒤 별도 동일 입력 runtime에서 실제 retrieval state와 P2 WAL의 정상 완료·강제 중단·재시작을 검증한다. 실제 COMPLETE holdout·겹치지 않는 라벨 자료·completed readback·실제 구간 전에는 P3 실제 확률을 만들지 않으며, actual paired ledger readback 전에는 P4 절감률을 만들거나 cheap 경로를 적용하지 않는다.

회차 판정은 `IMPROVEMENT_VERIFIED_CONTINUE`, `NO_DELTA_REDESIGN`, `REGRESSION_ROLLBACK_REQUIRED`, `PLATEAU_AUDIT` 중 하나다. 최종 goal은 bounded protocol의 `COMPLETE_GO`, `COMPLETE_SAFE_TERMINAL`, strict 3-turn 외부 blocker의 `BLOCKED_HANDOFF` 중 하나로만 닫는다. queue0/runtime 완료/dashboard 초록/정적 투영만으로 complete나 production GO를 선언하지 않는다.
```

## 현재 기준점

| 구분 | 상태 | 근거 |
| --- | --- | --- |
| P0-A 검색 상태형 게이트 | `GO_GATE_ONLY / NOT_WIRED` | `RetrievalState`는 opt-in이며 live 검색 상태 배선은 미완료 |
| P0-B 실제 저장본 정적 비교 | `PARTIAL_SAFETY_IMPROVEMENT_NOT_RUNTIME_VALIDATED` | baseline gate replay `5/5`, unsafe publish `1→0`, blocker `5→5`, 후보 누락 `0`, retrieval evidence `NO-GO` |
| P0 합성 계약 시험 | `GO_SYNTHETIC_CONTRACT` | 합성 7행 unsafe `5→0`, 정상 공개 `2→2` |
| P1 CandidateSet/NIL typed shadow | `GO_SAVED_ARTIFACT_SHADOW_ONLY` | Golden18 integrity/public 불변 `18/18`, candidate truth 사건 관측 `9/9`, NIL 원장 행 공통 선택지 `6/6`, UNJUDGED `3`; 정확도 검사가 아님 |
| P1 로컬 후보 잘림 탐지 | `GO_SAVED_ARTIFACT_AND_SYNTHETIC_SHADOW_ONLY` | 제목 고유 7개 `TRUNCATED 7→6`, serializer 고유 25개 `TRUNCATED 25→24`, cap 이하 `UNKNOWN`, Golden18 public 불변 `18/18` |
| P1 전문가 단계 잘림 진단 | `GO_DIAGNOSTIC_ONLY` | 실제 cap 7곳, 합성 cap+1 `7/7 TRUNCATED`, 경계 오탐 `0`, 유지 출력 `9/9`; CandidateSet·확률·공개 판정에는 미합성 |
| P1 bounded producer 완료 증명 | `GO_SYNTHETIC_CONTRACT_ONLY` | 합성 `COMPLETE 1 / UNKNOWN 4 / TRUNCATED 1 / false COMPLETE 0`; Golden18은 receipt가 없어 실제 `UNKNOWN / NOT_EVALUABLE` |
| P2 최종 공개 판정 exact-once | `GO_SAVED_ARTIFACT_AND_SYNTHETIC_ONLY / NOT_RUNTIME_VALIDATED` | Golden18 commit `0→18`, replay no-op `18`, public/full row 불변 `18/18`, 합성 공격 `21/21`, false GO `0` |
| P3 정확도 퍼센트 기반 | `NO_GO_ACTUAL_DATASET_NOT_READY` | readback v2·readiness source replay·6개 paired CI 정책 게이트 구현, Golden18 ready `0/18`, actual 지표 null |
| P4 선택적 비용 측정 | `IMPLEMENTED_REFERENCE_COPY_COST_ONLY_NO_ACTUAL_PAIR` | call reader·AFTER source route 구현, cheap reference copy는 production savings가 아니며 actual 비용 KPI null |
| 실제 개선 후 runtime | `NOT_RUN_STATIC_PROJECTION (BLOCKED_ACTIVE_PRODUCTION_RUN)` | 104,502건 실행이 진행 중이므로 새 LLM/MCP 부하 금지 |
| 실제 정확도 퍼센트 | `NOT_AVAILABLE_UNCALIBRATED` | reader·bootstrap 기반은 구현했지만 실제 라벨·보정·동결 파일과 completed output·실제 구간 전에는 숫자를 만들지 않음 |
| 의미 품질 | `REVIEW-LOCKED` | 정적 안전성 개선은 전체 의미 품질 승인이 아님 |
| 운영 전체 승인 | `false` | `full_scan_approval=false` 유지 |

## 현재 산출물

- 실행 명세: `out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/run_spec.json`
- 실제 저장본 비교 JSON: `out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/before_after_comparison.json`
- 사람이 읽는 비교 보고서: `out/pipeline_improvement_harness_20260711/retrieval_failclose_v5/before_after_comparison.md`
- 일반 하네스: `tools/run_pipeline_improvement_harness.py`
- 하네스 회귀 시험: `tests/test_pipeline_improvement_harness.py`
- 합성 게이트 probe: `tools/search_fail_close_probe.py`
- 합성 게이트 probe 결과: `docs/devs/loop_reports/search_fail_close_probe_20260711.json`
- 검색 상태형 게이트 시험: `tests/test_retrieval_state_fail_close.py`
- P1 실행 명세: `out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json`
- P1 사람이 읽는 비교: `out/candidate_set_nil_shadow_harness_20260711/v8/comparison.md`
- P1 completeness 실행 명세: `out/candidate_generation_completeness_harness_20260711/v6/run_spec.json`
- P1 completeness 한국어 비교: `out/candidate_generation_completeness_harness_20260711/v6/comparison.md`
- P1 producer 완료 증명 보고서: `docs/devs/loop_reports/LOOP_P1_PRODUCER_COMPLETION_PROOF_20260711.md`
- P2 실행 명세·정본 비교: `out/publication_exact_once_harness_20260711/v8/run_spec.json`, `comparison.json/.md`
- P2 기능 중심 한국어 보고서: `docs/devs/loop_reports/LOOP_P2_PUBLICATION_EXACT_ONCE_20260711.md`
- P3 실행 명세·정본 비교: `out/candidate_set_calibration_shadow_harness_20260711/v18/run_spec.json`, `comparison.json/.md`
- P3 기능 중심 한국어 보고서: `docs/devs/loop_reports/LOOP_P3_CALIBRATION_CONTRACT_FOUNDATION_20260711.md`
- P3 actual 정책 숫자 결정안: `docs/devs/P3_ACTUAL_POLICY_DECISION_KO_20260712.md` — A 권고/B 대안, 소유자 확정 전 JSON 생성 금지
- P3 코드·하네스·시험: `src/llm_batch/grounding/candidate_set_calibration_shadow.py`, `tools/run_candidate_set_calibration_shadow_harness.py`, `tests/test_candidate_set_calibration_shadow_contract.py`, `tests/test_candidate_set_calibration_shadow_harness.py`
- P4 실행 명세·정본 비교: `out/selective_compute_shadow_harness_20260712/v19/run_spec.json`, `comparison.json/.md`
- P4 기능 보고서: `docs/devs/loop_reports/LOOP_P4_SELECTIVE_COMPUTE_SHADOW_20260712.md`
- P4 코드·하네스·시험: `src/llm_batch/measurement/selective_compute_shadow.py`, `tools/run_selective_compute_shadow_harness.py`, `tests/test_selective_compute_shadow_contract.py`, `tests/test_selective_compute_shadow_harness.py`
- P1 정답 원장: `docs/devs/p1_candidate_set_nil_golden18_label_ledger_20260711.json`
- P1 하네스/시험: `tools/run_candidate_set_nil_shadow_harness.py`, `tools/run_candidate_generation_completeness_harness.py`, `tests/test_candidate_set_nil_shadow_harness.py`, `tests/test_candidate_set_shadow_contract.py`, `tests/test_candidate_generation_snapshot.py`, `tests/test_candidate_stage_receipts.py`, `tests/test_candidate_generation_completeness_harness.py`
- 기능 중심 한국어 안내: `docs/devs/LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`
- 최신 한국어 독자판: `docs/devs/LLM_PIPELINE_IMPROVEMENT_STATUS_KO_20260712.md`
- actual/readback 구현: `src/llm_batch/grounding/calibration_actual_readback.py`, `src/llm_batch/ledger/decision_call_readback.py`, `src/llm_batch/measurement/early_route_measurement.py`, `src/llm_batch/measurement/paired_measurement_readback.py`

## P3 실제 증거 동결 명령

아래 명령은 실제 자료 준비도가 `GO`가 된 뒤에만 실행한다. SHA 문자열을 직접 넣지 않고 모든 결속값을 파일에서 유도한다. 현재 Golden18에서는 `ready 0/18`이므로 실행하면 readback 전에 `NO_GO_ACTUAL_DATASET_NOT_READY`로 중단돼야 한다.

먼저 같은 인자를 `actual-preflight`에 주면 파일을 쓰거나 모델을 실행하지 않고 누락 파일, readiness, replay 구조·coverage를 확인한다. 현재처럼 actual packet이 없으면 exit `2`, `NO_GO_ACTUAL_PREFLIGHT`, `writes_performed=false`, `runtime_started=false`가 정상이다. preflight GO도 성능 증거가 아니며 실제 readback은 모든 파일을 다시 읽는다.

```powershell
.\.venv312\Scripts\python.exe tools/run_candidate_set_calibration_shadow_harness.py actual-preflight `
  --artifact-root "out/actual_calibration/<run-id>" `
  --p1-run-spec-json "p1/run_spec.json" `
  --p1-comparison-json "p1/comparison.json" `
  --label-ledger-json "labels/label_ledger.json" `
  --actual-evaluation-policy-json "policy/actual_policy.json" `
  --split-manifest-json "dataset/split_manifest.json" `
  --source-manifest-json "dataset/source_manifest.json" `
  --expected-universe-jsonl "dataset/frozen_expected.jsonl" `
  --producer-jsonl "predictions/producer.jsonl" `
  --prediction-jsonl "predictions/after.jsonl" `
  --baseline-prediction-jsonl "predictions/before.jsonl" `
  --artifact "after_base_shadows=replay/after_base_shadows.jsonl" `
  --artifact "after_score_vectors=replay/after_score_vectors.jsonl" `
  --artifact "after_calibration_artifact=replay/after_calibration_artifact.json" `
  --artifact "baseline_base_shadows=replay/baseline_base_shadows.jsonl" `
  --artifact "baseline_score_vectors=replay/baseline_score_vectors.jsonl" `
  --artifact "baseline_calibration_artifact=replay/baseline_calibration_artifact.json" `
  --seed 20260712 `
  --replicates 2000
```

```powershell
.\.venv312\Scripts\python.exe tools/run_candidate_set_calibration_shadow_harness.py actual-readback `
  --artifact-root "out/actual_calibration/<run-id>" `
  --p1-run-spec-json "p1/run_spec.json" `
  --p1-comparison-json "p1/comparison.json" `
  --label-ledger-json "labels/label_ledger.json" `
  --actual-evaluation-policy-json "policy/actual_policy.json" `
  --split-manifest-json "dataset/split_manifest.json" `
  --source-manifest-json "dataset/source_manifest.json" `
  --expected-universe-jsonl "dataset/frozen_expected.jsonl" `
  --producer-jsonl "predictions/producer.jsonl" `
  --prediction-jsonl "predictions/after.jsonl" `
  --baseline-prediction-jsonl "predictions/before.jsonl" `
  --artifact "after_base_shadows=replay/after_base_shadows.jsonl" `
  --artifact "after_score_vectors=replay/after_score_vectors.jsonl" `
  --artifact "after_calibration_artifact=replay/after_calibration_artifact.json" `
  --artifact "baseline_base_shadows=replay/baseline_base_shadows.jsonl" `
  --artifact "baseline_score_vectors=replay/baseline_score_vectors.jsonl" `
  --artifact "baseline_calibration_artifact=replay/baseline_calibration_artifact.json" `
  --seed 20260712 `
  --replicates 2000 `
  --output-dir "out/actual_calibration/<run-id>/readback_bundle"
```

readback 성공 게이트는 `GO_ACTUAL_READBACK_FOUNDATION_ONLY`다. 이어서 다음 명령이 bundle에 결속된 AFTER/baseline base shadow·score vector·보정 산출물·prediction을 재생해 기존 `evaluate_frozen_holdout(FROZEN_ACTUAL)`을 호출한다.

```powershell
.\.venv312\Scripts\python.exe tools/run_candidate_set_calibration_shadow_harness.py actual-evaluate `
  --artifact-root "out/actual_calibration/<run-id>" `
  --readback-bundle-dir "readback_bundle" `
  --output-dir "out/actual_calibration/<run-id>/evaluation_bundle"
```

평가 결과가 `GO_FROZEN_ACTUAL_SHADOW_ONLY`여도 정확도 그림자 게이트만 통과한 것이다. fresh 비용 pair·hard regression·public 비간섭·사람 검토 전에는 운영 승인을 만들지 않는다.

## active production 종료 뒤 실제 paired 실행 순서

현재는 실행하지 않는다. 먼저 measurement OFF로 완결된 새 authoritative source run과 publication WAL을 만든 뒤, 그 manifest와 동결 입력을 사용한다.

```powershell
$pairId = 'paired-YYYYMMDD-HHMMSS'
$input = '<frozen-input.jsonl>'
$sourceManifest = '<complete-source-manifest.json>'
$pairRunSpec = "out/paired_measurement/$pairId/run_spec.json"

.\.venv312\Scripts\python.exe tools\run_paired_measurement_readback.py `
  --freeze-run-spec $pairRunSpec `
  --input $input `
  --source-manifest $sourceManifest `
  --pair-id $pairId `
  --slang-access-mode OFF
```

RunSpec의 `run_spec_sha256`을 읽은 뒤 BEFORE와 AFTER를 서로 다른 output/prefix로 각각 한 번 실행한다. 공통 환경은 다음과 같다.

```powershell
$env:PIPELINE_DECISION_CALL_LEDGER_MODE = 'REQUIRED'
$env:PIPELINE_MEASUREMENT_RUN_SPEC_SHA256 = '<run_spec_sha256>'
$env:PIPELINE_MEASUREMENT_PAIR_ID = $pairId
$env:PIPELINE_MEASUREMENT_EXECUTION_MODE = 'FRESH_EXECUTION_REQUIRED'
$env:PIPELINE_MEASUREMENT_MUTABLE_CONTEXT_MODE = 'FROZEN_OFF'

# BEFORE
$env:PIPELINE_MEASUREMENT_ARM = 'BEFORE'
$env:PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE = 'OFF'
.\.venv312\Scripts\python.exe expert_main.py $input --output '<before-output.json>' --parallel 16 --reuse-shards-only --slang-db off --vlm on --ocr on --require-vlm-ocr-for-images

# AFTER
$env:PIPELINE_MEASUREMENT_ARM = 'AFTER'
$env:PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE = 'SOURCE_ONLY_V1'
.\.venv312\Scripts\python.exe expert_main.py $input --output '<after-output.json>' --parallel 16 --reuse-shards-only --slang-db off --vlm on --ocr on --require-vlm-ocr-for-images
```

두 실행 모두 dashboard를 켠다. `--no-dashboard`는 사용하지 않는다. 완료 뒤 실제 manifest를 독립 재판독한다.

```powershell
.\.venv312\Scripts\python.exe tools\run_paired_measurement_readback.py `
  --run-spec $pairRunSpec `
  --before-manifest '<before-manifest.json>' `
  --after-manifest '<after-manifest.json>' `
  --output-json "out/paired_measurement/$pairId/comparison.json" `
  --output-md "out/paired_measurement/$pairId/comparison.md"
```

실제 이미지가 없는 동결 입력은 RunSpec에 고정한 VLM/OCR 정책에 맞춰 조정한다. 실행 중 조건을 바꾸지 않는다.

## 개선 백로그

| 순서 | 개선 | 현재 상태 | 다음 완료 증거 |
| ---: | --- | --- | --- |
| P0 | 필수 검색 미복구 공개 차단 | 게이트·정적 투영 완료, live 배선/실제 after 미완료 | 별도 runtime에서 unsafe `0`, 후보 손실 `0`, 검색 게이트 별도 판정 |
| P1 | 여러 후보와 작품 없음을 함께 비교 | typed shadow v8·cap 6/24·전문가 cap 7곳·bounded producer proof v6를 합성 검증, public 미적용 | 실제 runtime receipt, cache origin binding, broader frozen holdout, candidate-set recall, 실제 selector shadow |
| P2 | 최종 공개 판정 한 번만 쓰기 | 저장본·합성 구현 검증, actual runtime 미검증 | 별도 runtime의 정상 완료·강제 중단·재시작에서 게시글당 최종 판정 정확히 1개, 우회 `0` |
| P3 | 보정된 정확도 퍼센트 shadow | readiness v2·정책/split/source bound runner·6개 CI 정책 게이트 구현, actual 자료·평가 출력·runtime 미완료 | 실제 분리 자료로 bound bundle과 `FROZEN_ACTUAL` CI 출력·public 불변 확인 |
| P4 | 쉬운 글·어려운 글 처리 분리 | 원장·독립 reader·AFTER 측정 라우터·paired source replay·교차 계보 구현, actual pair 미실행 | actual 고위험 품질 비열화 0, calls/post·회피율·p95 신뢰구간, public 비간섭 |
| P5 | 행별 저장·속어 승인 분리 | 미구현 | 중단 재처리 `0`, 속어 DB 되돌리기 가능 |
