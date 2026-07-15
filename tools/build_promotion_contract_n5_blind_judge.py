from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_regression_safe_golden import build_audit as rebuild_golden_audit
from tools.build_adjusted_collateral_adjudication import canonical_digest
from tools.build_adjusted_collateral_blind_packet import packet_row_digest
from tools.safe_loss_flip_rate_probe import (
    ACCEPTABLE_OUTCOME_LEGACY_FIELDS,
    ACCEPTABLE_OUTCOME_REQUIRED_FIELDS,
    OUTCOME_CONTRACT_FIELDS,
    row_outcome,
)


BUILDER_VERSION = "promotion-contract-n5-source-backed-blind-judge-v2"
EXPECTED_POST_IDS = (
    "11694035",
    "11663540",
    "11663514",
    "11682761",
    "11660237",
)
EXPECTED_STRATA = {
    "11694035": "aliases_including_아생갤",
    "11663540": "OCR",
    "11663514": "URL_canonical",
    "11682761": "context_only_HOLD",
    "11660237": "golden_stable",
}
GOLDEN_TARGET_STATUS = {
    "11694035": {"safe_resolved_or_evidence_preserved_unresolved"},
    # This older positive_expected_work row predates expected_status.  Its exact
    # row hash, expected title, and r6 semantic readback remain mandatory; the
    # judge materializes the same conservative resolved-or-preserved contract.
    "11663540": {None, "safe_resolved_or_evidence_preserved_unresolved"},
    "11660237": {"safe_resolved"},
}
ADJUDICATED_TARGETS = {
    "11694035": {"preferred_option": "A", "relation_to_post": "direct"},
    "11663540": {"preferred_option": "INSUFFICIENT", "relation_to_post": "insufficient"},
    "11663514": {"preferred_option": "A", "relation_to_post": "direct"},
    "11682761": {"preferred_option": "INSUFFICIENT", "relation_to_post": "insufficient"},
}
INDEPENDENT_IDENTITY_TARGETS = ("11663540",)
ADJUDICATION_ESSENTIAL_KEYS = (
    "derivation_version",
    "expected_scope_rows",
    "expected_golden_rows",
    "drift_ids",
    "drift_post_ids",
    "missing_verdict_drift_ids",
    "extra_verdict_drift_ids",
    "duplicate_verdict_drift_ids",
    "invalid_verdict_drift_ids",
    "unreviewed_adjusted_drift_ids",
    "unreviewed_adjusted_post_ids",
    "true_semantic_regression_drift_ids",
    "true_semantic_regression_post_ids",
    "classification_counts",
    "golden_audit_diagnostic",
    "validation_issues",
    "semantic_gate",
    "source_binding",
    "reviewed_rows",
)
R6_RECOMPUTED_FIELDS = (
    "after_result_sha256",
    "after_result_payload_sha256",
    "after_post_id_order_sha256",
    "after_post_id_set_sha256",
    "merged_manifest_sha256",
    "golden_manifest_sha256",
    "runtime",
    "runtime_full375_source",
    "audited_golden_rows",
    "golden_contract",
    "row_count",
    "passed_count",
    "failed_count",
    "negative_no_public_work_count",
    "negative_no_public_work_passed",
    "positive_expected_work_count",
    "positive_expected_work_passed",
    "status_counts",
    "role_counts",
    "semantic_quality",
    "full_scan_approval",
    "canary_semantic_gate",
    "rows",
)

# Judge requirements are normative policy, not a replay of whichever evidence
# route happened to win in the source r6 result.  Each publish route below keeps
# only the safety-critical provenance for its stratum.  In particular, OCR may
# publish through the canonical direct-image/OCR route without an incidental
# text-consumption or alias bridge, while a golden-stable row needs no
# release-context detail beyond a current-work bridge and the verified official
# title/URL identity.
PUBLISH_POLICY_BY_STRATUM: dict[str, dict[str, tuple[str, ...]]] = {
    "aliases_including_아생갤": {
        "reason_codes": ("alias_bridge", "official_detail_url"),
        "direct_bridge_sources": ("title_abbrev_mentioned", "official_detail_url"),
        "evidence_kinds": ("alias_bridge", "official_detail_url"),
        "evidence_reason_codes": ("alias_bridge", "official_detail_url"),
        "publish_supporting_evidence_kinds": ("alias_bridge",),
        "publish_supporting_evidence_reason_codes": ("alias_bridge",),
    },
    "OCR": {
        "reason_codes": (
            "direct_image_work_surface_bridge",
            "ocr_catalog_official_title",
            "official_detail_url",
        ),
        "direct_bridge_sources": (
            "ocr_catalog_official_title",
        ),
        "evidence_kinds": (
            "direct_image_work_surface",
            "ocr_catalog_official_title",
            "official_detail_url",
        ),
        "evidence_reason_codes": (
            "direct_image_work_surface_bridge",
            "ocr_catalog_official_title",
            "official_detail_url",
        ),
        "publish_supporting_evidence_kinds": (
            "direct_image_work_surface",
            "ocr_catalog_official_title",
        ),
        "publish_supporting_evidence_reason_codes": (
            "direct_image_work_surface_bridge",
            "ocr_catalog_official_title",
        ),
    },
    "URL_canonical": {
        "reason_codes": (
            "source_native_official_detail_identity",
            "source_native_non_image_work_relation_bridge",
        ),
        "direct_bridge_sources": (
            "source_native_non_image_work_relation_bridge",
        ),
        "evidence_kinds": (
            "source_native_official_detail_identity",
            "source_native_non_image_work_relation",
        ),
        "evidence_reason_codes": (
            "source_native_official_detail_identity",
            "source_native_non_image_work_relation_bridge",
        ),
        "publish_supporting_evidence_kinds": (
            "source_native_non_image_work_relation",
        ),
        "publish_supporting_evidence_reason_codes": (
            "source_native_non_image_work_relation_bridge",
        ),
    },
    "golden_stable": {
        "reason_codes": ("title_led_consumption_bridge", "official_detail_url"),
        "direct_bridge_sources": ("title_led_consumption_bridge",),
        "evidence_kinds": ("title_led_consumption", "official_detail_url"),
        "evidence_reason_codes": (
            "title_led_consumption_bridge",
            "official_detail_url",
        ),
        "publish_supporting_evidence_kinds": ("title_led_consumption",),
        "publish_supporting_evidence_reason_codes": (
            "title_led_consumption_bridge",
        ),
    },
}
HOLD_POLICY_BY_STRATUM = {
    "aliases_including_아생갤": "current_or_context",
    "OCR": "current_or_context",
    "URL_canonical": "none",
    "context_only_HOLD": "context_only",
    "golden_stable": "none",
}
POLICY_TEXT_BY_STRATUM = {
    "aliases_including_아생갤": (
        "정답 alias title/URL의 안전 publish 또는 같은 pair가 selected candidate와 "
        "inventory에 모두 남은 safe HOLD만 허용한다."
    ),
    "OCR": (
        "정답 OCR title/URL의 안전 publish 또는 같은 pair가 selected candidate와 "
        "inventory에 모두 남은 safe HOLD만 허용한다."
    ),
    "URL_canonical": "source-native canonical URL과 그 title의 안전 publish만 허용한다.",
    "context_only_HOLD": (
        "blind INSUFFICIENT이므로 public null, candidate-preserved context-only HOLD만 "
        "허용한다."
    ),
    "golden_stable": "Golden stable title/URL의 안전 publish만 허용한다.",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"JSONL row must be object: {path}:{line_number}")
            rows.append(value)
    return rows


