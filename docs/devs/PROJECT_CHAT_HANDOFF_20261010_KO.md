# 웹소설 매칭 프로젝트 최근 채팅 통합 인계

후속 확인: [대시보드 표시와 expert_main 적용 점검](DASHBOARD_EXPERT_MAIN_COVERAGE_AUDIT_20261010_KO.md). 최신 코드의 실제 호출은 확인했지만 기본 폴더 미통합, notes 독립 표시·중첩 실행 이력·R08 표시 누락이 남아 있다.

집계일은 2026년 10월 10일 KST다. 9월 14일부터 10월 8일까지 이어진 주요 채팅 11개와 두 작업 폴더의 문서·수령증을 대조했다. **원래 작품 매칭·커뮤니티 문맥 개선 Goal의 G1~G7은 10월 8일 완료됐다. 최신 구현과 실행 증거는 `233b` worktree에 있으며, 현재 기본 프로젝트 폴더에는 통합되지 않았다.**

완료 범위는 구현·실행·독립 검토에 합의된 원래 조건이다. 정식 KPI는 `NOT_ESTIMABLE`이고, 마지막 B14 수정 이후 최신 코드의 새 전체 80건 원격 실행은 없다. 후속 32건은 원형 80건의 부분집합이므로 고유 표본을 112건으로 세지 않는다.

## 이어서 작업할 위치와 읽는 순서

| 구분 | 경로와 상태 | 인계 시 주의점 |
|---|---|---|
| 현재 기본 폴더 | `C:/Users/kimjang/Documents/GitHub/llm_novel_dc_coommunity_parser` | 연구 기록은 주로 9월 15일, 대시보드 변경은 9월 22일 상태다. 이 인계 문서와 진입 안내만 최신으로 연결했다. |
| 최신 구현 폴더 | `C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser` | 10월 8일 코드·테스트·실측·완료 근거가 있다. detached HEAD이며 많은 staged·unstaged·untracked 자료를 보존해야 한다. |
| 공통 커밋 | `007c9d40a62dbd24b062cd317fa780c8d743ba24` | 커밋이 같아도 실제 파일은 다르다. 기본 폴더의 브랜치는 `codex/grounding-community-handoff-20260901`이다. |

`goal.md`, `expert_main.py`, `agentic_pipeline.py`, 연구 runner, 대시보드와 주요 개발 문서는 두 폴더에서 다르다. 최신 문맥 계약 `context_projection_contract.py`, `claim_scope_contract.py`와 연구 로드맵은 `233b`에만 있다. 단순 checkout·merge만으로 미커밋 작업이 옮겨졌다고 판단하면 안 된다. 이번 집계는 코드 복사·병합·커밋을 하지 않았다.

다음 순서로 읽으면 과거의 미완료 기록을 현재 상태로 오인하지 않는다.

1. [최종 완료 보고서](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_goal_completion_orchestration_20261006/FINAL_COMPLETION_REPORT_KO.md): 결과와 검증 한계.
2. [최신 goal 상단](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/goal.md)과 [최종 상태 기록](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_goal_completion_orchestration_20261006/STATE.json): 완료 범위와 시점.
3. [현재 단계](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_goal_completion_orchestration_20261006/CURRENT_STEPS_KO.md)와 [검증 결과 상단](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/docs/devs/VERIFICATION_RESULTS.md).
4. [R25 의미 수리](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/docs/devs/R25_SAME80_SEMANTIC_REPAIR_KO.md) → [후속 32건 기술 판독](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_r25_fresh32_postrun_20261008/REPORT_KO.md) → [마지막 B14 수리](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_r26_b14_actor_repair_20261008/REPORT_KO.md).

## 채팅별 역할과 최종 인계 결론

날짜는 메시지·실행 근거의 시점이다. 앱 목록의 최근 갱신 시각만으로 작업 시점을 정하지 않았다. 긴 제목은 앱이 반환한 제목 그대로 표기했다.

