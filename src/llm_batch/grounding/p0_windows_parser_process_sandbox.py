"""Fail-closed Windows process boundary for the P0 capture-hash probe.

This module launches exactly :data:`sys.executable` and the repository's
``p0_parser_process_worker.py``.  Callers supply canonical protocol bytes, not
an executable, command line, environment, or filesystem handle.

The child uses a privilege-stripped primary token restricted by an exact
projection of TokenUser plus every enabled, non-deny-only TokenGroup, an exact
three-handle inheritance list, and a one-process Job Object.  These controls
establish only the narrow observations recorded in the receipt.  They are not
a filesystem, network, AppContainer, semantic parser, runtime-noninterference,
owner-authority, or P0 approval boundary.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import hashlib
import importlib.machinery
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Mapping
import unicodedata

from llm_batch.grounding import p0_parser_process_protocol as protocol
from llm_batch.grounding import p0_parser_process_worker as worker
from llm_batch.grounding import p0_windows_fixed_directory_identity as _identity
from llm_batch.grounding import p0_windows_directory_change_watch as _watch


SANDBOX_RECEIPT_SCHEMA = "p0_windows_parser_process_sandbox_receipt_v3"
PARSER_VERSION = "capture-hash-probe-v1"
OBSERVER = "stdlib-ctypes-win32-primary-token-job-source-closure-v3"
GATE_STATUS = "NO_GO_PROCESS_SANDBOX_COMPONENT_ONLY"
MAX_STDERR_BYTES = 64 * 1024
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_TIMEOUT_SECONDS = 300.0

_IS_WINDOWS = os.name == "nt"
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_TOKEN_ASSIGN_PRIMARY = 0x0001
_TOKEN_DUPLICATE = 0x0002
_TOKEN_IMPERSONATE = 0x0004
_TOKEN_QUERY = 0x0008
_DISABLE_MAX_PRIVILEGE = 0x0001
_TOKEN_PRIVILEGES = 3
_TOKEN_USER = 1
_TOKEN_GROUPS = 2
_TOKEN_TYPE = 8
_TOKEN_RESTRICTED_SIDS = 11
_TOKEN_PRIMARY = 1
_SE_GROUP_ENABLED = 0x00000004
_SE_GROUP_USE_FOR_DENY_ONLY = 0x00000010

_GENERIC_READ = 0x80000000
_DELETE = 0x00010000
_FILE_LIST_DIRECTORY = 0x0001
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
_FILE_BEGIN = 0
_MAX_PROCESS_IMAGE_CHARS = 32768

_HANDLE_FLAG_INHERIT = 0x00000001
_STARTF_USESTDHANDLES = 0x00000100
_CREATE_SUSPENDED = 0x00000004
_CREATE_UNICODE_ENVIRONMENT = 0x00000400
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000
_CREATE_NO_WINDOW = 0x08000000

_PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_ERROR_INSUFFICIENT_BUFFER = 122
_ERROR_ALREADY_EXISTS = 183
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_STILL_ACTIVE = 259
_FILE_DISPOSITION_INFO_CLASS = 4
_BCRYPT_USE_SYSTEM_PREFERRED_RNG = 0x00000002
_CACHE_ANCHOR_NAME = "llm_novel_p0_parser_cache_v1"
_PYCACHE_TEMPLATE = "<PER_EXECUTION_EMPTY_ROOT>"
_WATCH_NOTIFY_FILTER = (
    _watch.FILE_NOTIFY_CHANGE_FILE_NAME
    | _watch.FILE_NOTIFY_CHANGE_DIR_NAME
    | _watch.FILE_NOTIFY_CHANGE_ATTRIBUTES
    | _watch.FILE_NOTIFY_CHANGE_SIZE
    | _watch.FILE_NOTIFY_CHANGE_LAST_WRITE
    | _watch.FILE_NOTIFY_CHANGE_CREATION
    | _watch.FILE_NOTIFY_CHANGE_SECURITY
)

_FALSE_FIELDS = tuple(sorted(set(protocol.FALSE_AUTHORITY_FIELDS) | {
    "network_deny_verified",
    "appcontainer_verified",
    "filesystem_write_deny_verified",
    "os_write_deny_verified",
    "registry_write_deny_verified",
    "desktop_isolation_verified",
    "runtime_noninterference_verified",
    "parser_runtime_execution_verified",
    "semantic_parser_executed",
    "actual_evidence_verified",
    "semantic_quality_verified",
    "owner_authority_verified",
    "actual_authority_granted",
    "external_code_authority_verified",
    "p0_phase_exit",
    "production_approval",
    "full_scan_approval",
    "action_applied",
    "parser_dependency_closure_verified",
    "project_source_load_candidate_closure_verified",
    "trusted_cpython_runtime_prerequisite_verified",
    "python_runtime_dependency_closure_verified",
    "python_stdlib_dependency_closure_verified",
    "native_dll_dependency_closure_verified",
    "actual_loaded_image_file_object_verified",
    "external_project_source_identity_pin_verified",
    "authorized_parser_version_verified",
    "protected_pipeline_state_mutated",
}))


class P0WindowsParserProcessSandboxError(RuntimeError):
    """The process sandbox could not preserve its fail-closed contract."""

    def __init__(self, message: str, receipt: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.receipt = dict(receipt) if receipt is not None else None


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TOKEN_USER_VALUE(ctypes.Structure):
    _fields_ = [("User", _SID_AND_ATTRIBUTES)]


class _TOKEN_GROUPS_HEADER(ctypes.Structure):
    _fields_ = [
        ("GroupCount", wintypes.DWORD),
        ("Groups", _SID_AND_ATTRIBUTES * 2),
    ]


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", _LUID), ("Attributes", wintypes.DWORD)]


class _TOKEN_PRIVILEGES_ONE(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", wintypes.DWORD),
        ("Privileges", _LUID_AND_ATTRIBUTES * 1),
    ]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", _STARTUPINFOW),
        ("lpAttributeList", ctypes.c_void_p),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _FILE_DISPOSITION_INFO(ctypes.Structure):
    _fields_ = [("DeleteFile", wintypes.BOOL)]


@dataclass(frozen=True)
class _PinnedFile:
    role: str
    path: Path
    handle: int
    snapshot: Any
    sha256: str
    project_source_candidate: bool


@dataclass(frozen=True)
class _NamespaceGuard:
    path: Path
    handle: int
    snapshot: Any


@dataclass(frozen=True)
class _CacheAnchorSelection:
    lexical_path: Path
    resolved_path: Path
    lexical_guards: tuple[_NamespaceGuard, ...]
    redirection_observed: bool


@dataclass(frozen=True)
class _SourceDirectoryInventory:
    role: str
    path: Path
    projection: tuple[dict[str, Any], ...]
    sha256: str


@dataclass
class _PinnedPycache:
    path: Path
    handle: int
    snapshot: Any
    empty_before_create: bool = False
    empty_before_resume: bool = False
    empty_after_exit: bool = False
    cleanup_attempted: bool = False
    disposition_set: bool = False
    handle_close_succeeded: bool = False
    cleanup_succeeded: bool = False
    path_absent_after_cleanup: bool = False


@dataclass(frozen=True)
class _SuspendedProcessEvidence:
    process_id: int
    creation_time_100ns: int
    reported_image_path: str
    reopened_image_final_path: str
    reopened_image_volume_serial: int
    reopened_image_file_id: str
    reopened_image_sha256: str


@dataclass(frozen=True)
class _PinnedLaunch:
    caller_sys_executable_path: Path
    caller_sys_executable_sha256: str
    executable_path: Path
    worker_path: Path
    protocol_path: Path
    llm_batch_init_path: Path
    grounding_init_path: Path
    executable_sha256: str
    worker_sha256: str
    protocol_sha256: str
    llm_batch_init_sha256: str
    grounding_init_sha256: str
    parser_manifest_sha256: str
    launch_sha256: str
    files: tuple[_PinnedFile, ...]
    namespace_guards: tuple[_NamespaceGuard, ...]
    cache_anchor: _NamespaceGuard
    cache_anchor_lexical_path: Path
    cache_anchor_redirection_observed: bool
    source_directory_inventories: tuple[_SourceDirectoryInventory, ...]
    source_import_graph: tuple[dict[str, Any], ...]
    source_import_graph_sha256: str
    import_suffix_universe: tuple[str, ...]
    static_collision_inventory_verified: bool

    @property
    def handles(self) -> tuple[int, ...]:
        return tuple(
            [item.handle for item in self.files]
            + [item.handle for item in self.namespace_guards]
        )


class _Win32:
    def __init__(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
        shell32 = ctypes.OleDLL("shell32", use_last_error=True)
        ole32 = ctypes.OleDLL("ole32", use_last_error=True)

        self.GetCurrentProcess = kernel32.GetCurrentProcess
        self.GetCurrentProcess.restype = wintypes.HANDLE
        self.CloseHandle = kernel32.CloseHandle
        self.CloseHandle.argtypes = [wintypes.HANDLE]
        self.CloseHandle.restype = wintypes.BOOL
        self.CreateFileW = kernel32.CreateFileW
        self.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.CreateFileW.restype = wintypes.HANDLE
        self.CreateDirectoryW = kernel32.CreateDirectoryW
        self.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
        self.CreateDirectoryW.restype = wintypes.BOOL
        self.RemoveDirectoryW = kernel32.RemoveDirectoryW
        self.RemoveDirectoryW.argtypes = [wintypes.LPCWSTR]
        self.RemoveDirectoryW.restype = wintypes.BOOL
        self.GetFileInformationByHandleEx = kernel32.GetFileInformationByHandleEx
        self.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
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
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        self.ReadFile.restype = wintypes.BOOL
        self.SetFilePointerEx = kernel32.SetFilePointerEx
        self.SetFilePointerEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        self.SetFilePointerEx.restype = wintypes.BOOL
        self.GetFileAttributesW = kernel32.GetFileAttributesW
        self.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        self.GetFileAttributesW.restype = wintypes.DWORD
        self.SetFileInformationByHandle = kernel32.SetFileInformationByHandle
        self.SetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.SetFileInformationByHandle.restype = wintypes.BOOL
        self.CreatePipe = kernel32.CreatePipe
        self.CreatePipe.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(wintypes.HANDLE),
            ctypes.POINTER(_SECURITY_ATTRIBUTES),
            wintypes.DWORD,
        ]
        self.CreatePipe.restype = wintypes.BOOL
        self.SetHandleInformation = kernel32.SetHandleInformation
        self.SetHandleInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        self.SetHandleInformation.restype = wintypes.BOOL
        self.CreateJobObjectW = kernel32.CreateJobObjectW
        self.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.CreateJobObjectW.restype = wintypes.HANDLE
        self.SetInformationJobObject = kernel32.SetInformationJobObject
        self.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.SetInformationJobObject.restype = wintypes.BOOL
        self.QueryInformationJobObject = kernel32.QueryInformationJobObject
        self.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.QueryInformationJobObject.restype = wintypes.BOOL
        self.AssignProcessToJobObject = kernel32.AssignProcessToJobObject
        self.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.AssignProcessToJobObject.restype = wintypes.BOOL
        self.IsProcessInJob = kernel32.IsProcessInJob
        self.IsProcessInJob.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.BOOL),
        ]
        self.IsProcessInJob.restype = wintypes.BOOL
        self.InitializeProcThreadAttributeList = (
            kernel32.InitializeProcThreadAttributeList
        )
        self.InitializeProcThreadAttributeList.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self.InitializeProcThreadAttributeList.restype = wintypes.BOOL
        self.UpdateProcThreadAttribute = kernel32.UpdateProcThreadAttribute
        self.UpdateProcThreadAttribute.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.UpdateProcThreadAttribute.restype = wintypes.BOOL
        self.DeleteProcThreadAttributeList = kernel32.DeleteProcThreadAttributeList
        self.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
        self.ResumeThread = kernel32.ResumeThread
        self.ResumeThread.argtypes = [wintypes.HANDLE]
        self.ResumeThread.restype = wintypes.DWORD
        self.WaitForSingleObject = kernel32.WaitForSingleObject
        self.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.WaitForSingleObject.restype = wintypes.DWORD
        self.GetExitCodeProcess = kernel32.GetExitCodeProcess
        self.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.GetExitCodeProcess.restype = wintypes.BOOL
        self.GetProcessId = kernel32.GetProcessId
        self.GetProcessId.argtypes = [wintypes.HANDLE]
        self.GetProcessId.restype = wintypes.DWORD
        self.GetProcessTimes = kernel32.GetProcessTimes
        self.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        self.GetProcessTimes.restype = wintypes.BOOL
        self.QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
        self.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self.TerminateJobObject = kernel32.TerminateJobObject
        self.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.TerminateJobObject.restype = wintypes.BOOL
        self.TerminateProcess = kernel32.TerminateProcess
        self.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.TerminateProcess.restype = wintypes.BOOL

        self.OpenProcessToken = advapi32.OpenProcessToken
        self.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self.OpenProcessToken.restype = wintypes.BOOL
        self.GetTokenInformation = advapi32.GetTokenInformation
        self.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.GetTokenInformation.restype = wintypes.BOOL
        self.CreateRestrictedToken = advapi32.CreateRestrictedToken
        self.CreateRestrictedToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_SID_AND_ATTRIBUTES),
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self.CreateRestrictedToken.restype = wintypes.BOOL
        self.IsTokenRestricted = advapi32.IsTokenRestricted
        self.IsTokenRestricted.argtypes = [wintypes.HANDLE]
        self.IsTokenRestricted.restype = wintypes.BOOL
        self.EqualSid = advapi32.EqualSid
        self.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.EqualSid.restype = wintypes.BOOL
        self.LookupPrivilegeNameW = advapi32.LookupPrivilegeNameW
        self.LookupPrivilegeNameW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(_LUID),
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.LookupPrivilegeNameW.restype = wintypes.BOOL
        self.CreateProcessAsUserW = advapi32.CreateProcessAsUserW
        self.CreateProcessAsUserW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.BOOL,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.LPCWSTR,
            ctypes.POINTER(_STARTUPINFOW),
            ctypes.POINTER(_PROCESS_INFORMATION),
        ]
        self.CreateProcessAsUserW.restype = wintypes.BOOL

        self.BCryptGenRandom = bcrypt.BCryptGenRandom
        self.BCryptGenRandom.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ubyte),
            wintypes.ULONG,
            wintypes.ULONG,
        ]
        self.BCryptGenRandom.restype = wintypes.LONG
        self.SHGetKnownFolderPath = shell32.SHGetKnownFolderPath
        self.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self.SHGetKnownFolderPath.restype = ctypes.c_long
        self.CoTaskMemFree = ole32.CoTaskMemFree
        self.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        self.CoTaskMemFree.restype = None


def _win_error(label: str) -> P0WindowsParserProcessSandboxError:
    code = ctypes.get_last_error()
    return P0WindowsParserProcessSandboxError(f"{label} failed with Win32 error {code}")


def _close(api: _Win32, handle: Any) -> None:
    value = handle.value if isinstance(handle, wintypes.HANDLE) else handle
    if value not in (None, 0, _INVALID_HANDLE_VALUE):
        api.CloseHandle(value)


def _identity_error(label: str, exc: BaseException) -> P0WindowsParserProcessSandboxError:
    return P0WindowsParserProcessSandboxError(f"{label}: {exc}")


def _cache_anchor_path(api: _Win32) -> _CacheAnchorSelection:
    folder_id = _GUID(
        0xF1B32785,
        0x6FBA,
        0x4FCF,
        (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
    )
    allocated = wintypes.LPWSTR()
    result = api.SHGetKnownFolderPath(
        ctypes.byref(folder_id), 0, None, ctypes.byref(allocated)
    )
    if result != 0 or not allocated.value:
        raise P0WindowsParserProcessSandboxError(
            f"SHGetKnownFolderPath(LocalAppData) failed with HRESULT {result}"
        )
    try:
        if not os.path.isabs(allocated.value):
            raise P0WindowsParserProcessSandboxError(
                "SHGetKnownFolderPath(LocalAppData) returned a non-absolute path"
            )
        local_appdata = Path(os.path.abspath(allocated.value))
    finally:
        api.CoTaskMemFree(ctypes.cast(allocated, ctypes.c_void_p))
    anchor = local_appdata / _CACHE_ANCHOR_NAME
    guards: list[_NamespaceGuard] = []
    try:
        root_path, ancestors = _identity._lexical_ancestor_paths(
            str(local_appdata)
        )
        for value in (*ancestors, root_path):
            current = _pin_directory(api, Path(value))
            if guards:
                previous = guards[-1]
                if current.snapshot.volume_serial != previous.snapshot.volume_serial:
                    raise P0WindowsParserProcessSandboxError(
                        "LocalAppData lexical chain crosses a volume"
                    )
                _identity._assert_direct_final_path_descendant(
                    previous.snapshot.final_path,
                    current.snapshot.final_path,
                    str(current.path),
                )
            guards.append(current)
        if not api.CreateDirectoryW(str(anchor), None):
            error = ctypes.get_last_error()
            if error != _ERROR_ALREADY_EXISTS:
                raise P0WindowsParserProcessSandboxError(
                    f"CreateDirectoryW(cache anchor) failed with Win32 error {error}"
                )
        anchor_guard = _pin_directory(api, anchor)
        guards.append(anchor_guard)
        redirection = False
        try:
            _identity._assert_direct_final_path_descendant(
                guards[-2].snapshot.final_path,
                anchor_guard.snapshot.final_path,
                str(anchor),
            )
        except BaseException:
            # MSIX-packaged desktop processes may virtualize LocalAppData.  All
            # lexical ancestors and the leaf itself were already opened with
            # OPEN_REPARSE_POINT and held, so record—but do not hide—the OS
            # redirection before selecting its stable DOS target.
            redirection = True
        resolved = anchor.resolve(strict=True)
        return _CacheAnchorSelection(
            lexical_path=anchor,
            resolved_path=resolved,
            lexical_guards=tuple(guards),
            redirection_observed=redirection,
        )
    except BaseException:
        for guard in guards:
            _close(api, guard.handle)
        raise


def _query_snapshot(api: _Win32, handle: int, *, streams: bool, label: str) -> Any:
    try:
        return _identity._query_snapshot(api, handle, include_streams=streams)
    except BaseException as exc:
        raise _identity_error(label, exc) from exc


def _seek_handle_start(api: _Win32, handle: int, label: str) -> None:
    position = ctypes.c_longlong()
    if not api.SetFilePointerEx(
        handle, ctypes.c_longlong(0), ctypes.byref(position), _FILE_BEGIN
    ):
        raise _win_error(f"SetFilePointerEx({label})")
    if position.value != 0:
        raise P0WindowsParserProcessSandboxError(
            f"SetFilePointerEx({label}) did not reach offset zero"
        )


def _hash_held_file(
    api: _Win32,
    handle: int,
    expected: Any,
    label: str,
) -> str:
    before = _query_snapshot(api, handle, streams=True, label=f"snapshot {label}")
    try:
        _identity._assert_regular_single_link(before, label)
    except BaseException as exc:
        raise _identity_error(label, exc) from exc
    if not _identity._snapshot_stable(expected, before):
        raise P0WindowsParserProcessSandboxError(
            f"held launch file changed before handle read: {label}"
        )
    _seek_handle_start(api, handle, label)
    try:
        raw = _identity._read_handle_exact(api, handle, before.standard[1], label)
    except BaseException as exc:
        raise _identity_error(f"read held launch file {label}", exc) from exc
    after = _query_snapshot(api, handle, streams=True, label=f"post-read {label}")
    _seek_handle_start(api, handle, label)
    if not _identity._snapshot_stable(before, after):
        raise P0WindowsParserProcessSandboxError(
            f"held launch file changed while read: {label}"
        )
    return hashlib.sha256(raw).hexdigest()


def _pin_directory(
    api: _Win32, path: Path, *, list_directory: bool = False
) -> _NamespaceGuard:
    access = _FILE_READ_ATTRIBUTES
    if list_directory:
        access |= _FILE_LIST_DIRECTORY
    handle = api.CreateFileW(
        str(path),
        access,
        _FILE_SHARE_READ,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        raise _win_error(f"CreateFileW(namespace guard {path})")
    try:
        snapshot = _query_snapshot(
            api, int(handle), streams=False, label=f"namespace guard {path}"
        )
        try:
            _identity._assert_directory(snapshot, f"namespace guard {path}")
        except BaseException as exc:
            raise _identity_error(f"namespace guard {path}", exc) from exc
        return _NamespaceGuard(path=path, handle=int(handle), snapshot=snapshot)
    except BaseException:
        _close(api, handle)
        raise


def _directory_inventory(
    api: _Win32, guard: _NamespaceGuard, role: str
) -> _SourceDirectoryInventory:
    try:
        values = _identity._enumerate_directory(api, guard.handle)
        projection = tuple(_identity._inventory_projection(values))
    except BaseException as exc:
        raise _identity_error(f"inventory {role}", exc) from exc
    return _SourceDirectoryInventory(
        role=role,
        path=guard.path,
        projection=projection,
        sha256=protocol.canonical_sha256(list(projection)),
    )


def _inventory_map(inventory: _SourceDirectoryInventory) -> dict[str, dict[str, Any]]:
    return {str(item["name"]): item for item in inventory.projection}


def _validate_source_collision_inventories(
    inventories: tuple[_SourceDirectoryInventory, ...],
) -> tuple[str, ...]:
    by_role = {item.role: item for item in inventories}
    if set(by_role) != {"src_directory", "llm_batch_directory", "grounding_directory"}:
        raise P0WindowsParserProcessSandboxError(
            "source collision inventory roles are not exact"
        )
    suffixes = tuple(
        dict.fromkeys(
            (*importlib.machinery.SOURCE_SUFFIXES, ".pyw",
             *importlib.machinery.BYTECODE_SUFFIXES,
             *importlib.machinery.EXTENSION_SUFFIXES)
        )
    )

    def validate_names(values: Mapping[str, dict[str, Any]], role: str) -> None:
        folded: set[str] = set()
        for name in values:
            if not name or name.endswith((".", " ")) or ":" in name or "\x00" in name:
                raise P0WindowsParserProcessSandboxError(
                    f"unsafe source inventory name in {role}"
                )
            normalized = unicodedata.normalize("NFC", name).casefold()
            if normalized in folded:
                raise P0WindowsParserProcessSandboxError(
                    f"Unicode/case-colliding source inventory name in {role}"
                )
            folded.add(normalized)

    src = _inventory_map(by_role["src_directory"])
    package = _inventory_map(by_role["llm_batch_directory"])
    grounding = _inventory_map(by_role["grounding_directory"])
    validate_names(src, "src")
    validate_names(package, "llm_batch")
    validate_names(grounding, "grounding")

    directory_flag = _FILE_ATTRIBUTE_DIRECTORY
    reparse_flag = _FILE_ATTRIBUTE_REPARSE_POINT

    def require(name: str, values: Mapping[str, dict[str, Any]], *, directory: bool) -> None:
        item = values.get(name)
        if item is None:
            raise P0WindowsParserProcessSandboxError(
                f"required source inventory entry absent: {name}"
            )
        attributes = int(item["attributes"])
        if bool(attributes & directory_flag) != directory:
            raise P0WindowsParserProcessSandboxError(
                f"source inventory entry kind mismatch: {name}"
            )
        if attributes & reparse_flag or int(item["reparse_tag"]):
            raise P0WindowsParserProcessSandboxError(
                f"source inventory entry is a reparse point: {name}"
            )

    require("llm_batch", src, directory=True)
    require("__init__.py", package, directory=False)
    require("grounding", package, directory=True)
    require("__init__.py", grounding, directory=False)
    require("p0_parser_process_worker.py", grounding, directory=False)
    require("p0_parser_process_protocol.py", grounding, directory=False)

    def reject_candidates(
        values: Mapping[str, dict[str, Any]], stems: tuple[str, ...], role: str
    ) -> None:
        expected = {
            "llm_batch": {"llm_batch"},
            "grounding": {"grounding"},
            "__init__": {"__init__.py"},
            "p0_parser_process_worker": {"p0_parser_process_worker.py"},
            "p0_parser_process_protocol": {"p0_parser_process_protocol.py"},
        }
        for name in values:
            folded = unicodedata.normalize("NFC", name).casefold()
            for stem in stems:
                candidates = {stem.casefold()}
                candidates.update((stem + suffix).casefold() for suffix in suffixes)
                if folded in candidates and name not in expected[stem]:
                    raise P0WindowsParserProcessSandboxError(
                        f"alternate import candidate in {role}: {name}"
                    )

    reject_candidates(src, ("llm_batch",), "src")
    reject_candidates(package, ("__init__", "grounding"), "llm_batch")
    reject_candidates(
        grounding,
        ("__init__", "p0_parser_process_worker", "p0_parser_process_protocol"),
        "grounding",
    )
    return suffixes


def _read_held_file_bytes(api: _Win32, item: _PinnedFile) -> bytes:
    before = _query_snapshot(api, item.handle, streams=True, label=item.role)
    if not _identity._snapshot_stable(item.snapshot, before):
        raise P0WindowsParserProcessSandboxError(
            f"held source changed before AST read: {item.role}"
        )
    _seek_handle_start(api, item.handle, item.role)
    try:
        raw = _identity._read_handle_exact(
            api, item.handle, before.standard[1], item.role
        )
    except BaseException as exc:
        raise _identity_error(f"AST read {item.role}", exc) from exc
    finally:
        _seek_handle_start(api, item.handle, item.role)
    return raw


def _source_import_graph(
    api: _Win32, files: tuple[_PinnedFile, ...]
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    project_edges: list[tuple[str, str]] = []
    forbidden_names = {"__import__", "eval", "exec", "compile"}
    forbidden_attributes = {
        "import_module", "spec_from_file_location", "run_module", "run_path",
        "load_module", "exec_module", "module_from_spec", "find_loader",
    }
    guarded_pathfinder_calls = 0
    for item in files:
        if not item.project_source_candidate:
            continue
        try:
            tree = ast.parse(_read_held_file_bytes(api, item), filename=item.role)
        except (SyntaxError, ValueError) as exc:
            raise P0WindowsParserProcessSandboxError(
                f"source AST parse failed: {item.role}"
            ) from exc
        if item.role == "worker_source_candidate":
            rendered_calls = [
                (node.lineno, ast.unparse(node.func))
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
            ]
            required_static_call_order = (
                "_prepare_direct_script_runtime",
                "guard.verify_complete",
                "guard.attestation",
                "execute_request_bytes",
            )
            positions: list[int] = []
            for required in required_static_call_order:
                matches = [line for line, rendered in rendered_calls if rendered == required]
                if len(matches) != 1:
                    raise P0WindowsParserProcessSandboxError(
                        f"worker guard static call count is not exact: {required}"
                    )
                positions.append(matches[0])
            if positions != sorted(positions) or len(set(positions)) != len(positions):
                raise P0WindowsParserProcessSandboxError(
                    "worker guard static call order is not exact"
                )
            mutation_calls = [
                rendered
                for _line, rendered in rendered_calls
                if rendered.startswith("sys.meta_path.")
                or rendered.startswith("sys.path.")
            ]
            if mutation_calls != ["sys.meta_path.insert", "sys.path.insert"]:
                raise P0WindowsParserProcessSandboxError(
                    "worker import-path mutation set is not exact"
                )
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Delete)):
                    targets: list[ast.AST] = []
                    if isinstance(node, ast.Assign):
                        targets.extend(node.targets)
                    elif isinstance(node, ast.Delete):
                        targets.extend(node.targets)
                    else:
                        targets.append(node.target)
                    if any(
                        ast.unparse(target) in {"sys.meta_path", "sys.path"}
                        for target in targets
                    ):
                        raise P0WindowsParserProcessSandboxError(
                            "worker direct import-path assignment is forbidden"
                        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    rows.append(
                        {"source_role": item.role, "kind": "import", "module": alias.name}
                    )
                    if alias.name == "llm_batch" or alias.name.startswith("llm_batch."):
                        project_edges.append((item.role, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0 or any(alias.name == "*" for alias in node.names):
                    raise P0WindowsParserProcessSandboxError(
                        f"relative/star import forbidden: {item.role}"
                    )
                module = node.module or ""
                rows.append(
                    {
                        "source_role": item.role,
                        "kind": "from",
                        "module": module,
                        "names": sorted(alias.name for alias in node.names),
                    }
                )
                if module == "llm_batch" or module.startswith("llm_batch."):
                    project_edges.append((item.role, module))
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                    forbidden = name in forbidden_names
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    forbidden = name in forbidden_attributes
                    if name == "find_spec":
                        rendered = ast.unparse(node.func)
                        if (
                            item.role != "worker_source_candidate"
                            or rendered
                            != "importlib.machinery.PathFinder.find_spec"
                        ):
                            forbidden = True
                        else:
                            guarded_pathfinder_calls += 1
                            rows.append(
                                {
                                    "source_role": item.role,
                                    "kind": "guarded_pathfinder_delegate",
                                    "module": rendered,
                                }
                            )
                else:
                    name = ""
                    forbidden = False
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "setattr", "delattr"
                }:
                    forbidden = True
                    name = node.func.id
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                    and node.args
                    and ast.unparse(node.args[0]).startswith("importlib")
                ):
                    forbidden = True
                    name = "getattr(importlib)"
                if forbidden:
                    raise P0WindowsParserProcessSandboxError(
                        f"dynamic code/import API forbidden: {item.role}:{name}"
                    )
    expected_edge = (
        "worker_source_candidate",
        "llm_batch.grounding.p0_parser_process_protocol",
    )
    if project_edges != [expected_edge]:
        raise P0WindowsParserProcessSandboxError(
            "project source AST import edge set is not exact"
        )
    if guarded_pathfinder_calls != 1:
        raise P0WindowsParserProcessSandboxError(
            "worker guarded PathFinder delegation count is not exact"
        )
    return tuple(sorted(rows, key=protocol.canonical_file_bytes))


def _pin_one(
    api: _Win32,
    *,
    role: str,
    path: Path,
    immediate_parent: _NamespaceGuard,
    project_source_candidate: bool,
) -> _PinnedFile:
    leaf = path.name
    if (
        not path.is_absolute()
        or not leaf
        or leaf in {".", ".."}
        or ":" in leaf
        or leaf.endswith((".", " "))
        or "\x00" in str(path)
    ):
        raise P0WindowsParserProcessSandboxError(
            f"launch file path is not one canonical local path: {path}"
        )
    handle = api.CreateFileW(
        str(path),
        _GENERIC_READ | _FILE_READ_ATTRIBUTES,
        _FILE_SHARE_READ,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_SEQUENTIAL_SCAN,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        raise _win_error(f"CreateFileW({path})")
    try:
        snapshot = _query_snapshot(api, int(handle), streams=True, label=role)
        try:
            _identity._assert_regular_single_link(snapshot, role)
            if snapshot.volume_serial != immediate_parent.snapshot.volume_serial:
                raise P0WindowsParserProcessSandboxError(
                    f"launch file crosses its pinned parent volume: {role}"
                )
            _identity._assert_direct_final_path_descendant(
                immediate_parent.snapshot.final_path, snapshot.final_path, role
            )
        except P0WindowsParserProcessSandboxError:
            raise
        except BaseException as exc:
            raise _identity_error(role, exc) from exc
        sha256 = _hash_held_file(api, int(handle), snapshot, role)
        return _PinnedFile(
            role=role,
            path=path,
            handle=int(handle),
            snapshot=snapshot,
            sha256=sha256,
            project_source_candidate=project_source_candidate,
        )
    except BaseException:
        _close(api, handle)
        raise


def _file_material(item: _PinnedFile) -> dict[str, Any]:
    return {
        "role": item.role,
        "path": str(item.path),
        "final_path": item.snapshot.final_path,
        "volume_serial": str(item.snapshot.volume_serial),
        "file_id": item.snapshot.file_id,
        "bytes": item.snapshot.standard[1],
        "sha256": item.sha256,
        "project_source_candidate": item.project_source_candidate,
    }


def _launch_material(
    files: tuple[_PinnedFile, ...],
    executable: Path,
    worker_path: Path,
    cache_anchor: _NamespaceGuard,
    cache_anchor_lexical_path: Path,
    cache_anchor_redirection_observed: bool,
    source_inventories: tuple[_SourceDirectoryInventory, ...],
    source_import_graph: tuple[dict[str, Any], ...],
    suffixes: tuple[str, ...],
) -> tuple[str, str]:
    project_sources = [
        _file_material(item) for item in files if item.project_source_candidate
    ]
    parser_manifest = {
        "schema_version": "p0_windows_parser_manifest_v3",
        "parser_version": PARSER_VERSION,
        "scope": "P0_CAPTURE_HASH_REQUIRED_PROJECT_SOURCE_CANDIDATES_ONLY",
        "required_project_source_candidates": project_sources,
        "source_directory_collision_inventories": [
            {
                "role": item.role,
                "path": str(item.path),
                "inventory": list(item.projection),
                "inventory_sha256": item.sha256,
            }
            for item in source_inventories
        ],
        "source_import_graph": list(source_import_graph),
        "source_import_graph_sha256": protocol.canonical_sha256(
            list(source_import_graph)
        ),
        "import_suffix_universe": list(suffixes),
        "static_import_collision_inventory_verified": True,
        "project_source_load_candidate_closure_verified": False,
        "parser_dependency_closure_verified": False,
    }
    parser_manifest_sha256 = protocol.canonical_sha256(parser_manifest)
    launch = {
        "schema_version": "p0_windows_parser_launch_v3",
        "parser_version": PARSER_VERSION,
        "launch_files": [_file_material(item) for item in files],
        "argv_template": _fixed_argv_template(executable, worker_path),
        "pycache_policy": {
            "anchor_path": str(cache_anchor.path),
            "anchor_known_folder_lexical_path": str(
                cache_anchor_lexical_path
            ),
            "known_folder_redirection_observed": (
                cache_anchor_redirection_observed
            ),
            "anchor_final_path": cache_anchor.snapshot.final_path,
            "anchor_volume_serial": str(cache_anchor.snapshot.volume_serial),
            "anchor_file_id": cache_anchor.snapshot.file_id,
            "per_execution_unique_empty_root": True,
            "bytecode_write_disabled": True,
        },
        "parent_observer_policy": {
            "schema_version": "p0_parser_parent_observer_policy_v1",
            "python_implementation": sys.implementation.name,
            "python_cache_tag": sys.implementation.cache_tag,
            "python_version": [
                sys.version_info.major,
                sys.version_info.minor,
                sys.version_info.micro,
            ],
            "directory_watch_notify_filter": _WATCH_NOTIFY_FILTER,
            "policy_source_roles": [
                "parser_sandbox_policy_source",
                "directory_watch_policy_source",
                "fixed_directory_identity_policy_source",
            ],
        },
        "parser_manifest_sha256": parser_manifest_sha256,
    }
    return parser_manifest_sha256, protocol.canonical_sha256(launch)


def _fixed_argv_template(executable: Path, worker_path: Path) -> list[str]:
    return _fixed_argv(executable, worker_path, _PYCACHE_TEMPLATE)


def _fixed_argv(
    executable: Path, worker_path: Path, pycache_root: str | Path
) -> list[str]:
    value = str(pycache_root)
    return [
        str(executable),
        "-I",
        "-S",
        "-B",
        "-X",
        f"pycache_prefix={value}",
        str(worker_path),
        f"{worker.EXPECTED_PYCACHE_PREFIX_ARGUMENT}{value}",
    ]


def _pin_launch(api: _Win32) -> _PinnedLaunch:
    caller_sys_executable = Path(sys.executable).resolve(strict=True)
    base_executable_value = getattr(sys, "_base_executable", None)
    if not isinstance(base_executable_value, str) or not os.path.isabs(
        base_executable_value
    ):
        raise P0WindowsParserProcessSandboxError(
            "sys._base_executable must identify one absolute fixed interpreter"
        )
    executable = Path(base_executable_value).resolve(strict=True)
    worker_path = Path(os.path.abspath(worker.__file__))
    protocol_path = Path(os.path.abspath(protocol.__file__))
    grounding_init_path = worker_path.parent / "__init__.py"
    llm_batch_init_path = worker_path.parents[1] / "__init__.py"
    source_directory_paths = {
        "src_directory": worker_path.parents[2],
        "llm_batch_directory": worker_path.parents[1],
        "grounding_directory": worker_path.parent,
    }
    cache_selection = _cache_anchor_path(api)
    cache_anchor_path = cache_selection.resolved_path
    sandbox_policy_path = Path(os.path.abspath(__file__))
    watch_policy_path = Path(os.path.abspath(_watch.__file__))
    identity_policy_path = Path(os.path.abspath(_identity.__file__))
    file_specs = (
        ("caller_sys_executable", caller_sys_executable, False),
        ("base_executable", executable, False),
        ("llm_batch_init_source_candidate", llm_batch_init_path, True),
        ("grounding_init_source_candidate", grounding_init_path, True),
        ("worker_source_candidate", worker_path, True),
        ("protocol_source_candidate", protocol_path, True),
        ("parser_sandbox_policy_source", sandbox_policy_path, False),
        ("directory_watch_policy_source", watch_policy_path, False),
        ("fixed_directory_identity_policy_source", identity_policy_path, False),
    )
    guards: list[_NamespaceGuard] = list(cache_selection.lexical_guards)
    files: list[_PinnedFile] = []
    try:
        ancestor_paths: dict[str, Path] = {}
        for _role, path, _project in file_specs:
            root_path, lexical_ancestors = _identity._lexical_ancestor_paths(
                str(path.parent)
            )
            for value in (*lexical_ancestors, root_path):
                ancestor_paths.setdefault(os.path.normcase(value), Path(value))
        _anchor_root, anchor_ancestors = _identity._lexical_ancestor_paths(
            str(cache_anchor_path)
        )
        for value in (*anchor_ancestors, _anchor_root):
            ancestor_paths.setdefault(os.path.normcase(value), Path(value))
        inventory_path_keys = {
            os.path.normcase(str(path)) for path in source_directory_paths.values()
        }
        existing_guard_keys = {
            os.path.normcase(str(item.path)) for item in guards
        }
        for path in sorted(ancestor_paths.values(), key=lambda value: len(value.parts)):
            if os.path.normcase(str(path)) in existing_guard_keys:
                continue
            guard = _pin_directory(
                api,
                path,
                list_directory=os.path.normcase(str(path)) in inventory_path_keys,
            )
            # Track ownership immediately so a later chain-validation failure
            # cannot leak the newly opened directory handle.
            guards.append(guard)
            existing_guard_keys.add(os.path.normcase(str(path)))
            parent_key = os.path.normcase(str(path.parent))
            if path.parent != path and parent_key in {
                os.path.normcase(str(item.path)) for item in guards
            }:
                parent = next(
                    item
                    for item in guards
                    if os.path.normcase(str(item.path)) == parent_key
                )
                if guard.snapshot.volume_serial != parent.snapshot.volume_serial:
                    raise P0WindowsParserProcessSandboxError(
                        f"namespace guard crosses volume boundary: {path}"
                    )
                try:
                    _identity._assert_direct_final_path_descendant(
                        parent.snapshot.final_path, guard.snapshot.final_path, str(path)
                    )
                except BaseException as exc:
                    raise _identity_error(f"namespace chain {path}", exc) from exc
        guard_by_path = {
            os.path.normcase(str(item.path)): item for item in guards
        }
        for role, path, project_source_candidate in file_specs:
            parent = guard_by_path.get(os.path.normcase(str(path.parent)))
            if parent is None:
                raise P0WindowsParserProcessSandboxError(
                    f"launch file immediate parent was not pinned: {path}"
                )
            files.append(
                _pin_one(
                    api,
                    role=role,
                    path=path,
                    immediate_parent=parent,
                    project_source_candidate=project_source_candidate,
                )
            )
        cache_anchor = guard_by_path.get(os.path.normcase(str(cache_anchor_path)))
        if cache_anchor is None:
            raise P0WindowsParserProcessSandboxError(
                "cache anchor was not pinned"
            )
        lexical_anchor = cache_selection.lexical_guards[-1]
        if (
            lexical_anchor.snapshot.volume_serial
            != cache_anchor.snapshot.volume_serial
            or lexical_anchor.snapshot.file_id != cache_anchor.snapshot.file_id
        ):
            raise P0WindowsParserProcessSandboxError(
                "resolved cache anchor does not reopen the held known-folder leaf"
            )
        source_inventories = tuple(
            _directory_inventory(
                api,
                guard_by_path[os.path.normcase(str(path))],
                role,
            )
            for role, path in source_directory_paths.items()
        )
        suffixes = _validate_source_collision_inventories(source_inventories)
        import_graph = _source_import_graph(api, tuple(files))
        parser_manifest_sha256, launch_sha256 = _launch_material(
            tuple(files),
            executable,
            worker_path,
            cache_anchor,
            cache_selection.lexical_path,
            cache_selection.redirection_observed,
            source_inventories,
            import_graph,
            suffixes,
        )
        by_role = {item.role: item for item in files}
        return _PinnedLaunch(
            caller_sys_executable_path=caller_sys_executable,
            caller_sys_executable_sha256=by_role["caller_sys_executable"].sha256,
            executable_path=executable,
            worker_path=worker_path,
            protocol_path=protocol_path,
            llm_batch_init_path=llm_batch_init_path,
            grounding_init_path=grounding_init_path,
            executable_sha256=by_role["base_executable"].sha256,
            worker_sha256=by_role["worker_source_candidate"].sha256,
            protocol_sha256=by_role["protocol_source_candidate"].sha256,
            llm_batch_init_sha256=by_role[
                "llm_batch_init_source_candidate"
            ].sha256,
            grounding_init_sha256=by_role[
                "grounding_init_source_candidate"
            ].sha256,
            parser_manifest_sha256=parser_manifest_sha256,
            launch_sha256=launch_sha256,
            files=tuple(files),
            namespace_guards=tuple(guards),
            cache_anchor=cache_anchor,
            cache_anchor_lexical_path=cache_selection.lexical_path,
            cache_anchor_redirection_observed=(
                cache_selection.redirection_observed
            ),
            source_directory_inventories=source_inventories,
            source_import_graph=import_graph,
            source_import_graph_sha256=protocol.canonical_sha256(
                list(import_graph)
            ),
            import_suffix_universe=suffixes,
            static_collision_inventory_verified=True,
        )
    except BaseException:
        for item in files:
            _close(api, item.handle)
        for item in guards:
            _close(api, item.handle)
        raise


def _verify_pinned_launch(api: _Win32, pinned: _PinnedLaunch) -> None:
    """Revalidate held objects and each lexical leaf without trusting path bytes."""

    for guard in pinned.namespace_guards:
        current = _query_snapshot(
            api,
            guard.handle,
            streams=False,
            label=f"revalidate namespace guard {guard.path}",
        )
        if (
            _identity._ancestor_namespace_projection(current)
            != _identity._ancestor_namespace_projection(guard.snapshot)
        ):
            raise P0WindowsParserProcessSandboxError(
                f"launch namespace guard identity changed: {guard.path}"
            )

    guard_by_path = {
        os.path.normcase(str(item.path)): item for item in pinned.namespace_guards
    }
    for expected_inventory in pinned.source_directory_inventories:
        guard = guard_by_path.get(os.path.normcase(str(expected_inventory.path)))
        if guard is None:
            raise P0WindowsParserProcessSandboxError(
                f"source inventory lost pinned directory: {expected_inventory.role}"
            )
        current_inventory = _directory_inventory(
            api, guard, expected_inventory.role
        )
        if (
            current_inventory.projection != expected_inventory.projection
            or current_inventory.sha256 != expected_inventory.sha256
        ):
            raise P0WindowsParserProcessSandboxError(
                f"source directory inventory changed: {expected_inventory.role}"
            )
    for item in pinned.files:
        if _hash_held_file(api, item.handle, item.snapshot, item.role) != item.sha256:
            raise P0WindowsParserProcessSandboxError(
                f"held launch file hash changed: {item.role}"
            )
        parent = guard_by_path.get(os.path.normcase(str(item.path.parent)))
        if parent is None:
            raise P0WindowsParserProcessSandboxError(
                f"launch file lost its pinned parent: {item.role}"
            )
        reopened = _pin_one(
            api,
            role=f"path_reopen_{item.role}",
            path=item.path,
            immediate_parent=parent,
            project_source_candidate=item.project_source_candidate,
        )
        try:
            if (
                not _identity._snapshot_stable(item.snapshot, reopened.snapshot)
                or reopened.sha256 != item.sha256
            ):
                raise P0WindowsParserProcessSandboxError(
                    f"launch lexical path no longer reopens the pinned object: {item.role}"
                )
        finally:
            _close(api, reopened.handle)


def _system_random(api: _Win32, size: int) -> bytes:
    buffer = (ctypes.c_ubyte * size)()
    status = api.BCryptGenRandom(
        None, buffer, size, _BCRYPT_USE_SYSTEM_PREFERRED_RNG
    )
    if status != 0:
        raise P0WindowsParserProcessSandboxError(
            f"BCryptGenRandom failed with NTSTATUS {status}"
        )
    return bytes(buffer)


def _assert_pycache_empty(
    api: _Win32, cache: _PinnedPycache, label: str
) -> None:
    if not cache.handle:
        raise P0WindowsParserProcessSandboxError(
            f"pycache handle is unavailable: {label}"
        )
    current = _query_snapshot(
        api, cache.handle, streams=False, label=f"pycache {label}"
    )
    if (
        _identity._ancestor_namespace_projection(current)
        != _identity._ancestor_namespace_projection(cache.snapshot)
    ):
        raise P0WindowsParserProcessSandboxError(
            f"pycache root identity changed: {label}"
        )
    try:
        entries = _identity._enumerate_directory(api, cache.handle)
    except BaseException as exc:
        raise _identity_error(f"enumerate pycache {label}", exc) from exc
    if entries:
        raise P0WindowsParserProcessSandboxError(
            f"pycache root is not empty: {label}"
        )


def _create_pinned_pycache(
    api: _Win32, pinned: _PinnedLaunch, request_sha256: str
) -> _PinnedPycache:
    current_anchor = _query_snapshot(
        api,
        pinned.cache_anchor.handle,
        streams=False,
        label="cache anchor before per-execution root",
    )
    if (
        _identity._ancestor_namespace_projection(current_anchor)
        != _identity._ancestor_namespace_projection(pinned.cache_anchor.snapshot)
    ):
        raise P0WindowsParserProcessSandboxError("cache anchor identity changed")
    path: Path | None = None
    for _attempt in range(8):
        entropy = _system_random(api, 32)
        name = "run-" + hashlib.sha256(
            b"p0-parser-pycache-v1\x00"
            + request_sha256.encode("ascii")
            + b"\x00"
            + entropy
        ).hexdigest()
        candidate = pinned.cache_anchor.path / name
        if api.CreateDirectoryW(str(candidate), None):
            path = candidate
            break
        if ctypes.get_last_error() != _ERROR_ALREADY_EXISTS:
            raise _win_error("CreateDirectoryW(per-execution pycache)")
    if path is None:
        raise P0WindowsParserProcessSandboxError(
            "could not allocate a unique per-execution pycache root"
        )
    handle = api.CreateFileW(
        str(path),
        _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES | _DELETE,
        _FILE_SHARE_READ,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        api.RemoveDirectoryW(str(path))
        raise P0WindowsParserProcessSandboxError(
            f"CreateFileW(per-execution pycache) failed with Win32 error {error}"
        )
    cache = _PinnedPycache(path=path, handle=int(handle), snapshot=None)
    try:
        snapshot = _query_snapshot(
            api, cache.handle, streams=False, label="per-execution pycache"
        )
        _identity._assert_directory(snapshot, "per-execution pycache")
        if snapshot.volume_serial != pinned.cache_anchor.snapshot.volume_serial:
            raise P0WindowsParserProcessSandboxError(
                "per-execution pycache crosses cache-anchor volume"
            )
        _identity._assert_direct_final_path_descendant(
            pinned.cache_anchor.snapshot.final_path,
            snapshot.final_path,
            "per-execution pycache",
        )
        cache.snapshot = snapshot
        _assert_pycache_empty(api, cache, "after-create")
        cache.empty_before_create = True
        return cache
    except BaseException:
        _close(api, cache.handle)
        cache.handle = 0
        api.RemoveDirectoryW(str(path))
        raise


def _cleanup_pinned_pycache(api: _Win32, cache: _PinnedPycache | None) -> None:
    if cache is None or cache.cleanup_attempted:
        return
    cache.cleanup_attempted = True
    if not cache.handle:
        return
    _assert_pycache_empty(api, cache, "before-cleanup")
    disposition = _FILE_DISPOSITION_INFO(wintypes.BOOL(True))
    if not api.SetFileInformationByHandle(
        cache.handle,
        _FILE_DISPOSITION_INFO_CLASS,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise _win_error("SetFileInformationByHandle(pycache disposition)")
    cache.disposition_set = True
    if not api.CloseHandle(cache.handle):
        raise _win_error("CloseHandle(pycache disposition handle)")
    cache.handle_close_succeeded = True
    cache.handle = 0
    attributes = api.GetFileAttributesW(str(cache.path))
    if attributes == _INVALID_FILE_ATTRIBUTES and ctypes.get_last_error() in {
        _ERROR_FILE_NOT_FOUND,
        _ERROR_PATH_NOT_FOUND,
    }:
        cache.path_absent_after_cleanup = True
        cache.cleanup_succeeded = True
    else:
        raise P0WindowsParserProcessSandboxError(
            "per-execution pycache path remained after exact-handle cleanup"
        )


def _start_interval_watches(
    pinned: _PinnedLaunch, cache: _PinnedPycache
) -> list[tuple[str, _watch.WindowsDirectoryChangeWatch]]:
    src_root = pinned.worker_path.parents[2]
    specifications = (
        ("source_parent_nonrecursive", src_root.parent, False),
        ("source_root_recursive", src_root, True),
        ("pycache_root_recursive", cache.path, True),
    )
    guards = {
        os.path.normcase(str(item.path)): item for item in pinned.namespace_guards
    }
    started: list[tuple[str, _watch.WindowsDirectoryChangeWatch]] = []
    try:
        for role, path, recursive in specifications:
            value = _watch.WindowsDirectoryChangeWatch.start(
                path,
                watch_subtree=recursive,
                notify_filter=_WATCH_NOTIFY_FILTER,
                cleanup_timeout_ms=2_000,
            )
            expected = (
                cache.snapshot
                if role == "pycache_root_recursive"
                else guards[os.path.normcase(str(path))].snapshot
            )
            if (
                value.identity.final_path.casefold()
                != expected.final_path.casefold()
                or value.identity.volume_serial != expected.volume_serial
                or value.identity.file_id != expected.file_id
            ):
                value.finalize()
                raise P0WindowsParserProcessSandboxError(
                    f"directory watch identity mismatch: {role}"
                )
            started.append((role, value))
        return started
    except BaseException:
        for _role, value in reversed(started):
            value.finalize()
        raise


def _watch_barrier(
    watches: list[tuple[str, _watch.WindowsDirectoryChangeWatch]],
    label: str,
    observations: list[dict[str, Any]],
) -> None:
    for role, value in watches:
        barrier = value.barrier()
        observations.append(
            {
                "label": label,
                "role": role,
                "counter_ns": barrier.counter_ns,
                "completion_status": barrier.completion_status,
                "request_pending_observed": barrier.request_pending_observed,
                "completion_observed": barrier.completion_observed,
                "observation_acceptable": barrier.observation_acceptable,
            }
        )
        if not barrier.observation_acceptable:
            raise P0WindowsParserProcessSandboxError(
                f"directory watch barrier failed: {label}:{role}:"
                f"{barrier.completion_status}"
            )


def _finalize_watches(
    watches: list[tuple[str, _watch.WindowsDirectoryChangeWatch]],
    outcomes: dict[str, dict[str, Any]],
) -> None:
    for role, value in reversed(watches):
        if role in outcomes:
            continue
        outcome = value.finalize()
        outcomes[role] = outcome.as_dict()


def _watches_verified(outcomes: Mapping[str, Mapping[str, Any]]) -> bool:
    expected = {
        "source_parent_nonrecursive",
        "source_root_recursive",
        "pycache_root_recursive",
    }
    return set(outcomes) == expected and all(
        item.get("project_source_directory_change_watch_observation_verified")
        is True
        for item in outcomes.values()
    )


def _cache_watch_allows_cleanup(
    watches: list[tuple[str, _watch.WindowsDirectoryChangeWatch]],
    outcomes: Mapping[str, Mapping[str, Any]],
) -> bool:
    if not any(role == "pycache_root_recursive" for role, _value in watches):
        return True
    outcome = outcomes.get("pycache_root_recursive")
    return bool(outcome and outcome.get("watch_handles_closed_observed") is True)


def _normalized_path_sha256(value: str | Path) -> str:
    normalized = os.path.normcase(os.path.abspath(os.fspath(value)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _expected_prefixed_cache_path(
    source: str | Path, prefix: str | Path, cache_tag: str
) -> Path:
    """Mirror CPython's optimization-0 pycache-prefix mapping on Windows."""

    source_path = os.path.abspath(os.fspath(source))
    _drive, tail = os.path.splitdrive(source_path)
    relative = tail.lstrip("\\/")
    directory, filename = os.path.split(relative)
    stem, extension = os.path.splitext(filename)
    if extension.casefold() not in {suffix.casefold() for suffix in importlib.machinery.SOURCE_SUFFIXES}:
        raise P0WindowsParserProcessSandboxError(
            "project source does not have a supported source suffix"
        )
    return Path(prefix) / directory / f"{stem}.{cache_tag}.pyc"


