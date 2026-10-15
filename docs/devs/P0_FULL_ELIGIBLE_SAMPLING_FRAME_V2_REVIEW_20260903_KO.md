# P0 full eligible sampling frame V2 구현·재회의 검토

작성일: 2026-09-03 KST
판정: `ADOPT_COMPONENT_ONLY / PRESENTED_SERIALIZATION_AND_DETERMINISTIC_REPLAY_PASS / ACTUAL_FULL_FRAME_AND_PROBABILITY_SAMPLE_NO_GO`

## 결론

V1의 selected 40개 목록은 전체 적격 모집단과 제외 사유를 보존하지 않아 표본추출틀, 포함확률, 누락 감사의 근거가 될 수 없었다. 이번 작업은 기존 V1 route·protocol·worker·Windows sandbox·13-child packet을 바꾸지 않고, **제출된 full census를 strict canonical bytes로 봉인하고 고정 층 안에서 결정적 표본 계획을 재생하는 V2 component**를 별도로 추가했다.

검색·통계·데이터/MLOps 전문가 사전회의와 구현 후 반대검토는 이 component만 채택했다. 외부 bounded enumeration completeness, 서명된 owner precommit, 외부 future-seed beacon, 실제 adapter/runtime·code identity는 아직 없으므로 actual source credit은 `0/40`, A-context 사람 검토는 `0/20`, 지표는 `NOT_ESTIMABLE`이다. `p0_phase_exit=false`, production/full scan과 Pyserini·gold-lite·reranker/NIL 실험은 계속 금지한다.

## 채택한 V2 범위

추가한 구현은 다음 세 파일이다.

- `src/llm_batch/grounding/p0_full_eligible_sampling_frame_v2_contract.py`: I/O 없는 producer. 제출된 scope·census·seed 값으로 canonical artifacts와 deterministic plan을 만든다.
- `src/llm_batch/grounding/p0_full_eligible_sampling_frame_v2_parent_validator.py`: producer와 `llm_batch`를 import하지 않는 별도 구현 validator. 원문 bytes부터 census·frame·seed·plan을 독립 재계산한다.
- `tests/test_p0_full_eligible_sampling_frame_v2.py`: chronology, lineage, quota, canonical bytes, scalar 혼동, coordinated reseal, parent 독립성을 검증한다.

입력 origin은 `ACTUAL_SCHEMA_CONTRACT_EXAMPLE_ONLY` 하나만 허용한다. profile은 caller label이 아니라 봉인된 adapter mapping으로 유도하며, 층은 `(source_profile, platform, UTC day)`로 고정한다. profile별 quota는 10, 총 40이다. 층이 부족하면 underfill로 종료하고 다른 층 spill, adaptive rebalance, reserve, replacement, backfill을 허용하지 않는다.

후보 ID는 locator에서, lineage group은 root locator에서 유도한다. 한 lineage group은 root가 최대 하나이고 root가 있으면 모든 member의 canonical minimum이어야 한다. 모든 member는 같은 root commitment와 같은 profile·platform·UTC-day 층을 가져야 한다. rootless group은 모든 member가 `UNKNOWN`일 때만 허용하며 표본에서 제외한다.

eligibility와 exclusion은 제출된 rights·collection·takedown·adapter·lineage primitive만으로 producer와 parent가 각각 재계산한다. title, body, surface, alias, `아생갤`, gold, target, parser-extra 같은 의미 필드는 census에 들어갈 수 없다. 따라서 이 component는 약칭이나 갤러리/작품 의미를 추정하지 않는다.

## 봉인 순서와 통계 의미

고정 순서는 다음과 같다.

1. scope와 future-seed specification을 먼저 고정한다.
2. frame cutoff 뒤 full census와 frame manifest를 봉인한다.
3. 제출된 owner-precommit reference와 timestamp를 기록한다.
4. seed를 reveal하고 seed receipt를 봉인한다.
5. eligible inventory, lineage unit, stratum별 rank와 selection plan을 봉인한다.

selection rank는 derived seed, eligible sampling-unit inventory SHA, stratum ID, lineage-unit SHA에 결속된다. full census, frame manifest, seed receipt는 plan에 별도로 결속된다. 제외된 junk row를 바꾸면 census/frame/seed artifact는 달라지지만 동일한 적격 inventory의 선택 ID와 rank는 재무작위화되지 않는다.

`n_h/N_h`는 float가 아니라 최대공약수로 약분한 정수 분수다. 예를 들어 quota 10, 적격 12이면 `5/6`으로 기록한다. 이는 **제출된 census가 완전하고 적격성·lineage가 사실이라는 조건 아래의 nominal design fraction**일 뿐, 실제 포함확률 추정치가 아니다.

## 권위와 진실 경계

현재 positive truth는 canonical serialization과 deterministic recomputation뿐이다. 특히 `frame_owner_precommit_sha256`과 timestamp는 caller가 제출한 참조값이며 다음을 증명하지 않는다.

- bounded scope의 외부 모집단 완전성
- 독립 owner의 서명, 고정 key store, trusted time, revocation, durable nonce
- enumeration adapter 실행과 cursor/page/high-watermark closure
- rights·takedown·lineage·eligibility의 사실성
- external beacon seed의 진위, 예측 불가능성, no-reroll/no-withhold
- code/dependency/runtime identity 또는 capture-before-selection 비간섭
- actual semantic evidence, route/packet/ledger credit, P0 Exit, production/full scan 권한

parent receipt가 추가로 참이라고 말할 수 있는 것은 `parent_separate_implementation_frame_replay_verified=true`뿐이다. producer·parent의 same-process code identity, 외부 population/owner/seed/runtime authority는 모두 false다.

## 반대검토에서 닫은 두 결함

