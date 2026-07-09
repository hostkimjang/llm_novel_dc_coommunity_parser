from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "results", "items"):
            values = payload.get(key)
            if isinstance(values, list):
                return [row for row in values if isinstance(row, dict)]
    return []


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_group(value: str) -> tuple[str, Path, str]:
    parts = value.split("|", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "--accounting-group must be formatted as group_id|path|description"
        )
    group_id, path, description = parts
    return group_id.strip(), Path(path.strip()), description.strip()


def is_processed(row: dict[str, Any]) -> bool:
    return bool(row.get("contract_processed") or row.get("source_native_processed")) and not row.get(
        "ordinary_residual_unprocessed"
    )


def decision_kind(row: dict[str, Any]) -> str:
    state = str(row.get("contract_accounting_state") or "")
    effect = str(row.get("contract_accounting_effect") or "")
    if row.get("source_native_processed"):
        return "source_native_exclusion_candidate_not_approval"
    if "no_publish" in state or "hold" in state:
        return "no_publish_or_hold_not_approval"
    if "release_candidate" in effect:
        return "release_candidate_not_approval_full375_recheck_required"
    return "contract_processed_not_approval"


def build_ledger(*, groups: list[tuple[str, Path, str]], ledger_id: str, generated_at: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    validation_issues: list[dict[str, Any]] = []
    group_summaries: list[dict[str, Any]] = []

    for group_id, path, description in groups:
        payload = load_json(path)
        selected = [row for row in rows(payload) if is_processed(row)]
        group_summaries.append(
            {
                "group_id": group_id,
                "source_path": rel(path),
                "description_ko": description,
                "processed_rows": len(selected),
            }
        )
        for row in selected:
            post_id = str(row.get("post_id") or "").strip()
            if not post_id:
                validation_issues.append({"group_id": group_id, "issue": "missing_post_id"})
                continue
            if post_id in seen:
                validation_issues.append(
                    {"post_id": post_id, "first_group": seen[post_id], "duplicate_group": group_id}
                )
                continue
            seen[post_id] = group_id
            entries.append(
                {
                    "post_id": int(post_id) if post_id.isdigit() else post_id,
                    "adjudication_group": group_id,
                    "source_accounting": rel(path),
                    "decision_kind": decision_kind(row),
                    "triage_bucket": row.get("triage_bucket"),
                    "review_label": row.get("review_label"),
                    "source_native_verdict": row.get("source_native_verdict"),
                    "contract_action": row.get("contract_action"),
                    "contract_accounting_state": row.get("contract_accounting_state"),
                    "contract_accounting_effect": row.get("contract_accounting_effect"),
                    "selected_title": row.get("selected_title"),
                    "target_title": row.get("target_title"),
                    "current_projection_candidate_title": row.get("current_projection_candidate_title"),
                    "release_gate_state": row.get("release_gate_state"),
                    "policy_review_ref": row.get("policy_review_ref"),
                    "publish_allowed": bool(row.get("publish_allowed")),
                    "runtime_replay_allowed": bool(row.get("runtime_replay_allowed")),
                    "full_scan_approval": bool(row.get("full_scan_approval")),
                    "rationale_ko": row.get("rationale_ko"),
                    "evidence_refs": row.get("evidence_refs") or [],
                }
            )

    state_counts = collections.Counter(str(entry.get("contract_accounting_state") or "") for entry in entries)
    effect_counts = collections.Counter(str(entry.get("contract_accounting_effect") or "") for entry in entries)
    kind_counts = collections.Counter(str(entry.get("decision_kind") or "") for entry in entries)
    bucket_counts = collections.Counter(str(entry.get("triage_bucket") or "") for entry in entries)
    entries.sort(key=lambda entry: int(entry["post_id"]) if str(entry["post_id"]).isdigit() else str(entry["post_id"]))

    return {
        "report_type": "adjudicated_rebaseline_adjudication_ledger",
        "ledger_id": ledger_id,
        "generated_at": generated_at,
        "gate": "REVIEW-LOCKED" if not validation_issues else "NO-GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "summary": {
            "adjudicated_rows": len(entries),
            "duplicate_or_validation_issue_count": len(validation_issues),
            "group_counts": {item["group_id"]: item["processed_rows"] for item in group_summaries},
            "decision_kind_counts": dict(sorted(kind_counts.items())),
            "contract_accounting_state_counts": dict(sorted(state_counts.items())),
            "contract_accounting_effect_counts": dict(sorted(effect_counts.items())),
            "triage_bucket_counts": dict(sorted(bucket_counts.items())),
            "publish_allowed_rows": sum(1 for entry in entries if entry["publish_allowed"]),
            "runtime_replay_allowed_rows": sum(1 for entry in entries if entry["runtime_replay_allowed"]),
            "completion_gate": "adjusted full375 collateral GO + full_scan path",
            "raw_20260626_baseline_is_completion_gate": False,
        },
        "groups": group_summaries,
        "validation_issues": validation_issues,
        "rows": entries,
        "approval_boundary": {
            "adjudication_ledger_is_not_runtime_replay": True,
            "release_candidate_not_approval": True,
            "full_scan_approval": False,
            "adjusted_drift_after_rebaseline_is_completion_metric": True,
            "historical_raw_vs_20260626_is_reference_only": True,
        },
    }


