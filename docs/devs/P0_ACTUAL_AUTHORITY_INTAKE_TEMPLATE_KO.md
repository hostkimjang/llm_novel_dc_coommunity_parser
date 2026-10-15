# P0 actual owner authority 입력 템플릿

상태: `SCHEMA_FOUNDATION_IMPLEMENTED / LINEAGE_CAPPED_A_CONTEXT_V2_COMPONENT_ONLY / KEYLESS_PACKET_STRUCTURAL_CONTRACT_IMPLEMENTED / DOWNSTREAM_WIRING_0 / EXTERNAL_ACTUAL_0_OF_40_0_OF_20 / OWNER_NOT_APPROVED / NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED`
용도: 실제 source claim 40건과 A context 20건을 수집하기 전에 owner가 범위·권리·주석·보호 대상을 확정하는 입력 문서
금지: 비밀 key 값, 원문 payload, 개인정보, caller가 만든 `authority=true`

이 문서는 승인 자체가 아니다. owner가 확정한 값을 별도 immutable JSON artifact와 detached authorization으로 만들고, run root 밖에 사전 provision된 trust anchor로 검증해야 authority 증거가 된다. 이 Markdown의 체크 표시나 SHA만으로 gate를 열지 않는다.

## 1. 승인 주체와 외부 trust anchor

- owner 조직/역할:
- owner principal의 공개 식별 fingerprint(SHA-256):
- 승인 artifact 발급 담당자:
- trust anchor 저장 위치: **repository와 pilot run root 밖의 사전 provision 경로만 허용**
- verification method: `HMAC_SHA256_EXTERNAL_KEY_V1` 또는 승인된 비대칭 서명 방식
- public key/key fingerprint(SHA-256):
- 유효 시작/종료 시각(RFC3339):
- 철회 registry/ref:
- 허용 범위: `P0_ACTUAL_PILOT_SHADOW_ONLY`
- 금지 범위: `PUBLIC_APPLY`, `CENTRAL_SLANG_DB_WRITE`, `PUBLICATION_WAL_WRITE`, `PRODUCTION`, `FULL_SCAN`

비밀 key 본문과 복구 문구는 이 문서·Git·manifest·로그·receipt에 기록하지 않는다. validator는 key를 생성하거나 복사하지 않고 read-only로 전달받아야 한다.

## 2. capture 정책

- 허용 platform/community/hostname:
- 허용 source profile: `OFFICIAL_STRUCTURED`, `COMMUNITY_STRUCTURED`, `MEDIA_OCR`, `GENERIC_FALLBACK`
- 수집 시간 창과 요청 상한:
- 접근 제한·로그인·robots/약관 처리 기준:
- capture 단계 네트워크 허용 범위:
- parse 단계 네트워크 정책: `DENY`
- raw payload 접근 통제 저장 root: **Git 및 일반 `out/**` 밖**
- 허용 output run root:
- 금지 write root:
- capture tool/code/config 고정 방법:

## 3. 권리·보존·철회 정책

각 source마다 아래 결정을 별도로 내리며 `UNKNOWN`은 fail-close한다.

| 권리 축 | 허용 조건 | 거부/UNKNOWN 조건 | 검토 주기 |
| --- | --- | --- | --- |
| `collection_allowed` |  |  |  |
| `content_retention_allowed` |  |  |  |
| `derived_index_allowed` |  |  |  |
| `quotation_allowed` |  |  |  |
| `publication_evidence_eligible` |  |  |  |

- retention class/최대 보존 기간:
- takedown 접수·반영 SLA:
- payload 삭제 receipt 형식:
- derived index 삭제 receipt 형식:
- 철회된 source의 기존 claim/context/event 처리:
- rights assessor 역할과 reviewer assignment 발급자:

## 4. sampling plan과 launch 선고정

- source claim 목표: `40`, profile별 `10`
- 실제 A context 목표: `20`
- sampling frame 기준 시각:
- strata: profile/OCR/multi-work/NIL/unavailable/challenge
- 선택 알고리즘과 seed 공개 방식:
- lineage dedupe 단위:
- label 확인 전 planned item ID/order SHA를 봉인하는 위치:
- 실패·접근 제한·generic queue를 분모에서 삭제하지 않는 회계 규칙:
- requested parallel: `16`
- dashboard: `ON`

결과 label을 본 뒤 quota·seed·planned set을 바꾸면 pilot은 무효다. 40 claim은 unique claim sampling unit으로, 독립 source 근거는 별도 independence group으로 계산한다.

## 5. annotation·candidate·novelty 정책

- guideline 정본 경로와 byte SHA:
- guideline version/effective interval:
- A/B truth·annotation·inference·publication reason registry:
- reviewer assignment 발급·만료·conflict 확인 방식:
- 동일 principal의 pseudonym 변경을 독립 vote로 세지 않는 규칙:
- candidate registry snapshot 생성/완료 회계:
- evidence cutoff 규칙:
- `NEW_SENSE` novelty review와 기존 sense 비교 범위:
- sensitive/temporal 판정과 HOLD 규칙:
- adjudication·intra-rater recheck·supersedes 규칙:

