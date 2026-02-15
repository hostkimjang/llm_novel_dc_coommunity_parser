# -*- coding: utf-8 -*-
"""
프롬프트 모듈 패키지

구조:
- pipeline_prompts.py: main.py용 (기존 단일 LLM 파이프라인)
- expert_prompts.py: expert_main.py용 (Agentic 멀티 전문가 시스템)
"""

from .pipeline_prompts import (
    IDENTIFY_PROMPT,
    SYSTEM_PROMPT,
    ANALYZE_PROMPT,
    SEARCH_PLANNER_PROMPT,
    HYPOTHESIS_PROMPT,
    VERIFICATION_PROMPT,
)

from .expert_prompts import (
    GATEKEEPER_SYSTEM,
    GATEKEEPER_PROMPT,
    DECODER_SYSTEM,
    DECODER_PROMPT,
    VERIFIER_SYSTEM,
    VERIFIER_PROMPT,
    CRITIC_SYSTEM,
    CRITIC_PROMPT,
    assemble_final_output,
)

__all__ = [
    # Pipeline (main.py)
    "IDENTIFY_PROMPT",
    "SYSTEM_PROMPT", 
    "ANALYZE_PROMPT",
    "SEARCH_PLANNER_PROMPT",
    "HYPOTHESIS_PROMPT",
    "VERIFICATION_PROMPT",
    # Expert (expert_main.py)
    "GATEKEEPER_SYSTEM",
    "GATEKEEPER_PROMPT",
    "DECODER_SYSTEM", 
    "DECODER_PROMPT",
    "VERIFIER_SYSTEM",
    "VERIFIER_PROMPT",
    "CRITIC_SYSTEM",
    "CRITIC_PROMPT",
    "assemble_final_output",
]
