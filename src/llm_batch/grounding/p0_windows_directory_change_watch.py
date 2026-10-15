"""Bounded Windows directory-change observation for P0 components.

The observer maintains one pending ``ReadDirectoryChangesExW`` request across
an explicitly delimited interval.  A successful outcome means only that the
request was still pending at the interval boundary and was then observed to
complete as cancelled.  It does not prove filesystem non-interference or an
authorized namespace.

Importing this module is portable.  Starting a watch outside Windows fails
closed before opening a filesystem object.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import ntpath
import os
import re
import threading
import time
from typing import Any
import weakref


WATCH_OUTCOME_SCHEMA = "p0_windows_directory_change_watch_outcome_v1"

FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x00000004
FILE_NOTIFY_CHANGE_SIZE = 0x00000008
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010
FILE_NOTIFY_CHANGE_LAST_ACCESS = 0x00000020
FILE_NOTIFY_CHANGE_CREATION = 0x00000040
FILE_NOTIFY_CHANGE_SECURITY = 0x00000100
DEFAULT_NOTIFY_FILTER = (
    FILE_NOTIFY_CHANGE_FILE_NAME
    | FILE_NOTIFY_CHANGE_DIR_NAME
    | FILE_NOTIFY_CHANGE_ATTRIBUTES
    | FILE_NOTIFY_CHANGE_SIZE
    | FILE_NOTIFY_CHANGE_LAST_WRITE
    | FILE_NOTIFY_CHANGE_LAST_ACCESS
    | FILE_NOTIFY_CHANGE_CREATION
    | FILE_NOTIFY_CHANGE_SECURITY
)

DEFAULT_CLEANUP_TIMEOUT_MS = 2_000
MAX_CLEANUP_TIMEOUT_MS = 30_000

_IS_WINDOWS = os.name == "nt"
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_ERROR_IO_INCOMPLETE = 996
_ERROR_IO_PENDING = 997
_ERROR_OPERATION_ABORTED = 995
_ERROR_NOT_FOUND = 1168
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258

_FILE_LIST_DIRECTORY = 0x0001
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_OVERLAPPED = 0x40000000
_HANDLE_FLAG_INHERIT = 0x00000001

_FILE_STANDARD_INFO_CLASS = 1
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_ID_INFO_CLASS = 18
_FILE_NAME_NORMALIZED = 0x0
_VOLUME_NAME_GUID = 0x1
_READ_DIRECTORY_NOTIFY_EXTENDED_INFORMATION = 2
_WATCH_BUFFER_BYTES = 64 * 1024
_MAX_FINAL_PATH_CHARS = 32_768

_LOCAL_DOS_PATH = re.compile(r"^[A-Za-z]:\\")
_VOLUME_GUID_PATH = re.compile(
    r"^\\\\\?\\Volume\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}(?:\\.*)?$"
)


class P0WindowsDirectoryChangeWatchError(RuntimeError):
    """The watcher could not preserve its bounded observation contract."""

    def __init__(
        self,
        message: str,
        *,
        outcome: "WindowsDirectoryChangeWatchOutcome | None" = None,
    ) -> None:
        super().__init__(message)
        self.outcome = outcome


class _FILE_ID_128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_ubyte * 16)]


class _FILE_ID_INFO(ctypes.Structure):
    _fields_ = [
        ("VolumeSerialNumber", ctypes.c_ulonglong),
        ("FileId", _FILE_ID_128),
    ]


class _FILE_STANDARD_INFO(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", ctypes.c_longlong),
        ("EndOfFile", ctypes.c_longlong),
        ("NumberOfLinks", wintypes.DWORD),
        ("DeletePending", ctypes.c_ubyte),
        ("Directory", ctypes.c_ubyte),
    ]


class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
    _fields_ = [
        ("FileAttributes", wintypes.DWORD),
        ("ReparseTag", wintypes.DWORD),
    ]


class _OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


@dataclass(frozen=True)
class WindowsDirectoryIdentity:
    """Kernel-handle identity observed for the watched local directory."""

    final_path: str
    volume_serial: int
    file_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "final_path": self.final_path,
            "volume_serial": str(self.volume_serial),
            "file_id": self.file_id,
        }


@dataclass(frozen=True)
class WindowsDirectoryChangeEvent:
    action: int
    relative_name: str
    file_id: str
    parent_file_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "relative_name": self.relative_name,
            "file_id": self.file_id,
            "parent_file_id": self.parent_file_id,
        }


@dataclass(frozen=True)
class WindowsDirectoryChangeBarrier:
    """Non-destructive poll of the one outstanding request."""

    counter_ns: int
    completion_status: str
    request_pending_observed: bool
    completion_observed: bool
    observation_acceptable: bool


@dataclass(frozen=True)
class WindowsDirectoryChangeWatchOutcome:
    """Truthfully scoped result of finalizing one pending request."""

    schema_version: str
    requested_path: str
    identity: WindowsDirectoryIdentity
    watch_subtree: bool
    notify_filter: int
    api_available: bool
    armed: bool
    armed_counter_ns: int
    interval_end_counter_ns: int
    interval_end_poll_status: str
    cleanup_completion_status: str
    completion_status: str
    events: tuple[WindowsDirectoryChangeEvent, ...]
    directory_change_notification_delivered_observed: bool
    overflow_observed: bool
    observation_gap_observed: bool
    pending_request_until_interval_end_observed: bool
    completion_drained_observed: bool
    watch_handles_non_inheritable_verified: bool
    watch_handles_closed_observed: bool
    quarantined_cleanup_observed: bool
    project_source_directory_change_watch_observation_verified: bool
    error_stage: str | None
    winerror: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "requested_path": self.requested_path,
            "identity": self.identity.as_dict(),
            "watch_subtree": self.watch_subtree,
            "notify_filter": self.notify_filter,
            "api_available": self.api_available,
            "armed": self.armed,
            "armed_counter_ns": self.armed_counter_ns,
            "interval_end_counter_ns": self.interval_end_counter_ns,
            "interval_end_poll_status": self.interval_end_poll_status,
            "cleanup_completion_status": self.cleanup_completion_status,
            "completion_status": self.completion_status,
            "events": [event.as_dict() for event in self.events],
            "directory_change_notification_delivered_observed": (
                self.directory_change_notification_delivered_observed
            ),
            "overflow_observed": self.overflow_observed,
            "observation_gap_observed": self.observation_gap_observed,
            "pending_request_until_interval_end_observed": (
                self.pending_request_until_interval_end_observed
            ),
            "completion_drained_observed": self.completion_drained_observed,
            "watch_handles_non_inheritable_verified": (
                self.watch_handles_non_inheritable_verified
            ),
            "watch_handles_closed_observed": self.watch_handles_closed_observed,
            "quarantined_cleanup_observed": self.quarantined_cleanup_observed,
            "project_source_directory_change_watch_observation_verified": (
                self.project_source_directory_change_watch_observation_verified
            ),
            "error_stage": self.error_stage,
            "winerror": self.winerror,
        }


@dataclass(frozen=True)
class _Completion:
    status: str
    events: tuple[WindowsDirectoryChangeEvent, ...] = ()
    overflow: bool = False
    error_stage: str | None = None
    winerror: int | None = None
    terminal_observed: bool = False


class _Win32:
    def __init__(self) -> None:
        if not _IS_WINDOWS:
            raise P0WindowsDirectoryChangeWatchError(
                "Windows directory-change observation is unavailable"
            )
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        self.CreateFileW = kernel32.CreateFileW
        self.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.CreateFileW.restype = wintypes.HANDLE

        self.CloseHandle = kernel32.CloseHandle
        self.CloseHandle.argtypes = [wintypes.HANDLE]
        self.CloseHandle.restype = wintypes.BOOL

        self.GetFileInformationByHandleEx = kernel32.GetFileInformationByHandleEx
        self.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        self.GetFileInformationByHandleEx.restype = wintypes.BOOL

        self.GetFinalPathNameByHandleW = kernel32.GetFinalPathNameByHandleW
        self.GetFinalPathNameByHandleW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self.GetFinalPathNameByHandleW.restype = wintypes.DWORD

        self.GetHandleInformation = kernel32.GetHandleInformation
        self.GetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
        self.GetHandleInformation.restype = wintypes.BOOL

        self.CreateEventW = kernel32.CreateEventW
        self.CreateEventW.argtypes = [
            wintypes.LPVOID,
            wintypes.BOOL,
            wintypes.BOOL,
            wintypes.LPCWSTR,
        ]
        self.CreateEventW.restype = wintypes.HANDLE

        self.ReadDirectoryChangesExW = getattr(
            kernel32, "ReadDirectoryChangesExW", None
        )
        if self.ReadDirectoryChangesExW is not None:
            self.ReadDirectoryChangesExW.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
                wintypes.LPDWORD,
                ctypes.POINTER(_OVERLAPPED),
                wintypes.LPVOID,
                ctypes.c_int,
            ]
            self.ReadDirectoryChangesExW.restype = wintypes.BOOL

        self.WaitForSingleObject = kernel32.WaitForSingleObject
        self.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.WaitForSingleObject.restype = wintypes.DWORD

        self.CancelIoEx = kernel32.CancelIoEx
        self.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(_OVERLAPPED)]
        self.CancelIoEx.restype = wintypes.BOOL

        self.GetOverlappedResultEx = getattr(kernel32, "GetOverlappedResultEx", None)
        if self.GetOverlappedResultEx is not None:
            self.GetOverlappedResultEx.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_OVERLAPPED),
                wintypes.LPDWORD,
                wintypes.DWORD,
                wintypes.BOOL,
            ]
            self.GetOverlappedResultEx.restype = wintypes.BOOL


@dataclass(eq=False)
class _WatchResources:
    api: _Win32
    directory_handle: int
    event_handle: int
    buffer: Any
    overlapped: _OVERLAPPED

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._closing = False
        self._close_succeeded = False
        self._close_error: int | None = None
        self._quarantine_claimed = False
        self.closed_event = threading.Event()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._close_succeeded

    @property
    def close_error(self) -> int | None:
        with self._lock:
            return self._close_error

    def close_once(self) -> bool:
        with self._lock:
            if self._close_succeeded or self._closing:
                return False
            self._closing = True
            directory = self.directory_handle
            event = self.event_handle
        close_error: int | None = None
        if directory not in (0, _INVALID_HANDLE_VALUE):
            try:
                closed = self.api.CloseHandle(directory)
            except BaseException:
                closed = False
            if closed:
                with self._lock:
                    if self.directory_handle == directory:
                        self.directory_handle = 0
            else:
                close_error = ctypes.get_last_error()
        if event not in (0, _INVALID_HANDLE_VALUE):
            try:
                closed = self.api.CloseHandle(event)
            except BaseException:
                closed = False
            if closed:
                with self._lock:
                    if self.event_handle == event:
                        self.event_handle = 0
            elif close_error is None:
                close_error = ctypes.get_last_error()
        with self._lock:
            succeeded = self.directory_handle == 0 and self.event_handle == 0
            self._close_succeeded = succeeded
            self._close_error = close_error
            self._closing = False
        if succeeded:
            self.closed_event.set()
        return True

    def claim_quarantine(self) -> bool:
        with self._lock:
            if self._quarantine_claimed:
                return False
            self._quarantine_claimed = True
            return True


_QUARANTINE_LOCK = threading.Lock()
_QUARANTINED: set[_WatchResources] = set()


def _strict_local_directory_path(value: os.PathLike[str] | str) -> str:
    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise P0WindowsDirectoryChangeWatchError(
            "watch path must be one nonempty Windows path string"
        )
    lexical = raw.replace("/", "\\")
    if lexical.startswith("\\\\") or _LOCAL_DOS_PATH.match(lexical) is None:
        raise P0WindowsDirectoryChangeWatchError(
            "watch path must be one absolute local DOS path"
        )
    if len(lexical) > 3 and lexical.endswith("\\"):
        lexical = lexical.rstrip("\\")
    parts = lexical[3:].split("\\") if len(lexical) > 3 else []
    if any(
        not part
        or part in {".", ".."}
        or ":" in part
        or part.endswith((" ", "."))
        for part in parts
    ):
        raise P0WindowsDirectoryChangeWatchError(
            "watch path contains an unsafe lexical component"
        )
    if ntpath.normpath(lexical).casefold() != lexical.casefold():
        raise P0WindowsDirectoryChangeWatchError(
            "watch path must already be lexically normalized"
        )
    return lexical


def _validate_options(
    *, watch_subtree: bool, notify_filter: int, cleanup_timeout_ms: int
) -> None:
    if type(watch_subtree) is not bool:
        raise P0WindowsDirectoryChangeWatchError("watch_subtree must be bool")
    if (
        isinstance(notify_filter, bool)
        or not isinstance(notify_filter, int)
        or notify_filter <= 0
        or notify_filter & ~DEFAULT_NOTIFY_FILTER
    ):
        raise P0WindowsDirectoryChangeWatchError(
            "notify_filter contains unsupported flags"
        )
    if (
        isinstance(cleanup_timeout_ms, bool)
        or not isinstance(cleanup_timeout_ms, int)
        or not 1 <= cleanup_timeout_ms <= MAX_CLEANUP_TIMEOUT_MS
    ):
        raise P0WindowsDirectoryChangeWatchError(
            f"cleanup_timeout_ms must be within 1..{MAX_CLEANUP_TIMEOUT_MS}"
        )


def _winerror(label: str) -> P0WindowsDirectoryChangeWatchError:
    return P0WindowsDirectoryChangeWatchError(
        f"{label} failed with Windows error {ctypes.get_last_error()}"
    )


def _query_struct(
    api: _Win32, handle: int, info_class: int, value: Any, label: str
) -> Any:
    if not api.GetFileInformationByHandleEx(
        handle, info_class, ctypes.byref(value), ctypes.sizeof(value)
    ):
        raise _winerror(label)
    return value


def _query_identity(api: _Win32, handle: int) -> WindowsDirectoryIdentity:
    file_id = _query_struct(
        api, handle, _FILE_ID_INFO_CLASS, _FILE_ID_INFO(), "query directory file ID"
    )
    standard = _query_struct(
        api,
        handle,
        _FILE_STANDARD_INFO_CLASS,
        _FILE_STANDARD_INFO(),
        "query directory standard information",
    )
    tag = _query_struct(
        api,
        handle,
        _FILE_ATTRIBUTE_TAG_INFO_CLASS,
        _FILE_ATTRIBUTE_TAG_INFO(),
        "query directory reparse information",
    )
    if not standard.Directory or standard.DeletePending:
        raise P0WindowsDirectoryChangeWatchError(
            "watched object must be one non-delete-pending directory"
        )
    if tag.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT or tag.ReparseTag:
        raise P0WindowsDirectoryChangeWatchError(
            "watched directory must not be a reparse point"
        )

    size = 1024
    while size <= _MAX_FINAL_PATH_CHARS:
        buffer = ctypes.create_unicode_buffer(size)
        used = api.GetFinalPathNameByHandleW(
            handle,
            buffer,
            size,
            _FILE_NAME_NORMALIZED | _VOLUME_NAME_GUID,
        )
        if used == 0:
            raise _winerror("GetFinalPathNameByHandleW")
        if used < size:
            final_path = buffer.value.rstrip("\\")
            if _VOLUME_GUID_PATH.fullmatch(final_path) is None:
                raise P0WindowsDirectoryChangeWatchError(
                    "watched directory final path is not a local volume-GUID path"
                )
            return WindowsDirectoryIdentity(
                final_path=final_path,
                volume_serial=int(file_id.VolumeSerialNumber),
                file_id=bytes(file_id.FileId.Identifier).hex(),
            )
        size = int(used) + 1
    raise P0WindowsDirectoryChangeWatchError(
        "watched directory final path exceeds strict limit"
    )


def _handle_is_non_inheritable(api: _Win32, handle: int) -> bool:
    flags = wintypes.DWORD()
    if not api.GetHandleInformation(handle, ctypes.byref(flags)):
        raise _winerror("GetHandleInformation")
    return not bool(flags.value & _HANDLE_FLAG_INHERIT)


def _parse_events(raw: bytes) -> tuple[WindowsDirectoryChangeEvent, ...]:
    events: list[WindowsDirectoryChangeEvent] = []
    offset = 0
    while True:
        if offset + 84 > len(raw):
            raise P0WindowsDirectoryChangeWatchError(
                "malformed extended directory-change event"
            )
        next_offset = int.from_bytes(raw[offset : offset + 4], "little")
        action = int.from_bytes(raw[offset + 4 : offset + 8], "little")
        file_id = raw[offset + 64 : offset + 72].hex()
        parent_file_id = raw[offset + 72 : offset + 80].hex()
        name_length = int.from_bytes(raw[offset + 80 : offset + 84], "little")
        end = offset + 84 + name_length
        if name_length % 2 or end > len(raw):
            raise P0WindowsDirectoryChangeWatchError(
                "malformed extended directory-change name"
            )
        try:
            name = raw[offset + 84 : end].decode("utf-16-le", errors="strict")
        except UnicodeDecodeError as exc:
            raise P0WindowsDirectoryChangeWatchError(
                "invalid extended directory-change name"
            ) from exc
        events.append(
            WindowsDirectoryChangeEvent(action, name, file_id, parent_file_id)
        )
        if next_offset == 0:
            break
        minimum_next = (84 + name_length + 3) & ~3
        if (
            next_offset < minimum_next
            or next_offset % 4
            or offset + next_offset >= len(raw)
        ):
            raise P0WindowsDirectoryChangeWatchError(
                "malformed extended directory-change offset"
            )
        offset += next_offset
    return tuple(events)


def _completion_for(resources: _WatchResources, timeout_ms: int) -> _Completion:
    wait = resources.api.WaitForSingleObject(
        resources.event_handle, timeout_ms
    )
    if wait == _WAIT_TIMEOUT:
        return _Completion(
            "CLEANUP_TIMEOUT",
            error_stage="completion_wait",
            winerror=_WAIT_TIMEOUT,
        )
    if wait != _WAIT_OBJECT_0:
        return _Completion(
            "CLEANUP_TIMEOUT",
            error_stage="WaitForSingleObject",
            winerror=ctypes.get_last_error(),
        )
    transferred = wintypes.DWORD()
    ok = resources.api.GetOverlappedResultEx(
        resources.directory_handle,
        ctypes.byref(resources.overlapped),
        ctypes.byref(transferred),
        timeout_ms,
        False,
    )
    if ok:
        if transferred.value == 0:
            return _Completion("OVERFLOW", overflow=True, terminal_observed=True)
        try:
            events = _parse_events(resources.buffer.raw[: transferred.value])
        except P0WindowsDirectoryChangeWatchError:
            return _Completion(
                "ERROR", error_stage="parse_events", terminal_observed=True
            )
        if not events:
            return _Completion(
                "ERROR", error_stage="empty_event_batch", terminal_observed=True
            )
        return _Completion("DELIVERED", events=events, terminal_observed=True)
    error = ctypes.get_last_error()
    if error == _ERROR_OPERATION_ABORTED:
        return _Completion(
            "CANCELED_PENDING_AT_END", terminal_observed=True
        )
    if error in {_WAIT_TIMEOUT, _ERROR_IO_INCOMPLETE}:
        return _Completion("CLEANUP_TIMEOUT", error_stage="completion_wait", winerror=error)
    # The event belongs exclusively to this one issued request.  Once it is
    # signaled, an operation-specific failure is terminal even though it makes
    # the observation unacceptable.
    return _Completion(
        "ERROR",
        error_stage="GetOverlappedResultEx",
        winerror=error,
        terminal_observed=True,
    )


def _start_quarantine_reaper(
    resources: _WatchResources, *, terminal_observed: bool = False
) -> None:
    if not resources.claim_quarantine():
        return
    with _QUARANTINE_LOCK:
        _QUARANTINED.add(resources)

    def reap() -> None:
        completion = _Completion(
            "TERMINAL_RETAINED" if terminal_observed else "CLEANUP_TIMEOUT",
            terminal_observed=terminal_observed,
        )
        while not resources.closed:
            try:
                if not completion.terminal_observed:
                    resources.api.CancelIoEx(
                        resources.directory_handle,
                        ctypes.byref(resources.overlapped),
                    )
                    completion = _completion_for(resources, 1_000)
                    if not completion.terminal_observed:
                        time.sleep(0.05)
                        continue
                resources.close_once()
                if not resources.closed:
                    time.sleep(0.05)
            except BaseException:
                # Strong retention in _QUARANTINED preserves the OVERLAPPED
                # and buffer.  Retry with backoff instead of releasing them.
                time.sleep(0.1)
        with _QUARANTINE_LOCK:
            if resources.closed:
                _QUARANTINED.discard(resources)

    try:
        threading.Thread(
            target=reap,
            name="p0-directory-watch-reaper",
            daemon=True,
        ).start()
    except BaseException:
        # Strong retention in _QUARANTINED is safer than freeing live I/O.
        return


def _abandon_resources(
    resources: _WatchResources, cleanup_timeout_ms: int
) -> None:
    """Preserve and drain issued I/O when a caller abandons the watcher."""

    if resources.closed:
        return
    try:
        resources.api.CancelIoEx(
            resources.directory_handle, ctypes.byref(resources.overlapped)
        )
        completion = _completion_for(resources, cleanup_timeout_ms)
    except BaseException:
        _start_quarantine_reaper(resources)
        return
    if not completion.terminal_observed:
        _start_quarantine_reaper(resources)
    else:
        resources.close_once()
        if not resources.closed:
            _start_quarantine_reaper(resources, terminal_observed=True)


class WindowsDirectoryChangeWatch:
    """One outstanding, parent-configured Windows directory watch."""

    def __init__(self) -> None:
        raise TypeError("use WindowsDirectoryChangeWatch.start(...) instead")

    @classmethod
    def start(
        cls,
        root: os.PathLike[str] | str,
        *,
        watch_subtree: bool,
        notify_filter: int,
        cleanup_timeout_ms: int = DEFAULT_CLEANUP_TIMEOUT_MS,
    ) -> "WindowsDirectoryChangeWatch":
        _validate_options(
            watch_subtree=watch_subtree,
            notify_filter=notify_filter,
            cleanup_timeout_ms=cleanup_timeout_ms,
        )
        requested_path = _strict_local_directory_path(root)
        api = _Win32()
        if api.ReadDirectoryChangesExW is None or api.GetOverlappedResultEx is None:
            raise P0WindowsDirectoryChangeWatchError(
                "required bounded Windows directory-change APIs are unavailable"
            )

        directory_handle = api.CreateFileW(
            requested_path,
            _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS
            | _FILE_FLAG_OPEN_REPARSE_POINT
            | _FILE_FLAG_OVERLAPPED,
            None,
        )
        if directory_handle == _INVALID_HANDLE_VALUE:
            raise _winerror("CreateFileW(watched directory)")

        event_handle = 0
        resources: _WatchResources | None = None
        request_issued = False
        try:
            identity = _query_identity(api, int(directory_handle))
            event_handle = api.CreateEventW(None, True, False, None)
            if not event_handle:
                raise _winerror("CreateEventW(directory watch)")
            buffer = ctypes.create_string_buffer(_WATCH_BUFFER_BYTES)
            overlapped = _OVERLAPPED()
            overlapped.hEvent = event_handle
            resources = _WatchResources(
                api,
                int(directory_handle),
                int(event_handle),
                buffer,
                overlapped,
            )
            non_inheritable = _handle_is_non_inheritable(
                api, int(directory_handle)
            ) and _handle_is_non_inheritable(api, int(event_handle))
            if not non_inheritable:
                raise P0WindowsDirectoryChangeWatchError(
                    "directory watch handles must not be inheritable"
                )
            ok = api.ReadDirectoryChangesExW(
                directory_handle,
                buffer,
                len(buffer),
                watch_subtree,
                notify_filter,
                None,
                ctypes.byref(overlapped),
                None,
                _READ_DIRECTORY_NOTIFY_EXTENDED_INFORMATION,
            )
            error = 0 if ok else ctypes.get_last_error()
            if not ok and error != _ERROR_IO_PENDING:
                raise P0WindowsDirectoryChangeWatchError(
                    f"ReadDirectoryChangesExW failed with Windows error {error}"
                )
            request_issued = True

            self = object.__new__(cls)
            self._lock = threading.RLock()
            self._resources = resources
            self._requested_path = requested_path
            self._identity = identity
            self._watch_subtree = watch_subtree
            self._notify_filter = notify_filter
            self._cleanup_timeout_ms = cleanup_timeout_ms
            self._armed_counter_ns = time.perf_counter_ns()
            self._terminal_completion: _Completion | None = None
            self._outcome: WindowsDirectoryChangeWatchOutcome | None = None
            self._non_inheritable = non_inheritable
            self._abandon_finalizer = weakref.finalize(
                self,
                _abandon_resources,
                resources,
                cleanup_timeout_ms,
            )
            return self
        except BaseException:
            if resources is None:
                if event_handle not in (0, _INVALID_HANDLE_VALUE):
                    api.CloseHandle(event_handle)
                api.CloseHandle(directory_handle)
            elif request_issued:
                _abandon_resources(resources, cleanup_timeout_ms)
            else:
                resources.close_once()
            raise

    @property
    def identity(self) -> WindowsDirectoryIdentity:
        return self._identity

    @property
    def requested_path(self) -> str:
        return self._requested_path

    def _poll_locked(self) -> _Completion:
        if self._terminal_completion is not None:
            return self._terminal_completion
        wait = self._resources.api.WaitForSingleObject(
            self._resources.event_handle, 0
        )
        if wait == _WAIT_TIMEOUT:
            return _Completion("PENDING")
        if wait != _WAIT_OBJECT_0:
            self._terminal_completion = _Completion(
                "POLL_ERROR",
                error_stage="WaitForSingleObject",
                winerror=ctypes.get_last_error(),
            )
            return self._terminal_completion
        completion = _completion_for(self._resources, 0)
        if completion.status == "CLEANUP_TIMEOUT":
            completion = _Completion(
                "POLL_ERROR",
                error_stage="signaled_completion_not_ready",
                winerror=completion.winerror,
            )
        self._terminal_completion = completion
        return completion

    def barrier(self) -> WindowsDirectoryChangeBarrier:
        """Poll without canceling; only ``PENDING`` is acceptable."""

        with self._lock:
            if self._outcome is not None:
                return WindowsDirectoryChangeBarrier(
                    time.perf_counter_ns(),
                    self._outcome.completion_status,
                    False,
                    True,
                    False,
                )
            completion = self._poll_locked()
            pending = completion.status == "PENDING"
            return WindowsDirectoryChangeBarrier(
                counter_ns=time.perf_counter_ns(),
                completion_status=completion.status,
                request_pending_observed=pending,
                completion_observed=not pending,
                observation_acceptable=pending,
            )

    def _build_outcome(
        self,
        *,
        interval_end: int,
        completion: _Completion,
        interval_end_status: str,
        cleanup_completion_status: str,
        interval_error_stage: str | None,
        interval_winerror: int | None,
        pending_at_end: bool,
        drained: bool,
        handles_closed: bool,
        quarantined: bool,
        cancel_error: int | None,
    ) -> WindowsDirectoryChangeWatchOutcome:
        delivered = completion.status == "DELIVERED"
        overflow = completion.status == "OVERFLOW" or completion.overflow
        error_stage = interval_error_stage or completion.error_stage
        winerror = (
            interval_winerror
            if interval_winerror is not None
            else completion.winerror
        )
        if cancel_error is not None:
            error_stage = error_stage or "CancelIoEx"
            winerror = winerror if winerror is not None else cancel_error
        if not handles_closed:
            error_stage = error_stage or "CloseHandle"
            winerror = (
                winerror
                if winerror is not None
                else self._resources.close_error
            )
        gap = bool(
            completion.status != "CANCELED_PENDING_AT_END"
            or interval_end_status != "PENDING"
            or not pending_at_end
            or not drained
            or not handles_closed
            or quarantined
            or cancel_error is not None
        )
        verified = bool(
            pending_at_end
            and interval_end_status == "PENDING"
            and completion.status == "CANCELED_PENDING_AT_END"
            and drained
            and handles_closed
            and not quarantined
            and cancel_error is None
            and not completion.events
            and not overflow
        )
        return WindowsDirectoryChangeWatchOutcome(
            schema_version=WATCH_OUTCOME_SCHEMA,
            requested_path=self._requested_path,
            identity=self._identity,
            watch_subtree=self._watch_subtree,
            notify_filter=self._notify_filter,
            api_available=True,
            armed=True,
            armed_counter_ns=self._armed_counter_ns,
            interval_end_counter_ns=interval_end,
            interval_end_poll_status=interval_end_status,
            cleanup_completion_status=cleanup_completion_status,
            completion_status=completion.status,
            events=completion.events,
            directory_change_notification_delivered_observed=delivered,
            overflow_observed=overflow,
            observation_gap_observed=gap,
            pending_request_until_interval_end_observed=pending_at_end,
            completion_drained_observed=drained,
            watch_handles_non_inheritable_verified=self._non_inheritable,
            watch_handles_closed_observed=handles_closed,
            quarantined_cleanup_observed=quarantined,
            project_source_directory_change_watch_observation_verified=verified,
            error_stage=error_stage,
            winerror=winerror,
        )

    def finalize(self) -> WindowsDirectoryChangeWatchOutcome:
        """End the interval, cancel/drain if pending, and close exactly once."""

        with self._lock:
            if self._outcome is not None:
                return self._outcome
            interval_end = time.perf_counter_ns()
            interval_completion = self._poll_locked()
            interval_end_status = interval_completion.status
            interval_error_stage = interval_completion.error_stage
            interval_winerror = interval_completion.winerror
            completion = interval_completion
            pending_at_end = interval_end_status == "PENDING"
            cancel_error: int | None = None
            cleanup_uncertain = interval_end_status in {"PENDING", "POLL_ERROR"}
            drained = interval_completion.terminal_observed
            quarantined = False
            cleanup_completion_status = interval_end_status

            if cleanup_uncertain:
                try:
                    cancelled = self._resources.api.CancelIoEx(
                        self._resources.directory_handle,
                        ctypes.byref(self._resources.overlapped),
                    )
                    if not cancelled:
                        cancel_error = ctypes.get_last_error()
                    cleanup_completion = _completion_for(
                        self._resources, self._cleanup_timeout_ms
                    )
                except BaseException:
                    cleanup_completion = _Completion(
                        "CLEANUP_TIMEOUT",
                        error_stage="cleanup_exception",
                    )
                cleanup_completion_status = cleanup_completion.status
                drained = cleanup_completion.terminal_observed
                completion = cleanup_completion

            if not completion.terminal_observed:
                quarantined = True
                _start_quarantine_reaper(self._resources)
                handles_closed = False
                self._abandon_finalizer.detach()
            else:
                self._resources.close_once()
                handles_closed = self._resources.closed
                if not handles_closed:
                    quarantined = True
                    _start_quarantine_reaper(
                        self._resources, terminal_observed=True
                    )
                self._abandon_finalizer.detach()

            self._terminal_completion = completion
            self._outcome = self._build_outcome(
                interval_end=interval_end,
                completion=completion,
                interval_end_status=interval_end_status,
                cleanup_completion_status=cleanup_completion_status,
                interval_error_stage=interval_error_stage,
                interval_winerror=interval_winerror,
                pending_at_end=pending_at_end,
                drained=drained,
                handles_closed=handles_closed,
                quarantined=quarantined,
                cancel_error=cancel_error,
            )
            return self._outcome

    close = finalize

    def __enter__(self) -> "WindowsDirectoryChangeWatch":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.finalize()


__all__ = [
    "DEFAULT_CLEANUP_TIMEOUT_MS",
    "DEFAULT_NOTIFY_FILTER",
    "FILE_NOTIFY_CHANGE_ATTRIBUTES",
    "FILE_NOTIFY_CHANGE_CREATION",
    "FILE_NOTIFY_CHANGE_DIR_NAME",
    "FILE_NOTIFY_CHANGE_FILE_NAME",
    "FILE_NOTIFY_CHANGE_LAST_ACCESS",
    "FILE_NOTIFY_CHANGE_LAST_WRITE",
    "FILE_NOTIFY_CHANGE_SECURITY",
    "FILE_NOTIFY_CHANGE_SIZE",
    "MAX_CLEANUP_TIMEOUT_MS",
    "P0WindowsDirectoryChangeWatchError",
    "WATCH_OUTCOME_SCHEMA",
    "WindowsDirectoryChangeBarrier",
    "WindowsDirectoryChangeEvent",
    "WindowsDirectoryChangeWatch",
    "WindowsDirectoryChangeWatchOutcome",
    "WindowsDirectoryIdentity",
]
