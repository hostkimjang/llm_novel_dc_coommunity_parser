from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PATTERNS: dict[str, tuple[str, ...]] = {
    "seed_candidate": ("seed \ud6c4\ubcf4(",),
    "seed_excluded": ("\uc791\ud488 seed \uc81c\uc678",),
    "stale_relevant": (
        "\ucd5c\uc885 \ud310\uc815\uc740 \uad00\ub828 \ud3ec\uc2a4\ud2b8",
        "\uc791\ud488 \uad00\ub828 \ub2e8\uc11c\ub294 \ucda9\ubd84\ud558\uc9c0\ub9cc",
    ),
    "llm_flip": ("LLM(False)\u2192\ucd5c\uc885(True)",),
    "bad_phrase": (
        "\ub2e8\uc815\ud558\uae30 \uc5b4\ub824\uc6c0\ud558\uae30",
        "\ub2e8\uc815\ud558\uae30 \uc5b4\ub824\uc6c0\ud560",
        "\ud45c\uba74 \uacc4\uc5f4",
    ),
    "reread_wording_drift": (
        "\ud45c\ud604 \uc624\ud0c0/\ucd95\uc57d/\ub744\uc5b4\uc4f0\uae30 \uac00\ub2a5\uc131",
        "\ud45c\ud604 \uc624\ud0c0/\ucd95\uc57d \uac00\ub2a5\uc131",
        "\ud45c\ud604 \uc624\ud0c0/\ucd95\uc57d/\ub744\uc5b4\uc4f0\uae30 \ud328\ud134",
    ),
    "surface_reread_label_colon_payload": (
        "\ud45c\ud604 \uc624\ud0c0/\ucd95\uc57d \ud328\ud134(\ubc94\uc6a9):",
    ),
    "normalization": (
        "23\uc138\uc778 \uc904",
        "23\uc138/16\uc138",
        "X -> Y",
    ),
}

DEFAULT_EXCLUDED_SUFFIXES = (
    "_manifest.json",
    "_pending_snapshot.json",
    "_completed_subset_manifest.json",
    "_tool_report.json",
)


def result_version(path: Path) -> int | None:
    match = re.match(r"v(\d+)", path.name)
    if not match:
        return None
    return int(match.group(1))


def iter_result_files(
    paths: Iterable[Path],
    *,
    min_version: int = 0,
    include_manifests: bool = False,
) -> list[Path]:
    out: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        candidates = sorted(path.rglob("*.json")) if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.suffix.lower() != ".json":
                continue
            if not include_manifests and candidate.name.endswith(DEFAULT_EXCLUDED_SUFFIXES):
                continue
            version = result_version(candidate)
            if min_version > 0 and version is None:
                continue
            if version is not None and version < min_version:
                continue
            out.append(candidate)
    return out


def find_samples(text: str, needles: Iterable[str], *, limit: int = 2, window: int = 80) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for needle in needles:
        start = 0
        while len(samples) < limit:
            pos = text.find(needle, start)
            if pos < 0:
                break
            line = text.count("\n", 0, pos) + 1
            excerpt_start = max(0, pos - window)
            excerpt_end = min(len(text), pos + len(needle) + window)
            excerpt = text[excerpt_start:excerpt_end].replace("\r", "\\r").replace("\n", "\\n")
            samples.append(
                {
                    "needle": needle,
                    "offset": pos,
                    "line": line,
                    "excerpt": excerpt,
                }
            )
            start = pos + len(needle)
    return samples


def scan_text(
    text: str,
    *,
    patterns: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    patterns = patterns or DEFAULT_PATTERNS
    hit_counts: dict[str, int] = {}
    samples: dict[str, list[dict[str, Any]]] = {}
    for name, needles in patterns.items():
        count = sum(text.count(needle) for needle in needles)
        if count <= 0:
            continue
        hit_counts[name] = count
        samples[name] = find_samples(text, needles)
    return {
        "hits": sorted(hit_counts),
        "hit_counts": hit_counts,
        "samples": samples,
    }


def scan_file(path: Path, *, patterns: dict[str, tuple[str, ...]] | None = None) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    result = scan_text(text, patterns=patterns)
    return {
        "path": str(path),
        "name": path.name,
        "version": result_version(path),
        "size_bytes": path.stat().st_size,
        **result,
    }


def build_scan_report(
    paths: Iterable[Path],
    *,
    min_version: int = 0,
    include_manifests: bool = False,
) -> dict[str, Any]:
    files = iter_result_files(paths, min_version=min_version, include_manifests=include_manifests)
    file_results = [scan_file(path) for path in files]
    hit_files = [item for item in file_results if item["hits"]]
    hit_type_counts = Counter(hit for item in hit_files for hit in item["hits"])
    return {
        "scan_type": "reason_hygiene_raw_text",
        "min_version": min_version,
        "include_manifests": include_manifests,
        "patterns": {name: list(values) for name, values in DEFAULT_PATTERNS.items()},
        "files_scanned": len(file_results),
        "hit_files": len(hit_files),
        "clean_files": len(file_results) - len(hit_files),
        "hit_type_counts": dict(sorted(hit_type_counts.items())),
        "results": file_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan result JSON raw text for public reason hygiene regressions.")
    parser.add_argument("paths", nargs="+", type=Path, help="Result JSON files or directories to scan.")
    parser.add_argument("--min-version", type=int, default=0, help="Only scan vN files where N is at least this value.")
    parser.add_argument("--include-manifests", action="store_true", help="Include manifest/snapshot JSON files.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write JSON report to this path.")
    parser.add_argument("--fail-on-hit", action="store_true", help="Exit with status 1 when any hit is found.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_scan_report(
        args.paths,
        min_version=args.min_version,
        include_manifests=args.include_manifests,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 1 if args.fail_on_hit and report["hit_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
