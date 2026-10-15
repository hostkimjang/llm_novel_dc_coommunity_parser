# P0 presented HTTP capture temporal evidence V2 검토

작성일: 2026-09-04 KST
상태: `ADOPT_COMPONENT_ONLY / NO_GO_PRESENTED_TEMPORAL_EVIDENCE_ONLY / VERIFIED`

## 결론

HTTP capture-intake V1은 HTTP `Date` 또는 `Last-Modified`에서 고른 값을 legacy `source_timestamp`로 기록했다. 그러나 `Date`는 응답 생성 시각이고 `Last-Modified`는 HTTP representation metadata일 뿐, 둘 중 어느 것도 그 자체로 페이지가 제공한 published/modified/version revision은 아니다.

이번 V2는 V1 wire와 component manifest를 변경하지 않는 additive presented-only component다. V1 intake와 receipt를 원 입력부터 재검증한 뒤 transport metadata와 decoded entity 안의 제한된 page-native temporal signal을 별도 projection으로 만든다. 네트워크 capture, 일반 HTML/JSON parser 실행, 외부 owner 권위, actual source credit은 추가하지 않는다.

구현 범위는 다음과 같다.

- `src/llm_batch/grounding/p0_presented_http_capture_temporal_evidence_v2_contract.py`: V1 predecessor 검증, transport/page-native 분리, artifact와 child receipt 생성·검증
- `src/llm_batch/grounding/p0_presented_http_capture_temporal_evidence_v2_parent_validator.py`: temporal producer를 import하지 않고 predecessor parent replay와 V2 projection을 별도 구현으로 재계산
- `tests/test_p0_presented_http_capture_temporal_evidence_v2.py`: marker, span, chronology, 자원 상한, runtime integrity, replay와 권위 과장 공격 회귀

## predecessor V1 불변과 시간 의미 분리

V2는 capture-intake V1의 component manifest SHA와 exact intake/receipt raw SHA를 predecessor로 고정한다. V1 schema, fixture, receipt 또는 기존 packet을 제자리 재해석하지 않으며 운영 runtime에도 연결하지 않는다.

각 행의 transport projection은 의미를 다음처럼 제한한다.

| 입력 | V2 의미 |
| --- | --- |
| HTTP `Date` | `HTTP_RESPONSE_ORIGIN_DATE_NOT_PAGE_REVISION` |
| HTTP `Last-Modified` | `HTTP_REPRESENTATION_METADATA_NOT_PAGE_NATIVE_REVISION` |
| V1 `source_timestamp` | `LEGACY_HTTP_METADATA_ONLY_NOT_PAGE_NATIVE_REVISION` |
| decoded entity의 지원 구문과 exact span | `PRESENTED_LOCATED` page-native revision observation 후보 |

`http_headers_accepted_as_page_revision=false`와 promotion count `0`을 행·bundle·receipt에서 유지한다. `Last-Modified`가 `Date`보다 뒤인 모순, HTTP metadata가 `presented_collected_at`보다 미래인 모순, page-native `published_at ≤ modified_at ≤ presented_collected_at` 위반을 caller-presented clock 안에서 fail-close한다. 이 순서는 trusted time 또는 capture 사실을 증명하지 않는다.

## 지원하는 page-native 구문 부분집합

V2는 일반 HTML/JSON parser가 아니라 최대 512-byte UTF-8 context와 최대 128-character value를 검사하는 bounded locator verifier다. 지원 범위는 다음 다섯 구문으로 한정한다.

- `JSON_LD_DATE_PUBLISHED`: context가 중첩 object/list 없는 top-level JSON object이고 `datePublished` marker의 exact value span과 일치
- `JSON_LD_DATE_MODIFIED`: context가 중첩 object/list 없는 top-level JSON object이고 `dateModified` marker의 exact value span과 일치
- `OPEN_GRAPH_ARTICLE_PUBLISHED_TIME`: 제한된 `<meta property="article:published_time" content="...">` 형태
- `OPEN_GRAPH_ARTICLE_MODIFIED_TIME`: 제한된 `<meta property="article:modified_time" content="...">` 형태
- `SITE_NATIVE_VERSION_TOKEN`: bounded context 안의 `data-version="..."`과 제한된 ASCII opaque token

행당 signal은 최대 3개이며 `PUBLISHED_AT`, `MODIFIED_AT`, `VERSION_ID`를 각각 한 번만 허용한다. value span은 서로 겹칠 수 없고 context/value SHA, half-open byte offset, UTF-8 decoding, syntax marker의 실제 value occurrence와 절대 payload attribute 경계를 모두 재검산한다. 지원하지 않는 HTML attribute 순서·추가 attribute·JSON nesting 또는 site-specific revision 표현은 추측해 수용하지 않고 후속 adapter 대상으로 남긴다.

