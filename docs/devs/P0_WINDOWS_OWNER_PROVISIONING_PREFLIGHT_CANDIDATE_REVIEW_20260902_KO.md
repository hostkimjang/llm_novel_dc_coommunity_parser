# P0 Windows owner provisioning preflight candidate 구현·재회의

## 결론

zero-input Windows host preflight의 첫 tranche를 구현했다. 공개 함수는 인자를 받지 않고 fixed ProgramData store를 먼저 검증한 뒤, 유효한 v2 정책일 때만 SCM의 고정 서비스 설정과 held verifier image identity를 읽는다. 현재 호스트에는 fixed store와 서비스가 없으므로 결과는 deterministic `NO_GO`다.

이번 결과는 `candidate_only`다. Python monkeypatch, store와 host 관측 사이의 비원자 구간, service process token, PE resource 실제 선택, Authenticode, active WDAC/UMCI, loaded CNG provider, trusted time·revocation, signed native observer가 닫히지 않았다. owner authority, actual, P0 Exit, production, full scan은 모두 false다.

```text
gate = WINDOWS_OWNER_PROVISIONING_PREFLIGHT_CANDIDATE_EXECUTED_HOST_AND_EXTERNAL_PROVISIONING_NO_GO
actual/credited source claims = 0/40
actual/credited A-context reviews = 0/20
p0_phase_exit = false
production_approval = false
full_scan_approval = false
```

## 전문가 회의와 채택 의견

세 분과를 병렬로 운영한 뒤 구현 전·후 채택 회의를 했다.

1. 계약·Windows 설계 분과는 기존 projection이 `ServiceSidType`, service type/start type/error control, raw `ImagePath` 문법, bootstrap resource selector를 owner-sign하지 않는다고 지적했다. external provisioning 전 v2 projection을 강화하고, fixed-store 공개 receipt에는 body를 노출하지 않는 private same-call handoff를 채택했다.
2. Windows host 감사 분과는 fixed store·고정 서비스·예상 PE 부재, UMCI off, medium-integrity/Administrators deny-only token을 확인했다. 디스크의 `bcrypt.dll`과 `bcryptprimitives.dll`은 Microsoft catalog-valid였지만 실행 verifier가 없으므로 loaded-provider 증거로 채택하지 않았다.
3. red-team 분과는 v1 downgrade, forged/resealed child receipt, service shared-process·wrong SID type·추가 argv, image identity 교체, generic WinVerifyTrust 성공을 authority로 올리는 공격을 제시했다. v1은 SCM 전에 거부하고 all-green Python mock도 authority를 열지 않는 규칙을 채택했다.

구현 후 독립 감사에서 세 결함을 추가로 발견했다. bootstrap resource language/count가 Python `False/True`로 통과하는 bool/int 혼동, outer/contract/bootstrap receipt의 불완전한 truth-table·raw/body 교차검증, invalid outer receipt에서도 fixed-store observation이 true로 남는 모순을 재현해 모두 수정했다. 최신 감사에서 P0/P1 잔여 finding은 없다.

서비스 계약은 요청형 검증기라는 현재 설계에 맞춰 `SERVICE_WIN32_OWN_PROCESS`, `SERVICE_DEMAND_START`, `SERVICE_ERROR_NORMAL`, `SERVICE_SID_TYPE_RESTRICTED`, exact quoted image path/no arguments로 확정했다. bootstrap resource는 고정 type/name/language와 exact-one을 owner-signed projection에 넣었다. Microsoft 문서상 restricted service SID는 서비스 SID를 token의 일반·제한 SID 목록에 넣으므로, 향후 실제 service token과 8-role ACL을 함께 검증해야 한다. `QueryServiceConfig2W`의 `SERVICE_CONFIG_SERVICE_SID_INFO`는 이 설정을 조회하는 계약이다. 근거는 [SERVICE_SID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_sid_info)와 [MS-SCMR SERVICE_SID_INFO](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-scmr/ea1a9acd-4bb2-473f-ae5b-55969c5960fc)다.

## 구현 범위와 명시적 비범위

### projection 강화

`p0_windows_owner_deployment_projection.py`에 다음 exact owner-signed material을 추가했다.

- service type/start type/error control/SID type
- raw binary path 정책 `EXACT_QUOTED_IMAGE_PATH_NO_ARGUMENTS`
- bootstrap resource type/name/language/exact count

이는 live host 증거가 아니라 정책 구조 계약이다. projection receipt도 host·code/provider·authority·production을 계속 false로 둔다.

### fixed-store private handoff

`p0_windows_fixed_owner_policy_store_candidate.py`는 held handle/watch 구간에서 검증한 parsed body를 private tuple로 전달한다. 기존 공개 함수와 public receipt material은 유지한다. preflight가 반환받을 때 store handles와 watches는 이미 닫혔으므로 `single_interval_store_host_cross_binding_verified=false`를 명시한다.

### zero-input preflight

공개 API는 다음 하나다.

```python
observe_fixed_windows_owner_provisioning_preflight_candidate()
```

동작 순서는 다음과 같다.

