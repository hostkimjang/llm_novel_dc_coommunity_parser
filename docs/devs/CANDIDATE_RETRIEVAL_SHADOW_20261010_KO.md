# 고정 작품 자료의 후보 회수 SHADOW

2026년 10월 10일 승인된 개발 계획의 R2 기능을 기본 프로젝트 폴더에 구현했다. 고정 corpus 로더·원문 후보 회수·실제 pipeline 주입·저장·표시·평가기 연결을 포함한다. 실제 source-backed corpus와 참조 ID 대응 자료가 없어 **실제 회수 성능은 미평가**다. 최종 통합 시험 결과는 아래 검증 기록에서 따로 관리한다.

## 실행과 저장

`expert_main`의 기본값은 `--candidate-retrieval OFF`다. OFF에서는 corpus를 읽지 않고 기존 파이프라인에 관측기를 주입하지 않는다. `SHADOW`는 고정된 작품 자료에서 원문과 관련된 후보를 조회하며, 원래 검색·전문가 호출·제목 선택·공식 URL 공개 경로에는 후보를 추가하지 않는다.

설정은 명시적인 CLI로만 받는다. SHADOW에는 `--candidate-corpus <파일>`과 `--candidate-corpus-sha256 <소문자 SHA-256>`가 필요하며 `--candidate-retrieval-top-k`의 기본값은20, 허용 범위는1~100이다. 저부하 실제 검증에는 사용자 지시에 따라 `--execution-profile low-load-validation --parallel 12`와 대시보드 ON을 사용한다. 입력이 12건 미만이면 실효 병렬도가 줄어들 수 있으므로 manifest의 requested/effective parallel을 함께 확인한다.

인덱스는 실행당 한 번 준비하고 워커가 읽기 전용으로 공유한다. query는 해당 게시글의 원래 제목·본문·댓글만 사용하고 각 원문 위치를 유지한다. 최종 공식 제목, 정답 라벨, 다른 게시글의 관측 결과를 query로 사용하지 않는다.

관측은 `run_meta.candidate_retrieval_shadow`에 저장한다. 게시글·입력 순번·실행·attempt·publication scope를 함께 기록하고 공개 payload의 durable digest에서는 제외한다. 이전 결과를 참조하는 early-route에서는 이번에 검색한 것처럼 기존 관측을 복사하지 않고 `PIPELINE_NOT_EXECUTED`로 남긴다. 관측 누락, 게시글 결속 불일치, 알 수 없는 스키마, 비정상 크기는 명시적인 미가용 상태다.

유효 설정과 종료 manifest에는 `candidate_retrieval_policy`를 저장한다. 대시보드의 live/history 상세는 상태·corpus/query 지문·후보 ID·점수·출처·행 결속을 표시한다. 관측 자료는 결과 목록이나 SSE에 싣지 않는다. 후보가 없는 것은 NIL 판정이 아니다.

## 판정과 분리되는 경계

- 관측은 `publication_authority=false`, `central_db_write=false`다.
- 후보 ID는 표시 제목과 별개다. 동명 작품과 판본·매체 차이를 보존한다.
- source lineage가 같은 mirror 자료를 독립 근거로 세지 않는다.
- 점수가0인 문서를 회수 성공으로 계산하지 않는다.
- 오류나 제한을 회수 성공 또는 제목 공개 근거로 바꾸지 않는다.
- 예전 합성 benchmark의 후보 모음은 실제 평가용 작품 corpus를 대신하지 않는다.

## 검증과 실제 평가

단위 시험 외에 실제 `AgenticPipeline.process_post`를 fake 전문가로 실행해 OFF/SHADOW에서 기존 모델·검색 호출과 공개 결과가 같은지 확인한다. 동일 pipeline 재사용, 독립 게시글 동시 관측, 예외·한도, 저장 및 대시보드 전달도 검사한다.

Recall@1/5/10/20과 lane/union은 동일한 JUDGED+WORK 분모를 사용해야 한다. 미가용·불완전 검색은 운영 회수 분모에서 누락하지 않는다. MRR·선택 정확도는 gold-present 조건분모를 따로 둔다. corpus와 참조 후보의 immutable ID 대응이 없으면 실제 성능을 계산할 수 없다.

