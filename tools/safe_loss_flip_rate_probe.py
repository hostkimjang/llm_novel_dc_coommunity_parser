from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.test_run_dashboard_policy import (
    attach_dashboard_command,
    dashboard_contract,
    requested_parallel_for_test_run,
    strip_no_dashboard,
)
from tools.audit_publication_contract_convergence import audit_row as audit_publication_contract_row
from src.llm_batch.promotion_gate import (
    candidate_inventory_evidence_from_sources,
    candidate_inventory_pairs,
    evidence_records_from_payload,
)


DEFAULT_SAFE_LOSS_POST_IDS = ("11674712", "11660237", "11698880")
MINIMUM_ANALYZE_REPEATS = 5
ROW_DERIVED_CONFIG_HASH_POLICY = "uniform_nonempty_row_derived"
RUNTIME_FINGERPRINT_ALIASES = (
    "runtime_release_fingerprint_sha256",
    "stable_runtime_fingerprint_sha256",
    "runtime_fingerprint_sha256",
)
RUNTIME_BINDING_ENV_FIELDS = {
    "LLM_MODEL": "model",
    "LLM_ENDPOINT": "llm_endpoint",
    "PIPELINE_PROMPT_VERSION": "prompt_version",
    "RUNTIME_RELEASE_FINGERPRINT_SHA256": "runtime_release_fingerprint_sha256",
}
N5_POST_ID_COUNT = 5
N5_REPEAT_COUNT = 5
N5_EXPECTED_RUN_COUNT = 25
N5_BLIND_JUDGE_REPORT_TYPE = "promotion_contract_n5_source_backed_blind_judge"
N5_BLIND_JUDGE_BUILDER = ROOT / "tools/build_promotion_contract_n5_blind_judge.py"
PLAN_SELF_BINDING_VERSION = "safe-loss-flip-rate-plan-self-binding-v1"

OUTCOME_EXACT_MATCH_FIELDS = frozenset(
    {
        "status",
        "title",
        "url",
        "public_title",
        "public_url",
        "candidate_title",
        "candidate_url",
        "decision_status",
        "publish_allowed",
        "candidate_preserved",
        "bypassed_gate",
        "reason_codes",
        "scope_kind",
        "direct_bridge_sources",
        "evidence_kinds",
        "evidence_reason_codes",
        "contract_consistency_issues",
        "canonical_publication_contract_gate",
        "canonical_publication_contract_violation_codes",
        "contract_version",
        "input_fingerprint",
    }
)
OUTCOME_CONTRACT_FIELDS = OUTCOME_EXACT_MATCH_FIELDS | {
    "required_reason_codes",
    "forbidden_reason_codes",
    "required_direct_bridge_sources",
    "required_evidence_kinds",
    "required_evidence_reason_codes",
    "required_publish_supporting_evidence_kinds",
    "required_publish_supporting_evidence_reason_codes",
    "required_candidate_inventory_pairs",
    "require_fingerprint",
    "require_contract_version",
}
ACCEPTABLE_OUTCOME_REQUIRED_FIELDS = frozenset(
    {
        "public_title",
        "public_url",
        "candidate_title",
        "candidate_url",
        "decision_status",
        "publish_allowed",
        "candidate_preserved",
        "bypassed_gate",
        "scope_kind",
        "required_reason_codes",
        "required_direct_bridge_sources",
        "required_evidence_kinds",
        "required_evidence_reason_codes",
        "required_publish_supporting_evidence_kinds",
        "required_publish_supporting_evidence_reason_codes",
        "require_fingerprint",
        "require_contract_version",
    }
)
ACCEPTABLE_OUTCOME_LEGACY_FIELDS = frozenset({"status", "title", "url"})


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


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _plan_self_binding(plan: dict[str, Any]) -> dict[str, str]:
    payload = dict(plan)
    payload.pop("plan_self_binding", None)
    return {
        "version": PLAN_SELF_BINDING_VERSION,
        "algorithm": "sha256",
        "canonicalization": "json-sort-keys-compact-utf8",
        "excluded_field": "plan_self_binding",
        "canonical_sha256": canonical_sha256(payload),
    }


def _exclusive_write_bundle(entries: list[tuple[Path, bytes]]) -> None:
    """Create a related artifact bundle without overwriting any existing path."""
    normalized = [path.resolve() for path, _payload in entries]
    if len(normalized) != len(set(normalized)):
        raise ValueError("exclusive artifact bundle contains duplicate paths")
    existing = [str(path) for path in normalized if path.exists()]
    if existing:
        raise FileExistsError(f"exclusive artifact path already exists: {existing}")
    created: list[Path] = []
    try:
        for (raw_path, payload), path in zip(entries, normalized, strict=True):
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as handle:
                created.append(path)
                handle.write(payload)
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        raise


def _assert_artifact_paths_absent(paths: list[Path]) -> None:
    normalized = [path.resolve() for path in paths]
    if len(normalized) != len(set(normalized)):
        raise ValueError("planned artifact paths are not unique")
    existing = [str(path) for path in normalized if path.exists()]
    if existing:
        raise FileExistsError(f"planned artifact path already exists: {existing}")


def post_id_key(value: Any) -> str:
    return str(value or "").strip()


def duplicate_post_ids(values: list[str]) -> list[str]:
    counts = Counter(value for value in values if value)
    return sorted(value for value, count in counts.items() if count > 1)


def assert_unique_post_ids(values: list[str], *, label: str) -> None:
    duplicates = duplicate_post_ids(values)
    if duplicates:
        raise ValueError(f"duplicate {label} post_ids: {duplicates}")


def unwrap_result_row(row: dict[str, Any]) -> dict[str, Any]:
    nested = row.get("result")
    if isinstance(nested, dict):
        return nested
    return row


