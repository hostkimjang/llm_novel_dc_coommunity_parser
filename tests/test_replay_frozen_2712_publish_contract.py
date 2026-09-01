from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.llm_batch.promotion_gate import (
    EvidenceRecord,
    GroundingState,
    ScopeState,
    apply_publish_contract,
    evaluate_publish_contract,
)
from tools.replay_frozen_2712_publish_contract import replay_frozen_contract


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _identity(post_id: int, *, publish: bool) -> dict:
    state = GroundingState(
        post_id=post_id,
        candidate_title="정식 작품" if publish else "보존 후보",
        candidate_url=f"https://novelpia.com/novel/{post_id}",
        source="fixture",
        official_title_exists=publish,
        row_discusses_work_as_work=publish,
        title_resolution_state="resolved" if publish else "unresolved_matchable",
        work_resolution="resolved" if publish else "unresolved",
        scope=ScopeState(
            scope_kind="current_work" if publish else "unknown",
            confidence="high",
            direct_bridge_sources=("body",) if publish else (),
        ),
    )
    evidence = [
        EvidenceRecord(
            kind="body",
            strength="strong",
            source_path_or_snippet="body",
            supports_publish=publish,
            reason_code="body",
            candidate_title=state.candidate_title,
            candidate_url=state.candidate_url,
            title_url_match=True,
        )
    ]
    identity: dict = {"novel_identity": {"official_title": state.candidate_title, "heretic_url": state.candidate_url}}
    apply_publish_contract(identity, evaluate_publish_contract(state, evidence))
    return identity


def _ledger(
    post_id: int,
    verdict: str = "PASS",
    action: str = "KEEP",
    *,
    recommended_title: str | None = None,
    dashboard_title_expected: str | None = None,
) -> dict:
    if action in {"KEEP", "CORRECT"}:
        recommended_title = recommended_title or "정식 작품"
        dashboard_title_expected = dashboard_title_expected or recommended_title
    return {
        "post_id": str(post_id),
        "pipeline": {
            "publish_allowed": action == "KEEP",
            "official_title": recommended_title if action == "KEEP" else None,
        },
        "independent_semantic_verdict": {
            "review_verdict": verdict,
            "dashboard_action": action,
            "recommended_title": recommended_title,
            "dashboard_title_expected": dashboard_title_expected,
        },
    }