## 6. append-only journal 정책

- 신규 genesis 또는 기존 predecessor checkpoint SHA:
- predecessor event count/head ID/head SHA:
- canonical JSONL framing과 newline 규칙:
- immutable segment 저장 위치:
- 전역 `(target_type,target_id) → single journal/head` map 위치:
- checkpoint signer/trust anchor:
- fork·rollback·prefix rewrite·journal 삭제 탐지 절차:

외부에 고정된 genesis/predecessor가 없으면 local event chain을 모두 다시 해시할 수 있으므로 `annotation_append_only_verified=false`다.

## 7. protected-state watch와 runtime 경계

실행 전에 watch spec과 pre-snapshot을 봉인한다.

- 중앙 Slang DB 파일과 parent directory:
- publication WAL/journal·scope descriptor·repair sidecar:
- checkpoint/result/recovery/decision ledger:
- watched directory별 sorted membership digest:
- file identity/reparse/symlink 검사:
- parser allow-write root:
- OS write-deny sandbox/ACL witness:
- post-snapshot 담당 독립 readback process:

before/after bytes·SHA와 directory membership이 같아도 실행 중 썼다가 복구한 사실은 증명하지 못한다. OS write-deny 증거가 없으면 결과 문구는 `terminal_membership_projection_equal`로 제한하고 `runtime_noninterference_verified=false`를 유지한다.

## 8. pre-capture authorization과 post-run attestation

pre-capture detached authorization은 다음을 묶는다.

- domain: `llm-novel-dc-community-parser/p0-actual-owner-authorization/v1`
- owner anchor SHA와 principal fingerprint
- approval decision: `AUTHORIZE_P0_ACTUAL_SHADOW_VALIDATION`
- pilot/launch ID와 유효 기간
- launch SHA를 통해 sampling, capture, rights, guideline, reviewer assignment policy SHA, watch spec, annotation predecessor, planned 40+20 set
- `public_apply=false`
- `central_slang_db_write=false`
- `publication_wal_write=false`
- `production_approval=false`
- `full_scan_approval=false`

capture 이후 생성되는 parser receipt, candidate/novelty artifact, current checkpoint/head map, watch PRE/POST·sandbox receipt, final pilot manifest는 별도 domain-separated **post-run final attestation**이 직접 묶어야 한다. 현재 v2 foundation은 manifest를 역참조하지 않는 terminal final-attestation schema와 unsigned example, 원문 event-byte/prefix/head 재구성을 제공한다. `p0_actual_keyless_pilot_manifest_v1` structural validator도 13개 child의 canonical bytes와 route/A receipt를 재계산하지만, 현재 입력은 controlled example/test bytes뿐이고 실제 owner signature/key·external anchor·외부 actual pilot manifest·trusted fixed-directory/OS write-deny validator는 없다. 따라서 `ACTUAL_FINAL_OWNER_ATTESTATION_NOT_VERIFIED`, `ACTUAL_AUTHORITY_DIRECTORY_VALIDATOR_NOT_IMPLEMENTED`를 유지한다. HMAC 또는 key-less 구조 검증이 성공해도 이 외부 증거가 없으면 `owner_authority_verified=false`다.

pre-capture launch의 하위 artifact가 바뀌면 authorization을, post-run artifact가 바뀌면 final attestation을 다시 발급해야 한다. 서명 성공은 owner가 해당 shadow packet 범위를 승인했다는 뜻일 뿐 source 내용의 진실성이나 production 승인이 아니다.

## 9. owner 확정 체크

- [ ] 외부 trust anchor/key가 run root 밖에 사전 provision됐다.
- [ ] capture·rights·retention·takedown 정책을 owner가 확정했다.
- [ ] annotation guideline과 reviewer assignment 정책을 확정했다.
- [ ] sampling plan과 launch planned set을 label 전에 봉인했다.
- [ ] predecessor/genesis checkpoint와 전역 head map을 봉인했다.
- [ ] protected-state watch spec과 OS write-deny 방식을 확정했다.
- [ ] detached authorization payload와 만료/철회 절차를 승인했다.
- [ ] 실제 40 claim+20 A-context를 수집·판정할 담당자와 저장 위치를 확정했다.

하나라도 미완료면 blocker `ACTUAL_OWNER_EXTERNAL_TRUST_NOT_VERIFIED` 등을 남긴다. authority v2 receipt는 `NO_GO_ACTUAL_P0_NOT_STARTED`, key-less packet receipt는 `NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED`, `p0_phase_exit=false`, `full_scan_approval=false`를 유지한다.

## 10. 구현된 key-less actual packet의 실제 입력 요건

