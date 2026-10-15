# P0 Windows native observer v3 계약·bounded component 구현 및 재회의

## 결론

세 차례의 아키텍처·Windows/PKI·red-team 회의와 구현 후 반대검토를 거쳐 **`ADOPT_CONTRACT_AND_BOUNDED_DIAGNOSTIC_ONLY / POSITIVE_REJECTED`**를 채택했다. 기존 owner policy v2는 native observer receipt signing key, owner-state authority, trusted time·revocation·durable nonce와 IPC protocol을 권한화할 수 없으므로 positive 경로로 재사용하지 않는다.

이번 tranche는 다음 두 경계를 실제로 구현했다.

1. v1/v2 의미와 receipt SHA를 보존하는 owner policy v3 presented contract 및 native observer profile/transcript validator
2. network restore 없이 MSVC로 빌드되는 unsigned x64 service-shaped PE와 zero-argument read-only diagnostic PE

둘 다 component evidence일 뿐이다. 현 호스트는 service 미설치, WLDP lockdown off, UMCI 미강제이며 외부 owner key·TPM/KSP·Authenticode·active WDAC identity·trusted state plane이 없다. 따라서 actual selected source unit은 `0/40`, A sampling unit은 `0/20`, P0 Exit·production·full scan은 모두 `false`다.

| 항목 | 결과 |
| --- | --- |
| 채택 판정 | `ADOPT_CONTRACT_AND_BOUNDED_DIAGNOSTIC_ONLY` |
| native positive | `REJECTED / NO_GO` |
| owner policy v3 fixture receipt | `922eae35…98aa6` (구조 fixture, authority 아님) |
| blocker compiler | `FIXED_STORE / NO_GO`, receipt `104d7c58…a501` |
| native diagnostic | `BOUNDED_NATIVE_OBSERVER_CANDIDATE_NO_GO` |
| WLDP / UMCI | `0x80000000 (OFF) / false` |
| fixed service | `absent` |
| actual credit | `0/40 · 0/20` |
| P0·production·full scan | `false · false · false` |

## 전문가 회의와 채택 결정

### 구현 전 회의

- 아키텍처 회의는 operational owner key가 preauthorization domain 하나만 허용한다는 점을 확인했다. 이 키를 observer receipt에 재사용하면 서비스가 자기 실행 권한을 발급할 수 있으므로 bootstrap, operational preauthorization, observer TPM, owner-state 키를 분리했다.
- Windows/PKI 회의는 설치된 VS 2022 MSVC·Windows SDK로 `/MT` C++ PE를 offline 빌드할 수 있고 NativeAOT pack은 미캐시임을 확인했다. 1차 candidate는 C++로 채택하고 NativeAOT는 별도 lane으로 보류했다.
- red-team 회의는 v2 deployment projection에 service privilege/DACL, exact provider catalog membership, full loaded-code closure가 없고 fixed store와 host 관측이 하나의 interval이 아님을 확인했다. 현재 blocker compiler를 GO compiler로 확장하는 안은 기각했다.

### 구현 후 재회의

최종 red-team은 현 component에서 authority/P0 조기 승격 경로를 찾지 못했다. 다만 다음을 명시적 residual blocker로 유지했다.

- v3 profile의 self-consistent reseal은 presented 구조와 서명 수학만 통과할 수 있다. external bootstrap pin·provisioning·freshness를 증명하지 않으므로 모든 authority truth는 false다.
- 동일 transcript의 stateless 재검증은 가능하다. `single_use_replay_consumed=false`이며 positive adapter는 durable owner nonce ledger 없이 이를 사용할 수 없다.
- negative/failed evidence도 정확한 component transcript로는 검증될 수 있다. component validator 성공을 positive predicate로 해석해서는 안 된다.
- 기존 preflight는 v2를 exact 고정하므로 v3 store를 묵시 수용하지 않는다. 별도 v3 successor preflight가 필요하다.
- C++ service configuration 관측은 full owner projection이 아니라 read-only shape 후보다. 구현 후 필드명을 `service_shape_candidate_config_matches`로 낮춰 overclaim을 제거했다.

## 구현 내용

### owner policy v3

`src/llm_batch/grounding/p0_windows_owner_policy_contract.py`에 기존 branch와 분리된 exact v3를 추가했다.

- body/signature/anchor domain을 v1/v2와 분리
- v3 body는 기존 core body에 exact v2 `deployment_projection`과 `native_observer_profile`을 추가
- anchor가 deployment/profile artifact SHA를 모두 결속
- policy verifier SID, deployment service SID, profile service SID/name/SHA를 교차 결속
- bootstrap·operational·observer·owner-state key ID와 fingerprint 중복을 거부
- operational key allowed domain은 기존 external preauthorization 하나로 유지
- v1/v2 receipt SHA를 각각 `6cbf89be…c344`, `9e969eff…e7a6`으로 고정 회귀
- v3 contract receipt도 `future_authority_policy_version_eligible=false`, `positive_native_observer_policy_profile_complete=false`다. v3는 필요 조건이지만 positive 충분 조건이 아니다.

### native observer profile/transcript contract

`src/llm_batch/grounding/p0_windows_native_observer_profile_contract.py`는 exact profile, request, owner-state ticket, raw observation body, detached observer signature를 검증한다.

