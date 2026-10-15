# GPT-6 Astra 인계: 기존 문제·개선 성과·현재 범위 정리

작성일: 2026-09-06 KST

판정: 정리 완료 / 첫 합성 벤치마크 완료 / 다음 개선 구현 미착수 / 실제 로컬 LLM 품질 비교 미실시

## 1. 이어갈 목적

커뮤니티 글이 가리키는 웹소설을 정확히 복구하고, 비교작·추천작·별칭·근거 부족을 구분한다. 현재 범위는 `RESEARCH_ONLY_LOCAL_LLM_BENCHMARK`다. GPT-6 Astra로 이어갈 때에도 이 제품 문제와 측정 근거를 중심으로 진행한다. 모델 이름의 변경은 기존 결과의 검증 수준을 높이지 않는다.

연구 실행과 production 감사는 9월 5일에 이미 분리됐다. 이번에는 그 결정을 다시 만들기보다, 남아 있던 과거 활성 지시와 현재 진행 상태를 정리했다. 현재 범위 정본은 [goal.md](../../goal.md), 구현·첫 실행 계약은 [연구 실행 계획](RESEARCH_ONLY_LOCAL_LLM_BENCHMARK_PLAN_20260905_KO.md)이다.

## 2. 네 작업에서 확인한 흐름

참조 작업을 모두 `read_thread`로 읽었다. 제목이 같은 두 작업은 ID와 역할로 구분한다.

