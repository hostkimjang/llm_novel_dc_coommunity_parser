#!/usr/bin/env python3
"""동결 2,712행 정본에서 재현 가능한 회귀 cohort와 실행 bundle을 만든다.

선정은 오직 정본 ledger의 구조화 판정과 중재 ledger의 상태를 사용한다.
게시글 ID, 제목, 약칭을 코드에 넣지 않으며 raw result는 post_id로 exact join한 뒤
`analysis_result`/`run_meta`를 제거해 ``expert_main.py`` 재실행 입력으로 투영한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO_ROOT / "out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl"
DEFAULT_RAW_RESULT = REPO_ROOT / "out/expert_result_20260715_143806_848671.json"
DEFAULT_CROSS_REVIEW = REPO_ROOT / "out/live_full_row_review_20260715_143806_848671_20260716/high_risk_cross_review_ledger.jsonl"
DEFAULT_ARBITRATION_DIR = REPO_ROOT / "out/live_full_row_review_20260715_143806_848671_20260716/arbitration_verdicts"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "out/frozen_2712_regression_cohorts_20260716"

PROFILE_COUNTS = {
    "published_intervention": 35,
    "fn_title_missing": 339,
    "fn_direct_ocr": 107,
    "fp_non_novel": 72,
    "wrong_work": 36,
    "multiwork": 91,
    "dashboard_title_mismatch": 7,
    "arbitration": 64,
    "pass": 230,
    "safe_no_title": 1580,
    "ultra_safe_no_title": 188,
}

PREDICATES = {
    "published_intervention": "pipeline.publish_allowed is true AND independent_semantic_verdict.dashboard_action != 'KEEP'",
    "fn_title_missing": "independent_semantic_verdict.review_verdict == 'FN_TITLE_MISSING'",
    "fn_direct_ocr": "FN_TITLE_MISSING AND len(source_evidence.explicit_ocr_titles) > 0",
    "fp_non_novel": "independent_semantic_verdict.review_verdict == 'FP_NONNOVEL'",
    "wrong_work": "independent_semantic_verdict.review_verdict == 'WRONG_WORK'",
    "multiwork": "independent_semantic_verdict.review_verdict == 'MULTIWORK_HOLD_CORRECT'",
    "dashboard_title_mismatch": "independent_semantic_verdict.review_verdict == 'DASHBOARD_TITLE_MISMATCH'",
    "arbitration": "high_risk_cross_review.cross_review_status == 'REQUIRES_ARBITRATION' AND post_id occurs exactly once in arbitration verdicts",
    "pass": "independent_semantic_verdict.review_verdict == 'PASS'",
    "safe_no_title": "review_verdict in {'NOISE_CORRECT','CONTEXT_ONLY_CORRECT'} AND dashboard_action == 'NOT_APPLICABLE'",
    "ultra_safe_no_title": "safe_no_title AND image_count == 0 AND explicit_ocr_titles empty AND title_candidates empty AND comments_count == 0",
}

BUNDLE_SPECS = {
    "publication_safety": (
        "published_intervention",
        "fp_non_novel",
        "wrong_work",
        "multiwork",
        "dashboard_title_mismatch",
        "arbitration",
    ),
    "title_recovery": ("fn_direct_ocr", "fn_without_direct_ocr"),
    "retention_controls": ("pass", "ultra_safe_no_title", "safe_no_title_without_ultra"),
}


def _post_id(row: Mapping[str, Any], *, label: str) -> str:
    value = row.get("post_id")
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{label}: post_id missing or invalid")
    return str(value).strip()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: row must be an object")
        rows.append(value)
    return rows


def _index_unique(rows: Sequence[dict[str, Any]], *, label: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
    order: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        post_id = _post_id(row, label=label)
        if post_id in index:
            duplicates.append(post_id)
        else:
            order.append(post_id)
            index[post_id] = row
    if duplicates:
        sample = sorted(set(duplicates))[:10]
        raise ValueError(f"{label}: duplicate post_id values: {sample}")
    return order, index


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(data)


def _file_ref(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": _sha256_bytes(data)}


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def _verdict(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("independent_semantic_verdict")
    if not isinstance(value, dict):
        raise ValueError(f"ledger post_id={_post_id(row, label='ledger')}: independent_semantic_verdict missing")
    return value


def _evidence(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("source_evidence")
    if not isinstance(value, dict):
        raise ValueError(f"ledger post_id={_post_id(row, label='ledger')}: source_evidence missing")
    return value


def _is_ultra_safe(row: Mapping[str, Any]) -> bool:
    evidence = _evidence(row)
    return (
        (evidence.get("image_count") or 0) == 0
        and not evidence.get("explicit_ocr_titles")
        and not evidence.get("title_candidates")
        and (evidence.get("comments_count") or 0) == 0
    )


def _cohort_predicates(arbitration_ids: set[str]) -> dict[str, Callable[[Mapping[str, Any]], bool]]:
    def verdict_is(name: str) -> Callable[[Mapping[str, Any]], bool]:
        return lambda row: _verdict(row).get("review_verdict") == name

    safe = lambda row: (
        _verdict(row).get("review_verdict") in {"NOISE_CORRECT", "CONTEXT_ONLY_CORRECT"}
        and _verdict(row).get("dashboard_action") == "NOT_APPLICABLE"
    )
    return {
        "published_intervention": lambda row: (row.get("pipeline") or {}).get("publish_allowed") is True
        and _verdict(row).get("dashboard_action") != "KEEP",
        "fn_title_missing": verdict_is("FN_TITLE_MISSING"),
        "fn_direct_ocr": lambda row: verdict_is("FN_TITLE_MISSING")(row)
        and bool(_evidence(row).get("explicit_ocr_titles")),
        "fp_non_novel": verdict_is("FP_NONNOVEL"),
        "wrong_work": verdict_is("WRONG_WORK"),
        "multiwork": verdict_is("MULTIWORK_HOLD_CORRECT"),
        "dashboard_title_mismatch": verdict_is("DASHBOARD_TITLE_MISMATCH"),
        "arbitration": lambda row: _post_id(row, label="ledger") in arbitration_ids,
        "pass": verdict_is("PASS"),
        "safe_no_title": safe,
        "ultra_safe_no_title": lambda row: safe(row) and _is_ultra_safe(row),
    }


def _source_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"analysis_result", "run_meta"}}


def _round_robin_stratified(
    strata: Sequence[tuple[str, Sequence[str]]], *, cap: int, ordinal: Mapping[str, int]
) -> tuple[list[str], dict[str, int]]:
    if cap < 1:
        raise ValueError("bundle cap must be positive")
    cursors = {name: 0 for name, _ in strata}
    selected: set[str] = set()
    credited = Counter()
    while len(selected) < cap:
        progressed = False
        for name, values in strata:
            cursor = cursors[name]
            while cursor < len(values) and values[cursor] in selected:
                cursor += 1
            cursors[name] = cursor
            if cursor >= len(values):
                continue
            post_id = values[cursor]
            cursors[name] += 1
            selected.add(post_id)
            credited[name] += 1
            progressed = True
            if len(selected) >= cap:
                break
        if not progressed:
            break
    return sorted(selected, key=lambda post_id: (ordinal[post_id], post_id)), dict(sorted(credited.items()))


def _load_arbitration_ids(cross_review_path: Path, verdict_paths: Sequence[Path]) -> tuple[set[str], dict[str, Any]]:
    cross_rows = _read_jsonl(cross_review_path)
    _, cross_index = _index_unique(cross_rows, label="high-risk cross-review ledger")
    required = {
        post_id
        for post_id, row in cross_index.items()
        if row.get("cross_review_status") == "REQUIRES_ARBITRATION"
    }
    unknown = sorted(
        {
            str(row.get("cross_review_status"))
            for row in cross_rows
            if row.get("cross_review_status") not in {"AGREE", "REQUIRES_ARBITRATION"}
        }
    )
    if unknown:
        raise ValueError(f"high-risk cross-review ledger: unsupported status values: {unknown}")
    verdict_rows: list[dict[str, Any]] = []
    for path in verdict_paths:
        verdict_rows.extend(_read_jsonl(path))
    verdict_order, _ = _index_unique(verdict_rows, label="arbitration verdicts")
    verdict_ids = set(verdict_order)
    if required != verdict_ids:
        raise ValueError(
            "arbitration coverage mismatch: "
            f"missing={sorted(required - verdict_ids)[:10]}, extra={sorted(verdict_ids - required)[:10]}"
        )
    return required, {
        "cross_review_rows": len(cross_rows),
        "required_arbitration_rows": len(required),
        "arbitration_verdict_rows": len(verdict_rows),
        "coverage": "EXACT",
    }


def build_cohorts(
    *,
    ledger_path: Path,
    raw_result_path: Path,
    cross_review_path: Path,
    arbitration_verdict_paths: Sequence[Path],
    output_dir: Path,
    profile: str = "frozen2712",
    family_cap: int = 192,
    cross_family_cap: int = 256,
    requested_parallel: int = 16,
) -> dict[str, Any]:
    if requested_parallel < 1:
        raise ValueError("requested_parallel must be positive")
    ledger_rows = _read_jsonl(ledger_path)
    ledger_order, ledger_index = _index_unique(ledger_rows, label="final adjudication ledger")
    raw_payload = _read_json(raw_result_path)
    if not isinstance(raw_payload, list) or not all(isinstance(row, dict) for row in raw_payload):
        raise ValueError("raw result must be a JSON array of objects")
    raw_order, raw_index = _index_unique(raw_payload, label="raw result")
    missing_raw = [post_id for post_id in ledger_order if post_id not in raw_index]
    if missing_raw:
        raise ValueError(f"raw result missing ledger post_id values: {missing_raw[:10]}")

    arbitration_ids, arbitration_coverage = _load_arbitration_ids(
        cross_review_path, arbitration_verdict_paths
    )
    missing_arbitration_ledger = sorted(arbitration_ids - set(ledger_order))
    if missing_arbitration_ledger:
        raise ValueError(f"arbitration post_id missing from final ledger: {missing_arbitration_ledger[:10]}")

    predicates = _cohort_predicates(arbitration_ids)
    cohort_ids = {
        name: [post_id for post_id in ledger_order if predicate(ledger_index[post_id])]
        for name, predicate in predicates.items()
    }
    if profile == "frozen2712":
        if len(ledger_rows) != 2712:
            raise ValueError(f"frozen2712 profile requires 2712 ledger rows, got {len(ledger_rows)}")
        observed = {name: len(values) for name, values in cohort_ids.items()}
        if observed != PROFILE_COUNTS:
            mismatches = {
                name: {"expected": PROFILE_COUNTS[name], "observed": observed.get(name)}
                for name in PROFILE_COUNTS
                if observed.get(name) != PROFILE_COUNTS[name]
            }
            raise ValueError(f"frozen2712 cohort count mismatch: {mismatches}")
    elif profile != "none":
        raise ValueError(f"unsupported profile: {profile}")

    ordinal = {post_id: offset for offset, post_id in enumerate(ledger_order)}
    source_inputs = {post_id: _source_projection(raw_index[post_id]) for post_id in ledger_order}
    derived = {
        "fn_without_direct_ocr": [
            post_id for post_id in cohort_ids["fn_title_missing"] if post_id not in set(cohort_ids["fn_direct_ocr"])
        ],
        "safe_no_title_without_ultra": [
            post_id for post_id in cohort_ids["safe_no_title"] if post_id not in set(cohort_ids["ultra_safe_no_title"])
        ],
    }
    populations = {**cohort_ids, **derived}

    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_artifacts: dict[str, Any] = {}
    for name, post_ids in cohort_ids.items():
        path = output_dir / "cohorts" / f"{name}.jsonl"
        _write_jsonl(path, (source_inputs[post_id] for post_id in post_ids))
        cohort_artifacts[name] = {
            "predicate": PREDICATES[name],
            "count": len(post_ids),
            "post_id_order_sha256": _canonical_sha256(post_ids),
            "effective_parallel": min(len(post_ids), requested_parallel),
            "artifact": _file_ref(path),
        }

    bundle_artifacts: dict[str, Any] = {}
    family_populations: dict[str, list[str]] = {}
    for name, stratum_names in BUNDLE_SPECS.items():
        strata = [(stratum, populations[stratum]) for stratum in stratum_names]
        selected, credits = _round_robin_stratified(strata, cap=family_cap, ordinal=ordinal)
        family_populations[name] = sorted(
            {post_id for _, values in strata for post_id in values}, key=lambda post_id: ordinal[post_id]
        )
        path = output_dir / "bundles" / f"{name}.jsonl"
        _write_jsonl(path, (source_inputs[post_id] for post_id in selected))
        bundle_artifacts[name] = {
            "strata": list(stratum_names),
            "selection_algorithm": "round_robin_unique_then_restore_ledger_order_v1",
            "cap": family_cap,
            "eligible_unique_count": len(family_populations[name]),
            "count": len(selected),
            "stratum_selection_credits": credits,
            "post_id_order_sha256": _canonical_sha256(selected),
            "effective_parallel": min(len(selected), requested_parallel),
            "artifact": _file_ref(path),
        }

    cross_strata = [(name, family_populations[name]) for name in BUNDLE_SPECS]
    cross_selected, cross_credits = _round_robin_stratified(
        cross_strata, cap=cross_family_cap, ordinal=ordinal
    )
    cross_path = output_dir / "bundles" / "cross_family.jsonl"
    _write_jsonl(cross_path, (source_inputs[post_id] for post_id in cross_selected))
    bundle_artifacts["cross_family"] = {
        "strata": list(BUNDLE_SPECS),
        "selection_algorithm": "round_robin_unique_then_restore_ledger_order_v1",
        "cap": cross_family_cap,
        "eligible_unique_count": len({post_id for _, values in cross_strata for post_id in values}),
        "count": len(cross_selected),
        "stratum_selection_credits": cross_credits,
        "post_id_order_sha256": _canonical_sha256(cross_selected),
        "effective_parallel": min(len(cross_selected), requested_parallel),
        "artifact": _file_ref(cross_path),
    }

    pairwise_overlap: dict[str, int] = {}
    for left_index, left in enumerate(cohort_ids):
        for right in list(cohort_ids)[left_index + 1 :]:
            count = len(set(cohort_ids[left]) & set(cohort_ids[right]))
            if count:
                pairwise_overlap[f"{left}&{right}"] = count

    manifest = {
        "manifest_type": "frozen_2712_regression_cohort_bundle_v1",
        "profile": profile,
        "determinism": {
            "row_order": "final adjudication ledger order",
            "jsonl_encoding": "UTF-8, LF, compact JSON with sorted keys",
            "selection": "no random sampling; round-robin strata with unique post_id and ledger-order restoration",
            "timestamps_in_manifest": False,
        },
        "sources": {
            "final_adjudication_ledger": _file_ref(ledger_path),
            "raw_result": _file_ref(raw_result_path),
            "high_risk_cross_review_ledger": _file_ref(cross_review_path),
            "arbitration_verdicts": [_file_ref(path) for path in arbitration_verdict_paths],
        },
        "reconciliation": {
            "ledger_rows": len(ledger_rows),
            "ledger_unique_post_ids": len(ledger_index),
            "raw_rows": len(raw_payload),
            "raw_unique_post_ids": len(raw_index),
            "ledger_missing_from_raw": 0,
            "raw_extra_to_ledger": len(set(raw_order) - set(ledger_order)),
            "source_projection_removed_fields": ["analysis_result", "run_meta"],
            "arbitration": arbitration_coverage,
        },
        "parallel": {
            "requested_parallel": requested_parallel,
            "effective_parallel": min(len(ledger_rows), requested_parallel),
            "effective_parallel_policy": "min(input_count, requested_parallel) per artifact",
        },
        "cohorts": cohort_artifacts,
        "bundles": bundle_artifacts,
        "overlap": {
            "cohorts_are_not_additive": True,
            "ultra_safe_no_title_is_subset_of_safe_no_title": set(cohort_ids["ultra_safe_no_title"]).issubset(cohort_ids["safe_no_title"]),
            "fn_direct_ocr_is_subset_of_fn_title_missing": set(cohort_ids["fn_direct_ocr"]).issubset(cohort_ids["fn_title_missing"]),
            "pairwise_nonzero_counts": dict(sorted(pairwise_overlap.items())),
            "bundle_deduplication_key": "post_id",
        },
        "gate": "GO",
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--raw-result", type=Path, default=DEFAULT_RAW_RESULT)
    parser.add_argument("--cross-review-ledger", type=Path, default=DEFAULT_CROSS_REVIEW)
    parser.add_argument("--arbitration-verdict-dir", type=Path, default=DEFAULT_ARBITRATION_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--profile", choices=("frozen2712", "none"), default="frozen2712")
    parser.add_argument("--family-cap", type=int, default=192)
    parser.add_argument("--cross-family-cap", type=int, default=256)
    parser.add_argument("--requested-parallel", type=int, default=16)
    return parser


def main() -> int:
    args = _parser().parse_args()
    verdict_paths = sorted(args.arbitration_verdict_dir.glob("*.jsonl"))
    if not verdict_paths:
        raise ValueError(f"no arbitration verdict JSONL files: {args.arbitration_verdict_dir}")
    manifest = build_cohorts(
        ledger_path=args.ledger.resolve(),
        raw_result_path=args.raw_result.resolve(),
        cross_review_path=args.cross_review_ledger.resolve(),
        arbitration_verdict_paths=[path.resolve() for path in verdict_paths],
        output_dir=args.output_dir.resolve(),
        profile=args.profile,
        family_cap=args.family_cap,
        cross_family_cap=args.cross_family_cap,
        requested_parallel=args.requested_parallel,
    )
    print(json.dumps({"gate": manifest["gate"], "manifest": str((args.output_dir / 'manifest.json').resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
