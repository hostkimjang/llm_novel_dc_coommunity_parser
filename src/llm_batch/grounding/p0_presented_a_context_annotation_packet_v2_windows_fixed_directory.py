"""Presented annotation packet V2 fixed-directory Windows validator.

The module owns its Win32 handle path and imports only the packet V2 producer and
producer-free parent. Success is a bounded local observation, never trust,
authenticity, authority, write denial, runtime safety, metrics, or approval.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct
from typing import Any, Mapping, Sequence

from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_contract as packet_v2
from llm_batch.grounding import p0_presented_a_context_annotation_packet_v2_parent_validator as packet_v2_parent


MEMORY_RECEIPT_SCHEMA = (
    "p0_presented_a_context_annotation_packet_v2_memory_binding_receipt_v1"
)
WINDOWS_HANDLE_RECEIPT_SCHEMA = (
    "p0_presented_a_context_annotation_packet_v2_windows_handle_receipt_v1"
)
WINDOWS_DIRECTORY_RECEIPT_SCHEMA = (
    "p0_presented_a_context_annotation_packet_v2_windows_directory_receipt_v1"
)
SAFE_HANDLE_PROJECTION_SCHEMA = (
    "p0_presented_a_context_annotation_packet_v2_windows_safe_handle_projection_v1"
)
PACKET_COMPONENT_MANIFEST_SHA256 = (
    "2a4b63518b8d80522469753191c9879af6f85f55828f28318a149911e564d59f"
)
FIXED_MEMBER_CONTRACT_SHA256 = (
    "37f3a34ab17c219065b81d9f2eb3d9a8876c5e32e12e7051ec30f3e5038385fc"
)
FIXED_MEMBER_CONTRACT = (
    ("packet_manifest", "p0_presented_a_context_annotation_packet_v2_manifest.json", "application/json", 1_000_000),
    ("source_scope", "presented_source_scope_v2.json", "application/json", 1_000_000),
    ("source_census", "presented_source_census_v2.jsonl", "application/x-ndjson", 64_000_000),
    ("source_frame", "presented_source_frame_v2.json", "application/json", 1_000_000),
    ("source_seed", "presented_source_seed_v2.json", "application/json", 64_000),
    ("source_plan", "presented_source_plan_v2.json", "application/json", 64_000_000),
    ("bridge_inventory", "presented_registry_capture_bridge_v1.jsonl", "application/x-ndjson", 16_777_216),
    ("a_scope", "presented_a_context_scope_v1.json", "application/json", 1_000_000),
    ("a_census", "presented_a_context_census_v1.jsonl", "application/x-ndjson", 64_000_000),
    ("a_frame", "presented_a_context_frame_v1.json", "application/json", 1_000_000),
    ("a_seed", "presented_a_context_seed_v1.json", "application/json", 64_000),
    ("a_plan", "presented_a_context_plan_v1.json", "application/json", 64_000_000),
    ("subject_rows", "presented_a_context_annotation_subject_v2.jsonl", "application/x-ndjson", 1_000_000),
    ("subject_precommit", "presented_a_context_annotation_subject_v2_precommit.json", "application/json", 1_000_000),
    ("target_rows", "presented_a_context_annotation_event_v2_targets.jsonl", "application/x-ndjson", 1_000_000),
    ("target_precommit", "presented_a_context_annotation_event_v2_target_precommit.json", "application/json", 1_000_000),
)
MEMBER_ROLES = tuple(value[0] for value in FIXED_MEMBER_CONTRACT)
CHILD_ROLES = MEMBER_ROLES[1:]
MEMBER_RAW_CAPS = {value[0]: value[3] for value in FIXED_MEMBER_CONTRACT}
FIXED_MEMBER_PATHS = {value[0]: value[1] for value in FIXED_MEMBER_CONTRACT}
AGGREGATE_MEMBER_CAP_BYTES = 281_905_216


_IS_WINDOWS = os.name == "nt"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FILE_ID = re.compile(r"^[0-9a-f]{32}$")
_ASCII_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)$")
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
_FILE_CASE_SENSITIVE_INFO_CLASS = 23
_FILE_CS_FLAG_CASE_SENSITIVE_DIR = 0x00000001

_FILE_NAME_NORMALIZED = 0x0
_VOLUME_NAME_GUID = 0x1

_ERROR_NO_MORE_FILES = 18
_ERROR_INSUFFICIENT_BUFFER = 122
_ERROR_MORE_DATA = 234
_ERROR_NOT_SUPPORTED = 50
_ERROR_INVALID_PARAMETER = 87
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_MAX_FINAL_PATH_CHARS = 32768
_MAX_STREAM_BUFFER = 1024 * 1024
_MAX_SINGLE_FILE_BYTES = 64_000_000
_MAX_TOTAL_BYTES = 281_905_216
_READ_CHUNK_BYTES = 1024 * 1024
_DIRECTORY_BUFFER_BYTES = 64 * 1024


class P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(ValueError):
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


class _FILE_CASE_SENSITIVE_INFO(ctypes.Structure):
    _fields_ = [("Flags", wintypes.DWORD)]


@dataclass(frozen=True)
class WindowsDirectoryIdentity:
    """Observed root identity; observation alone is not an authority pin."""

    final_path: str
    volume_serial: int
    file_id: str


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
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
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
                    raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
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


def _winerror(label: str) -> P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError:
    code = ctypes.get_last_error()
    return P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} failed with Windows error {code}")


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
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    "final path is not a local volume-GUID path"
                )
            return value.rstrip("\\")
        size = used + 1
    raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("final path exceeds strict size limit")


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
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("file stream inventory exceeds strict limit")

    result: list[tuple[str, int, int]] = []
    offset = 0
    while True:
        if offset + 24 > size:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("malformed FILE_STREAM_INFO buffer")
        next_offset, name_bytes = struct.unpack_from("<II", buffer.raw, offset)
        stream_size, allocation_size = struct.unpack_from("<qq", buffer.raw, offset + 8)
        end = offset + 24 + name_bytes
        if name_bytes % 2 or end > size:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("malformed file stream name")
        try:
            name = buffer.raw[offset + 24 : end].decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("invalid file stream name") from exc
        result.append((name, int(stream_size), int(allocation_size)))
        if next_offset == 0:
            break
        if next_offset < 24 or next_offset % 8 or offset + next_offset >= size:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("malformed file stream offset")
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
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} must not be a reparse point")


def _assert_directory(snapshot: _ObjectSnapshot, label: str) -> None:
    _assert_no_reparse(snapshot, label)
    if not snapshot.standard[4] or not snapshot.basic[4] & _FILE_ATTRIBUTE_DIRECTORY:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} must be a directory")
    if snapshot.standard[3]:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} is delete-pending")


def _assert_not_case_sensitive_directory(api: _Win32, handle: int, label: str) -> None:
    """Reject per-directory case sensitivity when the filesystem exposes it."""

    value = _FILE_CASE_SENSITIVE_INFO()
    if api.GetFileInformationByHandleEx(
        handle,
        _FILE_CASE_SENSITIVE_INFO_CLASS,
        ctypes.byref(value),
        ctypes.sizeof(value),
    ):
        if int(value.Flags) & _FILE_CS_FLAG_CASE_SENSITIVE_DIR:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"{label} must not be case-sensitive"
            )
        return
    error = ctypes.get_last_error()
    if error not in {_ERROR_NOT_SUPPORTED, _ERROR_INVALID_PARAMETER}:
        raise _winerror(f"query case-sensitive directory state for {label}")


def _assert_regular_single_link(snapshot: _ObjectSnapshot, label: str) -> None:
    _assert_no_reparse(snapshot, label)
    if snapshot.standard[4] or snapshot.basic[4] & _FILE_ATTRIBUTE_DIRECTORY:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} must be a regular file")
    if snapshot.standard[3]:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} is delete-pending")
    if snapshot.standard[2] != 1:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} hardlink count must be exactly one")
    if len(snapshot.streams) != 1 or snapshot.streams[0][0] != "::$DATA":
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            f"{label} must contain only the unnamed data stream"
        )
    if snapshot.streams[0][1] != snapshot.standard[1]:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} stream size mismatch")


def _normalise_final_path(value: str, label: str) -> str:
    if not isinstance(value, str) or not _VOLUME_GUID_PATH.fullmatch(
        value.rstrip("\\")
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            f"{label} must be an absolute Windows volume-GUID path"
        )
    result = value.rstrip("\\")
    if not result or "\x00" in result:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} is invalid")
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
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("expected root volume serial is invalid")
    if not isinstance(expected_file_id, str) or not _FILE_ID.fullmatch(expected_file_id):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "expected root file ID must be 32 lowercase hexadecimal characters"
        )
    return final_path, expected_volume_serial, expected_file_id


def _lexical_ancestor_paths(packet_dir: Path | str) -> tuple[str, tuple[str, ...]]:
    raw = os.fspath(packet_dir)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("packet directory path is invalid")
    if not os.path.isabs(raw):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("packet directory path must be absolute")
    absolute = os.path.abspath(raw)
    drive, tail = os.path.splitdrive(absolute)
    if not drive or drive.startswith("\\\\"):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("packet directory must be on a local drive")
    parts = [part for part in tail.replace("/", "\\").split("\\") if part]
    if not parts:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("volume root cannot be the packet directory")
    current = drive + "\\"
    built: list[str] = [current]
    for part in parts:
        if (
            part in {".", ".."}
            or ":" in part
            or part.endswith(".")
            or part.endswith(" ")
        ):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("packet path component is invalid")
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
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("malformed directory inventory buffer")
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
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("malformed directory entry name")
            try:
                name = buffer.raw[offset + 88 : end].decode("utf-16-le")
            except UnicodeDecodeError as exc:
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("invalid directory entry name") from exc
            if name not in {".", ".."}:
                folded = name.casefold()
                if name in values or folded in casefolded:
                    raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
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
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("malformed directory entry offset")
            offset += next_offset
    return values


def _inventory_projection(values: Mapping[str, _DirectoryEntry]) -> list[dict[str, Any]]:
    return [values[name].stable_projection() for name in sorted(values)]


def _validate_inventory(
    values: Mapping[str, _DirectoryEntry], expected_names: frozenset[str]
) -> None:
    if set(values) != expected_names:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError("fixed directory inventory mismatch")
    for name, entry in values.items():
        if entry.attributes & (_FILE_ATTRIBUTE_DIRECTORY | _FILE_ATTRIBUTE_REPARSE_POINT):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"fixed packet member is not a regular non-reparse file: {name}"
            )
        if entry.reparse_tag:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"fixed packet member has a reparse tag: {name}"
            )


def _read_handle_exact(api: _Win32, handle: int, expected_size: int, label: str) -> bytes:
    if not 0 <= expected_size <= _MAX_SINGLE_FILE_BYTES:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} exceeds strict byte limit")
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
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} returned a short/invalid read")
        chunks.append(buffer.raw[:count])
        remaining -= count

    probe = ctypes.create_string_buffer(1)
    probe_count = wintypes.DWORD()
    if not api.ReadFile(handle, probe, 1, ctypes.byref(probe_count), None):
        raise _winerror(f"probe EOF for {label}")
    if probe_count.value != 0:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(f"{label} grew while being read")
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
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            f"{label} is outside its pinned parent final path"
        )
    remainder = child_final_path[len(prefix) :]
    if not remainder or "\\" in remainder or "/" in remainder:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
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
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            f"directory-entry/open-handle metadata mismatch for {name}: {mismatched}"
        )


_DENIAL_FIELDS = (
    "filesystem_handle_binding_verified",
    "filesystem_handle_trust_verified",
    "external_root_identity_pin_verified",
    "root_identity_authority_verified",
    "external_manifest_pin_trust_verified",
    "upstream_code_identity_verified",
    "same_process_monkeypatch_resistance_verified",
    "external_owner_authority_verified",
    "authenticity_verified",
    "os_write_deny_verified",
    "runtime_noninterference_verified",
    "preauthorization_verified",
    "supervisor_execution_verified",
    "trusted_time_verified",
    "trusted_revocation_verified",
    "write_authority_verified",
    "actual_authority_granted",
    "descriptive_metrics_allowed",
    "inferential_metrics_allowed",
    "semantic_metrics_allowed",
    "complete_case_metrics_allowed",
    "production_approval",
    "full_scan_approval",
    "p0_phase_exit",
    "action_applied",
)
_HANDLE_TRUE_FIELDS = (
    "caller_pinned_root_identity_matched",
    "exact_fixed_inventory_verified",
    "ancestor_root_no_reparse_verified",
    "case_sensitive_directory_rejected_if_observable",
    "member_no_reparse_verified",
    "member_single_link_verified",
    "member_unnamed_stream_only_verified",
    "directory_entry_open_handle_identity_verified",
    "final_descendant_path_verified",
    "same_volume_verified",
    "unique_member_file_ids_verified",
    "before_after_handle_metadata_verified",
    "namespace_reopen_verified",
    "all_member_handles_open_before_first_read",
    "handles_held_across_packet_validation",
    "local_byte_handle_consistency_verified",
)
_HANDLE_MEMBER_FIELDS = (
    "role", "path", "media_type", "max_bytes", "final_path",
    "volume_serial", "file_id", "bytes", "sha256", "number_of_links",
    "unnamed_stream_only", "before_projection_sha256",
    "after_projection_sha256", "reopen_projection_sha256",
)
_ANCESTOR_EVIDENCE_FIELDS = (
    "index", "lexical_path", "before_projection_sha256",
    "after_projection_sha256", "reopen_projection_sha256",
)
_HANDLE_EVIDENCE_FIELDS = (
    "windows_component_manifest_sha256",
    "packet_component_manifest_sha256",
    "fixed_member_contract_sha256",
    "member_raw_caps_sha256",
    "expected_member_raw_pin_set_sha256",
    "member_sequence",
    "member_sequence_sha256",
    "total_member_bytes",
    "aggregate_member_cap_bytes",
    "inventory_before_sha256",
    "inventory_after_sha256",
    "ancestor_chain_sha256",
    "root_before_projection_sha256",
    "root_after_projection_sha256",
    "root_reopen_projection_sha256",
    "member_evidence_sha256",
)
_HANDLE_RECEIPT_FIELDS = (
    "schema_version", "platform", "root_final_path", "root_volume_serial",
    "root_file_id", "ancestor_handle_count", "member_handle_count",
    *_HANDLE_EVIDENCE_FIELDS, "members", "ancestor_chain",
    *_HANDLE_TRUE_FIELDS, *_DENIAL_FIELDS, "operational_effect", "gate_status",
    "receipt_hash_scope", "receipt_sha256",
)
_SAFE_HANDLE_PROJECTION_FIELDS = (
    "schema_version", "handle_receipt_sha256", "root_final_path",
    "root_volume_serial", "root_file_id", "ancestor_handle_count",
    "member_handle_count", *_HANDLE_EVIDENCE_FIELDS,
    "handles_held_across_packet_validation",
    "local_byte_handle_consistency_verified", *_DENIAL_FIELDS,
    "receipt_sha256",
)
_COMMON_BINDING_FIELDS = (
    "schema_version", "validation_mode", "windows_component_manifest_sha256",
    "packet_component_manifest_sha256",
    "fixed_member_contract_sha256", "fixed_member_count",
    "aggregate_member_cap_bytes", "expected_member_raw_sha256",
    "validated_member_raw_sha256", "expected_member_raw_pin_set_sha256",
    "producer_manifest_validated", "producer_parent_validated",
    "producer_parent_receipt_sha256", "producer_parent_receipt_full_sha256",
    "independent_target_parent_receipt_sha256",
    "independent_target_parent_receipt_full_sha256",
    "packet_parent_execution_count",
    "independent_target_parent_execution_count",
    "total_target_parent_execution_count",
    "target_parent_single_execution_claimed",
    "byte_inventory_binding_verified",
    "handles_held_across_packet_validation",
    "local_byte_handle_consistency_verified", *_DENIAL_FIELDS,
    "operational_effect", "gate_status", "receipt_hash_scope", "receipt_sha256",
)
MEMORY_RECEIPT_FIELDS = _COMMON_BINDING_FIELDS
WINDOWS_DIRECTORY_RECEIPT_FIELDS = (
    *_COMMON_BINDING_FIELDS[:-1], "root_final_path", "root_volume_serial",
    "root_file_id", "ancestor_handle_count", "member_handle_count",
    "handle_safe_projection", "handle_safe_projection_sha256",
    "receipt_sha256",
)

_PARENT_RECEIPT_FIELDS = (
    "schema_version", "expected_component_manifest_sha256",
    "component_manifest_parity_verified", "validation_architecture",
    "producer_free_composed_parent_verified", "target_parent_module",
    "target_component_manifest_sha256", "target_parent_executed",
    "target_parent_receipt_sha256", "target_parent_receipt_full_sha256",
    "target_replay_delegated", "target_replay_locally_verified",
    "packet_envelope_independently_replayed", "validated_member_raw_sha256",
    "validated_member_raw_pin_set_sha256", "fixed_member_contract_sha256",
    "packet_id", "packet_manifest_artifact_sha256",
    "packet_manifest_raw_sha256", "response_schema_commitment_sha256",
    "input_raw_artifact_count", "output_raw_artifact_count",
    "total_bound_raw_artifact_count", "fixed_child_count",
    "fixed_member_count", "source_selected_count", "bridge_count",
    "a_selected_count", "subject_count", "target_count",
    "annotation_opportunity_count", "planned_primary_opportunity_count",
    "unstarted_target_count", "journal_genesis_commitment_count",
    "source_profile_counts", "generic_subject_count", "generic_target_count",
    "review_assignment_count", "reviewer_count", "annotation_event_count",
    "primary_annotation_event_count", "recheck_annotation_event_count",
    "journal_head_count", "annotation_result_count",
    "actual_human_review_count", "actual_source_credit_count",
    "actual_a_context_review_count", "actual_a_context_credit_count",
    "gold_count", "metric_eligible_target_count", "terminal_status_counts",
    "statistical_denominator_contribution", "metric_status",
    "iid_independence_assumed", "future_inferential_cluster_unit",
    "target_precommitted_at", "packet_created_at",
    "target_precommit_strictly_precedes_packet_manifest_verified",
    "event_or_result_child_allowed", "labels_observed", "responses_observed",
    "semantic_truth_fields_used", "annotation_started",
    "target_wiring_applied", "journal_wiring_applied",
    "event_wiring_applied", "result_wiring_applied",
    "reviewer_identity_bound", "reviewer_assignment_bound",
    "guideline_authority_verified", "actual_source_evidence_verified",
    "actual_a_context_evidence_verified", "actual_authority_granted",
    "trusted_time_verified", "trusted_revocation_verified",
    "durable_predecessor_verified", "append_only_journal_verified",
    "filesystem_handle_binding_verified", "portable_directory_binding_verified",
    "preauthorization_verified", "supervisor_execution_verified",
    "os_write_deny_verified", "runtime_noninterference_verified",
    "write_authority_verified", "descriptive_metrics_allowed",
    "inferential_metrics_allowed", "semantic_metrics_allowed",
    "complete_case_metrics_allowed", "production_approval",
    "full_scan_approval", "p0_phase_exit", "action_applied",
    "upstream_code_identity_verified",
    "same_process_monkeypatch_resistance_verified", "producer_code_imported",
    "predecessor_subject_parent_receipt_value_independently_verified",
    "operational_effect", "gate_status", "receipt_sha256",
)
_PARENT_TRUE_FIELDS = (
    "component_manifest_parity_verified",
    "producer_free_composed_parent_verified",
    "target_parent_executed",
    "target_replay_delegated",
    "packet_envelope_independently_replayed",
    "target_precommit_strictly_precedes_packet_manifest_verified",
)
_PARENT_FALSE_FIELDS = (
    "target_replay_locally_verified", "iid_independence_assumed",
    "event_or_result_child_allowed", "labels_observed", "responses_observed",
    "semantic_truth_fields_used", "annotation_started",
    "target_wiring_applied", "journal_wiring_applied",
    "event_wiring_applied", "result_wiring_applied",
    "reviewer_identity_bound", "reviewer_assignment_bound",
    "guideline_authority_verified", "actual_source_evidence_verified",
    "actual_a_context_evidence_verified", "actual_authority_granted",
    "trusted_time_verified", "trusted_revocation_verified",
    "durable_predecessor_verified", "append_only_journal_verified",
    "filesystem_handle_binding_verified", "portable_directory_binding_verified",
    "preauthorization_verified", "supervisor_execution_verified",
    "os_write_deny_verified", "runtime_noninterference_verified",
    "write_authority_verified", "descriptive_metrics_allowed",
    "inferential_metrics_allowed", "semantic_metrics_allowed",
    "complete_case_metrics_allowed", "production_approval",
    "full_scan_approval", "p0_phase_exit", "action_applied",
    "upstream_code_identity_verified",
    "same_process_monkeypatch_resistance_verified", "producer_code_imported",
    "predecessor_subject_parent_receipt_value_independently_verified",
)
_PARENT_INTEGER_FIELDS = (
    "input_raw_artifact_count", "output_raw_artifact_count",
    "total_bound_raw_artifact_count", "fixed_child_count",
    "fixed_member_count", "source_selected_count", "bridge_count",
    "a_selected_count", "subject_count", "target_count",
    "annotation_opportunity_count", "planned_primary_opportunity_count",
    "unstarted_target_count", "journal_genesis_commitment_count",
    "generic_subject_count", "generic_target_count", "review_assignment_count",
    "reviewer_count", "annotation_event_count",
    "primary_annotation_event_count", "recheck_annotation_event_count",
    "journal_head_count", "annotation_result_count",
    "actual_human_review_count", "actual_source_credit_count",
    "actual_a_context_review_count", "actual_a_context_credit_count",
    "gold_count", "metric_eligible_target_count",
)
_PARENT_ZERO_FIELDS = (
    "review_assignment_count", "reviewer_count", "annotation_event_count",
    "primary_annotation_event_count", "recheck_annotation_event_count",
    "journal_head_count", "annotation_result_count",
    "actual_human_review_count", "actual_source_credit_count",
    "actual_a_context_review_count", "actual_a_context_credit_count",
    "gold_count", "metric_eligible_target_count",
)
_PARENT_DICT_FIELDS = (
    "validated_member_raw_sha256", "source_profile_counts",
    "terminal_status_counts",
)
_PARENT_BOOL_FIELDS = (*_PARENT_TRUE_FIELDS, *_PARENT_FALSE_FIELDS)
_PARENT_STRING_FIELDS = tuple(
    field for field in _PARENT_RECEIPT_FIELDS
    if field not in _PARENT_BOOL_FIELDS
    and field not in _PARENT_INTEGER_FIELDS
    and field not in _PARENT_DICT_FIELDS
)
MEMBER_SEQUENCE = MEMBER_ROLES
MEMBER_RAW_CAPS_SHA256 = _canonical_sha256(MEMBER_RAW_CAPS)
PUBLIC_APIS = (
    "bind_presented_a_context_annotation_packet_v2_memory",
    "observe_presented_a_context_annotation_packet_v2_windows_directory_identity",
    "validate_presented_a_context_annotation_packet_v2_windows_directory",
)
COMPONENT_MANIFEST = {
    "component":
        "p0_presented_a_context_annotation_packet_v2_windows_fixed_directory",
    "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
    "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
    "fixed_member_contract": FIXED_MEMBER_CONTRACT,
    "member_roles": MEMBER_ROLES,
    "member_raw_caps": MEMBER_RAW_CAPS,
    "member_raw_caps_sha256": MEMBER_RAW_CAPS_SHA256,
    "aggregate_member_cap_bytes": AGGREGATE_MEMBER_CAP_BYTES,
    "schemas": {
        "memory_receipt": MEMORY_RECEIPT_SCHEMA,
        "windows_handle_receipt": WINDOWS_HANDLE_RECEIPT_SCHEMA,
        "windows_directory_receipt": WINDOWS_DIRECTORY_RECEIPT_SCHEMA,
        "safe_handle_projection": SAFE_HANDLE_PROJECTION_SCHEMA,
    },
    "receipt_fields": {
        "memory": MEMORY_RECEIPT_FIELDS,
        "windows_handle": _HANDLE_RECEIPT_FIELDS,
        "windows_directory": WINDOWS_DIRECTORY_RECEIPT_FIELDS,
        "safe_handle_projection": _SAFE_HANDLE_PROJECTION_FIELDS,
        "packet_parent": _PARENT_RECEIPT_FIELDS,
    },
    "bounded_true_fields": _HANDLE_TRUE_FIELDS,
    "denial_fields": _DENIAL_FIELDS,
    "validation_call_architecture": {
        "packet_v2_producer_validation_count": 1,
        "packet_parent_validation_count": 1,
        "independent_target_parent_validation_count": 1,
        "target_parent_total_execution_count": 2,
        "target_parent_single_execution_claimed": False,
        "same_process_monkeypatch_resistance_verified": False,
    },
    "public_apis": PUBLIC_APIS,
    "serialized_handle_receipt_public_input_allowed": False,
    "filesystem_handle_trust": False,
    "authority": "NONE",
}
COMPONENT_MANIFEST_SHA256 = _canonical_sha256(COMPONENT_MANIFEST)


def _assert_fixed_drift_pins() -> None:
    if (
        packet_v2.COMPONENT_MANIFEST_SHA256 != PACKET_COMPONENT_MANIFEST_SHA256
        or packet_v2_parent.EXPECTED_COMPONENT_MANIFEST_SHA256
        != PACKET_COMPONENT_MANIFEST_SHA256
        or packet_v2.FIXED_MEMBER_CONTRACT_SHA256
        != FIXED_MEMBER_CONTRACT_SHA256
        or packet_v2_parent.FIXED_MEMBER_CONTRACT_SHA256
        != FIXED_MEMBER_CONTRACT_SHA256
        or packet_v2.FIXED_MEMBER_CONTRACT != FIXED_MEMBER_CONTRACT
        or packet_v2_parent.FIXED_MEMBER_CONTRACT != FIXED_MEMBER_CONTRACT
        or tuple(packet_v2.MEMBER_ROLES) != MEMBER_ROLES
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet V2 component or fixed-member contract drift pin mismatch"
        )


def _preflight_pins(expected_member_raw_sha256: Mapping[str, str]) -> dict[str, str]:
    if (
        type(expected_member_raw_sha256) is not dict
        or tuple(expected_member_raw_sha256) != MEMBER_ROLES
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "expected member SHA map must be the exact ordered 16-role inventory"
        )
    copied = dict(expected_member_raw_sha256)
    for role in MEMBER_ROLES:
        value = copied[role]
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"expected member SHA is invalid: {role}"
            )
    return copied


def _preflight_raws(
    manifest_raw: bytes,
    child_raw_by_role: Mapping[str, bytes],
    expected_member_raw_sha256: Mapping[str, str],
) -> tuple[dict[str, bytes], dict[str, str]]:
    _assert_fixed_drift_pins()
    pins = _preflight_pins(expected_member_raw_sha256)
    if type(child_raw_by_role) is not dict or tuple(child_raw_by_role) != CHILD_ROLES:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "child raw map must be the exact ordered 15-role inventory"
        )
    all_raws = {"packet_manifest": manifest_raw, **dict(child_raw_by_role)}
    total = 0
    for role in MEMBER_ROLES:
        raw = all_raws[role]
        if type(raw) is not bytes:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"{role} must be exact bytes"
            )
        if len(raw) > MEMBER_RAW_CAPS[role]:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"{role} exceeds its fixed role cap before hash/decode"
            )
        total += len(raw)
    if total > AGGREGATE_MEMBER_CAP_BYTES:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet exceeds aggregate cap before hash/decode"
        )
    return all_raws, pins


def _validated_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            f"{label} could not be projected"
        ) from exc
    if (
        type(value) is not dict
        or raw != packet_v2.canonical_file_bytes(value)
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            f"{label} projection is not canonical"
        )
    return value


def _strict_parent_receipt(
    value: Any,
    expected_member_raw_sha256: Mapping[str, str],
    *,
    manifest: Mapping[str, Any],
    target_precommit: Mapping[str, Any],
    expected_target_parent_receipt_sha256: str,
    expected_target_parent_receipt_full_sha256: str,
) -> dict[str, Any]:
    if (
        type(expected_target_parent_receipt_sha256) is not str
        or _SHA256.fullmatch(expected_target_parent_receipt_sha256) is None
        or type(expected_target_parent_receipt_full_sha256) is not str
        or _SHA256.fullmatch(expected_target_parent_receipt_full_sha256) is None
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "independent target parent hashes are invalid"
        )
    if (
        type(value) is not dict
        or tuple(value) != _PARENT_RECEIPT_FIELDS
        or any(type(key) is not str for key in value)
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent receipt exact ordered fields mismatch"
        )

    # Plain types are checked before self-hash or semantic comparisons so
    # bool/int confusion and scalar/container subclasses cannot hide behind a
    # correctly resealed JSON value.
    for field in _PARENT_STRING_FIELDS:
        if type(value[field]) is not str:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"packet parent receipt string type mismatch: {field}"
            )
    for field in _PARENT_INTEGER_FIELDS:
        if type(value[field]) is not int:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"packet parent receipt integer type mismatch: {field}"
            )
    for field in _PARENT_BOOL_FIELDS:
        if type(value[field]) is not bool:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"packet parent receipt boolean type mismatch: {field}"
            )
    for field in _PARENT_DICT_FIELDS:
        if type(value[field]) is not dict:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"packet parent receipt mapping type mismatch: {field}"
            )

    validated_pins = value["validated_member_raw_sha256"]
    if (
        tuple(validated_pins) != MEMBER_ROLES
        or any(type(key) is not str for key in validated_pins)
        or any(
            type(validated_pins[role]) is not str
            or _SHA256.fullmatch(validated_pins[role]) is None
            for role in MEMBER_ROLES
        )
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent validated-member map type/order mismatch"
        )
    profile_counts = value["source_profile_counts"]
    if (
        tuple(profile_counts) != tuple(packet_v2.SOURCE_PROFILES)
        or any(type(key) is not str for key in profile_counts)
        or any(type(item) is not int for item in profile_counts.values())
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent source-profile map type/order mismatch"
        )
    terminal_counts = value["terminal_status_counts"]
    if (
        tuple(terminal_counts) != ("JUDGED", "UNJUDGED", "UNAVAILABLE")
        or any(type(key) is not str for key in terminal_counts)
        or any(type(item) is not int for item in terminal_counts.values())
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent terminal map type/order mismatch"
        )

    receipt = dict(value)
    declared = receipt.pop("receipt_sha256")
    if (
        _SHA256.fullmatch(declared) is None
        or declared != _canonical_sha256(receipt)
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent receipt self-hash mismatch"
        )
    for field in _PARENT_STRING_FIELDS:
        if field.endswith("_sha256") and _SHA256.fullmatch(value[field]) is None:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"packet parent SHA field malformed: {field}"
            )

    expected_counts = {
        "input_raw_artifact_count": 13,
        "output_raw_artifact_count": 2,
        "total_bound_raw_artifact_count": 15,
        "fixed_child_count": 15,
        "fixed_member_count": 16,
        "source_selected_count": 40,
        "bridge_count": 40,
        "a_selected_count": 20,
        "subject_count": 20,
        "target_count": 20,
        "annotation_opportunity_count": 20,
        "planned_primary_opportunity_count": 20,
        "unstarted_target_count": 20,
        "journal_genesis_commitment_count": 20,
        "generic_subject_count": 5,
        "generic_target_count": 5,
        **{field: 0 for field in _PARENT_ZERO_FIELDS},
    }
    if any(value[field] != expected for field, expected in expected_counts.items()):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent fixed count semantics mismatch"
        )
    if any(value[field] is not True for field in _PARENT_TRUE_FIELDS):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent required-true semantics mismatch"
        )
    if any(value[field] is not False for field in _PARENT_FALSE_FIELDS):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent required-false semantics mismatch"
        )

    expected_profiles = {
        "OFFICIAL_STRUCTURED": 5,
        "COMMUNITY_STRUCTURED": 5,
        "MEDIA_OCR": 5,
        "GENERIC_FALLBACK": 5,
    }
    expected_terminal = {"JUDGED": 0, "UNJUDGED": 0, "UNAVAILABLE": 0}
    if (
        profile_counts != expected_profiles
        or terminal_counts != expected_terminal
        or type(manifest.get("source_profile_counts")) is not dict
        or tuple(manifest["source_profile_counts"])
        != tuple(sorted(expected_profiles))
        or manifest["source_profile_counts"] != expected_profiles
        or type(manifest.get("terminal_status_counts")) is not dict
        or tuple(manifest["terminal_status_counts"])
        != tuple(sorted(expected_terminal))
        or manifest["terminal_status_counts"] != expected_terminal
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent taxonomy map semantics mismatch"
        )
    if any(
        type(manifest.get(field)) is not int
        or manifest[field] != value[field]
        for field in _PARENT_INTEGER_FIELDS
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent count/manifest cross-binding mismatch"
        )

    target_time = target_precommit.get("precommitted_at")
    packet_time = manifest.get("created_at")
    if type(target_time) is not str or type(packet_time) is not str:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet chronology source types mismatch"
        )
    try:
        target_dt = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
        packet_dt = datetime.fromisoformat(packet_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet chronology parse failed"
        ) from exc
    if target_dt >= packet_dt:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet chronology cross-check failed"
        )

    expected_semantics = {
        "schema_version":
            "p0_presented_a_context_annotation_packet_v2_parent_receipt_v1",
        "expected_component_manifest_sha256":
            PACKET_COMPONENT_MANIFEST_SHA256,
        "validation_architecture": "PRODUCER_FREE_COMPOSED_PARENT",
        "target_parent_module":
            "llm_batch.grounding.p0_presented_a_context_annotation_event_v2_target_precommit_parent_validator",
        "target_component_manifest_sha256":
            packet_v2.TARGET_COMPONENT_MANIFEST_SHA256,
        "target_parent_receipt_sha256":
            expected_target_parent_receipt_sha256,
        "target_parent_receipt_full_sha256":
            expected_target_parent_receipt_full_sha256,
        "validated_member_raw_sha256": dict(expected_member_raw_sha256),
        "validated_member_raw_pin_set_sha256":
            _canonical_sha256(dict(expected_member_raw_sha256)),
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "packet_id": manifest.get("packet_id"),
        "packet_manifest_artifact_sha256": manifest.get("artifact_sha256"),
        "packet_manifest_raw_sha256":
            expected_member_raw_sha256["packet_manifest"],
        "response_schema_commitment_sha256":
            manifest.get("response_schema_commitment_sha256"),
        "source_profile_counts": expected_profiles,
        "terminal_status_counts": expected_terminal,
        "statistical_denominator_contribution": "NONE",
        "metric_status": "METRICS_NOT_ESTIMABLE_PRE_RESULT_PACKET_ONLY",
        "future_inferential_cluster_unit":
            "UPSTREAM_SOURCE_FRAME_CANDIDATE_ID",
        "target_precommitted_at": target_time,
        "packet_created_at": packet_time,
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status":
            "PRESENTED_A_CONTEXT_ANNOTATION_PACKET_V2_COMPOSED_PARENT_PASS_ALL_AUTHORITY_NO_GO",
    }
    if any(value[field] != expected for field, expected in expected_semantics.items()):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet parent dynamic/fixed semantics mismatch"
        )
    return dict(value)


def _validate_packet_raws(
    all_raws: Mapping[str, bytes], expected_member_raw_sha256: Mapping[str, str]
) -> dict[str, Any]:
    actual = {role: hashlib.sha256(all_raws[role]).hexdigest() for role in MEMBER_ROLES}
    if actual != dict(expected_member_raw_sha256):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "caller-pinned member raw SHA mismatch"
        )
    children = {role: all_raws[role] for role in CHILD_ROLES}
    try:
        child_pins = {
            role: expected_member_raw_sha256[role] for role in CHILD_ROLES
        }
        independent_target_receipt = (
            packet_v2_parent.target_parent.validate_target_precommit_against_raw_inputs(
                target_rows_raw=all_raws["target_rows"],
                target_precommit_raw=all_raws["target_precommit"],
                subject_rows_raw=all_raws["subject_rows"],
                subject_precommit_raw=all_raws["subject_precommit"],
                expected_raw_sha256=child_pins,
                **{role: all_raws[role] for role in CHILD_ROLES[:11]},
            )
        )
        independent_target_receipt = packet_v2_parent._target_receipt(
            independent_target_receipt, child_pins
        )
        independent_target_declared_sha = independent_target_receipt[
            "receipt_sha256"
        ]
        independent_target_full_sha = packet_v2_parent._digest(
            independent_target_receipt
        )
        manifest = packet_v2.validate_manifest_bytes(
            all_raws["packet_manifest"], children
        )
        target_precommit = _validated_object(
            all_raws["target_precommit"], "target precommit"
        )
        parent_receipt = packet_v2_parent.validate_packet_manifest_against_raw_inputs(
            manifest_raw=all_raws["packet_manifest"],
            expected_member_raw_sha256=dict(expected_member_raw_sha256),
            **children,
        )
    except (
        packet_v2.P0PresentedAContextAnnotationPacketV2Error,
        packet_v2_parent.P0PresentedAContextAnnotationPacketV2ParentError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
        AttributeError,
        IndexError,
        RecursionError,
    ) as exc:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "packet V2 producer/parent validation failed"
        ) from exc
    return _strict_parent_receipt(
        parent_receipt,
        expected_member_raw_sha256,
        manifest=manifest,
        target_precommit=target_precommit,
        expected_target_parent_receipt_sha256=independent_target_declared_sha,
        expected_target_parent_receipt_full_sha256=independent_target_full_sha,
    )


def _binding_material(
    *,
    schema_version: str,
    validation_mode: str,
    expected_member_raw_sha256: Mapping[str, str],
    parent_receipt: Mapping[str, Any],
    handles_held: bool,
) -> dict[str, Any]:
    parent_declared = parent_receipt["receipt_sha256"]
    return {
        "schema_version": schema_version,
        "validation_mode": validation_mode,
        "windows_component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "packet_component_manifest_sha256": PACKET_COMPONENT_MANIFEST_SHA256,
        "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
        "fixed_member_count": 16,
        "aggregate_member_cap_bytes": AGGREGATE_MEMBER_CAP_BYTES,
        "expected_member_raw_sha256": dict(expected_member_raw_sha256),
        "validated_member_raw_sha256": dict(expected_member_raw_sha256),
        "expected_member_raw_pin_set_sha256": _canonical_sha256(
            dict(expected_member_raw_sha256)
        ),
        "producer_manifest_validated": True,
        "producer_parent_validated": True,
        "producer_parent_receipt_sha256": parent_declared,
        "producer_parent_receipt_full_sha256": _canonical_sha256(
            dict(parent_receipt)
        ),
        "independent_target_parent_receipt_sha256":
            parent_receipt["target_parent_receipt_sha256"],
        "independent_target_parent_receipt_full_sha256":
            parent_receipt["target_parent_receipt_full_sha256"],
        "packet_parent_execution_count": 1,
        "independent_target_parent_execution_count": 1,
        "total_target_parent_execution_count": 2,
        "target_parent_single_execution_claimed": False,
        "byte_inventory_binding_verified": True,
        "handles_held_across_packet_validation": handles_held,
        "local_byte_handle_consistency_verified": handles_held,
        **{field: False for field in _DENIAL_FIELDS},
        "operational_effect": "NONE_SHADOW_ONLY",
        "gate_status": (
            "NO_GO_PRESENTED_PACKET_V2_MEMORY_BINDING_ONLY"
            if not handles_held
            else "NO_GO_PRESENTED_PACKET_V2_BOUNDED_WINDOWS_HANDLE_BINDING_ONLY"
        ),
        "receipt_hash_scope": "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
    }


def _seal_exact(material: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    if type(material) is not dict or tuple(material) + ("receipt_sha256",) != fields:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "internal receipt exact fields mismatch"
        )
    copied = dict(material)
    return {**copied, "receipt_sha256": _canonical_sha256(copied)}


def bind_presented_a_context_annotation_packet_v2_memory(
    *,
    manifest_raw: bytes,
    expected_member_raw_sha256: Mapping[str, str],
    **child_raw_by_role: bytes,
) -> dict[str, Any]:
    """Validate caller-pinned packet V2 bytes without filesystem claims."""

    all_raws, pins = _preflight_raws(
        manifest_raw, child_raw_by_role, expected_member_raw_sha256
    )
    parent_receipt = _validate_packet_raws(all_raws, pins)
    material = _binding_material(
        schema_version=MEMORY_RECEIPT_SCHEMA,
        validation_mode="MEMORY_RAW_BYTES",
        expected_member_raw_sha256=pins,
        parent_receipt=parent_receipt,
        handles_held=False,
    )
    return _seal_exact(material, MEMORY_RECEIPT_FIELDS)


def _validate_handle_receipt_projection(
    receipt_value: Any, *, expected_evidence: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate locally computed evidence and emit only its safe projection."""

    local_fields = (
        "root_final_path", "root_volume_serial", "root_file_id",
        "ancestor_handle_count", "member_handle_count",
        *_HANDLE_EVIDENCE_FIELDS, "members", "ancestor_chain",
    )
    if (
        type(expected_evidence) is not dict
        or tuple(expected_evidence) != local_fields
        or any(type(key) is not str for key in expected_evidence)
        or type(receipt_value) is not dict
        or tuple(receipt_value) != _HANDLE_RECEIPT_FIELDS
        or any(type(key) is not str for key in receipt_value)
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows handle receipt/evidence exact ordered fields mismatch"
        )

    # Reject container/scalar subclasses and bool/int confusion before hashing.
    string_fields = (
        "schema_version", "platform", "root_final_path", "root_volume_serial",
        "root_file_id", "packet_component_manifest_sha256",
        "windows_component_manifest_sha256", "fixed_member_contract_sha256",
        "member_raw_caps_sha256",
        "expected_member_raw_pin_set_sha256", "member_sequence_sha256",
        "inventory_before_sha256", "inventory_after_sha256",
        "ancestor_chain_sha256", "root_before_projection_sha256",
        "root_after_projection_sha256", "root_reopen_projection_sha256",
        "member_evidence_sha256", "operational_effect", "gate_status",
        "receipt_hash_scope", "receipt_sha256",
    )
    integer_fields = (
        "ancestor_handle_count", "member_handle_count", "total_member_bytes",
        "aggregate_member_cap_bytes",
    )
    for field in string_fields:
        if type(receipt_value[field]) is not str:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows handle receipt string type mismatch: {field}"
            )
    for field in integer_fields:
        if type(receipt_value[field]) is not int:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows handle receipt integer type mismatch: {field}"
            )
    for field in (*_HANDLE_TRUE_FIELDS, *_DENIAL_FIELDS):
        if type(receipt_value[field]) is not bool:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows handle receipt boolean type mismatch: {field}"
            )
    if (
        type(receipt_value["member_sequence"]) is not list
        or type(receipt_value["members"]) is not list
        or type(receipt_value["ancestor_chain"]) is not list
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows handle receipt list type mismatch"
        )
    for field in local_fields:
        expected = expected_evidence[field]
        actual = receipt_value[field]
        if type(actual) is not type(expected) or actual != expected:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows handle receipt locally computed evidence mismatch: {field}"
            )

    if (
        receipt_value["schema_version"] != WINDOWS_HANDLE_RECEIPT_SCHEMA
        or receipt_value["platform"] != "win32"
        or _VOLUME_GUID_PATH.fullmatch(
            receipt_value["root_final_path"].rstrip("\\")
        ) is None
        or _ASCII_DECIMAL.fullmatch(receipt_value["root_volume_serial"]) is None
        or not 0 <= int(receipt_value["root_volume_serial"]) < 2**64
        or _FILE_ID.fullmatch(receipt_value["root_file_id"]) is None
        or receipt_value["ancestor_handle_count"] < 1
        or receipt_value["member_handle_count"] != 16
        or receipt_value["packet_component_manifest_sha256"]
        != PACKET_COMPONENT_MANIFEST_SHA256
        or receipt_value["windows_component_manifest_sha256"]
        != COMPONENT_MANIFEST_SHA256
        or receipt_value["fixed_member_contract_sha256"]
        != FIXED_MEMBER_CONTRACT_SHA256
        or receipt_value["member_raw_caps_sha256"] != MEMBER_RAW_CAPS_SHA256
        or receipt_value["member_sequence"] != list(MEMBER_SEQUENCE)
        or receipt_value["member_sequence_sha256"]
        != _canonical_sha256(list(MEMBER_SEQUENCE))
        or receipt_value["aggregate_member_cap_bytes"]
        != AGGREGATE_MEMBER_CAP_BYTES
        or not 0 <= receipt_value["total_member_bytes"]
        <= AGGREGATE_MEMBER_CAP_BYTES
        or receipt_value["inventory_before_sha256"]
        != receipt_value["inventory_after_sha256"]
        or receipt_value["root_before_projection_sha256"]
        != receipt_value["root_after_projection_sha256"]
        or receipt_value["root_before_projection_sha256"]
        != receipt_value["root_reopen_projection_sha256"]
        or any(receipt_value[field] is not True for field in _HANDLE_TRUE_FIELDS)
        or any(receipt_value[field] is not False for field in _DENIAL_FIELDS)
        or receipt_value["operational_effect"] != "NONE_SHADOW_ONLY"
        or receipt_value["gate_status"]
        != "NO_GO_PRESENTED_PACKET_V2_BOUNDED_WINDOWS_HANDLE_BINDING_ONLY"
        or receipt_value["receipt_hash_scope"]
        != "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256"
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows handle receipt fixed safe semantics mismatch"
        )
    for field in (
        "packet_component_manifest_sha256",
        "windows_component_manifest_sha256",
        "fixed_member_contract_sha256",
        "member_raw_caps_sha256",
        "expected_member_raw_pin_set_sha256",
        "member_sequence_sha256",
        "inventory_before_sha256",
        "inventory_after_sha256",
        "ancestor_chain_sha256",
        "root_before_projection_sha256",
        "root_after_projection_sha256",
        "root_reopen_projection_sha256",
        "member_evidence_sha256",
        "receipt_sha256",
    ):
        if _SHA256.fullmatch(receipt_value[field]) is None:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows handle receipt SHA malformed: {field}"
            )

    members = receipt_value["members"]
    if len(members) != 16:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows handle receipt member inventory mismatch"
        )
    seen_ids: set[str] = set()
    total_bytes = 0
    for expected, member in zip(FIXED_MEMBER_CONTRACT, members):
        role, path, media_type, cap = expected
        if (
            type(member) is not dict
            or tuple(member) != _HANDLE_MEMBER_FIELDS
            or any(type(key) is not str for key in member)
        ):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "Windows handle member exact ordered fields mismatch"
            )
        for field in (
            "role", "path", "media_type", "final_path", "volume_serial",
            "file_id", "sha256", "before_projection_sha256",
            "after_projection_sha256", "reopen_projection_sha256",
        ):
            if type(member[field]) is not str:
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"Windows handle member string type mismatch: {role}.{field}"
                )
        for field in ("max_bytes", "bytes", "number_of_links"):
            if type(member[field]) is not int:
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"Windows handle member integer type mismatch: {role}.{field}"
                )
        if type(member["unnamed_stream_only"]) is not bool:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows handle member boolean type mismatch: {role}"
            )
        if (
            member["role"] != role
            or member["path"] != path
            or member["media_type"] != media_type
            or member["max_bytes"] != cap
            or not 0 <= member["bytes"] <= cap
            or _SHA256.fullmatch(member["sha256"]) is None
            or _ASCII_DECIMAL.fullmatch(member["volume_serial"]) is None
            or _FILE_ID.fullmatch(member["file_id"]) is None
            or member["final_path"]
            != receipt_value["root_final_path"] + "\\" + path
            or member["volume_serial"] != receipt_value["root_volume_serial"]
            or member["number_of_links"] != 1
            or member["unnamed_stream_only"] is not True
            or any(
                _SHA256.fullmatch(member[field]) is None
                for field in (
                    "before_projection_sha256", "after_projection_sha256",
                    "reopen_projection_sha256",
                )
            )
            or member["before_projection_sha256"]
            != member["after_projection_sha256"]
            or member["before_projection_sha256"]
            != member["reopen_projection_sha256"]
        ):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows handle member fixed semantics mismatch: {role}"
            )
        if member["file_id"] in seen_ids:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "Windows handle member file IDs must be unique"
            )
        seen_ids.add(member["file_id"])
        total_bytes += member["bytes"]
    if (
        total_bytes != receipt_value["total_member_bytes"]
        or _canonical_sha256(members)
        != receipt_value["member_evidence_sha256"]
    ):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows handle member aggregate evidence mismatch"
        )

    ancestors = receipt_value["ancestor_chain"]
    if len(ancestors) != receipt_value["ancestor_handle_count"]:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows ancestor evidence count mismatch"
        )
    for index, ancestor in enumerate(ancestors):
        if (
            type(ancestor) is not dict
            or tuple(ancestor) != _ANCESTOR_EVIDENCE_FIELDS
            or any(type(key) is not str for key in ancestor)
        ):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "Windows ancestor exact ordered fields mismatch"
            )
        if (
            type(ancestor["index"]) is not int
            or ancestor["index"] != index
            or type(ancestor["lexical_path"]) is not str
            or any(
                type(ancestor[field]) is not str
                or _SHA256.fullmatch(ancestor[field]) is None
                for field in (
                    "before_projection_sha256", "after_projection_sha256",
                    "reopen_projection_sha256",
                )
            )
            or ancestor["before_projection_sha256"]
            != ancestor["after_projection_sha256"]
            or ancestor["before_projection_sha256"]
            != ancestor["reopen_projection_sha256"]
        ):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                f"Windows ancestor evidence mismatch: {index}"
            )
    if _canonical_sha256(ancestors) != receipt_value["ancestor_chain_sha256"]:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows ancestor chain SHA mismatch"
        )

    receipt = dict(receipt_value)
    declared = receipt.pop("receipt_sha256")
    if declared != _canonical_sha256(receipt):
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows handle receipt self-hash mismatch"
        )
    safe = {
        "schema_version": SAFE_HANDLE_PROJECTION_SCHEMA,
        "handle_receipt_sha256": declared,
        "root_final_path": receipt_value["root_final_path"],
        "root_volume_serial": receipt_value["root_volume_serial"],
        "root_file_id": receipt_value["root_file_id"],
        "ancestor_handle_count": receipt_value["ancestor_handle_count"],
        "member_handle_count": receipt_value["member_handle_count"],
        **{field: receipt_value[field] for field in _HANDLE_EVIDENCE_FIELDS},
        "handles_held_across_packet_validation": True,
        "local_byte_handle_consistency_verified": True,
        **{field: False for field in _DENIAL_FIELDS},
    }
    return _seal_exact(safe, _SAFE_HANDLE_PROJECTION_FIELDS)


