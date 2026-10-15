"""Fail-closed Windows runtime evidence for the actual-P0 shadow path.

The observer in this module is deliberately a *bounded witness*, not an
authority source.  It uses only the Python standard library and Win32 APIs
loaded through :mod:`ctypes`.  A same-process execution can prove a narrow
PRE/parser/POST observation when every required signal is available.  A
serialized receipt cannot preserve that provenance, so public validation
always downgrades runtime, owner, semantic, P0, and production claims.

The write check is non-mutating: while the callback is impersonating an
actually restricted token, the observer asks Windows to open each protected
directory with child-create/write access.  Only ``ERROR_ACCESS_DENIED`` is a
denial.  No file is created.  ``CreateRestrictedToken`` by itself is not
treated as write denial; ordinary writable directories will therefore fail
closed, as they should.

USN observations are volume-wide journal bounds.  They do not identify which
file changed.  An unchanged protected tree additionally requires an active
``ReadDirectoryChangesExW`` request, no event/overflow/gap, stable root
identity, and equal recursive inventory hashes.
"""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import hmac
import json
import os
import secrets
import stat
import threading
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, TypeVar
import weakref


RUNTIME_EVIDENCE_SCHEMA = "p0_windows_runtime_evidence_v1"
RUNTIME_VALIDATION_RECEIPT_SCHEMA = "p0_windows_runtime_evidence_validation_v1"
REQUIRED_PROTECTED_CATEGORIES = (
    "CENTRAL_SLANG_DB",
    "CHECKPOINT",
    "DECISION_LEDGER",
    "PUBLICATION_JOURNAL",
    "RECOVERY",
    "RESULT",
)

_IS_WINDOWS = os.name == "nt"
_ERROR_ACCESS_DENIED = 5
_ERROR_IO_PENDING = 997
_ERROR_OPERATION_ABORTED = 995
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_GENERIC_READ = 0x80000000
_FILE_LIST_DIRECTORY = 0x0001
_FILE_ADD_FILE = 0x0002
_FILE_ADD_SUBDIRECTORY = 0x0004
_FILE_WRITE_DATA = 0x0002
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_SHARE_READ = 0x1
_FILE_SHARE_WRITE = 0x2
_FILE_SHARE_DELETE = 0x4
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_OVERLAPPED = 0x40000000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400

_FILE_NOTIFY_CHANGE_FILE_NAME = 0x1
_FILE_NOTIFY_CHANGE_DIR_NAME = 0x2
_FILE_NOTIFY_CHANGE_ATTRIBUTES = 0x4
_FILE_NOTIFY_CHANGE_SIZE = 0x8
_FILE_NOTIFY_CHANGE_LAST_WRITE = 0x10
_FILE_NOTIFY_CHANGE_LAST_ACCESS = 0x20
_FILE_NOTIFY_CHANGE_CREATION = 0x40
_FILE_NOTIFY_CHANGE_SECURITY = 0x100
_NOTIFY_FILTER = (
    _FILE_NOTIFY_CHANGE_FILE_NAME
    | _FILE_NOTIFY_CHANGE_DIR_NAME
    | _FILE_NOTIFY_CHANGE_ATTRIBUTES
    | _FILE_NOTIFY_CHANGE_SIZE
    | _FILE_NOTIFY_CHANGE_LAST_WRITE
    | _FILE_NOTIFY_CHANGE_LAST_ACCESS
    | _FILE_NOTIFY_CHANGE_CREATION
    | _FILE_NOTIFY_CHANGE_SECURITY
)
_READ_DIRECTORY_NOTIFY_EXTENDED_INFORMATION = 2
_WATCH_BUFFER_BYTES = 64 * 1024

_FILE_ID_INFO_CLASS = 18
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FSCTL_QUERY_USN_JOURNAL = 0x000900F4
_DISABLE_MAX_PRIVILEGE = 0x1
_TOKEN_DUPLICATE = 0x0002
_TOKEN_IMPERSONATE = 0x0004
_TOKEN_QUERY = 0x0008
_WIN_AUTHENTICATED_USER_SID = 17

_PHASES = (
    "PRE_BEGIN",
    "PRE_COMPLETE",
    "PARSER_BEGIN",
    "PARSER_COMPLETE",
    "POST_BEGIN",
    "POST_COMPLETE",
)

_T = TypeVar("_T")


class P0WindowsRuntimeEvidenceError(ValueError):
    """Raised when evidence is malformed or cannot satisfy the contract."""


class _FILE_ID_128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_ubyte * 16)]


class _FILE_ID_INFO(ctypes.Structure):
    _fields_ = [
        ("VolumeSerialNumber", ctypes.c_ulonglong),
        ("FileId", _FILE_ID_128),
    ]


class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
    _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]


class _OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_size_t),
        ("InternalHigh", ctypes.c_size_t),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


@dataclass(frozen=True)
class _Identity:
    final_path: str
    volume_serial: int
    file_id: str
    reparse_point: bool


@dataclass(frozen=True)
class _Usn:
    available: bool
    volume_guid: str | None
    journal_id: int | None
    first_usn: int | None
    next_usn: int | None
    lowest_valid_usn: int | None
    error_code: int | None


@dataclass(frozen=True)
class _Inventory:
    available: bool
    sha256: str | None
    entry_count: int
    reparse_seen: bool
    error: str | None


@dataclass(frozen=True)
class _WatchOutcome:
    api_available: bool
    armed: bool
    armed_counter: int | None
    stopped_counter: int | None
    continuous: bool
    overflow: bool
    gap: bool
    events: tuple[tuple[int, str], ...]
    error_code: int | None


@dataclass(frozen=True)
class _WriteProbe:
    attempted: bool
    counter: int | None
    desired_access: int
    open_succeeded: bool
    denied: bool
    error_code: int | None


@dataclass(frozen=True)
class _CategoryEvidence:
    category: str
    requested_root: str
    pre_identity: _Identity | None
    post_identity: _Identity | None
    expected_identity_match: bool | None
    pre_usn: _Usn
    post_usn: _Usn
    pre_inventory: _Inventory
    post_inventory: _Inventory
    watch: _WatchOutcome
    parent_namespace_watch: _WatchOutcome
    write_probe: _WriteProbe


@dataclass(frozen=True)
class _RuntimeRawEvidence:
    windows_observer: bool
    qpc_frequency: int | None
    timeline: tuple[tuple[str, int], ...]
    token_created: bool
    token_is_restricted: bool
    impersonation_active_for_operation: bool
    categories: tuple[_CategoryEvidence, ...]
    diagnostic_errors: tuple[str, ...]


@dataclass(frozen=True, eq=False)
class _RuntimeExecutionState:
    """Private immutable result retained by a same-process supervisor."""

    raw_evidence: _RuntimeRawEvidence
    operation_result: Any
    operation_exception: BaseException | None
    operation_traceback: Any
    bounded_runtime_noninterference_verified: bool
    detached_receipt: Mapping[str, Any]
    _execution_seal: bytes