def build_manifest(
    *,
    manifest_id: str,
    generated_at: str,
    ledger: dict[str, Any],
    ledger_path: Path,
    baseline_result: Path,
    projection_result: Path,
    adjusted_compare_path: Path,
    historical_compare_path: Path,
    always_on_path: Path,
    publication_path: Path,
    residual_dispatch_path: Path,
    source_run_id: str,
    projection_id: str,
) -> dict[str, Any]:
    baseline_rows = rows(load_json(baseline_result))
    adjusted_compare = load_json(adjusted_compare_path)
    historical_compare = load_json(historical_compare_path)
    always_on = load_json(always_on_path)
    publication = load_json(publication_path)
    residual = load_json(residual_dispatch_path)
    return {
        "report_type": "adjusted_baseline_manifest",
        "manifest_id": manifest_id,
        "generated_at": generated_at,
        "gate": "REVIEW-LOCKED",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "rebaseline_status": "APPLIED",
        "source_head_before_commit": git_head(),
        "source_run_id": source_run_id,
        "projection_id": projection_id,
        "baseline_mode": "adjudicated_rebaseline",
        "collateral_measure": "adjusted_drift",
        "completion_gate": "adjusted full375 collateral GO + full_scan path",
        "completion_gate_metric": "adjusted_drift_count",
        "raw_20260626_baseline_is_completion_gate": False,
        "raw_20260626_baseline_role": "diagnostic historical compare only",
        "summary": {
            "baseline_result_rows": len(baseline_rows),
            "adjudication_ledger_rows": ledger["summary"]["adjudicated_rows"],
            "ordinary_residual_rows_after_loop": residual.get("summary", {}).get("ordinary_residual_rows"),
            "publication_contract_convergence_gate": publication.get("gate"),
            "golden18_gate": always_on.get("golden", {}).get("gate"),
            "adjusted_drift_count": adjusted_compare.get("adjusted_drift_count"),
            "historical_raw_collateral_regression_count": historical_compare.get(
                "historical_raw_collateral_regression_count"
            ),
            "runtime_collateral_gate": adjusted_compare.get("runtime_collateral_gate"),
            "runtime_complete": adjusted_compare.get("runtime_complete"),
            "always_on_gate": always_on.get("gate"),
            "always_on_blockers": always_on.get("blockers"),
            "current_search_hard_blocker_gate": (
                "GO / 0 (carried from loop628 current-search closure; not rerun in loop638)"
            ),
        },
        "hashes": {
            "adjudicated_baseline_result_sha256": sha256_file(baseline_result),
            "projection_result_sha256": sha256_file(projection_result),
            "adjudication_ledger_sha256": sha256_file(ledger_path),
        },
        "artifacts": {
            "adjudicated_baseline_result": rel(baseline_result),
            "projection_result": rel(projection_result),
            "adjudication_ledger": rel(ledger_path),
            "adjusted_drift_compare": rel(adjusted_compare_path),
            "historical_raw_compare": rel(historical_compare_path),
            "always_on_gate": rel(always_on_path),
            "publication_contract_convergence": rel(publication_path),
            "residual0_dispatch": rel(residual_dispatch_path),
        },
        "approval_boundary": {
            "rebaseline_applied": True,
            "adjusted_drift_zero_is_static_collateral_go": True,
            "runtime_counts_missing_keeps_always_on_no_go": True,
            "full_scan_approval_requires_full_scan_path": True,
            "historical_raw_vs_20260626_is_reference_only": True,
        },
    }


