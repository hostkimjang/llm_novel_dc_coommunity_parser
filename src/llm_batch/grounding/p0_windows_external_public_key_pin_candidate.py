"""Windows ACL-bound external public-key pin *candidate* supervisor.

The public entry point never accepts public-key pin bytes, an owner SID, an
expected file identity, or a previously serialized observation receipt.  It
opens one fixed-name pin file from a dedicated directory, keeps the file and
every lexical ancestor pinned by non-delete-shared handles, observes the file
and parent security descriptors, and passes the exact handle-read bytes to the
existing asymmetric OWNER_STATE supervisor in the same call.

This is deliberately a candidate component.  The caller still selects the pin
store path and there is no independently provisioned owner-policy state.  A
successful receipt therefore does not establish external provisioning, owner
authority, rollback protection, P0 exit, or production approval.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import p0_actual_owner_root_preauthorization as preauth
from . import p0_external_owner_asymmetric_signature as asymmetric
from . import p0_external_owner_state_supervisor as owner_state
from . import p0_windows_directory_change_watch as directory_watch
from . import p0_windows_fixed_directory_identity as fixed
from . import p0_windows_runtime_evidence as runtime


PUBLIC_KEY_PIN_FILENAME = "p0_external_owner_public_key_pin_v1.json"
CANDIDATE_RECEIPT_SCHEMA = (
    "p0_windows_external_public_key_pin_candidate_receipt_v1"
)
SUPERVISOR_RECEIPT_SCHEMA = (
    "p0_windows_external_public_key_pin_candidate_supervisor_receipt_v1"
)
GATE_STATUS = (
    "WINDOWS_ACL_BOUND_PIN_CANDIDATE_OWNER_STATE_PASS_"
    "INDEPENDENT_PROVISIONING_NO_GO"
)

_IS_WINDOWS = os.name == "nt"
_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x00000001
_GROUP_SECURITY_INFORMATION = 0x00000002
_DACL_SECURITY_INFORMATION = 0x00000004
_SECURITY_INFORMATION = (
    _OWNER_SECURITY_INFORMATION
    | _GROUP_SECURITY_INFORMATION
    | _DACL_SECURITY_INFORMATION
)
_SDDL_REVISION_1 = 1
_SE_DACL_PRESENT = 0x0004
_SE_DACL_PROTECTED = 0x1000

_TOKEN_DUPLICATE = 0x0002
_TOKEN_QUERY = 0x0008
_SECURITY_IMPERSONATION = 2

_DELETE = 0x00010000
_READ_CONTROL = 0x00020000
_WRITE_DAC = 0x00040000
_WRITE_OWNER = 0x00080000
_SYNCHRONIZE = 0x00100000
_FILE_READ_DATA = 0x0001
_FILE_WRITE_DATA = 0x0002
_FILE_APPEND_DATA = 0x0004
_FILE_READ_EA = 0x0008
_FILE_WRITE_EA = 0x0010
_FILE_EXECUTE = 0x0020
_FILE_DELETE_CHILD = 0x0040
_FILE_READ_ATTRIBUTES = 0x0080
_FILE_WRITE_ATTRIBUTES = 0x0100
_FILE_GENERIC_READ = (
    _READ_CONTROL
    | _FILE_READ_DATA
    | _FILE_READ_ATTRIBUTES
    | _FILE_READ_EA
    | _SYNCHRONIZE
)
_FILE_GENERIC_WRITE = (
    _READ_CONTROL
    | _FILE_WRITE_DATA
    | _FILE_APPEND_DATA
    | _FILE_WRITE_EA
    | _FILE_WRITE_ATTRIBUTES
    | _SYNCHRONIZE
)
_FILE_GENERIC_EXECUTE = (
    _READ_CONTROL | _FILE_EXECUTE | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE
)
_FILE_ALL_ACCESS = 0x001F01FF
_ERROR_INSUFFICIENT_BUFFER = 122
_ERROR_NO_TOKEN = 1008
_FILE_PERSISTENT_ACLS = 0x00000008

_FILE_MUTATION_RIGHTS = (
    ("FILE_WRITE_DATA", _FILE_WRITE_DATA),
    ("FILE_APPEND_DATA", _FILE_APPEND_DATA),
    ("FILE_WRITE_EA", _FILE_WRITE_EA),
    ("FILE_WRITE_ATTRIBUTES", _FILE_WRITE_ATTRIBUTES),
    ("DELETE", _DELETE),
    ("WRITE_DAC", _WRITE_DAC),
    ("WRITE_OWNER", _WRITE_OWNER),
)
_PARENT_MUTATION_RIGHTS = (
    ("FILE_ADD_FILE", _FILE_WRITE_DATA),
    ("FILE_ADD_SUBDIRECTORY", _FILE_APPEND_DATA),
    ("FILE_DELETE_CHILD", _FILE_DELETE_CHILD),
    ("FILE_WRITE_EA", _FILE_WRITE_EA),
    ("FILE_WRITE_ATTRIBUTES", _FILE_WRITE_ATTRIBUTES),
    ("DELETE", _DELETE),
    ("WRITE_DAC", _WRITE_DAC),
    ("WRITE_OWNER", _WRITE_OWNER),
)
_PIN_NOTIFY_FILTER = (
    directory_watch.FILE_NOTIFY_CHANGE_FILE_NAME
    | directory_watch.FILE_NOTIFY_CHANGE_DIR_NAME
    | directory_watch.FILE_NOTIFY_CHANGE_ATTRIBUTES
    | directory_watch.FILE_NOTIFY_CHANGE_SIZE
    | directory_watch.FILE_NOTIFY_CHANGE_LAST_WRITE
    | directory_watch.FILE_NOTIFY_CHANGE_CREATION
    | directory_watch.FILE_NOTIFY_CHANGE_SECURITY
)


class P0WindowsExternalPublicKeyPinCandidateError(ValueError):
    """The bounded pin-candidate contract could not fail closed."""


class _GENERIC_MAPPING(ctypes.Structure):
    _fields_ = [
        ("GenericRead", wintypes.DWORD),
        ("GenericWrite", wintypes.DWORD),
        ("GenericExecute", wintypes.DWORD),
        ("GenericAll", wintypes.DWORD),
    ]


_FILE_MAPPING = _GENERIC_MAPPING(
    _FILE_GENERIC_READ,
    _FILE_GENERIC_WRITE,
    _FILE_GENERIC_EXECUTE,
    _FILE_ALL_ACCESS,
)


@dataclass(frozen=True)
class _SecuritySnapshot:
    owner_sid: str
    owner_sid_sha256: str
    group_sid_sha256: str
    sddl_sha256: str
    dacl_present: bool
    dacl_null: bool
    dacl_protected: bool
    effective_token_owner_membership: bool
    mutation_access: Mapping[str, bool]

    def projection(self) -> dict[str, Any]:
        return {
            "owner_sid_sha256": self.owner_sid_sha256,
            "group_sid_sha256": self.group_sid_sha256,
            "sddl_sha256": self.sddl_sha256,
            "dacl_present": self.dacl_present,
            "dacl_null": self.dacl_null,
            "dacl_protected": self.dacl_protected,
            "effective_token_owner_membership": (
                self.effective_token_owner_membership
            ),
            "mutation_access": dict(self.mutation_access),
        }


@dataclass
class _HeldPinCandidate:
    raw: bytes
    pin: Mapping[str, Any]
    receipt: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class _SignedProtectedRootExpectation:
    root_id: str
    final_path: str
    volume_serial: int
    file_id: str

    def projection(self) -> dict[str, str]:
        return {
            "root_id": self.root_id,
            "final_path": self.final_path,
            "volume_serial": str(self.volume_serial),
            "file_id": self.file_id,
        }


@dataclass(frozen=True)
class _SignedRootExpectation:
    preauthorization_bytes_sha256: str
    packet_final_path: str
    packet_volume_serial: int
    packet_file_id: str
    protected_parent_roots: tuple[_SignedProtectedRootExpectation, ...]
    protected_category_root_ids: Mapping[str, str]
    protected_final_paths: Mapping[str, str]
    protected_volume_serials: Mapping[str, int]

    def projection(self) -> dict[str, Any]:
        return {
            "packet_root": {
                "final_path": self.packet_final_path,
                "volume_serial": str(self.packet_volume_serial),
                "file_id": self.packet_file_id,
            },
            "protected_parent_roots": [
                root.projection() for root in self.protected_parent_roots
            ],
            "protected_category_roots": [
                {
                    "category": category,
                    "root_id": self.protected_category_root_ids[category],
                    "final_path": self.protected_final_paths[category],
                    "volume_serial": str(
                        self.protected_volume_serials[category]
                    ),
                }
                for category in runtime.REQUIRED_PROTECTED_CATEGORIES
            ],
        }


class _WinSecurity:
    def __init__(self) -> None:
        if not _IS_WINDOWS:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "Windows ACL pin candidate validation is unavailable"
            )
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        self.GetSecurityInfo = advapi32.GetSecurityInfo
        self.GetSecurityInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.GetSecurityInfo.restype = wintypes.DWORD

        self.ConvertSidToStringSidW = advapi32.ConvertSidToStringSidW
        self.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self.ConvertSidToStringSidW.restype = wintypes.BOOL

        convert_sd = advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW
        self.ConvertSecurityDescriptorToStringSecurityDescriptorW = convert_sd
        convert_sd.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(wintypes.DWORD),
        ]
        convert_sd.restype = wintypes.BOOL

        self.GetSecurityDescriptorControl = advapi32.GetSecurityDescriptorControl
        self.GetSecurityDescriptorControl.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.WORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.GetSecurityDescriptorControl.restype = wintypes.BOOL

        self.OpenProcessToken = advapi32.OpenProcessToken
        self.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self.OpenProcessToken.restype = wintypes.BOOL

        self.OpenThreadToken = advapi32.OpenThreadToken
        self.OpenThreadToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.BOOL,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self.OpenThreadToken.restype = wintypes.BOOL

        self.DuplicateToken = advapi32.DuplicateToken
        self.DuplicateToken.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self.DuplicateToken.restype = wintypes.BOOL

        self.CheckTokenMembership = advapi32.CheckTokenMembership
        self.CheckTokenMembership.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.BOOL),
        ]
        self.CheckTokenMembership.restype = wintypes.BOOL

        self.AccessCheck = advapi32.AccessCheck
        self.AccessCheck.argtypes = [
            ctypes.c_void_p,
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(_GENERIC_MAPPING),
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.BOOL),
        ]
        self.AccessCheck.restype = wintypes.BOOL

        self.GetCurrentProcess = kernel32.GetCurrentProcess
        self.GetCurrentProcess.argtypes = []
        self.GetCurrentProcess.restype = wintypes.HANDLE
        self.GetCurrentThread = kernel32.GetCurrentThread
        self.GetCurrentThread.argtypes = []
        self.GetCurrentThread.restype = wintypes.HANDLE
        self.CloseHandle = kernel32.CloseHandle
        self.CloseHandle.argtypes = [wintypes.HANDLE]
        self.CloseHandle.restype = wintypes.BOOL
        self.LocalFree = kernel32.LocalFree
        self.LocalFree.argtypes = [ctypes.c_void_p]
        self.LocalFree.restype = ctypes.c_void_p

        self.GetVolumeInformationByHandleW = (
            kernel32.GetVolumeInformationByHandleW
        )
        self.GetVolumeInformationByHandleW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPWSTR,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self.GetVolumeInformationByHandleW.restype = wintypes.BOOL


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _error(label: str, code: int | None = None) -> P0WindowsExternalPublicKeyPinCandidateError:
    value = ctypes.get_last_error() if code is None else code
    return P0WindowsExternalPublicKeyPinCandidateError(
        f"{label} failed with Windows error {value}"
    )


def _free_local_handles(
    api: _WinSecurity,
    handles: Sequence[tuple[str, ctypes.c_void_p]],
    primary_error: BaseException | None,
) -> None:
    cleanup_errors: list[BaseException] = []
    for label, handle in handles:
        if not handle.value:
            continue
        try:
            remaining = api.LocalFree(handle)
            if remaining:
                cleanup_errors.append(
                    P0WindowsExternalPublicKeyPinCandidateError(
                        f"LocalFree({label}) failed"
                    )
                )
        except BaseException as exc:
            cleanup_errors.append(exc)
    if cleanup_errors and primary_error is None:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "Windows local-allocation cleanup failed"
        ) from cleanup_errors[0]


@contextmanager
def _impersonation_token(api: _WinSecurity) -> Iterator[tuple[int, str]]:
    effective = wintypes.HANDLE()
    duplicate = wintypes.HANDLE()
    source = "THREAD_IMPERSONATION_TOKEN"
    primary_error: BaseException | None = None
    try:
        if not api.OpenThreadToken(
            api.GetCurrentThread(),
            _TOKEN_QUERY | _TOKEN_DUPLICATE,
            True,
            ctypes.byref(effective),
        ):
            error = ctypes.get_last_error()
            if error != _ERROR_NO_TOKEN:
                raise _error("OpenThreadToken", error)
            if effective.value:
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "OpenThreadToken failed with a non-NULL output handle"
                )
            source = "PROCESS_PRIMARY_TOKEN_NO_THREAD_TOKEN"
            if not api.OpenProcessToken(
                api.GetCurrentProcess(),
                _TOKEN_QUERY | _TOKEN_DUPLICATE,
                ctypes.byref(effective),
            ):
                raise _error("OpenProcessToken")
        if not api.DuplicateToken(
            effective,
            _SECURITY_IMPERSONATION,
            ctypes.byref(duplicate),
        ):
            raise _error("DuplicateToken")
        yield int(duplicate.value), source
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        cleanup_errors: list[BaseException] = []
        for label, handle in (
            ("CloseHandle(impersonation token)", duplicate),
            ("CloseHandle(effective token)", effective),
        ):
            if not handle.value:
                continue
            try:
                if not api.CloseHandle(handle):
                    cleanup_errors.append(_error(label))
            except BaseException as exc:
                cleanup_errors.append(exc)
        if cleanup_errors and primary_error is None:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "effective verifier token cleanup failed"
            ) from cleanup_errors[0]


def _sid_string(api: _WinSecurity, sid: ctypes.c_void_p, label: str) -> str:
    if not sid.value:
        raise P0WindowsExternalPublicKeyPinCandidateError(f"{label} SID is absent")
    value = wintypes.LPWSTR()
    primary_error: BaseException | None = None
    try:
        if not api.ConvertSidToStringSidW(sid, ctypes.byref(value)):
            raise _error(f"ConvertSidToStringSidW({label})")
        result = value.value
        if not result or not result.startswith("S-"):
            raise P0WindowsExternalPublicKeyPinCandidateError(
                f"{label} SID string is invalid"
            )
        return result
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if value:
            _free_local_handles(
                api,
                [(label, ctypes.cast(value, ctypes.c_void_p))],
                primary_error,
            )


def _sddl_string(api: _WinSecurity, descriptor: ctypes.c_void_p) -> str:
    value = wintypes.LPWSTR()
    length = wintypes.DWORD()
    primary_error: BaseException | None = None
    try:
        if not api.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor,
            _SDDL_REVISION_1,
            _SECURITY_INFORMATION,
            ctypes.byref(value),
            ctypes.byref(length),
        ):
            raise _error("ConvertSecurityDescriptorToStringSecurityDescriptorW")
        result = value.value
        if not result or int(length.value) <= 0:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "security descriptor SDDL is empty"
            )
        return result
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if value:
            _free_local_handles(
                api,
                [("security descriptor SDDL", ctypes.cast(value, ctypes.c_void_p))],
                primary_error,
            )


def _access_check(
    api: _WinSecurity,
    descriptor: ctypes.c_void_p,
    token: int,
    desired_access: int,
) -> bool:
    size = 1024
    while size <= 65536:
        privileges = ctypes.create_string_buffer(size)
        privileges_size = wintypes.DWORD(size)
        granted = wintypes.DWORD()
        status = wintypes.BOOL()
        ok = api.AccessCheck(
            descriptor,
            token,
            desired_access,
            ctypes.byref(_FILE_MAPPING),
            privileges,
            ctypes.byref(privileges_size),
            ctypes.byref(granted),
            ctypes.byref(status),
        )
        if ok:
            return bool(status.value)
        error = ctypes.get_last_error()
        if error != _ERROR_INSUFFICIENT_BUFFER:
            raise _error("AccessCheck", error)
        size = max(size * 2, int(privileges_size.value))
    raise P0WindowsExternalPublicKeyPinCandidateError(
        "AccessCheck privilege buffer exceeded strict limit"
    )


def _query_security_snapshot(
    api: _WinSecurity,
    *,
    handle: int,
    token: int,
    rights: Sequence[tuple[str, int]],
) -> _SecuritySnapshot:
    owner = ctypes.c_void_p()
    group = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    primary_error: BaseException | None = None
    try:
        status = api.GetSecurityInfo(
            handle,
            _SE_FILE_OBJECT,
            _SECURITY_INFORMATION,
            ctypes.byref(owner),
            ctypes.byref(group),
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )
        if status != 0:
            raise _error("GetSecurityInfo", int(status))
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not api.GetSecurityDescriptorControl(
            descriptor, ctypes.byref(control), ctypes.byref(revision)
        ):
            raise _error("GetSecurityDescriptorControl")
        owner_sid = _sid_string(api, owner, "owner")
        group_sid = _sid_string(api, group, "group")
        member = wintypes.BOOL()
        if not api.CheckTokenMembership(token, owner, ctypes.byref(member)):
            raise _error("CheckTokenMembership(owner)")
        mutation_access = {
            name: _access_check(api, descriptor, token, access)
            for name, access in rights
        }
        sddl = _sddl_string(api, descriptor)
        return _SecuritySnapshot(
            owner_sid=owner_sid,
            owner_sid_sha256=hashlib.sha256(owner_sid.encode("ascii")).hexdigest(),
            group_sid_sha256=hashlib.sha256(group_sid.encode("ascii")).hexdigest(),
            sddl_sha256=hashlib.sha256(sddl.encode("utf-8")).hexdigest(),
            dacl_present=bool(control.value & _SE_DACL_PRESENT),
            dacl_null=not bool(dacl.value),
            dacl_protected=bool(control.value & _SE_DACL_PROTECTED),
            effective_token_owner_membership=bool(member.value),
            mutation_access=mutation_access,
        )
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if descriptor.value:
            _free_local_handles(
                api,
                [("security descriptor", descriptor)],
                primary_error,
            )


def _persistent_acls_supported(api: _WinSecurity, handle: int) -> bool:
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    if not api.GetVolumeInformationByHandleW(
        handle,
        None,
        0,
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        None,
        0,
    ):
        raise _error("GetVolumeInformationByHandleW")
    return bool(flags.value & _FILE_PERSISTENT_ACLS)


def _validate_security_snapshot(value: _SecuritySnapshot, label: str) -> None:
    if not value.dacl_present or value.dacl_null or not value.dacl_protected:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            f"{label} must have a present, non-NULL, protected DACL"
        )
    if value.effective_token_owner_membership:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            f"effective verifier token must not own {label}"
        )
    granted = sorted(name for name, allowed in value.mutation_access.items() if allowed)
    if granted:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            f"effective verifier token has mutation access to {label}: {granted}"
        )


def _same_security(before: _SecuritySnapshot, after: _SecuritySnapshot) -> bool:
    return before == after


def _normalise_path(path: Path | str, label: str) -> str:
    if isinstance(path, Path):
        raw = str(path)
    elif isinstance(path, str):
        raw = path
    else:
        raise P0WindowsExternalPublicKeyPinCandidateError(f"{label} is invalid")
    if (
        not raw
        or raw.startswith("\\\\")
        or "\x00" in raw
        or not os.path.isabs(raw)
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(f"{label} is invalid")
    drive, tail = os.path.splitdrive(raw)
    if not drive or drive.startswith("\\"):
        raise P0WindowsExternalPublicKeyPinCandidateError(f"{label} is invalid")
    components = [
        component
        for component in tail.replace("/", "\\").split("\\")
        if component
    ]
    if any(
        component in {".", ".."}
        or ":" in component
        or component.endswith(".")
        or component.endswith(" ")
        for component in components
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            f"{label} contains an unsafe path component"
        )
    return os.path.normpath(raw)


def _strict_protected_roots(
    value: Mapping[str, Path | str],
) -> list[tuple[str, str]]:
    if not isinstance(value, Mapping) or list(value) != list(
        runtime.REQUIRED_PROTECTED_CATEGORIES
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "protected roots must contain the exact ordered category set"
        )
    return [
        (category, _normalise_path(value[category], f"protected root {category}"))
        for category in runtime.REQUIRED_PROTECTED_CATEGORIES
    ]


def _paths_overlap(first: str, second: str) -> bool:
    left = first.rstrip("\\").casefold()
    right = second.rstrip("\\").casefold()
    return bool(
        left == right
        or left.startswith(right + "\\")
        or right.startswith(left + "\\")
    )


def _normalise_final_path_for_binding(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise P0WindowsExternalPublicKeyPinCandidateError(f"{label} is invalid")
    return value.replace("/", "\\").rstrip("\\").casefold()


def _signed_root_expectation(raw: bytes) -> _SignedRootExpectation:
    try:
        value = asymmetric._parse_canonical_json(
            raw, "owner root preauthorization"
        )
        preauth.validate_owner_root_preauthorization(
            value,
            expected_origin=preauth.ACTUAL_ORIGIN,
            key=None,
        )
    except (
        asymmetric.P0ExternalOwnerAsymmetricSignatureError,
        preauth.P0ActualOwnerRootPreauthorizationError,
    ) as exc:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "signed root expectation source is invalid"
        ) from exc

    packet = value.get("allowed_packet_root")
    protected = value.get("protected_roots")
    categories = value.get("category_root_map")
    if (
        not isinstance(packet, Mapping)
        or not isinstance(protected, list)
        or not isinstance(categories, list)
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "signed root expectation projection is invalid"
        )
    protected_by_id: dict[str, _SignedProtectedRootExpectation] = {}
    for row in protected:
        if not isinstance(row, Mapping):
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "signed protected root projection is invalid"
            )
        root_id = row.get("root_id")
        if not isinstance(root_id, str) or root_id in protected_by_id:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "signed protected root ID projection is invalid"
            )
        try:
            volume_serial = int(row.get("volume_serial_decimal"))
        except (TypeError, ValueError) as exc:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "signed protected root volume serial is invalid"
            ) from exc
        file_id = row.get("file_id_128_hex")
        if not isinstance(file_id, str):
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "signed protected root file ID is invalid"
            )
        protected_by_id[root_id] = _SignedProtectedRootExpectation(
            root_id=root_id,
            final_path=_normalise_final_path_for_binding(
                row.get("final_volume_guid_path"),
                "signed protected root final path",
            ),
            volume_serial=volume_serial,
            file_id=file_id.casefold(),
        )

    expected_categories: dict[str, str] = {}
    expected_category_root_ids: dict[str, str] = {}
    expected_category_volumes: dict[str, int] = {}
    if len(categories) != len(runtime.REQUIRED_PROTECTED_CATEGORIES):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "signed protected category count mismatch"
        )
    for index, row in enumerate(categories):
        if not isinstance(row, Mapping):
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "signed protected category projection is invalid"
            )
        category = runtime.REQUIRED_PROTECTED_CATEGORIES[index]
        if row.get("category") != category:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "signed protected category order mismatch"
            )
        root_id = row.get("root_id")
        base_projection = protected_by_id.get(root_id)
        relative = row.get("relative_root")
        if base_projection is None or not isinstance(relative, str) or not relative:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "signed protected category root reference is invalid"
            )
        expected_categories[category] = _normalise_final_path_for_binding(
            base_projection.final_path + "\\" + relative,
            f"signed protected category final path {category}",
        )
        expected_category_root_ids[category] = base_projection.root_id
        expected_category_volumes[category] = base_projection.volume_serial

    try:
        packet_serial = int(packet.get("volume_serial_decimal"))
    except (TypeError, ValueError) as exc:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "signed packet root volume serial is invalid"
        ) from exc
    packet_file_id = packet.get("file_id_128_hex")
    if not isinstance(packet_file_id, str):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "signed packet root file ID is invalid"
        )
    return _SignedRootExpectation(
        preauthorization_bytes_sha256=hashlib.sha256(raw).hexdigest(),
        packet_final_path=_normalise_final_path_for_binding(
            packet.get("final_volume_guid_path"), "signed packet root final path"
        ),
        packet_volume_serial=packet_serial,
        packet_file_id=packet_file_id.casefold(),
        protected_parent_roots=tuple(protected_by_id.values()),
        protected_category_root_ids=expected_category_root_ids,
        protected_final_paths=expected_categories,
        protected_volume_serials=expected_category_volumes,
    )


def _signed_root_binding_projection(
    forbidden_handles: Sequence[tuple[str, Any, Any]],
    protected_parent_handles: Sequence[tuple[str, Any, Any]],
    expectation: _SignedRootExpectation,
) -> dict[str, Any]:
    observed = {label: snapshot for label, _handle, snapshot in forbidden_handles}
    packet = observed.get("packet_root")
    if packet is None or (
        _normalise_final_path_for_binding(
            packet.final_path, "observed packet root final path"
        )
        != expectation.packet_final_path
        or packet.volume_serial != expectation.packet_volume_serial
        or packet.file_id.casefold() != expectation.packet_file_id
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "held packet root does not match signed preauthorization identity"
        )
    observed_parents = {
        root_id: snapshot
        for root_id, _handle, snapshot in protected_parent_handles
    }
    parent_projection: list[dict[str, Any]] = []
    for expected_parent in expectation.protected_parent_roots:
        snapshot = observed_parents.get(expected_parent.root_id)
        if snapshot is None or (
            _normalise_final_path_for_binding(
                snapshot.final_path,
                f"observed protected parent {expected_parent.root_id}",
            )
            != expected_parent.final_path
            or snapshot.volume_serial != expected_parent.volume_serial
            or snapshot.file_id.casefold() != expected_parent.file_id
        ):
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "held protected parent does not match signed preauthorization: "
                + expected_parent.root_id
            )
        parent_projection.append(
            {
                "root_id": expected_parent.root_id,
                "observed_final_path": _normalise_final_path_for_binding(
                    snapshot.final_path,
                    f"observed protected parent {expected_parent.root_id}",
                ),
                "observed_volume_serial": str(snapshot.volume_serial),
                "observed_file_id": snapshot.file_id,
            }
        )
    protected_projection: list[dict[str, Any]] = []
    for category in runtime.REQUIRED_PROTECTED_CATEGORIES:
        snapshot = observed.get(category)
        expected_path = expectation.protected_final_paths[category]
        if snapshot is None or _normalise_final_path_for_binding(
            snapshot.final_path, f"observed protected root {category}"
        ) != expected_path or (
            snapshot.volume_serial
            != expectation.protected_volume_serials[category]
        ):
            raise P0WindowsExternalPublicKeyPinCandidateError(
                f"held protected root does not match signed preauthorization: {category}"
            )
        protected_projection.append(
            {
                "category": category,
                "observed_final_path": _normalise_final_path_for_binding(
                    snapshot.final_path, f"observed protected root {category}"
                ),
                "observed_volume_serial": str(snapshot.volume_serial),
                "observed_file_id": snapshot.file_id,
            }
        )
    return {
        "signed_expectation_sha256": canonical_sha256(expectation.projection()),
        "observed_packet_root": {
            "final_path": _normalise_final_path_for_binding(
                packet.final_path, "observed packet root final path"
            ),
            "volume_serial": str(packet.volume_serial),
            "file_id": packet.file_id,
        },
        "observed_protected_parent_roots": parent_projection,
        "observed_protected_category_roots": protected_projection,
    }


def _watch_projection(outcome: Any) -> dict[str, Any]:
    return {
        "schema_version": outcome.schema_version,
        "identity": outcome.identity.as_dict(),
        "watch_subtree": outcome.watch_subtree,
        "notify_filter": outcome.notify_filter,
        "completion_status": outcome.completion_status,
        "directory_change_notification_delivered_observed": (
            outcome.directory_change_notification_delivered_observed
        ),
        "overflow_observed": outcome.overflow_observed,
        "observation_gap_observed": outcome.observation_gap_observed,
        "pending_request_until_interval_end_observed": (
            outcome.pending_request_until_interval_end_observed
        ),
        "completion_drained_observed": outcome.completion_drained_observed,
        "watch_handles_closed_observed": outcome.watch_handles_closed_observed,
        "bounded_watch_observation_verified": (
            outcome.project_source_directory_change_watch_observation_verified
        ),
    }


def _assert_watch_clean(outcome: Any, label: str) -> None:
    if (
        not outcome.project_source_directory_change_watch_observation_verified
        or outcome.directory_change_notification_delivered_observed
        or outcome.overflow_observed
        or outcome.observation_gap_observed
        or not outcome.pending_request_until_interval_end_observed
        or not outcome.completion_drained_observed
        or not outcome.watch_handles_closed_observed
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            f"{label} directory-change interval is not clean"
        )


@contextmanager
def _hold_windows_pin_candidate(
    *,
    pin_store_dir: Path | str,
    run_root: Path | str,
    packet_root: Path | str,
    protected_category_roots: Mapping[str, Path | str],
    signed_roots: _SignedRootExpectation,
) -> Iterator[_HeldPinCandidate]:
    if not _IS_WINDOWS:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "Windows ACL pin candidate validation is unavailable"
        )
    store_path = _normalise_path(pin_store_dir, "pin_store_dir")
    pin_path = os.path.join(store_path, PUBLIC_KEY_PIN_FILENAME)
    resolved_pin_path, ancestor_paths = fixed._lexical_ancestor_paths(pin_path)
    if resolved_pin_path.casefold() != os.path.abspath(pin_path).casefold():
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin path lexical normalization mismatch"
        )
    if len(ancestor_paths) < 2 or ancestor_paths[-1].casefold() != store_path.casefold():
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin store must be a dedicated non-root directory"
        )
    protected = _strict_protected_roots(protected_category_roots)
    forbidden = [
        ("run_root", _normalise_path(run_root, "run_root")),
        ("packet_root", _normalise_path(packet_root, "packet_root")),
        *protected,
    ]

    parent_watch = directory_watch.WindowsDirectoryChangeWatch.start(
        ancestor_paths[-2],
        watch_subtree=False,
        notify_filter=_PIN_NOTIFY_FILTER,
    )
    store_watch: directory_watch.WindowsDirectoryChangeWatch | None = None
    primary_error: BaseException | None = None
    try:
        store_watch = directory_watch.WindowsDirectoryChangeWatch.start(
            store_path,
            watch_subtree=False,
            notify_filter=_PIN_NOTIFY_FILTER,
        )
        api = fixed._Win32()
        security_api = _WinSecurity()
        with ExitStack() as stack, _impersonation_token(security_api) as token_state:
            token, token_source = token_state
            ancestor_handles = [
                stack.enter_context(
                    fixed._open_handle(
                        api, path, directory=True, read_data=True
                    )
                )
                for path in ancestor_paths
            ]
            pin_handle = stack.enter_context(
                fixed._open_handle(
                    api, resolved_pin_path, directory=False, read_data=True
                )
            )
            forbidden_handles: list[tuple[str, Any, Any]] = []
            for label, path in forbidden:
                handle = stack.enter_context(
                    fixed._open_handle(
                        api, path, directory=True, read_data=False
                    )
                )
                snapshot = fixed._query_snapshot(
                    api, handle.value, include_streams=False
                )
                fixed._assert_directory(snapshot, label)
                forbidden_handles.append((label, handle, snapshot))
            protected_parent_handles: list[tuple[str, Any, Any]] = []
            for expected_parent in signed_roots.protected_parent_roots:
                handle = stack.enter_context(
                    fixed._open_handle(
                        api,
                        expected_parent.final_path,
                        directory=True,
                        read_data=False,
                    )
                )
                snapshot = fixed._query_snapshot(
                    api, handle.value, include_streams=False
                )
                fixed._assert_directory(
                    snapshot, f"protected parent {expected_parent.root_id}"
                )
                protected_parent_handles.append(
                    (expected_parent.root_id, handle, snapshot)
                )
            forbidden_identities = [
                (snapshot.volume_serial, snapshot.file_id)
                for _label, _handle, snapshot in (
                    *forbidden_handles,
                    *protected_parent_handles,
                )
            ]
            if len(forbidden_identities) != len(set(forbidden_identities)):
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "run/packet/protected roots must have distinct identities"
                )
            signed_root_binding = _signed_root_binding_projection(
                forbidden_handles, protected_parent_handles, signed_roots
            )

            ancestor_before = [
                fixed._query_snapshot(api, handle.value, include_streams=False)
                for handle in ancestor_handles
            ]
            for index, snapshot in enumerate(ancestor_before):
                fixed._assert_directory(snapshot, f"pin ancestor {index}")
                if index:
                    fixed._assert_direct_final_path_descendant(
                        ancestor_before[index - 1].final_path,
                        snapshot.final_path,
                        f"pin ancestor {index}",
                    )
            store_before = ancestor_before[-1]
            pin_before = fixed._query_snapshot(
                api, pin_handle.value, include_streams=True
            )
            fixed._assert_regular_single_link(pin_before, "public-key pin")
            if not _persistent_acls_supported(security_api, pin_handle.value):
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "pin filesystem does not advertise persistent ACL support"
                )
            fixed._assert_direct_final_path_descendant(
                store_before.final_path,
                pin_before.final_path,
                "public-key pin",
            )
            if any(
                snapshot.volume_serial == store_before.volume_serial
                and _paths_overlap(snapshot.final_path, store_before.final_path)
                for _label, _handle, snapshot in (
                    *forbidden_handles,
                    *protected_parent_handles,
                )
            ):
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "pin store overlaps a held run/packet/protected root"
                )
            store_inventory_before = fixed._enumerate_directory(
                api, ancestor_handles[-1].value
            )
            fixed._validate_inventory(
                store_inventory_before, frozenset({PUBLIC_KEY_PIN_FILENAME})
            )
            fixed._assert_entry_matches_snapshot(
                store_inventory_before[PUBLIC_KEY_PIN_FILENAME],
                pin_before,
                PUBLIC_KEY_PIN_FILENAME,
            )

            parent_security_before = _query_security_snapshot(
                security_api,
                handle=ancestor_handles[-1].value,
                token=token,
                rights=_PARENT_MUTATION_RIGHTS,
            )
            file_security_before = _query_security_snapshot(
                security_api,
                handle=pin_handle.value,
                token=token,
                rights=_FILE_MUTATION_RIGHTS,
            )
            _validate_security_snapshot(parent_security_before, "pin store")
            _validate_security_snapshot(file_security_before, "pin file")
            if parent_security_before.owner_sid != file_security_before.owner_sid:
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "pin store and pin file owner SID mismatch"
                )

            raw = fixed._read_handle_exact(
                api,
                pin_handle.value,
                pin_before.standard[1],
                "public-key pin",
            )
            try:
                pin_value = asymmetric._parse_canonical_json(raw, "public-key pin")
                pin, _x, _y = asymmetric._validate_pin(pin_value)
            except asymmetric.P0ExternalOwnerAsymmetricSignatureError as exc:
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "handle-read public-key pin is invalid"
                ) from exc

            held = _HeldPinCandidate(raw=raw, pin=pin)
            try:
                yield held
            except BaseException as exc:
                primary_error = exc
                raise
            finally:
                try:
                    file_security_after = _query_security_snapshot(
                        security_api,
                        handle=pin_handle.value,
                        token=token,
                        rights=_FILE_MUTATION_RIGHTS,
                    )
                    parent_security_after = _query_security_snapshot(
                        security_api,
                        handle=ancestor_handles[-1].value,
                        token=token,
                        rights=_PARENT_MUTATION_RIGHTS,
                    )
                    pin_after = fixed._query_snapshot(
                        api, pin_handle.value, include_streams=True
                    )
                    ancestor_after = [
                        fixed._query_snapshot(
                            api, handle.value, include_streams=False
                        )
                        for handle in ancestor_handles
                    ]
                    forbidden_after = [
                        fixed._query_snapshot(
                            api, handle.value, include_streams=False
                        )
                        for _label, handle, _before in forbidden_handles
                    ]
                    protected_parent_after = [
                        fixed._query_snapshot(
                            api, handle.value, include_streams=False
                        )
                        for _root_id, handle, _before in protected_parent_handles
                    ]
                    inventory_after = fixed._enumerate_directory(
                        api, ancestor_handles[-1].value
                    )
                    fixed._validate_inventory(
                        inventory_after, frozenset({PUBLIC_KEY_PIN_FILENAME})
                    )
                    if not fixed._snapshot_stable(pin_before, pin_after):
                        raise P0WindowsExternalPublicKeyPinCandidateError(
                            "pin file changed across asymmetric validation"
                        )
                    if any(
                        fixed._ancestor_namespace_projection(before)
                        != fixed._ancestor_namespace_projection(after)
                        for before, after in zip(ancestor_before, ancestor_after)
                    ):
                        raise P0WindowsExternalPublicKeyPinCandidateError(
                            "pin ancestor namespace changed across validation"
                        )
                    if any(
                        fixed._ancestor_namespace_projection(before)
                        != fixed._ancestor_namespace_projection(after)
                        for (_label, _handle, before), after in zip(
                            forbidden_handles, forbidden_after
                        )
                    ):
                        raise P0WindowsExternalPublicKeyPinCandidateError(
                            "run/packet/protected root identity changed across validation"
                        )
                    if any(
                        fixed._ancestor_namespace_projection(before)
                        != fixed._ancestor_namespace_projection(after)
                        for (_root_id, _handle, before), after in zip(
                            protected_parent_handles, protected_parent_after
                        )
                    ):
                        raise P0WindowsExternalPublicKeyPinCandidateError(
                            "protected parent identity changed across validation"
                        )
                    if fixed._inventory_projection(
                        store_inventory_before
                    ) != fixed._inventory_projection(inventory_after):
                        raise P0WindowsExternalPublicKeyPinCandidateError(
                            "pin store inventory changed across validation"
                        )
                    if not _same_security(
                        file_security_before, file_security_after
                    ) or not _same_security(
                        parent_security_before, parent_security_after
                    ):
                        raise P0WindowsExternalPublicKeyPinCandidateError(
                            "pin ACL/owner changed across validation"
                        )
                    with fixed._open_handle(
                        api,
                        resolved_pin_path,
                        directory=False,
                        read_data=True,
                    ) as reopened:
                        reopened_snapshot = fixed._query_snapshot(
                            api, reopened.value, include_streams=True
                        )
                        if not fixed._snapshot_stable(
                            pin_after, reopened_snapshot
                        ):
                            raise P0WindowsExternalPublicKeyPinCandidateError(
                                "pin path reopen identity mismatch"
                            )
                    held.receipt = {
                        "schema_version": CANDIDATE_RECEIPT_SCHEMA,
                        "pin_filename": PUBLIC_KEY_PIN_FILENAME,
                        "pin_bytes_length": len(raw),
                        "pin_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                        "pin_artifact_sha256": pin["artifact_sha256"],
                        "public_key_fingerprint_sha256": pin[
                            "public_key_fingerprint_sha256"
                        ],
                        "key_id": pin["key_id"],
                        "key_epoch": pin["key_epoch"],
                        "owner_principal_sha256": pin[
                            "owner_principal_sha256"
                        ],
                        "owner_anchor_sha256": pin["owner_anchor_sha256"],
                        "pin_file_identity": fixed._snapshot_stable_projection(
                            pin_after
                        ),
                        "pin_store_identity": fixed._ancestor_namespace_projection(
                            ancestor_after[-1]
                        ),
                        "pin_file_security": file_security_after.projection(),
                        "pin_store_security": parent_security_after.projection(),
                        "pin_owner_sid_equal_store_owner_sid": True,
                        "all_lexical_ancestor_handles_held": True,
                        "file_handle_non_delete_shared_across_validation": True,
                        "pin_store_handle_non_delete_shared_across_validation": True,
                        "single_link_non_reparse_unnamed_stream_verified": True,
                        "persistent_acls_filesystem_observed": True,
                        "dedicated_fixed_filename_inventory_verified": True,
                        "presented_preauthorization_bytes_sha256": (
                            signed_roots.preauthorization_bytes_sha256
                        ),
                        "presented_root_expectation_sha256": canonical_sha256(
                            signed_roots.projection()
                        ),
                        "presented_root_binding_projection_sha256": canonical_sha256(
                            signed_root_binding
                        ),
                        (
                            "presented_packet_and_protected_parent_"
                            "identities_bound_to_held_handles"
                        ): True,
                        "presented_protected_category_path_volumes_bound_to_held_handles": True,
                        "held_run_packet_protected_parent_category_handles_identity_stable": True,
                        (
                            "pin_store_overlap_with_held_run_packet_protected_"
                            "parent_category_roots_rejected"
                        ): True,
                        "effective_verifier_token_source": token_source,
                        "effective_verifier_file_mutation_access_denied_observed": True,
                        "effective_verifier_parent_mutation_access_denied_observed": True,
                        "effective_verifier_owner_membership_rejected": True,
                        "security_descriptor_pre_post_stable": True,
                        "file_identity_pre_post_reopen_stable": True,
                        "caller_supplied_expected_owner_sid_absent": True,
                        "caller_supplied_expected_pin_hash_absent": True,
                        "caller_supplied_expected_pin_identity_absent": True,
                        "independent_owner_policy_state_verified": False,
                        "external_public_key_pin_provisioning_verified": False,
                        "independent_readonly_public_key_pin_verified": False,
                        "public_key_pin_rollback_protection_verified": False,
                    }
                    candidate_material = dict(held.receipt)
                    held.receipt = {
                        **candidate_material,
                        "receipt_sha256": canonical_sha256(candidate_material),
                    }
                except BaseException:
                    if primary_error is None:
                        raise
    except BaseException as exc:
        primary_error = primary_error or exc
        raise
    finally:
        outcomes: list[tuple[str, Any]] = []
        cleanup_errors: list[BaseException] = []
        if store_watch is not None:
            try:
                outcomes.append(("pin_store", store_watch.finalize()))
            except BaseException as exc:
                cleanup_errors.append(exc)
        try:
            outcomes.append(("pin_store_parent", parent_watch.finalize()))
        except BaseException as exc:
            cleanup_errors.append(exc)
        if primary_error is None:
            if cleanup_errors:
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "pin directory-change watcher cleanup failed"
                ) from cleanup_errors[0]
            expected_watch_identities = {
                "pin_store": (
                    ancestor_after[-1].final_path,
                    ancestor_after[-1].volume_serial,
                    ancestor_after[-1].file_id,
                ),
                "pin_store_parent": (
                    ancestor_after[-2].final_path,
                    ancestor_after[-2].volume_serial,
                    ancestor_after[-2].file_id,
                ),
            }
            for label, outcome in outcomes:
                _assert_watch_clean(outcome, label)
                expected_identity = expected_watch_identities[label]
                observed_identity = (
                    outcome.identity.final_path,
                    outcome.identity.volume_serial,
                    outcome.identity.file_id,
                )
                if observed_identity != expected_identity:
                    raise P0WindowsExternalPublicKeyPinCandidateError(
                        f"{label} watch/held-handle identity mismatch"
                    )
            if held.receipt is None:
                raise P0WindowsExternalPublicKeyPinCandidateError(
                    "pin candidate receipt was not finalized"
                )
            material = dict(held.receipt)
            material.pop("receipt_sha256")
            material["directory_change_watches"] = {
                label: _watch_projection(outcome) for label, outcome in outcomes
            }
            material["receipt_sha256"] = canonical_sha256(material)
            held.receipt = material


def _validate_candidate_receipt(
    value: Mapping[str, Any],
    *,
    expected_pin_bytes: bytes,
    expected_pin: Mapping[str, Any],
    expected_preauthorization_sha256: str,
    expected_root_expectation_sha256: str,
) -> None:
    if not isinstance(value, Mapping):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin candidate receipt is unavailable"
        )
    material = dict(value)
    declared = material.pop("receipt_sha256", None)
    if (
        value.get("schema_version") != CANDIDATE_RECEIPT_SCHEMA
        or not isinstance(declared, str)
        or not hmac.compare_digest(declared, canonical_sha256(material))
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin candidate receipt self-binding mismatch"
        )
    pin_bindings = (
        ("pin_bytes_length", len(expected_pin_bytes)),
        ("pin_bytes_sha256", hashlib.sha256(expected_pin_bytes).hexdigest()),
        ("pin_artifact_sha256", expected_pin.get("artifact_sha256")),
        (
            "public_key_fingerprint_sha256",
            expected_pin.get("public_key_fingerprint_sha256"),
        ),
        ("key_id", expected_pin.get("key_id")),
        ("key_epoch", expected_pin.get("key_epoch")),
        ("owner_principal_sha256", expected_pin.get("owner_principal_sha256")),
        ("owner_anchor_sha256", expected_pin.get("owner_anchor_sha256")),
        (
            "presented_preauthorization_bytes_sha256",
            expected_preauthorization_sha256,
        ),
        ("presented_root_expectation_sha256", expected_root_expectation_sha256),
    )
    if any(value.get(field) != expected for field, expected in pin_bindings):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin candidate raw/root receipt cross-binding mismatch"
        )
    binding_sha = value.get("presented_root_binding_projection_sha256")
    if (
        not isinstance(binding_sha, str)
        or len(binding_sha) != 64
        or any(character not in "0123456789abcdef" for character in binding_sha)
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin candidate root binding digest is invalid"
        )
    if value.get("effective_verifier_token_source") not in {
        "THREAD_IMPERSONATION_TOKEN",
        "PROCESS_PRIMARY_TOKEN_NO_THREAD_TOKEN",
    }:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin candidate effective token source is invalid"
        )
    for field in (
        "all_lexical_ancestor_handles_held",
        "file_handle_non_delete_shared_across_validation",
        "pin_store_handle_non_delete_shared_across_validation",
        "single_link_non_reparse_unnamed_stream_verified",
        "persistent_acls_filesystem_observed",
        "dedicated_fixed_filename_inventory_verified",
        "presented_packet_and_protected_parent_identities_bound_to_held_handles",
        "presented_protected_category_path_volumes_bound_to_held_handles",
        "held_run_packet_protected_parent_category_handles_identity_stable",
        "pin_store_overlap_with_held_run_packet_protected_parent_category_roots_rejected",
        "effective_verifier_file_mutation_access_denied_observed",
        "effective_verifier_parent_mutation_access_denied_observed",
        "effective_verifier_owner_membership_rejected",
        "security_descriptor_pre_post_stable",
        "file_identity_pre_post_reopen_stable",
    ):
        if value.get(field) is not True:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "pin candidate signed-root binding is incomplete"
            )
    watches = value.get("directory_change_watches")
    if not isinstance(watches, Mapping) or set(watches) != {
        "pin_store",
        "pin_store_parent",
    }:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin candidate directory-change watch receipt is invalid"
        )
    for label, watch in watches.items():
        if not isinstance(watch, Mapping) or (
            watch.get("bounded_watch_observation_verified") is not True
            or watch.get("directory_change_notification_delivered_observed")
            is not False
            or watch.get("overflow_observed") is not False
            or watch.get("observation_gap_observed") is not False
            or watch.get("pending_request_until_interval_end_observed") is not True
            or watch.get("completion_drained_observed") is not True
            or watch.get("watch_handles_closed_observed") is not True
        ):
            raise P0WindowsExternalPublicKeyPinCandidateError(
                f"pin candidate directory-change watch is not clean: {label}"
            )
    for field in (
        "independent_owner_policy_state_verified",
        "external_public_key_pin_provisioning_verified",
        "independent_readonly_public_key_pin_verified",
        "public_key_pin_rollback_protection_verified",
    ):
        if value.get(field) is not False:
            raise P0WindowsExternalPublicKeyPinCandidateError(
                "pin candidate receipt authority overclaim"
            )


def execute_windows_external_public_key_pin_candidate_supervisor(
    *,
    pin_store_dir: Path | str,
    run_root: Path | str,
    packet_root: Path | str,
    protected_category_roots: Mapping[str, Path | str],
    signature_envelope_bytes: bytes,
    owner_root_preauthorization_bytes: bytes,
    expected_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Use one ACL-bound handle-read pin candidate for fresh CNG validation."""

    signed_roots = _signed_root_expectation(owner_root_preauthorization_bytes)
    candidate: _HeldPinCandidate | None = None
    try:
        with _hold_windows_pin_candidate(
            pin_store_dir=pin_store_dir,
            run_root=run_root,
            packet_root=packet_root,
            protected_category_roots=protected_category_roots,
            signed_roots=signed_roots,
        ) as candidate:
            owner_receipt = owner_state.execute_presented_external_owner_state_supervisor(
                public_key_pin_bytes=candidate.raw,
                signature_envelope_bytes=signature_envelope_bytes,
                owner_root_preauthorization_bytes=owner_root_preauthorization_bytes,
                expected_context=expected_context,
            )
    except (
        owner_state.P0ExternalOwnerStateSupervisorError,
        directory_watch.P0WindowsDirectoryChangeWatchError,
        fixed.P0WindowsFixedDirectoryError,
    ) as exc:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "ACL-bound pin candidate supervisor failed"
        ) from exc
    if candidate is None or candidate.receipt is None:
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "ACL-bound pin candidate lifecycle did not finalize"
        )
    pin = candidate.pin
    pin_sha = hashlib.sha256(candidate.raw).hexdigest()
    _validate_candidate_receipt(
        candidate.receipt,
        expected_pin_bytes=candidate.raw,
        expected_pin=pin,
        expected_preauthorization_sha256=(
            signed_roots.preauthorization_bytes_sha256
        ),
        expected_root_expectation_sha256=canonical_sha256(
            signed_roots.projection()
        ),
    )
    if (
        candidate.receipt.get("presented_preauthorization_bytes_sha256")
        != owner_receipt.get("preauthorization_bytes_sha256")
        or candidate.receipt.get("presented_preauthorization_bytes_sha256")
        != signed_roots.preauthorization_bytes_sha256
        or owner_receipt.get("public_key_pin_bytes_sha256") != pin_sha
        or owner_receipt.get("public_key_fingerprint_sha256")
        != pin.get("public_key_fingerprint_sha256")
        or owner_receipt.get("key_id") != pin.get("key_id")
        or owner_receipt.get("key_epoch") != pin.get("key_epoch")
        or owner_receipt.get("owner_principal_sha256")
        != pin.get("owner_principal_sha256")
        or owner_receipt.get("owner_anchor_sha256")
        != pin.get("owner_anchor_sha256")
    ):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "pin candidate to OWNER_STATE cross-binding mismatch"
        )
    false_fields = (
        "external_public_key_pin_provisioning_verified",
        "independent_readonly_public_key_pin_verified",
        "public_key_pin_rollback_protection_verified",
        "key_epoch_monotonicity_verified",
        "independent_context_policy_verified",
        "signature_freshness_verified",
        "external_owner_signing_key_verified",
        "private_key_outside_verifier_verified",
        "trusted_time_verified",
        "revocation_current_verified",
        "revocation_rollback_protection_verified",
        "durable_cross_process_nonce_verified",
        "power_loss_durable_replay_verified",
        "external_owner_trust_verified",
        "owner_authority_verified",
        "actual_authority_granted",
        "p0_phase_exit",
        "production_approval",
        "full_scan_approval",
    )
    if any(owner_receipt.get(field) is not False for field in false_fields):
        raise P0WindowsExternalPublicKeyPinCandidateError(
            "nested OWNER_STATE receipt authority overclaim"
        )
    material = {
        "schema_version": SUPERVISOR_RECEIPT_SCHEMA,
        "pin_candidate_receipt_sha256": candidate.receipt["receipt_sha256"],
        "owner_state_receipt_sha256": owner_receipt["receipt_sha256"],
        "pin_bytes_sha256": pin_sha,
        "pin_artifact_sha256": pin["artifact_sha256"],
        "public_key_fingerprint_sha256": pin[
            "public_key_fingerprint_sha256"
        ],
        "key_id": pin["key_id"],
        "key_epoch": pin["key_epoch"],
        "owner_principal_sha256": pin["owner_principal_sha256"],
        "owner_anchor_sha256": pin["owner_anchor_sha256"],
        "preauthorization_bytes_sha256": (
            signed_roots.preauthorization_bytes_sha256
        ),
        "signed_root_expectation_sha256": canonical_sha256(
            signed_roots.projection()
        ),
        "held_root_binding_projection_sha256": candidate.receipt[
            "presented_root_binding_projection_sha256"
        ],
        "same_call_handle_read_pin_bytes_used_for_cng": True,
        "pin_file_and_ancestor_handles_held_across_owner_state_validation": True,
        "directory_change_watch_interval_wrapped_owner_state_validation": True,
        "module_issued_owner_state_consumed_once": True,
        "caller_supplied_public_key_pin_bytes_absent": True,
        "caller_supplied_pin_receipt_absent": True,
        "caller_supplied_expected_owner_sid_absent": True,
        "caller_supplied_expected_pin_hash_absent": True,
        "caller_supplied_expected_pin_identity_absent": True,
        "bounded_local_windows_acl_pin_candidate_observed": True,
        "signed_packet_and_protected_parent_identities_bound_to_held_handles": True,
        "signed_protected_category_path_volumes_bound_to_held_handles": True,
        "asymmetric_signature_bound_preauthorization_root_projection_observed": True,
        "held_run_packet_protected_parent_category_handles_identity_stable": True,
        "serialized_receipt_authoritative": False,
        "execution_trace_transferable_by_receipt": False,
        "signature_artifact_replay_prevented": False,
        "independent_owner_policy_state_verified": False,
        "external_public_key_pin_provisioning_verified": False,
        "independent_readonly_public_key_pin_verified": False,
        "public_key_pin_rollback_protection_verified": False,
        "key_epoch_monotonicity_verified": False,
        "independent_context_policy_verified": False,
        "signature_freshness_verified": False,
        "external_owner_signing_key_verified": False,
        "private_key_outside_verifier_verified": False,
        "trusted_time_verified": False,
        "revocation_current_verified": False,
        "revocation_rollback_protection_verified": False,
        "durable_cross_process_nonce_verified": False,
        "power_loss_durable_replay_verified": False,
        "external_owner_trust_verified": False,
        "owner_authority_verified": False,
        "actual_authority_granted": False,
        "actual_semantic_evidence_verified": False,
        "p0_phase_exit": False,
        "production_approval": False,
        "full_scan_approval": False,
        "action_applied": False,
        "protected_pipeline_state_mutated": False,
        "credited_actual_source_claim_count": 0,
        "credited_actual_a_context_review_count": 0,
        "gate_status": GATE_STATUS,
    }
    return {**material, "receipt_sha256": canonical_sha256(material)}


__all__ = [
    "CANDIDATE_RECEIPT_SCHEMA",
    "GATE_STATUS",
    "P0WindowsExternalPublicKeyPinCandidateError",
    "PUBLIC_KEY_PIN_FILENAME",
    "SUPERVISOR_RECEIPT_SCHEMA",
    "canonical_bytes",
    "canonical_sha256",
    "execute_windows_external_public_key_pin_candidate_supervisor",
]
