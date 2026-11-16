# Expert 대시보드 사용과 운영

`expert_main` 실행의 진행률, 전문가 단계, 처리 결과, 로그와 과거 실행 이력을 웹 화면에서 확인하는 방법을 설명한다. 대시보드 표시는 저장된 결과와 이벤트를 보여 줄 뿐이며, 분석 품질이나 전체 스캔 승인의 근거가 아니다.

## 실행 방식

대시보드는 두 방식으로 뜬다. 어느 쪽이든 기본 주소는 `http://127.0.0.1:8080`이다.

| 방식 | 시작 | 수명 | 포트 |
| --- | --- | --- | --- |
| 내장(embedded) | `expert_main`이 외부 서버를 찾지 못하면 스스로 띄운다. | 실행이 끝나면 함께 종료 | `DASHBOARD_PORT`(기본 8080). 사용 중이면 다음 빈 포트를 찾아 옮기고 시작 로그에 실제 주소를 남긴다. |
| standalone | `python tools/dashboard_server.py --port 8080`을 먼저 실행한다. | 실행이 끝나도 유지 | 지정 포트가 사용 중이면 바로 실패한다. |

실행이 끝난 뒤에도 화면과 이력을 계속 보려면 standalone 서버를 먼저 띄운다.

```powershell
python tools/dashboard_server.py --port 8080
python expert_main.py tests/inputs/sample.jsonl --parallel 12 --output out/example/result.json
```

`expert_main`은 시작할 때 `DASHBOARD_URL`(없으면 `http://127.0.0.1:<DASHBOARD_PORT>`)의 `/api/health`를 호출한다. 응답의 service 표식이 맞고 `standalone=true`이면 내장 서버를 띄우지 않고 forwarder로 이벤트를 `POST /api/ingest`에 전달한다. 다른 `expert_main`의 내장 대시보드는 `standalone=false`라서 전달 대상이 되지 않는다. 다음 실행이 시작되면 standalone 서버는 `batch_start` 이벤트로 실시간 상태를 새로 시작한다.

| 환경 변수 | 의미 |
| --- | --- |
| `DASHBOARD_PORT` | 내장 서버 포트이자 외부 서버 감지 기본 포트. standalone 서버의 `--port` 기본값도 이 값이다. |
| `DASHBOARD_URL` | 외부 서버 감지 주소. 다른 호스트나 포트의 standalone 서버를 쓸 때 지정한다. |
| `EXPERT_DASHBOARD_FORWARD` | `0`이면 외부 서버 감지를 끄고 항상 내장 서버를 쓴다. |
| `DASHBOARD_INGEST_TOKEN` | 설정하면 standalone 서버가 `/api/ingest`에 `X-Ingest-Token` 헤더를 요구한다. `expert_main`도 같은 값을 읽어 붙이므로 두 프로세스에 같은 값을 준다. |

standalone 서버를 `127.0.0.1` 밖(`--host 0.0.0.0`)에 열 때는 `DASHBOARD_INGEST_TOKEN`을 함께 쓴다. 토큰 없이 비루프백 주소에 바인드하면 서버가 경고를 출력한다.

테스트런·검증런에는 `--no-dashboard`를 쓰지 않는다. 이미 대시보드 없이 시작한 실행은 manifest로 진행률을 붙인다. 토큰을 설정한 서버라면 `--token`으로 같은 값을 넘긴다.

```powershell
python tools/attach_manifest_dashboard.py --manifest out/example/result_manifest.json
```

## 화면

왼쪽 메뉴에서 실시간 모니터, 과거 실행 이력, Slang DB를 고른다.

- **실시간 모니터:** 진행률, KPI, 파이프라인 단계, 병렬 worker, 처리 결과, 로그를 보여 준다. 새로고침하면 최근 전체 로그는 복구되지만 worker별 스트림 탭은 이후 들어온 이벤트부터 표시한다.
- **과거 실행 이력:** `out/` 아래 결과와 manifest를 골라 상세, 로그, 실행 설정, 종료 계측을 본다. 중첩 manifest 실행은 실행 키로 선택한다.
- **Slang DB:** 중앙 slang DB의 항목·요약을 페이지 단위로 본다. 파일이 없거나 읽을 수 없으면 빈 목록을 보여 준다. 서버는 `<저장소>/slang_db/slang_db.json`을 읽으며, `expert_main`의 `--slang-db-path`와 자동으로 연동하지 않는다.

