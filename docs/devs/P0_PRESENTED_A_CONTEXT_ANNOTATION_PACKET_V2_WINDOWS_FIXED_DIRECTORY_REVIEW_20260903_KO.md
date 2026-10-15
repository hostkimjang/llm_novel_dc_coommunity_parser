# P0 annotation packet V2 Windows fixed-directory 구현·재회의

작성일: 2026-09-03 KST
판정: `ADOPT_BOUNDED_WINDOWS_V2 / COMPONENT_ONLY / OPERATIONAL_NO_GO`

## 결론

packet V2의 고정 16-member를 Windows 직접 handle로 관측하는 additive reader를 구현했다. 기존 Windows V1, preauthorization V1, supervisor와 runtime은 수정하거나 import하지 않았다. memory mode와 Windows directory mode를 분리하고, 성공 receipt도 로컬 byte/handle 일치 범위 밖의 신뢰를 열지 않는다.

최종 Windows component manifest SHA는 `4e4e5c76fd3fd210a5e3c381243dccec623f2c0a48afbba6e52667d38afaae02`, member caps SHA는 `07ab1bf2f6bd3bf85eb03d135fe92323e857122c5e363bd5e6751923fbd2ebfe`다.

## 채택한 관측 경계

- ancestor, root와 16개 member handle을 share-read-only로 모두 연 뒤 첫 read를 시작한다.
- reparse, case-sensitive directory, hardlink, ADS, cross-volume/path/file-ID 불일치, missing/extra/case collision을 fail-close한다.
- per-role cap과 aggregate cap을 첫 read 전에 검사하고, validators 전체를 held-handle `ExitStack` 안에서 실행한다.
- read 뒤 snapshot, reopen identity와 inventory를 다시 비교한다.
- root/ancestor/member before-after-reopen evidence, member sequence, total bytes와 cap을 safe projection에 hash로 결속한다.
- packet parent 1회와 별도 target-parent replay 1회를 구분한다. target parent total 2회를 정확히 기록하고 single-execution을 주장하지 않는다.
- memory mode의 filesystem/trust 주장은 모두 false다. direct mode도 `handles_held_across_packet_validation`과 local byte consistency만 true다.
- external root/manifest/code/owner/authenticity/write-deny/runtime/preauth/supervisor/time/revocation/authority/metrics/production/full scan/P0/action은 모두 false다.

## 재회의와 red-team

독립 검토는 outer receipt와 safe projection 사이의 root/member/cap/pin-set 결속, 99-field packet parent receipt의 exact type/order/value, target parent declared/full SHA 재봉인, Unicode volume serial, bool/int/subclass와 evidence 변조를 공격했다. 수정 뒤 해당 PoC는 모두 거부됐다.

같은 프로세스에서 exported mutable `COMPONENT_MANIFEST`를 monkeypatch하는 공격은 독립 code authority가 없으므로 구조적으로 막았다고 주장하지 않는다. `same_process_monkeypatch_resistance_verified=false`인 현재 bounded 계약에서는 component 채택 blocker가 아니지만 실제 authority blocker다.

## 검증

- focused Windows V2: `26/26 PASS`
- packet V2 및 Windows V1 인접: `59/59 PASS`
- 최종 전체 P0 재검증: `817/817 PASS`
- `py_compile PASS`
- 중앙 Slang DB 1개와 publication journal 5개: byte/SHA `6/6` 불변

## 다음 gate

owner preauthorization V2는 이 component SHA와 fixed 16-member 계약을 서명 본문에 고정하되, caller-presented key·clock·nonce·root를 외부 권한으로 승격하지 않는다. 실제 Windows positive path와 외부 key/root/code provisioning, trusted time/revocation, crash-durable replay 방지, OS write deny 전에는 운영 승인을 열지 않는다.
