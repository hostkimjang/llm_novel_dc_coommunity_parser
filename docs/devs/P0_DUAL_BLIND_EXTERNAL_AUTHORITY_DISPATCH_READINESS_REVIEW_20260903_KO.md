# P0 이중맹검 외부 권한·dispatch 준비도 검토

작성일: 2026-09-03 KST
판정: `DOCUMENT_EXTERNAL_PROVISIONING_BLOCKER / DISPATCH_SUCCESSOR_DESIGN_ADOPTED / IMPLEMENTATION_DEFERRED / ACTUAL_REVIEW_AND_P1_NO_GO`

## 결론

presented dual-blind precommit 다음 단계로 실제 reviewer dispatch를 바로 구현하지 않는다. 현재 호스트에는 review policy·lease·final attestation·reviewer key를 외부에서 고정한 review-authority store가 없고, zero-input owner preflight 두 경로가 모두 `FIXED_STORE`에서 fail-closed 됐다. 이 상태에서 self-hashed receipt, process-local one-shot state 또는 caller-presented key를 한 겹 더 감싸는 코드는 external authority·trusted time·revocation·durable replay·ACL isolation 중 어느 것도 새로 증명하지 못한다.

이번 회차는 새 runtime 코드를 추가하는 대신 다음 세 가지를 채택한다.

1. current-host blocker와 실제 receipt를 재현 가능한 근거로 고정한다.
2. 기존 bulk queue 직접 재사용을 기각하고, external provisioning 뒤 CSPRNG task-ID 재결속부터 시작하는 dispatch successor의 exact 경계를 고정한다.
3. primary `80`, pair `40`, disagreement `D`, reserve `D`, final `40` 상태기계와 metric 금지 조건을 결과 전에 고정한다.

실제 상태는 primary terminal `P=0/80`, two-terminal pair coverage `T=0/40`, both-`JUDGED` pair `J=0/40`, `D=null`, reserve terminal `R=0`, final judged `F=0/40`이다. actual source/context credit는 `0/40·0/20`이고 P0·production·full scan·Pyserini BM25·gold-lite·retrieval/reranker/NIL은 모두 `NO_GO`다.

## current-host 관측

서비스 설치·시작, ACL·policy·store 변경, nonce 소비는 수행하지 않았다. 공개 인자가 없는 read-only observer만 실행했다.

| observer | 실제 결과 | receipt SHA-256 | 해석 |
| --- | --- | --- | --- |
| fixed owner-policy store | watched directory `CreateFileW` Windows error 2, fail-closed | receipt 미발급 | 고정 store 자체가 없음 |
| owner policy v3 preflight | `decision=NO_GO`, `failure_stage=FIXED_STORE` | `da914d27db0f1694c6d1fc65953bd74e8b93e186693847b493ab6c4196a1b1ad` | v3 policy·native observer·external provisioning 미검증 |
| owner provisioning preflight | `decision=NO_GO`, `failure_stage=FIXED_STORE` | `bbed3cdd9d309f22db22fe9607b9000f31d924b8ed3c677b9dbbfadf2351a172` | v2 store·SCM/image/token/WDAC/provider/trusted state 미검증 |
| actual readiness blocker compiler | `decision=NO_GO`, actual source/context `0/40·0/20` | `104d7c58271c7d7ae20d00badeb09185023eff344f37fe05eef1867d2c93a501` | P0·production·full scan false, endpoint pre/post match |

v3 blocker는 fixed store, v3 policy, positive native-observer profile, native IPC/SCM host, Authenticode/catalog, WDAC/UMCI identity, TPM/KSP, trusted time·revocation·nonce, single-interval host binding, external owner provisioning이다. provisioning preflight도 fixed store, v2 policy, service config/image/token, embedded bootstrap resource, Authenticode, WDAC/UMCI, loaded CNG provider, trusted time·revocation, signed observer, single interval, external provisioning을 모두 미검증으로 남긴다.

이 값은 현 시점의 current-host 사실이다. 외부 운영자가 상태를 provision하면 receipt가 달라져야 하며, 과거 receipt를 positive 증거로 재사용해서는 안 된다.

## 기존 구성요소 감사

