# P0 Windows owner deployment projection v2 구현·재회의

## 결론

외부 owner가 서명할 정책에 native verifier 배포 의미를 포함하는 `deployment projection v2` 계약을 구현했다. 판정은 `OWNER_DEPLOYMENT_PROJECTION_V2_CONTRACT_PASS_HOST_AND_EXTERNAL_PROVISIONING_NO_GO`다. v2는 고정 Windows service, PE image·내장 bootstrap resource, Authenticode chain pin, WDAC/UMCI, 실제 로드 대상 CNG provider identity를 정책 body·owner anchor·detached signature bytes에 결속한다. 다만 지금 확인한 것은 presented material의 구조와 Windows CNG 서명 transcript뿐이며, 서비스 설치나 live host trust를 증명하지 않는다.

v1 body·signature·receipt 의미는 그대로 보존한다. 향후 authority 후보만 별도 body/signature/owner-anchor domain과 `p0_windows_owner_policy_contract_receipt_v2`를 요구한다. v1은 component validator에서 계속 읽을 수 있지만 authority version으로는 부적격이다.

## 전문가 회의와 채택 결정

owner provisioning, actual data readiness, Windows binary ACL, 독립 공격 감사 분과를 병렬로 진행하고 구현 뒤 다시 반대검토했다.

| 의견 | 최종 결정 | 반영 |
| --- | --- | --- |
| 현재 v1 genesis를 먼저 실제 key로 서명 | `REJECT` | trusted verifier·service·WDAC·provider가 서명 범위에 없어 재서명 의식이 필요하므로 v2 projection을 먼저 고정 |
| v1을 수정해 deployment field 추가 | `REJECT` | v1 exact field·domain·receipt 호환성을 보존하고 v2 body/signature/anchor/receipt를 분리 |
| native service·image·bootstrap resource·WDAC·provider를 owner policy에 결속 | `ADOPT_CONTRACT_ONLY` | exact projection schema와 self-hash, v2 owner anchor 및 body-byte signature cross-binding 구현 |
| service name과 임의 형식상 service SID를 별도 수락 | `REJECT` | `sc.exe showsid llm-novel-dc-p0-owner-verifier-v2`의 결정적 SID를 상수로 고정 |
| policy ACL verifier와 deployment service SID를 별도 principal로 허용 | `REJECT_AFTER_REPRODUCTION` | 최초 초안의 split을 두 독립 감사가 재현했고 v2 body `verifier_sid`, 8-role verifier ACE, projection `service_sid` exact equality로 수정 |
| self-consistent projection을 authority로 인정 | `REJECT` | self-hash·owner anchor를 모두 다시 계산할 수 있는 공격도 구조 PASS만 가능하고 authority·actual·production은 false |
| 다음에 actual readiness compiler부터 구현 | `DEFER_AFTER_PREFLIGHT` | `zero-input host preflight → blocker-only readiness compiler → externally provisioned positive → actual 40+20` 순서 채택 |

최종 재회의는 SID split 수정 뒤 `ADOPT_CONTRACT_ONLY`로 전환했다. 이 범위에 남은 reportable 구조 결함은 없지만 live authority gate는 열리지 않았다.

## 구현 계약

`p0_windows_owner_deployment_projection.py`는 다음을 exact owner-signed material로 요구한다.

- verifier kind `NATIVE_FIXED_PE_SERVICE`, 고정 service name과 그 결정적 service SID, LocalSystem start-account SID
- volume-GUID 고정 Program Files PE 경로, volume serial, 128-bit file ID, image SHA-256
- PE 내부 bootstrap-key resource SHA-256
- embedded Authenticode policy와 signer leaf/root SPKI pin
- non-nil·서로 다른 WDAC policy/base-policy UUID, policy SHA-256, `user_mode_code_integrity_required=true`
- ordered `bcrypt.dll`, `bcryptprimitives.dll` provider row의 loaded System32 volume-GUID path, volume/file identity, image SHA-256, Microsoft catalog policy와 signer SPKI pin

`p0_windows_owner_policy_contract.py`의 v2는 별도 body/signature/domain/owner-anchor를 사용한다. projection artifact SHA가 owner anchor에 들어가고 완성된 body raw SHA가 detached signature transcript에 들어간다. v2 `verifier_sid`는 projection의 fixed service SID와 같아야 하며, 기존 exact ACL validator 때문에 8개 role의 verifier ACE도 같은 SID여야 한다.

v1 receipt는 신규 v2 field를 추가하지 않는다. v2만 별도 receipt schema로 policy/signature domain, projection SHA, SID cross-binding, future-authority schema eligibility를 낸다. 이 eligibility는 권한 승인이 아니다.

## 반례와 수정

회귀는 다음 공격을 포함한다.

