#!/usr/bin/env python3
"""Audit that P0 fixture validation leaves existing Slang DB and publication journals unchanged."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "tools" / "validate_p0_grounding_contract.py"
DEFAULT_FIXTURE_DIRECTORY = REPO_ROOT / "tests" / "fixtures" / "p0_grounding_contract_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _discover_watch_paths() -> dict[str, list[Path]]:
    slang_path = REPO_ROOT / "slang_db" / "slang_db.json"
    journal_directory = REPO_ROOT / "out" / "publication_commit_journals"
    return {
        "CENTRAL_SLANG_DB": [slang_path] if slang_path.is_file() else [],
        "PUBLICATION_COMMIT_JOURNAL": (
            sorted(journal_directory.glob("*.jsonl")) if journal_directory.is_dir() else []
        ),
    }


def _snapshot(paths_by_kind: dict[str, list[Path]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in sorted(paths_by_kind):
        for path in paths_by_kind[kind]:
            resolved = path.resolve()
            if not resolved.is_file():
                raise ValueError(f"watched file disappeared: {resolved}")
            rows.append(
                {
                    "kind": kind,
                    "path": resolved.relative_to(REPO_ROOT).as_posix(),
                    "bytes": resolved.stat().st_size,
                    "sha256": _sha256(resolved),
                }
            )
    return rows


def audit(fixture_directory: Path) -> dict[str, Any]:
    watch_paths = _discover_watch_paths()
    before = _snapshot(watch_paths)
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "--directory", str(fixture_directory)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr or completed.stdout or "P0 validator failed")
    validation_receipt = json.loads(completed.stdout)
    after_paths = _discover_watch_paths()
    after = _snapshot(after_paths)
    required_watch_targets_present = all(watch_paths.values())
    watched_sets_unchanged = {
        kind: [path.resolve() for path in watch_paths[kind]]
        == [path.resolve() for path in after_paths[kind]]
        for kind in sorted(watch_paths)
    }
    unchanged = (
        required_watch_targets_present
        and before == after
        and all(watched_sets_unchanged.values())
    )
    material = {
        "schema_version": "p0_grounding_noninterference_audit_v1",
        "gate_status": (
            "GO_EXISTING_STATE_READONLY_AUDIT"
            if unchanged
            else "NO_GO_EXISTING_STATE_MUTATION_DETECTED"
        ),
        "evidence_scope": "EXISTING_CENTRAL_SLANG_DB_AND_PUBLICATION_JOURNALS",
        "fixture_gate_status": validation_receipt["gate_status"],
        "fixture_receipt_sha256": validation_receipt["receipt_sha256"],
        "watched_file_count": len(before),
        "required_watch_targets_present": required_watch_targets_present,
        "watched_sets_unchanged": watched_sets_unchanged,
        "before": before,
        "after": after,
        "full_scan_approval": False,
        "p0_phase_exit": False,
    }
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {**material, "receipt_sha256": hashlib.sha256(encoded).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_FIXTURE_DIRECTORY)
    args = parser.parse_args()
    receipt = audit(args.directory.resolve())
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if receipt["gate_status"] == "GO_EXISTING_STATE_READONLY_AUDIT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
