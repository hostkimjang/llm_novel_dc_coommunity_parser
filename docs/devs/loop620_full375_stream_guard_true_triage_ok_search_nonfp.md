# loop620_full375_stream_guard_survey_search_health_split true ok-search non-FP triage

Search status가 ok이고 detection_survey FP 제거 또는 의도 복구 blind-judge 대상이 아닌 잔여 raw regression이다. 현재 기준 실제 triage 후보로 다룬다.

- rows: `58`
- gate: `REVIEW-LOCKED`
- full_scan_approval: `false`

## Rows

- `11660229` `resolved_to_null` search=`ok` before=`로판 속 미친 북부대공이 되었다` after=`None` survey=`None` expected=`None` post=`로판 속 미친 북부대공이 되었다 하차함`
- `11660264` `resolved_to_null` search=`ok` before=`빚을 져서라도 세상은 구해야 할 거 아니야` after=`None` survey=`None` expected=`None` post=`빚세구 근데 주인공이 은발에 아이돌 출신이란 게 좀 신경쓰이네`
- `11660268` `resolved_to_null` search=`ok` before=`을 위한 세계는 없다` after=`None` survey=`None` expected=`None` post=`ㅁㅁ세계 초대용사전의 문제점`
- `11660271` `resolved_to_null` search=`ok` before=`월야의 여인들` after=`None` survey=`None` expected=`None` post=`아이돌 히로인 나오는 야설 어디 없나`
- `11661857` `resolved_to_different_title` search=`ok` before=`아카데미 개망나니 교수가 되었다` after=`두바이의 쫀득한 여초딩 재벌 9세` survey=`generic_phrase_substring` expected=`` post=`로판속 아카데미 앞 두쫀쿠 가게 사장이 되었다`
- `11661863` `resolved_to_null` search=`ok` before=`저주받은 영애가 되었습니다` after=`None` survey=`None` expected=`None` post=`두개 써서 동시에 올리나보네`
- `11663514` `resolved_to_different_title` search=`ok` before=`마탄 속의 제국` after=`올바른 슬라임 사용법` survey=`image_anchor_spurious` expected=`` post=`슬라임의 올바른 사용법`
- `11663521` `resolved_to_different_title` search=`ok` before=`초전자포] 시스터즈가 되었다` after=`카미조 토우마가 IS세계관에 떨어지는 이야기. 꽤 예전에 썼던 글인데 저쪽에선 읽기 힘들어서 여기에 재업합니다` survey=`generic_phrase_substring` expected=`어떤 마술의 금서목록 / 어떤 과학의 초전자포` post=`TS) 시스터즈 퍼스트 정신머리 고치려면`
- `11663535` `resolved_to_null` search=`ok` before=`퇴마록` after=`None` survey=`None` expected=`None` post=`퇴마록에 온갖 능력 다나오네 생각해보니`
- `11663554` `resolved_to_different_title` search=`ok` before=`주서연 ( 전 버튜버가 하고 싶은데요 )` after=`전 버튜버가 하고 싶은데요` survey=`over_resolved_nonwork` expected=`전 버튜버가 하고 싶은데요` post=`TS) 주서연 영화개봉 했는데 1엄복동도 못되면`
- `11663557` `resolved_to_different_title` search=`ok` before=`퇴마록` after=`퇴마록 1` survey=`None` expected=`None` post=`퇴마록 생각해보니 올해 예능프로그램으로 나오지 않나`
- `11665099` `resolved_to_different_title` search=`ok` before=`옥천마 출정` after=`옥탑방의 천재 마물 소환사` survey=`None` expected=`None` post=`옥천마 출정 ㅇㅈㄹ하는 부분부터 대가리 봉합됐음`
- `11665110` `resolved_to_different_title` search=`ok` before=`낭만적인 초능력을 위하여` after=`사이키델리아` survey=`homonym_cross_domain` expected=`사이케델리아 (이상규/sakali, 1998 퓨전판타지)` post=`사이키델리아 읽었던 사람 있냐?`
- `11666725` `resolved_to_null` search=`ok` before=`학대받던 11살 고마가 각성한 이유` after=`None` survey=`None` expected=`None` post=`아 이거 재밌어 보이는데 남주가 매력적임`
- `11666741` `resolved_to_null` search=`ok` before=`별을 품은 소드마스터` after=`None` survey=`None` expected=`None` post=`별품소 웹툰 가끔씩 보는데`
- `11668325` `resolved_to_null` search=`ok` before=`Fate/stay night` after=`None` survey=`None` expected=`None` post=`마파두부는 걍 이제 이새끼밖에 생각안남`
- `11669907` `resolved_to_different_title` search=`ok` before=`마법 좋아좋아좋아` after=`약스포) 마법 좋아좋아좋아` survey=`None` expected=`None` post=`이거 중간에 뱉길 잘했네`
- `11669926` `resolved_to_null` search=`ok` before=`싸울아비 룬` after=`None` survey=`None` expected=`None` post=`미적분 공식 외우면 발동되는 마법`
- `11669929` `resolved_to_different_title` search=`ok` before=`기계공주` after=`헌터갤러리의 국가권력급 기계공주` survey=`recall_miss` expected=`헌터갤러리의 국가권력급 기계공주` post=`기계공주 재밌네`
- `11671500` `resolved_to_different_title` search=`ok` before=`악당도 살고 싶다` after=`악당은 살고 싶다` survey=`other` expected=`악당은 살고 싶다` post=`말투 바뀌는 거 악살싶에서는 호평받았었는데`
- `11671512` `resolved_to_null` search=`ok` before=`삼시세끼, 심아식당` after=`None` survey=`None` expected=`None` post=`패러디 떡밥 하니까 이거 봐야하는데`
- `11673077` `resolved_to_null` search=`ok` before=`판초우의의 마법사` after=`None` survey=`None` expected=`None` post=`즉사무림 판초우의 빚세구 다 봄`
- `11673080` `resolved_to_different_title` search=`ok` before=`갤질하는 천재 의사` after=`방송했더니 천재 의사로 착각당했다` survey=`None` expected=`None` post=`의사물 볼때마다 의주빈 편 들고싶어지긴 하네`
- `11676314` `resolved_to_different_title` search=`ok` before=`소설 속 엑스트라` after=`마도서를 줍다 마법사가 되다` survey=`image_anchor_spurious` expected=`마도서를 줍다 마법사가 되다` post=`마도줍 완결이 빠를까`
- `11677924` `resolved_to_null` search=`ok` before=`고결에 오만이 깃들 때` after=`None` survey=`None` expected=`None` post=`남캐일러 거부감 해결법 알아왔다`
- `11677926` `resolved_to_null` search=`ok` before=`재앙급 막내 공자의 회귀` after=`None` survey=`None` expected=`None` post=`무영자 이 미친 꼴잘알새끼`
- `11679537` `resolved_to_null` search=`ok` before=`죽었다 깨어도 수선` after=`None` survey=`None` expected=`None` post=`내가 선협을 너무 비인간 장르로 봤나?`
- `11679547` `resolved_to_different_title` search=`ok` before=`도굴왕` after=`나 혼자만 레벨업` survey=`None` expected=`None` post=`나혼렙의 뒤를잇는 ㄷㄷ`
- `11681152` `resolved_to_null` search=`ok` before=`체육관 챌린지에서 살아남기` after=`None` survey=`None` expected=`None` post=`이거 살아날수 있을까`
- `11682767` `resolved_to_null` search=`ok` before=`묵향` after=`None` survey=`None` expected=`None` post=`근데 묵향 이 새끼 ts 초기에는 약했지`
- `11682768` `null_to_resolved` search=`ok` before=`None` after=`마법소녀는 은퇴하고 싶다` survey=`None` expected=`None` post=`근데 마법소녀ㄴ 일란성 쌍둥이라는거 뭔소리임`
- `11682775` `resolved_to_null` search=`ok` before=`여자가 되어서라도 복수한다` after=`None` survey=`None` expected=`None` post=`빵댕이쫀득ts무협`
- `11682780` `resolved_to_null` search=`ok` before=`이 무림의 미친년은 나야` after=`None` survey=`None` expected=`None` post=`근데 무친년은 뭉청이 지금 화경 대원만인데 현경 찍으면 ㅆㅂㅋㅋ`
- `11682791` `resolved_to_different_title` search=`ok` before=`피아조아 <시간을 달리는 소설가>` after=`시간을 달리는 소설가` survey=`None` expected=`None` post=`이거 진짜에요?`
- `11682800` `null_to_resolved` search=`ok` before=`None` after=`갤질하는 천재 의사` survey=`None` expected=`None` post=`갤질의사 최태수랑 비교하면 어떰`
- `11684370` `null_to_resolved` search=`ok` before=`None` after=`목표는 엔딩 요정 - 판타지 웹소설` survey=`None` expected=`None` post=`왜 단아엔딩인 것이지?`
- `11687618` `null_to_resolved` search=`ok` before=`None` after=`아카데미 생존 갤러리` survey=`None` expected=`None` post=`아생갤 떡밥 나오니까 좀 재밌네`
- `11687627` `null_to_resolved` search=`ok` before=`None` after=`변방계에서 회귀자로 살아남기` survey=`None` expected=`None` post=`렛따싶 풀네임이 뭐임?`
- `11689292` `resolved_to_different_title` search=`ok` before=`최악의 파트너` after=`[원신] 최악의 파트너` survey=`homonym_cross_domain` expected=`[원신] 최악의 파트너` post=`욘꼰 최악의 파트너 표지 쩌왔어`
- `11690855` `null_to_resolved` search=`ok` before=`None` after=`림버스 컴퍼니, 승리의 여신: 니케, 블루 아카이브` survey=`None` expected=`None` post=`림버스 저게 의외로 유저수 씹덕겜 3등인가 함`
- `11694047` `resolved_to_null` search=`ok` before=`판초우의의 마법사` after=`None` survey=`None` expected=`None` post=`판초법사 재밋음?`
- `11694049` `resolved_to_different_title` search=`ok` before=`아카데미 생존 갤러리` after=`아레스` survey=`recall_miss` expected=`` post=`아생갤) 아레스가 가장 무서워할 일은 바로`
- `11694068` `resolved_to_null` search=`ok` before=`트와일라잇` after=`None` survey=`None` expected=`None` post=`트와일라잇 인터뷰는 이게 명문임`
- `11695599` `resolved_to_null` search=`ok` before=`창관전생` after=`None` survey=`None` expected=`None` post=`봐라`
- `11697231` `null_to_resolved` search=`ok` before=`None` after=`아카데미 생존 갤러리` survey=`None` expected=`None` post=`아생갤 어렵네`
- `11702060` `null_to_resolved` search=`ok` before=`None` after=`괴담 호텔 탈출기` survey=`None` expected=`None` post=`한가인 4문장 어느정도일지 잘 모르겠음`
- `11702090` `resolved_to_null` search=`ok` before=`괴담 호텔 탈출기` after=`None` survey=`None` expected=`None` post=`애초에 한가인이 아리한테 부등변 준 이유가`
- `11702094` `resolved_to_different_title` search=`ok` before=`#더블오` after=`댓글창의 천재 마법사` survey=`over_resolved_nonwork` expected=`` post=`댓글창 이딴게 왜 재밌는거냐..?`
- `11703622` `resolved_to_null` search=`ok` before=`TS 남매근친순애` after=`None` survey=`None` expected=`None` post=`ts) 하아 쓉빨 너무 맛있다.....`
- `11705269` `resolved_to_different_title` search=`ok` before=`월야환담` after=`월야환담 : 신월야` survey=`None` expected=`None` post=`월야환담 베놈이 진짜 십사기 능력이었는데`
- `11706871` `resolved_to_null` search=`ok` before=`파우스트` after=`None` survey=`None` expected=`None` post=`독후감 쓰려고 파우스트 읽었었는데 결말에서 벙쪘음`
- `11708443` `resolved_to_null` search=`ok` before=`괴담에 떨어져도 출근을 해야 하는구나` after=`None` survey=`None` expected=`None` post=`괴담출근정도는 돼야 독창성 운운할수 있는거다`
- `11710045` `null_to_resolved` search=`ok` before=`None` after=`공주는 언니를 황제로 만든다` survey=`None` expected=`None` post=`섹스다섹스`
- `11710048` `resolved_to_null` search=`ok` before=`내 마법도서관이 살아있다` after=`None` survey=`None` expected=`None` post=`마법도서관이 살아있다 무슨내용임?`
- `11710052` `resolved_to_null` search=`ok` before=`아카데미 패드립 면역` after=`None` survey=`None` expected=`None` post=`아카엄창 엄마랑 섹스함?`
- `11714887` `resolved_to_null` search=`ok` before=`도굴왕 1 |` after=`None` survey=`None` expected=`None` post=`도굴왕 pv 츄라이 츄라이`
- `11714903` `resolved_to_different_title` search=`ok` before=`온 세상이 정신이상자다` after=`괴담 호텔 탈출기` survey=`generic_phrase_substring` expected=`괴담 호텔 탈출기` post=`온세상이 버튜버다`
- `11718099` `resolved_to_null` search=`ok` before=`빌어먹을 환생` after=`None` survey=`None` expected=`None` post=`빌환 표지변경됨`
