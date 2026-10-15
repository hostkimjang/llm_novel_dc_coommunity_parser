# P0 presented HTTP capture-intake V1 검토

## 판정

최종 판정은 `ADOPT_COMPONENT_ONLY / NO_GO_ACTUAL_CAPTURE`다. 연구에서 선별한 seed 8개와 caller가 제시한 HTTP 메타데이터·응답 바이트를 하나의 재현 가능한 입력 계약으로 묶었지만, 네트워크 capture를 실행하거나 외부 owner의 권리·보존 승인을 증명하지는 않는다.

- component manifest SHA: `e115cd8c8da2b7f4b09c0ff252055656ac206da062afc0fb9edbc517a8a77339`
- focused unittest: `31 PASS`와 subtest `17`
- seed·raw parser·profile parser adjacent: `84 PASS`와 subtest `55`
- actual source claim/A-context credit: `0/40`, `0/20`
- gate: `NO_GO_PRESENTED_HTTP_CAPTURE_INTAKE_ONLY`

구현은 [`p0_presented_http_capture_intake_v1_contract.py`](../../src/llm_batch/grounding/p0_presented_http_capture_intake_v1_contract.py), 독립 재구성은 [`p0_presented_http_capture_intake_v1_parent_validator.py`](../../src/llm_batch/grounding/p0_presented_http_capture_intake_v1_parent_validator.py), 공격 회귀 검증은 [`test_p0_presented_http_capture_intake_v1.py`](../../tests/test_p0_presented_http_capture_intake_v1.py)에 있다.

## 채택한 계약

계약은 seed registry V1의 exact 8행, Track A/B `3/5`, lineage family `4`를 고정한다. 각 seed는 다음 presented evidence와 결속된다.

- canonical requested URL, final URL, 순서가 고정된 redirect hop과 `urljoin(from, Location) == to`
- terminal HTTP status, lowercase ASCII MIME, 제한된 original content-encoding 표기
- 메모리에 전달된 decoded entity bytes의 길이와 SHA-256, 전체 응답 바이트 locator
- HTTP `Date` 또는 `Last-Modified` header와 동일 instant인 source timestamp
- caller-presented capture 시각·도구·config hash
- seed별 rights/retention attestation candidate reference

응답 본문은 intake·child receipt·parent receipt에 복사하지 않고 길이와 hash만 남긴다. 원본 `Content-Type` header bytes도 보존하지 않으므로 manifest는 normalized presented MIME임을 명시한다. capture clock, tool manifest, rights, retention은 모두 `PRESENTED_UNVERIFIED`, `NOT_ATTESTED`, `UNKNOWN_FAIL_CLOSED`다.

## 독립 replay와 반대검토

parent는 producer와 seed producer를 import하지 않고 caller-original metadata와 응답 bytes에서 bundle과 child receipt를 다시 만든다. 첫 구현은 child와 parent의 normalize helper를 함께 바꾸고 재봉인하면 `original_input_replayed=true`가 통과했고, Unicode 가짜 MIME도 수용했다. 독립 반대검토에서 두 반례를 실제 재현해 수정했다.

최종판은 public entry/exit에서 helper identity·code·defaults, semantic constants, manifest bytes/hash, module alias와 사용 attribute, SHA/ID/MIME regex를 closure-captured guard로 확인한다. coordinated child/parent helper patch, `json.loads`·Unicode normalization attribute patch, permissive MIME regex 교체, rights/credit 재봉인, redirect Location laundering, seed/payload swap은 모두 fail-close한다.

## 증거의 한계와 다음 단계

이 계약은 raw capture provenance의 구조를 정의할 뿐 실제 HTTP 실행 증거가 아니다. filesystem·network·subprocess·환경·clock 접근을 하지 않고 actual/semantic/index/publication/metric/production/full-scan 필드를 모두 `0` 또는 `false`로 유지한다. 따라서 이 순수 계약 테스트에는 dashboard와 `--parallel 16`을 적용하지 않았다.

다음 데이터 단계는 외부 owner가 승인한 전용 raw root·capture/rights/retention 정책과 실제 seed bytes를 provision한 뒤 진행한다. 그 전에는 HTML/OCR profile adapter, gold-lite, Pyserini BM25, retrieval/reranker/NIL A/B를 열지 않는다.
