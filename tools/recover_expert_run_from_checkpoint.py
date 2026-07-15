from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

try:
    from llm_batch.ledger.decision_call_readback import (
        read_decision_call_ledger,
        verify_readback_report_sha256,
    )
except ModuleNotFoundError:
    from src.llm_batch.ledger.decision_call_readback import (
        read_decision_call_ledger,
        verify_readback_report_sha256,
    )

try:
    from llm_batch.ledger.publication_commit import (
        PUBLICATION_COMMIT_SCHEMA,
        PUBLICATION_COMMIT_EVENT_SCHEMA,
        PUBLICATION_COMMIT_JOURNAL_SCHEMA,
        PUBLICATION_TAIL_REPAIR_SCHEMA,
        PublicationCommitError,
        PublicationDecisionCommit,
        PublicationScopeDescriptor,
        validate_publication_result_commit,
    )
except ModuleNotFoundError:
    from src.llm_batch.ledger.publication_commit import (
        PUBLICATION_COMMIT_SCHEMA,
        PUBLICATION_COMMIT_EVENT_SCHEMA,
        PUBLICATION_COMMIT_JOURNAL_SCHEMA,
        PUBLICATION_TAIL_REPAIR_SCHEMA,
        PublicationCommitError,
        PublicationDecisionCommit,
        PublicationScopeDescriptor,
        validate_publication_result_commit,
    )

try:
    from llm_batch.measurement.early_route_measurement import (
        LANE_CHEAP_NIL,
        LANE_FULL,
        EarlyRouteComparisonReceipt,
        EarlyRouteDecision,
        canonical_hash as early_route_canonical_hash,
    )
except ModuleNotFoundError:
    from src.llm_batch.measurement.early_route_measurement import (
        LANE_CHEAP_NIL,
        LANE_FULL,
        EarlyRouteComparisonReceipt,
        EarlyRouteDecision,
        canonical_hash as early_route_canonical_hash,
    )

try:
    from llm_batch.measurement.paired_measurement_readback import build_recovery_witness
except ModuleNotFoundError:
    from src.llm_batch.measurement.paired_measurement_readback import build_recovery_witness


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _iter_jsonl(
    path: Path,
    *,
    source: str,
    annotate_line: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return rows, [{"source": source, "reason": f"JSONL 읽기 실패: {exc}"}]
    if raw and not raw.endswith(b"\n"):
        errors.append(
            {"source": source, "reason": "JSONL 마지막 행이 newline으로 종료되지 않았습니다"}
        )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        errors.append(
            {"source": source, "reason": f"JSONL UTF-8 검증 실패: {exc}"}
        )
        return rows, errors
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                {"source": source, "line": line_no, "reason": f"JSONL JSON 검증 실패: {exc}"}
            )
            continue
        if isinstance(row, dict):
            if annotate_line:
                row["_line_no"] = line_no
            rows.append(row)
        else:
            errors.append(
                {"source": source, "line": line_no, "reason": "JSONL 행이 객체가 아닙니다"}
            )
    return rows, errors


def _iter_committed_wal_frames(
    path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], bytes]:
    """Read only newline-committed WAL frames and retain torn-tail evidence."""
    source = "publication_commit_journal"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return (
            [],
            [{"source": source, "reason": f"WAL 읽기 실패: {exc}"}],
            {
                "uncommitted_tail_present": False,
                "uncommitted_tail_bytes": 0,
                "uncommitted_tail_sha256": None,
                "tail_repair_required": False,
            },
            b"",
        )
    if raw and not raw.endswith(b"\n"):
        committed_size = raw.rfind(b"\n") + 1
        committed_raw = raw[:committed_size]
        uncommitted_tail = raw[committed_size:]
    else:
        committed_raw = raw
        uncommitted_tail = b""
    tail_meta = {
        "uncommitted_tail_present": bool(uncommitted_tail),
        "uncommitted_tail_bytes": len(uncommitted_tail),
        "uncommitted_tail_sha256": (
            hashlib.sha256(uncommitted_tail).hexdigest()
            if uncommitted_tail
            else None
        ),
        "tail_repair_required": bool(uncommitted_tail),
    }
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        text = committed_raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        errors.append(
            {"source": source, "reason": f"committed WAL UTF-8 검증 실패: {exc}"}
        )
        return rows, errors, tail_meta, raw
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(
                {
                    "source": source,
                    "line": line_number,
                    "reason": f"committed WAL JSON 검증 실패: {exc}",
                }
            )
            continue
        if not isinstance(value, dict):
            errors.append(
                {
                    "source": source,
                    "line": line_number,
                    "reason": "committed WAL frame이 객체가 아닙니다",
                }
            )
            continue
        rows.append(value)
    return rows, errors, tail_meta, raw


