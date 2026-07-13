from __future__ import annotations

"""Re-verify a captured no-write launch preflight receipt."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_launch_packet_preflight import LaunchPacketPreflightError, read_preflight_receipt


def read(path: Path) -> dict:
    return read_preflight_receipt(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-verify a captured no-write launch preflight receipt")
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(read(args.receipt), ensure_ascii=False))
    except (LaunchPacketPreflightError, OSError, ValueError) as exc:
        print(json.dumps({"gate": "NO_GO_LAUNCH_PACKET_PREFLIGHT_RECEIPT_READBACK", "runtime_started": False, "writes_to_production": False, "reason": str(exc)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
