from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def count_result_rows(path: Path) -> int | None:
    try:
        payload = load_json(path)
    except FileNotFoundError:
        return None
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("results", "rows", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def manifest_path_for_result(result_path: Path) -> Path:
    return result_path.with_name(f"{result_path.stem}_manifest.json")


def _get_int(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    if isinstance(value, bool):
        return None
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _manifest_counts(manifest: dict[str, Any] | None, result_rows: int | None) -> dict[str, Any]:
    manifest = manifest if isinstance(manifest, dict) else {}
    counts = {
        "run_id": manifest.get("run_id"),
        "input_post_count": _get_int(manifest, "input_post_count"),
        "completed_count": _get_int(manifest, "completed_count"),
        "flushed_count": _get_int(manifest, "flushed_count"),
        "pending_count": _get_int(manifest, "pending_count"),
        "failed_count": _get_int(manifest, "failed_count"),
        "requested_parallel": _get_int(manifest, "requested_parallel"),
        "effective_parallel": _get_int(manifest, "effective_parallel"),
        "next_save_idx": _get_int(manifest, "next_save_idx"),
        "result_rows": result_rows,
    }
    partial_signals: list[str] = []
    input_count = counts["input_post_count"]
    completed = counts["completed_count"]
    flushed = counts["flushed_count"]
    pending = counts["pending_count"]
    failed = counts["failed_count"]
    if input_count is None:
        partial_signals.append("input_post_count_missing")
    if completed is None:
        partial_signals.append("completed_count_missing")
    if input_count is not None and completed is not None and completed < input_count:
        partial_signals.append("completed_count_lt_input_post_count")
    if pending and pending > 0:
        partial_signals.append("pending_count_gt_zero")
    if failed and failed > 0:
        partial_signals.append("failed_count_gt_zero")
    if flushed is not None and completed is not None and flushed < completed:
        partial_signals.append("flushed_count_lt_completed_count")
    if result_rows is not None and completed is not None and result_rows < completed:
        partial_signals.append("result_rows_lt_completed_count")
    clean_by_counts = bool(
        input_count is not None
        and completed == input_count
        and flushed == completed
        and (pending or 0) == 0
        and (failed or 0) == 0
        and (result_rows is None or result_rows >= completed)
    )
    counts["clean_by_counts"] = clean_by_counts
    counts["partial_signals"] = partial_signals
    return counts


def _preflight_summary(preflight: dict[str, Any] | None) -> dict[str, Any]:
    preflight = preflight if isinstance(preflight, dict) else {}
    policy = preflight.get("source_review_policy") or preflight.get("source_policy") or {}
    policy_counts = policy.get("counts") if isinstance(policy, dict) else {}
    manifest_state = preflight.get("manifest_completion_state") or {}
    random_baseline = preflight.get("random_baseline") or {}
    gate = preflight.get("gate") or {}
    return {
        "path_present": bool(preflight),
        "source_result_path": preflight.get("source_result_path"),
        "source_dataset_kind": policy.get("source_dataset_kind") if isinstance(policy, dict) else None,
        "source_integrity_classification": (
            policy.get("source_integrity_classification") if isinstance(policy, dict) else None
        ),
        "large_run_complete": policy.get("large_run_complete") if isinstance(policy, dict) else None,
        "approval_policy": policy.get("approval_policy") if isinstance(policy, dict) else None,
        "policy_counts": policy_counts if isinstance(policy_counts, dict) else {},
        "manifest_completion_state": manifest_state if isinstance(manifest_state, dict) else {},
        "random_baseline": random_baseline if isinstance(random_baseline, dict) else {},
        "gate": gate if isinstance(gate, dict) else {},
    }


def _runtime_audit_summary(audit: dict[str, Any] | None) -> dict[str, Any]:
    audit = audit if isinstance(audit, dict) else {}
    observed = audit.get("observed") or {}
    gate = audit.get("gate") or {}
    return {
        "path_present": bool(audit),
        "run_id": observed.get("run_id"),
        "requested_parallel": observed.get("requested_parallel"),
        "effective_parallel": observed.get("effective_parallel"),
        "input_post_count": observed.get("input_post_count"),
        "completed_count": observed.get("completed_count"),
        "flushed_count": observed.get("flushed_count"),
        "pending_count": observed.get("pending_count"),
        "failed_count": observed.get("failed_count"),
        "image_post_count": observed.get("image_post_count"),
        "vlm_enabled": observed.get("vlm_enabled"),
        "ocr_enabled": observed.get("ocr_enabled"),
        "vlm_ocr_semantic_review_ready": observed.get("vlm_ocr_semantic_review_ready"),
        "auto_discovered_logs": audit.get("auto_discovered_logs"),
        "log_evidence_present": audit.get("log_evidence_present"),
        "runtime_contract": gate.get("runtime_contract"),
        "semantic_approval": gate.get("semantic_approval"),
        "issues": audit.get("issues") if isinstance(audit.get("issues"), list) else [],
    }


def _hygiene_summary(scan: dict[str, Any] | None) -> dict[str, Any]:
    scan = scan if isinstance(scan, dict) else {}
    hit_files = scan.get("hit_files")
    try:
        hit_files_int = int(hit_files)
    except (TypeError, ValueError):
        hit_files_int = None
    return {
        "path_present": bool(scan),
        "scan_type": scan.get("scan_type"),
        "files_scanned": scan.get("files_scanned"),
        "hit_files": hit_files,
        "clean_files": scan.get("clean_files"),
        "hit_type_counts": scan.get("hit_type_counts") if isinstance(scan.get("hit_type_counts"), dict) else {},
        "gate": "GO" if hit_files_int == 0 else ("NO-GO" if hit_files_int and hit_files_int > 0 else "MISSING"),
    }


def build_state_map(
    result_path: Path,
    *,
    preflight_path: Path | None = None,
    runtime_audit_path: Path | None = None,
    hygiene_scan_path: Path | None = None,
) -> dict[str, Any]:
    result_path = result_path.resolve()
    manifest_path = manifest_path_for_result(result_path)
    result_rows = count_result_rows(result_path)
    manifest = load_json(manifest_path) if manifest_path.exists() else None
    preflight = load_json(preflight_path) if preflight_path else None
    runtime_audit = load_json(runtime_audit_path) if runtime_audit_path else None
    hygiene_scan = load_json(hygiene_scan_path) if hygiene_scan_path else None

    manifest_counts = _manifest_counts(manifest, result_rows)
    preflight_summary = _preflight_summary(preflight)
    runtime_summary = _runtime_audit_summary(runtime_audit)
    hygiene_summary = _hygiene_summary(hygiene_scan)

    blockers: list[dict[str, Any]] = []
    if manifest_counts["partial_signals"]:
        blockers.append(
            {
                "code": "original_manifest_partial",
                "severity": "NO-GO",
                "evidence": manifest_counts["partial_signals"],
                "action": "completed VLM/OCR-on source를 확보한 뒤 preflight를 다시 실행한다.",
            }
        )
    random_baseline = preflight_summary["random_baseline"]
    if random_baseline and random_baseline.get("feasible") is False:
        blockers.append(
            {
                "code": "random_baseline_infeasible",
                "severity": "REVIEW-LOCKED",
                "evidence": {
                    "requested_sample_size": random_baseline.get("requested_sample_size"),
                    "available_rows": random_baseline.get("available_rows"),
                    "shortfall": random_baseline.get("shortfall"),
                },
                "action": "random baseline 1000건 이상을 뽑을 수 있는 completed source에서 다시 sampling한다.",
            }
        )
    if not runtime_summary["path_present"]:
        blockers.append(
            {
                "code": "latest_runtime_audit_missing",
                "severity": "REVIEW",
                "evidence": "small canary runtime contract audit artifact missing",
                "action": "소규모 rerun 후 audit_goal_test_run_contract.py 산출물을 붙인다.",
            }
        )
    if hygiene_summary["gate"] == "NO-GO":
        blockers.append(
            {
                "code": "latest_reason_hygiene_hits",
                "severity": "NO-GO",
                "evidence": hygiene_summary["hit_type_counts"],
                "action": "public reason drift를 먼저 수정하고 latest canary scan을 다시 실행한다.",
            }
        )
    if not hygiene_summary["path_present"]:
        blockers.append(
            {
                "code": "latest_reason_hygiene_scan_missing",
                "severity": "REVIEW",
                "evidence": "reason hygiene scan artifact missing",
                "action": "latest clean canary set에 scan_reason_hygiene.py를 실행한다.",
            }
        )

    original_source_approval = "NO-GO" if manifest_counts["partial_signals"] else "REVIEW"
    gates = {
        "original_source_approval": original_source_approval,
        "small_run_runtime_contract": runtime_summary["runtime_contract"] or "MISSING",
        "latest_reason_hygiene": hygiene_summary["gate"],
        "semantic_approval": "REVIEW-LOCKED",
    }

    return {
        "map_type": "goal_current_state_map",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "goal_result_path": str(result_path),
        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
        "preflight_path": str(preflight_path.resolve()) if preflight_path else None,
        "runtime_audit_path": str(runtime_audit_path.resolve()) if runtime_audit_path else None,
        "hygiene_scan_path": str(hygiene_scan_path.resolve()) if hygiene_scan_path else None,
        "original_run": manifest_counts,
        "source_review_policy": preflight_summary,
        "small_run_runtime_audit": runtime_summary,
        "reason_hygiene_scan": hygiene_summary,
        "gates": gates,
        "critical_blockers": blockers,
        "next_actions": [
            "원본 partial source는 approval source가 아니라 regression seed로만 유지한다.",
            "completed VLM/OCR-on source를 확보한 뒤 fail-on-locked preflight를 다시 실행한다.",
            "completed source에서 random baseline 1000건 이상과 P0/P1 high-risk expansion을 분리 실행한다.",
            "소규모 targeted rerun은 --parallel 36을 max로 쓰되 effective_parallel 축소와 no lifecycle을 post-run audit로 확인한다.",
            "VLM/OCR 이미지 케이스는 in-app browser 또는 동등한 시각 증거로 직접 로딩/스크린샷 상태를 확인한다.",
        ],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    original = report["original_run"]
    source_policy = report["source_review_policy"]
    runtime = report["small_run_runtime_audit"]
    hygiene = report["reason_hygiene_scan"]
    gates = report["gates"]
    blockers = report["critical_blockers"]

    lines = [
        "# Goal 현재 상태 맵",
        "",
        "## 요약 판정",
        "",
        f"- 원본 source approval: `{gates['original_source_approval']}`",
        f"- 최근 소규모 runtime contract: `{gates['small_run_runtime_contract']}`",
        f"- 최신 reason hygiene: `{gates['latest_reason_hygiene']}`",
        f"- 10만 semantic approval: `{gates['semantic_approval']}`",
        "- 결론: runtime/canary 통과와 10만 자연어 품질 승인은 분리한다.",
        "",
        "## 원본 10만 run source",
        "",
        f"- run_id: `{original.get('run_id')}`",
        (
            f"- counts: input/completed/flushed/pending/failed/result_rows = "
            f"`{original.get('input_post_count')}/{original.get('completed_count')}/"
            f"{original.get('flushed_count')}/{original.get('pending_count')}/"
            f"{original.get('failed_count')}/{original.get('result_rows')}`"
        ),
        f"- partial signals: `{', '.join(original.get('partial_signals') or []) or 'none'}`",
        f"- source policy: `{source_policy.get('source_dataset_kind')}` / `{source_policy.get('source_integrity_classification')}`",
        f"- large_run_complete: `{source_policy.get('large_run_complete')}`",
        f"- preflight gate: `{(source_policy.get('gate') or {}).get('overall')}`",
        "",
        "## Random baseline 가능성",
        "",
    ]
    rb = source_policy.get("random_baseline") or {}
    lines.extend(
        [
            f"- requested_sample_size: `{rb.get('requested_sample_size')}`",
            f"- available_rows: `{rb.get('available_rows')}`",
            f"- shortfall: `{rb.get('shortfall')}`",
            f"- feasible: `{rb.get('feasible')}`",
            "",
            "## 최근 소규모 runtime audit",
            "",
            f"- run_id: `{runtime.get('run_id')}`",
            f"- requested/effective parallel: `{runtime.get('requested_parallel')}/{runtime.get('effective_parallel')}`",
            (
                f"- counts: input/completed/flushed/pending/failed = "
                f"`{runtime.get('input_post_count')}/{runtime.get('completed_count')}/"
                f"{runtime.get('flushed_count')}/{runtime.get('pending_count')}/{runtime.get('failed_count')}`"
            ),
            f"- log_evidence_present: `{runtime.get('log_evidence_present')}`",
            f"- VLM/OCR ready: `{runtime.get('vlm_ocr_semantic_review_ready')}`",
            f"- semantic approval by runtime audit: `{runtime.get('semantic_approval')}`",
            "",
            "## Reason hygiene",
            "",
            f"- files_scanned: `{hygiene.get('files_scanned')}`",
            f"- hit_files: `{hygiene.get('hit_files')}`",
            f"- clean_files: `{hygiene.get('clean_files')}`",
            f"- hit_type_counts: `{json.dumps(hygiene.get('hit_type_counts') or {}, ensure_ascii=False)}`",
            "",
            "## Blockers",
            "",
        ]
    )
    if blockers:
        for item in blockers:
            lines.append(f"- `{item['severity']}` `{item['code']}`: {item['action']}")
    else:
        lines.append("- 현재 상태맵 기준 blocker 없음. 단, semantic approval은 별도 expanded review가 필요하다.")
    lines.extend(["", "## Next actions", ""])
    lines.extend(f"- {item}" for item in report["next_actions"])
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Korean current-state map for the active scan-review goal.")
    parser.add_argument("--result", required=True, type=Path, help="Original or target result JSON.")
    parser.add_argument("--preflight", type=Path, default=None, help="Large-scale qualitative preflight JSON.")
    parser.add_argument("--runtime-audit", type=Path, default=None, help="Small goal/test runtime audit JSON.")
    parser.add_argument("--hygiene-scan", type=Path, default=None, help="Reason hygiene raw scan JSON.")
    parser.add_argument("--output-json", type=Path, default=None, help="Write state map JSON.")
    parser.add_argument("--output-md", type=Path, default=None, help="Write Korean Markdown summary.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_state_map(
        args.result,
        preflight_path=args.preflight,
        runtime_audit_path=args.runtime_audit,
        hygiene_scan_path=args.hygiene_scan,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload + "\n", encoding="utf-8")
    if args.output_md:
        write_markdown(report, args.output_md)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
