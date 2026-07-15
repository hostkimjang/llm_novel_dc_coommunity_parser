from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from tests.test_run_codex_blind_adjudication import (
    CODEX_THREAD_ID,
    FakeTrustProbe,
    fake_signature,
    make_untrusted_anchor,
)
from tools.build_codex_cli_trust_anchor import (
    EXPECTED_CODEX_EXE_SHA256,
    UNTRUSTED_EXECUTION_MODE,
)
from tools.build_adjusted_collateral_blind_packet import canonical_digest
from tools.run_codex_blind_adjudication import (
    ACTIVE_GOAL_ID,
    CONTINUATION_SOURCE_SESSION,
    RECEIPT_DIGEST_CONTRACT,
    _build_session_bundle_stage,
    receipt_payload_digest,
)
from tools.verify_codex_blind_judge_thread import (
    RECEIPT_VERSION,
    TRUST_BOUNDARY,
    VERIFIER_SECURITY_DEPENDENCY_PATHS,
    VERIFIER_VERSION,
    _assert_child_context,
    _paths,
    _restore_session_bundle,
    _verify_core,
    _verify_unsealed,
    verify_thread_readback,
)


PRIMARY_RAW_SHA = "a" * 64
PRIMARY_FINAL_SHA = "b" * 64
PRIMARY_VERDICTS_SHA = "c" * 64
CHALLENGE = "readback-challenge-" + "d" * 48


def make_primary(root: Path) -> tuple[Path, dict]:
    codex_home = root / "primary-codex-home"
    sessions = codex_home / "sessions" / "2026" / "07" / "10"
    sessions.mkdir(parents=True)
    (sessions / "rollout.jsonl").write_text(
        json.dumps({"thread_id": CODEX_THREAD_ID, "event": "session_meta"}) + "\n",
        encoding="utf-8",
    )
    bundle = root / "primary-session.zip"
    metadata = _build_session_bundle_stage(codex_home, CODEX_THREAD_ID, bundle)
    metadata["path"] = str(bundle.resolve())
    primary = {
        "report_type": "codex_blind_judge_raw_receipt",
        "gate": UNTRUSTED_EXECUTION_MODE,
        "status": "SUCCEEDED_UNTRUSTED",
        "execution_mode": UNTRUSTED_EXECUTION_MODE,
        "goal_id": ACTIVE_GOAL_ID,
        "continuation_source_session": CONTINUATION_SOURCE_SESSION,
        "codex_thread_id": CODEX_THREAD_ID,
        "judge_run_id": "primary-judge-run",
        "runner_run_id": "primary-runner-run",
        "execution_process": {"process_id": 101},
        "raw_events_jsonl_sha256": PRIMARY_RAW_SHA,
        "final_response_sha256": PRIMARY_FINAL_SHA,
        "delivered_verdicts_jsonl_sha256": PRIMARY_VERDICTS_SHA,
        "session_bundle": metadata,
    }
    path = root / "primary-receipt.json"
    path.write_text(json.dumps(primary, sort_keys=True), encoding="utf-8")
    return path, primary


class FakeResume:
    def __init__(self, expected: dict, *, mutate: str | None = None, tool: bool = False) -> None:
        self.expected = dict(expected)
        if mutate:
            self.expected[mutate] = "wrong"
        self.tool = tool
        self.command: list[str] | None = None
        self.env: dict[str, str] | None = None

    def __call__(self, command, **kwargs):
        self.command = list(command)
        self.env = kwargs["env"]
        stdout = kwargs["stdout"]
        stderr = kwargs["stderr"]
        response = json.dumps(self.expected, sort_keys=True)
        events = [
            {"type": "thread.started", "thread_id": CODEX_THREAD_ID},
            {"type": "turn.started"},
        ]
        if self.tool:
            events.append(
                {"type": "item.started", "item": {"id": "tool", "type": "web_search"}}
            )
        events.extend(
            [
                {
                    "type": "item.completed",
                    "item": {"id": "answer", "type": "agent_message", "text": response},
                },
                {"type": "turn.completed"},
            ]
        )
        for event in events:
            stdout.write((json.dumps(event) + "\n").encode())
        stderr.write(b"OPENAI_API_KEY=should-redact\n")
        stdout.flush()
        stderr.flush()
        final = Path(command[command.index("-o") + 1])
        final.write_text(response + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)


