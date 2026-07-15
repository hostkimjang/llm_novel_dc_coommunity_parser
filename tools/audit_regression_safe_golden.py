"""Audit a regression-safe golden canary against its frozen manifest.

This tool intentionally separates runtime completion from semantic quality:
the expert_main manifest proves health/completion, while this audit checks
expected-answer movement for the frozen golden rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from llm_batch.domain.title_integrity import exact_title_integrity_match
from tools.bootstrap_regression_safe_grounding import (
    analysis_identity,
    baseline_identity,
    compare_collateral,
    row_by_post_id,
    titles_match,
)
from tools.compare_completed779_improvement import load_json_or_jsonl
from tools.merge_interrupted_run_results import (
    PRODUCTION_BASELINE_PATH,
    PRODUCTION_BASELINE_SHA256,
    PRODUCTION_GOLDEN_PATH,
    PRODUCTION_GOLDEN_SHA256,
)


PRODUCTION_PANEL_ROWS = 375
PRODUCTION_GOLDEN_ROWS = 18


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _runtime_full375_binding(
    *,
    run_manifest: dict[str, Any],
    canary_rows: list[dict[str, Any]],
    canary_result: Path,
) -> dict[str, Any]:
    source_result_row_count = len(canary_rows)
    post_ids = [str(row.get("post_id") or "").strip() for row in canary_rows]
    actual_bindings = {
        "result_payload_sha256": canonical_sha256(canary_rows),
        "input_post_id_order_sha256": canonical_sha256(post_ids),
        "input_post_id_set_sha256": canonical_sha256(sorted(post_ids)),
    }
    counts = {
        "input_post_count": run_manifest.get("input_post_count"),
        "completed_count": run_manifest.get("completed_count"),
        "flushed_count": run_manifest.get("flushed_count"),
        "pending_count": run_manifest.get("pending_count"),
        "failed_count": run_manifest.get("failed_count"),
    }
    blockers: list[str] = []
    for field, expected in {
        "input_post_count": PRODUCTION_PANEL_ROWS,
        "completed_count": PRODUCTION_PANEL_ROWS,
        "flushed_count": PRODUCTION_PANEL_ROWS,
        "pending_count": 0,
        "failed_count": 0,
    }.items():
        value = counts[field]
        if value is None:
            blockers.append(f"{field}_missing")
        elif value != expected:
            blockers.append(f"{field}_mismatch")
    if source_result_row_count != PRODUCTION_PANEL_ROWS:
        blockers.append("source_result_row_count_mismatch")
    if run_manifest.get("large_run_complete") is not True:
        blockers.append("large_run_complete_not_true")
    for field, expected in actual_bindings.items():
        if run_manifest.get(field) is None:
            blockers.append(f"manifest_{field}_missing")
        elif run_manifest.get(field) != expected:
            blockers.append(f"manifest_{field}_mismatch")
    output_file = run_manifest.get("output_file")
    if not output_file:
        blockers.append("manifest_output_file_missing")
    else:
        output_path = Path(str(output_file))
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        if output_path.resolve() != canary_result.resolve():
            blockers.append("manifest_output_file_mismatch")
    return {
        "gate": "GO" if not blockers else "NO-GO",
        "expected_source_rows": PRODUCTION_PANEL_ROWS,
        "source_result_row_count": source_result_row_count,
        **counts,
        "large_run_complete": run_manifest.get("large_run_complete"),
        **actual_bindings,
        "blockers": blockers,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def norm(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[\[\]【】()（）〈〉《》\"'`.,:;!?~·\-_/|]+", "", text)


def expected_alternates(expected: str | None) -> list[str]:
    if not expected:
        return []
    parts = re.split(r"\s+/\s+|\s+or\s+|\s+또는\s+", expected)
    return [part.strip() for part in parts if part.strip()]


def expected_title_matches(expected: str | None, actual: str | None) -> bool:
    if not expected or not actual:
        return False
    for alt in expected_alternates(expected):
        if exact_title_integrity_match(alt, actual):
            return True
    return False


def expected_is_hypothesis(expected: str | None) -> bool:
    if not expected:
        return False
    text = str(expected)
    return any(token in text for token in ("미상", "계열", "hypothesis", "추정"))


def _identity_flags(identity: dict[str, Any]) -> set[str]:
    return {
        str(flag or "").strip()
        for flag in (identity.get("consistency_flags") or [])
        if str(flag or "").strip()
    }


def _collect_text_fragments(value: Any) -> list[str]:
    fragments: list[str] = []
    if value is None:
        return fragments
    if isinstance(value, str):
        if value.strip():
            fragments.append(value)
        return fragments
    if isinstance(value, (int, float, bool)):
        fragments.append(str(value))
        return fragments
    if isinstance(value, dict):
        for item in value.values():
            fragments.extend(_collect_text_fragments(item))
        return fragments
    if isinstance(value, list):
        for item in value:
            fragments.extend(_collect_text_fragments(item))
        return fragments
    return fragments


def expected_evidence_preserved_unresolved(expected: str | None, identity: dict[str, Any]) -> bool:
    if not expected:
        return False
    title_state = str(identity.get("title_resolution_state") or "").strip()
    if title_state not in {"unresolved_matchable", "ocr_explicit_title_unresolved", "multi_work", "author_new_work_context"}:
        return False
    if not bool(identity.get("is_relevant")) and not bool(identity.get("is_novel_related")):
        return False
    blob_norm = norm(" ".join(_collect_text_fragments({
        "search_evidence_catalog": identity.get("search_evidence_catalog"),
        "image_evidence_catalog": identity.get("image_evidence_catalog"),
        "candidate_ledger": identity.get("candidate_ledger"),
        "candidate_preservation_sources": identity.get("candidate_preservation_sources"),
        "title_candidates": identity.get("title_candidates"),
        "reason": identity.get("reason"),
    })))
    if not blob_norm:
        return False
    for alt in expected_alternates(expected):
        alt_n = norm(alt)
        if alt_n and alt_n in blob_norm:
            return True
    return False


def expected_hypothesis_preserved_unresolved(expected: str | None, identity: dict[str, Any]) -> bool:
    if not expected_is_hypothesis(expected):
        return False
    title_state = str(identity.get("title_resolution_state") or "").strip()
    if title_state not in {"unresolved_matchable", "ocr_explicit_title_unresolved", "multi_work", "author_new_work_context"}:
        return False
    if not bool(identity.get("is_relevant")) and not bool(identity.get("is_novel_related")):
        return False
    flags = _identity_flags(identity)
    has_boundary_evidence = bool(identity.get("image_evidence_catalog") or identity.get("candidate_ledger"))
    if not has_boundary_evidence and not ({"direct_image_explicit_title_rescued", "local_candidate_hold_preserved"} & flags):
        return False
    blob_norm = norm(" ".join(_collect_text_fragments({
        "search_evidence_catalog": identity.get("search_evidence_catalog"),
        "image_evidence_catalog": identity.get("image_evidence_catalog"),
        "candidate_ledger": identity.get("candidate_ledger"),
        "candidate_preservation_sources": identity.get("candidate_preservation_sources"),
        "title_candidates": identity.get("title_candidates"),
        "reason": identity.get("reason"),
    })))
    if not blob_norm:
        return False
    generic = {norm(item) for item in ("계열", "표지", "작품", "미상", "hypothesis", "추정")}
    for raw in re.split(r"[^0-9A-Za-z가-힣]+", str(expected or "")):
        token = norm(raw)
        if len(token) >= 3 and token not in generic and token in blob_norm:
            return True
    return False


def expected_hypothesis_resolved_by_direct_image(
    expected: str | None,
    actual: str | None,
    identity: dict[str, Any],
) -> bool:
    if not expected_is_hypothesis(expected) or not actual:
        return False
    flags = _identity_flags(identity)
    if not ({"direct_image_explicit_title_rescued", "direct_image_work_surface_lock"} & flags):
        return False
    generic = {norm(item) for item in ("계열", "표지", "작품", "미상", "hypothesis", "추정")}
    actual_n = norm(actual)
    for raw in re.split(r"[^0-9A-Za-z가-힣]+", str(expected or "")):
        token = norm(raw)
        if len(token) >= 3 and token not in generic and token in actual_n:
            return True
    return False


def positive_image_boundary_preserved_unresolved(identity: dict[str, Any]) -> bool:
    title_state = str(identity.get("title_resolution_state") or "").strip()
    if title_state not in {"unresolved_matchable", "ocr_explicit_title_unresolved", "multi_work"}:
        return False
    if not bool(identity.get("is_relevant")):
        return False
    flags = _identity_flags(identity)
    if "vlm_ocr_title_conflict_with_final_title" in flags:
        return True
    image_catalog = identity.get("image_evidence_catalog")
    return bool(image_catalog and "relation_hold_unresolved_recovered" in flags)


def actual_title_from_identity(identity: dict[str, Any], analysis: dict[str, Any]) -> str | None:
    return (
        identity.get("official_title")
        or analysis.get("official_title")
        or analysis.get("pipeline_official_title")
    )


def build_audit(
    *,
    canary_rows: list[dict[str, Any]],
    golden_rows: list[dict[str, Any]],
    run_manifest: dict[str, Any],
    canary_result: Path,
    canary_manifest: Path,
    golden_manifest: Path,
) -> dict[str, Any]:
    after_by_id = row_by_post_id(canary_rows)
    audit_rows: list[dict[str, Any]] = []
    for expected in golden_rows:
        pid = int(expected["post_id"])
        after = after_by_id.get(pid)
        identity = baseline_identity(after) if after else {}
        analysis = analysis_identity(after) if after else {}
        raw_identity: dict[str, Any] = {}
        if isinstance(after, dict):
            result_payload = after.get("analysis_result") or {}
            if isinstance(result_payload, dict) and isinstance(result_payload.get("identity"), dict):
                raw_identity = result_payload.get("identity") or {}
        identity_for_gate = dict(raw_identity)
        for source in (analysis, identity):
            for key, value in source.items():
                identity_for_gate.setdefault(key, value)
        actual_title = actual_title_from_identity(identity, analysis)
        expected_title = expected.get("expected_title_or_hypothesis")
        expected_no_public_title = bool(expected.get("expected_no_public_title"))
        title_state = identity_for_gate.get("title_resolution_state")
        work_resolution = identity_for_gate.get("work_resolution")
        is_relevant = identity_for_gate.get("is_relevant")

        if not after:
            status = "missing_after_row"
            passed = False
        elif expected_no_public_title:
            passed = not bool(actual_title)
            status = "expected_null_respected" if passed else "unexpected_resolved_title"
        elif expected_title_matches(expected_title, actual_title):
            passed = True
            status = "expected_title_resolved"
        elif expected_hypothesis_resolved_by_direct_image(expected_title, actual_title, identity_for_gate):
            passed = True
            status = "expected_hypothesis_resolved_by_direct_image"
        elif not actual_title and expected_evidence_preserved_unresolved(expected_title, identity_for_gate):
            passed = True
            status = "expected_work_evidence_preserved_unresolved"
        elif not actual_title and positive_image_boundary_preserved_unresolved(identity_for_gate):
            passed = True
            status = "positive_image_boundary_preserved_unresolved"
        elif not actual_title and expected_hypothesis_preserved_unresolved(expected_title, identity_for_gate):
            passed = True
            status = "expected_hypothesis_preserved_unresolved"
        elif expected_is_hypothesis(expected_title) and not actual_title and is_relevant:
            passed = False
            status = "expected_hypothesis_unresolved_without_preserved_evidence"
        elif not actual_title and title_state in {"unresolved_matchable", "ocr_explicit_title_unresolved", "multi_work"}:
            passed = False
            status = "positive_work_unresolved"
        elif actual_title:
            passed = False
            status = "wrong_or_unexpected_title"
        else:
            passed = False
            status = "positive_work_unresolved"

        audit_rows.append(
            {
                "post_id": pid,
                "golden_role": expected.get("golden_role"),
                "failure_class": expected.get("failure_class"),
                "severity": expected.get("severity"),
                "expected_no_public_title": expected_no_public_title,
                "expected_title_or_hypothesis": expected_title,
                "actual_identity": identity,
                "title_resolution_state": title_state,
                "work_resolution": work_resolution,
                "status": status,
                "passed": passed,
                "note": expected.get("note"),
            }
        )

    status_counts = dict(Counter(row["status"] for row in audit_rows))
    role_counts = dict(Counter(row["golden_role"] for row in audit_rows))
    passed_count = sum(1 for row in audit_rows if row["passed"])
    negative_rows = [row for row in audit_rows if row["expected_no_public_title"]]
    positive_rows = [row for row in audit_rows if not row["expected_no_public_title"]]
    negative_passed = sum(1 for row in negative_rows if row["passed"])
    positive_passed = sum(1 for row in positive_rows if row["passed"])
    golden_post_ids = [str(row.get("post_id") or "").strip() for row in golden_rows]
    golden_contract_blockers: list[str] = []
    if len(golden_rows) != PRODUCTION_GOLDEN_ROWS:
        golden_contract_blockers.append("golden_row_count_not_18")
    if len(set(golden_post_ids)) != len(golden_post_ids):
        golden_contract_blockers.append("golden_post_id_duplicate")
    if any(not post_id for post_id in golden_post_ids):
        golden_contract_blockers.append("golden_post_id_missing")
    semantic_gate = (
        "PASS"
        if passed_count == len(audit_rows) and not golden_contract_blockers
        else "NO-GO"
    )
    runtime_full375 = _runtime_full375_binding(
        run_manifest=run_manifest,
        canary_rows=canary_rows,
        canary_result=canary_result,
    )
    after_post_ids = [str(row.get("post_id") or "").strip() for row in canary_rows]
    gate = "PASS" if semantic_gate == "PASS" and runtime_full375["gate"] == "GO" else "NO-GO"
    return {
        "report_type": "golden18_bound_audit",
        "scope": "golden_canary_expected_answer_audit",
        "gate": gate,
        "canary_result": str(canary_result),
        "canary_manifest": str(canary_manifest),
        "golden_manifest": str(golden_manifest),
        "after_result_path": str(canary_result),
        "merged_manifest_path": str(canary_manifest),
        "golden_manifest_path": str(golden_manifest),
        "after_result_sha256": file_sha256(canary_result),
        "after_result_payload_sha256": canonical_sha256(canary_rows),
        "after_post_id_order_sha256": canonical_sha256(after_post_ids),
        "after_post_id_set_sha256": canonical_sha256(sorted(after_post_ids)),
        "merged_manifest_sha256": file_sha256(canary_manifest),
        "golden_manifest_sha256": file_sha256(golden_manifest),
        "runtime": {
            "input_post_count": run_manifest.get("input_post_count"),
            "completed_count": run_manifest.get("completed_count"),
            "flushed_count": run_manifest.get("flushed_count"),
            "pending_count": run_manifest.get("pending_count"),
            "failed_count": run_manifest.get("failed_count"),
            "large_run_complete": run_manifest.get("large_run_complete"),
            "source_result_row_count": len(canary_rows),
            "source_full375_gate": runtime_full375["gate"],
            "source_full375_blockers": runtime_full375["blockers"],
            "vlm_ocr_semantic_review_ready": run_manifest.get("vlm_ocr_semantic_review_ready"),
            "vlm_ocr_semantic_review_blocker": run_manifest.get("vlm_ocr_semantic_review_blocker"),
            "slang_db_requested": "off",
        },
        "runtime_full375_source": runtime_full375,
        "audited_golden_rows": len(audit_rows),
        "golden_contract": {
            "gate": "GO" if not golden_contract_blockers else "NO-GO",
            "expected_rows": PRODUCTION_GOLDEN_ROWS,
            "actual_rows": len(golden_rows),
            "golden_manifest_path": str(golden_manifest),
            "golden_manifest_sha256": file_sha256(golden_manifest),
            "expected_production_path": str(PRODUCTION_GOLDEN_PATH),
            "expected_production_sha256": PRODUCTION_GOLDEN_SHA256,
            "blockers": golden_contract_blockers,
        },
        "row_count": len(audit_rows),
        "passed_count": passed_count,
        "failed_count": len(audit_rows) - passed_count,
        "negative_no_public_work_count": len(negative_rows),
        "negative_no_public_work_passed": negative_passed,
        "positive_expected_work_count": len(positive_rows),
        "positive_expected_work_passed": positive_passed,
        "status_counts": status_counts,
        "role_counts": role_counts,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "canary_semantic_gate": semantic_gate,
        "rows": audit_rows,
    }


def audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Regression-safe golden canary audit",
        "",
        f"- gate: `{audit['gate']}`",
        f"- canary_semantic_gate: `{audit['canary_semantic_gate']}`",
        (
            "- source runtime: "
            f"input=`{audit['runtime']['input_post_count']}`, "
            f"completed=`{audit['runtime']['completed_count']}`, "
            f"flushed=`{audit['runtime']['flushed_count']}`, "
            f"pending=`{audit['runtime']['pending_count']}`, "
            f"failed=`{audit['runtime']['failed_count']}`, "
            f"large_run_complete=`{audit['runtime']['large_run_complete']}`"
        ),
        f"- source runtime gate: `{audit['runtime_full375_source']['gate']}`",
        f"- audited golden rows: `{audit['audited_golden_rows']}`",
        f"- golden18 contract: `{audit['golden_contract']['gate']}` "
        f"(`{audit['golden_contract']['actual_rows']}/18`)",
        f"- VLM/OCR semantic gate ready: `{audit['runtime']['vlm_ocr_semantic_review_ready']}`",
        f"- slang_db: `{audit['runtime']['slang_db_requested']}`",
        f"- expected rows: `{audit['row_count']}`",
        f"- passed: `{audit['passed_count']}`",
        f"- failed: `{audit['failed_count']}`",
        (
            "- negative no-public-work passed: "
            f"`{audit['negative_no_public_work_passed']}/{audit['negative_no_public_work_count']}`"
        ),
        (
            "- positive expected-work resolved: "
            f"`{audit['positive_expected_work_passed']}/{audit['positive_expected_work_count']}`"
        ),
        f"- status counts: `{audit['status_counts']}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "## Rows",
        "",
    ]
    for row in audit["rows"]:
        lines.append(
            "- "
            f"`{row['post_id']}` `{row['golden_role']}`: "
            f"`{row['status']}`, passed=`{str(row['passed']).lower()}`, "
            f"expected=`{row['expected_title_or_hypothesis']}`, "
            f"actual=`{row['actual_identity'].get('official_title')}`"
        )
    lines.append("")
    return "\n".join(lines)


def collateral_markdown(collateral: dict[str, Any]) -> str:
    lines = [
        "# Regression-safe full375 adjusted collateral compare",
        "",
        f"- scope: `{collateral['scope']}`",
        f"- baseline_mode: `{collateral['baseline_mode']}`",
        f"- collateral_measure: `{collateral['collateral_measure']}`",
        f"- shared posts: `{collateral['shared_post_count']}`",
        f"- changed posts: `{collateral['changed_post_count']}`",
        f"- collateral regression candidates: `{collateral['collateral_regression_count']}`",
        f"- status counts: `{collateral['status_counts']}`",
        (
            "- source runtime: "
            f"input=`{collateral['runtime_input_post_count']}`, "
            f"completed=`{collateral['runtime_completed_count']}`, "
            f"flushed=`{collateral['runtime_flushed_count']}`, "
            f"pending=`{collateral['runtime_pending_count']}`, "
            f"failed=`{collateral['runtime_failed_count']}`, "
            f"large_run_complete=`{collateral['runtime_large_run_complete']}`"
        ),
        f"- source runtime gate: `{collateral['runtime_gate']}`",
        f"- VLM/OCR semantic gate ready: `{collateral['vlm_ocr_semantic_review_ready']}`",
        "- semantic_quality: `REVIEW-LOCKED`",
        "- full_scan_approval: `false`",
        "",
        "이 파일은 baseline375와 merged375의 canonical adjusted drift 입력이며, 판결/validator 전에는 approval이 아닙니다.",
        "",
        "## Changed Rows",
        "",
    ]
    for row in collateral["rows"]:
        lines.append(
            "- "
            f"`{row['post_id']}`: `{row['status']}`, "
            f"regression_candidate=`{str(row['is_regression']).lower()}`, "
            f"before=`{row['before_identity'].get('official_title')}`, "
            f"after=`{row['after_identity'].get('official_title')}`"
        )
    lines.append("")
    return "\n".join(lines)


def bind_collateral_runtime(
    *,
    collateral: dict[str, Any],
    audit: dict[str, Any],
    run_manifest: dict[str, Any],
    canary_rows: list[dict[str, Any]],
    baseline: Path,
    canary_result: Path,
    canary_manifest: Path,
    golden_manifest: Path,
) -> dict[str, Any]:
    output = dict(collateral)
    output.update(
        {
            "report_type": "full375_runtime_collateral_compare",
            "compare_id": f"{canary_result.stem}_adjudicated_adjusted_drift",
            "scope": "full375_adjudicated_baseline_vs_merged_runtime",
            "gate": (
                "REVIEW-LOCKED"
                if audit["runtime_full375_source"]["gate"] == "GO"
                else "NO-GO"
            ),
            "baseline_mode": "adjudicated_rebaseline",
            "collateral_measure": "adjusted_drift",
            "expected_shared_posts": PRODUCTION_PANEL_ROWS,
            "adjusted_drift_count": collateral.get("changed_post_count"),
            "baseline_path": str(baseline),
            "after_path": str(canary_result),
            "golden_manifest_path": str(golden_manifest),
            "canary_manifest_path": str(canary_manifest),
            "runtime_input_post_count": run_manifest.get("input_post_count"),
            "runtime_completed_count": run_manifest.get("completed_count"),
            "runtime_flushed_count": run_manifest.get("flushed_count"),
            "runtime_pending_count": run_manifest.get("pending_count"),
            "runtime_failed_count": run_manifest.get("failed_count"),
            "runtime_large_run_complete": run_manifest.get("large_run_complete"),
            "runtime_result_row_count": len(canary_rows),
            "runtime_gate": audit["runtime_full375_source"]["gate"],
            "runtime_complete": audit["runtime_full375_source"]["gate"] == "GO",
            "runtime_blockers": audit["runtime_full375_source"]["blockers"],
            "after_result_sha256": audit["after_result_sha256"],
            "after_result_payload_sha256": audit["after_result_payload_sha256"],
            "after_post_id_order_sha256": audit["after_post_id_order_sha256"],
            "after_post_id_set_sha256": audit["after_post_id_set_sha256"],
            "canary_manifest_sha256": audit["merged_manifest_sha256"],
            "golden_manifest_sha256": audit["golden_manifest_sha256"],
            "vlm_ocr_semantic_review_ready": run_manifest.get("vlm_ocr_semantic_review_ready"),
            "slang_db_requested": "off",
        }
    )
    return output


def apply_production_root_binding(
    *,
    audit: dict[str, Any],
    baseline: Path,
    canary_result: Path,
    golden_manifest: Path,
) -> None:
    production_root = PRODUCTION_BASELINE_PATH.parents[1]
    try:
        is_production = canary_result.resolve().is_relative_to(production_root)
    except AttributeError:  # pragma: no cover - Python 3.8 compatibility
        is_production = production_root in canary_result.resolve().parents
    issues: list[str] = []
    if is_production:
        if baseline.resolve() != PRODUCTION_BASELINE_PATH:
            issues.append("production_baseline_path_mismatch")
        elif file_sha256(baseline) != PRODUCTION_BASELINE_SHA256:
            issues.append("production_baseline_sha256_mismatch")
        if golden_manifest.resolve() != PRODUCTION_GOLDEN_PATH:
            issues.append("production_golden_path_mismatch")
        elif file_sha256(golden_manifest) != PRODUCTION_GOLDEN_SHA256:
            issues.append("production_golden_sha256_mismatch")
    audit["production_fixed_roots"] = {
        "applicable": is_production,
        "gate": "GO" if not issues else "NO-GO",
        "issues": issues,
        "panel_binding_delegated_to_merge_trust_anchor": True,
    }
    if issues:
        audit["gate"] = "NO-GO"
        audit["runtime_full375_source"]["gate"] = "NO-GO"
        audit["runtime_full375_source"]["blockers"].extend(issues)
        audit["runtime"]["source_full375_gate"] = "NO-GO"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--canary-result", required=True, type=Path)
    parser.add_argument("--canary-manifest", required=True, type=Path)
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--out-audit-json", required=True, type=Path)
    parser.add_argument("--out-audit-md", required=True, type=Path)
    parser.add_argument("--out-collateral-json", required=True, type=Path)
    parser.add_argument("--out-collateral-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    args = parser.parse_args()

    baseline_rows = load_json_or_jsonl(args.baseline)
    canary_rows = load_json_or_jsonl(args.canary_result)
    golden_payload = read_json(args.golden_manifest)
    golden_rows = golden_payload["rows"]
    run_manifest = read_json(args.canary_manifest)

    audit = build_audit(
        canary_rows=canary_rows,
        golden_rows=golden_rows,
        run_manifest=run_manifest,
        canary_result=args.canary_result,
        canary_manifest=args.canary_manifest,
        golden_manifest=args.golden_manifest,
    )
    apply_production_root_binding(
        audit=audit,
        baseline=args.baseline,
        canary_result=args.canary_result,
        golden_manifest=args.golden_manifest,
    )
    collateral = bind_collateral_runtime(
        collateral=compare_collateral(baseline_rows, canary_rows, expected_rows=golden_rows),
        audit=audit,
        run_manifest=run_manifest,
        canary_rows=canary_rows,
        baseline=args.baseline,
        canary_result=args.canary_result,
        canary_manifest=args.canary_manifest,
        golden_manifest=args.golden_manifest,
    )

    write_json(args.out_audit_json, audit)
    write_text(args.out_audit_md, audit_markdown(audit))
    write_json(args.out_collateral_json, collateral)
    write_text(args.out_collateral_md, collateral_markdown(collateral))
    print(
        json.dumps(
            {
                "audit_json": str(args.out_audit_json),
                "audit_md": str(args.out_audit_md),
                "collateral_json": str(args.out_collateral_json),
                "collateral_md": str(args.out_collateral_md),
                "gate": audit["gate"],
                "source_runtime_gate": audit["runtime_full375_source"]["gate"],
                "canary_semantic_gate": audit["canary_semantic_gate"],
                "passed_count": audit["passed_count"],
                "failed_count": audit["failed_count"],
                "status_counts": audit["status_counts"],
                "collateral_regression_count": collateral["collateral_regression_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.fail_on_no_go and audit["gate"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