class FrozenPublishContractReplayTest(unittest.TestCase):
    def test_replays_root_and_explicit_candidate_ledger_fallback_without_semantic_labels_as_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _identity(1, publish=True)
            second = _identity(2, publish=False)
            nested = second["candidate_ledger"]
            for key in (
                "promotion_decision", "promotion_gate_state", "promotion_gate_evidence", "publish_contract_trace",
                "publish_ledger", "publish_contract_input_fingerprint", "publish_contract_version",
            ):
                second.pop(key, None)
            ledger = root / "ledger.jsonl"
            raw = root / "raw.json"
            _write_jsonl(ledger, [_ledger(1), _ledger(2, "WRONG_WORK", "HOLD")])
            _write_json(raw, [{"post_id": 1, "analysis_result": {"identity": first}}, {"post_id": 2, "analysis_result": {"identity": second}}])

            summary = replay_frozen_contract(ledger_path=ledger, raw_result_path=raw, output_dir=root / "out", profile="none")
            rows = [json.loads(line) for line in (root / "out/publish_contract_replay_rows.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual("GO", summary["gate"])
            self.assertEqual(2, summary["coverage"]["estimable_rows"])
            self.assertEqual(2, summary["contract_counts"]["legacy_semantic_publication_missing_neutral_compatibility"])
            self.assertEqual("identity", rows[0]["authoritative_source"])
            self.assertEqual("candidate_ledger", rows[1]["authoritative_source"])
            self.assertFalse(rows[1]["adjudication_used_as_production_input"])
            self.assertEqual("MATCH", rows[0]["comparison"]["public_projection"])
            self.assertEqual("MATCH", rows[1]["comparison"]["input_fingerprint"])
            self.assertEqual("COMPLIANT", rows[0]["stored"]["adjudication_compliant"])
            self.assertEqual(nested["promotion_gate_state"], second["candidate_ledger"]["promotion_gate_state"])

    def test_adjudicated_unsafe_is_separate_from_internal_contract_validity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = _identity(1, publish=True)
            ledger = root / "ledger.jsonl"
            raw = root / "raw.json"
            _write_jsonl(ledger, [_ledger(1, "WRONG_WORK", "HOLD")])
            _write_json(raw, [{"post_id": 1, "analysis_result": {"identity": identity}}])

            summary = replay_frozen_contract(ledger_path=ledger, raw_result_path=raw, output_dir=root / "out", profile="none")
            row = json.loads((root / "out/publish_contract_replay_rows.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(0, summary["contract_counts"]["stored_contract_internally_invalid"])
            self.assertEqual(0, summary["contract_counts"]["recomputed_contract_internally_invalid"])
            self.assertEqual(1, summary["adjudication_projection_counts"]["stored_adjudicated_unsafe_publish"])
            self.assertEqual(1, summary["adjudication_projection_counts"]["recomputed_adjudicated_unsafe_publish"])
            self.assertTrue(row["stored"]["adjudicated_unsafe_publish"])
            self.assertEqual("NONCOMPLIANT", row["recomputed"]["adjudication_compliant"])

    def test_duplicate_and_missing_post_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = _identity(1, publish=True)
            ledger = root / "ledger.jsonl"
            raw = root / "raw.json"
            _write_jsonl(ledger, [_ledger(1), _ledger(1)])
            _write_json(raw, [{"post_id": 1, "analysis_result": {"identity": identity}}])
            with self.assertRaisesRegex(ValueError, "duplicate post_id"):
                replay_frozen_contract(ledger_path=ledger, raw_result_path=raw, output_dir=root / "out", profile="none")
            _write_jsonl(ledger, [_ledger(2)])
            with self.assertRaisesRegex(ValueError, "missing ledger post_id"):
                replay_frozen_contract(ledger_path=ledger, raw_result_path=raw, output_dir=root / "out", profile="none")

    def test_invalid_persisted_state_is_not_estimable_without_inventing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = _identity(1, publish=True)
            identity["promotion_gate_state"] = {"post_id": "not-an-int"}
            identity["candidate_ledger"]["promotion_gate_state"] = {"post_id": "not-an-int"}
            ledger = root / "ledger.jsonl"
            raw = root / "raw.json"
            _write_jsonl(ledger, [_ledger(1)])
            _write_json(raw, [{"post_id": 1, "analysis_result": {"identity": identity}}])

            summary = replay_frozen_contract(ledger_path=ledger, raw_result_path=raw, output_dir=root / "out", profile="none")
            row = json.loads((root / "out/publish_contract_replay_rows.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("REVIEW", summary["gate"])
            self.assertEqual(1, summary["coverage"]["not_estimable_rows"])
            self.assertEqual("NOT_ESTIMABLE", row["replay_status"])
            self.assertTrue(row["not_estimable_reasons"][0].startswith("state_or_evidence_unparseable:"))

    def test_candidate_ledger_fallback_requires_its_own_v2_schema_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = _identity(1, publish=True)
            for key in (
                "promotion_decision", "promotion_gate_state", "promotion_gate_evidence", "publish_contract_trace",
                "publish_ledger", "publish_contract_input_fingerprint", "publish_contract_version",
            ):
                identity.pop(key, None)
            identity["candidate_ledger"].pop("publish_contract_version")
            ledger = root / "ledger.jsonl"
            raw = root / "raw.json"
            _write_jsonl(ledger, [_ledger(1)])
            _write_json(raw, [{"post_id": 1, "analysis_result": {"identity": identity}}])

            summary = replay_frozen_contract(ledger_path=ledger, raw_result_path=raw, output_dir=root / "out", profile="none")
            row = json.loads((root / "out/publish_contract_replay_rows.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("REVIEW", summary["gate"])
            self.assertEqual(["candidate_ledger_contract_not_authoritative_v2"], row["not_estimable_reasons"])
