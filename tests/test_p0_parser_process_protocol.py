from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from llm_batch.grounding import p0_parser_process_protocol as protocol


ROOT = Path(__file__).resolve().parents[1]
WORKER_MODULE = "llm_batch.grounding.p0_parser_process_worker"
WORKER_PATH = (
    ROOT / "src" / "llm_batch" / "grounding" / "p0_parser_process_worker.py"
)


def _capture(capture_id: str, payload: bytes) -> dict[str, object]:
    return {
        "capture_id": capture_id,
        "payload_base64": base64.b64encode(payload).decode("ascii"),
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }


def _request(*captures: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": protocol.REQUEST_SCHEMA,
        "operation": protocol.OPERATION,
        "request_id": "capture-probe-request-001",
        "parser_run_id": "capture-probe-run-001",
        "launch_sha256": "9" * 64,
        "capture_manifest_sha256": "a" * 64,
        "input_registry_sha256": "b" * 64,
        "parser_manifest_sha256": "c" * 64,
        "parser_version": "capture-hash-probe-v1",
        "captures": list(captures) or [_capture("capture-001", b"hello")],
    }


def _raw(value: object) -> bytes:
    return protocol.canonical_file_bytes(value)


def _run_direct_worker(input_raw: bytes) -> tuple[subprocess.CompletedProcess[bytes], list[str]]:
    with tempfile.TemporaryDirectory(prefix="p0-worker-pycache-") as value:
        prefix = Path(value).resolve()
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                f"pycache_prefix={prefix}",
                str(WORKER_PATH),
                f"--p0-expected-pycache-prefix={prefix}",
            ],
            cwd=ROOT,
            input=input_raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        entries = [str(item.relative_to(prefix)) for item in prefix.rglob("*")]
    return completed, entries


