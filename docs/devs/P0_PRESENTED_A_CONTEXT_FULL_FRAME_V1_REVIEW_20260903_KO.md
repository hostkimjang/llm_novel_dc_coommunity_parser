# P0 presented A-context full frame V1 검토

작성일: 2026-09-03 KST
상태: `ADOPT_COMPONENT_ONLY / ACTUAL_A_CONTEXT_FRAME_NO_GO / METRICS_NOT_ESTIMABLE`

## 결론

기존 actual packet은 A-context 20개가 같은 `sampling_frame_sha256` 문자열을 공유하는지만 확인했다. 전체 모집단 원문, 포함·제외 판정, 선택과 surplus, 포함확률은 재생하지 않았고 packet receipt의 동명 필드는 source-input 40개 frame을 가리켰다. 테스트 fixture도 Track-A claim의 앞 20개를 사용했다. 모든 A-context의 frame SHA를 바꾸고 관련 행과 seal을 재봉인해도 기존 packet이 통과하는 반례를 확인했다. 현재 packet은 authority `NO_GO`라 actual credit 오염은 없지만, 외부 권위를 연결하기 전에 A 전용 frame predecessor가 필요하다.

요구사항·검색/annotation·통계/데이터·MLOps 네 관점의 회의는 별도 `presented A-context full frame V1`을 채택했다. 이 component는 caller가 제시한 pre-label census를 canonical bytes로 봉인하고, 고정 층에서 future-seed 기반으로 20개를 선택하며 모든 나머지 eligible unit을 surplus로 보존한다. 기존 A-context/packet V1과 13-child inventory는 변경하거나 실제 경로에 연결하지 않았다.

## 구현 범위

- `src/llm_batch/grounding/p0_presented_a_context_full_frame_v1_contract.py`: scope, full census, frame, seed receipt, selected 20+surplus plan의 producer와 fail-close validator
- `src/llm_batch/grounding/p0_presented_a_context_full_frame_v1_parent_validator.py`: producer/`llm_batch` import 없이 동일 raw chain과 rank·partition을 다시 계산하는 parent
- `tests/test_p0_presented_a_context_full_frame_v1.py`: positive fixture와 identity, chronology, raw-byte, scalar, cross-binding, authority/metric 공격 회귀

component manifest SHA는 `5b38f560cbe6c2af9294e79ad6298b798e7256426c2e1ca353162e7531c47aa9`다.

## 표본·분모 계약

canonical full census를 `C`, 원문에서 재계산한 eligible set을 `E`, excluded set을 `X`로 둔다. profile별 quota는 5개, 전체는 20개다. 각 고정 stratum `h`에서 모집단 크기 `N_h`, quota `n_h`를 봉인하고 `N_h < n_h`면 spill·backfill 없이 실패한다.

future-seed에서 파생한 rank로 각 층의 앞 `n_h`를 selected `S`, 나머지를 surplus `U`로 정한다.

```text
|S| = 20
S ∩ U = ∅
S ∪ U = E
|U| = Σ_h (N_h - n_h)
π_i = n_h / N_h
```

포함확률은 `Fraction`으로 기약한 exact integer numerator/denominator를 저장한다. selected와 surplus 전체 행을 plan에 보존해 count/hash만 위조할 수 없게 했다. input order는 canonical candidate order와 rank로 정규화하고 replacement, spill, retry는 모두 false다.

A-context opportunity 20과 surplus opportunity는 실제 사람 판정 수나 성능 metric 분모가 아니다. frame·plan·parent receipt는 아래 값을 고정한다.

```text
actual_a_context_review_count = 0
actual_surplus_review_count = 0
statistical_denominator_contribution = NONE
metric_status = METRICS_NOT_ESTIMABLE_PRESENTED_FRAME_ONLY
inferential_metrics_allowed = false
complete_case_metrics_allowed = false
```

## identity·label blindness·chronology

