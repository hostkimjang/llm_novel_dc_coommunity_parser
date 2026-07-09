# loop620_full375_stream_guard_survey_search_health_split intended recovery blind-judge batch

Survey recall_miss/wrong_work 방향과 일치하는 복구 후보만 모은 batch다. judge는 제목 정답성만 확인하고, search-degraded overlay는 별도 검색 복구 gate에 남긴다.

- rows: `28`
- gate: `REVIEW-LOCKED`
- full_scan_approval: `false`

## Rows

- `11658637` `null_to_resolved` search=`ok` before=`None` after=`재벌집 막내아들` survey=`recall_miss` expected=`재벌집 막내아들 (산경, 문피아/SERIES)` post=`재막아)영기는 진짜 답이 없구나`
- `11660232` `resolved_to_different_title` search=`ok` before=`괴담 동아리` after=`괴담 호텔 탈출기` survey=`wrong_work_among_aliases` expected=`괴담 호텔 탈출기` post=`괴담텔 이번 전개는 괴담동이 살짝 생각나네`
- `11666700` `resolved_to_different_title` search=`ok` before=`하남자의 탑 공략법` after=`내 고향엔 무림인이 산다` survey=`wrong_work_among_aliases` expected=`내 고향엔 무림인이 산다` post=`내고향무림 최신화 댓글창에도 벌레새끼가 있네`
- `11668324` `null_to_resolved` search=`ok` before=`None` after=`니생들이랑 김괴라리 장갤픽 아니였음?` survey=`recall_miss` expected=`니들 생각 다 들린다 (약칭 니생들, 노벨피아, 작가 유4)` post=`니생들이랑 김괴라리 장갤픽 아니였음?`
- `11669928` `null_to_resolved` search=`ok` before=`None` after=`탑의 성좌들이 날 애호한다` survey=`recall_miss` expected=`탑의 성좌들이 날 애호한다 (프리데이, 노벨피아 PLUS, novelpia.com/novel/377032)` post=`탑성좌애호 노벨피아 이거 연중했었네`
- `11671501` `null_to_resolved` search=`ok` before=`None` after=`판초우의의 마법사` survey=`recall_miss` expected=`판초우의의 마법사` post=`판초법사 막 게이트열린 시점아님?`
- `11671514` `resolved_to_different_title` search=`ok` before=`악신에게 총애받는 자` after=`악신의 총애를 받는 성직자가 되었다` survey=`wrong_work_among_aliases` expected=`악신이 총애하는 미궁 모험가` post=`악신총애) 마왕이 말하는거 의미심장한데`
- `11671538` `null_to_resolved` search=`ok` before=`None` after=`망한 교단의 성기사` survey=`recall_miss` expected=`망한 교단의 성기사` post=`여우비의 신 마커스 많이 아끼나보네`
- `11673086` `null_to_resolved` search=`ok` before=`None` after=`[림월드]변방계에서 회귀자로 살아남기` survey=`recall_miss` expected=`[림월드]변방계에서 회귀자로 살아남기` post=`랫따싶 칸시가 정실이엿으면`
- `11676317` `null_to_resolved` search=`ok` before=`None` after=`마도서를 줍다 마법사가 되다` survey=`recall_miss` expected=`마도서를 줍다 마법사가 되다 (방구석와룡, 문피아/네이버시리즈)` post=`마도서줍 그거 같아`
- `11681177` `null_to_resolved` search=`ok` before=`None` after=`격투 천재 여고생이 되었다` survey=`recall_miss` expected=`격투 천재 여고생이 되었다 (소설술사, 노벨피아)` post=`격투 천재 재밌다`
- `11682749` `resolved_to_different_title` search=`ok` before=`주인공인데 주인공이 아님` after=`묵향 다크레이디` survey=`wrong_work_among_aliases` expected=`묵향 (묵향 다크레이디)` post=`TS주인공인데 힘 쎄지는 템플릿이 어디서 나왔냐고?`
- `11694063` `resolved_to_different_title` search=`ok` before=`빙의한 신의 아이, 엘리시아` after=`엘리시아 전기` survey=`wrong_work_among_aliases` expected=`` post=`엘리시아가 아예 얀이 아니라`
- `11694067` `null_to_resolved` search=`ok` before=`None` after=`괴담에 휘말렸다` survey=`recall_miss` expected=`괴담에 휘말렸다` post=`김괴라리) 그롱 이 개새끼 그냥 죽어랏`
- `11695611` `null_to_resolved` search=`ok` before=`None` after=`여신이 나만 애호함` survey=`recall_miss` expected=`여신이 나만 애호함 (미츄리, novelpia.com/novel/346855)` post=`여신애호 디시콘도 내라는 것이야...!`
- `11697234` `null_to_resolved` search=`ok` before=`None` after=`검귀가 환생했더니` survey=`recall_miss` expected=`검귀가 환생함 (목마, 문피아)` post=`목마꺼 이번에 스타트 좋네`
- `11700475` `null_to_resolved` search=`ok` before=`None` after=`내 파티에는 미친년들만 꼬인다` survey=`recall_miss` expected=`내 파티에는 미친년들만 꼬인다 (novelpia.com/novel/398205)` post=`NTR`
- `11702084` `null_to_resolved` search=`ok` before=`None` after=`괴담 호텔 탈출기` survey=`recall_miss` expected=`괴담 호텔 탈출기 (노벨피아, 쿠크루) — 약칭 '담텔기/괴라리'` post=`담호텔기라리는 언제 완결날 각 보임?`
- `11703645` `null_to_resolved` search=`ok` before=`None` after=`남매근친물` survey=`recall_miss` expected=`남매근친물 (노벨피아/밀리언클래스, 작가 binibig=비니빅)` post=`오늘에 ts 맘마는~~~~~`
- `11703674` `resolved_to_different_title` search=`ok` before=`게임 속 도굴꾼이 되었다` after=`아카데미의 마피아가 되었다` survey=`wrong_work_among_aliases` expected=`아카데미의 마피아가 되었다` post=`아니 뭐야 아카데미 마피아 이거 씨즐꺼였네`
- `11706842` `resolved_to_different_title` search=`ok` before=`삼국지 마대 가 되었다` after=`대마법사였던것은 다시 대마법사를 꿈꾼다` survey=`wrong_work_among_aliases` expected=`대마법사였던것은 다시 대마법사를 꿈꾼다` post=`대마대는 언제 완결 날까`
- `11706852` `null_to_resolved` search=`ok` before=`None` after=`판타지 초보 법사` survey=`recall_miss` expected=`판초우의의 마법사 (문피아, 작가 하드폭발, 2026 연재; '판초법사'는 정착 약칭) — 웹확인됨` post=`개장빙들아 판초법사 잼나냐?`
- `11708466` `null_to_resolved` search=`ok` before=`None` after=`매국노` survey=`recall_miss` expected=`매국노 (노벨피아 추정, 동명 다수 존재로 불확실)` post=`매국노 본 게이들 질문 좀 와봐라 ㅇㅇ`
- `11708478` `resolved_to_different_title` search=`ok` before=`사연 있는 악역으로 착각 당한다` after=`머리 가 잘리셨습니다, 전하` survey=`wrong_work_among_aliases` expected=`내 설정 속의 대검영애가 되었다.` post=`사와요드릴머리영애등장 ㄷㄷ`
- `11710036` `resolved_to_different_title` search=`ok` before=`쳇바퀴의 생쥐 사도가 되었다` after=`변방계에서 회기자로 살아남기` survey=`wrong_work_among_aliases` expected=`[림월드]변방계에서 회귀자로 살아남기` post=`5시간 뒤면 랫따싶이 올까요?`
- `11710037` `null_to_resolved` search=`ok` before=`None` after=`괴담 호텔 탈출기` survey=`recall_miss` expected=`괴담 호텔 탈출기 (노벨피아 novel/102155, 작가 쿠크루)` post=`상식의 엇갈림 서술트릭 << GOAT임`
- `11710044` `null_to_resolved` search=`ok` before=`None` after=`가챠 중독자의 퓨전펑크 생활` survey=`recall_miss` expected=`가챠 중독자의 퓨전펑크 생활 (노벨피아 novel/387014, 작가 섦게지는꽃)` post=`가챠펑크 다음장이 아니였다고`
- `11718097` `resolved_to_different_title` search=`SEARCH_DEGRADED_RECOVERED` before=`라디오에서 우리의 노래가 나오면` after=`망겜의 힐러` survey=`wrong_work_among_aliases` expected=`망겜의 힐러` post=`망겜힐은 오행복 박태양이 빌런이였어야돼`
