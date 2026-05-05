# Development Checklist

변경 작업마다 이 체크리스트를 확인한다. 필요 없는 항목은 히스토리에 `해당 없음`으로 남긴다.

## 변경 전

- [ ] 기존 docs/TODO/checklist에서 관련 항목 확인
- [ ] 변경 대상 파일의 현재 사용자/기존 변경 여부 확인
- [ ] 관련 run id, 로그, output, DB 경로 확인
- [ ] 실패 증상과 확인된 사실을 분리해서 기록

## 구현 중

- [ ] 기존 패턴과 환경변수 이름을 우선 사용
- [ ] 대량 런에 영향을 주는 변경은 fail-open/fail-closed 정책 명시
- [ ] 검색/MCP 변경은 timeout, retry, backoff, failover 동작 확인
- [ ] slang DB 변경은 저장 기준과 오염 차단 기준을 함께 확인
- [ ] 새 도구는 `--help` 또는 기본 실행 경로가 명확해야 함
- [ ] 4~20건 스모크와 품질 검증 샘플을 혼동하지 않도록 표본 단계 명시

## 일반화 / 하드코딩 금지

- [ ] 특정 `post_id`, 특정 작품명, 특정 오답 문자열만 막는 조건을 추가하지 않음
- [ ] 새 실패 사례는 먼저 실패 유형, 증거 불변식, 허용/차단 기준으로 일반화해서 기록
- [ ] LLM 프롬프트 예시는 원리 설명용으로만 사용하고, 예시 문자열을 특수 규칙으로 만들지 않음
- [ ] 코드 lexicon이 필요하면 `의학/건강`, `장르 일반어`, `검색 메타데이터`, `타매체`처럼 범주 단위로 이름 붙이고 주석/문서에 근거를 남김
- [ ] 회귀 테스트는 해당 사례 1건만이 아니라 같은 실패 유형의 positive/negative 이웃 케이스를 포함
- [ ] 예외 rescue를 추가할 때는 과차단되는 정상 케이스와 과확정되는 오답 케이스를 함께 검증

## 검증

- [ ] Python 문법 확인: `.venv312\Scripts\python.exe -m py_compile <files>`
- [ ] 대량 런 감사: `.venv312\Scripts\python.exe tools\audit_expert_run_health.py --run-id <RUN_ID>`
- [ ] shard 감사: `.venv312\Scripts\python.exe tools\audit_search_shards.py --count <N>`
- [ ] 병렬 smoke: 4~20건, 판정은 `SMOKE ONLY`
- [ ] 병렬 canary: 최소 200건, timeout/degraded/worker 로그 확인
- [ ] risk discovery: 최소 1,000건, 위험 bucket 과표집
- [ ] validation: 최소 10,000건 또는 전체 run 100% 자동 감사와 결합
- [ ] slang DB 오염 지표 확인
- [ ] LLM/전문가 정성 리뷰 필요 여부 확인
- [ ] 필요 시 `tools/build_llm_judgment_review_packet.py --run-id <RUN_ID>` 실행
- [ ] 테스트 실행 가능 여부 확인. `pytest`가 없으면 그 사실을 기록

## 품질 개선 후 자동 확대 루틴

검색 품질, title/alias 판정, relevance gate, slang DB 저장 기준처럼 대량 런 품질에 영향을 주는 개선은 targeted 검증으로 끝내지 않는다.

- [ ] targeted/unit 검증이 통과하면 같은 턴의 기본 후속 작업으로 200건 canary를 실행
- [ ] 200건 canary가 `completed=200/200`, `failed=0`, `pending=0`을 만족하면 1,000건 risk discovery를 이어서 실행
- [ ] 200건 canary가 실패하면 1,000건으로 진행하지 않고 실패 원인, stuck/failed post, shard/search 상태를 먼저 기록
- [ ] canary/risk discovery는 `expert_main.py` startup auto-manage 또는 명시 shard audit을 사용
- [ ] 각 run마다 result/checkpoint/manifest/audit/review packet 경로를 `VERIFICATION_RESULTS.md`에 남김
- [ ] known bad, positive neighbor, negative neighbor의 판정 변화를 별도 기록
- [ ] canary에서 새 과보수/과확정 품질 회귀가 발견되면 1,000건으로 확대하지 않고 HOLD 사유와 단건 재현 결과를 문서화
- [ ] 시간/비용/인프라 문제로 즉시 실행하지 못하면 `HISTORY.md`와 `TODO.md`에 defer 사유와 재개 명령을 남김

## 개선 전후 자동 비교

기능/품질 개선은 구현만으로 완료하지 않는다. 같은 입력과 같은 shard/env 조건으로 개선 전후를 비교할 수 있어야 한다.

- [ ] baseline run id, 입력 JSONL, shard/env/worker 설정을 기록
- [ ] 개선 후 같은 입력으로 200건 canary를 자동 실행
- [ ] canary 통과 후 1,000건 risk discovery를 자동 실행
- [ ] canary 이상에서는 `expert_main.py` startup auto-manage 또는 명시 shard audit을 사용
- [ ] run audit을 baseline과 개선 run 양쪽에 실행
- [ ] checkpoint/manifest, failed/pending, search timeout/degraded, top latency를 표로 비교
- [ ] known bad post id의 판정 변화와 reason 변화를 별도 기록
- [ ] LLM 판단이 필요한 경우 개선 후 review packet을 생성
- [ ] 비교 결과 Markdown/JSON 경로를 `VERIFICATION_RESULTS.md`에 남김
- [ ] 자동화 스크립트가 없으면 수동 비교로 대체하되, 누락 사유를 `HISTORY.md`에 남김

## 문서 갱신

- [ ] `docs/devs/TODO.md` 색인 상태 갱신
- [ ] `docs/devs/DEV_TODO.md` 또는 `FEATURE_IMPROVEMENT_TODO.md` 상태 갱신
- [ ] `docs/devs/IMPROVEMENT_REGISTER.md` 개선 상태 갱신
- [ ] `docs/devs/HISTORY.md`에 결과/검증 추가
- [ ] `docs/devs/VERIFICATION_RESULTS.md`에 실행 명령과 판정 추가
- [ ] 관련 상세 문서 갱신 (`warp_sharding`, `slang_db`, run review 등)

## 완료 기준

- [ ] 문제 재현 또는 감사 결과가 문서화됨
- [ ] 조치 내용이 코드/설정/문서에 반영됨
- [ ] 검증 명령과 결과가 남음
- [ ] 개선 전후 비교 run 또는 비교 불가 사유가 남음
- [ ] 남은 위험과 다음 작업이 TODO에 남음
- [ ] 품질 판정이 `GO`, `REVIEW`, `NO-GO` 중 하나로 기록됨
