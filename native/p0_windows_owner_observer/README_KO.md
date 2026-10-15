# P0 Windows owner observer bounded candidate

## 판정

이 디렉터리는 Windows native observer의 **unsigned·read-only component candidate**다. 현재 판정은 다음과 같다.

```text
gate = BOUNDED_NATIVE_OBSERVER_CANDIDATE_NO_GO
decision = NO_GO
candidate_only = true
actual source credit = 0/40
actual A-context credit = 0/20
owner/P0/production/full scan = false
```

이 candidate는 owner authority나 actual 실행 권한을 발급하지 않는다. 서비스 설치·시작, SCM 구성 변경, WDAC 정책 변경, 네트워크 접근, NuGet/NativeAOT restore를 수행하지 않는다.

## 바이너리 분리

- `llm-novel-dc-owner-verifier.exe`: SCM 전용 production-shaped service binary다. console/diagnostic fallback이 없으며, SCM이 외부에서 시작하지 않으면 실행하지 않는다. 현재 unsigned candidate라서 정상 service context에서도 항상 `NO_GO`로 종료한다.
- `p0_windows_owner_observer_diagnostic.exe`: zero-argument read-only diagnostic binary다. JSON diagnostic projection만 stdout으로 반환하며, 인자가 하나라도 추가되면 거부한다. serialized JSON은 서명 receipt나 authority token이 아니다.
- `p0_owner_observer_core.lib`: 두 실행 파일에 정적으로 링크하는 공통 bounded observation 코드다. 별도 project DLL을 만들지 않는다.

custom resource `P0_OWNER_BOOTSTRAP_V2 / OWNER_POLICY_P256_SPKI / LANGID 0`는 service PE에만 exact-one으로 들어간다. diagnostic은 fixed sibling service PE를 `LOAD_LIBRARY_AS_DATAFILE_EXCLUSIVE | LOAD_LIBRARY_AS_IMAGE_RESOURCE`로 열어 resource를 관측하며 production resource를 자체 image에 복제하지 않는다. marker bytes는 실제 owner public key가 아니며, hash 성공을 external key 검증으로 승격하지 않는다.

## 현재 관측 범위

diagnostic은 다음 read-only candidate evidence를 수집한다.

1. 현재 process primary token의 user SID, system integrity 여부, deterministic service SID의 enabled/restricted 존재 여부, linked token 부재
2. 현재 diagnostic과 fixed sibling service PE를 non-inheritable held handle로 열어 volume-GUID final path, volume serial, 128-bit file ID, reparse/link 상태, pre/post identity, SHA-256
3. service PE custom resource의 string type/name, 전체 name/language count, neutral language, bytes SHA-256
4. `Microsoft Primitive Provider` CNG 호출 후 exact System32 경로의 loaded `bcrypt.dll`, `bcryptprimitives.dll`을 확인하고 재개방한 disk object identity/SHA-256
5. `WldpGetLockdownPolicy`와 `WldpQueryWindowsLockdownMode`의 coarse UMCI/lockdown 상태
6. fixed service의 존재·상태·PID와 read-only SCM configuration candidate
7. QPC 시작/종료와 현재 process creation time 안정성

다음은 의도적으로 항상 false다.

- loaded mapping과 재개방 disk object의 authoritative cross-binding
- 전체 loaded executable code closure
- active WDAC PolicyID/BasePolicyID/hash identity
- Authenticode/catalog chain 및 SPKI pin
- external owner key와 signed observer receipt
- trusted time·revocation freshness·rollback-resistant durable nonce
- single-interval fixed store/host/watch 결속과 unnamed-stream exactness
- owner/actual/P0/production/full-scan authority

WLDP의 UMCI flag가 true여도 exact active WDAC policy identity는 증명되지 않으므로 positive gate를 열지 않는다. System32 disk DLL hash도 target service의 mapped-image identity나 catalog membership 증거가 아니다.

## 빌드와 검증

Visual Studio Installer가 보고한 설치 경로와 VS-bundled CMake를 사용한다. download, package restore, PATH fallback은 없다.

```powershell
& .\native\p0_windows_owner_observer\build.ps1 -Configuration Release -Clean
& .\native\p0_windows_owner_observer\test.ps1 -Configuration Release -SkipBuild
```

빌드 요청 병렬도는 `16`이다. 이는 regression-safe grounding actual run이 아니라 native component build/smoke이므로 dashboard나 actual manifest 대상이 아니다.

Release PE는 `/MT`, `/GS`, `/sdl`, `/guard:cf`, `/guard:ehcont`, `/CETCOMPAT`, `/DYNAMICBASE`, `/NXCOMPAT`, `/HIGHENTROPYVA`, `/LARGEADDRESSAWARE`, `/DEPENDENTLOADFLAG:0x800`, `/Brepro`를 사용한다. smoke는 다음을 fail-close로 검사한다.

- AMD64 PE
- ASLR, DEP, high-entropy VA, CFG, CET, EH continuation table
- COM/CLR descriptor 0
- exact dynamic dependency set `ADVAPI32.dll`, `bcrypt.dll`, `KERNEL32.dll`
- `mscoree`, CoreCLR/hostfxr/hostpolicy, dynamic CRT, WinHTTP/WinINet/URLMon/Winsock 부재
- `CreateServiceW`, `ChangeServiceConfig*`, `DeleteService`, `ControlService` import 부재
- diagnostic unexpected argument 거부
- all-false authority truth table와 required blocker 존재

`test.ps1`은 service PE를 실행하지 않는다.

## 외부 gate

positive native observer는 이 diagnostic schema를 확장하지 않고 별도 version으로 구현해야 한다. 최소 외부 입력은 다음과 같다.

1. owner-signed policy/projection과 실제 Authenticode signing key/certificate
2. externally installed fixed service와 enforced WDAC/UMCI policy activation evidence
3. non-exportable NCrypt attestation key와 owner-pinned SPKI/key epoch
4. trusted-time token, signed revocation snapshot/high-watermark, rollback-resistant nonce broker
5. exact catalog member/tag, full loaded-code closure, store/host/watch single interval

이 항목이 모두 외부 owner 권한 경계에서 충족되고 새 positive readiness gate가 공격 검증을 통과하기 전에는 actual 40+20, P0 Exit, Pyserini/gold-lite/retrieval/reranker/NIL shadow를 시작하지 않는다.
