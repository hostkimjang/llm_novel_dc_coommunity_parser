# P0 owner root preauthorization V2 supervisor 구현·재회의

작성일: 2026-09-03 KST
판정: `ADOPT_COMPONENT_ONLY / NO_GO_AUTHORITY / OPERATIONAL_NO_GO`

## 결론

preauthorization V2 공개 API를 정확히 1회 호출하고 반환 receipt를 독립 재검증하는 memory-only supervisor를 추가했다. 이 wrapper는 Windows V2를 직접 import하거나 호출하지 않으며, 기존 V1 authority/supervisor/runtime, WAL, publication, 중앙 Slang DB에도 연결하지 않는다.

최종 component manifest SHA는 `239b595763bf1bef0d5ab925d51f864f1c1c3090123f6ca540a225e4f9c4fddf`다. child receipt 88필드, safe projection 33필드, 단일 step receipt 12필드, supervisor receipt 77필드로 고정했다.

## 채택한 실행 계약

- 공개 API는 packet directory와 raw public-key pin, preauthorization, detached signature envelope, `observed_at`만 받는다.
- serialized child receipt, private key, callback/provider, caller-selected component/code/root authority pin은 받지 않는다.
- wrapper 입력의 exact byte type/cap을 child 호출 전에 검사한다.
- preauthorization V2 component SHA와 공개 callable signature를 검사하고, 검사한 동일 callable 객체를 정확히 1회 호출한다.
- child 88-field receipt의 exact ordered plain dict, scalar type, self-hash, component 4-pin, raw input SHA, `observed_at`, true/false truth table, 0 credit와 `NO_GO`를 독립 재검증한다.
- 전체 child receipt 대신 고정 safe projection과 declared/full SHA만 남긴다.
- supervisor 직접 Windows 호출은 0이다. child의 `windows_direct_validator_called_once=true`는 엄격히 결속한 child claim이며 supervisor 독립 관측이 아니다.

## 반대검토에서 발견해 수정한 결함

초기 초안은 raw input aggregate에 `packet_dir`가 없고 explicit step input/output hash가 없었다. coherent mock child 아래 서로 다른 packet directory가 동일 supervisor receipt를 만드는 PoC가 성공했다.

수정본은 `STR/PATH` 입력 종류와 lexical UTF-8 길이·SHA를 raw input binding에 추가했다. 별도 domain의 ordinal 0 exact step receipt가 raw input binding SHA, child declared/full receipt SHA, child safe/truth projection SHA, preauthorization 실행 1회와 supervisor 직접 Windows 실행 0회를 self-hash로 봉인한다. 서로 다른 directory는 raw-input, step, final receipt SHA가 모두 달라진다.

또한 dependency callable을 검사한 뒤 다시 `getattr`하던 check/use 창을 닫았다. 검사 함수가 검증한 callable 객체를 반환하고 그 객체만 1회 호출한다. 동시 poison PoC에서 checked callable 1회, poison callable 0회를 확인했다.

## 진실 경계

supervisor가 직접 관측하는 것은 wrapper precheck와 child API 1회 호출뿐이다. Windows 실행, 서명 수학, owner/root/code 신뢰를 독립적으로 재실행하거나 증명하지 않는다. step receipt도 portable한 구조 결속이지 인증된 실행 trace가 아니다.

coherent same-process monkeypatch, complete attacker bundle substitution과 동일 bundle replay는 구조적으로 가능하다. 따라서 trusted time/freshness, revocation, durable nonce, replay 방지, external key/root/code authority, OS write deny, runtime noninterference, metrics, actual authority, production/full scan, P0 exit, action/mutation은 모두 false다. source/context credit도 `0/40·0/20`이다.

## 검증

- focused supervisor V2: `18/18 PASS`
- preauthorization V2 + supervisor 인접: `34/34 PASS`
- packet/Windows/preauthorization/supervisor 독립 red-team 묶음: `75/75 PASS`
- 전체 P0: `836/836 PASS`
- `py_compile`, `git diff --check`: `PASS`
- 중앙 Slang DB 1개와 publication journal 5개: byte/SHA `6/6` 불변

## 잔여 gate

lexical path 자체의 별도 길이 cap 부재와 self-hash 비인증성은 현재 component-only 범위의 비차단 잔여 위험이다. 외부 immutable owner key policy, trusted clock, rollback-protected revocation, crash/reboot-safe nonce ledger, external root/code pin, OS write deny와 격리 runtime witness, 실제 Windows end-to-end 및 actual semantic evidence가 생기기 전에는 P0, Pyserini/gold-lite/reranker/NIL A/B, production/full scan을 열지 않는다.