구현 후 독립 검토에서 다음 반례를 재현하고 공개 회귀로 고정했다.

1. parent가 같은 lineage group의 `(derived profile, platform, UTC day)` 단일성 검사를 빠뜨려, 공격자가 census 전체를 일관되게 재봉인하면 cross-stratum lineage가 parent를 통과할 수 있었다. parent에 독립 cardinality 검사를 추가했다.
2. parent의 object canonical re-encode에서 escaped surrogate가 raw `UnicodeEncodeError`로 공개 API 밖까지 빠져나왔다. 이를 `P0FullEligibleSamplingFrameV2ParentValidationError`로 정규화했다.

producer 상수나 manifest monkeypatch가 parent 판정을 바꾸지 않는 공격 회귀도 통과했다. UTF-8, NFC, LF, BOM/CR, duplicate key, nonfinite number, bool/int·float 혼동, field-set, self-hash와 canonical byte equality를 모두 fail-close한다.

## 검증과 비간섭

최종 검증은 다음과 같다.

| 범위 | 결과 |
| --- | --- |
| 신규 component focused | `18/18 PASS` |
| parser·route·protocol·sandbox·packet 인접 | `128/128 PASS` |
| 전체 `test_p0_*.py` | `618/618 PASS` |
| producer·parent·test compile | `PASS` |
| producer/parent contract manifest | `efed07649c14cc2af0b0916ef6e6a04b39ad0c9147b97daec74428521287111b` exact 일치 |
| 기존 packet inventory | `CHILD_FILES == 13`, V2 연결 없음 |
| 중앙 Slang DB 1개 + publication journal 5개 | bytes·SHA `6/6` 불변 |

이번 검증은 pure component unittest와 read-only hash audit이므로 dashboard를 띄우지 않았다. 실제 test/validation run은 저장소 원칙대로 dashboard ON, `--parallel 16`을 사용해야 한다.

## 전문가 사후회의 판정

- 검색·retrieval: `ADOPT_COMPONENT_ONLY / PRESENTED_SERIALIZATION_AND_DETERMINISTIC_PLAN_ONLY / ACTUAL_FULL_FRAME_NO_GO`
- 통계·평가: `ADOPT_COMPONENT_ONLY / PRESENTED_CENSUS_CONDITIONAL_NOMINAL_DESIGN_ONLY`; 실제 probability sample과 metric은 `NOT_ESTIMABLE`
- 데이터/MLOps: `ADOPT_COMPONENT_ONLY / PRESENTED_SERIALIZATION_AND_DETERMINISTIC_REPLAY_PASS`; owner precommit, future seed, population completeness는 `NO_GO`

세 분과 모두 기존 V1을 실제 full frame으로 승격하거나 현재 V2를 route/packet에 연결하는 안은 채택하지 않았다.

## 외부 조사·참조 task 상태

참조된 Codex task `01a05c8e-6daa-7a21-b207-008e5fa4f0aa`는 A100 host의 task 목록에는 존재하지만 body `read_thread`가 MCP internal error `-32000`으로 실패했다. 제목·요약을 연구 근거로 사용하지 않았다.

명시적으로 요청된 `chatgpt-deep-research-browser` live dispatch도 제출 전 단계에서 정지했다. 신규 run `20260902T195221Z-52ea5ddbe26f`는 `PROJECT_SESSION_STILL_LIVE / session_authority=pre_submit`, 기존 owner run `20260901T155700Z-63837e6702a4`는 exact session에서 `error / ChatGPT session not detected / Login button detected / no cookies applied`로 확인됐다. 사용자의 “첫 probe는 제출되지 않았다” 확인을 settle 명령에 반영했지만 하네스가 `NO_SUBMISSION_EVIDENCE_INCOMPLETE`로 거부했다.

`mcp-update-guard` 규칙에 따라 이 project session에서는 전역 Oracle runner/state를 강제 수정하거나 DevSpace MCP를 재시작하지 않았다. 두 run의 incident packet은 automation maintenance owner용으로 만들었고, diagnose가 fresh run을 unsafe로 판정하므로 추가 제출과 일반 웹 검색 대체도 하지 않았다. 이는 저장소 V2 component 채택과 별개의 자동화 repair-owner blocker다.

## 다음 작업 순서

1. cursor/page/snapshot/high-watermark chain과 외부 owner-pinned 정책으로 bounded enumeration completeness를 증명한다.
2. scope·census·frame·정책·quota·future-seed spec·run·nonce를 묶는 서명된 owner precommit과 fixed key store, trusted time/revocation, durable nonce를 마련한다.
3. provider·round·key·signature·exact response bytes를 보존하는 external beacon receipt와 no-fallback/no-reroll/no-withhold를 검증한다.
4. A-context 20개에 대해서도 별도 full frame을 만든다.
5. input별 result 정확히 1개, missing/duplicate/reorder/profile swap 거부, disposition과 `CORE_ERROR` ITT, no replacement인 batch accounting을 구현한다.
6. 각 input의 1:N observation과 gold missed span을 전수 사람 검토해 `unreviewed=0`을 만든다.
7. 그 뒤에만 새 process protocol·worker·Windows sandbox·route·packet·parent-ledger successor를 설계한다. 기존 계보는 변경하지 않는다.
8. 모든 gate 통과 뒤 dashboard ON·`--parallel 16`으로 actual 40+20을 실행한다.
9. P0 Exit 뒤에만 Pyserini BM25, gold-lite, retrieval/reranker/NIL shadow A/B를 시작한다.

Goal은 `ACTIVE / NOT_COMPLETE`다. 다음 내부 구현 tranche는 5번 batch exactly-one·`CORE_ERROR` accounting이지만, 실제 credit은 1~4의 외부 권위와 frame gate를 통과하기 전까지 계속 0이다.
