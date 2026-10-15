# P0 외부 owner 비대칭 서명 수학 컴포넌트 검토

작성일: 2026-09-02 KST

> 후속 상태: 이 문서의 `OWNER_STATE_NOT_YET_BOUND`는 당시 snapshot이다. same-call raw3 fresh validation과 private object-identity exact-once 소비는 [`P0_EXTERNAL_OWNER_ONESHOT_STATE_REVIEW_20260902_KO.md`](P0_EXTERNAL_OWNER_ONESHOT_STATE_REVIEW_20260902_KO.md)에서 구현·검증했다. artifact replay와 external authority는 계속 NO-GO다.

## 결론

Windows CNG의 ECDSA P-256/SHA-256 검증으로, 별도 제시된 public-key pin과 서명 envelope가 owner root preauthorization의 정확한 canonical bytes를 수학적으로 결속하는 컴포넌트를 구현했다. 채택 범위는 **서명 수학과 presented-pin 계약뿐**이다.

현재 판정은 다음과 같다.

`ASYMMETRIC_SIGNATURE_MATH_PASS / PRESENTED_PIN_ONLY / EXTERNAL_PROVISIONING_NO_GO / OWNER_STATE_NOT_YET_BOUND / TRUSTED_TIME_REVOCATION_DURABLE_NONCE_NO_GO / ACTUAL_0_OF_40_0_OF_20 / PARSER_SANDBOX_NO_GO`

caller가 pin, key, preauthorization을 모두 공격자 값으로 일관되게 교체하고 그 key로 다시 서명해도 `asymmetric_signature_math_verified=true`가 될 수 있다. 따라서 이 결과는 외부 owner가 key를 보유했다거나 pin이 독립적으로 provision됐다는 증거가 아니다. 공개 receipt도 `serialized_receipt_authoritative=false`, `execution_trace_transferable_by_receipt=false`이며, authority·P0 Exit·production/full scan을 열지 않는다.

## 구현 계약

대상 모듈은 `src/llm_batch/grounding/p0_external_owner_asymmetric_signature.py`다.

- 공개 검증 API는 `public_key_pin_bytes`, `signature_envelope_bytes`, `owner_root_preauthorization_bytes` 세 원문만 받는다. private key, signer callback, provider 선택 인자는 없다.
- pin의 P-256 공개키 좌표 X/Y는 각각 exact 32-byte big-endian canonical base64다.
- fingerprint는 RFC 5480 `id-ecPublicKey + prime256v1` DER SubjectPublicKeyInfo를 재구성한 SHA-256이다. provider 전용 key blob fingerprint로 대체하지 않는다.
- 서명은 exact 64-byte big-endian `r||s`이며 `0 < r < n`, `0 < s <= n/2`인 canonical low-S만 허용한다.
- 서명 입력은 signature와 envelope self-hash를 제외한 exact field inventory의 canonical UTF-8 JSON bytes다. domain, trust domain, project/environment/purpose, session/run/preauthorization/parser run, nonce commitment, key id/epoch, fingerprint, owner principal/anchor, preauthorization schema·raw-byte SHA·artifact SHA를 포함한다.
- pin·envelope·preauthorization은 duplicate key, BOM, CRLF, non-finite value, trailing bytes와 noncanonical base64를 거부한다. 세 원문의 raw SHA와 self-hash 및 context 교차 결속을 다시 계산한다.
- Windows CNG `BCryptOpenAlgorithmProvider`는 암묵적 기본값이 아니라 명시적 `Microsoft Primitive Provider`와 `ECDSA_P256`으로 고정한다. `BCRYPT_ECCPUBLIC_BLOB`으로 key를 import하고 SHA-256 digest를 `BCryptVerifySignature`에 전달한다.
- receipt는 provider 이름을 기록한다. 다만 DLL/native provider image provenance와 서명 구현 공급망은 닫지 않았으므로 `trusted_cng_provider_provenance_verified=false`다.

## 반대검토와 진실성 경계

| 공격·주장 | 결과 | 해석 |
| --- | --- | --- |
| signature bit, high-S/zero/out-of-range scalar 변조 | `REJECT` | 서명 형식과 수학 검증이 fail-close함 |
| preauthorization exact bytes, project/run/id, context, key epoch/fingerprint 변조 | `REJECT` | canonical preauth와 envelope/pin 교차 결속이 작동함 |
| HMAC/algorithm/domain downgrade | `REJECT` | 고정 ECDSA P-256 domain만 허용함 |
| attacker pin만 좌표 교체 | `REJECT` | 원래 서명과 새 공개키가 맞지 않음 |
| attacker pin+key+preauthorization 전체 일관 교체 | 서명 수학은 `PASS` 가능 | presented input 자체의 독립 provenance가 없으므로 external owner authority는 아님 |
| receipt 파일의 재제시 | authority로 사용 불가 | serialized receipt는 실행 진실을 이전하지 않음 |

