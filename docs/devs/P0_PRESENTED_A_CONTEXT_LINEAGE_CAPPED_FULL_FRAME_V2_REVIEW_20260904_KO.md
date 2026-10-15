# P0 presented A-context lineage-capped full-frame V2 검토

작성일: 2026-09-04 KST

## 결론

판정은 `ADOPT_COMPONENT_ONLY / DOWNSTREAM_WIRING_0 / ACTUAL_METRIC_NO_GO`다. 기존 A-context full-frame V1은 후보 context 행을 직접 추첨하므로, 같은 source lineage의 여러 span·revision·mirror 행이 명목 표본 20개를 중복 점유할 수 있었다. V2는 기존 source V2·bridge·A V1을 변경하지 않고, source lineage를 먼저 뽑은 뒤 그 lineage 안에서 context 하나만 뽑는 additive 2단계 계약으로 이 문제를 닫는다.

이 판정은 presented serialization과 결정적 선택 수학에만 적용된다. 외부 rights/capture/owner/runtime 권위, 실제 semantic evidence, 사람 annotation, publication 승인을 만들지 않는다. 실제 source/context는 `0/40·0/20`, metric은 `NOT_ESTIMABLE_LINEAGE_CAPPED_PRESENTED_FRAME_ONLY`, P0 Exit·production·full scan은 `NO_GO`다.

## 채택 설계

- 입력 11개 raw는 source scope/census/frame/seed/plan 5개, bridge inventory 1개, A scope/census/frame/seed/plan 5개다. component manifest는 source·bridge·A V1 predecessor manifest와 역할별 크기 상한을 고정한다.
- source selected candidate와 bridge decoded payload, A context를 candidate ID로 재결속한다. lineage ID는 caller 필드가 아니라 검증된 source selected item에서 도출한다. registry·adapter·platform·profile/day, payload hash, `content_fingerprint`, exact `surface_sha256`, observed/published timestamp를 다시 계산한다.
- 순서는 `source plan selection < A scope creation`, `A V1 plan selection < lineage frame seal < owner precommit < seed reveal < V2 selection`이다. lineage frame은 reveal 전에 전체 eligible context와 lineage partition을 봉인한다.
- 각 profile-day 층의 distinct lineage 모집단을 `G_h`, quota를 `n_h=5`로 둔다. `G_h<n_h`이면 hard fail하고 spill·backfill·replacement를 허용하지 않는다.
- 1단계는 층별 lineage를 rank하고, 2단계는 선택된 lineage 내부의 context를 rank한다. 전역 cap은 lineage당 1개다. 같은 lineage의 여러 행은 표본 수를 늘리지 않는다.
- fixture는 eligible context `80`, distinct lineage `40`, selected lineage/context `20`, context surplus `60`, lineage surplus `20`이다. surplus 이유는 `WITHIN_SELECTED_LINEAGE_SURPLUS`와 `UNSELECTED_LINEAGE_SURPLUS`로 완전 분할한다.
- lineage 포함확률은 `n_h/G_h`, lineage가 선택됐을 때 context 조건부 확률은 `1/K_g`, context 주변확률은 `n_h/(G_h*K_g)`다. 분수는 기약형으로 저장하며 `contexts_are_iid=false`, 동일 lineage 쌍의 joint inclusion은 `ZERO`다.
- 전체 frame hash는 seed receipt에는 결속하지만 derived seed 입력에서는 제외했다. 따라서 제외 junk나 한 lineage의 member 수 증가는 다른 lineage 1단계 선택을 재무작위화하지 않는다. 해당 lineage의 2단계 context 선택만 바뀔 수 있다.
- producer는 runtime helper·상수·stdlib·callable code/defaults/kwdefaults와 mutable manifest canonical bytes를 고정한다. 독립 parent는 producer를 import하지 않고 frame, 양 단계 rank, 확률, partition을 재계산한다.

## 반대검토와 수정

통계·MLOps·테스트 관점의 반복 검토에서 predecessor receipt/callable 치환, bridge 검증 비대칭, bool seed ID, 늦은 artifact cap, `splitlines()` materialization, chronology 누락, helper/constant rebind, seed replay 과장 문구, 거대 정수 예외 누출, content/surface/time 미결속, Unicode control metadata, mutable manifest drift, producer의 늦은 preflight를 재현했다. 이를 exact raw/self-hash 재검증, producer-free bridge parity, 조기 role·aggregate cap, incremental parsing, strict chronology, runtime guard, canonical 오류 정규화, metadata category 거부와 16 MiB bridge role cap으로 닫았다.

최종 독립 재검토에서는 material residual defect가 보고되지 않았다. 다만 Claude Fable 협업 경로는 별도 증거로 채택하지 않았다. native subagent 두 시도는 `unreadable_encrypted_agent_task`로 실패했고, 기존 task에 `anthropic/claude-fable-5` override를 보낸 시도는 완료 상태였지만 읽을 수 있는 turn item이 없었다. 따라서 본 판정은 로컬 구현·테스트와 읽을 수 있었던 전문가 검토만 근거로 한다.

## 검증 근거

- focused: `tests.test_p0_presented_a_context_lineage_capped_full_frame_v2` → `24/24 PASS`.
- 인접 A/source/bridge/subject/temporal 6모듈 → `132/132 PASS`.
- 전체 P0: 승인된 Windows host 권한에서 `1037/1037 PASS` (`114.815s`). workspace sandbox의 최초 실행은 LocalAppData pycache `CreateDirectoryW` error 5와 restricted-token 파생 실패가 있어 코드 회귀 수치로 채택하지 않았다.
- child·parent·test `py_compile PASS`.
- component manifest: `c1080b53622b1b1bb93b127361e333cadeddf664c44a94d329257a6a918d250b`.
- V1 predecessor manifest: `5b38f560cbe6c2af9294e79ad6298b798e7256426c2e1ca353162e7531c47aa9`.
- fixture frame/seed/plan raw SHA-256: `d0cc0a9b6071f69ba9f6ab9db2e9abb259503a299fee52383707875b978e0e16`, `1093941faaf10fad717dfa62d72475b3df366cb23de793c398f00c7fd167ffda`, `4bba654eae0d9fe04cc92ef19b04be0681b4acc5c8bbff4a3958960cb963202a`.
- 독립 parent receipt: `a4b890eeefd9fd4612b75cb5fe867c7c8b30a7ffacba531efc8d3ed3e1ef9c76`.
- 중앙 Slang DB 1개와 publication journal 5개는 `6/6` byte/SHA 불변이다. noninterference receipt는 `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`다.
- 이 범위는 pure unit/static/read-only 검증이므로 dashboard와 `--parallel 16`은 `N/A`다.

## 다음 gate

이 V2를 기존 subject V2나 packet V2에 연결하지 않는다. 외부 owner의 rights/retention, 권위 있는 capture와 source lineage, trusted runtime/code identity, actual source 40·context 20 이중맹검 검토가 먼저다. 이후에도 별도 version boundary의 subject V3→target V3→packet V3로만 연결하고, gate 통과 뒤 Pyserini BM25→gold-lite→retrieval/reranker/NIL shadow A/B 순으로 연다.
