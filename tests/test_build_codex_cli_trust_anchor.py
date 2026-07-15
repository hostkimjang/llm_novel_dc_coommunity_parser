from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.build_codex_cli_trust_anchor import (
    EXPECTED_CLI_VERSION,
    EXPECTED_MODEL_PROJECTION,
    EXPECTED_SIGNER_SUBJECT,
    EXPECTED_SIGNER_THUMBPRINT,
    PRODUCTION_EXECUTION_MODE,
    UNTRUSTED_EXECUTION_MODE,
    build_trust_anchor,
    canonical_digest,
    validate_trust_anchor,
    validate_direct_python_entrypoint,
    write_json_exclusive,
)


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


def fake_model_catalog() -> dict:
    return {
        "models": [
            {
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
        ]
    }


class FakeProbeRunner:
    def __call__(self, command, **kwargs):
        if command[1:] == ["--version"]:
            stdout = (EXPECTED_CLI_VERSION + "\n").encode()
        elif command[1:] == ["debug", "models", "--bundled"]:
            stdout = json.dumps(fake_model_catalog(), sort_keys=True).encode()
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=b"")


def make_fake_exe(root: Path) -> tuple[Path, str]:
    path = (
        root
        / "node_modules"
        / "@openai"
        / "codex-win32-x64"
        / "vendor"
        / "x86_64-pc-windows-msvc"
        / "bin"
        / "codex.exe"
    )
    path.parent.mkdir(parents=True)
    payload = b"unit-test-native-codex-placeholder"
    path.write_bytes(payload)
    return path.resolve(), hashlib.sha256(payload).hexdigest()


