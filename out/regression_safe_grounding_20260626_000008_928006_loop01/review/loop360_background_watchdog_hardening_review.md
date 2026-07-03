# Loop360 background watchdog hardening review

## 판정

- Loop359 background 런은 `STALLED_LLM_WATCHDOG / NOT_APPROVAL`이다.
- manifest count는 full375, bounded1200, golden18, safe-loss first 모두 `0/0/0/0`이라 stale evidence를 대체하지 못한다.
- safe-loss first combined log는 `llm-watchdog`가 터미널 `y` 또는 웹 대시보드 재개를 요구한 상태를 남겼다.

## 코드 계약

- N5 독립 plan command는 background에서 interactive LLM suspend prompt를 켜지 않는다.
- 오래된 plan도 `tools/run_independent_plan.py` runner를 경유하면 env 기본값으로 suspend prompt를 끈다.

## 검증

- `py_compile`: PASS.
- focused unittest: PASS, `9` tests.

## 게이트

- runtime completion: `NO_COMPLETION / NOT_APPROVAL`
- search recovery: `P0 / OPEN`
- promotion blocked: `search-blind conditional`
- collateral active lane: `REVIEW-LOCKED / residual_action_queue_rows=105`
- semantic quality: `REVIEW-LOCKED`
- full scan approval: `false`
- goal: `ACTIVE / NOT_COMPLETE`