- canonical UTF-8 JSON+LF, duplicate/nonfinite/BOM/CR/unknown field·bool/int 혼동 거부
- observer key는 `Microsoft Platform Crypto Provider`, TPM attestation, non-exportable/hardware-backed 요구를 signed profile에 고정
- observer receipt domain과 owner-state ticket domain을 별도 고정
- P-256 SPKI fingerprint, Windows CNG SHA-256 signature math, canonical low-S를 검증
- challenge/request/ticket/receipt, policy/profile/deployment, key epoch, revocation/counter floor, bounded time-window 구조를 교차 결속
- service/token/image/resource/Authenticode/WDAC/provider/key/state evidence는 exact projection으로만 읽음
- live host, trusted time, revocation freshness, durable replay consumption, external pin/provisioning, runtime 비간섭과 모든 authority/action은 false

이 contract는 서명 수학을 확인하지만 owner가 독립 provision한 키인지, local clock이 신뢰되는지, ticket이 실제로 한 번만 소비됐는지는 확인하지 않는다.

### native C++ bounded candidate

`native/p0_windows_owner_observer/`에는 production-shaped service PE와 diagnostic PE를 분리했다.

- `llm-novel-dc-owner-verifier.exe`: SCM service entry만 가지며 빌드·테스트에서 실행·설치·시작하지 않음
- `p0_windows_owner_observer_diagnostic.exe`: zero-argument read-only diagnostic; serialized JSON은 unsigned이며 authority token이 아님
- held self/service image의 volume GUID path·volume serial·128-bit file ID·SHA와 pre/post identity를 관측
- service PE의 exact-one resource type/name/language/bytes SHA를 diagnostic이 fixed sibling에서 관측
- current token, fixed service read-only state/PID/shape, loaded bcrypt module disk identity, WLDP coarse state를 관측
- Authenticode/catalog, exact active WDAC PolicyID/hash, loaded mapping closure, NCrypt receipt signing, trusted time/revocation/nonce는 구현하지 않고 blocker로 반환

Release build는 `/MT`, `/guard:cf`, `/guard:ehcont`, `/CETCOMPAT`, ASLR/NX/high-entropy, `/Brepro`를 사용한다. diagnostic smoke는 CLR·dynamic CRT·network·SCM-write import 부재와 COM descriptor 0을 확인한다.

## 검증 결과

| 검증 | 결과 |
| --- | --- |
| profile + v3 policy + 인접 focused | `77/77 PASS` |
| 전체 `test_p0*.py` | `552/552 PASS` (`41.251s`, 최종 코드) |
| 관련 Python `py_compile` | `PASS` |
| native clean `/Brepro` 2회 | service/diagnostic SHA 각각 동일 |
| service PE SHA | `878e1f52…5f4db` |
| diagnostic PE SHA | `0c24d984…08a0` |
| embedded resource SHA | `d0107685…b1694` |
| native PE/import/current-host smoke | `PASS / explicit NO_GO` |
| 중앙 Slang DB + publication journal | `6/6` path·length·SHA 전후 불변 |
| blocker compiler 2회 | receipt `104d7c58…a501` 동일 |

이 검증은 component unittest, offline native build/smoke, 두 point-in-time endpoint projection이다. regression-safe grounding actual run이 아니므로 dashboard와 actual `--parallel 16` manifest 대상이 아니다. transient write absence, continuous watch, runtime noninterference는 증명하지 않는다.

## positive 전 잔여 blocker

1. v3-only successor preflight와 negative transcript를 hard reject하는 별도 positive predicate
2. owner-signed run/session/host/boot/source-plan/sampling/parser/output-root lease 결속
3. externally provisioned Authenticode binary, exact SCM service DACL/required privileges/token, PID+creation-time pre/post 결속
4. enforced UMCI와 exact active WDAC base/supplemental policy identity·hash·member authorization
5. loaded mapping에서 held disk/catalog file ID·SHA·member tag·selected signer SPKI까지의 full executable closure
6. non-exportable TPM/NCrypt observer key attestation, trusted time/revocation high-watermark, crash/reboot rollback-resistant nonce consume
7. fixed store·SCM·process·image·resource·WDAC·provider/catalog·nonce를 하나의 held/watch interval로 결속
8. six-category protected root owner pin/watch, process-wide write deny, actual parser/capture와 per-unit signed 40+20 evidence

위 항목 전에는 `39/40`, `19/20`, duplicate/recheck inflation, synthetic/self-hash evidence를 모두 credit 0으로 처리한다. 모든 gate가 닫힌 뒤에만 dashboard ON·`--parallel 16` actual 40+20을 시작하고 post-run credit compiler를 별도 재회의한다. P0 Exit 뒤에만 Pyserini/gold-lite/retrieval/reranker/NIL shadow를 시작한다.

## 공식 API 근거

- [WinVerifyTrust](https://learn.microsoft.com/en-us/windows/win32/api/wintrust/nf-wintrust-winverifytrust): return 0만 성공으로 취급하며, 성공 자체가 owner authority는 아니다.
- [CertGetCertificateChain](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-certgetcertificatechain): chain/revocation 평가는 trusted time과 rollback-resistant freshness plane을 별도로 요구한다.
- [CryptCATAdminCalcHashFromFileHandle2](https://learn.microsoft.com/en-us/windows/win32/api/mscat/nf-mscat-cryptcatadmincalchashfromfilehandle2), [CryptCATAdminEnumCatalogFromHash](https://learn.microsoft.com/en-us/windows/win32/api/mscat/nf-mscat-cryptcatadminenumcatalogfromhash): held file digest와 exact catalog membership을 닫는 후속 native 경계다.
- [CiTool commands](https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/operations/citool-commands): exact active/deployed policy inventory는 coarse WLDP state와 별도다.
- [SERVICE_STATUS_PROCESS](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_status_process), [SID attributes in an access token](https://learn.microsoft.com/en-us/windows/win32/secauthz/sid-attributes-in-an-access-token): service PID·creation/token SID interval 결속의 후속 기준이다.