class CodexCliTrustAnchorTests(unittest.TestCase):
    def test_direct_entrypoint_parser_accepts_only_outer_or_single_isolated_child(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "tools/build_codex_cli_trust_anchor.py").resolve()
        outer = validate_direct_python_entrypoint(
            [sys.executable, str(script), "--help"],
            script,
        )
        child = validate_direct_python_entrypoint(
            [sys.executable, "-I", str(script), "--_production-child"],
            script,
        )
        self.assertFalse(outer["isolated_flag"])
        self.assertTrue(child["isolated_flag"])
        invalid = (
            [sys.executable, "-I", "-I", str(script)],
            [sys.executable, "-B", str(script)],
            [sys.executable, "-c", str(script)],
            [sys.executable, "-m", str(script)],
            [sys.executable, "-", str(script)],
            [sys.executable, "-I", "-B", str(script)],
            [sys.executable, str(script), "-I"],
            [sys.executable, str(script.with_name("other.py"))],
        )
        for argv in invalid:
            with self.subTest(argv=argv), self.assertRaises(RuntimeError):
                validate_direct_python_entrypoint(argv, script)

    def test_all_three_entrypoints_accept_real_outer_and_isolated_child_help(self) -> None:
        root = Path(__file__).resolve().parents[1]
        scripts = (
            root / "tools/build_codex_cli_trust_anchor.py",
            root / "tools/run_codex_blind_adjudication.py",
            root / "tools/verify_codex_blind_judge_thread.py",
        )
        for script in scripts:
            for prefix in ([sys.executable], [sys.executable, "-I"]):
                with self.subTest(script=script.name, prefix=prefix):
                    result = subprocess.run(
                        [*prefix, str(script), "--_production-child", "--help"]
                        if "-I" in prefix
                        else [*prefix, str(script), "--help"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
            for bad_prefix in (
                [sys.executable, "-B"],
                [sys.executable, "-I", "-I"],
            ):
                with self.subTest(script=script.name, bad_prefix=bad_prefix):
                    result = subprocess.run(
                        [*bad_prefix, str(script), "--help"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)

    def test_runpy_and_exec_compile_cannot_reach_production_seal(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "tools/build_codex_cli_trust_anchor.py"
        )
        runpy_result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy; runpy.run_path(r'" + str(script) + "', run_name='__main__')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(runpy_result.returncode, 0)
        self.assertIn("runpy", runpy_result.stderr)
        compiled_result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "import pathlib,sys; p=pathlib.Path(r'"
                    + str(script)
                    + "'); sys.argv=[str(p),'--_production-child']; "
                    "g={'__name__':'__main__','__file__':str(p)}; "
                    "exec(compile(p.read_bytes(),str(p),'exec'),g)"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(compiled_result.returncode, 0)
        self.assertIn("entrypoint", compiled_result.stderr)

    def test_imported_builder_cannot_be_monkeypatched_into_production_go(self) -> None:
        fake_evidence = {
            "executable_path": r"C:\\fake\\codex.exe",
            "executable_sha256": "0" * 64,
        }
        with patch(
            "tools.build_codex_cli_trust_anchor.probe_native_codex",
            return_value=fake_evidence,
        ):
            anchor = build_trust_anchor(codex_exe=Path(r"C:\\fake\\codex.exe"))
        self.assertEqual(anchor["gate"], UNTRUSTED_EXECUTION_MODE)
        self.assertEqual(anchor["execution_mode"], UNTRUSTED_EXECUTION_MODE)
        with self.assertRaises(TypeError):
            build_trust_anchor(
                codex_exe=Path(r"C:\\fake\\codex.exe"),
                execution_mode=PRODUCTION_EXECUTION_MODE,
            )

    def test_injected_probe_can_only_build_and_validate_untrusted_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            executable, executable_sha = make_fake_exe(root)
            runner = FakeProbeRunner()
            anchor = build_trust_anchor(
                codex_exe=executable,
                process_runner=runner,
                signature_reader=fake_signature,
                expected_exe_sha256=executable_sha,
                generated_at="2026-01-01T00:00:00+00:00",
            )
            self.assertEqual(anchor["gate"], UNTRUSTED_EXECUTION_MODE)
            self.assertEqual(anchor["execution_mode"], UNTRUSTED_EXECUTION_MODE)
            self.assertFalse(anchor["artifact_write_contract"]["read_only_after_create"])
            anchor_path = root / "anchor.json"
            write_json_exclusive(anchor_path, anchor, read_only=False)
            validation = validate_trust_anchor(
                anchor_path,
                production=False,
                process_runner=runner,
                signature_reader=fake_signature,
                expected_exe_sha256=executable_sha,
            )
            self.assertEqual(validation["gate"], UNTRUSTED_EXECUTION_MODE)
            with self.assertRaisesRegex(ValueError, "immutable GO"):
                validate_trust_anchor(
                    anchor_path,
                    production=True,
                    process_runner=runner,
                    signature_reader=fake_signature,
                    expected_exe_sha256=executable_sha,
                )

    def test_wrong_signer_is_rejected_before_anchor_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            executable, executable_sha = make_fake_exe(Path(tmp_name))

            def wrong_signer(path: Path) -> dict:
                payload = fake_signature(path)
                payload["signer_subject"] = "CN=Attacker"
                return payload

            with self.assertRaisesRegex(ValueError, "signer/status mismatch"):
                build_trust_anchor(
                    codex_exe=executable,
                    process_runner=FakeProbeRunner(),
                    signature_reader=wrong_signer,
                    expected_exe_sha256=executable_sha,
                )

    def test_path_shim_and_relative_path_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            shim = root / "codex.cmd"
            shim.write_text("@echo off", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absolute"):
                build_trust_anchor(codex_exe=Path("codex"))
            with self.assertRaisesRegex(ValueError, "native codex.exe"):
                build_trust_anchor(codex_exe=shim.resolve())

    def test_anchor_payload_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            executable, executable_sha = make_fake_exe(root)
            runner = FakeProbeRunner()
            anchor = build_trust_anchor(
                codex_exe=executable,
                process_runner=runner,
                signature_reader=fake_signature,
                expected_exe_sha256=executable_sha,
            )
            tampered = copy.deepcopy(anchor)
            tampered["judge_contract"]["reasoning_effort"] = "low"
            self.assertNotEqual(
                tampered["anchor_payload_sha256"],
                canonical_digest(
                    {key: value for key, value in tampered.items() if key != "anchor_payload_sha256"}
                ),
            )
            path = root / "tampered.json"
            write_json_exclusive(path, tampered, read_only=False)
            with self.assertRaisesRegex(ValueError, "payload hash mismatch"):
                validate_trust_anchor(
                    path,
                    production=False,
                    process_runner=runner,
                    signature_reader=fake_signature,
                    expected_exe_sha256=executable_sha,
                )


if __name__ == "__main__":
    unittest.main()
