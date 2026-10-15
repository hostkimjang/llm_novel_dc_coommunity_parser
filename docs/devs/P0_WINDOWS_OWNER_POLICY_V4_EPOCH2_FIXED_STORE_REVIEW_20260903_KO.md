# P0 Windows owner policy V4 epoch2 고정 저장소 검토

## 판정

최종 판정은 `PASS_WITH_LIMITATIONS / ADOPT_COMPONENT_ONLY / NO_GO_EXTERNAL_AUTHORITY`다. packet-V2용 V4 policy를 zero-input으로 찾을 수 있는 별도 epoch2 고정 경로와 all-handle-before-read 관찰기를 추가했지만, 현재 호스트에는 그 저장소가 없고 외부 owner 권위도 없다.

- store component manifest SHA: `6bfe0e80c26c707db3e0634700ad9d60574670179b33b610a10695e186ca0697`
- parent component manifest SHA: `36eec436b81138357b87d5368029754ac846c901db75e640a0889adaadc209e8`
- focused unittest: `19/19 PASS`, 공격 subtest `14 PASS`
- 인접 5-module: `104/104 PASS`
- 전체 P0: `942/942 PASS`
- current zero-input: `FIXED_STORE / NO_GO`, 91 fields, deterministic receipt `06474b801d115e97be20ce7e845a57145ba9cd95130b2b1ea7d08fa5c9a5eecd`
- actual source claim/A-context credit: `0/40`, `0/20`

구현은 [`p0_windows_owner_policy_v4_epoch2_fixed_store.py`](../../src/llm_batch/grounding/p0_windows_owner_policy_v4_epoch2_fixed_store.py), 부모 replay는 [`p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator.py`](../../src/llm_batch/grounding/p0_windows_owner_policy_v4_epoch2_fixed_store_parent_validator.py), 공격 회귀는 [`test_p0_windows_owner_policy_v4_epoch2_fixed_store.py`](../../tests/test_p0_windows_owner_policy_v4_epoch2_fixed_store.py)에 있다.

## 채택 범위

공개 API는 인자를 받지 않고 `ProgramData` 아래 고정 suffix `llm-novel-dc/p0-owner-policy-v4-packet-v2`와 epoch `00000000000000000002`만 관찰한다. predecessor V3 body/signature, packet-V2 pin, V4 body/signature, bootstrap SPKI의 6개 raw member를 먼저 모두 handle로 고정한 뒤 exact inventory, volume/file identity, reparse·hardlink·ADS·case-sensitive directory, binary ACL의 전후 안정성, directory-change interval과 reopen 안정성을 검사한다. 쓰기·network·subprocess·환경 selector·wall clock은 사용하지 않는다.

부모는 V4 producer를 import하지 않고 raw 6개에서 V4 exact 78-field schema와 type, operational effect `NONE_SHADOW_ONLY`, signature-input hash, canonical P-256 SPKI, low-S P1363 ECDSA 수학을 재검증한다. predecessor V3 경로는 기존 structural validator를 정확히 한 번 재실행하며 관련 검증 그래프의 함수·상수·정규식·호출 대상을 입·출구에서 고정한다. 이는 외부 권위가 아니라 bounded structural replay다.

## 반대검토에서 닫은 결함

초기 구현은 V4 validator의 in-place `__code__` 변조, semantic constant drift, mutable failure helper, 부모의 effect/hash/bool-int 혼동과 forged P1363 서명을 허용했다. 수정 뒤에도 base64 encode/decode 공조 변조, malformed V3 ACL에 대한 hardcoded receipt, V3 `frozenset`·정규식 drift, `uuid.UUID` 대체가 차례로 재현됐다.

최종판은 V4 public validator와 사용 helper graph, store/parent semantic constants, base64/binascii 속성, V3 4-module 함수·상수·정규식과 참조 호출 graph를 봉인하고 각 반례를 회귀 테스트로 남겼다. 재심 결과 잔여 high/material finding은 0이다. Python 내부 봉인은 OS가 보장하는 code authority가 아니므로 해당 truth는 계속 false다.

## 남은 blocker와 다음 순서

별도 epoch2 저장소는 live legacy V3 고정 저장소와 같은 관찰 구간의 연속성을 증명하지 않는다. 따라서 `LIVE_V3_FIXED_STORE_PREDECESSOR_CONTINUITY_NOT_VERIFIED`와 `PREDECESSOR_BOOTSTRAP_SIGNATURE_MATHEMATICS_NOT_VERIFIED`를 유지한다. ACL은 전후 안정성만 관찰하며 owner 정책, effective write deny 또는 외부 root/code authority가 아니다.

외부 operator가 정확한 V4 저장소와 독립 key/pin, trusted time·revocation·durable nonce, root/code authority, OS write deny와 signed runtime witness를 provision하고 live V3 continuity 또는 그에 상응하는 predecessor 증거를 별도로 닫아야 한다. 그 뒤 승인된 raw root에 seed 8개의 실제 bytes·rights/retention 증거를 수집한다. 그 전에는 actual `40+20`, Pyserini BM25, gold-lite, reranker/NIL A/B, production/full scan을 열지 않는다.
