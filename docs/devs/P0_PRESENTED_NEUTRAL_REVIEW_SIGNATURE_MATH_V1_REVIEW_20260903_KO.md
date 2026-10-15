# P0 presented neutral review signature math v1 검토

작성일: 2026-09-03 KST
최종 판정: `ADOPT_COMPONENT_ONLY / SIGNATURE_MATH_AND_CANONICAL_RAW_BINDING_PASS / EXTERNAL_REVIEW_AUTHORITY_NO_GO / SEMANTIC_GATE_NO_GO`

## 결론

후속 중립 검토 캠페인이 사용할 네 서명 종류를 기존 owner 서명과 분리했다. 채택 범위는 caller가 제시한 P-256 공개키 좌표, canonical subject·payload 원문, low-S 서명의 수학적 일치와 고정 역할·purpose·domain 매핑뿐이다. 이 결과는 외부 키 provisioning, reviewer 신원·독립성·blinding, 검토 내용의 사실성, 신뢰 시각·revocation·durable replay, 실제 human review 또는 지표 적격성을 증명하지 않는다.

기존 presented review accounting 40건에 서명만 덧붙여 actual로 소급 승격하는 안은 기각했다. `actual_human_review_count=0`, `actual_human_unreviewed_input_count=40`, `statistical_denominator_contribution=NONE`이며 새 campaign precommit이 필요하다. Pyserini BM25, gold-lite, reranker/NIL A/B, 작품·alias·sense 승격, P0 Exit, production/full scan은 계속 `NO_GO`다.

## 구현 범위

- `src/llm_batch/grounding/p0_presented_neutral_review_signature_math_v1_contract.py`
- `src/llm_batch/grounding/p0_presented_neutral_review_signature_math_v1_parent_validator.py`
- `tests/test_p0_presented_neutral_review_signature_math_v1.py`

서명 종류와 고정 역할은 다음과 같다.

| 서명 종류 | 전용 key role | 전용 purpose |
| --- | --- | --- |
| `CAMPAIGN_POLICY_PREAUTHORIZATION` | `REVIEW_POLICY_PREAUTH_SIGNING_ONLY` | `P0_NEUTRAL_REVIEW_CAMPAIGN_POLICY_PREAUTHORIZATION` |
| `REVIEW_LEASE` | `REVIEW_LEASE_SIGNING_ONLY` | `P0_NEUTRAL_REVIEW_LEASE` |
| `HUMAN_REVIEW_RESULT` | `HUMAN_REVIEW_RESULT_SIGNING_ONLY` | `P0_NEUTRAL_HUMAN_REVIEW_RESULT` |
| `FINAL_REVIEW_ATTESTATION` | `REVIEW_FINAL_ATTESTATION_SIGNING_ONLY` | `P0_NEUTRAL_REVIEW_FINAL_ATTESTATION` |

각 종류는 서로 다른 고정 signature domain을 사용한다. public-key pin은 exact 32-byte X/Y, RFC 5480 `id-ecPublicKey + prime256v1` DER-SPKI SHA-256 fingerprint, 단일 allowed domain을 가진다. envelope는 pin·subject·payload의 raw SHA와 artifact SHA, 캠페인·run·subject, key ID/epoch/fingerprint/principal commitment를 서명 입력에 결속한다. 서명은 exact 64-byte P1363 `r||s`이며 `0 < r < n`, `0 < s <= n/2`만 허용한다. 검증은 기존 provider-fixed Windows CNG primitive의 `Microsoft Primitive Provider`와 `NIST_P256`을 사용하며 production 모듈에는 key 생성·private signing API가 없다.

producer를 import하지 않는 parent는 pin·subject·payload·envelope 원문과 child receipt를 독립 파싱하고 CNG 검증까지 다시 실행한다. child receipt 전체가 독립 재구성과 같지 않으면 거부한다. 이 replay도 serialized receipt authority나 실행 trace 이전성을 부여하지 않는다.

## 전문가 회의와 반영 사항

| 관점 | 사전 판정 | 구현 후 발견 | 반영 후 판정 |
| --- | --- | --- | --- |
| 검색·semantic | 기존 owner receipt 재사용 기각, 전용 domain 요구 | payload 내부 semantic/production field, 잘못된 달력 시각, 회계 vocabulary 누락 | recursive promotion field 금지, 실제 UTC 달력 검증, workflow/accounting/metric false 고정 후 `ADOPT_COMPONENT_ONLY` |
| 통계·실험설계 | 과거 40건 소급 서명 기각, 새 이중맹검 campaign 요구 | 단일 서명·같은 물리 키 4역할·통계 분모 오소비 위험 | review evidence·role key separation·quorum·adjudication·retrospective·denominator를 false/none으로 고정 후 `ADOPT_COMPONENT_ONLY` |
| MLOps·crypto | hardened CNG primitive만 재사용, external provisioning 별도 요구 | malformed SHA 타입이 `TypeError`를 누출하는 반례 | SHA 선검증과 int/list/null 전용 오류 회귀 추가 후 `ADOPT_COMPONENT_ONLY` |

