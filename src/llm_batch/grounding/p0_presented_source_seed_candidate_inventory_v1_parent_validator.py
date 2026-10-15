"""Independent replay of the presented eight-source and seven-pool inventory.

No producer module is imported. URL specifications, historical byte identity
pins, row projections, pool grains, and zero-credit boundaries are duplicated.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import unicodedata
from typing import Any, Mapping


ROW_SCHEMA = "p0_presented_source_seed_candidate_row_v1"
REGISTRY_INVENTORY_SCHEMA = "p0_presented_source_seed_registry_inventory_v1"
LEGACY_ROW_SCHEMA = "p0_presented_legacy_pool_artifact_row_v1"
POOL_SUMMARY_SCHEMA = "p0_presented_legacy_pool_summary_v1"
ROLE_BLOCKER_SCHEMA = "p0_presented_legacy_pool_role_blocker_v1"
LEGACY_INVENTORY_SCHEMA = "p0_presented_legacy_pool_quality_inventory_v1"
RECEIPT_SCHEMA = "p0_presented_source_seed_candidate_receipt_v1"
PARENT_RECEIPT_SCHEMA = "p0_presented_source_seed_candidate_parent_receipt_v1"
COMPONENT_MANIFEST_SCHEMA = "p0_presented_source_seed_candidate_component_manifest_v1"
COMPONENT_VERSION = "presented-source-seed-candidate-inventory-v1"
ORIGIN = "PRESENTED_UNVERIFIED"
EFFECT = "NONE_SHADOW_ONLY"
METRIC = "NOT_ESTIMABLE"
CHILD_GATE = "NO_GO_PRESENTED_SOURCE_SEEDS_ONLY"
PARENT_GATE_STATUS = "NO_GO_INDEPENDENT_PRESENTED_SOURCE_SEED_REPLAY_ONLY"
MAX_BYTES = 4 * 1024 * 1024

RUN_SPEC = "out/candidate_set_nil_shadow_harness_20260711/v8/run_spec.json"
COMPARISON = "out/candidate_set_nil_shadow_harness_20260711/v8/comparison.json"
LEDGER = "docs/devs/p1_candidate_set_nil_golden18_label_ledger_20260711.json"
REFRESH = "out/completed779_improvement_goal_20260622/source_correctness_refresh_20260622/source_correctness_refresh_queue.json"
JUDGE = "out/judge3905_p0_seed_registry/judge3905_p0_candidate_ledger_shadow.jsonl"
P01 = "rows/full_post_judge_rows_p01.md"
P02 = "rows/full_post_judge_rows_p02.md"
IDENTITIES = (
    ("RUN_SPEC", RUN_SPEC, 3249, "148c903cbae7664c79b5aa6cc4f0e7b5b7f20d243be9c050a746a7e5d3f71626"),
    ("COMPARISON", COMPARISON, 124062, "0dc5719e85e758ea4f3f68e89d44b48248b7117849bc61a45b411aef5220afe9"),
    ("LABEL_LEDGER", LEDGER, 5434, "b7e75467744a1cf769763d459e3ebcfbf613bbaff703a0b6dedd55d29d905998"),
    ("SOURCE_REFRESH_QUEUE", REFRESH, 86246, "241b6c299066152b18fd84b7002235f38c8ce546ed0e59d96b20d0c23a48921f"),
    ("JUDGE3905_SHADOW", JUDGE, 2425983, "a768df069a68acc851d44590f9ff467b2aff23619377b8de14d9c1a18005eae3"),
    ("ROWS_P01", P01, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    ("ROWS_P02", P02, 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
)
PATHS = tuple(item[1] for item in IDENTITIES)
SEEDS = (
    ("seed-arca-novelchannel-abbreviation", "A", "https://arca.live/w/novelchannel/%EC%86%8C%EC%84%A4%20%EC%B6%95%EC%95%BD%EC%96%B4", "WORK_ALIAS_COLLABORATIVE_LIST", "lineage-arca-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-genrenovel-7614173", "A", "https://gall.dcinside.com/mgallery/board/view?id=genrenovel&no=7614173", "WORK_ALIAS_DASH_LIST_BACKUP", "lineage-arca-abbreviation-list", "BACKUP_SAME_LINEAGE"),
    ("seed-fmkorea-9330585139", "A", "https://www.fmkorea.com/9330585139", "WORK_ALIAS_EQUALS_LIST", "lineage-fmkorea-abbreviation-list", "PRIMARY_CANDIDATE"),
    ("seed-dc-tgijjdd-217475", "B", "https://gall.dcinside.com/mgallery/board/view/?id=tgijjdd&no=217475", "COMMUNITY_GLOSSARY_FREE_PARAGRAPH", "lineage-dc-webnovel-jargon-list", "PRIMARY_CANDIDATE"),
    ("seed-tanma-ganadala", "B", "https://tanma.kr/data/webnovel_terms_ganadala.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-mabasa", "B", "https://tanma.kr/data/webnovel_terms_mabasa.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-ajacha", "B", "https://tanma.kr/data/webnovel_terms_ajacha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
    ("seed-tanma-katapaha", "B", "https://tanma.kr/data/webnovel_terms_katapaha.html", "COMMUNITY_GLOSSARY_STRUCTURED_ENTRY_LIST", "lineage-tanma-webnovel-terms", "PARTITION_OF_SAME_SOURCE"),
)
CAPABILITIES = ("raw_capture_allowed", "parser_execution_allowed", "claim_derivation_allowed", "derived_index_allowed", "publication_evidence_allowed")
FALSE_AUTHORITY = ("source_enumeration_complete", "capture_authority_verified", "rights_authority_verified", "adapter_runtime_verified", "source_attestation_verified", "code_identity_verified", "actual_authority_granted", "production_approval", "full_scan_approval", "p0_phase_exit")
JUDGE_TOP = frozenset({"post_id", "seed_group", "disagreement_type", "severity", "agree", "likely_correct", "shadow_label", "candidate_ledger", "source", "judge"})
JUDGE_LEDGER = frozenset({"pipeline_official_title", "title_candidates", "candidate_count", "title_resolution_state", "title_resolution_allowed", "work_resolution", "discussion_type", "topicality", "is_novel_related", "is_resolved_work_discussion", "anchor_type", "anchor_strength", "context_sources", "has_evidence_catalog", "official_title_lint_reasons", "identity_consistency_lint_reasons", "judge_likely_correct", "judge_note", "judge_claude_take"})
JUDGE_SOURCE = frozenset({"source_path", "title", "url", "image_count", "has_image_url", "comment_count"})
JUDGE_JUDGE = frozenset({"claude_take", "note", "batch"})


class P0PresentedSourceSeedParentError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (RecursionError, UnicodeEncodeError, TypeError, ValueError) as exc:
        raise P0PresentedSourceSeedParentError("canonical JSON invalid") from exc


def _file(value: Any) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _raw(raw: bytes) -> str:
    if type(raw) is not bytes:
        raise P0PresentedSourceSeedParentError("raw input must be bytes")
    return hashlib.sha256(raw).hexdigest()


def _seal(material: Mapping[str, Any], field: str = "artifact_sha256") -> dict[str, Any]:
    clean = dict(material)
    clean.pop(field, None)
    return {**clean, field: _digest(clean)}


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise P0PresentedSourceSeedParentError("duplicate JSON key")
        output[key] = value
    return output


def _constant(value: str) -> None:
    raise P0PresentedSourceSeedParentError(f"nonfinite JSON: {value}")


def _obj(raw: bytes, label: str, canonical: bool = False) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES or raw.startswith(b"\xef\xbb\xbf") or (canonical and b"\r" in raw):
        raise P0PresentedSourceSeedParentError(f"{label} framing invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        if unicodedata.normalize("NFC", text) != text:
            raise P0PresentedSourceSeedParentError(f"{label} NFC invalid")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError, TypeError) as exc:
        if isinstance(exc, P0PresentedSourceSeedParentError):
            raise
        raise P0PresentedSourceSeedParentError(f"{label} parse invalid") from exc
    if type(value) is not dict or (canonical and raw != _file(value)):
        raise P0PresentedSourceSeedParentError(f"{label} canonical mismatch")
    return value


def _lines(raw: bytes, label: str, canonical: bool = False) -> list[dict[str, Any]]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise P0PresentedSourceSeedParentError(f"{label} framing invalid")
    rows = []
    for line in raw.splitlines():
        if not line:
            raise P0PresentedSourceSeedParentError(f"{label} blank row")
        rows.append(_obj(line + b"\n", label, canonical))
    return rows


def _int(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise P0PresentedSourceSeedParentError(f"{label} integer invalid")
    return value


def _bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise P0PresentedSourceSeedParentError(f"{label} bool invalid")
    return value


def _component_sha() -> str:
    manifest = {
        "schema_version": COMPONENT_MANIFEST_SCHEMA, "component_version": COMPONENT_VERSION,
        "record_origin": ORIGIN, "expected_seed_count": 8,
        "expected_track_counts": {"A": 3, "B": 5}, "expected_lineage_family_count": 4,
        "seed_specifications_sha256": _digest([list(item) for item in SEEDS]),
        "legacy_artifact_identities": [{"artifact_role": role, "path": path, "bytes": size, "sha256": digest} for role, path, size, digest in IDENTITIES],
        "legacy_artifact_identities_sha256": _digest([list(item) for item in IDENTITIES]),
        "max_legacy_artifact_bytes": MAX_BYTES,
        "network_access_allowed": False, "filesystem_access_allowed": False,
        "environment_access_allowed": False, "clock_access_allowed": False,
        "random_access_allowed": False, "subprocess_access_allowed": False,
        "import_side_effects_allowed": False, "semantic_field_injection_allowed": False,
        "legacy_binding_repair_allowed": False, "actual_credit_allowed": False,
    }
    return _digest(manifest)


def _seed_rows() -> list[dict[str, Any]]:
    rows = []
    for sequence, (seed_id, track, url, hint, lineage, relation) in enumerate(SEEDS, start=1):
        material = {
            "schema_version": ROW_SCHEMA, "seed_sequence": sequence, "seed_id": seed_id,
            "track": track, "record_type": "WORK_ALIAS_LIST" if track == "A" else "COMMUNITY_LEXICON_LIST",
            "canonical_url": url, "format_hint": hint,
            "source_profile_status": "PENDING_CAPTURE_ADAPTER", "source_lineage": lineage,
            "independence_group_id": lineage, "lineage_relation": relation,
            "status": ORIGIN, "attested_at": None, "attestation_status": "NOT_ATTESTED",
            "capture_status": "NOT_RUN", "parser_status": "NOT_RUN",
            "rights_status": "UNKNOWN_FAIL_CLOSED", "semantic_status": "REFERENCE_CANDIDATE_ONLY",
            "independence_eligible": False, **{field: False for field in CAPABILITIES},
        }
        rows.append({**material, "row_sha256": _digest(material)})
    return rows


def _registry_inventory(registry_raw: bytes, rows: list[dict[str, Any]]) -> dict[str, Any]:
    families = sorted({row["source_lineage"] for row in rows})
    return _seal({
        "schema_version": REGISTRY_INVENTORY_SCHEMA, "record_origin": ORIGIN,
        "component_version": COMPONENT_VERSION, "component_manifest_sha256": _component_sha(),
        "registry_raw_sha256": _raw(registry_raw), "registry_row_count": 8,
        "registry_rows_sha256": _digest(rows),
        "track_counts": dict(sorted(Counter(row["track"] for row in rows).items())),
        "lineage_family_count": 4, "lineage_family_ids_sha256": _digest(families),
        "presented_unverified_count": 8, "rights_unknown_count": 8,
        "capture_not_run_count": 8, "parser_not_run_count": 8,
        "attestation_not_run_count": 8, "eligible_independence_group_count": 0,
    })


def _golden(ledger: dict[str, Any], comparison: dict[str, Any]) -> dict[str, int]:
    rows = ledger.get("rows")
    if ledger.get("schema_version") != "candidate-set-nil-label-ledger-v1" or type(rows) is not list or len(rows) != 18:
        raise P0PresentedSourceSeedParentError("golden18 shape invalid")
    pairs = []
    counts: Counter[str] = Counter()
    for row in rows:
        if type(row) is not dict:
            raise P0PresentedSourceSeedParentError("golden row invalid")
        post_id = _int(row.get("post_id"), "golden post", 1)
        kind = row.get("truth_kind")
        if kind not in {"CANDIDATE", "NIL", "UNJUDGED"}:
            raise P0PresentedSourceSeedParentError("golden label invalid")
        title = row.get("expected_title")
        if (kind == "CANDIDATE" and (type(title) is not str or not title.strip())) or (kind != "CANDIDATE" and title is not None) or (kind == "UNJUDGED" and row.get("expected_action") != "ABSTAIN"):
            raise P0PresentedSourceSeedParentError("golden label/title invalid")
        pairs.append((post_id, kind)); counts[kind] += 1
    if len({post for post, _ in pairs}) != 18:
        raise P0PresentedSourceSeedParentError("golden post duplicate")
    expected = {"rows": 18, "candidate_truth": counts["CANDIDATE"], "nil_truth": counts["NIL"], "unjudged": counts["UNJUDGED"]}
    shown = ledger.get("counts")
    if type(shown) is not dict or set(shown) != set(expected) or any(_int(shown[key], key) != value for key, value in expected.items()) or sum(expected[key] for key in ("candidate_truth", "nil_truth", "unjudged")) != 18:
        raise P0PresentedSourceSeedParentError("golden counts invalid")
    crows = comparison.get("rows")
    summary = comparison.get("summary")
    if comparison.get("schema_version") != "candidate-set-nil-shadow-saved-artifact-v1" or type(crows) is not list or len(crows) != 18 or type(summary) is not dict:
        raise P0PresentedSourceSeedParentError("comparison shape invalid")
    cpairs = [(_int(row.get("post_id"), "comparison post", 1), row.get("truth_kind")) for row in crows if type(row) is dict]
    if len(cpairs) != 18 or cpairs != pairs or summary.get("generation_status") != "UNKNOWN" or summary.get("candidate_set_recall") != "NOT_EVALUABLE" or _int(summary.get("unjudged"), "comparison unjudged") != expected["unjudged"]:
        raise P0PresentedSourceSeedParentError("comparison replay invalid")
    if _int(summary["candidate_truth"].get("expected"), "candidate expected") != expected["candidate_truth"] or _int(summary["nil_truth"].get("expected"), "nil expected") != expected["nil_truth"]:
        raise P0PresentedSourceSeedParentError("comparison label counts invalid")
    return expected


def _refresh(queue: dict[str, Any]) -> dict[str, int]:
    rows = queue.get("rows")
    if queue.get("schema_version") != 1 or queue.get("semantic_quality") != "REVIEW-LOCKED" or _bool(queue.get("full_scan_approval"), "refresh full scan") or type(rows) is not list or len(rows) != 39:
        raise P0PresentedSourceSeedParentError("refresh gate/shape invalid")
    posts: set[int] = set(); urls = pending = 0
    for row in rows:
        if type(row) is not dict:
            raise P0PresentedSourceSeedParentError("refresh row invalid")
        post = _int(row.get("post_id"), "refresh post", 1)
        if post in posts:
            raise P0PresentedSourceSeedParentError("refresh duplicate post")
        posts.add(post)
        source_urls = row.get("source_urls")
        if type(source_urls) is not list or any(type(url) is not str or not url.startswith("http") for url in source_urls):
            raise P0PresentedSourceSeedParentError("refresh urls invalid")
        urls += len(source_urls); pending += row.get("acceptance_status") == "pending_source_refresh"
    coverage = queue.get("coverage")
    if len(posts) != 39 or urls != 87 or pending != 39 or type(coverage) is not dict or _int(coverage.get("rows"), "coverage rows") != 39 or _int(coverage.get("unique_post_ids"), "coverage unique") != 39:
        raise P0PresentedSourceSeedParentError("refresh raw counts invalid")
    return {"rows": 39, "unique": 39, "urls": 87, "pending": 39}


def _judge(raw: bytes) -> dict[str, int]:
    rows = _lines(raw, "judge3905")
    if len(rows) != 1505:
        raise P0PresentedSourceSeedParentError("judge row count invalid")
    posts: set[int] = set(); positive = titles = evidence = web = 0
    for row in rows:
        if set(row) != JUDGE_TOP:
            raise P0PresentedSourceSeedParentError("judge top shape invalid")
        post = _int(row["post_id"], "judge post", 1)
        if post in posts:
            raise P0PresentedSourceSeedParentError("judge duplicate post")
        posts.add(post)
        ledger, source, judge = row["candidate_ledger"], row["source"], row["judge"]
        if type(ledger) is not dict or set(ledger) != JUDGE_LEDGER or type(source) is not dict or set(source) != JUDGE_SOURCE or type(judge) is not dict or set(judge) != JUDGE_JUDGE:
            raise P0PresentedSourceSeedParentError("judge nested shape invalid")
        count = _int(ledger["candidate_count"], "candidate count")
        if type(ledger["title_candidates"]) is not list or count != len(ledger["title_candidates"]):
            raise P0PresentedSourceSeedParentError("candidate count mismatch")
        positive += count > 0
        title = ledger["pipeline_official_title"]
        if title is not None and (type(title) is not str or not title.strip()):
            raise P0PresentedSourceSeedParentError("judge title invalid")
        titles += title is not None
        evidence += _bool(ledger["has_evidence_catalog"], "judge evidence")
        if type(judge["note"]) is not str:
            raise P0PresentedSourceSeedParentError("judge note invalid")
        web += "web_unverified" in judge["note"]
    result = {"rows": 1505, "unique": len(posts), "candidate_positive": positive, "public_titles": titles, "evidence": evidence, "web_unverified": web}
    if result != {"rows": 1505, "unique": 1505, "candidate_positive": 0, "public_titles": 198, "evidence": 2, "web_unverified": 649}:
        raise P0PresentedSourceSeedParentError("judge raw counts invalid")
    return result


def _pool(sequence: int, pool_id: str, role: str, grain: str, **values: Any) -> dict[str, Any]:
    material = {"schema_version": POOL_SUMMARY_SCHEMA, "pool_sequence": sequence, "pool_id": pool_id, "source_artifact_role": role, "grain": grain, "row_count": None, "unique_post_id_count": None, "url_reference_count": None, "candidate_labeled_count": None, "nil_labeled_count": None, "unjudged_count": None, "pending_count": None, "candidate_count_positive_count": None, "public_title_present_count": None, "evidence_catalog_present_count": None, "web_unverified_count": None, "empty_bytes_verified": False, "metric_status": METRIC}
    material.update(values)
    return {**material, "pool_sha256": _digest(material)}


def _legacy(artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    if type(artifacts) is not dict or tuple(artifacts.keys()) != PATHS:
        raise P0PresentedSourceSeedParentError("legacy ordered allowlist invalid")
    for role, path, size, digest in IDENTITIES:
        raw = artifacts[path]
        if type(raw) is not bytes or len(raw) != size or _raw(raw) != digest:
            raise P0PresentedSourceSeedParentError(f"legacy identity mismatch: {role}")
    run, comp, ledger = _obj(artifacts[RUN_SPEC], "run spec"), _obj(artifacts[COMPARISON], "comparison"), _obj(artifacts[LEDGER], "ledger")
    refresh = _obj(artifacts[REFRESH], "refresh")
    if run.get("schema_version") != "candidate-set-nil-shadow-runspec-v1":
        raise P0PresentedSourceSeedParentError("run spec schema invalid")
    golden, rc, jc = _golden(ledger, comp), _refresh(refresh), _judge(artifacts[JUDGE])
    expected_run, expected_ledger = comp.get("run_spec"), run.get("artifacts", {}).get("label_ledger")
    if type(expected_run) is not dict or type(expected_ledger) is not dict:
        raise P0PresentedSourceSeedParentError("parent refs invalid")
    rows = []
    for sequence, (role, path, size, digest) in enumerate(IDENTITIES, start=1):
        parent_bytes = parent_sha = None
        if role == "RUN_SPEC":
            if expected_run.get("path") != path:
                raise P0PresentedSourceSeedParentError("run parent path invalid")
            parent_sha = expected_run.get("sha256")
            status = "SHA_MATCH_BYTES_UNAVAILABLE" if parent_sha == digest and "bytes" not in expected_run else "STALE_PARENT_BINDING"
        elif role == "LABEL_LEDGER":
            if expected_ledger.get("path") != path:
                raise P0PresentedSourceSeedParentError("ledger parent path invalid")
            parent_bytes, parent_sha = expected_ledger.get("bytes"), expected_ledger.get("sha256")
            status = "PARENT_BINDING_MATCH" if parent_bytes == size and parent_sha == digest else "STALE_PARENT_BINDING"
        else:
            status = "IDENTITY_PIN_MATCH_NO_PARENT_BINDING"
        material = {"schema_version": LEGACY_ROW_SCHEMA, "artifact_sequence": sequence, "artifact_role": role, "path": path, "actual_bytes": len(artifacts[path]), "actual_sha256": _raw(artifacts[path]), "pinned_bytes": size, "pinned_sha256": digest, "parent_expected_bytes": parent_bytes, "parent_expected_sha256": parent_sha, "binding_status": status, "identity_pin_verified": True, "stale_parent_binding": status == "STALE_PARENT_BINDING"}
        rows.append({**material, "row_sha256": _digest(material)})
    stale = [row["artifact_role"] for row in rows if row["stale_parent_binding"]]
    if stale != ["LABEL_LEDGER"]:
        raise P0PresentedSourceSeedParentError("unexpected stale role")
    blockers = [{"schema_version": ROLE_BLOCKER_SCHEMA, "artifact_role": "LABEL_LEDGER", "blocker_code": "LEGACY_LABEL_LEDGER_SHA256_BINDING_STALE"}]
    pools = [
        _pool(1, "golden18_label_pool", "LABEL_LEDGER", "GOLDEN18_POST_LABEL_ROW", row_count=18, unique_post_id_count=18, candidate_labeled_count=golden["candidate_truth"], nil_labeled_count=golden["nil_truth"], unjudged_count=golden["unjudged"]),
        _pool(2, "source_refresh_pool", "SOURCE_REFRESH_QUEUE", "SOURCE_REFRESH_POST_QUEUE_ROW", row_count=rc["rows"], unique_post_id_count=rc["unique"], url_reference_count=rc["urls"], pending_count=rc["pending"]),
        _pool(3, "judge3905_shadow_pool", "JUDGE3905_SHADOW", "JUDGE3905_SHADOW_POST_ROW", row_count=jc["rows"], unique_post_id_count=jc["unique"], candidate_count_positive_count=jc["candidate_positive"], public_title_present_count=jc["public_titles"], evidence_catalog_present_count=jc["evidence"], web_unverified_count=jc["web_unverified"]),
        _pool(4, "reserved_p01_pool", "ROWS_P01", "RESERVED_EMPTY_P01_BYTES", row_count=0, empty_bytes_verified=True),
        _pool(5, "reserved_p02_pool", "ROWS_P02", "RESERVED_EMPTY_P02_BYTES", row_count=0, empty_bytes_verified=True),
    ]
    if len({pool["grain"] for pool in pools}) != 5:
        raise P0PresentedSourceSeedParentError("pool grains not distinct")
    return _seal({"schema_version": LEGACY_INVENTORY_SCHEMA, "record_origin": ORIGIN, "component_version": COMPONENT_VERSION, "component_manifest_sha256": _component_sha(), "artifact_rows": rows, "artifact_rows_sha256": _digest(rows), "artifact_count": 7, "artifact_identity_pins_verified": True, "pool_summaries": pools, "pool_summaries_sha256": _digest(pools), "pool_count": 5, "distinct_pool_grain_count": 5, "must_not_sum_across_pools": True, "combined_unique_denominator": None, "combined_metric_denominator": 0, "legacy_metric_status": METRIC, "stale_parent_binding_count": 1, "stale_parent_binding_roles": stale, "role_blockers": blockers, "role_blockers_sha256": _digest(blockers), "role_blocker_count": 1})


def validate_presented_source_seed_candidate_bundle(*, registry_raw: bytes, registry_inventory_raw: bytes, legacy_inventory_raw: bytes, receipt_raw: bytes, legacy_artifacts: Mapping[str, bytes]) -> dict[str, object]:
    rows = _seed_rows()
    if registry_raw != b"".join(_file(row) for row in rows) or _lines(registry_raw, "registry", True) != rows:
        raise P0PresentedSourceSeedParentError("registry differs from independent specification")
    inventory = _registry_inventory(registry_raw, rows)
    if registry_inventory_raw != _file(inventory):
        raise P0PresentedSourceSeedParentError("registry inventory independent replay mismatch")
    legacy = _legacy(legacy_artifacts)
    if legacy_inventory_raw != _file(legacy):
        raise P0PresentedSourceSeedParentError("legacy inventory independent replay mismatch")
    blockers = ["SOURCE_BYTES_NOT_CAPTURED", "SOURCE_PARSER_NOT_RUN", "SOURCE_ATTESTATION_NOT_RUN", "SOURCE_RIGHTS_UNKNOWN", "ACTUAL_SOURCE_AND_CONTEXT_COUNTS_ZERO", "LEGACY_LABEL_LEDGER_SHA256_BINDING_STALE"]
    receipt = _seal({"schema_version": RECEIPT_SCHEMA, "record_origin": ORIGIN, "component_version": COMPONENT_VERSION, "component_manifest_sha256": _component_sha(), "registry_raw_sha256": _raw(registry_raw), "registry_inventory_raw_sha256": _raw(registry_inventory_raw), "registry_inventory_artifact_sha256": inventory["artifact_sha256"], "legacy_inventory_raw_sha256": _raw(legacy_inventory_raw), "legacy_inventory_artifact_sha256": legacy["artifact_sha256"], "legacy_artifact_identity_pins_verified": True, "seed_count": 8, "track_counts": {"A": 3, "B": 5}, "lineage_family_count": 4, "eligible_independence_group_count": 0, "actual_source_snapshot_count": 0, "actual_source_claim_count": 0, "actual_context_review_count": 0, "actual_credit_count": 0, "derived_index_row_count": 0, "pool_count": 5, "must_not_sum_across_pools": True, "combined_unique_denominator": None, "metric_denominator": 0, "statistical_estimate": None, "metric_status": METRIC, **{field: False for field in FALSE_AUTHORITY}, "action_applied": False, "operational_effect": EFFECT, "gate_status": CHILD_GATE, "blockers": blockers})
    if receipt_raw != _file(receipt):
        raise P0PresentedSourceSeedParentError("receipt independent replay mismatch")
    _obj(receipt_raw, "receipt", True)
    material = {"schema_version": PARENT_RECEIPT_SCHEMA, "expected_component_manifest_sha256": _component_sha(), "registry_raw_sha256": _raw(registry_raw), "registry_inventory_raw_sha256": _raw(registry_inventory_raw), "legacy_inventory_raw_sha256": _raw(legacy_inventory_raw), "receipt_raw_sha256": _raw(receipt_raw), "independent_exact_seed_specification_verified": True, "independent_registry_inventory_replay_verified": True, "independent_legacy_byte_inventory_replay_verified": True, "independent_pool_statistics_replay_verified": True, "legacy_binding_repair_performed": False, "must_not_sum_across_pools": True, "combined_unique_denominator": None, "seed_count": 8, "actual_credit_count": 0, "derived_index_row_count": 0, "metric_denominator": 0, "metric_status": METRIC, "actual_authority_granted": False, "production_approval": False, "full_scan_approval": False, "p0_phase_exit": False, "action_applied": False, "operational_effect": EFFECT, "gate_status": PARENT_GATE_STATUS}
    return {**material, "receipt_sha256": _digest(material)}


EXPECTED_COMPONENT_MANIFEST_SHA256 = _component_sha()

__all__ = ["EXPECTED_COMPONENT_MANIFEST_SHA256", "P0PresentedSourceSeedParentError", "PARENT_GATE_STATUS", "PARENT_RECEIPT_SCHEMA", "validate_presented_source_seed_candidate_bundle"]
