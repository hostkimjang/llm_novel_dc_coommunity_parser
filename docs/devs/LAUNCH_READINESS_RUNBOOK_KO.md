# Actual launch-readiness runbook

상태: `NOT_READY / REVIEW-LOCKED / full_scan_approval=false`.

이 runbook은 active production `20260711_113712_379597`에 쓰거나 중지하지 않는다. 현재 actual DEV/CAL/FROZEN 자료가 없으므로 1단계 결과는 `NOT_READY`가 정상이다. `READY_FOR_NO_WRITE_PREFLIGHT`도 runtime·정확도·운영 승인 증거가 아니다.

## 0. 외부 입력을 별도 packet 경로에 준비

동결 input, source manifest, P1 parent, label ledger, policy v3, split/source manifest, expected/producer/BEFORE/AFTER prediction, replay 6종을 production output과 다른 새 directory에 둔다. policy owner 결정과 source-backed DEV/CAL/FROZEN 없이는 2단계 이후로 진행하지 않는다.

## 1. launch manifest 생성

```powershell
.\.venv312\Scripts\python.exe tools\build_launch_readiness_manifest.py `
  --output out\launch_packet\<packet-id>\launch_readiness_manifest.json `
  --p1-run-spec <p1-run-spec.json> --p1-comparison <p1-comparison.json> `
  --label-ledger <label-ledger.json> --policy <actual-policy-v3.json> `
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
