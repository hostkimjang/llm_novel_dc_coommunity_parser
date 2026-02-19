# -*- coding: utf-8 -*-
"""
레거시 호환성을 위한 리다이렉트 모듈.

실제 프롬프트는 src/llm_batch/prompts/expert_prompts.py에 있습니다.
이 파일은 기존 코드의 import 호환성을 위해 유지됩니다.

예: from llm_batch.experts.prompts import GATEKEEPER_SYSTEM
"""

from ..prompts.expert_prompts import (
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
from ..prompts.prompt_router import (
    build_gatekeeper_system_prompt,
    build_decoder_system_prompt,
    build_verifier_system_prompt,
)

__all__ = [
    "GATEKEEPER_SYSTEM",
    "GATEKEEPER_PROMPT",
    "DECODER_SYSTEM",
    "DECODER_PROMPT",
    "VERIFIER_SYSTEM",
    "VERIFIER_PROMPT",
    "CRITIC_SYSTEM",
    "CRITIC_PROMPT",
    "assemble_final_output",
    "build_gatekeeper_system_prompt",
    "build_decoder_system_prompt",
    "build_verifier_system_prompt",
]
