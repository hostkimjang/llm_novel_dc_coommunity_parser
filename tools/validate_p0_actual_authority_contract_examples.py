#!/usr/bin/env python3
"""Read-only validator for the actual-P0 authority schema example."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding.p0_actual_authority_contract import (  # noqa: E402
    AUTHORITY_EXAMPLE_FILES_V2,
    EXAMPLE_ORIGIN,
    P0ActualAuthorityError,
    validate_authority_foundation_bundle,
)
from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    validate_example_directory as validate_foundation_directory,
)


DEFAULT_DIRECTORY = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_authority_contract_example_v2"
)
DEFAULT_FOUNDATION_DIRECTORY = (
    REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1"
)

FILES = AUTHORITY_EXAMPLE_FILES_V2


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise P0ActualAuthorityError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _load_json(path: Path, *, require_canonical: bool = True) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise P0ActualAuthorityError(f"authority example is not a regular file: {path.name}")
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf") or not raw.endswith(b"\n"):
        raise P0ActualAuthorityError(f"authority example framing mismatch: {path.name}")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P0ActualAuthorityError(
            f"authority example must be canonical UTF-8 JSON: {path.name}"
        ) from exc
    if not isinstance(value, dict):
        raise P0ActualAuthorityError(f"authority example must be an object: {path.name}")
    if require_canonical:
        expected = (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        if raw != expected:
            raise P0ActualAuthorityError(
                f"authority example must use canonical JSON bytes: {path.name}"
            )
    return value


def validate_example_directory(
    directory: str | Path,
    foundation_directory: str | Path,
) -> dict[str, Any]:
    requested_root = Path(directory)
    if requested_root.is_symlink():
        raise P0ActualAuthorityError("authority example directory must not be a symlink")
    root = requested_root.resolve()
    foundation_root = Path(foundation_directory).resolve()
    if not root.is_dir() or root.is_symlink():
        raise P0ActualAuthorityError("authority example directory is missing or unsafe")
    present = {path.name for path in root.iterdir()}
    expected = set(FILES.values())
    if present != expected:
        raise P0ActualAuthorityError(
            f"authority example file set mismatch: missing={sorted(expected - present)}, "
            f"extra={sorted(present - expected)}"
        )
    rows = {name: _load_json(root / basename) for name, basename in FILES.items()}
    foundation_receipt = validate_foundation_directory(foundation_root)
    foundation_manifest_path = (
        foundation_root / "p0_actual_contract_example_manifest_v1.json"
    )
    foundation_manifest = _load_json(
        foundation_manifest_path, require_canonical=False
    )
    return validate_authority_foundation_bundle(
        **rows,
        expected_origin=EXAMPLE_ORIGIN,
        foundation_manifest_sha256=foundation_manifest["manifest_sha256"],
        foundation_receipt_sha256=foundation_receipt["receipt_sha256"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument(
        "--foundation-directory", type=Path, default=DEFAULT_FOUNDATION_DIRECTORY
    )
    args = parser.parse_args()
    try:
        receipt = validate_example_directory(args.directory, args.foundation_directory)
    except (OSError, P0ActualAuthorityError, ValueError) as exc:
        print(
            json.dumps(
                {"validation_status": "FAIL", "error": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
