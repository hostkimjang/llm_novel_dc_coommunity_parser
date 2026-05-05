# Sampling And Parallel Test Guide

수백만 건 단위 처리를 검증할 때 4건, 30건, 300건 같은 작은 표본을 품질 승인 근거로 쓰면 안 된다. 작은 표본은 코드 경로 확인과 오류 유형 발견에만 쓴다.

## 샘플 단계

| 단계 | 크기 | 목적 | 품질 승인 가능 여부 |
| --- | ---: | --- | --- |
| unit/smoke | 4~20건 | 새 코드 경로가 터지지 않는지 확인 | 불가 |
| canary | 100~500건 | 병렬 실행, 로그, 검색 timeout/degraded, 결과 스키마 확인 | 불가 |
| risk discovery | 1,000~3,000건 | 위험 bucket별 오류 유형 발견 | 불가 |
| validation | 10,000건 이상 | 개선 전후 품질 비교, 주요 오류율 추정 | 제한적 가능 |
| production audit | 전체 run 100% 자동 감사 + 대형 샘플 정성 리뷰 | 운영 승인 | 가능 |

## 대형 run 기본 원칙

- 전체 결과는 자동 감사로 100% 본다.
  - checkpoint/manifest 정합성
  - failed/reason_error
  - search_degraded/search_timeout
  - slang DB store/block/conflict
  - worker/shard별 이상치
- 정성 리뷰는 표본으로 보되, 위험군을 과표집한다.
- 정상 대조군도 반드시 넣는다.
- 작은 smoke test는 문서에 `품질 승인용 아님`이라고 적는다.
- 같은 post id를 개선 전후로 재처리해 결과 변화를 비교한다.
- 개선 작업은 가능한 한 자동으로 `테스트 런 -> 감사 -> 전후 비교 문서 생성 -> 리뷰 패킷 생성`까지 이어지게 한다.
- 자동화가 아직 없는 단계는 수동으로 실행하되, 누락한 단계와 이유를 `VERIFICATION_RESULTS.md`와 `HISTORY.md`에 남긴다.

## 최소 샘플 권장치

수백만 건 run의 기본 검증 표본:

- 병렬 canary: 최소 200건
- risk discovery: 최소 1,000건
- validation: 최소 10,000건
- 정상 대조군: validation 표본의 15~25%
- 각 주요 bucket 최소치:
  - 검색 저하: 500건 이상
  - 검색 정상 대조군: 1,000건 이상
  - slang 후보: 500건 이상
  - slang 미저장/차단 후보: 300건 이상
  - resolved 저근거: 300건 이상
  - unresolved/multi_work: 300건 이상
  - non-relevant false negative 의심군: 300건 이상

치명 오류율을 1%p 안팎으로 보고 싶으면 랜덤 표본은 대략 10,000건 이상이 필요하다. 희귀 오류는 랜덤 표본만으로 잘 잡히지 않으므로 risk bucket 표본을 별도로 둔다.

## 병렬 테스트 기준

병렬 테스트는 최소 2단계로 나눈다.

1. 병렬 smoke
   - 4~20건
   - 목적: 코드 경로, worker 로그, shard routing, schema 깨짐 확인
   - 판정: `SMOKE ONLY`
2. 병렬 canary
   - 200~500건
   - 목적: 실제 병렬 구동에서 timeout/degraded/LLM 오류율 확인
   - 판정: `REVIEW`
3. 병렬 validation
   - 1,000건 이상
   - 목적: 개선 전후 오류율과 검색 품질 비교
   - 판정: `GO | REVIEW | NO-GO`

Targeted regression은 별도 단계로 둔다. known bad post 1~20건만 골라 고친 코드 경로가 실제로 바뀌는지 확인하는 용도이며, 품질 승인 근거는 아니다. targeted에서 통과한 케이스는 이후 200건 canary와 1,000건 risk discovery의 `must-post-ids` 또는 별도 고정 샘플에 포함한다.

## 병렬 실행 기록 규칙

