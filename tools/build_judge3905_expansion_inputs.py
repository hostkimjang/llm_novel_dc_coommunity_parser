from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_judge3905_source_enriched_canary import (
    build_enriched_row,
    expand_patterns,
    index_sources,
    post_id_key,
    write_json,
    write_jsonl,
)
from tools.test_run_dashboard_policy import (
    dashboard_contract,
    expected_effective_parallel,
    requested_parallel_for_test_run,
)


SEVERITY_RANK = {"high": 0, "med": 1, "medium": 1, "low": 2}
HIGH_RISK_BUCKETS = {
    "recall": {"under_resolved_false_negative"},
    "precision": {"cross_media_or_famous_mismatch", "wrong_work", "over_resolved", "garbage_title"},
    "hygiene": {"wrong_discussion_type", "wrong_relevance", "title_noisy_ocr"},
}
DEFAULT_QUOTAS = {"recall": 12, "precision": 16, "hygiene": 8}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sort_post_id(value: Any) -> tuple[int, str]:
    key = post_id_key(value)
    return (int(key), "") if key.isdigit() else (10**18, key)


def seed_group(disagreement_type: str) -> str:
    for group, types in HIGH_RISK_BUCKETS.items():
        if disagreement_type in types:
            return group
    return "other"


def load_excluded_ids(paths: Iterable[Path]) -> set[str]:
    excluded: set[str] = set()
    for path in paths:
        if not path or not path.is_file():
            continue
        payload = load_json(path)
        if isinstance(payload, dict):
            for key in ("canary_post_ids", "post_ids", "selected_post_ids"):
                value = payload.get(key)
                if isinstance(value, list):
                    excluded.update(post_id_key(item) for item in value)
            rows = payload.get("rows")
            if isinstance(rows, list):
                excluded.update(post_id_key(row.get("post_id")) for row in rows if isinstance(row, dict))
        elif isinstance(payload, list):
            excluded.update(post_id_key(row.get("post_id")) for row in payload if isinstance(row, dict))
    return {pid for pid in excluded if pid}


def _severity_key(seed: dict[str, Any]) -> int:
    return SEVERITY_RANK.get(str(seed.get("severity") or "").lower(), 9)


def _risk_sort_key(seed: dict[str, Any]) -> tuple[Any, ...]:
    source = seed.get("source") if isinstance(seed.get("source"), dict) else {}
    return (
        _severity_key(seed),
        0 if bool(source.get("image_count")) else 1,
        str(seed.get("disagreement_type") or ""),
        sort_post_id(seed.get("post_id")),
    )


def select_high_risk_seeds(
    seeds: list[dict[str, Any]],
    *,
    excluded_ids: set[str],
    quotas: dict[str, int],
    total: int,
) -> list[dict[str, Any]]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seed in seeds:
        pid = post_id_key(seed.get("post_id"))
        dtype = str(seed.get("disagreement_type") or "")
        group = seed_group(dtype)
        if not pid or pid in excluded_ids or group == "other":
            continue
        by_group[group].append(seed)

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for group in ("recall", "precision", "hygiene"):
        rows = sorted(by_group.get(group, []), key=_risk_sort_key)
        quota = max(0, int(quotas.get(group, 0)))
        for row in rows[:quota]:
            pid = post_id_key(row.get("post_id"))
            if pid and pid not in selected_ids:
                selected.append(row)
                selected_ids.add(pid)

    if len(selected) < total:
        remaining = [
            row
            for group_rows in by_group.values()
            for row in group_rows
            if post_id_key(row.get("post_id")) not in selected_ids
        ]
        for row in sorted(remaining, key=_risk_sort_key):
            if len(selected) >= total:
                break
            pid = post_id_key(row.get("post_id"))
            if pid and pid not in selected_ids:
                selected.append(row)
                selected_ids.add(pid)

    return selected[:total]


def seed_to_base_row(seed: dict[str, Any]) -> dict[str, Any]:
    source = seed.get("source") if isinstance(seed.get("source"), dict) else {}
    judge = seed.get("judge") if isinstance(seed.get("judge"), dict) else {}
    pid = seed.get("post_id")
    return {
        "post_id": pid,
        "title": source.get("title") or "",
        "url": source.get("url")
        or f"https://gall.dcinside.com/mgallery/board/view/?id=genrenovel&no={post_id_key(pid)}",
        "gallery_id": "genrenovel",
        "_judge_seed": {
            "seed_group": seed.get("seed_group") or seed_group(str(seed.get("disagreement_type") or "")),
            "disagreement_type": seed.get("disagreement_type"),
            "severity": seed.get("severity"),
            "shadow_label_before": seed.get("shadow_label"),
            "source_path": source.get("source_path"),
            "source_img_count": source.get("image_count") or 0,
            "expansion_kind": "high_risk",
            "judge_note": judge.get("note"),
            "judge_claude_take": judge.get("claude_take"),
        },
    }


