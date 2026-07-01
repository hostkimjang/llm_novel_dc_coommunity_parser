# 전수 POST 판정 재검 · 검색 정답성 검증 · 적대적 재검증 런북 (엔진 비의존 / ultracode)

목적: 최신 대규모 런(예: `out/expert_result_20260616_224555_632905.json`, flushed=2246 + pending=23)의
**처리된 모든 POST를 하나도 빠짐없이** 대상으로, 파이프라인이 내린 LLM 판정을 독립 재확인하고,
각 행에 이미 수집된 `search_evidence_catalog`(+필요 시 웹 재검색)로 **검색 정답성**을 검증하며,
자동수용 결과를 적대적으로 재검증하고, 문제점과 일반화 가능한 개선 아이디어까지 묶어 **전수 보고서**를 만든다.

이 런북은 **날짜 비의존**이며 새 런 스냅샷에 반복 적용한다(산출물 경로의 run_id만 교체).
**스키마는 엔진 비의존**이다: Claude Workflow(§9), Codex-native web judge(§8), 로컬 Python 집계 루프(§3)가 모두 **동일한 verdict 스키마(§4)** 를 만든다.
단 completed779 외부 LLM judge의 기본 실행 엔진은 Codex 5.5 native web search/open이며, 기존 `tools/run_agbrowse_llm_judge.py` 브라우저 GPT-Pro 경로는 legacy 참고용이다.

---

## 0. 실행 전 반드시 알아야 할 점

0.1 **엔진 비의존**: 핵심은 도구가 아니라 **프롬프트(§4·§5)와 출력 스키마(§4.3)** 다.
"판정/검증" 단계는 결국 *배치 파일마다 LLM 1회 호출 → JSON verdict 파일 쓰기* 루프다(순차·병렬 무관).
어느 백엔드를 쓰든 산출물(§4.3 스키마)은 같다. 단 **"웹검색 전반"(채택된 요구)** 충족 여부는 백엔드마다 다르므로
아래 **백엔드 × 웹검색 능력 매트릭스**로 경로를 고른다.

| 백엔드 | LLM 판정 | 네이티브 웹검색 | Claude 한도 소모 | 비고 |
| --- | --- | --- | --- | --- |
| **로컬 vLLM Gemma-4-26B-A4B** (`LLMClient` / OpenAI 호환, §2.2) | O (무료·빠름) | **X (없음)** | **없음** | 단독으론 웹검색 충족 불가. 단, **파이프라인 검색 클라이언트(아래 0.1a)를 루프에 붙이면** 로컬·무료로 웹증거 확보 가능. |
| **Codex 5.5 native web judge** (§8) | O | **O (Codex 내장 web search/open)** | **없음** | API key·agbrowse 없이 구독제 Codex가 직접 post 원문을 읽고 검색한다. **이번 completed779 전수 기본 경로.** |
| **Claude Workflow** (§9) | O | O (`WebSearch` 툴) | **있음 (~150 judge 에이전트 = 2246/15)** | 한도 여유 있을 때만. D4 기본 거절. |
| **브라우저 GPT-Pro/agbrowse** (`tools/run_agbrowse_llm_judge.py`) | O | X 또는 불안정 | 없음 | 이번 요구에는 쓰지 않는다. 과거 head-slice judge용 legacy 경로이며 Codex-native web judge를 대체하지 못한다. |

**중요 정정(2026-06-21):** 여기서 말하는 LLM judge는 파이프라인 로그/history를 규칙으로 재해석하는 deterministic audit가 아니다. Codex 5.5가 각 post의 원문(title/body/comments/OCR)과 pipeline final만 보고, 필요한 경우 내장 web search/open으로 공식 작품 페이지·커뮤니티 별칭·후보 URL을 직접 확인한 뒤 JSON verdict를 작성하는 **외부 시각의 Codex-native web judge**다. API key, OpenAI/Anthropic API client, `agbrowse`는 필요하지 않다.

**0.1a 파이프라인 자체 검색 클라이언트는 judge 루프에서 그대로 재사용 가능하다(검증됨).**
런 중 `search_evidence_catalog`를 채운 검색 경로는 `src/llm_batch/search/client.py::MCPClient.search(query, num_results, purpose) -> {results:[{title,url,content,engine}], total}` 이며,
`agentic_pipeline.py:58/141/633`이 이 클라이언트로 `self.mcp.search(...)`를 호출한다. 이는 **로컬에서 돌아가는 HTTP 서비스**(MCP Bridge `POST /mcp/search`, 기본 `http://127.0.0.1:3333`, SearXNG+headless 폴백)로,
Claude/Codex 없이 **판정 프로세스에서 독립적으로 호출 가능**하다(의존 없이 `httpx.post(f"{MCP_ENDPOINT}/mcp/search", json={"query":q,"num_results":8})` 한 줄, 또는 `from llm_batch.search.client import MCPClient; MCPClient().search(q)`).
페이지 본문이 필요하면 `MCPClient.fetch(url)`(`/mcp/fetch`). 따라서 **"웹검색 전반"은 로컬 vLLM 경로에서도 이 클라이언트로 충족된다** — 단 vLLM은 검색을 자율 호출하지 못하므로, 루프 측이 official_title/heretic_url 기반 질의를 만들어 evidence를 모델에 주입하는 **tool-injection 방식**이어야 한다(자율 tool-call 아님).

0.2 **LLM은 판정자(judge)로만 쓴다 (생성 금지).** 파이프라인은 retrieval-first라 *항상 무언가를 resolve하려고 과도하게 시도*한다.
판정자에게 작품명을 생성하게 하지 말고, 파이프라인이 낸 결론이 맞는지 **독립적으로** 판정만 시킨다.
**앵커링 방지**: 판정자에게 파이프라인의 내부 근거(`reason_lines` 체인)를 넣지 말고,
파이프라인의 *결론*(official_title / work_resolution / is_relevant / discussion_type)과 *원천 증거*(본문·댓글·이미지 OCR·`search_evidence_catalog`)만 준다.
판정자는 원천에서 스스로 결론을 도출한 뒤 파이프라인 결론과 대조한다.

0.3 **읽기 전용**: 결과 JSON·slang_db는 읽기만 한다. **`slang_db`에 write-back 금지** (`--slang-db off` 또는 판정 전용 경로).
파이프라인을 재실행(`expert_main.py`)하는 것은 별개 단계이며, 판정 런 자체는 어떤 출력 파일도 변형하지 않는다.

0.4 **결정성/재현성**: 배치 분할은 입력 순서 고정(시드 불필요, post_id 정렬). 판정은 LLM이라 완전 결정적이진 않으나
배치 크기·스키마·프롬프트를 고정하면 분포는 안정적이다. 멱등: 같은 배치를 다시 판정하면 verdict 파일을 덮어쓴다(부분 재실행 안전).

0.5 **개수 보존(누락 0)**: verdict의 post_id 집합은 입력 batch의 post_id 집합과 **정확히 같아야** 한다.
병합 후 `judged == flushed(2246)`, `missing == 0`을 검증한다. **pending 23건은 미처리(분석 결과 없음)** 이므로
판정 대상이 아니라 **`re_run` 큐**로만 기록한다(절대 ACCEPT/판정하지 않음).

0.6 **표기 규약(영어 enum + 한글 병기)**: `disagreement_type`·`candidate_ledger_status`·`resolution_label`은
코드/JSON에서는 영어 enum 원본을 유지하고, 사람이 읽는 Markdown 보고서에서는 `영어 (한글)` 병기로 렌더한다.
용어 뜻은 보고서 §0 용어표에 한글로 적는다.

0.7 **게이트 분리(필수)**: 모든 보고에서 **(a) run 무결성(GO/REVIEW/NO-GO)** 과 **(b) semantic 품질(GO/REVIEW-LOCKED)** 과
**(c) full-scan approval(true/false)** 을 절대 섞지 않는다. 이 전수 판정은 **보조 기준선**이며,
동결 gold 게이트도, full-scan approval도 아니다. semantic 품질은 기본 **REVIEW-LOCKED**, full-scan approval은 **false**로 둔다.

0.7a **completed779 native-web 개선 루프(2026-06-22 추가)**: completed subset `779`를 개선 source로 쓸 때는
deterministic `full_post_judge_report.md` 집계와 Codex-native web verdict 집계를 섞지 않는다. deterministic report는 source coverage와 이전 judge artifact,
native-web verdict는 issue index/action queue/seed packet의 기준선이다. 운영 절차는:

1. `tools/build_completed779_issue_index.py --result out\expert_result_20260620_165159_711176_completed_subset.json --judge-root out\codex_native_web_judge_20260620_165159_711176_completed779 --out-dir out\completed779_improvement_goal_YYYYMMDD`
2. `native_web_issue_index.json`에서 `total=779`, non-ACCEPT `266`, missing `0`, duplicate after dedupe `0`을 확인한다.
3. `balanced_p0_seed.jsonl`은 `65`건, 네 bucket `15/15/25/10`, `11694064` 포함, `wrong_work=9` 전체 포함이어야 한다.
4. `inputs/balanced_p0_text_url_comment.jsonl`과 `inputs/balanced_p0_image_ocr.jsonl`을 분리해 `expert_main.py` canary를 실행한다.
5. `tools/compare_completed779_improvement.py`로 before/after `official_title`, `heretic_url`, resolution/candidate/lint movement를 기록한다.
6. 이 루프가 성공해도 full-scan approval은 계속 `false`다. semantic 품질은 expanded review 전까지 `REVIEW-LOCKED`다.

0.8 **민감 표현 치환**: 본문/댓글에는 성적·연령·폭력 민감 표현이 섞여 있다. 판정자에게 넘기기 전
`tools/run_agbrowse_llm_judge.py`의 `redact_sensitive_payload`와 동일하게 bracket label(`[성적행위/성인표현]` 등)로 치환한다.
치환 label 자체를 작품명으로 보지 말 것.

---

## 1. 산출물 정의

