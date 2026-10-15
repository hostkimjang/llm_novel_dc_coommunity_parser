from __future__ import annotations

import base64
from copy import deepcopy
import ctypes
import hashlib
import inspect
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from llm_batch.grounding import p0_parser_process_protocol as protocol
from llm_batch.grounding import p0_windows_parser_process_sandbox as sandbox


def _request_raw(*, launch_sha256: str | None = None) -> bytes:
    bindings = sandbox.windows_parser_process_launch_bindings()
    if launch_sha256 is not None:
        bindings["launch_sha256"] = launch_sha256
    payloads = (b"alpha", "한글 capture".encode("utf-8"))
    captures = []
    for index, payload in enumerate(payloads):
        captures.append(
            {
                "capture_id": f"capture-{index + 1}",
                "payload_base64": base64.b64encode(payload).decode("ascii"),
                "payload_bytes": len(payload),
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return protocol.canonical_file_bytes(
        {
            "schema_version": protocol.REQUEST_SCHEMA,
            "operation": protocol.OPERATION,
            "request_id": "sandbox-request-1",
            "parser_run_id": "sandbox-run-1",
            **bindings,
            "capture_manifest_sha256": "a" * 64,
            "input_registry_sha256": "b" * 64,
            "captures": captures,
        }
    )


@unittest.skipUnless(os.name == "nt", "Windows ctypes sandbox only")
class WindowsParserProcessSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.request_raw = _request_raw()
        cls.response, cls.receipt = sandbox.execute_windows_parser_process_sandbox(
            cls.request_raw, timeout_seconds=20.0
        )

    def test_actual_windows_fixed_worker_e2e_succeeds_component_only(self) -> None:
        self.assertEqual(self.receipt["gate_status"], sandbox.GATE_STATUS)
        self.assertEqual(
            self.receipt["request_sha256"],
            hashlib.sha256(self.request_raw).hexdigest(),
        )
        self.assertEqual(self.response["gate_status"], protocol.GATE_STATUS)
        self.assertEqual(self.receipt["exit_code"], 0)
        self.assertTrue(self.receipt["child_exit_zero_observed"])
        self.assertTrue(
            self.receipt[
                "canonical_child_response_exact_cross_binding_verified"
            ]
        )
        self.assertEqual(self.receipt["stderr_bytes"], 0)

    def test_token_and_job_are_read_back_exactly(self) -> None:
        token = self.receipt["restricted_primary_token"]
        self.assertTrue(token["token_type_primary_verified"])
        self.assertTrue(token["privilege_stripped_primary_token_verified"])
        self.assertEqual(token["remaining_privilege_names"], ["SeChangeNotifyPrivilege"])
        self.assertTrue(token["restricted_primary_token_verified"])
        self.assertTrue(token["is_token_restricted_api_result"])
        self.assertGreaterEqual(token["restricting_sid_count"], 2)
        self.assertEqual(
            token["restricting_sid_count"],
            token["enabled_token_group_sid_count"] + 1,
        )
        self.assertTrue(token["current_token_user_restricting_sid_exact_verified"])
        self.assertTrue(token["enabled_sid_projection_restricting_policy_verified"])
        self.assertFalse(token["filesystem_write_deny_verified"])
        job = self.receipt["job_object"]
        self.assertTrue(job["kill_on_job_close_configured_verified"])
        self.assertTrue(job["active_process_limit_one_configured_verified"])
        self.assertTrue(job["job_limit_policy_roundtrip_verified"])
        self.assertTrue(self.receipt["job_membership_before_resume_verified"])
        self.assertTrue(self.receipt["exact_three_handle_list_configured_verified"])

    def test_fixed_base_executable_and_argv_are_exactly_bound(self) -> None:
        fixed = self.receipt["fixed_launch"]
        expected_base = str(Path(sys._base_executable).resolve(strict=True))
        expected_caller = str(Path(sys.executable).resolve(strict=True))
        expected_worker = str(Path(sandbox.worker.__file__).resolve(strict=True))
        self.assertEqual(fixed["executable_path"], expected_base)
        self.assertEqual(fixed["application_name"], expected_base)
        self.assertEqual(fixed["caller_sys_executable_path"], expected_caller)
        cache_root = self.receipt["isolated_pycache"]["root_path"]
        self.assertEqual(
            fixed["argv"],
            [
                expected_base,
                "-I",
                "-S",
                "-B",
                "-X",
                f"pycache_prefix={cache_root}",
                expected_worker,
                f"--p0-expected-pycache-prefix={cache_root}",
            ],
        )
        self.assertEqual(
            fixed["argv_template"],
            [
                expected_base,
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=<PER_EXECUTION_EMPTY_ROOT>",
                expected_worker,
                "--p0-expected-pycache-prefix=<PER_EXECUTION_EMPTY_ROOT>",
            ],
        )
        self.assertFalse(
            fixed["launch_files_path_hashed_and_handles_held_observed"]
        )
        self.assertTrue(
            fixed["launch_files_handle_hashed_and_handles_held_observed"]
        )

    def test_handle_identity_source_inventory_and_suspended_image_are_narrow(self) -> None:
        fixed = self.receipt["fixed_launch"]
        inventory = fixed["launch_file_inventory"]
        self.assertEqual(len(inventory), 9)
        self.assertTrue(
            {
                "parser_sandbox_policy_source",
                "directory_watch_policy_source",
                "fixed_directory_identity_policy_source",
            }.issubset({item["role"] for item in inventory})
        )
        self.assertEqual(
            {
                item["role"]
                for item in fixed["required_project_source_candidate_manifest"]
            },
            {
                "llm_batch_init_source_candidate",
                "grounding_init_source_candidate",
                "worker_source_candidate",
                "protocol_source_candidate",
            },
        )
        self.assertTrue(
            fixed["required_project_source_candidate_manifest_exact_verified"]
        )
        self.assertGreater(fixed["launch_namespace_guard_count"], 0)
        for item in inventory:
            self.assertRegex(item["file_id"], r"^[0-9a-f]{32}$")
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(item["bytes"], 0)
            self.assertTrue(item["final_path"].startswith(r"\\?\Volume{"))
        self.assertTrue(
            self.receipt[
                "launch_file_handle_and_path_identity_before_create_verified"
            ]
        )
        self.assertTrue(
            self.receipt[
                "launch_file_handle_and_path_identity_before_resume_verified"
            ]
        )
        self.assertTrue(
            self.receipt[
                "launch_file_handle_and_path_identity_after_exit_verified"
            ]
        )
        self.assertTrue(
            self.receipt[
                "reported_child_image_path_reopened_to_pinned_executable_before_resume_verified"
            ]
        )
        evidence = self.receipt["suspended_process_identity"]
        self.assertEqual(evidence["process_id"], self.receipt["process_id"])
        self.assertGreater(int(evidence["creation_time_100ns"]), 0)
        executable = next(
            item for item in inventory if item["role"] == "base_executable"
        )
        self.assertEqual(evidence["reopened_image_file_id"], executable["file_id"])
        self.assertEqual(evidence["reopened_image_sha256"], executable["sha256"])
        self.assertFalse(self.receipt["project_source_load_candidate_closure_verified"])
        self.assertFalse(self.receipt["parser_dependency_closure_verified"])

    def test_narrow_source_candidate_closure_has_all_required_evidence(self) -> None:
        fixed = self.receipt["fixed_launch"]
        self.assertTrue(fixed["static_import_collision_inventory_verified"])
        self.assertEqual(
            [], fixed["bounded_project_source_candidate_closure_blockers"]
        )
        self.assertGreaterEqual(
            len(fixed["broader_parser_dependency_closure_blockers"]), 3
        )
        self.assertEqual(
            {
                "src_directory",
                "llm_batch_directory",
                "grounding_directory",
            },
            {
                item["role"]
                for item in fixed["source_directory_collision_inventories"]
            },
        )
        self.assertRegex(fixed["source_import_graph_sha256"], r"^[0-9a-f]{64}$")
        self.assertIn(".py", fixed["import_suffix_universe"])
        cache = self.receipt["isolated_pycache"]
        for field in (
            "empty_before_create_verified",
            "empty_before_resume_verified",
            "empty_after_exit_verified",
            "exact_handle_cleanup_attempted",
            "delete_disposition_set_verified",
            "disposition_handle_close_succeeded_verified",
            "exact_handle_cleanup_succeeded",
            "path_absent_after_cleanup_verified",
            "normal_repository_pycache_lookup_excluded_observed",
        ):
            self.assertTrue(cache[field], field)
        observation = self.receipt["directory_change_observation"]
        self.assertTrue(observation["all_required_watch_intervals_verified"])
        self.assertFalse(observation["filesystem_noninterference_inferred"])
        self.assertEqual(
            {
                "source_parent_nonrecursive",
                "source_root_recursive",
                "pycache_root_recursive",
            },
            set(observation["outcomes"]),
        )
        self.assertEqual(12, len(observation["barriers"]))
        for outcome in observation["outcomes"].values():
            self.assertTrue(
                outcome[
                    "project_source_directory_change_watch_observation_verified"
                ]
            )
            self.assertFalse(outcome["observation_gap_observed"])
        self.assertTrue(self.receipt["child_project_origin_guard_completed_observed"])
        self.assertTrue(
            self.receipt[
                "child_runtime_guard_attestation_cross_binding_verified"
            ]
        )
        self.assertEqual(
            [
                "llm_batch",
                "llm_batch.grounding",
                "llm_batch.grounding.p0_parser_process_protocol",
            ],
            [
                item["module_name"]
                for item in self.receipt["child_runtime_guard_attestation"][
                    "project_specs"
                ]
            ],
        )
        attestation = self.receipt["child_runtime_guard_attestation"]
        self.assertEqual(sys.implementation.name, attestation["python_implementation"])
        self.assertEqual(sys.implementation.cache_tag, attestation["python_cache_tag"])
        self.assertEqual(list(sys.version_info[:3]), attestation["python_version"])
        expected_origins = (
            fixed["llm_batch_init_path"],
            fixed["grounding_init_path"],
            fixed["protocol_path"],
        )
        for item, origin in zip(attestation["project_specs"], expected_origins):
            expected_cache = sandbox._expected_prefixed_cache_path(
                origin, cache["root_path"], sys.implementation.cache_tag
            )
            self.assertEqual(
                sandbox._normalized_path_sha256(expected_cache),
                item["cached_path_sha256"],
            )
        self.assertTrue(
            self.receipt[
                "bounded_project_source_load_candidate_closure_verified"
            ]
        )

    def test_static_collision_inventory_rejects_alternate_pyc_candidate(self) -> None:
        suffixes = self.receipt["fixed_launch"]["import_suffix_universe"]
        alternate_names = [
            "P0_Parser_Process_Protocol.py",
            "p0_parser_process_protocol",
            *(
                "p0_parser_process_protocol" + suffix
                for suffix in suffixes
                if suffix != ".py"
            ),
        ]
        for alternate_name in alternate_names:
            values = []
            for item in self.receipt["fixed_launch"][
                "source_directory_collision_inventories"
            ]:
                projection = [dict(entry) for entry in item["inventory"]]
                if item["role"] == "grounding_directory":
                    alternate = dict(
                        next(
                            entry
                            for entry in projection
                            if entry["name"] == "p0_parser_process_protocol.py"
                        )
                    )
                    alternate["name"] = alternate_name
                    projection.append(alternate)
                values.append(
                    sandbox._SourceDirectoryInventory(
                        role=item["role"],
                        path=Path(item["path"]),
                        projection=tuple(projection),
                        sha256="0" * 64,
                    )
                )
            with self.subTest(alternate=alternate_name), self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                "alternate import candidate|Unicode/case-colliding",
            ):
                sandbox._validate_source_collision_inventories(tuple(values))

    def test_runtime_guard_attestation_rejects_child_abi_and_cache_path_drift(
        self,
    ) -> None:
        api = sandbox._Win32()
        pinned = sandbox._pin_launch(api)
        cache = sandbox._PinnedPycache(
            path=Path(self.receipt["isolated_pycache"]["root_path"]),
            handle=0,
            snapshot=None,
        )
        try:
            wrong_abi = deepcopy(self.response)
            wrong_abi["runtime_guard_attestation"]["python_cache_tag"] = (
                "cpython-999"
            )
            with self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                "attestation cross-binding mismatch",
            ):
                sandbox._validate_child_runtime_guard_attestation(
                    wrong_abi, pinned, cache
                )

            wrong_cache = deepcopy(self.response)
            wrong_cache["runtime_guard_attestation"]["project_specs"][0][
                "cached_path_sha256"
            ] = "0" * 64
            with self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                "attestation cross-binding mismatch",
            ):
                sandbox._validate_child_runtime_guard_attestation(
                    wrong_cache, pinned, cache
                )
        finally:
            for handle in pinned.handles:
                sandbox._close(api, handle)

    def test_stable_launch_hash_excludes_unique_per_execution_cache_root(self) -> None:
        first = sandbox.windows_parser_process_launch_bindings()
        second = sandbox.windows_parser_process_launch_bindings()
        self.assertEqual(first, second)
        _response, other = sandbox.execute_windows_parser_process_sandbox(
            self.request_raw, timeout_seconds=20.0
        )
        self.assertEqual(
            self.receipt["fixed_launch"]["launch_sha256"],
            other["fixed_launch"]["launch_sha256"],
        )
        self.assertNotEqual(
            self.receipt["isolated_pycache"]["root_path"],
            other["isolated_pycache"]["root_path"],
        )
        self.assertNotEqual(self.receipt["receipt_sha256"], other["receipt_sha256"])

    def test_pycache_handle_close_failure_cannot_verify_bounded_closure(self) -> None:
        real_api = sandbox._Win32()

        class CacheCloseFailureProxy:
            disposition_set = False
            injected = False

            def __getattr__(self, name: str):
                return getattr(real_api, name)

            def SetFileInformationByHandle(self, *args: object) -> bool:
                result = bool(real_api.SetFileInformationByHandle(*args))
                if result:
                    self.disposition_set = True
                return result

            def CloseHandle(self, handle: int) -> bool:
                if self.disposition_set and not self.injected:
                    self.injected = True
                    ctypes.set_last_error(5)
                    return False
                return bool(real_api.CloseHandle(handle))

        with mock.patch.object(
            sandbox, "_Win32", return_value=CacheCloseFailureProxy()
        ):
            with self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                r"CloseHandle\(pycache disposition handle\)",
            ) as captured:
                sandbox.execute_windows_parser_process_sandbox(
                    self.request_raw, timeout_seconds=20.0
                )
        receipt = captured.exception.receipt
        self.assertIsNotNone(receipt)
        assert receipt is not None
        cache = receipt["isolated_pycache"]
        self.assertTrue(cache["delete_disposition_set_verified"])
        self.assertFalse(cache["disposition_handle_close_succeeded_verified"])
        self.assertFalse(cache["exact_handle_cleanup_succeeded"])
        self.assertFalse(
            receipt["bounded_project_source_load_candidate_closure_verified"]
        )
        self.assertFalse(Path(cache["root_path"]).exists())

    def test_all_broad_security_and_authority_claims_remain_false(self) -> None:
        for field in sandbox._FALSE_FIELDS:
            self.assertIs(self.receipt[field], False, field)
        self.assertEqual(
            self.receipt["credited_counts"],
            {
                "actual_source_claim_count": 0,
                "actual_a_context_review_count": 0,
            },
        )
        for field in protocol.FALSE_AUTHORITY_FIELDS:
            self.assertIs(self.response[field], False, field)

    def test_launch_mismatch_is_rejected_before_token_or_process_creation(self) -> None:
        raw = _request_raw(launch_sha256="d" * 64)
        with mock.patch.object(
            sandbox, "_create_privilege_stripped_primary_token"
        ) as token_create:
            with self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                "fixed-launch binding mismatch",
            ):
                sandbox.execute_windows_parser_process_sandbox(raw)
        token_create.assert_not_called()

    def test_tiny_timeout_terminates_job_and_attaches_failure_receipt(self) -> None:
        with self.assertRaises(
            sandbox.P0WindowsParserProcessSandboxError
        ) as captured:
            sandbox.execute_windows_parser_process_sandbox(
                self.request_raw, timeout_seconds=1e-9
            )
        receipt = captured.exception.receipt
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertTrue(receipt["process_timeout_observed"])
        self.assertTrue(receipt["termination_after_failure_observed"])
        self.assertFalse(
            receipt["canonical_child_response_exact_cross_binding_verified"]
        )
        self.assertFalse(
            receipt["bounded_project_source_load_candidate_closure_verified"]
        )
        for field in sandbox._FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)

    def test_assignment_failure_terminates_unassigned_suspended_child(self) -> None:
        real_api = sandbox._Win32()

        class AssignFailureProxy:
            def __getattr__(self, name: str):
                return getattr(real_api, name)

            def AssignProcessToJobObject(self, job: int, process: int) -> bool:
                ctypes.set_last_error(5)
                return False

        with mock.patch.object(sandbox, "_Win32", return_value=AssignFailureProxy()):
            with self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                "AssignProcessToJobObject",
            ) as captured:
                sandbox.execute_windows_parser_process_sandbox(self.request_raw)
        receipt = captured.exception.receipt
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertFalse(receipt["job_membership_before_resume_verified"])
        self.assertFalse(receipt["initial_thread_resumed_verified"])
        self.assertTrue(receipt["termination_after_failure_observed"])
        self.assertEqual(receipt["stdout_bytes"], 0)
        self.assertEqual(receipt["stderr_bytes"], 0)
        self.assertFalse(
            receipt["canonical_child_response_exact_cross_binding_verified"]
        )

    def test_reported_image_mismatch_is_rejected_before_resume(self) -> None:
        real_api = sandbox._Win32()

        class ImageMismatchProxy:
            resume_called = False

            def __getattr__(self, name: str):
                return getattr(real_api, name)

            def QueryFullProcessImageNameW(
                self, process: int, flags: int, buffer: object, size: object
            ) -> bool:
                value = str(Path(sandbox.worker.__file__).resolve(strict=True))
                buffer.value = value
                ctypes.cast(size, ctypes.POINTER(ctypes.wintypes.DWORD)).contents.value = len(
                    value
                )
                return True

            def ResumeThread(self, thread: int) -> int:
                self.resume_called = True
                return real_api.ResumeThread(thread)

        proxy = ImageMismatchProxy()
        with mock.patch.object(sandbox, "_Win32", return_value=proxy):
            with self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                "reported child image path did not reopen",
            ) as captured:
                sandbox.execute_windows_parser_process_sandbox(self.request_raw)
        self.assertFalse(proxy.resume_called)
        receipt = captured.exception.receipt
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertFalse(receipt["initial_thread_resumed_verified"])
        self.assertTrue(receipt["termination_after_failure_observed"])
        self.assertFalse(
            receipt[
                "reported_child_image_path_reopened_to_pinned_executable_before_resume_verified"
            ]
        )

    def test_process_identity_queries_precede_resume(self) -> None:
        real_api = sandbox._Win32()
        calls: list[str] = []

        class OrderingProxy:
            def __getattr__(self, name: str):
                return getattr(real_api, name)

            def GetProcessTimes(self, *args: object) -> bool:
                calls.append("GetProcessTimes")
                return real_api.GetProcessTimes(*args)

            def QueryFullProcessImageNameW(self, *args: object) -> bool:
                calls.append("QueryFullProcessImageNameW")
                return real_api.QueryFullProcessImageNameW(*args)

            def ResumeThread(self, thread: int) -> int:
                calls.append("ResumeThread")
                return real_api.ResumeThread(thread)

        with mock.patch.object(sandbox, "_Win32", return_value=OrderingProxy()):
            _response, receipt = sandbox.execute_windows_parser_process_sandbox(
                self.request_raw
            )
        self.assertLess(calls.index("GetProcessTimes"), calls.index("ResumeThread"))
        self.assertLess(
            calls.index("QueryFullProcessImageNameW"), calls.index("ResumeThread")
        )
        self.assertTrue(receipt["initial_thread_resumed_verified"])

    def test_unexpected_resume_count_terminates_suspended_child(self) -> None:
        real_api = sandbox._Win32()

        class ResumeCountProxy:
            def __getattr__(self, name: str):
                return getattr(real_api, name)

            def ResumeThread(self, thread: int) -> int:
                return 2

        with mock.patch.object(sandbox, "_Win32", return_value=ResumeCountProxy()):
            with self.assertRaisesRegex(
                sandbox.P0WindowsParserProcessSandboxError,
                "unexpected suspend count",
            ) as captured:
                sandbox.execute_windows_parser_process_sandbox(self.request_raw)
        receipt = captured.exception.receipt
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertFalse(receipt["initial_thread_resumed_verified"])
        self.assertTrue(receipt["termination_after_failure_observed"])

    def test_held_leaf_handle_denies_rename_until_cleanup(self) -> None:
        api = sandbox._Win32()
        directory = Path(tempfile.mkdtemp(prefix="p0-handle-pin-"))
        source = directory / "source.py"
        replacement = directory / "replacement.py"
        source.write_bytes(b"print('source')\n")
        replacement.write_bytes(b"print('replacement')\n")
        guard = sandbox._pin_directory(api, directory)
        pinned = sandbox._pin_one(
            api,
            role="test_source",
            path=source,
            immediate_parent=guard,
            project_source_candidate=True,
        )
        try:
            with self.assertRaises(OSError):
                os.replace(replacement, source)
            self.assertEqual(
                sandbox._hash_held_file(
                    api, pinned.handle, pinned.snapshot, pinned.role
                ),
                pinned.sha256,
            )
        finally:
            sandbox._close(api, pinned.handle)
            sandbox._close(api, guard.handle)
        os.replace(replacement, source)
        source.unlink()
        directory.rmdir()

    def test_forged_resealed_child_response_fails_parent_cross_binding(self) -> None:
        response = protocol.validate_response_bytes(
            protocol.execute_request_bytes(self.request_raw)
        )
        response["request_id"] = "forged-request"
        material = {
            key: value for key, value in response.items() if key != "receipt_sha256"
        }
        response["receipt_sha256"] = protocol.canonical_sha256(material)
        forged_raw = protocol.canonical_file_bytes(response)
        # The child response is internally well formed and self-hashed, but it
        # is not the response to the parent's exact request.
        protocol.validate_response_bytes(forged_raw)
        with self.assertRaisesRegex(
            protocol.P0ParserProcessProtocolError, "cross-binding mismatch"
        ):
            protocol.validate_response_against_request(
                forged_raw, self.request_raw
            )

    def test_post_create_cross_binding_failure_attaches_no_go_receipt(self) -> None:
        with mock.patch.object(
            protocol,
            "validate_response_against_request",
            side_effect=protocol.P0ParserProcessProtocolError("injected mismatch"),
        ):
            with self.assertRaises(
                sandbox.P0WindowsParserProcessSandboxError
            ) as captured:
                sandbox.execute_windows_parser_process_sandbox(
                    self.request_raw, timeout_seconds=20.0
                )
        receipt = captured.exception.receipt
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(receipt["exit_code"], 0)
        self.assertTrue(receipt["child_exit_zero_observed"])
        self.assertFalse(
            receipt["canonical_child_response_exact_cross_binding_verified"]
        )
        for field in sandbox._FALSE_FIELDS:
            self.assertIs(receipt[field], False, field)

    def test_public_api_accepts_no_executable_worker_or_command(self) -> None:
        signature = inspect.signature(
            sandbox.execute_windows_parser_process_sandbox
        )
        self.assertEqual(list(signature.parameters), ["request_raw", "timeout_seconds"])
        source = inspect.getsource(sandbox)
        self.assertNotIn("def _sha_file", source)
        self.assertNotIn("Path.open(\"rb\")", source)
        self.assertNotIn("CreateProcessWithTokenW", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("restricted_sid_launch_fallback", source)
        self.assertNotIn("zero_restricting_sid", source)


if __name__ == "__main__":
    unittest.main()
