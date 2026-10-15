# M1 foundation acceptance 재감사 — 2026-07-12

## 판정

`ARCHITECTURE_INTEGRATION_COMPLETE / ACTUAL_BLOCKED_HANDOFF / REVIEW-LOCKED / full_scan_approval=false`.

선택한 shadow foundation 회귀와 explicit no-write observer 접목, launch manifest/preflight/readback wrapper, 한국어 runbook은 M1 범위에서 통과했다. fresh active runtime execution evidence와 source-backed actual packet은 M2 외부 게이트이며 같은 blocker가 `3/3`으로 재확인돼 `ACTUAL_BLOCKED_HANDOFF`로 전환했다. 전체 Goal 완료나 운영 승인을 주장하지 않는다.

## 확인된 정적 foundation

| 범위 | 근거 | 판정 |
| --- | --- | --- |
| P0~P4 계보 | P2 v8 → P3 v20 → P4 v21 | 정본 유지 |
| DecisionLedgerV2 | framed WAL, legacy replay, compaction, 104,502 acceptance, run/pair/arm binding sidecar, read-only post-run mirror | shadow only |
| stage control | bound receipt, dedicated canary, canonical key, limiter/lease/cache receipts, stale-delete guard, file-local shared-result singleflight, explicit pipeline search observer와 replay-only canary | shadow only |
| slang | work/manifest/proposal/owner approval/sidecar rollback | explicit temp-root·2 MB bound sidecar only |
| launch | v2 no-write manifest, build 후 standalone shared-verifier CLI, artifact-root-bound preflight wrapper/receipt reader, Korean runbook | packet source 없음 |

## 선택 회귀

```powershell
.\.venv312\Scripts\python.exe -m unittest -q tests.test_framed_wal tests.test_decision_ledger_v2 tests.test_decision_ledger_v2_legacy_replay tests.test_decision_ledger_v2_mirror tests.test_decision_ledger_v2_mirror_canary tests.test_decision_ledger_binding tests.test_stage_foundations tests.test_shared_cache_contract tests.test_shared_result_singleflight tests.test_pipeline_stage_shadow tests.test_pipeline_stage_shadow_canary tests.test_stage_budget_shadow_canary tests.test_build_stage_budget_receipt tests.test_slang_governance tests.test_slang_transaction tests.test_launch_readiness_manifest tests.test_decision_call_tracing tests.test_decision_call_readback tests.test_agentic_pipeline_search_evidence
```

결과: `120 tests PASS` (`30.088s`). 이는 synthetic/bounded/no-write 회귀이며 실제 정확도·비용·E2E 효과 증거가 아니다.

## 이번 재감사 보정

- launch reader는 required 10/replay 6 exact set과 missing list/path collision을 다시 계산한다. self-hash를 새로 계산해 artifact ref를 비운 뒤 `READY`로 바꾸는 입력은 fail-close한다.
- filesystem-local lease의 stale takeover/release와 file cache의 expired eviction은 각각 OS-file guard 안에서 observed owner/self-hash/expiry 또는 entry SHA/expiry를 다시 확인한다. 따라서 늦은 삭제자가 새 replacement lease/cache entry를 지우지 않는다.
- 이 race 보정 자체는 filesystem-local shadow coordination일 뿐 network/global coordinator 또는 active runtime integration을 뜻하지 않는다. 별도 shared-result contract도 같은 filesystem-local/OFF-by-default 경계를 유지한다.
- StageBudget reader 회귀는 mixed RunSpec/scope/attempt와 직접 snapshot self-hash 위조까지 분리해 fail-close를 확인했다. artifact bytes binding은 semantic runtime evidence가 아니다.
- slang transaction의 apply/reconcile/rollback은 이제 명시적 `sidecar_root`가 system temporary root 아래에 있고 DB·journal이 그 root 안에 있으며 DB가 2 MB 이하일 때만 시작한다. 이 안전 gate는 bounded temp-DB 시험 경계를 코드로 강제하며 `SlangDBManager.flush`나 active production을 호출하지 않는다.
- launch manifest는 library reader뿐 아니라 `tools/read_launch_readiness_manifest.py` CLI로도 별도 process 재독한다. canonical no-input manifest는 `NOT_READY / GO_LAUNCH_MANIFEST_BOUND`이며 외부 source 자료가 없다는 fail-close 증거다. verifier 구현은 builder와 공유하므로 독립 validator 구현으로 과장하지 않는다.
- malformed manifest CLI는 traceback 대신 `NO_GO_LAUNCH_MANIFEST_READBACK`, runtime/write false, exit 2로 fail-close한다.
- `tools/run_launch_packet_preflight.py`는 verified manifest에서만 10+6 ref/seed/replicates를 absolute→root-relative로 재결속하고 manifest·artifact bytes를 전/후 재검증한다. 모든 ref가 `artifact-root` 아래일 때만 actual-preflight reader를 호출하며 runtime/actual metrics/approval 위조 report는 거부한다. canonical no-input packet은 `NO_GO_LAUNCH_PACKET_PREFLIGHT`로 engine 실행 전 끝난다.
- `tools/read_launch_packet_preflight_receipt.py`는 operator가 capture한 no-write receipt의 self-hash·manifest·10+6 artifact bytes 및 safety field를 다시 읽는다. runtime/write/approval claim이 하나라도 다르면 `NO_GO`다.
- `tools/run_launch_packet_actual_readback.py`는 verified manifest와 GO preflight receipt가 일치할 때만 root-relative 10+6 input을 actual-readback builder에 전달한다. shared writer는 모든 호출에서 packet root의 새 직접 자식만 받고 무작위 staging write→rename을 쓰며 staging identity/reparse 교체 시 cleanup을 포기한다. canonical no-input packet은 receipt/engine 전에 `NO_GO`다.

