from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from src.llm_batch.ledger.publication_commit import (
    build_publication_scope_id,
    compute_publication_decision_commit,
)
from src.llm_batch.ledger.publication_finalizer import (
    PublicationFinalizationError,
    PublicationFinalizer,
)
from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    SemanticPublicationState,
    apply_publish_contract,
    evaluate_publish_contract,
)


_PUBLIC_TITLE_KEYS = ("official_title", "official_novel_title", "resolved_title")
_PUBLIC_URL_KEYS = ("heretic_url", "official_url", "resolved_url")


def _fixture_coordinates(seed: str) -> tuple[int, str, str]:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    post_id = int(digest[:8], 16) + 1
    title = f"fixture-work-{digest[8:20]}"
    url = f"https://example.invalid/work/{digest[20:36]}"
    return post_id, title, url


def _state_and_evidence(
    seed: str,
    *,
    semantic_hold: bool,
) -> tuple[GroundingState, list[EvidenceRecord]]:
    post_id, title, url = _fixture_coordinates(seed)
    semantic = SemanticPublicationState(
        evidence_status="conflict" if semantic_hold else "sufficient",
        media_domain_class="novel_work",
        primary_work_status="unique",
    )
    state = GroundingState(
        post_id=post_id,
        candidate_title=title,
        candidate_url=url,
        source=f"fixture-source-{hashlib.sha256(seed.encode()).hexdigest()[-8:]}",
        official_title_exists=True,
        row_discusses_work_as_work=True,
        title_resolution_state="resolved",
        work_resolution="resolved",
        discussion_type="review",
        scope=ScopeState(
            scope_kind="current_work",
            confidence="high",
            direct_bridge_sources=("fixture_body", "fixture_official_detail"),
        ),
        semantic_publication=semantic,
    )
    evidence = [
        EvidenceRecord(
            kind="direct_current_work",
            strength="strong",
            source_path_or_snippet=url,
            supports_publish=True,
            reason_code="fixture_direct_current_work",
            candidate_title=title,
            candidate_url=url,
            title_url_match=True,
        )
    ]
    return state, evidence


def _identity(seed: str) -> dict:
    _, title, url = _fixture_coordinates(seed)
    return {
        "official_title": f"{title}-pre-gate",
        "official_novel_title": f"{title}-pre-gate",
        "resolved_title": f"{title}-pre-gate",
        "heretic_url": f"{url}?pre_gate=1",
        "official_url": f"{url}?pre_gate=1",
        "resolved_url": f"{url}?pre_gate=1",
        "novel_identity": {
            "official_title": f"{title}-pre-gate",
            "official_url": f"{url}?pre_gate=1",
            "resolved_title": f"{title}-pre-gate",
            "resolved_url": f"{url}?pre_gate=1",
            "heretic_url": f"{url}?pre_gate=1",
            "fixture_metadata": {"nested": [seed]},
        },
        "candidate_ledger": {"fixture_metadata": {"nested": [seed]}},
        "fixture_metadata": {"nested": [{"seed": seed}]},
        "is_relevant": True,
    }


def _result(seed: str, identity: dict) -> dict:
    post_id, title, _ = _fixture_coordinates(seed)
    return {
        "gallery_id": f"fixture-gallery-{hashlib.sha256(seed.encode()).hexdigest()[:8]}",
        "post_id": post_id,
        "title": f"{title} fixture row",
        "post_author": "fixture-author",
        "created_at": "2000-01-01T00:00:00Z",
        "url": f"https://example.invalid/post/{post_id}",
        "content": [f"fixture-content-{seed}"],
        "content_blocks": [],
        "comments": [],
        "comment_metadata": {},
        "analysis_result": {"identity": identity},
        "run_meta": {
            "run_id": f"attempt-local-{seed}",
            "fixture_stable_field": hashlib.sha256(seed.encode()).hexdigest(),
        },
    }


