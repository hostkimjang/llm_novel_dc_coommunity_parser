# 2,712건 전수 판정 기반 구현 전 개선 기회 보고서

## Executive Summary

- **최우선은 최종 공개 게이트다.** pipeline이 공개한 263건 중 35건(13.3%)은 최종적으로 `KEEP`이 아니라 `REMOVE 8`, `CORRECT 15`, `HOLD 12`가 필요했다. 내부 형식 정합성만 확인하지 말고 evidence 상태·주작품 관계·다중작품·매체 도메인을 공개 직전에 다시 결속해야 한다.
- **정답 회수는 공개 차단과 별도 lane으로 개선해야 한다.** 정답 제목 누락은 339건이며, explicit OCR title 107건, title candidate 보유 249건, high-confidence 290건이다. 직접 근거가 하나의 작품으로 수렴하는 행부터 단계적으로 복구해야 한다.
- **현재 자동 의미 재검토 라우터는 구조 오류가 없는 의미 오류를 많이 놓친다.** 고위험 판정 872건 중 678건(77.8%)에 `manual_semantic_review_required`가 없었다. “구조 모순 없음”을 “의미상 안전”으로 읽지 않도록 라우팅 신호를 확장해야 한다.
- **비용 최적화는 마지막에 좁게 시작해야 한다.** 검증된 no-title 정답은 1,580건이지만, 이미지·OCR·후보·댓글이 모두 없는 초저위험 188건만 초기 early-route canary로 삼는 것이 안전하다.

이 보고서는 구현 전에 무엇을 어떤 순서로 바꿀지 정하기 위한 분석이다. 아래 “개선 후”는 실제 측정 결과가 아니라 2,712건 정본에서 도출한 기대 동작이며, 같은 입력·모델·검색 상태의 paired BEFORE/AFTER로 입증되기 전에는 운영 효과로 선언하지 않는다.

## 현재 결과는 공개 과신과 정답 누락이 동시에 존재한다

| 관측 모집단 | 건수 | 비율/비고 |
| --- | ---: | --- |
| pipeline 공개행 | 263 | 전체 2,712건의 9.7% |
| 공개 후 개입 필요 | 35 | 공개행의 13.3%; `REMOVE 8`, `CORRECT 15`, `HOLD 12` |
| 정답 제목 누락 | 339 | 전체의 12.5% |
| 비소설·wrong-work | 108 | `FP_NONNOVEL 72` + `WRONG_WORK 36` |
| 근거 충돌·부족·다중작품 | 418 | `25 + 302 + 91`; 단일 제목 확정 금지 |
| 대시보드 제목 문자열 불일치 | 7 | 6건 정정, 1건 보류 |
| 자동 재검토 플래그 누락 고위험 | 678 | 고위험 872건의 77.8% |
| 초기 안전 라우팅 후보 | 188 | 이미지·OCR·후보·댓글이 모두 없는 검증 음성 |

각 모집단은 서로 겹칠 수 있다. 예를 들어 공개 후 개입 35건은 wrong-work·비소설·근거 보류·제목 오표시에도 포함되므로 건수를 합산해 전체 개선량으로 해석하면 안 된다.

## P0-1. 최종 공개 게이트를 의미 근거에 결속한다

**관측 근거:** 공개 263건 중 35건이 유지되지 않았다. 그중 20건은 제거 또는 보류가 필요했고, 15건은 다른 제목으로 정정해야 했다.

| 구분 | 개선 전 관측 | 개선 후 기대 동작 |
| --- | --- | --- |
| 공개 조건 | 선택된 제목과 내부 publication 구조가 맞으면 공개될 수 있음 | `evidence_status=sufficient`, 단일 primary work, novel media domain, 검색·OCR 충돌 없음이 모두 참일 때만 공개 |
| 충돌 처리 | 충돌 issue가 있어도 다른 경로에서 publish가 남을 수 있음 | 최종 sealed decision에서 `HOLD`; title과 URL을 함께 비움 |
| 결과 기록 | 후보·중간 판정·최종 화면이 서로 다른 문자열을 가질 수 있음 | 최종 gate receipt만 dashboard public projection을 기록 |

예시 `11718099`는 제목·인물 맥락이 `빌어먹을 환생`을 가리키지만 OCR에는 별개 작품 `불어먹을 황제`가 있었다. 개선 전에는 `빌어먹을 환생`이 공개됐지만, 개선 후에는 evidence conflict가 해소될 때까지 `HOLD`가 되어야 한다.

**검증 게이트:** frozen replay의 공개 후 개입 35건은 최종 정본의 `REMOVE/CORRECT/HOLD`와 일치하고, 기존 `PASS 230`에는 hard regression이 없어야 한다.