상세 화면은 판정 결과, 판정 사유, 판정 범위·확정 상태, 후보 검토, 검색 상태, 근거 자료, 분석 메모 순으로 읽는다. 판정 사유는 구역별 카드로 나누고 `판정 사유 원문 보기`에서 저장된 문장을 그대로 보여 준다. 처리 로그는 입력, 이미지·OCR, 전문가 단계, 검색, 완료 결과로 묶고 종류 필터와 내용 검색을 함께 쓸 수 있다.

화이트·다크 테마는 상단 해·달 버튼으로 바꾼다. 선택하지 않았으면 OS의 `prefers-color-scheme`을 따르고, 선택값은 브라우저 `localStorage`의 `lndc_theme` 키에 저장해 같은 출처의 다른 탭과 동기화한다.

## 표시 규칙

- 저장하지 않은 값은 `미기록`으로 둔다. 새 코드의 해석으로 과거 결과의 빈 값을 채우지 않는다.
- NSFW는 true, false, 미기록, 형식 오류를 구분한다. 값이 `false`나 `0`이어도 숨기지 않는다.
- 결과와 sidecar manifest가 서로 연결되는지는 행 단위로 확인한다. `BOUND`는 저장 자료가 서로 맞는다는 뜻이고 품질 승인이 아니다. 일부 필드가 빠지면 `PARTIAL`, manifest가 없거나 결과와 맞지 않으면 `MISSING`·`MISMATCH`를 그대로 보여 준다.
- 행 저장 당시 호출 원장과 실행 종료 manifest의 계측은 따로 보여 준다. 실시간 이벤트로 합산한 토큰과 manifest 사용량은 집계 범위가 다르다. 기록된 토큰 수를 정식 KPI로 바꾸지 않으며 `NOT_ESTIMABLE`, null, `UNBOUND_PARTIAL`을 그대로 둔다.
- 후보 회수·재정렬·의미 역할·교정·inference와 커뮤니티 지식 기록은 결과의 `run_meta`에 저장된 경우에만 상세에 표시한다. 큰 기록 자료는 목록과 SSE에 넣지 않는다. 빈 후보를 NIL 판정으로, 미교정 점수를 확률로 표시하지 않는다.
- 복구 결과는 `run_meta`가 아니라 서버의 별도 reader가 읽어 `recovery_execution`, `recovery_provider_execution`, `recovery_native_execution`으로 붙인다. native 복구 reader는 aggregate가 원래 결과·manifest, 선택한 행과 SHA로 연결되는지 검사하고 맞지 않으면 `MISSING`·`INVALID`로 표시한다. 복구는 원래 결과·manifest·WAL을 덮어쓰지 않는다.

## 이력 탐색의 상한

| 항목 | 상한 |
| --- | --- |
| 목록 탐색 | 항목 50,000개, manifest 2,000개, 디렉터리 깊이 12, 결과 캐시 30초 |
| 선택한 결과 파일 | 128MiB |
| manifest 파일 | 2MiB |
| 최근 current 실행 위치 | 24개 |

탐색이 상한에 걸리면 `/api/runs` 응답의 `X-Run-Index-Truncated` 헤더가 `true`가 되고 화면에 일부 이력 생략 안내가 나온다. 상한을 넘거나 손상된 결과를 다른 최신 결과로 바꿔 보여 주지 않으며, 허용된 `out/` 경로 밖의 파일은 열지 않는다.

서버는 현재 실행(current)의 출력으로 확인한 위치를 최근 24개까지 따로 보존한다. 그래서 탐색 상한 밖에 있는 직전 실행도 이력 목록에 남는다. 이 보존 목록은 서버 메모리에만 있으므로 서버를 재시작하면 사라진다.

## 정적 자산

브라우저는 저장소의 정적 자산만 사용한다. 실행 중에는 Node.js나 CDN 접속이 필요하지 않다.

