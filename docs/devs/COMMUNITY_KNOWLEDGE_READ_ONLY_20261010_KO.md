# 커뮤니티 지식 READ_ONLY 구현·검증 기록

2026-10-10. 승인 계획 R3의 **FUNCTIONAL_VERIFIED / ACTUAL_DATA_PENDING** 기록이다. 로컬 기능 구현·통합 시험·실제 화면·독립 검토를 마쳤으며 실제 corpus 품질 평가는 남아 있다. 당시 P4 새80 실행은 사용자 재승인 후에도 자동 승인 검토의 `blocked by policy`로 차단돼 있었다. 이후 재승인 실행·의미 검토·화면 관측의 현재 상태는 [P4 운영 인계](P4_REAPPROVAL_RUN_20261010_KO.md)를 따른다. 이 문서의 기능 시험과 R3 OFF인 후속80 실행은 실제 READ_ONLY 지식 품질 평가를 대신하지 않는다.

## 기능과 범위

로컬에 확보된 원문을 중립 parser로 읽고 수집 후보 ledger, 작품 별칭 registry, 일반 community lexicon을 분리해 저장한다. 고정 snapshot을 읽어 원래 게시글 제목·본문·댓글의 surface를 조회하고, 적격 후보와 경쟁 의미를 Decoder의 별도 문맥으로 전달한다. `아생갤`과 `갤러리`를 무조건 현실 갤러리명으로 해석하지 않는다.

기본값은 OFF다. READ_ONLY는 저장소 쓰기와 자동 승격을 하지 않는다는 뜻이며 **모델 입력·결과가 OFF와 같다는 뜻은 아니다.** 모델 입력에 영향을 주는 snapshot·조회 정책을 실행의 판정 설정 지문에 포함한다. 이전 OFF 실행의 판정 범위를 그대로 재사용하지 않는다. 소비 영수증만 바꾼 경우의 stable payload 동일성과 실제 추론 결과 동일성은 별개다.

이번 버전은 로컬 캡처만 변환한다. 외부 자동 수집·새 sense 생성·중앙 Slang DB 자동 승격을 구현한 것으로 표시하지 않는다. `SOURCE_BACKED`와 `SYNTHETIC_FIXTURE`를 분리하며, 원문·권리 근거의 byte hash 확인은 그 내용의 사실성이나 권리 선언의 법적 효력에 대한 독립 검증이 아니다.

## 설정과 쓰기 경계

| 설정 | CLI | 환경변수 | 기본값 |
|---|---|---|---|
| 모드 | `--community-knowledge` | `EXPERT_COMMUNITY_KNOWLEDGE` | `OFF` |
| manifest 경로 | `--community-snapshot` | `EXPERT_COMMUNITY_SNAPSHOT` | 없음 |
| 사전 고정 manifest SHA-256 | `--community-snapshot-sha256` | `EXPERT_COMMUNITY_SNAPSHOT_SHA256` | 없음 |

우선순위는 CLI, 환경변수, 기본값 순이다. 실행 프로필은 이 기능을 자동으로 켜지 않는다. READ_ONLY에는 경로와 소문자 SHA-256을 함께 지정해야 한다. 로딩 실패는 다른 corpus로 대체하지 않고 UNAVAILABLE로 남긴다.

READ_ONLY에서는 유효 `PIPELINE_SLANG_DB=0`을 강제하고 BatchContextMemory 및 ordered publication learning을 끈다. 명시적으로 slang on을 함께 주더라도 READ_ONLY 조합 제약이 우선하며 시작 로그·유효 설정에 이를 표시한다. OFF 사용자의 기존 설정은 유지한다. 일반 실행의 VLM/OCR·대시보드 정책도 별도로 유지한다.

첫 READ_ONLY 버전은 `SOURCE_ONLY_V1` early route와 함께 사용할 수 없다. 모델 문맥이 달라진 실행에서 OFF의 판정을 복사하지 않도록 설정 단계에서 거절한다. 새 snapshot과 조회 정책은 판정 설정에 결속되며 단순히 영수증을 volatile 처리하는 것으로 이 차이를 숨기지 않는다.

## 저장과 조회 계약

[고정 저장 API 계약](../../out/development_plan_20261010/r3_store_api_KO.md)이 manifest, 세 JSONL, source inventory와 provenance의 정본이다. parser가 지원하는 로컬 정규화 문장은 제한적이다. parser의 MATCHED를 사람이 검토한 작품 별칭으로 승격하지 않는다. 수작업 분류는 원문 observation과 별도의 검토 영수증을 연결한다.

- snapshot은 외부에서 고정한 manifest SHA, 각 파일·payload·근거 SHA와 UTF-8 span을 확인한다. 총 고유 파일 4MiB, 후보 행 1,000개 상한을 둔다.
- 원문 fragment를 이어붙여 가짜 surface를 만들지 않는다. OCR, 모델이 만든 제목, 참조 정답은 조회 입력에서 제외한다.
- community와 timezone이 있는 as-of가 명시돼야 시간·커뮤니티 적합성을 판정한다. 기본 `gallery_id=test`나 시간 미상은 wild-card로 처리하지 않는다.
- 서로 다른 sense를 유지하고 적격 경쟁 의미가 둘 이상이면 AMBIGUOUS로 남긴다. 동일 lineage mirror를 독립 지지로 세지 않는다.
- query는 12,000자·128 fragments·100,000 비교, 32 occurrences·16 senses, 영수증 48KiB 상한을 갖는다. 상한 초과를 성공처럼 조용히 잘라 저장하지 않는다.