context unit은 A 전용 domain에서 `registry_record_id`, platform/community commitment, content fingerprint, surface span과 surface SHA를 결속한다. ID만 재발급하거나 서로 다른 post의 동일 content/span을 한 단위로 합치는 공격을 거부한다. census strict schema에는 truth, work/NIL, annotation, reviewer, inference, publication, gold/result 필드가 없으며 `아생갤` 표면으로 작품·현실 갤러리·alias target을 만드는 경로도 없다.

chronology는 `scope created ≤ frame cutoff < frame seal < presented owner precommit < seed reveal < selection seal`로 고정한다. scope는 upstream source sampling plan과 bridge inventory의 raw SHA, enumeration/eligibility/rights/strata/future-seed 정책 SHA를 결속한다. 다만 이 값들은 caller-presented commitment이며 외부 owner, beacon, capture 또는 adapter 실행의 사실성을 증명하지 않는다.

## 반대검토에서 닫은 결함

| 결함 | 조치 |
| --- | --- |
| A frame 없이 자유 문자열 SHA만 재봉인 가능 | A 전용 scope→census→frame→seed→plan raw chain과 독립 parent 추가 |
| 동일 content/span의 서로 다른 post 오병합 | `registry_record_id`를 context-unit domain에 포함 |
| Python `bool == int`로 count·sequence·확률 우회 | submitted nested row와 top-level count/boolean을 exact type으로 검증 |
| parent가 `5.0 == 5`를 quota로 수용 | 두 summary quota를 parent도 exact integer로 검사 |
| selected count/hash만으로 surplus 위조 | selected·surplus 전체 ordered inventory와 exact partition을 재계산 |
| deep JSON·초대형 integer·BOM/CRLF·oversize 예외 누출 | bounded canonical parser와 component 예외로 정규화 |
| producer frame 1MB, parent 64MB 상한 불일치 | parent frame 상한을 1MB로 통일하고 1,000,003-byte 공격 회귀 추가 |
| old frame/seed/plan 교차 재사용 | eligible 삭제·seed swap·registry rebinding predecessor 공격을 양쪽에서 거부 |

## 전문가 최종 판정

| 관점 | 판정 |
| --- | --- |
| 요구사항 | `ADOPT_COMPONENT_ONLY`; 기존 A frame 공백을 닫되 8개 seed registry는 다음 backlog |
| 검색·annotation | `ADOPT_COMPONENT_ONLY / ACTUAL_A_CONTEXT_FRAME_NO_GO`; label leakage·frame swap 공격 차단 |
| 통계·데이터 | `ADOPT_COMPONENT_ONLY`; selected/surplus exact partition과 비추론 분모 경계 통과 |
| MLOps | 1MB cap 불일치 수정 후 `ADOPT_COMPONENT_ONLY`; 운영 wiring 0 |

## 검증과 비간섭

| 검증 | 결과 |
| --- | --- |
| focused 신규 회귀 | `18/18 PASS` (`0.960s`; 독립 재검토 `0.974s`) |
| A-frame/source-frame/A-context/packet 인접 회귀 | `73/73 PASS` (`4.618s`) |
| 전체 `test_p0_*.py` | `723/723 PASS` (`51.644s`) |
| producer·parent·test `py_compile` | `PASS` |
| scoped `git diff --check` | `PASS` |
| 운영·packet·runtime reference | `0` |
| 중앙 Slang DB 1개 + publication journal 5개 | bytes/SHA `6/6` 기존 기준과 exact 일치 |

이번 작업은 pure unittest와 read-only hash 감사이므로 실제 grounding run이 아니다. dashboard와 `--parallel 16`은 사용하지 않았다. production runtime, publication WAL, 중앙 Slang DB에는 쓰지 않았다.

## 2026-09-04 census bounded incremental validation hardening delta