| 구성요소 | 재사용 범위 | 기각한 승격 |
| --- | --- | --- |
| dual-blind campaign precommit + independent parent | exact 40입력, 120 assignment, private/public projection, fixed guideline·response schema 재검증 | opaque ID 난수성, reviewer blinding, dispatch isolation, 사람 심사 |
| neutral-review signature math | fixed role/purpose/domain, canonical raw, P-256 low-S 수학 | 외부 key provisioning, trusted time, revocation, replay 방지 |
| Windows binary ACL projection | held handle의 owner/group/DACL/control/ACE 관측 primitive | reviewer별 접근 통제와 no-list 사실성 |
| fixed directory/store observer | handle identity·stable read·watch 패턴 | 기존 P0 owner store를 review-authority store로 재명명 |
| external trust nonce executor | caller-selected store 안의 `O_EXCL` 소비와 failure-burn 패턴 | power-loss/cross-process/cross-host durable CAS, 외부 신뢰 |
| process-local one-shot state | same-call exact-object handoff 패턴 | serialized receipt 재입력, restart-safe lease |
| 기존 blind adjudication 도구 | OS CSPRNG challenge·exclusive output·readback 결속 패턴 | multirow packet을 이 캠페인의 reviewer dispatch로 직접 사용 |

owner fixed-store operational key는 owner-preauthorization 전용 domain만 허용하고 review lease는 별도 `REVIEW_LEASE_SIGNING_ONLY / P0_NEUTRAL_REVIEW_LEASE` role/domain을 쓴다. 따라서 owner operational key나 기존 owner receipt를 lease signer authority로 치환할 수 없다. fixed-store observer의 private handles/watches도 반환 전에 닫히므로 후속 wrapper가 single-interval store/lease 관측을 주장할 수 없다.

## 전문가 회의와 채택·기각

### 검색·맹검 분과

whole task inventory가 reviewer에게 노출되면 동일 payload bytes/SHA만으로 같은 입력의 primary 두 건과 reserve 한 건을 묶을 수 있다고 지적했다. 현재 64-hex task ID는 형식만 검증하며 caller가 sequence·slot·reviewer 관계를 ID에 넣는 covert channel도 막지 않는다. 기존 residual/action/hardcoded-alias queue는 `post_id`, expected title, candidate/alias registry 또는 parser disposition을 포함하므로 이 캠페인에 직접 연결하지 않는다.

채택 의견은 OS CSPRNG opaque handle, campaign-wide durable uniqueness ledger, reviewer-principal binding, task당 단일 object, no-list ACL 또는 audience encryption, signed single-use lease, trusted dispatcher CAS receipt를 새 schema로 설계하는 것이다. traffic correlation까지 위협 모델에 포함하면 fixed-size padding/bucketing과 timing policy가 추가로 필요하다. reviewer 간 자발적 공모·화면 공유는 기술적 ACL만으로 보장하지 않고 별도 운영 독립성 권한으로 남긴다.

### MLOps·권한 분과

필요한 successor 설계에는 동의하지만 fixed review-authority state가 없는 현 호스트에서 구현하는 것은 기각했다. 공개 receipt와 process-local state를 합성해도 외부 provision·trusted time·revocation·reboot-safe nonce가 생기지 않는다. 따라서 `DOCUMENT_EXTERNAL_PROVISIONING_BLOCKER`를 이번 구현 판정으로 채택했다. 사후 반대심사에서는 trust store와 mutable CAS 분리, read-only preflight와 state-changing executor 분리, CSPRNG ID 재결속 우선 순서를 반영해 최종 `ADOPT`했다.

### 통계·결과 프로토콜 분과

primary review opportunity `80`, primary-pair input `40`, 최대 reserve capacity `40`, 실제 required adjudication denominator `D`, final input `40`을 서로 바꾸어 세지 않는다. lease/fetch/result authority가 없는 presented result는 terminal·pair·D 어느 분모에도 기여하지 않는다. exact 상태 전이는 아래 규칙만 허용한다.

사후 반대심사는 검색 분과가 ID/lease ordering과 store/CAS 혼동을 `REVISE`, 통계 분과가 pair 대수·final-gold·expiry origin을 `REVISE_NARROW`로 돌려보냈고 모두 본문에 반영했다. MLOps 분과가 lease issuance·object activation의 linearization point를 추가 요구해 아래 transaction 계약으로 고정했다. 최종 세 분과 판정은 `ADOPT`다.

## 결과 상태기계

