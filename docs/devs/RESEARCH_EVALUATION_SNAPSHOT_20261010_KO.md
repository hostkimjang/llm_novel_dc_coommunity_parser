# 저장 결과 평가 snapshot 운영

R1의 읽기 전용 snapshot 모듈·CLI를 기본 폴더에 구현했다. 기존 결과·manifest·원문을 명시한 바이트 해시로 연결하고 실행별 분모와 중복 제거 분모를 분리한다. 모델·검색을 호출하거나 원본 결과·참조판정·중앙 DB를 바꾸지 않는다.

## 사용 방법

`tools/build_research_evaluation_snapshot.py`는 요청 명세와 새 출력 디렉터리를 받는다. `research-root`는 이미 존재하는 디렉터리여야 하며 출력은 그 아래 새 경로로만 생성한다. 기존 출력 덮어쓰기는 거절한다.

```powershell
python tools/build_research_evaluation_snapshot.py --spec <명세.json> --research-root out/research --output-dir out/research/<새이름>
python tools/build_research_evaluation_snapshot.py --verify-dir out/research/<새이름>
```

요청 schema는 `research_snapshot_request_v1`이다. 각 dataset에 `dataset_id`, `sample_namespace`, `data_kind`, result·manifest의 정확한 path와 SHA-256을 지정한다. 같은 표본의 서로 다른 실행은 namespace를 같게 두고 dataset과 run을 구분한다. 합성 자료 `SYNTHETIC_FIXTURE`와 실제 저장 자료 `SAVED_ARTIFACT`는 별도 분모로 집계한다.

input과 reference는 선택 사항이다. 프로젝트의 게시글·댓글 혼합 JSONL은 `input.format=JSONL_POST_COMMENT_V1`을 명시한다. 원래 줄번호·줄 바이트 SHA·게시글 순서와 댓글의 부모 연결을 보존한다. 기존80·32를 읽은 [명세 예시](../../out/development_plan_20261010/r1_draft/saved80_32_request.json)는 당시 원본 경로와 해시에 고정돼 있다. 다른 실행에 적용할 때 경로·해시·run 결속을 함께 새로 지정한다.

출력은 `source_refs.json`, `rows.jsonl`, `snapshot_manifest.json`, `report_ko.md` 네 파일이다. source refs는 원본 위치와 바이트 해시, rows는 원래 저장 행과 입력·reference 연결, manifest는 실행별 분모·제한·출력 및 자기 해시를 담는다. `--verify-dir`은 이 네 파일의 자체 무결성을 검사하며 원본의 독립 권위나 판정의 진실성을 검증하지 않는다. 종료코드는 정상0, `INVALID_BINDING` 2, 파일·요청·해시·IO 오류1이다.

## 결속과 제한

- manifest의 입력 SHA·run·publication scope와 행의 receipt·ledger 좌표를 대조한다. 누락은 LIMIT, 알려진 모순은 ERROR다. receipt가 없다는 이유로 다른 ledger의 모순을 무시하지 않는다.
- false·0·null·미기록, 후보 UNKNOWN/TRUNCATED, 원문·판정·메모·저장 장부를 보존한다. 행의 연결 대기와 manifest의 종료 연결 수를 합치지 않는다.
- 과거 code/config 지문을 현재 checkout SHA로 채우지 않는다. reference는 명시적으로 결속된 호출자 값을 보존하되 `CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED`로 표시한다. 미결속 reference는 UNJUDGED다.
- 순수 builder는 파일을 읽지 않으므로 `CALLER_METADATA_ONLY`, 실제 exporter는 입력을 전후 재판독해 `VERIFIED_START_END`를 기록한다. 전역 파일시스템 비변경이나 독립 provenance를 증명한다는 뜻은 아니다.
- 파일당 읽기 상한은64MiB다. 쓰기 도중 실패하면 새 output에 일부 파일이 남을 수 있으나 최종 manifest를 발급하지 않는다. 자동 삭제·덮어쓰기 없이 새 경로를 사용한다.
- `publication_authority=false`, `central_db_write=false`, formal KPI `NOT_ESTIMABLE`을 유지한다. 독립 표본 수·후보 recall·가격 KPI를 임의 산정하지 않는다.

## 적용과 검증

정식 적용 파일은 `src/llm_batch/measurement/research_evaluation_snapshot.py`, `tools/build_research_evaluation_snapshot.py`, `tests/test_research_evaluation_snapshot.py`다. 독립 검토에서 입력 바이트 결속·scope·JSONL과 receipt 없는 ledger 모순을 찾아 수리했다. [최종 검토](../../out/development_plan_20261010/r1_draft_review.md)는 PASS다. 검토된 초안에서 package import와 CLI 경로·설명만 조정해 적용했다.

정식 경로의 시험 **28 PASS, 2.28초**다. 실제 Python 프로세스의 BelowNormal·단일 CPU·numeric threads1과 primary module 경로를 확인했다. [적용 수령증](../../out/development_plan_20261010/r1_application_receipt.json), [검증 수령증](../../out/development_plan_20261010/r1_package_verification_receipt.json), [시험 로그](../../out/development_plan_20261010/r1_package_tests.log)에 근거를 남겼다.

실제 저장 자료는 [새 snapshot 보고서](../../out/research/primary_evaluation_snapshot_20261010/report_ko.md)에서 확인한다. 기존80과 후속32의 입력/저장은80/80·32/32이며 관측112행, 고유 게시글80개·원문80개다. 독립 표본 수는 null이다. 원본6개와 명세의 해시는 전후 동일하고 초안·정식 도구의 semantic SHA도 `4fce6839ab9237daf634995d6e12aaac70db00e2c7813b12e2c2798bd0f007d8`로 같다. CLI 자체 검산도 VERIFIED다.

이 snapshot은 `COMPLETE_WITH_LIMITS`다. 과거 manifest2개에 `input_file` 경로가 없어 경로는 명세로 연결했지만 입력 바이트 SHA는 각각 정확히 일치했다. reference 변환기는 아직 연결하지 않아 모든 행은 REFERENCE_NOT_BOUND/UNJUDGED다. [별도80행 참조 색인](../../out/development_plan_20261010/p4_semantic_reference_inventory.json)의 MODEL_REFERENCE를 자동 Gold로 승격하지 않는다.

R1의 현재 완료 범위는 저장 자료의 재현 가능한 읽기·분모·검산이다. CandidateSet 원형은 그대로 보관하며, typed parser와 reference 후보 ID 대응은 R2 실제 회수 평가에 맞춰 후속 연결한다. 기존 observation envelope에 새 공개 권위를 추가하지 않았다. P4 새80건 실측·의미 검토, R2~R6 연구 개발과 성능 평가는 이 도구의 완료와 별개다.
