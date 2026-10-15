# P0 lineage V2 다음 gate 전문가 재회의

작성일: 2026-09-04 KST

## 결론

판정은 `ADOPT_INTERFACE / IMPLEMENTATION_DEFERRED / EXTERNAL_INPUT_REQUIRED / CURRENT_FIXED_STORE_NO_GO`다. A-context lineage-capped full-frame V2 이후 새 compiler·receipt·subject/target/packet V3를 만드는 안은 채택하지 않았다. 현재 필요한 것은 외부 owner가 실제 V3/V4 store, trust/runtime, rights/capture, label 전 actual 40+20과 review authority를 provision하는 일이다.

현재 zero-input readiness compiler를 다시 실행한 결과는 다음과 같다.

- receipt: `f3537ed24ed3c8a897ef252e218ae7b492ebae62ee9a823aef2d0c143eb18d42`
- `transition_status=VALID_COMPONENT_NO_GO`
- `transition_failure_stage=FIXED_STORE`
- `decision=NO_GO`
- actual/credited source·A-context: `0/40·0/20`
- protected endpoint point-in-time projection: 전후 일치
- `p0_phase_exit=false`, `production_approval=false`, `full_scan_approval=false`

이 결과는 외부 상태가 아직 바뀌지 않았음을 증명한다. endpoint 전후 일치는 실행 중 write-deny나 external authority를 증명하지 않는다.

## 분과별 판정

### 통계·데이터

가장 중요한 다음 인터페이스는 외부 owner가 서명한 actual `40+20` numerical policy다. 이 정책 SHA는 capture, full frame, seed, selection, reviewer assignment, subject/target/packet successor와 final attestation에 동일하게 결속돼야 한다. 다만 현재 canonical owner bytes·detached signature·external trust anchor·trusted time/revocation/durable nonce가 없으므로 example-only producer를 만들지 않는다.

채택한 통계 불변식은 다음과 같다.

- chronology: `policy authorization < capture start <= frame cutoff < owner precommit < seed reveal < selection seal < reviewer assignment < first response`
- source는 exact `40=10×4 profile`, A-context는 exact `20=5×4 profile-day`
- A 1차 단위는 distinct source lineage이고 `G_h`, `n_h=5`, global cap `1`; 2차는 lineage별 `K_g` 중 context 1개
- hard underfill, no spill/backfill/replacement/quota relaxation/reroll
- 기약분수 `π_g=n_h/G_h`, `w_g=G_h/n_h`, `p(i|g)=1/K_g`, `π_i=n_h/(G_h*K_g)`, `w_i=G_h*K_g/n_h`
- 같은 lineage의 두 context joint inclusion은 `0`, `contexts_are_iid=false`
- `JUDGED+UNJUDGED+UNAVAILABLE=planned`; 접근 실패와 미응답도 ITT 분모에 유지
- 일반 binomial IID CI와 complete-case/unweighted population 추론은 P0에서 금지

### MLOps·계약

readiness compiler V2는 현재 blocker를 정확히 표현하고 focused `12/12`를 통과한다. 여기에 lineage receipt를 붙인 compiler V3나 미리 연결한 subject/target/packet V3는 외부 blocker를 하나도 줄이지 못하므로 contract laundering 위험이 있다.

legacy `p0_actual_authority_raw_execution.py`의 canonical/resource-bound ingress와 `p0_actual_authority_event_bytes.py`의 bounded incremental parsing, capture-rights policy body 의미 계약은 future hardening debt로 남겼다. 실제 owner-pinned adapter·정책·파일 역할이 정해지기 전에 별도 component-only wrapper로 만들지 않는다. 외부 패키지가 들어오면 positive path 적용 전에 이 debt를 다시 감사한다.

### Claude Fable 협업 경로

`anthropic/claude-fable-5` native subagent는 `unreadable_encrypted_agent_task`로 실패했다. 지정된 기존 로컬 task에 같은 모델 override로 보낸 독립 감사는 약 90초 뒤 completed 상태가 됐지만 최근 turn의 `items`가 비어 있어 읽을 수 있는 검토 결과가 없었다. 따라서 Fable 결과는 이번 합의 근거에 포함하지 않았다.

## 외부 operator 최소 패키지

1. exact V3/V4 `21-role·9-file` fixed store와 독립 bootstrap/public pin
2. trusted time, signed revocation high-watermark, crash/reboot durable nonce
3. owner-signed root/code identity, OS write-deny, signed native runtime witness
4. source별 collection/retention/index/quotation/publication·takedown 결정과 승인 raw root/capture provenance
5. label 전 actual source40/A-context20 complete census, lineage frame/seed/plan과 owner-signed numerical policy
6. guideline SHA, conflict-free reviewer assignment, append-only genesis/head와 dual-blind terminal events

## 재개 기준

fixed store 또는 위 외부 package가 실제 제공되면 먼저 zero-input observer/compiler를 다시 실행한다. positive 관찰 뒤 legacy raw/event canonical·resource-bound debt를 확인하고, numerical policy parent replay와 별도 subject V3→target V3→packet V3를 순서대로 설계·반대검토한다. 실제 validation run은 dashboard ON, requested/effective `--parallel 16`을 확인한다. 그 전에는 Pyserini BM25·gold-lite·reranker/NIL·production/full scan을 열지 않는다.
