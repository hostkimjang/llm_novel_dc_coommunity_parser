# P0 key-less actual packet 구현·최종 재검토

작성일: 2026-09-02 KST
상태: `STRUCTURAL_CONTRACT_IMPLEMENTED / A_CONTEXT_18_PASS / ROUTE_27_PASS / PACKET_19_PASS / FOCUSED_64_PASS / SELECTED_ADJACENT_285_PASS / EXAMPLE_BYTES_ONLY / NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED`

## 결론

실제 owner key와 외부 자료가 오기 전에 40 source input과 20 A-context의 구조·회계를 검증하는 key-less packet 계약을 구현했다. 별도 A-context/A-event, capture 전 input plan, label-blind claim/A-subject seal, parser terminal route, manifest 1개와 child 13개의 canonical byte inventory를 원자료에서 다시 계산한다.

구조 계약과 최종 red-team 회귀는 통과했지만 현재 자료는 controlled example/test bytes뿐이다. 외부 actual source claim은 `0/40`, 실제 사람 A-context review는 `0/20`, credited count도 `0/40`, `0/20`이다. owner·OS write-deny·Windows handle·journal/watch·runtime authority는 모두 false이며 P0 Exit, production, full scan을 열지 않는다.

## 구현 범위

| 영역 | 구현 | 권한 경계 |
| --- | --- | --- |
| A-context | `p0_actual_a_context_contract.py`가 Track-A claim, `WORK_ID/NIL/UNRESOLVED`, candidate/evidence cutoff, 사람 review journal과 no-write projection을 검증 | validated 20건이 있어도 `actual_a_context_review_count=0`, `authority=SHADOW_ONLY` |
| parser route | `p0_actual_route_contract.py`가 capture 전 input plan, label 확인 전 claim seal, profile `10×4`, `TYPED/GENERIC_PENDING/PARSER_ERROR` exact-one route와 parser receipt v2를 검증 | route accounting 완료는 owner authority나 운영 승인 아님 |
| terminal packet | `p0_actual_packet_contract.py`가 caller-pinned manifest file SHA, canonical JSON/JSONL, 고정 13-child inventory, payload span, A-subject seal, candidate registry, stored receipt를 재계산 | portable directory 검사는 Windows handle authority가 아님 |

controlled packet의 구조 회계는 다음과 같다.

- source profile: `OFFICIAL_STRUCTURED/COMMUNITY_STRUCTURED/MEDIA_OCR/GENERIC_FALLBACK = 10/10/10/10`
- route: input `40`, typed input `30`, parsed claim row `31`, generic `10`, error `0`
- claim inventory: 전체 `41`, label-blind selected unit `40`
- A: context `20`, annotation event `20`
- 파일: manifest `1` + child `13`

전체 claim inventory `41`과 parser의 typed claim row `31`은 같은 분모가 아니다. 전자는 generic sealed claim unit 10개를 포함하고, 후자는 typed parser output만 센다. 이 둘을 합쳐 actual 40건으로 보고하지 않는다.

## 최종 red-team에서 닫은 일곱 축

1. **span/source binding**: 같은 surface를 다른 offset으로 재단해 다른 claim처럼 보이게 할 수 있었다. A-context가 참조한 모든 claim의 `span_start`, `span_end`, `span_text`를 captured content와 직접 대조하도록 보강했다.
2. **subject seal chronology**: A-subject seal이 context 관측보다 앞서도 통과할 수 있었다. seal 시각이 모든 selected context 관측 이후인지 검증한다.
3. **candidate cutoff**: candidate registry가 context의 evidence cutoff 뒤에 생성돼도 observation 시각만 맞으면 통과할 수 있었다. registry 생성 시각을 evidence cutoff에도 결속했다.
4. **parser-after-capture**: actual parser가 일부 source capture 전에 시작해도 receipt 자체 회계만 맞으면 통과할 수 있었다. 모든 source의 `collected_at <= parser.started_at`을 요구한다.
5. **generic claim parser binding**: generic sealed claim unit이 packet에는 있으면서 parser receipt의 output claim hash 밖에 남을 수 있었다. typed와 generic을 포함한 전체 claim inventory와 generic terminal queue를 parser receipt에 함께 결속했다.
6. **parser manifest provenance substitution**: 한 claim row만 다른 `parser_manifest_sha256` 또는 `parser_version`으로 바꿔도 개별 row self-hash를 다시 만들면 통과할 수 있었다. 모든 parser claim row가 단일 manifest SHA와 version을 공유하도록 검증한다.
7. **equal-timestamp chronology**: parser `completed_at`과 selection seal `sealed_at`이 같아도 통과해 label-blind 선후 관계가 모호했다. `completed_at < sealed_at`을 강제한다.

