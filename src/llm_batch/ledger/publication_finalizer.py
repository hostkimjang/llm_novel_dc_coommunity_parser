from __future__ import annotations

"""Copy-on-write façade for the existing publication contract boundary.

This module intentionally owns no publication semantics and no durable write.
It only delegates contract evaluation and application to ``promotion_gate`` so
callers can migrate orchestration without changing the authoritative result.
"""

from copy import deepcopy
from typing import Any, Iterable, Mapping, MutableMapping, Optional

from ..promotion_gate import (
    EvidenceRecord,
    GroundingState,
    PublishContract,
    apply_publish_contract,
    evaluate_publish_contract,
)


class PublicationFinalizationError(RuntimeError):
    """Raised when the façade cannot produce a complete copied result."""


class PublicationFinalizer:
    """Stateless compatibility boundary around the legacy contract functions.

    ``apply`` never mutates the supplied identity.  A fully independent copy is
    returned only after the authoritative apply function completes, so a
    partial failure cannot leak a partially finalized identity to the caller.
    """

    __slots__ = ()

    def evaluate(
        self,
        state: GroundingState,
        evidence: Optional[Iterable[EvidenceRecord]] = None,
        *,
        post_gate_context: Optional[Mapping[str, Any]] = None,
    ) -> PublishContract:
        try:
            return evaluate_publish_contract(
                state,
                evidence,
                post_gate_context=post_gate_context,
            )
        except Exception as exc:
            raise PublicationFinalizationError(
                "publication contract evaluation failed"
            ) from exc

    def apply(
        self,
        identity: Mapping[str, Any],
        contract: PublishContract,
    ) -> MutableMapping[str, Any]:
        if not isinstance(identity, Mapping):
            raise PublicationFinalizationError(
                "publication identity must be a mapping"
            )
        try:
            copied_identity: MutableMapping[str, Any] = deepcopy(dict(identity))
        except Exception as exc:
            raise PublicationFinalizationError(
                "publication identity copy failed"
            ) from exc

        try:
            applied_identity = apply_publish_contract(copied_identity, contract)
        except Exception as exc:
            raise PublicationFinalizationError(
                "publication contract application failed"
            ) from exc
        if applied_identity is not copied_identity:
            raise PublicationFinalizationError(
                "publication contract application replaced its copied identity"
            )
        return copied_identity

    def finalize(
        self,
        identity: Mapping[str, Any],
        state: GroundingState,
        evidence: Optional[Iterable[EvidenceRecord]] = None,
        *,
        post_gate_context: Optional[Mapping[str, Any]] = None,
    ) -> MutableMapping[str, Any]:
        contract = self.evaluate(
            state,
            evidence,
            post_gate_context=post_gate_context,
        )
        return self.apply(identity, contract)


__all__ = [
    "PublicationFinalizationError",
    "PublicationFinalizer",
]
