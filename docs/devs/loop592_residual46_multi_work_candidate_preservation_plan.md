# Loop592 residual46 multi-work candidate preservation plan

- 목적: residual46 ordinary 중 multi-work/listing 맥락을 단일 public identity로 좁히면 위험한 행을 candidate-set 재구성 hold로 보존했다.
- 선택 행: `11668324`, `11718105`, `11661863`, `11708453`.
- Plan rows: `4`.
- Action: `candidate_set_rebuild_required_before_publish 4`.
- Multi-work/listing hold rows: `4`.
- Validation issue: `0`.
- Runtime replay allowed rows: `0`.
- 보정: 최초 publication audit에서 `scope_multi_work_or_listing_context` reason 누락이 잡혀 plan reason code를 보강했고, 재감사에서 publication contract `GO`를 확인했다.
- Test/runtime 계약: 다음 실제 run은 `--parallel 16`, web dashboard 기본 ON, `--no-dashboard` 금지다.
- Gate: multi-work/listing preservation `REVIEW-LOCKED`, full375 collateral `NO-GO`, goal `ACTIVE / NOT_COMPLETE`.