`S = out/full_post_judge_<run_id>/` 로 둔다. (예: `run_id = 20260616_224555_632905`)

| 파일 | 내용 |
| --- | --- |
| `S/batches/batch_NNN.json` | 판정 입력 배치(배치당 ≤ batch_size). 컴팩트 projection(§2.3) + post_id 목록 메타. |
| `S/verdicts/verdicts_NNN.json` | 배치별 1차 LLM 판정 결과(§4.3b FULL 스키마; vLLM 경로는 §4.3a LEAN을 post-processor로 materialize). |
| `S/_verdicts_merged.json` | 1차 판정 병합 + 커버리지 검증(judged/missing/bad_files). |
| `S/verify/vbatch_NNN.json` | 정밀 verify 풀(ACCEPT/safe_resolved·resolved) 재검증 입력(1차 판정 첨부). |
| `S/verify/vverdicts_NNN.json` | 정밀 풀 적대적 재검증 결과(§4.3b 스키마 + `changed_from_first`). |
| `S/verify/rhold_batch_NNN.json` | 재현 verify 풀(hold/unresolved 15% 층화표본, §3 step 5b) 재검증 입력. |
| `S/verify/rhold_vverdicts_NNN.json` | 재현 풀 적대적 재검증 결과(§4.3b 스키마 + `changed_from_first`). |
| `S/_verdicts_final.json` | 1차 + 재검증 오버레이 최종 verdict + 일치율/다운·업그레이드 통계. |
| `S/_shadow_rebucket.json` | `candidate_audit`로 재산출한 결정적 `candidate_ledger_status`(파이프라인 라벨 vs judge 라벨 대조용). |
| `S/report/full_post_judge_metrics.json` | §6 집계 지표(전수, top-N 금지). |
| `S/report/full_post_judge_report.md` | 서술형 종합 보고서(용어표·정밀/재현 양면·문제점·개선 아이디어·게이트). |
| `S/report/rows/full_post_judge_rows_pNN.md` | **전수 행별 dump**(페이지 분할, 기본 300행/페이지). nav 링크 + 표 헤더 포함. |

`rows_pNN.md` 렌더 규약(필수): 5천 행급 단일 표는 미리보기에서 잘리므로 페이지로 분할한다.
각 페이지는 단독으로 미리보기 가능해야 하며 열은
`index · post_id · pipeline_verdict(work_resolution/official_title) · judge resolution_label(한글) · hold_reason · disagreement_type(한글) · search_grade · severity · recommended_action · LLM 판단 사유(한글)`.
표 셀은 `|`·줄바꿈 이스케이프, 제어문자(NUL 등) 정화, **상한·top-N 금지(전수 유지)**. 표 앞에는 빈 줄을 둔다.
모든 post 행은 GPT/Claude/vLLM 어느 경로의 judge이든 사람이 바로 읽을 수 있는 한국어 판단 사유를 반드시 가진다. `ACCEPT` 행도 "왜 수용했는지", `none/unresolved` 행도 "왜 작품명 미확정을 수용했는지"를 1~3문장으로 적는다. raw enum, URL, 검색 등급은 보조값으로 남길 수 있지만, 행별 dump의 주된 이유 칸이 영어 key-value만으로 끝나면 실패다.

---

## 2. 사전 준비

2.1 **대상 결과 파일**: `out/expert_result_<run_id>.json` (list of `PickvelOutputItemV2`).
각 원소: `gallery_id, post_id, title, content/content_blocks, image_urls, comments, comment_metadata, analysis_result{post_id, identity, analysis}, run_meta`.
판정자가 보는 핵심은 `analysis_result.identity`(=`PickvelIdentity`, `src/llm_batch/models.py:96-267`).
manifest(`*_manifest.json`)에서 `flushed_count/pending_count/large_run_complete/vlm_enabled/ocr_enabled`를 먼저 확인한다.
`large_run_complete=false`면 partial이므로 `completed_subset.json`은 부분 승인용일 뿐 1차 결과로 쓰지 않는다.

2.2 **LLM 호출 경로 (로컬 vLLM, Codex 기본)**: goal.md와 일치하는 기본값
```
endpoint = http://10.20.0.101:8000   model = bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4   server_type = vllm
```
OpenAI 호환 `/v1/chat/completions`. 두 가지 방법:
- (a) repo 내장 `src/llm_batch/llm/client.py::LLMClient` 재사용. 생성은 `LLMClient()`(인자 없음), 환경변수로 설정:
  `LLM_ENDPOINT`, `LLM_MODEL`, `LLM_SERVER_TYPE=vllm`. 호출은 `_stream_chat_http(messages=[{role,content}], tag="judge", use_grammar=False) -> str`.
  (주의: `_stream_chat_http`는 private. public wrapper 없음. JSON 루프 감지 캡(`LLM_POST_JSON_*`)이 있으니 판정 런에선 환경변수 점검.)
- (b) 의존 없이 `openai`/`requests`로 직접 `POST {endpoint}/v1/chat/completions` (model 위 값). **Codex는 (b)가 가장 단순.**
- 인터프리터: **`.venv312\Scripts\python.exe`** (Windows Python 3.12). 테스트는 `unittest`.

2.3 **컴팩트 projection(배치 입력 1행)** — 판정자에게 주는 1 POST 레코드. 앵커링 방지를 위해
파이프라인 `reason_lines`(내부 체인)는 제외하고 *결론*과 *원천 증거*만 담는다:
```json
{
  "post_id": 11718077,
  "gallery_id": "genrenovel",
  "title": "<글 제목(redacted)>",
  "url": "<url>",
  "body": "<content_blocks 텍스트 합본(redacted)>",
  "comments": ["<댓글 라인(redacted)>"],
  "comment_attribution": "anonymous_unverified | post_author_ip_match | ...",
  "image": {"image_count": 1, "ocr_text": "...", "visual_summary": "...",
            "explicit_work_title": "...", "promotion_eligible": false, "title_role": "character_name"},
  "search_evidence": [
    {"rank": 1, "source_tier": "community", "domain": "arca.live",
     "title": "...", "url": "...", "snippet": "...", "purpose": "title_anchor_exact_probe"}
  ],
  "pipeline_verdict": {
    "is_relevant": true, "is_novel_related": true, "topicality": "core_relevant",
    "discussion_type": "general", "work_resolution": "resolved",
    "title_resolution_state": "resolved", "title_resolution_allowed": true,
    "official_title": "즉사기 들고 무림에 떨어지다", "heretic_url": "https://novel.munpia.com/528383",
    "confidence": "High", "anchor_type": "title_alias", "anchor_strength": "medium",
    "primary_source_tier": "official_detail",
    "candidate_ledger_status": "safe_resolved",
    "blocked_official_title": null, "promotion_blocked_reasons": [],
    "official_title_lint": [], "identity_consistency_lint": [], "output_consistency_lint": []
  },
  "slang": {"detected_term": "즉사무림", "decoded_term": "...", "decode_verified": true,
            "canonical_work_alias": "즉사무림", "alias_scope": "pure_work_alias",
            "store_in_slang_db": true, "store_reason": "pure_work_alias"},
  "precomputed": {
    "shadow_candidate_ledger_status": "safe_resolved",
    "official_search_supports_title": true,
    "explicit_image_work_titles": [],
    "heretic_url_present": true,
    "primary_source_tier": "official_detail",
    "suggested_search_grade": "Strong",
    "official_title_lint_reasons": [], "identity_consistency_lint_reasons": [], "output_consistency_lint_reasons": [],
    "slang_present": true,
    "slang_store_in_db": true,
    "slang_pollution_suspect": false,
    "slang_suspect_reasons": [],
    "slang_axis_route": "llm",
    "deterministic_slang_verdict": "ok"
  }
}
```
`search_evidence`는 토큰을 위해 상위 ~8개(서로 다른 domain 우선)만 넣되, **`source_tier in {official_detail, novel_platform}`인 항목은 우선 포함**한다(검색 정답성 판정 핵심).

**`precomputed` 블록(결정적 사전계산, 채택됨)**: 슬라이스 단계에서 LLM 없이 `candidate_audit.py`로 미리 계산해 넣는다 —
`shadow_candidate_ledger_status`=`classify_candidate_audit(identity, {})`, `official_search_supports_title`=`official_search_supports_title(identity, official_title)`,
`explicit_image_work_titles`=`_explicit_image_work_titles(identity)`, `*_lint_reasons`=각 lint 함수, `suggested_search_grade`=아래 휴리스틱.
`suggested_search_grade` 휴리스틱: `official_search_supports_title and heretic_url 상세 → Strong` / `novel_platform·wiki 간접 정합 → Medium` / `community·listing·snippet → Weak` / `resolved인데 근거 없음 or heretic_url=null → Missing`.
판정자는 이 값을 **출발점**으로 삼아 [축 C]에서 확인·override만 한다(소형 모델 부담↓, 재현성↑).

**slang 결정적 사전계산(D2 확정 — deterministic-first)**: slang 필드도 슬라이스 단계에서 **LLM 없이** 미리 계산해 precomputed에 넣는다 —
- `slang_present`(bool) = `slang.detected_term`이 비어있지 않음.
- `slang_store_in_db` = `slang.store_in_slang_db`.
- `slang_pollution_suspect`(bool) = 아래 **ANY**:
  (`store_in_slang_db==true` AND `decode_verified==false`); (`store==true` AND official_title 부재); (`store==true` AND `alias_scope` ∉ `{pure_work_alias}`);
  (`store==true` AND `normalize(canonical_work_alias)==normalize(official_title)`); `slang_db._example_has_polluted_alias_seed_signal(...)==true`; `slang_db._is_unresolvable_memory_query_context(...)==true`.
- `slang_suspect_reasons`[..] = 위에서 참인 조건들의 라벨.
- `slang_axis_route`(`"llm"`|`"deterministic_na"`) = (`store_in_slang_db==true` OR `slang_pollution_suspect==true`) 이면 `"llm"`, 그 외 `"deterministic_na"`.
- `deterministic_slang_verdict`(`"ok"`|`"pollution_risk"`|`"over_blocked"`|`"na"`) = 결정적 사전판정. `slang_axis_route=="deterministic_na"`면 `na`.