- v1 body에 projection을 붙이는 downgrade, v2에서 projection 제거, v1/v2 signature domain cross-pair
- projection field·provider field 추가, self-hash 불일치, projection 변경 뒤 owner anchor 미갱신
- service name/SID/start account, verifier image fixed path·volume/file identity 대체
- policy ACL verifier account SID와 deployment service SID 분리
- WDAC UMCI off, nil/동일 policy UUID, verifier embedded signature와 provider catalog signature 혼동
- provider 순서·이름·System32 path·file identity·SPKI·signature type 대체
- uppercase/noncanonical hash·file ID, nil volume GUID, unsafe path
- 모든 공개 hash·anchor·envelope를 다시 계산한 self-consistent attacker material
- v2 exact transcript의 실제 Windows CNG positive와 authority false truth table

## 현재 호스트 관측

읽기 전용 감사에서 현재 token은 medium integrity이고 Administrators는 deny-only다. `C:\ProgramData\llm-novel-dc\p0-owner-policy-v1`과 외부 owner native verifier/service/key는 없다. `C:\ProgramData`에는 일반 사용자 write 선점 가능성이 있다. Device Guard는 kernel CI 관측만 있고 UMCI는 꺼져 있다. TPM 2.0은 존재하지만 attestation-ready가 아니며 IFX ROCA 취약 상태다. `bcrypt.dll`과 `bcryptprimitives.dll`의 Microsoft catalog signature는 유효하게 관측됐지만 이것만으로 owner-approved provider provenance가 되지 않는다.

따라서 이 회차는 OS 상태를 만들거나 서비스를 설치하지 않았다. `loaded_final_volume_guid_path`라는 필드명도 실제 loaded-module 증거가 아니다.

## 검증

- deployment v2 + owner-policy focused: `34/34 PASS`
- bootstrap + fixed-store 인접 포함: `56/56 PASS`
- 전체 `test_p0*.py`: `509/509 PASS`
- 변경 Python compile·scoped `git diff --check`: PASS
- 중앙 Slang DB 1개와 publication journal 5개: `6/6` byte·SHA 불변
- noninterference receipt: `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`
- `sc.exe showsid` 결과와 고정 service SID: exact 일치

이번 검증은 component unittest와 read-only host audit이다. actual dataset run이 아니므로 dashboard·`--parallel 16` manifest 대상이 아니다. actual source claim과 사람 A-context credited count는 `0/40`, `0/20`; `p0_phase_exit=false`, `production_approval=false`, `full_scan_approval=false`다.

## 다음 gate

다음 단일 tranche는 공개 인자가 없는 `zero-input Windows host preflight candidate`다. 반드시 다음을 fail-close해야 한다.

1. future authority consumer가 v1 및 v2 eligibility false receipt를 hard reject한다.
2. fixed SCM service name·`ServiceSidType`, LocalSystem account, 실행 process token의 exact service SID를 같은 관찰에 결속한다.
3. service command line이 가리키는 실행 image를 held handle로 열어 final path·volume serial·file ID·SHA와 projection을 비교한다.
4. embedded bootstrap resource, verifier embedded Authenticode chain과 active WDAC policy/base/hash·UMCI를 검증한다.
5. verifier process의 실제 loaded-module handle에서 두 CNG DLL의 identity를 얻고 disk object와 exact 비교한다.
6. provider catalog signer뿐 아니라 대상 DLL digest membership, selected chain/SPKI와 trusted-time revocation을 검증한다.
7. signed observer receipt는 observer identity·nonce·policy/projection digest에 결속하고 공개 self-hash receipt를 authority로 재사용하지 않는다.

현 호스트 preflight의 기대 결과는 deterministic NO-GO다. 외부 owner가 signed v2 genesis, native service, Authenticode/WDAC, exact fixed store를 provision하기 전에는 actual readiness compiler도 blocker-only여야 한다. 그 뒤에만 dashboard ON·`--parallel 16`으로 실제 40+20을 실행한다. Pyserini BM25, gold-lite, reranker/NIL shadow A/B는 P0 Exit 뒤로 유지한다.

## 2026-09-02 successor addendum

후속 zero-input preflight의 fixed store→v2 downgrade/receipt 방어→SCM exact config→held image identity candidate까지 구현했다. 현재 호스트는 fixed store 부재에서 structured `NO_GO`이며, 위 계획 2~6의 process token/resource/Authenticode/active WDAC·UMCI/loaded provider/catalog/time·revocation과 7의 signed native observer는 아직 미완료다. 상세와 최신 수치는 [`P0_WINDOWS_OWNER_PROVISIONING_PREFLIGHT_CANDIDATE_REVIEW_20260902_KO.md`](P0_WINDOWS_OWNER_PROVISIONING_PREFLIGHT_CANDIDATE_REVIEW_20260902_KO.md)를 따른다.

2026-09-03에는 그 다음 단계인 [actual readiness blocker compiler](P0_ACTUAL_READINESS_BLOCKER_COMPILER_REVIEW_20260903_KO.md)도 구현했다. 이 compiler는 외부 provisioning 전 blocker를 정리할 뿐 항상 `NO_GO`이며, actual selected source unit/A sampling unit credited `0/40·0/20`을 유지한다. focused `22/22`, 전체 P0 `531/531`이다.