class ThreadReadbackTests(unittest.TestCase):
    def _run(self, root: Path, *, mutate: str | None = None, tool: bool = False):
        primary_path, _ = make_primary(root)
        primary_sha = __import__("hashlib").sha256(primary_path.read_bytes()).hexdigest()
        expected = {
            "thread_id": CODEX_THREAD_ID,
            "challenge": CHALLENGE,
            "primary_receipt_sha256": primary_sha,
            "primary_raw_events_sha256": PRIMARY_RAW_SHA,
            "primary_final_response_sha256": PRIMARY_FINAL_SHA,
            "primary_verdicts_sha256": PRIMARY_VERDICTS_SHA,
        }
        anchor_path, _, executable_sha, trust_probe = make_untrusted_anchor(root)
        fake = FakeResume(expected, mutate=mutate, tool=tool)
        prefix = root / "readback" / "run001"
        receipt = verify_thread_readback(
            primary_receipt=primary_path,
            codex_cli_trust_anchor=anchor_path,
            output_prefix=prefix,
            process_runner=Mock(side_effect=fake),
            trust_process_runner=trust_probe,
            trust_signature_reader=fake_signature,
            trust_expected_exe_sha256=executable_sha,
            challenge=CHALLENGE,
            mark_artifacts_read_only=False,
            allow_unconfined_test_output=True,
        )
        return receipt, fake, prefix

    def test_mock_readback_is_bound_but_never_production_go(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            receipt, fake, prefix = self._run(Path(tmp_name))
            self.assertEqual(receipt["gate"], UNTRUSTED_EXECUTION_MODE)
            self.assertEqual(receipt["status"], "SUCCEEDED_UNTRUSTED")
            self.assertEqual(receipt["receipt_version"], RECEIPT_VERSION)
            self.assertEqual(receipt["verifier_version"], VERIFIER_VERSION)
            self.assertEqual(receipt["receipt_digest_contract"], RECEIPT_DIGEST_CONTRACT)
            self.assertEqual(receipt["receipt_payload_sha256"], receipt_payload_digest(receipt))
            dependency_manifest = receipt["security_dependency_manifest"]
            self.assertTrue(dependency_manifest["stable_during_execution"])
            self.assertEqual(
                {row["relative_path"] for row in dependency_manifest["dependencies"]},
                set(VERIFIER_SECURITY_DEPENDENCY_PATHS),
            )
            persisted_receipt = json.loads(_paths(prefix)["receipt"].read_text(encoding="utf-8-sig"))
            self.assertEqual(persisted_receipt, receipt)
            self.assertEqual(
                persisted_receipt["receipt_payload_sha256"],
                receipt_payload_digest(persisted_receipt),
            )
            self.assertFalse(receipt["cryptographic_service_attestation"])
            self.assertEqual(receipt["trust_boundary"], TRUST_BOUNDARY)
            self.assertEqual(receipt["codex_thread_id"], CODEX_THREAD_ID)
            self.assertNotEqual(receipt["readback_run_id"], receipt["primary_binding"]["primary_judge_run_id"])
            self.assertEqual(receipt["exit_code"], 0)
            self.assertFalse(receipt["timed_out"])
            self.assertIsNone(receipt["execution_error"])
            self.assertGreater(receipt["raw_events_byte_count"], 0)
            self.assertGreater(receipt["final_response_byte_count"], 0)
            runner_dependency = receipt["runner_dependency_artifact"]
            self.assertEqual(
                Path(runner_dependency["path"]).resolve(),
                Path(sys.modules["tools.run_codex_blind_adjudication"].__file__).resolve(),
            )
            self.assertTrue(runner_dependency["stable_during_execution"])
            self.assertEqual(
                runner_dependency["sha256_before"],
                runner_dependency["sha256_after"],
            )
            self.assertIn("resume", fake.command or [])
            self.assertIn(CODEX_THREAD_ID, fake.command or [])
            self.assertNotIn("--ephemeral", fake.command or [])
            for key in ("OPENAI_BASE_URL", "HTTP_PROXY", "HTTPS_PROXY", "PYTHONPATH"):
                self.assertNotIn(key, fake.env or {})
            self.assertTrue(_paths(prefix)["receipt"].is_file())

    def test_wrong_challenge_or_tool_event_is_no_go(self) -> None:
        for mutate, tool in (("challenge", False), (None, True)):
            with self.subTest(mutate=mutate, tool=tool), tempfile.TemporaryDirectory() as tmp_name:
                receipt, _, _ = self._run(Path(tmp_name), mutate=mutate, tool=tool)
                self.assertEqual(receipt["gate"], "NO_GO")

    def test_import_and_runpy_production_entrypoints_are_closed(self) -> None:
        self.assertNotIn("production", inspect.signature(verify_thread_readback).parameters)
        self.assertNotIn("production", inspect.signature(_verify_core).parameters)
        with self.assertRaisesRegex(RuntimeError, "direct isolated"):
            _assert_child_context()
        with self.assertRaises(TypeError):
            _verify_core(
                production=True,
                primary_receipt=Path("missing"),
                codex_cli_trust_anchor=Path("missing"),
                output_prefix=Path("missing"),
                timeout_seconds=60,
                process_runner=None,
                trust_process_runner=None,
                trust_signature_reader=None,
                trust_expected_exe_sha256="0" * 64,
                challenge=None,
                mark_artifacts_read_only=True,
                allow_unconfined_test_output=False,
            )
        verifier = Path(__file__).resolve().parents[1] / "tools/verify_codex_blind_judge_thread.py"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path(r'" + str(verifier) + "', run_name='__main__')",
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
                    + str(verifier)
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
            paths = _paths(root / "attack" / "run")
            forged = {
                "receipt": {
                    "gate": "GO",
                    "status": "SUCCEEDED",
                    "execution_mode": "subprocess_production",
                    "launcher_process": {"forged": True},
                    "receipt_digest_contract": RECEIPT_DIGEST_CONTRACT,
                },
                "paths": paths,
                "semantic_success": True,
                "native_candidate": True,
                "mark_artifacts_read_only": False,
            }
            with patch(
                "tools.verify_codex_blind_judge_thread._verify_unsealed",
                return_value=forged,
            ), patch(
                "tools.verify_codex_blind_judge_thread._assert_child_context",
                return_value={"forged": True},
            ), patch(
                "tools.verify_codex_blind_judge_thread.validate_trust_anchor",
                return_value={"gate": "GO"},
            ), patch(
                "tools.verify_codex_blind_judge_thread._execute_production_streaming",
                return_value={"exit_code": 0},
            ):
                receipt = _verify_core(
                    primary_receipt=Path("unused"),
                    codex_cli_trust_anchor=Path("unused"),
                    output_prefix=root / "unused",
                    timeout_seconds=60,
                    process_runner=Mock(),
                    trust_process_runner=None,
                    trust_signature_reader=None,
                    trust_expected_exe_sha256="0" * 64,
                    challenge=CHALLENGE,
                    mark_artifacts_read_only=False,
                    allow_unconfined_test_output=True,
                )
            self.assertEqual(receipt["gate"], UNTRUSTED_EXECUTION_MODE)
            self.assertEqual(receipt["execution_mode"], UNTRUSTED_EXECUTION_MODE)
            self.assertIsNone(receipt["launcher_process"])

    def test_full_primary_preflight_failure_has_zero_side_effects(self) -> None:
        for index, mutation in enumerate(("command", "launcher", "execution", "raw-event")):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp_name:
                root = Path(tmp_name)
                prefix = root / f"readback-{index}"
                writer = Mock()
                environment = Mock()
                restore = Mock()
                execute = Mock()
                with patch(
                    "tools.verify_codex_blind_judge_thread._is_confined_review_prefix",
                    return_value=True,
                ), patch(
                    "tools.build_adjusted_collateral_adjudication."
                    "preflight_raw_codex_judge_receipt_for_readback",
                    side_effect=ValueError(f"forged primary {mutation}"),
                ), patch(
                    "tools.verify_codex_blind_judge_thread._write_exclusive",
                    writer,
                ), patch(
                    "tools.verify_codex_blind_judge_thread._prepare_isolated_environment",
                    environment,
                ), patch(
                    "tools.verify_codex_blind_judge_thread._restore_session_bundle",
                    restore,
                ), patch(
                    "tools.verify_codex_blind_judge_thread._execute_production_streaming",
                    execute,
                ), self.assertRaisesRegex(ValueError, mutation):
                    _verify_unsealed(
                        primary_receipt=root / "forged-primary.json",
                        codex_cli_trust_anchor=root / "forged-anchor.json",
                        output_prefix=prefix,
                        timeout_seconds=60,
                        process_runner=None,
                        trust_process_runner=None,
                        trust_signature_reader=None,
                        trust_expected_exe_sha256=EXPECTED_CODEX_EXE_SHA256,
                        challenge=None,
                        mark_artifacts_read_only=True,
                        allow_unconfined_test_output=False,
                        launcher_evidence={"direct": True},
                    )
                writer.assert_not_called()
                environment.assert_not_called()
                restore.assert_not_called()
                execute.assert_not_called()
                self.assertFalse(any(path.exists() for path in _paths(prefix).values()))

    def test_session_bundle_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            row = {
                "path": "sessions/../escape.jsonl",
                "sha256": __import__("hashlib").sha256(b"x").hexdigest(),
                "size": 1,
            }
            metadata = {
                "report_type": "codex_blind_judge_session_bundle_manifest",
                "version": "codex-blind-session-bundle-v1",
                "thread_id": CODEX_THREAD_ID,
                "file_count": 1,
                "total_uncompressed_bytes": 1,
                "files": [row],
                "files_sha256": canonical_digest([row]),
                "secrets_excluded": True,
            }
            bundle = root / "malicious.zip"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr(row["path"], b"x")
                archive.writestr("session_manifest.json", json.dumps(metadata))
            primary = {"session_bundle": {**metadata, "path": str(bundle)}}
            writer = Mock()
            with patch(
                "tools.verify_codex_blind_judge_thread._write_exclusive",
                writer,
            ), self.assertRaisesRegex(ValueError, "traversal"):
                _restore_session_bundle(primary, root / "restore")
            writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
