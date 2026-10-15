"""Pure, presented-only inventory for eight researched source URL candidates.

The component accepts exact caller-supplied bytes only. Seven historical pool
artifacts are pinned by path, byte length, and SHA-256; drift is rejected rather
than normalized. The known label-ledger parent-binding drift is preserved as a
blocker. No source is fetched, parsed, attested, judged, indexed, or credited.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
import unicodedata
from typing import Any, Mapping


ROW_SCHEMA = "p0_presented_source_seed_candidate_row_v1"
REGISTRY_INVENTORY_SCHEMA = "p0_presented_source_seed_registry_inventory_v1"
LEGACY_ROW_SCHEMA = "p0_presented_legacy_pool_artifact_row_v1"
POOL_SUMMARY_SCHEMA = "p0_presented_legacy_pool_summary_v1"
ROLE_BLOCKER_SCHEMA = "p0_presented_legacy_pool_role_blocker_v1"
LEGACY_INVENTORY_SCHEMA = "p0_presented_legacy_pool_quality_inventory_v1"
RECEIPT_SCHEMA = "p0_presented_source_seed_candidate_receipt_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_source_seed_candidate_component_manifest_v1"
COMPONENT_VERSION = "presented-source-seed-candidate-inventory-v1"
RECORD_ORIGIN = "PRESENTED_UNVERIFIED"
OPERATIONAL_EFFECT = "NONE_SHADOW_ONLY"
GATE_STATUS = "NO_GO_PRESENTED_SOURCE_SEEDS_ONLY"
METRIC_STATUS = "NOT_ESTIMABLE"
EXPECTED_SEED_COUNT = 8
EXPECTED_TRACK_COUNTS = {"A": 3, "B": 5}
EXPECTED_LINEAGE_FAMILY_COUNT = 4
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_LEGACY_ARTIFACT_BYTES = 4 * 1024 * 1024

LEGACY_RUN_SPEC_PATH = "out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json"
LEGACY_COMPARISON_PATH = "out/candidate_set_nil_shadow_harness_20260711/v8/comparison.json"
LEGACY_LABEL_LEDGER_PATH = "docs/devs/p1_candidate_set_nil_golden18_label_ledger_20260711.json"
SOURCE_REFRESH_QUEUE_PATH = "out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_queue.json"
JUDGE3905_SHADOW_PATH = "out/judge3905_p0_seed_registry/judge3905_p0_candidate_ledger_shadow.jsonl"
ROWS_P01_PATH = "rows/full_post_judge_rows_p01.md"
ROWS_P02_PATH = "rows/full_post_judge_rows_p02.md"

# These literals describe the current evidence bytes. Changing any input is an
# identity failure, even if a caller coordinates new hashes and self-seals.
LEGACY_ARTIFACT_IDENTITIES = (
    ("RUN_SPEC", LEGACY_RUN_SPEC_PATH, 3249, "148c903cbae7664c79b5aa6cc4f0e7b5b7f20d243be9c050a746a7e5d3f71626"),
    ("COMPARISON", LEGACY_COMPARISON_PATH, 124062, "0dc5719e85e758ea4f3f68e89d44b48248b7117849bc61a45b411aef5220afe9"),
    ("LABEL_LEDGER", LEGACY_LABEL_LEDGER_PATH, 5434, "b7e75467744a1cf769763d459e3ebcfbf613bbaff703a0b6dedd55d29d905998"),
    ("SOURCE_REFRESH_QUEUE", SOURCE_REFRESH_QUEUE_PATH, 86246, "241b6c299066152b18fd84b7002235f38c8ce546ed0e59d96b20d0c23a48921f"),
    ("JUDGE3905_SHADOW", JUDGE3905_SHADOW_PATH, 2425983, "a768df069a68acc851d44590f9ff467b2aff23619377b8de14d9c1a18005eae3"),
    ("ROWS_P01", ROWS_P01_PATH, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    ("ROWS_P02", ROWS_P02_PATH, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
)
LEGACY_ARTIFACT_PATHS = tuple(item[1] for item in LEGACY_ARTIFACT_IDENTITIES)

SEED_SPECIFICATIONS = (
    ("seed-arca-novelchannel-abbreviation", "A", "https://arca.live/w/novelchannel/%EC%86%8C%EC%84%A4%20%EC%B6%95%EC%95%BD%EC%96%B4", "WORK_ALIAS_COLLABORATIVE_LIST", "lineage-arca-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-genrenovel-7614173", "A", "https://gall.dcinside.com/mgallery/board/view?id=genrenovel&no=7614173", "WORK_ALIAS_DASH_LIST_BACKUP", "lineage-arca-abbreviation-list", "BACKUP_SAME_LINEAGE"),
    ("seed-fmkorea-9330585139", "A", "https://www.fmkorea.com/9330585139", "WORK_ALIAS_EQUALS_LIST", "lineage-fmkorea-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-tgijjdd-217475", "B", "https://gall.dcinside.com/mgallery/board/view/?id=tgijjdd&no=217475", "COMMUNITY_GLOSSARY_FREE_PARAGRAPH", "lineage-dc-webnovel-jargon-list", "PRIMARY_CANDIDATE"),
    ("seed-tanma-ganadala", "B", "https://tanma.kr/data/webnovel_terms_ganadala.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-mabasa", "B", "https://tanma.kr/data/webnovel_terms_mabasa.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-ajacha", "B", "https://tanma.kr/data/webnovel_terms_ajacha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-katapaha", "B", "https://tanma.kr/data/webnovel_terms_katapaha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
)

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_CAPABILITY_FIELDS = (
    "raw_capture_allowed", "parser_execution_allowed", "claim_derivation_allowed",
    "derived_index_allowed", "publication_evidence_allowed",
)
_FALSE_AUTHORITY_FIELDS = (
    "source_enumeration_complete", "capture_authority_verified",
    "rights_authority_verified", "adapter_runtime_verified",
    "source_attestation_verified", "code_identity_verified",
    "actual_authority_granted", "production_approval", "full_scan_approval",
    "p0_phase_exit",
)
_FORBIDDEN_SEMANTIC_FIELDS = frozenset({
    "target_id", "target_work_id", "target_sense_id", "truth_kind",
    "truth_label", "definition", "judgment", "annotation_status",
    "publication_action",
})
_ROW_FIELDS = frozenset({
    "schema_version", "seed_sequence", "seed_id", "track", "record_type",
    "canonical_url", "format_hint", "source_profile_status", "source_lineage",
    "independence_group_id", "lineage_relation", "status", "attested_at",
    "attestation_status", "capture_status", "parser_status", "rights_status",
    "semantic_status", "independence_eligible", *_CAPABILITY_FIELDS, "row_sha256",
})


class P0PresentedSourceSeedCandidateError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedSourceSeedCandidateError("canonical JSON invalid") from exc


def canonical_file_bytes(value: Any) -> bytes:
    return canonical_bytes(value) + b"\n"


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def raw_sha256(value: bytes) -> str:
    if type(value) is not bytes:
        raise P0PresentedSourceSeedCandidateError("raw value must be exact bytes")
    return hashlib.sha256(value).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    material = dict(value)
    material.pop(field, None)
    return {**material, field: canonical_sha256(material)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise P0PresentedSourceSeedCandidateError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _constant(value: str) -> None:
    raise P0PresentedSourceSeedCandidateError(f"non-finite JSON forbidden: {value}")


def _json_document(raw: bytes, label: str, *, canonical: bool = False) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_LEGACY_ARTIFACT_BYTES or raw.startswith(b"\xef\xbb\xbf") or (canonical and b"\r" in raw):
        raise P0PresentedSourceSeedCandidateError(f"{label} framing invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0PresentedSourceSeedCandidateError(f"{label} NFC invalid")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, TypeError, ValueError) as exc:
        if isinstance(exc, P0PresentedSourceSeedCandidateError):
            raise
        raise P0PresentedSourceSeedCandidateError(f"{label} JSON invalid") from exc
    if type(value) is not dict or (canonical and raw != canonical_file_bytes(value)):
        raise P0PresentedSourceSeedCandidateError(f"{label} object/canonical mismatch")
    return value


def _jsonl_document(raw: bytes, label: str, *, canonical: bool) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_LEGACY_ARTIFACT_BYTES or raw.startswith(b"\xef\xbb\xbf") or not raw.endswith(b"\n") or raw.endswith(b"\n\n") or (canonical and b"\r" in raw):
        raise P0PresentedSourceSeedCandidateError(f"{label} framing invalid")
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(raw.splitlines(), start=1):
        if not line:
            raise P0PresentedSourceSeedCandidateError(f"{label} blank row {index}")
        row_raw = line + b"\n"
        rows.append(_json_document(row_raw, f"{label} row {index}", canonical=canonical))
    return rows


def _strict(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise P0PresentedSourceSeedCandidateError(f"{label} exact fields mismatch")
    if _FORBIDDEN_SEMANTIC_FIELDS.intersection(value):
        raise P0PresentedSourceSeedCandidateError(f"{label} semantic field forbidden")
    return value


def _integer(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedSourceSeedCandidateError(f"{field} must be non-bool integer >= {minimum}")
    return value


def _boolean(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedSourceSeedCandidateError(f"{field} must be bool")
    return value


def _sha(value: Any, field: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        raise P0PresentedSourceSeedCandidateError(f"{field} must be lowercase SHA-256")
    return value


def _self(row: Mapping[str, Any], field: str) -> None:
    material = dict(row)
    presented = material.pop(field, None)
    if _sha(presented, field) != canonical_sha256(material):
        raise P0PresentedSourceSeedCandidateError(f"{field} self-hash mismatch")


def _seed_rows_unchecked() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sequence, (seed_id, track, url, format_hint, lineage, relation) in enumerate(SEED_SPECIFICATIONS, start=1):
        material = {
            "schema_version": ROW_SCHEMA, "seed_sequence": sequence,
            "seed_id": seed_id, "track": track,
            "record_type": "WORK_ALIAS_LIST" if track == "A" else "COMMUNITY_LEXICON_LIST",
            "canonical_url": url, "format_hint": format_hint,
            "source_profile_status": "PENDING_CAPTURE_ADAPTER",
            "source_lineage": lineage, "independence_group_id": lineage,
            "lineage_relation": relation, "status": RECORD_ORIGIN,
            "attested_at": None, "attestation_status": "NOT_ATTESTED",
            "capture_status": "NOT_RUN", "parser_status": "NOT_RUN",
            "rights_status": "UNKNOWN_FAIL_CLOSED",
            "semantic_status": "REFERENCE_CANDIDATE_ONLY",
            "independence_eligible": False,
            **{field: False for field in _CAPABILITY_FIELDS},
        }
        rows.append({**material, "row_sha256": canonical_sha256(material)})
    return rows


COMPONENT_MANIFEST = {
    "schema_version": COMPONENT_MANIFEST_SCHEMA,
    "component_version": COMPONENT_VERSION,
    "record_origin": RECORD_ORIGIN,
    "expected_seed_count": EXPECTED_SEED_COUNT,
    "expected_track_counts": EXPECTED_TRACK_COUNTS,
    "expected_lineage_family_count": EXPECTED_LINEAGE_FAMILY_COUNT,
    "seed_specifications_sha256": canonical_sha256([list(item) for item in SEED_SPECIFICATIONS]),
    "legacy_artifact_identities": [
        {"artifact_role": role, "path": path, "bytes": size, "sha256": digest}
        for role, path, size, digest in LEGACY_ARTIFACT_IDENTITIES
    ],
    "legacy_artifact_identities_sha256": canonical_sha256([list(item) for item in LEGACY_ARTIFACT_IDENTITIES]),
    "max_legacy_artifact_bytes": MAX_LEGACY_ARTIFACT_BYTES,
    "network_access_allowed": False, "filesystem_access_allowed": False,
    "environment_access_allowed": False, "clock_access_allowed": False,
    "random_access_allowed": False, "subprocess_access_allowed": False,
    "import_side_effects_allowed": False, "semantic_field_injection_allowed": False,
    "legacy_binding_repair_allowed": False, "actual_credit_allowed": False,
}
COMPONENT_MANIFEST_SHA256 = canonical_sha256(COMPONENT_MANIFEST)


def build_registry_bytes() -> bytes:
    raw = b"".join(canonical_file_bytes(row) for row in _seed_rows_unchecked())
    validate_registry_bytes(raw)
    return raw


def validate_registry_bytes(raw: bytes) -> list[dict[str, Any]]:
    rows = _jsonl_document(raw, "source seed registry", canonical=True)
    expected = _seed_rows_unchecked()
    if rows != expected:
        raise P0PresentedSourceSeedCandidateError("source seed exact specification mismatch")
    for sequence, value in enumerate(rows, start=1):
        row = _strict(value, _ROW_FIELDS, f"source seed row {sequence}")
        if row["schema_version"] != ROW_SCHEMA or row["seed_sequence"] != sequence:
            raise P0PresentedSourceSeedCandidateError("source seed order mismatch")
        if _ID_RE.fullmatch(row["seed_id"]) is None or _ID_RE.fullmatch(row["source_lineage"]) is None:
            raise P0PresentedSourceSeedCandidateError("source seed identifier invalid")
        _self(row, "row_sha256")
    return rows


def _registry_inventory_value(registry_raw: bytes) -> dict[str, Any]:
    rows = validate_registry_bytes(registry_raw)
    families = sorted({row["source_lineage"] for row in rows})
    material = {
        "schema_version": REGISTRY_INVENTORY_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION,
        "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "registry_raw_sha256": raw_sha256(registry_raw), "registry_row_count": len(rows),
        "registry_rows_sha256": canonical_sha256(rows),
        "track_counts": dict(sorted(Counter(row["track"] for row in rows).items())),
        "lineage_family_count": len(families),
        "lineage_family_ids_sha256": canonical_sha256(families),
        "presented_unverified_count": len(rows), "rights_unknown_count": len(rows),
        "capture_not_run_count": len(rows), "parser_not_run_count": len(rows),
        "attestation_not_run_count": len(rows), "eligible_independence_group_count": 0,
    }
    return with_self_hash(material)


def build_registry_inventory_bytes(registry_raw: bytes) -> bytes:
    return canonical_file_bytes(_registry_inventory_value(registry_raw))


def validate_registry_inventory_bytes(raw: bytes, registry_raw: bytes) -> dict[str, Any]:
    value = _json_document(raw, "registry inventory", canonical=True)
    if value != _registry_inventory_value(registry_raw):
        raise P0PresentedSourceSeedCandidateError("registry inventory replay mismatch")
    _self(value, "artifact_sha256")
    return value


def _require_legacy_identities(artifacts: Mapping[str, bytes]) -> None:
    if type(artifacts) is not dict or tuple(artifacts.keys()) != LEGACY_ARTIFACT_PATHS:
        raise P0PresentedSourceSeedCandidateError("legacy artifact mapping must use exact ordered allowlist")
    for role, path, size, digest in LEGACY_ARTIFACT_IDENTITIES:
        raw = artifacts[path]
        if type(raw) is not bytes or len(raw) != size or raw_sha256(raw) != digest:
            raise P0PresentedSourceSeedCandidateError(f"legacy artifact identity pin mismatch: {role}")


def _validate_golden18(ledger: Mapping[str, Any], comparison: Mapping[str, Any]) -> dict[str, Any]:
    if ledger.get("schema_version") != "candidate-set-nil-label-ledger-v1":
        raise P0PresentedSourceSeedCandidateError("label ledger schema mismatch")
    rows = ledger.get("rows")
    if type(rows) is not list or len(rows) != 18:
        raise P0PresentedSourceSeedCandidateError("label ledger requires exact 18 rows")
    post_ids: list[int] = []
    labels: list[str] = []
    for index, row in enumerate(rows, start=1):
        if type(row) is not dict:
            raise P0PresentedSourceSeedCandidateError(f"label ledger row {index} invalid")
        post_id = _integer(row.get("post_id"), "label post_id", 1)
        label = row.get("truth_kind")
        if label not in {"CANDIDATE", "NIL", "UNJUDGED"}:
            raise P0PresentedSourceSeedCandidateError("label ledger label invalid")
        title = row.get("expected_title")
        if (label == "CANDIDATE" and (type(title) is not str or not title.strip())) or (label != "CANDIDATE" and title is not None):
            raise P0PresentedSourceSeedCandidateError("label ledger title/label shape mismatch")
        if label == "UNJUDGED" and row.get("expected_action") != "ABSTAIN":
            raise P0PresentedSourceSeedCandidateError("unjudged row must abstain")
        post_ids.append(post_id)
        labels.append(label)
    if len(set(post_ids)) != 18:
        raise P0PresentedSourceSeedCandidateError("label ledger post IDs must be unique")
    counts = Counter(labels)
    recomputed = {"rows": 18, "candidate_truth": counts["CANDIDATE"], "nil_truth": counts["NIL"], "unjudged": counts["UNJUDGED"]}
    presented = ledger.get("counts")
    if type(presented) is not dict or set(presented) != set(recomputed):
        raise P0PresentedSourceSeedCandidateError("label ledger counts shape mismatch")
    for key, expected in recomputed.items():
        if _integer(presented[key], f"label counts.{key}") != expected:
            raise P0PresentedSourceSeedCandidateError("label ledger counts replay mismatch")
    if sum(recomputed[key] for key in ("candidate_truth", "nil_truth", "unjudged")) != 18:
        raise P0PresentedSourceSeedCandidateError("label partition mismatch")
    if comparison.get("schema_version") != "candidate-set-nil-shadow-saved-artifact-v1":
        raise P0PresentedSourceSeedCandidateError("comparison schema mismatch")
    comparison_rows = comparison.get("rows")
    if type(comparison_rows) is not list or len(comparison_rows) != 18:
        raise P0PresentedSourceSeedCandidateError("comparison requires exact 18 rows")
    pairs = []
    for row in comparison_rows:
        if type(row) is not dict:
            raise P0PresentedSourceSeedCandidateError("comparison row invalid")
        pairs.append((_integer(row.get("post_id"), "comparison post_id", 1), row.get("truth_kind")))
    if pairs != list(zip(post_ids, labels)):
        raise P0PresentedSourceSeedCandidateError("comparison/label row cross-check mismatch")
    summary = comparison.get("summary")
    if type(summary) is not dict or summary.get("generation_status") != "UNKNOWN" or summary.get("candidate_set_recall") != "NOT_EVALUABLE":
        raise P0PresentedSourceSeedCandidateError("comparison metric boundary mismatch")
    if _integer(summary.get("unjudged"), "comparison unjudged") != recomputed["unjudged"]:
        raise P0PresentedSourceSeedCandidateError("comparison unjudged mismatch")
    for field, count_key in (("candidate_truth", "candidate_truth"), ("nil_truth", "nil_truth")):
        section = summary.get(field)
        if type(section) is not dict or _integer(section.get("expected"), f"comparison {field}.expected") != recomputed[count_key]:
            raise P0PresentedSourceSeedCandidateError("comparison label summary mismatch")
    return recomputed


def _validate_refresh_queue(queue: Mapping[str, Any]) -> dict[str, Any]:
    if queue.get("schema_version") != 1 or queue.get("semantic_quality") != "REVIEW-LOCKED" or _boolean(queue.get("full_scan_approval"), "refresh full_scan_approval") is not False:
        raise P0PresentedSourceSeedCandidateError("refresh queue gate mismatch")
    rows = queue.get("rows")
    if type(rows) is not list or len(rows) != 39:
        raise P0PresentedSourceSeedCandidateError("refresh queue requires exact 39 rows")
    post_ids: set[int] = set()
    url_count = 0
    pending = 0
    for row in rows:
        if type(row) is not dict:
            raise P0PresentedSourceSeedCandidateError("refresh row invalid")
        post_id = _integer(row.get("post_id"), "refresh post_id", 1)
        if post_id in post_ids:
            raise P0PresentedSourceSeedCandidateError("refresh post ID duplicate")
        post_ids.add(post_id)
        urls = row.get("source_urls")
        if type(urls) is not list or any(type(url) is not str or not url.startswith("http") for url in urls):
            raise P0PresentedSourceSeedCandidateError("refresh source URLs invalid")
        url_count += len(urls)
        pending += row.get("acceptance_status") == "pending_source_refresh"
    if url_count != 87 or pending != 39:
        raise P0PresentedSourceSeedCandidateError("refresh queue raw counts mismatch")
    coverage = queue.get("coverage")
    if type(coverage) is not dict or _integer(coverage.get("rows"), "refresh coverage.rows") != 39 or _integer(coverage.get("unique_post_ids"), "refresh coverage.unique_post_ids") != 39:
        raise P0PresentedSourceSeedCandidateError("refresh coverage mismatch")
    return {"rows": 39, "unique": 39, "urls": 87, "pending": 39}


_JUDGE_TOP_FIELDS = frozenset({"post_id", "seed_group", "disagreement_type", "severity", "agree", "likely_correct", "shadow_label", "candidate_ledger", "source", "judge"})
_JUDGE_LEDGER_FIELDS = frozenset({"pipeline_official_title", "title_candidates", "candidate_count", "title_resolution_state", "title_resolution_allowed", "work_resolution", "discussion_type", "topicality", "is_novel_related", "is_resolved_work_discussion", "anchor_type", "anchor_strength", "context_sources", "has_evidence_catalog", "official_title_lint_reasons", "identity_consistency_lint_reasons", "judge_likely_correct", "judge_note", "judge_claude_take"})
_JUDGE_SOURCE_FIELDS = frozenset({"source_path", "title", "url", "image_count", "has_image_url", "comment_count"})
_JUDGE_JUDGE_FIELDS = frozenset({"claude_take", "note", "batch"})


def _validate_judge_shadow(raw: bytes) -> dict[str, Any]:
    rows = _jsonl_document(raw, "judge3905 shadow", canonical=False)
    if len(rows) != 1505:
        raise P0PresentedSourceSeedCandidateError("judge3905 requires exact 1505 rows")
    post_ids: set[int] = set()
    candidate_positive = public_titles = evidence = web_unverified = 0
    for index, row in enumerate(rows, start=1):
        if set(row) != _JUDGE_TOP_FIELDS:
            raise P0PresentedSourceSeedCandidateError(f"judge row {index} shape mismatch")
        post_id = _integer(row["post_id"], "judge post_id", 1)
        if post_id in post_ids:
            raise P0PresentedSourceSeedCandidateError("judge post ID duplicate")
        post_ids.add(post_id)
        ledger = row["candidate_ledger"]
        source = row["source"]
        judge = row["judge"]
        if type(ledger) is not dict or set(ledger) != _JUDGE_LEDGER_FIELDS or type(source) is not dict or set(source) != _JUDGE_SOURCE_FIELDS or type(judge) is not dict or set(judge) != _JUDGE_JUDGE_FIELDS:
            raise P0PresentedSourceSeedCandidateError("judge nested shape mismatch")
        candidate_count = _integer(ledger["candidate_count"], "judge candidate_count")
        candidates = ledger["title_candidates"]
        if type(candidates) is not list or candidate_count != len(candidates):
            raise P0PresentedSourceSeedCandidateError("judge candidate count mismatch")
        candidate_positive += candidate_count > 0
        title = ledger["pipeline_official_title"]
        if title is not None and (type(title) is not str or not title.strip()):
            raise P0PresentedSourceSeedCandidateError("judge public title shape mismatch")
        public_titles += title is not None
        evidence += _boolean(ledger["has_evidence_catalog"], "has_evidence_catalog")
        note = judge["note"]
        if type(note) is not str:
            raise P0PresentedSourceSeedCandidateError("judge note must be string")
        web_unverified += "web_unverified" in note
    counts = {"rows": 1505, "unique": 1505, "candidate_positive": candidate_positive, "public_titles": public_titles, "evidence": evidence, "web_unverified": web_unverified}
    if counts != {"rows": 1505, "unique": 1505, "candidate_positive": 0, "public_titles": 198, "evidence": 2, "web_unverified": 649}:
        raise P0PresentedSourceSeedCandidateError("judge3905 raw counts mismatch")
    return counts


def _pool_summary(sequence: int, pool_id: str, role: str, grain: str, **values: Any) -> dict[str, Any]:
    common = {
        "schema_version": POOL_SUMMARY_SCHEMA, "pool_sequence": sequence,
        "pool_id": pool_id, "source_artifact_role": role, "grain": grain,
        "row_count": None, "unique_post_id_count": None, "url_reference_count": None,
        "candidate_labeled_count": None, "nil_labeled_count": None,
        "unjudged_count": None, "pending_count": None,
        "candidate_count_positive_count": None, "public_title_present_count": None,
        "evidence_catalog_present_count": None, "web_unverified_count": None,
        "empty_bytes_verified": False, "metric_status": METRIC_STATUS,
    }
    common.update(values)
    return {**common, "pool_sha256": canonical_sha256(common)}


def _legacy_inventory_value(artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    _require_legacy_identities(artifacts)
    run_spec = _json_document(artifacts[LEGACY_RUN_SPEC_PATH], "legacy run spec")
    comparison = _json_document(artifacts[LEGACY_COMPARISON_PATH], "legacy comparison")
    ledger = _json_document(artifacts[LEGACY_LABEL_LEDGER_PATH], "legacy label ledger")
    refresh = _json_document(artifacts[SOURCE_REFRESH_QUEUE_PATH], "source refresh queue")
    if run_spec.get("schema_version") != "candidate-set-nil-shadow-runspec-v1":
        raise P0PresentedSourceSeedCandidateError("legacy run spec schema mismatch")
    golden = _validate_golden18(ledger, comparison)
    refresh_counts = _validate_refresh_queue(refresh)
    judge_counts = _validate_judge_shadow(artifacts[JUDGE3905_SHADOW_PATH])
    expected_ledger = run_spec.get("artifacts", {}).get("label_ledger")
    expected_run_spec = comparison.get("run_spec")
    if type(expected_ledger) is not dict or type(expected_run_spec) is not dict:
        raise P0PresentedSourceSeedCandidateError("legacy parent references missing")
    rows: list[dict[str, Any]] = []
    for sequence, (role, path, size, digest) in enumerate(LEGACY_ARTIFACT_IDENTITIES, start=1):
        parent_bytes: int | None = None
        parent_sha: str | None = None
        if role == "RUN_SPEC":
            if expected_run_spec.get("path") != path:
                raise P0PresentedSourceSeedCandidateError("run spec parent path mismatch")
            parent_sha = expected_run_spec.get("sha256")
            status = "SHA_MATCH_BYTES_UNAVAILABLE" if parent_sha == digest and "bytes" not in expected_run_spec else "STALE_PARENT_BINDING"
        elif role == "LABEL_LEDGER":
            if expected_ledger.get("path") != path:
                raise P0PresentedSourceSeedCandidateError("label ledger parent path mismatch")
            parent_bytes = expected_ledger.get("bytes")
            parent_sha = expected_ledger.get("sha256")
            status = "PARENT_BINDING_MATCH" if parent_bytes == size and parent_sha == digest else "STALE_PARENT_BINDING"
        else:
            status = "IDENTITY_PIN_MATCH_NO_PARENT_BINDING"
        material = {
            "schema_version": LEGACY_ROW_SCHEMA, "artifact_sequence": sequence,
            "artifact_role": role, "path": path, "actual_bytes": len(artifacts[path]),
            "actual_sha256": raw_sha256(artifacts[path]), "pinned_bytes": size,
            "pinned_sha256": digest, "parent_expected_bytes": parent_bytes,
            "parent_expected_sha256": parent_sha, "binding_status": status,
            "identity_pin_verified": True,
            "stale_parent_binding": status == "STALE_PARENT_BINDING",
        }
        rows.append({**material, "row_sha256": canonical_sha256(material)})
    stale_roles = [row["artifact_role"] for row in rows if row["stale_parent_binding"]]
    role_blockers = [
        {"schema_version": ROLE_BLOCKER_SCHEMA, "artifact_role": role, "blocker_code": "LEGACY_LABEL_LEDGER_SHA256_BINDING_STALE"}
        for role in stale_roles
    ]
    if stale_roles != ["LABEL_LEDGER"]:
        raise P0PresentedSourceSeedCandidateError("unexpected legacy stale-role set")
    pools = [
        _pool_summary(1, "golden18_label_pool", "LABEL_LEDGER", "GOLDEN18_POST_LABEL_ROW", row_count=18, unique_post_id_count=18, candidate_labeled_count=golden["candidate_truth"], nil_labeled_count=golden["nil_truth"], unjudged_count=golden["unjudged"]),
        _pool_summary(2, "source_refresh_pool", "SOURCE_REFRESH_QUEUE", "SOURCE_REFRESH_POST_QUEUE_ROW", row_count=refresh_counts["rows"], unique_post_id_count=refresh_counts["unique"], url_reference_count=refresh_counts["urls"], pending_count=refresh_counts["pending"]),
        _pool_summary(3, "judge3905_shadow_pool", "JUDGE3905_SHADOW", "JUDGE3905_SHADOW_POST_ROW", row_count=judge_counts["rows"], unique_post_id_count=judge_counts["unique"], candidate_count_positive_count=judge_counts["candidate_positive"], public_title_present_count=judge_counts["public_titles"], evidence_catalog_present_count=judge_counts["evidence"], web_unverified_count=judge_counts["web_unverified"]),
        _pool_summary(4, "reserved_p01_pool", "ROWS_P01", "RESERVED_EMPTY_P01_BYTES", row_count=0, empty_bytes_verified=True),
        _pool_summary(5, "reserved_p02_pool", "ROWS_P02", "RESERVED_EMPTY_P02_BYTES", row_count=0, empty_bytes_verified=True),
    ]
    if len({pool["grain"] for pool in pools}) != len(pools):
        raise P0PresentedSourceSeedCandidateError("pool grains must be distinct")
    material = {
        "schema_version": LEGACY_INVENTORY_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION, "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "artifact_rows": rows, "artifact_rows_sha256": canonical_sha256(rows),
        "artifact_count": 7, "artifact_identity_pins_verified": True,
        "pool_summaries": pools, "pool_summaries_sha256": canonical_sha256(pools),
        "pool_count": 5, "distinct_pool_grain_count": 5,
        "must_not_sum_across_pools": True, "combined_unique_denominator": None,
        "combined_metric_denominator": 0, "legacy_metric_status": METRIC_STATUS,
        "stale_parent_binding_count": len(stale_roles), "stale_parent_binding_roles": stale_roles,
        "role_blockers": role_blockers, "role_blockers_sha256": canonical_sha256(role_blockers),
        "role_blocker_count": len(role_blockers),
    }
    return with_self_hash(material)


def build_legacy_quality_inventory_bytes(artifacts: Mapping[str, bytes]) -> bytes:
    return canonical_file_bytes(_legacy_inventory_value(artifacts))


def validate_legacy_quality_inventory_bytes(raw: bytes, artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    value = _json_document(raw, "legacy quality inventory", canonical=True)
    if value != _legacy_inventory_value(artifacts):
        raise P0PresentedSourceSeedCandidateError("legacy quality inventory replay mismatch")
    _self(value, "artifact_sha256")
    return value


def _receipt_value(registry_raw: bytes, registry_inventory_raw: bytes, legacy_inventory_raw: bytes, legacy_artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    rows = validate_registry_bytes(registry_raw)
    registry_inventory = validate_registry_inventory_bytes(registry_inventory_raw, registry_raw)
    legacy_inventory = validate_legacy_quality_inventory_bytes(legacy_inventory_raw, legacy_artifacts)
    blockers = ["SOURCE_BYTES_NOT_CAPTURED", "SOURCE_PARSER_NOT_RUN", "SOURCE_ATTESTATION_NOT_RUN", "SOURCE_RIGHTS_UNKNOWN", "ACTUAL_SOURCE_AND_CONTEXT_COUNTS_ZERO"]
    blockers.extend(blocker["blocker_code"] for blocker in legacy_inventory["role_blockers"])
    material = {
        "schema_version": RECEIPT_SCHEMA, "record_origin": RECORD_ORIGIN,
        "component_version": COMPONENT_VERSION, "component_manifest_sha256": COMPONENT_MANIFEST_SHA256,
        "registry_raw_sha256": raw_sha256(registry_raw),
        "registry_inventory_raw_sha256": raw_sha256(registry_inventory_raw),
        "registry_inventory_artifact_sha256": registry_inventory["artifact_sha256"],
        "legacy_inventory_raw_sha256": raw_sha256(legacy_inventory_raw),
        "legacy_inventory_artifact_sha256": legacy_inventory["artifact_sha256"],
        "legacy_artifact_identity_pins_verified": True,
        "seed_count": len(rows), "track_counts": EXPECTED_TRACK_COUNTS,
        "lineage_family_count": EXPECTED_LINEAGE_FAMILY_COUNT,
        "eligible_independence_group_count": 0, "actual_source_snapshot_count": 0,
        "actual_source_claim_count": 0, "actual_context_review_count": 0,
        "actual_credit_count": 0, "derived_index_row_count": 0,
        "pool_count": legacy_inventory["pool_count"],
        "must_not_sum_across_pools": True, "combined_unique_denominator": None,
        "metric_denominator": 0, "statistical_estimate": None,
        "metric_status": METRIC_STATUS,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
        "action_applied": False, "operational_effect": OPERATIONAL_EFFECT,
        "gate_status": GATE_STATUS, "blockers": blockers,
    }
    return with_self_hash(material)


def build_receipt_bytes(registry_raw: bytes, registry_inventory_raw: bytes, legacy_inventory_raw: bytes, legacy_artifacts: Mapping[str, bytes]) -> bytes:
    return canonical_file_bytes(_receipt_value(registry_raw, registry_inventory_raw, legacy_inventory_raw, legacy_artifacts))


def validate_receipt_bytes(raw: bytes, registry_raw: bytes, registry_inventory_raw: bytes, legacy_inventory_raw: bytes, legacy_artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    value = _json_document(raw, "source seed receipt", canonical=True)
    if value != _receipt_value(registry_raw, registry_inventory_raw, legacy_inventory_raw, legacy_artifacts):
        raise P0PresentedSourceSeedCandidateError("source seed receipt replay mismatch")
    _self(value, "artifact_sha256")
    return value


__all__ = [
    "COMPONENT_MANIFEST", "COMPONENT_MANIFEST_SHA256", "GATE_STATUS",
    "LEGACY_ARTIFACT_IDENTITIES", "LEGACY_ARTIFACT_PATHS", "METRIC_STATUS",
    "P0PresentedSourceSeedCandidateError", "SEED_SPECIFICATIONS",
    "build_legacy_quality_inventory_bytes", "build_receipt_bytes",
    "build_registry_bytes", "build_registry_inventory_bytes", "canonical_file_bytes",
    "canonical_sha256", "validate_legacy_quality_inventory_bytes",
    "validate_receipt_bytes", "validate_registry_bytes",
    "validate_registry_inventory_bytes",
]
