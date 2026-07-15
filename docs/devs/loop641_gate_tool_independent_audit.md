# Loop641 post-run gate 도구 독립 감사

초기 44개 테스트가 통과한 뒤 독립 subagent가 merge·adjudication·search gate를 공격적으로 재현했다. 그 결과 self-authored GO, checkpoint 위치 미결박, runtime/manifest 불일치, blind packet 변조, incomplete search manifest, self-review terminal 등 실제 fail-open이 확인됐다.

## 보강 결과

- merge: Loop640 checkpoint는 원본 panel 위치, Loop641 checkpoint는 original-order residual 위치에 exact bind한다. Row·manifest·plan의 stable runtime contract를 교차 검증하고, 입력 수를 포함해 달라지는 raw `config_hash`는 component별로 보존한다.
- adjudication: actual source/baseline/after/golden을 다시 계산하고 `drift_id`로 N=5 multi-variant union을 보존한다. Blind source는 allow-list만 사용하며 packet/map hash와 actual publication/golden/terminal 계약을 validator가 재검증한다.
- always-on: 수기 6필드 GO나 변조된 validator receipt를 거부하고 validated artifact readback과 runtime `375/375/0/0`을 요구한다.
- search: production scope `375/16`, complete manifest, result/post-id/run composition hash, shard 상세, runtime 완료 이후 postflight, golden18 positive loss hard block을 요구한다. No-public terminal은 source-only packet, packet row hash, 별도 reviewer, 실재 artifact SHA를 모두 검증한다.
- flip: `safe_loss_flip_rate_probe.py` 직접 실행 import 결함을 고치고 entrypoint를 테스트로 고정했다. N=5 실행 예산은 아직 사용하지 않았다.

검증은 관련 8개 suite `86 tests PASS`, `py_compile PASS`다. 이 판정은 `GO_TOOL_CONTRACT_ONLY`이며 Loop641 runtime completion, merged375 semantic gate, architecture refactor 또는 production 승인을 뜻하지 않는다. 현재 `semantic_quality=REVIEW-LOCKED`, production `full_scan_approval=false`다.
