# P0 presented A-context annotation packet V2 구현·재회의

작성일: 2026-09-03 KST
판정: `ADOPT_COMPONENT_ONLY / MEMORY_ENVELOPE_ONLY / ACTUAL_AUTHORITY_NO_GO`

## 결론

기존 packet V1의 13-child 계약과 runtime 연결을 보존한 채, source/A-context upstream 11개와 annotation subject/precommit 2개, event target/precommit 2개를 묶는 별도 packet V2를 추가했다. child는 15개이고 manifest를 포함한 고정 member는 16개다. 이 컴포넌트는 caller가 제시한 원시 바이트를 메모리에서 검증할 뿐 파일 시스템, WAL, publication, 중앙 Slang DB에 접근하지 않는다.

최종 component manifest SHA는 `2a4b63518b8d80522469753191c9879af6f85f55828f28318a149911e564d59f`, fixed member contract SHA는 `37f3a34ab17c219065b81d9f2eb3d9a8876c5e32e12e7051ec30f3e5038385fc`다. 고정 aggregate cap은 `281,905,216` bytes다.

## 채택한 계약

- 외부에서 제공된 exact ordered 16-role raw SHA map을 필수로 받는다. manifest 내부 선언은 외부 pin으로 간주하지 않는다.
- 각 member의 role, path, media type, max bytes와 원시 SHA를 함께 결속한다.
- producer는 current target contract만 import하고, composed parent는 target parent만 호출한 뒤 manifest와 상위 통계·진실표를 독립 재생한다.
- source40, selected A-context20, subject20, target20의 구조 수만 인정한다. actual source/event/result/reviewer/gold/metric credit는 모두 0이다.
- `JUDGED/UNJUDGED/UNAVAILABLE` terminal 결과는 아직 0이고 denominator는 `NONE`이다.
- profile `5×4`, generic `5/5`, fixed taxonomy, `iid_independence_assumed=false`, source candidate cluster를 봉인한다.
- 권한, runtime, metrics, production, full scan, P0 exit와 action은 모두 false다.
- manifest cap은 child hash/decode 전에 검사하고, timestamp는 canonical RFC3339와 strict chronology를 적용한다.

## 전문가 반대검토

검색·통계·데이터·MLOps 회의는 외부 16-pin 부재, manifest 자기승인, opaque predecessor receipt 과대해석, bool/int 혼동, cap 이후 hash, nested map order 변조를 공격 축으로 삼았다. 최종 구현은 target parent receipt의 exact ordered raw map과 declared/full SHA를 다시 검증하되, predecessor subject parent receipt의 내부 값은 독립 검증하지 못했음을 명시적으로 false로 남긴다.

최종 판정은 component-only 채택이다. 이 packet은 presented 구조의 무결성만 증명하며, 실제 capture·owner·reviewer·journal authority 또는 의미 정확도를 증명하지 않는다.

## 검증

- focused packet V2: `15/15 PASS`
- subject/target/packet 및 기존 packet 인접: `72/72 PASS`
- 최종 전체 P0 재검증: `817/817 PASS`
- 중앙 Slang DB 1개와 publication journal 5개: byte/SHA `6/6` 불변
- packet V1과 기존 runtime wiring: 변경 없음

## 다음 gate

고정 16-member를 직접 Windows held-handle로 읽는 별도 V2와 owner 서명 수학·supervisor는 additive successor로만 진행한다. 외부 key provisioning, trusted time/revocation, durable nonce, external root/code authority, OS write deny와 실제 semantic evidence 전에는 Pyserini BM25, gold-lite, reranker/NIL A/B, P0 exit, production/full scan을 시작하지 않는다.