로컬 합성 시험이 통과해도 실제80 실행, 의미 검토, 회수율 개선 또는 formal KPI 완료로 표시하지 않는다.

## corpus와 관측 계약

입력 파일은 `frozen_candidate_corpus_v1` JSON이다. 최상위에 `corpus_id`, `data_kind`, `entries`를 둔다. `data_kind`는 SOURCE_BACKED 또는 SYNTHETIC_FIXTURE다. 각 entry는 다음 필드를 요구한다.

| 필드 | 의미 |
|---|---|
| corpus_candidate_id / work_id / edition_id / media_type | 후보·작품·판본·매체의 독립 좌표 |
| title / aliases / text | 실제 회수에 쓰는 자료. 평가 reference를 넣지 않음 |
| content_sha256 | title·aliases·text의 canonical JSON 지문. 원본 페이지 byte SHA와 구분 |
| sources[].source_ref / source_sha256 / lineage_id | 선언된 출처 위치·원본 지문·공통 계보 |
| sources[].observed_at / rights | 시간대가 있는 관측 시각과 재사용 상태·근거 |

`candidate_content_sha256(title, aliases, text)`로 내용 지문을 계산한다. SOURCE_BACKED는 `rights.status=REUSE_PERMITTED`, 합성 자료는 SYNTHETIC_FIXTURE를 명시한다. loader는 corpus 바이트·필드·지문·명시된 만료를 검사하지만 source_ref의 페이지를 가져오거나 권리 주장을 독립 검증하지 않는다. 따라서 `source_refs_independently_verified=false`를 저장한다. `valid_until`이 없으면 신선도를 확인한 것으로 표시하지 않는다.

corpus16MiB·entry5,000개, query12,000자·fragment128개·token2,048개, scoring operation2,000,000회 상한이다. 원문 조각을 각각 토큰화해 조각 경계를 넘어 가짜 별칭을 만들지 않는다. scorer는 기존 연구 benchmark와 같은 한글·영문·숫자 regex/lower 토큰화, BM25 k1=1.5·b=0.75를 사용하고 후보 ID로 동점을 정렬한다. 형태소 분석·학습 검색기는 아니다.

동일 work/edition/media와 content SHA·lineage 집합을 가진 mirror만 합치며 원래 candidate ID와 출처를 보존한다. 양수 점수 후보만 반환하고 확률은 만들지 않는다. 관측은48KiB, 실행 결속을 더한 저장 관측은64KiB 상한이다. 후보 전체와 출처를 함께 보존할 수 없는 꼬리는 명시적으로 생략하며 제한 상태를 남긴다.

정상 상태는 OK, NO_MATCH, EMPTY_QUERY, EMPTY_CORPUS로 구분한다. corpus 오류는 UNAVAILABLE_CORPUS, query·계산·receipt 한도는 각각 명시 상태다. pipeline은 원문 캡처·observer·직렬화 오류를 격리한다. 캡처 실패 때 만들지 못한 전체 원문 SHA는 null이다. 정상 관측은 latency를 제외한 `observation_sha256`를 보존하고, query SHA를 보완한 제한 관측은 원래 지문과 보완 후 지문을 구분한다.

## 재사용 API와 자료 준비 상태

순수 로더는 `llm_batch.grounding.candidate_retrieval_shadow.load_candidate_retrieval_shadow`이며 반환한 불변 객체의 `observe(source_view)`와 `summary()`를 사용한다. 기존 `research_local_benchmark.py` 등 primary 연구6파일은 수정하지 않았다. 운영 연결은 `runtime/candidate_retrieval.py`, 판정 주입은 `AgenticPipeline`의 선택 인자, 표시는 dashboard presentation에 있다.

평가기는 `measurement/candidate_retrieval_evaluation.py`의 `evaluate_candidate_retrieval(snapshot, observations, corpus=..., id_mapping=..., lane_names=...)`다. 저장 관측은 `observation_from_saved_shadow(snapshot_row)`로 변환한다. R1 snapshot·corpus SHA와 corpus/CandidateOption/reference ID 대응을 명시적으로 결속하며 query·관측 지문 및 알려진 run/attempt/scope carrier를 각각 대조한다. 누락은 성공으로 바꾸지 않고, 알려진 모순은 INVALID_BINDING으로 거절한다. 상세 입력은 [평가기 계약](../../out/development_plan_20261010/r2_evaluator_contract_KO.md)을 따른다.

