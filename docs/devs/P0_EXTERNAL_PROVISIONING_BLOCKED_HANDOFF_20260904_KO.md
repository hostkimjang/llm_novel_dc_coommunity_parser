# P0 외부 provisioning blocked handoff

> `DEFERRED_P0_AUDIT_TRACK` (2026-09-05 scope supersession): 이 문서는 향후 P0/production/publication/full-scan 전환용 handoff다. 아래 blocked 상태는 당시 감사 사실로 보존되지만 현재 research-only benchmark의 blocker가 아니다.

작성일: 2026-09-04 KST

## 상태

`BLOCKED_EXTERNAL_PROVISIONING_REQUIRED / FIXED_STORE_NO_GO / ACTUAL_0_OF_40_0_OF_20 / PRODUCTION_FULL_SCAN_NO_GO`

동일 blocker를 세 차례 연속 감사했다. 첫 감사는 lineage-capped V2 완료 뒤 downstream wiring을 0으로 유지했고, 두 번째는 통계·MLOps 다음-gate 회의에서 내부 wrapper 구현을 보류했다. 세 번째 current-state 감사에서도 외부 store와 actual package가 없었다. 안전한 내부 구현은 더 이상 외부 blocker를 줄이지 못하므로 Goal을 blocked handoff로 전환한다.

## 3차 current-state 증거

- V3 store: `C:\ProgramData\llm-novel-dc\p0-owner-policy-v1` → 없음
- V4 store: `C:\ProgramData\llm-novel-dc\p0-owner-policy-v4-packet-v2` → 없음
- workspace: 새 owner-signed numerical policy, complete source40/A-context20 census, reviewer authority/terminal event, external trust/runtime/rights package 없음
- `rows/`의 관련 후보는 actual package가 아닌 0-byte 구자료
- fresh compiler receipt: `f3537ed24ed3c8a897ef252e218ae7b492ebae62ee9a823aef2d0c143eb18d42`
- `transition_status=VALID_COMPONENT_NO_GO`, `failure_stage=FIXED_STORE`, `decision=NO_GO`
- observed/credited actual source·A-context: `0/40·0/20`
- protected endpoint point-in-time projection: 전후 일치
- readiness compiler focused: `12/12 PASS` (`2.235s`)
- 중앙 Slang DB 1개와 publication journal 5개: `6/6` byte/SHA 불변, receipt `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`

endpoint projection 일치와 component self-hash는 external authority, OS write-deny 또는 실제 semantic evidence가 아니다.

## 외부 owner가 제공해야 하는 최소 package

1. exact V3/V4 `21-role·9-file` fixed store와 독립 bootstrap/public pin
2. trusted time, signed revocation high-watermark, crash/reboot durable nonce
3. owner-signed root/code identity, OS write-deny, signed native runtime witness
4. source별 collection/retention/index/quotation/publication·takedown 결정과 승인 raw root/capture provenance
5. label 전 actual source40/A-context20 complete census, lineage frame/seed/plan과 owner-signed numerical policy
6. guideline SHA, conflict-free reviewer assignment, append-only genesis/head와 dual-blind terminal events

비밀 key나 원문 payload를 Git에 넣지 않는다. fixed store는 zero-input observer가 요구하는 외부 고정 경로와 ACL/identity 조건을 만족해야 한다.

## 재개 절차

외부 package가 provision되거나 사용자가 정확한 외부 artifact 위치를 제공하면 Goal을 resume한다. 첫 행동은 store를 고치거나 복사하는 것이 아니라 zero-input transition observer/readiness compiler의 read-only 재실행이다. positive 관찰 뒤 legacy raw/event canonical·resource-bound ingress와 capture-rights policy body debt를 다시 감사한다. 그 다음 owner-signed numerical policy parent replay, subject V3→target V3→packet V3를 별도 version으로 구현·반대검토한다.

실제 validation run은 dashboard ON, requested/effective `--parallel 16`을 확인한다. actual semantic/human review와 owner authority 전에는 metric·Pyserini BM25·gold-lite·reranker/NIL·production/full scan을 열지 않는다.

Claude Fable 경로 실패는 별도 도구 문제이며 blocked의 주원인이 아니다. 주 blocker는 외부 owner package 부재다.