## 실제 소비와 화면

Pipeline은 post마다 한 번 query하고 후보 전용 context를 Orchestrator와 Decoder로 전달한다. 기존 `resolved_slang`, 검색 근거, curated registry에 직접 병합하지 않는다. Decoder 문맥 구간은 8KiB 상한이며 후보 정의가 지시문·공식 제목 증거로 승격되지 않게 한다. 근거 없는 Decoder best_match·High/verified/locked를 낮추고 후단 typed publication 계약을 HOLD로 봉인한다. 원문 완전 제목·공식 상세 검색 row의 독립 근거가 있으면 기존 공개 gate를 유지한다. 한국어 조사가 붙은 완전 제목도 확인하며 긴 다른 제목의 부분문자열은 허용하지 않는다.

행별 `run_meta.community_knowledge_readback`은 snapshot/query/config 지문, 원문 위치, 후보·출처, 실제 소비 상태와 run/input_index/post/attempt/publication_scope를 저장한다. 저장 영수증 상한은 64KiB다. 이전 실행 영수증을 현재 early route의 소비 기록으로 복사하지 않는다.

대시보드 live·history 상세는 같은 표시 함수를 사용한다. 조회 상태와 `QUERY_ONLY`, `PROMPT_SECTION_INCLUDED`, 미소비 사유를 구분하고 snapshot/query SHA·후보·출처·행 결속을 보여준다. prompt 포함은 모델이 의미를 올바르게 골랐다는 증거가 아니다. 후보 없음은 NIL 판정이 아니다.

## 검증과 남은 조건

현재 상태: **FUNCTIONAL_VERIFIED_ACTUAL_DATA_PENDING**. Python 37개 파일의 시험 726개와 하위 시험 132개, 화면 표시 시험 24개가 통과했다. 테스트 중 소스 변경과 외부 연결 시도는 0회이며 실제 모델 호출은 0회이다. 실제 CPython 프로세스(PID 44372)의 priority 16384와 affinity 2를 확인했고, 숫자 연산 라이브러리용 스레드 설정 5개가 모두 1이었다.

| 검증 | 결과·근거 |
|---|---|
| 저장소·로컬 변환 | 저장소48개, builder15개. 원문 span/SHA·경로·권리/시간 미상·경쟁 sense·세 namespace·신규 출력·원본 보존을 확인했다. 전체 통합 수치에 포함된다. |
| 실제 소비 | pipeline25개. 실제 builder→store→process→Orchestrator→Decoder prompt→root 저장을 fake LLM/MCP로 확인했다. 후보만의 공개 차단, OFF, 오류, fast path, 크기 한도, 워커별 분리도 포함한다. |
| 최종 통합 | [Python 37개 파일의 시험 726개와 하위 시험 132개, 화면 표시 시험 24개 PASS](../../out/development_plan_20261010/r3_validation_receipt.json), [97.84초의 시험 로그](../../out/development_plan_20261010/r3_validation_tests.log). 최초 자산 버전 기대값 불일치 기록은 별도 보존했다. |
| 독립 검토 | [runtime21개 검사](../../out/development_plan_20261010/r3_runtime_independent_final_review_KO.md), [pipeline5개 기능 묶음](../../out/development_plan_20261010/r3_pipeline_independent_final_review_KO.md) PASS. 오류 영수증 지문 누락·한국어 조사 경계·조회 오류 소비 상태를 수리했다. |
| 실제 화면 | [브라우저 수령증](../../out/development_plan_20261010/r3_browser_receipt.json) PASS. live/history 같은 snapshot·행 결속, 경쟁 sense·출처·유효기간·분류 표시, 콘솔0. 합성 fixture는 QUERY_ONLY이며 Decoder 소비를 허위로 기록하지 않았다. |

시험 묶음은 서로 겹치므로 합산하지 않는다. pytest가 기존 Windows Temp의 garbage 디렉터리를 정리하지 못한 경고 1개는 남았지만 시험 실패·오류·건너뜀은 없다. 브라우저에서 새 기능이 예전 자산 캐시에 가려지지 않도록 `presentation.js`의 버전도 갱신했다.

[적용·보존 수령증](../../out/development_plan_20261010/r3_preservation_receipt.json)과 [최종 전달 수령증](../../out/development_plan_20261010/R3_DELIVERY_RECEIPT.json)에 원본 worktree 선택 67개·primary 연구 6개·기존 32건 결과·중앙 Slang DB·수정 전 백업·HEAD와 staged 내용을 대조했다. Git index 원시 바이트와 staged 내용은 구분하며 stage/reset/commit은 하지 않았다. 신규 tests는 기존 ignore 규칙 대상이므로 추후 커밋 시 포함 여부를 별도로 확인해야 한다.

실제 source-backed corpus와 참조 sense·작품 ID 대응은 아직 확인하지 못했다. 기존80 입력을 지식 corpus로 재사용하지 않는다. 실제 지식 품질과 회수 성능, 새80의 최종 코드 실측·의미 검토, formal KPI는 미완료다. [개발 계획](EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md), [TODO](TODO.md), [CHECKLIST](CHECKLIST.md), [현재 개발 상태](../../out/development_plan_20261010/DEVELOPMENT_STATUS.json)를 함께 갱신한다.


다음 R4는 [구현 준비 계약](../../out/development_plan_20261010/r4_implementation_contract_KO.md)에 구형 하네스 지문 경로, TRAIN/DEV/CAL/FROZEN 분리와 실제 데이터·모델 선행 조건을 정리했다. 조사 완료이며 R4 구현·학습·실측 완료가 아니다.
