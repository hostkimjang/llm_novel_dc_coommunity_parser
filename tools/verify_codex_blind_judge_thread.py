from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_codex_cli_trust_anchor import (  # noqa: E402
    EXPECTED_CODEX_EXE_SHA256,
    EXPECTED_MODEL_SLUG,
    EXPECTED_REASONING_EFFORT,
    PRODUCTION_EXECUTION_MODE,
    UNTRUSTED_EXECUTION_MODE,
    validate_direct_python_entrypoint,
    validate_trust_anchor,
)
import tools.run_codex_blind_adjudication as runner_dependency  # noqa: E402
from tools.run_codex_blind_adjudication import (  # noqa: E402
    ACTIVE_GOAL_ID,
    CONTINUATION_SOURCE_SESSION,
    MAX_FINAL_RESPONSE_BYTES,
    MAX_RAW_EVENTS_BYTES,
    MAX_SESSION_BUNDLE_BYTES,
    MAX_SESSION_FILES,
    MAX_STDERR_RETAINED_BYTES,
    MAX_TIMEOUT_SECONDS,
    PRIMARY_TRUST_BOUNDARY,
    RECEIPT_DIGEST_CONTRACT,
    RECEIPT_VERSION as PRIMARY_RECEIPT_VERSION,
    RUNNER_SECURITY_DEPENDENCY_PATHS,
    RUNNER_VERSION as PRIMARY_RUNNER_VERSION,
    SECURITY_DEPENDENCY_MANIFEST_VERSION,
    SECRET_PATTERNS,
    _copy_prefix_exclusive,
    _execute_injected_runner,
    _execute_production_streaming,
    _file_sha256_and_size,
    _is_confined_review_prefix,
    _json_bytes,
    _mark_read_only,
    _parse_raw_events,
    _prepare_isolated_environment,
    _redact_stderr,
    _sha256_bytes,
    _write_exclusive,
    build_security_dependency_manifest,
    capture_security_dependency_snapshot,
    receipt_payload_digest,
    validate_security_dependency_manifest,
    validate_session_member_paths,
)


REPORT_TYPE = "codex_blind_judge_thread_readback_receipt"
RECEIPT_VERSION = "codex-blind-thread-readback-v3"
VERIFIER_VERSION = "verify-codex-blind-judge-thread-v3"
TRUST_BOUNDARY = "signed_native_codex_cli_live_thread_resume"
VERIFIER_SECURITY_DEPENDENCY_PATHS = (
    "tools/run_codex_blind_adjudication.py",
    "tools/build_codex_cli_trust_anchor.py",
    "tools/build_adjusted_collateral_adjudication.py",
    "tools/build_adjusted_collateral_blind_packet.py",
)
REVIEWED_PRIMARY_RUNNER_SHA256 = (
    "116cd1cd40d4e44e9d1b9450cce1d659f1a92de1df5fbd26591322d4d0d3f9e2"
)
REVIEWED_NON_SELF_DEPENDENCY_SHA256 = {
    "tools/build_codex_cli_trust_anchor.py": (
        "72211eaf7a8d8a9d6c266e9d3bc08dd879a78e573ba32826272f28c658079a02"
    ),
    "tools/build_adjusted_collateral_blind_packet.py": (
        "363670296e396661be79927f44f1bc520d319741548bc236e5fd51916bf1c0c2"
    ),
}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _paths(prefix: Path) -> dict[str, Path]:
    base = str(prefix.resolve())
    return {
        "prompt": Path(base + ".prompt.txt"),
        "schema": Path(base + ".output_schema.json"),
        "raw_events": Path(base + ".raw_events.jsonl"),
        "final_response": Path(base + ".final_response.json"),
        "stderr": Path(base + ".stderr.txt"),
        "receipt": Path(base + ".receipt.json"),
    }


def _preflight(paths: dict[str, Path]) -> None:
    collisions = sorted(str(path) for path in paths.values() if path.exists())
    if collisions:
        raise FileExistsError("thread readback artifacts are immutable: " + ", ".join(collisions))


def build_readback_schema() -> dict[str, Any]:
    fields = {
        "thread_id": {"type": "string", "pattern": r"^[0-9a-f-]{36}$"},
        "challenge": {"type": "string", "minLength": 32, "maxLength": 256},
        "primary_receipt_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
        "primary_raw_events_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
        "primary_final_response_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
        "primary_verdicts_sha256": {"type": "string", "pattern": r"^[0-9a-f]{64}$"},
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": sorted(fields),
        "properties": fields,
    }


def build_readback_prompt(expected: dict[str, str]) -> bytes:
    payload = json.dumps(expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        "이 요청은 기존 blind adjudication thread의 live resume readback이다. "
        "도구, 파일, 네트워크 검색을 사용하지 말고 아래 JSON object를 값 하나도 바꾸지 말고 "
        "그대로 최종 JSON으로 반환하라. 설명이나 추가 필드는 금지한다.\n"
        + payload
        + "\n"
    ).encode("utf-8")


