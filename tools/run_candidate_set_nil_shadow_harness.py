from __future__ import annotations

"""Saved-artifact-only CandidateSet + NIL shadow harness.

This tool deliberately never writes to, or projects into, the public result
fields.  It derives an uncalibrated CandidateSet/NIL envelope from a frozen
Golden18 result and records only an auditable shadow comparison.
"""

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_batch.grounding.candidate_set_shadow import (
    NIL_LABEL,
    PROBABILITY_STATUS,
    selective_shadow_from_identity,
    selective_shadow_from_dict,
)
from src.llm_batch.grounding.candidate_audit import apply_candidate_audit_fields
from src.llm_batch.grounding.candidate_generation import build_candidate_generation_snapshot


RUN_SPEC_SCHEMA = "candidate-set-nil-shadow-runspec-v1"
REPORT_SCHEMA = "candidate-set-nil-shadow-saved-artifact-v1"
PARENT_SCHEMA = "pipeline-improvement-runspec-v2"
MODE = "SAVED_ARTIFACT_SHADOW_NO_RUNTIME"
EXPECTED_GENERATION_STATUS = "UNKNOWN"
EXPECTED_RECALL_STATUS = "NOT_EVALUABLE_GENERATION_UNKNOWN"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(path: str | Path) -> Path:
    value = Path(path)
    return (value if value.is_absolute() else ROOT / value).resolve()


def _stored_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _artifact_ref(path: str | Path) -> dict[str, Any]:
    resolved = _resolve_path(path)
    if not resolved.is_file():
        raise ValueError(f"artifact missing: {resolved}")
    return {"path": _stored_path(resolved), "sha256": _sha256_file(resolved), "bytes": resolved.stat().st_size}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_rows(path: Path) -> list[dict[str, Any]]:
    value = _load_json(path)
    rows = value if isinstance(value, list) else value.get("rows") if isinstance(value, dict) else None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON row list: {path}")
    return rows


def _post_id(row: dict[str, Any]) -> str:
    post_id = str(row.get("post_id") or "").strip()
    if not post_id:
        raise ValueError("row is missing post_id")
    return post_id


