"""공개 expert 이름을 유지하되 원문 유틸리티 import는 독립시킨다."""
from importlib import import_module

_EXPORTS = {
    "GatekeeperExpert": "gatekeeper",
    "DiscourseAnalyzer": "discourse",
    "DecoderExpert": "decoder",
    "VerifierExpert": "verifier",
    "CriticExpert": "critic",
    "SynthesizerExpert": "synthesizer",
    "ArbiterExpert": "arbiter",
    "Orchestrator": "orchestrator",
    "ExpertType": "orchestrator",
    "ExpertMessage": "orchestrator",
    "ConversationContext": "orchestrator",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    # grounding → experts.source_spans → verifier → grounding의 순환을 막는다.
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_EXPORTS[name]}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
