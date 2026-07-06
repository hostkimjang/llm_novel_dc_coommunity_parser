from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PUBLIC_TITLE_KEYS = ("official_title", "official_novel_title", "resolved_title")
PUBLIC_URL_KEYS = ("heretic_url", "official_url", "resolved_url")
NO_CANDIDATE_REASON_CODES = {
    "hold_without_candidates",
    "no_candidate_title",
    "missing_candidate_title",
    "no_public_candidate",
}


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
        for key in ("results", "rows", "items", "data"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    raise ValueError(f"Unsupported row payload: {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def row_post_id(row: dict[str, Any]) -> str:
    row = unwrap_result_row(row)
    for source in (
        row,
        row.get("analysis_result") if isinstance(row.get("analysis_result"), dict) else {},
        row_identity(row),
    ):
        if isinstance(source, dict) and source.get("post_id") not in (None, ""):
            return str(source.get("post_id")).strip()
    return ""


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _first_public_value(identity: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    novel = _dict_or_empty(identity.get("novel_identity"))
    for source in (novel, identity):
        for key in keys:
            value = _string_or_none(source.get(key))
            if value:
                return value
    return None


def _public_identity(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_title": _first_public_value(identity, PUBLIC_TITLE_KEYS),
        "official_url": _first_public_value(identity, PUBLIC_URL_KEYS),
    }


def _same_dict(left: Any, right: Any) -> bool:
    return isinstance(left, dict) and isinstance(right, dict) and left == right


def _candidate_title_url(value: Any) -> dict[str, str | None]:
    payload = _dict_or_empty(value)
    return {
        "official_title": _string_or_none(payload.get("official_title")),
        "official_url": _string_or_none(payload.get("official_url")),
    }


def _has_candidate_payload(value: Any) -> bool:
    candidate = _candidate_title_url(value)
    return bool(candidate["official_title"] or candidate["official_url"])


def _append_violation(violations: list[dict[str, Any]], code: str, detail: str) -> None:
    violations.append({"code": code, "detail": detail})


def audit_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    identity = row_identity(row)
    post_id = row_post_id(row)
    public_identity = _public_identity(identity)
    violations: list[dict[str, Any]] = []
    if not identity:
        _append_violation(violations, "missing_identity", "row has no identity payload")
        return {
            "index": index,
            "post_id": post_id,
            "gate": "NO-GO",
            "public_identity": public_identity,
            "violations": violations,
        }

    ledger = _dict_or_empty(identity.get("candidate_ledger"))
    decision = identity.get("promotion_decision")
    if not isinstance(decision, dict):
        decision = ledger.get("promotion_decision")
    trace = identity.get("publish_contract_trace")
    if not isinstance(trace, dict):
        trace = ledger.get("publish_contract_trace")
    publish_ledger = identity.get("publish_ledger")
    if not isinstance(publish_ledger, dict):
        publish_ledger = ledger.get("publish_ledger")

    has_public_title = bool(public_identity["official_title"])
    if has_public_title and not isinstance(decision, dict):
        _append_violation(
            violations,
            "missing_publication_decision_for_public_identity",
            "serialized public title exists without PromotionDecision",
        )
    if isinstance(decision, dict) and not isinstance(trace, dict):
        _append_violation(violations, "missing_publish_contract_trace", "PromotionDecision exists without trace")
    if isinstance(decision, dict) and not isinstance(publish_ledger, dict):
        _append_violation(violations, "missing_publish_ledger", "PromotionDecision exists without publish ledger")

    if not isinstance(decision, dict):
        return {
            "index": index,
            "post_id": post_id,
            "gate": "NO-GO" if violations else "GO",
            "public_identity": public_identity,
            "violations": violations,
        }

    gate_decision = _dict_or_empty(trace.get("gate_decision")) if isinstance(trace, dict) else {}
    ledger_gate_decision = _dict_or_empty(publish_ledger.get("gate_decision")) if isinstance(publish_ledger, dict) else {}
    pre_gate_candidate = trace.get("pre_gate_candidate") if isinstance(trace, dict) else {}
    ledger_candidate_preservation = (
        publish_ledger.get("candidate_preservation") if isinstance(publish_ledger, dict) else {}
    )
    candidate_decision = ledger.get("promotion_decision")
    candidate_trace = ledger.get("publish_contract_trace")
    candidate_publish_ledger = ledger.get("publish_ledger")

    if decision.get("bypassed_gate") is True:
        _append_violation(violations, "promotion_decision_bypassed_gate", "PromotionDecision bypassed_gate=true")
    if not _same_dict(candidate_decision, decision):
        _append_violation(
            violations,
            "candidate_ledger_promotion_decision_mismatch",
            "candidate_ledger.promotion_decision differs from identity.promotion_decision",
        )
    if isinstance(trace, dict) and not _same_dict(gate_decision, decision):
        _append_violation(
            violations,
            "publish_contract_trace_gate_decision_mismatch",
            "publish_contract_trace.gate_decision differs from PromotionDecision",
        )
    if isinstance(publish_ledger, dict) and not _same_dict(ledger_gate_decision, decision):
        _append_violation(
            violations,
            "publish_ledger_gate_decision_mismatch",
            "publish_ledger.gate_decision differs from PromotionDecision",
        )
    if isinstance(trace, dict) and not _same_dict(candidate_trace, trace):
        _append_violation(
            violations,
            "candidate_ledger_publish_contract_trace_mismatch",
            "candidate_ledger.publish_contract_trace differs from identity.publish_contract_trace",
        )
    if isinstance(publish_ledger, dict) and not _same_dict(candidate_publish_ledger, publish_ledger):
        _append_violation(
            violations,
            "candidate_ledger_publish_ledger_mismatch",
            "candidate_ledger.publish_ledger differs from identity.publish_ledger",
        )

    publish_allowed = decision.get("publish_allowed") is True
    status = str(decision.get("status") or "").strip()
    if publish_allowed and status != "publish":
        _append_violation(violations, "publish_allowed_status_mismatch", "publish_allowed=true but status is not publish")
    if not publish_allowed and status == "publish":
        _append_violation(violations, "blocked_decision_status_publish", "publish_allowed=false but status=publish")
    if publish_allowed and decision.get("candidate_preserved") is True:
        _append_violation(
            violations,
            "publish_allowed_candidate_preserved_true",
            "publish_allowed=true but candidate_preserved=true",
        )

    post_gate = _dict_or_empty(trace.get("post_gate_identity")) if isinstance(trace, dict) else {}
    public_publish = _dict_or_empty(publish_ledger.get("public_publish")) if isinstance(publish_ledger, dict) else {}
    expected_title = _string_or_none(decision.get("official_title"))
    expected_url = _string_or_none(decision.get("official_url"))
    if publish_allowed:
        if not expected_title:
            _append_violation(violations, "publish_allowed_missing_official_title", "allowed decision lacks official_title")
        if _string_or_none(post_gate.get("official_title")) != expected_title:
            _append_violation(
                violations,
                "post_gate_identity_title_mismatch",
                "post_gate_identity.official_title does not match allowed decision",
            )
        if _string_or_none(post_gate.get("official_url")) != expected_url:
            _append_violation(
                violations,
                "post_gate_identity_url_mismatch",
                "post_gate_identity.official_url does not match allowed decision",
            )
        if _string_or_none(public_publish.get("official_title")) != expected_title:
            _append_violation(
                violations,
                "publish_ledger_public_title_mismatch",
                "publish_ledger.public_publish.official_title does not match allowed decision",
            )
        if public_identity["official_title"] != expected_title:
            _append_violation(
                violations,
                "serialized_public_title_mismatch",
                "serialized official_title does not match allowed decision",
            )
    else:
        reason_codes = {
            str(code or "").strip()
            for code in (decision.get("reason_codes") or [])
            if str(code or "").strip()
        }
        no_candidate_hold = bool(reason_codes & NO_CANDIDATE_REASON_CODES)
        candidate_preservation_expected = (
            decision.get("candidate_preserved") is True
            or ("serialized_public_identity_scrubbed" in reason_codes and not no_candidate_hold)
        )
        candidate_preservation_sources = [
            pre_gate_candidate,
            ledger_candidate_preservation,
            {
                "official_title": identity.get("blocked_official_title"),
                "official_url": identity.get("blocked_official_title_url"),
            },
            {
                "official_title": ledger.get("blocked_official_title"),
                "official_url": ledger.get("blocked_official_title_url"),
            },
        ]
        candidate_preserved_payload_present = any(
            _has_candidate_payload(source) for source in candidate_preservation_sources
        )
        if (
            "serialized_public_identity_scrubbed" in reason_codes
            and not no_candidate_hold
            and decision.get("candidate_preserved") is not True
        ):
            _append_violation(
                violations,
                "scrubbed_decision_not_candidate_preserved",
                "serialized_public_identity_scrubbed decision with a candidate must mark candidate_preserved=true",
            )
        if candidate_preservation_expected and not candidate_preserved_payload_present:
            _append_violation(
                violations,
                "blocked_candidate_preservation_missing",
                "blocked/scrubbed decision does not preserve the candidate in trace, ledger, or blocked title fields",
            )
        if (
            isinstance(trace, dict)
            and isinstance(publish_ledger, dict)
            and _has_candidate_payload(pre_gate_candidate)
            and _has_candidate_payload(ledger_candidate_preservation)
            and _candidate_title_url(pre_gate_candidate) != _candidate_title_url(ledger_candidate_preservation)
        ):
            _append_violation(
                violations,
                "candidate_preservation_trace_ledger_mismatch",
                "publish_ledger.candidate_preservation differs from publish_contract_trace.pre_gate_candidate",
            )
        if _string_or_none(post_gate.get("official_title")):
            _append_violation(violations, "blocked_trace_publishes_title", "blocked trace still publishes title")
        if _string_or_none(post_gate.get("official_url")):
            _append_violation(violations, "blocked_trace_publishes_url", "blocked trace still publishes url")
        if _string_or_none(public_publish.get("official_title")):
            _append_violation(violations, "blocked_ledger_publishes_title", "blocked publish ledger still publishes title")
        if _string_or_none(public_publish.get("official_url")):
            _append_violation(violations, "blocked_ledger_publishes_url", "blocked publish ledger still publishes url")
        if public_identity["official_title"]:
            _append_violation(
                violations,
                "blocked_serialized_public_title_leak",
                "blocked decision still has serialized public official_title",
            )
        if public_identity["official_url"]:
            _append_violation(
                violations,
                "blocked_serialized_public_url_leak",
                "blocked decision still has serialized public official_url",
            )

    return {
        "index": index,
        "post_id": post_id,
        "gate": "NO-GO" if violations else "GO",
        "public_identity": public_identity,
        "decision": {
            "status": status,
            "publish_allowed": publish_allowed,
            "official_title": expected_title,
            "official_url": expected_url,
        },
        "violations": violations,
    }


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_reports = [audit_row(row, index=index) for index, row in enumerate(rows, start=1)]
    violations = [item for item in row_reports if item["violations"]]
    counts = Counter(
        violation["code"]
        for item in row_reports
        for violation in item["violations"]
    )
    return {
        "report_type": "publication_contract_convergence_audit",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "gate": "GO" if not violations else "NO-GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "policy": {
            "promotion_decision_trace_ledger_serialized_identity_must_converge": True,
            "blocked_decision_must_not_publish_serialized_public_identity": True,
            "allowed_decision_must_match_serialized_public_identity": True,
            "scrubbed_candidate_must_be_preserved_or_marked_no_candidate": True,
        },
        "summary": {
            "row_count": len(row_reports),
            "violation_row_count": len(violations),
            "violation_counts": dict(counts.most_common()),
        },
        "violations": violations[:100],
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Publication contract convergence 감사",
        "",
        f"- gate: `{report['gate']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        "- 정책: `PromotionDecision`, `publish_contract_trace`, `publish_ledger`, serialized public identity는 같은 publish/block 결론으로 수렴해야 한다.",
        "- 정책: `serialized_public_identity_scrubbed`는 후보가 있으면 candidate ledger/trace에 보존하고, 후보가 없으면 `hold_without_candidates` 같은 no-candidate reason을 남겨야 한다.",
        "",
        "## 요약",
        "",
        f"- row_count: `{report['summary']['row_count']}`",
        f"- violation_row_count: `{report['summary']['violation_row_count']}`",
        f"- violation_counts: `{report['summary']['violation_counts']}`",
        "",
    ]
    if report["violations"]:
        lines.extend(["## 위반 샘플", ""])
        for item in report["violations"][:20]:
            lines.extend(
                [
                    f"### row {item['index']} post_id `{item['post_id']}`",
                    "",
                    f"- public_identity: `{item['public_identity']}`",
                    f"- decision: `{item.get('decision')}`",
                    "- violations:",
                ]
            )
            for violation in item["violations"]:
                lines.append(f"  - `{violation['code']}`: {violation['detail']}")
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit publication contract convergence in result rows.")
    parser.add_argument("--result", required=True, type=Path, action="append")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = [row for result_path in args.result for row in load_rows(result_path)]
    report = audit_rows(rows)
    report["result_paths"] = [str(path) for path in args.result]
    write_json(args.output_json, report)
    write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_no_go and report["gate"] != "GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