각 수정에는 positive branch를 보존한 음성 회귀 테스트를 추가했다. final test 수는 A-context `18`, route `27`, packet `19`다.

단일 claim provenance substitution은 닫혔지만 모든 claim row를 동일한 새 manifest/version으로 재봉인하는 공격은 구조적 일관성만으로 원본 parser를 식별할 수 없어 통과한다. 이것은 `ACTUAL_LAUNCH_CAPTURE_BINDING_NOT_VERIFIED` blocker다. authority step 6의 owner-authorized launch/capture witness에 `expected_parser_manifest_sha256`와 `expected_parser_version`을 넣고 route receipt의 값과 교차결속해야 한다.

## 검증 결과

정본 Python 환경은 저장소의 `.venv312`다.

```powershell
.\.venv312\Scripts\python.exe -m unittest `
  tests.test_p0_actual_a_context_contract `
  tests.test_p0_actual_route_contract `
  tests.test_p0_actual_packet_contract
```

결과는 `64 PASS`다. 기존 actual registry·authority와 observation, framed WAL, publication, Slang, calibration 인접 선택 묶음은 `Ran 285 tests in 12.307s / OK`로 통과했다. 시스템 Python으로 실행한 한 시도는 `httpx`가 없어 import error 1건이 났지만 `.venv312` 정본 런에서는 재현되지 않았으므로 기능 회귀로 세지 않는다.

## 증거와 SHA 경계

packet 테스트는 메모리와 임시 디렉터리에서 deterministic bytes를 만들지만 tracked external actual fixture나 owner-signed receipt가 아니다. 따라서 테스트가 생성한 packet manifest SHA를 durable artifact SHA로 문서화하지 않는다.

기존 authority v2 정본 SHA는 변경하지 않았다.

- authority manifest: `1a6e4af406dc687e5335773a443987703be0669478e4c4671bfe705f827985ed`
- unsigned final attestation: `b21e0e6ee2c180568d78bbda3602fccfad838c0ae873b67bdc4343e0146f9a5b`
- authority receipt: `3f692bc338dfecf9f7f721c4872c6240e2b6817a88d42e7957e84f4855df2d35`
- event-byte receipt: `d62553a2042902b65403543e265fff3b65604dedc73615ff9306598971082dbe`

이 SHA들도 schema example과 unsigned receipt의 정본일 뿐 실제 owner authority가 아니다.

## 남은 게이트

다음 항목은 미완료다.

- run root 밖에 provision한 owner anchor와 detached final signature
- caller-pinned actual root와 외부 category→root mapping
- Windows handle-level final path, volume, file ID, junction/reparse/TOCTOU 검증
- event-byte receipt와 journal/watch authority bundle 결속
- 독립 OS write-deny witness와 runtime noninterference
- 실제 capture/parser shadow와 외부 source claim 40건·사람 A-context 20건

따라서 최종 상태는 다음과 같다.

- `gate_status=NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED`
- `p0_phase_exit=false`
- `production_approval=false`
- `full_scan_approval=false`
- `runtime_noninterference_verified=false`

Pyserini, gold-lite, reranker/NIL semantic A/B는 위 actual P0 Exit 뒤에만 시작한다.

## 후속 authority bridge·Windows handle tranche

이 문서의 `64/285 PASS`는 key-less packet tranche의 역사 결과로 보존한다. 후속 A-event raw bytes, packet receipt v2, authority one-way bridge, Windows bounded handle binding과 fresh `115/134/299 PASS` 결과는 [P0 authority bridge·Windows handle 구현·재검토](P0_AUTHORITY_BRIDGE_AND_WINDOWS_HANDLE_REVIEW_20260902_KO.md)에 분리 기록했다. 후속 tranche도 actual `0/40`, `0/20`, external trust·OS write-deny·USN/watch·runtime false, `NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED`를 유지한다.
