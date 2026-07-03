# Loop365 11713222 blind/source-native 검증

## 결론

`11713222`는 `잘생기면 편해지는 인방 생활` publish가 정당하다. 기존 golden expected `잘생기면 인생이 편하다`는 댓글의 전작 언급을 public target으로 잘못 둔 label drift다.

## 근거

- 본문은 `잘생인방보는데 ...`로 현재 작품을 직접 말한다.
- 댓글 `전작도 잘생인편으로 ...`, `잘생인편 안봐서 ...`는 이전 작품을 회상하는 mentioned-work 문맥이다.
- Loop364 runtime row는 `잘생인방 -> 잘생기면 편해지는 인방 생활`을 primary, `잘생인편 -> 잘생기면 인생이 편하다`를 mentioned-work 후보로 보존했다.

## 조치

- 코드 변경 없음.
- R1 하드코딩 cue 리스트 확장 없음.
- `golden_manifest.json`의 `11713222` expected를 `잘생기면 편해지는 인방 생활`로 교정.
- 재감사 결과 expected-answer pass는 `13/18 -> 14/18`로 개선됐지만 `canary_semantic_gate=NO-GO`는 유지.

Gate: search recovery `P0 / OPEN`, semantic `REVIEW-LOCKED`, `full_scan_approval=false`, goal `ACTIVE / NOT_COMPLETE`.