def observe_presented_a_context_annotation_packet_v2_windows_directory_identity(
    packet_dir: Path | str,
) -> WindowsDirectoryIdentity:
    """Observe a root tuple; the result is not an external identity pin."""

    if not _IS_WINDOWS:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows fixed-directory validation is unavailable on this platform"
        )
    api = _Win32()
    root_path, _ = _lexical_ancestor_paths(packet_dir)
    with _open_handle(api, root_path, directory=True, read_data=False) as root:
        snapshot = _query_snapshot(api, root.value, include_streams=False)
        _assert_directory(snapshot, "observed root")
        _assert_not_case_sensitive_directory(api, root.value, "observed root")
        return WindowsDirectoryIdentity(
            snapshot.final_path, snapshot.volume_serial, snapshot.file_id
        )


def validate_presented_a_context_annotation_packet_v2_windows_directory(
    packet_dir: Path | str,
    *,
    expected_root_final_path: str,
    expected_root_volume_serial: int,
    expected_root_file_id: str,
    expected_member_raw_sha256: Mapping[str, str],
) -> dict[str, Any]:
    """Read and validate the exact 16-member directory under held Win32 handles."""

    _assert_fixed_drift_pins()
    pins = _preflight_pins(expected_member_raw_sha256)
    expected_final, expected_volume, expected_id = _validate_expected_identity(
        expected_final_path=expected_root_final_path,
        expected_volume_serial=expected_root_volume_serial,
        expected_file_id=expected_root_file_id,
    )
    if not _IS_WINDOWS:
        raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
            "Windows fixed-directory validation is unavailable on this platform"
        )
    expected_names = frozenset(value[1] for value in FIXED_MEMBER_CONTRACT)
    for name in expected_names:
        if Path(name).name != name or "/" in name or "\\" in name or ":" in name:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "fixed member name is unsafe"
            )

    api = _Win32()
    root_path, ancestors = _lexical_ancestor_paths(packet_dir)
    with ExitStack() as stack:
        ancestor_snapshots: list[tuple[str, _OwnedHandle, _ObjectSnapshot]] = []
        previous: _ObjectSnapshot | None = None
        for index, path in enumerate(ancestors):
            handle = stack.enter_context(
                _open_handle(api, path, directory=True, read_data=False)
            )
            snapshot = _query_snapshot(api, handle.value, include_streams=False)
            _assert_directory(snapshot, f"ancestor {index}")
            _assert_not_case_sensitive_directory(api, handle.value, f"ancestor {index}")
            if previous is not None:
                if snapshot.volume_serial != previous.volume_serial:
                    raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                        "ancestor chain crosses a volume boundary"
                    )
                _assert_direct_final_path_descendant(
                    previous.final_path, snapshot.final_path, f"ancestor {index}"
                )
            previous = snapshot
            ancestor_snapshots.append((path, handle, snapshot))

        root = stack.enter_context(
            _open_handle(api, root_path, directory=True, read_data=False)
        )
        root_before = _query_snapshot(api, root.value, include_streams=False)
        _assert_directory(root_before, "packet root")
        _assert_not_case_sensitive_directory(api, root.value, "packet root")
        if root_before.final_path != expected_final:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "caller-pinned root final path mismatch"
            )
        if root_before.volume_serial != expected_volume:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "caller-pinned root volume serial mismatch"
            )
        if root_before.file_id != expected_id:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "caller-pinned root file ID mismatch"
            )
        if not ancestor_snapshots:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "packet root requires a held immediate parent"
            )
        immediate_parent = ancestor_snapshots[-1][2]
        if root_before.volume_serial != immediate_parent.volume_serial:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "packet root crosses its parent volume boundary"
            )
        _assert_direct_final_path_descendant(
            immediate_parent.final_path, root_before.final_path, "packet root"
        )

        inventory_before = _enumerate_directory(api, root.value)
        _validate_inventory(inventory_before, expected_names)
        aggregate_size = 0
        for role, path, _media_type, cap in FIXED_MEMBER_CONTRACT:
            size = inventory_before[path].size
            if not 0 <= size <= cap:
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"{role} exceeds its fixed role cap before first read"
                )
            aggregate_size += size
        if aggregate_size > AGGREGATE_MEMBER_CAP_BYTES:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "packet exceeds aggregate cap before first read"
            )

        opened: dict[str, tuple[_OwnedHandle, _ObjectSnapshot]] = {}
        seen_ids: set[str] = set()
        for role, name, _media_type, _cap in FIXED_MEMBER_CONTRACT:
            handle_path = root_before.final_path + "\\" + name
            handle = stack.enter_context(
                _open_handle(api, handle_path, directory=False, read_data=True)
            )
            before = _query_snapshot(api, handle.value, include_streams=True)
            _assert_regular_single_link(before, role)
            if before.final_path != handle_path:
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"packet member final path mismatch: {role}"
                )
            if before.volume_serial != root_before.volume_serial:
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"packet member volume differs from root: {role}"
                )
            _assert_entry_matches_snapshot(inventory_before[name], before, name)
            if before.file_id in seen_ids:
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    "fixed packet members must have unique file IDs"
                )
            seen_ids.add(before.file_id)
            opened[role] = (handle, before)

        all_raws: dict[str, bytes] = {}
        member_receipts: list[dict[str, Any]] = []
        for role, name, media_type, cap in FIXED_MEMBER_CONTRACT:
            handle, before = opened[role]
            raw = _read_handle_exact(api, handle.value, before.standard[1], role)
            all_raws[role] = raw
            member_receipts.append({
                "role": role,
                "path": name,
                "media_type": media_type,
                "max_bytes": cap,
                "final_path": before.final_path,
                "volume_serial": str(before.volume_serial),
                "file_id": before.file_id,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "number_of_links": before.standard[2],
                "unnamed_stream_only": True,
            })

        actual_pins = {value["role"]: value["sha256"] for value in member_receipts}
        if actual_pins != pins:
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "caller-pinned member raw SHA mismatch"
            )

        # This call is deliberately inside ExitStack: every ancestor, root, and
        # member handle remains held while both packet validators execute.
        parent_receipt = _validate_packet_raws(all_raws, pins)

        for index, (role, name, _media_type, _cap) in enumerate(
            FIXED_MEMBER_CONTRACT
        ):
            handle, before = opened[role]
            after = _query_snapshot(api, handle.value, include_streams=True)
            if not _snapshot_stable(before, after):
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"packet member identity/metadata changed: {role}"
                )
            reopened = stack.enter_context(
                _open_handle(
                    api, root_before.final_path + "\\" + name,
                    directory=False, read_data=False,
                )
            )
            reopened_snapshot = _query_snapshot(
                api, reopened.value, include_streams=True
            )
            _assert_regular_single_link(reopened_snapshot, role)
            if not _snapshot_stable(before, reopened_snapshot):
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"reopened packet member mismatch: {role}"
                )
            before_sha = _canonical_sha256(_snapshot_stable_projection(before))
            after_sha = _canonical_sha256(_snapshot_stable_projection(after))
            reopen_sha = _canonical_sha256(
                _snapshot_stable_projection(reopened_snapshot)
            )
            member_receipts[index].update({
                "before_projection_sha256": before_sha,
                "after_projection_sha256": after_sha,
                "reopen_projection_sha256": reopen_sha,
            })

        root_after = _query_snapshot(api, root.value, include_streams=False)
        if not _snapshot_stable(root_before, root_after):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "packet root identity/metadata changed"
            )
        root_reopened = stack.enter_context(
            _open_handle(api, root_path, directory=True, read_data=False)
        )
        root_reopened_snapshot = _query_snapshot(
            api, root_reopened.value, include_streams=False
        )
        _assert_directory(root_reopened_snapshot, "reopened packet root")
        _assert_not_case_sensitive_directory(
            api, root_reopened.value, "reopened packet root"
        )
        if not _snapshot_stable(root_before, root_reopened_snapshot):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "reopened packet root mismatch"
            )
        inventory_after = _enumerate_directory(api, root_reopened.value)
        _validate_inventory(inventory_after, expected_names)
        if _inventory_projection(inventory_before) != _inventory_projection(
            inventory_after
        ):
            raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                "fixed directory inventory changed"
            )

        ancestor_chain: list[dict[str, Any]] = []
        for index, (path, handle, before) in enumerate(ancestor_snapshots):
            after = _query_snapshot(api, handle.value, include_streams=False)
            if _ancestor_namespace_projection(before) != _ancestor_namespace_projection(
                after
            ):
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"ancestor identity changed: {index}"
                )
            reopened = stack.enter_context(
                _open_handle(api, path, directory=True, read_data=False)
            )
            reopened_snapshot = _query_snapshot(
                api, reopened.value, include_streams=False
            )
            _assert_directory(reopened_snapshot, f"reopened ancestor {index}")
            _assert_not_case_sensitive_directory(
                api, reopened.value, f"reopened ancestor {index}"
            )
            if _ancestor_namespace_projection(
                before
            ) != _ancestor_namespace_projection(reopened_snapshot):
                raise P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError(
                    f"reopened ancestor mismatch: {index}"
                )

            ancestor_chain.append({
                "index": index,
                "lexical_path": path,
                "before_projection_sha256": _canonical_sha256(
                    _ancestor_namespace_projection(before)
                ),
                "after_projection_sha256": _canonical_sha256(
                    _ancestor_namespace_projection(after)
                ),
                "reopen_projection_sha256": _canonical_sha256(
                    _ancestor_namespace_projection(reopened_snapshot)
                ),
            })

        inventory_before_sha = _canonical_sha256(
            _inventory_projection(inventory_before)
        )
        inventory_after_sha = _canonical_sha256(
            _inventory_projection(inventory_after)
        )
        root_before_sha = _canonical_sha256(
            _snapshot_stable_projection(root_before)
        )
        root_after_sha = _canonical_sha256(
            _snapshot_stable_projection(root_after)
        )
        root_reopen_sha = _canonical_sha256(
            _snapshot_stable_projection(root_reopened_snapshot)
        )
        evidence_values = {
            "windows_component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
            "packet_component_manifest_sha256":
                PACKET_COMPONENT_MANIFEST_SHA256,
            "fixed_member_contract_sha256": FIXED_MEMBER_CONTRACT_SHA256,
            "member_raw_caps_sha256": MEMBER_RAW_CAPS_SHA256,
            "expected_member_raw_pin_set_sha256": _canonical_sha256(pins),
            "member_sequence": list(MEMBER_SEQUENCE),
            "member_sequence_sha256": _canonical_sha256(list(MEMBER_SEQUENCE)),
            "total_member_bytes": sum(len(raw) for raw in all_raws.values()),
            "aggregate_member_cap_bytes": AGGREGATE_MEMBER_CAP_BYTES,
            "inventory_before_sha256": inventory_before_sha,
            "inventory_after_sha256": inventory_after_sha,
            "ancestor_chain_sha256": _canonical_sha256(ancestor_chain),
            "root_before_projection_sha256": root_before_sha,
            "root_after_projection_sha256": root_after_sha,
            "root_reopen_projection_sha256": root_reopen_sha,
            "member_evidence_sha256": _canonical_sha256(member_receipts),
        }
        expected_evidence = {
            "root_final_path": root_before.final_path,
            "root_volume_serial": str(root_before.volume_serial),
            "root_file_id": root_before.file_id,
            "ancestor_handle_count": len(ancestor_snapshots),
            "member_handle_count": 16,
            **evidence_values,
            "members": member_receipts,
            "ancestor_chain": ancestor_chain,
        }

        handle_material = {
            "schema_version": WINDOWS_HANDLE_RECEIPT_SCHEMA,
            "platform": "win32",
            "root_final_path": root_before.final_path,
            "root_volume_serial": str(root_before.volume_serial),
            "root_file_id": root_before.file_id,
            "ancestor_handle_count": len(ancestor_snapshots),
            "member_handle_count": 16,
            **evidence_values,
            "members": member_receipts,
            "ancestor_chain": ancestor_chain,
            **{field: True for field in _HANDLE_TRUE_FIELDS},
            **{field: False for field in _DENIAL_FIELDS},
            "operational_effect": "NONE_SHADOW_ONLY",
            "gate_status":
                "NO_GO_PRESENTED_PACKET_V2_BOUNDED_WINDOWS_HANDLE_BINDING_ONLY",
            "receipt_hash_scope":
                "CANONICAL_MATERIAL_EXCLUDING_RECEIPT_SHA256",
        }
        handle_receipt = _seal_exact(handle_material, _HANDLE_RECEIPT_FIELDS)
        safe_projection = _validate_handle_receipt_projection(
            handle_receipt, expected_evidence=expected_evidence
        )

        material = _binding_material(
            schema_version=WINDOWS_DIRECTORY_RECEIPT_SCHEMA,
            validation_mode="WINDOWS_FIXED_DIRECTORY_DIRECT",
            expected_member_raw_sha256=pins,
            parent_receipt=parent_receipt,
            handles_held=True,
        )
        material.update({
            "root_final_path": root_before.final_path,
            "root_volume_serial": str(root_before.volume_serial),
            "root_file_id": root_before.file_id,
            "ancestor_handle_count": len(ancestor_snapshots),
            "member_handle_count": 16,
            "handle_safe_projection": safe_projection,
            "handle_safe_projection_sha256": safe_projection["receipt_sha256"],
        })
        result = _seal_exact(material, WINDOWS_DIRECTORY_RECEIPT_FIELDS)
    return result


