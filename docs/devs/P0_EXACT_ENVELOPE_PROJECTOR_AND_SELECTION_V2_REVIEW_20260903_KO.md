# P0 exact-envelope projector와 selection v2 검토

## 결론

최종 판정은 `ADOPT_EXACT_ENVELOPE_PROJECTOR_COMPONENT_ONLY`다. 이번 작업은 호출자가 제시한 canonical envelope를 결정적으로 projection하고 부모가 같은 payload를 독립 재생하는 순수 컴포넌트만 채택한다. 실제 웹·API·OCR 소스를 수집하고 의미를 판정하는 source parser는 `NOT_IMPLEMENTED`이며, parser runtime·sandbox·ledger·authority·credit·P0 Exit·production·full scan은 모두 `NO_GO`다. 실제 source claim과 사람 검토 실적은 각각 `0/40`, `0/20`이다.

`p0_source_profile_parser_candidate.py`라는 파일명은 기존 candidate 계보를 위한 이름일 뿐이다. 공개 producer kind는 `PURE_EXACT_ENVELOPE_PROJECTOR_COMPONENT`, parser manifest는 contract manifest이며 `code_identity_verified=false`다. OCR의 두 SHA도 제시된 envelope의 문법 필드일 뿐 실제 media bytes나 OCR engine provenance를 증명하지 않는다.

## 채택 범위

- `OFFICIAL_STRUCTURED`, `COMMUNITY_STRUCTURED`, `MEDIA_OCR`은 입력당 정확히 한 문장만 받는다. 문서 전체가 정확히 `'<surface>'은 <definition>을 뜻한다`이고 `evidence_start=0`, `evidence_end=len(document)`일 때만 Track B `NEW_SENSE_CANDIDATE` 한 행을 투영한다.
- Track B 행은 `target_work_id=None`, `target_sense_id=None`이다. 작품 또는 의미 정답을 발명하지 않으며 semantic truth로 승격하지 않는다.
- `GENERIC_FALLBACK`은 정확히 한 `UNKNOWN` claim과 `GENERIC_PENDING` terminal만 만든다.
- 단순 mention, `SURFACE_MENTION`, label·target nested field, 비정규 JSON, 중복 key, 부분 span, 주변 부정문, 다중 문장은 claim 없이 `PARSER_ERROR`로 닫힌다. 따라서 `아생갤`을 `아카데미 생존 갤러리`, 현실 DC 갤러리 또는 `WORK_ALIAS`로 자동 승격하지 않는다.
- producer와 parent는 request/snapshot/plan/capture profile, UTF-8 payload hash, character span과 UTF-8 byte span, claim·terminal·witness·class·order를 각각 재계산한다. fully resealed target·claim·order 변조도 부모 replay에서 거부한다.
- 컴포넌트는 in-memory bytes/mapping만 다룬다. file·network·environment·clock·random·subprocess·registry·ledger·publication 호출은 하지 않는다.

## label-blind selection v2

기존 `p0_label_blind_claim_selection_seal_v1`과 `SHA256_RANK_WITHIN_PROFILE_V1` 의미는 archival validator에 보존했다. 안전한 현행 route는 `p0_label_blind_claim_selection_seal_v2`와 `SHA256_RANK_ONE_CLAIM_PER_INPUT_WITHIN_PROFILE_V2`만 허용한다.

V2는 profile별로 먼저 `registry_record_id`당 결정적 대표 claim 하나를 선택한 뒤 source input을 rank한다. 한 source가 1:N claim을 내어 profile 10개 credit을 독점하는 공격은 이 순서로 막는다. 공개 `validate_exact_claim_profile_quota`의 `require_distinct_inputs=False` 기본값은 V1 direct caller 호환성을 보존하고, V2 validator만 `True`를 명시한다. V1 seal은 archival 검증만 가능하고 V2 route completion에는 사용할 수 없으며 schema/algorithm 교차도 거부한다. route receipt schema는 v2이고 선택 schema와 algorithm을 명시적으로 투영한다.

## 전문가 회의와 보정

초기 회의는 source-profile parser 후보보다 더 좁은 exact-envelope projector를 우선 구현하고 기존 capture probe, worker, Windows sandbox와 packet 13-child inventory를 변경하지 않기로 했다. 첫 구현 뒤 재회의에서 다음 문제를 찾아 모두 보정했다.

1. mention을 `NON_TERM_EVIDENCE`로 승격하던 의미 과장을 제거했다.
2. `capture_profile == source_profile.lower()`를 producer와 parent가 독립 검증하게 했다.
3. parser·semantic proof처럼 보이던 명칭을 projector·presented-payload replay로 낮췄다.
4. V1 archive 의미와 V2 secure route를 별도 schema·algorithm으로 분리했다.
5. 1:N source quota inflation을 source-first representative selection으로 막았다.
6. V1 공개 helper 기본 의미를 복원했다.
7. 부정문 내부 일부 span 세탁을 문서 전체·단일 문장 규칙으로 막았다.

최종 재회의 판정은 다음과 같다.

| 관점 | 판정 | 잔여 경계 |
| --- | --- | --- |
| 아키텍처 | `ADOPT` | exact-envelope projector component only; actual source parser 미구현 |
| red-team | `ADOPT_COMPONENT_ONLY` | same-process monkeypatch, transitive dependency closure와 실제 subprocess sandbox 미검증 |
| Windows/runtime | `ADOPT_EXACT_ENVELOPE_PROJECTOR_COMPONENT_ONLY` | capture probe 불변, packet runtime receipt 미결속, sandbox·ledger·authority NO-GO |

## 검증

- focused projector·route: `44/44 PASS`
- adjacent projector·route·packet·A event·supervisor·authority bridge: `120/120 PASS`
- 전체 `test_p0_*.py`: `585/585 PASS`
- 변경 Python 파일 `py_compile`: PASS
- 동일 request의 response bytes와 parent receipt 결정성: PASS
- 중앙 `slang_db/slang_db.json` 및 publication journal 5개: bytes·SHA `6/6` 완전 불변

이번 검증은 component unittest와 읽기 전용 hash 확인이므로 actual 연구 run이 아니다. 따라서 dashboard와 `--parallel 16` 적용 대상이 아니다. 향후 실제 40+20 run은 모든 gate 통과 뒤 dashboard ON, `--parallel 16`으로만 시작한다.

## 다음 gate

다음 안전 단계는 actual source-profile parser의 별도 설계다. 실제 source bytes·parser code/dependency identity·subprocess sandbox·process-wide deny·부모 전용 ledger를 외부 owner root/predecessor와 결속하고 새 packet/route successor를 별도 재회의해야 한다. 그 전에는 이 projector response를 runtime receipt, semantic evidence, owner authority 또는 실제 source credit으로 사용할 수 없다. Pyserini BM25, gold-lite, retrieval/reranker/NIL shadow A/B도 P0 Exit 뒤로 유지한다.