## M2 pending external gates

- source-backed packet 10 required + 6 replay artifact가 없어 v2 launch manifest는 `NOT_READY`다. 이는 M1 implementation 결함이 아니라 M2 actual packet 입력 부재다.
- actual 입력 인벤토리는 `docs/devs/ACTUAL_PACKET_INPUT_INVENTORY_KO_20260712.md`다. 현재 신규 owner policy v4, DEV/CAL/FROZEN split/source, COMPLETE producer와 10+6 artifact가 모두 없어 actual preflight는 열지 않는다.
- actual-readback 독립 감사 보정: receipt provenance는 같은 verified packet의 no-write preflight 재계산 결과와 exact-match해야 하며 self-hash만으로 GO를 만들 수 없다. output은 packet root의 직접 자식 새 directory로 제한해 nested symlink/junction parent 경로를 거부한다. source-less `NOT_READY` fail-close는 유지하며 actual source/effect 증거는 아니다.
- P1 v8→P2 v8→P3 v20→P4 v21 historical parent replay는 stored RunSpec/비교표/label/Golden18 artifact bytes·self-hash와 implementation record aggregate를 재생한다. 과거 implementation SHA는 current working-tree와 같다고 요구하지 않으며 direct validator의 기본 current-source 검증은 별도로 유지한다. P3 `19 PASS`, P4/paired `59 PASS`로 M1 lineage replay 경계를 확인했으나 actual packet/M2 evidence는 아니다.
- DecisionLedgerV2의 static shadow crash/scale foundation은 focused 6개 모듈 `22 PASS`로 재확인했다. 이는 P2 publication WAL을 바꾸거나 `DecisionCallLedgerRegistry` active writer를 교체한 것이 아니며, 해당 runtime-safe 접목은 M2 runtime gate다.
- active runtime에는 shared cache/lease/shared-result singleflight/DecisionLedgerV2가 연결되지 않았다. `AgenticPipeline` observer와 replay-only canary는 explicit no-write 경로만 가능하며 fresh runtime evidence는 없다.
- filesystem-local shared-result singleflight는 network/global coordinator가 아니며 result reuse 범위도 exact namespace의 shadow file cache로 제한된다.
- slang reconciliation은 sidecar operator/API 또는 다음 sidecar apply가 호출할 때만 수행된다. active runtime startup hook은 의도적으로 연결하지 않았으므로 runtime evidence로 읽지 않는다.

## M2 외부 게이트

policy v4 owner decision, source-backed DEV/CAL/FROZEN, 동일 RunSpec fresh BEFORE/AFTER(`--parallel 16`, dashboard ON), paired readback/CI, hard regression 0과 crash/restart evidence가 필요하다. 그 전에는 `REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.
