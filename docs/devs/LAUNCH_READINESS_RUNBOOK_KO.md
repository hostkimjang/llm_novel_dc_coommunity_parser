# 실제 입력 준비와 출시 판정 런북

> 적용 범위: production/P3 actual launch 전용. 2026-09-05에 활성화된 권리 안전 research-only benchmark에는 이 런북의 external authority gate를 적용하지 않는다.

상태: `NOT_READY / ACTUAL_BLOCKED_HANDOFF / NOT_COMPLETE / REVIEW-LOCKED / full_scan_approval=false`.

2026-09-03 presented HTTP capture-intake와 V4 epoch2 fixed-store observer가 component-only로 추가됐다. 전자는 실제 network/rights 증거가 없고, 후자는 current zero-input이 `FIXED_STORE / NO_GO`이며 distinct store의 live V3 continuity·bootstrap math를 증명하지 않는다. 두 receipt를 이 runbook의 source manifest, owner 결정 또는 launch authority로 재사용하지 않는다.

외부 operator는 별도 권위 root에 정확한 V4 store와 predecessor 연속성 또는 동등한 증거, key/pin·trusted time/revocation/nonce·root/code·write deny·runtime witness를 provision해야 한다. 이어 승인된 raw root에 seed8의 실제 bytes·capture receipt·rights/retention evidence를 준비한다. 그 전 actual source/context는 `0/40·0/20`이며 아래 0단계는 충족되지 않는다.

이 runbook은 active production `20260711_113712_379597`에 쓰거나 중지하지 않는다. 현재 policy v4, source-backed DEV/CAL/FROZEN, complete 10+6 packet, fresh pair가 없으므로 1단계 결과는 `NOT_READY`가 정상이다. 같은 external blocker가 3회 확인된 최신 actual lane은 `ACTUAL_BLOCKED_HANDOFF`다. `READY_FOR_NO_WRITE_PREFLIGHT`도 runtime·정확도·운영 승인 증거가 아니다. v4는 분모·최소 독립 group 30개·bootstrap 2,000회·percentile method를 hash-bound하며 v2/v3 저장 정본은 신규 actual readiness를 열지 않는다.

2026-09-03의 annotation packet V2 → Windows V2 → owner preauthorization V2 → supervisor V2 통과는 별도 component-only shadow 증거다. 해당 supervisor receipt가 있어도 externally provisioned key/time/revocation/nonce/root/code/write-deny/runtime witness와 actual source/context가 없으면 이 runbook의 0단계 입력이 충족된 것으로 간주하지 않는다. serialized receipt나 component self-hash를 launch authority로 재사용하지 않는다.

presented source seed candidate inventory V1의 URL 8개도 이 runbook의 source manifest가 아니다. source bytes를 fetch·capture·parse·attest하지 않았고 rights와 actual credit이 없으므로 0단계 source-backed DEV/CAL/FROZEN 입력을 충족하지 않는다.

이 runbook의 `<actual-policy-v4.json>`은 P3 numerical measurement policy다. 별도 Windows owner policy V4 packet-V2 profile과 이름만 같을 뿐 상호 대체하지 않는다. 후자는 component-only로 통과했지만 externally provisioned fixed store·trusted state·owner authority를 대신하지 않는다.

## 0. 외부 입력을 별도 packet 경로에 준비

동결 input, source manifest, P1 parent, label ledger, policy v4, split/source manifest, expected/producer/BEFORE/AFTER prediction, replay 6종을 production output과 다른 새 directory에 둔다. policy owner 결정과 source-backed DEV/CAL/FROZEN 없이는 2단계 이후로 진행하지 않는다.

## 1. launch manifest 생성

```powershell
.\.venv312\Scripts\python.exe tools\build_launch_readiness_manifest.py `
  --output out\launch_packet\<packet-id>\launch_readiness_manifest.json `
  --p1-run-spec <p1-run-spec.json> --p1-comparison <p1-comparison.json> `
  --label-ledger <label-ledger.json> --policy <actual-policy-v4.json> `
  --split-manifest <split.json> --source-manifest <source.json> `
  --expected-universe <frozen-expected.jsonl> --producer <producer.jsonl> `
  --after-prediction <after.jsonl> --before-prediction <before.jsonl> `
  --artifact after_base_shadows=<after-base-shadows.jsonl> `
  --artifact after_score_vectors=<after-score-vectors.jsonl> `
  --artifact after_calibration_artifact=<after-calibration.json> `
  --artifact baseline_base_shadows=<before-base-shadows.jsonl> `
  --artifact baseline_score_vectors=<before-score-vectors.jsonl> `
  --artifact baseline_calibration_artifact=<before-calibration.json>
```

v2 manifest는 exact 10 required/6 named replay artifact와 path collision을 검증하고 self-hash를 재검증하는 별도 CLI를 통과해야 한다. `NOT_READY`면 누락 ArtifactRef를 보충하고 다시 1단계만 실행한다.

```powershell
.\.venv312\Scripts\python.exe tools\read_launch_readiness_manifest.py `
  --manifest out\launch_packet\<packet-id>\launch_readiness_manifest.json
