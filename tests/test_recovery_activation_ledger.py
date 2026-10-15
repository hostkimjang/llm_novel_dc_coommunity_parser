from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import expert_main

from src.llm_batch.ledger.publication_commit import (
    PublicationCommitRegistry,
    build_publication_scope_descriptor,
    commit_publication_result,
)
from src.llm_batch.ledger.recovery_activation import (
    RECOVERY_CAPABILITY_SCOPE,
    RECOVERY_MODE,
    RecoveryActivationError,
    RecoveryActivationEvent,
    RecoveryActivationRegistry,
    RecoveryProposal,
    _create_event,
    derive_review_recovery_capability,
    extract_direct_ocr_review_proposals,
    load_or_create_recovery_activation_hmac_key,
    verify_recovery_capability,
)
from src.llm_batch.ledger.private_file import private_file_permissions_ok
from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)


def _scope_descriptor():
    return build_publication_scope_descriptor(
        input_file_sha256="a" * 64,
        post_ids=[101, 102],
        config_hash="recovery-overlay-test",
        release_fingerprint="release-test",
    )


def _hold_result(post_id: int = 101) -> dict:
    title = "검토 후보 작품"
    url = f"https://novelpia.com/novel/{post_id}"
    state = GroundingState(
        post_id=post_id,
        candidate_title=title,
        candidate_url=url,
        source="recovery_overlay_test",
        official_title_exists=False,
        row_discusses_work_as_work=False,
        title_resolution_state="unresolved_matchable",
        work_resolution="unresolved",
        discussion_type="unknown",
        scope=ScopeState(
            scope_kind="unknown",
            confidence="low",
            conflict_reason_codes=("review_only_recovery",),
        ),
    )
    contract = evaluate_publish_contract(
        state,
        [
            EvidenceRecord(
                kind="direct_ocr_review_candidate",
                strength="medium",
                source_path_or_snippet="image:0",
                supports_publish=False,
                reason_code="review_only_recovery",
                candidate_title=title,
                candidate_url=url,
            )
        ],
    )
    identity = {
        "is_relevant": True,
        "novel_identity": None,
    }
    apply_publish_contract(identity, contract)
    return {
        "gallery_id": "novel",
        "post_id": post_id,
        "title": "OCR 후보 검토",
        "content": ["본문"],
        "comments": [],
        "analysis_result": {"identity": identity},
        "run_meta": {},
    }


def _proposal(*, raw_title: str = "검토 후보 작품") -> RecoveryProposal:
    return RecoveryProposal(
        producer="direct_ocr_review_shadow",
        rule_version="direct_ocr_review_shadow_v1",
        activation_reason="conflict_free_direct_ocr_candidate",
        raw_candidate_title=raw_title,
        canonical_title="검토 후보 작품",
        candidate_url="https://novelpia.com/novel/101",
        canonical_work_id="novelpia:101",
        source_kind="direct_image_ocr",
        source_locator="image:0",
        source_payload_sha256="b" * 64,
        relation_role="primary_candidate",
        evidence_status="insufficient",
        media_domain_class="novel_work",
        primary_work_status="ambiguous",
        conflict_count=0,
        search_health="degraded",
        legacy_fallback_used=False,
        blocker_codes=("review_only", "search_degraded"),
    )


def _direct_ocr_hold_result() -> dict:
    result = _hold_result()
    identity = result["analysis_result"]["identity"]
    identity["title_candidates"] = [
        {
            "official_title": "검토 후보 작품",
            "heretic_url": None,
            "reference_role": "candidate",
        }
    ]
    identity["image_evidence_catalog"] = [
        {
            "eid": "IMG001",
            "block_index": 0,
            "ocr_text": "검토 후보 작품 · 88화 테스트 작가 SERIES",
            "visual_summary": "소설 본문과 작품명이 적힌 스크린샷",
            "explicit_work_title": "검토 후보 작품",
            "explicit_author_name": "테스트 작가",
            "evidence_type": "explicit_text",
            "title_role": "work_title",
            "promotion_eligible": True,
            "work_cues": ["검토 후보 작품", "88화"],
        }
    ]
    identity["search_health"] = {
        "status": "SEARCH_DEGRADED",
        "queries_issued": 2,
        "unrecovered_degraded": 2,
    }
    return result


class RecoveryActivationLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scope_descriptor = _scope_descriptor()
        self.publication_path = self.root / "publication.jsonl"
        self.recovery_path = self.root / "publication.recovery_activation.jsonl"
        self.publication_registry = PublicationCommitRegistry(
            self.publication_path,
            scope_descriptor=self.scope_descriptor,
            create_new=True,
        )
        self.result = _hold_result()
        self.receipt, created = commit_publication_result(
            self.result,
            registry=self.publication_registry,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        self.assertTrue(created)
        self.hmac_key = b"recovery-test-hmac-key-material-32+"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def registry(self) -> RecoveryActivationRegistry:
        return RecoveryActivationRegistry(
            self.recovery_path,
            publication_scope_id=self.scope_descriptor.publication_scope_id,
            hmac_key=self.hmac_key,
        )

    def test_sidecar_append_keeps_result_receipt_and_publication_wal_byte_exact(self) -> None:
        result_before = deepcopy(self.result)
        receipt_before = self.receipt.to_dict()
        publication_wal_before = self.publication_path.read_bytes()

        event, created = self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )

        self.assertTrue(created)
        self.assertEqual(self.result, result_before)
        self.assertEqual(self.receipt.to_dict(), receipt_before)
        self.assertEqual(self.publication_path.read_bytes(), publication_wal_before)
        self.assertFalse(event.public_apply)
        self.assertEqual(event.mode, RECOVERY_MODE)
        self.assertEqual(event.capability_scope, RECOVERY_CAPABILITY_SCOPE)
        self.assertTrue(
            verify_recovery_capability(
                event,
                "review-capability-101",
                hmac_key=self.hmac_key,
            )
        )
        self.assertFalse(
            verify_recovery_capability(
                event,
                "wrong-capability",
                hmac_key=self.hmac_key,
            )
        )

    def test_identical_replay_is_idempotent_after_registry_reload(self) -> None:
        first, first_created = self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )
        replay, replay_created = self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=deepcopy(self.result),
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )

        self.assertTrue(first_created)
        self.assertFalse(replay_created)
        self.assertEqual(first.event_sha256, replay.event_sha256)
        self.assertEqual(len(self.recovery_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_existing_proposal_rejects_different_capability(self) -> None:
        self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )
        with self.assertRaisesRegex(
            RecoveryActivationError,
            "existing recovery proposal capability mismatch",
        ):
            self.registry().ensure_proposal(
                receipt=self.receipt,
                canonical_result=self.result,
                proposal=_proposal(),
                raw_capability="replacement-capability",
            )

    def test_hash_chain_and_json_roundtrip_reject_tampering(self) -> None:
        first, _ = self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )
        second, _ = self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(raw_title="검토 후보 작품 원문 변형"),
            raw_capability="review-capability-102",
        )

        self.assertEqual(first.sequence, 1)
        self.assertEqual(second.sequence, 2)
        self.assertEqual(second.prev_event_sha256, first.event_sha256)
        self.assertEqual(
            RecoveryActivationEvent.from_dict(second.to_dict()).event_sha256,
            second.event_sha256,
        )

        lines = self.recovery_path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["proposal"]["raw_candidate_title"] = "변조된 후보"
        lines[0] = json.dumps(tampered, ensure_ascii=False, sort_keys=True)
        self.recovery_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RecoveryActivationError, "proposal id mismatch"):
            self.registry()

    def test_base_result_mismatch_fails_without_sidecar_write(self) -> None:
        forged = deepcopy(self.result)
        forged["analysis_result"]["identity"]["blocked_official_title"] = "다른 후보"
        with self.assertRaisesRegex(
            RecoveryActivationError,
            "base publication validation failed",
        ):
            self.registry().ensure_proposal(
                receipt=self.receipt,
                canonical_result=forged,
                proposal=_proposal(),
                raw_capability="review-capability-101",
            )
        self.assertFalse(self.recovery_path.exists())

    def test_proposal_schema_rejects_public_writer_field(self) -> None:
        payload = _proposal().to_dict()
        payload["official_title"] = "공개 필드 주입"
        with self.assertRaisesRegex(RecoveryActivationError, "fields mismatch"):
            RecoveryProposal.from_dict(payload)

    def test_direct_ocr_extractor_is_review_only_and_ignores_published_rows(self) -> None:
        hold = _direct_ocr_hold_result()
        proposals = extract_direct_ocr_review_proposals(hold)

        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].raw_candidate_title, "검토 후보 작품")
        self.assertEqual(proposals[0].canonical_title, "")
        self.assertEqual(proposals[0].search_health, "SEARCH_DEGRADED")
        self.assertIn("search_degraded", proposals[0].blocker_codes)
        serialized = proposals[0].to_dict()
        self.assertNotIn("official_title", serialized)
        self.assertNotIn("public_apply", serialized)

        published = deepcopy(hold)
        identity = published["analysis_result"]["identity"]
        identity["title_resolution_allowed"] = True
        identity["novel_identity"] = {
            "official_title": "검토 후보 작품",
            "heretic_url": None,
        }
        identity["promotion_decision"]["publish_allowed"] = True
        self.assertEqual(extract_direct_ocr_review_proposals(published), ())

    def test_direct_ocr_extractor_skips_suppressed_or_background_listing(self) -> None:
        for marker in ("suppressed_explicit_work_title", "background_listing_only"):
            with self.subTest(marker=marker):
                result = _direct_ocr_hold_result()
                item = result["analysis_result"]["identity"]["image_evidence_catalog"][0]
                item[marker] = (
                    "검토 후보 작품" if marker == "suppressed_explicit_work_title" else True
                )
                self.assertEqual(extract_direct_ocr_review_proposals(result), ())

    def test_direct_ocr_extractor_preserves_multi_title_conflict_as_review_metadata(self) -> None:
        result = _direct_ocr_hold_result()
        result["analysis_result"]["identity"]["image_evidence_catalog"].append(
            {
                "eid": "IMG002",
                "block_index": 1,
                "explicit_work_title": "경쟁 작품",
                "evidence_type": "explicit_text",
                "title_role": "work_title",
                "promotion_eligible": True,
            }
        )
        proposals = extract_direct_ocr_review_proposals(result)

        self.assertEqual(len(proposals), 2)
        self.assertTrue(all(proposal.conflict_count == 1 for proposal in proposals))
        self.assertTrue(
            all("multiple_explicit_ocr_titles" in proposal.blocker_codes for proposal in proposals)
        )

    def test_direct_ocr_verified_detail_identity_is_derived_for_three_platforms(self) -> None:
        cases = (
            ("https://page.kakao.com/content/12345?tab_type=comment#comments", "kakao:12345", "https://page.kakao.com/content/12345"),
            ("https://series.naver.com/novel/detail.series?productNo=23456&utm_source=x", "naver:23456", "https://series.naver.com/novel/detail.series?productNo=23456"),
            ("https://novelpia.com/novel/34567?sid=main", "novelpia:34567", "https://novelpia.com/novel/34567"),
        )
        for url, work_id, canonical_url in cases:
            with self.subTest(url=url):
                result = _direct_ocr_hold_result()
                candidate = result["analysis_result"]["identity"]["title_candidates"][0]
                candidate.update(
                    source_tier="official_detail",
                    page_type="novel_page",
                    content_status="active",
                    heretic_url=url,
                )
                proposal = extract_direct_ocr_review_proposals(result)[0]
                self.assertEqual(proposal.rule_version, "direct_ocr_review_shadow_v2")
                self.assertEqual(proposal.canonical_work_id, work_id)
                self.assertEqual(proposal.candidate_url, canonical_url)
                self.assertNotIn("canonical_identity_unverified", proposal.blocker_codes)

    def test_direct_ocr_rejects_listing_malformed_and_slug_urls(self) -> None:
        for url in (
            "https://page.kakao.com/home?seriesId=12345",
            "https://novelpia.com/novel/not-a-number",
            "https://example.com/work/title-slug",
        ):
            with self.subTest(url=url):
                result = _direct_ocr_hold_result()
                candidate = result["analysis_result"]["identity"]["title_candidates"][0]
                candidate.update(source_tier="official_detail", page_type="novel_page", content_status="active", heretic_url=url)
                proposal = extract_direct_ocr_review_proposals(result)[0]
                self.assertEqual(proposal.canonical_work_id, "")
                self.assertIn("canonical_identity_unverified", proposal.blocker_codes)

    def test_direct_ocr_same_title_multiple_identity_blocks_without_first_wins(self) -> None:
        result = _direct_ocr_hold_result()
        candidates = result["analysis_result"]["identity"]["title_candidates"]
        candidates[0].update(source_tier="official_detail", page_type="novel_page", content_status="active", heretic_url="https://novelpia.com/novel/1001")
        candidates.append({**candidates[0], "heretic_url": "https://page.kakao.com/content/2002"})
        proposal = extract_direct_ocr_review_proposals(result)[0]
        self.assertEqual(proposal.canonical_work_id, "")
        self.assertEqual(proposal.candidate_url, "")
        self.assertIn("canonical_identity_ambiguous", proposal.blocker_codes)

    def test_direct_ocr_duplicate_records_for_one_identity_are_deduplicated(self) -> None:
        result = _direct_ocr_hold_result()
        candidates = result["analysis_result"]["identity"]["title_candidates"]
        candidates[0].update(
            source_tier="official_detail",
            page_type="novel_page",
            content_status="active",
            heretic_url="https://novelpia.com/novel/1001?tracking=first",
        )
        candidates.append(
            {
                **candidates[0],
                "official_url": "https://novelpia.com/novel/1001#detail",
                "heretic_url": "",
            }
        )

        proposal = extract_direct_ocr_review_proposals(result)[0]

        self.assertEqual(proposal.canonical_work_id, "novelpia:1001")
        self.assertEqual(proposal.candidate_url, "https://novelpia.com/novel/1001")
        self.assertNotIn("canonical_identity_unverified", proposal.blocker_codes)

    def test_direct_ocr_missing_typed_identity_is_review_only(self) -> None:
        result = _direct_ocr_hold_result()
        candidate = result["analysis_result"]["identity"]["title_candidates"][0]
        candidate.update(heretic_url="https://novelpia.com/novel/101")
        proposal = extract_direct_ocr_review_proposals(result)[0]
        self.assertEqual(proposal.canonical_work_id, "")
        self.assertIn("canonical_identity_unverified", proposal.blocker_codes)

    def test_derived_review_capability_is_replay_stable_and_proposal_bound(self) -> None:
        first = derive_review_recovery_capability(
            self.receipt,
            _proposal(),
            hmac_key=self.hmac_key,
        )
        replay = derive_review_recovery_capability(
            self.receipt,
            _proposal(),
            hmac_key=self.hmac_key,
        )
        changed = derive_review_recovery_capability(
            self.receipt,
            _proposal(raw_title="다른 원문"),
            hmac_key=self.hmac_key,
        )

        self.assertEqual(first, replay)
        self.assertNotEqual(first, changed)

    def test_sixteen_registry_instances_append_same_proposal_once(self) -> None:
        def append_once(_index: int) -> bool:
            _event, created = self.registry().ensure_proposal(
                receipt=self.receipt,
                canonical_result=self.result,
                proposal=_proposal(),
                raw_capability="review-capability-101",
            )
            return created

        with ThreadPoolExecutor(max_workers=16) as executor:
            created_flags = list(executor.map(append_once, range(16)))

        self.assertEqual(sum(created_flags), 1)
        self.assertEqual(len(self.recovery_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_expert_main_sidecar_hook_is_after_base_validation_and_before_learning(self) -> None:
        source = inspect.getsource(expert_main.main)
        commit_source = source[
            source.index("def _commit_final_result") : source.index("# 📊 대시보드: batch_start")
        ]
        hook_index = commit_source.index("_ensure_review_recovery_sidecar(")
        validation_index = commit_source.rfind(
            "validate_publication_result_commit(",
            0,
            hook_index,
        )
        commit_index = commit_source.rfind(
            "commit_publication_result(",
            0,
            hook_index,
        )
        learning_index = commit_source.index(
            "_queue_batch_context_publication_learning(",
            hook_index,
        )
        fresh_return_index = commit_source.index(
            "return final_receipt, False, result_item"
        )

        self.assertLess(fresh_return_index, commit_index)
        self.assertLess(commit_index, validation_index)
        self.assertLess(validation_index, hook_index)
        self.assertLess(hook_index, learning_index)

    def test_scope_local_hmac_key_is_created_once_and_not_written_to_journal(self) -> None:
        key_path = self.root / "recovery.key"
        first = load_or_create_recovery_activation_hmac_key(key_path)
        second = load_or_create_recovery_activation_hmac_key(key_path)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)
        self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability=derive_review_recovery_capability(
                self.receipt,
                _proposal(),
                hmac_key=self.hmac_key,
            ),
        )
        journal_text = self.recovery_path.read_text(encoding="utf-8")
        self.assertNotIn(self.hmac_key.hex(), journal_text)
        self.assertNotIn(first.hex(), journal_text)

    def test_partial_hmac_key_fails_closed_without_touching_base_wal(self) -> None:
        publication_wal_before = self.publication_path.read_bytes()
        key_path = self.root / "partial-recovery.key"
        key_path.write_text("abcd", encoding="ascii")

        with self.assertRaisesRegex(
            RecoveryActivationError,
            "HMAC key file is invalid",
        ):
            load_or_create_recovery_activation_hmac_key(key_path)

        self.assertEqual(key_path.read_text(encoding="ascii"), "abcd")
        self.assertEqual(self.publication_path.read_bytes(), publication_wal_before)

    def test_concurrent_hmac_key_creators_publish_one_complete_0600_key(self) -> None:
        key_path = self.root / "concurrent-recovery.key"

        with ThreadPoolExecutor(max_workers=16) as executor:
            keys = list(
                executor.map(
                    lambda _index: load_or_create_recovery_activation_hmac_key(key_path),
                    range(16),
                )
            )

        self.assertEqual(len({key.hex() for key in keys}), 1)
        self.assertTrue(all(len(key) == 32 for key in keys))
        payload = key_path.read_text(encoding="ascii")
        self.assertRegex(payload, r"^[0-9a-f]{64}\n$")
        self.assertTrue(private_file_permissions_ok(key_path))

    def test_self_consistent_forged_base_event_is_rejected_on_authoritative_replay(self) -> None:
        proposal = _proposal()
        forged_receipt = replace(self.receipt, result_sha256="c" * 64)
        forged_capability = derive_review_recovery_capability(
            forged_receipt,
            proposal,
            hmac_key=self.hmac_key,
        )
        forged_event = _create_event(
            receipt=forged_receipt,
            proposal=proposal,
            raw_capability=forged_capability,
            hmac_key=self.hmac_key,
            sequence=1,
            prev_event_sha256="GENESIS",
        )
        self.recovery_path.write_text(
            json.dumps(
                forged_event.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            RecoveryActivationError,
            "existing recovery proposal base mismatch: base_result_sha256",
        ):
            self.registry().ensure_proposal(
                receipt=self.receipt,
                canonical_result=self.result,
                proposal=proposal,
                raw_capability=derive_review_recovery_capability(
                    self.receipt,
                    proposal,
                    hmac_key=self.hmac_key,
                ),
            )

    def test_unterminated_tail_is_repaired_then_reconciled_without_base_wal_change(self) -> None:
        publication_wal_before = self.publication_path.read_bytes()
        registry = self.registry()
        registry.ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )
        with self.recovery_path.open("ab") as handle:
            handle.write(b'{"partial_event":')

        repaired = self.registry()
        self.assertEqual(repaired.tail_repair_count, 1)
        self.assertEqual(len(repaired.events()), 1)
        _event, created = repaired.ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(raw_title="두 번째 검토 후보"),
            raw_capability="review-capability-102",
        )

        self.assertTrue(created)
        self.assertEqual(len(repaired.events()), 2)
        self.assertEqual(self.publication_path.read_bytes(), publication_wal_before)
        self.assertTrue(repaired.tail_repair_path.exists())

    def test_completed_invalid_tail_fails_closed_without_repair(self) -> None:
        self.registry().ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )
        payload_before = self.recovery_path.read_bytes() + b'{"invalid":}\n'
        self.recovery_path.write_bytes(payload_before)

        with self.assertRaisesRegex(
            RecoveryActivationError,
            "invalid recovery activation JSON line: 2",
        ):
            self.registry()

        self.assertEqual(self.recovery_path.read_bytes(), payload_before)
        self.assertFalse(
            self.recovery_path.with_name(
                self.recovery_path.name + ".tail_repair.jsonl"
            ).exists()
        )

    def test_corrupt_completed_middle_frame_fails_closed_without_repair(self) -> None:
        registry = self.registry()
        registry.ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(),
            raw_capability="review-capability-101",
        )
        registry.ensure_proposal(
            receipt=self.receipt,
            canonical_result=self.result,
            proposal=_proposal(raw_title="두 번째 검토 후보"),
            raw_capability="review-capability-102",
        )
        lines = self.recovery_path.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["proposal"]["raw_candidate_title"] = "완결 프레임 변조"
        lines[0] = json.dumps(first, ensure_ascii=False, sort_keys=True)
        payload_before = ("\n".join(lines) + "\n").encode("utf-8")
        self.recovery_path.write_bytes(payload_before)

        with self.assertRaises(RecoveryActivationError):
            self.registry()

        self.assertEqual(self.recovery_path.read_bytes(), payload_before)
        self.assertFalse(
            self.recovery_path.with_name(
                self.recovery_path.name + ".tail_repair.jsonl"
            ).exists()
        )

    def test_sidecar_io_error_is_normalized_and_base_wal_is_unchanged(self) -> None:
        publication_wal_before = self.publication_path.read_bytes()
        registry = self.registry()
        with patch(
            "src.llm_batch.ledger.recovery_activation.os.fsync",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaisesRegex(
                RecoveryActivationError,
                "journal I/O failed",
            ):
                registry.ensure_proposal(
                    receipt=self.receipt,
                    canonical_result=self.result,
                    proposal=_proposal(),
                    raw_capability="review-capability-101",
                )
        self.assertEqual(self.publication_path.read_bytes(), publication_wal_before)

    def test_fresh_measurement_runtime_creates_no_key_journal_or_lock_files(self) -> None:
        root = self.root / "fresh-runtime"
        journal = root / "recovery.jsonl"
        key = root / "recovery.key"

        hmac_key, registry, status, mode = (
            expert_main._initialize_recovery_activation_runtime(
                journal_path=journal,
                hmac_key_path=key,
                publication_scope_id=self.scope_descriptor.publication_scope_id,
                requested_mode="AUDIT_ONLY",
                fresh_execution_required=True,
            )
        )

        self.assertIsNone(hmac_key)
        self.assertIsNone(registry)
        self.assertEqual(status, "SKIPPED_FRESH_MEASUREMENT")
        self.assertEqual(mode, "AUDIT_ONLY")
        self.assertFalse(root.exists())

    def test_recovery_runtime_is_off_by_default_and_byte_clean(self) -> None:
        root = self.root / "off-runtime"
        hmac_key, registry, status, mode = (
            expert_main._initialize_recovery_activation_runtime(
                journal_path=root / "recovery.jsonl",
                hmac_key_path=root / "recovery.key",
                publication_scope_id=self.scope_descriptor.publication_scope_id,
                requested_mode="",
                fresh_execution_required=False,
            )
        )

        self.assertIsNone(hmac_key)
        self.assertIsNone(registry)
        self.assertEqual(status, "DISABLED")
        self.assertEqual(mode, "OFF")
        self.assertFalse(root.exists())

    def test_invalid_recovery_runtime_mode_fails_closed_without_writes(self) -> None:
        root = self.root / "invalid-runtime"
        with self.assertRaisesRegex(
            ValueError,
            "RECOVERY_ACTIVATION_MODE must be OFF or AUDIT_ONLY",
        ):
            expert_main._initialize_recovery_activation_runtime(
                journal_path=root / "recovery.jsonl",
                hmac_key_path=root / "recovery.key",
                publication_scope_id=self.scope_descriptor.publication_scope_id,
                requested_mode="PUBLIC_APPLY",
                fresh_execution_required=False,
            )
        self.assertFalse(root.exists())

    def test_replay_sidecar_call_remains_guarded_in_fresh_measurement(self) -> None:
        source = inspect.getsource(expert_main.main)
        replay_source = source[
            source.index("for _replay_receipt in publication_commit_registry.receipts()") :
            source.index("_publication_reference_by_index")
        ]
        self.assertIn(
            'if not _decision_call_measurement["fresh_execution_required"]:',
            replay_source,
        )

    def test_reconciliation_tool_rejects_mixed_publication_scopes(self) -> None:
        second_descriptor = build_publication_scope_descriptor(
            input_file_sha256="d" * 64,
            post_ids=[101],
            config_hash="different-scope",
            release_fingerprint="release-test",
        )
        second_registry = PublicationCommitRegistry(
            self.root / "publication-second.jsonl",
            scope_descriptor=second_descriptor,
            create_new=True,
        )
        second_receipt, _ = commit_publication_result(
            self.result,
            registry=second_registry,
            attempt_run_id="attempt-2",
            input_index=1,
            post_id=101,
        )
        first_checkpoint = self.root / "first_checkpoint.jsonl"
        second_checkpoint = self.root / "second_checkpoint.jsonl"
        first_checkpoint.write_text(
            json.dumps(
                {
                    "global_idx": 1,
                    "post_id": 101,
                    "status": "completed",
                    "publication_commit": self.receipt.to_dict(),
                    "result": self.result,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        second_checkpoint.write_text(
            json.dumps(
                {
                    "global_idx": 1,
                    "post_id": 101,
                    "status": "completed",
                    "publication_commit": second_receipt.to_dict(),
                    "result": self.result,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        output_dir = self.root / "mixed-scope-output"
        completed = subprocess.run(
            [
                sys.executable,
                "tools/reconcile_recovery_activation_checkpoint.py",
                "--checkpoint",
                str(first_checkpoint),
                "--checkpoint",
                str(second_checkpoint),
                "--output-dir",
                str(output_dir),
            ],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        summary = json.loads(
            (output_dir / "recovery_activation_reconciliation_summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(summary["gate"], "NO-GO")
        self.assertEqual(
            summary["scope_compatibility"]["reason"],
            "mixed_publication_scope_id",
        )


if __name__ == "__main__":
    unittest.main()