def _post_contract(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    ids = [_post_id(row) for row in rows]
    duplicate = sorted(value for value, count in Counter(ids).items() if count > 1)
    if duplicate:
        raise ValueError(f"{label} duplicate post_id: {','.join(duplicate)}")
    return {
        "row_count": len(ids),
        "post_id_order_sha256": _canonical_hash(ids),
        "post_id_set_sha256": _canonical_hash(sorted(ids)),
        "post_ids": ids,
    }


def _assert_contract(left: dict[str, Any], right: dict[str, Any], message: str) -> None:
    for key in ("row_count", "post_id_order_sha256", "post_id_set_sha256"):
        if left.get(key) != right.get(key):
            raise ValueError(f"{message} {key} mismatch")


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("analysis_result")
    identity = result.get("identity") if isinstance(result, dict) else None
    return identity if isinstance(identity, dict) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _public_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    novel = identity.get("novel_identity")
    novel = novel if isinstance(novel, dict) else {}
    ledger = identity.get("candidate_ledger")
    ledger = ledger if isinstance(ledger, dict) else {}
    decision = identity.get("promotion_decision")
    decision = decision if isinstance(decision, dict) else ledger.get("promotion_decision")
    decision = decision if isinstance(decision, dict) else {}
    trace = identity.get("publish_contract_trace")
    trace = trace if isinstance(trace, dict) else ledger.get("publish_contract_trace")
    trace = trace if isinstance(trace, dict) else {}
    fingerprint = _first_text(
        identity.get("publish_contract_input_fingerprint"),
        ledger.get("publish_contract_input_fingerprint"),
    )
    return {
        "official_title": _first_text(novel.get("official_title"), novel.get("official_novel_title"), identity.get("official_title"), decision.get("official_title")),
        "official_url": _first_text(novel.get("official_url"), novel.get("heretic_url"), identity.get("official_url"), decision.get("official_url")),
        "promotion_decision": copy.deepcopy(decision),
        "publish_contract_trace": copy.deepcopy(trace),
        "publish_contract_input_fingerprint": fingerprint,
        "promotion_gate_state": copy.deepcopy(identity.get("promotion_gate_state") or ledger.get("promotion_gate_state") or {}),
        "promotion_gate_evidence": copy.deepcopy(identity.get("promotion_gate_evidence") or ledger.get("promotion_gate_evidence") or []),
        "publish_contract_version": _first_text(identity.get("publish_contract_version"), ledger.get("publish_contract_version")),
        "decision_bypassed_gate": decision.get("bypassed_gate"),
        "trace_bypassed_gate": trace.get("bypassed_gate"),
    }


def _public_snapshot_hash(snapshot: dict[str, Any]) -> str:
    return _canonical_hash(snapshot)


def _implementation_contract() -> dict[str, Any]:
    refs = {
        "harness_tool": _artifact_ref(Path(__file__)),
        "candidate_generation": _artifact_ref(ROOT / "src/llm_batch/candidate_generation.py"),
        "candidate_set_shadow": _artifact_ref(ROOT / "src/llm_batch/candidate_set_shadow.py"),
        "candidate_audit": _artifact_ref(ROOT / "src/llm_batch/candidate_audit.py"),
        "agentic_pipeline": _artifact_ref(ROOT / "src/llm_batch/agentic_pipeline.py"),
    }
    return {"artifacts": refs, "sha256": _canonical_hash({name: ref["sha256"] for name, ref in sorted(refs.items())})}


def _validate_artifact_ref(ref: Any, name: str) -> Path:
    if not isinstance(ref, dict):
        raise ValueError(f"artifact ref missing: {name}")
    path = _resolve_path(str(ref.get("path") or ""))
    if not path.is_file():
        raise ValueError(f"artifact missing on disk: {name}")
    if _sha256_file(path) != ref.get("sha256"):
        raise ValueError(f"artifact sha256 mismatch: {name}")
    return path


def _validate_parent(parent_path: Path) -> tuple[dict[str, Any], Path, list[dict[str, Any]], dict[str, Any]]:
    # The P1 anchor is admissible only when the canonical P0 validator accepts
    # the whole P0 artifact graph, not merely its self-hash and baseline path.
    from tools.run_pipeline_improvement_harness import validate_run_spec as validate_p0_run_spec

    validate_p0_run_spec(parent_path)
    parent = _load_json(parent_path)
    if not isinstance(parent, dict) or parent.get("schema_version") != PARENT_SCHEMA:
        raise ValueError("unsupported P0 parent run spec")
    stored_hash = str(parent.get("run_spec_sha256") or "")
    payload = {key: value for key, value in parent.items() if key != "run_spec_sha256"}
    if stored_hash != _canonical_hash(payload):
        raise ValueError("P0 parent self hash mismatch")
    artifacts = parent.get("artifacts")
    if not isinstance(artifacts, dict) or not isinstance(artifacts.get("baseline_result"), dict):
        raise ValueError("P0 parent baseline artifact missing")
    baseline_path = _validate_artifact_ref(artifacts["baseline_result"], "P0 baseline_result")
    rows = _load_rows(baseline_path)
    actual_contract = _post_contract(rows, "P0 baseline")
    stored_contract = parent.get("post_contract")
    if not isinstance(stored_contract, dict):
        raise ValueError("P0 parent post contract missing")
    _assert_contract(actual_contract, stored_contract, "P0 parent post contract")
    return parent, baseline_path, rows, actual_contract


def _verify_expected_audit(
    audit: dict[str, Any], baseline_ref: dict[str, Any], baseline_contract: dict[str, Any]
) -> dict[str, Any]:
    if audit.get("report_type") != "golden18_bound_audit":
        raise ValueError("expected audit report type mismatch")
    if audit.get("semantic_quality") != "REVIEW-LOCKED" or audit.get("full_scan_approval") is not False:
        raise ValueError("expected audit approval boundary mismatch")
    if int(audit.get("row_count") or 0) != baseline_contract["row_count"]:
        raise ValueError("expected audit row_count mismatch")
    if audit.get("after_result_sha256") != baseline_ref["sha256"]:
        raise ValueError("expected audit baseline sha256 mismatch")
    for key, expected in (("after_post_id_order_sha256", baseline_contract["post_id_order_sha256"]), ("after_post_id_set_sha256", baseline_contract["post_id_set_sha256"])):
        if audit.get(key) != expected:
            raise ValueError(f"expected audit {key} mismatch")
    rows = audit.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("expected audit rows missing")
    audit_contract = _post_contract(rows, "expected audit")
    _assert_contract(audit_contract, baseline_contract, "expected audit/baseline")
    if any(row.get("passed") is not True for row in rows):
        raise ValueError("expected audit contains an unpassed row")
    return {"rows": rows, "post_contract": audit_contract}


def _verify_label_ledger(
    ledger: dict[str, Any], audit_ref: dict[str, Any], baseline_ref: dict[str, Any], baseline_contract: dict[str, Any], audit_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if ledger.get("schema_version") != "candidate-set-nil-label-ledger-v1":
        raise ValueError("label ledger schema mismatch")
    for name, expected in (("source_expected_audit", audit_ref), ("source_baseline_result", baseline_ref)):
        ref = ledger.get(name)
        if not isinstance(ref, dict) or ref.get("sha256") != expected["sha256"]:
            raise ValueError(f"label ledger {name} sha256 mismatch")
        if _stored_path(_resolve_path(str(ref.get("path") or ""))) != expected["path"]:
            raise ValueError(f"label ledger {name} path mismatch")
    if ledger.get("semantic_quality") != "REVIEW-LOCKED" or ledger.get("full_scan_approval") is not False:
        raise ValueError("label ledger approval boundary mismatch")
    policy = ledger.get("label_policy")
    if not isinstance(policy, dict) or policy.get("abstain_is_not_truth_label") is not True or policy.get("candidate_set_recall_requires_complete_generation_status") is not True:
        raise ValueError("label ledger policy flags mismatch")
    rows = ledger.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("label ledger rows missing")
    ledger_contract = _post_contract(rows, "label ledger")
    _assert_contract(ledger_contract, baseline_contract, "label ledger/baseline")
    truth_counts = Counter(str(row.get("truth_kind") or "") for row in rows)
    if set(truth_counts) - {"CANDIDATE", "NIL", "UNJUDGED"}:
        raise ValueError("label ledger truth_kind invalid")
    counts = ledger.get("counts")
    if not isinstance(counts, dict) or any(
        not isinstance(counts.get(key), int) or counts[key] != expected
        for key, expected in (
            ("rows", len(rows)),
            ("candidate_truth", truth_counts["CANDIDATE"]),
            ("nil_truth", truth_counts["NIL"]),
            ("unjudged", truth_counts["UNJUDGED"]),
        )
    ):
        raise ValueError("label ledger counts mismatch")
    audit_by_id = {str(row["post_id"]): row for row in audit_rows}
    for label in rows:
        audit = audit_by_id[_post_id(label)]
        truth = label.get("truth_kind")
        if truth == "CANDIDATE":
            if not isinstance(label.get("expected_title"), str) or label["expected_title"] != audit.get("expected_title_or_hypothesis"):
                raise ValueError("label ledger candidate/audit title mismatch")
        elif truth == "NIL":
            if not (audit.get("golden_role") == "negative_no_public_work" and audit.get("expected_no_public_title") is True and audit.get("status") == "expected_null_respected"):
                raise ValueError("label ledger NIL/audit semantics mismatch")
        elif truth == "UNJUDGED":
            if label.get("expected_title") is not None or label.get("expected_action") != "ABSTAIN":
                raise ValueError("label ledger UNJUDGED semantics mismatch")
    return {"rows": rows, "post_contract": ledger_contract, "truth_counts": dict(truth_counts)}


def create_run_spec(*, parent_p0_run_spec_path: str | Path, expected_audit_path: str | Path, label_ledger_path: str | Path) -> dict[str, Any]:
    parent_ref = _artifact_ref(parent_p0_run_spec_path)
    audit_ref = _artifact_ref(expected_audit_path)
    ledger_ref = _artifact_ref(label_ledger_path)
    parent, baseline_path, rows, contract = _validate_parent(_resolve_path(parent_ref["path"]))
    baseline_ref = _artifact_ref(baseline_path)
    audit = _load_json(_resolve_path(audit_ref["path"]))
    ledger = _load_json(_resolve_path(ledger_ref["path"]))
    if not isinstance(audit, dict) or not isinstance(ledger, dict):
        raise ValueError("expected audit and label ledger must be JSON objects")
    audit_info = _verify_expected_audit(audit, baseline_ref, contract)
    _verify_label_ledger(ledger, audit_ref, baseline_ref, contract, audit_info["rows"])
    spec: dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "artifacts": {"p0_parent_run_spec": parent_ref, "expected_audit": audit_ref, "label_ledger": ledger_ref, "baseline_result": baseline_ref},
        "p0_parent": {"run_spec_self_hash": parent["run_spec_sha256"], "baseline_result_sha256": baseline_ref["sha256"], "post_contract": {key: contract[key] for key in ("row_count", "post_id_order_sha256", "post_id_set_sha256")}},
        "post_contract": {key: contract[key] for key in ("row_count", "post_id_order_sha256", "post_id_set_sha256")},
        "implementation_contract": _implementation_contract(),
        "approval_boundary": {"semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False, "runtime_validation": "NOT_RUN", "saved_artifact_only": True},
    }
    spec["run_spec_sha256"] = _canonical_hash(spec)
    return spec


def _assert_output_paths(paths: list[Path]) -> None:
    resolved = [path.resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("output paths must be distinct")
    if any(path.exists() for path in resolved):
        raise ValueError("refusing to overwrite existing output")


def write_run_spec(run_spec: dict[str, Any], output_path: str | Path) -> Path:
    output = _resolve_path(output_path)
    _assert_output_paths([output])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return output


def _validate_frozen_implementation_contract(implementation: Any) -> None:
    """Validate a historical implementation record without treating it as current code."""
    if not isinstance(implementation, dict) or not isinstance(implementation.get("artifacts"), dict):
        raise ValueError("implementation contract missing")
    artifacts = implementation["artifacts"]
    expected = {
        "harness_tool",
        "candidate_generation",
        "candidate_set_shadow",
        "candidate_audit",
        "agentic_pipeline",
    }
    if set(artifacts) != expected:
        raise ValueError("frozen implementation contract artifact set mismatch")
    hashes: dict[str, str] = {}
    for name in sorted(expected):
        ref = artifacts[name]
        if not isinstance(ref, dict):
            raise ValueError(f"frozen implementation ref missing: {name}")
        path, digest, size = ref.get("path"), ref.get("sha256"), ref.get("bytes")
        if not isinstance(path, str) or Path(path).is_absolute() or not path:
            raise ValueError(f"frozen implementation path invalid: {name}")
        if not isinstance(digest, str) or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"frozen implementation sha256 invalid: {name}")
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"frozen implementation bytes invalid: {name}")
        hashes[name] = digest
    if implementation.get("sha256") != _canonical_hash(hashes):
        raise ValueError("frozen implementation contract sha256 mismatch")


def validate_run_spec(
    run_spec_path: str | Path,
    *,
    verify_implementation: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    path = _resolve_path(run_spec_path)
    spec = _load_json(path)
    if not isinstance(spec, dict) or spec.get("schema_version") != RUN_SPEC_SCHEMA or spec.get("mode") != MODE:
        raise ValueError("unsupported P1 saved-artifact run spec")
    stored_hash = str(spec.get("run_spec_sha256") or "")
    if stored_hash != _canonical_hash({key: value for key, value in spec.items() if key != "run_spec_sha256"}):
        raise ValueError("run spec self hash mismatch")
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("run spec artifacts missing")
    paths = {name: _validate_artifact_ref(artifacts.get(name), name) for name in ("p0_parent_run_spec", "expected_audit", "label_ledger", "baseline_result")}
    parent, baseline_path, rows, contract = _validate_parent(paths["p0_parent_run_spec"])
    if baseline_path != paths["baseline_result"]:
        raise ValueError("P0 parent/bound baseline path mismatch")
    if _sha256_file(baseline_path) != artifacts["baseline_result"]["sha256"]:
        raise ValueError("P0 parent/bound baseline sha256 mismatch")
    _assert_contract(contract, spec.get("post_contract") if isinstance(spec.get("post_contract"), dict) else {}, "run spec post contract")
    parent_contract = spec.get("p0_parent")
    if not isinstance(parent_contract, dict) or parent_contract.get("run_spec_self_hash") != parent.get("run_spec_sha256") or parent_contract.get("baseline_result_sha256") != artifacts["baseline_result"]["sha256"]:
        raise ValueError("P0 parent binding mismatch")
    _assert_contract(contract, parent_contract.get("post_contract") if isinstance(parent_contract.get("post_contract"), dict) else {}, "P0 parent binding")
    implementation = spec.get("implementation_contract")
    if verify_implementation:
        hashes = {
            str(name): _sha256_file(_validate_artifact_ref(ref, f"implementation {name}"))
            for name, ref in implementation["artifacts"].items()
        }
        if implementation.get("sha256") != _canonical_hash(dict(sorted(hashes.items()))):
            raise ValueError("implementation contract sha256 mismatch")
    _validate_frozen_implementation_contract(implementation)
    audit = _load_json(paths["expected_audit"])
    ledger = _load_json(paths["label_ledger"])
    if not isinstance(audit, dict) or not isinstance(ledger, dict):
        raise ValueError("expected audit or label ledger invalid")
    audit_info = _verify_expected_audit(audit, artifacts["baseline_result"], contract)
    ledger_info = _verify_label_ledger(ledger, artifacts["expected_audit"], artifacts["baseline_result"], contract, audit_info["rows"])
    return spec, rows, {"audit": audit_info, "ledger": ledger_info}


def _shadow_row(row: dict[str, Any], label: dict[str, Any]) -> dict[str, Any]:
    before = _public_snapshot(row)
    identity = copy.deepcopy(_identity(row))
    # Frozen artifacts did not record exhaustive candidate generation.  Marking this
    # explicitly prevents a candidate-set recall percentage from being inferred.
    retained_sources = identity.get("candidate_preservation_sources")
    retained_sources = retained_sources if isinstance(retained_sources, list) else []
    generation_snapshot = build_candidate_generation_snapshot(retained_sources, cap=24)
    ledger = dict(identity.get("candidate_ledger") or {})
    ledger["candidate_generation"] = generation_snapshot.to_ledger_dict()
    identity["candidate_ledger"] = ledger
    audit_fields = apply_candidate_audit_fields(identity)
    identity.update(audit_fields)
    shadow_payload = identity.get("candidate_ledger", {}).get("candidate_set_shadow")
    if not isinstance(shadow_payload, dict):
        raise ValueError(f"post {_post_id(row)} candidate shadow payload missing")
    shadow = selective_shadow_from_dict(shadow_payload)
    direct_shadow = selective_shadow_from_identity(identity)
    if shadow.to_dict() != direct_shadow.to_dict():
        raise ValueError(f"post {_post_id(row)} stored/direct shadow mismatch")
    event_probabilities = [item.to_dict() for item in shadow.event_probabilities]
    labels = [item["label"] for item in event_probabilities]
    if labels.count(NIL_LABEL) != 1 or any(item["probability"] is not None for item in event_probabilities):
        raise ValueError(f"post {_post_id(row)} candidate/NIL probability contract invalid")
    candidate_set = shadow.candidate_set
    if candidate_set.generation_status != EXPECTED_GENERATION_STATUS or candidate_set.candidate_set_recall_status != EXPECTED_RECALL_STATUS:
        raise ValueError(f"post {_post_id(row)} generation/recall contract invalid")
    if candidate_set.integrity_status != "GO":
        raise ValueError(f"post {_post_id(row)} candidate-set integrity is not GO")
    after_row = copy.deepcopy(row)
    after_result = after_row.get("analysis_result")
    if not isinstance(after_result, dict):
        raise ValueError(f"post {_post_id(row)} analysis_result missing")
    after_result["identity"] = identity
    after = _public_snapshot(after_row)
    if before != after or _public_snapshot_hash(before) != _public_snapshot_hash(after):
        raise ValueError(f"post {_post_id(row)} public publication contract changed")
    expected_title = label.get("expected_title")
    candidate_titles = sorted(
        {
            title
            for item in candidate_set.candidates
            if item.event_eligible
            for title in item.titles
        }
    )
    return {
        "post_id": int(_post_id(row)) if _post_id(row).isdigit() else _post_id(row),
        "truth_kind": label.get("truth_kind"),
        "expected_title": expected_title,
        "candidate_generation": generation_snapshot.to_ledger_dict(),
        "candidate_set": {"candidate_count": len(candidate_set.candidates), "work_candidate_count": candidate_set.work_candidate_count, "unlinked_surface_count": candidate_set.unlinked_surface_count, "observed_late_surface_count": candidate_set.observed_late_surface_count, "event_candidate_count": candidate_set.event_candidate_count, "nil_label": candidate_set.nil_label, "generation_status": candidate_set.generation_status, "candidate_set_recall_status": candidate_set.candidate_set_recall_status, "integrity_status": candidate_set.integrity_status, "candidate_set_fingerprint": candidate_set.candidate_set_fingerprint, "observation_fingerprint": candidate_set.observation_fingerprint, "event_candidate_titles": candidate_titles},
        "candidate_nil_event": {"labels": labels, "probability_status": shadow.probability_status, "probabilities_all_null": True, "selected_label": shadow.selected_label, "action": shadow.action, "action_applied": shadow.action_applied, "abstain_is_probability_label": "ABSTAIN" in labels},
        "label_comparison": {"candidate_title_observed": expected_title in candidate_titles if isinstance(expected_title, str) else None, "recall_status": "NOT_EVALUABLE", "reason_ko": "후보 생성 완전성이 UNKNOWN이므로 CandidateSet recall을 계산하지 않았다."},
        "public_noninterference": {"before_sha256": _public_snapshot_hash(before), "after_sha256": _public_snapshot_hash(after), "unchanged": True, "official_title": before["official_title"], "official_url": before["official_url"], "promotion_decision": before["promotion_decision"], "publish_contract_trace": before["publish_contract_trace"], "publish_contract_input_fingerprint": before["publish_contract_input_fingerprint"]},
    }


def build_saved_artifact_comparison(
    run_spec_path: str | Path,
    *,
    verify_implementation: bool = True,
) -> dict[str, Any]:
    spec, rows, sources = validate_run_spec(
        run_spec_path,
        verify_implementation=verify_implementation,
    )
    labels = {str(row["post_id"]): row for row in sources["ledger"]["rows"]}
    result_rows = [_shadow_row(row, labels[_post_id(row)]) for row in rows]
    candidate_rows = [row for row in result_rows if row["truth_kind"] == "CANDIDATE"]
    nil_rows = [row for row in result_rows if row["truth_kind"] == "NIL"]
    unjudged_rows = [row for row in result_rows if row["truth_kind"] == "UNJUDGED"]
    observed_candidate_titles = sum(row["label_comparison"]["candidate_title_observed"] is True for row in candidate_rows)
    if observed_candidate_titles != len(candidate_rows):
        raise ValueError("exact candidate truth missing from saved CandidateSet")
    if any(NIL_LABEL not in row["candidate_nil_event"]["labels"] for row in nil_rows):
        raise ValueError("NIL truth row is missing the NIL event")
    totals = {key: sum(row["candidate_set"][key] for row in result_rows) for key in ("work_candidate_count", "unlinked_surface_count", "observed_late_surface_count", "event_candidate_count")}
    action_counts = dict(Counter(str(row["candidate_nil_event"]["action"]) for row in result_rows))
    return {
        "schema_version": REPORT_SCHEMA,
        "generated_at": _now(),
        "mode": MODE,
        "run_spec": {"path": _stored_path(_resolve_path(run_spec_path)), "sha256": _sha256_file(_resolve_path(run_spec_path)), "self_hash": spec["run_spec_sha256"]},
        "source_integrity": {"row_count": len(rows), "p0_parent_verified": True, "expected_audit_verified": True, "label_ledger_verified": True, "post_id_completeness": "GO"},
        "summary": {"candidate_set_integrity": {"go_rows": len(result_rows), "total_rows": len(result_rows)}, "candidate_nil_event_rows": len(result_rows), "candidate_truth": {"expected": len(candidate_rows), "exact_title_observed_in_event_space": observed_candidate_titles}, "nil_truth": {"expected": len(nil_rows), "nil_event_present": len(nil_rows)}, "unjudged": len(unjudged_rows), "all_probability_null": True, "all_selected_label_null": all(row["candidate_nil_event"]["selected_label"] is None for row in result_rows), "abstain_is_not_probability_label": all(not row["candidate_nil_event"]["abstain_is_probability_label"] for row in result_rows), "generation_status": EXPECTED_GENERATION_STATUS, "candidate_set_recall": "NOT_EVALUABLE", "public_contract_unchanged_rows": len(result_rows), "candidate_totals": totals, "action_counts": action_counts},
        "rows": result_rows,
        "gates": {"artifact_integrity": "GO", "p0_parent": "GO", "expected_audit_and_label_ledger": "GO", "post_id_completeness": "GO", "candidate_nil_event": "GO", "probability": "NOT_AVAILABLE_UNCALIBRATED", "candidate_set_recall": "NOT_EVALUABLE", "public_noninterference": "GO", "runtime_validation": "NOT_RUN", "semantic_quality": "REVIEW-LOCKED", "full_scan_approval": False, "overall": "GO_SAVED_ARTIFACT_SHADOW_ONLY"},
        "approval_boundary_ko": "Golden18 저장 산출물에서 CandidateSet/NIL shadow의 계약과 공개 판정 무영향만 확인했다. 실제 런타임, 확률 보정, CandidateSet recall 및 전체 스캔 승인은 수행하지 않았다.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    gates = report["gates"]
    summary = report["summary"]
    candidate_truth = summary["candidate_truth"]
    nil_truth = summary["nil_truth"]
    totals = summary["candidate_totals"]
    actions = ", ".join(
        f"{name} {count}건" for name, count in sorted(summary["action_counts"].items())
    )
    lines = [
        "# 여러 작품 후보와 ‘작품 없음’을 함께 다루는 P1 검증 보고서",
        "",
        "## 한눈에 보는 결론",
        "",
        "- **새 기능은 기존 공개 결과를 바꾸지 않았다.** Golden18 18건의 공개 작품명·주소·공개 판정·근거 추적 지문이 모두 그대로였다.",
        f"- **작품 후보 정답 9건은 모두 확률 사건 후보 안에서 관측됐다.** 다만 후보 생성 완전성이 `{summary['generation_status']}`이므로 후보 재현율 100%나 모델 정확도 100%라는 뜻은 아니다.",
        f"- **NIL 정답 원장 6행 모두에 공통 NIL 선택지가 존재했다.** NIL은 전체 18행에 선택지로 붙으므로, 이 6/6은 NIL 분류 정확도가 아니라 사건 공간 구조 검사다. 단일 정답을 만들 수 없는 {summary['unjudged']}건은 별도 미판정으로 남겼다.",
        "- **정확도 퍼센트는 아직 만들지 않았다.** 보정용·최종 시험용 정답셋이 없으므로 모든 확률은 `null`이고 상태는 `NOT_AVAILABLE_UNCALIBRATED`다.",
        f"- **검증 범위는 저장된 결과의 그림자 비교까지다.** 실제 새 런타임은 `{gates['runtime_validation']}`, 의미 품질은 `{gates['semantic_quality']}`, 운영 전체 승인은 `{str(gates['full_scan_approval']).lower()}`다.",
        "",
        "이 보고서의 P0/P1은 이번 구현 순서를 뜻한다. 상세 아키텍처의 `P0-1/P1-1`은 문제 우선순위 번호이므로 같은 분류가 아니다. 여기서는 각각 ‘검색 실패 차단 단계’, ‘후보/NIL 그림자 단계’로 읽는다.",
        "",
        "## 이 기능은 무엇을 하는가",
        "",
        "| 기능 | 쉬운 설명 | 이번 단계에서 한 일 |",
        "| --- | --- | --- |",
        "| 여러 작품 후보 묶음 (`CandidateSet`) | 작품 A와 B가 모두 가능하면 하나를 일찍 버리지 않고 함께 보존한다. | 저장된 각 게시글에서 작품 후보 사건을 다시 구성했다. |",
        "| 후보 중 정답 없음 (`NIL`) | 작품 이야기가 아니거나 준비된 후보 중 정답이 없을 가능성을 뜻한다. | 전체 18행의 후보 사건 목록 끝에 공통 선택지로 정확히 한 번 넣었다. |",
        "| 판단 보류 (`ABSTAIN`) | 검색 실패나 무결성 문제 때문에 지금 답하지 않는 운영 행동이다. 정답 종류가 아니다. | 후보/NIL 확률 목록에서 제외되는지 검사했다. |",
        "| 비사건 약칭 표면 (`UNLINKED_SURFACE`) | `아생갤` 같은 약칭을 잃지 않되 별도 작품으로 중복 계산하지 않는다. | 작품 후보와 분리해 근거로만 보존했다. |",
        "| 그림자 기록 (`shadow`) | 새 판단을 옆에 기록하되 사용자에게 보이는 결과에는 적용하지 않는다. | 기존 공개 계약 18건이 전부 불변인지 비교했다. |",
        "| 확률 보정 대기 | 80%라고 한 사례가 실제로도 약 80% 맞는지 시험하기 전에는 숫자를 내지 않는다. | 후보별 확률과 NIL 확률을 모두 `null`로 유지했다. |",
        "",
        "## 실제 저장본에서 확인한 결과",
        "",
        "| 확인 항목 | 결과 | 뜻 |",
        "| --- | ---: | --- |",
        f"| 게시글 ID 완전성 | {report['source_integrity']['row_count']}/18 | 누락·추가·중복 없이 같은 Golden18을 비교했다. |",
        f"| 후보 묶음 무결성 | {summary['candidate_set_integrity']['go_rows']}/{summary['candidate_set_integrity']['total_rows']} | 후보 ID·지문·원본 판정 재현 계약이 모두 맞았다. |",
        f"| 작품 후보 정답의 사건 후보 내 관측 | {candidate_truth['exact_title_observed_in_event_space']}/{candidate_truth['expected']} | 구조 검사는 통과했지만 후보 재현율 퍼센트는 아니다. |",
        f"| NIL 정답 원장 행의 공통 NIL 선택지 | {nil_truth['nil_event_present']}/{nil_truth['expected']} | 사건 공간 구조 검사이며 NIL 선택 능력·정확도 검증은 아니다. |",
        f"| 단일 정답 미지정 | {summary['unjudged']}건 | 복합 작품·미상 가설·이미지 단서는 억지 정답을 만들지 않았다. |",
        f"| 작품 후보 사건 | {totals['event_candidate_count']}개 | 향후 후보별 확률을 계산할 대상이다. |",
        f"| 비사건 약칭 표면 | {totals['unlinked_surface_count']}개 | 근거는 보존하지만 확률 사건에는 넣지 않았다. |",
        f"| 후반 관측 표면 | {totals['observed_late_surface_count']}개 | 권위 원천이 아니어서 확률 사건에서 제외했다. |",
        f"| 기존 공개 계약 불변 | {summary['public_contract_unchanged_rows']}/18 | 작품명·주소·판정·trace·fingerprint가 바뀌지 않았다. |",
        f"| 그림자 행동 | {actions} | 확률이 없으므로 작품 또는 NIL을 실제 선택하지 않았다. |",
        "",
        "## 왜 아직 정확도 퍼센트가 아닌가",
        "",
        f"후보 생성 상태가 `{summary['generation_status']}`이므로 후보 목록이 완전한지 알 수 없다. 따라서 후보 목록 재현율은 `{gates['candidate_set_recall']}`이다. 기대 제목 9건이 현재 후보 안에 보였다는 사실은 유용한 구조 검사지만, 고정 최종 평가셋의 정확도나 재현율로 바꿔 쓰면 안 된다.",
        "",
        "퍼센트를 표시하려면 후보 생성 시점부터 `COMPLETE(완전)/TRUNCATED(잘림)/UNKNOWN(알 수 없음)`을 정확히 기록하고, 개발·확률 보정·최종 동결 시험셋을 겹치지 않게 나눈 뒤 ECE·Brier·risk-coverage를 측정해야 한다. 먼저 정답 작품이 후보 목록에 들어오는지 확인하고, ECE·Brier·log loss로 말한 퍼센트와 실제 적중률이 얼마나 맞는지 검사한다. 마지막으로 risk-coverage로 자동 처리 비율을 늘릴 때 오답 위험이 얼마나 커지는지 확인한다. ECE는 퍼센트와 실제 적중률의 간격, Brier와 log loss는 틀린 확률 예측에 주는 벌점이며 낮을수록 좋다. 그 전까지 `null`은 누락이 아니라 과신을 막는 안전 상태다.",
        "",
        "## 게시글별 그림자 결과",
        "",
        "| 게시글 번호 | 정답 원장 | 전체 보존 항목 | 작품 후보 사건 | 비사건 약칭 | 후반 관측 | NIL | 확률 | 공개 결과 |",
        "| ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in report["rows"]:
        event = row["candidate_nil_event"]
        candidate_set = row["candidate_set"]
        lines.append(
            f"| `{row['post_id']}` | `{row['truth_kind']}` | {candidate_set['candidate_count']} | "
            f"{candidate_set['event_candidate_count']} | {candidate_set['unlinked_surface_count']} | "
            f"{candidate_set['observed_late_surface_count']} | "
            f"{'있음' if NIL_LABEL in event['labels'] else '없음'} | `null` | 불변 |"
        )
    lines.extend(
        [
            "",
            "## 게이트 상태를 한국어로 읽기",
            "",
            "| 게이트 | 상태 | 뜻 |",
            "| --- | --- | --- |",
            f"| 산출물·게시글 무결성 | `{gates['artifact_integrity']}` | SHA와 게시글 순서·집합이 봉인된 입력과 일치한다. |",
            f"| 부모 P0 저장본 계약 | `{gates['p0_parent']}` | 앞 단계 RunSpec과 저장본 계약의 연결만 재검증했다. 검색 복구나 실제 runtime 통과를 뜻하지 않는다. |",
            f"| 후보/NIL 구조 | `{gates['candidate_nil_event']}` | 후보 사건 뒤 NIL 하나, ABSTAIN은 사건에서 제외됐다. |",
            f"| 정확도 퍼센트 | `{gates['probability']}` | 보정 전이라 숫자를 만들지 않았다. |",
            f"| 후보 목록 재현율 | `{gates['candidate_set_recall']}` | 후보 생성 완전성이 UNKNOWN이라 평가할 수 없다. |",
            f"| 공개 결과 무영향 | `{gates['public_noninterference']}` | 기존 공개 작품명·주소·판정·추적 지문이 모두 불변이다. |",
            f"| 실제 새 실행 | `{gates['runtime_validation']}` | 저장본 비교만 했고 새 LLM/MCP 런은 시작하지 않았다. |",
            f"| 의미 품질 | `{gates['semantic_quality']}` | 전체 작품 판정 품질은 아직 승인하지 않았다. |",
            f"| 운영 전체 승인 | `{str(gates['full_scan_approval']).lower()}` | 전수 운영 GO가 아니다. |",
            f"| 이번 단계 종합 | `{gates['overall']}` | 저장본 그림자 구조와 무영향 검증만 통과했다. |",
            "",
            "## 근거 산출물",
            "",
            f"- P1 실행 명세: `{report['run_spec']['path']}`",
            f"- 실행 명세 파일 지문: `{report['run_spec']['sha256']}`",
            f"- 실행 명세 자체 지문: `{report['run_spec']['self_hash']}`",
            "- 정답 원장: `docs/devs/p1_candidate_set_nil_golden18_label_ledger_20260711.json`",
            "- 상세 기능 설명: `docs/devs/LLM_PIPELINE_IMPROVEMENT_READER_GUIDE_KO_20260711.md`",
            "",
            report["approval_boundary_ko"],
            "",
        ]
    )
    return "\n".join(lines)


def write_comparison(report: dict[str, Any], *, output_json: str | Path, output_md: str | Path) -> tuple[Path, Path]:
    json_path, md_path = _resolve_path(output_json), _resolve_path(output_md)
    _assert_output_paths([json_path, md_path])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, md_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CandidateSet/NIL shadow against frozen Golden18 artifacts.")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Create an immutable P1 saved-artifact RunSpec.")
    freeze.add_argument("--parent-p0-run-spec", required=True)
    freeze.add_argument("--expected-audit", required=True)
    freeze.add_argument("--label-ledger", required=True)
    freeze.add_argument("--output", required=True)
    compare = commands.add_parser("compare", help="Build the non-mutating shadow comparison.")
    compare.add_argument("--run-spec", required=True)
    compare.add_argument("--output-json", required=True)
    compare.add_argument("--output-md", required=True)
    status = commands.add_parser("status", help="Validate a P1 RunSpec without writing outputs.")
    status.add_argument("--run-spec", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "freeze":
        spec = create_run_spec(parent_p0_run_spec_path=args.parent_p0_run_spec, expected_audit_path=args.expected_audit, label_ledger_path=args.label_ledger)
        output = write_run_spec(spec, args.output)
        print(json.dumps({"gate": "GO", "mode": MODE, "output": _stored_path(output), "run_spec_sha256": spec["run_spec_sha256"]}, ensure_ascii=False))
        return 0
    if args.command == "status":
        spec, rows, _ = validate_run_spec(args.run_spec)
        print(json.dumps({"gate": "GO", "mode": spec["mode"], "row_count": len(rows), "runtime_validation": "NOT_RUN"}, ensure_ascii=False))
        return 0
    report = build_saved_artifact_comparison(args.run_spec)
    json_path, md_path = write_comparison(report, output_json=args.output_json, output_md=args.output_md)
    print(json.dumps({"gate": report["gates"]["overall"], "output_json": _stored_path(json_path), "output_md": _stored_path(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