이 라우팅은 이 런 기준 **~94/2246 행만** LLM에 보낸다(`store_in_slang_db=true` 또는 결정적 pollution-suspect). 나머지는 `deterministic_slang_verdict`(보통 na)로 결정적 확정하고 LLM 토큰을 쓰지 않는다.

2.4 **재사용 자산(재발명 금지)**:
- `src/llm_batch/candidate_audit.py` — judge-grade 결정적 헬퍼: `classify_candidate_audit(identity, judge_seed)`(8 라벨),
  `official_search_supports_title(identity, title)`, `_explicit_image_work_titles`, `official_title_lint_reasons`/`identity_consistency_lint_reasons`/`output_consistency_lint_reasons`,
  `seed_group(disagreement_type)`(recall/precision/hygiene/unseeded), `build_candidate_ledger`.
  → judge 전/후 **결정적 재버킷**(LLM 없이)에 사용.
- `candidate_audit.slang_audit(identity) -> dict`(D2 추가 헬퍼) — `slang_db._is_generic_term`/`_is_exact_title_alias`/`_example_has_polluted_alias_seed_signal`/`_is_unresolvable_memory_query_context`를 래핑해
  §2.3 slang 필드(`slang_present`/`slang_store_in_db`/`slang_pollution_suspect`/`slang_suspect_reasons`/`slang_axis_route`/`deterministic_slang_verdict`)를 결정적으로 산출한다.
  (주의: `candidate_audit`에는 현재 slang 코드가 **없다** — 이는 additive 추가다. 슬라이스 단계가 다른 precomputed 헬퍼와 동일하게 이 함수를 호출한다.)
- `tools/build_judge_seed_registry.py` — `build`(judge 리뷰 JSONL → seed_registry + shadow_label + canary input), `compare`(before/after delta + run_integrity GO/REVIEW 게이트).
- `tools/run_agbrowse_llm_judge.py` — 완성형 배치 러너(프롬프트 템플릿·검증·정규화·fallback·재시작·집계). 단 **웹검색 미수행** → 본 런북은 검색 정답성 축을 추가하므로 §4 프롬프트로 교체해 사용.
- `docs/devs/SCAN_RESULT_REVIEW_GUIDE.md`(§4 증거정책·§10 판정품질·§13 게이트·§14 실패 taxonomy·§16 action queue·§17 출력 템플릿), `OPERATION_QUALITY_CHECKLIST.md`, `LLM_JUDGMENT_REVIEW.md`, `JUDGE3905_REPORT.md`.

---

## 3. 단계별 절차 (명령/루프)

```
# (1) 슬라이스: 결과 list를 post_id 정렬 → 컴팩트 projection(§2.3) → batch_NNN.json (배치당 BATCH).
#     로컬 vLLM 권장 BATCH=5 (Gemma-4-26B-A4B는 NVFP4 양자화 MoE(활성 ~4B) → enum 슬롯 안정성 위해 작게; 더 강하면 재측정 후 상향 가능). Claude/GPT-Pro면 10~15 가능.
#     pending 23건은 batch에서 제외하고 S/_pending_rerun.json 으로 따로 적는다.
# (1b) 결정적 사전계산(채택): 각 행의 identity로 candidate_audit.classify_candidate_audit / official_search_supports_title /
#      _explicit_image_work_titles / *_lint_reasons 를 LLM 없이 계산해 projection의 precomputed 블록에 넣는다(§2.3).
#      전수 4축 풀 판정이므로 noise/none 행도 batch에 포함한다(재현 거짓음성이 거기 숨어 있음).

# (2) 1차 전수 판정: batch_NNN.json 마다 §4 프롬프트로 LLM 1회 호출 → verdicts_NNN.json.
#     출력은 §4.3b FULL 스키마(vLLM은 §4.3a LEAN→결정적 post-processor로 materialize).
#     post_id 집합 == 입력 집합(누락 0), agree==(disagreement_type=="none") 검증.
#     실패 배치는 fallback(uncertain/REPROCESS) 후 재시도; 유효 verdicts 파일은 skip(재시작).

# (3) 병합 + 커버리지: 모든 verdicts 병합 → _verdicts_merged.json. judged==2246, missing==0, bad_files==[] 확인.
#     누락 배치는 그 번호만 재실행.

# (4) 결정적 재버킷: candidate_audit.classify_candidate_audit 로 각 행의 shadow candidate_ledger_status 재산출
#     → _shadow_rebucket.json. (파이프라인 라벨과 judge 라벨의 결정적 대조군.)

# (5) 정밀 verify 풀: resolution_label==ACCEPT 또는 (work_resolution=="resolved" & confidence in {High,Medium})
#     항목 + 1차 판정 첨부 → vbatch_NNN.json. (정밀 오류 = 잘못 ACCEPT한 해소를 잡는 풀.)

# (5b) 재현 verify 풀: candidate_ledger_status in {hold_unresolved} 및 title_resolution_state in
#      {unresolved_matchable, ocr_explicit_title_unresolved, author_new_work_context, context_only}를 모집단으로,
#      suggested_search_grade≠Missing·explicit_image_work_titles 존재·댓글 제목응답 등 신호로 층화한 15% 표본
#      (seed 고정, post_id 정렬 후 결정적 추출)을 rhold_batch_NNN.json 으로 쓴다.
#      demote-but-preserve(promotion_blocked)는 정밀 성공이므로 제외.

# (6a) 정밀 적대적 재검증: vbatch_NNN.json 마다 §5 프롬프트로 호출 → vverdicts_NNN.json (회의적 재판정).
# (6b) 재현 적대적 재검증: rhold_batch_NNN.json 마다 §5b 프롬프트로 호출 → rhold_vverdicts_NNN.json (놓친 작품 적극 재탐색).

# (7) 오버레이: 정밀 풀(vverdicts)·재현 풀(rhold_vverdicts) 재검증 판정을 해당 행에 최종 채택 → _verdicts_final.json.
#     1차↔재검증 일치율은 두 풀 분리 집계(정밀: ACCEPT→HOLD/REJECT downgrade / 재현: HOLD·none→REPROCESS upgrade). §6.6 참조.

# (8) 집계 + 보고서: §6 지표 → full_post_judge_metrics.json, 서술형 full_post_judge_report.md,
#     전수 페이지 rows/full_post_judge_rows_pNN.md(300행/페이지).
```

검증(코드 변경을 동반했을 때만; 순수 판정 런은 불필요):
```
.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit tests.test_judge_seed_registry -v
git diff --check
```

### 3.1 축소판 (기능 개선·버그 수정 후 소수 케이스)
전수 대신 high-risk/random 표본만 돌릴 때도 같은 judge 축을 축소 적용한다:
- 표본 = 정밀(precision) 위험 버킷(`safe_resolved` 중 weak source_tier·search_only·OCR-only) + 재현(recall) 위험 버킷(`unresolved_matchable`·`ocr_explicit_title_unresolved`·`hold_unresolved`) + random50.
- 항목별 §4.3 verdict + 한 줄 근거. 정밀/재현/검색 정답성/slang을 분리 보고.
- random_control과 high-risk_expansion은 **분리** 보고(오류율 합산 금지).
- 이 축소판도 보조 기준선이다. 사람 검수 gold와 full-scan approval을 대체하지 않는다.

---

## 4. 1차 판정 프롬프트 (그대로 사용)

### 4.1 system
```
You are a strict JSON API that independently re-audits a Korean web-novel community (dcinside) post→work matching pipeline.
Return exactly one valid JSON object and no markdown, no code fences, no tables, no prose outside JSON.
You judge; you never invent titles. Decide independently from the source, then compare to the pipeline conclusion.
Web search is allowed and encouraged to confirm/refute a title's real existence and detail-page title match; cite the decisive URL in note. Never fabricate a title from search.
If evidence is insufficient, use disagreement_type='uncertain' and resolution_label='INFO_MISSING'.
```

