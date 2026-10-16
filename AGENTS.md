# Repository Agent Instructions

- 2026-10-16 사용자 지시에 따라 이후 일반 개발·수정은 기본 프로젝트의 `main` 브랜치에서 직접 진행한다. 별도 작업 브랜치는 사용자가 명시적으로 요청한 경우에 만든다. 기존 detached worktree와 실행 원본 증거는 브랜치 정리와 구분해 보존한다.
- 2026-10-16 사용자 지시에 따라 Git에 공개하는 README는 프로젝트 소개·기능·설치·실행·입출력·설정과 사용자용 기술 문서 안내에 집중한다. 현재 작업 상태, Goal, 최근 시험 수치, 작업일지, 인계·정리 기록과 그 링크를 README에 올리지 않는다. 일회성 작업 기록과 README 보존본은 로컬 산출물로 관리하고 명시 요청 없이 Git에 추가하지 않는다.
- 진행 시 docs와 checklist가 존재하면 계속 확인, 수정, 리뷰, 검토하며 진행한다.
- 기능 변경, 추가, 개선 시 관련 docs를 함께 갱신한다.
- 모든 신규/갱신 보고서, 루프 보고서, review Markdown, Data Analytics reader-facing 산출물은 한국어로 작성한다. 간략하게 쓰되 의미, 근거, 산출물 경로, 게이트 상태를 생략하지 않는다. 영어 enum, 명령어, 파일 경로, URL은 필요한 경우 원문 그대로 둔다.
- 2026-10-12 사용자 지시에 따라 이후 expert_main 및 regression-safe grounding 계열 테스트런/검증런은 명시적 반대 지시가 없으면 요청 병렬도 `--parallel 12`를 기본으로 사용한다. 입력 수가 12보다 작으면 `effective_parallel=min(input_count,12)`로 축소될 수 있으므로 manifest의 requested/effective parallel을 함께 확인한다.
- 진행상황을 쉽게 볼 수 있도록 테스트런/검증런에는 웹 대시보드를 붙인다. 새 런은 `--no-dashboard`를 사용하지 말고, 필요하면 먼저 `tools/dashboard_server.py` standalone 서버를 띄운 뒤 expert_main이 포워딩하게 한다. `tools/run_independent_plan.py` 경유 planned run은 manifest attach fallback을 자동으로 붙인다. 이미 `--no-dashboard`로 시작한 런은 `tools/attach_manifest_dashboard.py --manifest <manifest>`로 manifest 기반 진행률을 사후 부착한다.
- 도메인 규칙: `아생갤`은 `아카데미 생존 갤러리`처럼 실제 웹소설 작품 약어일 수 있고, `갤러리` 표면은 현실 DC 갤러리명으로만 단정하지 않는다. 요즘 웹소설은 작품 안에서 갤러리/댓글식 커뮤니티를 서사 장치로 엮거나 오마주 컨셉으로 차용할 수 있고, 이 표면이 작품 제목 또는 약어일 수 있으므로 explicit alias relation, specific-work target, 공식/커뮤니티 근거, 경쟁 본문 작품 근거를 함께 확인한다.