def _validate_child_runtime_guard_attestation(
    response: Mapping[str, Any],
    pinned: _PinnedLaunch,
    cache: _PinnedPycache,
) -> dict[str, Any]:
    attestation = response.get("runtime_guard_attestation")
    if response.get("child_reported_runtime_guard_completed") is not True:
        raise P0WindowsParserProcessSandboxError(
            "child runtime guard completion was not attested"
        )
    validated = protocol._validate_runtime_guard_attestation(attestation)
    expected = (
        (
            "llm_batch",
            pinned.llm_batch_init_path,
            (pinned.llm_batch_init_path.parent,),
        ),
        (
            "llm_batch.grounding",
            pinned.grounding_init_path,
            (pinned.grounding_init_path.parent,),
        ),
        (
            "llm_batch.grounding.p0_parser_process_protocol",
            pinned.protocol_path,
            (),
        ),
    )
    expected_specs = [
        {
            "module_name": name,
            "origin_sha256": _normalized_path_sha256(origin),
            "cached_path_sha256": _normalized_path_sha256(
                _expected_prefixed_cache_path(
                    origin, cache.path, sys.implementation.cache_tag
                )
            ),
            "package_location_sha256s": [
                _normalized_path_sha256(location) for location in locations
            ],
        }
        for name, origin, locations in expected
    ]
    observed_specs = [
        {
            "module_name": item["module_name"],
            "origin_sha256": item["origin_sha256"],
            "cached_path_sha256": item["cached_path_sha256"],
            "package_location_sha256s": item["package_location_sha256s"],
        }
        for item in validated["project_specs"]
    ]
    if (
        validated["python_implementation"] != sys.implementation.name
        or validated["python_cache_tag"] != sys.implementation.cache_tag
        or validated["python_version"]
        != [
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        ]
        or validated["pycache_prefix_sha256"]
        != _normalized_path_sha256(cache.path)
        or observed_specs != expected_specs
    ):
        raise P0WindowsParserProcessSandboxError(
            "child runtime guard attestation cross-binding mismatch"
        )
    return validated