## P0-2. 직접 OCR·공식 근거를 이용한 정답 회수 lane을 분리한다

**관측 근거:** `FN_TITLE_MISSING` 339건은 전부 `recommended_title`이 존재한다. 그중 107건은 explicit OCR title이 있고, 249건은 title candidate가 있으며, 290건은 reviewer confidence가 high다.

| 구분 | 개선 전 관측 | 개선 후 기대 동작 |
| --- | --- | --- |
| 직접 OCR title | 다른 LLM 후보가 함께 있으면 candidate-only/null로 남을 수 있음 | OCR title+작가+플랫폼/회차가 일치하고 경쟁 근거가 없으면 direct anchor로 잠금 |
| 공식 detail 후보 | candidate에 보존되지만 public title로 승격되지 않음 | 본문·댓글의 specific-work target과 공식 detail이 같은 작품이면 canonical title로 승격 |
| 불확실 후보 | 정답 회수와 보수적 HOLD가 같은 경로에서 충돌 | direct-evidence recovery와 ambiguous-evidence HOLD를 별도 상태로 유지 |

예시 `11718117`은 OCR 하단에 `아카데미의 피해자`, 작가 `양파랑`, 카카오페이지 회차가 직접 있었지만 pipeline title은 null이었다. 개선 후에는 경쟁 direct anchor가 없는 경우 `아카데미의 피해자`로 정정되어야 한다.

**검증 순서:** 먼저 explicit OCR 107건을 P0 recovery set으로 사용하고, 다음으로 candidate-no-OCR 행을 alias·인물·댓글 corroboration 조건으로 확장한다. `FP_NONNOVEL 72`와 `WRONG_WORK 36`의 증가가 0이어야 한다.

## P0-3. 비소설 매체를 title-like 문자열보다 먼저 격리한다

**관측 근거:** 비소설 오채택은 72건이며 54건에 이미지가 있었다. OCR이나 공식-looking URL이 있어도 뉴스·프로그램·플랫폼 공지·게임·웹툰 등은 웹소설 작품 근거가 아니다.

| 구분 | 개선 전 관측 | 개선 후 기대 동작 |
| --- | --- | --- |
| 일반어 매칭 | `코로나`, `우리나라`, `세계` 같은 표면이 작품 후보와 연결됨 | 현실 뉴스·일상·프로그램이면 `media_domain_class != novel_work`로 후보 승격 차단 |
| 이미지/OCR | title-like 문자열 자체를 작품 단서로 취급할 수 있음 | 이미지 page type과 source intent를 먼저 판정하고 공지·뉴스·게임 UI를 quarantine |
| cross-media | 만화·게임·웹툰 언급이 동명 소설로 전환될 수 있음 | 현재 토론 대상과 원작/각색 관계가 명시되지 않으면 소설 title을 공개하지 않음 |

예시 `11714881`은 연합뉴스의 니파바이러스 보도였지만 일반어 `코로나`가 `코로나 시대에 흡혈귀로 살아남기` 후보와 연결됐다. 개선 후에는 뉴스 page type이 먼저 확정되어 작품 후보가 대시보드로 올라가지 않아야 한다.

**검증 게이트:** frozen `FP_NONNOVEL 72` 전부가 novel public projection을 만들지 않아야 하며, 실제 소설 OCR title을 가진 positive control은 유지해야 한다.

## P1-1. primary work·언급작·이전작·비교작 관계를 명시한다

**관측 근거:** wrong-work 36건과 multiwork hold 91건이 있다. wrong-work 중 15건, multiwork 중 2건은 실제 publish 상태였다.

| 구분 | 개선 전 관측 | 개선 후 기대 동작 |
| --- | --- | --- |
| 작가의 이전작과 신작 | 제목에서 가장 강한 이전작 표면이 선택될 수 있음 | `previous_work`는 author reference로 보존하고 현재 신작을 `primary`로 분리 |
| 비교·추천 글 | 여러 작품 중 점수가 높은 하나가 선택될 수 있음 | `comparison/recommendation` role과 `MULTIWORK` 상태를 부여하고 단일 공개 금지 |
| 관용구·우연 일치 | 문장 표면이 작품명과 겹치면 wrong-work가 됨 | 등장인물·회차·공식 URL 등 specific-work target이 없는 문자열 일치는 감점 |

예시 `11718051`은 `양치기 마법사` 작가의 신작을 논했지만 이전작이 공개됐다. 개선 후에는 이전작을 author reference로 내리고 신작 `몰락민족의 천재 기사`를 primary work로 잡아야 한다. `11708442`처럼 세 작품 정주행을 비교한 글은 어느 하나도 공개하지 않고 `MULTIWORK/HOLD`로 남아야 한다.

