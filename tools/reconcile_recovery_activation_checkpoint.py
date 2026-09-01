#!/usr/bin/env python3
from __future__ import annotations

"""검증된 publication checkpoint에서 review-only recovery sidecar를 재구성한다.

입력 checkpoint/result/WAL은 수정하지 않는다. 각 canonical result와 receipt를
재검증한 뒤 explicit direct OCR HOLD 후보만 별도 append-only journal에 기록한다.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.llm_batch.ledger.publication_commit import (  # noqa: E402
    PublicationDecisionCommit,
    validate_publication_result_commit,
)
from src.llm_batch.ledger.recovery_activation import (  # noqa: E402
    RECOVERY_ACTIVATION_LEDGER_SCHEMA,
    RecoveryActivationError,
    RecoveryActivationRegistry,
    derive_review_recovery_capability,
    extract_direct_ocr_review_proposals,
    load_or_create_recovery_activation_hmac_key,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _title_key(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _read_checkpoint(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                raise ValueError(f"blank checkpoint line: {path}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"checkpoint row is not an object: {path}:{line_number}")
            rows.append(value)
    return rows


def _read_frozen_ledger(
    path: Path,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    ordered_post_ids: list[str] = []
    by_post: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                raise ValueError(f"blank frozen ledger line: {path}:{line_number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"frozen ledger row is not an object: {path}:{line_number}")
            post_id = str(row.get("post_id") or "").strip()
            if not post_id:
                raise ValueError(f"frozen ledger post_id missing: {path}:{line_number}")
            if post_id in by_post:
                raise ValueError(f"duplicate frozen ledger post_id: {post_id}")
            independent = row.get("independent_semantic_verdict")
            independent = independent if isinstance(independent, Mapping) else {}
            by_post[post_id] = {
                "post_id": post_id,
                "review_verdict": independent.get("review_verdict"),
                "dashboard_action": independent.get("dashboard_action"),
                "recommended_title": independent.get("recommended_title"),
                "severity": row.get("severity") or independent.get("severity"),
                "issue_codes": list(row.get("issue_codes") or []),
            }
            ordered_post_ids.append(post_id)
    return ordered_post_ids, by_post


def _source_label(path: Path) -> str:
    return path.name.removesuffix(".jsonl")


def reconcile_source(
    checkpoint_path: Path,
    *,
    output_dir: Path,
    selected_post_ids: Optional[set[str]] = None,
    adjudication_by_post: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    input_sha_before = _sha256_file(checkpoint_path)
    rows = _read_checkpoint(checkpoint_path)
    if not rows:
        raise ValueError(f"empty checkpoint: {checkpoint_path}")
    source_row_count = len(rows)
    if selected_post_ids is not None:
        available = {str(row.get("post_id") or "").strip() for row in rows}
        missing = sorted(selected_post_ids - available)
        if missing:
            raise ValueError(
                "checkpoint is missing selected post_ids: "
                f"count={len(missing)} sample={missing[:10]}"
            )
        rows = [
            row
            for row in rows
            if str(row.get("post_id") or "").strip() in selected_post_ids
        ]
    receipts: list[PublicationDecisionCommit] = []
    seen_post_ids: set[int | str] = set()
    seen_indices: set[int] = set()
    for row_number, row in enumerate(rows, 1):
        receipt = PublicationDecisionCommit.from_dict(row.get("publication_commit"))
        result = row.get("result")
        if not isinstance(result, Mapping):
            raise ValueError(f"checkpoint result missing: row={row_number}")
        validate_publication_result_commit(
            result,
            receipt,
            expected_scope_id=receipt.publication_scope_id,
            expected_input_index=receipt.input_index,
            expected_post_id=receipt.post_id,
        )
        if receipt.post_id in seen_post_ids:
            raise ValueError(f"duplicate checkpoint post_id: {receipt.post_id}")
        if receipt.input_index in seen_indices:
            raise ValueError(f"duplicate checkpoint input_index: {receipt.input_index}")
        seen_post_ids.add(receipt.post_id)
        seen_indices.add(receipt.input_index)
        receipts.append(receipt)
    scope_ids = {receipt.publication_scope_id for receipt in receipts}
    if len(scope_ids) != 1:
        raise ValueError(f"mixed checkpoint publication scopes: {sorted(scope_ids)}")
    scope_id = next(iter(scope_ids))
    journal_path = output_dir / f"{_source_label(checkpoint_path)}.recovery_activation.jsonl"
    hmac_key = load_or_create_recovery_activation_hmac_key(
        journal_path.with_name(journal_path.name + ".key")
    )
    registry = RecoveryActivationRegistry(
        journal_path,
        publication_scope_id=scope_id,
        hmac_key=hmac_key,
    )

    outcomes = Counter()
    search_statuses = Counter()
    blocker_codes = Counter()
    proposals_observed = 0
    events_created = 0
    events_replayed = 0
    proposal_rows: list[dict[str, Any]] = []
    for row, receipt in sorted(
        zip(rows, receipts),
        key=lambda pair: pair[1].input_index,
    ):
        outcomes[receipt.outcome] += 1
        result = row["result"]
        proposals = extract_direct_ocr_review_proposals(result)
        proposals_observed += len(proposals)
        for proposal in proposals:
            raw_capability = derive_review_recovery_capability(
                receipt,
                proposal,
                hmac_key=hmac_key,
            )
            event, created = registry.ensure_proposal(
                receipt=receipt,
                canonical_result=result,
                proposal=proposal,
                raw_capability=raw_capability,
            )
            events_created += int(created)
            events_replayed += int(not created)
            if event.public_apply is not False:
                raise RecoveryActivationError("review event unexpectedly enables public_apply")
            search_statuses[proposal.search_health or "UNKNOWN"] += 1
            blocker_codes.update(proposal.blocker_codes)
            proposal_rows.append(
                {
                    "source": _source_label(checkpoint_path),
                    "input_index": receipt.input_index,
                    "post_id": receipt.post_id,
                    "outcome": receipt.outcome,
                    "raw_candidate_title": proposal.raw_candidate_title,
                    "title_key": _title_key(proposal.raw_candidate_title),
                    "proposal_id": event.proposal_id,
                    "event_sha256": event.event_sha256,
                    "search_health": proposal.search_health,
                    "conflict_count": proposal.conflict_count,
                    "public_apply": event.public_apply,
                    "review_verdict": (
                        (adjudication_by_post or {}).get(str(receipt.post_id), {}).get(
                            "review_verdict"
                        )
                    ),
                    "dashboard_action": (
                        (adjudication_by_post or {}).get(str(receipt.post_id), {}).get(
                            "dashboard_action"
                        )
                    ),
                    "severity": (
                        (adjudication_by_post or {}).get(str(receipt.post_id), {}).get(
                            "severity"
                        )
                    ),
                }
            )

    input_sha_after = _sha256_file(checkpoint_path)
    source_summary = {
        "source": _source_label(checkpoint_path),
        "checkpoint": str(checkpoint_path.resolve()),
        "checkpoint_sha256_before": input_sha_before,
        "checkpoint_sha256_after": input_sha_after,
        "checkpoint_unchanged": input_sha_before == input_sha_after,
        "checkpoint_source_rows": source_row_count,
        "selection_applied": selected_post_ids is not None,
        "publication_scope_id": scope_id,
        "rows": len(rows),
        "unique_post_ids": len(seen_post_ids),
        "outcomes": dict(sorted(outcomes.items())),
        "proposals_observed": proposals_observed,
        "proposal_post_ids": len({row["post_id"] for row in proposal_rows}),
        "events_created": events_created,
        "events_replayed": events_replayed,
        "event_count": len(registry.events()),
        "provenance_coverage": (
            len(registry.events()) / proposals_observed if proposals_observed else 1.0
        ),
        "search_health": dict(sorted(search_statuses.items())),
        "blocker_codes": dict(sorted(blocker_codes.items())),
        "journal": str(journal_path.resolve()),
        "journal_sha256": _sha256_file(journal_path) if journal_path.exists() else None,
        "public_apply_true": sum(bool(row["public_apply"]) for row in proposal_rows),
    }
    return source_summary, proposal_rows


def build_consensus(
    proposal_rows: Iterable[Mapping[str, Any]],
    *,
    source_count: int,
) -> dict[str, Any]:
    by_post: dict[int | str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in proposal_rows:
        by_post[row["post_id"]].append(row)
    consensus_rows = []
    presence_counts = Counter()
    for post_id, rows in sorted(by_post.items(), key=lambda pair: str(pair[0])):
        sources = sorted({str(row["source"]) for row in rows})
        title_counts = Counter(str(row["raw_candidate_title"]) for row in rows)
        title_key_counts = Counter(str(row["title_key"]) for row in rows)
        presence = len(sources)
        presence_counts[f"{presence}/{source_count}"] += 1
        consensus_rows.append(
            {
                "post_id": post_id,
                "proposal_presence": presence,
                "source_count": source_count,
                "sources": sources,
                "title_counts": dict(sorted(title_counts.items())),
                "normalized_title_counts": dict(sorted(title_key_counts.items())),
                "same_normalized_title_all_present_runs": len(title_key_counts) == 1,
                "public_apply_true": sum(bool(row["public_apply"]) for row in rows),
            }
        )
    return {
        "unique_proposal_post_ids": len(consensus_rows),
        "presence_distribution": dict(sorted(presence_counts.items())),
        "all_present_runs_same_normalized_title": sum(
            row["same_normalized_title_all_present_runs"] for row in consensus_rows
        ),
        "rows": consensus_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="publication checkpoint의 direct OCR review-only sidecar를 재구성한다."
    )
    parser.add_argument(
        "--checkpoint",
        action="append",
        required=True,
        help="검증된 expert_main checkpoint JSONL. 여러 번 지정 가능.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--frozen-ledger",
        help=(
            "선택 post_id와 review verdict를 제공하는 frozen adjudication JSONL. "
            "지정하면 checkpoint를 exact post_id 집합으로 제한한다."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_ledger_path = Path(args.frozen_ledger).resolve() if args.frozen_ledger else None
    if frozen_ledger_path is not None:
        frozen_ordered_post_ids, adjudication_by_post = _read_frozen_ledger(
            frozen_ledger_path
        )
        selected_post_ids = set(frozen_ordered_post_ids)
    else:
        frozen_ordered_post_ids = []
        adjudication_by_post = {}
        selected_post_ids = None
    source_summaries = []
    proposal_rows: list[dict[str, Any]] = []
    errors = []
    for raw_path in args.checkpoint:
        path = Path(raw_path).resolve()
        try:
            source_summary, source_rows = reconcile_source(
                path,
                output_dir=output_dir,
                selected_post_ids=selected_post_ids,
                adjudication_by_post=adjudication_by_post,
            )
            source_summaries.append(source_summary)
            proposal_rows.extend(source_rows)
        except Exception as exc:
            errors.append(
                {
                    "checkpoint": str(path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    consensus = build_consensus(proposal_rows, source_count=len(source_summaries))
    successful_scope_ids = sorted(
        {str(item["publication_scope_id"]) for item in source_summaries}
    )
    scope_compatible = len(successful_scope_ids) <= 1
    adjudication_denominators = Counter(
        str(row.get("review_verdict") or "UNKNOWN")
        for row in adjudication_by_post.values()
    )
    proposal_review_verdicts = Counter(
        str(row.get("review_verdict") or "UNKNOWN") for row in proposal_rows
    )
    proposal_dashboard_actions = Counter(
        str(row.get("dashboard_action") or "UNKNOWN") for row in proposal_rows
    )
    proposal_rates = {
        verdict: {
            "proposal_rows": proposal_review_verdicts.get(verdict, 0),
            "frozen_rows": count,
            "proposal_rate": (
                proposal_review_verdicts.get(verdict, 0) / count if count else 0.0
            ),
        }
        for verdict, count in sorted(adjudication_denominators.items())
    }
    gate = "GO"
    if (
        errors
        or not scope_compatible
        or any(not item["checkpoint_unchanged"] for item in source_summaries)
        or any(item["public_apply_true"] for item in source_summaries)
        or any(item["provenance_coverage"] != 1.0 for item in source_summaries)
    ):
        gate = "NO-GO"
    summary = {
        "schema_version": "recovery_activation_checkpoint_reconciliation_v1",
        "recovery_activation_schema": RECOVERY_ACTIVATION_LEDGER_SCHEMA,
        "purpose": "review_only_recovery_provenance_not_public_apply",
        "gate": gate,
        "network_used": False,
        "expert_main_used": False,
        "public_apply": False,
        "source_count": len(source_summaries),
        "scope_compatibility": {
            "gate": "GO" if scope_compatible else "NO-GO",
            "publication_scope_ids": successful_scope_ids,
            "reason": (
                "single_publication_scope"
                if scope_compatible
                else "mixed_publication_scope_id"
            ),
        },
        "frozen_ledger": (
            {
                "path": str(frozen_ledger_path),
                "sha256": _sha256_file(frozen_ledger_path),
                "rows": len(frozen_ordered_post_ids),
                "unique_post_ids": len(selected_post_ids or ()),
            }
            if frozen_ledger_path is not None
            else None
        ),
        "sources": source_summaries,
        "total_rows": sum(item["rows"] for item in source_summaries),
        "total_proposals_observed": sum(
            item["proposals_observed"] for item in source_summaries
        ),
        "total_events": sum(item["event_count"] for item in source_summaries),
        "consensus": consensus,
        "adjudication_denominators": dict(sorted(adjudication_denominators.items())),
        "proposal_review_verdicts": dict(sorted(proposal_review_verdicts.items())),
        "proposal_dashboard_actions": dict(sorted(proposal_dashboard_actions.items())),
        "proposal_rates_by_review_verdict": proposal_rates,
        "errors": errors,
    }
    summary_path = output_dir / "recovery_activation_reconciliation_summary.json"
    _atomic_write_json(summary_path, summary)
    print(
        json.dumps(
            {
                "gate": gate,
                "summary": str(summary_path),
                "total_proposals": summary["total_proposals_observed"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if gate == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
