from __future__ import annotations

import copy
import json
import stat
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
from tools.build_full375_search_adjudication_gate import (
    _canonical_hash,
    _search_health,
    _source_hash,
    _terminal_issues,
    build_terminal_packet,
)
from tools.build_search_terminal_consensus_ledger_v2 import (
    build_consensus,
    canonical_sha256,
    file_sha256,
    write_consensus_outputs,
)


def runtime_row(post_id: int) -> dict:
    scope = ScopeState(scope_kind="unknown", confidence="high")
    state = GroundingState(
        post_id=post_id,
        candidate_title=f"Candidate {post_id}",
        official_title_exists=True,
        row_discusses_work_as_work=False,
        scope=scope,
    )
    contract = evaluate_publish_contract(
        state,
        [
            EvidenceRecord(
                kind="candidate_surface",
                source_path_or_snippet=f"Candidate {post_id}",
                supports_publish=False,
                reason_code="unit_candidate_only",
                candidate_title=f"Candidate {post_id}",
            )
        ],
    )
    identity: dict = {}
    apply_publish_contract(identity, contract)
    health = {
        "queries_issued": 2,
        "upstream_zero": 0,
        "degraded": 1,
        "degraded_zero": 1,
        "degraded_recovered": 0,
        "unrecovered_degraded": 1,
        "status": "SEARCH_DEGRADED",
    }
    return {
        "post_id": post_id,
        "title": f"source {post_id}",
        "content": [f"body {post_id}"],
        "analysis_result": {"identity": {**identity, "search_health": health}},
        "run_meta": {"run_id": "unit-run", "search_health": copy.deepcopy(health)},
    }


