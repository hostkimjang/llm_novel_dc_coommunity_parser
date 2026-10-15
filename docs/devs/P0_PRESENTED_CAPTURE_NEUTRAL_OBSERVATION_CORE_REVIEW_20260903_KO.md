# P0 presented-capture neutral observation core 검토

## 결론

최종 판정은 `ADOPT_PRESENTED_CAPTURE_NEUTRAL_OBSERVATION_CORE_AND_SEPARATE_REPLAY_COMPONENT_ONLY`다. 호출자가 제시한 제한된 `COMMUNITY_STRUCTURED` UTF-8 line-list bytes에서 원문 span과 제시된 정의문을 중립 observation으로만 추출하고, 별도 구현 parent가 같은 bytes를 재생한다.

여기서 raw는 HTTP wire bytes나 owner-pinned source adapter 산출물을 뜻하지 않는다. `PRESENTED_CAPTURE_BYTES_NOT_HTTP_WIRE_OR_SOURCE_ADAPTER_AUTHORITY`다. 이 컴포넌트는 source claim, 작품·sense·alias target, route, credit, runtime receipt 또는 ledger를 만들지 않는다. actual source claim과 A context 사람 검토는 계속 `0/40`, `0/20`이며 actual source parser·P0 Exit·production·full scan은 `NO_GO`다.

## 지원 계약과 출력 의미

지원되는 유일한 입력 계약은 다음 네 필드의 exact 조합이다.

- `source_profile=COMMUNITY_STRUCTURED`
- `content_type=text/plain; charset=utf-8`
- `capture_version=normalized-community-explicit-statement-lines-v1`
- `normalization_version=utf8_identity_v1`

`OFFICIAL_STRUCTURED`는 owner-pinned JSON/HTML→text adapter가 없고, `MEDIA_OCR`은 media bytes·OCR engine·transcript·lineage 결속이 없으며, `GENERIC_FALLBACK`은 수동 lane이므로 모두 `UNSUPPORTED_PROFILE`이다. actual example에서 official이 text/plain인 것은 편의 fixture일 뿐 실제 official adapter 규격 근거로 사용하지 않는다.

상태는 기존 route의 `TYPED/PARSER_ERROR`를 재사용하지 않고 다음처럼 분리했다.

| 상태 | 의미 |
| --- | --- |
| `MATCHED` | 모든 non-empty line이 허용된 whole-line 문형이며 1~64개 neutral observation을 모두 보존 |
| `NO_MATCH` | 정상 UTF-8 capture지만 무매치 또는 matching/nonmatching 문맥 혼합; observation 0 |
| `UNSUPPORTED_PROFILE` | profile 또는 capture adapter 계약 미지원 |
| `INVALID_CAPTURE` | empty/oversize/invalid UTF-8/BOM/NUL/CR/NFC/format-control/limit 실패 |

허용 문형은 조사 조합 네 가지의 `'<surface>'은/는 <presented_definition_text>을/를 뜻한다.`다. 출력 relation은 `PRESENTED_EXPLICIT_DEFINITION_STATEMENT`이며 원문에 있는 surface·presented definition·character span·UTF-8 byte span·hash만 담는다. `track`, `claim_kind`, `WORK_ALIAS`, `target_work_id`, `target_sense_id`, truth, publication과 credit 필드는 schema에 없다.

따라서 `아생갤 재밌다`와 alias 서술은 `NO_MATCH`다. exact 뜻 문형의 `아생갤`도 작품 판정이 아니라 중립 presented text observation만 남긴다. explicit alias relation, owner-pinned specific-work target, 공식·독립 커뮤니티 근거와 post-side 경쟁 작품 근거 전에는 Track A로 승격할 수 없다.

## 의미·무결성 공격 보정

사전·사후 검색/통계/데이터·MLOps 회의에서 다음 문제를 찾아 닫았다.

