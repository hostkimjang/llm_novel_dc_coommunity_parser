from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SAFE_LOSS_POST_IDS = ("11674712", "11660237", "11698880")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        if not isinstance(row, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_no}")
        rows.append(row)
    return rows


def load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    payload = load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "rows", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Unsupported row payload: {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def post_id_key(value: Any) -> str:
    return str(value or "").strip()


def unwrap_result_row(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("result")
    if isinstance(nested, dict):
        return nested
    return row


def row_identity(row: dict[str, Any]) -> dict[str, Any]:
    row = unwrap_result_row(row)
    analysis = row.get("analysis_result")
    if isinstance(analysis, dict) and isinstance(analysis.get("identity"), dict):
        return analysis["identity"]
    identity = row.get("identity")
    return identity if isinstance(identity, dict) else {}


def row_outcome(row: dict[str, Any]) -> dict[str, Any]:
    row = unwrap_result_row(row)
    identity = row_identity(row)
    novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
    ledger = identity.get("candidate_ledger") if isinstance(identity.get("candidate_ledger"), dict) else {}
    title = (
        novel.get("official_title")
        or identity.get("official_title")
        or identity.get("official_novel_title")
        or identity.get("blocked_official_title")
        or ledger.get("blocked_official_title")
        or ""
    )
    url = (
        novel.get("heretic_url")
        or identity.get("heretic_url")
        or identity.get("official_url")
        or identity.get("blocked_official_title_url")
        or ledger.get("blocked_official_title_url")
        or ""
    )
    status = identity.get("candidate_ledger_status") or row.get("candidate_ledger_status") or ""
    return {
        "status": str(status or "").strip(),
        "title": str(title or "").strip(),
        "url": str(url or "").strip(),
    }


def build_probe_input(
    *,
    source_rows: list[dict[str, Any]],
    post_ids: list[str],
    repeats: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        pid = post_id_key(row.get("post_id"))
        if pid and pid not in by_id:
            by_id[pid] = row
    missing = [pid for pid in post_ids if pid not in by_id]
    probe_rows: list[dict[str, Any]] = []
    for _attempt in range(repeats):
        for pid in post_ids:
            if pid in by_id:
                probe_rows.append(dict(by_id[pid]))
    return probe_rows, missing


def write_probe_input(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_independent_run_plan(
    *,
    source_rows: list[dict[str, Any]],
    post_ids: list[str],
    repeats: int,
    work_dir: Path,
    run_prefix: str,
    python_executable: str,
    expert_main: Path,
    parallel: int = 1,
    expert_args: list[str] | None = None,
    minimum_repeats: int = 5,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        pid = post_id_key(row.get("post_id"))
        if pid and pid not in by_id:
            by_id[pid] = row

    missing = [pid for pid in post_ids if pid not in by_id]
    safe_prefix = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in run_prefix).strip("_")
    if not safe_prefix:
        safe_prefix = "safe_loss_flip_probe"
    expert_args = list(expert_args or [])
    input_dir = work_dir / "inputs"
    result_dir = work_dir / "results"
    planned_runs: list[dict[str, Any]] = []
    input_writes: list[tuple[Path, dict[str, Any]]] = []

    for attempt in range(1, max(1, repeats) + 1):
        for pid in post_ids:
            row = by_id.get(pid)
            if row is None:
                continue
            stem = f"{safe_prefix}_{pid}_r{attempt:02d}"
            input_path = input_dir / f"{stem}.jsonl"
            output_path = result_dir / f"{stem}_result.json"
            argv = [
                python_executable,
                str(expert_main),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--parallel",
                str(max(1, parallel)),
                *expert_args,
            ]
            planned_runs.append(
                {
                    "post_id": pid,
                    "repeat_index": attempt,
                    "input_jsonl": str(input_path),
                    "output_json": str(output_path),
                    "checkpoint_jsonl": str(output_path.with_name(output_path.stem + "_checkpoint.jsonl")),
                    "manifest_json": str(output_path.with_name(output_path.stem + "_manifest.json")),
                    "command_argv": argv,
                    "command_line": subprocess.list2cmdline(argv),
                }
            )
            input_writes.append((input_path, dict(row)))

    repeat_counts = Counter(str(run["post_id"]) for run in planned_runs)
    result_paths = [str(run["output_json"]) for run in planned_runs]
    analyze_argv = [
        python_executable,
        str(Path(__file__)),
        "analyze",
    ]
    for path in result_paths:
        analyze_argv.extend(["--result", path])
    analyze_argv.extend(["--post-ids", ",".join(post_ids), "--repeats", str(max(1, repeats))])

    manifest = {
        "manifest_type": "safe_loss_flip_rate_probe_independent_run_plan",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_input": "",
        "work_dir": str(work_dir),
        "run_prefix": safe_prefix,
        "post_ids": post_ids,
        "repeats": max(1, repeats),
        "minimum_repeats": max(1, minimum_repeats),
        "minimum_repeats_contract_met": max(1, repeats) >= max(1, minimum_repeats),
        "expected_run_count": len(post_ids) * max(1, repeats),
        "planned_run_count": len(planned_runs),
        "missing_post_ids": missing,
        "repeat_count_by_post": {pid: repeat_counts.get(pid, 0) for pid in post_ids},
        "dedupe_guard": "one_post_per_process",
        "input_surface_contract": "Each generated JSONL contains exactly one copied source row and no _flip_probe metadata.",
        "aggregation_contract": "Analyze all per-repeat result JSON files together with the same post_ids and repeats value.",
        "planned_runs": planned_runs,
        "analyze_command_argv": analyze_argv,
        "analyze_command_line": subprocess.list2cmdline(analyze_argv),
    }
    return manifest, input_writes


def load_blind_judge(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = load_json(path)
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("rows") or payload.get("items") or payload.get("judgments") or []
    else:
        rows = []
    out: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        pid = post_id_key(item.get("post_id"))
        if pid:
            out[pid] = item
    return out


def _matches_expected(outcome: dict[str, Any], judge: dict[str, Any]) -> bool | None:
    expected_status = str(
        judge.get("expected_status")
        or judge.get("candidate_ledger_status")
        or judge.get("blind_judge_status")
        or ""
    ).strip()
    expected_title = str(
        judge.get("expected_title")
        or judge.get("official_title")
        or judge.get("blind_judge_title")
        or ""
    ).strip()
    expected_url = str(judge.get("expected_url") or judge.get("official_url") or "").strip()
    checks: list[bool] = []
    if expected_status:
        checks.append(outcome["status"] == expected_status)
    if expected_title:
        checks.append(outcome["title"] == expected_title)
    if expected_url:
        checks.append(outcome["url"] == expected_url)
    if not checks:
        return None
    return all(checks)


def analyze_flip_rate(
    *,
    result_rows: list[dict[str, Any]],
    post_ids: list[str],
    repeats: int,
    blind_judge: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blind_judge = blind_judge or {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result_rows:
        pid = post_id_key(unwrap_result_row(row).get("post_id"))
        if pid in post_ids:
            grouped[pid].append(row_outcome(row))

    rows: list[dict[str, Any]] = []
    any_flip = False
    all_repeats_present = True
    all_stable_expected = True
    for pid in post_ids:
        outcomes = grouped.get(pid, [])
        if len(outcomes) != repeats:
            all_repeats_present = False
        outcome_keys = [
            json.dumps(outcome, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for outcome in outcomes
        ]
        counts = Counter(outcome_keys)
        unique_outcomes = [json.loads(key) for key in sorted(counts)]
        majority_count = max(counts.values()) if counts else 0
        flip_count = max(0, len(outcomes) - majority_count)
        flip_rate = (flip_count / len(outcomes)) if outcomes else None
        flipped = len(counts) > 1
        any_flip = any_flip or flipped
        stable_outcome = unique_outcomes[0] if len(unique_outcomes) == 1 else None
        judge = blind_judge.get(pid) or {}
        expected_match = _matches_expected(stable_outcome, judge) if stable_outcome else None
        if expected_match is not True:
            all_stable_expected = False
        if flipped:
            classification = "nondeterminism_unresolved"
        elif expected_match is True:
            classification = "stable_blind_judge_confirmed"
        elif judge:
            classification = "stable_blind_judge_mismatch_or_incomplete"
        else:
            classification = "stable_blind_judge_required"
        rows.append(
            {
                "post_id": pid,
                "expected_repeats": repeats,
                "observed_repeats": len(outcomes),
                "unique_outcome_count": len(counts),
                "flip_count": flip_count,
                "flip_rate": flip_rate,
                "flipped": flipped,
                "classification": classification,
                "stable_outcome": stable_outcome,
                "unique_outcomes": unique_outcomes,
                "outcome_counts": {key: counts[key] for key in sorted(counts)},
                "blind_judge_present": bool(judge),
                "blind_judge_expected_match": expected_match,
            }
        )

    gate = "GO" if all_repeats_present and not any_flip and all_stable_expected else "REVIEW"
    if any_flip:
        gate = "NO-GO"
    return {
        "report_type": "safe_loss_flip_rate_probe",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "post_ids": post_ids,
        "repeats": repeats,
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "hard_hold_relaxation_allowed": gate == "GO",
        "summary": {
            "all_repeats_present": all_repeats_present,
            "any_flip": any_flip,
            "all_stable_expected_by_blind_judge": all_stable_expected,
            "flipped_post_ids": [row["post_id"] for row in rows if row["flipped"]],
            "blind_judge_missing_post_ids": [
                row["post_id"] for row in rows if not row["blind_judge_present"]
            ],
        },
        "rows": rows,
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Safe-loss flip-rate probe 보고",
        "",
        f"- gate: `{report['gate']}`",
        f"- repeats: `{report['repeats']}`",
        f"- post_ids: `{report['post_ids']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- hard_hold_relaxation_allowed: `{report['hard_hold_relaxation_allowed']}`",
        "",
        "## 요약",
        "",
        f"- all_repeats_present: `{report['summary']['all_repeats_present']}`",
        f"- any_flip: `{report['summary']['any_flip']}`",
        f"- all_stable_expected_by_blind_judge: `{report['summary']['all_stable_expected_by_blind_judge']}`",
        f"- flipped_post_ids: `{report['summary']['flipped_post_ids']}`",
        f"- blind_judge_missing_post_ids: `{report['summary']['blind_judge_missing_post_ids']}`",
        "",
        "## 행별 결과",
        "",
    ]
    for row in report["rows"]:
        lines.extend(
            [
                f"### {row['post_id']}",
                "",
                f"- observed_repeats: `{row['observed_repeats']}` / `{row['expected_repeats']}`",
                f"- unique_outcome_count: `{row['unique_outcome_count']}`",
                f"- flip_rate: `{row['flip_rate']}`",
                f"- classification: `{row['classification']}`",
                f"- blind_judge_expected_match: `{row['blind_judge_expected_match']}`",
                f"- stable_outcome: `{row['stable_outcome']}`",
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_post_ids(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_SAFE_LOSS_POST_IDS)
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or analyze repeated safe-loss flip-rate probes.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build-input")
    build.add_argument("--source-input", required=True, type=Path)
    build.add_argument("--post-ids", default=",".join(DEFAULT_SAFE_LOSS_POST_IDS))
    build.add_argument("--repeats", type=int, default=5)
    build.add_argument("--output-jsonl", required=True, type=Path)
    build.add_argument("--manifest", required=True, type=Path)

    plan = sub.add_parser("build-run-plan")
    plan.add_argument("--source-input", required=True, type=Path)
    plan.add_argument("--post-ids", default=",".join(DEFAULT_SAFE_LOSS_POST_IDS))
    plan.add_argument("--repeats", type=int, default=5)
    plan.add_argument("--minimum-repeats", type=int, default=5)
    plan.add_argument("--work-dir", required=True, type=Path)
    plan.add_argument("--run-prefix", required=True)
    plan.add_argument("--manifest", required=True, type=Path)
    plan.add_argument("--python", default=sys.executable)
    plan.add_argument("--expert-main", default=Path("expert_main.py"), type=Path)
    plan.add_argument("--parallel", type=int, default=1)
    plan.add_argument(
        "--expert-arg",
        action="append",
        default=[],
        help="Additional argument passed through to each expert_main invocation. Repeat for multiple args.",
    )

    analyze = sub.add_parser("analyze")
    analyze.add_argument("--result", required=True, type=Path, action="append")
    analyze.add_argument("--post-ids", default=",".join(DEFAULT_SAFE_LOSS_POST_IDS))
    analyze.add_argument("--repeats", type=int, default=5)
    analyze.add_argument("--blind-judge", type=Path, default=None)
    analyze.add_argument("--output-json", required=True, type=Path)
    analyze.add_argument("--output-md", required=True, type=Path)
    analyze.add_argument("--fail-on-flip", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    post_ids = parse_post_ids(getattr(args, "post_ids", None))
    if args.command == "build-input":
        rows, missing = build_probe_input(
            source_rows=load_jsonl(args.source_input),
            post_ids=post_ids,
            repeats=max(1, int(args.repeats)),
        )
        write_probe_input(rows, args.output_jsonl)
        manifest = {
            "manifest_type": "safe_loss_flip_rate_probe_input",
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "source_input": str(args.source_input),
            "output_jsonl": str(args.output_jsonl),
            "post_ids": post_ids,
            "repeats": max(1, int(args.repeats)),
            "row_count": len(rows),
            "missing_post_ids": missing,
            "identical_input_note": "Rows are duplicated without probe metadata so the model receives the same input surface each time.",
        }
        write_json(args.manifest, manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 1 if missing else 0

    if args.command == "build-run-plan":
        manifest, input_writes = build_independent_run_plan(
            source_rows=load_jsonl(args.source_input),
            post_ids=post_ids,
            repeats=max(1, int(args.repeats)),
            work_dir=args.work_dir,
            run_prefix=args.run_prefix,
            python_executable=str(args.python),
            expert_main=args.expert_main,
            parallel=max(1, int(args.parallel)),
            expert_args=list(args.expert_arg or []),
            minimum_repeats=max(1, int(args.minimum_repeats)),
        )
        manifest["source_input"] = str(args.source_input)
        for input_path, row in input_writes:
            write_probe_input([row], input_path)
        write_json(args.manifest, manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        if manifest["missing_post_ids"]:
            return 1
        if not manifest["minimum_repeats_contract_met"]:
            return 2
        return 0

    report = analyze_flip_rate(
        result_rows=[
            row
            for result_path in args.result
            for row in load_rows(result_path)
        ],
        post_ids=post_ids,
        repeats=max(1, int(args.repeats)),
        blind_judge=load_blind_judge(args.blind_judge),
    )
    report["result_paths"] = [str(path) for path in args.result]
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_flip and report["summary"]["any_flip"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