```

CLI가 `GO_LAUNCH_MANIFEST_BOUND`를 반환하고 `status=READY_FOR_NO_WRITE_PREFLIGHT`일 때만 2단계로 간다. 이 CLI는 builder와 같은 verifier를 별도 process에서 재실행하는 readback이며 별도 validator 구현이라고 주장하지 않는다. `NOT_READY`는 정상적인 fail-close이며 runtime을 시작하거나 production에 쓰지 않는다.

## 2. 무쓰기 P3 preflight

```powershell
.\.venv312\Scripts\python.exe tools\run_launch_packet_preflight.py `
  --manifest out\launch_packet\<packet-id>\launch_readiness_manifest.json `
  --artifact-root out\launch_packet\<packet-id>
```

wrapper는 먼저 manifest self-hash/exact-set을 reader로 재검증하고 10 required·6 replay path·seed·replicates를 재사용한다. 모든 artifact가 `artifact-root` 아래에 있을 때만 실제 preflight reader를 호출한다. `NOT_READY`면 `NO_GO_LAUNCH_PACKET_PREFLIGHT`로 engine 호출 전 종료한다. 성공 조건은 `GO_ACTUAL_BOUND_READBACK_ATTEMPT_ALLOWED`; 이 단계는 output을 만들거나 모델을 실행하지 않는다.

성공 stdout을 audit evidence로 저장해야 하면 engine이 아니라 operator가 별도 파일에 capture한 뒤 아래 reader를 실행한다.

```powershell
.\.venv312\Scripts\python.exe tools\read_launch_packet_preflight_receipt.py `
  --receipt <captured-preflight-receipt.json>
```

reader는 receipt self-hash, bound launch manifest와 packet artifact bytes, runtime/write/approval safety field를 재검증한다. `GO_LAUNCH_PACKET_PREFLIGHT_RECEIPT_BOUND`만 후속 actual readback의 preflight 증적으로 쓴다.

## 3. source-backed P3 readback/evaluate

2단계의 capture receipt가 `GO_LAUNCH_PACKET_PREFLIGHT_RECEIPT_BOUND`일 때만 다음 wrapper로 readback bundle을 만든다.

```powershell
.\.venv312\Scripts\python.exe tools\run_launch_packet_actual_readback.py `
  --manifest out\launch_packet\<packet-id>\launch_readiness_manifest.json `
  --preflight-receipt <captured-preflight-receipt.json> `
  --artifact-root out\launch_packet\<packet-id> `
  --output-dir out\launch_packet\<packet-id>\p3_readback
```

wrapper는 verified manifest·GO receipt·root-relative 10+6 artifact를 다시 결속하고 packet root의 **새 직접 자식** `output-dir`에만 readback bundle을 쓴다. shared writer는 최종 경로에 직접 쓰지 않고 packet root 아래 무작위 staging directory에 완성본을 기록한 뒤 rename하며, staging identity/reparse 교체가 보이면 cleanup을 포기하고 fail-close한다. hostile-parent의 handle-relative/no-reparse 완전 방어는 이 foundation 범위 밖이다. `NOT_READY` packet은 `NO_GO_LAUNCH_PACKET_ACTUAL_READBACK`으로 receipt나 engine을 열기 전에 종료한다. 이어서 `actual-evaluate --artifact-root <packet> --readback-bundle-dir <packet>/p3_readback --output-dir <packet>/p3_evaluation`을 실행한다. `GO_FROZEN_ACTUAL_SHADOW_ONLY`도 M2 또는 운영 승인이 아니다.

## 4. production 종료 뒤 fresh pair freeze와 실행

별도 source output만 사용해 다음으로 pair RunSpec을 만든다.

```powershell
.\.venv312\Scripts\python.exe tools\run_paired_measurement_readback.py `
  --freeze-run-spec out\paired_measurement\<pair-id>\run_spec.json `
  --input <frozen-input.jsonl> --source-manifest <complete-source-manifest.json> `
  --pair-id <pair-id> --slang-access-mode OFF
```

RunSpec hash를 읽은 뒤 BEFORE (`PIPELINE_MEASUREMENT_EARLY_ROUTE_MODE=OFF`)와 AFTER (`SOURCE_ONLY_V1`)를 각각 한 번씩 실행한다. 둘 다 `expert_main.py ... --parallel 16 --reuse-shards-only --slang-db off --vlm on --ocr on --require-vlm-ocr-for-images`이며 dashboard를 켜고 `--no-dashboard`를 쓰지 않는다.

## 5. 독립 paired readback와 recovery

두 manifest가 완결된 뒤 `tools/run_paired_measurement_readback.py --run-spec ... --before-manifest ... --after-manifest ... --output-json ... --output-md ...`를 실행한다. 중단 arm은 `tools/recover_expert_run_from_checkpoint.py`의 paired witness 인자를 사용해 source/WAL/ledger/attempt를 재생한다. 실패·partial·multi-attempt면 arm 전체를 fresh rerun한다.

## 6. 판정

M2에는 source-backed accuracy/recall/NIL/Brier/log loss/ECE/selective risk/AURC, calls/tokens/E2E paired CI, hard regression 0, public/CandidateSet 비간섭, crash/restart readback이 모두 필요하다. 그 전에는 `REVIEW-LOCKED`, `full_scan_approval=false`다.
