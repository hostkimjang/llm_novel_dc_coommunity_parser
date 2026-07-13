from __future__ import annotations

import argparse
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

from src.llm_batch.promotion_gate import (
    can_publish_title,
    evidence_records_from_payload,
    grounding_state_from_dict,
)


RUN_SPEC_SCHEMA = "pipeline-improvement-runspec-v2"
REPORT_SCHEMA = "pipeline-improvement-static-projection-v2"
TREATMENT = "required-search-unrecovered-failclose-v2"
STATIC_MODE = "STATIC_PROJECTION_NO_RUNTIME"
PROBABILITY_STATUS = "NOT_AVAILABLE_UNCALIBRATED"


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
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def _stored_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _artifact_ref(path: str | Path) -> dict[str, Any]:
    resolved = _resolve_path(path)
    if not resolved.is_file():
        raise ValueError(f"artifact missing: {resolved}")
    return {
        "path": _stored_path(resolved),
        "sha256": _sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"expected object at {path}:{line_no}")
                rows.append(value)
        return rows

    value = _load_json(path)
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = value.get("rows") or value.get("results") or value.get("data")
    else:
        rows = None
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"expected JSON row list: {path}")
    return rows


def _post_id(row: dict[str, Any]) -> str:
    value = row.get("post_id")
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("row is missing post_id")
    return text


