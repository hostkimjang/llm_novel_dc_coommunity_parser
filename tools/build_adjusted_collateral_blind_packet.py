from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.bootstrap_regression_safe_grounding import compare_collateral
from tools.compare_completed779_improvement import analysis_identity, load_json_or_jsonl


PACKET_VERSION = "adjusted-collateral-blind-packet-v2"
SCOPE_VERSION = "adjusted-collateral-source-binding-v2"
PRODUCTION_PANEL_ROWS = 375
PRODUCTION_GOLDEN_ROWS = 18
PRODUCTION_RECOVERED_ROWS = 75
PRODUCTION_RESIDUAL_ROWS = 300
TRUST_VERSION = "regression-safe-grounding-authoritative-trust-v1"
PRODUCTION_BASELINE_MANIFEST_PATH = (
    ROOT / "docs/devs/loop638_adjudicated_rebaseline_manifest.json"
).resolve()
PRODUCTION_BASELINE_RESULT_PATH = (
    ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/baseline/loop638_adjudicated_rebaseline_result.json"
).resolve()
PRODUCTION_PANEL_SOURCE_PATH = (
    ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/panel/regression_panel_input.jsonl"
).resolve()
PRODUCTION_GOLDEN_MANIFEST_PATH = (
    ROOT
    / "out/regression_safe_grounding_20260626_000008_928006_loop01/golden/golden_manifest.json"
).resolve()
PRODUCTION_BASELINE_MANIFEST_SHA256 = "4fef46233747e62619487027cd07fd0a802e5174589f7a63b048487438d85751"
PRODUCTION_PANEL_SOURCE_SHA256 = "746c89217f8ab7d3dd44b3733ad8ab13801ebe9d995c125cc952806d7aed0cbe"
PRODUCTION_GOLDEN_MANIFEST_SHA256 = "2b9a0d882f22f23de246bfe18bb373ed1d98ade88ef1f10f9cb6952de22f9096"
PRODUCTION_GOAL_ID = "019f4850-7a35-7263-8347-362d7e553966"
RUNTIME_TRUST_ANCHOR_REPORT_TYPE = "interrupted_merge_preflight_trust_anchor"
RUNTIME_TRUST_ANCHOR_VERSION = "interrupted-merge-trust-v2"
INTERRUPTED_PROFILE = "interrupted_merge_75_300"
FRESH375_PROFILE = "fresh375"
FRESH375_CONSUMER_V2_CONTRACT = "supervisor-v2-final-continuity"
FRESH375_LEGACY_CONSUMER_CONTRACT = "legacy-actual-run-start-v1"
FRESH375_RUNTIME_FINGERPRINT_ENV = "RUNTIME_RELEASE_FINGERPRINT_SHA256"
FRESH375_RUNTIME_FINGERPRINT_FIELD = "runtime_release_fingerprint_sha256"
PRODUCTION_INTERRUPTED_TRUST_ANCHOR_PATH = (
    ROOT / "docs/devs/loop641_premerge_runtime_trust_anchor_v2.json"
).resolve()
PRODUCTION_INTERRUPTED_TRUST_ANCHOR_SHA256 = (
    "8a7487cff066d162c556678b3f76971436b4a4cba0aad1963b0312af0d2956b8"
)
SUPERSEDED_INTERRUPTED_V1_TRUST_ANCHOR_PATH = (
    ROOT / "docs/devs/loop641_premerge_runtime_trust_anchor.json"
).resolve()
# The production fresh375 anchor is created only after the one-shot plan is
# frozen. Its byte hash must then be compiled here before any downstream
# adjudication consumer may accept it. A caller-supplied hash is not a trust
# root and cannot replace this source-level pin.
PRODUCTION_FRESH375_COMPILED_ANCHOR_PATH = (
    ROOT / "docs/devs/loop642_current_head_fresh375_pre_run_anchor.json"
).resolve()
PRODUCTION_FRESH375_COMPILED_ANCHOR_SHA256: str | None = None