def _read_only(path: Path) -> bool:
    return path.is_file() and not (
        path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    )


def _load_primary(
    path: Path,
    *,
    production: bool,
    trust_binding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = path.resolve(strict=True)
    primary = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(primary, dict) or primary.get("report_type") != "codex_blind_judge_raw_receipt":
        raise ValueError("primary blind judge receipt type invalid")
    if production and (
        primary.get("gate") != "GO"
        or primary.get("status") != "SUCCEEDED"
        or primary.get("execution_mode") != PRODUCTION_EXECUTION_MODE
        or not _read_only(resolved)
    ):
        raise ValueError("primary blind judge receipt is not immutable production GO")
    if production and (
        primary.get("receipt_version") != PRIMARY_RECEIPT_VERSION
        or primary.get("runner_version") != PRIMARY_RUNNER_VERSION
        or primary.get("receipt_digest_contract") != RECEIPT_DIGEST_CONTRACT
        or primary.get("receipt_payload_sha256") != receipt_payload_digest(primary)
        or primary.get("cryptographic_service_attestation") is not False
        or primary.get("trust_boundary") != PRIMARY_TRUST_BOUNDARY
        or primary.get("thread_readback_required") is not True
    ):
        raise ValueError("primary blind judge receipt version/self-digest/trust boundary invalid")
    if production:
        runner_path = (ROOT / "tools/run_codex_blind_adjudication.py").resolve(strict=True)
        runner_sha256, runner_size = _file_sha256_and_size(runner_path)
        runner_artifact = primary.get("runner_artifact")
        if (
            not isinstance(runner_artifact, dict)
            or Path(str(runner_artifact.get("path") or "")).resolve() != runner_path
            or runner_artifact.get("size") != runner_size
            or runner_artifact.get("sha256_before") != runner_sha256
            or runner_artifact.get("sha256_after") != runner_sha256
            or runner_artifact.get("stable_during_execution") is not True
            or runner_sha256 != REVIEWED_PRIMARY_RUNNER_SHA256
        ):
            raise ValueError("primary blind judge runner pin/current bytes mismatch")
        dependency_rows = validate_security_dependency_manifest(
            primary.get("security_dependency_manifest"),
            RUNNER_SECURITY_DEPENDENCY_PATHS,
        )
        for row in dependency_rows:
            reviewed_sha256 = REVIEWED_NON_SELF_DEPENDENCY_SHA256.get(
                row["relative_path"]
            )
            if reviewed_sha256 is not None and row["sha256"] != reviewed_sha256:
                raise ValueError("primary local dependency reviewed SHA pin mismatch")
    thread_id = str(primary.get("codex_thread_id") or "")
    if not UUID_RE.fullmatch(thread_id):
        raise ValueError("primary blind judge thread id invalid")
    if primary.get("goal_id") != ACTIVE_GOAL_ID or primary.get(
        "continuation_source_session"
    ) != CONTINUATION_SOURCE_SESSION:
        raise ValueError("primary blind judge goal lineage mismatch")
    if production and primary.get("codex_cli_trust") != trust_binding:
        raise ValueError("primary/readback Codex CLI trust anchor mismatch")
    if production:
        isolation = primary.get("environment_isolation")
        relation = isolation.get("relation_contract") if isinstance(isolation, dict) else None
        policy = isolation.get("direct_service_policy") if isinstance(isolation, dict) else None
        if (
            not isinstance(relation, dict)
            or set(relation) != {
                "judge_cwd_parent_equals_isolated_home_parent",
                "codex_home_parent_equals_isolated_home",
            }
            or not all(value is True for value in relation.values())
            or not isinstance(policy, dict)
            or any(
                policy.get(key) is not False
                for key in (
                    "custom_endpoint_inherited",
                    "proxy_inherited",
                    "custom_ca_inherited",
                    "python_environment_inherited",
                )
            )
            or policy.get("auth_json_network_override_inherited") is not False
            or policy.get("auth_json_schema_allowlist_valid") is not True
        ):
            raise ValueError("primary blind judge environment isolation contract invalid")
    session = primary.get("session_bundle")
    if (
        not isinstance(session, dict)
        or session.get("thread_id") != thread_id
        or session.get("secrets_excluded") is not True
    ):
        raise ValueError("primary persisted session bundle receipt missing")
    bundle = Path(str(session.get("path") or "")).resolve(strict=True)
    bundle_sha256, bundle_size = _file_sha256_and_size(bundle)
    if (
        bundle_sha256 != session.get("bundle_sha256")
        or bundle_size != session.get("bundle_size")
        or bundle_size > MAX_SESSION_BUNDLE_BYTES
        or (production and not _read_only(bundle))
    ):
        raise ValueError("primary persisted session bundle hash/read-only mismatch")
    if production:
        artifacts = primary.get("artifacts")
        if (
            not isinstance(artifacts, dict)
            or Path(str(artifacts.get("receipt") or "")).resolve() != resolved
            or Path(str(artifacts.get("session_bundle") or "")).resolve() != bundle
        ):
            raise ValueError("primary session bundle artifact path mismatch")
        for artifact_key, receipt_key in (
            ("raw_events", "raw_events_jsonl_sha256"),
            ("final_response", "final_response_sha256"),
            ("verdicts", "delivered_verdicts_jsonl_sha256"),
        ):
            artifact_path = Path(str(artifacts.get(artifact_key) or "")).resolve(strict=True)
            if (
                _file_sha256_and_size(artifact_path)[0] != primary.get(receipt_key)
                or not _read_only(artifact_path)
            ):
                raise ValueError(f"primary artifact hash/read-only mismatch: {artifact_key}")
    primary_sha256, _ = _file_sha256_and_size(resolved)
    binding = {
        "primary_receipt_path": str(resolved),
        "primary_receipt_sha256": primary_sha256,
        "thread_id": thread_id,
        "primary_judge_run_id": primary.get("judge_run_id"),
        "primary_runner_run_id": primary.get("runner_run_id"),
        "primary_process_id": (primary.get("execution_process") or {}).get("process_id"),
        "primary_raw_events_sha256": primary.get("raw_events_jsonl_sha256"),
        "primary_final_response_sha256": primary.get("final_response_sha256"),
        "primary_verdicts_sha256": primary.get("delivered_verdicts_jsonl_sha256"),
        "session_bundle_path": str(bundle),
        "session_bundle_sha256": bundle_sha256,
        "session_files_sha256": session.get("files_sha256"),
    }
    for key in (
        "primary_raw_events_sha256",
        "primary_final_response_sha256",
        "primary_verdicts_sha256",
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", str(binding.get(key) or "")):
            raise ValueError(f"primary binding hash invalid: {key}")
    return primary, binding


def _restore_session_bundle(primary: dict[str, Any], codex_home: Path) -> dict[str, Any]:
    metadata = primary["session_bundle"]
    bundle = Path(metadata["path"])
    expected_rows = metadata.get("files")
    if not isinstance(expected_rows, list) or not expected_rows or len(expected_rows) > MAX_SESSION_FILES:
        raise ValueError("session bundle file manifest missing")
    if any(
        not isinstance(row, dict)
        or not isinstance(row.get("path"), str)
        or not isinstance(row.get("size"), int)
        or row["size"] < 0
        or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256") or ""))
        for row in expected_rows
    ):
        raise ValueError("session bundle file manifest row invalid")
    if sum(row["size"] for row in expected_rows) > MAX_SESSION_BUNDLE_BYTES:
        raise ValueError("session bundle uncompressed size exceeds cap")
    expected_by_path = {
        row["path"]: row for row in expected_rows
    }
    if len(expected_by_path) != len(expected_rows):
        raise ValueError("session bundle file manifest contains duplicate paths")
    if (
        metadata.get("report_type") != "codex_blind_judge_session_bundle_manifest"
        or metadata.get("version") != "codex-blind-session-bundle-v1"
        or metadata.get("file_count") != len(expected_rows)
        or metadata.get("total_uncompressed_bytes")
        != sum(row["size"] for row in expected_rows)
        or metadata.get("files_sha256") != _canonical_digest(expected_rows)
        or metadata.get("secrets_excluded") is not True
    ):
        raise ValueError("session bundle metadata integrity contract invalid")
    validated_paths = validate_session_member_paths(list(expected_by_path), codex_home)
    pending_writes: list[tuple[Path, bytes]] = []
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        normalized_names = {
            unicodedata.normalize("NFC", name).casefold() for name in names
        }
        if (
            len(names) != len(set(names))
            or len(names) != len(normalized_names)
            or set(names) != set(expected_by_path) | {"session_manifest.json"}
        ):
            raise ValueError("session bundle member set mismatch")
        manifest_info = archive.getinfo("session_manifest.json")
        if manifest_info.file_size > 1024 * 1024:
            raise ValueError("session bundle internal manifest exceeds cap")
        with archive.open("session_manifest.json") as manifest_handle:
            manifest_bytes = manifest_handle.read(1024 * 1024 + 1)
        if len(manifest_bytes) > 1024 * 1024:
            raise ValueError("session bundle internal manifest exceeds cap")
        manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
        manifest_projection = {
            key: metadata.get(key)
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
        if manifest != manifest_projection or manifest.get("secrets_excluded") is not True:
            raise ValueError("session bundle internal manifest mismatch")
        for name, _, destination in validated_paths:
            row = expected_by_path[name]
            if any(marker in name.casefold() for marker in ("auth", "token", "credential", "secret")):
                raise ValueError("session bundle secret-like member")
            info = archive.getinfo(name)
            if info.file_size != row.get("size"):
                raise ValueError("session bundle member declared size mismatch")
            with archive.open(name) as member_handle:
                payload = member_handle.read(row["size"] + 1)
            if len(payload) != row.get("size") or hashlib.sha256(payload).hexdigest() != row.get(
                "sha256"
            ):
                raise ValueError("session bundle member hash mismatch")
            decoded_payload = payload.decode("utf-8", errors="ignore")
            if any(pattern.search(decoded_payload) for pattern, _ in SECRET_PATTERNS):
                raise ValueError("session bundle member contains secret-like material")
            pending_writes.append((destination, payload))
    for destination, payload in pending_writes:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(destination, payload, read_only=False)
    return {
        "restored_file_count": len(expected_by_path),
        "restored_files_sha256": _canonical_digest(expected_rows),
        "secrets_restored": False,
    }


def _verify_unsealed(
    *,
    primary_receipt: Path,
    codex_cli_trust_anchor: Path,
    output_prefix: Path,
    timeout_seconds: int,
    process_runner: Callable[..., subprocess.CompletedProcess[Any]] | None,
    trust_process_runner: Callable[..., subprocess.CompletedProcess[Any]] | None,
    trust_signature_reader: Callable[[Path], dict[str, Any]] | None,
    trust_expected_exe_sha256: str,
    challenge: str | None,
    mark_artifacts_read_only: bool,
    allow_unconfined_test_output: bool,
    launcher_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    native_candidate = process_runner is None
    dependency_snapshot_before = capture_security_dependency_snapshot(
        VERIFIER_SECURITY_DEPENDENCY_PATHS
    )
    if timeout_seconds <= 0 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError("thread readback timeout invalid")
    confined = _is_confined_review_prefix(output_prefix)
    if not confined and not allow_unconfined_test_output:
        raise ValueError("thread readback output must be confined to out/.../review")
    native_candidate_contract = (
        process_runner is None
        and trust_process_runner is None
        and trust_signature_reader is None
        and trust_expected_exe_sha256 == EXPECTED_CODEX_EXE_SHA256
        and mark_artifacts_read_only
        and confined
        and not allow_unconfined_test_output
        and challenge is None
        and isinstance(launcher_evidence, dict)
    )
    if native_candidate and not native_candidate_contract:
        raise ValueError("thread readback native candidate contract is not satisfied")
    if not native_candidate and launcher_evidence is not None:
        raise ValueError("thread readback launcher evidence forbidden for untrusted execution")
    paths = _paths(output_prefix)
    _preflight(paths)
    if native_candidate:
        # This consumer-grade preflight is intentionally the last operation before
        # any output write, temp environment creation, session restore, or Codex
        # execution becomes reachable.
        from tools.build_adjusted_collateral_adjudication import (
            preflight_raw_codex_judge_receipt_for_readback,
        )

        validated_primary = preflight_raw_codex_judge_receipt_for_readback(
            raw_judge_receipt=primary_receipt,
            codex_cli_trust_anchor=codex_cli_trust_anchor,
        )
        primary = validated_primary["receipt"]
        trust = validated_primary["current_cli_trust"]
        binding = validated_primary["binding"]
    else:
        trust_kwargs: dict[str, Any] = {
            "production": False,
            "expected_exe_sha256": trust_expected_exe_sha256,
        }
        if trust_process_runner is not None:
            trust_kwargs["process_runner"] = trust_process_runner
        if trust_signature_reader is not None:
            trust_kwargs["signature_reader"] = trust_signature_reader
        trust = validate_trust_anchor(codex_cli_trust_anchor, **trust_kwargs)
        primary, binding = _load_primary(
            primary_receipt,
            production=False,
            trust_binding=trust,
        )
    challenge_value = challenge or secrets.token_urlsafe(48)
    if len(challenge_value) < 32:
        raise ValueError("thread readback challenge too short")
    expected = {
        "thread_id": binding["thread_id"],
        "challenge": challenge_value,
        "primary_receipt_sha256": binding["primary_receipt_sha256"],
        "primary_raw_events_sha256": binding["primary_raw_events_sha256"],
        "primary_final_response_sha256": binding["primary_final_response_sha256"],
        "primary_verdicts_sha256": binding["primary_verdicts_sha256"],
    }
    prompt = build_readback_prompt(expected)
    schema = build_readback_schema()
    schema_bytes = _json_bytes(schema, pretty=True)
    _write_exclusive(paths["prompt"], prompt, read_only=mark_artifacts_read_only)
    _write_exclusive(paths["schema"], schema_bytes, read_only=mark_artifacts_read_only)
    verifier_path = Path(__file__).resolve()
    verifier_sha256_before, verifier_size = _file_sha256_and_size(verifier_path)
    runner_dependency_path = Path(runner_dependency.__file__).resolve(strict=True)
    runner_dependency_sha256_before, runner_dependency_size = _file_sha256_and_size(
        runner_dependency_path
    )
    started_at = _utc_now()
    readback_run_id = f"codex-thread-readback-{uuid.uuid4()}"
    issues: list[str] = []
    raw_events: list[dict[str, Any]] = []
    raw_final: Any | None = None
    final_payload: Any | None = None
    thread_id: str | None = None
    with tempfile.TemporaryDirectory(prefix="codex-thread-readback-") as tmp_name:
        tmp = Path(tmp_name)
        cwd = tmp / "readback-cwd"
        cwd.mkdir()
        env, isolation = _prepare_isolated_environment(tmp, require_auth=native_candidate)
        isolation["judge_cwd"] = str(cwd)
        isolation["relation_contract"] = {
            "judge_cwd_parent_equals_isolated_home_parent": (
                cwd.parent == Path(isolation["home"]).parent
            ),
            "codex_home_parent_equals_isolated_home": (
                Path(isolation["codex_home"]).parent == Path(isolation["home"])
            ),
        }
        direct_policy = isolation.get("direct_service_policy")
        if (
            not all(isolation["relation_contract"].values())
            or not isinstance(direct_policy, dict)
            or any(
                direct_policy.get(key) is not False
                for key in (
                    "custom_endpoint_inherited",
                    "proxy_inherited",
                    "custom_ca_inherited",
                    "python_environment_inherited",
                    "auth_json_network_override_inherited",
                )
            )
            or (
                native_candidate
                and direct_policy.get("auth_json_schema_allowlist_valid") is not True
            )
        ):
            issues.append("readback_environment_isolation_contract_invalid")
        restore = _restore_session_bundle(primary, Path(isolation["codex_home"]))
        raw_stage = tmp / "raw.jsonl"
        stderr_stage = tmp / "stderr.bin"
        final_stage = tmp / "final.json"
        executable = str((trust.get("codex_cli") or {}).get("executable_path") or "")
        command = [
            executable,
            "exec",
            "--sandbox",
            "read-only",
            "resume",
            "-c",
            f'model_reasoning_effort="{EXPECTED_REASONING_EFFORT}"',
            "-m",
            EXPECTED_MODEL_SLUG,
            "--json",
            "--output-schema",
            str(paths["schema"]),
            "-o",
            str(final_stage),
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            binding["thread_id"],
            "-",
        ]
        if native_candidate:
            execution = _execute_production_streaming(
                command=command,
                prompt_bytes=prompt,
                raw_stage=raw_stage,
                stderr_stage=stderr_stage,
                final_stage=final_stage,
                timeout_seconds=timeout_seconds,
                env=env,
                cwd=cwd,
            )
        else:
            if process_runner is None:
                raise ValueError("untrusted thread readback requires injected process runner")
            execution = _execute_injected_runner(
                process_runner,
                command=command,
                prompt_bytes=prompt,
                raw_stage=raw_stage,
                stderr_stage=stderr_stage,
                timeout_seconds=timeout_seconds,
                env=env,
                cwd=cwd,
            )
        if execution.get("exit_code") != 0:
            issues.append(f"readback_exit_nonzero:{execution.get('exit_code')}")
        if execution.get("timed_out") is True or execution.get("execution_error"):
            issues.append("readback_execution_failed")
        if any(execution.get(f"{name}_limit_exceeded") for name in ("stdout", "stderr", "final")):
            issues.append("readback_stream_limit_exceeded")
        _copy_prefix_exclusive(
            raw_stage,
            paths["raw_events"],
            limit=MAX_RAW_EVENTS_BYTES,
            read_only=mark_artifacts_read_only,
        )
        raw_sha256, raw_size = _file_sha256_and_size(paths["raw_events"])
        raw_events, event_issues, thread_id, raw_final = _parse_raw_events(
            paths["raw_events"]
        )
        issues.extend(event_issues)
        if thread_id != binding["thread_id"]:
            issues.append("readback_thread_id_mismatch")
        if final_stage.is_file():
            _copy_prefix_exclusive(
                final_stage,
                paths["final_response"],
                limit=MAX_FINAL_RESPONSE_BYTES,
                read_only=mark_artifacts_read_only,
            )
        else:
            _write_exclusive(paths["final_response"], b"", read_only=mark_artifacts_read_only)
            issues.append("readback_final_response_missing")
        final_sha256, final_size = _file_sha256_and_size(paths["final_response"])
        if final_size:
            try:
                final_payload = json.loads(paths["final_response"].read_text(encoding="utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                issues.append("readback_final_response_invalid_json")
        if final_payload != expected or raw_final != expected:
            issues.append("readback_challenge_or_primary_binding_mismatch")
        stderr_sha256, stderr_size = _file_sha256_and_size(stderr_stage)
        with stderr_stage.open("rb") as handle:
            stderr_prefix = handle.read(MAX_STDERR_RETAINED_BYTES + 1)
        stderr_payload, stderr_truncated = _redact_stderr(
            stderr_prefix,
            raw_size=int(execution.get("stderr_observed_bytes") or stderr_size),
            limit=MAX_STDERR_RETAINED_BYTES,
        )
        _write_exclusive(paths["stderr"], stderr_payload, read_only=mark_artifacts_read_only)
    verifier_sha256_after, _ = _file_sha256_and_size(verifier_path)
    if verifier_sha256_after != verifier_sha256_before:
        issues.append("thread_verifier_changed_during_execution")
    runner_dependency_sha256_after, _ = _file_sha256_and_size(runner_dependency_path)
    if runner_dependency_sha256_after != runner_dependency_sha256_before:
        issues.append("thread_verifier_runner_dependency_changed_during_execution")
    dependency_snapshot_after = capture_security_dependency_snapshot(
        VERIFIER_SECURITY_DEPENDENCY_PATHS
    )
    security_dependency_manifest = build_security_dependency_manifest(
        dependency_snapshot_before,
        dependency_snapshot_after,
    )
    if (
        security_dependency_manifest.get("manifest_version")
        != SECURITY_DEPENDENCY_MANIFEST_VERSION
        or security_dependency_manifest.get("stable_during_execution") is not True
    ):
        issues.append("thread_verifier_local_security_dependency_changed")
    if execution.get("process_id") == binding.get("primary_process_id") and execution.get(
        "process_id"
    ) is not None:
        issues.append("readback_process_must_differ_from_primary")
    semantic_success = not issues
    gate = (
        "UNSEALED_NATIVE_CANDIDATE"
        if semantic_success and native_candidate
        else (UNTRUSTED_EXECUTION_MODE if semantic_success else "NO_GO")
    )
    status = (
        "SUCCEEDED_UNSEALED"
        if gate == "UNSEALED_NATIVE_CANDIDATE"
        else ("SUCCEEDED_UNTRUSTED" if gate == UNTRUSTED_EXECUTION_MODE else "FAILED")
    )
    finished_at = _utc_now()
    receipt = {
        "report_type": REPORT_TYPE,
        "receipt_version": RECEIPT_VERSION,
        "verifier_version": VERIFIER_VERSION,
        "gate": gate,
        "status": status,
        "execution_mode": (
            PRODUCTION_EXECUTION_MODE if native_candidate else UNTRUSTED_EXECUTION_MODE
        ),
        "provider": "codex",
        "model": EXPECTED_MODEL_SLUG,
        "reasoning_effort": EXPECTED_REASONING_EFFORT,
        "goal_id": ACTIVE_GOAL_ID,
        "continuation_source_session": CONTINUATION_SOURCE_SESSION,
        "codex_thread_id": binding["thread_id"],
        "readback_run_id": readback_run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": execution.get("exit_code"),
        "timed_out": execution.get("timed_out") is True,
        "execution_error": execution.get("execution_error"),
        "challenge": challenge_value,
        "challenge_sha256": hashlib.sha256(challenge_value.encode()).hexdigest(),
        "primary_binding": binding,
        "codex_cli_trust": trust,
        "launcher_process": launcher_evidence,
        "execution_process": {
            key: execution.get(key)
            for key in (
                "process_id",
                "parent_process_id",
                "process_image_path",
                "command_sha256",
            )
        },
        "verifier_artifact": {
            "path": str(verifier_path),
            "size": verifier_size,
            "sha256_before": verifier_sha256_before,
            "sha256_after": verifier_sha256_after,
            "stable_during_execution": verifier_sha256_before == verifier_sha256_after,
        },
        "runner_dependency_artifact": {
            "path": str(runner_dependency_path),
            "size": runner_dependency_size,
            "sha256_before": runner_dependency_sha256_before,
            "sha256_after": runner_dependency_sha256_after,
            "stable_during_execution": (
                runner_dependency_sha256_before == runner_dependency_sha256_after
            ),
        },
        "security_dependency_manifest": security_dependency_manifest,
        "environment_isolation": isolation,
        "session_restore": restore,
        "command": command,
        "prompt_sha256": _sha256_bytes(prompt),
        "schema_sha256": _sha256_bytes(schema_bytes),
        "raw_events_jsonl_sha256": raw_sha256,
        "raw_events_byte_count": raw_size,
        "raw_event_count": len(raw_events),
        "final_response_sha256": final_sha256,
        "final_response_byte_count": final_size,
        "final_response_payload_sha256": (
            _canonical_digest(final_payload) if final_payload is not None else None
        ),
        "artifacts": {key: str(path) for key, path in paths.items()},
        "stderr": {
            "raw_sha256": stderr_sha256,
            "raw_byte_count": stderr_size,
            "retained_redacted_sha256": _file_sha256_and_size(paths["stderr"])[0],
            "truncated": stderr_truncated,
        },
        "validation_issues": issues,
        "artifact_write_contract": {
            "exclusive_create_no_overwrite": True,
            "read_only_after_create": mark_artifacts_read_only,
            "output_prefix_confined_to_repo_out_review": confined,
        },
        "receipt_digest_contract": RECEIPT_DIGEST_CONTRACT,
        "cryptographic_service_attestation": False,
        "trust_boundary": TRUST_BOUNDARY,
    }
    return {
        "receipt": receipt,
        "paths": paths,
        "semantic_success": semantic_success,
        "native_candidate": native_candidate,
        "mark_artifacts_read_only": mark_artifacts_read_only,
    }


def _verify_core(
    *,
    primary_receipt: Path,
    codex_cli_trust_anchor: Path,
    output_prefix: Path,
    timeout_seconds: int,
    process_runner: Callable[..., subprocess.CompletedProcess[Any]],
    trust_process_runner: Callable[..., subprocess.CompletedProcess[Any]] | None,
    trust_signature_reader: Callable[[Path], dict[str, Any]] | None,
    trust_expected_exe_sha256: str,
    challenge: str,
    mark_artifacts_read_only: bool,
    allow_unconfined_test_output: bool,
) -> dict[str, Any]:
    """Imported test core. It always seals as UNIT_TEST_UNTRUSTED or NO_GO."""
    unsealed = _verify_unsealed(
        primary_receipt=primary_receipt,
        codex_cli_trust_anchor=codex_cli_trust_anchor,
        output_prefix=output_prefix,
        timeout_seconds=timeout_seconds,
        process_runner=process_runner,
        trust_process_runner=trust_process_runner,
        trust_signature_reader=trust_signature_reader,
        trust_expected_exe_sha256=trust_expected_exe_sha256,
        challenge=challenge,
        mark_artifacts_read_only=mark_artifacts_read_only,
        allow_unconfined_test_output=allow_unconfined_test_output,
        launcher_evidence=None,
    )
    receipt = unsealed["receipt"]
    receipt["gate"] = (
        UNTRUSTED_EXECUTION_MODE if unsealed.get("semantic_success") is True else "NO_GO"
    )
    receipt["status"] = (
        "SUCCEEDED_UNTRUSTED" if unsealed.get("semantic_success") is True else "FAILED"
    )
    receipt["execution_mode"] = UNTRUSTED_EXECUTION_MODE
    receipt["launcher_process"] = None
    receipt["receipt_payload_sha256"] = receipt_payload_digest(receipt)
    _write_exclusive(
        unsealed["paths"]["receipt"],
        _json_bytes(receipt, pretty=True),
        read_only=mark_artifacts_read_only,
    )
    return receipt


def verify_thread_readback(
    *,
    primary_receipt: Path,
    codex_cli_trust_anchor: Path,
    output_prefix: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[Any]],
    trust_process_runner: Callable[..., subprocess.CompletedProcess[Any]] | None = None,
    trust_signature_reader: Callable[[Path], dict[str, Any]] | None = None,
    trust_expected_exe_sha256: str = EXPECTED_CODEX_EXE_SHA256,
    challenge: str,
    timeout_seconds: int = 600,
    mark_artifacts_read_only: bool = False,
    allow_unconfined_test_output: bool = False,
) -> dict[str, Any]:
    return _verify_core(
        primary_receipt=primary_receipt,
        codex_cli_trust_anchor=codex_cli_trust_anchor,
        output_prefix=output_prefix,
        timeout_seconds=timeout_seconds,
        process_runner=process_runner,
        trust_process_runner=trust_process_runner,
        trust_signature_reader=trust_signature_reader,
        trust_expected_exe_sha256=trust_expected_exe_sha256,
        challenge=challenge,
        mark_artifacts_read_only=mark_artifacts_read_only,
        allow_unconfined_test_output=allow_unconfined_test_output,
    )


def _assert_child_context() -> dict[str, Any]:
    path = Path(__file__).resolve()
    if __name__ != "__main__" or sys.flags.isolated != 1 or Path(sys.argv[0]).resolve() != path:
        raise RuntimeError("thread verifier production requires direct isolated CLI child")
    challenge = os.environ.pop("CODEX_THREAD_VERIFY_LAUNCH_CHALLENGE", "")
    parent = os.environ.pop("CODEX_THREAD_VERIFY_PARENT_PID", "")
    if not re.fullmatch(r"[0-9a-f]{64}", challenge) or not parent.isdigit() or int(parent) != os.getppid():
        raise RuntimeError("thread verifier launcher evidence invalid")
    interpreter = Path(sys.executable).resolve(strict=True)
    interpreter_sha, interpreter_size = _file_sha256_and_size(interpreter)
    return {
        "execution_boundary": "isolated_python_cli_child",
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "process_image_path": str(interpreter),
        "process_image_sha256": interpreter_sha,
        "process_image_size": interpreter_size,
        "verifier_path": str(path),
        "verifier_sha256": _file_sha256_and_size(path)[0],
        "isolated_python": True,
        "argv_sha256": _canonical_digest(sys.argv),
        "launcher_challenge_sha256": hashlib.sha256(challenge.encode()).hexdigest(),
        "cryptographic_local_process_attestation": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a blind judge thread by signed native resume readback.")
    parser.add_argument("--primary-receipt", required=True, type=Path)
    parser.add_argument("--codex-cli-trust-anchor", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--_production-child", action="store_true", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    script_path = Path(__file__).resolve()
    original_argv = [str(value) for value in getattr(sys, "orig_argv", [])]
    if any("runpy" in frame.filename.casefold() for frame in inspect.stack()):
        raise RuntimeError("thread verifier main cannot be invoked through runpy")
    if __name__ != "__main__" or Path(sys.argv[0]).resolve() != script_path:
        raise RuntimeError("thread verifier main cannot be imported")
    entrypoint = validate_direct_python_entrypoint(original_argv, script_path)
    args = _parser().parse_args()
    if bool(args._production_child) != bool(entrypoint["isolated_flag"]):
        raise RuntimeError("thread verifier outer/isolated-child entrypoint shape mismatch")
    if not args._production_child:
        challenge = secrets.token_hex(32)
        command = [
            str(Path(sys.executable).resolve()),
            "-I",
            str(Path(__file__).resolve()),
            "--_production-child",
            "--primary-receipt",
            str(args.primary_receipt.resolve()),
            "--codex-cli-trust-anchor",
            str(args.codex_cli_trust_anchor.resolve()),
            "--output-prefix",
            str(args.output_prefix.resolve()),
            "--timeout-seconds",
            str(args.timeout_seconds),
        ]
        env = {
            key: os.environ[key]
            for key in (
                "SystemRoot",
                "WINDIR",
                "COMSPEC",
                "TEMP",
                "TMP",
                "OPENAI_API_KEY",
                "CODEX_API_KEY",
                "OPENAI_ORG_ID",
                "OPENAI_PROJECT_ID",
            )
            if os.environ.get(key)
        }
        env["CODEX_BLIND_AUTH_SOURCE"] = str(
            Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).resolve()
        )
        env["CODEX_THREAD_VERIFY_LAUNCH_CHALLENGE"] = challenge
        env["CODEX_THREAD_VERIFY_PARENT_PID"] = str(os.getpid())
        return int(subprocess.run(command, env=env, check=False).returncode)
    try:
        if sys.flags.isolated != 1 or original_argv.count("--_production-child") != 1:
            raise RuntimeError("thread verifier requires one direct isolated CLI child flag")
        launch_challenge = os.environ.pop("CODEX_THREAD_VERIFY_LAUNCH_CHALLENGE", "")
        parent_text = os.environ.pop("CODEX_THREAD_VERIFY_PARENT_PID", "")
        if not re.fullmatch(r"[0-9a-f]{64}", launch_challenge):
            raise RuntimeError("thread verifier launcher challenge invalid")
        if not parent_text.isdigit() or int(parent_text) != os.getppid():
            raise RuntimeError("thread verifier launcher parent PID mismatch")
        interpreter = Path(sys.executable).resolve(strict=True)
        interpreter_sha, interpreter_size = _file_sha256_and_size(interpreter)
        launcher_evidence = {
            "execution_boundary": "isolated_python_cli_child",
            "pid": os.getpid(),
            "parent_pid": os.getppid(),
            "process_image_path": str(interpreter),
            "process_image_sha256": interpreter_sha,
            "process_image_size": interpreter_size,
            "verifier_path": str(script_path),
            "verifier_sha256": _file_sha256_and_size(script_path)[0],
            "isolated_python": True,
            "argv_sha256": _canonical_digest(sys.argv),
            "original_argv_sha256": _canonical_digest(original_argv),
            "launcher_challenge_sha256": hashlib.sha256(
                launch_challenge.encode()
            ).hexdigest(),
            "closure_bound_production_seal": True,
            "cryptographic_local_process_attestation": False,
        }
        unsealed = _verify_unsealed(
            primary_receipt=args.primary_receipt,
            codex_cli_trust_anchor=args.codex_cli_trust_anchor,
            output_prefix=args.output_prefix,
            timeout_seconds=args.timeout_seconds,
            process_runner=None,
            trust_process_runner=None,
            trust_signature_reader=None,
            trust_expected_exe_sha256=EXPECTED_CODEX_EXE_SHA256,
            challenge=None,
            mark_artifacts_read_only=True,
            allow_unconfined_test_output=False,
            launcher_evidence=launcher_evidence,
        )
        production_seal = object()

        def seal_native_candidate(candidate: dict[str, Any], seal: object) -> dict[str, Any]:
            if seal is not production_seal or candidate.get("native_candidate") is not True:
                raise RuntimeError("thread readback production seal is not closure-authorized")
            receipt = candidate["receipt"]
            if receipt.get("gate") == "UNSEALED_NATIVE_CANDIDATE" and candidate.get(
                "semantic_success"
            ) is True:
                receipt["gate"] = "GO"
                receipt["status"] = "SUCCEEDED"
            else:
                receipt["gate"] = "NO_GO"
                receipt["status"] = "FAILED"
            receipt["receipt_payload_sha256"] = receipt_payload_digest(receipt)
            _write_exclusive(
                candidate["paths"]["receipt"],
                _json_bytes(receipt, pretty=True),
                read_only=True,
            )
            return receipt

        receipt = seal_native_candidate(unsealed, production_seal)
    except Exception as exc:
        print(f"thread readback verifier failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(str(_paths(args.output_prefix)["receipt"]))
    return 0 if receipt.get("gate") == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
