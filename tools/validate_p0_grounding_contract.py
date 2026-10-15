#!/usr/bin/env python3
"""Validate P0 source/lineage/four-axis fixture files and emit a receipt."""

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
    validate_fixture_directory,
)


DEFAULT_DIRECTORY = REPO_ROOT / "tests" / "fixtures" / "p0_grounding_contract_v1"


def validate(directory: Path) -> dict[str, object]:
    return validate_fixture_directory(directory)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    args = parser.parse_args()
    receipt = validate(args.directory.resolve())
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    print(payload, end="")
    return 0 if receipt["gate_status"] == "GO_P0_CONTRACT_FIXTURE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
