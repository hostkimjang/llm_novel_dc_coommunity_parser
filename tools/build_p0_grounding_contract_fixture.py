#!/usr/bin/env python3
"""Build the deterministic, synthetic-only P0 grounding contract fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding.p0_grounding_contract import (  # noqa: E402
    build_fixture_manifest,
    build_synthetic_contract_fixture,
    jsonl_bytes,
)


DEFAULT_DIRECTORY = REPO_ROOT / "tests" / "fixtures" / "p0_grounding_contract_v1"


def _write_new_or_identical(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"refusing to overwrite non-identical fixture: {path}")
        return
    path.write_bytes(payload)


def build(directory: Path) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=True)
    source_path = directory / "p0_source_claim_contract_v1.jsonl"
    context_path = directory / "p0_context_decision_contract_v1.jsonl"
    manifest_path = directory / "p0_grounding_contract_fixture_manifest_v1.json"
    sources, contexts = build_synthetic_contract_fixture()
    _write_new_or_identical(source_path, jsonl_bytes(sources))
    _write_new_or_identical(context_path, jsonl_bytes(contexts))
    manifest = build_fixture_manifest(
        source_path=source_path,
        context_path=context_path,
        source_count=len(sources),
        context_count=len(contexts),
    )
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    _write_new_or_identical(manifest_path, manifest_payload)
    return {
        "directory": str(directory),
        "source_claim_count": len(sources),
        "context_count": len(contexts),
        "manifest_sha256": manifest["manifest_sha256"],
        "fixture_origin": manifest["fixture_origin"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    result = build(args.directory.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
