#!/usr/bin/env python3
"""Validate the v2 authority example's annotation event bytes read-only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.grounding.p0_actual_authority_contract import (  # noqa: E402
    AUTHORITY_EXAMPLE_FILES_V2,
    EXAMPLE_ORIGIN as AUTHORITY_EXAMPLE_ORIGIN,
    P0ActualAuthorityError,
)
from llm_batch.grounding.p0_actual_authority_event_bytes import (  # noqa: E402
    verify_annotation_event_bytes,
)
from llm_batch.grounding.p0_actual_registry_contract import (  # noqa: E402
    EXAMPLE_ORIGIN as EVENT_EXAMPLE_ORIGIN,
)
from tools.validate_p0_actual_authority_contract_examples import (  # noqa: E402
    DEFAULT_DIRECTORY,
    DEFAULT_FOUNDATION_DIRECTORY,
    validate_example_directory,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument(
        "--foundation-directory", type=Path, default=DEFAULT_FOUNDATION_DIRECTORY
    )
    args = parser.parse_args()
    try:
        validate_example_directory(args.directory, args.foundation_directory)
        rows = {
            logical_name: json.loads(
                (args.directory / basename).read_text(encoding="utf-8")
            )
            for logical_name, basename in AUTHORITY_EXAMPLE_FILES_V2.items()
        }
        receipt = verify_annotation_event_bytes(
            event_path=(
                args.foundation_directory / "p0_annotation_events_example_v1.jsonl"
            ),
            predecessor_checkpoint=rows["predecessor_checkpoint"],
            predecessor_head_map=rows["predecessor_head_map"],
            current_checkpoint=rows["current_checkpoint"],
            current_head_map=rows["head_map"],
            expected_authority_origin=AUTHORITY_EXAMPLE_ORIGIN,
            expected_event_origin=EVENT_EXAMPLE_ORIGIN,
        )
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
