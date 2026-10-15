from __future__ import annotations

import gc
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock
import weakref

from llm_batch.grounding import p0_windows_directory_change_watch as watch_contract


@unittest.skipUnless(os.name == "nt", "requires real Windows overlapped I/O")
class WindowsDirectoryChangeWatchIntegrationTests(unittest.TestCase):
    def _start(
        self,
        root: Path,
        *,
        subtree: bool = False,
        notify_filter: int = watch_contract.DEFAULT_NOTIFY_FILTER,
    ) -> watch_contract.WindowsDirectoryChangeWatch:
        return watch_contract.WindowsDirectoryChangeWatch.start(
            root,
            watch_subtree=subtree,
            notify_filter=notify_filter,
            cleanup_timeout_ms=2_000,
        )

    def _wait_for_completion(
        self, watcher: watch_contract.WindowsDirectoryChangeWatch
    ) -> watch_contract.WindowsDirectoryChangeBarrier:
        deadline = time.monotonic() + 5.0
        while True:
            barrier = watcher.barrier()
            if barrier.completion_observed:
                return barrier
            if time.monotonic() >= deadline:
                self.fail("directory notification did not complete within test bound")
            time.sleep(0.01)

    def test_pending_request_finalizes_as_narrow_success_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            watcher = self._start(
                Path(directory),
                notify_filter=watch_contract.FILE_NOTIFY_CHANGE_FILE_NAME,
            )
            identity = watcher.identity
            self.assertRegex(identity.file_id, r"^[0-9a-f]{32}$")
            self.assertTrue(identity.final_path.startswith("\\\\?\\Volume{"))
            self.assertGreater(identity.volume_serial, 0)

            barrier = watcher.barrier()
            self.assertEqual("PENDING", barrier.completion_status)
            self.assertTrue(barrier.request_pending_observed)
            self.assertTrue(barrier.observation_acceptable)

            close_spy = mock.Mock(wraps=watcher._resources.api.CloseHandle)
            watcher._resources.api.CloseHandle = close_spy
            first = watcher.finalize()
            second = watcher.finalize()

        self.assertIs(first, second)
        self.assertEqual("CANCELED_PENDING_AT_END", first.completion_status)
        self.assertTrue(first.pending_request_until_interval_end_observed)
        self.assertTrue(first.completion_drained_observed)
        self.assertTrue(first.watch_handles_non_inheritable_verified)
        self.assertTrue(first.watch_handles_closed_observed)
        self.assertFalse(first.quarantined_cleanup_observed)
        self.assertFalse(first.observation_gap_observed)
        self.assertTrue(
            first.project_source_directory_change_watch_observation_verified
        )
        self.assertEqual(2, close_spy.call_count)
        self.assertEqual([], first.as_dict()["events"])

    def test_delivered_event_fails_observation_and_preserves_event_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            watcher = self._start(
                root,
                notify_filter=(
                    watch_contract.FILE_NOTIFY_CHANGE_FILE_NAME
                    | watch_contract.FILE_NOTIFY_CHANGE_LAST_WRITE
                ),
            )
            (root / "changed.txt").write_text("changed", encoding="utf-8")
            barrier = self._wait_for_completion(watcher)
            outcome = watcher.finalize()

        self.assertEqual("DELIVERED", barrier.completion_status)
        self.assertFalse(barrier.observation_acceptable)
        self.assertEqual("DELIVERED", outcome.completion_status)
        self.assertTrue(
            outcome.directory_change_notification_delivered_observed
        )
        self.assertTrue(outcome.observation_gap_observed)
        self.assertFalse(
            outcome.project_source_directory_change_watch_observation_verified
        )
        self.assertIn("changed.txt", {event.relative_name for event in outcome.events})
        self.assertTrue(outcome.watch_handles_closed_observed)

    def test_recursive_parent_selected_watch_detects_nested_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            watcher = self._start(
                root,
                subtree=True,
                notify_filter=watch_contract.FILE_NOTIFY_CHANGE_FILE_NAME,
            )
            (nested / "inside.txt").write_bytes(b"inside")
            self._wait_for_completion(watcher)
            outcome = watcher.finalize()

        self.assertTrue(outcome.watch_subtree)
        self.assertIn(
            "nested\\inside.txt",
            {event.relative_name for event in outcome.events},
        )
        self.assertFalse(
            outcome.project_source_directory_change_watch_observation_verified
        )

    def test_barrier_after_finalize_cannot_reopen_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            watcher = self._start(Path(directory))
            outcome = watcher.finalize()
            barrier = watcher.barrier()

        self.assertTrue(
            outcome.project_source_directory_change_watch_observation_verified
        )
        self.assertFalse(barrier.request_pending_observed)
        self.assertTrue(barrier.completion_observed)
        self.assertFalse(barrier.observation_acceptable)

    def test_cleanup_timeout_quarantines_then_reaper_closes_exactly_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            watcher = self._start(Path(directory))
            resources = watcher._resources
            close_spy = mock.Mock(wraps=resources.close_once)
            resources.close_once = close_spy
            original = watch_contract._completion_for
            main_thread = threading.get_ident()
            injected = False

            def first_main_completion_times_out(
                value: object, timeout_ms: int
            ) -> object:
                nonlocal injected
                if threading.get_ident() == main_thread and not injected:
                    injected = True
                    return watch_contract._Completion(
                        "CLEANUP_TIMEOUT",
                        error_stage="completion_wait",
                        winerror=watch_contract._WAIT_TIMEOUT,
                    )
                return original(value, timeout_ms)

            with mock.patch.object(
                watch_contract,
                "_completion_for",
                side_effect=first_main_completion_times_out,
            ):
                outcome = watcher.finalize()
                self.assertTrue(resources.closed_event.wait(5.0))
            again = watcher.finalize()

        self.assertIs(outcome, again)
        self.assertEqual("CLEANUP_TIMEOUT", outcome.completion_status)
        self.assertTrue(outcome.quarantined_cleanup_observed)
        self.assertFalse(outcome.completion_drained_observed)
        self.assertFalse(outcome.watch_handles_closed_observed)
        self.assertTrue(outcome.observation_gap_observed)
        self.assertFalse(
            outcome.project_source_directory_change_watch_observation_verified
        )
        self.assertEqual(1, close_spy.call_count)

    def test_wait_error_is_cancelled_and_drained_but_never_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            watcher = self._start(Path(directory))
            original_wait = watcher._resources.api.WaitForSingleObject
            injected = False

            def first_wait_fails(handle: int, timeout_ms: int) -> int:
                nonlocal injected
                if not injected:
                    injected = True
                    return 0xFFFFFFFF
                return original_wait(handle, timeout_ms)

            watcher._resources.api.WaitForSingleObject = first_wait_fails
            outcome = watcher.finalize()

        self.assertEqual("POLL_ERROR", outcome.interval_end_poll_status)
        self.assertEqual(
            "CANCELED_PENDING_AT_END", outcome.cleanup_completion_status
        )
        self.assertEqual("CANCELED_PENDING_AT_END", outcome.completion_status)
        self.assertTrue(outcome.completion_drained_observed)
        self.assertTrue(outcome.watch_handles_closed_observed)
        self.assertTrue(outcome.observation_gap_observed)
        self.assertFalse(
            outcome.project_source_directory_change_watch_observation_verified
        )

    def test_poll_error_without_terminal_signal_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            watcher = self._start(root)
            (root / "raced.txt").write_text("raced", encoding="utf-8")
            original_wait = watcher._resources.api.WaitForSingleObject
            deadline = time.monotonic() + 5.0
            while (
                original_wait(watcher._resources.event_handle, 0)
                != watch_contract._WAIT_OBJECT_0
            ):
                if time.monotonic() >= deadline:
                    self.fail("poll-error fixture request did not complete")
                time.sleep(0.01)
            watcher._resources.api.WaitForSingleObject = lambda _h, _ms: 0xFFFFFFFF
            outcome = watcher.finalize()
            watcher._resources.api.WaitForSingleObject = original_wait
            self.assertTrue(watcher._resources.closed_event.wait(5.0))

        self.assertEqual("POLL_ERROR", outcome.interval_end_poll_status)
        self.assertEqual("CLEANUP_TIMEOUT", outcome.cleanup_completion_status)
        self.assertEqual("CLEANUP_TIMEOUT", outcome.completion_status)
        self.assertFalse(outcome.completion_drained_observed)
        self.assertTrue(outcome.quarantined_cleanup_observed)
        self.assertTrue(outcome.observation_gap_observed)
        self.assertFalse(
            outcome.project_source_directory_change_watch_observation_verified
        )

    def test_overflow_completion_is_closed_and_fails_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            watcher = self._start(root)
            (root / "trigger.txt").write_bytes(b"trigger")
            deadline = time.monotonic() + 5.0
            while (
                watcher._resources.api.WaitForSingleObject(
                    watcher._resources.event_handle, 0
                )
                != watch_contract._WAIT_OBJECT_0
            ):
                if time.monotonic() >= deadline:
                    self.fail("overflow fixture request did not complete")
                time.sleep(0.01)
            with mock.patch.object(
                watch_contract,
                "_completion_for",
                return_value=watch_contract._Completion(
                    "OVERFLOW", overflow=True, terminal_observed=True
                ),
            ):
                outcome = watcher.finalize()

        self.assertEqual("OVERFLOW", outcome.completion_status)
        self.assertTrue(outcome.overflow_observed)
        self.assertTrue(outcome.observation_gap_observed)
        self.assertTrue(outcome.watch_handles_closed_observed)
        self.assertFalse(
            outcome.project_source_directory_change_watch_observation_verified
        )

    def test_close_api_failure_is_reported_and_cannot_verify_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            watcher = self._start(Path(directory))
            original_close = watcher._resources.api.CloseHandle
            injected = False

            def fail_once_then_close(handle: int) -> int:
                nonlocal injected
                if not injected:
                    injected = True
                    return 0
                return original_close(handle)

            watcher._resources.api.CloseHandle = fail_once_then_close
            outcome = watcher.finalize()
            self.assertTrue(watcher._resources.closed_event.wait(5.0))

        self.assertFalse(outcome.watch_handles_closed_observed)
        self.assertEqual("CloseHandle", outcome.error_stage)
        self.assertTrue(outcome.quarantined_cleanup_observed)
        self.assertTrue(outcome.observation_gap_observed)
        self.assertFalse(
            outcome.project_source_directory_change_watch_observation_verified
        )

    def test_context_manager_finalizes_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            watcher = self._start(Path(directory))
            with watcher:
                self.assertTrue(watcher.barrier().observation_acceptable)
            outcome = watcher.finalize()
        self.assertTrue(outcome.watch_handles_closed_observed)

    def test_abandoned_watcher_is_cancelled_drained_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            watcher = self._start(Path(directory))
            resources = watcher._resources
            reference = weakref.ref(watcher)
            del watcher
            for _ in range(3):
                gc.collect()
                if reference() is None:
                    break
            self.assertIsNone(reference())
            self.assertTrue(resources.closed_event.wait(5.0))
        self.assertTrue(resources.closed)

    def test_reparse_directory_fails_closed_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real = base / "real"
            link = base / "link"
            real.mkdir()
            try:
                os.symlink(real, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            with self.assertRaisesRegex(
                watch_contract.P0WindowsDirectoryChangeWatchError,
                "reparse point",
            ):
                self._start(link)


class WindowsDirectoryChangeWatchContractTests(unittest.TestCase):
    def test_unsafe_paths_and_options_fail_before_win32_open(self) -> None:
        cases = (
            ("relative", False, watch_contract.DEFAULT_NOTIFY_FILTER, 100),
            (r"\\server\share\root", False, watch_contract.DEFAULT_NOTIFY_FILTER, 100),
            (r"C:\safe\..\root", False, watch_contract.DEFAULT_NOTIFY_FILTER, 100),
            (r"C:\safe\root:stream", False, watch_contract.DEFAULT_NOTIFY_FILTER, 100),
            (r"C:\safe\root. ", False, watch_contract.DEFAULT_NOTIFY_FILTER, 100),
            (r"C:\safe", 1, watch_contract.DEFAULT_NOTIFY_FILTER, 100),
            (r"C:\safe", False, 0, 100),
            (r"C:\safe", False, 0x80000000, 100),
            (r"C:\safe", False, watch_contract.DEFAULT_NOTIFY_FILTER, 0),
        )
        for path, subtree, notify_filter, timeout in cases:
            with self.subTest(path=path, subtree=subtree, timeout=timeout), mock.patch.object(
                watch_contract, "_Win32"
            ) as api, self.assertRaises(
                watch_contract.P0WindowsDirectoryChangeWatchError
            ):
                watch_contract.WindowsDirectoryChangeWatch.start(
                    path,
                    watch_subtree=subtree,  # type: ignore[arg-type]
                    notify_filter=notify_filter,
                    cleanup_timeout_ms=timeout,
                )
            api.assert_not_called()

    def test_malformed_extended_event_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            watch_contract.P0WindowsDirectoryChangeWatchError,
            "malformed extended directory-change event",
        ):
            watch_contract._parse_events(b"short")

    def test_overlapping_extended_event_records_are_rejected(self) -> None:
        raw = bytearray(172)
        raw[0:4] = (84).to_bytes(4, "little")
        raw[4:8] = (1).to_bytes(4, "little")
        raw[80:84] = (4).to_bytes(4, "little")
        with self.assertRaisesRegex(
            watch_contract.P0WindowsDirectoryChangeWatchError,
            "malformed extended directory-change offset",
        ):
            watch_contract._parse_events(bytes(raw))

    def test_outcome_false_inventory_cannot_be_confused_with_authority(self) -> None:
        fields = set(
            watch_contract.WindowsDirectoryChangeWatchOutcome.__dataclass_fields__
        )
        self.assertNotIn("runtime_noninterference_verified", fields)
        self.assertNotIn("namespace_change_absent_verified", fields)
        self.assertIn(
            "project_source_directory_change_watch_observation_verified", fields
        )


if __name__ == "__main__":
    unittest.main()
