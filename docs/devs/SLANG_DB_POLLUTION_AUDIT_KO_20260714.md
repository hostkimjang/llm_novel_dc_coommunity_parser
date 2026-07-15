# 2026-07-14 Slang DB 오염 감사와 fail-close 보강

## 최신 실런 확인 — 신규 오염 0, 중앙 무변경

최종 검색 P1 런 `20260714_222518_895497`에서 strict exact-pair 저장 계약이 실제로 적용됐다.

- 중앙 DB: `261 title / 87 slang / 173 pending / 28 conflict`, SHA256 `a8c3fb9b083f6914e24bbede5adbbce73372f834dee4271611eefaaeeebcf10a`로 런 전후 동일하다.
- work DB: `261 / 87 / 173 / 28`, 신규 title/term/pending/conflict `0`이다.
- 달라진 레코드는 기존 작품 `즉사기 들고 무림에 떨어지다`, `아카데미 생존 갤러리` 2개뿐이며 새 일반명사 표면을 만들지 않았다.
- `11716480`, `11716475`, `11718099`은 최종 `HOLD`라 BatchContext publish-only 학습과 slang write 관측에서 제외됐다.
- VLM이 `꿇은→끓은`으로 오독했지만 오타 제목이 신규 DB 레코드로 저장되지 않았다.
- manifest의 work artifact `promotion_ready=true`는 파일 구조상 승격 가능 상태일 뿐 semantic approval이 아니다. `semantic_approval=NOT_EVALUATED`, 중앙 writeback `false`이므로 work artifact는 격리 유지한다.

판정은 `SLANG_WRITE_PATH_TARGETED_PASS / CENTRAL_PROMOTION_HOLD`다. 기존 중앙의 42개 격리 seed와 과거 work artifact 오염은 별도 정리 대상이며, 이번 결과를 근거로 자동 삭제하지 않는다.

## 결론

Run `20260714_160355_054970`의 attempt-local Slang DB는 `NO-GO / QUARANTINE`이다. 중앙 `slang_db/slang_db.json`은 아직 변경되지 않았지만, 작업 DB에는 일반명사·동사 조각·플랫폼명·비별칭 표면이 `slang` 또는 `pending`으로 들어갔다.

- 현재 런의 work artifact 중앙 승격: `BLOCKED`
- 중앙 DB 자동 writeback: `금지 유지`
- 신규 쓰기·기존 seed exact-pair fail-close 코드: `UNIT_VERIFIED / PREFIX_REPLAY_PASS`
- 현재 실행 프로세스 반영: `NOT_APPLIED` — 패치 전 코드를 이미 메모리에 올린 런이다.
- fresh targeted/canary: `NOT_RUN`
- 의미 품질/운영 승인: `REVIEW-LOCKED / full_scan_approval=false`

## 실제 증분

2026-07-14 18:30 KST, checkpoint `288`행과 work artifact `updated_at=18:20:44` 기준이다.

| 항목 | 중앙 DB | work DB | 변화 |
| --- | ---: | ---: | ---: |
| title bucket | 261 | 271 | +11 / -1 |
| slang | 87 | 91 | +4 |
| pending | 173 | 180 | +10 / -3 |
| conflict | 28 | 26 | 신규 0 / -2 |

신규 term 14개 중 명확한 오염은 8개(`57.1%`)였다.