| 파일 | 역할 |
| --- | --- |
| [`index.html`](../../src/llm_batch/monitor/static/index.html) | 화면 구조와 대시보드 동작 |
| [`dashboard.css`](../../src/llm_batch/monitor/static/dashboard.css) | 배치, 컴포넌트, 두 테마의 색상 변수 |
| [`theme.js`](../../src/llm_batch/monitor/static/theme.js) | 초기 테마, 선택 저장, OS 변경과 탭 동기화 |
| [`presentation.js`](../../src/llm_batch/monitor/static/presentation.js) | 판정 사유·진단 필드·단계별 로그와 JSON 표시 |
| [`utilities.css`](../../src/llm_batch/monitor/static/utilities.css) | 로컬 생성 Tailwind CSS. 직접 편집하지 않는다. |
| [`tailwind.config.cjs`](../../tools/dashboard/tailwind.config.cjs) · [`input.css`](../../tools/dashboard/input.css) | Tailwind 생성 입력, HTML 스캔 경로, 동적 worker 클래스 safelist |
| [`server.py`](../../src/llm_batch/monitor/server.py) | HTML, `/static` 자산, API, SSE 제공 |
| [`slang_view.py`](../../src/llm_batch/monitor/slang_view.py) | Slang DB 파일 내용을 화면용 행·요약으로 변환 |
| [`run_index.py`](../../src/llm_batch/monitor/run_index.py) | 실행 이력 탐색, 결과와 manifest 연결, 최근 current 실행 보존 |

`index.html`은 각 자산을 `/static/presentation.js?v=<토큰>`처럼 버전 토큰을 붙여 불러온다. JS나 CSS를 바꾸면 해당 토큰도 바꿔 이전 브라우저 캐시와 구분한다. 회귀시험이 `presentation.js` 토큰을 확인하므로 토큰을 바꾸면 `tests/test_dashboard_standalone.py`의 기대값도 같이 갱신한다.

유틸리티 클래스를 바꿨다면 개발 환경에서 Tailwind 3.4.17 결과를 다시 만든다. 처음 `npx`를 실행할 때는 패키지 다운로드가 필요할 수 있다.

```powershell
npx.cmd --yes --package tailwindcss@3.4.17 tailwindcss --config tools/dashboard/tailwind.config.cjs --input tools/dashboard/input.css --output src/llm_batch/monitor/static/utilities.css --minify
```

기본 색상 팔레트는 `--color-COLOR-SHADE` RGB 변수로 연결되고, 실행 중 만들어지는 worker 필터도 `dashboard.css`의 테마 값을 쓴다. 문자열로 조합하는 새 유틸리티는 Tailwind 정적 스캔에 잡히지 않을 수 있으니 config의 safelist도 확인한다.

아이콘은 공식 `lucide-static@0.468.0` 패키지의 SVG 원본을 [`static/icons`](../../src/llm_batch/monitor/static/icons)에 두고 CSS mask로 쓴다. 배포할 때 동봉한 [Lucide 라이선스](../../src/llm_batch/monitor/static/icons/LICENSE)를 유지한다.

서버 코드나 `/static` 경로가 바뀌면 대시보드 서버를 재시작한다. CSS·JS만 바뀌었다면 페이지를 새로고침하고, 이전 스타일이 남으면 강력 새로고침으로 캐시를 비운다. 실행 중인 분석을 멈출 필요는 없다.

## 점검

대시보드 관련 변경 뒤에는 서버·이벤트·이력 시험과 화면 표시 시험을 함께 실행한다.

```powershell
.venv312/Scripts/python.exe -m pytest -q tests/test_dashboard_standalone.py tests/test_dashboard_run_index.py tests/test_dashboard_cache_scan_budget.py tests/test_dashboard_current_run_resolution.py tests/test_history_current_retention.py tests/test_dashboard_slang_db_view.py
.venv312/Scripts/python.exe -m unittest tests.test_dashboard_standalone tests.test_monitor_event_bus
node --test tests/dashboard_presentation.test.cjs tests/dashboard_theme.test.cjs
```

화면 배치나 테마를 바꿨다면 실제 브라우저에서 화이트·다크 두 테마와 좁은 화면의 가로 넘침, 콘솔 오류를 확인한다. 개발 체크리스트는 [CHECKLIST](CHECKLIST.md)에 있다.
