"""Binary Windows DACL projection for the external-owner policy candidate.

The reader accepts an already-open file or directory handle and projects the
owner, group, security-descriptor control bits, and ordered standard allow
ACEs.  It deliberately rejects every non-standard ACE type instead of relying
on SDDL rendering.  A caller-provided handle is not independent provisioning;
the result is intended for a future fixed-store supervisor that owns and holds
the handle for its complete validation interval.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from typing import Any


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

_SE_DACL_PRESENT = 0x0004
_SE_DACL_DEFAULTED = 0x0008
_SE_DACL_AUTO_INHERIT_REQ = 0x0100
_SE_DACL_AUTO_INHERITED = 0x0400
_SE_DACL_PROTECTED = 0x1000
_ACCESS_ALLOWED_ACE_TYPE = 0
_ACL_SIZE_INFORMATION_CLASS = 2
_MAX_ACL_BYTES = 65536
_MAX_ACE_COUNT = 4096
_FILE_TYPE_DISK = 0x0001
_UINTPTR_MAX = int(ctypes.c_void_p(-1).value)
_PSEUDO_HANDLE_FLOOR = _UINTPTR_MAX - 15


class P0WindowsBinaryAclProjectionError(ValueError):
    """A held-handle Windows ACL could not be projected fail-closed."""


class _ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("AceCount", wintypes.DWORD),
        ("AclBytesInUse", wintypes.DWORD),
        ("AclBytesFree", wintypes.DWORD),
    ]


class _ACE_HEADER(ctypes.Structure):
    _fields_ = [
        ("AceType", wintypes.BYTE),
        ("AceFlags", wintypes.BYTE),
        ("AceSize", wintypes.WORD),
    ]


class _WinBinaryAclApi:
    def __init__(self) -> None:
        if not _IS_WINDOWS:
            raise P0WindowsBinaryAclProjectionError(
                "Windows binary ACL projection is unavailable"
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

        self.IsValidSecurityDescriptor = advapi32.IsValidSecurityDescriptor
        self.IsValidSecurityDescriptor.argtypes = [ctypes.c_void_p]
        self.IsValidSecurityDescriptor.restype = wintypes.BOOL

        self.GetSecurityDescriptorControl = advapi32.GetSecurityDescriptorControl
        self.GetSecurityDescriptorControl.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.WORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.GetSecurityDescriptorControl.restype = wintypes.BOOL

        self.GetSecurityDescriptorDacl = advapi32.GetSecurityDescriptorDacl
        self.GetSecurityDescriptorDacl.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.BOOL),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.BOOL),
        ]
        self.GetSecurityDescriptorDacl.restype = wintypes.BOOL

        self.IsValidAcl = advapi32.IsValidAcl
        self.IsValidAcl.argtypes = [ctypes.c_void_p]
        self.IsValidAcl.restype = wintypes.BOOL

        self.GetAclInformation = advapi32.GetAclInformation
        self.GetAclInformation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_int,
        ]
        self.GetAclInformation.restype = wintypes.BOOL

        self.GetAce = advapi32.GetAce
        self.GetAce.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self.GetAce.restype = wintypes.BOOL

        self.IsValidSid = advapi32.IsValidSid
        self.IsValidSid.argtypes = [ctypes.c_void_p]
        self.IsValidSid.restype = wintypes.BOOL

        self.GetLengthSid = advapi32.GetLengthSid
        self.GetLengthSid.argtypes = [ctypes.c_void_p]
        self.GetLengthSid.restype = wintypes.DWORD

        self.ConvertSidToStringSidW = advapi32.ConvertSidToStringSidW
        self.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        self.ConvertSidToStringSidW.restype = wintypes.BOOL

        self.LocalFree = kernel32.LocalFree
        self.LocalFree.argtypes = [ctypes.c_void_p]
        self.LocalFree.restype = ctypes.c_void_p

        self.GetFileType = kernel32.GetFileType
        self.GetFileType.argtypes = [wintypes.HANDLE]
        self.GetFileType.restype = wintypes.DWORD


def _error(label: str, code: int | None = None) -> P0WindowsBinaryAclProjectionError:
    value = ctypes.get_last_error() if code is None else code
    return P0WindowsBinaryAclProjectionError(
        f"{label} failed with Windows error {value}"
    )


def _local_free(api: _WinBinaryAclApi, pointer: ctypes.c_void_p, label: str) -> None:
    if pointer.value and api.LocalFree(pointer):
        raise P0WindowsBinaryAclProjectionError(f"LocalFree({label}) failed")


def _sid_string(
    api: _WinBinaryAclApi, sid_address: int | None, label: str
) -> str:
    if not sid_address:
        raise P0WindowsBinaryAclProjectionError(f"{label} SID is absent")
    sid = ctypes.c_void_p(sid_address)
    if not api.IsValidSid(sid):
        raise P0WindowsBinaryAclProjectionError(f"{label} SID is invalid")
    rendered = wintypes.LPWSTR()
    primary_error: BaseException | None = None
    try:
        if not api.ConvertSidToStringSidW(sid, ctypes.byref(rendered)):
            raise _error(f"ConvertSidToStringSidW({label})")
        value = rendered.value
        if not value or not value.startswith("S-"):
            raise P0WindowsBinaryAclProjectionError(
                f"{label} SID rendering is invalid"
            )
        return value
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if rendered:
            try:
                _local_free(
                    api, ctypes.cast(rendered, ctypes.c_void_p), f"{label} SID"
                )
            except BaseException:
                if primary_error is None:
                    raise


def _ordered_standard_allow_aces(
    api: _WinBinaryAclApi, dacl: ctypes.c_void_p
) -> list[dict[str, Any]]:
    if not dacl.value:
        return []
    if not api.IsValidAcl(dacl):
        raise P0WindowsBinaryAclProjectionError("DACL is not a valid ACL")
    info = _ACL_SIZE_INFORMATION()
    if not api.GetAclInformation(
        dacl,
        ctypes.byref(info),
        ctypes.sizeof(info),
        _ACL_SIZE_INFORMATION_CLASS,
    ):
        raise _error("GetAclInformation")
    ace_count = int(info.AceCount)
    bytes_in_use = int(info.AclBytesInUse)
    if (
        ace_count > _MAX_ACE_COUNT
        or bytes_in_use < 8
        or bytes_in_use > _MAX_ACL_BYTES
    ):
        raise P0WindowsBinaryAclProjectionError(
            "DACL size or ACE count exceeds the strict bound"
        )
    result: list[dict[str, Any]] = []
    expected_ace_address = int(dacl.value) + 8
    acl_end_address = int(dacl.value) + bytes_in_use
    for index in range(ace_count):
        ace = ctypes.c_void_p()
        if not api.GetAce(dacl, index, ctypes.byref(ace)):
            raise _error(f"GetAce({index})")
        if not ace.value:
            raise P0WindowsBinaryAclProjectionError(
                f"GetAce({index}) returned a NULL ACE"
            )
        header = ctypes.cast(ace, ctypes.POINTER(_ACE_HEADER)).contents
        ace_type = int(header.AceType)
        ace_flags = int(header.AceFlags)
        ace_size = int(header.AceSize)
        if ace_type != _ACCESS_ALLOWED_ACE_TYPE:
            raise P0WindowsBinaryAclProjectionError(
                f"unsupported ACE type at index {index}: {ace_type}"
            )
        if ace_size < 20 or ace_size > bytes_in_use:
            raise P0WindowsBinaryAclProjectionError(
                f"ACE size is invalid at index {index}"
            )
        if (
            int(ace.value) != expected_ace_address
            or int(ace.value) + ace_size > acl_end_address
        ):
            raise P0WindowsBinaryAclProjectionError(
                f"ACE pointer is outside the contiguous ACL at index {index}"
            )
        mask = ctypes.c_uint32.from_address(ace.value + 4).value
        sid_address = ace.value + 8
        if not api.IsValidSid(ctypes.c_void_p(sid_address)):
            raise P0WindowsBinaryAclProjectionError(
                f"ACE SID is invalid at index {index}"
            )
        sid_length = int(api.GetLengthSid(ctypes.c_void_p(sid_address)))
        if sid_length < 12 or 8 + sid_length != ace_size:
            raise P0WindowsBinaryAclProjectionError(
                f"ACE SID length does not exactly fill ACE {index}"
            )
        result.append(
            {
                "ace_type": ace_type,
                "ace_flags": ace_flags,
                "access_mask_decimal": str(mask),
                "sid": _sid_string(api, sid_address, f"ACE {index}"),
            }
        )
        expected_ace_address += ace_size
    if expected_ace_address != acl_end_address:
        raise P0WindowsBinaryAclProjectionError(
            "ACE sequence does not exactly fill AclBytesInUse"
        )
    return result


def _observe_windows_binary_acl_projection(*, handle: int) -> dict[str, Any]:
    """Project one held handle's binary DACL without granting authority."""

    if (
        type(handle) is not int
        or handle <= 0
        or handle > _UINTPTR_MAX
        or handle >= _PSEUDO_HANDLE_FLOOR
    ):
        raise P0WindowsBinaryAclProjectionError(
            "handle must be one canonical non-pseudo pointer-width Windows handle"
        )
    api = _WinBinaryAclApi()
    if int(api.GetFileType(handle)) != _FILE_TYPE_DISK:
        raise P0WindowsBinaryAclProjectionError(
            "handle must refer to a disk file or directory"
        )
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
        if not descriptor.value or not api.IsValidSecurityDescriptor(descriptor):
            raise P0WindowsBinaryAclProjectionError(
                "GetSecurityInfo returned an invalid security descriptor"
            )
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not api.GetSecurityDescriptorControl(
            descriptor, ctypes.byref(control), ctypes.byref(revision)
        ):
            raise _error("GetSecurityDescriptorControl")
        if int(revision.value) != 1:
            raise P0WindowsBinaryAclProjectionError(
                "security descriptor revision is unsupported"
            )
        dacl_present = wintypes.BOOL()
        descriptor_dacl = ctypes.c_void_p()
        dacl_defaulted = wintypes.BOOL()
        if not api.GetSecurityDescriptorDacl(
            descriptor,
            ctypes.byref(dacl_present),
            ctypes.byref(descriptor_dacl),
            ctypes.byref(dacl_defaulted),
        ):
            raise _error("GetSecurityDescriptorDacl")
        if bool(dacl_present.value) != bool(control.value & _SE_DACL_PRESENT):
            raise P0WindowsBinaryAclProjectionError(
                "DACL-present control projections disagree"
            )
        if not bool(dacl_present.value) and descriptor_dacl.value:
            raise P0WindowsBinaryAclProjectionError(
                "absent DACL cannot have a non-NULL pointer"
            )
        if (descriptor_dacl.value or None) != (dacl.value or None):
            raise P0WindowsBinaryAclProjectionError(
                "GetSecurityInfo and descriptor DACL pointers disagree"
            )
        control_defaulted = bool(control.value & _SE_DACL_DEFAULTED)
        if bool(dacl_defaulted.value) != control_defaulted:
            raise P0WindowsBinaryAclProjectionError(
                "DACL-defaulted control projections disagree"
            )
        return {
            "owner_sid": _sid_string(api, owner.value, "owner"),
            "group_sid": _sid_string(api, group.value, "group"),
            "dacl_present": bool(dacl_present.value),
            "dacl_null": not bool(descriptor_dacl.value),
            "dacl_protected": bool(control.value & _SE_DACL_PROTECTED),
            "dacl_defaulted": control_defaulted,
            "dacl_auto_inherited": bool(
                control.value & _SE_DACL_AUTO_INHERITED
            ),
            "dacl_auto_inherit_req": bool(
                control.value & _SE_DACL_AUTO_INHERIT_REQ
            ),
            "ordered_aces": _ordered_standard_allow_aces(api, descriptor_dacl),
        }
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if descriptor.value:
            try:
                _local_free(api, descriptor, "security descriptor")
            except BaseException:
                if primary_error is None:
                    raise


def observe_windows_binary_acl_projection(*, handle: int) -> dict[str, Any]:
    """Normalize platform/ctypes failures to the bounded contract error."""

    try:
        return _observe_windows_binary_acl_projection(handle=handle)
    except P0WindowsBinaryAclProjectionError:
        raise
    except (OSError, OverflowError, ctypes.ArgumentError, ValueError) as exc:
        raise P0WindowsBinaryAclProjectionError(
            "Windows binary ACL projection failed at the platform boundary"
        ) from exc


__all__ = [
    "P0WindowsBinaryAclProjectionError",
    "observe_windows_binary_acl_projection",
]
