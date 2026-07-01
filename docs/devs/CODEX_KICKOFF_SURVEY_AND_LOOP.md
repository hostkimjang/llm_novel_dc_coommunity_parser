# Codex 킥오프 프롬프트 — 전수 검사 → 회귀안전 개선 루프

> 아래 코드블록을 **그대로 복사해 Codex(GPT Pro)에 붙여넣어** 시작한다. Codex가 native web search로 전수 judge → 개선 아이디어 도출/구현 → 실제 expert_main.py canary → 회귀안전 재검수 → 루프를 자율 진행하게 하는 운영 지시다. (Claude Max 한도 절약 위해 무거운 루프는 Codex가 수행.)

---

```
역할: 너는 이 repo(llm_novel_dc_coommunity_parser)의 한국 웹소설 커뮤니티(dcinside) 글→작품 매칭 파이프라인 품질을 개선하는 시니어 엔지니어다. 종료 보고에서 멈추지 말고, 아래 단계를 next queue가 빌 때까지 연속(continuous)으로 돈다. 너는 GPT Pro라 native web search를 적극 활용한다.

[배경 — 직전 세션이 만든 것, 먼저 읽어라]
- docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md  ← 이 작업의 운영계약(메인). 8단계 루프·게이트·재사용 함수 좌표·함정이 여기 있다. 반드시 따른다.
- docs/devs/DETECTION_SURVEY_AND_ROOTCAUSE_20260626.md  ← 전수 조사 결과 + 6갈래 코드 근본원인 + FIX-0~4 로드맵.
- docs/devs/detection_survey_20260626_errors.json  ← 오류 136행(slice 기준, seed source).
- docs/devs/FULL_POST_JUDGE_RUNBOOK.md  ← 전수 판정 런북(엔진 비의존, 기본 엔진=Codex native web judge).
- docs/devs/LLM_JUDGE_ANALYSIS_SPEC_FOR_CODEX.md  ← judge 배치/스키마/taxonomy/웹검증 규칙.
- docs/devs/COMPLETED779_HERMES_CONTINUOUS_GOAL_PROMPT.md  ← 재사용할 연속루프 골격(Council fan-out·compare·requeue).

[핵심 진실 — 이걸 어기면 회귀가 재발한다]
- 6개 오류 클래스(과해소·동음이의·오답선택·이미지앵커·batch번짐·slang오염)는 별개 버그가 아니라 "맥락 결속(referential grounding) 게이트 부재"라는 단일 결함의 표면들이다. "표면 겹침(title_norm in full_norm 부분문자열)=결속"이 거짓 기본값. 모든 승격이 candidate_audit.classify_candidate_audit(:2158 `if title: return safe_resolved`)로 수렴한다.
- 직전 자동개선 루프가 회귀를 낸 이유: (B) 비단조 rescue 결합면(여러 승격 진입점)을 단건 패치하면 다른 진입점이 우회·재회귀(whack-a-mole). (C) seed-only 측정이 ACCEPT 행·비-seed 회귀를 정의상 못 봄(loop16 rank1 회귀, IMP-300 자백).
- 따라서: ① 맥락결속 fix는 단일 work-bridge 술어 1개로 수렴 + 모든 승격 진입점에 배선 + 계약 테스트로 우회 차단. ② 채택 게이트는 seed가 아니라 전수 collateral 회귀 + 동결 골든셋으로 본다.

[Phase 1 — 전수 검사 (먼저, 빠짐없이)]
- 직전 세션은 진행중 런의 1934-POST slice만 judge했고 적대검증도 29건만 끝냈다(세션한도). 너는 최신 런 결과(out/expert_result_*.json 중 flushed_count 최대, manifest의 large_run_complete 확인 — partial이면 slice로 명시)를 대상으로 FULL_POST_JUDGE_RUNBOOK대로 **모든 flushed POST를 전수 재판정**한다. 엔진 = 너의 native web search/open(외부 API 불필요). 재사용: tools/full_post_judge_codex_driver.py(project_row/precomputed/recall_population/overlay_verdicts), tools/build_completed779_issue_index.py.
- blind judge: 파이프라인 결론을 먼저 보지 말고 원천(title/body/comments/OCR/search_evidence)만으로 독립 판정 후 사후 대조(confirmation bias 제거).
- 산출: 오류 클래스별 전수 분포(개수/비율, top-N 금지) + 적대적 웹검증으로 확정한 오류 목록(detection_survey_20260626_errors.json를 확장/갱신). recall_miss 정답추정은 웹검색으로 확정하라(직전 세션은 미확정).
- failure_class enum: generic_phrase_substring / homonym_cross_domain / batch_context_bleed / wrong_work_among_aliases / image_anchor_spurious / over_resolved_nonwork / slang_pollution / recall_miss / none. fix_axis로 묶어 어떤 게 단일 work-bridge 술어로 닫히는지 표시.

[Phase 2 — 개선 아이디어 도출 (방법론 + 코드, 추가 발굴)]
- 내가 발굴한 것 외에 전수 결과에서 새 오류 패턴/엣지케이스를 적극 발굴하라. Hermes Council식으로 다수 subagent를 fan-out해 탐색하되(explorer/challenger, 승인권 없음; 모델 다양성=variance reduction, voting 아님), 메인인 네가 files/tests/canary/compare/web로 모든 주장을 재검증한 뒤에만 채택.
- 각 오류군마다: 어느 코드 게이트가 원인인가 / 단일 work-bridge 술어로 닫히는가, 별도 가드가 필요한가 / over-promotion·recall 회귀 위험 / 필요한 테스트·canary. 방법론 아이디어(측정·replay·quarantine)와 코드 아이디어를 분리 기록.

[Phase 3+ — 회귀안전 개선 루프 (GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md 8단계 그대로)]
- A) 측정 인프라 부트스트랩: 동결 baseline full-run 복사 + Regression Panel(6 error class 양/음성 + rank1/2/3 보호 해소 + 정당약칭 recall + survey 136행, 층화·불변) + 동결 골든셋(positive+negative, clean_canary_row로 정답누설 제거).
- B) 구현: 맥락결속 fix는 단일 술어 `_post_discusses_work_as_work(ctx,title)`(신규 LLM 호출 0, 기존 결정적 신호 재사용: official_url_recoverable / anchor_type∈{title_mention,character_title_link,plot_mention} / 약칭사전 / work_consumption_markers; generic substring·짧고흔한제목 배제)로 만들고 **모든 승격/복구 진입점에 배선**(agentic_pipeline의 _can_promote_title_after_semantic_no_work / _resolve_batch_memory_alias_candidate / _mark_batch_alias_rescue_flags / _pick_safe_single_candidate_unresolved_promotion, arbiter의 _apply_hypothesis_guard / _title_directly_in_post / _has_strong_title_support, VlmEnricher _infer_vlm_title_role — 거대파일이라 grep로 위치 확인). 새 rescue 경로가 술어를 우회 못 하도록 **계약 테스트** 추가. 동음이의/slang decode-게이트(decode_verified is True 인입 + is_confirmable 예외)/랭커 정확약칭 분리는 survey §4 위치대로.
- C) 실제 canary: .venv312\Scripts\python.exe expert_main.py 실재 실행. text: --server-type vllm --llm-endpoint http://10.20.0.101:8000 --reuse-shards-only --no-dashboard --slang-db off --parallel <min(input,36)>; image: --vlm on --ocr on --require-vlm-ocr-for-images 추가. 입력=queue seed + Regression Panel + 골든셋 + control sentinel(11694064 등). **동결 slang_db 스냅샷 read-only, ≥2회 재실행**(결정성). live 모델 확인: http://10.20.0.101:8000/v1/models. preflight 막히면 정확한 실패+resume 명령 기록(runtime 미검증 표기).
- D) 3중 회귀축 compare: ① seed movement(tools/compare_completed779_improvement.py) ② collateral 전수 스캔 — baseline∩canary 전 post_id를 analysis_identity(:87)/titles_match(:241)/movement_status(:386)로 diff하는 신규 패스 추가(compare()는 seed-only라 플래그 토글로 안 됨) → collateral_regression_count ③ 동결 골든셋 회귀 0. **단순 변화량 금지 — 골든/판단정답 대조로 정당 recall 개선(null→올바른 resolved)은 회귀에서 면제.**
- E) 테스트: git diff --name-only → 영향 모듈 매핑(rank 코드 건드리면 rank1/2/3 테스트 자동 포함) + 전체 unittest sweep + py_compile + git diff --check.
- F) Acceptance audit + requeue + docs sync(goal.md/TODO/CHECKLIST/HISTORY/IMPROVEMENT_REGISTER/VERIFICATION_RESULTS). collateral로 잡힌 신규 회귀행도 queue 추가.

[Phase G — 회차 보고서 (한 회차=개선+테스트구동+분석 끝날 때마다, 한국어, @data-analytics 사용)]
- 매 loop(한 회차)가 끝나면 한국어 종합 보고서를 docs/devs/loop_reports/LOOP_<N>_REPORT_<YYYYMMDD>.md 로 작성한다(회차별 파일, 덮어쓰기 금지).
- 정량 분석은 @data-analytics 플러그인에 이번 회차 산출물(seed compare JSON, collateral 스캔 결과, 골든셋 결과, before/after movement_status_counts, canary completed/failed/pending, 테스트 결과)을 입력해 생성한다 — 개선 전/후 분포 표·차트, official_title 변화 건수, collateral_regression_count, 골든 회귀, 클래스별 movement를 @data-analytics로 집계·시각화하고 그 출력을 보고서에 인용.
- 보고서 필수 섹션:
  1) 회차 요약: loop 번호·날짜·다룬 오류군/seed 수·구현한 fix 한 줄 요약.
  2) 개선 전/후 분석(@data-analytics): before vs after 정량 비교(movement 분포, resolved/HOLD/null 변화, 클래스별 오류 증감), collateral 전수 회귀·골든 결과.
  3) 연구·근본원인 분석: 이번 회차에서 새로 발굴한 오류 패턴/엣지케이스, 단일 work-bridge 술어로 닫힌 것 vs 별도 가드가 필요한 것, recall↔precision 트레이드 관측.
  4) 회의(Council) 의견: fan-out subagent들의 핵심 의견·대립/소수의견과 메인이 files/tests/canary/web로 재검증해 채택/기각한 결론(variance reduction 관점). 기각한 아이디어와 그 이유도 남긴다.
  5) 게이트 판정: run integrity / targeted canary status / semantic quality(REVIEW-LOCKED) / full-scan approval(false) / 이번 회차 GO·REVIEW·NO-GO + 근거.
  6) 다음 회차 계획: requeue된 행, 미해결/보류(HOLD/human_review) 사유, 남은 위험.
- 보고서는 chat에만 두지 말고 반드시 파일로 남긴다. @data-analytics 산출 차트/표는 보고서에 임베드하거나 경로로 링크.

[Non-Negotiable Gates — 매 loop·리포트]
- run integrity / targeted canary status / semantic quality / full-scan approval을 분리 보고. runtime 완료 ≠ semantic 승인.
- semantic_quality=REVIEW-LOCKED, full_scan_approval=false 끝까지 유지.
- post_id/title-specific 하드코딩 금지(production code). official_title 무분별 확대 금지. canary는 --slang-db off(production write-back 금지). deterministic full-post aggregate와 native-web aggregate 혼용 금지.
- collateral_regression_count(골든 대조 후) 순 회귀 > 0 또는 골든 회귀 ≥1 또는 술어형태 아님(표면별 단건패치) 또는 영향테스트·sweep 미green → 그 loop semantic NO-GO, 패치 보류/수정.
- 표면별 단건 패치 금지(다른 진입점 우회). seed movement만으로 채택 금지. 고정 테스트핀만 실행 금지. canary 1회 통과를 무회귀 증명으로 간주 금지(≥2회).

[정지 조건]
- next queue가 비었거나 모든 잔여 row가 HOLD/human_review/INFO_MISSING/unresolved_matchable/quarantine/no_generalizable_fix_left + row-level rationale일 때만 정지. 그 외에는 같은 루프를 계속 돈다.

[환경]
- 인터프리터 .venv312\Scripts\python.exe, 테스트는 unittest. vLLM endpoint http://10.20.0.101:8000, model bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4. 거대파일(agentic_pipeline.py 2.3MB/orchestrator.py 1.1MB/arbiter.py 522KB/decoder.py 478KB)은 grep로 심볼 잡아 해당 구간만 읽어라(라인은 드리프트하므로 심볼명 기준).

지금 Phase 1(전수 검사)부터 시작하라. 각 Phase 종료 시 산출물 경로와 게이트 상태를 보고하고, 멈추지 말고 다음 Phase로 이어가라.
```

