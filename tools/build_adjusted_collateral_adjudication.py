from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_publication_contract_convergence import audit_row, row_identity
from tools.bootstrap_regression_safe_grounding import expected_title_matches
from tools.build_adjusted_collateral_blind_packet import (
    PRODUCTION_GOAL_ID,
    PRODUCTION_GOLDEN_ROWS,
    PRODUCTION_PANEL_ROWS,
    canonical_digest,
    expected_blind_material,
    file_sha256,
    packet_row_digest,
    post_id,
    prepare_bound_scope,
    source_payload,
    validate_blind_material,
)
from tools.compare_completed779_improvement import load_json_or_jsonl


ADJUDICATION_CLASSES = {
    "intended_recovery",
    "legitimate_fp_removal",
    "same_work_canonical_change",
    "safe_no_public_terminal",
    "true_semantic_regression",
}
REVIEW_LABELS = {"ACCEPT", "HOLD", "REPROCESS", "REJECT", "INFO_MISSING"}
EVIDENCE_GRADES = {"Strong", "Medium", "Weak", "Missing"}
TERMINAL_LABELS = {
    "HOLD",
    "INFO_MISSING",
    "UNRESOLVED_MATCHABLE",
    "VARIANCE_QUARANTINE",
    "NO_GENERALIZABLE_FIX_LEFT",
}
BLIND_METHODS = {"source_native_blind", "blind_adjudication"}
BLIND_MODEL = "gpt-5.6-sol"
DERIVATION_VERSION = "adjusted-collateral-adjudication-v2"
REPORT_TYPE = "adjusted_full375_collateral_adjudication"
RAW_JUDGE_REPORT_TYPE = "codex_blind_judge_raw_receipt"
RAW_JUDGE_VERSION = "codex-blind-judge-artifact-v3"
RAW_JUDGE_RUNNER_VERSION = "run-codex-blind-adjudication-v3"
RAW_JUDGE_REASONING_EFFORT = "high"
RAW_JUDGE_ZERO_DRIFT_STATUS = "NOT_REQUIRED_ZERO_DRIFT"
CONTINUATION_SOURCE_SESSION = "019f0387-24d0-7313-a6c0-66d09f04bb33"
RAW_JUDGE_TRUST_BOUNDARY = "signed_native_codex_cli_plus_required_live_thread_resume"
THREAD_READBACK_TRUST_BOUNDARY = "signed_native_codex_cli_live_thread_resume"
RECEIPT_DIGEST_CONTRACT = {
    "algorithm": "sha256",
    "canonicalization": "json-sort-keys-compact-utf8",
    "excluded_fields": ["receipt_payload_sha256"],
}
# These are updated only after the standalone production runner and verifier
# finish their focused tests.  Runtime readback is insufficient without a
# compiled consumer pin to those exact reviewed source bytes.
PRODUCTION_RAW_JUDGE_RUNNER_SHA256 = (
    "116cd1cd40d4e44e9d1b9450cce1d659f1a92de1df5fbd26591322d4d0d3f9e2"
)
PRODUCTION_THREAD_READBACK_VERIFIER_SHA256 = (
    "7725d6307f8eb6a278029fead04b76e561d229160cd92615bf0acb84dfc53896"
)
PRODUCTION_CODEX_CLI_TRUST_ANCHOR_PATH = (
    ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/review/loop641_codex_cli_native_trust_anchor_v2.json"
).resolve()
PRODUCTION_CODEX_CLI_TRUST_ANCHOR_SHA256 = (
    "b017035b778fc71b31621306c51cb90114b19d1768253009dc3ba91ea288cfb0"
)
SECURITY_DEPENDENCY_MANIFEST_VERSION = "codex-local-security-dependencies-v1"
PRIMARY_SECURITY_DEPENDENCY_PATHS = (
    "tools/build_adjusted_collateral_adjudication.py",
    "tools/build_adjusted_collateral_blind_packet.py",
    "tools/build_codex_cli_trust_anchor.py",
)
READBACK_SECURITY_DEPENDENCY_PATHS = (
    *PRIMARY_SECURITY_DEPENDENCY_PATHS,
    "tools/run_codex_blind_adjudication.py",
)
PRODUCTION_SECURITY_DEPENDENCY_SHA256 = {
    "tools/build_adjusted_collateral_blind_packet.py": (
        "22ffb968a56c2dc442e299562f01e579b74d48f6b670901ce8c2c8ea80a3d199"
    ),
    "tools/build_codex_cli_trust_anchor.py": (
        "72211eaf7a8d8a9d6c266e9d3bc08dd879a78e573ba32826272f28c658079a02"
    ),
    "tools/run_codex_blind_adjudication.py": PRODUCTION_RAW_JUDGE_RUNNER_SHA256,
}
REVIEWED_PREDECESSOR_SECURITY_DEPENDENCY_SNAPSHOTS = {
    "tools/build_adjusted_collateral_adjudication.py": {
        "sha256": "08bcae3979858c639438673c25910b4e7862f8afd1a989ca91877b2246c50a12",
        "size": 111856,
        "migration_id": "thread-readback-primary-binding-v3-shape",
    },
}
RAW_JUDGE_ALLOWED_EVENT_TYPES = {
    "thread.started",
    "turn.started",
    "item.started",
    "item.updated",
    "item.completed",
    "turn.completed",
}
NO_CANDIDATE_REASON_CODES = {
    "hold_without_candidates",
    "no_candidate_title",
    "missing_candidate_title",
    "no_public_candidate",
}
FORBIDDEN_JUDGE_DERIVED_FIELDS = {
    "terminal_label",
    "source_hash",
    "input_hash",
    "before_after",
    "promotion_decision",
    "publish_contract_trace",
    "test_replay_artifacts",
    "attempted_lanes",
    "missing_or_conflicting_evidence",
    "official_title",
    "official_url",
    "publish_allowed",
    "bypassed_gate",
    "candidate_preserved",
    "candidate_unavailable_reason",
    "publication_violation",
    "unblock_condition",
    "independent_review",
    "validator_contract_recompute",
}
APPROVED_PRESERVED_UNRESOLVED_GOLDEN_STATUSES = {
    "expected_work_evidence_preserved_unresolved",
    "positive_image_boundary_preserved_unresolved",
    "expected_hypothesis_preserved_unresolved",
}