병렬 테스트 결과를 남길 때는 아래 값을 반드시 함께 기록한다.

- 입력 파일 경로와 manifest 경로
- 출력 JSON 경로
- run log 경로
- `--parallel` 값
- search shard 목표 수와 실제 감사 결과
- 주요 env override
- 총 처리 시간, post당 평균 시간
- `search_upstream_zero`, `search_degraded_detected`, `search_timeout`
- known bad sample의 개선 전후 판정 변화

작은 targeted 입력을 수동으로 만들 때는 JSONL을 UTF-8 BOM 없이 저장한다. BOM이 있으면 첫 post line이 `json.loads`에서 제외되고 댓글만 남아 `0개 포스트`로 로드될 수 있다.

4건 smoke가 통과해도 다음 단계는 200건 canary다. 200건 canary가 통과해도 품질 승인이 아니라 validation 준비 상태로만 본다.

## 개선 전후 자동화 루틴

기능 개선, 검색 품질 개선, slang DB 규칙 변경은 아래 루틴을 기본값으로 둔다.

1. baseline 고정
   - baseline run id, checkpoint, output JSON, run summary, shard audit 경로를 기록한다.
   - 같은 입력 JSONL을 재사용할 수 없으면 비교 불가 사유를 먼저 남긴다.
2. 개선 후 테스트 런
   - unit/smoke로 코드 경로를 확인한다.
   - canary 이상은 동일 입력, 동일 `--parallel`, 동일 shard 목표 수, 동일 주요 env로 재실행한다.
3. 자동 감사
   - baseline과 improved run 모두 `tools/audit_expert_run_health.py` 또는 동등한 감사 결과를 남긴다.
   - shard 상태는 `tools/audit_search_shards.py --count <N>`로 전후 기록한다.
4. 전후 비교 문서
   - checkpoint/manifest 정합성, failed/pending, 처리 시간, top latency, search timeout/degraded, slang store/block, known bad 판정 변화를 표로 기록한다.
   - 비교 Markdown/JSON은 `out/comparisons/` 또는 `out/sampling/`에 두고 `VERIFICATION_RESULTS.md`에서 링크한다.
5. 정성 리뷰
   - LLM 판단이 필요한 개선은 `tools/build_llm_judgment_review_packet.py`로 improved run 리뷰 패킷을 생성한다.
   - `ACCEPT/HOLD/REPROCESS/REJECT` 집계가 없으면 품질 gate는 `REVIEW`로 남긴다.

## 샘플 생성 예시

```powershell
.venv312\Scripts\python.exe tools\build_balanced_regression_input.py --checkpoint out\expert_result_20260423_170321_250907_checkpoint.jsonl --output out\sampling\query_gate_canary_200.jsonl --max-posts 200 --per-bucket 20 --order distributed
```

기본 샘플 출력 순서는 `distributed`이다. bucket round-robin으로 출력해 post id/시간대가 한쪽에 몰리지 않게 한다.

- `--order distributed`: canary/risk discovery 기본값. 위험 bucket과 정상군을 섞음.
- `--order random`: 완전 랜덤 순서.
- `--order post_id_desc` 또는 `--order post_id_asc`: 과거 정렬순 결과 재현이 필요할 때만 사용.