## observation identity와 lineage 경계

`revision_observation_identity_sha256`는 domain, predecessor capture row SHA, 검증된 signal projection으로 결정적으로 만든다. 이는 한 capture에서 특정 locator를 관측했다는 identity일 뿐이다.

다음 의미로 사용하면 안 된다.

- 여러 capture 사이에서 유지되는 stable page revision ID
- `source_id`, `lineage_root_id` 또는 temporal lineage edge
- 중복 source의 독립성 증거
- actual source snapshot 또는 annotation sampling unit

signal이 없는 `NOT_EXPOSED` 행의 observation identity는 `null`이다. bundle의 identity inventory hash는 이 null을 포함한 ordered 8행 projection만 봉인한다.

## 노출과 최소화 경계

artifact와 receipt는 raw response body, raw context, unnormalized value span을 복사하지 않는다. 대신 locator, context/value SHA와 normalized scalar를 보존한다.

normalized scalar는 의도적으로 artifact에 노출된다. timestamp는 canonical UTC RFC3339 seconds로, version token은 검증된 ASCII token 그대로 저장되므로 원문이 이미 canonical이면 raw value와 같을 수 있다. 따라서 `page_revision_normalized_scalar_exposed_in_artifact=true`이며, 비노출 주장은 `page_revision_raw_context_or_unnormalized_span_exposed_in_artifact=false` 범위에만 적용한다. normalized scalar에도 개인정보나 민감 식별자가 들어갈 수 있는 source는 이 component에 제출하지 않고 별도 최소화 정책을 선행해야 한다.

## 순수 replay idempotency

`replay_idempotency_key_sha256`는 전용 domain 아래 predecessor intake raw SHA, predecessor receipt raw SHA, ordered presented page-revision record SHA 목록에서 파생한다. 동일 입력은 동일 artifact·receipt·key를 만들고 signal 입력 순서 차이는 canonical order로 정규화한다.

이 key는 pure deterministic replay의 동일 입력 판별자일 뿐이다. durable state를 소비하지 않고 nonce, trusted time, external owner signature 또는 effect ledger를 포함하지 않으므로 cross-process anti-replay, exactly-once execution, 외부 retry deduplication을 증명하지 않는다. `OPERATIONAL_EFFECT=NONE_SHADOW_ONLY`와 `action_applied=false`를 유지한다.

## 자원 상한과 독립 parent replay

V2는 predecessor의 seed 8개와 payload 상한을 그대로 승계하고 temporal artifact·receipt를 각각 2 MiB로 제한한다. 각 page record는 다음 순서로 preflight한다.

1. exact 8행과 행당 signal 최대 3개를 확인한다.
2. record hash 계산 전에 status·kind·syntax·normalized/presented value의 type과 길이를 검사한다.
3. offset을 exact nonnegative integer로 검사하고 payload 범위, context 512 bytes, value 최대 128 UTF-8 character 경계를 확인한다.
4. 그 뒤 canonical record hash, exact span SHA, marker/value 관계와 chronology를 재생한다.

이 순서로 oversized presented scalar가 self-hash 직렬화를 먼저 일으키는 경로와 Python negative slicing 우회를 닫는다. child와 parent의 public entry/exit guard는 helper code identity뿐 아니라 defaults·keyword defaults, 사용 module/regex/callable, semantic constants와 predecessor entrypoint를 고정한다.

parent는 temporal child producer를 import하지 않는다. capture V1도 producer가 아니라 기존 독립 parent validator로 원 입력부터 재생한 뒤, V2 row·bundle·child receipt를 별도 구현으로 재계산한다. parent receipt의 `parent_separate_implementation_replay_verified=true`는 이 구조적 replay만 뜻하며 runtime code authority나 external witness를 뜻하지 않는다.

## 1차 반대검토와 수정