### 4.2 criteria (verbatim — 사용자 프롬프트 본문)
```
너는 한국 웹소설 커뮤니티(dcinside) 글의 "작품 매칭/관련성 판정" 파이프라인을 독립 재판정으로 검수하는 보안·품질 judge다.
각 POST 레코드는 원천(title/body/comments/image OCR)과 미리 수집된 search_evidence, 그리고 파이프라인의 결론(pipeline_verdict)을 담는다.
파이프라인은 retrieval-first라 항상 무언가를 resolve하려 과도하게 시도한다 — pipeline_verdict.official_title에 끌려가지 마라(anchoring 금지).
너는 원천과 search_evidence로 스스로 판단한 뒤 파이프라인 결론과 대조한다. 파이프라인이 틀린 케이스를 찾아내는 것이 목적이다.
웹검색은 허용된다(채택). official_title의 실제 존재·작품 상세페이지 제목 일치·관련성을 확증/반증하기 위해 적극적으로 웹검색하라.
다만 검색은 판정 근거 확인용이며, 검색 결과로 작품명을 "생성"하지 마라. 사용한 결정적 근거 URL은 note에 적는다. 검증 못 한 부분은 web_unverified를 note에 남기고 보수적으로 처리한다.

각 POST마다 4개 축을 모두 본다 (전수 동일 4축 풀 판정 — noise/none 행도 [축 A][recall] 포함 전부 본다):

[축 A — 관련성/문맥 판정 재확인]
- 이 글이 (a) 소설 관련인가(is_novel_related) (b) 특정 웹소설을 식별/토론하는가(is_relevant & work) (c) 실제 의도/문맥(discussion_type)이 맞는가.
- 파이프라인의 is_relevant/topicality/discussion_type과 대조. 어긋나면 hygiene/recall 계열 disagreement_type을 선택.

[축 B — 작품 해소(official_title) 정확성]
- pipeline_verdict.official_title이 이 글이 가리키는 바로 그 작품인가? 다른 작품/벤더면 wrong_work, 유명 타매체 혼동이면 cross_media_or_famous_mismatch,
  해소하지 말았어야 하는데 했으면 over_resolved, 제목이 아닌 표면(URL/광고/공지/문장)이면 garbage_title.
- 핵심: official_title이 "맞아 보인다"고 ACCEPT가 아니다. 아래 [축 C] 검색 정답성과 hard anchor가 충족되어야 ACCEPT다.

[축 C — 검색 정답성 확인 (가장 중요)]
- precomputed(official_search_supports_title / suggested_search_grade / *_lint_reasons / shadow_candidate_ledger_status)를 **출발점**으로 받는다. 이 결정적 값을 검토해 확인하거나 override한다(틀렸다고 보면 근거와 함께 바꾼다).
- search_evidence와 heretic_url, 그리고 필요 시 웹검색으로 official_title이 실제로 그 작품에 대응하는지 확인한다.
- OFFICIAL로 인정되는 근거: source_tier가 official_detail 또는 novel_platform 이고, URL이 작품 "상세 페이지"이며(작가/검색/랭킹/장르/목록/뷰어/커뮤니티/리뷰 탭 아님),
  그 페이지의 제목/설명이 official_title과 엄밀히 일치하는 경우.
- WEAK(불충분): 검색 스니펫 반복, listing/search 페이지, 삭제 페이지, community/wiki, 등록 약칭(KNOWN_*)·slang 사전 단독 일치, 다른 공식 제목의 부분문자열에 불과한 짧은 제목.
- official_detail_url_match: heretic_url이 작품 상세이고 제목이 일치하면 true, 상세인데 불일치면 false, 검증 불가/부재면 null.
- search_evidence_grade ∈ {Strong, Medium, Weak, Missing}:
  Strong=official_detail/novel_platform 상세 URL이 제목과 일치. Medium=플랫폼/위키 등 간접 근거가 제목과 정합. Weak=스니펫/listing/community 정도. Missing=해소했는데 근거 없음/heretic_url=null.
- 함정: official_title은 맞아도 heretic_url=null 또는 검색근거가 search_only(본문에 작품 단서 없음)면 ACCEPT가 아니라 HOLD다(search_only_resolved_title).
- 함정: official_urls가 있다고 reason에 적혀 있으나 heretic_url=null이면 모순(reason_evidence_state_mismatch).

[축 D — slang 저장 정당성]
- 축 D는 `precomputed.slang_axis_route=="llm"`인 행(이 런 기준 ~94건: store_in_slang_db=true 또는 결정적 pollution-suspect)에서만 LLM이 판정한다.
  그 외 행은 `precomputed.deterministic_slang_verdict`(보통 na)로 결정적 확정하고 LLM 토큰을 쓰지 않는다.
- (LLM 판정 행에서) slang.store_in_slang_db / store_reason / alias_scope / decode_verified와 함께 precomputed.deterministic_slang_verdict·slang_suspect_reasons를 본다.
  너의 일은 그 결정적 사전판정을 **확인(confirm)하거나 override**하는 것이다(틀렸다고 보면 근거와 함께 바꾼다).
- 정상 학습: 단일 (alias→official_title)이 실제 anchor(heretic_url/official_title_evidence/캐릭터·제목 anchor, decode_verified=true)로 확인된 pure_work_alias.
- 오염 위험(pollution_risk): canonical_work_alias가 official_title과 동일, decode_verified=false인데 고확신 저장, composite(work+character/author/meme)인데 저장, memory-query/context-only인데 저장, 한 alias가 여러 작품에 붙음.
- 과차단(over_blocked): 정당한 pure_work_alias가 근거 충분한데 store=false.
- store=true 행은 결정적 replay가 저장 contract와 같아야 한다 — deterministic_slang_verdict와 너의 판정이 어긋나면 **contract 버그 의심**이므로 recommended_action=slang_db_review.
- slang_verdict ∈ {ok, pollution_risk, over_blocked, na}.

[recall(거짓음성)을 반드시 본다]
- title=null / work_resolution in {none, unresolved} 인 행도 검수한다. 본문/댓글/이미지에 식별 가능한 작품 단서가 있는데 파이프라인이 놓쳤으면 under_resolved_false_negative.
- 단, demote-but-preserve(promotion_blocked/hold_unresolved로 candidate를 보존)는 정밀의 "성공"이지 miss가 아니다. candidate가 전혀 생성되지 않은 경우만 진짜 recall 실패(candidate_generation_miss)로 본다.

disagreement_type enum (1개 선택):
none, under_resolved_false_negative, wrong_work, garbage_title, over_resolved, wrong_relevance, wrong_discussion_type, cross_media_or_famous_mismatch, title_noisy_ocr, uncertain

우선순위(동시 충족 시):
garbage_title > cross_media_or_famous_mismatch > over_resolved > wrong_work > title_noisy_ocr > under_resolved_false_negative > wrong_relevance > wrong_discussion_type > uncertain

resolution_label (judge 최종 처분):
ACCEPT(근거 충분, lint/경계 위험 없음) / HOLD(작품은 그럴듯하나 hard anchor·heretic_url·검색정답성 부족) /
REPROCESS(증거는 있으나 reason이 과대단정·모순 → 재판정/재검색) / REJECT(명백한 오매칭/오관련/garbage) / INFO_MISSING(원천·증거 부족으로 판단 불가).
ACCEPT 게이트는 엄격하다: official_title이 맞아도 hard anchor·heretic_url·검색정답성이 부족하면 ACCEPT가 아니라 HOLD다.

[HOLD 원인 기록 (필수)] resolution_label이 HOLD 또는 REPROCESS면 왜 ACCEPT가 아닌지 hold_reason을 아래 enum에서 1개 고른다(ACCEPT/INFO_MISSING/REJECT이면 "na" — REJECT의 원인은 disagreement_type가 담으므로 hold_reason=na):
heretic_url_null(해소했는데 url 없음) / search_only_resolved_title(본문 단서 없이 검색 스니펫만) / ocr_only_title(OCR 단독, 본문/플랫폼 미재확인) /
registry_alias_only(등록약칭·slang 단독) / weak_source_tier(community/llm_only/listing 근거) / generic_abstract_title_collision(일반·추상 제목 우연일치) /
context_only_late_rescue(no-work 글을 늦은 검색·약칭으로 되살림) / comment_attribution_unverified(미검증 댓글 귀속이 유일 다리) /
memory_query_no_quote_anchor(인용 anchor 없는 memory-query) / conflicting_or_multi_candidate(경합·다작품 후보 잔존) /
boundary_needs_human(multi_work/adjacent/trope/author_talk 경계) / reason_evidence_mismatch(official_urls>0인데 heretic_url=null 등 모순) / other / na.
이 hold_reason 분포가 보고서의 정밀 개선 우선순위 목록이 된다(§6.3).

recommended_action enum:
no_action / re_search / re_judge / re_run / human_review / slang_db_review / docs_issue
(no_action=증거가 verdict를 직접 뒷받침·lint 없음. re_search=근거 약함/degraded/resolved-without-url. re_judge=증거는 있으나 reason 과신·모순.
 re_run=런타임이 결과 신뢰를 깸. human_review=multi_work/adjacent/trope/author_talk 경계·미검증 댓글 단독 단서·인용없는 memory-query. slang_db_review=alias 저장/차단/오염 문제. docs_issue=규칙/문서 갱신 필요.)

severity: high(locked/High resolved 확정 오매칭·garbage·over_resolved·cross_media 또는 명백한 거짓음성) / med(영향 있는 중간 오류·모호 거짓음성·Medium 이하 오매칭·관련성/문맥 오류) / low(경계적/사소).

과대단정 금지 — 불확실하면 uncertain + INFO_MISSING + 보수적 severity.
```

### 4.3 출력 스키마 (D5 확정 — 백엔드별 2단)

스키마는 두 단계로 나눈다(D5=B). 로컬 vLLM(Gemma-4-26B-A4B, NVFP4 양자화 MoE/활성 ~4B)에는 enum 슬롯이 적은 **LEAN(§4.3a)** 을 시키고,
나머지 결정적으로 도출 가능한 필드는 **결정적 post-processor**가 LEAN에서 채워 **FULL(§4.3b, canonical)** 로 materialize한다.
Claude/GPT-Pro는 FULL을 직접 낸다. 어느 경로든 **영속 산출물 `verdicts_NNN.json`은 항상 §4.3b FULL 16필드** 다.

#### 4.3a LEAN LLM OUTPUT (로컬 vLLM / Gemma-4-26B-A4B가 직접 내는 객체)
모델은 **다음 11필드만** 반환한다(나머지는 §4.3b post-processor가 결정적으로 채운다):
`post_id, agree, disagreement_type, resolution_label, hold_reason, search_evidence_grade, official_detail_url_match, web_reverify_needed, claude_take, note, improvement_idea`.
선택적으로 모델이 추가로 낼 수 있는(MAY) 필드(있으면 post-processor가 우선 반영, 없으면 규칙으로 derive):
`severity_hint, slang_verdict_override, recommended_action_hint`.
```json
{
  "post_id": 11718077,
  "agree": true,
  "disagreement_type": "none",
  "resolution_label": "ACCEPT",
  "hold_reason": "na",
  "search_evidence_grade": "Strong",
  "official_detail_url_match": true,
  "web_reverify_needed": false,
  "claude_take": "독립 판단 한국어 1문장",
  "note": "근거 한국어 1~2문장, 웹근거 필요 시 web_unverified 명시",
  "improvement_idea": "일반화 가능한 파이프라인 개선 아이디어 또는 빈 문자열"
}
```
불변식(LEAN): `agree==true ⇔ disagreement_type=="none"`. `hold_reason`이 비-na이면 반드시 `resolution_label in {HOLD, REPROCESS}`(즉 ACCEPT/INFO_MISSING/REJECT은 hold_reason=="na"; HOLD/REPROCESS는 §4.2 enum의 비-na 원인 1개 필수).
한 파일에 유효한 JSON 객체 한 개만, 코드펜스 금지.
`claude_take`와 `note`는 한국어 자연어를 기본으로 한다. 영어 enum·URL·작품명은 그대로 둘 수 있지만, 판정 사유는 "검색근거가 강하고 공식 상세 URL 제목이 일치하므로 수용"처럼 사람이 읽는 한국어 문장으로 적는다. 내부 reasoning chain을 길게 쓰지 말고, 결론을 뒷받침하는 관찰만 남긴다.

