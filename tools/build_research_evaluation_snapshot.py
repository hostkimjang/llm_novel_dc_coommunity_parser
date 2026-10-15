"""저장 자료 평가 snapshot 생성과 자체 해시 검산 CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from llm_batch.measurement.research_evaluation_snapshot import (
    SnapshotError, export_snapshot, verify_exported_snapshot,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="저장 artifact 읽기 전용 평가 snapshot")
    parser.add_argument("--spec")
    parser.add_argument("--output-dir")
    parser.add_argument("--research-root")
    parser.add_argument("--verify-dir")
    args = parser.parse_args(argv)
    if args.verify_dir:
        if any((args.spec, args.output_dir, args.research_root)):
            parser.error("--verify-dir은 export 인자와 함께 사용할 수 없습니다")
    elif not all((args.spec, args.output_dir, args.research_root)):
        parser.error("export에는 --spec --output-dir --research-root가 모두 필요합니다")
    try:
        if args.verify_dir:
            receipt = verify_exported_snapshot(args.verify_dir)
        else:
            manifest = export_snapshot(args.spec, args.output_dir, research_root=args.research_root)
            receipt = {"status": "EXPORTED", "binding_status": manifest["binding_status"],
                       "semantic_sha256": manifest["semantic_sha256"], "output_dir": args.output_dir,
                       "publication_authority": False}
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 2 if receipt["binding_status"] == "INVALID_BINDING" else 0
    except (SnapshotError, OSError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