def _public_projection(identity: dict) -> dict:
    novel = identity.get("novel_identity")
    novel = novel if isinstance(novel, dict) else {}
    return {
        f"{prefix}.{key}": {
            "present": key in source,
            "value": source.get(key) if key in source else None,
        }
        for prefix, source in (("identity", identity), ("novel_identity", novel))
        for key in (*_PUBLIC_TITLE_KEYS, *_PUBLIC_URL_KEYS)
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class _FalseyEvidence:
    def __init__(self, records: list[EvidenceRecord]) -> None:
        self._records = records

    def __bool__(self) -> bool:
        return False

    def __iter__(self):
        return iter(self._records)


class PublicationFinalizerGoldenEquivalenceTest(unittest.TestCase):
    def _assert_golden_equivalence(self, seed: str, *, semantic_hold: bool) -> None:
        state, evidence = _state_and_evidence(seed, semantic_hold=semantic_hold)
        original = _identity(seed)
        original_snapshot = deepcopy(original)

        legacy_contract = evaluate_publish_contract(state, evidence)
        legacy_identity = deepcopy(original)
        apply_publish_contract(legacy_identity, legacy_contract)

        finalizer = PublicationFinalizer()
        facade_contract = finalizer.evaluate(state, iter(evidence))
        facade_identity = finalizer.apply(original, facade_contract)

        self.assertEqual(original_snapshot, original)
        self.assertEqual(legacy_contract.to_dict(), facade_contract.to_dict())
        self.assertEqual(_canonical_bytes(legacy_identity), _canonical_bytes(facade_identity))
        self.assertEqual(
            _public_projection(legacy_identity),
            _public_projection(facade_identity),
        )

        legacy_result = _result(seed, legacy_identity)
        facade_result = _result(seed, facade_identity)
        self.assertEqual(_canonical_bytes(legacy_result), _canonical_bytes(facade_result))

        post_id, _, _ = _fixture_coordinates(seed)
        scope = build_publication_scope_id(
            input_file_sha256=hashlib.sha256(f"input-{seed}".encode()).hexdigest(),
            post_ids=[post_id],
            config_hash=hashlib.sha256(f"config-{seed}".encode()).hexdigest(),
        )
        attempt_run_id = f"attempt-{hashlib.sha256(seed.encode()).hexdigest()[-12:]}"
        legacy_receipt = compute_publication_decision_commit(
            legacy_result,
            publication_scope_id=scope,
            attempt_run_id=attempt_run_id,
            input_index=1,
            post_id=post_id,
        )
        facade_receipt = compute_publication_decision_commit(
            facade_result,
            publication_scope_id=scope,
            attempt_run_id=attempt_run_id,
            input_index=1,
            post_id=post_id,
        )

        for field in (
            "decision_id",
            "input_sha256",
            "decision_sha256",
            "public_projection_sha256",
            "stable_result_sha256",
            "result_sha256",
            "commit_sha256",
        ):
            self.assertEqual(
                getattr(legacy_receipt, field),
                getattr(facade_receipt, field),
                field,
            )
        for field in (
            "schema_version",
            "owner",
            "commit_index",
            "outcome",
            "publish_allowed",
            "contract_version",
            "contract_input_fingerprint",
        ):
            self.assertEqual(
                getattr(legacy_receipt, field),
                getattr(facade_receipt, field),
                field,
            )

        for path in (
            ("promotion_decision", "reason_codes"),
            ("publish_contract_trace", "reason_codes"),
            ("candidate_ledger", "promotion_decision", "reason_codes"),
            ("candidate_ledger", "publish_contract_trace", "reason_codes"),
        ):
            legacy_value = legacy_identity
            facade_value = facade_identity
            for key in path:
                legacy_value = legacy_value[key]
                facade_value = facade_value[key]
            self.assertEqual(legacy_value, facade_value, ".".join(path))

    def test_publish_path_matches_direct_legacy_contract_and_commit(self) -> None:
        self._assert_golden_equivalence("publish-golden", semantic_hold=False)

    def test_hold_path_matches_direct_legacy_contract_and_commit(self) -> None:
        self._assert_golden_equivalence("hold-golden", semantic_hold=True)

    def test_finalize_is_deterministic_and_returns_independent_copies(self) -> None:
        seed = "copy-on-write"
        state, evidence = _state_and_evidence(seed, semantic_hold=False)
        original = _identity(seed)
        original_snapshot = deepcopy(original)
        finalizer = PublicationFinalizer()

        first = finalizer.finalize(original, state, evidence)
        second = finalizer.finalize(original, state, evidence)

        self.assertEqual(_canonical_bytes(first), _canonical_bytes(second))
        self.assertIsNot(first, second)
        self.assertIsNot(first["fixture_metadata"], original["fixture_metadata"])
        first["fixture_metadata"]["nested"][0]["seed"] = "mutated-copy"
        self.assertEqual(original_snapshot, original)
        self.assertNotEqual(first, second)

    def test_falsey_custom_evidence_preserves_legacy_truthiness_semantics(self) -> None:
        state, evidence = _state_and_evidence("falsey-evidence", semantic_hold=False)

        legacy = evaluate_publish_contract(state, _FalseyEvidence(evidence))
        facade = PublicationFinalizer().evaluate(state, _FalseyEvidence(evidence))

        self.assertEqual(legacy.to_dict(), facade.to_dict())
        self.assertFalse(legacy.decision.publish_allowed)


class PublicationFinalizerFailClosedTest(unittest.TestCase):
    def test_evaluation_failure_returns_no_fallback_contract(self) -> None:
        with self.assertRaisesRegex(
            PublicationFinalizationError,
            "evaluation failed",
        ):
            PublicationFinalizer().evaluate(object())  # type: ignore[arg-type]

    def test_partial_apply_failure_cannot_mutate_source_identity(self) -> None:
        seed = "partial-apply-failure"
        state, evidence = _state_and_evidence(seed, semantic_hold=False)
        contract = evaluate_publish_contract(state, evidence)
        original = _identity(seed)
        original_snapshot = deepcopy(original)

        def _partial_failure(identity: dict, _contract: object) -> None:
            identity["novel_identity"]["official_title"] = "partial-mutation"
            raise ValueError("synthetic apply failure")

        with patch(
            "src.llm_batch.ledger.publication_finalizer.apply_publish_contract",
            side_effect=_partial_failure,
        ):
            with self.assertRaisesRegex(
                PublicationFinalizationError,
                "application failed",
            ):
                PublicationFinalizer().apply(original, contract)

        self.assertEqual(original_snapshot, original)

    def test_non_mapping_identity_fails_before_apply(self) -> None:
        seed = "non-mapping"
        state, evidence = _state_and_evidence(seed, semantic_hold=False)
        contract = evaluate_publish_contract(state, evidence)
        with patch(
            "src.llm_batch.ledger.publication_finalizer.apply_publish_contract"
        ) as delegated_apply:
            with self.assertRaisesRegex(
                PublicationFinalizationError,
                "must be a mapping",
            ):
                PublicationFinalizer().apply([], contract)  # type: ignore[arg-type]
        delegated_apply.assert_not_called()


if __name__ == "__main__":
    unittest.main()