def _load_result_rows(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = next(
            (
                payload[key]
                for key in ("results", "rows", "items")
                if isinstance(payload.get(key), list)
            ),
            None,
        )
    else:
        rows = None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"result must contain object rows: {path}")
    return rows


def _post_id(value: Any, label: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{label} post_id invalid")
    text = str(value or "").strip()
    if not text or not text.isdigit():
        raise ValueError(f"{label} post_id invalid")
    return text


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be a nonempty trimmed string")
    return value


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _sha(value: Any, label: str) -> str:
    text = _required_text(value, label).lower()
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ValueError(f"{label} must be lowercase sha256")
    return text


def _strict_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be int")
    return value


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be object")
    return value


def _object_rows(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{label} must be object row list")
    return value


def _resolve_path(value: Any, label: str) -> Path:
    raw = _required_text(value, label)
    path = Path(raw)
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _path_text(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _index_rows(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        post_id = _post_id(row.get("post_id"), label)
        if post_id in indexed:
            raise ValueError(f"{label} duplicate post_id: {post_id}")
        indexed[post_id] = row
    return indexed


def _verify_path_sha(
    path: Path, expected_sha256: Any, label: str, *, expected_path: Path | None = None
) -> str:
    if expected_path is not None and path.resolve() != expected_path.resolve():
        raise ValueError(f"{label} path mismatch")
    if not path.is_file():
        raise ValueError(f"{label} not found: {path}")
    expected = _sha(expected_sha256, f"{label} sha256")
    actual = file_sha256(path)
    if actual != expected:
        raise ValueError(f"{label} sha256 mismatch")
    return actual


def _validate_source_manifest(path: Path) -> dict[str, Any]:
    manifest = _mapping(_load_json(path), "source manifest")
    if manifest.get("manifest_type") != "loop642_promotion_contract_n5_source_input_manifest":
        raise ValueError("source manifest type mismatch")
    if manifest.get("gate") != "GO":
        raise ValueError("source manifest gate must be GO")
    scope = _mapping(manifest.get("scope"), "source manifest scope")
    for field, expected in (
        ("materialization_only", True),
        ("runtime_called", False),
        ("run_plan_created", False),
        ("repeats", 1),
        ("requested_strata_count", 5),
        ("row_count", 5),
        ("unique_post_ids", 5),
    ):
        if scope.get(field) != expected or type(scope.get(field)) is not type(expected):
            raise ValueError(f"source manifest scope {field} mismatch")
    for field in ("missing_post_ids", "extra_post_ids", "duplicate_post_ids"):
        if scope.get(field) != []:
            raise ValueError(f"source manifest scope {field} must be empty")

    source = _mapping(manifest.get("source"), "source manifest source")
    panel_path = _resolve_path(source.get("path"), "source panel path")
    source_expected = _sha(source.get("expected_byte_sha256"), "source expected sha256")
    if _sha(source.get("byte_sha256"), "source byte sha256") != source_expected:
        raise ValueError("source manifest source sha fields disagree")
    _verify_path_sha(panel_path, source_expected, "source panel")
    panel_rows = _load_jsonl(panel_path)
    if len(panel_rows) != _strict_int(source.get("panel_row_count"), "panel row count"):
        raise ValueError("source panel row count mismatch")
    if len(panel_rows) != 375:
        raise ValueError("source panel must contain exactly 375 rows")
    panel_by_id = _index_rows(panel_rows, "source panel")

    selection = _mapping(manifest.get("selection"), "source manifest selection")
    strata_rows = _object_rows(
        selection.get("requested_strata_order"), "requested strata order"
    )
    strata_ids = [_post_id(row.get("post_id"), "strata") for row in strata_rows]
    if tuple(strata_ids) != EXPECTED_POST_IDS:
        raise ValueError("requested strata post_ids mismatch")
    if [_post_id(value, "requested strata id") for value in selection.get("requested_strata_order_post_ids") or []] != list(EXPECTED_POST_IDS):
        raise ValueError("requested strata id mirror mismatch")
    selection_by_id: dict[str, dict[str, Any]] = {}
    for expected_order, row in enumerate(strata_rows, 1):
        post_id = _post_id(row.get("post_id"), "strata")
        if _strict_int(row.get("stratum_order"), "stratum order") != expected_order:
            raise ValueError(f"stratum order mismatch: {post_id}")
        if row.get("stratum") != EXPECTED_STRATA[post_id]:
            raise ValueError(f"stratum name mismatch: {post_id}")
        source_index = _strict_int(row.get("source_index_zero_based"), "source index")
        if source_index < 0 or source_index >= len(panel_rows):
            raise ValueError(f"source index out of range: {post_id}")
        source_row = panel_rows[source_index]
        if _post_id(source_row.get("post_id"), "source row") != post_id:
            raise ValueError(f"source index/post_id mismatch: {post_id}")
        row_hash = canonical_sha256(source_row)
        if _sha(row.get("source_row_canonical_sha256"), "source row sha256") != row_hash:
            raise ValueError(f"source row canonical sha256 mismatch: {post_id}")
        if panel_by_id[post_id] != source_row:
            raise ValueError(f"source panel index ambiguity: {post_id}")
        selection_by_id[post_id] = row

    artifact = _mapping(manifest.get("artifact"), "source manifest artifact")
    input_path = _resolve_path(artifact.get("path"), "N5 input path")
    input_expected = _sha(artifact.get("expected_byte_sha256"), "N5 input expected sha256")
    if _sha(artifact.get("byte_sha256"), "N5 input byte sha256") != input_expected:
        raise ValueError("N5 input manifest sha fields disagree")
    _verify_path_sha(input_path, input_expected, "N5 source input")
    if input_path.stat().st_size != _strict_int(artifact.get("bytes"), "N5 input bytes"):
        raise ValueError("N5 input size mismatch")
    input_rows = _load_jsonl(input_path)
    if len(input_rows) != 5 or artifact.get("rows") != 5 or artifact.get("unique_post_ids") != 5:
        raise ValueError("N5 input row count mismatch")
    input_by_id = _index_rows(input_rows, "N5 source input")
    input_ids = [_post_id(row.get("post_id"), "N5 source input") for row in input_rows]
    manifest_input_ids = [
        _post_id(value, "materialized id")
        for value in selection.get("materialized_original_source_order_post_ids") or []
    ]
    derived_input_rows = [
        row
        for row in panel_rows
        if _post_id(row.get("post_id"), "source panel") in set(EXPECTED_POST_IDS)
    ]
    derived_input_ids = [
        _post_id(row.get("post_id"), "derived N5 input") for row in derived_input_rows
    ]
    if input_ids != manifest_input_ids or input_ids != derived_input_ids:
        raise ValueError("N5 input original order mismatch")
    if input_rows != derived_input_rows:
        raise ValueError("N5 input rows are not exact source panel rows")
    if canonical_sha256([int(value) for value in input_ids]) != _sha(
        selection.get("materialized_original_source_order_sha256"),
        "materialized original order sha256",
    ):
        raise ValueError("N5 materialized order digest mismatch")
    _sha(selection.get("selection_sha256"), "selection sha256")
    if set(input_by_id) != set(EXPECTED_POST_IDS):
        raise ValueError("N5 input post_id set mismatch")
    return {
        "manifest": manifest,
        "manifest_path": path.resolve(),
        "manifest_sha256": file_sha256(path),
        "panel_path": panel_path,
        "panel_sha256": source_expected,
        "input_path": input_path,
        "input_sha256": input_expected,
        "input_rows": input_rows,
        "input_by_id": input_by_id,
        "selection_by_id": selection_by_id,
    }


def _validate_golden_manifest(path: Path) -> dict[str, Any]:
    payload = _mapping(_load_json(path), "golden manifest")
    rows = _object_rows(payload.get("rows"), "golden rows")
    if len(rows) != 18 or payload.get("golden_rows") != 18:
        raise ValueError("golden manifest must contain exactly 18 rows")
    indexed = _index_rows(rows, "golden manifest")
    for post_id, allowed_statuses in GOLDEN_TARGET_STATUS.items():
        row = indexed.get(post_id)
        if row is None:
            raise ValueError(f"golden target missing: {post_id}")
        if row.get("expected_status") not in allowed_statuses:
            raise ValueError(f"golden expected_status mismatch: {post_id}")
        if row.get("expected_no_public_title") is not False:
            raise ValueError(f"golden target unexpectedly null-only: {post_id}")
        _required_text(row.get("expected_title_or_hypothesis"), "golden expected title")
    for post_id in set(EXPECTED_POST_IDS) - set(GOLDEN_TARGET_STATUS):
        if post_id in indexed:
            raise ValueError(f"non-golden N5 target unexpectedly appears in golden manifest: {post_id}")
    if not _optional_text(indexed["11694035"].get("expected_url")):
        raise ValueError("alias golden expected_url missing")
    if not _optional_text(indexed["11660237"].get("expected_url")):
        raise ValueError("stable golden expected_url missing")
    return {
        "payload": payload,
        "rows": rows,
        "by_id": indexed,
        "path": path.resolve(),
        "sha256": file_sha256(path),
    }


def _validate_independent_identity_evidence(
    path: Path,
    *,
    golden: dict[str, Any],
) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("independent identity evidence must be an object")
    if payload.get("report_type") != "promotion_contract_n5_independent_identity_evidence":
        raise ValueError("independent identity evidence report_type mismatch")
    if payload.get("verification_status") != "SOURCE_VERIFIED":
        raise ValueError("independent identity evidence is not source verified")
    if payload.get("semantic_quality") != "REVIEW-LOCKED":
        raise ValueError("independent identity evidence must remain REVIEW-LOCKED")
    if payload.get("full_scan_approval") is not False:
        raise ValueError("independent identity evidence cannot approve full scan")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("independent identity evidence rows missing")
    by_id: dict[str, dict[str, str]] = {}
    row_bindings: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"independent identity evidence row {index} malformed")
        post_id = _post_id(row.get("post_id"), "independent identity evidence row")
        if post_id in by_id:
            raise ValueError("independent identity evidence duplicate post_id")
        title = _required_text(row.get("title"), "independent identity title")
        url = _required_text(row.get("url"), "independent identity URL")
        source_url = _required_text(
            row.get("source_url"), "independent identity source URL"
        )
        observed_title = _required_text(
            row.get("observed_title"), "independent observed title"
        )
        if row.get("verification_method") != "codex_web_primary_source":
            raise ValueError("independent identity verification method mismatch")
        if observed_title != title:
            raise ValueError("independent observed title mismatch")
        if source_url != url:
            raise ValueError("independent source URL must equal canonical URL")
        if re.fullmatch(r"https://novelpia\.com/novel/\d+", url) is None:
            raise ValueError("independent identity URL is not canonical novel detail")
        golden_row = golden["by_id"].get(post_id)
        if not isinstance(golden_row, dict):
            raise ValueError("independent identity post_id missing from golden")
        if _required_text(
            golden_row.get("expected_title_or_hypothesis"),
            "golden expected independent title",
        ) != title:
            raise ValueError("independent identity title differs from golden expectation")
        by_id[post_id] = {"title": title, "url": url}
        row_bindings[post_id] = {
            "row_sha256": canonical_sha256(row),
            "source_url": source_url,
            "verification_method": row["verification_method"],
        }
    if tuple(by_id) != INDEPENDENT_IDENTITY_TARGETS:
        raise ValueError("independent identity evidence scope mismatch")
    return {
        "payload": payload,
        "path": path.resolve(),
        "sha256": file_sha256(path),
        "by_id": by_id,
        "row_bindings": row_bindings,
    }


def _validate_adjudication(
    path: Path,
    *,
    source: dict[str, Any],
    golden: dict[str, Any],
) -> dict[str, Any]:
    payload = _mapping(_load_json(path), "Loop641 adjudication")
    if payload.get("report_type") != "adjusted_full375_collateral_adjudication":
        raise ValueError("Loop641 adjudication report_type mismatch")
    if payload.get("derivation_version") != "adjusted-collateral-adjudication-v2":
        raise ValueError("Loop641 adjudication derivation version mismatch")
    essential = {key: payload.get(key) for key in ADJUDICATION_ESSENTIAL_KEYS}
    if canonical_digest(essential) != _sha(
        payload.get("derivation_digest"), "Loop641 adjudication derivation digest"
    ):
        raise ValueError("Loop641 adjudication derivation digest mismatch")
    if payload.get("validation_issues") != []:
        raise ValueError("Loop641 adjudication validation issues are nonempty")
    source_binding = _mapping(payload.get("source_binding"), "adjudication source binding")
    authoritative = _mapping(
        source_binding.get("authoritative_trust"), "adjudication authoritative trust"
    )
    if authoritative.get("gate") != "GO":
        raise ValueError("adjudication authoritative trust gate must be GO")
    raw_judge = _mapping(source_binding.get("raw_judge_provenance"), "raw judge provenance")
    if raw_judge.get("gate") != "GO" or raw_judge.get("model") != "gpt-5.6-sol":
        raise ValueError("raw blind judge provenance is not authoritative")

    artifacts = _mapping(payload.get("artifacts"), "adjudication artifacts")
    artifact_golden = _resolve_path(artifacts.get("golden_manifest"), "adjudication golden path")
    _verify_path_sha(
        artifact_golden,
        artifacts.get("golden_manifest_sha256"),
        "adjudication golden manifest",
        expected_path=golden["path"],
    )
    artifact_source = _resolve_path(artifacts.get("source_input"), "adjudication source path")
    _verify_path_sha(
        artifact_source,
        artifacts.get("source_input_sha256"),
        "adjudication source panel",
        expected_path=source["panel_path"],
    )
    if file_sha256(artifact_source) != source["panel_sha256"]:
        raise ValueError("adjudication/source manifest panel hash mismatch")

    packet_path = _resolve_path(
        artifacts.get("blind_packet_jsonl"), "adjudication blind packet path"
    )
    packet_sha = _verify_path_sha(
        packet_path,
        artifacts.get("blind_packet_jsonl_sha256"),
        "adjudication blind packet",
    )
    packet_rows = _load_jsonl(packet_path)
    if canonical_digest(packet_rows) != _sha(
        source_binding.get("blind_packet_digest"), "blind packet canonical digest"
    ):
        raise ValueError("blind packet canonical digest mismatch")
    packet_by_drift: dict[str, dict[str, Any]] = {}
    for packet in packet_rows:
        drift_id = _required_text(packet.get("drift_id"), "blind packet drift_id")
        if drift_id in packet_by_drift:
            raise ValueError(f"blind packet duplicate drift_id: {drift_id}")
        if packet_row_digest(packet) != _sha(
            packet.get("packet_row_sha256"), "blind packet row sha256"
        ):
            raise ValueError(f"blind packet row digest mismatch: {drift_id}")
        if canonical_sha256(packet.get("source")) != _sha(
            packet.get("source_sha256"), "blind packet source sha256"
        ):
            raise ValueError(f"blind packet source digest mismatch: {drift_id}")
        packet_by_drift[drift_id] = packet

    blind_map_path = _resolve_path(
        artifacts.get("blind_map_json"), "adjudication blind map path"
    )
    _verify_path_sha(
        blind_map_path,
        artifacts.get("blind_map_json_sha256"),
        "adjudication blind map",
    )
    blind_map = _mapping(_load_json(blind_map_path), "blind private map")
    if canonical_digest(blind_map) != _sha(
        source_binding.get("blind_map_digest"), "blind map canonical digest"
    ):
        raise ValueError("blind private map canonical digest mismatch")
    map_rows = _object_rows(blind_map.get("rows"), "blind private map rows")
    map_by_drift: dict[str, dict[str, Any]] = {}
    for row in map_rows:
        drift_id = _required_text(row.get("drift_id"), "blind map drift_id")
        if drift_id in map_by_drift:
            raise ValueError(f"blind private map duplicate drift_id: {drift_id}")
        map_by_drift[drift_id] = row

    reviewed_rows = _object_rows(payload.get("reviewed_rows"), "adjudication reviewed rows")
    reviewed_by_post: dict[str, dict[str, Any]] = {}
    seen_drift_ids: set[str] = set()
    for row in reviewed_rows:
        drift_id = _required_text(row.get("drift_id"), "reviewed drift_id")
        if drift_id in seen_drift_ids:
            raise ValueError(f"adjudication duplicate reviewed drift_id: {drift_id}")
        seen_drift_ids.add(drift_id)
        post_id = _post_id(row.get("post_id"), "reviewed row")
        if post_id in ADJUDICATED_TARGETS:
            if post_id in reviewed_by_post:
                raise ValueError(f"adjudication target duplicate post_id: {post_id}")
            reviewed_by_post[post_id] = row
    if set(reviewed_by_post) != set(ADJUDICATED_TARGETS):
        raise ValueError("adjudication target missing/extra post_ids")

    target_packets: dict[str, dict[str, Any]] = {}
    for post_id, contract in ADJUDICATED_TARGETS.items():
        row = reviewed_by_post[post_id]
        if row.get("classification") != "true_semantic_regression":
            raise ValueError(f"adjudication target classification mismatch: {post_id}")
        if row.get("validation_issues") != []:
            raise ValueError(f"adjudication target validation issues: {post_id}")
        selection_hash = source["selection_by_id"][post_id]["source_row_canonical_sha256"]
        if _sha(row.get("input_hash"), "adjudication input hash") != selection_hash:
            raise ValueError(f"adjudication/source input hash mismatch: {post_id}")
        drift_id = _required_text(row.get("drift_id"), "reviewed drift_id")
        packet = packet_by_drift.get(drift_id)
        map_row = map_by_drift.get(drift_id)
        if packet is None or map_row is None:
            raise ValueError(f"adjudication target packet/map missing: {post_id}")
        packet_hash = _sha(packet.get("packet_row_sha256"), "packet row sha256")
        if _sha(row.get("packet_row_sha256"), "reviewed packet row sha256") != packet_hash:
            raise ValueError(f"reviewed/packet digest mismatch: {post_id}")
        if _post_id(packet.get("post_id"), "blind packet") != post_id:
            raise ValueError(f"reviewed/packet post_id mismatch: {post_id}")
        if _sha(row.get("source_hash"), "reviewed source hash") != _sha(
            packet.get("source_sha256"), "packet source hash"
        ):
            raise ValueError(f"reviewed/packet source hash mismatch: {post_id}")
        if _post_id(map_row.get("post_id"), "blind map") != post_id:
            raise ValueError(f"blind map post_id mismatch: {post_id}")
        if _sha(map_row.get("packet_row_sha256"), "blind map packet hash") != packet_hash:
            raise ValueError(f"blind map packet hash mismatch: {post_id}")
        verdict = _mapping(row.get("blind_verdict"), "blind verdict")
        if verdict.get("blind_to_baseline_preference") is not True:
            raise ValueError(f"blind verdict is not blind: {post_id}")
        if verdict.get("method") != "source_native_blind":
            raise ValueError(f"blind verdict method mismatch: {post_id}")
        if verdict.get("judge_model") != "gpt-5.6-sol":
            raise ValueError(f"blind verdict model mismatch: {post_id}")
        if verdict.get("preferred_option") != contract["preferred_option"]:
            raise ValueError(f"blind preferred option mismatch: {post_id}")
        if verdict.get("relation_to_post") != contract["relation_to_post"]:
            raise ValueError(f"blind relation mismatch: {post_id}")
        if _sha(verdict.get("packet_row_sha256"), "blind verdict packet hash") != packet_hash:
            raise ValueError(f"blind verdict packet hash mismatch: {post_id}")
        if _sha(verdict.get("delivered_packet_sha256"), "delivered packet hash") != packet_hash:
            raise ValueError(f"blind delivered packet hash mismatch: {post_id}")
        options = _object_rows(packet.get("candidate_options"), "blind candidate options")
        option_by_id: dict[str, dict[str, Any]] = {}
        for option in options:
            option_id = _required_text(option.get("option_id"), "blind option id")
            if option_id in option_by_id:
                raise ValueError(f"blind option duplicate: {post_id}/{option_id}")
            identity = _mapping(option.get("identity"), "blind option identity")
            option_by_id[option_id] = identity
            recorded_hash = _mapping(
                map_row.get("option_identity_sha256"), "option identity hashes"
            ).get(option_id)
            if canonical_sha256(identity) != _sha(recorded_hash, "option identity sha256"):
                raise ValueError(f"blind option identity hash mismatch: {post_id}/{option_id}")
        if set(option_by_id) != {"A", "B"}:
            raise ValueError(f"blind candidate options must be exactly A/B: {post_id}")
        target_packets[post_id] = {
            "packet": packet,
            "map": map_row,
            "reviewed": row,
            "options": option_by_id,
        }

    alias_title = golden["by_id"]["11694035"]["expected_title_or_hypothesis"]
    alias_selected = target_packets["11694035"]["options"]["A"]
    if alias_selected.get("official_title") != alias_title:
        raise ValueError("alias blind option/golden title mismatch")
    direct_selected = target_packets["11663514"]["options"]["A"]
    direct_title = _required_text(direct_selected.get("official_title"), "direct URL title")
    direct_url = _required_text(direct_selected.get("official_url"), "direct URL")
    direct_source_blob = json.dumps(
        target_packets["11663514"]["packet"].get("source"), ensure_ascii=False
    )
    if direct_url not in direct_source_blob:
        raise ValueError("direct canonical URL is not present in blind source")
    context_options = target_packets["11682761"]["options"]
    nonnull_context = [
        identity
        for identity in context_options.values()
        if _optional_text(identity.get("official_title"))
        or _optional_text(identity.get("official_url"))
    ]
    if len(nonnull_context) != 1:
        raise ValueError("context HOLD must have exactly one non-null candidate option")
    context_title = _required_text(
        nonnull_context[0].get("official_title"), "context HOLD candidate title"
    )
    context_url = _required_text(
        nonnull_context[0].get("official_url"), "context HOLD candidate URL"
    )
    return {
        "payload": payload,
        "path": path.resolve(),
        "sha256": file_sha256(path),
        "packet_path": packet_path,
        "packet_sha256": packet_sha,
        "blind_map_path": blind_map_path,
        "blind_map_sha256": file_sha256(blind_map_path),
        "targets": target_packets,
        "direct_identity": {"title": direct_title, "url": direct_url},
        "context_candidate": {"title": context_title, "url": context_url},
    }


def _candidate_pairs_from_identity(identity: dict[str, Any]) -> set[tuple[str, str | None]]:
    pairs: set[tuple[str, str | None]] = set()
    for key in ("title_candidates", "candidate_preservation_sources"):
        values = identity.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            title = _optional_text(
                value.get("official_title")
                or value.get("candidate_title")
                or value.get("title")
            )
            url = _optional_text(
                value.get("heretic_url")
                or value.get("official_url")
                or value.get("candidate_url")
                or value.get("url")
            )
            if title:
                pairs.add((title, url))
    return pairs


def _identity(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis_result")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("identity"), dict):
        raise ValueError(f"r6 identity missing: {row.get('post_id')}")
    return analysis["identity"]


def _validate_r6(
    audit_path: Path,
    result_path: Path,
    *,
    golden: dict[str, Any],
) -> dict[str, Any]:
    audit = _mapping(_load_json(audit_path), "r6 golden audit")
    if audit.get("report_type") != "golden18_bound_audit":
        raise ValueError("r6 golden audit report_type mismatch")
    if audit.get("canary_semantic_gate") != "PASS":
        raise ValueError("r6 canary semantic gate must be PASS")
    if audit.get("row_count") != 18 or audit.get("passed_count") != 18 or audit.get("failed_count") != 0:
        raise ValueError("r6 golden audit must be 18/18")
    recorded_result_path = Path(
        _required_text(audit.get("after_result_path"), "r6 audit result path")
    )
    recorded_golden_path = Path(
        _required_text(audit.get("golden_manifest_path"), "r6 audit golden path")
    )
    if _resolve_path(audit.get("after_result_path"), "r6 audit result path") != result_path.resolve():
        raise ValueError("r6 audit/result path mismatch")
    if _resolve_path(audit.get("golden_manifest_path"), "r6 audit golden path") != golden["path"]:
        raise ValueError("r6 audit/golden path mismatch")
    _verify_path_sha(result_path, audit.get("after_result_sha256"), "r6 result")
    if _sha(audit.get("golden_manifest_sha256"), "r6 audit golden sha256") != golden["sha256"]:
        raise ValueError("r6 audit/golden sha256 mismatch")
    recorded_manifest_path = Path(
        _required_text(audit.get("merged_manifest_path"), "r6 manifest path")
    )
    manifest_path = _resolve_path(audit.get("merged_manifest_path"), "r6 manifest path")
    _verify_path_sha(manifest_path, audit.get("merged_manifest_sha256"), "r6 manifest")
    result_rows = _load_result_rows(result_path)
    result_by_id = _index_rows(result_rows, "r6 result")
    if len(result_rows) != 18 or set(result_by_id) != set(golden["by_id"]):
        raise ValueError("r6 result/golden post_id coverage mismatch")
    manifest = _mapping(_load_json(manifest_path), "r6 manifest")
    rebuilt = rebuild_golden_audit(
        canary_rows=result_rows,
        golden_rows=golden["rows"],
        run_manifest=manifest,
        canary_result=recorded_result_path,
        canary_manifest=recorded_manifest_path,
        golden_manifest=recorded_golden_path,
    )
    for field in R6_RECOMPUTED_FIELDS:
        if audit.get(field) != rebuilt.get(field):
            raise ValueError(f"r6 golden audit recomputation mismatch: {field}")

    audit_rows = _index_rows(_object_rows(audit.get("rows"), "r6 audit rows"), "r6 audit")
    target_outcomes: dict[str, dict[str, Any]] = {}
    for post_id in GOLDEN_TARGET_STATUS:
        audit_row = audit_rows[post_id]
        if audit_row.get("passed") is not True:
            raise ValueError(f"r6 target audit failed: {post_id}")
        row = result_by_id[post_id]
        outcome = row_outcome(row)
        if outcome.get("canonical_publication_contract_gate") != "GO":
            raise ValueError(f"r6 target publication contract is not GO: {post_id}")
        if outcome.get("contract_version") != "promotion_contract_v2":
            raise ValueError(f"r6 target contract version mismatch: {post_id}")
        if outcome.get("bypassed_gate") is not False:
            raise ValueError(f"r6 target bypassed gate: {post_id}")
        target_outcomes[post_id] = outcome

    expected_pairs: dict[str, dict[str, str]] = {}
    for post_id in ("11694035", "11663540", "11660237"):
        expected_title = _required_text(
            golden["by_id"][post_id].get("expected_title_or_hypothesis"),
            f"golden expected title {post_id}",
        )
        result_identity = _identity(result_by_id[post_id])
        public = result_identity.get("novel_identity")
        public = public if isinstance(public, dict) else {}
        public_title = _optional_text(public.get("official_title"))
        public_url = _optional_text(public.get("heretic_url") or public.get("official_url"))
        candidate_pairs = _candidate_pairs_from_identity(result_identity)
        if public_title != expected_title and not any(
            title == expected_title for title, _url in candidate_pairs
        ):
            raise ValueError(f"r6 target expected title is neither public nor preserved: {post_id}")
        expected_url = _optional_text(golden["by_id"][post_id].get("expected_url"))
        if expected_url is None and public_title == expected_title:
            expected_url = public_url
        if expected_url is None:
            urls = sorted(
                {url for title, url in candidate_pairs if title == expected_title and url}
            )
            if len(urls) == 1:
                expected_url = urls[0]
        if expected_url is None:
            raise ValueError(f"r6/golden expected URL missing: {post_id}")
        if post_id == "11660237" and (public_title, public_url) != (
            expected_title,
            expected_url,
        ):
            raise ValueError("stable golden public title/URL mismatch")
        expected_pairs[post_id] = {"title": expected_title, "url": expected_url}
    return {
        "audit": audit,
        "audit_path": audit_path.resolve(),
        "audit_sha256": file_sha256(audit_path),
        "result_path": result_path.resolve(),
        "result_sha256": file_sha256(result_path),
        "manifest_path": manifest_path,
        "manifest_sha256": file_sha256(manifest_path),
        "result_by_id": result_by_id,
        "audit_rows": audit_rows,
        "target_outcomes": target_outcomes,
        "expected_pairs": expected_pairs,
    }


def _modern_outcome(
    *,
    public_title: str | None,
    public_url: str | None,
    candidate_title: str | None,
    candidate_url: str | None,
    decision_status: str,
    publish_allowed: bool,
    candidate_preserved: bool,
    scope_kind: str,
    required_reason_codes: Iterable[str],
    required_direct_bridge_sources: Iterable[str],
    required_evidence_kinds: Iterable[str],
    required_evidence_reason_codes: Iterable[str],
    required_publish_supporting_evidence_kinds: Iterable[str],
    required_publish_supporting_evidence_reason_codes: Iterable[str],
    forbidden_reason_codes: Iterable[str] = (),
    required_candidate_inventory_pairs: list[dict[str, str | None]] | None = None,
) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "public_title": public_title,
        "public_url": public_url,
        "candidate_title": candidate_title,
        "candidate_url": candidate_url,
        "decision_status": decision_status,
        "publish_allowed": publish_allowed,
        "candidate_preserved": candidate_preserved,
        "bypassed_gate": False,
        "scope_kind": scope_kind,
        "required_reason_codes": list(dict.fromkeys(required_reason_codes)),
        "required_direct_bridge_sources": list(
            dict.fromkeys(required_direct_bridge_sources)
        ),
        "required_evidence_kinds": list(dict.fromkeys(required_evidence_kinds)),
        "required_evidence_reason_codes": list(
            dict.fromkeys(required_evidence_reason_codes)
        ),
        "required_publish_supporting_evidence_kinds": list(
            dict.fromkeys(required_publish_supporting_evidence_kinds)
        ),
        "required_publish_supporting_evidence_reason_codes": list(
            dict.fromkeys(required_publish_supporting_evidence_reason_codes)
        ),
        "require_fingerprint": True,
        "require_contract_version": "promotion_contract_v2",
    }
    forbidden = list(dict.fromkeys(forbidden_reason_codes))
    if forbidden:
        outcome["forbidden_reason_codes"] = forbidden
    if required_candidate_inventory_pairs is not None:
        outcome["required_candidate_inventory_pairs"] = required_candidate_inventory_pairs
    _validate_modern_outcome_schema(outcome)
    return outcome


def _validate_modern_outcome_schema(outcome: dict[str, Any]) -> None:
    legacy = sorted(set(outcome) & ACCEPTABLE_OUTCOME_LEGACY_FIELDS)
    if legacy:
        raise ValueError(f"acceptable outcome contains legacy fields: {legacy}")
    unknown = sorted(set(outcome) - OUTCOME_CONTRACT_FIELDS)
    if unknown:
        raise ValueError(f"acceptable outcome contains unknown fields: {unknown}")
    missing = sorted(ACCEPTABLE_OUTCOME_REQUIRED_FIELDS - set(outcome))
    if missing:
        raise ValueError(f"acceptable outcome missing required fields: {missing}")
    for field in (
        "required_reason_codes",
        "required_direct_bridge_sources",
        "required_evidence_kinds",
        "required_evidence_reason_codes",
        "required_publish_supporting_evidence_kinds",
        "required_publish_supporting_evidence_reason_codes",
    ):
        values = outcome.get(field)
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value.strip() or value != value.strip()
            for value in values
        ):
            raise ValueError(f"acceptable outcome malformed {field}")
        if len(values) != len(set(values)):
            raise ValueError(f"acceptable outcome duplicate {field}")
    if outcome.get("publish_allowed") is True:
        for field in (
            "required_direct_bridge_sources",
            "required_publish_supporting_evidence_kinds",
            "required_publish_supporting_evidence_reason_codes",
        ):
            if not outcome[field]:
                raise ValueError(f"publish outcome requires nonempty {field}")
    if "required_candidate_inventory_pairs" in outcome:
        pairs = outcome["required_candidate_inventory_pairs"]
        if not isinstance(pairs, list) or not pairs:
            raise ValueError("required_candidate_inventory_pairs must be nonempty list")
        normalized: set[tuple[str | None, str | None]] = set()
        for pair in pairs:
            if not isinstance(pair, dict) or set(pair) != {"title", "url"}:
                raise ValueError("candidate inventory pair must contain exact title/url fields")
            title = pair.get("title")
            url = pair.get("url")
            if title is not None and (
                not isinstance(title, str) or not title.strip() or title != title.strip()
            ):
                raise ValueError("candidate inventory title malformed")
            if url is not None and (
                not isinstance(url, str) or not url.strip() or url != url.strip()
            ):
                raise ValueError("candidate inventory URL malformed")
            if title is None and url is None:
                raise ValueError("candidate inventory pair is empty")
            normalized_pair = (title, url)
            if normalized_pair in normalized:
                raise ValueError("candidate inventory pair duplicate")
            normalized.add(normalized_pair)


def _publish_outcome_for_policy(
    pair: dict[str, str], *, stratum: str
) -> dict[str, Any]:
    policy = PUBLISH_POLICY_BY_STRATUM.get(stratum)
    if policy is None:
        raise ValueError(f"stratum has no publish policy: {stratum}")
    title = _required_text(pair.get("title"), f"{stratum} authoritative title")
    url = _required_text(pair.get("url"), f"{stratum} authoritative URL")
    common_reasons = (
        "official_title_exists",
        "row_discusses_work_as_work",
        "scope_current_work",
        *policy["reason_codes"],
        "title_url_pair_verified",
    )
    return _modern_outcome(
        public_title=title,
        public_url=url,
        candidate_title=None,
        candidate_url=None,
        decision_status="publish",
        publish_allowed=True,
        candidate_preserved=False,
        scope_kind="current_work",
        required_reason_codes=common_reasons,
        required_direct_bridge_sources=policy["direct_bridge_sources"],
        required_evidence_kinds=policy["evidence_kinds"],
        required_evidence_reason_codes=policy["evidence_reason_codes"],
        required_publish_supporting_evidence_kinds=policy[
            "publish_supporting_evidence_kinds"
        ],
        required_publish_supporting_evidence_reason_codes=policy[
            "publish_supporting_evidence_reason_codes"
        ],
    )


def _safe_hold_outcomes(pair: dict[str, str], *, context_only_only: bool) -> list[dict[str, Any]]:
    pair_constraint = [{"title": pair["title"], "url": pair["url"]}]
    scopes = ("context_only",) if context_only_only else ("current_work", "context_only")
    outcomes: list[dict[str, Any]] = []
    for scope in scopes:
        scope_reasons = (
            ["scope_current_work"]
            if scope == "current_work"
            else ["scope_context_only", "scope_not_current_work"]
        )
        decision_statuses = (
            ("candidate_only", "hold")
            if scope == "current_work"
            else ("candidate_only",)
        )
        for decision_status in decision_statuses:
            outcomes.append(
                _modern_outcome(
                public_title=None,
                public_url=None,
                candidate_title=pair["title"],
                candidate_url=pair["url"],
                decision_status=decision_status,
                publish_allowed=False,
                candidate_preserved=True,
                scope_kind=scope,
                required_reason_codes=[
                    "official_title_exists",
                    *scope_reasons,
                    "official_detail_url",
                    "title_url_pair_verified",
                ],
                required_direct_bridge_sources=[],
                required_evidence_kinds=["official_detail_url"],
                required_evidence_reason_codes=["official_detail_url"],
                required_publish_supporting_evidence_kinds=[],
                required_publish_supporting_evidence_reason_codes=[],
                forbidden_reason_codes=["serialized_public_identity_published"],
                required_candidate_inventory_pairs=pair_constraint,
                )
            )
    return outcomes


def _outcomes_for_policy(
    pair: dict[str, str], *, stratum: str
) -> list[dict[str, Any]]:
    hold_policy = HOLD_POLICY_BY_STRATUM.get(stratum)
    if hold_policy is None:
        raise ValueError(f"unknown N5 policy stratum: {stratum}")
    outcomes: list[dict[str, Any]] = []
    if stratum in PUBLISH_POLICY_BY_STRATUM:
        outcomes.append(_publish_outcome_for_policy(pair, stratum=stratum))
    if hold_policy == "current_or_context":
        outcomes.extend(_safe_hold_outcomes(pair, context_only_only=False))
    elif hold_policy == "context_only":
        outcomes.extend(_safe_hold_outcomes(pair, context_only_only=True))
    elif hold_policy != "none":
        raise ValueError(f"unsupported hold policy for {stratum}: {hold_policy}")
    if not outcomes:
        raise ValueError(f"stratum has no acceptable outcomes: {stratum}")
    return outcomes


def _scan_runtime_literals(
    *,
    pairs: dict[str, dict[str, str]],
    runtime_source_paths: list[Path] | None,
) -> dict[str, Any]:
    if runtime_source_paths is None:
        files = [ROOT / "expert_main.py", *(ROOT / "src").rglob("*.py")]
    else:
        files = []
        for raw in runtime_source_paths:
            path = raw.resolve()
            if path.is_dir():
                files.extend(path.rglob("*.py"))
            else:
                files.append(path)
    unique_files = sorted({path.resolve() for path in files})
    if not unique_files or any(not path.is_file() for path in unique_files):
        raise ValueError("runtime source scan has missing or empty scope")
    forbidden = [*EXPECTED_POST_IDS]
    for pair in pairs.values():
        forbidden.extend((pair["title"], pair["url"]))
    forbidden = list(dict.fromkeys(value for value in forbidden if value))
    hits: list[dict[str, Any]] = []
    file_bindings: list[dict[str, str]] = []
    baseline_occurrence_count = 0
    current_occurrence_count = 0
    for path in unique_files:
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        path_text = _path_text(path)
        file_bindings.append({"path": path_text, "sha256": file_sha256(path)})
        baseline_text = ""
        if runtime_source_paths is None:
            try:
                relative = path.relative_to(ROOT).as_posix()
            except ValueError as exc:
                raise ValueError("default runtime source escaped repository root") from exc
            completed = subprocess.run(
                ["git", "show", f"HEAD:{relative}"],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            if completed.returncode == 0:
                baseline_text = completed.stdout.decode("utf-8-sig", errors="strict")
        for literal in forbidden:
            current_count = text.count(literal)
            baseline_count = baseline_text.count(literal)
            current_occurrence_count += current_count
            baseline_occurrence_count += baseline_count
            if current_count > baseline_count:
                hits.append(
                    {
                        "path": path_text,
                        "literal_sha256": hashlib.sha256(literal.encode("utf-8")).hexdigest(),
                        "baseline_count": baseline_count,
                        "current_count": current_count,
                        "new_count": current_count - baseline_count,
                    }
                )
    if hits:
        raise ValueError(f"forbidden N5 literal found in runtime source: {hits}")
    return {
        "gate": "GO",
        "checked_file_count": len(file_bindings),
        "checked_files_sha256": canonical_sha256(file_bindings),
        "forbidden_literal_count": len(forbidden),
        "baseline_occurrence_count": baseline_occurrence_count,
        "current_occurrence_count": current_occurrence_count,
        "new_occurrence_count": 0,
        "hit_count": 0,
        "hits": [],
        "scope_ko": "expert_main.py와 src/**/*.py production runtime source를 검사하고 git HEAD보다 늘어난 target literal만 금지했다. baseline 없는 새 파일은 0건 기준이다.",
    }


def build_judge(
    *,
    source_manifest_path: Path,
    golden_manifest_path: Path,
    blind_adjudication_path: Path,
    independent_identity_evidence_path: Path,
    r6_golden_audit_path: Path,
    r6_result_path: Path,
    runtime_source_paths: list[Path] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    source = _validate_source_manifest(source_manifest_path.resolve())
    golden = _validate_golden_manifest(golden_manifest_path.resolve())
    adjudication = _validate_adjudication(
        blind_adjudication_path.resolve(), source=source, golden=golden
    )
    independent_identity = _validate_independent_identity_evidence(
        independent_identity_evidence_path.resolve(),
        golden=golden,
    )
    r6 = _validate_r6(
        r6_golden_audit_path.resolve(), r6_result_path.resolve(), golden=golden
    )

    pairs = {
        "11694035": r6["expected_pairs"]["11694035"],
        "11663540": independent_identity["by_id"]["11663540"],
        "11663514": adjudication["direct_identity"],
        "11682761": adjudication["context_candidate"],
        "11660237": r6["expected_pairs"]["11660237"],
    }
    runtime_scan = _scan_runtime_literals(
        pairs=pairs, runtime_source_paths=runtime_source_paths
    )

    row_outcomes = {
        post_id: _outcomes_for_policy(
            pairs[post_id], stratum=EXPECTED_STRATA[post_id]
        )
        for post_id in EXPECTED_POST_IDS
    }
    rows: list[dict[str, Any]] = []
    for post_id in EXPECTED_POST_IDS:
        selection = source["selection_by_id"][post_id]
        evidence_refs: list[dict[str, Any]] = [
            {
                "artifact": "source_manifest",
                "post_id": int(post_id),
                "source_index_zero_based": selection["source_index_zero_based"],
                "source_row_canonical_sha256": selection[
                    "source_row_canonical_sha256"
                ],
            }
        ]
        if post_id in GOLDEN_TARGET_STATUS:
            evidence_refs.append(
                {
                    "artifact": "golden_manifest",
                    "golden_row_sha256": canonical_sha256(golden["by_id"][post_id]),
                    "expected_status": golden["by_id"][post_id].get("expected_status"),
                    "effective_expected_status": (
                        golden["by_id"][post_id].get("expected_status")
                        or "safe_resolved_or_evidence_preserved_unresolved"
                    ),
                }
            )
            evidence_refs.extend(
                [
                    {
                        "artifact": "r6_golden_audit",
                        "audit_row_sha256": canonical_sha256(r6["audit_rows"][post_id]),
                        "passed": r6["audit_rows"][post_id]["passed"],
                        "status": r6["audit_rows"][post_id]["status"],
                    },
                    {
                        "artifact": "r6_result",
                        "result_row_sha256": canonical_sha256(r6["result_by_id"][post_id]),
                        "publication_contract_gate": r6["target_outcomes"][post_id][
                            "canonical_publication_contract_gate"
                        ],
                    },
                ]
            )
        if post_id in ADJUDICATED_TARGETS:
            target = adjudication["targets"][post_id]
            evidence_refs.append(
                {
                    "artifact": "loop641_blind_adjudication",
                    "drift_id": target["reviewed"]["drift_id"],
                    "reviewed_row_sha256": canonical_sha256(target["reviewed"]),
                    "packet_row_sha256": target["packet"]["packet_row_sha256"],
                    "preferred_option": target["reviewed"]["blind_verdict"][
                        "preferred_option"
                    ],
                    "relation_to_post": target["reviewed"]["blind_verdict"][
                        "relation_to_post"
                    ],
                }
            )
        if post_id in independent_identity["by_id"]:
            evidence_refs.append(
                {
                    "artifact": "independent_identity_evidence",
                    **independent_identity["row_bindings"][post_id],
                }
            )
        rows.append(
            {
                "post_id": int(post_id),
                "stratum": EXPECTED_STRATA[post_id],
                "expected_policy_ko": POLICY_TEXT_BY_STRATUM[EXPECTED_STRATA[post_id]],
                "source_evidence": evidence_refs,
                "authoritative_identity": pairs[post_id],
                "acceptable_outcomes": row_outcomes[post_id],
            }
        )

    if tuple(_post_id(row.get("post_id"), "judge row") for row in rows) != EXPECTED_POST_IDS:
        raise AssertionError("internal N5 judge row order mismatch")
    for row in rows:
        outcomes = row.get("acceptable_outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            raise AssertionError("internal acceptable outcomes missing")
        for outcome in outcomes:
            _validate_modern_outcome_schema(outcome)

    tool_path = Path(__file__).resolve()
    matcher_path = (ROOT / "tools/safe_loss_flip_rate_probe.py").resolve()
    return {
        "report_type": "promotion_contract_n5_source_backed_blind_judge",
        "builder_version": BUILDER_VERSION,
        "generated_at": generated_at or datetime.now().replace(microsecond=0).isoformat(),
        "language": "ko",
        "gate": "GO",
        "semantic_quality": "REVIEW-LOCKED",
        "full_scan_approval": False,
        "production_approval": False,
        "scope": {
            "post_ids": [int(value) for value in EXPECTED_POST_IDS],
            "post_id_count": 5,
            "repeats_required": 5,
            "expected_independent_result_count": 25,
            "missing_post_ids": [],
            "extra_post_ids": [],
            "duplicate_post_ids": [],
        },
        "source_bindings": {
            "source_manifest": {
                "path": _path_text(source["manifest_path"]),
                "sha256": source["manifest_sha256"],
            },
            "source_panel": {
                "path": _path_text(source["panel_path"]),
                "sha256": source["panel_sha256"],
                "row_count": 375,
            },
            "n5_source_input": {
                "path": _path_text(source["input_path"]),
                "sha256": source["input_sha256"],
                "row_count": 5,
            },
            "golden_manifest": {
                "path": _path_text(golden["path"]),
                "sha256": golden["sha256"],
                "row_count": 18,
            },
            "independent_identity_evidence": {
                "path": _path_text(independent_identity["path"]),
                "sha256": independent_identity["sha256"],
                "row_count": len(independent_identity["by_id"]),
            },
            "loop641_blind_adjudication": {
                "path": _path_text(adjudication["path"]),
                "sha256": adjudication["sha256"],
            },
            "loop641_blind_packet": {
                "path": _path_text(adjudication["packet_path"]),
                "sha256": adjudication["packet_sha256"],
            },
            "loop641_blind_private_map": {
                "path": _path_text(adjudication["blind_map_path"]),
                "sha256": adjudication["blind_map_sha256"],
            },
            "r6_golden_audit": {
                "path": _path_text(r6["audit_path"]),
                "sha256": r6["audit_sha256"],
                "semantic_gate": r6["audit"]["canary_semantic_gate"],
            },
            "r6_result": {
                "path": _path_text(r6["result_path"]),
                "sha256": r6["result_sha256"],
                "row_count": 18,
            },
            "r6_manifest": {
                "path": _path_text(r6["manifest_path"]),
                "sha256": r6["manifest_sha256"],
            },
        },
        "builder_binding": {
            "path": _path_text(tool_path),
            "sha256": file_sha256(tool_path),
            "matcher_path": _path_text(matcher_path),
            "matcher_sha256": file_sha256(matcher_path),
        },
        "matcher_contract": {
            "style": "acceptable_outcomes",
            "evidence_requirement_derivation": (
                "stratum_policy_plus_authoritative_source_identity"
            ),
            "observed_r6_trace_requirement_copy_allowed": False,
            "legacy_fields_forbidden": sorted(ACCEPTABLE_OUTCOME_LEGACY_FIELDS),
            "all_required_fields_present": True,
            "unknown_field_count": 0,
            "candidate_inventory_constraint": "required exact title/URL pair must be a subset of typed inventory union; selected candidate alone is insufficient",
            "wrong_title_or_work_allowed": False,
            "bypassed_gate_allowed": False,
            "unsafe_publish_allowed": False,
        },
        "runtime_literal_scan": runtime_scan,
        "rows": rows,
        "approval_boundary": {
            "judge_materialization_is_not_runtime_completion": True,
            "n5_probe_is_not_full375_approval": True,
            "dashboard_is_not_approval": True,
            "production_approval": False,
        },
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Promotion Contract N=5 source-backed blind judge",
        "",
        f"- gate: `{report['gate']}`",
        f"- post_id_count: `{report['scope']['post_id_count']}`",
        f"- repeats_required: `{report['scope']['repeats_required']}`",
        f"- expected_independent_result_count: `{report['scope']['expected_independent_result_count']}`",
        f"- semantic_quality: `{report['semantic_quality']}`",
        f"- full_scan_approval: `{str(report['full_scan_approval']).lower()}`",
        f"- production_approval: `{str(report['production_approval']).lower()}`",
        "",
        "## 판정 계약",
        "",
        "- `acceptable_outcomes` modern schema만 사용하며 legacy `status/title/url`은 금지한다.",
        "- public title/URL, selected candidate title/URL, publish decision, scope, evidence, fingerprint, v2 contract를 함께 검사한다.",
        "- safe HOLD는 정답 title/URL pair가 selected candidate와 typed inventory union에 모두 있어야 한다.",
        "- wrong work/title, `bypassed_gate=true`, unsafe publish는 어떤 outcome에도 없다.",
        "",
        "## source binding",
        "",
    ]
    for name, binding in report["source_bindings"].items():
        lines.append(f"- {name}: `{binding['path']}` / `{binding['sha256']}`")
    lines.extend(["", "## 행별 허용 outcome", ""])
    for row in report["rows"]:
        identity = row["authoritative_identity"]
        lines.extend(
            [
                f"### `{row['post_id']}` · {row['stratum']}",
                "",
                f"- 계약: {row['expected_policy_ko']}",
                f"- authoritative title: `{identity['title']}`",
                f"- authoritative URL: `{identity['url']}`",
                f"- acceptable_outcomes: `{len(row['acceptable_outcomes'])}`",
                f"- source evidence refs: `{len(row['source_evidence'])}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 승인 경계",
            "",
            "이 파일 생성은 runtime 완료나 full375 승인, production 승인이 아니다. N=5x5 독립 결과는 동일 matcher와 runtime/search 계약으로 별도 분석해야 한다.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    report: dict[str, Any], *, output_json: Path, output_md: Path
) -> None:
    output_json = output_json.resolve()
    output_md = output_md.resolve()
    if output_json == output_md:
        raise ValueError("JSON and Markdown outputs must differ")
    if output_json.exists() or output_md.exists():
        raise FileExistsError("output paths are exclusive-create and must not exist")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    json_created = False
    try:
        with output_json.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        json_created = True
        with output_md.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown_report(report))
    except BaseException:
        if json_created and not output_md.exists():
            output_json.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the source-backed Promotion Contract N=5 blind judge."
    )
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--golden-manifest", required=True, type=Path)
    parser.add_argument("--blind-adjudication", required=True, type=Path)
    parser.add_argument("--independent-identity-evidence", required=True, type=Path)
    parser.add_argument("--r6-golden-audit", required=True, type=Path)
    parser.add_argument("--r6-result", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_judge(
        source_manifest_path=args.source_manifest,
        golden_manifest_path=args.golden_manifest,
        blind_adjudication_path=args.blind_adjudication,
        independent_identity_evidence_path=args.independent_identity_evidence,
        r6_golden_audit_path=args.r6_golden_audit,
        r6_result_path=args.r6_result,
    )
    write_outputs(report, output_json=args.output_json, output_md=args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
