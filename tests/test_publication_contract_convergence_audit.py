import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from llm_batch.promotion_gate import (
    candidate_inventory_evidence_from_sources,
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)
from tools.audit_publication_contract_convergence import (
    audit_rows,
    build_result_artifact_binding,
)


def _typed_row(state, evidence, *, identity_fields=None):
    identity = dict(identity_fields or {})
    contract = evaluate_publish_contract(state, evidence)
    apply_publish_contract(identity, contract)
    return {
        "post_id": state.post_id,
        "analysis_result": {"identity": identity},
    }


def _converged_publish_row():
    title = "이 무림의 미친년은 나야"
    url = "https://novelpia.com/novel/217943"
    state = GroundingState(
        post_id=11674712,
        candidate_title=title,
        candidate_url=url,
        source="publication_contract_test",
        official_title_exists=True,
        row_discusses_work_as_work=True,
        title_resolution_state="resolved",
        work_resolution="resolved",
        scope=ScopeState(
            scope_kind="current_work",
            confidence="high",
            direct_bridge_sources=["explicit_alias_relation", "official_detail_url"],
        ),
    )
    return _typed_row(
        state,
        [
            EvidenceRecord(
                kind="alias_bridge",
                source_path_or_snippet=title,
                supports_publish=True,
                reason_code="explicit_alias_relation",
                candidate_title=title,
            ),
            EvidenceRecord(
                kind="official_detail_url",
                source_path_or_snippet=url,
                reason_code="official_detail_url",
                candidate_title=title,
                candidate_url=url,
                title_url_match=True,
            ),
        ],
        identity_fields={"novel_identity": {"confidence": "High"}},
    )


def _converged_scrubbed_candidate_row():
    title = "아카데미 생존 갤러리"
    url = "https://novelpia.com/novel/380218"
    state = GroundingState(
        post_id=11698880,
        candidate_title=title,
        candidate_url=url,
        source="serialized_public_identity",
        official_title_exists=True,
        row_discusses_work_as_work=False,
        title_resolution_state="context_only",
        work_resolution="unresolved",
        scope=ScopeState(
            scope_kind="context_only",
            confidence="medium",
            direct_bridge_sources=["alias_surface"],
            conflict_reason_codes=["scope_contract_unit"],
        ),
    )
    return _typed_row(
        state,
        [
            EvidenceRecord(
                kind="candidate_surface",
                source_path_or_snippet="아생갤",
                supports_publish=False,
                reason_code="serialized_public_identity_scrubbed",
                candidate_title=title,
            )
        ],
    )


def _verified_image_ocr_blocked_row():
    scope = {
        "scope_kind": "current_work",
        "confidence": "high",
        "direct_bridge_sources": [
            "direct_image_work_surface_lock",
            "structured_direct_image_work_surface",
            "ocr_catalog_official_title",
        ],
    }
    decision = {
        "status": "candidate_only",
        "publish_allowed": False,
        "official_title": None,
        "official_url": None,
        "candidate_preserved": True,
        "reason_codes": [
            "official_title_exists",
            "row_discusses_work_as_work",
            "scope_current_work",
            "direct_image_work_surface_bridge",
            "ocr_catalog_official_title",
            "precision_seed_official_title_requires_review",
            "serialized_public_identity_scrubbed",
        ],
        "bypassed_gate": False,
        "scope": scope,
    }
    pre_gate = {
        "official_title": "밀리언 클래스",
        "official_url": None,
        "source": "candidate_ledger_or_serialized_identity",
    }
    post_gate = {
        "official_title": None,
        "official_url": None,
        "candidate_ledger_status": "promotion_blocked",
    }
    trace = {
        "pre_gate_candidate": pre_gate,
        "gate_decision": decision,
        "scope_state": scope,
        "post_gate_identity": post_gate,
        "reason_codes": decision["reason_codes"],
        "bypassed_gate": False,
    }
    publish_ledger = {
        "candidate_preservation": pre_gate,
        "public_publish": post_gate,
        "gate_decision": decision,
    }
    return {
        "post_id": 11684372,
        "analysis_result": {
            "identity": {
                "candidate_ledger_status": "promotion_blocked",
                "blocked_official_title": "밀리언 클래스",
                "context_sources": ["title", "body", "comments", "search", "image"],
                "image_evidence_catalog": [
                    {
                        "promotion_eligible": True,
                        "title_role": "work_title",
                        "evidence_type": "explicit_text",
                        "explicit_work_title": "밀리언 클래스",
                    }
                ],
                "promotion_decision": decision,
                "publish_contract_trace": trace,
                "publish_ledger": publish_ledger,
                "candidate_ledger": {
                    "candidate_ledger_status": "promotion_blocked",
                    "blocked_official_title": "밀리언 클래스",
                    "image_evidence_catalog": [
                        {
                            "promotion_eligible": True,
                            "title_role": "work_title",
                            "evidence_type": "explicit_text",
                            "explicit_work_title": "밀리언 클래스",
                        }
                    ],
                    "promotion_decision": decision,
                    "promotion_gate_state": {
                        "candidate_title": "밀리언 클래스",
                        "candidate_url": "",
                        "official_title_exists": True,
                        "row_discusses_work_as_work": True,
                        "scope": scope,
                    },
                    "publish_contract_trace": trace,
                    "publish_ledger": publish_ledger,
                },
            }
        },
    }


