# P0 Windows bootstrap policy 서명 수학 후보 구현·재회의

## 결론

고정 owner-policy 저장소가 같은 호출에서 읽은 `body.json`과 `signature.json`을 대상으로 Windows CNG ECDSA P-256/SHA-256 detached signature를 검증하도록 구현했다. 판정은 `BOOTSTRAP_POLICY_SIGNATURE_MATH_CANDIDATE_PASS_CODE_AUTHORITY_NO_GO`다. 서명 수학과 exact raw-byte 결속은 통과하지만, 컴파일 공개키 후보의 외부 owner 승인·독립 배포·실행 코드 신뢰·rollback 상태는 증명하지 않는다.

컴파일 공개키 후보 ID는 `compiled-bootstrap-candidate-20260902-001`, RFC 5480 SPKI fingerprint는 `5693c09f1b6a59b26a9c97d7c93c07549b39b0ec43eb6e5952769711bc726234`다. 후보 생성에 쓰인 임시 private key는 보존하지 않았으므로 이것은 실제 owner key나 production trust root가 아니다. 정책 파일 안의 key ID·fingerprint는 lookup 입력으로 사용하지 않고 컴파일 후보와 exact 비교만 한다.

## 전문가 재회의

암호 transcript 설계, 구현 독립 감사, API·테스트 공격 감사, fixed-store consumer 통합 검토를 병렬로 진행했다.

| 의견 | 결정 | 반영 |
| --- | --- | --- |
| 9개 envelope field만 canonical transcript로 사용 | `ADOPT` | `signature_rs_base64`, `artifact_sha256`를 제외한 고정 순서 field map을 canonical JSON bytes로 만들고 SHA-256을 한 번만 적용 |
| body raw SHA를 transcript에 포함 | `ADOPT` | 정규화 후 객체가 아니라 held handle에서 읽은 exact `body.json` bytes를 결속 |
| 정책 안의 bootstrap key로 verifier 선택 | `REJECT` | source candidate는 코드 상수로만 선택하고 body/envelope의 ID·fingerprint는 비교값으로만 사용 |
| 서명 수학을 독립 pin·소유자 권한으로 승격 | `REJECT` | `bootstrap_public_key_independently_pinned`, code/provider provenance, owner/actual/P0/production을 모두 false 유지 |
| child receipt 일부 SHA만 확인 | `REJECT` | schema, gate, self-hash, 필수 true, authority false, transcript/provider/key/body/contract 결속을 consumer가 재검증 |
| BCrypt Python 예외 원형 노출 | `REJECT` | 공용 CNG primitive와 bootstrap API 모두 전용 오류로 정규화하고 primary 오류를 cleanup보다 우선 |
| trusted code·key deployment, epoch/revocation/nonce를 이번 수학 단계에 포함 | `DEFER` | 외부 provisioner/service/TPM·Authenticode/WDAC와 durable state plane이 준비된 뒤 별도 gate로 검증 |

## 구현

- `p0_windows_bootstrap_policy_signature_candidate.py`
  - 공개 API는 exact raw bytes 두 개만 keyword-only로 받고 path/key/provider/callback/receipt/state selector를 받지 않는다.
  - strict owner-policy 계약을 재실행하고 body/envelope key ID·fingerprint를 컴파일 후보에 비교한다.
  - low-S raw P1363 `r||s`, exact transcript, single SHA-256, `Microsoft Primitive Provider` CNG 검증을 수행한다.
  - receipt는 signature math만 true로 두고 외부 pin·code/provider provenance·owner authority·actual/P0/production은 false로 둔다.
- `p0_windows_cng_ecdsa_p256.py`
  - provider·curve·blob·digest/signature 폭을 고정한 공용 검증 primitive다.
  - key/provider cleanup을 모두 시도하고 primary 오류를 보존한다. BCrypt가 status 대신 Python 예외를 던져도 전용 오류로 fail-close한다.
- `p0_windows_fixed_owner_policy_store_candidate.py`
  - 8개 role handle과 watcher가 유지된 같은 관측 구간에 bootstrap verifier를 호출한다.
  - child receipt의 canonical self-hash·schema·success truth table·authority false table·raw SHA·contract receipt·컴파일 key identity를 재검증한다.
  - top-level success boolean은 검증된 child receipt에서만 전달한다.