class P0ParserProcessProtocolTests(unittest.TestCase):
    def test_probe_binds_exact_capture_bytes_and_never_claims_authority(self) -> None:
        request = _request(
            _capture("capture-001", "아생갤".encode("utf-8")),
            _capture("capture-002", b"structured\x00payload"),
            _capture("capture-003", b""),
        )
        request_raw = _raw(request)
        response_raw = protocol.execute_request_bytes(request_raw)
        response = protocol.validate_response_bytes(response_raw)

        self.assertEqual(hashlib.sha256(request_raw).hexdigest(), response["request_sha256"])
        self.assertEqual(request["launch_sha256"], response["launch_sha256"])
        self.assertEqual(
            request["parser_manifest_sha256"], response["parser_manifest_sha256"]
        )
        self.assertEqual(request["parser_version"], response["parser_version"])
        self.assertEqual(3, response["capture_count"])
        self.assertEqual(
            sum(item["payload_bytes"] for item in request["captures"]),
            response["total_payload_bytes"],
        )
        self.assertTrue(response["child_reported_capture_hash_probe_completed"])
        self.assertTrue(
            response["child_reported_capture_payload_accounting_complete"]
        )
        self.assertEqual(protocol.GATE_STATUS, response["gate_status"])
        self.assertEqual(protocol.OPERATIONAL_EFFECT, response["operational_effect"])
        for field in protocol.FALSE_AUTHORITY_FIELDS:
            self.assertIs(response[field], False, field)
        self.assertEqual(
            {"actual_source_claim_count": 0, "actual_a_context_review_count": 0},
            response["credited_counts"],
        )
        self.assertNotIn("payload_base64", response_raw.decode("utf-8"))
        self.assertNotIn("payload_path", request_raw.decode("utf-8"))

    def test_request_rejects_bom_duplicate_nonfinite_trailing_and_noncanonical(self) -> None:
        valid = _raw(_request())
        cases = {
            "BOM": b"\xef\xbb\xbf" + valid,
            "duplicate": valid.replace(
                b"{", b'{"schema_version":"duplicate",', 1
            ),
            "non-finite": valid.replace(
                b'"payload_bytes":5', b'"payload_bytes":NaN', 1
            ),
            "trailing": valid + b"x",
            "missing final LF": valid[:-1],
            "pretty/noncanonical": json.dumps(
                _request(), ensure_ascii=False, indent=2
            ).encode("utf-8")
            + b"\n",
        }
        for label, raw in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(protocol.P0ParserProcessProtocolError):
                    protocol.parse_request_bytes(raw)

    def test_request_rejects_path_extra_invalid_base64_and_binding_mismatch(self) -> None:
        mutations: dict[str, dict[str, object]] = {}
        path = _request()
        path["captures"][0]["payload_path"] = "C:/secret/input.txt"  # type: ignore[index]
        mutations["path field"] = path
        invalid = _request()
        invalid["captures"][0]["payload_base64"] = "***"  # type: ignore[index]
        mutations["invalid base64"] = invalid
        noncanonical = _request()
        noncanonical["captures"][0]["payload_base64"] = "aGVsbG8=\n"  # type: ignore[index]
        mutations["noncanonical base64"] = noncanonical
        byte_mismatch = _request()
        byte_mismatch["captures"][0]["payload_bytes"] = 4  # type: ignore[index]
        mutations["byte mismatch"] = byte_mismatch
        sha_mismatch = _request()
        sha_mismatch["captures"][0]["payload_sha256"] = "0" * 64  # type: ignore[index]
        mutations["sha mismatch"] = sha_mismatch
        duplicate = _request(
            _capture("capture-001", b"one"), _capture("capture-001", b"two")
        )
        mutations["duplicate capture id"] = duplicate
        for label, value in mutations.items():
            with self.subTest(label=label):
                with self.assertRaises(protocol.P0ParserProcessProtocolError):
                    protocol.parse_request_bytes(_raw(value))

    def test_request_size_and_count_bounds_fail_closed(self) -> None:
        too_many = _request(
            *(
                _capture(f"capture-{index:03d}", b"x")
                for index in range(protocol.MAX_CAPTURE_COUNT + 1)
            )
        )
        with self.assertRaisesRegex(
            protocol.P0ParserProcessProtocolError, "1..40"
        ):
            protocol.parse_request_bytes(_raw(too_many))

        oversized_payload = _request(
            _capture("capture-large", b"x" * (protocol.MAX_CAPTURE_BYTES + 1))
        )
        with self.assertRaisesRegex(
            protocol.P0ParserProcessProtocolError, "per-capture"
        ):
            protocol.parse_request_bytes(_raw(oversized_payload))

        total_oversized = _request(
            *(
                _capture(
                    f"capture-{index:03d}",
                    b"x" * protocol.MAX_CAPTURE_BYTES,
                )
                for index in range(
                    protocol.MAX_TOTAL_CAPTURE_BYTES
                    // protocol.MAX_CAPTURE_BYTES
                    + 1
                )
            )
        )
        with self.assertRaisesRegex(
            protocol.P0ParserProcessProtocolError, "total decoded"
        ):
            protocol.parse_request_bytes(_raw(total_oversized))

        with self.assertRaisesRegex(
            protocol.P0ParserProcessProtocolError, "byte length"
        ):
            protocol.parse_request_bytes(b"x" * (protocol.MAX_REQUEST_BYTES + 1))

    def test_response_tamper_and_authority_upgrade_fail_closed(self) -> None:
        response = protocol.validate_response_bytes(
            protocol.execute_request_bytes(_raw(_request()))
        )
        cases: list[dict[str, object]] = []
        upgraded = deepcopy(response)
        upgraded["actual_semantic_evidence_verified"] = True
        upgraded["receipt_sha256"] = protocol.canonical_sha256(
            {key: value for key, value in upgraded.items() if key != "receipt_sha256"}
        )
        cases.append(upgraded)
        wrong_count = deepcopy(response)
        wrong_count["capture_count"] = 2
        wrong_count["receipt_sha256"] = protocol.canonical_sha256(
            {key: value for key, value in wrong_count.items() if key != "receipt_sha256"}
        )
        cases.append(wrong_count)
        wrong_hash = deepcopy(response)
        wrong_hash["receipt_sha256"] = "0" * 64
        cases.append(wrong_hash)
        for value in cases:
            with self.assertRaises(protocol.P0ParserProcessProtocolError):
                protocol.validate_response_bytes(_raw(value))

    def test_parent_cross_binding_recalculates_every_request_projection(self) -> None:
        request_raw = _raw(
            _request(
                _capture("capture-001", b"one"),
                _capture("capture-002", b"two"),
            )
        )
        response_raw = protocol.execute_request_bytes(request_raw)
        binding = protocol.validate_response_against_request(
            response_raw, request_raw
        )
        self.assertTrue(binding["child_response_exact_cross_binding_verified"])
        self.assertEqual(protocol.CROSS_BINDING_SCHEMA, binding["schema_version"])
        for field in protocol.FALSE_AUTHORITY_FIELDS:
            self.assertIs(binding[field], False, field)

        mutations = {
            "request_id": "capture-probe-request-002",
            "parser_run_id": "capture-probe-run-002",
            "launch_sha256": "1" * 64,
            "capture_manifest_sha256": "2" * 64,
            "input_registry_sha256": "3" * 64,
            "parser_manifest_sha256": "4" * 64,
            "parser_version": "capture-hash-probe-v2",
        }
        base = _request(
            _capture("capture-001", b"one"),
            _capture("capture-002", b"two"),
        )
        for field, replacement in mutations.items():
            other_request = deepcopy(base)
            other_request[field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(
                protocol.P0ParserProcessProtocolError, "cross-binding mismatch"
            ):
                protocol.validate_response_against_request(
                    response_raw, _raw(other_request)
                )
        changed_capture = deepcopy(base)
        changed_capture["captures"][1] = _capture("capture-002", b"changed")
        with self.assertRaisesRegex(
            protocol.P0ParserProcessProtocolError, "cross-binding mismatch"
        ):
            protocol.validate_response_against_request(
                response_raw, _raw(changed_capture)
            )

    def test_worker_success_has_exact_stdout_and_empty_stderr(self) -> None:
        request_raw = _raw(_request(_capture("capture-001", b"worker-input")))
        completed = subprocess.run(
            [sys.executable, "-m", WORKER_MODULE],
            cwd=ROOT,
            input=request_raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(protocol.execute_request_bytes(request_raw), completed.stdout)
        self.assertEqual(b"", completed.stderr)
        protocol.validate_response_bytes(completed.stdout)

    def test_worker_direct_isolated_script_success(self) -> None:
        request_raw = _raw(_request(_capture("capture-001", b"isolated-worker")))
        completed, cache_entries = _run_direct_worker(request_raw)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(b"", completed.stderr)
        self.assertEqual([], cache_entries)
        response = protocol.validate_response_bytes(completed.stdout)
        self.assertTrue(response["child_reported_runtime_guard_completed"])
        self.assertEqual(
            protocol.RUNTIME_GUARD_ATTESTATION_SCHEMA,
            response["runtime_guard_attestation"]["schema_version"],
        )
        attestation = response["runtime_guard_attestation"]
        self.assertEqual(sys.implementation.name, attestation["python_implementation"])
        self.assertEqual(sys.implementation.cache_tag, attestation["python_cache_tag"])
        self.assertEqual(list(sys.version_info[:3]), attestation["python_version"])
        self.assertEqual(0, attestation["runtime_flags"]["optimize"])
        protocol.validate_response_against_request(completed.stdout, request_raw)

    def test_worker_direct_rejects_missing_bound_pycache_prefix(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(WORKER_PATH)],
            cwd=ROOT,
            input=_raw(_request()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        self.assertEqual(4, completed.returncode)
        self.assertEqual(b"", completed.stdout)
        self.assertTrue(
            completed.stderr.startswith(b"P0_PARSER_PROCESS_RUNTIME_GUARD_ERROR:")
        )

    def test_worker_direct_rejects_wrong_prefix_and_missing_bytecode_flag(self) -> None:
        request_raw = _raw(_request())
        with tempfile.TemporaryDirectory(prefix="p0-worker-prefix-a-") as first, tempfile.TemporaryDirectory(
            prefix="p0-worker-prefix-b-"
        ) as second:
            cases = (
                (
                    [
                        sys.executable,
                        "-I",
                        "-S",
                        "-B",
                        "-X",
                        f"pycache_prefix={Path(first).resolve()}",
                        str(WORKER_PATH),
                        f"--p0-expected-pycache-prefix={Path(second).resolve()}",
                    ],
                    "wrong-prefix",
                ),
                (
                    [
                        sys.executable,
                        "-I",
                        "-S",
                        "-X",
                        f"pycache_prefix={Path(first).resolve()}",
                        str(WORKER_PATH),
                        f"--p0-expected-pycache-prefix={Path(first).resolve()}",
                    ],
                    "missing-B",
                ),
            )
            for command, label in cases:
                with self.subTest(label=label):
                    completed = subprocess.run(
                        command,
                        cwd=ROOT,
                        input=request_raw,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=15,
                    )
                    self.assertEqual(4, completed.returncode)
                    self.assertEqual(b"", completed.stdout)
                    self.assertTrue(
                        completed.stderr.startswith(
                            b"P0_PARSER_PROCESS_RUNTIME_GUARD_ERROR:"
                        )
                    )

    def test_worker_protocol_error_has_no_stdout_and_bounded_safe_stderr(self) -> None:
        secret = b"DO_NOT_ECHO_CAPTURE_PAYLOAD"
        bad = _raw(_request(_capture("capture-001", secret)))[:-1]
        completed = subprocess.run(
            [sys.executable, "-m", WORKER_MODULE],
            cwd=ROOT,
            input=bad,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
        self.assertEqual(2, completed.returncode)
        self.assertEqual(b"", completed.stdout)
        self.assertTrue(
            completed.stderr.startswith(b"P0_PARSER_PROCESS_PROTOCOL_ERROR:")
        )
        self.assertLessEqual(len(completed.stderr), 1024)
        self.assertNotIn(secret, completed.stderr)

    def test_worker_giant_duplicate_key_never_echoes_input(self) -> None:
        secret = b"GIANT_DUPLICATE_SECRET_" + b"X" * 5000
        raw = b'{"' + secret + b'":1,"' + secret + b'":2}\n'
        completed, cache_entries = _run_direct_worker(raw)
        self.assertEqual(2, completed.returncode)
        self.assertEqual(b"", completed.stdout)
        self.assertTrue(
            completed.stderr.startswith(b"P0_PARSER_PROCESS_PROTOCOL_ERROR:")
        )
        self.assertLessEqual(len(completed.stderr), 1024)
        self.assertNotIn(b"GIANT_DUPLICATE_SECRET", completed.stderr)
        self.assertNotIn(secret, completed.stderr)
        self.assertEqual([], cache_entries)


if __name__ == "__main__":
    unittest.main()