[자료 준비 조사](../../out/development_plan_20261010/r2_data_readiness_KO.md)에서 기존80/32 관측과 모델 참조16건은 확인했지만 신규 계약에 맞는 작품 corpus·불변 ID 대응은 확인하지 못했다. 기존 WORK2의 선호 제목은 원래 MODEL_REFERENCE이며 공식 URL·corpus ID를 대신하지 않는다. 현재 R1 snapshot112관측은 reference 미결속이고 unique post는80이다. 실제 Recall·정확도·비용 개선은 NOT_ESTIMABLE로 유지한다.

## 검증 기록

adapter30개, pipeline15개, evaluator 수리25개의 개별 시험은 통과했다. pipeline 시험은 실제 process_post·orchestrator에 fake 전문가를 붙여 모델2회·검색1회의 인자와 공개 결과가 OFF/SHADOW에서 같음을 확인했다. 실제 frozen adapter→pipeline→root 저장→stable publication payload 연결도 포함한다. 실제 원격 모델 호출은0이다.

독립 검토에서 attempt receipt의 scope가 없을 때 ledger의 알려진 scope 모순을 놓치는 결함을 재현해 수리했다. 초기 [검토 보고](../../out/development_plan_20261010/r2_integration_review_KO.md)는 당시 반례로 보존한다. [후속 독립 검토](../../out/development_plan_20261010/r2_integration_final_review_KO.md)의14개 확인은 모두 통과했고 미해결 지적은 없다.

화면은 순수 adapter와 저장 exporter로 만든 SYNTHETIC_DISPLAY_FIXTURE를 primary 서버에 표시했다. live/history에서 원문/corpus 지문·후보 ID·출처·판본·웹소설/웹툰 구분과 공개권한 false를 확인했다. 콘솔 오류·경고0,1280px 화면 가로 넘침0이었다. fixture manifest의 publication scope가 없어 PARTIAL로 표시되며 실제 공개 승인 자료가 아니다. 임시 서버18767과 탭은 종료했다. [화면 수령증](../../out/development_plan_20261010/r2_browser_receipt.json)에 범위를 기록했다.

![합성 후보 관측의 실제 상세 화면](../../out/development_plan_20261010/r2_browser_live.png)

최종 통합 회귀는33개 Python 파일608개 시험＋subtests122개, 프런트엔드23개가 모두 통과했다. 실패·오류·skip0, 시험 중 소스 변경0, 외부 socket 시도0이다. 실제 CPython PID81700의 BelowNormal16384·affinity2·수치 스레드5개=1을 시작·종료 시 확인했다. 총86.801초이며 경고1개는 pytest의 기존 Temp garbage 디렉터리 정리 WinError145다. 해당 디렉터리는 임의 삭제하지 않았다. [통합 수령증](../../out/development_plan_20261010/r2_validation_receipt.json)·[Python 로그](../../out/development_plan_20261010/r2_validation_tests.log)·[표시 로그](../../out/development_plan_20261010/r2_validation_node.log)에 근거가 있다. 개별 시험과 겹치므로 합산하지 않는다.

현재 R2 게이트는 **FUNCTIONAL_VERIFIED / ACTUAL_DATA_PENDING**이다. P4 새80건은 자동 승인 검토 차단으로 미시작이며 R3~R6은 별도 후속 작업이다. 앱 Goal은 active로 유지한다.

원본 worktree 선택67파일, primary 연구6파일, 기존32 result/manifest, R2 수정 전 백업과 최종 시험 후 소스·시험 지문을 대조했다. Git index의 byte SHA는 바뀌었지만 HEAD와 staged binary patch는 그대로이며 stage·reset·commit을 수행하지 않았다. 따라서 index 바이트 불변을 주장하지 않는다. [보존 수령증](../../out/development_plan_20261010/r2_preservation_receipt.json)에 이 차이와 대조 범위를 남겼다.