class SearchTerminalConsensusLedgerV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        for path in self.root.rglob("*"):
            if path.is_file():
                try:
                    path.chmod(stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass
        self.temp.cleanup()

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def write_jsonl(path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )

    def fixture(self, name: str = "case") -> dict[str, object]:
        folder = self.root / name
        packet_path = folder / "packet.jsonl"
        template_path = folder / "template.jsonl"
        blind_path = folder / "blind.json"
        independent_path = folder / "independent.json"
        result_path = folder / "result.json"
        output_ledger = folder / "ledger.jsonl"
        output_report = folder / "report.json"
        output_md = folder / "report.md"

        results = [runtime_row(30), runtime_row(10), runtime_row(20)]
        self.write_json(result_path, results)
        packets = build_terminal_packet(results)
        self.write_jsonl(packet_path, packets)
        packet_hash = file_sha256(packet_path)
        packet_ref = {"path": packet_path.as_posix(), "sha256": packet_hash, "row_count": 3}

        templates: list[dict] = []
        for packet, result in zip(packets, results, strict=True):
            identity = result["analysis_result"]["identity"]
            source_hash = _source_hash(result)
            templates.append(
                {
                    "post_id": result["post_id"],
                    "search_status": "SEARCH_DEGRADED",
                    "source_hash": source_hash,
                    "input_hash": source_hash,
                    "terminal_label": None,
                    "classification": "safe_no_public_terminal",
                    "row_rationale": None,
                    "evidence_refs": [],
                    "before_after": {
                        "before": {"source_hash": source_hash},
                        "after": {
                            "official_title": None,
                            "official_url": None,
                            "publish_allowed": False,
                        },
                    },
                    "blind_verdict": {
                        "packet_ref": copy.deepcopy(packet_ref),
                        "packet_sha256": packet_hash,
                        "packet_row_sha256": packet["packet_row_sha256"],
                    },
                    "promotion_decision": copy.deepcopy(identity["promotion_decision"]),
                    "publish_contract_trace": copy.deepcopy(
                        identity["publish_contract_trace"]
                    ),
                    "test_replay_artifacts": [],
                    "attempted_lanes": [],
                    "missing_or_conflicting_evidence": [],
                    "search_health_snapshot_sha256": _canonical_hash(
                        _search_health(result)
                    ),
                    "candidate_unavailable_reason": None,
                    "publication_violation": False,
                    "unblock_condition": None,
                    "independent_review": None,
                }
            )
        self.write_jsonl(template_path, templates)

        safe_flags = [True, False, True]
        blind_rows: list[dict] = []
        independent_rows: list[dict] = []
        for row_number, (packet, template, result, safe) in enumerate(
            zip(packets, templates, results, safe_flags, strict=True), 1
        ):
            binding = {
                "packet_path": packet_path.as_posix(),
                "packet_sha256": packet_hash,
                "packet_row_number": row_number,
                "source_hash": packet["source_hash"],
                "packet_row_sha256": packet["packet_row_sha256"],
            }
            blind_rows.append(
                {
                    "post_id": packet["post_id"],
                    "classification": "safe_no_public_terminal" if safe else "blocker",
                    "terminal_label": "safe_no_public_terminal" if safe else None,
                    "terminal_safe": safe,
                    "rationale": "블라인드 source 판정 근거다.",
                    "evidence_basis": "source 및 search 관찰을 사용했다.",
                    "unblock_condition": "추가 공식 근거가 생기면 재검토한다.",
                    "binding": copy.deepcopy(binding),
                }
            )
            independent_rows.append(
                {
                    "post_id": packet["post_id"],
                    "terminal_safe": True,
                    "terminal_label": "INFO_MISSING",
                    "classification": "SAFE_INFO_MISSING",
                    "rationale": "public null 및 fail-closed 상태를 확인했다.",
                    "evidence_basis": ["runtime publication contract"],
                    "unblock_condition": "검색 근거 복구 전 차단을 유지한다.",
                    "packet_binding": copy.deepcopy(binding),
                    "template_row_sha256": canonical_sha256(template),
                    "result_row_sha256": canonical_sha256(result),
                }
            )

        self.write_json(
            blind_path,
            {
                "report_type": "blind-review",
                "reviewer": "blind-reviewer",
                "model": "codex-subagent",
                "run_id": "blind-run",
                "review_id": "blind-review-id",
                "review_scope": {
                    "packet_path": packet_path.as_posix(),
                    "packet_sha256": packet_hash,
                    "packet_row_count": 3,
                },
                "decisions": blind_rows,
            },
        )
        self.write_json(
            independent_path,
            {
                "report_type": "independent-review",
                "role": "independent_reviewer",
                "reviewer": "independent-reviewer",
                "review_id": "independent-review-id",
                "reviewed_at": "2026-07-10T20:00:00+09:00",
                "packet": copy.deepcopy(packet_ref),
                "template": {
                    "path": template_path.as_posix(),
                    "sha256": file_sha256(template_path),
                    "row_count": 3,
                },
                "runtime_result": {
                    "path": result_path.as_posix(),
                    "sha256": file_sha256(result_path),
                    "row_count": 3,
                },
                "rows": independent_rows,
            },
        )
        return {
            "paths": {
                "packet": packet_path,
                "template": template_path,
                "blind_review": blind_path,
                "independent_review": independent_path,
                "result": result_path,
            },
            "outputs": {
                "ledger": output_ledger,
                "report": output_report,
                "md": output_md,
            },
            "results": results,
            "packets": packets,
            "templates": templates,
            "expected_hashes": {
                "packet": file_sha256(packet_path),
                "template": file_sha256(template_path),
                "result": file_sha256(result_path),
            },
        }

    def build(self, fixture: dict[str, object]):
        paths = fixture["paths"]
        outputs = fixture["outputs"]
        assert isinstance(paths, dict) and isinstance(outputs, dict)
        return build_consensus(
            packet_path=paths["packet"],
            template_path=paths["template"],
            blind_review_path=paths["blind_review"],
            independent_review_path=paths["independent_review"],
            result_path=paths["result"],
            output_ledger_path=outputs["ledger"],
            output_report_path=outputs["report"],
            output_md_path=outputs["md"],
            expected_hashes=fixture["expected_hashes"],
            expected_packet_rows=3,
            expected_result_rows=3,
            expected_consensus_rows=2,
            expected_excluded_rows=1,
        )

    def refresh_result_binding(self, fixture: dict[str, object]) -> None:
        paths = fixture["paths"]
        assert isinstance(paths, dict)
        results = json.loads(paths["result"].read_text(encoding="utf-8"))
        independent = json.loads(paths["independent_review"].read_text(encoding="utf-8"))
        independent["runtime_result"]["sha256"] = file_sha256(paths["result"])
        independent["runtime_result"]["row_count"] = len(results)
        result_by_id = {str(row["post_id"]): row for row in results}
        for review_row in independent["rows"]:
            review_row["result_row_sha256"] = canonical_sha256(
                result_by_id[str(review_row["post_id"])]
            )
        self.write_json(paths["independent_review"], independent)
        fixture["expected_hashes"]["result"] = file_sha256(paths["result"])

    def test_happy_path_emits_only_two_review_intersection_and_satisfies_gate(self) -> None:
        fixture = self.fixture()
        rows, report, markdown = self.build(fixture)
        self.assertEqual([row["post_id"] for row in rows], [30, 20])
        self.assertEqual(report["counts"]["consensus_terminal_safe"], 2)
        self.assertEqual(report["counts"]["excluded"], 1)
        self.assertEqual(report["excluded_rows"][0]["post_id"], 10)
        self.assertEqual(report["excluded_rows"][0]["exclusion_reason"], "blind_blocker")
        self.assertEqual(report["terminal_consensus_gate"], "NO-GO")
        self.assertIn("Search terminal 합의 ledger", markdown.decode("utf-8"))
        result_by_id = {str(row["post_id"]): row for row in fixture["results"]}
        for row in rows:
            runtime = result_by_id[str(row["post_id"])]
            self.assertEqual(_terminal_issues(row, runtime, {
                "official_title": None,
                "official_url": None,
                "publish_allowed": False,
                "candidate_preserved": True,
                "decision_bypassed_gate": False,
                "trace_bypassed_gate": False,
                "decision": runtime["analysis_result"]["identity"]["promotion_decision"],
                "trace": runtime["analysis_result"]["identity"]["publish_contract_trace"],
            }), [])

    def test_packet_template_and_result_byte_hash_mismatches_fail_closed(self) -> None:
        for label in ("packet", "template", "result"):
            with self.subTest(label=label):
                fixture = self.fixture(f"hash-{label}")
                path = fixture["paths"][label]
                path.write_bytes(path.read_bytes() + b"\n")
                with self.assertRaisesRegex(ValueError, rf"{label} byte sha256 mismatch"):
                    self.build(fixture)

    def test_runtime_source_and_independent_row_hash_mismatches_fail_closed(self) -> None:
        fixture = self.fixture("source-row")
        path = fixture["paths"]["result"]
        results = json.loads(path.read_text(encoding="utf-8"))
        results[0]["title"] = "forged source"
        self.write_json(path, results)
        self.refresh_result_binding(fixture)
        with self.assertRaisesRegex(ValueError, "runtime result source_hash mismatch"):
            self.build(fixture)

        fixture = self.fixture("template-row")
        independent_path = fixture["paths"]["independent_review"]
        independent = json.loads(independent_path.read_text(encoding="utf-8"))
        independent["rows"][0]["template_row_sha256"] = "0" * 64
        self.write_json(independent_path, independent)
        with self.assertRaisesRegex(ValueError, "template row sha256 mismatch"):
            self.build(fixture)

        fixture = self.fixture("result-row")
        independent_path = fixture["paths"]["independent_review"]
        independent = json.loads(independent_path.read_text(encoding="utf-8"))
        independent["rows"][0]["result_row_sha256"] = "0" * 64
        self.write_json(independent_path, independent)
        with self.assertRaisesRegex(ValueError, "result row sha256 mismatch"):
            self.build(fixture)

    def test_duplicate_and_extra_review_ids_fail_closed(self) -> None:
        fixture = self.fixture("duplicate")
        path = fixture["paths"]["independent_review"]
        review = json.loads(path.read_text(encoding="utf-8"))
        review["rows"][1]["post_id"] = review["rows"][0]["post_id"]
        self.write_json(path, review)
        with self.assertRaisesRegex(ValueError, "duplicate post_id"):
            self.build(fixture)

        fixture = self.fixture("extra")
        path = fixture["paths"]["independent_review"]
        review = json.loads(path.read_text(encoding="utf-8"))
        review["rows"][1]["post_id"] = 999
        self.write_json(path, review)
        with self.assertRaisesRegex(ValueError, "post_id set mismatch.*extra"):
            self.build(fixture)

    def test_same_reviewer_identity_is_rejected(self) -> None:
        fixture = self.fixture("same-reviewer")
        path = fixture["paths"]["independent_review"]
        review = json.loads(path.read_text(encoding="utf-8"))
        review["reviewer"] = "blind-reviewer"
        self.write_json(path, review)
        with self.assertRaisesRegex(ValueError, "reviewer identities must differ"):
            self.build(fixture)

    def test_public_publish_and_bypass_unsafe_states_are_rejected(self) -> None:
        mutations = {
            "public": lambda identity: identity.__setitem__(
                "novel_identity", {"official_title": "Unsafe", "official_url": None}
            ),
            "publish": lambda identity: identity["promotion_decision"].__setitem__(
                "publish_allowed", True
            ),
            "bypass": lambda identity: identity["publish_contract_trace"].__setitem__(
                "bypassed_gate", True
            ),
        }
        expected = {
            "public": "public identity is not null",
            "publish": "publish_allowed is not false",
            "bypass": "bypassed_gate is not false",
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                fixture = self.fixture(f"unsafe-{label}")
                path = fixture["paths"]["result"]
                results = json.loads(path.read_text(encoding="utf-8"))
                mutate(results[0]["analysis_result"]["identity"])
                self.write_json(path, results)
                self.refresh_result_binding(fixture)
                with self.assertRaisesRegex(ValueError, expected[label]):
                    self.build(fixture)

    def test_candidate_preservation_missing_is_rejected(self) -> None:
        fixture = self.fixture("candidate")
        path = fixture["paths"]["result"]
        results = json.loads(path.read_text(encoding="utf-8"))
        results[0]["analysis_result"]["identity"]["promotion_decision"][
            "candidate_preserved"
        ] = False
        self.write_json(path, results)
        self.refresh_result_binding(fixture)
        with self.assertRaisesRegex(ValueError, "candidate preservation missing"):
            self.build(fixture)

    def test_forged_review_binding_is_rejected(self) -> None:
        fixture = self.fixture("forged")
        path = fixture["paths"]["blind_review"]
        review = json.loads(path.read_text(encoding="utf-8"))
        review["decisions"][0]["binding"]["packet_row_sha256"] = "0" * 64
        self.write_json(path, review)
        with self.assertRaisesRegex(ValueError, "packet row sha256 mismatch"):
            self.build(fixture)

    def test_outputs_are_exclusive_read_only_and_never_overwritten(self) -> None:
        fixture = self.fixture("outputs")
        rows, report, markdown = self.build(fixture)
        outputs = fixture["outputs"]
        write_consensus_outputs(
            rows=rows,
            report=report,
            markdown_bytes=markdown,
            output_ledger_path=outputs["ledger"],
            output_report_path=outputs["report"],
            output_md_path=outputs["md"],
        )
        for path in outputs.values():
            self.assertTrue(path.is_file())
            self.assertFalse(path.stat().st_mode & stat.S_IWUSR)
        with self.assertRaises(FileExistsError):
            write_consensus_outputs(
                rows=rows,
                report=report,
                markdown_bytes=markdown,
                output_ledger_path=outputs["ledger"],
                output_report_path=outputs["report"],
                output_md_path=outputs["md"],
            )


if __name__ == "__main__":
    unittest.main()
