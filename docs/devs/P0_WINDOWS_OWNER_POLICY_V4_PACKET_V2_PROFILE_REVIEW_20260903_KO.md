# P0 Windows owner policy V4 packet-V2 profile 검토

## 판정

최종 판정은 `ADOPT_COMPONENT_ONLY / NO_GO_AUTHORITY`다. owner policy V1~V3를 수정하지 않고, V3가 허용하던 operational signature wire와 packet/preauthorization V2의 wire가 달랐던 단절을 별도 V4 successor profile로 봉인했다.

- component manifest SHA: `9224e3c69c2748a882b81d5ccd29d02f3a9ad689e29a20ea6de6f100edbb9fc7`
- focused unittest: `32/32 PASS`
- adjacent owner/V2 묶음: `109/109 PASS`
- 정상 receipt: exact `78` fields, positive structural flags `20/20`, denial flags `22/22`
- actual credit: source/context `0/0`
- gate: `NO_GO_SIGNED_OWNER_POLICY_V4_PACKET_V2_PROFILE_ONLY`

## 닫은 wire-level 공백

기존 owner policy V3 operational key는 `ECDSA_P256_SHA256_CNG_V1`과 `p0-external-owner-preauthorization-signature/v1`을 허용했다. packet V2는 `ECDSA_P256_SHA256_CNG_P1363_LOW_S_V2`와 `owner-root-preauthorization-v2/signature/v1`을 요구한다. 따라서 V3를 정상 provision해도 V2를 그 정책의 승인된 wire로 해석할 수 없었다.

V4는 다음 material을 별도 policy/profile/signature/owner-anchor domain에 서명 결속한다.

- packet V2 public-key pin의 exact 19-field canonical bytes, artifact SHA, fingerprint, owner principal/anchor, key ID/epoch, P-256 point
- packet, Windows reader, preauthorization, supervisor, fixed-member 계약의 component SHA 5개
- V3 predecessor body·detached signature·61-field receipt의 raw/artifact SHA와 epoch
- project, trust domain, environment, purpose, owner principal
- packet key와 V3 bootstrap/operational/observer/owner-state 네 역할의 ID·fingerprint 분리
- bounded monotonic epoch, revocation floor, 최대 authorization TTL
- trusted time, revocation high-watermark, durable nonce, external root/code authority, OS write-deny, actual semantic evidence가 후속 실행에 필요하다는 truth table
- profile artifact SHA를 포함하는 V4 owner anchor

`public_apply`, WAL, 중앙 Slang DB write, production, full scan, P0 Exit, action applied는 모두 false다.

## 반대검토와 수정 이력

초기 후보는 focused test가 통과했지만 독립 red-team에서 owner principal 불일치, 무효 P-256 point, mutable dependency downgrade, packet key 역할 충돌, epoch rollback/overflow, V3 detached signature 미결속이 실제로 수용되어 `REJECT_AS_IS`를 받았다.

1차 수정 뒤에도 forged V3 receipt, local/upstream semantic constant 동시 치환, patched parent callable이 accepted되어 다시 `REJECT`됐다. 이를 막기 위해 V3 61-field receipt를 body/signature에서 독립 재구성하고 local semantic literal·own manifest·upstream manifest를 교차검증했다.

2차 수정 뒤에는 V3 helper와 packet private validator 치환을 차단했지만 `deployment.uuid` module alias와 `uuid.UUID` attribute를 바꾸면 잘못된 UUID chain이 통과했다. 최종판은 V3 세 module 검증 graph를 disassembly로 닫아 defined callable `70`, critical constant `137`, referenced global `520`, referenced attribute `66`, referenced function/code/default `68`을 진입·parent 반환·replay 반환·종료 시점에 확인한다. module alias·attribute·helper·late TOCTOU 공격은 최종 재심에서 모두 거부됐고 추가 material finding은 없었다.

## 증거의 한계

이 검증 graph는 presented component가 의존하는 런타임 치환을 fail-close하기 위한 구조 증거다. 동일 프로세스 공격자가 V4 자기 코드까지 임의로 바꿀 수 있는 상황에 외부 신뢰를 만들지는 않는다. receipt는 다음을 명시적으로 false로 둔다.

- predecessor bootstrap signature mathematics
- bootstrap/public pin의 독립·외부 provisioning
- fixed policy store 및 zero-input 관측
- trusted time·revocation high-watermark·durable nonce/replay state
- external root/code authority
- OS write-deny 및 process-wide runtime noninterference
- actual semantic evidence와 owner authority

따라서 다음 owner 단계는 새 receipt wrapper가 아니다. 외부 operator가 signed V4, 독립 bootstrap/pin, immutable fixed store, trusted time/revocation, durable nonce, root/code identity, OS write-deny를 실제 provision한 뒤 held-handle store에서 V4→pin→preauthorization V2 supervisor를 한 관측 구간에 연결해야 한다.

## 검증 경계

신규 모듈은 filesystem·network·subprocess·protected endpoint write를 수행하지 않는다. pure unittest와 정적 검증이므로 dashboard와 `--parallel 16` 적용 대상이 아니다. actual source/context는 계속 `0/40·0/20`, Pyserini BM25·gold-lite·retrieval/reranker/NIL A/B·production/full scan은 계속 닫힌다.