def _post_contract(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    post_ids = [_post_id(row) for row in rows]
    duplicates = sorted(post_id for post_id, count in Counter(post_ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"{label} duplicate post_id: {','.join(duplicates)}")
    return {
        "row_count": len(rows),
        "post_id_order_sha256": _canonical_hash(post_ids),
        "post_id_set_sha256": _canonical_hash(sorted(post_ids)),
        "post_ids": post_ids,
    }


def _assert_same_post_contract(
    left: dict[str, Any],
    right: dict[str, Any],
    left_label: str,
    right_label: str,
) -> None:
    for field in ("row_count", "post_id_order_sha256", "post_id_set_sha256"):
        if left.get(field) != right.get(field):
            raise ValueError(f"{left_label}/{right_label} {field} mismatch")


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis_result = row.get("analysis_result")
    if not isinstance(analysis_result, dict):
        return {}
    identity = analysis_result.get("identity")
    return identity if isinstance(identity, dict) else {}


def _public_state(row: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    novel_identity = identity.get("novel_identity")
    if not isinstance(novel_identity, dict):
        novel_identity = {}
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = {}
    trace = identity.get("publish_contract_trace")
    if not isinstance(trace, dict):
        trace = ledger.get("publish_contract_trace")
    if not isinstance(trace, dict):
        trace = {}

    def first_text(*values: Any) -> str | None:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None

    return {
        "official_title": first_text(
            novel_identity.get("official_title"),
            novel_identity.get("official_novel_title"),
            novel_identity.get("resolved_title"),
            identity.get("official_title"),
            identity.get("official_novel_title"),
            identity.get("resolved_title"),
            decision.get("official_title"),
        ),
        "official_url": first_text(
            novel_identity.get("official_url"),
            novel_identity.get("heretic_url"),
            novel_identity.get("resolved_url"),
            identity.get("official_url"),
            identity.get("heretic_url"),
            identity.get("resolved_url"),
            decision.get("official_url"),
        ),
        "publish_allowed": decision.get("publish_allowed"),
        "candidate_preserved": decision.get("candidate_preserved"),
        "decision_bypassed_gate": decision.get("bypassed_gate"),
        "trace_bypassed_gate": trace.get("bypassed_gate"),
        "decision": decision,
        "trace": trace,
    }


def _candidate_material_available(row: dict[str, Any], public: dict[str, Any]) -> bool:
    if public.get("official_title") or public.get("official_url"):
        return True

    identity = _identity(row)
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    state = identity.get("promotion_gate_state")
    if not isinstance(state, dict):
        state = ledger.get("promotion_gate_state")
    if isinstance(state, dict) and (
        str(state.get("candidate_title") or "").strip()
        or str(state.get("candidate_url") or "").strip()
    ):
        return True
    evidence = identity.get("promotion_gate_evidence")
    if not isinstance(evidence, list):
        evidence = ledger.get("promotion_gate_evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            if str(item.get("candidate_title") or "").strip() or str(
                item.get("candidate_url") or ""
            ).strip():
                return True

    for field in ("title_candidates", "mentioned_works", "secondary_reference_works"):
        value = identity.get(field)
        if isinstance(value, list) and value:
            return True
    primary = identity.get("primary_work")
    if isinstance(primary, dict) and any(str(value or "").strip() for value in primary.values()):
        return True
    return False


def _promotion_inputs(row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    identity = _identity(row)
    ledger = identity.get("candidate_ledger")
    if not isinstance(ledger, dict):
        ledger = {}
    state = identity.get("promotion_gate_state")
    if not isinstance(state, dict):
        state = ledger.get("promotion_gate_state")
    evidence = identity.get("promotion_gate_evidence")
    if not isinstance(evidence, list):
        evidence = ledger.get("promotion_gate_evidence")
    if not isinstance(state, dict):
        raise ValueError(f"post {_post_id(row)} is missing promotion_gate_state")
    if not isinstance(evidence, list):
        raise ValueError(f"post {_post_id(row)} is missing promotion_gate_evidence")
    return dict(state), evidence


def _gate_replay(
    row: dict[str, Any], retrieval_payload: dict[str, Any] | None
) -> dict[str, Any]:
    state_payload, evidence_payload = _promotion_inputs(row)
    if retrieval_payload is None:
        state_payload.pop("retrieval", None)
    else:
        state_payload["retrieval"] = retrieval_payload
    state = grounding_state_from_dict(state_payload)
    evidence = evidence_records_from_payload(evidence_payload)
    decision = can_publish_title(state, evidence)
    return decision.to_dict()


def _typed_failclose_projection(
    row: dict[str, Any], blocker: dict[str, Any]
) -> dict[str, Any]:
    payload = _gate_replay(
        row,
        {
            "required": True,
            "attempted": True,
            "recovered": False,
            "hard_blocked": False,
            "reason_codes": [
                str(item)
                for item in (blocker.get("search_health_issues") or [])
                if str(item).strip()
            ],
        },
    )
    reason_codes = set(payload.get("reason_codes") or [])
    if not reason_codes.intersection({"search_evidence_missing", "search_blind_condition"}):
        raise ValueError(f"post {_post_id(row)} typed retrieval state did not reach publish gate")
    return payload


def _implementation_contract() -> dict[str, Any]:
    refs = {
        "harness_tool": _artifact_ref(Path(__file__)),
        "promotion_gate": _artifact_ref(ROOT / "src/llm_batch/promotion_gate.py"),
    }
    return {
        "artifacts": refs,
        "sha256": _canonical_hash(
            {name: ref["sha256"] for name, ref in sorted(refs.items())}
        ),
    }


def _public_identity_hash(public: dict[str, Any]) -> str | None:
    title = str(public.get("official_title") or "").strip()
    url = str(public.get("official_url") or "").strip()
    if not title and not url:
        return None
    return _canonical_hash({"official_title": title or None, "official_url": url or None})


def _public_exposed(public: dict[str, Any]) -> bool:
    return bool(
        public.get("publish_allowed") is True
        or str(public.get("official_title") or "").strip()
        or str(public.get("official_url") or "").strip()
    )


def _load_active_snapshot(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "manifest_path": None,
            "observed": False,
            "run_id": None,
            "large_run_complete": None,
            "runtime_execution_allowed": False,
        }
    if not path.is_file():
        raise ValueError(f"active manifest missing: {path}")
    manifest = _load_json(path)
    if not isinstance(manifest, dict):
        raise ValueError(f"active manifest must be an object: {path}")
    return {
        "manifest_path": _stored_path(path),
        "observed": True,
        "run_id": manifest.get("run_id"),
        "input_post_count": manifest.get("input_post_count"),
        "completed_count": manifest.get("completed_count"),
        "flushed_count": manifest.get("flushed_count"),
        "pending_count": manifest.get("pending_count"),
        "failed_count": manifest.get("failed_count"),
        "large_run_complete": manifest.get("large_run_complete"),
        "requested_parallel": manifest.get("requested_parallel"),
        "effective_parallel": manifest.get("effective_parallel"),
        "runtime_execution_allowed": False,
        "reason": "active production run is read-only; this harness phase is static only",
    }


def _active_manifest_from_spec(run_spec: dict[str, Any]) -> Path | None:
    active = run_spec.get("active_production_run")
    if not isinstance(active, dict):
        return None
    path_text = active.get("manifest_path")
    return _resolve_path(path_text) if path_text else None


def _assert_output_noninterference(
    output_paths: list[Path], active_manifest: Path | None
) -> None:
    resolved_outputs = [path.resolve() for path in output_paths]
    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise ValueError("output paths must be distinct")
    for path in resolved_outputs:
        if path.exists():
            raise ValueError(f"refusing to overwrite existing output: {path}")

    if active_manifest is None:
        return
    active_manifest = active_manifest.resolve()
    suffix = "_manifest.json"
    prefix_name = (
        active_manifest.name[: -len(suffix)]
        if active_manifest.name.endswith(suffix)
        else active_manifest.stem
    )
    for path in resolved_outputs:
        if path == active_manifest:
            raise ValueError("output overlaps active production manifest")
        if path.parent == active_manifest.parent and path.name.startswith(prefix_name):
            raise ValueError("output overlaps active production result prefix")


def _gate_blockers(gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = gate.get("required_search_hard_blocker_rows")
    if not isinstance(rows, list):
        raise ValueError("retrieval gate is missing required_search_hard_blocker_rows")
    blockers: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("retrieval blocker row must be an object")
        post_id = _post_id(row)
        if post_id in blockers:
            raise ValueError(f"retrieval gate duplicate post_id: {post_id}")
        unrecovered = int(row.get("unrecovered_degraded") or 0)
        if unrecovered <= 0 or row.get("publish_dependency") is not True:
            raise ValueError(f"retrieval blocker contract invalid: {post_id}")
        blockers[post_id] = row
    expected = gate.get("required_search_hard_blocker")
    if expected is not None and int(expected) != len(blockers):
        raise ValueError("retrieval blocker count mismatch")
    return blockers


def _validate_gate_provenance(
    gate: dict[str, Any],
    baseline_ref: dict[str, Any],
    manifest_ref: dict[str, Any],
) -> None:
    provenance = gate.get("artifact_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("retrieval gate artifact provenance missing")
    for label, expected_ref in (
        ("result", baseline_ref),
        ("manifest", manifest_ref),
    ):
        ref = provenance.get(label)
        if not isinstance(ref, dict):
            raise ValueError(f"retrieval gate {label} provenance missing")
        path_text = str(ref.get("path") or "").strip()
        expected_hash = str(ref.get("sha256") or "").strip().lower()
        if not path_text or _stored_path(_resolve_path(path_text)) != expected_ref.get("path"):
            raise ValueError(f"retrieval gate {label} path mismatch")
        if expected_hash != expected_ref.get("sha256"):
            raise ValueError(f"retrieval gate {label} sha256 mismatch")


def _validate_baseline_runtime_contract(
    *,
    input_ref: dict[str, Any],
    baseline_ref: dict[str, Any],
    manifest_ref: dict[str, Any],
    runtime_plan_ref: dict[str, Any],
    integrity_ref: dict[str, Any],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    manifest = _load_json(_resolve_path(manifest_ref["path"]))
    runtime_plan = _load_json(_resolve_path(runtime_plan_ref["path"]))
    integrity = _load_json(_resolve_path(integrity_ref["path"]))
    if not all(isinstance(value, dict) for value in (manifest, runtime_plan, integrity)):
        raise ValueError("baseline runtime artifacts must be JSON objects")

    row_count = len(baseline_rows)
    expected_counts = {
        "input_post_count": row_count,
        "completed_count": row_count,
        "flushed_count": row_count,
        "pending_count": 0,
        "failed_count": 0,
    }
    for field, expected in expected_counts.items():
        if int(manifest.get(field) or 0) != expected:
            raise ValueError(f"baseline manifest {field} mismatch")
    if manifest.get("large_run_complete") is not True:
        raise ValueError("baseline manifest is not complete")

    integrity_counts = integrity.get("counts")
    if not isinstance(integrity_counts, dict):
        raise ValueError("baseline integrity counts missing")
    for field, expected in {
        "input": row_count,
        "result": row_count,
        "checkpoint": row_count,
        "pending": 0,
        "failed": 0,
        "missing": 0,
        "extra": 0,
        "duplicate": 0,
    }.items():
        if int(integrity_counts.get(field) or 0) != expected:
            raise ValueError(f"baseline integrity {field} mismatch")
    if integrity.get("runtime_integrity_gate") != "GO":
        raise ValueError("baseline runtime integrity gate is not GO")

    artifact_hashes = integrity.get("artifact_sha256")
    if not isinstance(artifact_hashes, dict):
        raise ValueError("baseline integrity artifact hashes missing")
    for field, ref in {
        "input": input_ref,
        "result": baseline_ref,
        "manifest": manifest_ref,
    }.items():
        if artifact_hashes.get(field) != ref.get("sha256"):
            raise ValueError(f"baseline integrity {field} sha256 mismatch")

    source_input = runtime_plan.get("source_input")
    output_contract = runtime_plan.get("output_contract")
    plan_contract = runtime_plan.get("runtime_contract")
    integrity_contract = integrity.get("runtime_contract")
    if not all(
        isinstance(value, dict)
        for value in (source_input, output_contract, plan_contract, integrity_contract)
    ):
        raise ValueError("baseline runtime plan contract missing")
    if source_input.get("sha256") != input_ref.get("sha256"):
        raise ValueError("baseline runtime plan input sha256 mismatch")
    if _stored_path(_resolve_path(output_contract.get("output_json") or "")) != baseline_ref.get(
        "path"
    ):
        raise ValueError("baseline runtime plan result path mismatch")
    if _stored_path(_resolve_path(output_contract.get("manifest_json") or "")) != manifest_ref.get(
        "path"
    ):
        raise ValueError("baseline runtime plan manifest path mismatch")

    first_meta = baseline_rows[0].get("run_meta") if baseline_rows else None
    if not isinstance(first_meta, dict):
        raise ValueError("baseline result run_meta missing")
    runtime_meta_fields = (
        "runtime_release_fingerprint_sha256",
        "run_id",
        "model",
        "llm_endpoint",
        "prompt_version",
        "config_hash",
        "requested_parallel",
        "effective_parallel",
        "mcp_health_include_search",
        "mcp_health_light_mode",
    )
    first_meta_contract = {field: first_meta.get(field) for field in runtime_meta_fields}
    for row in baseline_rows:
        meta = row.get("run_meta")
        if not isinstance(meta, dict):
            raise ValueError(f"baseline post {_post_id(row)} run_meta missing")
        row_contract = {field: meta.get(field) for field in runtime_meta_fields}
        if row_contract != first_meta_contract:
            raise ValueError(f"baseline post {_post_id(row)} mixed runtime metadata")
    run_id = str(manifest.get("run_id") or "")
    if not run_id or run_id != str(first_meta.get("run_id") or "") or run_id != str(
        integrity.get("run_id") or ""
    ):
        raise ValueError("baseline run_id mismatch")
    fingerprint = str(runtime_plan.get("runtime_release_fingerprint_sha256") or "")
    if not fingerprint or fingerprint != str(
        first_meta.get("runtime_release_fingerprint_sha256") or ""
    ) or fingerprint != str(
        manifest.get("runtime_release_fingerprint_sha256") or ""
    ) or fingerprint != str(integrity.get("runtime_release_fingerprint_sha256") or ""):
        raise ValueError("baseline runtime fingerprint mismatch")

    comparisons = {
        "model": (
            first_meta.get("model"),
            manifest.get("llm_model"),
            plan_contract.get("model"),
            integrity_contract.get("model"),
        ),
        "endpoint": (
            first_meta.get("llm_endpoint"),
            manifest.get("llm_endpoint"),
            plan_contract.get("endpoint"),
        ),
        "requested_parallel": (
            first_meta.get("requested_parallel"),
            manifest.get("requested_parallel"),
            plan_contract.get("requested_parallel"),
            integrity_contract.get("requested_parallel"),
        ),
        "effective_parallel": (
            first_meta.get("effective_parallel"),
            manifest.get("effective_parallel"),
            plan_contract.get("effective_parallel_expected"),
            integrity_contract.get("effective_parallel"),
        ),
        "search_include": (
            first_meta.get("mcp_health_include_search"),
            manifest.get("mcp_health_include_search"),
            plan_contract.get("search_include"),
            integrity_contract.get("search_include"),
        ),
        "search_light_mode": (
            first_meta.get("mcp_health_light_mode"),
            manifest.get("mcp_health_light_mode"),
            plan_contract.get("search_light_mode"),
            integrity_contract.get("search_light_mode"),
        ),
        "vlm_enabled": (
            manifest.get("vlm_enabled"),
            plan_contract.get("vlm") == "on",
            integrity_contract.get("vlm_enabled"),
        ),
        "ocr_enabled": (
            manifest.get("ocr_enabled"),
            plan_contract.get("ocr") == "on",
            integrity_contract.get("ocr_enabled"),
        ),
    }
    for field, values in comparisons.items():
        if any(value is None for value in values) or len({_canonical_json(value) for value in values}) != 1:
            raise ValueError(f"baseline runtime contract mismatch: {field}")
    if int(plan_contract.get("requested_parallel") or 0) != 16:
        raise ValueError("baseline runtime requested_parallel must be 16")
    if plan_contract.get("dashboard_required") is not True or manifest.get(
        "dashboard_enabled"
    ) is not True:
        raise ValueError("baseline dashboard contract mismatch")
    if plan_contract.get("slang_db") != "off" or integrity_contract.get(
        "slang_db_requested"
    ) != "off":
        raise ValueError("baseline slang DB contract mismatch")
    if integrity_contract.get("healthy_shards") != "16/16":
        raise ValueError("baseline healthy search shard contract mismatch")
    if integrity_contract.get("vlm_ocr_ready") is not True:
        raise ValueError("baseline VLM/OCR readiness contract mismatch")
    if str(first_meta.get("prompt_version") or "") != str(
        plan_contract.get("prompt_version") or ""
    ):
        raise ValueError("baseline prompt version mismatch")
    if not str(first_meta.get("config_hash") or "").strip():
        raise ValueError("baseline config hash missing")

    return {
        "run_id": run_id,
        "runtime_release_fingerprint_sha256": fingerprint,
        "model": first_meta.get("model"),
        "endpoint": first_meta.get("llm_endpoint"),
        "prompt_version": first_meta.get("prompt_version"),
        "config_hash": first_meta.get("config_hash"),
        "requested_parallel": 16,
        "effective_parallel": int(first_meta.get("effective_parallel") or 0),
        "dashboard_enabled": True,
        "search_include": True,
        "search_light_mode": False,
        "healthy_search_shards": integrity_contract.get("healthy_shards"),
        "vlm_enabled": True,
        "ocr_enabled": True,
        "vlm_ocr_ready": integrity_contract.get("vlm_ocr_ready"),
        "slang_db": "off",
        "runtime_integrity_gate": integrity.get("runtime_integrity_gate"),
    }


def create_run_spec(
    *,
    input_path: str | Path,
    baseline_path: str | Path,
    baseline_manifest_path: str | Path,
    runtime_plan_path: str | Path,
    integrity_artifact_path: str | Path,
    retrieval_gate_path: str | Path,
    active_manifest_path: str | Path | None = None,
    runtime_parallel: int = 16,
) -> dict[str, Any]:
    if runtime_parallel != 16:
        raise ValueError("future runtime contract requires --runtime-parallel 16")

    input_ref = _artifact_ref(input_path)
    baseline_ref = _artifact_ref(baseline_path)
    baseline_manifest_ref = _artifact_ref(baseline_manifest_path)
    runtime_plan_ref = _artifact_ref(runtime_plan_path)
    integrity_ref = _artifact_ref(integrity_artifact_path)
    retrieval_ref = _artifact_ref(retrieval_gate_path)
    input_rows = _load_rows(_resolve_path(input_ref["path"]))
    baseline_rows = _load_rows(_resolve_path(baseline_ref["path"]))
    input_contract = _post_contract(input_rows, "input")
    baseline_contract = _post_contract(baseline_rows, "baseline")
    _assert_same_post_contract(input_contract, baseline_contract, "input", "baseline")

    gate = _load_json(_resolve_path(retrieval_ref["path"]))
    if not isinstance(gate, dict):
        raise ValueError("retrieval gate must be a JSON object")
    blockers = _gate_blockers(gate)
    missing_blockers = sorted(set(blockers) - set(baseline_contract["post_ids"]))
    if missing_blockers:
        raise ValueError(f"retrieval blocker absent from baseline: {','.join(missing_blockers)}")
    if gate.get("row_count") is not None and int(gate["row_count"]) != len(baseline_rows):
        raise ValueError("retrieval gate row_count mismatch")
    _validate_gate_provenance(gate, baseline_ref, baseline_manifest_ref)
    baseline_runtime_contract = _validate_baseline_runtime_contract(
        input_ref=input_ref,
        baseline_ref=baseline_ref,
        manifest_ref=baseline_manifest_ref,
        runtime_plan_ref=runtime_plan_ref,
        integrity_ref=integrity_ref,
        baseline_rows=baseline_rows,
    )

    active_path = _resolve_path(active_manifest_path) if active_manifest_path else None
    active_snapshot = _load_active_snapshot(active_path)
    spec: dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA,
        "generated_at": _now(),
        "mode": STATIC_MODE,
        "treatment": TREATMENT,
        "artifacts": {
            "input": input_ref,
            "baseline_result": baseline_ref,
            "baseline_manifest": baseline_manifest_ref,
            "runtime_plan": runtime_plan_ref,
            "integrity_artifact": integrity_ref,
            "retrieval_gate": retrieval_ref,
        },
        "post_contract": {
            "row_count": input_contract["row_count"],
            "post_id_order_sha256": input_contract["post_id_order_sha256"],
            "post_id_set_sha256": input_contract["post_id_set_sha256"],
        },
        "retrieval_contract": {
            "required_search_hard_blocker": len(blockers),
            "source_gate": gate.get("gate"),
        },
        "implementation_contract": _implementation_contract(),
        "baseline_runtime_contract": baseline_runtime_contract,
        "future_runtime_contract": {
            "requested_parallel": 16,
            "dashboard_required": True,
            "slang_db": "off_or_read_only_snapshot",
            "separate_output_prefix": True,
            "runtime_executed_in_this_phase": False,
        },
        "active_production_run": active_snapshot,
        "approval_boundary": {
            "semantic_quality": "REVIEW-LOCKED",
            "full_scan_approval": False,
            "static_projection_is_runtime_evidence": False,
            "dashboard_is_approval": False,
        },
    }
    spec["run_spec_sha256"] = _canonical_hash(spec)
    return spec


def write_run_spec(run_spec: dict[str, Any], output_path: str | Path) -> Path:
    output = _resolve_path(output_path)
    _assert_output_noninterference([output], _active_manifest_from_spec(run_spec))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def validate_run_spec(run_spec_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    path = _resolve_path(run_spec_path)
    run_spec = _load_json(path)
    if not isinstance(run_spec, dict) or run_spec.get("schema_version") != RUN_SPEC_SCHEMA:
        raise ValueError("unsupported run spec schema")
    expected_hash = str(run_spec.get("run_spec_sha256") or "")
    payload = {key: value for key, value in run_spec.items() if key != "run_spec_sha256"}
    if expected_hash != _canonical_hash(payload):
        raise ValueError("run spec self hash mismatch")
    if run_spec.get("mode") != STATIC_MODE or run_spec.get("treatment") != TREATMENT:
        raise ValueError("run spec mode or treatment mismatch")

    artifacts = run_spec.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("run spec artifacts missing")
    loaded_paths: dict[str, Path] = {}
    for name in (
        "input",
        "baseline_result",
        "baseline_manifest",
        "runtime_plan",
        "integrity_artifact",
        "retrieval_gate",
    ):
        ref = artifacts.get(name)
        if not isinstance(ref, dict):
            raise ValueError(f"run spec artifact missing: {name}")
        artifact_path = _resolve_path(str(ref.get("path") or ""))
        if not artifact_path.is_file():
            raise ValueError(f"run spec artifact missing on disk: {name}")
        if _sha256_file(artifact_path) != ref.get("sha256"):
            raise ValueError(f"run spec artifact sha256 mismatch: {name}")
        loaded_paths[name] = artifact_path

    implementation = run_spec.get("implementation_contract")
    if not isinstance(implementation, dict) or not isinstance(
        implementation.get("artifacts"), dict
    ):
        raise ValueError("run spec implementation contract missing")
    implementation_hashes: dict[str, str] = {}
    for name, ref in implementation["artifacts"].items():
        if not isinstance(ref, dict):
            raise ValueError(f"implementation artifact invalid: {name}")
        artifact_path = _resolve_path(str(ref.get("path") or ""))
        if not artifact_path.is_file():
            raise ValueError(f"implementation artifact missing: {name}")
        actual_hash = _sha256_file(artifact_path)
        if actual_hash != ref.get("sha256"):
            raise ValueError(f"implementation artifact sha256 mismatch: {name}")
        implementation_hashes[str(name)] = actual_hash
    if _canonical_hash(dict(sorted(implementation_hashes.items()))) != implementation.get(
        "sha256"
    ):
        raise ValueError("implementation contract sha256 mismatch")

    input_rows = _load_rows(loaded_paths["input"])
    baseline_rows = _load_rows(loaded_paths["baseline_result"])
    input_contract = _post_contract(input_rows, "input")
    baseline_contract = _post_contract(baseline_rows, "baseline")
    _assert_same_post_contract(input_contract, baseline_contract, "input", "baseline")
    stored_contract = run_spec.get("post_contract")
    if not isinstance(stored_contract, dict):
        raise ValueError("run spec post contract missing")
    for field in ("row_count", "post_id_order_sha256", "post_id_set_sha256"):
        if input_contract[field] != stored_contract.get(field):
            raise ValueError(f"run spec post contract drift: {field}")

    gate = _load_json(loaded_paths["retrieval_gate"])
    if not isinstance(gate, dict):
        raise ValueError("retrieval gate must be an object")
    blockers = _gate_blockers(gate)
    if set(blockers) - set(input_contract["post_ids"]):
        raise ValueError("retrieval blocker absent from frozen input")
    _validate_gate_provenance(
        gate,
        artifacts["baseline_result"],
        artifacts["baseline_manifest"],
    )
    baseline_runtime_contract = _validate_baseline_runtime_contract(
        input_ref=artifacts["input"],
        baseline_ref=artifacts["baseline_result"],
        manifest_ref=artifacts["baseline_manifest"],
        runtime_plan_ref=artifacts["runtime_plan"],
        integrity_ref=artifacts["integrity_artifact"],
        baseline_rows=baseline_rows,
    )
    if baseline_runtime_contract != run_spec.get("baseline_runtime_contract"):
        raise ValueError("baseline runtime contract drift")
    return run_spec, baseline_rows, gate


def build_static_projection(run_spec_path: str | Path) -> dict[str, Any]:
    run_spec, baseline_rows, gate = validate_run_spec(run_spec_path)
    blockers = _gate_blockers(gate)

    before_unsafe = 0
    after_unsafe = 0
    before_public_target = 0
    after_public_target = 0
    decision_changed = 0
    decision_status_changed = 0
    public_output_changed = 0
    candidate_missing_after = 0
    baseline_gate_replay_exact = 0
    rows_out: list[dict[str, Any]] = []

    for row in baseline_rows:
        post_id = _post_id(row)
        blocker = blockers.get(post_id)
        before = _public_state(row)
        before_exposed = _public_exposed(before)
        candidate_before = _candidate_material_available(row, before)
        before_status = None
        if isinstance(before.get("decision"), dict):
            before_status = before["decision"].get("status")

        targeted = blocker is not None
        if targeted:
            before_public_target += int(before_exposed)
            before_unsafe += int(before_exposed)
            stored_decision = (
                before.get("decision") if isinstance(before.get("decision"), dict) else {}
            )
            baseline_replay = _gate_replay(row, None)
            if _canonical_hash(stored_decision) != _canonical_hash(baseline_replay):
                raise ValueError(
                    f"post {post_id} current gate does not reproduce frozen baseline decision"
                )
            baseline_gate_replay_exact += 1
            after = _typed_failclose_projection(row, blocker)
            after_exposed = _public_exposed(after)
            decision_changed += int(_canonical_hash(stored_decision) != _canonical_hash(after))
            decision_status_changed += int(before_status != after["status"])
            public_output_changed += int(before_exposed != after_exposed)
            candidate_missing_after += int(
                not (candidate_before and after.get("candidate_preserved") is True)
            )
            classification = (
                "안전 개선: 검색 미복구 공개를 정보 부족 보류로 변경"
                if before_exposed
                else "기존 비공개 유지: 검색 근거는 여전히 미복구"
            )
        else:
            after = {
                "status": before_status,
                "publish_allowed": before.get("publish_allowed"),
                "official_title": before.get("official_title"),
                "official_url": before.get("official_url"),
                "candidate_preserved": before.get("candidate_preserved"),
                "bypassed_gate": before.get("decision_bypassed_gate"),
                "reason_codes": [],
            }
            after_exposed = before_exposed
            classification = "대상 아님: 기존 판정 유지"

        after_public_target += int(targeted and after_exposed)
        after_unsafe += int(targeted and after_exposed)
        rows_out.append(
            {
                "post_id": int(post_id) if post_id.isdigit() else post_id,
                "targeted_required_search_failclose": targeted,
                "baseline_gate_replay_exact": True if targeted else None,
                "search_status": blocker.get("search_status") if blocker else None,
                "unrecovered_degraded": int(blocker.get("unrecovered_degraded") or 0)
                if blocker
                else 0,
                "before": {
                    "decision_status": before_status,
                    "public_exposed": before_exposed,
                    "publish_allowed": before.get("publish_allowed"),
                    "public_identity_sha256": _public_identity_hash(before),
                    "candidate_material_available": candidate_before,
                },
                "after_projection": {
                    "decision_status": after["status"],
                    "public_exposed": after_exposed,
                    "publish_allowed": after["publish_allowed"],
                    "public_identity_sha256": _public_identity_hash(after),
                    "candidate_preserved": after["candidate_preserved"],
                    "bypassed_gate": after["bypassed_gate"],
                    "reason_codes": after["reason_codes"],
                },
                "accuracy_percentage_shadow": {
                    "status": PROBABILITY_STATUS,
                    "p_resolve": None,
                    "p_nil": None,
                    "p_uncertain": None,
                },
                "classification_ko": classification,
            }
        )

    blocker_count = len(blockers)
    safety_gate = "GO" if after_unsafe == 0 and candidate_missing_after == 0 else "NO-GO"
    if before_unsafe > after_unsafe and safety_gate == "GO":
        overall = "PARTIAL_SAFETY_IMPROVEMENT_NOT_RUNTIME_VALIDATED"
    elif safety_gate == "GO":
        overall = "NO_PUBLIC_SAFETY_DELTA_NOT_RUNTIME_VALIDATED"
    else:
        overall = "NO-GO_STATIC_PROJECTION"

    return {
        "schema_version": REPORT_SCHEMA,
        "generated_at": _now(),
        "mode": STATIC_MODE,
        "treatment": TREATMENT,
        "run_spec": {
            "path": _stored_path(_resolve_path(run_spec_path)),
            "sha256": _sha256_file(_resolve_path(run_spec_path)),
            "self_hash": run_spec["run_spec_sha256"],
        },
        "source_integrity": {
            "gate": "GO",
            "row_count": len(baseline_rows),
            "missing_post_ids": 0,
            "extra_post_ids": 0,
            "duplicate_post_ids": 0,
        },
        "before_after": {
            "targeted_required_search_rows": blocker_count,
            "typed_gate_invoked_rows": blocker_count,
            "baseline_gate_replay_exact_rows": baseline_gate_replay_exact,
            "decision_changed_rows": decision_changed,
            "decision_status_changed_rows": decision_status_changed,
            "public_output_changed_rows": public_output_changed,
            "unsafe_publish": {
                "before": before_unsafe,
                "after": after_unsafe,
                "delta": after_unsafe - before_unsafe,
            },
            "target_public_rows": {
                "before": before_public_target,
                "after": after_public_target,
                "delta": after_public_target - before_public_target,
            },
            "required_search_hard_blocker": {
                "before": blocker_count,
                "after": blocker_count,
                "delta": 0,
                "note_ko": "공개 안전성만 투영했으며 검색 근거 자체는 복구하지 않았다.",
            },
            "candidate_missing_after": candidate_missing_after,
        },
        "accuracy_percentage_shadow": {
            "status": PROBABILITY_STATUS,
            "reason_ko": "보정된 고정 평가 자료가 없어 퍼센트를 만들지 않았다.",
            "ece": None,
            "brier": None,
            "risk_coverage": None,
        },
        "rows": rows_out,
        "gates": {
            "artifact_integrity": "GO",
            "post_id_completeness": "GO",
            "retrieval_failclose_safety": safety_gate,
            "retrieval_evidence": "NO-GO" if blocker_count else "GO",
            "runtime_validation": "NOT_RUN_STATIC_PROJECTION",
            "semantic_quality": "REVIEW-LOCKED",
            "production_full_scan_approval": False,
            "overall": overall,
        },
        "approval_boundary_ko": (
            "검색 미복구 공개 차단의 정적 안전성 개선만 확인했다. "
            "검색 5건은 미복구이며 실제 런타임·정확도·운영 승인은 확인하지 않았다."
        ),
        "next_action_ko": (
            "진행 중 104,502건 실행이 끝난 뒤 RetrievalState를 실제 판정 계약에 연결하고, "
            "별도 출력·병렬 16·대시보드·속어 저장 끔 조건에서 동일 입력 전후 런을 검증한다."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    before_after = report["before_after"]
    gates = report["gates"]
    lines = [
        "# LLM 파이프라인 개선 전·후 정적 비교 보고서",
        "",
        "## 결론",
        "",
        report["approval_boundary_ko"],
        "",
        "| 확인 항목 | 개선 전 | 개선 후 투영 | 해석 |",
        "| --- | ---: | ---: | --- |",
        (
            f"| 검색 미복구 상태의 작품 공개 | {before_after['unsafe_publish']['before']} | "
            f"{before_after['unsafe_publish']['after']} | 잘못 공개될 수 있는 경로를 차단했다. |"
        ),
        (
            f"| 공개 결과가 바뀐 글 | - | {before_after['public_output_changed_rows']} | "
            "실제 공개값이 바뀐 행 수다. |"
        ),
        (
            f"| 필수 검색 미복구 글 | {before_after['required_search_hard_blocker']['before']} | "
            f"{before_after['required_search_hard_blocker']['after']} | 검색 근거 자체는 아직 복구하지 않았다. |"
        ),
        (
            f"| 대상 5건 내 개선 후 후보 자료 누락 | - | {before_after['candidate_missing_after']} | "
            "작품명을 비워도 재판단 후보는 보존해야 한다. |"
        ),
        "| 정확도 퍼센트 | 없음 | 없음 | 보정 자료가 없어 숫자를 만들지 않았다. |",
        "",
        "## 게시글별 변화",
        "",
        "| 게시글 번호 | 필수 검색 미복구 | 개선 전 공개 | 개선 후 공개 | 판정 |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in report["rows"]:
        if not row["targeted_required_search_failclose"]:
            continue
        before = "공개" if row["before"]["public_exposed"] else "비공개"
        after = "공개" if row["after_projection"]["public_exposed"] else "비공개"
        lines.append(
            f"| `{row['post_id']}` | {row['unrecovered_degraded']}건 | {before} | {after} | "
            f"{row['classification_ko']} |"
        )

    lines.extend(
        [
            "",
            "## 게이트",
            "",
            "| 게이트 | 상태 |",
            "| --- | --- |",
            f"| 입력·결과 지문과 게시글 완전성 | `{gates['artifact_integrity']} / {gates['post_id_completeness']}` |",
            f"| 검색 실패 시 공개 차단 안전성 | `{gates['retrieval_failclose_safety']}` |",
            f"| 검색 근거 복구 | `{gates['retrieval_evidence']}` |",
            f"| 실제 런타임 검증 | `{gates['runtime_validation']}` |",
            f"| 의미 품질 | `{gates['semantic_quality']}` |",
            f"| 운영 전체 승인 | `{str(gates['production_full_scan_approval']).lower()}` |",
            f"| 종합 | `{gates['overall']}` |",
            "",
            "## 다음 단계",
            "",
            report["next_action_ko"],
            "",
            "이 파일은 저장된 결과를 읽어 정책을 투영한 비교 보고서다. 실제 파이프라인 결과 파일이나 진행 중 실행은 변경하지 않았다.",
            "",
            "## 근거",
            "",
            f"- 실행 명세: `{report['run_spec']['path']}`",
            f"- 실행 명세 파일 지문: `{report['run_spec']['sha256']}`",
            f"- 실행 명세 자체 지문: `{report['run_spec']['self_hash']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_comparison(
    report: dict[str, Any],
    *,
    output_json: str | Path,
    output_md: str | Path,
    active_manifest: Path | None,
) -> tuple[Path, Path]:
    json_path = _resolve_path(output_json)
    md_path = _resolve_path(output_md)
    _assert_output_noninterference([json_path, md_path], active_manifest)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    md_path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    return json_path, md_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze and compare a static, non-runtime LLM pipeline improvement projection."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    freeze = subparsers.add_parser("freeze", help="Create an immutable static RunSpec.")
    freeze.add_argument("--input", required=True)
    freeze.add_argument("--baseline", required=True)
    freeze.add_argument("--baseline-manifest", required=True)
    freeze.add_argument("--runtime-plan", required=True)
    freeze.add_argument("--integrity-artifact", required=True)
    freeze.add_argument("--retrieval-gate", required=True)
    freeze.add_argument("--active-manifest")
    freeze.add_argument("--runtime-parallel", type=int, default=16)
    freeze.add_argument("--output", required=True)

    compare = subparsers.add_parser("compare", help="Project fail-close and compare by post_id.")
    compare.add_argument("--run-spec", required=True)
    compare.add_argument("--output-json", required=True)
    compare.add_argument("--output-md", required=True)

    status = subparsers.add_parser("status", help="Validate a RunSpec without writing outputs.")
    status.add_argument("--run-spec", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "freeze":
        run_spec = create_run_spec(
            input_path=args.input,
            baseline_path=args.baseline,
            baseline_manifest_path=args.baseline_manifest,
            runtime_plan_path=args.runtime_plan,
            integrity_artifact_path=args.integrity_artifact,
            retrieval_gate_path=args.retrieval_gate,
            active_manifest_path=args.active_manifest,
            runtime_parallel=args.runtime_parallel,
        )
        output = write_run_spec(run_spec, args.output)
        print(
            json.dumps(
                {
                    "gate": "GO",
                    "mode": STATIC_MODE,
                    "output": _stored_path(output),
                    "run_spec_sha256": run_spec["run_spec_sha256"],
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.command == "status":
        run_spec, rows, gate = validate_run_spec(args.run_spec)
        print(
            json.dumps(
                {
                    "gate": "GO",
                    "mode": run_spec["mode"],
                    "row_count": len(rows),
                    "required_search_hard_blocker": len(_gate_blockers(gate)),
                    "runtime_executed": False,
                },
                ensure_ascii=False,
            )
        )
        return 0

    report = build_static_projection(args.run_spec)
    run_spec, _, _ = validate_run_spec(args.run_spec)
    json_path, md_path = write_comparison(
        report,
        output_json=args.output_json,
        output_md=args.output_md,
        active_manifest=_active_manifest_from_spec(run_spec),
    )
    print(
        json.dumps(
            {
                "gate": report["gates"]["overall"],
                "output_json": _stored_path(json_path),
                "output_md": _stored_path(md_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
