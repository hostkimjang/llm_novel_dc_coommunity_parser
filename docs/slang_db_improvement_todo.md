# Slang DB Improvement TODO

정식 소설명 기준 은어 추출 품질을 유지하면서, `slang_db`가 대시보드와 운영 관점에서 더 읽기 쉽게 보이도록 정리하는 작업 메모다.

개발 TODO와 품질 게이트는 `docs/devs/FEATURE_IMPROVEMENT_TODO.md`, `docs/devs/OPERATION_QUALITY_CHECKLIST.md`에서도 함께 추적한다.

## 이번 반영

- [x] `slang_db` 기본 저장을 포스트 단위 즉시 flush로 변경
- [x] flush 로그에 `term -> title -> bucket` preview 추가
- [x] `family_aliases` 자동 승격 시 원본 source role 집계를 유지하도록 수정
- [x] 강한 단일 confirmed alias가 추정/보류 title 때문에 `family_alias/conflict`로 희석되지 않도록 보정
- [x] 20k 런 기준 slang audit 수행 (`20260423_170321_250907`)
- [x] 감사 스크립트가 대형 로그를 streaming으로 읽도록 보강

## 다음 우선순위

- [ ] 대시보드 API/화면에서 `titles[].slang/pending` 뿐 아니라 `examples.bucket`, `family_aliases`를 함께 보여주기
- [ ] `pending`를 단일 버킷으로 두지 말고 `pending_alias`, `secondary_reference`, `comparison_only` 같은 하위 성격으로 분리할지 검토
- [ ] 작품명이 아닌 일반 라벨성 title이 `pending`에 남는 패턴을 더 강하게 차단할지 검토
- [ ] `family_aliases` 승격 조건을 실데이터 기준으로 재조정
- [ ] `slang_db` 품질 검사용 샘플 리포트 스크립트 또는 audit 명령 추가
- [ ] `unclear_canonical_alias`로 차단된 실제 약칭 후보를 review queue로 분리
- [ ] 검색 안정화 후 slang 회수율이 올라가는지 같은 샘플로 재감사

## 관찰 메모

- 현재 DB는 `정식 작품 은어 사전`과 `보류/주변 참조 관측`이 섞인 구조다.
- 그래서 웹 대시보드가 `titles[].slang/pending`만 보면 실제보다 적게 보일 수 있다.
- `family_aliases`는 모호한 약칭을 숨기는 효과가 있어서, 조회 레이어가 이를 같이 보여주지 않으면 “저장이 안 된 것처럼” 보인다.
- 2026-04-26 감사 기준 `slang_insight=1817`, 저장 후보는 보정 전 `546`에서 보정 후 `532`로 줄었다.
- 현재 `slang_db/slang_db.json`은 `titles=340`, `family_aliases=1`, 문장형/작품명 동일 alias 오염 `0`으로 확인됐다.
- 차단된 14건은 모두 `unclear_canonical_alias`이며, 일부는 실제 약칭으로 보이는 표본이라 검색 안정화 후 재검토가 필요하다.
