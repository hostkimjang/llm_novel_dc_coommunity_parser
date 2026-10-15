"""stdin/stdout worker for the P0 capture-hash process protocol.

The direct-script entry point installs a narrow import-origin guard before it
adds the repository ``src`` directory.  This makes a successful child run an
observation about the three expected project modules only; it does not claim a
stdlib, native-loader, or complete runtime dependency closure.
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import os
from pathlib import Path
import sys
from typing import Any


PROTOCOL_ERROR_EXIT = 2
INTERNAL_ERROR_EXIT = 3
RUNTIME_GUARD_ERROR_EXIT = 4
EXPECTED_PYCACHE_PREFIX_ARGUMENT = "--p0-expected-pycache-prefix="


def _normal_path(value: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(value)))


def _is_within(path: str, directory: str) -> bool:
    try:
        return os.path.commonpath((_normal_path(path), _normal_path(directory))) == (
            _normal_path(directory)
        )
    except (OSError, ValueError):
        return False


class _ProjectOriginGuard:
    """Delegate to PathFinder while rejecting any unexpected repo origin."""

    def __init__(self, worker_path: Path, pycache_prefix: Path) -> None:
        grounding = worker_path.parent
        llm_batch = grounding.parent
        self._src = _normal_path(llm_batch.parent)
        self._pycache_prefix = _normal_path(pycache_prefix)
        self._expected = {
            "llm_batch": _normal_path(llm_batch / "__init__.py"),
            "llm_batch.grounding": _normal_path(grounding / "__init__.py"),
            "llm_batch.grounding.p0_parser_process_protocol": _normal_path(
                grounding / "p0_parser_process_protocol.py"
            ),
        }
        self._expected_packages = {
            "llm_batch": _normal_path(llm_batch),
            "llm_batch.grounding": _normal_path(grounding),
        }
        self._observed: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _locations(spec: Any) -> tuple[str, ...]:
        locations = spec.submodule_search_locations
        if locations is None:
            return ()
        return tuple(_normal_path(value) for value in locations)

    def find_spec(
        self, fullname: str, path: object = None, target: object = None
    ) -> Any:
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None:
            return None
        origin = spec.origin
        locations = self._locations(spec)
        repository_origin = isinstance(origin, str) and _is_within(origin, self._src)
        repository_location = any(_is_within(value, self._src) for value in locations)
        if fullname in self._expected:
            if not isinstance(spec.loader, importlib.machinery.SourceFileLoader):
                raise ImportError(f"unexpected loader for {fullname}")
            if not isinstance(origin, str) or _normal_path(origin) != self._expected[fullname]:
                raise ImportError(f"unexpected project origin for {fullname}")
            expected_package = self._expected_packages.get(fullname)
            if expected_package is None:
                if locations:
                    raise ImportError(f"unexpected module locations for {fullname}")
            elif locations != (expected_package,):
                raise ImportError(f"unexpected package locations for {fullname}")
            cached = spec.cached
            if not isinstance(cached, str) or not _is_within(
                cached, self._pycache_prefix
            ):
                raise ImportError(f"unexpected cache path for {fullname}")
            self._observed[fullname] = {
                "origin": _normal_path(origin),
                "cached": _normal_path(cached),
                "locations": locations,
            }
        elif repository_origin or repository_location:
            raise ImportError(f"unexpected repository import origin for {fullname}")
        return spec

    def verify_complete(self, worker_path: Path) -> None:
        if not sys.meta_path or sys.meta_path[0] is not self:
            raise ImportError("project origin guard is not first in sys.meta_path")
        if set(self._observed) != set(self._expected):
            raise ImportError("expected project imports were not all observed")
        if not sys.path or _normal_path(sys.path[0]) != self._src:
            raise ImportError("repository src root is not the first import path")
        allowed = set(self._expected)
        for name, module in tuple(sys.modules.items()):
            module_file = getattr(module, "__file__", None)
            if not isinstance(module_file, str) or not _is_within(
                module_file, self._src
            ):
                continue
            if name == "__main__":
                if _normal_path(module_file) != _normal_path(worker_path):
                    raise ImportError("unexpected __main__ repository origin")
                continue
            if name not in allowed:
                raise ImportError(f"unexpected loaded project module {name}")
            if _normal_path(module_file) != self._expected[name]:
                raise ImportError(f"loaded project module origin changed for {name}")
            cached = getattr(module, "__cached__", None)
            if not isinstance(cached, str) or not _is_within(
                cached, self._pycache_prefix
            ):
                raise ImportError(f"loaded project cache path changed for {name}")

    def attestation(self, schema_version: str) -> dict[str, Any]:
        def digest(value: str) -> str:
            return hashlib.sha256(value.encode("utf-8")).hexdigest()

        return {
            "schema_version": schema_version,
            "python_implementation": sys.implementation.name,
            "python_cache_tag": sys.implementation.cache_tag,
            "python_version": [
                sys.version_info.major,
                sys.version_info.minor,
                sys.version_info.micro,
            ],
            "pycache_prefix_sha256": digest(self._pycache_prefix),
            "runtime_flags": {
                "dont_write_bytecode": bool(sys.dont_write_bytecode),
                "isolated": int(sys.flags.isolated),
                "no_site": int(sys.flags.no_site),
                "ignore_environment": int(sys.flags.ignore_environment),
                "safe_path": int(sys.flags.safe_path),
                "optimize": int(sys.flags.optimize),
            },
            "guard_meta_path_index": next(
                index for index, value in enumerate(sys.meta_path) if value is self
            ),
            "project_specs": [
                {
                    "module_name": name,
                    "origin_sha256": digest(self._observed[name]["origin"]),
                    "cached_path_sha256": digest(self._observed[name]["cached"]),
                    "package_location_sha256s": [
                        digest(value)
                        for value in self._observed[name]["locations"]
                    ],
                    "loader": "SourceFileLoader",
                    "cached_under_bound_prefix_verified": _is_within(
                        self._observed[name]["cached"], self._pycache_prefix
                    ),
                }
                for name in self._expected
            ],
            "guard_finalized": True,
        }


def _prepare_direct_script_runtime() -> tuple[_ProjectOriginGuard, Path]:
    if len(sys.argv) != 2 or not sys.argv[1].startswith(
        EXPECTED_PYCACHE_PREFIX_ARGUMENT
    ):
        raise ImportError("one exact expected pycache-prefix argument is required")
    value = sys.argv[1][len(EXPECTED_PYCACHE_PREFIX_ARGUMENT) :]
    if not value or "\x00" in value or not os.path.isabs(value):
        raise ImportError("expected pycache prefix must be one absolute path")
    expected_prefix = Path(value)
    configured_prefix = sys.pycache_prefix
    if not isinstance(configured_prefix, str) or (
        _normal_path(configured_prefix) != _normal_path(expected_prefix)
    ):
        raise ImportError("interpreter pycache prefix does not match the bound value")
    if not sys.dont_write_bytecode:
        raise ImportError("interpreter bytecode-write disable flag is absent")
    required_flags = {
        "isolated": 1,
        "no_site": 1,
        "ignore_environment": 1,
        "safe_path": 1,
    }
    for name, expected in required_flags.items():
        if getattr(sys.flags, name, None) != expected:
            raise ImportError(f"interpreter flag mismatch: {name}")

    worker_path = Path(__file__).resolve(strict=True)
    src_root = _normal_path(worker_path.parents[2])
    if any(_normal_path(value) == src_root for value in sys.path if value):
        raise ImportError("repository src root was present before guard installation")
    guard = _ProjectOriginGuard(worker_path, expected_prefix)
    sys.meta_path.insert(0, guard)
    sys.path.insert(0, str(worker_path.parents[2]))
    return guard, worker_path
def _write_error(prefix: bytes, value: object) -> None:
    # The error may contain an input-derived duplicate key or parser token.
    # Emit only a stable digest, never exception text or captured payload bytes.
    digest = hashlib.sha256(
        str(value).encode("utf-8", errors="replace")
    ).hexdigest().encode("ascii")
    sys.stderr.buffer.write(prefix + digest + b"\n")
    sys.stderr.buffer.flush()


def main() -> int:
    guard: _ProjectOriginGuard | None = None
    worker_path: Path | None = None
    try:
        if __package__ in {None, ""}:
            guard, worker_path = _prepare_direct_script_runtime()
        from llm_batch.grounding.p0_parser_process_protocol import (
            MAX_REQUEST_BYTES,
            P0ParserProcessProtocolError,
            RUNTIME_GUARD_ATTESTATION_SCHEMA,
            execute_request_bytes,
        )
    except BaseException as exc:
        _write_error(b"P0_PARSER_PROCESS_RUNTIME_GUARD_ERROR:", type(exc).__name__)
        return RUNTIME_GUARD_ERROR_EXIT

    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    try:
        if guard is not None:
            assert worker_path is not None
            guard.verify_complete(worker_path)
            runtime_attestation = guard.attestation(
                RUNTIME_GUARD_ATTESTATION_SCHEMA
            )
        else:
            runtime_attestation = None
        output = execute_request_bytes(
            raw, runtime_guard_attestation=runtime_attestation
        )
    except P0ParserProcessProtocolError as exc:
        _write_error(
            b"P0_PARSER_PROCESS_PROTOCOL_ERROR:",
            exc,
        )
        return PROTOCOL_ERROR_EXIT
    except BaseException as exc:  # pragma: no cover - defensive process boundary
        _write_error(
            b"P0_PARSER_PROCESS_INTERNAL_ERROR:",
            type(exc).__name__,
        )
        return INTERNAL_ERROR_EXIT
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXPECTED_PYCACHE_PREFIX_ARGUMENT",
    "INTERNAL_ERROR_EXIT",
    "PROTOCOL_ERROR_EXIT",
    "RUNTIME_GUARD_ERROR_EXIT",
    "main",
]