post id 정렬순 테스트는 특정 시간대/게시 흐름이 초반 또는 후반 worker에 몰려 late budget, cache, shard 상태, 검색 rate-limit 평가를 왜곡할 수 있다. 운영 대상이 수백만 건이면 테스트도 시간/버킷/위험 유형이 섞여야 한다.

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 1000 --per-bucket 80 --strategy stratified --control-count 120
```

## 병렬 실행 예시

Smoke는 코드 경로 확인용이다.

```powershell
$env:PIPELINE_SEARCH_CONCURRENCY="2"
$env:LLM_ENABLE_CONFIDENT_QUERY_EXPANSION="1"
$env:LLM_ENABLE_GENRE_NOVEL_QUERY_EXPANSION="1"
.venv312\Scripts\python.exe expert_main.py --input out\sampling\query_gate_parallel_smoke_20260426.jsonl --output out\sampling\query_gate_parallel_smoke_20260426_result.json --parallel 2 --no-dashboard --vlm off --ocr off
```

Canary 이상은 shard 수를 먼저 명시하고 감사한 뒤 실행한다.

```powershell
.venv312\Scripts\python.exe tools\audit_search_shards.py --count 36 --timeout 1.5
$env:MCP_SHARD_COUNT="36"
$env:MCP_CLIENT_ENDPOINT_FAILOVER="1"
$env:MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH="4"
$env:MCP_CLIENT_SEARCH_TIMEOUT_SEC="12"
$env:MCP_CLIENT_SEARCH_MAX_RETRIES="1"
$env:PIPELINE_SEARCH_CONCURRENCY="8"
$env:LLM_ENABLE_CONFIDENT_QUERY_EXPANSION="1"
$env:LLM_ENABLE_GENRE_NOVEL_QUERY_EXPANSION="1"
$env:LLM_ENABLE_LATE_TOTAL_SEARCH_BUDGET="1"
$env:LLM_LATE_TOTAL_SEARCH_MIN_ITERATION="3"
.venv312\Scripts\python.exe expert_main.py --input out\sampling\query_gate_canary_200_20260426.jsonl --output out\sampling\query_gate_canary_200_20260426_result.json --parallel 8 --no-dashboard --vlm off --ocr off
```

실행 시간이 길면 200건 canary를 먼저 완료하고, 1,000건/10,000건은 같은 env와 shard 구성으로 이어서 돌린다.

Canary가 timeout wrapper 안에서 실행될 때는 CLI progress 출력 오류가 결과 실패로 기록되지 않아야 한다. 또한 검색 client failover가 전체 shard를 순차 순회하면 단일 검색이 수십 분까지 늘 수 있으므로 canary 이상에서는 `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH`와 `MCP_CLIENT_SEARCH_TIMEOUT_SEC`를 명시한다.

`expert_main.py`의 startup auto-manage 경로를 쓰려면 `MCP_ENDPOINTS`/`MCP_ENDPOINT`를 직접 지정하지 않는다. `MCP_SHARD_COUNT=36`만 지정하면 endpoint pool이 자동 생성되고, 시작 시 `warp_shards.py up`, WARP 상태 확인, `/readyz` health check, 실패 shard recreate 경로가 실행된다. 이 방식으로 canary를 실행할 때는 `--no-auto-up-shards`를 붙이지 않는다.

## 품질 판정

- `GO`: 전체 자동 감사 통과, validation 샘플 정성 리뷰 완료, 치명 오염 0, 재처리 대상 분리 완료
- `REVIEW`: smoke/canary만 수행했거나 risk discovery 단계만 완료
- `NO-GO`: shard 장애/검색 저하가 큰 run을 대형 샘플 없이 승인하려는 경우

## 2026-04-26 샘플 아티팩트

이번 쿼리 확장 gate 검증을 위해 다음 입력 샘플을 생성했다.

| 단계 | 파일 | 건수 | 용도 |
| --- | --- | ---: | --- |
| smoke | `out/sampling/query_gate_parallel_smoke_20260426.jsonl` | 4 | 파이프라인/worker 로그 확인만 가능 |
| canary | `out/sampling/query_gate_canary_200_20260426.jsonl` | 200 | 병렬 실행 안정성, timeout/degraded 관찰 |
| risk discovery | `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl` | 1,000 | 위험 bucket 오류 유형 발견 |
| validation | `out/sampling/query_gate_validation_10000_20260426.jsonl` | 10,000 | 개선 전후 품질 비교용 대형 표본 |

4건 smoke 결과는 `SMOKE ONLY`이며 품질 승인 근거로 사용하지 않는다.

## 품질 개선 후 기본 자동 루틴

검색 품질, title/alias 판정, relevance gate, slang DB 저장 기준을 바꾸는 모든 개선은 다음 확대 순서를 기본값으로 실행한다.

1. targeted/unit 검증
2. 같은 입력 정책의 200건 canary
3. canary 통과 시 1,000건 risk discovery
4. risk discovery 리뷰 패킷 생성

운영 원칙:

- 200건 canary는 `completed=200/200`, `failed=0`, `pending=0`을 만족해야 1,000건으로 넘어간다.
- canary 이상은 `expert_main.py` startup auto-manage 경로를 우선 사용한다. 직접 shard를 올렸다면 전후 shard audit을 남긴다.
- `out/sampling/query_gate_canary_200_20260426.jsonl`과 `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`을 기본 회귀 입력으로 사용한다. 개선 유형에 맞는 must-id나 이웃 케이스가 필요하면 새 balanced input을 만들고 manifest를 남긴다.
- 각 run은 result/checkpoint/manifest/audit을 남기고, `VERIFICATION_RESULTS.md`에 명령, run id, 판정, 다음 작업을 기록한다.
- risk discovery는 안정성 승인이 아니라 오류 유형 발견 단계다. 결과가 완주해도 품질 판정은 정성 리뷰 전까지 `REVIEW`로 둔다.
- 시간/비용/인프라 문제로 자동 확대를 즉시 수행하지 못하면 defer 사유, 재개 명령, 예상 산출물 경로를 `HISTORY.md`와 `TODO.md`에 남긴다.

## 2026-04-27 canary 교훈

- `20260427_002737_046977` 200건 canary는 `REVIEW / NO-GO`.
- shard 감사는 전후 모두 `ok=36/36`이었으므로, shard 정상만으로 품질/처리 완료를 보장하지 못한다.
- checkpoint 기준 `199/200`, false failed `105`, stuck `1`이 발생했다.
- stuck post `11478694`는 비소설 매체/라이트노벨/애니 경계 케이스이며, 전문가 정성 리뷰 샘플에 고정 포함한다.
- 후속 canary 통과 기준:
  - checkpoint rows `200/200`
  - false failed `0`
  - stuck `0`
  - top latency post 목록 기록
  - off-domain media가 alias bridge로 재확장되지 않음

## 2026-04-27 canary 재실행 결과

- `20260427_121338_563339` 200건 canary는 안정성 기준 `GO`, 품질 기준 `REVIEW`.
- 실행 방식:
  - `expert_main.py` startup auto-manage 사용.
  - `MCP_SHARD_COUNT=36`, `MCP_AUTO_SHARD_LIMIT=36`.
  - `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=4`, `MCP_CLIENT_SEARCH_TIMEOUT_SEC=12`, `MCP_CLIENT_SEARCH_MAX_RETRIES=1`.
  - `--no-auto-up-shards` 미사용.
- 결과:
  - checkpoint rows `200/200`.
  - failed `0`, missing `0`, pending `0`.
  - 사후 shard audit `ok_count=36/36`, `bad_count=0`.
  - stuck 재현 케이스 `11478694` 완료, `703.9s`.
- 남은 검토:
  - top latency post: `11457804=886.4s`, `11478694=703.9s`, `11456200=586.5s`.
  - 검색 오류/timeout/infra no-result가 남아 1,000건 risk discovery와 정성 리뷰 필요.
  - 80건 리뷰 패킷: `out/llm_judgment_reviews/llm_judgment_review_20260427_121338_563339_20260427_135409.md`.
- 다음 단계:
  - late search budget 적용 후 같은 env와 startup auto-manage 조건으로 200건 canary 재확인.
  - canary에서 `late_budget_capped_total`, `late_budget_exhausted_total`, top latency, 검색 실행 수 변화를 기록.
  - 이후 1,000건 risk discovery 실행.
  - 10,000건 validation은 1,000건 결과와 리뷰 adjudication 이후 진행.

## 2026-04-27 late search budget 추가 검증 지침

- 목적: 초기 title/alias 탐색 recall은 유지하되, verification/recall/unresolved 검색이 반복되며 long-tail을 만드는지 제어한다.
- 기본 env:
  - `LLM_ENABLE_LATE_TOTAL_SEARCH_BUDGET=1`
  - `LLM_ENABLE_LATE_SEARCH_BUDGET=1`
  - `LLM_LATE_TOTAL_SEARCH_MIN_ITERATION=3`
  - profile별 기본 cap: `core_fast_resolve=14`, `uncertain_core=16`, `adjacent_meta=10`, `adjacent_meta_cheap=6`, `quarantine_candidate=3`, `deep_research=24`.
- 확인 로그:
  - `late search budget cap`
  - `late search budget exhausted`
- 비교 지표:
  - post별 `executed_queries`
  - `search_query_stats.late_budget_capped_total`
  - `search_query_stats.late_budget_exhausted_total`
  - top latency post와 `search_degraded`/`timed out` 로그 수

## 2026-04-27 afterfix11 risk discovery 결과

- run id `20260427_212634_728016`
- 입력 `out/sampling/query_gate_risk_discovery_1000_20260426.jsonl`
- 출력 `out/sampling/query_gate_risk_discovery_1000_afterfix11_20260427_result.json`
- 결과:
  - `completed=1000/1000`, `failed=0`, `pending=0`
  - `Relevant=746`, `Identified=351`
  - `search_timeout=29`, `search_upstream_zero=539`, `search_degraded_detected=130`
  - `reason_error_count=0`
- 리뷰 패킷:
  - `out/llm_judgment_reviews/llm_judgment_review_20260427_212634_728016_risk1000_afterfix11.md`
  - selected `1000/1000`
- 교훈:
  - risk discovery는 안정성 확인이 아니라 오류 유형 발견 단계다. 이번 run은 안정성은 `GO`였지만 품질은 `REVIEW`.
  - `character_parenthetical_title_resolved`, `generic_relation_only_demoted`, malformed/generic official title, relevant_without_title bucket을 다음 리뷰 우선순위로 둔다.

## 2026-04-28 afterfix12 36병렬 일반화 canary 결과

- run id `20260428_142042_238055`
- 입력 `out/sampling/query_gate_canary_200_20260426.jsonl`
- 출력 `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_result.json`
- 실행:
  - `MCP_SHARD_COUNT=36`
  - `MCP_AUTO_SHARD_LIMIT=36`
  - `--parallel 36`
  - `expert_main.py` startup auto-manage 사용.
- 결과:
  - `completed=200/200`, `failed=0`, `pending=0`
  - `Relevant=146`, `Identified=67`
  - `Total Time=2473.3s`, `Avg Time/Post=12.4s`
  - 사후 shard audit `ok=36/36`
- 일반화 매트릭스:
  - 실패 유형을 먼저 정의하고 negative/positive 이웃 케이스를 함께 확인했다.
  - `11718070` ECT 의학 일반글은 non-relevant.
  - `11631298` 일반 무협 세력어는 non-relevant.
  - `11663540` 캐릭터 parenthetical positive는 resolved 유지.
  - `11620037` source metadata title 오염은 제거.
  - `11562020` strong alias positive는 resolved.
- 산출물:
  - `docs/devs/GENERALIZATION_CASE_MATRIX.md`
  - `out/sampling/query_gate_canary_200_afterfix12_parallel36_retry_20260428_case_matrix.md`
  - `out/comparisons/query_gate_canary_200_afterfix11_vs_afterfix12_parallel36_20260428.md`
  - `out/llm_judgment_reviews/llm_judgment_review_20260428_142042_238055_afterfix12_parallel36.md`
- 교훈:
  - 36병렬 자체는 안정성 `GO`였지만, `11689276` adjacent 경계와 `11702067/11576520` alias long-tail이 남아 품질은 `REVIEW`.
  - 이후 1,000건 risk discovery도 같은 matrix를 유지하며 positive/negative 이웃 케이스를 포함해야 한다.
