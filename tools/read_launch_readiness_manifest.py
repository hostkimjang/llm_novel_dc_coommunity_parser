from __future__ import annotations

"""Independently verify a no-runtime P3/P4 launch-readiness manifest."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_launch_readiness_manifest import read_packet


def read(path: Path) -> dict:
    return read_packet(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify a P3/P4 launch-readiness manifest")
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(read(args.manifest), ensure_ascii=False))
    except (OSError, ValueError) as exc:
        print(json.dumps({"gate": "NO_GO_LAUNCH_MANIFEST_READBACK", "runtime_started": False, "writes_to_production": False, "reason": str(exc)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
