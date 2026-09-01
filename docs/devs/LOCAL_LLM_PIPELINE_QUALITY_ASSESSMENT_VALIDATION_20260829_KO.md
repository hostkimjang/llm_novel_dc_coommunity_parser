# 로컬 LLM 파이프라인 품질 현황 검증

작성일: 2026-08-29

대상: 현재 working tree와 최신 qualified 실제 런(`v7`, 2026-07-23)

## 종합 판정

- 현재 파이프라인은 **로컬/self-hosted LLM을 이용한 `shadow·review-only` 검증 단계까지 통과**했다.
- runtime completion, 선택된 v7 원장 계측, publication noninterference, 2,712행 deterministic publish-contract replay는 `GO`다.
- 자동 작품명 공개에 필요한 semantic quality, search health, review router, P2 early route, production activation, full scan은 `NO-GO`다.
- 따라서 운영 단계 표현은 `SHADOW_READY / PRODUCTION_NOT_READY`, `full_scan_approval=false`가 적절하다.

## 평가한 “로컬 LLM 수준”

이 문서에서 로컬 LLM은 모델 크기만의 등급이 아니라 저장소에서 실제 재현한 self-hosted 실행 조건을 뜻한다.

- model: `unsloth/gemma-4-26B-A4B-it-NVFP4`
- endpoint: `http://10.20.0.101:8000/`
- server: vLLM HTTP stream
- 실행 조건: 동일 RunSpec, search non-light, VLM/OCR ready, `--slang-db off`, requested/effective parallel `16/16`, dashboard ON

README의 `LLM_BACKEND=local`과 `LLM_MODEL_PATH`는 선택 가능한 별도 backend일 뿐, 최신 품질 수치를 만든 실제 model path의 증거는 아니다. 따라서 `26B`라는 이름만으로 다른 로컬 모델의 품질을 추정하지 않는다.

## 최신 실제 런의 품질

선택된 qualified 표본은 고위험 32행의 BEFORE/OFF와 AFTER/AUDIT_ONLY를 각각 3회 실행한 총 192개 관측이다. 이 표본은 전체 데이터의 무작위 정확도 표본이 아니다.

| 지표 | BEFORE | AFTER | 해석 |
| --- | ---: | ---: | --- |
| adjudicated majority compliance | 18/32, 56.25% | 18/32, 56.25% | 순개선 없음 |
| exact compliant runs | 54/96, 56.25% | 54/96, 56.25% | 순개선 없음 |
| unsafe publish any-run | 3/32, 9.38% | 1/32, 3.13% | 2건 해소, 1건 지속 |
| wrong-title publish any-run | 2/32, 6.25% | 0/32, 0% | 개선 |
| correct-title recovery majority | 1/11, 9.09% | 1/11, 9.09% | 확대 실패 |
| wrong-work 미회복 | 3/5, 60% | 3/5, 60% | 미개선 |
| HOLD integrity majority | 4/5, 80% | 4/5, 80% | evidence conflict 1건 지속 |
| PASS retention majority | 2/2, 100% | 2/2, 100% | 정상 대조군 유지 |
| FP_NONNOVEL false positive | 0/3 | 0/3 | 유지 |

핵심 미해결은 `11718099` evidence-conflict unsafe publish와 wrong-work 3건이다. correct-title recovery도 1/11에 머문다. 따라서 56.25%는 “전체 운영 정확도”가 아니라 **의도적으로 어려운 회귀 cohort에서의 통과율**로만 사용한다.

## 독립 게이트

| 게이트 | 상태 | 근거와 경계 |
| --- | --- | --- |
| runtime completion | `GO` | 선택 6개 arm 모두 32/32 completed·flushed, failed/pending 0 |
| v7 call measurement | `GO` | immutable ledger exact linked 192/192; 아래 신규 framing 결함 때문에 구현 일반성은 조건부 |
| publication noninterference | `GO` | WAL event/hash 불변, `public_apply=false` |
| 2,712 publish-contract replay | `GO` | 2,712/2,712, projection/reason/fingerprint mismatch 0, normal→abnormal 0 |
| semantic auto activation | `NO-GO` | majority 18/32, unsafe 1건 지속, wrong-work 3/5 |
| search health | `NO-GO` | unrecovered degraded 182→178, AFTER `SEARCH_DEGRADED` 56/96 |
| review router | `NO-GO` | high-risk recall 44/66→43/66(65.15%) |
| production/full scan | `NO-GO` | targeted 32행과 deterministic replay만 완료, `full_scan_approval=false` |

2,712 replay는 저장된 공개 계약을 현재 코드로 재계산한 결과다. 네트워크와 LLM을 다시 호출하지 않았으므로 2,712행의 의미 정확도 증거로 사용하지 않는다.

## 현재 코드와 산출물 일치 검증