__all__ = [
    "AGGREGATE_MEMBER_CAP_BYTES",
    "CHILD_ROLES",
    "COMPONENT_MANIFEST",
    "COMPONENT_MANIFEST_SHA256",
    "FIXED_MEMBER_CONTRACT",
    "FIXED_MEMBER_CONTRACT_SHA256",
    "MEMBER_RAW_CAPS",
    "MEMBER_RAW_CAPS_SHA256",
    "MEMBER_ROLES",
    "MEMBER_SEQUENCE",
    "MEMORY_RECEIPT_FIELDS",
    "MEMORY_RECEIPT_SCHEMA",
    "PACKET_COMPONENT_MANIFEST_SHA256",
    "P0PresentedAContextAnnotationPacketV2WindowsFixedDirectoryError",
    "SAFE_HANDLE_PROJECTION_SCHEMA",
    "PUBLIC_APIS",
    "WINDOWS_DIRECTORY_RECEIPT_FIELDS",
    "WINDOWS_DIRECTORY_RECEIPT_SCHEMA",
    "WINDOWS_HANDLE_RECEIPT_SCHEMA",
    "WindowsDirectoryIdentity",
    "bind_presented_a_context_annotation_packet_v2_memory",
    "observe_presented_a_context_annotation_packet_v2_windows_directory_identity",
    "validate_presented_a_context_annotation_packet_v2_windows_directory",
]
