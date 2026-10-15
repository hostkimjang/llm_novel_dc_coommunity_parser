# 대시보드 표시와 expert_main 개선 적용 점검

후속 개발은 [expert_main 통합과 대시보드 개발 계획](EXPERT_DASHBOARD_DEVELOPMENT_PLAN_20261010_KO.md)을 따른다. P0~P3 반영과 화면 검증 결과는 [현재 구현 기록](EXPERT_DASHBOARD_IMPLEMENTATION_20261010_KO.md)에 있다. 아래 내용은 수정 전 점검 기록이다.

2026년 10월 10일 확인 결과, **최신 worktree의 주요 문맥 개선은 `expert_main.py`에서 최종 저장까지 연결돼 있다. 그러나 기본 프로젝트 폴더에는 통합되지 않았고, 대시보드도 개선된 정보를 전부 표시하지 않는다.** 원래 G1~G7 완료는 맞지만 연구 로드맵 전체 기능의 운영 적용 완료를 뜻하지 않는다.

기본 폴더는 `C:/Users/kimjang/Documents/GitHub/llm_novel_dc_coommunity_parser`, 최신 구현은 `C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser`다. 이 점검에서는 코드와 원본 결과를 수정하지 않았다. 문서·API·실제 화면·기존 시험을 대조했다.

## 대시보드에서 확인한 표시와 누락

점검 시작 시 `dashboard_server.py`와 `expert_main.py` 프로세스, 일반 대시보드 포트 8080·8081·8765·18765의 listener는 없었다. 최신 소스로 임시 loopback 서버를 띄우고, 후속32의 저장 결과를 메모리에 연결해 실제 브라우저에서 확인한 뒤 서버와 탭을 종료했다. 새 모델 실행은 없었다.

| 항목 | 판정 | 확인 내용 |
|---|---|---|
| 판정 사유·주요 화제 | 표시됨 | 원문에 근거한 설명, 발화 해석, 작성자·댓글 귀속, `primary_subject_text`가 상세창에 나타난다. |
| 후보·검색·이미지/OCR·공개 보류 | 표시됨 | 후보와 비교작, 검색 상태·근거, 이미지/OCR 근거, 제목 확정·출력 점검 JSON이 있다. 일부 내부 키는 영문 그대로다. |
| **분석 메모 `analysis.notes`** | **독립 표시 누락** | `reason` → `reason_lines` → `notes` 중 하나만 고른다. 실제 후속32는 32/32행에 reason과 notes가 함께 있어 notes가 별도 구역으로 보이지 않는다. API와 JSON 복사에는 있다. |
| 발화 사건·문맥 graph 상세 | 전용 화면 없음 | 최종 설명과 일부 후보 JSON으로 간접 확인한다. producer의 전체 구조를 따로 보여주는 화면은 없다. |
| **R08 호출·저장 연결·정식 KPI** | **표시·전달 일부 누락** | live 상세 API가 `run_meta`를 전달하지 않고 전용 화면도 없다. 상단 토큰 카드는 이벤트 합계이며 R08의 봉인·연결·provider 사용량 검증이나 formal KPI와 다르다. |
| **10월 최신 실행 이력** | **자동 노출 안 됨** | `/api/runs`가 `out` 최상위의 `expert_result_*.json`만 찾는다. 중첩된 `out/sol_r25_fresh32_actual_20261008/run/result.json`은 누락되며 실제 이력 화면은 9월22일 결과5개만 보였다. |
| 현재 런의 중첩 결과 | 연결 가능 | 명시적 `output_file`을 받으면 같은 런에 한정해 중첩 결과를 읽는다. 임시 표시 점검에서는 32행 모두 조회됐다. |
| NSFW false | 별도 표시 없음 | true일 때만 분석 상세에 나타난다. false와 미제공을 화면에서 명확히 구분하지 않는다. |

핵심 근거는 [상세 표시 선택 로직](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/monitor/static/index.html:2370), [주요 화제와 진단 표시](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/monitor/static/presentation.js:92), [live 상세 API](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/monitor/server.py:672), [이력 파일 탐색](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/monitor/server.py:347)이다.

실제 B14 게시글 `11718097`의 API에는 reason854자·notes835자·primary subject49자가 있었다. 화면에서는 판정 사유와 주요 화제를 확인했지만 별도 분석 메모 구역은 없었다. 제공된 HTML·presentation.js는 최신 worktree 파일과 일치했고 브라우저 경고·오류는 없었다. 따라서 오래된 브라우저 캐시만의 문제가 아니다.

**수정된 코드와 과거 저장 결과도 구분해야 한다.** B14의 마지막 수리는 원본 실제32 실행 뒤에 이루어졌다. 보존된 원본 notes에는 잘못된 댓글 화자 긍정 문장이 남아 있고, 수정 효과는 별도 저장 문맥 재생32에서 검증했다. 대시보드 새로고침이나 서버 재기동이 과거 결과를 다시 분석하지 않는다.

## expert_main에서 실제 적용되는 범위

