# Promotion Contract v2 구현 보고

- 상태: `STATIC_GO_RUNTIME_PROOF_PENDING`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- 범위: title/URL publication 단일 writer와 fail-closed serializer 경계
- 비범위: Loop641 immutable result·merge·gate·trust artifact, harness model/search/slang/VLM 설정, 10만 production scan

## 구현 결과

`src/llm_batch/promotion_gate.py`에 frozen typed contract를 추가했다.

- `GroundingState`와 `ScopeState`가 현재 글의 작품 논의 범위, 직접 bridge, 경쟁 후보, conflict를 보존한다.
- `EvidenceRecord`가 근거 종류뿐 아니라 근거가 지지하는 `candidate_title`/`candidate_url`과 `title_url_match`를 함께 고정한다.
- `PromotionDecision`, `PublishContractTrace`, `PublishContract`는 state/evidence의 canonical SHA-256 `input_fingerprint`를 공유한다.
- `can_publish_title(...)`은 `scope=current_work`, 직접 bridge, candidate-bound publish evidence를 모두 요구한다. scope 누락/unknown, 경쟁 작품 근거, title 품질 blocker는 candidate-only HOLD로 닫는다.
- URL은 지원되는 공식 상세 URL이며 동일 candidate title/URL pair가 검증된 경우에만 공개한다. URL 근거가 없거나 mismatch이면 title-only publication으로 제한한다.
- `apply_publish_contract(...)`만 public title/URL을 쓰거나 지우며, decision/state/evidence/trace/ledger/fingerprint/version을 같은 결과에 직렬화한다. 차단된 후보는 `blocked_official_title`, `blocked_official_title_url`, candidate ledger에 보존하고 `bypassed_gate=false`를 유지한다.

`src/llm_batch/agentic_pipeline.py`는 public promotion recorder와 최종 `PickvelIdentity` 경계가 동일 contract를 사용하도록 바꿨다. 모든 recorder의 `row_discusses_work_as_work`는 단일 `_post_discusses_work_as_work(...)`에서 재계산한다. source-native 공식 URL, 검증된 alias, OCR/visual 공식 상세 근거는 candidate-bound bridge로 기록하고 search-only URL은 직접 bridge로 취급하지 않는다.

`src/llm_batch/grounding/candidate_audit.py`의 후단 restore/canonicalizer는 authoritative `promotion_contract_v2`를 발견하면 public identity를 다시 쓰지 않는다. 기존 deterministic title 품질 lint는 agentic final contract의 blocking evidence로 앞당겨 보존했다.

`expert_main.py`는 v2 결과에서 judge seed, projection follow-up, legacy weak restore를 publication 입력으로 사용하지 않는다. serializer 직전에 typed state/evidence를 shadow recompute하고 fingerprint, decision, 현재 public surface가 다르면 새 unknown-scope HOLD contract로 fail-close한 뒤 다시 적용한다. 따라서 hand-authored decision dict나 late writer는 public identity를 유지할 수 없다.

`tools/audit_publication_contract_convergence.py`는 v2 state/evidence를 독립 재평가하여 version, fingerprint, decision, trace, public surface를 대조한다. 자기일관적인 legacy dict만으로는 v2 convergence `GO`를 만들 수 없다.

## 고정한 시나리오

- scope 누락/unknown, context-only `아생갤`, 경쟁 작품 evidence: public null, candidate 보존
- `11694035`: `아생갤`을 무조건 DC gallery surface로 단정하지 않되, 현재 작품 bridge 없이는 공개하지 않음
- `11663540`: OCR canonical 후보와 원본 후보를 보존하고 candidate-bound visual evidence가 없으면 HOLD
- `11682761`: OCR이 `그레이스 길들이기 웹툰`이고 검색 근거가 `non_novel_media_platform`일 때 direct-image fast path를 열지 않고 `platform_meta_nonwork` candidate HOLD
- `11663540`: 실제 웹소설 OCR과 Novelpia 공식 상세 근거는 non-novel media guard 뒤에도 current-work publish 유지
- `11663514`: 원문에 포함된 공식 상세 URL은 bridge provenance로 인정하고 search-only 동일 URL은 bridge로 인정하지 않음
- 공식 URL tracking query 정규화와 Naver `productNo` 같은 semantic query 보존
- `11663540` golden visual positive, visual bracket official-detail positive, preserved candidate positive
- v2 serializer 이후 adversarial `judge_seed`가 다른 title/URL을 주입해도 public identity·ledger·fingerprint 불변
- no-candidate terminal은 `hold_without_candidates`, candidate HOLD는 `promotion_blocked`, 허용은 `safe_resolved`

## 검증

