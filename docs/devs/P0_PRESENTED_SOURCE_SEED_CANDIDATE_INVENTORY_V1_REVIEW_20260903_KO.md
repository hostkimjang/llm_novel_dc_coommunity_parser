# P0 presented source seed candidate inventory V1 검토

## 판정

최종 판정은 `ADOPT_COMPONENT_ONLY / NO_GO_SOURCE_CAPTURE_AND_SEMANTIC_CREDIT`다. 이 tranche는 조사에서 제시된 URL 8개를 캡처 전 후보 목록으로 고정한다. source bytes를 가져오거나 HTML을 파싱하지 않았고, source 사실성·권리·독립성·semantic label을 승인하지 않는다.

- component manifest SHA: `52dcabd17c6d512643648e535f07cea4ab36e0af4f506da2a436150f356f219d`
- focused unittest: `24/24 PASS`
- Track: A `3`, B `5`
- candidate lineage family: `4`
- eligible actual independence group: `0`
- actual source claim / A-context review: `0/40`, `0/20`
- derived index / metric denominator: `0`, `0`
- gate: `NO_GO_PRESENTED_SOURCE_SEEDS_ONLY`

## 고정한 후보 범위

Track A는 작품 alias 후보, Track B는 커뮤니티 용어 후보라는 조사 방향일 뿐 정답 label이 아니다.

1. [Arca novelchannel 소설 축약어](https://arca.live/w/novelchannel/%EC%86%8C%EC%84%A4%20%EC%B6%95%EC%95%BD%EC%96%B4)
2. [DC genrenovel 7614173](https://gall.dcinside.com/mgallery/board/view?id=genrenovel&no=7614173)
3. [FMKorea 9330585139](https://www.fmkorea.com/9330585139)
4. [DC tgijjdd 217475](https://gall.dcinside.com/mgallery/board/view/?id=tgijjdd&no=217475)
5. [Tanma 가나다라](https://tanma.kr/data/webnovel_terms_ganadala.html)
6. [Tanma 마바사](https://tanma.kr/data/webnovel_terms_mabasa.html)
7. [Tanma 아자차](https://tanma.kr/data/webnovel_terms_ajacha.html)
8. [Tanma 카타파하](https://tanma.kr/data/webnovel_terms_katapaha.html)

Arca와 DC 백업은 같은 lineage family로, Tanma 네 페이지도 같은 publisher/catalog family로 접는다. 따라서 URL 8개를 독립 근거 8표로 세지 않는다. 모든 행은 `PRESENTED_UNVERIFIED`, `NOT_ATTESTED`, `NOT_RUN`, `UNKNOWN_FAIL_CLOSED`, `REFERENCE_CANDIDATE_ONLY` 상태다. `아생갤` 같은 표면만으로 특정 작품이나 현실 갤러리 target을 만들 수 없도록 truth·target·definition·judgment 필드를 금지했다.

## legacy 품질 인벤토리

다음 7개 artifact의 현재 path·bytes·SHA를 producer manifest와 독립 parent에 각각 고정하고 raw bytes에서 통계를 다시 계산한다.

| pool | 관측 | 사용 가능 범위 |
| --- | --- | --- |
| golden18 | `18`행, candidate/NIL/UNJUDGED `9/6/3` | legacy label 후보, metric 불가 |
| source refresh | `39`행, URL reference `87`, pending `39` | capture 후보 |
| judge shadow | `1,505`행, candidate-positive `0`, public-title `198`, evidence `2`, web-unverified `649` | 오류 triage 후보 |
| reserved P01/P02 | 두 파일 모두 exact empty | 분모 기여 없음 |

다섯 pool은 grain이 달라 합산하지 않는다. `combined_unique_denominator=null`, metric denominator `0`이다. readiness가 고정한 label-ledger SHA `717c6e52…c1102`와 현재 raw SHA `b7e75467…5998`의 차이는 `LEGACY_LABEL_LEDGER_SHA256_BINDING_STALE` blocker로 남겼고 자동 재봉인하지 않았다.

## 전문가 회의와 반대검토

검색·데이터·통계·MLOps 회의는 actual capture가 없는 상태에서 가짜 HTML parser나 gold-lite를 만드는 안을 기각하고 candidate inventory만 채택했다. 첫 red-team은 세 legacy artifact를 함께 재봉인하면 stale blocker와 18/9/6/3 통계를 바꿀 수 있음을 재현해 `REJECT_UNTIL_FIXED`를 냈다.

수정판은 7개 artifact identity를 독립적으로 고정하고, bool/count 위조와 row 재계산 불일치, 빈 파일 변경, pool 합산, URL·lineage·status·semantic 승격 공격을 거부한다. 최종 독립 재심은 actionable finding 없이 `ADOPT_COMPONENT_ONLY / NO_GO`를 냈다.

## 검증과 비간섭 경계

- producer와 producer-import 없는 parent가 exact URL·lineage·통계·receipt를 각각 재생한다.
- contract/parent/test SHA는 각각 `010c1bf0…92ad`, `ea9bc3d6…2b54`, `0b6589ac…dd4`다.
- 신규 모듈은 filesystem·network·environment·clock·random·subprocess를 직접 사용하지 않는다.
- pure unittest와 정적 byte/hash 검증이므로 dashboard와 `--parallel 16` 적용 대상이 아니다.

이 단계는 actual source registry 완료가 아니다. 다음 data gate는 외부 권한이 있는 전용 root에 raw response, final URL, redirect chain, content type, source timestamp, rights/retention, byte locator를 캡처한 뒤 profile별 offline adapter conformance를 검증하는 것이다. 그 전에는 actual credit, Pyserini BM25, gold-lite, retrieval/reranker/NIL A/B, production/full scan을 열지 않는다.
