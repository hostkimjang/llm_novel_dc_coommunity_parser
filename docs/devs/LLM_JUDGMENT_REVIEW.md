# LLM Judgment Review Protocol

이 문서는 코드/통계 검토가 아니라 LLM/전문가가 결과를 직접 읽고 판단하는 정성 리뷰 절차다. 대량 런 결과의 최종 품질 승인은 숫자 감사와 이 정성 리뷰를 함께 본다.

## 목적

- 모델 판정이 원문과 근거에 맞는지 확인한다.
- 검색 저하가 결과 오판으로 이어졌는지 확인한다.
- slang DB 후보가 실제 약칭인지, 보류/비교/노이즈인지 판정한다.
- 재검색, 재처리, 프롬프트 수정, slang rule 수정을 구분한다.

## 리뷰 대상 우선순위

1. 검색 저하 flag가 있고 slang 후보가 생성된 케이스
2. 검색 결과가 0 또는 빈약하지만 LLM이 강한 작품 판단을 내린 케이스
3. `unclear_canonical_alias`로 차단된 회수율 손실 의심 케이스
4. `resolved_title`이지만 anchor가 약한 케이스
5. `unresolved_title`, `multi_work`, `adjacent_relevant`, `trope_discussion`, `author_talk` 같은 경계 케이스
6. 비관련 판정이지만 원문에 작품/작가/캐릭터 단서가 있는 케이스
7. 정상군 대조 샘플

## 샘플링 단계

20k 이상 대량 run에서 300건 정성 리뷰는 품질 승인이 아니라 오류 유형 발견용 1차 패킷이다. 최종 품질 판단은 위험군 집중 샘플, 계층 샘플, 재처리 비교 샘플을 나눠서 본다.

- 1차 오류 발견: 위험군 중심 300건 이상
- 2차 커버리지 확인: 주요 bucket별 최소 표본 확보
  - 검색 저하
  - 검색 정상 대조군
  - slang 후보
  - slang 미저장/차단 후보
  - resolved 저근거
  - unresolved/multi_work
  - relevant_without_official_title
  - non-relevant false negative 의심군
- 3차 재처리 검증: 개선 코드/검색 안정화 후 같은 post id를 재처리해 판정 변화 비교
- 승인 기준: 각 bucket의 `REPROCESS/REJECT/HOLD` 비중, DB 오염 위험, false negative 재발 여부를 같이 본다.

## 전문가 역할

- 검색 품질 리뷰어: 검색 근거가 충분한지, 검색 장애가 판단에 영향을 줬는지 본다.
- slang/커뮤니티 용례 리뷰어: 후보 term이 실제 약칭, 별칭, 밈, 오타, 문장 조각, 일반어 중 무엇인지 판정한다.
- LLM 판정 리뷰어: 모델 이유와 최종 필드가 일치하는지, 과잉 추론이 있는지 본다.
- 최종 조정자: 리뷰어 불일치를 정리하고 최종 판정을 확정한다.

## 판정 Rubric

- 검색 근거 충분성: `1..5`
  - `5`: 검색/원문 근거만으로 판단 가능
  - `3`: 일부 근거는 있으나 추가 확인 필요
  - `1`: 검색 결과가 비었거나 엉뚱함
- LLM 판단 정합성: `1..5`
  - `5`: 근거와 결론이 일관됨
  - `3`: 결론은 가능하나 설명이 약함
  - `1`: 근거와 결론이 불일치
- slang 후보 라벨:
  - `confirmed_alias`: 실제 약칭/별칭으로 반영 가능
  - `pending_alias`: 가능성 있으나 추가 표본 필요
  - `secondary_reference`: 주변 언급, 저장 보류
  - `comparison_only`: 비교 대상으로만 등장
  - `noise`: 문장 조각, 일반어, 오염
  - `not_applicable`: slang 판단 대상 아님
- DB 반영 위험: `low | medium | high | not_applicable`
- 처리 판정:
  - `ACCEPT`: 현재 결과 승인
  - `HOLD`: DB 반영 보류
  - `RESEARCH`: 검색 안정화 후 재검색
  - `REPROCESS`: 같은 입력 재처리 필요
  - `REJECT`: 오염/오판으로 폐기

## 합의 방식

- 기본은 2인 독립 리뷰다.
- 두 리뷰어가 같은 최종 판정을 내리면 확정한다.
- 불일치 시 최종 조정자가 결정한다.
- 검색 flag가 있으면 보수적으로 `RESEARCH` 또는 `REPROCESS`를 우선 고려한다.
- slang DB 오염 가능성이 있으면 `HOLD`를 우선한다.
- 실제 약칭 가능성이 높지만 근거가 약하면 `pending_alias`로 분리한다.
- DB 반영 최종 결정은 LLM 단독 판단으로 확정하지 않는다.

## 리뷰 패킷 생성

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 300 --per-bucket 40
```

계층 샘플과 정상 대조군을 같이 넣는 확대 패킷:

```powershell
.venv312\Scripts\python.exe tools\build_llm_judgment_review_packet.py --run-id 20260423_170321_250907 --limit 1000 --per-bucket 80 --strategy stratified --control-count 120
```

기본 입력:

- checkpoint: `out/expert_result_<RUN_ID>_checkpoint.jsonl`
- run audit: `out/run_audit_<RUN_ID>.json`
- slang DB: `slang_db/slang_db.json`

기본 출력:

- `out/llm_judgment_reviews/llm_judgment_review_<RUN_ID>_<timestamp>.jsonl`
- `out/llm_judgment_reviews/llm_judgment_review_<RUN_ID>_<timestamp>.md`

패킷에는 원문, 댓글, 모델 최종 판정, reason, risk tags, sample bucket, risk score, worker/run audit 맥락, slang DB 맥락, 전문가 판정 입력란이 들어간다.

## 리뷰 배치 요약 템플릿

```markdown
## YYYY-MM-DD - Qualitative Review Batch

- 관련 run id:
- 대상 범위:
- 샘플링 기준:
- 리뷰어:
- 전체 판정: GO | REVIEW | NO-GO
- 검토 케이스 수:
- ACCEPT:
- HOLD:
- RESEARCH:
- REPROCESS:
- REJECT:
- 주요 발견:
- 검색 품질 이슈:
- slang DB 반영 후보:
- 보류 후보:
- 재처리 대상:
- 남은 위험:
- 다음 작업:
```

## 현재 20k Run 적용 상태

- 관련 run id: `20260423_170321_250907`
- 상태: REVIEW
- 이유: 검색 shard 장애가 섞인 baseline이라 단순 랜덤 표본으로는 위험 케이스를 놓칠 수 있음
- 우선 리뷰: 검색 저하 + slang 후보, resolved title 저근거, `unclear_canonical_alias` 차단 후보, non-relevant 경계
- 한계: 현재 checkpoint에는 최종 결과는 충분하지만 raw search snippet, used evidence URL, executed query별 상태가 제한적이다.
- 다음 run 개선: `search_health_flags`, `used_evidence_urls`, `raw/filtered search preview`, `executed_queries`, `degraded_queries`를 checkpoint에 직접 저장한다.