#### 4.3b FULL RECORD (canonical, 영속, 16필드)
아래 16필드 객체가 **표준·영속 verdict**다. Claude/GPT-Pro는 이 객체를 직접 낸다. vLLM 경로는 §4.3a LEAN을 결정적 post-processor로 이 형태로 materialize한다.
```json
{
  "batch": 0,
  "verdicts": [
    {
      "post_id": 11718077,
      "agree": true,
      "disagreement_type": "none",
      "judge_seed_group": "none",
      "likely_correct": "pipeline",
      "resolution_label": "ACCEPT",
      "hold_reason": "na",
      "search_evidence_grade": "Strong",
      "official_detail_url_match": true,
      "web_reverify_needed": false,
      "severity": "low",
      "recommended_action": "no_action",
      "slang_verdict": "ok",
      "claude_take": "독립 판단 한국어 1문장",
      "note": "근거 한국어 1~2문장, 웹근거 필요 시 web_unverified 명시",
      "improvement_idea": "일반화 가능한 파이프라인 개선 아이디어 또는 빈 문자열"
    }
  ]
}
```
불변식(FULL): 입력 개수 == 출력 개수(누락 금지). `agree==true ⇔ disagreement_type=="none"`.
`judge_seed_group`은 `seed_group(disagreement_type)` 결과(recall/precision/hygiene/none)와 일치해야 함(집계 시 재검증).
한 파일에 유효한 JSON 한 개만, 코드펜스 금지.
FULL verdict의 `claude_take`/`note`도 같은 한국어 사유 계약을 따른다. GPT/Claude-Pro가 직접 FULL을 쓰는 경우에도 모든 post_id에 사유가 있어야 하며, post-processor 또는 rows renderer는 이 사유를 `rows/full_post_judge_rows_pNN.md`의 `LLM 판단 사유(한글)` 열로 전수 materialize한다.

#### 결정적 post-processor (나머지 필드 derive)
vLLM 경로는 LEAN 객체 + precomputed(§2.3) + identity로 아래 5필드를 **LLM 없이** 결정적으로 채워 §4.3b를 만든다.
정확한 도출:
- `judge_seed_group` = `candidate_audit.seed_group(disagreement_type)`, 단 `'unseeded'` → `'none'`으로 치환.
- `likely_correct` = `disagreement_type=="uncertain"` 이면 `'both_unclear'`, 아니면 (`agree` 이면 `'pipeline'` 아니면 `'claude'`).
- `slang_verdict` = precomputed `deterministic_slang_verdict`(§2.3) 사용. LLM의 `slang_verdict_override`는 **있고 valid이며 그 행이 `precomputed.slang_axis_route=="llm"` 일 때만** 우선 반영.
- `severity` = `max(severity_hint(있으면), rule_floor)`. `rule_floor`: precision 그룹 type이 locked/High resolved에서 발생 → `'high'`; recall miss/명백한 false-negative → `'med'`; 그 외 → `'low'`.
- `recommended_action` = `recommended_action_hint`(있으면), 없으면 `(resolution_label, hold_reason)` 조합의 규칙 기본값.

이 post-processor는 `tools/run_agbrowse_llm_judge.py`의 `normalize_payload` 패턴(키 정규화·검증)과 `candidate_audit.seed_group`을 **재사용**한다 —
그 결과 `judge_seed_group`은 구성상 invalid이 될 수 없다(invalid-by-construction-impossible).

---

## 5. 정밀 적대적 재검증 프롬프트 (그대로 사용)

정밀 verify 풀(자동수용 ACCEPT + High/Medium resolved, §3 step 5)에 대해 1차 판정(`first_pass`)을 첨부해 호출, `vverdicts_NNN.json`에 §4.3b 스키마로 쓴다.

### 5.1 system — §4.1과 동일.

### 5.2 criteria (verbatim)
```
너는 회의적(adversarial) 3-lens 회의자다. 아래 항목들은 1차 judge가 ACCEPT(또는 자동수용)한 작품 해소이며, 일부는 실제로 틀렸다.
잘못 식별된 작품에 신뢰가 부여되면 정밀 오류이자 slang_db 오염원이다. 자동수용의 신뢰도를 엄격히 재검증하는 것이 목적이다.

각 항목에는 1차 판정(first_pass: resolution_label/disagreement_type/search_evidence_grade/note)이 함께 주어진다.
그 판정을 그대로 믿지 말고, 특히 first_pass.resolution_label=="ACCEPT" 항목에 대해 **이 매칭이 틀렸을 가능성을 적극적으로 찾아라.**
조금이라도 제품 동일성·검색 정답성·hard anchor가 불확실하면 ACCEPT를 주지 말고 HOLD/REPROCESS/REJECT로 내려라.

한 응답 안에서 다음 3개 lens를 각각 검토한 뒤 **가장 보수적 결론을 채택**하라:
- lens1 작품동일성: 이 제목이 정확히 이 작품인가(다른 작품/벤더·부분문자열·오타 변형 아닌가).
- lens2 검색존재성: official_detail/novel_platform 상세 URL이 실재하고 그 페이지 제목이 official_title과 일치하는가.
- lens3 cross-media/famous: 게임·웹툰·애니·고전·유명작 오인이 아닌가.

웹검색 필수 — 이 풀은 같은 payload 재독만으로는 정밀 오류의 59%를 못 잡는다.
official_title 실존·상세페이지 제목일치를 반드시 웹검색으로 확인하고, 못 하면 web_reverify_needed=true로 표기하라.

판정 축은 §4와 동일(A 관련성, B 작품 정확성, C 검색 정답성, D slang). 특히:
- official_title이 맞아도 heretic_url=null·search_only·OCR-only·등록약칭 단독이면 ACCEPT가 아니다(HOLD).
- 검색근거가 official_detail/novel_platform 상세 URL의 제목 일치가 아니면 search_evidence_grade를 Strong으로 올리지 마라.
- no-work 단조성: 사회적 푸념/장르 잡담/문맥-only 글을 늦은 검색·약칭·BatchContext로 특정 작품으로 되살리면 정밀 오류다.

출력은 §4.3b 스키마와 동일하되 note 앞부분에 1차와 달라졌으면 왜 바꿨는지(예: "downgrade: heretic_url=null, search_only")를 명시한다.
```

### 5b. 재현 적대적 재검증 프롬프트 (그대로 사용)

재현 verify 풀(§3 step 5b, `rhold_batch_NNN.json`)에 대해 호출, `rhold_vverdicts_NNN.json`에 §4.3b 스키마 + `changed_from_first`로 쓴다.

#### 5b.1 system — §4.1과 동일.

#### 5b.2 criteria (verbatim)
```
이 행들은 파이프라인이 none/unresolved/hold로 떨어뜨린 행이며 일부는 식별 가능한 작품을 놓친 false-negative다.
본문/댓글/이미지 OCR/약칭/캐릭터명/작가 신작 단서로 작품이 식별 가능한지 적극적으로 재탐색(웹검색 권장)하라.
식별되면 disagreement_type=under_resolved_false_negative + resolution_label=REPROCESS + recommended_action=re_search/re_run로 처분한다.
단 candidate가 보존된 promotion_blocked/hold_unresolved는 정밀 성공이니, candidate가 전혀 없을 때만 candidate_generation_miss로 표기한다.
과대구제 금지 — 단순 푸념/장르 잡담을 늦은 검색으로 작품화하지 마라.
출력은 §4.3b 스키마 + changed_from_first(1차와 무엇이 바뀌었는지) 1필드를 추가한다.
```

---

## 6. 집계 · 해석 · 의사결정 기준

보고서 `full_post_judge_report.md`는 다음을 **분리**해 싣는다(영어 enum + 한글 병기, 전수, top-N 금지).

**표 등급(D3=B 확정 — 필수 6표 + 보조 4표)**: 보고서는 아래 6개를 **필수표(T1~T6)** 로 싣되, 액션을 직접 굴리는 **T2~T3~T4를 보고서 최상단**에 둔다. 보조 4표는 삭제하지 않고 하위 서브섹션으로 **강등**해 유지한다(SCAN_RESULT_REVIEW_GUIDE §13 게이트는 random/high-risk + slang + 결정적 cross-tab을 요구하므로 보조표를 지운다는 뜻이 아니다).
- **필수 6표**: **T1** 커버리지/무결성(§6.1) · **T2** hold_reason 정밀-fix 우선순위(§6.3) · **T3** 재현손실(§6.4) · **T4** 정밀↔재현 balance(§6.8) · **T5** problem×severity(§6.10 상단 교차표) · **T6** improvement_idea 클러스터(§6.10 하단).
- **보고서 권장 배치 순서**: T1 → **T2 → T3 → T4** → T5 → T6 → (보조표들).
- **보조 4표(강등, 유지)**: 관련성 축 A(§6.2) · slang 축 D(§6.5) · 적대적 일치율(§6.6) · candidate_audit 결정적 대조(§6.7).

6.1 **[T1 — 필수] 커버리지/무결성**: input(processed)=2246, judged, missing, bad_files, pending(re_run)=23. `missing==0` 아니면 보고서 미완성.

6.2 **[보조] 관련성 축(축 A)**: is_relevant=true(501) / false(1745) 분포 대비 judge resolution_label·disagreement_type 분포.
- wrong_relevance / wrong_discussion_type 건수와 대표 post_id.

