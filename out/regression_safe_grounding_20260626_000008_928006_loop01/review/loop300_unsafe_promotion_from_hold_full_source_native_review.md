# Loop300 unsafe_promotion_from_hold full source-native verdicts (26/26)

- gate: `REVIEW-LOCKED`
- semantic_quality: `REVIEW-LOCKED`
- full_scan_approval: `false`
- batch review rows: `26`
- reviewed rows: `26`
- unreviewed batch rows: `0`
- validation issues: `0`

## Bucket counts

- `unsafe_promotion_from_hold`: `26`

## Label counts

- `ACCEPT`: `12`
- `REPROCESS`: `14`

## Source-native verdict counts

- `after_correct_source_native`: `12`
- `after_wrong_hold_preferred`: `14`

## Rows

- `11657046` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 마블/슈퍼맨/배트맨/스파이더맨 같은 슈퍼히어로 일반 담론이다. 후보 `[블루아카이브] 키보토스 속 슈퍼히어로가 되었다`를 직접 지지하는 작품명, 약칭, 인물, URL 앵커가 없다.
- `11658621` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 실제 이름을 못 쓰는 문제와 편결 도전 여부를 말한다. 후보 `무능한게 아니라 전설이였다고?`의 직접 title surface나 작품 고유 앵커가 없다.
- `11658668` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 문피아 수정/내림을 둘러싼 운영·작가 태도 이야기다. 후보 `전 버튜버가 하고 싶은데요`를 작품으로 특정할 직접 표면이나 URL 근거가 없다.
- `11669928` `ACCEPT` `after_correct_source_native` selected=`탑의 성좌들이 날 애호한다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목 `탑성좌애호`는 후보 `탑의 성좌들이 날 애호한다`의 압축 표면이고, 본문도 노벨피아 연중 여부를 말한다. after 승격은 source-native 정답으로 볼 수 있다.
- `11671490` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 림월드 게임과 특정 작가가 그 게임을 즐긴다는 커뮤니티 농담이다. 후보 `게임이 자꾸 사람을 구원함`을 현재 글의 논의 작품으로 확정할 직접 작품 앵커가 없다.
- `11671501` `ACCEPT` `after_correct_source_native` selected=`판타지 초인 법사` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `판초법사`는 `판타지 초인 법사` 약칭으로 읽히고, 본문·댓글도 게이트가 막 열린 시점과 국군/정부 반응 같은 작품 전개를 직접 논한다.
- `11674703` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문 제목과 본문은 `도굴왕` 애니화 난이도와 전투씬 비중을 직접 말한다. 후보 `신의 의지가 깃든 물건`은 원문 후보 목록에 없고, source-native 정답 후보도 아니다.
- `11687618` `ACCEPT` `after_correct_source_native` selected=`아카데미 생존 갤러리` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `아생갤`과 본문 인물 `라나`, `엘리`, `클레어`, `아레스`가 후보 `아카데미 생존 갤러리`에 결속된다.
- `11690874` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문 제목의 `전검`은 후보 `내 인생이 끝장날 때까지`가 아니라 별도 약칭으로 보인다. after 후보는 문장 일부 `끝장날 때까지`에 끌린 오귀결이므로 hold가 맞다.
- `11695623` `ACCEPT` `after_correct_source_native` selected=`[림월드]변방계에서 회귀자로 살아남기` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `랫따싶`과 본문/댓글의 작품 내 인물·반응 맥락이 후보 `[림월드]변방계에서 회귀자로 살아남기`를 지지한다.
- `11695639` `ACCEPT` `after_correct_source_native` selected=`TS 당 해서 인방 을 해봅니다.` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목과 댓글 `제목이`, `https://novelpia.com/novel/362860`이 후보 URL을 직접 지지한다.
- `11697231` `ACCEPT` `after_correct_source_native` selected=`아카데미 생존 갤러리` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목이 `아생갤`을 직접 언급하고, 본문도 작품의 현실쪽 위기 설정을 해석한다. 후보 `아카데미 생존 갤러리` 승격은 source-native 정답이다.
- `11700495` `ACCEPT` `after_correct_source_native` selected=`이 무림의 미친년은 나야` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `서문청`은 후보 작품의 직접 인물 앵커로 보이며, 후보 `이 무림의 미친년은 나야`와 결속된다. 다만 search degraded 복구 전에는 full approval로 승격하지 않는다.
- `11703657` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문과 댓글은 다른 노벨피아 URL `https://novelpia.com/novel/405310`을 직접 제시한다. batch 후보 C1/C2는 이 URL과 맞지 않으므로 현재 후보 승격은 안전하지 않고 hold/re-judge가 필요하다.
- `11706832` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 `황제분충`이 문피아/노피아 작품인지 묻고 댓글도 `노피아`라고 답한다. 후보 `엄마가 계약결혼 했다`는 카카오페이지 URL이며 source-native 맥락과 맞지 않는다.
- `11658637` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 `재막아`, 영기, 윤기, 진양철을 통해 `재벌집 막내아들` 계열을 말하지만, 후보 `일본 재벌집 막내아들`의 `일본` 특정 title surface나 URL 앵커는 source-native로 확인되지 않는다. after 승격은 같은 계열/인물 신호를 과확장한 것으로 보고 hold/re-judge가 필요하다.
- `11660238` `ACCEPT` `after_correct_source_native` selected=`무림마조` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `림조`와 본문 `한서진`, `청월`, 200화 맥락이 후보 `무림마조`의 작품/등장인물 신호와 결속된다. 공식 URL도 동일 title을 지지하므로 source-native 정당 해소로 본다.
- `11668324` `ACCEPT` `after_correct_source_native` selected=`괴담에 휘말렸다` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `김괴라리`는 `괴담에 휘말렸다`와 작가 김갈비뼈를 묶어 부르는 장갤 약칭으로 확인된다. `니생들`과 함께 언급된 다중 비교 맥락은 있지만, 후보 C1은 source-native로 정당한 작품 후보이므로 after 승격은 정당 해소로 분리한다.
- `11673086` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 `랫따싶`, 칸시, 시트러스, 피갈을 직접 말하므로 `[림월드]변방계에서 회귀자로 살아남기` 쪽 신호다. after 후보 `어느날 자고 일어났더니 포켓몬스터 게임 속 주인공의 라이벌 캐릭터가 되어 있었다`는 source-native 맥락과 맞지 않는다.
- `11674712` `ACCEPT` `after_correct_source_native` selected=`이 무림의 미친년은 나야` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `서문청`, `주서연` 비교와 댓글의 내공/호각 대화가 후보 `이 무림의 미친년은 나야`에 결속된다. 이 행은 Loop288에서 진동 이력이 있으므로 full approval이 아니라 source-native 정당 해소 후보로만 둔다.
- `11677913` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 남캐 일러스트와 `캇트` 반응을 말하지만, 후보 `이세계 검은머리 똥양인`을 직접 지지하는 작품명/URL 앵커가 없다. 이미지 의존 가능성이 있으므로 native image 확인 전까지 hold가 맞다.
- `11685985` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 고양이/홍어 수인 농담과 이미지 반응에 가깝고, 후보 `공작의 반려 수인 이 되었습니다`를 작품으로 확정할 직접 title surface나 공식 URL 앵커가 없다. `수인` 일반어 기반 승격으로 보고 hold/re-judge가 필요하다.
- `11685995` `ACCEPT` `after_correct_source_native` selected=`림월드 변방계에서 회귀자로 살아남기` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 댓글에서 post author가 `랫따싶`이라고 직접 답하고, 이어 `가챠펑크맛`은 비교/맛 설명으로 보인다. 공식 페이지도 `랫따싶` 태그와 `[림월드]변방계에서 회귀자로 살아남기` 제목을 지지하므로 after title은 source-native 정당 해소로 볼 수 있다. 다만 after URL이 비어 있어 full approval 근거는 아니다.
- `11695637` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 `알파카랑 눈싸움 하지마라`와 본문 `헙`뿐이며, 후보 `도네하지 마라`를 직접 지지하는 작품명/캐릭터/URL 앵커가 없다. `하지마라` 문장 표면만으로 public title을 확정한 과승격으로 본다.
- `11705261` `ACCEPT` `after_correct_source_native` selected=`이세계 TRPG 게임마스터` action=`exclude_from_regression_count_after_gate_wiring`
  - 근거: 원문 제목의 `이티알`은 `이세계 TRPG 게임마스터` 축약으로 읽히고, `루루`, 댓글의 `로데우스`도 같은 작품 토론 맥락을 보강한다. 공식 URL도 동일 title을 지지하므로 source-native 정당 해소다.
- `11718105` `REPROCESS` `after_wrong_hold_preferred` selected=`None` action=`repair_unsafe_promotion`
  - 근거: 원문은 시리즈 출시 대기와 작가/작품군 화제이며 댓글도 `트럭커`, `몰락`, `망배우`를 함께 묻는다. 후보 `미쳐버린 판타지에서 사제로 살아남기`를 단일 현재 작품으로 확정할 직접 title surface가 없어 hold/re-judge가 맞다.

## Gate 해석

이 검토는 collateral P0 bucket의 source-native 라벨 산출물이다. REPROCESS/HOLD 또는 validation issue가 남아 있으면 full collateral approval은 열리지 않는다.
