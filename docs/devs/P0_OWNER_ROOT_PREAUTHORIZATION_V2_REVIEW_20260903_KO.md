# P0 owner root preauthorization V2 구현·전문가 재회의

작성일: 2026-09-03 KST
판정: `ADOPT_COMPONENT_ONLY / NO_GO_AUTHORITY / OPERATIONAL_NO_GO`

## 결론

packet V2 Windows reader 앞에 caller-presented owner 서명 수학과 signed root/member commitment를 검증하는 별도 preauthorization V2를 추가했다. 공개 API는 raw public-key pin, preauthorization, detached signature envelope, caller-presented `observed_at`과 packet directory만 받는다. private key, verifier callback, serialized receipt, caller가 주는 expected component/root pin은 받지 않는다.

최종 component manifest SHA는 `07ae0af427112978ba3cb5f5a0ae8713a25837cbb9ae65ac0b7993da7d44876e`다. test에서 이 값을 재계산할 뿐 아니라 literal로도 고정했다. Windows V2 `4e4e5c76…aae02`, packet V2 `2a4b6351…d59f`, fixed member contract `37f3a34a…385fc`를 dependency pin으로 사용한다.

## 채택한 검증

- canonical UTF-8 JSON, sorted exact form, 단일 LF, byte cap을 파일 시스템 호출 전에 검증한다.
- RFC 5480 P-256 SPKI fingerprint를 X/Y 32-byte에서 재계산한다.
- detached signature는 Windows CNG P-256/SHA-256, exact 64-byte P1363 `r||s`, low-S로 검증한다.
- pin/body/envelope의 raw byte SHA, artifact SHA, owner anchor, key ID/epoch, context를 교차 결속한다.
- ordered 16-member의 ordinal/role/path/media type/cap/raw SHA와 signed root의 volume-GUID final path, ASCII serial, 128-bit file ID를 서명 material에 포함한다.
- 서명 preflight가 모두 끝난 뒤 Windows V2 direct validator를 정확히 1회 호출하고, directory receipt와 safe projection의 exact schema/type/order/self-hash/truth table을 다시 검증한다.
- 전체 nested Windows receipt는 반환하지 않고 고정 hash projection만 공개한다.

## 회의에서 발견해 수정한 결함

암호학 반대검토는 body의 `packet_manifest_raw_sha256`와 ordered member 0의 raw SHA가 분리될 수 있는 split-view를 재현했다. 둘의 exact equality를 CNG·Windows 호출 전에 강제하고 negative call-count test를 추가했다.

Windows receipt가 manifest 내부 `packet_id`와 artifact SHA를 직접 노출하지 않으므로 출력은 `signed_packet_id`, `signed_packet_manifest_artifact_sha256`로 이름을 제한했다. 실제 manifest bytes와 교차 검증된 것은 `verified_packet_manifest_raw_sha256`뿐이며, `packet_id_cross_verified`와 `packet_manifest_artifact_cross_verified`는 false다.

사전 권고 명칭과 실제 wire 명칭의 차이도 재검토했다. normative 조건은 V1과 분리된 고유 V2 schema/domain이며 현재 계약이 이를 충족하므로 현재 wire contract를 ratify했다.

## 진실 경계

true로 허용하는 것은 canonical/서명 수학, caller-presented raw 결속, signed root/member commitment, Windows validator 1회 호출과 반환 receipt의 구조 검증뿐이다. 같은 bundle은 두 번 성공할 수 있고, 완전한 attacker key+bundle 교체도 수학적으로 일관되면 통과할 수 있다.

따라서 external key provisioning, independent owner identity, private-key custody, trusted time/freshness, revocation, durable nonce/replay, external root/code authority, monkeypatch resistance, OS write deny, runtime noninterference, 모든 metric permission, actual authority, production/full scan, P0 exit와 action은 모두 false다. 실제 source/context credit도 `0/40·0/20`이다.

## 검증

- focused: `16/16 PASS`
- 독립 red-team 인접 묶음: `79/79 PASS`
- 최종 전체 P0: `817/817 PASS`
- `py_compile PASS`
- 실제 Windows CNG P-256/P1363 smoke: `PASS`
- V1 fixed 14-member SHA/schema/domain과 runtime import: 불변
- 중앙 Slang DB 1개와 publication journal 5개: byte/SHA `6/6` 불변

## 다음 gate

Supervisor V2는 이 raw3 API를 정확히 1회 호출하고 반환 receipt를 독립 재검증하는 memory-only wrapper로만 진행한다. 외부 immutable key policy, trusted clock, rollback-protected revocation, crash/reboot-safe nonce ledger, external root/code pin, OS write deny, 격리 runtime witness와 실제 Windows end-to-end 증거가 생기기 전에는 authority·P0·production/full scan을 열지 않는다.
