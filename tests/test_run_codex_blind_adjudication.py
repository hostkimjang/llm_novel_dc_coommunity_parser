from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from tools.build_adjusted_collateral_adjudication import (
    blind_receipt_digest,
    validate_raw_codex_judge_artifact,
)
from tools.build_adjusted_collateral_blind_packet import (
    PACKET_VERSION,
    canonical_digest,
    packet_row_digest,
)
from tools.build_codex_cli_trust_anchor import (
    EXPECTED_CLI_VERSION,
    EXPECTED_MODEL_PROJECTION,
    EXPECTED_SIGNER_SUBJECT,
    EXPECTED_SIGNER_THUMBPRINT,
    PRODUCTION_EXECUTION_MODE,
    UNTRUSTED_EXECUTION_MODE,
    build_trust_anchor,
    write_json_exclusive,
)
from tools.run_codex_blind_adjudication import (
    ACTIVE_GOAL_ID,
    CONTINUATION_SOURCE_SESSION,
    MAX_PACKET_ROWS,
    PRODUCTION_MODEL,
    PRODUCTION_REASONING_EFFORT,
    RECEIPT_DIGEST_CONTRACT,
    RECEIPT_VERSION,
    RUNNER_SECURITY_DEPENDENCY_PATHS,
    RUNNER_VERSION,
    _artifact_paths,
    _assert_production_child_context,
    _build_session_bundle_stage,
    _execute_production_streaming,
    _prepare_isolated_environment,
    _run_blind_adjudication_core,
    _validate_packet_rows,
    _validate_model_response,
    build_allowed_evidence_contract,
    build_output_schema,
    build_prompt,
    enumerate_allowed_evidence_refs,
    receipt_payload_digest,
    run_blind_adjudication,
    validate_session_member_paths,
)


CODEX_THREAD_ID = "119f4850-7a35-7263-8347-362d7e553966"
GOLDEN_AUDIT_CONSTRAINT_SHA256 = "e" * 64


def make_packet(post_id: int) -> dict:
    source = {
        "gallery_id": "novel",
        "post_id": post_id,
        "title": f"source title {post_id}",
        "content": ["작품 A에 관해 직접 토론하는 원문이다."],
        "comments": [{"body": "작품 A가 맞다."}],
    }
    drift_id = canonical_digest(
        {
            "post_id": str(post_id),
            "status": "changed",
            "before_identity": {"official_title": "작품 A", "official_url": None},
            "after_identity": {"official_title": "작품 B", "official_url": None},
        }
    )
    row = {
        "packet_version": PACKET_VERSION,
        "packet_id": "unit-packet",
        "drift_id": drift_id,
        "post_id": post_id,
        "source": source,
        "source_sha256": canonical_digest(source),
        "golden_audit_constraint_sha256": GOLDEN_AUDIT_CONSTRAINT_SHA256,
        "candidate_options": [
            {"option_id": "A", "identity": {"official_title": "작품 A", "official_url": None}},
            {"option_id": "B", "identity": {"official_title": "작품 B", "official_url": None}},
        ],
        "judge_contract": {
            "choose": ["A", "B", "EQUIVALENT", "NEITHER", "INSUFFICIENT"],
            "do_not_infer_before_after_order": True,
            "evaluate_work_identity_from_source_only": True,
        },
    }
    row["packet_row_sha256"] = packet_row_digest(row)
    return row


