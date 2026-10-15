"""로컬 capture만 읽어 새 커뮤니티 지식 snapshot을 생성한다."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from llm_batch.grounding.community_knowledge_builder import CommunityKnowledgeBuildError, build_snapshot


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="로컬 capture → 중립 관측 → 새 지식 snapshot")
    parser.add_argument("--capture-manifest", required=True)
    parser.add_argument("--capture-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = build_snapshot(args.capture_manifest, args.output_dir, capture_root=args.capture_root, output_root=args.output_root)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0
    except (CommunityKnowledgeBuildError, OSError, ValueError) as exc:
        print(json.dumps({"status": "ERROR", "code": getattr(exc, "code", type(exc).__name__), "error": str(exc),
                          "failure_directory": getattr(exc, "failure_directory", None)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