Windows `.venv312` Python `3.12.6`과 `PYTHONPATH=src`만 사용했다.

- modified Python `py_compile`: PASS
- `tests.test_title_lead_search_inferred_guard`: `227/227 PASS`
- `tests.test_promotion_gate_contract`, `tests.test_publication_contract_convergence_audit`, `tests.test_expert_main_comment_metadata`, `tests.test_completed_source_candidate_audit`: `154/154 PASS`
- `tests.test_expert_main_input_loader`: `41/41 PASS`
- 합계: `422/422 PASS`
- scoped `git diff --check`: PASS

`.venv` uv sync 사고는 별도 immutable 기록을 참조한다.

- `docs/devs/loop641_venv_uv_sync_incident_20260710.json`, SHA-256 `ed9e610a1d5484e53f45c3b5cb52adf0c49e54b2cfd83f8c8721720ac7cae5d6`
- `docs/devs/loop641_venv_uv_sync_incident_20260710.md`, SHA-256 `baa482114aeff6d083f649b12e0086500964cb666e30ec6cd87e81af7f700c1d`
- `.venv` 복구/삭제/재생성은 수행하지 않았고 후속 테스트는 `.venv312`만 사용했다.

## 독립 감사 P1 보완

독립 공격 감사에서 serialized `publish_contract_trace.post_gate_identity`가 shadow recompute의 `post_gate_context`로 다시 들어가, 변조된 `title_resolution_allowed`, `title_resolution_state`, `work_resolution`이 public title과 모순된 채 남을 수 있는 P1을 확인했다. 기존 convergence audit도 같은 변조 trace를 입력으로 재사용하여 자기검증하는 결함이 있었다.

bounded fix 후 계약은 다음처럼 수렴한다.

- `evaluate_publish_contract(...)`의 post-gate identity는 오직 frozen `GroundingState`와 `EvidenceRecord[]`에서 결정적으로 생성한다. 호환성을 위해 남긴 `post_gate_context` 인자는 publication/trace 계산에 사용하지 않는다.
- `apply_publish_contract(...)`는 root identity, trace, publish ledger, candidate ledger의 `title_resolution_allowed`, `title_resolution_state`, `work_resolution`, `candidate_ledger_status`를 동일한 deterministic 값으로 다시 쓴다.
- `expert_main.py` final serializer는 serialized trace/ledger를 recompute 입력으로 신뢰하지 않고 state/evidence만 재평가한다. public decision/fingerprint가 유효한 경우 stale trace/ledger/root resolution fields를 결정적으로 복구하고, 기존 decision/public surface 불일치는 계속 unknown-scope HOLD로 닫는다.
- `audit_publication_contract_convergence.py`도 state/evidence-only shadow contract를 만들고 root/trace/publish ledger/candidate ledger resolution fields를 대조한다. 모든 복사본을 같은 잘못된 값으로 변조한 공격 재현은 `NO-GO`다.

검증은 Windows `.venv312`만 사용했다.

- P1 focused suite: `153/153 PASS`
- promotion/publication/input-loader/title-led/expert serializer 확장 suite: `424/424 PASS`
- modified Python `py_compile`: PASS
- scoped `git diff --check`: PASS
- `_runtime_binding_echo_fields()` 정의와 result/manifest echo 호출은 보존했다.

URL canonicalization의 전역 tracking key(`ref`, `from`, `source`, `sid`)가 미래 플랫폼의 semantic query와 충돌할 수 있는 P2는 이번 P1 범위에서 변경하지 않았다. 현재 지원 플랫폼의 `productNo` 등 semantic identifier 보존 테스트는 유지하며, 이 항목은 residual risk로만 남긴다.

정적 상태는 계속 `STATIC_GO_RUNTIME_PROOF_PENDING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다. 이 보완은 runtime/golden/N=5/fresh375 승인 근거를 대신하지 않는다.

## 남은 gate

이번 변경은 bounded convergence의 안전 개입 `#1`이다. Loop641 panel375의 입력 375행 모두에 존재한 `judge_seed=375/375`는 v2 runtime publication 근거로 사용하지 않는다. 이 보고서는 static code contract만 증명하며 실행 증거 순서는 `token echo -> golden18 -> N=5 -> release fingerprint당 fresh375 1회`다. 메인 orchestration이 고정한 N=5 strata(`11694035`, `11663540`, `11663514`, `11682761`, `11660237`)와 homogeneous fresh375를 아직 이 구현 보고서의 근거로 승인하지 않는다. publication/golden/collateral/always-on/search terminal gate가 모두 연결될 때까지 `STATIC_GO_RUNTIME_PROOF_PENDING`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`다.
