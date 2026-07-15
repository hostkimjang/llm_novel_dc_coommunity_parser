from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_adjusted_collateral_adjudication import TERMINAL_LABELS
from tools.build_adjusted_collateral_blind_packet import (
    packet_row_digest,
    source_payload,
)
from tools.audit_publication_contract_convergence import audit_row as audit_publication_row
from tools.compare_completed779_improvement import load_json_or_jsonl


PRODUCTION_PANEL_ROWS = 375
PRODUCTION_SEARCH_SHARDS = 16
PRODUCTION_GOLDEN_ROWS = 18
MAX_PREFLIGHT_LEAD = timedelta(hours=2)
SEARCH_HEALTH_COUNTER_FIELDS = (
    "queries_issued",
    "upstream_zero",
    "degraded",
    "degraded_zero",
    "degraded_recovered",
    "unrecovered_degraded",
)
SEARCH_TERMINAL_PACKET_VERSION = "full375-search-terminal-blind-v1"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"expected object at {path}:{line_no}")
            rows.append(row)
    return rows


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@lru_cache(maxsize=256)
def _sha256_file(path_text: str) -> str:
    path = Path(path_text)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_ref_issues(value: Any, field: str) -> list[str]:
    issues: list[str] = []
    if not isinstance(value, list) or not value:
        return [f"terminal_{field}_must_be_nonempty_artifact_ref_list"]
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            issues.append(f"terminal_{field}_{index}_must_be_object")
            continue
        path_text = str(item.get("path") or "").strip()
        expected_hash = str(item.get("sha256") or "").strip().lower()
        if not path_text or not Path(path_text).is_file():
            issues.append(f"terminal_{field}_{index}_path_missing")
            continue
        if len(expected_hash) != 64:
            issues.append(f"terminal_{field}_{index}_sha256_invalid")
            continue
        if _sha256_file(str(Path(path_text))) != expected_hash:
            issues.append(f"terminal_{field}_{index}_sha256_mismatch")
    return issues


def _post_id(row: dict[str, Any]) -> str:
    text = "" if row.get("post_id") is None else str(row.get("post_id")).strip()
    if not text:
        raise ValueError("missing post_id")
    return text


