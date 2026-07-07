# Loop513 unsafe_promotion INFO_MISSING 12건 source-native 판정

이 문서는 `docs/devs/loop513_unsafe_promotion_info_missing12_source_native_verdicts.json`의 사람용 요약이다. 새 runtime replay는 실행하지 않았고, shared promotion gate를 풀어도 되는지 source-native/native-web 근거로 다시 보았다.

## 요약

- 대상: `unsafe_promotion_from_hold` INFO_MISSING `12`건
- 결과: `ACCEPT 7`, `REPROCESS 5`, `HOLD 0`
- gate: `REVIEW-LOCKED`
- full_scan_approval: `false`

## 판정

| post_id | label | 선택 | 의미 |
| --- | --- | --- | --- |
| `11658621` | `REPROCESS` | `HOLD` | title similarity와 character image만으로 C1 publish 부족 |
| `11660238` | `ACCEPT` | C1 `무림마조` | `림조`/한서진/청월 직접 맥락 |
| `11668324` | `REPROCESS` | C1 `니들 생각 다 들린다` | C1은 지지되지만 `김괴라리`와 함께 나온 다작품 질문 |
| `11677957` | `ACCEPT` | C1 `음악 천재가 불륜을 못 숨김` | `페도부이` 작가 표면과 native-web이 C1을 지지 |
| `11687635` | `ACCEPT` | C1 `아포칼립스의 던전주가 되었다` | 이미지 OCR explicit work title과 공식 URL |
| `11690855` | `REPROCESS` | `HOLD` | 림버스 게임 유저수 글을 팬픽 제목으로 과승격 |
| `11705256` | `ACCEPT` | C1 `하남자의 탑 공략법` | `하남자 탑` 직접 약칭과 리뷰 맥락 |
| `11705257` | `ACCEPT` | C1 `히어로 IN 히로인` | `히로히로 팬아트` native-web 근거 |
| `11708466` | `ACCEPT` | C1 `매국노` | 직접 제목과 하루토/이설/유하은 캐릭터 맥락 |
| `11710044` | `REPROCESS` | `HOLD` | `가챠펑크`는 C1이 아니라 다른 퓨전펑크 계열 충돌 |
| `11714913` | `ACCEPT` | C1 `전 버튜버가 하고 싶은데요` | `주서연` 캐릭터 표면과 official detail 결합 |
| `11718105` | `REPROCESS` | C1 `몰락민족의 천재 기사` | C1은 지지되지만 플랫폼 목록/다작품 맥락이라 단일 publish 불완전 |

## 다음

- 이 verdict를 반영하면 placeholder INFO_MISSING은 `53 -> 41`이 된다.
- 남은 source-native/blind review는 `safe_loss_resolved_to_null 41`이다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