def _verified_image_ocr_publish_row():
    title = "밀리언 클래스"
    state = GroundingState(
        post_id=11684372,
        candidate_title=title,
        source="direct_image_work_surface_lock",
        official_title_exists=True,
        row_discusses_work_as_work=True,
        title_resolution_state="resolved",
        work_resolution="resolved",
        scope=ScopeState(
            scope_kind="current_work",
            confidence="high",
            direct_bridge_sources=[
                "direct_image_work_surface_bridge",
                "ocr_catalog_official_title",
                "verified_image_ocr_work_title_publication",
            ],
        ),
    )
    return _typed_row(
        state,
        [
            EvidenceRecord(
                kind="ocr_catalog_official_title",
                source_path_or_snippet=title,
                supports_publish=True,
                reason_code="ocr_catalog_official_title",
                candidate_title=title,
            ),
            EvidenceRecord(
                kind="direct_image_work_surface",
                source_path_or_snippet=title,
                supports_publish=True,
                reason_code="direct_image_work_surface_bridge",
                candidate_title=title,
            ),
            EvidenceRecord(
                kind="verified_image_ocr_work_title_publication",
                source_path_or_snippet=title,
                supports_publish=True,
                reason_code="verified_image_ocr_work_title_publication",
                candidate_title=title,
            ),
        ],
        identity_fields={
            "novel_identity": {"confidence": "High"},
            "image_evidence_catalog": [
                {
                    "promotion_eligible": True,
                    "title_role": "work_title",
                    "evidence_type": "explicit_text",
                    "explicit_work_title": title,
                }
            ],
        },
    )