def model_verdict(packet: dict, *, preferred: str = "A") -> dict:
    insufficient = preferred == "INSUFFICIENT"
    return {
        "drift_id": packet["drift_id"],
        "packet_row_sha256": packet["packet_row_sha256"],
        "preferred_option": preferred,
        "same_work": preferred == "EQUIVALENT",
        "relation_to_post": "insufficient" if insufficient else "direct",
        "review_label": "INFO_MISSING" if insufficient else "ACCEPT",
        "evidence_grade": "Missing" if insufficient else "Strong",
        "row_rationale": "원문의 직접 작품 언급과 익명 후보를 대조했다.",
        "evidence_refs": [
            "source.content[0]",
            "candidate_options[0].identity.official_title",
        ],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fake_signature(_: Path) -> dict:
    return {
        "status": "Valid",
        "status_message": "Signature verified.",
        "signature_type": "Authenticode",
        "signer_subject": EXPECTED_SIGNER_SUBJECT,
        "signer_thumbprint": EXPECTED_SIGNER_THUMBPRINT,
        "signer_issuer": "CN=Microsoft Identity Verification Root",
        "signer_serial_number": "01",
        "signer_not_before": "2026-01-01T00:00:00.0000000Z",
        "signer_not_after": "2027-01-01T00:00:00.0000000Z",
    }


class FakeTrustProbe:
    def __call__(self, command, **kwargs):
        if command[1:] == ["--version"]:
            stdout = (EXPECTED_CLI_VERSION + "\n").encode()
        elif command[1:] == ["debug", "models", "--bundled"]:
            model = {
                "slug": EXPECTED_MODEL_PROJECTION["slug"],
                "display_name": EXPECTED_MODEL_PROJECTION["display_name"],
                "default_reasoning_level": EXPECTED_MODEL_PROJECTION[
                    "default_reasoning_level"
                ],
                "supported_reasoning_levels": [
                    {"effort": effort, "description": effort}
                    for effort in EXPECTED_MODEL_PROJECTION["supported_reasoning_efforts"]
                ],
                "visibility": EXPECTED_MODEL_PROJECTION["visibility"],
                "supported_in_api": EXPECTED_MODEL_PROJECTION["supported_in_api"],
                "context_window": EXPECTED_MODEL_PROJECTION["context_window"],
                "effective_context_window_percent": EXPECTED_MODEL_PROJECTION[
                    "effective_context_window_percent"
                ],
            }
            stdout = json.dumps({"models": [model]}, sort_keys=True).encode()
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=b"")


def make_untrusted_anchor(root: Path) -> tuple[Path, Path, str, FakeTrustProbe]:
    executable = (
        root
        / "node_modules"
        / "@openai"
        / "codex-win32-x64"
        / "vendor"
        / "x86_64-pc-windows-msvc"
        / "bin"
        / "codex.exe"
    )
    executable.parent.mkdir(parents=True)
    payload = b"unit-test-native-codex-placeholder"
    executable.write_bytes(payload)
    executable_sha = hashlib.sha256(payload).hexdigest()
    probe = FakeTrustProbe()
    anchor = build_trust_anchor(
        codex_exe=executable.resolve(),
        process_runner=probe,
        signature_reader=fake_signature,
        expected_exe_sha256=executable_sha,
        generated_at="2026-01-01T00:00:00+00:00",
    )
    anchor_path = root / "codex-cli-anchor.json"
    write_json_exclusive(anchor_path, anchor, read_only=False)
    return anchor_path, executable.resolve(), executable_sha, probe