| 판정 | term → title | 근거 |
| --- | --- | --- |
| 오염 | `지력 → 옥수수` | 일반명사인데 resolved row의 `primary_work/title_candidate`만으로 clean `slang` 승격 |
| 오염 | `네이버 → 조선에서 태종이 나를 픽함` | 플랫폼명이 작품 alias로 기록 |
| 오염 | `보내 → [메이플스토리] 두 명의 대적자` | 동사 조각 |
| 오염 | `세상 → [프문]부족한 예술일수록 더욱 아름답게 피어나리라` | 일반명사 |
| 오염 | `있었 → 호랑이 새끼` | 동사 조각 |
| 오염 | `연참 → 사랑에 연참이 있었다면` | 출판 일반어이며 explicit relation 근거 없음 |
| 오염 | `쿠크루 → 괴담 호텔 탈출기` | 해당 row에서는 작품 alias 관계가 검증되지 않음 |
| 오염 | `비처녀노 → 비처녀 용사파티 탈퇴합니다` | 게시글 문장 표면 오인 |
| 모호 | `라그나 → 라그나 크림슨`, `묵향 → 묵향 다크레이디` | title prefix/시리즈명일 수 있으나 alias 확정 근거 부족 |
| 유지 가능성 | `케문제`, `망겜성`, `마좋좋좋`, `마학간` | 사람 눈에는 약칭 형태지만, 이 중 명시 alias 관계가 없는 쌍은 DB-ready가 아니라 CandidateLedger HOLD 대상 |

기존 중앙 항목도 이번 런에서 `코로나 → 바이러스`, `솔직히 → 솔직히 보추까진...`, `페이트 → 페이 포인트`가 증폭됐다. 중앙 파일 자체는 delayed writeback 때문에 아직 바뀌지 않았다.

### 18:58 KST live delta 갱신

패치 전 프로세스가 계속 진행되면서 work DB는 `274 title / 92 slang / 182 pending / 26 conflict`, 중앙 대비 신규·승격 term `17`개가 됐다. 새로 `나누는게 → 한달마다 바뀌는 아내`, `전쟁 → 로판을 망친 매국노가 되었다`가 일반 문장/명사 오염으로 추가됐고, 구조적 약칭 `주술초월 → 주술사는 초월을 원한다`도 정상 추가됐다.

20:23:54 KST partial 종료 뒤 이중 읽기로 고정한 최종 work snapshot은 `279 title / 96 slang / 186 pending / 26 conflict`, SHA-256 `2a7c43a1...7333b`다. 중앙은 `261 / 87 / 173 / 28`, SHA-256 `a8c3fb9b...cf10a`로 변하지 않았다. 후반부에는 `어려운애기 → 응애 난 애기야`, `스미스든 → 도망자 스미스...`, `초보자 → [메이플]...` 같은 일반어·작성자 메타 표면도 추가됐다. 이 최종 수치는 patch 전 process가 만든 오염 artifact의 종료 스냅샷이며 새 guard의 실패로 세지 않는다. work artifact 전체는 계속 `NO-GO / QUARANTINE`, central promotion은 `BLOCKED`다.

patch 후 fresh targeted run `20260714_204406_840036`의 6행 work DB는 중앙과 term key가 완전히 같아 신규 `slang/pending/conflict`가 `0`이다. 실제 observation은 기존 검증 alias `즉사무림 → 즉사기 들고 무림에 떨어지다`, `아생갤 → 아카데미 생존 갤러리`만 갱신했고, 일반어 `고능아 → 지력 99 고능아인 척하기`는 `store_in_slang_db=false`라 mutation하지 않았다. 이 결과는 targeted gate 통과이며 200행 일반화 승인은 아직 아니다.

같은 시점 result prefix `316`행을 patched manager로 재생하면 `나누는게`, `전쟁`은 차단되고 `주술초월`만 추가된다. 따라서 당시 patch 전 process와 patched 경계의 실제 차이가 live prefix에서도 재현됐다.

### 19:23–19:30 KST 잔여 구조 유사도 경로 감사

첫 패치 뒤 strict-manager replay에는 `47 observation / slang 30 / pending 17`이 남았다. 원문과 provenance를 다시 대조하니 다음처럼 `abbreviation_match_score`가 높다는 이유만으로 비별칭 표면이 살아 있었다.

- `페이트 → 페이 포인트`: Fate를 직접 언급한 글인데 `title_candidate`, score `0.85`
- `로판이나 → 로판 속 주인공이 나만 좋아함`: 장르 일반 문장의 `recommendation_candidate`, score `0.90`
- `니생 → 니들 생각 다 들린다`: `recommendation_candidate`, score `0.95`
- `부분부분 → 정의실현부 전략병기분대 부분대장입니다`: 일반 부사 반복, score `0.80`
- `유니콘들 → 유니콘이 안심하고 먹을수 있는 노벨피아 사료들 ver 1.1`: 일반 독자 집단명, score `0.85`

