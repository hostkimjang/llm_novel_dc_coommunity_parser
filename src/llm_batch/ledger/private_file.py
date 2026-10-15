"""플랫폼의 실제 파일 권한으로 복구 키를 보호한다. 키 내용은 읽지 않는다."""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat


def _regular_private_target(path: Path) -> None:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, "st_file_attributes", 0) & 0x400):
        raise OSError("private key must be a regular unlinked file, without reparse points")


def _windows_file_acl(path: Path, *, restrict: bool, create: bool = False) -> bool | int:
    # ctypes의 HANDLE은 64비트에서도 잘리지 않도록 모든 원형을 지정한다.
    import ctypes as c
    from ctypes import wintypes as w

    kernel = c.WinDLL("kernel32", use_last_error=True)
    adv = c.WinDLL("advapi32", use_last_error=True)
    pointer = c.c_void_p
    pp = c.POINTER(pointer)

    def bind(dll, name, args, result):
        fn = getattr(dll, name)
        fn.argtypes, fn.restype = args, result
        return fn

    current = bind(kernel, "GetCurrentProcess", [], w.HANDLE)
    close = bind(kernel, "CloseHandle", [w.HANDLE], w.BOOL)
    free = bind(kernel, "LocalFree", [pointer], pointer)
    open_token = bind(adv, "OpenProcessToken", [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL)
    token_info = bind(adv, "GetTokenInformation", [w.HANDLE, c.c_int, pointer, w.DWORD, c.POINTER(w.DWORD)], w.BOOL)
    sid_string = bind(adv, "ConvertSidToStringSidW", [pointer, pp], w.BOOL)
    from_sddl = bind(adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [w.LPCWSTR, w.DWORD, pp, c.POINTER(w.DWORD)], w.BOOL)
    get_dacl = bind(adv, "GetSecurityDescriptorDacl", [pointer, c.POINTER(w.BOOL), pp, c.POINTER(w.BOOL)], w.BOOL)
    set_info = bind(adv, "SetNamedSecurityInfoW", [w.LPWSTR, c.c_int, w.DWORD, pointer, pointer, pointer, pointer], w.DWORD)
    get_info = bind(adv, "GetNamedSecurityInfoW", [w.LPWSTR, c.c_int, w.DWORD, pp, pp, pp, pp, pp], w.DWORD)
    to_sddl = bind(adv, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [pointer, w.DWORD, w.DWORD, pp, c.POINTER(w.DWORD)], w.BOOL)

    def check(ok):
        if not ok:
            raise c.WinError(c.get_last_error())

    token = w.HANDLE()
    check(open_token(current(), 0x0008, c.byref(token)))  # TOKEN_QUERY
    try:
        required = w.DWORD()
        token_info(token, 1, None, 0, c.byref(required))  # TokenUser
        if not required.value:
            raise c.WinError(c.get_last_error())
        buffer = c.create_string_buffer(required.value)
        check(token_info(token, 1, buffer, required, c.byref(required)))
        sid = c.cast(buffer, pp).contents
        sid_text = pointer()
        check(sid_string(sid, c.byref(sid_text)))
        try:
            user_sid = c.wstring_at(sid_text)
        finally:
            free(sid_text)
    finally:
        close(token)

    def owner_matches() -> bool:
        owner, descriptor, owner_text = pointer(), pointer(), pointer()
        error = get_info(str(path), 1, 0x1, c.byref(owner), None, None, None, c.byref(descriptor))
        if error:
            raise c.WinError(error)
        try:
            check(sid_string(owner, c.byref(owner_text)))
            return c.wstring_at(owner_text) == user_sid
        finally:
            if owner_text.value:
                free(owner_text)
            free(descriptor)

    if not create and not owner_matches():
        raise OSError("private key owner differs from current user")

    # 기존 상속 권한을 제거하고 현재 사용자와 SYSTEM만 허용한다.
    ace_user = "SY" if user_sid == "S-1-5-18" else user_sid
    expected_aces = {"A;;FA;;;SY", f"A;;FA;;;{ace_user}"}
    expected = "D:P" + "".join(f"({ace})" for ace in sorted(expected_aces))
    if restrict or create:
        descriptor = pointer()
        check(from_sddl("O:" + user_sid + expected, 1, c.byref(descriptor), None))
        try:
            if create:
                import msvcrt

                class SecurityAttributes(c.Structure):
                    _fields_ = [("length", w.DWORD), ("descriptor", pointer), ("inherit", w.BOOL)]

                create_file = bind(kernel, "CreateFileW", [w.LPCWSTR, w.DWORD, w.DWORD, c.POINTER(SecurityAttributes), w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
                attributes = SecurityAttributes(c.sizeof(SecurityAttributes), descriptor, False)
                # CREATE_NEW: 생성 순간부터 보호 DACL을 적용하며 기존 파일은 열지 않는다.
                handle = create_file(str(path), 0x40000000, 0x1, c.byref(attributes), 1, 0x80, None)
                if handle == w.HANDLE(-1).value:
                    raise c.WinError(c.get_last_error())
                try:
                    return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
                except BaseException:
                    close(handle)
                    raise
            present, defaulted, dacl = w.BOOL(), w.BOOL(), pointer()
            check(get_dacl(descriptor, c.byref(present), c.byref(dacl), c.byref(defaulted)))
            if not present.value or not dacl.value:
                raise OSError("private key DACL is missing")
            error = set_info(str(path), 1, 0x80000004, None, None, dacl, None)
            if error:
                raise c.WinError(error)
        finally:
            free(descriptor)

    descriptor, text = pointer(), pointer()
    error = get_info(str(path), 1, 0x4, None, None, None, None, c.byref(descriptor))
    if error:
        raise c.WinError(error)
    try:
        check(to_sddl(descriptor, 1, 0x4, c.byref(text), None))
        value = c.wstring_at(text)
        prefix = value.split("(", 1)[0]
        aces = re.findall(r"\(([^()]*)\)", value)
        return prefix in {"D:P", "D:PAI"} and len(aces) == len(expected_aces) and set(aces) == expected_aces
    finally:
        if text.value:
            free(text)
        free(descriptor)


def private_file_permissions_ok(path: Path | str) -> bool:
    path = Path(path)
    _regular_private_target(path)
    if os.name == "nt":
        return _windows_file_acl(path, restrict=False)
    return stat.S_IMODE(path.stat().st_mode) == 0o600


def restrict_private_file(path: Path | str) -> None:
    path = Path(path)
    _regular_private_target(path)
    if os.name == "nt":
        verified = _windows_file_acl(path, restrict=True)
    else:
        os.chmod(path, 0o600)
        verified = private_file_permissions_ok(path)
    if not verified:
        raise OSError("private key file permissions could not be verified")


def create_private_file(path: Path | str) -> int:
    """비어 있는 새 파일을 처음부터 비공개 권한으로 만들고 소유할 fd를 반환한다."""
    path = Path(path)
    if os.name == "nt":
        return int(_windows_file_acl(path, restrict=False, create=True))
    return os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
