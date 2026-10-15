"""실제 main 중첩 저장 함수의 AST 경계 계약. main/모델/네트워크는 실행하지 않는다."""
from __future__ import annotations

import ast
import ctypes
import errno
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "expert_main.py"


class _Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, delay):
        if not 0 < delay <= 0.200001:
            raise AssertionError(f"잘못된 backoff: {delay}")
        self.sleeps.append(delay)
        if len(self.sleeps) > 32:
            raise AssertionError("bounded retry가 종료하지 않음")
        self.now += delay


def _namespace(clock=None):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    main = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    names = {"_atomic_write_text", "_atomic_write_json", "_fsync_parent_directory"}
    functions = [node for node in main.body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    if len(functions) != 3 or {node.name for node in functions} != names:
        raise AssertionError("실제 main의 세 중첩 함수를 찾지 못함")
    # 프로세스 전역 os/time을 패치하지 않아 Path와 reader thread를 격리한다.
    os_proxy = SimpleNamespace(**vars(os))
    time_proxy = SimpleNamespace(**vars(time))
    if clock is not None:
        time_proxy.monotonic = clock.monotonic
        time_proxy.sleep = clock.sleep
    namespace = {
        "Path": Path, "Any": object, "os": os_proxy, "time": time_proxy,
        "threading": threading, "json": json, "sys": sys,
    }
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[
        ast.alias(name="annotations")], level=0), *functions], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace


def _windows_error(code):
    error = PermissionError(errno.EACCES, "교체 대상이 잠김")
    error.winerror = code
    return error


class _DeleteSharingLock:
    """실제 Windows 핸들. 잠금 사례는 기본값으로 DELETE 공유를 거부한다."""
    def __init__(self, path, *, share_delete=False):
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateFileW(
            str(path), 0x80000000, 0x1 | 0x2 | (0x4 if share_delete else 0),
            None, 3, 0x80, None,
        )
        if self.handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


