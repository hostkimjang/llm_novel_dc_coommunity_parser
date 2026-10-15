"""Provider-fixed Windows CNG ECDSA P-256/SHA-256 verification primitive."""

from __future__ import annotations

import ctypes
import os
import struct
from typing import Any, Callable


CNG_PROVIDER = "Microsoft Primitive Provider"
CURVE = "NIST_P256"
_STATUS_SUCCESS = 0
_BCRYPT_ECDSA_PUBLIC_P256_MAGIC = 0x31534345


class P0WindowsCngEcdsaP256Error(RuntimeError):
    """The provider-fixed CNG verification primitive failed closed."""


def _cleanup_cng_handles(
    *,
    destroy_key: Callable[[Any], int],
    close_provider: Callable[[Any, int], int],
    key: Any,
    provider: Any,
    primary_error: BaseException | None,
) -> None:
    errors: list[BaseException] = []
    if key.value:
        try:
            status = destroy_key(key)
            if status != _STATUS_SUCCESS:
                errors.append(
                    P0WindowsCngEcdsaP256Error(
                        "BCryptDestroyKey failed: "
                        f"0x{status & 0xffffffff:08x}"
                    )
                )
        except BaseException as exc:
            errors.append(exc)
    if provider.value:
        try:
            status = close_provider(provider, 0)
            if status != _STATUS_SUCCESS:
                errors.append(
                    P0WindowsCngEcdsaP256Error(
                        "BCryptCloseAlgorithmProvider failed: "
                        f"0x{status & 0xffffffff:08x}"
                    )
                )
        except BaseException as exc:
            errors.append(exc)
    if errors and primary_error is None:
        raise P0WindowsCngEcdsaP256Error(
            "CNG handle cleanup failed"
        ) from errors[0]
    if errors and primary_error is not None:
        for cleanup_error in errors:
            try:
                primary_error.add_note(
                    "suppressed CNG cleanup error: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
            except BaseException:
                break


def verify_p256_sha256(
    *, public_key_x: bytes, public_key_y: bytes, digest: bytes, signature: bytes
) -> None:
    """Verify one exact 32-byte digest and 64-byte P1363 signature."""

    if os.name != "nt":
        raise P0WindowsCngEcdsaP256Error(
            "Windows CNG ECDSA verification is required"
        )
    if (
        type(public_key_x) is not bytes
        or type(public_key_y) is not bytes
        or type(digest) is not bytes
        or type(signature) is not bytes
        or len(public_key_x) != 32
        or len(public_key_y) != 32
        or len(digest) != 32
        or len(signature) != 64
    ):
        raise P0WindowsCngEcdsaP256Error(
            "CNG P-256 inputs have an invalid type/fixed width"
        )

    try:
        bcrypt = ctypes.WinDLL("bcrypt", use_last_error=True)
        handle = ctypes.c_void_p
        byte_pointer = ctypes.POINTER(ctypes.c_ubyte)
        ulong = ctypes.c_ulong
        ntstatus = ctypes.c_long

        open_provider = bcrypt.BCryptOpenAlgorithmProvider
        open_provider.argtypes = [
            ctypes.POINTER(handle),
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ulong,
        ]
        open_provider.restype = ntstatus
        import_pair = bcrypt.BCryptImportKeyPair
        import_pair.argtypes = [
            handle,
            handle,
            ctypes.c_wchar_p,
            ctypes.POINTER(handle),
            byte_pointer,
            ulong,
            ulong,
        ]
        import_pair.restype = ntstatus
        verify = bcrypt.BCryptVerifySignature
        verify.argtypes = [
            handle,
            ctypes.c_void_p,
            byte_pointer,
            ulong,
            byte_pointer,
            ulong,
            ulong,
        ]
        verify.restype = ntstatus
        destroy_key = bcrypt.BCryptDestroyKey
        destroy_key.argtypes = [handle]
        destroy_key.restype = ntstatus
        close_provider = bcrypt.BCryptCloseAlgorithmProvider
        close_provider.argtypes = [handle, ulong]
        close_provider.restype = ntstatus
    except Exception as exc:
        raise P0WindowsCngEcdsaP256Error(
            "Windows CNG API initialization failed"
        ) from exc

    provider = handle()
    key = handle()
    primary_error: BaseException | None = None
    try:
        status = open_provider(
            ctypes.byref(provider), "ECDSA_P256", CNG_PROVIDER, 0
        )
        if status != _STATUS_SUCCESS:
            raise P0WindowsCngEcdsaP256Error(
                "BCryptOpenAlgorithmProvider failed: "
                f"0x{status & 0xffffffff:08x}"
            )
        blob = (
            struct.pack("<II", _BCRYPT_ECDSA_PUBLIC_P256_MAGIC, 32)
            + public_key_x
            + public_key_y
        )
        blob_buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        status = import_pair(
            provider,
            None,
            "ECCPUBLICBLOB",
            ctypes.byref(key),
            blob_buffer,
            len(blob),
            0,
        )
        if status != _STATUS_SUCCESS:
            raise P0WindowsCngEcdsaP256Error(
                "BCryptImportKeyPair rejected public key: "
                f"0x{status & 0xffffffff:08x}"
            )
        digest_buffer = (ctypes.c_ubyte * len(digest)).from_buffer_copy(digest)
        signature_buffer = (ctypes.c_ubyte * len(signature)).from_buffer_copy(
            signature
        )
        status = verify(
            key,
            None,
            digest_buffer,
            len(digest),
            signature_buffer,
            len(signature),
            0,
        )
        if status != _STATUS_SUCCESS:
            raise P0WindowsCngEcdsaP256Error(
                "ECDSA P-256 signature mismatch"
            )
    except P0WindowsCngEcdsaP256Error as exc:
        primary_error = exc
        raise
    except Exception as exc:
        normalized = P0WindowsCngEcdsaP256Error(
            "Windows CNG verification call failed closed"
        )
        primary_error = normalized
        raise normalized from exc
    finally:
        _cleanup_cng_handles(
            destroy_key=destroy_key,
            close_provider=close_provider,
            key=key,
            provider=provider,
            primary_error=primary_error,
        )


__all__ = [
    "CNG_PROVIDER",
    "CURVE",
    "P0WindowsCngEcdsaP256Error",
    "verify_p256_sha256",
]