1. Windows와 zero-input 공개 경계를 확인한다.
2. fixed store를 같은 호출에서 검증하고 outer/nested receipt self-hash·gate·truth table, v2 policy/signature domain, full body identity, bootstrap signature math·key/provider/raw hash, projection hash를 재검증한다.
3. v1 또는 forged/resealed child receipt는 SCM 호출 전에 `OWNER_POLICY_V2_NOT_VERIFIED`로 닫는다.
4. direct `advapi32` SCM API로 exact service만 열고 bounded two-call `QueryServiceConfigW`와 `QueryServiceConfig2W`를 수행한다. shell, PowerShell, `sc.exe`, `PATH`, environment selector는 사용하지 않는다.
5. exact 설정을 통과한 경우에만 verifier image를 held handle로 열어 volume-GUID final path, volume serial, 128-bit file ID, single-link/non-reparse/unnamed stream, SHA-256, pre/post stability를 비교한다.
6. 예상되는 store/service 부재나 불일치는 self-hashed structured `NO_GO` receipt로 반환한다. 서비스 설치·시작·변경, 파일·ACL·정책 변경은 하지 않는다.

서비스 process token, embedded resource 실제 선택, Authenticode, WDAC/UMCI, loaded provider, trusted time/revocation, signed native observer, external provisioning과 authority 필드는 모든 경로에서 false다.

## 현재 호스트 read-only 판정

실제 공개 API 결과는 다음과 같다.

```text
decision = NO_GO
failure_stage = FIXED_STORE
receipt_sha256 = bbed3cdd9d309f22db22fe9607b9000f31d924b8ed3c677b9dbbfadf2351a172
```

blocker는 fixed store/v2 policy/service config/image/token/resource/Authenticode/WDAC·UMCI/loaded CNG/trusted time·revocation/signed observer/single interval/external provisioning 전부 미검증이다. 별도 read-only host 감사에서는 다음을 확인했다.

- `C:\ProgramData\llm-novel-dc\p0-owner-policy-v1` 부재
- `llm-novel-dc-p0-owner-verifier-v2` 서비스와 예상 Program Files PE 부재
- kernel CI enforced, user-mode CI off
- 현재 token medium integrity, Administrators deny-only, admin false
- TPM 2.0 storage ready지만 attestation not ready이고 IFX ROCA 취약 firmware 표시
- System32 `bcrypt.dll`/`bcryptprimitives.dll`의 catalog 서명은 valid지만 실행 verifier loaded-module identity와 owner projection 결속은 불가

이는 외부 provisioning을 수행하라는 뜻이 아니라 현재 호스트에서 P0 authority를 열 수 없다는 읽기 전용 증거다.

## 검증

- preflight focused: `11/11 PASS`
- deployment/policy/bootstrap/fixed-store/preflight direct adjacent: `67/67 PASS`
- 전체 `test_p0*.py`: `520/520 PASS`
- 관련 module/test `py_compile`: PASS
- scoped `git diff --check`: PASS (`.gitignore` 기존 CRLF 경고만 존재)
- 종료 시점 중앙 Slang DB 1개와 publication journal 5개: 직전 기준 SHA와 `6/6` 일치
- 좁은 fixture validator noninterference receipt: `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`

noninterference 도구는 전체 P0 suite wrapper가 아니라 P0 fixture validator 자체의 before/after audit이다. 따라서 전체 suite 비간섭으로 과장하지 않는다. 이번 작업은 component unittest와 read-only host audit이므로 실제 regression run의 dashboard·`--parallel 16` 대상이 아니다. actual source claim과 사람 A-context review는 여전히 `0/40`, `0/20`이다.

## 잔여 gate

1. owner가 v2 signed genesis, native PE service, exact WDAC policy를 별도 권한 경계에서 provision할지 결정한다.
2. native observer는 nonce, policy body bytes SHA, projection SHA, service PID/creation time, token SID, image/module identity를 서명해야 한다.
3. service running/PID 안정성, LocalSystem user SID와 enabled restricted service SID, linked token 부재를 시작·종료 두 번 관측한다.
4. PE resource exact selector/bytes, embedded Authenticode selected chain SPKI, active WDAC policy/base/hash와 UMCI enforced를 검증한다.
5. target process의 실제 loaded bcrypt modules와 held disk identity, exact catalog member digest/tag, chain SPKI, trusted time·revocation을 결속한다.
6. SCM ctypes size/last-error/cleanup failure-injection과 v1 public receipt exact golden은 저우선순위 component 회귀로 추가한다.
7. 위 단계와 external owner provisioning이 모두 통과하기 전에는 실제 40+20, Pyserini/gold-lite/retrieval/reranker/NIL shadow를 시작하지 않는다.

## 2026-09-03 후속 상태

다음 tranche인 [actual readiness blocker compiler](P0_ACTUAL_READINESS_BLOCKER_COMPILER_REVIEW_20260903_KO.md)를 구현했다. 이 과정에서 service 설정 검증 뒤 image 실패 시 service projection이 유실되던 문제와 generic malformed v2 실패가 v1 hard-reject로 기록되던 문제를 수정했다. preflight+compiler focused `22/22`, 전체 P0 `531/531`이다. 현재 host child receipt `bbed3cdd…51a172`와 `FIXED_STORE / NO_GO`는 유지되며, fixed store 단계에서 멈추므로 SCM 뒤 service/image 부재를 단정하지 않는다.
