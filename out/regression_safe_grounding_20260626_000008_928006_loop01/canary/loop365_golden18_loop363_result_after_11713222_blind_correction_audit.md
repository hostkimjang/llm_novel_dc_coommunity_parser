# Loop365 golden18 expected-answer 재감사

## 요약

- 범위: `11713222` source-native expected 교정 뒤 기존 Loop363 golden18 결과를 재감사.
- runtime: completed/pending/failed `18/0/0`
- VLM/OCR semantic gate ready: `true`
- slang DB: `off`
- expected rows: `18`
- passed: `14`
- failed: `4`
- negative no-public-work passed: `8/8`
- positive expected-work resolved: `6/10`
- status counts: `expected_null_respected=8`, `positive_work_unresolved=2`, `expected_work_evidence_preserved_unresolved=3`, `expected_title_resolved=2`, `expected_hypothesis_preserved_unresolved=1`, `wrong_or_unexpected_title=2`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 행별 결과

- `11684371` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11694035` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11698897` `positive_expected_work`: `positive_work_unresolved`, passed=`false`, expected=`[림월드]변방계에서 회귀자로 살아남기`, actual=`None`
- `11705245` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11661857` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11663521` `positive_expected_work`: `expected_work_evidence_preserved_unresolved`, passed=`true`, expected=`어떤 마술의 금서목록 / 어떤 과학의 초전자포`, actual=`None`
- `11663540` `positive_expected_work`: `expected_title_resolved`, passed=`true`, expected=`전 버튜버가 하고 싶은데요`, actual=`전 버튜버가 하고 싶은데요`
- `11668307` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11669930` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11673082` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11685994` `positive_expected_work`: `expected_hypothesis_preserved_unresolved`, passed=`true`, expected=`교황님(아파하세요) 계열 표지 작품(미상)`, actual=`None`
- `11694019` `positive_expected_work`: `wrong_or_unexpected_title`, passed=`false`, expected=`이세계에서 사이비로 살아남기`, actual=`혼후순결`
- `11700470` `positive_expected_work`: `wrong_or_unexpected_title`, passed=`false`, expected=`악당 얼굴의 B급 모험자`, actual=`세계 최강 미소녀에게 납치당했습니다`
- `11705231` `positive_expected_work`: `expected_work_evidence_preserved_unresolved`, passed=`true`, expected=`탐식의 재림`, actual=`None`
- `11713212` `negative_no_public_work`: `expected_null_respected`, passed=`true`, expected=`None`, actual=`None`
- `11713222` `positive_expected_work`: `expected_title_resolved`, passed=`true`, expected=`잘생기면 편해지는 인방 생활`, actual=`잘생기면 편해지는 인방 생활`
- `11660237` `safe_loss_blind_judge_expected_work`: `expected_work_evidence_preserved_unresolved`, passed=`true`, expected=`테라포밍`, actual=`None`
- `11698880` `safe_loss_blind_judge_expected_work`: `positive_work_unresolved`, passed=`false`, expected=`가챠 중독자의 퓨전펑크 생활`, actual=`None`

Gate: `canary_semantic_gate=NO-GO`, `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`.