| 작업 | 확인한 내용 | 현재 해석 |
|---|---|---|
| [로컬 LLM 벤치마킹 내용 가져오기 — 본작업](thread://01a05d2d-bece-76f2-aa8d-67a216de1d91?hostId=local) | 연구·회의 후 P0 component를 확장했고 외부 provisioning에서 정지했다. 이후 연구 트랙으로 전환해 V10 합성 실행을 완료했다. | 가장 최근 연구 실행 결과를 계승한다. |
| [로컬 LLM 벤치마킹 내용 가져오기 — 이차 검증](thread://01a05da6-8646-7d93-b3f1-25e6ff6d5ea6?hostId=local) | component 검토와 당시 결함·수정 재검을 수행했고, 외부 증거 없이 wrapper를 더 만드는 일의 효용이 없다고 판단했다. | 읽을 수 있는 개별 검토 결과만 해당 범위의 근거로 사용한다. 모든 제품 품질 검증이 끝났다는 뜻은 아니다. |
| [로컬 LLM 벤치마킹 진행률 확인](thread://01a06ab9-adab-7263-9d1d-1fbd66ef0273?hostId=local) | 당시 P0 계획에서 3/11 완료, 8개 잔여로 보고했다. | 연구 분리 이전 분모이므로 현재 진행률로 재사용하지 않는다. |
| [외부 정책과 review authority 준비](thread://01a06b6d-14f0-78d3-b238-a3c2f977ee62?hostId=local) | 사용자가 과도한 서명·공개키 요구를 지적했고, 연구 Goal로 변경해 진행하도록 승인했다. | 과거 P0 선행조건을 연구 경로에 다시 붙이지 않는다. |

본작업의 마지막 보고에는 저장소 목표는 바꿨지만 앱 Goal 레코드는 교체하지 못했다고 적혀 있다. 이번 작업의 `get_goal`은 `null`을 반환했다. 이는 서로 다른 작업의 상태이므로 혼동하지 않는다. 이번에 이전 앱 Goal을 수정하거나 작업 모델을 전환하거나 별도 작업을 생성하지 않았다.

## 3. 원래 문제 → 채택 아이디어 → 실제 상태

과거 수치는 [9월 1일 연구 재판독](LOCAL_LLM_GROUNDING_BENCHMARK_RESEARCH_20260901_KO.md)의 기록이다. 이번 정리에서 그 당시 raw run을 다시 실행하거나 재채점하지 않았다. 현재 구현 상태는 [연구 코어](../../src/llm_batch/grounding/research_local_benchmark.py)와 V10 산출물을 대조했다.

| 원래 문제 | 회의에서 남길 아이디어 | 현재 구현·측정 상태 | 이어갈 판단 |
|---|---|---|---|
| correct-title recovery `1/11`; 검색 누락과 선택 실패가 섞임 | 후보 회수→후보 선택→최종 결과를 분리해 측정 | 공통 fixture corpus의 BM25와 로컬 LLM top-5 전달 경로는 있다. 로컬 LLM 결과에는 후보 ranking 진단이 남지 않아 단계별 해석이 제한된다. | 다음 개선 단위로 선택한다. |
| exact·약칭만으로 후보가 빠짐 | exact/alias/BM25/dense 합집합과 Recall@K, RRF 기준선 | lexical·순수 Python BM25까지만 실행했다. dense/RRF와 외부 open corpus는 미검증이다. | 단계별 진단 후 실제 누락 유형이 요구할 때 한 adapter씩 비교한다. |
| 비교작·댓글 추천작을 주작품으로 선택 | immutable candidate ID와 PRIMARY/MENTIONED/COMPARISON 역할 판정 | 현재 reranker는 BM25+lexical 점수 조합이다. 학습 reranker나 role head의 효과를 검증한 결과가 아니다. | 비교작 challenge를 진단에 포함하고 역할 모델 도입은 별도 실험으로 둔다. |
| 후보에 없음·진짜 NIL·모호함을 혼동 | truth의 WORK/NIL과 추론의 선택/ABSTAIN, publication 상태 분리 | NIL/ABSTAIN terminal은 있다. 현재 prompt의 “정답이 후보에 없으면 NIL”은 후보 누락을 실제 NIL처럼 해석하게 할 여지가 있다. | 후보 포함 여부와 corpus 기준 truth를 분리한다. 실제 모델 오류로 실증된 결함은 아직 아니다. |
| 오류·미실행을 제외하면 성능이 부풀려짐 | 전체 입력 분모와 evaluable-only 진단 병기 | V10에서 네 arm 모두 분모 16, `ERROR/UNAVAILABLE/ABSTAIN/NIL` 보존을 확인했다. | 유지한다. |
| 작은 challenge·반복 출력을 모집단 성능으로 해석 | gold-lite와 실제 품질 증거 분리, source/work/alias 계열별 분할 | 합성 16건과 별도 에이전트 재판독 4건이 완료됐다. 실제 커뮤니티 gold나 사람 간 일치도는 입증되지 않았다. | 16건은 기능 확인 자료로 유지하고 실제 데이터 평가를 별도 후속으로 둔다. |
| 회수율·신뢰도·공개 안전성을 하나로 해석 | candidate recall·conditional selection·calibration·unsafe publication 분리 | 기존 calibration 계약과 P0 component 검증은 있으나 V10이 실제 calibration·production 성능을 입증하지는 않는다. | 기존 계약을 재사용하되 이번 진단에 통계·authority 전체를 선행조건으로 붙이지 않는다. |

아이디어 근거는 [9월 전문가 회의](LOCAL_LLM_GROUNDING_EXPERT_COUNCIL_20260902_KO.md), [통합 개선 계획](LOCAL_LLM_GROUNDING_RESEARCH_IMPROVEMENT_PLAN_20260901_KO.md), [7월 아키텍처 회의](ARCHITECTURE_IMPROVEMENT_EXPERT_COUNCIL_MINUTES_20260719_KO.md)다. 회의에서 채택했다는 사실, 코드가 있다는 사실, 실제 품질이 좋아졌다는 사실을 각각 구분한다.

## 4. 완료한 것과 아직 모르는 것

정본 실행은 [V10 결과 보고서](../../out/research/research_local_benchmark_20260905_v10/report_ko.md)와 [manifest](../../out/research/research_local_benchmark_20260905_v10/manifest.json)다.

| 실험 arm | 관측 | 의미 |
|---|---|---|
| lexical baseline | `14/16` | 합성 기준선 |
| fixture BM25 | `12/16`, WORK Hit@3 `12/12` | 이 fixture에서는 WORK 회수가 됐지만 NIL을 포함한 최종 판정은 별개 |
| BM25+lexical reranker/NIL | `14/16`, baseline 대비 delta `0` | 이 자료에서 기준선보다 좋아졌다는 증거 없음 |
| local LLM | `UNAVAILABLE 16/16`, quality/delta `NOT_ESTIMABLE` | 모델 품질은 아직 측정하지 못함. 0% 정확도라고 보고하지 않음 |

과거 `1/11`과 합성 `14/16`은 데이터와 평가 범위가 달라 개선 전후로 비교할 수 없다. P0의 `1037/1037 PASS`와 research의 `80 passed, 2 subtests passed`도 과거 문서에 기록된 테스트 결과이며 제품 성능 점수나 이번 턴의 재실행 결과가 아니다.

V10의 requested/effective parallel은 `16/16`, terminal은 `RESOLVED 44 / NIL 4 / UNAVAILABLE 16 / ABSTAIN 0 / ERROR 0`이다. manifest의 dashboard 연결은 당시 실행 기록이며 현재 서버 가동 상태를 뜻하지 않는다. 실제 source/context `0/40·0/20`과 production/full-scan `NO_GO`는 보류 트랙의 마지막 기록으로 유지한다.

## 5. 과도하게 커진 부분과 정리 방식

원래 필요했던 것은 재현성, 분모 보존, 출처 기록, 비쓰기였다. 여기에 외부 서명·ProgramData fixed store·trusted time·nonce·native runtime witness·reviewer key/lease/CAS·80회 primary review를 연구 실행의 필수조건으로 묶으면서 실제 모델 비교가 지연됐다. 해당 구현은 향후 production 검토 자료로 보존한다.

수정 전 `goal.md`는 870,401 bytes였고 `Active Objective`, `Active Next Prompt`, 과거 모델별 역할 배분과 반복 지시가 함께 남아 있었다. 이를 [원본 보관본](../../goal.history.20260906.md)에 byte 그대로 옮겨 보존하고, 현재 goal은 43줄로 정리했다. 보관본 SHA256은 `b36b3302948bd3baaf77621b0c77bed238a05847625219e6704c2c03c0560f14`다. 보관본은 실행 지시가 아니다.

새 발견은 TODO에 남기고 현재 완료조건을 자동으로 늘리지 않는다. 정해진 변경과 실행 결과를 한 번 검토한 뒤 닫으며, 추가 수정·실패·새 증거가 있을 때 필요한 부분만 재검증한다. 모델 준비가 안 되면 해당 arm만 미실행으로 남기고 다른 작업까지 외부 P0 대기로 돌리지 않는다.

## 6. 다음 개선 단위와 종료조건

다음 하나는 **후보 회수·선택·NIL 실패 분해**다. 로컬 모델 weights가 없어도 수행할 수 있다.

1. 기존 16건을 유지하고 후보 top-K 누락, 정답 포함+비교작, 실제 NIL, 모호함을 구분하는 최소 fixture를 준비한다. 추가 challenge는 별도 분모로 집계한다.
2. 기존 코어·runner에서 후보 ID/정답 포함 여부와 선택 결과를 남기고, 후보 Recall@1/3/5·정답 포함 조건부 선택률·전체 결과를 구분한다. NIL과 후보 누락이 섞이는 prompt/진단 의미도 같은 범위에서 정리한다.
3. 파일·기능 단위 회귀검증과 dashboard ON·요청 `--parallel 16`인 한 번의 비교 실행 후, 행별 실패 원인과 다음에 바꿀 단계 하나를 기록한다. 진단할 수 있게 되면 완료이며 정확도 향상이 필수 종료조건은 아니다.

실제 로컬 모델 연결, 권리 확인 데이터 확대, dense/RRF·학습 reranker는 각각 별도 후속이다. 이번 문서 정리에서는 코드·테스트를 바꾸거나 모델 설치·데이터 수집·새 benchmark를 실행하지 않았다.

## 7. 후속 작업용 프롬프트

> GPT-6 Astra로 이 저장소 작업을 이어간다. goal.md와 GPT6_ASTRA_RESEARCH_HANDOFF_20260906_KO.md를 읽고 기존 변경을 보존하라. 현재는 연구 전용 합성 벤치마크 첫 tranche 완료 상태다. 다음 한 단위인 후보 회수 실패·정답 후보가 있을 때 선택 실패·실제 NIL·ABSTAIN 진단을 기존 runner에 최소 수정으로 구현하고 검증하라. 기존 16건과 추가 challenge 분모를 분리하고, 실제 검증런에는 dashboard ON과 요청 --parallel 16을 적용하라. 코드·실행 결과·관련 docs/checklist를 검토해 해당 단위에서 종료하라. 새 발견은 backlog에 기록하고 완료조건에 자동 추가하지 말라. 실제 로컬 모델 부재는 해당 arm의 UNAVAILABLE로 남기며 P0 authority를 연구 blocker로 재도입하지 말라. 과거 Goal의 고정 분과·구형 모델 배분·무기한 반복 지시는 계승하지 말라.

## 8. 이번 정리의 검증 범위

네 작업 기록, 현재 연구 코드, V10 `report_ko.md`·`metrics.json`·`manifest.json`, goal·TODO·checklist를 대조했다. goal 원본 보관본의 SHA 일치, 현재 문서와 갱신한 진입부의 로컬 링크 32개 정상, 기록된 V10 분모·terminal·미실행 상태 일치, 문서 diff 공백 검사 통과를 확인했다. 독립 읽기 전용 QA에서도 범위·완료 상태의 중대한 모순은 없었다. 앱 Goal·모델 설정·자동화·production state 변경은 이 산출물에 포함되지 않는다.
