#!/usr/bin/env python3
"""동결 2,712행의 저장된 publish contract를 현재 순수 계약으로 재평가한다.

네트워크와 ``expert_main.py``를 사용하지 않는다. 최종 의미 판정 ledger는 cohort
집계용으로만 읽으며, production promotion decision의 입력으로 사용하지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.llm_batch.promotion_gate import (
    PUBLISH_CONTRACT_VERSION,
    evaluate_publish_contract,
    evidence_records_from_payload,
    grounding_state_from_dict,
)


DEFAULT_LEDGER = REPO_ROOT / "out/live_combined_row_review_20260715_143806_848671_2712_20260716/final_2712_row_adjudication_ledger.jsonl"
DEFAULT_RAW_RESULT = REPO_ROOT / "out/expert_result_20260715_143806_848671.json"
ROW_SCHEMA = "frozen_2712_publish_contract_replay_row_v2"
SUMMARY_SCHEMA = "frozen_2712_publish_contract_replay_summary_v2"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_ref(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: row must be an object")
        rows.append(value)
    return rows


def _post_id(row: Mapping[str, Any], *, label: str) -> str:
    value = row.get("post_id")
    if value is None or isinstance(value, bool) or not str(value).strip():
        raise ValueError(f"{label}: post_id missing or invalid")
    return str(value).strip()


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
        raise ValueError(f"{label}: duplicate post_id values: {sorted(set(duplicates))[:10]}")
    return order, index


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_canonical(row).decode("utf-8") + "\n" for row in rows), encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _contract_version(container: Mapping[str, Any]) -> str:
    decision = _as_mapping(container.get("promotion_decision")) or {}
    trace = _as_mapping(container.get("publish_contract_trace")) or {}
    return str(
        container.get("publish_contract_version")
        or decision.get("contract_version")
        or trace.get("contract_version")
        or ""
    ).strip()


def _has_typed_contract(container: Mapping[str, Any]) -> bool:
    return (
        isinstance(container.get("promotion_gate_state"), Mapping)
        and isinstance(container.get("promotion_gate_evidence"), list)
        and isinstance(container.get("promotion_decision"), Mapping)
    )


def _authoritative_contract(identity: Mapping[str, Any]) -> tuple[str | None, Mapping[str, Any] | None, str | None]:
    """Select root v2 input, then only an explicitly v2 candidate-ledger mirror."""
    if _has_typed_contract(identity) and _contract_version(identity) == PUBLISH_CONTRACT_VERSION:
        return "identity", identity, None
    ledger = _as_mapping(identity.get("candidate_ledger"))
    # A nested mirror is only a fallback when its own schema marker says it is
    # authoritative.  Do not promote a stray nested decision/trace field.
    if (
        ledger is not None
        and _has_typed_contract(ledger)
        and str(ledger.get("publish_contract_version") or "").strip() == PUBLISH_CONTRACT_VERSION
    ):
        return "candidate_ledger", ledger, None
    if _has_typed_contract(identity):
        return None, None, "root_contract_not_authoritative_v2"
    if ledger is not None and _has_typed_contract(ledger):
        return None, None, "candidate_ledger_contract_not_authoritative_v2"
    return None, None, "authoritative_state_evidence_decision_missing"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _stored_projection(decision: Mapping[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    allowed = decision.get("publish_allowed")
    if not isinstance(allowed, bool):
        return None, ["stored_publish_allowed_not_strict_bool"]
    title = _optional_text(decision.get("official_title"))
    url = _optional_text(decision.get("official_url"))
    if decision.get("official_title") not in (None, "") and title is None:
        errors.append("stored_official_title_not_text")
    if decision.get("official_url") not in (None, "") and url is None:
        errors.append("stored_official_url_not_text")
    if allowed and title is None:
        errors.append("stored_publish_missing_title")
    if not allowed and (title is not None or url is not None):
        errors.append("stored_nonpublish_public_projection_present")
    if decision.get("bypassed_gate") is not False:
        errors.append("stored_gate_bypass_not_false")
    return {"publish_allowed": allowed, "official_title": title, "official_url": url}, errors


def _decision_projection(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "publish_allowed": decision.get("publish_allowed"),
        "official_title": _optional_text(decision.get("official_title")),
        "official_url": _optional_text(decision.get("official_url")),
    }


def _fingerprint_match(container: Mapping[str, Any], decision: Mapping[str, Any], recomputed: Any) -> tuple[str, list[str]]:
    candidates = {
        "container": container.get("publish_contract_input_fingerprint"),
        "decision": decision.get("input_fingerprint"),
        "trace": (_as_mapping(container.get("publish_contract_trace")) or {}).get("input_fingerprint"),
    }
    known = {name: value for name, value in candidates.items() if isinstance(value, str) and value.strip()}
    if not known:
        return "NOT_ESTIMABLE", ["stored_fingerprint_missing"]
    mismatched = [name for name, value in known.items() if value != recomputed.input_fingerprint]
    return ("MATCH" if not mismatched else "MISMATCH"), ([f"fingerprint_{name}_mismatch" for name in mismatched])


def _adjudication(row: Mapping[str, Any]) -> dict[str, str | None]:
    verdict = _as_mapping(row.get("independent_semantic_verdict")) or {}
    pipeline = _as_mapping(row.get("pipeline")) or {}
    return {
        "review_verdict": _optional_text(verdict.get("review_verdict")),
        "dashboard_action": _optional_text(verdict.get("dashboard_action")),
        "recommended_title": _optional_text(verdict.get("recommended_title")),
        "dashboard_title_expected": _optional_text(verdict.get("dashboard_title_expected")),
        "pipeline_official_title": _optional_text(pipeline.get("official_title")),
    }


def _adjudication_assessment(
    projection: Mapping[str, Any], adjudication: Mapping[str, Any]
) -> dict[str, Any]:
    """Score a projection after replay; this never feeds the publish contract."""
    action = _optional_text(adjudication.get("dashboard_action"))
    published = projection.get("publish_allowed") is True
    title = _optional_text(projection.get("official_title"))
    if action == "KEEP":
        expected = (
            _optional_text(adjudication.get("pipeline_official_title"))
            or _optional_text(adjudication.get("recommended_title"))
            or _optional_text(adjudication.get("dashboard_title_expected"))
        )
        if not expected:
            return {
                "adjudicated_unsafe_publish": None if published else False,
                "adjudication_compliant": "NOT_ESTIMABLE",
                "not_estimable_reason": "adjudication_expected_title_missing",
            }
        if published and title == expected:
            return {"adjudicated_unsafe_publish": False, "adjudication_compliant": "COMPLIANT"}
        return {
            "adjudicated_unsafe_publish": bool(published),
            "adjudication_compliant": "NONCOMPLIANT",
            "expected_public_title": expected,
        }
    if action == "CORRECT":
        recommended = _optional_text(adjudication.get("recommended_title"))
        dashboard_expected = _optional_text(adjudication.get("dashboard_title_expected"))
        if recommended and dashboard_expected and recommended != dashboard_expected:
            return {
                "adjudicated_unsafe_publish": None if published else False,
                "adjudication_compliant": "NOT_ESTIMABLE",
                "not_estimable_reason": "adjudication_expected_title_conflict",
            }
        expected = recommended or dashboard_expected
        if not expected:
            return {
                "adjudicated_unsafe_publish": None if published else False,
                "adjudication_compliant": "NOT_ESTIMABLE",
                "not_estimable_reason": "adjudication_expected_title_missing",
            }
        if published and title == expected:
            return {"adjudicated_unsafe_publish": False, "adjudication_compliant": "COMPLIANT"}
        return {
            "adjudicated_unsafe_publish": bool(published),
            "adjudication_compliant": "NONCOMPLIANT",
            "expected_public_title": expected,
        }
    if action in {"HOLD", "REMOVE", "NOT_APPLICABLE"}:
        return {
            "adjudicated_unsafe_publish": bool(published),
            "adjudication_compliant": "NONCOMPLIANT" if published else "COMPLIANT",
        }
    return {
        "adjudicated_unsafe_publish": None if published else False,
        "adjudication_compliant": "NOT_ESTIMABLE",
        "not_estimable_reason": "adjudication_dashboard_action_missing_or_unsupported",
    }


def _replay_row(post_id: str, raw: Mapping[str, Any], ledger: Mapping[str, Any]) -> dict[str, Any]:
    identity = _as_mapping((_as_mapping(raw.get("analysis_result")) or {}).get("identity"))
    base = {
        "schema_version": ROW_SCHEMA,
        "post_id": post_id,
        "adjudication_cohort": _adjudication(ledger),
        "adjudication_used_as_production_input": False,
        "semantic_publication_state": "UNKNOWN_NOT_ESTIMABLE",
    }
    if identity is None:
        return {**base, "replay_status": "NOT_ESTIMABLE", "not_estimable_reasons": ["identity_missing"]}
    source_name, container, source_error = _authoritative_contract(identity)
    if container is None:
        return {**base, "replay_status": "NOT_ESTIMABLE", "not_estimable_reasons": [source_error]}
    state_payload = container["promotion_gate_state"]
    evidence_payload = container["promotion_gate_evidence"]
    decision = _as_mapping(container["promotion_decision"])
    assert decision is not None
    semantic_present = isinstance(state_payload.get("semantic_publication"), Mapping)
    stored_projection, stored_errors = _stored_projection(decision)
    if stored_projection is None:
        return {
            **base,
            "authoritative_source": source_name,
            "semantic_publication_state": "PRESENT" if semantic_present else "LEGACY_MISSING_NEUTRAL_COMPATIBILITY",
            "replay_status": "NOT_ESTIMABLE",
            "not_estimable_reasons": stored_errors,
        }
    try:
        state = grounding_state_from_dict(state_payload)
        if state.post_id is None or str(state.post_id) != post_id:
            raise ValueError("persisted_state_post_id_mismatch")
        evidence = evidence_records_from_payload(evidence_payload)
        contract = evaluate_publish_contract(state, evidence)
    except (TypeError, ValueError) as error:
        return {
            **base,
            "authoritative_source": source_name,
            "semantic_publication_state": "PRESENT" if semantic_present else "LEGACY_MISSING_NEUTRAL_COMPATIBILITY",
            "replay_status": "NOT_ESTIMABLE",
            "not_estimable_reasons": [f"state_or_evidence_unparseable:{error}"],
        }
    recomputed_decision = contract.decision.to_dict()
    recomputed_projection = _decision_projection(recomputed_decision)
    stored_adjudication = _adjudication_assessment(stored_projection, base["adjudication_cohort"])
    recomputed_adjudication = _adjudication_assessment(recomputed_projection, base["adjudication_cohort"])
    reason_codes = decision.get("reason_codes")
    if isinstance(reason_codes, list) and all(isinstance(code, str) for code in reason_codes):
        reason_codes_match = "MATCH" if reason_codes == recomputed_decision["reason_codes"] else "MISMATCH"
        reason_reason = []
    else:
        reason_codes_match, reason_reason = "NOT_ESTIMABLE", ["stored_reason_codes_missing_or_invalid"]
    fingerprint_match, fingerprint_reasons = _fingerprint_match(container, decision, contract)
    projection_match = "MATCH" if stored_projection == recomputed_projection else "MISMATCH"
    comparison_reasons = [*stored_errors, *reason_reason, *fingerprint_reasons]
    current_contract_abnormal = projection_match == "MISMATCH" or reason_codes_match == "MISMATCH" or fingerprint_match == "MISMATCH"
    stored_contract_normal = not stored_errors
    return {
        **base,
        "authoritative_source": source_name,
        "authoritative_input": {"state_sha256": _sha256(state_payload), "evidence_sha256": _sha256(evidence_payload)},
        "semantic_publication_state": "PRESENT" if semantic_present else "LEGACY_MISSING_NEUTRAL_COMPATIBILITY",
        "replay_status": "ESTIMABLE",
        "stored": {
            "public_projection": stored_projection,
            "reason_codes": reason_codes,
            "input_fingerprint": decision.get("input_fingerprint"),
            **stored_adjudication,
        },
        "recomputed": {
            "public_projection": recomputed_projection,
            "reason_codes": recomputed_decision["reason_codes"],
            "input_fingerprint": contract.input_fingerprint,
            **recomputed_adjudication,
        },
        "comparison": {
            "public_projection": projection_match,
            "reason_codes": reason_codes_match,
            "input_fingerprint": fingerprint_match,
        },
        "stored_contract_internally_invalid": bool(stored_errors),
        "recomputed_contract_internally_invalid": current_contract_abnormal,
        "normal_to_abnormal_contract_regression": stored_contract_normal and current_contract_abnormal,
        "stored_compliant_to_recomputed_noncompliant_semantic_regression": (
            stored_adjudication["adjudication_compliant"] == "COMPLIANT"
            and recomputed_adjudication["adjudication_compliant"] == "NONCOMPLIANT"
        ),
        "comparison_reasons": comparison_reasons,
    }


def replay_frozen_contract(*, ledger_path: Path, raw_result_path: Path, output_dir: Path, profile: str = "frozen2712") -> dict[str, Any]:
    ledger_rows = _read_jsonl(ledger_path)
    ledger_order, ledger_index = _index_unique(ledger_rows, label="final adjudication ledger")
    raw_payload = json.loads(raw_result_path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw_payload, list) or not all(isinstance(row, dict) for row in raw_payload):
        raise ValueError("raw result must be a JSON array of objects")
    raw_order, raw_index = _index_unique(raw_payload, label="raw result")
    missing = [post_id for post_id in ledger_order if post_id not in raw_index]
    if missing:
        raise ValueError(f"raw result missing ledger post_id values: {missing[:10]}")
    if profile == "frozen2712" and len(ledger_order) != 2712:
        raise ValueError(f"frozen2712 profile requires 2712 ledger rows, got {len(ledger_order)}")
    if profile not in {"frozen2712", "none"}:
        raise ValueError(f"unsupported profile: {profile}")

    rows = [_replay_row(post_id, raw_index[post_id], ledger_index[post_id]) for post_id in ledger_order]
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / "publish_contract_replay_rows.jsonl"
    _write_jsonl(rows_path, rows)
    estimable = [row for row in rows if row["replay_status"] == "ESTIMABLE"]
    not_estimable = [row for row in rows if row["replay_status"] == "NOT_ESTIMABLE"]
    verdict_counts = Counter(
        row["adjudication_cohort"]["review_verdict"] or "MISSING" for row in rows
    )
    action_counts = Counter(
        row["adjudication_cohort"]["dashboard_action"] or "MISSING" for row in rows
    )
    reason_counts = Counter(reason for row in not_estimable for reason in row["not_estimable_reasons"])
    comparison_counts = Counter(reason for row in estimable for reason in row["comparison_reasons"])
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "profile": profile,
        "purpose": "deterministic_persisted_publish_contract_replay_not_semantic_llm_effectiveness",
        "network_used": False,
        "expert_main_used": False,
        "semantic_adjudication_is_cohort_only_not_production_input": True,
        "legacy_semantic_publication_policy": "missing SemanticPublicationState is neutral compatibility; it is not an effectiveness claim",
        "sources": {"final_adjudication_ledger": _file_ref(ledger_path), "raw_result": _file_ref(raw_result_path)},
        "coverage": {
            "ledger_rows": len(ledger_order),
            "ledger_unique_post_ids": len(ledger_index),
            "raw_rows": len(raw_payload),
            "raw_unique_post_ids": len(raw_index),
            "ledger_missing_from_raw": 0,
            "raw_extra_to_ledger": len(set(raw_order) - set(ledger_order)),
            "replay_rows": len(rows),
            "estimable_rows": len(estimable),
            "not_estimable_rows": len(not_estimable),
        },
        "adjudicated_cohorts": {"review_verdict": dict(sorted(verdict_counts.items())), "dashboard_action": dict(sorted(action_counts.items()))},
        "contract_counts": {
            "stored_contract_internally_invalid": sum(row["stored_contract_internally_invalid"] for row in estimable),
            "recomputed_contract_internally_invalid": sum(row["recomputed_contract_internally_invalid"] for row in estimable),
            "normal_to_abnormal_contract_regressions": sum(row["normal_to_abnormal_contract_regression"] for row in estimable),
            "public_projection_mismatch": sum(row["comparison"]["public_projection"] == "MISMATCH" for row in estimable),
            "reason_codes_mismatch": sum(row["comparison"]["reason_codes"] == "MISMATCH" for row in estimable),
            "fingerprint_mismatch": sum(row["comparison"]["input_fingerprint"] == "MISMATCH" for row in estimable),
            "legacy_semantic_publication_present": sum(row["semantic_publication_state"] == "PRESENT" for row in rows),
            "legacy_semantic_publication_missing_neutral_compatibility": sum(row["semantic_publication_state"] == "LEGACY_MISSING_NEUTRAL_COMPATIBILITY" for row in rows),
            "semantic_publication_unknown_not_estimable": sum(row["semantic_publication_state"] == "UNKNOWN_NOT_ESTIMABLE" for row in rows),
        },
        "adjudication_projection_counts": {
            "stored_adjudicated_unsafe_publish": sum(row["stored"]["adjudicated_unsafe_publish"] is True for row in estimable),
            "recomputed_adjudicated_unsafe_publish": sum(row["recomputed"]["adjudicated_unsafe_publish"] is True for row in estimable),
            "stored_adjudicated_unsafe_publish_not_estimable": sum(row["stored"]["adjudicated_unsafe_publish"] is None for row in estimable),
            "recomputed_adjudicated_unsafe_publish_not_estimable": sum(row["recomputed"]["adjudicated_unsafe_publish"] is None for row in estimable),
            "stored_adjudication_compliant": sum(row["stored"]["adjudication_compliant"] == "COMPLIANT" for row in estimable),
            "stored_adjudication_noncompliant": sum(row["stored"]["adjudication_compliant"] == "NONCOMPLIANT" for row in estimable),
            "stored_adjudication_not_estimable": sum(row["stored"]["adjudication_compliant"] == "NOT_ESTIMABLE" for row in estimable),
            "recomputed_adjudication_compliant": sum(row["recomputed"]["adjudication_compliant"] == "COMPLIANT" for row in estimable),
            "recomputed_adjudication_noncompliant": sum(row["recomputed"]["adjudication_compliant"] == "NONCOMPLIANT" for row in estimable),
            "recomputed_adjudication_not_estimable": sum(row["recomputed"]["adjudication_compliant"] == "NOT_ESTIMABLE" for row in estimable),
            "stored_compliant_to_recomputed_noncompliant_semantic_regressions": sum(
                row["stored_compliant_to_recomputed_noncompliant_semantic_regression"] for row in estimable
            ),
        },
        "not_estimable_reasons": dict(sorted(reason_counts.items())),
        "comparison_reasons": dict(sorted(comparison_counts.items())),
        "artifacts": {"rows_jsonl": _file_ref(rows_path), "post_id_order_sha256": _sha256(ledger_order)},
        "gate": "GO" if not not_estimable and not any(row["normal_to_abnormal_contract_regression"] for row in estimable) else "REVIEW",
    }
    _write_json(output_dir / "publish_contract_replay_summary.json", summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--raw-result", type=Path, default=DEFAULT_RAW_RESULT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("frozen2712", "none"), default="frozen2712")
    return parser


def main() -> int:
    args = _parser().parse_args()
    summary = replay_frozen_contract(
        ledger_path=args.ledger.resolve(), raw_result_path=args.raw_result.resolve(), output_dir=args.output_dir.resolve(), profile=args.profile
    )
    print(json.dumps({"gate": summary["gate"], "summary": str((args.output_dir / "publish_contract_replay_summary.json").resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