1. 앞줄 부정 뒤 matching line만 고르는 scope laundering을 막기 위해 모든 non-empty line이 문형과 일치할 때만 `MATCHED`로 한다.
2. 한 줄 안의 부정문·두 번째 문장 세탁을 막기 위해 quote, backslash, ASCII/fullwidth 종결부호와 ellipsis를 surface/definition에서 거부한다.
3. U+202E 등 시각 제어를 막기 위해 Unicode `Cc/Cf/Cs/Zl/Zp`와 zero-width format 문자를 거부한다.
4. metadata를 512자로 제한하고 같은 Unicode control policy를 적용한다.
5. parent의 Python `True == 1`, `1.0 == 1` 우회를 canonical JSON bytes 비교로 막았다.
6. observation 삭제·복제·재정렬, fully resealed span/surface/target 주입을 parent replay가 거부한다.
7. 최대 64개 observation은 전부 보존하고 65개는 부분 출력 없이 `INVALID_CAPTURE`로 닫는다.
8. parent에서 core import를 제거하고 schema·version·limit·grammar·manifest를 독립 literal로 pin했다. core version/manifest monkeypatch 결과는 거부한다.

parent receipt는 `parent_separate_implementation_capture_replay_verified=true`만 주장한다. `same_process_isolation_verified`, core·parent code identity, capture adapter authority, runtime/dependency closure와 actual semantic evidence는 모두 false다. core manifest도 `DECLARED_BEHAVIOR_CONTRACT_NOT_CODE_IDENTITY`이며 향후 executable identity로 사용할 수 없다.

## 전문가 최종 판정

| 관점 | 판정 | 잔여 hard gate |
| --- | --- | --- |
| 검색/grounding | `ADOPT_COMPONENT_ONLY` | official/OCR adapter와 alias/work 의미 결속 미구현 |
| 통계/평가 | `ADOPT_NEUTRAL_RAW_OBSERVATION_CORE_COMPONENT_ONLY` | full eligible frame, batch exactly-one, exhaustive surplus review |
| 데이터/MLOps | `ADOPT_CORE_AND_SEPARATE_REPLAY_COMPONENT_ONLY` | process protocol, held-source code identity, sandbox/runtime receipt, ledger, packet authority |

## 검증

- focused core·parent 공격 회귀: `15/15 PASS`
- adjacent core·projector·capture probe protocol·Windows sandbox·packet: `80/80 PASS`
- 전체 `test_p0_*.py`: `600/600 PASS`
- core·parent·test `py_compile`: PASS
- 기존 `CAPTURE_HASH_PROBE`, worker, Windows sandbox reference: 0; packet `CHILD_FILES`: 13 유지
- 중앙 Slang DB 및 publication journal 5개: bytes·SHA `6/6` 완전 불변

이번 검증은 component unittest와 읽기 전용 hash 확인이므로 dashboard·`--parallel 16` actual run 대상이 아니다.

## actual 연결 전 남은 순서

1. 선택 전 full eligible sampling frame, exclusion·lineage dedupe·외부 seed·포함 확률·no-replacement를 owner-precommit하는 plan successor를 만든다.
2. batch protocol에서 `input_sequence + registry_record_id + capture metadata + payload SHA + result SHA`를 input별 정확히 하나로 결속하고 omit/dup/reorder/profile swap을 거부한다.
3. disposition 합계, 전체 observation inventory, `CORE_ERROR`, 사람 검토·미검토 observation과 exhaustive annotation 분모를 별도 receipt로 회계한다. actual 후보는 surplus 미검토 0이어야 한다.
4. 기존 probe/worker/sandbox를 변경하지 않는 별도 process protocol·worker·Windows sandbox successor에서 parent-held exact source/launch manifest와 request/response/sandbox receipt를 결속한다.
5. official adapter와 OCR wire→transcript→engine→lineage successor를 별도 구현한다. 현재 OCR을 `ELIGIBLE_ROOT + utf8_identity` actual route로 열지 않는다.
6. parent-only ledger와 route/packet successor는 external owner pin, durable predecessor, idempotency·crash recovery, dependency closure와 OS deny가 닫힌 뒤 별도 재회의한다.

이 조건 전에는 actual `40+20`, gold-lite, Pyserini BM25, retrieval/reranker/NIL A/B를 시작하지 않는다.
