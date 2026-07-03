# Loop376 11705245 same URL-title mismatch preview

## 결론

- 신규 full375/bounded/N5 대형 런은 발주하지 않았다.
- `11705245`의 Loop374 actual `하남 남자` / `https://novelpia.com/novel/302245` publish는 같은 official URL의 공식 detail 후보 `하남자는 딸깍충이 되고 싶다`와 충돌한다.
- 패치 후 기존 Loop374 행에 postprocess preview를 적용하면 public title은 `null`, `candidate_ledger_status=promotion_blocked`, `publish_allowed=false`로 내려간다.
- URL만 제거한 뒤 title-only로 재복구되던 경로도 같은 URL 충돌 시 독립 title/snippet 양성 근거가 없으면 막는다.
- 이 변경은 `11705245` wrong publish closure preview이며 golden18 재실행은 아직 하지 않았다. 따라서 expected-answer는 `NO-GO / inherited 14 of 18`로 유지한다.
- search recovery는 계속 `P0 / OPEN`, `promotion_blocked=search-blind conditional`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`다.

## 근거

- 원문 제목: `하남자 재밌냐`
- 원문 본문/댓글: `주인공 첨부터쌤?`, `ㄴㄴ`
- Loop374 before: public title `하남 남자`, URL `https://novelpia.com/novel/302245`, `safe_resolved=true`
- Preview after: public title `null`, URL `null`, `promotion_blocked=true`, reason `official_detail_url_title_mismatch_publish_blocked`
- source-native/web 확인:
  - Novelpia official detail `https://novelpia.com/novel/302245`: `하남자는 딸깍충이 되고 싶다`
  - Munpia official detail `https://novel.munpia.com/400210`: `하남자의 탑 공략법`
  - Naver Series official detail `https://series.naver.com/novel/detail.series?productNo=11227324`: `하남자의 탑 공략법`

## 산출물

- preview JSON: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop376_11705245_same_url_mismatch_preview.json`
- preview Markdown: `out\regression_safe_grounding_20260626_000008_928006_loop01\review\loop376_11705245_same_url_mismatch_preview.md`
- state JSON: `docs\devs\loop376_11705245_same_url_mismatch_state_20260704.json`
- source result: `out\regression_safe_grounding_20260626_000008_928006_loop01\canary\loop374_golden18_signal_idle_de0eec1d_worktree_result.json`

## 검증

- `.venv312\Scripts\python.exe -m unittest tests.test_expert_main_comment_metadata -v` -> PASS, `52` tests.
- `.venv312\Scripts\python.exe -m unittest tests.test_candidate_audit.CandidateAuditTest.test_short_lead_public_title_bridge_is_held_without_confirmed_alias tests.test_candidate_audit.CandidateAuditTest.test_short_lead_public_title_bridge_is_held_with_confirmed_stem_alias tests.test_candidate_audit.CandidateAuditTest.test_weak_alias_surface_is_held_with_confirmed_stem_alias tests.test_candidate_audit.CandidateAuditTest.test_direct_exact_short_official_title_is_not_weak_alias_held -v` -> PASS, `4` tests.
- 실제 runtime replay는 `NOT_RUN`이다. 다음 golden18 전까지 이 결과는 contract preview로만 계산한다.

## 다음 작업

- `11705245`는 다음 golden18 또는 단건 runtime에서 null 유지 여부를 확인해야 expected-answer 카운트에 반영할 수 있다.
- 남은 실패 `11698897`, `11663521`, `11700470`은 계속 별도 source/search/OCR lane으로 둔다.
- search recovery P0가 열리기 전 semantic approval, full scan approval, hard-hold 완화는 금지한다.