**검증 게이트:** wrong-work 36건은 정본의 정정·제거·보류와 일치하고, multiwork 91건은 단일 public title을 만들지 않아야 한다.

## P1-2. 의미 재검토 라우터의 coverage를 구조 모순 밖으로 넓힌다

**관측 근거:** 고위험 872건 중 678건은 자동 의미 재검토 플래그가 없었다. 세부적으로 FN 339건 중 234건, FP 72건 중 43건, wrong-work 36건 중 18건, evidence-insufficient 302건 중 283건이 미플래그였다.

다음 신호 중 하나라도 있으면 구조가 정상이어도 semantic review queue로 보내는 것이 타당하다.

- explicit OCR title과 final title/null의 불일치
- candidate에는 공식 detail이 있지만 final title은 null
- title·본문·댓글이 서로 다른 작품을 지시
- author/character/previous-work 표면만 있고 current primary target이 없음
- news/program/game/comic page type과 novel candidate가 함께 존재
- `vs`, 비교, 추천, 작품 나열 등 multiwork signal
- search degraded 상태에서 publish 또는 canonical correction 시도

예시 `11718117`은 자동 판정이 `NONPUBLISH_NO_STRUCTURAL_CONTRADICTION`이고 review flag도 false였지만 직접 OCR 정답을 놓쳤다. `11718051`도 `PIPELINE_PUBLISH_NO_STRUCTURAL_CONTRADICTION`이었지만 실제로는 이전작을 신작으로 오인한 wrong-work였다.

**검증 게이트:** frozen high-risk recall을 우선 측정하고, `PASS 230`과 검증된 `NOT_APPLICABLE 1,580`의 불필요 재검토율·결과 drift를 함께 제한한다.

## P1-3. 작품 ID와 공개 정식명 렌더링을 분리한다

**관측 근거:** 대시보드 제목 문자열 불일치는 7건이다. 공백·조사 중복·OCR 오타·괄호 추정문·브래킷 라벨이 public title에 섞였다.

예시 `11682775`는 `여자가 되어서 되어라도 복수한다`로 공개됐지만 정식명은 `여자가 되어서라도 복수한다`다. 개선 후에는 작품을 canonical work ID로 선택하고, 대시보드 문자열은 검증된 official title registry에서 한 번만 렌더링해야 한다. OCR 문구·약칭·브래킷 라벨은 alias/evidence로만 보존한다.

**검증 게이트:** mismatch 7건은 canonical title 6건과 추정문 제거 HOLD 1건으로 정확히 재현하고, 동일 작품의 약어·공백 변형이 public identity를 새로 만들지 않아야 한다.

## P1-4. HOLD를 targeted evidence recovery 상태로 만든다

**관측 근거:** 근거 충돌·부족·다중작품 418건은 단일 제목을 확정하면 안 되는 모집단이다. 이 가운데 10건은 pipeline publish 상태였다.

개선 후에는 `HOLD`를 단순 null이 아니라 다음 상태와 함께 보존한다.

- 부족한 근거 종류: official title, alias relation, character-work link, page type, current-work relation
- 경쟁 후보와 충돌 필드
- 다음 검색 쿼리의 목적과 허용 횟수
- recovery 성공 시 canonical title, 실패 시 계속 HOLD하는 terminal rule

예시 `11718096`은 `기계공주`와 공식 detail 후보가 있지만 alias 신뢰도가 Medium이고 직접 title이 없다. 개선 후에는 alias relation과 특정 인물·작품 관계만 targeted search하고, 증명되면 정정하며 실패하면 계속 HOLD해야 한다.

**검증 게이트:** 418건에서 근거 없는 자동 승격은 0이어야 한다. search failure/degraded를 “정답 없음”과 구분하고, recovery 성공률과 잘못된 승격률을 별도로 측정한다.

## P2. 검증된 초저위험 음성부터 early route를 연다

**관측 근거:** `NOISE_CORRECT`와 `CONTEXT_ONLY_CORRECT` 중 대시보드 비대상은 1,580건이다. 그러나 이미지·댓글·후보가 있는 행을 곧바로 cheap route로 보내면 숨은 작품 단서를 놓칠 수 있다. 이미지·OCR·title candidate·댓글이 모두 없는 행은 188건이다.

예시 `11718070`은 현실 ECT 치료 잡담이고 작품 근거가 전혀 없다. 개선 후에는 초저위험 규칙이 `NO_WORK/NOT_APPLICABLE`을 제안할 수 있지만, 하나라도 이미지·OCR·후보·댓글·작품 약어 신호가 생기면 즉시 full semantic path로 fallback해야 한다.