| 항목 | 최신 worktree의 연결 | 제한 |
|---|---|---|
| 진입과 저장 | `AgenticPipeline` 생성 → `process_post` → 최종 source context 소비 → publication commit → 결과 JSON 저장 | 기본 폴더는 별도 코드다. 실행할 `expert_main.py`의 절대 경로가 중요하다. |
| A58 별칭과 관련성 | 후단 독립 별칭 근거를 재검사해 관련성을 복구 | 후속32의 post9218178에서 relevant=true, 제목 확정 허용=false를 확인했다. |
| B7 문맥·대상·관계 | typed projection → 설명 생성·검증 → reason·reason_lines·primary subject·notes 반영 | 설명이 공식 제목·URL 공개 권한을 자동으로 부여하지 않는다. |
| B69 놀라움·B9 당위와 질문 | 작품명 내부 표현과 독립 감정을 구별하고 요구·질문을 현재 평가로 바꾸는 경계를 차단 | 추가 표현·종결형 전체를 검증한 것은 아니다. |
| B14 제3자 행위자 | 명시 주어 해석과 댓글 화자 반응 합성 차단이 최종 설명 경로에 연결 | 최종 수리 후 새 전체80 원격 실런은 없다. |
| OCR 진단과 공식 근거 | 진단용 검색·OCR 표식을 공식 제목과 URL 공개 권한에서 분리 | 기본 VLM은 OFF다. 검증런은 VLM/OCR ON으로 실행했다. |
| R08 호출 장부 | 활성화하면 호출 dispatch/terminal·행 attempt·publication link 기록 | 기본 ledger는 OFF다. 검증런은 SHADOW였고 formal KPI는 여전히 `NOT_ESTIMABLE`이다. |

[진입점의 source 선택](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/expert_main.py:34), [실제 pipeline 호출](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/expert_main.py:13535), [최종 설명 생성·검증](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/agentic_pipeline.py:72762), [네 필드 저장 반영](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/agentic_pipeline.py:72868)을 확인했다.

기본 프로젝트 폴더에는 `context_projection_contract.py`, `source_context_explanation.py`, `source_speech_structure.py`가 없다. 따라서 **현재 기본 폴더에서 `python expert_main.py`를 실행하면 최신 문맥 개선판과 동일하게 동작한다고 볼 수 없다.** 같은 Git HEAD라는 사실도 이 차이를 해소하지 않는다.

옵션을 생략한 실행도 검증런과 다르다. [설정 코드](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/expert_main.py:11355)는 환경변수·CLI 재정의가 없을 때 VLM=0, OCR=1이며, [호출 장부 설정](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/expert_main.py:334)은 OFF다. CLI parallel 기본1과 저장소 일반 검증 권장16도 구분해야 한다. 최근 저부하 실측의 parallel1·BelowNormal·단일 코어·압축OFF 예외와 대시보드 ON 조건은 그대로 보존한다.

## 완료 Goal 밖에 남은 연구 기능

[연구 로드맵](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/docs/research/IMPROVEMENT_ROADMAP.md)의 아래 항목은 원래 G1~G7 완료와 별개다.

- R02: BM25는 연구 runner 전용이다. 실제 pipeline 회수 경로와 dense/RRF·확대 corpus 통합은 별도다.
- R03·R04: 연구 lexical reranker는 실제 선택기에 연결되지 않았으며 학습 reranker·운영 NIL/calibration 전체 완료 근거가 없다.
- R07: 게시글별 문맥 처리는 연결됐지만 지속 `community_lexicon` 수집→저장→소비, 신규 mining·중앙 DB 승격은 완료되지 않았다.
- R08: 선택적 계산 router는 `REVIEW_ONLY`, recovery는 `PLAN_ONLY`다. 정식 비교 pair와 비용·품질 KPI는 미완료다.
- R09: 외부 authority와 production/full-scan 전환은 보류 감사 트랙이다.

## 이번 검증과 다음 수정 순서

| 검증 | 결과 |
|---|---|
| 기존 dashboard standalone 시험 | 37/37 PASS |
| 기존 presentation JavaScript 시험 | 12/12 PASS |
| B14·최종 설명·reader state·CLI import·현재 런 결속 5개 파일 | 46 PASS＋12 subtests PASS, 10.73초 |
| 실제 HTTP·브라우저 | 저장32행 연결, B14 상세와 이력 누락 재현, 최신 자산2개 일치, 브라우저 오류0 |
| 원본 result·manifest | 전후 SHA-256 불변 |

시험은 원격 모델 호출 없이 수행했다. 마지막 5개 파일 묶음은 BelowNormal·affinity mask2·numeric threads1로 실행했다. 기존 시험 PASS는 표시 누락이 없다는 뜻이 아니다. 현재 시험이 검증하는 계약을 통과한 것이며 위 누락은 실제 코드·데이터·화면으로 별도 확인했다.

검증 기록: [HTTP·원본 보존 수령증](../../out/dashboard_expert_audit_20261010/http_saved_result_receipt.json), [화면·자산·시험 수령증](../../out/dashboard_expert_audit_20261010/verification_receipt.json), [B14 API 상세](../../out/dashboard_expert_audit_20261010/b14_api_detail.json).

다음 구현은 **최신 코드의 기본 폴더 통합 계획 → reason과 notes의 독립 표시 → 중첩 manifest 기반 이력 조회 → R08 관측·미추정 상태 표시** 순서가 적절하다. 원본 분석 결과와 수리 재생 결과는 구분해 표시하고 과거 결과를 고쳐 새 실측처럼 만들지 않는다. 문맥 graph·NSFW 상태와 연구 백로그 확대는 그 다음 범위를 정해 진행한다.