- `p0_external_owner_asymmetric_signature.py`
  - 중복 CNG 구현을 공용 primitive에 위임하되 기존 공개 오류 계약은 유지한다.

## 반례와 수정

독립 감사에서 두 실제 결함을 재현해 수정했다.

1. `BCryptOpenAlgorithmProvider` 등 ctypes 호출이 `OSError`/`TypeError`를 던지면 raw 예외가 공개 API로 누출됐다. 공용 primitive가 예상 밖 `Exception`을 전용 오류로 감싸고 bootstrap 계층도 방어적으로 정규화한다.
2. fixed-store consumer가 child receipt의 raw SHA 일부만 확인하고 top-level math success를 하드코딩했다. child의 math/selected를 false로 바꾸고 self-hash를 위조해도 성공하던 경로를 schema·self-hash·필수 boolean·key/provider/truth-table 재검증으로 차단했다.

테스트 감사에서 exact GUID를 캡처만 하고 assertion하지 않던 결함도 고쳤다. ProgramData GUID raw bytes를 고정 회귀로 검사한다. 실제 컴파일 공개키는 의도된 invalid signature canary에서 key import를 통과한 뒤 signature mismatch에 도달함을 확인한다. private key가 없는 설계이므로 실제 컴파일 key로 서명된 production positive golden은 아직 없으며, 이를 독립 owner provisioning 증거로 대체하지 않는다.

## 검증

- bootstrap + fixed-store + 외부 owner asymmetric focused: `47/47 PASS`
- Windows owner-policy 인접군: `117/117 PASS`
- 전체 `test_p0*.py`: `497/497 PASS` (`32.981s`)
- 변경 Python compile 및 scoped `git diff --check`: `PASS`
- 중앙 Slang DB 1개와 publication journal 5개: `6/6` byte·SHA 불변
- noninterference receipt: `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`

이 검증은 component unittest와 읽기 전용 감사다. actual dataset run이 아니므로 dashboard·`--parallel 16` manifest 대상이 아니다. actual source claim과 A-context credited count는 각각 `0/40`, `0/20`; `p0_phase_exit=false`, `production_approval=false`, `full_scan_approval=false`다.

## 남은 gate

1. 실제 외부 owner가 승인한 bootstrap public key와 signed genesis policy를 immutable service/binary/TPM 경계에 provision하고 code/DLL/provider provenance를 검증한다.
2. verifier 밖 owner SID·ACL로 8-role store를 실제 provision해 mock 없는 live ACL positive와 adversarial Windows E2E를 확보한다.
3. trusted time·revocation과 policy/key epoch rollback-resistant high-watermark를 독립 broker에 둔다.
4. crash/reboot durable nonce와 private authority lease를 결속한다.
5. 위 권한 plane이 닫힌 뒤에만 dashboard ON·`--parallel 16`으로 actual 40+20을 실행한다. Pyserini/gold-lite/reranker/NIL shadow는 P0 Exit 뒤로 유지한다.

낮은 우선순위 기술 부채로 primary 오류와 동시에 발생한 `CoTaskMemFree`·watch finalize·다중 `CloseHandle` 실패 진단 note, mock 없는 8-role ACL negative/positive matrix, production signed golden 부재를 추적한다. 이 부채가 남아 있으므로 현재 후보를 운영 authority로 승격하지 않는다.

## deployment projection v2 후속 정정

후속 전문가 회의는 실제 v1 genesis 서명 전에 trusted verifier 배포 의미를 owner policy에 넣어야 한다고 판정했다. [owner deployment projection v2](P0_WINDOWS_OWNER_DEPLOYMENT_PROJECTION_V2_REVIEW_20260902_KO.md)는 native service·결정적 SID, PE/resource·Authenticode, WDAC/UMCI, loaded CNG provider projection을 별도 v2 body/signature/anchor/receipt에 결속한다. 최초 SID split은 재현·수정됐고 전체 P0 `509/509 PASS`다. 그러나 이 보강도 presented contract이며 zero-input live host preflight와 external signed provisioning 전에는 code/provider authority·actual/P0/production은 NO-GO다.
