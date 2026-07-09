# Loop636 11674731 canonical cleanup verdict

Loop635 residual20 중 `11674731`은 clean title `여자아이 만들기`와 동일 NovelPia URL `https://novelpia.com/novel/10594`가 source-native 판결에서 이미 맞물린다.

## 판정

- review_label: `REPROCESS`
- expected_title: `여자아이 만들기`
- actual_title: `여자아 이 만들기 새 창 열림`
- selected_url: `https://novelpia.com/novel/10594`
- evidence_grade: `Strong`
- runtime_replay_allowed: `false`
- full_scan_approval: `false`

## 해석

현재 public title은 띄어쓰기와 브라우저 UI 노이즈가 섞인 canonical 오염이다. URL은 정답 작품과 동일하므로 clean title로 정리하되, 이는 projection-only 계약이다. 새 runtime approval이나 full_scan approval이 아니다.

## Gate

- semantic_quality: `REVIEW-LOCKED`
- re-baseline: `NOT_APPLIED`
- completion gate: `adjusted full375 collateral GO + full_scan path`
- 2026-06-26 raw baseline diff는 diagnostic historical compare로만 사용한다.