따라서 다음 필드는 계속 false다.

- `external_public_key_pin_provisioning_verified`
- `independent_readonly_public_key_pin_verified`
- `public_key_pin_rollback_protection_verified`
- `key_epoch_monotonicity_verified`
- `external_owner_signing_key_verified`
- `private_key_outside_verifier_verified`
- `trusted_cng_provider_provenance_verified`
- `trusted_time_verified`
- `revocation_current_verified`
- `revocation_rollback_protection_verified`
- `durable_cross_process_nonce_verified`
- `power_loss_durable_replay_verified`
- `external_owner_trust_verified`
- `owner_authority_verified`
- `actual_authority_granted`
- `p0_phase_exit`
- `production_approval`
- `full_scan_approval`

## fresh 검증

| 범위 | 결과 |
| --- | --- |
| 신규 비대칭 서명 focused | `15/15 PASS` (`3.970s`) |
| direct adjacent | `78/78 PASS` (`9.240s`) |
| 전체 P0 | `422/422 PASS` (`25.454s`) |
| Python compile | 신규 모듈·테스트 `py_compile PASS` |
| 기존 상태 비간섭 | 중앙 Slang DB 1개+publication journal 5개 `6/6` byte·SHA 불변 |
| actual·credited | source claim `0/40`, A-context `0/20` |

비간섭 receipt SHA는 `6033c6d0c648175f255c10042b9104d4ccc183d94a76901ed44a1649fd98204e`, fixture aggregate SHA는 `d94e1de3c5b4f8cd801804467fe82efed68ead1ec1b1abb986f48861a734545c`, 중앙 DB SHA는 `a8c3fb9b083f6914e24bbede5adbbce73372f834dee4271611eefaaeeebcf10a`다.

이 검증은 Windows component unittest다. actual regression-safe pipeline run이 아니므로 dashboard와 `--parallel 16` 적용 대상이 아니다. count와 gate를 실제 semantic evidence로 확대하지 않는다.

## 공식 근거

- Microsoft [BCryptImportKeyPair](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptimportkeypair): CNG key pair import와 blob type 계약.
- Microsoft [BCryptVerifySignature](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptverifysignature): 공개키 handle, hash, signature의 검증 계약.
- Microsoft [BCRYPT_ECCKEY_BLOB](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/ns-bcrypt-bcrypt_ecckey_blob): ECC public blob header와 고정-width X/Y 형식.
- Microsoft [CNG에서 데이터 서명](https://learn.microsoft.com/en-us/windows/win32/seccng/signing-data-with-cng): CNG signing/verification API 흐름.
- IETF [RFC 5480](https://www.rfc-editor.org/rfc/rfc5480): EC SubjectPublicKeyInfo의 algorithm identifier와 point encoding.
- NIST [Cryptographic Algorithm Validation Program](https://csrc.nist.gov/projects/cryptographic-algorithm-validation-program/digital-signatures): ECDSA 검증 벡터와 알고리즘 검증 맥락. 테스트는 P-256 base-point RFC 5480 SPKI fingerprint known vector도 독립 확인한다.

## 다음 P0 순서

다음 통합은 public receipt를 재입력하지 않는다. 같은 호출에서 검증된 원문 세 종류 `public_key_pin_bytes`, `signature_envelope_bytes`, `owner_root_preauthorization_bytes`를 다음 supervisor가 직접 소비하거나, private registry가 발급한 one-shot state만 소비해야 한다. 이를 `OWNER_STATE` 경계로 둔다.

그 뒤에도 아래가 순차적으로 필요하다.

1. run/protected root 밖 immutable read-only public-key pin과 owner SID/ACL, verifier 밖 owner signing key를 실제 provision한다.
2. key epoch·revocation high-watermark와 nonce 소비를 같은 durable state plane에 결속하고 trusted time·rollback·crash/reboot를 검증한다.
3. owner-signed root identity/USN, AppContainer/LPAC, network/write deny와 runtime/native dependency provenance를 닫는다.
4. adversarial Windows E2E와 실제 semantic source-profile parser를 통과한다.
5. 그 뒤에만 dashboard ON, 요청 병렬도 `--parallel 16`으로 actual source claim 40건+A-context 20건을 수집·사람 판정한다.

이전까지 actual·credited는 `0/40`, `0/20`, `PARSER_SANDBOX_NO_GO`, `METRICS_NOT_ESTIMABLE`, `REVIEW_LOCKED`, `full_scan_approval=false`다. Pyserini, gold-lite, retrieval/reranker/NIL shadow A/B도 시작하지 않는다.