| 1차 `REJECT` finding | 수정 |
| --- | --- |
| 임의 본문 timestamp/token을 JSON-LD·OG·native revision으로 라벨링 가능 | JSON object field, 제한된 OG meta 전체 형태, `data-version` marker와 exact value 관계를 child·parent 양쪽에서 검사 |
| 같은 byte span을 published와 modified 두 역할로 증식 가능 | value span overlap과 동일 역할 중복을 거부 |
| helper code만 고정해 `_integer`/`_int` default 변조로 음수 offset 수용 가능 | 모든 offset에 explicit minimum을 전달하고 helper defaults·keyword defaults를 runtime guard에 포함 |
| raw revision value 미노출이라고 했지만 normalized version/timestamp가 원문과 같을 수 있음 | raw context/unnormalized span 비노출과 normalized scalar 노출을 별도 manifest field로 분리 |
| signal 0에서도 `exact_payload_span_verified=true`가 존재 증명처럼 읽힘 | `all_presented_page_revision_spans_verified`로 의미를 축소하고 signal count `0`과 함께 읽도록 고정 |
| 큰 caller value가 field 상한 전에 canonical hashing됨 | per-record type·length·offset preflight를 record hash보다 먼저 수행 |
| deterministic hash는 있었지만 retry/idempotency 의미가 불명확 | domain-separated replay key를 추가하고 external anti-replay·effect deduplication이 아님을 manifest에 명시 |
| 같은 JSON scalar의 다른 field occurrence, nested marker, `not-data-version` suffix와 cropped context가 수용됨 | top-level flat JSON subset, marker group byte span, 원 payload의 좌·우 attribute 경계를 child·parent에서 결속 |
| `re.*`, HTTP date parser와 predecessor public entrypoint의 same-object code/default 변조 | 사용 속성과 외부 callable의 code/defaults/keyword-defaults를 runtime guard에 추가 |

## 권위·분모·동작 경계

이 component가 고정하는 것은 presented bytes와 제한된 locator syntax의 일관성뿐이다. 다음 값은 artifact, child receipt와 parent receipt에서 계속 `false` 또는 `0`이다.

```text
transport_time_authority_verified = false
page_revision_authority_verified = false
page_revision_parser_verified = false
capture_authority_verified = false
rights_authority_verified = false
retention_authority_verified = false
source_attestation_verified = false
actual_source_snapshot_credited = false
actual_authority_granted = false
metric_denominator_eligible = false
credited_actual_source_snapshot_count = 0
actual_credit_count = 0
metric_denominator = 0
claim_derivation_allowed = false
derived_index_allowed = false
publication_evidence_allowed = false
action_applied = false
p0_phase_exit = false
production_approval = false
full_scan_approval = false
```

현재 gate는 `NO_GO_PRESENTED_TEMPORAL_EVIDENCE_ONLY`, parent gate는 `NO_GO_PARENT_REPLAY_PRESENTED_TEMPORAL_EVIDENCE_ONLY`다. 권리·retention 승인, trusted capture/runtime, 외부 owner와 실제 source bytes 없이는 actual source/context credit, metric, publication 또는 production gate를 열지 않는다.

## 검증과 비간섭

| 검증 | 상태 |
| --- | --- |
| focused temporal V2 회귀 | `25/25 PASS` |
| seed·capture V1·temporal·actual registry·raw/profile parser 인접 6모듈 | `135/135 PASS` |
| 전체 `test_p0_*.py` | `1013/1013 PASS` (`102.983s`) |
| child·parent·test `py_compile` | `PASS` |
| `git diff --check` | `PASS` (기존 줄바꿈 경고만 존재) |
| 중앙 Slang DB 1개 + publication journal 5개 bytes/SHA | `6/6 UNCHANGED`, receipt `6033c6d0…204e` |
| 최종 독립 red-team delta | cropped `not-data-version` 포함 재현 공격 `REJECT`, 정상 version marker `ACCEPT`, material residual `0` |

component manifest SHA는 `8961fb8c5cc798d04eef08370563d7407344a70da4b43ea685406024f4f2cb8b`이고 독립 parent pin과 일치한다. predecessor V1 manifest `e115cd8c…7339`는 불변이다. 첫 전체 실행은 workspace sandbox의 Windows per-execution pycache ACL 때문에 코드 진입 전에 2건 실패했으며 결과로 채택하지 않았다. 같은 final code를 필요한 LocalAppData 권한에서 재실행한 `1013/1013`만 최종 결과다. 이 작업은 pure unit/static 검증 대상이므로 실제 grounding run이 아니며 dashboard와 `--parallel 16`을 적용하지 않는다. predecessor V1, packet V1/V2, seed inventory, A-context census와 운영 endpoint는 변경하지 않는다.

## 다음 우선순위

다음 additive P0 우선순위는 **A-context lineage-capped V2**다. temporal V2의 observation identity를 source lineage로 승격하지 않은 채, 같은 source lineage의 mirror·backup·temporal revision이 A-context opportunity와 selected 20을 중복 점유하거나 독립 표본처럼 계산되지 않도록 full frame과 selection cap을 별도 계약으로 고정해야 한다.

그 component도 기존 A-context V1/V2와 packet을 제자리 재해석하지 않고 별도 predecessor/parent replay로 구현한다. lineage cap, external enumeration completeness, rights/capture authority와 사람 annotation은 서로 다른 gate로 유지하며, actual `0/40·0/20`, metric `NOT_ESTIMABLE`, P0 Exit·production·full scan `NO_GO`를 계속 유지한다.
