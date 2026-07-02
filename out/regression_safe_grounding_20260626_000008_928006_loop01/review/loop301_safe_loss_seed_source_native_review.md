# Loop301 safe_loss_resolved_to_null seed source-native verdicts (15/147)

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- batch review rows: `147`
- reviewed rows: `15`
- unreviewed batch rows: `132`
- validation issues: `0`

## Bucket counts

- `safe_loss_resolved_to_null`: `15`

## Label counts

- `ACCEPT`: `1`
- `REPROCESS`: `14`

## Source-native verdict counts

- `after_hold_preferred_wrong_before_title`: `1`
- `before_correct_source_native`: `13`
- `before_correct_source_native_title_variant`: `1`

## Rows

- `11660232` `ACCEPT` `after_hold_preferred_wrong_before_title` selected=`None` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 제목은 `괴담텔 이번 전개`를 주제로 두고 `괴담동`은 비교 대상으로 언급한다. 후보 `괴담 동아리`를 현재 논의 작품으로 확정하면 current-work와 adjacent-work가 뒤섞이므로 HOLD가 더 맞다.
- `11660237` `REPROCESS` `before_correct_source_native` selected=`테라포밍` action=`repair_safe_loss`
  - 근거: 게시글 제목이 `테라포밍 볼만함?`으로 작품명을 직접 묻고, 후보 URL도 공식 작품 `테라포밍`에 대응한다. after null은 정당한 safe title을 잃은 회귀다.
- `11660257` `REPROCESS` `before_correct_source_native` selected=`암흑가 보스요? 제가요?` action=`repair_safe_loss`
  - 근거: 제목 `암흑가보스<<이거 재밋네`는 후보 작품의 안정 축약 표면이다. 공식 URL에서도 후보 제목이 확인되므로 after null은 safe-loss다.
- `11660258` `REPROCESS` `before_correct_source_native` selected=`괴담 호텔 탈출기` action=`repair_safe_loss`
  - 근거: 제목 `괴담텔 아리야...`는 `괴담 호텔 탈출기`의 장갤 약칭과 등장인물 맥락이다. 후보 URL의 공식 제목도 `괴담 호텔 탈출기`로 확인된다.
- `11660259` `REPROCESS` `before_correct_source_native` selected=`헌터갤러리의 국가권력급 기계공주` action=`repair_safe_loss`
  - 근거: 제목의 `기계공주`와 본문 전개 언급이 후보 작품을 직접 가리킨다. 공식 URL의 제목도 `헌터갤러리의 국가권력급 기계공주`다.
- `11660265` `REPROCESS` `before_correct_source_native` selected=`헌터갤러리의 국가권력급 기계공주` action=`repair_safe_loss`
  - 근거: 제목 `기계공주 전생 이브...`와 본문 `오필리아` 맥락은 후보 작품의 내부 인물/전개를 직접 다룬다. after의 author-new-work context demotion은 과도하다.
- `11661876` `REPROCESS` `before_correct_source_native` selected=`와인의 신` action=`repair_safe_loss`
  - 근거: 제목 `와인의신 재밌다`와 댓글의 `문피아에서 봤다`가 후보 `와인의 신`을 직접 지지한다. after null은 작품명 직접 언급을 잃은 회귀다.
- `11666731` `REPROCESS` `before_correct_source_native` selected=`약먹는 천재마법사` action=`repair_safe_loss`
  - 근거: 제목 `약먹마 요즘 좀 애매함`은 후보 작품의 통용 약칭을 직접 사용한다. 후보 URL은 없지만 원문 surface가 충분하므로 null demotion은 safe-loss다.
- `11669943` `REPROCESS` `before_correct_source_native` selected=`즉사기 들고 무림에 떨어지다` action=`repair_safe_loss`
  - 근거: 제목 `즉사무림 최신편`과 본문 `무협미식` 맥락은 후보 작품을 직접 다룬다. after의 author-new-work context demotion은 현재 작품 언급을 과소평가했다.
- `11671500` `REPROCESS` `before_correct_source_native` selected=`악당도 살고 싶다` action=`repair_safe_loss`
  - 근거: 제목 `악살싶에서는`은 후보 작품의 약칭이고, 댓글도 해당 작품의 말투/강의씬 맥락을 이어간다. after null은 직접 alias를 잃은 회귀다.
- `11671517` `REPROCESS` `before_correct_source_native_title_variant` selected=`헌터갤러리의 국가권력급 기계공주 마이너 ...` action=`repair_safe_loss`
  - 근거: 제목 `기계공주 작가...`와 댓글의 작가/전작 맥락은 후보 URL의 작품을 직접 다룬다. before title 문자열은 truncation variant지만 URL과 작품 표면은 정당하다.
- `11676310` `REPROCESS` `before_correct_source_native` selected=`마도서를 줍다 마법사가 되다` action=`repair_safe_loss`
  - 근거: 제목 `마도줍 시리즈 왔구나`는 후보 작품의 축약 표면이다. 후속 문맥도 구매/연재 소비 맥락이라 null demotion은 과도하다.
- `11684372` `REPROCESS` `before_correct_source_native` selected=`밀리언 클래스` action=`repair_safe_loss`
  - 근거: 제목 `밀리언클래스 공지보고`가 후보 작품명을 직접 붙여 쓴다. 본문/댓글도 공지와 대학원생 휴재 사유 맥락이라 작품 공지에 대한 반응으로 읽는 것이 자연스럽다.
- `11685987` `REPROCESS` `before_correct_source_native` selected=`괴담 동아리` action=`repair_safe_loss`
  - 근거: 제목 `괴담동 뭔데`는 후보 작품의 안정 약칭을 직접 사용한다. after의 OCR unresolved는 제목 표면을 잃은 safe-loss다.
- `11689292` `REPROCESS` `before_correct_source_native` selected=`최악의 파트너` action=`repair_safe_loss`
  - 근거: 제목이 `최악의 파트너 표지`를 직접 말하고, 본문도 표지/그림작가/패러디 작품 댓글로 이어진다. 후보 작품을 null로 내리는 것은 회귀다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