1. **Precommit**: 40개 입력마다 `PRIMARY_A`, `PRIMARY_B`, reserve를 결과 전에 고정한다. 이 단계 실제 terminal은 0이다.
2. **Primary delivery**: authority-qualified lease와 single-task fetch receipt가 있는 assignment만 결과 제출 기회를 얻는다. 전달 실패를 다른 reviewer나 reserve로 backfill하지 않는다.
3. **Primary terminal freeze**: assigned reviewer가 서명한 결과는 `JUDGED/UNAVAILABLE`만 허용한다. 응답 없이 lease가 끝난 `UNJUDGED`는 별도 `LEASE_EXPIRY_TERMINAL_ATTESTATION` role/domain의 trusted authority가 lease·fetch durable-CAS event를 결속해 생성하며 actual human review count에는 기여하지 않는다. 첫 authority-qualified terminal을 원문 그대로 동결하고 80개가 모두 동결되기 전 parser projection과 비교하지 않는다.
4. **Pair closure**: 각 입력의 두 primary terminal이 모두 존재하는 수를 terminal pair coverage `T`로 센다. 두 terminal이 모두 `JUDGED`인 수 `J`와 분리한다. 어느 한쪽이 nonjudged이면 `T`에는 남지만 `J`와 final에는 기여하지 않고, disposition은 `INCOMPLETE_NO_FINAL_JUDGED_RESULT_PRIMARY_TERMINALS_RETAINED`이며 reserve가 대체하지 않는다.
5. **D 산정**: 두 primary가 모두 authority-qualified `JUDGED`인 pair에서만 canonical full-gold set을 비교한다. exact set이 다른 입력 수가 `D`다. 그 전 `D`는 반드시 `null`이다.
6. **Reserve activation**: precommitted reserve 중 정확히 `D`건만 새 single-task lease로 활성화한다. peer result와 parser observation은 reserve에게 공개하지 않는다.
7. **Final gold 선택**: canonical set이 같은 both-judged primary pair는 그 공통 set을 final gold로 쓴다. 서로 다른 pair는 authority-qualified reserve가 `JUDGED`일 때 reserve complete set을 final gold로 쓴다. 세 set이 모두 달라도 reserve set이 adjudicated final이며, reserve가 nonjudged이면 해당 입력은 final judged가 아니다.
8. **Final attestation**: 아래 상태 대수, primary terminal `P=80`, terminal pair coverage `T=40`, both-judged pair `J=40`, reserve terminal `R=D`, reserve judged `A=D`, final `F=40`과 모든 raw predecessor를 결속한다.
9. **Metric gate**: external authority와 나머지 source/frame/runtime owner gate까지 통과한 뒤에만 사람 gold와 metric 적격성을 별도 compiler에서 판단한다. incomplete/unauthorized result를 complete-case 방식으로 버리고 metric을 계산하지 않는다.

상태 대수는 다음과 같다.

- `P`: authority-qualified primary terminal 수, `0..80`
- `T`: 두 primary terminal이 모두 존재하는 입력 수, `0..40`
- `J`: 두 primary가 모두 authority-qualified `JUDGED`인 입력 수, `0..T`
- `D`: `P=80` 동결 전 `null`; 이후 `J` 중 canonical full-gold set이 다른 입력 수
- `E=J-D`: 두 primary가 합의한 final judged 입력 수
- `R`: D seal 뒤 정확한 D 대상에서 얻은 reserve terminal 수, `0..D`
- `A`: reserve terminal 중 authority-qualified `JUDGED` 수, `0..R`
- `F=E+A`: final judged input 수

제약은 `0≤D≤J≤T≤40`, `0≤A≤R≤D`, `0≤P≤80`이다. `T`는 authority-qualified P inventory의 exact unique two-slot pair에서만 파생되므로 `T=40 ⇔ P=80`이다. 따라서 `F=40 ⇔ P=80 ∧ T=40 ∧ J=40 ∧ R=D ∧ A=D`다. `D=0`이면 `R=A=0`이어야 한다. `UNAVAILABLE/UNJUDGED`는 ITT와 terminal coverage에는 남지만 `J/F`에는 기여하지 않는다. 기존 presented result와 합성 fixture는 새 precommit·lease predecessor·trusted chronology가 없으므로 `P/T/J/D/R/A/F` 어느 값에도 기여하지 않는다.

## 외부 운영자 provisioning 계약

다음 두 상태면을 이 저장소가 self-provision하지 않는다. 서로 다른 root identity·ACL·service principal·rollback/fork detection·receipt를 가져야 한다.

### Immutable review-authority trust store

- externally pinned fixed root identity와 read-only exact inventory
- campaign-policy, review-lease, lease-expiry-terminal, final-attestation signer의 서로 다른 key ID·fingerprint·principal·role/domain
- reviewer 3~16명의 distinct result-signing key와 실제 auth principal/SID binding
- signing과 분리된 reviewer별 encryption/key-agreement pin 또는 동등한 audience-bound ACL
- monotonic policy/key epoch, signed revocation high-watermark와 rollback protection
- 외부 trusted time authority와 not-before/expiry 검증 정책
- dispatcher service code/image, Authenticode/catalog, WDAC/UMCI, service SID/token, loaded crypto provider 정책
- 운영상 reviewer 독립성·공모 통제 정책과 감사 주체