따라서 구조 점수는 alias 관계 증명이 아니라 후보 정렬 신호로만 남겼다. exact-pair gate 적용 뒤 고정 checkpoint prefix `419`행 strict-manager replay는 `36 observation / slang 32 / pending 4 / error 0`이며 위 다섯 표면과 `매국노` 관련 잘못된 `전쟁` 표면은 모두 `0`건이다. 중앙 snapshot에 실제 manager write를 재생한 결과 신규 term은 아래 검증된 6개만 남았다.

- `케문제 → K-문화의 제왕`
- `대마대 → 대마법사였던것은 다시 대마법사를 꿈꾼다`
- `망겜성 → 망겜의 성기사`
- `사연있는악역착각 → 사연 있는 악역으로 착각 당한다`
- `용파때 → 용사 파티 때려치웁니다`
- `주술초월 → 주술사는 초월을 원한다`

`마좋좋좋`, `마학간`은 형태상 정상 후보여도 해당 row에 exact alias 관계 증명이 없어 Slang DB 쓰기에서 제외했다. 이는 작품 후보 삭제가 아니라 CandidateLedger 보존과 alias memory mutation을 분리한 것이다.

## 원인

`src/llm_batch/slang/slang_db.py`의 기존 수집 계약에는 세 결함이 있었다.

1. `slang_insight.store_in_slang_db=false`가 직접 `slang_insight` 표면만 막고, 같은 결과의 `primary_work.alias_or_mention`과 `title_candidates[].alias_or_mention`은 별도 경로로 다시 수집할 수 있었다.
2. `confidence=High/Medium` 또는 `source_tier=official_detail`은 작품 후보의 근거일 뿐 alias 관계의 근거가 아닌데도 강한 alias로 인정했다.
3. `abbreviation_match_score >= 0.45`도 문자열 구조 유사도일 뿐 alias 관계 증명이 아닌데, title/reference candidate를 Slang DB `pending`으로 번역하는 허가로 사용했다.

그 결과 public title이 HOLD여도 work DB `pending`을 오염시켰고, resolved 오판 row에서는 일반명사가 clean `slang`으로 승격될 수 있었다. 기존 중앙 slang read 경로도 비구조 alias를 기본 허용해 다음 BatchContext seed로 재사용할 수 있었다.

## 보강한 계약

### 신규 쓰기

- `store_in_slang_db=false`이면 raw `detected_term`을 차단한다. clean `canonical_work_alias`는 `primary_work/title_candidate`에서 아래 exact-pair 증명을 독립적으로 통과할 때만 허용하고, reference 역할 우회는 허용하지 않는다.
- `store_in_slang_db=true`를 선언했지만 strict 계약이 불완전하면 관련 `slang_insight/primary_work/title_candidate`를 모두 fail-close한다.
- `store_in_slang_db=None`은 미설정으로 두되, 그 외 문자열·숫자·배열·객체는 명시 정책으로 해석하지 않고 fail-close한다.
- `mentioned_work`, `secondary_reference`, `recommendation_candidate`, `comparison_target`는 결과/CandidateLedger에만 보존하고 Slang DB mutation을 만들지 않는다.
- `confidence`·`source_tier`·official URL·`abbreviation_match_score`만으로 alias 자격을 만들지 않는다.
- 신규 write는 아래 셋 중 하나로 exact `(alias, official_title)` 관계가 증명돼야 한다.
  1. 완전한 `slang_insight` 계약:
  - `store_in_slang_db=true`
  - `decode_verified=true`
  - `alias_scope=pure_work_alias`
  - `store_reason=pure_work_alias`
  - `detected_term == canonical_work_alias`(정규화 기준)
  - `decoded_term == official_title`(정규화 기준)
  2. `confirmed_alias:<term>`과 verified official-alias flag가 함께 있고 candidate title이 final official title과 일치
  3. `novel_identity.alias_resolution_sources`의 enum tuple, actual registry mapping, alias, canonical title, final official title이 모두 일치