def build_high_risk_expansion(
    *,
    registry_path: Path,
    source_patterns: list[str],
    exclude_paths: list[Path],
    out_dir: Path,
    prefix: str,
    total: int,
    quotas: dict[str, int],
) -> dict[str, Any]:
    registry = load_json(registry_path)
    seeds = [row for row in registry.get("seeds", []) if isinstance(row, dict)]
    excluded_ids = load_excluded_ids(exclude_paths)
    selected = select_high_risk_seeds(seeds, excluded_ids=excluded_ids, quotas=quotas, total=total)
    wanted_ids = {post_id_key(seed.get("post_id")) for seed in selected}
    source_paths = expand_patterns(source_patterns)
    source_by_id = index_sources(source_paths, wanted_ids)

    rows: list[dict[str, Any]] = []
    restore_rows: list[dict[str, Any]] = []
    missing_source: list[str] = []
    for seed in selected:
        pid = post_id_key(seed.get("post_id"))
        source_row = source_by_id.get(pid)
        if source_row is None:
            missing_source.append(pid)
        row, report = build_enriched_row(seed_to_base_row(seed), source_row)
        row["_judge_seed"].update(
            {
                "seed_group": seed.get("seed_group"),
                "disagreement_type": seed.get("disagreement_type"),
                "severity": seed.get("severity"),
                "shadow_label_before": seed.get("shadow_label"),
                "expansion_kind": "high_risk",
            }
        )
        rows.append(row)
        restore_rows.append(report)

    out_dir.mkdir(parents=True, exist_ok=True)
    input_path = out_dir / f"{prefix}_highrisk_expansion_input.jsonl"
    manifest_path = out_dir / f"{prefix}_highrisk_expansion_manifest.json"
    restore_path = out_dir / f"{prefix}_highrisk_expansion_restore_report.json"
    result_path = out_dir / f"{prefix}_highrisk_expansion_result.json"
    compare_path = out_dir / f"{prefix}_highrisk_expansion_compare.json"
    compare_md_path = out_dir / f"{prefix}_highrisk_expansion_compare_ko.md"
    result_manifest_path = result_path.with_name(result_path.stem + "_manifest.json")
    recommended_parallel = requested_parallel_for_test_run(len(rows))
    expected_parallel = expected_effective_parallel(len(rows))

    manifest = {
        "generated_at": now(),
        "kind": "high_risk_expansion",
        "registry_path": registry_path.as_posix(),
        "source_patterns": source_patterns,
        "source_paths": [path.as_posix() for path in source_paths],
        "exclude_paths": [path.as_posix() for path in exclude_paths],
        "excluded_post_count": len(excluded_ids),
        "requested_total": total,
        "selected_count": len(rows),
        "recommended_parallel": recommended_parallel,
        "expected_effective_parallel": expected_parallel,
        "missing_source_count": len(missing_source),
        "missing_source_post_ids": sorted(missing_source, key=sort_post_id),
        "canary_post_ids": [row.get("post_id") for row in rows],
        "counts": {
            "by_group": dict(Counter((row.get("_judge_seed") or {}).get("seed_group") for row in rows)),
            "by_type": dict(Counter((row.get("_judge_seed") or {}).get("disagreement_type") for row in rows)),
            "by_severity": dict(Counter((row.get("_judge_seed") or {}).get("severity") for row in rows)),
            "image_post_count": sum(1 for row in rows if row.get("image_urls")),
            "by_restore_status": dict(Counter(row.get("restore_status") for row in restore_rows)),
        },
        "restore_rows": restore_rows,
        "outputs": {
            "input": input_path.as_posix(),
            "manifest": manifest_path.as_posix(),
            "restore_report": restore_path.as_posix(),
            "expected_result": result_path.as_posix(),
            "expected_compare_json": compare_path.as_posix(),
            "expected_compare_md": compare_md_path.as_posix(),
        },
        "recommended_commands": {
            "expert_main": (
                f"python expert_main.py --input {input_path.as_posix()} "
                f"--output {result_path.as_posix()} --server-type vllm "
                f"--parallel {recommended_parallel} --reuse-shards-only "
                "--slang-db on --vlm on --ocr on --require-vlm-ocr-for-images"
            ),
            "compare": (
                f"python tools/build_judge_seed_registry.py compare "
                f"--registry {registry_path.as_posix()} "
                f"--canary-result {result_path.as_posix()} "
                f"--manifest {manifest_path.as_posix()} "
                f"--output-json {compare_path.as_posix()} "
                f"--output-md {compare_md_path.as_posix()}"
            ),
        },
        "execution_contract": {
            "test_run_requested_parallel": recommended_parallel,
            "expected_effective_parallel": expected_parallel,
            "dashboard_contract": dashboard_contract(manifest_path=result_manifest_path),
            "forbidden_flags": ["--no-dashboard"],
        },
        "gate": {
            "run_integrity": "PENDING",
            "semantic_quality": "REVIEW-LOCKED",
            "reason": "selected high-risk seed expansion; expert_main run and compare are required.",
        },
    }
    write_jsonl(input_path, rows)
    write_json(manifest_path, manifest)
    write_json(restore_path, {"generated_at": manifest["generated_at"], "rows": restore_rows})
    return manifest


def parse_quota(value: str) -> tuple[str, int]:
    key, raw_count = value.split("=", 1)
    return key.strip(), int(raw_count.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Build JUDGE3905 high-risk expansion inputs.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--exclude", type=Path, action="append", default=[])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="judge3905_p0")
    parser.add_argument("--total", type=int, default=36)
    parser.add_argument("--quota", action="append", default=[], help="Override group quota, e.g. recall=12")
    parser.add_argument("--seed", type=int, default=3905, help="Reserved for future random-baseline selection.")
    args = parser.parse_args()

    random.seed(args.seed)
    quotas = dict(DEFAULT_QUOTAS)
    for item in args.quota:
        key, value = parse_quota(item)
        quotas[key] = value

    manifest = build_high_risk_expansion(
        registry_path=args.registry,
        source_patterns=args.source,
        exclude_paths=args.exclude,
        out_dir=args.out_dir,
        prefix=args.prefix,
        total=args.total,
        quotas=quotas,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
