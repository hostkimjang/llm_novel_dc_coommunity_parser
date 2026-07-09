# loop629_full375_after_loop628_survey_search_health_split search degraded/recovered hold

Row search_health가 SEARCH_DEGRADED 또는 SEARCH_DEGRADED_RECOVERED인 raw regression이다. 검색 복구 후 해당 행만 재실행하기 전까지 collateral regression evidence로 쓰지 않는다.

- rows: `13`
- gate: `REVIEW-LOCKED`
- full_scan_approval: `false`

## Rows

- `11661856` `resolved_to_null` search=`SEARCH_DEGRADED` before=`너랑은 절! 대! 안 사Kill거니까!` after=`None` survey=`None` expected=`None` post=`오늘에 맘마는~~~`
- `11669913` `resolved_to_null` search=`SEARCH_DEGRADED_RECOVERED` before=`하룬` after=`None` survey=`homonym_cross_domain` expected=`` post=`팩트는 하룬은 수학 마법을 증명했다는거임`
- `11669928` `null_to_resolved` search=`SEARCH_DEGRADED_RECOVERED` before=`None` after=`탑의 성좌들이 날 애호한다` survey=`recall_miss` expected=`탑의 성좌들이 날 애호한다 (프리데이, 노벨피아 PLUS, novelpia.com/novel/377032)` post=`탑성좌애호 노벨피아 이거 연중했었네`
- `11671512` `resolved_to_null` search=`SEARCH_DEGRADED_RECOVERED` before=`삼시세끼, 심아식당` after=`None` survey=`None` expected=`None` post=`패러디 떡밥 하니까 이거 봐야하는데`
- `11673080` `resolved_to_null` search=`SEARCH_DEGRADED` before=`갤질하는 천재 의사` after=`None` survey=`None` expected=`None` post=`의사물 볼때마다 의주빈 편 들고싶어지긴 하네`
- `11676314` `resolved_to_different_title` search=`SEARCH_DEGRADED_RECOVERED` before=`소설 속 엑스트라` after=`마도서를 줍다 마법사가 되다` survey=`image_anchor_spurious` expected=`마도서를 줍다 마법사가 되다` post=`마도줍 완결이 빠를까`
- `11677924` `resolved_to_different_title` search=`SEARCH_DEGRADED_RECOVERED` before=`고결에 오만이 깃들 때` after=`귀쟁이 투기장의 역배 기사님` survey=`None` expected=`None` post=`남캐일러 거부감 해결법 알아왔다`
- `11685994` `resolved_to_null` search=`SEARCH_DEGRADED_RECOVERED` before=`무한을 이해한 나는 외신의 사제가 되었습니다` after=`None` survey=`generic_phrase_substring` expected=`교황님(아파하세요) 계열 표지 작품(미상)` post=`념글 시발 외신소환 주문 뭐임...`
- `11694026` `resolved_to_null` search=`SEARCH_DEGRADED_RECOVERED` before=`괴담 호텔 탈출기` after=`None` survey=`None` expected=`None` post=`미로 방이 확실히 프로스페리티 테마긴 한듯`
- `11694067` `null_to_resolved` search=`SEARCH_DEGRADED_RECOVERED` before=`None` after=`괴담에 휘말렸다` survey=`recall_miss` expected=`괴담에 휘말렸다` post=`김괴라리) 그롱 이 개새끼 그냥 죽어랏`
- `11694068` `resolved_to_null` search=`SEARCH_DEGRADED_RECOVERED` before=`트와일라잇` after=`None` survey=`None` expected=`None` post=`트와일라잇 인터뷰는 이게 명문임`
- `11698870` `resolved_to_null` search=`SEARCH_DEGRADED_RECOVERED` before=`인간실격` after=`None` survey=`None` expected=`None` post=`인간실격이 살자엔딩이였나?`
- `11714885` `resolved_to_null` search=`SEARCH_DEGRADED_RECOVERED` before=`새아빠가 여동생을 탐하길래, 나는 새엄마를 길들였다` after=`None` survey=`over_resolved_nonwork` expected=`` post=`자식들로 몸 갈아타는 부모 ㅁㅊ`