- 현재 release fingerprint: `1ab9e3507c362c309427cbb69832815b2f69e3a173511c2783dc947c58f983aa`
- v7 source-owner release fingerprint: 동일
- 2026-08-29 관련 명시 모듈: `403 tests`, `OK`, 28.692초
- 변경·신규 production/tool Python: `py_compile OK`
- `git diff --check`: 기존 `expert_main.py:11280` trailing whitespace 1건
- 핵심 개선은 아직 미커밋 working tree에 있으며 modified/untracked 변경이 많아 커밋 단위 bisect는 불가능하다.

테스트 명령은 client/Synthesizer/shape guard, publication·measurement·router·recovery, analyzer, frozen cohort/replay, alias/Arbiter/search 계약 26개 모듈을 명시 실행했다. `unittest discover`의 import-time argparse 충돌을 피하기 위해 명시 모듈 방식을 사용했다.

## 이번 감사에서 새로 재현한 계측 결함

vLLM SSE의 JSON 반복 이벤트와 terminal usage 이벤트가 한 `iter_text()` 청크에 합쳐지면 의미 텍스트는 첫 JSON으로 안전하게 동결되지만, 이미 로컬 buffer에 남은 usage를 drain reader가 읽지 못한다.

- 입력 usage: prompt/completion/total `7/11/18`, finish reason `stop`
- 실제 결과: usage provenance `ESTIMATED`, 추정 usage `1/1/2`, finish reason `None`
- 원인: `src/llm_batch/llm/client.py:1433-1467`에서 inner buffer loop를 중단한 뒤 `:1158-1247`의 drain이 기존 buffer가 아니라 공유 iterator의 다음 청크부터 읽음
- 테스트 공백: 기존 repeat/hard-cap 테스트는 usage SSE를 별도 generator yield로만 제공
- 영향: 의미 텍스트 자체를 unsafe하게 공개하지는 않지만 Synthesizer quarantine, measurement `NO-GO`, 비용 누락, 재실행 증가를 만들 수 있음

이 결함은 저장된 v7의 192/192 계측 사실을 뒤집지 않는다. 다만 transport framing이 달라지는 다른 서버·프록시·httpx 조합까지 계측이 일반화됐다는 주장은 막는다.

## 비용·성능

| 지표 | BEFORE | AFTER | 변화 |
| --- | ---: | ---: | ---: |
| expert calls | 883 | 867 | -1.81% |
| total tokens | 11,516,810 | 11,337,065 | -1.56% |
| completion tokens | 565,056 | 621,973 | +10.07% |
| physical-call wall | 32,867,375ms | 35,823,371ms | +8.99% |
| run-wall 합 | 3,210.4s | 3,949.8s | +23.03% |

호출·전체 토큰은 소폭 줄었지만 completion과 wall time은 증가했다. AFTER의 긴 retry tail과 3회 소표본이 섞여 있으므로 비용·속도 개선으로 승인하지 않는다.

## 다음 통과 조건

1. same-chunk SSE framing 회귀 테스트와 buffer-first usage drain을 검증한다.
2. `11718099` evidence-conflict를 `HOLD`로 봉인하고 HOLD integrity 5/5를 반복 통과한다.
3. wrong-work 3건의 `primary/mentioned/comparison` 관계와 competing-work 근거를 보강해 미회복 0/5를 만든다.
4. `아생갤` 계열은 explicit alias relation, specific-work target, 공식/커뮤니티 근거, 경쟁 본문 작품 근거를 분리한 전용 cohort로 측정한다.
5. search unrecovered 0과 high-risk router recall green을 먼저 달성한다.
6. 그 뒤에만 P2 188행 canary와 family-wide/full semantic scan을 `--parallel 16`, dashboard ON, 최소 2회 반복으로 연다.

## 근거 산출물

- `docs/devs/NEXT_STRUCTURAL_AND_MEASUREMENT_IMPROVEMENT_FINAL_VALIDATION_20260723_KO.md`
- `out/regression_safe_2712_next_improvements_20260722/grouped_ab_v7_early_stop_drain_20260722_231437/grouped_analysis_v7_qualified/repeat_consensus_summary.json`
- `out/regression_safe_2712_next_improvements_20260722/grouped_ab_v7_early_stop_drain_20260722_231437/grouped_analysis_v7_qualified/sidecar_grouped/report.json`
- `out/regression_safe_2712_next_improvements_20260722/grouped_ab_v7_early_stop_drain_20260722_231437/frozen2712_publish_contract_replay_final_qualified_20260723/publish_contract_replay_summary.json`
- `docs/devs/CHECKLIST.md`

최종 신뢰도는 실행·공개 계약 `높음`, targeted 의미 품질 `중간`, alias/search 일반화 `낮음~중간`, 대형 운영 품질 `낮음`이다.