모든 전문가가 최종 component-only 채택에 합의했다. external review authority와 semantic/metric gate는 모두 `NO_GO`다.

## 공격 회귀

| 공격 | 결과 | 경계 |
| --- | --- | --- |
| role·purpose·domain 교체 후 재서명·재봉인 | `REJECT` | 고정 kind profile 불일치 |
| 다른 kind의 서명 재생 | `REJECT` | domain-separated material과 expected kind 불일치 |
| payload·pin·subject·envelope 일부 교체 | `REJECT` | exact raw/artifact projection 또는 CNG mismatch |
| pin·key·subject·서명 전체 coordinated 교체 | 수학만 `PASS` 가능 | caller-presented pin이므로 authority·identity는 false |
| 같은 물리 키를 네 역할 pin으로 재포장 | 네 수학 검증은 `PASS` 가능 | `cross_role_key_separation_verified=false` |
| `target_work_id`, `alias_relation`, `semantic_metrics_allowed`, actual credit/gate, nested action/effect 주입 | `REJECT` | payload는 no-effect presented artifact만 허용 |
| impossible calendar date | `REJECT` | 달력상 유효한 UTC 초 단위만 허용 |
| 오래된 시각·공격자 revocation commitment | 수학만 `PASS` 가능 | trusted time·revocation은 false |
| 같은 envelope 재검증 | 재검증 가능 | durable replay prevention은 false |
| SHA 필드 int/list/null, BOM·CRLF·duplicate key·trailing data, 1 MiB 초과 | 전용 오류로 `REJECT` | raw entrypoint fail-close |
| signature bit flip, zero scalar, high-S | `REJECT` | fixed-width/range/low-S/CNG 검증 |
| child receipt에서 actual count·retrospective·denominator 위조 후 self-reseal | parent `REJECT` | 독립 전체 receipt 재구성 |

`아생갤` 같은 표면 텍스트가 payload에 존재하더라도 이 컴포넌트는 그 의미를 검증하지 않는다. 작품 ID, alias relation, sense 또는 현실 갤러리 판정으로 소비해서는 안 된다.

## 검증 결과

- focused signature math: `19/19 PASS`.
- external-owner signature + neutral review accounting + 신규 signature math: `69/69 PASS`.
- 전체 P0: `684/684 PASS` (`48.977s`, 최종 재실행).
- producer·parent·test `py_compile PASS`, scoped `git diff --check PASS`.
- runtime import/reference: `0`; actual packet `CHILD_FILES=13` 불변.
- source snapshot:
  - contract `1dad86ab5c7ce1d5a8c2fd7389f1e5ab9c58f36c54ea6c2a2c6627ffe2913f41`
  - parent `a7bce6ed3aa8a49911cad6f63c758d242e81f3f858656ec1c2ea4e58581392fb`
  - test `df0bed296cc1b16fdae724ce656a591596d9b0b1837280c4ba106548a195271c`
- 중앙 Slang DB 1개와 publication journal 5개는 bytes/SHA `6/6` 불변이다.
- 단위 테스트와 정적 해시 감사이므로 actual-run dashboard·`--parallel 16` 적용 대상이 아니다.

## 다음 작업 순서

1. run root 밖 fixed external store에 review policy/lease/final key와 reviewer roster key를 실제 provision하고, singleton 역할과 reviewer 역할의 distinct fingerprint·key ID·principal·independence group을 검증한다.
2. trusted time, signed revocation/key epoch, rollback-resistant durable nonce와 lease 소비를 별도 native verifier로 닫는다.
3. 기존 40건을 재사용하지 않고 새 campaign precommit을 만든다. 각 입력에는 opaque task ID와 exact payload bytes/hash만 노출하고 parser observation·disposition은 숨긴다.
4. 입력마다 서로 다른 person/key/independence group의 blind primary 2개를 먼저 동결한다. 그 뒤 sealed parser observation과 비교하고 불일치에만 독립 제3 adjudicator를 배정한다.
5. 40개 전 입력의 authority-qualified final terminal과 필요한 adjudication을 exact accounting한다. unavailable/unjudged가 하나라도 있으면 quality metric은 계속 산출하지 않는다.
6. external frame·source/runtime/code authority까지 모두 통과한 뒤 dashboard ON·`--parallel 16` actual run을 검토한다. 그 전에는 BM25·gold-lite·reranker/NIL 실험을 시작하지 않는다.
