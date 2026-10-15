"""Windows handle-bound reader for the fixed actual-P0 packet directory.

This module is intentionally narrower than an authority verifier.  It pins the
packet namespace and every packet file to Windows kernel handles while bytes
are read, then returns those bytes to the existing pure packet validator.  A
successful receipt proves only the bounded handle/read observation.  It does
not prove an OS write-deny policy, a complete USN/watch interval, runtime
non-interference, external owner authority, or permission to leave P0.

The implementation uses only the Python standard library and Win32 APIs made
available through :mod:`ctypes`.  Importing the module is portable; attempting
to validate outside Windows fails closed before any filesystem access.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct
from typing import Any, Mapping, Sequence


WINDOWS_HANDLE_RECEIPT_SCHEMA = "p0_windows_fixed_directory_handle_receipt_v1"
WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA = (
    "p0_windows_fixed_directory_packet_validation_receipt_v1"
)

_IS_WINDOWS = os.name == "nt"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_VOLUME_GUID_PATH = re.compile(
    r"^\\\\\?\\Volume\{[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}(?:\\.*)?$"
)

_GENERIC_READ = 0x80000000
_FILE_LIST_DIRECTORY = 0x0001
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_SHARE_READ = 0x00000001
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000

_FILE_BASIC_INFO_CLASS = 0
_FILE_STANDARD_INFO_CLASS = 1
_FILE_STREAM_INFO_CLASS = 7
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_ID_INFO_CLASS = 0x12
_FILE_ID_EXTD_DIRECTORY_INFO_CLASS = 0x13
_FILE_ID_EXTD_DIRECTORY_RESTART_INFO_CLASS = 0x14

_FILE_NAME_NORMALIZED = 0x0
_VOLUME_NAME_GUID = 0x1

_ERROR_NO_MORE_FILES = 18
_ERROR_INSUFFICIENT_BUFFER = 122
_ERROR_MORE_DATA = 234
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_MAX_FINAL_PATH_CHARS = 32768
_MAX_STREAM_BUFFER = 1024 * 1024
_MAX_SINGLE_FILE_BYTES = 128 * 1024 * 1024
_MAX_TOTAL_BYTES = 512 * 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024
_DIRECTORY_BUFFER_BYTES = 64 * 1024


class P0WindowsFixedDirectoryError(ValueError):
    """Raised when the Windows fixed-directory observation fails closed."""


class _FILE_ID_128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_ubyte * 16)]


class _FILE_ID_INFO(ctypes.Structure):
    _fields_ = [
        ("VolumeSerialNumber", ctypes.c_ulonglong),
        ("FileId", _FILE_ID_128),
    ]


class _FILE_BASIC_INFO(ctypes.Structure):
    _fields_ = [
        ("CreationTime", ctypes.c_longlong),
        ("LastAccessTime", ctypes.c_longlong),
        ("LastWriteTime", ctypes.c_longlong),
        ("ChangeTime", ctypes.c_longlong),
        ("FileAttributes", wintypes.DWORD),
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


@dataclass(frozen=True)
class WindowsDirectoryIdentity:
    """Observed root identity; observation alone is not an authority pin."""

    final_path: str
    volume_serial: int
    file_id: str


@dataclass(frozen=True)
class WindowsFixedDirectoryRead:
    """Handle-bound packet bytes and the self-hashed observation receipt."""

    raw_by_name: Mapping[str, bytes]
    receipt: Mapping[str, Any]

    @property
    def manifest_bytes(self) -> bytes:
        from llm_batch.grounding.p0_actual_packet_contract import (
            PACKET_MANIFEST_FILENAME,
        )

        return self.raw_by_name[PACKET_MANIFEST_FILENAME]

    @property
    def child_bytes(self) -> dict[str, bytes]:
        from llm_batch.grounding.p0_actual_packet_contract import (
            PACKET_MANIFEST_FILENAME,
        )

        return {
            name: raw
            for name, raw in self.raw_by_name.items()
            if name != PACKET_MANIFEST_FILENAME
        }


@dataclass(frozen=True)
class _ObjectSnapshot:
    final_path: str
    volume_serial: int
    file_id: str
    basic: tuple[int, int, int, int, int]
    standard: tuple[int, int, int, bool, bool]
    reparse_tag: int
    streams: tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class _DirectoryEntry:
    name: str
    file_id: str
    size: int
    allocation_size: int
    creation_time: int
    last_write_time: int
    change_time: int
    attributes: int
    reparse_tag: int

    def stable_projection(self) -> dict[str, Any]:
        # Last-access time is deliberately excluded: a read can legitimately
        # update it on volumes where last-access tracking is enabled.
        return {
            "name": self.name,
            "file_id": self.file_id,
            "size": self.size,
            "allocation_size": self.allocation_size,
            "creation_time": self.creation_time,
            "last_write_time": self.last_write_time,
            "change_time": self.change_time,
            "attributes": self.attributes,
            "reparse_tag": self.reparse_tag,
        }


class _Win32:
    def __init__(self) -> None:
        if not _IS_WINDOWS:
            raise P0WindowsFixedDirectoryError(
                "Windows fixed-directory validation is unavailable on this platform"
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

        self.ReadFile = kernel32.ReadFile
        self.ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self.ReadFile.restype = wintypes.BOOL


class _OwnedHandle:
    def __init__(self, api: _Win32, value: int, label: str) -> None:
        self.api = api
        self.value = value
        self.label = label

    def __enter__(self) -> "_OwnedHandle":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.value not in (None, _INVALID_HANDLE_VALUE):
            value = self.value
            self.value = None  # type: ignore[assignment]
            try:
                closed = self.api.CloseHandle(value)
            except BaseException as cleanup_error:
                if exc_type is None:
                    raise P0WindowsFixedDirectoryError(
                        f"CloseHandle raised for {self.label}"
                    ) from cleanup_error
                return
            if not closed and exc_type is None:
                raise _winerror(f"CloseHandle({self.label})")


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


def _winerror(label: str) -> P0WindowsFixedDirectoryError:
    code = ctypes.get_last_error()
    return P0WindowsFixedDirectoryError(f"{label} failed with Windows error {code}")


def _open_handle(
    api: _Win32,
    path: str,
    *,
    directory: bool,
    read_data: bool,
) -> _OwnedHandle:
    desired = _FILE_READ_ATTRIBUTES
    if directory:
        desired |= _FILE_LIST_DIRECTORY
    if read_data:
        desired |= _GENERIC_READ
    flags = _FILE_FLAG_OPEN_REPARSE_POINT
    if directory:
        flags |= _FILE_FLAG_BACKUP_SEMANTICS
    if read_data:
        flags |= _FILE_FLAG_SEQUENTIAL_SCAN
    value = api.CreateFileW(
        path,
        desired,
        _FILE_SHARE_READ,
        None,
        _OPEN_EXISTING,
        flags,
        None,
    )
    if value == _INVALID_HANDLE_VALUE:
        raise _winerror(f"open {path}")
    return _OwnedHandle(api, value, path)


def _query_struct(api: _Win32, handle: int, info_class: int, value: Any, label: str) -> Any:
    if not api.GetFileInformationByHandleEx(
        handle, info_class, ctypes.byref(value), ctypes.sizeof(value)
    ):
        raise _winerror(label)
    return value


def _query_final_path(api: _Win32, handle: int) -> str:
    size = 1024
    while size <= _MAX_FINAL_PATH_CHARS:
        buffer = ctypes.create_unicode_buffer(size)
        used = api.GetFinalPathNameByHandleW(
            handle, buffer, size, _FILE_NAME_NORMALIZED | _VOLUME_NAME_GUID
        )
        if used == 0:
            raise _winerror("GetFinalPathNameByHandleW")
        if used < size:
            value = buffer.value
            if not _VOLUME_GUID_PATH.fullmatch(value.rstrip("\\")):
                raise P0WindowsFixedDirectoryError(
                    "final path is not a local volume-GUID path"
                )
            return value.rstrip("\\")
        size = used + 1
    raise P0WindowsFixedDirectoryError("final path exceeds strict size limit")


def _query_streams(api: _Win32, handle: int) -> tuple[tuple[str, int, int], ...]:
    size = 4096
    while size <= _MAX_STREAM_BUFFER:
        buffer = ctypes.create_string_buffer(size)
        if api.GetFileInformationByHandleEx(
            handle, _FILE_STREAM_INFO_CLASS, buffer, size
        ):
            break
        error = ctypes.get_last_error()
        if error not in {_ERROR_MORE_DATA, _ERROR_INSUFFICIENT_BUFFER}:
            raise _winerror("query file streams")
        size *= 2
    else:
        raise P0WindowsFixedDirectoryError("file stream inventory exceeds strict limit")

    result: list[tuple[str, int, int]] = []
    offset = 0
    while True:
        if offset + 24 > size:
            raise P0WindowsFixedDirectoryError("malformed FILE_STREAM_INFO buffer")
        next_offset, name_bytes = struct.unpack_from("<II", buffer.raw, offset)
        stream_size, allocation_size = struct.unpack_from("<qq", buffer.raw, offset + 8)
        end = offset + 24 + name_bytes
        if name_bytes % 2 or end > size:
            raise P0WindowsFixedDirectoryError("malformed file stream name")
        try:
            name = buffer.raw[offset + 24 : end].decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise P0WindowsFixedDirectoryError("invalid file stream name") from exc
        result.append((name, int(stream_size), int(allocation_size)))
        if next_offset == 0:
            break
        if next_offset < 24 or next_offset % 8 or offset + next_offset >= size:
            raise P0WindowsFixedDirectoryError("malformed file stream offset")
        offset += next_offset
    return tuple(result)


def _query_snapshot(api: _Win32, handle: int, *, include_streams: bool) -> _ObjectSnapshot:
    identity = _query_struct(api, handle, _FILE_ID_INFO_CLASS, _FILE_ID_INFO(), "query file ID")
    basic = _query_struct(api, handle, _FILE_BASIC_INFO_CLASS, _FILE_BASIC_INFO(), "query basic info")
    standard = _query_struct(
        api, handle, _FILE_STANDARD_INFO_CLASS, _FILE_STANDARD_INFO(), "query standard info"
    )
    tag = _query_struct(
        api,
        handle,
        _FILE_ATTRIBUTE_TAG_INFO_CLASS,
        _FILE_ATTRIBUTE_TAG_INFO(),
        "query attribute tag",
    )
    return _ObjectSnapshot(
        final_path=_query_final_path(api, handle),
        volume_serial=int(identity.VolumeSerialNumber),
        file_id=bytes(identity.FileId.Identifier).hex(),
        basic=(
            int(basic.CreationTime),
            int(basic.LastAccessTime),
            int(basic.LastWriteTime),
            int(basic.ChangeTime),
            int(basic.FileAttributes),
        ),
        standard=(
            int(standard.AllocationSize),
            int(standard.EndOfFile),
            int(standard.NumberOfLinks),
            bool(standard.DeletePending),
            bool(standard.Directory),
        ),
        reparse_tag=int(tag.ReparseTag),
        streams=_query_streams(api, handle) if include_streams else (),
    )


def _assert_no_reparse(snapshot: _ObjectSnapshot, label: str) -> None:
    if snapshot.basic[4] & _FILE_ATTRIBUTE_REPARSE_POINT or snapshot.reparse_tag:
        raise P0WindowsFixedDirectoryError(f"{label} must not be a reparse point")


def _assert_directory(snapshot: _ObjectSnapshot, label: str) -> None:
    _assert_no_reparse(snapshot, label)
    if not snapshot.standard[4] or not snapshot.basic[4] & _FILE_ATTRIBUTE_DIRECTORY:
        raise P0WindowsFixedDirectoryError(f"{label} must be a directory")
    if snapshot.standard[3]:
        raise P0WindowsFixedDirectoryError(f"{label} is delete-pending")


def _assert_regular_single_link(snapshot: _ObjectSnapshot, label: str) -> None:
    _assert_no_reparse(snapshot, label)
    if snapshot.standard[4] or snapshot.basic[4] & _FILE_ATTRIBUTE_DIRECTORY:
        raise P0WindowsFixedDirectoryError(f"{label} must be a regular file")
    if snapshot.standard[3]:
        raise P0WindowsFixedDirectoryError(f"{label} is delete-pending")
    if snapshot.standard[2] != 1:
        raise P0WindowsFixedDirectoryError(f"{label} hardlink count must be exactly one")
    if len(snapshot.streams) != 1 or snapshot.streams[0][0] != "::$DATA":
        raise P0WindowsFixedDirectoryError(
            f"{label} must contain only the unnamed data stream"
        )
    if snapshot.streams[0][1] != snapshot.standard[1]:
        raise P0WindowsFixedDirectoryError(f"{label} stream size mismatch")


def _normalise_final_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not _VOLUME_GUID_PATH.fullmatch(
        value.rstrip("\\")
    ):
        raise P0WindowsFixedDirectoryError(
            f"{label} must be an absolute Windows volume-GUID path"
        )
    result = value.rstrip("\\")
    if not result or "\x00" in result:
        raise P0WindowsFixedDirectoryError(f"{label} is invalid")
    return result


def _validate_expected_identity(
    *,
    expected_final_path: str,
    expected_volume_serial: int,
    expected_file_id: str,
) -> tuple[str, int, str]:
    final_path = _normalise_final_path(expected_final_path, "expected root final path")
    if (
        isinstance(expected_volume_serial, bool)
        or not isinstance(expected_volume_serial, int)
        or not 0 <= expected_volume_serial < 2**64
    ):
        raise P0WindowsFixedDirectoryError("expected root volume serial is invalid")
    if not isinstance(expected_file_id, str) or not _FILE_ID.fullmatch(expected_file_id):
        raise P0WindowsFixedDirectoryError(
            "expected root file ID must be 32 lowercase hexadecimal characters"
        )
    return final_path, expected_volume_serial, expected_file_id


def _lexical_ancestor_paths(packet_dir: Path | str) -> tuple[str, tuple[str, ...]]:
    raw = os.fspath(packet_dir)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise P0WindowsFixedDirectoryError("packet directory path is invalid")
    if not os.path.isabs(raw):
        raise P0WindowsFixedDirectoryError("packet directory path must be absolute")
    absolute = os.path.abspath(raw)
    drive, tail = os.path.splitdrive(absolute)
    if not drive or drive.startswith("\\\\"):
        raise P0WindowsFixedDirectoryError("packet directory must be on a local drive")
    parts = [part for part in tail.replace("/", "\\").split("\\") if part]
    if not parts:
        raise P0WindowsFixedDirectoryError("volume root cannot be the packet directory")
    current = drive + "\\"
    built: list[str] = [current]
    for part in parts:
        if (
            part in {".", ".."}
            or ":" in part
            or part.endswith(".")
            or part.endswith(" ")
        ):
            raise P0WindowsFixedDirectoryError("packet path component is invalid")
        current = os.path.join(current, part)
        built.append(current)
    return built[-1], tuple(built[:-1])


def _enumerate_directory(api: _Win32, handle: int) -> dict[str, _DirectoryEntry]:
    values: dict[str, _DirectoryEntry] = {}
    casefolded: set[str] = set()
    first = True
    while True:
        buffer = ctypes.create_string_buffer(_DIRECTORY_BUFFER_BYTES)
        info_class = (
            _FILE_ID_EXTD_DIRECTORY_RESTART_INFO_CLASS
            if first
            else _FILE_ID_EXTD_DIRECTORY_INFO_CLASS
        )
        first = False
        if not api.GetFileInformationByHandleEx(
            handle, info_class, buffer, _DIRECTORY_BUFFER_BYTES
        ):
            error = ctypes.get_last_error()
            if error == _ERROR_NO_MORE_FILES:
                break
            raise _winerror("enumerate directory by handle")

        offset = 0
        while True:
            if offset + 88 > _DIRECTORY_BUFFER_BYTES:
                raise P0WindowsFixedDirectoryError("malformed directory inventory buffer")
            (
                next_offset,
                _file_index,
                creation_time,
                _last_access_time,
                last_write_time,
                change_time,
                end_of_file,
                allocation_size,
                attributes,
                name_bytes,
                _ea_size,
                reparse_tag,
                file_id,
            ) = struct.unpack_from("<IIqqqqqqIIII16s", buffer.raw, offset)
            end = offset + 88 + name_bytes
            if name_bytes % 2 or end > _DIRECTORY_BUFFER_BYTES:
                raise P0WindowsFixedDirectoryError("malformed directory entry name")
            try:
                name = buffer.raw[offset + 88 : end].decode("utf-16-le")
            except UnicodeDecodeError as exc:
                raise P0WindowsFixedDirectoryError("invalid directory entry name") from exc
            if name not in {".", ".."}:
                folded = name.casefold()
                if name in values or folded in casefolded:
                    raise P0WindowsFixedDirectoryError(
                        "directory inventory contains duplicate/case-colliding names"
                    )
                casefolded.add(folded)
                values[name] = _DirectoryEntry(
                    name=name,
                    file_id=file_id.hex(),
                    size=int(end_of_file),
                    allocation_size=int(allocation_size),
                    creation_time=int(creation_time),
                    last_write_time=int(last_write_time),
                    change_time=int(change_time),
                    attributes=int(attributes),
                    reparse_tag=int(reparse_tag),
                )
            if next_offset == 0:
                break
            if next_offset < 88 or next_offset % 8 or offset + next_offset >= _DIRECTORY_BUFFER_BYTES:
                raise P0WindowsFixedDirectoryError("malformed directory entry offset")
            offset += next_offset
    return values


def _inventory_projection(values: Mapping[str, _DirectoryEntry]) -> list[dict[str, Any]]:
    return [values[name].stable_projection() for name in sorted(values)]


def _validate_inventory(
    values: Mapping[str, _DirectoryEntry], expected_names: frozenset[str]
) -> None:
    if set(values) != expected_names:
        raise P0WindowsFixedDirectoryError("fixed directory inventory mismatch")
    for name, entry in values.items():
        if entry.attributes & (_FILE_ATTRIBUTE_DIRECTORY | _FILE_ATTRIBUTE_REPARSE_POINT):
            raise P0WindowsFixedDirectoryError(
                f"fixed packet member is not a regular non-reparse file: {name}"
            )
        if entry.reparse_tag:
            raise P0WindowsFixedDirectoryError(
                f"fixed packet member has a reparse tag: {name}"
            )


def _read_handle_exact(api: _Win32, handle: int, expected_size: int, label: str) -> bytes:
    if not 0 <= expected_size <= _MAX_SINGLE_FILE_BYTES:
        raise P0WindowsFixedDirectoryError(f"{label} exceeds strict byte limit")
    remaining = expected_size
    chunks: list[bytes] = []
    while remaining:
        requested = min(remaining, _READ_CHUNK_BYTES)
        buffer = ctypes.create_string_buffer(requested)
        read = wintypes.DWORD()
        if not api.ReadFile(handle, buffer, requested, ctypes.byref(read), None):
            raise _winerror(f"read {label}")
        count = int(read.value)
        if count <= 0 or count > requested:
            raise P0WindowsFixedDirectoryError(f"{label} returned a short/invalid read")
        chunks.append(buffer.raw[:count])
        remaining -= count

    probe = ctypes.create_string_buffer(1)
    probe_count = wintypes.DWORD()
    if not api.ReadFile(handle, probe, 1, ctypes.byref(probe_count), None):
        raise _winerror(f"probe EOF for {label}")
    if probe_count.value != 0:
        raise P0WindowsFixedDirectoryError(f"{label} grew while being read")
    return b"".join(chunks)


def _snapshot_stable(before: _ObjectSnapshot, after: _ObjectSnapshot) -> bool:
    # LastAccessTime may change because this verifier read the file itself.
    before_basic = (before.basic[0], before.basic[2], before.basic[3], before.basic[4])
    after_basic = (after.basic[0], after.basic[2], after.basic[3], after.basic[4])
    return (
        before.final_path.casefold() == after.final_path.casefold()
        and before.volume_serial == after.volume_serial
        and before.file_id == after.file_id
        and before_basic == after_basic
        and before.standard == after.standard
        and before.reparse_tag == after.reparse_tag
        and before.streams == after.streams
    )


def _snapshot_stable_projection(snapshot: _ObjectSnapshot) -> dict[str, Any]:
    """Return the stable, receipt-safe projection used for before/after binding."""

    return {
        "final_path": snapshot.final_path,
        "volume_serial": str(snapshot.volume_serial),
        "file_id": snapshot.file_id,
        "creation_time": snapshot.basic[0],
        "last_write_time": snapshot.basic[2],
        "change_time": snapshot.basic[3],
        "file_attributes": snapshot.basic[4],
        "allocation_size": snapshot.standard[0],
        "end_of_file": snapshot.standard[1],
        "number_of_links": snapshot.standard[2],
        "delete_pending": snapshot.standard[3],
        "directory": snapshot.standard[4],
        "reparse_tag": snapshot.reparse_tag,
        "streams": [list(stream) for stream in snapshot.streams],
    }


def _ancestor_namespace_projection(snapshot: _ObjectSnapshot) -> dict[str, Any]:
    """Project only namespace identity stable across unrelated sibling activity."""

    return {
        "final_path": snapshot.final_path,
        "volume_serial": str(snapshot.volume_serial),
        "file_id": snapshot.file_id,
        "creation_time": snapshot.basic[0],
        "file_attributes": snapshot.basic[4],
        "number_of_links": snapshot.standard[2],
        "delete_pending": snapshot.standard[3],
        "directory": snapshot.standard[4],
        "reparse_tag": snapshot.reparse_tag,
    }


def _assert_direct_final_path_descendant(
    parent_final_path: str, child_final_path: str, label: str
) -> None:
    prefix = parent_final_path.rstrip("\\") + "\\"
    # Both values come from GetFinalPathNameByHandleW on the same volume, so
    # their normalized component casing must be identical.  Exact prefixing
    # also avoids Unicode case-fold length ambiguities during boundary slicing.
    if not child_final_path.startswith(prefix):
        raise P0WindowsFixedDirectoryError(
            f"{label} is outside its pinned parent final path"
        )
    remainder = child_final_path[len(prefix) :]
    if not remainder or "\\" in remainder or "/" in remainder:
        raise P0WindowsFixedDirectoryError(
            f"{label} is not a component-boundary direct descendant"
        )


def _assert_entry_matches_snapshot(
    entry: _DirectoryEntry, snapshot: _ObjectSnapshot, name: str
) -> None:
    expected = {
        "file_id": entry.file_id,
        "end_of_file": entry.size,
        "allocation_size": entry.allocation_size,
        "creation_time": entry.creation_time,
        "last_write_time": entry.last_write_time,
        "change_time": entry.change_time,
        "attributes": entry.attributes,
        "reparse_tag": entry.reparse_tag,
    }
    observed = {
        "file_id": snapshot.file_id,
        "end_of_file": snapshot.standard[1],
        "allocation_size": snapshot.standard[0],
        "creation_time": snapshot.basic[0],
        "last_write_time": snapshot.basic[2],
        "change_time": snapshot.basic[3],
        "attributes": snapshot.basic[4],
        "reparse_tag": snapshot.reparse_tag,
    }
    if expected != observed:
        mismatched = sorted(
            field for field in expected if expected[field] != observed[field]
        )
        raise P0WindowsFixedDirectoryError(
            f"directory-entry/open-handle metadata mismatch for {name}: {mismatched}"
        )


def observe_windows_directory_identity(packet_dir: Path | str) -> WindowsDirectoryIdentity:
    """Observe a directory identity without treating it as an external pin."""

    if not _IS_WINDOWS:
        raise P0WindowsFixedDirectoryError(
            "Windows fixed-directory validation is unavailable on this platform"
        )
    api = _Win32()
    root_path, _ = _lexical_ancestor_paths(packet_dir)
    with _open_handle(api, root_path, directory=True, read_data=False) as root:
        snapshot = _query_snapshot(api, root.value, include_streams=False)
        _assert_directory(snapshot, "observed root")
        return WindowsDirectoryIdentity(
            snapshot.final_path, snapshot.volume_serial, snapshot.file_id
        )


def read_windows_fixed_p0_packet_directory(
    packet_dir: Path | str,
    *,
    expected_root_final_path: str,
    expected_root_volume_serial: int,
    expected_root_file_id: str,
) -> WindowsFixedDirectoryRead:
    """Read the fixed P0 packet through simultaneously-held Windows handles.

    The three expected root identity values are mandatory caller inputs.  They
    must ultimately be bound by an external owner authorization before they can
    contribute to actual-P0 authority.
    """

    if not _IS_WINDOWS:
        raise P0WindowsFixedDirectoryError(
            "Windows fixed-directory validation is unavailable on this platform"
        )
    expected_final, expected_volume, expected_id = _validate_expected_identity(
        expected_final_path=expected_root_final_path,
        expected_volume_serial=expected_root_volume_serial,
        expected_file_id=expected_root_file_id,
    )
    from llm_batch.grounding.p0_actual_packet_contract import (
        CHILD_FILES,
        PACKET_MANIFEST_FILENAME,
    )

    expected_names = frozenset(
        {PACKET_MANIFEST_FILENAME, *(filename for _, filename, _ in CHILD_FILES)}
    )
    for name in expected_names:
        if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
            raise P0WindowsFixedDirectoryError("fixed member name is unsafe")

    api = _Win32()
    root_path, ancestors = _lexical_ancestor_paths(packet_dir)
    raw_by_name: dict[str, bytes] = {}
    file_receipts: list[dict[str, Any]] = []

    with ExitStack() as stack:
        ancestor_snapshots: list[tuple[str, _OwnedHandle, _ObjectSnapshot]] = []
        previous_ancestor: _ObjectSnapshot | None = None
        for index, path in enumerate(ancestors):
            handle = stack.enter_context(
                _open_handle(api, path, directory=True, read_data=False)
            )
            snapshot = _query_snapshot(api, handle.value, include_streams=False)
            _assert_directory(snapshot, f"ancestor {index}")
            if previous_ancestor is not None:
                if snapshot.volume_serial != previous_ancestor.volume_serial:
                    raise P0WindowsFixedDirectoryError(
                        "ancestor chain crosses a volume boundary"
                    )
                _assert_direct_final_path_descendant(
                    previous_ancestor.final_path,
                    snapshot.final_path,
                    f"ancestor {index}",
                )
            previous_ancestor = snapshot
            ancestor_snapshots.append((path, handle, snapshot))

        root = stack.enter_context(
            _open_handle(api, root_path, directory=True, read_data=False)
        )
        root_before = _query_snapshot(api, root.value, include_streams=False)
        _assert_directory(root_before, "packet root")
        if root_before.final_path.casefold() != expected_final.casefold():
            raise P0WindowsFixedDirectoryError("caller-pinned root final path mismatch")
        if root_before.volume_serial != expected_volume:
            raise P0WindowsFixedDirectoryError("caller-pinned root volume serial mismatch")
        if root_before.file_id != expected_id:
            raise P0WindowsFixedDirectoryError("caller-pinned root file ID mismatch")
        if not ancestor_snapshots:
            raise P0WindowsFixedDirectoryError(
                "packet root requires a pinned immediate parent"
            )
        immediate_parent = ancestor_snapshots[-1][2]
        if root_before.volume_serial != immediate_parent.volume_serial:
            raise P0WindowsFixedDirectoryError(
                "packet root crosses its pinned parent volume boundary"
            )
        _assert_direct_final_path_descendant(
            immediate_parent.final_path, root_before.final_path, "packet root"
        )

        inventory_before = _enumerate_directory(api, root.value)
        _validate_inventory(inventory_before, expected_names)

        opened: dict[str, tuple[_OwnedHandle, _ObjectSnapshot]] = {}
        seen_ids: set[str] = set()
        for name in sorted(expected_names):
            handle_path = root_before.final_path + "\\" + name
            handle = stack.enter_context(
                _open_handle(api, handle_path, directory=False, read_data=True)
            )
            before = _query_snapshot(api, handle.value, include_streams=True)
            _assert_regular_single_link(before, name)
            if before.final_path.casefold() != handle_path.casefold():
                raise P0WindowsFixedDirectoryError(
                    f"packet member final path escaped fixed root: {name}"
                )
            if before.volume_serial != root_before.volume_serial:
                raise P0WindowsFixedDirectoryError(
                    f"packet member volume differs from root: {name}"
                )
            _assert_entry_matches_snapshot(inventory_before[name], before, name)
            if before.file_id in seen_ids:
                raise P0WindowsFixedDirectoryError(
                    "fixed packet members must have unique file IDs"
                )
            seen_ids.add(before.file_id)
            opened[name] = (handle, before)

        total_expected = sum(before.standard[1] for _, before in opened.values())
        if not 0 <= total_expected <= _MAX_TOTAL_BYTES:
            raise P0WindowsFixedDirectoryError("fixed packet exceeds strict total byte limit")

        for name in sorted(expected_names):
            handle, before = opened[name]
            raw = _read_handle_exact(api, handle.value, before.standard[1], name)
            after = _query_snapshot(api, handle.value, include_streams=True)
            if not _snapshot_stable(before, after):
                raise P0WindowsFixedDirectoryError(
                    f"packet member identity/metadata changed while reading: {name}"
                )
            raw_by_name[name] = raw
            file_receipts.append(
                {
                    "name": name,
                    "final_path": before.final_path,
                    "volume_serial": str(before.volume_serial),
                    "file_id": before.file_id,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "number_of_links": before.standard[2],
                    "unnamed_stream_only": True,
                }
            )

        # Reopen the lexical root while the original root and every ancestor
        # handle are still held.  The second handle proves that the caller's
        # namespace still resolves to the pinned object, rather than merely
        # showing that the first handle continued to reference an old object.
        root_reopened = stack.enter_context(
            _open_handle(api, root_path, directory=True, read_data=False)
        )
        root_reopened_snapshot = _query_snapshot(
            api, root_reopened.value, include_streams=False
        )
        _assert_directory(root_reopened_snapshot, "reopened packet root")
        if not _snapshot_stable(root_before, root_reopened_snapshot):
            raise P0WindowsFixedDirectoryError(
                "reopened packet root does not match the pinned root identity"
            )
        inventory_after = _enumerate_directory(api, root_reopened.value)
        _validate_inventory(inventory_after, expected_names)
        if _inventory_projection(inventory_before) != _inventory_projection(inventory_after):
            raise P0WindowsFixedDirectoryError(
                "fixed directory inventory changed while handles were held"
            )

        root_after = _query_snapshot(api, root.value, include_streams=False)
        if not _snapshot_stable(root_before, root_after):
            raise P0WindowsFixedDirectoryError(
                "packet root identity/metadata changed while reading"
            )
        ancestor_chain: list[dict[str, Any]] = []
        for index, (lexical_path, handle, before) in enumerate(ancestor_snapshots):
            after = _query_snapshot(api, handle.value, include_streams=False)
            before_projection = _ancestor_namespace_projection(before)
            after_projection = _ancestor_namespace_projection(after)
            before_sha = _canonical_sha256(before_projection)
            after_sha = _canonical_sha256(after_projection)
            if before_sha != after_sha:
                raise P0WindowsFixedDirectoryError(
                    f"packet ancestor projection changed while reading: {index}"
                )
            ancestor_chain.append(
                {
                    "index": index,
                    "lexical_path": lexical_path,
                    "final_path": before.final_path,
                    "volume_serial": str(before.volume_serial),
                    "file_id": before.file_id,
                    "before_projection_sha256": before_sha,
                    "after_projection_sha256": after_sha,
                    "stable_projection_sha256": before_sha,
                    "before_after_projection_sha256": _canonical_sha256(
                        {"before": before_projection, "after": after_projection}
                    ),
                }
            )

    inventory_before_projection = _inventory_projection(inventory_before)
    inventory_after_projection = _inventory_projection(inventory_after)
    material = {
        "schema_version": WINDOWS_HANDLE_RECEIPT_SCHEMA,
        "platform": "win32",
        "root_final_path": root_before.final_path,
        "root_volume_serial": str(root_before.volume_serial),
        "root_file_id": root_before.file_id,
        "caller_pinned_root_identity_matched": True,
        "external_root_identity_pin_verified": False,
        "ancestor_handle_count": len(ancestors),
        "ancestor_chain": ancestor_chain,
        "ancestor_chain_sha256": _canonical_sha256(ancestor_chain),
        "root_direct_parent_component_boundary_verified": True,
        "member_handle_count": len(expected_names),
        "member_names": sorted(expected_names),
        "members": file_receipts,
        "inventory_before_sha256": _canonical_sha256(inventory_before_projection),
        "inventory_after_sha256": _canonical_sha256(inventory_after_projection),
        "exact_fixed_inventory_verified": True,
        "ancestor_root_no_reparse_verified": True,
        "member_no_reparse_verified": True,
        "member_single_link_verified": True,
        "member_unnamed_stream_only_verified": True,
        "directory_entry_open_handle_identity_verified": True,
        "final_descendant_path_verified": True,
        "same_volume_verified": True,
        "unique_member_file_ids_verified": True,
        "before_after_handle_metadata_verified": True,
        "root_namespace_reopen_verified": True,
        "handle_read_bytes_verified": True,
        "filesystem_handle_binding_verified": True,
        "filesystem_handle_trust_verified": False,
        "os_write_deny_verified": False,
        "runtime_noninterference_verified": False,
        "authority_journal_watch_bundle_verified": False,
        "external_owner_authority_verified": False,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }
    receipt = {**material, "receipt_sha256": _canonical_sha256(material)}
    return WindowsFixedDirectoryRead(dict(raw_by_name), receipt)


def bind_windows_fixed_packet_observation(
    observation: WindowsFixedDirectoryRead,
    *,
    expected_manifest_sha256: str,
    expected_origin: str,
) -> dict[str, Any]:
    """Bind one handle-captured observation to the pure packet validator.

    This helper performs no filesystem access.  It is intended for a
    supervisor that captures the fixed directory exactly once and then feeds
    the same in-memory bytes to all applicable pure validators.  Success is
    still only a bounded presented-observation binding, not external trust or
    actual-P0 authority.
    """

    if not isinstance(expected_manifest_sha256, str) or not _SHA256.fullmatch(
        expected_manifest_sha256
    ):
        raise P0WindowsFixedDirectoryError(
            "expected manifest SHA-256 must be 64 lowercase hexadecimal characters"
        )
    if not isinstance(observation, WindowsFixedDirectoryRead):
        raise P0WindowsFixedDirectoryError(
            "Windows fixed-directory observation has an invalid type"
        )
    if not isinstance(observation.raw_by_name, Mapping) or not isinstance(
        observation.receipt, Mapping
    ):
        raise P0WindowsFixedDirectoryError(
            "Windows fixed-directory observation is malformed"
        )
    for name, raw in observation.raw_by_name.items():
        if not isinstance(name, str) or not isinstance(raw, bytes):
            raise P0WindowsFixedDirectoryError(
                "Windows fixed-directory observation raw members are malformed"
            )

    handle_receipt = dict(observation.receipt)
    if handle_receipt.get("schema_version") != WINDOWS_HANDLE_RECEIPT_SCHEMA:
        raise P0WindowsFixedDirectoryError(
            "Windows handle receipt schema mismatch"
        )
    declared_handle_receipt_sha = handle_receipt.pop("receipt_sha256", None)
    from llm_batch.grounding.p0_actual_packet_contract import (
        PACKET_MANIFEST_FILENAME,
        validate_packet_bytes,
    )

    packet_receipt = validate_packet_bytes(
        observation.manifest_bytes,
        observation.child_bytes,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_origin=expected_origin,
    )
    try:
        packet_manifest = json.loads(observation.manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:  # pragma: no cover
        # The pure byte validator has already rejected this case; keep this
        # defensive branch fail-closed if its contract ever changes.
        raise P0WindowsFixedDirectoryError(
            "validated packet manifest could not be projected"
        ) from exc
    manifest_refs = packet_manifest.get("files")
    if not isinstance(manifest_refs, list):  # pragma: no cover - pure validator guard
        raise P0WindowsFixedDirectoryError(
            "validated packet manifest lacks a fixed file inventory"
        )
    ref_by_path: dict[str, Mapping[str, Any]] = {}
    for value in manifest_refs:
        if not isinstance(value, Mapping) or not isinstance(value.get("path"), str):
            raise P0WindowsFixedDirectoryError(
                "validated packet manifest contains an invalid file reference"
            )
        path = value["path"]
        if path in ref_by_path:
            raise P0WindowsFixedDirectoryError(
                "validated packet manifest contains duplicate file references"
            )
        ref_by_path[path] = value

    handle_members = observation.receipt.get("members")
    if not isinstance(handle_members, list):
        raise P0WindowsFixedDirectoryError(
            "Windows handle receipt lacks its member inventory"
        )
    handle_by_name: dict[str, Mapping[str, Any]] = {}
    for value in handle_members:
        if not isinstance(value, Mapping) or not isinstance(value.get("name"), str):
            raise P0WindowsFixedDirectoryError(
                "Windows handle receipt contains an invalid member"
            )
        name = value["name"]
        if name in handle_by_name:
            raise P0WindowsFixedDirectoryError(
                "Windows handle receipt contains duplicate members"
            )
        raw = observation.raw_by_name.get(name)
        if raw is None or value.get("bytes") != len(raw) or value.get(
            "sha256"
        ) != hashlib.sha256(raw).hexdigest():
            raise P0WindowsFixedDirectoryError(
                f"Windows handle receipt member bytes/hash mismatch: {name}"
            )
        handle_by_name[name] = value

    # Check member/raw diagnostics first to preserve the established precise
    # mismatch error, then authenticate the complete presented receipt.
    if (
        not isinstance(declared_handle_receipt_sha, str)
        or not _SHA256.fullmatch(declared_handle_receipt_sha)
        or declared_handle_receipt_sha != _canonical_sha256(handle_receipt)
    ):
        raise P0WindowsFixedDirectoryError(
            "Windows handle receipt self-hash mismatch"
        )

    actual_manifest_sha256 = hashlib.sha256(observation.manifest_bytes).hexdigest()
    if actual_manifest_sha256 != expected_manifest_sha256:
        raise P0WindowsFixedDirectoryError(
            "handle-read manifest does not match expected manifest SHA-256"
        )
    expected_member_names = {PACKET_MANIFEST_FILENAME, *ref_by_path}
    if set(handle_by_name) != expected_member_names:
        raise P0WindowsFixedDirectoryError(
            "handle receipt and packet manifest member names differ"
        )
    handle_projection: list[dict[str, Any]] = []
    packet_manifest_projection: list[dict[str, Any]] = []
    for name in sorted(expected_member_names):
        if name == PACKET_MANIFEST_FILENAME:
            role = "packet_manifest"
            expected_bytes = len(observation.manifest_bytes)
            expected_sha = expected_manifest_sha256
        else:
            reference = ref_by_path[name]
            role = reference.get("role")
            expected_bytes = reference.get("bytes")
            expected_sha = reference.get("sha256")
        handle_member = handle_by_name[name]
        handle_projection.append(
            {
                "role": role,
                "path": name,
                "bytes": handle_member.get("bytes"),
                "sha256": handle_member.get("sha256"),
            }
        )
        packet_manifest_projection.append(
            {
                "role": role,
                "path": name,
                "bytes": expected_bytes,
                "sha256": expected_sha,
            }
        )
    if handle_projection != packet_manifest_projection:
        raise P0WindowsFixedDirectoryError(
            "handle member inventory does not exactly match packet manifest references"
        )

    handle_declared_receipt_sha = observation.receipt.get("receipt_sha256")
    packet_declared_receipt_sha = packet_receipt.get("receipt_sha256")
    material = {
        "schema_version": WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA,
        "expected_manifest_sha256": expected_manifest_sha256,
        "windows_handle_receipt": dict(observation.receipt),
        "windows_handle_receipt_declared_receipt_sha256": handle_declared_receipt_sha,
        "windows_handle_receipt_full_canonical_sha256": _canonical_sha256(
            dict(observation.receipt)
        ),
        "packet_receipt": packet_receipt,
        "packet_receipt_declared_receipt_sha256": packet_declared_receipt_sha,
        "packet_receipt_full_canonical_sha256": _canonical_sha256(packet_receipt),
        "handle_member_inventory_projection": handle_projection,
        "handle_member_inventory_sha256": _canonical_sha256(handle_projection),
        "packet_manifest_fixed_file_inventory_projection": packet_manifest_projection,
        "packet_manifest_fixed_file_inventory_sha256": _canonical_sha256(
            packet_manifest_projection
        ),
        "handle_manifest_fixed_file_inventory_exact_match": True,
        "byte_inventory_binding_verified": True,
        "filesystem_handle_binding_verified": True,
        "filesystem_handle_trust_verified": False,
        "external_root_identity_pin_verified": False,
        "os_write_deny_verified": False,
        "runtime_noninterference_verified": False,
        "external_owner_authority_verified": False,
        "actual_authority_granted": False,
        "production_approval": False,
        "full_scan_approval": False,
        "p0_phase_exit": False,
        "action_applied": False,
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": "NO_GO_ACTUAL_P0_AUTHORITY_NOT_VERIFIED",
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }
    return {**material, "receipt_sha256": _canonical_sha256(material)}


def validate_windows_fixed_p0_packet_directory(
    packet_dir: Path | str,
    *,
    expected_root_final_path: str,
    expected_root_volume_serial: int,
    expected_root_file_id: str,
    expected_manifest_sha256: str,
    expected_origin: str,
) -> dict[str, Any]:
    """Handle-read the packet, then bind it to the pure byte validator."""

    # Preserve fail-close ordering: a malformed manifest pin is rejected
    # before any filesystem access, just as it was before bind extraction.
    if not isinstance(expected_manifest_sha256, str) or not _SHA256.fullmatch(
        expected_manifest_sha256
    ):
        raise P0WindowsFixedDirectoryError(
            "expected manifest SHA-256 must be 64 lowercase hexadecimal characters"
        )
    observation = read_windows_fixed_p0_packet_directory(
        packet_dir,
        expected_root_final_path=expected_root_final_path,
        expected_root_volume_serial=expected_root_volume_serial,
        expected_root_file_id=expected_root_file_id,
    )
    return bind_windows_fixed_packet_observation(
        observation,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_origin=expected_origin,
    )


__all__ = [
    "P0WindowsFixedDirectoryError",
    "WINDOWS_HANDLE_RECEIPT_SCHEMA",
    "WINDOWS_PACKET_VALIDATION_RECEIPT_SCHEMA",
    "WindowsDirectoryIdentity",
    "WindowsFixedDirectoryRead",
    "bind_windows_fixed_packet_observation",
    "observe_windows_directory_identity",
    "read_windows_fixed_p0_packet_directory",
    "validate_windows_fixed_p0_packet_directory",
]
