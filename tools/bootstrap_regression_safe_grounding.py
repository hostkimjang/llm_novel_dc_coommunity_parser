"""Bootstrap regression-safe grounding loop artifacts.

This tool freezes the measurement inputs required before work-bridge code
changes: baseline copy, regression panel, golden canary set, and collateral
comparison scaffolding.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_judge_seed_registry import clean_canary_row, seed_group
from tools.compare_completed779_improvement import (
    analysis_identity,
    load_json_or_jsonl,
    row_by_post_id,
    titles_match,
)


DEFAULT_CONTROLS = {
    11694064: "sentinel_bad_title_must_not_return",
    11698880: "seed_conflict_reason_hold_control",
    11702055: "source_url_hygiene_control",
    11703669: "same_title_official_url_control",
    11706871: "decoder_runtime_regression_control",
    11710037: "trope_boundary_candidate_hold_control",
    11710045: "image_ocr_hold_control",
    11718077: "source_canonical_distinction_control",
    11718105: "multi_title_ocr_candidate_preservation_control",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_phase2_queue(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
        raise ValueError(f"unsupported Phase 2 queue payload: {path}")
    return payload


def read_verdicts(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("verdicts"), list):
        return [row for row in payload["verdicts"] if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"unsupported verdict payload: {path}")


def post_id_key(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def severity_rank(value: Any) -> int:
    return {"high": 0, "med": 1, "medium": 1, "low": 2}.get(str(value or "").lower(), 9)


def seed_bucket_for(error: dict[str, Any]) -> str:
    dtype = str(error.get("disagreement_type") or "")
    if dtype == "wrong_work":
        return "precision_wrong_work_control"
    if dtype in {"over_resolved", "garbage_title", "cross_media_or_famous_mismatch"}:
        return "precision_identity_high"
    if dtype == "under_resolved_false_negative":
        return "recall_relevance_representative"
    if dtype in {"wrong_relevance", "wrong_discussion_type", "title_noisy_ocr"}:
        return "candidate_comment_multi"
    return seed_group(dtype) if dtype else "review_only"


def baseline_identity(row: dict[str, Any] | None) -> dict[str, Any]:
    identity = analysis_identity(row)
    return {
        "official_title": identity.get("official_title"),
        "heretic_url": identity.get("heretic_url"),
        "title_resolution_state": identity.get("title_resolution_state"),
        "title_resolution_allowed": identity.get("title_resolution_allowed"),
        "candidate_ledger_status": identity.get("candidate_ledger_status"),
        "candidate_count": identity.get("candidate_count") or 0,
    }


def _normalize_expected_title(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[\[\]【】()（）〈〉《》\"'`.,:;!?~·\-_/|]+", "", text)


def expected_title_matches(expected: str | None, actual: str | None) -> bool:
    if not expected or not actual:
        return False
    actual_norm = _normalize_expected_title(actual)
    for part in re.split(r"\s+/\s+|\s+or\s+|\s+또는\s+", str(expected)):
        candidate = part.strip()
        if not candidate:
            continue
        candidate_norm = _normalize_expected_title(candidate)
        if titles_match(candidate, actual):
            return True
        if candidate_norm and actual_norm and (candidate_norm in actual_norm or actual_norm in candidate_norm):
            return True
    return False


def make_seed(source_row: dict[str, Any], panel_row: dict[str, Any]) -> dict[str, Any]:
    disagreement_type = str(panel_row.get("disagreement_type") or "none")
    identity = baseline_identity(source_row)
    return {
        "post_id": panel_row["post_id"],
        "seed_group": panel_row.get("seed_bucket") or seed_bucket_for(panel_row),
        "disagreement_type": disagreement_type,
        "severity": str(panel_row.get("severity") or "low"),
        "shadow_label": identity.get("candidate_ledger_status") or "review_only",
    }


def add_panel_entry(
    panel_by_id: dict[int, dict[str, Any]],
    *,
    post_id: int,
    role: str,
    source_name: str,
    source_row: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    entry = panel_by_id.setdefault(
        post_id,
        {
            "post_id": post_id,
            "title": source_row.get("title"),
            "panel_roles": [],
            "baseline_identity": baseline_identity(source_row),
            "sources": [],
        },
    )
    if role not in entry["panel_roles"]:
        entry["panel_roles"].append(role)
    entry["sources"].append(
        {
            "source": source_name,
            "role": role,
            "failure_class": payload.get("failure_class"),
            "fix_axis": payload.get("fix_axis"),
            "disagreement_type": payload.get("disagreement_type"),
            "severity": payload.get("severity"),
            "recommended_action": payload.get("recommended_action"),
            "correct_hypothesis_present": bool(str(payload.get("correct_hypothesis") or "").strip()),
            "rationale": payload.get("note") or payload.get("row_rationale") or payload.get("control_reason"),
        }
    )
    for key in (
        "failure_class",
        "fix_axis",
        "disagreement_type",
        "severity",
        "recommended_action",
        "seed_bucket",
    ):
        if entry.get(key) is None and payload.get(key) is not None:
            entry[key] = payload.get(key)
    if str(payload.get("correct_hypothesis") or "").strip():
        entry.setdefault("correct_hypothesis", payload.get("correct_hypothesis"))


def add_accept_monitor_rows(
    panel_by_id: dict[int, dict[str, Any]],
    *,
    baseline_by_id: dict[int, dict[str, Any]],
    verdicts: list[dict[str, Any]],
    accept_sample_size: int,
) -> None:
    accepted = [row for row in verdicts if row.get("resolution_label") == "ACCEPT"]
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for verdict in accepted:
        pid = post_id_key(verdict.get("post_id"))
        if pid is None or pid not in baseline_by_id:
            continue
        identity = baseline_identity(baseline_by_id[pid])
        if identity.get("official_title"):
            resolved.append(verdict)
        else:
            unresolved.append(verdict)

    quota = max(1, accept_sample_size // 2)
    selected = resolved[:quota] + unresolved[: accept_sample_size - min(len(resolved), quota)]
    for verdict in selected:
        pid = post_id_key(verdict.get("post_id"))
        if pid is None or pid not in baseline_by_id:
            continue
        add_panel_entry(
            panel_by_id,
            post_id=pid,
            role="accept_monitor",
            source_name="phase1_accept_sample",
            source_row=baseline_by_id[pid],
            payload={
                "disagreement_type": "none",
                "severity": verdict.get("severity") or "low",
                "recommended_action": "no_action",
                "fix_axis": "accept_collateral_monitor",
                "note": verdict.get("note"),
            },
        )


def build_panel(
    *,
    baseline_rows: list[dict[str, Any]],
    survey_errors: list[dict[str, Any]],
    phase2_rows: list[dict[str, Any]],
    verdicts: list[dict[str, Any]],
    accept_sample_size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline_by_id = row_by_post_id(baseline_rows)
    panel_by_id: dict[int, dict[str, Any]] = {}
    missing = {"survey_errors": [], "phase2_queue": [], "controls": []}

    for error in survey_errors:
        pid = post_id_key(error.get("post_id"))
        if pid is None or pid not in baseline_by_id:
            missing["survey_errors"].append(error.get("post_id"))
            continue
        add_panel_entry(
            panel_by_id,
            post_id=pid,
            role="survey_error_136",
            source_name="detection_survey_20260626_errors",
            source_row=baseline_by_id[pid],
            payload={**error, "seed_bucket": seed_bucket_for(error)},
        )

    for queue_row in phase2_rows:
        pid = post_id_key(queue_row.get("post_id"))
        if pid is None or pid not in baseline_by_id:
            missing["phase2_queue"].append(queue_row.get("post_id"))
            continue
        add_panel_entry(
            panel_by_id,
            post_id=pid,
            role="phase2_queue",
            source_name="phase2_initial_queue",
            source_row=baseline_by_id[pid],
            payload=queue_row,
        )

    for pid, reason in DEFAULT_CONTROLS.items():
        if pid not in baseline_by_id:
            missing["controls"].append(pid)
            continue
        add_panel_entry(
            panel_by_id,
            post_id=pid,
            role="historical_regression_control",
            source_name="completed779_hermes_controls",
            source_row=baseline_by_id[pid],
            payload={
                "disagreement_type": "none",
                "severity": "high",
                "fix_axis": "regression_control",
                "control_reason": reason,
            },
        )

    add_accept_monitor_rows(
        panel_by_id,
        baseline_by_id=baseline_by_id,
        verdicts=verdicts,
        accept_sample_size=accept_sample_size,
    )

    panel_rows = sorted(
        panel_by_id.values(),
        key=lambda row: (
            severity_rank(row.get("severity")),
            str(row.get("fix_axis") or ""),
            int(row["post_id"]),
        ),
    )
    summary = {
        "unique_panel_posts": len(panel_rows),
        "survey_errors_total": len(survey_errors),
        "survey_errors_in_panel": len(survey_errors) - len(missing["survey_errors"]),
        "phase2_queue_total": len(phase2_rows),
        "phase2_queue_in_panel": len(phase2_rows) - len(missing["phase2_queue"]),
        "controls_requested": len(DEFAULT_CONTROLS),
        "controls_in_panel": len(DEFAULT_CONTROLS) - len(missing["controls"]),
        "missing": missing,
        "counts_by_role": dict(Counter(role for row in panel_rows for role in row["panel_roles"])),
        "counts_by_failure_class": dict(Counter(row.get("failure_class") or "none" for row in panel_rows)),
        "counts_by_fix_axis": dict(Counter(row.get("fix_axis") or "unknown" for row in panel_rows)),
        "counts_by_severity": dict(Counter(str(row.get("severity") or "") for row in panel_rows)),
    }
    return panel_rows, summary


def golden_bucket(error: dict[str, Any]) -> str | None:
    failure_class = str(error.get("failure_class") or "")
    correct = str(error.get("correct_hypothesis") or "").strip()
    if correct:
        return "positive_expected_work"
    if failure_class in {
        "over_resolved_nonwork",
        "generic_phrase_substring",
        "image_anchor_spurious",
        "slang_pollution",
        "homonym_cross_domain",
        "batch_context_bleed",
    }:
        return "negative_no_public_work"
    return None


def select_golden_rows(
    *,
    baseline_by_id: dict[int, dict[str, Any]],
    survey_errors: list[dict[str, Any]],
    per_bucket: int,
    extra_golden_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    selected_errors: list[dict[str, Any]] = []
    by_bucket: dict[str, list[dict[str, Any]]] = {"positive_expected_work": [], "negative_no_public_work": []}
    for error in sorted(
        survey_errors,
        key=lambda row: (
            str(row.get("failure_class") or ""),
            severity_rank(row.get("severity")),
            int(row.get("post_id") or 0),
        ),
    ):
        bucket = golden_bucket(error)
        pid = post_id_key(error.get("post_id"))
        if bucket and pid in baseline_by_id and len(by_bucket[bucket]) < per_bucket:
            by_bucket[bucket].append(error)
            selected_errors.append(error)

    golden_inputs: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for error in selected_errors:
        pid = int(error["post_id"])
        source_row = baseline_by_id[pid]
        panel_seed = {
            "post_id": pid,
            "disagreement_type": error.get("disagreement_type") or "none",
            "severity": error.get("severity") or "low",
            "seed_bucket": seed_bucket_for(error),
        }
        seed = make_seed(source_row, panel_seed)
        clean = clean_canary_row(source_row, seed)
        # Golden canaries must exercise production behavior, not judge-seed
        # remediation hooks. Expected answers stay only in golden_manifest.json.
        clean.pop("_judge_seed", None)
        clean["_golden_role"] = golden_bucket(error)
        golden_inputs.append(clean)
        manifest_rows.append(
            {
                "post_id": pid,
                "golden_role": golden_bucket(error),
                "failure_class": error.get("failure_class"),
                "disagreement_type": error.get("disagreement_type"),
                "severity": error.get("severity"),
                "expected_title_or_hypothesis": error.get("correct_hypothesis") or None,
                "expected_no_public_title": not bool(str(error.get("correct_hypothesis") or "").strip()),
                "baseline_identity": baseline_identity(source_row),
                "note": error.get("note"),
            }
        )

    extra_missing: list[int] = []
    extra_duplicate: list[int] = []
    selected_post_ids = {int(row["post_id"]) for row in manifest_rows}
    for extra in extra_golden_rows or []:
        pid = post_id_key(extra.get("post_id"))
        if pid is None:
            continue
        if pid not in baseline_by_id:
            extra_missing.append(pid)
            continue
        if pid in selected_post_ids:
            extra_duplicate.append(pid)
            continue
        source_row = baseline_by_id[pid]
        golden_role = str(extra.get("golden_role") or "extra_expected_work").strip()
        panel_seed = {
            "post_id": pid,
            "disagreement_type": extra.get("disagreement_type") or "none",
            "severity": extra.get("severity") or "high",
            "seed_bucket": golden_role,
        }
        seed = make_seed(source_row, panel_seed)
        clean = clean_canary_row(source_row, seed)
        clean.pop("_judge_seed", None)
        clean["_golden_role"] = golden_role
        golden_inputs.append(clean)
        selected_post_ids.add(pid)
        manifest_rows.append(
            {
                "post_id": pid,
                "golden_role": golden_role,
                "failure_class": extra.get("failure_class"),
                "disagreement_type": extra.get("disagreement_type"),
                "severity": extra.get("severity") or "high",
                "expected_title_or_hypothesis": extra.get("expected_title_or_hypothesis"),
                "expected_no_public_title": bool(extra.get("expected_no_public_title", False)),
                "expected_url": extra.get("expected_url"),
                "expected_status": extra.get("expected_status"),
                "baseline_identity": baseline_identity(source_row),
                "source": extra.get("source"),
                "note": extra.get("note"),
            }
        )
    summary = {
        "golden_rows": len(golden_inputs),
        "counts_by_role": dict(Counter(row["_golden_role"] for row in golden_inputs)),
        "per_bucket_limit": per_bucket,
        "extra_golden_rows_requested": len(extra_golden_rows or []),
        "extra_golden_rows_included": len(extra_golden_rows or []) - len(extra_missing) - len(extra_duplicate),
        "extra_golden_rows_missing": extra_missing,
        "extra_golden_rows_duplicate": extra_duplicate,
        "judge_seed_stripped_from_inputs": True,
    }
    return golden_inputs, manifest_rows, summary


def make_panel_inputs(
    *,
    panel_rows: list[dict[str, Any]],
    baseline_by_id: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for panel in panel_rows:
        pid = int(panel["post_id"])
        source_row = baseline_by_id[pid]
        clean = clean_canary_row(source_row, make_seed(source_row, panel))
        clean["_panel_roles"] = panel.get("panel_roles") or []
        inputs.append(clean)
    return inputs


def compare_collateral(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    *,
    expected_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    before_by_id = row_by_post_id(before_rows)
    after_by_id = row_by_post_id(after_rows)
    expected_by_id = {int(row["post_id"]): row for row in expected_rows or [] if row.get("post_id") is not None}
    shared_ids = sorted(set(before_by_id) & set(after_by_id))
    changes: list[dict[str, Any]] = []
    regression_count = 0
    for pid in shared_ids:
        before_identity = analysis_identity(before_by_id[pid])
        after_identity = analysis_identity(after_by_id[pid])
        before_title = before_identity.get("official_title")
        after_title = after_identity.get("official_title")
        if titles_match(before_title, after_title):
            if before_identity.get("heretic_url") != after_identity.get("heretic_url"):
                status = "same_title_url_changed"
            else:
                status = "unchanged"
        elif before_title and not after_title:
            status = "resolved_to_null"
        elif before_title and after_title:
            status = "resolved_to_different_title"
        elif not before_title and after_title:
            status = "null_to_resolved"
        else:
            status = "unchanged"
        if status == "unchanged":
            continue

        expected = expected_by_id.get(pid) or {}
        exempt = False
        if status in {"null_to_resolved", "resolved_to_different_title"}:
            expected_title = expected.get("expected_title_or_hypothesis")
            exempt = expected_title_matches(expected_title, after_title)
        if status == "resolved_to_null" and expected.get("expected_no_public_title"):
            exempt = True
        is_regression = status in {
            "resolved_to_null",
            "resolved_to_different_title",
            "null_to_resolved",
        } and not exempt
        if is_regression:
            regression_count += 1
        changes.append(
            {
                "post_id": pid,
                "status": status,
                "is_regression": is_regression,
                "exempted_by_expected_answer": exempt,
                "before_identity": baseline_identity(before_by_id[pid]),
                "after_identity": baseline_identity(after_by_id[pid]),
            }
        )
    return {
        "shared_post_count": len(shared_ids),
        "changed_post_count": len(changes),
        "collateral_regression_count": regression_count,
        "status_counts": dict(Counter(row["status"] for row in changes)),
        "regression_status_counts": dict(Counter(row["status"] for row in changes if row["is_regression"])),
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "rows": changes,
    }


def write_summary_markdown(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# Regression-safe grounding FIX-0 bootstrap 요약",
        "",
        f"- source result: `{summary['source_result']}`",
        f"- baseline artifact: `{summary['baseline_result']}`",
        f"- source manifest large_run_complete: `{summary.get('large_run_complete')}`",
        f"- source processed rows: `{summary['source_rows']}`",
        f"- regression panel unique posts: `{summary['panel']['unique_panel_posts']}`",
        f"- survey errors in panel: `{summary['panel']['survey_errors_in_panel']}/{summary['panel']['survey_errors_total']}`",
        f"- Phase 2 queue in panel: `{summary['panel']['phase2_queue_in_panel']}/{summary['panel']['phase2_queue_total']}`",
        f"- historical controls in panel: `{summary['panel']['controls_in_panel']}/{summary['panel']['controls_requested']}`",
        f"- golden rows: `{summary['golden']['golden_rows']}`",
        f"- extra golden rows: `{summary['golden'].get('extra_golden_rows_included', 0)}/{summary['golden'].get('extra_golden_rows_requested', 0)}`",
        f"- collateral selfcheck regression count: `{summary['collateral_selfcheck']['collateral_regression_count']}`",
        "",
        "## Gates",
        "",
        "- run integrity: `GO`는 FIX-0 산출물 생성에만 적용한다.",
        "- targeted canary status: `NOT_RUN`",
        "- semantic quality: `REVIEW-LOCKED`",
        "- full scan approval: `false`",
        "",
        "## Next",
        "",
        "이 panel/golden set을 canary 입력에 포함하고 실제 canary 결과와 collateral pass를 비교한 뒤에만 품질 승인을 논의한다.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def bootstrap(
    *,
    result_path: Path,
    phase1_root: Path,
    survey_errors_path: Path,
    out_dir: Path,
    accept_sample_size: int = 40,
    golden_per_bucket: int = 8,
    extra_golden_rows_path: Path | None = None,
) -> dict[str, Any]:
    baseline_rows = load_json_or_jsonl(result_path)
    baseline_by_id = row_by_post_id(baseline_rows)
    survey_payload = load_json(survey_errors_path)
    survey_errors = [row for row in survey_payload.get("errors", []) if isinstance(row, dict)]
    extra_golden_payload = load_json(extra_golden_rows_path) if extra_golden_rows_path else {}
    extra_golden_rows = (
        extra_golden_payload.get("rows", [])
        if isinstance(extra_golden_payload, dict)
        else extra_golden_payload
    )
    if not isinstance(extra_golden_rows, list):
        raise ValueError(f"unsupported extra golden payload: {extra_golden_rows_path}")
    phase2_queue = read_phase2_queue(phase1_root / "phase2_initial_queue.json")
    verdicts = read_verdicts(phase1_root / "_verdicts_final.json")

    baseline_result_path = out_dir / "baseline" / "baseline_result.json"
    baseline_manifest_path = out_dir / "baseline" / "baseline_manifest.json"
    baseline_result_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(result_path, baseline_result_path)
    source_manifest_path = result_path.with_name(result_path.stem + "_manifest.json")
    manifest_payload: dict[str, Any] = {}
    if source_manifest_path.exists():
        shutil.copy2(source_manifest_path, baseline_manifest_path)
        manifest_payload = load_json(source_manifest_path)

    panel_rows, panel_summary = build_panel(
        baseline_rows=baseline_rows,
        survey_errors=survey_errors,
        phase2_rows=phase2_queue["rows"],
        verdicts=verdicts,
        accept_sample_size=accept_sample_size,
    )
    panel_inputs = make_panel_inputs(panel_rows=panel_rows, baseline_by_id=baseline_by_id)
    golden_inputs, golden_manifest_rows, golden_summary = select_golden_rows(
        baseline_by_id=baseline_by_id,
        survey_errors=survey_errors,
        per_bucket=golden_per_bucket,
        extra_golden_rows=[row for row in extra_golden_rows if isinstance(row, dict)],
    )

    collateral_selfcheck = compare_collateral(baseline_rows, baseline_rows, expected_rows=golden_manifest_rows)

    write_jsonl(out_dir / "panel" / "regression_panel.jsonl", panel_rows)
    write_jsonl(out_dir / "panel" / "regression_panel_input.jsonl", panel_inputs)
    write_json(out_dir / "panel" / "regression_panel_summary.json", panel_summary)
    write_jsonl(out_dir / "golden" / "golden_set.jsonl", golden_inputs)
    write_json(out_dir / "golden" / "golden_manifest.json", {"rows": golden_manifest_rows, **golden_summary})
    write_json(out_dir / "collateral" / "collateral_baseline_selfcheck.json", collateral_selfcheck)

    summary = {
        "source_result": str(result_path),
        "source_rows": len(baseline_rows),
        "baseline_result": str(baseline_result_path),
        "baseline_manifest": str(baseline_manifest_path) if manifest_payload else None,
        "large_run_complete": manifest_payload.get("large_run_complete"),
        "completed_count": manifest_payload.get("completed_count"),
        "flushed_count": manifest_payload.get("flushed_count"),
        "pending_count": manifest_payload.get("pending_count"),
        "failed_count": manifest_payload.get("failed_count"),
        "phase1_root": str(phase1_root),
        "survey_errors": str(survey_errors_path),
        "extra_golden_rows": str(extra_golden_rows_path) if extra_golden_rows_path else None,
        "panel": panel_summary,
        "golden": golden_summary,
        "collateral_selfcheck": {
            "shared_post_count": collateral_selfcheck["shared_post_count"],
            "changed_post_count": collateral_selfcheck["changed_post_count"],
            "collateral_regression_count": collateral_selfcheck["collateral_regression_count"],
        },
        "gates": {
            "run_integrity": "GO_FIX0_ARTIFACTS_ONLY",
            "targeted_canary_status": "NOT_RUN",
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
        },
    }
    write_json(out_dir / "bootstrap_summary.json", summary)
    write_summary_markdown(out_dir / "summary_ko.md", summary)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--phase1-root", type=Path, required=True)
    parser.add_argument("--survey-errors", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--accept-sample-size", type=int, default=40)
    parser.add_argument("--golden-per-bucket", type=int, default=8)
    parser.add_argument("--extra-golden-rows", type=Path)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    summary = bootstrap(
        result_path=args.result,
        phase1_root=args.phase1_root,
        survey_errors_path=args.survey_errors,
        out_dir=args.out_dir,
        accept_sample_size=args.accept_sample_size,
        golden_per_bucket=args.golden_per_bucket,
        extra_golden_rows_path=args.extra_golden_rows,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