**검증 게이트:** 먼저 188건 canary에서 public/CandidateSet 결과 drift 0을 확인한다. 그 뒤에만 범위를 넓히며, 비용·지연 개선은 fresh paired run의 실제 호출 수와 wall time으로 측정한다.

## 구현 순서는 안전 차단에서 정답 회수, 비용 최적화 순이다

1. 2,712 정본에서 P0/P1 회귀 세트를 생성한다: 공개 후 개입 35, FN 339, FP 72, wrong-work 36, multiwork 91, mismatch 7, arbitration 64, PASS 230, 검증 음성 1,580.
2. 최종 공개 hard gate와 sealed dashboard projection을 먼저 적용한다.
3. non-novel media domain과 primary/reference/multiwork 관계 판정을 결속한다.
4. direct OCR·official-detail FN recovery를 별도 lane으로 연다.
5. semantic review router coverage를 확장하고 false-review rate를 함께 측정한다.
6. canonical work ID→official title 렌더링을 적용한다.
7. targeted evidence recovery를 HOLD state에 연결한다.
8. 모든 의미 게이트 통과 뒤 초저위험 188건부터 early-route 비용 canary를 시작한다.

## BEFORE/AFTER 승인 지표

| 지표 | BEFORE | AFTER 승인 기준 |
| --- | ---: | --- |
| 공개 후 개입 필요 | 35/263 | frozen replay 0; 정본 action과 일치 |
| direct OCR 포함 FN | 107/339 | conflict 없는 direct set 정확 회수, FP/wrong-work 증가 0 |
| 비소설 오채택 | 72 | novel public projection 0 |
| wrong-work | 36 | 정본의 correct/remove/hold와 일치 |
| multiwork 단일 공개 | 91건 대상 중 publish 2 | frozen 91건 단일 publish 0 |
| dashboard mismatch | 7 | canonical 6, 추정문 HOLD 1 |
| 고위험 자동 검토 미플래그 | 678/872 | high-risk recall 상승과 false-review rate 동시 보고 |
| PASS 회귀 | 230 | hard regression 0 |
| 검증된 no-title 회귀 | 1,580 | public title 생성 0 |
| 초저위험 early-route | 188 | 결과 drift 0 뒤 실제 호출·wall time 개선 측정 |
| 교차검토 중재 행 | 64 | 최종 중재 정본과 exact match |

## Further Questions

- 339 FN 중 explicit OCR가 없는 232건을 alias·character·author·official-detail 중 어떤 근거 조합으로 분해할지 별도 labeling이 필요하다.
- HOLD 418건의 검색 복구 가능률은 search degraded가 해소된 동일 조건 rerun 전에는 추정할 수 없다.
- 현재 worktree에는 canonicalization·reference role·publication gate 관련 코드가 일부 존재하므로, 신규 기능 추가보다 active path 배선과 중복 후처리 제거가 먼저일 수 있다.
- 대시보드가 single-title만 지원할지, multiwork를 별도 표시할지 제품 계약을 확정해야 한다.

## Caveats and Assumptions

- 이 보고서는 동결 2,712건의 행별 정본에만 적용된다. 실행 중인 전체 104,502건의 오류율이나 개선률로 외삽하지 않는다.
- “AFTER”는 설계 기대값이다. 구현·실행·paired 검증은 아직 수행하지 않았다.
- 모집단은 중복되므로 개선 후보별 건수를 더하지 않는다.
- active run은 시작 시점의 코드와 상태를 사용하며, 현재 dirty worktree의 부분 구현과 동일하다고 가정하지 않는다.
- search degraded와 외부 웹 미확인 행은 확정 정답이 아니라 HOLD로 유지한다.

## 근거 산출물

- 재현 가능한 분석 노트북: [`LIVE_RUN_2712_PRE_IMPROVEMENT_ANALYSIS_20260716.ipynb`](LIVE_RUN_2712_PRE_IMPROVEMENT_ANALYSIS_20260716.ipynb)
- 최종 2,712행 정본: [`final_2712_row_adjudication_ledger.jsonl`](../../out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl)
- 최종 집계: [`final_2712_row_summary.json`](../../out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_summary.json)
- 고위험 교차검토: [`high_risk_cross_review_summary.json`](../../out/live_full_row_review_20260715_143806_848671_20260716/high_risk_cross_review_summary.json)
- 제3 중재 coverage: [`arbitration_coverage.json`](../../out/live_full_row_review_20260715_143806_848671_20260716/arbitration_coverage.json)