### 기존 중앙 DB seed

기존 중앙 항목은 자동 삭제하지 않았다. 대신 다음 런의 BatchContext seed 주입을 fail-close했다.

- 구조 점수만 맞는 legacy alias는 허용하지 않는다.
- 저장 당시의 완전한 명시 계약, verified explicit-alias flag, trusted registry exact-pair provenance 중 하나를 요구한다.
- 근거가 없는 legacy entry는 DB에 보존하되 seed로 사용하지 않는다.

현재 중앙 slang `87`개를 재판독한 결과 `45`개 허용, `42`개 격리다. 첫 패치의 비구조 오염 14개뿐 아니라 구조 점수만 있고 exact-pair provenance가 없는 28개도 추가로 격리했다. 이는 자동 삭제 판정이 아니라 재검증 전 seed 금지 판정이며, fresh row가 strict 계약을 충족하면 같은 정상 약어를 다시 검증 관측할 수 있다.

`tools/audit_expert_run_health.py`도 기존 sentence/exact 지표와 별개로 `seed_safe_count`, `seed_quarantined_count`, 격리 sample과 실제 patched manager no-write observation을 출력한다. 최신 readback은 `87/45/42`를 재현했다.

## 검증

- `tests.test_slang_db`: `31 PASS`
- tracked regression `tests.test_arbiter_curated_alias_guard`: `34 PASS`
- 관련 묶음: write/seed/low-information `68 PASS`, governance/transaction/BatchContext `33 PASS`, health audit `18 PASS` — 합계 `119 PASS`
- 독립 adversarial 재검토: 음성 `17/17` 차단, 정상 `6/6` 허용, write/seed 불일치 `0`, focused `40/40 PASS`
- `py_compile`: `src/llm_batch/slang/slang_db.py`, 관련 test PASS
- health audit readback: `slang_term_count=87`, `seed_safe=45`, `seed_quarantined=42`
- 고정 checkpoint prefix `419`행 actual-manager replay:
  - strict observations `36`, confirmed `32`, pending `4`, errors `0`
  - 중앙 snapshot 대비 신규 term `6`: `케문제`, `대마대`, `망겜성`, `사연있는악역착각`, `용파때`, `주술초월`
  - 확인된 일반명사/문장 조각과 구조 유사도 오탐 `페이트`, `로판이나`, `니생`, `부분부분`, `유니콘들`, `전쟁`은 `0`
- 정상 제어: strict/verified 근거가 있는 `아생갤`, `즉사무림`, `망겜성`, `케문제`, `주술초월` 보존
- 음성 제어: 일반명사/동사 조각, 구조 점수-only, reference-only, incomplete `store=true`, invalid store reason, detected/canonical 불일치, `store=false` 우회 차단

이 검증은 저장 경계의 단위·prefix replay 증거다. fresh LLM targeted/canary, 중앙 DB 정화 승인, 현재 104,502행 런의 의미 품질 승인은 아니다.

## 다음 게이트

1. 현재 run의 `_slang_db_work.json`은 중앙 승격하지 않고 quarantine한다.
2. 기존 중앙 seed 격리 42개를 source row와 함께 사람이 검토한다. 자동 삭제하지 않는다.
3. 현재 런을 사용자 승인으로 정상 중단한 뒤 patched process에서 known-bad/positive targeted rerun을 수행한다.
4. targeted 통과 후 `--parallel 16`, dashboard ON, VLM/OCR required 조건의 200행 canary에서 신규 일반명사 유입 `0`을 확인한다.
5. canary 전에는 `REVIEW-LOCKED / full_scan_approval=false`를 유지한다.

## 증거 경로

- `slang_db/slang_db.json`
- `out/expert_result_20260714_160355_054970_slang_db_work.json`
- `out/expert_result_20260714_160355_054970.json`
- `out/expert_result_20260714_160355_054970_checkpoint.jsonl`
- `src/llm_batch/slang/slang_db.py`
- `tests/test_arbiter_curated_alias_guard.py`
- `tests/test_slang_db.py`