### Mutable durable state service/journal

- opaque-ID campaign uniqueness, nonce, lease state와 fetch count를 원자 갱신하는 CAS API
- crash/reboot/cross-process/cross-host durability와 fork/rollback detection
- previous/new journal head, mutation kind, externally authenticated service principal과 trusted-time receipt
- 동일 task/lease의 duplicate issue·fetch·result-freeze를 거부하는 상태 전이

두 root는 기존 packet root, run root, 중앙 Slang DB와 publication journal 밖에 있어야 한다. test fixture나 개발자 생성 key/state를 external provision으로 세지 않는다. trust store는 immutable/read-only이고 CAS state plane만 명시적 transaction으로 변경한다. 첫 state-changing successor 전에는 두 면의 root/principal/policy/time/revocation/code identity를 read-only external readiness observer로 새로 관측한다. 이 관측은 lease nonce를 소비하지 않는다.

## provisioning 뒤 첫 bounded successor: opaque task 재결속 precommit

현재 v1 task ID는 caller-supplied 64-hex라 형식만 맞고 비예측성·생성 provenance가 없다. 이 ID를 lease에 먼저 결속하거나 사후에 random이었다고 attest하지 않는다. 첫 state-changing successor는 결과·lease·dispatch가 없는 `P0_EXTERNAL_OPAQUE_TASK_REBINDING_PRECOMMIT_V1`이다.

필수 artifact inventory는 다음과 같다.

1. `external_opaque_id_issuance_policy_raw`: predecessor v1 precommit SHA, generator principal/key/domain, OS CSPRNG/provider profile, 256-bit handle 규칙, campaign-wide uniqueness/CAS 정책, trusted chronology와 rollback/fork 정책
2. `opaque_id_issuance_private_map_raw`: predecessor assignment/task SHA 120개, 새 opaque ID, issuance event ID, durable ledger previous/new head, reviewer actor binding; input·slot·private lineage는 evaluator-private
3. `reviewer_task_v2_inventory_raw`: 새 ID와 기존 exact payload/guideline/response schema만 포함하고 predecessor ID·v1 task raw를 중첩하지 않음
4. `rebinding_precommit_raw`: v1의 40입력·roster·120 assignment raw와 hash는 immutable predecessor로 exact 보존한다. 새 rebinding map이 predecessor assignment row SHA를 새 opaque ID에 잇고, reviewer task v2와 그 hash projection만 새로 만든다. result/lease/dispatch count는 0이다.
5. producer receipt와 producer-import 없는 parent receipt: predecessor assignment raw/hash와 non-ID assignment projection 보존, 120 distinct new ID, durable uniqueness-head chain, reviewer projection allowlist, old ID/private-map leak 0, actual/metric/P1 false를 독립 재계산

필수 공격 테스트는 deterministic payload-derived ID, ID collision, ledger rollback/fork, issuance chronology 역전, reviewer/task swap, v1 assignment 변경, old ID 중첩, roster/slot/ledger-position 누출, caller self-attestation/reseal을 포함한다.

## 이후 lease·dispatch successor 순서

1. **Read-only lease preflight**: rebinding precommit의 전체 raw bundle을 independent parent로 same-call 재검증하고 새 task ID, reviewer, policy/precommit/manifest, not-before/expiry, revocation, nonce commitment와 `REVIEW_LEASE` signature를 검증한다. state를 바꾸거나 dispatch/result 효과를 내지 않는다.
2. **Inaccessible object staging**: blind task 정확히 1개를 randomized audience AEAD 또는 service-mediated no-list capability/검증된 ACL 대상으로 준비하되 dispatcher-private inactive 상태로 둔다. `ISSUED→FETCHED_ONCE` 전에는 reviewer key/capability/ACL이 활성화되지 않아야 한다. peer index와 private map은 없다. threat model은 directory name/list/count·sibling access·object length를 in-scope로 두고 padding/bucketing을 요구한다. delivery timing correlation은 policy가 닫힐 때까지 residual blocker다.
3. **Atomic lease issuance**: signed lease와 exact staged-object receipt를 다시 검증하고 durable CAS의 `ABSENT→ISSUED`를 한 원자 명령으로 생성한다. lease ID·task/reviewer/object hash, nonce commitment, previous/new journal head, signer/time/revocation receipt와 단일 linearization point를 issuance receipt에 결속한다. staging 뒤 issue 전 crash는 reviewer에게 보이지 않는 orphan으로 남아야 한다.
4. **Atomic lease-consumption + fetch executor**: lease를 다시 검증하고 durable CAS의 `ISSUED→FETCHED_ONCE` 전이, reviewer key/capability/ACL 활성화와 exact one-object delivery authorization을 같은 linearization point에 묶는다. authenticated principal, lease/task/object/ciphertext hashes, trusted served time, delivered bytes/hash, `returned_task_count=1`, peer/list access 0, previous/new journal head를 receipt에 결속한다. 하위 실패 시 lease가 재사용 가능 상태로 되돌아가서는 안 된다.
5. **Result freeze**: assigned reviewer live pin, lease, single-fetch receipt, exact raw response를 `HUMAN_REVIEW_RESULT`에 결속하고 첫 valid freeze 뒤 불변으로 둔다. 무응답 expiry는 별도 attester가 fixed domain에서 lease subject·CAS head·trusted expiry를 봉인한 event로만 `UNJUDGED`를 생성한다.
6. **Campaign closure**: primary 80 freeze 뒤 D compiler, exact D reserve lease/delivery/result, final 40 attestation을 순서대로 수행한다.