실제 owner key와 무관하게 구조를 먼저 검증하는 packet은 기존 v1/v2를 제자리 확장하지 않는 별도 schema로 구현했다.

- pre-capture `source input plan`: 입력 registry ID·순서·sampling frame·seed commitment
- label 확인 전 `claim selection seal`: 1:N parse 뒤 고정한 unique claim unit 40개와 profile별 `10×4`
- parser terminal route: 각 input은 `TYPED`, `GENERIC_PENDING`, `PARSER_ERROR` 중 정확히 하나
- actual A-context 20건과 별도 A annotation event: 현재 B event의 sense decision field를 재사용하지 않음
- file-bound pilot manifest: 각 path·bytes·rows·SHA, parser/accounting/profile/A-status count를 원문에서 재계산

구조 계약은 A-context `18 PASS`, route `27 PASS`, packet `19 PASS`, focused `64 PASS`, `.venv312` selected adjacent `285 PASS`다. 최종 red-team의 기존 5축과 single-claim parser manifest/version provenance substitution, completion=seal equal-timestamp 우회를 닫았다. 모든 claim의 동일 manifest/version 재봉인은 structural consistency만으로 구분할 수 없으므로 owner-authorized launch/capture witness에 `expected_parser_manifest_sha256`·`expected_parser_version`을 넣어 route receipt와 교차결속해야 한다. controlled example/test bytes만 검증했으며 테스트 생성 manifest SHA는 durable artifact가 아니다. external owner/final signature·trusted handle/root·journal/watch·OS witness 전에는 실제와 credited count를 모두 `0/40`, `0/20`으로 유지하고 gate를 `NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED`로 닫는다.

## 11. lineage-capped A-context V2 외부 handoff delta

최신 A-context sampling component는 manifest `c1080b53622b1b1bb93b127361e333cadeddf664c44a94d329257a6a918d250b`다. 기존 subject V2·target V2·packet V2에는 연결되지 않았고 `downstream_wiring_count=0`이다. 외부 owner는 이 component를 곧바로 실행 승인으로 취급하지 말고, 다음 값을 pre-capture launch authorization에 직접 결속해야 한다.

- source scope/census/frame/seed/plan 5개, bridge inventory 1개, A scope/census/frame/seed/plan 5개의 exact raw SHA-256과 역할별 byte count
- lineage frame, lineage seed receipt, lineage plan의 exact raw SHA-256과 artifact SHA-256
- source V2, bridge, A V1, lineage-capped V2의 exact component manifest SHA-256
- source selection, A scope/frame/V1 selection, lineage frame, owner precommit, seed reveal, V2 selection의 strict chronology
- profile-day 층별 distinct lineage 모집단 `G_h`, quota `n_h=5`, lineage별 eligible context 수 `K_g`, 전역 selected cap `1`
- underfill hard fail, no spill/backfill/replacement, `WITHIN_SELECTED_LINEAGE_SURPLUS`·`UNSELECTED_LINEAGE_SURPLUS` exact partition
- actual capture root, rights/retention decision, capture code/parser manifest, source lineage 근거와 reviewer assignment의 외부 owner 서명

실제 handoff의 최소 파일·상태는 다음과 같다.

| 묶음 | 최소 증거 | 현재 상태 |
| --- | --- | --- |
| V3→V4 owner store | 고정 V3 body/signature/operational pin과 V4 predecessor/body/signature/SPKI, exact 21-role·9-file inventory | `FIXED_STORE_NOT_PROVISIONED` |
| trust/runtime | 독립 pin, trusted time, revocation high-watermark, durable nonce, root/code authority, OS write-deny, signed native runtime witness | `NOT_VERIFIED` |
| rights/capture | source별 collection/retention/index/quotation/publication 결정을 담은 detached authorization과 승인된 raw root | `0/8 OPERATIONALLY CLEARED` |
| sampling | label 전 고정된 actual source 40·A-context 20, lineage frame/seed/plan과 complete census | `0/40·0/20` |
| review | guideline SHA, conflict-free reviewer assignment, append-only genesis/head와 dual-blind terminal event | `0/80 PRIMARY TERMINAL` |

2026-09-04 현재 zero-input readiness compiler는 receipt `f3537ed24ed3c8a897ef252e218ae7b492ebae62ee9a823aef2d0c143eb18d42`, `failure_stage=FIXED_STORE`, `decision=NO_GO`를 재현했다. protected endpoint의 point-in-time 전후 projection은 일치했지만 이는 외부 권위나 runtime write-deny 증거가 아니다.

외부 owner가 위 최소 증거를 제공하고 기존 validator가 이를 성공적으로 관찰하기 전에는 새 receipt wrapper나 subject/target/packet V3를 만들지 않는다. 성공 관찰 뒤에도 별도 version boundary와 독립 검토를 거쳐야 하며, 실제 사람 검토 전 metric·Pyserini·gold-lite·production/full scan은 계속 닫는다.