class PublicationContractConvergenceAuditTest(unittest.TestCase):
    def test_duplicate_non_empty_post_id_is_never_go(self):
        row = _converged_publish_row()
        report = audit_rows([row, copy.deepcopy(row)])

        self.assertEqual(report["gate"], "NO-GO")
        self.assertEqual(report["exact_once"]["status"], "NOT_PROVABLE")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("duplicate_post_id", codes)

    def test_typed_state_post_id_must_match_row_post_id(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        identity["promotion_gate_state"]["post_id"] = 999999

        report = audit_rows([row])
        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("typed_state_post_id_mismatch", codes)

    def test_expected_post_id_scope_reports_missing_orphan_and_duplicate(self):
        row = _converged_publish_row()
        report = audit_rows(
            [row, copy.deepcopy(row)],
            expected_post_ids=[row["post_id"], 12345, row["post_id"]],
        )

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("expected_post_id_missing", codes)
        self.assertIn("expected_post_id_duplicate", codes)
    def test_result_artifact_binding_records_exact_file_identity(self):
        payload = {"results": [_converged_publish_row()]}
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result.json"
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            path.write_bytes(raw)

            binding = build_result_artifact_binding(path, row_count=1)

        self.assertEqual(binding["path"], str(path))
        self.assertEqual(binding["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(binding["size_bytes"], len(raw))
        self.assertEqual(binding["row_count"], 1)

    def test_converged_publish_contract_is_go(self):
        report = audit_rows([_converged_publish_row()])

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)

    def test_forged_self_consistent_decision_is_rejected_by_shadow_recompute(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        forged = {
            **identity["promotion_decision"],
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
        }
        identity["promotion_decision"] = forged
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": forged,
            "post_gate_identity": {
                **identity["publish_contract_trace"]["post_gate_identity"],
                "official_title": None,
                "official_url": None,
                "title_resolution_allowed": False,
                "candidate_ledger_status": "promotion_blocked",
            },
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": forged,
            "public_publish": identity["publish_contract_trace"]["post_gate_identity"],
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": forged,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }
        identity["novel_identity"]["official_title"] = None
        identity["novel_identity"]["heretic_url"] = None

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("promotion_decision_shadow_recompute_mismatch", codes)

    def test_forged_fingerprint_and_contract_version_are_rejected(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        identity["publish_contract_input_fingerprint"] = "0" * 64
        identity["publish_contract_version"] = "promotion_contract_v1"

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("authoritative_publish_contract_missing", codes)
        self.assertIn("publish_contract_input_fingerprint_mismatch", codes)

    def test_candidate_ledger_must_mirror_all_typed_contract_inputs(self):
        mutations = {
            "state": (
                "candidate_ledger_promotion_gate_state_mismatch",
                lambda ledger: ledger.__setitem__(
                    "promotion_gate_state",
                    {**ledger["promotion_gate_state"], "post_id": 999},
                ),
            ),
            "evidence": (
                "candidate_ledger_promotion_gate_evidence_mismatch",
                lambda ledger: ledger.__setitem__(
                    "promotion_gate_evidence",
                    [*ledger["promotion_gate_evidence"], {"kind": "forged"}],
                ),
            ),
            "version": (
                "candidate_ledger_publish_contract_version_mismatch",
                lambda ledger: ledger.__setitem__(
                    "publish_contract_version", "promotion_contract_v1"
                ),
            ),
            "fingerprint": (
                "candidate_ledger_publish_contract_input_fingerprint_mismatch",
                lambda ledger: ledger.__setitem__(
                    "publish_contract_input_fingerprint", "0" * 64
                ),
            ),
        }
        for name, (expected_code, mutate) in mutations.items():
            with self.subTest(field=name):
                row = _converged_publish_row()
                mutate(row["analysis_result"]["identity"]["candidate_ledger"])
                report = audit_rows([row])
                codes = {
                    violation["code"]
                    for row_report in report["violations"]
                    for violation in row_report["violations"]
                }
                self.assertEqual(report["gate"], "NO-GO")
                self.assertIn(expected_code, codes)

    def test_noncanonical_candidate_inventory_count_is_no_go_without_crash(self):
        sources = [{"official_title": "후보 A"}]
        evidence = candidate_inventory_evidence_from_sources(sources)
        for invalid in ("", "01", 1.9, True, -1):
            with self.subTest(value=invalid):
                row = _typed_row(
                    GroundingState(
                        post_id=11700470,
                        candidate_title="",
                        candidate_inventory_count=1,
                    ),
                    evidence,
                    identity_fields={
                        "title_candidates": list(sources),
                        "candidate_ledger": {
                            "candidate_preservation_sources": list(sources),
                        },
                    },
                )
                identity = row["analysis_result"]["identity"]
                identity["promotion_gate_state"]["candidate_inventory_count"] = invalid
                identity["candidate_ledger"]["promotion_gate_state"][
                    "candidate_inventory_count"
                ] = invalid

                report = audit_rows([row])
                codes = {
                    violation["code"]
                    for row_report in report["violations"]
                    for violation in row_report["violations"]
                }
                self.assertEqual(report["gate"], "NO-GO")
                self.assertIn("candidate_inventory_count_invalid_type", codes)

    def test_self_consistent_forged_resolution_trace_is_rejected(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        forged_fields = {
            "title_resolution_allowed": False,
            "title_resolution_state": "context_only",
            "work_resolution": "unresolved",
        }
        identity.update(forged_fields)
        identity["publish_contract_trace"]["post_gate_identity"].update(forged_fields)
        identity["publish_ledger"]["public_publish"].update(forged_fields)
        identity["candidate_ledger"].update(forged_fields)

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("post_gate_identity_title_resolution_allowed_shadow_mismatch", codes)
        self.assertIn("serialized_identity_title_resolution_state_shadow_mismatch", codes)
        self.assertIn("candidate_ledger_work_resolution_shadow_mismatch", codes)

    def test_blocked_contract_rejects_stale_root_public_surface(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        identity["official_title"] = "stale root title"

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("blocked_serialized_public_title_leak", codes)

    def test_semantic_query_identifier_is_not_dropped_during_url_pair_check(self):
        title = "테스트 작품"
        candidate_url = "https://series.naver.com/novel/detail.series?productNo=123"
        row = _typed_row(
            GroundingState(
                post_id=11663514,
                candidate_title=title,
                candidate_url=candidate_url,
                source="semantic_query_identifier_test",
                official_title_exists=True,
                row_discusses_work_as_work=True,
                scope=ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["explicit_alias_relation"],
                ),
            ),
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    source_path_or_snippet=title,
                    supports_publish=True,
                    candidate_title=title,
                ),
                EvidenceRecord(
                    kind="official_detail_url",
                    source_path_or_snippet=(
                        "https://series.naver.com/novel/detail.series?productNo=456"
                    ),
                    candidate_title=title,
                    candidate_url=(
                        "https://series.naver.com/novel/detail.series?productNo=456"
                    ),
                    title_url_match=True,
                ),
            ],
            identity_fields={"novel_identity": {"confidence": "High"}},
        )

        report = audit_rows([row])
        identity = row["analysis_result"]["identity"]

        self.assertEqual(report["gate"], "GO")
        self.assertTrue(identity["promotion_decision"]["publish_allowed"])
        self.assertIsNone(identity["promotion_decision"]["official_url"])
        self.assertIn(
            "official_url_evidence_missing",
            identity["promotion_decision"]["reason_codes"],
        )

    def test_scrubbed_blocked_candidate_preservation_contract_is_go(self):
        report = audit_rows([_converged_scrubbed_candidate_row()])

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)

    def test_verified_image_ocr_title_only_publication_contract_is_go(self):
        report = audit_rows([_verified_image_ocr_publish_row()])

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)

    def test_verified_image_ocr_work_title_blocked_by_precision_review_is_no_go(self):
        report = audit_rows([_verified_image_ocr_blocked_row()])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row in report["violations"]
            for violation in row["violations"]
        }
        self.assertIn("verified_image_ocr_work_title_blocked_by_precision_review", codes)

    def test_public_title_without_contract_is_no_go(self):
        report = audit_rows(
            [
                {
                    "post_id": 11660237,
                    "analysis_result": {
                        "identity": {
                            "novel_identity": {
                                "official_title": "테라포밍",
                                "heretic_url": "https://novel.munpia.com/416826",
                            }
                        }
                    },
                }
            ]
        )

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row in report["violations"]
            for violation in row["violations"]
        }
        self.assertIn("missing_publication_decision_for_public_identity", codes)

    def test_blocked_decision_with_stale_public_trace_is_no_go(self):
        blocked_decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": ["scope_context_only", "scope_not_current_work"],
            "bypassed_gate": False,
        }
        stale_publish_decision = {
            "status": "publish",
            "publish_allowed": True,
            "official_title": "가챠 중독자의 퓨전펑크 생활",
            "official_url": "https://novelpia.com/novel/387014",
            "candidate_preserved": False,
            "reason_codes": ["stale_publish"],
            "bypassed_gate": False,
        }
        stale_trace = {
            "pre_gate_candidate": {
                "official_title": "가챠 중독자의 퓨전펑크 생활",
                "official_url": "https://novelpia.com/novel/387014",
            },
            "gate_decision": stale_publish_decision,
            "post_gate_identity": {
                "official_title": "가챠 중독자의 퓨전펑크 생활",
                "official_url": "https://novelpia.com/novel/387014",
            },
        }
        stale_ledger = {
            "candidate_preservation": stale_trace["pre_gate_candidate"],
            "public_publish": stale_trace["post_gate_identity"],
            "gate_decision": stale_publish_decision,
        }
        report = audit_rows(
            [
                {
                    "post_id": 11698880,
                    "analysis_result": {
                        "identity": {
                            "novel_identity": {
                                "official_title": "가챠 중독자의 퓨전펑크 생활",
                                "heretic_url": "https://novelpia.com/novel/387014",
                            },
                            "promotion_decision": blocked_decision,
                            "publish_contract_trace": stale_trace,
                            "publish_ledger": stale_ledger,
                            "candidate_ledger": {
                                "promotion_decision": blocked_decision,
                                "publish_contract_trace": stale_trace,
                                "publish_ledger": stale_ledger,
                            },
                        }
                    },
                }
            ]
        )

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row in report["violations"]
            for violation in row["violations"]
        }
        self.assertIn("publish_contract_trace_gate_decision_mismatch", codes)
        self.assertIn("publish_ledger_gate_decision_mismatch", codes)
        self.assertIn("blocked_trace_publishes_title", codes)
        self.assertIn("blocked_ledger_publishes_title", codes)
        self.assertIn("blocked_serialized_public_title_leak", codes)

    def test_scrubbed_blocked_decision_requires_candidate_preservation(self):
        decision = {
            "status": "candidate_only",
            "publish_allowed": False,
            "official_title": None,
            "official_url": None,
            "candidate_preserved": True,
            "reason_codes": ["serialized_public_identity_scrubbed"],
            "bypassed_gate": False,
        }
        trace = {
            "gate_decision": decision,
            "post_gate_identity": {"official_title": None, "official_url": None},
            "reason_codes": decision["reason_codes"],
            "bypassed_gate": False,
        }
        publish_ledger = {
            "public_publish": trace["post_gate_identity"],
            "gate_decision": decision,
        }
        report = audit_rows(
            [
                {
                    "post_id": 11660271,
                    "analysis_result": {
                        "identity": {
                            "promotion_decision": decision,
                            "publish_contract_trace": trace,
                            "publish_ledger": publish_ledger,
                            "candidate_ledger": {
                                "promotion_decision": decision,
                                "publish_contract_trace": trace,
                                "publish_ledger": publish_ledger,
                            },
                        }
                    },
                }
            ]
        )

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row in report["violations"]
            for violation in row["violations"]
        }
        self.assertIn("blocked_candidate_preservation_missing", codes)

    def test_scrubbed_hold_without_candidates_is_converged_without_candidate_payload(self):
        row = _typed_row(
            GroundingState(
                post_id=11665122,
                candidate_title="",
                source="hold_without_candidates",
                official_title_exists=False,
                row_discusses_work_as_work=False,
                scope=ScopeState(
                    scope_kind="unknown",
                    confidence="low",
                    conflict_reason_codes=["hold_without_candidates"],
                ),
            ),
            [],
        )
        report = audit_rows([row])
        identity = row["analysis_result"]["identity"]

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)
        self.assertEqual(identity["candidate_ledger_status"], "hold_without_candidates")
        self.assertEqual(
            identity["publish_contract_trace"]["post_gate_identity"][
                "candidate_ledger_status"
            ],
            "hold_without_candidates",
        )
        self.assertEqual(
            identity["candidate_ledger"]["candidate_ledger_status"],
            "hold_without_candidates",
        )

    def test_inventory_only_typed_hold_is_converged(self):
        sources = [
            {"official_title": "후보 A", "heretic_url": "https://novelpia.com/novel/1001"},
            {"official_title": "후보 B"},
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)
        row = _typed_row(
            GroundingState(
                post_id=11700470,
                candidate_title="",
                source="serializer_missing_typed_contract",
                candidate_inventory_count=len(evidence),
            ),
            evidence,
            identity_fields={
                "title_candidates": list(sources),
                "candidate_ledger": {
                    "candidate_preservation_sources": list(sources),
                },
            },
        )

        report = audit_rows([row])
        identity = row["analysis_result"]["identity"]

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(identity["promotion_decision"]["status"], "candidate_only")
        self.assertTrue(identity["promotion_decision"]["candidate_preserved"])
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertIsNone(identity["novel_identity"]["official_title"])

    def test_inventory_count_evidence_mismatch_is_no_go(self):
        sources = [{"official_title": "후보 A"}]
        evidence = candidate_inventory_evidence_from_sources(sources)
        row = _typed_row(
            GroundingState(
                post_id=11700470,
                candidate_title="",
                candidate_inventory_count=2,
            ),
            evidence,
            identity_fields={
                "title_candidates": list(sources),
                "candidate_ledger": {
                    "candidate_preservation_sources": list(sources),
                },
            },
        )

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("candidate_inventory_count_evidence_mismatch", codes)

    def test_inventory_payload_mismatch_is_no_go(self):
        typed_sources = [{"official_title": "후보 A"}]
        actual_sources = [{"official_title": "후보 B"}]
        evidence = candidate_inventory_evidence_from_sources(typed_sources)
        row = _typed_row(
            GroundingState(
                post_id=11700470,
                candidate_title="",
                candidate_inventory_count=1,
            ),
            evidence,
            identity_fields={
                "title_candidates": list(actual_sources),
                "candidate_ledger": {
                    "candidate_preservation_sources": list(actual_sources),
                },
            },
        )

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("candidate_inventory_payload_mismatch", codes)

    def test_each_inventory_mirror_must_equal_typed_inventory(self):
        sources = [
            {"official_title": "후보 A", "heretic_url": "https://novelpia.com/novel/1001"},
            {"official_title": "후보 B", "heretic_url": "https://novelpia.com/novel/1002"},
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)

        for mirror_name in (
            "identity",
            "candidate_ledger",
        ):
            with self.subTest(mirror_name=mirror_name):
                row = _typed_row(
                    GroundingState(
                        post_id=20010067,
                        candidate_title="",
                        candidate_inventory_count=len(evidence),
                    ),
                    evidence,
                    identity_fields={
                        "title_candidates": list(sources),
                        "candidate_preservation_sources": list(sources),
                        "candidate_ledger": {
                            "title_candidates": list(sources),
                            "candidate_preservation_sources": list(sources),
                        },
                    },
                )
                identity = row["analysis_result"]["identity"]
                if mirror_name == "identity":
                    identity["title_candidates"] = [sources[0]]
                    identity["candidate_preservation_sources"] = [sources[0]]
                else:
                    identity["candidate_ledger"]["title_candidates"] = [sources[0]]
                    identity["candidate_ledger"]["candidate_preservation_sources"] = [
                        sources[0]
                    ]

                report = audit_rows([row])
                mirror_violations = [
                    violation
                    for row_report in report["violations"]
                    for violation in row_report["violations"]
                    if violation["code"]
                    == "candidate_inventory_mirror_payload_mismatch"
                ]

                self.assertEqual(report["gate"], "NO-GO")
                self.assertTrue(
                    any(mirror_name in violation["detail"] for violation in mirror_violations)
                )

    def test_inventory_group_allows_title_subset_with_complete_preservation_snapshot(self):
        sources = [
            {"official_title": "후보 A", "heretic_url": "https://novelpia.com/novel/1001"},
            {"official_title": "후보 B", "heretic_url": "https://novelpia.com/novel/1002"},
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)
        row = _typed_row(
            GroundingState(
                post_id=20010069,
                candidate_title="",
                candidate_inventory_count=len(evidence),
            ),
            evidence,
            identity_fields={
                "title_candidates": [sources[0]],
                "candidate_preservation_sources": list(sources),
            },
        )

        report = audit_rows([row])

        self.assertEqual(report["gate"], "GO")

    def test_inventory_group_allows_absent_identity_mirror_when_ledger_is_complete(self):
        sources = [
            {"official_title": "후보 A", "heretic_url": "https://novelpia.com/novel/1001"},
            {"official_title": "후보 B", "heretic_url": "https://novelpia.com/novel/1002"},
        ]
        evidence = candidate_inventory_evidence_from_sources(sources)
        row = _typed_row(
            GroundingState(
                post_id=20010070,
                candidate_title="",
                candidate_inventory_count=len(evidence),
            ),
            evidence,
            identity_fields={
                "candidate_ledger": {
                    "candidate_preservation_sources": list(sources),
                },
            },
        )

        report = audit_rows([row])

        self.assertEqual(report["gate"], "GO")

    def test_trace_and_publish_ledger_must_equal_shadow_contract(self):
        sources = [{"official_title": "후보 A"}]
        evidence = candidate_inventory_evidence_from_sources(sources)

        for mutation in ("trace_bypass", "candidate_preservation"):
            with self.subTest(mutation=mutation):
                row = _typed_row(
                    GroundingState(
                        post_id=20010068,
                        candidate_title="",
                        candidate_inventory_count=1,
                    ),
                    evidence,
                    identity_fields={
                        "title_candidates": list(sources),
                        "candidate_preservation_sources": list(sources),
                        "candidate_ledger": {
                            "candidate_preservation_sources": list(sources),
                        },
                    },
                )
                identity = row["analysis_result"]["identity"]
                trace = copy.deepcopy(identity["publish_contract_trace"])
                publish_ledger = copy.deepcopy(identity["publish_ledger"])
                if mutation == "trace_bypass":
                    trace["bypassed_gate"] = True
                else:
                    forged_candidate = {
                        "official_title": "위조 후보",
                        "official_url": "https://novelpia.com/novel/999999",
                    }
                    trace["pre_gate_candidate"] = dict(forged_candidate)
                    publish_ledger["candidate_preservation"] = dict(forged_candidate)
                identity["publish_contract_trace"] = copy.deepcopy(trace)
                identity["publish_ledger"] = copy.deepcopy(publish_ledger)
                identity["candidate_ledger"]["publish_contract_trace"] = copy.deepcopy(
                    trace
                )
                identity["candidate_ledger"]["publish_ledger"] = copy.deepcopy(
                    publish_ledger
                )

                report = audit_rows([row])
                codes = {
                    violation["code"]
                    for row_report in report["violations"]
                    for violation in row_report["violations"]
                }

                self.assertEqual(report["gate"], "NO-GO")
                self.assertIn(
                    "publish_contract_trace_shadow_recompute_mismatch",
                    codes,
                )
                if mutation == "candidate_preservation":
                    self.assertIn(
                        "publish_ledger_shadow_recompute_mismatch",
                        codes,
                    )

    def test_candidate_ledger_cannot_replace_missing_identity_authority(self):
        fields_by_case = {
            "decision": ("promotion_decision",),
            "trace": ("publish_contract_trace",),
            "ledger": ("publish_ledger",),
            "all": (
                "promotion_decision",
                "publish_contract_trace",
                "publish_ledger",
            ),
        }
        expected_code = {
            "promotion_decision": "identity_promotion_decision_missing",
            "publish_contract_trace": "identity_publish_contract_trace_missing",
            "publish_ledger": "identity_publish_ledger_missing",
        }

        for case_name, deleted_fields in fields_by_case.items():
            with self.subTest(case_name=case_name):
                row = _converged_publish_row()
                identity = row["analysis_result"]["identity"]
                for field in deleted_fields:
                    identity.pop(field)

                report = audit_rows([row])
                codes = {
                    violation["code"]
                    for row_report in report["violations"]
                    for violation in row_report["violations"]
                }

                self.assertEqual(report["gate"], "NO-GO")
                for field in deleted_fields:
                    self.assertIn(expected_code[field], codes)

    def test_v2_decision_missing_on_both_mirrors_never_early_returns_go(self):
        for mutation in (
            "missing",
            "non_dict",
            "stripped_versions_and_decisions",
            "partial_v2_residue_without_decision_version_trace",
        ):
            with self.subTest(mutation=mutation):
                row = _converged_scrubbed_candidate_row()
                identity = row["analysis_result"]["identity"]
                ledger = identity["candidate_ledger"]
                if mutation == "non_dict":
                    identity["promotion_decision"] = []
                    ledger["promotion_decision"] = []
                else:
                    identity.pop("promotion_decision")
                    ledger.pop("promotion_decision")
                if mutation in {
                    "stripped_versions_and_decisions",
                    "partial_v2_residue_without_decision_version_trace",
                }:
                    identity.pop("publish_contract_version")
                    ledger.pop("publish_contract_version")
                if mutation == "partial_v2_residue_without_decision_version_trace":
                    identity.pop("publish_contract_trace")
                    ledger.pop("publish_contract_trace")

                report = audit_rows([row])
                codes = {
                    violation["code"]
                    for row_report in report["violations"]
                    for violation in row_report["violations"]
                }

                self.assertEqual(report["gate"], "NO-GO")
                self.assertIn("identity_promotion_decision_missing", codes)
                self.assertIn("candidate_ledger_promotion_decision_missing", codes)

    def test_complete_contract_stripping_never_downgrades_to_legacy_go(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        ledger = identity["candidate_ledger"]
        for container in (identity, ledger):
            for field in (
                "promotion_decision",
                "promotion_gate_state",
                "promotion_gate_evidence",
                "publish_contract_trace",
                "publish_ledger",
                "publish_contract_input_fingerprint",
                "publish_contract_version",
            ):
                container.pop(field, None)

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("missing_authoritative_promotion_decision", codes)

    def test_titleless_url_only_pre_gate_still_audits_inventory_payload(self):
        typed_sources = [{"official_title": "후보 A"}]
        actual_sources = [{"official_title": "후보 B"}]
        evidence = candidate_inventory_evidence_from_sources(typed_sources)
        row = _typed_row(
            GroundingState(
                post_id=20010062,
                candidate_title="",
                candidate_url="https://novelpia.com/novel/900062",
                candidate_inventory_count=1,
            ),
            evidence,
            identity_fields={
                "title_candidates": list(actual_sources),
                "candidate_ledger": {
                    "candidate_preservation_sources": list(actual_sources),
                },
            },
        )

        report = audit_rows([row])
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }

        self.assertEqual(report["gate"], "NO-GO")
        self.assertIn("candidate_inventory_payload_mismatch", codes)

    def test_titleless_url_only_candidate_is_preserved_and_converged(self):
        row = _typed_row(
            GroundingState(
                post_id=20010066,
                candidate_title="",
                candidate_url="https://novelpia.com/novel/900066",
            ),
            [],
        )

        report = audit_rows([row])
        identity = row["analysis_result"]["identity"]

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(identity["promotion_decision"]["status"], "candidate_only")
        self.assertFalse(identity["promotion_decision"]["publish_allowed"])
        self.assertTrue(identity["promotion_decision"]["candidate_preserved"])
        self.assertFalse(identity["promotion_decision"]["bypassed_gate"])
        self.assertEqual(identity["candidate_ledger_status"], "promotion_blocked")
        self.assertEqual(
            identity["blocked_official_title_url"],
            "https://novelpia.com/novel/900066",
        )

    def test_scrubbed_decision_must_mark_candidate_preserved(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["candidate_preserved"] = False
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("scrubbed_decision_not_candidate_preserved", codes)

    def test_candidate_preservation_trace_and_ledger_must_match(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        publish_ledger = dict(identity["publish_ledger"])
        publish_ledger["candidate_preservation"] = {
            "official_title": "다른 후보",
            "official_url": "https://example.test/other",
        }
        identity["publish_ledger"] = publish_ledger
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "publish_ledger": publish_ledger,
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("candidate_preservation_trace_ledger_mismatch", codes)

    def test_scope_state_must_match_promotion_decision_scope(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "scope_state": {
                "scope_kind": "current_work",
                "confidence": "high",
            },
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "publish_contract_trace": identity["publish_contract_trace"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("publish_contract_trace_scope_state_mismatch", codes)

    def test_scope_kind_requires_matching_reason_code(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["reason_codes"] = [
            "scope_not_current_work",
            "serialized_public_identity_scrubbed",
        ]
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("promotion_decision_scope_reason_missing", codes)

    def test_non_current_scope_cannot_carry_current_work_reason(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["reason_codes"] = [
            "scope_context_only",
            "scope_current_work",
            "serialized_public_identity_scrubbed",
            "serialized_public_identity_published",
        ]
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("scope_non_current_conflicts_with_current_reason", codes)
        self.assertIn("blocked_non_current_scope_missing_not_current_reason", codes)
        self.assertIn("blocked_decision_has_publish_only_reason", codes)
        self.assertIn("published_and_scrubbed_reason_conflict", codes)

    def test_publish_allowed_requires_current_work_scope(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        scope = {"scope_kind": "context_only", "confidence": "medium"}
        decision = {
            **identity["promotion_decision"],
            "scope": scope,
            "reason_codes": ["scope_context_only", "row_discusses_work_as_work"],
        }
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "scope_state": scope,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("publish_allowed_non_current_scope", codes)

    def test_current_scope_reason_codes_cannot_mix_context_only_marker(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        scope = {"scope_kind": "current_work", "confidence": "high"}
        decision = {
            **identity["promotion_decision"],
            "scope": scope,
            "reason_codes": [
                "scope_current_work",
                "row_discusses_work_as_work",
                "context_only",
                "serialized_public_identity_scrubbed",
            ],
        }
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "scope_state": scope,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("mixed_current_noncurrent_scope_reason_codes", codes)

    def test_trace_reason_codes_cannot_add_noncurrent_marker_to_current_decision(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        decision = identity["promotion_decision"]
        trace = {
            **identity["publish_contract_trace"],
            "reason_codes": [
                *decision["reason_codes"],
                "scope_context_only",
            ],
        }
        identity["publish_contract_trace"] = trace
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "publish_contract_trace": trace,
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("mixed_current_noncurrent_scope_reason_codes", codes)

    def test_official_url_withheld_reason_allows_title_only_publication(self):
        title = "이 무림의 미친년은 나야"
        url = "https://novelpia.com/novel/217943?sid=main5"
        row = _typed_row(
            GroundingState(
                post_id=11674712,
                candidate_title=title,
                candidate_url=url,
                source="url_mismatch_title_only_test",
                official_title_exists=True,
                row_discusses_work_as_work=True,
                scope=ScopeState(
                    scope_kind="current_work",
                    confidence="high",
                    direct_bridge_sources=["explicit_alias_relation", "official_detail_url"],
                ),
            ),
            [
                EvidenceRecord(
                    kind="alias_bridge",
                    source_path_or_snippet=title,
                    supports_publish=True,
                    candidate_title=title,
                ),
                EvidenceRecord(
                    kind="official_detail_url",
                    source_path_or_snippet=url,
                    candidate_title=title,
                    candidate_url=url,
                    title_url_match=False,
                ),
            ],
            identity_fields={"novel_identity": {"confidence": "High"}},
        )

        report = audit_rows([row])

        self.assertEqual(report["gate"], "GO")
        self.assertEqual(report["summary"]["violation_row_count"], 0)

    def test_official_url_withheld_reason_must_not_publish_url(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        decision = dict(identity["promotion_decision"])
        decision["reason_codes"] = [
            *decision["reason_codes"],
            "official_url_withheld_by_title_mismatch",
        ]
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("official_url_withheld_reason_has_decision_url", codes)
        self.assertIn("official_url_withheld_reason_publishes_trace_url", codes)
        self.assertIn("official_url_withheld_reason_publishes_ledger_url", codes)
        self.assertIn("official_url_withheld_reason_serialized_url_leak", codes)

    def test_url_title_mismatch_block_reason_must_block_and_preserve_candidate_url(self):
        row = _converged_publish_row()
        identity = row["analysis_result"]["identity"]
        decision = {
            **identity["promotion_decision"],
            "reason_codes": [
                *identity["promotion_decision"]["reason_codes"],
                "url_title_mismatch",
                "official_detail_url_title_mismatch_publish_blocked",
            ],
        }
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = {
            **identity["publish_contract_trace"],
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        identity["publish_ledger"] = {
            **identity["publish_ledger"],
            "gate_decision": decision,
        }
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": identity["publish_contract_trace"],
            "publish_ledger": identity["publish_ledger"],
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("url_title_mismatch_block_reason_allows_publish", codes)
        self.assertIn("url_title_mismatch_block_reason_has_decision_url", codes)

    def test_url_title_mismatch_block_reason_requires_candidate_url_preservation(self):
        row = _converged_scrubbed_candidate_row()
        identity = row["analysis_result"]["identity"]
        decision = {
            **identity["promotion_decision"],
            "reason_codes": [
                *identity["promotion_decision"]["reason_codes"],
                "url_title_mismatch",
                "official_detail_url_title_mismatch_publish_blocked",
            ],
        }
        trace = {
            **identity["publish_contract_trace"],
            "pre_gate_candidate": {
                "official_title": "아카데미 생존 갤러리",
                "official_url": None,
                "source": "candidate_ledger_or_serialized_identity",
            },
            "gate_decision": decision,
            "reason_codes": decision["reason_codes"],
        }
        publish_ledger = {
            **identity["publish_ledger"],
            "candidate_preservation": trace["pre_gate_candidate"],
            "gate_decision": decision,
        }
        identity["blocked_official_title_url"] = None
        identity["candidate_ledger"]["blocked_official_title_url"] = None
        identity["promotion_decision"] = decision
        identity["publish_contract_trace"] = trace
        identity["publish_ledger"] = publish_ledger
        identity["candidate_ledger"] = {
            **identity["candidate_ledger"],
            "promotion_decision": decision,
            "publish_contract_trace": trace,
            "publish_ledger": publish_ledger,
        }

        report = audit_rows([row])

        self.assertEqual(report["gate"], "NO-GO")
        codes = {
            violation["code"]
            for row_report in report["violations"]
            for violation in row_report["violations"]
        }
        self.assertIn("url_title_mismatch_candidate_url_not_preserved", codes)


if __name__ == "__main__":
    unittest.main()
