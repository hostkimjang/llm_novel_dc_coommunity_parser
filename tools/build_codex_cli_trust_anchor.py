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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
REPORT_TYPE = "codex_cli_native_trust_anchor"
ANCHOR_VERSION = "codex-cli-native-trust-v1"
PRODUCTION_EXECUTION_MODE = "subprocess_production"
UNTRUSTED_EXECUTION_MODE = "UNIT_TEST_UNTRUSTED"
EXPECTED_CODEX_EXE_SHA256 = "2b3c18d9393ed794531ae3da13f43a6de3bcd91dc577222bd31a17c59f7de0aa"
EXPECTED_SIGNER_SUBJECT = (
    'CN="OpenAI OpCo, LLC", O="OpenAI OpCo, LLC", '
    "L=San Francisco, S=California, C=US"
)
EXPECTED_SIGNER_THUMBPRINT = "9D047AAFEB28C19CBBCAB88596E89524D39F3DFF"
EXPECTED_CLI_VERSION = "codex-cli 0.144.0"
EXPECTED_MODEL_SLUG = "gpt-5.6-sol"
EXPECTED_REASONING_EFFORT = "high"
EXPECTED_MODEL_PROJECTION = {
    "slug": "gpt-5.6-sol",
    "display_name": "GPT-5.6-Sol",
    "default_reasoning_level": "low",
    "supported_reasoning_efforts": ["low", "medium", "high", "xhigh", "max", "ultra"],
    "visibility": "list",
    "supported_in_api": True,
    "context_window": 372000,
    "effective_context_window_percent": 95,
}
MAX_VERSION_OUTPUT_BYTES = 4096
MAX_MODEL_CATALOG_BYTES = 8 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_direct_python_entrypoint(
    original_argv: list[str],
    script_path: Path,
) -> dict[str, Any]:
    """Allow only `python script` or `python -I script` before app arguments."""
    if len(original_argv) < 2:
        raise RuntimeError("direct Python entrypoint argv is incomplete")
    interpreter = Path(original_argv[0]).resolve()
    allowed_interpreters = {
        Path(sys.executable).resolve(),
        Path(getattr(sys, "_base_executable", sys.executable)).resolve(),
    }
    if interpreter not in allowed_interpreters:
        raise RuntimeError("direct Python entrypoint interpreter mismatch")
    if original_argv[1] == "-I":
        script_index = 2
        isolated_flag = True
    else:
        script_index = 1
        isolated_flag = False
    if len(original_argv) <= script_index:
        raise RuntimeError("direct Python entrypoint script token is missing")
    if original_argv[script_index] in {"-c", "-m", "-"}:
        raise RuntimeError("direct Python entrypoint code/module/stdin mode is forbidden")
    if Path(original_argv[script_index]).resolve() != script_path.resolve():
        raise RuntimeError("direct Python entrypoint has an unknown or extra interpreter flag")
    expected_isolated_count = 1 if isolated_flag else 0
    if original_argv.count("-I") != expected_isolated_count:
        raise RuntimeError("direct Python entrypoint -I flag is duplicated or misplaced")
    return {
        "isolated_flag": isolated_flag,
        "script_index": script_index,
        "application_argv": original_argv[script_index + 1 :],
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mark_read_only(path: Path) -> None:
    path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def write_json_exclusive(path: Path, payload: dict[str, Any], *, read_only: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    encoded = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    if read_only:
        _mark_read_only(path)


def _is_under_review_output(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to((ROOT / "out").resolve())
    except ValueError:
        return False
    return "review" in {part.casefold() for part in relative.parent.parts}


def _validate_native_executable_path(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("codex executable path must be absolute")
    resolved = path.resolve(strict=True)
    if resolved.name.casefold() != "codex.exe" or resolved.suffix.casefold() != ".exe":
        raise ValueError("codex executable must be the native codex.exe, not a PATH shim")
    layout = [part.casefold() for part in resolved.parts]
    required_tail = [
        "node_modules",
        "@openai",
        "codex-win32-x64",
        "vendor",
        "x86_64-pc-windows-msvc",
        "bin",
        "codex.exe",
    ]
    cursor = 0
    for expected in required_tail:
        try:
            cursor = layout.index(expected, cursor) + 1
        except ValueError as exc:
            raise ValueError("codex executable is not in the signed OpenAI vendor layout") from exc
    attributes = getattr(resolved.stat(), "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if resolved.is_symlink() or attributes & reparse_flag:
        raise ValueError("codex executable must not be a symlink or reparse point")
    return resolved


def _minimal_probe_env() -> dict[str, str]:
    allowed = ("SystemRoot", "WINDIR", "COMSPEC", "TEMP", "TMP")
    return {key: os.environ[key] for key in allowed if os.environ.get(key)}


def query_authenticode(path: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("production Authenticode validation requires Windows")
    system_root = Path(os.environ.get("SystemRoot") or r"C:\Windows")
    powershell = (
        system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    ).resolve(strict=True)
    script = r"""
$signature = Get-AuthenticodeSignature -LiteralPath $env:CODEX_TRUST_TARGET
$certificate = $signature.SignerCertificate
[pscustomobject]@{
  status = $signature.Status.ToString()
  status_message = $signature.StatusMessage
  signature_type = $signature.SignatureType.ToString()
  signer_subject = if ($certificate) { $certificate.Subject } else { $null }
  signer_thumbprint = if ($certificate) { $certificate.Thumbprint } else { $null }
  signer_issuer = if ($certificate) { $certificate.Issuer } else { $null }
  signer_serial_number = if ($certificate) { $certificate.SerialNumber } else { $null }
  signer_not_before = if ($certificate) { $certificate.NotBefore.ToUniversalTime().ToString('o') } else { $null }
  signer_not_after = if ($certificate) { $certificate.NotAfter.ToUniversalTime().ToString('o') } else { $null }
} | ConvertTo-Json -Compress
"""
    env = _minimal_probe_env()
    env["CODEX_TRUST_TARGET"] = str(path)
    result = subprocess.run(
        [
            str(powershell),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        env=env,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Authenticode probe failed with exit {result.returncode}")
    if len(result.stdout) > 64 * 1024:
        raise RuntimeError("Authenticode probe output exceeded cap")
    payload = json.loads(result.stdout.decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise RuntimeError("Authenticode probe returned a non-object")
    return payload


def _run_probe(
    command: list[str],
    *,
    max_stdout_bytes: int,
    process_runner: Callable[..., subprocess.CompletedProcess[Any]],
) -> bytes:
    with tempfile.TemporaryDirectory(prefix="codex-cli-trust-probe-") as tmp_name:
        isolated = Path(tmp_name)
        codex_home = isolated / ".codex"
        codex_home.mkdir()
        env = _minimal_probe_env()
        env.update(
            {
                "CODEX_HOME": str(codex_home),
                "HOME": str(isolated),
                "USERPROFILE": str(isolated),
                "APPDATA": str(isolated / "appdata"),
                "LOCALAPPDATA": str(isolated / "localappdata"),
                "TEMP": str(isolated),
                "TMP": str(isolated),
            }
        )
        result = process_runner(
            command,
            input=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=str(isolated),
            timeout=60,
            check=False,
        )
    stdout = result.stdout if isinstance(result.stdout, bytes) else str(result.stdout or "").encode()
    stderr = result.stderr if isinstance(result.stderr, bytes) else str(result.stderr or "").encode()
    if result.returncode != 0:
        raise RuntimeError(
            f"native Codex probe failed with exit {result.returncode}; stderr_sha256="
            f"{hashlib.sha256(stderr).hexdigest()}"
        )
    if len(stdout) > max_stdout_bytes:
        raise RuntimeError("native Codex probe output exceeded cap")
    return stdout


def _model_projection(model: dict[str, Any]) -> dict[str, Any]:
    levels = model.get("supported_reasoning_levels")
    efforts = (
        [str(row.get("effort")) for row in levels if isinstance(row, dict)]
        if isinstance(levels, list)
        else []
    )
    return {
        "slug": model.get("slug"),
        "display_name": model.get("display_name"),
        "default_reasoning_level": model.get("default_reasoning_level"),
        "supported_reasoning_efforts": efforts,
        "visibility": model.get("visibility"),
        "supported_in_api": model.get("supported_in_api"),
        "context_window": model.get("context_window"),
        "effective_context_window_percent": model.get("effective_context_window_percent"),
    }


def probe_native_codex(
    codex_exe: Path,
    *,
    process_runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
    signature_reader: Callable[[Path], dict[str, Any]] = query_authenticode,
    expected_exe_sha256: str = EXPECTED_CODEX_EXE_SHA256,
) -> dict[str, Any]:
    resolved = _validate_native_executable_path(codex_exe)
    actual_sha256 = file_sha256(resolved)
    if actual_sha256 != expected_exe_sha256:
        raise ValueError("native Codex executable sha256 does not match the pinned release")
    signature = signature_reader(resolved)
    if (
        signature.get("status") != "Valid"
        or signature.get("signer_subject") != EXPECTED_SIGNER_SUBJECT
        or str(signature.get("signer_thumbprint") or "").upper()
        != EXPECTED_SIGNER_THUMBPRINT
    ):
        raise ValueError("native Codex Authenticode signer/status mismatch")
    version_raw = _run_probe(
        [str(resolved), "--version"],
        max_stdout_bytes=MAX_VERSION_OUTPUT_BYTES,
        process_runner=process_runner,
    )
    version = version_raw.decode("utf-8-sig").strip()
    if version != EXPECTED_CLI_VERSION:
        raise ValueError("native Codex CLI version mismatch")
    catalog_raw = _run_probe(
        [str(resolved), "debug", "models", "--bundled"],
        max_stdout_bytes=MAX_MODEL_CATALOG_BYTES,
        process_runner=process_runner,
    )
    catalog = json.loads(catalog_raw.decode("utf-8-sig"))
    models = catalog.get("models") if isinstance(catalog, dict) else None
    if not isinstance(models, list):
        raise ValueError("native Codex bundled model catalog is invalid")
    matches = [row for row in models if isinstance(row, dict) and row.get("slug") == EXPECTED_MODEL_SLUG]
    if len(matches) != 1:
        raise ValueError("pinned judge model is missing or duplicated in bundled catalog")
    projection = _model_projection(matches[0])
    if projection != EXPECTED_MODEL_PROJECTION:
        raise ValueError("pinned judge model capability projection mismatch")
    if EXPECTED_REASONING_EFFORT not in projection["supported_reasoning_efforts"]:
        raise ValueError("pinned judge model lacks high reasoning capability")
    return {
        "executable_path": str(resolved),
        "executable_name": resolved.name,
        "executable_size": resolved.stat().st_size,
        "executable_sha256": actual_sha256,
        "authenticode": signature,
        "cli_version": version,
        "bundled_model_catalog_sha256": hashlib.sha256(catalog_raw).hexdigest(),
        "model_capability": projection,
    }


def _anchor_payload(anchor: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in anchor.items() if key != "anchor_payload_sha256"}


def build_trust_anchor(
    *,
    codex_exe: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
    signature_reader: Callable[[Path], dict[str, Any]] = query_authenticode,
    expected_exe_sha256: str = EXPECTED_CODEX_EXE_SHA256,
    generated_at: str | None = None,
) -> dict[str, Any]:
    evidence = probe_native_codex(
        codex_exe,
        process_runner=process_runner,
        signature_reader=signature_reader,
        expected_exe_sha256=expected_exe_sha256,
    )
    anchor = {
        "report_type": REPORT_TYPE,
        "anchor_version": ANCHOR_VERSION,
        "gate": UNTRUSTED_EXECUTION_MODE,
        "execution_mode": UNTRUSTED_EXECUTION_MODE,
        "generated_at": generated_at or _utc_now(),
        "codex_cli": evidence,
        "judge_contract": {
            "provider": "codex",
            "model": EXPECTED_MODEL_SLUG,
            "reasoning_effort": EXPECTED_REASONING_EFFORT,
            "native_absolute_executable_required": True,
            "path_lookup_and_script_shims_forbidden": True,
            "authenticode_status_required": "Valid",
            "signer_subject_required": EXPECTED_SIGNER_SUBJECT,
            "signer_thumbprint_required": EXPECTED_SIGNER_THUMBPRINT,
            "executable_sha256_required": EXPECTED_CODEX_EXE_SHA256,
        },
        "artifact_write_contract": {
            "exclusive_create_no_overwrite": True,
            "read_only_after_create": False,
        },
    }
    anchor["anchor_payload_sha256"] = canonical_digest(_anchor_payload(anchor))
    return anchor


def validate_trust_anchor(
    anchor_path: Path,
    *,
    production: bool,
    process_runner: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
    signature_reader: Callable[[Path], dict[str, Any]] = query_authenticode,
    expected_exe_sha256: str = EXPECTED_CODEX_EXE_SHA256,
) -> dict[str, Any]:
    resolved_anchor = anchor_path.resolve(strict=True)
    anchor = json.loads(resolved_anchor.read_text(encoding="utf-8-sig"))
    if not isinstance(anchor, dict):
        raise ValueError("Codex CLI trust anchor must be an object")
    if anchor.get("report_type") != REPORT_TYPE or anchor.get("anchor_version") != ANCHOR_VERSION:
        raise ValueError("Codex CLI trust anchor type/version mismatch")
    if anchor.get("anchor_payload_sha256") != canonical_digest(_anchor_payload(anchor)):
        raise ValueError("Codex CLI trust anchor payload hash mismatch")
    generated_at = anchor.get("generated_at")
    if not isinstance(generated_at, str):
        raise ValueError("Codex CLI trust anchor generated_at missing")
    try:
        generated_time = datetime.fromisoformat(generated_at)
    except ValueError as exc:
        raise ValueError("Codex CLI trust anchor generated_at invalid") from exc
    if generated_time.tzinfo is None or generated_time > datetime.now(timezone.utc):
        raise ValueError("Codex CLI trust anchor timestamp is naive or in the future")
    expected_gate = "GO" if production else anchor.get("gate")
    if production and (
        expected_gate != "GO"
        or anchor.get("execution_mode") != PRODUCTION_EXECUTION_MODE
        or anchor.get("artifact_write_contract")
        != {"exclusive_create_no_overwrite": True, "read_only_after_create": True}
    ):
        raise ValueError("production Codex CLI trust anchor is not immutable GO")
    if production and resolved_anchor.stat().st_mode & (
        stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    ):
        raise ValueError("production Codex CLI trust anchor file is writable")
    contract = anchor.get("judge_contract")
    expected_contract = {
        "provider": "codex",
        "model": EXPECTED_MODEL_SLUG,
        "reasoning_effort": EXPECTED_REASONING_EFFORT,
        "native_absolute_executable_required": True,
        "path_lookup_and_script_shims_forbidden": True,
        "authenticode_status_required": "Valid",
        "signer_subject_required": EXPECTED_SIGNER_SUBJECT,
        "signer_thumbprint_required": EXPECTED_SIGNER_THUMBPRINT,
        "executable_sha256_required": EXPECTED_CODEX_EXE_SHA256,
    }
    if contract != expected_contract:
        raise ValueError("Codex CLI trust anchor judge contract mismatch")
    recorded = anchor.get("codex_cli")
    if not isinstance(recorded, dict):
        raise ValueError("Codex CLI trust evidence missing")
    current = probe_native_codex(
        Path(str(recorded.get("executable_path") or "")),
        process_runner=process_runner,
        signature_reader=signature_reader,
        expected_exe_sha256=expected_exe_sha256,
    )
    if current != recorded:
        raise ValueError("Codex CLI trust evidence changed after anchor freeze")
    return {
        "gate": "GO" if production else UNTRUSTED_EXECUTION_MODE,
        "report_type": REPORT_TYPE,
        "anchor_version": ANCHOR_VERSION,
        "anchor_path": str(resolved_anchor),
        "anchor_file_sha256": file_sha256(resolved_anchor),
        "anchor_payload_sha256": anchor["anchor_payload_sha256"],
        "generated_at": generated_at,
        "execution_mode": anchor.get("execution_mode"),
        "codex_cli": current,
        "judge_contract": contract,
    }


def main() -> int:
    script_path = Path(__file__).resolve()
    original_argv = [str(value) for value in getattr(sys, "orig_argv", [])]
    if any("runpy" in frame.filename.casefold() for frame in inspect.stack()):
        raise RuntimeError("trust anchor CLI cannot be invoked through runpy")
    if __name__ != "__main__" or Path(sys.argv[0]).resolve() != script_path:
        raise RuntimeError("trust anchor production entry requires direct script execution")
    entrypoint = validate_direct_python_entrypoint(original_argv, script_path)
    parser = argparse.ArgumentParser(
        description="Freeze a signed native Codex CLI trust anchor before blind adjudication."
    )
    parser.add_argument("--codex-exe", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--_production-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if bool(args._production_child) != bool(entrypoint["isolated_flag"]):
        raise RuntimeError("trust anchor outer/isolated-child entrypoint shape mismatch")
    if not _is_under_review_output(args.output_json):
        parser.error("--output-json must be inside repository out/.../review")
    if not args._production_child:
        challenge = secrets.token_hex(32)
        command = [
            str(Path(sys.executable).resolve()),
            "-I",
            str(script_path),
            "--_production-child",
            "--codex-exe",
            str(args.codex_exe.resolve()),
            "--output-json",
            str(args.output_json.resolve()),
        ]
        env = {
            key: os.environ[key]
            for key in ("SystemRoot", "WINDIR", "COMSPEC", "TEMP", "TMP")
            if os.environ.get(key)
        }
        env["CODEX_TRUST_ANCHOR_LAUNCH_CHALLENGE"] = challenge
        env["CODEX_TRUST_ANCHOR_LAUNCH_PARENT_PID"] = str(os.getpid())
        return int(subprocess.run(command, env=env, check=False).returncode)
    try:
        if sys.flags.isolated != 1 or original_argv.count("--_production-child") != 1:
            raise RuntimeError("trust anchor production requires one direct isolated child flag")
        challenge = os.environ.pop("CODEX_TRUST_ANCHOR_LAUNCH_CHALLENGE", "")
        parent_text = os.environ.pop("CODEX_TRUST_ANCHOR_LAUNCH_PARENT_PID", "")
        if not re.fullmatch(r"[0-9a-f]{64}", challenge):
            raise RuntimeError("trust anchor launcher challenge invalid")
        if not parent_text.isdigit() or int(parent_text) != os.getppid():
            raise RuntimeError("trust anchor launcher parent PID mismatch")
        anchor = build_trust_anchor(
            codex_exe=args.codex_exe,
        )
        production_seal = object()

        def seal_anchor(candidate: dict[str, Any], seal: object) -> dict[str, Any]:
            if seal is not production_seal or candidate.get("gate") != UNTRUSTED_EXECUTION_MODE:
                raise RuntimeError("trust anchor production seal is not closure-authorized")
            candidate["gate"] = "GO"
            candidate["execution_mode"] = PRODUCTION_EXECUTION_MODE
            candidate["artifact_write_contract"] = {
                "exclusive_create_no_overwrite": True,
                "read_only_after_create": True,
            }
            candidate["anchor_payload_sha256"] = canonical_digest(_anchor_payload(candidate))
            return candidate

        anchor = seal_anchor(anchor, production_seal)
        write_json_exclusive(args.output_json.resolve(), anchor, read_only=True)
    except Exception as exc:
        print(f"Codex CLI trust anchor failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(str(args.output_json.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
