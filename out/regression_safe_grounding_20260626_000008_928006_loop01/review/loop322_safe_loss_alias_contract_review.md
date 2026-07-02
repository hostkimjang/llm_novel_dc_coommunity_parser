# Loop322 safe-loss alias contract review

Loop322는 approval 회차가 아니다. Loop321에서 source-native로 확인된 `repair_safe_loss=76` 중 실제 packet에 직접 별칭과 작품 소비 cue가 함께 있는 7건만 shared `KNOWN_TITLE_ABBREVIATIONS` 계약으로 올렸다. 이 결과는 unit-level contract이며, targeted runtime replay와 collateral compare 전까지 residual closure로 세지 않는다.

## 1) 변경 요약

- registry 추가: `괴담출근`, `절꺾않`, `무마`, `아카엄창`, `성좌안무서움`, `빌환`, `지구온라인`.
- cue 보강: `표절`, `보러감` 패턴을 known-title abbreviation work cue에 추가했다.
- 보류: `주전무`는 실제 packet에서 plot cue는 강하지만 shared cue 폭을 더 넓혀야 하므로 이번 registry 승격에서 제외했다.

## 2) 선택 alias

| post_id | alias | title | source cue |
|---|---|---|---|
| `11708443` | `괴담출근` | `괴담에 떨어져도 출근을 해야 하는구나` | 표절/괴담물 직접 비교 |
| `11708470` | `절꺾않` | `절대 꺾이지 않을거야!` | 웹툰/스토리/재밌음 |
| `11710021` | `무마` | `무한의 마법사` | 웹툰/시로네 캐릭터 맥락 |
| `11710052` | `아카엄창` | `아카데미 패드립 면역` | 보러감 조건부 작품 소비 |
| `11713220` | `성좌안무서움` | `나만 성좌들이 안 무서움` | 정체/설정 질문 |
| `11718099` | `빌환` | `빌어먹을 환생` | 표지 변경/캐릭터 cluster |
| `11718110` | `지구온라인` | `지구온라인에서 쌀먹합니다` | 재밌다며/주인공 묘사 |

## 3) 보류 alias

| post_id | alias | title | 이유 |
|---|---|---|---|
| `11710020` | `주전무` | `주무시기 전에 무엇을 하셨나요?` | 실제 packet은 plot cue가 있으나 현재 shared cue 폭을 넓혀야 하므로 이번 registry 승격에서 보류 |

## 4) 검증

- `.venv312\Scripts\python.exe -m py_compile src\llm_batch\agentic_pipeline.py src\llm_batch\experts\utils.py tests\test_known_title_abbreviation_safe_loss_contract.py` -> PASS
- `.venv312\Scripts\python.exe -m unittest tests.test_known_title_abbreviation_safe_loss_contract -v` -> PASS, `4` tests
- `.venv312\Scripts\python.exe -m unittest tests.test_known_title_abbreviation_support tests.test_arbiter_curated_alias_guard tests.test_title_lead_search_inferred_guard -v` -> PASS, `230` tests
- `.venv312\Scripts\python.exe -m unittest tests.test_always_on_regression_gates tests.test_goal_convergence -v` -> PASS, `12` tests
- actual Loop321 source packet helper check -> selected `7` aliases allowed, held `주전무` remains blocked

## 5) Gate 상태

- contract: `GO_UNIT_CONTRACT_ONLY`
- runtime replay: `NOT_RUN`
- residual closure: `NOT_COUNTED`
- source-native review: `REVIEW-LOCKED / COMPLETE_SOURCE_NATIVE_QUEUE`
- search recovery: `P0 / OPEN`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- overall goal: `ACTIVE / NOT_COMPLETE`