def _read_with_delete_sharing(path):
    """교체와 호환되는 실제 reader. 실패를 무시하거나 다시 읽지 않는다."""
    if os.name != "nt":
        return path.read_bytes()
    from ctypes import wintypes
    opened = _DeleteSharingLock(path, share_delete=True)
    try:
        opened.kernel.ReadFile.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
        ]
        opened.kernel.ReadFile.restype = wintypes.BOOL
        buffer = ctypes.create_string_buffer(65536)
        chunks = []
        while True:
            count = wintypes.DWORD()
            if not opened.kernel.ReadFile(
                opened.handle, buffer, len(buffer), ctypes.byref(count), None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if not count.value:
                return b"".join(chunks)
            chunks.append(buffer.raw[:count.value])
    finally:
        opened.close()


class ExpertMainAtomicWriteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "결과.json"
        self.clock = _Clock()
        self.ns = _namespace(self.clock)
        self.os = self.ns["os"]
        self.write = self.ns["_atomic_write_text"]

    def _temps(self):
        return list(self.target.parent.glob(f".{self.target.name}.*.tmp"))

    def _assert_preserved(self, payload, previous=b"old"):
        self.assertEqual(self.target.read_bytes(), previous)
        temporary = self._temps()
        self.assertEqual(len(temporary), 1)
        self.assertEqual(temporary[0].read_bytes(), payload.encode("utf-8"))

    def _transient(self, codes):
        self.target.write_bytes(b"old")
        calls = []
        real_replace = os.replace

        def replace(source, destination):
            calls.append((Path(source), Path(destination)))
            self.assertEqual(self.target.read_bytes(), b"old")
            self.assertEqual(Path(source).read_bytes(), "새 결과\n".encode("utf-8"))
            if len(calls) <= len(codes):
                raise _windows_error(codes[len(calls) - 1])
            real_replace(source, destination)

        self.os.replace = replace
        self.write(self.target, "새 결과\n")
        self.assertEqual(len(calls), len(codes) + 1)
        self.assertEqual(len({source for source, _ in calls}), 1)
        self.assertTrue(all(destination == self.target for _, destination in calls))
        self.assertEqual(self.target.read_bytes(), "새 결과\n".encode("utf-8"))
        self.assertEqual(self._temps(), [])
        return calls

    def test_first_write_creates_parents_and_complete_utf8(self):
        self.target = self.root / "nested" / "결과.json"
        self.write(self.target, "한글 😀\n둘째 줄\n")
        self.assertEqual(self.target.read_bytes(), "한글 😀\n둘째 줄\n".encode("utf-8"))
        self.assertEqual(self._temps(), [])
        self.assertEqual(self.clock.sleeps, [])

    def test_existing_target_replaced_once(self):
        self.target.write_bytes(b"old")
        self.os.replace = mock.Mock(wraps=os.replace)
        self.write(self.target, "new")
        self.os.replace.assert_called_once()
        self.assertEqual(self.target.read_bytes(), b"new")
        self.assertEqual(self._temps(), [])
        self.assertEqual(self.clock.sleeps, [])

    def test_json_uses_real_text_writer_and_preserves_unicode(self):
        payload = {"작품": "봄의 기록", "목록": [1, None, True, "😀"]}
        self.ns["_atomic_write_json"](self.target, payload, indent=4)
        expected = json.dumps(payload, ensure_ascii=False, indent=4) + "\n"
        self.assertEqual(self.target.read_bytes(), expected.encode("utf-8"))
        self.assertEqual(json.loads(self.target.read_text(encoding="utf-8")), payload)

    def test_empty_text_is_valid_atomic_replacement(self):
        self.target.write_bytes(b"old")
        self.write(self.target, "")
        self.assertEqual(self.target.read_bytes(), b"")
        self.assertEqual(self._temps(), [])

    def test_json_serialization_error_does_not_touch_target(self):
        self.target.write_bytes(b"old")
        with self.assertRaises(TypeError):
            self.ns["_atomic_write_json"](self.target, {"bad": object()})
        self.assertEqual(self.target.read_bytes(), b"old")
        self.assertEqual(self._temps(), [])

    def test_winerror_5_recovers_after_observed_failure(self):
        self._transient([5])
        self.assertEqual(self.clock.sleeps, [0.02])

    def test_winerror_32_recovers_after_observed_failure(self):
        self._transient([32])
        self.assertEqual(self.clock.sleeps, [0.02])

    def test_winerror_33_recovers_after_observed_failure(self):
        self._transient([33])
        self.assertEqual(self.clock.sleeps, [0.02])

    def test_retry_backoff_doubles_then_caps_and_reuses_one_temp(self):
        self._transient([5, 32, 33, 5, 32, 33, 5])
        self.assertEqual(len(self.clock.sleeps), 7)
        for actual, expected in zip(self.clock.sleeps, [.02, .04, .08, .16, .2, .2, .2]):
            self.assertAlmostEqual(actual, expected)

    def test_recovery_diagnostic_occurs_once_without_payload_or_directory(self):
        messages = []

        def observe(*args, **kwargs):
            message = " ".join(str(part) for part in args)
            if "[atomic_replace_recovered]" in message:
                messages.append(message)

        with mock.patch("builtins.print", side_effect=observe):
            self._transient([5, 32])
        self.assertEqual(len(messages), 1)
        self.assertIn(self.target.name, messages[0])
        self.assertRegex(messages[0], r'''retry_count['"]?\s*[:=]\s*2\b''')
        self.assertNotIn("새 결과", messages[0])
        self.assertNotIn(str(self.root), messages[0])

    def test_recovery_diagnostic_failure_cannot_undo_successful_save(self):
        for error in (OSError(errno.EIO, "로그 파이프 닫힘"), ValueError("로그 스트림 닫힘")):
            with self.subTest(error=type(error).__name__):
                messages = []

                def fail_diagnostic(*args, **kwargs):
                    message = " ".join(str(part) for part in args)
                    if "[atomic_replace_recovered]" in message:
                        messages.append(message)
                        raise error

                with mock.patch("builtins.print", side_effect=fail_diagnostic):
                    self._transient([32])
                self.assertEqual(len(messages), 1)
                self.assertEqual(self.target.read_bytes(), "새 결과\n".encode("utf-8"))

    def test_permanent_retryable_failure_has_two_second_deadline(self):
        for code in (5, 32, 33):
            with self.subTest(winerror=code):
                target = self.root / f"blocked-{code}.txt"
                target.write_bytes(b"old")
                clock = _Clock()
                ns = _namespace(clock)
                errors = []

                def fail(source, destination):
                    error = _windows_error(code)
                    errors.append(error)
                    if len(errors) > 32:
                        raise AssertionError("deadline 이후에도 replace 반복")
                    self.assertEqual(target.read_bytes(), b"old")
                    raise error

                ns["os"].replace = fail
                with self.assertRaises(PermissionError) as caught:
                    ns["_atomic_write_text"](target, "new")
                self.assertIs(caught.exception, errors[-1])
                self.assertGreater(len(errors), 1)
                self.assertGreaterEqual(clock.now, 2.0 - 1e-8)
                self.assertLessEqual(clock.now, 2.0 + 1e-8)
                self.assertEqual(target.read_bytes(), b"old")
                temps = list(self.root.glob(f".{target.name}.*.tmp"))
                self.assertEqual(len(temps), 1)
                self.assertEqual(temps[0].read_bytes(), b"new")

    def test_replace_call_duration_counts_toward_deadline(self):
        self.target.write_bytes(b"old")
        error = _windows_error(5)

        def fail(source, destination):
            self.clock.now += 2.1
            raise error

        self.os.replace = mock.Mock(side_effect=fail)
        with self.assertRaises(PermissionError) as caught:
            self.write(self.target, "new")
        self.assertIs(caught.exception, error)
        self.os.replace.assert_called_once()
        self.assertEqual(self.clock.sleeps, [])
        self._assert_preserved("new")

    def test_unlisted_windows_errors_propagate_without_retry(self):
        for code in (2, 3, 6, 87, 112, 206):
            with self.subTest(winerror=code):
                target = self.root / f"error-{code}.txt"
                target.write_bytes(b"old")
                error = _windows_error(code)
                self.os.replace = mock.Mock(side_effect=error)
                with self.assertRaises(PermissionError) as caught:
                    self.write(target, "new")
                self.assertIs(caught.exception, error)
                self.os.replace.assert_called_once()
                self.assertEqual(target.read_bytes(), b"old")
                self.assertEqual(len(list(self.root.glob(f".{target.name}.*.tmp"))), 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_plain_permission_error_does_not_gain_windows_retry(self):
        self.target.write_bytes(b"old")
        error = PermissionError(errno.EACCES, "winerror가 없는 권한 오류")
        self.os.replace = mock.Mock(side_effect=error)
        with self.assertRaises(PermissionError) as caught:
            self.write(self.target, "new")
        self.assertIs(caught.exception, error)
        self.os.replace.assert_called_once()
        self.assertEqual(self.clock.sleeps, [])
        self._assert_preserved("new")

    def test_non_oserror_propagates_immediately(self):
        self.target.write_bytes(b"old")
        error = ValueError("invalid replacement")
        self.os.replace = mock.Mock(side_effect=error)
        with self.assertRaises(ValueError) as caught:
            self.write(self.target, "new")
        self.assertIs(caught.exception, error)
        self.os.replace.assert_called_once()
        self.assertEqual(self.clock.sleeps, [])
        self._assert_preserved("new")

    def test_retry_stops_on_later_nonretryable_error(self):
        self.target.write_bytes(b"old")
        last = OSError(errno.ENOSPC, "공간 부족")
        self.os.replace = mock.Mock(side_effect=[_windows_error(32), last])
        with self.assertRaises(OSError) as caught:
            self.write(self.target, "new")
        self.assertIs(caught.exception, last)
        self.assertEqual(self.os.replace.call_count, 2)
        self.assertEqual(self.clock.sleeps, [.02])
        self._assert_preserved("new")

    def test_file_fsync_failure_prevents_replace_and_parent_fsync(self):
        self.target.write_bytes(b"old")
        # replace에서는 재시도 대상인 같은 WinError라도 fsync에서는 즉시 전파한다.
        error = _windows_error(5)
        self.os.fsync = mock.Mock(side_effect=error)
        self.os.replace = mock.Mock(wraps=os.replace)
        self.os.open = mock.Mock(wraps=os.open)
        with self.assertRaises(OSError) as caught:
            self.write(self.target, "new")
        self.assertIs(caught.exception, error)
        self.os.replace.assert_not_called()
        self.os.open.assert_not_called()
        self.os.fsync.assert_called_once()
        self.assertEqual(self.clock.sleeps, [])
        self._assert_preserved("new")

    def test_parent_fsync_is_attempted_only_after_successful_replace(self):
        events = []
        self.target.write_bytes(b"old")

        def fsync(descriptor):
            events.append("file_fsync")
            os.fsync(descriptor)

        def replace(source, destination):
            events.append("replace")
            os.replace(source, destination)

        def directory_open(path, flags):
            events.append("parent_open")
            self.assertEqual(self.target.read_bytes(), b"new")
            raise OSError(errno.EACCES, "Windows 디렉터리 fsync 미지원")

        self.os.fsync, self.os.replace, self.os.open = fsync, replace, directory_open
        self.write(self.target, "new")
        self.assertEqual(events, ["file_fsync", "replace", "parent_open"])

    def test_failed_replace_never_fsyncs_parent(self):
        self.target.write_bytes(b"old")
        self.os.replace = mock.Mock(side_effect=_windows_error(5))
        self.os.open = mock.Mock(wraps=os.open)
        with self.assertRaises(PermissionError):
            self.write(self.target, "new")
        self.os.open.assert_not_called()
        self._assert_preserved("new")

    def test_actual_parent_fsync_closes_descriptor_when_fsync_fails(self):
        self.os.open = mock.Mock(return_value=761)
        self.os.fsync = mock.Mock(side_effect=OSError(errno.EIO, "directory fsync"))
        self.os.close = mock.Mock()
        self.ns["_fsync_parent_directory"](self.target)
        self.os.open.assert_called_once_with(str(self.target.parent), os.O_RDONLY)
        self.os.fsync.assert_called_once_with(761)
        self.os.close.assert_called_once_with(761)

    def test_actual_parent_fsync_closes_descriptor_on_success(self):
        self.os.open = mock.Mock(return_value=762)
        self.os.fsync = mock.Mock()
        self.os.close = mock.Mock()
        self.ns["_fsync_parent_directory"](self.target)
        self.os.fsync.assert_called_once_with(762)
        self.os.close.assert_called_once_with(762)

    def test_retry_does_not_delete_or_open_existing_target_for_write(self):
        self.os.unlink = mock.Mock(side_effect=AssertionError("unlink 금지"))
        self.os.remove = mock.Mock(side_effect=AssertionError("remove 금지"))
        real_open = Path.open

        def guarded_open(path, mode="r", *args, **kwargs):
            if path == self.target and any(flag in mode for flag in ("w", "a", "+")):
                raise AssertionError("기존 대상 비원자 쓰기 금지")
            return real_open(path, mode, *args, **kwargs)

        # seed는 guard 밖에서 준비한다. 경로 unlink도 실제 삭제 전에 차단한다.
        self.target.write_bytes(b"old")
        calls = 0

        def replace(source, destination):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise _windows_error(5)
            os.replace(source, destination)

        self.os.replace = replace
        with mock.patch.object(Path, "open", guarded_open), mock.patch.object(
            Path, "unlink", side_effect=AssertionError("Path.unlink 금지")
        ):
            self.write(self.target, "new")
        self.assertEqual(calls, 2)
        self.assertEqual(self.target.read_bytes(), b"new")
        self.os.unlink.assert_not_called()
        self.os.remove.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows CreateFileW 계약")
    def test_native_windows_lock_released_after_first_replace_failure(self):
        self.target.write_bytes(b"old")
        lock = _DeleteSharingLock(self.target)
        self.addCleanup(lock.close)
        failures = []
        attempts = []

        def replace(source, destination):
            attempts.append((Path(source), Path(destination)))
            try:
                os.replace(source, destination)
            except OSError as error:
                failures.append(error.winerror)
                self.assertEqual(self.target.read_bytes(), b"old")
                self.assertEqual(Path(source).read_bytes(), b"new")
                # 시간에 맞춰 해제하지 않는다. 실제 첫 replace 실패가 해제 신호다.
                lock.close()
                raise

        self.os.replace = replace
        self.write(self.target, "new")
        self.assertEqual(len(failures), 1)
        self.assertIn(failures[0], (5, 32, 33))
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0], attempts[1])
        self.assertEqual(self.clock.sleeps, [.02])
        self.assertEqual(self.target.read_bytes(), b"new")
        self.assertEqual(self._temps(), [])

    @unittest.skipUnless(os.name == "nt", "Windows CreateFileW 계약")
    def test_native_permanent_windows_lock_is_bounded_and_preserves_both_files(self):
        self.target.write_bytes(b"old")
        lock = _DeleteSharingLock(self.target)
        self.addCleanup(lock.close)
        attempts = []

        def replace(source, destination):
            attempts.append((Path(source), Path(destination)))
            if len(attempts) > 32:
                raise AssertionError("실제 잠금에서 무한 재시도")
            os.replace(source, destination)

        self.os.replace = replace
        with self.assertRaises(OSError) as caught:
            self.write(self.target, "new")
        self.assertIn(caught.exception.winerror, (5, 32, 33))
        self.assertGreater(len(attempts), 1)
        self.assertLessEqual(len(attempts), 32)
        self.assertAlmostEqual(self.clock.now, 2.0)
        self.assertEqual(len(set(attempts)), 1)
        self._assert_preserved("new")
        lock.close()

    def test_concurrent_reader_observes_only_complete_published_bytes(self):
        payloads = [(f"버전 {index}\n" + ("가나다😀" * 16384) + "\n끝\n").encode("utf-8")
                    for index in range(9)]
        allowed = set(payloads)
        self.target.write_bytes(payloads[0])
        ns = _namespace()  # 실제 reader와의 경쟁에는 실제 monotonic/sleep을 사용한다.
        stop = threading.Event()
        condition = threading.Condition()
        seen, errors = set(), []

        def reader():
            try:
                while not stop.is_set():
                    # Windows rename에 필요한 DELETE 공유를 명시한다. 기본
                    # Path.open의 새 open 무오류 가용성은 writer-only 계약이 아니다.
                    data = _read_with_delete_sharing(self.target)
                    with condition:
                        if data not in allowed:
                            raise AssertionError("reader가 부분/혼합 바이트를 관측함")
                        seen.add(data)
                        condition.notify_all()
                    time.sleep(0)
            except BaseException as error:
                with condition:
                    errors.append(error)
                    condition.notify_all()

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        try:
            for index, payload in enumerate(payloads):
                if index:
                    ns["_atomic_write_text"](self.target, payload.decode("utf-8"))
                with condition:
                    self.assertTrue(condition.wait_for(lambda: payload in seen or errors, timeout=5))
                    self.assertEqual(errors, [])
        finally:
            stop.set()
            thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(seen, allowed)
        self.assertEqual(self.target.read_bytes(), payloads[-1])
        self.assertEqual(self._temps(), [])


if __name__ == "__main__":
    unittest.main()