6.3 **[T2 — 필수·최상단] 작품 해소 정밀(precision, 축 B+C)** — `work_resolution=="resolved"`(351) 기준:
- ACCEPT 비율 = ACCEPT / resolved. 정밀 오류 = precision 계열(wrong_work/over_resolved/cross_media_or_famous_mismatch/garbage_title) 건수(+severity high 분리).
- 검색 정답성 분포: resolved 중 search_evidence_grade {Strong/Medium/Weak/Missing}, `official_detail_url_match` {true/false/null}, **search_only_resolved_title 의심**(Weak/Missing & official_detail_url_match!=true) 건수, **heretic_url=null while resolved** 건수.
- **T2 본표 = hold_reason 분포(정밀-fix 우선순위)**:
  - 모수 = `resolution_label in {HOLD, REPROCESS}`.
  - 컬럼 = `hold_reason(enum+한글) | count | pct_of_hold | severity_high | resolved중건수 | 대표post_ids(≤3) | target_lever`.
  - 정렬 = count desc. 이 정렬이 곧 **정밀 fix 우선순위**다(가장 많은 원인부터 일반화 가능한 게이트/프롬프트 개선으로 연결).

6.4 **[T3 — 필수·최상단] 작품 해소 재현(recall, 축 B)** — 재현손실 표:
- 모수 = `title=null/none/unresolved` + hold 계열.
- 행(rows) = `under_resolved_false_negative`(과소해소·거짓음성) · `candidate_generation_miss`(candidate 자체가 없는 진짜 recall 실패 = 최악) · `hold_unresolved`(보존됨 = miss 아님, 분리표기).
- 컬럼 = `bucket | count | severity | 대표post_ids | candidate_ledger_status 내역`.
- **`candidate_generation_miss`와 `hold_unresolved`를 합산 금지**(보존된 hold는 정밀 성공이지 손실이 아니다). under_resolved_false_negative는 가장 큰 손실 축(JUDGE3905 기준치 644 참고).
- demote-but-preserve(promotion_blocked/hold_unresolved)는 정밀 성공으로 집계하고 miss로 세지 않는다.

6.5 **[보조] slang 정당성(축 D)**: pollution_risk/over_blocked/"store=true이지만 pollution_risk" 집계는 **`slang_axis_route=="llm"` 행만** 센다(이 런 ~94건).
`deterministic_na` 행의 na는 자동 채움이며 **LLM 판정이 아니므로** 분모/오류 집계에 섞지 않는다. slang_verdict {ok/pollution_risk/over_blocked} 분포 + store_in_slang_db=true인데 pollution_risk인 건수(우선 검수)를 LLM 모수 기준으로 보고한다.

6.6 **[보조] 적대적 일치율(두 풀 분리)**: 1차↔재검증 일치율(낮으면 판정 불안정 신호)을 두 풀로 나눠 보고한다.
- **정밀 풀**(§5/vverdicts): ACCEPT → stricter downgrade(ACCEPT→HOLD/REPROCESS/REJECT) 수.
- **재현 풀**(§5b/rhold_vverdicts): HOLD/none → REPROCESS upgrade(false-HOLD 구제) 수.
두 풀 결과를 §6.8 양면 밸런스 표에 모두 입력한다(합산 금지·분리 유지).

6.7 **[보조] 결정적 대조(candidate_audit cross-tab)**: `candidate_audit` shadow `candidate_ledger_status` 분포 vs 파이프라인 라벨 분포 vs judge resolution_label 매핑(불일치 = lint 누락/판정 흔들림).

6.8 **[T4 — 필수·최상단] 양면 밸런스 가드레일**: 정밀 위반(precision 계열 건수·high) ↔ 재현 위반(recall 계열 건수·candidate_generation_miss)을 **한 표에 나란히** 둔다.
§6.6의 정밀 풀 downgrade 수와 재현 풀 upgrade(false-HOLD 구제) 수를 이 표에 함께 입력한다(합산 금지·열 분리).
지침: "candidate-preservation recall WIDE, official_title promotion NARROW." 정밀을 위해 demote할 때 candidate는 절대 삭제하지 않았는지 확인.

6.9 **action queue**: recommended_action별 집계(no_action/re_search/re_judge/re_run/human_review/slang_db_review/docs_issue) + 우선순위(high severity 먼저) + post_id.

6.10 **문제점 & 개선 아이디어** — 두 필수표로 나눈다:
- **[T5 — 필수] problem×severity 교차표**: `disagreement_type × severity` 교차표로 **체계적 실패 패턴**을 도출한다.
- **[T6 — 필수] improvement_idea 클러스터**: verdict.improvement_idea를 아래 5-step 결정적 알고리즘으로 클러스터링한다(post_id 하드코딩 금지, top-N 금지):
  1. `improvement_idea`가 비어있지 않은 verdict만 수집.
  2. `(disagreement_type, judge_seed_group, hold_reason)` 키로 그룹핑 + idea 텍스트 정규화(소문자·공백 정리).
  3. backing post_id ≥ 2인 그룹만 클러스터로 채택. 단발(post_id 1개)은 §7 이슈후보로만 넘긴다.
  4. lever 매핑: precision → `candidate_audit.py`/`agentic_pipeline.py`; recall → `agentic_pipeline.py`+`prompt_router.py`; hygiene → `prompt_router.py`/`output_consistency_lint`; slang → `slang_db.py`.
  5. 컬럼 = `cluster_id | 요약 | seed_group | backing_post_ids(전수, top-N 금지) | target_lever(파일:함수) | 기대효과 | 근거표(T2/T3) 참조`.

6.11 **게이트(0.7 분리 유지)**: run 무결성(GO/REVIEW/NO-GO) / semantic 품질(REVIEW-LOCKED 유지) / full-scan approval(false 유지). 이 판정으로 approval 주장 금지.

### 6.1′ 반드시 구분할 것 (naive judge가 놓치는 함정)
- **non-null official_title ≠ 정답.** 파이프라인은 과도 시도하며, rank3 게이트가 `locked→False`로 강등해도 official_title/work_resolution=resolved는 보존한다(`agentic_pipeline.py:36225`). 카탈로그로 독립 검증하라.
- **locked=False ≠ unresolved.** hard anchor(matched_url/본문 제목/이미지 명시 제목/큐레이티드 alias)가 없을 뿐, resolved_recall_anchor=true로 재현 보호된 정당 해소일 수 있다.
- **demote-with-candidate = 정밀 성공**(miss 아님). cross_media/famous/garbage seed의 올바른 결과는 promotion_blocked + candidate 보존이다.
- **recall은 resolved 행만 보면 안 보인다.** 최대 손실축은 title=null로 흘려보낸 under_resolved_false_negative다. title=null/is_novel_related 행을 반드시 본다.
- **search_only_resolved_title**: 본문에 작품 단서가 없고 검색 스니펫만으로 세운 제목은 맞아도 hard 정밀 실패(단, 본문 직접 단서 + 공식 근거가 함께면 review_only로 강등).
- **OCR 제목 ≠ 본문 제목.** title_in_post=false + image_ocr면 anchor_type=image 유지, OCR 단독으로 title-lock 금지. 충돌 시 HOLD(ocr_explicit_title_unresolved).
- **등록 약칭/SLANG/KNOWN_* = 재현 힌트일 뿐 확증 아님.** 독립 hard anchor 없으면 Medium/HOLD.
- **댓글 author/IP 귀속 미검증**(author_match_unverified): 익명 댓글을 글쓴이 발화/작품 anchor로 승격 금지. 그게 유일한 다리면 hard blocker.
- **official_urls>0 인데 heretic_url=null** = 모순(reason_evidence_state_mismatch). 제목만 고치고 url/evidence 미갱신도 모순.
- **일반/추상 제목 우연일치**(집착/의존/피폐 등) ≠ Strong. 이미지 OCR 캐릭터/작가/회차/플랫폼 직접 일치 필요.
- **CVE식 "0건=실패" 착시 금지의 본 도메인판**: resolved=0인 noise/off_topic 글은 정상이다. 품질은 "붙은 해소가 옳은가(precision)"와 "놓친 해소가 있는가(recall)"로만 본다.

---

## 7. 실행 · 오케스트레이션 주의점

- **배치 크기 — driver는 post 수가 아니라 per-post enum 슬롯 수**: 한 배치에 직렬화되는 enum 슬롯 총량이 소형모델 실패(절단·invalid enum)를 좌우한다(post 수 자체가 아님).
  - **vLLM Gemma-4-26B-A4B**: LEAN 11필드(§4.3a) + 결정적 post-processor, **BATCH=5**, split-on-failure 유지. (모델 변경 노트 2026-06-18: 운영 모델이 E4B → `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4`로 교체됨. 더 강한 MoE이므로 FULL 스키마/더 큰 BATCH 수용 가능성 있으나, enum 안정성은 재측정 후 상향 — 기본은 보수적으로 LEAN/BATCH=5 유지.)
  - **Claude**: FULL 16필드(§4.3b), **BATCH=15**.
  - **GPT-Pro**: FULL, **BATCH=5**.
  - **vLLM client는 `response_format=json_object`만 강제(enum 미강제)** → enum 유효성은 프롬프트 + `validate` + `normalize` + `fallback` + `split`로 보장한다. LEAN이 singles율(배치 분할 빈도)·CHAR_CAP 절단 위험을 낮춘다.