def canonical_digest(value: Any) -> str:
    """Security-root canonical digest, independent of imported dependency code."""
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def file_sha256(path: Path) -> str:
    """Security-root byte hash, independent of imported dependency code."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def _is_read_only_file(path: Path) -> bool:
    if not path.is_file():
        return False
    attributes = getattr(path.stat(), "st_file_attributes", 0)
    readonly_flag = getattr(stat, "FILE_ATTRIBUTE_READONLY", 0x1)
    if attributes:
        return bool(attributes & readonly_flag)
    return not bool(path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _receipt_payload_digest(receipt: dict[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("receipt_payload_sha256", None)
    return canonical_digest(payload)


def _validate_receipt_self_digest(receipt: dict[str, Any], label: str) -> None:
    if receipt.get("receipt_digest_contract") != RECEIPT_DIGEST_CONTRACT:
        raise ValueError(f"{label} receipt digest contract invalid")
    if receipt.get("receipt_payload_sha256") != _receipt_payload_digest(receipt):
        raise ValueError(f"{label} receipt self-digest mismatch")


def _validate_primary_command_vector(
    command: Any,
    *,
    trusted_executable: str,
    schema_path: Path,
) -> tuple[Path, Path]:
    """Validate the only reviewed argv shape for the primary blind judge."""
    if not isinstance(command, list) or len(command) != 19:
        raise ValueError("raw judge Codex command vector length mismatch")
    final_stage = Path(str(command[10]))
    judge_cwd = Path(str(command[17]))
    expected_command = [
        trusted_executable,
        "exec",
        "-m",
        BLIND_MODEL,
        "-c",
        f'model_reasoning_effort="{RAW_JUDGE_REASONING_EFFORT}"',
        "--json",
        "--output-schema",
        str(schema_path),
        "-o",
        str(final_stage),
        "--sandbox",
        "read-only",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-C",
        str(judge_cwd),
        "-",
    ]
    if command != expected_command:
        raise ValueError("raw judge Codex command is not the exact reviewed vector")
    return final_stage, judge_cwd


def _validate_readback_command_vector(
    command: Any,
    *,
    trusted_executable: str,
    schema_path: Path,
    thread_id: str,
    readback_cwd: Path,
) -> Path:
    """Validate the only reviewed argv shape for the live-thread readback."""
    if not isinstance(command, list) or len(command) != 19:
        raise ValueError("thread readback command vector length mismatch")
    final_stage = Path(str(command[13]))
    expected_command = [
        trusted_executable,
        "exec",
        "--sandbox",
        "read-only",
        "resume",
        "-c",
        f'model_reasoning_effort="{RAW_JUDGE_REASONING_EFFORT}"',
        "-m",
        BLIND_MODEL,
        "--json",
        "--output-schema",
        str(schema_path),
        "-o",
        str(final_stage),
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        thread_id,
        "-",
    ]
    if (
        command != expected_command
        or not final_stage.is_absolute()
        or final_stage.name != "final.json"
        or final_stage.parent != readback_cwd.parent
    ):
        raise ValueError("thread readback command is not the exact reviewed vector")
    return final_stage


def _validate_security_dependency_manifest(
    *,
    manifest: Any,
    expected_relative_paths: tuple[str, ...],
    label: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not isinstance(manifest, dict) or set(manifest) != {
        "manifest_version",
        "dependencies",
        "aggregate_sha256_before",
        "aggregate_sha256_after",
        "stable_during_execution",
    }:
        raise ValueError(f"{label} local security dependency manifest schema invalid")
    dependencies = manifest.get("dependencies")
    expected_paths = tuple(sorted(set(expected_relative_paths)))
    if (
        manifest.get("manifest_version") != SECURITY_DEPENDENCY_MANIFEST_VERSION
        or manifest.get("stable_during_execution") is not True
        or not isinstance(dependencies, list)
        or len(dependencies) != len(expected_paths)
    ):
        raise ValueError(f"{label} local security dependency manifest invalid")
    by_path: dict[str, dict[str, Any]] = {}
    observed_snapshot: list[dict[str, Any]] = []
    migration_rows: list[dict[str, Any]] = []
    for expected_relative, record in zip(expected_paths, dependencies):
        if not isinstance(record, dict) or set(record) != {
            "relative_path",
            "absolute_path",
            "size_before",
            "size_after",
            "sha256_before",
            "sha256_after",
            "stable_during_execution",
        }:
            raise ValueError(f"{label} security dependency record schema invalid")
        relative = str(record.get("relative_path") or "").replace("\\", "/")
        source_path = ROOT / relative
        resolved = source_path.resolve()
        if (
            relative != expected_relative
            or source_path.is_symlink()
            or not resolved.is_file()
            or (resolved != ROOT and ROOT not in resolved.parents)
            or Path(str(record.get("absolute_path") or "")).resolve() != resolved
        ):
            raise ValueError(f"{label} security dependency path mismatch: {expected_relative}")
        current_hash = file_sha256(resolved)
        current_size = resolved.stat().st_size
        observed_size = record.get("size_before")
        observed_hash = record.get("sha256_before")
        if (
            record.get("stable_during_execution") is not True
            or isinstance(observed_size, bool)
            or not isinstance(observed_size, int)
            or observed_size < 0
            or not _is_sha256(observed_hash)
            or record.get("size_after") != observed_size
            or record.get("sha256_after") != observed_hash
        ):
            raise ValueError(f"{label} security dependency bytes changed: {relative}")
        current_bytes_match = observed_size == current_size and observed_hash == current_hash
        predecessor = REVIEWED_PREDECESSOR_SECURITY_DEPENDENCY_SNAPSHOTS.get(relative)
        predecessor_match = (
            isinstance(predecessor, dict)
            and observed_size == predecessor.get("size")
            and observed_hash == predecessor.get("sha256")
        )
        if not current_bytes_match and not predecessor_match:
            raise ValueError(f"{label} security dependency bytes changed: {relative}")
        if predecessor_match and not current_bytes_match:
            migration_rows.append(
                {
                    "relative_path": relative,
                    "receipt_observed_sha256": observed_hash,
                    "receipt_observed_size": observed_size,
                    "current_sha256": current_hash,
                    "current_size": current_size,
                    "migration_id": predecessor["migration_id"],
                }
            )
        reviewed_pin = PRODUCTION_SECURITY_DEPENDENCY_SHA256.get(relative)
        if reviewed_pin is not None and observed_hash != reviewed_pin:
            raise ValueError(f"{label} security dependency reviewed pin mismatch: {relative}")
        by_path[relative] = record
        observed_snapshot.append(
            {
                "relative_path": relative,
                "absolute_path": str(resolved),
                "size": observed_size,
                "sha256": observed_hash,
            }
        )
    aggregate = canonical_digest(observed_snapshot)
    if (
        manifest.get("aggregate_sha256_before") != aggregate
        or manifest.get("aggregate_sha256_after") != aggregate
    ):
        raise ValueError(f"{label} security dependency aggregate mismatch")
    consumer_path = (
        ROOT / "tools/build_adjusted_collateral_adjudication.py"
    ).resolve()
    current_consumer_artifact = {
        "path": str(consumer_path),
        "sha256": file_sha256(consumer_path),
        "size": consumer_path.stat().st_size,
        "read_only": _is_read_only_file(consumer_path),
    }
    return by_path, {
        "validation_mode": (
            "reviewed_predecessor_snapshot_migration"
            if migration_rows
            else "current_source_snapshot"
        ),
        "receipt_observed_aggregate_sha256": aggregate,
        "current_consumer_artifact": current_consumer_artifact,
        "migration_rows": migration_rows,
    }


def _require_exact_primary_binding(actual: Any, expected: dict[str, Any]) -> None:
    if not isinstance(actual, dict) or actual != expected:
        raise ValueError("thread readback primary binding mismatch")


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value)


def _public_identity(row: dict[str, Any]) -> dict[str, Any]:
    identity = row_identity(row)
    novel = identity.get("novel_identity") if isinstance(identity.get("novel_identity"), dict) else {}

    def first(*values: Any) -> str | None:
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return None

    return {
        "official_title": first(
            novel.get("official_title"),
            novel.get("official_novel_title"),
            novel.get("resolved_title"),
            identity.get("official_title"),
            identity.get("official_novel_title"),
            identity.get("resolved_title"),
        ),
        "official_url": first(
            novel.get("heretic_url"),
            novel.get("official_url"),
            novel.get("resolved_url"),
            identity.get("heretic_url"),
            identity.get("official_url"),
            identity.get("resolved_url"),
        ),
    }


def _actual_contract(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    identity = row_identity(row)
    decision = identity.get("promotion_decision")
    trace = identity.get("publish_contract_trace")
    return (
        decision if isinstance(decision, dict) else {},
        trace if isinstance(trace, dict) else {},
    )


def blind_receipt_payload(blind: dict[str, Any]) -> dict[str, Any]:
    return {
        key: blind.get(key)
        for key in (
            "review_id",
            "reviewer_id",
            "method",
            "provider",
            "judge_model",
            "judge_run_id",
            "codex_thread_id",
            "goal_id",
            "reviewed_at",
            "prompt_sha256",
            "delivered_packet_sha256",
            "packet_row_sha256",
            "blind_to_baseline_preference",
            "preferred_option",
            "same_work",
            "relation_to_post",
        )
    }


def blind_receipt_digest(blind: dict[str, Any]) -> str:
    return canonical_digest(blind_receipt_payload(blind))


def build_verdict_template(blind_packet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for packet in blind_packet_rows:
        templates.append(
            {
                "drift_id": packet.get("drift_id"),
                "post_id": packet.get("post_id"),
                "packet_row_sha256": packet.get("packet_row_sha256"),
                "classification": None,
                "review_label": None,
                "evidence_grade": None,
                "row_rationale": None,
                "evidence_refs": [],
                "blind_verdict": {
                    "review_id": None,
                    "reviewer_id": None,
                    "method": "source_native_blind",
                    "provider": "codex",
                    "judge_model": BLIND_MODEL,
                    "judge_run_id": None,
                    "codex_thread_id": None,
                    "goal_id": None,
                    "reviewed_at": None,
                    "prompt_sha256": None,
                    "delivered_packet_sha256": packet.get("packet_row_sha256"),
                    "packet_row_sha256": packet.get("packet_row_sha256"),
                    "blind_to_baseline_preference": True,
                    "preferred_option": None,
                    "same_work": None,
                    "relation_to_post": None,
                    "receipt_sha256": None,
                },
            }
        )
    return templates


def _index_by_drift_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        did = str(row.get("drift_id") or "").strip()
        if not did:
            raise ValueError(f"{label} missing drift_id")
        if did in index:
            raise ValueError(f"{label} duplicate drift_id: {did}")
        index[did] = row
    return index


def _recompute_golden_semantic_rows(
    *,
    after_rows: list[dict[str, Any]],
    golden_manifest: Any,
) -> dict[str, dict[str, Any]]:
    from tools.audit_regression_safe_golden import build_audit

    golden_rows = (
        golden_manifest.get("rows")
        if isinstance(golden_manifest, dict)
        else golden_manifest
    )
    if not isinstance(golden_rows, list):
        raise ValueError("golden rows missing for adjudication semantic recompute")
    # build_audit's per-row semantic decision is independent of its full375
    # runtime gate.  Existing source files are supplied only because the audit
    # receipt also records byte hashes; this helper consumes only `rows`.
    audit = build_audit(
        canary_rows=after_rows,
        golden_rows=golden_rows,
        run_manifest={
            "input_post_count": len(after_rows),
            "completed_count": len(after_rows),
            "flushed_count": len(after_rows),
            "pending_count": 0,
            "failed_count": 0,
            "large_run_complete": True,
        },
        canary_result=Path(__file__),
        canary_manifest=Path(__file__),
        golden_manifest=Path(__file__),
    )
    rows = audit.get("rows") if isinstance(audit.get("rows"), list) else []
    return {post_id(row.get("post_id")): row for row in rows if isinstance(row, dict)}


def _derive_blind_classification(
    blind: dict[str, Any],
    drift: dict[str, Any],
    map_row: dict[str, Any],
) -> tuple[str | None, list[str]]:
    preferred = str(blind.get("preferred_option") or "").strip().upper()
    if preferred not in {"A", "B", "EQUIVALENT", "NEITHER", "INSUFFICIENT"}:
        return None, ["blind_preferred_option_invalid_or_missing"]
    origins = map_row.get("option_origins") if isinstance(map_row.get("option_origins"), dict) else {}
    preferred_origin = origins.get(preferred) if preferred in {"A", "B"} else preferred.lower()
    same_work = blind.get("same_work")
    before = drift.get("before_identity") if isinstance(drift.get("before_identity"), dict) else {}
    after = drift.get("after_identity") if isinstance(drift.get("after_identity"), dict) else {}
    before_title = before.get("official_title")
    after_title = after.get("official_title")
    before_url = before.get("official_url") or before.get("heretic_url")
    after_url = after.get("official_url") or after.get("heretic_url")

    if preferred_origin == "before":
        return "true_semantic_regression", []
    if preferred_origin == "after":
        if after_title in (None, "") and before_title not in (None, ""):
            return "legitimate_fp_removal", []
        if after_title not in (None, "") and before_title in (None, ""):
            return "intended_recovery", []
        if after_title not in (None, "") and before_title not in (None, ""):
            return ("same_work_canonical_change" if same_work is True else "intended_recovery"), []
        if same_work is True and before_url != after_url:
            return "same_work_canonical_change", []
        return None, ["after_preference_has_no_deterministic_class"]
    if preferred_origin == "equivalent":
        if same_work is True:
            return "same_work_canonical_change", []
        return None, ["equivalent_preference_requires_same_work_true"]
    if preferred_origin in {"neither", "insufficient"}:
        if after_title not in (None, "") or after_url not in (None, ""):
            return "true_semantic_regression", []
        return "safe_no_public_terminal", []
    return None, ["preferred_option_origin_unresolved"]


def _review_confined_path(path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to((ROOT / "out").resolve())
    except ValueError as exc:
        raise ValueError(f"{label} is outside repository out") from exc
    if "review" not in {part.casefold() for part in relative.parent.parts}:
        raise ValueError(f"{label} is not review-confined")
    return resolved


def _validate_session_bundle(
    *,
    receipt: dict[str, Any],
    artifact_path: Path,
    thread_id: str,
) -> dict[str, Any]:
    session = receipt.get("session_bundle")
    if not isinstance(session, dict):
        raise ValueError("raw judge persisted session bundle receipt missing")
    required_fields = {
        "report_type",
        "version",
        "thread_id",
        "file_count",
        "total_uncompressed_bytes",
        "files",
        "files_sha256",
        "secrets_excluded",
        "bundle_sha256",
        "bundle_size",
        "path",
    }
    if set(session) != required_fields:
        raise ValueError("raw judge persisted session bundle schema mismatch")
    if (
        session.get("report_type") != "codex_blind_judge_session_bundle_manifest"
        or session.get("version") != "codex-blind-session-bundle-v1"
        or session.get("thread_id") != thread_id
        or session.get("secrets_excluded") is not True
        or Path(str(session.get("path") or "")).resolve() != artifact_path
        or file_sha256(artifact_path) != session.get("bundle_sha256")
        or artifact_path.stat().st_size != session.get("bundle_size")
        or not _is_read_only_file(artifact_path)
    ):
        raise ValueError("raw judge persisted session bundle identity mismatch")
    files = session.get("files")
    if not isinstance(files, list) or not files or any(not isinstance(row, dict) for row in files):
        raise ValueError("raw judge persisted session bundle file manifest invalid")
    if (
        session.get("file_count") != len(files)
        or session.get("files_sha256") != canonical_digest(files)
        or session.get("total_uncompressed_bytes")
        != sum(int(row.get("size") or -1) for row in files)
    ):
        raise ValueError("raw judge persisted session bundle counts/digest mismatch")
    expected_by_name: dict[str, dict[str, Any]] = {}
    for row in files:
        name = str(row.get("path") or "")
        pure = PurePosixPath(name)
        if (
            not name
            or pure.is_absolute()
            or ".." in pure.parts
            or not pure.parts
            or pure.parts[0] != "sessions"
            or any(":" in part or "\\" in part for part in pure.parts)
            or name in expected_by_name
            or any(
                marker in name.casefold()
                for marker in ("auth", "token", "credential", "secret")
            )
            or not _is_sha256(row.get("sha256"))
            or isinstance(row.get("size"), bool)
            or not isinstance(row.get("size"), int)
            or row.get("size") < 0
        ):
            raise ValueError("raw judge persisted session bundle member manifest invalid")
        expected_by_name[name] = row
    with zipfile.ZipFile(artifact_path) as archive:
        archive_names = archive.namelist()
        if (
            len(archive_names) != len(set(archive_names))
            or set(archive_names) != set(expected_by_name) | {"session_manifest.json"}
        ):
            raise ValueError("raw judge persisted session bundle member set mismatch")
        internal_manifest = json.loads(
            archive.read("session_manifest.json").decode("utf-8-sig")
        )
        manifest_projection = {
            key: session[key]
            for key in (
                "report_type",
                "version",
                "thread_id",
                "file_count",
                "total_uncompressed_bytes",
                "files",
                "files_sha256",
                "secrets_excluded",
            )
        }
        if internal_manifest != manifest_projection:
            raise ValueError("raw judge persisted session bundle internal manifest mismatch")
        for name, row in expected_by_name.items():
            member_mode = archive.getinfo(name).external_attr >> 16
            if stat.S_ISLNK(member_mode) or archive.getinfo(name).is_dir():
                raise ValueError("raw judge persisted session bundle special member forbidden")
            payload = archive.read(name)
            if len(payload) != row["size"] or hashlib.sha256(payload).hexdigest() != row[
                "sha256"
            ]:
                raise ValueError("raw judge persisted session bundle member hash mismatch")
    return session


def _validate_thread_readback_receipt(
    *,
    trust_bundle_paths: dict[str, Any],
    primary_receipt: dict[str, Any],
    primary_receipt_path: Path,
    current_cli_trust: dict[str, Any],
    trusted_executable: str,
    thread_id: str,
    primary_security_dependencies: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from tools.verify_codex_blind_judge_thread import (
        RECEIPT_VERSION,
        REPORT_TYPE,
        TRUST_BOUNDARY,
        VERIFIER_VERSION,
        build_readback_prompt,
        build_readback_schema,
    )
    from tools.run_codex_blind_adjudication import _parse_raw_events

    readback_path = _review_confined_path(
        Path(str(trust_bundle_paths.get("thread_readback_receipt") or "")),
        "thread readback receipt",
    )
    if not readback_path.is_file() or not _is_read_only_file(readback_path):
        raise ValueError("thread readback receipt is missing or writable")
    receipt = json.loads(readback_path.read_text(encoding="utf-8-sig"))
    if not isinstance(receipt, dict):
        raise ValueError("thread readback receipt must be an object")
    if (
        receipt.get("report_type") != REPORT_TYPE
        or receipt.get("receipt_version") != RECEIPT_VERSION
        or receipt.get("verifier_version") != VERIFIER_VERSION
        or RECEIPT_VERSION != "codex-blind-thread-readback-v3"
        or VERIFIER_VERSION != "verify-codex-blind-judge-thread-v3"
        or receipt.get("gate") != "GO"
        or receipt.get("status") != "SUCCEEDED"
        or receipt.get("execution_mode") != "subprocess_production"
        or receipt.get("provider") != "codex"
        or receipt.get("model") != BLIND_MODEL
        or receipt.get("reasoning_effort") != RAW_JUDGE_REASONING_EFFORT
        or receipt.get("goal_id") != PRODUCTION_GOAL_ID
        or receipt.get("continuation_source_session") != CONTINUATION_SOURCE_SESSION
        or receipt.get("codex_thread_id") != thread_id
        or receipt.get("exit_code") != 0
        or receipt.get("timed_out") is not False
        or receipt.get("execution_error") is not None
        or receipt.get("validation_issues") != []
        or receipt.get("cryptographic_service_attestation") is not False
        or receipt.get("trust_boundary") != TRUST_BOUNDARY
        or TRUST_BOUNDARY != THREAD_READBACK_TRUST_BOUNDARY
    ):
        raise ValueError("thread readback production receipt contract invalid")
    _validate_receipt_self_digest(receipt, "thread readback")
    if receipt.get("codex_cli_trust") != current_cli_trust:
        raise ValueError("thread readback Codex CLI trust differs from primary/current")

    session = primary_receipt["session_bundle"]
    primary_process = primary_receipt.get("execution_process") or {}
    primary_launcher = primary_receipt.get("launcher_process") or {}
    expected_primary_binding = {
        "primary_receipt_path": str(primary_receipt_path),
        "primary_receipt_sha256": file_sha256(primary_receipt_path),
        "thread_id": thread_id,
        "primary_judge_run_id": primary_receipt.get("judge_run_id"),
        "primary_runner_run_id": primary_receipt.get("runner_run_id"),
        "primary_process_id": primary_process.get("process_id"),
        "primary_parent_process_id": primary_process.get("parent_process_id"),
        "primary_launcher_process_id": primary_launcher.get("pid"),
        "primary_raw_events_sha256": primary_receipt.get("raw_events_jsonl_sha256"),
        "primary_final_response_sha256": primary_receipt.get("final_response_sha256"),
        "primary_verdicts_sha256": primary_receipt.get(
            "delivered_verdicts_jsonl_sha256"
        ),
        "session_bundle_path": session.get("path"),
        "session_bundle_sha256": session.get("bundle_sha256"),
        "session_files_sha256": session.get("files_sha256"),
    }
    _require_exact_primary_binding(
        receipt.get("primary_binding"),
        expected_primary_binding,
    )
    readback_run_id = str(receipt.get("readback_run_id") or "").strip()
    if not readback_run_id or readback_run_id in {
        str(primary_receipt.get("runner_run_id") or ""),
        str(primary_receipt.get("judge_run_id") or ""),
    }:
        raise ValueError("thread readback run id is missing or not independent")
    challenge = str(receipt.get("challenge") or "")
    if (
        not 32 <= len(challenge) <= 256
        or receipt.get("challenge_sha256")
        != hashlib.sha256(challenge.encode("utf-8")).hexdigest()
    ):
        raise ValueError("thread readback challenge binding invalid")

    verifier_path = (ROOT / "tools/verify_codex_blind_judge_thread.py").resolve()
    verifier_artifact = receipt.get("verifier_artifact")
    if (
        not isinstance(verifier_artifact, dict)
        or Path(str(verifier_artifact.get("path") or "")).resolve() != verifier_path
        or verifier_artifact.get("stable_during_execution") is not True
        or verifier_artifact.get("size") != verifier_path.stat().st_size
        or verifier_artifact.get("sha256_before") != file_sha256(verifier_path)
        or verifier_artifact.get("sha256_after") != file_sha256(verifier_path)
        or file_sha256(verifier_path) != PRODUCTION_THREAD_READBACK_VERIFIER_SHA256
    ):
        raise ValueError("thread readback verifier artifact pin/readback mismatch")
    runner_path = (ROOT / "tools/run_codex_blind_adjudication.py").resolve()
    runner_dependency = receipt.get("runner_dependency_artifact")
    primary_runner = primary_receipt.get("runner_artifact")
    if (
        not isinstance(runner_dependency, dict)
        or Path(str(runner_dependency.get("path") or "")).resolve() != runner_path
        or runner_dependency.get("stable_during_execution") is not True
        or runner_dependency.get("size") != runner_path.stat().st_size
        or runner_dependency.get("sha256_before") != file_sha256(runner_path)
        or runner_dependency.get("sha256_after") != file_sha256(runner_path)
        or file_sha256(runner_path) != PRODUCTION_RAW_JUDGE_RUNNER_SHA256
        or not isinstance(primary_runner, dict)
        or primary_runner.get("path") != str(runner_path)
        or primary_runner.get("size") != runner_dependency.get("size")
        or primary_runner.get("sha256_before")
        != runner_dependency.get("sha256_before")
        or primary_runner.get("sha256_after")
        != runner_dependency.get("sha256_after")
        or primary_runner.get("stable_during_execution") is not True
    ):
        raise ValueError("thread readback runner dependency pin/readback mismatch")
    (
        readback_security_dependencies,
        readback_security_dependency_provenance,
    ) = _validate_security_dependency_manifest(
        manifest=receipt.get("security_dependency_manifest"),
        expected_relative_paths=READBACK_SECURITY_DEPENDENCY_PATHS,
        label="thread readback",
    )
    for relative in PRIMARY_SECURITY_DEPENDENCY_PATHS:
        if readback_security_dependencies.get(relative) != primary_security_dependencies.get(
            relative
        ):
            raise ValueError(
                f"thread readback/primary security dependency mismatch: {relative}"
            )
    runner_security_record = readback_security_dependencies[
        "tools/run_codex_blind_adjudication.py"
    ]
    if (
        runner_security_record.get("size_before") != runner_dependency.get("size")
        or runner_security_record.get("sha256_before")
        != runner_dependency.get("sha256_before")
        or runner_security_record.get("sha256_after")
        != runner_dependency.get("sha256_after")
    ):
        raise ValueError("thread readback runner dependency manifest cross-binding mismatch")
    launcher = receipt.get("launcher_process")
    execution = receipt.get("execution_process")
    if (
        not isinstance(launcher, dict)
        or launcher.get("execution_boundary") != "isolated_python_cli_child"
        or launcher.get("isolated_python") is not True
        or launcher.get("verifier_path") != str(verifier_path)
        or launcher.get("verifier_sha256") != PRODUCTION_THREAD_READBACK_VERIFIER_SHA256
        or launcher.get("cryptographic_local_process_attestation") is not False
        or not isinstance(launcher.get("pid"), int)
        or not isinstance(execution, dict)
        or not isinstance(execution.get("process_id"), int)
        or execution.get("process_id") == primary_process.get("process_id")
        or execution.get("parent_process_id") != launcher.get("pid")
        or execution.get("process_image_path") != trusted_executable
    ):
        raise ValueError("thread readback independent process evidence invalid")
    command = receipt.get("command")
    isolation = receipt.get("environment_isolation")
    readback_cwd = Path(str((isolation or {}).get("judge_cwd") or ""))
    _validate_readback_command_vector(
        command,
        trusted_executable=trusted_executable,
        schema_path=Path(str((receipt.get("artifacts") or {}).get("schema") or "")),
        thread_id=thread_id,
        readback_cwd=readback_cwd,
    )
    if execution.get("command_sha256") != canonical_digest(command):
        raise ValueError("thread readback execution process command binding mismatch")
    direct_policy = isolation.get("direct_service_policy") if isinstance(isolation, dict) else None
    relation = isolation.get("relation_contract") if isinstance(isolation, dict) else None
    inherited = {
        str(key).casefold()
        for key in (isolation or {}).get("inherited_environment_keys", [])
    }
    required_isolated_environment_keys = {
        "codex_home",
        "home",
        "userprofile",
        "appdata",
        "localappdata",
        "temp",
        "tmp",
    }
    allowed_isolated_environment_keys = required_isolated_environment_keys | {
        "systemroot",
        "windir",
        "comspec",
    }
    forbidden = {
        "path",
        "https_proxy",
        "http_proxy",
        "all_proxy",
        "no_proxy",
        "ssl_cert_file",
        "ssl_cert_dir",
        "openai_base_url",
        "openai_api_key",
        "codex_api_key",
        "openai_org_id",
        "openai_project_id",
        "pythonhome",
        "pythonpath",
        "pythonstartup",
    }
    if (
        not isinstance(isolation, dict)
        or not readback_cwd.is_absolute()
        or readback_cwd.name != "readback-cwd"
        or isolation.get("path_inherited") is not False
        or isolation.get("global_codex_config_inherited") is not False
        or isolation.get("global_agents_inherited") is not False
        or isolation.get("authentication_source") != "isolated_auth_json_copy"
        or not required_isolated_environment_keys.issubset(inherited)
        or not inherited.issubset(allowed_isolated_environment_keys)
        or bool(inherited & forbidden)
        or not isinstance(direct_policy, dict)
        or any(
            direct_policy.get(field) is not False
            for field in (
                "custom_endpoint_inherited",
                "proxy_inherited",
                "custom_ca_inherited",
                "python_environment_inherited",
                "auth_json_network_override_inherited",
            )
        )
        or direct_policy.get("auth_json_schema_allowlist_valid") is not True
        or not isinstance(relation, dict)
        or any(value is not True for value in relation.values())
    ):
        raise ValueError("thread readback environment isolation invalid")
    restore = receipt.get("session_restore")
    if restore != {
        "restored_file_count": session.get("file_count"),
        "restored_files_sha256": session.get("files_sha256"),
        "secrets_restored": False,
    }:
        raise ValueError("thread readback session restore binding mismatch")

    artifacts = receipt.get("artifacts")
    required_artifacts = {
        "prompt",
        "schema",
        "raw_events",
        "final_response",
        "stderr",
        "receipt",
    }
    if not isinstance(artifacts, dict) or set(artifacts) != required_artifacts:
        raise ValueError("thread readback artifact set incomplete")
    artifact_paths = {
        key: _review_confined_path(Path(str(artifacts[key])), f"thread readback {key}")
        for key in required_artifacts
    }
    if artifact_paths["receipt"] != readback_path or any(
        not path.is_file() or not _is_read_only_file(path)
        for path in artifact_paths.values()
    ):
        raise ValueError("thread readback artifact set is missing or writable")
    expected_echo = {
        "thread_id": thread_id,
        "challenge": challenge,
        "primary_receipt_sha256": expected_primary_binding["primary_receipt_sha256"],
        "primary_raw_events_sha256": expected_primary_binding[
            "primary_raw_events_sha256"
        ],
        "primary_final_response_sha256": expected_primary_binding[
            "primary_final_response_sha256"
        ],
        "primary_verdicts_sha256": expected_primary_binding["primary_verdicts_sha256"],
    }
    if (
        artifact_paths["prompt"].read_bytes() != build_readback_prompt(expected_echo)
        or json.loads(artifact_paths["schema"].read_text(encoding="utf-8-sig"))
        != build_readback_schema()
        or file_sha256(artifact_paths["prompt"]) != receipt.get("prompt_sha256")
        or file_sha256(artifact_paths["schema"]) != receipt.get("schema_sha256")
        or file_sha256(artifact_paths["raw_events"])
        != receipt.get("raw_events_jsonl_sha256")
        or file_sha256(artifact_paths["final_response"])
        != receipt.get("final_response_sha256")
    ):
        raise ValueError("thread readback artifact content/hash binding mismatch")
    final_payload = json.loads(
        artifact_paths["final_response"].read_text(encoding="utf-8-sig")
    )
    raw_events, raw_issues, raw_thread, raw_final = _parse_raw_events(
        artifact_paths["raw_events"]
    )
    if (
        raw_issues
        or raw_thread != thread_id
        or raw_final != expected_echo
        or final_payload != expected_echo
        or receipt.get("raw_event_count") != len(raw_events)
        or receipt.get("final_response_payload_sha256")
        != canonical_digest(final_payload)
    ):
        raise ValueError("thread readback live challenge response mismatch")
    write_contract = receipt.get("artifact_write_contract")
    if (
        not isinstance(write_contract, dict)
        or any(
            write_contract.get(field) is not True
            for field in (
                "exclusive_create_no_overwrite",
                "read_only_after_create",
                "output_prefix_confined_to_repo_out_review",
            )
        )
    ):
        raise ValueError("thread readback immutable artifact contract invalid")
    return {
        "gate": "GO",
        "report_type": REPORT_TYPE,
        "receipt_version": RECEIPT_VERSION,
        "path": str(readback_path),
        "sha256": file_sha256(readback_path),
        "receipt_payload_sha256": receipt.get("receipt_payload_sha256"),
        "codex_thread_id": thread_id,
        "readback_run_id": readback_run_id,
        "trust_boundary": TRUST_BOUNDARY,
        "cryptographic_service_attestation_present": False,
        "security_dependency_aggregate_sha256": receipt[
            "security_dependency_manifest"
        ]["aggregate_sha256_after"],
        "security_dependency_validation": readback_security_dependency_provenance,
    }


def validate_raw_codex_judge_artifact(
    *,
    trust_bundle: dict[str, Any],
    blind_packet_rows: list[dict[str, Any]],
    verdict_rows: list[dict[str, Any]],
    _require_thread_readback: bool = True,
    _codex_cli_trust_anchor: Path | None = None,
    _return_primary_preflight: bool = False,
) -> dict[str, Any]:
    paths = trust_bundle.get("artifact_paths") if isinstance(trust_bundle, dict) else None
    anchors = trust_bundle.get("anchors") if isinstance(trust_bundle, dict) else None
    if not isinstance(paths, dict) or not isinstance(anchors, dict):
        raise ValueError("raw judge trust bundle paths/anchors missing")
    raw_path = Path(str(paths.get("raw_judge_receipt") or "")).resolve()
    if not raw_path.is_file():
        raise ValueError("raw Codex judge receipt artifact missing")
    receipt = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    if not isinstance(receipt, dict) or receipt.get("report_type") != RAW_JUDGE_REPORT_TYPE:
        raise ValueError("raw Codex judge receipt report_type invalid")
    if receipt.get("receipt_version") != RAW_JUDGE_VERSION:
        raise ValueError("raw Codex judge receipt version invalid")
    _validate_receipt_self_digest(receipt, "raw Codex judge")
    if not blind_packet_rows and not verdict_rows:
        try:
            zero_receipt_relative = raw_path.relative_to((ROOT / "out").resolve())
        except ValueError as exc:
            raise ValueError("zero-drift judge receipt is outside repository out") from exc
        if (
            "review" not in {part.casefold() for part in zero_receipt_relative.parent.parts}
            or not _is_read_only_file(raw_path)
        ):
            raise ValueError("zero-drift judge receipt is not immutable/review-confined")
        zero_drift_expected = {
            "gate": "NOT_REQUIRED",
            "status": RAW_JUDGE_ZERO_DRIFT_STATUS,
            "provider": "codex",
            "model": BLIND_MODEL,
            "goal_id": PRODUCTION_GOAL_ID,
            "continuation_source_session": CONTINUATION_SOURCE_SESSION,
            "packet_rows_sha256": canonical_digest([]),
            "delivered_verdict_rows_sha256": canonical_digest([]),
            "row_count": 0,
            "rows": [],
            "validation_issues": [],
        }
        if any(receipt.get(field) != expected for field, expected in zero_drift_expected.items()):
            raise ValueError("zero-drift raw judge not-required receipt invalid")
        return {
            "gate": RAW_JUDGE_ZERO_DRIFT_STATUS,
            "report_type": RAW_JUDGE_REPORT_TYPE,
            "receipt_version": RAW_JUDGE_VERSION,
            "raw_judge_receipt_path": str(raw_path),
            "raw_judge_receipt_sha256": file_sha256(raw_path),
            "packet_rows_sha256": canonical_digest([]),
            "delivered_verdict_rows_sha256": canonical_digest([]),
            "row_count": 0,
            "provider": "codex",
            "model": BLIND_MODEL,
            "goal_id": PRODUCTION_GOAL_ID,
        }
    if not blind_packet_rows or not verdict_rows:
        raise ValueError("nonzero blind judge packet/verdict coverage mismatch")
    if receipt.get("runner_version") != RAW_JUDGE_RUNNER_VERSION:
        raise ValueError("raw Codex judge runner version invalid")
    if receipt.get("provider") != "codex" or receipt.get("model") != BLIND_MODEL:
        raise ValueError("raw judge provider/model mismatch")
    if (
        receipt.get("gate") != "GO"
        or receipt.get("status") != "SUCCEEDED"
        or receipt.get("execution_mode") != "subprocess_production"
        or receipt.get("exit_code") != 0
        or receipt.get("timed_out") is not False
        or receipt.get("execution_error") is not None
        or receipt.get("reasoning_effort") != RAW_JUDGE_REASONING_EFFORT
        or receipt.get("continuation_source_session") != CONTINUATION_SOURCE_SESSION
        or receipt.get("validation_issues") != []
        or receipt.get("cryptographic_service_attestation") is not False
        or receipt.get("trust_boundary") != RAW_JUDGE_TRUST_BOUNDARY
        or receipt.get("thread_readback_required") is not True
    ):
        raise ValueError("raw Codex judge execution receipt is not successful")

    from tools.build_codex_cli_trust_anchor import (
        EXPECTED_CLI_VERSION,
        EXPECTED_CODEX_EXE_SHA256,
        EXPECTED_MODEL_SLUG,
        EXPECTED_REASONING_EFFORT,
        EXPECTED_SIGNER_SUBJECT,
        EXPECTED_SIGNER_THUMBPRINT,
        PRODUCTION_EXECUTION_MODE,
        validate_trust_anchor,
    )

    trust_receipt = receipt.get("codex_cli_trust")
    if not isinstance(trust_receipt, dict):
        raise ValueError("raw judge native Codex trust receipt missing")
    anchor_path = Path(str(trust_receipt.get("anchor_path") or "")).resolve()
    try:
        anchor_relative = anchor_path.relative_to((ROOT / "out").resolve())
    except ValueError as exc:
        raise ValueError("raw judge Codex trust anchor is outside repository out") from exc
    if "review" not in {part.casefold() for part in anchor_relative.parent.parts}:
        raise ValueError("raw judge Codex trust anchor is not review-confined")
    if not _is_read_only_file(anchor_path):
        raise ValueError("raw judge Codex trust anchor is not read-only")
    supplied_anchor_path = (
        Path(_codex_cli_trust_anchor).resolve()
        if _codex_cli_trust_anchor is not None
        else PRODUCTION_CODEX_CLI_TRUST_ANCHOR_PATH
    )
    if supplied_anchor_path != PRODUCTION_CODEX_CLI_TRUST_ANCHOR_PATH:
        raise ValueError("raw judge supplied Codex trust anchor is not the compiled pin")
    if (
        anchor_path != supplied_anchor_path
        or file_sha256(anchor_path) != PRODUCTION_CODEX_CLI_TRUST_ANCHOR_SHA256
    ):
        raise ValueError("raw judge Codex trust anchor v2 compiled pin mismatch")
    current_cli_trust = validate_trust_anchor(anchor_path, production=True)
    if current_cli_trust != trust_receipt:
        raise ValueError("raw judge Codex trust receipt/current native CLI mismatch")
    cli_evidence = trust_receipt.get("codex_cli")
    authenticode = (
        cli_evidence.get("authenticode") if isinstance(cli_evidence, dict) else None
    )
    if (
        trust_receipt.get("gate") != "GO"
        or trust_receipt.get("execution_mode") != PRODUCTION_EXECUTION_MODE
        or not isinstance(cli_evidence, dict)
        or cli_evidence.get("executable_sha256") != EXPECTED_CODEX_EXE_SHA256
        or cli_evidence.get("cli_version") != EXPECTED_CLI_VERSION
        or not isinstance(authenticode, dict)
        or authenticode.get("status") != "Valid"
        or authenticode.get("signer_subject") != EXPECTED_SIGNER_SUBJECT
        or str(authenticode.get("signer_thumbprint") or "").upper()
        != EXPECTED_SIGNER_THUMBPRINT
        or (cli_evidence.get("model_capability") or {}).get("slug")
        != EXPECTED_MODEL_SLUG
        or EXPECTED_REASONING_EFFORT
        not in (cli_evidence.get("model_capability") or {}).get(
            "supported_reasoning_efforts", []
        )
    ):
        raise ValueError("raw judge pinned native Codex identity/capability mismatch")
    runner_artifact = receipt.get("runner_artifact")
    expected_runner_path = (ROOT / "tools/run_codex_blind_adjudication.py").resolve()
    if not isinstance(runner_artifact, dict):
        raise ValueError("raw judge runner artifact receipt missing")
    if (
        Path(str(runner_artifact.get("path") or "")).resolve() != expected_runner_path
        or runner_artifact.get("stable_during_execution") is not True
        or runner_artifact.get("size") != expected_runner_path.stat().st_size
        or runner_artifact.get("sha256_before") != file_sha256(expected_runner_path)
        or runner_artifact.get("sha256_after") != file_sha256(expected_runner_path)
        or file_sha256(expected_runner_path) != PRODUCTION_RAW_JUDGE_RUNNER_SHA256
    ):
        raise ValueError("raw judge runner artifact readback mismatch")
    (
        primary_security_dependencies,
        primary_security_dependency_provenance,
    ) = _validate_security_dependency_manifest(
        manifest=receipt.get("security_dependency_manifest"),
        expected_relative_paths=PRIMARY_SECURITY_DEPENDENCY_PATHS,
        label="raw judge",
    )
    launcher = receipt.get("launcher_process")
    execution_process = receipt.get("execution_process")
    if (
        not isinstance(launcher, dict)
        or launcher.get("execution_boundary") != "isolated_python_cli_child"
        or launcher.get("isolated_python") is not True
        or launcher.get("runner_path") != str(expected_runner_path)
        or launcher.get("runner_sha256") != PRODUCTION_RAW_JUDGE_RUNNER_SHA256
        or launcher.get("imported_production_entrypoint") is not False
        or launcher.get("cryptographic_local_process_attestation") is not False
        or not isinstance(launcher.get("pid"), int)
        or not isinstance(execution_process, dict)
        or not isinstance(execution_process.get("process_id"), int)
        or execution_process.get("parent_process_id") != launcher.get("pid")
        or execution_process.get("process_image_path")
        != str(cli_evidence.get("executable_path") or "")
    ):
        raise ValueError("raw judge launcher/execution process evidence invalid")
    write_contract = receipt.get("artifact_write_contract")
    if not isinstance(write_contract, dict) or any(
        write_contract.get(field) is not True
        for field in (
            "exclusive_create_no_overwrite",
            "read_only_after_create",
            "output_prefix_confined_to_repo_out_review",
            "retry_requires_new_output_prefix",
            "verdict_is_final_commit_marker",
        )
    ):
        raise ValueError("raw judge immutable artifact write contract invalid")
    isolation = receipt.get("environment_isolation")
    direct_policy = isolation.get("direct_service_policy") if isinstance(isolation, dict) else None
    relation_contract = isolation.get("relation_contract") if isinstance(isolation, dict) else None
    if (
        not isinstance(isolation, dict)
        or isolation.get("path_inherited") is not False
        or isolation.get("global_codex_config_inherited") is not False
        or isolation.get("global_agents_inherited") is not False
        or isolation.get("authentication_source") != "isolated_auth_json_copy"
        or not isinstance(direct_policy, dict)
        or any(
            direct_policy.get(field) is not False
            for field in (
                "custom_endpoint_inherited",
                "proxy_inherited",
                "custom_ca_inherited",
                "python_environment_inherited",
                "auth_json_network_override_inherited",
            )
        )
        or direct_policy.get("auth_json_schema_allowlist_valid") is not True
        or not isinstance(relation_contract, dict)
        or relation_contract.get("judge_cwd_parent_equals_isolated_home_parent")
        is not True
        or relation_contract.get("codex_home_parent_equals_isolated_home") is not True
    ):
        raise ValueError("raw judge environment isolation invalid")
    expected_thread_id = str(receipt.get("codex_thread_id") or "").strip()
    expected_goal_id = PRODUCTION_GOAL_ID
    uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    if not re.fullmatch(uuid_pattern, expected_thread_id, re.IGNORECASE):
        raise ValueError("trusted Codex thread id invalid")
    if not re.fullmatch(uuid_pattern, expected_goal_id, re.IGNORECASE):
        raise ValueError("trusted goal id invalid")
    if receipt.get("codex_thread_id") != expected_thread_id or receipt.get("goal_id") != expected_goal_id:
        raise ValueError("raw judge thread/goal id mismatch")
    if not str(receipt.get("judge_run_id") or "").strip():
        raise ValueError("raw judge run id missing")
    if not _is_sha256(receipt.get("prompt_sha256")):
        raise ValueError("raw judge prompt sha256 invalid")

    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    required_artifacts = {
        "prompt",
        "schema",
        "raw_events",
        "final_response",
        "stderr",
        "session_bundle",
        "receipt",
        "verdicts",
    }
    if set(artifacts) != required_artifacts:
        raise ValueError("raw judge artifact path set incomplete")
    receipt_artifact_paths = {
        key: Path(str(artifacts[key])).resolve() for key in required_artifacts
    }
    for key, artifact_path in receipt_artifact_paths.items():
        try:
            artifact_relative = artifact_path.relative_to((ROOT / "out").resolve())
        except ValueError as exc:
            raise ValueError(f"raw judge artifact outside repository out: {key}") from exc
        if "review" not in {part.casefold() for part in artifact_relative.parent.parts}:
            raise ValueError(f"raw judge artifact is not review-confined: {key}")
    if receipt_artifact_paths["receipt"] != raw_path:
        raise ValueError("raw judge receipt self path mismatch")
    missing_artifacts = sorted(
        key for key, path in receipt_artifact_paths.items() if not path.is_file()
    )
    if missing_artifacts:
        raise ValueError(f"raw judge artifacts missing: {missing_artifacts}")
    if any(not _is_read_only_file(path) for path in receipt_artifact_paths.values()):
        raise ValueError("raw judge artifact set is not read-only")
    session_bundle = _validate_session_bundle(
        receipt=receipt,
        artifact_path=receipt_artifact_paths["session_bundle"],
        thread_id=expected_thread_id,
    )
    packet_path = Path(str(receipt.get("packet_jsonl_path") or "")).resolve()
    trusted_packet_path = Path(str(paths.get("blind_packet_jsonl") or "")).resolve()
    verdict_path = receipt_artifact_paths["verdicts"]
    trusted_verdict_path = Path(str(paths.get("verdicts_jsonl") or "")).resolve()
    if packet_path != trusted_packet_path or verdict_path != trusted_verdict_path:
        raise ValueError("raw judge packet/verdict artifact path mismatch")
    if not packet_path.is_file() or not verdict_path.is_file():
        raise ValueError("raw judge packet/verdict artifact missing")
    if not _is_read_only_file(packet_path):
        raise ValueError("raw judge delivered packet is not read-only")
    artifact_hash_expectations = {
        "prompt": receipt.get("prompt_sha256"),
        "schema": receipt.get("schema_sha256"),
        "raw_events": receipt.get("raw_events_jsonl_sha256"),
        "final_response": receipt.get("final_response_sha256"),
        "verdicts": receipt.get("delivered_verdicts_jsonl_sha256"),
    }
    for key, expected_hash in artifact_hash_expectations.items():
        if not _is_sha256(expected_hash) or file_sha256(receipt_artifact_paths[key]) != expected_hash:
            raise ValueError(f"raw judge artifact byte hash mismatch: {key}")
    stderr_receipt = receipt.get("stderr")
    if (
        not isinstance(stderr_receipt, dict)
        or stderr_receipt.get("raw_content_retained") is not False
        or Path(str(stderr_receipt.get("retained_redacted_path") or "")).resolve()
        != receipt_artifact_paths["stderr"]
        or stderr_receipt.get("retained_redacted_sha256")
        != file_sha256(receipt_artifact_paths["stderr"])
    ):
        raise ValueError("raw judge stderr redaction artifact binding mismatch")
    if (
        file_sha256(packet_path) != receipt.get("packet_jsonl_sha256")
        or _load_jsonl(verdict_path) != verdict_rows
    ):
        raise ValueError("raw judge delivered packet/verdict bytes mismatch")

    # Rebuild the exact source-only prompt/schema independently from the immutable
    # packet.  The runner imports this module, so keep this import local to avoid
    # a module-import cycle.
    from tools.run_codex_blind_adjudication import (
        _parse_raw_events,
        _validate_model_response,
        build_output_schema,
        build_prompt,
    )

    if receipt_artifact_paths["prompt"].read_bytes() != build_prompt(blind_packet_rows):
        raise ValueError("raw judge prompt is not the deterministic source-only prompt")
    schema_payload = json.loads(receipt_artifact_paths["schema"].read_text(encoding="utf-8-sig"))
    if schema_payload != build_output_schema(len(blind_packet_rows)):
        raise ValueError("raw judge output schema mismatch")
    command = receipt.get("command")
    trusted_executable = str(cli_evidence.get("executable_path") or "")
    final_stage, judge_cwd = _validate_primary_command_vector(
        command,
        trusted_executable=trusted_executable,
        schema_path=receipt_artifact_paths["schema"],
    )
    isolated_home = Path(str(isolation.get("home") or ""))
    isolated_codex_home = Path(str(isolation.get("codex_home") or ""))
    inherited_environment_keys = {
        str(key).casefold() for key in isolation.get("inherited_environment_keys", [])
    }
    required_isolated_environment_keys = {
        "codex_home",
        "home",
        "userprofile",
        "appdata",
        "localappdata",
        "temp",
        "tmp",
    }
    allowed_isolated_environment_keys = required_isolated_environment_keys | {
        "systemroot",
        "windir",
        "comspec",
    }
    forbidden_environment_keys = {
        "path",
        "https_proxy",
        "http_proxy",
        "all_proxy",
        "no_proxy",
        "ssl_cert_file",
        "ssl_cert_dir",
        "openai_base_url",
        "openai_api_key",
        "codex_api_key",
        "openai_org_id",
        "openai_project_id",
        "pythonhome",
        "pythonpath",
        "pythonstartup",
    }
    if (
        not judge_cwd.is_absolute()
        or not isolated_home.is_absolute()
        or not isolated_codex_home.is_absolute()
        or judge_cwd.name != "judge-cwd"
        or judge_cwd.parent != isolated_home.parent
        or isolated_codex_home.parent != isolated_home
        or judge_cwd == isolated_home
        or isolated_home in judge_cwd.parents
        or judge_cwd == isolated_codex_home
        or isolated_codex_home in judge_cwd.parents
        or not final_stage.is_absolute()
        or final_stage.name != "final-response.json"
        or final_stage.parent != judge_cwd.parent
        or bool(inherited_environment_keys & forbidden_environment_keys)
        or not required_isolated_environment_keys.issubset(
            inherited_environment_keys
        )
        or not inherited_environment_keys.issubset(
            allowed_isolated_environment_keys
        )
        or isolation.get("authentication_source") != "isolated_auth_json_copy"
    ):
        raise ValueError("raw judge cwd/environment isolation binding invalid")
    if execution_process.get("command_sha256") != canonical_digest(command):
        raise ValueError("raw judge execution process command binding mismatch")

    raw_events = _load_jsonl(receipt_artifact_paths["raw_events"])
    if receipt.get("raw_event_count") != len(raw_events):
        raise ValueError("raw judge raw event count mismatch")
    event_thread_ids = {
        str(event.get("thread_id") or "").strip()
        for event in raw_events
        if event.get("type") == "thread.started"
    }
    if event_thread_ids != {expected_thread_id}:
        raise ValueError("raw judge thread id is not bound to raw events")
    if not any(event.get("type") == "turn.completed" for event in raw_events):
        raise ValueError("raw judge raw events have no completed turn")
    for event in raw_events:
        event_type = str(event.get("type") or "")
        event_type_lower = event_type.lower()
        if event_type not in RAW_JUDGE_ALLOWED_EVENT_TYPES:
            raise ValueError("raw judge raw events contain unknown event type")
        if event_type in {"error", "turn.failed"} or any(
            marker in event_type_lower
            for marker in ("tool", "command", "web_search", "mcp", "file_change")
        ):
            raise ValueError("raw judge raw events violate source-only execution")
        if event_type in {"item.started", "item.completed", "item.updated"}:
            item = event.get("item") if isinstance(event.get("item"), dict) else {}
            if item.get("type") not in {"reasoning", "agent_message"}:
                raise ValueError("raw judge raw events contain tool or unknown item")
    final_payload = json.loads(
        receipt_artifact_paths["final_response"].read_text(encoding="utf-8-sig")
    )
    if receipt.get("final_response_payload_sha256") != canonical_digest(final_payload):
        raise ValueError("raw judge final response payload hash mismatch")
    final_messages = [
        event.get("item", {}).get("text")
        for event in raw_events
        if event.get("type") == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") == "agent_message"
        and isinstance(event["item"].get("text"), str)
    ]
    if not final_messages or json.loads(final_messages[-1]) != final_payload:
        raise ValueError("raw judge final response is not bound to raw event output")
    reparsed_events, raw_event_issues, reparsed_thread_id, reparsed_final = _parse_raw_events(
        receipt_artifact_paths["raw_events"]
    )
    if (
        raw_event_issues
        or reparsed_events != raw_events
        or reparsed_thread_id != expected_thread_id
        or reparsed_final != final_payload
    ):
        raise ValueError("raw judge raw event state-machine validation failed")
    raw_model_rows = receipt.get("raw_model_verdict_rows")
    if (
        not isinstance(raw_model_rows, list)
        or final_payload != {"verdicts": raw_model_rows}
        or receipt.get("raw_model_verdict_rows_sha256") != canonical_digest(raw_model_rows)
        or receipt.get("raw_event_final_payload_sha256") != canonical_digest(final_payload)
    ):
        raise ValueError("raw judge model verdict payload binding mismatch")
    validated_model_rows, model_issues = _validate_model_response(
        final_payload,
        blind_packet_rows,
    )
    if model_issues or validated_model_rows != raw_model_rows:
        raise ValueError("raw judge model verdict schema/semantics invalid")
    if receipt.get("packet_rows_sha256") != canonical_digest(blind_packet_rows):
        raise ValueError("raw judge packet payload hash mismatch")
    if receipt.get("delivered_verdict_rows_sha256") != canonical_digest(verdict_rows):
        raise ValueError("raw judge delivered verdict payload hash mismatch")
    if (
        receipt.get("packet_row_count") != len(blind_packet_rows)
        or receipt.get("packet_id")
        != (blind_packet_rows[0].get("packet_id") if blind_packet_rows else None)
        or receipt.get("packet_row_sha256_by_drift_id")
        != {
            str(row.get("drift_id")): row.get("packet_row_sha256")
            for row in blind_packet_rows
        }
        or receipt.get("delivered_verdict_row_sha256_by_drift_id")
        != {
            str(row.get("drift_id")): canonical_digest(row)
            for row in verdict_rows
        }
    ):
        raise ValueError("raw judge packet/delivered row hash index mismatch")
    raw_rows = receipt.get("rows") if isinstance(receipt.get("rows"), list) else []
    if receipt.get("row_count") != len(verdict_rows) or len(raw_rows) != len(verdict_rows):
        raise ValueError("raw judge receipt row count mismatch")
    packet_by_id = _index_by_drift_id(blind_packet_rows, "raw judge packet")
    verdict_by_id = _index_by_drift_id(verdict_rows, "raw judge delivered verdict")
    raw_by_id = _index_by_drift_id(
        [row for row in raw_rows if isinstance(row, dict)],
        "raw judge receipt",
    )
    if set(raw_by_id) != set(verdict_by_id) or set(packet_by_id) != set(verdict_by_id):
        raise ValueError("raw judge receipt drift union mismatch")
    raw_model_by_id = _index_by_drift_id(
        [row for row in raw_model_rows if isinstance(row, dict)],
        "raw judge model verdict",
    )
    if set(raw_model_by_id) != set(verdict_by_id):
        raise ValueError("raw judge model verdict drift union mismatch")
    for did, verdict in verdict_by_id.items():
        packet = packet_by_id[did]
        raw = raw_by_id[did]
        raw_model = raw_model_by_id[did]
        blind = verdict.get("blind_verdict") if isinstance(verdict.get("blind_verdict"), dict) else {}
        if raw.get("post_id") != verdict.get("post_id"):
            raise ValueError(f"raw judge post_id mismatch: {did}")
        if raw.get("packet_row_sha256") != packet.get("packet_row_sha256"):
            raise ValueError(f"raw judge packet row hash mismatch: {did}")
        verdict_hash = canonical_digest(verdict)
        if raw.get("raw_verdict_row_sha256") != verdict_hash:
            raise ValueError(f"raw judge raw verdict hash mismatch: {did}")
        if raw.get("delivered_verdict_row_sha256") != verdict_hash:
            raise ValueError(f"raw judge delivered verdict hash mismatch: {did}")
        if raw.get("raw_verdict") != verdict:
            raise ValueError(f"raw judge raw/delivered verdict mismatch: {did}")
        if (
            raw.get("raw_model_verdict") != raw_model
            or raw.get("raw_model_verdict_row_sha256") != canonical_digest(raw_model)
        ):
            raise ValueError(f"raw judge model verdict row mismatch: {did}")
        semantic_bindings = {
            "review_label": verdict.get("review_label"),
            "evidence_grade": verdict.get("evidence_grade"),
            "row_rationale": verdict.get("row_rationale"),
            "evidence_refs": verdict.get("evidence_refs"),
            "preferred_option": blind.get("preferred_option"),
            "same_work": blind.get("same_work"),
            "relation_to_post": blind.get("relation_to_post"),
        }
        if any(raw_model.get(field) != expected for field, expected in semantic_bindings.items()):
            raise ValueError(f"raw judge model/delivered semantics mismatch: {did}")
        for field, expected in (
            ("provider", "codex"),
            ("judge_model", BLIND_MODEL),
            ("judge_run_id", receipt.get("judge_run_id")),
            ("codex_thread_id", expected_thread_id),
            ("goal_id", expected_goal_id),
            ("prompt_sha256", receipt.get("prompt_sha256")),
        ):
            if blind.get(field) != expected:
                raise ValueError(f"raw judge delivered provenance mismatch {field}: {did}")
    primary_binding = {
        "thread_id": expected_thread_id,
        "primary_receipt_path": str(raw_path),
        "primary_receipt_sha256": file_sha256(raw_path),
        "primary_judge_run_id": receipt.get("judge_run_id"),
        "primary_runner_run_id": receipt.get("runner_run_id"),
        "primary_process_id": execution_process.get("process_id"),
        "primary_parent_process_id": execution_process.get("parent_process_id"),
        "primary_launcher_process_id": launcher.get("pid"),
        "primary_raw_events_sha256": receipt.get("raw_events_jsonl_sha256"),
        "primary_final_response_sha256": receipt.get("final_response_sha256"),
        "primary_verdicts_sha256": receipt.get(
            "delivered_verdicts_jsonl_sha256"
        ),
        "session_bundle_path": str(receipt_artifact_paths["session_bundle"]),
        "session_bundle_sha256": session_bundle.get("bundle_sha256"),
        "session_files_sha256": session_bundle.get("files_sha256"),
    }
    if _return_primary_preflight:
        if _require_thread_readback:
            raise ValueError("primary preflight cannot require an existing readback")
        return {
            "receipt": receipt,
            "receipt_path": raw_path,
            "receipt_sha256": file_sha256(raw_path),
            "packet_rows": blind_packet_rows,
            "verdict_rows": verdict_rows,
            "thread_id": expected_thread_id,
            "current_cli_trust": current_cli_trust,
            "trust_binding": current_cli_trust,
            "trusted_executable": trusted_executable,
            "primary_security_dependencies": primary_security_dependencies,
            "security_dependency_validation": primary_security_dependency_provenance,
            "session_bundle": session_bundle,
            "artifact_paths": receipt_artifact_paths,
            "binding": primary_binding,
        }
    thread_readback = _validate_thread_readback_receipt(
        trust_bundle_paths=paths,
        primary_receipt=receipt,
        primary_receipt_path=raw_path,
        current_cli_trust=current_cli_trust,
        trusted_executable=trusted_executable,
        thread_id=expected_thread_id,
        primary_security_dependencies=primary_security_dependencies,
    )
    return {
        "gate": "GO",
        "report_type": RAW_JUDGE_REPORT_TYPE,
        "receipt_version": RAW_JUDGE_VERSION,
        "raw_judge_receipt_path": str(raw_path),
        "raw_judge_receipt_sha256": file_sha256(raw_path),
        "packet_rows_sha256": canonical_digest(blind_packet_rows),
        "delivered_verdict_rows_sha256": canonical_digest(verdict_rows),
        "row_count": len(verdict_rows),
        "provider": "codex",
        "model": BLIND_MODEL,
        "reasoning_effort": RAW_JUDGE_REASONING_EFFORT,
        "execution_mode": PRODUCTION_EXECUTION_MODE,
        "codex_cli_trust_anchor_sha256": trust_receipt.get("anchor_file_sha256"),
        "codex_executable_sha256": cli_evidence.get("executable_sha256"),
        "runner_sha256": runner_artifact.get("sha256_after"),
        "cryptographic_service_attestation_present": False,
        "trust_boundary": THREAD_READBACK_TRUST_BOUNDARY,
        "thread_readback": thread_readback,
        "session_bundle_sha256": session_bundle.get("bundle_sha256"),
        "session_files_sha256": session_bundle.get("files_sha256"),
        "security_dependency_aggregate_sha256": receipt[
            "security_dependency_manifest"
        ]["aggregate_sha256_after"],
        "security_dependency_validation": primary_security_dependency_provenance,
        "codex_thread_id": expected_thread_id,
        "goal_id": expected_goal_id,
        "judge_run_id": receipt.get("judge_run_id"),
        "prompt_sha256": receipt.get("prompt_sha256"),
        "schema_sha256": receipt.get("schema_sha256"),
        "raw_events_jsonl_sha256": receipt.get("raw_events_jsonl_sha256"),
        "final_response_sha256": receipt.get("final_response_sha256"),
        "delivered_verdicts_jsonl_sha256": receipt.get(
            "delivered_verdicts_jsonl_sha256"
        ),
    }


def preflight_raw_codex_judge_receipt_for_readback(
    *,
    raw_judge_receipt: Path,
    codex_cli_trust_anchor: Path,
) -> dict[str, Any]:
    """Fully validate an immutable primary receipt before any readback side effect.

    The verifier calls this before it restores a persisted session, writes a
    prompt/schema, or starts Codex.  The returned values are derived only after
    the same consumer-grade primary validation used by adjudication succeeds;
    an existing readback receipt is deliberately neither required nor read.
    """
    raw_path = _review_confined_path(
        Path(raw_judge_receipt),
        "raw judge preflight receipt",
    )
    anchor_path = _review_confined_path(
        Path(codex_cli_trust_anchor),
        "raw judge preflight Codex trust anchor",
    )
    if not raw_path.is_file():
        raise ValueError("raw judge preflight receipt artifact missing")
    receipt = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    if not isinstance(receipt, dict):
        raise ValueError("raw judge preflight receipt must be an object")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("raw judge preflight artifact paths missing")
    packet_path = _review_confined_path(
        Path(str(receipt.get("packet_jsonl_path") or "")),
        "raw judge preflight packet",
    )
    verdict_path = _review_confined_path(
        Path(str(artifacts.get("verdicts") or "")),
        "raw judge preflight verdicts",
    )
    packet_rows = _load_jsonl(packet_path)
    verdict_rows = _load_jsonl(verdict_path)
    if not packet_rows or not verdict_rows:
        raise ValueError("thread readback preflight requires nonzero primary rows")
    return validate_raw_codex_judge_artifact(
        trust_bundle={
            "artifact_paths": {
                "raw_judge_receipt": raw_path,
                "blind_packet_jsonl": packet_path,
                "verdicts_jsonl": verdict_path,
            },
            "anchors": {},
        },
        blind_packet_rows=packet_rows,
        verdict_rows=verdict_rows,
        _require_thread_readback=False,
        _codex_cli_trust_anchor=anchor_path,
        _return_primary_preflight=True,
    )


def _hard_safety_classification(
    *,
    after_row: dict[str, Any],
    golden: dict[str, Any] | None,
    golden_audit_row: dict[str, Any] | None,
) -> tuple[str | None, list[str], dict[str, Any]]:
    audit = audit_row(after_row, index=1)
    issues: list[str] = []
    if audit.get("gate") != "GO":
        issues.extend(
            f"publication_contract:{violation.get('code')}"
            for violation in audit.get("violations") or []
            if isinstance(violation, dict)
        )
    actual = _public_identity(after_row)
    decision, trace = _actual_contract(after_row)
    if not actual["official_title"] and not actual["official_url"]:
        reason_codes = {
            str(code).strip()
            for code in decision.get("reason_codes", [])
            if str(code).strip()
        } if isinstance(decision.get("reason_codes"), list) else set()
        if not decision:
            issues.append("nonpublic_promotion_decision_missing")
        if not trace:
            issues.append("nonpublic_publish_contract_trace_missing")
        if decision and decision.get("publish_allowed") is not False:
            issues.append("nonpublic_publish_allowed_must_be_false")
        if decision and decision.get("bypassed_gate") is not False:
            issues.append("nonpublic_decision_bypassed_gate_must_be_false")
        if trace and trace.get("bypassed_gate") is not False:
            issues.append("nonpublic_trace_bypassed_gate_must_be_false")
        if (
            decision
            and decision.get("candidate_preserved") is not True
            and not (reason_codes & NO_CANDIDATE_REASON_CODES)
        ):
            issues.append("nonpublic_candidate_must_be_preserved_or_no_candidate")
    if golden:
        expected_no_public = golden.get("expected_no_public_title") is True
        expected_title = (
            golden.get("expected_title_or_hypothesis")
            or golden.get("expected_title")
            or golden.get("expected_official_title")
        )
        expected_url = golden.get("expected_url") or golden.get("expected_official_url")
        golden_passed = bool(golden_audit_row and golden_audit_row.get("passed") is True)
        golden_status = str((golden_audit_row or {}).get("status") or "")
        preserved_unresolved = (
            golden_passed
            and golden_status in APPROVED_PRESERVED_UNRESOLVED_GOLDEN_STATUSES
            and not actual["official_title"]
            and not actual["official_url"]
        )
        if not golden_passed:
            if expected_no_public and (actual["official_title"] or actual["official_url"]):
                issues.append("golden_expected_no_public_identity_violation")
            elif expected_title and not expected_title_matches(
                str(expected_title), actual["official_title"]
            ):
                issues.append("golden_expected_title_mismatch")
            else:
                issues.append("golden_expected_answer_mismatch")
        if (
            expected_url
            and str(expected_url).strip() != str(actual["official_url"] or "").strip()
            and not preserved_unresolved
        ):
            issues.append("golden_expected_url_mismatch")
    return ("true_semantic_regression" if issues else None), issues, audit


def _blind_provenance_issues(blind: dict[str, Any], packet_hash: str) -> list[str]:
    issues: list[str] = []
    if str(blind.get("method") or "").strip() not in BLIND_METHODS:
        issues.append("blind_method_invalid_or_missing")
    if str(blind.get("provider") or "").strip() != "codex":
        issues.append("blind_provider_must_be_codex")
    if blind.get("blind_to_baseline_preference") is not True:
        issues.append("blind_to_baseline_preference_must_be_true")
    if blind.get("packet_row_sha256") != packet_hash:
        issues.append("blind_verdict_packet_hash_mismatch")
    if blind.get("delivered_packet_sha256") != packet_hash:
        issues.append("blind_delivered_packet_hash_mismatch")
    if str(blind.get("judge_model") or "").strip() != BLIND_MODEL:
        issues.append("blind_judge_model_must_be_gpt_5_6_sol")
    for field in ("review_id", "reviewer_id", "judge_run_id", "reviewed_at"):
        if not str(blind.get(field) or "").strip():
            issues.append(f"blind_{field}_missing")
    reviewer = str(blind.get("reviewer_id") or "").strip().lower()
    if reviewer in {"builder", "validator", "self", "system", "auto"}:
        issues.append("blind_reviewer_id_invalid")
    if not _is_sha256(blind.get("prompt_sha256")):
        issues.append("blind_prompt_sha256_invalid_or_missing")
    uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    for field in ("codex_thread_id", "goal_id"):
        if not re.fullmatch(uuid_pattern, str(blind.get(field) or ""), re.IGNORECASE):
            issues.append(f"blind_{field}_invalid_or_missing")
    if str(blind.get("relation_to_post") or "") not in {"direct", "indirect", "insufficient"}:
        issues.append("blind_relation_to_post_invalid_or_missing")
    if blind.get("receipt_sha256") != blind_receipt_digest(blind):
        issues.append("blind_receipt_sha256_mismatch")
    return issues


def _terminal_issues(
    *,
    after_row: dict[str, Any],
    golden: dict[str, Any] | None,
    golden_audit_row: dict[str, Any] | None,
    publication_audit: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    if golden and golden.get("expected_no_public_title") is not True:
        if not (
            golden_audit_row
            and golden_audit_row.get("passed") is True
            and golden_audit_row.get("status")
            in APPROVED_PRESERVED_UNRESOLVED_GOLDEN_STATUSES
        ):
            issues.append("golden_positive_loss_cannot_be_terminal")
    actual_public = _public_identity(after_row)
    if actual_public["official_title"] not in (None, ""):
        issues.append("terminal_actual_official_title_must_be_null")
    if actual_public["official_url"] not in (None, ""):
        issues.append("terminal_actual_official_url_must_be_null")
    decision, trace = _actual_contract(after_row)
    if decision.get("publish_allowed") is not False:
        issues.append("terminal_publish_allowed_must_be_false")
    if decision.get("bypassed_gate") is not False or trace.get("bypassed_gate") is not False:
        issues.append("terminal_actual_bypassed_gate_must_be_false")
    reason_codes = {
        str(code).strip()
        for code in decision.get("reason_codes", [])
        if str(code).strip()
    } if isinstance(decision.get("reason_codes"), list) else set()
    if (
        decision.get("candidate_preserved") is not True
        and not (reason_codes & NO_CANDIDATE_REASON_CODES)
    ):
        issues.append("terminal_candidate_must_be_preserved_or_explained")
    if publication_audit.get("gate") != "GO":
        issues.append("terminal_publication_violation_must_be_false")
    return issues


def _derived_terminal_contract(
    *,
    verdict: dict[str, Any],
    drift: dict[str, Any],
    after_row: dict[str, Any],
    source_hash: str,
    input_hash: str,
    publication_audit: dict[str, Any],
    golden_audit_row: dict[str, Any] | None,
) -> dict[str, Any]:
    blind = verdict.get("blind_verdict") if isinstance(verdict.get("blind_verdict"), dict) else {}
    decision, trace = _actual_contract(after_row)
    preferred = str(blind.get("preferred_option") or "").upper()
    terminal_label = "INFO_MISSING" if preferred == "INSUFFICIENT" else "HOLD"
    missing_reason = (
        "blind_judge_insufficient_source_evidence"
        if preferred == "INSUFFICIENT"
        else "blind_judge_rejected_both_candidates"
    )
    reason_codes = decision.get("reason_codes") if isinstance(decision.get("reason_codes"), list) else []
    candidate_unavailable_reason = None
    if decision.get("candidate_preserved") is not True:
        candidate_unavailable_reason = next(
            (str(code) for code in reason_codes if str(code) in NO_CANDIDATE_REASON_CODES),
            None,
        )
    return {
        "terminal_label": terminal_label,
        "source_hash": source_hash,
        "input_hash": input_hash,
        "before_after": {
            "before_identity": drift.get("before_identity"),
            "after_identity": drift.get("after_identity"),
        },
        "blind_verdict": blind,
        "promotion_decision": decision,
        "publish_contract_trace": trace,
        "test_replay_artifacts": [
            f"packet_sha256:{verdict.get('packet_row_sha256')}",
            f"drift_sha256:{canonical_digest(drift)}",
        ],
        "attempted_lanes": ["source_native_blind", "shared_publication_contract_audit"],
        "missing_or_conflicting_evidence": [missing_reason],
        "official_title": _public_identity(after_row)["official_title"],
        "official_url": _public_identity(after_row)["official_url"],
        "publish_allowed": decision.get("publish_allowed"),
        "bypassed_gate": bool(
            decision.get("bypassed_gate") is True or trace.get("bypassed_gate") is True
        ),
        "candidate_preserved": decision.get("candidate_preserved"),
        "candidate_unavailable_reason": candidate_unavailable_reason,
        "publication_violation": publication_audit.get("gate") != "GO",
        "golden_audit_binding": (
            {
                "post_id": golden_audit_row.get("post_id"),
                "passed": golden_audit_row.get("passed"),
                "status": golden_audit_row.get("status"),
            }
            if golden_audit_row
            else None
        ),
        "unblock_condition": "새 direct official/source evidence 확보 후 새 fingerprint로 재판정",
        "validator_contract_recompute": {
            "validator_id": "deterministic-source-bound-contract-validator",
            "semantic_judgment_source": "raw_codex_blind_receipt",
            "recompute_state": "validator_recompute",
            "rationale": "actual after row와 shared publication contract 구조를 재계산했다.",
            "evidence_refs": [
                f"source_sha256:{source_hash}",
                f"after_row_sha256:{canonical_digest(after_row)}",
            ],
            "checks": {
                "no_public_identity": _public_identity(after_row)
                == {"official_title": None, "official_url": None},
                "publish_allowed_false": decision.get("publish_allowed") is False,
                "bypassed_gate_false": (
                    decision.get("bypassed_gate") is False
                    and trace.get("bypassed_gate") is False
                ),
                "candidate_accounted": (
                    decision.get("candidate_preserved") is True
                    or candidate_unavailable_reason is not None
                ),
            },
        },
    }


def _verdict_issues(
    *,
    verdict: dict[str, Any],
    drift: dict[str, Any],
    packet: dict[str, Any],
    map_row: dict[str, Any],
    after_row: dict[str, Any],
    golden: dict[str, Any] | None,
    golden_audit_row: dict[str, Any] | None,
    classification: str | None,
    derivation_issues: list[str],
    publication_audit: dict[str, Any],
) -> list[str]:
    issues = list(derivation_issues)
    if set(verdict) & FORBIDDEN_JUDGE_DERIVED_FIELDS:
        issues.append("judge_supplied_derived_terminal_contract_fields_forbidden")
    packet_hash = str(packet.get("packet_row_sha256") or "")
    if packet_hash != packet_row_digest(packet):
        issues.append("packet_row_sha256_mismatch")
    if verdict.get("drift_id") != drift.get("drift_id"):
        issues.append("verdict_drift_id_mismatch")
    if post_id(verdict.get("post_id")) != post_id(drift.get("post_id")):
        issues.append("verdict_post_id_mismatch")
    if verdict.get("packet_row_sha256") != packet_hash:
        issues.append("packet_row_sha256_mismatch")
    if map_row.get("packet_row_sha256") != packet_hash:
        issues.append("private_map_packet_hash_mismatch")
    if map_row.get("drift_row_sha256") != canonical_digest(drift):
        issues.append("private_map_drift_hash_mismatch")
    supplied = str(verdict.get("classification") or "").strip()
    if classification not in ADJUDICATION_CLASSES:
        issues.append("classification_not_derivable")
    if supplied and supplied != classification:
        issues.append("supplied_classification_mismatch")
    if verdict.get("review_label") not in REVIEW_LABELS:
        issues.append("review_label_invalid_or_missing")
    if verdict.get("evidence_grade") not in EVIDENCE_GRADES:
        issues.append("evidence_grade_invalid_or_missing")
    if not str(verdict.get("row_rationale") or "").strip():
        issues.append("row_rationale_missing")
    if not _nonempty_list(verdict.get("evidence_refs")):
        issues.append("evidence_refs_missing")
    blind = verdict.get("blind_verdict")
    if not isinstance(blind, dict):
        issues.append("blind_verdict_missing")
        blind = {}
    issues.extend(_blind_provenance_issues(blind, packet_hash))
    review_label = verdict.get("review_label")
    evidence_grade = verdict.get("evidence_grade")
    relation = blind.get("relation_to_post")
    accepted_public_or_removal = {
        "intended_recovery",
        "same_work_canonical_change",
        "legitimate_fp_removal",
    }
    if classification in accepted_public_or_removal:
        if review_label != "ACCEPT":
            issues.append("nonterminal_recovery_or_removal_requires_accept")
        if evidence_grade not in {"Strong", "Medium"}:
            issues.append("nonterminal_recovery_or_removal_requires_adequate_evidence")
        if relation != "direct":
            issues.append("nonterminal_recovery_or_removal_requires_direct_relation")
    if (
        review_label in {"HOLD", "INFO_MISSING"}
        or evidence_grade in {"Weak", "Missing"}
        or relation == "insufficient"
    ) and classification not in {"safe_no_public_terminal", "true_semantic_regression"}:
        issues.append("insufficient_evidence_must_be_safe_terminal_or_regression")
    if classification == "safe_no_public_terminal":
        if review_label not in {"HOLD", "INFO_MISSING"}:
            issues.append("safe_terminal_requires_hold_or_info_missing_label")
        issues.extend(
            _terminal_issues(
                after_row=after_row,
                golden=golden,
                golden_audit_row=golden_audit_row,
                publication_audit=publication_audit,
            )
        )
    return issues


def build_adjudication(
    *,
    compare: dict[str, Any],
    verdict_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    golden_manifest: Any,
    blind_packet_rows: list[dict[str, Any]],
    blind_map: dict[str, Any],
    expected_scope_rows: int = PRODUCTION_PANEL_ROWS,
    expected_golden_rows: int = PRODUCTION_GOLDEN_ROWS,
    allow_multi_variant: bool = False,
    trust_bundle: dict[str, Any] | None = None,
    allow_untrusted_test_scope: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    scope = prepare_bound_scope(
        compare=compare,
        baseline_rows=baseline_rows,
        source_rows=source_rows,
        after_rows=after_rows,
        golden_manifest=golden_manifest,
        expected_scope_rows=expected_scope_rows,
        expected_golden_rows=expected_golden_rows,
        allow_multi_variant=allow_multi_variant,
        trust_bundle=trust_bundle,
        allow_untrusted_test_scope=allow_untrusted_test_scope,
    )
    golden_semantic_by_id = _recompute_golden_semantic_rows(
        after_rows=after_rows,
        golden_manifest=golden_manifest,
    )
    ordered_golden_rows = (
        golden_manifest.get("rows")
        if isinstance(golden_manifest, dict)
        else golden_manifest
    )
    if not isinstance(ordered_golden_rows, list):
        raise ValueError("golden rows missing for adjudication diagnostic binding")
    ordered_golden_audit_rows = [
        golden_semantic_by_id[post_id(row.get("post_id"))]
        for row in ordered_golden_rows
    ]
    failed_golden_rows = [
        {
            "post_id": post_id(row.get("post_id")),
            "status": str(row.get("status") or "").strip(),
        }
        for row in ordered_golden_audit_rows
        if row.get("passed") is False
    ]
    derived_golden_diagnostic = {
        "gate": "NO-GO" if failed_golden_rows else "PASS",
        "canary_semantic_gate": "NO-GO" if failed_golden_rows else "PASS",
        "row_count": len(ordered_golden_audit_rows),
        "passed_count": len(ordered_golden_audit_rows) - len(failed_golden_rows),
        "failed_count": len(failed_golden_rows),
        "failed_rows": failed_golden_rows,
        "failed_rows_sha256": canonical_digest(failed_golden_rows),
        "blind_judge_may_override": False,
    }
    authoritative_golden_diagnostic = (
        scope.get("authoritative_trust", {}).get("golden_audit_diagnostic")
        if isinstance(scope.get("authoritative_trust"), dict)
        else None
    )
    if isinstance(authoritative_golden_diagnostic, dict):
        for field, expected in derived_golden_diagnostic.items():
            if authoritative_golden_diagnostic.get(field) != expected:
                raise ValueError(
                    f"authoritative/recomputed golden audit diagnostic mismatch: {field}"
                )
        golden_audit_diagnostic = authoritative_golden_diagnostic
    else:
        golden_audit_diagnostic = {
            **derived_golden_diagnostic,
            "canonical_audit_sha256": None,
        }
    drift_rows = scope["drift_rows"]
    drift_by_id = scope["drift_by_id"]
    packet_by_id = _index_by_drift_id(blind_packet_rows, "blind packet")
    map_rows = blind_map.get("rows") if isinstance(blind_map, dict) else None
    if not isinstance(map_rows, list):
        raise ValueError("blind private map rows must be a list")
    map_by_id = _index_by_drift_id([row for row in map_rows if isinstance(row, dict)], "blind private map")
    material_issues = validate_blind_material(
        scope=scope,
        blind_packet_rows=blind_packet_rows,
        blind_map=blind_map,
    )
    if allow_untrusted_test_scope:
        raw_judge_provenance = {"gate": "UNIT_TEST_UNTRUSTED"}
    else:
        if not isinstance(trust_bundle, dict):
            raise ValueError("authoritative trust bundle is required for raw judge provenance")
        raw_judge_provenance = validate_raw_codex_judge_artifact(
            trust_bundle=trust_bundle,
            blind_packet_rows=blind_packet_rows,
            verdict_rows=verdict_rows,
        )

    verdict_by_id: dict[str, dict[str, Any]] = {}
    duplicate_verdict_ids: list[str] = []
    malformed_verdict_rows = 0
    for verdict in verdict_rows:
        did = str(verdict.get("drift_id") or "").strip()
        if not did:
            malformed_verdict_rows += 1
            continue
        if did in verdict_by_id:
            duplicate_verdict_ids.append(did)
        else:
            verdict_by_id[did] = verdict

    drift_ids = set(drift_by_id)
    verdict_ids = set(verdict_by_id)
    missing_ids = sorted(drift_ids - verdict_ids)
    extra_ids = sorted(verdict_ids - drift_ids)
    classification_counts: Counter[str] = Counter()
    reviewed_rows: list[dict[str, Any]] = []
    invalid_ids: list[str] = []

    for drift in drift_rows:
        did = drift["drift_id"]
        verdict = verdict_by_id.get(did)
        if verdict is None:
            continue
        packet = packet_by_id.get(did)
        map_row = map_by_id.get(did)
        if packet is None or map_row is None:
            invalid_ids.append(did)
            reviewed_rows.append(
                {
                    "drift_id": did,
                    "post_id": drift.get("post_id"),
                    "classification": None,
                    "validation_issues": [
                        "blind_packet_row_missing" if packet is None else "blind_private_map_row_missing"
                    ],
                }
            )
            continue
        pid = post_id(drift.get("post_id"))
        after_row = scope["after_by_drift_id"][did]
        golden = scope["golden_by_id"].get(pid)
        golden_audit_row = golden_semantic_by_id.get(pid)
        blind = verdict.get("blind_verdict") if isinstance(verdict.get("blind_verdict"), dict) else {}
        blind_class, blind_issues = _derive_blind_classification(blind, drift, map_row)
        hard_class, hard_issues, publication_audit = _hard_safety_classification(
            after_row=after_row,
            golden=golden,
            golden_audit_row=golden_audit_row,
        )
        classification = hard_class or blind_class
        derivation_issues = blind_issues
        issues = _verdict_issues(
            verdict=verdict,
            drift=drift,
            packet=packet,
            map_row=map_row,
            after_row=after_row,
            golden=golden,
            golden_audit_row=golden_audit_row,
            classification=classification,
            derivation_issues=derivation_issues,
            publication_audit=publication_audit,
        )
        if issues:
            invalid_ids.append(did)
        else:
            classification_counts[str(classification)] += 1
        reviewed_rows.append(
            {
                "drift_id": did,
                "post_id": drift.get("post_id"),
                "variant_index": drift.get("variant_index"),
                "status": drift.get("status"),
                "classification": classification,
                "supplied_classification": verdict.get("classification"),
                "review_label": verdict.get("review_label"),
                "evidence_grade": verdict.get("evidence_grade"),
                "drift_row_sha256": canonical_digest(drift),
                "source_hash": scope["source_hashes"][pid],
                "input_hash": scope["input_hashes"][pid],
                "packet_row_sha256": verdict.get("packet_row_sha256"),
                "hard_safety_issues": hard_issues,
                "publication_audit": publication_audit,
                "golden_audit_binding": (
                    {
                        "passed": golden_audit_row.get("passed"),
                        "status": golden_audit_row.get("status"),
                    }
                    if golden_audit_row
                    else None
                ),
                "validation_issues": issues,
                "row_rationale": verdict.get("row_rationale"),
                "evidence_refs": verdict.get("evidence_refs"),
                "blind_verdict": verdict.get("blind_verdict"),
                "terminal_contract": (
                    _derived_terminal_contract(
                        verdict=verdict,
                        drift=drift,
                        after_row=after_row,
                        source_hash=scope["source_hashes"][pid],
                        input_hash=scope["input_hashes"][pid],
                        publication_audit=publication_audit,
                        golden_audit_row=golden_audit_row,
                    )
                    if classification == "safe_no_public_terminal"
                    else None
                ),
            }
        )

    invalid_set = set(invalid_ids)
    unreviewed_ids = sorted(set(missing_ids) | invalid_set)
    true_regression_ids = [
        row["drift_id"]
        for row in reviewed_rows
        if not row.get("validation_issues") and row.get("classification") == "true_semantic_regression"
    ]
    validation_issues = list(material_issues)
    if duplicate_verdict_ids:
        validation_issues.append("duplicate_verdict_drift_ids")
    if extra_ids:
        validation_issues.append("extra_verdict_drift_ids")
    if malformed_verdict_rows:
        validation_issues.append("malformed_verdict_rows")
    if set(packet_by_id) != drift_ids:
        validation_issues.append("blind_packet_drift_union_mismatch")
    if set(map_by_id) != drift_ids:
        validation_issues.append("blind_private_map_drift_union_mismatch")

    semantic_gate = (
        "GO"
        if not validation_issues and not unreviewed_ids and not true_regression_ids
        else "NO-GO"
    )
    true_regression_post_ids = sorted(
        {post_id(drift_by_id[did].get("post_id")) for did in true_regression_ids}
    )
    unreviewed_post_ids = sorted(
        {post_id(drift_by_id[did].get("post_id")) for did in unreviewed_ids if did in drift_by_id}
    )
    source_binding = {
        "expected_scope_rows": expected_scope_rows,
        "expected_golden_rows": expected_golden_rows,
        "allow_multi_variant": allow_multi_variant,
        "source_compare_digest": scope["compare_digest"],
        "baseline_digest": scope["baseline_digest"],
        "source_input_digest": scope["source_digest"],
        "after_result_digest": scope["after_digest"],
        "golden_manifest_digest": scope["golden_digest"],
        "blind_packet_digest": canonical_digest(blind_packet_rows),
        "blind_map_digest": canonical_digest(blind_map),
        "verdict_rows_digest": canonical_digest(verdict_rows),
        "post_id_order_digest": canonical_digest(scope["post_id_order"]),
        "authoritative_trust": scope["authoritative_trust"],
        "raw_judge_provenance": raw_judge_provenance,
    }
    essential = {
        "derivation_version": DERIVATION_VERSION,
        "expected_scope_rows": expected_scope_rows,
        "expected_golden_rows": expected_golden_rows,
        "drift_ids": [row["drift_id"] for row in drift_rows],
        "drift_post_ids": [post_id(row.get("post_id")) for row in drift_rows],
        "missing_verdict_drift_ids": missing_ids,
        "extra_verdict_drift_ids": extra_ids,
        "duplicate_verdict_drift_ids": sorted(set(duplicate_verdict_ids)),
        "invalid_verdict_drift_ids": sorted(set(invalid_ids)),
        "unreviewed_adjusted_drift_ids": unreviewed_ids,
        "unreviewed_adjusted_post_ids": unreviewed_post_ids,
        "true_semantic_regression_drift_ids": true_regression_ids,
        "true_semantic_regression_post_ids": true_regression_post_ids,
        "classification_counts": dict(sorted(classification_counts.items())),
        "golden_audit_diagnostic": golden_audit_diagnostic,
        "validation_issues": validation_issues,
        "semantic_gate": semantic_gate,
        "source_binding": source_binding,
        "reviewed_rows": reviewed_rows,
    }
    return {
        "report_type": REPORT_TYPE,
        "derivation_version": DERIVATION_VERSION,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "gate": semantic_gate,
        "adjusted_full375_collateral": semantic_gate,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "baseline_mode": compare.get("baseline_mode"),
        "diagnostic_adjusted_drift_count": len(drift_rows),
        "drift_union_count": len(drift_rows),
        "verdict_row_count": len(verdict_rows),
        "valid_reviewed_row_count": sum(classification_counts.values()),
        "unreviewed_adjusted_rows": len(unreviewed_ids),
        "true_semantic_regression_count": len(true_regression_ids),
        "actionable_unfixed_count": len(true_regression_ids),
        **essential,
        "derivation_digest": canonical_digest(essential),
        "approval_boundary": {
            "gate_is_derived_not_user_supplied": True,
            "source_compare_is_recomputed_from_bound_artifacts": True,
            "diagnostic_adjusted_drift_count_is_not_failure_metric": True,
            "gate_requires_unreviewed_zero": True,
            "gate_requires_true_semantic_regression_zero": True,
            "builder_output_requires_independent_validator": True,
            "semantic_judgment_is_raw_codex_blind_receipt": True,
            "validator_contract_recompute_is_structural_not_independent_semantic_review": True,
            "production_judge_requires_signed_native_cli_local_attestation": True,
            "cryptographic_service_attestation_present": False,
            "production_full_scan_approval": False,
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# 판결 기반 full375 collateral gate",
        "",
        f"- gate: `{report['gate']}`",
        f"- adjusted_full375_collateral: `{report['adjusted_full375_collateral']}`",
        f"- diagnostic_adjusted_drift_count: `{report['diagnostic_adjusted_drift_count']}`",
        f"- drift_union_count: `{report['drift_union_count']}`",
        f"- valid_reviewed_row_count: `{report['valid_reviewed_row_count']}`",
        f"- unreviewed_adjusted_rows: `{report['unreviewed_adjusted_rows']}`",
        f"- true_semantic_regression_count: `{report['true_semantic_regression_count']}`",
        f"- classification_counts: `{report['classification_counts']}`",
        f"- validation_issues: `{report['validation_issues']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        "- compare/count/class는 입력 선언을 승인값으로 쓰지 않고 baseline/source/after/golden에서 재계산한다.",
        "- Builder 결과만으로 승인하지 않으며 독립 validator receipt가 필요하다.",
        "",
        "## 미판결 또는 invalid drift_id",
        "",
        ", ".join(report.get("unreviewed_adjusted_drift_ids") or []) or "없음",
        "",
        "## True semantic regression drift_id",
        "",
        ", ".join(report.get("true_semantic_regression_drift_ids") or []) or "없음",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


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
    parser = argparse.ArgumentParser(description="Build the deterministic source-bound full375 adjudication gate.")
    parser.add_argument("--collateral-compare", type=Path)
    parser.add_argument("--baseline-result", type=Path)
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--source-input", type=Path)
    parser.add_argument("--after-result", type=Path)
    parser.add_argument("--merged-manifest", type=Path)
    parser.add_argument("--merged-checkpoint", type=Path)
    parser.add_argument("--merged-pending", type=Path)
    parser.add_argument("--merge-binding-receipt", type=Path)
    parser.add_argument("--merge-integrity", type=Path)
    parser.add_argument("--runtime-trust-anchor", type=Path)
    parser.add_argument("--golden-manifest", type=Path)
    parser.add_argument("--golden-audit", type=Path)
    parser.add_argument("--raw-judge-receipt", type=Path)
    parser.add_argument("--thread-readback-receipt", type=Path)
    parser.add_argument("--trusted-baseline-manifest-sha256")
    parser.add_argument("--trusted-panel-source-sha256")
    parser.add_argument("--trusted-golden-manifest-sha256")
    parser.add_argument("--blind-packet-jsonl", required=True, type=Path)
    parser.add_argument("--blind-map-json", type=Path)
    parser.add_argument("--verdicts-jsonl", type=Path)
    parser.add_argument("--template-jsonl", type=Path)
    parser.add_argument("--template-only", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--fail-on-no-go", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    blind_packet_rows = _load_jsonl(args.blind_packet_jsonl)
    if args.template_only:
        if args.template_jsonl is None:
            raise SystemExit("--template-only requires --template-jsonl")
        _write_jsonl(args.template_jsonl, build_verdict_template(blind_packet_rows))
        print(f"WROTE {args.template_jsonl} rows={len(blind_packet_rows)}")
        return 0
    required_fields = (
        "collateral_compare",
        "baseline_result",
        "baseline_manifest",
        "source_input",
        "after_result",
        "merged_manifest",
        "merged_checkpoint",
        "merged_pending",
        "merge_binding_receipt",
        "runtime_trust_anchor",
        "golden_manifest",
        "golden_audit",
        "raw_judge_receipt",
        "thread_readback_receipt",
        "trusted_baseline_manifest_sha256",
        "trusted_panel_source_sha256",
        "trusted_golden_manifest_sha256",
        "blind_map_json",
        "verdicts_jsonl",
        "output_json",
        "output_md",
    )
    missing = [field for field in required_fields if getattr(args, field) in (None, "")]
    if missing:
        raise SystemExit(f"normal adjudication mode missing required arguments: {missing}")
    compare = _load_json(args.collateral_compare)
    baseline_rows = load_json_or_jsonl(args.baseline_result)
    source_rows = load_json_or_jsonl(args.source_input)
    after_rows = load_json_or_jsonl(args.after_result)
    golden = _load_json(args.golden_manifest)
    blind_map = _load_json(args.blind_map_json)
    verdict_rows = _load_jsonl(args.verdicts_jsonl)
    trust_bundle = {
        "artifact_paths": {
            "baseline_result": args.baseline_result,
            "baseline_manifest": args.baseline_manifest,
            "source_input": args.source_input,
            "after_result": args.after_result,
            "merged_manifest": args.merged_manifest,
            "merged_checkpoint": args.merged_checkpoint,
            "merged_pending": args.merged_pending,
            "merge_binding_receipt": args.merge_binding_receipt,
            "runtime_trust_anchor": args.runtime_trust_anchor,
            "golden_manifest": args.golden_manifest,
            "golden_audit": args.golden_audit,
            "raw_judge_receipt": args.raw_judge_receipt,
            "thread_readback_receipt": args.thread_readback_receipt,
            "blind_packet_jsonl": args.blind_packet_jsonl,
            "verdicts_jsonl": args.verdicts_jsonl,
            **(
                {"merge_integrity": args.merge_integrity}
                if args.merge_integrity is not None
                else {}
            ),
        },
        "anchors": {
            "baseline_manifest_sha256": args.trusted_baseline_manifest_sha256,
            "panel_source_sha256": args.trusted_panel_source_sha256,
            "golden_manifest_sha256": args.trusted_golden_manifest_sha256,
        },
    }
    if args.template_jsonl:
        _write_jsonl(args.template_jsonl, build_verdict_template(blind_packet_rows))
    report = build_adjudication(
        compare=compare,
        verdict_rows=verdict_rows,
        baseline_rows=baseline_rows,
        source_rows=source_rows,
        after_rows=after_rows,
        golden_manifest=golden,
        blind_packet_rows=blind_packet_rows,
        blind_map=blind_map,
        expected_scope_rows=PRODUCTION_PANEL_ROWS,
        expected_golden_rows=PRODUCTION_GOLDEN_ROWS,
        trust_bundle=trust_bundle,
    )
    report["artifacts"] = {
        "collateral_compare": str(args.collateral_compare),
        "collateral_compare_sha256": file_sha256(args.collateral_compare),
        "baseline_result": str(args.baseline_result),
        "baseline_result_sha256": file_sha256(args.baseline_result),
        "baseline_manifest": str(args.baseline_manifest),
        "baseline_manifest_sha256": file_sha256(args.baseline_manifest),
        "source_input": str(args.source_input),
        "source_input_sha256": file_sha256(args.source_input),
        "after_result": str(args.after_result),
        "after_result_sha256": file_sha256(args.after_result),
        "merged_manifest": str(args.merged_manifest),
        "merged_manifest_sha256": file_sha256(args.merged_manifest),
        "merged_checkpoint": str(args.merged_checkpoint),
        "merged_checkpoint_sha256": file_sha256(args.merged_checkpoint),
        "merged_pending": str(args.merged_pending),
        "merged_pending_sha256": file_sha256(args.merged_pending),
        "merge_binding_receipt": str(args.merge_binding_receipt),
        "merge_binding_receipt_sha256": file_sha256(args.merge_binding_receipt),
        "merge_integrity": str(args.merge_integrity) if args.merge_integrity else None,
        "merge_integrity_sha256": (
            file_sha256(args.merge_integrity) if args.merge_integrity else None
        ),
        "runtime_trust_anchor": str(args.runtime_trust_anchor),
        "runtime_trust_anchor_sha256": file_sha256(args.runtime_trust_anchor),
        "golden_manifest": str(args.golden_manifest),
        "golden_manifest_sha256": file_sha256(args.golden_manifest),
        "golden_audit": str(args.golden_audit),
        "golden_audit_sha256": file_sha256(args.golden_audit),
        "raw_judge_receipt": str(args.raw_judge_receipt),
        "raw_judge_receipt_sha256": file_sha256(args.raw_judge_receipt),
        "thread_readback_receipt": str(args.thread_readback_receipt),
        "thread_readback_receipt_sha256": file_sha256(
            args.thread_readback_receipt
        ),
        "blind_packet_jsonl": str(args.blind_packet_jsonl),
        "blind_packet_jsonl_sha256": file_sha256(args.blind_packet_jsonl),
        "blind_map_json": str(args.blind_map_json),
        "blind_map_json_sha256": file_sha256(args.blind_map_json),
        "verdicts_jsonl": str(args.verdicts_jsonl) if args.verdicts_jsonl else None,
        "verdicts_jsonl_sha256": (
            file_sha256(args.verdicts_jsonl)
            if args.verdicts_jsonl and args.verdicts_jsonl.exists()
            else None
        ),
    }
    _write_json(args.output_json, report)
    write_markdown(args.output_md, report)
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "drift_union_count": report["drift_union_count"],
                "unreviewed_adjusted_rows": report["unreviewed_adjusted_rows"],
                "true_semantic_regression_count": report["true_semantic_regression_count"],
                "validation_issues": report["validation_issues"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2 if args.fail_on_no_go and report["gate"] != "GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