_ISSUED_EXECUTION_STATES: weakref.WeakKeyDictionary[
    _RuntimeExecutionState, bytes
] = weakref.WeakKeyDictionary()
_ISSUED_EXECUTION_STATES_LOCK = threading.Lock()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _with_hash(material: Mapping[str, Any], field: str) -> dict[str, Any]:
    result = dict(material)
    result[field] = _canonical_sha256(material)
    return result


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _issue_execution_state(
    raw: _RuntimeRawEvidence,
    result: Any,
    error: BaseException | None,
    traceback: Any,
    bounded: bool,
) -> _RuntimeExecutionState:
    detached = _freeze_json(_receipt(raw, bounded, error))
    seal = secrets.token_bytes(32)
    state = _RuntimeExecutionState(
        raw,
        result,
        error,
        traceback,
        bounded,
        detached,
        seal,
    )
    with _ISSUED_EXECUTION_STATES_LOCK:
        _ISSUED_EXECUTION_STATES[state] = seal
    return state


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:1000]


def _normalise_roots(protected_roots: Mapping[str, os.PathLike[str] | str]) -> tuple[tuple[str, str], ...]:
    if not isinstance(protected_roots, Mapping):
        raise P0WindowsRuntimeEvidenceError("protected_roots must be a mapping")
    if tuple(protected_roots.keys()) != REQUIRED_PROTECTED_CATEGORIES:
        raise P0WindowsRuntimeEvidenceError(
            "protected_roots must contain the exact ordered six-category map"
        )
    values: list[tuple[str, str]] = []
    folded: list[str] = []
    for category in REQUIRED_PROTECTED_CATEGORIES:
        raw = os.fspath(protected_roots[category])
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise P0WindowsRuntimeEvidenceError(f"{category} root is invalid")
        absolute = os.path.abspath(raw)
        if not os.path.isabs(absolute):
            raise P0WindowsRuntimeEvidenceError(f"{category} root must be absolute")
        normal = absolute.rstrip("\\/") or absolute
        values.append((category, normal))
        folded.append(normal.replace("/", "\\").rstrip("\\").casefold())
    for index, left in enumerate(folded):
        for right in folded[index + 1 :]:
            if left == right or left.startswith(right + "\\") or right.startswith(left + "\\"):
                raise P0WindowsRuntimeEvidenceError(
                    "protected category roots must be unique and non-overlapping"
                )
    return tuple(values)


def _expected_for(
    expected_identities: Mapping[str, Mapping[str, Any]] | None,
    category: str,
    identity: _Identity | None,
) -> bool | None:
    if expected_identities is None:
        return None
    if tuple(expected_identities.keys()) != REQUIRED_PROTECTED_CATEGORIES:
        raise P0WindowsRuntimeEvidenceError(
            "expected_identities must contain the exact ordered six-category map"
        )
    expected = expected_identities[category]
    if not isinstance(expected, Mapping) or set(expected) != {
        "final_path",
        "volume_serial",
        "file_id",
    }:
        raise P0WindowsRuntimeEvidenceError("expected identity shape is invalid")
    if identity is None:
        return False
    return (
        str(expected["final_path"]).rstrip("\\").casefold()
        == identity.final_path.rstrip("\\").casefold()
        and type(expected["volume_serial"]) is int
        and expected["volume_serial"] == identity.volume_serial
        and isinstance(expected["file_id"], str)
        and expected["file_id"] == identity.file_id
    )


