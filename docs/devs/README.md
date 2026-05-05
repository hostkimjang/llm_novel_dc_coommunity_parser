# Developer Docs Hub

이 디렉터리는 개발 TODO, 기능 개선, 런 리뷰, 체크리스트, 검증 결과를 한곳에서 추적하기 위한 운영 문서 허브다.

## 문서 맵

- `TODO.md`: 개발/기능개선 TODO 전체 색인
- `DEV_TODO.md`: 코드, 인프라, 테스트, 도구 중심 개발 TODO
- `FEATURE_IMPROVEMENT_TODO.md`: 검색 품질, slang DB, 대시보드 UX 같은 기능 개선 TODO
- `CHECKLIST.md`: 변경 전/중/후에 반드시 확인할 공통 체크리스트
- `OPERATION_QUALITY_CHECKLIST.md`: 대량 런 품질 승인용 GO/REVIEW/NO-GO 게이트
- `SAMPLING_AND_PARALLEL_TEST_GUIDE.md`: 수백만 건 운영을 위한 smoke/canary/risk/validation 샘플 규모 기준
- `LLM_JUDGMENT_REVIEW.md`: LLM/전문가가 결과를 직접 읽고 판단하는 정성 리뷰 프로토콜
- `QUALITATIVE_REVIEW_20260426.md`: 20k run 300건 전문가 정성 리뷰 결과
- `IMPROVEMENT_REGISTER.md`: 개선안의 문제 정의, 결정, 결과, 후속 검증 기록
- `VERIFICATION_RESULTS.md`: 감사 명령, 지표, 판정, 재검증 결과 누적
- `HISTORY.md`: 날짜별 개발/운영 히스토리와 확인 결과

개별 상세 문서는 기존 위치를 유지한다. 예를 들어 검색 shard 사건은 `docs/search_reliability_review_20260426.md`, WARP 구성은 `docs/warp_sharding.md`, slang DB 작업은 `docs/slang_db_improvement_todo.md`에 상세를 둔다.

## 운영 원칙

- 기능 변경, 검색/런 품질 개선, slang DB 규칙 변경 시 `DEV_TODO.md` 또는 `FEATURE_IMPROVEMENT_TODO.md`와 관련 상세 문서를 함께 갱신한다.
- 대량 런 후에는 `HISTORY.md`에 run id, 핵심 지표, 문제, 조치, 재검증 결과를 남긴다.
- 4~20건 테스트는 `SMOKE ONLY`로만 기록한다. 품질 승인에는 100% 자동 감사와 10,000건 이상 validation 샘플 또는 그에 준하는 대형 표본이 필요하다.
- 기능/품질 개선은 구현 후 자동 테스트 런, run audit, 개선 전후 비교 문서, 필요 시 LLM 리뷰 패킷까지 한 묶음으로 남긴다.
- 완료 처리 전에는 `CHECKLIST.md`와 `OPERATION_QUALITY_CHECKLIST.md`의 관련 항목을 확인하고, 확인한 명령/결과를 `VERIFICATION_RESULTS.md`에 적는다.
- 통계 감사만으로 판단할 수 없는 케이스는 `LLM_JUDGMENT_REVIEW.md` 절차에 따라 정성 리뷰 패킷을 만든다.
- 큰 개선은 `IMPROVEMENT_REGISTER.md`에 먼저 등록하고 상태를 `proposed -> in_progress -> verified` 순서로 이동한다.
- 문서에는 추측과 확인 결과를 분리해서 쓴다. 확인한 숫자에는 run id와 생성 파일 경로를 붙인다.

## 상태 규격

- `proposed`: 문제와 방향만 정리됨
- `in_progress`: 코드/설정/문서 변경 진행 중
- `implemented`: 변경은 반영됐지만 충분한 검증 전
- `verified`: 명령 또는 재런으로 개선 확인
- `deferred`: 지금은 보류
- `rejected`: 검토 후 채택하지 않음

## 품질 판정 규격

- `GO`: shard 100% 정상, run audit 정합성 통과, slang 오염 0, 필요한 정성 리뷰 완료, 문서/검증 결과 갱신 완료
- `REVIEW`: 운영은 가능하지만 검색 저하율 상승, 실제 약칭 후보 미검토, pending/flush 차이, LLM/전문가 정성 리뷰 필요
- `NO-GO`: bad shard 존재, `/readyz` 실패, SearchXNG UI 실패, fatal traceback 증가, slang DB 오염 발생

## 변경 기록 템플릿

```markdown
## YYYY-MM-DD - 짧은 제목

- 상태: proposed | in_progress | implemented | verified | deferred | rejected
- 관련 run id:
- 관련 파일:
- 문제:
- 조치:
- 확인:
- 남은 위험:
- 다음 작업:
```