- **`web_reverify_needed`는 derive하지 않는다**: vLLM 경로에서 **LLM-set 필드로 유지**한다. 그 경로는 네이티브 웹이 없으므로, 모델이 이 필드로 행을 self-flag해 Codex/Claude 타깃 웹 패스로 회수시킨다.
- **누락 0 강제**: 병합 후 `Counter(judged_ids)`가 입력과 동일한지 검증. 누락 배치 번호만 재실행.
- **재시작/멱등**: 유효 verdicts 파일(스키마·post_id 집합 일치)은 skip. 같은 배치 재판정 시 덮어쓰기.
- **JSON-only / 루프 감지**: 모델이 코드펜스·표를 붙이거나 누적-char 캡(`LLM_POST_JSON_*`, 131000)으로 잘릴 수 있음. `extract_json_object`(코드펜스/중괄호 추출)·`normalize_payload`(키 오타 교정)·`validate_verdict`(불변식)·fallback(uncertain) 4단을 둔다 — `tools/run_agbrowse_llm_judge.py`의 동명 함수 재사용.
- **민감 표현 치환**(0.8): 배치 직렬화 직전 `redact_sensitive_payload`.
- **인자 직렬화 함정**: 외부 워크플로/스크립트에 JSON 인자를 넘길 때 문자열로 도착할 수 있음 — 수신 측 `typeof==='string'`이면 `JSON.parse` 가드.
- **웹검색(채택) — 백엔드별 경로(D4 확정)**: 판정 전반 웹검색 허용. **Codex 에이전트·Claude Workflow 에이전트는 네이티브 웹검색**을 그대로 쓴다.
  **로컬 vLLM 순수 루프(Gemma-4)는 자율 웹검색 능력이 없다**. 그러나 §0.1a대로 **파이프라인의 검색 클라이언트(`MCPClient`, 라이브 `http://127.0.0.1:3333`)를 judge 루프에 직접 연결**하면
  로컬·무료로 웹증거를 모델에 주입할 수 있다(tool-injection). 두 가지 운용안:
  - **(권장·전수) Codex 단독 웹 전수 패스**: 2246행 전부를 Codex 에이전트가 네이티브 웹으로 판정(§8). {웹검색 전반·Claude한도무관·Codex실행·전수} 4조건을 단일 경로로 충족. 가장 단순.
  - **(대안·로컬우선 하이브리드) vLLM+검색클라이언트 전수 → 소형 웹-재검증 패스**:
    1단계 — 2246행 전부를 로컬 vLLM으로 판정하되, 각 행마다 루프가 `MCPClient.search(official_title 또는 핵심 alias)`를 1~2회 호출해 결과를 projection의 `search_evidence`에 합쳐 모델에 준다(검색근거 부족하면 `web_reverify_needed=true`).
    2단계 — `resolution_label in {ACCEPT}` 또는 `work_resolution=="resolved"` 중 **`search_evidence_grade in {Missing, Weak}` 이거나 `official_detail_url_match != true`** 인 행만 작은 큐로 모아(이 런 기준 모수 = resolved 351 중 heretic_url 부재 72 + weak-grade subset ≈ 합쳐 **~70–150행**) Codex(또는 한도 여유 시 Claude)의 네이티브 웹으로 §5 적대적 재검증. 비용을 2246 → 수백분의 일로 압축.
  - vLLM 자율 tool-call은 불가하므로, 로컬 경로는 반드시 **루프가 질의를 만들어 evidence를 주입**하는 형태여야 한다. 보고서에는 어느 경로를 썼고 어떤 행이 web_reverify되었는지 명시한다.
  - **검색 클라이언트 헬스체크(필수, 로컬/하이브리드 경로)**: 루프 시작 전 `MCPClient().health_check(include_search=True)["ok"]==True` 확인. degraded면 `MCP_ENDPOINTS`에 살아있는 shard를 채우거나(failover 내장) 그 행을 `web_reverify_needed=true`로 미뤄 Codex 패스로 넘긴다.
- **결정적 사전계산(채택)**: precomputed는 candidate_audit로 LLM 없이 계산되므로 vLLM/Codex/Claude 모든 경로에서 동일하다. 판정자는 이를 출발점으로 확인·override만 한다.
- **읽기 전용**: `--slang-db off`. 결과/슬랭 DB write-back 금지. 파이프라인 재실행은 별도 승인 단계.
- **pending 23건**: 미처리 → `re_run` 큐로만. 판정/ACCEPT 금지.
- **게이트 분리**(0.7): run 무결성 GO ≠ semantic 승인 ≠ full-scan approval. random_control과 high-risk_expansion 오류율 합산 금지.
- **대용량 파일**: 결과 JSON은 ~96만 라인(~58MB). 전체를 메모리에 한 번에 올리되(2246행은 가능) 보고서 md는 페이지(300행)로 분할.
- **Codex subagent 병렬 ≠ `expert_main.py --parallel`**: 판정 리뷰 병렬성과 파이프라인 실행 병렬성은 별개.

### 7.1 Codex subagent fan-out (검색/LLM judge 권장)

단일 Codex 에이전트의 네이티브 웹검색·LLM judge probing이 오래 걸릴 때는 batch 파일 경계로 Codex subagent를 팬아웃한다. 기준: 전수 first-pass, resolved/ACCEPT 정밀 verify, recall 15% verify처럼 웹 확인 대상이 수십 batch 이상이거나 30분 이상 걸릴 것으로 보이면 분할한다. 소수 canary, Slice, Aggregate는 단일 coordinator가 맡는다.

분할 단위는 `S/batches/batch_NNN.json`, `S/verify/vbatch_NNN.json`, `S/verify/rhold_batch_NNN.json` 파일이다. 한 batch를 여러 subagent가 동시에 쓰지 않는다. 느린 batch는 재슬라이스해 작은 batch로 다시 배정한다.

역할:
- Coordinator: Slice를 1회만 수행하고 `expected_post_ids`, batch 목록, pending/re_run 목록을 고정한다. subagent별 비중복 batch range를 배정하고, 공용 산출물(`_verdicts_merged.json`, `_verdicts_final.json`, report, rows)은 coordinator만 병합/작성한다.
- First-pass judge subagent: 배정된 `batch_NNN.json`만 읽고 §4 프롬프트 + §4.3b FULL 스키마로 `verdicts_NNN.json`만 쓴다. 네이티브 웹검색으로 `official_title` 실제 존재, 상세페이지 제목 일치, `heretic_url`/공식 URL 정합성을 확인하고 결정적 URL을 `note`에 남긴다. `claude_take`/`note`는 모든 post에 한국어 판단 사유를 남긴다.
- Precision verify subagent: 배정된 `vbatch_NNN.json`만 읽고 §5 기준으로 `vverdicts_NNN.json`만 쓴다. ACCEPT/resolved High·Medium의 과해소, wrong_work, search_only_resolved_title을 보수적으로 잡는다.
- Recall verify subagent: 배정된 `rhold_batch_NNN.json`만 읽고 §5b 기준으로 `rhold_vverdicts_NNN.json`만 쓴다. 놓친 작품 재탐색에 집중하되 `hold_unresolved`와 `candidate_generation_miss`를 합산하지 않는다.
- Merge/audit: 모든 verdict 파일을 읽어 schema, enum, post_id set, duplicate, missing, bad_files를 검증한다. 실패 batch만 재배정한다.

각 subagent 산출물은 기존 driver와 호환되도록 top-level `{ "batch": NNN, "verdicts": [...] }`를 유지한다. 선택 메타는 `_subagent_meta` 아래에만 둔다: `subagent_id`, `phase`, `assigned_files`, `input_post_ids`, `output_post_ids`, `missing_post_ids`, `duplicate_post_ids`, `web_sources_checked`, `status`.

Codex-native web judge 전용 산출물은 coordinator가 `tools/codex_native_web_judge_ingest.py`로 병합한다. 사용 절차:
- subagent가 반환한 JSON을 UTF-8-safe 경로(`apply_patch`로 만든 임시 JSON 등)로 저장한다. PowerShell literal write는 한국어를 `???`로 치환한 전례가 있으므로 쓰지 않는다.
- `python tools/codex_native_web_judge_ingest.py --root S --raw tmp_native_web_raw_NNN.json --subagent NAME --subagent-path AGENT_ID`를 실행한다.
- helper는 `subagent_returns/*_batch_NNN_raw.json`, `verdicts/verdict_NNN.json`, `report/codex_native_web_judge_progress.json`, `report/rows/codex_native_web_judge_rows_pNN.md`를 재생성한다.
- helper의 보정 범위는 작은 schema drift에 한정한다: `likely_correct=true/false`, 빈 `hold_reason`, accepted nonwork row의 `REJECT` label. 작품명 판단 자체는 바꾸지 않는다.

강제 불변식:
- 파일별 `set(verdict.post_id) == set(batch.posts.post_id)`.
- 전체 first-pass 병합 후 `judged == processed`, `missing == 0`, `bad_files == []`.
- pending은 `_pending_rerun.json`에만 남기고 판정/ACCEPT하지 않는다.
- off-topic/noise/정보부족 행도 생략하지 않는다. 웹 확인이 실패하면 행을 빠뜨리지 말고 `INFO_MISSING` 또는 `REPROCESS`, `web_reverify_needed=true`, `recommended_action=re_search|human_review`로 schema-valid verdict를 쓴다.
- duplicate post_id, batch 범위 밖 post_id, FULL schema 누락, enum 오류는 merge 실패로 보고 해당 batch를 재실행한다.
- LLM judge에는 `reason_lines`를 넣지 않고, 작품명 생성 금지·slang_db write-back 금지를 유지한다.
- 장기 web probe는 timeout/retry/env를 명시한다. 예: `MCP_CLIENT_SEARCH_TIMEOUT_SEC=8`, `MCP_CLIENT_SEARCH_MAX_RETRIES=0`, `MCP_CLIENT_MAX_ENDPOINTS_PER_SEARCH=1`로 느린 shard가 전체 judge를 붙잡지 않게 한다. timeout으로 근거가 부족한 행은 `web_reverify_needed=true` 또는 `re_search`로 보낸다.

---

## 8. Codex 한 줄 지시 예시 (웹검색 경로 명시 — D4 확정)

**권장(전수 웹): Codex 5.5 native web judge.** Codex는 API key·agbrowse·Claude 한도와 무관하게 내장 web search/open을 쓸 수 있으므로 {post 원문 직접 이해·웹검색·전수·한국어 사유} 조건을 단일 경로로 충족한다. 단, 배치가 많거나 검색/LLM judge가 30분 이상 걸릴 것으로 보이면 §7.1의 subagent fan-out을 기본 운영으로 사용한다.

