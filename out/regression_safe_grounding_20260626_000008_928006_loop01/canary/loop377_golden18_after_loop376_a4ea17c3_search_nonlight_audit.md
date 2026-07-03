# Loop377 golden18 expected-answer 감사

- canary semantic gate: `NO-GO`
- runtime: completed=`18`, pending=`0`, failed=`0`
- VLM/OCR semantic gate ready: `true`
- slang_db: `off`
- expected rows: `18`
- passed: `15`
- failed: `3`
- negative no-public-work: `7/7` 통과
- positive expected-work: `8/11` 통과
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 실패 행

- `11663521`: expected=`어떤 마술의 금서목록 / 어떤 과학의 초전자포`, actual=`구원자의 퍼스트 레이디`, status=`wrong_or_unexpected_title`
- `11668307`: expected=`빚을 져서라도 세상은 구해야 할 거 아니야`, actual=`None`, status=`positive_work_unresolved`
- `11698880`: expected=`가챠 중독자의 퓨전펑크 생활`, actual=`아카데미 생존 갤러리`, status=`wrong_or_unexpected_title`

## 통과 확인

- `11705245`: expected null을 지켰고 public title/url은 `None`이다.
- `11700470`: expected `악당 얼굴의 B급 모험자`를 public title로 과대승격하지 않고 image boundary unresolved로 보존했다.
- `11660237`: expected `테라포밍`으로 safe-resolved 됐다.
- `11713222`: expected `잘생기면 편해지는 인방 생활`로 safe-resolved 됐다.
- `11705231`: expected `탐식의 재림`으로 safe-resolved 됐다.

## Gate

Runtime production은 `GO / 18 of 18`이지만 expected-answer는 `NO-GO / 15 of 18`이다. 이 감사는 semantic approval, full scan approval, hard-hold 완화 근거가 아니다.
