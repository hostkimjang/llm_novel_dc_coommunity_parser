# P0 seed8 권리·접근 준비도 검토

관측 시각: 2026-09-03 22:52~22:56 KST

## 판정

현재 운영상 자동 capture 승인은 `0/8`이다. Arca wiki 1건만 라이선스 경로가 확인된 `CONDITIONAL_CLEARANCE_CANDIDATE`이고, DC 2건·FMKorea 1건·Tanma 4건은 서면 허가 또는 명시적 재사용 근거 전 `NO_GO_PERMISSION_REQUIRED`다. HTTP 200과 robots 허용은 저작권·AI 이용·장기 보존 허가로 해석하지 않는다.

이번 검토는 exact URL의 응답 상태·header·title·정책 신호만 읽었다. 본문 body를 저장소나 디스크에 보존하지 않았고, 법률 의견이 아니라 보수적인 연구 엔지니어링 gate다.

| seed 계열 | 현재 접근 관측 | 권리·보존 신호 | 보수적 gate |
| --- | --- | --- | --- |
| Arca wiki 1건 | `200`, HTML, 무리디렉트 | `/w/` robots 허용, 페이지에 CC BY-SA 4.0 표시, 응답 `no-store` | `CONDITIONAL_CLEARANCE_CANDIDATE / OPERATIONAL_NO_GO` |
| DC 2건 | 각각 `200`, HTML, 무리디렉트 | 현행 약관이 crawling과 AI 데이터 이용에 사전 서면 합의를 요구하고 게시물 권리는 작성자에게 둠 | `NO_GO_PERMISSION_REQUIRED` |
| FMKorea 1건 | 로컬 `200`, crawler `429`도 관측 | generic robots 차단, `noarchive`, HTTP `no-store`, 내부 연구 재사용 라이선스 미확인 | `NO_GO_PERMISSION_REQUIRED` |
| Tanma 4건 | 모두 `200`, HTML, 무리디렉트 | robots 허용이나 `by 탄마` 외 재사용 라이선스 미확인 | `NO_GO_PERMISSION_REQUIRED` |

## 근거 URL과 적용 범위

- Arca: [exact seed page](https://arca.live/w/novelchannel/%EC%86%8C%EC%84%A4%20%EC%B6%95%EC%95%BD%EC%96%B4), [robots.txt](https://arca.live/robots.txt), [정책](https://arca.live/policy), [CC BY-SA 4.0 법전](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en)
- DCInside: [robots.txt](https://gall.dcinside.com/robots.txt), [현행 약관](https://nstatic.dcinside.com/dc/w/policy/policy_index.html)
- FMKorea: [robots.txt](https://www.fmkorea.com/robots.txt), [약관](https://www.fmkorea.com/policy)
- Tanma: [robots.txt](https://tanma.kr/robots.txt), [가나다라](https://tanma.kr/data/webnovel_terms_ganadala.html), [마바사](https://tanma.kr/data/webnovel_terms_mabasa.html), [아자차](https://tanma.kr/data/webnovel_terms_ajacha.html), [카타파하](https://tanma.kr/data/webnovel_terms_katapaha.html)

Arca 조건부 경로도 즉시 capture 승인이 아니다. text-only, revision 고정, title-author-source-license(TASL) attribution, ShareAlike/publication 정책, 외부 asset 제외, 개인정보 최소화와 owner retention 승인이 모두 필요하다. `no-store`가 HTTP cache 지시인지 연구 원본 보존에도 적용되는지 owner/legal이 명시적으로 판정하기 전에는 nonvolatile raw 저장을 열지 않는다.

DC는 robots의 일반 허용 여부와 무관하게 약관상 서면 합의가 선행돼야 한다. FMKorea는 generic automated capture를 시도하지 않고 플랫폼·작성자 권리와 retention 승인을 요구한다. Tanma 4쪽은 한 owner/catalog lineage이므로, 허가가 오더라도 exact 4 URL·version·research/derivation/retention/publication 범위를 함께 명시해야 한다.

## 발견한 계약 공백

현재 HTTP intake는 HTTP `Date/Last-Modified`만 source timestamp evidence로 받는다. 그러나 HTTP `Date`는 수신 시각이고, FMKorea의 `Last-Modified`처럼 조회 시각에 가까운 값은 source revision 근거가 아닐 수 있다. actual 단계에서는 page-native published/modified/version evidence를 별도 artifact로 묶고 transport time과 분리해야 한다.

opaque rights/retention SHA만으로는 승인 의미를 검증할 수 없다. 후속 authorization artifact에는 exact URL, policy·robots URI와 bytes SHA/observed-at, 권리 주체와 basis, 허용 목적·추출 범위·derivative/publication 조건, TTL·삭제·takedown, truthful UA·rate, mature/privacy 처리를 canonical하게 넣어야 한다.

DC/FMK full HTML에는 article 외 광고·목록·닉네임·부분 IP·세션성 chrome이 포함될 수 있다. 승인 뒤에도 cookies/login/assets/comments를 제외하고, raw escrow 최소 TTL과 article-text 최소화 원칙을 사용한다. Arca↔DC backup과 Tanma 4쪽은 각각 같은 lineage라 독립 vote로 중복 계산하지 않는다.

## 다음 gate

1. 외부 owner가 site별 권리·retention authorization artifact와 policy/robots snapshot을 서명한다.
2. Arca는 조건부 요구를 모두 만족할 때만 text-only capture 후보가 된다. 나머지 7개는 명시적 site/author permission 전 HOLD한다.
3. capture 시 exact redirect/status/MIME/encoding/bytes SHA와 transport time, page-native revision을 분리해 기록하고 403/429/challenge에서 즉시 중단한다.
4. 권리와 retention이 모두 검증된 행만 capture credit 후보가 된다. source40/context20 및 human review 전 semantic·metric·P1·production credit은 0이다.
