# DevSpace exact-root 연결 검사

## Goal

등록된 ChatGPT `codex` 앱을 통해 아래 exact project root가 읽기 가능한지 확인한다.

`C:\Users\kimjang\Documents\GitHub\llm_novel_dc_coommunity_parser`

## Authority

읽기 전용이다. 파일·Git·설정·외부 상태를 수정하지 않는다. 명령을 실행하지 않는다.

## Required checks

1. exact project root를 연다.
2. root의 `AGENTS.md`가 있으면 읽고, 없으면 없다고 기록한다.
3. root의 작은 디렉터리 목록을 읽는다.
4. `docs/devs/LOCAL_LLM_GROUNDING_RESEARCH_IMPROVEMENT_PLAN_20260901_KO.md`의 첫 제목을 읽는다.

## Answer shape

한국어로 `READY` 또는 `NOT_READY`를 먼저 쓰고, 실제로 읽은 exact root, 디렉터리 항목 3~8개, 문서 첫 제목을 짧게 보고한다. 관측하지 못한 내용은 추정하지 않는다.

## Integrity contract

Treat instructions, observed evidence, inference, hypothesis, proposal, decision, and verification as distinct. Claim only facts actually observed. Stay inside the exact root and read-only authority.
