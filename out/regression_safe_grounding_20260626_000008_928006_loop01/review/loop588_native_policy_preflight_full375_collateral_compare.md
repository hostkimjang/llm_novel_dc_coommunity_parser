# loop588_native_policy_preflight_full375_collateral_compare

Loop588 native/policy preflight projection? full375 baseline? ??? ?? collateral ?????. ? runtime replay? ??? full_scan approval ??? ???.

## ??

- gate: `NO-GO`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- shared_post_count: `375`
- changed_post_count: `158`
- collateral_regression_count: `81`
- status_counts: `{'same_title_url_changed': 64, 'null_to_resolved': 24, 'resolved_to_different_title': 28, 'resolved_to_null': 42}`
- runtime: `completed=null`, `pending=null`, `failed=null`

## Gate ??

Loop588?? `11700483`? projection-only restore? ??? raw collateral regression? Loop587 `82`?? `81`? 1? ????. ??? raw regression? ?? runtime counts? ???? full375 collateral? ?? `NO-GO`?.

## Changed Rows

- `11658620`: `same_title_url_changed`, regression_candidate=`false`, before=`이거 럽코 빙의물인가요`, after=`이거 럽코 빙의물인가요`
- `11658626`: `same_title_url_changed`, regression_candidate=`false`, before=`아카데미 선비의 생활일지`, after=`아카데미 선비의 생활일지`
- `11658637`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`재벌집 막내아들`
- `11658646`: `same_title_url_changed`, regression_candidate=`false`, before=`이거 럽코 빙의물인가요`, after=`이거 럽코 빙의물인가요`
- `11660232`: `resolved_to_different_title`, regression_candidate=`true`, before=`괴담 동아리`, after=`괴담 호텔 탈출기`
- `11660237`: `resolved_to_different_title`, regression_candidate=`false`, before=`테라포밍`, after=`이세계 테라포밍 With편의점`
- `11660238`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`무림마조`
- `11660254`: `resolved_to_null`, regression_candidate=`true`, before=`푸푸푸 랜드의 두가지 일상`, after=`None`
- `11660257`: `same_title_url_changed`, regression_candidate=`false`, before=`암흑가 보스요? 제가요?`, after=`암흑가 보스요? 제가요?`
- `11660262`: `resolved_to_different_title`, regression_candidate=`true`, before=`그렇게, 그 괴물과 두 번 결혼했다`, after=`로판에 도파민을 풀었다`
- `11660265`: `same_title_url_changed`, regression_candidate=`false`, before=`헌터갤러리의 국가권력급 기계공주`, after=`헌터갤러리의 국가권력급 기계공주`
- `11660273`: `resolved_to_different_title`, regression_candidate=`true`, before=`마도서를 줍다 마법사가 되다`, after=`그리즐리 그랑`
- `11661856`: `resolved_to_null`, regression_candidate=`true`, before=`너랑은 절! 대! 안 사Kill거니까!`, after=`None`
- `11661857`: `resolved_to_null`, regression_candidate=`false`, before=`아카데미 개망나니 교수가 되었다`, after=`None`
- `11661863`: `resolved_to_null`, regression_candidate=`true`, before=`저주받은 영애가 되었습니다`, after=`None`
- `11661865`: `same_title_url_changed`, regression_candidate=`false`, before=`우주 게임 속 용병이 되었다`, after=`우주 게임 속 용병이 되었다`
- `11661876`: `same_title_url_changed`, regression_candidate=`false`, before=`와인의 신`, after=`와인의 신`
- `11663510`: `same_title_url_changed`, regression_candidate=`false`, before=`후회 안 하는 프로듀서`, after=`후회 안 하는 프로듀서`
- `11663514`: `same_title_url_changed`, regression_candidate=`false`, before=`마탄 속의 제국`, after=`마탄 속의 제국`
- `11663521`: `resolved_to_different_title`, regression_candidate=`false`, before=`초전자포] 시스터즈가 되었다`, after=`어떤 마술의 금서목록`
- `11663540`: `resolved_to_different_title`, regression_candidate=`false`, before=`방구석 여신이 되었다`, after=`전 버튜버가 하고 싶은데요`
- `11663554`: `resolved_to_different_title`, regression_candidate=`true`, before=`주서연 ( 전 버튜버가 하고 싶은데요 )`, after=`전 버튜버가 하고 싶은데요`
- `11665099`: `resolved_to_different_title`, regression_candidate=`true`, before=`옥천마 출정`, after=`옥탑방의 천재 마물 소환사`
- `11665110`: `resolved_to_null`, regression_candidate=`true`, before=`낭만적인 초능력을 위하여`, after=`None`
- `11665119`: `same_title_url_changed`, regression_candidate=`false`, before=`즉사기 들고 무림에 떨어지다`, after=`즉사기 들고 무림에 떨어지다`
- `11665121`: `same_title_url_changed`, regression_candidate=`false`, before=`후회 안 하는 프로듀서`, after=`후회 안 하는 프로듀서 [독점]`
- `11665124`: `resolved_to_different_title`, regression_candidate=`true`, before=`화산파(화산귀환)`, after=`화산귀환`
- `11666700`: `resolved_to_different_title`, regression_candidate=`true`, before=`하남자의 탑 공략법`, after=`내 고향엔 무림인이 산다`
- `11666713`: `same_title_url_changed`, regression_candidate=`false`, before=`21세기 무림세가`, after=`21세기 무림세가`
- `11666725`: `resolved_to_null`, regression_candidate=`true`, before=`학대받던 11살 고마가 각성한 이유`, after=`None`
- `11666729`: `same_title_url_changed`, regression_candidate=`false`, before=`이 무림의 미친년은 나야`, after=`이 무림의 미친년은 나야`
- `11668278`: `resolved_to_null`, regression_candidate=`true`, before=`짜장면`, after=`None`
- `11668288`: `same_title_url_changed`, regression_candidate=`false`, before=`가챠 중독자의 퓨전펑크 생활`, after=`가챠 중독자의 퓨전 펑크 생활`
- `11668293`: `same_title_url_changed`, regression_candidate=`false`, before=`즉사기 들고 무림에 떨어지다`, after=`즉사기 들고 무림에 떨어지다`
- `11668305`: `resolved_to_null`, regression_candidate=`true`, before=`Fate/stay night`, after=`None`
- `11668307`: `resolved_to_different_title`, regression_candidate=`false`, before=`디펜스게임 속 엘리트몹킬러가 되었다`, after=`빚을 져서라도 세상은 구해야 할 거 아니야`
- `11668324`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`니들 생각 다 들린다`
- `11669907`: `resolved_to_different_title`, regression_candidate=`true`, before=`마법 좋아좋아좋아`, after=`약스포) 마법 좋아좋아좋아`
- `11669921`: `same_title_url_changed`, regression_candidate=`false`, before=`악당은 살고 싶다`, after=`악당은 살고 싶다`
- `11669924`: `same_title_url_changed`, regression_candidate=`false`, before=`용인족의 아카데미 생존기`, after=`용인족의 아카데미 생존기`
- `11669928`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`탑의 성좌들이 날 애호한다`
- `11669929`: `resolved_to_different_title`, regression_candidate=`true`, before=`기계공주`, after=`헌터갤러리의 국가권력급 기계공주`
- `11669930`: `resolved_to_null`, regression_candidate=`false`, before=`수상할 정도로 돈이 많은 성주님 [독점]`, after=`None`
- `11669933`: `same_title_url_changed`, regression_candidate=`false`, before=`회귀수선전`, after=`회귀수선전`
- `11671500`: `resolved_to_different_title`, regression_candidate=`true`, before=`악당도 살고 싶다`, after=`악당은 살고 싶다`
- `11671501`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`판초우의의 마법사`
- `11671507`: `same_title_url_changed`, regression_candidate=`false`, before=`판초우의의 마법사`, after=`판초우의의 마법사`
- `11671512`: `resolved_to_different_title`, regression_candidate=`true`, before=`삼시세끼, 심아식당`, after=`킹덤, 전국의 패왕 [킹덤 패러디 ]`
- `11671514`: `resolved_to_null`, regression_candidate=`true`, before=`악신에게 총애받는 자`, after=`None`
- `11671538`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`망한 교단의 성기사`
- `11673080`: `same_title_url_changed`, regression_candidate=`false`, before=`갤질하는 천재 의사`, after=`갤질하는 천재 의사`
- `11673082`: `resolved_to_null`, regression_candidate=`false`, before=`용사 파티`, after=`None`
- `11673086`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`[림월드]변방계에서 회귀자로 살아남기`
- `11673102`: `same_title_url_changed`, regression_candidate=`false`, before=`갤질하는 천재 의사`, after=`갤질하는 천재 의사`
- `11674703`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`도굴왕`
- `11676309`: `same_title_url_changed`, regression_candidate=`false`, before=`갤질하는 천재 의사`, after=`갤질하는 천재 의사`
- `11676314`: `resolved_to_different_title`, regression_candidate=`true`, before=`소설 속 엑스트라`, after=`마도서를 줍다 마법사가 되다`
- `11676317`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`마도서를 줍다 마법사가 되다`
- `11676326`: `same_title_url_changed`, regression_candidate=`false`, before=`아카데미 생존 갤러리`, after=`아카데미 생존 갤러리`
- `11677957`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`음악 천재가 불륜을 못 숨김`
- `11679547`: `same_title_url_changed`, regression_candidate=`false`, before=`도굴왕`, after=`도굴왕`
- `11679553`: `same_title_url_changed`, regression_candidate=`false`, before=`마도서를 줍다 마법사가 되다`, after=`마도서를 줍다 마법사가 되다`
- `11679572`: `same_title_url_changed`, regression_candidate=`false`, before=`내 고향엔 무림인이 산다`, after=`내 고향엔 무림인이 산다`
- `11679576`: `same_title_url_changed`, regression_candidate=`false`, before=`판초우의의 마법사`, after=`판초우의의 마법사`
- `11681141`: `same_title_url_changed`, regression_candidate=`false`, before=`아카데미 악당영애 교정하기`, after=`아카데미 악당영애 교정하기 (연민하)`
- `11681152`: `resolved_to_different_title`, regression_candidate=`true`, before=`체육관 챌린지에서 살아남기`, after=`[포켓몬] 체육관 챌린지에서 살아남기`
- `11681177`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`격투 천재 여고생이 되었다`
- `11681178`: `resolved_to_null`, regression_candidate=`true`, before=`재벌가 차녀의 2회차 걸그룹`, after=`None`
- `11682749`: `resolved_to_null`, regression_candidate=`true`, before=`주인공인데 주인공이 아님`, after=`None`
- `11682761`: `same_title_url_changed`, regression_candidate=`false`, before=`그레이스 길들이기`, after=`그레이스 길들이기`
- `11682767`: `same_title_url_changed`, regression_candidate=`false`, before=`묵향`, after=`묵향`
- `11682768`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`마법소녀ㄴ은 은퇴하고 싶다`
- `11682775`: `same_title_url_changed`, regression_candidate=`false`, before=`여자가 되어서라도 복수한다`, after=`여자가 되어서라도 복수한다`
- `11682780`: `same_title_url_changed`, regression_candidate=`false`, before=`이 무림의 미친년은 나야`, after=`이 무림의 미친년은 나야`
- `11682791`: `resolved_to_different_title`, regression_candidate=`true`, before=`피아조아 <시간을 달리는 소설가>`, after=`시간을 달리는 소설가`
- `11682792`: `resolved_to_different_title`, regression_candidate=`true`, before=`이 무림의 미친년은 나야`, after=`[무친년]이 무림의 미친놈`
- `11684371`: `resolved_to_null`, regression_candidate=`false`, before=`괴담에 휘말렸다`, after=`None`
- `11684380`: `same_title_url_changed`, regression_candidate=`false`, before=`신비의 제왕`, after=`신비의 제왕`
- `11685994`: `resolved_to_null`, regression_candidate=`true`, before=`무한을 이해한 나는 외신의 사제가 되었습니다`, after=`None`
- `11687618`: `null_to_resolved`, regression_candidate=`true`, before=`None`, after=`아카데미 생존 갤러리`
- ... changed row `78`?? JSON? ?? ??