def _query_suspended_process_evidence(
    api: _Win32,
    process: _PROCESS_INFORMATION,
    pinned: _PinnedLaunch,
) -> _SuspendedProcessEvidence:
    process_id = int(api.GetProcessId(process.hProcess))
    if process_id == 0:
        raise _win_error("GetProcessId")
    if process_id != int(process.dwProcessId):
        raise P0WindowsParserProcessSandboxError(
            "suspended process ID does not match PROCESS_INFORMATION"
        )

    creation = wintypes.FILETIME()
    exit_time = wintypes.FILETIME()
    kernel = wintypes.FILETIME()
    user = wintypes.FILETIME()
    if not api.GetProcessTimes(
        process.hProcess,
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        raise _win_error("GetProcessTimes(suspended child)")
    creation_time = (int(creation.dwHighDateTime) << 32) | int(
        creation.dwLowDateTime
    )
    if creation_time <= 0:
        raise P0WindowsParserProcessSandboxError(
            "suspended process creation time is invalid"
        )

    image_buffer = ctypes.create_unicode_buffer(_MAX_PROCESS_IMAGE_CHARS)
    image_chars = wintypes.DWORD(_MAX_PROCESS_IMAGE_CHARS)
    if not api.QueryFullProcessImageNameW(
        process.hProcess, 0, image_buffer, ctypes.byref(image_chars)
    ):
        raise _win_error("QueryFullProcessImageNameW(suspended child)")
    if not 0 < image_chars.value < _MAX_PROCESS_IMAGE_CHARS:
        raise P0WindowsParserProcessSandboxError(
            "suspended process image path length is invalid"
        )
    reported = image_buffer.value
    if len(reported) != image_chars.value or "\x00" in reported:
        raise P0WindowsParserProcessSandboxError(
            "suspended process image path is malformed"
        )
    reported_path = Path(reported).resolve(strict=True)
    guard_by_path = {
        os.path.normcase(str(item.path)): item for item in pinned.namespace_guards
    }
    parent = guard_by_path.get(os.path.normcase(str(reported_path.parent)))
    if parent is None:
        raise P0WindowsParserProcessSandboxError(
            "reported child image path is outside the pinned launch namespace"
        )
    reopened = _pin_one(
        api,
        role="reported_child_image",
        path=reported_path,
        immediate_parent=parent,
        project_source_candidate=False,
    )
    try:
        executable = next(
            item for item in pinned.files if item.role == "base_executable"
        )
        if (
            not _identity._snapshot_stable(executable.snapshot, reopened.snapshot)
            or reopened.sha256 != executable.sha256
        ):
            raise P0WindowsParserProcessSandboxError(
                "reported child image path did not reopen the pinned executable"
            )
        return _SuspendedProcessEvidence(
            process_id=process_id,
            creation_time_100ns=creation_time,
            reported_image_path=reported,
            reopened_image_final_path=reopened.snapshot.final_path,
            reopened_image_volume_serial=reopened.snapshot.volume_serial,
            reopened_image_file_id=reopened.snapshot.file_id,
            reopened_image_sha256=reopened.sha256,
        )
    finally:
        _close(api, reopened.handle)


def windows_parser_process_launch_bindings() -> dict[str, str]:
    """Return current fixed-launch hashes for constructing a bound request."""

    if not _IS_WINDOWS:
        raise P0WindowsParserProcessSandboxError("Windows process sandbox unavailable")
    api = _Win32()
    pinned = _pin_launch(api)
    try:
        return {
            "launch_sha256": pinned.launch_sha256,
            "parser_manifest_sha256": pinned.parser_manifest_sha256,
            "parser_version": PARSER_VERSION,
        }
    finally:
        for handle in pinned.handles:
            _close(api, handle)


def _token_buffer(api: _Win32, token: int, info_class: int) -> ctypes.Array[Any]:
    size = wintypes.DWORD()
    api.GetTokenInformation(token, info_class, None, 0, ctypes.byref(size))
    if ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER or size.value == 0:
        raise _win_error(f"GetTokenInformation({info_class}) size")
    buffer = ctypes.create_string_buffer(size.value)
    if not api.GetTokenInformation(
        token, info_class, buffer, len(buffer), ctypes.byref(size)
    ):
        raise _win_error(f"GetTokenInformation({info_class})")
    return buffer


def _privilege_name(api: _Win32, luid: _LUID) -> str:
    size = wintypes.DWORD(128)
    buffer = ctypes.create_unicode_buffer(size.value)
    if not api.LookupPrivilegeNameW(None, ctypes.byref(luid), buffer, ctypes.byref(size)):
        raise _win_error("LookupPrivilegeNameW")
    return buffer.value


def _token_group_values(buffer: ctypes.Array[Any]) -> list[_SID_AND_ATTRIBUTES]:
    count = ctypes.cast(
        buffer, ctypes.POINTER(_TOKEN_GROUPS_HEADER)
    ).contents.GroupCount
    if count > 4096:
        raise P0WindowsParserProcessSandboxError("token group count is unbounded")
    values_type = _SID_AND_ATTRIBUTES * count
    values = values_type.from_address(
        ctypes.addressof(buffer) + _TOKEN_GROUPS_HEADER.Groups.offset
    )
    return [values[index] for index in range(count)]


def _sid_in(api: _Win32, sid: int, values: list[int]) -> bool:
    return any(bool(api.EqualSid(sid, candidate)) for candidate in values)


def _create_privilege_stripped_primary_token(
    api: _Win32,
) -> tuple[int, dict[str, Any]]:
    process_token = wintypes.HANDLE()
    access = (
        _TOKEN_ASSIGN_PRIMARY
        | _TOKEN_DUPLICATE
        | _TOKEN_IMPERSONATE
        | _TOKEN_QUERY
    )
    if not api.OpenProcessToken(
        api.GetCurrentProcess(), access, ctypes.byref(process_token)
    ):
        raise _win_error("OpenProcessToken")
    restricted = wintypes.HANDLE()
    try:
        user_buffer = _token_buffer(api, process_token.value, _TOKEN_USER)
        token_user = ctypes.cast(
            user_buffer, ctypes.POINTER(_TOKEN_USER_VALUE)
        ).contents
        token_groups_buffer = _token_buffer(
            api, process_token.value, _TOKEN_GROUPS
        )
        enabled_groups = [
            group
            for group in _token_group_values(token_groups_buffer)
            if group.Attributes & _SE_GROUP_ENABLED
            and not group.Attributes & _SE_GROUP_USE_FOR_DENY_ONLY
        ]
        projection_sids: list[int] = [int(token_user.User.Sid)]
        for group in enabled_groups:
            sid = int(group.Sid)
            if not _sid_in(api, sid, projection_sids):
                projection_sids.append(sid)
        restricting_count = len(projection_sids)
        restricting_type = _SID_AND_ATTRIBUTES * restricting_count
        restricting_values = restricting_type(
            *(_SID_AND_ATTRIBUTES(sid, 0) for sid in projection_sids)
        )
        if not api.CreateRestrictedToken(
            process_token,
            _DISABLE_MAX_PRIVILEGE,
            0,
            None,
            0,
            None,
            restricting_count,
            restricting_values,
            ctypes.byref(restricted),
        ):
            raise _win_error("CreateRestrictedToken")

        token_type = wintypes.DWORD()
        returned = wintypes.DWORD()
        if not api.GetTokenInformation(
            restricted,
            _TOKEN_TYPE,
            ctypes.byref(token_type),
            ctypes.sizeof(token_type),
            ctypes.byref(returned),
        ):
            raise _win_error("GetTokenInformation(TokenType)")
        restricted_groups_buffer = _token_buffer(
            api, restricted.value, _TOKEN_RESTRICTED_SIDS
        )
        observed_restrictions = [
            int(value.Sid)
            for value in _token_group_values(restricted_groups_buffer)
        ]
        exact_projection = bool(
            len(observed_restrictions) == len(projection_sids)
            and all(_sid_in(api, sid, observed_restrictions) for sid in projection_sids)
            and all(_sid_in(api, sid, projection_sids) for sid in observed_restrictions)
        )
        exact_user_sid = _sid_in(
            api, int(token_user.User.Sid), observed_restrictions
        )
        privileges_buffer = _token_buffer(api, restricted.value, _TOKEN_PRIVILEGES)
        privileges = ctypes.cast(
            privileges_buffer, ctypes.POINTER(_TOKEN_PRIVILEGES_ONE)
        ).contents
        privilege_names = []
        if privileges.PrivilegeCount == 1:
            privilege_names.append(_privilege_name(api, privileges.Privileges[0].Luid))
        is_restricted = bool(api.IsTokenRestricted(restricted))
        privilege_stripped = bool(
            token_type.value == _TOKEN_PRIMARY
            and privileges.PrivilegeCount == 1
            and privilege_names == ["SeChangeNotifyPrivilege"]
        )
        restricted_verified = bool(
            privilege_stripped
            and is_restricted
            and exact_user_sid
            and exact_projection
        )
        if not restricted_verified:
            raise P0WindowsParserProcessSandboxError(
                "privilege-stripped primary token policy did not verify exactly"
            )
        return restricted.value, {
            "token_type_primary_verified": True,
            "is_token_restricted_api_result": is_restricted,
            "current_token_user_restricting_sid_exact_verified": exact_user_sid,
            "enabled_sid_projection_restricting_policy_verified": exact_projection,
            "enabled_token_group_sid_count": len(projection_sids) - 1,
            "restricting_sid_count": restricting_count,
            "remaining_privilege_names": privilege_names,
            "disable_max_privilege_policy_verified": True,
            "privilege_stripped_primary_token_verified": privilege_stripped,
            "restricted_primary_token_verified": restricted_verified,
            "filesystem_write_deny_verified": False,
            "network_deny_verified": False,
        }
    except BaseException:
        _close(api, restricted)
        raise
    finally:
        _close(api, process_token)


def _create_job(api: _Win32) -> tuple[int, dict[str, Any]]:
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise _win_error("CreateJobObjectW")
    try:
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        if not api.SetInformationJobObject(
            job,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            raise _win_error("SetInformationJobObject")
        observed = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        returned = wintypes.DWORD()
        if not api.QueryInformationJobObject(
            job,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(observed),
            ctypes.sizeof(observed),
            ctypes.byref(returned),
        ):
            raise _win_error("QueryInformationJobObject")
        expected_flags = (
            _JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        verified = bool(
            observed.BasicLimitInformation.LimitFlags == expected_flags
            and observed.BasicLimitInformation.ActiveProcessLimit == 1
        )
        if not verified:
            raise P0WindowsParserProcessSandboxError(
                "Job Object limit roundtrip mismatch"
            )
        return int(job), {
            "kill_on_job_close_configured_verified": True,
            "active_process_limit_one_configured_verified": True,
            "job_limit_policy_roundtrip_verified": True,
        }
    except BaseException:
        _close(api, job)
        raise


def _create_pipe_pair(api: _Win32) -> tuple[int, int]:
    read_handle = wintypes.HANDLE()
    write_handle = wintypes.HANDLE()
    security = _SECURITY_ATTRIBUTES(
        ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True
    )
    if not api.CreatePipe(
        ctypes.byref(read_handle),
        ctypes.byref(write_handle),
        ctypes.byref(security),
        0,
    ):
        raise _win_error("CreatePipe")
    return int(read_handle.value), int(write_handle.value)


def _sanitized_environment() -> tuple[ctypes.Array[Any], list[str]]:
    keep = ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP")
    environment: dict[str, str] = {
        key: os.environ[key]
        for key in keep
        if key in os.environ and "\x00" not in os.environ[key]
    }
    environment["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).resolve().parent), str(Path(os.environ["SystemRoot"]) / "System32")]
    )
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    entries = [
        f"{key}={environment[key]}" for key in sorted(environment, key=str.casefold)
    ]
    block = ctypes.create_unicode_buffer("\x00".join(entries) + "\x00\x00")
    return block, sorted(environment, key=str.casefold)


def _attribute_list(
    api: _Win32, child_handles: tuple[int, int, int]
) -> tuple[ctypes.Array[Any], Any]:
    size = ctypes.c_size_t()
    if api.InitializeProcThreadAttributeList(
        None, 1, 0, ctypes.byref(size)
    ) or ctypes.get_last_error() != _ERROR_INSUFFICIENT_BUFFER:
        raise _win_error("InitializeProcThreadAttributeList(size)")
    storage = ctypes.create_string_buffer(size.value)
    if not api.InitializeProcThreadAttributeList(
        storage, 1, 0, ctypes.byref(size)
    ):
        raise _win_error("InitializeProcThreadAttributeList")
    handle_array = (wintypes.HANDLE * 3)(*child_handles)
    if not api.UpdateProcThreadAttribute(
        storage,
        0,
        _PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
        handle_array,
        ctypes.sizeof(handle_array),
        None,
        None,
    ):
        api.DeleteProcThreadAttributeList(storage)
        raise _win_error("UpdateProcThreadAttribute(HANDLE_LIST)")
    return storage, handle_array


def _receipt(
    *,
    pinned: _PinnedLaunch,
    pycache: _PinnedPycache | None,
    watch_barriers: list[dict[str, Any]],
    watch_outcomes: Mapping[str, Mapping[str, Any]],
    runtime_guard_attestation: Mapping[str, Any] | None,
    runtime_guard_cross_binding_verified: bool,
    request_sha256: str,
    token: Mapping[str, Any],
    job: Mapping[str, Any],
    process_id: int | None,
    environment_keys: list[str],
    assigned_before_resume: bool,
    exact_handles: bool,
    launch_revalidated_before_create: bool,
    launch_revalidated_before_resume: bool,
    launch_revalidated_after_exit: bool,
    process_evidence: _SuspendedProcessEvidence | None,
    resumed: bool,
    completed: bool,
    timed_out: bool,
    overflow: bool,
    termination_observed: bool,
    exit_code: int | None,
    stdout_bytes: int,
    stderr_bytes: int,
    cross_binding: Mapping[str, Any] | None,
    diagnostic_errors: list[str],
) -> dict[str, Any]:
    material: dict[str, Any] = {
        "schema_version": SANDBOX_RECEIPT_SCHEMA,
        "platform": "windows",
        "observer": OBSERVER,
        "request_sha256": request_sha256,
        "fixed_launch": {
            "caller_sys_executable_path": str(pinned.caller_sys_executable_path),
            "caller_sys_executable_sha256": pinned.caller_sys_executable_sha256,
            "executable_path": str(pinned.executable_path),
            "executable_sha256": pinned.executable_sha256,
            "worker_path": str(pinned.worker_path),
            "worker_sha256": pinned.worker_sha256,
            "protocol_path": str(pinned.protocol_path),
            "protocol_sha256": pinned.protocol_sha256,
            "llm_batch_init_path": str(pinned.llm_batch_init_path),
            "llm_batch_init_sha256": pinned.llm_batch_init_sha256,
            "grounding_init_path": str(pinned.grounding_init_path),
            "grounding_init_sha256": pinned.grounding_init_sha256,
            "parser_manifest_sha256": pinned.parser_manifest_sha256,
            "launch_sha256": pinned.launch_sha256,
            "parser_version": PARSER_VERSION,
            "application_name": str(pinned.executable_path),
            "argv_template": _fixed_argv_template(
                pinned.executable_path, pinned.worker_path
            ),
            "argv": (
                _fixed_argv(
                    pinned.executable_path, pinned.worker_path, pycache.path
                )
                if pycache is not None
                else None
            ),
            "launch_files_path_hashed_and_handles_held_observed": False,
            "launch_files_handle_hashed_and_handles_held_observed": True,
            "launch_file_inventory": [
                _file_material(item) for item in pinned.files
            ],
            "launch_namespace_guard_count": len(pinned.namespace_guards),
            "launch_ancestor_namespace_handles_held_observed": bool(
                pinned.namespace_guards
            ),
            "required_project_source_candidate_manifest": [
                _file_material(item)
                for item in pinned.files
                if item.project_source_candidate
            ],
            "required_project_source_candidate_manifest_exact_verified": (
                {
                    item.role
                    for item in pinned.files
                    if item.project_source_candidate
                }
                == {
                    "llm_batch_init_source_candidate",
                    "grounding_init_source_candidate",
                    "worker_source_candidate",
                    "protocol_source_candidate",
                }
            ),
            "source_directory_collision_inventories": [
                {
                    "role": item.role,
                    "path": str(item.path),
                    "inventory": list(item.projection),
                    "inventory_sha256": item.sha256,
                }
                for item in pinned.source_directory_inventories
            ],
            "source_import_graph": list(pinned.source_import_graph),
            "source_import_graph_sha256": pinned.source_import_graph_sha256,
            "import_suffix_universe": list(pinned.import_suffix_universe),
            "static_import_collision_inventory_verified": (
                pinned.static_collision_inventory_verified
            ),
            "bounded_project_source_candidate_closure_blockers": [
                blocker
                for blocker, blocked in (
                    (
                        "static_import_collision_inventory_not_verified",
                        not pinned.static_collision_inventory_verified,
                    ),
                    (
                        "source_parent_cache_watch_interval_not_verified",
                        not _watches_verified(watch_outcomes),
                    ),
                    (
                        "isolated_pycache_lifecycle_not_verified",
                        not (
                            pycache is not None
                            and pycache.empty_before_create
                            and pycache.empty_before_resume
                            and pycache.empty_after_exit
                            and pycache.disposition_set
                            and pycache.handle_close_succeeded
                            and pycache.cleanup_succeeded
                            and pycache.path_absent_after_cleanup
                        ),
                    ),
                )
                if blocked
            ],
            "broader_parser_dependency_closure_blockers": [
                "trusted_cpython_runtime_prerequisite_not_independently_verified",
                "complete_python_stdlib_dependency_closure_not_verified",
                "complete_native_loader_dll_closure_not_verified",
                "actual_loaded_image_file_objects_not_verified",
                "external_owner_project_source_identity_pin_not_verified",
            ],
        },
        "isolated_pycache": {
            "policy": "UNIQUE_EMPTY_LOCALAPPDATA_ANCHOR_CHILD_V1",
            "anchor_path": str(pinned.cache_anchor.path),
            "anchor_known_folder_lexical_path": str(
                pinned.cache_anchor_lexical_path
            ),
            "known_folder_redirection_observed": (
                pinned.cache_anchor_redirection_observed
            ),
            "anchor_final_path": pinned.cache_anchor.snapshot.final_path,
            "anchor_volume_serial": str(pinned.cache_anchor.snapshot.volume_serial),
            "anchor_file_id": pinned.cache_anchor.snapshot.file_id,
            "root_path": str(pycache.path) if pycache is not None else None,
            "root_final_path": (
                pycache.snapshot.final_path
                if pycache is not None and pycache.snapshot is not None
                else None
            ),
            "root_volume_serial": (
                str(pycache.snapshot.volume_serial)
                if pycache is not None and pycache.snapshot is not None
                else None
            ),
            "root_file_id": (
                pycache.snapshot.file_id
                if pycache is not None and pycache.snapshot is not None
                else None
            ),
            "empty_before_create_verified": bool(
                pycache is not None and pycache.empty_before_create
            ),
            "empty_before_resume_verified": bool(
                pycache is not None and pycache.empty_before_resume
            ),
            "empty_after_exit_verified": bool(
                pycache is not None and pycache.empty_after_exit
            ),
            "exact_handle_cleanup_attempted": bool(
                pycache is not None and pycache.cleanup_attempted
            ),
            "delete_disposition_set_verified": bool(
                pycache is not None and pycache.disposition_set
            ),
            "disposition_handle_close_succeeded_verified": bool(
                pycache is not None and pycache.handle_close_succeeded
            ),
            "exact_handle_cleanup_succeeded": bool(
                pycache is not None and pycache.cleanup_succeeded
            ),
            "path_absent_after_cleanup_verified": bool(
                pycache is not None and pycache.path_absent_after_cleanup
            ),
            "normal_repository_pycache_lookup_excluded_observed": bool(
                pycache is not None
                and pycache.empty_before_create
                and pycache.empty_before_resume
            ),
        },
        "directory_change_observation": {
            "claim_scope": (
                "SINGLE_PENDING_REQUEST_SPANNED_INTERVAL_WITHOUT_"
                "DELIVERED_NOTIFICATION_OBSERVED"
            ),
            "notify_filter": _WATCH_NOTIFY_FILTER,
            "last_access_notifications_deliberately_excluded": True,
            "barriers": list(watch_barriers),
            "outcomes": {
                role: dict(value) for role, value in watch_outcomes.items()
            },
            "all_required_watch_intervals_verified": _watches_verified(
                watch_outcomes
            ),
            "filesystem_noninterference_inferred": False,
        },
        "restricted_primary_token": dict(token),
        "job_object": dict(job),
        "process_id": process_id,
        "exact_three_handle_list_configured_verified": exact_handles,
        "sanitized_environment_keys": environment_keys,
        "sanitized_environment_applied_verified": bool(environment_keys),
        "job_membership_before_resume_verified": assigned_before_resume,
        "launch_file_handle_and_path_identity_before_create_verified": (
            launch_revalidated_before_create
        ),
        "launch_file_handle_and_path_identity_before_resume_verified": (
            launch_revalidated_before_resume
        ),
        "launch_file_handle_and_path_identity_after_exit_verified": (
            launch_revalidated_after_exit
        ),
        "required_project_source_handles_held_across_child_execution_observed": bool(
            resumed and completed and launch_revalidated_after_exit
        ),
        "reported_child_image_path_reopened_to_pinned_executable_before_resume_verified": bool(
            process_evidence is not None
        ),
        "suspended_process_creation_identity_observed": bool(
            process_evidence is not None
        ),
        "suspended_process_identity": (
            {
                "process_id": process_evidence.process_id,
                "creation_time_100ns": str(process_evidence.creation_time_100ns),
                "reported_image_path": process_evidence.reported_image_path,
                "reopened_image_final_path": process_evidence.reopened_image_final_path,
                "reopened_image_volume_serial": str(
                    process_evidence.reopened_image_volume_serial
                ),
                "reopened_image_file_id": process_evidence.reopened_image_file_id,
                "reopened_image_sha256": process_evidence.reopened_image_sha256,
            }
            if process_evidence is not None
            else None
        ),
        "initial_thread_resumed_verified": resumed,
        "process_completed_observed": completed,
        "process_timeout_observed": timed_out,
        "pipe_bound_overflow_observed": overflow,
        "termination_after_failure_observed": termination_observed,
        "exit_code": exit_code,
        "child_exit_zero_observed": completed and exit_code == 0,
        "child_project_origin_guard_completed_observed": (
            runtime_guard_cross_binding_verified
        ),
        "child_runtime_guard_attestation": (
            dict(runtime_guard_attestation)
            if runtime_guard_attestation is not None
            else None
        ),
        "child_runtime_guard_attestation_cross_binding_verified": (
            runtime_guard_cross_binding_verified
        ),
        "bounded_project_source_load_candidate_closure_verified": bool(
            pinned.static_collision_inventory_verified
            and _watches_verified(watch_outcomes)
            and pycache is not None
            and pycache.empty_before_create
            and pycache.empty_before_resume
            and pycache.empty_after_exit
            and pycache.disposition_set
            and pycache.handle_close_succeeded
            and pycache.cleanup_succeeded
            and pycache.path_absent_after_cleanup
            and launch_revalidated_before_create
            and launch_revalidated_before_resume
            and launch_revalidated_after_exit
            and assigned_before_resume
            and exact_handles
            and resumed
            and completed
            and exit_code == 0
            and stderr_bytes == 0
            and runtime_guard_cross_binding_verified
            and cross_binding
            and cross_binding.get("child_response_exact_cross_binding_verified")
            is True
        ),
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
        "stdout_within_bound_observed": stdout_bytes <= protocol.MAX_RESPONSE_BYTES,
        "stderr_within_bound_observed": stderr_bytes <= MAX_STDERR_BYTES,
        "stderr_empty_observed": stderr_bytes == 0,
        "canonical_child_response_exact_cross_binding_verified": bool(
            cross_binding
            and cross_binding.get("child_response_exact_cross_binding_verified")
            is True
        ),
        "parent_cross_binding_receipt": dict(cross_binding) if cross_binding else None,
        "diagnostic_errors": diagnostic_errors,
        **{field: False for field in _FALSE_FIELDS},
        "credited_counts": {
            "actual_source_claim_count": 0,
            "actual_a_context_review_count": 0,
        },
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": protocol.canonical_sha256(material)}


def _execute_windows_parser_process_sandbox_once(
    request_raw: bytes,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute the fixed capture-hash worker under bounded Windows controls."""

    if not _IS_WINDOWS:
        raise P0WindowsParserProcessSandboxError("Windows process sandbox unavailable")
    if type(request_raw) is not bytes:
        raise P0WindowsParserProcessSandboxError("request_raw must be exact bytes")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not 0 < float(timeout_seconds) <= MAX_TIMEOUT_SECONDS
    ):
        raise P0WindowsParserProcessSandboxError(
            f"timeout_seconds must be within (0,{MAX_TIMEOUT_SECONDS}]"
        )
    request = protocol.parse_request_bytes(request_raw)
    api = _Win32()
    pinned = _pin_launch(api)
    request_sha256 = hashlib.sha256(request_raw).hexdigest()
    pycache: _PinnedPycache | None = None
    watches: list[tuple[str, _watch.WindowsDirectoryChangeWatch]] = []
    watch_barriers: list[dict[str, Any]] = []
    watch_outcomes: dict[str, dict[str, Any]] = {}
    runtime_guard_attestation: dict[str, Any] | None = None
    runtime_guard_cross_binding_verified = False
    token_handle = 0
    job_handle = 0
    process = _PROCESS_INFORMATION()
    all_pipe_handles: set[int] = set()
    attribute_storage: ctypes.Array[Any] | None = None
    token_receipt: dict[str, Any] = {}
    job_receipt: dict[str, Any] = {}
    environment_keys: list[str] = []
    assigned_before_resume = False
    exact_handles = False
    launch_revalidated_before_create = False
    launch_revalidated_before_resume = False
    launch_revalidated_after_exit = False
    process_evidence: _SuspendedProcessEvidence | None = None
    resumed = False
    completed = False
    timed_out = False
    overflow = False
    termination_observed = False
    exit_code: int | None = None
    stdout = bytearray()
    stderr = bytearray()
    cross_binding: dict[str, Any] | None = None
    diagnostics: list[str] = []
    fd_values: list[int] = []
    try:
        if (
            request["launch_sha256"] != pinned.launch_sha256
            or request["parser_manifest_sha256"]
            != pinned.parser_manifest_sha256
            or request["parser_version"] != PARSER_VERSION
        ):
            raise P0WindowsParserProcessSandboxError(
                "request fixed-launch binding mismatch"
            )
        pycache = _create_pinned_pycache(api, pinned, request_sha256)
        watches = _start_interval_watches(pinned, pycache)
        _watch_barrier(watches, "armed_before_pre_inventory", watch_barriers)
        _verify_pinned_launch(api, pinned)
        _assert_pycache_empty(api, pycache, "watched-pre-inventory")
        token_handle, token_receipt = _create_privilege_stripped_primary_token(
            api
        )
        job_handle, job_receipt = _create_job(api)

        stdin_read, stdin_write = _create_pipe_pair(api)
        stdout_read, stdout_write = _create_pipe_pair(api)
        stderr_read, stderr_write = _create_pipe_pair(api)
        all_pipe_handles.update(
            (stdin_read, stdin_write, stdout_read, stdout_write, stderr_read, stderr_write)
        )
        for parent_end in (stdin_write, stdout_read, stderr_read):
            if not api.SetHandleInformation(
                parent_end, _HANDLE_FLAG_INHERIT, 0
            ):
                raise _win_error("SetHandleInformation(parent pipe end)")
        child_handles = (stdin_read, stdout_write, stderr_write)
        attribute_storage, handle_array = _attribute_list(api, child_handles)
        exact_handles = len(handle_array) == 3
        environment, environment_keys = _sanitized_environment()

        startup = _STARTUPINFOEXW()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.StartupInfo.dwFlags = _STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput = stdin_read
        startup.StartupInfo.hStdOutput = stdout_write
        startup.StartupInfo.hStdError = stderr_write
        startup.lpAttributeList = ctypes.cast(attribute_storage, ctypes.c_void_p)
        command = ctypes.create_unicode_buffer(
            subprocess.list2cmdline(
                _fixed_argv(
                    pinned.executable_path, pinned.worker_path, pycache.path
                )
            )
        )
        flags = (
            _CREATE_SUSPENDED
            | _CREATE_UNICODE_ENVIRONMENT
            | _EXTENDED_STARTUPINFO_PRESENT
            | _CREATE_NO_WINDOW
        )
        _verify_pinned_launch(api, pinned)
        _assert_pycache_empty(api, pycache, "immediately-before-create")
        _watch_barrier(watches, "immediately_before_create", watch_barriers)
        pycache.empty_before_create = True
        launch_revalidated_before_create = True
        if not api.CreateProcessAsUserW(
            token_handle,
            str(pinned.executable_path),
            command,
            None,
            None,
            True,
            flags,
            environment,
            str(pinned.worker_path.parent),
            ctypes.cast(ctypes.byref(startup), ctypes.POINTER(_STARTUPINFOW)),
            ctypes.byref(process),
        ):
            raise _win_error("CreateProcessAsUserW")
        for child_end in child_handles:
            _close(api, child_end)
            all_pipe_handles.discard(child_end)
        if not api.AssignProcessToJobObject(job_handle, process.hProcess):
            raise _win_error("AssignProcessToJobObject")
        in_job = wintypes.BOOL()
        if not api.IsProcessInJob(
            process.hProcess, job_handle, ctypes.byref(in_job)
        ) or not in_job.value:
            raise _win_error("IsProcessInJob")
        assigned_before_resume = True
        process_evidence = _query_suspended_process_evidence(api, process, pinned)
        _verify_pinned_launch(api, pinned)
        _assert_pycache_empty(api, pycache, "immediately-before-resume")
        _watch_barrier(watches, "immediately_before_resume", watch_barriers)
        pycache.empty_before_resume = True
        launch_revalidated_before_resume = True

        import msvcrt

        stdin_fd = msvcrt.open_osfhandle(stdin_write, os.O_WRONLY | os.O_BINARY)
        stdout_fd = msvcrt.open_osfhandle(stdout_read, os.O_RDONLY | os.O_BINARY)
        stderr_fd = msvcrt.open_osfhandle(stderr_read, os.O_RDONLY | os.O_BINARY)
        fd_values.extend((stdin_fd, stdout_fd, stderr_fd))
        for transferred in (stdin_write, stdout_read, stderr_read):
            all_pipe_handles.discard(transferred)

        io_errors: list[str] = []
        overflow_event = threading.Event()

        def write_request() -> None:
            try:
                offset = 0
                while offset < len(request_raw):
                    offset += os.write(stdin_fd, request_raw[offset : offset + 65536])
            except BaseException as exc:
                io_errors.append(f"stdin:{type(exc).__name__}:{exc}")
            finally:
                try:
                    os.close(stdin_fd)
                except OSError:
                    pass

        def read_bounded(fd: int, target: bytearray, maximum: int, label: str) -> None:
            try:
                while True:
                    chunk = os.read(fd, 65536)
                    if not chunk:
                        break
                    target.extend(chunk)
                    if len(target) > maximum:
                        overflow_event.set()
                        break
            except BaseException as exc:
                io_errors.append(f"{label}:{type(exc).__name__}:{exc}")
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass

        threads = [
            threading.Thread(target=write_request, daemon=True),
            threading.Thread(
                target=read_bounded,
                args=(stdout_fd, stdout, protocol.MAX_RESPONSE_BYTES, "stdout"),
                daemon=True,
            ),
            threading.Thread(
                target=read_bounded,
                args=(stderr_fd, stderr, MAX_STDERR_BYTES, "stderr"),
                daemon=True,
            ),
        ]
        for thread in threads[1:]:
            thread.start()
        previous_suspend_count = api.ResumeThread(process.hThread)
        if previous_suspend_count == 0xFFFFFFFF:
            raise _win_error("ResumeThread")
        if previous_suspend_count != 1:
            raise P0WindowsParserProcessSandboxError(
                "ResumeThread returned an unexpected suspend count"
            )
        resumed = True
        threads[0].start()

        deadline = time.monotonic() + float(timeout_seconds)
        failure_reason: str | None = None
        while True:
            if overflow_event.is_set():
                overflow = True
                failure_reason = "pipe bound exceeded"
                break
            if io_errors:
                failure_reason = "pipe I/O failed"
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                failure_reason = "parser subprocess timed out"
                break
            wait_ms = max(1, min(50, int(remaining * 1000)))
            wait_result = api.WaitForSingleObject(process.hProcess, wait_ms)
            if wait_result == _WAIT_OBJECT_0:
                completed = True
                break
            if wait_result != _WAIT_TIMEOUT:
                failure_reason = f"WaitForSingleObject returned {wait_result}"
                break
        if failure_reason is not None:
            diagnostics.append(failure_reason)
            if not api.TerminateJobObject(job_handle, 0xEE):
                diagnostics.append(
                    f"TerminateJobObject:{ctypes.get_last_error()}"
                )
            termination_observed = (
                api.WaitForSingleObject(process.hProcess, 5000) == _WAIT_OBJECT_0
            )
            if not termination_observed:
                if not api.TerminateProcess(process.hProcess, 0xEE):
                    diagnostics.append(
                        f"TerminateProcess:fallback:{ctypes.get_last_error()}"
                    )
                termination_observed = (
                    api.WaitForSingleObject(process.hProcess, 5000)
                    == _WAIT_OBJECT_0
                )
            completed = termination_observed

        for thread in threads:
            thread.join(5.0)
        if any(thread.is_alive() for thread in threads):
            diagnostics.append("pipe thread did not terminate")
        diagnostics.extend(io_errors)

        code = wintypes.DWORD()
        if completed and api.GetExitCodeProcess(process.hProcess, ctypes.byref(code)):
            exit_code = int(code.value)
        elif completed:
            diagnostics.append(f"GetExitCodeProcess:{ctypes.get_last_error()}")
        if exit_code == _STILL_ACTIVE:
            diagnostics.append("exit code remained STILL_ACTIVE")
        if completed:
            _assert_pycache_empty(api, pycache, "after-child-exit")
            pycache.empty_after_exit = True

        if failure_reason is not None or diagnostics:
            raise P0WindowsParserProcessSandboxError(failure_reason or diagnostics[0])
        if exit_code != 0:
            diagnostics.append(f"child exit code {exit_code}")
            raise P0WindowsParserProcessSandboxError(
                f"parser subprocess exited with code {exit_code}"
            )
        if stderr:
            diagnostics.append("child stderr was not empty")
            raise P0WindowsParserProcessSandboxError(
                "parser subprocess emitted stderr"
            )
        cross_binding = protocol.validate_response_against_request(
            bytes(stdout), request_raw
        )
        response = protocol.validate_response_bytes(bytes(stdout))
        runtime_guard_attestation = _validate_child_runtime_guard_attestation(
            response, pinned, pycache
        )
        runtime_guard_cross_binding_verified = True
        _verify_pinned_launch(api, pinned)
        launch_revalidated_after_exit = True
        _watch_barrier(watches, "after_post_inventory", watch_barriers)
        _finalize_watches(watches, watch_outcomes)
        if not _watches_verified(watch_outcomes):
            raise P0WindowsParserProcessSandboxError(
                "directory watch interval did not verify"
            )
        _cleanup_pinned_pycache(api, pycache)
        receipt = _receipt(
            pinned=pinned,
            pycache=pycache,
            watch_barriers=watch_barriers,
            watch_outcomes=watch_outcomes,
            runtime_guard_attestation=runtime_guard_attestation,
            runtime_guard_cross_binding_verified=(
                runtime_guard_cross_binding_verified
            ),
            request_sha256=request_sha256,
            token=token_receipt,
            job=job_receipt,
            process_id=int(process.dwProcessId),
            environment_keys=environment_keys,
            assigned_before_resume=assigned_before_resume,
            exact_handles=exact_handles,
            launch_revalidated_before_create=launch_revalidated_before_create,
            launch_revalidated_before_resume=launch_revalidated_before_resume,
            launch_revalidated_after_exit=launch_revalidated_after_exit,
            process_evidence=process_evidence,
            resumed=resumed,
            completed=completed,
            timed_out=timed_out,
            overflow=overflow,
            termination_observed=termination_observed,
            exit_code=exit_code,
            stdout_bytes=len(stdout),
            stderr_bytes=len(stderr),
            cross_binding=cross_binding,
            diagnostic_errors=diagnostics,
        )
        return response, receipt
    except BaseException as exc:
        if process.hProcess and not completed:
            if job_handle and assigned_before_resume:
                api.TerminateJobObject(job_handle, 0xEE)
            else:
                api.TerminateProcess(process.hProcess, 0xEE)
            termination_observed = (
                api.WaitForSingleObject(process.hProcess, 5000) == _WAIT_OBJECT_0
            )
            if not termination_observed:
                api.TerminateProcess(process.hProcess, 0xEE)
                termination_observed = (
                    api.WaitForSingleObject(process.hProcess, 5000)
                    == _WAIT_OBJECT_0
                )
        if pycache is not None and (completed or termination_observed):
            try:
                _assert_pycache_empty(api, pycache, "after-failed-child-exit")
                pycache.empty_after_exit = True
            except BaseException as cache_exc:
                diagnostics.append(
                    f"pycache-post-failure:{type(cache_exc).__name__}:{cache_exc}"
                )
        try:
            _finalize_watches(watches, watch_outcomes)
        except BaseException as watch_exc:
            diagnostics.append(
                f"watch-finalize:{type(watch_exc).__name__}:{watch_exc}"
            )
        try:
            if _cache_watch_allows_cleanup(watches, watch_outcomes):
                _cleanup_pinned_pycache(api, pycache)
            else:
                diagnostics.append(
                    "pycache-cleanup-skipped:watch-handle-not-closed"
                )
        except BaseException as cache_exc:
            diagnostics.append(
                f"pycache-cleanup:{type(cache_exc).__name__}:{cache_exc}"
            )
        failure_receipt = _receipt(
            pinned=pinned,
            pycache=pycache,
            watch_barriers=watch_barriers,
            watch_outcomes=watch_outcomes,
            runtime_guard_attestation=runtime_guard_attestation,
            runtime_guard_cross_binding_verified=(
                runtime_guard_cross_binding_verified
            ),
            request_sha256=request_sha256,
            token=token_receipt,
            job=job_receipt,
            process_id=int(process.dwProcessId) if process.dwProcessId else None,
            environment_keys=environment_keys,
            assigned_before_resume=assigned_before_resume,
            exact_handles=exact_handles,
            launch_revalidated_before_create=launch_revalidated_before_create,
            launch_revalidated_before_resume=launch_revalidated_before_resume,
            launch_revalidated_after_exit=launch_revalidated_after_exit,
            process_evidence=process_evidence,
            resumed=resumed,
            completed=completed,
            timed_out=timed_out,
            overflow=overflow,
            termination_observed=termination_observed,
            exit_code=exit_code,
            stdout_bytes=len(stdout),
            stderr_bytes=len(stderr),
            cross_binding=cross_binding,
            diagnostic_errors=diagnostics + [str(exc)],
        )
        if isinstance(exc, P0WindowsParserProcessSandboxError):
            if exc.receipt is None:
                exc.receipt = failure_receipt
            raise
        raise P0WindowsParserProcessSandboxError(
            str(exc), failure_receipt
        ) from exc
    finally:
        if attribute_storage is not None:
            api.DeleteProcThreadAttributeList(attribute_storage)
        for fd in fd_values:
            try:
                os.close(fd)
            except OSError:
                pass
        for handle in all_pipe_handles:
            _close(api, handle)
        _close(api, process.hThread)
        _close(api, process.hProcess)
        _close(api, token_handle)
        _close(api, job_handle)
        if pycache is not None and pycache.handle:
            _close(api, pycache.handle)
            pycache.handle = 0
        for handle in pinned.handles:
            _close(api, handle)


def execute_windows_parser_process_sandbox(
    request_raw: bytes,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute the fixed worker once under the enabled-SID projection policy.

    There is deliberately no retry with a weaker token.  A child-controlled
    exit code cannot prove that image-loader ACLs, rather than worker behavior,
    caused a failure, so any nonzero exit remains a terminal NO_GO receipt.
    """

    return _execute_windows_parser_process_sandbox_once(
        request_raw,
        timeout_seconds=timeout_seconds,
    )


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "GATE_STATUS",
    "MAX_STDERR_BYTES",
    "MAX_TIMEOUT_SECONDS",
    "P0WindowsParserProcessSandboxError",
    "SANDBOX_RECEIPT_SCHEMA",
    "execute_windows_parser_process_sandbox",
    "windows_parser_process_launch_bindings",
]