# Blind material is an allow-list, not a block-list.  New runtime/private fields
# therefore stay private until they are explicitly reviewed here.
SOURCE_FIELDS = (
    "gallery_id",
    "post_id",
    "title",
    "post_author",
    "author",
    "ip",
    "author_ip",
    "post_ip",
    "created_at",
    "url",
    "content",
    "content_blocks",
    "image_urls",
    "image_count",
    "comments",
    "comment_metadata",
    "comment_context",
    "comment_dialogue",
    "comment_context_lines",
    "comment_dialogue_context_lines",
)
SOURCE_BINDING_FIELDS = (
    "gallery_id",
    "post_id",
    "title",
    "post_author",
    "author",
    "ip",
    "author_ip",
    "post_ip",
    "created_at",
    "url",
    "content",
    "content_blocks",
    "image_urls",
    "image_count",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_read_only_file(path: Path) -> bool:
    if not path.is_file():
        return False
    return not bool(path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def post_id(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError("missing post_id")
    return text


def _unique_index(rows: list[dict[str, Any]], label: str) -> tuple[list[str], dict[str, dict[str, Any]]]:
    order: list[str] = []
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = post_id(row.get("post_id"))
        if pid in index:
            raise ValueError(f"{label} duplicate post_id: {pid}")
        order.append(pid)
        index[pid] = row
    return order, index


def source_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in SOURCE_FIELDS if field in row}


def identity_option(identity: Any) -> dict[str, Any]:
    payload = identity if isinstance(identity, dict) else {}
    return {
        "official_title": payload.get("official_title"),
        "official_url": payload.get("official_url") or payload.get("heretic_url"),
    }


def drift_id_for(row: dict[str, Any]) -> str:
    return canonical_digest(
        {
            "post_id": post_id(row.get("post_id")),
            "status": row.get("status"),
            "before_identity": row.get("before_identity"),
            "after_identity": row.get("after_identity"),
        }
    )


def packet_row_digest(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key != "packet_row_sha256"}
    return canonical_digest(payload)


def _golden_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("rows")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("golden manifest rows must be a list")
    return [row for row in rows if isinstance(row, dict)]


def _recorded_path(value: Any) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _require_sha256(value: Any, label: str) -> str:
    text = str(value or "").strip().lower()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{label} must be sha256")
    return text


def _load_json_path(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _anchor_payload_digest(anchor: dict[str, Any]) -> str:
    payload = dict(anchor)
    payload.pop("anchor_payload_sha256", None)
    return canonical_digest(payload)


def _runtime_code_tree_digest(anchor: dict[str, Any]) -> str:
    code_tree = anchor.get("runtime_code_tree")
    if not isinstance(code_tree, dict):
        raise ValueError("runtime trust anchor code tree missing")
    files = code_tree.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("runtime trust anchor code tree files missing")
    expected_paths: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            raise ValueError("runtime trust anchor code tree entry invalid")
        relative = str(entry.get("path") or "").replace("\\", "/")
        if not relative or relative.startswith("/") or ".." in Path(relative).parts:
            raise ValueError("runtime trust anchor code path invalid")
        path = (ROOT / relative).resolve()
        if ROOT not in path.parents and path != ROOT:
            raise ValueError("runtime trust anchor code path escapes repository")
        if not path.is_file() or file_sha256(path) != _require_sha256(
            entry.get("sha256"), f"runtime code file {relative}"
        ):
            raise ValueError(f"runtime code file drift: {relative}")
        expected_paths.append(relative)
    current_paths = ["expert_main.py"]
    current_paths.extend(
        path.resolve().relative_to(ROOT).as_posix()
        for path in (ROOT / "src").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )
    if sorted(expected_paths) != sorted(set(current_paths)):
        raise ValueError("runtime code tree file set drift")
    tree_digest = canonical_digest(files)
    if code_tree.get("file_count") != len(files) or code_tree.get("tree_sha256") != tree_digest:
        raise ValueError("runtime trust anchor code tree digest mismatch")
    return tree_digest


def _validate_runtime_trust_anchor(
    *,
    anchor: dict[str, Any],
    anchor_path: Path,
    anchor_byte_sha256: str,
    resolved: dict[str, Path],
    byte_hashes: dict[str, str],
    baseline_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    golden_manifest: Any,
    expected_scope_rows: int,
    expected_golden_rows: int,
    compiled_fresh_anchor_path: Path | None = None,
    compiled_fresh_anchor_sha256: str | None = None,
) -> dict[str, Any]:
    if anchor.get("report_type") != RUNTIME_TRUST_ANCHOR_REPORT_TYPE:
        raise ValueError("runtime trust anchor report_type invalid")
    if anchor.get("anchor_version") != RUNTIME_TRUST_ANCHOR_VERSION:
        raise ValueError("runtime trust anchor version invalid")
    if anchor.get("gate") != "GO" or anchor.get("generated_before_completion") is not True:
        raise ValueError("runtime trust anchor is not a pre-completion GO anchor")
    if anchor.get("anchor_payload_sha256") != _anchor_payload_digest(anchor):
        raise ValueError("runtime trust anchor payload digest mismatch")

    topology = anchor.get("topology")
    counts = anchor.get("expected_counts")
    run_ids = anchor.get("run_ids")
    if not isinstance(topology, dict) or not isinstance(counts, dict) or not isinstance(run_ids, dict):
        raise ValueError("runtime trust anchor topology/counts/run_ids missing")
    profile = str(topology.get("profile") or "")
    if profile == INTERRUPTED_PROFILE:
        if anchor_path == SUPERSEDED_INTERRUPTED_V1_TRUST_ANCHOR_PATH:
            raise ValueError("interrupted v1 runtime trust anchor is superseded")
        if (
            expected_scope_rows == PRODUCTION_PANEL_ROWS
            and expected_golden_rows == PRODUCTION_GOLDEN_ROWS
            and (
                anchor_path != PRODUCTION_INTERRUPTED_TRUST_ANCHOR_PATH
                or anchor_byte_sha256 != PRODUCTION_INTERRUPTED_TRUST_ANCHOR_SHA256
            )
        ):
            raise ValueError("production interrupted trust anchor v2 pin mismatch")
    elif profile == FRESH375_PROFILE:
        if compiled_fresh_anchor_path is None or compiled_fresh_anchor_sha256 is None:
            raise ValueError("fresh375 compiled pre-run anchor path/sha256 pin missing")
        compiled_sha256 = _require_sha256(
            compiled_fresh_anchor_sha256,
            "fresh375 compiled pre-run anchor",
        )
        if (
            anchor_path != compiled_fresh_anchor_path.resolve()
            or anchor_byte_sha256 != compiled_sha256
        ):
            raise ValueError("fresh375 compiled pre-run anchor pin mismatch")
        if (
            expected_scope_rows == PRODUCTION_PANEL_ROWS
            and expected_golden_rows == PRODUCTION_GOLDEN_ROWS
        ):
            if PRODUCTION_FRESH375_COMPILED_ANCHOR_SHA256 is None:
                raise ValueError(
                    "production fresh375 compiled pre-run anchor sha256 is not configured"
                )
            production_sha256 = _require_sha256(
                PRODUCTION_FRESH375_COMPILED_ANCHOR_SHA256,
                "production fresh375 compiled pre-run anchor",
            )
            if (
                anchor_path != PRODUCTION_FRESH375_COMPILED_ANCHOR_PATH
                or compiled_fresh_anchor_path.resolve()
                != PRODUCTION_FRESH375_COMPILED_ANCHOR_PATH
                or anchor_byte_sha256 != production_sha256
            ):
                raise ValueError("production fresh375 compiled pre-run anchor pin mismatch")
    stable_projection = anchor.get("stable_projection")
    if not isinstance(stable_projection, dict) or not isinstance(
        stable_projection.get("plan"), dict
    ):
        raise ValueError("runtime trust anchor stable plan projection invalid")
    if profile == INTERRUPTED_PROFILE and not all(
        isinstance(stable_projection.get(key), dict) for key in ("row", "manifest")
    ):
        raise ValueError("interrupted runtime trust anchor row/manifest projection invalid")
    fingerprint = _require_sha256(
        anchor.get("stable_runtime_fingerprint_sha256"),
        "runtime trust anchor fingerprint",
    )
    if fingerprint != canonical_digest(stable_projection):
        raise ValueError("runtime trust anchor fingerprint does not match projection")
    release_fingerprint = _require_sha256(
        anchor.get("release_fingerprint_sha256"),
        "runtime trust anchor release fingerprint",
    )
    code_tree_sha256 = _require_sha256(
        anchor.get("runtime_code_tree_sha256"),
        "runtime trust anchor code tree",
    )
    if code_tree_sha256 != _runtime_code_tree_digest(anchor):
        raise ValueError("runtime trust anchor current code tree mismatch")
    configuration_hashes = anchor.get("configuration_hashes")
    if not isinstance(configuration_hashes, dict):
        raise ValueError("runtime trust anchor configuration hashes missing")
    expected_configuration_hashes = {
        "plan_signature_sha256": canonical_digest(stable_projection["plan"]),
        "runtime_code_tree_sha256": code_tree_sha256,
    }
    if profile == INTERRUPTED_PROFILE:
        expected_configuration_hashes.update(
            {
                "row_signature_sha256": canonical_digest(stable_projection["row"]),
                "manifest_signature_sha256": canonical_digest(
                    stable_projection["manifest"]
                ),
                "stable_runtime_fingerprint_sha256": fingerprint,
            }
        )
    elif profile == FRESH375_PROFILE:
        expected_configuration_hashes["release_fingerprint_sha256"] = fingerprint
    for field, expected in expected_configuration_hashes.items():
        if configuration_hashes.get(field) != expected:
            raise ValueError(f"runtime trust anchor configuration hash mismatch: {field}")

    if profile == INTERRUPTED_PROFILE:
        expected_counts = {
            "source_rows": expected_scope_rows,
            "recovered_rows": PRODUCTION_RECOVERED_ROWS,
            "residual_rows": PRODUCTION_RESIDUAL_ROWS,
            "golden_rows": expected_golden_rows,
        }
        if counts != expected_counts:
            raise ValueError("interrupted runtime trust anchor counts mismatch")
        prompt_binding = anchor.get("prompt_version_binding")
        expected_prompt = str(
            (stable_projection.get("row") or {}).get("prompt_version") or ""
        ).strip()
        if (
            not isinstance(prompt_binding, dict)
            or prompt_binding.get("gate") != "GO"
            or not expected_prompt
            or any(
                prompt_binding.get(field) != expected_prompt
                for field in ("expected", "recovered", "residual_partial")
            )
        ):
            raise ValueError("interrupted runtime trust anchor prompt binding mismatch")
        expected_release_fingerprint = canonical_digest(
            {
                "stable_runtime_fingerprint_sha256": fingerprint,
                "runtime_code_tree_sha256": code_tree_sha256,
                "source_panel_sha256": byte_hashes["source_input"],
                "prompt_version": expected_prompt,
            }
        )
        if release_fingerprint != expected_release_fingerprint:
            raise ValueError("interrupted runtime trust anchor release fingerprint mismatch")
        source_run_id = str(run_ids.get("source") or "").strip()
        residual_run_id = str(run_ids.get("residual") or "").strip()
        if set(run_ids) != {"source", "residual"} or not source_run_id or not residual_run_id:
            raise ValueError("interrupted runtime trust anchor run ids invalid")
        if source_run_id == residual_run_id:
            raise ValueError("interrupted runtime trust anchor run ids must differ")
        topology_summary = {
            "profile": profile,
            "recovered_rows": counts["recovered_rows"],
            "residual_rows": counts["residual_rows"],
            "source_run_id": source_run_id,
            "residual_run_id": residual_run_id,
        }
    elif profile == FRESH375_PROFILE:
        expected_counts = {
            "source_rows": expected_scope_rows,
            "fresh_rows": expected_scope_rows,
            "golden_rows": expected_golden_rows,
        }
        if counts != expected_counts or set(run_ids) != {"fresh"}:
            raise ValueError("fresh375 runtime trust anchor counts/run ids mismatch")
        prompt_binding = anchor.get("prompt_version_binding")
        expected_prompt = str(stable_projection.get("expected_prompt_version") or "").strip()
        if (
            anchor.get("binding_phase") != "pre_run_release_anchor"
            or release_fingerprint != fingerprint
            or not isinstance(prompt_binding, dict)
            or prompt_binding.get("expected") != expected_prompt
            or prompt_binding.get("actual_run_start") is not None
            or prompt_binding.get("gate") != "PENDING_RUN_START_RECEIPT"
        ):
            raise ValueError("fresh375 pre-run release binding mismatch")
        fresh_run_id = str(run_ids.get("fresh") or "").strip() or None
        topology_summary = {
            "profile": profile,
            "fresh_rows": counts["fresh_rows"],
            "fresh_run_id": fresh_run_id,
        }
    else:
        raise ValueError("runtime trust anchor topology profile invalid")

    source_order = [post_id(row.get("post_id")) for row in source_rows]
    baseline_order = [post_id(row.get("post_id")) for row in baseline_rows]
    golden_rows = _golden_rows(golden_manifest)
    golden_order = [post_id(row.get("post_id")) for row in golden_rows]
    fixed = anchor.get("fixed_artifacts")
    if not isinstance(fixed, dict) or set(fixed) != {
        "source_panel",
        "adjudicated_baseline",
        "golden_manifest",
    }:
        raise ValueError("runtime trust anchor fixed artifacts invalid")
    fixed_expectations = {
        "source_panel": (
            resolved["source_input"],
            byte_hashes["source_input"],
            source_order,
        ),
        "adjudicated_baseline": (
            resolved["baseline_result"],
            byte_hashes["baseline_result"],
            baseline_order,
        ),
        "golden_manifest": (
            resolved["golden_manifest"],
            byte_hashes["golden_manifest"],
            golden_order,
        ),
    }
    for label, (expected_path, expected_hash, ids) in fixed_expectations.items():
        record = fixed.get(label)
        if not isinstance(record, dict):
            raise ValueError(f"runtime trust anchor fixed artifact missing: {label}")
        if _recorded_path(record.get("path")) != expected_path:
            raise ValueError(f"runtime trust anchor fixed path mismatch: {label}")
        if record.get("sha256") != expected_hash or record.get("row_count") != len(ids):
            raise ValueError(f"runtime trust anchor fixed artifact mismatch: {label}")
        if record.get("post_id_order_sha256") != canonical_digest(ids):
            raise ValueError(f"runtime trust anchor fixed order mismatch: {label}")
        if record.get("post_id_set_sha256") != canonical_digest(sorted(ids)):
            raise ValueError(f"runtime trust anchor fixed set mismatch: {label}")
    input_hashes = anchor.get("input_hashes")
    expected_input_hashes = {
        "source_panel_sha256": byte_hashes["source_input"],
        "adjudicated_baseline_sha256": byte_hashes["baseline_result"],
        "golden_manifest_sha256": byte_hashes["golden_manifest"],
        "source_post_id_order_sha256": canonical_digest(source_order),
    }
    if not isinstance(input_hashes, dict) or any(
        input_hashes.get(field) != expected for field, expected in expected_input_hashes.items()
    ):
        raise ValueError("runtime trust anchor input hashes mismatch")
    if profile == INTERRUPTED_PROFILE:
        immutable = anchor.get("immutable_components")
        expected_immutable_names = {
            "recovered_result",
            "recovery_summary",
            "source_checkpoint",
            "residual_input",
            "source_manifest",
            "source_plan",
            "residual_plan",
        }
        if not isinstance(immutable, dict) or set(immutable) != expected_immutable_names:
            raise ValueError("runtime trust anchor v2 immutable component set invalid")
        for name, record in immutable.items():
            if not isinstance(record, dict):
                raise ValueError(f"runtime trust anchor immutable record invalid: {name}")
            component_path = _recorded_path(record.get("path"))
            if not component_path.is_file():
                raise ValueError(f"runtime trust anchor immutable artifact missing: {name}")
            if (
                file_sha256(component_path) != record.get("byte_sha256")
                or component_path.stat().st_size != record.get("size_bytes")
            ):
                raise ValueError(f"runtime trust anchor immutable bytes changed: {name}")
            component_payload = (
                load_json_or_jsonl(component_path)
                if component_path.suffix.lower() == ".jsonl"
                else _load_json_path(component_path)
            )
            if canonical_digest(component_payload) != record.get("canonical_sha256"):
                raise ValueError(f"runtime trust anchor immutable payload changed: {name}")

    component_paths = anchor.get("component_paths")
    if not isinstance(component_paths, dict):
        raise ValueError("runtime trust anchor component plan paths missing")
    expected_plan_keys = (
        ("source_plan", "residual_plan")
        if profile == INTERRUPTED_PROFILE
        else ("fresh_plan",)
    )
    from tools.merge_interrupted_run_results import _plan_signature

    for key in expected_plan_keys:
        plan_path = _recorded_path(component_paths.get(key))
        if not plan_path.is_file():
            raise ValueError(f"runtime trust anchor component plan missing: {key}")
        plan_payload = _load_json_path(plan_path)
        if _plan_signature(plan_payload, key) != stable_projection["plan"]:
            raise ValueError(f"runtime trust anchor component plan projection drift: {key}")

    contract = anchor.get("contract")
    if not isinstance(contract, dict) or "gemma" not in str(contract.get("model") or "").lower():
        raise ValueError("runtime trust anchor model is not pinned Gemma")
    parallel = contract.get("parallel") if isinstance(contract.get("parallel"), dict) else {}
    if parallel.get("requested") != 16:
        raise ValueError("runtime trust anchor parallel contract invalid")
    effective_parallel = parallel.get("effective")
    if profile == INTERRUPTED_PROFILE and not isinstance(effective_parallel, int):
        raise ValueError("interrupted runtime trust anchor effective parallel missing")
    if effective_parallel is not None and (
        not isinstance(effective_parallel, int) or not 1 <= effective_parallel <= 16
    ):
        raise ValueError("runtime trust anchor effective parallel invalid")
    search = contract.get("search") if isinstance(contract.get("search"), dict) else {}
    if (
        search.get("included") is not True
        or search.get("light_mode") is not False
        or search.get("required_ok") != 16
        or search.get("reuse_shards_only") is not True
    ):
        raise ValueError("runtime trust anchor search contract invalid")
    if profile == INTERRUPTED_PROFILE and (
        int(search.get("healthy_ok") or 0) < 16 or search.get("failure_count") != 0
    ):
        raise ValueError("interrupted runtime trust anchor search health invalid")
    if search.get("healthy_ok") is not None and int(search.get("healthy_ok") or 0) < 16:
        raise ValueError("runtime trust anchor recorded healthy search count invalid")
    if search.get("failure_count") not in (None, 0):
        raise ValueError("runtime trust anchor recorded search failures nonzero")
    vlm_ocr = contract.get("vlm_ocr") if isinstance(contract.get("vlm_ocr"), dict) else {}
    if (
        not vlm_ocr.get("vlm")
        or not vlm_ocr.get("ocr")
        or vlm_ocr.get("require_for_images") is not True
        or str(contract.get("slang_db") or "").lower() != "off"
        or contract.get("dashboard_required") is not True
    ):
        raise ValueError("runtime trust anchor VLM/OCR/slang/dashboard contract invalid")
    if profile == INTERRUPTED_PROFILE and vlm_ocr.get("semantic_review_ready") is not True:
        raise ValueError("interrupted runtime trust anchor VLM/OCR readiness invalid")
    if vlm_ocr.get("semantic_review_ready") not in (None, True):
        raise ValueError("runtime trust anchor recorded VLM/OCR readiness invalid")

    expected_binding = {
        "gate": "GO",
        "path": str(anchor_path),
        "sha256": anchor_byte_sha256,
        "anchor_version": RUNTIME_TRUST_ANCHOR_VERSION,
        "topology_profile": profile,
        "stable_runtime_fingerprint_sha256": fingerprint,
        "release_fingerprint_sha256": release_fingerprint,
        "runtime_code_tree_sha256": code_tree_sha256,
    }
    validated = {
        **topology_summary,
        "fingerprint": fingerprint,
        "release_fingerprint": release_fingerprint,
        "code_tree_sha256": code_tree_sha256,
        "binding": expected_binding,
        "anchor_payload_sha256": anchor.get("anchor_payload_sha256"),
    }
    if profile == FRESH375_PROFILE:
        validated["compiled_anchor_path"] = str(
            (compiled_fresh_anchor_path or anchor_path).resolve()
        )
        validated["compiled_anchor_sha256"] = _require_sha256(
            compiled_fresh_anchor_sha256,
            "fresh375 compiled pre-run anchor",
        )
    return validated


def _bound_payload(path: Path) -> Any:
    return (
        load_json_or_jsonl(path)
        if path.suffix.lower() == ".jsonl"
        else _load_json_path(path)
    )


def _validate_artifact_binding(
    *,
    record: Any,
    expected_path: Path,
    expected_payload: Any,
    label: str,
    require_row_count: int | None = None,
    require_read_only: bool = True,
) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"{label} binding missing")
    if _recorded_path(record.get("path")) != expected_path:
        raise ValueError(f"{label} path mismatch")
    if (
        record.get("byte_sha256") != file_sha256(expected_path)
        or record.get("canonical_sha256") != canonical_digest(expected_payload)
        or record.get("size_bytes") != expected_path.stat().st_size
    ):
        raise ValueError(f"{label} byte/canonical/size binding mismatch")
    if require_row_count is not None and record.get("row_count") != require_row_count:
        raise ValueError(f"{label} row count mismatch")
    if require_read_only and not _is_read_only_file(expected_path):
        raise ValueError(f"{label} artifact is not read-only")


def _validate_interrupted_dashboard_manifest_transition(
    *,
    stable_manifest: dict[str, Any],
    source_manifest: dict[str, Any],
    residual_manifest: dict[str, Any],
    merged_manifest: dict[str, Any],
) -> None:
    """Allow only the merge tool's intentional dashboard composition transition."""
    component_mode = "standalone_forward"
    merged_mode = "composite_source_runs"
    if stable_manifest.get("dashboard_mode") != component_mode:
        raise ValueError("interrupted anchor dashboard mode is not standalone_forward")
    for label, component in (
        ("source", source_manifest),
        ("residual", residual_manifest),
    ):
        if (
            component.get("dashboard_mode") != component_mode
            or component.get("dashboard_standalone_forwarding") is not True
        ):
            raise ValueError(
                f"interrupted {label} component dashboard mode is not standalone_forward"
            )
    if merged_manifest.get("dashboard_mode") != merged_mode:
        raise ValueError("interrupted merged dashboard mode is not composite_source_runs")
    for field, expected in stable_manifest.items():
        if field == "dashboard_mode":
            continue
        if merged_manifest.get(field) != expected:
            raise ValueError(
                f"merged manifest stable projection mismatch outside dashboard_mode: {field}"
            )


def _validate_golden_audit_diagnostic_contract(
    *,
    golden_audit: dict[str, Any],
    expected_golden_rows: int,
    canonical_audit_sha256: str,
) -> dict[str, Any]:
    """Validate semantic PASS/NO-GO accounting without turning NO-GO into trust failure."""
    if golden_audit.get("report_type") != "golden18_bound_audit":
        raise ValueError("golden audit report_type invalid")
    if golden_audit.get("scope") != "golden_canary_expected_answer_audit":
        raise ValueError("golden audit scope invalid")
    audit_gate = golden_audit.get("gate")
    semantic_gate = golden_audit.get("canary_semantic_gate")
    if audit_gate not in {"PASS", "GO", "NO-GO"}:
        raise ValueError("golden audit gate invalid")
    if semantic_gate not in {"PASS", "GO", "NO-GO"}:
        raise ValueError("golden semantic gate invalid")
    audit_rows = golden_audit.get("rows") if isinstance(golden_audit.get("rows"), list) else []
    passed_count = golden_audit.get("passed_count")
    failed_count = golden_audit.get("failed_count")
    if (
        golden_audit.get("row_count") != expected_golden_rows
        or len(audit_rows) != expected_golden_rows
        or not isinstance(passed_count, int)
        or isinstance(passed_count, bool)
        or not isinstance(failed_count, int)
        or isinstance(failed_count, bool)
        or passed_count < 0
        or failed_count < 0
        or passed_count + failed_count != expected_golden_rows
    ):
        raise ValueError("golden audit row count mismatch")
    if any(
        not isinstance(row, dict) or not isinstance(row.get("passed"), bool)
        for row in audit_rows
    ):
        raise ValueError("golden audit rows require explicit boolean passed values")
    row_passed_count = sum(row["passed"] is True for row in audit_rows)
    row_failed_count = sum(row["passed"] is False for row in audit_rows)
    if row_passed_count != passed_count or row_failed_count != failed_count:
        raise ValueError("golden audit row pass/fail counts invalid")
    if failed_count == 0:
        if passed_count != expected_golden_rows or audit_gate not in {"PASS", "GO"} or semantic_gate not in {
            "PASS",
            "GO",
        }:
            raise ValueError("golden audit expected-answer counts invalid")
    elif audit_gate != "NO-GO" or semantic_gate != "NO-GO":
        raise ValueError("golden audit semantic failure gate mismatch")
    failed_rows = [
        {
            "post_id": post_id(row.get("post_id")),
            "status": str(row.get("status") or "").strip(),
        }
        for row in audit_rows
        if row["passed"] is False
    ]
    if any(not row["status"] for row in failed_rows):
        raise ValueError("golden audit failed row status missing")
    return {
        "gate": audit_gate,
        "canary_semantic_gate": semantic_gate,
        "row_count": expected_golden_rows,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "failed_rows": failed_rows,
        "failed_rows_sha256": canonical_digest(failed_rows),
        "canonical_audit_sha256": _require_sha256(
            canonical_audit_sha256,
            "canonical golden audit",
        ),
        "blind_judge_may_override": False,
    }


def _validate_fresh375_runtime_fingerprint_echo(
    *,
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    expected_fingerprint: str,
    label: str,
) -> None:
    expected = _require_sha256(expected_fingerprint, f"{label} runtime fingerprint")
    if manifest.get(FRESH375_RUNTIME_FINGERPRINT_FIELD) != expected:
        raise ValueError(f"{label} manifest current runtime fingerprint echo mismatch")
    for index, row in enumerate(rows, start=1):
        run_meta = row.get("run_meta")
        if (
            not isinstance(run_meta, dict)
            or run_meta.get(FRESH375_RUNTIME_FINGERPRINT_FIELD) != expected
        ):
            raise ValueError(
                f"{label} row {index} current runtime fingerprint echo mismatch"
            )


def validate_fresh375_v2_consumer_contract(
    *,
    pre_run_anchor_path: Path,
    compiled_anchor_path: Path,
    compiled_anchor_sha256: str,
    supervisor_start_event_path: Path,
    snapshot_result_path: Path,
    snapshot_manifest_path: Path,
    run_start_receipt_path: Path,
    final_continuity_path: Path,
    source_jsonl: Path,
    final_result_path: Path,
    final_manifest_path: Path,
    final_checkpoint_path: Path,
    final_pending_path: Path,
) -> dict[str, Any]:
    """Validate the complete supervisor-v2 chain before semantic adjudication."""
    from tools.build_interrupted_merge_trust_anchor import (
        validate_fresh375_consumer_trust_bundle,
    )

    consumer = validate_fresh375_consumer_trust_bundle(
        pre_run_anchor_path=pre_run_anchor_path,
        compiled_anchor_path=compiled_anchor_path,
        compiled_anchor_sha256=compiled_anchor_sha256,
        supervisor_start_event_path=supervisor_start_event_path,
        run_start_receipt_path=run_start_receipt_path,
        final_continuity_path=final_continuity_path,
        source_jsonl=source_jsonl,
    )
    if (
        consumer.get("gate") != "GO"
        or consumer.get("schema") != "fresh375-consumer-trust-bundle-v2"
    ):
        raise ValueError("fresh375 supervisor-v2 base consumer gate invalid")

    anchor = _load_json_path(pre_run_anchor_path)
    event = _load_json_path(supervisor_start_event_path)
    receipt = _load_json_path(run_start_receipt_path)
    continuity = _load_json_path(final_continuity_path)
    if any(not isinstance(value, dict) for value in (anchor, event, receipt, continuity)):
        raise ValueError("fresh375 supervisor-v2 trust artifact payload invalid")
    if set(receipt).intersection({"partial_result", "run_manifest"}):
        raise ValueError("fresh375 supervisor-v2 receipt contains legacy live-root fields")
    if (
        receipt.get("report_type") != "fresh375_actual_run_start_binding_receipt"
        or receipt.get("schema_version") != "fresh375-run-start-binding-v2"
        or receipt.get("binding_phase")
        != "supervised_immutable_first_durable_flush"
        or receipt.get("snapshot_schema_version")
        != "fresh375-first-durable-snapshot-v2"
    ):
        raise ValueError("fresh375 supervisor-v2 run-start receipt contract invalid")

    explicit_paths = {
        "live_result": final_result_path,
        "live_manifest": final_manifest_path,
        "live_checkpoint": final_checkpoint_path,
        "live_pending": final_pending_path,
        "snapshot_result": snapshot_result_path,
        "snapshot_manifest": snapshot_manifest_path,
        "run_start_receipt": run_start_receipt_path,
        "final_continuity": final_continuity_path,
    }
    event_paths = event.get("artifact_paths")
    if not isinstance(event_paths, dict):
        raise ValueError("fresh375 supervisor-v2 start-event paths missing")
    for field, expected_path in explicit_paths.items():
        if _recorded_path(event_paths.get(field)) != expected_path.resolve():
            raise ValueError(f"fresh375 supervisor-v2 start-event path mismatch: {field}")

    anchor_sha256 = _require_sha256(
        compiled_anchor_sha256,
        "fresh375 compiled pre-run anchor",
    )
    anchor_binding = {
        "path": str(pre_run_anchor_path.resolve()),
        "sha256": anchor_sha256,
        "anchor_version": RUNTIME_TRUST_ANCHOR_VERSION,
        "release_fingerprint_sha256": anchor.get("release_fingerprint_sha256"),
    }
    if (
        compiled_anchor_path.resolve() != pre_run_anchor_path.resolve()
        or file_sha256(pre_run_anchor_path) != anchor_sha256
        or event.get("pre_run_anchor") != anchor_binding
        or receipt.get("pre_run_anchor") != anchor_binding
    ):
        raise ValueError("fresh375 supervisor-v2 compiled anchor cross binding mismatch")
    if (
        event.get("fresh_plan") != receipt.get("fresh_plan")
        or receipt.get("fresh_plan")
        != (anchor.get("immutable_components") or {}).get("fresh_plan")
    ):
        raise ValueError("fresh375 supervisor-v2 immutable plan cross binding mismatch")

    snapshot_rows = load_json_or_jsonl(snapshot_result_path)
    snapshot_manifest = _load_json_path(snapshot_manifest_path)
    if not isinstance(snapshot_manifest, dict):
        raise ValueError("fresh375 supervisor-v2 snapshot manifest invalid")
    _validate_artifact_binding(
        record=receipt.get("snapshot_result"),
        expected_path=snapshot_result_path.resolve(),
        expected_payload=snapshot_rows,
        label="fresh375 supervisor-v2 snapshot result",
        require_row_count=len(snapshot_rows),
    )
    _validate_artifact_binding(
        record=receipt.get("snapshot_manifest"),
        expected_path=snapshot_manifest_path.resolve(),
        expected_payload=snapshot_manifest,
        label="fresh375 supervisor-v2 snapshot manifest",
    )
    if (
        receipt.get("supervisor_start_event", {}).get("path")
        != str(supervisor_start_event_path.resolve())
        or continuity.get("immutable_snapshot") != receipt.get("snapshot_result")
    ):
        raise ValueError("fresh375 supervisor-v2 snapshot/start-event cross binding mismatch")

    final_rows = load_json_or_jsonl(final_result_path)
    final_manifest = _load_json_path(final_manifest_path)
    final_checkpoint = load_json_or_jsonl(final_checkpoint_path)
    final_pending = _load_json_path(final_pending_path)
    if not isinstance(final_manifest, dict):
        raise ValueError("fresh375 supervisor-v2 final manifest invalid")
    final_artifacts = continuity.get("final_artifacts")
    if not isinstance(final_artifacts, dict) or set(final_artifacts) != {
        "result",
        "manifest",
        "checkpoint",
        "pending",
    }:
        raise ValueError("fresh375 supervisor-v2 final artifact set invalid")
    final_bindings = {
        "result": (final_result_path.resolve(), final_rows, len(final_rows)),
        "manifest": (final_manifest_path.resolve(), final_manifest, None),
        "checkpoint": (
            final_checkpoint_path.resolve(),
            final_checkpoint,
            len(final_checkpoint),
        ),
        "pending": (final_pending_path.resolve(), final_pending, None),
    }
    for name, (path, payload, row_count) in final_bindings.items():
        _validate_artifact_binding(
            record=final_artifacts.get(name),
            expected_path=path,
            expected_payload=payload,
            label=f"fresh375 supervisor-v2 final {name}",
            require_row_count=row_count,
        )
    if consumer.get("final_artifacts") != final_artifacts:
        raise ValueError("fresh375 supervisor-v2 base/final continuity binding mismatch")

    run_id = str(receipt.get("run_id") or "").strip()
    release_fingerprint = _require_sha256(
        anchor.get("release_fingerprint_sha256"),
        "fresh375 anchor release fingerprint",
    )
    continuity_state = continuity.get("continuity")
    if (
        not run_id
        or continuity.get("run_id") != run_id
        or continuity.get("release_fingerprint_sha256") != release_fingerprint
        or receipt.get("release_fingerprint_sha256") != release_fingerprint
        or final_manifest.get("run_id") != run_id
        or not isinstance(continuity_state, dict)
        or continuity_state.get("exact_prefix_preserved") is not True
        or continuity_state.get("same_run_id") is not True
        or continuity_state.get("same_runtime_signature") is not True
        or continuity_state.get("same_config_hash") is not True
        or continuity_state.get("process_exit_code") != 0
    ):
        raise ValueError("fresh375 supervisor-v2 final continuity/run binding mismatch")

    execution_contract = anchor.get("execution_contract")
    if not isinstance(execution_contract, dict):
        raise ValueError("fresh375 supervisor-v2 execution contract missing")
    event_execution = event.get("execution_binding")
    if not isinstance(event_execution, dict):
        raise ValueError("fresh375 supervisor-v2 start-event execution binding missing")
    immutable_execution_fields = (
        "command_argv",
        "command_argv_sha256",
        "resolved_command_argv",
        "resolved_command_argv_sha256",
        "executable",
        "cwd",
        "input_path",
        "output_path",
        "manifest_path",
        "checkpoint_path",
        "pending_path",
        "required_env",
        "env_overrides",
        "child_environment_policy",
        "binding_echo_contract",
        "runtime_contract",
    )
    if any(
        event_execution.get(field) != execution_contract.get(field)
        for field in immutable_execution_fields
    ):
        raise ValueError(
            "fresh375 supervisor-v2 command/model/search execution contract drift"
        )
    required_env = execution_contract.get("required_env")
    effective_env = execution_contract.get("effective_env")
    runtime_contract = execution_contract.get("runtime_contract")
    runtime_required_env = (
        runtime_contract.get("required_env")
        if isinstance(runtime_contract, dict)
        else None
    )
    event_required_env = event_execution.get("required_env")
    if not all(
        isinstance(value, dict)
        for value in (
            required_env,
            effective_env,
            runtime_required_env,
            event_required_env,
        )
    ):
        raise ValueError("fresh375 supervisor-v2 runtime env contract missing")
    current_runtime_fingerprint = _require_sha256(
        required_env.get(FRESH375_RUNTIME_FINGERPRINT_ENV),
        "fresh375 current runtime fingerprint",
    )
    if any(
        source.get(FRESH375_RUNTIME_FINGERPRINT_ENV)
        != current_runtime_fingerprint
        for source in (effective_env, runtime_required_env, event_required_env)
    ):
        raise ValueError("fresh375 supervisor-v2 runtime fingerprint env binding mismatch")
    child_environment = event_execution.get("child_environment")
    anchored_child_environment = execution_contract.get(
        "child_environment_without_binding_token"
    )
    token_commitment = str(
        event.get("pre_dispatch_binding_token_commitment") or ""
    )
    anchored_child_names = (
        anchored_child_environment.get("names") or []
        if isinstance(anchored_child_environment, dict)
        else []
    )
    expected_child_names = sorted(
        [*anchored_child_names, "FRESH375_RUN_BINDING_TOKEN"]
    )
    if (
        not isinstance(child_environment, dict)
        or not isinstance(anchored_child_environment, dict)
        or child_environment.get("names") != expected_child_names
        or child_environment.get("variable_count") != len(expected_child_names)
        or child_environment.get("values_redacted") is not True
        or any(
            child_environment.get("value_sha256", {}).get(name) != digest
            for name, digest in (
                anchored_child_environment.get("value_sha256") or {}
            ).items()
        )
        or child_environment.get("value_sha256", {}).get(
            "FRESH375_RUN_BINDING_TOKEN"
        )
        != token_commitment
    ):
        raise ValueError("fresh375 supervisor-v2 child environment binding drift")
    expected_child_digest = canonical_digest(
        {
            "name": FRESH375_RUNTIME_FINGERPRINT_ENV,
            "value": current_runtime_fingerprint,
        }
    )
    if (
        child_environment.get("value_sha256", {}).get(
            FRESH375_RUNTIME_FINGERPRINT_ENV
        )
        != expected_child_digest
    ):
        raise ValueError("fresh375 supervisor-v2 child runtime fingerprint binding mismatch")
    _validate_fresh375_runtime_fingerprint_echo(
        rows=snapshot_rows,
        manifest=snapshot_manifest,
        expected_fingerprint=current_runtime_fingerprint,
        label="fresh375 supervisor-v2 snapshot",
    )
    _validate_fresh375_runtime_fingerprint_echo(
        rows=final_rows,
        manifest=final_manifest,
        expected_fingerprint=current_runtime_fingerprint,
        label="fresh375 supervisor-v2 final",
    )
    return {
        **consumer,
        "consumer_contract": FRESH375_CONSUMER_V2_CONTRACT,
        "binding_phase": receipt.get("binding_phase"),
        "snapshot_result_sha256": file_sha256(snapshot_result_path),
        "snapshot_manifest_sha256": file_sha256(snapshot_manifest_path),
        "current_runtime_fingerprint_sha256": current_runtime_fingerprint,
        "runtime_code_tree_sha256": anchor.get("runtime_code_tree_sha256"),
        "release_fingerprint_sha256": release_fingerprint,
    }


def _validate_runtime_binding_receipt(
    *,
    receipt: dict[str, Any],
    receipt_path: Path,
    runtime_anchor: dict[str, Any],
    runtime_trust: dict[str, Any],
    resolved: dict[str, Path],
    after_rows: list[dict[str, Any]],
    merged_checkpoint: list[dict[str, Any]],
    merged_pending: Any,
    merged_manifest: dict[str, Any],
    merge_integrity: dict[str, Any] | None,
    fresh375_consumer_contract: str | None = None,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError("runtime binding receipt must be an object")
    if not _is_read_only_file(receipt_path):
        raise ValueError("runtime binding receipt is not read-only")
    profile = runtime_trust["profile"]
    if profile == INTERRUPTED_PROFILE:
        from tools.merge_interrupted_run_results import (
            validate_finalized_merge_binding_receipt,
        )

        validate_finalized_merge_binding_receipt(
            receipt,
            receipt_path=receipt_path,
            verify_artifact_bytes=True,
        )
        preflight = receipt.get("preflight_paths")
        expected_preflight_paths = {
            "result": resolved["after_result"],
            "checkpoint": resolved["merged_checkpoint"],
            "pending": resolved["merged_pending"],
            "manifest": resolved["merged_manifest"],
            "integrity_json": resolved["merge_integrity"],
            "binding_receipt": receipt_path,
        }
        if not isinstance(preflight, dict):
            raise ValueError("interrupted merge receipt preflight paths missing")
        for field, expected_path in expected_preflight_paths.items():
            if _recorded_path(preflight.get(field)) != expected_path:
                raise ValueError(f"interrupted merge receipt preflight path mismatch: {field}")
        output_artifacts = receipt.get("output_artifacts")
        if not isinstance(output_artifacts, dict):
            raise ValueError("interrupted merge receipt output artifacts missing")
        _validate_artifact_binding(
            record=output_artifacts.get("result"),
            expected_path=resolved["after_result"],
            expected_payload=after_rows,
            label="interrupted merged result",
            require_row_count=len(after_rows),
        )
        result_binding = output_artifacts["result"]
        after_ids = [post_id(row.get("post_id")) for row in after_rows]
        if (
            result_binding.get("post_id_order_sha256") != canonical_digest(after_ids)
            or result_binding.get("post_id_set_sha256")
            != canonical_digest(sorted(after_ids))
        ):
            raise ValueError("interrupted merged result post_id binding mismatch")
        _validate_artifact_binding(
            record=output_artifacts.get("checkpoint"),
            expected_path=resolved["merged_checkpoint"],
            expected_payload=merged_checkpoint,
            label="interrupted merged checkpoint",
            require_row_count=len(merged_checkpoint),
        )
        _validate_artifact_binding(
            record=output_artifacts.get("pending"),
            expected_path=resolved["merged_pending"],
            expected_payload=merged_pending,
            label="interrupted merged pending",
            require_row_count=0,
        )
        _validate_artifact_binding(
            record=receipt.get("manifest"),
            expected_path=resolved["merged_manifest"],
            expected_payload=merged_manifest,
            label="interrupted merged manifest",
        )
        if not isinstance(merge_integrity, dict):
            raise ValueError("interrupted merge receipt requires integrity payload")
        _validate_artifact_binding(
            record=receipt.get("integrity"),
            expected_path=resolved["merge_integrity"],
            expected_payload=merge_integrity,
            label="interrupted merge integrity",
        )
        markdown_binding = receipt.get("integrity_markdown")
        if not isinstance(markdown_binding, dict):
            raise ValueError("interrupted merge integrity markdown binding missing")
        markdown_path = _recorded_path(markdown_binding.get("path"))
        if (
            _recorded_path(preflight.get("integrity_md")) != markdown_path
            or not markdown_path.is_file()
            or file_sha256(markdown_path) != markdown_binding.get("byte_sha256")
            or markdown_path.stat().st_size != markdown_binding.get("size_bytes")
            or not _is_read_only_file(markdown_path)
        ):
            raise ValueError("interrupted merge integrity markdown binding mismatch")
        trust_binding = receipt.get("trust_anchor")
        if not isinstance(trust_binding, dict) or any(
            trust_binding.get(field) != expected
            for field, expected in runtime_trust["binding"].items()
        ):
            raise ValueError("interrupted merge receipt trust anchor mismatch")
        if (
            merged_manifest.get("premerge_trust_anchor") != trust_binding
            or merge_integrity.get("premerge_trust_anchor") != trust_binding
            or merged_manifest.get("output_artifacts") != output_artifacts
            or merged_manifest.get("residual_runtime_artifacts")
            != receipt.get("residual_runtime_artifacts")
        ):
            raise ValueError("interrupted merge detached receipt is not exact output binding")
        boundary = receipt.get("approval_boundary")
        if (
            not isinstance(boundary, dict)
            or boundary.get("detached_receipt_is_binding_evidence_not_semantic_approval")
            is not True
            or boundary.get("production_full_scan_approval") is not False
        ):
            raise ValueError("interrupted merge receipt approval boundary invalid")
        return {
            "report_type": receipt.get("report_type"),
            "schema_version": receipt.get("schema_version"),
            "path": str(receipt_path),
            "sha256": file_sha256(receipt_path),
            "payload_sha256": receipt.get("receipt_payload_sha256"),
            "trust_anchor": trust_binding,
        }

    if profile != FRESH375_PROFILE:
        raise ValueError("unsupported runtime binding receipt profile")
    if fresh375_consumer_contract == FRESH375_CONSUMER_V2_CONTRACT:
        required_v2_paths = (
            "fresh_supervisor_start_event",
            "fresh_snapshot_result",
            "fresh_snapshot_manifest",
            "fresh_final_continuity",
        )
        missing_v2_paths = [key for key in required_v2_paths if key not in resolved]
        if missing_v2_paths:
            raise ValueError(
                f"fresh375 supervisor-v2 consumer paths missing: {missing_v2_paths}"
            )
        return validate_fresh375_v2_consumer_contract(
            pre_run_anchor_path=resolved["runtime_trust_anchor"],
            compiled_anchor_path=Path(runtime_trust["compiled_anchor_path"]),
            compiled_anchor_sha256=runtime_trust["compiled_anchor_sha256"],
            supervisor_start_event_path=resolved["fresh_supervisor_start_event"],
            snapshot_result_path=resolved["fresh_snapshot_result"],
            snapshot_manifest_path=resolved["fresh_snapshot_manifest"],
            run_start_receipt_path=receipt_path,
            final_continuity_path=resolved["fresh_final_continuity"],
            source_jsonl=resolved["source_input"],
            final_result_path=resolved["after_result"],
            final_manifest_path=resolved["merged_manifest"],
            final_checkpoint_path=resolved["merged_checkpoint"],
            final_pending_path=resolved["merged_pending"],
        )
    if fresh375_consumer_contract != FRESH375_LEGACY_CONSUMER_CONTRACT:
        raise ValueError("fresh375 consumer contract missing or unsupported")

    # Explicit compatibility-only path for pre-supervisor-v2 test artifacts.
    # Production 375/18 scope rejects this contract before reaching here.
    from tools.build_interrupted_merge_trust_anchor import (
        _legacy_validate_fresh375_run_start_binding_receipt_v1,
    )

    _legacy_validate_fresh375_run_start_binding_receipt_v1(
        receipt,
        receipt_path=receipt_path,
        verify_artifact_bytes=True,
    )
    if (
        receipt.get("report_type") != "fresh375_actual_run_start_binding_receipt"
        or receipt.get("binding_phase") != "actual_run_start"
        or receipt.get("gate") != "GO"
    ):
        raise ValueError("fresh375 run-start binding receipt invalid")
    pre_run_anchor = receipt.get("pre_run_anchor")
    if (
        not isinstance(pre_run_anchor, dict)
        or _recorded_path(pre_run_anchor.get("path")) != resolved["runtime_trust_anchor"]
        or pre_run_anchor.get("sha256") != file_sha256(resolved["runtime_trust_anchor"])
        or pre_run_anchor.get("anchor_version") != RUNTIME_TRUST_ANCHOR_VERSION
        or pre_run_anchor.get("release_fingerprint_sha256")
        != runtime_trust["release_fingerprint"]
        or receipt.get("release_fingerprint_sha256")
        != runtime_trust["release_fingerprint"]
        or receipt.get("runtime_code_tree_sha256")
        != runtime_trust["code_tree_sha256"]
    ):
        raise ValueError("fresh375 run-start pre-run anchor binding mismatch")
    expected_rows = int(runtime_anchor["expected_counts"]["fresh_rows"])
    source_binding = receipt.get("source_input")
    _validate_artifact_binding(
        record=source_binding,
        expected_path=resolved["source_input"],
        expected_payload=_bound_payload(resolved["source_input"]),
        label="fresh375 run-start source input",
        require_row_count=expected_rows,
    )
    source_ids = [
        post_id(row.get("post_id"))
        for row in _bound_payload(resolved["source_input"])
    ]
    if (
        source_binding.get("post_id_order_sha256") != canonical_digest(source_ids)
        or source_binding.get("post_id_set_sha256")
        != canonical_digest(sorted(source_ids))
    ):
        raise ValueError("fresh375 run-start source input post_id binding mismatch")
    run_id = str(receipt.get("run_id") or "").strip()
    if not run_id or merged_manifest.get("run_id") != run_id:
        raise ValueError("fresh375 run-start run id mismatch")
    observed = receipt.get("observed_counts")
    if not isinstance(observed, dict):
        raise ValueError("fresh375 run-start observed counts missing")
    completed = observed.get("completed_count")
    flushed = observed.get("flushed_count")
    pending = observed.get("pending_count")
    failed = observed.get("failed_count")
    if (
        any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in (completed, flushed, pending, failed)
        )
        or observed.get("input_post_count") != expected_rows
        or not (0 < completed < expected_rows)
        or not (0 < flushed <= completed)
        or pending != completed - flushed
        or failed != 0
        or observed.get("large_run_complete") is not False
    ):
        raise ValueError("fresh375 run-start counts do not prove an incomplete run")
    prompt_binding = receipt.get("prompt_version_binding")
    expected_prompt = runtime_anchor["prompt_version_binding"]["expected"]
    if prompt_binding != {
        "expected": expected_prompt,
        "actual": expected_prompt,
        "gate": "GO",
    }:
        raise ValueError("fresh375 run-start prompt binding mismatch")
    partial_record = receipt.get("partial_result")
    if not isinstance(partial_record, dict):
        raise ValueError("fresh375 run-start partial result binding missing")
    partial_path = _recorded_path(partial_record.get("path"))
    if not partial_path.is_file():
        raise ValueError("fresh375 run-start partial result missing")
    partial_rows = load_json_or_jsonl(partial_path)
    _validate_artifact_binding(
        record=partial_record,
        expected_path=partial_path,
        expected_payload=partial_rows,
        label="fresh375 run-start partial result",
        require_row_count=flushed,
    )
    if partial_rows != after_rows[:flushed]:
        raise ValueError("fresh375 run-start partial rows are not final result prefix")
    from tools.merge_interrupted_run_results import _uniform_row_signature

    partial_signature = _uniform_row_signature(partial_rows, "fresh375 run-start")
    final_signature = _uniform_row_signature(after_rows, "fresh375 final")
    if receipt.get("row_signature") != partial_signature or partial_signature != final_signature:
        raise ValueError("fresh375 run-start/final row signature mismatch")
    final_config_hashes = {
        str((row.get("run_meta") or {}).get("config_hash") or "").strip()
        for row in after_rows
    }
    config_binding = receipt.get("config_binding")
    if (
        len(final_config_hashes) != 1
        or "" in final_config_hashes
        or not isinstance(config_binding, dict)
        or config_binding.get("gate") != "GO"
        or config_binding.get("uniform_row_config_hash")
        != next(iter(final_config_hashes))
    ):
        raise ValueError("fresh375 run-start/final config binding mismatch")
    if any(
        str((row.get("run_meta") or {}).get("run_id") or "") != run_id
        for row in partial_rows
    ):
        raise ValueError("fresh375 run-start partial row run id mismatch")
    start_manifest_record = receipt.get("run_manifest")
    if not isinstance(start_manifest_record, dict):
        raise ValueError("fresh375 run-start manifest binding missing")
    start_manifest_path = _recorded_path(start_manifest_record.get("path"))
    if not start_manifest_path.is_file():
        raise ValueError("fresh375 run-start manifest snapshot missing")
    start_manifest = _load_json_path(start_manifest_path)
    _validate_artifact_binding(
        record=start_manifest_record,
        expected_path=start_manifest_path,
        expected_payload=start_manifest,
        label="fresh375 run-start manifest snapshot",
    )
    if (
        start_manifest_path == resolved["merged_manifest"]
        or start_manifest.get("run_id") != run_id
        or any(start_manifest.get(field) != value for field, value in observed.items())
    ):
        raise ValueError("fresh375 run-start manifest snapshot mismatch")
    boundary = receipt.get("approval_boundary")
    if (
        not isinstance(boundary, dict)
        or boundary.get("run_start_binding_is_not_completion_or_semantic_approval")
        is not True
        or boundary.get("production_full_scan_approval") is not False
    ):
        raise ValueError("fresh375 run-start receipt approval boundary invalid")
    return {
        "report_type": receipt.get("report_type"),
        "binding_phase": receipt.get("binding_phase"),
        "path": str(receipt_path),
        "sha256": file_sha256(receipt_path),
        "run_id": run_id,
        "release_fingerprint_sha256": runtime_trust["release_fingerprint"],
    }


def validate_authoritative_scope(
    *,
    baseline_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    golden_manifest: Any,
    trust_bundle: dict[str, Any],
    expected_scope_rows: int,
    expected_golden_rows: int,
) -> dict[str, Any]:
    paths = trust_bundle.get("artifact_paths")
    anchors = trust_bundle.get("anchors")
    if not isinstance(paths, dict) or not isinstance(anchors, dict):
        raise ValueError("authoritative trust bundle paths/anchors missing")
    required_paths = {
        "baseline_result",
        "baseline_manifest",
        "source_input",
        "after_result",
        "merged_manifest",
        "merged_checkpoint",
        "merged_pending",
        "merge_binding_receipt",
        "golden_manifest",
        "golden_audit",
        "runtime_trust_anchor",
    }
    if set(paths) & required_paths != required_paths:
        raise ValueError("authoritative trust bundle artifact paths incomplete")
    initial_resolved = {key: Path(str(paths[key])).resolve() for key in required_paths}
    initial_missing = sorted(key for key, path in initial_resolved.items() if not path.is_file())
    if initial_missing:
        raise ValueError(f"authoritative artifacts missing: {initial_missing}")
    runtime_trust_anchor = _load_json_path(initial_resolved["runtime_trust_anchor"])
    if not isinstance(runtime_trust_anchor, dict):
        raise ValueError("runtime trust anchor must be an object")
    topology = runtime_trust_anchor.get("topology")
    profile = str((topology or {}).get("profile") or "") if isinstance(topology, dict) else ""
    fresh375_consumer_contract: str | None = None
    compiled_fresh_anchor_path: Path | None = None
    compiled_fresh_anchor_sha256: str | None = None
    if profile == INTERRUPTED_PROFILE:
        if not paths.get("merge_integrity"):
            raise ValueError("interrupted profile requires merge integrity artifact")
        required_paths.add("merge_integrity")
    elif profile == FRESH375_PROFILE:
        fresh375_consumer_contract = str(
            trust_bundle.get("fresh375_consumer_contract") or ""
        ).strip()
        if fresh375_consumer_contract == FRESH375_CONSUMER_V2_CONTRACT:
            required_paths.update(
                {
                    "fresh_supervisor_start_event",
                    "fresh_snapshot_result",
                    "fresh_snapshot_manifest",
                    "fresh_final_continuity",
                }
            )
        elif fresh375_consumer_contract == FRESH375_LEGACY_CONSUMER_CONTRACT:
            if (
                expected_scope_rows == PRODUCTION_PANEL_ROWS
                and expected_golden_rows == PRODUCTION_GOLDEN_ROWS
            ):
                raise ValueError(
                    "production fresh375 legacy actual_run_start consumer is forbidden"
                )
        else:
            raise ValueError("fresh375 consumer contract missing or unsupported")
        compiled_path_value = anchors.get("compiled_fresh_anchor_path")
        compiled_sha_value = anchors.get("compiled_fresh_anchor_sha256")
        if not compiled_path_value or not compiled_sha_value:
            raise ValueError("fresh375 compiled anchor path/sha256 trust pin missing")
        compiled_fresh_anchor_path = _recorded_path(compiled_path_value)
        compiled_fresh_anchor_sha256 = _require_sha256(
            compiled_sha_value,
            "fresh375 compiled pre-run anchor",
        )
    else:
        raise ValueError("runtime trust anchor topology profile invalid")
    resolved = {key: Path(str(paths[key])).resolve() for key in required_paths}
    missing = sorted(key for key, path in resolved.items() if not path.is_file())
    if missing:
        raise ValueError(f"authoritative artifacts missing: {missing}")
    if expected_scope_rows == PRODUCTION_PANEL_ROWS and expected_golden_rows == PRODUCTION_GOLDEN_ROWS:
        pinned_paths = {
            "baseline_result": PRODUCTION_BASELINE_RESULT_PATH,
            "baseline_manifest": PRODUCTION_BASELINE_MANIFEST_PATH,
            "source_input": PRODUCTION_PANEL_SOURCE_PATH,
            "golden_manifest": PRODUCTION_GOLDEN_MANIFEST_PATH,
        }
        for key, expected_path in pinned_paths.items():
            if resolved[key] != expected_path:
                raise ValueError(f"production authoritative path mismatch: {key}")

    baseline_manifest = _load_json_path(resolved["baseline_manifest"])
    merged_manifest = _load_json_path(resolved["merged_manifest"])
    merged_checkpoint = load_json_or_jsonl(resolved["merged_checkpoint"])
    merged_pending = _load_json_path(resolved["merged_pending"])
    merge_binding_receipt = _load_json_path(resolved["merge_binding_receipt"])
    merge_integrity = (
        _load_json_path(resolved["merge_integrity"])
        if "merge_integrity" in resolved
        else None
    )
    golden_from_path = _load_json_path(resolved["golden_manifest"])
    golden_audit = _load_json_path(resolved["golden_audit"])
    baseline_from_path = load_json_or_jsonl(resolved["baseline_result"])
    source_from_path = load_json_or_jsonl(resolved["source_input"])
    after_from_path = load_json_or_jsonl(resolved["after_result"])
    if canonical_digest(baseline_from_path) != canonical_digest(baseline_rows):
        raise ValueError("baseline payload differs from authoritative path")
    if canonical_digest(source_from_path) != canonical_digest(source_rows):
        raise ValueError("source payload differs from authoritative path")
    if canonical_digest(after_from_path) != canonical_digest(after_rows):
        raise ValueError("after payload differs from authoritative path")
    if canonical_digest(golden_from_path) != canonical_digest(golden_manifest):
        raise ValueError("golden payload differs from authoritative path")
    from tools.audit_regression_safe_golden import build_audit as rebuild_golden_audit

    recomputed_golden_audit = rebuild_golden_audit(
        canary_rows=after_rows,
        golden_rows=_golden_rows(golden_manifest),
        run_manifest=merged_manifest,
        canary_result=resolved["after_result"],
        canary_manifest=resolved["merged_manifest"],
        golden_manifest=resolved["golden_manifest"],
    )
    golden_semantic_fields = (
        "report_type",
        "scope",
        "gate",
        "after_result_sha256",
        "after_result_payload_sha256",
        "after_post_id_order_sha256",
        "after_post_id_set_sha256",
        "merged_manifest_sha256",
        "golden_manifest_sha256",
        "runtime",
        "runtime_full375_source",
        "audited_golden_rows",
        "row_count",
        "passed_count",
        "failed_count",
        "negative_no_public_work_count",
        "negative_no_public_work_passed",
        "positive_expected_work_count",
        "positive_expected_work_passed",
        "status_counts",
        "role_counts",
        "canary_semantic_gate",
        "rows",
    )
    if any(
        golden_audit.get(field) != recomputed_golden_audit.get(field)
        for field in golden_semantic_fields
    ):
        raise ValueError("golden audit does not match independent recomputation")

    byte_hashes = {key: file_sha256(path) for key, path in resolved.items()}
    if byte_hashes["baseline_manifest"] != _require_sha256(
        anchors.get("baseline_manifest_sha256"), "trusted baseline manifest"
    ):
        raise ValueError("trusted baseline manifest sha256 mismatch")
    if byte_hashes["source_input"] != _require_sha256(
        anchors.get("panel_source_sha256"), "trusted panel source"
    ):
        raise ValueError("trusted panel source sha256 mismatch")
    if byte_hashes["golden_manifest"] != _require_sha256(
        anchors.get("golden_manifest_sha256"), "trusted golden manifest"
    ):
        raise ValueError("trusted golden manifest sha256 mismatch")
    if expected_scope_rows == PRODUCTION_PANEL_ROWS and expected_golden_rows == PRODUCTION_GOLDEN_ROWS:
        pinned_hashes = {
            "baseline_manifest_sha256": PRODUCTION_BASELINE_MANIFEST_SHA256,
            "panel_source_sha256": PRODUCTION_PANEL_SOURCE_SHA256,
            "golden_manifest_sha256": PRODUCTION_GOLDEN_MANIFEST_SHA256,
        }
        for field, expected_hash in pinned_hashes.items():
            if anchors.get(field) != expected_hash:
                raise ValueError(f"production trust root override forbidden: {field}")

    if baseline_manifest.get("report_type") != "adjusted_baseline_manifest":
        raise ValueError("baseline manifest report_type invalid")
    if baseline_manifest.get("rebaseline_status") != "APPLIED":
        raise ValueError("baseline manifest rebaseline_status must be APPLIED")
    if baseline_manifest.get("baseline_mode") != "adjudicated_rebaseline":
        raise ValueError("baseline manifest mode invalid")
    if int((baseline_manifest.get("summary") or {}).get("baseline_result_rows") or -1) != expected_scope_rows:
        raise ValueError("baseline manifest row count mismatch")
    if (baseline_manifest.get("hashes") or {}).get("adjudicated_baseline_result_sha256") != byte_hashes[
        "baseline_result"
    ]:
        raise ValueError("baseline result is not bound to baseline manifest")
    baseline_artifact_path = (baseline_manifest.get("artifacts") or {}).get(
        "adjudicated_baseline_result"
    )
    if _recorded_path(baseline_artifact_path) != resolved["baseline_result"]:
        raise ValueError("baseline manifest artifact path mismatch")

    runtime_trust = _validate_runtime_trust_anchor(
        anchor=runtime_trust_anchor,
        anchor_path=resolved["runtime_trust_anchor"],
        anchor_byte_sha256=byte_hashes["runtime_trust_anchor"],
        resolved=resolved,
        byte_hashes=byte_hashes,
        baseline_rows=baseline_rows,
        source_rows=source_rows,
        golden_manifest=golden_manifest,
        expected_scope_rows=expected_scope_rows,
        expected_golden_rows=expected_golden_rows,
        compiled_fresh_anchor_path=compiled_fresh_anchor_path,
        compiled_fresh_anchor_sha256=compiled_fresh_anchor_sha256,
    )

    source_order = [post_id(row.get("post_id")) for row in source_rows]
    after_order = [post_id(row.get("post_id")) for row in after_rows]
    source_set = sorted(set(source_order))
    after_set = sorted(set(after_order))
    source_order_hash = canonical_digest(source_order)
    source_set_hash = canonical_digest(source_set)
    after_order_hash = canonical_digest(after_order)
    after_set_hash = canonical_digest(after_set)
    after_payload_hash = canonical_digest(after_rows)

    required_merged_counts = {
        "input_post_count": expected_scope_rows,
        "completed_count": expected_scope_rows,
        "flushed_count": expected_scope_rows,
        "pending_count": 0,
        "failed_count": 0,
    }
    for field, expected in required_merged_counts.items():
        if merged_manifest.get(field) != expected:
            raise ValueError(f"merged manifest {field} mismatch")
    if merged_manifest.get("large_run_complete") is not True:
        raise ValueError("merged manifest complete flag invalid")
    if _recorded_path(merged_manifest.get("output_file")) != resolved["after_result"]:
        raise ValueError("merged manifest output path mismatch")
    if _recorded_path(merged_manifest.get("checkpoint_jsonl")) != resolved[
        "merged_checkpoint"
    ]:
        raise ValueError("merged manifest checkpoint path mismatch")
    if _recorded_path(merged_manifest.get("pending_snapshot")) != resolved["merged_pending"]:
        raise ValueError("merged manifest pending path mismatch")
    if merged_pending != []:
        raise ValueError("merged/fresh375 pending snapshot must be empty")
    if len(merged_checkpoint) != expected_scope_rows:
        raise ValueError("merged/fresh375 checkpoint row count mismatch")
    for index, (checkpoint_row, after_row) in enumerate(
        zip(merged_checkpoint, after_rows),
        start=1,
    ):
        if (
            checkpoint_row.get("global_idx") != index
            or checkpoint_row.get("status") != "completed"
            or post_id(checkpoint_row.get("post_id")) != post_id(after_row.get("post_id"))
            or checkpoint_row.get("result") != after_row
        ):
            raise ValueError(f"merged/fresh375 checkpoint payload mismatch: {index}")
    row_run_ids = Counter(
        str((row.get("run_meta") or {}).get("run_id") or "")
        for row in after_rows
        if isinstance(row.get("run_meta"), dict)
    )
    if sum(row_run_ids.values()) != expected_scope_rows or "" in row_run_ids:
        raise ValueError("after result run_id coverage mismatch")
    immutable_runtime_keys = {
        "after_result",
        "merged_checkpoint",
        "merged_pending",
        "merged_manifest",
        "merge_binding_receipt",
    }
    if "merge_integrity" in resolved:
        immutable_runtime_keys.add("merge_integrity")
    writable_runtime_artifacts = sorted(
        key for key in immutable_runtime_keys if not _is_read_only_file(resolved[key])
    )
    if writable_runtime_artifacts:
        raise ValueError(
            f"completed runtime artifacts must be read-only: {writable_runtime_artifacts}"
        )
    runtime_binding_receipt = _validate_runtime_binding_receipt(
        receipt=merge_binding_receipt,
        receipt_path=resolved["merge_binding_receipt"],
        runtime_anchor=runtime_trust_anchor,
        runtime_trust=runtime_trust,
        resolved=resolved,
        after_rows=after_rows,
        merged_checkpoint=merged_checkpoint,
        merged_pending=merged_pending,
        merged_manifest=merged_manifest,
        merge_integrity=merge_integrity,
        fresh375_consumer_contract=fresh375_consumer_contract,
    )
    runtime_trust["binding_receipt"] = runtime_binding_receipt

    if runtime_trust["profile"] == INTERRUPTED_PROFILE:
        expected_recovered = int(runtime_trust["recovered_rows"])
        expected_residual = int(runtime_trust["residual_rows"])
        expected_source_run_id = runtime_trust["source_run_id"]
        expected_residual_run_id = runtime_trust["residual_run_id"]
        runtime_composition = (
            merged_manifest.get("runtime_composition")
            if isinstance(merged_manifest.get("runtime_composition"), dict)
            else {}
        )
        expected_composition = {
            "source_run_id": expected_source_run_id,
            "source_completed_rows": expected_recovered,
            "residual_run_id": expected_residual_run_id,
            "residual_completed_rows": expected_residual,
            "merge_integrity_gate": "GO",
        }
        if any(runtime_composition.get(key) != value for key, value in expected_composition.items()):
            raise ValueError("merged manifest runtime composition mismatch")
        merged_hash_expectations = {
            "input_post_id_order_sha256": source_order_hash,
            "input_post_id_set_sha256": source_set_hash,
            "result_payload_sha256": after_payload_hash,
            "stable_runtime_fingerprint_sha256": runtime_trust["fingerprint"],
        }
        for field, expected in merged_hash_expectations.items():
            if merged_manifest.get(field) != expected:
                raise ValueError(f"merged manifest {field} mismatch")
        stable_manifest = runtime_trust_anchor["stable_projection"]["manifest"]
        component_paths = runtime_trust_anchor.get("component_paths")
        immutable_components = runtime_trust_anchor.get("immutable_components")
        if not isinstance(component_paths, dict) or not isinstance(
            immutable_components, dict
        ):
            raise ValueError("interrupted component manifest bindings missing")
        source_manifest_path = _recorded_path(component_paths.get("source_manifest"))
        source_manifest = _load_json_path(source_manifest_path)
        if not isinstance(source_manifest, dict):
            raise ValueError("interrupted source component manifest must be an object")
        _validate_artifact_binding(
            record=immutable_components.get("source_manifest"),
            expected_path=source_manifest_path,
            expected_payload=source_manifest,
            label="interrupted source component manifest",
            require_read_only=False,
        )
        residual_runtime_artifacts = merge_binding_receipt.get(
            "residual_runtime_artifacts"
        )
        residual_manifest_binding = (
            residual_runtime_artifacts.get("manifest")
            if isinstance(residual_runtime_artifacts, dict)
            else None
        )
        if not isinstance(residual_manifest_binding, dict):
            raise ValueError("interrupted residual component manifest binding missing")
        residual_manifest_path = _recorded_path(
            residual_manifest_binding.get("path")
        )
        residual_manifest = _load_json_path(residual_manifest_path)
        if not isinstance(residual_manifest, dict):
            raise ValueError("interrupted residual component manifest must be an object")
        _validate_artifact_binding(
            record=residual_manifest_binding,
            expected_path=residual_manifest_path,
            expected_payload=residual_manifest,
            label="interrupted residual component manifest",
            require_read_only=False,
        )
        _validate_interrupted_dashboard_manifest_transition(
            stable_manifest=stable_manifest,
            source_manifest=source_manifest,
            residual_manifest=residual_manifest,
            merged_manifest=merged_manifest,
        )
        stable_row = runtime_trust_anchor["stable_projection"]["row"]
        for row in after_rows:
            run_meta = row.get("run_meta") if isinstance(row.get("run_meta"), dict) else {}
            if any(run_meta.get(field) != value for field, value in stable_row.items()):
                raise ValueError("merged after row stable projection mismatch")
        detached_trust_binding = runtime_binding_receipt["trust_anchor"]
        if merged_manifest.get("premerge_trust_anchor") != detached_trust_binding:
            raise ValueError("merged manifest runtime trust anchor binding mismatch")
        if not isinstance(merge_integrity, dict):
            raise ValueError("interrupted profile merge integrity missing")
        if merge_integrity.get("report_type") != "interrupted_run_original_order_merge_integrity":
            raise ValueError("merge integrity report_type invalid")
        if merge_integrity.get("gate") != "GO":
            raise ValueError("merge integrity gate must be GO")
        if merge_integrity.get("premerge_trust_anchor") != detached_trust_binding:
            raise ValueError("merge integrity runtime trust anchor binding mismatch")
        counts = merge_integrity.get("counts") if isinstance(merge_integrity.get("counts"), dict) else {}
        integrity_counts = {
            "source_rows": expected_scope_rows,
            "source_unique_post_ids": expected_scope_rows,
            "recovered_rows": expected_recovered,
            "recovered_checkpoint_completed_rows": expected_recovered,
            "residual_rows": expected_residual,
            "residual_checkpoint_completed_rows": expected_residual,
            "residual_pending_rows": 0,
            "merged_rows": expected_scope_rows,
            "merged_checkpoint_rows": expected_scope_rows,
        }
        for field, expected in integrity_counts.items():
            if counts.get(field) != expected:
                raise ValueError(f"merge integrity count mismatch: {field}")
        post_integrity = (
            merge_integrity.get("post_id_integrity")
            if isinstance(merge_integrity.get("post_id_integrity"), dict)
            else {}
        )
        if post_integrity.get("original_order_preserved") is not True:
            raise ValueError("merge original order not preserved")
        for field in ("overlap_post_ids", "missing_post_ids", "extra_post_ids", "duplicate_post_ids"):
            if post_integrity.get(field) != []:
                raise ValueError(f"merge post_id integrity not empty: {field}")
        runtime_homogeneity = (
            merge_integrity.get("runtime_homogeneity")
            if isinstance(merge_integrity.get("runtime_homogeneity"), dict)
            else {}
        )
        if (
            runtime_homogeneity.get("gate") != "GO"
            or runtime_homogeneity.get("stable_runtime_fingerprint_sha256")
            != runtime_trust["fingerprint"]
            or runtime_homogeneity.get("source_run_id") != expected_source_run_id
            or runtime_homogeneity.get("residual_run_id") != expected_residual_run_id
        ):
            raise ValueError("merge runtime homogeneity does not match trust anchor")
        if row_run_ids != Counter(
            {
                expected_source_run_id: expected_recovered,
                expected_residual_run_id: expected_residual,
            }
        ):
            raise ValueError("after result contains untrusted interrupted run ids")
        recovery = (
            merge_integrity.get("recovery")
            if isinstance(merge_integrity.get("recovery"), dict)
            else {}
        )
        if recovery.get("recovery_safe_to_use_as_completed_subset") is not True:
            raise ValueError("merge recovery subset is not safe")
        integrity_artifacts = (
            merge_integrity.get("artifacts")
            if isinstance(merge_integrity.get("artifacts"), dict)
            else {}
        )
        artifact_expectations = {
            "source_jsonl_sha256": byte_hashes["source_input"],
            "output_result_sha256": byte_hashes["after_result"],
            "output_manifest_sha256": byte_hashes["merged_manifest"],
            "trust_anchor_sha256": byte_hashes["runtime_trust_anchor"],
        }
        for field, expected in artifact_expectations.items():
            if integrity_artifacts.get(field) != expected:
                raise ValueError(f"merge integrity artifact hash mismatch: {field}")
        artifact_paths = {
            "source_jsonl": resolved["source_input"],
            "output_result": resolved["after_result"],
            "output_manifest": resolved["merged_manifest"],
            "trust_anchor": resolved["runtime_trust_anchor"],
        }
        for field, expected in artifact_paths.items():
            if _recorded_path(integrity_artifacts.get(field)) != expected:
                raise ValueError(f"merge integrity artifact path mismatch: {field}")
    else:
        expected_fresh_run_id = runtime_trust["fresh_run_id"]
        if len(row_run_ids) != 1:
            raise ValueError("fresh375 after result is not a single trusted run")
        actual_fresh_run_id = next(iter(row_run_ids))
        if row_run_ids[actual_fresh_run_id] != expected_scope_rows:
            raise ValueError("fresh375 after result run-id coverage mismatch")
        if expected_fresh_run_id is not None and actual_fresh_run_id != expected_fresh_run_id:
            raise ValueError("fresh375 actual run id differs from pre-run planned id")
        if merged_manifest.get("run_id") != actual_fresh_run_id:
            raise ValueError("fresh375 manifest run id mismatch")
        from tools.merge_interrupted_run_results import (
            _manifest_signature,
            _uniform_row_signature,
            _validate_plan_manifest_binding,
            _validate_row_manifest_binding,
        )

        observed_row_signature = _uniform_row_signature(after_rows, "fresh375")
        observed_manifest_signature = _manifest_signature(merged_manifest)
        _validate_row_manifest_binding(observed_row_signature, merged_manifest, "fresh375")
        _validate_plan_manifest_binding(
            runtime_trust_anchor["stable_projection"]["plan"],
            merged_manifest,
            "fresh375",
        )
        observed_fingerprint = canonical_digest(
            {
                "row": observed_row_signature,
                "manifest": observed_manifest_signature,
                "plan": runtime_trust_anchor["stable_projection"]["plan"],
            }
        )
        if merged_manifest.get("stable_runtime_fingerprint_sha256") not in (
            None,
            observed_fingerprint,
        ):
            raise ValueError("fresh375 observed runtime fingerprint mismatch")
        if (
            merged_manifest.get("requested_parallel") != 16
            or merged_manifest.get("effective_parallel") != 16
            or merged_manifest.get("mcp_health_include_search") is not True
            or merged_manifest.get("mcp_health_light_mode") is not False
            or merged_manifest.get("mcp_health_required_ok_count") != 16
            or int(merged_manifest.get("mcp_health_ok_count") or 0) < 16
            or merged_manifest.get("mcp_health_failure_count") != 0
            or merged_manifest.get("vlm_ocr_semantic_review_ready") is not True
            or merged_manifest.get("dashboard_enabled") is not True
        ):
            raise ValueError("fresh375 post-run runtime/search/VLM/dashboard contract invalid")
        manifest_binding = merged_manifest.get("premerge_trust_anchor")
        if manifest_binding is not None and manifest_binding != runtime_trust["binding"]:
            raise ValueError("fresh375 manifest runtime trust anchor binding mismatch")

    golden_audit_diagnostic = _validate_golden_audit_diagnostic_contract(
        golden_audit=golden_audit,
        expected_golden_rows=expected_golden_rows,
        canonical_audit_sha256=byte_hashes["golden_audit"],
    )
    audit_rows = golden_audit["rows"]
    golden_bindings = {
        "golden_manifest_sha256": byte_hashes["golden_manifest"],
        "after_result_sha256": byte_hashes["after_result"],
        "after_result_payload_sha256": after_payload_hash,
        "after_post_id_order_sha256": after_order_hash,
        "after_post_id_set_sha256": after_set_hash,
        "merged_manifest_sha256": byte_hashes["merged_manifest"],
    }
    for field, expected in golden_bindings.items():
        if golden_audit.get(field) != expected:
            raise ValueError(f"golden audit binding mismatch: {field}")
    audit_golden_path = golden_audit.get("golden_manifest_path") or golden_audit.get(
        "golden_manifest"
    )
    audit_after_path = golden_audit.get("after_result_path") or golden_audit.get("canary_result")
    audit_manifest_path = golden_audit.get("merged_manifest_path") or golden_audit.get(
        "canary_manifest"
    )
    if _recorded_path(audit_golden_path) != resolved["golden_manifest"]:
        raise ValueError("golden audit manifest path mismatch")
    if _recorded_path(audit_after_path) != resolved["after_result"]:
        raise ValueError("golden audit after path mismatch")
    if _recorded_path(audit_manifest_path) != resolved["merged_manifest"]:
        raise ValueError("golden audit runtime manifest path mismatch")
    audit_runtime = golden_audit.get("runtime") if isinstance(golden_audit.get("runtime"), dict) else {}
    if audit_runtime.get("pending_count") != 0 or audit_runtime.get("failed_count") != 0:
        raise ValueError("golden audit runtime invalid")
    full_runtime = (
        golden_audit.get("runtime_full375_source")
        if isinstance(golden_audit.get("runtime_full375_source"), dict)
        else {}
    )
    full_completed = full_runtime.get(
        "completed_count",
        audit_runtime.get("source_full375_completed_count", audit_runtime.get("completed_count")),
    )
    full_flushed = full_runtime.get("flushed_count")
    full_pending = full_runtime.get(
        "pending_count",
        audit_runtime.get("source_full375_pending_count", audit_runtime.get("pending_count")),
    )
    full_failed = full_runtime.get(
        "failed_count",
        audit_runtime.get("source_full375_failed_count", audit_runtime.get("failed_count")),
    )
    if (
        full_completed != expected_scope_rows
        or full_flushed != expected_scope_rows
        or full_pending != 0
        or full_failed != 0
        or full_runtime.get("source_result_row_count") != expected_scope_rows
        or full_runtime.get("large_run_complete") is not True
        or full_runtime.get("gate") != "GO"
    ):
        raise ValueError("golden audit full scope runtime invalid")
    golden_ids = [post_id(row.get("post_id")) for row in _golden_rows(golden_manifest)]
    audit_ids = [post_id(row.get("post_id")) for row in audit_rows if isinstance(row, dict)]
    if audit_ids != golden_ids:
        raise ValueError("golden audit rows are not exact canonical golden18 order")
    after_by_id = {post_id(row.get("post_id")): row for row in after_rows}
    for row in audit_rows:
        pid = post_id(row.get("post_id"))
        actual = row.get("actual_identity") if isinstance(row.get("actual_identity"), dict) else {}
        runtime_identity = identity_option(analysis_identity(after_by_id[pid]))
        audit_identity = identity_option(actual)
        if audit_identity != runtime_identity:
            raise ValueError(f"golden audit actual identity not bound to after result: {pid}")

    return {
        "trust_version": TRUST_VERSION,
        "artifact_paths": {key: str(path) for key, path in sorted(resolved.items())},
        "artifact_byte_sha256": dict(sorted(byte_hashes.items())),
        "anchors": {
            "baseline_manifest_sha256": anchors.get("baseline_manifest_sha256"),
            "panel_source_sha256": anchors.get("panel_source_sha256"),
            "golden_manifest_sha256": anchors.get("golden_manifest_sha256"),
            "runtime_trust_anchor_sha256": byte_hashes["runtime_trust_anchor"],
            "runtime_trust_anchor_payload_sha256": runtime_trust["anchor_payload_sha256"],
            "runtime_release_fingerprint_sha256": runtime_trust["release_fingerprint"],
            "runtime_topology_profile": runtime_trust["profile"],
            "stable_runtime_fingerprint_sha256": runtime_trust["fingerprint"],
            "runtime_code_tree_sha256": runtime_trust["code_tree_sha256"],
            "runtime_binding_receipt_sha256": byte_hashes["merge_binding_receipt"],
            "runtime_binding_receipt_report_type": runtime_binding_receipt[
                "report_type"
            ],
            "runtime_consumer_contract": runtime_binding_receipt.get(
                "consumer_contract"
            ),
            "runtime_current_fingerprint_sha256": runtime_binding_receipt.get(
                "current_runtime_fingerprint_sha256"
            ),
            "fresh375_final_continuity_sha256": runtime_binding_receipt.get(
                "final_continuity_sha256"
            ),
        },
        "source_order_sha256": source_order_hash,
        "source_set_sha256": source_set_hash,
        "after_order_sha256": after_order_hash,
        "after_set_sha256": after_set_hash,
        "after_payload_sha256": after_payload_hash,
        "golden_audit_diagnostic": golden_audit_diagnostic,
        "trust_root_digest": canonical_digest(
            {
                "byte_hashes": byte_hashes,
                "pinned_roots": {
                    "baseline_manifest_sha256": anchors.get("baseline_manifest_sha256"),
                    "panel_source_sha256": anchors.get("panel_source_sha256"),
                    "golden_manifest_sha256": anchors.get("golden_manifest_sha256"),
                },
                "runtime_trust": runtime_trust,
                "source_order": source_order_hash,
                "after_order": after_order_hash,
                "after_payload": after_payload_hash,
                "after_bytes": byte_hashes["after_result"],
            }
        ),
    }


def _compare_projection(compare: dict[str, Any]) -> dict[str, Any]:
    rows = compare.get("rows")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("collateral compare rows must be a list of objects")
    projected_rows = []
    for row in rows:
        projected_rows.append(
            {
                "post_id": row.get("post_id"),
                "status": row.get("status"),
                "is_regression": row.get("is_regression"),
                "exempted_by_expected_answer": row.get("exempted_by_expected_answer"),
                "before_identity": row.get("before_identity"),
                "after_identity": row.get("after_identity"),
            }
        )
    return {
        "baseline_mode": compare.get("baseline_mode"),
        "collateral_measure": compare.get("collateral_measure"),
        "expected_shared_posts": compare.get("expected_shared_posts"),
        "shared_post_count": compare.get("shared_post_count"),
        "changed_post_count": compare.get("changed_post_count"),
        "adjusted_drift_count": compare.get("adjusted_drift_count"),
        "collateral_regression_count": compare.get("collateral_regression_count"),
        "status_counts": compare.get("status_counts"),
        "regression_status_counts": compare.get("regression_status_counts"),
        "rows": sorted(projected_rows, key=drift_id_for),
    }


def prepare_bound_scope(
    *,
    compare: dict[str, Any],
    baseline_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    golden_manifest: Any,
    expected_scope_rows: int = PRODUCTION_PANEL_ROWS,
    expected_golden_rows: int = PRODUCTION_GOLDEN_ROWS,
    allow_multi_variant: bool = False,
    trust_bundle: dict[str, Any] | None = None,
    allow_untrusted_test_scope: bool = False,
) -> dict[str, Any]:
    if expected_scope_rows <= 0 or expected_golden_rows < 0:
        raise ValueError("expected scope sizes must be positive")
    baseline_order, baseline_by_id = _unique_index(baseline_rows, "baseline result")
    source_order, source_by_id = _unique_index(source_rows, "source input")
    if len(baseline_order) != expected_scope_rows:
        raise ValueError(f"baseline row count mismatch: {len(baseline_order)} != {expected_scope_rows}")
    if len(source_order) != expected_scope_rows:
        raise ValueError(f"source row count mismatch: {len(source_order)} != {expected_scope_rows}")
    if baseline_order != source_order:
        raise ValueError("baseline/source post_id order mismatch")

    after_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    after_first_order: list[str] = []
    for row in after_rows:
        pid = post_id(row.get("post_id"))
        if pid not in after_by_id:
            after_first_order.append(pid)
        after_by_id[pid].append(row)
    if after_first_order != source_order:
        raise ValueError("after/source post_id order mismatch")
    if set(after_by_id) != set(source_by_id):
        raise ValueError("after/source post_id set mismatch")
    if not allow_multi_variant and any(len(rows) != 1 for rows in after_by_id.values()):
        raise ValueError("after result duplicate post_id requires allow_multi_variant")
    for pid, variants in after_by_id.items():
        expected_source = source_payload(source_by_id[pid])
        for variant in variants:
            observed_source = source_payload(variant)
            missing_fields = [
                field
                for field in SOURCE_BINDING_FIELDS
                if field in expected_source and field not in observed_source
            ]
            if missing_fields:
                raise ValueError(
                    f"after/source binding fields missing for post_id {pid}: {sorted(missing_fields)}"
                )
            mismatched_fields = [
                field
                for field in SOURCE_BINDING_FIELDS
                if field in observed_source
                and field in expected_source
                and observed_source[field] != expected_source[field]
            ]
            if mismatched_fields:
                raise ValueError(
                    f"after/source payload mismatch for post_id {pid}: {sorted(mismatched_fields)}"
                )

    golden_rows = _golden_rows(golden_manifest)
    if len(golden_rows) != expected_golden_rows:
        raise ValueError(f"golden row count mismatch: {len(golden_rows)} != {expected_golden_rows}")
    golden_order, golden_by_id = _unique_index(golden_rows, "golden manifest")
    extra_golden = sorted(set(golden_order) - set(source_order))
    if extra_golden:
        raise ValueError(f"golden post_ids outside panel: {extra_golden}")

    drift_rows: list[dict[str, Any]] = []
    after_by_drift_id: dict[str, dict[str, Any]] = {}
    duplicate_drift_ids: list[str] = []
    for pid in source_order:
        expected = [golden_by_id[pid]] if pid in golden_by_id else []
        for variant_index, after_row in enumerate(after_by_id[pid], start=1):
            recomputed = compare_collateral(
                [baseline_by_id[pid]],
                [after_row],
                expected_rows=expected,
            )
            for raw_drift in recomputed["rows"]:
                drift = dict(raw_drift)
                did = drift_id_for(drift)
                if did in after_by_drift_id:
                    duplicate_drift_ids.append(did)
                    continue
                drift["drift_id"] = did
                drift["variant_index"] = variant_index
                drift_rows.append(drift)
                after_by_drift_id[did] = after_row
    if duplicate_drift_ids:
        raise ValueError(f"duplicate identical drift variants: {sorted(set(duplicate_drift_ids))}")

    status_counts = dict(Counter(row["status"] for row in drift_rows))
    regression_status_counts = dict(
        Counter(row["status"] for row in drift_rows if row.get("is_regression"))
    )
    expected_compare = {
        "baseline_mode": "adjudicated_rebaseline",
        "collateral_measure": "adjusted_drift",
        "expected_shared_posts": expected_scope_rows,
        "shared_post_count": expected_scope_rows,
        "changed_post_count": len(drift_rows),
        "adjusted_drift_count": len(drift_rows),
        "collateral_regression_count": sum(1 for row in drift_rows if row.get("is_regression")),
        "status_counts": status_counts,
        "regression_status_counts": regression_status_counts,
        "rows": [
            {key: value for key, value in row.items() if key not in {"drift_id", "variant_index"}}
            for row in drift_rows
        ],
    }
    if _compare_projection(compare) != _compare_projection(expected_compare):
        raise ValueError("collateral compare does not match recomputation from bound source artifacts")

    if allow_untrusted_test_scope:
        authoritative_trust = {
            "trust_version": TRUST_VERSION,
            "gate": "UNIT_TEST_UNTRUSTED",
            "trust_root_digest": None,
        }
    else:
        if not isinstance(trust_bundle, dict):
            raise ValueError("authoritative trust bundle is required")
        strict_runtime_counts = {
            "runtime_completed_count": expected_scope_rows,
            "runtime_flushed_count": expected_scope_rows,
            "runtime_pending_count": 0,
            "runtime_failed_count": 0,
        }
        for field, expected in strict_runtime_counts.items():
            if compare.get(field) != expected:
                raise ValueError(f"collateral compare authoritative runtime mismatch: {field}")
        authoritative_trust = {
            **validate_authoritative_scope(
                baseline_rows=baseline_rows,
                source_rows=source_rows,
                after_rows=after_rows,
                golden_manifest=golden_manifest,
                trust_bundle=trust_bundle,
                expected_scope_rows=expected_scope_rows,
                expected_golden_rows=expected_golden_rows,
            ),
            "gate": "GO",
        }

    source_hashes = {pid: canonical_digest(source_payload(source_by_id[pid])) for pid in source_order}
    input_hashes = {pid: canonical_digest(source_by_id[pid]) for pid in source_order}
    return {
        "scope_version": SCOPE_VERSION,
        "expected_scope_rows": expected_scope_rows,
        "expected_golden_rows": expected_golden_rows,
        "allow_multi_variant": allow_multi_variant,
        "post_id_order": source_order,
        "baseline_by_id": baseline_by_id,
        "source_by_id": source_by_id,
        "after_by_id": dict(after_by_id),
        "after_by_drift_id": after_by_drift_id,
        "golden_by_id": golden_by_id,
        "drift_rows": drift_rows,
        "drift_by_id": {row["drift_id"]: row for row in drift_rows},
        "source_hashes": source_hashes,
        "input_hashes": input_hashes,
        "compare_digest": canonical_digest(compare),
        "baseline_digest": canonical_digest(baseline_rows),
        "source_digest": canonical_digest(source_rows),
        "after_digest": canonical_digest(after_rows),
        "golden_digest": canonical_digest(golden_manifest),
        "authoritative_trust": authoritative_trust,
    }


def expected_blind_material(*, scope: dict[str, Any], packet_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packet_rows: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []
    authoritative_trust = (
        scope.get("authoritative_trust")
        if isinstance(scope.get("authoritative_trust"), dict)
        else {}
    )
    golden_audit_constraint = authoritative_trust.get("golden_audit_diagnostic")
    golden_audit_constraint_sha256 = (
        canonical_digest(golden_audit_constraint)
        if isinstance(golden_audit_constraint, dict)
        else None
    )
    for drift in scope["drift_rows"]:
        did = drift["drift_id"]
        pid = post_id(drift.get("post_id"))
        before_option = identity_option(drift.get("before_identity"))
        after_option = identity_option(drift.get("after_identity"))
        swap = int(hashlib.sha256(f"{packet_id}:{did}".encode("utf-8")).hexdigest(), 16) % 2 == 1
        ordered = (
            [("after", after_option), ("before", before_option)]
            if swap
            else [("before", before_option), ("after", after_option)]
        )
        packet = {
            "packet_version": PACKET_VERSION,
            "packet_id": packet_id,
            "drift_id": did,
            "post_id": drift.get("post_id"),
            "source": source_payload(scope["source_by_id"][pid]),
            "source_sha256": scope["source_hashes"][pid],
            "golden_audit_constraint_sha256": golden_audit_constraint_sha256,
            "candidate_options": [
                {"option_id": option_id, "identity": identity}
                for option_id, (_, identity) in zip(("A", "B"), ordered)
            ],
            "judge_contract": {
                "choose": ["A", "B", "EQUIVALENT", "NEITHER", "INSUFFICIENT"],
                "do_not_infer_before_after_order": True,
                "evaluate_work_identity_from_source_only": True,
            },
        }
        packet["packet_row_sha256"] = packet_row_digest(packet)
        packet_rows.append(packet)
        mapping_rows.append(
            {
                "drift_id": did,
                "post_id": drift.get("post_id"),
                "packet_row_sha256": packet["packet_row_sha256"],
                "drift_row_sha256": canonical_digest(drift),
                "status": drift.get("status"),
                "golden_audit_constraint_sha256": golden_audit_constraint_sha256,
                "option_origins": {
                    option_id: origin for option_id, (origin, _) in zip(("A", "B"), ordered)
                },
                "option_identity_sha256": {
                    option_id: canonical_digest(identity)
                    for option_id, (_, identity) in zip(("A", "B"), ordered)
                },
            }
        )
    private_map = {
        "report_type": "adjusted_collateral_blind_private_map",
        "packet_version": PACKET_VERSION,
        "packet_id": packet_id,
        "row_count": len(mapping_rows),
        "rows": mapping_rows,
        "rows_sha256": canonical_digest(mapping_rows),
        "golden_audit_constraint": golden_audit_constraint,
        "golden_audit_constraint_sha256": golden_audit_constraint_sha256,
        "approval_boundary": {
            "private_map_must_not_be_given_to_blind_judge": True,
            "packet_omits_before_after_status_and_golden_labels": True,
            "packet_binds_only_opaque_golden_audit_constraint_hash": True,
            "packet_generation_is_not_adjudication": True,
        },
    }
    return packet_rows, private_map


def validate_blind_material(
    *,
    scope: dict[str, Any],
    blind_packet_rows: list[dict[str, Any]],
    blind_map: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    packet_id = str(blind_map.get("packet_id") or "").strip()
    if not packet_id:
        return ["blind_map_packet_id_missing"]
    expected_packets, expected_map = expected_blind_material(scope=scope, packet_id=packet_id)
    if blind_packet_rows != expected_packets:
        issues.append("blind_packet_source_binding_mismatch")
    actual_map_projection = {
        key: blind_map.get(key)
        for key in (
            "report_type",
            "packet_version",
            "packet_id",
            "row_count",
            "rows",
            "rows_sha256",
            "golden_audit_constraint",
            "golden_audit_constraint_sha256",
            "approval_boundary",
        )
    }
    if actual_map_projection != expected_map:
        issues.append("blind_private_map_source_binding_mismatch")
    for packet in blind_packet_rows:
        if packet.get("packet_row_sha256") != packet_row_digest(packet):
            issues.append(f"packet_row_sha256_mismatch:{packet.get('drift_id')}")
    return issues


def build_blind_packet(
    *,
    compare: dict[str, Any],
    baseline_rows: list[dict[str, Any]],
    source_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    golden_manifest: Any,
    packet_id: str,
    expected_scope_rows: int = PRODUCTION_PANEL_ROWS,
    expected_golden_rows: int = PRODUCTION_GOLDEN_ROWS,
    allow_multi_variant: bool = False,
    trust_bundle: dict[str, Any] | None = None,
    allow_untrusted_test_scope: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
    packets, private_map = expected_blind_material(scope=scope, packet_id=packet_id)
    private_map["generated_at"] = datetime.now().replace(microsecond=0).isoformat()
    private_map["source_binding"] = {
        "scope_version": SCOPE_VERSION,
        "expected_scope_rows": expected_scope_rows,
        "expected_golden_rows": expected_golden_rows,
        "compare_digest": scope["compare_digest"],
        "baseline_digest": scope["baseline_digest"],
        "source_digest": scope["source_digest"],
        "after_digest": scope["after_digest"],
        "golden_digest": scope["golden_digest"],
        "authoritative_trust": scope["authoritative_trust"],
    }
    return packets, private_map


def _write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    path.chmod(stat.S_IREAD)


def _write_json_exclusive(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    path.chmod(stat.S_IREAD)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a source-bound anonymous A/B drift adjudication packet.")
    parser.add_argument("--collateral-compare", required=True, type=Path)
    parser.add_argument("--baseline-result", required=True, type=Path)
    parser.add_argument("--baseline-manifest", required=True, type=Path)
    parser.add_argument("--source-input", required=True, type=Path)
    parser.add_argument("--after-result", required=True, type=Path)
    parser.add_argument("--merged-manifest", required=True, type=Path)
    parser.add_argument("--merged-checkpoint", required=True, type=Path)
    parser.add_argument("--merged-pending", required=True, type=Path)
    parser.add_argument(
        "--runtime-binding-receipt",
        "--merge-binding-receipt",
        dest="merge_binding_receipt",
        required=True,
        type=Path,
    )
    parser.add_argument("--merge-integrity", type=Path)
    parser.add_argument("--runtime-trust-anchor", required=True, type=Path)
    parser.add_argument(
        "--fresh375-consumer-contract",
        choices=(
            FRESH375_CONSUMER_V2_CONTRACT,
            FRESH375_LEGACY_CONSUMER_CONTRACT,
        ),
        default=None,
    )
    parser.add_argument("--fresh-supervisor-start-event", type=Path)
    parser.add_argument("--fresh-snapshot-result", type=Path)
    parser.add_argument("--fresh-snapshot-manifest", type=Path)
    parser.add_argument("--fresh-final-continuity", type=Path)
    parser.add_argument("--compiled-fresh-anchor-path", type=Path)
    parser.add_argument("--compiled-fresh-anchor-sha256")
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--golden-audit", required=True, type=Path)
    parser.add_argument("--trusted-baseline-manifest-sha256", required=True)
    parser.add_argument("--trusted-panel-source-sha256", required=True)
    parser.add_argument("--trusted-golden-manifest-sha256", required=True)
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--private-map-json", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    compare = json.loads(args.collateral_compare.read_text(encoding="utf-8-sig"))
    golden = json.loads(args.golden_manifest.read_text(encoding="utf-8-sig"))
    packet_rows, private_map = build_blind_packet(
        compare=compare,
        baseline_rows=load_json_or_jsonl(args.baseline_result),
        source_rows=load_json_or_jsonl(args.source_input),
        after_rows=load_json_or_jsonl(args.after_result),
        golden_manifest=golden,
        packet_id=args.packet_id,
        expected_scope_rows=PRODUCTION_PANEL_ROWS,
        expected_golden_rows=PRODUCTION_GOLDEN_ROWS,
        trust_bundle={
            "fresh375_consumer_contract": args.fresh375_consumer_contract,
            "artifact_paths": {
                "baseline_result": args.baseline_result,
                "baseline_manifest": args.baseline_manifest,
                "source_input": args.source_input,
                "after_result": args.after_result,
                "merged_manifest": args.merged_manifest,
                "merged_checkpoint": args.merged_checkpoint,
                "merged_pending": args.merged_pending,
                "merge_binding_receipt": args.merge_binding_receipt,
                "golden_manifest": args.golden_manifest,
                "golden_audit": args.golden_audit,
                "runtime_trust_anchor": args.runtime_trust_anchor,
                **(
                    {
                        "fresh_supervisor_start_event": args.fresh_supervisor_start_event,
                        "fresh_snapshot_result": args.fresh_snapshot_result,
                        "fresh_snapshot_manifest": args.fresh_snapshot_manifest,
                        "fresh_final_continuity": args.fresh_final_continuity,
                    }
                    if all(
                        value is not None
                        for value in (
                            args.fresh_supervisor_start_event,
                            args.fresh_snapshot_result,
                            args.fresh_snapshot_manifest,
                            args.fresh_final_continuity,
                        )
                    )
                    else {}
                ),
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
                **(
                    {
                        "compiled_fresh_anchor_path": str(
                            args.compiled_fresh_anchor_path
                        ),
                        "compiled_fresh_anchor_sha256": args.compiled_fresh_anchor_sha256,
                    }
                    if args.compiled_fresh_anchor_path is not None
                    and args.compiled_fresh_anchor_sha256 is not None
                    else {}
                ),
            },
        },
    )
    _write_jsonl_exclusive(args.output_jsonl, packet_rows)
    private_map["artifacts"] = {
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
        "fresh375_consumer_contract": args.fresh375_consumer_contract,
        "compiled_fresh_anchor_path": (
            str(args.compiled_fresh_anchor_path)
            if args.compiled_fresh_anchor_path is not None
            else None
        ),
        "compiled_fresh_anchor_sha256": args.compiled_fresh_anchor_sha256,
        "fresh_supervisor_start_event": (
            str(args.fresh_supervisor_start_event)
            if args.fresh_supervisor_start_event is not None
            else None
        ),
        "fresh_supervisor_start_event_sha256": (
            file_sha256(args.fresh_supervisor_start_event)
            if args.fresh_supervisor_start_event is not None
            else None
        ),
        "fresh_snapshot_result": (
            str(args.fresh_snapshot_result)
            if args.fresh_snapshot_result is not None
            else None
        ),
        "fresh_snapshot_result_sha256": (
            file_sha256(args.fresh_snapshot_result)
            if args.fresh_snapshot_result is not None
            else None
        ),
        "fresh_snapshot_manifest": (
            str(args.fresh_snapshot_manifest)
            if args.fresh_snapshot_manifest is not None
            else None
        ),
        "fresh_snapshot_manifest_sha256": (
            file_sha256(args.fresh_snapshot_manifest)
            if args.fresh_snapshot_manifest is not None
            else None
        ),
        "fresh_final_continuity": (
            str(args.fresh_final_continuity)
            if args.fresh_final_continuity is not None
            else None
        ),
        "fresh_final_continuity_sha256": (
            file_sha256(args.fresh_final_continuity)
            if args.fresh_final_continuity is not None
            else None
        ),
        "golden_manifest": str(args.golden_manifest),
        "golden_manifest_sha256": file_sha256(args.golden_manifest),
        "golden_audit": str(args.golden_audit),
        "golden_audit_sha256": file_sha256(args.golden_audit),
        "blind_packet_jsonl": str(args.output_jsonl),
    }
    _write_json_exclusive(args.private_map_json, private_map)
    print(f"WROTE {args.output_jsonl} rows={len(packet_rows)}")
    print(f"WROTE {args.private_map_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
