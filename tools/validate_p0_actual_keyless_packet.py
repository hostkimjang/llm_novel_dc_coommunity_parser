"""Caller-pinned key-less actual-P0 packet directory를 읽기 전용 검증한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from llm_batch.grounding.p0_actual_packet_contract import (
    ACTUAL_ORIGIN,
    EXAMPLE_ORIGIN,
    P0ActualPacketError,
    validate_packet_directory,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "고정 inventory와 caller-pinned manifest SHA로 key-less P0 packet을 "
            "검증한다. 성공해도 external authority/OS witness 전에는 NO_GO다."
        )
    )
    parser.add_argument("packet_dir", type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument(
        "--origin",
        choices=(ACTUAL_ORIGIN, EXAMPLE_ORIGIN),
        default=ACTUAL_ORIGIN,
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        receipt = validate_packet_directory(
            args.packet_dir,
            expected_manifest_sha256=args.expected_manifest_sha256,
            expected_origin=args.origin,
        )
    except (OSError, P0ActualPacketError) as exc:
        print(
            json.dumps(
                {
                    "schema_validation": "FAIL_CLOSED",
                    "gate_status": "NO_GO_ACTUAL_P0_PACKET_INVALID",
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
