#!/usr/bin/env python3
"""Read-only validator for the actual-P0 schema-contract example directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    P0ActualContractError,
    validate_example_directory,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--directory",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "p0_actual_contract_example_v1",
    )
    args = parser.parse_args()
    try:
        receipt = validate_example_directory(args.directory)
    except (OSError, P0ActualContractError) as exc:
        print(json.dumps({"validation_status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