class _Win32:
    def __init__(self) -> None:
        if not _IS_WINDOWS:
            raise OSError("Win32 runtime observer is unavailable")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

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
        self.QueryPerformanceCounter = kernel32.QueryPerformanceCounter
        self.QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
        self.QueryPerformanceCounter.restype = wintypes.BOOL
        self.QueryPerformanceFrequency = kernel32.QueryPerformanceFrequency
        self.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
        self.QueryPerformanceFrequency.restype = wintypes.BOOL
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
        self.GetVolumePathNameW = kernel32.GetVolumePathNameW
        self.GetVolumeNameForVolumeMountPointW = kernel32.GetVolumeNameForVolumeMountPointW
        self.DeviceIoControl = kernel32.DeviceIoControl
        self.DeviceIoControl.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self.DeviceIoControl.restype = wintypes.BOOL
        self.CreateEventW = kernel32.CreateEventW
        self.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self.CreateEventW.restype = wintypes.HANDLE
        self.WaitForSingleObject = kernel32.WaitForSingleObject
        self.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.WaitForSingleObject.restype = wintypes.DWORD
        self.CancelIoEx = kernel32.CancelIoEx
        self.GetOverlappedResult = kernel32.GetOverlappedResult
        self.GetOverlappedResult.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_OVERLAPPED),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.BOOL,
        ]
        self.GetOverlappedResult.restype = wintypes.BOOL
        self.ReadDirectoryChangesExW = getattr(kernel32, "ReadDirectoryChangesExW", None)
        if self.ReadDirectoryChangesExW is not None:
            self.ReadDirectoryChangesExW.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(_OVERLAPPED),
                wintypes.LPVOID,
                ctypes.c_int,
            ]
            self.ReadDirectoryChangesExW.restype = wintypes.BOOL

        self.GetCurrentProcess = kernel32.GetCurrentProcess
        self.OpenProcessToken = advapi32.OpenProcessToken
        self.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        self.OpenProcessToken.restype = wintypes.BOOL
        self.CreateRestrictedToken = advapi32.CreateRestrictedToken
        self.CreateRestrictedToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(_SID_AND_ATTRIBUTES),
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(_SID_AND_ATTRIBUTES),
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self.CreateRestrictedToken.restype = wintypes.BOOL
        self.CreateWellKnownSid = advapi32.CreateWellKnownSid
        self.CreateWellKnownSid.argtypes = [
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.CreateWellKnownSid.restype = wintypes.BOOL
        self.IsTokenRestricted = advapi32.IsTokenRestricted
        self.IsTokenRestricted.argtypes = [wintypes.HANDLE]
        self.IsTokenRestricted.restype = wintypes.BOOL
        self.ImpersonateLoggedOnUser = advapi32.ImpersonateLoggedOnUser
        self.ImpersonateLoggedOnUser.argtypes = [wintypes.HANDLE]
        self.ImpersonateLoggedOnUser.restype = wintypes.BOOL
        self.RevertToSelf = advapi32.RevertToSelf
        self.RevertToSelf.restype = wintypes.BOOL
        self.SetThreadToken = advapi32.SetThreadToken
        self.SetThreadToken.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.HANDLE,
        ]
        self.SetThreadToken.restype = wintypes.BOOL

    def qpc(self) -> int:
        value = ctypes.c_longlong()
        if not self.QueryPerformanceCounter(ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(value.value)

    def frequency(self) -> int:
        value = ctypes.c_longlong()
        if not self.QueryPerformanceFrequency(ctypes.byref(value)) or value.value <= 0:
            raise ctypes.WinError(ctypes.get_last_error())
        return int(value.value)


def _close(api: _Win32, handle: Any) -> None:
    if handle not in (None, 0, _INVALID_HANDLE_VALUE):
        api.CloseHandle(handle)


def _open_directory(api: _Win32, root: str, *, watch: bool = False, desired: int | None = None) -> Any:
    access = _FILE_READ_ATTRIBUTES | (_FILE_LIST_DIRECTORY if watch else 0)
    if desired is not None:
        access = desired
    flags = _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT
    if watch:
        flags |= _FILE_FLAG_OVERLAPPED
    return api.CreateFileW(
        root,
        access,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
        None,
        _OPEN_EXISTING,
        flags,
        None,
    )


def _identity_from_handle(api: _Win32, handle: Any) -> _Identity:
    file_id = _FILE_ID_INFO()
    if not api.GetFileInformationByHandleEx(
        handle, _FILE_ID_INFO_CLASS, ctypes.byref(file_id), ctypes.sizeof(file_id)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    tag = _FILE_ATTRIBUTE_TAG_INFO()
    if not api.GetFileInformationByHandleEx(
        handle,
        _FILE_ATTRIBUTE_TAG_INFO_CLASS,
        ctypes.byref(tag),
        ctypes.sizeof(tag),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    size = 32768
    buffer = ctypes.create_unicode_buffer(size)
    used = api.GetFinalPathNameByHandleW(handle, buffer, size, 0)
    if not used or used >= size:
        raise ctypes.WinError(ctypes.get_last_error())
    return _Identity(
        final_path=buffer.value.rstrip("\\"),
        volume_serial=int(file_id.VolumeSerialNumber),
        file_id=bytes(file_id.FileId.Identifier).hex(),
        reparse_point=bool(
            tag.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT or tag.ReparseTag
        ),
    )


def _identity(api: _Win32, root: str) -> _Identity:
    handle = _open_directory(api, root)
    if handle == _INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return _identity_from_handle(api, handle)
    finally:
        _close(api, handle)


def _inventory(root: str) -> _Inventory:
    try:
        pending = [(root, "")]
        entries: list[dict[str, Any]] = []
        reparse = False
        while pending:
            directory, prefix = pending.pop()
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda value: value.name.casefold())
            for child in children:
                relative = f"{prefix}/{child.name}" if prefix else child.name
                info = child.stat(follow_symlinks=False)
                is_reparse = bool(getattr(info, "st_file_attributes", 0) & _FILE_ATTRIBUTE_REPARSE_POINT)
                reparse = reparse or is_reparse or child.is_symlink()
                entries.append(
                    {
                        "path": relative.replace("\\", "/"),
                        "mode": stat.S_IFMT(info.st_mode),
                        "size": int(info.st_size),
                        "mtime_ns": int(info.st_mtime_ns),
                        "ctime_ns": int(info.st_ctime_ns),
                        "file_id": int(info.st_ino),
                        "reparse": is_reparse,
                    }
                )
                if child.is_dir(follow_symlinks=False) and not is_reparse:
                    pending.append((child.path, relative))
        entries.sort(key=lambda value: value["path"].casefold())
        return _Inventory(True, _canonical_sha256(entries), len(entries), reparse, None)
    except BaseException as exc:
        return _Inventory(False, None, 0, False, _safe_error(exc))


def _unavailable_usn(error: int | None = None) -> _Usn:
    return _Usn(False, None, None, None, None, None, error)


def _query_usn(api: _Win32, root: str) -> _Usn:
    mount = ctypes.create_unicode_buffer(32768)
    if not api.GetVolumePathNameW(root, mount, len(mount)):
        return _unavailable_usn(ctypes.get_last_error())
    guid = ctypes.create_unicode_buffer(128)
    if not api.GetVolumeNameForVolumeMountPointW(mount.value, guid, len(guid)):
        return _unavailable_usn(ctypes.get_last_error())
    volume_guid = guid.value.rstrip("\\")
    handle = api.CreateFileW(
        volume_guid,
        _GENERIC_READ,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
        None,
        _OPEN_EXISTING,
        0,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        return _unavailable_usn(ctypes.get_last_error())
    try:
        output = ctypes.create_string_buffer(80)
        returned = wintypes.DWORD()
        if not api.DeviceIoControl(
            handle,
            _FSCTL_QUERY_USN_JOURNAL,
            None,
            0,
            output,
            len(output),
            ctypes.byref(returned),
            None,
        ):
            return _unavailable_usn(ctypes.get_last_error())
        if returned.value < 40:
            return _unavailable_usn(None)
        journal_id = int.from_bytes(output.raw[0:8], "little", signed=False)
        first = int.from_bytes(output.raw[8:16], "little", signed=True)
        next_usn = int.from_bytes(output.raw[16:24], "little", signed=True)
        lowest = int.from_bytes(output.raw[24:32], "little", signed=True)
        return _Usn(True, volume_guid, journal_id, first, next_usn, lowest, None)
    finally:
        _close(api, handle)


class _Watcher:
    def __init__(self, api: _Win32, root: str, *, watch_subtree: bool = True) -> None:
        self.api = api
        self.root = root
        self.watch_subtree = watch_subtree
        self.handle: Any = None
        self.event: Any = None
        self.buffer = ctypes.create_string_buffer(_WATCH_BUFFER_BYTES)
        self.overlapped = _OVERLAPPED()
        self.api_available = api.ReadDirectoryChangesExW is not None
        self.armed = False
        self.armed_counter: int | None = None
        self.error_code: int | None = None

    def start(self) -> None:
        if not self.api_available:
            return
        self.handle = _open_directory(self.api, self.root, watch=True)
        if self.handle == _INVALID_HANDLE_VALUE:
            self.error_code = ctypes.get_last_error()
            return
        self.event = self.api.CreateEventW(None, True, False, None)
        if not self.event:
            self.error_code = ctypes.get_last_error()
            return
        self.overlapped.hEvent = self.event
        returned = wintypes.DWORD()
        ok = self.api.ReadDirectoryChangesExW(
            self.handle,
            self.buffer,
            len(self.buffer),
            self.watch_subtree,
            _NOTIFY_FILTER,
            ctypes.byref(returned),
            ctypes.byref(self.overlapped),
            None,
            _READ_DIRECTORY_NOTIFY_EXTENDED_INFORMATION,
        )
        error = 0 if ok else ctypes.get_last_error()
        if not ok and error != _ERROR_IO_PENDING:
            self.error_code = error
            return
        self.armed_counter = self.api.qpc()
        self.armed = True

    def stop(self) -> _WatchOutcome:
        stopped = self.api.qpc()
        events: tuple[tuple[int, str], ...] = ()
        overflow = False
        gap = not self.armed
        continuous = False
        error = self.error_code
        try:
            if not self.armed or not self.event:
                return _WatchOutcome(
                    self.api_available, self.armed, self.armed_counter, stopped,
                    False, False, True, (), error,
                )
            wait = self.api.WaitForSingleObject(self.event, 0)
            completed_before_stop = wait == _WAIT_OBJECT_0
            if wait not in (_WAIT_OBJECT_0, _WAIT_TIMEOUT):
                error = int(wait)
                gap = True
            if not completed_before_stop:
                self.api.CancelIoEx(self.handle, ctypes.byref(self.overlapped))
            returned = wintypes.DWORD()
            ok = self.api.GetOverlappedResult(
                self.handle, ctypes.byref(self.overlapped), ctypes.byref(returned), True
            )
            if completed_before_stop:
                if not ok:
                    error = ctypes.get_last_error()
                    gap = True
                elif returned.value == 0:
                    overflow = True
                    gap = True
                else:
                    events = _parse_extended_events(self.buffer.raw[: returned.value])
                    # The one pending request completed at the first batch.  It
                    # proves a change but cannot prove continuity afterwards.
                    gap = True
            else:
                if ok or ctypes.get_last_error() != _ERROR_OPERATION_ABORTED:
                    error = 0 if ok else ctypes.get_last_error()
                    gap = True
                else:
                    continuous = not gap
            if events or overflow:
                continuous = False
            return _WatchOutcome(
                self.api_available,
                self.armed,
                self.armed_counter,
                stopped,
                continuous,
                overflow,
                gap,
                events,
                error,
            )
        finally:
            _close(self.api, self.event)
            _close(self.api, self.handle)


def _parse_extended_events(raw: bytes) -> tuple[tuple[int, str], ...]:
    events: list[tuple[int, str]] = []
    offset = 0
    while True:
        if offset + 84 > len(raw):
            raise P0WindowsRuntimeEvidenceError("malformed extended watch event")
        next_offset = int.from_bytes(raw[offset : offset + 4], "little")
        action = int.from_bytes(raw[offset + 4 : offset + 8], "little")
        name_length = int.from_bytes(raw[offset + 80 : offset + 84], "little")
        end = offset + 84 + name_length
        if name_length % 2 or end > len(raw):
            raise P0WindowsRuntimeEvidenceError("malformed extended watch name")
        name = raw[offset + 84 : end].decode("utf-16-le", errors="strict")
        events.append((action, name))
        if next_offset == 0:
            break
        if next_offset < 84 or next_offset % 4 or offset + next_offset >= len(raw):
            raise P0WindowsRuntimeEvidenceError("malformed extended watch offset")
        offset += next_offset
    return tuple(events)


def _create_restricted_token(api: _Win32) -> tuple[Any, bool, str | None]:
    process_token = wintypes.HANDLE()
    restricted = wintypes.HANDLE()
    access = _TOKEN_DUPLICATE | _TOKEN_IMPERSONATE | _TOKEN_QUERY
    if not api.OpenProcessToken(api.GetCurrentProcess(), access, ctypes.byref(process_token)):
        return None, False, f"OpenProcessToken:{ctypes.get_last_error()}"
    try:
        sid_buffer = ctypes.create_string_buffer(68)
        sid_size = wintypes.DWORD(len(sid_buffer))
        if not api.CreateWellKnownSid(
            _WIN_AUTHENTICATED_USER_SID,
            None,
            sid_buffer,
            ctypes.byref(sid_size),
        ):
            return None, False, f"CreateWellKnownSid:{ctypes.get_last_error()}"
        restricting = _SID_AND_ATTRIBUTES(
            ctypes.cast(sid_buffer, ctypes.c_void_p), 0
        )
        if not api.CreateRestrictedToken(
            process_token,
            _DISABLE_MAX_PRIVILEGE,
            0,
            None,
            0,
            None,
            1,
            ctypes.byref(restricting),
            ctypes.byref(restricted),
        ):
            return None, False, f"CreateRestrictedToken:{ctypes.get_last_error()}"
        is_restricted = bool(api.IsTokenRestricted(restricted))
        return restricted.value, is_restricted, None
    finally:
        _close(api, process_token.value)


def _probe_write(api: _Win32, root: str) -> _WriteProbe:
    counter = api.qpc()
    desired = _FILE_ADD_FILE | _FILE_ADD_SUBDIRECTORY | _FILE_WRITE_DATA
    handle = _open_directory(api, root, desired=desired)
    if handle != _INVALID_HANDLE_VALUE:
        _close(api, handle)
        return _WriteProbe(True, counter, desired, True, False, None)
    error = ctypes.get_last_error()
    return _WriteProbe(True, counter, desired, False, error == _ERROR_ACCESS_DENIED, error)


def _same_identity(left: _Identity | None, right: _Identity | None) -> bool:
    return left is not None and right is not None and left == right and not left.reparse_point


def _usn_interval(pre: _Usn, post: _Usn) -> bool:
    return bool(
        pre.available
        and post.available
        and pre.volume_guid == post.volume_guid
        and pre.journal_id == post.journal_id
        and type(pre.next_usn) is int
        and type(post.next_usn) is int
        and type(post.first_usn) is int
        and post.first_usn <= pre.next_usn <= post.next_usn
    )


def _watch_ok(value: _WatchOutcome) -> bool:
    return bool(
        value.api_available
        and value.armed
        and value.continuous
        and not value.overflow
        and not value.gap
        and not value.events
    )


def _category_ok(value: _CategoryEvidence) -> bool:
    return bool(
        _same_identity(value.pre_identity, value.post_identity)
        and value.expected_identity_match is not False
        and value.pre_inventory.available
        and value.post_inventory.available
        and not value.pre_inventory.reparse_seen
        and not value.post_inventory.reparse_seen
        and value.pre_inventory.sha256 == value.post_inventory.sha256
        and value.pre_inventory.entry_count == value.post_inventory.entry_count
        and _usn_interval(value.pre_usn, value.post_usn)
        and _watch_ok(value.watch)
        and _watch_ok(value.parent_namespace_watch)
        and value.write_probe.attempted
        and value.write_probe.denied
        and not value.write_probe.open_succeeded
        and value.write_probe.error_code == _ERROR_ACCESS_DENIED
    )


def _identity_dict(value: _Identity | None) -> dict[str, Any] | None:
    return None if value is None else {
        "final_path": value.final_path,
        "volume_serial": value.volume_serial,
        "file_id": value.file_id,
        "reparse_point": value.reparse_point,
    }


def _usn_dict(value: _Usn) -> dict[str, Any]:
    return {
        "available": value.available,
        "volume_guid": value.volume_guid,
        "journal_id": value.journal_id,
        "first_usn": value.first_usn,
        "next_usn": value.next_usn,
        "lowest_valid_usn": value.lowest_valid_usn,
        "error_code": value.error_code,
    }


def _inventory_dict(value: _Inventory) -> dict[str, Any]:
    return {
        "available": value.available,
        "sha256": value.sha256,
        "entry_count": value.entry_count,
        "reparse_seen": value.reparse_seen,
        "error": value.error,
    }


def _category_dict(value: _CategoryEvidence) -> dict[str, Any]:
    def watch_dict(watch: _WatchOutcome, *, scope: str) -> dict[str, Any]:
        return {
            "api": "ReadDirectoryChangesExW",
            "scope": scope,
            "api_available": watch.api_available,
            "armed": watch.armed,
            "armed_counter": watch.armed_counter,
            "stopped_counter": watch.stopped_counter,
            "continuous": watch.continuous,
            "overflow": watch.overflow,
            "gap": watch.gap,
            "events": [
                {"action": action, "relative_path": relative}
                for action, relative in watch.events
            ],
            "error_code": watch.error_code,
        }

    return {
        "category": value.category,
        "requested_root": value.requested_root,
        "pre_identity": _identity_dict(value.pre_identity),
        "post_identity": _identity_dict(value.post_identity),
        "expected_identity_match": value.expected_identity_match,
        "pre_usn": _usn_dict(value.pre_usn),
        "post_usn": _usn_dict(value.post_usn),
        "pre_inventory": _inventory_dict(value.pre_inventory),
        "post_inventory": _inventory_dict(value.post_inventory),
        "watch": watch_dict(value.watch, scope="PROTECTED_ROOT_RECURSIVE"),
        "parent_namespace_watch": watch_dict(
            value.parent_namespace_watch,
            scope="PARENT_DIRECTORY_ROOT_ENTRY_NAMESPACE",
        ),
        "write_open_probe": {
            "scope": "CURRENT_THREAD_RESTRICTED_TOKEN_NON_MUTATING_OPEN_PROBE",
            "attempted": value.write_probe.attempted,
            "counter": value.write_probe.counter,
            "desired_access": value.write_probe.desired_access,
            "open_succeeded": value.write_probe.open_succeeded,
            "denied": value.write_probe.denied,
            "error_code": value.write_probe.error_code,
        },
        "bounded_category_noninterference_verified": _category_ok(value),
    }


def _receipt(raw: _RuntimeRawEvidence, bounded: bool, operation_exception: BaseException | None) -> dict[str, Any]:
    root_identity_and_membership = bool(
        raw.categories
        and all(
            _same_identity(value.pre_identity, value.post_identity)
            and value.expected_identity_match is not False
            and value.pre_inventory.available
            and value.post_inventory.available
            and not value.pre_inventory.reparse_seen
            and not value.post_inventory.reparse_seen
            and value.pre_inventory.sha256 == value.post_inventory.sha256
            and value.pre_inventory.entry_count == value.post_inventory.entry_count
            for value in raw.categories
        )
    )
    continuous_watch = bool(
        raw.categories
        and all(
            _watch_ok(value.watch) and _watch_ok(value.parent_namespace_watch)
            for value in raw.categories
        )
    )
    usn_interval = bool(
        raw.categories and all(_usn_interval(value.pre_usn, value.post_usn) for value in raw.categories)
    )
    current_thread_write_deny = bool(
        raw.token_created
        and raw.token_is_restricted
        and raw.impersonation_active_for_operation
        and raw.categories
        and all(
            value.write_probe.attempted
            and value.write_probe.denied
            and not value.write_probe.open_succeeded
            and value.write_probe.error_code == _ERROR_ACCESS_DENIED
            for value in raw.categories
        )
    )
    material = {
        "schema": RUNTIME_EVIDENCE_SCHEMA,
        "platform": "windows" if raw.windows_observer else os.name,
        "observer": "stdlib-ctypes-win32-v1",
        "required_categories": list(REQUIRED_PROTECTED_CATEGORIES),
        "qpc_frequency": raw.qpc_frequency,
        "timeline": [
            {"phase": phase, "counter": counter} for phase, counter in raw.timeline
        ],
        "restricted_parser_token": {
            "created": raw.token_created,
            "is_restricted": raw.token_is_restricted,
            "impersonation_active_for_operation": raw.impersonation_active_for_operation,
        },
        "categories": [_category_dict(value) for value in raw.categories],
        "operation_completed": operation_exception is None,
        "operation_exception_observed": operation_exception is not None,
        "diagnostic_errors": list(raw.diagnostic_errors),
        "bounded_runtime_noninterference_verified": bounded,
        "root_identity_and_membership_verified": root_identity_and_membership,
        "continuous_watch_verified": continuous_watch,
        "usn_interval_verified": usn_interval,
        "current_thread_restricted_token_write_open_denial_verified": (
            current_thread_write_deny
        ),
        # A thread impersonation token and bounded open probes are not a
        # process/job-wide write-deny policy.  Keep the stronger name false.
        "os_write_deny_verified": False,
        # Bounded current-thread observation is not a process/job-wide
        # noninterference proof.  Keep the unqualified authority claim false.
        "runtime_noninterference_verified": False,
        # This module accepts an arbitrary callback.  A higher layer must bind
        # parser provenance before it can truthfully name the callback parser.
        "parser_runtime_execution_verified": False,
        "qpc_monotonic_timeline_verified": bool(raw.qpc_frequency and _timeline_ok(raw.timeline)),
        "owner_authority_verified": False,
        "semantic_quality_verified": False,
        "p0_exit_authorized": False,
        "production_authorized": False,
        "gate_status": "NO_GO_BOUNDED_RUNTIME_EVIDENCE_ONLY" if bounded else "NO_GO_RUNTIME_EVIDENCE_INCOMPLETE",
    }
    return _with_hash(material, "evidence_sha256")


def _timeline_ok(timeline: tuple[tuple[str, int], ...]) -> bool:
    return (
        tuple(phase for phase, _ in timeline) == _PHASES
        and all(type(counter) is int and counter >= 0 for _, counter in timeline)
        and all(timeline[index][1] <= timeline[index + 1][1] for index in range(len(timeline) - 1))
    )


def _bounded_from_raw(
    raw: _RuntimeRawEvidence, operation_error: BaseException | None
) -> bool:
    return bool(
        raw.windows_observer
        and _timeline_ok(raw.timeline)
        and raw.token_created
        and raw.token_is_restricted
        and raw.impersonation_active_for_operation
        and operation_error is None
        and not raw.diagnostic_errors
        and all(_category_ok(value) for value in raw.categories)
    )


def _consume_windows_runtime_evidence_state(
    state: Any,
) -> _RuntimeExecutionState:
    """Consume and verify one state minted by this module exactly once.

    This is an in-process integrity boundary for honest integration code, not
    protection against arbitrary code execution in the verifier process.
    Registry membership prevents a caller-presented receipt, ``SimpleNamespace``
    lookalike, or copied dataclass from being mistaken for an observer result.
    """

    if type(state) is not _RuntimeExecutionState:
        raise P0WindowsRuntimeEvidenceError(
            "runtime execution state was not minted by the Windows observer"
        )
    with _ISSUED_EXECUTION_STATES_LOCK:
        issued_seal = _ISSUED_EXECUTION_STATES.pop(state, None)
    if (
        issued_seal is None
        or type(state._execution_seal) is not bytes
        or len(state._execution_seal) != 32
        or not hmac.compare_digest(issued_seal, state._execution_seal)
    ):
        raise P0WindowsRuntimeEvidenceError(
            "runtime execution state seal is absent, copied, or already consumed"
        )
    if type(state.raw_evidence) is not _RuntimeRawEvidence:
        raise P0WindowsRuntimeEvidenceError("runtime raw evidence type mismatch")
    expected_bounded = _bounded_from_raw(
        state.raw_evidence, state.operation_exception
    )
    if state.bounded_runtime_noninterference_verified is not expected_bounded:
        raise P0WindowsRuntimeEvidenceError(
            "runtime state bounded result disagrees with raw evidence"
        )
    expected_receipt = _receipt(
        state.raw_evidence, expected_bounded, state.operation_exception
    )
    presented_receipt = _thaw_json(state.detached_receipt)
    if (
        not isinstance(presented_receipt, dict)
        or not hmac.compare_digest(
            _canonical_sha256(presented_receipt),
            _canonical_sha256(expected_receipt),
        )
        or presented_receipt != expected_receipt
    ):
        raise P0WindowsRuntimeEvidenceError(
            "runtime execution receipt disagrees with frozen raw evidence"
        )
    return state


def _portable_failed_state(
    roots: tuple[tuple[str, str], ...],
    operation: Callable[[], _T],
) -> _RuntimeExecutionState:
    points: list[tuple[str, int]] = [("PRE_BEGIN", time.perf_counter_ns())]
    points.append(("PRE_COMPLETE", time.perf_counter_ns()))
    points.append(("PARSER_BEGIN", time.perf_counter_ns()))
    result: Any = None
    error: BaseException | None = None
    traceback: Any = None
    try:
        result = operation()
    except BaseException as exc:
        error, traceback = exc, exc.__traceback__
    points.append(("PARSER_COMPLETE", time.perf_counter_ns()))
    points.append(("POST_BEGIN", time.perf_counter_ns()))
    points.append(("POST_COMPLETE", time.perf_counter_ns()))
    categories = tuple(
        _CategoryEvidence(
            category,
            root,
            None,
            None,
            None,
            _unavailable_usn(),
            _unavailable_usn(),
            _Inventory(False, None, 0, False, "Win32 observer unavailable"),
            _Inventory(False, None, 0, False, "Win32 observer unavailable"),
            _WatchOutcome(False, False, None, None, False, False, True, (), None),
            _WatchOutcome(False, False, None, None, False, False, True, (), None),
            _WriteProbe(False, None, _FILE_ADD_FILE | _FILE_ADD_SUBDIRECTORY, False, False, None),
        )
        for category, root in roots
    )
    raw = _RuntimeRawEvidence(
        False,
        None,
        tuple(points),
        False,
        False,
        False,
        categories,
        ("Win32 QPC/USN/watch/restricted-token observer unavailable",),
    )
    return _issue_execution_state(raw, result, error, traceback, False)


def _execute_windows_runtime_evidence_state(
    protected_roots: Mapping[str, os.PathLike[str] | str],
    operation: Callable[[], _T],
    *,
    expected_identities: Mapping[str, Mapping[str, Any]] | None = None,
    impersonate_operation: bool = True,
) -> _RuntimeExecutionState:
    """Run ``operation`` inside the private same-process witness boundary."""

    if not callable(operation):
        raise P0WindowsRuntimeEvidenceError("operation must be callable")
    if type(impersonate_operation) is not bool:
        raise P0WindowsRuntimeEvidenceError("impersonate_operation must be boolean")
    roots = _normalise_roots(protected_roots)
    if expected_identities is not None:
        # Validate every caller-presented pin before the callback can run.  The
        # pins can constrain an observation but can never create authority.
        for category, _root in roots:
            _expected_for(expected_identities, category, None)
    if not _IS_WINDOWS:
        return _portable_failed_state(roots, operation)

    api = _Win32()
    frequency = api.frequency()
    timeline: list[tuple[str, int]] = [("PRE_BEGIN", api.qpc())]
    diagnostics: list[str] = []
    pre_identity: dict[str, _Identity | None] = {}
    pre_usn: dict[str, _Usn] = {}
    pre_inventory: dict[str, _Inventory] = {}
    watchers: dict[str, _Watcher] = {}
    parent_watchers: dict[str, _Watcher] = {}

    # Parent namespace requests are armed first.  They conservatively fail the
    # category on any parent entry change, including rename-aside, replacement,
    # deletion, or restore of the protected root name.
    for category, root in roots:
        parent = os.path.dirname(root.rstrip("\\/"))
        watcher = _Watcher(api, parent, watch_subtree=False)
        try:
            watcher.start()
        except BaseException as exc:
            diagnostics.append(
                f"{category}.parent_namespace_watch_start:{_safe_error(exc)}"
            )
        parent_watchers[category] = watcher

    # Every root watcher is pending before any PRE identity, USN, or inventory
    # snapshot is taken.
    for category, root in roots:
        watcher = _Watcher(api, root)
        try:
            watcher.start()
        except BaseException as exc:
            diagnostics.append(f"{category}.watch_start:{_safe_error(exc)}")
        watchers[category] = watcher

    for category, root in roots:
        try:
            if watchers[category].armed:
                pre_identity[category] = _identity_from_handle(
                    api, watchers[category].handle
                )
            else:
                pre_identity[category] = _identity(api, root)
        except BaseException as exc:
            pre_identity[category] = None
            diagnostics.append(f"{category}.pre_identity:{_safe_error(exc)}")
        pre_usn[category] = _query_usn(api, root)
        pre_inventory[category] = _inventory(root)
    timeline.append(("PRE_COMPLETE", api.qpc()))

    restricted_handle, token_restricted, token_error = _create_restricted_token(api)
    if token_error:
        diagnostics.append(token_error)
    impersonating = False
    if restricted_handle is not None:
        if api.ImpersonateLoggedOnUser(restricted_handle):
            impersonating = True
        else:
            diagnostics.append(f"ImpersonateLoggedOnUser:{ctypes.get_last_error()}")

    probes: dict[str, _WriteProbe] = {}
    for category, root in roots:
        try:
            probes[category] = _probe_write(api, root)
        except BaseException as exc:
            diagnostics.append(f"{category}.write_probe:{_safe_error(exc)}")
            probes[category] = _WriteProbe(
                False, None, _FILE_ADD_FILE | _FILE_ADD_SUBDIRECTORY, False, False, None
            )

    if impersonating and not impersonate_operation:
        if api.RevertToSelf():
            impersonating = False
        else:
            first_error = ctypes.get_last_error()
            if api.SetThreadToken(None, None):
                impersonating = False
                diagnostics.append(
                    f"RevertToSelf:{first_error};SetThreadToken:fallback"
                )
            else:
                diagnostics.append(
                    f"RevertToSelf:{first_error};SetThreadToken:{ctypes.get_last_error()}"
                )
    impersonated_operation = impersonating and impersonate_operation
    result: Any = None
    operation_error: BaseException | None = None
    operation_traceback: Any = None
    timeline.append(("PARSER_BEGIN", api.qpc()))
    try:
        result = operation()
    except BaseException as exc:
        operation_error, operation_traceback = exc, exc.__traceback__
    finally:
        timeline.append(("PARSER_COMPLETE", api.qpc()))
        if impersonating:
            if api.RevertToSelf():
                impersonating = False
            else:
                first_error = ctypes.get_last_error()
                # Documented fallback for clearing the current thread token.
                # Failure remains diagnostic and therefore closes the gate.
                if api.SetThreadToken(None, None):
                    impersonating = False
                    diagnostics.append(f"RevertToSelf:{first_error};SetThreadToken:fallback")
                else:
                    diagnostics.append(
                        f"RevertToSelf:{first_error};SetThreadToken:{ctypes.get_last_error()}"
                    )
        _close(api, restricted_handle)

    timeline.append(("POST_BEGIN", api.qpc()))
    post_identities: dict[str, _Identity | None] = {}
    post_usns: dict[str, _Usn] = {}
    post_inventories: dict[str, _Inventory] = {}
    for category, root in roots:
        try:
            post_identities[category] = _identity(api, root)
        except BaseException as exc:
            post_identities[category] = None
            diagnostics.append(f"{category}.post_identity:{_safe_error(exc)}")
        post_usns[category] = _query_usn(api, root)
        post_inventories[category] = _inventory(root)

    # Keep every directory request pending through every POST snapshot.  Only
    # after the complete category set is captured may cancellation establish
    # the no-completion/no-gap outcome.
    watch_outcomes: dict[str, _WatchOutcome] = {}
    parent_watch_outcomes: dict[str, _WatchOutcome] = {}
    for category, _root in roots:
        try:
            watch_outcomes[category] = watchers[category].stop()
        except BaseException as exc:
            diagnostics.append(f"{category}.watch_stop:{_safe_error(exc)}")
            watch_outcomes[category] = _WatchOutcome(
                True, False, None, api.qpc(), False, False, True, (), None
            )
    for category, _root in roots:
        try:
            parent_watch_outcomes[category] = parent_watchers[category].stop()
        except BaseException as exc:
            diagnostics.append(
                f"{category}.parent_namespace_watch_stop:{_safe_error(exc)}"
            )
            parent_watch_outcomes[category] = _WatchOutcome(
                True, False, None, api.qpc(), False, False, True, (), None
            )

    categories: list[_CategoryEvidence] = []
    for category, root in roots:
        evidence = _CategoryEvidence(
            category=category,
            requested_root=root,
            pre_identity=pre_identity[category],
            post_identity=post_identities[category],
            expected_identity_match=_expected_for(
                expected_identities, category, pre_identity[category]
            ),
            pre_usn=pre_usn[category],
            post_usn=post_usns[category],
            pre_inventory=pre_inventory[category],
            post_inventory=post_inventories[category],
            watch=watch_outcomes[category],
            parent_namespace_watch=parent_watch_outcomes[category],
            write_probe=probes[category],
        )
        categories.append(evidence)
    timeline.append(("POST_COMPLETE", api.qpc()))
    raw = _RuntimeRawEvidence(
        True,
        frequency,
        tuple(timeline),
        restricted_handle is not None,
        token_restricted,
        impersonated_operation,
        tuple(categories),
        tuple(diagnostics),
    )
    bounded = _bounded_from_raw(raw, operation_error)
    return _issue_execution_state(
        raw, result, operation_error, operation_traceback, bounded
    )


def execute_windows_runtime_evidence(
    protected_roots: Mapping[str, os.PathLike[str] | str],
    operation: Callable[[], _T],
    *,
    expected_identities: Mapping[str, Mapping[str, Any]] | None = None,
    impersonate_operation: bool = True,
) -> tuple[_T, dict[str, Any]]:
    """Execute a callback and return its result plus a detached diagnostic receipt.

    If the callback raises, POST collection and watch finalization occur first,
    then the original exception is re-raised with its original traceback.  When
    possible a detached receipt is attached as
    ``p0_windows_runtime_evidence_receipt``.
    """

    state = _execute_windows_runtime_evidence_state(
        protected_roots,
        operation,
        expected_identities=expected_identities,
        impersonate_operation=impersonate_operation,
    )
    state = _consume_windows_runtime_evidence_state(state)
    detached = _thaw_json(state.detached_receipt)
    if state.operation_exception is not None:
        try:
            setattr(
                state.operation_exception,
                "p0_windows_runtime_evidence_receipt",
                detached,
            )
        except BaseException:
            pass
        raise state.operation_exception.with_traceback(state.operation_traceback)
    return state.operation_result, detached


def _strict_mapping(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise P0WindowsRuntimeEvidenceError(f"{label} has invalid fields")
    return value


def _presented_violation(row: Mapping[str, Any]) -> str | None:
    if row["platform"] != "windows" or row["observer"] != "stdlib-ctypes-win32-v1":
        return "Windows ctypes observer provenance is absent"
    if row["required_categories"] != list(REQUIRED_PROTECTED_CATEGORIES):
        return "required category set is missing or reordered"
    timeline = row["timeline"]
    if not isinstance(timeline, list) or len(timeline) != len(_PHASES):
        return "QPC timeline is incomplete"
    pairs: list[tuple[str, int]] = []
    for item in timeline:
        value = _strict_mapping(item, {"phase", "counter"}, "timeline point")
        if not isinstance(value["phase"], str) or type(value["counter"]) is not int:
            return "QPC timeline value is invalid"
        pairs.append((value["phase"], value["counter"]))
    if type(row["qpc_frequency"]) is not int or row["qpc_frequency"] <= 0 or not _timeline_ok(tuple(pairs)):
        return "QPC timeline is not monotonic"
    phase_counter = dict(pairs)
    if row["qpc_monotonic_timeline_verified"] is not True:
        return "QPC timeline claim is not verified"
    if row["diagnostic_errors"] != []:
        return "runtime observer reported diagnostic errors"
    token = _strict_mapping(
        row["restricted_parser_token"],
        {"created", "is_restricted", "impersonation_active_for_operation"},
        "restricted parser token",
    )
    if not all(token.get(key) is True for key in token):
        return "restricted parser token did not span operation"
    categories = row["categories"]
    if not isinstance(categories, list) or [value.get("category") for value in categories if isinstance(value, Mapping)] != list(REQUIRED_PROTECTED_CATEGORIES):
        return "protected categories are incomplete or reordered"
    folded: list[str] = []
    for category in categories:
        if not isinstance(category, Mapping):
            return "category evidence is invalid"
        root = category.get("requested_root")
        if not isinstance(root, str) or not root:
            return "protected root is invalid"
        folded.append(root.replace("/", "\\").rstrip("\\").casefold())
        pre = category.get("pre_identity")
        post = category.get("post_identity")
        if not isinstance(pre, Mapping) or pre != post or pre.get("reparse_point") is not False:
            return "protected root identity mismatch"
        if category.get("expected_identity_match") is False:
            return "protected root differs from expected identity"
        pre_inventory = category.get("pre_inventory")
        post_inventory = category.get("post_inventory")
        if (
            not isinstance(pre_inventory, Mapping)
            or not isinstance(post_inventory, Mapping)
            or pre_inventory.get("available") is not True
            or post_inventory.get("available") is not True
            or pre_inventory.get("reparse_seen") is not False
            or post_inventory.get("reparse_seen") is not False
            or pre_inventory.get("sha256") != post_inventory.get("sha256")
            or pre_inventory.get("entry_count") != post_inventory.get("entry_count")
        ):
            return "protected tree inventory changed or is unavailable"
        for watch_key, expected_scope in (
            ("watch", "PROTECTED_ROOT_RECURSIVE"),
            (
                "parent_namespace_watch",
                "PARENT_DIRECTORY_ROOT_ENTRY_NAMESPACE",
            ),
        ):
            watch = category.get(watch_key)
            if not isinstance(watch, Mapping):
                return f"{watch_key} evidence is invalid"
            if watch.get("overflow") is True:
                return f"{watch_key} overflow observed"
            if (
                watch.get("gap") is True
                or watch.get("continuous") is not True
                or watch.get("armed") is not True
            ):
                return f"{watch_key} continuity gap observed"
            if watch.get("events") != []:
                return f"{watch_key} change event observed"
            if (
                watch.get("api_available") is not True
                or watch.get("api") != "ReadDirectoryChangesExW"
                or watch.get("scope") != expected_scope
            ):
                return f"{watch_key} ReadDirectoryChangesExW evidence unavailable"
            armed_counter = watch.get("armed_counter")
            stopped_counter = watch.get("stopped_counter")
            if (
                type(armed_counter) is not int
                or type(stopped_counter) is not int
                or not phase_counter["PRE_BEGIN"]
                <= armed_counter
                <= phase_counter["PRE_COMPLETE"]
                or not phase_counter["POST_BEGIN"]
                <= stopped_counter
                <= phase_counter["POST_COMPLETE"]
            ):
                return f"{watch_key} does not span PRE/parser/POST chronology"
        pre_usn = category.get("pre_usn")
        post_usn = category.get("post_usn")
        if not isinstance(pre_usn, Mapping) or not isinstance(post_usn, Mapping):
            return "USN evidence is invalid"
        if (
            pre_usn.get("available") is not True
            or post_usn.get("available") is not True
            or pre_usn.get("volume_guid") != post_usn.get("volume_guid")
            or pre_usn.get("journal_id") != post_usn.get("journal_id")
            or type(pre_usn.get("next_usn")) is not int
            or type(post_usn.get("next_usn")) is not int
            or type(post_usn.get("first_usn")) is not int
            or not post_usn["first_usn"] <= pre_usn["next_usn"] <= post_usn["next_usn"]
        ):
            return "USN journal interval is unavailable or discontinuous"
        probe = category.get("write_open_probe")
        if not isinstance(probe, Mapping) or not (
            probe.get("scope")
            == "CURRENT_THREAD_RESTRICTED_TOKEN_NON_MUTATING_OPEN_PROBE"
            and
            probe.get("attempted") is True
            and probe.get("open_succeeded") is False
            and probe.get("denied") is True
            and probe.get("error_code") == _ERROR_ACCESS_DENIED
        ):
            return "restricted-token write-open denial was not observed"
        if (
            type(probe.get("counter")) is not int
            or not phase_counter["PRE_COMPLETE"]
            <= probe["counter"]
            <= phase_counter["PARSER_BEGIN"]
        ):
            return "write-open probe is outside parser chronology"
        if category.get("bounded_category_noninterference_verified") is not True:
            return "bounded category evidence is not verified"
    for index, left in enumerate(folded):
        for right in folded[index + 1 :]:
            if left == right or left.startswith(right + "\\") or right.startswith(left + "\\"):
                return "protected category roots overlap"
    if row["operation_completed"] is not True or row["operation_exception_observed"] is not False:
        return "operation did not complete"
    if row["bounded_runtime_noninterference_verified"] is not True:
        return "bounded runtime evidence is not verified"
    if row["gate_status"] != "NO_GO_BOUNDED_RUNTIME_EVIDENCE_ONLY":
        return "bounded evidence gate status is invalid"
    for aggregate in (
        "root_identity_and_membership_verified",
        "continuous_watch_verified",
        "usn_interval_verified",
    ):
        if row[aggregate] is not True:
            return f"aggregate runtime evidence is not verified: {aggregate}"
    if row["current_thread_restricted_token_write_open_denial_verified"] is not True:
        return "current-thread restricted-token write denial is not verified"
    if row["os_write_deny_verified"] is not False:
        return "forbidden process-wide OS write-deny overclaim"
    if row["runtime_noninterference_verified"] is not False:
        return "forbidden process/job-wide runtime noninterference overclaim"
    if row["parser_runtime_execution_verified"] is not False:
        return "forbidden upgrade claim: parser_runtime_execution_verified"
    for field in (
        "owner_authority_verified",
        "semantic_quality_verified",
        "p0_exit_authorized",
        "production_authorized",
    ):
        if row[field] is not False:
            return f"forbidden upgrade claim: {field}"
    return None


def validate_windows_runtime_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a serialized receipt, then explicitly downgrade its truths.

    The input must describe a complete bounded observation.  Missing
    categories, overlap, changes, identity/USN discontinuity, watch gaps or
    overflow, and successful write-open probes are rejected.  Even accepted
    bytes are merely presented data and cannot establish same-process runtime
    provenance.
    """

    fields = {
        "schema",
        "platform",
        "observer",
        "required_categories",
        "qpc_frequency",
        "timeline",
        "restricted_parser_token",
        "categories",
        "operation_completed",
        "operation_exception_observed",
        "diagnostic_errors",
        "bounded_runtime_noninterference_verified",
        "root_identity_and_membership_verified",
        "continuous_watch_verified",
        "usn_interval_verified",
        "current_thread_restricted_token_write_open_denial_verified",
        "os_write_deny_verified",
        "runtime_noninterference_verified",
        "parser_runtime_execution_verified",
        "qpc_monotonic_timeline_verified",
        "owner_authority_verified",
        "semantic_quality_verified",
        "p0_exit_authorized",
        "production_authorized",
        "gate_status",
        "evidence_sha256",
    }
    row = _strict_mapping(value, fields, "runtime evidence")
    if row["schema"] != RUNTIME_EVIDENCE_SCHEMA:
        raise P0WindowsRuntimeEvidenceError("runtime evidence schema mismatch")
    stored_hash = row["evidence_sha256"]
    material = {key: item for key, item in row.items() if key != "evidence_sha256"}
    if not isinstance(stored_hash, str) or stored_hash != _canonical_sha256(material):
        raise P0WindowsRuntimeEvidenceError("runtime evidence self-hash mismatch")
    violation = _presented_violation(row)
    if violation is not None:
        raise P0WindowsRuntimeEvidenceError(violation)
    material_out = {
        "schema": RUNTIME_VALIDATION_RECEIPT_SCHEMA,
        "presented_evidence_sha256": stored_hash,
        "presented_structure_verified": True,
        "presented_bounded_claim_well_formed": True,
        "same_process_execution_provenance_verified": False,
        "qpc_monotonic_timeline_verified": False,
        "root_identity_and_membership_verified": False,
        "usn_interval_verified": False,
        "watch_continuity_verified": False,
        "restricted_parser_write_denial_verified": False,
        "current_thread_restricted_token_write_open_denial_verified": False,
        "os_write_deny_verified": False,
        "runtime_noninterference_verified": False,
        "parser_runtime_execution_verified": False,
        "owner_authority_verified": False,
        "semantic_quality_verified": False,
        "p0_exit_authorized": False,
        "production_authorized": False,
        "gate_status": "NO_GO_PRESENTED_RECEIPT_CANNOT_PROVE_EXECUTION",
    }
    return _with_hash(material_out, "receipt_sha256")


__all__ = [
    "P0WindowsRuntimeEvidenceError",
    "REQUIRED_PROTECTED_CATEGORIES",
    "RUNTIME_EVIDENCE_SCHEMA",
    "RUNTIME_VALIDATION_RECEIPT_SCHEMA",
    "execute_windows_runtime_evidence",
    "validate_windows_runtime_evidence",
]