2026-09-03의 focused `18/18`, adjacent `73/73`, 전체 P0 `723/723`은 최초 component 채택 당시의 역사적 검증치로 보존한다. 이번 hardening은 wire/schema/manifest 의미를 바꾸지 않고, runtime 연결 전에 남아 있던 census 자원 경계를 보강했다.

builder는 `Sequence.__len__`만 믿지 않고 실제 enumerate loop에서 `1,000,000`행 상한을 다시 검사한다. 각 candidate는 `enumeration_sequence=1`인 canonical row 크기를 conservative lower bound로 사용해 `prepared`에 유지하기 전에 명백한 `64,000,000`-byte 초과를 거부한다. deterministic `candidate_id` 정렬 뒤에는 실제 sequence로 직렬화한 각 행을 output에 추가하기 전에 `64,000`-byte 행 상한과 `64,000,000`-byte 전체 상한을 exact 검사한다.

producer와 독립 parent parser는 `splitlines()`로 전체 line 목록을 만들지 않고 offset/newline 방식으로 한 행씩 진행한다. newline 위치로 행 길이를 계산해 slice 전에 `64,000` bytes를 넘는 행을 거부하고, exact field shape와 각 구현의 semantic row validator를 통과한 행만 결과 목록에 추가한다. 따라서 첫 malformed shape/semantic row, `1,000,001`번째 행, oversized first row에서 다음 parse나 큰 line copy 전에 fail-close한다.

이 구현은 constant-memory의 완전 streaming은 아니다. 정상 유효 모집단의 deterministic sort와 validated row list, 최종 bytearray→bytes 변환은 메모리에 남는다. 따라서 runtime wiring 시 병렬도별 메모리 예산은 별도 계측해야 하며, 이번 delta를 external enumeration completeness·runtime authority·actual evidence로 해석하지 않는다.

독립 성능·red-team 재회의는 deceptive sequence, `MAX_BYTES=1`, malformed 100,000행, oversized-first-row+후속 행, conservative/final row cap, total/row exact cap과 actual count·authority·production·denominator 재봉인을 반복했다. 최종적으로 새 수용 우회는 없었다. latest focused `24/24 PASS`, 인접 8모듈 `158/158 PASS`, 전체 P0 `988/988 PASS`, `py_compile PASS`, 중앙 DB/journal `6/6` 불변을 확인했다. noninterference receipt는 `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`다.

actual source/context credit은 계속 `0/40·0/20`, metric은 `NOT_ESTIMABLE`, P0 Exit·production·full scan은 `NO_GO`다. pure unit/static/read-only 검증이므로 dashboard와 `--parallel 16`은 적용 대상이 아니다.

## 남은 gate와 채택 순서

이 component 내부에서는 census와 frame substitution을 막았고, 기존 packet V1은 새 A frame을 소비하도록 제자리 재해석하지 않았다. 이후 additive packet V2에서 `source_sampling_frame_sha256`와 `a_context_sampling_frame_sha256`를 분리하고, selected A context 20개를 새 plan 및 annotation subject/target과 1:1 결속했다. 기존 13-child fixture와 SHA는 변경하지 않았다.

8개 seed URL candidate inventory와 `record_type/source_lineage/attested_at/status` shadow schema도 후속 component-only 단계에서 완료했다. 남은 순서는 rights 승인된 actual source capture, source-profile adapter/parser·attestation·code identity, external authority/runtime, exhaustive human review다. 외부 source enumeration completeness, owner/rights/capture authority, adapter runtime, seed beacon/randomness, annotation-not-started 증명은 여전히 외부·runtime gate다. census의 bounded incremental validation은 위 delta에서 닫았지만, constant-memory full streaming과 runtime 병렬 메모리 계측은 실제 wiring 단계의 별도 운영 과제로 남긴다.

actual source/context credit은 계속 `0/40·0/20`이고 P0 Exit, Pyserini, gold-lite, retrieval/reranker/NIL A/B, production/full scan은 `NO_GO`다. Goal은 `ACTIVE / NOT_COMPLETE`다.