```
docs/devs/FULL_POST_JUDGE_RUNBOOK.md 의 §3 절차를 순서대로 수행하라.
대상은 out/expert_result_20260616_224555_632905.json(processed 2246). §2.3 컴팩트 projection으로 batch_NNN.json(BATCH=5)을 만들고,
슬라이스 시 §3 step(1b)대로 candidate_audit로 precomputed(official_search_supports_title·*_lint·slang_audit 라우팅 등)를 LLM 없이 채워라(축 C·D 출발점).
§4 프롬프트·§4.3b FULL 스키마로 배치당 1회 판정하라(BATCH=5). 판정 본체는 너(Codex)가 직접 수행하며, [축 C] 검색 정답성은
**너의 네이티브 웹검색으로 official_title 실제 존재·상세페이지 제목 일치를 확증/반증**하고 결정적 URL을 note에 적어라(작품명 생성 금지).
[축 D] slang은 precomputed.slang_axis_route=="llm"인 행만 판정(나머지는 deterministic_slang_verdict로 na 확정).
(로컬 vLLM은 보조: 대량 1차 분류가 필요하면 http://10.20.0.101:8000 / bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4(server vllm)로 돌리되,
 vLLM은 자율 웹검색이 없으므로 검색 정답성 행은 web_reverify_needed=true로 표기해 너의 웹 패스로 회수하라.)
병합 후 judged==2246·missing==0을 검증하고(모든 verdict enum 정규화+검증, REJECT의 hold_reason=na 허용), candidate_audit로 shadow 재버킷하라.
그다음 두 적대적 패스를 돌려 오버레이하라: (정밀) ACCEPT/High·Medium resolved에 §5 3-lens 재검증(웹 확인 필수) → vverdicts; (재현) §3 step(5b)의 hold/unresolved 15% 층화표본에 §5b 재검증(놓친 작품 웹 재탐색) → rhold_vverdicts.
LLM은 판정자로만 쓰고(생성 금지), 파이프라인 reason_lines는 judge에 넣지 말며, slang_db write-back은 하지 마라.
완료 후 §6 기준으로 관련성·작품 정밀(검색 정답성 포함)·재현(거짓음성)·slang 정당성·적대적 일치율·action queue·문제점/개선 아이디어를
full_post_judge_report.md + 전수 rows/full_post_judge_rows_pNN.md 로 산출하라. rows dump에는 모든 post별 GPT/Claude/vLLM judge 판단 사유를 한국어로 적고, ACCEPT/none 행도 왜 수용했는지 설명하라. semantic 품질은 REVIEW-LOCKED, full-scan approval은 false로 유지하라.
```

**대안(로컬우선 하이브리드): vLLM+파이프라인 검색클라이언트 전수 → 소형 웹-재검증.** Claude/Codex 호출을 ~70–150행으로 압축하고 싶을 때.

```
1) 슬라이스 시 §0.1a의 검색 클라이언트로 각 행 evidence를 보강한다(루프가 질의 생성):
   from llm_batch.search.client import MCPClient
   mcp = MCPClient()                      # 기본 http://127.0.0.1:3333, MCP_ENDPOINTS로 shard pool 지정
   assert mcp.health_check(include_search=True)["ok"]   # degraded면 그 행은 web_reverify_needed=true로 미룸
   # official_title(또는 핵심 alias)로 1~2회 검색 → results를 projection.search_evidence에 머지
   ev = mcp.search(official_title, num_results=8, purpose="judge_title_anchor_probe")["results"]
2) 2246행 전부 로컬 vLLM(§2.2)로 §4 판정. 검색근거 불충분이면 web_reverify_needed=true.
3) resolved 중 (search_evidence_grade in {Missing,Weak}) 또는 (official_detail_url_match!=true) 행만 큐로 모아
   (이 런 기준 ~70–150행) Codex 네이티브 웹으로 §5 적대적 재검증 → 오버레이.
나머지 멱등·누락0·게이트 분리는 권장 경로와 동일.
```

---

## 9. ultracode Workflow 형태 (Claude 엔진)

Claude 사용량 여유가 있을 때는 동일 절차를 Workflow로 팬아웃한다: `tools/workflows/full_post_judge.workflow.js`.
페이즈는 **Slice → Judge → Verify → Aggregate**:
- **Slice**: 1 에이전트가 결과 파일을 읽어 §2.3 projection으로 `S/batches/batch_NNN.json`을 쓰고 batch 목록·pending을 반환.
- **Judge**: 배치별 파이프라인 — 각 judge 에이전트가 batch를 읽고 §4 프롬프트로 판정(Claude는 §4.3b FULL 직접 출력; 필요 시 WebSearch로 §축 C 검색 정답성 직접 검증) → `verdicts_NNN.json`.
- **Verify**: 정밀 풀(ACCEPT/High·Medium resolved)은 §5로, 재현 풀(hold/unresolved 15% 표본, §3 step 5b)은 §5b로 적대적 재검증(같은 배치 파이프라인 단계, barrier 없음) → `vverdicts_NNN.json` / `rhold_vverdicts_NNN.json`.
- **Aggregate**: 1 에이전트가 전 verdicts + 결과를 읽어 §6 지표·보고서·전수 페이지를 쓰고, `candidate_audit` shadow 재버킷을 Bash로 실행.

호출:
```
Workflow({ scriptPath: "tools/workflows/full_post_judge.workflow.js",
           args: { resultPath: "out/expert_result_20260616_224555_632905.json",
                   outDir: "out/full_post_judge_20260616_224555_632905", batchSize: 15 } })
```
주의: Workflow 경로는 **Claude 사용량을 소모**한다(2246/15 ≈ 150 judge 에이전트). 한도가 걱정되면 §3/§8의 로컬 vLLM 또는 Codex 경로를 쓴다. 두 경로의 verdict 스키마는 동일하다.

---

## 부록 A. 용어표 (보고서 §0에 복사)

- `candidate_ledger_status`(파이프라인 결정 라벨, `candidate_audit.py`): safe_resolved(안전해소)·promotion_blocked(승격차단)·hold_unresolved(미해소보류)·candidate_generation_miss(후보생성실패=재현실패)·official_title_lint·identity_consistency_lint·output_consistency_lint·review_only.
- `disagreement_type`(judge 불일치 분류, 3 그룹): **recall** = under_resolved_false_negative(과소해소·거짓음성). **precision** = cross_media_or_famous_mismatch(타매체·유명작 혼동)·wrong_work(다른 작품)·over_resolved(과해소)·garbage_title(비제목 표면). **hygiene** = wrong_discussion_type(문맥분류 오류)·wrong_relevance(관련성 오판)·title_noisy_ocr(OCR 잡음 제목). + none/uncertain.
- `resolution_label`(judge 처분): ACCEPT(수용)·HOLD(보류)·REPROCESS(재처리)·REJECT(기각)·INFO_MISSING(정보부족). ACCEPT 게이트는 엄격.
- `hold_reason`(HOLD/REPROCESS 원인; na=ACCEPT/INFO_MISSING/REJECT — REJECT 원인은 disagreement_type가 담음): heretic_url_null·search_only_resolved_title·ocr_only_title·registry_alias_only·weak_source_tier·generic_abstract_title_collision·context_only_late_rescue·comment_attribution_unverified·memory_query_no_quote_anchor·conflicting_or_multi_candidate·boundary_needs_human·reason_evidence_mismatch·other·na. → §6.3 정밀 개선 우선순위.
- `search_evidence_grade`(검색 정답성): Strong/Medium/Weak/Missing.
- `source_tier` 신뢰 사다리: official_detail > official_search > community > listing > llm_only > mixed. OFFICIAL 인정 = {official_detail, novel_platform}.
- `recommended_action`: no_action·re_search·re_judge·re_run·human_review·slang_db_review·docs_issue.
- **LEAN 스키마(§4.3a)** vs **FULL 스키마(§4.3b)**: LEAN=소형 vLLM이 직접 내는 11필드(+선택 hint). FULL=영속·표준 16필드. vLLM은 결정적 post-processor로 LEAN→FULL materialize, Claude/GPT-Pro는 FULL 직접.
- **slang precompute(§2.3, D2)**: `slang_present`·`slang_store_in_db`·`slang_pollution_suspect`·`slang_suspect_reasons`·`slang_axis_route`(llm/deterministic_na)·`deterministic_slang_verdict`(ok/pollution_risk/over_blocked/na). 슬라이스 단계가 `candidate_audit.slang_audit(identity)`로 LLM 없이 계산. 축 D LLM 판정은 `slang_axis_route=="llm"` 행만.
- `web_reverify_needed`(bool): vLLM 경로에서 LLM-set 필드(derive 금지). true면 그 행을 Codex/Claude 네이티브 웹 패스로 회수.

## 부록 B. 이 런(20260616_224555_632905) 베이스라인 분포 (참고)

processed=2246, pending=23. is_relevant: true=501 / false=1745.
work_resolution: resolved=351 / unresolved=140 / multi_work=10 / none=1745.
title_resolution_state: resolved=351 / adjacent=833 / unresolved_matchable=568 / author_new_work_context=194 / context_only=177 / ocr_explicit_title_unresolved=58 / nonwork=40 / unresolvable_memory_query=15 / multi_work=10.
candidate_ledger_status: hold_unresolved=1465 / promotion_blocked=393 / safe_resolved=345 / review_only=37 / official_title_lint=6.
confidence(resolved): High=291 / Medium=60 / Low=1.
검색증거 보유=1445, 이미지증거 보유=1319(이미지 글=1319), 댓글 글=1735.
judge_seed_group: 전부 unseeded, judge_disagreement_type: 전부 None → **이 런은 아직 판정 레이어가 입혀지지 않음**(이 런북이 그 레이어를 만든다).
→ 정밀 1차 검수 모수 = resolved 351(특히 safe_resolved 345). 재현 1차 검수 모수 = unresolved_matchable 568 + ocr_explicit_title_unresolved 58 + hold_unresolved 1465.