| 채팅 | 담당과 읽은 시기 | 현재 인계에 반영할 결론 |
|---|---|---|
| [점검 중인 로드맵 진행도](thread://01a0e161-6dd5-79a2-b383-0ef5b358a6d3?hostId=local) | 10월 2~8일 총괄·독립 검토·최종 접수 | 가장 최신의 완료 판단. 10월 8일 G1~G7 충족 후 앱 Goal `complete` 적용 기록이 있다. |
| [웹소설 매칭 연구 로드맵 인계](thread://01a0d184-858b-7070-8c56-0983d813f5f8?hostId=local) | 10월 7~8일 구현·실측·국소 수리·문서 | R25 실제80, 후속32, A58/B69/B14 등의 수리를 수행했다. 최종 응답의 앱 상태 동기화 대기는 이후 총괄 완료 기록으로 해소됐다. |
| [Claude Opus 5.5 웹소설 코드 구현·검토](thread://01a0eadb-4558-7850-8ea9-b6d68f0274c4?hostId=local) | 10월 7~8일 독립 코드·원문 검토 | 중간 결함 후보를 총괄이 원문 재판정했다. 최종 B14 변경 범위의 새 P1/P2는 0건이다. |
| [웹소설 매칭 로드맵 완료 여부 점검](thread://01a0f65a-d701-7080-8b69-770bb28d08fa?hostId=local) | 10월 1~2일 이전 총괄 | source32·Image72와 당시 잔여 수리의 역사다. 중단된 turn의 미완료 상태는 10월 8일 결과보다 우선하지 않는다. |
| [웹소설 매칭 · 연구 로드맵 구현·실측 Goal](thread://01a07316-031e-7d70-9f4a-2724e18998b1?hostId=local) | 9월 15일~10월 2일 원래 Goal·R05/R08 감사 | 원래 채팅의 paused Goal과 이후 총괄의 완료 Goal은 별개다. 오래된 429·한도·연결 거부를 현재 blocker로 재사용하지 않는다. |
| [Update expert_main 대시보드 UI](thread://01a0c708-eb45-7320-a810-dd305efc6cae?hostId=local) | 9월 22일 UI 작업 | 판정 사유 카드, 단계별 로그·JSON·필터·원문 보기, 한국어 표현 정리 완료. 테스트48개와 실제 화면 검증 기록이 있다. |
| [Define GPT Astra orchestration role](thread://01a0bea5-8c85-7302-9f72-fd2a6bc2c9af?hostId=local) | 9월 20일 역할 분담 | 당시 Astra 총괄·5.6 Sol 구현 방침이다. 이후 모델 인계와 최종 총괄 체계를 덮어쓰지 않는다. |
| [Explain search alias reject](thread://01a0bdd3-86d7-7d31-9f40-a3638d6d1a7c?hostId=local) | 9월 별칭 검색 설명 | `search_alias_relation_rejected`는 특정 약칭과 검색 제목의 연결 배제다. 게시글 전체 비작품 판정이나 새 모델 호출을 뜻하지 않는다. |
| [너는 이 저장소 작업을 재개하기 위한 오케스트레이션 헤드다. 모델은 ChatGPT Latest → Pro를…](thread://01a0a009-529f-7cf2-b040-7e6779ab778e?hostId=local) | 9월 15일 연구 workflow·회수 진단 | configured remote vLLM 실행과 진단 manifest를 보존했다. `challenge-001`은 정답 후보가 BM25 top-5 밖인 회수 실패다. |
| [@웹소설 매칭 · 연구 로드맵 구현·실측 Goal astra의 사용량을 다써서 $multi-gpt 와 lu…](thread://01a09fc8-60a9-7a01-b43c-3c03643533d9?hostId=local) | 9월 14일 후보 진단·인계 | 회수·선택·NIL/ABSTAIN 분리, baseline16/challenge4 진단의 앞선 단계다. 당시 weights 부재의 `UNAVAILABLE`을 이후 전체 상태로 일반화하지 않는다. |
| [@@웹소설 매칭 · 연구 로드맵 구현·실측 Goal astra의 사용량을 다써서 $multi-gpt 와 l…](thread://01a0a2ee-fd16-7fc0-8b36-65e9f71cd6c3?hostId=local) | 9월 15일 새 인계 시도 | 마지막 두 turn은 interrupted/failed이며 별도 완료 산출 근거가 없다. 후속 채팅의 작업과 중복 집계하지 않는다. |

이번 집계는 주요 채팅의 최근·관련 turn과 연결된 산출물을 읽은 범위다. 모든 과거 채팅·하위 에이전트 로그의 전수 감사는 아니다. 목록의 최근 50개 밖에 있던 프로젝트 채팅은 로컬 메타데이터를 읽기 전용으로 찾아 `read_thread`로 내용을 확인했다.

## 구현된 개선과 실제 검증

작품명 추출뿐 아니라 **누가 무엇을 말했는지**를 보존하는 문맥 처리가 추가·수리됐다. 작가와 작품, 댓글 작성자와 댓글 속 제3자, 질문·반문과 단정, 조건·부정·전언, 요구와 현재 평가를 구별한다. 원문 설명의 근거와 공식 제목·URL 공개 권한을 분리하고, OCR 오독의 진단 검색이 공식 근거로 소비되는 경계를 좁혔다.

| 작업 | 실제 바뀐 점 | 검증과 한계 |
|---|---|---|
| A58 관련성 | 실제 별명 근거가 후단에 도착했는데 관련성이 누락되던 경계 수리 | 후속32에서 관련성 회복을 확인했다. 공식 제목·URL을 무조건 공개하는 규칙은 아니다. |
| B69 문맥 | 작품명 안의 `미친마법사`를 별도 놀라움으로 바꾸는 오독 수리 | 인접 시험과 후속32의 독립 검토에서 접수했다. |
| 원형4·6·19·21·32·46·57 | 대상·관계·발화 역할 손실 수리 | Claude31건 주장의 원문 재판정으로 확정한7건이며 최종 접수에서 닫혔다. |
| B9와 품질 질문 | 당위를 현재 불만으로, 질문을 단정 평가로 만드는 경계 수리 | 최종 핀 기준 독립 변경부 검토에서 새 P1/P2 0건이다. |
| B14 최종 수리 | 말줄임표로 끝난 구절의 명시적 제3자 주어를 놓쳐 댓글 화자의 취향으로 합성하던 오류 수정 | 저장 전문가 문맥32행 재생에서 B14 `notes` 한 필드만 변경했다. 새 모델 실행은 아니다. |

주요 구현은 최신 worktree의 [문맥 계약](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/grounding/context_projection_contract.py), [발화 구조](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/grounding/source_speech_structure.py), [파이프라인](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/src/llm_batch/agentic_pipeline.py)에 있다. 최종 회귀는 [B14 행위자 시험](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/tests/test_r26_b14_third_person_comment_actor.py)에서 시작할 수 있다.

| 증거 묶음 | 기록된 결과 | 해석 범위 |
|---|---|---|
| R25 실제 실행 | 글80·댓글193, 저장80/80, 실패·대기0, 호출646 | 마지막 B14 이전의 전체 실행이다. |
| 후속32 실제 실행 | 글32·댓글95, 저장32/32, 실패·대기0, 보호279개 불일치0 | 원형80의 부분집합을 별도로 실행했다. |
| 후속32 호출 장부 | TEXT298＋VLM12＝310, 종료·성공·provider usage310, seal/link32 | 관측 토큰4,328,129. 비용 절감·정확도 개선의 정식 비교 KPI가 아니다. |
| B14 최종 시험 | 국소·인접57, 주변73＋subtest3, 원래 회귀5 각각 통과 | 서로 다른 묶음과 과거 시험 숫자를 합산하지 않는다. |
| B14 저장 문맥 재생 | 32행·공개128필드 중 notes1필드 변화, 권한 필드32행 동일 | 전체 sidecar·본문 제3자·다른 consumer·새 원격 전체 실행을 증명하지 않는다. |
| 최종 독립 변경부 검토 | GPT·Claude 새 P1/P2 0, 확정 핵심 잔여0 | 검토된 범위의 결론이다. 모든 미래 입력의 무결함을 뜻하지 않는다. |

9월 연구 runner의 별도 기준선은 [후보 회수·선택 진단](RESEARCH_CANDIDATE_SELECTION_DIAGNOSTICS_20260914_KO.md)과 [9월15일 workflow manifest](../../out/research/research_workflow_20260915_diagnostics_manifest_vllm_v2/workflow_manifest.json)에 있다. baseline16·challenge4와 10월 원형80은 다른 분모다. challenge의 local_llm은 회수 실패·후보 선택 실패·NIL 오분류·모호함의 비보류가 각1건이었고 Recall@5는2/3, 후보 포함 후 조건부 선택은0/1이었다. 이 진단을 10월 실제80 정확도로 옮기지 않는다.

대시보드 작업은 [운영 문서](EXPERT_DASHBOARD_DESIGN_KO.md)에 정리돼 있다. UI PASS는 의미 품질·전체 스캔 승인과 별개이며, 과거 localhost 주소가 지금도 실행 중이라는 뜻은 아니다.

## 완료 판단과 상충 기록 정리

| 항목 | 인계 판정 |
|---|---|
| 원래 G1~G7 | 완료. G1 회귀, G2 WORK2, G3 NIL6, G4 U8, G5 OCR 오독 전파 경계, G6 호출 장부, G7 종료·보존·독립 검토·문서를 접수했다. |
| WORK2 | 원형3은 근거 있는 공식쌍 `233173` 공개로 최소1 조건 충족, 원형14는 정당한 HOLD다. |
| NIL6·U8 | NIL6의 잘못된 공식 공개0, U8 전행 검토 완료. U8을 새 Gold로 바꾸지 않았다. |
| 앱 Goal | 총괄 채팅에서 10월8일08:00:39 KST 완료 기록. 이번 집계는 해당 채팅의 live Goal을 변경하거나 새 Goal을 만들지 않았다. |
| 정식 KPI | `NOT_ESTIMABLE`. 측정 pair 미결속으로 formal KPI GO는 false다. 원래 구현 Goal 완료와 구분한다. |
| production·full scan·P0 authority | 새 승인을 발급한 근거가 없다. 9월 P0 감사 트랙은 `DEFERRED_P0_AUDIT_TRACK`이며 연구를 다시 막는 조건으로 쓰지 않는다. |

G5는 과거 R05의 실제 오독 질의 전파와 현재 소비 차단을 대조해 접수했다. 새 실런에서는 해당 오독 분기가 드러나지 않았으므로 모든 OCR 오독의 전체 실행 효과를 입증했다고 확대하지 않는다.

[최종 코드·의미 수령증](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_goal_completion_orchestration_20261006/ROOT_R26_FINAL_CODE_AND_MEANING_ACCEPTANCE.json)과 [G1~G7·문서 수령증](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_goal_completion_orchestration_20261006/FINAL_G1_G7_AND_DOCS_ACCEPTANCE.json)의 `Goal_complete=false`는 앱 완료 처리 직전 상태다. 이후 `STATE.json`의 `goal_status=complete`, 저장된 완료 도구 결과와 최종 보고서가 이를 잇는다.

Claude의 중간 “P2 31행”은 [최종 재판정](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_goal_completion_orchestration_20261006/ROOT_R25_CLAUDE31_FINAL_ADJUDICATION.json)에서 확정7·표현 취향21·반증2·미확정1로 나뉘었고 확정7은 수리됐다. 후속32의 S20·S21 후보도 [원문 재판정](C:/Users/kimjang/.codex/worktrees/233b/llm_novel_dc_coommunity_parser/out/sol_goal_completion_orchestration_20261006/r26_Claude_A_candidates_adjudication_20261008/REPORT_KO.md)에서 새 확정 P2로 채택되지 않았다. 잘린 notes를 읽어 생긴 empty 주장, JSON 직렬화 공백 차이의 해시 불일치도 정정된 이력이다.

원래 Goal의 paused, 10월2일 Image72 의미 NO_GO, 9월 `UNAVAILABLE`, 과거 429·사용량·연결 장애는 각각 당시 상태다. 이후 실행·수리·접수를 건너뛰고 현 blocker로 삼지 않는다. 10월5일 사용자는 PC 멈춤 해소를 확인했으며 이후 실행은 저부하 조건을 유지했다.

## 후속 작업 순서와 운영 조건

1. **최신 미커밋 작업을 보존한 상태에서 통합 계획을 잡는다.** `233b`의 코드·시험·docs·필요한 `out` 증거와 primary의 별도 변경을 비교한다. staged 항목 전체를 무조건 커밋하거나 untracked/ignored 증거를 삭제하지 않는다. 완료 수령증과 원본 결과는 고치지 않는다.
2. **다음 품질 개선은 남은 한계 하나를 선택한다.** 설명의 일반성·전사 의존·조사/분류 경계, 댓글 NSFW 회수, 제3자 발화의 추가 종결형, 픽셀과 sidecar 미확인 범위가 후보다. 현재 미재현 P3/U를 확정 결함으로 적지 않는다. R07 지속 지식 체계도 별도 후속 범위다.
3. **추가 실측이 필요한 목적을 먼저 고정한다.** 최종 소스 전체80 효과 확인과 정식 KPI용 측정 pair 설계는 가능한 후속 작업이지만 완료한 기존 Goal의 새 필수조건으로 소급하지 않는다. 새 입력의 의미 정답·공식 근거·terminal 분모를 구분한다.

같은 검증 흐름을 잇는 경우 최근 적용 조건은 요청/실효 `1/1`, BelowNormal, numeric threads1, 실제 CPython 자식의 CPU affinity1bit, 대시보드 ON, 원격 Gemma·VLM·OCR ON, 압축 OFF다. 이는 PC 부하를 줄이기 위해 적용한 사용자 예외다. 저장소 일반 기본은 `--parallel 16`이지만 과거 명령을 복사해 이 예외를 지우지 않는다. 기본16을 적용하는 다른 런은 requested/effective 병렬도를 모두 확인한다.

런을 새로 시작할 때는 해당 코드·입력·설정을 고정하고, 자연 종료 증명과 보호 파일 대조를 먼저 확인한 뒤 결과를 판독한다. 단위시험 통과, 저장 완료, 의미 검토, formal KPI, production 승인을 각각 구분한다. `아생갤`과 `갤러리` 표면은 실제 작품 약어·작품 내 커뮤니티 장치일 수 있으므로 현실 갤러리명으로 단정하지 않는다.

## 이번 인계 정리의 확인 범위

- [x] 주요 채팅11개의 역할·최신 결론·역사 상태를 모았다.
- [x] primary와 `233b`의 위치·HEAD·실제 파일 차이를 확인했다.
- [x] 최종 수령증의 현재 소스3개, 문서·선택 시험12개, Claude 최종 검토3개를 실제 SHA-256과 대조했다. 불일치0이다.
- [x] 기본 폴더의 README·goal 안내·개발 허브·TODO·CHECKLIST를 이 문서에 연결했다.
- [x] 최신 worktree의 뒤처진 README·개발/연구 허브·로드맵·현재 관문 상단을 완료 범위와 맞췄다. 최종 수령증에 묶인 문서·선택 시험12개와 수령증은 보존했다.
- [x] 인계 문서의 로컬 링크20개(후속 적용 점검 포함)와 최신 worktree의 인계 링크5개가 모두 존재하며, 변경 문서의 공백 오류 검사를 통과했다.
- [ ] 미커밋 코드와 증거의 별도 보존·통합 작업은 후속으로 남긴다.
- [ ] 새 품질 개선이나 정식 KPI 실험은 목표와 분모를 정한 뒤 별도 작업으로 진행한다.

이번에는 문서와 저장된 근거를 대조했다. 새 모델 호출·테스트런·전체 스캔은 실행하지 않았고 다른 채팅의 재개·메시지 발신·Goal·자동화 상태 변경도 하지 않았다. 위 시험과 실측 숫자는 기존 실행의 기록이다.