def _index(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        post_id = _post_id(row)
        if post_id in out:
            raise ValueError(f"{label} duplicate post_id: {post_id}")
        out[post_id] = row
    return out


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis_result = row.get("analysis_result") if isinstance(row.get("analysis_result"), dict) else {}
    identity = analysis_result.get("identity") if isinstance(analysis_result.get("identity"), dict) else {}
    return identity


def _source_hash(row: dict[str, Any]) -> str:
    source = {key: value for key, value in row.items() if key not in {"analysis_result", "run_meta"}}
    return _canonical_hash(source)


def _public_state(row: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    novel_identity = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}
    ledger = identity.get("candidate_ledger") if isinstance(identity.get("candidate_ledger"), dict) else {}
    decision = identity.get("promotion_decision") if isinstance(identity.get("promotion_decision"), dict) else {}
    if not decision and isinstance(ledger.get("promotion_decision"), dict):
        decision = ledger["promotion_decision"]
    trace = identity.get("publish_contract_trace") if isinstance(identity.get("publish_contract_trace"), dict) else {}
    if not trace and isinstance(ledger.get("publish_contract_trace"), dict):
        trace = ledger["publish_contract_trace"]

    def first_text(*values: Any) -> str | None:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None

    title = first_text(
        novel_identity.get("official_title"),
        novel_identity.get("official_novel_title"),
        novel_identity.get("resolved_title"),
        identity.get("official_title"),
        identity.get("official_novel_title"),
        identity.get("resolved_title"),
        decision.get("official_title"),
    )
    url = (
        first_text(
            novel_identity.get("official_url"),
            novel_identity.get("heretic_url"),
            novel_identity.get("resolved_url"),
            identity.get("official_url"),
            identity.get("heretic_url"),
            identity.get("resolved_url"),
            decision.get("official_url"),
        )
    )
    return {
        "official_title": title,
        "official_url": url,
        "publish_allowed": decision.get("publish_allowed"),
        "candidate_preserved": decision.get("candidate_preserved"),
        "decision_bypassed_gate": decision.get("bypassed_gate"),
        "trace_bypassed_gate": trace.get("bypassed_gate"),
        "decision": decision,
        "trace": trace,
    }


def _search_health(row: dict[str, Any]) -> dict[str, Any]:
    identity = _identity(row)
    health = identity.get("search_health")
    if not isinstance(health, dict):
        run_meta = row.get("run_meta") if isinstance(row.get("run_meta"), dict) else {}
        health = run_meta.get("search_health")
    return health if isinstance(health, dict) else {}


def _search_health_issues(health: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not health:
        return ["search_health_missing"]
    for field in SEARCH_HEALTH_COUNTER_FIELDS:
        if field not in health:
            issues.append(f"search_health_{field}_missing")
            continue
        value = health.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            issues.append(f"search_health_{field}_invalid")
    status = str(health.get("status") or "").strip()
    if not status:
        issues.append("search_health_status_missing")
        return issues
    queries = int(health.get("queries_issued") or 0)
    degraded = int(health.get("degraded") or 0)
    degraded_zero = int(health.get("degraded_zero") or 0)
    recovered = int(health.get("degraded_recovered") or 0)
    unrecovered = int(health.get("unrecovered_degraded") or 0)
    if queries <= 0:
        issues.append("search_queries_not_executed")
    if degraded_zero > degraded:
        issues.append("search_degraded_zero_exceeds_degraded")
    if recovered > degraded:
        issues.append("search_degraded_recovered_exceeds_degraded")
    if status == "ok" and (degraded_zero > recovered or unrecovered):
        issues.append("search_status_ok_conflicts_with_degraded_counters")
    if status == "SEARCH_DEGRADED_RECOVERED":
        if degraded <= 0 or recovered <= 0 or unrecovered != 0:
            issues.append("search_recovered_status_counter_mismatch")
    if unrecovered > 0:
        issues.append("search_unrecovered_degraded_nonzero")
    return issues


def _search_issue(health: dict[str, Any]) -> tuple[bool, str]:
    status = str(health.get("status") or "MISSING").strip()
    if _search_health_issues(health):
        return True, status
    if status == "ok":
        return False, status
    if status == "SEARCH_DEGRADED_RECOVERED":
        return False, status
    return True, status


def _query_audit_issues(
    audit: dict[str, Any],
    label: str,
    expected_count: int,
    expected_probe_scope: str,
) -> list[str]:
    issues: list[str] = []
    probe = audit.get("search_probe_summary") if isinstance(audit.get("search_probe_summary"), dict) else {}
    if int(audit.get("count") or 0) != expected_count or int(audit.get("ok_count") or 0) != expected_count:
        issues.append(f"{label}_shard_not_all_ok")
    if int(audit.get("bad_count") or 0) != 0:
        issues.append(f"{label}_bad_shards_nonzero")
    if probe.get("enabled") is not True or int(probe.get("ok_count") or 0) != expected_count:
        issues.append(f"{label}_query_probe_not_all_ok")
    if int(probe.get("bad_count") or 0) != 0:
        issues.append(f"{label}_query_bad_nonzero")
    if int(probe.get("degraded_count") or 0) != 0:
        issues.append(f"{label}_query_degraded_nonzero")
    if int(probe.get("forbidden_engine_count") or 0) != 0:
        issues.append(f"{label}_forbidden_engine_nonzero")
    shards = audit.get("shards") if isinstance(audit.get("shards"), list) else []
    if len(shards) != expected_count:
        issues.append(f"{label}_shard_detail_count_mismatch")
        return issues
    shard_ids = [item.get("shard") for item in shards if isinstance(item, dict)]
    if sorted(shard_ids) != list(range(1, expected_count + 1)):
        issues.append(f"{label}_shard_detail_ids_mismatch")
    summary_query = str(probe.get("query") or "").strip()
    expected_scope = str(expected_probe_scope or "").strip().lower()
    for item in shards:
        if not isinstance(item, dict):
            issues.append(f"{label}_shard_detail_nonobject")
            continue
        shard = item.get("shard")
        for field in ("ok",):
            if item.get(field) is not True:
                issues.append(f"{label}_shard_{shard}_{field}_not_true")
        for field in ("healthz", "readyz"):
            payload = item.get(field) if isinstance(item.get(field), dict) else {}
            if payload.get("ok") is not True:
                issues.append(f"{label}_shard_{shard}_{field}_not_ok")
        shard_probe = item.get("search_probe") if isinstance(item.get("search_probe"), dict) else {}
        if shard_probe.get("ok") is not True:
            issues.append(f"{label}_shard_{shard}_search_probe_not_ok")
        if str(shard_probe.get("query") or "").strip() != summary_query:
            issues.append(f"{label}_shard_{shard}_probe_query_mismatch")
        purpose = str(shard_probe.get("purpose") or "").strip().lower()
        if label not in purpose or (expected_scope and expected_scope not in purpose):
            issues.append(f"{label}_shard_{shard}_probe_purpose_mismatch")
        docker = item.get("docker") if isinstance(item.get("docker"), dict) else {}
        for component in ("warp", "searchxng", "mcp_bridge", "browser_search"):
            component_state = docker.get(component) if isinstance(docker.get(component), dict) else {}
            if component_state.get("ok") is not True:
                issues.append(f"{label}_shard_{shard}_docker_{component}_not_ok")
    return issues


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _run_started_at(manifest: dict[str, Any]) -> datetime | None:
    composition = manifest.get("runtime_composition") if isinstance(manifest.get("runtime_composition"), dict) else {}
    candidates = [composition.get("residual_run_id"), manifest.get("run_id")]
    for value in candidates:
        text = str(value or "").strip()
        try:
            return datetime.strptime(text, "%Y%m%d_%H%M%S_%f")
        except ValueError:
            continue
    return None


def _query_audit_temporal_issues(
    preflight: dict[str, Any],
    postflight: dict[str, Any],
    manifest: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    pre_at = _parse_timestamp(preflight.get("generated_at"))
    post_at = _parse_timestamp(postflight.get("generated_at"))
    run_at = _run_started_at(manifest)
    completed_at = _parse_timestamp(
        manifest.get("runtime_completed_at") or manifest.get("generated_at")
    )
    if pre_at is None:
        issues.append("preflight_generated_at_missing_or_invalid")
    if post_at is None:
        issues.append("postflight_generated_at_missing_or_invalid")
    if run_at is None:
        issues.append("manifest_runtime_start_unavailable")
    if completed_at is None:
        issues.append("manifest_runtime_completion_unavailable")
    if pre_at is not None and run_at is not None:
        if pre_at > run_at:
            issues.append("preflight_not_before_runtime")
        elif run_at - pre_at > MAX_PREFLIGHT_LEAD:
            issues.append("preflight_stale_for_runtime")
    if post_at is not None and run_at is not None and post_at < run_at:
        issues.append("postflight_before_runtime")
    if post_at is not None and completed_at is not None and post_at < completed_at:
        issues.append("postflight_before_runtime_completion")
    if pre_at is not None and post_at is not None and post_at <= pre_at:
        issues.append("postflight_not_after_preflight")

    pre_probe = preflight.get("search_probe_summary") if isinstance(preflight.get("search_probe_summary"), dict) else {}
    post_probe = postflight.get("search_probe_summary") if isinstance(postflight.get("search_probe_summary"), dict) else {}
    pre_query = str(pre_probe.get("query") or "").strip()
    post_query = str(post_probe.get("query") or "").strip()
    if not pre_query or pre_query != post_query:
        issues.append("preflight_postflight_probe_query_mismatch")

    def purposes(audit: dict[str, Any]) -> set[str]:
        values: set[str] = set()
        for shard in audit.get("shards") or []:
            if not isinstance(shard, dict):
                continue
            probe = shard.get("search_probe") if isinstance(shard.get("search_probe"), dict) else {}
            purpose = str(probe.get("purpose") or "").strip().lower()
            if purpose:
                values.add(purpose)
        return values

    pre_purposes = purposes(preflight)
    post_purposes = purposes(postflight)
    if not pre_purposes or not all("preflight" in value for value in pre_purposes):
        issues.append("preflight_probe_purpose_mismatch")
    if not post_purposes or not all("postflight" in value for value in post_purposes):
        issues.append("postflight_probe_purpose_mismatch")
    return issues


def _runtime_binding_issues(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    expected_rows: int,
    expected_shards: int,
) -> list[str]:
    issues: list[str] = []
    post_ids = [_post_id(row) for row in rows]
    expected_hashes = {
        "result_payload_sha256": _canonical_hash(rows),
        "input_post_id_order_sha256": _canonical_hash(post_ids),
        "input_post_id_set_sha256": _canonical_hash(sorted(post_ids)),
    }
    for field, expected in expected_hashes.items():
        if str(manifest.get(field) or "").strip() != expected:
            issues.append(f"manifest_{field}_mismatch")

    composition = manifest.get("runtime_composition") if isinstance(manifest.get("runtime_composition"), dict) else {}
    if composition:
        expected_run_counts = {
            str(composition.get("source_run_id") or "").strip(): int(
                composition.get("source_completed_rows") or 0
            ),
            str(composition.get("residual_run_id") or "").strip(): int(
                composition.get("residual_completed_rows") or 0
            ),
        }
        if "" in expected_run_counts or sum(expected_run_counts.values()) != expected_rows:
            issues.append("manifest_runtime_composition_invalid")
    else:
        run_id = str(manifest.get("run_id") or "").strip()
        expected_run_counts = {run_id: expected_rows} if run_id else {}
        if not expected_run_counts:
            issues.append("manifest_run_id_missing")

    actual_run_counts: Counter[str] = Counter()
    row_manifest_bindings = (
        ("model", "llm_model"),
        ("llm_endpoint", "llm_endpoint"),
        ("requested_parallel", "requested_parallel"),
        ("effective_parallel", "effective_parallel"),
        ("mcp_health_include_search", "mcp_health_include_search"),
        ("mcp_health_light_mode", "mcp_health_light_mode"),
        ("mcp_health_required_ok_count", "mcp_health_required_ok_count"),
        ("mcp_health_ok_count", "mcp_health_ok_count"),
    )
    for row in rows:
        run_meta = row.get("run_meta") if isinstance(row.get("run_meta"), dict) else {}
        run_id = str(run_meta.get("run_id") or "").strip()
        actual_run_counts[run_id] += 1
        if not run_id:
            issues.append("result_row_run_id_missing")
        for row_field, manifest_field in row_manifest_bindings:
            if row_field not in run_meta or manifest_field not in manifest:
                issues.append(f"result_manifest_binding_field_missing:{row_field}/{manifest_field}")
                continue
            if run_meta.get(row_field) != manifest.get(manifest_field):
                issues.append(f"result_manifest_binding_mismatch:{row_field}/{manifest_field}")
        if int(run_meta.get("mcp_health_failure_count") or 0) != 0:
            issues.append("result_row_mcp_health_failure_nonzero")
        if int(run_meta.get("mcp_health_ok_count") or 0) != expected_shards:
            issues.append("result_row_mcp_health_ok_count_mismatch")
    if actual_run_counts != Counter(expected_run_counts):
        issues.append(
            "result_manifest_run_composition_mismatch:"
            f"actual={dict(actual_run_counts)} expected={expected_run_counts}"
        )
    return sorted(set(issues))


def build_terminal_packet(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for row in rows:
        public = _public_state(row)
        health = _search_health(row)
        issue, status = _search_issue(health)
        if not issue or public.get("official_title") or public.get("official_url") or public.get("publish_allowed") is True:
            continue
        packet = {
            "packet_version": SEARCH_TERMINAL_PACKET_VERSION,
            "post_id": row.get("post_id"),
            "source_hash": _source_hash(row),
            "source": source_payload(row),
            "search_observation": {
                "status": status,
                "queries_issued": health.get("queries_issued"),
                "degraded_zero": health.get("degraded_zero"),
                "degraded_recovered": health.get("degraded_recovered"),
                "unrecovered_degraded": health.get("unrecovered_degraded"),
                "schema_issues": _search_health_issues(health),
            },
            "allowed_classification": "safe_no_public_terminal",
            "forbidden_outcomes": ["publish", "wrong_work", "golden_positive_loss"],
        }
        packet["packet_row_sha256"] = packet_row_digest(packet)
        packets.append(packet)
    return packets


def _blind_packet_binding_issues(
    blind_verdict: dict[str, Any],
    row: dict[str, Any],
    expected_source_hash: str,
) -> list[str]:
    issues: list[str] = []
    packet_ref = blind_verdict.get("packet_ref") if isinstance(blind_verdict.get("packet_ref"), dict) else {}
    packet_path = Path(str(packet_ref.get("path") or ""))
    if not packet_path.is_file():
        return ["terminal_blind_packet_path_missing"]
    try:
        packets = _load_jsonl(packet_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return ["terminal_blind_packet_unreadable"]
    matching = [item for item in packets if str(item.get("post_id")) == str(row.get("post_id"))]
    if len(matching) != 1:
        return ["terminal_blind_packet_post_id_binding_mismatch"]
    packet = matching[0]
    if packet.get("packet_version") != SEARCH_TERMINAL_PACKET_VERSION:
        issues.append("terminal_blind_packet_version_mismatch")
    if packet.get("source_hash") != expected_source_hash:
        issues.append("terminal_blind_packet_source_hash_mismatch")
    if packet.get("source") != source_payload(row):
        issues.append("terminal_blind_packet_source_payload_mismatch")
    actual_row_hash = packet_row_digest(packet)
    if packet.get("packet_row_sha256") != actual_row_hash:
        issues.append("terminal_blind_packet_row_hash_mismatch")
    if blind_verdict.get("packet_row_sha256") != actual_row_hash:
        issues.append("terminal_blind_verdict_packet_row_hash_mismatch")
    return issues


def _terminal_issues(ledger: dict[str, Any], row: dict[str, Any], public: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    expected_source_hash = _source_hash(row)
    if ledger.get("source_hash") != expected_source_hash or ledger.get("input_hash") != expected_source_hash:
        issues.append("terminal_source_or_input_hash_mismatch")
    if ledger.get("terminal_label") not in TERMINAL_LABELS:
        issues.append("terminal_label_invalid_or_missing")
    if ledger.get("classification") != "safe_no_public_terminal":
        issues.append("terminal_classification_must_be_safe_no_public_terminal")
    if not str(ledger.get("row_rationale") or "").strip():
        issues.append("terminal_row_rationale_missing")
    if not isinstance(ledger.get("evidence_refs"), list) or not ledger.get("evidence_refs"):
        issues.append("terminal_evidence_refs_missing")
    if public.get("official_title") not in (None, "") or public.get("official_url") not in (None, ""):
        issues.append("terminal_public_identity_must_be_null")
    if public.get("publish_allowed") is not False:
        issues.append("terminal_publish_allowed_must_be_false")
    if public.get("decision_bypassed_gate") is not False or public.get("trace_bypassed_gate") is not False:
        issues.append("terminal_bypassed_gate_must_be_false")
    if public.get("candidate_preserved") is not True and not str(
        ledger.get("candidate_unavailable_reason") or ""
    ).strip():
        issues.append("terminal_candidate_preservation_missing")
    if ledger.get("publication_violation") is not False:
        issues.append("terminal_publication_violation_must_be_false")
    actual_decision = public.get("decision") if isinstance(public.get("decision"), dict) else {}
    actual_trace = public.get("trace") if isinstance(public.get("trace"), dict) else {}
    if ledger.get("promotion_decision") != actual_decision:
        issues.append("terminal_promotion_decision_mismatch")
    if ledger.get("publish_contract_trace") != actual_trace:
        issues.append("terminal_publish_contract_trace_mismatch")
    before_after = ledger.get("before_after") if isinstance(ledger.get("before_after"), dict) else {}
    after = before_after.get("after") if isinstance(before_after.get("after"), dict) else {}
    expected_after = {
        "official_title": public.get("official_title"),
        "official_url": public.get("official_url"),
        "publish_allowed": public.get("publish_allowed"),
    }
    before = before_after.get("before") if isinstance(before_after.get("before"), dict) else {}
    if before.get("source_hash") != expected_source_hash:
        issues.append("terminal_before_after_before_source_hash_mismatch")
    if after != expected_after:
        issues.append("terminal_before_after_after_mismatch")
    blind_verdict = ledger.get("blind_verdict")
    if not isinstance(blind_verdict, dict) or not blind_verdict:
        issues.append("terminal_blind_verdict_missing")
    else:
        if blind_verdict.get("blind") is not True or blind_verdict.get("method") != "source_native_blind":
            issues.append("terminal_blind_verdict_method_invalid")
        if blind_verdict.get("classification") != "safe_no_public_terminal":
            issues.append("terminal_blind_verdict_classification_mismatch")
        if blind_verdict.get("terminal_label") != ledger.get("terminal_label"):
            issues.append("terminal_blind_verdict_label_mismatch")
        for field in ("reviewer", "model", "run_id", "review_id"):
            if not str(blind_verdict.get(field) or "").strip():
                issues.append(f"terminal_blind_verdict_{field}_missing")
        packet_ref = blind_verdict.get("packet_ref")
        issues.extend(_artifact_ref_issues([packet_ref] if isinstance(packet_ref, dict) else [], "blind_packet_ref"))
        packet_hash = str(blind_verdict.get("packet_sha256") or "").strip().lower()
        if not isinstance(packet_ref, dict) or packet_hash != str(packet_ref.get("sha256") or "").strip().lower():
            issues.append("terminal_blind_verdict_packet_hash_mismatch")
        issues.extend(_blind_packet_binding_issues(blind_verdict, row, expected_source_hash))
    if not str(ledger.get("unblock_condition") or "").strip():
        issues.append("terminal_unblock_condition_missing")
    independent_review = ledger.get("independent_review")
    if not isinstance(independent_review, dict):
        issues.append("terminal_independent_review_invalid")
    else:
        if independent_review.get("role") != "independent_reviewer":
            issues.append("terminal_independent_review_role_invalid")
        for field in ("reviewer", "review_id", "reviewed_at"):
            if not str(independent_review.get(field) or "").strip():
                issues.append(f"terminal_independent_review_{field}_missing")
        if isinstance(blind_verdict, dict) and str(independent_review.get("reviewer") or "").strip() == str(
            blind_verdict.get("reviewer") or ""
        ).strip():
            issues.append("terminal_independent_reviewer_must_differ_from_blind_reviewer")
        review_ref = independent_review.get("artifact_ref")
        issues.extend(
            _artifact_ref_issues([review_ref] if isinstance(review_ref, dict) else [], "independent_review_ref")
        )
    issues.extend(_artifact_ref_issues(ledger.get("evidence_refs"), "evidence_refs"))
    issues.extend(_artifact_ref_issues(ledger.get("test_replay_artifacts"), "test_replay_artifacts"))
    for field in ("attempted_lanes", "missing_or_conflicting_evidence"):
        values = ledger.get(field)
        if not isinstance(values, list) or not values or any(not str(value or "").strip() for value in values):
            issues.append(f"terminal_{field}_must_be_nonempty_string_list")
    expected_health_hash = _canonical_hash(_search_health(row))
    if ledger.get("search_health_snapshot_sha256") != expected_health_hash:
        issues.append("terminal_search_health_snapshot_hash_mismatch")
    publication_audit = audit_publication_row(row, index=0)
    if publication_audit.get("gate") != "GO":
        codes = [item.get("code") for item in publication_audit.get("violations") or [] if isinstance(item, dict)]
        issues.append("terminal_actual_publication_contract_no_go:" + ",".join(str(code) for code in codes))
    return issues


def build_search_gate(
    *,
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    preflight: dict[str, Any],
    postflight: dict[str, Any],
    terminal_rows: list[dict[str, Any]],
    golden_rows: list[dict[str, Any]] | None = None,
    expected_rows: int = 375,
    expected_shards: int = 16,
    expected_probe_scope: str = "",
) -> dict[str, Any]:
    row_by_id = _index(rows, "runtime result")
    terminal_by_id = _index(terminal_rows, "search terminal ledger")
    golden_by_id = _index(golden_rows or [], "golden manifest")
    infrastructure_issues: list[str] = []
    if expected_rows != PRODUCTION_PANEL_ROWS:
        infrastructure_issues.append("production_expected_rows_must_equal_375")
    if expected_shards != PRODUCTION_SEARCH_SHARDS:
        infrastructure_issues.append("production_expected_shards_must_equal_16")
    if len(golden_by_id) != PRODUCTION_GOLDEN_ROWS:
        infrastructure_issues.append("golden_manifest_row_count_must_equal_18")
    if not set(golden_by_id).issubset(row_by_id):
        infrastructure_issues.append("golden_manifest_post_ids_not_in_runtime_panel")
    if len(rows) != expected_rows:
        infrastructure_issues.append("runtime_row_count_mismatch")
    if not str(expected_probe_scope or "").strip():
        infrastructure_issues.append("expected_probe_scope_missing")
    expected_manifest_counts = {
        "input_post_count": expected_rows,
        "completed_count": expected_rows,
        "flushed_count": expected_rows,
        "pending_count": 0,
        "failed_count": 0,
    }
    for field, expected in expected_manifest_counts.items():
        if field not in manifest:
            infrastructure_issues.append(f"manifest_{field}_missing")
        elif isinstance(manifest.get(field), bool) or not isinstance(manifest.get(field), int):
            infrastructure_issues.append(f"manifest_{field}_invalid")
        elif manifest.get(field) != expected:
            infrastructure_issues.append(f"manifest_{field}_mismatch")
    for field, expected in {
        "large_run_complete": True,
        "partial_flush_gap": False,
        "ordered_flush_blocked": False,
    }.items():
        if field not in manifest:
            infrastructure_issues.append(f"manifest_{field}_missing")
        elif manifest.get(field) is not expected:
            infrastructure_issues.append(f"manifest_{field}_mismatch")
    if manifest.get("mcp_health_include_search") is not True:
        infrastructure_issues.append("manifest_search_not_included")
    if manifest.get("mcp_health_light_mode") is not False:
        infrastructure_issues.append("manifest_search_light_mode_not_false")
    if int(manifest.get("mcp_health_ok_count") or 0) != expected_shards:
        infrastructure_issues.append("manifest_healthy_shard_count_mismatch")
    infrastructure_issues.extend(
        _query_audit_issues(preflight, "preflight", expected_shards, expected_probe_scope)
    )
    infrastructure_issues.extend(
        _query_audit_issues(postflight, "postflight", expected_shards, expected_probe_scope)
    )
    infrastructure_issues.extend(_query_audit_temporal_issues(preflight, postflight, manifest))
    infrastructure_issues.extend(
        _runtime_binding_issues(rows, manifest, expected_rows, expected_shards)
    )

    required_blockers: list[dict[str, Any]] = []
    unreviewed_rows: list[dict[str, Any]] = []
    terminal_accounted: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    recovered_observation_count = 0
    used_terminal_ids: set[str] = set()
    for post_id, row in row_by_id.items():
        health = _search_health(row)
        issue, status = _search_issue(health)
        health_issues = _search_health_issues(health)
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "SEARCH_DEGRADED_RECOVERED" and not issue:
            recovered_observation_count += 1
        if not issue:
            continue
        public = _public_state(row)
        golden = golden_by_id.get(post_id) or {}
        golden_positive_requires_public = bool(golden) and golden.get("expected_no_public_title") is False
        publish_dependency = bool(
            public.get("official_title")
            or public.get("official_url")
            or public.get("publish_allowed") is True
            or golden_positive_requires_public
        )
        detail = {
            "post_id": row.get("post_id"),
            "search_status": status,
            "unrecovered_degraded": int(health.get("unrecovered_degraded") or 0),
            "search_health_issues": health_issues,
            "publish_dependency": publish_dependency,
            "golden_positive_requires_public": golden_positive_requires_public,
        }
        if publish_dependency:
            required_blockers.append(detail)
            continue
        ledger = terminal_by_id.get(post_id)
        if ledger is None:
            unreviewed_rows.append({**detail, "issues": ["search_terminal_ledger_missing"]})
            continue
        used_terminal_ids.add(post_id)
        issues = _terminal_issues(ledger, row, public)
        if issues:
            unreviewed_rows.append({**detail, "issues": issues})
        else:
            terminal_accounted.append({**detail, "terminal_label": ledger.get("terminal_label")})

    extra_terminal_ids = sorted(set(terminal_by_id) - set(row_by_id))
    if extra_terminal_ids:
        infrastructure_issues.append("search_terminal_extra_post_ids")
    unused_terminal_ids = sorted(set(terminal_by_id) - used_terminal_ids)
    if unused_terminal_ids:
        infrastructure_issues.append("search_terminal_unused_post_ids")
    gate = (
        "GO"
        if not infrastructure_issues and not required_blockers and not unreviewed_rows
        else "NO-GO"
    )
    return {
        "report_type": "full375_search_adjudication_gate",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "row_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "recovered_only_observation_count": recovered_observation_count,
        "required_search_hard_blocker": len(required_blockers),
        "unreviewed_search_rows": len(unreviewed_rows),
        "terminal_adjudicated_search_rows": len(terminal_accounted),
        "infrastructure_issues": infrastructure_issues,
        "required_search_hard_blocker_rows": required_blockers,
        "unreviewed_search_row_details": unreviewed_rows,
        "terminal_adjudicated_rows": terminal_accounted,
        "extra_terminal_post_ids": extra_terminal_ids,
        "unused_terminal_post_ids": unused_terminal_ids,
        "approval_boundary": {
            "publish_dependency_search_issue_is_never_terminal_exempt": True,
            "recovered_only_with_unrecovered_zero_is_observation": True,
            "dashboard_is_not_approval": True,
            "production_full_scan_approval": False,
        },
    }


def build_terminal_template(
    rows: list[dict[str, Any]],
    *,
    packet_rows: list[dict[str, Any]] | None = None,
    packet_ref: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    packets_by_id = {
        str(packet.get("post_id")): packet
        for packet in (packet_rows or [])
        if isinstance(packet, dict)
    }
    for row in rows:
        public = _public_state(row)
        issue, status = _search_issue(_search_health(row))
        if not issue or public.get("official_title") or public.get("official_url") or public.get("publish_allowed") is True:
            continue
        source_hash = _source_hash(row)
        packet = packets_by_id.get(str(row.get("post_id"))) or {}
        templates.append(
            {
                "post_id": row.get("post_id"),
                "search_status": status,
                "source_hash": source_hash,
                "input_hash": source_hash,
                "terminal_label": None,
                "classification": "safe_no_public_terminal",
                "row_rationale": None,
                "evidence_refs": [],
                "before_after": {
                    "before": {"source_hash": source_hash},
                    "after": {
                        "official_title": public.get("official_title"),
                        "official_url": public.get("official_url"),
                        "publish_allowed": public.get("publish_allowed"),
                    },
                },
                "blind_verdict": {
                    "blind": True,
                    "method": "source_native_blind",
                    "classification": None,
                    "terminal_label": None,
                    "reviewer": None,
                    "model": None,
                    "run_id": None,
                    "review_id": None,
                    "packet_ref": dict(packet_ref or {}),
                    "packet_sha256": (packet_ref or {}).get("sha256"),
                    "packet_row_sha256": packet.get("packet_row_sha256"),
                },
                "promotion_decision": public.get("decision"),
                "publish_contract_trace": public.get("trace"),
                "test_replay_artifacts": [],
                "attempted_lanes": [],
                "missing_or_conflicting_evidence": [],
                "search_health_snapshot_sha256": _canonical_hash(_search_health(row)),
                "candidate_unavailable_reason": None,
                "publication_violation": False,
                "unblock_condition": None,
                "independent_review": None,
            }
        )
    return templates


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the full375 search hard-blocker and terminal gate.")
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--preflight", required=True, type=Path)
    parser.add_argument("--postflight", required=True, type=Path)
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--expected-probe-scope", required=True)
    parser.add_argument("--terminal-ledger-jsonl", type=Path)
    parser.add_argument("--terminal-packet-jsonl", type=Path)
    parser.add_argument("--terminal-template-jsonl", type=Path)
    parser.add_argument("--expected-rows", type=int, default=375)
    parser.add_argument("--expected-shards", type=int, default=16)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_json_or_jsonl(args.result)
    if args.terminal_template_jsonl and not args.terminal_packet_jsonl:
        raise ValueError("--terminal-template-jsonl requires --terminal-packet-jsonl")
    packet_rows: list[dict[str, Any]] = []
    packet_ref: dict[str, Any] = {}
    if args.terminal_packet_jsonl:
        packet_rows = build_terminal_packet(rows)
        _write_jsonl(args.terminal_packet_jsonl, packet_rows)
        packet_ref = {
            "path": str(args.terminal_packet_jsonl),
            "sha256": _sha256_file(str(args.terminal_packet_jsonl)),
        }
    if args.terminal_template_jsonl:
        _write_jsonl(
            args.terminal_template_jsonl,
            build_terminal_template(rows, packet_rows=packet_rows, packet_ref=packet_ref),
        )
    manifest = _load_json(args.manifest)
    preflight = _load_json(args.preflight)
    postflight = _load_json(args.postflight)
    golden_payload = _load_json(args.golden_manifest)
    golden_rows = golden_payload.get("rows") if isinstance(golden_payload, dict) else None
    if not isinstance(golden_rows, list):
        raise ValueError("golden manifest must contain rows")
    report = build_search_gate(
        rows=rows,
        manifest=manifest,
        preflight=preflight,
        postflight=postflight,
        terminal_rows=_load_jsonl(args.terminal_ledger_jsonl),
        golden_rows=golden_rows,
        expected_rows=args.expected_rows,
        expected_shards=args.expected_shards,
        expected_probe_scope=args.expected_probe_scope,
    )
    report["artifact_provenance"] = {
        "result": {"path": str(args.result), "sha256": _sha256_file(str(args.result))},
        "manifest": {"path": str(args.manifest), "sha256": _sha256_file(str(args.manifest))},
        "preflight": {"path": str(args.preflight), "sha256": _sha256_file(str(args.preflight))},
        "postflight": {"path": str(args.postflight), "sha256": _sha256_file(str(args.postflight))},
        "golden_manifest": {
            "path": str(args.golden_manifest),
            "sha256": _sha256_file(str(args.golden_manifest)),
        },
    }
    _write_json(args.output_json, report)
    lines = [
        "# Full375 search 판결 gate",
        "",
        f"- gate: `{report['gate']}`",
        f"- required_search_hard_blocker: `{report['required_search_hard_blocker']}`",
        f"- unreviewed_search_rows: `{report['unreviewed_search_rows']}`",
        f"- terminal_adjudicated_search_rows: `{report['terminal_adjudicated_search_rows']}`",
        f"- infrastructure_issues: `{report['infrastructure_issues']}`",
        "- Public title/URL 의존 search issue는 terminal로 면제하지 않는다.",
        "",
    ]
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    with args.output_md.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if args.fail_on_no_go and report["gate"] != "GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