분산 object store와 CAS를 함께 쓰면 transactional outbox 또는 단일 service transaction을 요구한다. crash 회귀는 stage-before-issue orphan 비노출, issued-before-fetch 유지, fetch commit 뒤 응답 유실을 구분한다. 마지막 경우 같은 principal·request nonce에는 committed encrypted response/receipt만 idempotent readback하고 새 fetch 전이·다른 object·다른 reviewer 전달을 만들지 않는다. 이는 한 번의 논리적 authorization 보장이지 네트워크 바이트가 물리적으로 한 번만 보인다는 과장은 아니다.

현 signature-math v1에는 `LEASE_EXPIRY_TERMINAL_ATTESTATION` kind가 없다. 미래 구현은 v1 manifest나 role/domain을 수정하지 않고 새 version/profile로 추가해야 한다.

각 successor는 evaluator-private 원문과 reviewer-visible projection을 분리하고 producer-import 없는 parent validator를 둔다. reviewer projection에는 whole inventory, 전체 actor roster, 다른 reviewer의 pin/principal/group, predecessor v1 opaque ID, assignment raw/hash, input sequence/slot/peer link, private map·upstream lineage, directory/object index·sibling count, generator event sequence·ledger position, evaluator full raw bundle, parser result, registry ID, 작품/alias/sense/NIL 후보를 넣지 않는다.

serialized child receipt만으로 다음 단계를 열지 않는다. same-call full-raw replay 뒤 module-issued exact-object one-shot state를 쓸 수 있지만 process-local state 자체를 external authority나 durable replay 증거로 세지 않는다.

`아생갤`은 fixed guideline에 따라 해석되지 않은 payload 표면일 뿐이다. 작품명·alias·sense·NIL 판단은 별도 검색 증거 단계에서 explicit alias relation, specific-work target, 공식/커뮤니티 근거, 경쟁 본문 작품 근거를 함께 검증한 뒤에만 다룬다.

## 검증과 비간섭

- current-host zero-input v3/provisioning observer와 blocker compiler를 재실행해 위 세 receipt, `FIXED_STORE / NO_GO`, actual `0/40·0/20`을 확인했다.
- dual-blind/signature/owner/external-trust/Windows preflight 관련 10개 suite를 현재 worktree에서 `195/195 PASS`로 확인했다.
- nonce를 소비하는 external trust/runtime executor는 실행하지 않았다.
- 이번 회차는 read-only observer, unittest와 문서 갱신뿐이며 actual grounding run이 아니다. dashboard와 `--parallel 16` manifest 적용 대상이 아니다.
- 중앙 Slang DB 1개와 publication journal 5개는 최종 문서 동기화 뒤 기존 bytes/SHA와 `6/6` exact 일치했다.

## 재개 조건

외부 운영자가 위 review-authority store를 실제 provision하고 다음 정보를 제공할 때 구현을 재개한다.

- store의 고정 위치와 root identity pin
- campaign/lease/lease-expiry-terminal/final/reviewer/encryption pin inventory의 canonical raw bytes
- owner anchor, epoch, revocation high-watermark와 trusted-time receipt
- durable nonce/lease CAS의 API·crash/reboot 보장과 감사 journal 형식
- reviewer auth principal/SID, dispatcher service identity와 ACL 정책

이 조건 전에는 `actual_authority_granted=false`, `reviewer_dispatch_isolation_verified=false`, `mapping_confidentiality_verified=false`, `opaque_identifier_unpredictability_verified=false`, `durable_replay_prevention_verified=false`, `metric_eligibility_verified=false`를 유지한다.
