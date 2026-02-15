# -*- coding: utf-8 -*-
"""
레거시 호환성을 위한 리다이렉트 모듈.

실제 프롬프트는 src/llm_batch/prompts/pipeline_prompts.py에 있습니다.
이 파일은 기존 코드의 import 호환성을 위해 유지됩니다.

예: from llm_batch.llm.prompt import IDENTIFY_PROMPT
"""

from ..prompts.pipeline_prompts import (
    IDENTIFY_PROMPT,
    SYSTEM_PROMPT,
    ANALYZE_PROMPT,
    SEARCH_PLANNER_PROMPT,
    HYPOTHESIS_PROMPT,
    VERIFICATION_PROMPT,
)

__all__ = [
    "IDENTIFY_PROMPT",
    "SYSTEM_PROMPT",
    "ANALYZE_PROMPT",
    "SEARCH_PLANNER_PROMPT",
    "HYPOTHESIS_PROMPT",
    "VERIFICATION_PROMPT",
]

