# Loop512 wrong_work INFO_MISSING 10건 source-native 판정

이 문서는 `docs/devs/loop512_wrong_work_info_missing10_source_native_verdicts.json`의 사람용 요약이다. 새 runtime replay는 실행하지 않았고, 일부 행은 source-native 근거에 native-web 링크를 보강했다. `ACCEPT`는 regression count 제외 후보일 뿐 full_scan approval이 아니다.

## 요약

- 대상: `wrong_work_title_flip` INFO_MISSING `10`건
- 결과: `ACCEPT 4`, `REPROCESS 6`, `HOLD 0`
- gate: `REVIEW-LOCKED`
- full_scan_approval: `false`
- 연결 summary: `out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop512_projected_loop511_after_wrong_work10_review_summary.json`

## 판정

| post_id | label | 선택 | 의미 |
| --- | --- | --- | --- |
| `11660241` | `REPROCESS` | C2 `이세계 TRPG 게임마스터` | `이티알`/TRPG/탑주 맥락이 C2를 지지하고 after C1은 wrong-work flip |
| `11663554` | `ACCEPT` | C1 `전 버튜버가 하고 싶은데요` | 캐릭터 표면을 canonical title로 정리한 같은 URL 후보 |
| `11666731` | `REPROCESS` | C1 `약먹는 천재마법사` | after `약먹는 천재마사`는 typo publication |
| `11669907` | `REPROCESS` | C1 `마법 좋아좋아좋아` | `약스포)` 접두가 public title에 섞인 title cleanup 대상 |
| `11671512` | `REPROCESS` | `HOLD` | `유카리` 패러디 맥락과 promoted kingdom title이 충돌해 candidate set rebuild 필요 |
| `11681152` | `ACCEPT` | C1 `[포켓몬] 체육관 챌린지에서 살아남기` | bracket canonical title과 URL이 붙은 after 정리 |
| `11694041` | `REPROCESS` | `HOLD` | 현재 C1/C2가 official title을 정확히 담지 못해 후보셋 재구축 필요 |
| `11698870` | `REPROCESS` | C1 `인간실격` | 일본 고전 문맥을 같은 표면의 웹소설로 과승격 |
| `11703631` | `ACCEPT` | C2 `이블 파티 대 헌터` | `이블파티` 직접 표면과 문피아 official detail이 after C2를 지지 |
| `11703674` | `ACCEPT` | C2 `아카데미의 마피아가 되었다 - 웹소설` | 현재 논의작은 아카마피아이고 C1 도굴꾼은 작가 과거작 비교 후보 |

## 다음

- 이 verdict를 반영한 residual action queue는 `docs/devs/loop512_after_wrong_work10_review_adjusted_residual111_action_queue.json/.md`다.
- 남은 `source_native_or_blind_review_required 53`은 단건 반복이 아니라 N건 배치로 처리한다.
- 완료 기준은 계속 `full375 collateral GO + full_scan 경로 정의`다.