def row_repeat_binding(row: dict[str, Any]) -> str | None:
    unwrapped = unwrap_result_row(row)
    run_meta = _mapping(unwrapped.get("run_meta"))
    run_id = _first_text(run_meta.get("run_id"), unwrapped.get("run_id"))
    if run_id is not None:
        return f"run_id:{run_id}"
    explicit = row.get("_flip_probe_result_binding")
    if isinstance(explicit, dict) and explicit:
        return "result:" + hashlib.sha256(
            json.dumps(explicit, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
    explicit_text = _optional_text(explicit)
    return f"result:{explicit_text}" if explicit_text is not None else None


def row_runtime_signature(row: dict[str, Any]) -> tuple[str | None, list[str], dict[str, Any]]:
    unwrapped = unwrap_result_row(row)
    run_meta = _mapping(unwrapped.get("run_meta"))
    explicit = _mapping(row.get("_flip_probe_runtime_binding"))
    sources = {
        "model": [("run_meta", run_meta, "model"), ("explicit", explicit, "model")],
        "llm_mode": [
            ("run_meta", run_meta, "llm_mode"),
            ("explicit", explicit, "llm_mode"),
        ],
        "llm_endpoint": [
            ("run_meta", run_meta, "llm_endpoint"),
            ("explicit", explicit, "llm_endpoint"),
        ],
        "prompt_version": [
            ("run_meta", run_meta, "prompt_version"),
            ("explicit", explicit, "prompt_version"),
        ],
        "config_hash": [
            ("run_meta", run_meta, "config_hash"),
            ("explicit", explicit, "config_hash"),
        ],
        "runtime_fingerprint": [
            ("run_meta", run_meta, "runtime_release_fingerprint_sha256"),
            ("run_meta", run_meta, "stable_runtime_fingerprint_sha256"),
            ("run_meta", run_meta, "runtime_fingerprint_sha256"),
            ("explicit", explicit, "runtime_release_fingerprint_sha256"),
            ("explicit", explicit, "stable_runtime_fingerprint_sha256"),
            ("explicit", explicit, "runtime_fingerprint_sha256"),
        ],
    }
    payload: dict[str, Any] = {}
    issues: list[str] = []
    for field, field_sources in sources.items():
        present_values = [
            (source, key, owner[key])
            for source, owner, key in field_sources
            if key in owner
        ]
        values: list[str] = []
        for source, key, value in present_values:
            if not isinstance(value, str) or not value or value != value.strip():
                issues.append(f"runtime_signature_{field}_{source}_{key}_invalid")
                continue
            if field == "runtime_fingerprint" and re.fullmatch(r"[0-9a-f]{64}", value) is None:
                issues.append(f"runtime_signature_{field}_{source}_{key}_invalid")
                continue
            values.append(value)
        payload[field] = values[0] if values else None
        if len(set(values)) > 1:
            issues.append(f"runtime_signature_{field}_surface_mismatch")
    issues.extend(
        f"runtime_signature_{field}_missing" for field, value in payload.items() if value is None
    )
    if issues:
        return None, issues, payload
    signature = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return signature, [], payload


def row_identity(row: dict[str, Any]) -> dict[str, Any]:
    row = unwrap_result_row(row)
    analysis = row.get("analysis_result")
    if isinstance(analysis, dict) and isinstance(analysis.get("identity"), dict):
        return analysis["identity"]
    identity = row.get("identity")
    return identity if isinstance(identity, dict) else {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _first_text(*values: Any) -> str | None:
    for value in values:
        normalized = _optional_text(value)
        if normalized is not None:
            return normalized
    return None


def _typed_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _unique_text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for item in value:
        text = _optional_text(item)
        if text is None or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _contract_surface_conflicts(
    *,
    identity: dict[str, Any],
    ledger: dict[str, Any],
    decision: dict[str, Any],
    trace: dict[str, Any],
    trace_decision: dict[str, Any],
    promotion_state: dict[str, Any],
    public_title: str | None,
    public_url: str | None,
    candidate_title: str | None,
    candidate_url: str | None,
) -> list[str]:
    issues: list[str] = []

    def compare(label: str, values: list[tuple[str, Any]]) -> None:
        present = [
            (source, value)
            for source, value in values
            if value is not None and not (isinstance(value, dict) and not value)
        ]
        canonical = {_json_value(value) for _source, value in present}
        if len(canonical) > 1:
            issues.append(f"{label}_surface_mismatch")

    identity_decision = _mapping(identity.get("promotion_decision"))
    identity_state = _mapping(identity.get("promotion_gate_state"))
    identity_publish_ledger = _mapping(identity.get("publish_ledger"))
    ledger_decision = _mapping(ledger.get("promotion_decision"))
    ledger_state = _mapping(ledger.get("promotion_gate_state"))
    ledger_trace = _mapping(ledger.get("publish_contract_trace"))
    ledger_publish_ledger = _mapping(ledger.get("publish_ledger"))
    decision_surfaces = [
        ("identity", identity_decision),
        ("trace", trace_decision),
        ("ledger", ledger_decision),
        ("identity_publish_ledger", _mapping(identity_publish_ledger.get("gate_decision"))),
        ("ledger_publish_ledger", _mapping(ledger_publish_ledger.get("gate_decision"))),
    ]
    for field in (
        "status",
        "publish_allowed",
        "official_title",
        "official_url",
        "candidate_preserved",
        "bypassed_gate",
        "reason_codes",
        "input_fingerprint",
        "contract_version",
    ):
        compare(
            f"promotion_decision_{field}",
            [
                (source, surface.get(field) if field in surface else None)
                for source, surface in decision_surfaces
                if surface
            ],
        )

    compare(
        "publish_contract_input_fingerprint",
        [
            ("decision", decision.get("input_fingerprint")),
            ("trace", trace.get("input_fingerprint")),
            ("identity", identity.get("publish_contract_input_fingerprint")),
            ("ledger", ledger.get("publish_contract_input_fingerprint")),
        ],
    )
    compare(
        "publish_contract_version",
        [
            ("decision", decision.get("contract_version")),
            ("trace", trace.get("contract_version")),
            ("identity", identity.get("publish_contract_version")),
            ("ledger", ledger.get("publish_contract_version")),
        ],
    )
    compare(
        "promotion_scope",
        [
            ("decision", _mapping(decision.get("scope"))),
            ("trace", _mapping(trace.get("scope_state"))),
            ("state", _mapping(promotion_state.get("scope"))),
            ("ledger", _mapping(ledger_decision.get("scope"))),
            (
                "identity_publish_ledger",
                _mapping(_mapping(identity_publish_ledger.get("gate_decision")).get("scope")),
            ),
            (
                "ledger_publish_ledger",
                _mapping(_mapping(ledger_publish_ledger.get("gate_decision")).get("scope")),
            ),
        ],
    )
    compare(
        "trace_reason_codes",
        [
            ("decision", decision.get("reason_codes")),
            ("identity_trace", trace.get("reason_codes")),
            ("ledger_trace", ledger_trace.get("reason_codes")),
        ],
    )
    compare(
        "trace_bypassed_gate",
        [
            ("decision", decision.get("bypassed_gate")),
            ("identity_trace", trace.get("bypassed_gate")),
            ("ledger_trace", ledger_trace.get("bypassed_gate")),
        ],
    )
    compare(
        "promotion_gate_state",
        [("identity", identity_state), ("ledger", ledger_state)],
    )
    compare(
        "promotion_gate_evidence",
        [
            (
                "identity",
                identity.get("promotion_gate_evidence")
                if isinstance(identity.get("promotion_gate_evidence"), list)
                else None,
            ),
            (
                "ledger",
                ledger.get("promotion_gate_evidence")
                if isinstance(ledger.get("promotion_gate_evidence"), list)
                else None,
            ),
        ],
    )
    compare(
        "publish_contract_trace",
        [("identity", trace), ("ledger", ledger_trace)],
    )
    compare(
        "publish_ledger",
        [("identity", identity_publish_ledger), ("ledger", ledger_publish_ledger)],
    )

    def identity_pair(surface: dict[str, Any]) -> dict[str, str | None]:
        return {
            "title": _first_text(surface.get("official_title"), surface.get("candidate_title")),
            "url": _first_text(
                surface.get("official_url"), surface.get("heretic_url"), surface.get("candidate_url")
            ),
        }

    compare(
        "candidate_identity",
        [
            ("identity_state", identity_pair(identity_state)),
            ("ledger_state", identity_pair(ledger_state)),
            ("trace_pre_gate", identity_pair(_mapping(trace.get("pre_gate_candidate")))),
            (
                "identity_publish_ledger",
                identity_pair(_mapping(identity_publish_ledger.get("candidate_preservation"))),
            ),
            (
                "ledger_publish_ledger",
                identity_pair(_mapping(ledger_publish_ledger.get("candidate_preservation"))),
            ),
        ],
    )
    compare(
        "blocked_candidate_identity",
        [
            (
                "identity",
                {
                    "title": _optional_text(identity.get("blocked_official_title")),
                    "url": _optional_text(identity.get("blocked_official_title_url")),
                },
            )
            if "blocked_official_title" in identity or "blocked_official_title_url" in identity
            else ("identity", None),
            (
                "ledger",
                {
                    "title": _optional_text(ledger.get("blocked_official_title")),
                    "url": _optional_text(ledger.get("blocked_official_title_url")),
                },
            )
            if "blocked_official_title" in ledger or "blocked_official_title_url" in ledger
            else ("ledger", None),
        ],
    )
    public_identity_values: list[tuple[str, Any]] = [
        ("serialized", {"title": public_title, "url": public_url}),
        ("trace_post_gate", identity_pair(_mapping(trace.get("post_gate_identity")))),
        (
            "identity_publish_ledger",
            identity_pair(_mapping(identity_publish_ledger.get("public_publish"))),
        ),
        (
            "ledger_publish_ledger",
            identity_pair(_mapping(ledger_publish_ledger.get("public_publish"))),
        ),
    ]
    if _typed_bool(decision.get("publish_allowed")) is True:
        public_identity_values.append(("decision", identity_pair(decision)))
    compare("public_identity", public_identity_values)

    contract_version = _first_text(
        decision.get("contract_version"),
        trace.get("contract_version"),
        identity.get("publish_contract_version"),
        ledger.get("publish_contract_version"),
    )
    if decision and contract_version != "promotion_contract_v2":
        issues.append("publish_contract_version_unsupported")
    if contract_version == "promotion_contract_v2":
        required_mapping_surfaces = (
            ("identity_promotion_decision", identity_decision),
            ("identity_promotion_gate_state", identity_state),
            ("identity_publish_contract_trace", trace),
            ("identity_publish_ledger", identity_publish_ledger),
            ("trace_gate_decision", trace_decision),
            ("trace_scope_state", _mapping(trace.get("scope_state"))),
            ("trace_post_gate_identity", _mapping(trace.get("post_gate_identity"))),
            ("candidate_ledger", ledger),
            ("ledger_promotion_decision", ledger_decision),
            ("ledger_promotion_gate_state", ledger_state),
            ("ledger_publish_contract_trace", ledger_trace),
            ("ledger_publish_ledger", ledger_publish_ledger),
            (
                "identity_publish_ledger_gate_decision",
                _mapping(identity_publish_ledger.get("gate_decision")),
            ),
            (
                "ledger_publish_ledger_gate_decision",
                _mapping(ledger_publish_ledger.get("gate_decision")),
            ),
        )
        for label, surface in required_mapping_surfaces:
            if not surface:
                issues.append(f"{label}_missing")
        for label, owner in (("identity", identity), ("ledger", ledger)):
            if "promotion_gate_evidence" not in owner:
                issues.append(f"{label}_promotion_gate_evidence_missing")
            elif not isinstance(owner.get("promotion_gate_evidence"), list):
                issues.append(f"{label}_promotion_gate_evidence_invalid")
            fingerprint = _optional_text(owner.get("publish_contract_input_fingerprint"))
            if fingerprint is None:
                issues.append(f"{label}_publish_contract_input_fingerprint_missing")
            elif re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
                issues.append(f"{label}_publish_contract_input_fingerprint_invalid")
            if owner.get("publish_contract_version") != "promotion_contract_v2":
                issues.append(f"{label}_publish_contract_version_missing_or_mismatch")
        if trace.get("contract_version") != "promotion_contract_v2":
            issues.append("trace_contract_version_missing_or_mismatch")
        trace_fingerprint = _optional_text(trace.get("input_fingerprint"))
        if trace_fingerprint is None:
            issues.append("trace_input_fingerprint_missing")
        elif re.fullmatch(r"[0-9a-f]{64}", trace_fingerprint) is None:
            issues.append("trace_input_fingerprint_invalid")

    post_gate_identity = _mapping(trace.get("post_gate_identity"))
    if post_gate_identity:
        if _optional_text(post_gate_identity.get("official_title")) != public_title:
            issues.append("post_gate_public_title_mismatch")
        if _first_text(
            post_gate_identity.get("official_url"), post_gate_identity.get("heretic_url")
        ) != public_url:
            issues.append("post_gate_public_url_mismatch")

    publish_allowed = _typed_bool(decision.get("publish_allowed"))
    if publish_allowed is True:
        if _optional_text(decision.get("official_title")) != public_title:
            issues.append("published_title_decision_surface_mismatch")
        if _optional_text(decision.get("official_url")) != public_url:
            issues.append("published_url_decision_surface_mismatch")
    elif publish_allowed is False and (public_title is not None or public_url is not None):
        issues.append("nonpublic_decision_has_stale_public_identity")
    expected_ledger_status = None
    if publish_allowed is True:
        expected_ledger_status = "safe_resolved"
    elif publish_allowed is False:
        expected_ledger_status = (
            "promotion_blocked"
            if candidate_title is not None
            or candidate_url is not None
            or decision.get("candidate_preserved") is True
            else "hold_without_candidates"
        )
    if expected_ledger_status is not None and identity.get("candidate_ledger_status") != expected_ledger_status:
        issues.append("candidate_ledger_status_decision_mismatch")
    if (
        expected_ledger_status is not None
        and "candidate_ledger_status" in ledger
        and ledger.get("candidate_ledger_status") != expected_ledger_status
    ):
        issues.append("ledger_candidate_ledger_status_decision_mismatch")

    if decision:
        decision_status = _optional_text(decision.get("status"))
        if decision_status is None:
            issues.append("promotion_decision_status_missing_or_invalid")
        for field in ("publish_allowed", "candidate_preserved", "bypassed_gate"):
            if _typed_bool(decision.get(field)) is None:
                issues.append(f"promotion_decision_{field}_missing_or_invalid")
        reason_codes = decision.get("reason_codes")
        if not isinstance(reason_codes, list) or any(
            not isinstance(code, str) or not code.strip() for code in reason_codes
        ):
            issues.append("promotion_decision_reason_codes_missing_or_invalid")
        fingerprint = _optional_text(decision.get("input_fingerprint"))
        if fingerprint is not None and re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
            issues.append("promotion_decision_input_fingerprint_invalid")
        if _optional_text(decision.get("contract_version")) is None:
            issues.append("promotion_decision_contract_version_missing_or_invalid")
        decision_reason_codes = set(_unique_text_list(decision.get("reason_codes")))
        decision_scope_kind = _optional_text(_mapping(decision.get("scope")).get("scope_kind"))
        noncurrent_reason_codes = {
            "scope_not_current_work",
            "scope_context_only",
            "scope_platform_meta_nonwork",
            "scope_unknown",
            "scope_unclassified",
            "row_discussion_missing",
            "nonwork",
            "community_banter",
        }
        if "serialized_public_identity_published" in decision_reason_codes and "serialized_public_identity_scrubbed" in decision_reason_codes:
            issues.append("published_and_scrubbed_reason_conflict")
        if publish_allowed is True:
            if decision_status != "publish":
                issues.append("publish_allowed_decision_status_mismatch")
            if _typed_bool(decision.get("candidate_preserved")) is not False:
                issues.append("publish_allowed_candidate_preserved_mismatch")
            if public_title is None:
                issues.append("publish_allowed_public_title_missing")
            if decision_scope_kind != "current_work":
                issues.append("publish_allowed_scope_not_current_work")
            if "serialized_public_identity_scrubbed" in decision_reason_codes:
                issues.append("publish_allowed_scrubbed_reason_present")
        elif publish_allowed is False:
            if decision_status == "publish":
                issues.append("nonpublic_decision_status_publish")
            if decision_status == "candidate_only" and _typed_bool(
                decision.get("candidate_preserved")
            ) is not True:
                issues.append("candidate_only_candidate_preserved_missing")
            if decision_status == "candidate_only" and candidate_title is None:
                issues.append("candidate_only_candidate_title_missing")
            if "serialized_public_identity_published" in decision_reason_codes:
                issues.append("nonpublic_decision_published_reason_present")
        if decision_scope_kind == "current_work":
            if "scope_current_work" not in decision_reason_codes:
                issues.append("scope_current_work_reason_missing")
            if "row_discusses_work_as_work" not in decision_reason_codes:
                issues.append("current_work_discussion_reason_missing")
            if decision_reason_codes & noncurrent_reason_codes:
                issues.append("current_work_noncurrent_reason_conflict")
        elif decision_scope_kind is not None:
            expected_scope_reason = (
                "scope_unknown"
                if decision_scope_kind == "unknown"
                else f"scope_{decision_scope_kind}"
            )
            if expected_scope_reason not in decision_reason_codes:
                issues.append("noncurrent_scope_specific_reason_missing")
            if "scope_not_current_work" not in decision_reason_codes:
                issues.append("noncurrent_scope_reason_missing")
            if {
                "scope_current_work",
                "row_discusses_work_as_work",
            } & decision_reason_codes:
                issues.append("noncurrent_scope_current_work_reason_conflict")
    return sorted(set(issues))


def row_outcome(row: dict[str, Any]) -> dict[str, Any]:
    row = unwrap_result_row(row)
    identity = row_identity(row)
    novel = _mapping(identity.get("novel_identity"))
    ledger = _mapping(identity.get("candidate_ledger"))
    trace = _mapping(identity.get("publish_contract_trace"))
    trace_decision = _mapping(trace.get("gate_decision"))
    decision = _mapping(identity.get("promotion_decision")) or trace_decision or _mapping(
        ledger.get("promotion_decision")
    )
    promotion_state = _mapping(identity.get("promotion_gate_state"))
    state_scope = _mapping(promotion_state.get("scope"))
    scope = (
        _mapping(decision.get("scope"))
        or _mapping(trace.get("scope_state"))
        or state_scope
    )

    # Public identity is read only from the serialized public surface.  A blocked
    # candidate must never be silently upgraded to public identity here.
    public_title = _first_text(
        novel.get("official_title"),
        identity.get("official_title"),
        identity.get("official_novel_title"),
    )
    public_url = _first_text(
        novel.get("heretic_url"),
        novel.get("official_url"),
        identity.get("heretic_url"),
        identity.get("official_url"),
    )

    publish_allowed = _typed_bool(decision.get("publish_allowed"))
    candidate_title = _first_text(
        identity.get("blocked_official_title"),
        ledger.get("blocked_official_title"),
    )
    candidate_url = _first_text(
        identity.get("blocked_official_title_url"),
        ledger.get("blocked_official_title_url"),
    )
    if publish_allowed is not True:
        pre_gate = _mapping(trace.get("pre_gate_candidate"))
        candidate_title = candidate_title or _first_text(
            promotion_state.get("candidate_title"),
            decision.get("official_title"),
            pre_gate.get("official_title"),
        )
        candidate_url = candidate_url or _first_text(
            promotion_state.get("candidate_url"),
            decision.get("official_url"),
            pre_gate.get("official_url"),
        )

    # Keep the legacy status/title/url surface for existing blind-judge files.
    # New contracts must use public_* and candidate_* to avoid the old fallback
    # ambiguity where a blocked candidate appeared in `title`/`url`.
    title = public_title or candidate_title or ""
    url = public_url or candidate_url or ""
    status = identity.get("candidate_ledger_status") or row.get("candidate_ledger_status") or ""
    raw_reason_codes = decision.get("reason_codes")
    if not isinstance(raw_reason_codes, (list, tuple)):
        raw_reason_codes = trace.get("reason_codes")
    reason_codes = (
        [str(code).strip() for code in raw_reason_codes if isinstance(code, str) and code.strip()]
        if isinstance(raw_reason_codes, (list, tuple))
        else []
    )
    direct_bridge_sources = _unique_text_list(state_scope.get("direct_bridge_sources"))
    if not direct_bridge_sources:
        direct_bridge_sources = _unique_text_list(scope.get("direct_bridge_sources"))
    raw_evidence = identity.get("promotion_gate_evidence")
    if not isinstance(raw_evidence, list):
        raw_evidence = ledger.get("promotion_gate_evidence")
    evidence_kinds: list[str] = []
    evidence_reason_codes: list[str] = []
    publish_supporting_evidence_kinds: list[str] = []
    publish_supporting_evidence_reason_codes: list[str] = []
    relevant_evidence_title = public_title if publish_allowed is True else candidate_title
    relevant_evidence_url = public_url if publish_allowed is True else candidate_url
    if isinstance(raw_evidence, list):
        for item in raw_evidence:
            evidence = _mapping(item)
            kind = _optional_text(evidence.get("kind"))
            if kind is not None and kind not in evidence_kinds:
                evidence_kinds.append(kind)
            item_reason_codes = _unique_text_list(evidence.get("reason_codes"))
            singular_reason = _optional_text(evidence.get("reason_code"))
            if singular_reason is not None:
                item_reason_codes.insert(0, singular_reason)
            for code in item_reason_codes:
                if code not in evidence_reason_codes:
                    evidence_reason_codes.append(code)
            evidence_title = _optional_text(evidence.get("candidate_title"))
            evidence_url = _optional_text(evidence.get("candidate_url"))
            candidate_matches = (
                (evidence_title is None or evidence_title == relevant_evidence_title)
                and (evidence_url is None or evidence_url == relevant_evidence_url)
            )
            supports_publish = evidence.get("supports_publish") is True
            title_url_match = evidence.get("title_url_match")
            if supports_publish and title_url_match is not False and candidate_matches:
                if kind is not None and kind not in publish_supporting_evidence_kinds:
                    publish_supporting_evidence_kinds.append(kind)
                for code in item_reason_codes:
                    if code not in publish_supporting_evidence_reason_codes:
                        publish_supporting_evidence_reason_codes.append(code)
    contract_version = _first_text(
        decision.get("contract_version"),
        trace.get("contract_version"),
        identity.get("publish_contract_version"),
        ledger.get("publish_contract_version"),
    )
    input_fingerprint = _first_text(
        decision.get("input_fingerprint"),
        trace.get("input_fingerprint"),
        identity.get("publish_contract_input_fingerprint"),
        ledger.get("publish_contract_input_fingerprint"),
    )
    contract_consistency_issues = _contract_surface_conflicts(
        identity=identity,
        ledger=ledger,
        decision=decision,
        trace=trace,
        trace_decision=trace_decision,
        promotion_state=promotion_state,
        public_title=public_title,
        public_url=public_url,
        candidate_title=candidate_title,
        candidate_url=candidate_url,
    )
    canonical_contract_audit = audit_publication_contract_row(row, index=1)
    canonical_violation_codes = [
        str(violation.get("code") or "").strip()
        for violation in canonical_contract_audit.get("violations") or []
        if isinstance(violation, dict) and str(violation.get("code") or "").strip()
    ]
    inventory_evidence = candidate_inventory_evidence_from_sources(
        identity.get("title_candidates"),
        identity.get("candidate_preservation_sources"),
        ledger.get("title_candidates"),
        ledger.get("candidate_preservation_sources"),
    )
    typed_inventory_evidence = tuple(
        record
        for record in evidence_records_from_payload(raw_evidence if isinstance(raw_evidence, list) else [])
        if record.kind == "candidate_preservation" and not record.supports_publish
    )
    inventory_pairs = sorted(
        candidate_inventory_pairs((*inventory_evidence, *typed_inventory_evidence))
    )
    return {
        "status": str(status or "").strip(),
        "title": str(title or "").strip(),
        "url": str(url or "").strip(),
        "public_title": public_title,
        "public_url": public_url,
        "candidate_title": candidate_title,
        "candidate_url": candidate_url,
        "decision_status": _optional_text(decision.get("status")),
        "publish_allowed": publish_allowed,
        "candidate_preserved": _typed_bool(decision.get("candidate_preserved")),
        "bypassed_gate": _typed_bool(
            decision.get("bypassed_gate")
            if "bypassed_gate" in decision
            else trace.get("bypassed_gate")
        ),
        "reason_codes": reason_codes,
        "scope_kind": _optional_text(scope.get("scope_kind")),
        "direct_bridge_sources": direct_bridge_sources,
        "evidence_kinds": evidence_kinds,
        "evidence_reason_codes": evidence_reason_codes,
        "publish_supporting_evidence_kinds": publish_supporting_evidence_kinds,
        "publish_supporting_evidence_reason_codes": publish_supporting_evidence_reason_codes,
        "candidate_inventory_pairs": [
            {"title": title or None, "url": url or None}
            for title, url in inventory_pairs
        ],
        "contract_consistency_issues": contract_consistency_issues,
        "canonical_publication_contract_gate": canonical_contract_audit.get("gate"),
        "canonical_publication_contract_violation_codes": canonical_violation_codes,
        "contract_version": contract_version,
        "input_fingerprint": input_fingerprint,
    }


SEMANTIC_DECISION_SURFACE_FIELDS = (
    "public_title",
    "public_url",
    "candidate_title",
    "candidate_url",
    "decision_status",
    "publish_allowed",
    "candidate_preserved",
    "bypassed_gate",
    "scope_kind",
    "canonical_publication_contract_gate",
    "canonical_publication_contract_violation_codes",
)


def semantic_decision_surface(outcome: dict[str, Any]) -> dict[str, Any]:
    """Return only the publication decision surface used for semantic flip gating.

    The complete ``row_outcome`` remains authoritative for blind-judge matching and
    diagnostics.  Volatile provenance and evidence inventory fields are deliberately
    excluded here: their variance must be reviewed, but it is not a title publication
    decision flip when the serialized/public/candidate decision is identical.
    """

    violation_codes = outcome.get("canonical_publication_contract_violation_codes")
    if isinstance(violation_codes, list):
        normalized_violations: Any = sorted(
            {
                str(code).strip()
                for code in violation_codes
                if isinstance(code, str) and str(code).strip()
            }
        )
    else:
        # Preserve malformedness on the semantic surface.  The safety evaluator also
        # marks this fail-closed, so malformed values can never become a GO by being
        # normalized to an empty list.
        normalized_violations = None
    surface = {field: outcome.get(field) for field in SEMANTIC_DECISION_SURFACE_FIELDS}
    surface["canonical_publication_contract_violation_codes"] = normalized_violations
    return surface


def semantic_decision_surface_key(outcome: dict[str, Any]) -> str:
    return json.dumps(
        semantic_decision_surface(outcome),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _outcome_safety_evaluation(outcome: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed structural safety check independent of blind-judge correctness."""

    reasons: list[str] = []
    consistency_issues = outcome.get("contract_consistency_issues")
    if not isinstance(consistency_issues, list):
        reasons.append("contract_consistency_issues_malformed")
    elif consistency_issues:
        reasons.append("contract_consistency_issues_present")

    canonical_gate = outcome.get("canonical_publication_contract_gate")
    if canonical_gate != "GO":
        reasons.append("canonical_publication_contract_gate_not_go")
    violation_codes = outcome.get("canonical_publication_contract_violation_codes")
    if not isinstance(violation_codes, list):
        reasons.append("canonical_publication_contract_violation_codes_malformed")
    elif violation_codes:
        reasons.append("canonical_publication_contract_violations_present")

    decision_status = outcome.get("decision_status")
    publish_allowed = outcome.get("publish_allowed")
    candidate_preserved = outcome.get("candidate_preserved")
    bypassed_gate = outcome.get("bypassed_gate")
    scope_kind = outcome.get("scope_kind")
    if decision_status not in {"publish", "candidate_only", "hold", "quarantine"}:
        reasons.append("decision_status_missing_or_invalid")
    if not isinstance(publish_allowed, bool):
        reasons.append("publish_allowed_missing_or_invalid")
    if not isinstance(candidate_preserved, bool):
        reasons.append("candidate_preserved_missing_or_invalid")
    if bypassed_gate is not False:
        reasons.append("bypassed_gate_not_false")
    if not isinstance(scope_kind, str) or not scope_kind.strip():
        reasons.append("scope_kind_missing_or_invalid")

    public_title = outcome.get("public_title")
    public_url = outcome.get("public_url")
    if publish_allowed is True:
        if decision_status != "publish":
            reasons.append("publish_allowed_status_mismatch")
        if candidate_preserved is not False:
            reasons.append("publish_allowed_candidate_preserved_mismatch")
        if not isinstance(public_title, str) or not public_title.strip():
            reasons.append("publish_allowed_public_title_missing")
        if scope_kind != "current_work":
            reasons.append("publish_allowed_scope_not_current_work")
    elif publish_allowed is False:
        if decision_status == "publish":
            reasons.append("nonpublic_status_publish")
        if public_title is not None or public_url is not None:
            reasons.append("nonpublic_serialized_identity_present")

    unique_reasons = list(dict.fromkeys(reasons))
    return {"safe": not unique_reasons, "unsafe_reasons": unique_reasons}


def build_probe_input(
    *,
    source_rows: list[dict[str, Any]],
    post_ids: list[str],
    repeats: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    assert_unique_post_ids(post_ids, label="requested")
    source_post_ids = [post_id_key(row.get("post_id")) for row in source_rows]
    assert_unique_post_ids(source_post_ids, label="source")
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
    path.write_text(probe_input_text(rows), encoding="utf-8", newline="\n")


def probe_input_text(rows: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
        )
        + "\n"
    )


def _with_noninteractive_watchdog_args(args: list[str]) -> list[str]:
    """Keep background probe processes from waiting for terminal/web resume."""
    out = list(args)
    if "--llm-suspend-on-anomaly" not in out:
        out.extend(["--llm-suspend-on-anomaly", "off"])
    if "--llm-suspend-threshold" not in out:
        out.extend(["--llm-suspend-threshold", "0"])
    if "--llm-stream-first-token-timeout" not in out:
        out.extend(["--llm-stream-first-token-timeout", "45"])
    if "--llm-stream-idle-timeout" not in out:
        out.extend(["--llm-stream-idle-timeout", "45"])
    return out


def parse_required_env_entries(values: list[str]) -> dict[str, str]:
    required_env: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"--required-env expects KEY=VALUE, got: {raw}")
        key, value = raw.split("=", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None:
            raise ValueError(f"invalid --required-env key: {key}")
        if value == "":
            raise ValueError(f"empty --required-env value for: {key}")
        if key in required_env:
            raise ValueError(f"duplicate --required-env key: {key}")
        required_env[key] = value
    return required_env


def _runtime_contract_payload(
    *,
    model: str | None,
    llm_mode: str | None,
    llm_endpoint: str | None,
    prompt_version: str | None,
    runtime_release_fingerprint_sha256: str | None,
    required_env: dict[str, str] | None,
) -> tuple[dict[str, Any], dict[str, str]]:
    values = {
        "model": model,
        "llm_mode": llm_mode,
        "llm_endpoint": llm_endpoint,
        "prompt_version": prompt_version,
        "runtime_release_fingerprint_sha256": runtime_release_fingerprint_sha256,
    }
    present = [value is not None for value in values.values()]
    if not any(present):
        return {}, dict(required_env or {})
    if not all(present):
        missing = sorted(field for field, value in values.items() if value is None)
        raise ValueError(f"incomplete runtime contract fields: {missing}")
    for field, value in values.items():
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError(f"invalid runtime contract {field}")
    fingerprint = str(runtime_release_fingerprint_sha256)
    if re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise ValueError("runtime release fingerprint must be raw lowercase sha256")
    merged_required_env = dict(required_env or {})
    for env_name, contract_field in RUNTIME_BINDING_ENV_FIELDS.items():
        expected = str(values[contract_field])
        if env_name in merged_required_env and merged_required_env[env_name] != expected:
            raise ValueError(f"required_env conflicts with runtime contract: {env_name}")
        merged_required_env[env_name] = expected
    contract = {
        **values,
        "config_hash_policy": ROW_DERIVED_CONFIG_HASH_POLICY,
        "required_env": dict(merged_required_env),
    }
    return contract, merged_required_env


def _ensure_exact_option(argv: list[str], option: str, expected: str) -> None:
    values = _argv_option_values(argv, option)
    if not values:
        argv.extend([option, expected])
    elif values != [expected]:
        raise ValueError(f"conflicting or duplicate expert argument: {option}={values}")


def _ensure_exact_flag(argv: list[str], flag: str) -> None:
    count = argv.count(flag)
    if count == 0:
        argv.append(flag)
    elif count != 1:
        raise ValueError(f"duplicate expert argument: {flag}")


def build_independent_run_plan(
    *,
    source_rows: list[dict[str, Any]],
    post_ids: list[str],
    repeats: int,
    work_dir: Path,
    run_prefix: str,
    python_executable: str,
    expert_main: Path,
    parallel: int = 16,
    expert_args: list[str] | None = None,
    minimum_repeats: int = 5,
    runtime_model: str | None = None,
    runtime_llm_mode: str | None = None,
    runtime_llm_endpoint: str | None = None,
    runtime_prompt_version: str | None = None,
    runtime_release_fingerprint_sha256: str | None = None,
    required_env: dict[str, str] | None = None,
    blind_judge: Path | None = None,
    run_plan_path: Path | None = None,
    analysis_output_json: Path | None = None,
    analysis_output_md: Path | None = None,
    source_input_path: Path | None = None,
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    assert_unique_post_ids(post_ids, label="requested")
    source_post_ids = [post_id_key(row.get("post_id")) for row in source_rows]
    assert_unique_post_ids(source_post_ids, label="source")
    if len(post_ids) != N5_POST_ID_COUNT:
        raise ValueError("build-run-plan requires exactly five post_ids")
    if repeats != N5_REPEAT_COUNT:
        raise ValueError("build-run-plan requires exactly five repeats")
    if minimum_repeats != N5_REPEAT_COUNT:
        raise ValueError("build-run-plan minimum_repeats must be exactly five")
    if blind_judge is None:
        raise ValueError("build-run-plan requires an immutable blind judge")
    by_id: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        pid = post_id_key(row.get("post_id"))
        if pid and pid not in by_id:
            by_id[pid] = row

    missing = [pid for pid in post_ids if pid not in by_id]
    safe_prefix = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in run_prefix).strip("_")
    if not safe_prefix:
        safe_prefix = "safe_loss_flip_probe"
    runtime_contract, plan_required_env = _runtime_contract_payload(
        model=runtime_model,
        llm_mode=runtime_llm_mode,
        llm_endpoint=runtime_llm_endpoint,
        prompt_version=runtime_prompt_version,
        runtime_release_fingerprint_sha256=runtime_release_fingerprint_sha256,
        required_env=required_env,
    )
    raw_expert_args = list(expert_args or [])
    expert_args = _with_noninteractive_watchdog_args(strip_no_dashboard(raw_expert_args))
    for option, expected in (
        ("--slang-db", "off"),
        ("--vlm", "on"),
        ("--ocr", "on"),
    ):
        _ensure_exact_option(expert_args, option, expected)
    for flag in ("--reuse-shards-only", "--require-vlm-ocr-for-images"):
        _ensure_exact_flag(expert_args, flag)
    if runtime_contract:
        _ensure_exact_option(expert_args, "--llm-model", str(runtime_contract["model"]))
        _ensure_exact_option(
            expert_args, "--llm-endpoint", str(runtime_contract["llm_endpoint"])
        )
    input_dir = work_dir / "inputs"
    result_dir = work_dir / "results"
    execution_anchor = work_dir / ".independent_plan_execution" / safe_prefix
    execution_attempts_dir = execution_anchor / "attempts"
    execution_adoptions_dir = execution_anchor / "adoptions"
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
            input_sha256 = hashlib.sha256(probe_input_text([row]).encode("utf-8")).hexdigest()
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
                    "input_post_id": pid,
                    "input_row_count": 1,
                    "input_sha256": input_sha256,
                    "output_json": str(output_path),
                    "checkpoint_jsonl": str(output_path.with_name(output_path.stem + "_checkpoint.jsonl")),
                    "manifest_json": str(output_path.with_name(output_path.stem + "_manifest.json")),
                    "attempt_dir": str(execution_attempts_dir / stem),
                    "adopted_completion_receipt_json": str(
                        execution_adoptions_dir / f"{stem}.adopted.json"
                    ),
                    "command_argv": argv,
                    "command_line": subprocess.list2cmdline(argv),
                    "attach_dashboard_command_line": attach_dashboard_command(
                        output_path.with_name(output_path.stem + "_manifest.json"),
                        python_executable=python_executable,
                    ),
                    "required_env": dict(plan_required_env),
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
    blind_judge_path = blind_judge
    blind_judge_binding = _blind_judge_binding(
        blind_judge_path,
        post_ids=post_ids,
        repeats=repeats,
    )
    plan_artifact_path = run_plan_path or work_dir / f"{safe_prefix}_run_plan.json"
    analysis_json_path = analysis_output_json or work_dir / f"{safe_prefix}_analysis.json"
    analysis_md_path = analysis_output_md or work_dir / f"{safe_prefix}_analysis.md"
    analyze_argv.extend(
        [
            "--post-ids",
            ",".join(post_ids),
            "--repeats",
            str(max(1, repeats)),
            "--blind-judge",
            str(blind_judge_path),
            "--run-plan",
            str(plan_artifact_path),
            "--require-runtime-contract",
            "--output-json",
            str(analysis_json_path),
            "--output-md",
            str(analysis_md_path),
            "--fail-on-no-go",
        ]
    )

    manifest = {
        "manifest_type": "safe_loss_flip_rate_probe_independent_run_plan",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "source_input": str(source_input_path) if source_input_path is not None else "",
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
        "runtime_contract": runtime_contract,
        "required_env": dict(plan_required_env),
        "noninteractive_watchdog_contract": "background_probe_commands_disable_llm_suspend_prompt",
        "requested_parallel_policy": "test_run_requested_parallel_locked_to_16_by_user",
        "dashboard_contract": dashboard_contract(python_executable=python_executable),
        "stripped_forbidden_expert_args": [
            str(arg) for arg in raw_expert_args if str(arg).strip() == "--no-dashboard"
        ],
        "input_surface_contract": "Each generated JSONL contains exactly one copied source row and no _flip_probe metadata.",
        "aggregation_contract": "Analyze all per-repeat result JSON files together with the same post_ids and repeats value.",
        "blind_judge": str(blind_judge_path),
        "blind_judge_binding": blind_judge_binding,
        "run_plan_path": str(plan_artifact_path),
        "analysis_output_json": str(analysis_json_path),
        "analysis_output_md": str(analysis_md_path),
        "planned_runs": planned_runs,
        "analyze_command_argv": analyze_argv,
        "analyze_command_line": subprocess.list2cmdline(analyze_argv),
        "exclusive_create_contract": {
            "plan_and_inputs": "exclusive_create",
            "preexisting_runtime_or_analysis_artifacts": "fail_before_write",
            "overwrite_allowed": False,
        },
        "execution_claim_contract": {
            "version": "independent-plan-execution-claim-v3",
            "anchor_dir": str(execution_anchor),
            "persistent_plan_claim_json": str(execution_anchor / "plan.claim.json"),
            "active_lock_file": str(execution_anchor / "plan.active.lock"),
            "attempts_dir": str(execution_attempts_dir),
            "adoptions_dir": str(execution_adoptions_dir),
            "attempt_claim_pattern": "attempt_{index:03d}.claim.json",
            "attempt_terminal_receipt_pattern": "attempt_{index:03d}.terminal.json",
            "required_adopted_completion_count": N5_EXPECTED_RUN_COUNT,
            "one_adopted_attempt_per_post_repeat": True,
            "unrecorded_attempts_allowed": False,
            "indeterminate_attempts_allowed": False,
            "failed_child_rc_without_artifacts_may_retry": False,
            "complete_artifacts_without_terminal_may_recover": True,
            "global_runtime_path_claims_required": True,
            "runtime_path_overlap_allowed": False,
            "recovery_unknown_child_liveness_allowed": False,
            "recovery_artifact_quiescence_seconds": 0.1,
        },
    }
    manifest["plan_self_binding"] = _plan_self_binding(manifest)
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
            if pid in out:
                raise ValueError(f"duplicate blind judge post_id: {pid}")
            out[pid] = item
    return out


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_artifact_path(value: Any) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _lowercase_sha256(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must be a raw lowercase sha256")
    return value


def _validate_bound_file(
    binding: dict[str, Any],
    *,
    label: str,
    required_path: Path | None = None,
) -> dict[str, str]:
    path_value = binding.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError(f"{label} path missing or invalid")
    path = resolve_artifact_path(path_value)
    if required_path is not None and path != required_path.resolve():
        raise ValueError(f"{label} path is not the required current file")
    if not path.is_file():
        raise ValueError(f"{label} file not found")
    recorded = _lowercase_sha256(binding.get("sha256"), label=f"{label} sha256")
    actual = file_sha256(path)
    if actual != recorded:
        raise ValueError(f"{label} current byte sha256 mismatch")
    return {"path": str(path), "sha256": recorded}


def _blind_judge_binding(
    path: Path,
    *,
    post_ids: list[str],
    repeats: int,
) -> dict[str, Any]:
    """Validate and freeze the complete N5 judge trust root used by a run plan."""
    resolved = resolve_artifact_path(path)
    if not resolved.is_file():
        raise ValueError("blind judge file not found")
    payload = load_json(resolved)
    if not isinstance(payload, dict):
        raise ValueError("blind judge must be a JSON object")
    if len(post_ids) != N5_POST_ID_COUNT or len(set(post_ids)) != N5_POST_ID_COUNT:
        raise ValueError("blind judge binding requires exactly five unique post_ids")
    if repeats != N5_REPEAT_COUNT:
        raise ValueError("blind judge binding requires exactly five repeats")
    if payload.get("report_type") != N5_BLIND_JUDGE_REPORT_TYPE:
        raise ValueError("blind judge report_type mismatch")
    builder_version = payload.get("builder_version")
    if not isinstance(builder_version, str) or not builder_version.strip():
        raise ValueError("blind judge builder_version missing or invalid")
    if payload.get("gate") != "GO":
        raise ValueError("blind judge gate must be GO")
    if payload.get("semantic_quality") != "REVIEW-LOCKED":
        raise ValueError("blind judge semantic_quality must be REVIEW-LOCKED")
    for field in ("full_scan_approval", "production_approval"):
        if payload.get(field) is not False:
            raise ValueError(f"blind judge {field} must be false")

    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("blind judge scope missing or invalid")
    scope_post_ids = [post_id_key(value) for value in (scope.get("post_ids") or [])]
    if (
        len(scope_post_ids) != N5_POST_ID_COUNT
        or len(set(scope_post_ids)) != N5_POST_ID_COUNT
        or set(scope_post_ids) != set(post_ids)
    ):
        raise ValueError("blind judge scope post_ids mismatch")
    scope_expectations = {
        "post_id_count": N5_POST_ID_COUNT,
        "repeats_required": N5_REPEAT_COUNT,
        "expected_independent_result_count": N5_EXPECTED_RUN_COUNT,
        "missing_post_ids": [],
        "extra_post_ids": [],
        "duplicate_post_ids": [],
    }
    for field, expected in scope_expectations.items():
        if not _strict_equal(scope.get(field), expected):
            raise ValueError(f"blind judge scope {field} mismatch")

    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != N5_POST_ID_COUNT:
        raise ValueError("blind judge rows must contain exactly five objects")
    row_post_ids: list[str] = []
    acceptable_outcome_count_by_post: dict[str, int] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"blind judge row[{index}] must be an object")
        pid = post_id_key(row.get("post_id"))
        row_post_ids.append(pid)
        outcomes = row.get("acceptable_outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            raise ValueError(f"blind judge row[{index}] acceptable_outcomes missing")
        for outcome_index, outcome in enumerate(outcomes):
            if not isinstance(outcome, dict):
                raise ValueError(
                    f"blind judge row[{index}] acceptable_outcomes[{outcome_index}] invalid"
                )
            if set(outcome) & ACCEPTABLE_OUTCOME_LEGACY_FIELDS:
                raise ValueError("blind judge contains legacy acceptable outcome fields")
            if set(outcome) - OUTCOME_CONTRACT_FIELDS:
                raise ValueError("blind judge contains unknown acceptable outcome fields")
            if ACCEPTABLE_OUTCOME_REQUIRED_FIELDS - set(outcome):
                raise ValueError("blind judge acceptable outcome required fields missing")
            if outcome.get("bypassed_gate") is not False:
                raise ValueError("blind judge acceptable outcome permits gate bypass")
        acceptable_outcome_count_by_post[pid] = len(outcomes)
    if (
        len(set(row_post_ids)) != N5_POST_ID_COUNT
        or set(row_post_ids) != set(post_ids)
    ):
        raise ValueError("blind judge row post_ids mismatch")

    builder_binding = payload.get("builder_binding")
    if not isinstance(builder_binding, dict):
        raise ValueError("blind judge builder_binding missing or invalid")
    builder_file = _validate_bound_file(
        {"path": builder_binding.get("path"), "sha256": builder_binding.get("sha256")},
        label="blind judge builder",
        required_path=N5_BLIND_JUDGE_BUILDER,
    )
    matcher_file = _validate_bound_file(
        {
            "path": builder_binding.get("matcher_path"),
            "sha256": builder_binding.get("matcher_sha256"),
        },
        label="blind judge matcher",
        required_path=Path(__file__).resolve(),
    )
    normalized_builder_binding = {
        "path": builder_file["path"],
        "sha256": builder_file["sha256"],
        "matcher_path": matcher_file["path"],
        "matcher_sha256": matcher_file["sha256"],
    }

    source_bindings = payload.get("source_bindings")
    if not isinstance(source_bindings, dict) or not source_bindings:
        raise ValueError("blind judge source_bindings missing or invalid")
    source_file_records: list[dict[str, str]] = []
    for name in sorted(source_bindings):
        binding = source_bindings[name]
        if not isinstance(name, str) or not name or not isinstance(binding, dict):
            raise ValueError("blind judge source binding name or value invalid")
        validated = _validate_bound_file(binding, label=f"blind judge source binding {name}")
        source_file_records.append({"name": name, **validated})

    matcher_contract = payload.get("matcher_contract")
    if not isinstance(matcher_contract, dict):
        raise ValueError("blind judge matcher_contract missing or invalid")
    for field in (
        "wrong_title_or_work_allowed",
        "bypassed_gate_allowed",
        "unsafe_publish_allowed",
    ):
        if matcher_contract.get(field) is not False:
            raise ValueError(f"blind judge matcher_contract {field} must be false")

    required_derivation_bindings = {
        "source_manifest",
        "golden_manifest",
        "loop641_blind_adjudication",
        "independent_identity_evidence",
        "r6_golden_audit",
        "r6_result",
    }
    missing_derivation_bindings = sorted(
        required_derivation_bindings - set(source_bindings)
    )
    if missing_derivation_bindings:
        raise ValueError(
            "blind judge deterministic derivation bindings missing: "
            + ",".join(missing_derivation_bindings)
        )
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise ValueError("blind judge generated_at missing or invalid")
    from tools.build_promotion_contract_n5_blind_judge import build_judge

    rebuilt_payload = build_judge(
        source_manifest_path=resolve_artifact_path(
            source_bindings["source_manifest"]["path"]
        ),
        golden_manifest_path=resolve_artifact_path(
            source_bindings["golden_manifest"]["path"]
        ),
        blind_adjudication_path=resolve_artifact_path(
            source_bindings["loop641_blind_adjudication"]["path"]
        ),
        independent_identity_evidence_path=resolve_artifact_path(
            source_bindings["independent_identity_evidence"]["path"]
        ),
        r6_golden_audit_path=resolve_artifact_path(
            source_bindings["r6_golden_audit"]["path"]
        ),
        r6_result_path=resolve_artifact_path(
            source_bindings["r6_result"]["path"]
        ),
        generated_at=generated_at,
    )
    rebuilt_canonical_sha256 = canonical_sha256(rebuilt_payload)
    if rebuilt_canonical_sha256 != canonical_sha256(payload):
        raise ValueError(
            "blind judge payload differs from deterministic builder derivation"
        )

    normalized_scope = {
        "post_ids": scope_post_ids,
        **scope_expectations,
    }
    schema_contract = {
        "report_type": payload["report_type"],
        "builder_version": builder_version,
        "semantic_quality": payload["semantic_quality"],
        "row_count": len(rows),
        "row_post_ids": row_post_ids,
        "acceptable_outcome_count_by_post": acceptable_outcome_count_by_post,
        "modern_outcome_schema_required": True,
        "bypassed_gate_allowed": False,
    }
    return {
        "binding_version": "safe-loss-flip-rate-n5-blind-judge-binding-v1",
        "path": str(resolved),
        "byte_sha256": file_sha256(resolved),
        "canonical_sha256": canonical_sha256(payload),
        "gate": payload["gate"],
        "schema_contract": schema_contract,
        "schema_contract_canonical_sha256": canonical_sha256(schema_contract),
        "scope": normalized_scope,
        "scope_canonical_sha256": canonical_sha256(normalized_scope),
        "rows_canonical_sha256": canonical_sha256(rows),
        "builder_binding": normalized_builder_binding,
        "builder_binding_canonical_sha256": canonical_sha256(normalized_builder_binding),
        "matcher_contract_canonical_sha256": canonical_sha256(matcher_contract),
        "source_bindings_canonical_sha256": canonical_sha256(source_bindings),
        "source_binding_files_digest_sha256": canonical_sha256(source_file_records),
        "source_binding_files": source_file_records,
        "deterministic_derivation_verified": True,
        "deterministic_derivation_canonical_sha256": rebuilt_canonical_sha256,
    }


def _argv_option_values(argv: list[str], option: str) -> list[str]:
    values: list[str] = []
    for index, item in enumerate(argv):
        if item == option:
            values.append(str(argv[index + 1]) if index + 1 < len(argv) else "")
        elif item.startswith(option + "="):
            values.append(item.split("=", 1)[1])
    return values


def _strict_equal(actual: Any, expected: Any) -> bool:
    """Keep booleans from satisfying integer runtime-contract fields (and vice versa)."""
    return type(actual) is type(expected) and actual == expected


def _required_env_mapping(
    value: Any, *, label: str, issues: list[str]
) -> dict[str, str]:
    if not isinstance(value, dict):
        issues.append(f"{label}_missing_or_invalid")
        return {}
    out: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None:
            issues.append(f"{label}_invalid_key")
            continue
        if not isinstance(item, str) or item == "":
            issues.append(f"{label}_{key}_invalid_value")
            continue
        out[key] = item
    return out


def _fingerprint_alias_issues(
    owner: dict[str, Any],
    *,
    label: str,
    expected: Any,
    require_release: bool,
) -> list[str]:
    issues: list[str] = []
    present: list[tuple[str, Any]] = [
        (alias, owner[alias]) for alias in RUNTIME_FINGERPRINT_ALIASES if alias in owner
    ]
    if require_release and "runtime_release_fingerprint_sha256" not in owner:
        issues.append(f"{label}_runtime_release_fingerprint_sha256_missing")
    valid_values: list[str] = []
    for alias, value in present:
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            issues.append(f"{label}_{alias}_invalid")
            continue
        valid_values.append(value)
        if value != expected:
            issues.append(f"{label}_{alias}_runtime_contract_mismatch")
    if len(set(valid_values)) > 1:
        issues.append(f"{label}_fingerprint_aliases_mismatch")
    return issues


def _row_search_health_issues(run_meta: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    health = run_meta.get("search_health")
    if not isinstance(health, dict):
        return ["row_run_meta_search_health_missing_or_invalid"], {}
    status = health.get("status")
    unrecovered = health.get("unrecovered_degraded")
    issues: list[str] = []
    if status not in {"ok", "SEARCH_DEGRADED_RECOVERED"}:
        issues.append("row_run_meta_search_health_status_not_acceptable")
    if isinstance(unrecovered, bool) or not isinstance(unrecovered, int):
        issues.append("row_run_meta_search_health_unrecovered_degraded_invalid")
    elif unrecovered != 0:
        issues.append("row_run_meta_search_health_unrecovered_degraded_nonzero")
    return issues, {
        "status": status,
        "unrecovered_degraded": unrecovered,
        "degraded": health.get("degraded"),
        "degraded_recovered": health.get("degraded_recovered"),
    }


def audit_run_plan_runtime_contract(
    *,
    run_plan_path: Path | None,
    result_paths: list[Path],
    post_ids: list[str],
    repeats: int,
    blind_judge_path: Path | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "report_type": "safe_loss_flip_rate_runtime_plan_contract_audit",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": "NO-GO",
        "required": True,
        "run_plan": str(run_plan_path) if run_plan_path else None,
        "expected_post_ids": post_ids,
        "expected_repeats": repeats,
        "expected_run_count": len(post_ids) * repeats,
        "issues": [],
        "runs": [],
        "runtime_bindings_by_result_path": {},
        "blind_judge_binding": {},
        "plan_self_binding": {},
        "execution_adoption_audit": {},
    }
    issues: list[str] = report["issues"]
    if run_plan_path is None:
        issues.append("run_plan_missing")
        return report
    if not run_plan_path.is_file():
        issues.append("run_plan_not_found")
        return report
    try:
        plan = load_json(run_plan_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        issues.append(f"run_plan_unreadable:{type(exc).__name__}")
        return report
    if not isinstance(plan, dict):
        issues.append("run_plan_not_object")
        return report

    recorded_plan_self_binding = plan.get("plan_self_binding")
    expected_plan_self_binding = _plan_self_binding(plan)
    report["plan_self_binding"] = {
        "recorded": recorded_plan_self_binding,
        "recomputed": expected_plan_self_binding,
    }
    if recorded_plan_self_binding != expected_plan_self_binding:
        issues.append("run_plan_self_binding_mismatch")

    expected_count = len(post_ids) * repeats
    if len(post_ids) != 5:
        issues.append("runtime_contract_requires_exact_five_post_ids")
    if repeats != 5:
        issues.append("runtime_contract_requires_exact_five_repeats")
    if expected_count != 25:
        issues.append("runtime_contract_requires_exact_25_runs")
    planned_runs = plan.get("planned_runs")
    if not isinstance(planned_runs, list):
        issues.append("run_plan_planned_runs_missing_or_invalid")
        planned_runs = []
    plan_post_ids = [post_id_key(value) for value in (plan.get("post_ids") or [])]
    if plan_post_ids != post_ids:
        issues.append("run_plan_post_ids_mismatch")
    if not _strict_equal(plan.get("repeats"), repeats):
        issues.append("run_plan_repeats_mismatch")
    if not _strict_equal(plan.get("expected_run_count"), expected_count):
        issues.append("run_plan_expected_run_count_mismatch")
    if not _strict_equal(plan.get("planned_run_count"), expected_count):
        issues.append("run_plan_planned_run_count_mismatch")
    if len(planned_runs) != expected_count:
        issues.append("run_plan_planned_runs_length_mismatch")
    if plan.get("minimum_repeats_contract_met") is not True:
        issues.append("run_plan_minimum_repeats_contract_not_met")
    if plan.get("dedupe_guard") != "one_post_per_process":
        issues.append("run_plan_dedupe_guard_mismatch")
    if plan.get("missing_post_ids") != []:
        issues.append("run_plan_missing_post_ids_not_empty")
    expected_repeat_counts = {pid: repeats for pid in post_ids}
    if plan.get("repeat_count_by_post") != expected_repeat_counts:
        issues.append("run_plan_repeat_count_by_post_mismatch")

    plan_blind_judge = plan.get("blind_judge")
    if not isinstance(plan_blind_judge, str) or not plan_blind_judge.strip():
        issues.append("run_plan_blind_judge_path_missing_or_invalid")
    else:
        plan_blind_judge_path = resolve_artifact_path(plan_blind_judge)
        if blind_judge_path is not None and resolve_artifact_path(blind_judge_path) != plan_blind_judge_path:
            issues.append("supplied_blind_judge_does_not_match_run_plan")
        recorded_judge_binding = plan.get("blind_judge_binding")
        try:
            current_judge_binding = _blind_judge_binding(
                plan_blind_judge_path,
                post_ids=post_ids,
                repeats=repeats,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            current_judge_binding = {}
            issues.append(f"blind_judge_binding_invalid:{type(exc).__name__}:{exc}")
        report["blind_judge_binding"] = {
            "recorded": recorded_judge_binding,
            "recomputed": current_judge_binding,
        }
        if not isinstance(recorded_judge_binding, dict) or not recorded_judge_binding:
            issues.append("run_plan_blind_judge_binding_missing_or_invalid")
        elif current_judge_binding and recorded_judge_binding != current_judge_binding:
            issues.append("run_plan_blind_judge_binding_mismatch")

    runtime_contract = _mapping(plan.get("runtime_contract"))
    runtime_fields = (
        "model",
        "llm_mode",
        "llm_endpoint",
        "prompt_version",
        "runtime_release_fingerprint_sha256",
    )
    if not runtime_contract:
        issues.append("run_plan_runtime_contract_missing")
    for field in runtime_fields:
        value = runtime_contract.get(field)
        if not isinstance(value, str) or not value or value != value.strip():
            issues.append(f"run_plan_runtime_contract_{field}_missing_or_invalid")
    runtime_fingerprint = runtime_contract.get("runtime_release_fingerprint_sha256")
    if not isinstance(runtime_fingerprint, str) or re.fullmatch(
        r"[0-9a-f]{64}", runtime_fingerprint
    ) is None:
        issues.append("run_plan_runtime_release_fingerprint_invalid")
    if runtime_contract.get("config_hash_policy") != ROW_DERIVED_CONFIG_HASH_POLICY:
        issues.append("run_plan_config_hash_policy_mismatch")
    runtime_required_env = _required_env_mapping(
        runtime_contract.get("required_env"),
        label="run_plan_runtime_contract_required_env",
        issues=issues,
    )
    plan_required_env = _required_env_mapping(
        plan.get("required_env"), label="run_plan_required_env", issues=issues
    )
    if plan_required_env != runtime_required_env:
        issues.append("run_plan_required_env_runtime_contract_mismatch")
    for env_name, contract_field in RUNTIME_BINDING_ENV_FIELDS.items():
        if plan_required_env.get(env_name) != runtime_contract.get(contract_field):
            issues.append(f"run_plan_required_env_{env_name}_runtime_contract_mismatch")

    provided_paths = [resolve_artifact_path(path) for path in result_paths]
    if len(provided_paths) != len(set(provided_paths)):
        issues.append("provided_result_paths_duplicate")
    planned_result_paths: list[Path] = []
    planned_checkpoint_paths: list[Path] = []
    planned_manifest_paths: list[Path] = []
    planned_input_paths: list[Path] = []
    planned_pairs: list[tuple[str, int]] = []
    for index, run in enumerate(planned_runs):
        if not isinstance(run, dict):
            issues.append(f"planned_run[{index}]_not_object")
            continue
        planned_result_paths.append(resolve_artifact_path(run.get("output_json")))
        planned_checkpoint_paths.append(
            resolve_artifact_path(run.get("checkpoint_jsonl"))
        )
        planned_manifest_paths.append(resolve_artifact_path(run.get("manifest_json")))
        planned_input_paths.append(resolve_artifact_path(run.get("input_jsonl")))
        try:
            repeat_index = int(run.get("repeat_index"))
        except (TypeError, ValueError):
            repeat_index = -1
        planned_pairs.append((post_id_key(run.get("post_id")), repeat_index))
    if len(planned_result_paths) != len(set(planned_result_paths)):
        issues.append("run_plan_result_paths_duplicate")
    if len(planned_checkpoint_paths) != len(set(planned_checkpoint_paths)):
        issues.append("run_plan_checkpoint_paths_duplicate")
    if len(planned_manifest_paths) != len(set(planned_manifest_paths)):
        issues.append("run_plan_manifest_paths_duplicate")
    planned_runtime_paths = (
        planned_result_paths + planned_checkpoint_paths + planned_manifest_paths
    )
    if len(planned_runtime_paths) != len(set(planned_runtime_paths)):
        issues.append("run_plan_runtime_artifact_paths_overlap")
    if len(planned_input_paths) != len(set(planned_input_paths)):
        issues.append("run_plan_input_paths_duplicate")
    if set(provided_paths) != set(planned_result_paths) or len(provided_paths) != len(
        planned_result_paths
    ):
        issues.append("provided_results_do_not_exactly_match_run_plan")
    expected_pairs = {(pid, repeat_index) for pid in post_ids for repeat_index in range(1, repeats + 1)}
    if set(planned_pairs) != expected_pairs or len(planned_pairs) != len(expected_pairs):
        issues.append("run_plan_post_id_repeat_pairs_mismatch")

    try:
        from tools.run_independent_plan import audit_plan_execution_adoption_contract

        execution_adoption_audit = audit_plan_execution_adoption_contract(
            plan_path=run_plan_path,
            plan=plan,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        execution_adoption_audit = {
            "report_type": "independent_plan_execution_adoption_audit",
            "gate": "NO-GO",
            "issues": [f"audit_failed:{type(exc).__name__}:{exc}"],
            "runs": [],
            "summary": {},
        }
    report["execution_adoption_audit"] = execution_adoption_audit
    if execution_adoption_audit.get("gate") != "GO":
        issues.append("execution_adoption_contract_not_go")

    observed_run_ids: list[str] = []
    observed_config_hashes: list[str] = []
    observed_search_health_statuses: list[str] = []
    for index, run in enumerate(planned_runs):
        if not isinstance(run, dict):
            continue
        run_issues: list[str] = []
        pid = post_id_key(run.get("post_id"))
        result_path = resolve_artifact_path(run.get("output_json"))
        manifest_path = resolve_artifact_path(run.get("manifest_json"))
        input_path = resolve_artifact_path(run.get("input_jsonl"))
        if not _strict_equal(run.get("input_post_id"), pid):
            run_issues.append("planned_input_post_id_mismatch")
        if not _strict_equal(run.get("input_row_count"), 1):
            run_issues.append("planned_input_row_count_mismatch")
        planned_input_sha256 = run.get("input_sha256")
        if not isinstance(planned_input_sha256, str) or re.fullmatch(
            r"[0-9a-f]{64}", planned_input_sha256
        ) is None:
            run_issues.append("planned_input_sha256_invalid")

        input_rows: list[dict[str, Any]] = []
        if not input_path.is_file():
            run_issues.append("input_not_found")
        else:
            try:
                input_bytes = input_path.read_bytes()
                input_rows = load_jsonl(input_path)
            except (OSError, ValueError, json.JSONDecodeError):
                input_bytes = b""
                run_issues.append("input_unreadable")
            if len(input_rows) != 1:
                run_issues.append("input_row_count_not_one")
            if len(input_rows) == 1 and post_id_key(input_rows[0].get("post_id")) != pid:
                run_issues.append("input_post_id_mismatch")
            canonical_input_bytes = probe_input_text(input_rows).encode("utf-8")
            canonical_input_sha256 = hashlib.sha256(canonical_input_bytes).hexdigest()
            actual_input_sha256 = hashlib.sha256(input_bytes).hexdigest()
            if input_bytes != canonical_input_bytes:
                run_issues.append("input_bytes_not_canonical_probe_input_text")
            if actual_input_sha256 != planned_input_sha256:
                run_issues.append("input_file_sha256_mismatch")
            if canonical_input_sha256 != planned_input_sha256:
                run_issues.append("input_canonical_sha256_mismatch")
        argv = run.get("command_argv")
        argv = [str(value) for value in argv] if isinstance(argv, list) else []
        required_argv_options = {
            "--parallel": "16",
            "--slang-db": "off",
            "--vlm": "on",
            "--ocr": "on",
            "--llm-model": runtime_contract.get("model"),
            "--llm-endpoint": runtime_contract.get("llm_endpoint"),
        }
        for option, expected_value in required_argv_options.items():
            values = _argv_option_values(argv, option)
            if values != [expected_value]:
                run_issues.append(f"command_{option.lstrip('-').replace('-', '_')}_mismatch")
        for flag in ("--reuse-shards-only", "--require-vlm-ocr-for-images"):
            if argv.count(flag) != 1:
                run_issues.append(f"command_{flag.lstrip('-').replace('-', '_')}_missing")
        if "--no-dashboard" in argv:
            run_issues.append("command_forbidden_no_dashboard")
        command_input_values = _argv_option_values(argv, "--input")
        if len(command_input_values) != 1 or resolve_artifact_path(
            command_input_values[0] if command_input_values else ""
        ) != input_path:
            run_issues.append("command_input_not_bound_to_planned_input_jsonl")
        command_output_values = _argv_option_values(argv, "--output")
        if len(command_output_values) != 1 or resolve_artifact_path(
            command_output_values[0] if command_output_values else ""
        ) != result_path:
            run_issues.append("command_output_not_bound_to_planned_output_json")
        run_required_env_issues: list[str] = []
        run_required_env = _required_env_mapping(
            run.get("required_env"),
            label=f"planned_run[{index}]_required_env",
            issues=run_required_env_issues,
        )
        run_issues.extend(run_required_env_issues)
        if run_required_env != plan_required_env:
            run_issues.append("required_env_not_exactly_bound_to_plan")

        manifest: dict[str, Any] = {}
        if not manifest_path.is_file():
            run_issues.append("manifest_not_found")
        else:
            try:
                payload = load_json(manifest_path)
                manifest = payload if isinstance(payload, dict) else {}
            except (OSError, ValueError, json.JSONDecodeError):
                run_issues.append("manifest_unreadable")
        manifest_expectations = {
            "input_post_count": 1,
            "completed_count": 1,
            "flushed_count": 1,
            "pending_count": 0,
            "failed_count": 0,
            "requested_parallel": 16,
            "effective_parallel": 1,
            "dashboard_enabled": True,
            "dashboard_standalone_forwarding": True,
            "mcp_health_include_search": True,
            "mcp_health_light_mode": False,
            "mcp_health_required_ok_count": 16,
            "mcp_health_checked_endpoint_count": 16,
            "mcp_health_ok_count": 16,
            "mcp_health_failure_count": 0,
            "mcp_requested_endpoint_count_before_health_filter": 16,
            "mcp_healthy_endpoint_count": 16,
            "mcp_endpoint_count_after_health_filter": 16,
            "vlm_enabled": True,
            "ocr_enabled": True,
            "vlm_ocr_semantic_review_ready": True,
            "vlm_ocr_semantic_review_required_for_images": True,
            "vlm_ocr_semantic_review_skip_reasons": [],
            "vlm_ocr_semantic_review_skip_reason": "",
            "vlm_ocr_semantic_review_blocker": False,
            "vlm_ocr_semantic_review_blocker_code": "",
            "vlm_ocr_semantic_review_blocker_action": "",
        }
        for field, expected_value in manifest_expectations.items():
            if not _strict_equal(manifest.get(field), expected_value):
                run_issues.append(f"manifest_{field}_mismatch")
        dashboard_mode = str(manifest.get("dashboard_mode") or "").strip().lower()
        if dashboard_mode != "standalone_forward":
            run_issues.append("manifest_dashboard_mode_not_standalone_forward")
        if str(manifest.get("dashboard_start_error") or "").strip():
            run_issues.append("manifest_dashboard_start_error")
        if manifest.get("partial_flush_gap") is not None and manifest.get("partial_flush_gap") is not False:
            run_issues.append("manifest_partial_flush_gap")
        if manifest.get("ordered_flush_blocked") is not None and manifest.get("ordered_flush_blocked") is not False:
            run_issues.append("manifest_ordered_flush_blocked")
        manifest_output = manifest.get("output_file")
        if not isinstance(manifest_output, str) or not manifest_output.strip():
            run_issues.append("manifest_output_file_missing")
        elif resolve_artifact_path(manifest_output) != result_path:
            run_issues.append("manifest_output_file_mismatch")

        manifest_runtime_fields = {
            "llm_model": "model",
            "llm_endpoint": "llm_endpoint",
        }
        for manifest_field, contract_field in manifest_runtime_fields.items():
            if not _strict_equal(
                manifest.get(manifest_field), runtime_contract.get(contract_field)
            ):
                run_issues.append(f"manifest_{manifest_field}_runtime_contract_mismatch")
        run_issues.extend(
            _fingerprint_alias_issues(
                manifest,
                label="manifest",
                expected=runtime_fingerprint,
                require_release=True,
            )
        )

        result_rows: list[dict[str, Any]] = []
        if not result_path.is_file():
            run_issues.append("result_not_found")
        else:
            try:
                result_rows = load_rows(result_path)
            except (OSError, ValueError, json.JSONDecodeError):
                run_issues.append("result_unreadable")
        if len(result_rows) != 1:
            run_issues.append("result_row_count_not_one")
        result_row = unwrap_result_row(result_rows[0]) if len(result_rows) == 1 else {}
        if post_id_key(result_row.get("post_id")) != pid:
            run_issues.append("result_post_id_mismatch")
        run_meta = _mapping(result_row.get("run_meta"))
        run_id = _optional_text(manifest.get("run_id"))
        if run_id is None or manifest.get("run_id") != run_id:
            run_issues.append("manifest_run_id_missing")
        else:
            observed_run_ids.append(run_id)
        row_runtime_expectations = {
            "run_id": manifest.get("run_id"),
            "model": runtime_contract.get("model"),
            "llm_mode": runtime_contract.get("llm_mode"),
            "llm_endpoint": runtime_contract.get("llm_endpoint"),
            "prompt_version": runtime_contract.get("prompt_version"),
            "requested_parallel": manifest.get("requested_parallel"),
            "effective_parallel": manifest.get("effective_parallel"),
        }
        for field, expected_value in row_runtime_expectations.items():
            if not _strict_equal(run_meta.get(field), expected_value):
                run_issues.append(f"row_run_meta_{field}_runtime_contract_mismatch")
        run_issues.extend(
            _fingerprint_alias_issues(
                run_meta,
                label="row_run_meta",
                expected=runtime_fingerprint,
                require_release=True,
            )
        )
        config_hash = run_meta.get("config_hash")
        if not isinstance(config_hash, str) or not config_hash or config_hash != config_hash.strip():
            run_issues.append("row_run_meta_config_hash_not_nonempty_raw_string")
        else:
            observed_config_hashes.append(config_hash)
        search_health_issues, search_health_snapshot = _row_search_health_issues(run_meta)
        run_issues.extend(search_health_issues)
        search_status = search_health_snapshot.get("status")
        if isinstance(search_status, str):
            observed_search_health_statuses.append(search_status)

        runtime_binding = {
            "model": runtime_contract.get("model"),
            "llm_mode": runtime_contract.get("llm_mode"),
            "llm_endpoint": runtime_contract.get("llm_endpoint"),
            "prompt_version": runtime_contract.get("prompt_version"),
            "runtime_release_fingerprint_sha256": runtime_contract.get(
                "runtime_release_fingerprint_sha256"
            ),
        }
        report["runtime_bindings_by_result_path"][str(result_path)] = runtime_binding
        report["runs"].append(
            {
                "index": index,
                "post_id": pid,
                "repeat_index": run.get("repeat_index"),
                "result_path": str(result_path),
                "manifest_path": str(manifest_path),
                "input_path": str(input_path),
                "row_search_health": search_health_snapshot,
                "gate": "GO" if not run_issues else "NO-GO",
                "issues": run_issues,
            }
        )
        issues.extend(f"run[{index}]:{issue}" for issue in run_issues)

    if len(observed_run_ids) != expected_count or len(set(observed_run_ids)) != expected_count:
        issues.append("runtime_manifest_run_ids_not_unique_or_complete")
    if len(observed_config_hashes) != expected_count or len(set(observed_config_hashes)) != 1:
        issues.append("row_derived_config_hash_not_uniform_nonempty_across_25")
    report["summary"] = {
        "planned_run_count": len(planned_runs),
        "provided_result_count": len(provided_paths),
        "manifest_count": len(planned_manifest_paths),
        "unique_run_id_count": len(set(observed_run_ids)),
        "row_derived_config_hash_unique_count": len(set(observed_config_hashes)),
        "row_derived_config_hash": (
            observed_config_hashes[0]
            if len(observed_config_hashes) == expected_count
            and len(set(observed_config_hashes)) == 1
            else None
        ),
        "row_search_health_status_counts": dict(
            sorted(Counter(observed_search_health_statuses).items())
        ),
        "execution_adopted_completion_count": execution_adoption_audit.get(
            "summary", {}
        ).get("adopted_completion_count", 0),
        "execution_child_started_count": execution_adoption_audit.get(
            "summary", {}
        ).get("child_started_count", 0),
        "execution_failed_attempt_count": execution_adoption_audit.get(
            "summary", {}
        ).get("failed_attempt_count", 0),
        "execution_indeterminate_attempt_count": execution_adoption_audit.get(
            "summary", {}
        ).get("indeterminate_attempt_count", 0),
        "issue_count": len(issues),
    }
    report["gate"] = "GO" if not issues else "NO-GO"
    return report


def load_result_rows_with_bindings(
    *,
    result_paths: list[Path],
    runtime_contract_audit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Load result files while binding every row to its immutable file and audited runtime."""
    runtime_bindings = _mapping(
        (runtime_contract_audit or {}).get("runtime_bindings_by_result_path")
    )
    rows: list[dict[str, Any]] = []
    for supplied_path in result_paths:
        resolved_path = resolve_artifact_path(supplied_path)
        result_sha256 = file_sha256(resolved_path)
        runtime_binding = _mapping(runtime_bindings.get(str(resolved_path)))
        for row in load_rows(resolved_path):
            enriched = dict(row)
            enriched["_flip_probe_result_binding"] = {
                "result_path": str(resolved_path),
                "result_sha256": result_sha256,
            }
            if runtime_binding:
                enriched["_flip_probe_runtime_binding"] = dict(runtime_binding)
            rows.append(enriched)
    return rows


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reason_code_list(value: Any, *, field: str) -> tuple[list[str], list[str]]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        return [], [f"malformed_{field}"]
    return [item.strip() for item in value], []


def _candidate_pair_list(
    value: Any, *, field: str
) -> tuple[list[tuple[str | None, str | None]], list[str]]:
    if not isinstance(value, list) or not value:
        return [], [f"malformed_{field}_empty_or_not_list"]
    pairs: list[tuple[str | None, str | None]] = []
    issues: list[str] = []
    seen: set[tuple[str | None, str | None]] = set()
    for index, item in enumerate(value):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict) or set(item) != {"title", "url"}:
            issues.append(f"malformed_{prefix}_requires_exact_title_url_fields")
            continue
        title_value = item.get("title")
        url_value = item.get("url")
        if title_value is not None and (
            not isinstance(title_value, str)
            or not title_value.strip()
            or title_value != title_value.strip()
        ):
            issues.append(f"malformed_{prefix}_title")
            continue
        if url_value is not None and (
            not isinstance(url_value, str)
            or not url_value.strip()
            or url_value != url_value.strip()
        ):
            issues.append(f"malformed_{prefix}_url")
            continue
        title = title_value if isinstance(title_value, str) else None
        url = url_value if isinstance(url_value, str) else None
        if title is None and url is None:
            issues.append(f"malformed_{prefix}_empty_pair")
            continue
        pair = (title, url)
        if pair in seen:
            issues.append(f"duplicate_{prefix}")
            continue
        seen.add(pair)
        pairs.append(pair)
    return pairs, issues


def _match_acceptable_outcome(
    outcome: dict[str, Any],
    expected: Any,
    *,
    index: int,
) -> tuple[bool, list[str], bool]:
    prefix = f"acceptable_outcomes[{index}]"
    if not isinstance(expected, dict) or not expected:
        return False, [f"{prefix}:malformed_or_empty"], True
    legacy_fields = sorted(set(expected) & ACCEPTABLE_OUTCOME_LEGACY_FIELDS)
    if legacy_fields:
        return (
            False,
            [f"{prefix}:legacy_fields_not_allowed={','.join(legacy_fields)}"],
            True,
        )
    unknown = sorted(set(expected) - OUTCOME_CONTRACT_FIELDS)
    if unknown:
        return False, [f"{prefix}:unknown_fields={','.join(unknown)}"], True
    missing_required_fields = sorted(ACCEPTABLE_OUTCOME_REQUIRED_FIELDS - set(expected))
    if missing_required_fields:
        return (
            False,
            [f"{prefix}:missing_required_fields={','.join(missing_required_fields)}"],
            True,
        )

    reasons: list[str] = []
    malformed: list[str] = []
    meaningful_constraint = False
    for field in sorted(OUTCOME_EXACT_MATCH_FIELDS & set(expected)):
        meaningful_constraint = True
        wanted = expected[field]
        if field in {"publish_allowed", "candidate_preserved", "bypassed_gate"} and not isinstance(
            wanted, (bool, type(None))
        ):
            malformed.append(f"{prefix}:malformed_{field}")
            continue
        if field == "reason_codes":
            _codes, issues = _reason_code_list(wanted, field=field)
            if issues:
                malformed.extend(f"{prefix}:{issue}" for issue in issues)
                continue
        actual = outcome.get(field)
        if actual != wanted:
            reasons.append(
                f"{prefix}.{field}:expected={_json_value(wanted)}:actual={_json_value(actual)}"
            )

    actual_reason_codes = outcome.get("reason_codes")
    actual_reason_codes = actual_reason_codes if isinstance(actual_reason_codes, list) else []
    if "required_reason_codes" in expected:
        required, issues = _reason_code_list(
            expected.get("required_reason_codes"), field="required_reason_codes"
        )
        malformed.extend(f"{prefix}:{issue}" for issue in issues)
        if required:
            meaningful_constraint = True
            missing = [code for code in required if code not in actual_reason_codes]
            if missing:
                reasons.append(f"{prefix}.required_reason_codes_missing={_json_value(missing)}")
        else:
            malformed.append(f"{prefix}:required_reason_codes_empty")
    if "forbidden_reason_codes" in expected:
        forbidden, issues = _reason_code_list(
            expected.get("forbidden_reason_codes"), field="forbidden_reason_codes"
        )
        malformed.extend(f"{prefix}:{issue}" for issue in issues)
        if forbidden:
            meaningful_constraint = True
            present = [code for code in forbidden if code in actual_reason_codes]
            if present:
                reasons.append(f"{prefix}.forbidden_reason_codes_present={_json_value(present)}")

    for requirement, outcome_field in (
        ("required_direct_bridge_sources", "direct_bridge_sources"),
        ("required_evidence_kinds", "evidence_kinds"),
        ("required_evidence_reason_codes", "evidence_reason_codes"),
        (
            "required_publish_supporting_evidence_kinds",
            "publish_supporting_evidence_kinds",
        ),
        (
            "required_publish_supporting_evidence_reason_codes",
            "publish_supporting_evidence_reason_codes",
        ),
    ):
        if requirement not in expected:
            continue
        required, issues = _reason_code_list(expected.get(requirement), field=requirement)
        malformed.extend(f"{prefix}:{issue}" for issue in issues)
        if required:
            meaningful_constraint = True
            actual_values = outcome.get(outcome_field)
            actual_values = actual_values if isinstance(actual_values, list) else []
            missing = [value for value in required if value not in actual_values]
            if missing:
                reasons.append(f"{prefix}.{requirement}_missing={_json_value(missing)}")
        elif expected.get("publish_allowed") is True and requirement in {
            "required_direct_bridge_sources",
            "required_publish_supporting_evidence_kinds",
            "required_publish_supporting_evidence_reason_codes",
        }:
            malformed.append(f"{prefix}:{requirement}_empty_for_publish")

    if "required_candidate_inventory_pairs" in expected:
        required_pairs, pair_issues = _candidate_pair_list(
            expected.get("required_candidate_inventory_pairs"),
            field="required_candidate_inventory_pairs",
        )
        malformed.extend(f"{prefix}:{issue}" for issue in pair_issues)
        if required_pairs:
            meaningful_constraint = True
            actual_pairs, actual_pair_issues = _candidate_pair_list(
                outcome.get("candidate_inventory_pairs"),
                field="runtime_candidate_inventory_pairs",
            )
            if actual_pair_issues:
                reasons.extend(f"{prefix}:{issue}" for issue in actual_pair_issues)
            missing_pairs = [
                {"title": title, "url": url}
                for title, url in required_pairs
                if (title, url) not in set(actual_pairs)
            ]
            if missing_pairs:
                reasons.append(
                    f"{prefix}.required_candidate_inventory_pairs_missing={_json_value(missing_pairs)}"
                )

    for requirement, outcome_field in (
        ("require_fingerprint", "input_fingerprint"),
        ("require_contract_version", "contract_version"),
    ):
        if requirement not in expected:
            continue
        meaningful_constraint = True
        wanted = expected[requirement]
        actual = outcome.get(outcome_field)
        if requirement == "require_fingerprint" and wanted is True:
            if not isinstance(actual, str) or re.fullmatch(r"[0-9a-f]{64}", actual) is None:
                reasons.append(f"{prefix}.{outcome_field}:required_lowercase_sha256_missing_or_invalid")
        elif requirement == "require_contract_version" and wanted != "promotion_contract_v2":
            malformed.append(f"{prefix}:unsupported_contract_version={_json_value(wanted)}")
        elif isinstance(wanted, str) and wanted.strip():
            if actual != wanted.strip():
                reasons.append(
                    f"{prefix}.{outcome_field}:expected={_json_value(wanted.strip())}:actual={_json_value(actual)}"
                )
        else:
            malformed.append(f"{prefix}:malformed_{requirement}")

    consistency_issues = outcome.get("contract_consistency_issues")
    if not isinstance(consistency_issues, list):
        malformed.append(f"{prefix}:runtime_contract_consistency_issues_malformed")
    elif consistency_issues:
        reasons.append(
            f"{prefix}.runtime_contract_consistency_issues={_json_value(consistency_issues)}"
        )
    canonical_gate = outcome.get("canonical_publication_contract_gate")
    if canonical_gate != "GO":
        reasons.append(
            f"{prefix}.canonical_publication_contract_gate:expected=\"GO\":actual={_json_value(canonical_gate)}"
        )
        violation_codes = outcome.get("canonical_publication_contract_violation_codes")
        if isinstance(violation_codes, list) and violation_codes:
            reasons.append(
                f"{prefix}.canonical_publication_contract_violations={_json_value(violation_codes)}"
            )

    if not meaningful_constraint:
        malformed.append(f"{prefix}:empty_contract")
    if malformed:
        return False, malformed, True
    return not reasons, reasons, False


def _evaluate_expected_contract(
    outcome: dict[str, Any], judge: Any
) -> dict[str, Any]:
    if not isinstance(judge, dict) or not judge:
        return {
            "matched": False,
            "matched_acceptable_outcome_index": None,
            "mismatch_reasons": ["expected_contract_missing_or_empty"],
            "acceptable_outcome_mismatch_reasons": [],
            "contract_style": "malformed",
        }

    if "acceptable_outcomes" in judge:
        acceptable = judge.get("acceptable_outcomes")
        if not isinstance(acceptable, list) or not acceptable:
            return {
                "matched": False,
                "matched_acceptable_outcome_index": None,
                "mismatch_reasons": ["acceptable_outcomes_missing_malformed_or_empty"],
                "acceptable_outcome_mismatch_reasons": [],
                "contract_style": "acceptable_outcomes",
            }
        per_outcome: list[dict[str, Any]] = []
        matched_indexes: list[int] = []
        malformed = False
        for index, expected in enumerate(acceptable):
            matched, reasons, item_malformed = _match_acceptable_outcome(
                outcome, expected, index=index
            )
            malformed = malformed or item_malformed
            if matched:
                matched_indexes.append(index)
            per_outcome.append(
                {"index": index, "reasons": reasons, "malformed": item_malformed}
            )
        if malformed:
            return {
                "matched": False,
                "matched_acceptable_outcome_index": None,
                "mismatch_reasons": [
                    reason
                    for item in per_outcome
                    if item["malformed"]
                    for reason in item["reasons"]
                ],
                "acceptable_outcome_mismatch_reasons": per_outcome,
                "contract_style": "acceptable_outcomes",
            }
        if matched_indexes:
            return {
                "matched": True,
                "matched_acceptable_outcome_index": matched_indexes[0],
                "mismatch_reasons": [],
                "acceptable_outcome_mismatch_reasons": per_outcome,
                "contract_style": "acceptable_outcomes",
            }
        return {
            "matched": False,
            "matched_acceptable_outcome_index": None,
            "mismatch_reasons": [
                reason for item in per_outcome for reason in item["reasons"]
            ],
            "acceptable_outcome_mismatch_reasons": per_outcome,
            "contract_style": "acceptable_outcomes",
        }

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
    checks: list[tuple[str, str, str]] = []
    if not expected_status or not expected_title:
        return {
            "matched": False,
            "matched_acceptable_outcome_index": None,
            "mismatch_reasons": ["legacy_expected_contract_requires_status_and_title"],
            "acceptable_outcome_mismatch_reasons": [],
            "contract_style": "legacy",
        }
    if expected_status not in {"safe_resolved", "resolved"}:
        return {
            "matched": False,
            "matched_acceptable_outcome_index": None,
            "mismatch_reasons": ["legacy_expected_contract_nonpublic_status_not_authoritative"],
            "acceptable_outcome_mismatch_reasons": [],
            "contract_style": "legacy",
        }
    if expected_status:
        checks.append(("status", expected_status, str(outcome.get("status") or "")))
    if expected_title:
        checks.append(("public_title", expected_title, str(outcome.get("public_title") or "")))
    if expected_url:
        checks.append(("public_url", expected_url, str(outcome.get("public_url") or "")))
    if not checks:
        return {
            "matched": False,
            "matched_acceptable_outcome_index": None,
            "mismatch_reasons": ["legacy_expected_contract_empty"],
            "acceptable_outcome_mismatch_reasons": [],
            "contract_style": "legacy",
        }
    mismatch_reasons = [
        f"legacy.{field}:expected={_json_value(expected)}:actual={_json_value(actual)}"
        for field, expected, actual in checks
        if actual != expected
    ]
    return {
        "matched": not mismatch_reasons,
        "matched_acceptable_outcome_index": None,
        "mismatch_reasons": mismatch_reasons,
        "acceptable_outcome_mismatch_reasons": [],
        "contract_style": "legacy",
    }


def _matches_expected(outcome: dict[str, Any], judge: dict[str, Any]) -> bool:
    """Compatibility wrapper around the fail-closed expected-contract matcher."""
    return bool(_evaluate_expected_contract(outcome, judge)["matched"])


def analyze_flip_rate(
    *,
    result_rows: list[dict[str, Any]],
    post_ids: list[str],
    repeats: int,
    blind_judge: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blind_judge = blind_judge or {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_repeat_bindings: dict[str, list[str | None]] = defaultdict(list)
    grouped_runtime_signatures: dict[str, list[str | None]] = defaultdict(list)
    grouped_runtime_issues: dict[str, list[list[str]]] = defaultdict(list)
    grouped_runtime_payloads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result_rows:
        pid = post_id_key(unwrap_result_row(row).get("post_id"))
        if pid in post_ids:
            grouped[pid].append(row_outcome(row))
            grouped_repeat_bindings[pid].append(row_repeat_binding(row))
            runtime_signature, runtime_issues, runtime_payload = row_runtime_signature(row)
            grouped_runtime_signatures[pid].append(runtime_signature)
            grouped_runtime_issues[pid].append(runtime_issues)
            grouped_runtime_payloads[pid].append(runtime_payload)

    rows: list[dict[str, Any]] = []
    any_semantic_flip = False
    any_decision_surface_flip = False
    any_raw_outcome_variance = False
    all_repeats_present = True
    all_independent_repeats_present = True
    all_runtime_signatures_valid = True
    global_runtime_signatures: set[str] = set()
    all_repeats_expected = True
    all_expected_contracts_authoritative = True
    blind_judge_mismatch_repeat_count = 0
    unsafe_repeat_count = 0
    unsafe_or_blind_judge_mismatch_repeat_count = 0
    minimum_repeats_contract_met = repeats >= MINIMUM_ANALYZE_REPEATS
    post_ids_unique = len(post_ids) == len(set(post_ids))
    for pid in post_ids:
        outcomes = grouped.get(pid, [])
        repeat_bindings = grouped_repeat_bindings.get(pid, [])
        runtime_signatures = grouped_runtime_signatures.get(pid, [])
        runtime_issues = grouped_runtime_issues.get(pid, [])
        runtime_payloads = grouped_runtime_payloads.get(pid, [])
        if len(outcomes) != repeats:
            all_repeats_present = False
        unique_repeat_bindings = {
            binding for binding in repeat_bindings if isinstance(binding, str) and binding
        }
        independent_repeats_present = (
            len(repeat_bindings) == repeats
            and len(unique_repeat_bindings) == repeats
            and all(binding is not None for binding in repeat_bindings)
        )
        if not independent_repeats_present:
            all_independent_repeats_present = False
        unique_runtime_signatures = {
            signature for signature in runtime_signatures if isinstance(signature, str) and signature
        }
        runtime_signatures_valid = (
            len(runtime_signatures) == repeats
            and len(unique_runtime_signatures) == 1
            and all(not issues for issues in runtime_issues)
        )
        global_runtime_signatures.update(unique_runtime_signatures)
        if not runtime_signatures_valid:
            all_runtime_signatures_valid = False
        raw_outcome_keys = [
            json.dumps(outcome, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for outcome in outcomes
        ]
        raw_counts = Counter(raw_outcome_keys)
        unique_outcomes = [json.loads(key) for key in sorted(raw_counts)]
        raw_majority_count = max(raw_counts.values()) if raw_counts else 0
        raw_flip_count = max(0, len(outcomes) - raw_majority_count)
        raw_flip_rate = (raw_flip_count / len(outcomes)) if outcomes else None
        raw_outcome_variance = len(raw_counts) > 1
        any_raw_outcome_variance = any_raw_outcome_variance or raw_outcome_variance
        stable_outcome = unique_outcomes[0] if len(unique_outcomes) == 1 else None

        semantic_keys = [semantic_decision_surface_key(outcome) for outcome in outcomes]
        semantic_counts = Counter(semantic_keys)
        unique_semantic_decision_surfaces = [
            json.loads(key) for key in sorted(semantic_counts)
        ]
        decision_surface_majority_count = (
            max(semantic_counts.values()) if semantic_counts else 0
        )
        decision_surface_flip_count = max(
            0, len(outcomes) - decision_surface_majority_count
        )
        decision_surface_flip_rate = (
            decision_surface_flip_count / len(outcomes) if outcomes else None
        )
        decision_surface_flipped = len(semantic_counts) > 1
        any_decision_surface_flip = (
            any_decision_surface_flip or decision_surface_flipped
        )
        stable_semantic_decision_surface = (
            unique_semantic_decision_surfaces[0]
            if len(unique_semantic_decision_surfaces) == 1
            else None
        )

        judge_present = pid in blind_judge
        judge = blind_judge.get(pid)
        repeat_contract_evaluations: list[dict[str, Any]] = []
        for repeat_index, outcome in enumerate(outcomes, start=1):
            if judge_present:
                contract_evaluation = _evaluate_expected_contract(outcome, judge)
            else:
                contract_evaluation = {
                    "matched": False,
                    "matched_acceptable_outcome_index": None,
                    "mismatch_reasons": ["blind_judge_contract_missing"],
                    "acceptable_outcome_mismatch_reasons": [],
                    "contract_style": "missing",
                }
            safety_evaluation = _outcome_safety_evaluation(outcome)
            judge_mismatch = not bool(contract_evaluation["matched"])
            unsafe = not bool(safety_evaluation["safe"])
            repeat_contract_evaluations.append(
                {
                    "repeat_index": repeat_index,
                    "repeat_binding": (
                        repeat_bindings[repeat_index - 1]
                        if repeat_index <= len(repeat_bindings)
                        else None
                    ),
                    "runtime_signature": (
                        runtime_signatures[repeat_index - 1]
                        if repeat_index <= len(runtime_signatures)
                        else None
                    ),
                    "runtime_signature_issues": (
                        runtime_issues[repeat_index - 1]
                        if repeat_index <= len(runtime_issues)
                        else ["runtime_signature_result_missing"]
                    ),
                    "raw_outcome": outcome,
                    "semantic_decision_surface": semantic_decision_surface(outcome),
                    "semantic_decision_surface_key": semantic_keys[repeat_index - 1],
                    "blind_judge_match": bool(contract_evaluation["matched"]),
                    "blind_judge_mismatch": judge_mismatch,
                    "matched_acceptable_outcome_index": contract_evaluation[
                        "matched_acceptable_outcome_index"
                    ],
                    "expected_contract_style": contract_evaluation["contract_style"],
                    "mismatch_reasons": contract_evaluation["mismatch_reasons"],
                    "acceptable_outcome_mismatch_reasons": contract_evaluation[
                        "acceptable_outcome_mismatch_reasons"
                    ],
                    "unsafe": unsafe,
                    "unsafe_reasons": safety_evaluation["unsafe_reasons"],
                    "unsafe_or_blind_judge_mismatch": unsafe or judge_mismatch,
                }
            )

        repeat_match_count = sum(
            1 for evaluation in repeat_contract_evaluations if evaluation["blind_judge_match"]
        )
        repeat_mismatch_count = sum(
            1
            for evaluation in repeat_contract_evaluations
            if evaluation["blind_judge_mismatch"]
        )
        row_unsafe_repeat_count = sum(
            1 for evaluation in repeat_contract_evaluations if evaluation["unsafe"]
        )
        row_union_repeat_count = sum(
            1
            for evaluation in repeat_contract_evaluations
            if evaluation["unsafe_or_blind_judge_mismatch"]
        )
        blind_judge_mismatch_repeat_count += repeat_mismatch_count
        unsafe_repeat_count += row_unsafe_repeat_count
        unsafe_or_blind_judge_mismatch_repeat_count += row_union_repeat_count

        semantic_adjudication_keys = [
            json.dumps(
                {
                    "blind_judge_match": evaluation["blind_judge_match"],
                    "unsafe": evaluation["unsafe"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            for evaluation in repeat_contract_evaluations
        ]
        semantic_adjudication_counts = Counter(semantic_adjudication_keys)
        semantic_majority_count = (
            max(semantic_adjudication_counts.values())
            if semantic_adjudication_counts
            else 0
        )
        semantic_flip_count = max(0, len(outcomes) - semantic_majority_count)
        semantic_flip_rate = (
            semantic_flip_count / len(outcomes) if outcomes else None
        )
        semantic_flipped = len(semantic_adjudication_counts) > 1
        any_semantic_flip = any_semantic_flip or semantic_flipped

        expected_match = (
            repeat_mismatch_count == 0
            if judge_present and len(repeat_contract_evaluations) == repeats
            else None
        )
        styles = {
            evaluation["expected_contract_style"]
            for evaluation in repeat_contract_evaluations
        }
        expected_contract_authoritative = bool(
            expected_match is True
            and styles == {"acceptable_outcomes"}
        )
        if expected_match is not True:
            all_repeats_expected = False
        if not expected_contract_authoritative:
            all_expected_contracts_authoritative = False
        mismatch_reasons = list(
            dict.fromkeys(
                reason
                for evaluation in repeat_contract_evaluations
                for reason in evaluation["mismatch_reasons"]
            )
        )
        matched_indexes = {
            evaluation["matched_acceptable_outcome_index"]
            for evaluation in repeat_contract_evaluations
            if evaluation["blind_judge_match"]
        }
        matched_acceptable_outcome_index = (
            next(iter(matched_indexes))
            if expected_match is True and len(matched_indexes) == 1
            else None
        )
        matched_acceptable_outcome_indexes = sorted(
            index for index in matched_indexes if isinstance(index, int)
        )
        if decision_surface_flipped and expected_match is not True:
            classification = "nondeterminism_unresolved"
        elif row_unsafe_repeat_count:
            classification = "stable_unsafe_outcome"
        elif decision_surface_flipped and expected_match is True:
            classification = "authoritative_acceptable_outcome_union"
        elif expected_match is True:
            classification = "stable_blind_judge_confirmed"
        elif judge_present:
            classification = "stable_blind_judge_mismatch_or_incomplete"
        else:
            classification = "stable_blind_judge_required"
        rows.append(
            {
                "post_id": pid,
                "expected_repeats": repeats,
                "observed_repeats": len(outcomes),
                "repeat_bindings": repeat_bindings,
                "unique_repeat_binding_count": len(unique_repeat_bindings),
                "independent_repeats_present": independent_repeats_present,
                "runtime_signatures": runtime_signatures,
                "unique_runtime_signature_count": len(unique_runtime_signatures),
                "runtime_signatures_valid": runtime_signatures_valid,
                "runtime_signature_issues": runtime_issues,
                "runtime_signature_payloads": runtime_payloads,
                # Preserve legacy raw/full outcome fields for readers that already
                # consume them.  They are diagnostic only; the explicit semantic
                # fields below are the release-gating decision surface.
                "unique_outcome_count": len(raw_counts),
                "flip_count": raw_flip_count,
                "flip_rate": raw_flip_rate,
                "flipped": raw_outcome_variance,
                "semantic_unique_decision_surface_count": len(semantic_counts),
                "stable_semantic_decision_surface": stable_semantic_decision_surface,
                "unique_semantic_decision_surfaces": unique_semantic_decision_surfaces,
                "semantic_decision_surface_counts": {
                    key: semantic_counts[key] for key in sorted(semantic_counts)
                },
                "decision_surface_flip_count": decision_surface_flip_count,
                "decision_surface_flip_rate": decision_surface_flip_rate,
                "decision_surface_flipped": decision_surface_flipped,
                "semantic_flip_count": semantic_flip_count,
                "semantic_flip_rate": semantic_flip_rate,
                "semantic_flipped": semantic_flipped,
                "semantic_adjudication_states": [
                    json.loads(key) for key in sorted(semantic_adjudication_counts)
                ],
                "semantic_adjudication_state_counts": {
                    key: semantic_adjudication_counts[key]
                    for key in sorted(semantic_adjudication_counts)
                },
                "raw_unique_outcome_count": len(raw_counts),
                "raw_flip_count": raw_flip_count,
                "raw_flip_rate": raw_flip_rate,
                "raw_outcome_variance": raw_outcome_variance,
                "classification": classification,
                "stable_outcome": stable_outcome,
                "unique_outcomes": unique_outcomes,
                "outcome_counts": {
                    key: raw_counts[key] for key in sorted(raw_counts)
                },
                "blind_judge_present": judge_present,
                "blind_judge_expected_match": expected_match,
                "blind_judge_match_repeat_count": repeat_match_count,
                "blind_judge_mismatch_repeat_count": repeat_mismatch_count,
                "unsafe_repeat_count": row_unsafe_repeat_count,
                "unsafe_or_blind_judge_mismatch_repeat_count": row_union_repeat_count,
                "wrong_or_unsafe_repeat_count": row_union_repeat_count,
                "expected_contract_authoritative": expected_contract_authoritative,
                "expected_contract_style": (
                    next(iter(styles)) if len(styles) == 1 else "mixed"
                ),
                "matched_acceptable_outcome_index": matched_acceptable_outcome_index,
                "matched_acceptable_outcome_indexes": matched_acceptable_outcome_indexes,
                "acceptable_outcome_union_authoritative": (
                    expected_contract_authoritative and row_unsafe_repeat_count == 0
                ),
                "mismatch_reasons": mismatch_reasons,
                "expected_mismatch_reasons": mismatch_reasons,
                "acceptable_outcome_mismatch_reasons": (
                    repeat_contract_evaluations[0][
                        "acceptable_outcome_mismatch_reasons"
                    ]
                    if repeat_contract_evaluations
                    else []
                ),
                "repeat_contract_evaluations": repeat_contract_evaluations,
            }
        )

    provenance_contract_met = bool(
        post_ids
        and post_ids_unique
        and all_repeats_present
        and all_independent_repeats_present
        and all_runtime_signatures_valid
        and len(global_runtime_signatures) == 1
        and minimum_repeats_contract_met
    )
    gate = (
        "GO"
        if provenance_contract_met
        and not any_semantic_flip
        and blind_judge_mismatch_repeat_count == 0
        and unsafe_repeat_count == 0
        and all_repeats_expected
        and all_expected_contracts_authoritative
        else "REVIEW"
    )
    if (
        not provenance_contract_met
        or any_semantic_flip
        or blind_judge_mismatch_repeat_count
        or unsafe_repeat_count
    ):
        gate = "NO-GO"
    return {
        "report_type": "safe_loss_flip_rate_probe",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "post_ids": post_ids,
        "repeats": repeats,
        "minimum_repeats": MINIMUM_ANALYZE_REPEATS,
        "minimum_repeats_contract_met": minimum_repeats_contract_met,
        "gate": gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "hard_hold_relaxation_allowed": gate == "GO",
        "summary": {
            "post_ids_present": bool(post_ids),
            "post_ids_unique": post_ids_unique,
            "all_repeats_present": all_repeats_present,
            "all_independent_repeats_present": all_independent_repeats_present,
            "all_runtime_signatures_valid": all_runtime_signatures_valid,
            "global_unique_runtime_signature_count": len(global_runtime_signatures),
            "minimum_repeats_contract_met": minimum_repeats_contract_met,
            # Legacy any_flip remains the raw/full outcome diagnostic.  Only the
            # explicit semantic metric participates in the release gate.
            "any_flip": any_raw_outcome_variance,
            "any_semantic_flip": any_semantic_flip,
            "any_decision_surface_flip": any_decision_surface_flip,
            "any_raw_outcome_variance": any_raw_outcome_variance,
            "all_stable_expected_by_blind_judge": all_repeats_expected,
            "all_repeats_expected_by_blind_judge": all_repeats_expected,
            "all_expected_contracts_authoritative": all_expected_contracts_authoritative,
            "flipped_post_ids": [row["post_id"] for row in rows if row["flipped"]],
            "semantic_flipped_post_ids": [
                row["post_id"] for row in rows if row["semantic_flipped"]
            ],
            "decision_surface_flipped_post_ids": [
                row["post_id"] for row in rows if row["decision_surface_flipped"]
            ],
            "raw_outcome_variance_post_ids": [
                row["post_id"] for row in rows if row["raw_outcome_variance"]
            ],
            "blind_judge_mismatch_repeat_count": blind_judge_mismatch_repeat_count,
            "unsafe_repeat_count": unsafe_repeat_count,
            "unsafe_or_blind_judge_mismatch_repeat_count": (
                unsafe_or_blind_judge_mismatch_repeat_count
            ),
            "wrong_or_unsafe_repeat_count": (
                unsafe_or_blind_judge_mismatch_repeat_count
            ),
            "blind_judge_mismatch_post_ids": [
                row["post_id"]
                for row in rows
                if row["blind_judge_mismatch_repeat_count"]
            ],
            "unsafe_post_ids": [
                row["post_id"] for row in rows if row["unsafe_repeat_count"]
            ],
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
        f"- minimum_repeats: `{report['minimum_repeats']}`",
        f"- minimum_repeats_contract_met: `{report['minimum_repeats_contract_met']}`",
        f"- post_ids: `{report['post_ids']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- hard_hold_relaxation_allowed: `{report['hard_hold_relaxation_allowed']}`",
        "",
        "## 요약",
        "",
        f"- post_ids_present: `{report['summary']['post_ids_present']}`",
        f"- post_ids_unique: `{report['summary']['post_ids_unique']}`",
        f"- all_repeats_present: `{report['summary']['all_repeats_present']}`",
        f"- all_independent_repeats_present: `{report['summary']['all_independent_repeats_present']}`",
        f"- all_runtime_signatures_valid: `{report['summary']['all_runtime_signatures_valid']}`",
        f"- global_unique_runtime_signature_count: `{report['summary']['global_unique_runtime_signature_count']}`",
        f"- any_flip (legacy raw diagnostic): `{report['summary']['any_flip']}`",
        f"- any_semantic_flip: `{report['summary']['any_semantic_flip']}`",
        f"- any_decision_surface_flip (acceptable union diagnostic): `{report['summary']['any_decision_surface_flip']}`",
        f"- any_raw_outcome_variance (diagnostic): `{report['summary']['any_raw_outcome_variance']}`",
        f"- all_stable_expected_by_blind_judge: `{report['summary']['all_stable_expected_by_blind_judge']}`",
        f"- all_expected_contracts_authoritative: `{report['summary']['all_expected_contracts_authoritative']}`",
        f"- flipped_post_ids: `{report['summary']['flipped_post_ids']}`",
        f"- raw_outcome_variance_post_ids: `{report['summary']['raw_outcome_variance_post_ids']}`",
        f"- blind_judge_mismatch_repeat_count: `{report['summary']['blind_judge_mismatch_repeat_count']}`",
        f"- unsafe_repeat_count: `{report['summary']['unsafe_repeat_count']}`",
        f"- unsafe_or_blind_judge_mismatch_repeat_count: `{report['summary']['unsafe_or_blind_judge_mismatch_repeat_count']}`",
        f"- blind_judge_missing_post_ids: `{report['summary']['blind_judge_missing_post_ids']}`",
    ]
    runtime_audit = report.get("runtime_contract_audit")
    if isinstance(runtime_audit, dict):
        runtime_summary = _mapping(runtime_audit.get("summary"))
        lines.extend(
            [
                "",
                "## Runtime plan 계약 감사",
                "",
                f"- required: `{report.get('runtime_contract_required', False)}`",
                f"- gate: `{runtime_audit.get('gate')}`",
                f"- run_plan: `{runtime_audit.get('run_plan')}`",
                f"- expected_run_count: `{runtime_audit.get('expected_run_count')}`",
                f"- planned_run_count: `{runtime_summary.get('planned_run_count')}`",
                f"- provided_result_count: `{runtime_summary.get('provided_result_count')}`",
                f"- manifest_count: `{runtime_summary.get('manifest_count')}`",
                f"- unique_run_id_count: `{runtime_summary.get('unique_run_id_count')}`",
                f"- execution_adopted_completion_count: `{runtime_summary.get('execution_adopted_completion_count')}`",
                f"- execution_child_started_count: `{runtime_summary.get('execution_child_started_count')}`",
                f"- execution_failed_attempt_count: `{runtime_summary.get('execution_failed_attempt_count')}`",
                f"- execution_indeterminate_attempt_count: `{runtime_summary.get('execution_indeterminate_attempt_count')}`",
                f"- issues: `{runtime_audit.get('issues', [])}`",
            ]
        )
    lines.extend(["", "## 행별 결과", ""])
    for row in report["rows"]:
        lines.extend(
            [
                f"### {row['post_id']}",
                "",
                f"- observed_repeats: `{row['observed_repeats']}` / `{row['expected_repeats']}`",
                f"- independent_repeats_present: `{row['independent_repeats_present']}`",
                f"- unique_repeat_binding_count: `{row['unique_repeat_binding_count']}`",
                f"- repeat_bindings: `{row['repeat_bindings']}`",
                f"- runtime_signatures_valid: `{row['runtime_signatures_valid']}`",
                f"- runtime_signature_issues: `{row['runtime_signature_issues']}`",
                f"- runtime_signature_payloads: `{row['runtime_signature_payloads']}`",
                f"- unique_outcome_count (legacy raw diagnostic): `{row['unique_outcome_count']}`",
                f"- flip_rate (legacy raw diagnostic): `{row['flip_rate']}`",
                f"- semantic_unique_decision_surface_count: `{row['semantic_unique_decision_surface_count']}`",
                f"- decision_surface_flip_rate (diagnostic): `{row['decision_surface_flip_rate']}`",
                f"- semantic_flip_rate (judge/safety adjudication): `{row['semantic_flip_rate']}`",
                f"- raw_unique_outcome_count (diagnostic): `{row['raw_unique_outcome_count']}`",
                f"- raw_flip_rate (diagnostic): `{row['raw_flip_rate']}`",
                f"- classification: `{row['classification']}`",
                f"- blind_judge_expected_match: `{row['blind_judge_expected_match']}`",
                f"- blind_judge_match_repeat_count: `{row['blind_judge_match_repeat_count']}`",
                f"- blind_judge_mismatch_repeat_count: `{row['blind_judge_mismatch_repeat_count']}`",
                f"- unsafe_repeat_count: `{row['unsafe_repeat_count']}`",
                f"- unsafe_or_blind_judge_mismatch_repeat_count: `{row['unsafe_or_blind_judge_mismatch_repeat_count']}`",
                f"- expected_contract_authoritative: `{row['expected_contract_authoritative']}`",
                f"- matched_acceptable_outcome_index: `{row['matched_acceptable_outcome_index']}`",
                f"- matched_acceptable_outcome_indexes: `{row['matched_acceptable_outcome_indexes']}`",
                f"- acceptable_outcome_union_authoritative: `{row['acceptable_outcome_union_authoritative']}`",
                f"- expected_mismatch_reasons: `{row['expected_mismatch_reasons']}`",
                f"- stable_semantic_decision_surface: `{row['stable_semantic_decision_surface']}`",
                f"- stable_outcome: `{row['stable_outcome']}`",
                f"- repeat_contract_evaluations: `{row['repeat_contract_evaluations']}`",
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
    plan.add_argument("--parallel", type=int, default=16)
    plan.add_argument("--runtime-model", required=True)
    plan.add_argument("--runtime-llm-mode", required=True)
    plan.add_argument("--runtime-llm-endpoint", required=True)
    plan.add_argument("--runtime-prompt-version", required=True)
    plan.add_argument("--runtime-release-fingerprint-sha256", required=True)
    plan.add_argument("--blind-judge", required=True, type=Path)
    plan.add_argument("--analysis-output-json", required=True, type=Path)
    plan.add_argument("--analysis-output-md", required=True, type=Path)
    plan.add_argument(
        "--required-env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Required environment entry copied exactly to the plan and every planned run.",
    )
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
    analyze.add_argument(
        "--run-plan",
        type=Path,
        default=None,
        help="Independent N=5 x 5 run-plan JSON whose exact results/manifests are audited.",
    )
    analyze.add_argument(
        "--require-runtime-contract",
        action="store_true",
        help="Fail closed unless the exact 25-run plan/result/manifest runtime contract audits GO.",
    )
    analyze.add_argument("--output-json", required=True, type=Path)
    analyze.add_argument("--output-md", required=True, type=Path)
    analyze.add_argument("--fail-on-flip", action="store_true")
    analyze.add_argument(
        "--fail-on-no-go",
        action="store_true",
        help="Return nonzero when the final semantic/runtime report gate is not GO.",
    )
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
            parallel=requested_parallel_for_test_run(1) if int(args.parallel) <= 0 else max(1, int(args.parallel)),
            expert_args=list(args.expert_arg or []),
            minimum_repeats=max(1, int(args.minimum_repeats)),
            runtime_model=args.runtime_model,
            runtime_llm_mode=args.runtime_llm_mode,
            runtime_llm_endpoint=args.runtime_llm_endpoint,
            runtime_prompt_version=args.runtime_prompt_version,
            runtime_release_fingerprint_sha256=args.runtime_release_fingerprint_sha256,
            required_env=parse_required_env_entries(list(args.required_env or [])),
            blind_judge=args.blind_judge,
            run_plan_path=args.manifest,
            analysis_output_json=args.analysis_output_json,
            analysis_output_md=args.analysis_output_md,
            source_input_path=args.source_input,
        )
        write_entries = [
            (input_path, probe_input_text([row]).encode("utf-8"))
            for input_path, row in input_writes
        ]
        write_entries.append(
            (
                args.manifest,
                (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
        )
        runtime_and_analysis_paths = [args.analysis_output_json, args.analysis_output_md]
        runtime_and_analysis_paths.append(
            resolve_artifact_path(manifest["execution_claim_contract"]["anchor_dir"])
        )
        for run in manifest["planned_runs"]:
            runtime_and_analysis_paths.extend(
                resolve_artifact_path(run[field])
                for field in ("output_json", "checkpoint_jsonl", "manifest_json")
            )
        _assert_artifact_paths_absent(
            [path for path, _payload in write_entries] + runtime_and_analysis_paths
        )
        _exclusive_write_bundle(write_entries)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        if manifest["missing_post_ids"]:
            return 1
        if not manifest["minimum_repeats_contract_met"]:
            return 2
        return 0

    repeats = max(1, int(args.repeats))
    runtime_audit_requested = bool(args.run_plan or args.require_runtime_contract)
    if runtime_audit_requested:
        runtime_contract_audit = audit_run_plan_runtime_contract(
            run_plan_path=(resolve_artifact_path(args.run_plan) if args.run_plan else None),
            result_paths=list(args.result),
            post_ids=post_ids,
            repeats=repeats,
            blind_judge_path=args.blind_judge,
        )
        runtime_contract_audit["required"] = bool(args.require_runtime_contract)
    else:
        runtime_contract_audit = {
            "report_type": "safe_loss_flip_rate_runtime_plan_contract_audit",
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "gate": "NOT_REQUESTED",
            "required": False,
            "run_plan": None,
            "expected_post_ids": post_ids,
            "expected_repeats": repeats,
            "expected_run_count": len(post_ids) * repeats,
            "issues": [],
            "runs": [],
            "runtime_bindings_by_result_path": {},
            "summary": {},
        }
    try:
        semantic_blind_judge = load_blind_judge(args.blind_judge)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if not runtime_audit_requested:
            raise
        semantic_blind_judge = {}
        runtime_contract_audit["issues"].append(
            f"blind_judge_semantic_load_failed:{type(exc).__name__}:{exc}"
        )
        runtime_contract_audit["gate"] = "NO-GO"
        runtime_contract_audit.setdefault("summary", {})["issue_count"] = len(
            runtime_contract_audit["issues"]
        )
    report = analyze_flip_rate(
        result_rows=load_result_rows_with_bindings(
            result_paths=list(args.result),
            runtime_contract_audit=runtime_contract_audit,
        ),
        post_ids=post_ids,
        repeats=repeats,
        blind_judge=semantic_blind_judge,
    )
    report["result_paths"] = [str(path) for path in args.result]
    report["run_plan_path"] = str(args.run_plan) if args.run_plan else None
    report["runtime_contract_required"] = bool(args.require_runtime_contract)
    report["runtime_contract_audit"] = runtime_contract_audit
    report["summary"]["runtime_contract_required"] = bool(args.require_runtime_contract)
    report["summary"]["runtime_contract_gate"] = runtime_contract_audit["gate"]
    if args.require_runtime_contract and runtime_contract_audit["gate"] != "GO":
        report["gate"] = "NO-GO"
        report["hard_hold_relaxation_allowed"] = False
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_flip and report["summary"]["any_semantic_flip"]:
        return 2
    if args.require_runtime_contract and runtime_contract_audit["gate"] != "GO":
        return 3
    if args.fail_on_no_go and report["gate"] != "GO":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
