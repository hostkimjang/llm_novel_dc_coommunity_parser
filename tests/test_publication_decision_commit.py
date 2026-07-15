from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import FrozenInstanceError
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import expert_main
from src.llm_batch.agentic_pipeline import AgenticPipeline
from src.llm_batch.domain.batch_context import (
    BATCH_CONTEXT_LEARNING_ENVELOPE_SCHEMA,
    BATCH_CONTEXT_LEARNING_MAX_CHARACTERS,
    BatchContextMemory,
)
from src.llm_batch.experts.orchestrator import ExpertType
from src.llm_batch.domain.models import PickvelOutputItemV2

from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)
from src.llm_batch.ledger.publication_commit import (
    PUBLICATION_COMMIT_OWNER,
    PUBLICATION_COMMIT_SCHEMA,
    PublicationCommitError,
    PublicationCommitRegistry,
    PublicationScopeDescriptor,
    audit_publication_commits,
    build_publication_scope_descriptor,
    build_publication_scope_id,
    commit_publication_result,
    compute_publication_decision_commit,
    validate_publication_result_commit,
)


class _DummyLLM:
    pass


class _DummyMCP:
    pass


class _RecordingBatchContext:
    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.learned: list[dict] = []
        self.learning_kwargs: list[dict] = []

    def learn_from_result(self, result: dict, **kwargs) -> None:
        self.learned.append(result)
        self.learning_kwargs.append(kwargs)


class _EnvelopeContext:
    def __init__(self) -> None:
        self.snippet_hints = {
            "author_hints": [
                {
                    "name": "테스트 작가",
                    "source": "url_fetch_platform",
                    "raw_prompt": "DO_NOT_PERSIST_AUTHOR_PROMPT",
                }
            ]
        }
        self.fetched_page_info = [
            {
                "url": "https://namu.wiki/w/test",
                "page_title": "테스트",
                "content": "DO_NOT_PERSIST_RAW_PAGE",
            }
        ]

    def get_expert_output(self, expert_type):
        if expert_type == ExpertType.DECODER:
            return {
                "decoded_terms": [
                    {
                        "original": "작품약칭",
                        "best_match": {
                            "title": "정식 작품",
                            "raw_snippet": "DO_NOT_PERSIST_MATCH_SNIPPET",
                        },
                        "source_role": "work_alias",
                        "raw_prompt": "DO_NOT_PERSIST_DECODER_PROMPT",
                    }
                ]
            }
        if expert_type == ExpertType.VERIFIER:
            return {
                "verification_result": {
                    "confirmed_characters": [
                        "주인공",
                        "주인공",
                        *[f"인물{i}" for i in range(40)],
                    ],
                    "raw_snippet": "DO_NOT_PERSIST_VERIFIER_SNIPPET",
                }
            }
        return {}


def _scope_descriptor(post_ids=(101, 102)):
    return build_publication_scope_descriptor(
        input_file_sha256="a" * 64,
        post_ids=list(post_ids),
        config_hash="config-v1",
        release_fingerprint="release-v1",
    )


def _scope_id(post_ids=(101, 102)) -> str:
    return _scope_descriptor(post_ids).publication_scope_id


def _valid_result(
    *,
    post_id: int = 101,
    publish: bool = True,
    candidate_title: str = "작품 A",
) -> dict:
    candidate_url = f"https://novelpia.com/novel/{post_id}"
    state = GroundingState(
        post_id=post_id,
        candidate_title=candidate_title,
        candidate_url=candidate_url,
        source="test",
        official_title_exists=publish,
        row_discusses_work_as_work=publish,
        title_resolution_state="resolved" if publish else "unresolved_matchable",
        work_resolution="resolved" if publish else "unresolved",
        discussion_type="specific_work" if publish else "unknown",
        scope=ScopeState(
            scope_kind="current_work" if publish else "unknown",
            confidence="high" if publish else "low",
            direct_bridge_sources=("body", "official_detail") if publish else (),
            conflict_reason_codes=() if publish else ("test_hold",),
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="official_detail" if publish else "test_hold",
            strength="strong",
            source_path_or_snippet=candidate_url,
            supports_publish=publish,
            reason_code="official_support" if publish else "test_hold",
            candidate_title=candidate_title,
            candidate_url=candidate_url,
            title_url_match=True if publish else None,
        )
    ]
    contract = evaluate_publish_contract(state, evidence)
    identity = {
        "is_relevant": publish,
        "novel_identity": (
            {
                "official_title": candidate_title,
                "heretic_url": candidate_url,
                "confidence": "High",
            }
            if publish
            else None
        ),
    }
    apply_publish_contract(identity, contract)
    return {
        "gallery_id": "novel",
        "post_id": post_id,
        "title": "동일 입력 게시글",
        "post_author": "tester",
        "created_at": "2026-07-11T00:00:00+09:00",
        "url": f"https://example.com/post/{post_id}",
        "content": ["동일 본문"],
        "content_blocks": [{"type": "text", "text": "동일 본문"}],
        "comments": ["동일 댓글"],
        "comment_metadata": [],
        "analysis_result": {"identity": identity},
        "run_meta": {},
    }


def _error_result(post_id: int = 101) -> dict:
    return {
        "post_id": post_id,
        "title": "",
        "error": "private upstream detail",
        "analysis_result": {
            "identity": {
                "is_relevant": False,
                "reason": "처리 오류",
            }
        },
    }


class PublicationDecisionCommitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.scope_descriptor = _scope_descriptor()
        self.scope = self.scope_descriptor.publication_scope_id

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def registry(self, *, create_new: bool = True) -> PublicationCommitRegistry:
        return PublicationCommitRegistry(
            self.root / "publication_commits.jsonl",
            scope_descriptor=self.scope_descriptor,
            create_new=create_new,
        )

    def test_receipt_is_scalar_frozen_and_contains_no_public_title_or_url(self) -> None:
        row = _valid_result()
        receipt = compute_publication_decision_commit(
            row,
            publication_scope_id=self.scope,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )

        self.assertEqual(receipt.schema_version, PUBLICATION_COMMIT_SCHEMA)
        self.assertEqual(receipt.owner, PUBLICATION_COMMIT_OWNER)
        self.assertEqual(receipt.outcome, "PUBLISH")
        serialized = json.dumps(receipt.to_dict(), ensure_ascii=False)
        self.assertNotIn("작품 A", serialized)
        self.assertNotIn("https://novelpia.com/novel/101", serialized)
        with self.assertRaises(FrozenInstanceError):
            receipt.post_id = 999  # type: ignore[misc]

    def test_durable_identical_replay_is_noop_even_after_registry_reload(self) -> None:
        row = _valid_result()
        first_registry = self.registry()
        first, first_created = commit_publication_result(
            row,
            registry=first_registry,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        reloaded = self.registry(create_new=False)
        replay, replay_created = commit_publication_result(
            deepcopy(row),
            registry=reloaded,
            attempt_run_id="attempt-2",
            input_index=1,
            post_id=101,
        )

        self.assertTrue(first_created)
        self.assertFalse(replay_created)
        self.assertEqual(first.decision_id, replay.decision_id)
        self.assertEqual(first.commit_sha256, replay.commit_sha256)
        self.assertEqual(len((self.root / "publication_commits.jsonl").read_text().splitlines()), 1)

    def test_attempt_local_run_meta_does_not_conflict_and_first_row_stays_canonical(self) -> None:
        first_row = _valid_result()
        first_row["run_meta"] = {
            "run_id": "attempt-a",
            "worker_id": 1,
            "worker_log_file": "logs/a.log",
            "decision_cost_trace": {
                "run_id": "attempt-a",
                "processing_started_at": "2026-07-12T01:00:00+09:00",
                "wall_ms": 1000,
                "total_tokens": 100,
            },
            "decision_call_ledger": {
                "attempt_run_id": "attempt-a",
                "row_attempt_id": "row-attempt-a",
                "event_root_sha256": "a" * 64,
            },
            "decision_call_ledger_summary": {
                "expert_calls": 1,
                "total_tokens": 100,
            },
            "decision_call_attempt_receipt": {
                "publication_decision_id": "c" * 64,
                "row_attempt_id": "row-attempt-a",
            },
            "decision_call_measurement": {
                "pair_id": "pair-1",
                "arm": "BEFORE",
            },
            "measurement_execution_source": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
        }
        retry_row = deepcopy(first_row)
        retry_row["run_meta"] = {
            "run_id": "attempt-b",
            "worker_id": 7,
            "worker_log_file": "logs/b.log",
            "decision_cost_trace": {
                "run_id": "attempt-b",
                "processing_started_at": "2026-07-12T02:00:00+09:00",
                "wall_ms": 9000,
                "total_tokens": 900,
            },
            "decision_call_ledger": {
                "attempt_run_id": "attempt-b",
                "row_attempt_id": "row-attempt-b",
                "event_root_sha256": "b" * 64,
            },
            "decision_call_ledger_summary": {
                "expert_calls": 2,
                "total_tokens": 900,
            },
            "decision_call_attempt_receipt": {
                "publication_decision_id": "c" * 64,
                "row_attempt_id": "row-attempt-b",
            },
            "decision_call_measurement": {
                "pair_id": "pair-1",
                "arm": "AFTER",
            },
            "measurement_execution_source": "FRESH_EXECUTION_NO_PUBLIC_WRITE",
        }
        registry = self.registry()

        first, first_created = commit_publication_result(
            first_row,
            registry=registry,
            attempt_run_id="attempt-a",
            input_index=1,
            post_id=101,
        )
        replay, replay_created = commit_publication_result(
            retry_row,
            registry=registry,
            attempt_run_id="attempt-b",
            input_index=1,
            post_id=101,
        )

        self.assertTrue(first_created)
        self.assertFalse(replay_created)
        self.assertEqual(first.decision_id, replay.decision_id)
        self.assertEqual(registry.result(101), first_row)
        self.assertEqual(len(registry.events()), 1)

    def test_non_attempt_analysis_difference_is_a_conflicting_stable_result(self) -> None:
        first_row = _valid_result()
        second_row = deepcopy(first_row)
        first_row["analysis_result"]["analysis"] = {"notes": "first analysis"}
        second_row["analysis_result"]["analysis"] = {"notes": "different analysis"}
        registry = self.registry()
        commit_publication_result(
            first_row,
            registry=registry,
            attempt_run_id="attempt-a",
            input_index=1,
            post_id=101,
        )

        with self.assertRaisesRegex(PublicationCommitError, "conflicting terminal"):
            commit_publication_result(
                second_row,
                registry=registry,
                attempt_run_id="attempt-b",
                input_index=1,
                post_id=101,
            )

    def test_same_registry_appends_without_repeating_full_load(self) -> None:
        post_ids = tuple(range(1, 51))
        descriptor = _scope_descriptor(post_ids)
        journal = self.root / "incremental.jsonl"
        registry = PublicationCommitRegistry(
            journal,
            scope_descriptor=descriptor,
            create_new=True,
        )

        with patch.object(registry, "_load", side_effect=AssertionError("full reload")):
            for index, post_id in enumerate(post_ids, 1):
                _, created = commit_publication_result(
                    _valid_result(post_id=post_id, candidate_title=f"작품 {post_id}"),
                    registry=registry,
                    attempt_run_id="incremental-attempt",
                    input_index=index,
                    post_id=post_id,
                )
                self.assertTrue(created)

        self.assertEqual(registry.count, len(post_ids))
        self.assertEqual(registry._validated_size_bytes, journal.stat().st_size)

    def test_stale_registries_incrementally_ingest_each_others_frames(self) -> None:
        journal = self.root / "stale_instances.jsonl"
        first = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=True,
        )
        second = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=False,
        )
        commit_publication_result(
            _valid_result(post_id=101),
            registry=first,
            attempt_run_id="attempt-a",
            input_index=1,
            post_id=101,
        )
        _, created = commit_publication_result(
            _valid_result(post_id=102, candidate_title="작품 B"),
            registry=second,
            attempt_run_id="attempt-b",
            input_index=2,
            post_id=102,
        )

        self.assertTrue(created)
        reopened = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=False,
        )
        self.assertEqual(reopened.count, 2)

    def test_live_registry_rejects_shrink_replacement_and_prefix_rewrite(self) -> None:
        for mutation in ("shrink", "replace", "tail_anchor_rewrite"):
            with self.subTest(mutation=mutation):
                journal = self.root / f"binding_{mutation}.jsonl"
                registry = PublicationCommitRegistry(
                    journal,
                    scope_descriptor=self.scope_descriptor,
                    create_new=True,
                )
                commit_publication_result(
                    _valid_result(post_id=101),
                    registry=registry,
                    attempt_run_id="attempt-a",
                    input_index=1,
                    post_id=101,
                )
                original = journal.read_bytes()
                if mutation == "shrink":
                    journal.write_bytes(original[:-1])
                    expected = "shrank"
                elif mutation == "replace":
                    replacement = journal.with_name(journal.name + ".replacement")
                    replacement.write_bytes(original)
                    os.replace(replacement, journal)
                    expected = "identity changed"
                else:
                    rewritten = bytearray(original)
                    rewritten[-2] = (
                        ord("[") if rewritten[-2] != ord("[") else ord("{")
                    )
                    journal.write_bytes(bytes(rewritten))
                    expected = "prefix tail changed"

                with self.assertRaisesRegex(PublicationCommitError, expected):
                    commit_publication_result(
                        _valid_result(post_id=102, candidate_title="작품 B"),
                        registry=registry,
                        attempt_run_id="attempt-b",
                        input_index=2,
                        post_id=102,
                    )

    def test_conflicting_second_decision_for_same_scope_post_is_rejected(self) -> None:
        registry = self.registry()
        first = _valid_result(candidate_title="작품 A")
        second = _valid_result(candidate_title="작품 B")
        commit_publication_result(
            first,
            registry=registry,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )

        with self.assertRaisesRegex(PublicationCommitError, "conflicting terminal"):
            commit_publication_result(
                second,
                registry=registry,
                attempt_run_id="attempt-2",
                input_index=1,
                post_id=101,
            )

    def test_cross_post_typed_state_replay_is_rejected(self) -> None:
        row = _valid_result(post_id=101)
        row["post_id"] = 202

        with self.assertRaisesRegex(PublicationCommitError, "typed state post_id"):
            compute_publication_decision_commit(
                row,
                publication_scope_id=self.scope,
                attempt_run_id="attempt-1",
                input_index=1,
                post_id=202,
            )

    def test_forged_contract_version_and_missing_typed_inputs_are_rejected(self) -> None:
        forged = _valid_result()
        identity = forged["analysis_result"]["identity"]
        identity["publish_contract_version"] = "evil_contract"
        identity["candidate_ledger"]["publish_contract_version"] = "evil_contract"
        identity["promotion_decision"]["contract_version"] = "evil_contract"
        identity["candidate_ledger"]["promotion_decision"]["contract_version"] = "evil_contract"

        with self.assertRaisesRegex(PublicationCommitError, "not authoritative"):
            compute_publication_decision_commit(
                forged,
                publication_scope_id=self.scope,
                attempt_run_id="attempt-1",
                input_index=1,
                post_id=101,
            )

        missing = _valid_result()
        missing["analysis_result"]["identity"].pop("promotion_gate_state")
        with self.assertRaisesRegex(PublicationCommitError, "state/evidence"):
            compute_publication_decision_commit(
                missing,
                publication_scope_id=self.scope,
                attempt_run_id="attempt-1",
                input_index=1,
                post_id=101,
            )

    def test_public_or_input_mutation_after_commit_is_rejected(self) -> None:
        row = _valid_result()
        receipt, _ = commit_publication_result(
            row,
            registry=self.registry(),
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        public_changed = deepcopy(row)
        public_changed["analysis_result"]["identity"]["novel_identity"]["official_title"] = "변조"
        input_changed = deepcopy(row)
        input_changed["content"] = ["변조된 본문"]

        with self.assertRaises(PublicationCommitError):
            validate_publication_result_commit(public_changed, receipt)
        with self.assertRaisesRegex(PublicationCommitError, "no longer matches"):
            validate_publication_result_commit(input_changed, receipt)

        relevance_changed = deepcopy(row)
        relevance_changed["analysis_result"]["identity"]["is_relevant"] = False
        run_meta_changed = deepcopy(row)
        run_meta_changed["run_meta"]["unexpected"] = "mutation"
        with self.assertRaisesRegex(PublicationCommitError, "no longer matches"):
            validate_publication_result_commit(relevance_changed, receipt)
        with self.assertRaisesRegex(PublicationCommitError, "no longer matches"):
            validate_publication_result_commit(run_meta_changed, receipt)

    def test_legacy_unowned_publication_is_rejected_not_split_brain_committed(self) -> None:
        row = {
            "post_id": 101,
            "title": "legacy",
            "analysis_result": {
                "identity": {
                    "is_relevant": True,
                    "novel_identity": {
                        "official_title": "unowned title",
                        "heretic_url": "https://example.com/unowned",
                    },
                }
            },
        }

        with self.assertRaisesRegex(PublicationCommitError, "candidate ledger"):
            compute_publication_decision_commit(
                row,
                publication_scope_id=self.scope,
                attempt_run_id="attempt-1",
                input_index=1,
                post_id=101,
            )

    def test_error_row_commits_error_hold_without_raw_error_leak(self) -> None:
        row = _error_result()
        receipt, created = commit_publication_result(
            row,
            registry=self.registry(),
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )

        self.assertTrue(created)
        self.assertEqual(receipt.outcome, "ERROR_HOLD")
        self.assertFalse(receipt.publish_allowed)
        self.assertNotIn("private upstream detail", json.dumps(receipt.to_dict()))
        validate_publication_result_commit(row, receipt)
        changed_error = deepcopy(row)
        changed_error["error"] = "different private failure"
        with self.assertRaisesRegex(PublicationCommitError, "no longer matches"):
            validate_publication_result_commit(changed_error, receipt)
        self.assertEqual(self.registry(create_new=False).result(101), row)

    def test_error_hold_rejects_nested_ledger_and_trace_public_leaks(self) -> None:
        row = _error_result()
        identity = row["analysis_result"]["identity"]
        leaked_projection = {
            "official_title": "LEAK TITLE",
            "official_url": "https://leak.example",
        }
        identity["publish_ledger"] = {
            "public_publish": deepcopy(leaked_projection),
        }
        identity["publish_contract_trace"] = {
            "post_gate_identity": deepcopy(leaked_projection),
        }

        with self.assertRaisesRegex(PublicationCommitError, "must be null"):
            compute_publication_decision_commit(
                row,
                publication_scope_id=self.scope,
                attempt_run_id="error-nested-leak",
                input_index=1,
                post_id=101,
            )

    def test_error_hold_rejects_result_and_analysis_root_public_alias_leaks(self) -> None:
        for surface in ("result", "analysis_result"):
            with self.subTest(surface=surface):
                row = _error_result()
                target = row if surface == "result" else row["analysis_result"]
                target["official_title"] = "TOP LEAK"
                target["official_url"] = "https://top-leak.example"

                with self.assertRaisesRegex(PublicationCommitError, "official_title"):
                    compute_publication_decision_commit(
                        row,
                        publication_scope_id=self.scope,
                        attempt_run_id=f"root-leak-{surface}",
                        input_index=1,
                        post_id=101,
                    )

    def test_error_hold_rejects_stale_publish_decision_mirror(self) -> None:
        row = _error_result()
        row["analysis_result"]["identity"]["promotion_decision"] = {
            "status": "publish",
            "publish_allowed": None,
            "bypassed_gate": True,
            "official_title": None,
            "official_url": None,
        }

        with self.assertRaisesRegex(PublicationCommitError, "strict false"):
            compute_publication_decision_commit(
                row,
                publication_scope_id=self.scope,
                attempt_run_id="error-stale-publish",
                input_index=1,
                post_id=101,
            )

    def test_hold_and_error_reject_all_alternate_public_title_url_keys(self) -> None:
        hold = _valid_result(publish=False)
        hold["analysis_result"]["identity"]["novel_identity"] = {
            "resolved_title": "숨은 공개값",
            "official_url": "https://example.com/hidden",
        }
        with self.assertRaisesRegex(PublicationCommitError, "novel_identity.resolved_title"):
            compute_publication_decision_commit(
                hold,
                publication_scope_id=self.scope,
                attempt_run_id="hold-leak",
                input_index=1,
                post_id=101,
            )

    def test_typed_publish_and_hold_reject_nested_alternate_public_key_leaks(self) -> None:
        for publish in (True, False):
            with self.subTest(publish=publish):
                row = _valid_result(publish=publish)
                identity = row["analysis_result"]["identity"]
                trace_projection = identity["publish_contract_trace"][
                    "post_gate_identity"
                ]
                ledger_projection = identity["publish_ledger"]["public_publish"]
                trace_projection["resolved_title"] = "NESTED LEAK"
                trace_projection["resolved_url"] = "https://leak.example"
                ledger_projection["resolved_title"] = "NESTED LEAK"
                ledger_projection["resolved_url"] = "https://leak.example"
                identity["candidate_ledger"]["publish_contract_trace"] = deepcopy(
                    identity["publish_contract_trace"]
                )
                identity["candidate_ledger"]["publish_ledger"] = deepcopy(
                    identity["publish_ledger"]
                )

                with self.assertRaisesRegex(PublicationCommitError, "resolved_title"):
                    compute_publication_decision_commit(
                        row,
                        publication_scope_id=self.scope,
                        attempt_run_id=f"nested-{publish}",
                        input_index=1,
                        post_id=101,
                    )

        error = _error_result()
        error["analysis_result"]["identity"]["novel_identity"] = {
            "official_novel_title": "숨은 오류 공개값",
            "resolved_url": "https://example.com/error-hidden",
        }
        with self.assertRaisesRegex(
            PublicationCommitError, "novel_identity.official_novel_title"
        ):
            compute_publication_decision_commit(
                error,
                publication_scope_id=self.scope,
                attempt_run_id="error-leak",
                input_index=1,
                post_id=101,
            )

    def test_same_post_race_creates_exactly_one_journal_line(self) -> None:
        registry = self.registry()
        row = _valid_result()

        def do_commit(index: int) -> bool:
            _, created = commit_publication_result(
                deepcopy(row),
                registry=registry,
                attempt_run_id=f"attempt-{index}",
                input_index=1,
                post_id=101,
            )
            return created

        with ThreadPoolExecutor(max_workers=16) as pool:
            created_flags = list(pool.map(do_commit, range(16)))

        self.assertEqual(sum(created_flags), 1)
        self.assertEqual(registry.count, 1)
        self.assertEqual(len((self.root / "publication_commits.jsonl").read_text().splitlines()), 1)

    def test_independent_registry_instances_share_one_file_cas(self) -> None:
        journal = self.root / "publication_commits.jsonl"
        first = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=True,
        )
        registries = [first] + [
            PublicationCommitRegistry(
                journal,
                scope_descriptor=self.scope_descriptor,
                create_new=False,
            )
            for _ in range(15)
        ]
        row = _valid_result()

        def do_commit(index: int) -> bool:
            _, created = commit_publication_result(
                deepcopy(row),
                registry=registries[index],
                attempt_run_id=f"independent-attempt-{index}",
                input_index=1,
                post_id=101,
            )
            return created

        with ThreadPoolExecutor(max_workers=16) as pool:
            created_flags = list(pool.map(do_commit, range(16)))

        reloaded = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=False,
        )
        self.assertEqual(sum(created_flags), 1)
        self.assertEqual(reloaded.count, 1)
        self.assertEqual(len(journal.read_text(encoding="utf-8").splitlines()), 1)

    def test_sixteen_processes_share_one_file_cas(self) -> None:
        journal = self.root / "multiprocess_publication_commits.jsonl"
        PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=True,
        )
        worker = (
            "import json,sys; "
            "from src.llm_batch.ledger.publication_commit import "
            "PublicationCommitRegistry,PublicationScopeDescriptor,commit_publication_result; "
            "descriptor=PublicationScopeDescriptor.from_dict(json.loads(sys.argv[2])); "
            "registry=PublicationCommitRegistry(sys.argv[1],scope_descriptor=descriptor,create_new=False); "
            "row={'post_id':101,'error':'process test','analysis_result':{'identity':{'is_relevant':False}}}; "
            "receipt,created=commit_publication_result(row,registry=registry,"
            "attempt_run_id=sys.argv[3],input_index=1,post_id=101); "
            "print(1 if created else 0)"
        )
        descriptor_json = json.dumps(
            self.scope_descriptor.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    worker,
                    str(journal),
                    descriptor_json,
                    f"process-{index}",
                ],
                cwd=Path(__file__).resolve().parents[1],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            for index in range(16)
        ]
        created_flags = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stderr)
            created_flags.append(int(stdout.strip()))

        reloaded = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=False,
        )
        self.assertEqual(sum(created_flags), 1)
        self.assertEqual(reloaded.count, 1)
        self.assertEqual(len(journal.read_text(encoding="utf-8").splitlines()), 1)

    def test_registry_repairs_uncommitted_tail_but_rejects_complete_duplicate(self) -> None:
        registry = self.registry()
        receipt, _ = commit_publication_result(
            _valid_result(),
            registry=registry,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        journal = self.root / "publication_commits.jsonl"
        with journal.open("a", encoding="utf-8") as handle:
            handle.write("{truncated")
        repaired = self.registry(create_new=False)
        self.assertEqual(repaired.count, 1)
        self.assertTrue(journal.read_bytes().endswith(b"\n"))
        self.assertEqual(repaired.tail_repair_count, 1)
        repair_record = repaired.tail_repair_records()[0]
        self.assertEqual(repair_record["discarded_tail_bytes"], len(b"{truncated"))
        self.assertEqual(
            repair_record["commit_point_policy"],
            "newline_terminated_valid_frame",
        )

        event = registry.events()[0]
        journal.write_text(
            json.dumps(event, ensure_ascii=False) + "\n"
            + json.dumps(event, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(PublicationCommitError, "duplicate post_id"):
            self.registry(create_new=False)

    def test_registry_rejects_invalid_newline_terminated_frame(self) -> None:
        registry = self.registry()
        commit_publication_result(
            _valid_result(),
            registry=registry,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        journal = self.root / "publication_commits.jsonl"
        with journal.open("ab") as handle:
            handle.write(b"{invalid-complete-frame}\n")

        with self.assertRaisesRegex(PublicationCommitError, "invalid publication"):
            self.registry(create_new=False)

    def test_registry_rejects_wal_result_tamper(self) -> None:
        registry = self.registry()
        commit_publication_result(
            _valid_result(),
            registry=registry,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        journal = self.root / "publication_commits.jsonl"
        event = json.loads(journal.read_text(encoding="utf-8"))
        event["result"]["run_meta"]["tampered"] = True
        journal.write_text(json.dumps(event, ensure_ascii=False) + "\n", encoding="utf-8")

        with self.assertRaisesRegex(PublicationCommitError, "no longer matches"):
            self.registry(create_new=False)

    def test_registry_refuses_existing_path_for_new_run(self) -> None:
        self.registry()
        with self.assertRaises(FileExistsError):
            self.registry(create_new=True)

    def test_registry_heals_matching_descriptor_only_creation_crash(self) -> None:
        journal = self.root / "descriptor_only.jsonl"
        descriptor_path = journal.with_name(journal.name + ".scope.json")
        descriptor_path.write_text(
            json.dumps(self.scope_descriptor.to_dict(), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        registry = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=True,
        )

        self.assertTrue(journal.exists())
        self.assertEqual(registry.count, 0)

    def test_registry_heals_torn_descriptor_when_journal_was_never_created(self) -> None:
        journal = self.root / "torn_descriptor_only.jsonl"
        descriptor_path = journal.with_name(journal.name + ".scope.json")
        descriptor_path.write_bytes(b'{"schema_version":')

        registry = PublicationCommitRegistry(
            journal,
            scope_descriptor=self.scope_descriptor,
            create_new=True,
        )

        self.assertTrue(journal.exists())
        self.assertEqual(registry.count, 0)
        self.assertEqual(
            PublicationScopeDescriptor.from_dict(
                json.loads(descriptor_path.read_text(encoding="utf-8"))
            ).to_dict(),
            self.scope_descriptor.to_dict(),
        )

    def test_registry_does_not_heal_torn_descriptor_after_journal_exists(self) -> None:
        registry = self.registry()
        registry.scope_descriptor_path.write_bytes(b'{"schema_version":')

        with self.assertRaisesRegex(PublicationCommitError, "invalid publication scope"):
            self.registry(create_new=False)

    def test_registry_enforces_descriptor_membership_and_descriptor_tamper(self) -> None:
        registry = self.registry()
        outsider = _valid_result(post_id=999, candidate_title="범위 밖 작품")
        outsider_receipt = compute_publication_decision_commit(
            outsider,
            publication_scope_id=self.scope,
            attempt_run_id="outsider",
            input_index=3,
            post_id=999,
        )
        with self.assertRaisesRegex(PublicationCommitError, "outside scope"):
            registry.record(outsider_receipt, result=outsider)

        descriptor_path = self.root / "publication_commits.jsonl.scope.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        descriptor["post_ids"] = [101, 999]
        descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
        with self.assertRaisesRegex(PublicationCommitError, "descriptor"):
            self.registry(create_new=False)

    def test_audit_binds_scope_order_indices_rows_and_receipts(self) -> None:
        rows = [_valid_result(post_id=101), _valid_result(post_id=102, candidate_title="작품 B")]
        registry = self.registry()
        receipts = []
        for index, row in enumerate(rows, 1):
            receipt, _ = commit_publication_result(
                row,
                registry=registry,
                attempt_run_id="attempt-1",
                input_index=index,
                post_id=row["post_id"],
            )
            receipts.append(receipt)

        report = audit_publication_commits(
            rows,
            receipts,
            expected_post_ids=[101, 102],
            expected_scope_id=self.scope,
        )

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["valid_commit_count"], 2)
        self.assertTrue(report["post_id_order_match"])
        self.assertTrue(report["input_indices_contiguous"])
        self.assertTrue(report["scope_match"])

    def test_audit_rejects_duplicate_rows_missing_receipt_and_mixed_scope(self) -> None:
        row = _valid_result(post_id=101)
        receipt = compute_publication_decision_commit(
            row,
            publication_scope_id=self.scope,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        other_scope = build_publication_scope_id(
            input_file_sha256="b" * 64,
            post_ids=[102],
            config_hash="config-v2",
        )
        other_row = _valid_result(post_id=102, candidate_title="작품 B")
        other_receipt = compute_publication_decision_commit(
            other_row,
            publication_scope_id=other_scope,
            attempt_run_id="attempt-2",
            input_index=2,
            post_id=102,
        )

        report = audit_publication_commits(
            [row, deepcopy(row), other_row],
            [receipt, other_receipt],
            expected_post_ids=[101, 102, 103],
            expected_scope_id=self.scope,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["duplicate_row_post_ids"], [101])
        self.assertEqual(report["missing_expected_post_ids"], [103])
        self.assertFalse(report["scope_match"])

    def test_noncontiguous_input_index_and_order_mismatch_are_no_go(self) -> None:
        first_row = _valid_result(post_id=101)
        second_row = _valid_result(post_id=102, candidate_title="작품 B")
        first = compute_publication_decision_commit(
            first_row,
            publication_scope_id=self.scope,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        second = compute_publication_decision_commit(
            second_row,
            publication_scope_id=self.scope,
            attempt_run_id="attempt-1",
            input_index=99,
            post_id=102,
        )

        report = audit_publication_commits(
            [first_row, second_row],
            [second, first],
            expected_post_ids=[101, 102],
            expected_scope_id=self.scope,
        )

        self.assertEqual(report["gate"], "NO-GO")
        self.assertFalse(report["input_indices_contiguous"])

    def test_scope_rejects_duplicate_post_ids(self) -> None:
        with self.assertRaisesRegex(PublicationCommitError, "must be unique"):
            _scope_id((101, 101))

    def test_canonical_publish_envelope_learns_alias_author_character_after_commit_and_replay(
        self,
    ) -> None:
        pipeline = AgenticPipeline(llm=_DummyLLM(), mcp=_DummyMCP())
        envelope = pipeline._build_batch_context_learning_envelope(_EnvelopeContext())
        serialized_model = PickvelOutputItemV2(
            post_id=101,
            identity={"is_relevant": True},
            batch_context_learning_envelope=envelope,
        ).model_dump()
        canonical_result = _valid_result(
            post_id=101,
            publish=True,
            candidate_title="정식 작품",
        )
        canonical_result["analysis_result"]["batch_context_learning_envelope"] = (
            serialized_model["batch_context_learning_envelope"]
        )
        registry = self.registry()
        receipt, created = commit_publication_result(
            canonical_result,
            registry=registry,
            attempt_run_id="attempt-1",
            input_index=1,
            post_id=101,
        )
        stored_result = registry.result(101)

        memory = BatchContextMemory(enabled=True)
        learned = expert_main._learn_batch_context_from_canonical_publication(
            memory,
            stored_result,
            receipt,
            created=created,
        )

        self.assertTrue(learned)
        self.assertEqual(memory.get_abbreviation("작품약칭"), "정식 작품")
        self.assertEqual(memory.get_author_works("테스트 작가")["title"], "정식 작품")
        self.assertEqual(memory.get_character_work("주인공"), "정식 작품")

        reloaded = self.registry(create_new=False)
        replay_result = reloaded.result(101)
        replay_receipt = reloaded.receipts()[0]
        replay_memory = BatchContextMemory(enabled=True)
        replay_learned = expert_main._learn_batch_context_from_canonical_publication(
            replay_memory,
            replay_result,
            replay_receipt,
            created=True,
        )

        self.assertTrue(replay_learned)
        self.assertEqual(replay_memory.get_abbreviation("작품약칭"), "정식 작품")
        self.assertEqual(
            replay_memory.get_author_works("테스트 작가")["title"],
            "정식 작품",
        )
        self.assertEqual(replay_memory.get_character_work("주인공"), "정식 작품")

    def test_learning_envelope_is_bounded_allowlisted_json_safe_and_omits_namu_raw(self) -> None:
        pipeline = AgenticPipeline(llm=_DummyLLM(), mcp=_DummyMCP())
        envelope = pipeline._build_batch_context_learning_envelope(_EnvelopeContext())
        serialized = json.dumps(envelope, ensure_ascii=False, sort_keys=True)

        self.assertEqual(
            envelope["schema_version"],
            BATCH_CONTEXT_LEARNING_ENVELOPE_SCHEMA,
        )
        self.assertEqual(
            set(envelope),
            {
                "schema_version",
                "decoded_terms",
                "identified_author",
                "identified_characters",
            },
        )
        self.assertEqual(
            envelope["decoded_terms"],
            [
                {
                    "original": "작품약칭",
                    "source_role": "work_alias",
                    "best_match": {"title": "정식 작품"},
                }
            ],
        )
        self.assertEqual(envelope["identified_author"], "테스트 작가")
        self.assertEqual(
            len(envelope["identified_characters"]),
            BATCH_CONTEXT_LEARNING_MAX_CHARACTERS,
        )
        self.assertEqual(envelope["identified_characters"].count("주인공"), 1)
        for forbidden in (
            "DO_NOT_PERSIST",
            "raw_prompt",
            "raw_snippet",
            "fetched_page_info",
            "namu.wiki",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_learning_envelope_assignment_is_validated_and_bounded(self) -> None:
        result = PickvelOutputItemV2(
            post_id=101,
            identity={"is_relevant": True},
        )
        with self.assertRaises(ValueError):
            result.batch_context_learning_envelope = {
                "schema_version": "untrusted_schema",
                "raw_prompt": "DO_NOT_PERSIST",
            }

        result.batch_context_learning_envelope = {
            "schema_version": BATCH_CONTEXT_LEARNING_ENVELOPE_SCHEMA,
            "decoded_terms": [],
            "identified_author": "가" * 1000,
            "identified_characters": [],
            "raw_prompt": "DO_NOT_PERSIST",
        }
        envelope = result.model_dump()["batch_context_learning_envelope"]
        self.assertIsNotNone(envelope)
        self.assertNotIn("raw_prompt", envelope)
        self.assertLess(len(envelope["identified_author"]), 1000)

    def test_non_publish_candidate_and_duplicate_results_do_not_learn_batch_context(self) -> None:
        cases = [
            (
                "hold",
                _valid_result(post_id=101, publish=False),
                SimpleNamespace(outcome="HOLD", publish_allowed=False),
                True,
            ),
            (
                "error_hold",
                {"post_id": 101, "error": "provider failed"},
                SimpleNamespace(outcome="ERROR_HOLD", publish_allowed=False),
                True,
            ),
            (
                "candidate_only",
                {
                    "post_id": 101,
                    "analysis_result": {
                        "identity": {
                            "is_relevant": True,
                            "candidate_title": "검증 전 후보",
                            "promotion_decision": {"publish_allowed": False},
                        }
                    },
                },
                SimpleNamespace(outcome="HOLD", publish_allowed=False),
                True,
            ),
            (
                "duplicate_same_run",
                _valid_result(post_id=101, publish=True),
                SimpleNamespace(outcome="PUBLISH", publish_allowed=True),
                False,
            ),
        ]

        for label, result, receipt, created in cases:
            with self.subTest(label=label):
                analysis_result = result.setdefault("analysis_result", {})
                analysis_result["batch_context_learning_envelope"] = {
                    "schema_version": BATCH_CONTEXT_LEARNING_ENVELOPE_SCHEMA,
                    "decoded_terms": [
                        {
                            "original": "차단약칭",
                            "best_match": {"title": "차단 작품"},
                        }
                    ],
                    "identified_author": "차단 작가",
                    "identified_characters": ["차단 인물"],
                }
                memory = _RecordingBatchContext()
                learned = expert_main._learn_batch_context_from_canonical_publication(
                    memory,
                    result,
                    receipt,
                    created=created,
                )
                self.assertFalse(learned)
                self.assertEqual(memory.learned, [])
                self.assertEqual(memory.learning_kwargs, [])

    def test_pipeline_inline_batch_context_learning_requires_explicit_opt_in(self) -> None:
        memory = _RecordingBatchContext()
        pipeline = AgenticPipeline(
            llm=_DummyLLM(),
            mcp=_DummyMCP(),
            parallel_count=2,
            batch_context=memory,
            batch_context_learning_enabled=False,
        )
        self.assertFalse(pipeline.batch_context_learning_enabled)
        default_pipeline = AgenticPipeline(llm=_DummyLLM(), mcp=_DummyMCP())
        self.assertFalse(default_pipeline.batch_context_learning_enabled)

        ctx = SimpleNamespace()
        result = SimpleNamespace(identity=SimpleNamespace(is_relevant=True))
        post = SimpleNamespace(post_id=301, title="테스트")
        with patch.object(pipeline.orchestrator, "process", return_value=ctx), patch.object(
            pipeline, "_post_to_dict", return_value={}
        ), patch.object(pipeline, "_extract_comments", return_value=[]), patch.object(
            pipeline, "_maybe_enrich_post_images", return_value={}
        ), patch.object(pipeline, "_context_to_output", return_value=result), patch.object(
            pipeline, "_learn_batch_context"
        ) as learn, patch.object(pipeline, "_log_result"), patch.object(
            pipeline, "_append_active_learning_queue"
        ):
            pipeline.process_post(post)
            learn.assert_not_called()

            pipeline.batch_context_learning_enabled = True
            pipeline.process_post(post)
            learn.assert_called_once_with(ctx, result)

    def test_post_commit_batch_context_learning_drains_in_input_order(self) -> None:
        memory = _RecordingBatchContext()
        pending = {}
        publish = SimpleNamespace(outcome="PUBLISH", publish_allowed=True)
        hold = SimpleNamespace(outcome="HOLD", publish_allowed=False)
        second = _valid_result(post_id=102, publish=True, candidate_title="두 번째")
        first = _valid_result(post_id=101, publish=False, candidate_title="첫 번째")

        pending[2] = (second, publish, True)
        next_index = expert_main._drain_ordered_batch_context_learning(
            memory,
            pending,
            next_input_index=1,
        )
        self.assertEqual(next_index, 1)
        self.assertEqual(memory.learned, [])

        pending[1] = (first, hold, True)
        next_index = expert_main._drain_ordered_batch_context_learning(
            memory,
            pending,
            next_input_index=next_index,
        )
        self.assertEqual(next_index, 3)
        self.assertEqual(
            [row["post_id"] for row in memory.learned],
            [102],
        )
        self.assertEqual(pending, {})

    def test_expert_main_factory_and_restart_replay_use_post_commit_learning(self) -> None:
        source = inspect.getsource(expert_main.main)
        factory_source = source[
            source.index("def _create_pipeline") : source.index(
                "def _decision_call_row_attempt_id"
            )
        ]
        replay_source = source[
            source.index("for _replay_index, (_replay_result, _replay_receipt) in sorted") :
            source.index("def _finalize_slang_db")
        ]
        commit_source = source[
            source.index("def _commit_final_result") : source.index("# 📊 대시보드: batch_start")
        ]

        self.assertIn("batch_context=_batch_context", factory_source)
        self.assertIn("batch_context_learning_enabled=False", factory_source)
        self.assertIn("_queue_batch_context_publication_learning", replay_source)
        self.assertIn("created=True", replay_source)
        self.assertNotIn("_batch_context.learn_from_result", replay_source)
        self.assertIn("_queue_batch_context_publication_learning", commit_source)
        self.assertIn("created=created", commit_source)


if __name__ == "__main__":
    unittest.main()