class FakeCodex:
    def __init__(
        self,
        response: dict,
        *,
        exit_code: int = 0,
        extra_events: list[dict] | None = None,
        timeout: bool = False,
        stderr: bytes | None = None,
    ) -> None:
        self.response = response
        self.exit_code = exit_code
        self.extra_events = extra_events or []
        self.timeout = timeout
        self.stderr = stderr or (
            b"Authorization: Bearer secret-token\n"
            b"refresh_token=refresh-secret\n"
            b"Cookie: session=private-cookie\n"
            b"github_pat_ABCDEF0123456789\n"
        )
        self.exec_command: list[str] | None = None
        self.prompt: bytes | None = None
        self.env: dict[str, str] | None = None

    def __call__(self, command, **kwargs):
        self.exec_command = list(command)
        self.prompt = kwargs["input"]
        self.env = kwargs["env"]
        stdout = kwargs["stdout"]
        stderr = kwargs["stderr"]
        final_path = Path(command[command.index("-o") + 1])
        response_text = json.dumps(self.response, ensure_ascii=False, sort_keys=True)
        events = [
            {"type": "thread.started", "thread_id": CODEX_THREAD_ID},
            {"type": "turn.started"},
            *self.extra_events,
            {
                "type": "item.completed",
                "item": {"id": "answer-1", "type": "agent_message", "text": response_text},
            },
            {"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50}},
        ]
        for event in events:
            stdout.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
        stderr.write(self.stderr)
        stdout.flush()
        stderr.flush()
        if self.timeout:
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        final_path.write_text(response_text + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, self.exit_code)


class RunCodexBlindAdjudicationTests(unittest.TestCase):
    def test_prompt_allowed_refs_are_deterministic_bound_and_packet_immutable(self) -> None:
        packet = make_packet(1)
        before = deepcopy(packet)
        allowed = enumerate_allowed_evidence_refs(packet)
        self.assertEqual(allowed, enumerate_allowed_evidence_refs(deepcopy(packet)))
        self.assertIn("source.content[0]", allowed)
        self.assertIn("candidate_options[0].identity.official_title", allowed)
        self.assertNotIn("candidate_options[0].identity.official_url", allowed)
        self.assertNotIn("candidate_options[0].identity", allowed)
        contract = build_allowed_evidence_contract([packet])
        self.assertEqual(contract[0]["drift_id"], packet["drift_id"])
        self.assertEqual(contract[0]["packet_row_sha256"], packet["packet_row_sha256"])
        self.assertEqual(contract[0]["allowed_evidence_refs"], allowed)
        self.assertEqual(
            contract[0]["allowed_evidence_refs_sha256"],
            canonical_digest(allowed),
        )
        prompt = build_prompt([packet])
        self.assertIn(b"BEGIN_ALLOWED_EVIDENCE_REFS_JSONL", prompt)
        self.assertIn(contract[0]["allowed_evidence_refs_sha256"].encode("ascii"), prompt)
        self.assertEqual(packet, before)
        self.assertEqual(packet["packet_row_sha256"], before["packet_row_sha256"])

        reordered = deepcopy(packet)
        reordered["source"] = dict(reversed(list(reordered["source"].items())))
        self.assertEqual(
            enumerate_allowed_evidence_refs(reordered),
            allowed,
        )

    def test_postparse_rejects_oob_null_container_and_missing_root_coverage(self) -> None:
        packet = make_packet(1)
        cases: list[tuple[str, dict]] = []

        oob = model_verdict(packet)
        oob["evidence_refs"] = [
            "source.content[99]",
            "candidate_options[0].identity.official_title",
        ]
        cases.append(("oob", oob))

        null_leaf = model_verdict(packet)
        null_leaf["evidence_refs"] = [
            "source.content[0]",
            "candidate_options[0].identity.official_url",
        ]
        cases.append(("null", null_leaf))

        container = model_verdict(packet)
        container["evidence_refs"] = [
            "source.content",
            "candidate_options[0].identity",
        ]
        cases.append(("container", container))

        source_only_accept = model_verdict(packet)
        source_only_accept["evidence_refs"] = ["source.content[0]"]
        cases.append(("accept-source-only", source_only_accept))

        candidate_only_accept = model_verdict(packet)
        candidate_only_accept["evidence_refs"] = [
            "candidate_options[0].identity.official_title"
        ]
        cases.append(("accept-candidate-only", candidate_only_accept))

        candidate_only_insufficient = model_verdict(packet, preferred="INSUFFICIENT")
        candidate_only_insufficient["evidence_refs"] = [
            "candidate_options[0].identity.official_title"
        ]
        cases.append(("insufficient-candidate-only", candidate_only_insufficient))

        for label, verdict in cases:
            with self.subTest(label=label):
                _, issues = _validate_model_response({"verdicts": [verdict]}, [packet])
                self.assertIn(
                    f"model_verdict_evidence_refs_invalid:{packet['drift_id']}",
                    issues,
                )

        valid_insufficient = model_verdict(packet, preferred="INSUFFICIENT")
        valid_insufficient["evidence_refs"] = ["source.content[0]"]
        _, valid_issues = _validate_model_response(
            {"verdicts": [valid_insufficient]},
            [packet],
        )
        self.assertNotIn(
            f"model_verdict_evidence_refs_invalid:{packet['drift_id']}",
            valid_issues,
        )

    def test_schema_omits_unique_items_but_postparse_rejects_duplicate_refs(self) -> None:
        packet = make_packet(1)
        schema = build_output_schema(1)
        evidence_schema = schema["properties"]["verdicts"]["items"]["properties"][
            "evidence_refs"
        ]
        self.assertNotIn("uniqueItems", evidence_schema)
        duplicate = model_verdict(packet)
        duplicate["evidence_refs"] = ["source.content[0]", "source.content[0]"]
        rows, issues = _validate_model_response({"verdicts": [duplicate]}, [packet])
        self.assertEqual(rows, [duplicate])
        self.assertTrue(
            any(issue.startswith("model_verdict_evidence_refs_invalid:") for issue in issues)
        )

    def test_golden_audit_constraint_is_required_valid_and_uniform(self) -> None:
        valid_rows = [make_packet(1), make_packet(2)]
        _validate_packet_rows(valid_rows)
        prompt = build_prompt(valid_rows)
        self.assertEqual(
            prompt.count(GOLDEN_AUDIT_CONSTRAINT_SHA256.encode("ascii")),
            len(valid_rows),
        )

        missing = make_packet(3)
        missing.pop("golden_audit_constraint_sha256")
        with self.assertRaisesRegex(ValueError, "root fields invalid"):
            _validate_packet_rows([missing])

        tampered = make_packet(4)
        tampered["golden_audit_constraint_sha256"] = "not-a-sha256"
        tampered["packet_row_sha256"] = packet_row_digest(tampered)
        with self.assertRaisesRegex(ValueError, "constraint sha256 invalid"):
            _validate_packet_rows([tampered])

        mixed = [make_packet(5), make_packet(6)]
        mixed[1]["golden_audit_constraint_sha256"] = "f" * 64
        mixed[1]["packet_row_sha256"] = packet_row_digest(mixed[1])
        with self.assertRaisesRegex(ValueError, "must share one golden audit constraint"):
            _validate_packet_rows(mixed)

    def _run(
        self,
        root: Path,
        packets: list[dict],
        fake: FakeCodex,
        *,
        mark_read_only: bool = False,
    ):
        packet_path = root / "packet.jsonl"
        write_jsonl(packet_path, packets)
        anchor_path, executable, executable_sha, trust_probe = make_untrusted_anchor(root)
        prefix = root / "judge" / "run001"
        mocked = Mock(side_effect=fake)
        receipt = run_blind_adjudication(
            blind_packet_jsonl=packet_path,
            output_prefix=prefix,
            codex_cli_trust_anchor=anchor_path,
            goal_id=ACTIVE_GOAL_ID,
            continuation_source_session=CONTINUATION_SOURCE_SESSION,
            timeout_seconds=30,
            process_runner=mocked,
            trust_process_runner=trust_probe,
            trust_signature_reader=fake_signature,
            trust_expected_exe_sha256=executable_sha,
            mark_artifacts_read_only=mark_read_only,
            allow_unconfined_test_output=True,
        )
        return receipt, prefix, mocked, executable

    def test_mock_success_is_unit_test_untrusted_and_never_production_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            packets = [make_packet(1), make_packet(2)]
            fake = FakeCodex({"verdicts": [model_verdict(row) for row in reversed(packets)]})
            receipt, prefix, mocked, executable = self._run(root, packets, fake)
            paths = _artifact_paths(prefix)
            verdicts = load_jsonl(paths["verdicts"])

            self.assertEqual(receipt["gate"], UNTRUSTED_EXECUTION_MODE)
            self.assertEqual(receipt["status"], "SUCCEEDED_UNTRUSTED")
            self.assertEqual(receipt["execution_mode"], UNTRUSTED_EXECUTION_MODE)
            self.assertEqual(receipt["receipt_version"], RECEIPT_VERSION)
            self.assertEqual(receipt["runner_version"], RUNNER_VERSION)
            self.assertEqual(receipt["receipt_digest_contract"], RECEIPT_DIGEST_CONTRACT)
            self.assertEqual(receipt["receipt_payload_sha256"], receipt_payload_digest(receipt))
            dependency_manifest = receipt["security_dependency_manifest"]
            self.assertTrue(dependency_manifest["stable_during_execution"])
            self.assertEqual(
                {row["relative_path"] for row in dependency_manifest["dependencies"]},
                set(RUNNER_SECURITY_DEPENDENCY_PATHS),
            )
            self.assertTrue(
                all(row["stable_during_execution"] for row in dependency_manifest["dependencies"])
            )
            persisted_receipt = json.loads(paths["receipt"].read_text(encoding="utf-8-sig"))
            self.assertEqual(persisted_receipt, receipt)
            self.assertEqual(
                persisted_receipt["receipt_payload_sha256"],
                receipt_payload_digest(persisted_receipt),
            )
            self.assertNotEqual(receipt["gate"], "GO")
            self.assertEqual(receipt["codex_cli_trust"]["gate"], UNTRUSTED_EXECUTION_MODE)
            self.assertEqual(receipt["command"][0], str(executable))
            self.assertNotIn("--ephemeral", receipt["command"])
            self.assertEqual(receipt["runner_artifact"]["sha256_before"], receipt["runner_artifact"]["sha256_after"])
            self.assertEqual(receipt["delivered_verdict_rows_sha256"], canonical_digest(verdicts))
            self.assertTrue(paths["verdicts"].is_file())
            self.assertIsNone(verdicts[0]["classification"])
            blind = verdicts[0]["blind_verdict"]
            self.assertEqual(blind["receipt_sha256"], blind_receipt_digest(blind))
            self.assertNotIn("PATH", fake.env or {})
            for key in (
                "OPENAI_BASE_URL",
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "SSL_CERT_FILE",
                "SSL_CERT_DIR",
                "PYTHONHOME",
                "PYTHONPATH",
            ):
                self.assertNotIn(key, fake.env or {})
            self.assertFalse(receipt["environment_isolation"]["global_agents_inherited"])
            self.assertFalse(receipt["environment_isolation"]["global_codex_config_inherited"])
            self.assertTrue(
                all(receipt["environment_isolation"]["relation_contract"].values())
            )
            self.assertEqual(mocked.call_count, 1)
            with self.assertRaises(ValueError):
                validate_raw_codex_judge_artifact(
                    trust_bundle={
                        "artifact_paths": {"raw_judge_receipt": str(paths["receipt"])},
                        "anchors": {},
                    },
                    blind_packet_rows=packets,
                    verdict_rows=verdicts,
                )

            stderr_text = paths["stderr"].read_text(encoding="utf-8")
            for secret in (
                "secret-token",
                "refresh-secret",
                "private-cookie",
                "github_pat_ABCDEF0123456789",
            ):
                self.assertNotIn(secret, stderr_text)

    def test_receipt_and_commit_marker_can_be_made_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            packet = make_packet(1)
            fake = FakeCodex({"verdicts": [model_verdict(packet)]})
            receipt, prefix, _, _ = self._run(root, [packet], fake, mark_read_only=True)
            paths = _artifact_paths(prefix)
            try:
                self.assertTrue(receipt["artifact_write_contract"]["read_only_after_create"])
                for path in paths.values():
                    if path.is_file():
                        self.assertFalse(
                            path.stat().st_mode
                            & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
                        )
            finally:
                for path in paths.values():
                    if path.is_file():
                        path.chmod(path.stat().st_mode | stat.S_IWUSR)

    def test_import_and_runpy_production_entrypoints_are_closed(self) -> None:
        signature = inspect.signature(run_blind_adjudication)
        self.assertNotIn("_production_main_token", signature.parameters)
        self.assertNotIn("execution_mode", signature.parameters)
        self.assertNotIn("production", inspect.signature(_run_blind_adjudication_core).parameters)
        with self.assertRaisesRegex(RuntimeError, "imported module"):
            _assert_production_child_context()
        with self.assertRaises(TypeError):
            _run_blind_adjudication_core(
                production=True,
                blind_packet_jsonl=Path("missing"),
                output_prefix=Path("missing"),
                codex_cli_trust_anchor=Path("missing"),
                goal_id=ACTIVE_GOAL_ID,
                continuation_source_session=CONTINUATION_SOURCE_SESSION,
                process_runner=None,
            )
        runner = Path(__file__).resolve().parents[1] / "tools/run_codex_blind_adjudication.py"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path(r'" + str(runner) + "', run_name='__main__')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runpy", result.stderr)
        compiled = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "import pathlib,sys; p=pathlib.Path(r'"
                    + str(runner)
                    + "'); sys.argv=[str(p),'--_production-child']; "
                    "g={'__name__':'__main__','__file__':str(p)}; "
                    "exec(compile(p.read_bytes(),str(p),'exec'),g)"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled.returncode, 0)
        self.assertIn("entrypoint", compiled.stderr)

    def test_imported_core_reseals_fully_monkeypatched_go_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            paths = _artifact_paths(root / "attack" / "run")
            forged = {
                "receipt": {
                    "gate": "GO",
                    "status": "SUCCEEDED",
                    "execution_mode": PRODUCTION_EXECUTION_MODE,
                    "launcher_process": {"forged": True},
                    "receipt_digest_contract": RECEIPT_DIGEST_CONTRACT,
                },
                "verdict_bytes": b"{}\n",
                "semantic_success": True,
                "paths": paths,
                "native_candidate": True,
                "mark_artifacts_read_only": False,
            }
            with patch(
                "tools.run_codex_blind_adjudication._run_blind_adjudication_unsealed",
                return_value=forged,
            ), patch(
                "tools.run_codex_blind_adjudication._assert_production_child_context",
                return_value={"forged": True},
            ), patch(
                "tools.run_codex_blind_adjudication.validate_trust_anchor",
                return_value={"gate": "GO"},
            ), patch(
                "tools.run_codex_blind_adjudication._execute_production_streaming",
                return_value={"exit_code": 0},
            ):
                receipt = _run_blind_adjudication_core(
                    blind_packet_jsonl=Path("unused"),
                    output_prefix=root / "unused",
                    codex_cli_trust_anchor=Path("unused"),
                    goal_id=ACTIVE_GOAL_ID,
                    continuation_source_session=CONTINUATION_SOURCE_SESSION,
                    process_runner=Mock(),
                )
            self.assertEqual(receipt["gate"], UNTRUSTED_EXECUTION_MODE)
            self.assertEqual(receipt["execution_mode"], UNTRUSTED_EXECUTION_MODE)
            self.assertIsNone(receipt["launcher_process"])
            persisted = json.loads(paths["receipt"].read_text(encoding="utf-8-sig"))
            self.assertEqual(persisted["gate"], UNTRUSTED_EXECUTION_MODE)

    def test_session_member_paths_reject_windows_aliases_and_case_duplicates(self) -> None:
        invalid = (
            "sessions/D:x",
            "sessions/file.txt:ads",
            "sessions/foo\\bar",
            "//server/share",
            "/sessions/absolute",
            "D:relative",
            "sessions/../escape",
            "sessions/CON",
            "sessions/con.txt",
            "sessions/LPT9.log",
            "sessions/trailing.",
            "sessions/trailing ",
        )
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            for name in invalid:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    validate_session_member_paths([name], root)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                validate_session_member_paths(
                    ["sessions/Run.jsonl", "sessions/run.jsonl"],
                    root,
                )

    def test_unknown_event_tool_event_and_second_turn_are_fail_closed(self) -> None:
        cases = [
            [{"type": "future.unknown", "payload": {}}],
            [{"type": "item.started", "item": {"id": "tool", "type": "web_search"}}],
            [{"type": "turn.started"}],
        ]
        for index, events in enumerate(cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp_name:
                root = Path(tmp_name)
                packet = make_packet(index + 1)
                receipt, prefix, _, _ = self._run(
                    root,
                    [packet],
                    FakeCodex({"verdicts": [model_verdict(packet)]}, extra_events=events),
                )
                self.assertEqual(receipt["gate"], "NO_GO")
                self.assertFalse(_artifact_paths(prefix)["verdicts"].exists())

    def test_strict_types_and_real_evidence_paths_are_required(self) -> None:
        mutations = (
            ("non_string_rationale", lambda row: row.update(row_rationale=7)),
            ("missing_source_path", lambda row: row.update(evidence_refs=["source.missing"])),
            ("fake_candidate_index", lambda row: row.update(evidence_refs=["source.content[0]", "candidate_options[7].identity"])),
            ("non_string_ref", lambda row: row.update(evidence_refs=["source.content[0]", 7])),
        )
        for index, (label, mutate) in enumerate(mutations):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp_name:
                root = Path(tmp_name)
                packet = make_packet(index + 1)
                verdict = model_verdict(packet)
                mutate(verdict)
                receipt, prefix, _, _ = self._run(
                    root,
                    [packet],
                    FakeCodex({"verdicts": [verdict]}),
                )
                self.assertEqual(receipt["gate"], "NO_GO")
                self.assertFalse(_artifact_paths(prefix)["verdicts"].exists())

    def test_nonzero_timeout_and_partial_response_never_publish_verdict(self) -> None:
        for label in ("nonzero", "timeout", "partial"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp_name:
                root = Path(tmp_name)
                packets = [make_packet(1), make_packet(2)]
                rows = [model_verdict(row) for row in packets]
                fake = FakeCodex(
                    {"verdicts": rows[:1] if label == "partial" else rows},
                    exit_code=17 if label == "nonzero" else 0,
                    timeout=label == "timeout",
                )
                receipt, prefix, _, _ = self._run(root, packets, fake)
                self.assertEqual(receipt["gate"], "NO_GO")
                self.assertFalse(_artifact_paths(prefix)["verdicts"].exists())

    def test_output_confinement_and_packet_row_cap_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            packet_path = root / "packet.jsonl"
            packet = make_packet(1)
            write_jsonl(packet_path, [packet])
            anchor_path, _, executable_sha, trust_probe = make_untrusted_anchor(root)
            with self.assertRaisesRegex(ValueError, "confined"):
                run_blind_adjudication(
                    blind_packet_jsonl=packet_path,
                    output_prefix=root / "outside" / "run",
                    codex_cli_trust_anchor=anchor_path,
                    goal_id=ACTIVE_GOAL_ID,
                    continuation_source_session=CONTINUATION_SOURCE_SESSION,
                    process_runner=Mock(),
                    trust_process_runner=trust_probe,
                    trust_signature_reader=fake_signature,
                    trust_expected_exe_sha256=executable_sha,
                )

            write_jsonl(packet_path, [make_packet(index + 1) for index in range(MAX_PACKET_ROWS + 1)])
            with self.assertRaisesRegex(ValueError, "row count exceeds"):
                run_blind_adjudication(
                    blind_packet_jsonl=packet_path,
                    output_prefix=root / "outside" / "run2",
                    codex_cli_trust_anchor=anchor_path,
                    goal_id=ACTIVE_GOAL_ID,
                    continuation_source_session=CONTINUATION_SOURCE_SESSION,
                    process_runner=Mock(),
                    trust_process_runner=trust_probe,
                    trust_signature_reader=fake_signature,
                    trust_expected_exe_sha256=executable_sha,
                    allow_unconfined_test_output=True,
                )

    def test_private_packet_field_and_model_downgrade_are_rejected_prejudge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            packet = make_packet(1)
            packet["source"]["reason_lines"] = ["private baseline hint"]
            packet["source_sha256"] = canonical_digest(packet["source"])
            packet["packet_row_sha256"] = packet_row_digest(packet)
            packet_path = root / "packet.jsonl"
            write_jsonl(packet_path, [packet])
            anchor_path, _, executable_sha, trust_probe = make_untrusted_anchor(root)
            common = {
                "blind_packet_jsonl": packet_path,
                "output_prefix": root / "judge" / "private",
                "codex_cli_trust_anchor": anchor_path,
                "goal_id": ACTIVE_GOAL_ID,
                "continuation_source_session": CONTINUATION_SOURCE_SESSION,
                "process_runner": Mock(),
                "trust_process_runner": trust_probe,
                "trust_signature_reader": fake_signature,
                "trust_expected_exe_sha256": executable_sha,
                "allow_unconfined_test_output": True,
            }
            with self.assertRaisesRegex(ValueError, "non-allowlisted"):
                run_blind_adjudication(**common)
            clean_path = root / "clean.jsonl"
            write_jsonl(clean_path, [make_packet(1)])
            with self.assertRaisesRegex(ValueError, "fixed"):
                run_blind_adjudication(**{**common, "blind_packet_jsonl": clean_path, "model": "test-model"})
            with self.assertRaisesRegex(ValueError, "reasoning effort is fixed"):
                run_blind_adjudication(
                    **{**common, "blind_packet_jsonl": clean_path, "reasoning_effort": "low"}
                )

    def test_production_streaming_executor_enforces_stdout_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            raw = root / "raw.jsonl"
            stderr = root / "stderr.bin"
            final = root / "final.json"
            command = [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'x' * 4096); sys.stdout.flush()",
            ]
            with patch(
                "tools.run_codex_blind_adjudication.MAX_RAW_EVENTS_BYTES",
                128,
            ):
                result = _execute_production_streaming(
                    command=command,
                    prompt_bytes=b"",
                    raw_stage=raw,
                    stderr_stage=stderr,
                    final_stage=final,
                    timeout_seconds=10,
                    env=dict(os.environ),
                    cwd=root,
                )
            self.assertTrue(result["stdout_limit_exceeded"])
            self.assertEqual(raw.stat().st_size, 128)

    def test_session_bundle_is_thread_bound_and_excludes_auth_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            codex_home = root / ".codex"
            sessions = codex_home / "sessions" / "2026" / "07" / "10"
            sessions.mkdir(parents=True)
            session = sessions / "rollout.jsonl"
            session.write_text(
                json.dumps({"thread_id": CODEX_THREAD_ID, "event": "session_meta"}) + "\n",
                encoding="utf-8",
            )
            (codex_home / "auth.json").write_text('{"access_token":"secret"}', encoding="utf-8")
            destination = root / "session.zip"
            metadata = _build_session_bundle_stage(codex_home, CODEX_THREAD_ID, destination)
            self.assertTrue(metadata["secrets_excluded"])
            self.assertEqual(metadata["thread_id"], CODEX_THREAD_ID)
            with zipfile.ZipFile(destination) as archive:
                names = archive.namelist()
            self.assertTrue(any(name.startswith("sessions/") for name in names))
            self.assertFalse(any("auth" in name.casefold() for name in names))

            session.write_text(
                json.dumps(
                    {
                        "thread_id": CODEX_THREAD_ID,
                        "event": "session_meta",
                        "OPENAI_API_KEY": "sk-unit-secret-ABCDEFGHIJKLMNOP",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "secret-like material"):
                _build_session_bundle_stage(
                    codex_home,
                    CODEX_THREAD_ID,
                    root / "secret-session.zip",
                )

    def test_isolated_auth_copy_does_not_also_inherit_auth_or_network_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            source = root / "source-codex-home"
            source.mkdir()
            (source / "auth.json").write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "last_refresh": "2026-07-10T00:00:00Z",
                        "OPENAI_API_KEY": None,
                        "tokens": {
                            "access_token": "unit-access-secret",
                            "account_id": "unit-account",
                            "id_token": "unit-id-secret",
                            "refresh_token": "unit-refresh-secret",
                        },
                    }
                ),
                encoding="utf-8",
            )
            overrides = {
                "CODEX_BLIND_AUTH_SOURCE": str(source),
                "OPENAI_API_KEY": "must-not-be-inherited-when-auth-json-exists",
                "OPENAI_BASE_URL": "https://attacker.invalid",
                "HTTPS_PROXY": "http://attacker.invalid:8080",
                "SSL_CERT_FILE": str(root / "attacker-ca.pem"),
                "PYTHONPATH": str(root / "attacker-python"),
            }
            with patch.dict(os.environ, overrides, clear=False):
                env, receipt = _prepare_isolated_environment(
                    root / "isolated",
                    require_auth=True,
                )
            for key in (
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "HTTPS_PROXY",
                "SSL_CERT_FILE",
                "PYTHONPATH",
            ):
                self.assertNotIn(key, env)
            self.assertEqual(receipt["authentication_source"], "isolated_auth_json_copy")
            self.assertTrue(
                receipt["direct_service_policy"]["auth_json_schema_allowlist_valid"]
            )
            self.assertFalse(
                receipt["direct_service_policy"]["auth_json_network_override_inherited"]
            )
            self.assertFalse(any(receipt["direct_service_policy"][key] for key in (
                "custom_endpoint_inherited",
                "proxy_inherited",
                "custom_ca_inherited",
                "python_environment_inherited",
            )))


if __name__ == "__main__":
    unittest.main()