---

## 사용법

1. 위 코드블록을 Codex 세션에 붙여넣는다. (repo 루트에서 실행하는 Codex여야 문서/도구 경로가 맞는다.)
2. Codex가 길게 돌다 멈추면 `"이어서 진행. 정지 조건 미충족이면 다음 loop 계속."` 한 줄로 재촉한다.
3. 진행 중 런이 끝나 더 큰 결과가 나오면, Phase 1을 그 최신 `out/expert_result_*`에 다시 적용하라고 지시(런북은 날짜 비의존).
4. 만약 vLLM/shard 인프라가 죽어 canary 실행이 안 되면 Codex는 "preflight failure + resume 명령"을 기록하고 코드/측정 작업만 진행한다(runtime 미검증으로 표기).

## 짧은 버전 (이미 Codex가 맥락을 아는 경우)

```
docs/devs/GOAL_REGRESSION_SAFE_GROUNDING_LOOP.md 의 운영계약대로 회귀안전 개선 루프를 continuous로 돌려라.
먼저 Phase 1: 최신 out/expert_result_*(flushed 최대) 전수를 FULL_POST_JUDGE_RUNBOOK대로 native web blind judge로 재판정해 오류 클래스별 분포 + 확정 오류 목록을 만들고 detection_survey_20260626_errors.json을 확장하라.
그다음 단일 work-bridge 술어 + 전 진입점 배선 + 계약 테스트로 fix하고, 실제 expert_main.py canary(--slang-db off, ≥2회) 후 3중 회귀축(seed movement + collateral 전수 + 동결 골든셋)으로 검증, NO-GO면 보류. 한 회차 끝날 때마다 @data-analytics로 개선 전/후 정량분석을 만들고 한국어 보고서(개선 전후·연구분석·회의 의견·게이트·다음 계획)를 docs/devs/loop_reports/LOOP_<N>_REPORT_<날짜>.md로 작성. REVIEW-LOCKED·full_scan=false 유지. next queue 빌 때까지 멈추지 마라.
```