def _valid_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _validate_tail_repair_history(
    *,
    journal_path: Path | None,
    journal_raw: bytes,
    expected_scope_id: str | None,
    descriptor_sha256: str | None,
) -> dict[str, Any]:
    repair_dir = (
        journal_path.with_name(journal_path.name + ".tail_repairs")
        if journal_path is not None
        else None
    )
    errors: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    if repair_dir is None or not repair_dir.exists():
        empty_ledger_sha256 = hashlib.sha256(b"[]").hexdigest()
        return {
            "status": "NONE",
            "count": 0,
            "path": str(repair_dir) if repair_dir is not None else None,
            "ledger_sha256": empty_ledger_sha256,
            "record_ids": [],
            "errors": errors,
        }
    if not repair_dir.is_dir():
        return {
            "status": "UNSAFE",
            "count": 0,
            "path": str(repair_dir),
            "ledger_sha256": None,
            "record_ids": [],
            "errors": [{"reason": "tail repair 경로가 directory가 아닙니다"}],
        }
    entries = sorted(repair_dir.iterdir(), key=lambda item: item.name)
    for entry in entries:
        if not entry.is_file() or entry.suffix.lower() != ".json":
            errors.append(
                {"path": str(entry), "reason": "tail repair directory에 예상하지 않은 항목이 있습니다"}
            )
            continue
        try:
            raw = entry.read_bytes()
            if not raw.endswith(b"\n"):
                raise ValueError("record가 newline으로 종료되지 않았습니다")
            value = json.loads(raw.decode("utf-8", errors="strict"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(
                {"path": str(entry), "reason": f"tail repair record 검증 실패: {exc}"}
            )
            continue
        expected_fields = {
            "schema_version",
            "repair_id",
            "publication_scope_id",
            "scope_descriptor_sha256",
            "journal_name",
            "original_size_bytes",
            "retained_size_bytes",
            "retained_prefix_sha256",
            "discarded_tail_bytes",
            "discarded_tail_sha256",
            "commit_point_policy",
            "repaired_at_unix_ns",
        }
        if not isinstance(value, dict) or set(value) != expected_fields:
            errors.append(
                {"path": str(entry), "reason": "tail repair record field 집합이 다릅니다"}
            )
            continue
        record_errors: list[str] = []
        for field in (
            "original_size_bytes",
            "retained_size_bytes",
            "discarded_tail_bytes",
            "repaired_at_unix_ns",
        ):
            field_value = value.get(field)
            if (
                isinstance(field_value, bool)
                or not isinstance(field_value, int)
                or field_value < 0
            ):
                record_errors.append(f"{field}가 non-negative integer가 아닙니다")
        if value.get("schema_version") != PUBLICATION_TAIL_REPAIR_SCHEMA:
            record_errors.append("schema_version mismatch")
        if value.get("publication_scope_id") != expected_scope_id:
            record_errors.append("publication_scope_id mismatch")
        if value.get("scope_descriptor_sha256") != descriptor_sha256:
            record_errors.append("scope_descriptor_sha256 mismatch")
        if journal_path is None or value.get("journal_name") != journal_path.name:
            record_errors.append("journal_name mismatch")
        if value.get("commit_point_policy") != "newline_terminated_valid_frame":
            record_errors.append("commit_point_policy mismatch")
        for field in (
            "repair_id",
            "retained_prefix_sha256",
            "discarded_tail_sha256",
        ):
            if not _valid_sha256(value.get(field)):
                record_errors.append(f"{field}가 lowercase sha256가 아닙니다")
        if not record_errors:
            retained = value["retained_size_bytes"]
            discarded = value["discarded_tail_bytes"]
            if value["original_size_bytes"] != retained + discarded:
                record_errors.append("original_size_bytes 합계가 다릅니다")
            if retained > len(journal_raw):
                record_errors.append("retained_size_bytes가 현재 journal보다 큽니다")
            elif hashlib.sha256(journal_raw[:retained]).hexdigest() != value[
                "retained_prefix_sha256"
            ]:
                record_errors.append("현재 journal retained prefix SHA가 다릅니다")
            repair_material = (
                f"{expected_scope_id}:{value['original_size_bytes']}:"
                f"{retained}:{value['retained_prefix_sha256']}:"
                f"{descriptor_sha256}:{value['discarded_tail_sha256']}"
            ).encode("utf-8")
            expected_repair_id = hashlib.sha256(repair_material).hexdigest()
            if value["repair_id"] != expected_repair_id:
                record_errors.append("repair_id 재계산이 다릅니다")
            if entry.stem != value["repair_id"]:
                record_errors.append("repair record filename이 repair_id와 다릅니다")
        if record_errors:
            errors.append(
                {"path": str(entry), "reason": "; ".join(record_errors)}
            )
        else:
            records.append(value)
    ledger_sha256 = hashlib.sha256(
        json.dumps(
            records,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "status": "UNSAFE" if errors else ("VALID" if records else "NONE"),
        "count": len(records),
        "path": str(repair_dir),
        "ledger_sha256": ledger_sha256,
        "record_ids": [record["repair_id"] for record in records],
        "errors": errors,
    }


def _validate_tail_repair_manifest_binding(
    *,
    manifest: dict[str, Any],
    manifest_path: Path | None,
    journal_path: Path | None,
    history: dict[str, Any],
) -> dict[str, Any]:
    count_field = "publication_commit_tail_repair_count"
    ledger_field = "publication_commit_tail_repair_ledger_sha256"
    dir_field = "publication_commit_tail_repair_dir"
    declared = any(field in manifest for field in (count_field, ledger_field, dir_field))
    if not declared:
        return {
            "status": "NOT_PROVABLE",
            "policy": "legacy_manifest_without_repair_snapshot",
            "declared_count": None,
            "actual_count": history["count"],
            "errors": [],
        }
    errors: list[str] = []
    declared_count = _nonnegative_int(manifest.get(count_field))
    declared_ledger_sha = str(manifest.get(ledger_field) or "").strip().lower()
    declared_dir = _artifact_path_from_manifest(manifest.get(dir_field), manifest_path)
    expected_dir = (
        journal_path.with_name(journal_path.name + ".tail_repairs")
        if journal_path is not None
        else None
    )
    if declared_count is None:
        errors.append("declared repair count가 non-negative integer가 아닙니다")
    if not _valid_sha256(declared_ledger_sha):
        errors.append("declared repair ledger SHA가 유효하지 않습니다")
    if (
        declared_dir is None
        or expected_dir is None
        or declared_dir.resolve() != expected_dir.resolve()
    ):
        errors.append("declared repair directory가 scope journal repair directory와 다릅니다")
    actual_count = int(history.get("count") or 0)
    terminal_finalized = manifest.get("terminal_artifacts_finalized") is True
    status = "UNSAFE" if errors else "VALID"
    policy = "terminal_exact_snapshot" if terminal_finalized else "incomplete_lower_bound"
    if not errors:
        if terminal_finalized:
            if declared_count != actual_count:
                errors.append("terminal repair count가 current scope ledger와 다릅니다")
            if declared_ledger_sha != history.get("ledger_sha256"):
                errors.append("terminal repair ledger SHA가 current scope ledger와 다릅니다")
        elif declared_count is not None and declared_count > actual_count:
            errors.append("incomplete manifest repair count가 current scope ledger보다 큽니다")
        elif declared_count == actual_count:
            if declared_ledger_sha != history.get("ledger_sha256"):
                errors.append("동일 count repair ledger SHA가 다릅니다")
        else:
            status = "SUPERSEDED"
            policy = "scope_history_added_after_incomplete_attempt"
    if errors:
        status = "UNSAFE"
    return {
        "status": status,
        "policy": policy,
        "terminal_artifacts_finalized": terminal_finalized,
        "declared_count": declared_count,
        "actual_count": actual_count,
        "declared_ledger_sha256": declared_ledger_sha or None,
        "actual_ledger_sha256": history.get("ledger_sha256"),
        "errors": errors,
    }


def _post_id_from_result(row: dict[str, Any]) -> int | None:
    try:
        return int(row.get("post_id"))
    except Exception:
        return None


def _post_id_from_checkpoint(row: dict[str, Any]) -> int | None:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    try:
        return int(row.get("post_id") or result.get("post_id"))
    except Exception:
        return None


def _post_id_from_pending(row: dict[str, Any]) -> int | None:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    try:
        return int(row.get("post_id") or result.get("post_id"))
    except Exception:
        return None


def _canonical_post_id(value: Any) -> int | str | None:
    """Return the sidecar-compatible identity used for duplicate detection."""
    if isinstance(value, bool) or value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = int(text)
    except ValueError:
        return text
    return number if number > 0 else None


def _wrapper_post_id(row: dict[str, Any]) -> int | str | None:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    outer = _canonical_post_id(row.get("post_id"))
    inner = _canonical_post_id(result.get("post_id"))
    return outer if outer is not None else inner


def _global_idx(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _duplicate_values(values: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    duplicates: set[Any] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return sorted(duplicates, key=str)


def _validate_scope_provenance(
    *,
    manifest: dict[str, Any],
    manifest_path: Path | None,
    journal_path: Path | None,
    descriptor: PublicationScopeDescriptor | None,
) -> dict[str, Any]:
    path_field = "publication_scope_config"
    sha_field = "publication_scope_config_sha256"
    expected_path = (
        journal_path.with_name(journal_path.name + ".config.json")
        if journal_path is not None
        else None
    )
    implicit_sidecar_exists = bool(expected_path is not None and expected_path.exists())
    declared = path_field in manifest or sha_field in manifest or implicit_sidecar_exists
    manifest_attestation = str(
        manifest.get("publication_release_attestation_status") or ""
    ).strip()
    if not declared:
        return {
            "status": "NOT_PROVABLE",
            "gate": "NOT_PROVABLE",
            "path": None,
            "file_sha256": None,
            "release_attestation_status": "NOT_PROVABLE",
            "errors": [],
        }
    errors: list[str] = []
    config_path = _artifact_path_from_manifest(manifest.get(path_field), manifest_path)
    payload: dict[str, Any] | None = None
    file_sha256: str | None = None
    raw: bytes | None = None
    if config_path is None or not config_path.exists():
        errors.append("publication scope config 파일이 없습니다")
    else:
        try:
            raw = config_path.read_bytes()
            if not raw.endswith(b"\n"):
                raise ValueError("scope config가 newline으로 종료되지 않았습니다")
            file_sha256 = hashlib.sha256(raw).hexdigest()
            value = json.loads(raw.decode("utf-8", errors="strict"))
            if not isinstance(value, dict):
                raise ValueError("scope config가 JSON 객체가 아닙니다")
            payload = value
            canonical_raw = (_canonical_json(payload) + "\n").encode("utf-8")
            if raw != canonical_raw:
                errors.append("scope config가 canonical JSON 직렬화와 다릅니다")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"publication scope config 검증 실패: {exc}")
    if (
        config_path is None
        or expected_path is None
        or config_path.resolve() != expected_path.resolve()
    ):
        errors.append("scope config 경로가 scope journal config 경로와 다릅니다")
    declared_file_sha = str(manifest.get(sha_field) or "").strip().lower()
    if not _valid_sha256(declared_file_sha):
        errors.append("manifest scope config SHA가 유효하지 않습니다")
    elif file_sha256 is not None and file_sha256 != declared_file_sha:
        errors.append("scope config file SHA가 manifest와 다릅니다")
    payload_attestation = ""
    if payload is not None:
        expected_fields = {
            "schema_version",
            "publication_scope_id",
            "input_snapshot_sha256",
            "ordered_post_ids",
            "decision_config",
            "decision_config_sha256",
            "decision_environment",
            "decision_environment_sha256",
            "release_fingerprint",
            "release_fingerprint_source",
            "release_attestation_status",
            "slang_db_input_sha256",
        }
        if set(payload) != expected_fields:
            errors.append("scope config field 집합이 다릅니다")
        if payload.get("schema_version") != "publication_scope_config_v1":
            errors.append("scope config schema_version이 다릅니다")
        decision_config = payload.get("decision_config")
        decision_environment = payload.get("decision_environment")
        if descriptor is None:
            errors.append("scope config를 검증할 descriptor가 없습니다")
        else:
            if payload.get("publication_scope_id") != descriptor.publication_scope_id:
                errors.append("scope config publication_scope_id가 descriptor와 다릅니다")
            if payload.get("publication_scope_id") != manifest.get("publication_scope_id"):
                errors.append("scope config publication_scope_id가 manifest와 다릅니다")
            if payload.get("input_snapshot_sha256") != descriptor.input_file_sha256:
                errors.append("scope config input snapshot이 descriptor와 다릅니다")
            if manifest.get("publication_input_snapshot_sha256") != descriptor.input_file_sha256:
                errors.append("manifest input snapshot이 descriptor와 다릅니다")
            ordered = payload.get("ordered_post_ids")
            normalized_order = (
                [_canonical_post_id(value) for value in ordered]
                if isinstance(ordered, list)
                else None
            )
            if normalized_order != list(descriptor.post_ids):
                errors.append("scope config ordered_post_ids가 descriptor와 다릅니다")
            if not isinstance(decision_config, dict):
                errors.append("scope config decision_config가 객체가 아닙니다")
            else:
                config_sha = _canonical_sha256(decision_config)
                if payload.get("decision_config_sha256") != config_sha:
                    errors.append("scope config decision_config SHA가 재계산과 다릅니다")
                if descriptor.config_hash != config_sha:
                    errors.append("descriptor config_hash가 decision_config와 다릅니다")
                if manifest.get("publication_config_sha256") != config_sha:
                    errors.append("manifest publication_config_sha256가 다릅니다")
            payload_release = str(payload.get("release_fingerprint") or "").strip().lower() or None
            manifest_release = str(
                manifest.get("publication_release_fingerprint") or ""
            ).strip().lower() or None
            if payload_release is None or not _valid_sha256(payload_release):
                errors.append("scope config release fingerprint가 64자리 SHA256이 아닙니다")
            if payload_release != descriptor.release_fingerprint:
                errors.append("scope config release fingerprint가 descriptor와 다릅니다")
            if manifest_release != descriptor.release_fingerprint:
                errors.append("manifest release fingerprint가 descriptor와 다릅니다")
        payload_release_source = str(
            payload.get("release_fingerprint_source") or ""
        ).strip()
        manifest_release_source = str(
            manifest.get("publication_release_fingerprint_source") or ""
        ).strip()
        allowed_release_sources = {
            "trusted_runtime_environment",
            "development_disk_snapshot",
        }
        if payload_release_source not in allowed_release_sources:
            errors.append("release_fingerprint_source가 허용 enum이 아닙니다")
        if manifest_release_source != payload_release_source:
            errors.append("manifest release fingerprint source가 scope config와 다릅니다")
        if not isinstance(decision_environment, dict):
            errors.append("scope config decision_environment가 객체가 아닙니다")
        else:
            environment_sha = _canonical_sha256(decision_environment)
            if payload.get("decision_environment_sha256") != environment_sha:
                errors.append("scope config decision environment SHA가 재계산과 다릅니다")
            if manifest.get("publication_decision_environment_sha256") != environment_sha:
                errors.append("manifest decision environment SHA가 다릅니다")
            if not isinstance(decision_config, dict):
                pass
            else:
                if decision_config.get("decision_environment_sha256") != environment_sha:
                    errors.append("decision_config environment SHA가 raw environment와 다릅니다")
                if decision_config.get("decision_environment_keys") != sorted(
                    decision_environment
                ):
                    errors.append("decision_config environment keys가 raw environment와 다릅니다")
        slang_db_sha = payload.get("slang_db_input_sha256")
        if slang_db_sha is not None and not _valid_sha256(slang_db_sha):
            errors.append("scope config slang DB SHA가 유효하지 않습니다")
        if isinstance(decision_config, dict):
            if decision_config.get("slang_db_input_sha256") != slang_db_sha:
                errors.append("decision_config slang DB SHA가 scope config와 다릅니다")
            if decision_config.get("release_fingerprint") != payload.get(
                "release_fingerprint"
            ):
                errors.append("decision_config release fingerprint가 scope config와 다릅니다")
            if decision_config.get("release_fingerprint_source") != payload_release_source:
                errors.append("decision_config release source가 scope config와 다릅니다")
            if decision_config.get("release_attestation_status") != payload.get(
                "release_attestation_status"
            ):
                errors.append("decision_config release attestation이 scope config와 다릅니다")
        if manifest.get("publication_slang_db_input_sha256") != slang_db_sha:
            errors.append("manifest slang DB SHA가 scope config와 다릅니다")
        payload_attestation = str(
            payload.get("release_attestation_status") or ""
        ).strip()
        if payload_attestation not in {"OPERATOR_ATTESTED", "NOT_PROVABLE"}:
            errors.append("release_attestation_status가 허용 enum이 아닙니다")
        if manifest_attestation != payload_attestation:
            errors.append("manifest release attestation status가 scope config와 다릅니다")
        expected_attestation = (
            "OPERATOR_ATTESTED"
            if payload_release_source == "trusted_runtime_environment"
            else "NOT_PROVABLE"
            if payload_release_source == "development_disk_snapshot"
            else None
        )
        if expected_attestation is not None and payload_attestation != expected_attestation:
            errors.append("release source와 attestation status 조합이 다릅니다")
    status = "UNSAFE" if errors else "VALID"
    return {
        "status": status,
        "gate": "NO-GO" if errors else "GO",
        "path": str(config_path) if config_path is not None else None,
        "file_sha256": file_sha256,
        "release_attestation_status": (
            payload_attestation if status == "VALID" else "NOT_PROVABLE"
        ),
        "errors": errors,
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _validate_terminal_manifest_integrity(
    *,
    manifest: dict[str, Any],
    exact_once: dict[str, Any],
    final_rows: list[Any],
    checkpoint_rows: list[dict[str, Any]],
    completed_rows: list[dict[str, Any]],
    failed_rows: list[dict[str, Any]],
    pending_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if exact_once.get("journal_mode") != "current":
        return {"status": "NOT_APPLICABLE", "errors": []}
    if manifest.get("terminal_artifacts_finalized") is not True:
        return {"status": "NOT_FINALIZED", "errors": []}
    expected_count = _nonnegative_int(manifest.get("input_post_count"))
    errors: list[str] = []
    if not expected_count:
        errors.append("terminal input_post_count가 positive integer가 아닙니다")
    else:
        expected_fields = {
            "completed_count": expected_count,
            "publication_commit_count": expected_count,
            "flushed_count": expected_count,
            "pending_count": 0,
            "failed_count": 0,
            "next_save_idx": expected_count + 1,
        }
        for field, expected in expected_fields.items():
            if _nonnegative_int(manifest.get(field)) != expected:
                errors.append(f"manifest {field}가 terminal expected count와 다릅니다")
        if exact_once.get("journal_event_count") != expected_count:
            errors.append("WAL event count가 input_post_count와 다릅니다")
        if len(final_rows) != expected_count:
            errors.append("final result row count가 input_post_count와 다릅니다")
        if len(checkpoint_rows) != expected_count:
            errors.append("checkpoint row count가 input_post_count와 다릅니다")
        if len(completed_rows) != expected_count:
            errors.append("checkpoint completed row count가 input_post_count와 다릅니다")
        if failed_rows:
            errors.append("terminal checkpoint에 failed row가 있습니다")
        if pending_rows:
            errors.append("terminal pending snapshot에 row가 있습니다")
        if manifest.get("large_run_complete") is not True:
            errors.append("terminal manifest large_run_complete가 true가 아닙니다")
    return {"status": "UNSAFE" if errors else "VALID", "errors": errors}


def _artifact_path_from_manifest(raw: Any, manifest_path: Path | None) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    configured = Path(raw)
    if configured.is_absolute() or configured.exists() or manifest_path is None:
        return configured
    return manifest_path.parent / configured


def _journal_path_from_manifest(manifest: dict[str, Any], manifest_path: Path | None) -> Path | None:
    return _artifact_path_from_manifest(
        manifest.get("publication_commit_journal"),
        manifest_path,
    )


def _p2_enabled(
    manifest: dict[str, Any],
    checkpoint_rows: list[dict[str, Any]],
    pending_rows: list[dict[str, Any]],
) -> bool:
    manifest_declares_p2 = any(
        manifest.get(key) not in (None, "")
        for key in (
            "publication_commit_schema",
            "publication_scope_id",
            "publication_commit_journal",
            "publication_scope_descriptor",
        )
    )
    wrapper_declares_p2 = any(
        "publication_commit" in row for row in checkpoint_rows
    ) or any("publication_commit" in row for row in pending_rows)
    return manifest_declares_p2 or wrapper_declares_p2


def _fresh_measurement_required(manifest: dict[str, Any]) -> bool:
    """Return whether recovery must fail closed on a fresh measurement claim."""

    measurement = manifest.get("decision_call_measurement")
    return bool(
        isinstance(measurement, dict)
        and (
            str(measurement.get("mode") or "").upper() == "REQUIRED"
            or measurement.get("early_route_enabled") is True
        )
    ) or str(manifest.get("publication_execution_mode") or "").upper() == (
        "FRESH_EXECUTION_NO_PUBLIC_WRITE"
    )


def _wal_snapshot(path: Path | None) -> dict[str, Any]:
    """Capture only immutable WAL bytes/counts; this helper never writes."""

    if path is None:
        return {"sha256": None, "event_count": None}
    try:
        raw = path.read_bytes()
    except OSError:
        return {"sha256": None, "event_count": None}
    event_count = 0
    try:
        for line in raw.splitlines():
            if line.strip():
                json.loads(line)
                event_count += 1
    except (UnicodeDecodeError, json.JSONDecodeError):
        event_count = None
    return {"sha256": hashlib.sha256(raw).hexdigest(), "event_count": event_count}


_EARLY_ROUTE_EXECUTION_RECEIPT_SCHEMA = "early_route_execution_receipt_v1"
_EARLY_ROUTE_MANIFEST_AGGREGATE_SCHEMA = "early_route_manifest_aggregate_v1"
_EARLY_ROUTE_MODE_SOURCE_ONLY_V1 = "SOURCE_ONLY_V1"
_EARLY_ROUTE_EXECUTION_RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "mode",
        "route_decision",
        "execution_status",
        "compute_skip_applied",
        "public_action_applied",
        "production_enable_allowed",
        "accuracy_status",
        "receipt_sha256",
    }
)
_EARLY_ROUTE_ROW_BINDING_FIELDS = frozenset(
    {
        "input_index",
        "post_id",
        "selected_lane",
        "source_view_sha256",
        "policy_sha256",
        "route_decision_sha256",
        "execution_receipt_sha256",
        "comparison_receipt_sha256",
        "comparison_gate",
        "decision_call_event_root_sha256",
        "cheap_zero_call_writer_verified",
    }
)
_EARLY_ROUTE_MANIFEST_AGGREGATE_FIELDS = frozenset(
    {
        "schema_version",
        "mode",
        "enabled",
        "measurement_arm",
        "mutable_context_mode",
        "mutable_context_binding_sha256",
        "slang_access_mode",
        "central_slang_db_write_allowed",
        "expected_input_count",
        "observed_route_count",
        "observed_comparison_count",
        "cheap_count",
        "full_count",
        "cheap_zero_call_writer_verified_count",
        "missing_route_count",
        "missing_comparison_count",
        "row_bindings",
        "row_bindings_sha256",
        "execution_gate",
        "execution_reason_codes",
        "production_enable_allowed",
        "accuracy_status",
        "gate",
        "aggregate_sha256",
    }
)
_EARLY_ROUTE_ZERO_FIELDS = (
    "expert_calls",
    "text_calls",
    "vlm_calls",
    "retry_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
)


def _is_strict_zero(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _safe_early_route_canonical_hash(value: Any) -> str | None:
    try:
        return early_route_canonical_hash(value)
    except (TypeError, ValueError):
        return None


def _early_route_hash_matches(value: Mapping[str, Any], field_name: str) -> bool:
    try:
        payload = dict(value)
        observed = payload.pop(field_name)
        expected = _safe_early_route_canonical_hash(payload)
        return _valid_sha256(observed) and observed == expected
    except (KeyError, TypeError, ValueError):
        return False


def _validate_early_route_measurement_config(
    measurement: Mapping[str, Any],
) -> list[str]:
    """Validate only the AFTER-only execution contract declared in the manifest."""

    reasons: list[str] = []
    required_values = {
        "mode": "REQUIRED",
        "binding_status": "BOUND",
        "arm": "AFTER",
        "execution_mode": "FRESH_EXECUTION_REQUIRED",
        "early_route_mode": _EARLY_ROUTE_MODE_SOURCE_ONLY_V1,
        "mutable_context_mode": "FROZEN_OFF",
    }
    if any(measurement.get(field) != expected for field, expected in required_values.items()):
        reasons.append("EARLY_ROUTE_MEASUREMENT_BINDING_INVALID")
    if (
        measurement.get("early_route_enabled") is not True
        or measurement.get("fresh_execution_required") is not True
        or measurement.get("actual_kpi_eligible") is not True
        or measurement.get("central_slang_db_write_allowed") is not False
        or measurement.get("slang_access_mode") not in {"OFF", "READ_ONLY"}
    ):
        reasons.append("EARLY_ROUTE_MEASUREMENT_BINDING_INVALID")

    mutable_context = measurement.get("mutable_context_binding")
    expected_context = {
        "schema_version": "paired_measurement_mutable_context_binding_v1",
        "mutable_context_mode": "FROZEN_OFF",
        "batch_context_enabled": False,
        "slang_access_mode": measurement.get("slang_access_mode"),
        "central_slang_db_write_allowed": False,
    }
    declared_context_hash = measurement.get("mutable_context_binding_sha256")
    expected_context_hash = _safe_early_route_canonical_hash(expected_context)
    if (
        not isinstance(mutable_context, Mapping)
        or dict(mutable_context) != expected_context
        or not _valid_sha256(declared_context_hash)
        or declared_context_hash != expected_context_hash
    ):
        reasons.append("EARLY_ROUTE_MUTABLE_CONTEXT_BINDING_INVALID")
    return reasons


def _parse_early_route_execution_receipt(
    value: Any,
    *,
    publication_scope_id: Any,
    pair_id: Any,
    input_index: int,
    post_id: Any,
) -> tuple[EarlyRouteDecision | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(value, Mapping):
        return None, ["EARLY_ROUTE_EXECUTION_RECEIPT_MISSING"]
    if set(value) != _EARLY_ROUTE_EXECUTION_RECEIPT_FIELDS:
        return None, ["EARLY_ROUTE_EXECUTION_RECEIPT_SHAPE_INVALID"]
    if not _early_route_hash_matches(value, "receipt_sha256"):
        reasons.append("EARLY_ROUTE_EXECUTION_RECEIPT_HASH_INVALID")
    if (
        value.get("schema_version") != _EARLY_ROUTE_EXECUTION_RECEIPT_SCHEMA
        or value.get("mode") != _EARLY_ROUTE_MODE_SOURCE_ONLY_V1
        or value.get("public_action_applied") is not False
        or value.get("production_enable_allowed") is not False
        or value.get("accuracy_status") != "NOT_ESTIMABLE"
    ):
        reasons.append("EARLY_ROUTE_EXECUTION_RECEIPT_CONTRACT_INVALID")
    try:
        decision = EarlyRouteDecision.from_dict(value.get("route_decision"))
    except (TypeError, ValueError):
        return None, [*reasons, "EARLY_ROUTE_DECISION_RECEIPT_INVALID"]
    expected_skip = decision.selected_lane == LANE_CHEAP_NIL
    expected_status = (
        "CHEAP_ZERO_CALL_AUTHORITATIVE_REFERENCE_COPY"
        if expected_skip
        else "FULL_EXPERT_EXECUTED"
    )
    if (
        decision.publication_scope_id != publication_scope_id
        or decision.pair_id != pair_id
        or decision.arm != "AFTER"
        or decision.input_index != input_index
        or _canonical_post_id(decision.post_id) != _canonical_post_id(post_id)
        or value.get("compute_skip_applied") is not expected_skip
        or value.get("execution_status") != expected_status
    ):
        reasons.append("EARLY_ROUTE_EXECUTION_RECEIPT_BINDING_MISMATCH")
    return decision, reasons


def _parse_early_route_comparison_receipt(
    value: Any,
    *,
    decision: EarlyRouteDecision,
    authoritative: Mapping[str, Any],
) -> tuple[EarlyRouteComparisonReceipt | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(value, Mapping):
        return None, ["EARLY_ROUTE_COMPARISON_RECEIPT_MISSING"]
    try:
        comparison = EarlyRouteComparisonReceipt.from_dict(value)
    except (TypeError, ValueError):
        return None, ["EARLY_ROUTE_COMPARISON_RECEIPT_INVALID"]

    if (
        comparison.publication_scope_id != decision.publication_scope_id
        or comparison.pair_id != decision.pair_id
        or comparison.input_index != decision.input_index
        or comparison.post_id != decision.post_id
        or comparison.route_decision_sha256 != decision.decision_sha256
        or comparison.selected_lane != decision.selected_lane
    ):
        reasons.append("EARLY_ROUTE_COMPARISON_RECEIPT_BINDING_MISMATCH")
    if (
        comparison.authoritative_wal_receipt_sha256
        != authoritative.get("commit_sha256")
        or comparison.authoritative_wal_outcome != authoritative.get("outcome")
        or comparison.public_projection_before_sha256
        != authoritative.get("public_projection_sha256")
        or comparison.public_projection_after_sha256
        != authoritative.get("public_projection_sha256")
    ):
        reasons.append("EARLY_ROUTE_PUBLICATION_WAL_BINDING_MISMATCH")
    if comparison.public_noninterference_status != "GO":
        reasons.append("EARLY_ROUTE_PUBLIC_NONINTERFERENCE_VIOLATION")
    if decision.selected_lane == LANE_CHEAP_NIL:
        if (
            comparison.baseline_equivalence_status != "BASELINE_EQUIVALENT"
            or comparison.public_projection_match is not True
            or comparison.authoritative_wal_outcome != "HOLD"
        ):
            reasons.append("EARLY_ROUTE_CHEAP_BASELINE_MISMATCH")
    elif decision.selected_lane != LANE_FULL:
        reasons.append("EARLY_ROUTE_DECISION_LANE_INVALID")
    return comparison, reasons


def _validate_early_route_measurement_recovery(
    *,
    manifest: dict[str, Any],
    measurement: Mapping[str, Any],
    checkpoint_rows: list[dict[str, Any]],
    canonical_wal_decision_ids: dict[int, dict[str, Any]],
    decision_call_rows_by_coordinate: dict[tuple[int, Any], dict[str, Any]],
    expected_run_id: str,
) -> tuple[list[str], dict[str, Any]]:
    """Independently bind AFTER receipts to the immutable WAL and ledger rows.

    The aggregate is an attestation, never an authority.  This function
    reconstructs its row bindings from checkpoint-local typed receipts and the
    independently read decision-call ledger before accepting its self hash.
    """

    reasons = _validate_early_route_measurement_config(measurement)
    expected: dict[tuple[int, Any], dict[str, Any]] = {}
    for raw_index, authoritative in canonical_wal_decision_ids.items():
        index = _global_idx(raw_index)
        post_id = (
            _canonical_post_id(authoritative.get("post_id"))
            if isinstance(authoritative, Mapping)
            else None
        )
        if (
            index is None
            or post_id is None
            or not isinstance(authoritative, Mapping)
            or not _valid_sha256(authoritative.get("decision_id"))
            or not _valid_sha256(authoritative.get("commit_sha256"))
            or not _valid_sha256(authoritative.get("public_projection_sha256"))
            or authoritative.get("outcome") not in {"PUBLISH", "HOLD", "ERROR_HOLD"}
        ):
            reasons.append("EARLY_ROUTE_AUTHORITATIVE_WAL_EVIDENCE_INVALID")
            continue
        expected[(index, post_id)] = dict(authoritative)
    if not expected:
        reasons.append("EARLY_ROUTE_AUTHORITATIVE_WAL_EVIDENCE_MISSING")
    manifest_count = _nonnegative_int(manifest.get("input_post_count"))
    if manifest_count != len(expected):
        reasons.append("EARLY_ROUTE_MANIFEST_INPUT_COVERAGE_MISMATCH")

    checkpoint_by_coordinate: dict[tuple[int, Any], dict[str, Any]] = {}
    seen_checkpoint_coordinates: set[tuple[int, Any]] = set()
    for row in checkpoint_rows:
        index = _global_idx(row.get("global_idx"))
        post_id = _canonical_post_id(row.get("post_id"))
        if index is None or post_id is None:
            reasons.append("EARLY_ROUTE_CHECKPOINT_COORDINATE_INVALID")
            continue
        coordinate = (index, post_id)
        if coordinate not in expected:
            reasons.append("EARLY_ROUTE_CHECKPOINT_ROW_OUT_OF_SCOPE")
            continue
        if coordinate in seen_checkpoint_coordinates:
            reasons.append("EARLY_ROUTE_CHECKPOINT_COORDINATE_DUPLICATE")
            continue
        seen_checkpoint_coordinates.add(coordinate)
        if row.get("status") != "completed":
            reasons.append("EARLY_ROUTE_CHECKPOINT_ROW_NOT_COMPLETED")
            continue
        checkpoint_by_coordinate[coordinate] = row
    if set(checkpoint_by_coordinate) != set(expected):
        reasons.append("EARLY_ROUTE_CHECKPOINT_COVERAGE_INCOMPLETE")

    row_bindings: list[dict[str, Any]] = []
    parsed_decisions: dict[tuple[int, Any], EarlyRouteDecision] = {}
    parsed_comparisons: dict[tuple[int, Any], EarlyRouteComparisonReceipt] = {}
    cheap_zero_verified: set[tuple[int, Any]] = set()
    for coordinate in sorted(expected, key=lambda item: str(item[0])):
        index, post_id = coordinate
        authoritative = expected[coordinate]
        row = checkpoint_by_coordinate.get(coordinate)
        if row is None:
            continue
        row_valid = True
        result = row.get("result")
        if not isinstance(result, dict):
            reasons.append("EARLY_ROUTE_CHECKPOINT_RESULT_INVALID")
            continue
        try:
            attempt_receipt = validate_publication_result_commit(
                result,
                row.get("publication_commit"),
                expected_scope_id=manifest.get("publication_scope_id"),
                expected_input_index=index,
                expected_post_id=post_id,
            )
        except (TypeError, ValueError, PublicationCommitError):
            reasons.append("EARLY_ROUTE_CHECKPOINT_ATTEMPT_RECEIPT_INVALID")
            row_valid = False
            attempt_receipt = None
        if attempt_receipt is not None and (
            attempt_receipt.attempt_run_id != expected_run_id
            or attempt_receipt.decision_id != authoritative.get("decision_id")
            or attempt_receipt.public_projection_sha256
            != authoritative.get("public_projection_sha256")
        ):
            reasons.append("EARLY_ROUTE_CHECKPOINT_ATTEMPT_BINDING_MISMATCH")
            row_valid = False

        run_meta = result.get("run_meta")
        if not isinstance(run_meta, Mapping):
            reasons.append("EARLY_ROUTE_CHECKPOINT_RUN_META_MISSING")
            continue
        if (
            run_meta.get("run_id") != expected_run_id
            or run_meta.get("measurement_execution_source")
            != "FRESH_EXECUTION_NO_PUBLIC_WRITE"
            or run_meta.get("decision_call_measurement") != dict(measurement)
        ):
            reasons.append("EARLY_ROUTE_CHECKPOINT_MEASUREMENT_BINDING_MISMATCH")
            row_valid = False
        early_row = run_meta.get("early_route_measurement")
        if not isinstance(early_row, Mapping) or set(early_row) != {
            "execution_receipt",
            "comparison_receipt",
        }:
            reasons.append("EARLY_ROUTE_CHECKPOINT_RECEIPTS_MISSING")
            continue

        decision, execution_reasons = _parse_early_route_execution_receipt(
            early_row.get("execution_receipt"),
            publication_scope_id=manifest.get("publication_scope_id"),
            pair_id=measurement.get("pair_id"),
            input_index=index,
            post_id=post_id,
        )
        reasons.extend(execution_reasons)
        if execution_reasons or decision is None:
            continue
        comparison, comparison_reasons = _parse_early_route_comparison_receipt(
            early_row.get("comparison_receipt"),
            decision=decision,
            authoritative=authoritative,
        )
        reasons.extend(comparison_reasons)
        if comparison_reasons or comparison is None:
            continue

        ledger_row = decision_call_rows_by_coordinate.get(coordinate)
        if not isinstance(ledger_row, Mapping):
            reasons.append("EARLY_ROUTE_DECISION_CALL_ROW_MISSING")
            continue
        if (
            ledger_row.get("attempt_run_id") != expected_run_id
            or ledger_row.get("seal_status") != "SEALED"
            or ledger_row.get("link_status") != "LINKED"
            or ledger_row.get("publication_decision_id")
            != authoritative.get("decision_id")
            or not _valid_sha256(ledger_row.get("event_root_sha256"))
        ):
            reasons.append("EARLY_ROUTE_DECISION_CALL_LINKAGE_INVALID")
            row_valid = False
        zero_verified = False
        if decision.selected_lane == LANE_CHEAP_NIL:
            zero_verified = bool(
                ledger_row.get("usage_status") == "NO_CALLS"
                and all(_is_strict_zero(ledger_row.get(field)) for field in _EARLY_ROUTE_ZERO_FIELDS)
            )
            if not zero_verified:
                reasons.append("EARLY_ROUTE_CHEAP_ZERO_CALL_NOT_PROVEN")
                row_valid = False
            else:
                cheap_zero_verified.add(coordinate)

        parsed_decisions[coordinate] = decision
        parsed_comparisons[coordinate] = comparison
        if not row_valid:
            continue
        row_bindings.append(
            {
                "input_index": index,
                "post_id": decision.post_id,
                "selected_lane": decision.selected_lane,
                "source_view_sha256": decision.source_view_sha256,
                "policy_sha256": decision.policy_sha256,
                "route_decision_sha256": decision.decision_sha256,
                "execution_receipt_sha256": early_row["execution_receipt"].get(
                    "receipt_sha256"
                ),
                "comparison_receipt_sha256": comparison.receipt_sha256,
                "comparison_gate": comparison.gate,
                "decision_call_event_root_sha256": ledger_row.get("event_root_sha256"),
                "cheap_zero_call_writer_verified": zero_verified,
            }
        )

    aggregate = manifest.get("early_route_measurement")
    if not isinstance(aggregate, Mapping):
        reasons.append("EARLY_ROUTE_MANIFEST_AGGREGATE_MISSING")
    elif set(aggregate) != _EARLY_ROUTE_MANIFEST_AGGREGATE_FIELDS:
        reasons.append("EARLY_ROUTE_MANIFEST_AGGREGATE_SHAPE_INVALID")
    else:
        if not _early_route_hash_matches(aggregate, "aggregate_sha256"):
            reasons.append("EARLY_ROUTE_MANIFEST_AGGREGATE_HASH_INVALID")
        raw_bindings = aggregate.get("row_bindings")
        if (
            not isinstance(raw_bindings, list)
            or any(
                not isinstance(binding, Mapping)
                or set(binding) != _EARLY_ROUTE_ROW_BINDING_FIELDS
                for binding in raw_bindings
            )
        ):
            reasons.append("EARLY_ROUTE_ROW_BINDINGS_SHAPE_INVALID")
        else:
            computed_row_bindings_sha256 = _safe_early_route_canonical_hash(
                raw_bindings
            )
            if (
                computed_row_bindings_sha256 is None
                or aggregate.get("row_bindings_sha256")
                != computed_row_bindings_sha256
            ):
                reasons.append("EARLY_ROUTE_ROW_BINDINGS_HASH_INVALID")

        expected_cheap_count = sum(
            decision.selected_lane == LANE_CHEAP_NIL
            for decision in parsed_decisions.values()
        )
        expected_full_count = sum(
            decision.selected_lane == LANE_FULL
            for decision in parsed_decisions.values()
        )
        aggregate_contract = {
            "schema_version": _EARLY_ROUTE_MANIFEST_AGGREGATE_SCHEMA,
            "mode": _EARLY_ROUTE_MODE_SOURCE_ONLY_V1,
            "enabled": True,
            "measurement_arm": "AFTER",
            "mutable_context_mode": measurement.get("mutable_context_mode"),
            "mutable_context_binding_sha256": measurement.get(
                "mutable_context_binding_sha256"
            ),
            "slang_access_mode": measurement.get("slang_access_mode"),
            "central_slang_db_write_allowed": measurement.get(
                "central_slang_db_write_allowed"
            ),
            "expected_input_count": len(expected),
            "observed_route_count": len(parsed_decisions),
            "observed_comparison_count": len(parsed_comparisons),
            "cheap_count": expected_cheap_count,
            "full_count": expected_full_count,
            "cheap_zero_call_writer_verified_count": len(cheap_zero_verified),
            "missing_route_count": max(0, len(expected) - len(parsed_decisions)),
            "missing_comparison_count": max(0, len(expected) - len(parsed_comparisons)),
            "execution_gate": "GO",
            "execution_reason_codes": [],
            "production_enable_allowed": False,
            "accuracy_status": "NOT_ESTIMABLE",
            "gate": "NO_GO_ACCURACY_NOT_ESTIMABLE",
        }
        if any(aggregate.get(key) != value for key, value in aggregate_contract.items()):
            reasons.append("EARLY_ROUTE_MANIFEST_AGGREGATE_CONTRACT_MISMATCH")
        if aggregate.get("row_bindings") != row_bindings:
            reasons.append("EARLY_ROUTE_MANIFEST_ROW_BINDINGS_MISMATCH")

    diagnostics = {
        "required": True,
        "expected_row_count": len(expected),
        "checkpoint_row_count": len(checkpoint_by_coordinate),
        "independent_route_receipt_count": len(parsed_decisions),
        "independent_comparison_receipt_count": len(parsed_comparisons),
        "independent_cheap_zero_call_verified_count": len(cheap_zero_verified),
    }
    return sorted(set(reasons)), diagnostics


def _validate_fresh_measurement_recovery(
    *,
    manifest: dict[str, Any],
    manifest_path: Path | None,
    canonical_wal_decision_ids: dict[int, dict[str, Any]],
    checkpoint_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Independently prove a REQUIRED fresh arm without mutating either ledger.

    Publication WAL rows remain the only logical-decision authority.  The
    decision-call ledger is read with the independent reader and can only make
    a measurement claim eligible when every fresh attempt row links back to
    that authoritative decision set.
    """

    if not _fresh_measurement_required(manifest):
        return {
            "status": "NOT_APPLICABLE",
            "measurement_eligible": False,
            "actual_kpi_status": "NOT_ESTIMABLE",
            "recovery_action": "NOT_APPLICABLE",
            "reason_codes": [],
        }

    measurement = manifest.get("decision_call_measurement")
    measurement = measurement if isinstance(measurement, dict) else {}
    reasons: list[str] = []
    required_declared = str(measurement.get("mode") or "").upper() == "REQUIRED"
    publication_fresh = str(manifest.get("publication_execution_mode") or "").upper() == (
        "FRESH_EXECUTION_NO_PUBLIC_WRITE"
    )
    expected_bindings = {
        "run_spec_sha256": measurement.get("run_spec_sha256"),
        "pair_id": measurement.get("pair_id"),
        "arm": measurement.get("arm"),
        "fresh_execution_mode": True,
    }
    if (
        not required_declared
        or measurement.get("binding_status") != "BOUND"
        or measurement.get("actual_kpi_eligible") is not True
        or measurement.get("execution_mode") != "FRESH_EXECUTION_REQUIRED"
        or measurement.get("fresh_execution_required") is not True
        or not _valid_sha256(expected_bindings["run_spec_sha256"])
        or not isinstance(expected_bindings["pair_id"], str)
        or not expected_bindings["pair_id"].strip()
        or expected_bindings["arm"] not in {"BEFORE", "AFTER"}
    ):
        reasons.append("MEASUREMENT_MANIFEST_BINDING_INVALID")
    if publication_fresh != required_declared:
        reasons.append("PUBLICATION_FRESH_MODE_MEASUREMENT_INCONSISTENT")

    ledger_path = _artifact_path_from_manifest(
        manifest.get("decision_call_ledger_path"), manifest_path
    )
    declared_scope_sha = str(manifest.get("decision_call_ledger_scope_sha256") or "")
    if ledger_path is None:
        reasons.append("DECISION_CALL_LEDGER_PATH_MISSING")
    if not _valid_sha256(declared_scope_sha):
        reasons.append("DECISION_CALL_LEDGER_SCOPE_SHA256_INVALID")

    readback: dict[str, Any] | None = None
    if ledger_path is not None:
        try:
            readback = read_decision_call_ledger(ledger_path)
        except Exception as exc:  # independent reader failures must be forensic NO-GO
            reasons.append(f"DECISION_CALL_READBACK_ERROR:{type(exc).__name__}")

    scope = readback.get("scope") if isinstance(readback, dict) else None
    rows = readback.get("rows") if isinstance(readback, dict) else None
    coverage = readback.get("coverage") if isinstance(readback, dict) else None
    if not isinstance(readback, dict) or readback.get("gate_status") != "GO":
        reasons.append("DECISION_CALL_READBACK_NOT_GO")
    elif not verify_readback_report_sha256(readback):
        reasons.append("DECISION_CALL_READBACK_REPORT_SHA256_INVALID")
    if not isinstance(scope, dict):
        reasons.append("DECISION_CALL_LEDGER_SCOPE_MISSING")
    else:
        if scope.get("scope_sha256") != declared_scope_sha:
            reasons.append("DECISION_CALL_LEDGER_SCOPE_SHA256_MISMATCH")
        if scope.get("publication_scope_id") != manifest.get("publication_scope_id"):
            reasons.append("DECISION_CALL_LEDGER_PUBLICATION_SCOPE_MISMATCH")
        if scope.get("measurement_bindings") != expected_bindings:
            reasons.append("DECISION_CALL_MEASUREMENT_BINDING_MISMATCH")

    expected_run_id = str(manifest.get("run_id") or "").strip()
    if not expected_run_id:
        reasons.append("MEASUREMENT_ATTEMPT_RUN_ID_MISSING")
    if not isinstance(coverage, dict):
        reasons.append("DECISION_CALL_COVERAGE_MISSING")
    else:
        run_ids = coverage.get("attempt_run_ids")
        if run_ids != [expected_run_id]:
            reasons.append("MEASUREMENT_ATTEMPT_RUN_ID_MISMATCH")
        if coverage.get("attempt_run_count") != 1:
            reasons.append("MEASUREMENT_MULTIPLE_ATTEMPT_RUNS")
        if coverage.get("observed_row_count") != len(canonical_wal_decision_ids):
            reasons.append("MEASUREMENT_ROW_COVERAGE_INCOMPLETE")

    if not canonical_wal_decision_ids:
        reasons.append("AUTHORITATIVE_WAL_DECISION_SET_MISSING")
    by_coordinate: dict[tuple[int, Any], dict[str, Any]] = {}
    if not isinstance(rows, list):
        reasons.append("DECISION_CALL_ROWS_MISSING")
    else:
        for row in rows:
            if not isinstance(row, dict):
                reasons.append("DECISION_CALL_ROW_INVALID")
                continue
            index = _global_idx(row.get("input_index"))
            post_id = _canonical_post_id(row.get("post_id"))
            if index is None or post_id is None:
                reasons.append("DECISION_CALL_ROW_COORDINATE_INVALID")
                continue
            key = (index, post_id)
            if key in by_coordinate:
                reasons.append("DECISION_CALL_ROW_COORDINATE_DUPLICATE")
            by_coordinate[key] = row
        expected_coordinates = {
            (index, _canonical_post_id(value.get("post_id"))): value
            for index, value in canonical_wal_decision_ids.items()
        }
        if set(by_coordinate) != set(expected_coordinates):
            reasons.append("MEASUREMENT_ROW_COVERAGE_MISMATCH")
        for coordinate, authoritative in expected_coordinates.items():
            row = by_coordinate.get(coordinate)
            if row is None:
                continue
            if row.get("attempt_run_id") != expected_run_id:
                reasons.append("MEASUREMENT_ROW_ATTEMPT_RUN_ID_MISMATCH")
            if row.get("seal_status") != "SEALED":
                reasons.append("MEASUREMENT_ROW_NOT_SEALED")
            if row.get("link_status") != "LINKED":
                reasons.append("MEASUREMENT_ROW_NOT_LINKED")
            if row.get("publication_decision_id") != authoritative.get("decision_id"):
                reasons.append("AUTHORITATIVE_WAL_LINK_MISMATCH")

    early_route_recovery: dict[str, Any] | None = None
    if measurement.get("early_route_enabled") is True:
        early_reasons, early_route_recovery = _validate_early_route_measurement_recovery(
            manifest=manifest,
            measurement=measurement,
            checkpoint_rows=checkpoint_rows or [],
            canonical_wal_decision_ids=canonical_wal_decision_ids,
            decision_call_rows_by_coordinate=by_coordinate,
            expected_run_id=expected_run_id,
        )
        reasons.extend(early_reasons)

    reason_codes = sorted(set(reasons))
    go = not reason_codes
    recovery = {
        "status": "GO" if go else "NO-GO",
        "measurement_eligible": go,
        "actual_kpi_status": "INDEPENDENTLY_VERIFIED_EXACT" if go else "NOT_ESTIMABLE",
        "recovery_action": "NONE" if go else "FULL_FRESH_ARM_RERUN_REQUIRED",
        "reason_codes": reason_codes,
        "ledger_path": str(ledger_path) if ledger_path is not None else None,
        "independent_readback": {
            "gate_status": readback.get("gate_status") if isinstance(readback, dict) else None,
            "report_sha256": readback.get("report_sha256") if isinstance(readback, dict) else None,
            "reason_codes": readback.get("reason_codes") if isinstance(readback, dict) else [],
        },
    }
    if early_route_recovery is not None:
        recovery["early_route_recovery"] = early_route_recovery
    return recovery


def _p2_validation(
    *,
    manifest: dict[str, Any],
    manifest_path: Path | None,
    result_path: Path,
    checkpoint_rows: list[dict[str, Any]],
    checkpoint_read_errors: list[dict[str, Any]],
    pending_rows: list[dict[str, Any]],
    pending_read_errors: list[dict[str, Any]],
    final_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail closed when an exact-once sidecar is declared by the manifest.

    The journal is the durable owner; checkpoint and pending files are only
    wrappers around its receipts.  A recovery artifact must not promote one
    without a one-to-one correspondence to the other.
    """
    reasons: list[str] = []
    fresh_measurement_attempt = _fresh_measurement_required(manifest)
    declared_journal_schema = manifest.get("publication_commit_journal_schema")
    if declared_journal_schema == PUBLICATION_COMMIT_JOURNAL_SCHEMA:
        journal_mode = "current"
    elif declared_journal_schema in (
        None,
        "",
        "publication_decision_commit_journal_v1",
    ):
        journal_mode = "v1_legacy"
    else:
        journal_mode = "unknown"
        reasons.append("manifest publication_commit_journal_schema가 지원되지 않습니다")
    schema_match = manifest.get("publication_commit_schema") == PUBLICATION_COMMIT_SCHEMA
    if not schema_match:
        reasons.append("manifest publication_commit_schema가 현재 P2 schema와 일치하지 않습니다")
    expected_scope = manifest.get("publication_scope_id")
    if not isinstance(expected_scope, str) or len(expected_scope.strip()) != 64:
        reasons.append("manifest publication_scope_id가 없거나 유효하지 않습니다")
        expected_scope = None
    else:
        expected_scope = expected_scope.strip().lower()

    journal_path = _journal_path_from_manifest(manifest, manifest_path)
    implicit_descriptor_path = (
        journal_path.with_name(journal_path.name + ".scope.json")
        if journal_path is not None
        else None
    )
    descriptor_declared = any(
        key in manifest
        for key in (
            "publication_scope_descriptor",
            "publication_scope_descriptor_sha256",
        )
    )
    descriptor_sidecar_exists = bool(
        implicit_descriptor_path is not None and implicit_descriptor_path.exists()
    )
    descriptor_required = descriptor_declared or descriptor_sidecar_exists
    descriptor_path = _artifact_path_from_manifest(
        manifest.get("publication_scope_descriptor"),
        manifest_path,
    )
    descriptor: PublicationScopeDescriptor | None = None
    descriptor_errors: list[dict[str, Any]] = []
    if descriptor_required:
        if not descriptor_declared:
            descriptor_errors.append(
                {
                    "reason": "journal scope descriptor는 존재하지만 manifest descriptor 계약이 제거되었습니다"
                }
            )
        if descriptor_path is None or not descriptor_path.exists():
            descriptor_errors.append(
                {"reason": "선언된 publication scope descriptor 파일이 없습니다"}
            )
        else:
            try:
                descriptor = PublicationScopeDescriptor.from_dict(
                    json.loads(descriptor_path.read_text(encoding="utf-8"))
                )
            except (json.JSONDecodeError, PublicationCommitError) as exc:
                descriptor_errors.append(
                    {"reason": f"publication scope descriptor 검증 실패: {exc}"}
                )
        if (
            descriptor_path is not None
            and implicit_descriptor_path is not None
            and descriptor_path.resolve() != implicit_descriptor_path.resolve()
        ):
            descriptor_errors.append(
                {"reason": "manifest descriptor 경로가 journal-owned scope descriptor와 다릅니다"}
            )
        declared_descriptor_sha = manifest.get(
            "publication_scope_descriptor_sha256"
        )
        if not isinstance(declared_descriptor_sha, str) or not declared_descriptor_sha.strip():
            descriptor_errors.append(
                {"reason": "manifest publication_scope_descriptor_sha256가 없습니다"}
            )
        elif (
            descriptor is not None
            and descriptor.descriptor_sha256 != declared_descriptor_sha.strip().lower()
        ):
            descriptor_errors.append(
                {"reason": "descriptor SHA가 manifest와 다릅니다"}
            )
        if (
            descriptor is not None
            and expected_scope is not None
            and descriptor.publication_scope_id != expected_scope
        ):
            descriptor_errors.append(
                {"reason": "descriptor publication_scope_id가 manifest와 다릅니다"}
            )
        manifest_input_count = _global_idx(manifest.get("input_post_count"))
        if (
            descriptor is not None
            and manifest_input_count is not None
            and len(descriptor.post_ids) != manifest_input_count
        ):
            descriptor_errors.append(
                {
                    "reason": "descriptor post_id 수가 manifest input_post_count와 다릅니다",
                    "descriptor_post_count": len(descriptor.post_ids),
                    "manifest_input_post_count": manifest_input_count,
                }
            )

    scope_provenance = _validate_scope_provenance(
        manifest=manifest,
        manifest_path=manifest_path,
        journal_path=journal_path,
        descriptor=descriptor,
    )

    attempt_claim_declared = any(
        key in manifest
        for key in ("output_attempt_claim", "output_attempt_claim_sha256")
    )
    attempt_claim_path = _artifact_path_from_manifest(
        manifest.get("output_attempt_claim"),
        manifest_path,
    )
    attempt_claim_errors: list[dict[str, Any]] = []
    attempt_claim_payload: dict[str, Any] | None = None
    attempt_claim_actual_sha256: str | None = None
    if attempt_claim_declared:
        if attempt_claim_path is None or not attempt_claim_path.exists():
            attempt_claim_errors.append(
                {"reason": "선언된 output attempt claim 파일이 없습니다"}
            )
        else:
            try:
                claim_bytes = attempt_claim_path.read_bytes()
                claim_text = claim_bytes.decode("utf-8", errors="strict")
                claim_value = json.loads(claim_text)
                attempt_claim_actual_sha256 = hashlib.sha256(claim_bytes).hexdigest()
                if not isinstance(claim_value, dict):
                    attempt_claim_errors.append(
                        {"reason": "output attempt claim이 JSON 객체가 아닙니다"}
                    )
                else:
                    attempt_claim_payload = claim_value
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                attempt_claim_errors.append(
                    {"reason": f"output attempt claim 검증 실패: {exc}"}
                )
        expected_claim_sha = manifest.get("output_attempt_claim_sha256")
        if not isinstance(expected_claim_sha, str) or not expected_claim_sha.strip():
            attempt_claim_errors.append(
                {"reason": "manifest output_attempt_claim_sha256가 없습니다"}
            )
        elif (
            attempt_claim_actual_sha256 is not None
            and attempt_claim_actual_sha256 != expected_claim_sha.strip().lower()
        ):
            attempt_claim_errors.append(
                {"reason": "output attempt claim SHA가 manifest와 다릅니다"}
            )
        if attempt_claim_payload is not None:
            if attempt_claim_payload.get("schema_version") != "expert_output_attempt_claim_v1":
                attempt_claim_errors.append(
                    {"reason": "output attempt claim schema_version이 다릅니다"}
                )
            if str(attempt_claim_payload.get("run_id") or "") != str(
                manifest.get("run_id") or ""
            ):
                attempt_claim_errors.append(
                    {"reason": "output attempt claim run_id가 manifest와 다릅니다"}
                )
            claim_output_path = _artifact_path_from_manifest(
                attempt_claim_payload.get("output_file"),
                attempt_claim_path,
            )
            manifest_output_path = _artifact_path_from_manifest(
                manifest.get("output_file"),
                manifest_path,
            )
            if manifest_output_path is None:
                attempt_claim_errors.append(
                    {"reason": "claim을 선언한 manifest에 output_file이 없습니다"}
                )
            if (
                claim_output_path is None
                or claim_output_path.resolve() != result_path.resolve()
            ):
                attempt_claim_errors.append(
                    {"reason": "output attempt claim output_file이 현재 final result와 다릅니다"}
                )
            if (
                manifest_output_path is not None
                and manifest_output_path.resolve() != result_path.resolve()
            ):
                attempt_claim_errors.append(
                    {"reason": "manifest output_file이 현재 final result와 다릅니다"}
                )

    wrapper_by_index: dict[int, dict[str, Any]] = {}
    wrapper_post_ids: list[int | str] = []
    wrapper_indices: list[int] = []
    wrapper_receipts: dict[int, PublicationDecisionCommit] = {}
    wrapper_errors: list[dict[str, Any]] = []
    for source, rows in (("checkpoint", checkpoint_rows), ("pending_snapshot", pending_rows)):
        for row in rows:
            idx = _global_idx(row.get("global_idx"))
            post_id = _wrapper_post_id(row)
            result = row.get("result")
            if idx is None or post_id is None or not isinstance(result, dict):
                wrapper_errors.append(
                    {"source": source, "line": row.get("_line_no"), "reason": "global_idx/post_id/result wrapper가 유효하지 않습니다"}
                )
                continue
            if _canonical_post_id(result.get("post_id")) != post_id:
                wrapper_errors.append(
                    {"source": source, "global_idx": idx, "post_id": post_id, "reason": "wrapper post_id와 result.post_id가 다릅니다"}
                )
            receipt_payload = row.get("publication_commit")
            if not isinstance(receipt_payload, dict):
                wrapper_errors.append(
                    {"source": source, "global_idx": idx, "post_id": post_id, "reason": "P2 publication_commit receipt가 없습니다"}
                )
                continue
            try:
                receipt = validate_publication_result_commit(
                    result,
                    receipt_payload,
                    expected_scope_id=expected_scope,
                    expected_input_index=idx,
                    expected_post_id=post_id,
                )
            except PublicationCommitError as exc:
                wrapper_errors.append(
                    {"source": source, "global_idx": idx, "post_id": post_id, "reason": f"P2 receipt 검증 실패: {exc}"}
                )
                continue

            existing = wrapper_by_index.get(idx)
            if existing is None:
                wrapper_by_index[idx] = {
                    "post_id": post_id,
                    "result": result,
                    "receipt": receipt,
                    "source": source,
                }
                wrapper_receipts[idx] = receipt
                wrapper_indices.append(idx)
                wrapper_post_ids.append(post_id)
            elif (
                existing["post_id"] != post_id
                or _canonical_json(existing["result"]) != _canonical_json(result)
                or existing["receipt"].to_dict() != receipt.to_dict()
            ):
                wrapper_errors.append(
                    {"source": source, "global_idx": idx, "post_id": post_id, "reason": "checkpoint와 pending wrapper가 서로 다릅니다"}
                )

    duplicate_wrapper_indices = _duplicate_values(wrapper_indices)
    duplicate_wrapper_post_ids = _duplicate_values(wrapper_post_ids)
    # A repeated checkpoint index is only harmless when it is the matching
    # pending snapshot copy; repeated checkpoint rows are collected below.
    checkpoint_indices = [_global_idx(row.get("global_idx")) for row in checkpoint_rows]
    checkpoint_post_ids = [_wrapper_post_id(row) for row in checkpoint_rows]
    pending_indices = [_global_idx(row.get("global_idx")) for row in pending_rows]
    pending_post_ids = [_wrapper_post_id(row) for row in pending_rows]
    duplicate_checkpoint_indices = _duplicate_values([x for x in checkpoint_indices if x is not None])
    duplicate_checkpoint_post_ids = _duplicate_values([x for x in checkpoint_post_ids if x is not None])
    duplicate_pending_indices = _duplicate_values([x for x in pending_indices if x is not None])
    duplicate_pending_post_ids = _duplicate_values([x for x in pending_post_ids if x is not None])
    descriptor_membership_errors: list[dict[str, Any]] = []
    if descriptor is not None:
        for row in checkpoint_rows:
            idx = _global_idx(row.get("global_idx"))
            post_id = _wrapper_post_id(row)
            if idx is None or post_id is None:
                continue
            try:
                descriptor_post_id = descriptor.expected_post_id(idx)
            except PublicationCommitError as exc:
                descriptor_membership_errors.append(
                    {
                        "global_idx": idx,
                        "post_id": post_id,
                        "reason": f"checkpoint index가 descriptor scope 밖입니다: {exc}",
                    }
                )
                continue
            if post_id != descriptor_post_id:
                descriptor_membership_errors.append(
                    {
                        "global_idx": idx,
                        "post_id": post_id,
                        "descriptor_post_id": descriptor_post_id,
                        "reason": "checkpoint (global_idx, post_id)가 descriptor membership과 다릅니다",
                    }
                )

    journal_receipts: list[PublicationDecisionCommit] = []
    journal_results_by_index: dict[int, dict[str, Any]] = {}
    journal_errors: list[dict[str, Any]] = []
    journal_raw = b""
    tail_state = {
        "uncommitted_tail_present": False,
        "uncommitted_tail_bytes": 0,
        "uncommitted_tail_sha256": None,
        "tail_repair_required": False,
    }
    if journal_path is None or not journal_path.exists():
        journal_errors.append({"reason": "P2 durable publication commit journal이 없습니다"})
    else:
        if journal_mode == "current":
            (
                journal_payloads,
                journal_read_errors,
                tail_state,
                journal_raw,
            ) = _iter_committed_wal_frames(journal_path)
        else:
            journal_payloads, journal_read_errors = _iter_jsonl(
                journal_path,
                source="publication_commit_journal",
                annotate_line=False,
            )
            try:
                journal_raw = journal_path.read_bytes()
            except OSError:
                journal_raw = b""
        journal_errors.extend(journal_read_errors)
        for event_number, payload in enumerate(journal_payloads, 1):
            try:
                if journal_mode == "current":
                    if set(payload) != {"schema_version", "receipt", "result"}:
                        raise PublicationCommitError(
                            "publication commit event fields mismatch"
                        )
                    if payload.get("schema_version") != PUBLICATION_COMMIT_EVENT_SCHEMA:
                        raise PublicationCommitError(
                            "publication commit event schema mismatch"
                        )
                    event_result = payload.get("result")
                    if not isinstance(event_result, dict):
                        raise PublicationCommitError(
                            "publication commit event result must be an object"
                        )
                    receipt = validate_publication_result_commit(
                        event_result,
                        payload.get("receipt"),
                        expected_scope_id=expected_scope,
                    )
                    if descriptor is None:
                        raise PublicationCommitError(
                            "current WAL requires a valid publication scope descriptor"
                        )
                    descriptor_post_id = descriptor.expected_post_id(
                        receipt.input_index
                    )
                    if receipt.post_id != descriptor_post_id:
                        raise PublicationCommitError(
                            "publication WAL event is outside descriptor membership"
                        )
                    journal_results_by_index[receipt.input_index] = event_result
                else:
                    receipt = PublicationDecisionCommit.from_dict(payload)
                journal_receipts.append(receipt)
            except PublicationCommitError as exc:
                journal_errors.append(
                    {
                        "event_number": event_number,
                        "reason": f"journal event 검증 실패: {exc}",
                    }
                )

    if journal_mode == "current":
        tail_repair_history = _validate_tail_repair_history(
            journal_path=journal_path,
            journal_raw=journal_raw,
            expected_scope_id=expected_scope,
            descriptor_sha256=(
                descriptor.descriptor_sha256 if descriptor is not None else None
            ),
        )
        tail_repair_manifest_binding = _validate_tail_repair_manifest_binding(
            manifest=manifest,
            manifest_path=manifest_path,
            journal_path=journal_path,
            history=tail_repair_history,
        )
    else:
        tail_repair_history = {
            "status": "NOT_APPLICABLE",
            "count": 0,
            "path": None,
            "errors": [],
        }
        tail_repair_manifest_binding = {
            "status": "NOT_APPLICABLE",
            "policy": "legacy_journal",
            "errors": [],
        }

    journal_by_index: dict[int, PublicationDecisionCommit] = {}
    journal_post_ids = [receipt.post_id for receipt in journal_receipts]
    journal_indices = [receipt.input_index for receipt in journal_receipts]
    duplicate_journal_indices = _duplicate_values(journal_indices)
    duplicate_journal_post_ids = _duplicate_values(journal_post_ids)
    for receipt in journal_receipts:
        journal_by_index.setdefault(receipt.input_index, receipt)
    wal_error_hold_indices = sorted(
        {
            receipt.input_index
            for receipt in journal_receipts
            if receipt.outcome == "ERROR_HOLD"
        }
    )

    if expected_scope is not None:
        for receipt in journal_receipts:
            if receipt.publication_scope_id != expected_scope:
                journal_errors.append(
                    {
                        "global_idx": receipt.input_index,
                        "post_id": receipt.post_id,
                        "reason": "durable journal receipt의 publication_scope_id가 manifest와 다릅니다",
                    }
                )

    correspondence_errors: list[dict[str, Any]] = []
    for idx, wrapper_receipt in wrapper_receipts.items():
        durable = journal_by_index.get(idx)
        if durable is None:
            correspondence_errors.append({"global_idx": idx, "reason": "wrapper receipt에 대응하는 durable journal receipt가 없습니다"})
        elif fresh_measurement_attempt:
            # Fresh measurement output has an attempt-local receipt hash/run ID.
            # It must not replace the authoritative WAL owner, but its logical
            # decision must agree with that owner for this exact scope row.
            if (
                durable.post_id != wrapper_receipt.post_id
                or durable.input_index != wrapper_receipt.input_index
                or durable.decision_id != wrapper_receipt.decision_id
            ):
                correspondence_errors.append(
                    {
                        "global_idx": idx,
                        "reason": "fresh wrapper logical decision이 authoritative WAL과 다릅니다",
                    }
                )
        elif durable.to_dict() != wrapper_receipt.to_dict():
            correspondence_errors.append({"global_idx": idx, "reason": "wrapper receipt와 durable journal receipt가 다릅니다"})
        elif journal_mode == "current" and _canonical_json(
            journal_results_by_index.get(idx)
        ) != _canonical_json(wrapper_by_index[idx]["result"]):
            correspondence_errors.append(
                {
                    "global_idx": idx,
                    "reason": "wrapper result와 canonical WAL result가 다릅니다",
                }
            )
    for idx, durable in journal_by_index.items():
        wrapper = wrapper_by_index.get(idx)
        if wrapper is None:
            if journal_mode != "current":
                correspondence_errors.append({"global_idx": idx, "post_id": durable.post_id, "reason": "durable journal receipt에 대응하는 wrapper가 없습니다"})
            continue
        if wrapper["post_id"] != durable.post_id:
            correspondence_errors.append({"global_idx": idx, "reason": "durable journal post_id와 wrapper post_id가 다릅니다"})

    final_post_ids = [
        _canonical_post_id(row.get("post_id")) if isinstance(row, dict) else None
        for row in final_rows
    ]
    duplicate_final_post_ids = _duplicate_values(
        [post_id for post_id in final_post_ids if post_id is not None]
    )
    ordered_checkpoint_rows = sorted(
        (
            row
            for row in checkpoint_rows
            if _global_idx(row.get("global_idx")) is not None
            and isinstance(row.get("result"), dict)
        ),
        key=lambda row: (
            _global_idx(row.get("global_idx")) or 0,
            int(row.get("_line_no") or 0),
        ),
    )
    ordered_wal_rows = [
        {
            "global_idx": idx,
            "post_id": journal_by_index[idx].post_id,
            "result": journal_results_by_index[idx],
        }
        for idx in sorted(journal_results_by_index)
    ]
    # Fresh measurement wrappers intentionally carry attempt-local run_meta.
    # Their final/pending ordering is therefore checked against their own
    # checkpoint rows, while recovered logical output still comes from WAL.
    canonical_source_rows = (
        ordered_checkpoint_rows
        if fresh_measurement_attempt
        else (ordered_wal_rows if journal_mode == "current" else ordered_checkpoint_rows)
    )
    manifest_large_run_complete = manifest.get("large_run_complete")
    if (
        "large_run_complete" in manifest
        and not isinstance(manifest_large_run_complete, bool)
    ):
        reasons.append("manifest large_run_complete가 boolean이 아닙니다")
    incomplete_prefix_policy = manifest_large_run_complete is False
    flushed_count = _nonnegative_int(manifest.get("flushed_count"))
    if incomplete_prefix_policy and flushed_count is None:
        reasons.append("불완전 P2 manifest flushed_count가 유효하지 않습니다")
    expected_final_checkpoint_rows = (
        canonical_source_rows[: flushed_count or 0]
        if incomplete_prefix_policy
        else canonical_source_rows
    )
    expected_final_post_ids = [
        _wrapper_post_id(row) for row in expected_final_checkpoint_rows
    ]
    final_cardinality_match = len(final_rows) == len(expected_final_checkpoint_rows)
    final_order_match = final_post_ids == expected_final_post_ids
    flushed_global_idx_match = True
    pending_wrapper_match = True
    final_correspondence_errors: list[dict[str, Any]] = []
    if not final_cardinality_match:
        final_correspondence_errors.append(
            {
                "reason": (
                    "final result row 수가 manifest flushed_count와 다릅니다"
                    if incomplete_prefix_policy
                    else "final result와 checkpoint wrapper의 row 수가 다릅니다"
                ),
                "final_row_count": len(final_rows),
                "expected_final_row_count": len(expected_final_checkpoint_rows),
            }
        )
    if not final_order_match:
        final_correspondence_errors.append(
            {
                "reason": "final result post_id 순서가 checkpoint global_idx 순서와 다릅니다",
                "final_post_ids": final_post_ids,
                "checkpoint_post_ids": expected_final_post_ids,
            }
        )
    if incomplete_prefix_policy:
        expected_flushed_indices = list(range(1, (flushed_count or 0) + 1))
        actual_flushed_indices = [
            _global_idx(row.get("global_idx"))
            for row in expected_final_checkpoint_rows
        ]
        flushed_global_idx_match = actual_flushed_indices == expected_flushed_indices
        if not flushed_global_idx_match:
            final_correspondence_errors.append(
                {
                    "reason": "final prefix의 checkpoint global_idx가 1..flushed_count 연속 범위가 아닙니다",
                    "expected_global_idx": expected_flushed_indices,
                    "actual_global_idx": actual_flushed_indices,
                }
            )
        actual_pending_indices = {
            _global_idx(row.get("global_idx")) for row in pending_rows
        }
        if journal_mode == "current":
            unflushed_indices = {
                _global_idx(row.get("global_idx"))
                for row in canonical_source_rows[(flushed_count or 0) :]
            }
            pending_wrapper_match = (
                None not in actual_pending_indices
                and actual_pending_indices.issubset(unflushed_indices)
                and _nonnegative_int(manifest.get("pending_count"))
                == len(pending_rows)
            )
        else:
            unflushed_indices = {
                _global_idx(row.get("global_idx"))
                for row in ordered_checkpoint_rows[(flushed_count or 0) :]
            }
            pending_wrapper_match = (
                None not in unflushed_indices
                and None not in actual_pending_indices
                and unflushed_indices == actual_pending_indices
                and _nonnegative_int(manifest.get("pending_count"))
                == len(pending_rows)
            )
        if not pending_wrapper_match:
            final_correspondence_errors.append(
                {
                    "reason": "unflushed checkpoint wrapper와 pending snapshot/manifest count가 다릅니다",
                    "unflushed_global_idx": sorted(
                        idx for idx in unflushed_indices if idx is not None
                    ),
                    "pending_global_idx": sorted(
                        idx for idx in actual_pending_indices if idx is not None
                    ),
                    "manifest_pending_count": manifest.get("pending_count"),
                    "pending_row_count": len(pending_rows),
                }
            )
    elif manifest_large_run_complete is True and pending_rows:
        pending_wrapper_match = False
        final_correspondence_errors.append(
            {"reason": "large_run_complete=true manifest에 pending wrapper가 남아 있습니다"}
        )
    for row_number, (row, checkpoint) in enumerate(
        zip(final_rows, expected_final_checkpoint_rows),
        1,
    ):
        if not isinstance(row, dict):
            final_correspondence_errors.append({"row": row_number, "reason": "final result row가 객체가 아닙니다"})
            continue
        post_id = _canonical_post_id(row.get("post_id"))
        checkpoint_post_id = _wrapper_post_id(checkpoint)
        if post_id != checkpoint_post_id:
            final_correspondence_errors.append(
                {
                    "row": row_number,
                    "global_idx": _global_idx(checkpoint.get("global_idx")),
                    "post_id": post_id,
                    "checkpoint_post_id": checkpoint_post_id,
                    "reason": "final result post_id가 동일 위치 checkpoint wrapper와 다릅니다",
                }
            )
        if _canonical_json(checkpoint.get("result")) != _canonical_json(row):
            final_correspondence_errors.append(
                {
                    "row": row_number,
                    "global_idx": _global_idx(checkpoint.get("global_idx")),
                    "post_id": post_id,
                    "reason": "final result와 동일 위치 checkpoint result가 다릅니다",
                }
            )

    expected_count = _global_idx(manifest.get("input_post_count"))
    if expected_count is None:
        reasons.append("manifest input_post_count가 없거나 유효하지 않습니다")
    expected_indices = set(range(1, (expected_count or 0) + 1))
    observed_indices = (
        set(journal_by_index) if journal_mode == "current" else set(wrapper_by_index)
    )
    missing_indices = sorted(expected_indices - observed_indices)
    extra_indices = sorted(observed_indices - expected_indices) if expected_count is not None else []
    coverage_complete = bool(expected_count) and not missing_indices and not extra_indices

    canonical_wal_unsafe = bool(
        reasons
        or descriptor_errors
        or attempt_claim_errors
        or journal_errors
        or tail_repair_history["errors"]
        or duplicate_journal_indices
        or duplicate_journal_post_ids
    )
    secondary_wrapper_unsafe = bool(
        checkpoint_read_errors
        or pending_read_errors
        or descriptor_membership_errors
        or wrapper_errors
        or correspondence_errors
        or final_correspondence_errors
        or duplicate_wrapper_indices
        or duplicate_wrapper_post_ids
        or duplicate_checkpoint_indices
        or duplicate_checkpoint_post_ids
        or duplicate_pending_indices
        or duplicate_pending_post_ids
        or duplicate_final_post_ids
    )
    unsafe = bool(
        canonical_wal_unsafe
        or (journal_mode != "current" and secondary_wrapper_unsafe)
    )
    subset_gate = "NO-GO" if unsafe else "GO"
    publication_rows_complete = bool(
        journal_mode == "current" and not unsafe and coverage_complete
    )
    if unsafe:
        exact_once_gate = "NO-GO"
        exact_once_status = "UNSAFE"
    elif journal_mode == "current":
        exact_once_gate = "GO" if coverage_complete else "NO-GO"
        exact_once_status = "PROVABLE" if coverage_complete else "INCOMPLETE"
    else:
        exact_once_gate = "NOT_PROVABLE"
        exact_once_status = "NOT_PROVABLE"
    return {
        "enabled": True,
        "journal_mode": journal_mode,
        "journal_schema": declared_journal_schema,
        "canonical_wal_integrity": (
            "UNSAFE"
            if canonical_wal_unsafe
            else ("VALID" if journal_mode == "current" else "NOT_PROVABLE")
        ),
        "secondary_wrapper_integrity": (
            "UNSAFE" if secondary_wrapper_unsafe else "VALID"
        ),
        "scope_provenance": scope_provenance,
        "scope_provenance_gate": scope_provenance["gate"],
        "release_attestation_status": scope_provenance[
            "release_attestation_status"
        ],
        "publication_rows_complete": publication_rows_complete,
        **tail_state,
        "tail_repair_history": tail_repair_history,
        "tail_repair_manifest_binding": tail_repair_manifest_binding,
        "tail_repair_record_count": tail_repair_history["count"],
        "tail_repair_history_status": tail_repair_history["status"],
        "exact_once_gate": exact_once_gate,
        "completed_subset_gate": subset_gate,
        "status": exact_once_status,
        "schema_match": schema_match,
        "source_artifact_errors": [
            *checkpoint_read_errors,
            *pending_read_errors,
        ],
        "output_attempt_claim": {
            "declared": attempt_claim_declared,
            "status": (
                "NO-GO"
                if attempt_claim_declared and attempt_claim_errors
                else ("GO" if attempt_claim_declared else "NOT_PROVABLE")
            ),
            "path": str(attempt_claim_path) if attempt_claim_path is not None else None,
            "actual_sha256": attempt_claim_actual_sha256,
            "errors": attempt_claim_errors,
        },
        "scope_descriptor": {
            "declared": descriptor_declared,
            "required": descriptor_required,
            "status": (
                "NO-GO"
                if descriptor_required
                and (descriptor_errors or descriptor_membership_errors)
                else ("GO" if descriptor_required else "NOT_PROVABLE")
            ),
            "path": str(descriptor_path) if descriptor_path is not None else None,
            "descriptor_sha256": (
                descriptor.descriptor_sha256 if descriptor is not None else None
            ),
            "membership_match": (
                not descriptor_membership_errors if descriptor is not None else None
            ),
            "errors": [*descriptor_errors, *descriptor_membership_errors],
        },
        "scope_match": (
            expected_scope is not None
            and not any("scope" in item.get("reason", "") for item in wrapper_errors)
            and not any("scope_id" in item.get("reason", "") for item in journal_errors)
            and not descriptor_errors
        ),
        "journal_path": str(journal_path) if journal_path is not None else None,
        "wrapper_count": len(wrapper_by_index),
        "journal_receipt_count": len(journal_receipts),
        "journal_event_count": (
            len(journal_results_by_index) if journal_mode == "current" else None
        ),
        "wal_error_hold_count": (
            len(wal_error_hold_indices) if journal_mode == "current" else None
        ),
        "wal_error_hold_global_idx_sample": (
            wal_error_hold_indices[:100] if journal_mode == "current" else []
        ),
        "expected_global_idx_count": expected_count,
        "expected_coverage_complete": coverage_complete,
        "missing_expected_global_idx_count": len(missing_indices),
        "missing_expected_global_idx_sample": missing_indices[:100],
        "extra_global_idx": extra_indices,
        "wrapper_errors": wrapper_errors,
        "journal_errors": journal_errors,
        "journal_correspondence_errors": correspondence_errors,
        "final_correspondence_errors": final_correspondence_errors,
        "final_cardinality_match": final_cardinality_match,
        "final_order_match": final_order_match,
        "final_policy": (
            "canonical_checkpoint_prefix"
            if incomplete_prefix_policy
            else "exact_checkpoint_equality"
        ),
        "flushed_global_idx_match": flushed_global_idx_match,
        "pending_wrapper_match": pending_wrapper_match,
        "duplicate_final_post_ids": duplicate_final_post_ids,
        "duplicate_wrapper_global_idx": duplicate_wrapper_indices,
        "duplicate_wrapper_post_ids": duplicate_wrapper_post_ids,
        "duplicate_checkpoint_global_idx": duplicate_checkpoint_indices,
        "duplicate_checkpoint_post_ids": duplicate_checkpoint_post_ids,
        "duplicate_pending_global_idx": duplicate_pending_indices,
        "duplicate_pending_post_ids": duplicate_pending_post_ids,
        "duplicate_journal_global_idx": duplicate_journal_indices,
        "duplicate_journal_post_ids": duplicate_journal_post_ids,
        "_canonical_wal_decision_ids": (
            {
                receipt.input_index: {
                    "post_id": receipt.post_id,
                    "decision_id": receipt.decision_id,
                    "commit_sha256": receipt.commit_sha256,
                    "public_projection_sha256": receipt.public_projection_sha256,
                    "outcome": receipt.outcome,
                    "publication_scope_id": receipt.publication_scope_id,
                    "publish_allowed": receipt.publish_allowed,
                }
                for receipt in journal_receipts
            }
            if journal_mode == "current"
            else {}
        ),
        "_canonical_rows": (
            [row["result"] for row in ordered_wal_rows]
            if journal_mode == "current"
            else None
        ),
    }


def publish_paired_recovery_artifacts(
    *,
    paired_run_spec_path: Path,
    source_manifest_path: Path,
    source_checkpoint_path: Path,
    source_pending_snapshot_path: Path,
    recovery_summary_path: Path,
    recovered_output_path: Path,
    recovery_witness_output_path: Path,
    recovered_manifest_output_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Publish a witness first and its recovered-manifest pointer last."""

    paths = {
        "paired_run_spec": paired_run_spec_path.resolve(),
        "source_manifest": source_manifest_path.resolve(),
        "source_checkpoint": source_checkpoint_path.resolve(),
        "source_pending": source_pending_snapshot_path.resolve(),
        "recovery_summary": recovery_summary_path.resolve(),
        "recovered_output": recovered_output_path.resolve(),
        "recovery_witness": recovery_witness_output_path.resolve(),
        "recovered_manifest": recovered_manifest_output_path.resolve(),
    }
    paths["recovery_witness"].unlink(missing_ok=True)
    paths["recovered_manifest"].unlink(missing_ok=True)
    try:
        source_manifest = _load_json(paths["source_manifest"])
        summary = _load_json(paths["recovery_summary"])
        if not isinstance(source_manifest, dict) or not isinstance(summary, dict):
            raise ValueError("paired recovery source manifest/summary must be objects")
        fresh_gate = summary.get("fresh_measurement_recovery")
        if (
            not isinstance(fresh_gate, dict)
            or fresh_gate.get("status") != "GO"
            or fresh_gate.get("measurement_eligible") is not True
            or fresh_gate.get("actual_kpi_status")
            != "INDEPENDENTLY_VERIFIED_EXACT"
            or fresh_gate.get("recovery_action") != "NONE"
            or fresh_gate.get("reason_codes") != []
            or summary.get("recovery_safe_to_use_as_completed_subset") is not True
            or summary.get("large_run_complete") is not True
        ):
            raise ValueError("paired recovery summary is not exact GO")
        witness = build_recovery_witness(
            run_spec_path=paths["paired_run_spec"],
            source_manifest_path=paths["source_manifest"],
            source_checkpoint_path=paths["source_checkpoint"],
            source_pending_snapshot_path=paths["source_pending"],
            recovery_summary_path=paths["recovery_summary"],
            recovered_output_path=paths["recovered_output"],
        )
        _atomic_write_json(paths["recovery_witness"], witness)
        recovered_manifest = json.loads(json.dumps(source_manifest))
        input_count = int(recovered_manifest.get("input_post_count") or 0)
        recovered_manifest.update(
            {
                "output_file": str(paths["recovered_output"]),
                "completed_count": input_count,
                "flushed_count": input_count,
                "pending_count": 0,
                "failed_count": 0,
                "next_save_idx": input_count + 1,
                "large_run_complete": True,
                "terminal_artifacts_finalized": True,
                "runtime_completion_gate": {"status": "GO"},
                "measurement_gate": {"status": "GO"},
                "fresh_measurement_recovery": fresh_gate,
                "recovered_from": str(paths["source_manifest"]),
                "recovered_output_path": str(paths["recovered_output"]),
                "recovery_source": "publication_commit_wal_current",
                "recovery_summary": str(paths["recovery_summary"]),
                "recovery_witness": str(paths["recovery_witness"]),
            }
        )
        _atomic_write_json(paths["recovered_manifest"], recovered_manifest)
        return witness, recovered_manifest
    except Exception:
        paths["recovered_manifest"].unlink(missing_ok=True)
        paths["recovery_witness"].unlink(missing_ok=True)
        raise


def recover(
    *,
    result_path: Path,
    checkpoint_path: Path,
    pending_snapshot_path: Path,
    manifest_path: Path | None,
    recovered_output_path: Path,
    summary_output_path: Path,
    paired_run_spec_path: Path | None = None,
    recovery_witness_output_path: Path | None = None,
    recovered_manifest_output_path: Path | None = None,
) -> dict[str, Any]:
    result_path = result_path.resolve()
    checkpoint_path = checkpoint_path.resolve()
    pending_snapshot_path = pending_snapshot_path.resolve()
    manifest_path = None if manifest_path is None else manifest_path.resolve()
    recovered_output_path = recovered_output_path.resolve()
    summary_output_path = summary_output_path.resolve()
    optional_witness_paths = (
        paired_run_spec_path,
        recovery_witness_output_path,
        recovered_manifest_output_path,
    )
    witness_publication_requested = any(optional_witness_paths)
    if witness_publication_requested and not all(optional_witness_paths):
        raise ValueError(
            "paired recovery publication requires run spec, witness output, and recovered manifest output"
        )
    if witness_publication_requested:
        paired_run_spec_path = paired_run_spec_path.resolve()  # type: ignore[union-attr]
        recovery_witness_output_path = recovery_witness_output_path.resolve()  # type: ignore[union-attr]
        recovered_manifest_output_path = recovered_manifest_output_path.resolve()  # type: ignore[union-attr]
        for stale_path in (
            recovery_witness_output_path,
            recovered_manifest_output_path,
        ):
            stale_path.unlink(missing_ok=True)
    final_rows = _load_json(result_path) if result_path.exists() else []
    if not isinstance(final_rows, list):
        raise ValueError(f"result JSON must be a list: {result_path}")

    checkpoint_rows, checkpoint_read_errors = _iter_jsonl(
        checkpoint_path,
        source="checkpoint",
    )
    completed_rows = [row for row in checkpoint_rows if row.get("status") == "completed"]
    failed_rows = [row for row in checkpoint_rows if row.get("status") == "failed"]

    pending_rows: list[dict[str, Any]] = []
    pending_read_errors: list[dict[str, Any]] = []
    if pending_snapshot_path.exists():
        try:
            pending_payload = _load_json(pending_snapshot_path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            pending_read_errors.append(
                {"source": "pending_snapshot", "reason": f"pending JSON 검증 실패: {exc}"}
            )
        else:
            if not isinstance(pending_payload, list):
                pending_read_errors.append(
                    {"source": "pending_snapshot", "reason": "pending payload가 list가 아닙니다"}
                )
            else:
                for row_number, row in enumerate(pending_payload, 1):
                    if isinstance(row, dict):
                        pending_rows.append(row)
                    else:
                        pending_read_errors.append(
                            {
                                "source": "pending_snapshot",
                                "row": row_number,
                                "reason": "pending 항목이 객체가 아닙니다",
                            }
                        )
    else:
        pending_read_errors.append(
            {"source": "pending_snapshot", "reason": "pending snapshot 파일이 없습니다"}
        )

    final_read_errors = [
        {"source": "final_result", "row": row_number, "reason": "final result 항목이 객체가 아닙니다"}
        for row_number, row in enumerate(final_rows, 1)
        if not isinstance(row, dict)
    ]
    source_artifact_errors = [
        *checkpoint_read_errors,
        *pending_read_errors,
        *final_read_errors,
    ]

    completed_rows_sorted = sorted(
        completed_rows,
        key=lambda row: (
            int(row.get("global_idx") or 0),
            int(row.get("_line_no") or 0),
        ),
    )
    recovered_rows = [
        row["result"]
        for row in completed_rows_sorted
        if isinstance(row.get("result"), dict)
    ]

    final_post_ids = [_canonical_post_id(row.get("post_id")) for row in final_rows if isinstance(row, dict)]
    checkpoint_post_ids = [_wrapper_post_id(row) for row in checkpoint_rows]
    pending_post_ids = [_wrapper_post_id(row) for row in pending_rows]
    duplicate_final_post_ids = _duplicate_values([pid for pid in final_post_ids if pid is not None])
    duplicate_checkpoint_post_ids = _duplicate_values([pid for pid in checkpoint_post_ids if pid is not None])
    duplicate_pending_post_ids = _duplicate_values([pid for pid in pending_post_ids if pid is not None])
    duplicate_checkpoint_global_idx = _duplicate_values(
        [idx for idx in (_global_idx(row.get("global_idx")) for row in checkpoint_rows) if idx is not None]
    )
    duplicate_pending_global_idx = _duplicate_values(
        [idx for idx in (_global_idx(row.get("global_idx")) for row in pending_rows) if idx is not None]
    )
    duplicate_rows_present = bool(
        duplicate_final_post_ids
        or duplicate_checkpoint_post_ids
        or duplicate_pending_post_ids
        or duplicate_checkpoint_global_idx
        or duplicate_pending_global_idx
    )

    final_ids = {
        _post_id_from_result(row) for row in final_rows if isinstance(row, dict)
    }
    checkpoint_ids = {_post_id_from_checkpoint(row) for row in completed_rows}
    pending_ids = {_post_id_from_pending(row) for row in pending_rows}
    final_ids.discard(None)
    checkpoint_ids.discard(None)
    pending_ids.discard(None)

    missing_from_final = sorted(int(pid) for pid in checkpoint_ids - final_ids)
    pending_not_in_final = sorted(int(pid) for pid in pending_ids - final_ids)
    checkpoint_missing_not_pending = sorted(int(pid) for pid in (checkpoint_ids - final_ids) - pending_ids)
    extra_in_final = sorted(int(pid) for pid in final_ids - checkpoint_ids)
    pending_not_in_checkpoint = sorted(int(pid) for pid in pending_ids - checkpoint_ids)

    manifest = _load_json(manifest_path) if manifest_path and manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        raise ValueError(f"manifest JSON must be an object: {manifest_path}")
    p2_enabled = _p2_enabled(manifest, checkpoint_rows, pending_rows)
    exact_once = (
        _p2_validation(
            manifest=manifest,
            manifest_path=manifest_path,
            result_path=result_path,
            checkpoint_rows=checkpoint_rows,
            checkpoint_read_errors=checkpoint_read_errors,
            pending_rows=pending_rows,
            pending_read_errors=pending_read_errors,
            final_rows=final_rows,
        )
        if p2_enabled
        else {
            "enabled": False,
            "exact_once_gate": "NOT_PROVABLE",
            "completed_subset_gate": "NOT_PROVABLE",
            "status": "NOT_PROVABLE",
            "reason": "legacy manifest에는 P2 durable receipt/journal 계약이 없습니다",
        }
    )
    canonical_wal_rows = exact_once.pop("_canonical_rows", None)
    p2_wal_v2 = bool(
        p2_enabled
        and exact_once.get("journal_mode") == "current"
        and isinstance(canonical_wal_rows, list)
    )
    canonical_wal_decision_ids = exact_once.pop("_canonical_wal_decision_ids", {})
    if not isinstance(canonical_wal_decision_ids, dict):
        canonical_wal_decision_ids = {}
    wal_path = _artifact_path_from_manifest(
        exact_once.get("journal_path"), manifest_path
    )
    wal_before = _wal_snapshot(wal_path)
    fresh_measurement_recovery = _validate_fresh_measurement_recovery(
        manifest=manifest,
        manifest_path=manifest_path,
        canonical_wal_decision_ids=canonical_wal_decision_ids,
        checkpoint_rows=checkpoint_rows,
    )
    wal_after = _wal_snapshot(wal_path)
    fresh_measurement_recovery["publication_wal_sha256_before"] = wal_before["sha256"]
    fresh_measurement_recovery["publication_wal_sha256_after"] = wal_after["sha256"]
    fresh_measurement_recovery["publication_wal_event_count_before"] = wal_before[
        "event_count"
    ]
    fresh_measurement_recovery["publication_wal_event_count_after"] = wal_after[
        "event_count"
    ]
    fresh_measurement_recovery["publication_wal_unchanged"] = bool(
        wal_before["sha256"] is not None
        and wal_before["event_count"] is not None
        and wal_before == wal_after
    )
    measurement_required = _fresh_measurement_required(manifest)
    if measurement_required and not fresh_measurement_recovery["publication_wal_unchanged"]:
        reasons = set(fresh_measurement_recovery.get("reason_codes") or [])
        reasons.add("PUBLICATION_WAL_CHANGED_DURING_RECOVERY")
        fresh_measurement_recovery.update(
            {
                "status": "NO-GO",
                "measurement_eligible": False,
                "actual_kpi_status": "NOT_ESTIMABLE",
                "recovery_action": "FULL_FRESH_ARM_RERUN_REQUIRED",
                "reason_codes": sorted(reasons),
            }
        )
    if p2_wal_v2:
        recovered_rows = canonical_wal_rows
    terminal_manifest_integrity = _validate_terminal_manifest_integrity(
        manifest=manifest,
        exact_once=exact_once,
        final_rows=final_rows,
        checkpoint_rows=checkpoint_rows,
        completed_rows=completed_rows,
        failed_rows=failed_rows,
        pending_rows=pending_rows,
    )
    exact_once["terminal_manifest_integrity"] = terminal_manifest_integrity
    p2_recovered_output_allowed = bool(
        not p2_enabled
        or (
            exact_once["completed_subset_gate"] == "GO"
            and (not p2_wal_v2 or bool(recovered_rows))
        )
    )
    recovered_output_written = False
    if p2_recovered_output_allowed:
        recovered_output_path.parent.mkdir(parents=True, exist_ok=True)
        recovered_output_path.write_text(
            json.dumps(recovered_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        recovered_output_written = True
    elif recovered_output_path.exists():
        # 명시된 output target에 이전 실행의 평문 결과가 남아 있으면 현재
        # NO-GO summary와 혼동될 수 있으므로 fail-closed로 제거한다.
        recovered_output_path.unlink()

    manifest_input_count = _nonnegative_int(manifest.get("input_post_count"))
    large_run_complete = bool(
        manifest_input_count
        and len(recovered_rows) == manifest_input_count
        and (p2_wal_v2 or not pending_rows)
        and (p2_wal_v2 or not failed_rows)
        and not source_artifact_errors
        and not duplicate_rows_present
        and (not p2_enabled or exact_once["exact_once_gate"] == "GO")
        and (
            not p2_wal_v2
            or (
                exact_once.get("publication_rows_complete") is True
                and exact_once.get("wal_error_hold_count") == 0
                and exact_once.get("secondary_wrapper_integrity") == "VALID"
                and exact_once.get("scope_provenance", {}).get("status") == "VALID"
                and exact_once.get("tail_repair_required") is False
                and exact_once.get("tail_repair_manifest_binding", {}).get(
                    "status"
                )
                == "VALID"
                and terminal_manifest_integrity["status"] == "VALID"
            )
        )
        and (
            not measurement_required
            or fresh_measurement_recovery["status"] == "GO"
        )
    )

    if (
        p2_wal_v2
        and exact_once.get("scope_provenance", {}).get("status") == "UNSAFE"
    ):
        integrity_classification = "wal_current_scope_provenance_unsafe"
    elif p2_wal_v2 and terminal_manifest_integrity["status"] == "UNSAFE":
        integrity_classification = "wal_current_terminal_manifest_unsafe"
    elif (
        source_artifact_errors
        or duplicate_rows_present
        or exact_once["status"] == "UNSAFE"
        or (
            p2_wal_v2
            and exact_once.get("secondary_wrapper_integrity") == "UNSAFE"
        )
        or (
            p2_wal_v2
            and exact_once.get("tail_repair_manifest_binding", {}).get("status")
            == "UNSAFE"
        )
    ):
        integrity_classification = "requires_manual_review"
    elif p2_wal_v2 and exact_once["exact_once_gate"] == "GO":
        if large_run_complete:
            integrity_classification = "wal_current_clean_completed_run"
        elif exact_once.get("tail_repair_required") is True:
            integrity_classification = (
                "wal_current_publication_rows_complete_repair_required"
            )
        elif (
            exact_once.get("scope_provenance", {}).get("status") != "VALID"
            or exact_once.get("tail_repair_manifest_binding", {}).get("status")
            != "VALID"
        ):
            integrity_classification = (
                "wal_current_publication_rows_complete_config_or_repair_not_provable"
            )
        elif terminal_manifest_integrity["status"] != "VALID":
            integrity_classification = (
                "wal_current_publication_rows_complete_terminal_incomplete"
            )
        else:
            integrity_classification = (
                "wal_current_publication_rows_complete_runtime_incomplete"
            )
    elif p2_wal_v2:
        integrity_classification = "wal_current_recoverable_completed_subset"
    elif not missing_from_final and not pending_not_in_final and not checkpoint_missing_not_pending and not extra_in_final:
        integrity_classification = "clean_completed_run"
    elif missing_from_final and missing_from_final == pending_not_in_final and not checkpoint_missing_not_pending:
        integrity_classification = "recoverable_pending_flush_gap"
    else:
        integrity_classification = "requires_manual_review"

    logical_publication_recovery_safe = bool(
        recovered_rows
        and (p2_wal_v2 or not failed_rows)
        and (p2_wal_v2 or not checkpoint_missing_not_pending)
        and (p2_wal_v2 or not pending_not_in_checkpoint)
        and (p2_wal_v2 or not extra_in_final)
        and (p2_wal_v2 or not source_artifact_errors)
        and (p2_wal_v2 or not duplicate_rows_present)
        and recovered_output_written
        and (
            not p2_enabled
            or exact_once["completed_subset_gate"] == "GO"
        )
    )
    summary = {
        "run_id": manifest.get("run_id"),
        "source_result_path": str(result_path),
        "source_checkpoint_path": str(checkpoint_path),
        "source_pending_snapshot_path": str(pending_snapshot_path),
        "requested_recovered_output_path": str(recovered_output_path),
        "recovered_output_path": str(recovered_output_path) if recovered_output_written else None,
        "recovered_output_written": recovered_output_written,
        "recovered_output_suppressed": not recovered_output_written,
        "recovered_output_suppressed_reason": (
            None
            if recovered_output_written
            else "P2 completed_subset_gate가 GO가 아니므로 평문 recovered JSON을 생성하지 않았습니다"
        ),
        "final_result_rows": len(final_rows),
        "checkpoint_rows": len(checkpoint_rows),
        "checkpoint_completed_rows": len(completed_rows),
        "checkpoint_failed_rows": len(failed_rows),
        "pending_snapshot_rows": len(pending_rows),
        "recovered_rows": len(recovered_rows),
        "recovery_source": (
            "publication_commit_wal_current"
            if p2_wal_v2
            else "checkpoint_completed_rows"
        ),
        "logical_publication_recovery": {
            "status": "GO" if logical_publication_recovery_safe else "NO-GO",
            "safe_to_use_as_completed_subset": logical_publication_recovery_safe,
            "authority": "publication_commit_wal" if p2_wal_v2 else "checkpoint_wrapper",
            "measurement_claim": "NOT_A_MEASUREMENT_CLAIM",
        },
        "fresh_measurement_recovery": fresh_measurement_recovery,
        "manifest": {
            "input_post_count": manifest.get("input_post_count"),
            "completed_count": manifest.get("completed_count"),
            "flushed_count": manifest.get("flushed_count"),
            "pending_count": manifest.get("pending_count"),
            "failed_count": manifest.get("failed_count"),
            "next_save_idx": manifest.get("next_save_idx"),
            "large_run_complete": manifest.get("large_run_complete"),
            "terminal_artifacts_finalized": manifest.get(
                "terminal_artifacts_finalized"
            ),
            "publication_commit_journal_schema": manifest.get(
                "publication_commit_journal_schema"
            ),
            "publication_commit_count": manifest.get("publication_commit_count"),
        },
        "missing_from_final_post_ids": missing_from_final,
        "pending_not_in_final_post_ids": pending_not_in_final,
        "checkpoint_missing_not_pending_post_ids": checkpoint_missing_not_pending,
        "pending_not_in_checkpoint_post_ids": pending_not_in_checkpoint,
        "extra_in_final_not_checkpoint_post_ids": extra_in_final,
        "duplicate_final_post_ids": duplicate_final_post_ids,
        "duplicate_checkpoint_post_ids": duplicate_checkpoint_post_ids,
        "duplicate_pending_post_ids": duplicate_pending_post_ids,
        "duplicate_checkpoint_global_idx": duplicate_checkpoint_global_idx,
        "duplicate_pending_global_idx": duplicate_pending_global_idx,
        "duplicate_rows_present": duplicate_rows_present,
        "source_artifact_errors": source_artifact_errors,
        "source_artifact_unsafe": bool(source_artifact_errors),
        "integrity_classification": integrity_classification,
        "exact_once": exact_once,
        "exact_once_gate": exact_once["exact_once_gate"],
        "exact_once_status": exact_once["status"],
        "scope_provenance": exact_once.get("scope_provenance"),
        "scope_provenance_gate": exact_once.get("scope_provenance_gate"),
        "release_attestation_status": exact_once.get(
            "release_attestation_status", "NOT_PROVABLE"
        ),
        "terminal_manifest_integrity": terminal_manifest_integrity,
        "publication_rows_complete": exact_once.get(
            "publication_rows_complete", False
        ),
        "terminal_artifacts_finalized": (
            manifest.get("terminal_artifacts_finalized") is True
        ),
        "wal_error_hold_count": exact_once.get("wal_error_hold_count"),
        "recovery_safe_to_use_as_completed_subset": bool(
            logical_publication_recovery_safe
            and (
                not measurement_required
                or fresh_measurement_recovery["status"] == "GO"
            )
        ),
        "large_run_complete": large_run_complete,
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
    }
    _atomic_write_json(summary_output_path, summary)
    if witness_publication_requested:
        assert paired_run_spec_path is not None
        assert recovery_witness_output_path is not None
        assert recovered_manifest_output_path is not None
        if (
            manifest_path is None
            or not measurement_required
            or fresh_measurement_recovery.get("status") != "GO"
            or not summary["recovery_safe_to_use_as_completed_subset"]
            or not summary["large_run_complete"]
            or not recovered_output_written
        ):
            return summary
        publish_paired_recovery_artifacts(
            paired_run_spec_path=paired_run_spec_path,
            source_manifest_path=manifest_path,
            source_checkpoint_path=checkpoint_path,
            source_pending_snapshot_path=pending_snapshot_path,
            recovery_summary_path=summary_output_path,
            recovered_output_path=recovered_output_path,
            recovery_witness_output_path=recovery_witness_output_path,
            recovered_manifest_output_path=recovered_manifest_output_path,
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recover completed expert_main rows from checkpoint JSONL without overwriting the original result.",
    )
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--pending-snapshot", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--recovered-output", required=True, type=Path)
    parser.add_argument("--summary-output", required=True, type=Path)
    parser.add_argument("--paired-run-spec", type=Path)
    parser.add_argument("--recovery-witness-output", type=Path)
    parser.add_argument("--recovered-manifest-output", type=Path)
    args = parser.parse_args()

    summary = recover(
        result_path=args.result,
        checkpoint_path=args.checkpoint,
        pending_snapshot_path=args.pending_snapshot,
        manifest_path=args.manifest,
        recovered_output_path=args.recovered_output,
        summary_output_path=args.summary_output,
        paired_run_spec_path=args.paired_run_spec,
        recovery_witness_output_path=args.recovery_witness_output,
        recovered_manifest_output_path=args.recovered_manifest_output,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