def write_outputs(
    *,
    ledger: dict[str, Any],
    manifest: dict[str, Any],
    ledger_md: Path,
    manifest_md: Path,
    readiness_json: Path,
    readiness_md: Path,
    generated_at: str,
) -> dict[str, Any]:
    readiness = {
        "report_type": "adjudicated_rebaseline_readiness",
        "readiness_id": readiness_json.stem,
        "generated_at": generated_at,
        "gate": "READY_FOR_RUNTIME_FULL375_REPLAY",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "rebaseline_status": "APPLIED",
        "completion_gate": "adjusted full375 collateral GO + full_scan path",
        "completion_gate_metric": "adjusted_drift_count",
        "raw_20260626_baseline_is_completion_gate": False,
        "summary": manifest["summary"],
        "blockers": ["collateral_runtime_counts_missing", "full_scan_path_not_completed"],
        "inputs": manifest["artifacts"],
        "next_required_action": (
            "새 adjudicated baseline 기준으로 full375/runtime replay 또는 full_scan 경로를 열 때 "
            "--parallel 16과 웹 대시보드를 사용한다."
        ),
    }
    write_json(readiness_json, readiness)

    write_markdown(
        ledger_md,
        [
            "# Loop638 adjudication ledger",
            "",
            "Loop632 이후 residual chain에서 판결된 행을 새 adjudicated baseline의 판결 ledger로 고정한다. 이 ledger는 runtime replay나 full_scan approval이 아니다.",
            "",
            "## 요약",
            "",
            f"- gate: `{ledger['gate']}`",
            f"- adjudicated_rows: `{ledger['summary']['adjudicated_rows']}`",
            f"- duplicate_or_validation_issue_count: `{ledger['summary']['duplicate_or_validation_issue_count']}`",
            f"- decision_kind_counts: `{ledger['summary']['decision_kind_counts']}`",
            f"- triage_bucket_counts: `{ledger['summary']['triage_bucket_counts']}`",
            f"- publish_allowed_rows: `{ledger['summary']['publish_allowed_rows']}`",
            f"- runtime_replay_allowed_rows: `{ledger['summary']['runtime_replay_allowed_rows']}`",
            "- completion gate: `adjusted full375 collateral GO + full_scan path`",
            "- raw 2026-06-26 baseline: `diagnostic only`",
            "",
            "## 묶음",
            "",
            *[
                f"- `{group['group_id']}`: `{group['processed_rows']}`건 - {group['description_ko']}"
                for group in ledger["groups"]
            ],
        ],
    )
    write_markdown(
        manifest_md,
        [
            "# Loop638 adjudicated re-baseline manifest",
            "",
            "Loop638은 판결된 375행 projection을 새 adjudicated baseline으로 재동결했다. 이후 collateral은 2026-06-26 raw 변화가 아니라 이 baseline 대비 `adjusted_drift_count`로 본다.",
            "",
            "## 요약",
            "",
            f"- rebaseline_status: `{manifest['rebaseline_status']}`",
            f"- baseline rows: `{manifest['summary']['baseline_result_rows']}`",
            f"- adjudication ledger rows: `{manifest['summary']['adjudication_ledger_rows']}`",
            f"- ordinary residual after loop: `{manifest['summary']['ordinary_residual_rows_after_loop']}`",
            f"- publication contract: `{manifest['summary']['publication_contract_convergence_gate']}`",
            f"- adjusted_drift_count: `{manifest['summary']['adjusted_drift_count']}`",
            f"- historical raw collateral regression: `{manifest['summary']['historical_raw_collateral_regression_count']}` (참고값)",
            f"- always-on gate: `{manifest['summary']['always_on_gate']}` / blockers `{manifest['summary']['always_on_blockers']}`",
            f"- completion gate metric: `{manifest['completion_gate_metric']}`",
            "- full_scan_approval: `false`",
            "",
            "## 해시",
            "",
            f"- adjudicated_baseline_result_sha256: `{manifest['hashes']['adjudicated_baseline_result_sha256']}`",
            f"- projection_result_sha256: `{manifest['hashes']['projection_result_sha256']}`",
            f"- adjudication_ledger_sha256: `{manifest['hashes']['adjudication_ledger_sha256']}`",
            "",
            "## Gate 해석",
            "",
            "정적 adjusted drift는 `0`이지만 runtime counts가 없으므로 always-on은 아직 `NO-GO`다. 완료 기준은 raw가 아니라 adjusted 기준이며, full_scan 경로가 끝나기 전까지 `semantic_quality=REVIEW-LOCKED`, `full_scan_approval=false`를 유지한다.",
        ],
    )
    write_markdown(
        readiness_md,
        [
            "# Loop638 판결 baseline 재동결 준비도",
            "",
            "Residual queue는 `0`이고 adjudicated re-baseline은 적용됐다. 남은 blocker는 runtime full375 counts와 full_scan 경로다.",
            "",
            "## 요약",
            "",
            f"- gate: `{readiness['gate']}`",
            f"- rebaseline_status: `{readiness['rebaseline_status']}`",
            f"- adjusted_drift_count: `{readiness['summary']['adjusted_drift_count']}`",
            f"- historical raw collateral regression: `{readiness['summary']['historical_raw_collateral_regression_count']}` (완료 기준 아님)",
            f"- ordinary residual after loop: `{readiness['summary']['ordinary_residual_rows_after_loop']}`",
            f"- publication contract: `{readiness['summary']['publication_contract_convergence_gate']}`",
            f"- blockers: `{readiness['blockers']}`",
            "- semantic_quality: `REVIEW-LOCKED`",
            "- full_scan_approval: `false`",
            "",
            "## 다음 조치",
            "",
            "다음 full375/runtime 또는 full_scan 실행은 `--parallel 16`과 웹 대시보드를 붙여 진행한다. raw 105건은 6/26 baseline 대비 역사적 이동량이며 매 run의 완료 blocker가 아니다.",
        ],
    )
    return readiness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build adjudicated re-baseline ledger and manifest.")
    parser.add_argument("--accounting-group", action="append", type=parse_group, required=True)
    parser.add_argument("--ledger-id", required=True)
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--baseline-result", required=True, type=Path)
    parser.add_argument("--projection-result", required=True, type=Path)
    parser.add_argument("--adjusted-compare", required=True, type=Path)
    parser.add_argument("--historical-compare", required=True, type=Path)
    parser.add_argument("--always-on", required=True, type=Path)
    parser.add_argument("--publication-convergence", required=True, type=Path)
    parser.add_argument("--residual-dispatch", required=True, type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--projection-id", required=True)
    parser.add_argument("--output-ledger-json", required=True, type=Path)
    parser.add_argument("--output-ledger-md", required=True, type=Path)
    parser.add_argument("--output-manifest-json", required=True, type=Path)
    parser.add_argument("--output-manifest-md", required=True, type=Path)
    parser.add_argument("--output-readiness-json", required=True, type=Path)
    parser.add_argument("--output-readiness-md", required=True, type=Path)
    parser.add_argument("--fail-on-validation-issue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    ledger = build_ledger(groups=args.accounting_group, ledger_id=args.ledger_id, generated_at=generated_at)
    write_json(args.output_ledger_json, ledger)
    manifest = build_manifest(
        manifest_id=args.manifest_id,
        generated_at=generated_at,
        ledger=ledger,
        ledger_path=args.output_ledger_json,
        baseline_result=args.baseline_result,
        projection_result=args.projection_result,
        adjusted_compare_path=args.adjusted_compare,
        historical_compare_path=args.historical_compare,
        always_on_path=args.always_on,
        publication_path=args.publication_convergence,
        residual_dispatch_path=args.residual_dispatch,
        source_run_id=args.source_run_id,
        projection_id=args.projection_id,
    )
    write_json(args.output_manifest_json, manifest)
    readiness = write_outputs(
        ledger=ledger,
        manifest=manifest,
        ledger_md=args.output_ledger_md,
        manifest_md=args.output_manifest_md,
        readiness_json=args.output_readiness_json,
        readiness_md=args.output_readiness_md,
        generated_at=generated_at,
    )
    print(
        json.dumps(
            {
                "ledger_gate": ledger["gate"],
                "ledger_rows": ledger["summary"]["adjudicated_rows"],
                "rebaseline_status": manifest["rebaseline_status"],
                "adjusted_drift_count": manifest["summary"]["adjusted_drift_count"],
                "readiness_gate": readiness["gate"],
                "blockers": readiness["blockers"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.fail_on_validation_issue and ledger["validation_issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
